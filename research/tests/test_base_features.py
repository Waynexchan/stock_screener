from __future__ import annotations

import numpy as np
import pandas as pd

from research.engine.base_features import (
    BASE_FEATURE_COLUMNS,
    delayed_followthrough_signals,
    enrich_base_features,
)


def _history(periods: int = 320) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=periods)
    close = 80 + np.linspace(0, 20, periods) + np.sin(np.arange(periods) / 8)
    return pd.DataFrame(
        {
            "Open": close - 0.2,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": np.full(periods, 1_000_000.0),
        },
        index=dates,
    )


def test_base_features_are_populated_and_ignore_appended_future_bar() -> None:
    history = _history()
    signal_date = history.index[-1].date().isoformat()
    signals = pd.DataFrame([{"signal_date": signal_date, "ticker": "AAA"}])
    before = enrich_base_features(signals, {"AAA": history}).iloc[0]
    future = pd.DataFrame(
        {
            "Open": [1.0],
            "High": [10_000.0],
            "Low": [0.01],
            "Close": [5_000.0],
            "Volume": [100_000_000.0],
        },
        index=[history.index[-1] + pd.offsets.BDay(1)],
    )
    after = enrich_base_features(signals, {"AAA": pd.concat([history, future])}).iloc[0]
    assert pd.notna(before["pivot_price_126d"])
    for column in BASE_FEATURE_COLUMNS:
        if pd.isna(before[column]):
            assert pd.isna(after[column])
        else:
            assert after[column] == before[column]


def test_delayed_followthrough_uses_first_qualifying_close_and_rebuilds_stop() -> None:
    history = _history(80)
    signal_position = 70
    signal_date = history.index[signal_position]
    history.loc[signal_date, ["Open", "High", "Low", "Close"]] = [99, 101, 98, 100]
    first = history.index[signal_position + 1]
    history.loc[first, ["Open", "High", "Low", "Close", "Volume"]] = [
        100,
        103,
        99,
        102,
        1_000_000,
    ]
    signals = pd.DataFrame(
        [
            {
                "signal_date": signal_date.date().isoformat(),
                "ticker": "AAA",
                "universe_version": "test",
                "data_as_of": signal_date.date().isoformat(),
                "price": 100.0,
                "volume": 1_000_000.0,
                "dollar_volume": 100_000_000.0,
                "average_volume_50d": 1_000_000.0,
                "valid_data": True,
                "tradable": True,
                "stage2_pass": True,
                "structural_stop": 90.0,
                "model_0_signal": True,
            }
        ]
    )
    confirmed = delayed_followthrough_signals(signals, {"AAA": history})
    assert len(confirmed) == 1
    row = confirmed.iloc[0]
    assert row["original_signal_date"] == signal_date.date().isoformat()
    assert row["signal_date"] == first.date().isoformat()
    assert row["confirmation_lag_sessions"] == 1
    expected_stop = (
        history["Low"].iloc[signal_position - 18 : signal_position + 2].min()
    )
    assert row["structural_stop"] == expected_stop
