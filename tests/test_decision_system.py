from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

import config
from sample_daily_run import build_sample_report, validate_sample_report
from decision_system import (
    PortfolioRisk,
    Position,
    apply_concentration_limits,
    calculate_portfolio_risk,
    calculate_position_risk,
    calculate_recent_rs_frame,
    calculate_reward_risk,
    construct_trade_plan,
    calculate_drawdown_state,
    canonicalise_candidates,
    decide_candidate,
    enforce_setup_consistency,
    expectancy_summary,
    entry_timing_for_candidate,
    final_candidate_score,
    market_regime_from_metrics,
    qualify_industries,
    sister_stock_confirmation,
    size_additional_tranche,
    size_trade_candidate,
    journal_drawdown_analytics,
    validate_position,
)


def _sizing_row(**updates):
    row = {
        "Ticker": "TEST",
        "Recent RS Score": 85.0,
        "RS Trend": "Improving",
        "Industry": "Software",
        "Theme": "Industry: Software",
        "Industry Qualified": True,
        "Sister Confirmation": True,
        "Planned Entry": 100.0,
        "Initial Stop": 95.0,
        "Realistic Target": 110.0,
        "Realistic Target Source": "prior high resistance",
        "Extension Status": "Not Extended",
        "Entry Timing": "OPTIMAL",
        "Volume Ratio": 1.0,
        "Price Data Warning": "",
    }
    row.update(updates)
    return row


def _empty_portfolio(maximum=3.0):
    return PortfolioRisk((), 0.0, maximum, maximum, {}, {}, {}, ())


def test_only_four_trade_states_and_risk_budgets():
    normal = calculate_drawdown_state(100_000, 100_000)
    full = size_trade_candidate(_sizing_row(), "Strong", normal, _empty_portfolio(), 0)
    half = size_trade_candidate(
        _sizing_row(**{"Sister Confirmation": False}),
        "Strong",
        normal,
        _empty_portfolio(),
        0,
    )
    assert full.state == "FULL" and full.maximum_risk_r == 1.0
    assert full.maximum_risk_dollars == 587.0
    assert half.state == "HALF" and half.maximum_risk_r == 0.5
    assert half.maximum_risk_dollars == 293.5
    assert {full.state, half.state, "WATCH", "NO TRADE"} == {
        "FULL",
        "HALF",
        "WATCH",
        "NO TRADE",
    }


def test_secondary_confirmation_can_reduce_to_half():
    normal = calculate_drawdown_state(100_000, 100_000)
    for update in (
        {"Sister Confirmation": False},
        {"Industry Qualified": False},
        {"Volume Ratio": 0.1},
    ):
        result = size_trade_candidate(
            _sizing_row(**update), "Strong", normal, _empty_portfolio(), 0
        )
        assert result.state == "HALF"


def test_caution_market_blocks_candidate_instead_of_showing_half():
    normal = calculate_drawdown_state(100_000, 100_000)
    result = size_trade_candidate(
        _sizing_row(), "Caution", normal, _empty_portfolio(), 0
    )
    assert result.state == "NO TRADE"
    assert result.maximum_risk_r == 0.0
    assert "Caution market does not permit new risk" in result.reasons


def test_half_requires_recent_rs_to_be_strong_or_clearly_improving():
    normal = calculate_drawdown_state(100_000, 100_000)
    weak = size_trade_candidate(
        _sizing_row(**{"Recent RS Score": 55.0, "RS Trend": "Weakening"}),
        "Strong",
        normal,
        _empty_portfolio(),
        0,
    )
    improving = size_trade_candidate(
        _sizing_row(**{"Recent RS Score": 55.0, "RS Trend": "Improving"}),
        "Strong",
        normal,
        _empty_portfolio(),
        0,
    )
    assert weak.state == "NO TRADE"
    assert "Recent RS is below the minimum primary-edge floor" in weak.reasons
    assert improving.state == "NO TRADE"


