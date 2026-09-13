# EXIT_STOP_GRID_V1 engineering discovery result

Run date: 2026-09-13. Historical decision: **HOLD**.

> **SURVIVORSHIP-BIASED RESEARCH — NOT PRODUCTION EVIDENCE**

## Hypothesis and fixed design

This experiment tests whether a fixed profit target or a tighter ATR-based initial stop improves the MODEL_0 baseline. The signal remains the same false-to-true Stage 2 transition. Entry is the next session open plus 5 bps adverse slippage; exit also applies 5 bps adverse slippage. Maximum holding time remains 40 sessions, same-bar ambiguity is stop-first, stop gaps fill at the open, and favorable target gaps fill only at the target level.

ATR20 is the simple mean of True Range through the signal date, matching production's indicator definition. Because entry occurs next session, “previous-day low” means the signal-day low. Every initial stop is fixed after entry. Each target is calculated from that combination's slipped entry and initial stop:

```text
1R = slipped entry - initial stop
target = slipped entry + target multiple x 1R
```

The five stops crossed with no target, 2R, 2.5R, and 3R produce 20 preregistered combinations. The 2017–2023 discovery sample contains 30,129 signals. The 2024–2025 period was not evaluated as a holdout. A post-run boundary audit found that late-2023 discovery signals used up to 40 sessions of early-2024 prices for their outcomes, so early 2024 is contaminated for this experiment version and may not be described as untouched. The numerical discovery results are preserved rather than rewritten.

## Complete results

| Stop | Target | Trades | Win rate | Expectancy R | Delta R | Profit factor | Payoff | Max DD R | Avg hold |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20-day low | None | 259 | 39.8% | 0.348 | — | 1.644 | 2.490 | 22.284 | 27.4 |
| 20-day low | 2R | 350 | 40.9% | 0.005 | -0.344 | 1.008 | 1.459 | 34.477 | 20.3 |
| 20-day low | 2.5R | 330 | 39.4% | 0.061 | -0.287 | 1.104 | 1.698 | 29.624 | 21.4 |
| 20-day low | 3R | 292 | 41.1% | 0.062 | -0.287 | 1.113 | 1.596 | 35.952 | 24.3 |
| Entry - 0.5 ATR | None | 911 | 10.5% | 0.226 | -0.122 | 1.229 | 10.435 | 101.418 | 7.6 |
| Entry - 0.5 ATR | 2R | 3,521 | 32.8% | -0.082 | -0.431 | 0.887 | 1.818 | 300.213 | 2.0 |
| Entry - 0.5 ATR | 2.5R | 3,034 | 29.0% | -0.059 | -0.408 | 0.923 | 2.259 | 262.980 | 2.3 |
| Entry - 0.5 ATR | 3R | 2,712 | 26.3% | -0.026 | -0.375 | 0.967 | 2.712 | 181.808 | 2.5 |
| Entry - 1 ATR | None | 519 | 20.2% | 0.242 | -0.106 | 1.284 | 5.064 | 57.683 | 13.5 |
| Entry - 1 ATR | 2R | 1,310 | 34.8% | -0.015 | -0.363 | 0.979 | 1.833 | 118.411 | 5.3 |
| Entry - 1 ATR | 2.5R | 1,091 | 30.4% | -0.006 | -0.354 | 0.993 | 2.269 | 75.112 | 6.4 |
| Entry - 1 ATR | 3R | 972 | 26.1% | -0.031 | -0.379 | 0.962 | 2.718 | 106.635 | 7.2 |
| Signal low - 0.5 ATR | None | 424 | 26.4% | 0.241 | -0.108 | 1.305 | 3.637 | 41.778 | 16.6 |
| Signal low - 0.5 ATR | 2R | 734 | 36.1% | 0.010 | -0.339 | 1.015 | 1.796 | 60.791 | 9.5 |
| Signal low - 0.5 ATR | 2.5R | 644 | 32.3% | 0.024 | -0.324 | 1.034 | 2.167 | 46.107 | 10.8 |
| Signal low - 0.5 ATR | 3R | 597 | 29.5% | -0.001 | -0.350 | 0.998 | 2.387 | 56.562 | 11.7 |
| Signal low - 1 ATR | None | 349 | 31.5% | 0.138 | -0.210 | 1.199 | 2.604 | 40.691 | 20.2 |
| Signal low - 1 ATR | 2R | 498 | 38.8% | 0.045 | -0.303 | 1.072 | 1.694 | 44.897 | 14.1 |
| Signal low - 1 ATR | 2.5R | 450 | 35.8% | 0.058 | -0.290 | 1.088 | 1.954 | 33.883 | 15.6 |
| Signal low - 1 ATR | 3R | 394 | 34.3% | 0.054 | -0.294 | 1.082 | 2.075 | 48.747 | 17.8 |

Trade counts differ because earlier exits release one of the four portfolio slots for later signals. The same ticker cannot occupy two slots at once. This is an end-to-end capacity result, not a comparison on a fixed accepted-trade cohort. Sizing normalizes every accepted trade to USD 587 initial risk but does not model portfolio cash or a maximum notional exposure; very tight ATR stops can therefore imply unrealistic share counts.

## Interpretation and decision

- The original no-target, 20-day-low baseline remained the strongest combination on expectancy, profit factor, and maximum drawdown. It exactly reproduced the earlier 0.348480R result.
- No fixed 2R, 2.5R, or 3R target improved the baseline. With the same 20-day stop, fixed targets reduced expectancy to 0.005R–0.062R and increased maximum drawdown to 29.624R–35.952R.
- Tighter ATR stops produced more turnover but worse drawdown. Entry - 0.5 ATR with no target had a 10.5% win rate and 10.435 payoff ratio, yet expectancy fell to 0.226R and maximum drawdown rose to 101.418R. High payoff alone therefore did not create a superior portfolio result.
- All 20 combinations failed the preregistered numeric shortlist gate. Historical decision: **HOLD**; keep every variant research-only and do not alter production.

The current-universe Yahoo archive excludes historical failures and delistings, so all figures may be materially distorted by survivorship bias. Twenty related comparisons on one discovery sample also create parameter-mining risk. The absence of a cash/notional cap is an additional limitation for narrow stops. These results reject none of the production rules and validate none of the tested exits or stops.
