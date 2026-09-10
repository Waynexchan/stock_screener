from pathlib import Path

import numpy as np
import pandas as pd

import config
import ai_analysis
from decision_system import (
    construct_trade_plan,
    decide_candidate,
    load_portfolio_status,
    market_regime_from_metrics,
    PortfolioRisk,
    qualify_industries,
    score_candidate,
)
import run_screener


def _industry_members(
    size: int, industry: str = "Restaurants", setup_ticker: bool = True
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Ticker": f"T{i}",
                "Industry": industry,
                "Sector": "Consumer Cyclical",
                "Return 5D": -1.0,
                "Return 10D": 2.0,
                "Return 20D": 4.0,
                "Relative Return 10D": 1.0,
                "Relative Return 20D": 2.0,
                "Above 10EMA": True,
                "Above 20EMA": True,
                "Above 50MA": True,
                "Near 20D High": True,
                "Near 52W High": True,
                "Valid Breakout": i == 0,
                "Failed Breakout": False,
                "High Volume Breakdown": False,
                "Recent RS Score": 80.0,
                "Long-Term RS Score": 90.0,
                "Is Candidate": setup_ticker and i == 0,
            }
            for i in range(size)
        ]
    )


def test_portfolio_missing_is_not_zero_and_empty_file_is_real_zero(tmp_path: Path):
    missing = load_portfolio_status(str(tmp_path / "missing.csv"), "Strong")
    assert missing["portfolio"] is None
    assert not missing["portfolio_new_risk_allowed"]
    empty = tmp_path / "positions.csv"
    empty.write_text("ticker,status\n", encoding="utf-8")
    status = load_portfolio_status(str(empty), "Strong")
    assert status["data_status"] == "No open positions"
    assert status["portfolio"].portfolio_heat_r == 0


def test_portfolio_file_without_status_column_is_invalid_not_zero(tmp_path: Path):
    positions = tmp_path / "positions.csv"
    positions.write_text(
        "ticker,entry_date,entry_price,initial_stop,current_stop,shares\n"
        "IMVT,2026-08-01,40,38,39,100\n",
        encoding="utf-8",
    )
    status = load_portfolio_status(str(positions), "Strong")
    assert status["data_status"] == "Invalid: required status column is missing"
    assert status["portfolio"] is None
    assert status["open_position_count"] is None
    assert not status["portfolio_new_risk_allowed"]

    positions.write_text(
        "ticker,entry_date,entry_price,initial_stop,current_stop,shares,status\n"
        "IMVT,2026-08-01,40,38,39,100,\n",
        encoding="utf-8",
    )
    blank = load_portfolio_status(str(positions), "Strong")
    assert blank["data_status"] == "Invalid: position status is missing"
    assert blank["portfolio"] is None
    assert blank["open_position_count"] is None
    assert not blank["portfolio_new_risk_allowed"]


def test_portfolio_file_with_unknown_status_is_invalid_not_zero(tmp_path: Path):
    positions = tmp_path / "positions.csv"
    positions.write_text(
        "ticker,entry_date,entry_price,initial_stop,current_stop,shares,status\n"
        "IMVT,2026-08-01,40,38,39,100,opne\n",
        encoding="utf-8",
    )
    status = load_portfolio_status(str(positions), "Strong")
    assert status["data_status"] == "Invalid: unsupported position status: opne"
    assert status["portfolio"] is None
    assert status["open_position_count"] is None
    assert not status["portfolio_new_risk_allowed"]


def test_minimal_position_input_is_enriched_from_current_snapshot(tmp_path: Path):
    positions = tmp_path / "positions.csv"
    positions.write_text(
        "ticker,entry_date,entry_price,initial_stop,current_stop,shares,status\n"
        "IMVT,2026-08-01,40,38,39,100,open\n",
        encoding="utf-8",
    )
    snapshot = pd.DataFrame(
        [
            {
                "Ticker": "IMVT",
                "Price": 42.0,
                "Industry": "Biotechnology",
                "Sector": "Healthcare",
            }
        ]
    )
    status = load_portfolio_status(str(positions), "Strong", snapshot)
    assert status["data_status"] == "Valid (auto-enriched)"
    assert status["portfolio"].positions[0].current_open_risk_dollars == 300
    assert set(status["auto_filled_fields"]) >= {
        "current_price",
        "industry",
        "sector",
        "last_updated",
    }


