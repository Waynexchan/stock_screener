"""Point-in-time SPY-only entry and heat gates for research simulations."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd


def spy_trend_features(benchmark: pd.DataFrame) -> pd.DataFrame:
    """Calculate causal SPY trend features available after each session close."""

    required = {"Close"}
    missing = required.difference(benchmark.columns)
    if missing:
        raise ValueError(f"benchmark missing market-gate columns: {sorted(missing)}")
    frame = benchmark.copy().sort_index()
    frame.index = pd.to_datetime(frame.index)
    if frame.index.has_duplicates:
        raise ValueError("benchmark has duplicate market-gate sessions")
    close = pd.to_numeric(frame["Close"], errors="coerce")
    result = pd.DataFrame(index=frame.index)
    result["close"] = close
    result["ema20"] = close.ewm(span=20, adjust=False).mean()
    result["sma50"] = close.rolling(50, min_periods=50).mean()
    result["sma200"] = close.rolling(200, min_periods=200).mean()
    return result


def market_limits_for_signal_dates(
    benchmark: pd.DataFrame,
    signal_dates: Iterable[str],
    specification: dict[str, Any],
) -> tuple[dict[str, float], dict[str, str]]:
    """Return fail-closed entry heat and state from each signal-date SPY close."""

    features = spy_trend_features(benchmark)
    limits: dict[str, float] = {}
    states: dict[str, str] = {}
    for date_text in sorted(set(signal_dates)):
        date = pd.Timestamp(date_text)
        if date not in features.index:
            raise ValueError(f"SPY market-gate data unavailable on {date_text}")
        row = features.loc[date]
        policy_type = str(specification["type"])
        if policy_type == "FIXED_HEAT":
            limit = float(specification["maximum_heat_r"])
            state = "NO_GATE"
        else:
            required = ["close"]
            if policy_type == "BINARY_GATE":
                gate_id = str(specification["id"])
                if gate_id == "spy_above_sma50":
                    reference_name = "sma50"
                elif gate_id == "spy_above_sma200":
                    reference_name = "sma200"
                else:
                    raise ValueError(f"unsupported binary market gate: {gate_id}")
                required.append(reference_name)
                values = [float(row[name]) for name in required]
                if not all(np.isfinite(value) and value > 0 for value in values):
                    raise ValueError(
                        f"SPY market-gate indicators unavailable on {date_text}"
                    )
                allowed = float(row["close"]) > float(row[reference_name])
                limit = float(
                    specification["allowed_heat_r"]
                    if allowed
                    else specification["blocked_heat_r"]
                )
                state = "ALLOWED" if allowed else "BLOCKED"
            elif policy_type == "THREE_STATE_HEAT":
                required += ["ema20", "sma50", "sma200"]
                values = [float(row[name]) for name in required]
                if not all(np.isfinite(value) and value > 0 for value in values):
                    raise ValueError(
                        f"SPY market-gate indicators unavailable on {date_text}"
                    )
                close = float(row["close"])
                normal = all(
                    close > float(row[name]) for name in ("ema20", "sma50", "sma200")
                )
                if normal:
                    limit = float(specification["normal_heat_r"])
                    state = "NORMAL"
                elif close > float(row["sma200"]):
                    limit = float(specification["reduced_heat_r"])
                    state = "REDUCED"
                else:
                    limit = float(specification["blocked_heat_r"])
                    state = "BLOCKED"
            else:
                raise ValueError(f"unsupported market-gate type: {policy_type}")
        if not np.isfinite(limit) or limit < 0:
            raise ValueError(f"invalid market heat limit on {date_text}")
        limits[date_text] = limit
        states[date_text] = state
    return limits, states
