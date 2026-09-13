from __future__ import annotations

import pandas as pd

from research.download_yahoo_earnings import normalize_calendar_frame, week_windows


def test_week_windows_cover_every_calendar_date_once() -> None:
    assert week_windows("2026-01-01", "2026-01-10") == [
        ("2026-01-01", "2026-01-07"),
        ("2026-01-08", "2026-01-10"),
    ]


def test_normalize_calendar_frame_preserves_event_date_and_ticker() -> None:
    frame = pd.DataFrame(
        {
            "Event Start Date": [pd.Timestamp("2026-01-05 21:00:00+00:00")],
            "Timing": ["AMC"],
            "Company": ["Example"],
        },
        index=pd.Index(["abc"], name="Symbol"),
    )
    result = normalize_calendar_frame(frame)
    assert result.loc[0, "Ticker"] == "ABC"
    assert result.loc[0, "EarningsDate"] == "2026-01-05"
    assert result.loc[0, "Timing"] == "AMC"
