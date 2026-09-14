"""Run the preregistered completed leader-selection robustness backtest."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd

from research.engine.base_features import (
    delayed_followthrough_signals,
    enrich_base_features,
)
from research.engine.baseline import execution_assumptions, load_model_0_config
from research.engine.data import load_price_csv
from research.engine.earnings import (
    EarningsBlackoutContext,
    apply_earnings_blackout_to_signals,
    load_verified_earnings_blackout_context,
)
from research.engine.features import generate_model_0_features
from research.engine.leader_features import (
    enrich_leader_features,
    load_current_sector_industry,
)
from research.engine.market_features import enrich_market_features
from research.engine.models import ExecutionAssumptions, SimulatedTrade
from research.engine.portfolio_overlays import simulate_portfolio_overlay
from research.engine.reporting import ensure_research_output_path
from research.engine.reproducibility import git_state, sha256_file
from research.run_combined_exit_exposure_grid import discovery_period_returns
from research.run_leader_rs_robustness import (
    _largest_winner_metrics,
    _simulate_independent,
    _stage_table,
    add_baseline_deltas,
    cross_stage_summary,
    meets_stage_gate,
    variant_mask,
)


PREREGISTRATION_COMMIT = "b34c90b"


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--prices", type=Path, required=True)
    command.add_argument("--benchmark", type=Path, required=True)
    command.add_argument("--earnings", type=Path, required=True)
    command.add_argument("--earnings-metadata", type=Path, required=True)
    command.add_argument(
        "--output-dir",
        type=Path,
        default=Path("research/output/leader_completeness_v2"),
    )
    return command


def _key(row: Any) -> tuple[str, str]:
    return str(row.signal_date), str(row.ticker)


def candidate_priorities(
    selected: pd.DataFrame, mode: str | None
) -> dict[tuple[str, str], tuple[float, ...]] | None:
    """Return ascending sort keys; negative values implement descending ranks."""

    if mode is None:
        return None
    if mode != "INDUSTRY_THEN_STOCK":
        raise ValueError(f"unsupported candidate order: {mode}")
    priorities: dict[tuple[str, str], tuple[float, ...]] = {}
    for row in selected.itertuples(index=False):
        scores = (
            pd.to_numeric(getattr(row, "industry_proxy_score"), errors="coerce"),
            pd.to_numeric(getattr(row, "stock_within_industry_score"), errors="coerce"),
            pd.to_numeric(getattr(row, "marketsmith_proxy_score"), errors="coerce"),
        )
        priorities[_key(row)] = tuple(
            -float(value) if pd.notna(value) else float("inf") for value in scores
        )
    return priorities


def candidate_risks(
    selected: pd.DataFrame, mode: str | None
) -> dict[tuple[str, str], float] | None:
    if mode is None:
        return None
    if mode != "INDUSTRY_SECONDARY_HALF":
        raise ValueError(f"unsupported risk mode: {mode}")
    risks: dict[tuple[str, str], float] = {}
    for row in selected.itertuples(index=False):
        score = pd.to_numeric(getattr(row, "industry_proxy_score"), errors="coerce")
        risks[_key(row)] = 1.0 if pd.notna(score) and float(score) >= 80 else 0.5
    return risks


def _trades_for_selected(
    selected: pd.DataFrame,
    independent: dict[tuple[str, str], SimulatedTrade],
) -> list[SimulatedTrade]:
    return [
        independent[key]
        for key in zip(selected["signal_date"], selected["ticker"], strict=False)
        if key in independent
    ]


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
    independent = _simulate_independent(signals, histories, assumptions, outcome_end)
    portfolio = {"type": "FIXED", "maximum_heat_r": 2.0, "risk_per_trade_r": 1.0}
    rows: list[dict[str, Any]] = []
    variants = experiment["variants"]
    delayed_confirmation_total = 0
    delayed_blackout_rejection_total = 0
    for variant in variants:
        selected = signals[variant_mask(signals, variants, variant)].copy()
        execution_mode = variant.get("execution_mode")
        confirmation_count: int | None = None
        confirmation_rejection_count: int | None = None
        execution_signals = selected
        execution_map = independent
        if execution_mode == "DELAYED_FOLLOWTHROUGH_3D":
            execution_signals = delayed_followthrough_signals(
                selected,
                histories,
                maximum_confirmation_sessions=3,
                signal_period_end=signal_period[1],
            )
            confirmation_count = len(execution_signals)
            execution_signals, confirmation_rejected = (
                apply_earnings_blackout_to_signals(
                    execution_signals, blackout, blackout_calendar_days=10
                )
            )
            confirmation_rejection_count = len(confirmation_rejected)
            confirmation_rejected.to_csv(
                stage_dir / "confirmation_blackout_rejections.csv", index=False
            )
            execution_map = _simulate_independent(
                execution_signals, histories, assumptions, outcome_end
            )
            delayed_confirmation_total += confirmation_count
            delayed_blackout_rejection_total += confirmation_rejection_count
        elif execution_mode is not None:
            raise ValueError(f"unsupported execution mode: {execution_mode}")

        trades = _trades_for_selected(execution_signals, execution_map)
        order_mode = variant.get("candidate_order")
        risk_mode = variant.get("risk_mode")
        metrics, ledger, curve = simulate_portfolio_overlay(
            trades,
            histories,
            sessions,
            portfolio,
            starting_equity_r=float(experiment["portfolio"]["starting_equity_r"]),
            maximum_positions=int(experiment["portfolio"]["maximum_positions"]),
            candidate_priority_by_signal_ticker=candidate_priorities(
                execution_signals, order_mode
            ),
            risk_per_trade_by_signal_ticker=candidate_risks(
                execution_signals, risk_mode
            ),
        )
        metrics["signal_count"] = len(signals)
        metrics["selected_signal_count"] = len(selected)
        metrics["execution_signal_count"] = len(execution_signals)
        metrics["confirmation_signal_count"] = confirmation_count
        metrics["confirmation_blackout_rejection_count"] = confirmation_rejection_count
        metrics["candidate_order"] = order_mode or "DEFAULT_TICKER"
        metrics["risk_mode"] = risk_mode or "FIXED_1R"
        metrics["execution_mode"] = execution_mode or "NEXT_OPEN"
        metrics["variant_id"] = str(variant["id"])
        metrics["stage"] = stage_id
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
        ledger.to_csv(stage_dir / f"ledger__{safe}.csv", index=False)
        curve.to_csv(stage_dir / f"equity__{safe}.csv", index=False)
        rows.append(metrics)
    if len(rows) != int(experiment["variant_count"]):
        raise AssertionError("reported variant count differs from preregistration")
    return rows, {
        "pre_blackout_signal_count": pre_blackout_count,
        "earnings_blackout_rejection_count": len(rejected),
        "post_blackout_signal_count": len(signals),
        "independent_execution_count": len(independent),
        "delayed_confirmation_signal_count": delayed_confirmation_total,
        "delayed_confirmation_blackout_rejection_count": delayed_blackout_rejection_total,
        "reported_variant_count": len(rows),
    }


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    output_dir = ensure_research_output_path(project_root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    experiment_path = project_root / "research/experiments/leader_completeness_v2.json"
    model_path = project_root / "research/config/model_0.json"
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    variants = experiment["variants"]
    if len(variants) != int(experiment["variant_count"]):
        raise ValueError("preregistered variant count does not match")
    if len({item["id"] for item in variants}) != len(variants):
        raise ValueError("variant ids must be unique")

    model_config = load_model_0_config(model_path)
    histories, price_diagnostics = load_price_csv(args.prices)
    benchmarks, benchmark_diagnostics = load_price_csv(args.benchmark)
    if "SPY" not in benchmarks:
        raise ValueError("benchmark file must contain SPY")
    spy = benchmarks["SPY"].sort_index()
    sessions = pd.DatetimeIndex(spy.index).sort_values()
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
    sectors, industries = load_current_sector_industry(project_root)
    signals = enrich_market_features(signals, histories, spy, classifications=sectors)
    signals = enrich_leader_features(
        signals,
        histories,
        spy,
        sectors=sectors,
        industries=industries,
        minimum_industry_members=5,
    )
    signals = enrich_base_features(signals, histories)
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
    shortlist = [row for row in summary if row["cross_stage_shortlist"]]
    mixed_support = [
        row
        for row in summary
        if row["variant_id"] != "baseline"
        and row["return_to_drawdown_improvement_period_count"] >= 2
    ]
    decision = "HOLD" if shortlist or mixed_support else "REJECT"
    pd.DataFrame(rows).to_csv(output_dir / "all_stage_results.csv", index=False)
    pd.DataFrame(summary).to_csv(output_dir / "cross_stage_summary.csv", index=False)

    git_commit, git_dirty = git_state(project_root)
    payload = {
        "experiment": experiment,
        "execution_status": "COMPLETED_ADAPTIVE_ROBUSTNESS_NO_UNTOUCHED_HOLDOUT",
        "research_label": experiment["research_label"],
        "historical_decision": decision,
        "preregistration_commit": PREREGISTRATION_COMMIT,
        "run_git_commit": git_commit,
        "run_git_dirty": git_dirty,
        "production_effect": "NONE",
        "untouched_holdout_evaluated": False,
        "shortlist_count": len(shortlist),
        "mixed_support_count": len(mixed_support),
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
        "all_stage_results": rows,
        "cross_stage_summary": summary,
    }
    (output_dir / "results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    report = [
        "# LEADER_COMPLETENESS_V2",
        "",
        "> **SURVIVORSHIP-, EARNINGS-SCHEDULE-, AND CLASSIFICATION-BIASED RESEARCH — NO UNTOUCHED HOLDOUT**",
        "",
        f"Historical decision: **{decision}**",
        f"Cross-stage shortlist count: {len(shortlist)}",
        f"Mixed-support count: {len(mixed_support)}",
        "Fundamental acceleration: **BLOCKED_DATA_NOT_READY**",
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
        "Every period is reused adaptive robustness. The universe contains current survivors, industry labels are current, earnings dates are retrospective, base stages are mechanical proxies, and the RS score is not MarketSmith's proprietary rating.",
        "",
        "Production and the immutable forward journal are unchanged.",
    ]
    (output_dir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(
        f"Decision: {decision}; shortlist: {len(shortlist)}; mixed support: {len(mixed_support)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