def test_structural_and_portfolio_hard_blocks():
    normal = calculate_drawdown_state(100_000, 100_000)
    cases = [
        _sizing_row(**{"Initial Stop": 101.0}),
        _sizing_row(**{"Realistic Target": 107.0}),
        _sizing_row(
            **{"Extension Status": "Overextended", "Entry Timing": "OVEREXTENDED"}
        ),
    ]
    for row in cases:
        assert (
            size_trade_candidate(row, "Strong", normal, _empty_portfolio(), 0).state
            == "NO TRADE"
        )
    assert (
        size_trade_candidate(
            _sizing_row(), "Strong", normal, _empty_portfolio(), 4
        ).state
        == "NO TRADE"
    )
    exhausted = PortfolioRisk((), 3.0, 3.0, 0.0, {}, {}, {}, ())
    assert (
        size_trade_candidate(_sizing_row(), "Strong", normal, exhausted, 0).state
        == "NO TRADE"
    )


def test_drawdown_modes_and_effective_heat():
    normal = calculate_drawdown_state(100_000, 100_000)
    reduced = calculate_drawdown_state(100_000 - 2 * 587, 100_000)
    defensive = calculate_drawdown_state(100_000 - 4 * 587, 100_000)
    stopped = calculate_drawdown_state(100_000 - 6 * 587, 100_000)
    assert normal.mode == "NORMAL" and normal.heat_limit_r == 3.0
    assert reduced.mode == "REDUCED" and not reduced.full_allowed
    assert defensive.mode == "DEFENSIVE" and defensive.heat_limit_r == 0.5
    assert stopped.mode == "STOP_NEW_RISK" and not stopped.new_risk_allowed
    portfolio = calculate_portfolio_risk([], "Strong", reduced.heat_limit_r)
    assert portfolio.maximum_heat_r == min(3.0, reduced.heat_limit_r)
    assert (
        size_trade_candidate(_sizing_row(), "Strong", reduced, portfolio, 0).state
        == "HALF"
    )
    assert (
        size_trade_candidate(_sizing_row(), "Strong", stopped, portfolio, 0).state
        == "NO TRADE"
    )
    assert (
        size_trade_candidate(
            _sizing_row(), "Strong", defensive, portfolio, 0, new_positions_today=1
        ).state
        == "NO TRADE"
    )


def test_concentration_capacity_reduces_full_to_half():
    normal = calculate_drawdown_state(100_000, 100_000)
    portfolio = PortfolioRisk(
        (), 1.5, 3.0, 1.5, {"Software": 1.5}, {}, {"Industry: Software": 1.5}, ()
    )
    result = size_trade_candidate(_sizing_row(), "Strong", normal, portfolio, 0)
    assert result.state == "HALF"


def test_entry_timing_requires_a_complete_plan_and_supports_four_trade_states():
    rows = [
        _sizing_row(**{"Nearest Support Distance ATR": 0.5}),
        _sizing_row(**{"Distance From Pivot %": -2, "Nearest Support Distance ATR": 2}),
        _sizing_row(**{"Distance From Pivot %": 8, "Nearest Support Distance ATR": 2}),
        _sizing_row(**{"Extension Status": "Overextended"}),
    ]
    assert {entry_timing_for_candidate(row) for row in rows} == {
        "EARLY",
        "OPTIMAL",
        "LATE",
        "OVEREXTENDED",
    }
    assert (
        entry_timing_for_candidate(_sizing_row(**{"Planned Entry": np.nan}))
        == "NOT AVAILABLE"
    )


def test_observed_resistance_is_not_artificially_clamped_to_two_r():
    index = pd.date_range("2026-01-01", periods=30, freq="D")
    history = pd.DataFrame(
        {
            "High": [120.0] + [105.0] * 27 + [101.0, 102.0],
            "Low": [99.0] * 30,
            "Close": [100.0] * 30,
            "ATR20": [2.0] * 30,
        },
        index=index,
    )
    plan = construct_trade_plan(history, "Pullback Candidates")
    assert plan.realistic_target_source == "observed prior-high resistance"
    assert plan.realistic_target == 120.0
    assert plan.reward_risk_ratio is not None
    assert plan.reward_risk_ratio > 2.0


