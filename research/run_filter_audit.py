"""Run the preregistered survivorship-biased engineering filter audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from research.engine.baseline import execution_assumptions, load_model_0_config
from research.engine.data import load_price_csv
from research.engine.execution import simulate_trade
from research.engine.features import generate_model_0_features
from research.engine.market_features import (
    enrich_market_features,
    load_current_classifications,
)
from research.engine.metrics import calculate_metrics
from research.engine.models import ExecutionAssumptions, FeatureRecord
from research.engine.portfolio import apply_position_capacity
from research.engine.reporting import ensure_research_output_path


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--prices", type=Path, required=True)
    command.add_argument("--benchmark", type=Path, required=True)
    command.add_argument(
        "--output-dir", type=Path, default=Path("research/output/filter_audit_v1")
    )
    return command


def filter_mask(frame: pd.DataFrame, specification: dict[str, Any]) -> pd.Series:
    values = frame[specification["column"]]
    operator = specification["operator"]
    target = specification.get("value")
    if operator == ">=":
        return pd.to_numeric(values, errors="coerce").ge(float(target)).fillna(False)
    if operator == "between":
        if not isinstance(target, list) or len(target) != 2:
            raise ValueError("between filter requires a two-value list")
        low, high = target
        return pd.to_numeric(values, errors="coerce").between(low, high).fillna(False)
    if operator == "is_true":
        return values.eq(True).fillna(False)
    if operator == "is_false":
        return values.eq(False).fillna(False)
    raise ValueError(f"unsupported filter operator: {operator}")


def simulate_independent_trades(
    signals: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    assumptions: ExecutionAssumptions,
) -> dict[tuple[str, str], Any]:
    independent: dict[tuple[str, str], Any] = {}
    feature_fields = list(FeatureRecord.__dataclass_fields__)
    for row in signals.to_dict("records"):
        feature = FeatureRecord(**{name: row.get(name) for name in feature_fields})
        history = histories.get(feature.ticker)
        if history is None:
            continue
        trade = simulate_trade(feature, history, assumptions)
        if trade is not None:
            independent[(feature.signal_date, feature.ticker)] = trade
    return independent


def simulated_metrics(
    signals: pd.DataFrame,
    independent: dict[tuple[str, str], Any],
    assumptions: ExecutionAssumptions,
    seed: int,
) -> dict[str, Any]:
    selected = [
        independent[key]
        for key in zip(signals["signal_date"], signals["ticker"], strict=False)
        if key in independent
    ]
    accepted, rejected = apply_position_capacity(
        selected, assumptions.maximum_positions
    )
    metrics = calculate_metrics(
        accepted,
        signal_count=len(signals),
        maximum_positions=assumptions.maximum_positions,
        seed=seed,
    )
    average_win = metrics.get("average_win_r")
    average_loss = metrics.get("average_loss_r")
    metrics["payoff_ratio"] = (
        None
        if average_win is None or average_loss in (None, 0)
        else round(float(average_win) / abs(float(average_loss)), 6)
    )
    metrics["capacity_rejection_count"] = len(rejected)
    return metrics


def metric_delta(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "expectancy_r",
        "profit_factor",
        "maximum_drawdown_r",
        "payoff_ratio",
        "exposure",
    )
    result: dict[str, Any] = {}
    for key in keys:
        left, right = candidate.get(key), baseline.get(key)
        result[key] = (
            None
            if left is None or right is None
            else round(float(left) - float(right), 6)
        )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    output_dir = ensure_research_output_path(project_root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    experiment_path = project_root / "research" / "experiments" / "filter_audit_v1.json"
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    model_config = load_model_0_config(
        project_root / "research" / "config" / "model_0.json"
    )
    histories, _ = load_price_csv(args.prices)
    benchmarks, _ = load_price_csv(args.benchmark)
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
    signals = enrich_market_features(
        signals,
        histories,
        benchmarks["SPY"],
        classifications=load_current_classifications(project_root),
    )
    start, end = experiment["discovery_period"]
    dates = pd.to_datetime(signals["signal_date"])
    discovery = signals[dates.between(start, end)].copy()
    assumptions = execution_assumptions(model_config)
    seed = int(model_config["random_seed"])
    independent = simulate_independent_trades(discovery, histories, assumptions)
    baseline_metrics = simulated_metrics(discovery, independent, assumptions, seed)
    comparisons: dict[str, Any] = {}
    for name, specification in experiment["filters"].items():
        selected = discovery[filter_mask(discovery, specification)].copy()
        metrics = simulated_metrics(selected, independent, assumptions, seed)
        comparisons[name] = {
            "eligible_signal_count": len(selected),
            "excluded_signal_count": len(discovery) - len(selected),
            "metrics": metrics,
            "delta_vs_baseline": metric_delta(metrics, baseline_metrics),
        }
    payload = {
        "experiment": experiment,
        "execution_status": "COMPLETED_SURVIVORSHIP_BIASED_ENGINEERING_DISCOVERY",
        "research_label": "SURVIVORSHIP-BIASED RESEARCH",
        "holdout_evaluated": False,
        "classification_warning": "Utilities use current metadata and are not point-in-time historical classifications.",
        "baseline_metrics": baseline_metrics,
        "comparisons": comparisons,
    }
    signals.to_csv(output_dir / "signal_features.csv", index=False)
    (output_dir / "results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    lines = [
        "# FILTER_AUDIT_V1 engineering discovery",
        "",
        "> **SURVIVORSHIP-BIASED RESEARCH — NOT PRODUCTION EVIDENCE**",
        "",
        f"Discovery signals: {len(discovery)}",
        f"Baseline expectancy R: {baseline_metrics.get('expectancy_r')}",
        f"Baseline profit factor: {baseline_metrics.get('profit_factor')}",
        f"Baseline maximum drawdown R: {baseline_metrics.get('maximum_drawdown_r')}",
        "",
        "| Filter | Kept | Excluded | Expectancy R | Delta R | Profit factor | Max DD R |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, item in comparisons.items():
        metrics = item["metrics"]
        delta = item["delta_vs_baseline"]
        lines.append(
            f"| {name} | {item['eligible_signal_count']} | {item['excluded_signal_count']} | "
            f"{metrics.get('expectancy_r')} | {delta.get('expectancy_r')} | "
            f"{metrics.get('profit_factor')} | {metrics.get('maximum_drawdown_r')} |"
        )
    lines.extend(
        [
            "",
            "The 2024–2025 holdout was not evaluated. No filter may be promoted or removed from production from this report.",
        ]
    )
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Filter audit complete: {output_dir}")
    print(f"Discovery signals: {len(discovery)}")
    print("Holdout evaluated: False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
