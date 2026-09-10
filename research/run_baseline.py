"""Command-line entry for the gated MODEL_0 baseline."""

from __future__ import annotations

import argparse
from pathlib import Path

from research.engine.baseline import run_model_0
from research.engine.reporting import write_baseline_artifacts


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--prices", type=Path)
    command.add_argument("--universe-history", type=Path)
    command.add_argument("--benchmark", type=Path)
    command.add_argument(
        "--allow-survivorship-biased",
        action="store_true",
        help="Explicitly allow a labelled, non-validating run when historical membership is unavailable.",
    )
    command.add_argument(
        "--output-dir", type=Path, default=Path("research/output/baseline")
    )
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    config_path = project_root / "research" / "config" / "model_0.json"
    result = run_model_0(
        project_root=project_root,
        config_path=config_path,
        price_path=args.prices,
        universe_history_path=args.universe_history,
        benchmark_path=args.benchmark,
        allow_survivorship_biased=args.allow_survivorship_biased,
    )
    target = write_baseline_artifacts(result, project_root, args.output_dir)
    print("MODEL_0 baseline research")
    print(f"Execution status: {result['manifest']['execution_status']}")
    print(f"Data readiness: {result['data_readiness']['overall_status']}")
    print(f"Research label: {result['manifest']['research_label']}")
    print(f"Signal count: {result['metrics']['signal_count']}")
    print(f"Triggered trades: {result['metrics']['triggered_trade_count']}")
    print(f"Output: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