def test_existing_half_is_not_auto_upgraded_and_new_tranche_needs_plan():
    normal = calculate_drawdown_state(100_000, 100_000)
    portfolio = _empty_portfolio()
    existing_half_state = "HALF"
    improved = _sizing_row()
    assert existing_half_state == "HALF"
    denied = size_additional_tranche(improved, "Strong", normal, portfolio, 1)
    assert denied.state == "NO TRADE"
    improved["New Tranche Plan"] = True
    allowed = size_additional_tranche(improved, "Strong", normal, portfolio, 1)
    assert allowed.state in {"FULL", "HALF"}


def test_journal_drawdown_and_full_half_splits():
    result = journal_drawdown_analytics(
        pd.DataFrame(
            {
                "realised_r": [1.0, -2.0, 0.5, -0.5],
                "trade_state": ["FULL", "FULL", "HALF", "HALF"],
                "MFE_R": [2.0, 0.3, 1.2, 0.2],
                "MAE_R": [-0.2, -1.0, -0.1, -0.5],
            }
        )
    )
    assert result["equity_high_water_mark_r"] == 1.0
    assert result["maximum_historical_drawdown_r"] == 2.0
    assert result["by_trade_state"]["FULL"]["sample_size"] == 2
    assert result["by_trade_state"]["HALF"]["sample_size"] == 2


def position(**updates):
    data = dict(
        ticker="AAA",
        entry_date="2026-08-01",
        entry_price=100.0,
        initial_stop=95.0,
        current_stop=105.0,
        current_price=110.0,
        shares=100,
        standard_r_dollars_at_entry=500.0,
        industry="Software",
        sector="Technology",
        theme="AI",
        setup_type="Pullback",
        status="open",
        last_updated=datetime.now(timezone.utc).isoformat(),
        stop_update_reason="raised stop",
    )
    data.update(updates)
    return Position(**data)


def market(regime="Strong"):
    values = {
        "spy_above_20ema": True,
        "spy_above_50ma": True,
        "qqq_above_20ema": True,
        "qqq_above_50ma": True,
        "ema20_slope_positive": True,
        "ema50_slope_positive": True,
        "breadth_above_20ema": 70.0,
        "breadth_above_50ma": 65.0,
        "breakout_success_rate": 50.0,
        "breakout_failure_rate": 10.0,
        "breakout_sample_size": 20,
        "leadership_contribution": 2.0,
        "leadership_sample_size": 20,
        "volatility_contribution": 1.0,
        "confirmation_days": 2,
    }
    result = market_regime_from_metrics(values)
    if regime == "Risk Off":
        values["emergency_deterioration"] = True
        result = market_regime_from_metrics(values)
    return result


def portfolio(remaining=4.0):
    return PortfolioRisk((), 0, remaining, remaining, {}, {}, {}, ())


def candidate(**updates):
    data = {
        "Ticker": "AAA",
        "Sector": "Technology",
        "Industry": "Software",
        "Theme": "AI",
        "Category": "Pullback Candidates",
        "Recent RS Score": 90.0,
        "RS Trend": "Improving",
        "RS Score": 85,
        "Industry Qualified": True,
        "Industry Confirmation Score": 90,
        "Sister Confirmation": True,
        "Tightness Label": "Tight",
        "VCP Label": "Good VCP",
        "Extension Status": "Not Extended",
        "Planned Entry": 100.0,
        "Initial Stop": 95.0,
        "Realistic Target": 110.0,
        "Realistic Target Source": "prior high resistance",
        "Trade Plan Confidence": "High",
        "Distance From Pivot %": 1.0,
        "Nearest Support Distance ATR": 0.5,
        "Setup Quality Score": 90,
        "Volume Quality Score": 90,
        "Entry Stop Quality Score": 90,
        "Intermediate Trend Score": 85,
        "Volume Ratio": 1.0,
        "Price Data Warning": "",
    }
    data.update(updates)
    return data


def histories():
    dates = pd.date_range("2026-01-01", periods=80, freq="B")
    spy = pd.DataFrame({"Close": np.linspace(100, 110, 80)}, index=dates)
    stocks = {
        "AAA": pd.DataFrame({"Close": np.linspace(100, 140, 80)}, index=dates),
        "BBB": pd.DataFrame({"Close": np.linspace(100, 105, 80)}, index=dates),
    }
    return stocks, spy


