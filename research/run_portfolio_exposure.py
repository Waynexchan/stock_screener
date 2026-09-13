"""Run the preregistered portfolio exposure and drawdown-control study."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from research.engine.baseline import execution_assumptions, load_model_0_config
from research.engine.data import load_price_csv
from research.engine.earnings import (
    apply_earnings_blackout_to_signals,
    load_verified_earnings_blackout_context,
)
from research.engine.execution import prepare_trade_executions, simulate_prepared_trade
from research.engine.features import generate_model_0_features
from research.engine.models import FeatureRecord, SimulatedTrade
from research.engine.portfolio import apply_position_capacity
from research.engine.portfolio_overlays import simulate_portfolio_overlay
from research.engine.reporting import ensure_research_output_path
from research.engine.reproducibility import sha256_file


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--prices", type=Path, required=True)
    command.add_argument("--benchmark", type=Path, required=True)
    command.add_argument("--earnings", type=Path)
    command.add_argument("--earnings-metadata", type=Path)
    command.add_argument(
        "--output-dir",
        type=Path,
        default=Path("research/output/portfolio_exposure_v1"),
    )
    return command


def _feature(row: dict[str, Any]) -> FeatureRecord:
    fields = FeatureRecord.__dataclass_fields__
    return FeatureRecord(**{name: row.get(name) for name in fields})


def _format_metric(value: Any) -> str:
    return "N/A" if value is None else f"{float(value):.3f}"


def _trade_keys(trades: list[SimulatedTrade]) -> list[tuple[str, str, str, str]]:
    return [
        (trade.entry_date, trade.signal_date, trade.ticker, trade.exit_date)
        for trade in trades
    ]


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    output_dir = ensure_research_output_path(project_root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    experiment_path = (
        project_root / "research" / "experiments" / "portfolio_exposure_v1.json"
    )
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    model_config = load_model_0_config(
        project_root / "research" / "config" / "model_0.json"
    )
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
    dates = pd.to_datetime(signals["signal_date"])
    discovery = signals[dates.between(start, end)].copy()
    pre_blackout_signal_count = len(discovery)
    blackout_rejections = pd.DataFrame()
    blackout_provenance: dict[str, Any] | None = None
    if (args.earnings is None) != (args.earnings_metadata is None):
        raise ValueError("--earnings and --earnings-metadata must be supplied together")
    if args.earnings is not None and args.earnings_metadata is not None:
        context = load_verified_earnings_blackout_context(
            args.earnings,
            args.earnings_metadata,
            required_signal_start=start,
            required_signal_end=end,
            blackout_calendar_days=10,
        )
        discovery, blackout_rejections = apply_earnings_blackout_to_signals(
            discovery, context, blackout_calendar_days=10
        )
        blackout_provenance = {**context.provenance(), "blackout_calendar_days": 10}
        blackout_rejections.to_csv(
            output_dir / "earnings_blackout_rejections.csv", index=False
        )
    assumptions = execution_assumptions(model_config)
    prepared = prepare_trade_executions(
        [_feature(row) for row in discovery.to_dict("records")],
        histories,
        assumptions,
    )
    independent_trades: list[SimulatedTrade] = []
    for execution in prepared:
        trade = simulate_prepared_trade(execution, assumptions)
        if trade is not None:
            independent_trades.append(trade)
    outcome_end = pd.Timestamp(experiment["discovery_price_period"][1])
    late_exits = [
        trade
        for trade in independent_trades
        if pd.Timestamp(trade.exit_date) > outcome_end
    ]
    if late_exits:
        raise ValueError("discovery trade outcome crossed the reserved-period boundary")
    sessions = pd.DatetimeIndex(benchmarks["SPY"].index).sort_values()
    expected_baseline, _ = apply_position_capacity(
        independent_trades,
        int(experiment["shared_constraints"]["maximum_positions"]),
    )
    rows: list[dict[str, Any]] = []
    for specification in experiment["portfolio_variants"]:
        metrics, ledger, curve = simulate_portfolio_overlay(
            independent_trades,
            histories,
            sessions,
            specification,
            starting_equity_r=float(experiment["starting_equity_r"]),
            maximum_positions=int(
                experiment["shared_constraints"]["maximum_positions"]
            ),
        )
        metrics["variant_id"] = specification["id"]
        if specification["id"] == "fixed_4r_baseline":
            actual_baseline = [
                SimulatedTrade(
                    **{name: row[name] for name in SimulatedTrade.__dataclass_fields__}
                )
                for row in ledger.to_dict("records")
            ]
            if _trade_keys(actual_baseline) != _trade_keys(expected_baseline):
                raise ValueError(
                    "fixed 4R overlay diverged from existing capacity logic"
                )
        metrics["meets_shortlist_gate"] = bool(
            metrics.get("maximum_drawdown_pct") is not None
            and metrics["maximum_drawdown_pct"] <= 10.0
            and metrics.get("total_return_pct", 0) > 0
            and metrics.get("profit_factor") is not None
            and metrics["profit_factor"] >= 1.20
            and metrics.get("accepted_trade_count", 0) >= 150
            and metrics.get("missing_mark_count") == 0
        )
        rows.append(metrics)
        ledger.to_csv(output_dir / f"ledger__{specification['id']}.csv", index=False)
        curve.to_csv(output_dir / f"equity__{specification['id']}.csv", index=False)
    result_frame = pd.DataFrame(rows)
    result_frame.to_csv(output_dir / "summary.csv", index=False)
    payload = {
        "experiment": experiment,
        "execution_status": "COMPLETED_SURVIVORSHIP_BIASED_ENGINEERING_DISCOVERY",
        "research_label": (
            "SURVIVORSHIP-AND-EARNINGS-SCHEDULE-BIASED RESEARCH"
            if blackout_provenance is not None
            else "SURVIVORSHIP-BIASED RESEARCH"
        ),
        "historical_decision": "HOLD",
        "holdout_evaluated": False,
        "prior_2024_boundary_warning": "This V1 purges 40-session outcomes before 2024; earlier FILTER_AUDIT_V1 and EXIT_STOP_GRID_V1 did not and therefore contaminated early 2024 for their own designs.",
        "price_sha256": sha256_file(args.prices),
        "benchmark_sha256": sha256_file(args.benchmark),
        "price_diagnostics": price_diagnostics,
        "benchmark_diagnostics": benchmark_diagnostics,
        "discovery_signal_count": len(discovery),
        "pre_blackout_signal_count": pre_blackout_signal_count,
        "earnings_blackout_rejection_count": len(blackout_rejections),
        "earnings_blackout": blackout_provenance,
        "independent_trade_count": len(independent_trades),
        "fixed_4r_baseline_parity_verified": True,
        "results": rows,
    }
    (output_dir / "results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    lines = [
        "# PORTFOLIO_EXPOSURE_V1 engineering discovery",
        "",
        "> **SURVIVORSHIP-AND-EARNINGS-SCHEDULE-BIASED RESEARCH — NOT PRODUCTION EVIDENCE**"
        if blackout_provenance is not None
        else "> **SURVIVORSHIP-BIASED RESEARCH — NOT PRODUCTION EVIDENCE**",
        "",
        f"Signals after boundary purge: {len(discovery)}",
        f"Earnings-blackout exclusions: {len(blackout_rejections)}",
        f"Independent executable trades: {len(independent_trades)}",
        "Historical decision: **HOLD**",
        "",
        "| Variant | Trades | Avg risk R | Expectancy R | PF | Total return % | CAGR % | Max DD R | Max DD % | Avg heat R | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['variant_id']} | {row['accepted_trade_count']} | "
            f"{_format_metric(row['average_allocated_r'])} | "
            f"{_format_metric(row['expectancy_per_trade_r'])} | "
            f"{_format_metric(row['profit_factor'])} | "
            f"{_format_metric(row['total_return_pct'])} | "
            f"{_format_metric(row['cagr_pct'])} | "
            f"{_format_metric(row['maximum_drawdown_r'])} | "
            f"{_format_metric(row['maximum_drawdown_pct'])} | "
            f"{_format_metric(row['average_heat_r'])} | "
            f"{row['meets_shortlist_gate']} |"
        )
    lines.extend(
        [
            "",
            "Drawdown is daily mark-to-market. All variants use the same purged signals and frozen trade exits; only causal allocation changes.",
        ]
    )
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Portfolio exposure study complete: {output_dir}")
    print(f"Signals after boundary purge: {len(discovery)}")
    print(f"Independent trades: {len(independent_trades)}")
    print(f"Variants reported: {len(rows)}")
    print("Holdout evaluated: False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
