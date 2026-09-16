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
    apply_manual_earnings_journal,
    audit_outcome_inputs,
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
from research.engine.reproducibility import stable_payload_hash


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


def _formal_snapshot(root: Path) -> tuple[Path, dict[str, object]]:
    date = "2026-01-02"
    run = _snapshot(root, date, "formal")
    candidates = pd.DataFrame(
        [
            {
                "Signal Date": date,
                "Ticker": "AAA",
                "Final Decision": "FULL",
                "Actionable": True,
                "Planned Entry": 100.0,
                "Initial Stop": 95.0,
                "Realistic Target": 110.0,
                "Realistic Target Source": "prior high resistance",
                "Maximum Risk R": 1.0,
                "Final Score": 90.0,
                "Industry": "Software",
                "Sector": "Technology",
                "Recent RS Score": 80,
            }
        ]
    )
    candidates.to_csv(run / "candidates.csv", index=False)
    ranking = [
        {"column": "Final Score", "direction": "DESC"},
        {"column": "snapshot_row_order", "direction": "ASC"},
    ]
    policy = {"earnings": "NOT_ENFORCED", "market_cap": "NOT_ENFORCED"}
    metadata = {
        "snapshot_schema_version": 2,
        "signal_trading_date": date,
        "candidate_count": 1,
        "generated_timestamp": f"{date}T22:00:00+00:00",
        "git_commit": "frozen-commit",
        "git_dirty": False,
        "config_hash": "config-hash",
        "universe_hash": "universe-hash",
        "universe_methodology_version": "UNIVERSE_V1",
        "data_provider": {"name": "fixture", "version": "1"},
        "policy": policy,
        "candidate_ranking": ranking,
    }
    cohort_payload = {
        "git_commit": metadata["git_commit"],
        "config_hash": metadata["config_hash"],
        "universe_hash": metadata["universe_hash"],
        "universe_methodology_version": metadata["universe_methodology_version"],
        "data_provider": metadata["data_provider"],
        "policy": policy,
        "ranking": ranking,
    }
    metadata["strategy_cohort_id"] = stable_payload_hash(cohort_payload)
    metadata["artifact_hashes"] = {
        name: sha256_file(run / name)
        for name in ("candidates.csv", "market.json", "portfolio.json", "config.json")
    }
    metadata["candidate_record_hash"] = metadata["artifact_hashes"]["candidates.csv"]
    (run / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    experiment: dict[str, object] = {
        "collection_mode": "FORMAL",
        "frozen_epoch": {
            "git_commit": "frozen-commit",
            "config_hash": "config-hash",
            "universe_hash": "universe-hash",
            "universe_methodology_version": "UNIVERSE_V1",
            "data_provider_name": "fixture",
            "data_provider_version": "1",
            "strategy_cohort_id": metadata["strategy_cohort_id"],
        },
        "trading_policy": {
            "earnings_snapshot_policy": "NOT_ENFORCED",
            "market_cap_snapshot_policy": "NOT_ENFORCED",
        },
        "ranking_and_tie_break": ranking,
    }
    return run, experiment


@pytest.mark.parametrize(
    "missing_name", ["config.json", "market.json", "portfolio.json"]
)
def test_formal_snapshot_requires_every_payload_hash(
    tmp_path: Path, missing_name: str
) -> None:
    run, experiment = _formal_snapshot(tmp_path)
    metadata_path = run / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["artifact_hashes"].pop(missing_name)
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="missing_artifact_hash"):
        _snapshot_audit(run, experiment)


def test_formal_snapshot_rejects_corrupt_config_and_wrong_cohort(
    tmp_path: Path,
) -> None:
    run, experiment = _formal_snapshot(tmp_path)
    (run / "config.json").write_text('{"changed": true}', encoding="utf-8")
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        _snapshot_audit(run, experiment)
    run, experiment = _formal_snapshot(tmp_path / "second")
    metadata_path = run / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["strategy_cohort_id"] = "wrong"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="strategy_cohort_id"):
        _snapshot_audit(run, experiment)


