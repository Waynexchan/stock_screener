from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import config
from research.engine.portfolio_ranking import (
    DEFAULT_RESEARCH_SEED,
    RANKER_NAMES,
    annotate_candidate_eligibility,
    build_ranking_dataset,
    deterministic_random_key,
    enrich_point_in_time_ranking_factors,
    evaluate_ranking_arms,
    phase_b_advancement_shortlist,
)
from research.run_portfolio_ranking_phase_a import (
    _stage_rows,
    prepare_candidate_journal,
    validate_runner_data_gate,
)


def candidates() -> pd.DataFrame:
    rows = []
    definitions = [
        ("2026-01-02", "CCC", True, "", "2026-01-05", "2026-01-08", 70.0),
        ("2026-01-02", "AAA", True, "", "2026-01-05", "2026-01-08", 90.0),
        ("2026-01-02", "BBB", True, "", "2026-01-05", "2026-01-08", 80.0),
        (
            "2026-01-02",
            "ZZZ",
            False,
            "CANONICAL_INELIGIBLE",
            "2026-01-05",
            "2026-01-08",
            100.0,
        ),
        ("2026-01-06", "DDD", True, "", "2026-01-07", "2026-01-09", 95.0),
        ("2026-01-08", "EEE", True, "", "2026-01-09", "2026-01-12", 85.0),
    ]
    for offset, (as_of, ticker, eligible, reason, entry, exit_date, score) in enumerate(
        definitions
    ):
        rows.append(
            {
                "as_of_date": as_of,
                "ticker": ticker,
                "canonical_eligible": eligible,
                "canonical_blocked_reason": reason,
                "Final Score": score,
                "recent_rs_score": 95.0 - offset,
                "industry_proxy_score": np.nan if ticker == "CCC" else 80.0 - offset,
                "pivot_supply_quality_score": 70.0 + offset,
                "volume_quality_score": 60.0 + offset,
                "Industry": "Software",
                "Sector": "Technology",
                "Industry Composite Score": 70.0,
                "effective_heat_limit_r": 2.0,
                "plan_entry_date": entry,
                "plan_exit_date": exit_date,
                "plan_entry": 100.0,
                "Initial Stop": 95.0,
                "plan_realised_r": 1.0 if ticker != "BBB" else -1.0,
                "plan_mfe_r": 1.5,
                "plan_mae_r": -0.5,
                "plan_holding_sessions": 4,
            }
        )
    return pd.DataFrame(rows)


def annotated_candidates() -> pd.DataFrame:
    return annotate_candidate_eligibility(
        candidates(),
        eligibility_column="canonical_eligible",
        blocked_reason_column="canonical_blocked_reason",
    )


def histories() -> dict[str, pd.DataFrame]:
    dates = pd.bdate_range("2026-01-05", "2026-01-12")
    frame = pd.DataFrame({"Close": [101.0] * len(dates)}, index=dates)
    return {ticker: frame.copy() for ticker in candidates()["ticker"]}


def test_fixed_random_baseline_has_a_known_cross_process_key() -> None:
    expected = "487a92fbcd4024db1b4b354d1dd519e570cc3eb0ef79bc1aeb8b46fe406e857f"
    assert (
        deterministic_random_key(DEFAULT_RESEARCH_SEED, "2026-01-02", "AAA") == expected
    )
    command = (
        "from research.engine.portfolio_ranking import deterministic_random_key; "
        "print(deterministic_random_key(20260916, '2026-01-02', 'AAA'))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", command], check=True, capture_output=True, text=True
    )
    assert completed.stdout.strip() == expected


def test_rankings_are_permutation_invariant_and_use_exact_composite_weights() -> None:
    baseline = build_ranking_dataset(annotated_candidates())
    shuffled = (
        annotated_candidates().sample(frac=1.0, random_state=42).reset_index(drop=True)
    )
    reranked = build_ranking_dataset(shuffled)
    columns = ["as_of_date", "ticker", "ranker_name", "rank_score", "rank_position"]
    pd.testing.assert_frame_equal(
        baseline[columns].sort_values(columns[:3]).reset_index(drop=True),
        reranked[columns].sort_values(columns[:3]).reset_index(drop=True),
    )
    composite = baseline[
        baseline["ranker_name"].eq("composite_equal_weight")
        & baseline["ticker"].eq("AAA")
    ].iloc[0]
    expected = 0.25 * sum(
        composite[f"{factor}_percentile"]
        for factor in (
            "recent_rs",
            "industry_strength",
            "pivot_supply_quality",
            "volume_quality",
        )
    )
    assert composite["rank_score"] == pytest.approx(expected)
    loo = baseline[
        baseline["ranker_name"].eq("loo_without_recent_rs")
        & baseline["ticker"].eq("AAA")
    ].iloc[0]
    assert loo["rank_score"] == pytest.approx(
        sum(
            loo[f"{factor}_percentile"]
            for factor in (
                "industry_strength",
                "pivot_supply_quality",
                "volume_quality",
            )
        )
        / 3.0
    )


