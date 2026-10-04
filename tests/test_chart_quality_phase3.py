from __future__ import annotations

from datetime import datetime, timezone
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from decision_system import PortfolioRisk, calculate_drawdown_state
import run_screener
from research.chart_quality import (
    CHART_QUALITY_COMPONENTS,
    DISTRIBUTION,
    PHASE3_RESEARCH_FIELDS,
    calculate_chart_quality_fields,
)
from research.setup_lanes import PULLBACK_LANE, annotate_setup_lanes
from scripts.validate_report import validate_csv_semantics


def history_from_close(
    close: list[float] | np.ndarray,
    *,
    volume: list[float] | np.ndarray | None = None,
    spread: float = 1.0,
) -> pd.DataFrame:
    values = np.asarray(close, dtype=float)
    volumes = (
        np.full(len(values), 1_000_000.0)
        if volume is None
        else np.asarray(volume, dtype=float)
    )
    dates = pd.bdate_range("2025-01-02", periods=len(values))
    return pd.DataFrame(
        {
            "Open": values - 0.2,
            "High": values + spread,
            "Low": values - spread,
            "Close": values,
            "Volume": volumes,
        },
        index=dates,
    )


def component(
    frame: pd.DataFrame,
    name: str,
    *,
    benchmark: pd.DataFrame | None = None,
    as_of: object | None = None,
    recent_rs_score: float | None = 80.0,
    pivot: float | None = None,
) -> dict[str, object]:
    fields = calculate_chart_quality_fields(
        frame,
        benchmark=benchmark,
        as_of=as_of,
        recent_rs_score=recent_rs_score,
        pivot=pivot,
    )
    prefix = f"CQ {name}"
    return {
        "status": fields[f"{prefix} Status"],
        "state": fields[f"{prefix} State"],
        "value": fields[f"{prefix} Value"],
        "evidence": json.loads(fields[f"{prefix} Evidence"]),
        "warnings": fields[f"{prefix} Warnings"],
        "reason": fields[f"{prefix} Reason"],
    }


def benchmark(
    periods: int, *, start: float = 100.0, end: float = 100.0
) -> pd.DataFrame:
    return history_from_close(np.linspace(start, end, periods))


def production_context() -> dict[str, object]:
    return {
        "market_regime": SimpleNamespace(regime="Strong"),
        "market_new_risk_allowed": True,
        "drawdown": calculate_drawdown_state(100_000, 100_000),
        "portfolio_status": {
            "portfolio": PortfolioRisk((), 0.0, 3.0, 3.0, {}, {}, {}, ()),
            "open_position_count": 0,
            "portfolio_new_risk_allowed": True,
            "new_initial_risk_r_today": 0.0,
            "new_position_count_today": 0,
        },
    }


def production_candidate(ticker: str, score: float = 82.0, **updates: object):
    row: dict[str, object] = {
        "Ticker": ticker,
        "Category": "Pullback Candidates",
        "Sector": "Technology",
        "Industry": "Software",
        "Theme": "Industry: Software",
        "Recent RS Score": 88.0,
        "RS Trend": "Improving",
        "Industry Qualified": True,
        "Sister Confirmation": True,
        "Tightness Label": "Tight",
        "VCP Label": "Good VCP",
        "Pullback Quality": "A - Ideal Pullback",
        "Trade Plan Confidence": "High",
        "Planned Entry": 100.0,
        "Initial Stop": 95.0,
        "Realistic Target": 110.0,
        "Realistic Target Source": "observed prior-high resistance",
        "Reward/Risk Ratio": 2.0,
        "Extension Status": "Not Extended",
        "Distance From Pivot %": 1.0,
        "Nearest Support Distance ATR": 0.5,
        "Volume Ratio": 1.0,
        "Price Freshness Status": "CURRENT",
        "Price Data Warning": "",
        "Final Score": score,
    }
    row.update(updates)
    return row


def test_prior_advance_rewards_orderly_path_over_equal_return_spike():
    orderly = history_from_close(np.r_[np.linspace(80, 100, 71), np.full(10, 100)])
    spike_closes = np.r_[np.full(70, 80.0), 100.0, np.full(10, 100.0)]
    spike = history_from_close(spike_closes)

    good = component(orderly, "Prior Advance Quality")
    poor = component(spike, "Prior Advance Quality")

    assert good["value"] > poor["value"]
    assert good["state"] != poor["state"]
    assert poor["evidence"]["largest_positive_progress_share"] > 0.5


