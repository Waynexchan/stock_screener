"""Conservative next-session execution and R-based trade accounting."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import valid_bar_mask
from .models import ExecutionAssumptions, FeatureRecord, SimulatedTrade


@dataclass(frozen=True)
class PreparedTradeExecution:
    """Validated future bars cached once for multiple execution variants."""

    feature: FeatureRecord
    dates: pd.DatetimeIndex
    opens: np.ndarray
    highs: np.ndarray
    lows: np.ndarray
    closes: np.ndarray
    valid: np.ndarray
    reference_entry: float
    entry: float
    entry_slippage_bps: float
    maximum_holding_sessions: int


def _slipped(price: float, basis_points: float, direction: str) -> float:
    multiplier = (
        1 + basis_points / 10_000 if direction == "BUY" else 1 - basis_points / 10_000
    )
    return float(price * multiplier)


def prepare_trade_execution(
    feature: FeatureRecord,
    history: pd.DataFrame,
    assumptions: ExecutionAssumptions,
) -> PreparedTradeExecution | None:
    """Prepare one signal's future bars without evaluating any stop or target."""

    if not feature.model_0_signal or feature.structural_stop is None:
        return None
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
    reference_entry = float(future.iloc[0]["Open"])
    entry = _slipped(reference_entry, assumptions.entry_slippage_bps, "BUY")
    return PreparedTradeExecution(
        feature=feature,
        dates=pd.DatetimeIndex(future.index),
        opens=future["Open"].to_numpy(dtype=float),
        highs=future["High"].to_numpy(dtype=float),
        lows=future["Low"].to_numpy(dtype=float),
        closes=future["Close"].to_numpy(dtype=float),
        valid=valid_future.to_numpy(dtype=bool),
        reference_entry=reference_entry,
        entry=entry,
        entry_slippage_bps=assumptions.entry_slippage_bps,
        maximum_holding_sessions=assumptions.maximum_holding_sessions,
    )


def prepare_trade_executions(
    features: list[FeatureRecord],
    histories: dict[str, pd.DataFrame],
    assumptions: ExecutionAssumptions,
) -> list[PreparedTradeExecution]:
    """Batch-prepare many signals while validating each ticker history once."""

    grouped: dict[str, list[FeatureRecord]] = defaultdict(list)
    for feature in features:
        if feature.model_0_signal and feature.structural_stop is not None:
            grouped[feature.ticker].append(feature)
    prepared: list[PreparedTradeExecution] = []
    for ticker, ticker_features in grouped.items():
        history = histories.get(ticker)
        if history is None or history.empty:
            continue
        if (
            isinstance(history.index, pd.DatetimeIndex)
            and history.index.is_monotonic_increasing
        ):
            frame = history
        else:
            frame = history.copy()
            frame.index = pd.to_datetime(frame.index)
            frame = frame.sort_index()
        dates = pd.DatetimeIndex(frame.index)
        opens = frame["Open"].to_numpy(dtype=float)
        highs = frame["High"].to_numpy(dtype=float)
        lows = frame["Low"].to_numpy(dtype=float)
        closes = frame["Close"].to_numpy(dtype=float)
        valid = valid_bar_mask(frame).to_numpy(dtype=bool)
        for feature in ticker_features:
            start = dates.searchsorted(pd.Timestamp(feature.signal_date), side="right")
            end = min(start + assumptions.maximum_holding_sessions, len(dates))
            if start >= end or not valid[start]:
                continue
            reference_entry = float(opens[start])
            prepared.append(
                PreparedTradeExecution(
                    feature=feature,
                    dates=dates[start:end],
                    opens=opens[start:end],
                    highs=highs[start:end],
                    lows=lows[start:end],
                    closes=closes[start:end],
                    valid=valid[start:end],
                    reference_entry=reference_entry,
                    entry=_slipped(
                        reference_entry, assumptions.entry_slippage_bps, "BUY"
                    ),
                    entry_slippage_bps=assumptions.entry_slippage_bps,
                    maximum_holding_sessions=assumptions.maximum_holding_sessions,
                )
            )
    return prepared


