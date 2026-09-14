from __future__ import annotations

import numpy as np
import pandas as pd

from research.engine.leader_features import enrich_leader_features
from research.run_leader_rs_robustness import (
    cross_stage_summary,
    resolved_variant_rules,
    rule_mask,
    variant_mask,
)


def _histories() -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    dates = pd.bdate_range("2024-01-02", periods=300)
    histories: dict[str, pd.DataFrame] = {}
    for index, ticker in enumerate(("AAA", "AAB", "AAC", "BBA", "BBB", "BBC")):
        growth = 1.0005 + index * 0.0004
        close = 20 * growth ** np.arange(len(dates))
        histories[ticker] = pd.DataFrame(
            {"Close": close, "Volume": np.full(len(dates), 1_000_000.0)},
            index=dates,
        )
    spy = pd.DataFrame({"Close": 100 * 1.0003 ** np.arange(len(dates))}, index=dates)
    return histories, spy


def test_leader_features_rank_full_archive_before_signal_filter() -> None:
    histories, spy = _histories()
    date = histories["AAA"].index[-1].date().isoformat()
    signals = pd.DataFrame(
        [
            {"signal_date": date, "ticker": "AAA"},
            {"signal_date": date, "ticker": "BBC"},
        ]
    )
    result = enrich_leader_features(
        signals,
        histories,
        spy,
        sectors={"AAA": "Utilities", "BBC": "Technology"},
        industries={
            "AAA": "A",
            "AAB": "A",
            "AAC": "A",
            "BBA": "B",
            "BBB": "B",
            "BBC": "B",
        },
        minimum_industry_members=3,
    ).set_index("ticker")
    assert result.at["BBC", "marketsmith_proxy_score"] == 99
    assert result.at["AAA", "marketsmith_proxy_score"] < 99
    assert (
        result.at["BBC", "industry_proxy_score"]
        > result.at["AAA", "industry_proxy_score"]
    )
    assert bool(result.at["AAA", "is_utility"])


def test_rule_masks_fail_closed_and_variant_inherits_profile() -> None:
    frame = pd.DataFrame(
        {
            "score": [90.0, np.nan, 75.0],
            "flag": [True, False, True],
            "utility": [False, False, True],
        }
    )
    assert rule_mask(
        frame, {"column": "score", "operator": ">=", "value": 85}
    ).tolist() == [True, False, False]
    variants = [
        {
            "id": "profile",
            "rules": [{"column": "score", "operator": ">=", "value": 85}],
        },
        {
            "id": "profile_no_utility",
            "base_variant": "profile",
            "rules": [{"column": "utility", "operator": "is_false"}],
        },
    ]
    assert len(resolved_variant_rules(variants, variants[1])) == 2
    assert variant_mask(frame, variants, variants[1]).tolist() == [True, False, False]


def test_cross_stage_shortlist_requires_every_frozen_condition() -> None:
    experiment = {
        "variants": [{"id": "baseline"}, {"id": "candidate"}],
        "cross_stage_shortlist": {
            "largest_winner_positive_pnl_contribution_at_most": 0.5,
            "total_return_beats_baseline_in_at_least_periods": 2,
            "return_to_drawdown_beats_baseline_in_at_least_periods": 2,
        },
    }
    rows = []
    for stage in ("development", "reused_2024", "reused_2025"):
        for variant, delta in (("baseline", 0.0), ("candidate", 1.0)):
            rows.append(
                {
                    "stage": stage,
                    "variant_id": variant,
                    "passes_stage_gate": True,
                    "total_return_pct_delta_vs_baseline": delta,
                    "return_to_drawdown_delta_vs_baseline": delta,
                    "largest_winner_share_of_positive_pnl": 0.4,
                }
            )
    summary = cross_stage_summary(
        rows, ["development", "reused_2024", "reused_2025"], experiment
    )
    candidate = next(row for row in summary if row["variant_id"] == "candidate")
    assert candidate["cross_stage_shortlist"] is True
