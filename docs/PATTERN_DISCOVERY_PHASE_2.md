# Pattern Discovery Reporting — Phase 2 Setup Lanes

## Status and authority

- Status: authorised for Phase 2 implementation only.
- Classification: `RESEARCH_ONLY`, hypothesis-generating chart-review ranking.
- Outcome exposure: no Phase 2 performance or trading-outcome evidence is used by
  this specification. The lane definitions are not validated edge claims.
- Production authority: unchanged. `decision_system.canonical_candidate_decision`,
  called through `run_screener.apply_canonical_decision_pipeline`, remains the
  sole authority for `FULL`, `HALF`, `WATCH`, `NO TRADE`, actionability, risk,
  shares, structural plan validity, portfolio capacity, and concentration.
- Upstream universe: unchanged. Phase 2 ranks candidates already produced by the
  current discovery and canonical-decision paths; it does not redefine Stage 2,
  minimum-RS, freshness, or candidate-universe eligibility.
- Non-goals: no Phase 3 component framework, persistent Phase 4 state machine,
  manual labels, precision/recall or expectancy evaluation, strategy-rule
  change, or production promotion.

## Architecture and isolation contract

The two paths remain one-way and separate:

```text
candidate record -> canonical decision -> allocation -> immutable production fields
                                                |
                                                v
                                copied post-canonical report record
                                                |
                                                v
                      Phase 1 section -> Phase 2 lanes -> report only
```

Phase 2:

1. consumes a deep copy after the canonical decision and Phase 1 section are
   known;
2. may classify and rank only rows in `Pattern Watchlist`;
3. overwrites untrusted incoming Phase 2 fields deterministically;
4. never supplies an entry, stop, target, R/R, decision, risk, shares,
   confirmation, production score, capacity order, or concentration result;
5. never reads a Phase 2 score or rank while making a canonical decision; and
6. is excluded from immutable production forward-snapshot candidate payloads.

`Actionable Now` and `Avoid / Failed` may retain observable Phase 2 input
evidence for diagnostics, but they receive no setup-lane membership, score, or
rank. A ticker may belong to multiple setup lanes. That represents multiple
chart-review hypotheses for one canonical candidate record, never multiple
trades or additional risk.

## Point-in-time feature contract

All features use bars at or before the record's signal date. No future bar,
outcome, revised label, or later snapshot may be read.

Existing observable fields are reused where available: Recent RS, long-term RS,
RS trend and acceleration, 10/20-day range, ADR20/ADR60, VCP ratio, distance to
pivot and 52-week high, moving-average distances, ATR, volume ratio, support
signal, pullback quality, and extension status.

The following narrow Phase 2 evidence may be calculated directly from the
current point-in-time OHLCV history. These are lane inputs, not a reusable
Phase 3 quality framework:

- prior-advance 60-session return ending 10 sessions before the signal;
- recent pullback depth from the 20-session high in ATR;
- recent down-session volume relative to earlier advancing-session volume;
- preservation of the recent higher low;
- current close position within the daily range;
- recent five-session volume relative to the preceding 20 sessions;
- most recent price-and-volume breakout over the prior 50-session high within
  the last 15 sessions;
- breakout age, pivot, hold sessions, post-breakout range, and post-breakout
  volume relative to the pre-breakout baseline.

The 20-session pullback-depth ATR requires valid `High`, `Low`, and `Close` for
all 20 measured sessions plus the immediately preceding close needed by the
first true-range observation. If any required value is missing, pullback depth
remains missing; true range may not fall back to a partial component.

The Lane C lifecycle definitions are frozen as follows:

- A breakout event requires the event close to exceed the highest high of the
  preceding 50 sessions and event volume to be at least `1.20x` the mean of
  valid volume observations in the rolling 50-session window immediately
  preceding the event. Both windows exclude the event bar. The price window
  requires all 50 prior highs; the 50-session volume window requires at least
  20 valid observations. It is not a trailing-20-session volume average.
