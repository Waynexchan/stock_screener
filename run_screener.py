"""Simple US stock screener using Yahoo Finance data."""

from __future__ import annotations

import math
import os
import re
import subprocess
import sys
import time
import shutil
import logging
from dataclasses import dataclass, field
from html import escape
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import pandas as pd
import yfinance as yf

import config
import ai_analysis
from ai_analysis import AIAnalysisResult, analyse_top_action_list


OUTPUT_CSV = "daily_watchlist.csv"
OUTPUT_MD = "daily_watchlist.md"
OUTPUT_HTML = "daily_watchlist.html"
EMAIL_SUMMARY = "email_summary.txt"
LAST_GOOD_CSV = "daily_watchlist_last_good.csv"
LAST_GOOD_MD = "daily_watchlist_last_good.md"
LAST_GOOD_HTML = "daily_watchlist_last_good.html"
DATA_FAILURE_REPORT = "data_failure_report.txt"
UNIVERSE_TEMP_CSV = "universe_temp.csv"
UNIVERSE_RAW_TEMP_CSV = "universe_raw_temp.csv"
UNIVERSE_BACKUP_CSV = "universe_backup.csv"
YFINANCE_CACHE_DIR = ".yfinance_cache"
UNIVERSE_COLUMNS = [
    "Ticker", "Symbol", "Security Name", "Exchange", "Sector", "Industry",
    "Market Cap", "Avg Volume",
]
DISCOVERY_COLUMNS = [
    "Category", "Ticker", "Sector", "Industry", "RS Score", "Price",
    "Action",
    "ATR20", "ATR20 %",
    "ADR %", "From 52W High %", "Distance From 50MA %",
    "Distance From 30WMA %", "Distance From Pivot %", "Volume Ratio",
    "Distance From EMA10 ATR", "Distance From EMA20 ATR",
    "Distance From MA50 ATR", "Distance From 30WMA ATR",
    "Nearest Support Distance ATR",
    "Support Signal",
    "10 Day Range %", "20 Day Range %", "Tightness Score",
    "Tightness Label", "ADR20 %", "ADR60 %", "VCP Ratio", "VCP Label",
    "Pullback Quality", "Extension Status", "Risk/Reward Quality",
    "Industry Rank", "Avg Volume", "TradingView",
]
TOP_INDUSTRY_COLUMNS = [
    "Industry", "Sector", "Industry Strength Score", "Candidate Count",
    "Avg RS Score", "Best RS Score", "Top 3 Leaders",
]
CATEGORY_NAMES = [
    "Breakout Candidates",
    "Pullback Candidates",
    "Tight Consolidation Candidates",
    "Extended Candidates",
    "Volume Surge Candidates",
]
CATEGORY_PRIORITY = [
    "Breakout Candidates",
    "Volume Surge Candidates",
    "Pullback Candidates",
    "Tight Consolidation Candidates",
    "Extended Candidates",
]
FOCUS_LIMITS = {
    "Breakout Candidates": 5,
    "Volume Surge Candidates": 5,
    "Pullback Candidates": 8,
    "Tight Consolidation Candidates": 8,
    "Extended Candidates": 3,
}
DAILY_FOCUS_MAX = 25
TOP_ACTION_MAX = 8
MARKET_COLUMNS = ["Symbol", "10EMA", "20EMA", "50MA"]
NON_COMMON_PATTERNS = [
    r"\bETF\b",
    r"\bFUND\b",
    r"\bETN\b",
    r"\bNOTES?\b",
    r"\bWARRANTS?\b",
    r"\bRIGHTS?\b",
    r"\bUNITS?\b",
    r"\bPREFERRED\b",
    r"\bPREFERENCE\b",
    r"\bDEPOSITARY\b",
    r"\bDEPOSITORY\b",
    r"\bACQUISITION\b",
    r"\bSPAC\b",
    r"\bCONVERTIBLE\b",
    r"\bBONDS?\b",
    r"\bINDEX\b",
]


Path(YFINANCE_CACHE_DIR).mkdir(exist_ok=True)
yf.cache.set_cache_location(YFINANCE_CACHE_DIR)
logging.getLogger("yfinance").setLevel(logging.CRITICAL)


@dataclass
class DownloadStats:
    requested: int = 0
    successful: int = 0
    failed: int = 0
    temporary_failures: int = 0
    network_failures: int = 0
    no_price_history: int = 0

    @property
    def success_rate(self) -> float:
        if self.requested == 0:
            return 0.0
        return self.successful / self.requested


@dataclass
class UniverseLoadResult:
    universe: pd.DataFrame
    total_downloaded: int
    total_after_filter: int
    fallback_used: bool = False
    refresh_failed_validation: bool = False


@dataclass
class MarketConditionResult:
    frame: pd.DataFrame
    status: str
    spy_valid: bool
    qqq_valid: bool
    data_failure: bool
    stats: DownloadStats


@dataclass
class RunQualityResult:
    valid: bool
    reason: str
    universe_count: int
    requested_tickers: int
    successful_downloads: int
    failed_downloads: int
    success_rate: float
    spy_valid: bool
    qqq_valid: bool
    fallback_used: bool


@dataclass
class RunTimer:
    max_seconds: int
    started_at: float = field(default_factory=time.monotonic)

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.started_at

    @property
    def expired(self) -> bool:
        return self.elapsed_seconds >= self.max_seconds

    def sleep(self, seconds: int | float) -> bool:
        if self.expired:
            return False
        remaining = max(0.0, self.max_seconds - self.elapsed_seconds)
        time.sleep(min(seconds, remaining))
        return not self.expired


@dataclass
class UniverseRefreshResult:
    raw_symbols: int = 0
    filtered_symbols: int = 0
    final_valid_symbols: int = 0
    spy_valid: bool = False
    qqq_valid: bool = False
    download_success_rate: float = 0.0
    runtime_seconds: float = 0.0
    universe_replaced: bool = False
    backup_created: bool = False
    fallback_used: bool = False
    reason: str = ""


def pct(part: float, whole: float) -> float:
    if whole == 0 or pd.isna(whole):
        return np.nan
    return (part / whole) * 100


def pullback_quality(distance_50ma_atr: float, distance_30wma_atr: float) -> str:
    if pd.isna(distance_50ma_atr) or pd.isna(distance_30wma_atr):
        return ""
    if distance_50ma_atr <= 2 and distance_30wma_atr <= 5:
        return "A"
    if distance_50ma_atr <= 3 and distance_30wma_atr <= 7:
        return "B"
    if distance_50ma_atr <= 5 and distance_30wma_atr <= 10:
        return "C"
    return "D"


def pullback_quality_label(quality: str) -> str:
    labels = {
        "A": "A - Ideal Pullback",
        "B": "B - Healthy Pullback",
        "C": "C - Extended Pullback",
        "D": "D - Overextended Pullback",
    }
    return labels.get(quality, "")


def extension_status(distance_50ma_atr: float) -> str:
    if pd.isna(distance_50ma_atr):
        return ""
    if distance_50ma_atr <= 2:
        return "Not Extended"
    if distance_50ma_atr <= 4:
        return "Moderately Extended"
    if distance_50ma_atr <= 6:
        return "Extended"
    return "Overextended"


def risk_reward_quality(nearest_support_atr: float, status: str) -> str:
    if pd.isna(nearest_support_atr) or not status:
        return ""
    if status == "Overextended":
        return "Avoid"
    if nearest_support_atr <= 1.0 and status == "Not Extended":
        return "Excellent R/R"
    if nearest_support_atr <= 1.5 and status in {"Not Extended", "Moderately Extended"}:
        return "Good R/R"
    if nearest_support_atr > 2.0 or status == "Extended":
        return "Poor R/R"
    return "Fair R/R"


def tightness_label(range_10d_pct: float) -> str:
    if pd.isna(range_10d_pct):
        return ""
    if range_10d_pct <= 5:
        return "Very Tight"
    if range_10d_pct <= 8:
        return "Tight"
    if range_10d_pct <= 12:
        return "Normal"
    return "Loose"


def vcp_label(vcp_ratio: float) -> str:
    if pd.isna(vcp_ratio):
        return ""
    if vcp_ratio <= 0.50:
        return "Excellent VCP"
    if vcp_ratio <= 0.70:
        return "Good VCP"
    if vcp_ratio <= 0.90:
        return "Average VCP"
    return "Poor VCP"


def pullback_quality_rank(quality_label: str) -> int:
    if quality_label.startswith("A"):
        return 1
    if quality_label.startswith("B"):
        return 2
    if quality_label.startswith("C"):
        return 3
    if quality_label.startswith("D"):
        return 4
    return 0


def extension_status_rank(status: str) -> int:
    ranks = {
        "Not Extended": 1,
        "Moderately Extended": 2,
        "Extended": 3,
        "Overextended": 4,
    }
    return ranks.get(status, 99)


def risk_reward_quality_rank(quality: str) -> int:
    ranks = {
        "Excellent R/R": 1,
        "Good R/R": 2,
        "Fair R/R": 3,
        "Poor R/R": 4,
        "Avoid": 5,
    }
    return ranks.get(quality, 99)


def category_priority_rank(category: str) -> int:
    try:
        return CATEGORY_PRIORITY.index(category) + 1
    except ValueError:
        return 99


def vcp_label_rank(label: str) -> int:
    ranks = {
        "Excellent VCP": 1,
        "Good VCP": 2,
        "Average VCP": 3,
        "Poor VCP": 4,
    }
    return ranks.get(label, 99)


def yahoo_symbol(symbol: str) -> str:
    return symbol.replace(".", "-")


def tradingview_url(exchange: str, ticker: str) -> str:
    tv_symbol = ticker.replace("-", ".")
    return f"https://www.tradingview.com/chart/?symbol={exchange}:{tv_symbol}"


def read_nasdaq_trader_file(url: str) -> pd.DataFrame:
    with urlopen(url, timeout=30) as response:
        return pd.read_csv(response, sep="|")


def is_common_stock(name: str) -> bool:
    upper_name = str(name).upper()
    return not any(re.search(pattern, upper_name) for pattern in NON_COMMON_PATTERNS)


