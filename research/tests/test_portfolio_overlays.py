from __future__ import annotations

import pandas as pd
import pytest

from research.engine.models import SimulatedTrade
from research.engine.portfolio_overlays import policy_limits, simulate_portfolio_overlay


def trade(
    ticker: str,
    *,
    entry_date: str = "2026-01-05",
    exit_date: str = "2026-01-07",
    realised_r: float = 0.0,
) -> SimulatedTrade:
    return SimulatedTrade(
        signal_date="2026-01-02",
        ticker=ticker,
        entry_date=entry_date,
        exit_date=exit_date,
        entry=100.0,
        initial_stop=95.0,
        target=None,
        initial_risk_per_share=5.0,
        shares=100,
        exit=100.0 + realised_r * 5.0,
        gross_pnl=realised_r * 500.0,
        costs=0.0,
        net_pnl=realised_r * 500.0,
        realised_r=realised_r,
        MFE_R=max(0.0, realised_r),
        MAE_R=min(0.0, realised_r),
        holding_days=3,
        exit_reason="FIXTURE",
    )


def history(rows: list[tuple[str, float, float]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=["Date", "Open", "Close"]).set_index("Date")
    frame.index = pd.to_datetime(frame.index)
    frame["High"] = frame[["Open", "Close"]].max(axis=1)
    frame["Low"] = frame[["Open", "Close"]].min(axis=1)
    return frame[["Open", "High", "Low", "Close"]]


def fixed_policy(heat_r: float) -> dict[str, float | str]:
    return {"type": "FIXED", "maximum_heat_r": heat_r, "risk_per_trade_r": 1.0}


def test_earned_policy_unlocks_only_from_realised_profit_high_water() -> None:
    policy = {
        "type": "EARNED",
        "initial_heat_r": 2.0,
        "unlock_profit_r": [1.0, 2.0],
        "unlocked_heat_r": [3.0, 4.0],
        "risk_per_trade_r": 1.0,
    }
    assert policy_limits(
        policy, realised_profit_high_water_r=0.9, current_drawdown_r=0.0
    ) == (2.0, 1.0, "EARNED")
    assert policy_limits(
        policy, realised_profit_high_water_r=1.0, current_drawdown_r=0.0
    ) == (3.0, 1.0, "EARNED")
    assert policy_limits(
        policy, realised_profit_high_water_r=2.1, current_drawdown_r=99.0
    ) == (4.0, 1.0, "EARNED")


def test_last_exit_batch_policy_uses_explicit_dynamic_state() -> None:
    policy = {
        "type": "LAST_EXIT_BATCH",
        "initial_heat_r": 2.0,
        "profitable_heat_r": 3.0,
        "non_positive_heat_r": 2.0,
        "risk_per_trade_r": 1.0,
    }
    assert policy_limits(
        policy,
        realised_profit_high_water_r=99.0,
        current_drawdown_r=99.0,
        dynamic_heat_r=2.0,
    ) == (2.0, 1.0, "BASE_2")
    assert policy_limits(
        policy,
        realised_profit_high_water_r=0.0,
        current_drawdown_r=0.0,
        dynamic_heat_r=3.0,
    ) == (3.0, 1.0, "WIN_TO_3")


def test_drawdown_policy_reduces_and_then_stops_new_risk() -> None:
    policy = {
        "type": "DRAWDOWN",
        "normal_heat_r": 3.0,
        "reduced_at_r": 2.0,
        "reduced_heat_r": 1.5,
        "defensive_at_r": 4.0,
        "defensive_heat_r": 0.5,
        "stop_at_r": 6.0,
        "normal_risk_per_trade_r": 1.0,
        "reduced_risk_per_trade_r": 0.5,
    }
    assert policy_limits(
        policy, realised_profit_high_water_r=0.0, current_drawdown_r=1.9
    ) == (3.0, 1.0, "NORMAL")
    assert policy_limits(
        policy, realised_profit_high_water_r=0.0, current_drawdown_r=2.0
    ) == (1.5, 0.5, "REDUCED")
    assert policy_limits(
        policy, realised_profit_high_water_r=0.0, current_drawdown_r=4.0
    ) == (0.5, 0.5, "DEFENSIVE")
    assert policy_limits(
        policy, realised_profit_high_water_r=0.0, current_drawdown_r=6.0
    ) == (0.0, 0.0, "STOP_NEW_RISK")


def test_fixed_heat_rejects_excess_same_session_candidates() -> None:
    trades = [trade("AAA", realised_r=2.0), trade("BBB", realised_r=-1.0), trade("CCC")]
    prices = {
        ticker: history(
            [
                ("2026-01-05", 100.0, 100.0),
                ("2026-01-06", 100.0, 100.0),
                ("2026-01-07", 100.0, 100.0),
            ]
        )
        for ticker in ("AAA", "BBB", "CCC")
    }
    metrics, ledger, _ = simulate_portfolio_overlay(
        trades,
        prices,
        pd.bdate_range("2026-01-05", "2026-01-07"),
        fixed_policy(2.0),
    )
    assert ledger["ticker"].tolist() == ["AAA", "BBB"]
    assert metrics["accepted_trade_count"] == 2
    assert metrics["rejection_reasons"] == {"MAX_HEAT": 1}
    assert metrics["maximum_heat_r"] == 2.0
    assert metrics["maximum_positions"] == 2
    assert metrics["average_win_r"] == 2.0
    assert metrics["average_loss_r"] == -1.0
    assert metrics["payoff_ratio"] == 2.0


def test_last_exit_batch_win_expands_and_loss_contracts_next_session() -> None:
    policy = {
        "type": "LAST_EXIT_BATCH",
        "initial_heat_r": 2.0,
        "profitable_heat_r": 3.0,
        "non_positive_heat_r": 2.0,
        "risk_per_trade_r": 1.0,
    }
    trades = [
        trade("AAA", entry_date="2026-01-05", exit_date="2026-01-06", realised_r=1),
        trade("BBB", entry_date="2026-01-05", exit_date="2026-01-08", realised_r=0),
        trade("CCC", entry_date="2026-01-07", exit_date="2026-01-09", realised_r=-1),
        trade("DDD", entry_date="2026-01-07", exit_date="2026-01-09", realised_r=0),
        trade("EEE", entry_date="2026-01-09", exit_date="2026-01-09", realised_r=0),
    ]
    prices = {
        ticker: history(
            [
                (date, 100.0, 100.0)
                for date in pd.bdate_range("2026-01-05", "2026-01-09").strftime(
                    "%Y-%m-%d"
                )
            ]
        )
        for ticker in ("AAA", "BBB", "CCC", "DDD", "EEE")
    }
    metrics, ledger, curve = simulate_portfolio_overlay(
        trades,
        prices,
        pd.bdate_range("2026-01-05", "2026-01-09"),
        policy,
        maximum_positions=3,
    )
    assert ledger["ticker"].tolist() == ["AAA", "BBB", "CCC", "DDD"]
    assert metrics["maximum_positions"] == 3
    assert metrics["exposure_expansion_count"] == 1
    assert metrics["exposure_contraction_count"] == 1
    assert curve.set_index("date").loc["2026-01-07", "policy_heat_limit_r"] == 3.0
    assert curve.set_index("date").loc["2026-01-09", "policy_heat_limit_r"] == 2.0


def test_same_session_exit_does_not_release_capacity_for_entries() -> None:
    trades = [
        trade("AAA", exit_date="2026-01-05"),
        trade("BBB", exit_date="2026-01-05"),
    ]
    prices = {
        ticker: history([("2026-01-05", 100.0, 100.0)]) for ticker in ("AAA", "BBB")
    }
    metrics, ledger, _ = simulate_portfolio_overlay(
        trades,
        prices,
        pd.DatetimeIndex([pd.Timestamp("2026-01-05")]),
        fixed_policy(1.0),
    )
    assert ledger["ticker"].tolist() == ["AAA"]
    assert metrics["rejection_reasons"] == {"MAX_HEAT": 1}


def test_daily_drawdown_captures_opening_gap_even_if_close_recovers() -> None:
    prices = {
        "AAA": history(
            [
                ("2026-01-05", 100.0, 100.0),
                ("2026-01-06", 90.0, 100.0),
            ]
        )
    }
    metrics, _, curve = simulate_portfolio_overlay(
        [trade("AAA", exit_date="2026-01-06")],
        prices,
        pd.bdate_range("2026-01-05", "2026-01-06"),
        fixed_policy(1.0),
    )
    assert metrics["maximum_drawdown_r"] == pytest.approx(2.0)
    assert metrics["maximum_drawdown_pct"] == pytest.approx(2.0)
    assert curve.iloc[-1]["close_drawdown_pct"] == pytest.approx(0.0)


def test_missing_benchmark_sessions_fail_closed() -> None:
    with pytest.raises(ValueError, match="benchmark sessions"):
        simulate_portfolio_overlay(
            [trade("AAA")],
            {"AAA": history([("2026-01-05", 100.0, 100.0)])},
            pd.DatetimeIndex([pd.Timestamp("2025-01-02")]),
            fixed_policy(1.0),
        )