def test_minimal_position_without_snapshot_price_is_invalid_not_zero(tmp_path: Path):
    positions = tmp_path / "positions.csv"
    positions.write_text(
        "ticker,entry_date,entry_price,initial_stop,current_stop,shares,status\n"
        "IMVT,2026-08-01,40,38,39,100,open\n",
        encoding="utf-8",
    )
    status = load_portfolio_status(str(positions), "Strong", pd.DataFrame())
    assert status["portfolio"] is None
    assert status["data_status"].startswith("Invalid / Stale")
    assert not status["portfolio_new_risk_allowed"]


def test_valid_rr_is_not_mislabeled_as_weak():
    reasons = run_screener.setup_noise_reasons(
        {
            "Recent RS Score": 80,
            "Industry Qualified": True,
            "Risk/Reward Quality": "Valid R/R",
            "Trade Plan Confidence": "High",
            "Realistic Target Source": "prior high resistance",
            "Extension Status": "Not Extended",
            "VCP Label": "Good VCP",
            "Tightness Label": "Normal",
            "Pullback Quality": "B - Healthy Pullback",
            "RS Trend": "Improving",
            "Action": "Review breakout confirmation",
            "Volume Ratio": 1.2,
            "Nearest Support Distance ATR": 0.5,
            "Industry Setup Count": 2,
            "Sister Confirmation State": "Sister confirmation passed",
        }
    )
    assert "weak R/R" not in reasons


def test_production_review_tier_cannot_promote_model_2r_target():
    row = {
        "Recent RS Score": 90,
        "RS Score": 90,
        "Industry Qualified": True,
        "Industry Setup Count": 3,
        "Sister Confirmation State": "Sister confirmation passed",
        "Risk/Reward Quality": "Excellent R/R",
        "Trade Plan Confidence": "Medium",
        "Realistic Target Source": "model 2R feasibility target",
        "Extension Status": "Not Extended",
        "VCP Label": "Good VCP",
        "Tightness Label": "Tight",
        "Pullback Quality": "A - Ideal Pullback",
        "RS Trend": "Emerging Leader",
        "Volume Ratio": 1.5,
        "Nearest Support Distance ATR": 0.5,
        "Review Priority Score": 95,
        "Action": "Confirmed pullback entry review",
    }
    assert run_screener.review_tier(row) != "Review Now"
    assert (
        "model 2R target requires chart-confirmed resistance"
        in run_screener.setup_noise_reasons(row)
    )


def test_primary_report_lists_are_unique_and_limited():
    rows = [
        {
            "Ticker": f"T{i // 2}" if i < 2 else f"T{i}",
            "Final Decision": "WATCH" if i < 12 else "NO TRADE",
            "Final Score": 100 - i,
        }
        for i in range(20)
    ]
    watch, blocked = run_screener.primary_decision_sections(pd.DataFrame(rows))
    assert len(watch) <= 8 and len(blocked) <= 8
    assert watch["Ticker"].is_unique and blocked["Ticker"].is_unique


def test_market_does_not_claim_complete_when_major_factors_are_missing():
    regime = market_regime_from_metrics(
        {
            "spy_above_20ema": True,
            "spy_above_50ma": True,
            "qqq_above_20ema": True,
            "qqq_above_50ma": True,
            "breadth_above_20ema": 70,
            "breadth_above_50ma": 65,
        }
    )
    assert not regime.data_complete
    assert regime.confidence == "Low"
    assert not regime.new_risk_allowed


