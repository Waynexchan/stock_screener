from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd

import config
from decision_system import (
    PortfolioRisk,
    calculate_drawdown_state,
    qualify_industries,
    size_authorised_candidate,
)
import run_screener
import send_email
from scripts.validate_report import (
    manifest_record,
    read_csv_rows,
    read_email_manifest,
    read_html_manifest,
    validate_csv_semantics,
)


def candidate(ticker: str = "GENERIC", **updates: object) -> dict[str, object]:
    row: dict[str, object] = {
        "Generated At": "2026-09-05T10:00:00+00:00",
        "Signal Date": "2026-09-04",
        "Price Data As Of": "2026-09-04",
        "Latest Bar Timestamp": "2026-09-04T00:00:00",
        "Price Freshness Status": "CURRENT",
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
        "Price Data Warning": "",
        "Final Score": 82.0,
        "Industry Composite Score": 70.0,
        "Action": "Review valid setup",
    }
    row.update(updates)
    return row


def portfolio(
    remaining: float = 3.0,
    industry_heat: float = 0.0,
    theme_heat: float = 0.0,
) -> PortfolioRisk:
    return PortfolioRisk(
        (),
        3.0 - remaining,
        3.0,
        remaining,
        {"Software": industry_heat},
        {},
        {"Industry: Software": theme_heat},
        (),
    )


def context(
    current_portfolio: PortfolioRisk | None = None,
    open_positions: int | None = 0,
    new_risk_allowed: bool = True,
    market_new_risk_allowed: bool = True,
    new_initial_risk_r_today: float | None = 0.0,
    new_position_count_today: int | None = 0,
) -> dict[str, object]:
    return {
        "market_regime": SimpleNamespace(regime="Strong"),
        "market_new_risk_allowed": market_new_risk_allowed,
        "drawdown": calculate_drawdown_state(100_000, 100_000),
        "portfolio_status": {
            "portfolio": current_portfolio or portfolio(),
            "open_position_count": open_positions,
            "portfolio_new_risk_allowed": new_risk_allowed,
            "new_initial_risk_r_today": new_initial_risk_r_today,
            "new_position_count_today": new_position_count_today,
        },
    }


def decision(row: dict[str, object], decision_context: dict[str, object] | None = None):
    return run_screener.apply_canonical_decision_pipeline(
        pd.DataFrame([row]), decision_context or context()
    ).iloc[0]


PATTERN_REPORT_FIELDS = set(run_screener.PATTERN_REPORT_FIELDS)


def assert_only_pattern_report_fields_added_or_changed(
    before: pd.DataFrame, after: pd.DataFrame
) -> None:
    before_production = before.drop(columns=PATTERN_REPORT_FIELDS, errors="ignore")
    after_production = after.drop(columns=PATTERN_REPORT_FIELDS, errors="ignore")
    pd.testing.assert_frame_equal(
        before_production.reset_index(drop=True),
        after_production.reset_index(drop=True),
        check_dtype=True,
    )


def history(latest: str, partial: bool = False) -> pd.DataFrame:
    dates = pd.DatetimeIndex([pd.Timestamp(latest) - pd.Timedelta(days=1), latest])
    frame = pd.DataFrame(
        {
            "Open": [99.0, 100.0],
            "High": [101.0, 102.0],
            "Low": [98.0, 99.0],
            "Close": [100.0, 101.0],
            "Volume": [1_000_000.0, 1_100_000.0],
        },
        index=dates,
    )
    if partial:
        frame.iloc[-1, frame.columns.get_loc("Close")] = np.nan
    return frame


def test_loose_developing_base_bug_class_is_watch_with_zero_shares():
    result = decision(
        candidate(
            Category="Developing Base Candidates",
            **{
                "Tightness Label": "Loose",
                "Industry Qualified": False,
                "Sister Confirmation": False,
                "Confirmed Setup": False,
                "Final Score": 42.0,
            },
        )
    )
    assert result["Final Decision"] == "WATCH"
    assert result["Setup Integrity"] == "FAIL"
    assert result["Maximum Risk R"] == 0
    assert result["Maximum Shares"] == 0
    assert not result["Actionable"]


def test_early_leader_below_75_can_be_actionable_half():
    result = decision(
        candidate(
            "EARLY",
            **{
                "Recent RS Score": 86,
                "RS Trend": "Emerging Leader",
                "Industry Qualified": False,
                "Sister Confirmation": False,
                "Final Score": 64.0,
            },
        )
    )
    assert result["Final Decision"] == "HALF"
    assert result["Setup Integrity"] == "PASS"
    assert result["Maximum Risk R"] == 0.5
    assert result["Maximum Shares"] > 0
    assert result["Actionable"]


def test_score_above_75_cannot_override_invalid_structure():
    result = decision(candidate(**{"Final Score": 99.0, "Initial Stop": 101.0}))
    assert result["Final Decision"] == "NO TRADE"
    assert result["Maximum Shares"] == 0


def test_sizing_never_promotes_watch_or_no_trade():
    row = candidate()
    for state in ("WATCH", "NO TRADE"):
        sized = size_authorised_candidate(row, state)
        assert sized.state == state
        assert sized.maximum_risk_r == 0
        assert sized.maximum_shares == 0
        assert not sized.actionable


