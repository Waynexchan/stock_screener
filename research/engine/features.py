"""Causal MODEL_0 feature construction."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from run_screener import add_indicators

from .data import valid_bar_mask
from .models import FeatureRecord

MODEL_0_ID = "MODEL_0_BASELINE"
MODEL_0_EXCLUDED_ALPHA_FEATURES = (
    "Recent RS",
    "Industry Qualification",
    "Sister-Stock Confirmation",
    "VCP Quality",
    "Pullback Quality",
    "Complex Setup Scoring",
    "Candidate Final Score",
    "AI Commentary",
)
OUTCOME_PREFIX = "future_"


def assert_feature_columns_safe(columns: Iterable[str]) -> None:
    leaked = sorted(
        column for column in columns if str(column).lower().startswith(OUTCOME_PREFIX)
    )
    if leaked:
        raise ValueError(
            f"outcome columns are forbidden in feature generation: {', '.join(leaked)}"
        )


def history_as_of(history: pd.DataFrame, as_of: pd.Timestamp | str) -> pd.DataFrame:
    """Return a defensive copy containing no row after the signal date."""

    cutoff = pd.Timestamp(as_of)
    frame = history.copy()
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()
    sliced = frame.loc[frame.index <= cutoff].copy()
    if not sliced.empty and pd.Timestamp(sliced.index.max()) > cutoff:
        raise AssertionError("future bar entered the point-in-time feature slice")
    return sliced


def _valid_history_window(frame: pd.DataFrame, sessions: int) -> bool:
    window = frame.tail(sessions)
    return bool(len(window) == sessions and valid_bar_mask(window).all())


def feature_at_date(
    ticker: str,
    history: pd.DataFrame,
    signal_date: pd.Timestamp | str,
    universe_version: str,
    *,
    min_price: float = 10.0,
    min_average_volume: float = 500_000.0,
    minimum_history_sessions: int = 220,
    stop_lookback_sessions: int = 20,
) -> FeatureRecord:
    """Build one feature record using bars no later than ``signal_date``."""

    assert_feature_columns_safe(history.columns)
    frame = history_as_of(history, signal_date)
    empty = FeatureRecord(
        signal_date=pd.Timestamp(signal_date).date().isoformat(),
        ticker=ticker.upper(),
        universe_version=universe_version,
        data_as_of=(
            pd.Timestamp(frame.index.max()).date().isoformat()
            if not frame.empty
            else ""
        ),
        price=float("nan"),
        volume=float("nan"),
        dollar_volume=float("nan"),
        average_volume_50d=float("nan"),
        valid_data=False,
        tradable=False,
        stage2_pass=False,
        structural_stop=None,
    )
    if not _valid_history_window(frame, minimum_history_sessions):
        return empty
    indicators = add_indicators(frame)
    latest = indicators.iloc[-1]
    required = [
        "Close",
        "Volume",
        "AVG_VOLUME50",
        "MA50",
        "MA150",
        "MA200",
        "MA200_20D_AGO",
    ]
    if latest[required].isna().any():
        return empty
    price = float(latest["Close"])
    volume = float(latest["Volume"])
    average_volume = float(latest["AVG_VOLUME50"])
    valid_data = bool(
        np.isfinite(price) and np.isfinite(volume) and np.isfinite(average_volume)
    )
    tradable = bool(
        valid_data and price >= min_price and average_volume >= min_average_volume
    )
    stage2_pass = bool(
        valid_data
        and price > float(latest["MA50"])
        and float(latest["MA50"]) > float(latest["MA150"])
        and float(latest["MA150"]) > float(latest["MA200"])
        and float(latest["MA200"]) > float(latest["MA200_20D_AGO"])
    )
    stop_window = frame["Low"].dropna().tail(stop_lookback_sessions)
    structural_stop = (
        float(stop_window.min()) if len(stop_window) == stop_lookback_sessions else None
    )
    if structural_stop is not None and (
        not np.isfinite(structural_stop) or structural_stop >= price
    ):
        structural_stop = None
    return FeatureRecord(
        signal_date=pd.Timestamp(signal_date).date().isoformat(),
        ticker=ticker.upper(),
        universe_version=universe_version,
        data_as_of=pd.Timestamp(frame.index.max()).date().isoformat(),
        price=price,
        volume=volume,
        dollar_volume=price * volume,
        average_volume_50d=average_volume,
        valid_data=valid_data,
        tradable=tradable,
        stage2_pass=stage2_pass,
        structural_stop=structural_stop,
    )


def generate_model_0_features(
    histories: dict[str, pd.DataFrame],
    universe_version: str,
    *,
    min_price: float = 10.0,
    min_average_volume: float = 500_000.0,
    minimum_history_sessions: int = 220,
    stop_lookback_sessions: int = 20,
) -> pd.DataFrame:
    """Emit a signal only on a false-to-true MODEL_0 eligibility transition."""

    records: list[dict[str, object]] = []
    for ticker in sorted(histories):
        history = histories[ticker].sort_index()
        previous_eligible = False
        for date in history.index:
            feature = feature_at_date(
                ticker,
                history,
                date,
                universe_version,
                min_price=min_price,
                min_average_volume=min_average_volume,
                minimum_history_sessions=minimum_history_sessions,
                stop_lookback_sessions=stop_lookback_sessions,
            )
            eligible = bool(
                feature.valid_data
                and feature.tradable
                and feature.stage2_pass
                and feature.structural_stop is not None
            )
            record = feature.to_dict()
            record["model_0_signal"] = bool(eligible and not previous_eligible)
            records.append(record)
            previous_eligible = eligible
    columns = list(FeatureRecord.__dataclass_fields__)
    return pd.DataFrame(records).reindex(columns=columns)
