"""Deterministic Phase 2 research-only setup lanes.

This module annotates copied, post-canonical report records.  It never makes a
production decision, sizes a trade, or supplies a missing trade-plan value.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from research.chart_quality import (
    CONTRACTION,
    DISTRIBUTION,
    OVERHEAD_SUPPLY,
    PRIOR_ADVANCE,
    RS_PERSISTENCE,
    SUPPORT_RESPECT,
    TREND_SMOOTHNESS,
)


TIGHT_BASE_LANE = "Tight Base / VCP"
PULLBACK_LANE = "Pullback to Support"
BREAKOUT_LANE = "Breakout Retest / High Flag"
LANE_NAMES = (TIGHT_BASE_LANE, PULLBACK_LANE, BREAKOUT_LANE)

PHASE2_RESEARCH_FIELDS = (
    "Research Prior Advance 60D %",
    "Research Pullback Depth ATR",
    "Research Pullback Volume Ratio",
    "Research Higher Low Preserved",
    "Research Close Strength %",
    "Research Volume Dry-Up Ratio",
    "Research Breakout Evidence",
    "Research Breakout Age Sessions",
    "Research Breakout Pivot",
    "Research Breakout Hold Sessions",
    "Research Post-Breakout Range %",
    "Research Post-Breakout Volume Ratio",
)

LANE_OUTPUT_FIELDS = (
    "Setup Lanes",
    f"{TIGHT_BASE_LANE} Member",
    f"{TIGHT_BASE_LANE} Score",
    f"{TIGHT_BASE_LANE} Rank",
    f"{TIGHT_BASE_LANE} Reason",
    f"{TIGHT_BASE_LANE} Missing",
    f"{PULLBACK_LANE} Member",
    f"{PULLBACK_LANE} Score",
    f"{PULLBACK_LANE} Rank",
    f"{PULLBACK_LANE} Reason",
    f"{PULLBACK_LANE} Missing",
    "Pullback Lane Quality",
    f"{BREAKOUT_LANE} Member",
    f"{BREAKOUT_LANE} Score",
    f"{BREAKOUT_LANE} Rank",
    f"{BREAKOUT_LANE} Reason",
    f"{BREAKOUT_LANE} Missing",
    "Breakout Lane State",
)

PHASE2_REPORT_FIELDS = PHASE2_RESEARCH_FIELDS + LANE_OUTPUT_FIELDS

_BREAKOUT_MEMBER_STATES = {
    "NEAR_PIVOT_UNCONFIRMED",
    "SAME_DAY_BREAKOUT_UNCONFIRMED",
    "POST_BREAKOUT_HOLD",
    "POST_BREAKOUT_CONSOLIDATION",
}


@dataclass(frozen=True)
class LaneResult:
    member: bool
    score: float | None
    reason: str
    missing: tuple[str, ...]
    label: str = ""


def _number(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if np.isfinite(parsed) else None


def _truth(value: object) -> bool | None:
    if value is True or str(value).strip().lower() == "true":
        return True
    if value is False or str(value).strip().lower() == "false":
        return False
    return None


def _text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    parsed = str(value).strip()
    return "" if parsed.lower() in {"nan", "none"} else parsed


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def _higher(value: float | None, low: float, high: float) -> float | None:
    if value is None:
        return None
    if high <= low:
        raise ValueError("high must exceed low")
    return _clamp((value - low) * 100.0 / (high - low))


def _lower(value: float | None, best: float, worst: float) -> float | None:
    if value is None:
        return None
    if worst <= best:
        raise ValueError("worst must exceed best")
    return _clamp((worst - value) * 100.0 / (worst - best))


def _pullback_depth_score(value: float | None) -> float | None:
    if value is None:
        return None
    if value < 0:
        return 0.0
    if value < 1.5:
        return 70.0 + (value / 1.5) * 30.0
    if value <= 3.0:
        return 100.0
    return _clamp((6.0 - value) * 100.0 / 3.0)


def _weighted_score(
    components: list[tuple[str, float | None, float]], penalties: float = 0.0
) -> tuple[float, tuple[str, ...]]:
    missing = tuple(name for name, value, _ in components if value is None)
    score = sum((value or 0.0) * weight / 100.0 for _, value, weight in components)
    return round(_clamp(score - penalties), 2), missing


def _support_distance(row: Mapping[str, object]) -> float | None:
    direct = _number(row.get("Nearest Support Distance ATR"))
    if direct is not None:
        return direct
    distances = [
        _number(row.get("Distance From EMA10 ATR")),
        _number(row.get("Distance From EMA20 ATR")),
        _number(row.get("Distance From MA50 ATR")),
    ]
    usable = [value for value in distances if value is not None]
    return min(usable) if usable else None


def _explicit_support_signal(value: object) -> str:
    """Return observable support evidence, excluding the generic placeholder."""
    text = _text(value)
    tokens = [
        item.strip() for item in text.replace(";", ",").split(",") if item.strip()
    ]
    return text if any(item.casefold() != "recent support" for item in tokens) else ""


def _phase3_context(row: Mapping[str, object], components: tuple[str, ...]) -> str:
    """Return concise Phase 3 context without affecting lane calculations."""
    states = []
    for component in components:
        state = _text(row.get(f"CQ {component} State"))
        if state:
            states.append(f"{component}={state}")
    return "Phase 3 RESEARCH_ONLY: " + ", ".join(states) if states else ""


def _tight_base_result(row: Mapping[str, object]) -> LaneResult:
    recent_rs = _number(row.get("Recent RS Score"))
    acceleration = _number(row.get("RS Momentum Acceleration"))
    trend = _text(row.get("RS Trend"))
    trend_base = {
        "Emerging Leader": 100.0,
        "Improving": 85.0,
        "Stable Leader": 80.0,
        "Stable": 55.0,
        "Weakening": 25.0,
        "Fading": 10.0,
        "Lagging": 0.0,
    }.get(trend)
    trend_score = None
    if trend_base is not None or acceleration is not None:
        parts = []
        if trend_base is not None:
            parts.append((trend_base, 0.7))
        if acceleration is not None:
            parts.append((_higher(acceleration, -0.05, 0.05) or 0.0, 0.3))
        denominator = sum(weight for _, weight in parts)
        trend_score = sum(value * weight for value, weight in parts) / denominator

    range_10 = _number(row.get("10 Day Range %"))
    range_20 = _number(row.get("20 Day Range %"))
    contraction = (
        range_10 / range_20
        if range_10 is not None and range_20 not in {None, 0.0}
        else None
    )
    adr20 = _number(row.get("ADR20 %"))
    adr60 = _number(row.get("ADR60 %"))
    vcp_ratio = _number(row.get("VCP Ratio"))
    if vcp_ratio is None and adr20 is not None and adr60 not in {None, 0.0}:
        vcp_ratio = adr20 / adr60
    dry_up = _number(row.get("Research Volume Dry-Up Ratio"))
    pivot_distance = _number(row.get("Distance From Pivot %"))
    high_distance = _number(row.get("From 52W High %"))
    prior_advance = _number(row.get("Research Prior Advance 60D %"))

    components = [
        ("Recent RS", _higher(recent_rs, 40.0, 90.0), 12.0),
        ("RS improvement", trend_score, 8.0),
        ("10-day range", _lower(range_10, 4.0, 20.0), 18.0),
        ("10D/20D contraction", _lower(contraction, 0.45, 1.0), 14.0),
        ("ADR20/ADR60", _lower(vcp_ratio, 0.50, 1.10), 14.0),
        ("volume dry-up", _lower(dry_up, 0.50, 1.30), 10.0),
        (
            "pivot proximity",
            _lower(
                abs(pivot_distance) if pivot_distance is not None else None, 0.0, 10.0
            ),
            10.0,
        ),
        (
            "52-week-high proximity",
            _lower(
                abs(high_distance) if high_distance is not None else None, 0.0, 30.0
            ),
            6.0,
        ),
        ("prior-advance proxy", _higher(prior_advance, 0.0, 30.0), 8.0),
    ]

    extension = _text(row.get("Extension Status"))
    penalties = (
        30.0
        if extension == "Overextended"
        else 15.0
        if extension == "Extended"
        else 0.0
    )
    penalty_reasons: list[str] = []
    if penalties:
        penalty_reasons.append(f"extension penalty -{int(penalties)}")
    if range_10 is not None and range_10 > 18.0:
        penalties += 10.0
        penalty_reasons.append("loose-range penalty -10")
    volume_ratio = _number(row.get("Volume Ratio"))
    if volume_ratio is not None and volume_ratio > 1.5:
        penalties += 10.0
        penalty_reasons.append("volume-expansion penalty -10")

    score, missing = _weighted_score(components, penalties)
    category = _text(row.get("Category"))
    contraction_available = any(
        value is not None for value in (range_10, contraction, vcp_ratio)
    )
    broad_match = (
        category in {"Tight Consolidation Candidates", "Developing Base Candidates"}
        or (contraction is not None and contraction <= 1.0)
        or (vcp_ratio is not None and vcp_ratio <= 1.0)
        or (pivot_distance is not None and abs(pivot_distance) <= 10.0)
    )
    member = contraction_available and broad_match
    evidence = [
        f"10D range {range_10:.2f}%"
        if range_10 is not None
        else "10D range unavailable",
        f"10D/20D {contraction:.2f}"
        if contraction is not None
        else "10D/20D unavailable",
        f"ADR ratio {vcp_ratio:.2f}"
        if vcp_ratio is not None
        else "ADR ratio unavailable",
        f"volume dry-up {dry_up:.2f}"
        if dry_up is not None
        else "volume dry-up unavailable",
        f"pivot distance {pivot_distance:.2f}%"
        if pivot_distance is not None
        else "pivot distance unavailable",
        f"52W high distance {high_distance:.2f}%"
        if high_distance is not None
        else "52W high distance unavailable",
    ]
    evidence.extend(penalty_reasons)
    if missing:
        evidence.append("missing: " + ", ".join(missing))
    if not member:
        evidence.insert(0, "insufficient observable contraction evidence")
    phase3 = _phase3_context(
        row, (PRIOR_ADVANCE, TREND_SMOOTHNESS, CONTRACTION, RS_PERSISTENCE)
    )
    if phase3:
        evidence.append(phase3)
    return LaneResult(member, score if member else None, "; ".join(evidence), missing)


def _pullback_result(row: Mapping[str, object]) -> LaneResult:
    prior_advance = _number(row.get("Research Prior Advance 60D %"))
    recent_rs = _number(row.get("Recent RS Score"))
    support_distance = _support_distance(row)
    depth = _number(row.get("Research Pullback Depth ATR"))
    distance_50ma = _number(row.get("Distance From 50MA %"))
    higher_low = _truth(row.get("Research Higher Low Preserved"))
    structure_parts: list[float] = []
    if distance_50ma is not None:
        structure_parts.append(100.0 if distance_50ma >= 0 else 0.0)
    if higher_low is not None:
        structure_parts.append(100.0 if higher_low else 0.0)
    structure_score = (
        sum(structure_parts) / len(structure_parts) if structure_parts else None
    )
    pullback_volume = _number(row.get("Research Pullback Volume Ratio"))
    close_strength = _number(row.get("Research Close Strength %"))
    support_signal = _explicit_support_signal(row.get("Support Signal"))
    pivot_distance = _number(row.get("Distance From Pivot %"))

    components = [
        ("prior advance", _higher(prior_advance, 0.0, 30.0), 15.0),
        ("Recent RS", _higher(recent_rs, 40.0, 90.0), 8.0),
        ("support distance", _lower(support_distance, 0.0, 3.0), 18.0),
        ("pullback depth ATR", _pullback_depth_score(depth), 14.0),
        ("trend structure", structure_score, 12.0),
        ("pullback volume", _lower(pullback_volume, 0.50, 1.40), 10.0),
        ("close strength", _higher(close_strength, 25.0, 85.0), 8.0),
        ("support/reclaim evidence", 100.0 if support_signal else None, 10.0),
        (
            "pivot/overhead context",
            _lower(
                abs(pivot_distance) if pivot_distance is not None else None, 0.0, 15.0
            ),
            5.0,
        ),
    ]

    penalties = 0.0
    penalty_reasons: list[str] = []
    broken = distance_50ma is not None and distance_50ma < 0
    excessive = depth is not None and depth > 6.0
    if broken:
        penalties += 25.0
        penalty_reasons.append("broken-MA50 penalty -25")
    if higher_low is False:
        penalties += 20.0
        penalty_reasons.append("lost-higher-low penalty -20")
    if excessive:
        penalties += 20.0
        penalty_reasons.append("excessive-pullback penalty -20")
    if not support_signal:
        penalties += 10.0
        penalty_reasons.append("no reclaim/support confirmation -10")
    extension = _text(row.get("Extension Status"))
    if extension == "Overextended":
        penalties += 30.0
        penalty_reasons.append("extension penalty -30")
    elif extension == "Extended":
        penalties += 15.0
        penalty_reasons.append("extension penalty -15")

    score, missing = _weighted_score(components, penalties)
    category = _text(row.get("Category"))
    member = support_distance is not None and (
        support_distance <= 3.0 or category == "Pullback Candidates"
    )
    structure_broken = broken or higher_low is False
    if structure_broken or excessive:
        quality = "WEAK_OR_BROKEN"
    elif not member:
        quality = "AMBIGUOUS_SUPPORT"
    elif score >= 70.0 and support_signal:
        quality = "CONSTRUCTIVE"
    elif score >= 50.0:
        quality = "POTENTIAL"
    else:
        quality = "AMBIGUOUS_SUPPORT"
    reason_parts = [
        quality,
        (
            f"support distance {support_distance:.2f} ATR"
            if support_distance is not None
            else "support distance unavailable"
        ),
        f"pullback depth {depth:.2f} ATR"
        if depth is not None
        else "pullback depth unavailable",
        f"prior advance {prior_advance:.2f}%"
        if prior_advance is not None
        else "prior advance unavailable",
    ]
    reason_parts.extend(penalty_reasons)
    if missing:
        reason_parts.append("missing: " + ", ".join(missing))
    if not member:
        reason_parts.insert(0, "insufficient support-distance evidence")
    phase3 = _phase3_context(
        row,
        (
            PRIOR_ADVANCE,
            TREND_SMOOTHNESS,
            OVERHEAD_SUPPLY,
            SUPPORT_RESPECT,
            RS_PERSISTENCE,
        ),
    )
    if phase3:
        reason_parts.append(phase3)
    return LaneResult(
        member,
        score if member else None,
        "; ".join(reason_parts),
        missing,
        quality,
    )


def _breakout_state(row: Mapping[str, object]) -> str:
    state = _text(row.get("Research Breakout Evidence")).upper()
    pivot_distance = _number(row.get("Distance From Pivot %"))
    if state == "NO_RECENT_BREAKOUT_EVIDENCE":
        if pivot_distance is not None and abs(pivot_distance) <= 3.0:
            return "NEAR_PIVOT_UNCONFIRMED"
    return state or "UNKNOWN"


def _breakout_result(row: Mapping[str, object]) -> LaneResult:
    state = _breakout_state(row)
    recent_rs = _number(row.get("Recent RS Score"))
    pivot_distance = _number(row.get("Distance From Pivot %"))
    post_range = _number(row.get("Research Post-Breakout Range %"))
    post_volume = _number(row.get("Research Post-Breakout Volume Ratio"))
    hold_sessions = _number(row.get("Research Breakout Hold Sessions"))
    range_10 = _number(row.get("10 Day Range %"))
    extension = _text(row.get("Extension Status"))
    lifecycle_score = {
        "POST_BREAKOUT_CONSOLIDATION": 100.0,
        "POST_BREAKOUT_HOLD": 75.0,
        "SAME_DAY_BREAKOUT_UNCONFIRMED": 50.0,
        "NEAR_PIVOT_UNCONFIRMED": 35.0,
        "RECENT_BREAKOUT_INVALIDATED": 0.0,
        "RECENT_BREAKOUT_DATA_INCOMPLETE": 0.0,
        "BREAKOUT_WINDOW_INCOMPLETE": 0.0,
        "NO_RECENT_BREAKOUT_EVIDENCE": 0.0,
    }.get(state)
    extension_score = {
        "Not Extended": 100.0,
        "Normal": 80.0,
        "Extended": 25.0,
        "Overextended": 0.0,
    }.get(extension)
    components = [
        ("breakout history/state", lifecycle_score, 30.0),
        ("Recent RS", _higher(recent_rs, 40.0, 90.0), 12.0),
        (
            "pivot proximity",
            _lower(
                abs(pivot_distance) if pivot_distance is not None else None, 0.0, 10.0
            ),
            14.0,
        ),
        ("post-breakout range", _lower(post_range, 3.0, 12.0), 12.0),
        ("post-breakout volume", _lower(post_volume, 0.60, 1.50), 10.0),
        ("hold duration", _higher(hold_sessions, 0.0, 5.0), 8.0),
        ("10-day contraction", _lower(range_10, 4.0, 20.0), 8.0),
        ("extension control", extension_score, 6.0),
    ]
    penalties = 0.0
    penalty_reasons: list[str] = []
    if extension == "Overextended":
        penalties += 30.0
        penalty_reasons.append("extension penalty -30")
    elif extension == "Extended":
        penalties += 15.0
        penalty_reasons.append("extension penalty -15")
    if post_range is not None and post_range > 12.0:
        penalties += 15.0
        penalty_reasons.append("wide-post-breakout-range penalty -15")
    if post_volume is not None and post_volume > 1.5:
        penalties += 10.0
        penalty_reasons.append("post-breakout-volume-expansion penalty -10")
    score, missing = _weighted_score(components, penalties)
    member = state in _BREAKOUT_MEMBER_STATES
    state_text = {
        "NEAR_PIVOT_UNCONFIRMED": "near pivot; no confirmed breakout/retest state",
        "SAME_DAY_BREAKOUT_UNCONFIRMED": "same-day breakout; not a confirmed retest or high flag",
        "POST_BREAKOUT_HOLD": "rolling lookback shows a held recent breakout",
        "POST_BREAKOUT_CONSOLIDATION": "rolling lookback shows post-breakout consolidation",
        "RECENT_BREAKOUT_INVALIDATED": "recent breakout lost its pivot and is unranked",
        "RECENT_BREAKOUT_DATA_INCOMPLETE": "recent breakout lifecycle data is incomplete and unranked",
        "BREAKOUT_WINDOW_INCOMPLETE": "recent breakout event window is incomplete and unranked",
        "NO_RECENT_BREAKOUT_EVIDENCE": "no recent breakout evidence",
        "UNKNOWN": "breakout history/state unavailable",
    }.get(state, state.lower().replace("_", " "))
    reason_parts = [state_text, "rolling lookback only; no persistent Phase 4 state"]
    reason_parts.extend(penalty_reasons)
    if missing:
        reason_parts.append("missing: " + ", ".join(missing))
    phase3 = _phase3_context(
        row, (PRIOR_ADVANCE, DISTRIBUTION, OVERHEAD_SUPPLY, RS_PERSISTENCE)
    )
    if phase3:
        reason_parts.append(phase3)
    return LaneResult(
        member,
        score if member else None,
        "; ".join(reason_parts),
        missing,
        state,
    )


def _rank_lane(frame: pd.DataFrame, lane: str) -> None:
    member_column = f"{lane} Member"
    score_column = f"{lane} Score"
    missing_column = f"{lane} Missing"
    rank_column = f"{lane} Rank"
    member_indices = frame.index[frame[member_column].eq(True)].tolist()  # noqa: E712
    if not member_indices:
        return
    ordered = sorted(
        member_indices,
        key=lambda index: (
            len(
                [
                    item
                    for item in str(frame.at[index, missing_column]).split("; ")
                    if item
                ]
            ),
            -float(frame.at[index, score_column]),
            str(frame.at[index, "Ticker"]),
        ),
    )
    for rank, index in enumerate(ordered, start=1):
        frame.at[index, rank_column] = rank


def annotate_setup_lanes(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a deep-copied frame with independent Phase 2 lane annotations."""
    annotated = frame.copy(deep=True)
    for field in LANE_OUTPUT_FIELDS:
        if field.endswith(" Member"):
            annotated[field] = False
        elif field.endswith(" Score") or field.endswith(" Rank"):
            annotated[field] = np.nan
        else:
            annotated[field] = ""
    if annotated.empty:
        return annotated

    for index, row in annotated.iterrows():
        if _text(row.get("Report Section")) != "Pattern Watchlist":
            continue
        record: Mapping[str, Any] = row.to_dict()
        results = {
            TIGHT_BASE_LANE: _tight_base_result(record),
            PULLBACK_LANE: _pullback_result(record),
            BREAKOUT_LANE: _breakout_result(record),
        }
        memberships: list[str] = []
        for lane, result in results.items():
            annotated.at[index, f"{lane} Member"] = result.member
            annotated.at[index, f"{lane} Score"] = (
                result.score if result.member else np.nan
            )
            annotated.at[index, f"{lane} Reason"] = result.reason
            annotated.at[index, f"{lane} Missing"] = "; ".join(result.missing)
            if result.member:
                memberships.append(lane)
        annotated.at[index, "Pullback Lane Quality"] = results[PULLBACK_LANE].label
        annotated.at[index, "Breakout Lane State"] = results[BREAKOUT_LANE].label
        annotated.at[index, "Setup Lanes"] = "; ".join(memberships)

    for lane in LANE_NAMES:
        _rank_lane(annotated, lane)
    return annotated


