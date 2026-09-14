# Completed Leader Selection Robustness V2

Status: **REJECT — RESEARCH_ONLY**

Production effect: **NONE**

Data label: **SURVIVORSHIP-, EARNINGS-SCHEDULE-, AND
CLASSIFICATION-BIASED RESEARCH — NO UNTOUCHED HOLDOUT**

## What was completed before testing

The specification was preregistered at commit `b34c90b`. The clean final run
used commit `b33241a`; its configuration, inputs, and output hashes are recorded
in `research/output/leader_completeness_v2/results.json`.

V2 completed the price/volume features that were missing from V1:

- MarketSmith-style 1-99 RS proxy level plus 21- and 63-session changes;
- exact stock/SPY RS-line 252-session high and whether it leads the stock's own
  252-session closing high;
- stock rank within its current industry;
- current-industry median RS rank, breadth above RS 80, and 21-/63-session
  breadth changes;
- causal pivot, base duration/depth, three-block contraction, volume dry-up,
  pivot supply, shakeout/reclaim, breakout quality, and a mechanical base-stage
  proxy; and
- a delayed breakout follow-through signal that confirms after a later close,
  reapplies the earnings blackout, rebuilds the stop, and enters on the next
  session.

Fundamental acceleration remained `BLOCKED_DATA_NOT_READY`. No point-in-time
fundamentals were approximated. Exit and exposure were frozen at the
20-session-low stop, no target, 40-session maximum hold, next-open execution,
and fixed 2R heat so that selection effects remained attributable.

## Fixed RS buckets

No bucket showed a stable monotonic relationship between higher RS and better
portfolio performance.

| RS bucket | 2017-2023 return / DD | Reused 2024 | Reused 2025 |
|---|---:|---:|---:|
| 1-69 | 41.32% / 17.02% | 6.78% / 5.51% | 10.64% / 6.13% |
| 70-79 | 34.17% / 11.42% | 7.41% / 5.69% | 3.77% / 8.40% |
| 80-89 | 27.27% / 18.28% | 2.09% / 5.77% | 5.91% / 6.06% |
| 90-94 | -6.64% / 57.55% | 4.59% / 6.40% | 14.37% / 6.57% |
| 95-99 | 37.80% / 12.60% | -0.55% / 5.86% | 5.73% / 8.80% |

The baseline returned 42.78% / 9.75%, 9.93% / 3.93%, and 28.01% / 13.07%
over the same three periods. Requiring both one- and three-month RS increases
lost 6.71% with 22.51% drawdown in development, made 7.32% in reused 2024, and
made 28.58% with 13.23% drawdown in reused 2025. The last result remained
outlier-dependent.

An exact RS-line lead was sparse: 67, 4, and 10 trades. It returned 12.34%,
3.43%, and -2.31%. A stock-within-industry score >=80 returned 30.28%, -1.61%,
and 3.94%. Neither completed RS feature improved the baseline robustly.

## Industry policy comparison

| Policy | 2017-2023 return / DD | Reused 2024 | Reused 2025 |
|---|---:|---:|---:|
| Secondary: weak group gets 0.5R | 25.41% / 13.63% | 14.69% / 2.74% | 15.64% / 7.63% |
| Industry >=80 hard gate | 14.75% / 16.85% | 7.73% / 5.09% | 12.76% / 5.06% |
| Industry rank only | 38.28% / 13.12% | 2.83% / 5.57% | 15.61% / 6.99% |
| Strong industry or stock RS >=95 | 15.11% / 14.94% | 10.46% / 2.35% | 5.10% / 7.16% |
| Breadth accelerating hard gate | 9.02% / 15.43% | 7.64% / 4.59% | -1.22% / 6.65% |

Secondary sizing was attractive only in reused 2024. It admitted 253
development trades because 0.5R candidates allowed more positions under 2R
heat, yet still reduced return and increased drawdown. Hard gates reduced 2025
drawdown, but none preserved enough return or passed the cross-stage
improvement rule. Current classifications also make these results unsuitable
for validation claims.

## Base, pivot, and follow-through

`pivot_supply_clear` was the only variant to pass every absolute stage gate:

| Period | Trades | Return | Max DD | Expectancy | PF | Return/DD |
|---|---:|---:|---:|---:|---:|---:|
| 2017-2023 | 121 | 39.12% | 9.35% | 0.323R | 1.63 | 4.18 |
| Reused 2024 | 11 | 6.71% | 3.90% | 0.610R | 2.63 | 1.72 |
| Reused 2025 | 13 | 6.33% | 3.41% | 0.487R | 3.06 | 1.86 |

It nevertheless underperformed baseline return and return/drawdown in all three
periods. It is a lower-opportunity risk screen, not evidence of a
superperformance alpha filter. The simpler baseline is preferred under the
frozen decision rule.

Contraction plus volume dry-up produced an isolated 66.94% return with 8.84%
drawdown in reused 2025, but development returned only 4.40% with 51.71%
drawdown. Its largest 2025 winner supplied 75.0% of positive P&L. Shakeout was
similarly unstable: 14.71% in reused 2024 but -9.32% in 2025.

Breakout quality made 15.36% with 5.54% drawdown in development, lost 2.43% in
2024, and made 5.49% in 2025. The causal delayed follow-through improved the
development drawdown to 3.87% and returned 16.03%, but accepted only 55 trades;
it then lost 2.44% in 2024 and made 6.25% on nine trades in 2025. It was not
stable enough to advance.

The complete base rule selected 87, 8, and 1 signals after the earnings
blackout. The complete technical-leader conjunction selected none. Across all
48,510 unfiltered MODEL_0 signals, only one row met that entire conjunction and
it did not survive into an eligible test stage. This is direct evidence that
stacking every plausible quality condition created an unusably narrow model.

## Audit and decision

The final clean run produced all 72 expected stage/variant rows and 3,360
accepted ledger rows. The baseline reproduced V1 exactly. Audits found:

- zero missing daily marks;
- zero earnings-blackout or stage-boundary violations;
- zero 2R heat, four-position, or per-candidate risk violations;
- unique signal keys and valid RS score ranges; and
- 155 causal delayed confirmations: 100/25/30 by period, with two development
  confirmations rejected after the confirmation-date earnings recheck. Every
  retained confirmation occurred one to three sessions after its original
  signal.

No variant improved both return and return/drawdown versus baseline in two
periods. Cross-stage shortlist: zero. Mixed support: zero. Historical decision:
**REJECT**.

This rejects the frozen V2 technical rules as alpha additions; it does not prove
that relative strength, industry leadership, or discretionary base reading are
useless. The archive lacks delistings, historical membership, effective-dated
classifications, point-in-time fundamentals, and a fresh holdout. Production
and the immutable forward journal remain unchanged.

