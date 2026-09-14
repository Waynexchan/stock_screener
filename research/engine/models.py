"""Typed records shared by the research engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ExecutionAssumptions:
    """Conservative, explicit defaults for research simulations."""

    standard_r_dollars: float = 587.0
    entry_slippage_bps: float = 5.0
    exit_slippage_bps: float = 5.0
    commission_per_share: float = 0.0
    target_r: float | None = None
    maximum_holding_sessions: int = 40
    stop_lookback_sessions: int = 20
    maximum_positions: int = 4
    same_bar_policy: str = "STOP_FIRST"
    favorable_gap_fill: str = "LEVEL"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MovingAverageTrailingStop:
    """Causal profit-protection stop evaluated from prior-session indicators."""

    activation_r: float
    moving_average_sessions: int = 20
    atr_sessions: int = 20
    atr_offset: float = 0.0


@dataclass(frozen=True)
class FeatureRecord:
    """Information observable at or before the signal date only."""

    signal_date: str
    ticker: str
    universe_version: str
    data_as_of: str
    price: float
    volume: float
    dollar_volume: float
    average_volume_50d: float
    valid_data: bool
    tradable: bool
    stage2_pass: bool
    structural_stop: float | None
    model_0_signal: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OutcomeRecord:
    """Forward-looking labels kept structurally separate from features."""

    signal_date: str
    ticker: str
    entry_date: str | None
    future_5d_return: float | None
    future_10d_return: float | None
    future_20d_return: float | None
    future_40d_return: float | None
    future_5d_mfe: float | None
    future_10d_mfe: float | None
    future_20d_mfe: float | None
    future_40d_mfe: float | None
    future_5d_mae: float | None
    future_10d_mae: float | None
    future_20d_mae: float | None
    future_40d_mae: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SimulatedTrade:
    """One normalized initial-risk trade outcome."""

    signal_date: str
    ticker: str
    entry_date: str
    exit_date: str
    entry: float
    initial_stop: float
    target: float | None
    initial_risk_per_share: float
    shares: int
    exit: float
    gross_pnl: float
    costs: float
    net_pnl: float
    realised_r: float
    MFE_R: float
    MAE_R: float
    holding_days: int
    exit_reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