def test_prior_advance_internal_drawdown_and_reversals_reduce_quality():
    smooth = np.r_[np.linspace(80, 105, 71), np.full(10, 105)]
    jagged = smooth.copy()
    jagged[20:31] = np.linspace(88, 76, 11)
    jagged[31:71] = np.linspace(78, 105, 40)

    good = component(history_from_close(smooth), "Prior Advance Quality")
    weak = component(history_from_close(jagged), "Prior Advance Quality")

    assert (
        weak["evidence"]["maximum_drawdown_pct"]
        > good["evidence"]["maximum_drawdown_pct"]
    )
    assert weak["value"] < good["value"]


@pytest.mark.parametrize("periods", [20, 70])
def test_prior_advance_insufficient_or_missing_history_is_explicit(periods: int):
    frame = history_from_close(np.linspace(80, 100, periods))
    if periods == 70:
        frame.iloc[-20, frame.columns.get_loc("Close")] = np.nan
    result = component(frame, "Prior Advance Quality")
    assert result["status"] in {"INSUFFICIENT_HISTORY", "MISSING_DATA"}
    assert result["value"] is None


def test_smooth_uptrend_beats_equal_net_erratic_trend_and_reversals_are_counted():
    smooth = history_from_close(np.linspace(80, 100, 61))
    alternating = np.linspace(80, 100, 61) + np.tile([0, 4, -4], 21)[:61]
    erratic = history_from_close(alternating)

    good = component(smooth, "Trend Smoothness")
    poor = component(erratic, "Trend Smoothness")

    assert good["value"] > poor["value"]
    assert (
        poor["evidence"]["large_reversal_count"]
        > good["evidence"]["large_reversal_count"]
    )


def test_flat_quiet_stock_is_not_a_smooth_uptrend():
    result = component(
        history_from_close(np.full(61, 100.0), spread=0.05), "Trend Smoothness"
    )
    assert result["state"] == "FLAT_OR_DIRECTIONLESS"
    assert result["state"] != "SMOOTH_UPTREND"


def test_trend_smoothness_insufficient_history_is_explicit():
    result = component(history_from_close(np.linspace(90, 100, 40)), "Trend Smoothness")
    assert result["status"] == "INSUFFICIENT_HISTORY"
    assert result["value"] is None


def distribution_frame(events: int) -> pd.DataFrame:
    close = np.linspace(100, 110, 70)
    volume = np.full(70, 1_000_000.0)
    frame = history_from_close(close, volume=volume, spread=0.8)
    for offset in range(events):
        position = -2 - offset * 3
        prior = float(frame["Close"].iloc[position - 1])
        frame.iloc[position, frame.columns.get_loc("Close")] = prior - 4.0
        frame.iloc[position, frame.columns.get_loc("High")] = prior + 1.0
        frame.iloc[position, frame.columns.get_loc("Low")] = prior - 5.0
        frame.iloc[position, frame.columns.get_loc("Volume")] = 2_000_000.0
    return frame


def test_repeated_wide_high_volume_down_bars_raise_distribution_penalty():
    one = component(distribution_frame(1), "Distribution / Wide-Bar Penalty")
    repeated = component(distribution_frame(4), "Distribution / Wide-Bar Penalty")
    assert repeated["value"] > one["value"]
    assert repeated["state"] in {"MODERATE", "HEAVY"}
    assert one["value"] <= 25


def test_normal_small_down_days_do_not_equal_distribution_events():
    close = 100 + np.sin(np.arange(70) / 3) * 0.2
    result = component(
        history_from_close(close, spread=0.4), "Distribution / Wide-Bar Penalty"
    )
    assert result["evidence"]["distribution_event_count"] == 0
    assert result["value"] == 0


def test_missing_volume_is_not_favourable_distribution_evidence():
    frame = distribution_frame(0)
    frame.iloc[-3, frame.columns.get_loc("Volume")] = np.nan
    result = component(frame, "Distribution / Wide-Bar Penalty")
    assert result["status"] == "MISSING_DATA"
    assert result["value"] is None


def test_negative_volume_is_invalid_distribution_evidence():
    frame = distribution_frame(0)
    frame.iloc[-3, frame.columns.get_loc("Volume")] = -1_000_000.0
    result = component(frame, "Distribution / Wide-Bar Penalty")
    assert result["status"] == "MISSING_DATA"
    assert result["value"] is None


def test_distribution_requires_positive_volume_baseline():
    frame = distribution_frame(0)
    frame.loc[:, "Volume"] = 0.0
    result = component(frame, "Distribution / Wide-Bar Penalty")
    assert result["status"] == "MISSING_DATA"
    assert result["value"] is None


