from __future__ import annotations

import json
from pathlib import Path

from research.run_easy_execution_cross_validation import (
    meets_discovery_gate,
    meets_validation_gate,
    supporting_neighbor_ids,
)


def test_preregistered_matrix_has_168_unique_cells() -> None:
    path = (
        Path(__file__).parents[1]
        / "experiments"
        / "easy_execution_cross_validation_v1.json"
    )
    experiment = json.loads(path.read_text(encoding="utf-8"))
    cells = {
        (stop["id"], exit_specification["id"], portfolio["id"])
        for stop in experiment["stop_variants"]
        for exit_specification in experiment["exit_variants"]
        for portfolio in experiment["portfolio_variants"]
    }
    assert len(cells) == experiment["combination_count"] == 168
    assert experiment["periods"]["validation_signal"][0] == "2024-03-01"
    assert experiment["periods"]["holdout_signal"][0] == "2025-01-02"


def passing_metrics() -> dict[str, float | int]:
    return {
        "maximum_drawdown_pct": 8.0,
        "total_return_pct": 10.0,
        "expectancy_per_trade_r": 0.2,
        "expectancy_per_allocated_r": 0.2,
        "profit_factor": 1.3,
        "accepted_trade_count": 100,
        "missing_mark_count": 0,
        "early_period_return_pct": 4.0,
        "late_period_return_pct": 5.0,
    }


def test_discovery_and_validation_gates_have_separate_sample_rules() -> None:
    discovery_gate = {
        "maximum_drawdown_pct_at_most": 10,
        "total_return_pct_above": 0,
        "expectancy_per_trade_r_above": 0,
        "profit_factor_at_least": 1.2,
        "accepted_trade_count_at_least": 100,
        "missing_mark_count": 0,
        "early_period_return_pct_above": 0,
        "late_period_return_pct_above": 0,
    }
    validation_gate = {
        "maximum_drawdown_pct_at_most": 10,
        "total_return_pct_above": 0,
        "expectancy_per_trade_r_above": 0,
        "profit_factor_at_least": 1.1,
        "accepted_trade_count_at_least": 8,
        "missing_mark_count": 0,
    }
    metrics = passing_metrics()
    assert meets_discovery_gate(metrics, discovery_gate)
    metrics["accepted_trade_count"] = 8
    assert not meets_discovery_gate(metrics, discovery_gate)
    assert meets_validation_gate(metrics, validation_gate)


def test_neighbor_support_requires_same_family_stop_exposure_and_adjacent_order() -> (
    None
):
    base = {
        **passing_metrics(),
        "cell_id": "base",
        "stop_id": "stop",
        "portfolio_id": "portfolio",
        "exit_family": "TARGET",
        "exit_order": 2,
    }
    adjacent = {
        **passing_metrics(),
        "cell_id": "adjacent",
        "stop_id": "stop",
        "portfolio_id": "portfolio",
        "exit_family": "TARGET",
        "exit_order": 3,
    }
    wrong_family = {**adjacent, "cell_id": "wrong", "exit_family": "TIME"}
    assert supporting_neighbor_ids(base, [base, adjacent, wrong_family]) == ["adjacent"]
