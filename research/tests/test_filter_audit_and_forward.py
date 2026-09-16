from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from research.download_yahoo import long_form, ticker_frame, yahoo_symbol
from research.run_filter_audit import filter_mask
from research.run_forward_test import (
    _snapshot_audit,
    add_filter_flags,
    earliest_complete_snapshots,
    load_experiment,
    load_snapshot_signals,
    main as run_forward_test,
)
from research.engine.forward_portfolio import (
    build_independent_episodes,
    evaluate_portfolio_variants,
)
from research.engine.reproducibility import sha256_file


def test_snapshot_actionability_requires_decision_and_actionable_flag() -> None:
    frame = pd.DataFrame(
        {
            "Final Decision": ["FULL", "HALF", "WATCH", "NO TRADE"],
            "Actionable": [True, False, True, False],
        }
    )
    result = add_filter_flags(frame)
    assert result["snapshot_actionable"].tolist() == [True, False, False, False]


def test_formal_forward_epoch_template_is_fail_closed() -> None:
    template = Path(__file__).parents[1] / "config" / "forward_epoch_template.json"
    with pytest.raises(ValueError, match="preregistered and active"):
        load_experiment(template)


def test_unknown_sector_fails_closed_for_utilities_exclusion() -> None:
    frame = pd.DataFrame({"Sector": ["Technology", "Utilities", "Unknown", ""]})
    result = add_filter_flags(frame)
    assert result["sector_known"].tolist() == [True, True, False, False]
    assert result["exclude_utility"].tolist() == [True, False, False, False]


def test_yahoo_download_conversion_preserves_original_ticker() -> None:
    dates = pd.to_datetime(["2026-01-02", "2026-01-05"])
    columns = pd.MultiIndex.from_product(
        [["BRK-B"], ["Open", "High", "Low", "Close", "Volume"]]
    )
    raw = pd.DataFrame(
        [[100, 101, 99, 100, 1_000], [101, 102, 100, 101, 1_100]],
        index=dates,
        columns=columns,
    )
    converted = long_form(ticker_frame(raw, "BRK-B"), "BRK.B")
    assert yahoo_symbol("brk.b") == "BRK-B"
    assert converted["Ticker"].unique().tolist() == ["BRK.B"]
    assert converted["Date"].astype(str).tolist() == ["2026-01-02", "2026-01-05"]


def test_preregistered_filter_masks_fail_closed_on_missing_values() -> None:
    frame = pd.DataFrame({"beta": [0.7, 0.8, None]})
    mask = filter_mask(frame, {"column": "beta", "operator": ">=", "value": 0.8})
    assert mask.tolist() == [False, True, False]


def _snapshot(root: Path, date: str, run_id: str, *, complete: bool = True) -> Path:
    run = root / date / run_id
    run.mkdir(parents=True)
    candidates = pd.DataFrame(
        [{"Signal Date": date, "Ticker": "AAA", "Final Decision": "WATCH"}]
    )
    candidates.to_csv(run / "candidates.csv", index=False)
    metadata = {
        "signal_trading_date": date,
        "candidate_count": len(candidates),
        "generated_timestamp": f"{date}T22:00:00+00:00",
    }
    (run / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    if complete:
        for name in ("market.json", "portfolio.json", "config.json"):
            (run / name).write_text("{}", encoding="utf-8")
    return run


def test_forward_journal_uses_earliest_complete_snapshot_per_date(
    tmp_path: Path,
) -> None:
    root = tmp_path / "snapshots"
    _snapshot(root, "2026-01-02", "20260102T210000Z", complete=False)
    expected = _snapshot(root, "2026-01-02", "20260102T220000Z")
    _snapshot(root, "2026-01-02", "20260102T230000Z")
    assert earliest_complete_snapshots(root) == [expected]
    signals = load_snapshot_signals(root)
    assert len(signals) == 1
    assert signals.iloc[0]["snapshot_run_id"] == expected.name


def test_snapshot_artifact_hash_is_verified_and_corruption_fails(
    tmp_path: Path,
) -> None:
    run = _snapshot(tmp_path, "2026-01-02", "run")
    metadata_path = run / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["snapshot_schema_version"] = 2
    metadata["artifact_hashes"] = {
        name: sha256_file(run / name)
        for name in ("candidates.csv", "market.json", "portfolio.json", "config.json")
    }
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    experiment = {"collection_mode": "PILOT", "frozen_epoch": {}}
    assert _snapshot_audit(run, experiment)["candidate_file_hash_status"] == "VERIFIED"
    (run / "candidates.csv").write_text("Ticker\nCORRUPTED\n", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        _snapshot_audit(run, experiment)


def test_forward_episodes_exclude_overlapping_same_ticker() -> None:
    journal = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "signal_date": "2026-01-02",
                "plan_triggered": True,
                "plan_entry_date": "2026-01-05",
                "plan_exit_date": "2026-01-12",
            },
            {
                "ticker": "AAA",
                "signal_date": "2026-01-06",
                "plan_triggered": True,
                "plan_entry_date": "2026-01-07",
                "plan_exit_date": "2026-01-20",
            },
            {
                "ticker": "AAA",
                "signal_date": "2026-01-13",
                "plan_triggered": True,
                "plan_entry_date": "2026-01-13",
                "plan_exit_date": "2026-01-20",
            },
        ]
    )
    annotated, episodes = build_independent_episodes(
        journal, pd.Timestamp("2026-01-31")
    )
    assert episodes["signal_date"].tolist() == ["2026-01-02", "2026-01-13"]
    assert annotated["episode_exclusion_reason"].eq("SAME_TICKER_OVERLAP").sum() == 1