def test_distribution_penalty_direction_is_explicitly_higher_is_worse():
    none = component(distribution_frame(0), "Distribution / Wide-Bar Penalty")
    heavy = component(distribution_frame(4), "Distribution / Wide-Bar Penalty")
    assert none["value"] < heavy["value"]
    assert "higher is worse" in heavy["warnings"].lower()


def test_overhead_congestion_is_heavier_than_clear_price_space():
    heavy = history_from_close(np.r_[np.full(60, 102.0), 100.0], spread=3.0)
    clear = history_from_close(np.r_[np.linspace(80, 94, 60), 100.0], spread=0.5)
    congested = component(heavy, "Overhead Supply")
    open_space = component(clear, "Overhead Supply")
    assert congested["value"] > open_space["value"]
    assert congested["state"] in {"MODERATE", "HEAVY"}
    assert open_space["state"] == "NO_OBSERVED_OVERHEAD"
    assert "volume_profile" not in congested["evidence"]


def test_future_high_does_not_affect_historical_overhead_supply():
    frame = history_from_close(np.r_[np.linspace(80, 94, 60), 100.0], spread=0.5)
    as_of = frame.index[-1]
    future = frame.copy()
    future.loc[as_of + pd.offsets.BDay(1)] = [100, 150, 99, 101, 5_000_000]
    assert component(frame, "Overhead Supply", as_of=as_of) == component(
        future, "Overhead Supply", as_of=as_of
    )


def test_overhead_supply_insufficient_history_is_explicit():
    result = component(history_from_close(np.linspace(90, 100, 60)), "Overhead Supply")
    assert result["status"] == "INSUFFICIENT_HISTORY"
    assert result["value"] is None


def contraction_frame(*, contracting: bool, dry_volume: bool = True) -> pd.DataFrame:
    base = np.linspace(90, 100, 65)
    amplitudes = np.linspace(4.0, 0.6, 65) if contracting else np.linspace(0.5, 5.0, 65)
    close = base + np.sin(np.arange(65) * 1.7) * amplitudes
    volume = np.full(65, 1_000_000.0)
    if dry_volume:
        volume[-5:] = 500_000.0
    return history_from_close(close, volume=volume, spread=amplitudes * 0.25 + 0.2)


def test_multi_dimensional_contraction_beats_one_dimension_only():
    full = component(contraction_frame(contracting=True), "Contraction Quality")
    price_only = component(
        contraction_frame(contracting=True, dry_volume=False), "Contraction Quality"
    )
    assert full["value"] > price_only["value"]
    assert full["state"] == "STRONG_MULTI_DIMENSIONAL"
    assert price_only["state"] == "PRICE_CONTRACTION_ONLY"


def test_expanding_volatility_is_not_constructive_contraction():
    result = component(contraction_frame(contracting=False), "Contraction Quality")
    assert result["state"] == "EXPANDING"
    assert result["state"] != "STRONG_MULTI_DIMENSIONAL"


def test_missing_volume_is_not_volume_dry_up_and_nulls_value():
    frame = contraction_frame(contracting=True)
    frame.iloc[-2, frame.columns.get_loc("Volume")] = np.nan
    result = component(frame, "Contraction Quality")
    assert result["state"] == "PRICE_CONTRACTION_VOLUME_UNKNOWN"
    assert result["value"] is None
    assert result["evidence"]["volume_dry_up_ratio"] is None


def test_negative_volume_cannot_receive_contraction_credit():
    frame = contraction_frame(contracting=True)
    frame.iloc[-5:, frame.columns.get_loc("Volume")] = -1_000_000.0
    result = component(frame, "Contraction Quality")
    assert result["status"] == "MISSING_DATA"
    assert result["value"] is None
    assert result["evidence"]["volume_dry_up_ratio"] is None


@pytest.mark.parametrize("overflow_window", ["prior", "recent"])
def test_non_finite_volume_aggregates_cannot_receive_contraction_credit(
    overflow_window: str,
):
    frame = contraction_frame(contracting=True)
    target = slice(-25, -5) if overflow_window == "prior" else slice(-5, None)
    frame.iloc[target, frame.columns.get_loc("Volume")] = 1e308
    result = component(frame, "Contraction Quality")
    assert result["status"] == "MISSING_DATA"
    assert result["value"] is None
    assert result["evidence"]["volume_dry_up_ratio"] is None
    assert "volume evidence unavailable" in result["reason"].lower()