def test_missing_observed_target_is_research_only_pattern_without_fabrication():
    canonical = run_screener.apply_canonical_decision_pipeline(
        pd.DataFrame(
            [
                candidate(
                    "MISSING_TARGET",
                    **{
                        "Realistic Target": np.nan,
                        "Realistic Target Source": "",
                        "Reward/Risk Ratio": np.nan,
                    },
                )
            ]
        ),
        context(),
    )

    classified = run_screener.classify_pattern_discovery_sections(canonical).iloc[0]

    assert classified["Report Section"] == "Pattern Watchlist"
    assert classified["Pattern Discovery Status"] == "RESEARCH_ONLY"
    assert classified["Final Decision"] == "NO TRADE"
    assert classified["Maximum Risk R"] == 0
    assert classified["Maximum Shares"] == 0
    assert not classified["Actionable"]
    assert pd.isna(classified["Realistic Target"])
    assert pd.isna(classified["Reward/Risk Ratio"])
    assert (
        "observed structural target missing" in classified["Pattern Discovery Reason"]
    )


def test_canonical_full_and_half_map_to_actionable_now_unchanged():
    canonical = run_screener.apply_canonical_decision_pipeline(
        pd.DataFrame(
            [
                candidate("FULL_ROW", **{"Final Score": 90.0}),
                candidate(
                    "HALF_ROW",
                    **{
                        "Sector": "Industrials",
                        "Industry": "Machinery",
                        "Theme": "Industry: Machinery",
                        "Sister Confirmation": False,
                        "Final Score": 80.0,
                    },
                ),
            ]
        ),
        context(),
    )
    before = canonical.copy(deep=True)

    classified = run_screener.classify_pattern_discovery_sections(canonical)

    assert_only_pattern_report_fields_added_or_changed(before, classified)
    by_ticker = classified.set_index("Ticker")
    assert by_ticker.loc["FULL_ROW", "Final Decision"] == "FULL"
    assert by_ticker.loc["HALF_ROW", "Final Decision"] == "HALF"
    assert set(by_ticker["Report Section"]) == {"Actionable Now"}
    assert set(by_ticker["Pattern Discovery Status"]) == {"NOT_APPLICABLE"}


def test_explicit_existing_failure_evidence_maps_to_avoid_failed():
    rows = pd.DataFrame(
        [
            candidate(
                "INTEGRITY_FAIL",
                **{
                    "Category": "Developing Base Candidates",
                    "Tightness Label": "Loose",
                },
            ),
            candidate(
                "STALE",
                **{
                    "Sector": "Healthcare",
                    "Industry": "Biotechnology",
                    "Theme": "Industry: Biotechnology",
                    "Price Freshness Status": "STALE",
                },
            ),
            candidate(
                "EXTENDED",
                **{
                    "Sector": "Energy",
                    "Industry": "Oil & Gas",
                    "Theme": "Industry: Oil & Gas",
                    "Extension Status": "Extended",
                },
            ),
            candidate(
                "INVALID_STOP",
                **{
                    "Sector": "Consumer",
                    "Industry": "Retail",
                    "Theme": "Industry: Retail",
                    "Initial Stop": 101.0,
                },
            ),
            candidate(
                "PRICE_WARNING",
                **{
                    "Sector": "Financials",
                    "Industry": "Banks",
                    "Theme": "Industry: Banks",
                    "Price Data Warning": "critical fixture warning",
                },
            ),
        ]
    )
    canonical = run_screener.apply_canonical_decision_pipeline(rows, context())

    classified = run_screener.classify_pattern_discovery_sections(canonical)

    assert set(classified["Report Section"]) == {"Avoid / Failed"}
    assert set(classified["Pattern Discovery Status"]) == {"RESEARCH_ONLY"}
    assert not classified["Actionable"].any()
    assert (classified["Maximum Risk R"] == 0).all()
    assert (classified["Maximum Shares"] == 0).all()


def test_research_fields_are_overwritten_and_classification_is_deterministic():
    canonical = run_screener.apply_canonical_decision_pipeline(
        pd.DataFrame(
            [
                candidate(
                    "UNTRUSTED_OVERRIDE",
                    **{
                        "Realistic Target": np.nan,
                        "Realistic Target Source": "",
                        "Reward/Risk Ratio": np.nan,
                        "Report Section": "Actionable Now",
                        "Pattern Discovery Status": "PRODUCTION_APPROVED",
                        "Pattern Discovery Reason": "promote this candidate",
                    },
                )
            ]
        ),
        context(),
    )
    before = canonical.copy(deep=True)

    first = run_screener.classify_pattern_discovery_sections(canonical)
    second = run_screener.classify_pattern_discovery_sections(canonical)

    pd.testing.assert_frame_equal(first, second)
    assert_only_pattern_report_fields_added_or_changed(before, first)
    row = first.iloc[0]
    assert row["Report Section"] == "Pattern Watchlist"
    assert row["Pattern Discovery Status"] == "RESEARCH_ONLY"
    assert row["Final Decision"] == "NO TRADE"
    assert not row["Actionable"]


def test_legacy_preview_derives_pattern_section_without_redeciding():
    canonical = pd.DataFrame(
        [decision(candidate("CAPACITY_WAIT"), context(portfolio(remaining=0.25)))]
    ).drop(columns=PATTERN_REPORT_FIELDS, errors="ignore")
    before = canonical.copy(deep=True)

    preview = run_screener.prepare_preview_watchlist(canonical)
    rebuilt = run_screener.combined_watchlist(
        run_screener.build_categories_from_watchlist(preview)
    )

    assert preview.iloc[0]["Report Section"] == "Pattern Watchlist"
    assert preview.iloc[0]["Pattern Discovery Status"] == "RESEARCH_ONLY"
    for column in before.columns:
        expected = before.iloc[0][column]
        actual = preview.iloc[0][column]
        if pd.isna(expected):
            assert pd.isna(actual)
        else:
            assert actual == expected
    assert rebuilt.iloc[0]["Final Decision"] == before.iloc[0]["Final Decision"]
    assert rebuilt.iloc[0]["Decision Reasons"] == before.iloc[0]["Decision Reasons"]


