# Pattern Discovery Reporting — Phase 3 Chart Quality

## Status and authority

- Status: authorised for Phase 3 implementation only.
- Classification: `RESEARCH_ONLY` structural chart-description infrastructure.
- Purpose: explain which observable price, volume, support, resistance, and
  benchmark-relative characteristics make a chart look constructive, average,
  ambiguous, or weak. Phase 3 does not test or claim predictive edge.
- Production authority: unchanged. `decision_system.canonical_candidate_decision`,
  called through `run_screener.apply_canonical_decision_pipeline`, remains the
  sole authority for decisions, plan validity, risk, shares, concentration, and
  capacity allocation.
- Non-goals: no unified Left Side Score, outcome optimisation, lane redesign,
  persistent lifecycle, manual label workflow, formal ranking evaluation, or
  production promotion. Phases 4 through 7 remain deferred.

## Isolation and output contract

Phase 3 calculations are pure, deterministic functions of stock OHLCV, the SPY
benchmark where required, the evaluation timestamp, and already observable
current research fields. They return new records and never mutate history or a
canonical candidate in place.

The screening path may carry Phase 3 fields alongside a candidate so the
post-canonical report copy can display them. The canonical engine must ignore
all Phase 3 fields. Every Phase 3 field is explicitly excluded from immutable
forward-snapshot candidates. Tampering with inputs, states, values, evidence,
warnings, summaries, or reasons must leave all canonical fields and allocation
ordering value-equivalent.

Each component exposes:

- `status`: `AVAILABLE`, `INSUFFICIENT_HISTORY`, `MISSING_DATA`, or
  `NOT_APPLICABLE` where relevant;
- `state`: the interpretation described below, or an explicit unknown state;
- `value`: an optional 0–100 descriptive value, with direction documented per
  component; missing is `null`, never a favourable zero;
- `evidence`: deterministic JSON containing the raw/derived observations;
- `warnings`: deterministic, semicolon-delimited limitations; and
- `reason`: concise deterministic prose grounded in the evidence.

There is no aggregate score. `Chart Quality Summary` lists component states in
a fixed order and is labelled `RESEARCH_ONLY` in the Pattern Discovery report.
Numeric values are descriptive transformations only. Thresholds are engineering
interpretation boundaries, easy to change in one module, and are not validated
trading rules.

## Point-in-time and missing-data contract

1. History is sorted by timestamp and sliced at or before `as_of` before any
   calculation. Future rows cannot affect a historical result.
   String date indices must be converted and validated before slicing. When an
   `as_of` cutoff is supplied, a numeric/range index or any index that cannot be
   converted completely and unambiguously to timestamps fails closed as
   `MISSING_DATA`; it must never bypass the cutoff.
2. Positional windows retain missing sessions; incomplete required windows do
   not backfill from older rows.
3. Resistance uses only highs and congestion already observable by `as_of`.
   Phase 3 does not use later-confirmed swing points or volume profile.
4. RS history aligns stock and SPY timestamps through `as_of`. Missing benchmark
   data yields an explicit unavailable result.
5. Missing volume never means volume dry-up or absence of distribution.
   Negative volume is invalid, not low activity. Every component-required
   volume window must reject it as `MISSING_DATA`, and any relative-volume
   calculation requires a strictly positive baseline.
6. Component values are `null` whenever required evidence is unavailable.
   Undefined or non-finite derived ratios are unavailable evidence and cannot
   receive score credit through numeric clamping.
7. Shuffled input rows with the same unique timestamps produce identical output.
8. Price windows requiring OHLC geometry must contain positive prices with
   `Low <= Open/Close <= High` (for the columns present). Impossible geometry
   fails closed as `MISSING_DATA` rather than producing a component value.

## Components

### 1. Prior Advance Quality

- Type/direction: hybrid numeric + categorical; higher is more orderly and
  constructive.
