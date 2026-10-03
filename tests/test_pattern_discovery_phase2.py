from __future__ import annotations

from datetime import datetime, timezone
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import run_screener
from decision_system import PortfolioRisk, calculate_drawdown_state
from research.setup_lanes import (
    BREAKOUT_LANE,
    LANE_OUTPUT_FIELDS,
    PHASE2_RESEARCH_FIELDS,
    PULLBACK_LANE,
    TIGHT_BASE_LANE,
    annotate_setup_lanes,
    calculate_phase2_history_features,
)
from scripts.validate_report import validate_csv_semantics


def lane_row(ticker: str, **updates: object) -> dict[str, object]:
    row: dict[str, object] = {
        "Ticker": ticker,
        "Report Section": "Pattern Watchlist",
        "Pattern Discovery Status": "RESEARCH_ONLY",
        "Pattern Discovery Reason": "chart review only",
        "Category": "Developing Base Candidates",
        "Final Decision": "WATCH",
        "Actionable": False,
        "Confirmed Setup": False,
        "Maximum Risk R": 0.0,
        "Maximum Risk Dollars": 0.0,
        "Maximum Shares": 0,
        "Setup Integrity": "PASS",
        "Price Freshness Status": "CURRENT",
        "Price Data Warning": "",
        "Final Score": 71.0,
        "Planned Entry": 100.0,
        "Initial Stop": 95.0,
        "Realistic Target": np.nan,
        "Reward/Risk Ratio": np.nan,
        "RS Score": 82.0,
        "Recent RS Score": 78.0,
        "RS Trend": "Improving",
        "RS Momentum Acceleration": 0.03,
        "10 Day Range %": 7.0,
        "20 Day Range %": 13.0,
        "ADR20 %": 3.0,
        "ADR60 %": 4.2,
        "VCP Ratio": 0.71,
        "Volume Ratio": 0.75,
        "Distance From Pivot %": -1.0,
        "From 52W High %": -8.0,
        "Nearest Support Distance ATR": 0.6,
        "Distance From EMA10 ATR": 0.6,
        "Distance From EMA20 ATR": 0.8,
        "Distance From MA50 ATR": 1.4,
        "Distance From 50MA %": 4.0,
        "Support Signal": "EMA20 reclaim",
        "Pullback Quality": "A - Ideal Pullback",
        "Extension Status": "Not Extended",
        "Research Prior Advance 60D %": 22.0,
        "Research Pullback Depth ATR": 2.1,
        "Research Pullback Volume Ratio": 0.68,
        "Research Higher Low Preserved": True,
        "Research Close Strength %": 78.0,
        "Research Volume Dry-Up Ratio": 0.66,
        "Research Breakout Evidence": "NEAR_PIVOT_UNCONFIRMED",
        "Research Breakout Age Sessions": np.nan,
        "Research Breakout Pivot": 101.0,
        "Research Breakout Hold Sessions": np.nan,
        "Research Post-Breakout Range %": np.nan,
        "Research Post-Breakout Volume Ratio": np.nan,
    }
    row.update(updates)
    return row


def breakout_history(
    *,
    age: int,
    event_volume_ratio: float = 1.2,
    post_closes: list[float] | None = None,
    post_highs: list[float] | None = None,
    post_lows: list[float] | None = None,
    post_volumes: list[float] | None = None,
) -> pd.DataFrame:
    periods = 80
    dates = pd.bdate_range("2026-01-02", periods=periods)
    frame = pd.DataFrame(
        {
            "Open": np.full(periods, 100.0),
            "High": np.full(periods, 101.0),
            "Low": np.full(periods, 99.0),
            "Close": np.full(periods, 100.0),
            "Volume": np.full(periods, 1_000_000.0),
        },
        index=dates,
    )
    event_position = periods - age - 1
    frame.iloc[event_position, frame.columns.get_loc("Close")] = 102.0
    frame.iloc[event_position, frame.columns.get_loc("High")] = 103.0
    frame.iloc[event_position, frame.columns.get_loc("Low")] = 100.0
    frame.iloc[event_position, frame.columns.get_loc("Volume")] = (
        event_volume_ratio * 1_000_000.0
    )
    if age:
        closes = post_closes or [100.0] * age
        highs = post_highs or [102.0] * age
        lows = post_lows or [99.0] * age
        volumes = post_volumes or [1_000_000.0] * age
        frame.iloc[event_position + 1 :, frame.columns.get_loc("Close")] = closes
        frame.iloc[event_position + 1 :, frame.columns.get_loc("High")] = highs
        frame.iloc[event_position + 1 :, frame.columns.get_loc("Low")] = lows
        frame.iloc[event_position + 1 :, frame.columns.get_loc("Volume")] = volumes
    return frame


def output(frame: pd.DataFrame, ticker: str) -> pd.Series:
    return frame.set_index("Ticker").loc[ticker]


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


