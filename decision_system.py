"""Deterministic trading-decision, portfolio-risk, and expectancy models.

This module never executes trades. Missing required values remain missing and
become explicit validation/decision reasons instead of optimistic fallbacks.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

import config


DECISIONS = {"FULL", "HALF", "WATCH", "NO TRADE"}
SUPPORTED_POSITION_STATUSES = {"open", "closed"}


def normalise_position_status(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().lower()


@dataclass(frozen=True)
class Position:
    ticker: str
    entry_date: str
    entry_price: float
    initial_stop: float
    current_stop: float
    current_price: float
    shares: float
    standard_r_dollars_at_entry: float
    industry: str
    sector: str
    theme: str
    setup_type: str
    status: str
    last_updated: str
    stop_update_reason: str = ""
    notes: str = ""
    previous_stop: float | None = None


@dataclass(frozen=True)
class PositionRisk:
    ticker: str
    initial_risk_dollars: float
    initial_risk_r: float
    unrealised_pnl_dollars: float
    unrealised_pnl_r: float
    pnl_at_stop_dollars: float
    pnl_at_stop_r: float
    current_open_risk_dollars: float
    current_open_risk_r: float
    effective_open_risk_r: float
    industry: str
    sector: str
    theme: str


@dataclass(frozen=True)
class PortfolioRisk:
    positions: tuple[PositionRisk, ...]
    portfolio_heat_r: float
    maximum_heat_r: float
    remaining_heat_r: float
    industry_heat: dict[str, float]
    sector_heat: dict[str, float]
    theme_heat: dict[str, float]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class MarketRegime:
    market_score: float
    regime: str
    maximum_heat_r: float
    positive_factors: tuple[str, ...]
    negative_factors: tuple[str, ...]
    explanation: str
    data_complete: bool
    confidence: str
    new_risk_allowed: bool
    component_scores: dict[str, float] | None = None


@dataclass(frozen=True)
class RewardRisk:
    ratio: float | None
    label: str
    valid: bool
    reason: str


@dataclass(frozen=True)
class TradePlan:
    planned_entry: float | None
    planned_entry_source: str
    structural_stop: float | None
    structural_stop_source: str
    realistic_target: float | None
    realistic_target_source: str
    reward_risk_ratio: float | None
    confidence: str
    validation_reasons: tuple[str, ...]


@dataclass(frozen=True)
class ScoreBreakdown:
    recent_rs_component: float
    industry_sister_component: float
    setup_quality_component: float
    volume_component: float
    entry_stop_component: float
    intermediate_trend_component: float
    base_score: float
    penalties: dict[str, float]
    total_penalty: float
    final_score: float


@dataclass(frozen=True)
class DecisionResult:
    decision: str
    confirmed_setup: bool
    review_tier: str
    final_score: float
    reasons: tuple[str, ...]
    blocking_reasons: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class DrawdownState:
    mode: str
    current_equity: float | None
    high_water_mark_equity: float | None
    drawdown_dollars: float | None
    drawdown_r: float | None
    heat_limit_r: float
    full_allowed: bool
    new_risk_allowed: bool
    data_status: str


@dataclass(frozen=True)
class TradeSizingDecision:
    state: str
    maximum_risk_r: float
    maximum_risk_dollars: float
    maximum_shares: int
    reasons: tuple[str, ...]
    missing_confirmations: tuple[str, ...]
    setup_integrity: str = "UNKNOWN"
    actionable: bool = False


@dataclass(frozen=True)
class SetupIntegrityResult:
    state: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ExpectancySummary:
    sample_size: int
    sample_label: str
    expectancy_r: float | None
    win_rate: float | None
    average_win_r: float | None
    average_loss_r: float | None
    average_cost_and_slippage_r: float | None
    payoff_ratio: float | None
    profit_factor: float | None
    maximum_drawdown_r: float | None
    rolling_20_expectancy_r: float | None
    rolling_50_expectancy_r: float | None


def _required_text(value: object) -> bool:
    return bool(str(value or "").strip()) and str(value).strip().lower() not in {
        "unknown",
        "nan",
        "none",
    }


def validate_position(position: Position, now: datetime | None = None) -> list[str]:
    errors: list[str] = []
    if not _required_text(position.ticker):
        errors.append("ticker is missing")
    for name in (
        "entry_price",
        "initial_stop",
        "current_stop",
        "current_price",
        "standard_r_dollars_at_entry",
    ):
        value = getattr(position, name)
        if value is None or not np.isfinite(value) or value <= 0:
            errors.append(f"{name} must be positive")
    if (
        position.shares is None
        or not np.isfinite(position.shares)
        or position.shares <= 0
    ):
        errors.append("shares must be positive")
    if position.initial_stop >= position.entry_price:
        errors.append("long initial stop must be below entry")
    if position.current_stop >= position.current_price:
        errors.append("long current stop must be below current market price")
    if (
        position.previous_stop is not None
        and position.current_stop < position.previous_stop
        and not _required_text(position.stop_update_reason)
    ):
        errors.append("current stop moved lower without documented override reason")
    for name in ("sector", "industry", "theme"):
        if not _required_text(getattr(position, name)):
            errors.append(f"{name} mapping is missing")
    try:
        updated = datetime.fromisoformat(position.last_updated.replace("Z", "+00:00"))
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        reference = now or datetime.now(timezone.utc)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        if (reference - updated).total_seconds() > config.POSITION_STALE_HOURS * 3600:
            errors.append("position data is stale")
    except (TypeError, ValueError):
        errors.append("last_updated is invalid")
    return errors


def calculate_position_risk(
    position: Position, gap_floor_r: float | None = None
) -> PositionRisk:
    errors = validate_position(position)
    if errors:
        raise ValueError("; ".join(errors))
    standard_r = position.standard_r_dollars_at_entry
    initial = max(0.0, position.entry_price - position.initial_stop) * position.shares
    unrealised = (position.current_price - position.entry_price) * position.shares
    pnl_stop = (position.current_stop - position.entry_price) * position.shares
    current = max(0.0, position.current_price - position.current_stop) * position.shares
    current_r = current / standard_r
    effective = max(
        current_r,
        config.OVERNIGHT_GAP_RISK_FLOOR_R if gap_floor_r is None else gap_floor_r,
    )
    return PositionRisk(
        ticker=position.ticker.upper(),
        initial_risk_dollars=round(initial, 2),
        initial_risk_r=round(initial / standard_r, 4),
        unrealised_pnl_dollars=round(unrealised, 2),
        unrealised_pnl_r=round(unrealised / standard_r, 4),
        pnl_at_stop_dollars=round(pnl_stop, 2),
        pnl_at_stop_r=round(pnl_stop / standard_r, 4),
        current_open_risk_dollars=round(current, 2),
        current_open_risk_r=round(current_r, 4),
        effective_open_risk_r=round(effective, 4),
        industry=position.industry,
        sector=position.sector,
        theme=position.theme,
    )


def calculate_portfolio_risk(
    positions: Iterable[Position],
    market_regime: str,
    maximum_heat_override_r: float | None = None,
) -> PortfolioRisk:
    items = list(positions)
    statuses = [normalise_position_status(position.status) for position in items]
    unsupported_statuses = sorted(set(statuses) - SUPPORTED_POSITION_STATUSES)
    if unsupported_statuses:
        labels = [status or "<blank>" for status in unsupported_statuses]
        raise ValueError("unsupported position status: " + ", ".join(labels))
    tickers = [
        position.ticker.upper()
        for position, status in zip(items, statuses, strict=True)
        if status == "open"
    ]
    warnings = [
        f"duplicate open position: {ticker}"
        for ticker in sorted(set(tickers))
        if tickers.count(ticker) > 1
    ]
    risks: list[PositionRisk] = []
    for position, status in zip(items, statuses, strict=True):
        if status != "open":
            continue
        risks.append(calculate_position_risk(position))

    def grouped(field_name: str) -> dict[str, float]:
        result: dict[str, float] = {}
        for risk in risks:
            key = getattr(risk, field_name)
            result[key] = round(result.get(key, 0.0) + risk.effective_open_risk_r, 4)
        return result

    market_maximum = config.MARKET_HEAT_LIMITS[market_regime]
    maximum = (
        market_maximum
        if maximum_heat_override_r is None
        else min(market_maximum, maximum_heat_override_r)
    )
    heat = round(sum(r.effective_open_risk_r for r in risks), 4)
    industry = grouped("industry")
    theme = grouped("theme")
    for name, value in industry.items():
        if value > config.MAX_INDUSTRY_EFFECTIVE_HEAT_R:
            warnings.append(f"industry heat limit exceeded: {name}")
    for name, value in theme.items():
        if value > config.MAX_THEME_EFFECTIVE_HEAT_R:
            warnings.append(f"theme heat limit exceeded: {name}")
    if heat > maximum:
        warnings.append("portfolio heat exceeds market limit")
    return PortfolioRisk(
        tuple(risks),
        heat,
        maximum,
        round(max(0.0, maximum - heat), 4),
        industry,
        grouped("sector"),
        theme,
        tuple(warnings),
    )


def calculate_drawdown_state(
    current_equity: float | None,
    high_water_mark_equity: float | None,
) -> DrawdownState:
    """Return the configured portfolio drawdown mode without optimistic fallback."""
    if (
        current_equity is None
        or high_water_mark_equity is None
        or not np.isfinite(current_equity)
        or not np.isfinite(high_water_mark_equity)
        or current_equity <= 0
        or high_water_mark_equity <= 0
        or current_equity > high_water_mark_equity
    ):
        return DrawdownState(
            "STOP_NEW_RISK",
            current_equity,
            high_water_mark_equity,
            None,
            None,
            0.0,
            False,
            False,
            "Missing / Invalid",
        )
    drawdown_dollars = float(high_water_mark_equity - current_equity)
    drawdown_r = drawdown_dollars / config.STANDARD_R_DOLLARS
    if drawdown_r >= config.DRAWDOWN_STOP_NEW_RISK_AT_R:
        mode = "STOP_NEW_RISK"
    elif drawdown_r >= config.DRAWDOWN_DEFENSIVE_AT_R:
        mode = "DEFENSIVE"
    elif drawdown_r >= config.DRAWDOWN_REDUCED_AT_R:
        mode = "REDUCED"
    else:
        mode = "NORMAL"
    return DrawdownState(
        mode,
        round(float(current_equity), 2),
        round(float(high_water_mark_equity), 2),
        round(drawdown_dollars, 2),
        round(drawdown_r, 4),
        float(config.DRAWDOWN_HEAT_LIMITS[mode]),
        mode == "NORMAL" or (mode == "REDUCED" and config.REDUCED_MODE_ALLOW_FULL),
        mode != "STOP_NEW_RISK",
        "Valid",
    )


def load_drawdown_state(path: str) -> DrawdownState:
    source = Path(path)
    if not source.exists():
        return calculate_drawdown_state(None, None)
    try:
        frame = pd.read_csv(source)
        if frame.empty or not {"current_equity", "high_water_mark_equity"}.issubset(
            frame
        ):
            return calculate_drawdown_state(None, None)
        latest = frame.iloc[-1]
        return calculate_drawdown_state(
            float(latest["current_equity"]), float(latest["high_water_mark_equity"])
        )
    except (
        OSError,
        ValueError,
        TypeError,
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
    ):
        return calculate_drawdown_state(None, None)


def entry_timing_for_candidate(row: dict[str, object]) -> str:
    entry = pd.to_numeric(row.get("Planned Entry"), errors="coerce")
    stop = pd.to_numeric(row.get("Initial Stop"), errors="coerce")
    target = pd.to_numeric(row.get("Realistic Target"), errors="coerce")
    if pd.isna(entry) or pd.isna(stop) or pd.isna(target):
        return "NOT AVAILABLE"
    extension = str(row.get("Extension Status", ""))
    if extension == "Overextended":
        return "OVEREXTENDED"
    if extension == "Extended":
        return "LATE"
    pivot = pd.to_numeric(row.get("Distance From Pivot %"), errors="coerce")
    support = pd.to_numeric(row.get("Nearest Support Distance ATR"), errors="coerce")
    if (
        pd.notna(support)
        and float(support) <= 1.0
        and (pd.isna(pivot) or abs(float(pivot)) <= 5)
    ):
        return "OPTIMAL"
    if pd.notna(pivot) and float(pivot) < 0:
        return "EARLY"
    return "LATE"


def assess_setup_integrity(row: dict[str, object]) -> SetupIntegrityResult:
    """Classify observable setup quality without using score or secondary breadth.

    A FAIL is still potentially interesting, so it becomes WATCH unless another
    independent hard gate requires NO TRADE.  This keeps setup quality separate
    from industry and sister-stock confirmation.
    """
    category = str(row.get("Category", ""))
    tightness = str(row.get("Tightness Label", ""))
    vcp = str(row.get("VCP Label", ""))
    pullback = str(row.get("Pullback Quality", ""))
    extension = str(row.get("Extension Status", ""))
    confidence = str(row.get("Trade Plan Confidence", ""))

    weaknesses: list[str] = []
    if tightness == "Loose":
        weaknesses.append("loose price action")
    if vcp == "Poor VCP":
        weaknesses.append("poor volatility contraction")
    if pullback.startswith(("C", "D")):
        weaknesses.append("weak pullback structure")
    if category == "Developing Base Candidates":
        weaknesses.append("developing base is not a completed setup")
    if extension == "Moderately Extended":
        weaknesses.append("moderately extended entry")
    if confidence == "Medium":
        weaknesses.append("medium-confidence trade plan")

    fail = (
        confidence == "Low"
        or extension in {"Extended", "Overextended"}
        or (tightness == "Loose" and category == "Developing Base Candidates")
        or (tightness == "Loose" and vcp == "Poor VCP")
        or (
            category == "Developing Base Candidates" and pullback.startswith(("C", "D"))
        )
    )
    if fail:
        if confidence == "Low":
            weaknesses.append("trade-plan confidence is insufficient")
        return SetupIntegrityResult("FAIL", tuple(dict.fromkeys(weaknesses)))
    if weaknesses:
        return SetupIntegrityResult("MARGINAL", tuple(dict.fromkeys(weaknesses)))
    return SetupIntegrityResult("PASS", ())


def size_authorised_candidate(
    row: dict[str, object],
    authorised_state: str,
) -> TradeSizingDecision:
    """Size an already-authorised state and never promote a non-actionable one."""
    integrity = str(row.get("Setup Integrity", "UNKNOWN"))
    if authorised_state not in {"FULL", "HALF"}:
        return TradeSizingDecision(
            authorised_state
            if authorised_state in {"WATCH", "NO TRADE"}
            else "NO TRADE",
            0.0,
            0.0,
            0,
            (),
            (),
            integrity,
            False,
        )
    entry = pd.to_numeric(row.get("Planned Entry"), errors="coerce")
    stop = pd.to_numeric(row.get("Initial Stop"), errors="coerce")
    if pd.isna(entry) or pd.isna(stop) or float(stop) >= float(entry):
        return TradeSizingDecision(
            "NO TRADE",
            0.0,
            0.0,
            0,
            ("invalid structural stop",),
            (),
            integrity,
            False,
        )
    risk_r = config.FULL_RISK_R if authorised_state == "FULL" else config.HALF_RISK_R
    risk_dollars = risk_r * config.STANDARD_R_DOLLARS
    shares = math.floor(risk_dollars / float(entry - stop))
    if shares <= 0:
        return TradeSizingDecision(
            "NO TRADE",
            0.0,
            0.0,
            0,
            ("risk budget cannot buy one share",),
            (),
            integrity,
            False,
        )
    return TradeSizingDecision(
        authorised_state,
        risk_r,
        round(risk_dollars, 2),
        shares,
        (),
        (),
        integrity,
        True,
    )


def canonical_candidate_decision(
    row: dict[str, object],
    market_regime: str,
    drawdown: DrawdownState,
    portfolio: PortfolioRisk | None,
    open_position_count: int | None,
    new_positions_today: int = 0,
    portfolio_new_risk_allowed: bool | None = None,
    market_new_risk_allowed: bool | None = None,
    remaining_new_risk_r: float | None = None,
) -> TradeSizingDecision:
    """Authoritative FULL/HALF/WATCH/NO TRADE decision and sizing pipeline."""
    hard: list[str] = []
    secondary: list[str] = []
    integrity = assess_setup_integrity(row)
    row = {**row, "Setup Integrity": integrity.state}
    recent = pd.to_numeric(row.get("Recent RS Score"), errors="coerce")
    entry = pd.to_numeric(row.get("Planned Entry"), errors="coerce")
    stop = pd.to_numeric(row.get("Initial Stop"), errors="coerce")
    target = pd.to_numeric(row.get("Realistic Target"), errors="coerce")
    rr = calculate_reward_risk(entry, stop, target)
    timing = str(row.get("Entry Timing") or entry_timing_for_candidate(row))
    trend = str(row.get("RS Trend", ""))
    price = pd.to_numeric(row.get("Price"), errors="coerce")
    average_volume = pd.to_numeric(row.get("Avg Volume"), errors="coerce")
    if pd.isna(recent):
        hard.append("Recent RS missing")
    elif float(recent) < config.MIN_EARLY_LEADER_RS_SCORE:
        hard.append("Recent RS is below the minimum primary-edge floor")
    elif float(recent) < config.MIN_RECENT_RS_ALLOWED and trend not in {
        "Improving",
        "Emerging Leader",
    }:
        hard.append("Recent RS is neither strong nor clearly improving")
    elif trend not in {"Improving", "Emerging Leader", "Stable Leader", "Stable"}:
        hard.append("RS trend is not acceptable for an actionable setup")
    if pd.isna(entry):
        hard.append("valid entry missing")
    if pd.isna(stop) or (pd.notna(entry) and float(stop) >= float(entry)):
        hard.append("invalid structural stop")
    if (
        pd.isna(target)
        or str(row.get("Realistic Target Source", "")) == "model 2R feasibility target"
    ):
        hard.append("model 2R target requires chart-confirmed resistance")
    if not rr.valid:
        hard.append("actual structural R/R below 2 or unavailable")
    if timing == "OVEREXTENDED" or str(row.get("Extension Status")) == "Overextended":
        hard.append("overextended")
    if "Price" in row and (pd.isna(price) or float(price) < config.MIN_PRICE):
        hard.append("price liquidity gate failed")
    if "Avg Volume" in row and (
        pd.isna(average_volume) or float(average_volume) < config.MIN_AVG_VOLUME
    ):
        hard.append("average-volume liquidity gate failed")
    freshness = str(row.get("Price Freshness Status", "")).strip().upper()
    if freshness and freshness != "CURRENT":
        hard.append("stale or incomplete critical price data")
    raw_price_warning = row.get("Price Data Warning")
    if (
        raw_price_warning is not None
        and not pd.isna(raw_price_warning)
        and str(raw_price_warning).strip()
    ):
        hard.append("critical price/data warning")
    if market_regime in {"Caution", "Risk Off"}:
        hard.append(f"{market_regime} market does not permit new risk")
    if not drawdown.new_risk_allowed:
        hard.append("drawdown stop-new-risk threshold reached")
    if market_new_risk_allowed is not True:
        hard.append("market status prohibits new risk")
    if portfolio_new_risk_allowed is not True:
        hard.append("portfolio status prohibits new risk")
    if (
        remaining_new_risk_r is not None
        and remaining_new_risk_r < config.HALF_RISK_R - 1e-9
    ):
        hard.append("daily new-risk limit reached")
    if (
        drawdown.mode == "DEFENSIVE"
        and new_positions_today >= config.DEFENSIVE_MAX_NEW_HALF_POSITIONS
    ):
        hard.append("Defensive drawdown-mode new-position limit reached")
    if portfolio is None or open_position_count is None:
        hard.append("portfolio risk unavailable")
    else:
        if open_position_count >= config.MAX_OPEN_POSITIONS:
            hard.append("maximum open-position count reached")
        if portfolio.remaining_heat_r < config.HALF_RISK_R:
            hard.append("portfolio heat exhausted")
        industry = str(row.get("Industry", ""))
        theme = str(row.get("Theme", f"Industry: {industry}"))
        if (
            portfolio.industry_heat.get(industry, 0.0) + config.HALF_RISK_R
            > config.MAX_INDUSTRY_EFFECTIVE_HEAT_R
        ):
            hard.append("industry heat limit exceeded")
        if (
            portfolio.theme_heat.get(theme, 0.0) + config.HALF_RISK_R
            > config.MAX_THEME_EFFECTIVE_HEAT_R
        ):
            hard.append("theme heat limit exceeded")
    if hard:
        return TradeSizingDecision(
            "NO TRADE",
            0.0,
            0.0,
            0,
            tuple(dict.fromkeys(hard)),
            (),
            integrity.state,
            False,
        )
    if integrity.state == "FAIL":
        return TradeSizingDecision(
            "WATCH",
            0.0,
            0.0,
            0,
            tuple(f"setup integrity: {reason}" for reason in integrity.reasons),
            (),
            integrity.state,
            False,
        )
    if integrity.state == "MARGINAL":
        secondary.append("setup integrity is marginal")
    if not bool(row.get("Industry Qualified")):
        secondary.append("industry leadership incomplete")
    if not bool(row.get("Sister Confirmation")):
        secondary.append("sister-stock confirmation incomplete")
    volume_ratio = pd.to_numeric(row.get("Volume Ratio"), errors="coerce")
    if (
        pd.isna(volume_ratio)
        or float(volume_ratio) < config.MIN_CONFIRMATION_VOLUME_RATIO
    ):
        secondary.append("volume confirmation incomplete")
    if pd.notna(recent) and float(recent) < config.MIN_RECENT_RS_ALLOWED:
        secondary.append("Recent RS below full-risk threshold")
    if timing == "LATE":
        secondary.append("late entry timing")
    industry = str(row.get("Industry", ""))
    theme = str(row.get("Theme", f"Industry: {industry}"))
    full_capacity = bool(
        portfolio is not None
        and portfolio.remaining_heat_r >= config.FULL_RISK_R
        and (
            remaining_new_risk_r is None
            or remaining_new_risk_r >= config.FULL_RISK_R - 1e-9
        )
        and portfolio.industry_heat.get(industry, 0.0) + config.FULL_RISK_R
        <= config.MAX_INDUSTRY_EFFECTIVE_HEAT_R
        and portfolio.theme_heat.get(theme, 0.0) + config.FULL_RISK_R
        <= config.MAX_THEME_EFFECTIVE_HEAT_R
    )
    full = (
        not secondary
        and integrity.state == "PASS"
        and drawdown.full_allowed
        and market_regime in {"Strong", "Constructive"}
        and timing in {"EARLY", "OPTIMAL"}
        and str(row.get("RS Trend"))
        in {"Emerging Leader", "Improving", "Stable Leader"}
        and full_capacity
    )
    state = "FULL" if full else "HALF"
    sized = size_authorised_candidate(row, state)
    return TradeSizingDecision(
        sized.state,
        sized.maximum_risk_r,
        sized.maximum_risk_dollars,
        sized.maximum_shares,
        sized.reasons,
        tuple(dict.fromkeys(secondary)),
        integrity.state,
        sized.actionable,
    )


def size_trade_candidate(
    row: dict[str, object],
    market_regime: str,
    drawdown: DrawdownState,
    portfolio: PortfolioRisk | None,
    open_position_count: int | None,
    new_positions_today: int = 0,
) -> TradeSizingDecision:
    """Backward-compatible alias for the single canonical decision engine."""
    return canonical_candidate_decision(
        row,
        market_regime,
        drawdown,
        portfolio,
        open_position_count,
        new_positions_today,
        portfolio_new_risk_allowed=bool(
            portfolio is not None
            and open_position_count is not None
            and open_position_count < config.MAX_OPEN_POSITIONS
            and portfolio.remaining_heat_r >= config.HALF_RISK_R
            and not portfolio.warnings
        ),
        market_new_risk_allowed=market_regime in {"Strong", "Constructive"},
    )


def size_additional_tranche(
    row: dict[str, object],
    market_regime: str,
    drawdown: DrawdownState,
    portfolio: PortfolioRisk | None,
    open_position_count: int | None,
    new_positions_today: int = 0,
) -> TradeSizingDecision:
    """Require an explicitly new plan; never auto-upgrade an existing HALF."""
    if not bool(row.get("New Tranche Plan")):
        return TradeSizingDecision(
            "NO TRADE",
            0.0,
            0.0,
            0,
            ("new tranche requires a new valid trade plan",),
            (),
        )
    return size_trade_candidate(
        row,
        market_regime,
        drawdown,
        portfolio,
        open_position_count,
        new_positions_today,
    )


def load_portfolio_status(
    path: str,
    market_regime: str,
    market_snapshot: pd.DataFrame | None = None,
    as_of: datetime | None = None,
    maximum_heat_override_r: float | None = None,
) -> dict[str, object]:
    """Load positions, enriching non-trade fields from the current market snapshot.

    The user only needs to maintain the trade facts (ticker, entry details, stops,
    shares and status).  Prices and classifications are derived explicitly; if a
    required snapshot value is unavailable the portfolio remains invalid rather
    than being made to look like zero risk.
    """
    source = Path(path).exists()
    if not source:
        return {
            "data_status": "Missing",
            "portfolio": None,
            "open_position_count": None,
            "portfolio_new_risk_allowed": False,
            "new_initial_risk_r_today": None,
            "new_position_count_today": None,
        }
    try:
        frame = pd.read_csv(path)
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return {
            "data_status": "Invalid",
            "portfolio": None,
            "open_position_count": None,
            "portfolio_new_risk_allowed": False,
            "new_initial_risk_r_today": None,
            "new_position_count_today": None,
        }
    if "status" not in frame.columns:
        return {
            "data_status": "Invalid: required status column is missing",
            "portfolio": None,
            "open_position_count": None,
            "portfolio_new_risk_allowed": False,
            "new_initial_risk_r_today": None,
            "new_position_count_today": None,
        }
    normalised_status = frame["status"].map(normalise_position_status)
    if normalised_status.eq("").any():
        return {
            "data_status": "Invalid: position status is missing",
            "portfolio": None,
            "open_position_count": None,
            "portfolio_new_risk_allowed": False,
            "new_initial_risk_r_today": None,
            "new_position_count_today": None,
        }
    unsupported_statuses = sorted(set(normalised_status) - SUPPORTED_POSITION_STATUSES)
    if unsupported_statuses:
        return {
            "data_status": (
                "Invalid: unsupported position status: "
                + ", ".join(unsupported_statuses)
            ),
            "portfolio": None,
            "open_position_count": None,
            "portfolio_new_risk_allowed": False,
            "new_initial_risk_r_today": None,
            "new_position_count_today": None,
        }
    reference = as_of or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    market_date = reference.astimezone(ZoneInfo("America/New_York")).date()

    def entry_market_date(value: object):
        entry_timestamp = pd.Timestamp(value)
        if pd.isna(entry_timestamp):
            raise ValueError("entry_date unavailable")
        if entry_timestamp.tzinfo is not None:
            entry_timestamp = entry_timestamp.tz_convert("America/New_York")
        return entry_timestamp.date()

    try:
        new_initial_risk_by_ticker_today: dict[str, float] = {}
        for row in frame.to_dict("records"):
            if entry_market_date(row.get("entry_date")) != market_date:
                continue
            ticker = str(row.get("ticker", "")).strip().upper()
            entry = float(row.get("entry_price"))
            initial_stop = float(row.get("initial_stop"))
            shares = float(row.get("shares"))
            raw_standard_r = row.get("standard_r_dollars_at_entry")
            standard_r = (
                config.STANDARD_R_DOLLARS
                if raw_standard_r is None or pd.isna(raw_standard_r)
                else float(raw_standard_r)
            )
            risk_values = (entry, initial_stop, shares, standard_r)
            if (
                not ticker
                or not all(np.isfinite(value) for value in risk_values)
                or entry <= initial_stop
                or shares <= 0
                or standard_r <= 0
            ):
                raise ValueError(
                    f"{ticker or 'position'}: invalid same-day initial-risk facts"
                )
            initial_r = (entry - initial_stop) * shares / standard_r
            new_initial_risk_by_ticker_today[ticker] = round(
                new_initial_risk_by_ticker_today.get(ticker, 0.0) + initial_r, 4
            )
        new_initial_risk_r_today = round(
            sum(new_initial_risk_by_ticker_today.values()), 4
        )
    except (TypeError, ValueError, OverflowError) as exc:
        return {
            "data_status": f"Invalid / Stale: {exc}",
            "portfolio": None,
            "open_position_count": None,
            "portfolio_new_risk_allowed": False,
            "new_initial_risk_r_today": None,
            "new_initial_risk_by_ticker_today": None,
            "new_position_count_today": None,
        }
    open_rows = frame[normalised_status.eq("open")]
    if open_rows.empty:
        portfolio = calculate_portfolio_risk([], market_regime, maximum_heat_override_r)
        return {
            "data_status": "No open positions",
            "portfolio": portfolio,
            "open_position_count": 0,
            "portfolio_new_risk_allowed": portfolio.remaining_heat_r
            >= config.HALF_RISK_R,
            "new_initial_risk_r_today": new_initial_risk_r_today,
            "new_initial_risk_by_ticker_today": new_initial_risk_by_ticker_today,
            "new_position_count_today": len(new_initial_risk_by_ticker_today),
        }
    positions: list[Position] = []
    auto_filled: set[str] = set()

    def missing(value: object) -> bool:
        return value is None or pd.isna(value) or not str(value).strip()

    snapshot_by_ticker: dict[str, dict[str, object]] = {}
    if market_snapshot is not None and not market_snapshot.empty:
        for snapshot_row in market_snapshot.to_dict("records"):
            ticker = str(snapshot_row.get("Ticker", "")).strip().upper()
            if ticker:
                snapshot_by_ticker[ticker] = snapshot_row
    timestamp = reference.astimezone(timezone.utc).isoformat()
    try:
        for row in open_rows.to_dict("records"):
            ticker = str(row.get("ticker", "")).strip().upper()
            snapshot = snapshot_by_ticker.get(ticker, {})
            values = {name: row.get(name) for name in Position.__dataclass_fields__}
            values["ticker"] = ticker
            derived = {
                "current_price": snapshot.get("Price"),
                "industry": snapshot.get("Industry"),
                "sector": snapshot.get("Sector"),
                "last_updated": timestamp,
                "standard_r_dollars_at_entry": config.STANDARD_R_DOLLARS,
            }
            for name, value in derived.items():
                if missing(values.get(name)):
                    if missing(value):
                        raise ValueError(f"{ticker or 'position'}: {name} unavailable")
                    values[name] = value
                    auto_filled.add(name)
            if missing(values.get("theme")):
                values["theme"] = f"Industry: {values['industry']}"
                auto_filled.add("theme")
            if missing(values.get("setup_type")):
                values["setup_type"] = "Unspecified"
                auto_filled.add("setup_type")
            for numeric in (
                "entry_price",
                "initial_stop",
                "current_stop",
                "current_price",
                "shares",
                "standard_r_dollars_at_entry",
                "previous_stop",
            ):
                if not missing(values.get(numeric)):
                    values[numeric] = float(values[numeric])
                elif numeric == "previous_stop":
                    values[numeric] = None
            positions.append(Position(**values))
        portfolio = calculate_portfolio_risk(
            positions, market_regime, maximum_heat_override_r
        )
    except (TypeError, ValueError) as exc:
        return {
            "data_status": f"Invalid / Stale: {exc}",
            "portfolio": None,
            "open_position_count": len(open_rows),
            "portfolio_new_risk_allowed": False,
            "new_initial_risk_r_today": None,
            "new_initial_risk_by_ticker_today": None,
            "new_position_count_today": None,
        }
    allowed = (
        portfolio.remaining_heat_r >= config.HALF_RISK_R
        and len(positions) < config.MAX_OPEN_POSITIONS
        and not portfolio.warnings
    )
    return {
        "data_status": "Valid (auto-enriched)" if auto_filled else "Valid",
        "portfolio": portfolio,
        "open_position_count": len(positions),
        "portfolio_new_risk_allowed": allowed,
        "new_initial_risk_r_today": new_initial_risk_r_today,
        "new_initial_risk_by_ticker_today": new_initial_risk_by_ticker_today,
        "new_position_count_today": len(new_initial_risk_by_ticker_today),
        "auto_filled_fields": sorted(auto_filled),
    }


def market_regime_from_metrics(
    metrics: dict[str, float | bool | None], previous_regime: str | None = None
) -> MarketRegime:
    required = (
        "spy_above_20ema",
        "spy_above_50ma",
        "qqq_above_20ema",
        "qqq_above_50ma",
        "breadth_above_20ema",
        "breadth_above_50ma",
        "ema20_slope_positive",
        "ema50_slope_positive",
        "breakout_success_rate",
        "breakout_failure_rate",
        "breakout_sample_size",
        "leadership_contribution",
        "leadership_sample_size",
        "volatility_contribution",
    )
    missing = [
        name
        for name in required
        if metrics.get(name) is None or pd.isna(metrics.get(name))
    ]
    positives: list[str] = []
    negatives: list[str] = []
    components = {
        "SPY trend": 0.0,
        "QQQ trend": 0.0,
        "Breadth": 0.0,
        "Breakout quality": 0.0,
        "Leadership": 0.0,
        "Volatility": 0.0,
    }
    score = 50.0
    for name, weight in (
        ("spy_above_20ema", 8),
        ("spy_above_50ma", 10),
        ("qqq_above_20ema", 8),
        ("qqq_above_50ma", 10),
        ("ema20_slope_positive", 6),
        ("ema50_slope_positive", 8),
    ):
        if metrics.get(name) is True:
            score += weight
            components[
                "SPY trend"
                if name.startswith("spy") or name.startswith("ema")
                else "QQQ trend"
            ] += weight
            positives.append(name)
        elif metrics.get(name) is False:
            score -= weight
            components[
                "SPY trend"
                if name.startswith("spy") or name.startswith("ema")
                else "QQQ trend"
            ] -= weight
            negative_labels = {
                "spy_above_20ema": "SPY below 20EMA",
                "spy_above_50ma": "SPY below 50MA",
                "qqq_above_20ema": "QQQ below 20EMA",
                "qqq_above_50ma": "QQQ below 50MA",
                "ema20_slope_positive": "20EMA slope not positive",
                "ema50_slope_positive": "50MA slope not positive",
            }
            negatives.append(negative_labels[name])
    breadth20 = metrics.get("breadth_above_20ema")
    breadth50 = metrics.get("breadth_above_50ma")
    if breadth20 is not None and not pd.isna(breadth20):
        contribution = (float(breadth20) - 50) * 0.25
        score += contribution
        components["Breadth"] += contribution
    if breadth50 is not None and not pd.isna(breadth50):
        contribution = (float(breadth50) - 50) * 0.20
        score += contribution
        components["Breadth"] += contribution
    breakout_contribution = min(
        8.0, float(metrics.get("breakout_success_rate") or 0) * 0.08
    ) - min(10.0, float(metrics.get("breakout_failure_rate") or 0) * 0.10)
    score += breakout_contribution
    components["Breakout quality"] = breakout_contribution
    leadership = float(metrics.get("leadership_contribution") or 0)
    volatility = float(metrics.get("volatility_contribution") or 0)
    score += leadership + volatility
    components["Leadership"] = leadership
    components["Volatility"] = volatility
    emergency = bool(metrics.get("emergency_deterioration"))
    if emergency:
        regime = "Risk Off"
        score = min(score, 19.0)
        negatives.append("emergency deterioration")
    elif score >= 75:
        regime = "Strong"
    elif score >= 62:
        regime = "Constructive"
    elif score >= 45:
        regime = "Neutral"
    elif score >= 25:
        regime = "Caution"
    else:
        regime = "Risk Off"
    order = ["Risk Off", "Caution", "Neutral", "Constructive", "Strong"]
    if previous_regime in order and not emergency:
        distance = abs(order.index(regime) - order.index(previous_regime))
        confirmation_days = int(metrics.get("confirmation_days") or 1)
        if distance == 1 and confirmation_days < 2:
            regime = previous_regime
    complete = not missing
    if missing:
        negatives.append("incomplete market-factor data")
    breakout_sample_size = int(metrics.get("breakout_sample_size") or 0)
    leadership_sample_size = int(metrics.get("leadership_sample_size") or 0)
    thin_confirmation = breakout_sample_size < 5 or leadership_sample_size < 5
    if complete and breakout_sample_size < 5:
        negatives.append("breakout sample is thin")
    if complete and leadership_sample_size < 5:
        negatives.append("leadership sample is thin")
    maximum = config.MARKET_HEAT_LIMITS[regime]
    return MarketRegime(
        round(max(0, min(100, score)), 1),
        regime,
        maximum,
        tuple(positives),
        tuple(negatives),
        f"{regime}: score {round(score, 1)}; "
        + (", ".join(negatives) if negatives else "supportive factors dominate"),
        complete,
        "Low" if not complete else "Medium" if thin_confirmation else "High",
        complete and regime not in {"Caution", "Risk Off"},
        {name: round(value, 2) for name, value in components.items()},
    )


def calculate_recent_rs_frame(
    histories: dict[str, pd.DataFrame],
    spy: pd.DataFrame,
    as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Calculate 5/10/20/30-day absolute and SPY-relative returns without future rows."""
    rows = []
    spy_close = (
        spy.loc[:as_of, "Close"].dropna()
        if as_of is not None
        else spy["Close"].dropna()
    )
    for ticker, history in histories.items():
        close = (
            history.loc[:as_of, "Close"].dropna()
            if as_of is not None
            else history["Close"].dropna()
        )
        row: dict[str, object] = {"Ticker": ticker}
        complete = True
        for days in config.RECENT_RS_PERIODS:
            if len(close) <= days or len(spy_close) <= days:
                absolute = relative = np.nan
                complete = False
            else:
                absolute = ((close.iloc[-1] / close.iloc[-1 - days]) - 1) * 100
                spy_return = (
                    (spy_close.iloc[-1] / spy_close.iloc[-1 - days]) - 1
                ) * 100
                relative = absolute - spy_return
            row[f"Return {days}D"] = absolute
            row[f"Relative Return {days}D"] = relative
        aligned = pd.concat(
            [close.rename("stock"), spy_close.rename("spy")], axis=1, join="inner"
        ).dropna()
        daily = aligned.pct_change().tail(30) * 100
        pullback_days = daily[daily["spy"] < 0]
        row["Pullback Day Relative Behaviour"] = (
            float((pullback_days["stock"] - pullback_days["spy"]).mean())
            if not pullback_days.empty
            else np.nan
        )
        row["Recent RS Complete"] = complete
        rows.append(row)
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    score = pd.Series(0.0, index=frame.index)
    for label, weight in config.RECENT_RS_DECISION_WEIGHTS.items():
        score += (
            frame[f"Relative Return {label}"].rank(pct=True, method="average")
            * 100
            * weight
        )
    frame["Recent RS Score"] = score.where(frame["Recent RS Complete"])
    frame["Recent RS Trend Delta"] = (
        frame["Relative Return 5D"] - frame["Relative Return 20D"] / 4
    )
    frame["RS Momentum Acceleration"] = frame["Recent RS Trend Delta"]
    frame["Recent RS Trend"] = np.select(
        [
            (frame["Recent RS Score"] >= 80) & (frame["Recent RS Trend Delta"] > 0),
            frame["Recent RS Trend Delta"] > 0,
            frame["Recent RS Trend Delta"] < 0,
        ],
        ["Emerging Leader", "Improving", "Weakening"],
        default="Stable",
    )
    frame.loc[~frame["Recent RS Complete"], "Recent RS Trend"] = "DATA_INCOMPLETE"
    return frame


