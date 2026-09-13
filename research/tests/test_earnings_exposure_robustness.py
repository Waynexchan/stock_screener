from __future__ import annotations

from research.run_earnings_exposure_robustness import stage_gate


def test_stage_gate_uses_separate_development_and_post_sample_floors() -> None:
    gate = {
        "each_stage_maximum_drawdown_pct_at_most": 10,
        "each_stage_total_return_pct_above": 0,
        "each_stage_expectancy_per_trade_r_above": 0,
        "each_stage_profit_factor_at_least": 1.2,
        "development_accepted_trade_count_at_least": 100,
        "post_2023_accepted_trade_count_at_least": 20,
        "missing_mark_count": 0,
    }
    metrics = {
        "maximum_drawdown_pct": 9,
        "total_return_pct": 5,
        "expectancy_per_trade_r": 0.2,
        "profit_factor": 1.3,
        "accepted_trade_count": 20,
        "missing_mark_count": 0,
    }
    assert not stage_gate(metrics, gate, development=True)
    assert stage_gate(metrics, gate, development=False)
