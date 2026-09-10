"""Minimal deterministic portfolio-capacity simulation."""

from __future__ import annotations

import pandas as pd

from .models import SimulatedTrade


def apply_position_capacity(
    trades: list[SimulatedTrade], maximum_positions: int
) -> tuple[list[SimulatedTrade], list[SimulatedTrade]]:
    """Accept trades in signal/ticker order without using their profitability."""

    if maximum_positions <= 0:
        raise ValueError("maximum_positions must be positive")
    accepted: list[SimulatedTrade] = []
    rejected: list[SimulatedTrade] = []
    for trade in sorted(
        trades, key=lambda item: (item.entry_date, item.signal_date, item.ticker)
    ):
        entry = pd.Timestamp(trade.entry_date)
        open_at_entry = [
            item for item in accepted if pd.Timestamp(item.exit_date) >= entry
        ]
        same_ticker_open = any(item.ticker == trade.ticker for item in open_at_entry)
        if same_ticker_open or len(open_at_entry) >= maximum_positions:
            rejected.append(trade)
        else:
            accepted.append(trade)
    return accepted, rejected


def portfolio_exposure(
    trades: list[SimulatedTrade], maximum_positions: int
) -> float | None:
    if not trades or maximum_positions <= 0:
        return None
    start = min(pd.Timestamp(item.entry_date) for item in trades)
    end = max(pd.Timestamp(item.exit_date) for item in trades)
    sessions = pd.bdate_range(start, end)
    if not len(sessions):
        return None
    active_slots = 0
    for session in sessions:
        active_slots += sum(
            pd.Timestamp(item.entry_date) <= session <= pd.Timestamp(item.exit_date)
            for item in trades
        )
    return float(active_slots / (len(sessions) * maximum_positions))
