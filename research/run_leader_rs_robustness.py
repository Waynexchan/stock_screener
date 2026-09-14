"""Run the preregistered MarketSmith-style leader robustness backtest."""

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
from research.engine.execution import simulate_trade
from research.engine.features import generate_model_0_features
from research.engine.leader_features import (
    enrich_leader_features,
    load_current_sector_industry,
)
from research.engine.market_features import enrich_market_features
from research.engine.models import ExecutionAssumptions, FeatureRecord, SimulatedTrade
from research.engine.portfolio_overlays import simulate_portfolio_overlay
from research.engine.reporting import ensure_research_output_path
from research.engine.reproducibility import git_state, sha256_file
from research.run_combined_exit_exposure_grid import discovery_period_returns


PREREGISTRATION_COMMIT = "48512fb"


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--prices", type=Path, required=True)
    command.add_argument("--benchmark", type=Path, required=True)
    command.add_argument("--earnings", type=Path, required=True)
    command.add_argument("--earnings-metadata", type=Path, required=True)
    command.add_argument(
        "--output-dir",
        type=Path,
        default=Path("research/output/leader_rs_robustness_v1"),
    )
    return command


def rule_mask(frame: pd.DataFrame, rule: dict[str, Any]) -> pd.Series:
    """Evaluate one preregistered rule and fail closed on missing values."""

    operator = str(rule["operator"])
    if operator == "any":
        nested = rule.get("rules")
        if not isinstance(nested, list) or not nested:
            raise ValueError("any rule requires a non-empty rules list")
        mask = pd.Series(False, index=frame.index, dtype=bool)
        for child in nested:
            mask |= rule_mask(frame, child)
        return mask
    values = frame[rule["column"]]
    target = rule.get("value")
    if operator == ">=":
        return pd.to_numeric(values, errors="coerce").ge(float(target)).fillna(False)
    if operator == ">":
        return pd.to_numeric(values, errors="coerce").gt(float(target)).fillna(False)
    if operator == "<=":
        return pd.to_numeric(values, errors="coerce").le(float(target)).fillna(False)
    if operator == "between":
        if not isinstance(target, list) or len(target) != 2:
            raise ValueError("between rule requires exactly two values")
        return (
            pd.to_numeric(values, errors="coerce")
            .between(float(target[0]), float(target[1]))
            .fillna(False)
        )
    if operator == "is_true":
        return values.eq(True).fillna(False)
    if operator == "is_false":
        return values.eq(False).fillna(False)
    raise ValueError(f"unsupported rule operator: {operator}")


def resolved_variant_rules(
    variants: list[dict[str, Any]], variant: dict[str, Any]
) -> list[dict[str, Any]]:
    by_id = {str(item["id"]): item for item in variants}
    rules: list[dict[str, Any]] = []
    base = variant.get("base_variant")
    seen: set[str] = set()
    while base is not None:
        base_id = str(base)
        if base_id in seen or base_id not in by_id:
            raise ValueError(f"invalid variant inheritance: {base_id}")
        seen.add(base_id)
        parent = by_id[base_id]
        rules = list(parent.get("rules", [])) + rules
        base = parent.get("base_variant")
    return rules + list(variant.get("rules", []))


def variant_mask(
    frame: pd.DataFrame,
    variants: list[dict[str, Any]],
    variant: dict[str, Any],
) -> pd.Series:
    mask = pd.Series(True, index=frame.index, dtype=bool)
    for rule in resolved_variant_rules(variants, variant):
        mask &= rule_mask(frame, rule)
    return mask