def test_formal_snapshot_rejects_ranking_drift(tmp_path: Path) -> None:
    run, experiment = _formal_snapshot(tmp_path)
    metadata_path = run / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["candidate_ranking"] = [{"column": "Ticker", "direction": "ASC"}]
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="candidate_ranking"):
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


def test_boolean_variant_eligibility_parses_false_string_as_false() -> None:
    episodes = pd.DataFrame(
        [
            {
                "ticker": ticker,
                "signal_date": "2026-01-02",
                "plan_entry_date": "2026-01-05",
                "plan_exit_date": "2026-01-06",
                "plan_entry": 10.0,
                "Initial Stop": 9.0,
                "plan_realised_r": 0.5,
                "eligible": value,
            }
            for ticker, value in (("AAA", "False"), ("BBB", "True"), ("CCC", None))
        ]
    )
    sessions = pd.date_range("2026-01-05", "2026-01-06", freq="B")
    history = pd.DataFrame(
        {"Open": [10.0, 10.0], "Close": [10.0, 10.0]}, index=sessions
    )
    variant = {
        "variant_id": "BOOLEAN",
        "role": "CHALLENGER",
        "eligibility": {"all": [{"column": "eligible", "equals": True}]},
        "risk": {"fixed_r": 1.0},
        "portfolio": {"maximum_positions": 3, "maximum_heat_r": 3.0},
    }
    metrics, ledger, _, _ = evaluate_portfolio_variants(
        episodes,
        {ticker: history for ticker in ("AAA", "BBB", "CCC")},
        sessions,
        [variant],
        observation_end=sessions[-1],
        bootstrap_seed=7,
        bootstrap_resamples=10,
    )
    assert ledger["ticker"].tolist() == ["BBB"]
    assert metrics.iloc[0]["selected_episode_count"] == 1


def test_portfolio_ordering_column_and_direction_fail_closed() -> None:
    episodes = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "signal_date": "2026-01-02",
                "plan_entry_date": "2026-01-05",
                "plan_exit_date": "2026-01-06",
                "plan_entry": 10.0,
                "Initial Stop": 9.0,
                "plan_realised_r": 0.5,
            }
        ]
    )
    sessions = pd.date_range("2026-01-05", "2026-01-06", freq="B")
    history = pd.DataFrame(
        {"Open": [10.0, 10.0], "Close": [10.0, 10.0]}, index=sessions
    )
    base = {
        "variant_id": "ORDERED",
        "role": "CHALLENGER",
        "eligibility": {"all": []},
        "risk": {"fixed_r": 1.0},
        "portfolio": {"maximum_positions": 1, "maximum_heat_r": 1.0},
    }
    for ordering, match in (
        ([{"column": "Missing", "direction": "ASC"}], "column is missing"),
        ([{"column": "ticker", "direction": "SIDEWAYS"}], "direction is invalid"),
    ):
        with pytest.raises(ValueError, match=match):
            evaluate_portfolio_variants(
                episodes,
                {"AAA": history},
                sessions,
                [{**base, "ordering": ordering}],
                observation_end=sessions[-1],
                bootstrap_seed=7,
                bootstrap_resamples=10,
            )