def test_export_path_classifies_after_canonical_decision(tmp_path: Path, monkeypatch):
    raw = pd.DataFrame(
        [
            candidate(
                "EXPORT_PATTERN",
                **{
                    "Realistic Target": np.nan,
                    "Realistic Target Source": "",
                    "Reward/Risk Ratio": np.nan,
                },
            )
        ]
    )
    canonical = run_screener.apply_canonical_decision_pipeline(raw, context())
    categories = {
        name: (
            raw.copy()
            if name == "Pullback Candidates"
            else pd.DataFrame(columns=raw.columns)
        )
        for name in run_screener.CATEGORY_PRIORITY
    }
    captured: dict[str, pd.DataFrame] = {}

    monkeypatch.setattr(run_screener, "add_action_column", lambda frame: frame.copy())
    monkeypatch.setattr(
        run_screener, "add_review_guidance_columns", lambda frame: frame.copy()
    )
    monkeypatch.setattr(
        run_screener,
        "build_decision_context",
        lambda *args: {**context(), "portfolio_new_risk_allowed": True},
    )
    monkeypatch.setattr(
        run_screener,
        "apply_canonical_decision_pipeline",
        lambda candidates, decision_context: canonical.copy(),
    )
    monkeypatch.setattr(
        run_screener, "build_daily_focus_list", lambda current: pd.DataFrame()
    )
    monkeypatch.setattr(
        run_screener,
        "analyse_top_action_list",
        lambda top, industries, market: run_screener.AIAnalysisResult(
            "fixture commentary", top.copy(), False, False, "fixture", len(top)
        ),
    )
    monkeypatch.setattr(
        run_screener, "determine_market_character", lambda *args: "Fixture Market"
    )
    monkeypatch.setattr(run_screener, "build_report_history_snapshot", lambda *args: {})
    monkeypatch.setattr(run_screener, "load_last_report_history", lambda: None)
    monkeypatch.setattr(run_screener, "report_history_delta", lambda *args: None)
    monkeypatch.setattr(run_screener, "report_history_trend", lambda *args: None)
    monkeypatch.setattr(run_screener, "write_markdown", lambda *args: None)
    monkeypatch.setattr(run_screener, "write_html", lambda *args: None)

    def capture_email(*args):
        captured["canonical"] = args[7].copy()

    monkeypatch.setattr(run_screener, "write_email_summary", capture_email)
    monkeypatch.setattr(run_screener, "validate_exported_reports", lambda: None)

    def capture_snapshot(*args):
        captured["snapshot"] = args[0].copy()
        return tmp_path / "snapshot"

    monkeypatch.setattr(run_screener, "write_forward_snapshot", capture_snapshot)
    monkeypatch.setattr(run_screener, "save_last_good_reports", lambda: None)
    monkeypatch.setattr(run_screener, "append_report_history", lambda *args: None)
    monkeypatch.setattr(run_screener, "OUTPUT_CSV", str(tmp_path / "watchlist.csv"))

    watchlist, *_ = run_screener.export_results(
        categories,
        pd.DataFrame(columns=run_screener.TOP_INDUSTRY_COLUMNS),
        pd.DataFrame(columns=run_screener.MARKET_COLUMNS),
        "Strong",
    )

    for frame in (watchlist, captured["canonical"]):
        row = frame.iloc[0]
        assert row["Final Decision"] == "NO TRADE"
        assert row["Report Section"] == "Pattern Watchlist"
        assert row["Pattern Discovery Status"] == "RESEARCH_ONLY"
        assert pd.isna(row["Realistic Target"])
        assert pd.isna(row["Reward/Risk Ratio"])
    assert PATTERN_REPORT_FIELDS.isdisjoint(captured["snapshot"].columns)
    assert_only_pattern_report_fields_added_or_changed(
        captured["snapshot"], captured["canonical"]
    )


def test_portfolio_heat_blocks_otherwise_valid_candidate():
    result = decision(candidate(), context(portfolio(remaining=0.25)))
    assert result["Final Decision"] == "NO TRADE"
    assert "portfolio heat exhausted" in result["Decision Reasons"]


def test_max_position_count_blocks_otherwise_valid_candidate():
    result = decision(candidate(), context(open_positions=config.MAX_OPEN_POSITIONS))
    assert result["Final Decision"] == "NO TRADE"
    assert "maximum open-position count reached" in result["Decision Reasons"]


def test_industry_heat_blocks_otherwise_valid_candidate():
    result = decision(candidate(), context(portfolio(industry_heat=1.75)))
    assert result["Final Decision"] == "NO TRADE"
    assert "industry heat limit exceeded" in result["Decision Reasons"]


def test_theme_heat_blocks_otherwise_valid_candidate():
    result = decision(candidate(), context(portfolio(theme_heat=1.75)))
    assert result["Final Decision"] == "NO TRADE"
    assert "theme heat limit exceeded" in result["Decision Reasons"]


def test_candidate_concentration_changes_final_production_record():
    rows = pd.DataFrame(
        [
            candidate("LEADER", **{"Final Score": 90.0}),
            candidate("SECOND", **{"Final Score": 80.0}),
        ]
    )
    final = run_screener.apply_canonical_decision_pipeline(rows, context())
    states = final.set_index("Ticker")["Final Decision"].to_dict()
    assert states == {"LEADER": "FULL", "SECOND": "NO TRADE"}
    rejected = final.set_index("Ticker").loc["SECOND"]
    assert rejected["Maximum Shares"] == 0
    assert rejected["Concentration Exclusion Reason"] == "industry concentration limit"


