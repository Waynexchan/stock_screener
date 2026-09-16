"""Build a reproducible research journal from immutable production snapshots."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from research.engine.ablation import with_without_summary
from research.engine.data import load_price_csv
from research.engine.forward_execution import PLAN_OUTCOME_COLUMNS, simulate_frozen_plan
from research.engine.forward_portfolio import (
    build_independent_episodes,
    evaluate_portfolio_variants,
    ticker_cluster_bootstrap_ci,
)
from research.engine.market_features import enrich_market_features
from research.engine.models import FeatureRecord, OutcomeRecord
from research.engine.outcomes import calculate_forward_outcomes
from research.engine.reporting import ensure_research_output_path
from research.engine.reproducibility import git_state, sha256_file

EXPECTED_SNAPSHOT_FILES = {
    "candidates.csv",
    "market.json",
    "portfolio.json",
    "config.json",
    "metadata.json",
}


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--prices", type=Path)
    command.add_argument("--benchmark", type=Path)
    command.add_argument(
        "--snapshot-root", type=Path, default=Path("output/forward_snapshots")
    )
    command.add_argument(
        "--output-dir", type=Path, default=Path("research/output/forward_test_v1")
    )
    command.add_argument(
        "--experiment",
        type=Path,
        default=Path("research/experiments/forward_test_v1.json"),
    )
    command.add_argument(
        "--events",
        type=Path,
        help="Append-only JSONL operational/actual-execution event journal.",
    )
    return command


def _truth(value: object) -> bool:
    return value is True or str(value).strip().casefold() == "true"


def load_experiment(path: Path) -> dict[str, Any]:
    experiment = json.loads(path.read_text(encoding="utf-8"))
    mode = str(experiment.get("collection_mode", "")).upper()
    if mode not in {"PILOT", "FORMAL"}:
        raise ValueError("collection_mode must be PILOT or FORMAL")
    variants = experiment.get("portfolio_experiment", {}).get("variants", [])
    if mode == "FORMAL":
        if experiment.get("status") != "PREREGISTERED_ACTIVE_COLLECTION":
            raise ValueError("formal epoch must be preregistered and active")
        roles = [str(item.get("role", "")).upper() for item in variants]
        if roles.count("CHAMPION") != 1 or "CHALLENGER" not in roles:
            raise ValueError("formal epoch requires one champion and a challenger")
        frozen = experiment.get("frozen_epoch", {})
        required = (
            "strategy_epoch_id",
            "git_commit",
            "config_hash",
            "universe_hash",
            "universe_methodology_version",
            "data_provider_name",
            "data_provider_version",
        )
        missing = [name for name in required if not frozen.get(name)]
        if missing:
            raise ValueError(
                "formal epoch has unresolved frozen fields: " + ", ".join(missing)
            )
        if not experiment.get("start_date"):
            raise ValueError("formal epoch requires a start_date")
    return experiment


def _snapshot_audit(run_dir: Path, experiment: dict[str, Any]) -> dict[str, Any]:
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    artifact_hashes = metadata.get("artifact_hashes", {})
    verified_files: list[str] = []
    for name, expected in artifact_hashes.items():
        path = run_dir / str(name)
        if not path.is_file() or sha256_file(path) != str(expected):
            raise ValueError(f"snapshot artifact hash mismatch: {path}")
        verified_files.append(str(name))
    mode = str(experiment["collection_mode"]).upper()
    frozen = experiment.get("frozen_epoch", {})
    mismatches: list[str] = []
    for metadata_key, frozen_key in (
        ("git_commit", "git_commit"),
        ("config_hash", "config_hash"),
        ("universe_hash", "universe_hash"),
    ):
        expected = frozen.get(frozen_key)
        if expected and metadata.get(metadata_key) != expected:
            mismatches.append(metadata_key)
    provider = metadata.get("data_provider", {})
    if frozen.get("data_provider_name") and provider.get("name") != frozen.get(
        "data_provider_name"
    ):
        mismatches.append("data_provider_name")
    if frozen.get("data_provider_version") and provider.get("version") != frozen.get(
        "data_provider_version"
    ):
        mismatches.append("data_provider_version")
    if frozen.get("universe_methodology_version") and metadata.get(
        "universe_methodology_version"
    ) != frozen.get("universe_methodology_version"):
        mismatches.append("universe_methodology_version")
    if mode == "FORMAL":
        if metadata.get("git_dirty") is not False:
            mismatches.append("git_dirty")
        if int(metadata.get("snapshot_schema_version", 0)) < 2:
            mismatches.append("snapshot_schema_version")
        if "candidates.csv" not in verified_files:
            mismatches.append("candidate_file_hash")
        if metadata.get("candidate_record_hash") != artifact_hashes.get(
            "candidates.csv"
        ):
            mismatches.append("candidate_record_hash")
        policy = metadata.get("policy", {})
        declared = experiment.get("trading_policy", {})
        if policy.get("earnings") != declared.get("earnings_snapshot_policy"):
            mismatches.append("earnings_policy")
        if policy.get("market_cap") != declared.get("market_cap_snapshot_policy"):
            mismatches.append("market_cap_policy")
        if mismatches:
            raise ValueError(
                f"snapshot outside frozen epoch ({run_dir}): "
                + ", ".join(sorted(set(mismatches)))
            )
    return {
        "snapshot_path": str(run_dir.resolve()),
        "signal_date": metadata.get("signal_trading_date"),
        "run_id": run_dir.name,
        "git_commit": metadata.get("git_commit"),
        "git_dirty": metadata.get("git_dirty"),
        "config_hash": metadata.get("config_hash"),
        "universe_hash": metadata.get("universe_hash"),
        "universe_methodology_version": metadata.get("universe_methodology_version"),
        "candidate_record_hash": metadata.get("candidate_record_hash"),
        "candidate_file_hash_status": (
            "VERIFIED" if "candidates.csv" in verified_files else "LEGACY_UNVERIFIABLE"
        ),
        "snapshot_schema_version": metadata.get("snapshot_schema_version", 1),
        "cohort_mismatches": "|".join(sorted(set(mismatches))),
    }


def earliest_complete_snapshots(
    root: Path, experiment: dict[str, Any] | None = None
) -> list[Path]:
    selected: list[Path] = []
    if not root.exists():
        return selected
    start_date = str((experiment or {}).get("start_date", ""))
    end_date = str((experiment or {}).get("end_date", ""))
    for date_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        if start_date and date_dir.name < start_date:
            continue
        if end_date and date_dir.name > end_date:
            continue
        complete: list[Path] = []
        for run_dir in sorted(path for path in date_dir.iterdir() if path.is_dir()):
            if EXPECTED_SNAPSHOT_FILES <= {
                path.name for path in run_dir.iterdir() if path.is_file()
            }:
                metadata = json.loads(
                    (run_dir / "metadata.json").read_text(encoding="utf-8")
                )
                candidates = pd.read_csv(run_dir / "candidates.csv")
                if str(metadata.get("signal_trading_date")) == date_dir.name and int(
                    metadata.get("candidate_count", -1)
                ) == len(candidates):
                    complete.append(run_dir)
        if complete:
            selected.append(complete[0])
    return selected


def load_snapshot_signals(
    root: Path,
    experiment: dict[str, Any] | None = None,
    *,
    audit_rows: list[dict[str, Any]] | None = None,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for run_dir in earliest_complete_snapshots(root, experiment):
        audit = _snapshot_audit(run_dir, experiment) if experiment else None
        if audit is not None and audit_rows is not None:
            audit_rows.append(audit)
        frame = pd.read_csv(run_dir / "candidates.csv")
        metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
        frame["snapshot_row_order"] = range(len(frame))
        frame["snapshot_run_id"] = run_dir.name
        frame["snapshot_path"] = str(run_dir.resolve())
        frame["snapshot_generated_at"] = metadata.get("generated_timestamp")
        frame["snapshot_git_commit"] = metadata.get("git_commit")
        frame["snapshot_git_dirty"] = metadata.get("git_dirty")
        frame["snapshot_config_hash"] = metadata.get("config_hash")
        frame["snapshot_universe_hash"] = metadata.get("universe_hash")
        frame["snapshot_candidate_record_hash"] = metadata.get("candidate_record_hash")
        frame["snapshot_candidate_file_hash_status"] = (
            audit.get("candidate_file_hash_status") if audit else "NOT_CHECKED"
        )
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).drop_duplicates(
        ["Signal Date", "Ticker"], keep="first"
    )


def outcome_for_candidate(
    ticker: str, signal_date: str, history: pd.DataFrame
) -> dict[str, Any]:
    feature = FeatureRecord(
        signal_date=signal_date,
        ticker=ticker,
        universe_version="immutable production snapshot",
        data_as_of=signal_date,
        price=float("nan"),
        volume=float("nan"),
        dollar_volume=float("nan"),
        average_volume_50d=float("nan"),
        valid_data=True,
        tradable=True,
        stage2_pass=True,
        structural_stop=None,
        model_0_signal=True,
    )
    return calculate_forward_outcomes(feature, history).to_dict()


EVENT_TYPES = {
    "ACTUAL_FILL",
    "EARNINGS_EXCLUSION",
    "EARNINGS_SCREEN_COMPLETE",
    "HALT",
    "MISSED_RUN",
    "ORDER_CANCELLED",
    "PARTIAL_FILL",
    "SPLIT",
}


def load_execution_events(path: Path | None) -> tuple[pd.DataFrame, str | None]:
    if path is None:
        return pd.DataFrame(), None
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    prior_recorded_at: datetime | None = None
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        record = json.loads(line)
        event_id = str(record.get("event_id", "")).strip()
        event_type = str(record.get("event_type", "")).strip().upper()
        if not event_id or event_id in seen:
            raise ValueError(f"invalid or duplicate event_id at line {line_number}")
        if event_type not in EVENT_TYPES:
            raise ValueError(
                f"unsupported event_type at line {line_number}: {event_type}"
            )
        if not record.get("recorded_at") or not record.get("signal_date"):
            raise ValueError(
                f"event lacks recorded_at/signal_date at line {line_number}"
            )
        try:
            recorded_at = datetime.fromisoformat(
                str(record["recorded_at"]).replace("Z", "+00:00")
            )
            pd.Timestamp(str(record["signal_date"]))
        except ValueError as exc:
            raise ValueError(
                f"invalid event timestamp/date at line {line_number}"
            ) from exc
        if recorded_at.tzinfo is None:
            raise ValueError(f"recorded_at lacks timezone at line {line_number}")
        if prior_recorded_at is not None and recorded_at < prior_recorded_at:
            raise ValueError("event journal is not in append-time order")
        prior_recorded_at = recorded_at
        seen.add(event_id)
        rows.append({**record, "event_type": event_type, "source_line": line_number})
    return pd.DataFrame(rows), sha256_file(path)


def validate_manual_earnings_journal(
    experiment: dict[str, Any], snapshot_dates: list[str], events: pd.DataFrame
) -> None:
    if experiment.get("trading_policy", {}).get("earnings_policy") != (
        "MANUAL_FAIL_CLOSED_JOURNAL"
    ):
        return
    if events.empty:
        raise ValueError("formal manual earnings policy requires an event journal")
    completed = set(
        events.loc[
            events["event_type"].eq("EARNINGS_SCREEN_COMPLETE"), "signal_date"
        ].astype(str)
    )
    missing = sorted(set(snapshot_dates) - completed)
    if missing:
        raise ValueError(
            "earnings review is missing for signal dates: " + ", ".join(missing)
        )
    completions = events[events["event_type"].eq("EARNINGS_SCREEN_COMPLETE")]
    completion_required = {"reviewed_at", "source"}
    if not completion_required <= set(completions) or completions[
        list(completion_required)
    ].isna().any(axis=None):
        raise ValueError("earnings review completion requires reviewed_at and source")
    if (
        pd.to_datetime(completions["reviewed_at"], errors="coerce", utc=True)
        .isna()
        .any()
    ):
        raise ValueError("earnings review completion has invalid reviewed_at")
    exclusions = events[events["event_type"].eq("EARNINGS_EXCLUSION")]
    required = {"ticker", "earnings_date", "reviewed_at", "reason"}
    if not exclusions.empty and (
        not required <= set(exclusions)
        or exclusions[list(required)].isna().any(axis=None)
    ):
        raise ValueError("earnings exclusions require ticker/date/reviewed_at/reason")
    if not exclusions.empty and (
        pd.to_datetime(exclusions["reviewed_at"], errors="coerce", utc=True)
        .isna()
        .any()
        or pd.to_datetime(exclusions["earnings_date"], errors="coerce").isna().any()
    ):
        raise ValueError("earnings exclusion has invalid date or reviewed_at")


def add_filter_flags(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    missing = pd.Series(pd.NA, index=result.index, dtype="object")
    decision_actionable = (
        result.get("Final Decision", pd.Series("", index=result.index))
        .astype(str)
        .isin({"FULL", "HALF"})
    )
    if "Actionable" in result:
        reported_actionable = result["Actionable"].map(_truth)
    else:
        reported_actionable = decision_actionable
    result["snapshot_actionable"] = decision_actionable & reported_actionable
    result["pass_recent_rs_70"] = pd.to_numeric(
        result.get("Recent RS Score", missing), errors="coerce"
    ).ge(70)
    result["pass_long_term_rs_75"] = pd.to_numeric(
        result.get("RS Score", missing), errors="coerce"
    ).ge(75)
    result["pass_volume_0_30"] = pd.to_numeric(
        result.get("Volume Ratio", missing), errors="coerce"
    ).ge(0.30)
    result["pass_beta_0_8"] = pd.to_numeric(
        result.get("rolling_beta_126", missing), errors="coerce"
    ).ge(0.8)
    sector = (
        result.get("Sector", pd.Series("", index=result.index)).astype(str).str.strip()
    )
    known_sector = ~sector.str.casefold().isin({"", "unknown", "n/a", "none", "nan"})
    result["sector_known"] = known_sector
    result["exclude_utility"] = known_sector & ~sector.str.casefold().eq("utilities")
    result["pass_not_overextended"] = ~result.get(
        "Extension Status", pd.Series("", index=result.index)
    ).astype(str).str.casefold().eq("overextended")
    result["pass_industry_qualified"] = result.get(
        "Industry Qualified", pd.Series(False, index=result.index)
    ).map(_truth)
    result["pass_sister_confirmation"] = result.get(
        "Sister Confirmation", pd.Series(False, index=result.index)
    ).map(_truth)
    result["pass_structural_rr_2"] = pd.to_numeric(
        result.get("Reward/Risk Ratio", missing), errors="coerce"
    ).ge(2.0)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    experiment_path = args.experiment
    if not experiment_path.is_absolute():
        experiment_path = project_root / experiment_path
    experiment = load_experiment(experiment_path)
    output_root = ensure_research_output_path(project_root, args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    audit_rows: list[dict[str, Any]] = []
    signals = load_snapshot_signals(
        args.snapshot_root, experiment, audit_rows=audit_rows
    )
    if signals.empty:
        raise ValueError("no complete immutable forward snapshots found")
    signals = signals.rename(columns={"Signal Date": "signal_date", "Ticker": "ticker"})
    histories: dict[str, pd.DataFrame] = {}
    benchmark: pd.DataFrame | None = None
    if args.prices:
        histories, _ = load_price_csv(args.prices)
    if args.benchmark:
        benchmark_histories, _ = load_price_csv(args.benchmark)
        benchmark = benchmark_histories.get("SPY")
    if histories and benchmark is not None:
        market = enrich_market_features(
            signals[["signal_date", "ticker"]], histories, benchmark
        )
        signals = signals.merge(
            market[["signal_date", "ticker", "rolling_beta_126"]],
            on=["signal_date", "ticker"],
            how="left",
        )
    else:
        signals["rolling_beta_126"] = pd.NA
    signals = add_filter_flags(signals)
    outcomes: list[dict[str, Any]] = []
    plan_outcomes: list[dict[str, Any]] = []
    for row in signals.to_dict("records"):
        history = histories.get(str(row["ticker"]))
        if history is not None:
            outcomes.append(
                outcome_for_candidate(
                    str(row["ticker"]), str(row["signal_date"]), history
                )
            )
            plan_outcomes.append(simulate_frozen_plan(row, history))
    outcome_frame = pd.DataFrame(outcomes).reindex(
        columns=list(OutcomeRecord.__dataclass_fields__)
    )
    journal = signals.merge(outcome_frame, on=["signal_date", "ticker"], how="left")
    plan_frame = pd.DataFrame(plan_outcomes)
    if plan_frame.empty:
        plan_frame = pd.DataFrame(columns=PLAN_OUTCOME_COLUMNS)
    journal = journal.merge(plan_frame, on=["signal_date", "ticker"], how="left")
    horizon_columns = [f"future_{days}d_return" for days in (5, 10, 20, 40)]
    journal["maximum_mature_horizon"] = journal.apply(
        lambda row: max(
            [
                days
                for days in (5, 10, 20, 40)
                if pd.notna(row.get(f"future_{days}d_return"))
            ],
            default=0,
        ),
        axis=1,
    )
    summaries: dict[str, Any] = {}
    flag_columns = [
        column for column in journal if column.startswith(("pass_", "exclude_"))
    ]
    for flag in flag_columns:
        summaries[flag] = {}
        for outcome in horizon_columns:
            summaries[flag][outcome] = with_without_summary(
                journal,
                feature_column=flag,
                outcome_column=outcome,
                included=lambda values: values.fillna(False).astype(bool),
            )
        summaries[flag]["plan_realised_r"] = with_without_summary(
            journal,
            feature_column=flag,
            outcome_column="plan_realised_r",
            included=lambda values: values.fillna(False).astype(bool),
        )
    observation_end = max(
        (pd.DatetimeIndex(history.index).max() for history in histories.values()),
        default=pd.Timestamp(max(journal["signal_date"].astype(str))),
    )
    journal, episodes = build_independent_episodes(journal, observation_end)
    production_accepted = journal[journal["snapshot_actionable"].eq(True)].copy()
    events_path = args.events
    if events_path is not None and not events_path.is_absolute():
        events_path = project_root / events_path
    events, events_hash = load_execution_events(events_path)
    snapshot_dates = sorted(journal["signal_date"].astype(str).unique())
    validate_manual_earnings_journal(experiment, snapshot_dates, events)
    bootstrap = experiment.get("uncertainty", {})
    bootstrap_seed = int(bootstrap.get("seed", 20260916))
    bootstrap_resamples = int(bootstrap.get("resamples", 2000))
    mature_episodes = episodes[
        pd.to_numeric(episodes.get("plan_realised_r"), errors="coerce").notna()
    ].copy()
    episode_interval = ticker_cluster_bootstrap_ci(
        mature_episodes,
        value_column="plan_realised_r",
        seed=bootstrap_seed,
        resamples=bootstrap_resamples,
    )
    variants = experiment.get("portfolio_experiment", {}).get("variants", [])
    sessions = (
        pd.DatetimeIndex(benchmark.index)
        if benchmark is not None
        else pd.DatetimeIndex(
            sorted(
                {
                    pd.Timestamp(session)
                    for history in histories.values()
                    for session in history.index
                }
            )
        )
    )
    portfolio_metrics = pd.DataFrame()
    portfolio_ledger = pd.DataFrame()
    portfolio_curve = pd.DataFrame()
    portfolio_intervals: dict[str, Any] = {}
    if variants and histories and not sessions.empty:
        (
            portfolio_metrics,
            portfolio_ledger,
            portfolio_curve,
            portfolio_intervals,
        ) = evaluate_portfolio_variants(
            journal[journal["plan_triggered"].eq(True)].copy(),
            histories,
            sessions,
            variants,
            observation_end=observation_end,
            bootstrap_seed=bootstrap_seed,
            bootstrap_resamples=bootstrap_resamples,
        )
    minimum_review_sample = int(
        experiment["sample_definition"]["minimum_mature_independent_episodes"]
    )
    champion_mature_count = 0
    portfolio_valid = False
    if not portfolio_metrics.empty:
        champion = portfolio_metrics[portfolio_metrics["role"].eq("CHAMPION")]
        if not champion.empty:
            champion_mature_count = int(
                champion.iloc[0]["mature_accepted_episode_count"]
            )
        portfolio_valid = bool(portfolio_metrics["missing_mark_count"].eq(0).all())
    audit_frame = pd.DataFrame(audit_rows)
    cohort_valid = bool(
        not audit_frame.empty
        and audit_frame["cohort_mismatches"].fillna("").eq("").all()
        and audit_frame["candidate_file_hash_status"].eq("VERIFIED").all()
    )
    formal = experiment["collection_mode"] == "FORMAL"
    review_eligible = bool(
        formal
        and cohort_valid
        and portfolio_valid
        and len(mature_episodes) >= minimum_review_sample
        and champion_mature_count >= minimum_review_sample
    )
    generated_at = datetime.now(timezone.utc)
    run_id = generated_at.strftime("%Y%m%dT%H%M%S%fZ")
    output_dir = output_root / "runs" / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    journal.to_csv(output_dir / "raw_snapshot_journal.csv", index=False)
    episodes.to_csv(output_dir / "independent_episodes.csv", index=False)
    production_accepted.to_csv(
        output_dir / "production_accepted_candidates.csv", index=False
    )
    audit_frame.to_csv(output_dir / "snapshot_audit.csv", index=False)
    events.to_csv(output_dir / "execution_events.csv", index=False)
    portfolio_metrics.to_csv(output_dir / "portfolio_metrics.csv", index=False)
    portfolio_ledger.to_csv(output_dir / "portfolio_ledger.csv", index=False)
    portfolio_curve.to_csv(output_dir / "portfolio_equity_curve.csv", index=False)
    (output_dir / "filter_outcomes.json").write_text(
        json.dumps(summaries, indent=2, sort_keys=True), encoding="utf-8"
    )
    confidence_intervals = {
        "all_independent_mature_episodes": episode_interval,
        "portfolio_variants": portfolio_intervals,
    }
    (output_dir / "confidence_intervals.json").write_text(
        json.dumps(confidence_intervals, indent=2, sort_keys=True), encoding="utf-8"
    )
    metadata = {
        "experiment_id": experiment["experiment_id"],
        "strategy_epoch_id": experiment.get("frozen_epoch", {}).get(
            "strategy_epoch_id"
        ),
        "collection_mode": experiment["collection_mode"],
        "research_label": experiment["research_label"],
        "evidence_status": (
            "FORMAL_FROZEN_FORWARD_COLLECTION"
            if formal
            else "ENGINEERING_PILOT_NOT_FORMAL"
        ),
        "snapshot_dates": snapshot_dates,
        "raw_snapshot_row_count": len(journal),
        "raw_unique_ticker_count": int(journal["ticker"].nunique()),
        "repeated_ticker_row_count": int(
            journal["ticker"].duplicated(keep=False).sum()
        ),
        "independent_episode_count": len(episodes),
        "mature_independent_episode_count": len(mature_episodes),
        "overlap_excluded_count": int(
            journal["episode_exclusion_reason"].eq("SAME_TICKER_OVERLAP").sum()
        ),
        "production_accepted_candidate_count": len(production_accepted),
        "minimum_review_sample": minimum_review_sample,
        "minimum_review_sample_unit": "MATURE_INDEPENDENT_EPISODES",
        "review_eligible": review_eligible,
        "cohort_valid": cohort_valid,
        "portfolio_valid": portfolio_valid,
        "mature_5d_count": int(journal["future_5d_return"].notna().sum()),
        "plan_triggered_count": int(journal["plan_triggered"].eq(True).sum()),
        "plan_mature_count": int(journal["plan_realised_r"].notna().sum()),
        "plan_open_unmatured_count": int(
            journal["plan_outcome_status"].eq("OPEN_UNMATURED").sum()
        ),
        "actionable_candidate_count": int(journal["snapshot_actionable"].sum()),
        "actionable_plan_triggered_count": int(
            (journal["snapshot_actionable"] & journal["plan_triggered"].eq(True)).sum()
        ),
        "actionable_plan_mature_count": int(
            (journal["snapshot_actionable"] & journal["plan_realised_r"].notna()).sum()
        ),
        "maximum_mature_horizon": int(journal["maximum_mature_horizon"].max()),
        "prices_supplied": bool(args.prices),
        "plan_trigger_r_outcomes": "ENABLED_CONSERVATIVE_DAILY_BAR_MODEL",
        "execution_event_count": len(events),
        "execution_event_journal_hash": events_hash,
        "research_decision": "CONTINUE FORWARD TEST",
        "production_effect": "NONE",
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )
    commit, dirty = git_state(project_root)
    output_hashes = {
        path.name: sha256_file(path)
        for path in sorted(output_dir.iterdir())
        if path.is_file()
    }
    manifest_index = output_root / "run_manifest.jsonl"
    manifest_index_hash_before = (
        sha256_file(manifest_index) if manifest_index.is_file() else None
    )
    run_manifest = {
        "run_id": run_id,
        "generated_at": generated_at.isoformat(),
        "experiment_id": experiment["experiment_id"],
        "experiment_hash": sha256_file(experiment_path),
        "git_commit": commit,
        "git_dirty": dirty,
        "snapshot_run_ids": audit_frame["run_id"].astype(str).tolist(),
        "snapshot_candidate_record_hashes": audit_frame["candidate_record_hash"]
        .astype(str)
        .tolist(),
        "execution_event_journal_hash": events_hash,
        "output_directory": str(output_dir.resolve()),
        "output_hashes": output_hashes,
        "manifest_index_hash_before_append": manifest_index_hash_before,
    }
    (output_dir / "run_manifest.json").write_text(
        json.dumps(run_manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    with manifest_index.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(run_manifest, sort_keys=True) + "\n")
    print(f"Forward run: {output_dir}")
    print(f"Raw snapshot rows: {len(journal)}")
    print(f"Independent episodes: {len(episodes)}")
    print(f"Mature independent episodes: {len(mature_episodes)}")
    print(f"Mature 5-session outcomes: {metadata['mature_5d_count']}")
    print(f"Triggered plans: {metadata['plan_triggered_count']}")
    print(f"Mature plan R outcomes: {metadata['plan_mature_count']}")
    print(f"Actionable triggered plans: {metadata['actionable_plan_triggered_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