def _mean_or_none(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    return float(clean.mean()) if not clean.empty else None


def calculate_phase2_history_features(
    history: pd.DataFrame, *, as_of: object | None = None
) -> dict[str, object]:
    """Calculate narrow point-in-time OHLCV evidence for Phase 2 lanes."""
    missing: dict[str, object] = {field: None for field in PHASE2_RESEARCH_FIELDS}
    required = {"Open", "High", "Low", "Close", "Volume"}
    if history.empty or not required.issubset(history.columns):
        return missing
    frame = history.copy().sort_index()
    if as_of is not None and isinstance(frame.index, pd.DatetimeIndex):
        cutoff = pd.Timestamp(as_of)
        if frame.index.tz is not None and cutoff.tzinfo is None:
            cutoff = cutoff.tz_localize(frame.index.tz)
        elif frame.index.tz is None and cutoff.tzinfo is not None:
            cutoff = cutoff.tz_localize(None)
        frame = frame.loc[frame.index <= cutoff]
    if frame.empty:
        return missing
    for column in required:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").replace(
            [np.inf, -np.inf], np.nan
        )
    result: dict[str, object] = dict(missing)
    close = frame["Close"]
    high = frame["High"]
    low = frame["Low"]
    volume = frame["Volume"]
    previous_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)

    if len(frame) >= 71:
        advance_start = _number(close.iloc[-71])
        advance_end = _number(close.iloc[-11])
        if advance_start not in {None, 0.0} and advance_end is not None:
            result["Research Prior Advance 60D %"] = round(
                (advance_end / advance_start - 1.0) * 100.0, 4
            )

    if len(frame) >= 21:
        atr_input_window = frame.iloc[-21:]
        measured_window = atr_input_window.iloc[-20:]
        if (
            not atr_input_window["Close"].isna().any()
            and not measured_window[["High", "Low"]].isna().any().any()
        ):
            atr20 = _mean_or_none(true_range.iloc[-20:])
            if atr20 not in {None, 0.0}:
                result["Research Pullback Depth ATR"] = round(
                    (high.iloc[-20:].max() - close.iloc[-1]) / float(atr20), 4
                )

    if len(frame) >= 31:
        pullback_price_window = close.iloc[-31:]
        pullback_volume_window = volume.iloc[-30:]
        if (
            not pullback_price_window.isna().any()
            and not pullback_volume_window.isna().any()
        ):
            returns = close.pct_change()
            recent_down = volume.iloc[-10:][returns.iloc[-10:] < 0]
            prior_up = volume.iloc[-30:-10][returns.iloc[-30:-10] > 0]
            recent_down_mean = _mean_or_none(recent_down)
            prior_up_mean = _mean_or_none(prior_up)
            if recent_down_mean is not None and prior_up_mean not in {None, 0.0}:
                result["Research Pullback Volume Ratio"] = round(
                    recent_down_mean / float(prior_up_mean), 4
                )
        higher_low_window = low.iloc[-30:]
        if not higher_low_window.isna().any():
            result["Research Higher Low Preserved"] = bool(
                low.iloc[-10:].min() >= low.iloc[-30:-10].min()
            )

    latest_high = _number(high.iloc[-1])
    latest_low = _number(low.iloc[-1])
    latest_close = _number(close.iloc[-1])
    if latest_high is not None and latest_low is not None and latest_close is not None:
        latest_range = latest_high - latest_low
        if latest_range > 0:
            result["Research Close Strength %"] = round(
                (latest_close - latest_low) / latest_range * 100.0, 4
            )

    if len(frame) >= 25:
        dry_up_window = volume.iloc[-25:]
        if not dry_up_window.isna().any():
            recent_volume = _mean_or_none(volume.iloc[-5:])
            prior_volume = _mean_or_none(volume.iloc[-25:-5])
            if recent_volume is not None and prior_volume not in {None, 0.0}:
                result["Research Volume Dry-Up Ratio"] = round(
                    recent_volume / float(prior_volume), 4
                )

    prior_high = high.shift(1).rolling(50, min_periods=50).max()
    prior_volume = volume.shift(1).rolling(50, min_periods=20).mean()
    assessable = (
        close.notna()
        & volume.notna()
        & prior_high.notna()
        & prior_volume.notna()
        & (prior_volume > 0)
    )
    candidate_positions = list(range(max(0, len(frame) - 16), len(frame)))
    event_positions = [
        position
        for position in candidate_positions
        if bool(assessable.iloc[position])
        and bool(close.iloc[position] > prior_high.iloc[position])
        and bool(volume.iloc[position] / prior_volume.iloc[position] >= 1.2)
    ]
    incomplete_positions = [
        position
        for position in candidate_positions
        if not bool(assessable.iloc[position])
    ]
    if not event_positions:
        result["Research Breakout Evidence"] = (
            "BREAKOUT_WINDOW_INCOMPLETE"
            if incomplete_positions
            else "NO_RECENT_BREAKOUT_EVIDENCE"
        )
        return result

    event_position = event_positions[-1]
    age = len(frame) - 1 - event_position
    pivot = _number(prior_high.iloc[event_position])
    result["Research Breakout Age Sessions"] = age
    result["Research Breakout Pivot"] = None if pivot is None else round(pivot, 4)
    if pivot is None:
        result["Research Breakout Evidence"] = "BREAKOUT_WINDOW_INCOMPLETE"
        return result

    if age == 0:
        result["Research Breakout Evidence"] = "SAME_DAY_BREAKOUT_UNCONFIRMED"
        return result

    post_event = frame.iloc[event_position + 1 :]
    lifecycle_columns = ["High", "Low", "Close", "Volume"]
    if post_event[lifecycle_columns].isna().any().any():
        result["Research Breakout Evidence"] = "RECENT_BREAKOUT_DATA_INCOMPLETE"
        return result

    held = bool((post_event["Close"] >= pivot * 0.97).all())
    result["Research Breakout Hold Sessions"] = int(len(post_event)) if held else 0
    result["Research Post-Breakout Range %"] = round(
        (post_event["High"].max() - post_event["Low"].min()) / close.iloc[-1] * 100.0,
        4,
    )
    pre_volume_window = volume.iloc[event_position - 20 : event_position]
    pre_volume = (
        _mean_or_none(pre_volume_window)
        if len(pre_volume_window) == 20 and not pre_volume_window.isna().any()
        else None
    )
    post_volume = _mean_or_none(post_event["Volume"])
    if post_volume is not None and pre_volume not in {None, 0.0}:
        result["Research Post-Breakout Volume Ratio"] = round(
            post_volume / float(pre_volume), 4
        )

    if not held:
        state = "RECENT_BREAKOUT_INVALIDATED"
    elif (
        age >= 3
        and _number(result["Research Post-Breakout Range %"]) is not None
        and float(result["Research Post-Breakout Range %"]) <= 8.0
        and _number(result["Research Post-Breakout Volume Ratio"]) is not None
        and float(result["Research Post-Breakout Volume Ratio"]) <= 1.0
    ):
        state = "POST_BREAKOUT_CONSOLIDATION"
    else:
        state = "POST_BREAKOUT_HOLD"
    result["Research Breakout Evidence"] = state
    return result
