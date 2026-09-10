from __future__ import annotations

import pandas as pd
import pytest

from research.engine.data import (
    adjust_ohlcv,
    audit_repository_data,
    normalise_price_frame,
)
from research.engine.features import (
    MODEL_0_EXCLUDED_ALPHA_FEATURES,
    assert_feature_columns_safe,
    feature_at_date,
)
from research.engine.outcomes import calculate_forward_outcomes, next_available_session


def rising_history(periods: int = 260) -> pd.DataFrame:
    index = pd.bdate_range("2025-01-02", periods=periods)
    close = pd.Series(
        [20 + position * 0.15 for position in range(periods)], index=index
    )
    return pd.DataFrame(
        {
            "Open": close - 0.05,
            "High": close + 0.40,
            "Low": close - 0.40,
            "Close": close,
            "Volume": 1_000_000.0,
        },
        index=index,
    )


def test_no_future_bar_visible_during_feature_calculation() -> None:
    history = rising_history()
    cutoff = history.index[229]
    before = feature_at_date("AAA", history, cutoff, "fixture")
    changed = history.copy()
    changed.loc[changed.index > cutoff, ["Open", "High", "Low", "Close"]] = 9_999.0
    after = feature_at_date("AAA", changed, cutoff, "fixture")
    assert before == after
    assert before.data_as_of == cutoff.date().isoformat()


def test_outcomes_are_structurally_forbidden_as_features() -> None:
    with pytest.raises(ValueError, match="outcome columns"):
        assert_feature_columns_safe(["Close", "future_20d_return"])


def test_missing_historical_data_is_non_actionable() -> None:
    history = rising_history(30)
    feature = feature_at_date("AAA", history, history.index[-1], "fixture")
    assert not feature.valid_data
    assert not feature.tradable
    assert not feature.stage2_pass
    assert feature.structural_stop is None


def test_invalid_bar_inside_required_history_is_non_actionable() -> None:
    history = rising_history()
    history.loc[history.index[-10], "High"] = history.loc[history.index[-10], "Low"] - 1
    feature = feature_at_date("AAA", history, history.index[-1], "fixture")
    assert not feature.valid_data
    assert not feature.model_0_signal


def test_split_adjusted_data_handling() -> None:
    raw = pd.DataFrame(
        {
            "Open": [100.0, 50.0],
            "High": [102.0, 51.0],
            "Low": [98.0, 49.0],
            "Close": [100.0, 50.0],
            "Adj Close": [50.0, 50.0],
            "Volume": [1_000.0, 2_000.0],
        }
    )
    adjusted, method = adjust_ohlcv(raw)
    assert method == "ADJ_CLOSE_RATIO"
    assert adjusted["Close"].tolist() == [50.0, 50.0]
    assert adjusted["Volume"].tolist() == [2_000.0, 2_000.0]


def test_price_loader_reports_missing_frequency() -> None:
    raw = pd.DataFrame(
        {
            "Date": ["2026-01-02", "2026-01-05"],
            "Ticker": ["AAA", "AAA"],
            "Open": [10.0, None],
            "High": [11.0, 11.0],
            "Low": [9.0, 9.0],
            "Close": [10.5, 10.5],
            "Volume": [1_000.0, 1_000.0],
        }
    )
    _, diagnostics = normalise_price_frame(raw)
    assert diagnostics["invalid_or_missing_bar_count"] == 1
    assert diagnostics["missing_or_invalid_bar_frequency"] == 0.5


def test_weekend_uses_next_available_session() -> None:
    history = pd.DataFrame(index=pd.to_datetime(["2026-01-09", "2026-01-12"]))
    assert next_available_session(history, "2026-01-09") == pd.Timestamp("2026-01-12")


def test_market_holiday_uses_next_available_session() -> None:
    history = pd.DataFrame(index=pd.to_datetime(["2026-07-02", "2026-07-06"]))
    assert next_available_session(history, "2026-07-02") == pd.Timestamp("2026-07-06")


def test_forward_outcomes_start_at_next_session() -> None:
    history = rising_history()
    cutoff = history.index[220]
    feature = feature_at_date("AAA", history, cutoff, "fixture")
    outcome = calculate_forward_outcomes(feature, history)
    assert outcome.entry_date == history.index[221].date().isoformat()
    assert not hasattr(feature, "future_5d_return")


def test_baseline_excludes_alpha_filters() -> None:
    expected = {
        "Recent RS",
        "VCP Quality",
        "Pullback Quality",
        "Complex Setup Scoring",
        "Candidate Final Score",
        "AI Commentary",
    }
    assert expected.issubset(set(MODEL_0_EXCLUDED_ALPHA_FEATURES))


def test_baseline_excludes_industry_and_sister_filters() -> None:
    assert "Industry Qualification" in MODEL_0_EXCLUDED_ALPHA_FEATURES
    assert "Sister-Stock Confirmation" in MODEL_0_EXCLUDED_ALPHA_FEATURES


def test_default_repository_audit_blocks_untrustworthy_backtest(tmp_path) -> None:
    readiness = audit_repository_data(tmp_path)
    assert readiness["overall_status"] == "NOT_READY"
    assert readiness["research_label"] == "SURVIVORSHIP-BIASED RESEARCH"
    assert readiness["items"]["delisted_stocks"]["status"] == "NOT_READY"
