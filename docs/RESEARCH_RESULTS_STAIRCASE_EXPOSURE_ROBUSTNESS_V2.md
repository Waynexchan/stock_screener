# Staircase Exposure Robustness V2

Date: 2026-09-13

Decision: **HOLD**

Evidence label: **SURVIVORSHIP-AND-EARNINGS-SCHEDULE-BIASED RESEARCH**

Production effect: **NONE**

## Question tested

Does a disciplined exposure staircase improve the existing swing-trade plan while keeping maximum daily mark-to-market drawdown at or below 10%?

Every cell used the same MODEL_0 signal, next-session-open entry with 5 bps adverse slippage, signal-date 20-session-low initial stop, no fixed target, 40-session maximum hold, and inclusive zero-to-ten-calendar-day pre-earnings signal blackout. The fixed-2R comparison always permitted at most two 1R positions.

Each staircase started at 2R. A net-positive realised exit batch added one 1R position slot for the next session. A zero-or-negative batch either reduced capacity by 1R (`STEP`) or reset it immediately to 2R (`RESET`). Separate hard ceilings of 4R, 6R, and 8R were frozen before execution. Existing valid positions were not force-liquidated after a contraction, but no new position was admitted until actual heat fitted the lower limit.

## Results

### Reused 2017–2023 development period

Signals ran from 2017-01-01 through 2023-11-01 and outcomes were allowed through 2023-12-29.

| Variant | Trades | Return | Max DD | Expectancy | Profit factor | Max positions | Gate |
|---|---:|---:|---:|---:|---:|---:|---|
| Fixed 2R | 124 | 42.78% | 9.75% | 0.345R | 1.691 | 2 | PASS |
| 4R STEP | 183 | 82.66% | 16.46% | 0.452R | 1.783 | 4 | FAIL |
| 4R RESET | 179 | 83.11% | 15.58% | 0.464R | 1.802 | 4 | FAIL |
| 6R STEP | 191 | 33.54% | 16.59% | 0.176R | 1.293 | 6 | FAIL |
| 6R RESET | 183 | 72.50% | 15.70% | 0.396R | 1.660 | 6 | FAIL |
| 8R STEP | 214 | 55.69% | 16.59% | 0.260R | 1.420 | 8 | FAIL |
| 8R RESET | 183 | 72.50% | 15.70% | 0.396R | 1.660 | 6 | FAIL |

All staircase variants failed because maximum drawdown exceeded the frozen 10% ceiling. The 8R RESET path happened not to reach seven or eight simultaneous positions, so it matched 6R RESET in this sample.

### Reused March 2024–October 2025 robustness period

Signals ran from 2024-03-01 through 2025-10-31 and outcomes were allowed through 2025-12-31. January and February 2024 remained excluded because earlier research contaminated them.

| Variant | Trades | Return | Max DD | Expectancy | Profit factor | Max positions | Gate |
|---|---:|---:|---:|---:|---:|---:|---|
| Fixed 2R | 27 | 13.13% | 4.84% | 0.486R | 2.285 | 2 | PASS |
| 4R STEP | 38 | 11.03% | 9.90% | 0.290R | 1.594 | 4 | PASS |
| 4R RESET | 37 | 10.59% | 9.94% | 0.286R | 1.570 | 4 | PASS |
| 6R STEP | 44 | 33.75% | 12.91% | 0.767R | 2.580 | 6 | FAIL |
| 6R RESET | 38 | 13.16% | 9.72% | 0.346R | 1.708 | 5 | PASS |
| 8R STEP | 44 | 33.75% | 12.91% | 0.767R | 2.580 | 6 | FAIL |
| 8R RESET | 38 | 13.16% | 9.72% | 0.346R | 1.708 | 5 | PASS |

The high-return 6R/8R STEP path again breached the 10% drawdown limit. The 4R variants and RESET variants that stayed under 10% did not repair the older-period failure.

## Interpretation

No adaptive variant passed both reused periods, so the preregistered decision is `HOLD`. The result does not show that repeated exposure expansion is useless: every variant retained positive expectancy and a profit factor above 1.2 in both periods. It does show that this particular realised-exit-batch staircase did not achieve the requested combination of higher exposure in strong states and maximum drawdown no greater than 10%.

The simpler fixed-2R baseline was the only rule that passed the numeric gate in both reused periods. That is evidence for retaining it as the research risk benchmark, not proof that it is a validated production strategy. The adaptive rank-one path was 4R RESET, but its older-period 15.58% maximum drawdown is a decisive failure rather than a near pass.

## Audit and limitations

- All six dynamic curves respected their 2R floor and frozen 4R, 6R, or 8R hard ceiling.
- The audit checked 1,523 accepted ledger rows across all cells and found zero accepted signals inside the earnings blackout.
- Every result reported zero missing daily marks.
- The run was made from clean implementation commit `3eed4e1ee5451b508368fd7cfc3dcbdd3a021d4e`; preregistration was commit `0df092a`.
- The current-symbol Yahoo archive has survivorship bias and lacks historical membership and delisted-symbol coverage.
- Earnings dates are retrospective event records, not point-in-time schedule snapshots known on each signal date.
- Both periods and the earnings proxy had already been inspected. There is no untouched historical holdout, and post-2023 results are robustness rather than validation.
- Capacity-limited results are path-dependent because simultaneous candidates are admitted in deterministic entry-date, signal-date, and ticker order.

## Reproduction

```powershell
python -m research.run_staircase_exposure_robustness --prices research/output/yahoo_engineering/prices.csv --benchmark research/output/yahoo_engineering/benchmark.csv --earnings research/output/yahoo_earnings_engineering/earnings.csv --earnings-metadata research/output/yahoo_earnings_engineering/download_metadata.json
```

Generated ledgers, daily equity curves, cross-period ranking, hashes, and machine-readable results are under `research/output/staircase_exposure_robustness_v2/`. The generated directory is intentionally ignored by Git.
