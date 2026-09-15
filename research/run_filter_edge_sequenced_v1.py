"""Run the preregistered opportunity-first filter and concentration audit."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research.engine.base_features import enrich_base_features
from research.engine.baseline import execution_assumptions, load_model_0_config
from research.engine.data import load_price_csv
from research.engine.earnings import (
    EarningsBlackoutContext,
    apply_earnings_blackout_to_signals,
    load_verified_earnings_blackout_context,
)
from research.engine.features import generate_model_0_features
from research.engine.leader_features import (
    enrich_leader_features,
    load_current_sector_industry,
)
from research.engine.market_features import enrich_market_features
from research.engine.models import ExecutionAssumptions, SimulatedTrade
from research.engine.portfolio_overlays import simulate_portfolio_overlay
from research.engine.reporting import ensure_research_output_path
from research.engine.reproducibility import git_state, sha256_file
from research.run_filter_combination_audit_v1 import (
    _factorial_variant_id,
    enrich_spy_signal_trend,
    generate_variants,
)
from research.run_leader_rs_robustness import _simulate_independent, variant_mask


STAGE_ORDER = ["development_2017_2023", "reused_2024", "reused_2025"]


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--prices", type=Path, required=True)
    command.add_argument("--benchmark", type=Path, required=True)
    command.add_argument("--earnings", type=Path, required=True)
    command.add_argument("--earnings-metadata", type=Path, required=True)
    command.add_argument(
        "--prior-portfolio-results",
        type=Path,
        default=Path(
            "research/output/filter_combination_audit_v1/combination_decisions.csv"
        ),
    )
    command.add_argument(
        "--output-dir",
        type=Path,
        default=Path("research/output/filter_edge_sequenced_v1"),
    )
    return command


def select_nonoverlapping_ticker_episodes(
    trades: list[SimulatedTrade],
) -> tuple[list[SimulatedTrade], int]:
    """Allow one open opportunity per ticker without cross-stock constraints."""

    accepted: list[SimulatedTrade] = []
    last_exit_by_ticker: dict[str, pd.Timestamp] = {}
    rejected = 0
    for trade in sorted(
        trades,
        key=lambda item: (
            item.ticker,
            pd.Timestamp(item.entry_date),
            pd.Timestamp(item.signal_date),
        ),
    ):
        entry = pd.Timestamp(trade.entry_date)
        previous_exit = last_exit_by_ticker.get(trade.ticker)
        if previous_exit is not None and entry <= previous_exit:
            rejected += 1
            continue
        accepted.append(trade)
        last_exit_by_ticker[trade.ticker] = pd.Timestamp(trade.exit_date)
    return accepted, rejected


def _ratio(numerator: float, denominator: float) -> float | None:
    return None if denominator == 0 else float(numerator / denominator)


def opportunity_metrics(
    trades: list[SimulatedTrade],
    *,
    selected_signal_count: int,
    executable_trade_count: int,
    overlap_rejection_count: int,
) -> dict[str, Any]:
    frame = pd.DataFrame([trade.to_dict() for trade in trades])
    empty: dict[str, Any] = {
        "selected_signal_count": selected_signal_count,
        "executable_trade_count": executable_trade_count,
        "episode_count": 0,
        "overlap_rejection_count": overlap_rejection_count,
        "unique_ticker_count": 0,
        "expectancy_r": None,
        "median_r": None,
        "standard_deviation_r": None,
        "win_rate": None,
        "average_win_r": None,
        "average_loss_r": None,
        "payoff_ratio": None,
        "profit_factor": None,
        "average_mfe_r": None,
        "average_mae_r": None,
        "average_holding_days": None,
        "total_r": 0.0,
        "largest_winner_r": None,
        "largest_winner_share_of_positive_r": None,
        "exit_reason_counts": "{}",
    }
    if frame.empty:
        return empty
    realised = pd.to_numeric(frame["realised_r"], errors="coerce")
    wins = realised[realised > 0]
    losses = realised[realised <= 0]
    average_win = None if wins.empty else float(wins.mean())
    average_loss = None if losses.empty else float(losses.mean())
    positive_total = float(wins.sum())
    largest_winner = 0.0 if wins.empty else float(wins.max())
    return {
        **empty,
        "episode_count": len(frame),
        "unique_ticker_count": int(frame["ticker"].nunique()),
        "expectancy_r": float(realised.mean()),
        "median_r": float(realised.median()),
        "standard_deviation_r": float(realised.std(ddof=1)) if len(frame) > 1 else None,
        "win_rate": float((realised > 0).mean()),
        "average_win_r": average_win,
        "average_loss_r": average_loss,
        "payoff_ratio": (
            None
            if average_win is None or average_loss in (None, 0)
            else average_win / abs(average_loss)
        ),
        "profit_factor": _ratio(positive_total, abs(float(losses.sum()))),
        "average_mfe_r": float(pd.to_numeric(frame["MFE_R"]).mean()),
        "average_mae_r": float(pd.to_numeric(frame["MAE_R"]).mean()),
        "average_holding_days": float(pd.to_numeric(frame["holding_days"]).mean()),
        "total_r": float(realised.sum()),
        "largest_winner_r": largest_winner,
        "largest_winner_share_of_positive_r": _ratio(largest_winner, positive_total),
        "exit_reason_counts": json.dumps(
            dict(sorted(Counter(frame["exit_reason"]).items()))
        ),
    }


def monthly_block_delta_interval(
    baseline: list[SimulatedTrade],
    variant: list[SimulatedTrade],
    *,
    samples: int,
    confidence: float,
    seed: int,
) -> tuple[float | None, float | None]:
    """Paired calendar-month bootstrap interval for expectancy change."""

    if samples <= 0 or not baseline or not variant:
        return None, None

    def aggregates(trades: list[SimulatedTrade]) -> dict[str, tuple[float, int]]:
        grouped: dict[str, list[float]] = {}
        for trade in trades:
            month = pd.Timestamp(trade.entry_date).to_period("M").strftime("%Y-%m")
            grouped.setdefault(month, []).append(float(trade.realised_r))
        return {
            month: (float(np.sum(values)), len(values))
            for month, values in grouped.items()
        }

    base = aggregates(baseline)
    selected = aggregates(variant)
    months = sorted(set(base) | set(selected))
    if len(months) < 2:
        return None, None
    base_sum = np.asarray([base.get(month, (0.0, 0))[0] for month in months])
    base_count = np.asarray([base.get(month, (0.0, 0))[1] for month in months])
    selected_sum = np.asarray([selected.get(month, (0.0, 0))[0] for month in months])
    selected_count = np.asarray([selected.get(month, (0.0, 0))[1] for month in months])
    generator = np.random.default_rng(seed)
    draws = generator.integers(0, len(months), size=(samples, len(months)))
    base_denominator = base_count[draws].sum(axis=1)
    selected_denominator = selected_count[draws].sum(axis=1)
    valid = (base_denominator > 0) & (selected_denominator > 0)
    if valid.sum() < max(100, samples // 2):
        return None, None
    deltas = (
        selected_sum[draws].sum(axis=1)[valid] / selected_denominator[valid]
        - base_sum[draws].sum(axis=1)[valid] / base_denominator[valid]
    )
    tail = (1.0 - confidence) / 2.0
    return float(np.quantile(deltas, tail)), float(np.quantile(deltas, 1.0 - tail))


def _metric_delta(child: Any, parent: Any) -> float | None:
    if child is None or parent is None or pd.isna(child) or pd.isna(parent):
        return None
    return float(child) - float(parent)


def add_opportunity_deltas(
    rows: list[dict[str, Any]],
    episode_sets: dict[tuple[str, str], list[SimulatedTrade]],
    experiment: dict[str, Any],
) -> None:
    by_key = {(str(row["stage"]), str(row["variant_id"])): row for row in rows}
    bootstrap = experiment["opportunity_construction"]
    for stage_index, stage in enumerate(STAGE_ORDER):
        baseline = by_key[(stage, "baseline")]
        baseline_episodes = episode_sets[(stage, "baseline")]
        stage_rows = [row for row in rows if str(row["stage"]) == stage]
        for variant_index, row in enumerate(stage_rows):
            for metric in (
                "expectancy_r",
                "profit_factor",
                "average_mfe_r",
                "average_mae_r",
                "win_rate",
                "payoff_ratio",
            ):
                row[f"{metric}_delta_vs_baseline"] = _metric_delta(
                    row.get(metric), baseline.get(metric)
                )
            row["episode_retention_vs_baseline_pct"] = (
                0.0
                if int(baseline["episode_count"]) == 0
                else int(row["episode_count"]) / int(baseline["episode_count"]) * 100.0
            )
            low, high = monthly_block_delta_interval(
                baseline_episodes,
                episode_sets[(stage, str(row["variant_id"]))],
                samples=int(bootstrap["bootstrap_samples"]),
                confidence=float(bootstrap["bootstrap_confidence"]),
                seed=int(bootstrap["bootstrap_seed"])
                + stage_index * 1_000
                + variant_index,
            )
            row["expectancy_delta_month_block_95_low_r"] = low
            row["expectancy_delta_month_block_95_high_r"] = high


def _count_positive(values: list[Any], *, above: float = 0.0) -> int:
    return sum(
        value is not None and not pd.isna(value) and float(value) > above
        for value in values
    )


def classify_variant(
    variant_id: str,
    stage_rows: list[dict[str, Any]],
    gate: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    if variant_id == "baseline":
        return "BASELINE", {}
    by_stage = {str(row["stage"]): row for row in stage_rows}
    development = by_stage["development_2017_2023"]
    reused = [by_stage["reused_2024"], by_stage["reused_2025"]]
    sample_ok = bool(
        int(development["episode_count"])
        >= int(gate["development_episode_count_at_least"])
        and all(
            int(row["episode_count"]) >= int(gate["reused_episode_count_at_least"])
            for row in reused
        )
    )
    positive_expectancy_count = _count_positive(
        [row.get("expectancy_r") for row in stage_rows]
    )
    expectancy_deltas = [
        row.get("expectancy_r_delta_vs_baseline") for row in stage_rows
    ]
    alpha_improvements = _count_positive(
        expectancy_deltas,
        above=float(gate["alpha_expectancy_delta_at_least_r"]) - 1e-12,
    )
    profit_factor_improvements = _count_positive(
        [row.get("profit_factor_delta_vs_baseline") for row in stage_rows]
    )
    mfe_improvements = _count_positive(
        [row.get("average_mfe_r_delta_vs_baseline") for row in stage_rows]
    )
    mae_improvements = _count_positive(
        [row.get("average_mae_r_delta_vs_baseline") for row in stage_rows]
    )
    retention_ok = all(
        float(row["episode_retention_vs_baseline_pct"])
        >= float(gate["retention_vs_baseline_at_least_pct"])
        for row in stage_rows
    )
    development_low = development.get("expectancy_delta_month_block_95_low_r")
    development_ci_ok = bool(
        development_low is not None
        and float(development_low)
        > float(gate["alpha_development_bootstrap_delta_low_above_r"])
    )
    alpha = bool(
        sample_ok
        and positive_expectancy_count == len(STAGE_ORDER)
        and alpha_improvements
        >= int(gate["alpha_expectancy_improvement_periods_at_least"])
        and development_ci_ok
        and profit_factor_improvements
        >= int(gate["alpha_profit_factor_improvement_periods_at_least"])
        and mfe_improvements >= int(gate["alpha_mfe_improvement_periods_at_least"])
        and retention_ok
    )
    risk_expectancy_ok = all(
        value is not None
        and float(value) >= float(gate["risk_expectancy_delta_not_below_r"])
        for value in expectancy_deltas
    )
    risk = bool(
        sample_ok
        and positive_expectancy_count == len(STAGE_ORDER)
        and risk_expectancy_ok
        and mae_improvements >= int(gate["risk_mae_improvement_periods_at_least"])
        and profit_factor_improvements
        >= int(gate["risk_profit_factor_improvement_periods_at_least"])
        and retention_ok
    )
    if alpha:
        label = "ALPHA_SUPPORT"
    elif risk:
        label = "RISK_QUALITY_SUPPORT"
    elif not sample_ok:
        label = "INCONCLUSIVE_SPARSE"
    elif len(STAGE_ORDER) - positive_expectancy_count >= int(
        gate["negative_expectancy_periods_at_least"]
    ):
        label = "NEGATIVE"
    else:
        label = "MIXED"
    return label, {
        "sample_floor_pass": sample_ok,
        "positive_expectancy_period_count": positive_expectancy_count,
        "alpha_expectancy_improvement_period_count": alpha_improvements,
        "profit_factor_improvement_period_count": profit_factor_improvements,
        "mfe_improvement_period_count": mfe_improvements,
        "mae_improvement_period_count": mae_improvements,
        "retention_pass": retention_ok,
        "development_bootstrap_pass": development_ci_ok,
        "risk_expectancy_pass": risk_expectancy_ok,
    }


def build_variant_decisions(
    rows: list[dict[str, Any]],
    variants: list[dict[str, Any]],
    experiment: dict[str, Any],
    prior_portfolio: pd.DataFrame,
) -> list[dict[str, Any]]:
    rows_by_key = {(str(row["stage"]), str(row["variant_id"])): row for row in rows}
    variant_by_id = {str(item["id"]): item for item in variants}
    id_by_components = {
        tuple(str(value) for value in item["component_ids"]): str(item["id"])
        for item in variants
        if item["variant_family"] == "FACTORIAL"
    }
    prior = {
        str(row.variant_id): bool(row.decision_shortlist)
        for row in prior_portfolio.itertuples(index=False)
    }
    combination_gate = experiment["combination_gate"]
    excluded = set(combination_gate["promotion_excluded_filter_ids"])
    decisions: list[dict[str, Any]] = []
    for variant_id, variant in variant_by_id.items():
        stage_rows = [rows_by_key[(stage, variant_id)] for stage in STAGE_ORDER]
        label, diagnostics = classify_variant(
            variant_id, stage_rows, experiment["classification_gates"]
        )
        components = [str(value) for value in variant["component_ids"]]
        leave_one_out: dict[str, int] = {}
        for component in components:
            parent_components = tuple(
                value for value in components if value != component
            )
            parent_id = id_by_components[parent_components]
            leave_one_out[component] = _count_positive(
                [
                    _metric_delta(
                        rows_by_key[(stage, variant_id)].get("expectancy_r"),
                        rows_by_key[(stage, parent_id)].get("expectancy_r"),
                    )
                    for stage in STAGE_ORDER
                ]
            )
        leave_one_out_support = bool(
            components
            and all(
                count
                >= int(
                    combination_gate[
                        "each_component_expectancy_improvement_periods_at_least"
                    ]
                )
                for count in leave_one_out.values()
            )
        )
        promotion_excluded = bool(excluded.intersection({variant_id, *components}))
        sequential_candidate = bool(
            variant["variant_family"] == "FACTORIAL"
            and 0 < len(components) <= int(combination_gate["maximum_component_count"])
            and label in combination_gate["accepted_labels"]
            and leave_one_out_support
            and not promotion_excluded
        )
        prior_support = prior.get(variant_id, False)
        decisions.append(
            {
                "variant_id": variant_id,
                "variant_family": variant["variant_family"],
                "component_count": len(components),
                "component_ids": json.dumps(components),
                "opportunity_label": label,
                **diagnostics,
                "leave_one_out_support": leave_one_out_support,
                "leave_one_out_details": json.dumps(leave_one_out, sort_keys=True),
                "promotion_excluded": promotion_excluded,
                "sequential_candidate": sequential_candidate,
                "prior_portfolio_shortlist": prior_support,
                "sequential_and_portfolio_support": bool(
                    sequential_candidate and prior_support
                ),
                **{
                    f"{stage}_{metric}": rows_by_key[(stage, variant_id)].get(metric)
                    for stage in STAGE_ORDER
                    for metric in (
                        "episode_count",
                        "episode_retention_vs_baseline_pct",
                        "expectancy_r",
                        "expectancy_r_delta_vs_baseline",
                        "expectancy_delta_month_block_95_low_r",
                        "expectancy_delta_month_block_95_high_r",
                        "profit_factor",
                        "average_mfe_r",
                        "average_mae_r",
                    )
                },
            }
        )
    return decisions


def individual_summary(
    decisions: list[dict[str, Any]],
    variants: list[dict[str, Any]],
    component_ids: list[str],
) -> list[dict[str, Any]]:
    by_id = {str(row["variant_id"]): row for row in decisions}
    ids = [_factorial_variant_id((component,)) for component in component_ids]
    ids += [
        str(item["id"])
        for item in variants
        if item["variant_family"] == "SUPPLEMENTAL_INDIVIDUAL"
    ]
    return [by_id[variant_id] for variant_id in ids]


def _signals_for_stage(
    all_signals: pd.DataFrame,
    period: dict[str, Any],
    blackout: EarningsBlackoutContext,
) -> tuple[pd.DataFrame, int]:
    dates = pd.to_datetime(all_signals["signal_date"])
    selected = all_signals[dates.between(*period["signal"])].copy()
    eligible, rejected = apply_earnings_blackout_to_signals(
        selected, blackout, blackout_calendar_days=10
    )
    return eligible, len(rejected)


def concentration_stage(
    *,
    stage: str,
    signals: pd.DataFrame,
    independent: dict[tuple[str, str], SimulatedTrade],
    histories: dict[str, pd.DataFrame],
    sessions: pd.DatetimeIndex,
    experiment: dict[str, Any],
    output_dir: Path,
) -> list[dict[str, Any]]:
    known_mask = signals["industry"].notna() & signals["industry"].astype(
        str
    ).str.strip().ne("")
    known = signals[known_mask].copy()
    trades = [
        independent[key]
        for key in zip(known["signal_date"], known["ticker"], strict=False)
        if key in independent
    ]
    industry_map = {
        (str(row.signal_date), str(row.ticker)): str(row.industry)
        for row in known[["signal_date", "ticker", "industry"]].itertuples(index=False)
    }
    specification = experiment["industry_concentration"]
    stage_dir = output_dir / "concentration" / stage
    stage_dir.mkdir(parents=True, exist_ok=True)
    output: list[dict[str, Any]] = []
    ledgers: dict[tuple[float, bool], pd.DataFrame] = {}
    for risk in specification["risk_per_trade_variants_r"]:
        for capped in (False, True):
            policy = {
                "type": "FIXED",
                "maximum_heat_r": float(specification["maximum_heat_r"]),
                "risk_per_trade_r": float(risk),
            }
            maximum_industry = (
                int(specification["maximum_positions_per_industry"])
                if capped
                else int(specification["maximum_positions"])
            )
            metrics, ledger, curve = simulate_portfolio_overlay(
                trades,
                histories,
                sessions,
                policy,
                starting_equity_r=100.0,
                maximum_positions=int(specification["maximum_positions"]),
                industry_by_signal_ticker=industry_map,
                maximum_positions_per_industry=maximum_industry,
            )
            variant_id = (
                f"fixed2r_{risk:g}r__industry_{'cap2' if capped else 'uncapped'}"
            )
            row = {
                **metrics,
                "stage": stage,
                "variant_id": variant_id,
                "risk_per_trade_r": float(risk),
                "industry_cap": 2 if capped else None,
                "known_industry_signal_count": len(known),
                "missing_industry_signal_count": len(signals) - len(known),
                "industry_coverage_pct": (
                    0.0 if signals.empty else len(known) / len(signals) * 100.0
                ),
            }
            safe = variant_id.replace(".", "_")
            ledger.to_csv(stage_dir / f"ledger__{safe}.csv", index=False)
            curve.to_csv(stage_dir / f"equity__{safe}.csv", index=False)
            output.append(row)
            ledgers[(float(risk), capped)] = ledger
    for risk in specification["risk_per_trade_variants_r"]:
        uncapped = ledgers[(float(risk), False)]
        capped = ledgers[(float(risk), True)]
        columns = ["signal_date", "ticker", "allocated_r", "portfolio_realised_r"]
        invariant = (
            uncapped[columns]
            .reset_index(drop=True)
            .equals(capped[columns].reset_index(drop=True))
        )
        for row in output:
            if float(row["risk_per_trade_r"]) == float(risk):
                row["cap_path_matches_uncapped"] = invariant
    return output


def _fmt(value: Any) -> str:
    if value is None or pd.isna(value):
        return "—"
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.3f}"
    return str(value)


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    return [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
        *("| " + " | ".join(_fmt(value) for value in row) + " |" for row in rows),
    ]


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    project_root = Path(__file__).resolve().parents[1]
    output_dir = ensure_research_output_path(project_root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    experiment_path = (
        project_root / "research/experiments/filter_edge_sequenced_v1.json"
    )
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    variant_path = project_root / str(experiment["variant_source"])
    variant_experiment = json.loads(variant_path.read_text(encoding="utf-8"))
    variants = generate_variants(variant_experiment)
    if len(variants) != int(experiment["variant_count"]):
        raise ValueError("variant source differs from sequenced preregistration")

    model_path = project_root / "research/config/model_0.json"
    model_config = load_model_0_config(model_path)
    histories, price_diagnostics = load_price_csv(args.prices)
    benchmarks, benchmark_diagnostics = load_price_csv(args.benchmark)
    if "SPY" not in benchmarks:
        raise ValueError("benchmark file must contain SPY")
    spy = benchmarks["SPY"].sort_index()
    sessions = pd.DatetimeIndex(spy.index).sort_values()
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
    sectors, industries = load_current_sector_industry(project_root)
    signals = enrich_market_features(signals, histories, spy, classifications=sectors)
    signals = enrich_leader_features(
        signals,
        histories,
        spy,
        sectors=sectors,
        industries=industries,
        minimum_industry_members=5,
    )
    signals = enrich_base_features(signals, histories)
    signals = enrich_spy_signal_trend(signals, spy)
    signals.to_csv(output_dir / "signal_features.csv", index=False)

    periods = experiment["periods"]
    blackout = load_verified_earnings_blackout_context(
        args.earnings,
        args.earnings_metadata,
        required_signal_start=periods[STAGE_ORDER[0]]["signal"][0],
        required_signal_end=periods[STAGE_ORDER[-1]]["signal"][1],
        blackout_calendar_days=10,
    )
    assumptions: ExecutionAssumptions = replace(
        execution_assumptions(model_config),
        target_r=None,
        maximum_holding_sessions=40,
    )
    rows: list[dict[str, Any]] = []
    episode_sets: dict[tuple[str, str], list[SimulatedTrade]] = {}
    stage_diagnostics: dict[str, Any] = {}
    concentration: list[dict[str, Any]] = []
    for stage in STAGE_ORDER:
        stage_signals, blackout_rejections = _signals_for_stage(
            signals, periods[stage], blackout
        )
        independent = _simulate_independent(
            stage_signals,
            histories,
            assumptions,
            str(periods[stage]["outcome_end"]),
        )
        stage_dir = output_dir / "opportunities" / stage
        stage_dir.mkdir(parents=True, exist_ok=True)
        for variant in variants:
            selected = stage_signals[
                variant_mask(stage_signals, variants, variant)
            ].copy()
            trades = [
                independent[key]
                for key in zip(
                    selected["signal_date"], selected["ticker"], strict=False
                )
                if key in independent
            ]
            episodes, overlap_rejections = select_nonoverlapping_ticker_episodes(trades)
            metrics = opportunity_metrics(
                episodes,
                selected_signal_count=len(selected),
                executable_trade_count=len(trades),
                overlap_rejection_count=overlap_rejections,
            )
            metrics.update(
                {
                    "stage": stage,
                    "variant_id": str(variant["id"]),
                    "variant_family": variant["variant_family"],
                    "component_count": len(variant["component_ids"]),
                    "component_ids": json.dumps(variant["component_ids"]),
                }
            )
            rows.append(metrics)
            episode_sets[(stage, str(variant["id"]))] = episodes
            safe = str(variant["id"]).replace(".", "_")
            pd.DataFrame([trade.to_dict() for trade in episodes]).to_csv(
                stage_dir / f"episodes__{safe}.csv", index=False
            )
        concentration.extend(
            concentration_stage(
                stage=stage,
                signals=stage_signals,
                independent=independent,
                histories=histories,
                sessions=sessions,
                experiment=experiment,
                output_dir=output_dir,
            )
        )
        stage_diagnostics[stage] = {
            "earnings_eligible_signal_count": len(stage_signals),
            "earnings_blackout_rejection_count": blackout_rejections,
            "independent_execution_count": len(independent),
            "missing_current_industry_signal_count": int(
                stage_signals["industry"].isna().sum()
            ),
        }
        print(f"Completed {stage}: {len(variants)} variants", flush=True)

    add_opportunity_deltas(rows, episode_sets, experiment)
    prior_path = (
        args.prior_portfolio_results
        if args.prior_portfolio_results.is_absolute()
        else project_root / args.prior_portfolio_results
    )
    prior_portfolio = pd.read_csv(prior_path)
    decisions = build_variant_decisions(rows, variants, experiment, prior_portfolio)
    component_ids = [
        str(item["id"]) for item in variant_experiment["factorial_components"]
    ]
    individual = individual_summary(decisions, variants, component_ids)
    supported = [row for row in decisions if row["sequential_and_portfolio_support"]]
    historical_decision = "HOLD" if supported else "REJECT"

    pd.DataFrame(rows).to_csv(output_dir / "all_opportunity_results.csv", index=False)
    pd.DataFrame(decisions).to_csv(output_dir / "variant_decisions.csv", index=False)
    pd.DataFrame(individual).to_csv(
        output_dir / "individual_filter_summary.csv", index=False
    )
    pd.DataFrame(concentration).to_csv(
        output_dir / "industry_concentration_results.csv", index=False
    )

    git_commit, git_dirty = git_state(project_root)
    payload = {
        "experiment": experiment,
        "execution_status": "COMPLETED_ADAPTIVE_DIAGNOSTIC_NO_UNTOUCHED_HOLDOUT",
        "historical_decision": historical_decision,
        "production_effect": "NONE",
        "untouched_holdout_evaluated": False,
        "preregistration_commit": experiment["preregistration_commit"],
        "run_git_commit": git_commit,
        "run_git_dirty": git_dirty,
        "reported_variant_count": len(variants),
        "sequential_and_portfolio_support_count": len(supported),
        "experiment_sha256": sha256_file(experiment_path),
        "variant_source_sha256": sha256_file(variant_path),
        "model_config_sha256": sha256_file(model_path),
        "price_sha256": sha256_file(args.prices),
        "benchmark_sha256": sha256_file(args.benchmark),
        "earnings_sha256": sha256_file(args.earnings),
        "prior_portfolio_sha256": sha256_file(prior_path),
        "price_diagnostics": price_diagnostics,
        "benchmark_diagnostics": benchmark_diagnostics,
        "earnings_blackout": blackout.provenance(),
        "stage_diagnostics": stage_diagnostics,
        "opportunity_results": rows,
        "variant_decisions": decisions,
        "individual_filter_summary": individual,
        "industry_concentration_results": concentration,
    }
    (output_dir / "results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )

    report = [
        "# FILTER_EDGE_SEQUENCED_V1",
        "",
        f"> **{experiment['research_label']}**",
        "",
        f"Historical decision: **{historical_decision}**",
        f"Sequential plus prior-portfolio support: {len(supported)}",
        "Production effect: **NONE**",
        "",
        "## Individual opportunity-level filters",
        "",
        *_table(
            ["Filter", "Label", "Dev N", "Dev Exp", "2024 Exp", "2025 Exp"],
            [
                [
                    row["variant_id"],
                    row["opportunity_label"],
                    row["development_2017_2023_episode_count"],
                    row["development_2017_2023_expectancy_r"],
                    row["reused_2024_expectancy_r"],
                    row["reused_2025_expectancy_r"],
                ]
                for row in individual
            ],
        ),
        "",
        "## Industry concentration",
        "",
        *_table(
            [
                "Stage",
                "Risk/trade",
                "Cap",
                "Trades",
                "Return %",
                "DD %",
                "Max industry",
                "Cap rejects",
                "Matches uncapped",
            ],
            [
                [
                    row["stage"],
                    row["risk_per_trade_r"],
                    row["industry_cap"],
                    row.get("accepted_trade_count"),
                    row.get("total_return_pct"),
                    row.get("maximum_drawdown_pct"),
                    row.get("maximum_same_industry_positions"),
                    row.get("rejection_reasons", {}).get("MAX_INDUSTRY_POSITIONS", 0),
                    row["cap_path_matches_uncapped"],
                ]
                for row in concentration
            ],
        ),
        "",
        "## Interpretation boundary",
        "",
        "Opportunity results are non-overlapping same-ticker cohorts, not an unlimited-capital portfolio. Every period is reused and contaminated. Industry comparisons exclude missing classifications from both sides and use current, not effective-dated, labels. Full losing and empty results remain in CSV/JSON artifacts.",
        "",
        "Production and the immutable forward journal are unchanged.",
    ]
    (output_dir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(
        f"Decision: {historical_decision}; sequential support: {len(supported)}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
