"""Run the preregistered individual-filter and bounded-combination audit."""

from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research.engine.base_features import enrich_base_features
from research.engine.baseline import execution_assumptions, load_model_0_config
from research.engine.data import load_price_csv
from research.engine.earnings import load_verified_earnings_blackout_context
from research.engine.features import generate_model_0_features
from research.engine.leader_features import (
    enrich_leader_features,
    load_current_sector_industry,
)
from research.engine.market_features import enrich_market_features
from research.engine.reporting import ensure_research_output_path
from research.engine.reproducibility import git_state, sha256_file
from research.run_leader_completeness_v2 import _stage
from research.run_leader_rs_robustness import (
    add_baseline_deltas,
    cross_stage_summary,
)


METRIC_NAMES = (
    "total_return_pct",
    "maximum_drawdown_pct",
    "expectancy_per_trade_r",
    "profit_factor",
    "return_to_drawdown",
    "selected_signal_count",
    "accepted_trade_count",
)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--prices", type=Path, required=True)
    command.add_argument("--benchmark", type=Path, required=True)
    command.add_argument("--earnings", type=Path, required=True)
    command.add_argument("--earnings-metadata", type=Path, required=True)
    command.add_argument(
        "--output-dir",
        type=Path,
        default=Path("research/output/filter_combination_audit_v1"),
    )
    return command


def _factorial_variant_id(component_ids: tuple[str, ...]) -> str:
    return "baseline" if not component_ids else "combo__" + "__".join(component_ids)


