"""Run the preregistered 180-cell exit, stop, and exposure cross."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd

from research.engine.baseline import execution_assumptions, load_model_0_config
from research.engine.data import load_price_csv
from research.engine.execution import prepare_trade_executions, simulate_prepared_trade
from research.engine.features import generate_model_0_features
from research.engine.models import FeatureRecord, SimulatedTrade
from research.engine.portfolio import apply_position_capacity
from research.engine.portfolio_overlays import simulate_portfolio_overlay
from research.engine.reporting import ensure_research_output_path
from research.engine.reproducibility import git_state, sha256_file
from research.run_exit_stop_grid import add_risk_inputs, stop_for_variant


PREREGISTRATION_COMMIT = "04365b7"


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--prices", type=Path, required=True)
    command.add_argument("--benchmark", type=Path, required=True)
    command.add_argument(
        "--output-dir",
        type=Path,
        default=Path("research/output/combined_exit_exposure_grid_v1"),
    )
    return command


def _feature(row: dict[str, Any]) -> FeatureRecord:
    fields = FeatureRecord.__dataclass_fields__
    return FeatureRecord(**{name: row.get(name) for name in fields})


def _target_label(target_r: float | None) -> str:
    return "none" if target_r is None else f"{target_r:g}r"


def _cell_id(stop_id: str, target_r: float | None, portfolio_id: str) -> str:
    return f"{stop_id}__target_{_target_label(target_r)}__{portfolio_id}"


def discovery_period_returns(
    curve: pd.DataFrame, split_date: str
) -> tuple[float | None, float | None]:
    """Return causal MTM percentage changes before and after the fixed split."""

    if curve.empty:
        return None, None
    dates = pd.to_datetime(curve["date"])
    early = curve.loc[dates <= pd.Timestamp(split_date), "equity_r"]
    late = curve.loc[dates > pd.Timestamp(split_date), "equity_r"]
    if early.empty or late.empty:
        return None, None
    starting_equity = float(curve.iloc[0]["equity_r"]) - float(
        curve.iloc[0]["portfolio_pnl_r"]
    )
    split_equity = float(early.iloc[-1])
    ending_equity = float(late.iloc[-1])
    if starting_equity <= 0 or split_equity <= 0:
        return None, None
    return (
        (split_equity / starting_equity - 1) * 100,
        (ending_equity / split_equity - 1) * 100,
    )


def meets_shortlist_gate(metrics: dict[str, Any], gate: dict[str, Any]) -> bool:
    """Apply the preregistered complete numeric discovery gate."""

    required = (
        "maximum_drawdown_pct",
        "total_return_pct",
        "expectancy_per_trade_r",
        "profit_factor",
        "accepted_trade_count",
        "missing_mark_count",
        "early_period_return_pct",
        "late_period_return_pct",
    )
    if any(metrics.get(name) is None for name in required):
        return False
    return bool(
        metrics["maximum_drawdown_pct"] <= float(gate["maximum_drawdown_pct_at_most"])
        and metrics["total_return_pct"] > float(gate["total_return_pct_above"])
        and metrics["expectancy_per_trade_r"]
        > float(gate["expectancy_per_trade_r_above"])
        and metrics["profit_factor"] >= float(gate["profit_factor_at_least"])
        and metrics["accepted_trade_count"]
        >= int(gate["accepted_trade_count_at_least"])
        and metrics["missing_mark_count"] == int(gate["missing_mark_count"])
        and metrics["early_period_return_pct"]
        > float(gate["early_period_return_pct_above"])
        and metrics["late_period_return_pct"]
        > float(gate["late_period_return_pct_above"])
    )


def _trade_keys(trades: list[SimulatedTrade]) -> list[tuple[str, str, str, str]]:
    return [
        (trade.entry_date, trade.signal_date, trade.ticker, trade.exit_date)
        for trade in trades
    ]


def _ledger_trade_keys(ledger: pd.DataFrame) -> list[tuple[str, str, str, str]]:
    return [
        (
            str(row["entry_date"]),
            str(row["signal_date"]),
            str(row["ticker"]),
            str(row["exit_date"]),
        )
        for row in ledger.to_dict("records")
    ]


def _optional_delta(value: object, baseline: object) -> float | None:
    if value is None or baseline is None:
        return None
    return float(value) - float(baseline)


def _format(value: object) -> str:
    return "N/A" if value is None else f"{float(value):.3f}"


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    output_dir = ensure_research_output_path(project_root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cell_dir = output_dir / "cells"
    cell_dir.mkdir(parents=True, exist_ok=True)
    experiment_path = (
        project_root
        / "research"
        / "experiments"
        / "combined_exit_exposure_grid_v1.json"
    )
    model_path = project_root / "research" / "config" / "model_0.json"
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    model_config = load_model_0_config(model_path)
    expected_count = (
        len(experiment["stop_variants"])
        * len(experiment["target_r_variants"])
        * len(experiment["portfolio_variants"])
    )
    if expected_count != int(experiment["combination_count"]):
        raise ValueError("preregistered combination count does not match the matrix")

    histories, price_diagnostics = load_price_csv(args.prices)
    benchmarks, benchmark_diagnostics = load_price_csv(args.benchmark)
    if "SPY" not in benchmarks:
        raise ValueError("benchmark file must contain SPY")
    feature_config = model_config["feature_configuration"]
    signals = generate_model_0_features(
        histories,
        universe_version=model_config["universe_definition"],
        min_price=float(feature_config["min_price"]),
        min_average_volume=float(feature_config["min_average_volume_50d"]),
        minimum_history_sessions=int(feature_config["minimum_history_sessions"]),
        stop_lookback_sessions=int(feature_config["structural_stop_lookback_sessions"]),
        signals_only=True,
    )
    start, end = experiment["discovery_signal_period"]
    signal_dates = pd.to_datetime(signals["signal_date"])
    discovery = signals[signal_dates.between(start, end)].copy()
    base_assumptions = execution_assumptions(model_config)
    discovery = add_risk_inputs(
        discovery,
        histories,
        entry_slippage_bps=base_assumptions.entry_slippage_bps,
    )
    rows_by_key = {
        (str(row["signal_date"]), str(row["ticker"])): row
        for row in discovery.to_dict("records")
    }
    executions = prepare_trade_executions(
        [_feature(row) for row in rows_by_key.values()], histories, base_assumptions
    )
    prepared = [
        (
            execution,
            rows_by_key[(execution.feature.signal_date, execution.feature.ticker)],
        )
        for execution in executions
    ]
    sessions = pd.DatetimeIndex(benchmarks["SPY"].index).sort_values()
    outcome_end = pd.Timestamp(experiment["discovery_price_period"][1])
    result_rows: list[dict[str, Any]] = []
    cell_number = 0
    fixed_four_parity_checks = 0

    for stop_specification in experiment["stop_variants"]:
        for target_r in experiment["target_r_variants"]:
            assumptions = replace(base_assumptions, target_r=target_r)
            independent_trades: list[SimulatedTrade] = []
            for execution, row in prepared:
                stop = stop_for_variant(row, stop_specification)
                trade = simulate_prepared_trade(
                    execution,
                    assumptions,
                    stop_price=stop,
                )
                if trade is not None:
                    independent_trades.append(trade)
            if any(
                pd.Timestamp(trade.exit_date) > outcome_end
                for trade in independent_trades
            ):
                raise ValueError(
                    "a discovery trade crossed the reserved-period boundary"
                )
            expected_fixed_four, _ = apply_position_capacity(
                independent_trades, int(experiment["execution"]["maximum_positions"])
            )
            for portfolio_specification in experiment["portfolio_variants"]:
                cell_number += 1
                cell_id = _cell_id(
                    str(stop_specification["id"]),
                    target_r,
                    str(portfolio_specification["id"]),
                )
                metrics, ledger, curve = simulate_portfolio_overlay(
                    independent_trades,
                    histories,
                    sessions,
                    portfolio_specification,
                    starting_equity_r=float(experiment["starting_equity_r"]),
                    maximum_positions=int(experiment["execution"]["maximum_positions"]),
                )
                if portfolio_specification["id"] == "fixed_4r_baseline":
                    if _ledger_trade_keys(ledger) != _trade_keys(expected_fixed_four):
                        raise ValueError(
                            f"fixed 4R cell diverged from capacity logic: {cell_id}"
                        )
                    fixed_four_parity_checks += 1
                early_return, late_return = discovery_period_returns(
                    curve, str(experiment["discovery_stability_split"])
                )
                metrics.update(
                    {
                        "cell_number": cell_number,
                        "cell_id": cell_id,
                        "stop_id": stop_specification["id"],
                        "target_r": target_r,
                        "portfolio_id": portfolio_specification["id"],
                        "combined_complexity": int(stop_specification["complexity"])
                        + (0 if target_r is None else 1)
                        + int(portfolio_specification["complexity"]),
                        "early_period_return_pct": early_return,
                        "late_period_return_pct": late_return,
                        "cagr_to_drawdown": (
                            None
                            if metrics.get("cagr_pct") is None
                            or not metrics.get("maximum_drawdown_pct")
                            else float(metrics["cagr_pct"])
                            / float(metrics["maximum_drawdown_pct"])
                        ),
                    }
                )
                metrics["meets_numeric_shortlist_gate"] = meets_shortlist_gate(
                    metrics, experiment["numeric_shortlist_rule"]
                )
                metrics["shortlist_rank"] = None
                result_rows.append(metrics)
                ledger.to_csv(cell_dir / f"ledger__{cell_number:03d}.csv", index=False)
                curve.to_csv(cell_dir / f"equity__{cell_number:03d}.csv", index=False)
            print(
                "Completed exit/stop family "
                f"{stop_specification['id']} target {_target_label(target_r)} "
                f"({cell_number}/{expected_count} cells)",
                flush=True,
            )

    if cell_number != expected_count:
        raise ValueError("reported cell count does not match preregistration")
    baseline = next(
        row
        for row in result_rows
        if row["stop_id"] == "structural_20d_low"
        and row["target_r"] is None
        and row["portfolio_id"] == "fixed_4r_baseline"
    )
    for row in result_rows:
        row["total_return_delta_pct"] = _optional_delta(
            row.get("total_return_pct"), baseline.get("total_return_pct")
        )
        row["maximum_drawdown_delta_pct"] = _optional_delta(
            row.get("maximum_drawdown_pct"), baseline.get("maximum_drawdown_pct")
        )
        row["expectancy_delta_r"] = _optional_delta(
            row.get("expectancy_per_trade_r"),
            baseline.get("expectancy_per_trade_r"),
        )
    shortlisted = sorted(
        (row for row in result_rows if row["meets_numeric_shortlist_gate"]),
        key=lambda row: (
            -float(row["cagr_to_drawdown"]),
            -float(row["expectancy_per_allocated_r"]),
            int(row["combined_complexity"]),
            str(row["cell_id"]),
        ),
    )
    for rank, row in enumerate(shortlisted, start=1):
        row["shortlist_rank"] = rank

    frame = pd.DataFrame(result_rows)
    frame.to_csv(output_dir / "grid_results.csv", index=False)
    pd.DataFrame(shortlisted, columns=frame.columns).to_csv(
        output_dir / "shortlist.csv", index=False
    )
    git_commit, git_dirty = git_state(project_root)
    payload = {
        "experiment": experiment,
        "execution_status": "COMPLETED_SURVIVORSHIP_BIASED_ENGINEERING_DISCOVERY",
        "research_label": "SURVIVORSHIP-BIASED RESEARCH",
        "historical_decision": "HOLD",
        "holdout_evaluated": False,
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "run_git_commit": git_commit,
        "run_git_dirty": git_dirty,
        "multiple_comparison_warning": "All 180 related cells reuse one biased discovery sample; shortlist rank is not independent validation.",
        "price_sha256": sha256_file(args.prices),
        "benchmark_sha256": sha256_file(args.benchmark),
        "experiment_sha256": sha256_file(experiment_path),
        "model_config_sha256": sha256_file(model_path),
        "price_diagnostics": price_diagnostics,
        "benchmark_diagnostics": benchmark_diagnostics,
        "discovery_signal_count": len(discovery),
        "prepared_execution_count": len(prepared),
        "reported_cell_count": len(result_rows),
        "shortlist_count": len(shortlisted),
        "fixed_4r_parity_checks": fixed_four_parity_checks,
        "baseline_cell": baseline,
        "results": result_rows,
    }
    (output_dir / "results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )

    lines = [
        "# COMBINED_EXIT_EXPOSURE_GRID_V1 engineering discovery",
        "",
        "> **SURVIVORSHIP-BIASED RESEARCH — NOT PRODUCTION EVIDENCE**",
        "",
        f"Preregistration commit: `{PREREGISTRATION_COMMIT}`",
        f"Discovery signals: {len(discovery)}",
        f"Reported cells: {len(result_rows)}",
        f"Numeric shortlist cells: {len(shortlisted)}",
        "Historical decision: **HOLD**",
        "",
        "| Rank | Cell | Trades | Exp R | PF | Return % | CAGR % | Max DD % | Early % | Late % | Gate |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    display_rows = (
        shortlisted
        if shortlisted
        else sorted(
            result_rows,
            key=lambda row: (
                float(row["maximum_drawdown_pct"]),
                -float(row["total_return_pct"]),
                str(row["cell_id"]),
            ),
        )[:20]
    )
    for row in display_rows:
        lines.append(
            f"| {row['shortlist_rank'] or ''} | {row['cell_id']} | "
            f"{row['accepted_trade_count']} | "
            f"{_format(row['expectancy_per_trade_r'])} | "
            f"{_format(row['profit_factor'])} | "
            f"{_format(row['total_return_pct'])} | "
            f"{_format(row['cagr_pct'])} | "
            f"{_format(row['maximum_drawdown_pct'])} | "
            f"{_format(row['early_period_return_pct'])} | "
            f"{_format(row['late_period_return_pct'])} | "
            f"{row['meets_numeric_shortlist_gate']} |"
        )
    lines.extend(
        [
            "",
            "The table shows every passing cell, or the 20 lowest-drawdown cells when none passes. `grid_results.csv` and `results.json` report all 180 cells; numbered ledgers and daily equity curves are under `cells/`.",
            "",
            "The 2024–2025 holdout was not evaluated. No result changes production or the existing frozen forward journal.",
        ]
    )
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Combined grid complete: {output_dir}")
    print(f"Reported cells: {len(result_rows)}")
    print(f"Shortlist cells: {len(shortlisted)}")
    print(f"Fixed 4R parity checks: {fixed_four_parity_checks}")
    print("Historical decision: HOLD")
    print("Holdout evaluated: False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