- Purpose: distinguish an orderly advance from a one-day spike or unstable path.
- Inputs: adjusted closes from a 60-session advance window ending 10 sessions
  before the evaluation session.
- Lookback/minimum: 71 rows (61 closes for 60 returns plus the 10-session gap).
- Calculation: preserve the existing Phase 2 endpoint return definition and add
  path efficiency (net progress / total absolute path), positive-session share,
  maximum internal drawdown, large downside reversal count, and largest positive
  session as a share of all positive progress. The descriptive value weights
  return 25%, efficiency 25%, constructive-session share 20%, drawdown control
  20%, and reversal control 10%; a positive-progress concentration above 50%
  receives a transparent 20-point spike penalty. Return maps 0%→0 and 25%→100;
  efficiency maps 0.15→0 and 0.80→100; constructive share maps 40%→0 and
  70%→100; drawdown control maps 5%→100 and 20%→0; reversal control maps zero
  events→100 and five→0.
- Interpretation: `STRONG` ≥75, `CONSTRUCTIVE` ≥55, `MIXED` ≥35, otherwise
  `WEAK`. A larger return cannot compensate automatically for a concentrated
  spike or severe drawdown.
- Missing behaviour: incomplete close history -> `INSUFFICIENT_HISTORY` or
  `MISSING_DATA`, value `null`.
- Reason: return, efficiency, constructive-session share, drawdown, reversal
  count, and spike concentration.
- Phase 2 consumers: explanatory context for all three lanes; no score or
  membership input.

### 2. Trend Smoothness

- Type/direction: hybrid numeric + categorical; higher means a smoother
  advancing trend.
- Purpose: distinguish orderly directional progress from erratic or flat quiet
  behaviour.
- Inputs: recent adjusted closes.
- Lookback/minimum: 41 closes / 40 returns.
- Calculation: net 40-session return, directional path efficiency, positive-day
  share, linear fit of log price, normalised positive slope, and large reversal
  frequency. The value weights direction 25%, efficiency 25%, positive-day share
  15%, regression fit 20%, and reversal control 15%. Direction maps 0%→0 and
  10%→100; efficiency 0.15→0 and 0.80→100; positive-day share 45%→0 and
  65%→100; reversal control zero→100 and eight→0.
- Interpretation: `SMOOTH_UPTREND`, `ORDERLY_UPTREND`, `FLAT_OR_DIRECTIONLESS`,
  `ERRATIC`, or `WEAK_DOWNTREND`. A return ≤−2% is weak/down; absolute return
  below 2% or non-positive fitted slope is flat/directionless; at least six
  large reversals or value below 40 is erratic; value ≥75 with return ≥5% is
  smooth; other positive trends are orderly. Low volatility alone cannot
  qualify.
- Missing behaviour: incomplete closes -> explicit insufficient/missing state.
- Reason: net direction, efficiency, regression fit, and reversal count.
- Phase 2 consumers: explanatory context for Tight Base and Pullback only.

### 3. Distribution / Wide-Bar Penalty

- Type/direction: penalty; 0 means no observed penalty and higher is worse.
- Purpose: identify repeated disruptive downside price/volume behaviour.
- Inputs: 20 recent sessions of OHLCV plus prior data for true-range and volume
  baselines.
- Lookback/minimum: 51 sessions; all measured OHLCV and baseline observations
  must be valid.
- Calculation: count down sessions with true range at least 1.5 times the prior
  20-session median, volume at least 1.5 times the prior 20-session mean, and/or
  close location in the bottom 25% of the bar. A distribution event requires at
  least two of those three observations. Penalty is 20 per event plus five for
  each repeated wide-down or high-volume-down observation beyond the first,
  capped at 100. One isolated event therefore cannot exceed `LIGHT` by itself.
- Interpretation: `NONE`, `LIGHT`, `MODERATE`, or `HEAVY`.
- Missing behaviour: missing/negative volume, a non-positive volume baseline,
  or invalid price inputs/geometry -> `MISSING_DATA`, value `null`; invalid or
  missing evidence cannot be read as no distribution.