- The implementation selects the most recent qualifying event at age 0 through
  15 sessions, inclusive. Age 0 is the signal bar.
- Session rows remain on the point-in-time timeline even when a required OHLCV
  value is missing. Missing data never removes a session from any Phase 2
  positional lookback, breakout age, or hold-session accounting. A feature with
  missing data at a required exact position or anywhere in its required window
  remains missing; an older complete row never backfills that session.
- `NO_RECENT_BREAKOUT_EVIDENCE` is emitted only when every candidate event
  position at age 0 through 15 has an evaluable event window and none qualifies.
  An event position is evaluable only when its event close and volume are valid,
  all 50 preceding highs are valid, and the preceding rolling 50-session volume
  window contains at least 20 valid observations with a positive mean. If no
  verified event can be selected and any relevant position is unevaluable, the
  state is `BREAKOUT_WINDOW_INCOMPLETE`; it is unranked and cannot fall back to
  near-pivot membership. Once a verified event exists, later missing bars are
  governed by the post-event `RECENT_BREAKOUT_DATA_INCOMPLETE` rule so the known
  event age remains observable.
- Post-breakout evidence uses only bars strictly after the breakout event. The
  event bar cannot contribute a hold session, post-breakout range, or
  post-breakout volume observation.
- A same-day event therefore has missing hold duration, post-breakout range,
  and post-breakout volume. Those factors contribute zero and are listed as
  missing; the event remains `SAME_DAY_BREAKOUT_UNCONFIRMED`.
- A breakout is held only when every available post-event close is at least
  `97%` of the event pivot. Any post-event close below that boundary means the
  pivot was materially lost and the event is `RECENT_BREAKOUT_INVALIDATED`.
- Hold sessions count strictly post-event sessions. Post-breakout range is the
  highest high minus lowest low across strictly post-event bars, divided by the
  current close.
- Post-breakout volume is the mean volume of strictly post-event bars divided
  by the mean volume of the 20 sessions preceding the event.
- If any strictly post-event bar is missing `High`, `Low`, `Close`, or `Volume`,
  lifecycle verification fails closed as `RECENT_BREAKOUT_DATA_INCOMPLETE`.
  Breakout age and pivot remain observable, but hold sessions, post-breakout
  range, and post-breakout volume remain missing. The incomplete state is not a
  lane member and receives no rank.
- `POST_BREAKOUT_CONSOLIDATION` requires event age of at least three sessions,
  a held pivot, post-breakout range no greater than `8%`, and post-breakout
  volume no greater than `1.00x`. A valid held event that does not satisfy all
  consolidation conditions is `POST_BREAKOUT_HOLD`.

If history is insufficient, the field remains missing. Missing evidence is
never converted to zero, a passing boolean, a favourable label, or a synthetic
price.

## Shared ranking semantics

- Every factor contribution is a fixed, documented 0–100 transformation; no
  cross-sectional normalisation or input-row-order dependency is permitted.
- Each lane uses its own weights, penalties, membership, score, reasons, and
  ordering. There is no shared generic composite presented under three names.
- A missing factor contributes no favourable points and is listed explicitly.
- Lane ordering is: fewer missing factors, higher lane score, then ticker
  ascending. Rank is the resulting one-based ordinal, so ties are replayable.
- Scores are rounded to two decimals after all weights and penalties.
- Ranking is recomputed independently per lane. One lane's score or rank cannot
  overwrite another lane's fields.
- Membership is deliberately broader than top-quality classification. Except
  for unusable evidence or an explicit invalidated breakout, quality is normally
  expressed through continuous scores and penalties rather than hard filters.

## Lane A — Tight Base / VCP

### Purpose and membership

Identify Pattern Watchlist charts showing observable base/contraction evidence.
Membership requires usable contraction evidence and at least one of:

- an existing tight/developing-base category;
- 10-day range no wider than 20-day range;
- ADR20 no greater than ADR60; or
- price within 10% of the observable pivot.

