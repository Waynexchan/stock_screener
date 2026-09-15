# FILTER_COMBINATION_AUDIT_V1

Status: **PREREGISTERED_ADAPTIVE_DIAGNOSTIC_NO_UNTOUCHED_HOLDOUT**

Production effect: **NONE**

## Questions

1. Are historical transactions scarce because the sample produces few signals,
   because successive filters remove them, or because fixed portfolio capacity
   rejects otherwise executable trades?
2. Which observable price/volume filter proxies add incremental portfolio value
   on their own?
3. Across a complete, bounded six-component factorial, does any simple
   combination show stable return, expectancy, drawdown, and outlier behavior?

The purpose is an evidence audit of existing ideas, not a search for a visually
attractive backtest. All reported combinations are frozen before their outcomes
are calculated. Losing and empty combinations remain in the result.

## Interpretation boundary

The exact production Daily Watchlist cannot be reconstructed historically.
Manual chart decisions, chart-confirmed resistance, point-in-time fundamentals,
historical universe membership and delistings, effective-dated industries,
sister-stock membership, and immutable earnings schedules are unavailable.

Every 2017-2025 period has already been inspected in earlier research. This
experiment is adaptive diagnosis, not validation or an untouched holdout. The
current-symbol Yahoo archive is survivorship-biased, current industry labels
create classification bias, and earnings dates were retrieved retrospectively.
No result may change production or be called validated.

## Frozen baseline and execution

- Universe signal: the causal MODEL_0 false-to-true mature Stage-2 transition,
  minimum price USD10 and 50-session average volume 500,000.
- Signal time: after the close; entry: next available session open plus 5 bps
  adverse slippage.
- Stop: signal-date 20-session low; no fixed target; maximum hold 40 sessions;
  5 bps exit slippage; conservative stop-first ambiguity and open gap fill.
- Mandatory inclusive zero-to-ten-calendar-day retrospective earnings blackout
  is applied before any filter, ordering, execution, or allocation.
- Portfolio: 100R starting equity, 1R per accepted trade, fixed 2R maximum heat,
  maximum four positions, normalized R accounting, default entry-date then
  signal-date then ticker ordering.

## Frozen individual filter audit

The following single-filter variants are evaluated against the same baseline:

- Recent RS >=70 and long-term RS >=75 separately;
- production volume-ratio proxy >=0.30;
- ADR between 1% and 10%;
- rolling beta >=0.8 and no current Utilities;
- MarketSmith-style proxy >=80 and positive 21-/63-session proxy change;
- RS line leads the price to a 252-session high;
- stock-within-current-industry rank >=80;
- current-industry breadth >=20% with positive 21-day and non-negative 63-day
  change;
- 50-session up/down-volume ratio >=1.25;
- base duration 15-65 sessions with 3%-35% depth;
- at least one contraction plus 10/40 volume dry-up <=0.8;
- ten-session shakeout/reclaim;
- mechanical base-stage proxy <=2; and
- complete mechanical base quality.

These are declared proxies. They do not silently stand in for unavailable exact
production semantics.

## Frozen six-component factorial

All 64 subsets, including the empty baseline, of these six orthogonal mechanisms
are evaluated:

1. `rs_dual`: Recent RS >=70 and long-term RS >=75;
2. `extension`: within the existing causal EMA/high extension limits;
3. `industry_strong`: current-industry proxy score >=80;
4. `pivot_supply`: price within -5% to +2% of the 126-session pivot and no more
   than one supply day in the prior ten sessions;
5. `breakout_demand`: breakout-quality event with volume ratio >=1.5 and close
   location >=75%;
6. `market_sma50`: signal-date SPY close above its signal-date SMA50.

This produces 80 total variants: the 64 factorial subsets plus 16 non-duplicate
individual diagnostics. Candidate order and risk are identical in every cell.
No threshold optimization is authorized.

The cumulative scarcity funnel uses the fixed order: raw MODEL_0, earnings
blackout, `rs_dual`, `extension`, `industry_strong`, `pivot_supply`,
`breakout_demand`, then `market_sma50`. Single-filter retention is also reported
so the funnel order is not mistaken for marginal value.

## Periods

- Development signals: 2017-01-01 through 2023-11-01; outcomes end 2023-12-29;
  stability split 2020-12-31.
- Excluded contaminated gap: 2024-01-01 through 2024-02-29.
- Reused 2024 signals: 2024-03-01 through 2024-10-31; outcomes end 2024-12-31.
- Reused 2025 signals: 2025-01-02 through 2025-10-31; outcomes end 2025-12-31.

## Marginal and combination evaluation

For each factorial component, all 32 paired contexts with and without that
component are compared in each period. The audit reports median and mean changes
in return, expectancy, profit factor, return/drawdown, drawdown, signal count,
and accepted trades, plus the fraction of contexts improving each metric.

Stage gates are frozen at:

- development: at least 75 accepted trades, positive early and late return,
  positive total return and expectancy, profit factor >=1.2, drawdown <=10%, and
  zero missing marks;
- each reused period: at least eight accepted trades, positive return and
  expectancy, profit factor >=1.1, drawdown <=10%, and zero missing marks.

A factorial combination is a decision shortlist only when it contains at most
three filters, passes every stage gate, beats baseline return and return/drawdown
in at least two periods, has no more than 50% of positive P&L from its largest
winner in every period, and every included filter improves both return and
return/drawdown versus that combination with the filter removed in at least two
periods. Larger conjunctions remain diagnostic because complexity and scarcity
are themselves part of the question.

The historical decision is `HOLD` if at least one combination meets the full
frozen shortlist; otherwise `REJECT`. `HOLD` means only that a frozen candidate
may deserve genuinely new point-in-time validation. It does not authorize a
forward specification or production change.

## Unavailable components

- Point-in-time fundamental acceleration: `BLOCKED_DATA_NOT_READY`.
- Exact historical sister confirmation and effective-dated industry membership:
  `BLOCKED_DATA_NOT_READY`.
- Exact manual setup integrity and chart-confirmed structural R/R:
  `UNAVAILABLE_FOR_PARITY`; preserve their separate prior proxy evidence.
- Operational freshness, valid stops, heat, concentration, and position limits
  remain risk controls, not alpha filters to remove from this test.
