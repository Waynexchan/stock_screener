"""Research-only artifact writer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def ensure_research_output_path(
    project_root: str | Path, output_dir: str | Path
) -> Path:
    root = Path(project_root).resolve()
    allowed = (root / "research" / "output").resolve()
    target = Path(output_dir)
    if not target.is_absolute():
        target = root / target
    target = target.resolve()
    if target != allowed and allowed not in target.parents:
        raise ValueError("research output must remain under research/output")
    return target


def _json_default(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=_json_default),
        encoding="utf-8",
    )


def baseline_report(result: dict[str, Any]) -> str:
    manifest = result["manifest"]
    readiness = result["data_readiness"]
    metrics = result["metrics"]

    def value(name: str) -> str:
        item = metrics.get(name)
        return "Not available" if item is None else str(item)

    readiness_lines = [
        f"- {name}: **{item['status']}** — {item['summary']}"
        for name, item in readiness["items"].items()
    ]
    bias_lines = [
        f"- **{name}:** {summary}" for name, summary in readiness["biases"].items()
    ]
    excluded = "\n".join(f"- {name}" for name in manifest["excluded_alpha_filters"])
    price_history = readiness["items"].get("price_history", {})
    universe_history = readiness["items"].get("universe_history", {})
    snapshots = readiness["items"].get("forward_snapshots", {})
    return "\n".join(
        [
            "# MODEL_0 Baseline Research Report",
            "",
            "> **THIS IS A BASELINE, NOT A PRODUCTION RECOMMENDATION.**",
            "",
            f"> **{manifest['research_label']}**",
            "",
            f"Execution status: **{manifest['execution_status']}**",
            f"Run ID: `{manifest['run_id']}`",
            f"Git commit: `{manifest['git_commit']}` (dirty: `{manifest['git_dirty']}`)",
            f"Data period: `{manifest['data_period']['start']}` to `{manifest['data_period']['end']}`",
            f"Historical OHLCV symbol coverage: `{price_history.get('symbol_count', 0)}`",
            f"Current snapshot symbols (not historical membership): `{universe_history.get('current_snapshot_symbols', 0)}`",
            f"Forward evidence: `{snapshots.get('candidate_rows', 0)}` candidate rows across `{snapshots.get('snapshot_file_count', 0)}` snapshot files",
            "",
            "## Exact MODEL_0 definition",
            "",
            "MODEL_0 uses only validated adjusted OHLCV, the configured minimum price and 50-session average-volume tradability checks, a causal intermediate-uptrend test (`Close > MA50 > MA150 > MA200` and rising MA200), a false-to-true eligibility signal after the close, a structural stop at the trailing 20-session low, and earliest entry at the next available session open. The default baseline has no profit target and exits at the stop or after 40 sessions.",
            "",
            "Excluded alpha filters:",
            "",
            excluded,
            "",
            "## Data readiness",
            "",
            *readiness_lines,
            "",
            "## Metrics",
            "",
            f"- Signal count: {value('signal_count')}",
            f"- Triggered trades: {value('triggered_trade_count')}",
            f"- Win rate: {value('win_rate')}",
            f"- Expectancy R: {value('expectancy_r')}",
            f"- Profit factor: {value('profit_factor')}",
            f"- Maximum drawdown R: {value('maximum_drawdown_r')}",
            f"- Average drawdown R: {value('average_drawdown_r')}",
            f"- Average win R: {value('average_win_r')}",
            f"- Average loss R: {value('average_loss_r')}",
            f"- Average MFE R: {value('average_mfe_r')}",
            f"- Average MAE R: {value('average_mae_r')}",
            f"- Average holding sessions: {value('average_holding_days')}",
            f"- Trade frequency/year: {value('trade_frequency_per_year')}",
            f"- Exposure: {value('exposure')}",
            "",
            "Null metrics are intentional when the data-readiness gate blocks execution. They must not be converted to zero-performance claims.",
            "",
            "## Known biases and limitations",
            "",
            *bias_lines,
            "",
            "No filter is validated by this report. No production threshold or decision was changed.",
        ]
    )


def write_baseline_artifacts(
    result: dict[str, Any], project_root: str | Path, output_dir: str | Path
) -> Path:
    target = ensure_research_output_path(project_root, output_dir)
    target.mkdir(parents=True, exist_ok=True)
    _write_json(target / "manifest.json", result["manifest"])
    _write_json(target / "data_readiness.json", result["data_readiness"])
    _write_json(target / "metrics.json", result["metrics"])
    for name in ("features", "outcomes", "trades", "capacity_rejections"):
        frame: pd.DataFrame = result[name]
        frame.to_csv(target / f"{name}.csv", index=False)
    (target / "report.md").write_text(baseline_report(result), encoding="utf-8")
    return target
