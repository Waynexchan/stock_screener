# EASY_EXECUTION_CROSS_VALIDATION_V1 result

Run date: 2026-09-13. Historical decision: **HOLD**.

> **SURVIVORSHIP-BIASED RESEARCH — NOT PRODUCTION EVIDENCE**

## Frozen design and coverage

The experiment crossed six initial stops, seven exits, and four portfolio-exposure rules: 6 x 7 x 4 = 168 discovery cells. The design was committed as `5ba5767` before any new outcomes were calculated. A pre-outcome clarification fixed fresh 100R stage accounts, a 20-day-low/40-session/fixed-4R comparison baseline, and conditional holdout isolation; its corrected identifier was committed as `60f24ab`.

The stop set covered the signal-date 20-day low, entry minus 1 ATR, prior/signal-day low minus 0.5 ATR or 1 ATR, a suggested 10-day low, and a suggested tighter-of-20-day-low-or-entry-minus-1-ATR rule. The exit set covered fixed 2R, 2.5R, 3R, and 4R targets with a 40-session backstop plus no-target exits after 20, 30, or 40 sessions. Exposure was fixed at 2R, 3R, or 4R, or started at 2R and permanently unlocked 3R/4R after realised-profit high-water marks of +2R/+4R.

All entries used the next available open plus 5 bps adverse slippage. Exits used 5 bps adverse slippage, stop-first same-bar handling, open fills for adverse stop gaps, target-level fills for favorable target gaps, at most four simultaneous positions, and daily open/close mark-to-market drawdown. There was no cash or maximum-notional constraint.

| Stage | Signal dates | Latest permitted outcome | Purpose |
|---|---|---|---|
| Discovery | 2017-01-01 to 2023-11-01 | 2023-12-29 | Iterative selection; not independent |
| Excluded | 2024-01-01 to 2024-02-29 | — | Previously contaminated boundary gap |
| Validation | 2024-03-01 to 2024-10-31 | 2024-12-31 | Frozen candidate check |
| Holdout | 2025-01-02 to 2025-10-31 | 2025-12-31 | One-time, conditional evaluation |

The archive contained 4,126,702 rows for 1,840 current symbols from 2016-01-04 through 2026-09-11. This is not point-in-time membership and omits historical failures and delistings.

## Integrity audit

- All 168 cells were unique and present: six stops, seven exits, and four exposure policies.
- All 168 discovery ledgers and equity curves were retained; no cell had a missing mark.
- Discovery entries ranged from 2017-01-04 to 2023-11-02 and exits ended no later than 2023-12-29.
- The discovery selection file was written before 2024 validation began.
- Validation entries ranged from 2024-03-04 to 2024-10-31 and exits ended no later than 2024-12-16.
- The validation result file was written before the 2025 gate was evaluated.
- One candidate passed validation, so the holdout was unlocked. Holdout entries ranged from 2025-01-03 to 2025-10-30 and exits ended no later than 2025-12-11.
- No trade exceeded its declared 20-, 30-, or 40-session limit.
- Discovery, validation, and holdout each started from a fresh 100R account.

## Discovery and frozen selection

Only one cell met the complete frozen discovery gate: no more than 10% drawdown, positive return and expectancy, profit factor at least 1.20, at least 100 accepted trades, no missing marks, and positive returns in both discovery subperiods.

| Stop | Exit | Exposure | Trades | Return | CAGR | Max DD | Exp/trade | PF | Payoff | Avg hold | 2017–20 | 2021–23 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20-day low | No target; 40 sessions | Fixed 2R | 123 | 72.96% | 8.16% | 6.97% | 0.593R | 2.198 | 3.001 | 28.24 | 49.40% | 15.77% |

The adjacent 30-session version supported the selection under the predeclared relaxed-neighbour rule, but missed the main drawdown gate at 10.50%. The 20-session version reached 10.11% drawdown. No other cell combined positive expectancy with drawdown at or below 10%.

