from __future__ import annotations

import numpy as np
import pandas as pd

import run_screener


def valid_close_history(rows: int = 140) -> pd.DataFrame:
    return pd.DataFrame({"Close": np.linspace(100.0, 140.0, rows)})


def test_period_returns_treat_missing_close_as_unavailable():
    malformed = pd.DataFrame({"Open": [100.0, 101.0, 102.0]})

    assert pd.isna(run_screener.period_return(malformed, 1))
    assert pd.isna(run_screener.period_return_as_of(malformed, 1))


def test_close_guard_removes_non_numeric_and_non_finite_values():
    history = pd.DataFrame({"Close": [100.0, "bad", np.inf, 104.0]})

    closes = run_screener.usable_close_prices(history)

    assert closes.tolist() == [100.0, 104.0]


def test_recent_rs_skips_symbol_with_missing_close_history():
    malformed = pd.DataFrame({"Open": np.linspace(100.0, 140.0, 140)})

    metrics = run_screener.calculate_recent_rs_metrics(
        {"BAD": malformed}, ["BAD"], valid_close_history()
    )

    assert metrics == {}


def test_recent_rs_handles_benchmark_with_missing_close_history():
    metrics = run_screener.calculate_recent_rs_metrics(
        {"GOOD": valid_close_history()},
        ["GOOD"],
        pd.DataFrame(index=range(140)),
    )

    assert metrics == {}
