from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from research.engine.earnings import (
    EarningsBlackoutContext,
    apply_earnings_blackout,
    apply_earnings_blackout_to_signals,
    load_verified_earnings_blackout_context,
    next_earnings_date,
)
from research.engine.reproducibility import sha256_file
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


def test_signal_blackout_happens_before_downstream_portfolio_selection() -> None:
    context = EarningsBlackoutContext(
        calendar={"AAA": pd.DatetimeIndex(["2026-01-15"])},
        coverage_start="2026-01-01",
        coverage_end="2026-12-31",
        earnings_sha256="fixture",
        metadata_sha256="fixture",
    )
    signals = pd.DataFrame(
        [
            {"signal_date": "2026-01-05", "ticker": "AAA", "score": 99},
            {"signal_date": "2026-01-04", "ticker": "AAA", "score": 98},
            {"signal_date": "2026-01-05", "ticker": "BBB", "score": 97},
        ]
    )
    allowed, rejected = apply_earnings_blackout_to_signals(
        signals, context, blackout_calendar_days=10
    )
    assert allowed[["ticker", "score"]].to_dict("records") == [
        {"ticker": "AAA", "score": 98},
        {"ticker": "BBB", "score": 97},
    ]
    assert rejected.to_dict("records") == [
        {
            "signal_date": "2026-01-05",
            "ticker": "AAA",
            "earnings_date": "2026-01-15",
            "calendar_days_to_earnings": 10,
            "earnings_rejection_reason": "EARNINGS_WITHIN_BLACKOUT",
        }
    ]


def test_verified_blackout_context_requires_matching_hash_and_full_window(
    tmp_path: Path,
) -> None:
    earnings = tmp_path / "earnings.csv"
    earnings.write_text("Ticker,EarningsDate\nAAA,2026-01-15\n", encoding="utf-8")
    metadata = tmp_path / "metadata.json"
    payload = {
        "complete_calendar_date_coverage": True,
        "earnings_sha256": sha256_file(earnings),
        "requested_start_inclusive": "2026-01-01",
        "requested_end_inclusive": "2026-01-31",
    }
    metadata.write_text(json.dumps(payload), encoding="utf-8")
    context = load_verified_earnings_blackout_context(
        earnings,
        metadata,
        required_signal_start="2026-01-05",
        required_signal_end="2026-01-20",
        blackout_calendar_days=10,
    )
    assert context.earnings_sha256 == payload["earnings_sha256"]
    payload["earnings_sha256"] = "wrong"
    metadata.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        load_verified_earnings_blackout_context(
            earnings,
            metadata,
            required_signal_start="2026-01-05",
            required_signal_end="2026-01-20",
            blackout_calendar_days=10,
        )