def test_model_2r_target_cannot_by_itself_be_allowed():
    market = market_regime_from_metrics(
        {
            "spy_above_20ema": True,
            "spy_above_50ma": True,
            "qqq_above_20ema": True,
            "qqq_above_50ma": True,
            "ema20_slope_positive": True,
            "ema50_slope_positive": True,
            "breadth_above_20ema": 70,
            "breadth_above_50ma": 65,
            "breakout_success_rate": 50,
            "breakout_failure_rate": 10,
            "breakout_sample_size": 20,
            "leadership_contribution": 3,
            "leadership_sample_size": 20,
            "volatility_contribution": 1,
        }
    )
    portfolio = PortfolioRisk((), 0, 4, 4, {}, {}, {}, ())
    result = decide_candidate(
        {
            "Ticker": "TEST",
            "Industry": "Software",
            "Theme": "AI",
            "Recent RS Score": 95,
            "RS Score": 90,
            "Industry Qualified": True,
            "Sister Confirmation": True,
            "Tightness Label": "Tight",
            "VCP Label": "Good VCP",
            "Extension Status": "Not Extended",
            "Planned Entry": 100,
            "Initial Stop": 95,
            "Realistic Target": 110,
            "Realistic Target Source": "model 2R feasibility target",
            "Trade Plan Confidence": "Medium",
            "Distance From Pivot %": 1,
            "Nearest Support Distance ATR": 0.5,
            "Setup Quality Score": 95,
            "Volume Quality Score": 95,
            "Entry Stop Quality Score": 90,
            "Intermediate Trend Score": 90,
        },
        market,
        portfolio,
    )
    assert result.decision == "NO TRADE"
    assert "model 2R target requires chart-confirmed resistance" in result.reasons


def test_industry_raw_candidates_cannot_be_below_qualifying_setups():
    members = _industry_members(5, setup_ticker=False)
    result = qualify_industries(members, pd.DataFrame({"Ticker": ["T0"]})).iloc[0]
    assert result["Raw Candidate Count"] >= result["Qualifying Setup Count"]


def test_small_sample_labels_and_no_qualification():
    for size, quality in [
        (1, "Insufficient"),
        (2, "Insufficient"),
        (4, "Thin"),
        (5, "Adequate"),
        (10, "Strong"),
    ]:
        members = _industry_members(size)
        setups = pd.DataFrame({"Ticker": ["T0"]})
        row = qualify_industries(members, setups).iloc[0]
        assert row["Breadth Sample Quality"] == quality
        if size < 5:
            assert not bool(row["Industry Qualified"])
            assert row["Industry Classification"] != "Broadly Improving"


def test_lagging_restaurants_with_zero_setups_has_no_actionable_rank():
    members = _industry_members(5, setup_ticker=False)
    members["Return 10D"] = -1.0
    members["Relative Return 20D"] = -0.5
    row = qualify_industries(members, pd.DataFrame(columns=["Ticker"])).iloc[0]
    assert not bool(row["Industry Qualified"])
    assert pd.isna(row["Industry Rank"])
    assert row["Industry Classification"] == "Long-Term Leader Currently Lagging"


def test_trade_plan_is_structural_and_never_uses_future_data():
    dates = pd.date_range("2026-01-01", periods=30, freq="B")
    close = np.linspace(100, 102, 30)
    history = pd.DataFrame(
        {"High": close + 1, "Low": close - 1, "Close": close, "ATR20": 2.0}, index=dates
    )
    pullback = construct_trade_plan(history, "Pullback Candidates")
    breakout = construct_trade_plan(history, "Breakout Candidates")
    tight = construct_trade_plan(history, "Tight Consolidation Candidates")
    assert pullback.planned_entry is not None
    assert breakout.planned_entry is not None
    assert tight.planned_entry is not None
    assert (
        "source" not in pullback.planned_entry_source.lower()
        or pullback.planned_entry_source
    )
    changed = history.copy()
    changed.loc[dates[-1] + pd.Timedelta(days=1)] = [999, 1, 500, 2]
    assert construct_trade_plan(changed, "Pullback Candidates", dates[-1]) == pullback
    assert construct_trade_plan(history, "ambiguous").planned_entry is None
    assert pullback.reward_risk_ratio is not None
    assert pullback.reward_risk_ratio >= 2.0