def test_zero_range_denominators_cannot_receive_contraction_credit():
    frame = history_from_close(
        np.full(65, 100.0),
        volume=np.r_[np.full(60, 1_000_000.0), np.full(5, 500_000.0)],
        spread=0.0,
    )
    frame["Open"] = frame["Close"]
    result = component(frame, "Contraction Quality")
    assert result["status"] == "MISSING_DATA"
    assert result["value"] is None
    assert result["evidence"]["range_10_to_20_ratio"] is None
    assert result["evidence"]["adr20_to_adr60_ratio"] is None
    assert "undefined" in result["reason"].lower()


@pytest.mark.parametrize(
    "name",
    [
        "Distribution / Wide-Bar Penalty",
        "Overhead Supply",
        "Contraction Quality",
        "Support Respect",
    ],
)
def test_impossible_ohlc_geometry_fails_closed(name: str):
    frame = history_from_close(np.linspace(90, 105, 75))
    frame.iloc[-1, frame.columns.get_loc("High")] = 90.0
    frame.iloc[-1, frame.columns.get_loc("Low")] = 110.0
    result = component(frame, name)
    assert result["status"] == "MISSING_DATA"
    assert result["value"] is None


def test_sequential_contraction_is_deterministic():
    frame = contraction_frame(contracting=True)
    first = component(frame, "Contraction Quality")
    second = component(frame, "Contraction Quality")
    assert first == second
    assert first["evidence"]["sequential_contraction_count"] in {0, 1, 2}


def test_sequential_contraction_counts_both_adjacent_ten_session_blocks():
    frame = history_from_close(np.full(61, 100.0))
    for start, stop, spread in ((31, 41, 6.0), (41, 51, 4.0), (51, 61, 2.0)):
        frame.iloc[start:stop, frame.columns.get_loc("High")] = 100.0 + spread
        frame.iloc[start:stop, frame.columns.get_loc("Low")] = 100.0 - spread
    result = component(frame, "Contraction Quality")
    assert result["evidence"]["sequential_contraction_count"] == 2


def support_frame(*, broken: bool = False) -> pd.DataFrame:
    close = np.full(75, 100.0)
    close[-15:] = [
        101,
        100.2,
        101,
        100.1,
        101,
        100.3,
        101,
        100.2,
        101,
        100.1,
        101,
        100.4,
        101,
        100.3,
        101,
    ]
    if broken:
        close[-5:] = [99, 97, 96, 95, 94]
    frame = history_from_close(close, spread=0.7)
    if not broken:
        frame.loc[frame.index[-14::3], "Low"] = 99.3
    return frame


def test_repeated_support_holds_beat_repeated_breaches():
    held = component(support_frame(), "Support Respect")
    broken = component(support_frame(broken=True), "Support Respect")
    assert held["value"] > broken["value"]
    assert held["state"] in {"CONSTRUCTIVE", "STRONG"}
    assert broken["state"] == "BROKEN"


def test_near_ema_without_interaction_is_only_ambiguous():
    close = np.linspace(70, 100, 75)
    frame = history_from_close(close, spread=0.3)
    frame["High"] = frame["Close"] + 2.0
    result = component(frame, "Support Respect")
    assert result["state"] == "AMBIGUOUS_PROXIMITY"
    assert result["evidence"]["successful_interactions"] == 0


def test_broken_support_cannot_look_constructive_due_to_proximity():
    result = component(support_frame(broken=True), "Support Respect")
    assert result["state"] == "BROKEN"
    assert result["evidence"]["destructive_breach_count"] >= 1


def test_multiple_support_references_use_deterministic_priority():
    frame = history_from_close(np.full(75, 100.0), spread=0.5)
    result = component(frame, "Support Respect", pivot=100.0)
    assert result["evidence"]["reference_name"] == "EMA20"
    assert (
        component(
            frame.sample(frac=1.0, random_state=7), "Support Respect", pivot=100.0
        )
        == result
    )


def test_missing_support_evidence_is_explicit():
    frame = support_frame()
    frame.loc[:, "Close"] = np.nan
    result = component(frame, "Support Respect")
    assert result["status"] == "MISSING_DATA"
    assert result["value"] is None