def test_missing_industry_strength_is_ranked_last_without_changing_eligibility() -> (
    None
):
    ranked = build_ranking_dataset(annotated_candidates())
    same_day = ranked[
        ranked["ranker_name"].eq("industry_strength")
        & ranked["as_of_date"].eq("2026-01-02")
    ].set_index("ticker")
    assert same_day.at["CCC", "industry_strength_percentile"] == 0.0
    assert same_day.at["CCC", "rank_position"] == 3
    assert bool(same_day.at["CCC", "ranking_eligible"])
    assert pd.isna(same_day.at["ZZZ", "rank_position"])


def test_non_finite_final_score_and_factor_values_are_missing_last() -> None:
    annotated = annotated_candidates()
    annotated.loc[annotated["ticker"].eq("AAA"), "Final Score"] = np.inf
    annotated.loc[annotated["ticker"].eq("AAA"), "industry_proxy_score"] = -np.inf
    annotated.loc[annotated["ticker"].eq("CCC"), "industry_proxy_score"] = 70.0
    ranked = build_ranking_dataset(annotated)
    production = ranked[
        ranked["ranker_name"].eq("production_final_score")
        & ranked["as_of_date"].eq("2026-01-02")
    ].set_index("ticker")
    industry = ranked[
        ranked["ranker_name"].eq("industry_strength")
        & ranked["as_of_date"].eq("2026-01-02")
    ].set_index("ticker")
    assert pd.isna(production.at["AAA", "raw_final_score"])
    assert production.at["AAA", "rank_position"] == 3
    assert pd.isna(industry.at["AAA", "industry_strength_raw"])
    assert industry.at["AAA", "industry_strength_percentile"] == 0.0
    assert industry.at["AAA", "rank_position"] == 3