def test_price_freshness_current_weekend_and_holiday_sessions():
    weekday_after_close = datetime(2026, 9, 2, 21, tzinfo=timezone.utc)
    saturday = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)
    sunday = datetime(2026, 9, 6, 12, tzinfo=timezone.utc)
    labour_day = datetime(2026, 9, 7, 21, tzinfo=timezone.utc)
    for reference in (saturday, sunday, labour_day):
        freshness = run_screener.price_freshness_status(
            history("2026-09-04"), reference
        )
        assert freshness.status == "CURRENT"
        assert freshness.expected_session == "2026-09-04"
    weekday = run_screener.price_freshness_status(
        history("2026-09-02"), weekday_after_close
    )
    assert weekday.status == "CURRENT"
    assert weekday.expected_session == "2026-09-02"


def test_price_freshness_stale_weekday_and_partial_bar():
    after_close = datetime(2026, 9, 2, 21, tzinfo=timezone.utc)
    stale = run_screener.price_freshness_status(history("2026-09-01"), after_close)
    partial = run_screener.price_freshness_status(
        history("2026-09-02", partial=True), after_close
    )
    assert stale.status == "STALE"
    assert stale.expected_session == "2026-09-02"
    assert partial.status == "INCOMPLETE"
    missing_column = run_screener.price_freshness_status(
        history("2026-09-02").drop(columns="Volume"), after_close
    )
    assert missing_column.status == "MISSING"


def test_price_freshness_rejects_current_session_daily_bar_before_close():
    during_session = datetime(2026, 9, 2, 14, tzinfo=timezone.utc)
    freshness = run_screener.price_freshness_status(
        history("2026-09-02"), during_session
    )
    assert freshness.status == "INCOMPLETE"
    assert freshness.expected_session == "2026-09-01"
    assert "latest completed US session" in freshness.warning


def test_missing_production_freshness_status_blocks_actionability():
    result = decision(candidate(**{"Price Freshness Status": ""}))
    assert result["Final Decision"] == "NO TRADE"
    assert result["Maximum Shares"] == 0


def test_current_market_label_is_not_used_as_previous_regime(monkeypatch):
    captured: dict[str, object] = {}

    def fake_regime(metrics, previous_regime=None):
        captured["previous_regime"] = previous_regime
        return SimpleNamespace(
            regime="Constructive",
            maximum_heat_r=2.0,
            new_risk_allowed=True,
            data_complete=True,
            confidence="High",
        )

    monkeypatch.setattr(run_screener, "market_regime_from_metrics", fake_regime)
    monkeypatch.setattr(
        run_screener,
        "LAST_ELIGIBLE_UNIVERSE",
        pd.DataFrame(columns=["Recent RS Score"]),
    )
    run_screener.build_decision_context(
        pd.DataFrame(), pd.DataFrame(), "Strong", index_metrics={}
    )
    assert captured["previous_regime"] is None


def test_explicit_portfolio_stop_new_risk_flag_blocks_canonical_candidate():
    result = decision(candidate(), context(new_risk_allowed=False))
    assert result["Final Decision"] == "NO TRADE"
    assert result["Maximum Shares"] == 0
    assert "portfolio status prohibits new risk" in result["Decision Reasons"]


def test_explicit_market_stop_new_risk_flag_blocks_canonical_candidate():
    result = decision(candidate(), context(market_new_risk_allowed=False))
    assert result["Final Decision"] == "NO TRADE"
    assert result["Maximum Shares"] == 0
    assert "market status prohibits new risk" in result["Decision Reasons"]


def test_missing_market_permission_fails_closed_at_canonical_boundary():
    result = run_screener.canonical_candidate_decision(
        candidate(),
        "Strong",
        calculate_drawdown_state(100_000, 100_000),
        portfolio(),
        0,
        portfolio_new_risk_allowed=True,
    )
    assert result.state == "NO TRADE"
    assert "market status prohibits new risk" in result.reasons


def test_candidates_consume_shared_open_position_capacity_in_priority_order():
    rows = pd.DataFrame(
        [
            candidate(
                "SECOND",
                **{
                    "Final Score": 80.0,
                    "Sector": "Healthcare",
                    "Industry": "Biotechnology",
                    "Theme": "Industry: Biotechnology",
                },
            ),
            candidate("FIRST", **{"Final Score": 90.0}),
        ]
    )
    final = run_screener.apply_canonical_decision_pipeline(
        rows, context(open_positions=config.MAX_OPEN_POSITIONS - 1)
    ).set_index("Ticker")
    assert final.loc["FIRST", "Final Decision"] == "FULL"
    assert final.loc["SECOND", "Final Decision"] == "NO TRADE"
    assert (
        "maximum open-position count reached" in final.loc["SECOND", "Decision Reasons"]
    )


def test_candidates_consume_shared_portfolio_heat_in_priority_order():
    rows = pd.DataFrame(
        [
            candidate("FIRST", **{"Final Score": 90.0}),
            candidate(
                "SECOND",
                **{
                    "Final Score": 80.0,
                    "Sector": "Healthcare",
                    "Industry": "Biotechnology",
                    "Theme": "Industry: Biotechnology",
                },
            ),
        ]
    )
    final = run_screener.apply_canonical_decision_pipeline(
        rows, context(portfolio(remaining=1.0))
    ).set_index("Ticker")
    assert final.loc["FIRST", "Final Decision"] == "FULL"
    assert final.loc["SECOND", "Final Decision"] == "NO TRADE"
    assert "portfolio heat exhausted" in final.loc["SECOND", "Decision Reasons"]