- Reason: composite, wide-down, high-volume-down, and weak-close counts.
- Phase 2 consumers: Breakout lane explanation only; no hard gate.

### 4. Overhead Supply

- Type/direction: hybrid numeric + categorical penalty; higher means more
  observable overhead supply.
- Purpose: describe nearby resistance and congestion above current price.
- Inputs: current close and the previous 60 sessions' highs/lows/closes.
- Lookback/minimum: 61 complete price sessions.
- Calculation: distance to the nearest prior high at or above current close,
  share of prior sessions whose traded range overlaps the band from current
  price to 10% above it, and share of closes in that band. The value equally
  weights high proximity (0% distance→100, 10%→0) and mean congestion density
  (0%→0, 30%→100). No volume-at-price profile or future-confirmed swing point is
  used.
- Interpretation: `LOW`, `MODERATE`, `HEAVY`, or `NO_OBSERVED_OVERHEAD`; unknown
  is explicit. `HEAVY` is value ≥70, `MODERATE` ≥35, otherwise `LOW`; no prior
  high at/above price is `NO_OBSERVED_OVERHEAD` with genuine value zero.
- Missing behaviour: incomplete window -> insufficient/missing state.
- Reason: nearest-high distance and congestion observations.
- Phase 2 consumers: Breakout and Pullback explanatory context.

### 5. Contraction Quality

- Type/direction: hybrid numeric + categorical; higher means broader confirmed
  contraction.
- Purpose: combine price, daily-range, sequential-range, and volume contraction
  without reducing contraction to one threshold.
- Inputs: OHLCV; the existing definitions of 10D/20D range, ADR20/ADR60, and
  Phase 2 recent-five/prior-20 volume ratio are reused exactly.
- Lookback/minimum: 61 sessions for complete price/ADR evidence; volume evidence
  additionally requires the complete latest 25 sessions.
- Calculation: 10D/20D range ratio, ADR20/ADR60 ratio, volume dry-up ratio, and
  number of strict contractions across three consecutive 10-session ranges.
  The three blocks are exactly `[-30:-20]`, `[-20:-10]`, and `[-10:]`, so both
  adjacent comparisons are observable and a count of two is reachable.
  Available full evidence uses 30% range, 30% ADR, 30% volume, and 10%
  sequential contraction. Each price/ADR ratio maps 0.50→100 and 1.10→0;
  volume maps 0.50→100 and 1.20→0. Price contraction requires range ratio ≤0.80
  and ADR ratio ≤0.90; volume dry-up requires ratio ≤0.80; expanding means
  either price/ADR ratio >1.10; strong multi-dimensional additionally requires
  at least one strict sequential contraction.
- Interpretation: `STRONG_MULTI_DIMENSIONAL`, `PRICE_CONTRACTION_ONLY`,
  `VOLUME_DRY_UP_ONLY`, `WEAK_OR_NONE`, `EXPANDING`, or
  `PRICE_CONTRACTION_VOLUME_UNKNOWN`.
- Missing behaviour: absent or negative volume never earns dry-up credit, and
  the prior-20 volume baseline must be positive. The prior mean, recent mean,
  and resulting volume ratio must all be finite before volume evidence is
  available. When price evidence is complete but volume is unavailable or
  invalid, state is explicit and value is `null`.
  A non-positive 20-session price-range or ADR60 denominator makes the price
  contraction ratios undefined; the component then returns `MISSING_DATA` with
  a null value while exposing the observed zero baselines and null ratios.
- Reason: all ratios and sequential count.
- Phase 2 consumers: Tight Base explanation. Existing Phase 2 membership, score,
  contraction thresholds, and ranks remain unchanged.

### 6. Support Respect

- Type/direction: hybrid numeric + categorical; higher means more observed
  holding/reclaim behaviour.