def test_forward_portfolio_applies_order_heat_and_unknown_industry_fail_closed() -> (
    None
):
    episodes = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "signal_date": "2026-01-02",
                "plan_entry_date": "2026-01-05",
                "plan_exit_date": "2026-01-07",
                "plan_entry": 10.0,
                "Initial Stop": 9.0,
                "plan_realised_r": 0.5,
                "Industry": "Unknown",
                "Final Score": 100.0,
                "snapshot_row_order": 0,
            },
            {
                "ticker": "BBB",
                "signal_date": "2026-01-02",
                "plan_entry_date": "2026-01-05",
                "plan_exit_date": "2026-01-07",
                "plan_entry": 10.0,
                "Initial Stop": 9.0,
                "plan_realised_r": 0.5,
                "Industry": "Software",
                "Final Score": 90.0,
                "snapshot_row_order": 1,
            },
            {
                "ticker": "CCC",
                "signal_date": "2026-01-02",
                "plan_entry_date": "2026-01-05",
                "plan_exit_date": "2026-01-07",
                "plan_entry": 10.0,
                "Initial Stop": 9.0,
                "plan_realised_r": -0.5,
                "Industry": "Hardware",
                "Final Score": 80.0,
                "snapshot_row_order": 2,
            },
        ]
    )
    sessions = pd.date_range("2026-01-05", "2026-01-07", freq="B")
    history = pd.DataFrame(
        {"Open": [10.0, 10.0, 10.0], "Close": [10.0, 10.0, 10.0]},
        index=sessions,
    )
    variant = {
        "variant_id": "TEST",
        "role": "CHALLENGER",
        "eligibility": {"all": []},
        "risk": {"fixed_r": 1.0},
        "portfolio": {
            "maximum_positions": 2,
            "maximum_heat_r": 2.0,
            "maximum_positions_per_industry": 2,
        },
        "ordering": [{"column": "Final Score", "direction": "DESC"}],
    }
    metrics, ledger, _, _ = evaluate_portfolio_variants(
        episodes,
        {ticker: history for ticker in ("AAA", "BBB", "CCC")},
        sessions,
        [variant],
        observation_end=sessions[-1],
        bootstrap_seed=7,
        bootstrap_resamples=50,
    )
    reasons = ledger.set_index("ticker")["portfolio_rejection_reason"].to_dict()
    assert reasons == {"AAA": "UNKNOWN_INDUSTRY", "BBB": None, "CCC": None}
    assert metrics.iloc[0]["accepted_episode_count"] == 2
    assert metrics.iloc[0]["maximum_positions"] == 2


def test_forward_journal_without_prices_freezes_signals_with_missing_outcomes(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "snapshots"
    run = _snapshot(root, "2026-09-16", "20260916T220000Z")
    candidates = pd.read_csv(run / "candidates.csv")
    candidates["Recent RS Score"] = 80
    candidates["RS Score"] = 90
    candidates["Volume Ratio"] = 1.0
    candidates["Sector"] = "Technology"
    candidates["Extension Status"] = "Not Extended"
    candidates["Industry Qualified"] = True
    candidates["Sister Confirmation"] = True
    candidates["Reward/Risk Ratio"] = 2.0
    candidates.to_csv(run / "candidates.csv", index=False)
    metadata = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
    metadata["candidate_count"] = len(candidates)
    (run / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    output = tmp_path / "research_output"
    monkeypatch.setattr(
        "research.run_forward_test.ensure_research_output_path",
        lambda project_root, output_dir: output,
    )
    result = run_forward_test(
        [
            "--snapshot-root",
            str(root),
            "--output-dir",
            str(output),
        ]
    )
    assert result == 0
    runs = list((output / "runs").iterdir())
    assert len(runs) == 1
    journal = pd.read_csv(runs[0] / "raw_snapshot_journal.csv")
    assert journal.empty is False
    assert journal["future_5d_return"].isna().all()
    metadata = json.loads((runs[0] / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["evidence_status"] == "ENGINEERING_PILOT_NOT_FORMAL"
    assert metadata["minimum_review_sample_unit"] == "MATURE_INDEPENDENT_EPISODES"
    assert (output / "run_manifest.jsonl").is_file()