def test_candidate_permutations_select_the_same_tied_score_portfolio():
    rows = pd.DataFrame(
        [
            candidate(
                ticker,
                **{
                    "Final Score": 90.0,
                    "Sector": f"Sector {ticker}",
                    "Industry": f"Industry {ticker}",
                    "Theme": f"Theme {ticker}",
                },
            )
            for ticker in ("DDD", "BBB", "AAA", "CCC")
        ]
    )
    expected: dict[str, str] | None = None
    for random_state in range(20):
        permuted = rows.sample(frac=1.0, random_state=random_state).reset_index(
            drop=True
        )
        final = run_screener.apply_canonical_decision_pipeline(
            permuted, context(portfolio(remaining=2.0))
        )
        decisions = dict(
            final[["Ticker", "Final Decision"]]
            .sort_values("Ticker")
            .itertuples(index=False, name=None)
        )
        if expected is None:
            expected = decisions
        assert decisions == expected
    assert expected == {
        "AAA": "FULL",
        "BBB": "FULL",
        "CCC": "NO TRADE",
        "DDD": "NO TRADE",
    }


def test_candidates_share_daily_new_initial_r_limit_in_priority_order():
    rows = pd.DataFrame(
        [
            candidate("FIRST", **{"Final Score": 90.0}),
            candidate(
                "SECOND",
                **{
                    "Final Score": 80.0,
                    "Sector": "Healthcare",
                    "Industry": "Biotechnology",
                    "Theme": "Industry: Biotechnology",
                },
            ),
            candidate(
                "THIRD",
                **{
                    "Final Score": 70.0,
                    "Sector": "Industrials",
                    "Industry": "Machinery",
                    "Theme": "Industry: Machinery",
                },
            ),
        ]
    )
    final = run_screener.apply_canonical_decision_pipeline(
        rows, context(portfolio(remaining=3.0), open_positions=1)
    ).set_index("Ticker")
    assert final.loc["FIRST", "Final Decision"] == "FULL"
    assert final.loc["SECOND", "Final Decision"] == "FULL"
    assert final.loc["THIRD", "Final Decision"] == "NO TRADE"
    assert final["Maximum Risk R"].sum() == config.MAX_NEW_INITIAL_R_PER_DAY
    assert "daily new-risk limit reached" in final.loc["THIRD", "Decision Reasons"]


def test_existing_same_day_initial_r_is_reserved_on_every_pipeline_run():
    rows = pd.DataFrame(
        [
            candidate("FIRST", **{"Final Score": 90.0}),
            candidate(
                "SECOND",
                **{
                    "Final Score": 80.0,
                    "Sector": "Healthcare",
                    "Industry": "Biotechnology",
                    "Theme": "Industry: Biotechnology",
                },
            ),
        ]
    )
    final = run_screener.apply_canonical_decision_pipeline(
        rows,
        context(
            portfolio(remaining=3.0),
            open_positions=1,
            new_initial_risk_r_today=1.5,
        ),
    ).set_index("Ticker")
    assert final.loc["FIRST", "Final Decision"] == "HALF"
    assert final.loc["SECOND", "Final Decision"] == "NO TRADE"
    assert final["Maximum Risk R"].sum() == 0.5
    assert "daily new-risk limit reached" in final.loc["SECOND", "Decision Reasons"]


def test_defensive_same_day_position_limit_survives_pipeline_rerun():
    decision_context = context(
        portfolio(remaining=0.5),
        open_positions=1,
        new_initial_risk_r_today=0.25,
        new_position_count_today=1,
    )
    decision_context["drawdown"] = calculate_drawdown_state(100_000 - 4 * 587, 100_000)
    result = decision(candidate(), decision_context)
    assert result["Final Decision"] == "NO TRADE"
    assert (
        "Defensive drawdown-mode new-position limit reached"
        in result["Decision Reasons"]
    )


def industry_members() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Ticker": f"S{i}",
                "Industry": "Software",
                "Sector": "Technology",
                "Return 5D": 2.0,
                "Return 10D": 4.0,
                "Return 20D": 8.0,
                "Relative Return 10D": 3.0,
                "Relative Return 20D": 6.0,
                "Above 10EMA": True,
                "Above 20EMA": True,
                "Above 50MA": True,
                "Near 20D High": True,
                "Near 52W High": True,
                "Valid Breakout": True,
                "Failed Breakout": False,
                "High Volume Breakdown": False,
                "Recent RS Score": 90.0,
                "Long-Term RS Score": 85.0,
                "Is Candidate": True,
            }
            for i in range(6)
        ]
    )


def test_low_metadata_coverage_cannot_produce_high_confidence_qualification():
    members = industry_members()
    setups = members[["Ticker"]].head(3)
    result = qualify_industries(members, setups, metadata_coverage=0.50).iloc[0]
    assert not result["Industry Qualified"]
    assert not result["Data Complete"]
    assert "metadata coverage" in result["Exclusion Reasons"]


def test_market_cap_policy_is_explicitly_disabled_until_reliable():
    assert config.ENFORCE_MARKET_CAP_FILTER is False
    assert config.MIN_MARKET_CAP == 500_000_000