def test_portfolio_ranking_uses_exit_aware_heat_and_audits_every_arm() -> None:
    annotated = annotated_candidates()
    metrics, audit, curves, intervals = evaluate_ranking_arms(
        annotated,
        histories(),
        pd.bdate_range("2026-01-05", "2026-01-12"),
        risk={"fixed_r": 1.0},
        portfolio={
            "maximum_positions": 4,
            "maximum_heat_r": 3.0,
            "maximum_heat_r_source_column": "effective_heat_limit_r",
        },
        observation_end=pd.Timestamp("2026-01-12"),
        bootstrap_resamples=10,
    )
    assert set(metrics["ranker_name"]) == set(RANKER_NAMES)
    assert set(intervals) == set(RANKER_NAMES)
    assert not curves.empty
    production = audit[audit["ranker_name"].eq("production_final_score")].set_index(
        "ticker"
    )
    assert bool(production.at["AAA", "selected"])
    assert bool(production.at["BBB", "selected"])
    assert not bool(production.at["CCC", "selected"])
    assert production.at["CCC", "blocked_reason"] == "MAX_HEAT"
    assert production.at["CCC", "portfolio_heat_before"] == 2.0
    assert production.at["CCC", "portfolio_heat_after"] == 2.0
    assert production.at["DDD", "blocked_reason"] == "MAX_HEAT"
    assert bool(production.at["EEE", "selected"])
    assert production.at["EEE", "portfolio_heat_before"] == 0.0
    assert production.at["EEE", "portfolio_heat_after"] == 1.0
    assert production.at["ZZZ", "blocked_reason"] == "CANONICAL_INELIGIBLE"
    assert pd.isna(production.at["ZZZ", "rank_position"])
    assert "champion" not in {column.casefold() for column in metrics.columns}
    production_metrics = metrics[
        metrics["ranker_name"].eq("production_final_score")
    ].iloc[0]
    assert production_metrics["candidate_count"] == 6
    assert production_metrics["eligible_candidate_count"] == 5
    assert production_metrics["ineligible_candidate_count"] == 1
    assert production_metrics["canonical_ineligible_candidate_count"] == 1
    assert production_metrics["blocked_reason_counts"] == {
        "CANONICAL_INELIGIBLE": 1,
        "MAX_HEAT": 2,
    }
    assert {
        "as_of_date",
        "ticker",
        "ranker_name",
        "recent_rs_raw",
        "industry_strength_raw",
        "pivot_supply_quality_raw",
        "volume_quality_raw",
        "recent_rs_percentile",
        "industry_strength_percentile",
        "pivot_supply_quality_percentile",
        "volume_quality_percentile",
        "rank_score",
        "rank_position",
        "selected",
        "blocked_reason",
        "portfolio_heat_before",
        "portfolio_heat_after",
    } <= set(audit)

    replay_metrics, replay_audit, _, _ = evaluate_ranking_arms(
        annotated.sample(frac=1.0, random_state=9).reset_index(drop=True),
        histories(),
        pd.bdate_range("2026-01-05", "2026-01-12"),
        risk={"fixed_r": 1.0},
        portfolio={
            "maximum_positions": 4,
            "maximum_heat_r": 3.0,
            "maximum_heat_r_source_column": "effective_heat_limit_r",
        },
        observation_end=pd.Timestamp("2026-01-12"),
        bootstrap_resamples=10,
    )
    pd.testing.assert_frame_equal(
        metrics.sort_values("ranker_name").reset_index(drop=True),
        replay_metrics.sort_values("ranker_name").reset_index(drop=True),
    )
    audit_comparison = [
        "ranker_name",
        "as_of_date",
        "ticker",
        "rank_position",
        "selected",
        "blocked_reason",
        "portfolio_heat_before",
        "portfolio_heat_after",
    ]
    pd.testing.assert_frame_equal(
        audit[audit_comparison]
        .sort_values(audit_comparison[:3])
        .reset_index(drop=True),
        replay_audit[audit_comparison]
        .sort_values(audit_comparison[:3])
        .reset_index(drop=True),
    )


def test_candidate_concentration_is_reapplied_after_each_ranker_orders_rows() -> None:
    annotated = annotated_candidates()
    annotated = annotated[
        annotated["as_of_date"].eq("2026-01-02") & annotated["ranking_eligible"]
    ].copy()
    portfolio = {
        "maximum_positions": 4,
        "maximum_heat_r": 3.0,
        "maximum_heat_r_source_column": "effective_heat_limit_r",
        "candidate_concentration": {
            "industry_column": "Industry",
            "sector_column": "Sector",
            "industry_score_column": "Industry Composite Score",
            "maximum_per_industry": 1,
            "high_conviction_industry_score": 90.0,
            "high_conviction_extra_positions": 1,
            "maximum_per_sector": 5,
        },
    }
    metrics, audit, _, _ = evaluate_ranking_arms(
        annotated,
        histories(),
        pd.bdate_range("2026-01-05", "2026-01-12"),
        risk={"fixed_r": 1.0},
        portfolio=portfolio,
        observation_end=pd.Timestamp("2026-01-12"),
        bootstrap_resamples=10,
    )
    assert not metrics.empty
    production = audit[audit["ranker_name"].eq("production_final_score")].set_index(
        "ticker"
    )
    volume = audit[audit["ranker_name"].eq("volume_quality")].set_index("ticker")
    assert bool(production.at["AAA", "selected"])
    assert production.at["BBB", "blocked_reason"] == "INDUSTRY_CONCENTRATION"
    assert production.at["CCC", "blocked_reason"] == "INDUSTRY_CONCENTRATION"
    assert bool(volume.at["BBB", "selected"])
    assert volume.at["AAA", "blocked_reason"] == "INDUSTRY_CONCENTRATION"
    production_metrics = metrics[
        metrics["ranker_name"].eq("production_final_score")
    ].iloc[0]
    assert production_metrics["blocked_reason_counts"] == {"INDUSTRY_CONCENTRATION": 2}
    replay_metrics, replay_audit, _, _ = evaluate_ranking_arms(
        annotated.sample(frac=1.0, random_state=71).reset_index(drop=True),
        histories(),
        pd.bdate_range("2026-01-05", "2026-01-12"),
        risk={"fixed_r": 1.0},
        portfolio=portfolio,
        observation_end=pd.Timestamp("2026-01-12"),
        bootstrap_resamples=10,
    )
    pd.testing.assert_frame_equal(
        metrics.sort_values("ranker_name").reset_index(drop=True),
        replay_metrics.sort_values("ranker_name").reset_index(drop=True),
    )
    comparison = [
        "ranker_name",
        "as_of_date",
        "ticker",
        "rank_position",
        "selected",
        "blocked_reason",
    ]
    pd.testing.assert_frame_equal(
        audit[comparison].sort_values(comparison[:3]).reset_index(drop=True),
        replay_audit[comparison].sort_values(comparison[:3]).reset_index(drop=True),
    )