def test_manual_earnings_exclusion_is_applied_before_research_accounting() -> None:
    signals = pd.DataFrame(
        {
            "signal_date": ["2026-01-02", "2026-01-02"],
            "ticker": ["AAA", "BBB"],
            "snapshot_generated_at": [
                "2026-01-02T22:00:00+00:00",
                "2026-01-02T22:00:00+00:00",
            ],
        }
    )
    events = pd.DataFrame(
        [
            {
                "event_type": "EARNINGS_SCREEN_COMPLETE",
                "signal_date": "2026-01-02",
                "reviewed_at": "2026-01-02T20:00:00+00:00",
                "recorded_at": "2026-01-02T20:01:00+00:00",
                "source": "fixture",
            },
            {
                "event_type": "EARNINGS_EXCLUSION",
                "signal_date": "2026-01-02",
                "ticker": "AAA",
                "earnings_date": "2026-01-08",
                "reviewed_at": "2026-01-02T20:00:00+00:00",
                "recorded_at": "2026-01-02T20:01:00+00:00",
                "reason": "earnings blackout",
            },
        ]
    )
    experiment = {
        "trading_policy": {
            "earnings_policy": "MANUAL_FAIL_CLOSED_JOURNAL",
            "earnings_blackout_calendar_days": 10,
        }
    }
    annotated = apply_manual_earnings_journal(experiment, signals, events)
    assert annotated.set_index("ticker")["earnings_excluded"].to_dict() == {
        "AAA": True,
        "BBB": False,
    }


def test_manual_earnings_review_recorded_after_snapshot_fails_closed() -> None:
    signals = pd.DataFrame(
        {
            "signal_date": ["2026-01-02"],
            "ticker": ["AAA"],
            "snapshot_generated_at": ["2026-01-02T22:00:00+00:00"],
        }
    )
    events = pd.DataFrame(
        [
            {
                "event_type": "EARNINGS_SCREEN_COMPLETE",
                "signal_date": "2026-01-02",
                "reviewed_at": "2026-01-02T23:00:00+00:00",
                "recorded_at": "2026-01-02T23:01:00+00:00",
                "source": "fixture",
            }
        ]
    )
    experiment = {"trading_policy": {"earnings_policy": "MANUAL_FAIL_CLOSED_JOURNAL"}}
    with pytest.raises(ValueError, match="no later than the signal snapshot"):
        apply_manual_earnings_journal(experiment, signals, events)


def test_manual_earnings_review_requires_non_empty_source() -> None:
    signals = pd.DataFrame(
        {
            "signal_date": ["2026-01-02"],
            "ticker": ["AAA"],
            "snapshot_generated_at": ["2026-01-02T22:00:00+00:00"],
        }
    )
    events = pd.DataFrame(
        [
            {
                "event_type": "EARNINGS_SCREEN_COMPLETE",
                "signal_date": "2026-01-02",
                "reviewed_at": "2026-01-02T20:00:00+00:00",
                "recorded_at": "2026-01-02T20:01:00+00:00",
                "source": "   ",
            }
        ]
    )
    experiment = {
        "trading_policy": {
            "earnings_policy": "MANUAL_FAIL_CLOSED_JOURNAL",
            "earnings_blackout_calendar_days": 10,
        }
    }
    with pytest.raises(ValueError, match="non-empty source"):
        apply_manual_earnings_journal(experiment, signals, events)


def test_earnings_exclusion_must_match_one_frozen_candidate() -> None:
    signals = pd.DataFrame(
        {
            "signal_date": ["2026-01-02"],
            "ticker": ["AAA"],
            "snapshot_generated_at": ["2026-01-02T22:00:00+00:00"],
        }
    )
    events = pd.DataFrame(
        [
            {
                "event_type": "EARNINGS_SCREEN_COMPLETE",
                "signal_date": "2026-01-02",
                "reviewed_at": "2026-01-02T20:00:00+00:00",
                "recorded_at": "2026-01-02T20:01:00+00:00",
                "source": "fixture",
            },
            {
                "event_type": "EARNINGS_EXCLUSION",
                "signal_date": "2026-01-02",
                "ticker": "AAB",
                "earnings_date": "2026-01-08",
                "reviewed_at": "2026-01-02T20:00:00+00:00",
                "recorded_at": "2026-01-02T20:01:00+00:00",
                "reason": "earnings blackout",
            },
        ]
    )
    experiment = {
        "trading_policy": {
            "earnings_policy": "MANUAL_FAIL_CLOSED_JOURNAL",
            "earnings_blackout_calendar_days": 10,
        }
    }
    with pytest.raises(ValueError, match="must match exactly one frozen candidate"):
        apply_manual_earnings_journal(experiment, signals, events)


