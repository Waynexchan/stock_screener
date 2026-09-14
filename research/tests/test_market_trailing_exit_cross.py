from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from research.engine.market_gates import market_limits_for_signal_dates
from research.run_market_trailing_exit_cross import meets_stage_gate, trailing_policy


def benchmark() -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-02", periods=252)
    closes = (
        [80.0] * 200 + [float(value) for value in range(100, 149)] + [100.0, 50.0, 50.0]
    )
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [value + 1 for value in closes],
            "Low": [value - 1 for value in closes],
            "Close": closes,
            "Volume": 1_000_000.0,
        },
        index=dates,
    )


def experiment() -> dict:
    path = (
        Path(__file__).parents[1] / "experiments" / "market_trailing_exit_cross_v1.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_preregistered_market_trailing_matrix_has_28_unique_cells() -> None:
    config = experiment()
    cells = {
        (market["id"], trailing["id"])
        for market in config["market_gate_variants"]
        for trailing in config["trailing_exit_variants"]
    }
    assert len(cells) == config["combination_count"] == 28
    assert {item["activation_r"] for item in config["trailing_exit_variants"]} == {
        None,
        2.0,
        3.0,
    }


def test_three_state_spy_gate_has_normal_reduced_and_blocked_heat() -> None:
    frame = benchmark()
    dates = [frame.index[position].date().isoformat() for position in (248, 249, 250)]
    policy = next(
        item
        for item in experiment()["market_gate_variants"]
        if item["id"] == "spy_three_state_heat"
    )
    limits, states = market_limits_for_signal_dates(frame, dates, policy)
    assert [states[date] for date in dates] == ["NORMAL", "REDUCED", "BLOCKED"]
    assert [limits[date] for date in dates] == [2.0, 1.0, 0.0]


def test_trailing_policy_uses_frozen_twenty_session_indicators() -> None:
    config = experiment()
    specification = next(
        item
        for item in config["trailing_exit_variants"]
        if item["id"] == "activate_3r_sma20_minus_0_5atr20"
    )
    policy = trailing_policy(specification)
    assert policy is not None
    assert policy.activation_r == 3.0
    assert policy.moving_average_sessions == 20
    assert policy.atr_sessions == 20
    assert policy.atr_offset == 0.5


def test_stage_gate_rejects_drawdown_over_ten_percent() -> None:
    metrics = {
        "maximum_drawdown_pct": 10.01,
        "total_return_pct": 20.0,
        "expectancy_per_trade_r": 0.2,
        "profit_factor": 1.5,
        "accepted_trade_count": 120,
        "missing_mark_count": 0,
        "early_period_return_pct": 5.0,
        "late_period_return_pct": 5.0,
    }
    assert not meets_stage_gate(
        metrics, experiment()["stage_gate"]["development"], development=True
    )
