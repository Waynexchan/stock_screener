"""Forward labels calculated only after point-in-time features are frozen."""

from __future__ import annotations

import pandas as pd

from .data import valid_bar_mask
from .models import FeatureRecord, OutcomeRecord

HORIZONS = (5, 10, 20, 40)


def next_available_session(
    history: pd.DataFrame, signal_date: pd.Timestamp | str
) -> pd.Timestamp | None:
    dates = pd.DatetimeIndex(pd.to_datetime(history.index)).sort_values()
    future = dates[dates > pd.Timestamp(signal_date)]
    return pd.Timestamp(future[0]) if len(future) else None


def calculate_forward_outcomes(
    feature: FeatureRecord, history: pd.DataFrame
) -> OutcomeRecord:
    """Calculate next-session-based labels; never return them in a feature record."""

    frame = history.copy()
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()
    future = frame.loc[frame.index > pd.Timestamp(feature.signal_date)]
    entry_date = pd.Timestamp(future.index[0]) if not future.empty else None
    entry = float(future.iloc[0]["Open"]) if entry_date is not None else None
    values: dict[str, float | None] = {}
    for horizon in HORIZONS:
        window = future.head(horizon)
        complete = bool(
            entry is not None
            and entry > 0
            and len(window) == horizon
            and valid_bar_mask(window).all()
        )
        values[f"future_{horizon}d_return"] = (
            float(window.iloc[-1]["Close"] / entry - 1) if complete else None
        )
        values[f"future_{horizon}d_mfe"] = (
            float(window["High"].max() / entry - 1) if complete else None
        )
        values[f"future_{horizon}d_mae"] = (
            float(window["Low"].min() / entry - 1) if complete else None
        )
    return OutcomeRecord(
        signal_date=feature.signal_date,
        ticker=feature.ticker,
        entry_date=entry_date.date().isoformat() if entry_date is not None else None,
        **values,
    )


def build_outcome_frame(
    features: pd.DataFrame, histories: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for item in features[features["model_0_signal"]].to_dict("records"):
        feature = FeatureRecord(**item)
        history = histories.get(feature.ticker)
        if history is None:
            continue
        records.append(calculate_forward_outcomes(feature, history).to_dict())
    return pd.DataFrame(records).reindex(
        columns=list(OutcomeRecord.__dataclass_fields__)
    )
