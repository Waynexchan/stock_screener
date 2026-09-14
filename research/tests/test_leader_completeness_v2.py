from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.run_leader_completeness_v2 import (
    candidate_priorities,
    candidate_risks,
)


def test_preregistered_complete_variant_matrix_is_fixed() -> None:
    root = Path(__file__).resolve().parents[2]
    experiment = json.loads(
        (root / "research/experiments/leader_completeness_v2.json").read_text(
            encoding="utf-8"
        )
    )
    variants = experiment["variants"]
    ids = [item["id"] for item in variants]
    assert len(ids) == experiment["variant_count"] == 24
    assert len(ids) == len(set(ids))
    assert ids[:6] == [
        "baseline",
        "ms_proxy_1_69",
        "ms_proxy_70_79",
        "ms_proxy_80_89",
        "ms_proxy_90_94",
        "ms_proxy_95_99",
    ]
    assert ids[-1] == "delayed_breakout_followthrough"


def test_industry_priority_is_descending_and_missing_is_last() -> None:
    frame = pd.DataFrame(
        [
            {
                "signal_date": "2026-01-02",
                "ticker": "AAA",
                "industry_proxy_score": 90,
                "stock_within_industry_score": 80,
                "marketsmith_proxy_score": 95,
            },
            {
                "signal_date": "2026-01-02",
                "ticker": "BBB",
                "industry_proxy_score": np.nan,
                "stock_within_industry_score": np.nan,
                "marketsmith_proxy_score": 99,
            },
        ]
    )
    priorities = candidate_priorities(frame, "INDUSTRY_THEN_STOCK")
    assert priorities is not None
    assert priorities[("2026-01-02", "AAA")] == (-90.0, -80.0, -95.0)
    assert priorities[("2026-01-02", "BBB")][0] == float("inf")


def test_secondary_industry_risk_uses_half_r_when_not_strong_or_missing() -> None:
    frame = pd.DataFrame(
        [
            {
                "signal_date": "2026-01-02",
                "ticker": "AAA",
                "industry_proxy_score": 80,
            },
            {
                "signal_date": "2026-01-02",
                "ticker": "BBB",
                "industry_proxy_score": 79,
            },
            {
                "signal_date": "2026-01-02",
                "ticker": "CCC",
                "industry_proxy_score": np.nan,
            },
        ]
    )
    risks = candidate_risks(frame, "INDUSTRY_SECONDARY_HALF")
    assert risks == {
        ("2026-01-02", "AAA"): 1.0,
        ("2026-01-02", "BBB"): 0.5,
        ("2026-01-02", "CCC"): 0.5,
    }
