"""Run the adaptive earnings-blackout and win/relock exposure robustness study."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from research.engine.baseline import execution_assumptions, load_model_0_config
from research.engine.data import load_price_csv
from research.engine.earnings import (
    EarningsRejection,
    apply_earnings_blackout,
    load_earnings_calendar,
)
from research.engine.portfolio_overlays import simulate_portfolio_overlay
from research.engine.reporting import ensure_research_output_path
from research.engine.reproducibility import git_state, sha256_file
from research.run_easy_execution_cross_validation import (
    _prepare_stage,
    _simulate_independent_trades,
    _stage_signals,
)


PREREGISTRATION_COMMIT = "9545103"


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--prices", type=Path, required=True)
    command.add_argument("--benchmark", type=Path, required=True)
    command.add_argument("--earnings", type=Path, required=True)
    command.add_argument("--earnings-metadata", type=Path, required=True)
    command.add_argument(
        "--output-dir",
        type=Path,
        default=Path("research/output/earnings_exposure_robustness_v1"),
    )
    return command


def stage_gate(
    metrics: dict[str, Any], gate: dict[str, Any], *, development: bool
) -> bool:
    minimum_trades = int(
        gate[
            "development_accepted_trade_count_at_least"
            if development
            else "post_2023_accepted_trade_count_at_least"
        ]
    )
    required = (
        metrics.get("maximum_drawdown_pct"),
        metrics.get("total_return_pct"),
        metrics.get("expectancy_per_trade_r"),
        metrics.get("profit_factor"),
        metrics.get("accepted_trade_count"),
        metrics.get("missing_mark_count"),
    )
    if any(value is None for value in required):
        return False
    return bool(
        float(required[0]) <= float(gate["each_stage_maximum_drawdown_pct_at_most"])
        and float(required[1]) > float(gate["each_stage_total_return_pct_above"])
        and float(required[2]) > float(gate["each_stage_expectancy_per_trade_r_above"])
        and float(required[3]) >= float(gate["each_stage_profit_factor_at_least"])
        and int(required[4]) >= minimum_trades
        and int(required[5]) == int(gate["missing_mark_count"])
    )


def _rejections_frame(rejections: list[EarningsRejection]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                **item.trade.to_dict(),
                "earnings_rejection_reason": item.reason,
                "earnings_date": item.earnings_date,
                "calendar_days_to_earnings": item.calendar_days_to_earnings,
            }
            for item in rejections
        ]
    )


def _delta(value: Any, baseline: Any) -> float | None:
    if value is None or baseline is None:
        return None
    return float(value) - float(baseline)


def _run_stage(
    *,
    stage_id: str,
    signal_period: list[str],
    outcome_end: str,
    development: bool,
    histories: dict[str, pd.DataFrame],
    sessions: pd.DatetimeIndex,
    earnings: dict[str, pd.DatetimeIndex],
    earnings_coverage_start: str,
    earnings_coverage_end: str,
    model_config: dict[str, Any],
    experiment: dict[str, Any],
    output_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    signals = _stage_signals(histories, model_config, *signal_period)
    assumptions = execution_assumptions(model_config)
    prepared = _prepare_stage(signals, histories, assumptions)
    trades = _simulate_independent_trades(
        prepared,
        {"id": "structural_20d_low", "anchor": "signal_20d_low", "atr_multiple": 0},
        {"id": "time_40s_no_target", "target_r": None, "maximum_holding_sessions": 40},
        assumptions,
        outcome_end,
    )
    allowed, rejections = apply_earnings_blackout(
        trades,
        earnings,
        blackout_calendar_days=10,
        covered_start=earnings_coverage_start,
        covered_end=earnings_coverage_end,
    )
    coverage_rejections = [
        item for item in rejections if item.reason == "CALENDAR_COVERAGE_UNAVAILABLE"
    ]
    if coverage_rejections:
        raise ValueError("earnings calendar coverage unavailable for stage signals")
    stage_dir = output_dir / stage_id
    stage_dir.mkdir(parents=True, exist_ok=True)
    _rejections_frame(rejections).to_csv(
        stage_dir / "earnings_blackout_rejections.csv", index=False
    )
    portfolios = {
        experiment["portfolio"]["fixed_baseline"]["id"]: experiment["portfolio"][
            "fixed_baseline"
        ],
        experiment["portfolio"]["dynamic_candidate"]["id"]: experiment["portfolio"][
            "dynamic_candidate"
        ],
    }
    results: list[dict[str, Any]] = []
    for variant in experiment["variants"]:
        candidate_trades = allowed if variant["earnings_blackout"] else trades
        portfolio = portfolios[variant["portfolio_id"]]
        metrics, ledger, curve = simulate_portfolio_overlay(
            candidate_trades,
            histories,
            sessions,
            portfolio,
            starting_equity_r=float(experiment["portfolio"]["starting_equity_r"]),
            maximum_positions=int(
                experiment["portfolio"]["dynamic_candidate"]["hard_maximum_positions"]
            ),
        )
        metrics.update(
            {
                "stage": stage_id,
                "variant_id": variant["id"],
                "portfolio_id": variant["portfolio_id"],
                "earnings_blackout": bool(variant["earnings_blackout"]),
                "signal_count": len(signals),
                "prepared_execution_count": len(prepared),
                "pre_blackout_trade_count": len(trades),
                "earnings_blackout_rejection_count": (
                    len(rejections) if variant["earnings_blackout"] else 0
                ),
                "passes_stage_gate": False,
            }
        )
        metrics["passes_stage_gate"] = stage_gate(
            metrics, experiment["decision_gate"], development=development
        )
        ledger.to_csv(stage_dir / f"ledger__{variant['id']}.csv", index=False)
        curve.to_csv(stage_dir / f"equity__{variant['id']}.csv", index=False)
        results.append(metrics)
    baseline = next(
        row for row in results if row["variant_id"] == "fixed_2r_no_blackout"
    )
    for row in results:
        for metric in (
            "total_return_pct",
            "maximum_drawdown_pct",
            "expectancy_per_trade_r",
            "profit_factor",
            "accepted_trade_count",
        ):
            row[f"{metric}_delta_vs_fixed_2r"] = _delta(
                row.get(metric), baseline.get(metric)
            )
        row["return_retention_vs_fixed_2r"] = (
            None
            if not baseline.get("total_return_pct")
            else float(row["total_return_pct"]) / float(baseline["total_return_pct"])
        )
    diagnostics = {
        "signal_count": len(signals),
        "prepared_execution_count": len(prepared),
        "pre_blackout_trade_count": len(trades),
        "earnings_blackout_rejection_count": len(rejections),
        "earnings_blackout_rejection_average_independent_r": (
            None
            if not rejections
            else sum(item.trade.realised_r for item in rejections) / len(rejections)
        ),
    }
    pd.DataFrame(results).to_csv(stage_dir / "summary.csv", index=False)
    return results, diagnostics


def _format(value: Any) -> str:
    return "N/A" if value is None else f"{float(value):.3f}"


def _table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Variant | Trades | Return % | Max DD % | Exp R | PF | Payoff | Avg hold | Expanded | Contracted | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        metrics = [
            "accepted_trade_count",
            "total_return_pct",
            "maximum_drawdown_pct",
            "expectancy_per_trade_r",
            "profit_factor",
            "payoff_ratio",
            "average_holding_days",
            "exposure_expansion_count",
            "exposure_contraction_count",
        ]
        lines.append(
            f"| {row['variant_id']} | "
            + " | ".join(_format(row.get(name)) for name in metrics)
            + f" | {row['passes_stage_gate']} |"
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
        / "earnings_exposure_robustness_v1.json"
    )
    model_path = project_root / "research" / "config" / "model_0.json"
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    model_config = load_model_0_config(model_path)
    earnings_metadata = json.loads(args.earnings_metadata.read_text(encoding="utf-8"))
    if not earnings_metadata.get("complete_calendar_date_coverage"):
        raise ValueError("earnings calendar does not have complete date coverage")
    if earnings_metadata.get("earnings_sha256") != sha256_file(args.earnings):
        raise ValueError("earnings calendar hash does not match metadata")
    coverage_start = str(earnings_metadata["requested_start_inclusive"])
    coverage_end = str(earnings_metadata["requested_end_inclusive"])
    required_start = experiment["periods"]["development_signal"][0]
    required_end = (
        (
            pd.Timestamp(experiment["periods"]["post_2023_robustness_signal"][1])
            + pd.Timedelta(days=10)
        )
        .date()
        .isoformat()
    )
    if pd.Timestamp(coverage_start) > pd.Timestamp(required_start) or pd.Timestamp(
        coverage_end
    ) < pd.Timestamp(required_end):
        raise ValueError(
            "earnings calendar does not cover every required signal window"
        )

    histories, price_diagnostics = load_price_csv(args.prices)
    benchmarks, benchmark_diagnostics = load_price_csv(args.benchmark)
    if "SPY" not in benchmarks:
        raise ValueError("benchmark file must contain SPY")
    earnings = load_earnings_calendar(args.earnings)
    sessions = pd.DatetimeIndex(benchmarks["SPY"].index).sort_values()
    development_results, development_diagnostics = _run_stage(
        stage_id="development_2017_2023",
        signal_period=experiment["periods"]["development_signal"],
        outcome_end=experiment["periods"]["development_outcome_end"],
        development=True,
        histories=histories,
        sessions=sessions,
        earnings=earnings,
        earnings_coverage_start=coverage_start,
        earnings_coverage_end=coverage_end,
        model_config=model_config,
        experiment=experiment,
        output_dir=output_dir,
    )
    print("Development robustness complete", flush=True)
    post_results, post_diagnostics = _run_stage(
        stage_id="post_2023_reused",
        signal_period=experiment["periods"]["post_2023_robustness_signal"],
        outcome_end=experiment["periods"]["post_2023_robustness_outcome_end"],
        development=False,
        histories=histories,
        sessions=sessions,
        earnings=earnings,
        earnings_coverage_start=coverage_start,
        earnings_coverage_end=coverage_end,
        model_config=model_config,
        experiment=experiment,
        output_dir=output_dir,
    )
    candidate_id = "dynamic_earnings_blackout"
    development_candidate = next(
        row for row in development_results if row["variant_id"] == candidate_id
    )
    post_candidate = next(
        row for row in post_results if row["variant_id"] == candidate_id
    )
    retention_floor = float(
        experiment["decision_gate"]["candidate_return_retention_vs_fixed_2r_at_least"]
    )
    complete_gate = bool(
        development_candidate["passes_stage_gate"]
        and post_candidate["passes_stage_gate"]
        and float(development_candidate["return_retention_vs_fixed_2r"])
        >= retention_floor
        and float(post_candidate["return_retention_vs_fixed_2r"]) >= retention_floor
    )
    decision = "CONTINUE_FORWARD_OBSERVATION" if complete_gate else "HOLD"
    git_commit, git_dirty = git_state(project_root)
    payload = {
        "experiment": experiment,
        "execution_status": "COMPLETED_ADAPTIVE_ROBUSTNESS_NO_UNTOUCHED_HOLDOUT",
        "research_label": experiment["research_label"],
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "run_git_commit": git_commit,
        "run_git_dirty": git_dirty,
        "decision": decision,
        "complete_numeric_gate_pass": complete_gate,
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
        "earnings_metadata": earnings_metadata,
        "development_diagnostics": development_diagnostics,
        "post_2023_diagnostics": post_diagnostics,
        "development_results": development_results,
        "post_2023_results": post_results,
    }
    (output_dir / "results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    pd.DataFrame(development_results + post_results).to_csv(
        output_dir / "all_results.csv", index=False
    )
    report = [
        "# EARNINGS_EXPOSURE_ROBUSTNESS_V1",
        "",
        "> **SURVIVORSHIP-AND-EARNINGS-SCHEDULE-BIASED RESEARCH**",
        "",
        "This adaptive study has no untouched historical holdout. It cannot validate or promote a production rule.",
        "",
        f"Decision: **{decision}**",
        "",
        "## Reused 2017-2023 development robustness",
        "",
        *_table(development_results),
        "",
        f"Blackout rejected {development_diagnostics['earnings_blackout_rejection_count']} independent trade paths.",
        "",
        "## Reused post-2023 robustness",
        "",
        *_table(post_results),
        "",
        f"Blackout rejected {post_diagnostics['earnings_blackout_rejection_count']} independent trade paths.",
        "",
        "The dynamic rule starts at two 1R positions, expands to three on the session after a net-profitable exit batch, and returns to two after a zero/negative exit batch. No fourth position is possible.",
        "",
        "Earnings dates are retrospective actual/revised-date proxies, not point-in-time schedule snapshots. Production and the existing forward journal are unchanged.",
    ]
    (output_dir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Completed earnings/exposure robustness: {output_dir}")
    print(f"Decision: {decision}; untouched holdout evaluated: False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
