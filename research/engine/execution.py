"""Conservative next-session execution and R-based trade accounting."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .data import valid_bar_mask
from .models import ExecutionAssumptions, FeatureRecord, SimulatedTrade


def _slipped(price: float, basis_points: float, direction: str) -> float:
    multiplier = (
        1 + basis_points / 10_000 if direction == "BUY" else 1 - basis_points / 10_000
    )
    return float(price * multiplier)


def simulate_trade(
    feature: FeatureRecord,
    history: pd.DataFrame,
    assumptions: ExecutionAssumptions,
    *,
    target_price: float | None = None,
) -> SimulatedTrade | None:
    """Simulate a long trade beginning at the first session after the signal.

    Stops gap through at the next observable open. Favorable target gaps fill at
    the target level by default. If stop and target are both touched in one bar,
    STOP_FIRST is mandatory for the current foundation.
    """

    if not feature.model_0_signal or feature.structural_stop is None:
        return None
    if assumptions.same_bar_policy != "STOP_FIRST":
        raise ValueError("only conservative STOP_FIRST same-bar handling is supported")
    if (
        isinstance(history.index, pd.DatetimeIndex)
        and history.index.is_monotonic_increasing
    ):
        frame = history
    else:
        frame = history.copy()
        frame.index = pd.to_datetime(frame.index)
        frame = frame.sort_index()
    start = frame.index.searchsorted(pd.Timestamp(feature.signal_date), side="right")
    future = frame.iloc[start : start + assumptions.maximum_holding_sessions]
    valid_future = valid_bar_mask(future)
    if future.empty or not bool(valid_future.iloc[0]):
        return None

    entry_date = pd.Timestamp(future.index[0])
    reference_entry = float(future.iloc[0]["Open"])
    entry = _slipped(reference_entry, assumptions.entry_slippage_bps, "BUY")
    stop = float(feature.structural_stop)
    if (
        not all(np.isfinite(value) and value > 0 for value in (entry, stop))
        or stop >= entry
    ):
        return None
    initial_risk_per_share = entry - stop
    shares = math.floor(assumptions.standard_r_dollars / initial_risk_per_share)
    if shares <= 0:
        return None
    target = target_price
    if target is None and assumptions.target_r is not None:
        target = entry + assumptions.target_r * initial_risk_per_share
    if target is not None and (not np.isfinite(target) or target <= entry):
        raise ValueError("target must be finite and above entry")

    reference_exit = float(future.iloc[-1]["Close"])
    exit_date = pd.Timestamp(future.index[-1])
    exit_reason = "MAX_HOLD"
    observed = future.iloc[0:0]
    for position, (bar_date, bar) in enumerate(future.iterrows()):
        if not bool(valid_future.iloc[position]):
            break
        observed = future.iloc[: position + 1]
        open_price = float(bar["Open"])
        low = float(bar["Low"])
        high = float(bar["High"])
        if position > 0 and open_price <= stop:
            reference_exit = open_price
            exit_date = pd.Timestamp(bar_date)
            exit_reason = "STOP_GAP"
            break
        if position > 0 and target is not None and open_price >= target:
            reference_exit = (
                target if assumptions.favorable_gap_fill == "LEVEL" else open_price
            )
            exit_date = pd.Timestamp(bar_date)
            exit_reason = "TARGET_GAP"
            break
        stop_touched = low <= stop
        target_touched = target is not None and high >= target
        if stop_touched and target_touched:
            reference_exit = stop
            exit_date = pd.Timestamp(bar_date)
            exit_reason = "STOP_AND_TARGET_SAME_BAR_CONSERVATIVE"
            break
        if stop_touched:
            reference_exit = stop
            exit_date = pd.Timestamp(bar_date)
            exit_reason = "STOP"
            break
        if target_touched:
            reference_exit = float(target)
            exit_date = pd.Timestamp(bar_date)
            exit_reason = "TARGET"
            break
    if observed.empty:
        return None

    exit_price = _slipped(reference_exit, assumptions.exit_slippage_bps, "SELL")
    entry_slippage = max(0.0, entry - reference_entry) * shares
    exit_slippage = max(0.0, reference_exit - exit_price) * shares
    commissions = assumptions.commission_per_share * shares * 2
    costs = entry_slippage + exit_slippage + commissions
    gross_pnl = (reference_exit - reference_entry) * shares
    net_pnl = gross_pnl - costs
    initial_risk_dollars = initial_risk_per_share * shares
    realised_r = net_pnl / initial_risk_dollars
    mfe_r = max(0.0, (float(observed["High"].max()) - entry) / initial_risk_per_share)
    mae_r = min(0.0, (float(observed["Low"].min()) - entry) / initial_risk_per_share)
    return SimulatedTrade(
        signal_date=feature.signal_date,
        ticker=feature.ticker,
        entry_date=entry_date.date().isoformat(),
        exit_date=exit_date.date().isoformat(),
        entry=round(entry, 6),
        initial_stop=round(stop, 6),
        target=None if target is None else round(float(target), 6),
        initial_risk_per_share=round(initial_risk_per_share, 6),
        shares=shares,
        exit=round(exit_price, 6),
        gross_pnl=round(gross_pnl, 6),
        costs=round(costs, 6),
        net_pnl=round(net_pnl, 6),
        realised_r=round(realised_r, 6),
        MFE_R=round(mfe_r, 6),
        MAE_R=round(mae_r, 6),
        holding_days=len(observed),
        exit_reason=exit_reason,
    )
