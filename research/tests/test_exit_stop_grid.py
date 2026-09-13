from __future__ import annotations

import pandas as pd
import pytest

from research.run_exit_stop_grid import stop_for_variant, true_range_atr20


def test_atr20_is_simple_mean_of_causal_true_range() -> None:
    dates = pd.bdate_range("2026-01-01", periods=21)
    frame = pd.DataFrame(
        {
            "High": [11.0] * 21,
            "Low": [9.0] * 21,
            "Close": [10.0] * 21,
        },
        index=dates,
    )
    atr = true_range_atr20(frame)
    assert atr.iloc[:19].isna().all()
    assert atr.iloc[19] == 2.0
    assert atr.iloc[20] == 2.0


@pytest.mark.parametrize(
    ("specification", "expected"),
    [
        ({"anchor": "signal_20d_low", "atr_multiple": 0}, 90.0),
        ({"anchor": "slipped_entry", "atr_multiple": 0.5}, 98.0),
        ({"anchor": "slipped_entry", "atr_multiple": 1.0}, 96.0),
        ({"anchor": "signal_day_low", "atr_multiple": 0.5}, 93.0),
        ({"anchor": "signal_day_low", "atr_multiple": 1.0}, 91.0),
        ({"anchor": "signal_10d_low", "atr_multiple": 0}, 92.0),
        (
            {
                "anchor": "higher_of_signal_20d_low_and_entry_minus_atr",
                "atr_multiple": 1.0,
            },
            96.0,
        ),
    ],
)
def test_stop_variants_use_frozen_anchors(
    specification: dict[str, object], expected: float
) -> None:
    row = {
        "structural_stop": 90.0,
        "slipped_next_open": 100.0,
        "signal_day_low": 95.0,
        "signal_10d_low": 92.0,
        "atr20": 4.0,
    }
    assert stop_for_variant(row, specification) == expected