def test_formal_outcome_input_audit_rejects_missing_candidate_history() -> None:
    signals = pd.DataFrame({"ticker": ["AAA"], "signal_date": ["2026-01-02"]})
    benchmark = pd.DataFrame(
        {
            "Open": [100.0],
            "High": [101.0],
            "Low": [99.0],
            "Close": [100.0],
            "Volume": [1_000_000],
        },
        index=pd.to_datetime(["2026-01-02"]),
    )
    with pytest.raises(ValueError, match="formal outcome inputs are incomplete"):
        audit_outcome_inputs(signals, {}, benchmark, formal=True)


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


def _active_formal_experiment(
    audit_experiment: dict[str, object], *, challenger_expected: bool
) -> dict[str, object]:
    frozen = dict(audit_experiment["frozen_epoch"])  # type: ignore[arg-type]
    frozen["strategy_epoch_id"] = "FORMAL_FIXTURE_EPOCH"
    ordering = audit_experiment["ranking_and_tie_break"]
    return {
        "experiment_id": "FORMAL_FIXTURE",
        "status": "PREREGISTERED_ACTIVE_COLLECTION",
        "collection_mode": "FORMAL",
        "research_label": "FORMAL TEST FIXTURE",
        "start_date": "2026-01-02",
        "frozen_epoch": frozen,
        "trading_policy": {
            "earnings_policy": "MANUAL_FAIL_CLOSED_JOURNAL",
            "earnings_blackout_calendar_days": 10,
            "earnings_snapshot_policy": "NOT_ENFORCED",
            "market_cap_snapshot_policy": "NOT_ENFORCED",
        },
        "plan_execution": {
            "entry_valid_sessions": 1,
            "entry_slippage_bps": 0.0,
            "exit_slippage_bps": 0.0,
            "maximum_holding_sessions_from_trigger": 2,
            "same_bar_policy": "STOP_FIRST",
            "favorable_target_gap_fill": "TARGET_LEVEL",
            "unresolved_policy": "OPEN_UNMATURED with null realised R",
        },
        "ranking_and_tie_break": audit_experiment["ranking_and_tie_break"],
        "sample_definition": {"minimum_mature_independent_episodes": 1},
        "uncertainty": {"seed": 1, "resamples": 10},
        "portfolio_experiment": {
            "variants": [
                {
                    "variant_id": "CHAMPION",
                    "role": "CHAMPION",
                    "eligibility": {
                        "all": [{"column": "snapshot_actionable", "equals": True}]
                    },
                    "risk": {"source_column": "Maximum Risk R"},
                    "portfolio": {"maximum_positions": 2, "maximum_heat_r": 2.0},
                    "ordering": ordering,
                },
                {
                    "variant_id": "CHALLENGER",
                    "role": "CHALLENGER",
                    "eligibility": {
                        "all": [
                            {
                                "column": "snapshot_actionable",
                                "equals": challenger_expected,
                            }
                        ]
                    },
                    "risk": {"fixed_r": 1.0},
                    "portfolio": {"maximum_positions": 2, "maximum_heat_r": 2.0},
                    "ordering": ordering,
                },
            ]
        },
    }


def _write_experiment(path: Path, experiment: dict[str, object]) -> Path:
    path.write_text(json.dumps(experiment), encoding="utf-8")
    return path


def test_formal_variant_ids_must_be_unique(tmp_path: Path) -> None:
    _, audit_experiment = _formal_snapshot(tmp_path / "snapshots")
    experiment = _active_formal_experiment(audit_experiment, challenger_expected=True)
    variants = experiment["portfolio_experiment"]["variants"]  # type: ignore[index]
    variants[1]["variant_id"] = str(  # type: ignore[index]
        variants[0]["variant_id"]  # type: ignore[index]
    ).lower()
    with pytest.raises(ValueError, match="variant_id values must be unique"):
        load_experiment(_write_experiment(tmp_path / "experiment.json", experiment))


