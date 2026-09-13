"""Causal interfaces for research-only pre-earnings entry blackouts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .models import SimulatedTrade


@dataclass(frozen=True)
class EarningsRejection:
    trade: SimulatedTrade
    reason: str
    earnings_date: str | None
    calendar_days_to_earnings: int | None


def load_earnings_calendar(path: str | Path) -> dict[str, pd.DatetimeIndex]:
    """Load a normalized, retrospectively retrieved earnings-event calendar."""

    frame = pd.read_csv(path, usecols=["Ticker", "EarningsDate"])
    frame["Ticker"] = frame["Ticker"].astype(str).str.strip().str.upper()
    frame["EarningsDate"] = pd.to_datetime(frame["EarningsDate"], errors="coerce")
    frame = frame.dropna(subset=["Ticker", "EarningsDate"])
    frame = frame.drop_duplicates(["Ticker", "EarningsDate"])
    return {
        str(ticker): pd.DatetimeIndex(group["EarningsDate"]).normalize().sort_values()
        for ticker, group in frame.groupby("Ticker", sort=False)
    }


def next_earnings_date(
    signal_date: str, ticker: str, calendar: dict[str, pd.DatetimeIndex]
) -> pd.Timestamp | None:
    dates = calendar.get(ticker.strip().upper())
    if dates is None or dates.empty:
        return None
    signal = pd.Timestamp(signal_date).normalize()
    position = dates.searchsorted(signal, side="left")
    if position >= len(dates):
        return None
    return pd.Timestamp(dates[position])


def apply_earnings_blackout(
    trades: list[SimulatedTrade],
    calendar: dict[str, pd.DatetimeIndex],
    *,
    blackout_calendar_days: int,
    covered_start: str,
    covered_end: str,
) -> tuple[list[SimulatedTrade], list[EarningsRejection]]:
    """Reject signals within the inclusive pre-event window; fail closed outside coverage."""

    if blackout_calendar_days < 0:
        raise ValueError("blackout days cannot be negative")
    coverage_start = pd.Timestamp(covered_start).normalize()
    coverage_end = pd.Timestamp(covered_end).normalize()
    allowed: list[SimulatedTrade] = []
    rejected: list[EarningsRejection] = []
    for trade in trades:
        signal = pd.Timestamp(trade.signal_date).normalize()
        required_end = signal + pd.Timedelta(days=blackout_calendar_days)
        if signal < coverage_start or required_end > coverage_end:
            rejected.append(
                EarningsRejection(trade, "CALENDAR_COVERAGE_UNAVAILABLE", None, None)
            )
            continue
        event = next_earnings_date(trade.signal_date, trade.ticker, calendar)
        days_to_event = None if event is None else int((event - signal).days)
        if days_to_event is not None and 0 <= days_to_event <= blackout_calendar_days:
            assert event is not None
            rejected.append(
                EarningsRejection(
                    trade,
                    "EARNINGS_WITHIN_BLACKOUT",
                    event.date().isoformat(),
                    days_to_event,
                )
            )
            continue
        allowed.append(trade)
    return allowed, rejected