def generate_variants(experiment: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand the frozen complete factorial and supplemental single variants."""

    components = experiment["factorial_components"]
    variants: list[dict[str, Any]] = []
    for size in range(len(components) + 1):
        for selected in itertools.combinations(components, size):
            component_ids = tuple(str(item["id"]) for item in selected)
            variants.append(
                {
                    "id": _factorial_variant_id(component_ids),
                    "rules": [
                        dict(rule) for item in selected for rule in item["rules"]
                    ],
                    "component_ids": list(component_ids),
                    "variant_family": "FACTORIAL",
                }
            )
    for item in experiment["supplemental_individual_filters"]:
        variants.append(
            {
                "id": str(item["id"]),
                "rules": [dict(rule) for rule in item["rules"]],
                "component_ids": [],
                "variant_family": "SUPPLEMENTAL_INDIVIDUAL",
            }
        )
    ids = [str(item["id"]) for item in variants]
    expected = int(experiment["variant_count"])
    if len(variants) != expected or len(set(ids)) != expected:
        raise ValueError("generated filter matrix differs from preregistration")
    if sum(item["variant_family"] == "FACTORIAL" for item in variants) != int(
        experiment["factorial_subset_count"]
    ):
        raise ValueError("factorial subset count differs from preregistration")
    return variants


def enrich_spy_signal_trend(
    signals: pd.DataFrame, benchmark: pd.DataFrame
) -> pd.DataFrame:
    """Add a signal-close SPY/SMA50 state without using future sessions."""

    result = signals.copy()
    spy = pd.to_numeric(benchmark["Close"], errors="coerce").sort_index()
    spy.index = pd.to_datetime(spy.index)
    sma50 = spy.rolling(50, min_periods=50).mean()
    state = spy.gt(sma50).where(spy.notna() & sma50.notna())
    lookup = {date.date().isoformat(): value for date, value in state.items()}
    result["spy_above_sma50"] = result["signal_date"].astype(str).map(lookup)
    return result


def _delta(child: Any, parent: Any) -> float | None:
    if child is None or parent is None or pd.isna(child) or pd.isna(parent):
        return None
    return float(child) - float(parent)


def marginal_pairs(
    rows: list[dict[str, Any]],
    variants: list[dict[str, Any]],
    component_ids: list[str],
    stage_order: list[str],
) -> list[dict[str, Any]]:
    """Pair every factorial context with and without each component."""

    result_by_key = {(str(row["stage"]), str(row["variant_id"])): row for row in rows}
    id_by_components = {
        tuple(str(value) for value in variant["component_ids"]): str(variant["id"])
        for variant in variants
        if variant["variant_family"] == "FACTORIAL"
    }
    pairs: list[dict[str, Any]] = []
    for component in component_ids:
        remaining = [value for value in component_ids if value != component]
        for size in range(len(remaining) + 1):
            for context in itertools.combinations(remaining, size):
                without_components = tuple(
                    value for value in component_ids if value in context
                )
                with_components = tuple(
                    value
                    for value in component_ids
                    if value in set(context) | {component}
                )
                without_id = id_by_components[without_components]
                with_id = id_by_components[with_components]
                for stage in stage_order:
                    child = result_by_key[(stage, with_id)]
                    parent = result_by_key[(stage, without_id)]
                    pair: dict[str, Any] = {
                        "component_id": component,
                        "stage": stage,
                        "context_components": json.dumps(list(without_components)),
                        "without_variant_id": without_id,
                        "with_variant_id": with_id,
                    }
                    for metric in METRIC_NAMES:
                        pair[f"{metric}_delta"] = _delta(
                            child.get(metric), parent.get(metric)
                        )
                    pairs.append(pair)
    expected = len(component_ids) * (2 ** (len(component_ids) - 1)) * len(stage_order)
    if len(pairs) != expected:
        raise AssertionError("marginal pair count differs from complete factorial")
    return pairs


def marginal_summary(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(pairs)
    result: list[dict[str, Any]] = []
    for (component, stage), group in frame.groupby(["component_id", "stage"]):
        row: dict[str, Any] = {
            "component_id": str(component),
            "stage": str(stage),
            "paired_context_count": len(group),
        }
        for metric in METRIC_NAMES:
            values = pd.to_numeric(group[f"{metric}_delta"], errors="coerce").dropna()
            row[f"median_{metric}_delta"] = (
                None if values.empty else float(values.median())
            )
            row[f"mean_{metric}_delta"] = None if values.empty else float(values.mean())
            if metric == "maximum_drawdown_pct":
                row[f"improving_{metric}_context_count"] = int((values < 0).sum())
            else:
                row[f"improving_{metric}_context_count"] = int((values > 0).sum())
        result.append(row)
    return result


def _leave_one_out_support(
    components: list[str],
    rows_by_key: dict[tuple[str, str], dict[str, Any]],
    stage_order: list[str],
    id_by_components: dict[tuple[str, ...], str],
    required_return_periods: int,
    required_ratio_periods: int,
) -> tuple[bool, dict[str, dict[str, int]]]:
    details: dict[str, dict[str, int]] = {}
    for component in components:
        parent_components = tuple(value for value in components if value != component)
        child_id = id_by_components[tuple(components)]
        parent_id = id_by_components[parent_components]
        return_count = 0
        ratio_count = 0
        for stage in stage_order:
            child = rows_by_key[(stage, child_id)]
            parent = rows_by_key[(stage, parent_id)]
            return_count += bool(
                (
                    _delta(
                        child.get("total_return_pct"), parent.get("total_return_pct")
                    )
                    or 0
                )
                > 0
            )
            ratio_count += bool(
                (
                    _delta(
                        child.get("return_to_drawdown"),
                        parent.get("return_to_drawdown"),
                    )
                    or 0
                )
                > 0
            )
        details[component] = {
            "return_improvement_period_count": return_count,
            "return_to_drawdown_improvement_period_count": ratio_count,
        }
    supported = all(
        detail["return_improvement_period_count"] >= required_return_periods
        and detail["return_to_drawdown_improvement_period_count"]
        >= required_ratio_periods
        for detail in details.values()
    )
    return supported, details


def combination_decisions(
    summary: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    variants: list[dict[str, Any]],
    stage_order: list[str],
    gate: dict[str, Any],
) -> list[dict[str, Any]]:
    variant_by_id = {str(item["id"]): item for item in variants}
    rows_by_key = {(str(row["stage"]), str(row["variant_id"])): row for row in rows}
    id_by_components = {
        tuple(str(value) for value in variant["component_ids"]): str(variant["id"])
        for variant in variants
        if variant["variant_family"] == "FACTORIAL"
    }
    decisions: list[dict[str, Any]] = []
    for item in summary:
        variant = variant_by_id[str(item["variant_id"])]
        components = [str(value) for value in variant["component_ids"]]
        factorial = variant["variant_family"] == "FACTORIAL"
        support = False
        details: dict[str, dict[str, int]] = {}
        if factorial and components:
            support, details = _leave_one_out_support(
                components,
                rows_by_key,
                stage_order,
                id_by_components,
                int(
                    gate[
                        "each_component_leave_one_out_return_improvement_periods_at_least"
                    ]
                ),
                int(
                    gate[
                        "each_component_leave_one_out_return_to_drawdown_improvement_periods_at_least"
                    ]
                ),
            )
        decision_shortlist = bool(
            factorial
            and 0 < len(components) <= int(gate["maximum_component_count"])
            and item["cross_stage_shortlist"]
            and support
        )
        decisions.append(
            {
                **item,
                "variant_family": variant["variant_family"],
                "component_count": len(components),
                "component_ids": json.dumps(components),
                "leave_one_out_support": support,
                "leave_one_out_details": json.dumps(details, sort_keys=True),
                "decision_shortlist": decision_shortlist,
            }
        )
    return decisions


def individual_filter_summary(
    decisions: list[dict[str, Any]],
    variants: list[dict[str, Any]],
    component_ids: list[str],
) -> list[dict[str, Any]]:
    decision_by_id = {str(item["variant_id"]): item for item in decisions}
    individual_map = {
        component: _factorial_variant_id((component,)) for component in component_ids
    }
    individual_map.update(
        {
            str(item["id"]): str(item["id"])
            for item in variants
            if item["variant_family"] == "SUPPLEMENTAL_INDIVIDUAL"
        }
    )
    output: list[dict[str, Any]] = []
    for filter_id, variant_id in individual_map.items():
        row = decision_by_id[variant_id]
        stage_trades = [
            int(row[f"{stage}_accepted_trade_count"])
            for stage in (
                "development_2017_2023",
                "reused_2024",
                "reused_2025",
            )
        ]
        if stage_trades[0] < 75 or min(stage_trades[1:]) < 8:
            evidence_label = "INCONCLUSIVE_SPARSE"
        elif row["cross_stage_shortlist"]:
            evidence_label = "CONSISTENT_POSITIVE"
        elif (
            int(row["return_improvement_period_count"]) == 0
            and int(row["return_to_drawdown_improvement_period_count"]) == 0
        ):
            evidence_label = "NEGATIVE_OR_NO_VALUE"
        else:
            evidence_label = "MIXED"
        output.append(
            {
                "filter_id": filter_id,
                "variant_id": variant_id,
                "evidence_label": evidence_label,
                **{
                    key: value
                    for key, value in row.items()
                    if key
                    in {
                        "passes_all_stage_gates",
                        "return_improvement_period_count",
                        "return_to_drawdown_improvement_period_count",
                        "largest_winner_contribution_passes_all_periods",
                    }
                    or key.startswith("development_2017_2023_")
                    or key.startswith("reused_2024_")
                    or key.startswith("reused_2025_")
                },
            }
        )
    return output


def cumulative_funnel(
    rows: list[dict[str, Any]],
    diagnostics: dict[str, Any],
    stage_order: list[str],
    order: list[str],
) -> list[dict[str, Any]]:
    by_key = {(str(row["stage"]), str(row["variant_id"])): row for row in rows}
    output: list[dict[str, Any]] = []
    for stage in stage_order:
        raw = int(diagnostics[stage]["pre_blackout_signal_count"])
        previous = raw
        output.append(
            {
                "stage": stage,
                "step": "raw_model_0",
                "selected_signal_count": raw,
                "candidate_trade_count": None,
                "accepted_trade_count": None,
                "retention_vs_previous_pct": 100.0,
                "retention_vs_raw_pct": 100.0,
                "capacity_acceptance_pct": None,
            }
        )
        steps: list[tuple[str, str]] = [("earnings_eligible", "baseline")]
        prefix: list[str] = []
        for component in order:
            prefix.append(component)
            steps.append((component, _factorial_variant_id(tuple(prefix))))
        for step, variant_id in steps:
            row = by_key[(stage, variant_id)]
            selected = int(row["selected_signal_count"])
            accepted = int(row["accepted_trade_count"])
            # Older staged-result schemas do not always retain the redundant
            # candidate count.  Every candidate is admitted or rejected once,
            # so reconstructing it from those two canonical counts is exact.
            reconstructed_candidates = accepted + int(row["rejection_count"])
            reported_candidates = row.get("candidate_trade_count")
            if (
                reported_candidates is not None
                and int(reported_candidates) != reconstructed_candidates
            ):
                raise AssertionError(
                    "candidate count does not reconcile with admissions and rejections"
                )
            candidate_count = reconstructed_candidates
            output.append(
                {
                    "stage": stage,
                    "step": step,
                    "variant_id": variant_id,
                    "selected_signal_count": selected,
                    "candidate_trade_count": candidate_count,
                    "accepted_trade_count": accepted,
                    "retention_vs_previous_pct": (
                        0.0 if previous == 0 else selected / previous * 100
                    ),
                    "retention_vs_raw_pct": (0.0 if raw == 0 else selected / raw * 100),
                    "capacity_acceptance_pct": (
                        0.0
                        if candidate_count == 0
                        else accepted / candidate_count * 100
                    ),
                    "rejection_count": int(row["rejection_count"]),
                    "rejection_reasons": row["rejection_reasons"],
                }
            )
            previous = selected
    return output


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "—"
    if isinstance(value, (bool, np.bool_)):
        return "YES" if bool(value) else "NO"
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.{digits}f}"
    return str(value)


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
        *("| " + " | ".join(_fmt(value) for value in row) + " |" for row in rows),
    ]


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    output_dir = ensure_research_output_path(project_root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    experiment_path = (
        project_root / "research/experiments/filter_combination_audit_v1.json"
    )
    model_path = project_root / "research/config/model_0.json"
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    variants = generate_variants(experiment)
    run_experiment = {**experiment, "variants": variants}

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
    signals = enrich_spy_signal_trend(signals, spy)
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
    variant_by_id = {str(item["id"]): item for item in variants}
    for stage, period, outcome_end, development in stage_specs:
        stage_rows, stage_diagnostics = _stage(
            stage_id=stage,
            signal_period=period,
            outcome_end=outcome_end,
            development=development,
            all_signals=signals,
            experiment=run_experiment,
            histories=histories,
            sessions=sessions,
            blackout=blackout,
            assumptions=assumptions,
            output_dir=output_dir,
        )
        for row in stage_rows:
            variant = variant_by_id[str(row["variant_id"])]
            row["variant_family"] = variant["variant_family"]
            row["component_count"] = len(variant["component_ids"])
            row["component_ids"] = json.dumps(variant["component_ids"])
        rows.extend(stage_rows)
        diagnostics[stage] = stage_diagnostics
        print(f"Completed {stage}: {len(stage_rows)} variants", flush=True)

    add_baseline_deltas(rows)
    stage_order = [item[0] for item in stage_specs]
    summary = cross_stage_summary(rows, stage_order, run_experiment)
    decisions = combination_decisions(
        summary,
        rows,
        variants,
        stage_order,
        experiment["cross_stage_shortlist"],
    )
    shortlist = [row for row in decisions if row["decision_shortlist"]]
    decision = "HOLD" if shortlist else "REJECT"
    component_ids = [str(item["id"]) for item in experiment["factorial_components"]]
    pairs = marginal_pairs(rows, variants, component_ids, stage_order)
    marginal = marginal_summary(pairs)
    individual = individual_filter_summary(decisions, variants, component_ids)
    funnel = cumulative_funnel(
        rows,
        diagnostics,
        stage_order,
        [str(value) for value in experiment["cumulative_funnel_order"]],
    )

    pd.DataFrame(rows).to_csv(output_dir / "all_stage_results.csv", index=False)
    pd.DataFrame(decisions).to_csv(
        output_dir / "combination_decisions.csv", index=False
    )
    pd.DataFrame(individual).to_csv(
        output_dir / "individual_filter_summary.csv", index=False
    )
    pd.DataFrame(pairs).to_csv(output_dir / "marginal_pairs.csv", index=False)
    pd.DataFrame(marginal).to_csv(output_dir / "marginal_summary.csv", index=False)
    pd.DataFrame(funnel).to_csv(output_dir / "cumulative_funnel.csv", index=False)

    git_commit, git_dirty = git_state(project_root)
    payload = {
        "experiment": experiment,
        "generated_variants": variants,
        "execution_status": "COMPLETED_ADAPTIVE_DIAGNOSTIC_NO_UNTOUCHED_HOLDOUT",
        "research_label": experiment["research_label"],
        "historical_decision": decision,
        "preregistration_commit": experiment["preregistration_commit"],
        "run_git_commit": git_commit,
        "run_git_dirty": git_dirty,
        "production_effect": "NONE",
        "untouched_holdout_evaluated": False,
        "decision_shortlist_count": len(shortlist),
        "reported_variant_count": len(variants),
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
        "combination_decisions": decisions,
        "individual_filter_summary": individual,
        "marginal_summary": marginal,
        "cumulative_funnel": funnel,
    }
    (output_dir / "results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )

    baseline_funnel = [
        row for row in funnel if row["step"] in {"raw_model_0", "earnings_eligible"}
    ]
    individual_rows = []
    for item in individual:
        individual_rows.append(
            [
                item["filter_id"],
                item["evidence_label"],
                item["development_2017_2023_accepted_trade_count"],
                item["development_2017_2023_total_return_pct"],
                item["development_2017_2023_maximum_drawdown_pct"],
                item["reused_2024_total_return_pct"],
                item["reused_2025_total_return_pct"],
            ]
        )
    marginal_rows = [
        [
            item["component_id"],
            item["stage"],
            item["median_total_return_pct_delta"],
            item["improving_total_return_pct_context_count"],
            item["median_return_to_drawdown_delta"],
            item["improving_return_to_drawdown_context_count"],
        ]
        for item in marginal
    ]
    report = [
        "# FILTER_COMBINATION_AUDIT_V1",
        "",
        f"> **{experiment['research_label']}**",
        "",
        f"Historical decision: **{decision}**",
        f"Reported variants: {len(variants)}",
        f"Decision shortlist count: {len(shortlist)}",
        "Production effect: **NONE**",
        "",
        "## Baseline scarcity",
        "",
        *_markdown_table(
            ["Stage", "Step", "Signals", "Candidate trades", "Accepted", "Capacity %"],
            [
                [
                    item["stage"],
                    item["step"],
                    item["selected_signal_count"],
                    item.get("candidate_trade_count"),
                    item.get("accepted_trade_count"),
                    item.get("capacity_acceptance_pct"),
                ]
                for item in baseline_funnel
            ],
        ),
        "",
        "## Individual filters",
        "",
        *_markdown_table(
            [
                "Filter",
                "Evidence",
                "Dev trades",
                "Dev return",
                "Dev DD",
                "2024 return",
                "2025 return",
            ],
            individual_rows,
        ),
        "",
        "## Factorial marginal effects",
        "",
        *_markdown_table(
            [
                "Component",
                "Stage",
                "Median return delta",
                "Positive / 32",
                "Median return/DD delta",
                "Positive / 32",
            ],
            marginal_rows,
        ),
        "",
        "## Decision shortlist",
        "",
    ]
    if shortlist:
        report += [
            *_markdown_table(
                ["Variant", "Components", "Return wins", "Return/DD wins"],
                [
                    [
                        item["variant_id"],
                        item["component_ids"],
                        item["return_improvement_period_count"],
                        item["return_to_drawdown_improvement_period_count"],
                    ]
                    for item in shortlist
                ],
            ),
            "",
        ]
    else:
        report += ["None.", ""]
    report += [
        "## Interpretation boundary",
        "",
        "Every period is reused adaptive diagnosis. The archive contains current survivors, industry labels are current, earnings dates are retrospective, and exact production manual/fundamental/sister/structural-target logic is unavailable. Full results and all losing combinations are retained in the accompanying CSV and JSON artifacts.",
        "",
        "Production and the immutable forward journal are unchanged.",
    ]
    (output_dir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Decision: {decision}; shortlist: {len(shortlist)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