def test_formal_variant_ordering_is_required_and_validated(tmp_path: Path) -> None:
    _, audit_experiment = _formal_snapshot(tmp_path / "snapshots")
    experiment = _active_formal_experiment(audit_experiment, challenger_expected=True)
    variants = experiment["portfolio_experiment"]["variants"]  # type: ignore[index]
    variants[1].pop("ordering")  # type: ignore[union-attr]
    with pytest.raises(ValueError, match="ordering is required"):
        load_experiment(_write_experiment(tmp_path / "missing.json", experiment))

    experiment = _active_formal_experiment(audit_experiment, challenger_expected=True)
    variants = experiment["portfolio_experiment"]["variants"]  # type: ignore[index]
    variants[1]["ordering"] = [  # type: ignore[index]
        {"column": "Final Score", "direction": "SIDEWAYS"}
    ]
    with pytest.raises(ValueError, match="invalid ordering rule"):
        load_experiment(_write_experiment(tmp_path / "direction.json", experiment))


def test_misspelled_formal_earnings_policy_fails_closed(tmp_path: Path) -> None:
    _, audit_experiment = _formal_snapshot(tmp_path / "snapshots")
    experiment = _active_formal_experiment(audit_experiment, challenger_expected=True)
    experiment["trading_policy"]["earnings_policy"] = (  # type: ignore[index]
        "MANUAL_FAIL_CLOSE_JOURNAL"
    )
    with pytest.raises(ValueError, match="unsupported earnings_policy"):
        load_experiment(_write_experiment(tmp_path / "experiment.json", experiment))


@pytest.mark.parametrize(
    ("field", "target"),
    [("entry_slippage_bps", "plan_execution"), ("maximum_heat_r", "portfolio")],
)
def test_non_finite_formal_numeric_settings_fail_closed(
    tmp_path: Path, field: str, target: str
) -> None:
    _, audit_experiment = _formal_snapshot(tmp_path / "snapshots")
    experiment = _active_formal_experiment(audit_experiment, challenger_expected=True)
    if target == "plan_execution":
        experiment["plan_execution"][field] = float("nan")  # type: ignore[index]
        match = "slippage must be finite"
    else:
        variants = experiment["portfolio_experiment"]["variants"]  # type: ignore[index]
        variants[0]["portfolio"][field] = float("nan")  # type: ignore[index]
        match = "maximum_heat_r must be finite"
    with pytest.raises(ValueError, match=match):
        load_experiment(_write_experiment(tmp_path / "experiment.json", experiment))


@pytest.mark.parametrize("sample_floor", [0, -1, 0.5, True])
def test_formal_sample_floor_must_be_a_positive_integer(
    tmp_path: Path, sample_floor: object
) -> None:
    _, audit_experiment = _formal_snapshot(tmp_path / "snapshots")
    experiment = _active_formal_experiment(audit_experiment, challenger_expected=True)
    experiment["sample_definition"][  # type: ignore[index]
        "minimum_mature_independent_episodes"
    ] = sample_floor
    with pytest.raises(ValueError, match="must be an integer >= 1"):
        load_experiment(_write_experiment(tmp_path / "experiment.json", experiment))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("entry_valid_sessions", 1.5),
        ("maximum_holding_sessions_from_trigger", "2.9"),
    ],
)
def test_formal_session_counts_reject_fractional_values(
    tmp_path: Path, field: str, value: object
) -> None:
    _, audit_experiment = _formal_snapshot(tmp_path / "snapshots")
    experiment = _active_formal_experiment(audit_experiment, challenger_expected=True)
    experiment["plan_execution"][field] = value  # type: ignore[index]
    with pytest.raises(ValueError, match=rf"{field} must be an integer >= 1"):
        load_experiment(_write_experiment(tmp_path / "experiment.json", experiment))


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("missing", "plan_execution missing fields: unresolved_policy"),
        ("mismatch", "supports only OPEN_UNMATURED"),
        ("extra", "formal plan_execution has unsupported fields"),
    ],
)
def test_formal_execution_contract_must_exactly_match_simulator(
    tmp_path: Path, mutation: str, match: str
) -> None:
    _, audit_experiment = _formal_snapshot(tmp_path / "snapshots")
    experiment = _active_formal_experiment(audit_experiment, challenger_expected=True)
    plan = experiment["plan_execution"]  # type: ignore[assignment]
    if mutation == "missing":
        plan.pop("unresolved_policy")  # type: ignore[union-attr]
    elif mutation == "mismatch":
        plan["unresolved_policy"] = "MARK_TO_MARKET"  # type: ignore[index]
    else:
        plan["commission_bps"] = 2.0  # type: ignore[index]
    with pytest.raises(ValueError, match=match):
        load_experiment(_write_experiment(tmp_path / f"{mutation}.json", experiment))


