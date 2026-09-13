from __future__ import annotations

import pandas as pd
import pytest

from research.engine.execution import (
    prepare_trade_execution,
    prepare_trade_executions,
    simulate_prepared_trade,
    simulate_trade,
)
from research.engine.models import ExecutionAssumptions, FeatureRecord


def signal(stop: float = 95.0) -> FeatureRecord:
    return FeatureRecord(
        signal_date="2026-01-02",
        ticker="AAA",
        universe_version="fixture",
        data_as_of="2026-01-02",
        price=100.0,
        volume=1_000_000.0,
        dollar_volume=100_000_000.0,
        average_volume_50d=1_000_000.0,
        valid_data=True,
        tradable=True,
        stage2_pass=True,
        structural_stop=stop,
        model_0_signal=True,
    )


def bars(rows: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [row[1] for row in rows],
            "High": [row[2] for row in rows],
            "Low": [row[3] for row in rows],
            "Close": [row[4] for row in rows],
            "Volume": 1_000_000.0,
        },
        index=pd.to_datetime([row[0] for row in rows]),
    )


def assumptions(**updates) -> ExecutionAssumptions:
    values = {
        "entry_slippage_bps": 0.0,
        "exit_slippage_bps": 0.0,
        "commission_per_share": 0.0,
        "maximum_holding_sessions": 40,
    }
    values.update(updates)
    return ExecutionAssumptions(**values)


def test_next_session_execution() -> None:
    history = bars(
        [
            ("2026-01-02", 90, 101, 89, 100),
            ("2026-01-05", 102, 103, 100, 101),
        ]
    )
    trade = simulate_trade(signal(), history, assumptions(maximum_holding_sessions=1))
    assert trade is not None
    assert trade.entry_date == "2026-01-05"
    assert trade.entry == 102.0


def test_stop_gap_through_fills_at_open() -> None:
    history = bars(
        [
            ("2026-01-02", 99, 101, 98, 100),
            ("2026-01-05", 100, 104, 97, 102),
            ("2026-01-06", 90, 92, 88, 89),
        ]
    )
    trade = simulate_trade(signal(), history, assumptions())
    assert trade is not None
    assert trade.exit_reason == "STOP_GAP"
    assert trade.exit == 90.0


def test_target_gap_through_uses_conservative_level_fill() -> None:
    history = bars(
        [
            ("2026-01-02", 99, 101, 98, 100),
            ("2026-01-05", 100, 105, 97, 102),
            ("2026-01-06", 112, 114, 111, 113),
        ]
    )
    trade = simulate_trade(signal(), history, assumptions(), target_price=110.0)
    assert trade is not None
    assert trade.exit_reason == "TARGET_GAP"
    assert trade.exit == 110.0


def test_same_bar_stop_target_is_conservative() -> None:
    history = bars(
        [
            ("2026-01-02", 99, 101, 98, 100),
            ("2026-01-05", 100, 111, 94, 105),
        ]
    )
    trade = simulate_trade(signal(), history, assumptions(), target_price=110.0)
    assert trade is not None
    assert trade.exit_reason == "STOP_AND_TARGET_SAME_BAR_CONSERVATIVE"
    assert trade.exit == 95.0


def test_r_calculation_for_two_r_target() -> None:
    history = bars(
        [
            ("2026-01-02", 99, 101, 98, 100),
            ("2026-01-05", 100, 110, 96, 110),
        ]
    )
    trade = simulate_trade(signal(), history, assumptions(), target_price=110.0)
    assert trade is not None
    assert trade.realised_r == pytest.approx(2.0)
    assert trade.shares == 117


def test_explicit_research_stop_overrides_structural_stop() -> None:
    history = bars(
        [
            ("2026-01-02", 99, 101, 98, 100),
            ("2026-01-05", 100, 104, 97, 103),
        ]
    )
    trade = simulate_trade(
        signal(stop=95.0),
        history,
        assumptions(maximum_holding_sessions=1),
        stop_price=98.0,
    )
    assert trade is not None
    assert trade.initial_stop == 98.0
    assert trade.exit_reason == "STOP"
    assert trade.realised_r == -1.0


def test_prepared_execution_matches_single_trade_path() -> None:
    history = bars(
        [
            ("2026-01-02", 99, 101, 98, 100),
            ("2026-01-05", 100, 105, 97, 102),
            ("2026-01-06", 102, 111, 101, 110),
        ]
    )
    settings = assumptions(target_r=2.0)
    expected = simulate_trade(signal(), history, settings)
    prepared = prepare_trade_execution(signal(), history, settings)
    assert prepared is not None
    actual = simulate_prepared_trade(prepared, settings)
    assert actual == expected


def test_long_preparation_can_run_a_shorter_time_exit() -> None:
    history = bars(
        [
            ("2026-01-02", 99, 101, 98, 100),
            ("2026-01-05", 100, 105, 97, 102),
            ("2026-01-06", 102, 111, 101, 110),
        ]
    )
    long_settings = assumptions(maximum_holding_sessions=2)
    short_settings = assumptions(maximum_holding_sessions=1)
    prepared = prepare_trade_execution(signal(), history, long_settings)
    assert prepared is not None
    actual = simulate_prepared_trade(prepared, short_settings)
    expected = simulate_trade(signal(), history, short_settings)
    assert actual == expected


def test_prepared_execution_rejects_a_longer_requested_time_exit() -> None:
    history = bars(
        [
            ("2026-01-02", 99, 101, 98, 100),
            ("2026-01-05", 100, 105, 97, 102),
        ]
    )
    prepared = prepare_trade_execution(
        signal(), history, assumptions(maximum_holding_sessions=1)
    )
    assert prepared is not None
    with pytest.raises(ValueError, match="exceeds prepared"):
        simulate_prepared_trade(prepared, assumptions(maximum_holding_sessions=2))


def test_batch_preparation_matches_single_preparation() -> None:
    history = bars(
        [
            ("2026-01-02", 99, 101, 98, 100),
            ("2026-01-05", 100, 105, 97, 102),
        ]
    )
    settings = assumptions(maximum_holding_sessions=1)
    single = prepare_trade_execution(signal(), history, settings)
    batch = prepare_trade_executions([signal()], {"AAA": history}, settings)
    assert single is not None
    assert len(batch) == 1
    assert batch[0].entry == single.entry
    assert batch[0].dates.equals(single.dates)
    assert batch[0].opens.tolist() == single.opens.tolist()


def test_mfe_and_mae_calculation() -> None:
    history = bars(
        [
            ("2026-01-02", 99, 101, 98, 100),
            ("2026-01-05", 100, 105, 97, 102),
        ]
    )
    trade = simulate_trade(signal(), history, assumptions(maximum_holding_sessions=1))
    assert trade is not None
    assert trade.MFE_R == pytest.approx(1.0)
    assert trade.MAE_R == pytest.approx(-0.6)


def test_unsupported_favourable_same_bar_policy_is_rejected() -> None:
    history = bars([("2026-01-05", 100, 105, 97, 102)])
    with pytest.raises(ValueError, match="STOP_FIRST"):
        simulate_trade(signal(), history, assumptions(same_bar_policy="TARGET_FIRST"))
