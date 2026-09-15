from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.run_filter_combination_audit_v1 import (
    _factorial_variant_id,
    _leave_one_out_support,
    cumulative_funnel,
    enrich_spy_signal_trend,
    generate_variants,
    marginal_pairs,
)


def _experiment() -> dict[str, object]:
    root = Path(__file__).resolve().parents[2]
    return json.loads(
        (root / "research/experiments/filter_combination_audit_v1.json").read_text(
            encoding="utf-8"
        )
    )


def test_preregistered_matrix_is_complete_and_unique() -> None:
    experiment = _experiment()
    variants = generate_variants(experiment)
    factorial = [item for item in variants if item["variant_family"] == "FACTORIAL"]
    assert len(variants) == experiment["variant_count"] == 80
    assert len(factorial) == experiment["factorial_subset_count"] == 64
    assert len({item["id"] for item in variants}) == 80
    assert {tuple(item["component_ids"]) for item in factorial} == {
        tuple(
            component["id"]
            for index, component in enumerate(experiment["factorial_components"])
            if mask & (1 << index)
        )
        for mask in range(64)
    }
    assert experiment["preregistration_commit"] == "3f8d0a6"


def test_spy_sma50_feature_does_not_change_when_future_bar_changes() -> None:
    dates = pd.bdate_range("2024-01-02", periods=80)
    spy = pd.DataFrame({"Close": np.linspace(100, 120, 80)}, index=dates)
    signal_date = dates[-2].date().isoformat()
    signals = pd.DataFrame({"signal_date": [signal_date], "ticker": ["AAA"]})
    before = enrich_spy_signal_trend(signals, spy).at[0, "spy_above_sma50"]
    changed = spy.copy()
    changed.iloc[-1, 0] = 1.0
    after = enrich_spy_signal_trend(signals, changed).at[0, "spy_above_sma50"]
    assert bool(before)
    assert before == after


def test_marginal_pairs_cover_all_contexts_and_stages() -> None:
    experiment = _experiment()
    variants = generate_variants(experiment)
    components = [item["id"] for item in experiment["factorial_components"]]
    stages = ["development", "reused_2024", "reused_2025"]
    rows = [
        {
            "stage": stage,
            "variant_id": variant["id"],
            **{
                metric: float(len(variant["component_ids"]))
                for metric in (
                    "total_return_pct",
                    "maximum_drawdown_pct",
                    "expectancy_per_trade_r",
                    "profit_factor",
                    "return_to_drawdown",
                    "selected_signal_count",
                    "accepted_trade_count",
                )
            },
        }
        for stage in stages
        for variant in variants
    ]
    pairs = marginal_pairs(rows, variants, components, stages)
    assert len(pairs) == 6 * 32 * 3
    assert all(item["total_return_pct_delta"] == 1.0 for item in pairs)


def test_leave_one_out_requires_every_component_in_two_periods() -> None:
    components = ["a", "b"]
    subsets = [(), ("a",), ("b",), ("a", "b")]
    ids = {subset: _factorial_variant_id(subset) for subset in subsets}
    stages = ["development", "reused_2024", "reused_2025"]
    rows_by_key = {}
    for stage_index, stage in enumerate(stages):
        for subset in subsets:
            score = float(len(subset))
            if subset == ("a", "b") and stage_index == 2:
                score = 0.0
            rows_by_key[(stage, ids[subset])] = {
                "total_return_pct": score,
                "return_to_drawdown": score,
            }
    supported, details = _leave_one_out_support(
        components,
        rows_by_key,
        stages,
        ids,
        required_return_periods=2,
        required_ratio_periods=2,
    )
    assert supported
    assert details["a"]["return_improvement_period_count"] == 2
    assert details["b"]["return_to_drawdown_improvement_period_count"] == 2

    rows_by_key[("reused_2024", ids[("a", "b")])]["total_return_pct"] = 0.0
    supported, _ = _leave_one_out_support(
        components,
        rows_by_key,
        stages,
        ids,
        required_return_periods=2,
        required_ratio_periods=2,
    )
    assert not supported


def test_cumulative_funnel_reconstructs_candidate_count_from_ledger_outcomes() -> None:
    diagnostics = {"development": {"pre_blackout_signal_count": 12}}
    rows = [
        {
            "stage": "development",
            "variant_id": "baseline",
            "selected_signal_count": 10,
            "accepted_trade_count": 2,
            "rejection_count": 7,
            "rejection_reasons": {"MAX_HEAT": 7},
        },
        {
            "stage": "development",
            "variant_id": "combo__a",
            "selected_signal_count": 5,
            "accepted_trade_count": 2,
            "rejection_count": 2,
            "rejection_reasons": {"MAX_HEAT": 2},
        },
    ]
    funnel = cumulative_funnel(rows, diagnostics, ["development"], ["a"])
    assert funnel[1]["candidate_trade_count"] == 9
    assert funnel[1]["capacity_acceptance_pct"] == 2 / 9 * 100
    assert funnel[2]["candidate_trade_count"] == 4
