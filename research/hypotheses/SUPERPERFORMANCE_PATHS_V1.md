# SUPERPERFORMANCE_PATHS_V1

Status: **PREREGISTERED_ADAPTIVE_ROBUSTNESS_NO_UNTOUCHED_HOLDOUT**

Production effect: **NONE**

## Hypothesis

A small number of separately defined, causal superperformance entry paths may
retain more large winners than either a generic Stage-2 transition or a single
conjunction of every plausible quality feature. In particular, permitting a
confirmed blue-sky breakout when no prior resistance supplies a nominal 2R
target may be more coherent than requiring overhead resistance for every
trade.

## Interpretation boundary

The Daily Watchlist is a decision-support workflow with manual entry judgment,
not a fully specified historical order stream. This experiment is therefore a
mechanical translation of observable production concepts, **not** an exact
production-parity backtest. Exact parity is unavailable because historical
manual decisions, point-in-time fundamentals, membership including delistings,
effective-dated classifications, and point-in-time earnings schedules are not
available.

All 2017-2025 outcomes have already been inspected. Every period is reused
adaptive robustness. No result is independent validation or an untouched
holdout, and no result can change production.

## Frozen causal signal paths

All signals form after the close. Entry is the next available session open plus
5 bps adverse slippage. Every path uses the signal-date trailing 20-session low
as its initial stop, fixed 1R per accepted trade, maximum 2R portfolio heat,
maximum four positions, no fixed target, and a 40-session maximum hold. Signals
zero through ten calendar days before a retrospectively retrieved earnings
event are excluded before selection, ranking, or allocation.

- `MODEL_0`: existing false-to-true mature Stage-2 eligibility transition.
- `mature_breakout`: mature Stage 2, close above the prior 50-session high,
  bullish body at least 25% of the daily range, close location at least 60%,
  volume at least 0.9 times the 50-session average, and controlled extension.
- `quality_breakout`: mature breakout with close location at least 75% and
  volume at least 1.5 times average.
- `tight_base_breakout`: quality breakout preceded by a 10-session range no
  wider than 8%, 20/60-session ADR ratio at most 0.8, and 10/40-session volume
  ratio at most 0.8.
- `constructive_pullback`: mature Stage 2, A/B moving-average proximity,
  volume at most 1.5 times average, and a new bullish reversal event. Repeated
  consecutive true states do not create repeated signals.
- `young_leader_breakout`: 90-219 valid sessions, close above EMA10 above
  EMA20 above a rising MA50, within 15% of the available 126-session high, and
  a close above the prior 20-session high on at least 1.5 times average volume
  with a top-quartile close.

`observed_2r_resistance` uses only signal-close information: the prior
252-session high must be above the signal close by at least twice the distance
from signal close to the frozen 20-session stop. `blue_sky_breakout` means the
signal close exceeds the prior 252-session high. This proxy deliberately does
not use the unknowable next-session opening price in signal selection.

The production-style RS gate is frozen as Recent RS at least 70 with an
acceptable causal trend, or Recent RS 60-69.99 with an Improving/Emerging
trend. Young-leader RS is a separate 1-99 cross-sectional score of 60% 63-day
and 40% 20-day return because a 12-month score is structurally unavailable.
The causal trend labels reproduce the production thresholds: Emerging requires
Recent RS at least 80, positive 20-day relative return, and acceleration at
least 0.02 percentage points; Improving requires Recent RS at least 60 and
positive acceleration; Stable Leader requires Long-Term RS at least 80, Recent
RS at least 70, and absolute acceleration below 0.02; a mature leader is
Weakening when Long-Term RS is at least 75 and either acceleration is negative
or 20-day relative return is non-positive.

## Frozen ranking

Unranked variants use entry date, signal date, then ticker. RS ranking sorts by
descending applicable RS score. The superperformance rank is fixed before
outcomes as:

```text
40% applicable RS score
+ 20% clipped volume-ratio quality
+ 15% close location
+ 15% inverse prior 10-session range
+ 10% blue-sky indicator
```

The score changes order only; it is not a hard gate. Missing components receive
zero contribution rather than a plausible imputation, and their count is
reported.

Applicable RS is the completed 12-month proxy for mature paths and the young-RS
score for young paths. Volume quality is `clip(volume_ratio / 2 * 100, 0, 100)`;
close location is clipped to 0-100; inverse-range quality is
`clip(100 - 5 * prior_10_session_range_pct, 0, 100)`; and the blue-sky
indicator is either zero or 100.

## Frozen variants

Eighteen variants are reported in all three periods:

1. MODEL_0 baseline;
2. mature breakout;
3. mature breakout with observed 2R resistance;
4. mature blue-sky breakout;
5. mature breakout with observed resistance **or** blue-sky exception;
6. quality breakout;
7. quality breakout plus production-style RS gate;
8. quality breakout ranked by applicable RS;
9. quality breakout ranked by the frozen superperformance score;
10. tight-base breakout;
11. constructive pullback;
12. young-leader breakout;
13. young-leader breakout with young RS at least 80;
14. union of quality breakout, tight-base breakout, constructive pullback, and
    young-leader breakout;
15. the same union with its applicable RS gate;
16. the same union ranked by the frozen superperformance score;
17. mature blue-sky breakout with a causal 2R-activated SMA20-minus-1ATR20
    ratcheting stop; and
18. ranked multi-path union with the same trailing stop.

The trailing stop becomes eligible only on the session after first touching
2R, uses prior-session SMA20 and ATR20, never loosens, and retains conservative
gap and stop-first handling.

## Periods and decision rule

- Development signal dates: 2017-01-01 through 2023-11-01; outcome end
  2023-12-29; stability split 2020-12-31.
- Excluded contaminated gap: 2024-01-01 through 2024-02-29.
- Reused 2024 signal dates: 2024-03-01 through 2024-10-31; outcome end
  2024-12-31.
- Reused 2025 signal dates: 2025-01-02 through 2025-10-31; outcome end
  2025-12-31.

Development requires positive early/late return, at least 75 accepted trades,
positive expectancy and return, profit factor at least 1.2, and maximum
drawdown at most 10%. Each reused period requires at least eight trades,
positive expectancy and return, profit factor at least 1.1, and drawdown at
most 10%.

A cross-stage shortlist additionally requires return and return/drawdown above
MODEL_0 in at least two periods and no more than 50% of positive P&L from the
largest winner. Pairwise blue-sky-exception, ranking, and trailing comparisons
are reported against their frozen parent even if they do not beat MODEL_0.

With no independent validation or untouched holdout, any numerical pass ends
at `HOLD`; otherwise the decision is `REVISE` or `REJECT`. Production and the
immutable forward journal remain unchanged.