def test_final_score_survives_hard_gate_and_summary_uses_canonical_records():
    row = {
        "Ticker": "HPE",
        "Recent RS Score": 83,
        "RS Score": 95,
        "Tightness Label": "Loose",
        "VCP Label": "Poor VCP",
        "Extension Status": "Not Extended",
        "Volume Ratio": 0.5,
        "10 Day Range %": 20,
        "Industry Qualified": False,
        "Sister Confirmation": False,
    }
    score = score_candidate(row)
    assert score.final_score >= 0 and score.base_score > score.final_score
    frame = pd.DataFrame(
        [
            {
                **row,
                "Final Decision": "NO TRADE",
                "RS Trend": "Emerging Leader",
                "Price Data Warning": "",
            },
            {
                **row,
                "Final Decision": "NO TRADE",
                "RS Trend": "Emerging Leader",
                "Price Data Warning": "",
            },
        ]
    )
    counts = run_screener.report_summary_counts(frame)
    assert counts["blocked"] == 1
    assert counts["emerging_leaders"] == 1
    assert counts["caution_rows"] == 1


def test_missing_recent_rs_never_becomes_a_perfect_score():
    score = score_candidate(
        {
            "Ticker": "DCTH",
            "Recent RS Score": np.nan,
            "RS Score": 82,
            "10 Day Range %": 7.5,
            "Volume Ratio": 0.73,
            "Trade Plan Confidence": "Medium",
            "Industry Qualified": False,
            "Sister Confirmation": False,
        }
    )
    assert pd.isna(score.recent_rs_component)
    assert pd.isna(score.final_score)


def test_ai_payload_cannot_call_half_candidate_a_best_opportunity():
    payload = {
        "rankings": [{"ticker": "MU", "status": "Best Opportunity"}],
        "stocks_to_wait": [],
    }
    frame = pd.DataFrame([{"Ticker": "MU", "Final Decision": "HALF"}])
    safe = ai_analysis._enforce_payload_decisions(payload, frame, "Strong")
    assert safe["rankings"][0]["status"] == "Watch"
    assert any("MU - HALF" in item for item in safe["stocks_to_wait"])


def test_decision_invariants_reject_actionable_missing_rs_or_invalid_rr():
    frame = pd.DataFrame(
        [
            {
                "Ticker": "BAD",
                "Final Decision": "HALF",
                "Recent RS Score": np.nan,
                "Reward/Risk Ratio": 1.5,
                "Maximum Shares": 10,
                "Maximum Risk R": 0.5,
            }
        ]
    )
    errors = run_screener.validate_canonical_decision_invariants(frame)
    assert "actionable row has missing Recent RS" in errors
    assert "actionable row has invalid structural R/R" in errors


def test_loose_poor_vcp_is_reclassified_and_blocked():
    frame = pd.DataFrame(
        [
            {
                "Ticker": "NESR",
                "Category": "Pullback Candidates",
                "Pullback Quality": "A - Ideal Pullback",
                "Tightness Label": "Loose",
                "VCP Label": "Poor VCP",
                "Extension Status": "Not Extended",
                "Recent RS Score": 80,
                "RS Score": 90,
                "Volume Ratio": 0.8,
                "10 Day Range %": 18,
                "Industry Qualified": False,
                "Sister Confirmation": False,
                "Risk/Reward Quality": "Not Available",
                "Price Data Warning": "",
                "Action": "Watch only",
                "Support Signal": "Recent support",
            }
        ]
    )
    result = run_screener.add_review_guidance_columns(frame).iloc[0]
    assert result["Category"] == "Developing Base Candidates"
    assert result["Pullback Quality"].startswith("C")
    assert result["Final Decision"] == ""
    assert pd.notna(result["Final Score"])


def test_market_character_accepts_qualified_industry_schema():
    industries = pd.DataFrame([{"Industry": "Asset Management", "Above 20EMA %": 80.0}])
    character = run_screener.determine_market_character({}, "Strong", industries)
    assert character == "Neutral Rotation Market"


def test_displayed_two_r_survives_price_rounding():
    result = run_screener.calculate_reward_risk(39.89, 36.63, 46.41)
    assert result.ratio == 2.0
    assert result.valid