def meets_stage_gate(
    metrics: dict[str, Any], gate: dict[str, Any], *, development: bool
) -> bool:
    required = [
        "maximum_drawdown_pct",
        "total_return_pct",
        "expectancy_per_trade_r",
        "profit_factor",
        "accepted_trade_count",
        "missing_mark_count",
    ]
    if development:
        required += ["early_period_return_pct", "late_period_return_pct"]
    if any(metrics.get(name) is None for name in required):
        return False
    passed = bool(
        float(metrics["maximum_drawdown_pct"])
        <= float(gate["maximum_drawdown_pct_at_most"])
        and float(metrics["total_return_pct"]) > float(gate["total_return_pct_above"])
        and float(metrics["expectancy_per_trade_r"])
        > float(gate["expectancy_per_trade_r_above"])
        and float(metrics["profit_factor"]) >= float(gate["profit_factor_at_least"])
        and int(metrics["accepted_trade_count"])
        >= int(gate["accepted_trade_count_at_least"])
        and int(metrics["missing_mark_count"]) == int(gate["missing_mark_count"])
    )
    if development:
        passed = bool(
            passed
            and float(metrics["early_period_return_pct"])
            > float(gate["early_period_return_pct_above"])
            and float(metrics["late_period_return_pct"])
            > float(gate["late_period_return_pct_above"])
        )
    return passed


def _feature(row: dict[str, Any]) -> FeatureRecord:
    return FeatureRecord(
        **{name: row.get(name) for name in FeatureRecord.__dataclass_fields__}
    )


def _simulate_independent(
    signals: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    assumptions: ExecutionAssumptions,
    outcome_end: str,
) -> dict[tuple[str, str], SimulatedTrade]:
    result: dict[tuple[str, str], SimulatedTrade] = {}
    cutoff = pd.Timestamp(outcome_end)
    for row in signals.to_dict("records"):
        feature = _feature(row)
        history = histories.get(feature.ticker)
        if history is None:
            continue
        trade = simulate_trade(feature, history, assumptions)
        if trade is None:
            continue
        if pd.Timestamp(trade.exit_date) > cutoff:
            raise AssertionError("trade outcome crossed the frozen stage boundary")
        result[(trade.signal_date, trade.ticker)] = trade
    return result


def _largest_winner_metrics(ledger: pd.DataFrame) -> dict[str, float | None]:
    if ledger.empty:
        return {
            "largest_winner_r": None,
            "largest_winner_share_of_positive_pnl": None,
            "total_pnl_ex_largest_winner_r": None,
        }
    outcomes = pd.to_numeric(ledger["portfolio_realised_r"], errors="coerce")
    positive = outcomes[outcomes > 0]
    largest = float(positive.max()) if len(positive) else 0.0
    positive_total = float(positive.sum())
    total = float(outcomes.sum())
    return {
        "largest_winner_r": largest,
        "largest_winner_share_of_positive_pnl": (
            None if positive_total <= 0 else largest / positive_total
        ),
        "total_pnl_ex_largest_winner_r": total - largest,
    }


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
    for variant in variants:
        selected = signals[variant_mask(signals, variants, variant)].copy()
        trades = [
            independent[key]
            for key in zip(selected["signal_date"], selected["ticker"], strict=False)
            if key in independent
        ]
        metrics, ledger, curve = simulate_portfolio_overlay(
            trades,
            histories,
            sessions,
            portfolio,
            starting_equity_r=float(experiment["portfolio"]["starting_equity_r"]),
            maximum_positions=int(experiment["portfolio"]["maximum_positions"]),
        )
        metrics["signal_count"] = len(signals)
        metrics["selected_signal_count"] = len(selected)
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
        "reported_variant_count": len(rows),
    }


def _delta(value: Any, baseline: Any) -> float | None:
    if value is None or baseline is None:
        return None
    return float(value) - float(baseline)


def add_baseline_deltas(rows: list[dict[str, Any]]) -> None:
    metrics = (
        "total_return_pct",
        "cagr_pct",
        "maximum_drawdown_pct",
        "expectancy_per_trade_r",
        "profit_factor",
        "accepted_trade_count",
        "return_to_drawdown",
    )
    for stage in sorted({str(row["stage"]) for row in rows}):
        stage_rows = [row for row in rows if row["stage"] == stage]
        baseline = next(row for row in stage_rows if row["variant_id"] == "baseline")
        for row in stage_rows:
            for metric in metrics:
                row[f"{metric}_delta_vs_baseline"] = _delta(
                    row.get(metric), baseline.get(metric)
                )


