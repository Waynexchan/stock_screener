"""MODEL_0 baseline orchestration, deliberately excluding alpha filters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .data import audit_repository_data, load_price_csv
from .execution import simulate_trade
from .features import (
    MODEL_0_EXCLUDED_ALPHA_FEATURES,
    MODEL_0_ID,
    generate_model_0_features,
)
from .metrics import calculate_metrics
from .models import ExecutionAssumptions, FeatureRecord, OutcomeRecord, SimulatedTrade
from .outcomes import build_outcome_frame
from .portfolio import apply_position_capacity
from .reproducibility import build_manifest


def load_model_0_config(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def execution_assumptions(config: dict[str, Any]) -> ExecutionAssumptions:
    return ExecutionAssumptions(**config["execution_assumptions"])


def _feature_from_row(row: dict[str, Any]) -> FeatureRecord:
    values = {name: row.get(name) for name in FeatureRecord.__dataclass_fields__}
    if pd.isna(values["structural_stop"]):
        values["structural_stop"] = None
    return FeatureRecord(**values)


def run_model_0(
    *,
    project_root: str | Path,
    config_path: str | Path,
    price_path: str | Path | None = None,
    universe_history_path: str | Path | None = None,
    benchmark_path: str | Path | None = None,
    allow_survivorship_biased: bool = False,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    config = load_model_0_config(config_path)
    audit = audit_repository_data(
        root, price_path, universe_history_path, benchmark_path
    )
    assumptions = execution_assumptions(config)
    features = pd.DataFrame(columns=list(FeatureRecord.__dataclass_fields__))
    outcomes = pd.DataFrame(columns=list(OutcomeRecord.__dataclass_fields__))
    trades: list[SimulatedTrade] = []
    rejected_capacity: list[SimulatedTrade] = []
    execution_status = "BLOCKED_DATA_NOT_READY"
    may_run_biased = price_path is not None and allow_survivorship_biased
    fully_ready = audit["overall_status"] == "READY"
    if fully_ready or may_run_biased:
        histories, _ = load_price_csv(price_path)
        feature_config = config["feature_configuration"]
        features = generate_model_0_features(
            histories,
            universe_version=config["universe_definition"],
            min_price=float(feature_config["min_price"]),
            min_average_volume=float(feature_config["min_average_volume_50d"]),
            minimum_history_sessions=int(feature_config["minimum_history_sessions"]),
            stop_lookback_sessions=int(
                feature_config["structural_stop_lookback_sessions"]
            ),
        )
        outcomes = build_outcome_frame(features, histories)
        independent: list[SimulatedTrade] = []
        for row in features[features["model_0_signal"]].to_dict("records"):
            feature = _feature_from_row(row)
            trade = simulate_trade(feature, histories[feature.ticker], assumptions)
            if trade is not None:
                independent.append(trade)
        trades, rejected_capacity = apply_position_capacity(
            independent, assumptions.maximum_positions
        )
        execution_status = (
            "COMPLETED_POINT_IN_TIME"
            if fully_ready
            else "COMPLETED_SURVIVORSHIP_BIASED_RESEARCH"
        )
    signal_count = int(features.get("model_0_signal", pd.Series(dtype=bool)).sum())
    metrics = calculate_metrics(
        trades,
        signal_count=signal_count,
        maximum_positions=assumptions.maximum_positions,
        seed=int(config["random_seed"]),
    )
    if execution_status == "BLOCKED_DATA_NOT_READY":
        metrics = {
            key: (0 if key in {"signal_count", "triggered_trade_count"} else None)
            for key in metrics
        }
    price_item = audit["items"]["price_history"]
    limitations = [value for value in audit["biases"].values()]
    manifest = build_manifest(
        project_root=root,
        config_path=config_path,
        experiment_id=MODEL_0_ID,
        data_period={
            "start": price_item.get("earliest_reliable_date"),
            "end": price_item.get("latest_reliable_date"),
        },
        universe_definition=config["universe_definition"],
        execution_assumptions=assumptions.to_dict(),
        feature_configuration=config["feature_configuration"],
        known_limitations=limitations,
        random_seed=int(config["random_seed"]),
    )
    manifest["research_label"] = audit["research_label"]
    manifest["execution_status"] = execution_status
    manifest["excluded_alpha_filters"] = list(MODEL_0_EXCLUDED_ALPHA_FEATURES)
    return {
        "manifest": manifest,
        "data_readiness": audit,
        "metrics": metrics,
        "features": features,
        "outcomes": outcomes,
        "trades": pd.DataFrame(
            [item.to_dict() for item in trades],
            columns=list(SimulatedTrade.__dataclass_fields__),
        ),
        "capacity_rejections": pd.DataFrame(
            [item.to_dict() for item in rejected_capacity],
            columns=list(SimulatedTrade.__dataclass_fields__),
        ),
    }
