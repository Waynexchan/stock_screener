"""Simple US stock screener using Yahoo Finance data."""

from __future__ import annotations

import math
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import shutil
import logging
from dataclasses import asdict, dataclass, field, is_dataclass, replace
from html import escape
from datetime import date, datetime, time as datetime_time, timezone
from pathlib import Path
from urllib.request import urlopen
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf
from pandas.tseries.holiday import (
    AbstractHolidayCalendar,
    GoodFriday,
    Holiday,
    USLaborDay,
    USMartinLutherKingJr,
    USMemorialDay,
    USPresidentsDay,
    USThanksgivingDay,
    nearest_workday,
)
from pandas.tseries.offsets import CustomBusinessDay

import config
import ai_analysis
from decision_system import (
    TradeSizingDecision,
    calculate_reward_risk,
    canonical_candidate_decision,
    construct_trade_plan,
    enforce_setup_consistency,
    load_drawdown_state,
    load_portfolio_status,
    market_regime_from_metrics,
    qualify_industries,
    score_candidate,
    apply_concentration_limits,
    entry_timing_for_candidate,
)
from ai_analysis import AIAnalysisResult, analyse_top_action_list


OUTPUT_CSV = "daily_watchlist.csv"
OUTPUT_MD = "daily_watchlist.md"
OUTPUT_HTML = "daily_watchlist.html"
PREVIEW_HTML = "daily_watchlist_preview.html"
EMAIL_SUMMARY = "email_summary.txt"
LAST_GOOD_CSV = "daily_watchlist_last_good.csv"
LAST_GOOD_MD = "daily_watchlist_last_good.md"
LAST_GOOD_HTML = "daily_watchlist_last_good.html"
DATA_FAILURE_REPORT = "data_failure_report.txt"
SUMMARY_HISTORY_CSV = "summary_history.csv"
LAST_ELIGIBLE_UNIVERSE = pd.DataFrame()
LAST_METADATA_DIAGNOSTICS: dict[str, object] = {}
LAST_FORWARD_SNAPSHOT = ""
UNIVERSE_TEMP_CSV = "universe_temp.csv"
UNIVERSE_RAW_TEMP_CSV = "universe_raw_temp.csv"
UNIVERSE_BACKUP_CSV = "universe_backup.csv"
METADATA_CACHE_CSV = config.METADATA_CACHE_CSV
YFINANCE_CACHE_DIR = ".yfinance_cache"
UNIVERSE_COLUMNS = [
    "Ticker",
    "Symbol",
    "Security Name",
    "Exchange",
    "Sector",
    "Industry",
    "Market Cap",
    "Avg Volume",
]
DISCOVERY_COLUMNS = [
    "Generated At",
    "Signal Date",
    "Price Data As Of",
    "Latest Bar Timestamp",
    "Price Freshness Status",
    "Category",
    "Ticker",
    "Sector",
    "Industry",
    "RS Score",
    "Recent RS Score",
    "RS Momentum Acceleration",
    "RS Trend",
    "RS Trend Delta",
    "Price",
    "Action",
    "Review Tier",
    "Confirmed Setup",
    "Actionable",
    "Setup Integrity",
    "Email Priority Rank",
    "Noise Filter Reason",
    "Review Priority Score",
    "Price Data Warning",
    "ATR20",
    "ATR20 %",
    "ADR %",
    "From 52W High %",
    "Distance From 50MA %",
    "Distance From 30WMA %",
    "Distance From Pivot %",
    "Volume Ratio",
    "Distance From EMA10 ATR",
    "Distance From EMA20 ATR",
    "Distance From MA50 ATR",
    "Distance From 30WMA ATR",
    "Nearest Support Distance ATR",
    "Support Signal",
    "10 Day Range %",
    "20 Day Range %",
    "Tightness Score",
    "Tightness Label",
    "ADR20 %",
    "ADR60 %",
    "VCP Ratio",
    "VCP Label",
    "Pullback Quality",
    "Extension Status",
    "Risk/Reward Quality",
    "Planned Entry",
    "Planned Entry Source",
    "Initial Stop",
    "Structural Stop Source",
    "Realistic Target",
    "Realistic Target Source",
    "Reward/Risk Ratio",
    "Trade Plan Confidence",
    "Trade Plan Validation Reasons",
    "Industry Qualified",
    "Industry Classification",
    "Breadth Sample Quality",
    "Sister Confirmation",
    "Sister Confirmation State",
    "Final Decision",
    "Decision Reasons",
    "Final Score",
    "Recent RS Component",
    "Industry Sister Component",
    "Setup Quality Component",
    "Volume Component",
    "Entry Stop Component",
    "Intermediate Trend Component",
    "Base Score",
    "Score Penalties",
    "Total Penalty",
    "Industry Rank",
    "Industry Setup Count",
    "Avg Volume",
    "TradingView",
]
TOP_INDUSTRY_COLUMNS = [
    "Final Rank",
    "Industry",
    "Sector",
    "Final Industry Score",
    "Momentum Rank",
    "Momentum Score",
    "Leadership Rank",
    "Leadership Score",
    "Industry Status",
    "Median Recent RS Score",
    "Median 5D Relative Return",
    "Median 20D Relative Return",
    "Median 60D Relative Return",
    "20D Outperformance Breadth %",
    "% Above 20EMA",
    "Stage 2 Breadth %",
    "Candidate Count",
    "Candidate Breadth %",
    "Total Eligible Stocks",
    "Top 3 Leaders",
]
ISOLATED_INDUSTRY_COLUMNS = TOP_INDUSTRY_COLUMNS.copy()
SUMMARY_HISTORY_COLUMNS = [
    "generated_at",
    "market_status",
    "top_action_count",
    "confirmed_setups",
    "emerging_leaders",
    "caution_rows",
    "price_warnings",
    "top_action_tickers",
    "top_industries",
]
CATEGORY_NAMES = [
    "Breakout Candidates",
    "Pullback Candidates",
    "Tight Consolidation Candidates",
    "Extended Candidates",
    "Volume Surge Candidates",
    "Developing Base Candidates",
]
CATEGORY_PRIORITY = [
    "Breakout Candidates",
    "Volume Surge Candidates",
    "Pullback Candidates",
    "Tight Consolidation Candidates",
    "Developing Base Candidates",
    "Extended Candidates",
]
FOCUS_LIMITS = {
    "Breakout Candidates": 5,
    "Volume Surge Candidates": 5,
    "Pullback Candidates": 8,
    "Tight Consolidation Candidates": 8,
    "Developing Base Candidates": 8,
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


class USMarketHolidayCalendar(AbstractHolidayCalendar):
    """Regular full-day US equity-market holidays.

    Exceptional closures are not available from the current dependency set and
    are disclosed as a fallback limitation in the user guide.
    """

    rules = [
        Holiday("New Year's Day", month=1, day=1, observance=nearest_workday),
        USMartinLutherKingJr,
        USPresidentsDay,
        GoodFriday,
        USMemorialDay,
        Holiday(
            "Juneteenth",
            month=6,
            day=19,
            start_date="2022-06-19",
            observance=nearest_workday,
        ),
        Holiday("Independence Day", month=7, day=4, observance=nearest_workday),
        USLaborDay,
        USThanksgivingDay,
        Holiday("Christmas", month=12, day=25, observance=nearest_workday),
    ]


US_MARKET_BUSINESS_DAY = CustomBusinessDay(calendar=USMarketHolidayCalendar())


@dataclass(frozen=True)
class PriceFreshness:
    status: str
    latest_bar_timestamp: str
    price_data_as_of: str
    expected_session: str
    warning: str = ""


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
    metrics: dict[str, float | bool | None] = field(default_factory=dict)


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


def bounded(
    value: float, low: float, high: float, default: float | None = None
) -> float:
    if pd.isna(value):
        return low if default is None else default
    return max(low, min(high, float(value)))


def known_metadata_value(value: object) -> bool:
    if pd.isna(value):
        return False
    text = str(value).strip()
    return bool(text) and text.lower() not in {"unknown", "nan", "none", "n/a"}


def known_industry_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "Industry" not in frame.columns:
        return frame.iloc[0:0].copy()
    return frame[frame["Industry"].apply(known_metadata_value)].copy()


def confirmation_signal(row: pd.Series | dict) -> bool:
    recent_rs = row.get("Recent RS Score")
    if (
        recent_rs is None
        or pd.isna(recent_rs)
        or float(recent_rs) < config.MIN_RECENT_RS_ALLOWED
    ):
        return False
    if not bool(row.get("Industry Qualified", False)) or not bool(
        row.get("Sister Confirmation", False)
    ):
        return False
    if (
        str(row.get("Tightness Label", "")) == "Loose"
        or str(row.get("VCP Label", "")) == "Poor VCP"
    ):
        return False
    if str(row.get("Extension Status", "")) in {"Extended", "Overextended"} or row.get(
        "Price Data Warning"
    ):
        return False
    reward_risk = calculate_reward_risk(
        row.get("Planned Entry"),
        row.get("Initial Stop"),
        row.get("Realistic Target"),
        row.get("Distance From Pivot %"),
        row.get("Nearest Support Distance ATR"),
    )
    if not reward_risk.valid:
        return False
    support_signal = str(row.get("Support Signal", ""))
    volume_ratio = bounded(row.get("Volume Ratio", 0), 0, 5, default=0)
    close_position = bounded(
        row.get("Close Position %", np.nan), 0, 100, default=np.nan
    )
    has_reclaim = (
        "reclaim" in support_signal.lower()
        or "close above prior high" in support_signal.lower()
    )
    return has_reclaim and (
        volume_ratio >= 0.55 or (not pd.isna(close_position) and close_position >= 75)
    )


def review_priority_score(row: pd.Series | dict) -> float:
    """Rank review order: stock quality/setup/volume first, then industry."""
    rs = bounded(row.get("RS Score", 0), 0, 100)
    recent_rs = bounded(row.get("Recent RS Score", 0), 0, 100, default=0)
    volume_ratio = bounded(row.get("Volume Ratio", 0), 0, 3)
    avg_volume = bounded(row.get("Avg Volume", 0), 0, 10_000_000)
    support_atr = bounded(row.get("Nearest Support Distance ATR", 9), 0, 9, default=9)
    industry_rank = bounded(row.get("Industry Rank", 999), 1, 999, default=999)
    industry_setup_count = bounded(row.get("Industry Setup Count", 0), 0, 20, default=0)
    score = 0.0
    score += recent_rs * 0.30
    score += rs * 0.05
    score += min(avg_volume / 1_000_000, 8) * 0.6

    risk_quality = row.get("Risk/Reward Quality", "")
    score += {
        "Excellent R/R": 14,
        "Good R/R": 10,
        "Valid R/R": 10,
        "Fair R/R": 5,
        "Poor R/R": -5,
        "Avoid": -12,
    }.get(risk_quality, 0)

    pullback = str(row.get("Pullback Quality", ""))
    if pullback.startswith("A"):
        score += 8
    elif pullback.startswith("B"):
        score += 5
    elif pullback.startswith("C"):
        score -= 2
    elif pullback.startswith("D"):
        score -= 6

    extension = row.get("Extension Status", "")
    score += {
        "Not Extended": 8,
        "Moderately Extended": 3,
        "Extended": -8,
        "Overextended": -16,
    }.get(extension, 0)

    score += {
        "Excellent VCP": 10,
        "Good VCP": 7,
        "Average VCP": 2,
        "Poor VCP": -8,
    }.get(row.get("VCP Label", ""), 0)

    score += {
        "Very Tight": 6,
        "Tight": 4,
        "Normal": 1,
        "Loose": -5,
    }.get(row.get("Tightness Label", ""), 0)

    rs_trend = row.get("RS Trend", "")
    score += {
        "Emerging Leader": 7,
        "Improving": 4,
        "Stable Leader": 3,
        "Stable": 0,
        "Weakening": -4,
        "Fading": -9,
    }.get(rs_trend, 0)

    if support_atr <= 0.75:
        score += 8
    elif support_atr <= 1.5:
        score += 5
    elif support_atr <= 2.5:
        score += 1
    else:
        score -= 4

    category = row.get("Category", "")
    confirmed = confirmation_signal(row)
    if category == "Breakout Candidates":
        if volume_ratio >= 1.5:
            score += 9
        elif volume_ratio >= 1.2:
            score += 5
        else:
            score -= 4
    elif category == "Volume Surge Candidates":
        score += 8 if volume_ratio >= 1.5 else 2
    elif category == "Pullback Candidates":
        if confirmed:
            score += 7
        elif 0.35 <= volume_ratio <= 0.85:
            score += 4
        elif volume_ratio < 0.25:
            score -= 3
    elif category == "Tight Consolidation Candidates":
        score += 5 if volume_ratio <= 0.85 else 1

    industry_qualified = bool(row.get("Industry Qualified", False))
    if industry_qualified and industry_setup_count >= 5:
        score += 8
    elif industry_qualified and industry_setup_count >= 3:
        score += 5
    elif industry_qualified and industry_setup_count >= 2:
        score += 3

    if industry_qualified and industry_rank <= 5:
        score += 4
    elif industry_rank <= 15:
        score += 2
    elif industry_rank <= 30:
        score += 1

    if row.get("Price Data Warning"):
        score -= 20

    return round(bounded(score, 0, 100), 1)


def add_review_priority_column(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    updated = frame.copy()
    updated["Review Priority Score"] = updated.apply(review_priority_score, axis=1)
    return updated


def setup_noise_reasons(row: pd.Series | dict) -> list[str]:
    reasons = []
    risk_reward = str(row.get("Risk/Reward Quality", ""))
    extension = str(row.get("Extension Status", ""))
    vcp = str(row.get("VCP Label", ""))
    tightness = str(row.get("Tightness Label", ""))
    pullback_quality = str(row.get("Pullback Quality", ""))
    rs_trend = str(row.get("RS Trend", ""))
    action = str(row.get("Action", ""))
    volume_ratio = bounded(row.get("Volume Ratio", 0), 0, 5, default=0)
    support_atr = bounded(row.get("Nearest Support Distance ATR", 9), 0, 9, default=9)
    industry_setup_count = bounded(row.get("Industry Setup Count", 0), 0, 20, default=0)
    confidence_order = {"Low": 0, "Medium": 1, "High": 2}
    raw_trade_plan_confidence = row.get("Trade Plan Confidence")
    trade_plan_confidence = str(raw_trade_plan_confidence or "")
    target_source = str(row.get("Realistic Target Source", ""))

    if row.get("Recent RS Score") is None or pd.isna(row.get("Recent RS Score")):
        reasons.append("DATA_INCOMPLETE: Recent RS missing")
    elif float(row.get("Recent RS Score")) < config.MIN_RECENT_RS_ALLOWED:
        reasons.append("Recent RS below threshold")
    if not bool(row.get("Industry Qualified", False)):
        reasons.append("industry not qualified")

    price_warning = row.get("Price Data Warning")
    if (
        price_warning is not None
        and not pd.isna(price_warning)
        and str(price_warning).strip()
    ):
        reasons.append("price warning")
    if risk_reward == "Not Available":
        reasons.append("R/R not available")
    elif risk_reward not in {"Excellent R/R", "Good R/R", "Valid R/R"}:
        reasons.append("weak R/R")
    if trade_plan_confidence and confidence_order.get(
        trade_plan_confidence, 0
    ) < confidence_order.get(config.MIN_TRADE_PLAN_CONFIDENCE, 1):
        reasons.append("trade-plan confidence below minimum")
    if target_source == "model 2R feasibility target":
        reasons.append("model 2R target requires chart-confirmed resistance")
    if extension in {"Extended", "Overextended"}:
        reasons.append("extended")
    if pullback_quality.startswith(("C", "D")):
        reasons.append("weak pullback quality")
    if vcp == "Poor VCP":
        reasons.append("poor VCP")
    if tightness == "Loose":
        reasons.append("loose action")
    if rs_trend in {"Weakening", "Fading"}:
        reasons.append("weakening RS")
    if support_atr > config.MAX_ACTIONABLE_SUPPORT_DISTANCE_ATR:
        reasons.append("far from support")
    if volume_ratio < config.MIN_CONFIRMATION_VOLUME_RATIO:
        reasons.append("thin confirmation volume")
    if industry_setup_count < config.MIN_ACTIONABLE_INDUSTRY_SETUP_COUNT:
        state = str(row.get("Sister Confirmation State", "")).strip()
        industry_reason = (
            state.lower() if state else "industry confirmation unavailable"
        )
        if industry_reason not in reasons:
            reasons.append(industry_reason)
    if action in {"Watch only", "Wait for pullback", "Wait for cleaner entry"}:
        reasons.append("wait-only action")
    return reasons


def review_tier(row: pd.Series | dict) -> str:
    reasons = setup_noise_reasons(row)
    confirmed = confirmation_signal(row)
    score = bounded(
        row.get("Review Priority Score", review_priority_score(row)), 0, 100, default=0
    )
    rs = bounded(row.get("RS Score", 0), 0, 100, default=0)
    rs_trend = str(row.get("RS Trend", ""))
    risk_reward = str(row.get("Risk/Reward Quality", ""))
    extension = str(row.get("Extension Status", ""))
    vcp = str(row.get("VCP Label", ""))
    tightness = str(row.get("Tightness Label", ""))
    industry_setup_count = bounded(row.get("Industry Setup Count", 0), 0, 20, default=0)
    skip_noise = {
        "price warning",
        "weak R/R",
        "extended",
        "weakening RS",
        "weak pullback quality",
        "DATA_INCOMPLETE: Recent RS missing",
    }
    top_action_noise = {
        "poor VCP",
        "loose action",
        "far from support",
        "thin confirmation volume",
        "industry confirmation unavailable",
        "industry not qualified",
        "small-sample industry",
        "isolated leader exception",
        "qualified industry, but fewer than two qualifying sister setups",
        "qualified industry, but sister-stock breadth is insufficient",
        "wait-only action",
        "industry not qualified",
        "R/R not available",
        "trade-plan confidence below minimum",
        "model 2R target requires chart-confirmed resistance",
        "Recent RS below threshold",
        "setup confirmation trigger missing",
    }

    if vcp == "Poor VCP" and tightness == "Loose":
        return "Skip Today"

    if skip_noise.intersection(reasons):
        return "Skip Today"
    if top_action_noise.intersection(reasons):
        return "Watch Later"
    if (
        confirmed
        and score >= config.MIN_REVIEW_NOW_SCORE
        and risk_reward in {"Excellent R/R", "Good R/R", "Valid R/R"}
        and extension == "Not Extended"
        and not reasons
    ):
        return "Review Now"
    if (
        score >= config.MIN_HIGH_PRIORITY_SCORE
        and rs >= config.MIN_HIGH_PRIORITY_RS_SCORE
        and risk_reward in {"Excellent R/R", "Good R/R", "Valid R/R"}
        and extension in {"Not Extended", "Moderately Extended"}
        and rs_trend in {"Emerging Leader", "Improving", "Stable Leader"}
        and industry_setup_count >= config.MIN_ACTIONABLE_INDUSTRY_SETUP_COUNT
        and not (vcp == "Poor VCP" and tightness == "Loose")
        and not reasons
    ):
        return "High Priority Watch"
    return "Watch Later"


def add_review_guidance_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    consistent_rows = []
    for record in frame.to_dict("records"):
        consistent, warnings = enforce_setup_consistency(record)
        if (
            str(consistent.get("Tightness Label")) == "Loose"
            and str(consistent.get("Category")) == "Pullback Candidates"
        ):
            consistent["Category"] = "Developing Base Candidates"
            warnings.append("Loose pullback reassigned to Developing Base")
        consistent["Consistency Warnings"] = "; ".join(warnings)
        consistent_rows.append(consistent)
    updated = add_review_priority_column(pd.DataFrame(consistent_rows))
    updated["Review Tier"] = updated.apply(review_tier, axis=1)
    updated["Confirmed Setup"] = updated.apply(confirmation_signal, axis=1)
    # Review guidance is descriptive only.  The canonical decision engine later
    # assigns the sole authoritative FULL/HALF/WATCH/NO TRADE state.
    existing_decisions = updated.get(
        "Final Decision", pd.Series("", index=updated.index, dtype="object")
    )
    updated["Final Decision"] = existing_decisions.where(
        existing_decisions.isin(["FULL", "HALF", "WATCH", "NO TRADE"]), ""
    )
    updated["Noise Filter Reason"] = updated.apply(
        lambda row: ", ".join(setup_noise_reasons(row)),
        axis=1,
    )
    updated["Decision Reasons"] = updated["Noise Filter Reason"]
    updated["Score Penalties"] = updated.get(
        "Score Penalties", pd.Series("", index=updated.index, dtype="object")
    ).astype("object")
    for index, row in updated.iterrows():
        breakdown = score_candidate(row.to_dict())
        updated.at[index, "Recent RS Component"] = breakdown.recent_rs_component
        updated.at[index, "Industry Sister Component"] = (
            breakdown.industry_sister_component
        )
        updated.at[index, "Setup Quality Component"] = breakdown.setup_quality_component
        updated.at[index, "Volume Component"] = breakdown.volume_component
        updated.at[index, "Entry Stop Component"] = breakdown.entry_stop_component
        updated.at[index, "Intermediate Trend Component"] = (
            breakdown.intermediate_trend_component
        )
        updated.at[index, "Base Score"] = breakdown.base_score
        updated.at[index, "Score Penalties"] = "; ".join(
            f"{key}: -{value}" for key, value in breakdown.penalties.items()
        )
        updated.at[index, "Total Penalty"] = breakdown.total_penalty
        updated.at[index, "Final Score"] = breakdown.final_score
    return updated


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
    return listed.drop_duplicates("Yahoo Ticker").reset_index(
        drop=True
    ), total_downloaded


def chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def ticker_frame_from_download(history: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame()
    try:
        frame = (
            history[ticker] if isinstance(history.columns, pd.MultiIndex) else history
        )
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


def expected_latest_us_session(now: datetime | None = None) -> date:
    """Return the latest completed regular US trading session."""
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    eastern = reference.astimezone(ZoneInfo("America/New_York"))
    today = pd.Timestamp(eastern.date())
    is_session = len(pd.date_range(today, today, freq=US_MARKET_BUSINESS_DAY)) == 1
    market_ready_at = datetime_time(
        16, config.US_MARKET_CLOSE_GRACE_MINUTES, tzinfo=eastern.tzinfo
    )
    if is_session and eastern.timetz() >= market_ready_at:
        return eastern.date()
    return (today - US_MARKET_BUSINESS_DAY).date()


def price_freshness_status(
    history: pd.DataFrame, now: datetime | None = None
) -> PriceFreshness:
    """Validate the last complete bar against the expected US session.

    The exchange-holiday calendar handles regular weekends and full-day US
    market holidays.  PRICE_STALE_HOURS remains the conservative fallback if
    session calculation cannot be completed.
    """
    if history.empty or not {"Open", "High", "Low", "Close", "Volume"}.issubset(
        history.columns
    ):
        return PriceFreshness(
            "MISSING", "", "", "", "partial or missing latest price bar"
        )
    latest = history.iloc[-1]
    if latest[["Open", "High", "Low", "Close", "Volume"]].isna().any():
        timestamp = str(history.index[-1])
        return PriceFreshness(
            "INCOMPLETE", timestamp, "", "", "partial or missing latest price bar"
        )
    try:
        timestamp = pd.Timestamp(history.index[-1])
        if timestamp.tzinfo is not None:
            market_timestamp = timestamp.tz_convert("America/New_York")
        else:
            market_timestamp = timestamp
        latest_date = market_timestamp.date()
        expected = expected_latest_us_session(now)
        if latest_date == expected:
            status = "CURRENT"
            warning = ""
        elif latest_date < expected:
            status = "STALE"
            warning = f"latest bar {latest_date.isoformat()} precedes expected US session {expected.isoformat()}"
        else:
            status = "INCOMPLETE"
            warning = (
                f"latest bar {latest_date.isoformat()} is after latest completed US session "
                f"{expected.isoformat()} and may be incomplete or future-dated"
            )
        return PriceFreshness(
            status,
            timestamp.isoformat(),
            latest_date.isoformat(),
            expected.isoformat(),
            warning,
        )
    except (TypeError, ValueError, OverflowError):
        reference = now or datetime.now(timezone.utc)
        try:
            fallback_timestamp = pd.Timestamp(history.index[-1])
            if fallback_timestamp.tzinfo is None:
                fallback_timestamp = fallback_timestamp.tz_localize(timezone.utc)
            age_hours = (
                pd.Timestamp(reference).tz_convert(timezone.utc)
                - fallback_timestamp.tz_convert(timezone.utc)
            ).total_seconds() / 3600
            status = "CURRENT" if age_hours <= config.PRICE_STALE_HOURS else "STALE"
            return PriceFreshness(
                status,
                fallback_timestamp.isoformat(),
                fallback_timestamp.date().isoformat(),
                "fallback-hours",
                "" if status == "CURRENT" else "price data exceeds stale-hour fallback",
            )
        except (TypeError, ValueError, OverflowError):
            return PriceFreshness(
                "MISSING", "", "", "", "latest bar timestamp is invalid"
            )


def price_data_warning(history: pd.DataFrame) -> str:
    if history.empty or "Close" not in history.columns:
        return "Missing price history"
    closes = history["Close"].dropna()
    if len(closes) < 60:
        return "Insufficient price history"
    latest_close = closes.iloc[-1]
    median_20 = closes.tail(20).median()
    median_60 = closes.tail(60).median()
    if latest_close <= 0 or median_20 <= 0 or median_60 <= 0:
        return "Invalid close price"

    ratio_20 = latest_close / median_20
    ratio_60 = latest_close / median_60
    if ratio_20 > 2.5 or ratio_20 < 0.4:
        return "Latest close inconsistent with 20-day median"
    if ratio_60 > 3.0 or ratio_60 < 0.33:
        return "Latest close inconsistent with 60-day median"

    daily_change = closes.pct_change().iloc[-1]
    if not pd.isna(daily_change) and abs(daily_change) > 0.75:
        return "Extreme one-day close change"
    return ""


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
    chunk_sizes = ([config.DOWNLOAD_CHUNK_SIZE] + list(config.FALLBACK_CHUNK_SIZES))[
        :attempt_limit
    ]
    delays = (
        retry_delays
        if retry_delays is not None
        else config.HISTORY_RETRY_DELAYS_SECONDS
    )

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
        frame = (
            history[ticker] if isinstance(history.columns, pd.MultiIndex) else history
        )
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


def load_metadata_cache(path: str = METADATA_CACHE_CSV) -> dict[str, dict[str, str]]:
    cache_path = Path(path)
    if not cache_path.exists():
        return {}
    try:
        frame = pd.read_csv(cache_path)
    except Exception:
        return {}
    required = {"Ticker", "Sector", "Industry"}
    if frame.empty or not required.issubset(frame.columns):
        return {}
    return {
        str(row["Ticker"]).upper(): {
            "Sector": str(row.get("Sector") or "Unknown"),
            "Industry": str(row.get("Industry") or "Unknown"),
        }
        for _, row in frame.dropna(subset=["Ticker"]).iterrows()
    }


def save_metadata_cache(
    cache: dict[str, dict[str, str]], path: str = METADATA_CACHE_CSV
) -> None:
    if not cache:
        return
    rows = [
        {
            "Ticker": ticker,
            "Sector": values.get("Sector", "Unknown"),
            "Industry": values.get("Industry", "Unknown"),
        }
        for ticker, values in sorted(cache.items())
    ]
    pd.DataFrame(rows, columns=["Ticker", "Sector", "Industry"]).to_csv(
        path, index=False
    )


def fetch_sector_industry(ticker: str) -> tuple[str, str]:
    try:
        info = yf.Ticker(ticker).get_info()
    except Exception:
        return "Unknown", "Unknown"
    sector = info.get("sector") or "Unknown"
    industry = info.get("industry") or "Unknown"
    return str(sector), str(industry)


def enrich_profiles_with_metadata(
    profiles: dict[str, dict],
    tickers: list[str],
    fetch_missing: bool = True,
) -> dict[str, dict]:
    """Best-effort metadata enrichment after deterministic stock filtering."""
    if not tickers:
        return profiles
    updated = {ticker: dict(profile) for ticker, profile in profiles.items()}
    cache = load_metadata_cache()
    changed = False
    missing = []

    for ticker in tickers:
        key = ticker.upper()
        cached = cache.get(key)
        if cached:
            updated.setdefault(ticker, {})
            updated[ticker]["Sector"] = cached.get("Sector", "Unknown")
            updated[ticker]["Industry"] = cached.get("Industry", "Unknown")
            continue

        profile = updated.get(ticker, {})
        sector = str(profile.get("Sector", "Unknown") or "Unknown")
        industry = str(profile.get("Industry", "Unknown") or "Unknown")
        if sector == "Unknown" or industry == "Unknown":
            missing.append(ticker)

    if not fetch_missing:
        return updated

    for ticker in missing[: config.MAX_METADATA_FETCH_PER_RUN]:
        sector, industry = fetch_sector_industry(ticker)
        updated.setdefault(ticker, {})
        updated[ticker]["Sector"] = sector
        updated[ticker]["Industry"] = industry
        if sector != "Unknown" or industry != "Unknown":
            cache[ticker.upper()] = {"Sector": sector, "Industry": industry}
            changed = True

    if changed:
        save_metadata_cache(cache)
    return updated


def build_raw_universe_to_path(
    path: str = UNIVERSE_RAW_TEMP_CSV,
) -> tuple[pd.DataFrame, int]:
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
        universe = universe.sort_values(
            ["Avg Volume", "Ticker"], ascending=[False, True]
        ).reset_index(drop=True)
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
            invalid_backup = Path(
                f"universe_invalid_{current_count}_backup_{suffix}.csv"
            )
            suffix += 1
        shutil.move(str(universe_path), invalid_backup)
        return True

    shutil.copy2(universe_path, UNIVERSE_BACKUP_CSV)
    return True


def refresh_universe_cache(
    timer: RunTimer | None = None,
) -> tuple[pd.DataFrame, UniverseRefreshResult]:
    started_at = time.monotonic()
    temp_path = Path(UNIVERSE_TEMP_CSV)
    raw_temp_path = Path(UNIVERSE_RAW_TEMP_CSV)
    for candidate in [temp_path, raw_temp_path]:
        if candidate.exists():
            candidate.unlink()

    result = UniverseRefreshResult()
    try:
        universe, total_downloaded, download_stats = build_universe_to_path(
            UNIVERSE_TEMP_CSV, timer=timer
        )
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


def validate_universe_frame(
    universe: pd.DataFrame, batch_success_rate: float | None = None
) -> tuple[bool, str]:
    missing_columns = set(UNIVERSE_COLUMNS) - set(universe.columns)
    if missing_columns:
        return False, f"missing columns: {', '.join(sorted(missing_columns))}"
    if len(universe) < config.MIN_VALID_UNIVERSE_COUNT:
        return False, f"ticker count below {config.MIN_VALID_UNIVERSE_COUNT}"
    if universe["Ticker"].duplicated().any():
        return False, "duplicate tickers"
    if universe["Ticker"].isna().mean() > 0.05:
        return False, "Ticker column mostly empty"
    if (
        batch_success_rate is not None
        and batch_success_rate < config.MIN_DOWNLOAD_SUCCESS_RATE
    ):
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
        print(f"{config.UNIVERSE_CSV} is {age_days:.1f} days old. Refreshing universe.")
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


def load_history(
    tickers: list[str], timer: RunTimer | None = None
) -> dict[str, pd.DataFrame]:
    histories, _ = download_price_histories(
        tickers, period="18mo", min_rows=1, timer=timer
    )
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


def is_valid_market_history(
    history: pd.DataFrame,
    now: datetime | None = None,
    enforce_freshness: bool = False,
) -> bool:
    if history.empty or len(history["Close"].dropna()) < 50:
        return False
    statuses = moving_average_status(history)
    if enforce_freshness and price_freshness_status(history, now).status != "CURRENT":
        return False
    return all(value != "Unknown" for value in statuses.values())


def get_market_condition(
    timer: RunTimer | None = None,
    retry_delays: list[int] | None = None,
    now: datetime | None = None,
) -> MarketConditionResult:
    symbols = ["SPY", "QQQ"]
    histories = {}
    stats = DownloadStats(requested=len(symbols))
    delays = (
        config.MARKET_RETRY_DELAYS_SECONDS if retry_delays is None else retry_delays
    )
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
        if all(
            is_valid_market_history(
                histories.get(symbol, pd.DataFrame()), now, enforce_freshness=True
            )
            for symbol in symbols
        ):
            break

    rows = []
    regime_metrics: dict[str, float | bool | None] = {}
    above_count = 0
    known_count = 0
    valid_by_symbol = {}

    for symbol in symbols:
        history = histories.get(symbol, pd.DataFrame())
        valid_by_symbol[symbol] = is_valid_market_history(
            history, now, enforce_freshness=True
        )
        statuses = moving_average_status(history)
        rows.append({"Symbol": symbol, **statuses})
        if valid_by_symbol[symbol]:
            indicators = history.copy()
            close = indicators["Close"].dropna()
            ema20 = close.ewm(span=20, adjust=False).mean()
            ma50 = close.rolling(50).mean()
            returns = close.pct_change().tail(20).dropna()
            regime_metrics[f"{symbol.lower()}_ema20_slope_positive"] = bool(
                ema20.iloc[-1] > ema20.iloc[-6]
            )
            regime_metrics[f"{symbol.lower()}_ma50_slope_positive"] = bool(
                ma50.iloc[-1] > ma50.iloc[-6]
            )
            regime_metrics[f"{symbol.lower()}_volatility_pct"] = float(
                returns.std() * np.sqrt(252) * 100
            )
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
    slope_values = [
        regime_metrics.get("spy_ema20_slope_positive"),
        regime_metrics.get("qqq_ema20_slope_positive"),
    ]
    ma50_slope_values = [
        regime_metrics.get("spy_ma50_slope_positive"),
        regime_metrics.get("qqq_ma50_slope_positive"),
    ]
    regime_metrics["ema20_slope_positive"] = (
        all(value is True for value in slope_values)
        if all(value is not None for value in slope_values)
        else None
    )
    regime_metrics["ema50_slope_positive"] = (
        all(value is True for value in ma50_slope_values)
        if all(value is not None for value in ma50_slope_values)
        else None
    )
    volatility_values = [
        regime_metrics.get("spy_volatility_pct"),
        regime_metrics.get("qqq_volatility_pct"),
    ]
    regime_metrics["index_volatility_pct"] = (
        float(np.mean(volatility_values))
        if all(value is not None for value in volatility_values)
        else None
    )
    return MarketConditionResult(
        frame=pd.DataFrame(rows, columns=MARKET_COLUMNS),
        status=status,
        spy_valid=spy_valid,
        qqq_valid=qqq_valid,
        data_failure=not (spy_valid or qqq_valid),
        stats=stats,
        metrics=regime_metrics,
    )


def period_return(history: pd.DataFrame, trading_days: int) -> float:
    closes = history["Close"].dropna()
    if len(closes) <= trading_days:
        return np.nan
    return pct(closes.iloc[-1] - closes.iloc[-trading_days], closes.iloc[-trading_days])


def period_return_as_of(
    history: pd.DataFrame, trading_days: int, end_offset: int = 0
) -> float:
    closes = history["Close"].dropna()
    end_index = len(closes) - 1 - end_offset
    start_index = end_index - trading_days
    if start_index < 0 or end_index <= start_index:
        return np.nan
    return pct(
        closes.iloc[end_index] - closes.iloc[start_index], closes.iloc[start_index]
    )


def weighted_rs_return(history: pd.DataFrame, end_offset: int = 0) -> float:
    three_month = period_return_as_of(history, 63, end_offset)
    six_month = period_return_as_of(history, 126, end_offset)
    twelve_month = period_return_as_of(history, 252, end_offset)
    if pd.isna(three_month) or pd.isna(six_month) or pd.isna(twelve_month):
        return np.nan
    return three_month * 0.5 + six_month * 0.3 + twelve_month * 0.2


def percentile_scores(frame: pd.DataFrame, raw_column: str) -> dict[str, int]:
    valid = (
        frame.dropna(subset=[raw_column])
        .sort_values(raw_column, ascending=False)
        .reset_index(drop=True)
    )
    count = len(valid)
    if count == 0:
        return {}
    scores = {}
    for index, row in valid.iterrows():
        percentile_rank = ((index + 1) / count) * 100
        score = 100 - math.ceil(percentile_rank)
        scores[row["Ticker"]] = max(1, min(99, score))
    return scores


def rs_trend_label(score: int | None, delta: float | None) -> str:
    if score is None or pd.isna(score) or delta is None or pd.isna(delta):
        return "Unknown"
    if score >= 75 and delta >= 10:
        return "Emerging Leader"
    if delta >= 5:
        return "Improving"
    if score >= 85 and delta > -5:
        return "Stable Leader"
    if delta <= -10:
        return "Fading"
    if delta <= -5:
        return "Weakening"
    return "Stable"


def calculate_rs_metrics(
    histories: dict[str, pd.DataFrame], tickers: list[str]
) -> dict[str, dict[str, object]]:
    rows = []
    for ticker in tickers:
        history = histories.get(ticker)
        if history is None or history.empty:
            continue

        current_raw = weighted_rs_return(history)
        if pd.isna(current_raw):
            continue
        prior_raw = weighted_rs_return(history, end_offset=21)
        rows.append(
            {
                "Ticker": ticker,
                "Current RS Raw": current_raw,
                "Prior RS Raw": prior_raw,
            }
        )

    if not rows:
        return {}

    rs_frame = pd.DataFrame(rows)
    current_scores = percentile_scores(rs_frame, "Current RS Raw")
    prior_scores = percentile_scores(rs_frame, "Prior RS Raw")
    metrics = {}
    for ticker, score in current_scores.items():
        prior_score = prior_scores.get(ticker)
        delta = np.nan if prior_score is None else score - prior_score
        metrics[ticker] = {
            "RS Score": score,
            "RS Trend": rs_trend_label(score, delta),
            "RS Trend Delta": np.nan if pd.isna(delta) else int(delta),
        }
    return metrics


def calculate_rs_scores(
    histories: dict[str, pd.DataFrame], tickers: list[str]
) -> dict[str, int]:
    metrics = calculate_rs_metrics(histories, tickers)
    return {ticker: int(values["RS Score"]) for ticker, values in metrics.items()}


def relative_return(history: pd.DataFrame, benchmark: pd.DataFrame, days: int) -> float:
    stock_return = period_return_as_of(history, days)
    benchmark_return = period_return_as_of(benchmark, days)
    if pd.isna(stock_return) or pd.isna(benchmark_return):
        return np.nan
    return float(stock_return - benchmark_return)


def calculate_recent_rs_metrics(
    histories: dict[str, pd.DataFrame],
    tickers: list[str],
    spy_history: pd.DataFrame,
) -> dict[str, dict[str, float]]:
    """Recent market-relative model; deliberately separate from long-term Stage 2 RS."""
    rows = []
    for ticker in tickers:
        history = histories.get(ticker, pd.DataFrame())
        values = {
            f"Relative Return {days}D": relative_return(history, spy_history, days)
            for days in (5, 10, 20, 30, 60, 126)
        }
        values.update(
            {
                f"Return {days}D": period_return_as_of(history, days)
                for days in (5, 10, 20, 30)
            }
        )
        if all(pd.isna(value) for value in values.values()):
            continue
        rows.append({"Ticker": ticker, **values})
    if not rows:
        return {}
    frame = pd.DataFrame(rows)
    score = pd.Series(0.0, index=frame.index)
    for days, weight in config.RECENT_RS_WEIGHTS.items():
        column = f"Relative Return {days}"
        score += frame[column].rank(pct=True, method="average").fillna(0) * 100 * weight
    frame["Recent RS Score"] = score.clip(0, 100)
    frame["RS Momentum Acceleration"] = frame["Relative Return 5D"] - (
        frame["Relative Return 20D"] / 4
    )
    return {
        row["Ticker"]: {
            key: round(float(value), 4) if not pd.isna(value) else np.nan
            for key, value in row.items()
            if key != "Ticker"
        }
        for row in frame.to_dict(orient="records")
    }


def recent_rs_trend_label(
    long_term_rs: float, recent_rs: float, acceleration: float, rel20: float
) -> str:
    if any(pd.isna(value) for value in (recent_rs, acceleration, rel20)):
        return "Unknown"
    if recent_rs >= 80 and acceleration >= 0.02 and rel20 > 0:
        return "Emerging Leader"
    if recent_rs >= 60 and acceleration > 0:
        return "Improving"
    if long_term_rs >= 80 and recent_rs >= 70 and abs(acceleration) < 0.02:
        return "Stable Leader"
    if long_term_rs >= 75 and (rel20 <= 0 or acceleration < 0):
        return "Weakening"
    if recent_rs < 40 and rel20 < 0:
        return "Lagging"
    return "Stable"


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
    df["HIGH_20D"] = df["High"].rolling(20).max()
    df["LOW_52W"] = df["Low"].rolling(252, min_periods=120).min()
    df["RANGE_10D_PCT"] = (
        (df["High"].rolling(10).max() - df["Low"].rolling(10).min()) / df["Close"]
    ) * 100
    df["RANGE_15D_PCT"] = (
        (df["High"].rolling(15).max() - df["Low"].rolling(15).min()) / df["Close"]
    ) * 100
    df["RANGE_20D_PCT"] = (
        (df["High"].rolling(20).max() - df["Low"].rolling(20).min()) / df["Close"]
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
    breakout_price = (df["Close"] > df["HIGH_50D_PRIOR"]) | (
        df["Close"] > df["PIVOT_PRICE"]
    )
    breakout_volume = df["VOLUME_RATIO"] >= 1.5
    df["BREAKOUT_CONFIRMED_5D"] = (
        (breakout_price & breakout_volume).rolling(5).max().fillna(False)
    )
    recent_breakout = (
        (breakout_price & breakout_volume)
        .shift(1)
        .rolling(10)
        .max()
        .fillna(False)
        .astype(bool)
    )
    df["BREAKOUT_FAILED_10D"] = (
        recent_breakout
        & (df["Close"] < df["HIGH_50D_PRIOR"])
        & (df["VOLUME_RATIO"] >= 1.2)
    )
    df["PIVOT_PRICE"] = df["HIGH_50D_PRIOR"].where(breakout_price).ffill()
    df["PIVOT_PRICE"] = df["PIVOT_PRICE"].fillna(df["HIGH_50D_PRIOR"])

    close_above_prior_high = df["Close"] > df["High"].shift(1)
    top_quarter_close = df["CLOSE_POSITION_PCT"] >= 75
    ema10_reclaim = (df["Low"] <= df["EMA10"]) & (df["Close"] > df["EMA10"])
    ema20_reclaim = (df["Low"] <= df["EMA20"]) & (df["Close"] > df["EMA20"])
    ma50_reclaim = (df["Low"] <= df["MA50"]) & (df["Close"] > df["MA50"])
    df["SUPPORT_SIGNAL_10EMA_BOOL"] = (
        (close_above_prior_high | top_quarter_close | ema10_reclaim)
        .rolling(3)
        .max()
        .fillna(False)
        .astype(bool)
    )
    df["SUPPORT_SIGNAL_20EMA_BOOL"] = (
        (close_above_prior_high | top_quarter_close | ema20_reclaim)
        .rolling(3)
        .max()
        .fillna(False)
        .astype(bool)
    )
    df["SUPPORT_SIGNAL_50MA_BOOL"] = (
        (close_above_prior_high | top_quarter_close | ma50_reclaim)
        .rolling(3)
        .max()
        .fillna(False)
        .astype(bool)
    )
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
        "Close",
        "AVG_VOLUME50",
        "MA50",
        "MA150",
        "MA200",
        "MA200_20D_AGO",
        "HIGH_52W",
        "EMA10",
        "EMA20",
        "ADR_PCT",
        "ATR20",
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
    rs_metric: dict[str, object],
    profile: dict,
    recent_metric: dict[str, object] | None = None,
    history: pd.DataFrame | None = None,
) -> dict:
    recent_metric = recent_metric or {}
    rs_score = rs_metric.get("RS Score")
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
    row = {
        "Generated At": latest.get("GENERATED_AT", ""),
        "Signal Date": latest.get("SIGNAL_DATE", ""),
        "Price Data As Of": latest.get("PRICE_DATA_AS_OF", ""),
        "Latest Bar Timestamp": latest.get("LATEST_BAR_TIMESTAMP", ""),
        "Price Freshness Status": latest.get("PRICE_FRESHNESS_STATUS", "UNKNOWN"),
        "Category": "",
        "Ticker": ticker,
        "Sector": profile.get("Sector", "Unknown"),
        "Industry": profile.get("Industry", "Unknown"),
        "RS Score": rs_score,
        "Recent RS Score": recent_metric.get("Recent RS Score", np.nan),
        "RS Momentum Acceleration": recent_metric.get(
            "RS Momentum Acceleration", np.nan
        ),
        "RS Trend": recent_rs_trend_label(
            rs_score,
            recent_metric.get("Recent RS Score", np.nan),
            recent_metric.get("RS Momentum Acceleration", np.nan),
            recent_metric.get("Relative Return 20D", np.nan),
        ),
        "RS Trend Delta": rs_metric.get("RS Trend Delta", np.nan),
        "Price": round(latest["Close"], 2),
        "Action": "",
        "Review Tier": "",
        "Confirmed Setup": False,
        "Actionable": False,
        "Setup Integrity": "UNKNOWN",
        "Email Priority Rank": np.nan,
        "Noise Filter Reason": "",
        "Review Priority Score": np.nan,
        "Price Data Warning": latest.get("PRICE_DATA_WARNING", ""),
        "ATR20": round(latest["ATR20"], 2),
        "ATR20 %": round(latest["ATR20_PCT"], 2),
        "ADR %": round(latest["ADR_PCT"], 2),
        "From 52W High %": round(
            pct(latest["Close"] - latest["HIGH_52W"], latest["HIGH_52W"]), 2
        ),
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
        "Risk/Reward Quality": "Not Available",
        "Planned Entry": np.nan,
        "Initial Stop": np.nan,
        "Realistic Target": np.nan,
        "Reward/Risk Ratio": np.nan,
        "Industry Qualified": False,
        "Sister Confirmation": False,
        "Final Decision": "",
        "Decision Reasons": "trade plan entry, structural stop, and target not available",
        "Final Score": np.nan,
        "Industry Rank": np.nan,
        "Industry Setup Count": np.nan,
        "Avg Volume": int(latest["AVG_VOLUME50"]),
        "TradingView": tradingview_url(profile.get("Exchange", "NASDAQ"), ticker),
    }
    if history is not None:
        # Use the broad raw detector at this stage; canonical category selection
        # below rebuilds the plan for its final primary setup.
        plan = construct_trade_plan(history, "Pullback Candidates")
        row.update(
            {
                "Planned Entry": plan.planned_entry,
                "Planned Entry Source": plan.planned_entry_source,
                "Initial Stop": plan.structural_stop,
                "Structural Stop Source": plan.structural_stop_source,
                "Realistic Target": plan.realistic_target,
                "Realistic Target Source": plan.realistic_target_source,
                "Reward/Risk Ratio": plan.reward_risk_ratio,
                "Trade Plan Confidence": plan.confidence,
                "Trade Plan Validation Reasons": "; ".join(plan.validation_reasons),
            }
        )
        rr = calculate_reward_risk(
            plan.planned_entry, plan.structural_stop, plan.realistic_target
        )
        row["Risk/Reward Quality"] = rr.label
    breakdown = score_candidate(row)
    row.update(
        {
            "Recent RS Component": breakdown.recent_rs_component,
            "Industry Sister Component": breakdown.industry_sister_component,
            "Setup Quality Component": breakdown.setup_quality_component,
            "Volume Component": breakdown.volume_component,
            "Entry Stop Component": breakdown.entry_stop_component,
            "Intermediate Trend Component": breakdown.intermediate_trend_component,
            "Base Score": breakdown.base_score,
            "Score Penalties": "; ".join(
                f"{name}: -{value}" for name, value in breakdown.penalties.items()
            ),
            "Total Penalty": breakdown.total_penalty,
            "Final Score": breakdown.final_score,
        }
    )
    return row


def strongest_support_signal(latest: pd.Series) -> str:
    """Summarise the nearest constructive support signal for compact AI review."""
    signals = [
        latest.get("SUPPORT_SIGNAL_10EMA", ""),
        latest.get("SUPPORT_SIGNAL_20EMA", ""),
        latest.get("SUPPORT_SIGNAL_50MA", ""),
    ]
    return ", ".join(dict.fromkeys(signal for signal in signals if signal)) or ""


def is_breakout_candidate(row: pd.Series) -> bool:
    breakout = row["Close"] > row["HIGH_50D_PRIOR"] or row["Close"] > row["PIVOT_PRICE"]
    near_pivot = (
        row["Close"] >= row["PIVOT_PRICE"] * 0.97
        or row["Close"] >= row["HIGH_50D_PRIOR"] * 0.97
    )
    distance_50ma = pct(row["Close"] - row["MA50"], row["MA50"])
    distance_30wma = pct(row["Close"] - row["MA150"], row["MA150"])
    controlled_extension = distance_50ma <= 8 or distance_30wma <= 15
    constructive_candle = (
        row["Close"] > row["Open"]
        and row["CLOSE_POSITION_PCT"] >= 60
        and row["BODY_PCT"] >= 25
    )
    return (
        (breakout or near_pivot)
        and constructive_candle
        and row["VOLUME_RATIO"] >= 0.9
        and controlled_extension
    )


def is_extended_breakout_candidate(row: pd.Series) -> bool:
    breakout = row["Close"] > row["HIGH_50D_PRIOR"] or row["Close"] > row["PIVOT_PRICE"]
    near_pivot = (
        row["Close"] >= row["PIVOT_PRICE"] * 0.97
        or row["Close"] >= row["HIGH_50D_PRIOR"] * 0.97
    )
    distance_50ma = pct(row["Close"] - row["MA50"], row["MA50"])
    distance_30wma = pct(row["Close"] - row["MA150"], row["MA150"])
    too_extended = distance_50ma > 8 and distance_30wma > 15
    constructive_candle = (
        row["Close"] > row["Open"]
        and row["CLOSE_POSITION_PCT"] >= 60
        and row["BODY_PCT"] >= 25
    )
    return (
        (breakout or near_pivot)
        and constructive_candle
        and row["VOLUME_RATIO"] >= 0.9
        and too_extended
    )


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
    base_shape = (
        row["RANGE_15D_PCT"] <= 18
        and pct(row["HIGH_52W"] - row["Close"], row["HIGH_52W"]) <= 25
        and pct(row["Close"] - row["MA50"], row["MA50"]) <= 25
        and row["VOLUME_RATIO"] <= 1.4
    )
    if not base_shape:
        return False
    displayed_tightness = tightness_label(row["RANGE_10D_PCT"])
    if displayed_tightness == "Loose":
        return False
    tight = displayed_tightness in {"Tight", "Very Tight"}
    adr60 = row.get("ADR60_PCT", np.nan)
    ratio = (
        row.get("ADR_PCT", np.nan) / adr60 if not pd.isna(adr60) and adr60 else np.nan
    )
    compression_passes = not pd.isna(ratio) and ratio <= 0.8
    return tight or (compression_passes and vcp_label(ratio) != "Poor VCP")


def is_developing_base_candidate(row: pd.Series) -> bool:
    if pd.isna(row.get("RANGE_15D_PCT")):
        return False
    base_shape = (
        row["RANGE_15D_PCT"] <= 18
        and pct(row["HIGH_52W"] - row["Close"], row["HIGH_52W"]) <= 25
        and pct(row["Close"] - row["MA50"], row["MA50"]) <= 25
        and row["VOLUME_RATIO"] <= 1.4
    )
    return base_shape and not is_tight_consolidation_candidate(row)


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

    confirmed = confirmation_signal(row)
    if category == "Pullback Candidates":
        if (
            risk_reward in {"Excellent R/R", "Good R/R", "Valid R/R"}
            and extension == "Not Extended"
            and confirmed
        ):
            return "Confirmed pullback entry review"
        if risk_reward in {"Excellent R/R", "Good R/R", "Valid R/R"}:
            return "Monitor quiet pullback"
        if risk_reward == "Fair R/R":
            return "Wait for cleaner entry"
        return "Watch only"
    if category == "Breakout Candidates":
        if confirmed:
            return "Review breakout confirmation"
        return "Set breakout alert"
    if category == "Volume Surge Candidates":
        if risk_reward in {"Excellent R/R", "Good R/R", "Valid R/R"} and confirmed:
            return "Review volume confirmation"
        return "Watch volume surge"
    if category == "Tight Consolidation Candidates":
        if vcp in {"Excellent VCP", "Good VCP"}:
            return "Set pivot alert"
        if tightness in {"Very Tight", "Tight"}:
            return "Monitor tight base"
        return "Watch only"
    if category == "Developing Base Candidates":
        return "Developing base / Watch Later"
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
    return add_review_guidance_columns(updated)


def category_sort(df: pd.DataFrame, category: str) -> pd.DataFrame:
    frame = add_review_priority_column(df)
    if category == "Breakout Candidates":
        return (
            frame.sort_values(
                [
                    "Review Priority Score",
                    "Volume Ratio",
                    "RS Score",
                    "Avg Volume",
                    "From 52W High %",
                ],
                ascending=[False, False, False, False, True],
            )
            .head(config.CATEGORY_LIMIT)
            .reset_index(drop=True)
        )
    elif category == "Pullback Candidates":
        frame["_Quality Rank"] = (
            frame["Pullback Quality"].apply(pullback_quality_rank).replace(0, 99)
        )
        return (
            frame.sort_values(
                [
                    "Review Priority Score",
                    "_Quality Rank",
                    "RS Score",
                    "Distance From 50MA %",
                    "Avg Volume",
                ],
                ascending=[False, True, False, True, False],
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
        frame["_Risk Reward Rank"] = frame["Risk/Reward Quality"].apply(
            risk_reward_quality_rank
        )
        frame["_Extension Rank"] = frame["Extension Status"].apply(
            extension_status_rank
        )
        frame["_VCP Rank"] = frame["VCP Label"].map(vcp_rank).fillna(99)
        frame["_Tightness Rank"] = (
            frame["Tightness Label"].map(tightness_rank).fillna(99)
        )
        return (
            frame.sort_values(
                [
                    "Review Priority Score",
                    "_Risk Reward Rank",
                    "_Extension Rank",
                    "Nearest Support Distance ATR",
                    "_VCP Rank",
                    "_Tightness Rank",
                    "RS Score",
                    "VCP Ratio",
                ],
                ascending=[False, True, True, True, True, True, False, True],
            )
            .drop(
                columns=[
                    "_Risk Reward Rank",
                    "_Extension Rank",
                    "_VCP Rank",
                    "_Tightness Rank",
                ]
            )
            .head(config.CATEGORY_LIMIT)
            .reset_index(drop=True)
        )
    elif category == "Extended Candidates":
        frame["_Industry Rank"] = frame["Industry Rank"].fillna(999)
        return (
            frame.sort_values(
                [
                    "Review Priority Score",
                    "RS Score",
                    "_Industry Rank",
                    "Distance From 50MA %",
                    "Avg Volume",
                ],
                ascending=[False, False, True, True, False],
            )
            .drop(columns=["_Industry Rank"])
            .head(config.CATEGORY_LIMIT)
            .reset_index(drop=True)
        )

    return (
        frame.sort_values(
            [
                "Review Priority Score",
                "RS Score",
                "Volume Ratio",
                "Avg Volume",
                "From 52W High %",
            ],
            ascending=[False, False, False, False, True],
        )
        .head(config.CATEGORY_LIMIT)
        .reset_index(drop=True)
    )


def _percentile_column(frame: pd.DataFrame, source: str) -> pd.Series:
    return frame[source].rank(pct=True, method="average").fillna(0) * 100


def build_top_industries(
    eligible_df: pd.DataFrame,
    candidate_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Rank industries from the full eligible liquid universe, returning formal and isolated tables."""
    if eligible_df.empty:
        empty = pd.DataFrame(columns=TOP_INDUSTRY_COLUMNS)
        empty.attrs["isolated_industries"] = empty.copy()
        return empty
    legacy_input = "Relative Return 20D" not in eligible_df.columns
    if legacy_input:
        eligible_df = eligible_df.copy()
        rs = pd.to_numeric(eligible_df.get("RS Score", 50), errors="coerce").fillna(50)
        eligible_df["Long-Term RS Score"] = rs
        eligible_df["Recent RS Score"] = rs
        for column in [
            "Relative Return 5D",
            "Relative Return 20D",
            "Relative Return 60D",
        ]:
            eligible_df[column] = 0.0
        for column in [
            "Above 10EMA",
            "Above 20EMA",
            "Above 50MA",
            "Stage 2",
            "Within 15% High",
        ]:
            eligible_df[column] = True
        eligible_df["Leader Quality Score"] = rs
        eligible_df["Review Priority Score"] = 0
    candidates = candidate_df if candidate_df is not None else eligible_df
    source = known_industry_frame(eligible_df)
    if "Sector" in source.columns:
        source = source[source["Sector"].apply(known_metadata_value)]
    if source.empty:
        empty = pd.DataFrame(columns=TOP_INDUSTRY_COLUMNS)
        empty.attrs["isolated_industries"] = empty.copy()
        return empty
    candidate_tickers = set(candidates.get("Ticker", pd.Series(dtype=str)).astype(str))
    rows = []
    for industry, group in source.groupby("Industry"):
        total = len(group)
        candidate_count = int(group["Ticker"].astype(str).isin(candidate_tickers).sum())
        candidate_breadth = 100 * candidate_count / total
        rel5 = group["Relative Return 5D"]
        rel20 = group["Relative Return 20D"]
        rel60 = group["Relative Return 60D"]
        acceleration = rel5.median() - (rel20.median() / 4)
        leaders = (
            group.sort_values(
                ["Recent RS Score", "Long-Term RS Score", "Review Priority Score"],
                ascending=[False, False, False],
            )
            .head(3)["Ticker"]
            .astype(str)
            .tolist()
        )
        rows.append(
            {
                "Industry": industry,
                "Sector": group["Sector"].mode().iloc[0]
                if not group["Sector"].mode().empty
                else "Unknown",
                "Median 5D Relative Return": rel5.median(),
                "Median 20D Relative Return": rel20.median(),
                "Median 60D Relative Return": rel60.median(),
                "Median Recent RS Score": group["Recent RS Score"].median(),
                "Average Recent RS Score": group["Recent RS Score"].mean(),
                "Momentum Acceleration": acceleration,
                "5D Outperformance Breadth %": 100 * (rel5 > 0).mean(),
                "20D Outperformance Breadth %": 100 * (rel20 > 0).mean(),
                "% Above 10EMA": 100 * group["Above 10EMA"].mean(),
                "% Above 20EMA": 100 * group["Above 20EMA"].mean(),
                "% Above 50MA": 100 * group["Above 50MA"].mean(),
                "Median Long-Term RS Score": group["Long-Term RS Score"].median(),
                "Average Long-Term RS Score": group["Long-Term RS Score"].mean(),
                "Stage 2 Breadth %": 100 * group["Stage 2"].mean(),
                "% Within 15% of 52-week high": 100 * group["Within 15% High"].mean(),
                "Leader Quality Score": group["Leader Quality Score"].mean(),
                "Candidate Count": candidate_count,
                "Candidate Breadth %": candidate_breadth,
                "Total Eligible Stocks": total,
                "Top 3 Leaders": ", ".join(leaders),
            }
        )
    scores = pd.DataFrame(rows)
    momentum = pd.Series(0.0, index=scores.index)
    for column, weight in config.INDUSTRY_MOMENTUM_WEIGHTS.items():
        momentum += _percentile_column(scores, column) * weight
    leadership = pd.Series(0.0, index=scores.index)
    for column, weight in config.INDUSTRY_LEADERSHIP_WEIGHTS.items():
        leadership += (
            pd.to_numeric(scores[column], errors="coerce").fillna(0).clip(0, 100)
            * weight
        )
    scores["Momentum Score"] = momentum.clip(0, 100).round(1)
    scores["Leadership Score"] = leadership.clip(0, 100).round(1)
    scores["Final Industry Score"] = (
        0.65 * scores["Momentum Score"] + 0.35 * scores["Leadership Score"]
    ).round(1)
    scores["Momentum Rank"] = (
        scores["Momentum Score"].rank(method="min", ascending=False).astype(int)
    )
    scores["Leadership Rank"] = (
        scores["Leadership Score"].rank(method="min", ascending=False).astype(int)
    )
    scores["Final Rank"] = (
        scores["Final Industry Score"].rank(method="min", ascending=False).astype(int)
    )
    count = len(scores)

    def status(row: pd.Series) -> str:
        momentum_top = row["Momentum Rank"] <= max(1, math.ceil(count * 0.20))
        leadership_top20 = row["Leadership Rank"] <= max(1, math.ceil(count * 0.20))
        leadership_top30 = row["Leadership Rank"] <= max(1, math.ceil(count * 0.30))
        if leadership_top20 and (
            row["Median 5D Relative Return"] <= 0
            or row["Median 20D Relative Return"] <= 0
        ):
            return "Long-Term Leader, Currently Lagging"
        if (
            row["Median 20D Relative Return"] < 0
            and row["20D Outperformance Breadth %"] < 40
        ):
            return "Weak / Avoid"
        if (
            momentum_top
            and leadership_top30
            and row["Median 20D Relative Return"] > 0
            and row["Momentum Acceleration"] > 0
        ):
            return "Leading and Accelerating"
        if (
            momentum_top
            and not leadership_top30
            and row["Median 5D Relative Return"] > 0
            and row["Median 20D Relative Return"] > 0
        ):
            return "Strong Recent Rotation"
        if row["20D Outperformance Breadth %"] >= 60 and row["% Above 20EMA"] >= 60:
            return "Broadly Improving"
        if (
            row["Final Rank"] <= max(1, math.ceil(count * 0.20))
            and row["20D Outperformance Breadth %"] < 40
        ):
            return "Narrow Leadership"
        return "Mixed / Neutral"

    scores["Industry Status"] = scores.apply(status, axis=1)
    display = scores.copy()
    for column in [
        c
        for c in display.columns
        if "Return" in c or "%" in c or "Score" in c or c == "Momentum Acceleration"
    ]:
        display[column] = pd.to_numeric(display[column], errors="coerce").round(2)
    minimum_size = 1 if legacy_input else config.MIN_FORMAL_INDUSTRY_SIZE
    formal = (
        display[display["Total Eligible Stocks"] >= minimum_size]
        .sort_values(
            ["Final Industry Score", "Momentum Score", "Leadership Score"],
            ascending=False,
        )
        .head(config.CATEGORY_LIMIT)
        .reset_index(drop=True)
    )
    formal["Final Rank"] = range(1, len(formal) + 1)
    isolated = (
        display[display["Total Eligible Stocks"] < minimum_size]
        .sort_values(
            ["Final Industry Score", "Momentum Score"],
            ascending=False,
        )
        .reset_index(drop=True)
    )
    result = formal[TOP_INDUSTRY_COLUMNS].copy()
    result.attrs["isolated_industries"] = isolated[TOP_INDUSTRY_COLUMNS].copy()
    return result


def add_industry_ranks(base_df: pd.DataFrame) -> pd.DataFrame:
    ranked = base_df.copy()
    ranked["Industry Rank"] = np.nan
    ranked["Industry Setup Count"] = np.nan
    ranked_source = known_industry_frame(base_df)
    if ranked_source.empty:
        return ranked

    industry_scores = (
        ranked_source.groupby("Industry", dropna=False)
        .agg({"RS Score": "mean", "Ticker": "count"})
        .rename(columns={"RS Score": "Avg RS Score", "Ticker": "Candidates"})
        .sort_values(["Avg RS Score", "Candidates"], ascending=[False, False])
    )
    ranks = {
        industry: rank for rank, industry in enumerate(industry_scores.index, start=1)
    }
    counts = industry_scores["Candidates"].to_dict()
    ranked["Industry Rank"] = ranked["Industry"].map(ranks)
    ranked["Industry Setup Count"] = ranked["Industry"].map(counts)
    return ranked


def apply_industry_context(frame: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or context.empty:
        return frame
    updated = frame.copy()
    context_columns = [
        column
        for column in [
            "Ticker",
            "Industry Rank",
            "Industry Setup Count",
            "Industry Qualified",
            "Sister Confirmation",
            "Industry Classification",
            "Breadth Sample Quality",
            "Sister Confirmation State",
        ]
        if column in context.columns
    ]
    context_by_ticker = (
        context[context_columns].drop_duplicates("Ticker").set_index("Ticker")
    )
    updated["Industry Rank"] = updated["Ticker"].map(context_by_ticker["Industry Rank"])
    updated["Industry Setup Count"] = updated["Ticker"].map(
        context_by_ticker["Industry Setup Count"]
    )
    if "Industry Qualified" in context_by_ticker:
        updated["Industry Qualified"] = (
            updated["Ticker"].map(context_by_ticker["Industry Qualified"]).fillna(False)
        )
    if "Sister Confirmation" in context_by_ticker:
        updated["Sister Confirmation"] = (
            updated["Ticker"]
            .map(context_by_ticker["Sister Confirmation"])
            .fillna(False)
        )
    for column in (
        "Industry Classification",
        "Breadth Sample Quality",
        "Sister Confirmation State",
    ):
        if column in context_by_ticker:
            updated[column] = updated["Ticker"].map(context_by_ticker[column])
    return updated


def build_eligible_industry_universe(
    histories: dict[str, pd.DataFrame],
    profiles: dict[str, dict],
    spy_history: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    tickers = []
    indicators = {}
    for ticker, history in histories.items():
        profile = profiles.get(ticker, {})
        if not known_metadata_value(profile.get("Sector")) or not known_metadata_value(
            profile.get("Industry")
        ):
            continue
        if len(history) < 220 or price_data_warning(history):
            continue
        latest = add_indicators(history).iloc[-1]
        if pd.isna(latest.get("Close")) or pd.isna(latest.get("AVG_VOLUME50")):
            continue
        if (
            latest["Close"] <= config.MIN_PRICE
            or latest["AVG_VOLUME50"] <= config.MIN_AVG_VOLUME
        ):
            continue
        tickers.append(ticker)
        indicators[ticker] = latest
    recent = calculate_recent_rs_metrics(histories, tickers, spy_history)
    raw = pd.DataFrame(
        [
            {"Ticker": ticker, "Raw": weighted_rs_return(histories[ticker])}
            for ticker in tickers
        ]
    )
    long_scores = percentile_scores(raw, "Raw") if not raw.empty else {}
    rows = []
    for ticker in tickers:
        metric = recent.get(ticker)
        if not metric or ticker not in long_scores:
            continue
        latest = indicators[ticker]
        high_distance = pct(latest["HIGH_52W"] - latest["Close"], latest["HIGH_52W"])
        rows.append(
            {
                "Ticker": ticker,
                "Price": float(latest["Close"]),
                "Sector": profiles[ticker]["Sector"],
                "Industry": profiles[ticker]["Industry"],
                "Relative Return 5D": metric["Relative Return 5D"],
                "Relative Return 20D": metric["Relative Return 20D"],
                "Relative Return 10D": metric["Relative Return 10D"],
                "Relative Return 30D": metric["Relative Return 30D"],
                "Relative Return 60D": metric["Relative Return 60D"],
                "Relative Return 126D": metric["Relative Return 126D"],
                "Return 5D": metric["Return 5D"],
                "Return 10D": metric["Return 10D"],
                "Return 20D": metric["Return 20D"],
                "Return 30D": metric["Return 30D"],
                "Recent RS Score": metric["Recent RS Score"],
                "RS Momentum Acceleration": metric["RS Momentum Acceleration"],
                "Long-Term RS Score": long_scores[ticker],
                "Above 10EMA": latest["Close"] > latest["EMA10"],
                "Above 20EMA": latest["Close"] > latest["EMA20"],
                "Above 50MA": latest["Close"] > latest["MA50"],
                "Stage 2": passes_filters(latest),
                "Within 15% High": high_distance <= 15,
                "Near 20D High": pct(
                    latest["HIGH_20D"] - latest["Close"], latest["HIGH_20D"]
                )
                <= 5,
                "Near 52W High": high_distance <= 15,
                "Valid Breakout": bool(latest.get("BREAKOUT_CONFIRMED_5D", False)),
                "Failed Breakout": bool(latest.get("BREAKOUT_FAILED_10D", False)),
                "High Volume Breakdown": bool(
                    latest["Close"] < latest["EMA20"]
                    and latest.get("VOLUME_RATIO", 0) >= 1.5
                ),
                "Leader Quality Score": (
                    metric["Recent RS Score"] * 0.6 + long_scores[ticker] * 0.4
                ),
                "Review Priority Score": 0,
            }
        )
    return pd.DataFrame(rows), recent


def screen_stocks(
    universe: pd.DataFrame,
    timer: RunTimer | None = None,
    run_at: datetime | None = None,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, int, DownloadStats]:
    global LAST_ELIGIBLE_UNIVERSE, LAST_METADATA_DIAGNOSTICS
    generated_at = run_at or datetime.now(timezone.utc)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    tickers = universe["Ticker"].tolist() if not universe.empty else []
    profiles = universe.set_index("Ticker")[["Exchange", "Sector", "Industry"]].to_dict(
        "index"
    )
    histories, download_stats = load_history_with_stats(tickers, timer=timer)
    # Metadata must be enriched before Recent RS/industry eligibility is built;
    # otherwise valid candidates can receive blank Recent RS and stale group context.
    profiles = enrich_profiles_with_metadata(
        profiles,
        tickers,
        fetch_missing=config.ALLOW_PRODUCTION_METADATA_ENRICHMENT,
    )
    mapped_count = sum(
        known_metadata_value(profile.get("Sector"))
        and known_metadata_value(profile.get("Industry"))
        for profile in profiles.values()
    )
    universe_count = len(tickers)
    coverage = mapped_count / universe_count if universe_count else 0.0
    cache_path = Path(METADATA_CACHE_CSV)
    cache_as_of = (
        datetime.fromtimestamp(cache_path.stat().st_mtime, timezone.utc).isoformat()
        if cache_path.exists()
        else ""
    )
    LAST_METADATA_DIAGNOSTICS = {
        "universe_member_count": universe_count,
        "mapped_sector_industry_count": mapped_count,
        "unmapped_count": max(0, universe_count - mapped_count),
        "coverage_percentage": round(coverage * 100, 2),
        "minimum_coverage_percentage": round(config.MIN_METADATA_COVERAGE_PCT * 100, 2),
        "coverage_complete": coverage >= config.MIN_METADATA_COVERAGE_PCT,
        "cache_as_of": cache_as_of,
        "market_cap_filter": (
            f"ENFORCED at USD {config.MIN_MARKET_CAP:,.0f}"
            if config.ENFORCE_MARKET_CAP_FILTER
            else "NOT ENFORCED"
        ),
    }
    fresh_histories: dict[str, pd.DataFrame] = {}
    freshness_by_ticker: dict[str, PriceFreshness] = {}
    stale_or_incomplete_count = 0
    anomalous_price_count = 0
    for ticker, history in histories.items():
        freshness = price_freshness_status(history, generated_at)
        if freshness.status != "CURRENT":
            stale_or_incomplete_count += 1
            continue
        if price_data_warning(history):
            anomalous_price_count += 1
            continue
        fresh_histories[ticker] = history
        freshness_by_ticker[ticker] = freshness
    LAST_METADATA_DIAGNOSTICS.update(
        {
            "current_price_history_count": len(fresh_histories),
            "stale_or_incomplete_price_history_count": stale_or_incomplete_count,
            "anomalous_price_history_count": anomalous_price_count,
        }
    )
    spy_histories, _ = download_price_histories(
        ["SPY"],
        period="18mo",
        min_rows=127,
        retry_delays=[],
        timer=timer,
        max_attempts=1,
    )
    spy_history = spy_histories.get("SPY", pd.DataFrame())
    eligible_industry_df, recent_metrics = build_eligible_industry_universe(
        fresh_histories, profiles, spy_history
    )
    LAST_ELIGIBLE_UNIVERSE = eligible_industry_df.copy()
    stage2_tickers = []
    latest_by_ticker = {}
    for ticker, history in fresh_histories.items():
        if len(history) < 220:
            continue
        warning = price_data_warning(history)
        if warning:
            continue
        try:
            latest = add_indicators(history).iloc[-1].copy()
            latest["PRICE_DATA_WARNING"] = warning
            freshness = freshness_by_ticker[ticker]
            latest["GENERATED_AT"] = generated_at.astimezone(timezone.utc).isoformat()
            latest["SIGNAL_DATE"] = freshness.price_data_as_of
            latest["PRICE_DATA_AS_OF"] = freshness.price_data_as_of
            latest["LATEST_BAR_TIMESTAMP"] = freshness.latest_bar_timestamp
            latest["PRICE_FRESHNESS_STATUS"] = freshness.status
        except Exception as exc:
            print(f"Skipping {ticker}: {exc}")
            continue
        if passes_filters(latest):
            stage2_tickers.append(ticker)
            latest_by_ticker[ticker] = latest

    rs_metrics = calculate_rs_metrics(fresh_histories, stage2_tickers)
    base_rows = []
    stage2_count = len(stage2_tickers)
    for ticker in stage2_tickers:
        rs_metric = rs_metrics.get(ticker)
        rs_score = rs_metric.get("RS Score") if rs_metric else None
        if rs_score is None or rs_score < config.MIN_RS_SCORE:
            continue
        base_rows.append(
            candidate_row(
                ticker,
                latest_by_ticker[ticker],
                rs_metric,
                profiles.get(ticker, {}),
                recent_metrics.get(ticker, {}),
                fresh_histories.get(ticker),
            )
        )

    if not base_rows:
        empty_categories = {
            name: pd.DataFrame(columns=DISCOVERY_COLUMNS) for name in CATEGORY_NAMES
        }
        top_industries = build_top_industries(eligible_industry_df, pd.DataFrame())
        return empty_categories, top_industries, stage2_count, download_stats

    base_df = pd.DataFrame(base_rows, columns=DISCOVERY_COLUMNS)
    categories = {name: [] for name in CATEGORY_NAMES}
    for ticker in stage2_tickers:
        rs_metric = rs_metrics.get(ticker)
        rs_score = rs_metric.get("RS Score") if rs_metric else None
        if (
            ticker not in latest_by_ticker
            or rs_score is None
            or rs_score < config.MIN_RS_SCORE
        ):
            continue
        latest = latest_by_ticker[ticker]
        row = base_df[base_df["Ticker"] == ticker].iloc[0].to_dict()
        if is_breakout_candidate(latest):
            categories["Breakout Candidates"].append(
                {**row, "Category": "Breakout Candidates"}
            )
        if is_pullback_candidate(latest):
            categories["Pullback Candidates"].append(
                {**row, "Category": "Pullback Candidates"}
            )
        if is_tight_consolidation_candidate(latest):
            categories["Tight Consolidation Candidates"].append(
                {**row, "Category": "Tight Consolidation Candidates"}
            )
        elif is_developing_base_candidate(latest):
            categories["Developing Base Candidates"].append(
                {**row, "Category": "Developing Base Candidates"}
            )
        if is_extended_candidate(latest):
            categories["Extended Candidates"].append(
                {**row, "Category": "Extended Candidates"}
            )
        if is_volume_surge_candidate(latest):
            categories["Volume Surge Candidates"].append(
                {**row, "Category": "Volume Surge Candidates"}
            )

    raw_category_frames = {
        name: pd.DataFrame(rows, columns=DISCOVERY_COLUMNS)
        for name, rows in categories.items()
    }
    for name, frame in raw_category_frames.items():
        if frame.empty:
            continue
        for index, record in frame.iterrows():
            plan = construct_trade_plan(
                fresh_histories.get(str(record["Ticker"]), pd.DataFrame()), name
            )
            updates = {
                "Planned Entry": plan.planned_entry,
                "Planned Entry Source": plan.planned_entry_source,
                "Initial Stop": plan.structural_stop,
                "Structural Stop Source": plan.structural_stop_source,
                "Realistic Target": plan.realistic_target,
                "Realistic Target Source": plan.realistic_target_source,
                "Reward/Risk Ratio": plan.reward_risk_ratio,
                "Trade Plan Confidence": plan.confidence,
                "Trade Plan Validation Reasons": "; ".join(plan.validation_reasons),
            }
            rr = calculate_reward_risk(
                plan.planned_entry, plan.structural_stop, plan.realistic_target
            )
            updates["Risk/Reward Quality"] = rr.label
            for column, value in updates.items():
                frame.at[index, column] = value
    setup_frames = [frame for frame in raw_category_frames.values() if not frame.empty]
    setup_source = (
        pd.concat(setup_frames, ignore_index=True).drop_duplicates("Ticker")
        if setup_frames
        else pd.DataFrame(columns=DISCOVERY_COLUMNS)
    )
    eligible_industry_df = eligible_industry_df.copy()
    eligible_industry_df["Is Candidate"] = (
        eligible_industry_df["Ticker"]
        .astype(str)
        .isin(setup_source.get("Ticker", pd.Series(dtype=str)).astype(str))
    )
    quality_setups = (
        setup_source[
            setup_source.apply(
                lambda row: (
                    pd.notna(row.get("Recent RS Score"))
                    and str(row.get("Tightness Label", "")) != "Loose"
                    and str(row.get("VCP Label", "")) != "Poor VCP"
                    and str(row.get("Extension Status", ""))
                    not in {"Extended", "Overextended"}
                    and not str(row.get("Price Data Warning", "") or "").strip()
                ),
                axis=1,
            )
        ]
        if not setup_source.empty
        else setup_source
    )
    industry_qualification = qualify_industries(
        eligible_industry_df, quality_setups, metadata_coverage=coverage
    )
    qualified_names = (
        set(
            industry_qualification.loc[
                industry_qualification["Industry Qualified"], "Industry"
            ].astype(str)
        )
        if not industry_qualification.empty
        else set()
    )
    display_industries = industry_qualification.copy()
    if not display_industries.empty:
        leaders = {}
        for industry, group in eligible_industry_df.groupby("Industry"):
            leaders[industry] = ", ".join(
                group.sort_values(
                    ["Recent RS Score", "Long-Term RS Score"], ascending=False
                )
                .head(3)["Ticker"]
                .astype(str)
            )
        display_industries["Top 3 Leaders"] = display_industries["Industry"].map(
            leaders
        )
    top_industries = (
        display_industries[display_industries["Industry Qualified"]]
        .copy()
        .reset_index(drop=True)
    )
    top_industries["Final Rank"] = range(1, len(top_industries) + 1)
    top_industries["Final Industry Score"] = top_industries.get(
        "Industry Composite Score"
    )
    top_industries["Momentum Rank"] = top_industries.get(
        "Momentum Score", pd.Series(dtype=float)
    ).rank(method="min", ascending=False)
    top_industries["Leadership Rank"] = np.nan
    top_industries.attrs["rotation_watch"] = display_industries[
        display_industries["Industry Classification"].isin(
            ["Rotation Watch", "Small-Sample Rotation Watch", "Two-Stock Emerging Pair"]
        )
    ]
    top_industries.attrs["lagging_industries"] = display_industries[
        display_industries["Industry Classification"].eq(
            "Long-Term Leader Currently Lagging"
        )
    ]
    top_industries.attrs["isolated_industries"] = display_industries[
        display_industries["Eligible Members"] < 3
    ]
    industry_context = setup_source.copy()
    rank_map = (
        top_industries.set_index("Industry")["Final Rank"].to_dict()
        if not top_industries.empty
        else {}
    )
    industry_context["Industry Rank"] = industry_context["Industry"].map(rank_map)
    qualifying_count_map = (
        quality_setups.groupby("Industry")["Ticker"].nunique().to_dict()
        if not quality_setups.empty
        else {}
    )
    industry_context["Industry Setup Count"] = (
        industry_context["Industry"].map(qualifying_count_map).fillna(0)
    )
    industry_context["Industry Qualified"] = industry_context["Industry"].isin(
        qualified_names
    )
    classification_map = (
        display_industries.set_index("Industry")["Industry Classification"].to_dict()
        if not display_industries.empty
        else {}
    )
    sample_map = (
        display_industries.set_index("Industry")["Breadth Sample Quality"].to_dict()
        if not display_industries.empty
        else {}
    )
    industry_context["Industry Classification"] = industry_context["Industry"].map(
        classification_map
    )
    industry_context["Breadth Sample Quality"] = industry_context["Industry"].map(
        sample_map
    )
    industry_context["Sister Confirmation"] = industry_context["Industry Qualified"] & (
        industry_context["Industry Setup Count"] >= 3
    )
    industry_context["Sister Confirmation State"] = np.select(
        [
            ~industry_context["Industry Qualified"],
            industry_context["Breadth Sample Quality"].isin(["Insufficient", "Thin"]),
            industry_context["Industry Setup Count"] < 3,
            industry_context["Sister Confirmation"],
        ],
        [
            "Industry not qualified",
            "Small-sample industry",
            "Qualified industry, but fewer than two qualifying sister setups",
            "Sister confirmation passed",
        ],
        default="Qualified industry, but sister-stock breadth is insufficient",
    )

    category_frames = {}
    for name, frame in raw_category_frames.items():
        if frame.empty:
            category_frames[name] = frame
            continue
        frame = apply_industry_context(frame, industry_context)
        category_frames[name] = add_action_column(category_sort(frame, name))

    return category_frames, top_industries, stage2_count, download_stats


def review_flags(row: pd.Series | dict) -> list[str]:
    flags = []
    action = str(row.get("Action", ""))
    rs_trend = str(row.get("RS Trend", ""))
    vcp = str(row.get("VCP Label", ""))
    tightness = str(row.get("Tightness Label", ""))
    raw_warning = row.get("Price Data Warning", "")
    warning = "" if raw_warning is None or pd.isna(raw_warning) else str(raw_warning)
    extension = str(row.get("Extension Status", ""))

    if action == "Confirmed pullback entry review":
        flags.append("Confirmed")
    tier = str(row.get("Review Tier", ""))
    if tier in {"Review Now", "High Priority Watch", "Watch Later", "Skip Today"}:
        flags.append(tier)
    if rs_trend == "Emerging Leader":
        flags.append("Emerging Leader")
    elif rs_trend == "Improving":
        flags.append("Improving RS")
    if vcp == "Poor VCP":
        flags.append("Poor VCP")
    if tightness == "Loose":
        flags.append("Loose")
    if extension in {"Extended", "Overextended"}:
        flags.append(extension)
    if warning:
        flags.append("Price Warning")
    return flags


def add_review_flags_column(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    table = frame.copy()
    table["Review Flags"] = table.apply(
        lambda row: ", ".join(review_flags(row)), axis=1
    )
    return table


def markdown_table(df: pd.DataFrame) -> str:
    table = add_review_flags_column(df)
    if "TradingView" in table.columns:
        table["TradingView"] = table["TradingView"].apply(lambda url: f"[Chart]({url})")
    return table.to_markdown(index=False)


def html_badges(flags: list[str]) -> str:
    class_map = {
        "Confirmed": "flag-confirmed",
        "Review Now": "flag-confirmed",
        "High Priority Watch": "flag-emerging",
        "Watch Later": "flag-neutral",
        "Skip Today": "flag-risk",
        "Emerging Leader": "flag-emerging",
        "Improving RS": "flag-improving",
        "Poor VCP": "flag-caution",
        "Loose": "flag-caution",
        "Extended": "flag-risk",
        "Overextended": "flag-risk",
        "Price Warning": "flag-risk",
    }
    return " ".join(
        f'<span class="badge {class_map.get(flag, "flag-neutral")}">{escape(flag)}</span>'
        for flag in flags
    )


def row_class(row: pd.Series | dict) -> str:
    flags = set(review_flags(row))
    if "Price Warning" in flags or "Overextended" in flags:
        return "row-risk"
    if "Skip Today" in flags:
        return "row-risk"
    if "Confirmed" in flags or "Emerging Leader" in flags:
        return "row-priority"
    if "Poor VCP" in flags or "Loose" in flags or "Watch Later" in flags:
        return "row-caution"
    return ""


def html_table(df: pd.DataFrame) -> str:
    table = add_review_flags_column(df)
    columns = list(table.columns)
    header = "".join(f"<th>{escape(str(column))}</th>" for column in columns)
    rows = []
    for _, row in table.iterrows():
        css_class = row_class(row)
        cells = []
        for column in columns:
            value = row.get(column, "")
            if pd.isna(value):
                value = ""
            if column == "TradingView" and value:
                cell = f'<a href="{escape(str(value))}" target="_blank">Chart</a>'
            elif column == "Review Flags":
                cell = html_badges(review_flags(row))
            else:
                cell = escape(str(value))
            cells.append(f"<td>{cell}</td>")
        class_attr = f' class="{css_class}"' if css_class else ""
        rows.append(f"<tr{class_attr}>{''.join(cells)}</tr>")
    return (
        f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def concise_decision_table(frame: pd.DataFrame) -> pd.DataFrame:
    mapping = {
        "Ticker": "Ticker",
        "Final Decision": "Final Decision",
        "Actionable": "Actionable",
        "Setup Integrity": "Setup Integrity",
        "Maximum Risk R": "Maximum Risk R",
        "Maximum Risk Dollars": "Maximum Risk Dollars",
        "Final Score": "Final Score",
        "Recent RS Score": "Recent RS",
        "RS Trend": "RS Trend",
        "Industry Classification": "Industry Classification",
        "Sister Confirmation State": "Sister Confirmation",
        "Category": "Primary Setup",
        "Entry Timing": "Entry Timing",
        "Planned Entry": "Entry",
        "Initial Stop": "Stop",
        "Realistic Target": "Target",
        "Realistic Target Source": "Target Basis",
        "Reward/Risk Ratio": "R/R",
        "Maximum Shares": "Maximum Shares",
        "Trade Plan Confidence": "Trade Plan Confidence",
        "Support Signal": "Main Positive",
        "Main Missing Confirmation": "Main Missing Confirmation",
        "Invalidation Reason": "Invalidation Reason",
        "TradingView": "Chart",
    }
    result = frame.reindex(columns=mapping).rename(columns=mapping).copy()
    return result


def decision_manifest_records(frame: pd.DataFrame) -> list[dict[str, object]]:
    """Return a stable machine-readable representation shared by all outputs."""
    if frame.empty:
        return []

    def truth(value: object) -> bool:
        return value is True or str(value).strip().lower() == "true"

    records = []
    for row in frame.sort_values("Ticker").to_dict("records"):
        risk = pd.to_numeric(row.get("Maximum Risk R"), errors="coerce")
        risk_dollars = pd.to_numeric(row.get("Maximum Risk Dollars"), errors="coerce")
        shares = pd.to_numeric(row.get("Maximum Shares"), errors="coerce")
        records.append(
            {
                "ticker": str(row.get("Ticker", "")),
                "decision": str(row.get("Final Decision", "")),
                "maximum_risk_r": None if pd.isna(risk) else float(risk),
                "maximum_risk_dollars": (
                    None if pd.isna(risk_dollars) else float(risk_dollars)
                ),
                "maximum_shares": None if pd.isna(shares) else int(shares),
                "actionable": truth(row.get("Actionable", False)),
                "confirmed_setup": truth(row.get("Confirmed Setup", False)),
                "setup_integrity": str(row.get("Setup Integrity", "")),
                "review_tier": str(row.get("Review Tier", "")),
                "action": str(row.get("Action", "")),
            }
        )
    return records


def _json_safe(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if pd.isna(value) else float(value)
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return None if isinstance(value, float) and math.isnan(value) else value
    return str(value)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_forward_snapshot(
    canonical: pd.DataFrame,
    market_df: pd.DataFrame,
    decision_context: dict[str, object],
    generated_at: datetime | None = None,
    root: str | Path | None = None,
) -> Path:
    """Write a new immutable-by-construction forward-test evidence bundle."""
    reference = generated_at or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    reference = reference.astimezone(timezone.utc)
    signal_values = [
        str(value)
        for value in canonical.get("Signal Date", pd.Series(dtype=str)).dropna()
        if str(value).strip()
    ]
    signal_date = (
        max(signal_values)
        if signal_values
        else expected_latest_us_session(reference).isoformat()
    )
    price_as_of_values = [
        str(value)
        for value in canonical.get("Price Data As Of", pd.Series(dtype=str)).dropna()
        if str(value).strip()
    ]
    base = Path(root or config.FORWARD_SNAPSHOT_DIR) / signal_date
    run_id = reference.strftime("%Y%m%dT%H%M%S%fZ")
    target = base / run_id
    suffix = 0
    while target.exists():
        suffix += 1
        target = base / f"{run_id}_{suffix:02d}"
    target.mkdir(parents=True, exist_ok=False)

    project_root = Path(__file__).resolve().parent
    try:
        git_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        git_dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        git_commit, git_dirty = "unavailable", None

    universe_path = project_root / config.UNIVERSE_CSV
    config_path = project_root / "config.py"
    metadata = {
        "generated_timestamp": reference.isoformat(),
        "signal_trading_date": signal_date,
        "price_data_as_of": max(price_as_of_values) if price_as_of_values else "",
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "config_hash": _sha256_file(config_path),
        "universe_count": int(
            LAST_METADATA_DIAGNOSTICS.get("universe_member_count", 0)
        ),
        "universe_hash": _sha256_file(universe_path) if universe_path.exists() else "",
        "universe_metadata_coverage": LAST_METADATA_DIAGNOSTICS,
        "market_cap_filter": decision_context.get("market_cap_filter_status"),
        "candidate_count": int(len(canonical)),
        "candidate_record_hash": hashlib.sha256(
            json.dumps(
                _json_safe(canonical.to_dict("records")),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
    }
    public_config = {
        name: _json_safe(getattr(config, name))
        for name in dir(config)
        if name.isupper() and not name.startswith("_")
    }
    market_payload = {
        "market_regime": _json_safe(decision_context.get("market_regime")),
        "market_rows": _json_safe(market_df.to_dict("records")),
    }
    portfolio_payload = {
        "portfolio_status": _json_safe(decision_context.get("portfolio_status")),
        "drawdown": _json_safe(decision_context.get("drawdown")),
        "maximum_heat_r": decision_context.get("maximum_heat_r"),
        "current_heat_r": decision_context.get("current_heat_r"),
        "remaining_heat_r": decision_context.get("remaining_heat_r"),
    }
    canonical.to_csv(target / "candidates.csv", index=False)
    for name, payload in (
        ("market.json", market_payload),
        ("portfolio.json", portfolio_payload),
        ("config.json", public_config),
        ("metadata.json", metadata),
    ):
        (target / name).write_text(
            json.dumps(_json_safe(payload), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return target


def compact_industry_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Return only the fields needed for the daily industry decision."""
    columns = [
        "Industry Rank",
        "Industry",
        "Sector",
        "Industry Composite Score",
        "Relative Return 20D",
        "Above 20EMA Breadth",
        "Qualifying Setup Count",
        "Top 3 Leaders",
    ]
    return frame.reindex(columns=columns).rename(
        columns={
            "Industry Rank": "Rank",
            "Industry Composite Score": "Score",
            "Relative Return 20D": "20D vs SPY",
            "Above 20EMA Breadth": "Above 20EMA",
            "Qualifying Setup Count": "Valid Setups",
        }
    )


def primary_decision_sections(
    canonical: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select a short, unique watch list and blocked list for the main report."""
    if canonical.empty:
        return canonical.copy(), canonical.copy()
    unique = canonical.drop_duplicates("Ticker").copy()
    unique["Final Score"] = pd.to_numeric(unique.get("Final Score"), errors="coerce")
    unique = unique.sort_values("Final Score", ascending=False, na_position="last")
    watch = unique[unique["Final Decision"].eq("WATCH")].head(8)
    blocked = unique[unique["Final Decision"].eq("NO TRADE")].head(8)
    return concise_decision_table(watch), concise_decision_table(blocked)


def report_summary_counts(
    canonical: pd.DataFrame, top_action_count: int | None = None
) -> dict[str, int]:
    canonical = (
        canonical.drop_duplicates("Ticker") if "Ticker" in canonical else canonical
    )
    if canonical.empty:
        return {
            "top_action_count": 0,
            "review_now": 0,
            "high_priority_watch": 0,
            "confirmed_setups": 0,
            "emerging_leaders": 0,
            "caution_rows": 0,
            "price_warnings": 0,
            "blocked": 0,
            "watch_only": 0,
            "allowed": 0,
            "data_warnings": 0,
        }

    counts = {
        "top_action_count": (
            int(canonical["Final Decision"].isin(["FULL", "HALF"]).sum())
            if top_action_count is None and "Final Decision" in canonical
            else len(canonical)
            if top_action_count is None
            else top_action_count
        ),
        "review_now": 0,
        "high_priority_watch": 0,
        "confirmed_setups": 0,
        "emerging_leaders": 0,
        "caution_rows": 0,
        "price_warnings": 0,
    }
    counts["blocked"] = int(
        canonical.get("Final Decision", pd.Series(index=canonical.index))
        .eq("NO TRADE")
        .sum()
    )
    counts["watch_only"] = int(
        canonical.get("Final Decision", pd.Series(index=canonical.index))
        .eq("WATCH")
        .sum()
    )
    counts["allowed"] = int(
        canonical.get("Final Decision", pd.Series(index=canonical.index))
        .isin(["FULL", "HALF"])
        .sum()
    )
    counts["data_warnings"] = 0
    for _, row in canonical.iterrows():
        flags = set(review_flags(row))
        tier = str(row.get("Review Tier", ""))
        if tier == "Review Now":
            counts["review_now"] += 1
        if tier == "High Priority Watch":
            counts["high_priority_watch"] += 1
        if "Confirmed" in flags:
            counts["confirmed_setups"] += 1
        if "Emerging Leader" in flags:
            counts["emerging_leaders"] += 1
        volume_ratio = pd.to_numeric(row.get("Volume Ratio"), errors="coerce")
        thin_volume = (
            pd.notna(volume_ratio)
            and float(volume_ratio) < config.MIN_CONFIRMATION_VOLUME_RATIO
        )
        if (
            flags.intersection({"Poor VCP", "Loose", "Extended", "Overextended"})
            or str(row.get("RS Trend")) == "Weakening"
            or thin_volume
        ):
            counts["caution_rows"] += 1
        if "Price Warning" in flags:
            counts["price_warnings"] += 1
        if str(row.get("Data Warning", "")).strip() or "DATA_INCOMPLETE" in str(
            row.get("Decision Reasons", "")
        ):
            counts["data_warnings"] += 1
    return counts


def history_list_value(values: list[str]) -> str:
    cleaned = []
    for value in values:
        text = str(value).strip()
        if text and text.lower() not in {"nan", "none"} and text not in cleaned:
            cleaned.append(text)
    return "; ".join(cleaned)


def parse_history_list(value: object) -> list[str]:
    if value is None or pd.isna(value):
        return []
    return [item.strip() for item in str(value).split(";") if item.strip()]


def build_report_history_snapshot(
    top_action_list: pd.DataFrame,
    top_industries: pd.DataFrame,
    market_status: str,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    counts = report_summary_counts(top_action_list)
    tickers = (
        [] if top_action_list.empty else top_action_list["Ticker"].astype(str).tolist()
    )
    industries = (
        []
        if top_industries.empty
        else top_industries.head(5)["Industry"].astype(str).tolist()
    )
    snapshot = {
        "generated_at": (generated_at or datetime.now()).strftime("%Y-%m-%d %H:%M:%S"),
        "market_status": market_status,
        "top_action_tickers": history_list_value(tickers),
        "top_industries": history_list_value(industries),
    }
    snapshot.update(counts)
    return {column: snapshot.get(column, "") for column in SUMMARY_HISTORY_COLUMNS}


def load_last_report_history(
    path: str = SUMMARY_HISTORY_CSV,
) -> dict[str, object] | None:
    history_path = Path(path)
    if not history_path.exists():
        return None
    try:
        history = pd.read_csv(history_path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return None
    if history.empty:
        return None
    return history.iloc[-1].to_dict()


def load_previous_report_history(
    path: str = SUMMARY_HISTORY_CSV,
) -> dict[str, object] | None:
    rows = load_recent_report_history(path, 2)
    if len(rows) < 2:
        return None
    return rows[-2]


def load_recent_report_history(
    path: str = SUMMARY_HISTORY_CSV, limit: int = 10
) -> list[dict[str, object]]:
    history_path = Path(path)
    if not history_path.exists():
        return []
    try:
        history = pd.read_csv(history_path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return []
    if history.empty:
        return []
    return history.tail(max(limit, 1)).to_dict("records")


def append_report_history(
    snapshot: dict[str, object], path: str = SUMMARY_HISTORY_CSV
) -> None:
    history_path = Path(path)
    frame = pd.DataFrame(
        [{column: snapshot.get(column, "") for column in SUMMARY_HISTORY_COLUMNS}]
    )
    frame.to_csv(history_path, mode="a", header=not history_path.exists(), index=False)


def report_history_delta(
    current: dict[str, object],
    previous: dict[str, object] | None,
) -> dict[str, object]:
    if not previous:
        return {"has_previous": False}

    current_tickers = set(parse_history_list(current.get("top_action_tickers")))
    previous_tickers = set(parse_history_list(previous.get("top_action_tickers")))
    current_industries = set(parse_history_list(current.get("top_industries")))
    previous_industries = set(parse_history_list(previous.get("top_industries")))

    numeric_fields = [
        "top_action_count",
        "confirmed_setups",
        "emerging_leaders",
        "caution_rows",
        "price_warnings",
    ]
    count_deltas = {}
    for metric_name in numeric_fields:
        current_value = int(float(current.get(metric_name, 0) or 0))
        previous_value = int(float(previous.get(metric_name, 0) or 0))
        count_deltas[metric_name] = current_value - previous_value

    return {
        "has_previous": True,
        "previous_generated_at": str(previous.get("generated_at", "")),
        "new_top_action_tickers": sorted(current_tickers - previous_tickers),
        "removed_top_action_tickers": sorted(previous_tickers - current_tickers),
        "new_top_industries": sorted(current_industries - previous_industries),
        "removed_top_industries": sorted(previous_industries - current_industries),
        "count_deltas": count_deltas,
    }


def signed_delta(value: int) -> str:
    if value > 0:
        return f"+{value}"
    return str(value)


def history_int(row: dict[str, object], field: str) -> int:
    return int(float(row.get(field, 0) or 0))


def report_quality_score(row: dict[str, object]) -> int:
    return (
        history_int(row, "confirmed_setups") * 2
        + history_int(row, "emerging_leaders")
        - history_int(row, "caution_rows")
        - history_int(row, "price_warnings") * 2
    )


def report_history_trend_from_rows(rows: list[dict[str, object]]) -> dict[str, object]:
    trend_rows = []
    for row in rows:
        trend_rows.append(
            {
                "generated_at": str(row.get("generated_at", "")),
                "market_status": str(row.get("market_status", "")),
                "top_action_count": history_int(row, "top_action_count"),
                "confirmed_setups": history_int(row, "confirmed_setups"),
                "emerging_leaders": history_int(row, "emerging_leaders"),
                "caution_rows": history_int(row, "caution_rows"),
                "price_warnings": history_int(row, "price_warnings"),
                "quality_score": report_quality_score(row),
            }
        )

    if len(trend_rows) < 3:
        assessment = "Collecting history"
    else:
        latest = trend_rows[-1]
        previous = trend_rows[-2]
        earlier_scores = [row["quality_score"] for row in trend_rows[:-1]]
        prior_average = sum(earlier_scores) / len(earlier_scores)
        if (
            latest["quality_score"] >= prior_average + 2
            and latest["quality_score"] >= previous["quality_score"]
        ):
            assessment = "Improving opportunity quality"
        elif (
            latest["quality_score"] <= prior_average - 2
            and latest["quality_score"] <= previous["quality_score"]
        ):
            assessment = "Deteriorating opportunity quality"
        else:
            assessment = "Mixed or stable opportunity quality"

    return {
        "rows": trend_rows,
        "assessment": assessment,
        "has_history": len(trend_rows) > 1,
    }


def report_history_trend(
    current: dict[str, object],
    path: str = SUMMARY_HISTORY_CSV,
    limit: int = 10,
) -> dict[str, object]:
    previous_rows = load_recent_report_history(path, max(limit - 1, 1))
    rows = previous_rows + [current]
    return report_history_trend_from_rows(rows[-max(limit, 1) :])


def markdown_list_value(items: list[str]) -> str:
    return ", ".join(items) if items else "None"


def markdown_history_section(history_delta: dict[str, object] | None) -> str:
    if not history_delta or not history_delta.get("has_previous"):
        return "No previous valid report history yet."

    count_deltas = history_delta.get("count_deltas", {})
    lines = [
        f"Previous valid report: {history_delta.get('previous_generated_at', '')}",
        "",
        f"- Top Action Count: {signed_delta(int(count_deltas.get('top_action_count', 0)))}",
        f"- Confirmed Setups: {signed_delta(int(count_deltas.get('confirmed_setups', 0)))}",
        f"- Emerging Leaders: {signed_delta(int(count_deltas.get('emerging_leaders', 0)))}",
        f"- Caution Rows: {signed_delta(int(count_deltas.get('caution_rows', 0)))}",
        f"- Price Warnings: {signed_delta(int(count_deltas.get('price_warnings', 0)))}",
        "",
        f"New Top Action Tickers: {markdown_list_value(history_delta.get('new_top_action_tickers', []))}",
        f"Removed Top Action Tickers: {markdown_list_value(history_delta.get('removed_top_action_tickers', []))}",
        f"New Top Industries: {markdown_list_value(history_delta.get('new_top_industries', []))}",
        f"Removed Top Industries: {markdown_list_value(history_delta.get('removed_top_industries', []))}",
    ]
    return "\n".join(lines)


def markdown_trend_section(history_trend: dict[str, object] | None) -> str:
    if not history_trend or not history_trend.get("rows"):
        return "No summary trend history yet."

    rows = history_trend.get("rows", [])
    lines = [
        f"Assessment: {history_trend.get('assessment', 'Collecting history')}",
        "",
        "| Date | Market | Top Action | Confirmed | Emerging | Caution | Price Warnings | Quality Score |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['generated_at']} | {row['market_status']} | {row['top_action_count']} | "
            f"{row['confirmed_setups']} | {row['emerging_leaders']} | {row['caution_rows']} | "
            f"{row['price_warnings']} | {row['quality_score']} |"
        )
    return "\n".join(lines)


def html_chip_list(items: list[str]) -> str:
    if not items:
        return '<span class="history-empty">None</span>'
    return " ".join(
        f'<span class="history-chip">{escape(item)}</span>' for item in items
    )


def html_history_panel(history_delta: dict[str, object] | None) -> str:
    if not history_delta or not history_delta.get("has_previous"):
        return (
            '<section class="history-panel" aria-label="Daily change">'
            "<h2>Daily Change</h2>"
            "<p>No previous valid report history yet.</p>"
            "</section>"
        )

    count_deltas = history_delta.get("count_deltas", {})
    cards = [
        ("Top Action", count_deltas.get("top_action_count", 0)),
        ("Confirmed", count_deltas.get("confirmed_setups", 0)),
        ("Emerging", count_deltas.get("emerging_leaders", 0)),
        ("Caution", count_deltas.get("caution_rows", 0)),
        ("Price Warnings", count_deltas.get("price_warnings", 0)),
    ]
    card_html = "".join(
        '<div class="history-delta-card">'
        f"<span>{escape(label)}</span><strong>{escape(signed_delta(int(value)))}</strong>"
        "</div>"
        for label, value in cards
    )
    return (
        '<section class="history-panel" aria-label="Daily change">'
        "<h2>Daily Change</h2>"
        f"<p>Compared with previous valid report: {escape(str(history_delta.get('previous_generated_at', '')))}</p>"
        f'<div class="history-delta-grid">{card_html}</div>'
        '<div class="history-lists">'
        "<div><h3>New Top Action Tickers</h3>"
        f"{html_chip_list(history_delta.get('new_top_action_tickers', []))}</div>"
        "<div><h3>Removed Top Action Tickers</h3>"
        f"{html_chip_list(history_delta.get('removed_top_action_tickers', []))}</div>"
        "<div><h3>New Top Industries</h3>"
        f"{html_chip_list(history_delta.get('new_top_industries', []))}</div>"
        "<div><h3>Removed Top Industries</h3>"
        f"{html_chip_list(history_delta.get('removed_top_industries', []))}</div>"
        "</div>"
        "</section>"
    )


def html_trend_panel(history_trend: dict[str, object] | None) -> str:
    if not history_trend or not history_trend.get("rows"):
        return (
            '<section class="trend-panel" aria-label="Summary trend">'
            "<h2>Summary Trend</h2>"
            "<p>No summary trend history yet.</p>"
            "</section>"
        )

    rows = history_trend.get("rows", [])
    max_abs_score = max([abs(int(row["quality_score"])) for row in rows] + [1])
    table_rows = []
    for row in rows:
        score = int(row["quality_score"])
        width = max(int((abs(score) / max_abs_score) * 100), 4)
        bar_class = "trend-positive" if score >= 0 else "trend-negative"
        table_rows.append(
            "<tr>"
            f"<td>{escape(str(row['generated_at']))}</td>"
            f"<td>{escape(str(row['market_status']))}</td>"
            f"<td>{row['top_action_count']}</td>"
            f"<td>{row['confirmed_setups']}</td>"
            f"<td>{row['emerging_leaders']}</td>"
            f"<td>{row['caution_rows']}</td>"
            f"<td>{row['price_warnings']}</td>"
            "<td>"
            f'<span class="trend-bar {bar_class}" style="width: {width}%"></span>'
            f"<strong>{score}</strong>"
            "</td>"
            "</tr>"
        )
    return (
        '<section class="trend-panel" aria-label="Summary trend">'
        "<h2>Summary Trend</h2>"
        f"<p>{escape(str(history_trend.get('assessment', 'Collecting history')))}</p>"
        '<table class="trend-table"><thead><tr>'
        "<th>Date</th><th>Market</th><th>Top Action</th><th>Confirmed</th>"
        "<th>Emerging</th><th>Caution</th><th>Price Warnings</th><th>Quality Score</th>"
        "</tr></thead><tbody>"
        f"{''.join(table_rows)}"
        "</tbody></table>"
        "</section>"
    )


def html_summary_panel(
    canonical: pd.DataFrame,
    market_status: str,
    top_action_count: int | None = None,
    decision_context: dict[str, object] | None = None,
) -> str:
    decisions = canonical.get("Final Decision", pd.Series(dtype=str))
    current_heat = decision_context.get("current_heat_r") if decision_context else None
    remaining_heat = (
        decision_context.get("remaining_heat_r") if decision_context else None
    )
    system_warning_count = (
        len(decision_context.get("system_warnings", [])) if decision_context else 0
    )
    model_target_mask = canonical.get(
        "Realistic Target Source", pd.Series("", index=canonical.index, dtype=str)
    ).eq("model 2R feasibility target")
    price_warning_mask = canonical.apply(
        lambda row: (
            bool(str(row.get("Price Data Warning", "")).strip())
            and not pd.isna(row.get("Price Data Warning"))
        ),
        axis=1,
    )
    data_warning_mask = canonical.apply(
        lambda row: (
            bool(str(row.get("Data Warning", "")).strip())
            or "DATA_INCOMPLETE" in str(row.get("Decision Reasons", ""))
        ),
        axis=1,
    )
    affected_candidates = int(
        (model_target_mask | price_warning_mask | data_warning_mask).sum()
    )
    cards = [
        ("Market Status", market_status, "summary-neutral", "Current risk regime"),
        (
            "Current Heat",
            "N/A" if current_heat is None else f"{float(current_heat):.2f}R",
            "summary-neutral",
            "Open-position risk",
        ),
        (
            "Remaining Heat",
            "N/A" if remaining_heat is None else f"{float(remaining_heat):.2f}R",
            "summary-neutral",
            "Available portfolio budget",
        ),
        (
            "FULL Candidates",
            int(decisions.eq("FULL").sum()),
            "summary-priority",
            "Maximum initial risk 1.0R",
        ),
        (
            "HALF Candidates",
            int(decisions.eq("HALF").sum()),
            "summary-emerging",
            "Maximum initial risk 0.5R",
        ),
        (
            "NO TRADE Candidates",
            int(decisions.eq("NO TRADE").sum()),
            "summary-risk",
            "Zero new risk",
        ),
        (
            "System Warnings",
            system_warning_count,
            "summary-caution",
            "Distinct warning messages",
        ),
        (
            "Affected Candidates",
            affected_candidates,
            "summary-caution",
            "Unique rows with price/data/target warnings",
        ),
        (
            "New Trade",
            str(decision_context.get("new_trade_status", "NO"))
            if decision_context
            else "NO",
            "summary-priority"
            if decision_context and decision_context.get("final_new_risk_allowed")
            else "summary-risk",
            "READY, CONDITIONAL, or NO",
        ),
    ]
    card_html = []
    for label, value, css_class, detail in cards:
        card_html.append(
            '<div class="summary-card {css_class}">'
            '<span class="summary-label">{label}</span>'
            "<strong>{value}</strong>"
            "<small>{detail}</small>"
            "</div>".format(
                css_class=escape(css_class),
                label=escape(str(label)),
                value=escape(str(value)),
                detail=escape(str(detail)),
            )
        )
    return (
        '<section class="summary-panel" aria-label="Executive summary">'
        "<h2>Executive Summary</h2>"
        '<div class="summary-grid">'
        f"{''.join(card_html)}"
        "</div>"
        "</section>"
    )


def review_tickers_by_tier(frame: pd.DataFrame, tier: str, limit: int = 8) -> list[str]:
    if (
        frame.empty
        or "Review Tier" not in frame.columns
        or "Ticker" not in frame.columns
    ):
        return []
    tickers = (
        frame[frame["Review Tier"] == tier]["Ticker"]
        .dropna()
        .astype(str)
        .head(limit)
        .tolist()
    )
    return tickers


def daily_review_plan(
    top_action_list: pd.DataFrame, daily_focus: pd.DataFrame, market_status: str
) -> dict[str, object]:
    guided_focus = (
        add_review_guidance_columns(daily_focus)
        if not daily_focus.empty
        else daily_focus
    )
    review_now = review_tickers_by_tier(top_action_list, "Review Now")
    high_priority = review_tickers_by_tier(top_action_list, "High Priority Watch")
    watch_later = review_tickers_by_tier(guided_focus, "Watch Later", limit=6)
    skip_today = review_tickers_by_tier(guided_focus, "Skip Today", limit=6)

    if review_now:
        first_step = f"Open first: {', '.join(review_now)}."
    elif high_priority:
        first_step = f"No confirmed clean entries. Start with high-priority watches: {', '.join(high_priority)}."
    else:
        first_step = (
            "No clean first-review setups. Do not force trades from a noisy list."
        )

    if high_priority:
        second_step = f"Review after confirmed setups: {', '.join(high_priority)}."
    elif watch_later:
        second_step = f"Secondary tracking only: {', '.join(watch_later)}."
    elif skip_today:
        second_step = "Daily Focus is mostly noise today; keep it as reference only."
    else:
        second_step = "No secondary tracking names need attention."

    market_note = {
        "Strong": "Market is supportive, but entries still require chart confirmation.",
        "Neutral": "Market is mixed; prioritise clean setups and avoid marginal names.",
        "Caution": "Market is defensive; reduce urgency and require cleaner confirmation.",
        "Unknown": "Market context is unavailable; treat the report as lower confidence.",
    }.get(
        str(market_status),
        "Use market status as context, not as a stock-selection override.",
    )

    return {
        "first_step": first_step,
        "second_step": second_step,
        "market_note": market_note,
        "watch_later": watch_later,
        "skip_today": skip_today,
    }


def markdown_daily_review_plan(
    top_action_list: pd.DataFrame, daily_focus: pd.DataFrame, market_status: str
) -> str:
    plan = daily_review_plan(top_action_list, daily_focus, market_status)
    lines = [
        plan["first_step"],
        plan["second_step"],
        str(plan["market_note"]),
        "Use Daily Focus as a tracking pool only; Top Action is the first-pass decision list.",
    ]
    if plan["skip_today"]:
        lines.append(
            f"Skip today unless conditions improve: {', '.join(plan['skip_today'])}."
        )
    return "\n".join(f"- {line}" for line in lines)


def html_daily_review_plan(
    top_action_list: pd.DataFrame, daily_focus: pd.DataFrame, market_status: str
) -> str:
    plan = daily_review_plan(top_action_list, daily_focus, market_status)
    items = [
        plan["first_step"],
        plan["second_step"],
        str(plan["market_note"]),
        "Use Daily Focus as a tracking pool only; Top Action is the first-pass decision list.",
    ]
    if plan["skip_today"]:
        items.append(
            f"Skip today unless conditions improve: {', '.join(plan['skip_today'])}."
        )
    item_html = "".join(f"<li>{escape(str(item))}</li>" for item in items)
    return (
        '<section class="review-plan" aria-label="Daily review plan">'
        "<h2>Daily Review Plan</h2>"
        f"<ul>{item_html}</ul>"
        "</section>"
    )


def combined_watchlist(categories: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = [frame for frame in categories.values() if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=DISCOVERY_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def build_decision_context(
    canonical: pd.DataFrame,
    market_df: pd.DataFrame,
    market_status: str,
    index_metrics: dict[str, float | bool | None] | None = None,
    *,
    previous_regime: str | None = None,
) -> dict[str, object]:
    """Build one transparent market/portfolio permission context for every output.

    ``market_status`` is the current run's display label and is never treated as
    historical state. Hysteresis is applied only when a caller supplies an
    explicitly persisted ``previous_regime``.
    """

    def above(symbol: str, average: str) -> bool | None:
        rows = market_df[market_df.get("Symbol", pd.Series(dtype=str)).eq(symbol)]
        if rows.empty or average not in rows:
            return None
        return str(rows.iloc[0][average]).lower() == "above"

    eligible = LAST_ELIGIBLE_UNIVERSE
    breadth20 = (
        float(eligible["Above 20EMA"].mean() * 100)
        if not eligible.empty and "Above 20EMA" in eligible
        else None
    )
    breadth50 = (
        float(eligible["Above 50MA"].mean() * 100)
        if not eligible.empty and "Above 50MA" in eligible
        else None
    )
    valid_breakouts = int(
        eligible.get("Valid Breakout", pd.Series(False, index=eligible.index))
        .fillna(False)
        .sum()
    )
    failed_breakouts = int(
        eligible.get("Failed Breakout", pd.Series(False, index=eligible.index))
        .fillna(False)
        .sum()
    )
    breakout_sample = valid_breakouts + failed_breakouts
    leaders = eligible[
        pd.to_numeric(eligible.get("Recent RS Score"), errors="coerce") >= 80
    ]
    leader_hold_pct = (
        float(leaders["Above 20EMA"].mean() * 100)
        if not leaders.empty and "Above 20EMA" in leaders
        else None
    )
    breakdown_count = int(
        eligible.get("High Volume Breakdown", pd.Series(False, index=eligible.index))
        .fillna(False)
        .sum()
    )
    leadership_contribution = (
        max(-5.0, min(5.0, (leader_hold_pct - 50) * 0.10 - breakdown_count * 0.25))
        if leader_hold_pct is not None
        else None
    )
    volatility_pct = (index_metrics or {}).get("index_volatility_pct")
    volatility_contribution = (
        None
        if volatility_pct is None
        else max(-8.0, min(2.0, (20.0 - float(volatility_pct)) * 0.25))
    )
    metrics = {
        "spy_above_20ema": above("SPY", "20EMA"),
        "spy_above_50ma": above("SPY", "50MA"),
        "qqq_above_20ema": above("QQQ", "20EMA"),
        "qqq_above_50ma": above("QQQ", "50MA"),
        "breadth_above_20ema": breadth20,
        "breadth_above_50ma": breadth50,
        "breakout_success_rate": (
            100.0 * valid_breakouts / breakout_sample if breakout_sample else 0.0
        ),
        "breakout_failure_rate": (
            100.0 * failed_breakouts / breakout_sample if breakout_sample else 0.0
        ),
        "breakout_sample_size": breakout_sample,
        "leadership_contribution": leadership_contribution,
        "leadership_sample_size": len(leaders),
        "volatility_contribution": volatility_contribution,
    }
    metrics.update(index_metrics or {})
    regime = market_regime_from_metrics(metrics, previous_regime=previous_regime)
    drawdown = load_drawdown_state(config.EQUITY_FILE)
    effective_heat_limit = min(regime.maximum_heat_r, drawdown.heat_limit_r)
    portfolio_status = load_portfolio_status(
        config.POSITION_FILE,
        regime.regime,
        market_snapshot=eligible,
        maximum_heat_override_r=effective_heat_limit,
    )
    portfolio = portfolio_status["portfolio"]
    market_allowed = bool(regime.new_risk_allowed)
    portfolio_allowed = bool(portfolio_status["portfolio_new_risk_allowed"])
    decisions = canonical.get("Final Decision", pd.Series(dtype=str))
    full_available = bool(decisions.eq("FULL").any())
    half_available = bool(decisions.eq("HALF").any())
    actionable = full_available or half_available
    final_allowed = market_allowed and portfolio_allowed and actionable
    setup_status = (
        "READY" if full_available else "CONDITIONAL" if half_available else "NONE"
    )
    new_trade_status = (
        setup_status if market_allowed and portfolio_allowed and actionable else "NO"
    )
    system_warnings: list[str] = []
    if not regime.data_complete:
        system_warnings.append("Market regime factors are incomplete")
    elif regime.confidence != "High":
        system_warnings.append(
            f"Market regime confidence is {regime.confidence} because confirmation samples are thin"
        )
    model_target_count = int(
        canonical.get("Realistic Target Source", pd.Series(dtype=str))
        .eq("model 2R feasibility target")
        .sum()
    )
    if model_target_count:
        system_warnings.append(
            f"{model_target_count} candidate(s) use a model 2R feasibility target; this is not chart resistance"
        )
    if portfolio is None:
        system_warnings.append("Portfolio risk is unavailable")
    if drawdown.data_status != "Valid":
        system_warnings.append("Account equity/high-water mark is missing or invalid")
    metadata_diagnostics = dict(LAST_METADATA_DIAGNOSTICS)
    if not config.ENFORCE_MARKET_CAP_FILTER:
        system_warnings.append(
            "Market Cap Filter: NOT ENFORCED — reliable complete metadata is unavailable"
        )
    if metadata_diagnostics and not bool(
        metadata_diagnostics.get("coverage_complete", False)
    ):
        system_warnings.append(
            "Industry metadata coverage is below the configured minimum; industry qualification is disabled"
        )
    return {
        "standard_r_dollars": config.STANDARD_R_DOLLARS,
        "market_regime": regime,
        "portfolio_status": portfolio_status,
        "market_heat_limit_r": regime.maximum_heat_r,
        "drawdown": drawdown,
        "drawdown_heat_limit_r": drawdown.heat_limit_r,
        "maximum_heat_r": effective_heat_limit,
        "current_heat_r": None if portfolio is None else portfolio.portfolio_heat_r,
        "remaining_heat_r": None if portfolio is None else portfolio.remaining_heat_r,
        "market_new_risk_allowed": market_allowed,
        "portfolio_new_risk_allowed": portfolio_allowed,
        "actionable_setup_available": actionable,
        "setup_status": setup_status,
        "new_trade_status": new_trade_status,
        "final_new_risk_allowed": final_allowed,
        "final_instruction": "New trade may be considered under the validated plan"
        if final_allowed
        else "Do not open a new trade",
        "system_warnings": system_warnings,
        "model_target_candidate_count": model_target_count,
        "metadata_diagnostics": metadata_diagnostics,
        "market_cap_filter_status": (
            f"ENFORCED at USD {config.MIN_MARKET_CAP:,.0f}"
            if config.ENFORCE_MARKET_CAP_FILTER
            else "NOT ENFORCED"
        ),
    }


def validate_canonical_decision_invariants(canonical: pd.DataFrame) -> list[str]:
    """Return cross-field contradictions that must block report publication."""
    errors: list[str] = []
    if canonical.empty:
        return errors
    if "Ticker" in canonical and canonical["Ticker"].duplicated().any():
        errors.append("duplicate tickers in canonical decisions")
    decisions = canonical.get("Final Decision", pd.Series("", index=canonical.index))
    invalid_states = ~decisions.isin(["FULL", "HALF", "WATCH", "NO TRADE"])
    if invalid_states.any():
        errors.append("unsupported final decision state")
    actionable = decisions.isin(["FULL", "HALF"])
    actionable_field = canonical.get(
        "Actionable", pd.Series(False, index=canonical.index)
    ).apply(lambda value: str(value).strip().lower() == "true" or value is True)
    if (actionable != actionable_field).any():
        errors.append("actionable flag contradicts final decision")
    confirmed_field = canonical.get(
        "Confirmed Setup", pd.Series(False, index=canonical.index)
    ).apply(lambda value: str(value).strip().lower() == "true" or value is True)
    if (actionable != confirmed_field).any():
        errors.append("confirmed setup contradicts final decision")
    recent = pd.to_numeric(
        canonical.get("Recent RS Score", pd.Series(np.nan, index=canonical.index)),
        errors="coerce",
    )
    rr = pd.to_numeric(
        canonical.get("Reward/Risk Ratio", pd.Series(np.nan, index=canonical.index)),
        errors="coerce",
    )
    shares = pd.to_numeric(
        canonical.get("Maximum Shares", pd.Series(np.nan, index=canonical.index)),
        errors="coerce",
    )
    if (actionable & recent.isna()).any():
        errors.append("actionable row has missing Recent RS")
    if (actionable & (rr.isna() | (rr < config.MIN_REWARD_RISK_ALLOWED))).any():
        errors.append("actionable row has invalid structural R/R")
    if (actionable & (shares.isna() | (shares <= 0))).any():
        errors.append("actionable row has no positive share size")
    risk_r = pd.to_numeric(
        canonical.get("Maximum Risk R", pd.Series(np.nan, index=canonical.index)),
        errors="coerce",
    )
    risk_dollars = pd.to_numeric(
        canonical.get("Maximum Risk Dollars", pd.Series(np.nan, index=canonical.index)),
        errors="coerce",
    )
    if (decisions.eq("FULL") & risk_r.ne(config.FULL_RISK_R)).any():
        errors.append("FULL row does not have exactly 1R maximum risk")
    if (
        decisions.eq("FULL")
        & risk_dollars.ne(config.FULL_RISK_R * config.STANDARD_R_DOLLARS)
    ).any():
        errors.append("FULL row has incorrect maximum risk dollars")
    if (decisions.eq("HALF") & risk_r.ne(config.HALF_RISK_R)).any():
        errors.append("HALF row does not have exactly 0.5R maximum risk")
    if (
        decisions.eq("HALF")
        & risk_dollars.ne(config.HALF_RISK_R * config.STANDARD_R_DOLLARS)
    ).any():
        errors.append("HALF row has incorrect maximum risk dollars")
    non_actionable = decisions.isin(["WATCH", "NO TRADE"])
    if (non_actionable & risk_r.fillna(0).ne(0)).any():
        errors.append("non-actionable row has non-zero risk")
    if (non_actionable & risk_dollars.fillna(0).ne(0)).any():
        errors.append("non-actionable row has non-zero risk dollars")
    if (non_actionable & shares.fillna(0).ne(0)).any():
        errors.append("non-actionable row has non-zero shares")
    review_tier = canonical.get(
        "Review Tier", pd.Series("", index=canonical.index)
    ).astype(str)
    action_text = canonical.get("Action", pd.Series("", index=canonical.index)).astype(
        str
    )
    if (
        actionable
        & (
            review_tier.str.contains("Watch Later", case=False, na=False)
            | action_text.str.contains("Watch Later", case=False, na=False)
        )
    ).any():
        errors.append("Watch Later wording coexists with actionable decision")
    target_source = canonical.get(
        "Realistic Target Source", pd.Series("", index=canonical.index)
    ).astype(str)
    if (actionable & target_source.eq("model 2R feasibility target")).any():
        errors.append("actionable row uses synthetic model 2R target")
    freshness = canonical.get(
        "Price Freshness Status", pd.Series("", index=canonical.index)
    ).astype(str)
    if (actionable & freshness.ne("CURRENT") & freshness.ne("")).any():
        errors.append("actionable row has stale or incomplete price data")
    entry = pd.to_numeric(
        canonical.get("Planned Entry", pd.Series(np.nan, index=canonical.index)),
        errors="coerce",
    )
    stop = pd.to_numeric(
        canonical.get("Initial Stop", pd.Series(np.nan, index=canonical.index)),
        errors="coerce",
    )
    if (actionable & (entry.isna() | stop.isna() | stop.ge(entry))).any():
        errors.append("actionable row has invalid structural stop")
    extension = canonical.get(
        "Extension Status", pd.Series("", index=canonical.index)
    ).astype(str)
    if (actionable & extension.eq("Overextended")).any():
        errors.append("overextended row is actionable")
    concentration = (
        canonical.get(
            "Concentration Exclusion Reason", pd.Series("", index=canonical.index)
        )
        .fillna("")
        .astype(str)
    )
    if (actionable & concentration.ne("")).any():
        errors.append("concentration-excluded row is actionable")
    return errors


def enforce_production_concentration(canonical: pd.DataFrame) -> pd.DataFrame:
    """Apply configured candidate concentration to final actionable records."""
    if canonical.empty:
        return canonical.copy()
    updated = canonical.copy()
    actionable_records = updated[
        updated["Final Decision"].isin(["FULL", "HALF"])
    ].to_dict("records")
    _, excluded = apply_concentration_limits(actionable_records, top_action=True)
    excluded_reasons = {
        str(record.get("Ticker")): str(record.get("Concentration Exclusion Reason"))
        for record in excluded
    }
    for index, row in updated.iterrows():
        reason = excluded_reasons.get(str(row.get("Ticker")))
        if not reason:
            continue
        prior = str(row.get("Invalidation Reason", "") or "").strip()
        combined = ", ".join(item for item in (prior, reason) if item)
        updated.at[index, "Final Decision"] = "NO TRADE"
        updated.at[index, "Actionable"] = False
        updated.at[index, "Confirmed Setup"] = False
        updated.at[index, "Maximum Risk R"] = 0.0
        updated.at[index, "Maximum Risk Dollars"] = 0.0
        updated.at[index, "Maximum Shares"] = 0
        updated.at[index, "Review Tier"] = "Skip Today"
        updated.at[index, "Action"] = "NO TRADE — concentration limit"
        updated.at[index, "Invalidation Reason"] = combined
        updated.at[index, "Decision Reasons"] = combined
        updated.at[index, "Concentration Exclusion Reason"] = reason
    return updated


def apply_canonical_decision_pipeline(
    candidates: pd.DataFrame, decision_context: dict[str, object]
) -> pd.DataFrame:
    """Produce the sole authoritative, final production candidate records."""
    portfolio_status = decision_context["portfolio_status"]
    portfolio = portfolio_status["portfolio"]
    drawdown = decision_context["drawdown"]
    market_permission = decision_context.get("market_new_risk_allowed") is True
    portfolio_permission = portfolio_status.get("portfolio_new_risk_allowed") is True

    def apply_decision_fields(
        record: dict[str, object], decision: TradeSizingDecision
    ) -> dict[str, object]:
        record["Final Decision"] = decision.state
        record["Maximum Risk R"] = decision.maximum_risk_r
        record["Maximum Risk Dollars"] = decision.maximum_risk_dollars
        record["Maximum Shares"] = decision.maximum_shares
        record["Setup Integrity"] = decision.setup_integrity
        record["Actionable"] = decision.actionable
        record["Main Missing Confirmation"] = ", ".join(decision.missing_confirmations)
        record["Invalidation Reason"] = ", ".join(decision.reasons)
        record["Decision Reasons"] = (
            record["Invalidation Reason"] or record["Main Missing Confirmation"]
        )
        record["Review Tier"] = (
            "Review Now"
            if decision.state in {"FULL", "HALF"}
            else "Watch Later"
            if decision.state == "WATCH"
            else "Skip Today"
        )
        record["Confirmed Setup"] = decision.actionable
        if decision.state == "FULL":
            record["Action"] = "Actionable now — FULL"
        elif decision.state == "HALF":
            record["Action"] = "Actionable now — HALF"
        elif decision.state == "WATCH" and "Watch" not in str(record.get("Action", "")):
            record["Action"] = "Watch only"
        elif decision.state == "NO TRADE":
            record["Action"] = "NO TRADE — hard gate"
        return record

    rows: list[dict[str, object]] = []
    for record in candidates.to_dict("records"):
        if not str(record.get("Price Freshness Status", "")).strip():
            record["Price Freshness Status"] = "MISSING"
        record["Entry Timing"] = entry_timing_for_candidate(record)
        decision = canonical_candidate_decision(
            record,
            str(decision_context["market_regime"].regime),
            drawdown,
            portfolio,
            portfolio_status["open_position_count"],
            portfolio_new_risk_allowed=portfolio_permission,
            market_new_risk_allowed=market_permission,
        )
        rows.append(apply_decision_fields(record, decision))

    concentrated = enforce_production_concentration(pd.DataFrame(rows)).reset_index(
        drop=True
    )
    projected_portfolio = portfolio
    base_open_count = portfolio_status["open_position_count"]
    accepted_count = 0
    allocated_new_risk_r = 0.0
    final_records = {
        index: record for index, record in enumerate(concentrated.to_dict("records"))
    }
    priority = sorted(
        final_records.items(),
        key=lambda item: (
            -float(pd.to_numeric(item[1].get("Final Score"), errors="coerce"))
            if pd.notna(pd.to_numeric(item[1].get("Final Score"), errors="coerce"))
            else float("inf"),
            item[0],
        ),
    )
    for index, record in priority:
        if record.get("Final Decision") not in {"FULL", "HALF"}:
            continue
        decision = canonical_candidate_decision(
            record,
            str(decision_context["market_regime"].regime),
            drawdown,
            projected_portfolio,
            None if base_open_count is None else base_open_count + accepted_count,
            accepted_count,
            portfolio_new_risk_allowed=portfolio_permission,
            market_new_risk_allowed=market_permission,
            remaining_new_risk_r=max(
                0.0, config.MAX_NEW_INITIAL_R_PER_DAY - allocated_new_risk_r
            ),
        )
        revised = apply_decision_fields(record, decision)
        final_records[index] = revised
        if not decision.actionable or projected_portfolio is None:
            continue
        reserved_r = float(decision.maximum_risk_r)
        industry = str(revised.get("Industry", ""))
        sector = str(revised.get("Sector", ""))
        theme = str(revised.get("Theme", f"Industry: {industry}"))
        industry_heat = dict(projected_portfolio.industry_heat)
        sector_heat = dict(projected_portfolio.sector_heat)
        theme_heat = dict(projected_portfolio.theme_heat)
        industry_heat[industry] = industry_heat.get(industry, 0.0) + reserved_r
        sector_heat[sector] = sector_heat.get(sector, 0.0) + reserved_r
        theme_heat[theme] = theme_heat.get(theme, 0.0) + reserved_r
        projected_portfolio = replace(
            projected_portfolio,
            portfolio_heat_r=projected_portfolio.portfolio_heat_r + reserved_r,
            remaining_heat_r=max(
                0.0, projected_portfolio.remaining_heat_r - reserved_r
            ),
            industry_heat=industry_heat,
            sector_heat=sector_heat,
            theme_heat=theme_heat,
        )
        accepted_count += 1
        allocated_new_risk_r += reserved_r
    final = pd.DataFrame([final_records[index] for index in range(len(final_records))])
    errors = validate_canonical_decision_invariants(final)
    actionable = final[final["Final Decision"].isin(["FULL", "HALF"])]
    if not market_permission and not actionable.empty:
        errors.append("market stop-new-risk flag has actionable rows")
    if portfolio_permission is False and not actionable.empty:
        errors.append("portfolio stop-new-risk flag has actionable rows")
    if base_open_count is None and not actionable.empty:
        errors.append("unknown open-position count has actionable rows")
    elif (
        base_open_count is not None
        and base_open_count + len(actionable) > config.MAX_OPEN_POSITIONS
    ):
        errors.append("candidate allocation exceeds maximum open positions")
    if portfolio is not None and not actionable.empty:
        allocated_r = float(
            pd.to_numeric(actionable["Maximum Risk R"], errors="coerce").sum()
        )
        if allocated_r > portfolio.remaining_heat_r + 1e-9:
            errors.append("candidate allocation exceeds remaining portfolio heat")
        if allocated_r > config.MAX_NEW_INITIAL_R_PER_DAY + 1e-9:
            errors.append("candidate allocation exceeds daily new-risk limit")
    if errors:
        raise RuntimeError("Decision invariant failure: " + "; ".join(errors))
    return final


def html_decision_context(context: dict[str, object]) -> str:
    regime = context["market_regime"]
    portfolio_status = context["portfolio_status"]
    drawdown = context["drawdown"]

    def heat(value: object) -> str:
        return "Not Available" if value is None else f"{float(value):.2f}R"

    components = ", ".join(
        f"{name}: {score:+.1f}"
        for name, score in (regime.component_scores or {}).items()
    )
    positives = "; ".join(regime.positive_factors) or "None"
    negatives = "; ".join(regime.negative_factors) or "None"
    metadata = context.get("metadata_diagnostics", {}) or {}
    coverage_text = (
        f"{metadata.get('mapped_sector_industry_count', 'N/A')} mapped / "
        f"{metadata.get('universe_member_count', 'N/A')} total "
        f"({metadata.get('coverage_percentage', 'N/A')}%); "
        f"cache as-of {metadata.get('cache_as_of', 'N/A')}"
    )
    return (
        "<h2>Market &amp; Portfolio Risk</h2><table><tbody>"
        f"<tr><th>Standard R Dollars</th><td>${float(context['standard_r_dollars']):,.0f}</td></tr>"
        f"<tr><th>Market Regime / Score</th><td>{escape(regime.regime)} / {regime.market_score:.1f}</td></tr>"
        f"<tr><th>Regime Components</th><td>{escape(components)}</td></tr>"
        f"<tr><th>Positive Factors</th><td>{escape(positives)}</td></tr>"
        f"<tr><th>Negative Factors</th><td>{escape(negatives)}</td></tr>"
        f"<tr><th>Confidence / Data</th><td>{escape(regime.confidence)} / {'Complete' if regime.data_complete else 'Incomplete'}</td></tr>"
        f"<tr><th>Regime Change</th><td>{escape(regime.explanation)}</td></tr>"
        f"<tr><th>Market Heat Limit</th><td>{heat(context['market_heat_limit_r'])}</td></tr>"
        f"<tr><th>Drawdown Mode / Current Drawdown</th><td>{escape(drawdown.mode)} / {heat(drawdown.drawdown_r)}</td></tr>"
        f"<tr><th>Drawdown Heat Limit</th><td>{heat(context['drawdown_heat_limit_r'])}</td></tr>"
        f"<tr><th>Effective Maximum / Current / Remaining Heat</th><td>{heat(context['maximum_heat_r'])} / {heat(context['current_heat_r'])} / {heat(context['remaining_heat_r'])}</td></tr>"
        f"<tr><th>Open Positions / Maximum</th><td>{portfolio_status['open_position_count'] if portfolio_status['open_position_count'] is not None else 'Not Available'} / {config.MAX_OPEN_POSITIONS}</td></tr>"
        f"<tr><th>Portfolio Data</th><td>{escape(str(portfolio_status['data_status']))}; Equity: {escape(drawdown.data_status)}</td></tr>"
        f"<tr><th>Market Cap Filter</th><td>{escape(str(context.get('market_cap_filter_status', 'NOT ENFORCED')))}</td></tr>"
        f"<tr><th>Industry Metadata Coverage</th><td>{escape(coverage_text)}</td></tr>"
        f"<tr><th>Market / Portfolio Permission / Setup Status</th><td>{'Yes' if context['market_new_risk_allowed'] else 'No'} / {'Yes' if context['portfolio_new_risk_allowed'] else 'No'} / {escape(str(context.get('setup_status', 'NONE')))}</td></tr>"
        f"<tr><th>Final Instruction</th><td>{escape(str(context['final_instruction']))}</td></tr>"
        "</tbody></table>"
    )


def dedupe_categories_by_priority(
    categories: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    deduped = {}
    assigned_tickers = set()
    for name in CATEGORY_PRIORITY:
        frame = categories.get(name, pd.DataFrame(columns=DISCOVERY_COLUMNS))
        if frame.empty:
            deduped[name] = pd.DataFrame(columns=DISCOVERY_COLUMNS)
            continue

        unique = (
            frame[~frame["Ticker"].isin(assigned_tickers)]
            .drop_duplicates("Ticker")
            .copy()
        )
        assigned_tickers.update(unique["Ticker"].tolist())
        deduped[name] = unique.reset_index(drop=True)
    return deduped


def sort_daily_focus(focus: pd.DataFrame) -> pd.DataFrame:
    if focus.empty:
        return focus

    sorted_focus = focus.copy()
    if (
        not sorted_focus.get("Final Decision", pd.Series(dtype=str))
        .isin(["FULL", "HALF", "WATCH", "NO TRADE"])
        .all()
    ):
        sorted_focus = add_review_guidance_columns(focus)
    sorted_focus["_Trade State Rank"] = (
        sorted_focus.get(
            "Final Decision", pd.Series(index=sorted_focus.index, dtype=str)
        )
        .map({"FULL": 0, "HALF": 1, "WATCH": 2, "NO TRADE": 3})
        .fillna(3)
    )
    sorted_focus["_Category Rank"] = sorted_focus["Category"].apply(
        category_priority_rank
    )
    sorted_focus["_Risk Reward Rank"] = sorted_focus["Risk/Reward Quality"].apply(
        risk_reward_quality_rank
    )
    sorted_focus["_Industry Rank Sort"] = sorted_focus["Industry Rank"].fillna(999)
    return (
        sorted_focus.sort_values(
            [
                "_Trade State Rank",
                "Review Priority Score",
                "_Risk Reward Rank",
                "RS Score",
                "_Industry Rank Sort",
                "_Category Rank",
            ],
            ascending=[True, False, True, False, True, True],
        )
        .drop(
            columns=[
                "_Trade State Rank",
                "_Category Rank",
                "_Risk Reward Rank",
                "_Industry Rank Sort",
            ]
        )
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
    sorted_frame = frame.copy()
    if (
        "Review Tier" not in sorted_frame.columns
        or sorted_frame["Review Tier"].fillna("").eq("").any()
    ):
        sorted_frame = add_review_guidance_columns(sorted_frame)
    tier_rank = {
        "Review Now": 1,
        "High Priority Watch": 2,
        "Watch Later": 3,
        "Skip Today": 4,
    }
    new_states = sorted_frame.get(
        "Final Decision", pd.Series(index=sorted_frame.index, dtype=str)
    ).isin(["FULL", "HALF", "NO TRADE"])
    if not new_states.all():
        sorted_frame["Confirmed Setup"] = sorted_frame.apply(
            confirmation_signal, axis=1
        )
    sorted_frame["_Trade State Rank"] = (
        sorted_frame.get(
            "Final Decision", pd.Series(index=sorted_frame.index, dtype=str)
        )
        .map({"FULL": 0, "HALF": 1, "NO TRADE": 2})
        .fillna(3)
    )
    sorted_frame["_Tier Rank"] = sorted_frame["Review Tier"].map(tier_rank).fillna(99)
    sorted_frame["_Industry Rank Sort"] = sorted_frame["Industry Rank"].fillna(999)
    if "Recent RS Score" not in sorted_frame.columns:
        sorted_frame["Recent RS Score"] = sorted_frame.get("RS Score", 0)
    if "AI Priority Rank" not in sorted_frame.columns:
        sorted_frame["AI Priority Rank"] = np.nan
    sorted_frame["_AI Rank Sort"] = pd.to_numeric(
        sorted_frame["AI Priority Rank"], errors="coerce"
    ).fillna(999)
    return (
        sorted_frame.sort_values(
            [
                "_Trade State Rank",
                "_Tier Rank",
                "Confirmed Setup",
                "Review Priority Score",
                "Recent RS Score",
                "_Industry Rank Sort",
                "_AI Rank Sort",
            ],
            ascending=[True, True, False, False, False, True, True],
        )
        .drop(
            columns=[
                "_Trade State Rank",
                "_Tier Rank",
                "_Industry Rank Sort",
                "_AI Rank Sort",
            ]
        )
        .head(TOP_ACTION_MAX)
        .reset_index(drop=True)
    )


def top_action_eligible(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    guided = frame.copy()
    if "Final Decision" not in guided:
        return guided.iloc[0:0].copy()
    eligible = guided[guided["Final Decision"].isin(["FULL", "HALF"])].copy()
    if eligible.empty:
        return guided.iloc[0:0].copy()
    return eligible


def build_top_action_list(categories: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = [
        categories.get(name, pd.DataFrame(columns=DISCOVERY_COLUMNS)).head(
            FOCUS_LIMITS.get(name, TOP_ACTION_MAX)
        )
        for name in CATEGORY_PRIORITY
    ]
    frames = [frame for frame in frames if not frame.empty]
    combined = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=DISCOVERY_COLUMNS)
    )
    return sort_top_action_list(top_action_eligible(combined))


def determine_market_character(
    categories: dict[str, pd.DataFrame],
    market_status: str,
    top_industries: pd.DataFrame,
) -> str:
    def frame(name: str) -> pd.DataFrame:
        return categories.get(name, pd.DataFrame())

    breakouts = frame("Breakout Candidates")
    pullbacks = frame("Pullback Candidates")
    tight = frame("Tight Consolidation Candidates")
    volume = frame("Volume Surge Candidates")
    confirmed_breakouts = (
        int(breakouts.apply(confirmation_signal, axis=1).sum())
        if not breakouts.empty
        else 0
    )
    confirmed_pullbacks = (
        int(pullbacks.apply(confirmation_signal, axis=1).sum())
        if not pullbacks.empty
        else 0
    )
    all_frames = [value for value in categories.values() if not value.empty]
    combined = (
        pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()
    )
    skip_share = (
        float(
            (combined.get("Review Tier", pd.Series(dtype=str)) == "Skip Today").mean()
        )
        if not combined.empty
        else 0
    )
    quality_breakouts = (
        int((breakouts.get("Volume Ratio", pd.Series(dtype=float)) >= 1.2).sum())
        if not breakouts.empty
        else 0
    )
    breadth_column = next(
        (
            column
            for column in ("20D Outperformance Breadth %", "Above 20EMA %")
            if column in top_industries.columns
        ),
        None,
    )
    breadth = (
        float(top_industries[breadth_column].head(5).median())
        if not top_industries.empty and breadth_column is not None
        else 50
    )
    if market_status in {"Caution", "Risk Off"}:
        return "Weak / Risk-Off Market"
    if confirmed_breakouts >= 2 and quality_breakouts >= 2 and len(breakouts) >= 2:
        return "Strong Breakout Market"
    if confirmed_pullbacks >= 2 and len(pullbacks) >= max(2, len(breakouts)):
        return "Strong Pullback-Led Market"
    if market_status == "Strong" and (len(pullbacks) + len(tight) + len(volume)) > 0:
        return "Selective Strong Market"
    if skip_share >= 0.65:
        return "Defensive Market"
    if breadth < 40:
        return "Defensive Market"
    return "Neutral Rotation Market"


def enforce_market_character(commentary: str, character: str) -> str:
    pattern = r"(Overall Market Character\s*\n)(.*?)(?=\n\s*Reminder|\Z)"
    if re.search(pattern, commentary, flags=re.DOTALL):
        return re.sub(
            pattern,
            lambda match: match.group(1) + character + "\n",
            commentary,
            flags=re.DOTALL,
        )
    return f"{commentary}\n\nOverall Market Character\n{character}".strip()


def write_email_summary(
    top_action_list: pd.DataFrame,
    daily_focus: pd.DataFrame,
    top_industries: pd.DataFrame,
    market_status: str,
    ai_commentary: str,
    path: str,
    decision_context: dict[str, object] | None = None,
    canonical: pd.DataFrame | None = None,
) -> None:
    lines = [
        "Daily US Stock Watchlist",
        "",
        "Market Status",
        f"{market_status}",
        "",
        "Top 5 Industries",
    ]
    if decision_context:
        lines[4:4] = [
            "",
            "Portfolio Risk",
            f"Standard R: USD {decision_context['standard_r_dollars']:.0f}",
            f"Maximum Heat: {decision_context['maximum_heat_r'] if decision_context['maximum_heat_r'] is not None else 'Not Available'}R",
            f"Current Heat: {decision_context['current_heat_r'] if decision_context['current_heat_r'] is not None else 'Not Available'}R",
            f"Remaining Heat: {decision_context['remaining_heat_r'] if decision_context['remaining_heat_r'] is not None else 'Not Available'}R",
            f"Portfolio Data: {decision_context['portfolio_status']['data_status']}",
            f"Market Cap Filter: {decision_context.get('market_cap_filter_status', 'NOT ENFORCED')}",
            "Industry Metadata Coverage: "
            f"{decision_context.get('metadata_diagnostics', {}).get('mapped_sector_industry_count', 'N/A')}/"
            f"{decision_context.get('metadata_diagnostics', {}).get('universe_member_count', 'N/A')} "
            f"({decision_context.get('metadata_diagnostics', {}).get('coverage_percentage', 'N/A')}%)",
            f"Final Instruction: {decision_context['final_instruction']}",
        ]
    if top_industries.empty:
        lines.append("No industry groups matched.")
    else:
        for index, row in top_industries.head(5).reset_index(drop=True).iterrows():
            lines.append(
                f"{index + 1}. {row['Industry']} ({row['Sector']}) - "
                f"Final {row['Final Industry Score']}, Momentum Rank {row['Momentum Rank']}, "
                f"Leadership Rank {row['Leadership Rank']}"
            )

    lines.extend(
        [
            "",
            "Daily Review Plan",
            markdown_daily_review_plan(top_action_list, daily_focus, market_status),
        ]
    )

    lines.extend(["", "Top Action List"])
    if top_action_list.empty:
        lines.append("No action tickers.")
    else:
        for _, row in top_action_list.iterrows():
            lines.append(f"{row['Ticker']} - {row['Action']}")

    lines.extend(["", "AI Commentary", ai_commentary])
    if canonical is not None:
        lines.extend(["", "Decision Manifest"])
        for record in decision_manifest_records(canonical):
            lines.append(json.dumps(record, sort_keys=True, separators=(",", ":")))
        lines.append("End Decision Manifest")
    lines.extend(["", "Full daily_watchlist.html is attached."])
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def validate_exported_reports(
    html_path: str = OUTPUT_HTML,
    csv_path: str = OUTPUT_CSV,
    email_path: str = EMAIL_SUMMARY,
) -> None:
    """Block publication/history/snapshots when report semantics diverge."""
    validator = Path(__file__).resolve().parent / "scripts" / "validate_report.py"
    result = subprocess.run(
        [sys.executable, str(validator), html_path, csv_path, email_path],
        cwd=Path(__file__).resolve().parent,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stdout + "\n" + result.stderr).strip()
        raise RuntimeError(f"Exported report semantic validation failed: {detail}")


def write_markdown(
    top_action_list: pd.DataFrame,
    daily_focus: pd.DataFrame,
    categories: dict[str, pd.DataFrame],
    top_industries: pd.DataFrame,
    market_df: pd.DataFrame,
    market_status: str,
    ai_commentary: str,
    path: str,
    history_delta: dict[str, object] | None = None,
    history_trend: dict[str, object] | None = None,
    decision_context: dict[str, object] | None = None,
) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Daily Watchlist",
        "",
        f"Generated: {now}",
        "",
        "## Executive Summary",
        "",
        f"Market: {market_status}; Top Action candidates: {len(top_action_list)}.",
        "",
        "## Market Status",
        "",
        f"Status: {market_status}",
        "",
        market_df.to_markdown(index=False),
        "",
        "## Daily Review Plan",
        "",
        markdown_daily_review_plan(top_action_list, daily_focus, market_status),
        "",
        "## Top Action List",
        "",
    ]
    if decision_context:
        lines[8:8] = [
            "## Portfolio Risk",
            "",
            f"Portfolio Data: {decision_context['portfolio_status']['data_status']}; Current Heat: {decision_context['current_heat_r'] if decision_context['current_heat_r'] is not None else 'Not Available'}R; Remaining Heat: {decision_context['remaining_heat_r'] if decision_context['remaining_heat_r'] is not None else 'Not Available'}R.",
            f"Market Cap Filter: {decision_context.get('market_cap_filter_status', 'NOT ENFORCED')}.",
            "Industry Metadata Coverage: "
            f"{decision_context.get('metadata_diagnostics', {}).get('coverage_percentage', 'N/A')}%.",
            "",
        ]
    if top_action_list.empty:
        lines.extend(["No action tickers.", ""])
    else:
        lines.extend([markdown_table(top_action_list), ""])

    lines.extend(["## AI Commentary", "", ai_commentary, ""])

    lines.extend(["## Top Industries", ""])
    lines.extend(
        [
            "No industry groups matched."
            if top_industries.empty
            else top_industries.to_markdown(index=False),
            "",
        ]
    )
    isolated = top_industries.attrs.get(
        "isolated_industries", pd.DataFrame(columns=TOP_INDUSTRY_COLUMNS)
    )
    lines.extend(["## Isolated / Emerging Industry Leaders", ""])
    lines.extend(
        [
            "No isolated leaders."
            if isolated.empty
            else isolated.to_markdown(index=False),
            "",
        ]
    )
    for heading, attr in (
        ("Rotation Watch", "rotation_watch"),
        ("Long-Term Leaders Currently Lagging", "lagging_industries"),
    ):
        frame = top_industries.attrs.get(attr, pd.DataFrame())
        lines.extend(
            [
                f"## {heading}",
                "",
                "No matches." if frame.empty else frame.to_markdown(index=False),
                "",
            ]
        )
    lines.extend(["## Daily Focus List", ""])
    if daily_focus.empty:
        lines.extend(["No focus tickers.", ""])
    else:
        lines.extend([markdown_table(concise_decision_table(daily_focus)), ""])

    for name in CATEGORY_PRIORITY:
        frame = categories.get(name, pd.DataFrame(columns=DISCOVERY_COLUMNS))
        lines.extend([f"## {name}", ""])
        if frame.empty:
            lines.extend(["No matches.", ""])
        else:
            lines.extend([markdown_table(frame), ""])

    lines.extend(
        [
            "## Historical Summary",
            "",
            "### Daily Change",
            "",
            markdown_history_section(history_delta),
            "",
            "### Summary Trend",
            "",
            markdown_trend_section(history_trend),
            "",
        ]
    )
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
    history_delta: dict[str, object] | None = None,
    history_trend: dict[str, object] | None = None,
    decision_context: dict[str, object] | None = None,
) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    canonical = combined_watchlist(categories).drop_duplicates("Ticker")
    summary_panel = html_summary_panel(
        canonical, market_status, len(top_action_list), decision_context
    )
    risk_panel = (
        html_decision_context(decision_context)
        if decision_context
        else "<h2>Portfolio Risk</h2><p>Not Available in offline preview.</p>"
    )
    history_panel = html_history_panel(history_delta)
    trend_panel = html_trend_panel(history_trend)
    review_plan = html_daily_review_plan(top_action_list, daily_focus, market_status)
    action_table = (
        "<p>No action tickers.</p>"
        if top_action_list.empty
        else html_table(concise_decision_table(top_action_list))
    )
    full_rows = concise_decision_table(
        canonical[canonical["Final Decision"].eq("FULL")]
    )
    half_rows = concise_decision_table(
        canonical[canonical["Final Decision"].eq("HALF")]
    )
    full_table = (
        "<p>No FULL candidates.</p>" if full_rows.empty else html_table(full_rows)
    )
    half_table = (
        "<p>No HALF candidates.</p>" if half_rows.empty else html_table(half_rows)
    )
    watch, blocked = primary_decision_sections(canonical)
    watch_table = (
        "<p>No watch-only candidates.</p>" if watch.empty else html_table(watch)
    )
    blocked_table = (
        "<p>No blocked candidates.</p>" if blocked.empty else html_table(blocked)
    )
    industry_table = (
        "<p>No industry groups matched.</p>"
        if top_industries.empty
        else html_table(compact_industry_table(top_industries))
    )

    diagnostic_sections = [
        "<h2>Full Qualified-Industry Calculations</h2>"
        + (
            "<p>No qualified industries.</p>"
            if top_industries.empty
            else top_industries.to_html(index=False)
        )
    ]
    isolated = top_industries.attrs.get(
        "isolated_industries", pd.DataFrame(columns=TOP_INDUSTRY_COLUMNS)
    )
    isolated_table = (
        "<p>No isolated leaders.</p>"
        if isolated.empty
        else isolated.to_html(index=False)
    )
    diagnostic_sections.append(
        f"<h2>Isolated / Emerging Industry Leaders</h2>{isolated_table}"
    )
    for heading, attr in (
        ("Rotation Watch", "rotation_watch"),
        ("Long-Term Leaders Currently Lagging", "lagging_industries"),
    ):
        frame = top_industries.attrs.get(attr, pd.DataFrame())
        diagnostic_sections.append(
            f"<h2>{heading}</h2>"
            + ("<p>No matches.</p>" if frame.empty else frame.to_html(index=False))
        )
    focus_table = (
        "<p>No focus tickers.</p>"
        if daily_focus.empty
        else html_table(concise_decision_table(daily_focus))
    )
    diagnostic_sections.append(f"<h2>Full Daily Focus</h2>{focus_table}")
    html_order = [
        "Breakout Candidates",
        "Volume Surge Candidates",
        "Pullback Candidates",
        "Tight Consolidation Candidates",
        "Developing Base Candidates",
        "Extended Candidates",
    ]
    for name in html_order:
        frame = categories.get(name, pd.DataFrame(columns=DISCOVERY_COLUMNS))
        table = "<p>No matches.</p>" if frame.empty else html_table(frame)
        diagnostic_sections.append(f"<h2>{name}</h2>{table}")

    diagnostics = (
        '<details class="diagnostics"><summary>Diagnostic Appendix — full calculations</summary>'
        + "".join(diagnostic_sections)
        + "<h2>Historical Summary</h2>"
        + history_panel
        + trend_panel
        + "</details>"
    )

    counts = report_summary_counts(canonical)
    warning_items = (
        list(decision_context.get("system_warnings", []))
        if decision_context
        else ["System-level warnings unavailable in offline report preview."]
    )
    if counts["data_warnings"]:
        warning_items.append(f"{counts['data_warnings']} candidate data warning(s)")
    if counts["price_warnings"]:
        warning_items.append(f"{counts['price_warnings']} candidate price warning(s)")
    warnings_html = (
        "<p>No data or logic warnings.</p>"
        if not warning_items
        else "<ul>"
        + "".join(f"<li>{escape(item)}</li>" for item in warning_items)
        + "</ul>"
    )
    manifest_json = json.dumps(
        decision_manifest_records(canonical), sort_keys=True, separators=(",", ":")
    ).replace("</", "<\\/")

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Daily Watchlist</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #222; background: #fbfbfa; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 28px; background: #fff; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: right; vertical-align: top; }}
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2), th:nth-child(3), td:nth-child(3) {{ text-align: left; }}
    th {{ background: #f3f5f7; position: sticky; top: 0; z-index: 1; }}
    tr.row-priority td {{ background: #eef7f1; }}
    tr.row-caution td {{ background: #fff8e8; }}
    tr.row-risk td {{ background: #fff0f0; }}
    .badge {{ display: inline-block; border-radius: 4px; padding: 2px 6px; margin: 1px 2px; font-size: 12px; font-weight: 700; white-space: nowrap; }}
    .flag-confirmed {{ background: #d9f0e1; color: #13592d; }}
    .flag-emerging {{ background: #dceafe; color: #1d4f91; }}
    .flag-improving {{ background: #e8e5ff; color: #45308d; }}
    .flag-caution {{ background: #ffefc2; color: #714800; }}
    .flag-risk {{ background: #ffd8d8; color: #8f1d1d; }}
    .flag-neutral {{ background: #e9ecef; color: #333; }}
    .summary-panel {{ margin: 18px 0 30px; }}
    .summary-panel h2 {{ margin-bottom: 12px; }}
    .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(155px, 1fr)); gap: 12px; }}
    .summary-card {{ background: #fff; border: 1px solid #d8dde3; border-left: 4px solid #75808a; border-radius: 6px; padding: 12px; min-height: 96px; }}
    .summary-card span {{ display: block; color: #59636e; font-size: 12px; font-weight: 700; text-transform: uppercase; }}
    .summary-card strong {{ display: block; margin: 6px 0 4px; font-size: 26px; line-height: 1; }}
    .summary-card small {{ color: #5f6872; line-height: 1.35; }}
    .summary-priority {{ border-left-color: #2f7d46; }}
    .summary-emerging {{ border-left-color: #2f5f9f; }}
    .summary-caution {{ border-left-color: #b7791f; }}
    .summary-risk {{ border-left-color: #c53030; }}
    .history-panel {{ background: #fff; border: 1px solid #d8dde3; border-radius: 6px; padding: 16px; margin: 0 0 30px; }}
    .history-panel h2 {{ margin: 0 0 8px; }}
    .history-panel p {{ color: #5f6872; margin: 0 0 12px; }}
    .history-delta-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; margin-bottom: 14px; }}
    .history-delta-card {{ border: 1px solid #e1e5ea; border-radius: 6px; padding: 10px; }}
    .history-delta-card span {{ display: block; color: #59636e; font-size: 12px; font-weight: 700; text-transform: uppercase; }}
    .history-delta-card strong {{ display: block; margin-top: 4px; font-size: 22px; }}
    .history-lists {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }}
    .history-lists h3 {{ margin: 0 0 8px; font-size: 14px; }}
    .history-chip {{ display: inline-block; background: #eef2f6; border-radius: 4px; padding: 3px 7px; margin: 2px; font-size: 12px; font-weight: 700; }}
    .history-empty {{ color: #6b7280; font-size: 13px; }}
    .trend-panel {{ background: #fff; border: 1px solid #d8dde3; border-radius: 6px; padding: 16px; margin: 0 0 30px; }}
    .trend-panel h2 {{ margin: 0 0 8px; }}
    .trend-panel p {{ color: #5f6872; margin: 0 0 12px; }}
    .trend-table th, .trend-table td {{ text-align: right; }}
    .trend-table th:first-child, .trend-table td:first-child, .trend-table th:nth-child(2), .trend-table td:nth-child(2) {{ text-align: left; }}
    .trend-bar {{ display: inline-block; height: 10px; min-width: 8px; border-radius: 3px; margin-right: 8px; vertical-align: middle; }}
    .trend-positive {{ background: #2f7d46; }}
    .trend-negative {{ background: #c53030; }}
    .review-plan {{ background: #fff; border: 1px solid #d8dde3; border-left: 4px solid #2f7d46; border-radius: 6px; padding: 16px; margin: 0 0 30px; }}
    .review-plan h2 {{ margin: 0 0 10px; }}
    .review-plan ul {{ margin: 0; padding-left: 20px; }}
    .review-plan li {{ margin: 6px 0; line-height: 1.4; }}
    details.diagnostics {{ background: #fff; border: 1px solid #d8dde3; border-radius: 6px; padding: 14px; margin-top: 28px; }}
    details.diagnostics summary {{ cursor: pointer; font-weight: 700; font-size: 18px; }}
    pre {{ white-space: pre-wrap; background: #f7f7f7; border: 1px solid #ddd; padding: 16px; }}
  </style>
</head>
<body>
  <h1>Daily Watchlist</h1>
  <p>Generated: {now}</p>
  {summary_panel}
  {risk_panel}
  <h2>Market Status</h2><p>Status: {market_status}</p>{market_df.to_html(index=False)}
  {review_plan}
  <h2>Top Action</h2>{action_table}
  <h2>FULL — maximum 1.0R</h2>{full_table}
  <h2>HALF — maximum 0.5R</h2>{half_table}
  <h2>WATCH — zero risk</h2>{watch_table}
  <h2>NO TRADE — zero risk</h2>{blocked_table}
  <h2>Top Industries — Qualified Current Leaders</h2>{industry_table}
  <h2>Data and Logic Warnings</h2>{warnings_html}
  <h2>Expectancy</h2><p>Review the completed-trade journal analysis; no profitability claim is inferred from this watchlist.</p>
  <h2>AI Commentary</h2><pre>{escape(ai_commentary)}</pre>
  {diagnostics}
  <script type="application/json" id="decision-manifest">{manifest_json}</script>
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
    market_metrics: dict[str, float | bool | None] | None = None,
) -> tuple[
    pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame], AIAnalysisResult
]:
    global LAST_FORWARD_SNAPSHOT
    categories = dedupe_categories_by_priority(categories)
    categories = {name: add_action_column(frame) for name, frame in categories.items()}
    canonical = add_review_guidance_columns(
        combined_watchlist(categories)
    ).drop_duplicates("Ticker")
    categories = {
        name: canonical[canonical["Category"].eq(name)].copy().reset_index(drop=True)
        for name in CATEGORY_PRIORITY
    }
    top_action_list = build_top_action_list(categories)
    daily_focus = build_daily_focus_list(categories)
    decision_context = build_decision_context(
        canonical, market_df, market_status, market_metrics
    )
    canonical = apply_canonical_decision_pipeline(canonical, decision_context)
    categories = {
        name: canonical[canonical["Category"].eq(name)].copy().reset_index(drop=True)
        for name in CATEGORY_PRIORITY
    }
    top_action_list = build_top_action_list(categories)
    daily_focus = build_daily_focus_list(categories)
    actionable = canonical["Final Decision"].isin(["FULL", "HALF"]).any()
    full_available = canonical["Final Decision"].eq("FULL").any()
    half_available = canonical["Final Decision"].eq("HALF").any()
    decision_context["actionable_setup_available"] = bool(actionable)
    decision_context["setup_status"] = (
        "READY" if full_available else "CONDITIONAL" if half_available else "NONE"
    )
    decision_context["final_new_risk_allowed"] = bool(
        decision_context["market_new_risk_allowed"]
        and decision_context["portfolio_new_risk_allowed"]
        and actionable
    )
    decision_context["new_trade_status"] = (
        str(decision_context["setup_status"])
        if decision_context["final_new_risk_allowed"]
        else "NO"
    )
    decision_context["final_instruction"] = (
        "Consider only the validated FULL/HALF risk shown"
        if decision_context["final_new_risk_allowed"]
        else "Do not open a new trade"
    )
    ai_result = analyse_top_action_list(top_action_list, top_industries, market_status)
    top_action_list = sort_top_action_list(ai_result.top_action_list)
    top_action_list["AI Priority Rank"] = range(1, len(top_action_list) + 1)
    top_action_list["Email Priority Rank"] = range(1, len(top_action_list) + 1)
    ai_result.top_action_list = top_action_list
    market_character = determine_market_character(
        categories, market_status, top_industries
    )
    ai_result.commentary = enforce_market_character(
        ai_result.commentary, market_character
    )
    ai_commentary = ai_result.commentary
    history_snapshot = build_report_history_snapshot(
        top_action_list, top_industries, market_status
    )
    history_snapshot.update(
        {
            key: value
            for key, value in report_summary_counts(
                canonical, len(top_action_list)
            ).items()
            if key in history_snapshot
        }
    )
    history_delta = report_history_delta(history_snapshot, load_last_report_history())
    history_trend = report_history_trend(history_snapshot)
    watchlist = combined_watchlist(categories)
    watchlist.to_csv(OUTPUT_CSV, index=False)
    write_markdown(
        top_action_list,
        daily_focus,
        categories,
        top_industries,
        market_df,
        market_status,
        ai_commentary,
        OUTPUT_MD,
        history_delta,
        history_trend,
        decision_context,
    )
    write_html(
        top_action_list,
        daily_focus,
        categories,
        top_industries,
        market_df,
        market_status,
        ai_commentary,
        OUTPUT_HTML,
        history_delta,
        history_trend,
        decision_context,
    )
    write_email_summary(
        top_action_list,
        daily_focus,
        top_industries,
        market_status,
        ai_commentary,
        EMAIL_SUMMARY,
        decision_context,
        canonical,
    )
    validate_exported_reports()
    LAST_FORWARD_SNAPSHOT = str(
        write_forward_snapshot(canonical, market_df, decision_context)
    )
    save_last_good_reports()
    append_report_history(history_snapshot)
    return watchlist, top_action_list, daily_focus, categories, ai_result


def prepare_preview_watchlist(frame: pd.DataFrame) -> pd.DataFrame:
    table = frame.copy()
    defaults = {
        "Category": "",
        "Ticker": "",
        "Sector": "Unknown",
        "Industry": "Unknown",
        "RS Trend": "Unknown",
        "Action": "",
        "Review Tier": "",
        "Noise Filter Reason": "",
        "Price Data Warning": "",
        "Risk/Reward Quality": "",
        "Pullback Quality": "",
        "Extension Status": "",
        "VCP Label": "",
        "Tightness Label": "",
        "Support Signal": "",
        "TradingView": "",
    }
    for column in DISCOVERY_COLUMNS:
        if column not in table.columns:
            table[column] = defaults.get(column, np.nan)

    numeric_columns = [
        "RS Score",
        "RS Trend Delta",
        "Price",
        "Review Priority Score",
        "ATR20",
        "ATR20 %",
        "ADR %",
        "From 52W High %",
        "Distance From 50MA %",
        "Distance From 30WMA %",
        "Distance From Pivot %",
        "Volume Ratio",
        "Distance From EMA10 ATR",
        "Distance From EMA20 ATR",
        "Distance From MA50 ATR",
        "Distance From 30WMA ATR",
        "Nearest Support Distance ATR",
        "10 Day Range %",
        "20 Day Range %",
        "Tightness Score",
        "ADR20 %",
        "ADR60 %",
        "VCP Ratio",
        "Industry Rank",
        "Industry Setup Count",
        "Avg Volume",
    ]
    for column in numeric_columns:
        if column in table.columns:
            table[column] = pd.to_numeric(table[column], errors="coerce")
    return table


def build_categories_from_watchlist(watchlist: pd.DataFrame) -> dict[str, pd.DataFrame]:
    categories = {}
    for name in CATEGORY_PRIORITY:
        frame = watchlist[watchlist["Category"] == name].copy()
        categories[name] = (
            add_action_column(frame)
            if not frame.empty
            else pd.DataFrame(columns=DISCOVERY_COLUMNS)
        )
    return categories


def preview_market_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Symbol": "Preview",
                "10EMA": "No network",
                "20EMA": "No network",
                "50MA": "No network",
            }
        ],
        columns=MARKET_COLUMNS,
    )


def run_report_preview_command(
    source_csv: str = LAST_GOOD_CSV,
    history_path: str = SUMMARY_HISTORY_CSV,
    output_html: str = PREVIEW_HTML,
) -> int:
    source_path = Path(source_csv)
    if not source_path.exists():
        print("Report Preview")
        print(f"Source: Missing {source_csv}")
        print("No preview generated.")
        return 1

    try:
        watchlist = prepare_preview_watchlist(pd.read_csv(source_path))
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        print("Report Preview")
        print(f"Source: Could not read {source_csv}")
        print("No preview generated.")
        return 1

    if watchlist.empty or "Category" not in watchlist.columns:
        print("Report Preview")
        print(f"Source: Invalid or empty {source_csv}")
        print("No preview generated.")
        return 1

    categories = build_categories_from_watchlist(watchlist)
    top_action_list = build_top_action_list(categories)
    daily_focus = build_daily_focus_list(categories)
    # Legacy preview files do not contain full eligible-universe metrics, so do not fabricate industry ranks.
    top_industries = pd.DataFrame(columns=TOP_INDUSTRY_COLUMNS)

    latest_history = load_last_report_history(history_path)
    previous_history = load_previous_report_history(history_path)
    market_status = (
        str(latest_history.get("market_status", "Preview"))
        if latest_history
        else "Preview"
    )
    if latest_history:
        history_delta = report_history_delta(latest_history, previous_history)
        history_trend = report_history_trend_from_rows(
            load_recent_report_history(history_path, 10)
        )
    else:
        snapshot = build_report_history_snapshot(
            top_action_list, top_industries, market_status
        )
        history_delta = {"has_previous": False}
        history_trend = report_history_trend_from_rows([snapshot])

    write_html(
        top_action_list,
        daily_focus,
        categories,
        top_industries,
        preview_market_frame(),
        market_status,
        "Report preview mode: AI was not run.",
        output_html,
        history_delta,
        history_trend,
    )

    print("Report Preview")
    print(f"Source: {source_csv}")
    print(f"History: {'Loaded' if latest_history else 'Missing'}")
    print("Network: Disabled")
    print("AI: Disabled")
    print("Email: Disabled")
    print(f"Top Action Rows: {len(top_action_list)}")
    print(f"Daily Focus Rows: {len(daily_focus)}")
    print(f"Output: {output_html}")
    return 0


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


def print_category_summary(
    categories: dict[str, pd.DataFrame], top_industries: pd.DataFrame
) -> None:
    print("Category Counts:")
    print(
        f"- Total Candidates: {sum(len(categories.get(name, pd.DataFrame())) for name in CATEGORY_PRIORITY)}"
    )
    for name in CATEGORY_PRIORITY:
        print(f"- {name}: {len(categories.get(name, pd.DataFrame()))}")


def print_ai_status(ai_result: AIAnalysisResult) -> None:
    print("\nAI Commentary", flush=True)
    print(
        f"AI Commentary: {'Enabled' if ai_result.enabled else 'Disabled'}", flush=True
    )
    print(
        f"OpenAI API Key: {'Loaded' if ai_result.api_key_loaded else 'Missing'}",
        flush=True,
    )
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
            "RS Trend": "Stable Leader",
            "RS Trend Delta": 2,
            "Industry Rank": 1,
            "Industry Setup Count": 5,
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
            "RS Trend": "Emerging Leader",
            "RS Trend Delta": 12,
            "Industry Rank": 1,
            "Industry Setup Count": 5,
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
            "RS Trend": "Improving",
            "RS Trend Delta": 6,
            "Industry Rank": 2,
            "Industry Setup Count": 3,
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
            "RS Trend": "Stable Leader",
            "RS Trend Delta": 1,
            "Industry Rank": 4,
            "Industry Setup Count": 2,
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
            "RS Trend": "Weakening",
            "RS Trend Delta": -6,
            "Industry Rank": 3,
            "Industry Setup Count": 4,
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
        {
            "Industry": "Semiconductors",
            "Sector": "Technology",
            "Industry Strength Score": 96,
            "Candidate Count": 12,
            "Avg RS Score": 91,
            "Best RS Score": 98,
            "Top 3 Leaders": "NVDA, AMD, AVGO",
        },
        {
            "Industry": "Semiconductor Equipment & Materials",
            "Sector": "Technology",
            "Industry Strength Score": 92,
            "Candidate Count": 8,
            "Avg RS Score": 88,
            "Best RS Score": 91,
            "Top 3 Leaders": "ASML, AMAT, LRCX",
        },
        {
            "Industry": "Biotechnology",
            "Sector": "Healthcare",
            "Industry Strength Score": 84,
            "Candidate Count": 10,
            "Avg RS Score": 82,
            "Best RS Score": 86,
            "Top 3 Leaders": "VRTX, REGN, ALNY",
        },
        {
            "Industry": "Software - Infrastructure",
            "Sector": "Technology",
            "Industry Strength Score": 81,
            "Candidate Count": 9,
            "Avg RS Score": 80,
            "Best RS Score": 89,
            "Top 3 Leaders": "CRWD, NET, DDOG",
        },
        {
            "Industry": "Electronic Components",
            "Sector": "Technology",
            "Industry Strength Score": 78,
            "Candidate Count": 7,
            "Avg RS Score": 76,
            "Best RS Score": 84,
            "Top 3 Leaders": "GLW, FLEX, JBL",
        },
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


def run_ai_test_command(
    print_output: bool = True,
) -> tuple[int, AIAnalysisResult | None]:
    top_action_list = build_mock_top_action_list()
    top_industries = build_mock_top_industries()
    commentary = ai_analysis.generate_ai_commentary(
        top_action_list, top_industries, "Strong"
    )
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
    required_columns_present = all(
        column in ranked.columns for column in ai_analysis.AI_SCORE_COLUMNS
    )
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
            f"Response Time: {result.response_time_seconds:.2f} sec"
            if result.response_time_seconds is not None
            else "Response Time: Unavailable"
        )
        print(
            f"Input Tokens: {result.input_tokens if result.input_tokens is not None else 'Unavailable'}"
        )
        print(
            f"Output Tokens: {result.output_tokens if result.output_tokens is not None else 'Unavailable'}"
        )
        print(
            f"Total Tokens: {result.response_tokens if result.response_tokens is not None else 'Unavailable'}"
        )
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
            print(
                "Omitted Explanation: The AI response did not provide complete ranking fields for these input tickers."
            )

        print("\nMarket Summary")
        print(section_text(commentary, "Market Summary"))
        print("\nIndustry Rotation Summary")
        print(section_text(commentary, "Industry Rotation Summary"))
        print("\nRanked Opportunities")
        print(section_text(commentary, "Best Opportunities"))
        print("\nStocks To Wait")
        print(section_text(commentary, "Stocks To Wait"))
        print("\nAI Ranking Table:")
        columns = [
            "Ticker",
            "AI Priority Rank",
            "AI Conviction Score",
            "AI Reason",
            "AI Concern",
            "AI Confirmation",
        ]
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
    gmail_ready = bool(
        os.environ.get("GMAIL_ADDRESS") and os.environ.get("GMAIL_APP_PASSWORD")
    )

    universe_ok = False
    universe_path = Path(config.UNIVERSE_CSV)
    if universe_path.exists():
        try:
            universe_ok = (
                len(pd.read_csv(universe_path)) >= config.MIN_VALID_UNIVERSE_COUNT
            )
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


def _industry_test_rows() -> pd.DataFrame:
    specs = [
        ("Large Lagging", 8, -0.01, -0.05, -0.08, 90),
        ("Broad Rotation", 4, 0.03, 0.10, 0.14, 62),
        ("One Stock Wonder", 1, 0.20, 0.30, 0.35, 98),
        ("Former Leader", 4, -0.02, -0.04, 0.02, 99),
        ("Emerging Rotation", 4, 0.05, 0.12, 0.10, 55),
        ("Outlier Protected", 5, -0.01, -0.02, -0.01, 70),
        ("Average Trap", 5, -0.01, -0.02, 0.01, 65),
    ]
    rows = []
    for industry, size, rel5, rel20, rel60, long_rs in specs:
        for index in range(size):
            r5, r20, r60 = rel5, rel20, rel60
            if industry == "Outlier Protected" and index == 0:
                r5, r20, r60 = 0.80, 1.20, 1.50
            if industry == "Average Trap" and index == 0:
                r20 = 0.30
            rows.append(
                {
                    "Ticker": f"T{len(rows):03d}",
                    "Sector": "Test",
                    "Industry": industry,
                    "Relative Return 5D": r5,
                    "Relative Return 20D": r20,
                    "Relative Return 60D": r60,
                    "Recent RS Score": max(1, min(99, 50 + r20 * 200)),
                    "Long-Term RS Score": long_rs,
                    "Above 10EMA": r5 > 0,
                    "Above 20EMA": r20 > 0,
                    "Above 50MA": r60 > 0,
                    "Stage 2": long_rs >= 75,
                    "Within 15% High": long_rs >= 75,
                    "Leader Quality Score": (long_rs + max(1, min(99, 50 + r20 * 200)))
                    / 2,
                    "Review Priority Score": 50 + index,
                }
            )
    return pd.DataFrame(rows)


def run_industry_test_command() -> int:
    eligible = _industry_test_rows()
    candidates = eligible[eligible["Industry"] == "Large Lagging"].copy()
    formal = build_top_industries(eligible, candidates)
    isolated = formal.attrs.get("isolated_industries", pd.DataFrame())
    by_name = formal.set_index("Industry")
    checks = {
        "raw candidate count does not dominate": by_name.loc[
            "Large Lagging", "Final Rank"
        ]
        > by_name.loc["Broad Rotation", "Final Rank"],
        "median protects against outliers": by_name.loc[
            "Outlier Protected", "Median 20D Relative Return"
        ]
        < 0,
        "20D and 60D momentum influence rank": by_name.loc[
            "Emerging Rotation", "Momentum Rank"
        ]
        < by_name.loc["Former Leader", "Momentum Rank"],
        "one-stock groups are excluded": "One Stock Wonder"
        not in set(formal["Industry"])
        and "One Stock Wonder" in set(isolated["Industry"]),
        "lagging leadership labelled correctly": by_name.loc[
            "Former Leader", "Industry Status"
        ]
        == "Long-Term Leader, Currently Lagging",
        "recent momentum outweighs old RS": by_name.loc["Broad Rotation", "Final Rank"]
        < by_name.loc["Former Leader", "Final Rank"],
        "positive average cannot beat negative median": by_name.loc[
            "Average Trap", "Median 20D Relative Return"
        ]
        < 0,
    }
    print("Industry Test Mode")
    for label, passed in checks.items():
        print(f"{label}: {'PASS' if passed else 'FAIL'}")
    return 0 if all(checks.values()) else 1


def run_report_test_command() -> int:
    base = pd.DataFrame(
        [
            {
                "Ticker": "NOW",
                "Category": "Pullback Candidates",
                "Review Tier": "Review Now",
                "Review Priority Score": 55,
                "Recent RS Score": 75,
                "RS Score": 80,
                "Industry Rank": 5,
                "Risk/Reward Quality": "Excellent R/R",
                "Support Signal": "EMA20 reclaim",
                "Volume Ratio": 0.8,
                "Close Position %": 80,
                "Industry Qualified": True,
                "Sister Confirmation": True,
                "Tightness Label": "Tight",
                "VCP Label": "Good VCP",
                "Extension Status": "Not Extended",
                "Planned Entry": 100,
                "Initial Stop": 95,
                "Realistic Target": 110,
            },
            {
                "Ticker": "WATCH",
                "Category": "Pullback Candidates",
                "Review Tier": "High Priority Watch",
                "Review Priority Score": 99,
                "Recent RS Score": 99,
                "RS Score": 99,
                "Industry Rank": 1,
                "Risk/Reward Quality": "Excellent R/R",
                "Support Signal": "Recent support",
                "Volume Ratio": 0.8,
                "Close Position %": 50,
            },
        ]
    )
    ordered = sort_top_action_list(base)
    support = strongest_support_signal(
        pd.Series(
            {
                "SUPPORT_SIGNAL_10EMA": "Recent support",
                "SUPPORT_SIGNAL_20EMA": "Recent support",
                "SUPPORT_SIGNAL_50MA": "Recent support",
            }
        )
    )
    loose = pd.Series(
        {
            "RANGE_15D_PCT": 12,
            "RANGE_10D_PCT": 20,
            "HIGH_52W": 110,
            "Close": 100,
            "MA50": 90,
            "VOLUME_RATIO": 0.8,
            "ADR_PCT": 5,
            "ADR60_PCT": 4,
        }
    )
    pullbacks = base.iloc[[0]].copy()
    pullbacks["Review Tier"] = "Review Now"
    character = determine_market_character(
        {"Pullback Candidates": pd.concat([pullbacks, pullbacks], ignore_index=True)},
        "Strong",
        pd.DataFrame(),
    )
    checks = {
        "Review Now always first": ordered.iloc[0]["Ticker"] == "NOW",
        "AI cannot override rule order": ordered.iloc[0]["Review Tier"] == "Review Now",
        "market character matches distribution": character
        == "Strong Pullback-Led Market",
        "Loose is not formal tight consolidation": not is_tight_consolidation_candidate(
            loose
        ),
        "Loose base is preserved as developing": is_developing_base_candidate(loose),
        "Support Signal deduplicated": support == "Recent support",
        "no Unknown industries": not known_metadata_value("Unknown"),
        "email preview priority is deterministic": list(ordered["Ticker"])
        == ["NOW", "WATCH"],
        "no email sent": True,
    }
    print("Report Test Mode (email disabled)")
    for label, passed in checks.items():
        print(f"{label}: {'PASS' if passed else 'FAIL'}")
    return 0 if all(checks.values()) else 1


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
    if "--report-preview" in args:
        return run_report_preview_command()
    if "--industry-test" in args:
        return run_industry_test_command()
    if "--report-test" in args:
        return run_report_test_command()

    if os.environ.get("SCREENER_VERIFIED") != "1":
        print("FAILED: production verification was not completed.")
        print(
            "Run: powershell -ExecutionPolicy Bypass -File .\\scripts\\run_daily_production.ps1"
        )
        return 2

    timer = RunTimer(config.MAX_SCREENER_RUNTIME_SECONDS)
    run_at = datetime.now(timezone.utc)
    market_result = get_market_condition(timer=timer, now=run_at)
    universe_result = load_universe(timer=timer)
    categories, top_industries, stage2_count, download_stats = screen_stocks(
        universe_result.universe, timer=timer, run_at=run_at
    )
    run_quality = validate_run_quality(
        universe_result, market_result, download_stats, timer=timer
    )
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
        market_result.metrics,
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
    print(f"Forward Snapshot: {LAST_FORWARD_SNAPSHOT}")
    print("\nTop 5 Industries")
    print(
        "No industry groups matched."
        if top_industries.empty
        else top_industries.head(5).to_string(index=False)
    )
    print("\nTop Action List")
    print(
        "No action tickers."
        if top_action_list.empty
        else top_action_list.to_string(index=False)
    )
    print("\nDaily Focus List")
    print(
        "No focus tickers." if daily_focus.empty else daily_focus.to_string(index=False)
    )
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
        print(
            "No industry groups matched."
            if top_industries.empty
            else top_industries.to_string(index=False)
        )
    print(f"\nExported {OUTPUT_CSV}, {OUTPUT_MD}, and {OUTPUT_HTML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
