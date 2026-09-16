"""Independent-episode and portfolio accounting for forward research."""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pandas as pd


def _number(value: object) -> float | None:
    parsed = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(parsed) or not np.isfinite(parsed) else float(parsed)


def build_independent_episodes(
    journal: pd.DataFrame, observation_end: pd.Timestamp
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep at most one active triggered plan per ticker at any instant."""

    annotated = journal.copy()
    annotated["independent_episode"] = False
    annotated["episode_id"] = pd.NA
    annotated["episode_exclusion_reason"] = pd.NA
    triggered = annotated[annotated["plan_triggered"].eq(True)].copy()
    if triggered.empty:
        return annotated, triggered
    triggered["_entry"] = pd.to_datetime(triggered["plan_entry_date"], errors="coerce")
    triggered["_exit"] = pd.to_datetime(triggered["plan_exit_date"], errors="coerce")
    triggered["_row_order"] = range(len(triggered))
    triggered = triggered.sort_values(
        ["ticker", "_entry", "signal_date", "_row_order"], kind="stable"
    )
    active_until: dict[str, pd.Timestamp] = {}
    sequence: Counter[str] = Counter()
    kept_indices: list[int] = []
    for index, row in triggered.iterrows():
        ticker = str(row["ticker"])
        entry = row["_entry"]
        if pd.isna(entry):
            annotated.at[index, "episode_exclusion_reason"] = "INVALID_ENTRY_DATE"
            continue
        prior_end = active_until.get(ticker)
        if prior_end is not None and entry <= prior_end:
            annotated.at[index, "episode_exclusion_reason"] = "SAME_TICKER_OVERLAP"
            continue
        sequence[ticker] += 1
        episode_id = f"{ticker}:{entry.date().isoformat()}:{sequence[ticker]:04d}"
        annotated.at[index, "independent_episode"] = True
        annotated.at[index, "episode_id"] = episode_id
        kept_indices.append(index)
        exit_date = row["_exit"]
        active_until[ticker] = (
            observation_end.normalize() if pd.isna(exit_date) else exit_date.normalize()
        )
    episodes = annotated.loc[kept_indices].copy()
    return annotated, episodes


def ticker_cluster_bootstrap_ci(
    frame: pd.DataFrame,
    *,
    value_column: str,
    seed: int,
    resamples: int,
) -> dict[str, Any]:
    """Return a deterministic ticker-cluster bootstrap interval for a mean."""

    if not {"ticker", value_column} <= set(frame):
        frame = pd.DataFrame(columns=["ticker", value_column])
    usable = frame[["ticker", value_column]].copy()
    usable[value_column] = pd.to_numeric(usable[value_column], errors="coerce")
    usable = usable.dropna()
    clusters = {
        str(ticker): group[value_column].to_numpy(dtype=float)
        for ticker, group in usable.groupby("ticker", sort=True)
    }
    if not clusters:
        return {
            "method": "TICKER_CLUSTER_BOOTSTRAP",
            "cluster_count": 0,
            "observation_count": 0,
            "mean": None,
            "lower_95": None,
            "upper_95": None,
            "seed": seed,
            "resamples": resamples,
        }
    values = np.concatenate(list(clusters.values()))
    if len(clusters) < 2 or resamples <= 0:
        lower = upper = None
    else:
        rng = np.random.default_rng(seed)
        names = np.array(sorted(clusters), dtype=object)
        estimates = np.empty(resamples, dtype=float)
        for position in range(resamples):
            sampled = rng.choice(names, size=len(names), replace=True)
            sample = np.concatenate([clusters[str(name)] for name in sampled])
            estimates[position] = float(sample.mean())
        lower, upper = (
            float(value) for value in np.quantile(estimates, [0.025, 0.975])
        )
    return {
        "method": "TICKER_CLUSTER_BOOTSTRAP",
        "cluster_count": len(clusters),
        "observation_count": len(values),
        "mean": float(values.mean()),
        "lower_95": lower,
        "upper_95": upper,
        "seed": seed,
        "resamples": resamples,
    }


def _eligibility_mask(frame: pd.DataFrame, variant: dict[str, Any]) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    for rule in variant.get("eligibility", {}).get("all", []):
        column = str(rule["column"])
        if column not in frame:
            mask &= False
            continue
        expected = rule.get("equals")
        if isinstance(expected, bool):
            values = frame[column].map(
                lambda value: (
                    value
                    if isinstance(value, (bool, np.bool_))
                    else str(value).strip().casefold() == "true"
                )
            )
        else:
            values = frame[column]
        mask &= values.eq(expected)
    return mask


def _risk_for_row(row: pd.Series, variant: dict[str, Any]) -> float | None:
    risk = variant["risk"]
    if "fixed_r" in risk:
        value = _number(risk["fixed_r"])
    else:
        value = _number(row.get(str(risk["source_column"])))
    return value if value is not None and value > 0 else None


def _mark_close(
    histories: dict[str, pd.DataFrame], ticker: str, session: pd.Timestamp
) -> float | None:
    history = histories.get(ticker)
    if history is None or history.empty:
        return None
    index = pd.DatetimeIndex(history.index)
    positions = index.get_indexer([session])
    position = int(positions[0])
    if position < 0:
        return None
    value = _number(history.iloc[position].get("Close"))
    return value if value is not None and value > 0 else None


def evaluate_portfolio_variants(
    episodes: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    sessions: pd.DatetimeIndex,
    variants: list[dict[str, Any]],
    *,
    observation_end: pd.Timestamp,
    bootstrap_seed: int,
    bootstrap_resamples: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Apply shared heat, capacity and ordering to frozen forward episodes."""

    metric_rows: list[dict[str, Any]] = []
    ledger_frames: list[pd.DataFrame] = []
    curve_frames: list[pd.DataFrame] = []
    intervals: dict[str, Any] = {}
    for variant in variants:
        variant_id = str(variant["variant_id"])
        selected = episodes.loc[_eligibility_mask(episodes, variant)].copy()
        selected["_entry"] = pd.to_datetime(selected["plan_entry_date"])
        selected["_exit"] = pd.to_datetime(selected["plan_exit_date"], errors="coerce")
        snapshot_order = (
            selected["snapshot_row_order"]
            if "snapshot_row_order" in selected
            else pd.Series(np.inf, index=selected.index)
        )
        selected["_snapshot_order"] = pd.to_numeric(
            snapshot_order, errors="coerce"
        ).fillna(np.inf)
        ordering = variant.get("ordering", [])
        sort_columns = ["_entry"]
        ascending = [True]
        for rule in ordering:
            column = str(rule["column"])
            if column not in selected:
                raise ValueError(
                    f"variant {variant_id} ordering column is missing: {column}"
                )
            direction = str(rule.get("direction", "")).upper()
            if direction not in {"ASC", "DESC"}:
                raise ValueError(
                    f"variant {variant_id} ordering direction is invalid: {direction}"
                )
            sort_columns.append(column)
            ascending.append(direction == "ASC")
        sort_columns.extend(["signal_date", "ticker", "_snapshot_order"])
        ascending.extend([True, True, True])
        selected = selected.sort_values(
            sort_columns, ascending=ascending, kind="stable"
        )
        portfolio = variant["portfolio"]
        maximum_positions = int(portfolio["maximum_positions"])
        maximum_heat_r = float(portfolio["maximum_heat_r"])
        if maximum_positions <= 0:
            raise ValueError(f"variant {variant_id} maximum_positions must be positive")
        if not np.isfinite(maximum_heat_r) or maximum_heat_r <= 0:
            raise ValueError(
                f"variant {variant_id} maximum_heat_r must be finite and positive"
            )
        industry_cap = portfolio.get("maximum_positions_per_industry")
        if industry_cap is not None:
            industry_cap = int(industry_cap)
        accepted: list[dict[str, Any]] = []
        ledger_rows: list[dict[str, Any]] = []
        peak_positions = 0
        peak_heat_r = 0.0
        for _, row in selected.iterrows():
            entry = pd.Timestamp(row["_entry"]).normalize()
            open_rows = [
                item for item in accepted if entry <= item["effective_exit_date"]
            ]
            risk_r = _risk_for_row(row, variant)
            reason = "ACCEPTED"
            industry = str(row.get("Industry", "")).strip()
            if risk_r is None:
                reason = "INVALID_RISK"
            elif any(item["ticker"] == str(row["ticker"]) for item in open_rows):
                reason = "SAME_TICKER"
            elif len(open_rows) >= maximum_positions:
                reason = "MAX_POSITIONS"
            elif (
                sum(float(item["allocated_r"]) for item in open_rows) + risk_r
                > maximum_heat_r + 1e-12
            ):
                reason = "MAX_HEAT"
            elif industry_cap is not None and industry.casefold() in {
                "",
                "unknown",
                "n/a",
                "none",
                "nan",
            }:
                reason = "UNKNOWN_INDUSTRY"
            elif (
                industry_cap is not None
                and sum(
                    item["industry"].casefold() == industry.casefold()
                    for item in open_rows
                )
                >= industry_cap
            ):
                reason = "MAX_INDUSTRY_POSITIONS"
            record = row.to_dict()
            record.update(
                {
                    "variant_id": variant_id,
                    "variant_role": variant["role"],
                    "portfolio_accepted": reason == "ACCEPTED",
                    "portfolio_rejection_reason": None
                    if reason == "ACCEPTED"
                    else reason,
                    "allocated_r": risk_r,
                }
            )
            ledger_rows.append(record)
            if reason == "ACCEPTED":
                assert risk_r is not None
                exit_date = row["_exit"]
                accepted.append(
                    {
                        "row": row,
                        "ticker": str(row["ticker"]),
                        "industry": industry,
                        "allocated_r": risk_r,
                        "entry_date": entry,
                        "effective_exit_date": (
                            observation_end.normalize()
                            if pd.isna(exit_date)
                            else pd.Timestamp(exit_date).normalize()
                        ),
                    }
                )
                peak_positions = max(peak_positions, len(open_rows) + 1)
                peak_heat_r = max(
                    peak_heat_r,
                    sum(float(item["allocated_r"]) for item in open_rows) + risk_r,
                )
        ledger = pd.DataFrame(ledger_rows)
        if not ledger.empty:
            ledger_frames.append(
                ledger.drop(
                    columns=["_entry", "_exit", "_snapshot_order"], errors="ignore"
                )
            )
        accepted_rows = (
            ledger[ledger["portfolio_accepted"].eq(True)].copy()
            if not ledger.empty
            else ledger
        )
        mature = (
            accepted_rows[
                pd.to_numeric(
                    accepted_rows.get("plan_realised_r"), errors="coerce"
                ).notna()
            ].copy()
            if not accepted_rows.empty
            else accepted_rows
        )
        interval = ticker_cluster_bootstrap_ci(
            mature,
            value_column="plan_realised_r",
            seed=bootstrap_seed,
            resamples=bootstrap_resamples,
        )
        intervals[variant_id] = interval
        curve_rows: list[dict[str, Any]] = []
        realised_r = 0.0
        high_water = 0.0
        missing_marks = 0
        calendar = (
            sessions[
                (sessions >= selected["_entry"].min()) & (sessions <= observation_end)
            ]
            if not selected.empty
            else pd.DatetimeIndex([])
        )
        for session in calendar:
            exiting = [
                item
                for item in accepted
                if pd.notna(item["row"]["plan_exit_date"])
                and pd.Timestamp(item["row"]["plan_exit_date"]).normalize()
                == session.normalize()
            ]
            realised_r += sum(
                float(item["row"]["plan_realised_r"]) * float(item["allocated_r"])
                for item in exiting
            )
            open_rows = [
                item
                for item in accepted
                if item["entry_date"] <= session.normalize()
                and (
                    pd.isna(item["row"]["plan_exit_date"])
                    or pd.Timestamp(item["row"]["plan_exit_date"]).normalize()
                    > session.normalize()
                )
            ]
            unrealised_r = 0.0
            for item in open_rows:
                close = _mark_close(histories, item["ticker"], session)
                entry = _number(item["row"].get("plan_entry"))
                stop = _number(item["row"].get("Initial Stop"))
                if close is None or entry is None or stop is None or entry <= stop:
                    missing_marks += 1
                    continue
                unrealised_r += (
                    (close - entry) / (entry - stop) * float(item["allocated_r"])
                )
            equity_pnl_r = realised_r + unrealised_r
            high_water = max(high_water, equity_pnl_r)
            curve_rows.append(
                {
                    "variant_id": variant_id,
                    "date": session.date().isoformat(),
                    "portfolio_pnl_r": equity_pnl_r,
                    "drawdown_r": high_water - equity_pnl_r,
                    "initial_heat_r": sum(
                        float(item["allocated_r"]) for item in open_rows
                    ),
                    "open_positions": len(open_rows),
                }
            )
        curve = pd.DataFrame(curve_rows)
        if not curve.empty:
            curve_frames.append(curve)
        realised = (
            pd.to_numeric(mature.get("plan_realised_r"), errors="coerce")
            if not mature.empty
            else pd.Series(dtype=float)
        )
        wins = realised[realised > 0]
        losses = realised[realised <= 0]
        metric_rows.append(
            {
                "variant_id": variant_id,
                "role": variant["role"],
                "selected_episode_count": len(selected),
                "accepted_episode_count": len(accepted_rows),
                "mature_accepted_episode_count": len(mature),
                "open_accepted_episode_count": int(
                    accepted_rows["plan_exit_date"].isna().sum()
                )
                if not accepted_rows.empty
                else 0,
                "expectancy_r": float(realised.mean()) if len(realised) else None,
                "profit_factor": float(wins.sum() / abs(losses.sum()))
                if len(losses) and losses.sum() != 0
                else None,
                "win_rate": float((realised > 0).mean()) if len(realised) else None,
                "maximum_drawdown_r": float(curve["drawdown_r"].max())
                if not curve.empty
                else None,
                "maximum_heat_r": peak_heat_r,
                "maximum_positions": peak_positions,
                "missing_mark_count": missing_marks,
                "rejection_reasons": dict(
                    sorted(
                        Counter(
                            ledger.loc[
                                ledger["portfolio_accepted"].eq(False),
                                "portfolio_rejection_reason",
                            ]
                        ).items()
                    )
                )
                if not ledger.empty
                else {},
            }
        )
    return (
        pd.DataFrame(metric_rows),
        pd.concat(ledger_frames, ignore_index=True)
        if ledger_frames
        else pd.DataFrame(),
        pd.concat(curve_frames, ignore_index=True) if curve_frames else pd.DataFrame(),
        intervals,
    )