def test_duplicate_business_keys_fail_instead_of_using_row_order() -> None:
    duplicated = pd.concat([candidates(), candidates().iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate as_of_date/ticker"):
        annotate_candidate_eligibility(
            duplicated,
            eligibility_column="canonical_eligible",
            blocked_reason_column="canonical_blocked_reason",
        )


def _price_history() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=320)
    close = pd.Series(
        np.linspace(50.0, 100.0, len(dates))
        + 3.0 * np.sin(np.arange(len(dates), dtype=float)),
        index=dates,
    )
    return pd.DataFrame(
        {
            "Open": close * 0.995,
            "High": close * 1.01,
            "Low": close * 0.985,
            "Close": close,
            "Volume": np.where(np.arange(len(dates)) % 2 == 0, 1_000_000, 800_000),
        },
        index=dates,
    )


def test_point_in_time_factor_builder_has_real_fixed_formulas_and_no_future_leak() -> (
    None
):
    history = _price_history()
    as_of = history.index[279]
    input_rows = pd.DataFrame(
        {"as_of_date": [as_of.date().isoformat()], "ticker": ["AAA"]}
    )
    baseline = enrich_point_in_time_ranking_factors(
        input_rows,
        {"AAA": history},
        history,
        sectors={"AAA": "Technology"},
        industries={"AAA": "Software"},
        minimum_industry_members=1,
    )
    changed = history.copy()
    changed.loc[changed.index > as_of, ["Open", "High", "Low", "Close", "Volume"]] = [
        900.0,
        1_000.0,
        1.0,
        950.0,
        99_000_000,
    ]
    replay = enrich_point_in_time_ranking_factors(
        input_rows,
        {"AAA": changed},
        changed,
        sectors={"AAA": "Technology"},
        industries={"AAA": "Software"},
        minimum_industry_members=1,
    )
    columns = list(
        {
            "recent_rs_score",
            "industry_proxy_score",
            "pivot_supply_quality_score",
            "volume_quality_score",
        }
    )
    pd.testing.assert_series_equal(
        baseline.loc[0, columns], replay.loc[0, columns], check_names=False
    )
    assert baseline.at[0, "pivot_supply_quality_score"] == pytest.approx(
        10.0 - baseline.at[0, "pivot_supply_days_10d"]
    )
    assert baseline.at[0, "volume_quality_score"] == pytest.approx(
        baseline.at[0, "up_down_volume_ratio_50d"]
    )


def test_candidate_journal_keeps_eligibility_separate_from_ranking() -> None:
    journal = candidates().rename(columns={"canonical_eligible": "source_eligible"})
    journal["canonical_eligible"] = journal.pop("source_eligible")
    journal["candidate_risk_r"] = 1.0
    journal["plan_triggered"] = True
    journal.loc[journal["ticker"].eq("CCC"), "plan_triggered"] = False
    prepared = prepare_candidate_journal(journal).set_index("ticker")
    assert bool(prepared.at["AAA", "canonical_eligible"])
    assert bool(prepared.at["AAA", "ranking_eligible"])
    assert bool(prepared.at["CCC", "canonical_eligible"])
    assert not bool(prepared.at["CCC", "ranking_eligible"])
    assert prepared.at["CCC", "eligibility_blocked_reason"] == "PLAN_NOT_TRIGGERED"
    assert not bool(prepared.at["ZZZ", "ranking_eligible"])
    assert prepared.at["ZZZ", "eligibility_blocked_reason"] == "CANONICAL_INELIGIBLE"


def test_formal_stage_purges_outcomes_that_cross_observation_cutoff() -> None:
    row = candidates().iloc[[0]].copy()
    row["as_of_date"] = "2027-09-17"
    row["plan_entry_date"] = "2027-09-20"
    row["plan_exit_date"] = "2027-11-22"
    row["plan_realised_r"] = 9.0
    row["candidate_risk_r"] = 1.0
    prepared = prepare_candidate_journal(row)
    experiment = {
        "formal_periods": {
            "development": {
                "signal_start": "2026-09-21",
                "signal_end": "2027-09-17",
                "outcomes_observed_through": "2027-11-19",
            },
            "validation": {
                "signal_start": "2027-11-22",
                "signal_end": "2028-05-19",
                "outcomes_observed_through": "2028-07-21",
            },
        }
    }
    stages = _stage_rows(prepared, experiment, engineering_replay=False)
    assert len(stages) == 1
    stage_name, stage, observation_end = stages[0]
    assert stage_name == "development"
    assert observation_end == pd.Timestamp("2027-11-19")
    assert bool(stage.at[stage.index[0], "stage_outcome_purged"])
    assert pd.isna(stage.at[stage.index[0], "plan_exit_date"])
    assert pd.isna(stage.at[stage.index[0], "plan_realised_r"])

    sessions = pd.bdate_range("2027-09-20", "2027-11-19")
    history = pd.DataFrame({"Close": 101.0}, index=sessions)
    metrics, _, _, _ = evaluate_ranking_arms(
        stage,
        {"CCC": history},
        sessions,
        risk={"source_column": "candidate_risk_r"},
        portfolio={"maximum_positions": 4, "maximum_heat_r": 3.0},
        observation_end=observation_end,
        bootstrap_resamples=10,
    )
    production = metrics[metrics["ranker_name"].eq("production_final_score")].iloc[0]
    assert production["accepted_episode_count"] == 1
    assert production["mature_accepted_episode_count"] == 0
    assert production["open_accepted_episode_count"] == 1
    assert pd.isna(production["expectancy_r"])


def test_formal_runner_fails_closed_before_current_classifications_are_used() -> None:
    experiment_path = (
        Path(__file__).parents[1] / "experiments" / "portfolio_ranking_phase_a_v1.json"
    )
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    assert (
        validate_runner_data_gate(experiment, engineering_replay=True)
        == "ENGINEERING_CURRENT_CLASSIFICATION_NON_VALIDATING"
    )
    with pytest.raises(ValueError, match="BLOCKED_DATA_NOT_READY"):
        validate_runner_data_gate(experiment, engineering_replay=False)

    ready_but_current = dict(experiment)
    ready_but_current["formal_data_gate"] = {
        "status": "READY",
        "classification_provenance": "CURRENT_NOT_EFFECTIVE_DATED",
        "formal_runner_enabled": True,
    }
    with pytest.raises(ValueError, match="point-in-time effective-dated"):
        validate_runner_data_gate(ready_but_current, engineering_replay=False)

    declared_ready = dict(experiment)
    declared_ready["formal_data_gate"] = {
        "status": "READY",
        "classification_provenance": "POINT_IN_TIME_EFFECTIVE_DATED",
        "formal_runner_enabled": True,
    }
    with pytest.raises(ValueError, match="loading is not implemented"):
        validate_runner_data_gate(declared_ready, engineering_replay=False)


def test_preregistered_concentration_matches_production_constants() -> None:
    experiment_path = (
        Path(__file__).parents[1] / "experiments" / "portfolio_ranking_phase_a_v1.json"
    )
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    concentration = experiment["portfolio_evaluation"]["runner_contract"][
        "candidate_concentration"
    ]
    assert concentration["maximum_per_industry"] == config.MAX_TOP_ACTION_PER_INDUSTRY
    assert (
        concentration["high_conviction_industry_score"]
        == config.HIGH_CONVICTION_INDUSTRY_SCORE
    )
    assert concentration["high_conviction_extra_positions"] == 1
    assert concentration["maximum_per_sector"] == config.MAX_PER_SECTOR


def test_phase_b_gate_is_frozen_and_returns_shortlist_not_champion() -> None:
    rows = []
    definitions = {
        "production_final_score": (0.10, 1.20, 10.0, 4.0),
        "recent_rs": (0.17, 1.30, 12.0, 4.5),
        "volume_quality": (0.12, 1.25, 11.0, 4.0),
        "deterministic_random": (0.30, 2.00, 20.0, 2.0),
    }
    for stage in ("development", "validation"):
        for ranker, values in definitions.items():
            expectancy, profit_factor, total_r, drawdown = values
            rows.append(
                {
                    "stage": stage,
                    "ranker_name": ranker,
                    "mature_accepted_episode_count": 120,
                    "expectancy_r": expectancy,
                    "profit_factor": profit_factor,
                    "total_realised_r": total_r,
                    "maximum_drawdown_r": drawdown,
                }
            )
    gate = {
        "baseline_ranker": "production_final_score",
        "excluded_rankers": ["deterministic_random"],
        "required_stages": ["development", "validation"],
        "minimum_mature_accepted_episodes_per_stage": 100,
        "minimum_expectancy_improvement_r": 0.05,
        "maximum_drawdown_worsening_r": 1.0,
        "maximum_phase_b_rankers": 2,
    }
    shortlist = phase_b_advancement_shortlist(pd.DataFrame(rows), gate).set_index(
        "ranker_name"
    )
    assert bool(shortlist.at["recent_rs", "shortlisted_for_phase_b_review"])
    assert not bool(shortlist.at["volume_quality", "phase_b_eligible"])
    assert "deterministic_random" not in shortlist.index
    assert "champion" not in shortlist.columns


def _valid_gate() -> dict[str, object]:
    return {
        "baseline_ranker": "production_final_score",
        "excluded_rankers": ["deterministic_random"],
        "required_stages": ["development", "validation"],
        "minimum_mature_accepted_episodes_per_stage": 100,
        "minimum_expectancy_improvement_r": 0.05,
        "maximum_drawdown_worsening_r": 1.0,
        "maximum_phase_b_rankers": 2,
    }


def _gate_metrics(*, baseline_count: int = 120) -> pd.DataFrame:
    rows = []
    for stage in ("development", "validation"):
        rows.extend(
            [
                {
                    "stage": stage,
                    "ranker_name": "production_final_score",
                    "mature_accepted_episode_count": baseline_count,
                    "expectancy_r": 0.10,
                    "profit_factor": 1.20,
                    "total_realised_r": 10.0,
                    "maximum_drawdown_r": 4.0,
                },
                {
                    "stage": stage,
                    "ranker_name": "recent_rs",
                    "mature_accepted_episode_count": 120,
                    "expectancy_r": 0.20,
                    "profit_factor": 1.40,
                    "total_realised_r": 14.0,
                    "maximum_drawdown_r": 4.5,
                },
            ]
        )
    return pd.DataFrame(rows)


def test_phase_b_gate_requires_baseline_to_meet_sample_floor() -> None:
    shortlist = phase_b_advancement_shortlist(
        _gate_metrics(baseline_count=1), _valid_gate()
    ).set_index("ranker_name")
    assert not bool(shortlist.at["recent_rs", "phase_b_eligible"])
    assert not bool(shortlist.at["recent_rs", "shortlisted_for_phase_b_review"])
    assert (
        "development:BASELINE_INSUFFICIENT_MATURE_EPISODES"
        in shortlist.at["recent_rs", "gate_failures"]
    )
    assert (
        "validation:BASELINE_INSUFFICIENT_MATURE_EPISODES"
        in shortlist.at["recent_rs", "gate_failures"]
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("minimum_mature_accepted_episodes_per_stage", 100.9),
        ("minimum_mature_accepted_episodes_per_stage", True),
        ("minimum_mature_accepted_episodes_per_stage", np.nan),
        ("minimum_expectancy_improvement_r", np.nan),
        ("minimum_expectancy_improvement_r", -0.01),
        ("minimum_expectancy_improvement_r", True),
        ("maximum_drawdown_worsening_r", np.nan),
        ("maximum_drawdown_worsening_r", -1.0),
        ("maximum_phase_b_rankers", 1.5),
        ("maximum_phase_b_rankers", True),
        ("maximum_phase_b_rankers", 3),
    ],
)
def test_phase_b_gate_rejects_permissive_numeric_coercion(
    field: str, value: object
) -> None:
    gate = _valid_gate()
    gate[field] = value
    with pytest.raises(ValueError):
        phase_b_advancement_shortlist(_gate_metrics(), gate)