def test_phase3_support_does_not_restore_favourable_phase2_non_member_quality():
    row = production_candidate(
        "NO_SUPPORT_DISTANCE",
        **{
            "Report Section": "Pattern Watchlist",
            "Pattern Discovery Status": "RESEARCH_ONLY",
            "Pattern Discovery Reason": "chart review only",
            "Final Decision": "WATCH",
            "Actionable": False,
            "Confirmed Setup": False,
            "Maximum Risk R": 0.0,
            "Maximum Risk Dollars": 0.0,
            "Maximum Shares": 0,
            "Setup Integrity": "PASS",
            "Nearest Support Distance ATR": np.nan,
            "Distance From EMA10 ATR": np.nan,
            "Distance From EMA20 ATR": np.nan,
            "Distance From MA50 ATR": np.nan,
            "CQ Support Respect State": "STRONG",
            "CQ Support Respect Reason": "repeated holds",
        },
    )
    annotated = annotate_setup_lanes(pd.DataFrame([row])).iloc[0]
    assert not annotated[f"{PULLBACK_LANE} Member"]
    assert annotated["Pullback Lane Quality"] == "AMBIGUOUS_SUPPORT"


def test_phase3_explanations_do_not_change_phase2_membership_scores_or_ranks():
    rows = []
    for ticker, quality in (("AAA", "STRONG"), ("BBB", "WEAK")):
        row = production_candidate(
            ticker,
            **{
                "Report Section": "Pattern Watchlist",
                "Pattern Discovery Status": "RESEARCH_ONLY",
                "Pattern Discovery Reason": "chart review only",
                "Final Decision": "WATCH",
                "Actionable": False,
                "Confirmed Setup": False,
                "Maximum Risk R": 0.0,
                "Maximum Risk Dollars": 0.0,
                "Maximum Shares": 0,
                "Setup Integrity": "PASS",
                "10 Day Range %": 7.0,
                "20 Day Range %": 13.0,
                "ADR20 %": 3.0,
                "ADR60 %": 4.2,
                "VCP Ratio": 0.71,
                "Distance From EMA10 ATR": 0.5,
                "Distance From EMA20 ATR": 0.8,
                "Distance From MA50 ATR": 1.4,
                "CQ Contraction Quality State": quality,
                "CQ Contraction Quality Reason": f"{quality.lower()} contraction",
            },
        )
        rows.append(row)
    first = annotate_setup_lanes(pd.DataFrame(rows)).set_index("Ticker")
    swapped_rows = [dict(rows[0]), dict(rows[1])]
    swapped_rows[0]["CQ Contraction Quality State"] = "WEAK"
    swapped_rows[1]["CQ Contraction Quality State"] = "STRONG"
    second = annotate_setup_lanes(pd.DataFrame(swapped_rows)).set_index("Ticker")
    for suffix in ("Member", "Score", "Rank"):
        pd.testing.assert_series_equal(
            first[f"Tight Base / VCP {suffix}"],
            second[f"Tight Base / VCP {suffix}"],
        )
    assert (
        first.at["AAA", "Tight Base / VCP Reason"]
        != second.at["AAA", "Tight Base / VCP Reason"]
    )


def test_persistent_rs_beats_one_day_spike_with_same_current_level():
    spy = benchmark(70)
    persistent = history_from_close(np.linspace(100, 120, 70))
    spike = history_from_close(np.r_[np.full(69, 100.0), 120.0])
    sustained = component(persistent, "Relative Strength Persistence", benchmark=spy)
    sudden = component(spike, "Relative Strength Persistence", benchmark=spy)
    assert sustained["value"] > sudden["value"]
    assert sudden["evidence"]["latest_day_positive_progress_share"] > 0.5


def test_improving_rs_differs_from_strong_but_deteriorating():
    spy = benchmark(70)
    improving = history_from_close(
        np.r_[
            np.linspace(100, 104, 50),
            np.linspace(104, 108, 15),
            np.linspace(108, 116, 5),
        ]
    )
    deteriorating = history_from_close(
        np.r_[np.linspace(100, 120, 50), np.linspace(120, 116, 20)]
    )
    assert (
        component(improving, "Relative Strength Persistence", benchmark=spy)["state"]
        == "IMPROVING"
    )
    assert (
        component(deteriorating, "Relative Strength Persistence", benchmark=spy)[
            "state"
        ]
        == "STRONG_BUT_DETERIORATING"
    )


def test_one_day_rs_spike_takes_precedence_over_deteriorating_path():
    result = component(
        history_from_close(np.r_[np.linspace(130, 100, 30), 101.0]),
        "Relative Strength Persistence",
        benchmark=benchmark(31),
        recent_rs_score=80.0,
    )
    assert result["evidence"]["latest_day_positive_progress_share"] > 0.5
    assert result["evidence"]["recent_5_session_relative_return_pct"] < 0
    assert result["evidence"]["relative_line_slope_pct_per_session"] < 0
    assert result["state"] == "INCONSISTENT"


