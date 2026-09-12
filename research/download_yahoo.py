"""Download a labelled current-universe Yahoo dataset for engineering research."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

from research.engine.reporting import ensure_research_output_path


def yahoo_symbol(ticker: str) -> str:
    return ticker.strip().upper().replace(".", "-")


def ticker_frame(download: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if download.empty:
        return pd.DataFrame()
    if isinstance(download.columns, pd.MultiIndex):
        first = set(download.columns.get_level_values(0))
        second = set(download.columns.get_level_values(1))
        if symbol in first:
            return download[symbol].copy()
        if symbol in second:
            return download.xs(symbol, axis=1, level=1).copy()
        return pd.DataFrame()
    return download.copy()


def long_form(frame: pd.DataFrame, original_ticker: str) -> pd.DataFrame:
    if frame.empty or not {"Open", "High", "Low", "Close", "Volume"} <= set(
        frame.columns
    ):
        return pd.DataFrame()
    result = frame.reset_index()
    date_column = result.columns[0]
    result = result.rename(columns={date_column: "Date"})
    result.insert(1, "Ticker", original_ticker)
    result["Date"] = pd.to_datetime(result["Date"], errors="coerce", utc=True).dt.date
    result = result.dropna(subset=["Date", "Open", "High", "Low", "Close", "Volume"])
    return result[["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"]]


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--universe", type=Path, default=Path("universe.csv"))
    command.add_argument("--start", default="2016-01-01")
    command.add_argument("--end", default="2026-09-13")
    command.add_argument("--batch-size", type=int, default=50)
    command.add_argument(
        "--output-dir", type=Path, default=Path("research/output/yahoo_engineering")
    )
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    output_dir = ensure_research_output_path(project_root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    universe = pd.read_csv(args.universe, usecols=["Ticker"])
    requested = list(dict.fromkeys(universe["Ticker"].dropna().astype(str).str.upper()))
    if "SPY" not in requested:
        requested.append("SPY")
    symbol_map = {ticker: yahoo_symbol(ticker) for ticker in requested}
    reverse_map = {symbol: ticker for ticker, symbol in symbol_map.items()}
    successful: set[str] = set()
    parts: list[pd.DataFrame] = []
    for offset in range(0, len(requested), args.batch_size):
        originals = requested[offset : offset + args.batch_size]
        symbols = [symbol_map[item] for item in originals]
        downloaded = yf.download(
            symbols,
            start=args.start,
            end=args.end,
            interval="1d",
            auto_adjust=True,
            group_by="ticker",
            threads=True,
            progress=False,
            timeout=30,
        )
        for symbol in symbols:
            original = reverse_map[symbol]
            part = long_form(ticker_frame(downloaded, symbol), original)
            if not part.empty:
                parts.append(part)
                successful.add(original)
        print(
            f"Downloaded batch {offset // args.batch_size + 1}: "
            f"{len(successful)}/{len(requested)} symbols available"
        )
    table = (
        pd.concat(parts, ignore_index=True)
        if parts
        else pd.DataFrame(
            columns=["Date", "Ticker", "Open", "High", "Low", "Close", "Volume"]
        )
    )
    table = table.sort_values(["Ticker", "Date"]).drop_duplicates(
        ["Ticker", "Date"], keep="last"
    )
    benchmark_table = table[table["Ticker"].eq("SPY")].copy()
    price_table = table[~table["Ticker"].eq("SPY")].copy()
    price_path = output_dir / "prices.csv"
    benchmark_path = output_dir / "benchmark.csv"
    temporary = output_dir / "prices.csv.partial"
    price_table.to_csv(temporary, index=False)
    temporary.replace(price_path)
    benchmark_table.to_csv(benchmark_path, index=False)
    digest = hashlib.sha256(price_path.read_bytes()).hexdigest()
    metadata = {
        "source": "Yahoo Finance via yfinance",
        "research_label": "SURVIVORSHIP-BIASED RESEARCH",
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "requested_start": args.start,
        "requested_end_exclusive": args.end,
        "universe_source": str(args.universe.resolve()),
        "current_universe_only": True,
        "includes_delisted_symbols": False,
        "auto_adjust": True,
        "requested_symbol_count": len(requested),
        "successful_symbol_count": len(successful),
        "failed_symbols": sorted(set(requested) - successful),
        "row_count": len(price_table),
        "benchmark_row_count": len(benchmark_table),
        "earliest_date": str(table["Date"].min()) if len(table) else None,
        "latest_date": str(table["Date"].max()) if len(table) else None,
        "sha256": digest,
        "benchmark_sha256": hashlib.sha256(benchmark_path.read_bytes()).hexdigest(),
    }
    (output_dir / "download_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"Dataset: {price_path}")
    print(f"Rows: {len(table)}; symbols: {len(successful)}/{len(requested)}")
    print("Label: SURVIVORSHIP-BIASED RESEARCH")
    return 0 if successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
