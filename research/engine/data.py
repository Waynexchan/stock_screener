"""Research data loading, adjustment, validation, and readiness auditing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PRICE_COLUMNS = ("Open", "High", "Low", "Close", "Volume")
READINESS_STATES = {"READY", "PARTIALLY_READY", "NOT_READY"}


def valid_bar_mask(frame: pd.DataFrame) -> pd.Series:
    """Identify internally consistent OHLCV rows without filling bad values."""

    missing = set(PRICE_COLUMNS) - set(frame.columns)
    if missing:
        return pd.Series(False, index=frame.index, dtype=bool)
    numeric = frame.loc[:, PRICE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    price = numeric[["Open", "High", "Low", "Close"]]
    return (
        numeric.notna().all(axis=1)
        & (price > 0).all(axis=1)
        & (numeric["Volume"] >= 0)
        & (numeric["High"] >= price[["Open", "Close", "Low"]].max(axis=1))
        & (numeric["Low"] <= price[["Open", "Close", "High"]].min(axis=1))
    )


def _canonical_columns(frame: pd.DataFrame) -> pd.DataFrame:
    aliases = {
        "date": "Date",
        "ticker": "Ticker",
        "symbol": "Ticker",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "adj close": "Adj Close",
        "adj_close": "Adj Close",
        "volume": "Volume",
    }
    return frame.rename(
        columns={
            column: aliases.get(column.strip().lower(), column)
            for column in frame.columns
        }
    )


def adjust_ohlcv(frame: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Return an adjusted OHLCV frame and a transparent adjustment label.

    If both Close and Adj Close exist, the ratio is applied to OHLC and the
    reciprocal ratio to volume. This handles ordinary split-adjusted datasets,
    but dividend and split effects cannot be separated without an action ledger.
    """

    adjusted = frame.copy()
    if "Adj Close" not in adjusted.columns:
        return adjusted, "PROVIDER_ADJUSTED_OR_UNVERIFIED"
    close = pd.to_numeric(adjusted["Close"], errors="coerce")
    adj_close = pd.to_numeric(adjusted["Adj Close"], errors="coerce")
    factor = (adj_close / close).replace([np.inf, -np.inf], np.nan)
    for column in ("Open", "High", "Low", "Close"):
        adjusted[column] = pd.to_numeric(adjusted[column], errors="coerce") * factor
    adjusted["Volume"] = pd.to_numeric(adjusted["Volume"], errors="coerce") / factor
    return adjusted, "ADJ_CLOSE_RATIO"


def normalise_price_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    table = _canonical_columns(frame)
    missing = {"Date", "Ticker", *PRICE_COLUMNS} - set(table.columns)
    if missing:
        raise ValueError(f"price data missing columns: {', '.join(sorted(missing))}")
    table = table.copy()
    table["Date"] = pd.to_datetime(table["Date"], errors="coerce")
    table["Ticker"] = table["Ticker"].astype(str).str.strip().str.upper()
    table = table.dropna(subset=["Date"]).sort_values(["Ticker", "Date"])
    table, adjustment_method = adjust_ohlcv(table)
    for column in PRICE_COLUMNS:
        table[column] = pd.to_numeric(table[column], errors="coerce")
    duplicate_count = int(table.duplicated(["Ticker", "Date"]).sum())
    table = table.drop_duplicates(["Ticker", "Date"], keep="last")
    invalid_bar = ~valid_bar_mask(table)
    diagnostics = {
        "adjustment_method": adjustment_method,
        "row_count": int(len(table)),
        "symbol_count": int(table["Ticker"].nunique()),
        "duplicate_rows_removed": duplicate_count,
        "invalid_or_missing_bar_count": int(invalid_bar.sum()),
        "missing_or_invalid_bar_frequency": (
            round(float(invalid_bar.mean()), 6) if len(table) else None
        ),
        "earliest_date": table["Date"].min().date().isoformat() if len(table) else None,
        "latest_date": table["Date"].max().date().isoformat() if len(table) else None,
    }
    table["Valid Bar"] = ~invalid_bar
    return table.reset_index(drop=True), diagnostics


def load_price_csv(path: str | Path) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    table, diagnostics = normalise_price_frame(pd.read_csv(source))
    histories: dict[str, pd.DataFrame] = {}
    for ticker, group in table.groupby("Ticker", sort=True):
        histories[str(ticker)] = group.set_index("Date").sort_index()
    diagnostics["source"] = str(source.resolve())
    return histories, diagnostics


def _item(status: str, summary: str, **details: Any) -> dict[str, Any]:
    if status not in READINESS_STATES:
        raise ValueError(f"unsupported readiness status: {status}")
    return {"status": status, "summary": summary, **details}


