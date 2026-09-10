"""Reusable R-based research metrics."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .models import SimulatedTrade
from .portfolio import portfolio_exposure


def _round(value: float | None) -> float | None:
    return None if value is None or not np.isfinite(value) else round(float(value), 6)


def drawdown_statistics(realised_r: pd.Series) -> tuple[float | None, float | None]:
    values = pd.to_numeric(realised_r, errors="coerce").dropna()
    if values.empty:
        return None, None
    equity = values.cumsum()
    high_water = equity.cummax().clip(lower=0.0)
    drawdown = high_water - equity
    return float(drawdown.max()), float(drawdown.mean())


def bootstrap_mean_interval(
    values: pd.Series, *, seed: int, samples: int = 1_000, confidence: float = 0.95
) -> tuple[float | None, float | None]:
    clean = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    if len(clean) < 2 or samples <= 0:
        return None, None
    generator = np.random.default_rng(seed)
    means = generator.choice(clean, size=(samples, len(clean)), replace=True).mean(
        axis=1
    )
    tail = (1 - confidence) / 2
    return float(np.quantile(means, tail)), float(np.quantile(means, 1 - tail))


def calculate_metrics(
    trades: list[SimulatedTrade],
    *,
    signal_count: int,
    maximum_positions: int,
    seed: int,
) -> dict[str, Any]:
    frame = pd.DataFrame([item.to_dict() for item in trades])
    empty: dict[str, Any] = {
        "signal_count": int(signal_count),
        "triggered_trade_count": 0,
        "win_rate": None,
        "average_win_r": None,
        "average_loss_r": None,
        "expectancy_r": None,
        "median_r": None,
        "standard_deviation_r": None,
        "expectancy_bootstrap_95_low_r": None,
        "expectancy_bootstrap_95_high_r": None,
        "profit_factor": None,
        "maximum_drawdown_r": None,
        "average_drawdown_r": None,
        "average_mfe_r": None,
        "average_mae_r": None,
        "average_holding_days": None,
        "trade_frequency_per_year": None,
        "exposure": None,
    }
    if frame.empty:
        return empty
    realised = pd.to_numeric(frame["realised_r"], errors="coerce").dropna()
    wins = realised[realised > 0]
    losses = realised[realised <= 0]
    maximum_drawdown, average_drawdown = drawdown_statistics(realised)
    interval_low, interval_high = bootstrap_mean_interval(realised, seed=seed)
    first = pd.to_datetime(frame["entry_date"]).min()
    last = pd.to_datetime(frame["exit_date"]).max()
    years = max((last - first).days / 365.25, 1 / 252)
    profit_factor = (
        float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() else None
    )
    return {
        "signal_count": int(signal_count),
        "triggered_trade_count": int(len(realised)),
        "win_rate": _round(float((realised > 0).mean())),
        "average_win_r": _round(float(wins.mean())) if len(wins) else None,
        "average_loss_r": _round(float(losses.mean())) if len(losses) else None,
        "expectancy_r": _round(float(realised.mean())),
        "median_r": _round(float(realised.median())),
        "standard_deviation_r": _round(float(realised.std(ddof=1)))
        if len(realised) > 1
        else None,
        "expectancy_bootstrap_95_low_r": _round(interval_low),
        "expectancy_bootstrap_95_high_r": _round(interval_high),
        "profit_factor": _round(profit_factor),
        "maximum_drawdown_r": _round(maximum_drawdown),
        "average_drawdown_r": _round(average_drawdown),
        "average_mfe_r": _round(
            float(pd.to_numeric(frame["MFE_R"], errors="coerce").mean())
        ),
        "average_mae_r": _round(
            float(pd.to_numeric(frame["MAE_R"], errors="coerce").mean())
        ),
        "average_holding_days": _round(
            float(pd.to_numeric(frame["holding_days"]).mean())
        ),
        "trade_frequency_per_year": _round(float(len(realised) / years)),
        "exposure": _round(portfolio_exposure(trades, maximum_positions)),
    }
