from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from research.engine.models import SimulatedTrade
from research.run_filter_combination_audit_v1 import generate_variants
from research.run_filter_edge_sequenced_v1 import (
    classify_variant,
    known_industry_mask,
    monthly_block_delta_interval,
    select_nonoverlapping_ticker_episodes,
)


def _trade(
    ticker: str,
    signal: str,
    entry: str,
    exit_date: str,
    realised_r: float,
) -> SimulatedTrade:
    return SimulatedTrade(
        signal_date=signal,
        ticker=ticker,
        entry_date=entry,
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
        MFE_R=max(realised_r, 0.0),
        MAE_R=min(realised_r, 0.0),
        holding_days=3,
        exit_reason="FIXTURE",
    )


def _experiment() -> dict[str, object]:
    root = Path(__file__).resolve().parents[2]
    return json.loads(
        (root / "research/experiments/filter_edge_sequenced_v1.json").read_text(
            encoding="utf-8"
        )
    )


def test_preregistered_variant_source_remains_exactly_eighty() -> None:
    experiment = _experiment()
    root = Path(__file__).resolve().parents[2]
    source = json.loads(
        (root / str(experiment["variant_source"])).read_text(encoding="utf-8")
    )
    assert len(generate_variants(source)) == experiment["variant_count"] == 80
    assert experiment["preregistration_commit"] == "42ea515"


def test_known_industry_mask_rejects_null_empty_and_whitespace() -> None:
    frame = pd.DataFrame({"industry": ["Software", None, "", "  ", "Semiconductors"]})
    assert known_industry_mask(frame).tolist() == [True, False, False, False, True]


def test_ticker_episode_selection_rejects_entries_through_exit_session() -> None:
    trades = [
        _trade("AAA", "2025-01-01", "2025-01-02", "2025-01-10", 1.0),
        _trade("AAA", "2025-01-05", "2025-01-06", "2025-01-08", -1.0),
        _trade("AAA", "2025-01-09", "2025-01-10", "2025-01-12", 2.0),
        _trade("AAA", "2025-01-10", "2025-01-13", "2025-01-15", 3.0),
        _trade("BBB", "2025-01-05", "2025-01-06", "2025-01-08", 0.5),
    ]
    selected, rejected = select_nonoverlapping_ticker_episodes(trades)
    assert [(trade.ticker, trade.signal_date) for trade in selected] == [
        ("AAA", "2025-01-01"),
        ("AAA", "2025-01-10"),
        ("BBB", "2025-01-05"),
    ]
    assert rejected == 2


def test_month_block_interval_is_deterministic_and_detects_uplift() -> None:
    baseline = [
        _trade("AAA", "2025-01-01", "2025-01-02", "2025-01-03", 0.0),
        _trade("BBB", "2025-02-01", "2025-02-03", "2025-02-04", 0.0),
        _trade("CCC", "2025-03-01", "2025-03-03", "2025-03-04", 0.0),
    ]
    variant = [
        _trade("AAA", "2025-01-01", "2025-01-02", "2025-01-03", 1.0),
        _trade("BBB", "2025-02-01", "2025-02-03", "2025-02-04", 1.0),
        _trade("CCC", "2025-03-01", "2025-03-03", "2025-03-04", 1.0),
    ]
    first = monthly_block_delta_interval(
        baseline, variant, samples=500, confidence=0.95, seed=7
    )
    second = monthly_block_delta_interval(
        baseline, variant, samples=500, confidence=0.95, seed=7
    )
    assert first == second
    assert first == pytest.approx((1.0, 1.0))


def test_classification_respects_sample_floor_before_positive_metrics() -> None:
    gate = _experiment()["classification_gates"]
    rows = [
        {
            "stage": stage,
            "episode_count": 49,
            "expectancy_r": 1.0,
            "expectancy_r_delta_vs_baseline": 0.5,
            "profit_factor_delta_vs_baseline": 1.0,
            "average_mfe_r_delta_vs_baseline": 1.0,
            "average_mae_r_delta_vs_baseline": 1.0,
            "episode_retention_vs_baseline_pct": 50.0,
            "expectancy_delta_month_block_95_low_r": 0.1,
        }
        for stage in ("development_2017_2023", "reused_2024", "reused_2025")
    ]
    label, diagnostics = classify_variant("candidate", rows, gate)
    assert label == "INCONCLUSIVE_SPARSE"
    assert not diagnostics["sample_floor_pass"]