def simulate_prepared_trade(
    prepared: PreparedTradeExecution,
    assumptions: ExecutionAssumptions,
    *,
    target_price: float | None = None,
    stop_price: float | None = None,
) -> SimulatedTrade | None:
    """Apply one stop/target policy to already validated future bars."""

    if assumptions.same_bar_policy != "STOP_FIRST":
        raise ValueError("only conservative STOP_FIRST same-bar handling is supported")
    if assumptions.entry_slippage_bps != prepared.entry_slippage_bps:
        raise ValueError("prepared entry or holding assumptions do not match")
    if (
        assumptions.maximum_holding_sessions <= 0
        or assumptions.maximum_holding_sessions > prepared.maximum_holding_sessions
    ):
        raise ValueError("requested holding period exceeds prepared execution")
    holding_limit = min(assumptions.maximum_holding_sessions, len(prepared.dates))
    dates = prepared.dates[:holding_limit]
    opens = prepared.opens[:holding_limit]
    highs = prepared.highs[:holding_limit]
    lows = prepared.lows[:holding_limit]
    closes = prepared.closes[:holding_limit]
    valid = prepared.valid[:holding_limit]
    feature = prepared.feature
    entry = prepared.entry
    stop = float(feature.structural_stop if stop_price is None else stop_price)
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

    reference_exit = float(closes[-1])
    exit_date = pd.Timestamp(dates[-1])
    exit_reason = "MAX_HOLD"
    observed_count = 0
    for position in range(len(dates)):
        if not valid[position]:
            break
        observed_count = position + 1
        open_price = float(opens[position])
        low = float(lows[position])
        high = float(highs[position])
        if position > 0 and open_price <= stop:
            reference_exit = open_price
            exit_date = pd.Timestamp(dates[position])
            exit_reason = "STOP_GAP"
            break
        if position > 0 and target is not None and open_price >= target:
            reference_exit = (
                target if assumptions.favorable_gap_fill == "LEVEL" else open_price
            )
            exit_date = pd.Timestamp(dates[position])
            exit_reason = "TARGET_GAP"
            break
        stop_touched = low <= stop
        target_touched = target is not None and high >= target
        if stop_touched and target_touched:
            reference_exit = stop
            exit_date = pd.Timestamp(dates[position])
            exit_reason = "STOP_AND_TARGET_SAME_BAR_CONSERVATIVE"
            break
        if stop_touched:
            reference_exit = stop
            exit_date = pd.Timestamp(dates[position])
            exit_reason = "STOP"
            break
        if target_touched:
            reference_exit = float(target)
            exit_date = pd.Timestamp(dates[position])
            exit_reason = "TARGET"
            break
    if observed_count == 0:
        return None

    exit_price = _slipped(reference_exit, assumptions.exit_slippage_bps, "SELL")
    entry_slippage = max(0.0, entry - prepared.reference_entry) * shares
    exit_slippage = max(0.0, reference_exit - exit_price) * shares
    commissions = assumptions.commission_per_share * shares * 2
    costs = entry_slippage + exit_slippage + commissions
    gross_pnl = (reference_exit - prepared.reference_entry) * shares
    net_pnl = gross_pnl - costs
    initial_risk_dollars = initial_risk_per_share * shares
    realised_r = net_pnl / initial_risk_dollars
    mfe_r = max(
        0.0,
        (float(highs[:observed_count].max()) - entry) / initial_risk_per_share,
    )
    mae_r = min(
        0.0,
        (float(lows[:observed_count].min()) - entry) / initial_risk_per_share,
    )
    return SimulatedTrade(
        signal_date=feature.signal_date,
        ticker=feature.ticker,
        entry_date=pd.Timestamp(dates[0]).date().isoformat(),
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
        holding_days=observed_count,
        exit_reason=exit_reason,
    )


def simulate_trade(
    feature: FeatureRecord,
    history: pd.DataFrame,
    assumptions: ExecutionAssumptions,
    *,
    target_price: float | None = None,
    stop_price: float | None = None,
) -> SimulatedTrade | None:
    """Simulate a conservative long trade from the first post-signal session.

    Stops gap through at the next observable open. Favorable target gaps fill at
    the target level by default. If stop and target are both touched in one bar,
    STOP_FIRST is mandatory for the current foundation.
    """

    prepared = prepare_trade_execution(feature, history, assumptions)
    if prepared is None:
        return None
    return simulate_prepared_trade(
        prepared,
        assumptions,
        target_price=target_price,
        stop_price=stop_price,
    )
