"""Conservative forward execution for frozen production trade plans."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .data import valid_bar_mask

PLAN_OUTCOME_COLUMNS = (
    "signal_date",
    "ticker",
    "plan_triggered",
    "plan_entry_date",
    "plan_exit_date",
    "plan_entry",
    "plan_exit",
    "plan_realised_r",
    "plan_mfe_r",
    "plan_mae_r",
    "plan_holding_sessions",
    "plan_outcome_status",
)


def _number(value: object) -> float | None:
    parsed = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(parsed) or not np.isfinite(parsed) else float(parsed)


def _slip(price: float, basis_points: float, buy: bool) -> float:
    direction = 1 if buy else -1
    return price * (1 + direction * basis_points / 10_000)


def simulate_frozen_plan(
    row: dict[str, Any],
    history: pd.DataFrame,
    *,
    entry_valid_sessions: int = 5,
    maximum_holding_sessions: int = 40,
    entry_slippage_bps: float = 5.0,
    exit_slippage_bps: float = 5.0,
) -> dict[str, Any]:
    """Evaluate a point-in-time entry/stop/target plan without inventing maturity."""

    ticker = str(row.get("ticker", row.get("Ticker", ""))).upper()
    signal_date = str(row.get("signal_date", row.get("Signal Date", "")))
    planned_entry = _number(row.get("Planned Entry"))
    stop = _number(row.get("Initial Stop"))
    target = _number(row.get("Realistic Target"))
    target_source = str(row.get("Realistic Target Source", ""))
    base: dict[str, Any] = {
        "signal_date": signal_date,
        "ticker": ticker,
        "plan_triggered": False,
        "plan_entry_date": None,
        "plan_exit_date": None,
        "plan_entry": None,
        "plan_exit": None,
        "plan_realised_r": None,
        "plan_mfe_r": None,
        "plan_mae_r": None,
        "plan_holding_sessions": None,
        "plan_outcome_status": "INVALID_PLAN",
    }
    if (
        planned_entry is None
        or stop is None
        or stop >= planned_entry
        or entry_valid_sessions <= 0
        or maximum_holding_sessions <= 0
    ):
        return base
    if (
        target_source == "model 2R feasibility target"
        or target is None
        or target <= planned_entry
    ):
        target = None
    frame = history.copy().sort_index()
    frame.index = pd.to_datetime(frame.index)
    future = frame.loc[frame.index > pd.Timestamp(signal_date)]
    trigger_position: int | None = None
    reference_entry: float | None = None
    for position, (_, bar) in enumerate(future.head(entry_valid_sessions).iterrows()):
        if not bool(valid_bar_mask(future.iloc[[position]]).iloc[0]):
            continue
        open_price = float(bar["Open"])
        high = float(bar["High"])
        if open_price >= planned_entry:
            trigger_position, reference_entry = position, open_price
            break
        if high >= planned_entry:
            trigger_position, reference_entry = position, planned_entry
            break
    if trigger_position is None or reference_entry is None:
        base["plan_outcome_status"] = "NOT_TRIGGERED"
        return base
    entry = _slip(reference_entry, entry_slippage_bps, True)
    risk = entry - stop
    if risk <= 0 or not np.isfinite(risk):
        return base
    observed = future.iloc[
        trigger_position : trigger_position + maximum_holding_sessions
    ]
    valid = valid_bar_mask(observed)
    exit_reference: float | None = None
    exit_date: pd.Timestamp | None = None
    exit_reason: str | None = None
    observed_count = 0
    for position, (bar_date, bar) in enumerate(observed.iterrows()):
        if not bool(valid.iloc[position]):
            break
        observed_count = position + 1
        open_price, low, high = (float(bar[name]) for name in ("Open", "Low", "High"))
        if position > 0 and open_price <= stop:
            exit_reference, exit_date, exit_reason = (
                open_price,
                pd.Timestamp(bar_date),
                "STOP_GAP",
            )
            break
        if position > 0 and target is not None and open_price >= target:
            exit_reference, exit_date, exit_reason = (
                target,
                pd.Timestamp(bar_date),
                "TARGET_GAP_LEVEL",
            )
            break
        stop_touched = low <= stop
        target_touched = target is not None and high >= target
        if stop_touched:
            exit_reference, exit_date = stop, pd.Timestamp(bar_date)
            exit_reason = "STOP_AND_TARGET_SAME_BAR" if target_touched else "STOP"
            break
        if target_touched:
            exit_reference, exit_date, exit_reason = (
                target,
                pd.Timestamp(bar_date),
                "TARGET",
            )
            break
    entry_date = pd.Timestamp(observed.index[0])
    base.update(
        {
            "plan_triggered": True,
            "plan_entry_date": entry_date.date().isoformat(),
            "plan_entry": entry,
            "plan_mfe_r": max(
                0.0,
                float((observed.iloc[:observed_count]["High"].max() - entry) / risk),
            ),
            "plan_mae_r": min(
                0.0, float((observed.iloc[:observed_count]["Low"].min() - entry) / risk)
            ),
            "plan_holding_sessions": observed_count,
        }
    )
    if exit_reference is None:
        if observed_count < maximum_holding_sessions:
            base["plan_outcome_status"] = "OPEN_UNMATURED"
            return base
        exit_reference = float(observed.iloc[maximum_holding_sessions - 1]["Close"])
        exit_date = pd.Timestamp(observed.index[maximum_holding_sessions - 1])
        exit_reason = "MAX_HOLD"
    exit_price = _slip(exit_reference, exit_slippage_bps, False)
    realised_r = (exit_price - entry) / risk
    base.update(
        {
            "plan_exit_date": exit_date.date().isoformat() if exit_date else None,
            "plan_exit": exit_price,
            "plan_realised_r": realised_r,
            "plan_outcome_status": exit_reason,
        }
    )
    return base
