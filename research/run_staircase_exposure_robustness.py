"""Run capped staircase exposure variants with the earnings blackout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from research.engine.baseline import execution_assumptions, load_model_0_config
from research.engine.data import load_price_csv
from research.engine.earnings import apply_earnings_blackout, load_earnings_calendar
from research.engine.portfolio_overlays import simulate_portfolio_overlay
from research.engine.reporting import ensure_research_output_path
from research.engine.reproducibility import git_state, sha256_file
from research.run_earnings_exposure_robustness import _rejections_frame, stage_gate
from research.run_easy_execution_cross_validation import (
    _prepare_stage,
    _simulate_independent_trades,
    _stage_signals,
)


PREREGISTRATION_COMMIT = "0df092a"


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--prices", type=Path, required=True)
    command.add_argument("--benchmark", type=Path, required=True)
    command.add_argument("--earnings", type=Path, required=True)
    command.add_argument("--earnings-metadata", type=Path, required=True)
    command.add_argument(
        "--output-dir",
        type=Path,
        default=Path("research/output/staircase_exposure_robustness_v2"),
    )
    return command


def portfolio_variants(experiment: dict[str, Any]) -> list[dict[str, Any]]:
    variants = [dict(experiment["baseline"])]
    portfolio = experiment["portfolio"]
    for ceiling in experiment["ceiling_variants_r"]:
        for contraction in experiment["contraction_variants"]:
            ceiling_r = float(ceiling)
            variants.append(
                {
                    "id": (f"staircase_cap_{ceiling_r:g}r__{contraction['id']}"),
                    "type": "STAIRCASE",
                    "floor_heat_r": float(portfolio["floor_heat_r"]),
                    "ceiling_heat_r": ceiling_r,
                    "profit_increment_r": float(portfolio["profit_increment_r"]),
                    "loss_step_r": float(portfolio["loss_step_r"]),
                    "contraction_mode": contraction["mode"],
                    "risk_per_trade_r": float(portfolio["risk_per_trade_r"]),
                }
            )
    return variants


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
    coverage_start: str,
    coverage_end: str,
    model_config: dict[str, Any],
    experiment: dict[str, Any],
    output_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    signals = _stage_signals(histories, model_config, *signal_period)
    assumptions = execution_assumptions(model_config)
    prepared = _prepare_stage(signals, histories, assumptions)
    trades = _simulate_independent_trades(
        prepared,
        {
            "id": "structural_20d_low",
            "anchor": "signal_20d_low",
            "atr_multiple": 0,
        },
        {
            "id": "time_40s_no_target",
            "target_r": None,
            "maximum_holding_sessions": 40,
        },
        assumptions,
        outcome_end,
    )
    allowed, rejected = apply_earnings_blackout(
        trades,
        earnings,
        blackout_calendar_days=10,
        covered_start=coverage_start,
        covered_end=coverage_end,
    )
    if any(item.reason == "CALENDAR_COVERAGE_UNAVAILABLE" for item in rejected):
        raise ValueError("earnings calendar coverage unavailable for stage signals")
    stage_dir = output_dir / stage_id
    stage_dir.mkdir(parents=True, exist_ok=True)
    _rejections_frame(rejected).to_csv(
        stage_dir / "earnings_blackout_rejections.csv", index=False
    )
    variants = portfolio_variants(experiment)
    if len(variants) != int(experiment["combination_count"]):
        raise ValueError("preregistered combination count does not match variants")
    maximum_ceiling = int(max(experiment["ceiling_variants_r"]))
    results: list[dict[str, Any]] = []
    for specification in variants:
        metrics, ledger, curve = simulate_portfolio_overlay(
            allowed,
            histories,
            sessions,
            specification,
            starting_equity_r=float(experiment["portfolio"]["starting_equity_r"]),
            maximum_positions=maximum_ceiling,
        )
        ceiling = float(
            specification["ceiling_heat_r"]
            if "ceiling_heat_r" in specification
            else specification["maximum_heat_r"]
        )
        if float(metrics["maximum_heat_r"]) > ceiling or int(
            metrics["maximum_positions"]
        ) > int(ceiling):
            raise ValueError(
                f"portfolio exceeded frozen ceiling: {specification['id']}"
            )
        metrics.update(
            {
                "stage": stage_id,
                "variant_id": specification["id"],
                "portfolio_type": specification["type"],
                "ceiling_heat_r": ceiling,
                "contraction_mode": specification.get("contraction_mode"),
                "signal_count": len(signals),
                "prepared_execution_count": len(prepared),
                "pre_blackout_trade_count": len(trades),
                "earnings_blackout_rejection_count": len(rejected),
            }
        )
        metrics["passes_stage_gate"] = stage_gate(
            metrics, experiment["decision_gate"], development=development
        )
        ledger.to_csv(stage_dir / f"ledger__{specification['id']}.csv", index=False)
        curve.to_csv(stage_dir / f"equity__{specification['id']}.csv", index=False)
        results.append(metrics)
    baseline = next(
        row for row in results if row["variant_id"] == experiment["baseline"]["id"]
    )
    for row in results:
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
        row["return_retention_vs_baseline"] = (
            None
            if not baseline.get("total_return_pct")
            else float(row["total_return_pct"]) / float(baseline["total_return_pct"])
        )
    pd.DataFrame(results).to_csv(stage_dir / "summary.csv", index=False)
    return results, {
        "signal_count": len(signals),
        "prepared_execution_count": len(prepared),
        "pre_blackout_trade_count": len(trades),
        "earnings_blackout_rejection_count": len(rejected),
    }


def _paired_candidates(
    development: list[dict[str, Any]],
    post_2023: list[dict[str, Any]],
    experiment: dict[str, Any],
) -> list[dict[str, Any]]:
    post_by_id = {row["variant_id"]: row for row in post_2023}
    floor = float(
        experiment["decision_gate"][
            "each_stage_return_retention_vs_fixed_2r_earnings_at_least"
        ]
    )
    pairs: list[dict[str, Any]] = []
    for early in development:
        if early["portfolio_type"] != "STAIRCASE":
            continue
        late = post_by_id[early["variant_id"]]
        complete_pass = bool(
            early["passes_stage_gate"]
            and late["passes_stage_gate"]
            and float(early["return_retention_vs_baseline"]) >= floor
            and float(late["return_retention_vs_baseline"]) >= floor
        )
        pairs.append(
            {
                "variant_id": early["variant_id"],
                "ceiling_heat_r": early["ceiling_heat_r"],
                "contraction_mode": early["contraction_mode"],
                "development_return_pct": early["total_return_pct"],
                "development_maximum_drawdown_pct": early["maximum_drawdown_pct"],
                "development_expectancy_r": early["expectancy_per_trade_r"],
                "development_return_retention": early["return_retention_vs_baseline"],
                "post_2023_return_pct": late["total_return_pct"],
                "post_2023_maximum_drawdown_pct": late["maximum_drawdown_pct"],
                "post_2023_expectancy_r": late["expectancy_per_trade_r"],
                "post_2023_return_retention": late["return_retention_vs_baseline"],
                "worst_stage_maximum_drawdown_pct": max(
                    float(early["maximum_drawdown_pct"]),
                    float(late["maximum_drawdown_pct"]),
                ),
                "lower_stage_expectancy_r": min(
                    float(early["expectancy_per_trade_r"]),
                    float(late["expectancy_per_trade_r"]),
                ),
                "complete_gate_pass": complete_pass,
            }
        )
    pairs.sort(
        key=lambda row: (
            not bool(row["complete_gate_pass"]),
            float(row["worst_stage_maximum_drawdown_pct"]),
            -float(row["lower_stage_expectancy_r"]),
            float(row["ceiling_heat_r"]),
            0 if row["contraction_mode"] == "RESET" else 1,
            str(row["variant_id"]),
        )
    )
    for rank, row in enumerate(pairs, start=1):
        row["robustness_rank"] = rank
    return pairs


def _format(value: Any) -> str:
    return "N/A" if value is None else f"{float(value):.3f}"


def _table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Variant | Trades | Return % | Max DD % | Exp R | PF | Max heat | Max positions | Expanded | Contracted | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    names = (
        "accepted_trade_count",
        "total_return_pct",
        "maximum_drawdown_pct",
        "expectancy_per_trade_r",
        "profit_factor",
        "maximum_heat_r",
        "maximum_positions",
        "exposure_expansion_count",
        "exposure_contraction_count",
    )
    for row in rows:
        lines.append(
            f"| {row['variant_id']} | "
            + " | ".join(_format(row.get(name)) for name in names)
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
        / "staircase_exposure_robustness_v2.json"
    )
    model_path = project_root / "research" / "config" / "model_0.json"
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    model_config = load_model_0_config(model_path)
    metadata = json.loads(args.earnings_metadata.read_text(encoding="utf-8"))
    if not metadata.get("complete_calendar_date_coverage"):
        raise ValueError("earnings calendar does not have complete date coverage")
    if metadata.get("earnings_sha256") != sha256_file(args.earnings):
        raise ValueError("earnings calendar hash does not match metadata")
    coverage_start = str(metadata["requested_start_inclusive"])
    coverage_end = str(metadata["requested_end_inclusive"])
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
        raise ValueError("earnings calendar does not cover required signal windows")

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
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        model_config=model_config,
        experiment=experiment,
        output_dir=output_dir,
    )
    print("Development staircase robustness complete", flush=True)
    post_results, post_diagnostics = _run_stage(
        stage_id="post_2023_reused",
        signal_period=experiment["periods"]["post_2023_robustness_signal"],
        outcome_end=experiment["periods"]["post_2023_robustness_outcome_end"],
        development=False,
        histories=histories,
        sessions=sessions,
        earnings=earnings,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        model_config=model_config,
        experiment=experiment,
        output_dir=output_dir,
    )
    pairs = _paired_candidates(development_results, post_results, experiment)
    complete_passes = [row for row in pairs if row["complete_gate_pass"]]
    decision = "CONTINUE_FORWARD_OBSERVATION" if complete_passes else "HOLD"
    pd.DataFrame(development_results + post_results).to_csv(
        output_dir / "all_results.csv", index=False
    )
    pd.DataFrame(pairs).to_csv(output_dir / "cross_period_ranking.csv", index=False)
    git_commit, git_dirty = git_state(project_root)
    payload = {
        "experiment": experiment,
        "execution_status": "COMPLETED_ADAPTIVE_ROBUSTNESS_NO_UNTOUCHED_HOLDOUT",
        "research_label": experiment["research_label"],
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "run_git_commit": git_commit,
        "run_git_dirty": git_dirty,
        "decision": decision,
        "complete_gate_pass_count": len(complete_passes),
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
        "development_diagnostics": development_diagnostics,
        "post_2023_diagnostics": post_diagnostics,
        "development_results": development_results,
        "post_2023_results": post_results,
        "cross_period_ranking": pairs,
    }
    (output_dir / "results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    report = [
        "# STAIRCASE_EXPOSURE_ROBUSTNESS_V2",
        "",
        "> **SURVIVORSHIP-AND-EARNINGS-SCHEDULE-BIASED RESEARCH**",
        "",
        "This adaptive study has no untouched historical holdout.",
        f"Decision: **{decision}**",
        "",
        "## Reused 2017-2023 development robustness",
        "",
        *_table(development_results),
        "",
        "## Reused post-2023 robustness",
        "",
        *_table(post_results),
        "",
        f"Complete cross-period gate passes: {len(complete_passes)}",
        "",
        "Every positive realised exit batch adds one position slot up to the frozen ceiling; STEP loses one slot after a non-positive batch, while RESET returns immediately to two. All cells use the ten-calendar-day earnings blackout.",
        "",
        "Production and the immutable forward journal are unchanged.",
    ]
    (output_dir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Completed staircase exposure robustness: {output_dir}")
    print(f"Decision: {decision}; complete passes: {len(complete_passes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