@pytest.mark.parametrize("missing", ["benchmark", "history", "score"])
def test_missing_rs_inputs_never_receive_favourable_default(missing: str):
    frame = history_from_close(np.linspace(100, 120, 70))
    spy = benchmark(70)
    score: float | None = 80.0
    if missing == "benchmark":
        spy = None
    elif missing == "history":
        frame = frame.iloc[-20:]
    else:
        score = None
    result = component(
        frame, "Relative Strength Persistence", benchmark=spy, recent_rs_score=score
    )
    assert result["status"] in {"INSUFFICIENT_HISTORY", "MISSING_DATA"}
    assert result["value"] is None


def test_current_rs_level_and_persistence_are_distinct_evidence():
    result = component(
        history_from_close(np.linspace(100, 120, 70)),
        "Relative Strength Persistence",
        benchmark=benchmark(70),
        recent_rs_score=55.0,
    )
    assert result["evidence"]["current_recent_rs_score"] == 55.0
    assert "relative_return_20d_pct" in result["evidence"]


def test_identical_replay_and_shuffled_history_are_deterministic():
    frame = contraction_frame(contracting=True)
    spy = benchmark(len(frame))
    first = calculate_chart_quality_fields(frame, benchmark=spy, recent_rs_score=80)
    second = calculate_chart_quality_fields(frame, benchmark=spy, recent_rs_score=80)
    shuffled = calculate_chart_quality_fields(
        frame.sample(frac=1.0, random_state=11),
        benchmark=spy.sample(frac=1.0, random_state=12),
        recent_rs_score=80,
    )
    assert first == second == shuffled
    assert all(first[f"CQ {name} Reason"] for name in CHART_QUALITY_COMPONENTS)


def test_historical_replay_ignores_future_stock_and_benchmark_rows():
    frame = history_from_close(np.linspace(80, 110, 80))
    spy = benchmark(80, start=100, end=105)
    as_of = frame.index[-1]
    future_date = as_of + pd.offsets.BDay(1)
    future_frame = frame.copy()
    future_frame.loc[future_date] = [10, 300, 5, 10, 9_000_000]
    future_spy = spy.copy()
    future_spy.loc[future_date] = [200, 210, 190, 200, 9_000_000]
    assert calculate_chart_quality_fields(
        frame, benchmark=spy, as_of=as_of, recent_rs_score=80
    ) == calculate_chart_quality_fields(
        future_frame, benchmark=future_spy, as_of=as_of, recent_rs_score=80
    )


def test_string_date_stock_index_is_sliced_at_as_of_before_calculation():
    frame = history_from_close(np.linspace(80, 110, 80))
    cutoff = frame.index[69]
    historical = frame.iloc[:70].copy()
    with_future = frame.copy()
    with_future.iloc[70:, with_future.columns.get_loc("High")] = 300.0
    with_future.iloc[70:, with_future.columns.get_loc("Close")] = 90.0
    historical.index = historical.index.strftime("%Y-%m-%d")
    with_future.index = with_future.index.strftime("%Y-%m-%d")
    spy = benchmark(80)
    expected = calculate_chart_quality_fields(
        historical, benchmark=spy, as_of=cutoff, recent_rs_score=80
    )
    actual = calculate_chart_quality_fields(
        with_future, benchmark=spy, as_of=cutoff, recent_rs_score=80
    )
    assert actual == expected


def test_string_date_benchmark_index_is_sliced_at_as_of_before_rs_calculation():
    stock = history_from_close(np.linspace(80, 110, 80))
    cutoff = stock.index[69]
    historical_spy = benchmark(70, start=100, end=105)
    future_spy = benchmark(80, start=100, end=105)
    future_spy.iloc[:70] = historical_spy.to_numpy()
    future_spy.iloc[70:, future_spy.columns.get_loc("Close")] = 300.0
    stock.index = stock.index.strftime("%Y-%m-%d")
    historical_spy.index = historical_spy.index.strftime("%Y-%m-%d")
    future_spy.index = future_spy.index.strftime("%Y-%m-%d")
    expected = component(
        stock,
        "Relative Strength Persistence",
        benchmark=historical_spy,
        as_of=cutoff,
    )
    actual = component(
        stock,
        "Relative Strength Persistence",
        benchmark=future_spy,
        as_of=cutoff,
    )
    assert actual == expected