def production_candidate(ticker: str, score: float) -> dict[str, object]:
    return {
        **lane_row(ticker),
        "Report Section": "",
        "Pattern Discovery Status": "",
        "Pattern Discovery Reason": "",
        "Category": "Pullback Candidates",
        "Recent RS Score": 88.0,
        "RS Trend": "Improving",
        "Industry Qualified": True,
        "Sister Confirmation": True,
        "Tightness Label": "Tight",
        "VCP Label": "Good VCP",
        "Pullback Quality": "A - Ideal Pullback",
        "Trade Plan Confidence": "High",
        "Realistic Target": 110.0,
        "Realistic Target Source": "observed prior-high resistance",
        "Reward/Risk Ratio": 2.0,
        "Price Freshness Status": "CURRENT",
        "Price Data Warning": "",
        "Industry": "Software",
        "Sector": "Technology",
        "Theme": "Industry: Software",
        "Final Score": score,
    }


def test_annotation_is_copy_only_and_preserves_all_canonical_values():
    source = pd.DataFrame(
        [
            lane_row("WATCHING"),
            lane_row(
                "ACTIONABLE",
                **{
                    "Report Section": "Actionable Now",
                    "Pattern Discovery Status": "NOT_APPLICABLE",
                    "Final Decision": "FULL",
                    "Actionable": True,
                    "Confirmed Setup": True,
                    "Maximum Risk R": 1.0,
                    "Maximum Risk Dollars": 587.0,
                    "Maximum Shares": 117,
                },
            ),
            lane_row(
                "FAILED",
                **{
                    "Report Section": "Avoid / Failed",
                    "Final Decision": "NO TRADE",
                    "Setup Integrity": "FAIL",
                    "Initial Stop": 101.0,
                },
            ),
        ]
    )
    before = source.copy(deep=True)

    annotated = annotate_setup_lanes(source)

    pd.testing.assert_frame_equal(source, before)
    pd.testing.assert_frame_equal(
        annotated.drop(columns=list(LANE_OUTPUT_FIELDS), errors="ignore")[
            before.columns
        ],
        before,
        check_dtype=True,
    )
    for ticker in ("ACTIONABLE", "FAILED"):
        row = output(annotated, ticker)
        assert row["Setup Lanes"] == ""
        assert not row[f"{TIGHT_BASE_LANE} Member"]
        assert not row[f"{PULLBACK_LANE} Member"]
        assert not row[f"{BREAKOUT_LANE} Member"]


def test_lane_inputs_scores_and_ranks_cannot_change_production_fields():
    base = pd.DataFrame([lane_row("ISOLATED")])
    changed = base.copy(deep=True)
    changed.loc[0, "VCP Ratio"] = 1.4
    changed.loc[0, "Research Pullback Volume Ratio"] = 1.8
    changed.loc[0, "Research Breakout Evidence"] = "POST_BREAKOUT_CONSOLIDATION"
    changed.loc[0, "Research Breakout Age Sessions"] = 5
    changed.loc[0, "Research Breakout Hold Sessions"] = 5
    changed.loc[0, "Research Post-Breakout Range %"] = 4.0
    changed.loc[0, "Research Post-Breakout Volume Ratio"] = 0.7

    first = annotate_setup_lanes(base).iloc[0]
    second = annotate_setup_lanes(changed).iloc[0]

    production_fields = [
        "Final Decision",
        "Actionable",
        "Confirmed Setup",
        "Maximum Risk R",
        "Maximum Risk Dollars",
        "Maximum Shares",
        "Final Score",
        "Planned Entry",
        "Initial Stop",
        "Realistic Target",
        "Reward/Risk Ratio",
    ]
    pd.testing.assert_series_equal(
        first[production_fields], second[production_fields], check_names=False
    )
    assert first[f"{TIGHT_BASE_LANE} Score"] != second[f"{TIGHT_BASE_LANE} Score"]
    assert first[f"{PULLBACK_LANE} Score"] != second[f"{PULLBACK_LANE} Score"]
    assert first[f"{BREAKOUT_LANE} Score"] != second[f"{BREAKOUT_LANE} Score"]
    assert np.isnan(first["Realistic Target"])
    assert np.isnan(second["Realistic Target"])


def test_tampered_phase2_fields_do_not_change_any_canonical_output():
    candidates = pd.DataFrame(
        [production_candidate("AAA", 90.0), production_candidate("BBB", 80.0)]
    )
    baseline = run_screener.apply_canonical_decision_pipeline(
        candidates, production_context()
    )
    tampered = candidates.copy(deep=True)
    for field in PHASE2_RESEARCH_FIELDS:
        tampered[field] = "999"
    for field in LANE_OUTPUT_FIELDS:
        tampered[field] = "999"
    replay = run_screener.apply_canonical_decision_pipeline(
        tampered, production_context()
    )

    canonical_fields = [
        column
        for column in baseline.columns
        if column not in set(PHASE2_RESEARCH_FIELDS + LANE_OUTPUT_FIELDS)
    ]
    pd.testing.assert_frame_equal(
        baseline.reindex(columns=canonical_fields),
        replay.reindex(columns=canonical_fields),
        check_dtype=True,
    )


