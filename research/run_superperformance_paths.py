"""Run the preregistered causal superperformance entry-path experiment."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd

from research.engine.baseline import execution_assumptions, load_model_0_config
from research.engine.data import load_price_csv
from research.engine.earnings import (
    EarningsBlackoutContext,
    apply_earnings_blackout_to_signals,
    load_verified_earnings_blackout_context,
)
from research.engine.execution import simulate_trade
from research.engine.leader_features import enrich_leader_features
from research.engine.market_features import enrich_market_features
from research.engine.models import (
    ExecutionAssumptions,
    FeatureRecord,
    MovingAverageTrailingStop,
    SimulatedTrade,
)
from research.engine.portfolio_overlays import simulate_portfolio_overlay
from research.engine.reporting import ensure_research_output_path
from research.engine.reproducibility import git_state, sha256_file
from research.engine.superperformance_features import (
    enrich_superperformance_ranks,
    generate_superperformance_path_features,
    path_counts,
)
from research.run_combined_exit_exposure_grid import discovery_period_returns
from research.run_leader_rs_robustness import (
    _largest_winner_metrics,
    _stage_table,
    add_baseline_deltas,
    cross_stage_summary,
    meets_stage_gate,
)


PREREGISTRATION_COMMIT = "f6b9741"
PREREGISTRATION_CLARIFICATION_COMMIT = "4ab979a"
PATH_COLUMN_ALIASES = {"model_0": "model_0_path"}


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--prices", type=Path, required=True)
    command.add_argument("--benchmark", type=Path, required=True)
    command.add_argument("--earnings", type=Path, required=True)
    command.add_argument("--earnings-metadata", type=Path, required=True)
    command.add_argument(
        "--experiment-config",
        type=Path,
        default=Path("research/experiments/superperformance_paths_v1.json"),
    )
    command.add_argument(
        "--output-dir",
        type=Path,
        default=Path("research/output/superperformance_paths_v1"),
    )
    return command


def _feature(row: dict[str, Any]) -> FeatureRecord:
    values = {name: row.get(name) for name in FeatureRecord.__dataclass_fields__}
    values["model_0_signal"] = True
    return FeatureRecord(**values)


def _simulate_selected(
    selected: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    assumptions: ExecutionAssumptions,
    outcome_end: str,
    exit_mode: str | None,
) -> dict[tuple[str, str], SimulatedTrade]:
    if exit_mode is None:
        trailing = None
    elif exit_mode == "ACTIVATE_2R_SMA20_MINUS_1ATR":
        trailing = MovingAverageTrailingStop(
            activation_r=2.0,
            moving_average_sessions=20,
            atr_sessions=20,
            atr_offset=1.0,
        )
    else:
        raise ValueError(f"unsupported exit mode: {exit_mode}")
    cutoff = pd.Timestamp(outcome_end)
    result: dict[tuple[str, str], SimulatedTrade] = {}
    for row in selected.to_dict("records"):
        feature = _feature(row)
        history = histories.get(feature.ticker)
        if history is None:
            continue
        trade = simulate_trade(feature, history, assumptions, trailing_stop=trailing)
        if trade is None:
            continue
        if pd.Timestamp(trade.exit_date) > cutoff:
            raise AssertionError("trade outcome crossed the frozen stage boundary")
        result[(trade.signal_date, trade.ticker)] = trade
    return result


def _priority_map(
    selected: pd.DataFrame, mode: str | None
) -> dict[tuple[str, str], tuple[float, ...]] | None:
    if mode is None:
        return None
    if mode in {"YOUNG_FIRST", "MODEL0_FIRST"}:
        path_priorities: dict[tuple[str, str], tuple[float, ...]] = {}
        for row in selected[
            ["signal_date", "ticker", "young_leader_breakout", "model_0_path"]
        ].itertuples(index=False):
            is_young = bool(row.young_leader_breakout)
            is_model_0 = bool(row.model_0_path)
            preferred = is_young if mode == "YOUNG_FIRST" else is_model_0
            path_priorities[(str(row.signal_date), str(row.ticker))] = (
                0.0 if preferred else 1.0,
            )
        return path_priorities
    column = {
        "APPLICABLE_RS": "applicable_rs_score",
        "SUPERPERFORMANCE": "superperformance_rank_score",
    }.get(mode)
    if column is None:
        raise ValueError(f"unsupported candidate order: {mode}")
    result: dict[tuple[str, str], tuple[float, ...]] = {}
    for row in selected[["signal_date", "ticker", column]].itertuples(index=False):
        value = pd.to_numeric(getattr(row, column), errors="coerce")
        result[(str(row.signal_date), str(row.ticker))] = (
            -float(value) if pd.notna(value) else float("inf"),
        )
    return result


def _apply_primary_additive_gate(
    summary: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    stage_order: list[str],
    experiment: dict[str, Any],
) -> bool | None:
    """Apply the extra preregistered additive-sleeve decision conditions."""

    primary_id = experiment.get("primary_candidate_id")
    if primary_id is None:
        return None
    by_summary = {str(row["variant_id"]): row for row in summary}
    by_result = {(str(row["stage"]), str(row["variant_id"])): row for row in rows}
    primary = by_summary[str(primary_id)]
    ex_largest_values = [
        by_result[(stage, str(primary_id))].get("total_pnl_ex_largest_winner_r")
        for stage in stage_order
    ]
    ex_largest_positive = all(
        value is not None and pd.notna(value) and float(value) > 0
        for value in ex_largest_values
    )
    neighbor_ids = ("additive_default", "additive_model0_first")
    neighbor_support_count = sum(
        int(by_summary[neighbor]["return_improvement_period_count"]) >= 2
        and int(by_summary[neighbor]["return_to_drawdown_improvement_period_count"])
        >= 2
        for neighbor in neighbor_ids
    )
    primary_pass = bool(
        primary["cross_stage_shortlist"]
        and ex_largest_positive
        and neighbor_support_count >= 1
    )
    for item in summary:
        is_primary = str(item["variant_id"]) == str(primary_id)
        item["decision_eligible"] = is_primary
        item["positive_pnl_ex_largest_winner_all_periods"] = (
            ex_largest_positive if is_primary else None
        )
        item["neighbor_direction_support_count"] = (
            neighbor_support_count if is_primary else None
        )
        item["primary_additive_gate_pass"] = primary_pass if is_primary else False
    return primary_pass


def _parent_deltas(
    rows: list[dict[str, Any]], experiment: dict[str, Any]
) -> list[dict[str, Any]]:
    by_key = {(str(row["stage"]), str(row["variant_id"])): row for row in rows}
    metrics = (
        "total_return_pct",
        "maximum_drawdown_pct",
        "expectancy_per_trade_r",
        "profit_factor",
        "return_to_drawdown",
        "accepted_trade_count",
    )
    comparisons: list[dict[str, Any]] = []
    for variant in experiment["variants"]:
        parent = variant.get("parent")
        if parent is None:
            continue
        variant_id = str(variant["id"])
        for stage in sorted({str(row["stage"]) for row in rows}):
            child_row = by_key[(stage, variant_id)]
            parent_row = by_key[(stage, str(parent))]
            comparison: dict[str, Any] = {
                "stage": stage,
                "variant_id": variant_id,
                "parent_id": str(parent),
            }
            for metric in metrics:
                child = child_row.get(metric)
                base = parent_row.get(metric)
                comparison[f"{metric}_delta_vs_parent"] = (
                    None
                    if child is None or base is None
                    else float(child) - float(base)
                )
            comparisons.append(comparison)
    return comparisons


def _stage(
    *,
    stage_id: str,
    signal_period: list[str],
    outcome_end: str,
    development: bool,
    all_signals: pd.DataFrame,
    experiment: dict[str, Any],
    histories: dict[str, pd.DataFrame],
    sessions: pd.DatetimeIndex,
    blackout: EarningsBlackoutContext,
    assumptions: ExecutionAssumptions,
    output_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    dates = pd.to_datetime(all_signals["signal_date"])
    signals = all_signals[dates.between(*signal_period)].copy()
    pre_blackout_count = len(signals)
    signals, rejected = apply_earnings_blackout_to_signals(
        signals, blackout, blackout_calendar_days=10
    )
    stage_dir = output_dir / stage_id
    stage_dir.mkdir(parents=True, exist_ok=True)
    rejected.to_csv(stage_dir / "earnings_blackout_rejections.csv", index=False)
    portfolio = {"type": "FIXED", "maximum_heat_r": 2.0, "risk_per_trade_r": 1.0}
    cache: dict[tuple[str, str | None], dict[tuple[str, str], SimulatedTrade]] = {}
    rows: list[dict[str, Any]] = []
    for variant in experiment["variants"]:
        path = str(variant["path"])
        path_column = PATH_COLUMN_ALIASES.get(path, path)
        if path_column not in signals:
            raise ValueError(f"unknown superperformance path: {path}")
        selected = signals[signals[path_column].fillna(False).astype(bool)].copy()
        exit_mode = variant.get("exit_mode")
        cache_key = (path, exit_mode)
        if cache_key not in cache:
            cache[cache_key] = _simulate_selected(
                selected, histories, assumptions, outcome_end, exit_mode
            )
        execution_map = cache[cache_key]
        trades = [
            execution_map[key]
            for key in zip(selected["signal_date"], selected["ticker"], strict=False)
            if key in execution_map
        ]
        order = variant.get("candidate_order")
        metrics, ledger, curve = simulate_portfolio_overlay(
            trades,
            histories,
            sessions,
            portfolio,
            starting_equity_r=float(experiment["portfolio"]["starting_equity_r"]),
            maximum_positions=int(experiment["portfolio"]["maximum_positions"]),
            candidate_priority_by_signal_ticker=_priority_map(selected, order),
        )
        metrics.update(
            {
                "stage": stage_id,
                "variant_id": str(variant["id"]),
                "path": path,
                "candidate_order": order or "DEFAULT_TICKER",
                "exit_mode": exit_mode or "NO_TRAILING",
                "signal_count": len(signals),
                "selected_signal_count": len(selected),
                "independent_execution_count": len(execution_map),
                "selected_ranking_missing_component_count": int(
                    pd.to_numeric(
                        selected.get(
                            "ranking_missing_component_count",
                            pd.Series(0, index=selected.index),
                        ),
                        errors="coerce",
                    )
                    .fillna(0)
                    .sum()
                ),
            }
        )
        if development:
            early, late = discovery_period_returns(
                curve, experiment["periods"]["development_stability_split"]
            )
            metrics["early_period_return_pct"] = early
            metrics["late_period_return_pct"] = late
        drawdown = metrics.get("maximum_drawdown_pct")
        total_return = metrics.get("total_return_pct")
        metrics["return_to_drawdown"] = (
            None
            if drawdown in (None, 0) or total_return is None
            else float(total_return) / float(drawdown)
        )
        metrics.update(_largest_winner_metrics(ledger))
        metrics["exit_reason_counts"] = json.dumps(
            dict(
                sorted(Counter(ledger.get("exit_reason", pd.Series(dtype=str))).items())
            )
        )
        gate = experiment["stage_gates"][
            "development" if development else "reused_period"
        ]
        metrics["passes_stage_gate"] = meets_stage_gate(
            metrics, gate, development=development
        )
        safe = str(variant["id"]).replace(".", "_")
        provenance_columns = [
            "signal_date",
            "ticker",
            "archive_first_valid_date",
            "history_age_sessions",
            "archive_left_censored_history",
            "young_leader_breakout",
            "young_leader_breakout_additive_eligible",
            "model_0_path",
        ]
        available_provenance = [
            column for column in provenance_columns if column in selected.columns
        ]
        if available_provenance and not ledger.empty:
            ledger = ledger.merge(
                selected[available_provenance],
                on=["signal_date", "ticker"],
                how="left",
                validate="one_to_one",
            )
        ledger.to_csv(stage_dir / f"ledger__{safe}.csv", index=False)
        curve.to_csv(stage_dir / f"equity__{safe}.csv", index=False)
        rows.append(metrics)
    if len(rows) != int(experiment["variant_count"]):
        raise AssertionError("reported variant count differs from preregistration")
    return rows, {
        "pre_blackout_signal_count": pre_blackout_count,
        "earnings_blackout_rejection_count": len(rejected),
        "post_blackout_signal_count": len(signals),
        "path_counts_post_blackout": path_counts(signals),
        "reported_variant_count": len(rows),
    }


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    output_dir = ensure_research_output_path(project_root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    experiment_path = args.experiment_config
    if not experiment_path.is_absolute():
        experiment_path = project_root / experiment_path
    experiment_path = experiment_path.resolve()
    model_path = project_root / "research/config/model_0.json"
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    variants = experiment["variants"]
    if len(variants) != int(experiment["variant_count"]):
        raise ValueError("preregistered variant count does not match")
    if len({str(item["id"]) for item in variants}) != len(variants):
        raise ValueError("variant ids must be unique")

    model_config = load_model_0_config(model_path)
    histories, price_diagnostics = load_price_csv(args.prices)
    benchmarks, benchmark_diagnostics = load_price_csv(args.benchmark)
    if "SPY" not in benchmarks:
        raise ValueError("benchmark file must contain SPY")
    spy = benchmarks["SPY"].sort_index()
    sessions = pd.DatetimeIndex(spy.index).sort_values()
    feature_config = model_config["feature_configuration"]
    signals = generate_superperformance_path_features(
        histories,
        universe_version=model_config["universe_definition"],
        min_price=float(feature_config["min_price"]),
        min_average_volume=float(feature_config["min_average_volume_50d"]),
    )
    signals = enrich_market_features(signals, histories, spy)
    signals = enrich_leader_features(signals, histories, spy)
    signals = enrich_superperformance_ranks(signals, histories, spy)
    signals.to_csv(output_dir / "signal_features.csv", index=False)

    periods = experiment["periods"]
    blackout = load_verified_earnings_blackout_context(
        args.earnings,
        args.earnings_metadata,
        required_signal_start=periods["development_signal"][0],
        required_signal_end=periods["reused_2025_signal"][1],
        blackout_calendar_days=10,
    )
    assumptions = replace(
        execution_assumptions(model_config),
        target_r=None,
        maximum_holding_sessions=40,
    )
    stage_specs = [
        (
            "development_2017_2023",
            periods["development_signal"],
            periods["development_outcome_end"],
            True,
        ),
        (
            "reused_2024",
            periods["reused_2024_signal"],
            periods["reused_2024_outcome_end"],
            False,
        ),
        (
            "reused_2025",
            periods["reused_2025_signal"],
            periods["reused_2025_outcome_end"],
            False,
        ),
    ]
    rows: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {}
    for stage_id, period, outcome_end, development in stage_specs:
        stage_rows, stage_diagnostics = _stage(
            stage_id=stage_id,
            signal_period=period,
            outcome_end=outcome_end,
            development=development,
            all_signals=signals,
            experiment=experiment,
            histories=histories,
            sessions=sessions,
            blackout=blackout,
            assumptions=assumptions,
            output_dir=output_dir,
        )
        rows.extend(stage_rows)
        diagnostics[stage_id] = stage_diagnostics
        print(f"Completed {stage_id}: {len(stage_rows)} variants", flush=True)

    add_baseline_deltas(rows)
    stage_order = [item[0] for item in stage_specs]
    summary = cross_stage_summary(rows, stage_order, experiment)
    primary_additive_pass = _apply_primary_additive_gate(
        summary, rows, stage_order, experiment
    )
    parent_comparisons = _parent_deltas(rows, experiment)
    shortlist = [row for row in summary if row["cross_stage_shortlist"]]
    decision = (
        "HOLD"
        if (
            primary_additive_pass
            if primary_additive_pass is not None
            else bool(shortlist)
        )
        else "REJECT"
    )
    pd.DataFrame(rows).to_csv(output_dir / "all_stage_results.csv", index=False)
    pd.DataFrame(summary).to_csv(output_dir / "cross_stage_summary.csv", index=False)
    pd.DataFrame(parent_comparisons).to_csv(
        output_dir / "parent_comparisons.csv", index=False
    )

    git_commit, git_dirty = git_state(project_root)
    payload = {
        "experiment": experiment,
        "execution_status": "COMPLETED_ADAPTIVE_ROBUSTNESS_NO_UNTOUCHED_HOLDOUT",
        "research_label": experiment["research_label"],
        "historical_decision": decision,
        "preregistration_commit": experiment.get(
            "preregistration_commit", PREREGISTRATION_COMMIT
        ),
        "preregistration_clarification_commit": experiment.get(
            "preregistration_schema_commit", PREREGISTRATION_CLARIFICATION_COMMIT
        ),
        "run_git_commit": git_commit,
        "run_git_dirty": git_dirty,
        "production_effect": "NONE",
        "untouched_holdout_evaluated": False,
        "shortlist_count": len(shortlist),
        "primary_additive_gate_pass": primary_additive_pass,
        "price_sha256": sha256_file(args.prices),
        "benchmark_sha256": sha256_file(args.benchmark),
        "earnings_sha256": sha256_file(args.earnings),
        "earnings_metadata_sha256": sha256_file(args.earnings_metadata),
        "experiment_sha256": sha256_file(experiment_path),
        "model_config_sha256": sha256_file(model_path),
        "price_diagnostics": price_diagnostics,
        "benchmark_diagnostics": benchmark_diagnostics,
        "earnings_blackout": {
            **blackout.provenance(),
            "blackout_calendar_days": 10,
        },
        "full_path_counts": path_counts(signals),
        "stage_diagnostics": diagnostics,
        "all_stage_results": rows,
        "cross_stage_summary": summary,
        "parent_comparisons": parent_comparisons,
    }
    (output_dir / "results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    report = [
        f"# {experiment['experiment_id']}",
        "",
        f"> **{experiment['research_label']}**",
        "",
        f"Historical decision: **{decision}**",
        f"Cross-stage shortlist count: {len(shortlist)}",
        "Exact production parity: **UNAVAILABLE; MECHANICAL TRANSLATION ONLY**",
        "Point-in-time fundamentals: **BLOCKED_DATA_NOT_READY**",
        "",
    ]
    if primary_additive_pass is not None:
        report += [
            f"Primary additive gate pass: **{'YES' if primary_additive_pass else 'NO'}**",
            "",
        ]
    for stage_id in stage_order:
        report += [
            f"## {stage_id}",
            "",
            *_stage_table([row for row in rows if row["stage"] == stage_id]),
            "",
        ]
    report += [
        "## Interpretation boundary",
        "",
        "Every period is reused adaptive robustness. Signals are causal mechanical translations, not historical manual Daily Watchlist decisions. The archive contains current survivors and retrospective earnings events, and no point-in-time fundamentals are available.",
        "",
        "Production and the immutable forward journal are unchanged.",
    ]
    (output_dir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Decision: {decision}; shortlist: {len(shortlist)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