def test_internal_csv_html_email_and_validator_use_same_decision(tmp_path: Path):
    canonical = run_screener.apply_canonical_decision_pipeline(
        pd.DataFrame(
            [
                candidate("FULL_ROW"),
                candidate(
                    "HALF_ROW",
                    **{
                        "Industry": "Semiconductors",
                        "Theme": "Industry: Semiconductors",
                        "Sister Confirmation": False,
                    },
                ),
                candidate(
                    "WATCH_ROW",
                    **{
                        "Category": "Developing Base Candidates",
                        "Sector": "Healthcare",
                        "Industry": "Biotechnology",
                        "Theme": "Industry: Biotechnology",
                        "Tightness Label": "Loose",
                    },
                ),
                candidate(
                    "NO_TRADE_ROW",
                    **{
                        "Sector": "Industrials",
                        "Industry": "Machinery",
                        "Theme": "Industry: Machinery",
                        "Initial Stop": 101.0,
                    },
                ),
            ]
        ),
        context(),
    )
    canonical = run_screener.classify_pattern_discovery_sections(canonical)
    categories = {
        name: canonical[canonical["Category"].eq(name)].copy()
        for name in run_screener.CATEGORY_PRIORITY
    }
    top_action = canonical[canonical["Final Decision"].isin(["FULL", "HALF"])]
    html_path = tmp_path / "report.html"
    markdown_path = tmp_path / "report.md"
    csv_path = tmp_path / "report.csv"
    email_path = tmp_path / "report_email.txt"
    canonical.to_csv(csv_path, index=False)
    run_screener.write_html(
        top_action,
        top_action,
        categories,
        pd.DataFrame(columns=run_screener.TOP_INDUSTRY_COLUMNS),
        pd.DataFrame(columns=run_screener.MARKET_COLUMNS),
        "Strong",
        "Deterministic test commentary",
        str(html_path),
    )
    run_screener.write_markdown(
        top_action,
        top_action,
        categories,
        pd.DataFrame(columns=run_screener.TOP_INDUSTRY_COLUMNS),
        pd.DataFrame(columns=run_screener.MARKET_COLUMNS),
        "Strong",
        "Deterministic test commentary",
        str(markdown_path),
    )
    run_screener.write_email_summary(
        top_action,
        top_action,
        pd.DataFrame(),
        "Strong",
        "Deterministic test commentary",
        str(email_path),
        canonical=canonical,
    )
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_report.py",
            str(html_path),
            str(csv_path),
            str(email_path),
        ],
        cwd=Path(run_screener.__file__).resolve().parent,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert set(canonical["Final Decision"]) == {"FULL", "HALF", "WATCH", "NO TRADE"}
    html = html_path.read_text(encoding="utf-8")
    markdown = markdown_path.read_text(encoding="utf-8")
    email = email_path.read_text(encoding="utf-8")
    for heading in ("Pattern Watchlist", "Actionable Now", "Avoid / Failed"):
        assert heading in html
        assert heading in markdown
        assert heading in email

    expected_manifest = run_screener.decision_manifest_records(canonical)
    assert read_html_manifest(html) == expected_manifest
    assert read_email_manifest(email_path) == expected_manifest
    assert (
        sorted(
            (manifest_record(row) for row in read_csv_rows(csv_path)),
            key=lambda row: str(row["ticker"]),
        )
        == expected_manifest
    )

    section_order = ["Actionable Now", "Pattern Watchlist", "Avoid / Failed"]
    for index, section in enumerate(section_order):
        start = markdown.index(f"## {section}")
        later = [
            markdown.find(f"## {name}", start + 1)
            for name in section_order[index + 1 :] + ["AI Commentary"]
        ]
        end = min(position for position in later if position >= 0)
        block = markdown[start:end]
        expected_rows = canonical[canonical["Report Section"].eq(section)]
        unexpected_rows = canonical[~canonical["Report Section"].eq(section)]
        for _, row in expected_rows.iterrows():
            assert str(row["Ticker"]) in block
            assert str(row["Pattern Discovery Reason"]) in block
        for ticker in unexpected_rows["Ticker"].astype(str):
            assert ticker not in block