def test_tight_base_clear_contraction_ranks_above_loose_and_missing_ranks_last():
    frame = pd.DataFrame(
        [
            lane_row("TIGHT"),
            lane_row(
                "LOOSE",
                **{
                    "10 Day Range %": 17.0,
                    "20 Day Range %": 18.0,
                    "ADR20 %": 4.8,
                    "ADR60 %": 4.4,
                    "VCP Ratio": 1.09,
                    "Research Volume Dry-Up Ratio": 1.25,
                },
            ),
            lane_row(
                "MISSING",
                **{
                    "10 Day Range %": 9.0,
                    "20 Day Range %": np.nan,
                    "ADR20 %": 3.2,
                    "ADR60 %": np.nan,
                    "VCP Ratio": np.nan,
                    "Research Volume Dry-Up Ratio": np.nan,
                },
            ),
        ]
    )

    annotated = annotate_setup_lanes(frame).set_index("Ticker")

    assert (
        annotated.at["TIGHT", f"{TIGHT_BASE_LANE} Rank"]
        < annotated.at["LOOSE", f"{TIGHT_BASE_LANE} Rank"]
    )
    assert (
        annotated.at["LOOSE", f"{TIGHT_BASE_LANE} Rank"]
        < annotated.at["MISSING", f"{TIGHT_BASE_LANE} Rank"]
    )
    assert (
        "10D/20D contraction" in annotated.at["MISSING", f"{TIGHT_BASE_LANE} Missing"]
    )


def test_tight_base_reason_reports_pivot_and_52_week_high_proximity():
    annotated = annotate_setup_lanes(pd.DataFrame([lane_row("VISIBLE")])).iloc[0]

    reason = annotated[f"{TIGHT_BASE_LANE} Reason"]
    assert "pivot distance -1.00%" in reason
    assert "52W high distance -8.00%" in reason


def test_tight_base_extension_penalty_is_research_only():
    frame = pd.DataFrame(
        [
            lane_row("CONTROL"),
            lane_row("EXTENDED", **{"Extension Status": "Extended"}),
        ]
    )
    annotated = annotate_setup_lanes(frame).set_index("Ticker")

    assert (
        annotated.at["CONTROL", f"{TIGHT_BASE_LANE} Score"]
        > annotated.at["EXTENDED", f"{TIGHT_BASE_LANE} Score"]
    )
    assert "extension penalty" in annotated.at["EXTENDED", f"{TIGHT_BASE_LANE} Reason"]
    assert annotated.at["EXTENDED", "Final Decision"] == "WATCH"
    assert annotated.at["EXTENDED", "Maximum Risk R"] == 0


def test_constructive_pullback_ranks_above_broken_and_deep_pullback():
    frame = pd.DataFrame(
        [
            lane_row("CONSTRUCTIVE", **{"Category": "Pullback Candidates"}),
            lane_row(
                "BROKEN",
                **{
                    "Category": "Pullback Candidates",
                    "Distance From 50MA %": -4.0,
                    "Research Higher Low Preserved": False,
                    "Research Pullback Depth ATR": 7.5,
                    "Support Signal": "",
                },
            ),
        ]
    )
    annotated = annotate_setup_lanes(frame).set_index("Ticker")

    assert annotated.at["CONSTRUCTIVE", f"{PULLBACK_LANE} Rank"] == 1
    assert annotated.at["BROKEN", f"{PULLBACK_LANE} Rank"] == 2
    assert annotated.at["CONSTRUCTIVE", "Pullback Lane Quality"] == "CONSTRUCTIVE"
    assert annotated.at["BROKEN", "Pullback Lane Quality"] == "WEAK_OR_BROKEN"


def test_lost_higher_low_cannot_be_labelled_constructive():
    annotated = annotate_setup_lanes(
        pd.DataFrame(
            [
                lane_row(
                    "LOST_HIGHER_LOW",
                    **{
                        "Category": "Pullback Candidates",
                        "Research Prior Advance 60D %": 30.0,
                        "Recent RS Score": 90.0,
                        "Nearest Support Distance ATR": 0.0,
                        "Research Pullback Depth ATR": 2.0,
                        "Distance From 50MA %": 5.0,
                        "Research Higher Low Preserved": False,
                        "Research Pullback Volume Ratio": 0.5,
                        "Research Close Strength %": 85.0,
                        "Support Signal": "EMA20 reclaim",
                        "Distance From Pivot %": 0.0,
                    },
                )
            ]
        )
    ).iloc[0]

    assert annotated[f"{PULLBACK_LANE} Score"] >= 70.0
    assert annotated["Pullback Lane Quality"] == "WEAK_OR_BROKEN"
    assert "lost-higher-low penalty" in annotated[f"{PULLBACK_LANE} Reason"]


