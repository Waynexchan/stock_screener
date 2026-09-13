"""Causal interfaces for research-only pre-earnings entry blackouts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .models import SimulatedTrade
from .reproducibility import sha256_file


@dataclass(frozen=True)
class EarningsRejection:
    trade: SimulatedTrade
    reason: str
    earnings_date: str | None
    calendar_days_to_earnings: int | None


@dataclass(frozen=True)
class EarningsBlackoutContext:
    """Verified retrospective earnings input and its declared coverage."""

    calendar: dict[str, pd.DatetimeIndex]
    coverage_start: str
    coverage_end: str
    earnings_sha256: str
    metadata_sha256: str

    def provenance(self) -> dict[str, Any]:
        return {
            "calendar_coverage_start": self.coverage_start,
            "calendar_coverage_end": self.coverage_end,
            "earnings_sha256": self.earnings_sha256,
            "earnings_metadata_sha256": self.metadata_sha256,
            "point_in_time_schedule": False,
        }


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


def load_verified_earnings_blackout_context(
    earnings_path: str | Path,
    metadata_path: str | Path,
    *,
    required_signal_start: str,
    required_signal_end: str,
    blackout_calendar_days: int,
) -> EarningsBlackoutContext:
    """Load a hash-verified calendar and require coverage through the blackout."""

    if blackout_calendar_days < 0:
        raise ValueError("blackout days cannot be negative")
    earnings_file = Path(earnings_path)
    metadata_file = Path(metadata_path)
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    if not bool(metadata.get("complete_calendar_date_coverage", False)):
        raise ValueError("earnings calendar does not have complete date coverage")
    earnings_hash = sha256_file(earnings_file)
    if str(metadata.get("earnings_sha256")) != earnings_hash:
        raise ValueError("earnings calendar hash does not match metadata")
    coverage_start = str(metadata["requested_start_inclusive"])
    coverage_end = str(metadata["requested_end_inclusive"])
    required_end = pd.Timestamp(required_signal_end) + pd.Timedelta(
        days=blackout_calendar_days
    )
    if (
        pd.Timestamp(coverage_start) > pd.Timestamp(required_signal_start)
        or pd.Timestamp(coverage_end) < required_end
    ):
        raise ValueError("earnings calendar does not cover required signal windows")
    return EarningsBlackoutContext(
        calendar=load_earnings_calendar(earnings_file),
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        earnings_sha256=earnings_hash,
        metadata_sha256=sha256_file(metadata_file),
    )


def apply_earnings_blackout_to_signals(
    signals: pd.DataFrame,
    context: EarningsBlackoutContext,
    *,
    blackout_calendar_days: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Remove blacked-out signals before ranking, execution, or allocation."""

    required = {"signal_date", "ticker"}
    missing = required.difference(signals.columns)
    if missing:
        raise ValueError(
            f"signals missing earnings-blackout columns: {sorted(missing)}"
        )
    keep: list[bool] = []
    rejections: list[dict[str, Any]] = []
    coverage_start = pd.Timestamp(context.coverage_start).normalize()
    coverage_end = pd.Timestamp(context.coverage_end).normalize()
    for row in signals[["signal_date", "ticker"]].to_dict("records"):
        signal_date = str(row["signal_date"])
        ticker = str(row["ticker"])
        signal = pd.Timestamp(signal_date).normalize()
        required_end = signal + pd.Timedelta(days=blackout_calendar_days)
        if signal < coverage_start or required_end > coverage_end:
            raise ValueError("earnings calendar coverage unavailable for signal")
        event = next_earnings_date(signal_date, ticker, context.calendar)
        days_to_event = None if event is None else int((event - signal).days)
        rejected = bool(
            days_to_event is not None and 0 <= days_to_event <= blackout_calendar_days
        )
        keep.append(not rejected)
        if rejected:
            assert event is not None
            rejections.append(
                {
                    "signal_date": signal.date().isoformat(),
                    "ticker": ticker,
                    "earnings_date": event.date().isoformat(),
                    "calendar_days_to_earnings": days_to_event,
                    "earnings_rejection_reason": "EARNINGS_WITHIN_BLACKOUT",
                }
            )
    return signals.loc[keep].copy(), pd.DataFrame(rejections)


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