def audit_repository_data(
    project_root: str | Path,
    price_path: str | Path | None = None,
    universe_history_path: str | Path | None = None,
    benchmark_path: str | Path | None = None,
) -> dict[str, Any]:
    """Audit durable local research inputs without downloading or inventing data."""

    root = Path(project_root).resolve()
    diagnostics: dict[str, Any] | None = None
    price_item: dict[str, Any]
    if price_path is None:
        price_item = _item(
            "NOT_READY",
            "No durable long-form historical OHLCV research dataset was supplied.",
            earliest_reliable_date=None,
            latest_reliable_date=None,
            symbol_count=0,
            missing_data_frequency=None,
        )
    else:
        try:
            _, diagnostics = load_price_csv(price_path)
            long_enough = bool(diagnostics["row_count"] and diagnostics["symbol_count"])
            price_item = _item(
                "READY" if long_enough else "NOT_READY",
                "A readable research OHLCV dataset was supplied."
                if long_enough
                else "The supplied OHLCV dataset contains no usable rows.",
                earliest_reliable_date=diagnostics["earliest_date"],
                latest_reliable_date=diagnostics["latest_date"],
                symbol_count=diagnostics["symbol_count"],
                missing_data_frequency=diagnostics["missing_or_invalid_bar_frequency"],
                adjustment_method=diagnostics["adjustment_method"],
            )
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            price_item = _item(
                "NOT_READY", f"Historical OHLCV input failed validation: {exc}"
            )

    universe_snapshot = root / "universe.csv"
    current_universe_count = 0
    if universe_snapshot.exists():
        try:
            current_universe_count = len(
                pd.read_csv(universe_snapshot, usecols=["Ticker"])
            )
        except (OSError, ValueError, pd.errors.ParserError):
            current_universe_count = 0
    universe_history_exists = bool(
        universe_history_path and Path(universe_history_path).exists()
    )

    snapshot_files = sorted(
        (root / "output" / "forward_snapshots").glob("*/*/candidates.csv")
    )
    snapshot_dates = sorted({path.parents[1].name for path in snapshot_files})
    snapshot_rows = 0
    for path in snapshot_files:
        try:
            snapshot_rows += len(pd.read_csv(path, usecols=["Ticker"]))
        except (OSError, ValueError, pd.errors.ParserError):
            continue

    benchmark_exists = bool(benchmark_path and Path(benchmark_path).exists())
    items = {
        "price_history": price_item,
        "universe_history": _item(
            "READY" if universe_history_exists else "NOT_READY",
            "Point-in-time universe membership supplied."
            if universe_history_exists
            else "Only a current-universe snapshot exists; historical membership is unavailable.",
            current_snapshot_symbols=current_universe_count,
        ),
        "delisted_stocks": _item(
            "NOT_READY", "No delisted-symbol membership or return history is archived."
        ),
        "sector_industry_history": _item(
            "NOT_READY",
            "Current metadata caches have no point-in-time effective-date history.",
        ),
        "market_cap_history": _item(
            "NOT_READY", "No point-in-time market-cap history is available."
        ),
        "benchmark_history": _item(
            "READY" if benchmark_exists else "NOT_READY",
            "A durable benchmark history was supplied."
            if benchmark_exists
            else "SPY/QQQ are downloaded for production but not archived as research history.",
        ),
        "corporate_actions": _item(
            "PARTIALLY_READY",
            "Production downloads use auto-adjusted data, but no durable split/dividend/delisting action ledger exists.",
        ),
        "split_adjustment": _item(
            "PARTIALLY_READY",
            "The research loader supports provider-adjusted OHLCV or Adj Close ratio adjustment; an action ledger is still absent.",
        ),
        "dividend_adjustment": _item(
            "PARTIALLY_READY",
            "Adj Close may include dividends, but split and dividend effects cannot be audited separately without an action ledger.",
        ),
        "forward_snapshots": _item(
            "PARTIALLY_READY" if snapshot_files else "NOT_READY",
            "Recent immutable candidate snapshots are evidence, not a multi-year OHLCV backtest dataset.",
            snapshot_dates=snapshot_dates,
            snapshot_file_count=len(snapshot_files),
            candidate_rows=snapshot_rows,
        ),
    }
    required = (
        "price_history",
        "universe_history",
        "delisted_stocks",
        "benchmark_history",
    )
    overall = (
        "READY"
        if all(items[name]["status"] == "READY" for name in required)
        else "NOT_READY"
    )
    return {
        "overall_status": overall,
        "research_label": "SURVIVORSHIP-BIASED RESEARCH"
        if items["universe_history"]["status"] != "READY"
        or items["delisted_stocks"]["status"] != "READY"
        else "POINT-IN-TIME UNIVERSE RESEARCH",
        "items": items,
        "biases": {
            "SURVIVORSHIP_BIAS": "HIGH: historical membership and delisted symbols are unavailable.",
            "LOOK_AHEAD_BIAS": "CONTROLLED BY ENGINE: features slice all bars at the signal date; input provenance still requires audit.",
            "CLASSIFICATION_BIAS": "HIGH: sector/industry history with effective dates is unavailable.",
            "DATA_AVAILABILITY_BIAS": "HIGH: only current universe data and three recent forward-snapshot dates are present.",
        },
        "price_diagnostics": diagnostics,
    }