def cross_stage_summary(
    rows: list[dict[str, Any]], stage_order: list[str], experiment: dict[str, Any]
) -> list[dict[str, Any]]:
    by_key = {(str(row["stage"]), str(row["variant_id"])): row for row in rows}
    limit = float(
        experiment["cross_stage_shortlist"][
            "largest_winner_positive_pnl_contribution_at_most"
        ]
    )
    result: list[dict[str, Any]] = []
    for variant in experiment["variants"]:
        variant_id = str(variant["id"])
        stage_rows = [by_key[(stage, variant_id)] for stage in stage_order]
        return_improvements = sum(
            float(row.get("total_return_pct_delta_vs_baseline") or 0) > 0
            for row in stage_rows
        )
        ratio_improvements = sum(
            float(row.get("return_to_drawdown_delta_vs_baseline") or 0) > 0
            for row in stage_rows
        )
        outlier_ok = all(
            row.get("largest_winner_share_of_positive_pnl") is not None
            and float(row["largest_winner_share_of_positive_pnl"]) <= limit
            for row in stage_rows
        )
        all_gates = all(bool(row["passes_stage_gate"]) for row in stage_rows)
        shortlist = bool(
            variant_id != "baseline"
            and all_gates
            and return_improvements
            >= int(
                experiment["cross_stage_shortlist"][
                    "total_return_beats_baseline_in_at_least_periods"
                ]
            )
            and ratio_improvements
            >= int(
                experiment["cross_stage_shortlist"][
                    "return_to_drawdown_beats_baseline_in_at_least_periods"
                ]
            )
            and outlier_ok
        )
        result.append(
            {
                "variant_id": variant_id,
                "passes_all_stage_gates": all_gates,
                "return_improvement_period_count": return_improvements,
                "return_to_drawdown_improvement_period_count": ratio_improvements,
                "largest_winner_contribution_passes_all_periods": outlier_ok,
                "cross_stage_shortlist": shortlist,
                **{
                    f"{stage}_{metric}": by_key[(stage, variant_id)].get(metric)
                    for stage in stage_order
                    for metric in (
                        "selected_signal_count",
                        "accepted_trade_count",
                        "total_return_pct",
                        "maximum_drawdown_pct",
                        "expectancy_per_trade_r",
                        "profit_factor",
                        "return_to_drawdown",
                        "largest_winner_share_of_positive_pnl",
                        "passes_stage_gate",
                    )
                },
            }
        )
    return result


def _format(value: Any) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "—"
    if isinstance(value, bool):
        return "YES" if value else "NO"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _stage_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Variant | Signals | Trades | Return % | Max DD % | Exp R | PF | Return/DD | Largest winner share | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['variant_id']} | "
            + " | ".join(
                _format(row.get(name))
                for name in (
                    "selected_signal_count",
                    "accepted_trade_count",
                    "total_return_pct",
                    "maximum_drawdown_pct",
                    "expectancy_per_trade_r",
                    "profit_factor",
                    "return_to_drawdown",
                    "largest_winner_share_of_positive_pnl",
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
        project_root / "research" / "experiments" / "leader_rs_robustness_v1.json"
    )
    model_path = project_root / "research" / "config" / "model_0.json"
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    if len(experiment["variants"]) != int(experiment["variant_count"]):
        raise ValueError("preregistered leader variant count does not match")
    if len({item["id"] for item in experiment["variants"]}) != len(
        experiment["variants"]
    ):
        raise ValueError("leader variant ids must be unique")
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
        "# LEADER_RS_ROBUSTNESS_V1",
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
        "The proxy is not MarketSmith's proprietary RS Rating. The universe contains current survivors, industry labels are current rather than effective-dated, earnings dates are retrospective, and every historical period is reused. Results are robustness evidence only.",
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
