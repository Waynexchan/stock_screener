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
from scripts.validate_report import validate_csv_semantics


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
) -> dict[str, object]:
    return {
        "market_regime": SimpleNamespace(regime="Strong"),
        "drawdown": calculate_drawdown_state(100_000, 100_000),
        "portfolio_status": {
            "portfolio": current_portfolio or portfolio(),
            "open_position_count": open_positions,
            "portfolio_new_risk_allowed": new_risk_allowed,
        },
    }


def decision(row: dict[str, object], decision_context: dict[str, object] | None = None):
    return run_screener.apply_canonical_decision_pipeline(
        pd.DataFrame([row]), decision_context or context()
    ).iloc[0]


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
    categories = {
        name: canonical[canonical["Category"].eq(name)].copy()
        for name in run_screener.CATEGORY_PRIORITY
    }
    top_action = canonical[canonical["Final Decision"].isin(["FULL", "HALF"])]
    html_path = tmp_path / "report.html"
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
