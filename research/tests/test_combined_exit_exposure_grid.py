from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from research.run_combined_exit_exposure_grid import (
    discovery_period_returns,
    meets_shortlist_gate,
)


def test_preregistered_matrix_has_180_unique_cells() -> None:
    path = (
        Path(__file__).parents[1]
        / "experiments"
        / "combined_exit_exposure_grid_v1.json"
    )
    experiment = json.loads(path.read_text(encoding="utf-8"))
    cells = {
        (stop["id"], target, portfolio["id"])
        for stop in experiment["stop_variants"]
        for target in experiment["target_r_variants"]
        for portfolio in experiment["portfolio_variants"]
    }
    assert len(cells) == experiment["combination_count"] == 180
    assert experiment["discovery_signal_period"][1] == "2023-11-01"
    assert experiment["discovery_price_period"][1] == "2023-12-29"


def test_discovery_period_returns_use_split_mark_to_market_equity() -> None:
    curve = pd.DataFrame(
        {
            "date": ["2017-01-03", "2020-12-31", "2021-01-04", "2023-12-29"],
            "equity_r": [101.0, 120.0, 118.0, 132.0],
            "portfolio_pnl_r": [1.0, 20.0, 18.0, 32.0],
        }
    )
    early, late = discovery_period_returns(curve, "2020-12-31")
    assert early == pytest.approx(20.0)
    assert late == pytest.approx(10.0)


def test_shortlist_gate_requires_both_discovery_subperiods() -> None:
    gate = {
        "maximum_drawdown_pct_at_most": 10.0,
        "total_return_pct_above": 0.0,
        "expectancy_per_trade_r_above": 0.0,
        "profit_factor_at_least": 1.2,
        "accepted_trade_count_at_least": 150,
        "missing_mark_count": 0,
        "early_period_return_pct_above": 0.0,
        "late_period_return_pct_above": 0.0,
    }
    metrics = {
        "maximum_drawdown_pct": 9.0,
        "total_return_pct": 20.0,
        "expectancy_per_trade_r": 0.2,
        "profit_factor": 1.3,
        "accepted_trade_count": 150,
        "missing_mark_count": 0,
        "early_period_return_pct": 5.0,
        "late_period_return_pct": 4.0,
    }
    assert meets_shortlist_gate(metrics, gate)
    metrics["late_period_return_pct"] = 0.0
    assert not meets_shortlist_gate(metrics, gate)


def test_shortlist_gate_rejects_small_samples_and_missing_marks() -> None:
    gate = {
        "maximum_drawdown_pct_at_most": 10.0,
        "total_return_pct_above": 0.0,
        "expectancy_per_trade_r_above": 0.0,
        "profit_factor_at_least": 1.2,
        "accepted_trade_count_at_least": 150,
        "missing_mark_count": 0,
        "early_period_return_pct_above": 0.0,
        "late_period_return_pct_above": 0.0,
    }
    metrics = {
        "maximum_drawdown_pct": 5.0,
        "total_return_pct": 10.0,
        "expectancy_per_trade_r": 0.5,
        "profit_factor": 2.0,
        "accepted_trade_count": 149,
        "missing_mark_count": 0,
        "early_period_return_pct": 5.0,
        "late_period_return_pct": 4.0,
    }
    assert not meets_shortlist_gate(metrics, gate)
    metrics["accepted_trade_count"] = 150
    metrics["missing_mark_count"] = 1
    assert not meets_shortlist_gate(metrics, gate)
