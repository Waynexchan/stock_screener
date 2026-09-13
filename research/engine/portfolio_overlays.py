"""Causal portfolio-level exposure overlays for research simulations."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .models import SimulatedTrade


@dataclass(frozen=True)
class AllocatedTrade:
    trade: SimulatedTrade
    allocated_r: float


def policy_limits(
    specification: dict[str, Any],
    *,
    realised_profit_high_water_r: float,
    current_drawdown_r: float,
    dynamic_heat_r: float | None = None,
) -> tuple[float, float, str]:
    """Return causal maximum heat, new-trade risk and policy mode."""

    policy_type = str(specification["type"])
    if policy_type == "FIXED":
        return (
            float(specification["maximum_heat_r"]),
            float(specification["risk_per_trade_r"]),
            "FIXED",
        )
    if policy_type == "LAST_EXIT_BATCH":
        if dynamic_heat_r is None:
            raise ValueError("LAST_EXIT_BATCH requires dynamic heat state")
        initial_heat = float(specification["initial_heat_r"])
        profitable_heat = float(specification["profitable_heat_r"])
        if dynamic_heat_r not in {initial_heat, profitable_heat}:
            raise ValueError("invalid LAST_EXIT_BATCH dynamic heat state")
        mode = "WIN_TO_3" if dynamic_heat_r == profitable_heat else "BASE_2"
        return dynamic_heat_r, float(specification["risk_per_trade_r"]), mode
    earned_heat = float(specification.get("initial_heat_r", np.inf))
    if policy_type in {"EARNED", "EARNED_DRAWDOWN"}:
        for threshold, unlocked_heat in zip(
            specification["unlock_profit_r"],
            specification["unlocked_heat_r"],
            strict=True,
        ):
            if realised_profit_high_water_r >= float(threshold):
                earned_heat = float(unlocked_heat)
        if policy_type == "EARNED":
            return earned_heat, float(specification["risk_per_trade_r"]), "EARNED"
    if policy_type not in {"DRAWDOWN", "EARNED_DRAWDOWN"}:
        raise ValueError(f"unsupported portfolio policy type: {policy_type}")
    if current_drawdown_r >= float(specification["stop_at_r"]):
        drawdown_heat, risk_r, mode = 0.0, 0.0, "STOP_NEW_RISK"
    elif current_drawdown_r >= float(specification["defensive_at_r"]):
        drawdown_heat = float(specification["defensive_heat_r"])
        risk_r = float(specification["reduced_risk_per_trade_r"])
        mode = "DEFENSIVE"
    elif current_drawdown_r >= float(specification["reduced_at_r"]):
        drawdown_heat = float(specification["reduced_heat_r"])
        risk_r = float(specification["reduced_risk_per_trade_r"])
        mode = "REDUCED"
    else:
        drawdown_heat = float(specification["normal_heat_r"])
        risk_r = float(specification["normal_risk_per_trade_r"])
        mode = "NORMAL"
    return min(earned_heat, drawdown_heat), risk_r, mode


def _price_as_of(
    history: pd.DataFrame, session: pd.Timestamp, preferred_column: str
) -> float | None:
    frame = history
    index = pd.DatetimeIndex(frame.index)
    position = index.searchsorted(session, side="right") - 1
    if position < 0:
        return None
    exact = index[position] == session
    column = preferred_column if exact else "Close"
    value = pd.to_numeric(frame.iloc[position].get(column), errors="coerce")
    return float(value) if np.isfinite(value) and float(value) > 0 else None


def _marked_pnl_r(
    allocated: AllocatedTrade,
    histories: dict[str, pd.DataFrame],
    session: pd.Timestamp,
    column: str,
) -> float | None:
    trade = allocated.trade
    history = histories.get(trade.ticker)
    if history is None:
        return None
    price = _price_as_of(history, session, column)
    if price is None or trade.initial_risk_per_share <= 0:
        return None
    full_r = (price - trade.entry) / trade.initial_risk_per_share
    return full_r * allocated.allocated_r


def simulate_portfolio_overlay(
    trades: list[SimulatedTrade],
    histories: dict[str, pd.DataFrame],
    sessions: pd.DatetimeIndex,
    specification: dict[str, Any],
    *,
    starting_equity_r: float = 100.0,
    maximum_positions: int = 4,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    """Allocate trades and calculate a daily mark-to-market equity curve."""

    if starting_equity_r <= 0 or maximum_positions <= 0:
        raise ValueError("starting equity and maximum positions must be positive")
    candidates: dict[pd.Timestamp, list[SimulatedTrade]] = defaultdict(list)
    for trade in sorted(
        trades, key=lambda item: (item.entry_date, item.signal_date, item.ticker)
    ):
        candidates[pd.Timestamp(trade.entry_date)].append(trade)
    if not candidates:
        return ({"accepted_trade_count": 0}, pd.DataFrame(), pd.DataFrame())
    first_entry = min(candidates)
    final_exit = max(pd.Timestamp(trade.exit_date) for trade in trades)
    calendar = sessions[(sessions >= first_entry) & (sessions <= final_exit)]
    if calendar.empty:
        raise ValueError("benchmark sessions do not cover the candidate trade period")
    open_trades: list[AllocatedTrade] = []
    accepted: list[AllocatedTrade] = []
    rejection_reasons: Counter[str] = Counter()
    curve_rows: list[dict[str, Any]] = []
    realised_r = 0.0
    realised_profit_high_water_r = 0.0
    dynamic_heat_r = (
        float(specification["initial_heat_r"])
        if specification["type"] == "LAST_EXIT_BATCH"
        else None
    )
    exposure_expansion_count = 0
    exposure_contraction_count = 0
    equity_high_water_r = 0.0
    missing_mark_count = 0
    for session in calendar:
        opening_marks = [
            _marked_pnl_r(item, histories, session, "Open") for item in open_trades
        ]
        missing_mark_count += sum(value is None for value in opening_marks)
        opening_equity_r = realised_r + sum(
            value for value in opening_marks if value is not None
        )
        equity_high_water_r = max(equity_high_water_r, opening_equity_r)
        current_drawdown_r = max(0.0, equity_high_water_r - opening_equity_r)
        opening_high_water_equity_r = starting_equity_r + equity_high_water_r
        opening_drawdown_pct = (
            current_drawdown_r / opening_high_water_equity_r * 100
            if opening_high_water_equity_r > 0
            else float("nan")
        )
        maximum_heat_r, risk_per_trade_r, mode = policy_limits(
            specification,
            realised_profit_high_water_r=realised_profit_high_water_r,
            current_drawdown_r=current_drawdown_r,
            dynamic_heat_r=dynamic_heat_r,
        )
        for trade in candidates.get(pd.Timestamp(session), []):
            current_heat = sum(item.allocated_r for item in open_trades)
            if risk_per_trade_r <= 0:
                rejection_reasons["STOP_NEW_RISK"] += 1
                continue
            if any(item.trade.ticker == trade.ticker for item in open_trades):
                rejection_reasons["SAME_TICKER"] += 1
                continue
            if len(open_trades) >= maximum_positions:
                rejection_reasons["MAX_POSITIONS"] += 1
                continue
            if current_heat + risk_per_trade_r > maximum_heat_r + 1e-12:
                rejection_reasons["MAX_HEAT"] += 1
                continue
            allocated = AllocatedTrade(trade=trade, allocated_r=risk_per_trade_r)
            open_trades.append(allocated)
            accepted.append(allocated)
        peak_heat_r = sum(item.allocated_r for item in open_trades)
        peak_positions = len(open_trades)
        exiting = [
            item
            for item in open_trades
            if pd.Timestamp(item.trade.exit_date) == session
        ]
        exit_batch_r = sum(item.trade.realised_r * item.allocated_r for item in exiting)
        realised_r += exit_batch_r
        realised_profit_high_water_r = max(realised_profit_high_water_r, realised_r)
        if specification["type"] == "LAST_EXIT_BATCH" and exiting:
            assert dynamic_heat_r is not None
            next_heat = float(
                specification[
                    "profitable_heat_r" if exit_batch_r > 0 else "non_positive_heat_r"
                ]
            )
            if next_heat > dynamic_heat_r:
                exposure_expansion_count += 1
            elif next_heat < dynamic_heat_r:
                exposure_contraction_count += 1
            dynamic_heat_r = next_heat
        open_trades = [item for item in open_trades if item not in exiting]
        closing_marks = [
            _marked_pnl_r(item, histories, session, "Close") for item in open_trades
        ]
        missing_mark_count += sum(value is None for value in closing_marks)
        closing_equity_r = realised_r + sum(
            value for value in closing_marks if value is not None
        )
        equity_high_water_r = max(equity_high_water_r, closing_equity_r)
        drawdown_r = max(0.0, equity_high_water_r - closing_equity_r)
        equity_r = starting_equity_r + closing_equity_r
        high_water_equity_r = starting_equity_r + equity_high_water_r
        drawdown_pct = (
            drawdown_r / high_water_equity_r * 100
            if high_water_equity_r > 0
            else float("nan")
        )
        daily_drawdown_r = max(current_drawdown_r, drawdown_r)
        daily_drawdown_pct = max(opening_drawdown_pct, drawdown_pct)
        curve_rows.append(
            {
                "date": session.date().isoformat(),
                "equity_r": equity_r,
                "portfolio_pnl_r": closing_equity_r,
                "drawdown_r": daily_drawdown_r,
                "drawdown_pct": daily_drawdown_pct,
                "close_drawdown_r": drawdown_r,
                "close_drawdown_pct": drawdown_pct,
                "initial_heat_r": peak_heat_r,
                "open_positions": peak_positions,
                "policy_mode_at_open": mode,
                "policy_heat_limit_r": maximum_heat_r,
                "new_trade_risk_r": risk_per_trade_r,
            }
        )
    curve = pd.DataFrame(curve_rows)
    ledger = pd.DataFrame(
        [
            {
                **item.trade.to_dict(),
                "allocated_r": item.allocated_r,
                "portfolio_realised_r": item.trade.realised_r * item.allocated_r,
            }
            for item in accepted
        ]
    )
    if ledger.empty:
        metrics = {
            "candidate_trade_count": len(trades),
            "accepted_trade_count": 0,
            "rejection_count": int(sum(rejection_reasons.values())),
            "rejection_reasons": dict(sorted(rejection_reasons.items())),
            "average_allocated_r": None,
            "expectancy_per_trade_r": None,
            "expectancy_per_allocated_r": None,
            "profit_factor": None,
            "win_rate": None,
            "average_win_r": None,
            "average_loss_r": None,
            "payoff_ratio": None,
            "average_mfe_r": None,
            "average_mae_r": None,
            "average_holding_days": None,
            "total_pnl_r": 0.0,
            "starting_equity_r": starting_equity_r,
            "ending_equity_r": starting_equity_r,
            "total_return_pct": 0.0,
            "cagr_pct": 0.0,
            "maximum_drawdown_r": float(curve["drawdown_r"].max()),
            "maximum_drawdown_pct": float(curve["drawdown_pct"].max()),
            "average_heat_r": float(curve["initial_heat_r"].mean()),
            "maximum_heat_r": float(curve["initial_heat_r"].max()),
            "maximum_positions": int(curve["open_positions"].max()),
            "stop_new_risk_sessions": int(
                curve["policy_mode_at_open"].eq("STOP_NEW_RISK").sum()
            ),
            "missing_mark_count": missing_mark_count,
            "exposure_expansion_count": exposure_expansion_count,
            "exposure_contraction_count": exposure_contraction_count,
        }
        return metrics, ledger, curve
    outcomes = pd.to_numeric(ledger["portfolio_realised_r"], errors="coerce")
    allocated_r = pd.to_numeric(ledger["allocated_r"], errors="coerce")
    wins = outcomes[outcomes > 0]
    losses = outcomes[outcomes <= 0]
    average_win_r = float(wins.mean()) if len(wins) else None
    average_loss_r = float(losses.mean()) if len(losses) else None
    total_pnl_r = float(outcomes.sum())
    duration_years = max(
        (pd.Timestamp(calendar[-1]) - pd.Timestamp(calendar[0])).days / 365.25,
        1 / 252,
    )
    ending_equity_r = starting_equity_r + total_pnl_r
    cagr = (
        (ending_equity_r / starting_equity_r) ** (1 / duration_years) - 1
        if ending_equity_r > 0
        else None
    )
    metrics = {
        "candidate_trade_count": len(trades),
        "accepted_trade_count": len(accepted),
        "rejection_count": int(sum(rejection_reasons.values())),
        "rejection_reasons": dict(sorted(rejection_reasons.items())),
        "average_allocated_r": float(allocated_r.mean()),
        "expectancy_per_trade_r": float(outcomes.mean()),
        "expectancy_per_allocated_r": float(total_pnl_r / allocated_r.sum()),
        "profit_factor": (
            float(wins.sum() / abs(losses.sum()))
            if len(losses) and losses.sum() != 0
            else None
        ),
        "win_rate": float((outcomes > 0).mean()),
        "average_win_r": average_win_r,
        "average_loss_r": average_loss_r,
        "payoff_ratio": (
            average_win_r / abs(average_loss_r)
            if average_win_r is not None and average_loss_r not in (None, 0)
            else None
        ),
        "average_mfe_r": float(
            (pd.to_numeric(ledger["MFE_R"], errors="coerce") * allocated_r).mean()
        ),
        "average_mae_r": float(
            (pd.to_numeric(ledger["MAE_R"], errors="coerce") * allocated_r).mean()
        ),
        "average_holding_days": float(
            pd.to_numeric(ledger["holding_days"], errors="coerce").mean()
        ),
        "total_pnl_r": total_pnl_r,
        "starting_equity_r": starting_equity_r,
        "ending_equity_r": ending_equity_r,
        "total_return_pct": total_pnl_r / starting_equity_r * 100,
        "cagr_pct": None if cagr is None else cagr * 100,
        "maximum_drawdown_r": float(curve["drawdown_r"].max()),
        "maximum_drawdown_pct": float(curve["drawdown_pct"].max()),
        "average_heat_r": float(curve["initial_heat_r"].mean()),
        "maximum_heat_r": float(curve["initial_heat_r"].max()),
        "maximum_positions": int(curve["open_positions"].max()),
        "stop_new_risk_sessions": int(
            curve["policy_mode_at_open"].eq("STOP_NEW_RISK").sum()
        ),
        "missing_mark_count": missing_mark_count,
        "exposure_expansion_count": exposure_expansion_count,
        "exposure_contraction_count": exposure_contraction_count,
    }
    return metrics, ledger, curve
