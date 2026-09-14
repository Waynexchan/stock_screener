"""Run the preregistered SPY-gate by moving-average trailing-exit cross."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research.engine.baseline import execution_assumptions, load_model_0_config
from research.engine.data import load_price_csv
from research.engine.earnings import (
    EarningsBlackoutContext,
    apply_earnings_blackout_to_signals,
    load_verified_earnings_blackout_context,
)
from research.engine.execution import PreparedTradeExecution, simulate_prepared_trade
from research.engine.market_gates import market_limits_for_signal_dates
from research.engine.models import MovingAverageTrailingStop, SimulatedTrade
from research.engine.portfolio_overlays import simulate_portfolio_overlay
from research.engine.reporting import ensure_research_output_path
from research.engine.reproducibility import git_state, sha256_file
from research.run_combined_exit_exposure_grid import discovery_period_returns
from research.run_easy_execution_cross_validation import _prepare_stage, _stage_signals


PREREGISTRATION_COMMIT = "f534cc8"


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--prices", type=Path, required=True)
    command.add_argument("--benchmark", type=Path, required=True)
    command.add_argument("--earnings", type=Path, required=True)
    command.add_argument("--earnings-metadata", type=Path, required=True)
    command.add_argument(
        "--output-dir",
        type=Path,
        default=Path("research/output/market_trailing_exit_cross_v1"),
    )
    return command


def trailing_policy(specification: dict[str, Any]) -> MovingAverageTrailingStop | None:
    activation = specification.get("activation_r")
    if activation is None:
        return None
    return MovingAverageTrailingStop(
        activation_r=float(activation),
        moving_average_sessions=int(specification["moving_average_sessions"]),
        atr_sessions=int(specification["atr_sessions"]),
        atr_offset=float(specification["atr_offset"]),
    )


def simulate_trailing_variant(
    prepared: list[tuple[PreparedTradeExecution, dict[str, Any]]],
    assumptions: Any,
    specification: dict[str, Any],
    outcome_end: str,
) -> list[SimulatedTrade]:
    policy = trailing_policy(specification)
    trades = [
        trade
        for execution, _ in prepared
        if (
            trade := simulate_prepared_trade(
                execution,
                assumptions,
                trailing_stop=policy,
            )
        )
        is not None
    ]
    if any(
        pd.Timestamp(trade.exit_date) > pd.Timestamp(outcome_end) for trade in trades
    ):
        raise ValueError("a trailing trade crossed the declared outcome boundary")
    return trades


def meets_stage_gate(
    metrics: dict[str, Any], gate: dict[str, Any], *, development: bool
) -> bool:
    comparisons = [
        ("maximum_drawdown_pct", "maximum_drawdown_pct_at_most", "le"),
        ("total_return_pct", "total_return_pct_above", "gt"),
        ("expectancy_per_trade_r", "expectancy_per_trade_r_above", "gt"),
        ("profit_factor", "profit_factor_at_least", "ge"),
        ("accepted_trade_count", "accepted_trade_count_at_least", "ge"),
        ("missing_mark_count", "missing_mark_count", "eq"),
    ]
    if development:
        comparisons += [
            ("early_period_return_pct", "early_period_return_pct_above", "gt"),
            ("late_period_return_pct", "late_period_return_pct_above", "gt"),
        ]
    for metric_name, gate_name, operator in comparisons:
        value = metrics.get(metric_name)
        threshold = gate.get(gate_name)
        if value is None or threshold is None:
            return False
        parsed, limit = float(value), float(threshold)
        if operator == "le" and not parsed <= limit:
            return False
        if operator == "gt" and not parsed > limit:
            return False
        if operator == "ge" and not parsed >= limit:
            return False
        if operator == "eq" and not parsed == limit:
            return False
    return True


def _delta(value: Any, baseline: Any) -> float | None:
    if value is None or baseline is None:
        return None
    return float(value) - float(baseline)


def _largest_winner_metrics(ledger: pd.DataFrame) -> dict[str, float | None]:
    if ledger.empty:
        return {
            "largest_winner_r": None,
            "largest_winner_share_of_total_pnl": None,
            "total_pnl_ex_largest_winner_r": None,
        }
    outcomes = pd.to_numeric(ledger["portfolio_realised_r"], errors="coerce")
    largest = float(outcomes.max())
    total = float(outcomes.sum())
    return {
        "largest_winner_r": largest,
        "largest_winner_share_of_total_pnl": (None if total <= 0 else largest / total),
        "total_pnl_ex_largest_winner_r": total - largest,
    }


def _consecutive_loss_count(ledger: pd.DataFrame) -> int:
    if ledger.empty:
        return 0
    ordered = ledger.assign(_exit=pd.to_datetime(ledger["exit_date"])).sort_values(
        ["_exit", "ticker"]
    )
    maximum = current = 0
    for outcome in pd.to_numeric(ordered["portfolio_realised_r"], errors="coerce"):
        current = current + 1 if outcome <= 0 else 0
        maximum = max(maximum, current)
    return maximum


def _run_stage(
    *,
    stage_id: str,
    signal_period: list[str],
    outcome_end: str,
    development: bool,
    experiment: dict[str, Any],
    model_config: dict[str, Any],
    histories: dict[str, pd.DataFrame],
    spy: pd.DataFrame,
    sessions: pd.DatetimeIndex,
    blackout: EarningsBlackoutContext,
    assumptions: Any,
    output_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    signals = _stage_signals(histories, model_config, *signal_period)
    pre_blackout_count = len(signals)
    signals, rejected = apply_earnings_blackout_to_signals(
        signals, blackout, blackout_calendar_days=10
    )
    stage_dir = output_dir / stage_id
    stage_dir.mkdir(parents=True, exist_ok=True)
    rejected.to_csv(stage_dir / "earnings_blackout_rejections.csv", index=False)
    prepared = _prepare_stage(signals, histories, assumptions)
    portfolio = {
        "id": "fixed_2r",
        "type": "FIXED",
        "maximum_heat_r": 2.0,
        "risk_per_trade_r": 1.0,
    }
    rows: list[dict[str, Any]] = []
    for trailing in experiment["trailing_exit_variants"]:
        trades = simulate_trailing_variant(prepared, assumptions, trailing, outcome_end)
        signal_dates = [trade.signal_date for trade in trades]
        for market in experiment["market_gate_variants"]:
            heat_limits, market_states = market_limits_for_signal_dates(
                spy, signal_dates, market
            )
            metrics, ledger, curve = simulate_portfolio_overlay(
                trades,
                histories,
                sessions,
                portfolio,
                starting_equity_r=float(experiment["starting_equity_r"]),
                maximum_positions=int(
                    experiment["fixed_trade_plan"]["maximum_positions"]
                ),
                entry_heat_limit_by_signal_date=heat_limits,
                market_state_by_signal_date=market_states,
            )
            cell_id = f"{market['id']}__{trailing['id']}"
            if development:
                early, late = discovery_period_returns(
                    curve, experiment["periods"]["development_stability_split"]
                )
                metrics["early_period_return_pct"] = early
                metrics["late_period_return_pct"] = late
            exits = Counter(ledger.get("exit_reason", pd.Series(dtype=str)))
            states = Counter(ledger.get("market_state", pd.Series(dtype=str)))
            activation = trailing.get("activation_r")
            metrics.update(
                {
                    "stage": stage_id,
                    "cell_id": cell_id,
                    "market_gate_id": market["id"],
                    "trailing_exit_id": trailing["id"],
                    "activation_r": activation,
                    "atr_offset": trailing.get("atr_offset"),
                    "combined_complexity": int(market["complexity"])
                    + int(trailing["complexity"]),
                    "passes_stage_gate": meets_stage_gate(
                        metrics,
                        experiment["stage_gate"][
                            "development" if development else "reused_period"
                        ],
                        development=development,
                    ),
                    "exit_reason_counts": json.dumps(dict(sorted(exits.items()))),
                    "accepted_market_state_counts": json.dumps(
                        dict(sorted(states.items()))
                    ),
                    "trailing_activation_count": (
                        0
                        if activation is None or ledger.empty
                        else int(
                            (
                                pd.to_numeric(ledger["MFE_R"], errors="coerce")
                                >= float(activation)
                            ).sum()
                        )
                    ),
                    "trailing_exit_count": int(
                        ledger.get("exit_reason", pd.Series(dtype=str))
                        .astype(str)
                        .str.startswith("TRAILING_STOP")
                        .sum()
                    ),
                    "maximum_consecutive_losing_exits": _consecutive_loss_count(ledger),
                    **_largest_winner_metrics(ledger),
                }
            )
            if (
                not ledger.empty
                and (
                    pd.to_numeric(ledger["market_heat_limit_r"], errors="coerce") <= 0
                ).any()
            ):
                raise AssertionError("a market-blocked trade entered the ledger")
            safe = cell_id.replace(".", "_")
            ledger.to_csv(stage_dir / f"ledger__{safe}.csv", index=False)
            curve.to_csv(stage_dir / f"equity__{safe}.csv", index=False)
            rows.append(metrics)
    expected = int(experiment["combination_count"])
    if len(rows) != expected:
        raise AssertionError(f"expected {expected} stage cells, got {len(rows)}")
    diagnostics = {
        "pre_blackout_signal_count": pre_blackout_count,
        "earnings_blackout_rejection_count": len(rejected),
        "post_blackout_signal_count": len(signals),
        "prepared_execution_count": len(prepared),
        "reported_cell_count": len(rows),
        "missing_mark_count": int(sum(int(row["missing_mark_count"]) for row in rows)),
    }
    return rows, diagnostics


def _add_deltas(rows: list[dict[str, Any]]) -> None:
    metrics = (
        "total_return_pct",
        "cagr_pct",
        "maximum_drawdown_pct",
        "expectancy_per_trade_r",
        "profit_factor",
        "accepted_trade_count",
    )
    by_stage: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_stage.setdefault(str(row["stage"]), []).append(row)
    for stage_rows in by_stage.values():
        baseline = next(
            row
            for row in stage_rows
            if row["cell_id"] == "no_market_gate__no_trailing_stop"
        )
        no_trailing = {
            str(row["market_gate_id"]): row
            for row in stage_rows
            if row["trailing_exit_id"] == "no_trailing_stop"
        }
        for row in stage_rows:
            same_market = no_trailing[str(row["market_gate_id"])]
            for metric in metrics:
                row[f"{metric}_delta_vs_global_baseline"] = _delta(
                    row.get(metric), baseline.get(metric)
                )
                row[f"{metric}_delta_vs_same_market_no_trail"] = _delta(
                    row.get(metric), same_market.get(metric)
                )


def _cross_period_summary(
    rows: list[dict[str, Any]], stage_order: list[str]
) -> list[dict[str, Any]]:
    by_cell: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_cell.setdefault(str(row["cell_id"]), {})[str(row["stage"])] = row
    summary: list[dict[str, Any]] = []
    for cell_id, stages in by_cell.items():
        if sorted(stages) != sorted(stage_order):
            raise AssertionError(f"cell {cell_id} is missing a stage")
        ordered = [stages[stage] for stage in stage_order]
        trailing = str(ordered[0]["trailing_exit_id"])
        return_deltas = [
            row["total_return_pct_delta_vs_same_market_no_trail"] for row in ordered
        ]
        row = {
            "cell_id": cell_id,
            "market_gate_id": ordered[0]["market_gate_id"],
            "trailing_exit_id": trailing,
            "stage_gate_pass_count": sum(
                bool(item["passes_stage_gate"]) for item in ordered
            ),
            "passes_all_stage_gates": all(
                bool(item["passes_stage_gate"]) for item in ordered
            ),
            "return_improves_vs_same_market_no_trail_all_periods": (
                trailing != "no_trailing_stop"
                and all(
                    delta is not None and float(delta) > 0 for delta in return_deltas
                )
            ),
            "maximum_drawdown_pct_worst_period": max(
                float(item["maximum_drawdown_pct"]) for item in ordered
            ),
            "minimum_accepted_trade_count": min(
                int(item["accepted_trade_count"]) for item in ordered
            ),
            "total_return_pct_sum": sum(
                float(item["total_return_pct"]) for item in ordered
            ),
            "total_return_pct_by_stage": json.dumps(
                {stage: stages[stage]["total_return_pct"] for stage in stage_order}
            ),
            "maximum_drawdown_pct_by_stage": json.dumps(
                {stage: stages[stage]["maximum_drawdown_pct"] for stage in stage_order}
            ),
            "return_delta_vs_same_market_no_trail_by_stage": json.dumps(
                {
                    stage: stages[stage][
                        "total_return_pct_delta_vs_same_market_no_trail"
                    ]
                    for stage in stage_order
                }
            ),
        }
        summary.append(row)
    return sorted(
        summary,
        key=lambda item: (
            -int(item["passes_all_stage_gates"]),
            -int(item["stage_gate_pass_count"]),
            float(item["maximum_drawdown_pct_worst_period"]),
            -float(item["total_return_pct_sum"]),
            str(item["cell_id"]),
        ),
    )


def _format(value: Any) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "N/A"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, np.integer)):
        return str(value)
    return f"{float(value):.3f}"


def _stage_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Market | Trail | Trades | Return % | Max DD % | Exp R | PF | Payoff | Largest win R | Ex-largest R | Trail exits | Pass |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['market_gate_id']} | {row['trailing_exit_id']} | "
            + " | ".join(
                _format(row.get(name))
                for name in (
                    "accepted_trade_count",
                    "total_return_pct",
                    "maximum_drawdown_pct",
                    "expectancy_per_trade_r",
                    "profit_factor",
                    "payoff_ratio",
                    "largest_winner_r",
                    "total_pnl_ex_largest_winner_r",
                    "trailing_exit_count",
                    "passes_stage_gate",
                )
            )
            + " |"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    output_dir = ensure_research_output_path(project_root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    experiment_path = (
        project_root / "research" / "experiments" / "market_trailing_exit_cross_v1.json"
    )
    model_path = project_root / "research" / "config" / "model_0.json"
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    model_config = load_model_0_config(model_path)
    expected = len(experiment["market_gate_variants"]) * len(
        experiment["trailing_exit_variants"]
    )
    if expected != int(experiment["combination_count"]):
        raise ValueError("preregistered market/trailing matrix count does not match")
    histories, price_diagnostics = load_price_csv(args.prices)
    benchmarks, benchmark_diagnostics = load_price_csv(args.benchmark)
    if "SPY" not in benchmarks:
        raise ValueError("benchmark file must contain SPY")
    spy = benchmarks["SPY"].sort_index()
    sessions = pd.DatetimeIndex(spy.index).sort_values()
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
    all_rows: list[dict[str, Any]] = []
    diagnostics: dict[str, Any] = {}
    for stage_id, signal_period, outcome_end, development in stage_specs:
        rows, stage_diagnostics = _run_stage(
            stage_id=stage_id,
            signal_period=signal_period,
            outcome_end=outcome_end,
            development=development,
            experiment=experiment,
            model_config=model_config,
            histories=histories,
            spy=spy,
            sessions=sessions,
            blackout=blackout,
            assumptions=assumptions,
            output_dir=output_dir,
        )
        all_rows.extend(rows)
        diagnostics[stage_id] = stage_diagnostics
        print(f"Completed {stage_id}: {len(rows)} cells", flush=True)
    _add_deltas(all_rows)
    stage_order = [item[0] for item in stage_specs]
    cross_period = _cross_period_summary(all_rows, stage_order)
    complete_passes = [row for row in cross_period if row["passes_all_stage_gates"]]
    return_improvers = [
        row
        for row in cross_period
        if row["return_improves_vs_same_market_no_trail_all_periods"]
    ]
    decision = "HOLD" if complete_passes else "REVISE"
    pd.DataFrame(all_rows).to_csv(output_dir / "all_stage_results.csv", index=False)
    pd.DataFrame(cross_period).to_csv(
        output_dir / "cross_period_summary.csv", index=False
    )
    git_commit, git_dirty = git_state(project_root)
    payload = {
        "experiment": experiment,
        "execution_status": "COMPLETED_ADAPTIVE_ROBUSTNESS_NO_UNTOUCHED_HOLDOUT",
        "research_label": experiment["research_label"],
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "run_git_commit": git_commit,
        "run_git_dirty": git_dirty,
        "historical_decision": decision,
        "complete_cross_period_pass_count": len(complete_passes),
        "return_improver_all_period_count": len(return_improvers),
        "production_effect": "NONE",
        "untouched_holdout_evaluated": False,
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
        "stage_diagnostics": diagnostics,
        "all_stage_results": all_rows,
        "cross_period_summary": cross_period,
    }
    (output_dir / "results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    report = [
        "# MARKET_TRAILING_EXIT_CROSS_V1",
        "",
        "> **SURVIVORSHIP-AND-EARNINGS-SCHEDULE-BIASED RESEARCH — NO UNTOUCHED HOLDOUT**",
        "",
        f"Historical decision: **{decision}**",
        f"Complete cross-period gate passes: {len(complete_passes)}",
        f"Trailing cells improving same-market return in all periods: {len(return_improvers)}",
        "",
    ]
    for stage_id in stage_order:
        report += [
            f"## {stage_id}",
            "",
            *_stage_table([row for row in all_rows if row["stage"] == stage_id]),
            "",
        ]
    report += [
        "## Interpretation boundary",
        "",
        "The SPY three-state rule is a reproducible proxy, not the production market regime. All periods are reused, the current-symbol archive is survivorship-biased, and earnings dates are retrospective. Results cannot authorize production or a new forward test.",
        "",
        "Production and the immutable forward journal are unchanged.",
    ]
    (output_dir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(
        f"Decision: {decision}; complete passes: {len(complete_passes)}; "
        f"all-period return improvers: {len(return_improvers)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