def _write_price_fixture(path: Path, ticker: str) -> None:
    pd.DataFrame(
        [
            {
                "Date": date,
                "Ticker": ticker,
                "Open": open_price,
                "High": high,
                "Low": low,
                "Close": close,
                "Volume": 1_000_000,
            }
            for date, open_price, high, low, close in (
                ("2026-01-02", 98.0, 99.0, 97.0, 98.0),
                ("2026-01-05", 100.0, 101.0, 99.0, 100.0),
                ("2026-01-06", 105.0, 111.0, 99.0, 110.0),
            )
        ]
    ).to_csv(path, index=False)


@pytest.mark.parametrize(
    ("challenger_expected", "expected_review_eligible"),
    [(True, True), (False, False)],
)
def test_active_formal_flow_requires_evidence_for_every_variant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    challenger_expected: bool,
    expected_review_eligible: bool,
) -> None:
    snapshot_root = tmp_path / "snapshots"
    _, audit_experiment = _formal_snapshot(snapshot_root)
    experiment = _active_formal_experiment(
        audit_experiment, challenger_expected=challenger_expected
    )
    experiment_path = tmp_path / "experiment.json"
    experiment_path.write_text(json.dumps(experiment), encoding="utf-8")
    prices = tmp_path / "prices.csv"
    benchmark = tmp_path / "benchmark.csv"
    _write_price_fixture(prices, "AAA")
    _write_price_fixture(benchmark, "SPY")
    events = tmp_path / "events.jsonl"
    events.write_text(
        json.dumps(
            {
                "event_id": "earnings-complete",
                "event_type": "EARNINGS_SCREEN_COMPLETE",
                "signal_date": "2026-01-02",
                "reviewed_at": "2026-01-02T20:00:00+00:00",
                "recorded_at": "2026-01-02T20:01:00+00:00",
                "source": "fixture",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "research_output"
    monkeypatch.setattr(
        "research.run_forward_test.ensure_research_output_path",
        lambda project_root, output_dir: output,
    )
    assert (
        run_forward_test(
            [
                "--snapshot-root",
                str(snapshot_root),
                "--output-dir",
                str(output),
                "--experiment",
                str(experiment_path),
                "--prices",
                str(prices),
                "--benchmark",
                str(benchmark),
                "--events",
                str(events),
            ]
        )
        == 0
    )
    run_dir = next((output / "runs").iterdir())
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert metadata["review_eligible"] is expected_review_eligible
    assert metadata["variant_sample_ready"] == {
        "CHALLENGER": expected_review_eligible,
        "CHAMPION": True,
    }
    assert metadata["plan_execution_applied"] == experiment["plan_execution"]
    assert manifest["prices_input_hash"] == sha256_file(prices)
    assert manifest["benchmark_input_hash"] == sha256_file(benchmark)