Missing production plan fields do not prevent membership. Missing all usable
contraction/pivot evidence does.

### Factors and direction

| Factor | Weight | Better direction / fixed interpretation | Missing behaviour |
| --- | ---: | --- | --- |
| Recent RS | 12 | higher; 40→0, 90→100 | zero contribution; listed |
| RS improvement | 8 | improving/emerging and positive acceleration higher | zero; listed |
| 10-day range | 18 | lower; 20%→0, 4%→100 | zero; listed |
| 10D/20D contraction | 14 | lower; 1.0→0, 0.45→100 | zero; listed |
| ADR20/ADR60 | 14 | lower; 1.10→0, 0.50→100 | zero; listed |
| volume dry-up | 10 | lower recent/prior ratio; 1.30→0, 0.50→100 | zero; listed |
| pivot proximity | 10 | smaller absolute distance; 10%→0, 0%→100 | zero; listed |
| 52-week-high proximity | 6 | closer from below; 30% away→0, at high→100 | zero; listed |
| prior-advance proxy | 8 | higher 60-session pre-pullback advance; 0%→0, 30%→100 | zero; listed |

Penalties: `Extended` −15, `Overextended` −30, materially loose 10-day
range −10, and volume expansion above 1.5× −10. Penalties affect research score
only.

Reason text reports contraction, VCP/ADR evidence, pivot/high proximity,
volume behaviour, extension penalties, and missing factors.

## Lane B — Pullback to Support

### Purpose and membership

Identify Pattern Watchlist charts near observable EMA10/EMA20/MA50 support or
already classified in the existing pullback family. Membership requires at
least one usable support-distance value and either nearest support within 3 ATR
or the existing pullback category.

Touching a moving average is not sufficient for a top-quality classification.
Support/reclaim evidence, prior advance, structure, pullback depth, volume, and
close strength are evaluated separately.

### Factors and direction

| Factor | Weight | Better direction / fixed interpretation | Missing behaviour |
| --- | ---: | --- | --- |
| prior advance | 15 | higher; 0%→0, 30%→100 | zero; listed |
| Recent RS | 8 | higher; 40→0, 90→100 | zero; listed |
| support proximity | 18 | closer; 3 ATR→0, 0 ATR→100 | zero; listed |
| pullback depth | 14 | constructive 1.5–3 ATR best; >6 ATR poor | zero; listed |
| trend structure | 12 | above MA50 and higher-low preservation higher | zero; listed |
| pullback volume | 10 | lower down-volume/prior-up-volume ratio better | zero; listed |
| close strength | 8 | higher close-in-range better | zero; listed |
| support/reclaim evidence | 10 | explicit reclaim/support evidence higher | zero; listed |
| pivot/overhead context | 5 | smaller absolute pivot distance better | zero; listed |

Penalties: broken MA50 structure −25, lost higher low −20, excessive pullback
depth above 6 ATR −20, missing reclaim/support evidence −10, and
`Extended`/`Overextended` −15/−30.

Quality label:

- `CONSTRUCTIVE`: score ≥70, explicit support evidence, structure not broken,
  and pullback depth not excessive;
- `POTENTIAL`: score ≥50 with structure not broken;
- `AMBIGUOUS_SUPPORT`: observable proximity without enough confirming evidence;
- `WEAK_OR_BROKEN`: broken structure or excessive depth.

The quality label is explanatory research text only.

## Lane C — Breakout Retest / High Flag

### Purpose and membership

Identify Pattern Watchlist charts in the near-breakout, same-day-breakout, or
bounded post-breakout family. Phase 2 uses only a rolling point-in-time lookback;
it does not create or claim a persistent setup lifecycle.

Evidence states are:

- `NEAR_PIVOT_UNCONFIRMED`: near an observable pivot with no recent verified
  price-and-volume breakout;
