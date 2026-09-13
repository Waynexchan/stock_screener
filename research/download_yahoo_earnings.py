"""Download a retrospective Yahoo earnings-event calendar for research."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

from research.engine.reporting import ensure_research_output_path
from research.engine.reproducibility import sha256_file


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--start", default="2017-01-01")
    command.add_argument("--end", default="2025-11-10")
    command.add_argument("--workers", type=int, default=4)
    command.add_argument(
        "--output-dir",
        type=Path,
        default=Path("research/output/yahoo_earnings_engineering"),
    )
    return command


def week_windows(start: str, end: str) -> list[tuple[str, str]]:
    first = pd.Timestamp(start).normalize()
    last = pd.Timestamp(end).normalize()
    if first > last:
        raise ValueError("earnings calendar start must not follow end")
    windows: list[tuple[str, str]] = []
    current = first
    while current <= last:
        window_end = min(current + pd.Timedelta(days=6), last)
        windows.append((current.date().isoformat(), window_end.date().isoformat()))
        current = window_end + pd.Timedelta(days=1)
    return windows


def normalize_calendar_frame(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Ticker",
        "EarningsDate",
        "EventTimestamp",
        "Timing",
        "Company",
        "Source",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    if "Event Start Date" not in frame.columns:
        raise ValueError("Yahoo earnings response lacks Event Start Date")
    result = frame.reset_index().rename(columns={frame.index.name or "index": "Ticker"})
    timestamps = pd.to_datetime(result["Event Start Date"], errors="coerce", utc=True)
    result["Ticker"] = result["Ticker"].astype(str).str.strip().str.upper()
    result["EarningsDate"] = timestamps.dt.date.astype("string")
    result["EventTimestamp"] = timestamps.astype("string")
    if "Timing" not in result:
        result["Timing"] = pd.NA
    if "Company" not in result:
        result["Company"] = pd.NA
    result["Source"] = "Yahoo Finance via yfinance Calendars"
    result = result.dropna(subset=["Ticker", "EarningsDate"])
    return result[columns]


def _fetch_window(start: str, end: str) -> tuple[pd.DataFrame, int]:
    calendar = yf.Calendars(start=start, end=end)
    pages: list[pd.DataFrame] = []
    page_count = 0
    for offset in range(0, 2500, 100):
        page = calendar.get_earnings_calendar(
            filter_most_active=False,
            limit=100,
            offset=offset,
            force=True,
        )
        page_count += 1
        if page is None or page.empty:
            break
        pages.append(page)
        if len(page) < 100:
            break
    else:
        raise ValueError(f"earnings pagination exceeded safety cap: {start} to {end}")
    raw = pd.concat(pages) if pages else pd.DataFrame()
    return normalize_calendar_frame(raw), page_count


def _cache_name(start: str, end: str) -> str:
    return f"earnings__{start}__{end}.csv"


def _load_cached(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"Ticker": str, "EarningsDate": str})


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.workers <= 0:
        raise ValueError("workers must be positive")
    project_root = Path(__file__).resolve().parents[1]
    output_dir = ensure_research_output_path(project_root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = output_dir / "weeks"
    cache_dir.mkdir(parents=True, exist_ok=True)
    windows = week_windows(args.start, args.end)
    parts: dict[tuple[str, str], pd.DataFrame] = {}
    pending: list[tuple[str, str]] = []
    for window in windows:
        cached = cache_dir / _cache_name(*window)
        if cached.exists():
            parts[window] = _load_cached(cached)
        else:
            pending.append(window)

    failures: dict[str, str] = {}
    page_counts: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(_fetch_window, start, end): (start, end)
            for start, end in pending
        }
        complete = len(parts)
        for future in as_completed(futures):
            window = futures[future]
            key = f"{window[0]}__{window[1]}"
            try:
                frame, pages = future.result()
                frame.to_csv(cache_dir / _cache_name(*window), index=False)
                parts[window] = frame
                page_counts[key] = pages
            except Exception as exc:  # pragma: no cover - network behavior
                failures[key] = f"{type(exc).__name__}: {exc}"
            complete += 1
            if complete % 25 == 0 or complete == len(windows):
                print(
                    f"Earnings windows: {complete}/{len(windows)}; failures: {len(failures)}",
                    flush=True,
                )

    metadata: dict[str, Any] = {
        "source": "Yahoo Finance via yfinance Calendars",
        "source_limitation": "Retrospective actual/revised earnings dates; not point-in-time schedule snapshots.",
        "research_label": "EARNINGS-SCHEDULE-BIASED RESEARCH",
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "requested_start_inclusive": args.start,
        "requested_end_inclusive": args.end,
        "window_days": 7,
        "window_count": len(windows),
        "successful_window_count": len(parts),
        "failed_windows": failures,
        "new_window_page_counts": page_counts,
        "complete_calendar_date_coverage": not failures and len(parts) == len(windows),
    }
    if failures or len(parts) != len(windows):
        (output_dir / "download_metadata.partial.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
        )
        print("Earnings download incomplete; final calendar was not replaced.")
        return 1

    table = pd.concat([parts[window] for window in windows], ignore_index=True)
    table = table.drop_duplicates(
        ["Ticker", "EarningsDate", "EventTimestamp"], keep="last"
    ).sort_values(["EarningsDate", "Ticker", "EventTimestamp"])
    temporary = output_dir / "earnings.csv.partial"
    final = output_dir / "earnings.csv"
    table.to_csv(temporary, index=False)
    temporary.replace(final)
    metadata.update(
        {
            "row_count": len(table),
            "symbol_count": int(table["Ticker"].nunique()),
            "earliest_event_date": str(table["EarningsDate"].min()),
            "latest_event_date": str(table["EarningsDate"].max()),
            "earnings_sha256": sha256_file(final),
        }
    )
    (output_dir / "download_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"Earnings calendar: {final}")
    print(f"Rows: {len(table)}; symbols: {table['Ticker'].nunique()}")
    print("Label: EARNINGS-SCHEDULE-BIASED RESEARCH")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
