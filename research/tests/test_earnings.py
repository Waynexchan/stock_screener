from __future__ import annotations

import pandas as pd

from research.engine.earnings import apply_earnings_blackout, next_earnings_date
from research.engine.models import SimulatedTrade


def trade(signal_date: str, ticker: str = "AAA") -> SimulatedTrade:
    return SimulatedTrade(
        signal_date=signal_date,
        ticker=ticker,
        entry_date="2026-01-06",
        exit_date="2026-01-07",
        entry=100,
        initial_stop=95,
        target=None,
        initial_risk_per_share=5,
        shares=100,
        exit=105,
        gross_pnl=500,
        costs=0,
        net_pnl=500,
        realised_r=1,
        MFE_R=1,
        MAE_R=0,
        holding_days=2,
        exit_reason="FIXTURE",
    )


def test_next_earnings_date_is_on_or_after_signal() -> None:
    calendar = {"AAA": pd.DatetimeIndex(["2026-01-05", "2026-02-01"])}
    assert next_earnings_date("2026-01-05", "AAA", calendar) == pd.Timestamp(
        "2026-01-05"
    )
    assert next_earnings_date("2026-01-06", "AAA", calendar) == pd.Timestamp(
        "2026-02-01"
    )


def test_earnings_blackout_is_inclusive_through_ten_calendar_days() -> None:
    calendar = {"AAA": pd.DatetimeIndex(["2026-01-15"])}
    allowed, rejected = apply_earnings_blackout(
        [trade("2026-01-05"), trade("2026-01-04")],
        calendar,
        blackout_calendar_days=10,
        covered_start="2026-01-01",
        covered_end="2026-12-31",
    )
    assert [item.signal_date for item in allowed] == ["2026-01-04"]
    assert rejected[0].reason == "EARNINGS_WITHIN_BLACKOUT"
    assert rejected[0].calendar_days_to_earnings == 10


def test_earnings_blackout_fails_closed_outside_calendar_coverage() -> None:
    allowed, rejected = apply_earnings_blackout(
        [trade("2025-12-25")],
        {},
        blackout_calendar_days=10,
        covered_start="2025-01-01",
        covered_end="2025-12-31",
    )
    assert not allowed
    assert rejected[0].reason == "CALENDAR_COVERAGE_UNAVAILABLE"