High-return cells using tighter ATR stops, 3R/4R heat, or the earned-exposure ladder had materially larger drawdowns. The highest discovery return was 166.94% for the tighter hybrid stop, 40-session exit, and earned ladder, but its maximum drawdown was 28.11%. Fixed-target families also missed the drawdown objective; the best risk-adjusted fixed-target cell still reached 14.16% drawdown.

## Frozen post-2023 results

| Stage / role | Stop / exit / exposure | Trades | Return | CAGR | Max DD | Exp/trade | PF | Payoff | Avg hold | Frozen gate |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2024 selected | 20-day low / 40 sessions / fixed 2R | 12 | 6.74% | 8.23% | 4.03% | 0.561R | 2.420 | 1.728 | 31.33 | PASS |
| 2024 baseline | 20-day low / 40 sessions / fixed 4R | 23 | 23.64% | 29.37% | 4.58% | 1.028R | 4.261 | 2.273 | 33.39 | Context only |
| 2025 selected | 20-day low / 40 sessions / fixed 2R | 13 | 26.94% | 27.30% | 13.29% | 2.072R | 8.521 | 3.787 | 34.31 | **FAIL: DD > 10%** |
| 2025 baseline | 20-day low / 40 sessions / fixed 4R | 32 | 23.35% | 23.66% | 14.14% | 0.730R | 2.607 | 2.300 | 28.03 | Context only |

The selected 2R rule reduced 2025 drawdown by only 0.85 percentage points versus fixed 4R and both exceeded the 10% objective. Its 2025 return was 3.59 percentage points higher, but this came from only 13 accepted trades. In 2024 the fixed-4R baseline earned much more while drawdown stayed below 5%, illustrating strong regime and scarce-slot sensitivity rather than a stable fixed-2R advantage.

The engine produced 4,429 independently executable validation candidates but capacity admitted only 12 selected-rule trades; the holdout produced 4,492 candidates but admitted 13. Same-day candidates are accepted deterministically by signal date and ticker when no separate point-in-time rank is supplied. These small, path-dependent portfolio samples are a material limitation.

## Decision

The simple candidate is worth continuing only as a **research/forward-test hypothesis**: 20-day-low initial stop, no fixed-R target, 40-session maximum hold, and fixed 2R portfolio heat. It is easier to execute and outperformed the discovery risk-adjusted alternatives, and it passed the frozen 2024 gate. It did not meet the central requirement in the one-time 2025 holdout because maximum drawdown was 13.29%.

Therefore no stop/exit/exposure combination is validated as maintaining maximum drawdown at or below 10%, and no production or existing forward-test rule changes. A next experiment should be preregistered separately and address deterministic candidate ranking, a cash/maximum-notional cap, gap-risk-aware position sizing, and a non-permanent exposure reset. It should use point-in-time universe membership including delistings before any production review.

Input hashes:

- Price archive: `dbb63ab89bc1aba69a62452fe2d267aca9cdf6ef8ec9d3d214f8e847d9fa0f61`
- SPY benchmark: `2f23c2f096c0f712ab102a938b5aa0e04dad78b7345355b525a9b979a08e09f9`
- Experiment: `3a3e09a6b82c2f876d0f72cca1e4ad3f511dd9337eb17f90885c66bc64b23430`
- Amendment: `708fd27851e0d5d4db95fb54162d867920e7c013836d27b7e6545a68711d1404`
- Discovery grid: `448860cbfabc0e599653989670afab4c80b3adf37e4e6319c4cf08596600c931`
- Frozen selection: `ea13bd7c5bf8b6597516cb3214f446df5a4fad83d254bcff1db802c19b09899c`
- Validation result: `a15ad78785b3bd4cff4fb74e6df9c2f97adefcc052b1e53ae121b41a327643c6`
- Holdout result: `7eed43e5c9937395c9323e7d6b129de8025c96ce807a89dee5a093b00535cf6f`
- Run manifest: `7d0b472ecea39533af229d79a326fbed9220e46e3d71b16fa500535643844c55`
