from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.engine.features import generate_model_0_features
from research.engine.superperformance_features import (
    enrich_superperformance_ranks,
    generate_superperformance_path_features,
)
from research.run_superperformance_paths import PATH_COLUMN_ALIASES, _priority_map


def _history(periods: int, growth: float = 1.001) -> pd.DataFrame:
    dates = pd.bdate_range("2023-01-03", periods=periods)
    close = 20 * growth ** np.arange(periods)
    frame = pd.DataFrame(
        {
            "Open": close * 0.995,
            "High": close * 1.002,
            "Low": close * 0.99,
            "Close": close,
            "Volume": np.full(periods, 1_000_000.0),
        },
        index=dates,
    )
    frame.iloc[-1, frame.columns.get_loc("Volume")] = 2_000_000.0
    return frame


def test_preregistered_superperformance_matrix_is_frozen() -> None:
    root = Path(__file__).resolve().parents[2]
    experiment = json.loads(
        (root / "research/experiments/superperformance_paths_v1.json").read_text(
            encoding="utf-8"
        )
    )
    ids = [item["id"] for item in experiment["variants"]]
    assert len(ids) == experiment["variant_count"] == 18
    assert len(ids) == len(set(ids))
    assert ids[0] == "baseline"
    assert ids[-1] == "multi_path_ranked_2r_sma20_minus_1atr"
    assert PATH_COLUMN_ALIASES[experiment["variants"][0]["path"]] == "model_0_path"


def test_mature_blue_sky_breakout_is_causal_and_not_observed_resistance() -> None:
    history = _history(320)
    breakout_close = float(history["Close"].iloc[-2]) * 1.03
    history.iloc[-1, history.columns.get_loc("Open")] = breakout_close * 0.995
    history.iloc[-1, history.columns.get_loc("High")] = breakout_close * 1.002
    history.iloc[-1, history.columns.get_loc("Low")] = breakout_close * 0.99
    history.iloc[-1, history.columns.get_loc("Close")] = breakout_close
    signal_date = history.index[-1].date().isoformat()
    before = generate_superperformance_path_features(
        {"AAA": history}, "test"
    ).set_index(["signal_date", "ticker"])
    row = before.loc[(signal_date, "AAA")]
    assert bool(row["mature_breakout"])
    assert bool(row["mature_breakout_blue_sky"])
    assert not bool(row["mature_breakout_observed_2r"])

    future_date = history.index[-1] + pd.offsets.BDay(1)
    future = pd.DataFrame(
        {
            "Open": [1.0],
            "High": [100_000.0],
            "Low": [0.01],
            "Close": [50_000.0],
            "Volume": [100_000_000.0],
        },
        index=[future_date],
    )
    after = generate_superperformance_path_features(
        {"AAA": pd.concat([history, future])}, "test"
    ).set_index(["signal_date", "ticker"])
    for column in before.columns:
        left = before.at[(signal_date, "AAA"), column]
        right = after.at[(signal_date, "AAA"), column]
        if pd.isna(left):
            assert pd.isna(right)
        else:
            assert right == left


def test_young_leader_path_does_not_require_ma200() -> None:
    history = _history(150, growth=1.003)
    signal_date = history.index[-1].date().isoformat()
    rows = generate_superperformance_path_features({"IPO": history}, "test")
    row = rows.set_index(["signal_date", "ticker"]).loc[(signal_date, "IPO")]
    assert row["history_age_sessions"] == 150
    assert bool(row["young_leader_breakout"])
    assert not bool(row["stage2_pass"])


def test_model_0_path_keys_match_canonical_research_feature_generator() -> None:
    histories = {
        "AAA": _history(320, growth=1.002),
        "BBB": _history(340, growth=1.0015),
    }
    expected = generate_model_0_features(
        histories,
        "test",
        minimum_history_sessions=220,
        stop_lookback_sessions=20,
        signals_only=True,
    )
    actual = generate_superperformance_path_features(histories, "test")
    actual = actual[actual["model_0_path"]]
    expected_keys = set(zip(expected["signal_date"], expected["ticker"], strict=False))
    actual_keys = set(zip(actual["signal_date"], actual["ticker"], strict=False))
    assert actual_keys == expected_keys


def test_superperformance_rank_and_priority_are_descending() -> None:
    dates = pd.bdate_range("2024-01-02", periods=300)
    histories = {
        "SLOW": pd.DataFrame({"Close": 20 * 1.0005 ** np.arange(300)}, index=dates),
        "FAST": pd.DataFrame({"Close": 20 * 1.002 ** np.arange(300)}, index=dates),
    }
    signal_date = dates[-1].date().isoformat()
    signals = pd.DataFrame(
        [
            {
                "signal_date": signal_date,
                "ticker": ticker,
                "recent_rs_score": 80.0,
                "long_term_rs_score": 80.0,
                "marketsmith_proxy_score": score,
                "young_leader_breakout": False,
                "quality_breakout": True,
                "tight_base_breakout": False,
                "constructive_pullback": False,
                "volume_ratio_path": 1.5,
                "close_location_pct_path": 80.0,
                "prior_range_10d_pct_path": 8.0,
                "blue_sky_breakout": False,
            }
            for ticker, score in (("SLOW", 70.0), ("FAST", 95.0))
        ]
    )
    spy = pd.DataFrame({"Close": 100 * 1.0002 ** np.arange(300)}, index=dates)
    ranked = enrich_superperformance_ranks(signals, histories, spy).set_index("ticker")
    assert (
        ranked.at["FAST", "superperformance_rank_score"]
        > ranked.at["SLOW", "superperformance_rank_score"]
    )
    priorities = _priority_map(ranked.reset_index(), "SUPERPERFORMANCE")
    assert priorities is not None
    assert priorities[(signal_date, "FAST")] < priorities[(signal_date, "SLOW")]


def test_missing_rank_components_receive_zero_and_are_counted() -> None:
    dates = pd.bdate_range("2024-01-02", periods=100)
    histories = {"AAA": pd.DataFrame({"Close": np.linspace(20, 30, 100)}, index=dates)}
    signal_date = dates[-1].date().isoformat()
    signals = pd.DataFrame(
        [
            {
                "signal_date": signal_date,
                "ticker": "AAA",
                "recent_rs_score": np.nan,
                "long_term_rs_score": np.nan,
                "marketsmith_proxy_score": np.nan,
                "young_leader_breakout": False,
                "quality_breakout": True,
                "tight_base_breakout": False,
                "constructive_pullback": False,
                "volume_ratio_path": np.nan,
                "close_location_pct_path": np.nan,
                "prior_range_10d_pct_path": np.nan,
                "blue_sky_breakout": False,
            }
        ]
    )
    spy = pd.DataFrame({"Close": np.linspace(100, 110, 100)}, index=dates)
    row = enrich_superperformance_ranks(signals, histories, spy).iloc[0]
    assert row["ranking_missing_component_count"] == 4
    assert row["superperformance_rank_score"] == 0
