from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from research.engine.ablation import (
    RECENT_RS_BUCKET_EDGES,
    threshold_buckets,
    with_without_summary,
)
from research.engine.metrics import (
    bootstrap_mean_interval,
    calculate_metrics,
    drawdown_statistics,
)
from research.engine.models import SimulatedTrade
from research.engine.reporting import (
    ensure_research_output_path,
    write_baseline_artifacts,
)
from research.engine.reproducibility import build_manifest, stable_payload_hash
from research.engine.baseline import run_model_0


def trade(
    realised_r: float,
    *,
    ticker: str = "AAA",
    entry_date: str = "2026-01-05",
    exit_date: str = "2026-01-06",
) -> SimulatedTrade:
    return SimulatedTrade(
        signal_date="2026-01-02",
        ticker=ticker,
        entry_date=entry_date,
        exit_date=exit_date,
        entry=100.0,
        initial_stop=95.0,
        target=None,
        initial_risk_per_share=5.0,
        shares=100,
        exit=100 + realised_r * 5,
        gross_pnl=realised_r * 500,
        costs=0.0,
        net_pnl=realised_r * 500,
        realised_r=realised_r,
        MFE_R=max(0.0, realised_r + 0.5),
        MAE_R=min(0.0, realised_r - 0.5),
        holding_days=2,
        exit_reason="FIXTURE",
    )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_maximum_and_average_drawdown() -> None:
    maximum, average = drawdown_statistics(pd.Series([1.0, -2.0, 0.5]))
    assert maximum == pytest.approx(2.0)
    assert average == pytest.approx((0.0 + 2.0 + 1.5) / 3)


def test_core_metrics() -> None:
    metrics = calculate_metrics(
        [
            trade(1.0),
            trade(-1.0, ticker="BBB", entry_date="2026-01-07", exit_date="2026-01-08"),
        ],
        signal_count=3,
        maximum_positions=4,
        seed=7,
    )
    assert metrics["signal_count"] == 3
    assert metrics["triggered_trade_count"] == 2
    assert metrics["win_rate"] == 0.5
    assert metrics["expectancy_r"] == 0.0
    assert metrics["profit_factor"] == 1.0
    assert metrics["maximum_drawdown_r"] == 1.0


def test_deterministic_repeatability() -> None:
    values = pd.Series([1.0, -1.0, 0.5, 2.0])
    first = bootstrap_mean_interval(values, seed=123, samples=200)
    second = bootstrap_mean_interval(values, seed=123, samples=200)
    assert first == second
    assert stable_payload_hash({"b": 2, "a": 1}) == stable_payload_hash(
        {"a": 1, "b": 2}
    )


def test_recent_rs_bucket_shape_is_prepared_without_search() -> None:
    frame = pd.DataFrame({"Recent RS": [10, 55, 65, 75, 85, 95]})
    labels = threshold_buckets(frame, "Recent RS", RECENT_RS_BUCKET_EDGES)
    assert labels.astype(str).tolist() == [
        "0-50",
        "50-60",
        "60-70",
        "70-80",
        "80-90",
        "90-100",
    ]


def test_with_without_ablation_is_fixed() -> None:
    frame = pd.DataFrame({"feature": [0, 1, 2], "outcome": [-1.0, 1.0, 2.0]})
    result = with_without_summary(
        frame,
        feature_column="feature",
        outcome_column="outcome",
        included=lambda values: values >= 1,
    )
    assert result["WITH_FEATURE"]["sample_size"] == 2
    assert result["WITHOUT_FEATURE"]["mean_outcome"] == -1.0


def test_research_output_cannot_escape_isolated_directory(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "research" / "output").mkdir(parents=True)
    assert ensure_research_output_path(
        project, "research/output/baseline"
    ).is_relative_to(project / "research" / "output")
    with pytest.raises(ValueError, match="research/output"):
        ensure_research_output_path(project, project / "daily_watchlist.csv")


def test_research_artifact_write_does_not_modify_production_outputs(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    output = project / "research" / "output" / "baseline"
    output.mkdir(parents=True)
    production = project / "daily_watchlist.csv"
    production.write_text("ticker,decision\nAAA,FULL\n", encoding="utf-8")
    before = digest(production)
    result = {
        "manifest": {
            "research_label": "SURVIVORSHIP-BIASED RESEARCH",
            "execution_status": "BLOCKED_DATA_NOT_READY",
            "run_id": "fixture",
            "git_commit": "fixture",
            "git_dirty": True,
            "data_period": {"start": None, "end": None},
            "excluded_alpha_filters": [],
        },
        "data_readiness": {
            "items": {},
            "biases": {},
        },
        "metrics": {
            "signal_count": 0,
            "triggered_trade_count": 0,
        },
        "features": pd.DataFrame(),
        "outcomes": pd.DataFrame(),
        "trades": pd.DataFrame(),
        "capacity_rejections": pd.DataFrame(),
    }
    write_baseline_artifacts(result, project, output)
    assert digest(production) == before


def test_manifest_records_reproducibility_fields(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")
    manifest = build_manifest(
        project_root=tmp_path,
        config_path=config,
        experiment_id="MODEL_0_BASELINE",
        data_period={"start": None, "end": None},
        universe_definition="fixture",
        execution_assumptions={"target_r": None},
        feature_configuration={"recent_rs": "excluded"},
        known_limitations=["fixture"],
        random_seed=42,
        generated_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
    )
    assert manifest["run_id"] == "20260910T000000000000Z"
    assert manifest["config_hash"]
    assert manifest["random_seed"] == 42


def test_blocked_baseline_keeps_machine_readable_csv_schemas(tmp_path: Path) -> None:
    config = Path(__file__).parents[1] / "config" / "model_0.json"
    result = run_model_0(project_root=tmp_path, config_path=config)
    output = write_baseline_artifacts(
        result, tmp_path, tmp_path / "research" / "output" / "baseline"
    )
    assert pd.read_csv(output / "outcomes.csv").columns.tolist()[0:3] == [
        "signal_date",
        "ticker",
        "entry_date",
    ]
    expected_trade_columns = {"entry", "initial_stop", "realised_r", "MFE_R", "MAE_R"}
    assert expected_trade_columns <= set(pd.read_csv(output / "trades.csv").columns)