def test_touching_a_moving_average_is_not_constructive_without_confirmation():
    annotated = annotate_setup_lanes(
        pd.DataFrame(
            [
                lane_row(
                    "TOUCH_ONLY",
                    **{
                        "Category": "Pullback Candidates",
                        "Nearest Support Distance ATR": 0.05,
                        "Support Signal": "",
                        "Research Prior Advance 60D %": np.nan,
                        "Research Higher Low Preserved": np.nan,
                        "Research Pullback Volume Ratio": np.nan,
                        "Research Close Strength %": 35.0,
                    },
                )
            ]
        )
    ).iloc[0]

    assert annotated[f"{PULLBACK_LANE} Member"]
    assert annotated["Pullback Lane Quality"] != "CONSTRUCTIVE"
    assert "no reclaim/support confirmation" in annotated[f"{PULLBACK_LANE} Reason"]
    assert "support/reclaim evidence" in annotated[f"{PULLBACK_LANE} Missing"]


def test_generic_recent_support_placeholder_is_not_explicit_confirmation():
    latest = pd.Series(
        {
            "SUPPORT_SIGNAL_10EMA": "Recent support",
            "SUPPORT_SIGNAL_20EMA": "Recent support",
            "SUPPORT_SIGNAL_50MA": "Recent support",
            "SUPPORT_SIGNAL_10EMA_BOOL": False,
            "SUPPORT_SIGNAL_20EMA_BOOL": False,
            "SUPPORT_SIGNAL_50MA_BOOL": False,
        }
    )
    generic_signal = run_screener.strongest_support_signal(latest)

    annotated = annotate_setup_lanes(
        pd.DataFrame(
            [
                lane_row(
                    "GENERIC_ONLY",
                    **{
                        "Category": "Pullback Candidates",
                        "Nearest Support Distance ATR": 0.05,
                        "Research Prior Advance 60D %": 30.0,
                        "Recent RS Score": 90.0,
                        "Research Pullback Depth ATR": 2.0,
                        "Distance From 50MA %": 5.0,
                        "Research Higher Low Preserved": True,
                        "Research Pullback Volume Ratio": 0.5,
                        "Research Close Strength %": 85.0,
                        "Support Signal": generic_signal,
                        "Distance From Pivot %": 0.0,
                    },
                )
            ]
        )
    ).iloc[0]

    assert generic_signal == "Recent support"
    assert annotated[f"{PULLBACK_LANE} Member"]
    assert annotated["Pullback Lane Quality"] != "CONSTRUCTIVE"
    assert "no reclaim/support confirmation" in annotated[f"{PULLBACK_LANE} Reason"]
    assert "support/reclaim evidence" in annotated[f"{PULLBACK_LANE} Missing"]


def test_missing_support_confirmation_ranks_after_complete_comparable_evidence():
    annotated = annotate_setup_lanes(
        pd.DataFrame(
            [
                lane_row("CONFIRMED", **{"Category": "Pullback Candidates"}),
                lane_row(
                    "MISSING",
                    **{
                        "Category": "Pullback Candidates",
                        "Support Signal": "",
                    },
                ),
            ]
        )
    ).set_index("Ticker")

    assert annotated.at["CONFIRMED", f"{PULLBACK_LANE} Rank"] == 1
    assert annotated.at["MISSING", f"{PULLBACK_LANE} Rank"] == 2
    assert (
        "support/reclaim evidence"
        in annotated.at["MISSING", f"{PULLBACK_LANE} Missing"]
    )


def test_missing_support_and_atr_inputs_are_explicit_not_favourable():
    annotated = annotate_setup_lanes(
        pd.DataFrame(
            [
                lane_row(
                    "NO_SUPPORT",
                    **{
                        "Category": "Pullback Candidates",
                        "Nearest Support Distance ATR": np.nan,
                        "Distance From EMA10 ATR": np.nan,
                        "Distance From EMA20 ATR": np.nan,
                        "Distance From MA50 ATR": np.nan,
                        "Research Pullback Depth ATR": np.nan,
                    },
                )
            ]
        )
    ).iloc[0]

    assert not annotated[f"{PULLBACK_LANE} Member"]
    assert np.isnan(annotated[f"{PULLBACK_LANE} Rank"])
    assert annotated["Pullback Lane Quality"] == "AMBIGUOUS_SUPPORT"
    assert "support distance" in annotated[f"{PULLBACK_LANE} Missing"]
    assert "pullback depth ATR" in annotated[f"{PULLBACK_LANE} Missing"]


def test_high_scoring_missing_support_distance_is_unranked_and_not_favourable():
    annotated = annotate_setup_lanes(
        pd.DataFrame(
            [
                lane_row(
                    "NO_SUPPORT_HIGH_SCORE",
                    **{
                        "Category": "Pullback Candidates",
                        "Nearest Support Distance ATR": np.nan,
                        "Distance From EMA10 ATR": np.nan,
                        "Distance From EMA20 ATR": np.nan,
                        "Distance From MA50 ATR": np.nan,
                        "Research Prior Advance 60D %": 30.0,
                        "Recent RS Score": 95.0,
                        "Research Pullback Depth ATR": 2.0,
                        "Distance From 50MA %": 5.0,
                        "Research Higher Low Preserved": True,
                        "Research Pullback Volume Ratio": 0.5,
                        "Research Close Strength %": 90.0,
                        "Support Signal": "EMA20 reclaim",
                        "Distance From Pivot %": 0.0,
                    },
                )
            ]
        )
    ).iloc[0]

    assert not annotated[f"{PULLBACK_LANE} Member"]
    assert np.isnan(annotated[f"{PULLBACK_LANE} Rank"])
    assert annotated["Pullback Lane Quality"] == "AMBIGUOUS_SUPPORT"
    assert (
        "insufficient support-distance evidence; AMBIGUOUS_SUPPORT"
        in annotated[f"{PULLBACK_LANE} Reason"]
    )
    assert "support distance" in annotated[f"{PULLBACK_LANE} Missing"]


