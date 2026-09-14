"""Causal mechanical entry paths for superperformance research."""

from __future__ import annotations

import numpy as np
import pandas as pd

from run_screener import add_indicators

from .data import valid_bar_mask


PATH_COLUMNS = (
    "model_0_path",
    "mature_breakout",
    "mature_breakout_observed_2r",
    "mature_breakout_blue_sky",
    "mature_breakout_observed_or_blue_sky",
    "quality_breakout",
    "quality_breakout_production_rs",
    "tight_base_breakout",
    "constructive_pullback",
    "young_leader_breakout",
    "young_leader_breakout_rs80",
    "multi_path_union",
    "multi_path_production_rs",
)


def _numeric(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy().sort_index()
    result.index = pd.to_datetime(result.index)
    for column in ("Open", "High", "Low", "Close", "Volume"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def _signal_frame(
    ticker: str,
    history: pd.DataFrame,
    universe_version: str,
    *,
    min_price: float,
    min_average_volume: float,
) -> pd.DataFrame:
    frame = _numeric(history)
    indicators = add_indicators(frame)
    valid = valid_bar_mask(frame)
    valid_220 = valid.astype(int).rolling(220, min_periods=220).sum().eq(220)
    valid_90 = valid.astype(int).rolling(90, min_periods=90).sum().eq(90)
    age = valid.astype(int).cumsum()

    close = pd.to_numeric(indicators["Close"], errors="coerce")
    open_price = pd.to_numeric(indicators["Open"], errors="coerce")
    high = pd.to_numeric(indicators["High"], errors="coerce")
    low = pd.to_numeric(indicators["Low"], errors="coerce")
    volume = pd.to_numeric(indicators["Volume"], errors="coerce")
    average_volume = pd.to_numeric(indicators["AVG_VOLUME50"], errors="coerce")
    ma50 = pd.to_numeric(indicators["MA50"], errors="coerce")
    ma150 = pd.to_numeric(indicators["MA150"], errors="coerce")
    ma200 = pd.to_numeric(indicators["MA200"], errors="coerce")
    ma200_prior = pd.to_numeric(indicators["MA200_20D_AGO"], errors="coerce")
    ema10 = pd.to_numeric(indicators["EMA10"], errors="coerce")
    ema20 = pd.to_numeric(indicators["EMA20"], errors="coerce")
    atr20 = pd.to_numeric(indicators["ATR20"], errors="coerce")
    volume_ratio = pd.to_numeric(indicators["VOLUME_RATIO"], errors="coerce")
    close_location = pd.to_numeric(indicators["CLOSE_POSITION_PCT"], errors="coerce")
    body_pct = pd.to_numeric(indicators["BODY_PCT"], errors="coerce")

    finite_mature = (
        pd.concat(
            [close, volume, average_volume, ma50, ma150, ma200, ma200_prior], axis=1
        )
        .notna()
        .all(axis=1)
    )
    tradable = valid & close.ge(min_price) & average_volume.ge(min_average_volume)
    stage2 = (
        valid_220
        & finite_mature
        & close.gt(ma50)
        & ma50.gt(ma150)
        & ma150.gt(ma200)
        & ma200.gt(ma200_prior)
    )
    stop_20 = low.rolling(20, min_periods=20).min()
    stop_20 = stop_20.where(np.isfinite(stop_20) & stop_20.lt(close))
    model_0_eligible = tradable & stage2 & stop_20.notna()
    model_0_path = model_0_eligible & ~model_0_eligible.shift(1, fill_value=False)

    prior_50_high = high.shift(1).rolling(50, min_periods=50).max()
    prior_252_high = high.shift(1).rolling(252, min_periods=252).max()
    distance_50_pct = (close - ma50).div(ma50) * 100
    distance_150_pct = (close - ma150).div(ma150) * 100
    controlled_extension = distance_50_pct.le(8) | distance_150_pct.le(15)
    mature_breakout = (
        model_0_eligible
        & close.gt(prior_50_high)
        & close.gt(open_price)
        & body_pct.ge(25)
        & close_location.ge(60)
        & volume_ratio.ge(0.9)
        & controlled_extension
    )
    signal_risk = close - stop_20
    observed_2r = (
        prior_252_high.notna()
        & signal_risk.gt(0)
        & prior_252_high.ge(close + 2 * signal_risk)
    )
    blue_sky = prior_252_high.notna() & close.gt(prior_252_high)
    quality_breakout = mature_breakout & volume_ratio.ge(1.5) & close_location.ge(75)

    prior_10_high = high.shift(1).rolling(10, min_periods=10).max()
    prior_10_low = low.shift(1).rolling(10, min_periods=10).min()
    prior_range_10_pct = (prior_10_high - prior_10_low).div(close.shift(1)) * 100
    adr20 = pd.to_numeric(indicators["ADR_PCT"], errors="coerce")
    adr60 = pd.to_numeric(indicators["ADR60_PCT"], errors="coerce")
    prior_adr_ratio = adr20.shift(1).div(adr60.shift(1).where(adr60.shift(1).gt(0)))
    prior_volume_10 = volume.shift(1).rolling(10, min_periods=10).mean()
    older_volume_40 = volume.shift(11).rolling(40, min_periods=40).mean()
    prior_volume_dryup = prior_volume_10.div(
        older_volume_40.where(older_volume_40.gt(0))
    )
    tight_base_breakout = (
        quality_breakout
        & prior_range_10_pct.le(8)
        & prior_adr_ratio.le(0.8)
        & prior_volume_dryup.le(0.8)
    )

    dist_ema10_atr = (close - ema10).abs().div(atr20)
    dist_ema20_atr = (close - ema20).abs().div(atr20)
    dist_ma50_atr = (close - ma50).abs().div(atr20)
    dist_ma150_atr = (close - ma150).abs().div(atr20)
    near_support = (
        (close.ge(ema10) & dist_ema10_atr.le(1.0))
        | (close.ge(ema20) & dist_ema20_atr.le(1.5))
        | (close.ge(ma50) & dist_ma50_atr.le(2.0))
    )
    ab_pullback = dist_ma50_atr.le(3) & dist_ma150_atr.le(7)
    reversal = indicators["BULLISH_REVERSAL_CANDLE"].fillna(False).astype(bool)
    pullback_state = (
        model_0_eligible & near_support & ab_pullback & volume_ratio.le(1.5) & reversal
    )
    constructive_pullback = pullback_state & ~pullback_state.shift(1, fill_value=False)

    prior_20_high = high.shift(1).rolling(20, min_periods=20).max()
    available_high = high.shift(1).rolling(126, min_periods=60).max()
    young_trend = (
        valid_90
        & age.between(90, 219)
        & tradable
        & close.gt(ema10)
        & ema10.gt(ema20)
        & ema20.gt(ma50)
        & ma50.gt(ma50.shift(20))
        & ((available_high - close).div(available_high) * 100).le(15)
    )
    young_leader_breakout = (
        young_trend
        & close.gt(prior_20_high)
        & volume_ratio.ge(1.5)
        & close_location.ge(75)
        & stop_20.notna()
    )

    any_signal = (
        model_0_path
        | mature_breakout
        | quality_breakout
        | tight_base_breakout
        | constructive_pullback
        | young_leader_breakout
    )
    result = pd.DataFrame(
        {
            "signal_date": frame.index.date.astype(str),
            "ticker": ticker.upper(),
            "universe_version": universe_version,
            "data_as_of": frame.index.date.astype(str),
            "price": close,
            "volume": volume,
            "dollar_volume": close * volume,
            "average_volume_50d": average_volume,
            "valid_data": valid,
            "tradable": tradable,
            "stage2_pass": stage2,
            "structural_stop": stop_20,
            "model_0_signal": model_0_path,
            "history_age_sessions": age,
            "volume_ratio_path": volume_ratio,
            "close_location_pct_path": close_location,
            "body_pct_path": body_pct,
            "prior_range_10d_pct_path": prior_range_10_pct,
            "prior_adr20_to_adr60_path": prior_adr_ratio,
            "prior_volume_10_to_40_path": prior_volume_dryup,
            "observed_2r_resistance": observed_2r,
            "blue_sky_breakout": blue_sky,
            "model_0_path": model_0_path,
            "mature_breakout": mature_breakout,
            "mature_breakout_observed_2r": mature_breakout & observed_2r,
            "mature_breakout_blue_sky": mature_breakout & blue_sky,
            "mature_breakout_observed_or_blue_sky": mature_breakout
            & (observed_2r | blue_sky),
            "quality_breakout": quality_breakout,
            "tight_base_breakout": tight_base_breakout,
            "constructive_pullback": constructive_pullback,
            "young_leader_breakout": young_leader_breakout,
        },
        index=frame.index,
    )
    return result.loc[any_signal].reset_index(drop=True)


def generate_superperformance_path_features(
    histories: dict[str, pd.DataFrame],
    universe_version: str,
    *,
    min_price: float = 10.0,
    min_average_volume: float = 500_000.0,
) -> pd.DataFrame:
    """Generate unique causal path candidates from the entire price archive."""

    frames = [
        _signal_frame(
            ticker,
            histories[ticker],
            universe_version,
            min_price=min_price,
            min_average_volume=min_average_volume,
        )
        for ticker in sorted(histories)
    ]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame()
    result = pd.concat(frames, ignore_index=True)
    if result.duplicated(["signal_date", "ticker"]).any():
        raise AssertionError("superperformance signal keys are not unique")
    return result.sort_values(["signal_date", "ticker"]).reset_index(drop=True)


def _close_panel(histories: dict[str, pd.DataFrame]) -> pd.DataFrame:
    panel = pd.concat(
        {
            ticker: pd.to_numeric(frame["Close"], errors="coerce")
            for ticker, frame in histories.items()
            if "Close" in frame
        },
        axis=1,
    ).sort_index()
    panel.index = pd.to_datetime(panel.index)
    return panel


def _score_1_to_99(raw: pd.DataFrame) -> pd.DataFrame:
    return np.ceil(raw.rank(axis=1, pct=True, method="average") * 99).clip(1, 99)


def _lookup(panel: pd.DataFrame, signals: pd.DataFrame) -> list[float]:
    values: list[float] = []
    for row in signals[["signal_date", "ticker"]].itertuples(index=False):
        date = pd.Timestamp(row.signal_date)
        value = (
            panel.at[date, row.ticker]
            if date in panel.index and row.ticker in panel.columns
            else np.nan
        )
        values.append(float(value) if pd.notna(value) else np.nan)
    return values


def enrich_superperformance_ranks(
    signals: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    benchmark: pd.DataFrame,
) -> pd.DataFrame:
    """Add frozen RS gates and candidate-order scores without future data."""

    result = signals.copy()
    if result.empty:
        return result
    closes = _close_panel(histories)
    young_raw = 0.60 * (closes.div(closes.shift(63)) - 1) + 0.40 * (
        closes.div(closes.shift(20)) - 1
    )
    young_score = _score_1_to_99(young_raw)
    spy = pd.to_numeric(benchmark["Close"], errors="coerce").sort_index()
    spy.index = pd.to_datetime(spy.index)
    rel_5 = ((closes.div(closes.shift(5)) - 1) * 100).sub(
        ((spy.div(spy.shift(5)) - 1) * 100).reindex(closes.index), axis=0
    )
    rel_20 = ((closes.div(closes.shift(20)) - 1) * 100).sub(
        ((spy.div(spy.shift(20)) - 1) * 100).reindex(closes.index), axis=0
    )
    result["young_rs_score"] = _lookup(young_score, result)
    result["relative_return_5d_path"] = _lookup(rel_5, result)
    result["relative_return_20d_path"] = _lookup(rel_20, result)
    result["recent_rs_acceleration_path"] = result["relative_return_5d_path"] - (
        result["relative_return_20d_path"] / 4
    )

    recent = pd.to_numeric(result.get("recent_rs_score"), errors="coerce")
    long_term = pd.to_numeric(result.get("long_term_rs_score"), errors="coerce")
    acceleration = pd.to_numeric(result["recent_rs_acceleration_path"], errors="coerce")
    rel20 = pd.to_numeric(result["relative_return_20d_path"], errors="coerce")
    complete = recent.notna() & acceleration.notna() & rel20.notna()
    labels = np.select(
        [
            complete & recent.ge(80) & acceleration.ge(0.02) & rel20.gt(0),
            complete & recent.ge(60) & acceleration.gt(0),
            complete & long_term.ge(80) & recent.ge(70) & acceleration.abs().lt(0.02),
            complete & long_term.ge(75) & (rel20.le(0) | acceleration.lt(0)),
            complete & recent.lt(40) & rel20.lt(0),
        ],
        ["Emerging Leader", "Improving", "Stable Leader", "Weakening", "Lagging"],
        default="Stable",
    )
    result["production_rs_trend_path"] = labels
    result.loc[~complete, "production_rs_trend_path"] = "Unknown"
    acceptable = result["production_rs_trend_path"].isin(
        ["Emerging Leader", "Improving", "Stable Leader", "Stable"]
    )
    result["production_rs_gate"] = (
        recent.ge(60)
        & acceptable
        & (
            recent.ge(70)
            | result["production_rs_trend_path"].isin(["Emerging Leader", "Improving"])
        )
    )
    young = result["young_leader_breakout"].fillna(False).astype(bool)
    result["applicable_rs_score"] = pd.to_numeric(
        result.get("marketsmith_proxy_score"), errors="coerce"
    ).where(~young, pd.to_numeric(result["young_rs_score"], errors="coerce"))
    result["pathway_rs_gate"] = result["production_rs_gate"].where(
        ~young, pd.to_numeric(result["young_rs_score"], errors="coerce").ge(80)
    )
    result["quality_breakout_production_rs"] = result["quality_breakout"].fillna(
        False
    ).astype(bool) & result["production_rs_gate"].fillna(False).astype(bool)
    result["young_leader_breakout_rs80"] = young & pd.to_numeric(
        result["young_rs_score"], errors="coerce"
    ).ge(80)
    result["multi_path_union"] = (
        result[
            [
                "quality_breakout",
                "tight_base_breakout",
                "constructive_pullback",
                "young_leader_breakout",
            ]
        ]
        .fillna(False)
        .any(axis=1)
    )
    result["multi_path_production_rs"] = result["multi_path_union"] & result[
        "pathway_rs_gate"
    ].fillna(False).astype(bool)

    volume_quality = (
        pd.to_numeric(result["volume_ratio_path"], errors="coerce")
        .div(2)
        .mul(100)
        .clip(0, 100)
    )
    close_quality = pd.to_numeric(
        result["close_location_pct_path"], errors="coerce"
    ).clip(0, 100)
    range_quality = (
        100 - 5 * pd.to_numeric(result["prior_range_10d_pct_path"], errors="coerce")
    ).clip(0, 100)
    applicable = pd.to_numeric(result["applicable_rs_score"], errors="coerce")
    blue = result["blue_sky_breakout"].fillna(False).astype(bool).astype(float) * 100
    result["ranking_missing_component_count"] = (
        pd.concat([applicable, volume_quality, close_quality, range_quality], axis=1)
        .isna()
        .sum(axis=1)
    )
    result["superperformance_rank_score"] = (
        0.40 * applicable.fillna(0)
        + 0.20 * volume_quality.fillna(0)
        + 0.15 * close_quality.fillna(0)
        + 0.15 * range_quality.fillna(0)
        + 0.10 * blue
    )
    return result


def path_counts(frame: pd.DataFrame) -> dict[str, int]:
    """Return declared path counts for audit output."""

    return {
        column: int(frame.get(column, pd.Series(dtype=bool)).fillna(False).sum())
        for column in PATH_COLUMNS
    }
