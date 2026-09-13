from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research.run_staircase_exposure_robustness import portfolio_variants


def experiment() -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "staircase_exposure_robustness_v2.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_preregistered_matrix_contains_baseline_and_six_staircase_variants() -> None:
    variants = portfolio_variants(experiment())
    assert len(variants) == 7
    assert len({variant["id"] for variant in variants}) == 7
    assert [variant["id"] for variant in variants] == [
        "fixed_2r_earnings_blackout",
        "staircase_cap_4r__step_down_1r",
        "staircase_cap_4r__reset_to_2r",
        "staircase_cap_6r__step_down_1r",
        "staircase_cap_6r__reset_to_2r",
        "staircase_cap_8r__step_down_1r",
        "staircase_cap_8r__reset_to_2r",
    ]


def test_all_staircase_variants_preserve_frozen_floor_and_one_r_steps() -> None:
    variants = portfolio_variants(experiment())[1:]
    assert {variant["floor_heat_r"] for variant in variants} == {2.0}
    assert {variant["profit_increment_r"] for variant in variants} == {1.0}
    assert {variant["loss_step_r"] for variant in variants} == {1.0}
    assert {variant["risk_per_trade_r"] for variant in variants} == {1.0}
    assert {variant["ceiling_heat_r"] for variant in variants} == {4.0, 6.0, 8.0}
    assert {variant["contraction_mode"] for variant in variants} == {"STEP", "RESET"}