def test_same_day_breakout_is_never_called_a_confirmed_retest_or_high_flag():
    annotated = annotate_setup_lanes(
        pd.DataFrame(
            [
                lane_row(
                    "BREAKING",
                    **{
                        "Research Breakout Evidence": "SAME_DAY_BREAKOUT_UNCONFIRMED",
                        "Research Breakout Age Sessions": 0,
                    },
                )
            ]
        )
    ).iloc[0]

    assert annotated[f"{BREAKOUT_LANE} Member"]
    assert annotated["Breakout Lane State"] == "SAME_DAY_BREAKOUT_UNCONFIRMED"
    reason = annotated[f"{BREAKOUT_LANE} Reason"].lower()
    assert "same-day breakout" in reason
    assert "not a confirmed retest or high flag" in reason


def test_same_day_breakout_bar_is_excluded_from_post_breakout_evidence():
    features = calculate_phase2_history_features(breakout_history(age=0))

    assert features["Research Breakout Evidence"] == "SAME_DAY_BREAKOUT_UNCONFIRMED"
    assert features["Research Breakout Age Sessions"] == 0
    assert features["Research Breakout Hold Sessions"] is None
    assert features["Research Post-Breakout Range %"] is None
    assert features["Research Post-Breakout Volume Ratio"] is None

    annotated = annotate_setup_lanes(
        pd.DataFrame([lane_row("SAME_DAY", **features)])
    ).iloc[0]
    missing = annotated[f"{BREAKOUT_LANE} Missing"]
    assert "hold duration" in missing
    assert "post-breakout range" in missing
    assert "post-breakout volume" in missing


def test_breakout_event_volume_threshold_is_inclusive_at_1_20x():
    below = calculate_phase2_history_features(
        breakout_history(age=0, event_volume_ratio=1.199)
    )
    boundary = calculate_phase2_history_features(
        breakout_history(age=0, event_volume_ratio=1.2)
    )

    assert below["Research Breakout Evidence"] == "NO_RECENT_BREAKOUT_EVIDENCE"
    assert boundary["Research Breakout Evidence"] == "SAME_DAY_BREAKOUT_UNCONFIRMED"


def test_breakout_event_volume_uses_rolling_50_session_not_trailing_20_mean():
    frame = breakout_history(age=0, event_volume_ratio=1.3)
    volume_column = frame.columns.get_loc("Volume")
    frame.iloc[-51:-21, volume_column] = 2_000_000.0
    frame.iloc[-21:-1, volume_column] = 1_000_000.0

    event_volume = float(frame["Volume"].iloc[-1])
    trailing_20_mean = float(frame["Volume"].iloc[-21:-1].mean())
    rolling_50_mean = float(frame["Volume"].iloc[-51:-1].mean())
    assert event_volume / trailing_20_mean >= 1.2
    assert event_volume / rolling_50_mean < 1.2

    features = calculate_phase2_history_features(frame)

    assert features["Research Breakout Evidence"] == "NO_RECENT_BREAKOUT_EVIDENCE"


@pytest.mark.parametrize(
    ("missing_column", "missing_position", "expected_missing_field"),
    [
        ("Close", -11, "Research Prior Advance 60D %"),
        ("High", -5, "Research Pullback Depth ATR"),
        ("Close", -21, "Research Pullback Depth ATR"),
        ("Low", -5, "Research Higher Low Preserved"),
        ("Close", -1, "Research Close Strength %"),
        ("Volume", -3, "Research Volume Dry-Up Ratio"),
    ],
)
def test_non_lifecycle_features_do_not_backfill_missing_sessions(
    missing_column: str,
    missing_position: int,
    expected_missing_field: str,
):
    frame = breakout_history(age=0, event_volume_ratio=1.0)
    control = calculate_phase2_history_features(frame)
    assert control[expected_missing_field] is not None

    frame.iloc[missing_position, frame.columns.get_loc(missing_column)] = np.nan
    features = calculate_phase2_history_features(frame)

    assert features[expected_missing_field] is None


def test_pullback_volume_window_does_not_backfill_a_missing_session():
    frame = breakout_history(age=0, event_volume_ratio=1.0)
    close_column = frame.columns.get_loc("Close")
    high_column = frame.columns.get_loc("High")
    low_column = frame.columns.get_loc("Low")
    for offset, position in enumerate(range(len(frame) - 31, len(frame))):
        close = 100.0 + float(offset % 2)
        frame.iloc[position, close_column] = close
        frame.iloc[position, high_column] = close + 1.0
        frame.iloc[position, low_column] = close - 1.0

    control = calculate_phase2_history_features(frame)
    assert control["Research Pullback Volume Ratio"] is not None

    frame.iloc[-5, frame.columns.get_loc("Volume")] = np.nan
    features = calculate_phase2_history_features(frame)

    assert features["Research Pullback Volume Ratio"] is None