def test_numeric_history_index_with_as_of_fails_closed():
    frame = history_from_close(np.linspace(80, 110, 80)).reset_index(drop=True)
    fields = calculate_chart_quality_fields(
        frame, benchmark=benchmark(80), as_of="2025-04-01", recent_rs_score=80
    )
    for name in CHART_QUALITY_COMPONENTS:
        assert fields[f"CQ {name} Status"] == "MISSING_DATA"
        assert fields[f"CQ {name} Value"] is None


def test_phase3_tampering_cannot_change_canonical_outputs_or_capacity_order():
    candidates = pd.DataFrame(
        [production_candidate("AAA", 90), production_candidate("BBB", 80)]
    )
    baseline = run_screener.apply_canonical_decision_pipeline(
        candidates, production_context()
    )
    tampered = candidates.copy(deep=True)
    for field in PHASE3_RESEARCH_FIELDS:
        tampered[field] = "adversarial"
    replay = run_screener.apply_canonical_decision_pipeline(
        tampered, production_context()
    )
    canonical_columns = [
        column for column in baseline.columns if column not in PHASE3_RESEARCH_FIELDS
    ]
    pd.testing.assert_frame_equal(
        baseline[canonical_columns], replay[canonical_columns], check_dtype=True
    )
    assert baseline["Ticker"].tolist() == replay["Ticker"].tolist()


@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        ({"Initial Stop": 101.0}, "NO TRADE"),
        (
            {
                "Realistic Target": np.nan,
                "Realistic Target Source": "",
                "Reward/Risk Ratio": np.nan,
            },
            "NO TRADE",
        ),
    ],
)
def test_excellent_phase3_never_repairs_invalid_production_plan(updates, expected):
    candidate = production_candidate("INVALID", **updates)
    for name in CHART_QUALITY_COMPONENTS:
        candidate[f"CQ {name} Status"] = "AVAILABLE"
        candidate[f"CQ {name} State"] = "STRONG"
        candidate[f"CQ {name} Value"] = 100.0
        candidate[f"CQ {name} Reason"] = "excellent"
    result = run_screener.apply_canonical_decision_pipeline(
        pd.DataFrame([candidate]), production_context()
    ).iloc[0]
    assert result["Final Decision"] == expected
    if expected in {"WATCH", "NO TRADE"}:
        assert result["Maximum Risk R"] == 0
        assert result["Maximum Shares"] == 0


def test_weak_phase3_cannot_demote_canonical_candidate_or_overwrite_fields():
    candidate = production_candidate("VALID")
    baseline = run_screener.apply_canonical_decision_pipeline(
        pd.DataFrame([candidate]), production_context()
    ).iloc[0]
    for field in PHASE3_RESEARCH_FIELDS:
        candidate[field] = "WEAK"
    replay = run_screener.apply_canonical_decision_pipeline(
        pd.DataFrame([candidate]), production_context()
    ).iloc[0]
    for field in (
        "Final Decision",
        "Planned Entry",
        "Initial Stop",
        "Realistic Target",
        "Reward/Risk Ratio",
        "Maximum Risk R",
        "Maximum Risk Dollars",
        "Maximum Shares",
    ):
        assert baseline[field] == replay[field]


def test_phase3_fields_are_excluded_from_forward_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(run_screener, "LAST_METADATA_DIAGNOSTICS", {})
    row = production_candidate("SNAPSHOT")
    row.update(
        calculate_chart_quality_fields(
            history_from_close(np.linspace(80, 110, 80)),
            benchmark=benchmark(80),
            recent_rs_score=88,
        )
    )
    canonical = run_screener.apply_canonical_decision_pipeline(
        pd.DataFrame([row]), production_context()
    )
    path = run_screener.write_forward_snapshot(
        canonical,
        pd.DataFrame(),
        {
            "market_cap_filter_status": "NOT ENFORCED",
            "market_regime": {},
            "portfolio_status": {},
            "drawdown": {},
            "maximum_heat_r": 3.0,
            "current_heat_r": 0.0,
            "remaining_heat_r": 3.0,
        },
        datetime(2026, 10, 4, 12, tzinfo=timezone.utc),
        tmp_path,
    )
    columns = set(pd.read_csv(path / "candidates.csv").columns)
    assert not columns.intersection(PHASE3_RESEARCH_FIELDS)