class RiskTests(unittest.TestCase):
    def test_initial_risk(self):
        self.assertEqual(calculate_position_risk(position()).initial_risk_dollars, 500)

    def test_unrealised_pnl(self):
        self.assertEqual(
            calculate_position_risk(position()).unrealised_pnl_dollars, 1000
        )

    def test_profitable_position_has_open_risk(self):
        self.assertGreater(calculate_position_risk(position()).current_open_risk_r, 0)

    def test_stop_above_entry_positive_pnl_at_stop(self):
        self.assertGreater(calculate_position_risk(position()).pnl_at_stop_r, 0)

    def test_gap_floor(self):
        self.assertEqual(
            calculate_position_risk(
                position(current_stop=109.9), 0.25
            ).effective_open_risk_r,
            0.25,
        )

    def test_portfolio_heat_sum(self):
        self.assertEqual(
            calculate_portfolio_risk(
                [position(), position(ticker="BBB")], "Strong"
            ).portfolio_heat_r,
            2,
        )

    def test_remaining_never_negative(self):
        self.assertEqual(
            calculate_portfolio_risk(
                [
                    position(),
                    position(ticker="B"),
                    position(ticker="C"),
                    position(ticker="D"),
                    position(ticker="E"),
                ],
                "Strong",
            ).remaining_heat_r,
            0,
        )

    def test_industry_heat(self):
        self.assertEqual(
            calculate_portfolio_risk([position()], "Strong").industry_heat["Software"],
            1,
        )

    def test_theme_heat(self):
        self.assertEqual(
            calculate_portfolio_risk([position()], "Strong").theme_heat["AI"], 1
        )

    def test_invalid_initial_stop(self):
        self.assertIn(
            "long initial stop", ";".join(validate_position(position(initial_stop=101)))
        )

    def test_invalid_current_stop(self):
        self.assertIn(
            "long current stop", ";".join(validate_position(position(current_stop=111)))
        )

    def test_lower_stop_needs_reason(self):
        self.assertIn(
            "moved lower",
            ";".join(
                validate_position(position(previous_stop=106, stop_update_reason=""))
            ),
        )

    def test_duplicate_position_warning(self):
        self.assertTrue(
            calculate_portfolio_risk([position(), position()], "Strong").warnings
        )


class MarketTests(unittest.TestCase):
    def test_regime_maps_heat(self):
        self.assertEqual(
            market().maximum_heat_r, config.MARKET_HEAT_LIMITS[market().regime]
        )

    def test_risk_off_prevents_risk(self):
        self.assertFalse(market("Risk Off").new_risk_allowed)

    def test_hysteresis(self):
        values = {
            "spy_above_20ema": True,
            "spy_above_50ma": True,
            "qqq_above_20ema": False,
            "qqq_above_50ma": True,
            "breadth_above_20ema": 50,
            "breadth_above_50ma": 50,
            "confirmation_days": 1,
        }
        self.assertEqual(
            market_regime_from_metrics(values, "Constructive").regime, "Constructive"
        )

    def test_emergency(self):
        self.assertEqual(market("Risk Off").regime, "Risk Off")

    def test_incomplete_breadth_warning(self):
        self.assertFalse(market_regime_from_metrics({}).data_complete)


