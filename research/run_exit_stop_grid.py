"""Run the preregistered MODEL_0 target/initial-stop discovery grid."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research.engine.baseline import execution_assumptions, load_model_0_config
from research.engine.data import load_price_csv
from research.engine.execution import prepare_trade_execution, simulate_prepared_trade
from research.engine.features import generate_model_0_features
from research.engine.metrics import calculate_metrics
from research.engine.models import ExecutionAssumptions, FeatureRecord, SimulatedTrade
from research.engine.portfolio import apply_position_capacity
from research.engine.reporting import ensure_research_output_path


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--prices", type=Path, required=True)
    command.add_argument(
        "--output-dir", type=Path, default=Path("research/output/exit_stop_grid_v1")
    )
    return command


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def true_range_atr20(history: pd.DataFrame) -> pd.Series:
    """Match production's causal 20-session simple-mean True Range ATR."""

    high = pd.to_numeric(history["High"], errors="coerce")
    low = pd.to_numeric(history["Low"], errors="coerce")
    previous_close = pd.to_numeric(history["Close"], errors="coerce").shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(20, min_periods=20).mean()


def add_risk_inputs(
    signals: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    *,
    entry_slippage_bps: float,
) -> pd.DataFrame:
    """Attach signal-time ATR/low and next-session executable entry inputs."""

    result = signals.copy()
    result["atr20"] = np.nan
    result["signal_day_low"] = np.nan
    result["slipped_next_open"] = np.nan
    for ticker, indexes in result.groupby("ticker", sort=False).groups.items():
        history = histories.get(str(ticker))
        if history is None or history.empty:
            continue
        frame = history.sort_index()
        frame.index = pd.to_datetime(frame.index)
        atr = true_range_atr20(frame)
        signal_dates = pd.to_datetime(result.loc[indexes, "signal_date"])
        for row_index, signal_date in zip(indexes, signal_dates, strict=True):
            if signal_date not in frame.index:
                continue
            atr_value = pd.to_numeric(atr.loc[signal_date], errors="coerce")
            low_value = pd.to_numeric(frame.loc[signal_date, "Low"], errors="coerce")
            next_position = frame.index.searchsorted(signal_date, side="right")
            if next_position >= len(frame):
                continue
            next_open = pd.to_numeric(
                frame.iloc[next_position]["Open"], errors="coerce"
            )
            if not all(
                np.isfinite(value) and float(value) > 0
                for value in (atr_value, low_value, next_open)
            ):
                continue
            result.at[row_index, "atr20"] = float(atr_value)
            result.at[row_index, "signal_day_low"] = float(low_value)
            result.at[row_index, "slipped_next_open"] = float(next_open) * (
                1 + entry_slippage_bps / 10_000
            )
    return result


def stop_for_variant(row: dict[str, Any], specification: dict[str, Any]) -> float:
    anchor = specification["anchor"]
    multiple = float(specification["atr_multiple"])
    if anchor == "signal_20d_low":
        value = row.get("structural_stop")
    elif anchor == "slipped_entry":
        value = float(row["slipped_next_open"]) - multiple * float(row["atr20"])
    elif anchor == "signal_day_low":
        value = float(row["signal_day_low"]) - multiple * float(row["atr20"])
    else:
        raise ValueError(f"unsupported stop anchor: {anchor}")
    parsed = pd.to_numeric(value, errors="coerce")
    return float(parsed) if np.isfinite(parsed) else float("nan")