- `SAME_DAY_BREAKOUT_UNCONFIRMED`: a price-and-volume breakout occurred on the
  signal bar; never labelled retest or high flag;
- `POST_BREAKOUT_HOLD`: a breakout occurred 1–15 sessions ago and subsequent
  closes have not materially lost the event pivot;
- `POST_BREAKOUT_CONSOLIDATION`: a held breakout is at least three sessions old
  and shows bounded range and non-expanding post-breakout volume;
- `RECENT_BREAKOUT_INVALIDATED`: a recent breakout materially lost its pivot;
- `RECENT_BREAKOUT_DATA_INCOMPLETE`: a recent breakout exists, but one or more
  post-event bars lack required lifecycle OHLCV evidence;
- `BREAKOUT_WINDOW_INCOMPLETE`: the recent event-search window lacks sufficient
  event close/volume, prior-50 high, or rolling-50 volume-baseline evidence;
- `NO_RECENT_BREAKOUT_EVIDENCE`: neither breakout nor near-pivot evidence is
  available.

Membership includes the first four states and excludes invalidated,
data-incomplete, and no-evidence states. A same-day breakout remains explicitly
unconfirmed.

### Factors and direction

| Factor | Weight | Better direction / fixed interpretation | Missing behaviour |
| --- | ---: | --- | --- |
| lifecycle evidence | 30 | consolidation > hold > same-day > near-pivot | zero; listed |
| Recent RS | 12 | higher; 40→0, 90→100 | zero; listed |
| pivot proximity | 14 | closer to pivot within the family higher | zero; listed |
| post-breakout range | 12 | lower; 12%→0, 3%→100 | zero; listed |
| post-breakout volume | 10 | lower relative volume better after breakout | zero; listed |
| hold duration | 8 | more held sessions up to five better | zero for states where unavailable; listed |
| 10-day contraction | 8 | lower; 20%→0, 4%→100 | zero; listed |
| extension control | 6 | not extended higher | zero; listed |

Penalties: `Extended` −15, `Overextended` −30, post-breakout range above 12%
−15, and post-breakout volume above 1.5× −10. An invalidated breakout is not
ranked.

Reason text always names the lifecycle evidence and explicitly states the
rolling-lookback limitation. `SAME_DAY_BREAKOUT_UNCONFIRMED` must never be
rendered as a confirmed retest or high flag.

## Output and compatibility contract

One CSV row remains the canonical record for one ticker. Phase 2 adds:

- a semicolon-delimited `Setup Lanes` summary;
- per-lane membership, score, rank, reason, and missing-factor fields;
- pullback quality and breakout-evidence state; and
- the narrow research input evidence listed above.

HTML and email may render three lane subsections under Pattern Watchlist,
ordered by each lane's independent rank. Markdown renders every Pattern
Watchlist ticker exactly once in one canonical table; its `Setup Lanes` summary
and separate per-lane membership, score, rank, reason, and missing-factor
columns preserve multi-lane semantics without duplicate visible ticker rows.
Markdown retains all lane headings with member counts, including the
`Unassigned / Insufficient Lane Evidence` count. A multi-lane ticker remains
one canonical record with unchanged production risk.

The shared machine-readable manifest includes lane membership, scores, ranks,
and breakout/pullback labels so CSV, HTML, and email can be compared. Legacy CSV
preview derives what it can from existing columns and reports missing inputs;
it does not recalculate production decisions.

Phase 2 research input/output fields are excluded from immutable forward
snapshots. Forward-snapshot schema version, report-history schema, production
entry points, and canonical state names remain unchanged.

## Acceptance criteria

1. Applying Phase 2 annotation leaves every canonical production field
   value-equivalent, including decision, actionability, confirmation, risk,
   shares, plan values, production score, allocation, and concentration.
2. Changing any lane input, score, membership, or rank cannot change a
   canonical decision or risk size.