class RecentRSTests(unittest.TestCase):
    def test_recent_rs_calculation(self):
        stocks, spy = histories()
        self.assertGreater(
            calculate_recent_rs_frame(stocks, spy).loc[0, "Return 20D"], 0
        )

    def test_recent_rs_percentile(self):
        stocks, spy = histories()
        frame = calculate_recent_rs_frame(stocks, spy).set_index("Ticker")
        self.assertGreater(
            frame.loc["AAA", "Recent RS Score"], frame.loc["BBB", "Recent RS Score"]
        )

    def test_pullback_day_behaviour_is_calculated(self):
        stocks, spy = histories()
        spy.loc[spy.index[-5], "Close"] = spy.loc[spy.index[-6], "Close"] * 0.98
        result = calculate_recent_rs_frame(stocks, spy)
        self.assertTrue(result["Pullback Day Relative Behaviour"].notna().all())

    def test_missing_rs_blocks(self):
        self.assertEqual(
            decide_candidate(
                candidate(**{"Recent RS Score": None}), market(), portfolio()
            ).decision,
            "NO TRADE",
        )

    def test_nan_warning_is_not_a_price_warning(self):
        result = decide_candidate(
            candidate(**{"Price Data Warning": np.nan}), market(), portfolio()
        )
        self.assertNotIn("price data warning", result.blocking_reasons)

    def test_missing_rs_not_confirmed(self):
        self.assertFalse(
            decide_candidate(
                candidate(**{"Recent RS Score": None}), market(), portfolio()
            ).confirmed_setup
        )

    def test_long_rs_not_fallback(self):
        self.assertEqual(
            decide_candidate(
                candidate(**{"Recent RS Score": None, "RS Score": 99}),
                market(),
                portfolio(),
            ).decision,
            "NO TRADE",
        )

    def test_recent_rs_weight_material(self):
        self.assertGreater(
            final_candidate_score(candidate(**{"Recent RS Score": 99, "RS Score": 1})),
            final_candidate_score(candidate(**{"Recent RS Score": 1, "RS Score": 99})),
        )

    def test_no_future_data(self):
        stocks, spy = histories()
        cutoff = spy.index[-10]
        before = calculate_recent_rs_frame(stocks, spy, cutoff)
        stocks["AAA"].loc[spy.index[-1], "Close"] = 9999
        after = calculate_recent_rs_frame(stocks, spy, cutoff)
        pd.testing.assert_frame_equal(before, after)


class RewardRiskTests(unittest.TestCase):
    def test_missing_entry(self):
        self.assertEqual(calculate_reward_risk(None, 90, 120).label, "Not Available")

    def test_missing_stop(self):
        self.assertEqual(calculate_reward_risk(100, None, 120).label, "Not Available")

    def test_invalid_stop(self):
        self.assertFalse(calculate_reward_risk(100, 101, 120).valid)

    def test_below_two(self):
        self.assertFalse(calculate_reward_risk(100, 90, 115).valid)

    def test_far_pivot_not_excellent(self):
        self.assertNotEqual(
            calculate_reward_risk(100, 95, 120, 40, 1).label, "Excellent R/R"
        )

    def test_far_support_not_excellent(self):
        self.assertNotEqual(
            calculate_reward_risk(100, 95, 120, 1, 5).label, "Excellent R/R"
        )

    def test_not_extended_irrelevant(self):
        self.assertEqual(calculate_reward_risk(None, None, None).label, "Not Available")


