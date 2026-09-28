"""Research-only candidate ranking with canonical portfolio-state evaluation."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from .forward_portfolio import evaluate_portfolio_variants
from .base_features import enrich_base_features
from .leader_features import enrich_leader_features
from .market_features import enrich_market_features


EXPERIMENT_ID = "PORTFOLIO_RANKING_PHASE_A_V1"
DEFAULT_RESEARCH_SEED = 20260916
DEFAULT_FACTOR_COLUMNS = {
    "recent_rs": "recent_rs_score",
    "industry_strength": "industry_proxy_score",
    "pivot_supply_quality": "pivot_supply_quality_score",
    "volume_quality": "volume_quality_score",
}
FACTOR_NAMES = tuple(DEFAULT_FACTOR_COLUMNS)
RANKER_NAMES = (
    "production_final_score",
    "deterministic_random",
    "recent_rs",
    "industry_strength",
    "pivot_supply_quality",
    "volume_quality",
    "composite_equal_weight",
    "loo_without_recent_rs",
    "loo_without_industry_strength",
    "loo_without_pivot_supply_quality",
    "loo_without_volume_quality",
)


def _strict_boolean(value: object, *, label: str) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    raise ValueError(f"{label} must contain only booleans")


def deterministic_random_key(seed: int, as_of_date: object, ticker: object) -> str:
    """Return a cross-process SHA-256 order key for the fixed random baseline."""

    normalized_date = pd.Timestamp(as_of_date).date().isoformat()
    normalized_ticker = str(ticker).strip().upper()
    payload = f"{EXPERIMENT_ID}|{seed}|{normalized_date}|{normalized_ticker}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def annotate_candidate_eligibility(
    candidates: pd.DataFrame,
    *,
    eligibility_column: str,
    blocked_reason_column: str | None = None,
) -> pd.DataFrame:
    """Freeze candidate eligibility before any ranker is calculated or applied."""

    required = {"as_of_date", "ticker", eligibility_column}
    missing = sorted(required - set(candidates.columns))
    if missing:
        raise ValueError(
            "candidate eligibility columns are missing: " + ", ".join(missing)
        )
    result = candidates.copy()
    result["as_of_date"] = pd.to_datetime(
        result["as_of_date"], errors="raise"
    ).dt.date.astype(str)
    result["ticker"] = result["ticker"].astype(str).str.strip().str.upper()
    if result["ticker"].eq("").any():
        raise ValueError("candidate ticker must be non-empty")
    duplicated = result.duplicated(["as_of_date", "ticker"], keep=False)
    if duplicated.any():
        keys = result.loc[duplicated, ["as_of_date", "ticker"]].head(5)
        raise ValueError(
            "duplicate as_of_date/ticker candidates: "
            + ", ".join(
                f"{row.as_of_date}/{row.ticker}" for row in keys.itertuples(index=False)
            )
        )

    result["ranking_eligible"] = result[eligibility_column].map(
        lambda value: _strict_boolean(value, label=eligibility_column)
    )
    if blocked_reason_column is not None:
        if blocked_reason_column not in result:
            raise ValueError(
                f"candidate blocked-reason column is missing: {blocked_reason_column}"
            )
        reasons = result[blocked_reason_column].fillna("").astype(str).str.strip()
    else:
        reasons = pd.Series("", index=result.index, dtype=str)
    result["eligibility_blocked_reason"] = np.where(
        result["ranking_eligible"], "", reasons.mask(reasons.eq(""), "INELIGIBLE")
    )
    return result


def _factor_percentile(values: pd.Series, eligible: pd.Series) -> pd.Series:
    numeric = _finite_numeric(values)
    result = pd.Series(np.nan, index=values.index, dtype=float)
    usable = eligible & numeric.notna()
    if usable.any():
        result.loc[usable] = (
            numeric.loc[usable].rank(pct=True, method="average", ascending=True) * 100.0
        )
    result.loc[eligible & numeric.isna()] = 0.0
    return result


def _finite_numeric(values: pd.Series) -> pd.Series:
    """Coerce ranking inputs to finite floats and preserve invalids as missing."""

    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    return numeric.where(np.isfinite(numeric), np.nan)


def _strict_integer(
    value: object,
    *,
    label: str,
    minimum: int,
    maximum: int | None = None,
) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{label} must be an integer >= {minimum}")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer >= {minimum}") from exc
    if (
        not np.isfinite(numeric)
        or not numeric.is_integer()
        or numeric < minimum
        or (maximum is not None and numeric > maximum)
    ):
        suffix = (
            f" between {minimum} and {maximum}"
            if maximum is not None
            else f" >= {minimum}"
        )
        raise ValueError(f"{label} must be an integer{suffix}")
    return int(numeric)


def _strict_nonnegative_number(value: object, *, label: str) -> float:
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{label} must be finite and non-negative")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be finite and non-negative") from exc
    if not np.isfinite(numeric) or numeric < 0:
        raise ValueError(f"{label} must be finite and non-negative")
    return numeric


def _candidate_concentration_reasons(
    episodes: pd.DataFrame,
    concentration: Mapping[str, Any],
) -> pd.Series:
    """Apply the frozen production candidate-list concentration per ranker/day."""

    industry_column = str(concentration["industry_column"])
    sector_column = str(concentration["sector_column"])
    score_column = str(concentration["industry_score_column"])
    required = {
        "as_of_date",
        "ticker",
        "rank_position",
        "ranking_eligible",
        industry_column,
        sector_column,
        score_column,
    }
    missing = sorted(required - set(episodes.columns))
    if missing:
        raise ValueError(
            "candidate concentration columns are missing: " + ", ".join(missing)
        )
    industry_limit = _strict_integer(
        concentration["maximum_per_industry"],
        label="maximum_per_industry",
        minimum=1,
    )
    sector_limit = _strict_integer(
        concentration["maximum_per_sector"],
        label="maximum_per_sector",
        minimum=1,
    )
    high_conviction_extra = _strict_integer(
        concentration["high_conviction_extra_positions"],
        label="high_conviction_extra_positions",
        minimum=0,
    )
    high_conviction_score = _strict_nonnegative_number(
        concentration["high_conviction_industry_score"],
        label="high_conviction_industry_score",
    )
    reasons = pd.Series("", index=episodes.index, dtype=str)
    for _, indices in episodes.groupby("as_of_date", sort=True).groups.items():
        ordered = episodes.loc[indices].sort_values(
            ["rank_position", "ticker"], na_position="last", kind="stable"
        )
        industry_counts: dict[str, int] = {}
        sector_counts: dict[str, int] = {}
        for index, row in ordered.iterrows():
            if not bool(row["ranking_eligible"]):
                continue
            industry = str(row[industry_column])
            sector = str(row[sector_column])
            score = pd.to_numeric(row[score_column], errors="coerce")
            row_industry_limit = industry_limit
            if (
                pd.notna(score)
                and np.isfinite(float(score))
                and float(score) >= high_conviction_score
            ):
                row_industry_limit += high_conviction_extra
            reason = ""
            if industry_counts.get(industry, 0) >= row_industry_limit:
                reason = "INDUSTRY_CONCENTRATION"
            elif sector_counts.get(sector, 0) >= sector_limit:
                reason = "SECTOR_CONCENTRATION"
            if reason:
                reasons.at[index] = reason
                continue
            industry_counts[industry] = industry_counts.get(industry, 0) + 1
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
    return reasons


def enrich_point_in_time_ranking_factors(
    candidates: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    benchmark: pd.DataFrame,
    *,
    sectors: dict[str, str] | None = None,
    industries: dict[str, str] | None = None,
    minimum_industry_members: int = 5,
) -> pd.DataFrame:
    """Calculate the four frozen Phase A factors from bars through the as-of date.

    ``pivot_supply_quality_score`` is the fixed inverse count of distribution
    days near the causal 126-session pivot (10 minus ``pivot_supply_days_10d``).
    ``volume_quality_score`` is the causal 50-session up/down-volume ratio.
    Neither formula contains a fitted threshold or tunable factor weight.
    """

    required = {"as_of_date", "ticker"}
    missing = sorted(required - set(candidates.columns))
    if missing:
        raise ValueError("factor input columns are missing: " + ", ".join(missing))
    result = candidates.copy()
    result["signal_date"] = pd.to_datetime(
        result["as_of_date"], errors="raise"
    ).dt.date.astype(str)
    result["ticker"] = result["ticker"].astype(str).str.strip().str.upper()
    result = enrich_market_features(
        result,
        histories,
        benchmark,
        classifications=sectors,
    )
    result = enrich_leader_features(
        result,
        histories,
        benchmark,
        sectors=sectors,
        industries=industries,
        minimum_industry_members=minimum_industry_members,
    )
    result = enrich_base_features(result, histories)
    pivot_supply_days = _finite_numeric(result["pivot_supply_days_10d"])
    pivot_supply_days = pivot_supply_days.where(pivot_supply_days.between(0.0, 10.0))
    result["pivot_supply_quality_score"] = 10.0 - pivot_supply_days
    result["volume_quality_score"] = _finite_numeric(result["up_down_volume_ratio_50d"])
    for column in DEFAULT_FACTOR_COLUMNS.values():
        result[column] = _finite_numeric(result[column])
    return result


def build_ranking_dataset(
    candidates: pd.DataFrame,
    *,
    final_score_column: str = "Final Score",
    factor_columns: dict[str, str] | None = None,
    research_seed: int = DEFAULT_RESEARCH_SEED,
) -> pd.DataFrame:
    """Build every preregistered ranker without changing candidate eligibility."""

    factors = dict(DEFAULT_FACTOR_COLUMNS if factor_columns is None else factor_columns)
    if set(factors) != set(FACTOR_NAMES):
        raise ValueError(
            "factor_columns must define exactly: " + ", ".join(FACTOR_NAMES)
        )
    required = {
        "as_of_date",
        "ticker",
        "ranking_eligible",
        "eligibility_blocked_reason",
        final_score_column,
        *factors.values(),
    }
    missing = sorted(required - set(candidates.columns))
    if missing:
        raise ValueError("ranking columns are missing: " + ", ".join(missing))
    frame = candidates.copy()
    frame["as_of_date"] = pd.to_datetime(
        frame["as_of_date"], errors="raise"
    ).dt.date.astype(str)
    frame["ticker"] = frame["ticker"].astype(str).str.strip().str.upper()
    frame["ranking_eligible"] = frame["ranking_eligible"].map(
        lambda value: _strict_boolean(value, label="ranking_eligible")
    )
    duplicated = frame.duplicated(["as_of_date", "ticker"], keep=False)
    if duplicated.any():
        raise ValueError("ranking requires one candidate per as_of_date/ticker")
    frame["raw_final_score"] = _finite_numeric(frame[final_score_column])
    for factor, column in factors.items():
        frame[f"{factor}_raw"] = _finite_numeric(frame[column])
        percentile_column = f"{factor}_percentile"
        frame[percentile_column] = np.nan
        for indices in frame.groupby("as_of_date", sort=True).groups.values():
            frame.loc[indices, percentile_column] = _factor_percentile(
                frame.loc[indices, f"{factor}_raw"],
                frame.loc[indices, "ranking_eligible"],
            )
    percentile_columns = [f"{factor}_percentile" for factor in FACTOR_NAMES]
    frame["composite_equal_weight_score"] = frame[percentile_columns].sum(axis=1) * 0.25
    for omitted in FACTOR_NAMES:
        included = [
            f"{factor}_percentile" for factor in FACTOR_NAMES if factor != omitted
        ]
        frame[f"loo_without_{omitted}_score"] = frame[included].sum(axis=1) / 3.0
    frame["deterministic_random_key"] = [
        deterministic_random_key(research_seed, date, ticker)
        for date, ticker in zip(frame["as_of_date"], frame["ticker"], strict=True)
    ]
    frame["deterministic_random_score"] = frame["deterministic_random_key"].map(
        lambda value: int(value[:13], 16) / float(16**13 - 1)
    )

    score_columns = {
        "production_final_score": "raw_final_score",
        "deterministic_random": "deterministic_random_score",
        "recent_rs": "recent_rs_percentile",
        "industry_strength": "industry_strength_percentile",
        "pivot_supply_quality": "pivot_supply_quality_percentile",
        "volume_quality": "volume_quality_percentile",
        "composite_equal_weight": "composite_equal_weight_score",
        **{
            f"loo_without_{factor}": f"loo_without_{factor}_score"
            for factor in FACTOR_NAMES
        },
    }
    raw_audit_columns = [
        "as_of_date",
        "ticker",
        "ranking_eligible",
        "eligibility_blocked_reason",
        "raw_final_score",
        *[f"{factor}_raw" for factor in FACTOR_NAMES],
        *percentile_columns,
        "deterministic_random_key",
    ]
    outputs: list[pd.DataFrame] = []
    for ranker_name in RANKER_NAMES:
        ranked = frame[raw_audit_columns].copy()
        ranked["ranker_name"] = ranker_name
        ranked["rank_score"] = frame[score_columns[ranker_name]]
        ranked["rank_position"] = pd.Series(pd.NA, index=ranked.index, dtype="Int64")
        for _, indices in ranked.groupby("as_of_date", sort=True).groups.items():
            eligible_indices = [
                index for index in indices if bool(ranked.at[index, "ranking_eligible"])
            ]
            if ranker_name == "deterministic_random":
                ordered = sorted(
                    eligible_indices,
                    key=lambda index: (
                        str(ranked.at[index, "deterministic_random_key"]),
                        str(ranked.at[index, "ticker"]),
                    ),
                )
            else:
                ordered = sorted(
                    eligible_indices,
                    key=lambda index: (
                        -float(ranked.at[index, "rank_score"])
                        if pd.notna(ranked.at[index, "rank_score"])
                        else float("inf"),
                        str(ranked.at[index, "ticker"]),
                    ),
                )
            for position, index in enumerate(ordered, start=1):
                ranked.at[index, "rank_position"] = position
        outputs.append(ranked)
    return (
        pd.concat(outputs, ignore_index=True)
        .sort_values(
            ["ranker_name", "as_of_date", "rank_position", "ticker"],
            na_position="last",
            kind="stable",
        )
        .reset_index(drop=True)
    )


def evaluate_ranking_arms(
    candidates: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    sessions: pd.DatetimeIndex,
    *,
    risk: dict[str, Any],
    portfolio: dict[str, Any],
    observation_end: pd.Timestamp,
    final_score_column: str = "Final Score",
    factor_columns: dict[str, str] | None = None,
    research_seed: int = DEFAULT_RESEARCH_SEED,
    bootstrap_resamples: int = 2000,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Evaluate all rankers through one shared, exit-aware portfolio engine."""

    rankings = build_ranking_dataset(
        candidates,
        final_score_column=final_score_column,
        factor_columns=factor_columns,
        research_seed=research_seed,
    )
    candidate_keys = candidates.copy()
    candidate_keys["as_of_date"] = pd.to_datetime(
        candidate_keys["as_of_date"], errors="raise"
    ).dt.date.astype(str)
    candidate_keys["ticker"] = (
        candidate_keys["ticker"].astype(str).str.strip().str.upper()
    )
    if "signal_date" in candidate_keys:
        signal_dates = pd.to_datetime(
            candidate_keys["signal_date"], errors="raise"
        ).dt.date.astype(str)
        if not signal_dates.eq(candidate_keys["as_of_date"]).all():
            raise ValueError("signal_date must equal as_of_date for ranking evaluation")
        candidate_keys["signal_date"] = signal_dates
    else:
        candidate_keys["signal_date"] = candidate_keys["as_of_date"]

    metric_frames: list[pd.DataFrame] = []
    ledger_frames: list[pd.DataFrame] = []
    concentration_frames: list[pd.DataFrame] = []
    curve_frames: list[pd.DataFrame] = []
    intervals: dict[str, Any] = {}
    for ranker_name in RANKER_NAMES:
        rank_rows = rankings[rankings["ranker_name"].eq(ranker_name)].copy()
        episodes = candidate_keys.merge(
            rank_rows,
            on=[
                "as_of_date",
                "ticker",
                "ranking_eligible",
                "eligibility_blocked_reason",
            ],
            how="inner",
            validate="one_to_one",
        ).drop(columns=["ranker_name"])
        concentration = portfolio.get("candidate_concentration")
        episodes["portfolio_ranking_eligible"] = episodes["ranking_eligible"]
        if concentration is not None:
            if not isinstance(concentration, Mapping):
                raise ValueError("candidate_concentration must be an object")
            episodes["concentration_blocked_reason"] = _candidate_concentration_reasons(
                episodes, concentration
            )
            episodes["portfolio_ranking_eligible"] = episodes[
                "ranking_eligible"
            ] & episodes["concentration_blocked_reason"].eq("")
            concentration_blocked = episodes[
                episodes["ranking_eligible"]
                & episodes["concentration_blocked_reason"].ne("")
            ].copy()
            if not concentration_blocked.empty:
                concentration_blocked["ranker_name"] = ranker_name
                concentration_blocked["selected"] = False
                concentration_blocked["blocked_reason"] = concentration_blocked[
                    "concentration_blocked_reason"
                ]
                concentration_blocked["portfolio_heat_before"] = np.nan
                concentration_blocked["portfolio_heat_after"] = np.nan
                concentration_frames.append(concentration_blocked)
        variant = {
            "variant_id": ranker_name,
            "role": "RESEARCH_RANKER",
            "eligibility": {
                "all": [{"column": "portfolio_ranking_eligible", "equals": True}]
            },
            "risk": risk,
            "portfolio": portfolio,
            "ordering": [{"column": "rank_position", "direction": "ASC"}],
        }
        metrics, ledger, curve, arm_intervals = evaluate_portfolio_variants(
            episodes,
            histories,
            sessions,
            [variant],
            observation_end=observation_end,
            bootstrap_seed=research_seed,
            bootstrap_resamples=bootstrap_resamples,
        )
        metric_frames.append(metrics.rename(columns={"variant_id": "ranker_name"}))
        if not ledger.empty:
            ledger_frames.append(ledger)
        if not curve.empty:
            curve_frames.append(curve.rename(columns={"variant_id": "ranker_name"}))
        intervals.update(arm_intervals)

    ledger = (
        pd.concat(ledger_frames, ignore_index=True) if ledger_frames else pd.DataFrame()
    )
    if not ledger.empty:
        ledger = ledger.rename(columns={"variant_id": "ranker_name"})
        ledger["selected"] = ledger["portfolio_accepted"].astype(bool)
        ledger["blocked_reason"] = ledger["portfolio_rejection_reason"].fillna("")
    if concentration_frames:
        ledger = pd.concat(
            [ledger, *concentration_frames], ignore_index=True, sort=False
        )
    ineligible = rankings[~rankings["ranking_eligible"]].copy()
    if not ineligible.empty:
        ineligible["selected"] = False
        ineligible["blocked_reason"] = ineligible["eligibility_blocked_reason"]
        ineligible["portfolio_heat_before"] = np.nan
        ineligible["portfolio_heat_after"] = np.nan
        ledger = pd.concat([ledger, ineligible], ignore_index=True, sort=False)

    audit_columns = [
        "as_of_date",
        "ticker",
        "ranker_name",
        *[f"{factor}_raw" for factor in FACTOR_NAMES],
        *[f"{factor}_percentile" for factor in FACTOR_NAMES],
        "raw_final_score",
        "deterministic_random_key",
        "rank_score",
        "rank_position",
        "selected",
        "blocked_reason",
        "portfolio_heat_before",
        "portfolio_heat_after",
    ]
    audit = (
        ledger.reindex(columns=audit_columns)
        .sort_values(
            ["ranker_name", "as_of_date", "rank_position", "ticker"],
            na_position="last",
            kind="stable",
        )
        .reset_index(drop=True)
    )
    metrics = pd.DataFrame(
        [record for frame in metric_frames for record in frame.to_dict("records")]
    )
    if not metrics.empty:
        metrics["candidate_count"] = len(candidate_keys)
        metrics["eligible_candidate_count"] = int(
            rankings.loc[
                rankings["ranker_name"].eq(RANKER_NAMES[0]), "ranking_eligible"
            ].sum()
        )
        metrics["ineligible_candidate_count"] = (
            metrics["candidate_count"] - metrics["eligible_candidate_count"]
        )
        if "canonical_eligible" in candidate_keys:
            canonical_eligible = candidate_keys["canonical_eligible"].map(
                lambda value: _strict_boolean(value, label="canonical_eligible")
            )
            metrics["canonical_ineligible_candidate_count"] = int(
                (~canonical_eligible).sum()
            )
        blocked_counts: dict[str, dict[str, int]] = {}
        for ranker_name, rows in audit.groupby("ranker_name", sort=True):
            blocked = rows.loc[~rows["selected"], "blocked_reason"]
            counts = blocked[blocked.fillna("").astype(str).str.strip().ne("")]
            blocked_counts[str(ranker_name)] = {
                str(reason): int(count)
                for reason, count in counts.value_counts().sort_index().items()
            }
        metrics["blocked_reason_counts"] = metrics["ranker_name"].map(blocked_counts)
    curves = (
        pd.concat(curve_frames, ignore_index=True) if curve_frames else pd.DataFrame()
    )
    return metrics, audit, curves, intervals


