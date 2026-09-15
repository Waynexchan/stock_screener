# YOUNG_LEADER_ADDITIVE_V1

Status: **PREREGISTERED_ADAPTIVE_FOLLOWUP_NO_UNTOUCHED_HOLDOUT**

Production effect: **NONE**

## Origin and hypothesis

`SUPERPERFORMANCE_PATHS_V1` was rejected, but its frozen short-history leader
path was the only distinct entry path with positive return, expectancy, profit
factor, and low drawdown in all three reused periods. This follow-up asks one
narrow portfolio question: does adding that unchanged path ahead of MODEL_0
candidates improve portfolio return and return/drawdown without breaking the
10% drawdown, sample-size, or outlier-concentration gates?

The expected mechanism is that a separately admitted cohort with 90-219 valid
archive sessions may capture emerging price leaders before a mature 220-session
Stage-2 rule can observe them. It is an archive-age proxy, **not** verified IPO
age. No V1 signal threshold is retuned.

## Evidence boundary

All 2017-2025 periods and the standalone component outcomes have already been
inspected. This is adaptive follow-up evidence, not independent validation or an
untouched holdout. The archive contains current surviving symbols, retrospective
earnings dates, imperfect ticker/listing provenance, and no point-in-time
fundamental, membership, delisting, or classification history. The strongest
possible historical decision is `HOLD`.

Any short-history candidate whose first valid bar equals the global archive
start is excluded from the additive path as left-censored. The first valid bar
is reported for every accepted short-history trade. This protects the stated
proxy from obvious archive-boundary contamination but does not prove an IPO or
listing date.

## Frozen signals and execution

- `MODEL_0` is the existing false-to-true mature Stage-2 transition.
- `young_leader_breakout` is copied unchanged from
  `SUPERPERFORMANCE_PATHS_V1`: 90-219 valid sessions, close above EMA10 above
  EMA20 above a rising MA50, within 15% of the available 126-session high, and
  a close above the prior 20-session high on at least 1.5 times 50-session
  average volume with a top-quartile close.
- `additive_union` is `MODEL_0 OR young_leader_breakout` after the mandatory
  earnings blackout and left-censor exclusion.
- All signals form after the close and enter the next available session open
  plus 5 bps adverse slippage.
- Initial stop is the signal-date 20-session low; there is no fixed target;
  maximum hold is 40 sessions; exit slippage is 5 bps; ambiguous bars use
  stop-first handling.
- Every accepted position risks 1R. Portfolio heat is at most 2R, concurrent
  positions at most four, and starting equity is 100R.

## Frozen variants

Five variants are reported in every stage:

1. `baseline`: MODEL_0 using default entry-date/signal-date/ticker ordering;
2. `young_standalone`: unchanged short-history leader path;
3. `additive_default`: union using default ticker ordering;
4. `additive_young_first`: union with short-history candidates ahead of
   MODEL_0-only candidates on the same entry date; this is the **primary
   candidate**;
5. `additive_model0_first`: union with MODEL_0 candidates first, a declared
   path-dependence neighbor.

When one signal satisfies both paths it is one candidate, not two trades. All
remaining ties use signal date then ticker. The priority rule has no access to
future outcomes.

## Periods

- Development signals: 2017-01-01 through 2023-11-01; outcomes end 2023-12-29;
  early/late split 2020-12-31.
- 2024-01-01 through 2024-02-29 remains an excluded contaminated gap.
- Reused 2024 signals: 2024-03-01 through 2024-10-31; outcomes end 2024-12-31.
- Reused 2025 signals: 2025-01-02 through 2025-10-31; outcomes end 2025-12-31.

The inclusive zero-to-ten-calendar-day retrospective earnings blackout is
applied before path selection, ordering, execution, and allocation.

## Frozen decision rule

Every development path must have at least 75 accepted trades, positive early
and late return, positive total return and expectancy, profit factor at least
1.2, and maximum daily mark-to-market drawdown at most 10%. Every reused period
requires at least eight trades, positive return and expectancy, profit factor
at least 1.1, and drawdown at most 10%.

The primary `additive_young_first` candidate reaches `HOLD` only if all of the
following are true:

- it passes every stage gate;
- both total return and return/drawdown exceed MODEL_0 in at least two of three
  periods;
- total P&L excluding the largest winner is positive in every period;
- the largest winner supplies no more than 50% of positive P&L in every period;
- its result direction is not contradicted by both declared ordering neighbors.

The standalone and neighbor variants are diagnostics and cannot substitute for
a failed primary candidate. A pass remains `HOLD`, not validation or forward
promotion. Otherwise the decision is `REJECT` or `REVISE`; no production or
immutable forward-journal change is authorised.