def calculate_reward_risk(
    entry: float | None,
    stop: float | None,
    target: float | None,
    distance_from_pivot_pct: float | None = None,
    support_distance_atr: float | None = None,
) -> RewardRisk:
    if entry is None or pd.isna(entry):
        return RewardRisk(None, "Not Available", False, "planned entry missing")
    if stop is None or pd.isna(stop):
        return RewardRisk(None, "Not Available", False, "structural stop missing")
    if target is None or pd.isna(target):
        return RewardRisk(None, "Not Available", False, "realistic target missing")
    if stop >= entry:
        return RewardRisk(
            None, "Invalid", False, "initial stop must be below planned entry"
        )
    if target <= entry:
        return RewardRisk(None, "Invalid", False, "target must be above planned entry")
    ratio = round(float((target - entry) / (entry - stop)), 2)
    if ratio < config.MIN_REWARD_RISK_ALLOWED:
        label = "Below Minimum"
    elif (
        ratio >= 3
        and (distance_from_pivot_pct is None or abs(distance_from_pivot_pct) <= 5)
        and (support_distance_atr is None or support_distance_atr <= 1.5)
    ):
        label = "Excellent R/R"
    else:
        label = "Valid R/R"
    return RewardRisk(ratio, label, ratio >= config.MIN_REWARD_RISK_ALLOWED, "")


