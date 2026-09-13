# COMBINED_EXIT_EXPOSURE_GRID_V1 engineering discovery result

Run date: 2026-09-13. Historical decision: **HOLD**.

> **SURVIVORSHIP-BIASED RESEARCH — NOT PRODUCTION EVIDENCE**

## Hypothesis and preregistration

Stops, targets, and portfolio exposure can interact because each exit changes when a scarce risk slot becomes available. The experiment therefore crossed all five previously declared initial stops, four targets, and nine exposure policies: 5 x 4 x 9 = 180 cells. The matrix, outcome boundary, metrics, gate, stability split, and ranking were committed as `04365b7` before combined outcomes were inspected.

Signals execute at the next available open with 5 bps adverse entry and exit slippage. Stops are fixed at entry, favorable target gaps fill only at the target, same-bar stop/target ambiguity is stop-first, and maximum holding time is 40 sessions. The portfolio starts at 100R, permits at most four positions, charges allocated initial R until exit, prevents same-ticker overlap, and does not allow a same-session exit to fund an earlier entry. Drawdown uses daily open/close mark-to-market equity.

Discovery signals end on 2023-11-01 and every outcome ends by 2023-12-29. The 2024–2025 holdout was not evaluated. The run used 29,452 signals and prepared 29,448 executable signal paths. All 180 cells, 180 ledgers, and 180 daily equity curves were retained. All 20 fixed-4R cells matched the pre-existing capacity allocator exactly, and no cell had a missing mark.

## Evidence

Only one cell passed the complete preregistered gate of no more than 10% maximum drawdown, positive return and expectancy, profit factor at least 1.20, at least 150 accepted trades, no missing marks, and positive returns in both 2017–2020 and 2021–2023.

| Cell | Trades | Exp R | PF | Payoff | Return | CAGR | Max DD | 2017–20 | 2021–23 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20-day low, no target, fixed 4R baseline | 254 | 0.347 | 1.635 | 2.519 | 88.24% | 9.48% | 20.31% | 52.02% | 23.83% |
| 20-day low, no target, fixed 2R | 123 | 0.593 | 2.198 | 3.001 | 72.96% | 8.16% | 6.97% | 49.40% | 15.77% |
| **20-day low, 2R target, earned 2R plus 2/4/6R DD modes** | **170** | **0.194** | **1.573** | **1.611** | **33.02%** | **4.17%** | **4.65%** | **28.08%** | **3.85%** |
| Same shortlist policy, 2.5R target | 31 | 0.091 | 1.192 | 2.168 | 2.81% | 0.40% | 5.62% | 2.81% | 0.00% |
| Same shortlist policy, 3R target | 43 | 0.075 | 1.211 | 1.682 | 3.21% | 0.45% | 5.68% | 3.21% | 0.00% |
| 20-day low, 2R target, fixed 4R | 343 | -0.010 | 0.983 | 1.460 | -3.45% | -0.50% | 29.47% | 19.09% | -18.93% |
| Entry - 0.5 ATR, no target, fixed 2R | 433 | 0.334 | 1.343 | 11.026 | 144.43% | 13.66% | 37.30% | 30.35% | 87.51% |
| Signal low - 0.5 ATR, no target, fixed 2R | 209 | 0.358 | 1.459 | 3.799 | 74.87% | 8.33% | 15.89% | 70.12% | 2.79% |

Across the whole grid, 53 cells stayed at or below 10% drawdown, 108 had at least 150 trades, 56 had profit factor at least 1.20, and 32 were positive in both discovery subperiods. Only the bold cell satisfied all conditions together.

The shortlist cell allocated 1R to 81 trades and 0.5R to 89 trades. It spent 495 sessions in normal mode, 587 reduced, 629 defensive, and 48 in stop-new-risk. Its total return was 55.22 percentage points below the fixed-4R baseline and expectancy was lower by 0.153R per accepted trade.

## Interpretation

- The complete cross found a real portfolio interaction: a fixed 2R target was unprofitable with fixed 4R exposure, but became positive when paired with causal earned-exposure and drawdown sizing.
- The one passing cell is complex and sits at a sharp target optimum. Changing its target from 2R to 2.5R or 3R reduced the sample to 31–43 trades, produced no later-period gain, and caused long shutdowns. This lack of neighboring support is an overfitting warning.
- Fixed 2R with the original no-target/20-day-low exit remains the simpler and more stable trade-off, but its 123 trades miss the predeclared 150-trade floor.
- Very tight stops can generate high total return or payoff while producing unacceptable drawdown. Entry - 0.5 ATR with fixed 2R heat reached 144.43% return and 11.03 payoff, but also 37.30% drawdown.
- The passing cell's 2021–2023 return was only 3.85%, much weaker than its earlier 28.08%. A positive split alone does not establish stable edge.

## Decision and limitations

Historical decision: **HOLD**. The passing cell is a discovery shortlist, not a frozen forward-test strategy. It should not advance until it survives independent point-in-time validation and stronger robustness checks. The 180 related comparisons create substantial multiple-testing risk, and the isolated optimum makes that risk concrete.

The current-symbol archive omits historical failures and delistings and has no point-in-time universe membership, effective-dated classification, cash/notional cap, partial-fill model, or independent corporate-action ledger. Tight ATR stops may imply unrealistic share counts. These limitations can materially distort both return and drawdown, so this experiment validates no production rule and guarantees no future 10% drawdown ceiling.

Input hashes:

- Price archive: `dbb63ab89bc1aba69a62452fe2d267aca9cdf6ef8ec9d3d214f8e847d9fa0f61`
- SPY benchmark: `2f23c2f096c0f712ab102a938b5aa0e04dad78b7345355b525a9b979a08e09f9`
- Generated 180-cell summary: `57f3b9e61d65fef8549813065d18e34116c0bcd50ae3af2dac505d7bc013ad8c`