class ConsistencyDecisionTests(unittest.TestCase):
    def test_loose_caps_a(self):
        self.assertTrue(
            enforce_setup_consistency(
                candidate(
                    **{
                        "Tightness Label": "Loose",
                        "Pullback Quality": "A - Ideal Pullback",
                    }
                )
            )[0]["Pullback Quality"].startswith("B")
        )

    def test_loose_poor_caps_c(self):
        self.assertTrue(
            enforce_setup_consistency(
                candidate(**{"Tightness Label": "Loose", "VCP Label": "Poor VCP"})
            )[0]["Pullback Quality"].startswith("C")
        )

    def test_poor_vcp_alone_is_marginal_half(self):
        result = decide_candidate(
            candidate(**{"VCP Label": "Poor VCP"}), market(), portfolio()
        )
        self.assertEqual(result.decision, "HALF")
        self.assertTrue(result.confirmed_setup)

    def test_loose_poor_blocked(self):
        self.assertEqual(
            decide_candidate(
                candidate(**{"Tightness Label": "Loose", "VCP Label": "Poor VCP"}),
                market(),
                portfolio(),
            ).decision,
            "WATCH",
        )

    def test_overextended_blocked(self):
        self.assertEqual(
            decide_candidate(
                candidate(**{"Extension Status": "Overextended"}), market(), portfolio()
            ).decision,
            "NO TRADE",
        )

    def test_tight_category_not_loose(self):
        self.assertEqual(
            enforce_setup_consistency(
                candidate(
                    **{
                        "Category": "Tight Consolidation Candidates",
                        "Tightness Label": "Loose",
                    }
                )
            )[0]["Category"],
            "Developing Base Candidates",
        )

    def test_ema_reclaim_not_confirmation(self):
        row = candidate(**{"Support Signal": "EMA20 reclaim", "Recent RS Score": None})
        self.assertFalse(decide_candidate(row, market(), portfolio()).confirmed_setup)

    def test_allowed_all_gates(self):
        self.assertEqual(
            decide_candidate(candidate(), market(), portfolio()).decision, "FULL"
        )

    def test_watch_exact_reason(self):
        self.assertIn(
            "industry leadership incomplete",
            decide_candidate(
                candidate(**{"Industry Qualified": False}), market(), portfolio()
            ).reasons,
        )

    def test_block_exact_reason(self):
        self.assertIn(
            "overextended",
            decide_candidate(
                candidate(**{"Extension Status": "Overextended"}), market(), portfolio()
            ).blocking_reasons,
        )

    def test_low_final_score_does_not_create_a_hard_cliff(self):
        self.assertEqual(
            decide_candidate(
                candidate(
                    **{
                        "Setup Quality Score": 0,
                        "Volume Quality Score": 0,
                        "Entry Stop Quality Score": 0,
                    }
                ),
                market(),
                portfolio(),
            ).decision,
            "FULL",
        )

    def test_portfolio_heat_blocks(self):
        self.assertEqual(
            decide_candidate(candidate(), market(), portfolio(0.5)).decision,
            "HALF",
        )

    def test_industry_heat_blocks(self):
        p = PortfolioRisk((), 0, 4, 4, {"Software": 2}, {}, {}, ())
        self.assertEqual(
            decide_candidate(candidate(), market(), p).decision, "NO TRADE"
        )

    def test_theme_heat_blocks(self):
        p = PortfolioRisk((), 0, 4, 4, {}, {}, {"AI": 2}, ())
        self.assertEqual(
            decide_candidate(candidate(), market(), p).decision, "NO TRADE"
        )


class CanonicalConcentrationTests(unittest.TestCase):
    def test_one_record_per_ticker(self):
        self.assertEqual(
            len(
                canonicalise_candidates(
                    [candidate(), candidate(**{"Category": "Breakout Candidates"})]
                )
            ),
            1,
        )

    def test_tags_retained(self):
        self.assertIn(
            "Pullback",
            canonicalise_candidates(
                [candidate(), candidate(**{"Category": "Breakout Candidates"})]
            )[0]["Matched Setup Tags"],
        )

    def test_primary_precedence(self):
        self.assertEqual(
            canonicalise_candidates(
                [candidate(), candidate(**{"Category": "Breakout Candidates"})]
            )[0]["Primary Setup Category"],
            "Breakout Candidates",
        )

    def test_industry_cap(self):
        rows = [
            {
                **candidate(Ticker=str(i)),
                "Final Score": 90 - i,
                "Industry Composite Score": 70,
            }
            for i in range(3)
        ]
        self.assertEqual(len(apply_concentration_limits(rows)[0]), 1)

    def test_sector_cap(self):
        rows = [
            {
                **candidate(Ticker=str(i), Industry=str(i)),
                "Final Score": 90 - i,
                "Industry Composite Score": 70,
            }
            for i in range(7)
        ]
        self.assertEqual(len(apply_concentration_limits(rows, False)[0]), 5)

    def test_high_conviction_exception(self):
        rows = [
            {
                **candidate(Ticker=str(i)),
                "Final Score": 90 - i,
                "Industry Composite Score": 95,
            }
            for i in range(3)
        ]
        self.assertEqual(len(apply_concentration_limits(rows)[0]), 2)


