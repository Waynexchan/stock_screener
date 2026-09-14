# Earnings Blackout Full Retest V1

Date: 2026-09-14

Decision: **HOLD**

Evidence label: **SURVIVORSHIP-AND-EARNINGS-SCHEDULE-BIASED RESEARCH**

Production effect: **NONE**

## Question and scope

The user will not open a position when an earnings event falls from the signal date through ten calendar days later, inclusive. This adaptive retest recalculated every earlier filter, stop, exit, and exposure setting that did not already enforce that restriction.

The blackout was applied to the signal universe before filter selection, trade simulation, deterministic candidate ordering, position-capacity allocation, and exposure-state transitions. The source experiments' execution assumptions, periods, gates, and other parameters remained unchanged.

| Suite | Settings retested |
|---|---:|
| MODEL_0 baseline plus filter ablations | 8 |
| Initial stop × exit grid | 20 |
| Standalone portfolio exposure policies | 9 |
| Stop × exit × exposure cross | 180 |
| Easy-execution stop × exit × exposure cross | 168 |
| **Total** | **385** |

The earlier earnings V1 blackout cells and all seven staircase V2 cells already enforced the same rule and were not counted as new independent runs.

## Blackout effect on signal availability

- The wider 2017–2023 filter/exit-stop sample fell from 30,129 to 26,084 signals: 4,045 exclusions, or 13.4%.
- The boundary-purged 2017–2023 portfolio sample fell from 29,452 to 25,456 signals: 3,996 exclusions. There were 25,413 executable trade paths.
- Reused 2024 fell from 4,445 to 3,759 signals: 686 exclusions.
- Reused 2025 fell from 4,509 to 3,764 signals: 745 exclusions.

## Filter audit

The blackout baseline accepted 257 capacity-limited trades at 0.350R expectancy, 1.653 profit factor, and 21.64R maximum closed-trade drawdown.

| Rule | Signals retained | Trades | Expectancy | Delta vs blackout baseline | Profit factor | Max DD R |
|---|---:|---:|---:|---:|---:|---:|
| Blackout baseline | 26,084 | 257 | 0.350R | — | 1.653 | 21.64R |
| Within extension limits | 25,740 | 262 | 0.367R | +0.018R | 1.671 | 21.64R |
| Volume ratio ≥0.30 | 25,975 | 260 | 0.327R | -0.022R | 1.592 | 21.64R |
| ADR 1%–10% | 25,622 | 266 | 0.313R | -0.037R | 1.551 | 23.64R |
| Exclude Utilities | 25,353 | 267 | 0.263R | -0.087R | 1.456 | 34.02R |
| Long-term RS ≥75 | 10,897 | 282 | 0.222R | -0.128R | 1.364 | 27.35R |
| Recent RS ≥70 | 10,005 | 258 | 0.148R | -0.202R | 1.269 | 36.85R |
| Exclude beta below 0.8 | 18,110 | 281 | 0.118R | -0.232R | 1.192 | 28.57R |

The earlier apparent benefit from excluding Utilities did not survive the user's earnings restriction. Excluding low-beta stocks also remained unsupported. These are historical research results, not instructions to include unwanted Utilities or low-beta stocks in a real portfolio.

## Stops and exits

No 20-cell stop/exit variant met the source shortlist improvement rule. The 20-day-low, no-target, 40-session baseline produced 0.350R expectancy, 1.653 profit factor, and 21.64R maximum closed-trade drawdown.

Entry minus 1ATR with no target had the highest raw expectancy at 0.393R, but improved expectancy by only 0.044R and more than doubled maximum drawdown to 46.00R. It therefore was not a risk-controlled improvement.

Fixed targets remained weak. The best fixed-target result was previous-day low minus 1ATR with a 3R target at 0.134R expectancy and 1.203 profit factor. Fixed-target expectancy ranged from -0.052R to 0.134R, materially below the no-target baselines.

## Portfolio exposure and 180-cell cross

None of the nine standalone exposure policies passed its frozen gate. Fixed 2R returned 42.78% with 9.75% maximum daily mark-to-market drawdown, but accepted only 124 trades versus the 150-trade gate. Fixed 3R and 4R reached 10.95% and 16.18% drawdown. Drawdown overlays remained below 10% but achieved that partly by admitting only 26–55 trades.

No cell passed the complete 180-cell cross. The earlier lone shortlist—20-day-low stop, 2R target, earned exposure plus the 2R/4R/6R drawdown overlay—fell to 119 trades, 0.179R expectancy, 21.24% return, and 5.04% drawdown; its later development return was -3.19%, so it failed stability and sample-size requirements.

## Easy-execution 168-cell cross

Two of 168 development cells passed. Both used a 20-day-low stop, no fixed target, and fixed 2R heat.

| Maximum hold | Development trades | Return | Max DD | Expectancy | PF | Reused 2024 return / DD | Reused 2025 return / DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| 30 sessions | 161 | 64.71% | 9.08% | 0.402R | 1.836 | 0.76% / 4.73% | 17.50% / 12.86% |
| 40 sessions | 124 | 42.78% | 9.75% | 0.345R | 1.691 | 9.93% / 3.93% | 28.01% / 13.07% |

Both passed the reused 2024 numeric gate and both failed reused 2025 because drawdown exceeded 10%. The 30-session rule improved substantially over its no-blackout development result, while the 40-session rule became weaker in development but modestly stronger in both later periods. This instability is a warning against treating either setting as proven.

## Audit and evidence limits

- All 385 configured settings were reported: 8 + 20 + 9 + 180 + 168.
- The accepted portfolio-ledger audit covered 163,076 rows and found zero intersection with each suite's blackout rejection ledger.
- All 363 portfolio result rows across the 9-, 180-, and staged 168-cell suites reported zero missing daily marks.
- Earnings input hash and declared date coverage were verified independently by every runner. Missing coverage fails the run rather than being treated as no event.
- Preregistration commit: `a677f75`. Final labelled run commit: `e933f16f237730b29e75296afa01da95745100ac`, clean working tree.
- The universe is a current-symbol Yahoo archive and has survivorship bias, no delisted-symbol history, and incomplete corporate-action provenance.
- Earnings dates were retrieved retrospectively; they are not immutable point-in-time schedule snapshots known ten days before each event.
- All price periods and source results were already inspected. Reused 2024 and 2025 results are explicitly `REUSED_CONTAMINATED`, not independent validation or untouched holdout.
- Capacity-limited results remain path-dependent on deterministic entry-date, signal-date, and ticker order.

## Decision

The historical decision remains `HOLD`. Applying the user's real-world earnings rule materially changes which filters and holding periods appear attractive, but no setting demonstrated positive expectancy with maximum drawdown at or below 10% across all reused periods. Production and the immutable forward journal remain unchanged.

Generated manifests, rejection ledgers, all 385 result rows, accepted-trade ledgers, and daily equity curves are under `research/output/earnings_blackout_full_retest_v1/` and are intentionally ignored by Git.