def construct_trade_plan(
    history: pd.DataFrame,
    setup: str,
    as_of: pd.Timestamp | None = None,
) -> TradePlan:
    """Build a provisional plan from observable structure only."""
    frame = history.loc[:as_of].copy() if as_of is not None else history.copy()
    required = {"High", "Low", "Close"}
    if len(frame) < 20 or not required.issubset(frame.columns):
        return TradePlan(
            None, "", None, "", None, "", None, "Low", ("insufficient price structure",)
        )
    frame = frame.dropna(subset=list(required))
    if len(frame) < 20:
        return TradePlan(
            None, "", None, "", None, "", None, "Low", ("insufficient price structure",)
        )
    latest = frame.iloc[-1]
    previous = frame.iloc[-2]
    atr = float(latest.get("ATR20", np.nan))
    if not np.isfinite(atr) or atr <= 0:
        true_range = pd.concat(
            [
                frame["High"] - frame["Low"],
                (frame["High"] - frame["Close"].shift()).abs(),
                (frame["Low"] - frame["Close"].shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = float(true_range.tail(20).mean())
    buffer = config.TRADE_PLAN_ENTRY_BUFFER_PCT / 100
    atr_buffer = config.TRADE_PLAN_STOP_ATR_BUFFER * atr
    label = setup.lower()
    if "breakout" in label:
        pivot = float(latest.get("PIVOT_PRICE", frame["High"].iloc[-21:-1].max()))
        entry, entry_source = pivot * (1 + buffer), "pivot plus configured buffer"
        stop, stop_source = (
            float(frame["Low"].tail(10).min()) - atr_buffer,
            "10-day base low plus ATR buffer",
        )
    elif "tight" in label:
        entry, entry_source = (
            float(frame["High"].tail(10).max()) * (1 + buffer),
            "10-day consolidation high plus buffer",
        )
        stop, stop_source = (
            float(frame["Low"].tail(10).min()) - atr_buffer,
            "10-day consolidation low plus ATR buffer",
        )
    elif "pullback" in label:
        entry, entry_source = (
            float(previous["High"]) * (1 + buffer),
            "prior-day high confirmation",
        )
        stop, stop_source = (
            float(frame["Low"].tail(5).min()) - atr_buffer,
            "5-day pullback low plus ATR buffer",
        )
    else:
        return TradePlan(
            None,
            "",
            None,
            "",
            None,
            "",
            None,
            "Low",
            ("unsupported or ambiguous setup",),
        )
    risk = entry - stop
    reasons: list[str] = []
    if risk <= 0:
        reasons.append("structural stop is not below entry")
    risk_atr = risk / atr if atr else np.inf
    if risk_atr < config.TRADE_PLAN_MIN_RISK_ATR:
        reasons.append("stop width is artificially narrow")
    if risk_atr > config.TRADE_PLAN_MAX_RISK_ATR:
        reasons.append("structural stop is too wide")
    resistance = float(frame["High"].tail(252).max())
    model_target = entry + config.MIN_REWARD_RISK_ALLOWED * risk
    if resistance > entry and resistance >= model_target:
        target, target_source = resistance, "observed prior-high resistance"
    else:
        target, target_source = model_target, "model 2R feasibility target"
    rr = calculate_reward_risk(entry, stop, target)
    if not rr.valid:
        reasons.append(rr.reason or "R/R below minimum")
    confidence = (
        "Low" if reasons else ("High" if "resistance" in target_source else "Medium")
    )
    if reasons:
        return TradePlan(
            None,
            entry_source,
            None,
            stop_source,
            None,
            target_source,
            None,
            confidence,
            tuple(reasons),
        )
    rounded_entry = round(entry, 2)
    rounded_stop = round(stop, 2)
    rounded_target = round(target, 2)
    if target_source == "model 2R feasibility target":
        minimum_target = rounded_entry + config.MIN_REWARD_RISK_ALLOWED * (
            rounded_entry - rounded_stop
        )
        rounded_target = math.ceil(minimum_target * 100) / 100
    rounded_rr = calculate_reward_risk(rounded_entry, rounded_stop, rounded_target)
    return TradePlan(
        rounded_entry,
        entry_source,
        rounded_stop,
        stop_source,
        rounded_target,
        target_source,
        rounded_rr.ratio,
        confidence,
        (),
    )


def score_candidate(row: dict[str, object]) -> ScoreBreakdown:
    recent_value = pd.to_numeric(row.get("Recent RS Score"), errors="coerce")
    recent = float(recent_value) if pd.notna(recent_value) else float("nan")
    industry = (
        100.0
        if row.get("Industry Qualified") and row.get("Sister Confirmation")
        else 55.0
        if row.get("Industry Qualified")
        else 0.0
    )
    setup = float(
        row.get("Setup Quality Score")
        or max(0, 100 - float(row.get("10 Day Range %") or 100))
    )
    volume = float(
        row.get("Volume Quality Score")
        or min(100, float(row.get("Volume Ratio") or 0) * 60)
    )
    entry = float(
        row.get("Entry Stop Quality Score")
        or (
            80
            if str(row.get("Trade Plan Confidence")) == "High"
            else 60
            if str(row.get("Trade Plan Confidence")) == "Medium"
            else 0
        )
    )
    trend = float(row.get("Intermediate Trend Score") or row.get("RS Score") or 0)
    components = [
        0.30 * recent,
        0.20 * industry,
        0.20 * setup,
        0.15 * volume,
        0.10 * entry,
        0.05 * trend,
    ]
    penalties: dict[str, float] = {}
    if str(row.get("Tightness Label")) == "Loose":
        penalties["Loose action"] = 8.0
    if str(row.get("VCP Label")) == "Poor VCP":
        penalties["Poor VCP"] = 10.0
    if str(row.get("Extension Status")) in {"Extended", "Overextended"}:
        penalties["Extension"] = 15.0
    warning = row.get("Price Data Warning")
    if warning is not None and not pd.isna(warning) and str(warning).strip():
        penalties["Price warning"] = 25.0
    base = sum(components)
    total = sum(penalties.values())
    final_score = (
        float("nan") if pd.isna(recent) else round(max(0, min(100, base - total)), 2)
    )
    return ScoreBreakdown(
        recent_rs_component=round(components[0], 2),
        industry_sister_component=round(components[1], 2),
        setup_quality_component=round(components[2], 2),
        volume_component=round(components[3], 2),
        entry_stop_component=round(components[4], 2),
        intermediate_trend_component=round(components[5], 2),
        base_score=round(base, 2),
        penalties=penalties,
        total_penalty=round(total, 2),
        final_score=final_score,
    )


def qualify_industries(
    members: pd.DataFrame,
    qualifying_setups: pd.DataFrame,
    metadata_coverage: float = 1.0,
) -> pd.DataFrame:
    """Apply absolute momentum/breadth gates; raw member count never adds score."""
    columns = [
        "Industry",
        "Sector",
        "Eligible Members",
        "Raw Candidate Count",
        "Qualifying Setup Count",
        "Absolute Return 5D",
        "Absolute Return 10D",
        "Absolute Return 20D",
        "Relative Return 10D",
        "Relative Return 20D",
        "Above 10EMA %",
        "Above 20EMA %",
        "Above 50MA %",
        "Near 20D High %",
        "Near 52W High %",
        "Valid Breakout Count",
        "Breakout Success Rate",
        "Breakout Failure Rate",
        "High Volume Breakdown Count",
        "Average Recent RS",
        "Median Recent RS",
        "Breadth Score",
        "Momentum Score",
        "Setup Quality Score",
        "Industry Composite Score",
        "Industry Qualified",
        "Industry Classification",
        "Breadth Sample Quality",
        "Above 20EMA Breadth",
        "Above 50MA Breadth",
        "Near 20D High Breadth",
        "Data Complete",
        "Metadata Coverage %",
        "Industry Rank",
        "Exclusion Reasons",
    ]
    if members.empty:
        return pd.DataFrame(columns=columns)
    qualifying_tickers = set(
        qualifying_setups.get("Ticker", pd.Series(dtype=str)).astype(str)
    )
    rows = []
    for industry, group in members.groupby("Industry"):
        sector = (
            group["Sector"].mode().iloc[0]
            if "Sector" in group and not group["Sector"].mode().empty
            else "Unknown"
        )
        valid_breakouts = int(
            group.get("Valid Breakout", pd.Series(False, index=group.index))
            .fillna(False)
            .sum()
        )
        failed_breakouts = int(
            group.get("Failed Breakout", pd.Series(False, index=group.index))
            .fillna(False)
            .sum()
        )
        breakout_sample = valid_breakouts + failed_breakouts
        failure_rate = (
            100 * failed_breakouts / breakout_sample if breakout_sample else 0.0
        )
        success_rate = (
            100 * valid_breakouts / breakout_sample if breakout_sample else 0.0
        )
        eligible = len(group)
        raw_candidates = int(
            group.get("Is Candidate", pd.Series(False, index=group.index))
            .fillna(False)
            .sum()
        )
        setup_count = int(group["Ticker"].astype(str).isin(qualifying_tickers).sum())
        # A qualifying setup is necessarily a raw candidate. Keep the invariant
        # true even when a caller supplies an older eligible-universe fixture
        # without the Is Candidate marker.
        raw_candidates = max(raw_candidates, setup_count)
        metrics = {
            "Absolute Return 5D": float(group["Return 5D"].median()),
            "Absolute Return 10D": float(group["Return 10D"].median()),
            "Absolute Return 20D": float(group["Return 20D"].median()),
            "Relative Return 10D": float(group["Relative Return 10D"].median()),
            "Relative Return 20D": float(group["Relative Return 20D"].median()),
            "Above 10EMA %": 100 * float(group["Above 10EMA"].mean()),
            "Above 20EMA %": 100 * float(group["Above 20EMA"].mean()),
            "Above 50MA %": 100 * float(group["Above 50MA"].mean()),
            "Near 20D High %": 100 * float(group["Near 20D High"].mean()),
            "Near 52W High %": 100 * float(group["Near 52W High"].mean()),
        }
        required_metric_values = list(metrics.values())
        local_data_complete = all(
            np.isfinite(value) for value in required_metric_values
        )
        metadata_complete = bool(
            np.isfinite(metadata_coverage)
            and metadata_coverage >= config.MIN_METADATA_COVERAGE_PCT
        )
        data_complete = local_data_complete and metadata_complete
        exclusions = []
        if not local_data_complete:
            exclusions.append("required industry metric missing")
        if not metadata_complete:
            exclusions.append("universe metadata coverage below minimum")
        if eligible < config.MIN_QUALIFIED_INDUSTRY_SIZE:
            exclusions.append("fewer than five eligible liquid stocks")
        if metrics["Absolute Return 10D"] <= config.MIN_INDUSTRY_ABSOLUTE_RETURN_10D:
            exclusions.append("10D absolute return not positive")
        if metrics["Relative Return 20D"] <= config.MIN_INDUSTRY_RELATIVE_RETURN_20D:
            exclusions.append("20D relative return not positive")
        if metrics["Above 20EMA %"] < config.MIN_INDUSTRY_ABOVE_20EMA_PCT:
            exclusions.append("breadth above 20EMA below minimum")
        if metrics["Above 50MA %"] < config.MIN_INDUSTRY_ABOVE_50MA_PCT:
            exclusions.append("breadth above 50MA below minimum")
        if metrics["Near 20D High %"] < config.MIN_INDUSTRY_NEAR_20D_HIGH_PCT:
            exclusions.append("insufficient members near 20D highs")
        if valid_breakouts < config.MIN_INDUSTRY_VALID_BREAKOUTS:
            exclusions.append("insufficient valid breakouts")
        if setup_count < 1:
            exclusions.append("no qualifying setups")
        if (
            breakout_sample >= config.MIN_BREAKOUT_SAMPLE_FOR_FAILURE_GATE
            and failure_rate > config.MAX_INDUSTRY_BREAKOUT_FAILURE_RATE
        ):
            exclusions.append("breakout failure rate too high")
        breadth_score = (
            0.45 * metrics["Above 20EMA %"]
            + 0.35 * metrics["Above 50MA %"]
            + 0.20 * metrics["Near 20D High %"]
        )
        breakout_quality = max(0.0, success_rate - failure_rate)
        momentum_score = max(
            0.0,
            min(
                100.0,
                50
                + metrics["Relative Return 20D"] * 2
                + metrics["Relative Return 10D"] * 1.5,
            ),
        )
        composite = (
            0.30 * max(0, min(100, 50 + metrics["Relative Return 20D"] * 2))
            + 0.20 * max(0, min(100, 50 + metrics["Relative Return 10D"] * 2))
            + 0.20 * metrics["Above 20EMA %"]
            + 0.15 * metrics["Above 50MA %"]
            + 0.10 * ((metrics["Near 20D High %"] + metrics["Near 52W High %"]) / 2)
            + 0.05 * breakout_quality
        )
        sample_quality = (
            "Insufficient"
            if eligible < 3
            else "Thin"
            if eligible < 5
            else "Adequate"
            if eligible < 10
            else "Strong"
        )
        qualified = data_complete and not exclusions
        improving = (
            metrics["Absolute Return 10D"] > 0 and metrics["Relative Return 20D"] > 0
        )
        long_term = (
            float(group.get("Long-Term RS Score", group["Recent RS Score"]).median())
            >= 70
        )
        if qualified:
            classification = "Qualified Current Leader"
        elif eligible == 1:
            classification = "Isolated Leader"
        elif eligible == 2:
            classification = "Two-Stock Emerging Pair"
        elif improving:
            classification = (
                "Small-Sample Rotation Watch" if eligible < 5 else "Rotation Watch"
            )
        elif long_term:
            classification = "Long-Term Leader Currently Lagging"
        else:
            classification = "Not Qualified"
        rows.append(
            {
                "Industry": industry,
                "Sector": sector,
                "Eligible Members": eligible,
                "Raw Candidate Count": raw_candidates,
                "Qualifying Setup Count": setup_count,
                **metrics,
                "Valid Breakout Count": valid_breakouts,
                "Breakout Success Rate": success_rate,
                "Breakout Failure Rate": failure_rate,
                "High Volume Breakdown Count": int(
                    group.get(
                        "High Volume Breakdown", pd.Series(False, index=group.index)
                    )
                    .fillna(False)
                    .sum()
                ),
                "Average Recent RS": float(group["Recent RS Score"].mean()),
                "Median Recent RS": float(group["Recent RS Score"].median()),
                "Breadth Score": breadth_score,
                "Momentum Score": momentum_score,
                "Setup Quality Score": min(100, setup_count * 20),
                "Industry Composite Score": round(composite, 1),
                "Industry Qualified": qualified,
                "Industry Classification": classification,
                "Breadth Sample Quality": sample_quality,
                "Above 20EMA Breadth": f"{int(group['Above 20EMA'].sum())}/{eligible} ({metrics['Above 20EMA %']:.1f}%)",
                "Above 50MA Breadth": f"{int(group['Above 50MA'].sum())}/{eligible} ({metrics['Above 50MA %']:.1f}%)",
                "Near 20D High Breadth": f"{int(group['Near 20D High'].sum())}/{eligible} ({metrics['Near 20D High %']:.1f}%)",
                "Data Complete": data_complete,
                "Metadata Coverage %": round(float(metadata_coverage) * 100, 1),
                "Industry Rank": np.nan,
                "Exclusion Reasons": "; ".join(exclusions),
            }
        )
    result = pd.DataFrame(rows)
    ranked = (
        result[result["Industry Qualified"]]
        .sort_values("Industry Composite Score", ascending=False)
        .index
    )
    for rank, index in enumerate(ranked, 1):
        result.at[index, "Industry Rank"] = rank
    return (
        result[columns]
        .sort_values(
            ["Industry Qualified", "Industry Composite Score"], ascending=[False, False]
        )
        .reset_index(drop=True)
    )


def sister_stock_confirmation(
    ticker: str, industry: str, members: pd.DataFrame, industry_qualified: bool
) -> dict[str, object]:
    sisters = members[
        (members["Industry"] == industry)
        & (members["Ticker"].astype(str).str.upper() != ticker.upper())
    ]
    result = {
        "Qualifying Sister Count": 0,
        "Sisters Above 20EMA": 0,
        "Sisters Above 50MA": 0,
        "Sisters Positive 10D": 0,
        "Sisters Positive Relative 20D": 0,
        "Sisters Near Highs": 0,
        "Sister Valid Breakouts": 0,
        "Sister Failed Breakouts": 0,
        "Sister Median Recent RS": np.nan,
        "Sister Group Broad": False,
        "Sister Confirmation": False,
        "Sister Confirmation State": "Industry not qualified",
    }
    industry_size = int((members["Industry"] == industry).sum())
    if industry_size < config.MIN_QUALIFIED_INDUSTRY_SIZE:
        result["Sister Confirmation State"] = "Small-sample industry"
        return result
    if not industry_qualified:
        return result
    if sisters.empty:
        result["Sister Confirmation State"] = (
            "Qualified industry, but fewer than two qualifying sister setups"
        )
        return result
    result.update(
        {
            "Sisters Above 20EMA": int(sisters["Above 20EMA"].sum()),
            "Sisters Above 50MA": int(sisters["Above 50MA"].sum()),
            "Sisters Positive 10D": int((sisters["Return 10D"] > 0).sum()),
            "Sisters Positive Relative 20D": int(
                (sisters["Relative Return 20D"] > 0).sum()
            ),
            "Sisters Near Highs": int(sisters["Near 20D High"].sum()),
            "Sister Valid Breakouts": int(
                sisters.get(
                    "Valid Breakout", pd.Series(False, index=sisters.index)
                ).sum()
            ),
            "Sister Failed Breakouts": int(
                sisters.get(
                    "Failed Breakout", pd.Series(False, index=sisters.index)
                ).sum()
            ),
            "Sister Median Recent RS": float(sisters["Recent RS Score"].median()),
        }
    )
    qualifying = sisters[
        (sisters["Above 20EMA"])
        & (sisters["Above 50MA"])
        & (sisters["Return 10D"] > 0)
        & (sisters["Relative Return 20D"] > 0)
    ]
    result["Qualifying Sister Count"] = len(qualifying)
    result["Sister Group Broad"] = (
        len(qualifying) >= 2 and len(qualifying) / len(sisters) >= 0.4
    )
    result["Sister Confirmation"] = bool(
        result["Sister Group Broad"]
        and int(result["Sister Failed Breakouts"])
        <= int(result["Sister Valid Breakouts"])
    )
    if result["Sister Confirmation"]:
        result["Sister Confirmation State"] = "Sister confirmation passed"
    elif int(result["Qualifying Sister Count"]) < 2:
        result["Sister Confirmation State"] = (
            "Qualified industry, but fewer than two qualifying sister setups"
        )
    else:
        result["Sister Confirmation State"] = (
            "Qualified industry, but sister-stock breadth is insufficient"
        )
    return result


def enforce_setup_consistency(
    row: dict[str, object],
) -> tuple[dict[str, object], list[str]]:
    result = dict(row)
    warnings: list[str] = []
    tightness, vcp = (
        str(result.get("Tightness Label", "")),
        str(result.get("VCP Label", "")),
    )
    quality = str(result.get("Pullback Quality", ""))
    if tightness == "Loose" and quality.startswith("A"):
        result["Pullback Quality"] = "B - Healthy Pullback"
        warnings.append("Loose caps Pullback Quality at B")
    if tightness == "Loose" and vcp == "Poor VCP":
        result["Pullback Quality"] = "C - Extended Pullback"
        warnings.append("Loose plus Poor VCP consistency conflict")
    if (
        result.get("Category") == "Tight Consolidation Candidates"
        and tightness == "Loose"
    ):
        result["Category"] = "Developing Base Candidates"
        warnings.append("Loose cannot be Tight Consolidation")
    return result, warnings


def final_candidate_score(row: dict[str, object]) -> float:
    return score_candidate(row).final_score


def decide_candidate(
    row: dict[str, object], market: MarketRegime, portfolio: PortfolioRisk
) -> DecisionResult:
    """Compatibility view over the authoritative decision-and-sizing engine."""
    consistent, warnings = enforce_setup_consistency(row)
    score = final_candidate_score(consistent)
    normal_drawdown = calculate_drawdown_state(100_000.0, 100_000.0)
    result = canonical_candidate_decision(
        consistent,
        market.regime if market.new_risk_allowed else "Risk Off",
        normal_drawdown,
        portfolio,
        len(portfolio.positions),
        portfolio_new_risk_allowed=bool(
            len(portfolio.positions) < config.MAX_OPEN_POSITIONS
            and portfolio.remaining_heat_r >= config.HALF_RISK_R
            and not portfolio.warnings
        ),
        market_new_risk_allowed=market.new_risk_allowed,
    )
    tier = (
        "Review Now"
        if result.actionable
        else ("Watch Later" if result.state == "WATCH" else "Skip Today")
    )
    blocking = result.reasons if result.state == "NO TRADE" else ()
    decision_reasons = (
        result.missing_confirmations
        if result.actionable
        else result.reasons + result.missing_confirmations
    )
    return DecisionResult(
        result.state,
        result.actionable,
        tier,
        score,
        tuple(decision_reasons),
        tuple(blocking),
        tuple(warnings),
    )


def canonicalise_candidates(
    rows: Iterable[dict[str, object]],
) -> list[dict[str, object]]:
    precedence = {
        name: index
        for index, name in enumerate(
            (
                "Breakout Candidates",
                "Volume Surge Candidates",
                "Pullback Candidates",
                "Tight Consolidation Candidates",
                "Developing Base Candidates",
                "Extended Candidates",
            )
        )
    }
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("Ticker", "")).upper(), []).append(dict(row))
    output = []
    for ticker, matches in grouped.items():
        chosen = min(
            matches, key=lambda item: precedence.get(str(item.get("Category")), 99)
        )
        chosen["Ticker"] = ticker
        chosen["Matched Setup Tags"] = ", ".join(
            dict.fromkeys(str(item.get("Category", "")) for item in matches)
        )
        chosen["Primary Setup Category"] = chosen.get("Category", "")
        output.append(chosen)
    return output


def apply_concentration_limits(
    rows: list[dict[str, object]], top_action: bool = True
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    selected, excluded = [], []
    industry_counts: dict[str, int] = {}
    sector_counts: dict[str, int] = {}
    for row in sorted(
        rows, key=lambda item: float(item.get("Final Score") or 0), reverse=True
    ):
        industry, sector = str(row.get("Industry", "")), str(row.get("Sector", ""))
        industry_limit = (
            config.MAX_TOP_ACTION_PER_INDUSTRY
            if top_action
            else config.MAX_DAILY_FOCUS_PER_INDUSTRY
        )
        if (
            float(row.get("Industry Composite Score") or 0)
            >= config.HIGH_CONVICTION_INDUSTRY_SCORE
        ):
            industry_limit += 1
        reason = ""
        if industry_counts.get(industry, 0) >= industry_limit:
            reason = "industry concentration limit"
        sector_limit = (
            config.MAX_PER_SECTOR if top_action else config.MAX_DAILY_FOCUS_PER_SECTOR
        )
        if not reason and sector_counts.get(sector, 0) >= sector_limit:
            reason = "sector concentration limit"
        if reason:
            copy = dict(row)
            copy["Concentration Exclusion Reason"] = reason
            excluded.append(copy)
            continue
        selected.append(row)
        industry_counts[industry] = industry_counts.get(industry, 0) + 1
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
    return selected, excluded


def expectancy_summary(trades: pd.DataFrame) -> ExpectancySummary:
    if trades.empty or "realised_r" not in trades.columns:
        return ExpectancySummary(
            0,
            "Insufficient sample",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )
    realised = pd.to_numeric(trades["realised_r"], errors="coerce").dropna()
    count = len(realised)
    if count < config.MIN_COMPLETED_TRADES_FOR_PRELIMINARY:
        label = "Insufficient sample"
    elif count < config.MIN_COMPLETED_TRADES_FOR_DEVELOPING:
        label = "Preliminary"
    elif count < config.MIN_COMPLETED_TRADES_FOR_MEANINGFUL:
        label = "Developing evidence"
    else:
        label = "Statistically more meaningful"
    zeros = pd.Series(0.0, index=trades.index)
    missing = pd.Series(np.nan, index=trades.index)
    costs = pd.to_numeric(trades.get("fees", zeros), errors="coerce").fillna(
        0
    ) + pd.to_numeric(trades.get("slippage", zeros), errors="coerce").fillna(0)
    risk = pd.to_numeric(trades.get("initial_risk_dollars", missing), errors="coerce")
    cost_r = (costs / risk).replace([np.inf, -np.inf], np.nan).fillna(0)
    wins, losses = realised[realised > 0], realised[realised <= 0]
    win_rate = len(wins) / count if count else None
    avg_win = wins.mean() if len(wins) else 0.0
    avg_loss = losses.mean() if len(losses) else 0.0
    avg_cost = float(cost_r.mean()) if len(cost_r) else 0.0
    expectancy = (
        (win_rate * avg_win - (1 - win_rate) * abs(avg_loss) - avg_cost)
        if win_rate is not None
        else None
    )
    equity = realised.cumsum()
    drawdown = equity - equity.cummax()
    rolling20 = realised.rolling(20).mean().iloc[-1] if count >= 20 else np.nan
    rolling50 = realised.rolling(50).mean().iloc[-1] if count >= 50 else np.nan
    profit_factor = (
        wins.sum() / abs(losses.sum()) if len(losses) and losses.sum() != 0 else None
    )
    payoff = avg_win / abs(avg_loss) if avg_loss else None
    return ExpectancySummary(
        count,
        label,
        round(float(expectancy), 4),
        round(float(win_rate), 4),
        round(float(avg_win), 4),
        round(float(avg_loss), 4),
        round(avg_cost, 4),
        None if payoff is None else round(float(payoff), 4),
        None if profit_factor is None else round(float(profit_factor), 4),
        round(float(drawdown.min()), 4),
        None if pd.isna(rolling20) else round(float(rolling20), 4),
        None if pd.isna(rolling50) else round(float(rolling50), 4),
    )


def journal_drawdown_analytics(trades: pd.DataFrame) -> dict[str, object]:
    """Calculate realised-R equity/drawdown path and FULL/HALF performance splits."""
    if trades.empty or "realised_r" not in trades:
        return {
            "equity_high_water_mark_r": None,
            "current_drawdown_r": None,
            "maximum_historical_drawdown_r": None,
            "drawdown_duration": 0,
            "recovery_duration": None,
            "by_trade_state": {},
        }
    ordered = trades.copy()
    if "exit_date" in ordered:
        ordered = ordered.sort_values("exit_date")
    realised = pd.to_numeric(ordered["realised_r"], errors="coerce").dropna()
    equity = realised.cumsum()
    high_water = equity.cummax().clip(lower=0)
    drawdown = high_water - equity
    in_drawdown = drawdown > 0
    duration = 0
    max_duration = 0
    recovery_duration: int | None = None
    for flag in in_drawdown:
        duration = duration + 1 if flag else 0
        max_duration = max(max_duration, duration)
        if not flag and duration == 0:
            recovery_duration = max_duration or recovery_duration
    by_state: dict[str, object] = {}
    state_column = "trade_state" if "trade_state" in ordered else "position_size_state"
    if state_column in ordered:
        for state in ("FULL", "HALF"):
            subset = ordered[ordered[state_column].eq(state)]
            summary = expectancy_summary(subset)
            state_realised = pd.to_numeric(
                subset.get("realised_r"), errors="coerce"
            ).dropna()
            state_equity = state_realised.cumsum()
            state_drawdown = state_equity.cummax().clip(lower=0) - state_equity
            by_state[state] = {
                **asdict(summary),
                "maximum_drawdown_contribution_r": (
                    round(float(state_drawdown.max()), 4)
                    if not state_drawdown.empty
                    else None
                ),
                "average_mfe_r": float(
                    pd.to_numeric(subset.get("MFE_R"), errors="coerce").mean()
                )
                if "MFE_R" in subset
                else None,
                "average_mae_r": float(
                    pd.to_numeric(subset.get("MAE_R"), errors="coerce").mean()
                )
                if "MAE_R" in subset
                else None,
            }
    return {
        "equity_high_water_mark_r": round(float(high_water.iloc[-1]), 4),
        "current_drawdown_r": round(float(drawdown.iloc[-1]), 4),
        "maximum_historical_drawdown_r": round(float(drawdown.max()), 4),
        "drawdown_duration": duration,
        "maximum_drawdown_duration": max_duration,
        "recovery_duration": recovery_duration,
        "by_trade_state": by_state,
    }


def dataclass_record(value: object) -> dict[str, object]:
    return asdict(value)