def test_incomplete_prior_50_breakout_window_is_unranked_not_near_pivot():
    complete = breakout_history(age=0, event_volume_ratio=1.0)
    complete_features = calculate_phase2_history_features(complete)
    assert complete_features["Research Breakout Evidence"] == (
        "NO_RECENT_BREAKOUT_EVIDENCE"
    )
    complete_lane = annotate_setup_lanes(
        pd.DataFrame([lane_row("COMPLETE", **complete_features)])
    ).iloc[0]
    assert complete_lane["Breakout Lane State"] == "NEAR_PIVOT_UNCONFIRMED"
    assert complete_lane[f"{BREAKOUT_LANE} Member"]

    incomplete = complete.copy()
    incomplete.iloc[-20, incomplete.columns.get_loc("High")] = np.nan
    incomplete_features = calculate_phase2_history_features(incomplete)

    assert incomplete_features["Research Breakout Evidence"] == (
        "BREAKOUT_WINDOW_INCOMPLETE"
    )
    incomplete_lane = annotate_setup_lanes(
        pd.DataFrame([lane_row("INCOMPLETE", **incomplete_features)])
    ).iloc[0]
    assert incomplete_lane["Breakout Lane State"] == "BREAKOUT_WINDOW_INCOMPLETE"
    assert not incomplete_lane[f"{BREAKOUT_LANE} Member"]
    assert np.isnan(incomplete_lane[f"{BREAKOUT_LANE} Rank"])
    assert "incomplete" in incomplete_lane[f"{BREAKOUT_LANE} Reason"].lower()


@pytest.mark.parametrize("missing_column", ["High", "Low", "Close", "Volume"])
def test_missing_post_breakout_ohlcv_preserves_age_and_fails_lifecycle_closed(
    missing_column: str,
):
    frame = breakout_history(age=3)
    frame.iloc[-2, frame.columns.get_loc(missing_column)] = np.nan

    features = calculate_phase2_history_features(frame)

    assert features["Research Breakout Age Sessions"] == 3
    assert features["Research Breakout Evidence"] == "RECENT_BREAKOUT_DATA_INCOMPLETE"
    assert features["Research Breakout Hold Sessions"] is None
    assert features["Research Post-Breakout Range %"] is None
    assert features["Research Post-Breakout Volume Ratio"] is None

    annotated = annotate_setup_lanes(
        pd.DataFrame([lane_row("INCOMPLETE", **features)])
    ).iloc[0]
    assert not annotated[f"{BREAKOUT_LANE} Member"]
    assert np.isnan(annotated[f"{BREAKOUT_LANE} Rank"])
    assert annotated["Breakout Lane State"] == "RECENT_BREAKOUT_DATA_INCOMPLETE"
    assert "incomplete" in annotated[f"{BREAKOUT_LANE} Reason"].lower()


def test_breakout_pivot_retention_boundary_is_97_percent():
    pivot = 101.0
    held = calculate_phase2_history_features(
        breakout_history(age=1, post_closes=[pivot * 0.97])
    )
    invalidated = calculate_phase2_history_features(
        breakout_history(age=1, post_closes=[pivot * 0.97 - 0.01])
    )

    assert held["Research Breakout Evidence"] == "POST_BREAKOUT_HOLD"
    assert held["Research Breakout Hold Sessions"] == 1
    assert invalidated["Research Breakout Evidence"] == "RECENT_BREAKOUT_INVALIDATED"
    assert invalidated["Research Breakout Hold Sessions"] == 0


def test_breakout_consolidation_range_and_volume_boundaries_are_inclusive():
    boundary = calculate_phase2_history_features(
        breakout_history(
            age=3,
            post_highs=[104.0, 103.0, 102.0],
            post_lows=[96.0, 98.0, 99.0],
            post_volumes=[1_000_000.0] * 3,
        )
    )
    wide = calculate_phase2_history_features(
        breakout_history(
            age=3,
            post_highs=[104.1, 103.0, 102.0],
            post_lows=[96.0, 98.0, 99.0],
            post_volumes=[1_000_000.0] * 3,
        )
    )
    heavy = calculate_phase2_history_features(
        breakout_history(age=3, post_volumes=[1_000_100.0] * 3)
    )

    assert boundary["Research Post-Breakout Range %"] == 8.0
    assert boundary["Research Post-Breakout Volume Ratio"] == 1.0
    assert boundary["Research Breakout Evidence"] == "POST_BREAKOUT_CONSOLIDATION"
    assert wide["Research Breakout Evidence"] == "POST_BREAKOUT_HOLD"
    assert heavy["Research Breakout Evidence"] == "POST_BREAKOUT_HOLD"


