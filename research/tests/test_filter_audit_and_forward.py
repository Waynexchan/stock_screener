from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from research.download_yahoo import long_form, ticker_frame, yahoo_symbol
from research.run_filter_audit import filter_mask
from research.run_forward_test import (
    add_filter_flags,
    earliest_complete_snapshots,
    load_snapshot_signals,
    main as run_forward_test,
)


def test_snapshot_actionability_requires_decision_and_actionable_flag() -> None:
    frame = pd.DataFrame(
        {
            "Final Decision": ["FULL", "HALF", "WATCH", "NO TRADE"],
            "Actionable": [True, False, True, False],
        }
    )
    result = add_filter_flags(frame)
    assert result["snapshot_actionable"].tolist() == [True, False, False, False]


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


def test_forward_journal_without_prices_freezes_signals_with_missing_outcomes(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "snapshots"
    run = _snapshot(root, "2026-01-02", "20260102T220000Z")
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
    journal = pd.read_csv(output / "journal.csv")
    assert journal.empty is False
    assert journal["future_5d_return"].isna().all()