def phase_b_advancement_shortlist(
    metrics: pd.DataFrame,
    gate: Mapping[str, Any],
) -> pd.DataFrame:
    """Apply the frozen Phase A gate without naming or promoting a champion."""

    required = {
        "stage",
        "ranker_name",
        "mature_accepted_episode_count",
        "expectancy_r",
        "profit_factor",
        "total_realised_r",
        "maximum_drawdown_r",
    }
    missing = sorted(required - set(metrics.columns))
    if missing:
        raise ValueError("advancement metrics are missing: " + ", ".join(missing))
    baseline_name = str(gate["baseline_ranker"]).strip()
    if not baseline_name:
        raise ValueError("baseline_ranker must be non-empty")
    raw_stages = gate["required_stages"]
    if not isinstance(raw_stages, (list, tuple)) or not raw_stages:
        raise ValueError("required_stages must be a non-empty list")
    stages = tuple(str(value).strip() for value in raw_stages)
    if any(not stage for stage in stages) or len(set(stages)) != len(stages):
        raise ValueError("required_stages must contain unique non-empty names")
    excluded = {str(value) for value in gate.get("excluded_rankers", [])}
    minimum_count = _strict_integer(
        gate["minimum_mature_accepted_episodes_per_stage"],
        label="minimum_mature_accepted_episodes_per_stage",
        minimum=100,
    )
    minimum_delta = _strict_nonnegative_number(
        gate["minimum_expectancy_improvement_r"],
        label="minimum_expectancy_improvement_r",
    )
    drawdown_tolerance = _strict_nonnegative_number(
        gate["maximum_drawdown_worsening_r"],
        label="maximum_drawdown_worsening_r",
    )
    maximum_rankers = _strict_integer(
        gate["maximum_phase_b_rankers"],
        label="maximum_phase_b_rankers",
        minimum=1,
        maximum=2,
    )

    indexed = metrics.set_index(["stage", "ranker_name"], verify_integrity=True)
    baseline: dict[str, pd.Series] = {}
    baseline_sample_failures: list[str] = []
    for stage in stages:
        key = (stage, baseline_name)
        if key not in indexed.index:
            raise ValueError(f"missing baseline metrics for stage: {stage}")
        baseline[stage] = indexed.loc[key]

    def metric_number(row: pd.Series, column: str) -> float | None:
        value = pd.to_numeric(row.get(column), errors="coerce")
        return float(value) if pd.notna(value) and np.isfinite(float(value)) else None

    for stage in stages:
        baseline_count = metric_number(baseline[stage], "mature_accepted_episode_count")
        if baseline_count is None or baseline_count < minimum_count:
            baseline_sample_failures.append(
                f"{stage}:BASELINE_INSUFFICIENT_MATURE_EPISODES"
            )

    records: list[dict[str, Any]] = []
    for ranker_name in sorted(set(metrics["ranker_name"].astype(str))):
        if ranker_name == baseline_name or ranker_name in excluded:
            continue
        stage_rows: dict[str, pd.Series] = {}
        if any((stage, ranker_name) not in indexed.index for stage in stages):
            continue
        for stage in stages:
            stage_rows[stage] = indexed.loc[(stage, ranker_name)]

        reasons: list[str] = list(baseline_sample_failures)
        validation_delta = np.nan
        for stage in stages:
            row = stage_rows[stage]
            base = baseline[stage]
            mature_count = metric_number(row, "mature_accepted_episode_count")
            row_expectancy = metric_number(row, "expectancy_r")
            base_expectancy = metric_number(base, "expectancy_r")
            row_total = metric_number(row, "total_realised_r")
            base_total = metric_number(base, "total_realised_r")
            row_profit_factor = metric_number(row, "profit_factor")
            base_profit_factor = metric_number(base, "profit_factor")
            row_drawdown = metric_number(row, "maximum_drawdown_r")
            base_drawdown = metric_number(base, "maximum_drawdown_r")
            if mature_count is None or mature_count < minimum_count:
                reasons.append(f"{stage}:INSUFFICIENT_MATURE_EPISODES")
            expectancy_delta = (
                row_expectancy - base_expectancy
                if row_expectancy is not None and base_expectancy is not None
                else None
            )
            if expectancy_delta is None or expectancy_delta < minimum_delta:
                reasons.append(f"{stage}:EXPECTANCY_GATE")
            if row_total is None or base_total is None or row_total <= base_total:
                reasons.append(f"{stage}:TOTAL_R_GATE")
            if (
                row_profit_factor is None
                or base_profit_factor is None
                or row_profit_factor < base_profit_factor
            ):
                reasons.append(f"{stage}:PROFIT_FACTOR_GATE")
            drawdown_worsening = (
                row_drawdown - base_drawdown
                if row_drawdown is not None and base_drawdown is not None
                else None
            )
            if drawdown_worsening is None or drawdown_worsening > drawdown_tolerance:
                reasons.append(f"{stage}:DRAWDOWN_GATE")
            if stage == stages[-1] and expectancy_delta is not None:
                validation_delta = expectancy_delta
        validation_stage = stages[-1]
        validation_drawdown = metric_number(
            stage_rows[validation_stage], "maximum_drawdown_r"
        )
        records.append(
            {
                "ranker_name": ranker_name,
                "phase_b_eligible": not reasons,
                "gate_failures": reasons,
                "validation_expectancy_delta_r": validation_delta,
                "validation_maximum_drawdown_r": validation_drawdown,
            }
        )
    result = pd.DataFrame(records)
    if result.empty:
        return result
    eligible = result[result["phase_b_eligible"]].sort_values(
        [
            "validation_expectancy_delta_r",
            "validation_maximum_drawdown_r",
            "ranker_name",
        ],
        ascending=[False, True, True],
        kind="stable",
    )
    selected = set(eligible.head(maximum_rankers)["ranker_name"])
    result["shortlisted_for_phase_b_review"] = result["ranker_name"].isin(selected)
    return result.sort_values("ranker_name", kind="stable").reset_index(drop=True)
