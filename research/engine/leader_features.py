"""Causal cross-sectional leadership features for research-only experiments."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


LEADER_FEATURE_COLUMNS = (
    "marketsmith_proxy_score",
    "marketsmith_proxy_delta_21d",
    "rs_line",
    "rs_line_within_2pct_252d_high",
    "industry",
    "industry_proxy_score",
    "up_down_volume_ratio_50d",
    "price_off_252d_high_pct",
)


def load_current_sector_industry(
    project_root: str | Path,
) -> tuple[dict[str, str], dict[str, str]]:
    """Load explicitly current, non-point-in-time classification mappings."""

    path = Path(project_root) / "sector_industry_cache.csv"
    if not path.exists():
        return {}, {}
    table = pd.read_csv(path, usecols=["Ticker", "Sector", "Industry"])
    tickers = table["Ticker"].astype(str).str.upper()
    sectors = dict(zip(tickers, table["Sector"].fillna("").astype(str), strict=False))
    industries = dict(
        zip(tickers, table["Industry"].fillna("").astype(str), strict=False)
    )
    return sectors, industries


def _panel(histories: dict[str, pd.DataFrame], column: str) -> pd.DataFrame:
    series = {
        ticker: pd.to_numeric(frame[column], errors="coerce")
        for ticker, frame in histories.items()
        if column in frame
    }
    if not series:
        return pd.DataFrame()
    result = pd.concat(series, axis=1).sort_index()
    result.index = pd.to_datetime(result.index)
    return result


def _score_1_to_99(raw: pd.DataFrame) -> pd.DataFrame:
    percentiles = raw.rank(axis=1, pct=True, method="average")
    return np.ceil(percentiles * 99).clip(1, 99)


def _lookup(panel: pd.DataFrame, signals: pd.DataFrame) -> list[object]:
    values: list[object] = []
    for row in signals[["signal_date", "ticker"]].itertuples(index=False):
        date = pd.Timestamp(row.signal_date)
        value = (
            panel.at[date, row.ticker]
            if date in panel.index and row.ticker in panel.columns
            else np.nan
        )
        values.append(value)
    return values


def leader_feature_panels(
    histories: dict[str, pd.DataFrame],
    benchmark: pd.DataFrame,
    industries: dict[str, str],
    *,
    minimum_industry_members: int = 5,
) -> dict[str, pd.DataFrame]:
    """Build signal-date-only full-universe leadership feature panels."""

    if minimum_industry_members <= 0:
        raise ValueError("minimum industry members must be positive")
    closes = _panel(histories, "Close")
    volumes = _panel(histories, "Volume").reindex_like(closes)
    if closes.empty:
        return {name: pd.DataFrame() for name in LEADER_FEATURE_COLUMNS}

    q1 = closes.div(closes.shift(63)) - 1
    q2 = closes.shift(63).div(closes.shift(126)) - 1
    q3 = closes.shift(126).div(closes.shift(189)) - 1
    q4 = closes.shift(189).div(closes.shift(252)) - 1
    raw = 0.40 * q1 + 0.20 * q2 + 0.20 * q3 + 0.20 * q4
    proxy_score = _score_1_to_99(raw)
    proxy_delta = proxy_score - proxy_score.shift(21)

    spy = pd.to_numeric(benchmark["Close"], errors="coerce").copy()
    spy.index = pd.to_datetime(spy.index)
    spy = spy.sort_index().reindex(closes.index)
    rs_line = closes.div(spy, axis=0)
    rs_line_high = rs_line.rolling(252, min_periods=252).max()
    rs_line_near_high = rs_line.ge(rs_line_high * 0.98)

    price_high = closes.rolling(252, min_periods=252).max()
    price_off_high = (price_high - closes).div(price_high) * 100

    changes = closes.pct_change(fill_method=None)
    valid_50 = (
        (closes.notna() & volumes.notna()).rolling(50, min_periods=50).sum().eq(50)
    )
    up_volume = volumes.where(changes.gt(0), 0.0).rolling(50, min_periods=50).sum()
    down_volume = volumes.where(changes.lt(0), 0.0).rolling(50, min_periods=50).sum()
    up_down_ratio = up_volume.div(down_volume).where(valid_50 & down_volume.gt(0))

    industry_medians: dict[str, pd.Series] = {}
    for industry in sorted({value for value in industries.values() if value}):
        members = [
            ticker
            for ticker in proxy_score.columns
            if industries.get(str(ticker), "") == industry
        ]
        if len(members) < minimum_industry_members:
            continue
        member_scores = proxy_score[members]
        median = member_scores.median(axis=1, skipna=True).where(
            member_scores.count(axis=1).ge(minimum_industry_members)
        )
        industry_medians[industry] = median
    industry_raw = pd.DataFrame(industry_medians, index=proxy_score.index)
    industry_scores = _score_1_to_99(industry_raw)
    stock_industry_scores = pd.DataFrame(
        {
            ticker: industry_scores.get(industries.get(str(ticker), ""))
            for ticker in proxy_score.columns
        },
        index=proxy_score.index,
    )

    return {
        "marketsmith_proxy_score": proxy_score,
        "marketsmith_proxy_delta_21d": proxy_delta,
        "rs_line": rs_line,
        "rs_line_within_2pct_252d_high": rs_line_near_high,
        "industry_proxy_score": stock_industry_scores,
        "up_down_volume_ratio_50d": up_down_ratio,
        "price_off_252d_high_pct": price_off_high,
    }


def enrich_leader_features(
    signals: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    benchmark: pd.DataFrame,
    *,
    sectors: dict[str, str] | None = None,
    industries: dict[str, str] | None = None,
    minimum_industry_members: int = 5,
) -> pd.DataFrame:
    """Attach causal leader features to signal rows without future outcomes."""

    result = signals.copy()
    if result.empty:
        return result
    result["signal_date"] = pd.to_datetime(result["signal_date"]).dt.date.astype(str)
    result["ticker"] = result["ticker"].astype(str).str.upper()
    sector_map = sectors or {}
    industry_map = industries or {}
    panels = leader_feature_panels(
        histories,
        benchmark,
        industry_map,
        minimum_industry_members=minimum_industry_members,
    )
    for column, panel in panels.items():
        result[column] = _lookup(panel, result)
    result["rs_line_within_2pct_252d_high"] = (
        result["rs_line_within_2pct_252d_high"].fillna(False).astype(bool)
    )
    result["sector"] = result["ticker"].map(sector_map).fillna("")
    result["industry"] = result["ticker"].map(industry_map).fillna("")
    result["is_utility"] = result["sector"].str.casefold().eq("utilities")
    return result
