"""Causal base, pivot, supply, and delayed follow-through research features."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


BASE_FEATURE_COLUMNS = (
    "pivot_price_126d",
    "base_duration_sessions",
    "base_depth_pct",
    "distance_from_pivot_pct",
    "contraction_count_3x20d",
    "contraction_ratio_60d",
    "volume_dryup_ratio_10v40",
    "pivot_supply_days_10d",
    "shakeout_reclaim_10d",
    "breakout_quality",
    "base_stage_proxy",
    "complete_base_quality",
)


def _numeric_history(history: pd.DataFrame) -> pd.DataFrame:
    frame = history.copy().sort_index()
    frame.index = pd.to_datetime(frame.index)
    for column in ("Open", "High", "Low", "Close", "Volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _range_pct(
    highs: pd.Series, lows: pd.Series, closes: pd.Series, sessions: int
) -> pd.Series:
    mean_close = closes.rolling(sessions, min_periods=sessions).mean()
    return (
        (
            highs.rolling(sessions, min_periods=sessions).max()
            - lows.rolling(sessions, min_periods=sessions).min()
        )
        .div(mean_close)
        .mul(100)
    )


def base_feature_frame(history: pd.DataFrame) -> pd.DataFrame:
    """Calculate fixed base proxies using bars through each row only."""

    frame = _numeric_history(history)
    high = frame["High"]
    low = frame["Low"]
    close = frame["Close"]
    volume = frame["Volume"]
    average_volume_50 = volume.rolling(50, min_periods=50).mean()
    pivot = high.shift(1).rolling(126, min_periods=126).max()

    range_20 = _range_pct(high, low, close, 20)
    old_range = range_20.shift(40)
    middle_range = range_20.shift(20)
    recent_range = range_20
    complete_ranges = old_range.notna() & middle_range.notna() & recent_range.notna()
    contraction_count = (
        middle_range.lt(old_range).astype(int)
        + recent_range.lt(middle_range).astype(int)
    ).where(complete_ranges)
    contraction_ratio = recent_range.div(old_range).where(complete_ranges)

    recent_volume = volume.rolling(10, min_periods=10).mean()
    prior_volume = volume.shift(10).rolling(40, min_periods=40).mean()
    volume_dryup = recent_volume.div(prior_volume.where(prior_volume.gt(0)))

    prior_20d_low = low.shift(1).rolling(20, min_periods=20).min()
    shakeout_event = low.lt(prior_20d_low) & close.gt(prior_20d_low)
    shakeout_recent = (
        shakeout_event.rolling(10, min_periods=10).max().fillna(False).astype(bool)
    )

    prior_63d_high = high.shift(1).rolling(63, min_periods=63).max()
    volume_ratio = volume.div(average_volume_50.where(average_volume_50.gt(0)))
    prior_breakout = close.gt(prior_63d_high) & volume_ratio.ge(1.2)
    distinct_breakout = prior_breakout & ~prior_breakout.shift(1, fill_value=False)
    prior_breakout_count = (
        distinct_breakout.shift(1, fill_value=False)
        .astype(int)
        .rolling(252, min_periods=252)
        .sum()
    )
    base_stage = 1 + prior_breakout_count

    daily_range = (high - low).where(high.gt(low))
    close_location = close.sub(low).div(daily_range).mul(100)
    breakout_quality = close.gt(pivot) & volume_ratio.ge(1.5) & close_location.ge(75)

    return pd.DataFrame(
        {
            "pivot_price_126d": pivot,
            "contraction_count_3x20d": contraction_count,
            "contraction_ratio_60d": contraction_ratio,
            "volume_dryup_ratio_10v40": volume_dryup,
            "shakeout_reclaim_10d": shakeout_recent,
            "breakout_quality": breakout_quality,
            "base_stage_proxy": base_stage,
            "average_volume_50d_base": average_volume_50,
            "volume_ratio_base": volume_ratio,
            "close_location_pct_base": close_location,
        },
        index=frame.index,
    )


def _point_base_features(
    frame: pd.DataFrame, calculated: pd.DataFrame, date: pd.Timestamp
) -> dict[str, Any]:
    if date not in calculated.index:
        return {}
    position = calculated.index.get_loc(date)
    if not isinstance(position, (int, np.integer)):
        return {}
    pivot = pd.to_numeric(calculated.at[date, "pivot_price_126d"], errors="coerce")
    if pd.isna(pivot) or position < 1:
        return {}
    prior_start = max(0, int(position) - 126)
    prior_highs = frame["High"].iloc[prior_start : int(position)]
    matches = np.flatnonzero(
        np.isclose(prior_highs.to_numpy(dtype=float), float(pivot))
    )
    if len(matches) == 0:
        return {}
    base_start = prior_start + int(matches[-1])
    base_window = frame.iloc[base_start : int(position) + 1]
    base_low = pd.to_numeric(base_window["Low"], errors="coerce").min()
    close = float(frame["Close"].iloc[int(position)])
    duration = int(position) - base_start
    depth = (float(pivot) - float(base_low)) / float(pivot) * 100
    distance = (close - float(pivot)) / float(pivot) * 100

    supply_window = frame.iloc[max(1, int(position) - 9) : int(position) + 1]
    previous_close = frame["Close"].shift(1).reindex(supply_window.index)
    average_volume = calculated["average_volume_50d_base"].reindex(supply_window.index)
    near_pivot = supply_window["Close"].between(
        float(pivot) * 0.92, float(pivot) * 1.08
    )
    supply_days = int(
        (
            supply_window["Close"].lt(previous_close)
            & supply_window["Volume"].ge(average_volume)
            & near_pivot
        ).sum()
    )
    contraction_count = pd.to_numeric(
        calculated.at[date, "contraction_count_3x20d"], errors="coerce"
    )
    dryup = pd.to_numeric(
        calculated.at[date, "volume_dryup_ratio_10v40"], errors="coerce"
    )
    base_stage = pd.to_numeric(calculated.at[date, "base_stage_proxy"], errors="coerce")
    complete = bool(
        15 <= duration <= 65
        and 3 <= depth <= 35
        and -5 <= distance <= 2
        and pd.notna(contraction_count)
        and float(contraction_count) >= 1
        and pd.notna(dryup)
        and float(dryup) <= 0.8
        and supply_days <= 1
        and pd.notna(base_stage)
        and float(base_stage) <= 2
    )
    return {
        "base_duration_sessions": duration,
        "base_depth_pct": depth,
        "distance_from_pivot_pct": distance,
        "pivot_supply_days_10d": supply_days,
        "complete_base_quality": complete,
    }


def enrich_base_features(
    signals: pd.DataFrame, histories: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """Attach fixed causal base/pivot features to signal rows."""

    result = signals.copy()
    if result.empty:
        return result
    result["signal_date"] = pd.to_datetime(result["signal_date"]).dt.date.astype(str)
    result["ticker"] = result["ticker"].astype(str).str.upper()
    values: dict[tuple[str, str], dict[str, Any]] = {}
    direct_columns = (
        "pivot_price_126d",
        "contraction_count_3x20d",
        "contraction_ratio_60d",
        "volume_dryup_ratio_10v40",
        "shakeout_reclaim_10d",
        "breakout_quality",
        "base_stage_proxy",
    )
    for ticker, group in result.groupby("ticker", sort=False):
        history = histories.get(str(ticker))
        if history is None or history.empty:
            continue
        numeric = _numeric_history(history)
        frame = base_feature_frame(numeric)
        for date_text in group["signal_date"].unique():
            date = pd.Timestamp(date_text)
            if date not in frame.index:
                continue
            row = {column: frame.at[date, column] for column in direct_columns}
            row.update(_point_base_features(numeric, frame, date))
            values[(str(ticker), str(date_text))] = row
    for column in BASE_FEATURE_COLUMNS:
        result[column] = [
            values.get((row.ticker, row.signal_date), {}).get(column, np.nan)
            for row in result[["ticker", "signal_date"]].itertuples(index=False)
        ]
    for column in ("shakeout_reclaim_10d", "breakout_quality", "complete_base_quality"):
        result[column] = result[column].fillna(False).astype(bool)
    return result


def delayed_followthrough_signals(
    breakout_signals: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    *,
    maximum_confirmation_sessions: int = 3,
    signal_period_end: str | None = None,
) -> pd.DataFrame:
    """Move breakout signals to the first causal follow-through close."""

    if maximum_confirmation_sessions <= 0:
        raise ValueError("maximum confirmation sessions must be positive")
    rows: list[dict[str, Any]] = []
    cutoff = pd.Timestamp(signal_period_end) if signal_period_end else None
    for ticker_value, ticker_signals in breakout_signals.groupby("ticker", sort=False):
        ticker = str(ticker_value)
        history = histories.get(ticker)
        if history is None or history.empty:
            continue
        frame = _numeric_history(history)
        calculated = base_feature_frame(frame)
        for original in ticker_signals.to_dict("records"):
            signal_date = pd.Timestamp(original["signal_date"])
            if signal_date not in frame.index:
                continue
            position = frame.index.get_loc(signal_date)
            if not isinstance(position, (int, np.integer)):
                continue
            original_close = float(frame.at[signal_date, "Close"])
            for lag in range(1, maximum_confirmation_sessions + 1):
                confirmation_position = int(position) + lag
                if confirmation_position >= len(frame):
                    break
                date = frame.index[confirmation_position]
                if cutoff is not None and date > cutoff:
                    break
                close = float(frame["Close"].iloc[confirmation_position])
                prior_close = float(frame["Close"].iloc[confirmation_position - 1])
                close_location = pd.to_numeric(
                    calculated["close_location_pct_base"].iloc[confirmation_position],
                    errors="coerce",
                )
                volume_ratio = pd.to_numeric(
                    calculated["volume_ratio_base"].iloc[confirmation_position],
                    errors="coerce",
                )
                if not (
                    close > original_close
                    and close > prior_close
                    and pd.notna(close_location)
                    and float(close_location) >= 60
                    and pd.notna(volume_ratio)
                    and float(volume_ratio) >= 0.8
                ):
                    continue
                stop_window = frame["Low"].iloc[
                    confirmation_position - 19 : confirmation_position + 1
                ]
                if len(stop_window) != 20:
                    break
                stop = float(stop_window.min())
                if not np.isfinite(stop) or stop >= close:
                    break
                confirmed = dict(original)
                confirmed.update(
                    {
                        "original_signal_date": str(original["signal_date"]),
                        "signal_date": date.date().isoformat(),
                        "data_as_of": date.date().isoformat(),
                        "price": close,
                        "volume": float(frame["Volume"].iloc[confirmation_position]),
                        "dollar_volume": close
                        * float(frame["Volume"].iloc[confirmation_position]),
                        "average_volume_50d": float(
                            calculated["average_volume_50d_base"].iloc[
                                confirmation_position
                            ]
                        ),
                        "structural_stop": stop,
                        "confirmation_lag_sessions": lag,
                        "confirmation_close_location_pct": float(close_location),
                        "confirmation_volume_ratio": float(volume_ratio),
                    }
                )
                rows.append(confirmed)
                break
    if not rows:
        return pd.DataFrame(columns=[*breakout_signals.columns, "original_signal_date"])
    return (
        pd.DataFrame(rows)
        .sort_values(["signal_date", "ticker", "original_signal_date"])
        .drop_duplicates(["signal_date", "ticker"], keep="first")
        .reset_index(drop=True)
    )
