"""Build a reproducible research journal from immutable production snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from research.engine.ablation import with_without_summary
from research.engine.data import load_price_csv
from research.engine.market_features import enrich_market_features
from research.engine.models import FeatureRecord, OutcomeRecord
from research.engine.outcomes import calculate_forward_outcomes
from research.engine.reporting import ensure_research_output_path

EXPECTED_SNAPSHOT_FILES = {
    "candidates.csv",
    "market.json",
    "portfolio.json",
    "config.json",
    "metadata.json",
}


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--prices", type=Path)
    command.add_argument("--benchmark", type=Path)
    command.add_argument(
        "--snapshot-root", type=Path, default=Path("output/forward_snapshots")
    )
    command.add_argument(
        "--output-dir", type=Path, default=Path("research/output/forward_test_v1")
    )
    return command


def _truth(value: object) -> bool:
    return value is True or str(value).strip().casefold() == "true"


def earliest_complete_snapshots(root: Path) -> list[Path]:
    selected: list[Path] = []
    if not root.exists():
        return selected
    for date_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        complete: list[Path] = []
        for run_dir in sorted(path for path in date_dir.iterdir() if path.is_dir()):
            if EXPECTED_SNAPSHOT_FILES <= {
                path.name for path in run_dir.iterdir() if path.is_file()
            }:
                metadata = json.loads(
                    (run_dir / "metadata.json").read_text(encoding="utf-8")
                )
                candidates = pd.read_csv(run_dir / "candidates.csv")
                if str(metadata.get("signal_trading_date")) == date_dir.name and int(
                    metadata.get("candidate_count", -1)
                ) == len(candidates):
                    complete.append(run_dir)
        if complete:
            selected.append(complete[0])
    return selected


def load_snapshot_signals(root: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for run_dir in earliest_complete_snapshots(root):
        frame = pd.read_csv(run_dir / "candidates.csv")
        metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
        frame["snapshot_run_id"] = run_dir.name
        frame["snapshot_path"] = str(run_dir.resolve())
        frame["snapshot_generated_at"] = metadata.get("generated_timestamp")
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).drop_duplicates(
        ["Signal Date", "Ticker"], keep="first"
    )


def outcome_for_candidate(
    ticker: str, signal_date: str, history: pd.DataFrame
) -> dict[str, Any]:
    feature = FeatureRecord(
        signal_date=signal_date,
        ticker=ticker,
        universe_version="immutable production snapshot",
        data_as_of=signal_date,
        price=float("nan"),
        volume=float("nan"),
        dollar_volume=float("nan"),
        average_volume_50d=float("nan"),
        valid_data=True,
        tradable=True,
        stage2_pass=True,
        structural_stop=None,
        model_0_signal=True,
    )
    return calculate_forward_outcomes(feature, history).to_dict()


def add_filter_flags(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["pass_recent_rs_70"] = pd.to_numeric(
        result.get("Recent RS Score"), errors="coerce"
    ).ge(70)
    result["pass_long_term_rs_75"] = pd.to_numeric(
        result.get("RS Score"), errors="coerce"
    ).ge(75)
    result["pass_volume_0_30"] = pd.to_numeric(
        result.get("Volume Ratio"), errors="coerce"
    ).ge(0.30)
    result["pass_beta_0_8"] = pd.to_numeric(
        result.get("rolling_beta_126"), errors="coerce"
    ).ge(0.8)
    result["exclude_utility"] = ~result.get(
        "Sector", pd.Series("", index=result.index)
    ).astype(str).str.casefold().eq("utilities")
    result["pass_not_overextended"] = ~result.get(
        "Extension Status", pd.Series("", index=result.index)
    ).astype(str).str.casefold().eq("overextended")
    result["pass_industry_qualified"] = result.get(
        "Industry Qualified", pd.Series(False, index=result.index)
    ).map(_truth)
    result["pass_sister_confirmation"] = result.get(
        "Sister Confirmation", pd.Series(False, index=result.index)
    ).map(_truth)
    result["pass_structural_rr_2"] = pd.to_numeric(
        result.get("Reward/Risk Ratio"), errors="coerce"
    ).ge(2.0)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    output_dir = ensure_research_output_path(project_root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    signals = load_snapshot_signals(args.snapshot_root)
    if signals.empty:
        raise ValueError("no complete immutable forward snapshots found")
    signals = signals.rename(columns={"Signal Date": "signal_date", "Ticker": "ticker"})
    histories: dict[str, pd.DataFrame] = {}
    benchmark: pd.DataFrame | None = None
    if args.prices:
        histories, _ = load_price_csv(args.prices)
    if args.benchmark:
        benchmark_histories, _ = load_price_csv(args.benchmark)
        benchmark = benchmark_histories.get("SPY")
    if histories and benchmark is not None:
        market = enrich_market_features(
            signals[["signal_date", "ticker"]], histories, benchmark
        )
        signals = signals.merge(
            market[["signal_date", "ticker", "rolling_beta_126"]],
            on=["signal_date", "ticker"],
            how="left",
        )
    else:
        signals["rolling_beta_126"] = pd.NA
    signals = add_filter_flags(signals)
    outcomes: list[dict[str, Any]] = []
    for row in signals[["ticker", "signal_date"]].itertuples(index=False):
        history = histories.get(row.ticker)
        if history is not None:
            outcomes.append(outcome_for_candidate(row.ticker, row.signal_date, history))
    outcome_frame = pd.DataFrame(outcomes).reindex(
        columns=list(OutcomeRecord.__dataclass_fields__)
    )
    journal = signals.merge(outcome_frame, on=["signal_date", "ticker"], how="left")
    horizon_columns = [f"future_{days}d_return" for days in (5, 10, 20, 40)]
    journal["maximum_mature_horizon"] = journal.apply(
        lambda row: max(
            [
                days
                for days in (5, 10, 20, 40)
                if pd.notna(row.get(f"future_{days}d_return"))
            ],
            default=0,
        ),
        axis=1,
    )
    summaries: dict[str, Any] = {}
    flag_columns = [
        column for column in journal if column.startswith(("pass_", "exclude_"))
    ]
    for flag in flag_columns:
        summaries[flag] = {}
        for outcome in horizon_columns:
            summaries[flag][outcome] = with_without_summary(
                journal,
                feature_column=flag,
                outcome_column=outcome,
                included=lambda values: values.fillna(False).astype(bool),
            )
    journal.to_csv(output_dir / "journal.csv", index=False)
    (output_dir / "filter_outcomes.json").write_text(
        json.dumps(summaries, indent=2, sort_keys=True), encoding="utf-8"
    )
    metadata = {
        "experiment_id": "FORWARD_FILTER_AUDIT_V1",
        "research_label": "POINT-IN-TIME SNAPSHOT FORWARD RESEARCH",
        "snapshot_dates": sorted(journal["signal_date"].astype(str).unique()),
        "candidate_count": len(journal),
        "mature_5d_count": int(journal["future_5d_return"].notna().sum()),
        "maximum_mature_horizon": int(journal["maximum_mature_horizon"].max()),
        "prices_supplied": bool(args.prices),
        "plan_trigger_r_outcomes": "NOT_YET_IMPLEMENTED",
        "production_effect": "NONE",
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"Forward journal: {output_dir / 'journal.csv'}")
    print(f"Candidates frozen: {len(journal)}")
    print(f"Mature 5-session outcomes: {metadata['mature_5d_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