def download_listed_tickers() -> tuple[pd.DataFrame, int]:
    nasdaq = read_nasdaq_trader_file(config.NASDAQ_LISTED_URL)
    other = read_nasdaq_trader_file(config.OTHER_LISTED_URL)

    raw_nasdaq = nasdaq[nasdaq["Symbol"].notna() & (nasdaq["Test Issue"] == "N")]
    raw_nyse = other[
        other["ACT Symbol"].notna()
        & (other["Exchange"] == "N")
        & (other["Test Issue"] == "N")
    ]
    total_downloaded = len(raw_nasdaq) + len(raw_nyse)

    nasdaq = nasdaq[nasdaq["Symbol"].notna() & (nasdaq["Test Issue"] == "N")]
    nasdaq = nasdaq[nasdaq["ETF"] == "N"]
    nasdaq = nasdaq[["Symbol", "Security Name"]].copy()
    nasdaq["Exchange"] = "NASDAQ"

    nyse = other[
        other["ACT Symbol"].notna()
        & (other["Exchange"] == "N")
        & (other["Test Issue"] == "N")
        & (other["ETF"] == "N")
    ].copy()
    nyse = nyse[["ACT Symbol", "Security Name"]]
    nyse.columns = ["Symbol", "Security Name"]
    nyse["Exchange"] = "NYSE"

    listed = pd.concat([nasdaq, nyse], ignore_index=True)
    listed = listed[~listed["Symbol"].str.contains(r"[$^/]", regex=True, na=False)]
    listed = listed[listed["Security Name"].apply(is_common_stock)]
    listed["Yahoo Ticker"] = listed["Symbol"].apply(yahoo_symbol)
    return listed.drop_duplicates("Yahoo Ticker").reset_index(drop=True), total_downloaded


def chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def ticker_frame_from_download(history: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame()
    try:
        frame = history[ticker] if isinstance(history.columns, pd.MultiIndex) else history
    except (KeyError, TypeError):
        return pd.DataFrame()
    if not isinstance(frame, pd.DataFrame):
        return pd.DataFrame()
    return frame.dropna(how="all")


def has_usable_price_history(frame: pd.DataFrame, min_rows: int = 1) -> bool:
    required = {"Close", "Volume"}
    if frame.empty or not required.issubset(frame.columns):
        return False
    close = frame["Close"].dropna()
    return len(close) >= min_rows


def download_history_batch(tickers: list[str], period: str) -> pd.DataFrame:
    if not tickers:
        return pd.DataFrame()
    try:
        return yf.download(
            tickers=tickers,
            period=period,
            interval="1d",
            auto_adjust=True,
            group_by="ticker",
            threads=False,
            progress=False,
            timeout=config.YAHOO_DOWNLOAD_TIMEOUT_SECONDS,
        )
    except Exception:
        return pd.DataFrame()


def download_price_histories(
    tickers: list[str],
    period: str = "18mo",
    min_rows: int = 1,
    retry_delays: list[int] | None = None,
    timer: RunTimer | None = None,
    max_attempts: int | None = None,
) -> tuple[dict[str, pd.DataFrame], DownloadStats]:
    print(f"Downloading Yahoo Finance price data for {len(tickers)} tickers...")
    histories: dict[str, pd.DataFrame] = {}
    requested = list(dict.fromkeys(tickers))
    if not requested:
        return histories, DownloadStats()

    pending = requested
    attempt_limit = max_attempts or config.MAX_DOWNLOAD_ATTEMPTS
    chunk_sizes = ([config.DOWNLOAD_CHUNK_SIZE] + list(config.FALLBACK_CHUNK_SIZES))[:attempt_limit]
    delays = retry_delays if retry_delays is not None else config.HISTORY_RETRY_DELAYS_SECONDS

    for attempt, chunk_size in enumerate(chunk_sizes):
        if timer and timer.expired:
            break
        failed_this_attempt = []
        for batch in chunked(pending, chunk_size):
            if timer and timer.expired:
                failed_this_attempt.extend(batch)
                continue
            history = download_history_batch(batch, period)
            if history.empty:
                failed_this_attempt.extend(batch)
                continue

            for ticker in batch:
                frame = ticker_frame_from_download(history, ticker)
                if has_usable_price_history(frame, min_rows=min_rows):
                    histories[ticker] = frame
                else:
                    failed_this_attempt.append(ticker)

        pending = [ticker for ticker in failed_this_attempt if ticker not in histories]
        if not pending or attempt == len(chunk_sizes) - 1:
            break

        delay_index = min(attempt, len(delays) - 1)
        if delays:
            if timer:
                timer.sleep(delays[delay_index])
            else:
                time.sleep(delays[delay_index])

    failed = len([ticker for ticker in requested if ticker not in histories])
    stats = DownloadStats(
        requested=len(requested),
        successful=len(histories),
        failed=failed,
        temporary_failures=failed,
        no_price_history=failed,
    )
    return histories, stats


def latest_average_volume(history: pd.DataFrame, ticker: str) -> float:
    try:
        frame = history[ticker] if isinstance(history.columns, pd.MultiIndex) else history
        volume = frame["Volume"].dropna()
    except (KeyError, TypeError):
        return np.nan

    if volume.empty:
        return np.nan
    return float(volume.tail(50).mean())


def latest_price_and_average_volume(frame: pd.DataFrame) -> tuple[float, float]:
    if frame.empty or "Close" not in frame.columns or "Volume" not in frame.columns:
        return np.nan, np.nan
    close = frame["Close"].dropna()
    volume = frame["Volume"].dropna()
    if close.empty or volume.empty:
        return np.nan, np.nan
    return float(close.iloc[-1]), float(volume.tail(50).mean())


def get_company_profile(ticker: str) -> tuple[float, str, str]:
    market_cap = np.nan
    sector = "Unknown"
    industry = "Unknown"

    try:
        ticker_data = yf.Ticker(ticker)
        fast_info = ticker_data.fast_info
        fast_market_cap = fast_info.get("market_cap")
        if fast_market_cap:
            market_cap = float(fast_market_cap)
    except Exception:
        pass

    try:
        info = yf.Ticker(ticker).get_info()
        info_market_cap = info.get("marketCap")
        if info_market_cap:
            market_cap = float(info_market_cap)
        sector = info.get("sector") or sector
        industry = info.get("industry") or industry
    except Exception:
        pass
    return market_cap, sector, industry


def build_raw_universe_to_path(path: str = UNIVERSE_RAW_TEMP_CSV) -> tuple[pd.DataFrame, int]:
    listed, total_downloaded = download_listed_tickers()
    raw = listed.rename(columns={"Yahoo Ticker": "Ticker"}).copy()
    raw = raw[["Ticker", "Symbol", "Security Name", "Exchange"]]
    raw.to_csv(path, index=False)
    return raw.reset_index(drop=True), total_downloaded


def build_universe_to_path(
    path: str,
    timer: RunTimer | None = None,
) -> tuple[pd.DataFrame, int, DownloadStats]:
    raw, total_downloaded = build_raw_universe_to_path(UNIVERSE_RAW_TEMP_CSV)
    print(f"Total tickers downloaded: {total_downloaded}")
    print(f"Raw common-stock symbols: {len(raw)}")
    rows = []
    ticker_map = raw.set_index("Ticker").to_dict("index")
    tickers = raw["Ticker"].tolist()

    print("Filtering universe by Yahoo Finance price and average volume...")
    histories, stats = download_price_histories(
        tickers,
        period="3mo",
        min_rows=20,
        timer=timer,
    )

    for ticker, frame in histories.items():
        price, avg_volume = latest_price_and_average_volume(frame)
        if (
            pd.isna(price)
            or pd.isna(avg_volume)
            or price < config.MIN_PRICE
            or avg_volume < config.MIN_AVG_VOLUME
        ):
            continue

        meta = ticker_map.get(ticker)
        if not meta:
            continue
        rows.append(
            {
                "Ticker": ticker,
                "Symbol": meta["Symbol"],
                "Security Name": meta["Security Name"],
                "Exchange": meta["Exchange"],
                "Sector": "Unknown",
                "Industry": "Unknown",
                "Market Cap": np.nan,
                "Avg Volume": int(avg_volume),
            }
        )

    universe = pd.DataFrame(rows, columns=UNIVERSE_COLUMNS)
    if not universe.empty:
        universe = universe.sort_values(["Avg Volume", "Ticker"], ascending=[False, True]).reset_index(drop=True)
    universe.to_csv(path, index=False)
    return universe, total_downloaded, stats


def backup_or_rename_existing_universe(universe_path: Path) -> bool:
    if not universe_path.exists():
        return False
    try:
        current_count = len(pd.read_csv(universe_path))
    except Exception:
        current_count = 0

    if current_count and current_count < config.MIN_VALID_UNIVERSE_COUNT:
        invalid_backup = Path(f"universe_invalid_{current_count}_backup.csv")
        suffix = 1
        while invalid_backup.exists():
            invalid_backup = Path(f"universe_invalid_{current_count}_backup_{suffix}.csv")
            suffix += 1
        shutil.move(str(universe_path), invalid_backup)
        return True

    shutil.copy2(universe_path, UNIVERSE_BACKUP_CSV)
    return True


def refresh_universe_cache(timer: RunTimer | None = None) -> tuple[pd.DataFrame, UniverseRefreshResult]:
    started_at = time.monotonic()
    temp_path = Path(UNIVERSE_TEMP_CSV)
    raw_temp_path = Path(UNIVERSE_RAW_TEMP_CSV)
    for candidate in [temp_path, raw_temp_path]:
        if candidate.exists():
            candidate.unlink()

    result = UniverseRefreshResult()
    try:
        universe, total_downloaded, download_stats = build_universe_to_path(UNIVERSE_TEMP_CSV, timer=timer)
        result.raw_symbols = total_downloaded
        result.filtered_symbols = len(universe)
        result.final_valid_symbols = len(universe)
        result.download_success_rate = download_stats.success_rate

        market_result = get_market_condition(timer=timer)
        result.spy_valid = market_result.spy_valid
        result.qqq_valid = market_result.qqq_valid

        valid, reason = validate_universe_frame(universe, download_stats.success_rate)
        if not (result.spy_valid and result.qqq_valid):
            valid = False
            reason = f"{reason} SPY/QQQ validation failed.".strip()
        if timer and timer.expired:
            valid = False
            reason = f"{reason} Runtime limit reached.".strip()

        if not valid:
            result.reason = reason or "Universe validation failed."
            result.fallback_used = True
            if temp_path.exists():
                temp_path.unlink()
            print("Universe refresh failed validation. Using last known good universe.")
            existing_path = Path(config.UNIVERSE_CSV)
            if existing_path.exists():
                return pd.read_csv(existing_path), result
            return pd.DataFrame(columns=UNIVERSE_COLUMNS), result

        universe_path = Path(config.UNIVERSE_CSV)
        result.backup_created = backup_or_rename_existing_universe(universe_path)
        shutil.move(str(temp_path), config.UNIVERSE_CSV)
        shutil.copy2(config.UNIVERSE_CSV, UNIVERSE_BACKUP_CSV)
        result.backup_created = True
        result.universe_replaced = True
        result.reason = "Universe refresh passed validation."
        return pd.read_csv(config.UNIVERSE_CSV), result
    except Exception:
        result.reason = "Universe source or price download failed."
        result.fallback_used = True
        if temp_path.exists():
            temp_path.unlink()
        print("Universe refresh failed validation. Using last known good universe.")
        existing_path = Path(config.UNIVERSE_CSV)
        if existing_path.exists():
            return pd.read_csv(existing_path), result
        return pd.DataFrame(columns=UNIVERSE_COLUMNS), result
    finally:
        result.runtime_seconds = time.monotonic() - started_at


def build_universe(timer: RunTimer | None = None) -> tuple[pd.DataFrame, int, bool]:
    universe, refresh_result = refresh_universe_cache(timer=timer)
    downloaded = refresh_result.raw_symbols or len(universe)
    return universe, downloaded, refresh_result.fallback_used


def validate_universe_frame(universe: pd.DataFrame, batch_success_rate: float | None = None) -> tuple[bool, str]:
    missing_columns = set(UNIVERSE_COLUMNS) - set(universe.columns)
    if missing_columns:
        return False, f"missing columns: {', '.join(sorted(missing_columns))}"
    if len(universe) < config.MIN_VALID_UNIVERSE_COUNT:
        return False, f"ticker count below {config.MIN_VALID_UNIVERSE_COUNT}"
    if universe["Ticker"].duplicated().any():
        return False, "duplicate tickers"
    if universe["Ticker"].isna().mean() > 0.05:
        return False, "Ticker column mostly empty"
    if batch_success_rate is not None and batch_success_rate < config.MIN_DOWNLOAD_SUCCESS_RATE:
        return False, "universe batch success rate below threshold"
    return True, ""


def universe_cache_age_days(path: Path) -> float:
    modified_at = datetime.fromtimestamp(path.stat().st_mtime)
    return (datetime.now() - modified_at).total_seconds() / 86_400


def should_rebuild_universe(path: Path) -> bool:
    if not path.exists():
        print(f"{config.UNIVERSE_CSV} not found. Building universe.")
        return True

    try:
        existing_columns = set(pd.read_csv(path, nrows=0).columns)
    except Exception:
        print(f"{config.UNIVERSE_CSV} could not be read. Rebuilding universe.")
        return True

    missing_columns = set(UNIVERSE_COLUMNS) - existing_columns
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        print(f"{config.UNIVERSE_CSV} is missing {missing}. Rebuilding universe.")
        return True

    age_days = universe_cache_age_days(path)
    if age_days >= config.UNIVERSE_REFRESH_DAYS:
        print(
            f"{config.UNIVERSE_CSV} is {age_days:.1f} days old. "
            "Refreshing universe."
        )
        return True

    print(
        f"Using cached {config.UNIVERSE_CSV} "
        f"({age_days:.1f} days old; refresh every {config.UNIVERSE_REFRESH_DAYS} days)."
    )
    return False


def load_universe(timer: RunTimer | None = None) -> UniverseLoadResult:
    universe_path = Path(config.UNIVERSE_CSV)
    total_downloaded = 0
    fallback_used = False
    built_universe: pd.DataFrame | None = None
    if should_rebuild_universe(universe_path):
        built_universe, total_downloaded, fallback_used = build_universe(timer=timer)

    if universe_path.exists():
        universe = pd.read_csv(universe_path)
    elif built_universe is not None:
        universe = built_universe
    else:
        universe = pd.DataFrame(columns=UNIVERSE_COLUMNS)
    total_after_filter = len(universe)
    if total_downloaded == 0:
        total_downloaded = total_after_filter
    print(f"Total tickers after universe filter: {total_after_filter}")
    return UniverseLoadResult(
        universe=universe,
        total_downloaded=total_downloaded,
        total_after_filter=total_after_filter,
        fallback_used=fallback_used,
        refresh_failed_validation=fallback_used,
    )


def load_history(tickers: list[str], timer: RunTimer | None = None) -> dict[str, pd.DataFrame]:
    histories, _ = download_price_histories(tickers, period="18mo", min_rows=1, timer=timer)
    return histories


def load_history_with_stats(
    tickers: list[str],
    timer: RunTimer | None = None,
) -> tuple[dict[str, pd.DataFrame], DownloadStats]:
    return download_price_histories(tickers, period="18mo", min_rows=1, timer=timer)


def moving_average_status(history: pd.DataFrame) -> dict[str, str]:
    if history.empty:
        return {"10EMA": "Unknown", "20EMA": "Unknown", "50MA": "Unknown"}

    df = history.copy()
    df["EMA10"] = df["Close"].ewm(span=10, adjust=False).mean()
    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["MA50"] = df["Close"].rolling(50).mean()
    latest = df.iloc[-1]

    statuses = {}
    for label, column in [("10EMA", "EMA10"), ("20EMA", "EMA20"), ("50MA", "MA50")]:
        if pd.isna(latest[column]):
            statuses[label] = "Unknown"
        else:
            statuses[label] = "Above" if latest["Close"] > latest[column] else "Below"
    return statuses


def is_valid_market_history(history: pd.DataFrame) -> bool:
    if history.empty or len(history["Close"].dropna()) < 50:
        return False
    statuses = moving_average_status(history)
    return all(value != "Unknown" for value in statuses.values())


def get_market_condition(
    timer: RunTimer | None = None,
    retry_delays: list[int] | None = None,
) -> MarketConditionResult:
    symbols = ["SPY", "QQQ"]
    histories = {}
    stats = DownloadStats(requested=len(symbols))
    delays = config.MARKET_RETRY_DELAYS_SECONDS if retry_delays is None else retry_delays
    for attempt, delay in enumerate([0] + delays):
        if timer and timer.expired:
            break
        if delay:
            if timer:
                timer.sleep(delay)
            else:
                time.sleep(delay)
        histories, stats = download_price_histories(
            symbols,
            period="18mo",
            min_rows=50,
            retry_delays=[],
            timer=timer,
        )
        if all(is_valid_market_history(histories.get(symbol, pd.DataFrame())) for symbol in symbols):
            break

    rows = []
    above_count = 0
    known_count = 0
    valid_by_symbol = {}

    for symbol in symbols:
        history = histories.get(symbol, pd.DataFrame())
        valid_by_symbol[symbol] = is_valid_market_history(history)
        statuses = moving_average_status(history)
        rows.append({"Symbol": symbol, **statuses})
        for value in statuses.values():
            if value == "Unknown":
                continue
            known_count += 1
            if value == "Above":
                above_count += 1

    if known_count == 0:
        status = "Unknown"
    elif above_count >= 5:
        status = "Strong"
    elif above_count >= 3:
        status = "Neutral"
    else:
        status = "Caution"

    spy_valid = valid_by_symbol.get("SPY", False)
    qqq_valid = valid_by_symbol.get("QQQ", False)
    return MarketConditionResult(
        frame=pd.DataFrame(rows, columns=MARKET_COLUMNS),
        status=status,
        spy_valid=spy_valid,
        qqq_valid=qqq_valid,
        data_failure=not (spy_valid or qqq_valid),
        stats=stats,
    )


def period_return(history: pd.DataFrame, trading_days: int) -> float:
    closes = history["Close"].dropna()
    if len(closes) <= trading_days:
        return np.nan
    return pct(closes.iloc[-1] - closes.iloc[-trading_days], closes.iloc[-trading_days])


def calculate_rs_scores(histories: dict[str, pd.DataFrame], tickers: list[str]) -> dict[str, int]:
    rows = []
    for ticker in tickers:
        history = histories.get(ticker)
        if history is None or history.empty:
            continue

        three_month = period_return(history, 63)
        six_month = period_return(history, 126)
        twelve_month = period_return(history, 252)
        if pd.isna(three_month) or pd.isna(six_month) or pd.isna(twelve_month):
            continue

        weighted_return = (
            three_month * 0.5
            + six_month * 0.3
            + twelve_month * 0.2
        )
        rows.append(
            {
                "Ticker": ticker,
                "RS Raw": weighted_return,
                "3M Return %": three_month,
                "6M Return %": six_month,
                "12M Return %": twelve_month,
            }
        )

    if not rows:
        return {}

    rs_frame = pd.DataFrame(rows).sort_values("RS Raw", ascending=False).reset_index(drop=True)
    count = len(rs_frame)
    scores = {}
    for index, row in rs_frame.iterrows():
        percentile_rank = ((index + 1) / count) * 100
        score = 100 - math.ceil(percentile_rank)
        scores[row["Ticker"]] = max(1, min(99, score))
    return scores


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    previous_close = df["Close"].shift(1)
    true_range = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - previous_close).abs(),
            (df["Low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["ATR20"] = true_range.rolling(20).mean()
    df["ATR20_PCT"] = (df["ATR20"] / df["Close"]) * 100
    df["EMA10"] = df["Close"].ewm(span=10, adjust=False).mean()
    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["MA50"] = df["Close"].rolling(50).mean()
    df["MA150"] = df["Close"].rolling(150).mean()
    df["MA200"] = df["Close"].rolling(200).mean()
    df["MA200_20D_AGO"] = df["MA200"].shift(20)
    df["AVG_VOLUME50"] = df["Volume"].rolling(50).mean()
    df["HIGH_52W"] = df["High"].rolling(252, min_periods=120).max()
    df["LOW_52W"] = df["Low"].rolling(252, min_periods=120).min()
    df["RANGE_10D_PCT"] = (
        (df["High"].rolling(10).max() - df["Low"].rolling(10).min())
        / df["Close"]
    ) * 100
    df["RANGE_15D_PCT"] = (
        (df["High"].rolling(15).max() - df["Low"].rolling(15).min())
        / df["Close"]
    ) * 100
    df["RANGE_20D_PCT"] = (
        (df["High"].rolling(20).max() - df["Low"].rolling(20).min())
        / df["Close"]
    ) * 100
    daily_range_pct = ((df["High"] / df["Low"]) - 1) * 100
    df["ADR_PCT"] = daily_range_pct.rolling(20).mean()
    df["ADR60_PCT"] = daily_range_pct.rolling(60).mean()
    df["HIGH_50D_PRIOR"] = df["High"].shift(1).rolling(50).max()
    df["PRIOR_VOLUME"] = df["Volume"].shift(1)
    df["VOLUME_RATIO"] = df["Volume"] / df["AVG_VOLUME50"]
    df["DAILY_RANGE"] = (df["High"] - df["Low"]).replace(0, np.nan)
    df["BODY_PCT"] = (abs(df["Close"] - df["Open"]) / df["DAILY_RANGE"]) * 100
    df["CLOSE_POSITION_PCT"] = ((df["Close"] - df["Low"]) / df["DAILY_RANGE"]) * 100
    df["DIST_EMA10_ATR"] = (df["Close"] - df["EMA10"]).abs() / df["ATR20"]
    df["DIST_EMA20_ATR"] = (df["Close"] - df["EMA20"]).abs() / df["ATR20"]
    df["DIST_MA50_ATR"] = (df["Close"] - df["MA50"]).abs() / df["ATR20"]
    df["DIST_30WMA_ATR"] = (df["Close"] - df["MA150"]).abs() / df["ATR20"]
    df["BULLISH_POWER_CANDLE"] = (
        (df["Close"] > df["Open"])
        & (df["BODY_PCT"] >= 50)
        & (df["CLOSE_POSITION_PCT"] >= 75)
        & (df["VOLUME_RATIO"] >= 1.2)
    )
    df["BULLISH_REVERSAL_CANDLE"] = (
        (df["Close"] > df["Open"])
        & ((df["Close"] > df["High"].shift(1)) | (df["CLOSE_POSITION_PCT"] >= 60))
        & ((df["Volume"] > df["Volume"].shift(1)) | (df["VOLUME_RATIO"] >= 0.8))
    )
    df["PIVOT_PRICE"] = df["HIGH_50D_PRIOR"].ffill()
    breakout_price = (df["Close"] > df["HIGH_50D_PRIOR"]) | (df["Close"] > df["PIVOT_PRICE"])
    breakout_volume = df["VOLUME_RATIO"] >= 1.5
    df["BREAKOUT_CONFIRMED_5D"] = (breakout_price & breakout_volume).rolling(5).max().fillna(False)
    df["PIVOT_PRICE"] = df["HIGH_50D_PRIOR"].where(breakout_price).ffill()
    df["PIVOT_PRICE"] = df["PIVOT_PRICE"].fillna(df["HIGH_50D_PRIOR"])

    close_above_prior_high = df["Close"] > df["High"].shift(1)
    top_quarter_close = df["CLOSE_POSITION_PCT"] >= 75
    ema10_reclaim = (df["Low"] <= df["EMA10"]) & (df["Close"] > df["EMA10"])
    ema20_reclaim = (df["Low"] <= df["EMA20"]) & (df["Close"] > df["EMA20"])
    ma50_reclaim = (df["Low"] <= df["MA50"]) & (df["Close"] > df["MA50"])
    df["SUPPORT_SIGNAL_10EMA_BOOL"] = (
        close_above_prior_high | top_quarter_close | ema10_reclaim
    ).rolling(3).max().fillna(False).astype(bool)
    df["SUPPORT_SIGNAL_20EMA_BOOL"] = (
        close_above_prior_high | top_quarter_close | ema20_reclaim
    ).rolling(3).max().fillna(False).astype(bool)
    df["SUPPORT_SIGNAL_50MA_BOOL"] = (
        close_above_prior_high | top_quarter_close | ma50_reclaim
    ).rolling(3).max().fillna(False).astype(bool)
    df["SUPPORT_SIGNAL_10EMA"] = np.select(
        [ema10_reclaim, close_above_prior_high, top_quarter_close],
        ["EMA10 reclaim", "Close above prior high", "Top-25% close"],
        default="Recent support",
    )
    df["SUPPORT_SIGNAL_20EMA"] = np.select(
        [ema20_reclaim, close_above_prior_high, top_quarter_close],
        ["EMA20 reclaim", "Close above prior high", "Top-25% close"],
        default="Recent support",
    )
    df["SUPPORT_SIGNAL_50MA"] = np.select(
        [ma50_reclaim, close_above_prior_high, top_quarter_close],
        ["50MA reclaim", "Close above prior high", "Top-25% close"],
        default="Recent support",
    )
    return df


def passes_filters(row: pd.Series) -> bool:
    required = [
        "Close", "AVG_VOLUME50", "MA50", "MA150", "MA200", "MA200_20D_AGO",
        "HIGH_52W", "EMA10", "EMA20", "ADR_PCT", "ATR20",
    ]
    if row[required].isna().any():
        return False

    distance_from_high = pct(row["HIGH_52W"] - row["Close"], row["HIGH_52W"])
    above_10ema = pct(row["Close"] - row["EMA10"], row["EMA10"])
    above_20ema = pct(row["Close"] - row["EMA20"], row["EMA20"])

    return all(
        [
            row["Close"] > config.MIN_PRICE,
            row["AVG_VOLUME50"] > config.MIN_AVG_VOLUME,
            row["Close"] > row["MA50"],
            row["MA50"] > row["MA150"],
            row["MA150"] > row["MA200"],
            row["MA200"] > row["MA200_20D_AGO"],
            distance_from_high <= config.MAX_DISTANCE_FROM_HIGH_PCT,
            config.MIN_ADR_PCT <= row["ADR_PCT"] <= config.MAX_ADR_PCT,
            above_10ema <= config.MAX_ABOVE_10EMA_PCT,
            above_20ema <= config.MAX_ABOVE_20EMA_PCT,
        ]
    )


def candidate_row(
    ticker: str,
    latest: pd.Series,
    rs_score: int | None,
    profile: dict,
) -> dict:
    volume_ratio = latest["Volume"] / latest["AVG_VOLUME50"]
    distance_50ma = pct(latest["Close"] - latest["MA50"], latest["MA50"])
    distance_30wma = pct(latest["Close"] - latest["MA150"], latest["MA150"])
    distance_pivot = pct(latest["Close"] - latest["PIVOT_PRICE"], latest["PIVOT_PRICE"])
    distance_ema10_atr = latest["DIST_EMA10_ATR"]
    distance_ema20_atr = latest["DIST_EMA20_ATR"]
    distance_50ma_atr = latest["DIST_MA50_ATR"]
    distance_30wma_atr = latest["DIST_30WMA_ATR"]
    nearest_support_atr = min(distance_ema10_atr, distance_ema20_atr, distance_50ma_atr)
    status = extension_status(distance_50ma_atr)
    range_10d = latest["RANGE_10D_PCT"]
    adr20 = latest["ADR_PCT"]
    adr60 = latest["ADR60_PCT"]
    vcp_ratio = adr20 / adr60 if not pd.isna(adr60) and adr60 != 0 else np.nan
    quality = pullback_quality(distance_50ma_atr, distance_30wma_atr)
    support_signal = strongest_support_signal(latest)
    return {
        "Category": "",
        "Ticker": ticker,
        "Sector": profile.get("Sector", "Unknown"),
        "Industry": profile.get("Industry", "Unknown"),
        "RS Score": rs_score,
        "Price": round(latest["Close"], 2),
        "Action": "",
        "ATR20": round(latest["ATR20"], 2),
        "ATR20 %": round(latest["ATR20_PCT"], 2),
        "ADR %": round(latest["ADR_PCT"], 2),
        "From 52W High %": round(pct(latest["Close"] - latest["HIGH_52W"], latest["HIGH_52W"]), 2),
        "Distance From 50MA %": round(distance_50ma, 2),
        "Distance From 30WMA %": round(distance_30wma, 2),
        "Distance From Pivot %": round(distance_pivot, 2),
        "Volume Ratio": round(volume_ratio, 2),
        "Distance From EMA10 ATR": round(distance_ema10_atr, 2),
        "Distance From EMA20 ATR": round(distance_ema20_atr, 2),
        "Distance From MA50 ATR": round(distance_50ma_atr, 2),
        "Distance From 30WMA ATR": round(distance_30wma_atr, 2),
        "Nearest Support Distance ATR": round(nearest_support_atr, 2),
        "Support Signal": support_signal,
        "10 Day Range %": round(range_10d, 2),
        "20 Day Range %": round(latest["RANGE_20D_PCT"], 2),
        "Tightness Score": round(100 - range_10d, 2),
        "Tightness Label": tightness_label(range_10d),
        "ADR20 %": round(adr20, 2),
        "ADR60 %": round(adr60, 2),
        "VCP Ratio": round(vcp_ratio, 2),
        "VCP Label": vcp_label(vcp_ratio),
        "Pullback Quality": pullback_quality_label(quality),
        "Extension Status": status,
        "Risk/Reward Quality": risk_reward_quality(nearest_support_atr, status),
        "Industry Rank": np.nan,
        "Avg Volume": int(latest["AVG_VOLUME50"]),
        "TradingView": tradingview_url(profile.get("Exchange", "NASDAQ"), ticker),
    }


def strongest_support_signal(latest: pd.Series) -> str:
    """Summarise the nearest constructive support signal for compact AI review."""
    signals = [
        latest.get("SUPPORT_SIGNAL_10EMA", ""),
        latest.get("SUPPORT_SIGNAL_20EMA", ""),
        latest.get("SUPPORT_SIGNAL_50MA", ""),
    ]
    return ", ".join(signal for signal in signals if signal) or ""


def is_breakout_candidate(row: pd.Series) -> bool:
    breakout = row["Close"] > row["HIGH_50D_PRIOR"] or row["Close"] > row["PIVOT_PRICE"]
    near_pivot = row["Close"] >= row["PIVOT_PRICE"] * 0.97 or row["Close"] >= row["HIGH_50D_PRIOR"] * 0.97
    distance_50ma = pct(row["Close"] - row["MA50"], row["MA50"])
    distance_30wma = pct(row["Close"] - row["MA150"], row["MA150"])
    controlled_extension = distance_50ma <= 8 or distance_30wma <= 15
    constructive_candle = (
        row["Close"] > row["Open"]
        and row["CLOSE_POSITION_PCT"] >= 60
        and row["BODY_PCT"] >= 25
    )
    return (breakout or near_pivot) and constructive_candle and row["VOLUME_RATIO"] >= 0.9 and controlled_extension


def is_extended_breakout_candidate(row: pd.Series) -> bool:
    breakout = row["Close"] > row["HIGH_50D_PRIOR"] or row["Close"] > row["PIVOT_PRICE"]
    near_pivot = row["Close"] >= row["PIVOT_PRICE"] * 0.97 or row["Close"] >= row["HIGH_50D_PRIOR"] * 0.97
    distance_50ma = pct(row["Close"] - row["MA50"], row["MA50"])
    distance_30wma = pct(row["Close"] - row["MA150"], row["MA150"])
    too_extended = distance_50ma > 8 and distance_30wma > 15
    constructive_candle = (
        row["Close"] > row["Open"]
        and row["CLOSE_POSITION_PCT"] >= 60
        and row["BODY_PCT"] >= 25
    )
    return (breakout or near_pivot) and constructive_candle and row["VOLUME_RATIO"] >= 0.9 and too_extended


def moving_average_pullback_quality(row: pd.Series) -> str:
    return pullback_quality(row["DIST_MA50_ATR"], row["DIST_30WMA_ATR"])


def is_near_key_moving_average(row: pd.Series) -> bool:
    close = row["Close"]
    near_10ema = close >= row["EMA10"] and row["DIST_EMA10_ATR"] <= 1.0
    near_20ema = close >= row["EMA20"] and row["DIST_EMA20_ATR"] <= 1.5
    near_50ma = close >= row["MA50"] and row["DIST_MA50_ATR"] <= 2.0
    return near_10ema or near_20ema or near_50ma


def is_pullback_candidate(row: pd.Series) -> bool:
    return (
        is_near_key_moving_average(row)
        and moving_average_pullback_quality(row) in {"A", "B"}
        and row["VOLUME_RATIO"] <= 1.5
    )


def is_extended_candidate(row: pd.Series) -> bool:
    status = extension_status(row["DIST_MA50_ATR"])
    return (
        (
            is_near_key_moving_average(row)
            and moving_average_pullback_quality(row) in {"C", "D"}
        )
        or status in {"Extended", "Overextended"}
        or row["DIST_30WMA_ATR"] > 10
    )


def is_tight_consolidation_candidate(row: pd.Series) -> bool:
    if pd.isna(row.get("RANGE_15D_PCT")):
        return False
    return (
        row["RANGE_15D_PCT"] <= 18
        and pct(row["HIGH_52W"] - row["Close"], row["HIGH_52W"]) <= 25
        and pct(row["Close"] - row["MA50"], row["MA50"]) <= 25
        and row["VOLUME_RATIO"] <= 1.4
    )


def is_volume_surge_candidate(row: pd.Series) -> bool:
    return (
        row["VOLUME_RATIO"] >= 1.5
        and row["Close"] > row["Open"]
        and row["CLOSE_POSITION_PCT"] >= 60
        and pct(row["HIGH_52W"] - row["Close"], row["HIGH_52W"]) <= 20
    )


def action_for_row(row: pd.Series | dict) -> str:
    category = row.get("Category", "")
    risk_reward = row.get("Risk/Reward Quality", "")
    extension = row.get("Extension Status", "")
    vcp = row.get("VCP Label", "")
    tightness = row.get("Tightness Label", "")

    if category == "Pullback Candidates":
        if risk_reward == "Excellent R/R" and extension == "Not Extended":
            return "Review for pullback entry"
        if risk_reward == "Good R/R":
            return "Watch for confirmation"
        return "Watch only"
    if category == "Tight Consolidation Candidates":
        if vcp in {"Excellent VCP", "Good VCP"}:
            return "Set pivot alert"
        if tightness in {"Very Tight", "Tight"}:
            return "Monitor tight base"
        return "Watch only"
    if category == "Extended Candidates":
        if risk_reward == "Poor R/R" or extension in {"Extended", "Overextended"}:
            return "Wait for pullback"
        return "Watch only"
    return ""


def add_action_column(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    updated = frame.copy()
    updated["Action"] = updated.apply(action_for_row, axis=1)
    return updated


def category_sort(df: pd.DataFrame, category: str) -> pd.DataFrame:
    frame = df.copy()
    if category == "Breakout Candidates":
        return (
            frame
            .sort_values(
                ["RS Score", "Volume Ratio", "Avg Volume", "From 52W High %"],
                ascending=[False, False, False, True],
            )
            .head(config.CATEGORY_LIMIT)
            .reset_index(drop=True)
        )
    elif category == "Pullback Candidates":
        frame["_Quality Rank"] = frame["Pullback Quality"].apply(pullback_quality_rank).replace(0, 99)
        return (
            frame
            .sort_values(
                ["_Quality Rank", "RS Score", "Distance From 50MA %", "Avg Volume"],
                ascending=[True, False, True, False],
            )
            .drop(columns=["_Quality Rank"])
            .head(config.CATEGORY_LIMIT)
            .reset_index(drop=True)
        )
    elif category == "Tight Consolidation Candidates":
        vcp_rank = {
            "Excellent VCP": 1,
            "Good VCP": 2,
            "Average VCP": 3,
            "Poor VCP": 4,
        }
        tightness_rank = {
            "Very Tight": 1,
            "Tight": 2,
            "Normal": 3,
            "Loose": 4,
        }
        frame["_Risk Reward Rank"] = frame["Risk/Reward Quality"].apply(risk_reward_quality_rank)
        frame["_Extension Rank"] = frame["Extension Status"].apply(extension_status_rank)
        frame["_VCP Rank"] = frame["VCP Label"].map(vcp_rank).fillna(99)
        frame["_Tightness Rank"] = frame["Tightness Label"].map(tightness_rank).fillna(99)
        return (
            frame
            .sort_values(
                [
                    "_Risk Reward Rank", "_Extension Rank",
                    "Nearest Support Distance ATR", "_VCP Rank",
                    "_Tightness Rank", "RS Score", "VCP Ratio",
                ],
                ascending=[True, True, True, True, True, False, True],
            )
            .drop(columns=["_Risk Reward Rank", "_Extension Rank", "_VCP Rank", "_Tightness Rank"])
            .head(config.CATEGORY_LIMIT)
            .reset_index(drop=True)
        )
    elif category == "Extended Candidates":
        frame["_Industry Rank"] = frame["Industry Rank"].fillna(999)
        return (
            frame
            .sort_values(
                ["RS Score", "_Industry Rank", "Distance From 50MA %", "Avg Volume"],
                ascending=[False, True, True, False],
            )
            .drop(columns=["_Industry Rank"])
            .head(config.CATEGORY_LIMIT)
            .reset_index(drop=True)
        )

    return (
        frame
        .sort_values(
            ["RS Score", "Volume Ratio", "Avg Volume", "From 52W High %"],
            ascending=[False, False, False, True],
        )
        .head(config.CATEGORY_LIMIT)
        .reset_index(drop=True)
    )


def build_top_industries(base_df: pd.DataFrame) -> pd.DataFrame:
    if base_df.empty:
        return pd.DataFrame(columns=TOP_INDUSTRY_COLUMNS)

    rows = []
    for industry, group in base_df.groupby("Industry", dropna=False):
        candidate_count = len(group)
        avg_rs_score = round(group["RS Score"].mean(), 1)
        strength_score = round((avg_rs_score * 0.7) + (min(candidate_count, 20) * 1.5), 1)
        leaders = (
            group.sort_values(["RS Score", "Avg Volume"], ascending=[False, False])
            .head(3)["Ticker"]
            .tolist()
        )
        rows.append(
            {
                "Industry": industry,
                "Sector": group["Sector"].mode().iloc[0] if not group["Sector"].mode().empty else "Unknown",
                "Industry Strength Score": strength_score,
                "Candidate Count": candidate_count,
                "Avg RS Score": avg_rs_score,
                "Best RS Score": int(group["RS Score"].max()),
                "Top 3 Leaders": ", ".join(leaders),
            }
        )

    return (
        pd.DataFrame(rows, columns=TOP_INDUSTRY_COLUMNS)
        .sort_values(
            ["Industry Strength Score", "Avg RS Score", "Candidate Count"],
            ascending=[False, False, False],
        )
        .head(config.CATEGORY_LIMIT)
        .reset_index(drop=True)
    )


def add_industry_ranks(base_df: pd.DataFrame) -> pd.DataFrame:
    industry_scores = (
        base_df
        .groupby("Industry", dropna=False)
        .agg({"RS Score": "mean", "Ticker": "count"})
        .rename(columns={"RS Score": "Avg RS Score", "Ticker": "Candidates"})
        .sort_values(["Avg RS Score", "Candidates"], ascending=[False, False])
    )
    ranks = {industry: rank for rank, industry in enumerate(industry_scores.index, start=1)}
    ranked = base_df.copy()
    ranked["Industry Rank"] = ranked["Industry"].map(ranks)
    return ranked


def screen_stocks(
    universe: pd.DataFrame,
    timer: RunTimer | None = None,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, int, DownloadStats]:
    tickers = universe["Ticker"].tolist() if not universe.empty else []
    profiles = universe.set_index("Ticker")[["Exchange", "Sector", "Industry"]].to_dict("index")
    histories, download_stats = load_history_with_stats(tickers, timer=timer)
    stage2_tickers = []
    latest_by_ticker = {}
    for ticker, history in histories.items():
        if len(history) < 220:
            continue
        try:
            latest = add_indicators(history).iloc[-1]
        except Exception as exc:
            print(f"Skipping {ticker}: {exc}")
            continue
        if passes_filters(latest):
            stage2_tickers.append(ticker)
            latest_by_ticker[ticker] = latest

    rs_scores = calculate_rs_scores(histories, stage2_tickers)
    base_rows = []
    stage2_count = len(stage2_tickers)
    for ticker in stage2_tickers:
        rs_score = rs_scores.get(ticker)
        if rs_score is None or rs_score < config.MIN_RS_SCORE:
            continue
        base_rows.append(
            candidate_row(
                ticker,
                latest_by_ticker[ticker],
                rs_score,
                profiles.get(ticker, {}),
            )
        )

    if not base_rows:
        empty_categories = {name: pd.DataFrame(columns=DISCOVERY_COLUMNS) for name in CATEGORY_NAMES}
        return empty_categories, pd.DataFrame(columns=TOP_INDUSTRY_COLUMNS), stage2_count, download_stats

    base_df = add_industry_ranks(pd.DataFrame(base_rows, columns=DISCOVERY_COLUMNS))
    categories = {name: [] for name in CATEGORY_NAMES}
    for ticker in stage2_tickers:
        if ticker not in latest_by_ticker or ticker not in rs_scores or rs_scores[ticker] < config.MIN_RS_SCORE:
            continue
        latest = latest_by_ticker[ticker]
        row = base_df[base_df["Ticker"] == ticker].iloc[0].to_dict()
        if is_breakout_candidate(latest):
            categories["Breakout Candidates"].append({**row, "Category": "Breakout Candidates"})
        if is_pullback_candidate(latest):
            categories["Pullback Candidates"].append({**row, "Category": "Pullback Candidates"})
        if is_tight_consolidation_candidate(latest):
            categories["Tight Consolidation Candidates"].append({**row, "Category": "Tight Consolidation Candidates"})
        if is_extended_candidate(latest):
            categories["Extended Candidates"].append({**row, "Category": "Extended Candidates"})
        if is_volume_surge_candidate(latest):
            categories["Volume Surge Candidates"].append({**row, "Category": "Volume Surge Candidates"})

    category_frames = {}
    for name, rows in categories.items():
        frame = pd.DataFrame(rows, columns=DISCOVERY_COLUMNS)
        category_frames[name] = add_action_column(category_sort(frame, name)) if not frame.empty else frame

    top_industries = build_top_industries(base_df)
    return category_frames, top_industries, stage2_count, download_stats


def markdown_table(df: pd.DataFrame) -> str:
    table = df.copy()
    if "TradingView" in table.columns:
        table["TradingView"] = table["TradingView"].apply(lambda url: f"[Chart]({url})")
    return table.to_markdown(index=False)


def html_table(df: pd.DataFrame) -> str:
    table = df.copy()
    if "TradingView" in table.columns:
        table["TradingView"] = table["TradingView"].apply(
            lambda url: f'<a href="{url}" target="_blank">Chart</a>'
        )
    return table.to_html(index=False, escape=False)


def combined_watchlist(categories: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = [frame for frame in categories.values() if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=DISCOVERY_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def dedupe_categories_by_priority(categories: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    deduped = {}
    assigned_tickers = set()
    for name in CATEGORY_PRIORITY:
        frame = categories.get(name, pd.DataFrame(columns=DISCOVERY_COLUMNS))
        if frame.empty:
            deduped[name] = pd.DataFrame(columns=DISCOVERY_COLUMNS)
            continue

        unique = frame[~frame["Ticker"].isin(assigned_tickers)].drop_duplicates("Ticker").copy()
        assigned_tickers.update(unique["Ticker"].tolist())
        deduped[name] = unique.reset_index(drop=True)
    return deduped


def sort_daily_focus(focus: pd.DataFrame) -> pd.DataFrame:
    if focus.empty:
        return focus

    sorted_focus = focus.copy()
    sorted_focus["_Category Rank"] = sorted_focus["Category"].apply(category_priority_rank)
    sorted_focus["_Risk Reward Rank"] = sorted_focus["Risk/Reward Quality"].apply(risk_reward_quality_rank)
    sorted_focus["_Industry Rank Sort"] = sorted_focus["Industry Rank"].fillna(999)
    return (
        sorted_focus
        .sort_values(
            ["_Category Rank", "_Risk Reward Rank", "RS Score", "_Industry Rank Sort"],
            ascending=[True, True, False, True],
        )
        .drop(columns=["_Category Rank", "_Risk Reward Rank", "_Industry Rank Sort"])
        .head(DAILY_FOCUS_MAX)
        .reset_index(drop=True)
    )


def extended_focus_filter(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    return frame[
        (frame["RS Score"] >= 90)
        & (frame["Industry Rank"] <= 15)
        & (frame["Risk/Reward Quality"] != "Poor R/R")
    ].copy()


def build_daily_focus_list(categories: dict[str, pd.DataFrame]) -> pd.DataFrame:
    focus_frames = []
    for name in CATEGORY_PRIORITY:
        frame = categories.get(name, pd.DataFrame(columns=DISCOVERY_COLUMNS))
        if frame.empty:
            continue
        if name == "Extended Candidates":
            frame = extended_focus_filter(frame)
        focus_frames.append(frame.head(FOCUS_LIMITS[name]))

    if not focus_frames:
        return pd.DataFrame(columns=DISCOVERY_COLUMNS)
    return sort_daily_focus(pd.concat(focus_frames, ignore_index=True))


def sort_top_action_list(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    category_rank = {
        "Pullback Candidates": 1,
        "Tight Consolidation Candidates": 2,
        "Extended Candidates": 3,
    }
    sorted_frame = frame.copy()
    sorted_frame["_Category Rank"] = sorted_frame["Category"].map(category_rank).fillna(99)
    sorted_frame["_Risk Reward Rank"] = sorted_frame["Risk/Reward Quality"].apply(risk_reward_quality_rank)
    sorted_frame["_Industry Rank Sort"] = sorted_frame["Industry Rank"].fillna(999)
    return (
        sorted_frame
        .sort_values(
            ["_Category Rank", "_Risk Reward Rank", "RS Score", "_Industry Rank Sort"],
            ascending=[True, True, False, True],
        )
        .drop(columns=["_Category Rank", "_Risk Reward Rank", "_Industry Rank Sort"])
        .head(TOP_ACTION_MAX)
        .reset_index(drop=True)
    )


def build_top_action_list(categories: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = []
    pullbacks = categories.get("Pullback Candidates", pd.DataFrame(columns=DISCOVERY_COLUMNS))
    tight = categories.get("Tight Consolidation Candidates", pd.DataFrame(columns=DISCOVERY_COLUMNS))
    if not pullbacks.empty:
        frames.append(pullbacks.head(5))
    if not tight.empty:
        frames.append(tight.head(3))

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=DISCOVERY_COLUMNS)
    if len(combined) < TOP_ACTION_MAX:
        extended = categories.get("Extended Candidates", pd.DataFrame(columns=DISCOVERY_COLUMNS))
        if not extended.empty:
            need = TOP_ACTION_MAX - len(combined)
            frames.append(extended.head(need))
            combined = pd.concat(frames, ignore_index=True)
    return sort_top_action_list(combined)


def write_email_summary(
    top_action_list: pd.DataFrame,
    daily_focus: pd.DataFrame,
    top_industries: pd.DataFrame,
    market_status: str,
    ai_commentary: str,
    path: str,
) -> None:
    lines = [
        "Daily US Stock Watchlist",
        "",
        "Market Status",
        f"{market_status}",
        "",
        "Top 5 Industries",
    ]
    if top_industries.empty:
        lines.append("No industry groups matched.")
    else:
        for index, row in top_industries.head(5).reset_index(drop=True).iterrows():
            lines.append(
                f"{index + 1}. {row['Industry']} ({row['Sector']}) - "
                f"Strength {row['Industry Strength Score']}"
            )

    lines.extend(["", "Top Action List"])
    if top_action_list.empty:
        lines.append("No action tickers.")
    else:
        for _, row in top_action_list.iterrows():
            lines.append(f"{row['Ticker']} - {row['Action']}")

    lines.extend(["", "AI Commentary", ai_commentary])
    lines.extend(["", "Full daily_watchlist.html is attached."])
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def write_markdown(
    top_action_list: pd.DataFrame,
    daily_focus: pd.DataFrame,
    categories: dict[str, pd.DataFrame],
    top_industries: pd.DataFrame,
    market_df: pd.DataFrame,
    market_status: str,
    ai_commentary: str,
    path: str,
) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Daily Watchlist",
        "",
        f"Generated: {now}",
        "",
        "## Top Action List",
        "",
    ]
    if top_action_list.empty:
        lines.extend(["No action tickers.", ""])
    else:
        lines.extend([markdown_table(top_action_list), ""])

    lines.extend(["## AI Commentary", "", ai_commentary, ""])

    lines.extend([
        "## Daily Focus List",
        "",
    ])
    if daily_focus.empty:
        lines.extend(["No focus tickers.", ""])
    else:
        lines.extend([markdown_table(daily_focus), ""])

    lines.extend([
        "## Market Status",
        "",
        f"Status: {market_status}",
        "",
        market_df.to_markdown(index=False),
        "",
    ])

    for name in CATEGORY_PRIORITY:
        frame = categories.get(name, pd.DataFrame(columns=DISCOVERY_COLUMNS))
        lines.extend([f"## {name}", ""])
        if frame.empty:
            lines.extend(["No matches.", ""])
        else:
            lines.extend([markdown_table(frame), ""])

    lines.extend(["## Top Industries", ""])
    if top_industries.empty:
        lines.extend(["No industry groups matched.", ""])
    else:
        lines.extend([top_industries.to_markdown(index=False), ""])
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def write_html(
    top_action_list: pd.DataFrame,
    daily_focus: pd.DataFrame,
    categories: dict[str, pd.DataFrame],
    top_industries: pd.DataFrame,
    market_df: pd.DataFrame,
    market_status: str,
    ai_commentary: str,
    path: str,
) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    sections = []
    action_table = "<p>No action tickers.</p>" if top_action_list.empty else html_table(top_action_list)
    sections.append(f"<h2>Top Action List</h2>{action_table}")
    sections.append(f"<h2>AI Commentary</h2><pre>{escape(ai_commentary)}</pre>")
    sections.append(
        f"<h2>Market Status</h2><p>Status: {market_status}</p>{market_df.to_html(index=False)}"
    )
    industry_table = "<p>No industry groups matched.</p>" if top_industries.empty else top_industries.to_html(index=False)
    sections.append(f"<h2>Top Industries</h2>{industry_table}")
    focus_table = "<p>No focus tickers.</p>" if daily_focus.empty else html_table(daily_focus)
    sections.append(f"<h2>Daily Focus List</h2>{focus_table}")
    html_order = [
        "Breakout Candidates",
        "Volume Surge Candidates",
        "Pullback Candidates",
        "Tight Consolidation Candidates",
        "Extended Candidates",
    ]
    for name in html_order:
        frame = categories.get(name, pd.DataFrame(columns=DISCOVERY_COLUMNS))
        table = "<p>No matches.</p>" if frame.empty else html_table(frame)
        sections.append(f"<h2>{name}</h2>{table}")

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Daily Watchlist</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #222; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 28px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: right; }}
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2), th:nth-child(3), td:nth-child(3) {{ text-align: left; }}
    th {{ background: #f3f5f7; }}
    pre {{ white-space: pre-wrap; background: #f7f7f7; border: 1px solid #ddd; padding: 16px; }}
  </style>
</head>
<body>
  <h1>Daily Watchlist</h1>
  <p>Generated: {now}</p>
  {''.join(sections)}
</body>
</html>
"""
    Path(path).write_text(html, encoding="utf-8")


def save_last_good_reports() -> None:
    report_pairs = [
        (OUTPUT_CSV, LAST_GOOD_CSV),
        (OUTPUT_MD, LAST_GOOD_MD),
        (OUTPUT_HTML, LAST_GOOD_HTML),
    ]
    for source, target in report_pairs:
        source_path = Path(source)
        if source_path.exists():
            shutil.copy2(source_path, target)


def validate_run_quality(
    universe_result: UniverseLoadResult,
    market_result: MarketConditionResult,
    download_stats: DownloadStats,
    timer: RunTimer | None = None,
) -> RunQualityResult:
    reasons = []
    if universe_result.total_after_filter < config.MIN_VALID_UNIVERSE_COUNT:
        reasons.append("Universe count below minimum valid threshold.")
    if not (market_result.spy_valid or market_result.qqq_valid):
        reasons.append("SPY and QQQ market data unavailable.")
    if download_stats.success_rate < config.MIN_DOWNLOAD_SUCCESS_RATE:
        reasons.append("Price download success rate below threshold.")
    if timer and timer.expired:
        reasons.append("Maximum screener runtime reached.")

    return RunQualityResult(
        valid=not reasons,
        reason=" ".join(reasons) if reasons else "Run passed data validation.",
        universe_count=universe_result.total_after_filter,
        requested_tickers=download_stats.requested,
        successful_downloads=download_stats.successful,
        failed_downloads=download_stats.failed,
        success_rate=download_stats.success_rate,
        spy_valid=market_result.spy_valid,
        qqq_valid=market_result.qqq_valid,
        fallback_used=universe_result.fallback_used,
    )


def write_data_failure_report(run_quality: RunQualityResult) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "Stock Screener Data Failure",
        "",
        f"Date and time: {now}",
        f"Requested ticker count: {run_quality.requested_tickers}",
        f"Successful ticker count: {run_quality.successful_downloads}",
        f"Failed ticker count: {run_quality.failed_downloads}",
        f"Success rate: {run_quality.success_rate:.1%}",
        f"SPY loaded: {run_quality.spy_valid}",
        f"QQQ loaded: {run_quality.qqq_valid}",
        f"Reason rejected: {run_quality.reason}",
    ]
    Path(DATA_FAILURE_REPORT).write_text("\n".join(lines), encoding="utf-8")


def print_data_quality_check(run_quality: RunQualityResult) -> None:
    print("\nData Quality Check")
    print(f"Universe Count: {run_quality.universe_count}")
    print(f"Requested Tickers: {run_quality.requested_tickers}")
    print(f"Successful Downloads: {run_quality.successful_downloads}")
    print(f"Failed Downloads: {run_quality.failed_downloads}")
    print(f"Download Success Rate: {run_quality.success_rate:.1%}")
    print(f"SPY Valid: {run_quality.spy_valid}")
    print(f"QQQ Valid: {run_quality.qqq_valid}")
    print(f"Run Valid: {run_quality.valid}")
    print(f"Fallback Used: {run_quality.fallback_used}")


def export_results(
    categories: dict[str, pd.DataFrame],
    top_industries: pd.DataFrame,
    market_df: pd.DataFrame,
    market_status: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame], AIAnalysisResult]:
    categories = dedupe_categories_by_priority(categories)
    categories = {name: add_action_column(frame) for name, frame in categories.items()}
    top_action_list = build_top_action_list(categories)
    daily_focus = build_daily_focus_list(categories)
    ai_result = analyse_top_action_list(top_action_list, top_industries, market_status)
    top_action_list = ai_result.top_action_list
    ai_commentary = ai_result.commentary
    watchlist = combined_watchlist(categories)
    watchlist.to_csv(OUTPUT_CSV, index=False)
    write_markdown(top_action_list, daily_focus, categories, top_industries, market_df, market_status, ai_commentary, OUTPUT_MD)
    write_html(top_action_list, daily_focus, categories, top_industries, market_df, market_status, ai_commentary, OUTPUT_HTML)
    write_email_summary(top_action_list, daily_focus, top_industries, market_status, ai_commentary, EMAIL_SUMMARY)
    save_last_good_reports()
    return watchlist, top_action_list, daily_focus, categories, ai_result


def send_watchlist_email() -> None:
    if not config.EMAIL_ENABLED:
        print("Email sending disabled.")
        return

    try:
        subprocess.run(
            [sys.executable, "send_email.py"],
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"Email sending failed: {exc}")
    except OSError as exc:
        print(f"Email sending failed: {exc}")


def send_data_failure_email() -> None:
    if not config.EMAIL_ENABLED:
        print("Data failure email disabled.")
        return

    try:
        subprocess.run(
            [sys.executable, "send_email.py", "data_failure"],
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"Data failure email failed: {exc}")
    except OSError as exc:
        print(f"Data failure email failed: {exc}")


def print_category_summary(categories: dict[str, pd.DataFrame], top_industries: pd.DataFrame) -> None:
    print("Category Counts:")
    print(f"- Total Candidates: {sum(len(categories.get(name, pd.DataFrame())) for name in CATEGORY_PRIORITY)}")
    for name in CATEGORY_PRIORITY:
        print(f"- {name}: {len(categories.get(name, pd.DataFrame()))}")


def print_ai_status(ai_result: AIAnalysisResult) -> None:
    print("\nAI Commentary", flush=True)
    print(f"AI Commentary: {'Enabled' if ai_result.enabled else 'Disabled'}", flush=True)
    print(f"OpenAI API Key: {'Loaded' if ai_result.api_key_loaded else 'Missing'}", flush=True)
    print(f"AI Model: {ai_result.model}", flush=True)
    print(f"AI Tickers Analysed: {ai_result.tickers_analysed}", flush=True)
    if ai_result.failed_safely:
        print("AI Commentary failed safely.", flush=True)


def print_universe_rebuild_summary(result: UniverseRefreshResult) -> None:
    print("\nUniverse Rebuild Summary")
    print(f"Raw Symbols: {result.raw_symbols}")
    print(f"Filtered Symbols: {result.filtered_symbols}")
    print(f"Final Valid Symbols: {result.final_valid_symbols}")
    print(f"SPY Valid: {result.spy_valid}")
    print(f"QQQ Valid: {result.qqq_valid}")
    print(f"Download Success Rate: {result.download_success_rate:.1%}")
    print(f"Runtime: {result.runtime_seconds:.1f} sec")
    print(f"Universe Replaced: {result.universe_replaced}")
    print(f"Backup Created: {result.backup_created}")
    if result.reason:
        print(f"Reason: {result.reason}")


def run_refresh_universe_command() -> int:
    timer = RunTimer(config.MAX_SCREENER_RUNTIME_SECONDS)
    _, result = refresh_universe_cache(timer=timer)
    print_universe_rebuild_summary(result)
    return 0 if result.universe_replaced else 1


def run_data_test_command() -> int:
    timer = RunTimer(config.DATA_TEST_MAX_RUNTIME_SECONDS)
    started_at = time.monotonic()
    result = UniverseRefreshResult()
    try:
        raw, total_downloaded = build_raw_universe_to_path(UNIVERSE_RAW_TEMP_CSV)
        sample = raw["Ticker"].head(config.DATA_TEST_TICKER_LIMIT).tolist()
        result.raw_symbols = total_downloaded
    except Exception:
        raw = pd.DataFrame()
        sample = []
        result.reason = "Universe source download failed."

    market_result = get_market_condition(timer=timer, retry_delays=[1, 1])
    histories, stats = download_price_histories(
        sample,
        period="3mo",
        min_rows=20,
        retry_delays=[1],
        timer=timer,
        max_attempts=2,
    )

    filtered = []
    ticker_map = raw.set_index("Ticker").to_dict("index") if not raw.empty else {}
    for ticker, frame in histories.items():
        price, avg_volume = latest_price_and_average_volume(frame)
        if (
            pd.notna(price)
            and pd.notna(avg_volume)
            and price >= config.MIN_PRICE
            and avg_volume >= config.MIN_AVG_VOLUME
            and ticker in ticker_map
        ):
            filtered.append(ticker)

    result.filtered_symbols = len(filtered)
    result.final_valid_symbols = len(filtered)
    result.spy_valid = market_result.spy_valid
    result.qqq_valid = market_result.qqq_valid
    result.download_success_rate = stats.success_rate
    result.runtime_seconds = time.monotonic() - started_at
    if not result.reason:
        result.reason = "Data-test completed. Reports, AI, and email were disabled."
    print_universe_rebuild_summary(result)
    return 0 if sample and (market_result.spy_valid or market_result.qqq_valid) else 1


def build_mock_top_action_list() -> pd.DataFrame:
    rows = [
        {
            "Ticker": "NVDA",
            "Category": "Pullback Candidates",
            "Action": "Review for pullback entry",
            "Focus Reason": "High RS + strong industry + near support",
            "RS Score": 98,
            "Industry Rank": 1,
            "Risk/Reward Quality": "Excellent R/R",
            "Pullback Quality": "A - Ideal Pullback",
            "Extension Status": "Not Extended",
            "VCP Label": "Good VCP",
            "Volume Ratio": 0.65,
            "Nearest Support Distance ATR": 0.55,
            "Distance From Pivot %": -3.2,
            "Support Signal": "EMA20 reclaim",
        },
        {
            "Ticker": "AMD",
            "Category": "Tight Consolidation Candidates",
            "Action": "Set pivot alert",
            "Focus Reason": "Strong industry + tightening range",
            "RS Score": 94,
            "Industry Rank": 1,
            "Risk/Reward Quality": "Good R/R",
            "Pullback Quality": "B - Healthy Pullback",
            "Extension Status": "Moderately Extended",
            "VCP Label": "Excellent VCP",
            "Volume Ratio": 0.50,
            "Nearest Support Distance ATR": 0.80,
            "Distance From Pivot %": -1.5,
            "Support Signal": "Recent support",
        },
        {
            "Ticker": "ASML",
            "Category": "Pullback Candidates",
            "Action": "Review for pullback entry",
            "Focus Reason": "Semiconductor equipment leader near support",
            "RS Score": 91,
            "Industry Rank": 2,
            "Risk/Reward Quality": "Good R/R",
            "Pullback Quality": "A - Ideal Pullback",
            "Extension Status": "Not Extended",
            "VCP Label": "Average VCP",
            "Volume Ratio": 0.72,
            "Nearest Support Distance ATR": 0.95,
            "Distance From Pivot %": -4.1,
            "Support Signal": "50MA reclaim",
        },
        {
            "Ticker": "CRWD",
            "Category": "Tight Consolidation Candidates",
            "Action": "Monitor tight base",
            "Focus Reason": "Software leadership with controlled base",
            "RS Score": 89,
            "Industry Rank": 4,
            "Risk/Reward Quality": "Fair R/R",
            "Pullback Quality": "B - Healthy Pullback",
            "Extension Status": "Moderately Extended",
            "VCP Label": "Good VCP",
            "Volume Ratio": 0.58,
            "Nearest Support Distance ATR": 1.25,
            "Distance From Pivot %": -2.4,
            "Support Signal": "Recent support",
        },
        {
            "Ticker": "VRTX",
            "Category": "Extended Candidates",
            "Action": "Wait for pullback",
            "Focus Reason": "Biotech leader but extended from support",
            "RS Score": 86,
            "Industry Rank": 3,
            "Risk/Reward Quality": "Poor R/R",
            "Pullback Quality": "C - Extended Pullback",
            "Extension Status": "Extended",
            "VCP Label": "Poor VCP",
            "Volume Ratio": 1.10,
            "Nearest Support Distance ATR": 2.60,
            "Distance From Pivot %": 4.8,
            "Support Signal": "Top-25% close",
        },
    ]
    return pd.DataFrame(rows)


def build_mock_top_industries() -> pd.DataFrame:
    rows = [
        {"Industry": "Semiconductors", "Sector": "Technology", "Industry Strength Score": 96, "Candidate Count": 12, "Avg RS Score": 91, "Best RS Score": 98, "Top 3 Leaders": "NVDA, AMD, AVGO"},
        {"Industry": "Semiconductor Equipment & Materials", "Sector": "Technology", "Industry Strength Score": 92, "Candidate Count": 8, "Avg RS Score": 88, "Best RS Score": 91, "Top 3 Leaders": "ASML, AMAT, LRCX"},
        {"Industry": "Biotechnology", "Sector": "Healthcare", "Industry Strength Score": 84, "Candidate Count": 10, "Avg RS Score": 82, "Best RS Score": 86, "Top 3 Leaders": "VRTX, REGN, ALNY"},
        {"Industry": "Software - Infrastructure", "Sector": "Technology", "Industry Strength Score": 81, "Candidate Count": 9, "Avg RS Score": 80, "Best RS Score": 89, "Top 3 Leaders": "CRWD, NET, DDOG"},
        {"Industry": "Electronic Components", "Sector": "Technology", "Industry Strength Score": 78, "Candidate Count": 7, "Avg RS Score": 76, "Best RS Score": 84, "Top 3 Leaders": "GLW, FLEX, JBL"},
    ]
    return pd.DataFrame(rows, columns=TOP_INDUSTRY_COLUMNS)


def section_text(commentary: str, heading: str) -> str:
    lines = commentary.splitlines()
    captured = []
    capture = False
    for line in lines:
        stripped = line.strip().strip("#:")
        if stripped.lower() == heading.lower():
            capture = True
            continue
        if capture and stripped in {
            "Market Summary",
            "Industry Rotation Summary",
            "Best Opportunities",
            "Stocks To Wait",
            "Overall Market Character",
            "Reminder",
        }:
            break
        if capture:
            captured.append(line)
    text = "\n".join(captured).strip()
    return text or "Unavailable"


def run_ai_test_command(print_output: bool = True) -> tuple[int, AIAnalysisResult | None]:
    top_action_list = build_mock_top_action_list()
    top_industries = build_mock_top_industries()
    commentary = ai_analysis.generate_ai_commentary(top_action_list, top_industries, "Strong")
    result = ai_analysis.get_last_ai_analysis_result()
    if result is None:
        return 1, None

    expected_tickers = set(top_action_list["Ticker"])
    ranked = result.top_action_list.copy()
    ranked_tickers = set(
        ranked[
            ranked["AI Conviction Score"].astype(str).str.len().gt(0)
            & ranked["AI Priority Rank"].astype(str).str.len().gt(0)
            & ranked["AI Reason"].astype(str).str.len().gt(0)
        ]["Ticker"]
    )
    omitted = sorted(expected_tickers - ranked_tickers)
    required_columns_present = all(column in ranked.columns for column in ai_analysis.AI_SCORE_COLUMNS)
    success = (
        result.api_call_success
        and result.json_parsed
        and result.commentary_generated
        and required_columns_present
        and bool(ranked_tickers)
    )

    if print_output:
        print("\nAI Test Mode")
        print(f"AI Commentary: {'Enabled' if result.enabled else 'Disabled'}")
        print(f"OpenAI API Key: {'Loaded' if result.api_key_loaded else 'Missing'}")
        print(f"AI Model: {result.model}")
        print(f"AI Tickers Analysed: {result.tickers_analysed}")
        print(f"API Call: {'Success' if result.api_call_success else 'Failed'}")
        print(f"JSON Parsed: {'Yes' if result.json_parsed else 'No'}")
        print(
            "Response Time: "
            f"{result.response_time_seconds:.2f} sec"
            if result.response_time_seconds is not None
            else "Response Time: Unavailable"
        )
        print(f"Input Tokens: {result.input_tokens if result.input_tokens is not None else 'Unavailable'}")
        print(f"Output Tokens: {result.output_tokens if result.output_tokens is not None else 'Unavailable'}")
        print(f"Total Tokens: {result.response_tokens if result.response_tokens is not None else 'Unavailable'}")
        if result.failed_safely:
            print("AI Commentary failed safely.")
        if result.error_type:
            print(f"OpenAI Error Type: {result.error_type}")
        if result.error_code:
            print(f"Safe Error Code: {result.error_code}")
        if result.http_status is not None:
            print(f"HTTP Status: {result.http_status}")
        if omitted:
            print(f"Omitted Tickers: {', '.join(omitted)}")
            print("Omitted Explanation: The AI response did not provide complete ranking fields for these input tickers.")

        print("\nMarket Summary")
        print(section_text(commentary, "Market Summary"))
        print("\nIndustry Rotation Summary")
        print(section_text(commentary, "Industry Rotation Summary"))
        print("\nRanked Opportunities")
        print(section_text(commentary, "Best Opportunities"))
        print("\nStocks To Wait")
        print(section_text(commentary, "Stocks To Wait"))
        print("\nAI Ranking Table:")
        columns = ["Ticker", "AI Priority Rank", "AI Conviction Score", "AI Reason"]
        print(ranked[columns].to_string(index=False))

    return (0 if success else 1), result


def command_success(command: list[str], timeout_seconds: int) -> bool:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except Exception:
        return False
    return completed.returncode == 0


def run_self_test_command() -> int:
    print("\nSystem Health Check")
    config_ok = bool(config.AI_MODEL) and config.AI_MAX_TICKERS > 0
    ai_analysis.load_dotenv_if_available()
    openai_key_ready = bool(ai_analysis.load_openai_api_key())
    gmail_ready = bool(os.environ.get("GMAIL_ADDRESS") and os.environ.get("GMAIL_APP_PASSWORD"))

    universe_ok = False
    universe_path = Path(config.UNIVERSE_CSV)
    if universe_path.exists():
        try:
            universe_ok = len(pd.read_csv(universe_path)) >= config.MIN_VALID_UNIVERSE_COUNT
        except Exception:
            universe_ok = False

    yahoo_result = get_market_condition(
        timer=RunTimer(config.DATA_TEST_MAX_RUNTIME_SECONDS),
        retry_delays=[1, 1],
    )
    yahoo_ok = yahoo_result.spy_valid and yahoo_result.qqq_valid
    openai_ok = command_success([sys.executable, "test_openai.py"], 20)
    ai_code, _ = run_ai_test_command(print_output=False)
    ai_ok = ai_code == 0

    report_ok = False
    try:
        probe = Path(".self_test_write.tmp")
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        report_ok = True
    except Exception:
        report_ok = False

    checks = {
        "Config": config_ok,
        "Environment": openai_key_ready,
        "Universe": universe_ok,
        "Yahoo SPY/QQQ": yahoo_ok,
        "OpenAI Connection": openai_ok,
        "AI Analysis": ai_ok,
        "Reports Folder": report_ok,
    }
    for label, ok in checks.items():
        print(f"{label}: {'OK' if ok else 'Failed'}")
    print(f"Gmail Configuration: {'Ready' if gmail_ready else 'Missing'}")
    healthy = all(checks.values())
    print(f"Overall Status: {'Healthy' if healthy else 'Attention Required'}")
    return 0 if healthy else 1


def main(argv: list[str] | None = None) -> int:
    args = set(argv if argv is not None else sys.argv[1:])
    if "--data-test" in args:
        return run_data_test_command()
    if "--refresh-universe" in args:
        return run_refresh_universe_command()
    if "--ai-test" in args:
        code, _ = run_ai_test_command(print_output=True)
        return code
    if "--self-test" in args:
        return run_self_test_command()

    timer = RunTimer(config.MAX_SCREENER_RUNTIME_SECONDS)
    market_result = get_market_condition(timer=timer)
    universe_result = load_universe(timer=timer)
    categories, top_industries, stage2_count, download_stats = screen_stocks(
        universe_result.universe,
        timer=timer,
    )
    run_quality = validate_run_quality(universe_result, market_result, download_stats, timer=timer)
    print_data_quality_check(run_quality)

    if not run_quality.valid:
        write_data_failure_report(run_quality)
        print("DATA FAILURE: Previous valid watchlist preserved.")
        send_data_failure_email()
        return 1

    watchlist, top_action_list, daily_focus, categories, ai_result = export_results(
        categories,
        top_industries,
        market_result.frame,
        market_result.status,
    )
    print_ai_status(ai_result)
    send_watchlist_email()

    print("\nMarket Status")
    print(f"Status: {market_result.status}")
    print(market_result.frame.to_string(index=False))
    print(f"Total tickers passing Stage 2 filters: {stage2_count}")
    print(f"Total watchlist rows: {len(watchlist)}")
    print(f"Top Action List rows: {len(top_action_list)}")
    print(f"Daily Focus List rows: {len(daily_focus)}")
    print("\nTop 5 Industries")
    print("No industry groups matched." if top_industries.empty else top_industries.head(5).to_string(index=False))
    print("\nTop Action List")
    print("No action tickers." if top_action_list.empty else top_action_list.to_string(index=False))
    print("\nDaily Focus List")
    print("No focus tickers." if daily_focus.empty else daily_focus.to_string(index=False))
    print()
    print_category_summary(categories, top_industries)

    if watchlist.empty:
        print("No stocks matched the screener.")
    else:
        for name in CATEGORY_PRIORITY:
            frame = categories.get(name, pd.DataFrame(columns=DISCOVERY_COLUMNS))
            print(f"\n{name}")
            print("No matches." if frame.empty else frame.to_string(index=False))
        print("\nTop Industries")
        print("No industry groups matched." if top_industries.empty else top_industries.to_string(index=False))
    print(f"\nExported {OUTPUT_CSV}, {OUTPUT_MD}, and {OUTPUT_HTML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
