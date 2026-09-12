"""Point-in-time market features used by historical and forward research."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from run_screener import add_indicators


def _close_panel(histories: dict[str, pd.DataFrame]) -> pd.DataFrame:
    series = {
        ticker: pd.to_numeric(frame["Close"], errors="coerce")
        for ticker, frame in histories.items()
        if "Close" in frame
    }
    if not series:
        return pd.DataFrame()
    panel = pd.concat(series, axis=1).sort_index()
    panel.index = pd.to_datetime(panel.index)
    return panel


def _lookup(panel: pd.DataFrame, signals: pd.DataFrame) -> list[float]:
    values: list[float] = []
    for row in signals[["signal_date", "ticker"]].itertuples(index=False):
        date = pd.Timestamp(row.signal_date)
        value = (
            panel.at[date, row.ticker]
            if date in panel.index and row.ticker in panel
            else np.nan
        )
        values.append(float(value) if pd.notna(value) else np.nan)
    return values


def load_current_classifications(project_root: str | Path) -> dict[str, str]:
    path = Path(project_root) / "sector_industry_cache.csv"
    if not path.exists():
        return {}
    table = pd.read_csv(path, usecols=["Ticker", "Sector"])
    return dict(
        zip(
            table["Ticker"].astype(str).str.upper(),
            table["Sector"].fillna("").astype(str),
            strict=False,
        )
    )


def enrich_market_features(
    signals: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    benchmark: pd.DataFrame,
    *,
    classifications: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Add only features observable on or before each signal date."""

    result = signals.copy()
    if result.empty:
        return result
    result["signal_date"] = pd.to_datetime(result["signal_date"]).dt.date.astype(str)
    result["ticker"] = result["ticker"].astype(str).str.upper()
    closes = _close_panel(histories)
    recent_raw = sum(
        (closes / closes.shift(days) - 1) * weight
        for days, weight in ((5, 0.15), (20, 0.45), (60, 0.30), (126, 0.10))
    )
    long_raw = sum(
        (closes / closes.shift(days) - 1) * weight
        for days, weight in ((63, 0.50), (126, 0.30), (252, 0.20))
    )
    recent_scores = recent_raw.rank(axis=1, pct=True, method="average") * 100
    long_scores = long_raw.rank(axis=1, pct=True, method="average") * 100
    result["recent_rs_score"] = _lookup(recent_scores, result)
    result["long_term_rs_score"] = _lookup(long_scores, result)

    stock_returns = closes.pct_change(fill_method=None)
    spy = pd.to_numeric(benchmark["Close"], errors="coerce").copy()
    spy.index = pd.to_datetime(spy.index)
    spy_returns = spy.sort_index().pct_change(fill_method=None)
    beta = (
        stock_returns.rolling(126, min_periods=100)
        .cov(spy_returns)
        .div(spy_returns.rolling(126, min_periods=100).var(), axis=0)
    )
    result["rolling_beta_126"] = _lookup(beta, result)

    point_features: dict[tuple[str, str], dict[str, object]] = {}
    for ticker, group in result.groupby("ticker"):
        history = histories.get(ticker)
        if history is None or history.empty:
            continue
        indicators = add_indicators(history.sort_index())
        indicators.index = pd.to_datetime(indicators.index)
        for date_text in group["signal_date"].unique():
            date = pd.Timestamp(date_text)
            if date not in indicators.index:
                continue
            row = indicators.loc[date]
            close = pd.to_numeric(row.get("Close"), errors="coerce")
            ema10 = pd.to_numeric(row.get("EMA10"), errors="coerce")
            ema20 = pd.to_numeric(row.get("EMA20"), errors="coerce")
            high52 = pd.to_numeric(row.get("HIGH_52W"), errors="coerce")
            within = bool(
                pd.notna(close)
                and pd.notna(ema10)
                and pd.notna(ema20)
                and pd.notna(high52)
                and float(close) <= float(ema10) * 1.15
                and float(close) <= float(ema20) * 1.20
                and (float(high52) - float(close)) / float(high52) * 100 <= 35.0
            )
            point_features[(ticker, date_text)] = {
                "volume_ratio": pd.to_numeric(row.get("VOLUME_RATIO"), errors="coerce"),
                "adr_pct": pd.to_numeric(row.get("ADR_PCT"), errors="coerce"),
                "within_extension_limits": within,
            }
    for column in ("volume_ratio", "adr_pct", "within_extension_limits"):
        result[column] = [
            point_features.get((row.ticker, row.signal_date), {}).get(column, np.nan)
            for row in result[["ticker", "signal_date"]].itertuples(index=False)
        ]
    sectors = classifications or {}
    result["sector"] = result["ticker"].map(sectors).fillna("")
    result["is_utility"] = result["sector"].str.casefold().eq("utilities")
    return result