def test_post_breakout_consolidation_evidence_improves_breakout_lane_ranking():
    frame = pd.DataFrame(
        [
            lane_row(
                "SAME_DAY",
                **{
                    "Research Breakout Evidence": "SAME_DAY_BREAKOUT_UNCONFIRMED",
                    "Research Breakout Age Sessions": 0,
                },
            ),
            lane_row(
                "CONSOLIDATED",
                **{
                    "Research Breakout Evidence": "POST_BREAKOUT_CONSOLIDATION",
                    "Research Breakout Age Sessions": 5,
                    "Research Breakout Hold Sessions": 5,
                    "Research Post-Breakout Range %": 4.0,
                    "Research Post-Breakout Volume Ratio": 0.72,
                },
            ),
        ]
    )
    annotated = annotate_setup_lanes(frame).set_index("Ticker")

    assert annotated.at["CONSOLIDATED", f"{BREAKOUT_LANE} Rank"] == 1
    assert annotated.at["SAME_DAY", f"{BREAKOUT_LANE} Rank"] == 2
    assert (
        annotated.at["CONSOLIDATED", f"{BREAKOUT_LANE} Score"]
        > annotated.at["SAME_DAY", f"{BREAKOUT_LANE} Score"]
    )


def test_missing_breakout_history_is_honest_and_unranked():
    annotated = annotate_setup_lanes(
        pd.DataFrame(
            [
                lane_row(
                    "UNKNOWN",
                    **{
                        "Distance From Pivot %": np.nan,
                        "Research Breakout Evidence": "",
                        "Research Breakout Pivot": np.nan,
                    },
                )
            ]
        )
    ).iloc[0]

    assert not annotated[f"{BREAKOUT_LANE} Member"]
    assert np.isnan(annotated[f"{BREAKOUT_LANE} Rank"])
    assert "breakout history/state" in annotated[f"{BREAKOUT_LANE} Missing"]


def test_missing_breakout_history_cannot_use_near_pivot_fallback():
    annotated = annotate_setup_lanes(
        pd.DataFrame(
            [
                lane_row(
                    "UNKNOWN_NEAR_PIVOT",
                    **{
                        "Distance From Pivot %": -1.0,
                        "Research Breakout Evidence": "",
                        "Research Breakout Pivot": np.nan,
                    },
                )
            ]
        )
    ).iloc[0]

    assert annotated["Breakout Lane State"] == "UNKNOWN"
    assert not annotated[f"{BREAKOUT_LANE} Member"]
    assert np.isnan(annotated[f"{BREAKOUT_LANE} Rank"])
    assert "breakout history/state" in annotated[f"{BREAKOUT_LANE} Missing"]


def test_ranks_are_deterministic_under_permutation_and_ties_use_ticker():
    rows = [lane_row("BBB"), lane_row("AAA"), lane_row("CCC", **{"VCP Ratio": 0.9})]
    first = annotate_setup_lanes(pd.DataFrame(rows)).set_index("Ticker")
    second = annotate_setup_lanes(
        pd.DataFrame(rows).sample(frac=1.0, random_state=17).reset_index(drop=True)
    ).set_index("Ticker")

    for lane in (TIGHT_BASE_LANE, PULLBACK_LANE, BREAKOUT_LANE):
        pd.testing.assert_series_equal(
            first[f"{lane} Rank"].sort_index(),
            second[f"{lane} Rank"].sort_index(),
            check_names=False,
        )
    assert (
        first.at["AAA", f"{TIGHT_BASE_LANE} Rank"]
        < first.at["BBB", f"{TIGHT_BASE_LANE} Rank"]
    )


def test_lane_rankings_are_independent_and_multi_lane_membership_is_explicit():
    base = pd.DataFrame([lane_row("MULTI")])
    tight_changed = base.copy(deep=True)
    tight_changed.loc[0, "VCP Ratio"] = 1.05

    first = annotate_setup_lanes(base).iloc[0]
    second = annotate_setup_lanes(tight_changed).iloc[0]

    assert first["Setup Lanes"] == "; ".join(
        (TIGHT_BASE_LANE, PULLBACK_LANE, BREAKOUT_LANE)
    )
    assert first[f"{TIGHT_BASE_LANE} Score"] != second[f"{TIGHT_BASE_LANE} Score"]
    assert first[f"{PULLBACK_LANE} Score"] == second[f"{PULLBACK_LANE} Score"]
    assert first[f"{BREAKOUT_LANE} Score"] == second[f"{BREAKOUT_LANE} Score"]