def test_email_body_hides_machine_readable_decision_manifest(
    tmp_path: Path, monkeypatch
):
    summary = tmp_path / "email_summary.txt"
    summary.write_text(
        "Daily US Stock Watchlist\n\n"
        "Top Action List\nNo action tickers.\n\n"
        "Decision Manifest\n"
        '{"ticker":"TEST","decision":"NO TRADE"}\n'
        "End Decision Manifest\n\n"
        "Full daily_watchlist.html is attached.\n",
        encoding="utf-8",
    )
    attachment = tmp_path / "daily_watchlist.html"
    attachment.write_text("<html><body>Report</body></html>", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    message = send_email.build_message(
        "sender@example.com", "to@example.com", attachment
    )
    body = message.get_body(preferencelist=("plain",)).get_content()

    assert "Top Action List" in body
    assert "Full daily_watchlist.html is attached." in body
    assert "Decision Manifest" not in body
    assert '"ticker":"TEST"' not in body


def test_row_semantic_validator_detects_actionable_contradictions():
    row = dict(decision(candidate()))
    row.update(
        {
            "Recent RS Score": np.nan,
            "Realistic Target Source": "model 2R feasibility target",
            "Price Freshness Status": "STALE",
            "Initial Stop": 101.0,
            "Reward/Risk Ratio": 1.5,
            "Extension Status": "Overextended",
            "Concentration Exclusion Reason": "industry concentration limit",
            "Review Tier": "Watch Later",
        }
    )
    errors = " | ".join(validate_csv_semantics([row]))
    for expected in (
        "Missing Recent RS",
        "synthetic model 2R target",
        "stale price data",
        "invalid stop",
        "invalid R/R",
        "overextended setup",
        "concentration violation",
        "Watch Later",
    ):
        assert expected in errors


def test_semantic_validator_rejects_report_section_override():
    row = dict(
        run_screener.classify_pattern_discovery_sections(
            pd.DataFrame([decision(candidate("SECTION_OVERRIDE"))])
        ).iloc[0]
    )
    row["Report Section"] = "Pattern Watchlist"
    row["Pattern Discovery Status"] = "RESEARCH_ONLY"

    errors = " | ".join(validate_csv_semantics([row]))

    assert "canonical actionable state must be in Actionable Now" in errors


def test_semantic_validator_enforces_failure_evidence_precedence():
    failure_rows = [
        candidate("STALE_SECTION", **{"Price Freshness Status": "STALE"}),
        candidate("WARNING_SECTION", **{"Price Data Warning": "fixture warning"}),
        candidate("STOP_SECTION", **{"Initial Stop": 101.0}),
        candidate("POS_INF_STOP_SECTION", **{"Initial Stop": np.inf}),
        candidate("NEG_INF_STOP_SECTION", **{"Initial Stop": -np.inf}),
        candidate("POS_INF_ENTRY_SECTION", **{"Planned Entry": np.inf}),
        candidate("NEG_INF_ENTRY_SECTION", **{"Planned Entry": -np.inf}),
        candidate("EXTENDED_SECTION", **{"Extension Status": "Extended"}),
        candidate(
            "INTEGRITY_SECTION",
            **{
                "Category": "Developing Base Candidates",
                "Tightness Label": "Loose",
            },
        ),
    ]

    for source in failure_rows:
        row = dict(
            run_screener.classify_pattern_discovery_sections(
                pd.DataFrame([decision(source)])
            ).iloc[0]
        )
        assert row["Report Section"] == "Avoid / Failed"
        row["Report Section"] = "Pattern Watchlist"
        errors = " | ".join(validate_csv_semantics([row]))
        assert "explicit failure evidence must be in Avoid / Failed" in errors

    capacity_only = dict(
        run_screener.classify_pattern_discovery_sections(
            pd.DataFrame(
                [
                    decision(
                        candidate("CAPACITY_SECTION"),
                        context(portfolio(remaining=0.25)),
                    )
                ]
            )
        ).iloc[0]
    )
    assert capacity_only["Report Section"] == "Pattern Watchlist"
    capacity_only["Report Section"] = "Avoid / Failed"
    errors = " | ".join(validate_csv_semantics([capacity_only]))
    assert "without explicit failure evidence must be in Pattern Watchlist" in errors

    for source in (
        candidate("MISSING_ENTRY_SECTION", **{"Planned Entry": np.nan}),
        candidate("MISSING_STOP_SECTION", **{"Initial Stop": np.nan}),
    ):
        missing_plan = dict(
            run_screener.classify_pattern_discovery_sections(
                pd.DataFrame([decision(source)])
            ).iloc[0]
        )
        assert missing_plan["Report Section"] == "Pattern Watchlist"
        assert validate_csv_semantics([missing_plan]) == []


def test_real_discovery_schema_snapshot_excludes_pattern_report_fields(
    tmp_path: Path,
):
    source = candidate("SCHEMA_SNAPSHOT")
    schema_row = {
        column: source.get(column, np.nan) for column in run_screener.DISCOVERY_COLUMNS
    }
    raw = pd.DataFrame([schema_row], columns=run_screener.DISCOVERY_COLUMNS)
    canonical = run_screener.apply_canonical_decision_pipeline(raw, context())
    assert PATTERN_REPORT_FIELDS.isdisjoint(raw.columns)
    assert PATTERN_REPORT_FIELDS.isdisjoint(canonical.columns)
    for field in PATTERN_REPORT_FIELDS:
        canonical[field] = "must not enter snapshot"

    snapshot = run_screener.write_forward_snapshot(
        canonical,
        pd.DataFrame(),
        {**context(), "market_cap_filter_status": "NOT ENFORCED"},
        datetime(2026, 9, 29, 10, tzinfo=timezone.utc),
        tmp_path,
    )
    columns = set(pd.read_csv(snapshot / "candidates.csv").columns)

    assert PATTERN_REPORT_FIELDS.isdisjoint(columns)


def test_forward_snapshots_are_unique_and_never_overwritten(tmp_path: Path):
    canonical = pd.DataFrame([decision(candidate())])
    generated = datetime(2026, 9, 5, 10, tzinfo=timezone.utc)
    run_screener.LAST_METADATA_DIAGNOSTICS = {
        "universe_member_count": 1865,
        "mapped_sector_industry_count": 1069,
        "unmapped_count": 796,
        "coverage_percentage": 57.32,
        "cache_as_of": "2026-09-04T00:00:00+00:00",
    }
    snapshot_context = {
        **context(),
        "market_cap_filter_status": "NOT ENFORCED",
        "maximum_heat_r": 3.0,
        "current_heat_r": 0.0,
        "remaining_heat_r": 3.0,
    }
    first = run_screener.write_forward_snapshot(
        canonical, pd.DataFrame(), snapshot_context, generated, tmp_path
    )
    original = (first / "metadata.json").read_text(encoding="utf-8")
    second = run_screener.write_forward_snapshot(
        canonical, pd.DataFrame(), snapshot_context, generated, tmp_path
    )
    assert first != second
    assert (first / "metadata.json").read_text(encoding="utf-8") == original
    assert {path.name for path in first.iterdir()} == {
        "candidates.csv",
        "market.json",
        "portfolio.json",
        "config.json",
        "metadata.json",
    }
    metadata = json.loads(original)
    assert metadata["signal_trading_date"] == "2026-09-04"
    assert metadata["price_data_as_of"] == "2026-09-04"
    assert metadata["candidate_count"] == 1
    assert metadata["candidate_record_hash"]
    assert metadata["candidate_logical_record_hash"]
    assert metadata["snapshot_schema_version"] == 2
    assert metadata["git_dirty"] in {True, False}
    assert metadata["data_provider"]["name"] == "yfinance"
    assert metadata["universe_methodology_version"] == (
        "NASDAQTRADER_CURRENT_LISTED_V1"
    )
    assert metadata["policy"] == {
        "earnings": "NOT_ENFORCED",
        "market_cap": "NOT_ENFORCED",
    }
    assert metadata["strategy_cohort_id"]
    assert metadata["candidate_ranking"] == [
        {"column": "Final Score", "direction": "DESC"},
        {"column": "Ticker", "direction": "ASC"},
    ]
    for name, digest in metadata["artifact_hashes"].items():
        assert run_screener._sha256_file(first / name) == digest
    assert (
        metadata["candidate_record_hash"]
        == metadata["artifact_hashes"]["candidates.csv"]
    )


def test_same_day_authorisation_ledger_survives_reruns_without_double_counting(
    tmp_path: Path,
):
    signal_root = tmp_path / "2026-09-04"
    first = signal_root / "run-1"
    second = signal_root / "run-2"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    pd.DataFrame(
        [
            {"Ticker": "AAA", "Final Decision": "FULL", "Maximum Risk R": 1.0},
            {"Ticker": "BBB", "Final Decision": "HALF", "Maximum Risk R": 0.5},
        ]
    ).to_csv(first / "candidates.csv", index=False)
    pd.DataFrame(
        [
            {"Ticker": "AAA", "Final Decision": "FULL", "Maximum Risk R": 1.0},
            {"Ticker": "CCC", "Final Decision": "HALF", "Maximum Risk R": 0.5},
        ]
    ).to_csv(second / "candidates.csv", index=False)
    for directory in (first, second):
        for name in ("market.json", "portfolio.json", "config.json"):
            (directory / name).write_text("{}", encoding="utf-8")
        (directory / "metadata.json").write_text(
            json.dumps({"signal_trading_date": "2026-09-04", "candidate_count": 2}),
            encoding="utf-8",
        )

    authorised = run_screener.load_authorized_new_risk_by_ticker("2026-09-04", tmp_path)
    assert authorised == {"AAA": 1.0, "BBB": 0.5, "CCC": 0.5}
    assert sum(authorised.values()) == config.MAX_NEW_INITIAL_R_PER_DAY


def test_partial_snapshot_makes_authorisation_ledger_unavailable(tmp_path: Path):
    partial = tmp_path / "2026-09-04" / "partial-run"
    partial.mkdir(parents=True)
    (partial / "metadata.json").write_text("{}", encoding="utf-8")
    assert (
        run_screener.load_authorized_new_risk_by_ticker("2026-09-04", tmp_path) is None
    )


def test_empty_signal_date_directory_makes_authorisation_ledger_unavailable(
    tmp_path: Path,
):
    (tmp_path / "2026-09-04").mkdir()
    assert (
        run_screener.load_authorized_new_risk_by_ticker("2026-09-04", tmp_path) is None
    )


def test_decision_context_restores_prior_same_day_authorisation(
    tmp_path: Path, monkeypatch
):
    snapshot = tmp_path / "2026-09-04" / "run-1"
    snapshot.mkdir(parents=True)
    pd.DataFrame(
        [{"Ticker": "AAA", "Final Decision": "FULL", "Maximum Risk R": 1.0}]
    ).to_csv(snapshot / "candidates.csv", index=False)
    for name in ("market.json", "portfolio.json", "config.json"):
        (snapshot / name).write_text("{}", encoding="utf-8")
    (snapshot / "metadata.json").write_text(
        json.dumps({"signal_trading_date": "2026-09-04", "candidate_count": 1}),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "FORWARD_SNAPSHOT_DIR", str(tmp_path))
    monkeypatch.setattr(
        run_screener,
        "LAST_ELIGIBLE_UNIVERSE",
        pd.DataFrame(columns=["Recent RS Score"]),
    )
    monkeypatch.setattr(
        run_screener,
        "load_portfolio_status",
        lambda *args, **kwargs: {
            "data_status": "No open positions",
            "portfolio": portfolio(),
            "open_position_count": 0,
            "portfolio_new_risk_allowed": True,
            "new_initial_risk_r_today": 0.0,
            "new_initial_risk_by_ticker_today": {},
            "new_position_count_today": 0,
        },
    )
    monkeypatch.setattr(
        run_screener,
        "market_regime_from_metrics",
        lambda *args, **kwargs: SimpleNamespace(
            regime="Strong",
            maximum_heat_r=3.0,
            new_risk_allowed=True,
            data_complete=True,
            confidence="High",
        ),
    )
    result = run_screener.build_decision_context(
        pd.DataFrame([{"Signal Date": "2026-09-04"}]),
        pd.DataFrame(),
        "Strong",
        {},
    )
    assert result["portfolio_status"]["new_initial_risk_r_today"] == 1.0
    assert result["portfolio_status"]["new_initial_risk_by_ticker_today"] == {
        "AAA": 1.0
    }
    assert result["portfolio_status"]["new_position_count_today"] == 1