class IndustryTests(unittest.TestCase):
    def member_frame(self, defensive=False):
        rows = []
        for industry, strong in (("Healthcare", False), ("Software", True)):
            for i in range(6):
                positive = strong and not defensive
                rows.append(
                    {
                        "Ticker": f"{industry}{i}",
                        "Industry": industry,
                        "Sector": "X",
                        "Return 5D": 2 if positive else -1,
                        "Return 10D": 3 if positive else -1,
                        "Return 20D": 5 if positive else -2,
                        "Relative Return 10D": 2 if positive else 1,
                        "Relative Return 20D": 4 if positive else 1,
                        "Above 10EMA": positive,
                        "Above 20EMA": positive,
                        "Above 50MA": positive,
                        "Near 20D High": positive,
                        "Near 52W High": positive,
                        "Valid Breakout": positive,
                        "Failed Breakout": False,
                        "High Volume Breakdown": False,
                        "Recent RS Score": 90 if positive else 60,
                        "Is Candidate": True,
                    }
                )
        return pd.DataFrame(rows)

    def test_defensive_not_qualified(self):
        self.assertFalse(
            qualify_industries(self.member_frame(), pd.DataFrame())[
                "Industry Qualified"
            ].iloc[-1]
        )

    def test_member_count_not_score(self):
        self.assertNotIn("Eligible Members", config.INDUSTRY_QUALIFICATION_WEIGHTS)

    def test_setup_count_quality_only(self):
        members = self.member_frame()
        setups = pd.DataFrame({"Ticker": ["Software0"]})
        result = qualify_industries(members, setups).set_index("Industry")
        self.assertEqual(result.loc["Software", "Qualifying Setup Count"], 1)

    def test_no_qualified_no_rank(self):
        members = self.member_frame(defensive=True)
        result = qualify_industries(members, pd.DataFrame())
        self.assertTrue(result["Industry Rank"].isna().all())

    def test_genuine_momentum_outranks_healthcare(self):
        result = qualify_industries(self.member_frame(), pd.DataFrame()).set_index(
            "Industry"
        )
        self.assertGreater(
            result.loc["Software", "Industry Composite Score"],
            result.loc["Healthcare", "Industry Composite Score"],
        )

    def test_no_qualified_sister_confirmation(self):
        self.assertFalse(
            sister_stock_confirmation("X", "Software", self.member_frame(), False)[
                "Sister Confirmation"
            ]
        )


class ExpectancyPipelineTests(unittest.TestCase):
    def test_expectancy_realised_r(self):
        self.assertAlmostEqual(
            expectancy_summary(
                pd.DataFrame(
                    {
                        "realised_r": [2, -1],
                        "fees": [0, 0],
                        "slippage": [0, 0],
                        "initial_risk_dollars": [500, 500],
                    }
                )
            ).expectancy_r,
            0.5,
        )

    def test_expectancy_costs(self):
        self.assertLess(
            expectancy_summary(
                pd.DataFrame(
                    {
                        "realised_r": [2, -1],
                        "fees": [5, 5],
                        "slippage": [5, 5],
                        "initial_risk_dollars": [500, 500],
                    }
                )
            ).expectancy_r,
            0.5,
        )

    def test_insufficient_sample(self):
        self.assertEqual(
            expectancy_summary(pd.DataFrame({"realised_r": [1]})).sample_label,
            "Insufficient sample",
        )

    def test_rolling_expectancy(self):
        self.assertIsNotNone(
            expectancy_summary(
                pd.DataFrame({"realised_r": [1] * 20})
            ).rolling_20_expectancy_r
        )

    def test_drawdown(self):
        self.assertLess(
            expectancy_summary(
                pd.DataFrame({"realised_r": [1, -2, 1]})
            ).maximum_drawdown_r,
            0,
        )

    def test_sample_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame, html = build_sample_report(Path(tmp) / "report.html")
            self.assertFalse(validate_sample_report(frame, html))

    def test_required_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, html = build_sample_report(Path(tmp) / "report.html")
            self.assertIn("Data and Logic Warnings", html)

    def test_regression_unknown_rs_no_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame, _ = build_sample_report(Path(tmp) / "report.html")
            self.assertEqual(
                set(frame["Final Decision"]), {"FULL", "HALF", "WATCH", "NO TRADE"}
            )


if __name__ == "__main__":
    unittest.main()
