"""Run the preregistered Phase A portfolio-ranking infrastructure."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research.engine.data import load_price_csv
from research.engine.leader_features import load_current_sector_industry
from research.engine.portfolio_ranking import (
    DEFAULT_RESEARCH_SEED,
    annotate_candidate_eligibility,
    enrich_point_in_time_ranking_factors,
    evaluate_ranking_arms,
    phase_b_advancement_shortlist,
)
from research.engine.reporting import ensure_research_output_path
from research.engine.reproducibility import git_state, sha256_file


DEFAULT_EXPERIMENT = Path("research/experiments/portfolio_ranking_phase_a_v1.json")
REQUIRED_PLAN_COLUMNS = {
    "plan_entry_date",
    "plan_exit_date",
    "plan_entry",
    "Initial Stop",
    "plan_realised_r",
    "plan_mfe_r",
    "plan_mae_r",
    "plan_holding_sessions",
}
OUTCOME_COLUMNS = {
    "plan_realised_r",
    "plan_mfe_r",
    "plan_mae_r",
    "plan_holding_sessions",
}


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--candidates", type=Path, required=True)
    command.add_argument("--prices", type=Path, required=True)
    command.add_argument("--benchmark", type=Path, required=True)
    command.add_argument("--experiment", type=Path, default=DEFAULT_EXPERIMENT)
    command.add_argument(
        "--output-dir",
        type=Path,
        default=Path("research/output/portfolio_ranking_phase_a_v1"),
    )
    command.add_argument(
        "--engineering-replay",
        action="store_true",
        help=(
            "Evaluate all supplied rows as an explicitly non-validating pipeline "
            "replay; the Phase B shortlist gate is disabled."
        ),
    )
    return command


def _strict_bool(value: object, *, label: str) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    text = str(value).strip().casefold()
    if text in {"true", "1"}:
        return True
    if text in {"false", "0"}:
        return False
    raise ValueError(f"{label} must contain only explicit booleans")


def prepare_candidate_journal(candidates: pd.DataFrame) -> pd.DataFrame:
    """Validate and freeze the non-ranking candidate contract."""

    required = {
        "as_of_date",
        "ticker",
        "canonical_eligible",
        "canonical_blocked_reason",
        "candidate_risk_r",
        "effective_heat_limit_r",
        "Final Score",
        "Industry",
        "Sector",
        "Industry Composite Score",
        *REQUIRED_PLAN_COLUMNS,
    }
    missing = sorted(required - set(candidates.columns))
    if missing:
        raise ValueError("candidate journal columns are missing: " + ", ".join(missing))
    result = candidates.copy()
    result["canonical_eligible"] = result["canonical_eligible"].map(
        lambda value: _strict_bool(value, label="canonical_eligible")
    )
    if "plan_triggered" in result:
        plan_triggered = result["plan_triggered"].map(
            lambda value: _strict_bool(value, label="plan_triggered")
        )
    else:
        plan_triggered = pd.to_datetime(
            result["plan_entry_date"], errors="coerce"
        ).notna()
    result["evaluation_eligible"] = result["canonical_eligible"] & plan_triggered
    reasons = result["canonical_blocked_reason"].fillna("").astype(str).str.strip()
    reasons = reasons.mask(
        result["canonical_eligible"] & ~plan_triggered, "PLAN_NOT_TRIGGERED"
    )
    result["evaluation_blocked_reason"] = reasons
    result = annotate_candidate_eligibility(
        result,
        eligibility_column="evaluation_eligible",
        blocked_reason_column="evaluation_blocked_reason",
    )
    eligible = result["ranking_eligible"]
    entry_dates = pd.to_datetime(result["plan_entry_date"], errors="coerce")
    missing_entry = eligible & entry_dates.isna()
    if missing_entry.any():
        row = result.loc[missing_entry, ["as_of_date", "ticker"]].iloc[0]
        raise ValueError(
            "eligible candidate has no observable plan entry date: "
            f"{row['as_of_date']}/{row['ticker']}"
        )
    for column in ("candidate_risk_r", "effective_heat_limit_r"):
        numeric = pd.to_numeric(result[column], errors="coerce")
        invalid = eligible & (~np.isfinite(numeric) | numeric.le(0))
        if invalid.any():
            row = result.loc[invalid, ["as_of_date", "ticker"]].iloc[0]
            raise ValueError(
                f"eligible candidate has invalid {column}: "
                f"{row['as_of_date']}/{row['ticker']}"
            )
        result[column] = numeric
    return result


def validate_runner_data_gate(
    experiment: Mapping[str, Any], *, engineering_replay: bool
) -> str:
    """Block formal evidence before any current-classification data is loaded."""

    if engineering_replay:
        return "ENGINEERING_CURRENT_CLASSIFICATION_NON_VALIDATING"
    gate = experiment.get("formal_data_gate")
    if not isinstance(gate, Mapping):
        raise ValueError("formal_data_gate must be declared for a formal run")
    status = str(gate.get("status", "")).strip().upper()
    if status != "READY":
        raise ValueError(
            f"formal portfolio-ranking data gate is {status or 'UNDECLARED'}; "
            "use --engineering-replay only for a non-validating pipeline check"
        )
    provenance = str(gate.get("classification_provenance", "")).strip().upper()
    if provenance != "POINT_IN_TIME_EFFECTIVE_DATED":
        raise ValueError(
            "formal portfolio ranking requires point-in-time effective-dated "
            "classification provenance"
        )
    if gate.get("formal_runner_enabled") is not True:
        raise ValueError(
            "formal portfolio-ranking runner remains disabled until its "
            "effective-dated classification loader is implemented and verified"
        )
    raise ValueError(
        "formal effective-dated classification loading is not implemented; "
        "current classifications are prohibited for formal evidence"
    )


def _load_benchmark(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    histories, diagnostics = load_price_csv(path)
    if "SPY" in histories:
        return histories["SPY"], diagnostics
    if len(histories) == 1:
        return next(iter(histories.values())), diagnostics
    raise ValueError("benchmark input must contain SPY or exactly one symbol")


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if pd.isna(value):
        return None
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=_json_default),
        encoding="utf-8",
    )


def _stage_rows(
    candidates: pd.DataFrame,
    experiment: dict[str, Any],
    *,
    engineering_replay: bool,
) -> list[tuple[str, pd.DataFrame, pd.Timestamp]]:
    if engineering_replay:
        observation_end = pd.to_datetime(
            candidates["plan_exit_date"], errors="coerce"
        ).max()
        if pd.isna(observation_end):
            observation_end = pd.Timestamp(candidates["as_of_date"].max())
        return [("engineering_replay", candidates.copy(), observation_end)]

    dates = pd.to_datetime(candidates["as_of_date"], errors="raise")
    stages: list[tuple[str, pd.DataFrame, pd.Timestamp]] = []
    for stage_name in ("development", "validation"):
        period = experiment["formal_periods"][stage_name]
        mask = dates.between(period["signal_start"], period["signal_end"])
        rows = candidates.loc[mask].copy()
        if not rows.empty:
            observation_end = pd.Timestamp(period["outcomes_observed_through"])
            entry_dates = pd.to_datetime(rows["plan_entry_date"], errors="coerce")
            exit_dates = pd.to_datetime(rows["plan_exit_date"], errors="coerce")
            realised = pd.to_numeric(rows["plan_realised_r"], errors="coerce")
            impossible_outcome = exit_dates.isna() & realised.notna()
            if impossible_outcome.any():
                row = rows.loc[impossible_outcome, ["as_of_date", "ticker"]].iloc[0]
                raise ValueError(
                    "realised outcome has no plan exit date: "
                    f"{row['as_of_date']}/{row['ticker']}"
                )
            future_entry = rows["ranking_eligible"] & (
                entry_dates.isna() | entry_dates.gt(observation_end)
            )
            rows.loc[future_entry, "ranking_eligible"] = False
            rows.loc[future_entry, "eligibility_blocked_reason"] = (
                "PLAN_NOT_TRIGGERED_BY_STAGE_CUTOFF"
            )
            crossing_outcome = exit_dates.gt(observation_end)
            rows["stage_outcome_purged"] = crossing_outcome
            rows.loc[crossing_outcome, "plan_exit_date"] = pd.NaT
            rows.loc[crossing_outcome, list(OUTCOME_COLUMNS)] = np.nan
            stages.append(
                (
                    stage_name,
                    rows,
                    observation_end,
                )
            )
    if not stages:
        raise ValueError(
            "candidate journal has no rows in the preregistered development or "
            "validation windows; use --engineering-replay only for a labelled "
            "non-validating pipeline check"
        )
    return stages


def main() -> int:
    args = parser().parse_args()
    project_root = Path(__file__).resolve().parents[1]
    experiment_path = (
        args.experiment
        if args.experiment.is_absolute()
        else project_root / args.experiment
    ).resolve()
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    if experiment["experiment_id"] != "PORTFOLIO_RANKING_PHASE_A_V1":
        raise ValueError("unexpected portfolio-ranking experiment id")
    classification_mode = validate_runner_data_gate(
        experiment, engineering_replay=args.engineering_replay
    )

    candidate_path = (
        args.candidates
        if args.candidates.is_absolute()
        else project_root / args.candidates
    ).resolve()
    price_path = (
        args.prices if args.prices.is_absolute() else project_root / args.prices
    ).resolve()
    benchmark_path = (
        args.benchmark
        if args.benchmark.is_absolute()
        else project_root / args.benchmark
    ).resolve()
    output_dir = ensure_research_output_path(project_root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates = prepare_candidate_journal(pd.read_csv(candidate_path))
    histories, price_diagnostics = load_price_csv(price_path)
    benchmark, benchmark_diagnostics = _load_benchmark(benchmark_path)
    if classification_mode != "ENGINEERING_CURRENT_CLASSIFICATION_NON_VALIDATING":
        raise AssertionError("formal classification mode must fail closed above")
    sectors, industries = load_current_sector_industry(project_root)
    candidates = enrich_point_in_time_ranking_factors(
        candidates,
        histories,
        benchmark,
        sectors=sectors,
        industries=industries,
    )
    sessions = pd.DatetimeIndex(benchmark.index).sort_values()
    portfolio_contract = experiment["portfolio_evaluation"]["runner_contract"]
    common_risk = {"source_column": portfolio_contract["candidate_risk_source_column"]}
    common_portfolio = {
        "maximum_positions": portfolio_contract["maximum_positions"],
        "maximum_heat_r": portfolio_contract["maximum_heat_ceiling_r"],
        "maximum_heat_r_source_column": portfolio_contract[
            "effective_heat_source_column"
        ],
        "candidate_concentration": portfolio_contract["candidate_concentration"],
    }

    metric_frames: list[pd.DataFrame] = []
    audit_frames: list[pd.DataFrame] = []
    curve_frames: list[pd.DataFrame] = []
    intervals: dict[str, Any] = {}
    for stage_name, stage_candidates, observation_end in _stage_rows(
        candidates,
        experiment,
        engineering_replay=args.engineering_replay,
    ):
        metrics, audit, curves, stage_intervals = evaluate_ranking_arms(
            stage_candidates,
            histories,
            sessions,
            risk=common_risk,
            portfolio=common_portfolio,
            observation_end=observation_end,
            research_seed=int(experiment["random_baseline"]["seed"]),
        )
        for frame in (metrics, audit, curves):
            frame.insert(0, "stage", stage_name)
        metric_frames.append(metrics)
        audit_frames.append(audit)
        curve_frames.append(curves)
        intervals[stage_name] = stage_intervals

    all_metrics = pd.concat(metric_frames, ignore_index=True)
    all_audit = pd.concat(audit_frames, ignore_index=True)
    all_curves = pd.concat(curve_frames, ignore_index=True)
    if args.engineering_replay or set(all_metrics["stage"]) != {
        "development",
        "validation",
    }:
        shortlist = pd.DataFrame(
            columns=[
                "ranker_name",
                "phase_b_eligible",
                "gate_failures",
                "shortlisted_for_phase_b_review",
            ]
        )
        gate_status = "NOT_APPLIED_ENGINEERING_OR_INCOMPLETE_FORMAL_STAGES"
    else:
        shortlist = phase_b_advancement_shortlist(
            all_metrics, experiment["phase_b_advancement_gate"]
        )
        gate_status = "APPLIED_SHORTLIST_ONLY_NO_CHAMPION"

    all_metrics.assign(
        blocked_reason_counts=all_metrics["blocked_reason_counts"].map(
            lambda value: json.dumps(value, sort_keys=True)
        ),
        rejection_reasons=all_metrics["rejection_reasons"].map(
            lambda value: json.dumps(value, sort_keys=True)
        ),
    ).to_csv(output_dir / "portfolio_metrics.csv", index=False)
    all_audit.to_csv(output_dir / "ranking_audit.csv", index=False)
    all_curves.to_csv(output_dir / "portfolio_curve.csv", index=False)
    shortlist.assign(
        gate_failures=shortlist.get("gate_failures", pd.Series(dtype=object)).map(
            lambda value: json.dumps(value, sort_keys=True)
        )
    ).to_csv(output_dir / "phase_b_review_shortlist.csv", index=False)
    _write_json(output_dir / "bootstrap_intervals.json", intervals)

    commit, dirty = git_state(project_root)
    manifest = {
        "experiment_id": experiment["experiment_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "git_dirty": dirty,
        "engineering_replay": args.engineering_replay,
        "evidence_status": (
            "ENGINEERING_ONLY_NOT_VALIDATION_EVIDENCE"
            if args.engineering_replay
            else "FORMAL_WINDOWS_NO_AUTOMATIC_CHAMPION"
        ),
        "advancement_gate_status": gate_status,
        "production_effect": "NONE",
        "phase_b_implemented": False,
        "phase_c_implemented": False,
        "classification_limitation": (
            "sector_industry_cache.csv is current, not effective-dated; outputs "
            "cannot establish point-in-time classification correctness"
        ),
        "classification_mode": classification_mode,
        "inputs": {
            "candidates": str(candidate_path),
            "candidates_sha256": sha256_file(candidate_path),
            "prices": str(price_path),
            "prices_sha256": sha256_file(price_path),
            "benchmark": str(benchmark_path),
            "benchmark_sha256": sha256_file(benchmark_path),
            "experiment": str(experiment_path),
            "experiment_sha256": sha256_file(experiment_path),
        },
        "price_diagnostics": price_diagnostics,
        "benchmark_diagnostics": benchmark_diagnostics,
        "research_seed": int(
            experiment.get("random_baseline", {}).get("seed", DEFAULT_RESEARCH_SEED)
        ),
        "row_counts": {
            "candidate_rows": len(candidates),
            "audit_rows": len(all_audit),
            "metric_rows": len(all_metrics),
        },
    }
    _write_json(output_dir / "run_manifest.json", manifest)
    print(f"Phase A portfolio-ranking artifacts written to {output_dir}")
    print(f"Advancement gate: {gate_status}; no champion selected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