def test_history_features_are_point_in_time_and_distinguish_breakout_age():
    dates = pd.bdate_range("2026-01-02", periods=90)
    close = np.linspace(80.0, 100.0, len(dates))
    frame = pd.DataFrame(
        {
            "Open": close - 0.5,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": np.full(len(dates), 1_000_000.0),
        },
        index=dates,
    )
    breakout_at = dates[-5]
    prior_high = frame.loc[:breakout_at].iloc[:-1]["High"].tail(50).max()
    frame.loc[breakout_at, "Close"] = prior_high + 2.0
    frame.loc[breakout_at, "High"] = prior_high + 2.5
    frame.loc[breakout_at, "Volume"] = 1_800_000.0
    frame.loc[dates[-4] :, "Close"] = prior_high + 1.0
    frame.loc[dates[-4] :, "High"] = prior_high + 2.0
    frame.loc[dates[-4] :, "Low"] = prior_high
    future = frame.copy()
    future.loc[dates[-1] + pd.offsets.BDay(1)] = [50, 51, 49, 50, 9_000_000]

    as_of = dates[-1]
    first = calculate_phase2_history_features(frame, as_of=as_of)
    second = calculate_phase2_history_features(future, as_of=as_of)

    assert first == second
    assert first["Research Breakout Age Sessions"] == 4
    assert first["Research Breakout Evidence"] in {
        "POST_BREAKOUT_HOLD",
        "POST_BREAKOUT_CONSOLIDATION",
    }
    expected_prior_advance = round(
        (frame["Close"].iloc[-11] / frame["Close"].iloc[-71] - 1.0) * 100.0, 4
    )
    assert first["Research Prior Advance 60D %"] == expected_prior_advance


def test_empty_pattern_watchlist_still_exposes_every_lane_section():
    sections = run_screener.pattern_watchlist_lane_sections(
        pd.DataFrame(columns=["Ticker", *LANE_OUTPUT_FIELDS])
    )

    assert [name for name, _ in sections] == [
        TIGHT_BASE_LANE,
        PULLBACK_LANE,
        BREAKOUT_LANE,
        "Unassigned / Insufficient Lane Evidence",
    ]
    assert all(section.empty for _, section in sections)


def test_phase2_integrates_after_phase1_and_manifest_has_one_multi_lane_record():
    canonical = pd.DataFrame([lane_row("MANIFEST")]).drop(
        columns=[
            "Report Section",
            "Pattern Discovery Status",
            "Pattern Discovery Reason",
        ]
    )
    classified = run_screener.classify_pattern_discovery_sections(canonical)
    records = run_screener.decision_manifest_records(classified)

    assert len(classified) == 1
    assert classified.iloc[0]["Report Section"] == "Pattern Watchlist"
    assert classified.iloc[0]["Setup Lanes"]
    assert len(records) == 1
    assert records[0]["setup_lanes"] == classified.iloc[0]["Setup Lanes"]
    assert records[0]["lane_ranks"][TIGHT_BASE_LANE] == 1


def test_forward_snapshot_excludes_every_phase2_field(tmp_path, monkeypatch):
    monkeypatch.setattr(run_screener, "LAST_METADATA_DIAGNOSTICS", {})
    canonical = run_screener.classify_pattern_discovery_sections(
        pd.DataFrame([lane_row("SNAPSHOT")])
    )
    generated = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
    decision_context = {
        "market_cap_filter_status": "NOT ENFORCED",
        "market_regime": {},
        "portfolio_status": {},
        "drawdown": {},
        "maximum_heat_r": 3.0,
        "current_heat_r": 0.0,
        "remaining_heat_r": 3.0,
    }

    path = run_screener.write_forward_snapshot(
        canonical, pd.DataFrame(), decision_context, generated, tmp_path
    )
    columns = set(pd.read_csv(path / "candidates.csv").columns)

    assert not columns.intersection(PHASE2_RESEARCH_FIELDS)
    assert not columns.intersection(LANE_OUTPUT_FIELDS)
    metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["snapshot_schema_version"] == 2


def test_validator_rejects_lane_membership_outside_pattern_watchlist():
    row = lane_row(
        "BAD_LANE",
        **{
            "Report Section": "Actionable Now",
            "Pattern Discovery Status": "NOT_APPLICABLE",
            "Pattern Discovery Reason": "Canonical production decision: FULL",
            "Final Decision": "FULL",
            "Actionable": True,
            "Confirmed Setup": True,
            "Maximum Risk R": 1.0,
            "Maximum Risk Dollars": 587.0,
            "Maximum Shares": 117,
            "Realistic Target": 110.0,
            "Realistic Target Source": "observed prior-high resistance",
            "Reward/Risk Ratio": 2.0,
            "Price Freshness Status": "CURRENT",
            "Setup Lanes": TIGHT_BASE_LANE,
            f"{TIGHT_BASE_LANE} Member": True,
            f"{TIGHT_BASE_LANE} Score": 88.0,
            f"{TIGHT_BASE_LANE} Rank": 1,
        },
    )

    errors = validate_csv_semantics([row])

    assert any(
        "lane membership is only valid in Pattern Watchlist" in error
        for error in errors
    )


def test_validator_rejects_fractional_lane_rank():
    row = lane_row(
        "FRACTIONAL",
        **{
            "Setup Lanes": TIGHT_BASE_LANE,
            f"{TIGHT_BASE_LANE} Member": True,
            f"{TIGHT_BASE_LANE} Score": 75.0,
            f"{TIGHT_BASE_LANE} Rank": 1.5,
            f"{TIGHT_BASE_LANE} Reason": "test reason",
        },
    )

    errors = validate_csv_semantics([row])

    assert any("member lacks score/rank/reason" in error for error in errors)