def metrics_for_variant(
    trades: list[SimulatedTrade],
    *,
    signal_count: int,
    assumptions: ExecutionAssumptions,
    seed: int,
) -> dict[str, Any]:
    accepted, rejected = apply_position_capacity(trades, assumptions.maximum_positions)
    metrics = calculate_metrics(
        accepted,
        signal_count=signal_count,
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
    metrics["independent_trade_count"] = len(trades)
    metrics["capacity_rejection_count"] = len(rejected)
    return metrics


def _feature(row: dict[str, Any]) -> FeatureRecord:
    fields = FeatureRecord.__dataclass_fields__
    return FeatureRecord(**{name: row.get(name) for name in fields})


def _delta(value: object, baseline: object) -> float | None:
    if value is None or baseline is None:
        return None
    return round(float(value) - float(baseline), 6)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    output_dir = ensure_research_output_path(project_root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    experiment_path = (
        project_root / "research" / "experiments" / "exit_stop_grid_v1.json"
    )
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    model_config = load_model_0_config(
        project_root / "research" / "config" / "model_0.json"
    )
    histories, diagnostics = load_price_csv(args.prices)
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
    start, end = experiment["discovery_period"]
    signal_dates = pd.to_datetime(signals["signal_date"])
    discovery = signals[signal_dates.between(start, end)].copy()
    base_assumptions = execution_assumptions(model_config)
    discovery = add_risk_inputs(
        discovery,
        histories,
        entry_slippage_bps=base_assumptions.entry_slippage_bps,
    )
    prepared = []
    for row in discovery.to_dict("records"):
        feature = _feature(row)
        history = histories.get(feature.ticker)
        if history is None:
            continue
        execution = prepare_trade_execution(feature, history, base_assumptions)
        if execution is not None:
            prepared.append((execution, row))
    seed = int(model_config["random_seed"])
    variant_results: list[dict[str, Any]] = []
    for stop_specification in experiment["stop_variants"]:
        for target_r in experiment["target_r_variants"]:
            assumptions = replace(base_assumptions, target_r=target_r)
            trades: list[SimulatedTrade] = []
            for execution, row in prepared:
                stop = stop_for_variant(row, stop_specification)
                trade = simulate_prepared_trade(
                    execution,
                    assumptions,
                    stop_price=stop,
                )
                if trade is not None:
                    trades.append(trade)
            metrics = metrics_for_variant(
                trades,
                signal_count=len(discovery),
                assumptions=assumptions,
                seed=seed,
            )
            target_label = "none" if target_r is None else f"{target_r:g}r"
            variant_results.append(
                {
                    "variant_id": f"{stop_specification['id']}__target_{target_label}",
                    "stop_id": stop_specification["id"],
                    "target_r": target_r,
                    **metrics,
                }
            )
    baseline = next(
        item
        for item in variant_results
        if item["stop_id"] == "structural_20d_low" and item["target_r"] is None
    )
    for item in variant_results:
        item["expectancy_delta_r"] = _delta(
            item.get("expectancy_r"), baseline.get("expectancy_r")
        )
        item["profit_factor_delta"] = _delta(
            item.get("profit_factor"), baseline.get("profit_factor")
        )
        item["maximum_drawdown_delta_r"] = _delta(
            item.get("maximum_drawdown_r"), baseline.get("maximum_drawdown_r")
        )
        item["meets_numeric_shortlist_gate"] = bool(
            item["expectancy_delta_r"] is not None
            and item["expectancy_delta_r"] >= 0.10
            and item["profit_factor_delta"] is not None
            and item["profit_factor_delta"] >= 0
            and item["maximum_drawdown_delta_r"] is not None
            and item["maximum_drawdown_delta_r"] <= 0
        )
    result_frame = pd.DataFrame(variant_results)
    result_frame.to_csv(output_dir / "grid_results.csv", index=False)
    payload = {
        "experiment": experiment,
        "execution_status": "COMPLETED_SURVIVORSHIP_BIASED_ENGINEERING_DISCOVERY",
        "research_label": "SURVIVORSHIP-BIASED RESEARCH",
        "historical_decision": "HOLD",
        "holdout_evaluated": False,
        "multiple_comparison_warning": "Twenty combinations reused one biased discovery sample; a high-ranked cell is not validation.",
        "price_source": str(args.prices.resolve()),
        "price_sha256": sha256_file(args.prices),
        "price_diagnostics": diagnostics,
        "discovery_signal_count": len(discovery),
        "baseline": baseline,
        "variants": variant_results,
    }
    (output_dir / "results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    lines = [
        "# EXIT_STOP_GRID_V1 engineering discovery",
        "",
        "> **SURVIVORSHIP-BIASED RESEARCH — NOT PRODUCTION EVIDENCE**",
        "",
        f"Discovery signals: {len(discovery)}",
        "Historical decision: **HOLD**",
        "",
        "| Stop | Target | Trades | Win rate | Expectancy R | Delta R | Profit factor | Payoff | Max DD R | Avg hold |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in variant_results:
        lines.append(
            f"| {item['stop_id']} | {item['target_r']} | "
            f"{item['triggered_trade_count']} | {item['win_rate']} | "
            f"{item['expectancy_r']} | {item['expectancy_delta_r']} | "
            f"{item['profit_factor']} | {item['payoff_ratio']} | "
            f"{item['maximum_drawdown_r']} | {item['average_holding_days']} |"
        )
    lines.extend(
        [
            "",
            "All 20 combinations are reported. The 2024-2025 holdout was not evaluated, and no result changes production.",
            "",
            "Sizing normalizes each accepted trade to USD 587 initial risk but does not model portfolio cash or a maximum notional exposure; tight ATR stops may imply unrealistic share counts.",
        ]
    )
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Exit/stop grid complete: {output_dir}")
    print(f"Discovery signals: {len(discovery)}")
    print("Variants reported: 20")
    print("Holdout evaluated: False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