def test_pattern_discovery_manifest_exposes_research_only_chart_quality_summary():
    row = production_candidate(
        "PATTERN",
        **{
            "Realistic Target": np.nan,
            "Realistic Target Source": "",
            "Reward/Risk Ratio": np.nan,
        },
    )
    row.update(
        calculate_chart_quality_fields(
            history_from_close(np.linspace(80, 110, 80)),
            benchmark=benchmark(80),
            recent_rs_score=88,
        )
    )
    canonical = run_screener.apply_canonical_decision_pipeline(
        pd.DataFrame([row]), production_context()
    )
    classified = run_screener.classify_pattern_discovery_sections(canonical)
    manifest = run_screener.decision_manifest_records(classified)[0]
    assert classified.iloc[0]["Report Section"] == "Pattern Watchlist"
    assert classified.iloc[0]["Chart Quality Summary"].startswith("RESEARCH_ONLY")
    assert (
        manifest["chart_quality_summary"] == classified.iloc[0]["Chart Quality Summary"]
    )
    assert set(manifest["chart_quality"]) == set(CHART_QUALITY_COMPONENTS)


def test_report_validator_accepts_complete_components_and_rejects_missing_reason():
    row = production_candidate(
        "VALIDATED_REPORT",
        **{
            "Realistic Target": np.nan,
            "Realistic Target Source": "",
            "Reward/Risk Ratio": np.nan,
        },
    )
    row.update(
        calculate_chart_quality_fields(
            history_from_close(np.linspace(80, 110, 80)),
            benchmark=benchmark(80),
            recent_rs_score=88,
        )
    )
    canonical = run_screener.apply_canonical_decision_pipeline(
        pd.DataFrame([row]), production_context()
    )
    classified = run_screener.classify_pattern_discovery_sections(canonical)
    record = classified.iloc[0].to_dict()
    assert validate_csv_semantics([record]) == []

    missing_reason = record.copy()
    missing_reason[f"CQ {CHART_QUALITY_COMPONENTS[0]} Reason"] = ""
    errors = validate_csv_semantics([missing_reason])
    assert any("incomplete chart quality component" in error for error in errors)

    invalid_status = record.copy()
    invalid_status[f"CQ {CHART_QUALITY_COMPONENTS[0]} Status"] = "BOGUS_STATUS"
    errors = validate_csv_semantics([invalid_status])
    assert any("unsupported chart quality status" in error for error in errors)

    invalid_not_applicable = record.copy()
    invalid_not_applicable[f"CQ {CHART_QUALITY_COMPONENTS[0]} Status"] = (
        "NOT_APPLICABLE"
    )
    invalid_not_applicable[f"CQ {CHART_QUALITY_COMPONENTS[0]} State"] = "NOT_APPLICABLE"
    invalid_not_applicable[f"CQ {CHART_QUALITY_COMPONENTS[0]} Value"] = np.nan
    invalid_not_applicable["Chart Quality Summary"] = "; ".join(
        ["RESEARCH_ONLY"]
        + [
            f"{name}: {invalid_not_applicable[f'CQ {name} State']}"
            for name in CHART_QUALITY_COMPONENTS
        ]
    )
    errors = validate_csv_semantics([invalid_not_applicable])
    assert any("unsupported chart quality status" in error for error in errors)

    invalid_state = record.copy()
    invalid_state[f"CQ {CHART_QUALITY_COMPONENTS[0]} State"] = "BOGUS_STATE"
    errors = validate_csv_semantics([invalid_state])
    assert any("unsupported chart quality state" in error for error in errors)

    invalid_value = record.copy()
    invalid_value[f"CQ {CHART_QUALITY_COMPONENTS[0]} Value"] = 100.01
    errors = validate_csv_semantics([invalid_value])
    assert any("chart quality value outside 0-100" in error for error in errors)

    contradictory_summary = record.copy()
    contradictory_summary["Chart Quality Summary"] = "RESEARCH_ONLY; contradictory"
    errors = validate_csv_semantics([contradictory_summary])
    assert any(
        "chart quality summary contradicts components" in error for error in errors
    )

    missing_direction = record.copy()
    missing_direction[f"CQ {DISTRIBUTION} Warnings"] = ""
    errors = validate_csv_semantics([missing_direction])
    assert any(
        "distribution penalty direction warning missing" in error for error in errors
    )


def test_unknown_component_values_render_as_explicit_unknown_not_zero():
    fields = calculate_chart_quality_fields(history_from_close([100.0] * 10))
    for name in CHART_QUALITY_COMPONENTS:
        assert fields[f"CQ {name} Value"] is None
        assert "UNKNOWN" in fields[f"CQ {name} State"] or fields[
            f"CQ {name} State"
        ] in {"INSUFFICIENT_HISTORY", "MISSING_DATA", "NOT_APPLICABLE"}
    assert "INSUFFICIENT_HISTORY" in fields["Chart Quality Summary"]
