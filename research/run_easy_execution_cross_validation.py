"""Run the frozen easy-execution discovery, validation, and conditional holdout."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd

from research.engine.baseline import execution_assumptions, load_model_0_config
from research.engine.data import load_price_csv
from research.engine.execution import (
    PreparedTradeExecution,
    prepare_trade_executions,
    simulate_prepared_trade,
)
from research.engine.features import generate_model_0_features
from research.engine.models import FeatureRecord, SimulatedTrade
from research.engine.portfolio_overlays import simulate_portfolio_overlay
from research.engine.reporting import ensure_research_output_path
from research.engine.reproducibility import git_state, sha256_file
from research.run_combined_exit_exposure_grid import discovery_period_returns
from research.run_exit_stop_grid import add_risk_inputs, stop_for_variant


PREREGISTRATION_COMMIT = "5ba5767"
AMENDMENT_CORRECTION_COMMIT = "60f24ab"


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--prices", type=Path, required=True)
    command.add_argument("--benchmark", type=Path, required=True)
    command.add_argument(
        "--output-dir",
        type=Path,
        default=Path("research/output/easy_execution_cross_validation_v1"),
    )
    return command


def _feature(row: dict[str, Any]) -> FeatureRecord:
    fields = FeatureRecord.__dataclass_fields__
    return FeatureRecord(**{name: row.get(name) for name in fields})


def _cell_id(stop_id: str, exit_id: str, portfolio_id: str) -> str:
    return f"{stop_id}__{exit_id}__{portfolio_id}"


def _numeric_gate(
    metrics: dict[str, Any], gate: dict[str, Any], *, discovery: bool
) -> bool:
    pairs = [
        ("maximum_drawdown_pct", "maximum_drawdown_pct_at_most", "le"),
        ("total_return_pct", "total_return_pct_above", "gt"),
        ("expectancy_per_trade_r", "expectancy_per_trade_r_above", "gt"),
        ("profit_factor", "profit_factor_at_least", "ge"),
        ("accepted_trade_count", "accepted_trade_count_at_least", "ge"),
        ("missing_mark_count", "missing_mark_count", "eq"),
    ]
    if discovery:
        pairs += [
            ("early_period_return_pct", "early_period_return_pct_above", "gt"),
            ("late_period_return_pct", "late_period_return_pct_above", "gt"),
        ]
    for metric_name, gate_name, operator in pairs:
        value = metrics.get(metric_name)
        threshold = gate.get(gate_name)
        if value is None or threshold is None:
            return False
        if operator == "le" and not float(value) <= float(threshold):
            return False
        if operator == "gt" and not float(value) > float(threshold):
            return False
        if operator == "ge" and not float(value) >= float(threshold):
            return False
        if operator == "eq" and not float(value) == float(threshold):
            return False
    return True


def meets_discovery_gate(metrics: dict[str, Any], gate: dict[str, Any]) -> bool:
    return _numeric_gate(metrics, gate, discovery=True)


def meets_validation_gate(metrics: dict[str, Any], gate: dict[str, Any]) -> bool:
    return _numeric_gate(metrics, gate, discovery=False)


def supporting_neighbor_ids(
    row: dict[str, Any], results: list[dict[str, Any]]
) -> list[str]:
    """Find preregistered adjacent exit settings with relaxed stability support."""

    supported: list[str] = []
    for candidate in results:
        if candidate["cell_id"] == row["cell_id"]:
            continue
        if (
            candidate["stop_id"] != row["stop_id"]
            or candidate["portfolio_id"] != row["portfolio_id"]
            or candidate["exit_family"] != row["exit_family"]
            or abs(int(candidate["exit_order"]) - int(row["exit_order"])) != 1
        ):
            continue
        required = (
            candidate.get("expectancy_per_trade_r"),
            candidate.get("profit_factor"),
            candidate.get("maximum_drawdown_pct"),
            candidate.get("accepted_trade_count"),
            candidate.get("early_period_return_pct"),
            candidate.get("late_period_return_pct"),
        )
        if any(value is None for value in required):
            continue
        if (
            float(required[0]) > 0
            and float(required[1]) >= 1.10
            and float(required[2]) <= 12.0
            and int(required[3]) >= 75
            and float(required[4]) >= 0
            and float(required[5]) >= 0
        ):
            supported.append(str(candidate["cell_id"]))
    return sorted(supported)


def _stage_signals(
    histories: dict[str, pd.DataFrame],
    model_config: dict[str, Any],
    start: str,
    end: str,
) -> pd.DataFrame:
    """Generate causal signals only through the declared stage signal end."""

    end_date = pd.Timestamp(end)
    stage_histories = {
        ticker: frame.loc[pd.DatetimeIndex(frame.index) <= end_date]
        for ticker, frame in histories.items()
    }
    feature_config = model_config["feature_configuration"]
    signals = generate_model_0_features(
        stage_histories,
        universe_version=model_config["universe_definition"],
        min_price=float(feature_config["min_price"]),
        min_average_volume=float(feature_config["min_average_volume_50d"]),
        minimum_history_sessions=int(feature_config["minimum_history_sessions"]),
        stop_lookback_sessions=int(feature_config["structural_stop_lookback_sessions"]),
        signals_only=True,
    )
    dates = pd.to_datetime(signals["signal_date"])
    return signals[dates.between(start, end)].copy()


def _prepare_stage(
    signals: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    base_assumptions: Any,
) -> list[tuple[PreparedTradeExecution, dict[str, Any]]]:
    enriched = add_risk_inputs(
        signals,
        histories,
        entry_slippage_bps=base_assumptions.entry_slippage_bps,
    )
    rows = {
        (str(row["signal_date"]), str(row["ticker"])): row
        for row in enriched.to_dict("records")
    }
    executions = prepare_trade_executions(
        [_feature(row) for row in rows.values()], histories, base_assumptions
    )
    return [
        (execution, rows[(execution.feature.signal_date, execution.feature.ticker)])
        for execution in executions
    ]


def _simulate_independent_trades(
    prepared: list[tuple[PreparedTradeExecution, dict[str, Any]]],
    stop_specification: dict[str, Any],
    exit_specification: dict[str, Any],
    base_assumptions: Any,
    outcome_end: str,
) -> list[SimulatedTrade]:
    assumptions = replace(
        base_assumptions,
        target_r=exit_specification["target_r"],
        maximum_holding_sessions=int(exit_specification["maximum_holding_sessions"]),
    )
    trades: list[SimulatedTrade] = []
    for execution, row in prepared:
        trade = simulate_prepared_trade(
            execution,
            assumptions,
            stop_price=stop_for_variant(row, stop_specification),
        )
        if trade is not None:
            trades.append(trade)
    if any(
        pd.Timestamp(trade.exit_date) > pd.Timestamp(outcome_end) for trade in trades
    ):
        raise ValueError("a trade crossed the declared stage outcome boundary")
    return trades


def _run_cell(
    *,
    stage: str,
    prepared: list[tuple[PreparedTradeExecution, dict[str, Any]]],
    stop_specification: dict[str, Any],
    exit_specification: dict[str, Any],
    portfolio_specification: dict[str, Any],
    base_assumptions: Any,
    outcome_end: str,
    histories: dict[str, pd.DataFrame],
    sessions: pd.DatetimeIndex,
    starting_equity_r: float,
    maximum_positions: int,
    output_dir: Path,
) -> dict[str, Any]:
    trades = _simulate_independent_trades(
        prepared,
        stop_specification,
        exit_specification,
        base_assumptions,
        outcome_end,
    )
    metrics, ledger, curve = simulate_portfolio_overlay(
        trades,
        histories,
        sessions,
        portfolio_specification,
        starting_equity_r=starting_equity_r,
        maximum_positions=maximum_positions,
    )
    cell_id = _cell_id(
        str(stop_specification["id"]),
        str(exit_specification["id"]),
        str(portfolio_specification["id"]),
    )
    metrics.update(
        {
            "stage": stage,
            "cell_id": cell_id,
            "stop_id": stop_specification["id"],
            "exit_id": exit_specification["id"],
            "exit_family": exit_specification["family"],
            "exit_order": exit_specification["order"],
            "target_r": exit_specification["target_r"],
            "maximum_holding_sessions": exit_specification["maximum_holding_sessions"],
            "portfolio_id": portfolio_specification["id"],
            "combined_complexity": int(stop_specification["complexity"])
            + int(exit_specification["complexity"])
            + int(portfolio_specification["complexity"]),
        }
    )
    safe_id = cell_id.replace(".", "_")
    ledger.to_csv(output_dir / f"ledger__{safe_id}.csv", index=False)
    curve.to_csv(output_dir / f"equity__{safe_id}.csv", index=False)
    return metrics


def _lookup(experiment: dict[str, Any], kind: str, identifier: str) -> dict[str, Any]:
    return next(item for item in experiment[kind] if item["id"] == identifier)


def _candidate_specification(
    experiment: dict[str, Any], row: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        _lookup(experiment, "stop_variants", str(row["stop_id"])),
        _lookup(experiment, "exit_variants", str(row["exit_id"])),
        _lookup(experiment, "portfolio_variants", str(row["portfolio_id"])),
    )


def _score(row: dict[str, Any]) -> tuple[float, float, int, str]:
    drawdown = float(row["maximum_drawdown_pct"])
    ratio = float("inf") if drawdown == 0 else float(row["cagr_pct"]) / drawdown
    return (
        -ratio,
        -float(row["expectancy_per_allocated_r"]),
        int(row["combined_complexity"]),
        str(row["cell_id"]),
    )


def _delta(value: Any, baseline: Any) -> float | None:
    if value is None or baseline is None:
        return None
    return float(value) - float(baseline)


def _add_baseline_deltas(rows: list[dict[str, Any]], baseline: dict[str, Any]) -> None:
    for row in rows:
        for metric in (
            "total_return_pct",
            "maximum_drawdown_pct",
            "expectancy_per_trade_r",
            "profit_factor",
            "accepted_trade_count",
        ):
            row[f"{metric}_delta_vs_baseline"] = _delta(
                row.get(metric), baseline.get(metric)
            )


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def _table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Role | Cell | Trades | Return % | CAGR % | Max DD % | Exp R | PF | Payoff | Avg hold | Pass |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        values = []
        for key in (
            "accepted_trade_count",
            "total_return_pct",
            "cagr_pct",
            "maximum_drawdown_pct",
            "expectancy_per_trade_r",
            "profit_factor",
            "payoff_ratio",
            "average_holding_days",
        ):
            value = row.get(key)
            values.append("N/A" if value is None else f"{float(value):.3f}")
        lines.append(
            f"| {row.get('role', '')} | {row['cell_id']} | "
            + " | ".join(values)
            + f" | {row.get('passes_gate', '')} |"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    output_dir = ensure_research_output_path(project_root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    experiment_path = (
        project_root
        / "research"
        / "experiments"
        / "easy_execution_cross_validation_v1.json"
    )
    amendment_path = (
        project_root
        / "research"
        / "experiments"
        / "easy_execution_cross_validation_v1_amendment_1.json"
    )
    model_path = project_root / "research" / "config" / "model_0.json"
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
    model_config = load_model_0_config(model_path)
    expected_count = (
        len(experiment["stop_variants"])
        * len(experiment["exit_variants"])
        * len(experiment["portfolio_variants"])
    )
    if expected_count != int(experiment["combination_count"]):
        raise ValueError("preregistered combination count does not match the matrix")

    histories, price_diagnostics = load_price_csv(args.prices)
    benchmarks, benchmark_diagnostics = load_price_csv(args.benchmark)
    if "SPY" not in benchmarks:
        raise ValueError("benchmark file must contain SPY")
    sessions = pd.DatetimeIndex(benchmarks["SPY"].index).sort_values()
    base_assumptions = replace(
        execution_assumptions(model_config), maximum_holding_sessions=40
    )
    starting_equity_r = float(experiment["starting_equity_r"])
    maximum_positions = int(experiment["execution"]["maximum_positions"])
    periods = experiment["periods"]

    discovery_signals = _stage_signals(
        histories, model_config, *periods["discovery_signal"]
    )
    discovery_prepared = _prepare_stage(discovery_signals, histories, base_assumptions)
    discovery_dir = output_dir / "discovery_cells"
    discovery_dir.mkdir(parents=True, exist_ok=True)
    discovery_results: list[dict[str, Any]] = []
    completed = 0
    for stop in experiment["stop_variants"]:
        for exit_specification in experiment["exit_variants"]:
            independent_trades = _simulate_independent_trades(
                discovery_prepared,
                stop,
                exit_specification,
                base_assumptions,
                periods["discovery_outcome_end"],
            )
            for portfolio in experiment["portfolio_variants"]:
                metrics, ledger, curve = simulate_portfolio_overlay(
                    independent_trades,
                    histories,
                    sessions,
                    portfolio,
                    starting_equity_r=starting_equity_r,
                    maximum_positions=maximum_positions,
                )
                cell_id = _cell_id(
                    stop["id"], exit_specification["id"], portfolio["id"]
                )
                early, late = discovery_period_returns(
                    curve, periods["discovery_stability_split"]
                )
                metrics.update(
                    {
                        "stage": "DISCOVERY",
                        "cell_id": cell_id,
                        "stop_id": stop["id"],
                        "exit_id": exit_specification["id"],
                        "exit_family": exit_specification["family"],
                        "exit_order": exit_specification["order"],
                        "target_r": exit_specification["target_r"],
                        "maximum_holding_sessions": exit_specification[
                            "maximum_holding_sessions"
                        ],
                        "portfolio_id": portfolio["id"],
                        "combined_complexity": int(stop["complexity"])
                        + int(exit_specification["complexity"])
                        + int(portfolio["complexity"]),
                        "early_period_return_pct": early,
                        "late_period_return_pct": late,
                    }
                )
                metrics["passes_gate"] = meets_discovery_gate(
                    metrics, experiment["discovery_gate"]
                )
                discovery_results.append(metrics)
                safe_id = cell_id.replace(".", "_")
                ledger.to_csv(discovery_dir / f"ledger__{safe_id}.csv", index=False)
                curve.to_csv(discovery_dir / f"equity__{safe_id}.csv", index=False)
                completed += 1
            print(
                f"Discovery {stop['id']} / {exit_specification['id']} "
                f"({completed}/{expected_count})",
                flush=True,
            )
    for row in discovery_results:
        neighbors = supporting_neighbor_ids(row, discovery_results)
        row["supporting_neighbor_cell_ids"] = neighbors
        row["neighbor_supported"] = bool(neighbors)
    gate_passes = [row for row in discovery_results if row["passes_gate"]]
    selected = sorted(
        gate_passes,
        key=lambda row: (not bool(row["neighbor_supported"]), *_score(row)),
    )[:3]
    for rank, row in enumerate(selected, start=1):
        row["selection_rank"] = rank
    pd.DataFrame(discovery_results).to_csv(
        output_dir / "discovery_grid.csv", index=False
    )
    pd.DataFrame(gate_passes).to_csv(
        output_dir / "discovery_gate_passes.csv", index=False
    )
    selection_payload = {
        "frozen_before_validation": True,
        "discovery_signal_count": len(discovery_signals),
        "prepared_execution_count": len(discovery_prepared),
        "reported_cell_count": len(discovery_results),
        "gate_pass_count": len(gate_passes),
        "selected_count": len(selected),
        "selected_candidates": selected,
    }
    _write_json(output_dir / "discovery_selection.json", selection_payload)
    pd.DataFrame(selected).to_csv(output_dir / "selected_candidates.csv", index=False)

    validation_results: list[dict[str, Any]] = []
    validation_baseline: dict[str, Any] | None = None
    if selected:
        print("Discovery selection frozen; beginning 2024 validation", flush=True)
        validation_signals = _stage_signals(
            histories, model_config, *periods["validation_signal"]
        )
        validation_prepared = _prepare_stage(
            validation_signals, histories, base_assumptions
        )
        validation_dir = output_dir / "validation_cells"
        validation_dir.mkdir(parents=True, exist_ok=True)
        baseline_ids = amendment["clarifications"]["comparison_baseline"]
        specs: dict[str, tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = {
            row["cell_id"]: _candidate_specification(experiment, row)
            for row in selected
        }
        baseline_cell_id = _cell_id(
            baseline_ids["stop_id"],
            baseline_ids["exit_id"],
            baseline_ids["portfolio_id"],
        )
        specs[baseline_cell_id] = (
            _lookup(experiment, "stop_variants", baseline_ids["stop_id"]),
            _lookup(experiment, "exit_variants", baseline_ids["exit_id"]),
            _lookup(experiment, "portfolio_variants", baseline_ids["portfolio_id"]),
        )
        selected_ids = {row["cell_id"] for row in selected}
        for cell_id, (stop, exit_specification, portfolio) in specs.items():
            result = _run_cell(
                stage="VALIDATION",
                prepared=validation_prepared,
                stop_specification=stop,
                exit_specification=exit_specification,
                portfolio_specification=portfolio,
                base_assumptions=base_assumptions,
                outcome_end=periods["validation_outcome_end"],
                histories=histories,
                sessions=sessions,
                starting_equity_r=starting_equity_r,
                maximum_positions=maximum_positions,
                output_dir=validation_dir,
            )
            result["role"] = (
                "SELECTED_AND_BASELINE"
                if cell_id in selected_ids and cell_id == baseline_cell_id
                else "SELECTED"
                if cell_id in selected_ids
                else "BASELINE"
            )
            result["passes_gate"] = (
                meets_validation_gate(result, experiment["validation_gate"])
                if cell_id in selected_ids
                else None
            )
            validation_results.append(result)
        validation_baseline = next(
            row for row in validation_results if "BASELINE" in row["role"]
        )
        _add_baseline_deltas(validation_results, validation_baseline)
    validation_payload = {
        "calculated_after_discovery_selection_was_written": True,
        "evaluated": bool(selected),
        "selected_candidate_count": len(selected),
        "results": validation_results,
    }
    _write_json(output_dir / "validation_results.json", validation_payload)
    pd.DataFrame(validation_results).to_csv(
        output_dir / "validation_results.csv", index=False
    )

    validation_passes = [
        row
        for row in validation_results
        if row.get("role") in {"SELECTED", "SELECTED_AND_BASELINE"}
        and row.get("passes_gate") is True
    ]
    holdout_results: list[dict[str, Any]] = []
    holdout_evaluated = bool(validation_passes)
    if holdout_evaluated:
        print("2024 gate passed; beginning one-time 2025 holdout", flush=True)
        holdout_signals = _stage_signals(
            histories, model_config, *periods["holdout_signal"]
        )
        holdout_prepared = _prepare_stage(holdout_signals, histories, base_assumptions)
        holdout_dir = output_dir / "holdout_cells"
        holdout_dir.mkdir(parents=True, exist_ok=True)
        holdout_specs = {
            row["cell_id"]: _candidate_specification(experiment, row)
            for row in validation_passes
        }
        assert validation_baseline is not None
        baseline_specs = _candidate_specification(experiment, validation_baseline)
        holdout_specs[validation_baseline["cell_id"]] = baseline_specs
        passing_ids = {row["cell_id"] for row in validation_passes}
        for cell_id, (stop, exit_specification, portfolio) in holdout_specs.items():
            result = _run_cell(
                stage="HOLDOUT",
                prepared=holdout_prepared,
                stop_specification=stop,
                exit_specification=exit_specification,
                portfolio_specification=portfolio,
                base_assumptions=base_assumptions,
                outcome_end=periods["holdout_outcome_end"],
                histories=histories,
                sessions=sessions,
                starting_equity_r=starting_equity_r,
                maximum_positions=maximum_positions,
                output_dir=holdout_dir,
            )
            result["role"] = (
                "VALIDATED_AND_BASELINE"
                if cell_id in passing_ids and cell_id == validation_baseline["cell_id"]
                else "VALIDATED_CANDIDATE"
                if cell_id in passing_ids
                else "BASELINE"
            )
            result["passes_gate"] = meets_validation_gate(
                result, experiment["validation_gate"]
            )
            holdout_results.append(result)
        holdout_baseline = next(
            row for row in holdout_results if "BASELINE" in row["role"]
        )
        _add_baseline_deltas(holdout_results, holdout_baseline)
    holdout_payload = {
        "evaluated": holdout_evaluated,
        "reason": (
            "At least one candidate passed the frozen 2024 validation gate."
            if holdout_evaluated
            else "No selected candidate passed the frozen 2024 validation gate."
        ),
        "results": holdout_results,
    }
    _write_json(output_dir / "holdout_results.json", holdout_payload)
    pd.DataFrame(holdout_results).to_csv(
        output_dir / "holdout_results.csv", index=False
    )

    git_commit, git_dirty = git_state(project_root)
    manifest = {
        "experiment_id": experiment["experiment_id"],
        "execution_status": "COMPLETED_SURVIVORSHIP_BIASED_STAGED_RESEARCH",
        "research_label": experiment["research_label"],
        "historical_decision": "HOLD",
        "production_effect": "NONE",
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "amendment_correction_commit": AMENDMENT_CORRECTION_COMMIT,
        "run_git_commit": git_commit,
        "run_git_dirty": git_dirty,
        "price_sha256": sha256_file(args.prices),
        "benchmark_sha256": sha256_file(args.benchmark),
        "experiment_sha256": sha256_file(experiment_path),
        "amendment_sha256": sha256_file(amendment_path),
        "model_config_sha256": sha256_file(model_path),
        "price_diagnostics": price_diagnostics,
        "benchmark_diagnostics": benchmark_diagnostics,
        "discovery_reported_cells": len(discovery_results),
        "discovery_gate_passes": len(gate_passes),
        "selected_candidates": len(selected),
        "validation_passes": len(validation_passes),
        "holdout_evaluated": holdout_evaluated,
        "holdout_candidate_count": len(
            [row for row in holdout_results if row["role"] != "BASELINE"]
        ),
        "limitations": [
            "Current-symbol Yahoo archive creates survivorship bias.",
            "Discovery follows earlier grid inspection and is not independent.",
            "No cash, maximum-notional, borrow, tax, or market-impact model.",
            "Post-2023 samples are short and cannot authorize production promotion.",
        ],
    }
    _write_json(output_dir / "run_manifest.json", manifest)

    report = [
        "# EASY_EXECUTION_CROSS_VALIDATION_V1",
        "",
        "> **SURVIVORSHIP-BIASED RESEARCH — NOT PRODUCTION EVIDENCE**",
        "",
        f"Discovery cells: {len(discovery_results)} / {expected_count}",
        f"Discovery gate passes: {len(gate_passes)}",
        f"Frozen selected candidates: {len(selected)}",
        f"2024 validation passes: {len(validation_passes)}",
        f"2025 holdout evaluated: {holdout_evaluated}",
        "Historical decision: **HOLD**",
        "",
        "## Frozen discovery selections",
        "",
        *_table(
            [{**row, "role": f"RANK_{index}"} for index, row in enumerate(selected, 1)]
        ),
        "",
        "## 2024 validation",
        "",
        *_table(validation_results),
        "",
        "## Conditional 2025 holdout",
        "",
        *(_table(holdout_results) if holdout_results else ["Not evaluated."]),
        "",
        "Every stage starts from a fresh 100R account. The 2025 stage was inaccessible to the simulation until the 2024 result file had been written and a candidate passed its frozen gate.",
        "",
        "No result changes production or the existing forward-test journal.",
    ]
    (output_dir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Completed staged experiment: {output_dir}")
    print(f"Discovery gate passes: {len(gate_passes)}; selected: {len(selected)}")
    print(f"Validation passes: {len(validation_passes)}")
    print(f"Holdout evaluated: {holdout_evaluated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