- Purpose: distinguish actual support interaction from proximity alone.
- Inputs: point-in-time EMA10, EMA20, MA50, existing observable pivot, ATR20,
  and the last 15 OHLC sessions.
- Lookback/minimum: 60 sessions so all candidate references and ATR20 are
  available.
- Reference resolution: select the reference with the smallest absolute current
  ATR distance within three ATR. Exact ties use `EMA20`, `EMA10`, `MA50`, then
  `PIVOT`. References are not averaged.
- Calculation: a test intersects a ±1% band; a successful hold closes at/above
  the reference; a reclaim crosses from below to at/above; a destructive breach
  closes more than 2% below. The value rewards successful interactions and
  penalises breaches: three successful interactions map to 100 on the 70%
  interaction term, while zero→100 and three breaches→0 on the 30% control term.
- Interpretation: `STRONG`, `CONSTRUCTIVE`, `AMBIGUOUS_PROXIMITY`, or `BROKEN`.
  `STRONG` requires at least two successful holds/reclaims and no destructive
  breach. One success with no more than one breach is `CONSTRUCTIVE`; two or
  more breaches, or the latest close more than 2% below support, is `BROKEN`;
  proximity without a test/hold/reclaim is only ambiguous.
- Missing behaviour: no valid nearby reference -> `NOT_APPLICABLE`; incomplete
  interaction evidence -> explicit insufficient/missing state.
- Reason: chosen reference, distance, tests, holds, reclaims, and breaches.
- Phase 2 consumers: Pullback explanation only. It cannot change Pullback lane
  membership or `Pullback Lane Quality`; a non-member stays non-member and
  cannot regain `CONSTRUCTIVE`/`POTENTIAL` through Phase 3.

### 7. Relative Strength Persistence

- Type/direction: hybrid numeric + categorical; higher means more persistent
  benchmark-relative leadership.
- Purpose: distinguish sustained/improving RS from one recent surge.
- Inputs: current existing Recent RS score plus aligned stock and SPY closes.
- Lookback/minimum: 31 aligned sessions.
- Calculation: 20-session relative return, log relative-line slope and fit,
  positive relative-session share, share of the relative line above its trailing
  10-session mean, recent-five versus prior-15 relative progress, and the latest
  day as a share of positive relative progress. The value weights current level
  20%, relative direction 20%, persistence 25%, baseline persistence 20%, and
  fit 15%. Relative return maps 0%→0 and 10%→100; positive-session share maps
  40%→0 and 70%→100; above-baseline share maps 40%→0 and 80%→100. A latest-day
  concentration above 50% receives a transparent 20-point spike penalty and is
  `INCONSISTENT`.
- Interpretation: `PERSISTENTLY_STRONG`, `IMPROVING`,
  `STRONG_BUT_DETERIORATING`, `INCONSISTENT`, or `WEAK`.
  Current RS ≥70 with negative recent-five return or non-positive relative-line
  slope is deteriorating, except that latest-day concentration above 50% takes
  precedence and is always `INCONSISTENT`. Positive direction whose recent per-session progress
  exceeds the prior-15 rate by 25% is improving. Persistent strength requires
  current RS ≥70, positive 20-session direction, at least 55% positive relative
  sessions, at least 65% above the rolling baseline, and positive slope. Current
  RS below 40 with non-positive relative return is weak; other mixed paths are
  inconsistent.
- Missing behaviour: missing current score, benchmark, or aligned history yields
  an explicit unavailable state and value `null`.
- Reason: current level (kept conceptually separate), relative direction,
  persistence, deterioration, and one-day concentration.
- Phase 2 consumers: explanatory context for all lanes; existing Recent RS lane
  factors remain unchanged.

## Phase 2 integration

Phase 3 states and concise reasons may be appended to lane explanation text:

- Tight Base: Prior Advance, Trend Smoothness, Contraction, RS Persistence.
- Pullback: Prior Advance, Trend Smoothness, Overhead Supply, Support Respect,
  RS Persistence.
- Breakout: Prior Advance, Distribution, Overhead Supply, RS Persistence.

They do not enter a lane score, membership rule, rank key, quality label, or
lifecycle state. Existing Phase 2 values remain the ranking authority.

## Acceptance criteria and test design

The implementation must cover the 50 scenarios authorised in the Phase 3 task,
grouped as follows:

1. Production isolation: full canonical-field equivalence under Phase 3 input,
   output, and reason tampering; invalid stop/target still fail; weak quality
   cannot demote; WATCH/NO TRADE stay zero-risk; capacity ordering is unchanged.
2. Component direction: orderly advance over spike; smooth uptrend over erratic
   or flat quiet; repeated distribution over small down days; congestion over
   clear space; multi-dimensional contraction over one dimension; observed
   holds/reclaims over proximity or breaks; persistent RS over one-day surge.
3. Missing data: insufficient history and missing volume/benchmark/support stay
   explicit with null values and cannot rank favourably.
4. Point-in-time: future rows do not affect resistance, support, breakout, RS,
   or any component when `as_of` is fixed.
5. Determinism: repeated inputs and shuffled history/candidate rows produce
   identical component states, evidence, reasons, and existing lane ranks.
6. Phase 1/2 regression: Actionable Now remains canonical; the fixed generic-
   support, missing-support, non-member quality, lost-higher-low, incomplete-
   breakout, and one-row/multi-lane behaviours remain intact.
7. Reporting/snapshots: Pattern Discovery outputs carry intended summary and
   machine evidence; unknowns render clearly; CSV/HTML/Markdown/email manifests
   agree; validators reject contradictions; Phase 3 fields are absent from
   forward snapshots.

For every report row containing Phase 3 evidence, validators must accept only
the documented status and component-state enums, require values to be within
0–100 when `AVAILABLE` and null otherwise, require the Distribution direction
warning, and reconstruct the exact fixed-order `Chart Quality Summary` from the
seven component states. A merely `RESEARCH_ONLY`-prefixed but contradictory
summary is invalid.

### Mandatory test-design review

- Research-to-production leakage is caught by complete canonical-field and
  allocation comparisons rather than decision-only assertions.
- Inverted direction is caught with paired synthetic paths for every component,
  including an explicit penalty-direction assertion for Distribution.
- Favourable missing treatment is caught by missing close, volume, support, and
  benchmark fixtures that require null values and unavailable states.
- Future leakage is caught by appending extreme future price/volume/benchmark
  rows and holding `as_of` constant.
- Flat quiet stocks are compared directly with smooth positive trends.
- EMA proximity without interaction is required to remain ambiguous.
- A one-day RS surge is compared with a multi-session relative-strength path.
- Phase 3 contamination of Phase 1/2 is caught by tampering every Phase 3 field,
  re-running canonical decisions, and asserting Phase 1 sections and Phase 2
  lane membership/scores/ranks are unchanged.
- The previous missing-support/non-member regression remains in the Phase 2
  suite and receives an additional Phase 3-positive-evidence isolation case.

These tests establish deterministic engineering behaviour and isolation only.
They do not establish expectancy, predictive value, or production readiness.

## Known limitations and deferred work

- Yahoo-style adjusted OHLCV and an on-demand SPY series do not provide an
  auditable historical volume profile, point-in-time universe, or delisting
  coverage. Overhead Supply is therefore price-congestion evidence only.
- Current Recent RS is cross-sectional to the screened universe while RS path
  evidence is time-series relative to SPY; both are exposed separately.
- Thresholds are interpretable engineering defaults, not empirically optimised.
- Phase 4 lifecycle, Phase 5 labels, Phase 6 evaluation, Phase 7 promotion, and
  all outcome optimisation are explicitly deferred.