def test_offline_preview_discloses_unavailable_system_warnings(tmp_path):
    output = tmp_path / "preview.html"
    run_screener.write_html(
        pd.DataFrame(),
        pd.DataFrame(),
        {},
        pd.DataFrame(),
        pd.DataFrame(columns=["Symbol", "10EMA", "20EMA", "50MA"]),
        "Neutral",
        "Offline preview",
        str(output),
    )
    html = output.read_text(encoding="utf-8")
    assert "System-level warnings unavailable in offline report preview" in html


def test_breakout_failure_indicator_is_boolean_and_stable():
    dates = pd.date_range("2026-01-01", periods=80, freq="B")
    close = np.linspace(100.0, 120.0, len(dates))
    history = pd.DataFrame(
        {
            "Open": close - 0.2,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": np.full(len(dates), 1_000_000),
        },
        index=dates,
    )
    result = run_screener.add_indicators(history)
    assert "BREAKOUT_FAILED_10D" in result
    assert result["BREAKOUT_FAILED_10D"].dtype == bool


def test_negative_market_factor_uses_negative_human_readable_wording():
    metrics = {
        "spy_above_20ema": True,
        "spy_above_50ma": True,
        "qqq_above_20ema": True,
        "qqq_above_50ma": True,
        "breadth_above_20ema": 60.0,
        "breadth_above_50ma": 55.0,
        "ema20_slope_positive": True,
        "ema50_slope_positive": False,
        "breakout_success_rate": 50.0,
        "breakout_failure_rate": 20.0,
        "breakout_sample_size": 10,
        "leadership_contribution": 1.0,
        "leadership_sample_size": 10,
        "volatility_contribution": 0.0,
    }
    regime = market_regime_from_metrics(metrics)
    assert "50MA slope not positive" in regime.negative_factors
    assert "ema50_slope_positive" not in regime.negative_factors


def test_valid_rr_is_recognised_by_action_and_review_mapping():
    row = {
        "Category": "Pullback Candidates",
        "Ticker": "PASS",
        "Recent RS Score": 85.0,
        "RS Score": 90.0,
        "RS Trend": "Improving",
        "Industry Qualified": True,
        "Industry Setup Count": 3,
        "Industry Rank": 1,
        "Sister Confirmation": True,
        "Sister Confirmation State": "Sister confirmation passed",
        "Tightness Label": "Normal",
        "VCP Label": "Average VCP",
        "Pullback Quality": "A - Ideal Pullback",
        "Extension Status": "Not Extended",
        "Risk/Reward Quality": "Valid R/R",
        "Planned Entry": 100.0,
        "Initial Stop": 95.0,
        "Realistic Target": 110.0,
        "Realistic Target Source": "prior high resistance",
        "Trade Plan Confidence": "High",
        "Distance From Pivot %": 1.0,
        "Nearest Support Distance ATR": 0.5,
        "Support Signal": "Close above prior high",
        "Volume Ratio": 1.0,
        "Avg Volume": 1_000_000,
        "HIGH_52W": 105.0,
        "Close": 100.0,
        "MA50": 95.0,
        "Price Data Warning": "",
    }
    assert run_screener.action_for_row(row) == "Confirmed pullback entry review"
    row["Action"] = run_screener.action_for_row(row)
    assert run_screener.review_tier(row) == "Review Now"


def test_below_threshold_recent_rs_has_exact_watch_reason():
    row = {
        "Recent RS Score": config.MIN_RECENT_RS_ALLOWED - 1,
        "Industry Qualified": True,
        "Industry Setup Count": 3,
        "Sister Confirmation State": "Sister confirmation passed",
        "Risk/Reward Quality": "Valid R/R",
        "Trade Plan Confidence": "High",
        "Realistic Target Source": "prior high resistance",
        "Extension Status": "Not Extended",
        "Pullback Quality": "A - Ideal Pullback",
        "VCP Label": "Average VCP",
        "Tightness Label": "Normal",
        "RS Trend": "Improving",
        "Volume Ratio": 1.0,
        "Nearest Support Distance ATR": 0.5,
        "Action": "Monitor quiet pullback",
    }
    reasons = run_screener.setup_noise_reasons(row)
    assert "Recent RS below threshold" in reasons
    assert run_screener.review_tier(row) == "Watch Later"