3. `WATCH` and `NO TRADE` remain zero-risk and zero-share.
4. Missing target remains missing, invalid stop remains invalid, and lane logic
   never creates either value.
5. Existing portfolio capacity ordering and outcomes are unchanged.
6. Clear contraction ranks above a materially looser otherwise-comparable base.
7. Missing contraction evidence is explicit and ranks after complete evidence.
8. Extension receives the specified research penalty without changing
   production fields.
9. A constructive pullback ranks above a broken-structure comparable pullback.
10. Moving-average proximity without confirmation cannot receive
    `CONSTRUCTIVE` quality.
11. Missing ATR/support evidence is explicit and never favourable.
12. A deep destructive pullback is labelled `WEAK_OR_BROKEN`.
13. A same-day breakout is labelled `SAME_DAY_BREAKOUT_UNCONFIRMED`, never a
    confirmed retest/high flag; the breakout bar is excluded from hold,
    post-breakout range, and post-breakout volume evidence.
14. Available post-breakout consolidation evidence improves the lane result
    relative to otherwise-comparable same-day evidence.
15. Missing breakout history remains explicit; future bars are not inferred.
    A missing post-event OHLCV value cannot compress the session timeline or
    produce ranked lifecycle evidence.
16. Missing values at exact prior-advance positions or inside pullback, ATR,
    close-strength, and volume windows leave the affected feature missing; no
    older session is substituted. ATR completeness includes the close
    immediately before its 20-session measurement window.
17. An incomplete breakout event-search window is unranked and cannot become a
    near-pivot member. A fully evaluable window with no event may still use the
    documented near-pivot fallback.
18. Repeated inputs and permuted input order produce identical per-ticker ranks.
19. Ties resolve by ticker ascending.
20. Lane scores/ranks are independent and stored in distinct fields.
21. Pattern Watchlist shows lane membership and preserves unassigned rows.
22. Actionable Now remains exactly canonical `FULL`/`HALF`; Avoid / Failed
    remains governed by Phase 1 failure evidence.
23. Multi-lane membership is explicit and creates no duplicate CSV, Markdown
    canonical row, or manifest record and no additional risk.
24. CSV, HTML, Markdown, and email present consistent lane semantics; the
    validator rejects cross-output disagreement and invalid lane placement.
25. Phase 2 fields are absent from forward-snapshot candidates.
26. All existing Phase 1, canonical-decision, report, and full repository gates
    pass with no intentional production-decision change.

## Test-design review

- Production-isolation tests compare the complete canonical field set rather
  than only final state, guarding against score, plan, sizing, and capacity
  leakage.
- Lane tests use pairs that differ in the intended evidence while holding
  unrelated evidence constant; this reduces the chance that a generic score
  accidentally satisfies all three lanes.
- Missing-value cases assert both rank ordering and human-readable missing
  indicators, guarding against favourable imputation.
- Determinism tests permute rows and assert per-ticker results, not DataFrame
  order.
- Breakout tests distinguish signal-day breakout, post-breakout hold,
  consolidation, and invalidation; they do not treat the same candle as a full
  lifecycle. Boundary cases cover `1.20x` event volume, `97%` pivot retention,
  `8%` consolidation range, and `1.00x` post-breakout volume. Missing
  post-event OHLCV preserves breakout age and fails lifecycle evidence closed.
  A volume-baseline case where trailing-20 and rolling-50 means disagree locks
  the event definition to the rolling 50-session window. Exact-position and
  fixed-window missing-data cases prove that older complete sessions never
  backfill a Phase 2 feature, and an incomplete prior-50 event window remains
  unranked instead of using near-pivot fallback.
- Reporting tests inspect lane headings/counts, one-row-per-ticker Markdown and
  manifest output, multi-lane fields, and validator rejection paths.
- Snapshot tests use a complete discovery-shaped record and assert every Phase
  2 field is excluded.
- The tests establish software behaviour and isolation only. They do not
  establish predictive value, trading edge, or readiness for production use.
