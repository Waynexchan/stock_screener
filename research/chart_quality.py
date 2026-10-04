"""Deterministic, explainable Phase 3 research-only chart quality.

The functions in this module describe observable chart structure.  They do not
make production decisions, size trades, rank production candidates, or infer
missing trade-plan values.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any

import numpy as np
import pandas as pd


PRIOR_ADVANCE = "Prior Advance Quality"
TREND_SMOOTHNESS = "Trend Smoothness"
DISTRIBUTION = "Distribution / Wide-Bar Penalty"
OVERHEAD_SUPPLY = "Overhead Supply"
CONTRACTION = "Contraction Quality"
SUPPORT_RESPECT = "Support Respect"
RS_PERSISTENCE = "Relative Strength Persistence"

CHART_QUALITY_COMPONENTS = (
    PRIOR_ADVANCE,
    TREND_SMOOTHNESS,
    DISTRIBUTION,
    OVERHEAD_SUPPLY,
    CONTRACTION,
    SUPPORT_RESPECT,
    RS_PERSISTENCE,
)

_COMPONENT_SUFFIXES = (
    "Status",
    "State",
    "Value",
    "Evidence",
    "Warnings",
    "Reason",
)

PHASE3_RESEARCH_FIELDS = tuple(
    f"CQ {component} {suffix}"
    for component in CHART_QUALITY_COMPONENTS
    for suffix in _COMPONENT_SUFFIXES
) + ("Chart Quality Summary",)

_HISTORY_ERROR_ATTR = "phase3_history_error"


@dataclass(frozen=True)
class ChartQualityComponent:
    status: str
    state: str
    value: float | None
    evidence: dict[str, object]
    warnings: tuple[str, ...]
    reason: str


def _round(value: float | None, digits: int = 4) -> float | None:
    if value is None or not math.isfinite(float(value)):
        return None
    return round(float(value), digits)


def _clamp(value: float) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        return 0.0
    return max(0.0, min(100.0, parsed))


def _higher(value: float, low: float, high: float) -> float:
    return _clamp((value - low) * 100.0 / (high - low))


def _lower(value: float, best: float, worst: float) -> float:
    return _clamp((worst - value) * 100.0 / (worst - best))


def _unavailable(status: str, reason: str) -> ChartQualityComponent:
    return ChartQualityComponent(status, status, None, {}, (reason,), reason)


def _prepare_history(history: pd.DataFrame, as_of: object | None) -> pd.DataFrame:
    frame = history.copy(deep=True)
    if as_of is not None:
        try:
            cutoff = pd.Timestamp(as_of)
        except (TypeError, ValueError):
            invalid = frame.iloc[0:0].copy()
            invalid.attrs[_HISTORY_ERROR_ATTR] = "Evaluation timestamp is invalid."
            return invalid
        if pd.isna(cutoff):
            invalid = frame.iloc[0:0].copy()
            invalid.attrs[_HISTORY_ERROR_ATTR] = "Evaluation timestamp is invalid."
            return invalid
        if not isinstance(frame.index, pd.DatetimeIndex):
            if isinstance(frame.index, pd.RangeIndex) or pd.api.types.is_numeric_dtype(
                frame.index.dtype
            ):
                invalid = frame.iloc[0:0].copy()
                invalid.attrs[_HISTORY_ERROR_ATTR] = (
                    "History index is numeric and cannot be used for an as-of cutoff."
                )
                return invalid
            try:
                converted = pd.to_datetime(frame.index, errors="coerce")
            except (TypeError, ValueError, OverflowError):
                converted = pd.DatetimeIndex([pd.NaT] * len(frame))
            if converted.isna().any():
                invalid = frame.iloc[0:0].copy()
                invalid.attrs[_HISTORY_ERROR_ATTR] = (
                    "History index cannot be converted completely to timestamps."
                )
                return invalid
            frame.index = pd.DatetimeIndex(converted)
        if frame.index.hasnans or frame.index.duplicated().any():
            invalid = frame.iloc[0:0].copy()
            invalid.attrs[_HISTORY_ERROR_ATTR] = (
                "History timestamp index contains missing or duplicate values."
            )
            return invalid
        frame = frame.sort_index(kind="stable")
        if frame.index.tz is not None and cutoff.tzinfo is None:
            cutoff = cutoff.tz_localize(frame.index.tz)
        elif frame.index.tz is None and cutoff.tzinfo is not None:
            cutoff = cutoff.tz_localize(None)
        frame = frame.loc[frame.index <= cutoff]
    else:
        try:
            frame = frame.sort_index(kind="stable")
        except TypeError:
            invalid = frame.iloc[0:0].copy()
            invalid.attrs[_HISTORY_ERROR_ATTR] = (
                "History index cannot be sorted safely."
            )
            return invalid
    for column in ("Open", "High", "Low", "Close", "Volume"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").replace(
                [np.inf, -np.inf], np.nan
            )
    return frame


def _maximum_drawdown_pct(close: pd.Series) -> float:
    running_high = close.cummax()
    drawdown = close.div(running_high).sub(1.0)
    return abs(float(drawdown.min())) * 100.0


def _has_invalid_ohlc_geometry(window: pd.DataFrame) -> bool:
    """Return whether a required price window contains impossible OHLC values."""
    columns = ["High", "Low", "Close"]
    if "Open" in window:
        columns.append("Open")
    values = window[columns]
    if values.isna().any().any() or bool((values <= 0).any().any()):
        return True
    invalid = (window["High"] < window["Low"]) | (
        ~window["Close"].between(window["Low"], window["High"], inclusive="both")
    )
    if "Open" in window:
        invalid |= ~window["Open"].between(
            window["Low"], window["High"], inclusive="both"
        )
    return bool(invalid.any())


def _linear_fit(values: pd.Series) -> tuple[float, float]:
    array = np.log(values.to_numpy(dtype=float))
    x = np.arange(len(array), dtype=float)
    slope, intercept = np.polyfit(x, array, 1)
    fitted = slope * x + intercept
    residual = float(np.square(array - fitted).sum())
    total = float(np.square(array - array.mean()).sum())
    r_squared = 1.0 if total <= 1e-15 else max(0.0, 1.0 - residual / total)
    return (math.expm1(float(slope)) * 100.0, r_squared)


def _prior_advance(frame: pd.DataFrame) -> ChartQualityComponent:
    if len(frame) < 71:
        return _unavailable(
            "INSUFFICIENT_HISTORY", "Prior advance requires 71 sessions."
        )
    if "Close" not in frame:
        return _unavailable("MISSING_DATA", "Close history is unavailable.")
    close = frame["Close"].iloc[-71:-10]
    if len(close) != 61 or close.isna().any() or bool((close <= 0).any()):
        return _unavailable("MISSING_DATA", "Prior-advance close window is incomplete.")
    returns = close.pct_change().dropna()
    total_return = float(close.iloc[-1] / close.iloc[0] - 1.0)
    total_path = float(returns.abs().sum())
    efficiency = max(0.0, total_return) / total_path if total_path > 0 else 0.0
    constructive_share = float((returns > 0).mean())
    drawdown = _maximum_drawdown_pct(close)
    median_abs = float(returns.abs().median())
    reversal_threshold = max(0.02, median_abs * 1.5)
    reversal_count = int((returns <= -reversal_threshold).sum())
    positive_progress = returns.clip(lower=0)
    positive_total = float(positive_progress.sum())
    largest_share = (
        float(positive_progress.max()) / positive_total if positive_total > 0 else 0.0
    )
    value = (
        0.25 * _higher(total_return * 100.0, 0.0, 25.0)
        + 0.25 * _higher(efficiency, 0.15, 0.80)
        + 0.20 * _higher(constructive_share, 0.40, 0.70)
        + 0.20 * _lower(drawdown, 5.0, 20.0)
        + 0.10 * _lower(float(reversal_count), 0.0, 5.0)
    )
    warnings: list[str] = []
    if largest_share > 0.50:
        value -= 20.0
        warnings.append("One session supplied more than half of positive progress.")
    value = round(_clamp(value), 2)
    state = (
        "STRONG"
        if value >= 75
        else "CONSTRUCTIVE"
        if value >= 55
        else "MIXED"
        if value >= 35
        else "WEAK"
    )
    evidence = {
        "advance_return_pct": _round(total_return * 100.0),
        "constructive_session_share": _round(constructive_share),
        "large_downside_reversal_count": reversal_count,
        "largest_positive_progress_share": _round(largest_share),
        "maximum_drawdown_pct": _round(drawdown),
        "path_efficiency": _round(efficiency),
        "window_end_offset_sessions": 10,
        "window_returns": 60,
    }
    reason = (
        f"{state}: advance {total_return * 100.0:.2f}%, efficiency {efficiency:.2f}, "
        f"constructive sessions {constructive_share:.0%}, drawdown {drawdown:.2f}%, "
        f"large reversals {reversal_count}, largest positive day share {largest_share:.0%}."
    )
    return ChartQualityComponent(
        "AVAILABLE", state, value, evidence, tuple(warnings), reason
    )


def _trend_smoothness(frame: pd.DataFrame) -> ChartQualityComponent:
    if len(frame) < 41:
        return _unavailable(
            "INSUFFICIENT_HISTORY", "Trend smoothness requires 41 closes."
        )
    if "Close" not in frame:
        return _unavailable("MISSING_DATA", "Close history is unavailable.")
    close = frame["Close"].iloc[-41:]
    if close.isna().any() or bool((close <= 0).any()):
        return _unavailable("MISSING_DATA", "Trend close window is incomplete.")
    returns = close.pct_change().dropna()
    net_return = float(close.iloc[-1] / close.iloc[0] - 1.0)
    total_path = float(returns.abs().sum())
    efficiency = max(0.0, net_return) / total_path if total_path > 0 else 0.0
    positive_share = float((returns > 0).mean())
    slope_pct, r_squared = _linear_fit(close)
    median_abs = float(returns.abs().median())
    threshold = max(0.01, median_abs * 1.5)
    prior = returns.shift(1)
    reversals = (returns * prior < 0) & (returns.abs() >= threshold)
    reversal_count = int(reversals.sum())
    value = round(
        _clamp(
            0.25 * _higher(net_return * 100.0, 0.0, 10.0)
            + 0.25 * _higher(efficiency, 0.15, 0.80)
            + 0.15 * _higher(positive_share, 0.45, 0.65)
            + 0.20 * _clamp(r_squared * 100.0)
            + 0.15 * _lower(float(reversal_count), 0.0, 8.0)
        ),
        2,
    )
    if net_return <= -0.02:
        state = "WEAK_DOWNTREND"
    elif abs(net_return) < 0.02 or slope_pct <= 0:
        state = "FLAT_OR_DIRECTIONLESS"
    elif reversal_count >= 6 or value < 40:
        state = "ERRATIC"
    elif value >= 75 and net_return >= 0.05:
        state = "SMOOTH_UPTREND"
    else:
        state = "ORDERLY_UPTREND"
    evidence = {
        "large_reversal_count": reversal_count,
        "net_return_pct": _round(net_return * 100.0),
        "path_efficiency": _round(efficiency),
        "positive_session_share": _round(positive_share),
        "regression_r_squared": _round(r_squared),
        "regression_slope_pct_per_session": _round(slope_pct),
        "window_returns": 40,
    }
    reason = (
        f"{state}: net {net_return * 100.0:.2f}%, efficiency {efficiency:.2f}, "
        f"fit {r_squared:.2f}, slope {slope_pct:.3f}%/session, "
        f"large reversals {reversal_count}."
    )
    return ChartQualityComponent("AVAILABLE", state, value, evidence, (), reason)


def _distribution(frame: pd.DataFrame) -> ChartQualityComponent:
    required = {"High", "Low", "Close", "Volume"}
    if len(frame) < 51:
        return _unavailable(
            "INSUFFICIENT_HISTORY", "Distribution analysis requires 51 sessions."
        )
    if not required.issubset(frame.columns):
        return _unavailable("MISSING_DATA", "Required OHLCV history is unavailable.")
    window = frame.iloc[-51:]
    if window[list(required)].isna().any().any():
        return _unavailable("MISSING_DATA", "Distribution OHLCV window is incomplete.")
    if _has_invalid_ohlc_geometry(window):
        return _unavailable("MISSING_DATA", "Distribution price geometry is invalid.")
    if bool((window["Volume"] < 0).any()):
        return _unavailable("MISSING_DATA", "Distribution volume is invalid.")
    previous_close = frame["Close"].shift(1)
    true_range = pd.concat(
        [
            frame["High"] - frame["Low"],
            (frame["High"] - previous_close).abs(),
            (frame["Low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1, skipna=False)
    wide_down = high_volume_down = weak_close_down = event_count = 0
    for position in range(len(frame) - 20, len(frame)):
        baseline_tr = true_range.iloc[position - 20 : position]
        baseline_volume = frame["Volume"].iloc[position - 20 : position]
        if baseline_tr.isna().any() or baseline_volume.isna().any():
            return _unavailable(
                "MISSING_DATA", "Distribution baseline window is incomplete."
            )
        with np.errstate(over="ignore", invalid="ignore"):
            baseline_volume_mean = float(baseline_volume.mean())
        if not math.isfinite(baseline_volume_mean) or baseline_volume_mean <= 0:
            return _unavailable(
                "MISSING_DATA", "Distribution volume baseline is not positive."
            )
        down = bool(frame["Close"].iloc[position] < frame["Close"].iloc[position - 1])
        if not down:
            continue
        wide = bool(true_range.iloc[position] >= 1.5 * baseline_tr.median())
        high_volume = bool(frame["Volume"].iloc[position] >= 1.5 * baseline_volume_mean)
        bar_range = float(frame["High"].iloc[position] - frame["Low"].iloc[position])
        weak_close = bool(
            bar_range > 0
            and (
                (frame["Close"].iloc[position] - frame["Low"].iloc[position])
                / bar_range
            )
            <= 0.25
        )
        wide_down += int(wide)
        high_volume_down += int(high_volume)
        weak_close_down += int(weak_close)
        event_count += int(sum((wide, high_volume, weak_close)) >= 2)
    penalty = min(
        100.0,
        event_count * 20.0
        + max(0, wide_down - 1) * 5.0
        + max(0, high_volume_down - 1) * 5.0,
    )
    state = (
        "NONE"
        if penalty == 0
        else "LIGHT"
        if penalty <= 25
        else "MODERATE"
        if penalty <= 55
        else "HEAVY"
    )
    evidence = {
        "distribution_event_count": event_count,
        "high_volume_down_count": high_volume_down,
        "measured_sessions": 20,
        "weak_close_down_count": weak_close_down,
        "wide_range_down_count": wide_down,
    }
    reason = (
        f"{state}: {event_count} composite distribution events, {wide_down} wide-range "
        f"down bars, {high_volume_down} high-volume down bars, and "
        f"{weak_close_down} weak closes in 20 sessions."
    )
    return ChartQualityComponent(
        "AVAILABLE",
        state,
        round(penalty, 2),
        evidence,
        ("Penalty direction: higher is worse.",),
        reason,
    )


def _overhead_supply(frame: pd.DataFrame) -> ChartQualityComponent:
    required = {"High", "Low", "Close"}
    if len(frame) < 61:
        return _unavailable(
            "INSUFFICIENT_HISTORY", "Overhead supply requires 61 price sessions."
        )
    if not required.issubset(frame.columns):
        return _unavailable("MISSING_DATA", "Required price history is unavailable.")
    window = frame.iloc[-61:]
    if window[list(required)].isna().any().any():
        return _unavailable(
            "MISSING_DATA", "Overhead-supply price window is incomplete."
        )
    if _has_invalid_ohlc_geometry(window):
        return _unavailable(
            "MISSING_DATA", "Overhead-supply price geometry is invalid."
        )
    current = float(window["Close"].iloc[-1])
    if current <= 0:
        return _unavailable("MISSING_DATA", "Current close is invalid.")
    prior = window.iloc[:-1]
    overhead_highs = prior.loc[prior["High"] >= current, "High"]
    if overhead_highs.empty:
        evidence = {
            "congestion_close_share": 0.0,
            "congestion_range_share": 0.0,
            "nearest_overhead_high_distance_pct": None,
            "prior_sessions": 60,
        }
        return ChartQualityComponent(
            "AVAILABLE",
            "NO_OBSERVED_OVERHEAD",
            0.0,
            evidence,
            ("Price congestion only; no volume-profile evidence is used.",),
            "NO_OBSERVED_OVERHEAD: no prior 60-session high is at or above the current close.",
        )
    nearest_distance = float(overhead_highs.min() / current - 1.0) * 100.0
    upper = current * 1.10
    range_share = float(((prior["High"] >= current) & (prior["Low"] <= upper)).mean())
    close_share = float(prior["Close"].between(current, upper, inclusive="both").mean())
    density = (range_share + close_share) / 2.0
    value = round(
        0.50 * _lower(nearest_distance, 0.0, 10.0) + 0.50 * _higher(density, 0.0, 0.30),
        2,
    )
    state = "HEAVY" if value >= 70 else "MODERATE" if value >= 35 else "LOW"
    evidence = {
        "congestion_close_share": _round(close_share),
        "congestion_range_share": _round(range_share),
        "nearest_overhead_high_distance_pct": _round(nearest_distance),
        "prior_sessions": 60,
    }
    reason = (
        f"{state}: nearest prior high {nearest_distance:.2f}% above price; "
        f"range congestion {range_share:.0%} and close congestion {close_share:.0%}."
    )
    return ChartQualityComponent(
        "AVAILABLE",
        state,
        value,
        evidence,
        ("Price congestion only; no volume-profile evidence is used.",),
        reason,
    )


def _range_pct(window: pd.DataFrame) -> float:
    mean_close = float(window["Close"].mean())
    return float((window["High"].max() - window["Low"].min()) / mean_close * 100.0)


def _contraction(frame: pd.DataFrame) -> ChartQualityComponent:
    required = {"High", "Low", "Close"}
    if len(frame) < 61:
        return _unavailable(
            "INSUFFICIENT_HISTORY", "Contraction quality requires 61 price sessions."
        )
    if not required.issubset(frame.columns):
        return _unavailable("MISSING_DATA", "Required price history is unavailable.")
    price = frame.iloc[-61:]
    if price[list(required)].isna().any().any() or bool((price["Close"] <= 0).any()):
        return _unavailable("MISSING_DATA", "Contraction price window is incomplete.")
    if _has_invalid_ohlc_geometry(price):
        return _unavailable("MISSING_DATA", "Contraction price geometry is invalid.")
    range_10 = _range_pct(price.iloc[-10:])
    range_20 = _range_pct(price.iloc[-20:])
    range_ratio = range_10 / range_20 if range_20 > 0 else math.nan
    daily_range_pct = (price["High"] - price["Low"]).div(price["Close"]).mul(100)
    adr20 = float(daily_range_pct.iloc[-20:].mean())
    adr60 = float(daily_range_pct.iloc[-60:].mean())
    adr_ratio = adr20 / adr60 if adr60 > 0 else math.nan
    block_ranges = [
        _range_pct(price.iloc[-30:-20]),
        _range_pct(price.iloc[-20:-10]),
        _range_pct(price.iloc[-10:]),
    ]
    sequential = int(block_ranges[1] < block_ranges[0]) + int(
        block_ranges[2] < block_ranges[1]
    )
    volume_ratio: float | None = None
    volume_complete = False
    if "Volume" in frame:
        volume_window = frame["Volume"].iloc[-25:]
        if not volume_window.isna().any() and not (volume_window < 0).any():
            with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
                prior_volume = float(volume_window.iloc[:-5].mean())
                recent_volume = float(volume_window.iloc[-5:].mean())
                candidate_ratio = float(np.divide(recent_volume, prior_volume))
            if (
                math.isfinite(prior_volume)
                and prior_volume > 0
                and math.isfinite(recent_volume)
                and math.isfinite(candidate_ratio)
            ):
                volume_ratio = candidate_ratio
                volume_complete = True
    evidence = {
        "adr20_pct": _round(adr20),
        "adr20_to_adr60_ratio": _round(adr_ratio),
        "adr60_pct": _round(adr60),
        "range_10_pct": _round(range_10),
        "range_10_to_20_ratio": _round(range_ratio),
        "range_20_pct": _round(range_20),
        "sequential_contraction_count": sequential,
        "volume_dry_up_ratio": _round(volume_ratio),
    }
    if (
        range_20 <= 0
        or adr60 <= 0
        or not math.isfinite(range_ratio)
        or not math.isfinite(adr_ratio)
    ):
        reason = (
            "MISSING_DATA: contraction ratios are undefined because the 20-session "
            f"range ({range_20:.2f}) or ADR60 ({adr60:.2f}) baseline is not positive."
        )
        return ChartQualityComponent(
            "MISSING_DATA",
            "MISSING_DATA",
            None,
            evidence,
            ("Undefined contraction ratios receive no score credit.",),
            reason,
        )
    price_contraction = range_ratio <= 0.80 and adr_ratio <= 0.90
    expanding = range_ratio > 1.10 or adr_ratio > 1.10
    if not volume_complete or volume_ratio is None:
        state = (
            "PRICE_CONTRACTION_VOLUME_UNKNOWN"
            if price_contraction
            else "EXPANDING"
            if expanding
            else "WEAK_OR_NONE"
        )
        reason = (
            f"{state}: range ratio {range_ratio:.2f}, ADR ratio {adr_ratio:.2f}; "
            "volume evidence unavailable."
        )
        return ChartQualityComponent(
            "MISSING_DATA",
            state,
            None,
            evidence,
            ("Missing or invalid volume is not treated as volume dry-up.",),
            reason,
        )
    volume_contraction = volume_ratio <= 0.80
    value = round(
        _clamp(
            0.30 * _lower(range_ratio, 0.50, 1.10)
            + 0.30 * _lower(adr_ratio, 0.50, 1.10)
            + 0.30 * _lower(volume_ratio, 0.50, 1.20)
            + 0.10 * (sequential / 2.0 * 100.0)
        ),
        2,
    )
    if expanding:
        state = "EXPANDING"
    elif price_contraction and volume_contraction and sequential >= 1:
        state = "STRONG_MULTI_DIMENSIONAL"
    elif price_contraction:
        state = "PRICE_CONTRACTION_ONLY"
    elif volume_contraction:
        state = "VOLUME_DRY_UP_ONLY"
    else:
        state = "WEAK_OR_NONE"
    reason = (
        f"{state}: 10D/20D range {range_ratio:.2f}, ADR20/ADR60 {adr_ratio:.2f}, "
        f"recent/prior volume {volume_ratio:.2f}, sequential contractions {sequential}/2."
    )
    return ChartQualityComponent("AVAILABLE", state, value, evidence, (), reason)


def _atr20(frame: pd.DataFrame) -> float | None:
    if len(frame) < 21:
        return None
    window = frame.iloc[-21:]
    if window[["High", "Low", "Close"]].isna().any().any():
        return None
    previous = frame["Close"].shift(1)
    true_range = pd.concat(
        [
            frame["High"] - frame["Low"],
            (frame["High"] - previous).abs(),
            (frame["Low"] - previous).abs(),
        ],
        axis=1,
    ).max(axis=1, skipna=False)
    value = float(true_range.iloc[-20:].mean())
    return value if math.isfinite(value) and value > 0 else None


def _support_respect(frame: pd.DataFrame, pivot: float | None) -> ChartQualityComponent:
    required = {"High", "Low", "Close"}
    if len(frame) < 60:
        return _unavailable(
            "INSUFFICIENT_HISTORY", "Support respect requires 60 sessions."
        )
    if not required.issubset(frame.columns):
        return _unavailable("MISSING_DATA", "Required support history is unavailable.")
    if frame[list(required)].iloc[-60:].isna().any().any():
        return _unavailable("MISSING_DATA", "Support interaction window is incomplete.")
    if _has_invalid_ohlc_geometry(frame.iloc[-60:]):
        return _unavailable("MISSING_DATA", "Support price geometry is invalid.")
    close = frame["Close"]
    atr = _atr20(frame)
    current = float(close.iloc[-1])
    if atr is None or current <= 0:
        return _unavailable("MISSING_DATA", "ATR or current close is unavailable.")
    series_by_name: dict[str, pd.Series] = {
        "EMA20": close.ewm(span=20, adjust=False, min_periods=20).mean(),
        "EMA10": close.ewm(span=10, adjust=False, min_periods=10).mean(),
        "MA50": close.rolling(50, min_periods=50).mean(),
    }
    if pivot is not None:
        try:
            pivot_value = float(pivot)
        except (TypeError, ValueError):
            pivot_value = math.nan
        if math.isfinite(pivot_value) and pivot_value > 0:
            series_by_name["PIVOT"] = pd.Series(pivot_value, index=frame.index)
    priority = {
        name: index for index, name in enumerate(("EMA20", "EMA10", "MA50", "PIVOT"))
    }
    references: list[tuple[float, int, str, pd.Series]] = []
    for name, series in series_by_name.items():
        value = _round(float(series.iloc[-1])) if pd.notna(series.iloc[-1]) else None
        if value is None:
            continue
        distance = abs(current - value) / atr
        if distance <= 3.0:
            references.append((distance, priority[name], name, series))
    if not references:
        return ChartQualityComponent(
            "NOT_APPLICABLE",
            "NOT_APPLICABLE",
            None,
            {"nearest_reference_within_atr": None},
            ("No support reference is within three ATR.",),
            "NOT_APPLICABLE: no observable EMA, MA, or pivot is within three ATR.",
        )
    distance, _, name, support = min(references, key=lambda item: (item[0], item[1]))
    recent = frame.iloc[-15:]
    support_recent = support.iloc[-15:]
    tests = holds = reclaims = breaches = successful = 0
    prior_close = close.shift(1).iloc[-15:]
    prior_support = support.shift(1).iloc[-15:]
    for position in range(len(recent)):
        reference = float(support_recent.iloc[position])
        tested = bool(
            recent["Low"].iloc[position] <= reference * 1.01
            and recent["High"].iloc[position] >= reference * 0.99
        )
        held = bool(tested and recent["Close"].iloc[position] >= reference)
        reclaimed = bool(
            pd.notna(prior_close.iloc[position])
            and pd.notna(prior_support.iloc[position])
            and prior_close.iloc[position] < prior_support.iloc[position]
            and recent["Close"].iloc[position] >= reference
        )
        breached = bool(recent["Close"].iloc[position] < reference * 0.98)
        tests += int(tested)
        holds += int(held)
        reclaims += int(reclaimed)
        breaches += int(breached)
        successful += int(held or reclaimed)
    latest_broken = bool(current < float(support.iloc[-1]) * 0.98)
    if breaches >= 2 or latest_broken:
        state = "BROKEN"
    elif successful >= 2 and breaches == 0:
        state = "STRONG"
    elif successful >= 1 and breaches <= 1:
        state = "CONSTRUCTIVE"
    else:
        state = "AMBIGUOUS_PROXIMITY"
    interaction_score = min(100.0, successful / 3.0 * 100.0)
    breach_control = _lower(float(breaches), 0.0, 3.0)
    value = round(_clamp(0.70 * interaction_score + 0.30 * breach_control), 2)
    evidence = {
        "destructive_breach_count": breaches,
        "distance_atr": _round(distance),
        "hold_count": holds,
        "reclaim_count": reclaims,
        "reference_name": name,
        "reference_price": _round(float(support.iloc[-1])),
        "successful_interactions": successful,
        "test_count": tests,
        "window_sessions": 15,
    }
    reason = (
        f"{state}: {name} at {float(support.iloc[-1]):.2f}, distance {distance:.2f} ATR; "
        f"tests {tests}, holds {holds}, reclaims {reclaims}, breaches {breaches}."
    )
    return ChartQualityComponent("AVAILABLE", state, value, evidence, (), reason)


def _rs_persistence(
    frame: pd.DataFrame,
    benchmark: pd.DataFrame | None,
    as_of: object | None,
    recent_rs_score: float | None,
) -> ChartQualityComponent:
    if benchmark is None or benchmark.empty or "Close" not in benchmark:
        return _unavailable("MISSING_DATA", "SPY benchmark history is unavailable.")
    try:
        score = float(recent_rs_score) if recent_rs_score is not None else math.nan
    except (TypeError, ValueError):
        score = math.nan
    if not math.isfinite(score):
        return _unavailable("MISSING_DATA", "Current Recent RS score is unavailable.")
    benchmark_frame = _prepare_history(benchmark, as_of)
    benchmark_error = benchmark_frame.attrs.get(_HISTORY_ERROR_ATTR)
    if benchmark_error:
        return _unavailable(
            "MISSING_DATA", f"SPY benchmark history is invalid: {benchmark_error}"
        )
    if "Close" not in frame:
        return _unavailable("MISSING_DATA", "Stock close history is unavailable.")
    aligned = pd.concat(
        [frame["Close"].rename("stock"), benchmark_frame["Close"].rename("benchmark")],
        axis=1,
        join="inner",
    ).iloc[-31:]
    if len(aligned) < 31:
        return _unavailable(
            "INSUFFICIENT_HISTORY", "RS persistence requires 31 aligned sessions."
        )
    if aligned.isna().any().any() or bool((aligned <= 0).any().any()):
        return _unavailable("MISSING_DATA", "Aligned stock/SPY history is incomplete.")
    relative = aligned["stock"].div(aligned["benchmark"])
    daily = relative.pct_change().dropna()
    recent_daily = daily.iloc[-20:]
    relative_return = float(relative.iloc[-1] / relative.iloc[-21] - 1.0)
    slope_pct, r_squared = _linear_fit(relative.iloc[-21:])
    improving_share = float((recent_daily > 0).mean())
    baseline = relative.rolling(10, min_periods=10).mean()
    above_baseline = float((relative.iloc[-20:] > baseline.iloc[-20:]).mean())
    recent_five = float(relative.iloc[-1] / relative.iloc[-6] - 1.0)
    prior_fifteen = float(relative.iloc[-6] / relative.iloc[-21] - 1.0)
    positive_progress = recent_daily.clip(lower=0)
    positive_total = float(positive_progress.sum())
    latest_share = (
        float(max(0.0, recent_daily.iloc[-1])) / positive_total
        if positive_total > 0
        else 0.0
    )
    value = (
        0.20 * _clamp(score)
        + 0.20 * _higher(relative_return * 100.0, 0.0, 10.0)
        + 0.25 * _higher(improving_share, 0.40, 0.70)
        + 0.20 * _higher(above_baseline, 0.40, 0.80)
        + 0.15 * _clamp(r_squared * 100.0)
    )
    warnings: list[str] = []
    if latest_share > 0.50:
        value -= 20.0
        warnings.append(
            "Latest session supplied more than half of positive relative progress."
        )
    value = round(_clamp(value), 2)
    recent_rate = recent_five / 5.0
    prior_rate = prior_fifteen / 15.0
    if latest_share > 0.50:
        state = "INCONSISTENT"
    elif score >= 70 and (recent_five < 0 or slope_pct <= 0):
        state = "STRONG_BUT_DETERIORATING"
    elif (
        relative_return > 0
        and slope_pct > 0
        and recent_rate > max(0.0, prior_rate) * 1.25
    ):
        state = "IMPROVING"
    elif (
        score >= 70
        and relative_return > 0
        and improving_share >= 0.55
        and above_baseline >= 0.65
        and slope_pct > 0
    ):
        state = "PERSISTENTLY_STRONG"
    elif score < 40 and relative_return <= 0:
        state = "WEAK"
    else:
        state = "INCONSISTENT"
    evidence = {
        "above_10_session_baseline_share": _round(above_baseline),
        "current_recent_rs_score": _round(score),
        "latest_day_positive_progress_share": _round(latest_share),
        "positive_relative_session_share": _round(improving_share),
        "prior_15_session_relative_return_pct": _round(prior_fifteen * 100.0),
        "recent_5_session_relative_return_pct": _round(recent_five * 100.0),
        "relative_line_r_squared": _round(r_squared),
        "relative_line_slope_pct_per_session": _round(slope_pct),
        "relative_return_20d_pct": _round(relative_return * 100.0),
    }
    reason = (
        f"{state}: current Recent RS {score:.1f}; 20D relative return "
        f"{relative_return * 100.0:.2f}%, positive relative sessions "
        f"{improving_share:.0%}, above baseline {above_baseline:.0%}, "
        f"latest-day share {latest_share:.0%}."
    )
    return ChartQualityComponent(
        "AVAILABLE", state, value, evidence, tuple(warnings), reason
    )


def calculate_chart_quality_components(
    history: pd.DataFrame,
    *,
    benchmark: pd.DataFrame | None = None,
    as_of: object | None = None,
    recent_rs_score: float | None = None,
    pivot: float | None = None,
) -> dict[str, ChartQualityComponent]:
    """Return all seven independent Phase 3 components."""
    frame = _prepare_history(history, as_of)
    history_error = frame.attrs.get(_HISTORY_ERROR_ATTR)
    if history_error:
        unavailable = _unavailable(
            "MISSING_DATA", f"Stock history is invalid: {history_error}"
        )
        return {component: unavailable for component in CHART_QUALITY_COMPONENTS}
    return {
        PRIOR_ADVANCE: _prior_advance(frame),
        TREND_SMOOTHNESS: _trend_smoothness(frame),
        DISTRIBUTION: _distribution(frame),
        OVERHEAD_SUPPLY: _overhead_supply(frame),
        CONTRACTION: _contraction(frame),
        SUPPORT_RESPECT: _support_respect(frame, pivot),
        RS_PERSISTENCE: _rs_persistence(frame, benchmark, as_of, recent_rs_score),
    }


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def calculate_chart_quality_fields(
    history: pd.DataFrame,
    *,
    benchmark: pd.DataFrame | None = None,
    as_of: object | None = None,
    recent_rs_score: float | None = None,
    pivot: float | None = None,
) -> dict[str, object]:
    """Flatten components into deterministic report-friendly fields."""
    components = calculate_chart_quality_components(
        history,
        benchmark=benchmark,
        as_of=as_of,
        recent_rs_score=recent_rs_score,
        pivot=pivot,
    )
    fields: dict[str, object] = {}
    summary_parts = ["RESEARCH_ONLY"]
    for name in CHART_QUALITY_COMPONENTS:
        result = components[name]
        prefix = f"CQ {name}"
        fields[f"{prefix} Status"] = result.status
        fields[f"{prefix} State"] = result.state
        fields[f"{prefix} Value"] = result.value
        fields[f"{prefix} Evidence"] = json.dumps(
            _json_value(result.evidence), sort_keys=True, separators=(",", ":")
        )
        fields[f"{prefix} Warnings"] = "; ".join(result.warnings)
        fields[f"{prefix} Reason"] = result.reason
        summary_parts.append(f"{name}: {result.state}")
    fields["Chart Quality Summary"] = "; ".join(summary_parts)
    return fields
