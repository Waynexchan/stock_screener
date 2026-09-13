from __future__ import annotations

import pandas as pd
import pytest

from research.engine.forward_execution import simulate_frozen_plan


def history(rows: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [row[1] for row in rows],
            "High": [row[2] for row in rows],
            "Low": [row[3] for row in rows],
            "Close": [row[4] for row in rows],
            "Volume": 1_000_000,
        },
        index=pd.to_datetime([row[0] for row in rows]),
    )


def plan(**updates: object) -> dict[str, object]:
    row: dict[str, object] = {
        "signal_date": "2026-01-02",
        "ticker": "AAA",
        "Planned Entry": 100.0,
        "Initial Stop": 95.0,
        "Realistic Target": 110.0,
        "Realistic Target Source": "prior high resistance",
    }
    row.update(updates)
    return row


def test_plan_that_never_touches_entry_is_not_triggered() -> None:
    bars = history([(f"2026-01-{day:02d}", 98, 99, 97, 98) for day in range(5, 10)])
    result = simulate_frozen_plan(plan(), bars, entry_slippage_bps=0)
    assert result["plan_outcome_status"] == "NOT_TRIGGERED"
    assert not result["plan_triggered"]


def test_gap_entry_uses_open_and_stop_gap_uses_later_open() -> None:
    bars = history(
        [
            ("2026-01-05", 102, 104, 100, 103),
            ("2026-01-06", 94, 96, 93, 95),
        ]
    )
    result = simulate_frozen_plan(
        plan(), bars, entry_slippage_bps=0, exit_slippage_bps=0
    )
    assert result["plan_entry"] == 102.0
    assert result["plan_exit"] == 94.0
    assert result["plan_outcome_status"] == "STOP_GAP"
    assert result["plan_realised_r"] == pytest.approx(-8 / 7)


def test_entry_bar_stop_and_target_is_stop_first() -> None:
    bars = history([("2026-01-05", 99, 111, 94, 105)])
    result = simulate_frozen_plan(
        plan(), bars, entry_slippage_bps=0, exit_slippage_bps=0
    )
    assert result["plan_outcome_status"] == "STOP_AND_TARGET_SAME_BAR"
    assert result["plan_realised_r"] == -1.0


def test_open_plan_before_40_sessions_has_no_realised_r() -> None:
    bars = history([(f"2026-01-{day:02d}", 100, 105, 96, 102) for day in range(5, 15)])
    result = simulate_frozen_plan(plan(**{"Realistic Target": None}), bars)
    assert result["plan_outcome_status"] == "OPEN_UNMATURED"
    assert result["plan_realised_r"] is None


def test_model_target_is_not_used_as_observed_exit() -> None:
    bars = history([("2026-01-05", 100, 120, 96, 115)])
    result = simulate_frozen_plan(
        plan(**{"Realistic Target Source": "model 2R feasibility target"}), bars
    )
    assert result["plan_outcome_status"] == "OPEN_UNMATURED"
