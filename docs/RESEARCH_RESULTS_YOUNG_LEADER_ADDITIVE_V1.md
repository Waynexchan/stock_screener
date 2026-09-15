# YOUNG_LEADER_ADDITIVE_V1 results

Historical decision: **REJECT**

Production effect: **NONE**

Research label: **SURVIVORSHIP- AND EARNINGS-SCHEDULE-BIASED ADAPTIVE RESEARCH; NO UNTOUCHED HOLDOUT**

## Hypothesis

The unchanged 90-219-valid-session leader breakout might improve the fixed-2R
MODEL_0 portfolio if those candidates received priority on the same entry date.
No signal threshold, stop, exit, cost, earnings blackout, or exposure rule was
retuned after `SUPERPERFORMANCE_PATHS_V1`.

## Evidence

The primary `additive_young_first` path improved development return from 42.78%
to 58.70%, reduced drawdown from 9.75% to 8.92%, and raised expectancy from
0.345R to 0.489R. In reused 2024 it improved return from 9.93% to 12.30% at
similar drawdown. It did not repeat in reused 2025: return fell from 28.01% to
27.00%, expectancy fell from 2.155R to 1.929R, and drawdown remained 13.07%.

| Variant | Development return / DD / trades | Reused 2024 | Reused 2025 |
|---|---:|---:|---:|
| MODEL_0 | 42.78% / 9.75% / 124 | 9.93% / 3.93% / 12 | 28.01% / 13.07% / 13 |
| Young standalone | 15.21% / 4.66% / 48 | 6.07% / 1.28% / 8 | 13.16% / 5.46% / 7 |
| Additive default ticker order | 41.64% / 9.82% / 124 | 9.93% / 3.93% / 12 | 28.01% / 13.07% / 13 |
| **Additive young-first** | **58.70% / 8.92% / 120** | **12.30% / 3.92% / 11** | **27.00% / 13.07% / 14** |
| Additive MODEL_0-first | 42.78% / 9.75% / 124 | 9.93% / 3.93% / 12 | 28.01% / 13.07% / 13 |

The primary beat both baseline return and return/drawdown in two periods and
had positive P&L after removing its largest winner in every period. It still
failed the frozen decision gate because reused-2025 drawdown exceeded 10%, the
largest winner supplied 74.39% of positive 2025 P&L, and neither declared
ordering neighbor supported the improvement direction.

## Portfolio-path diagnosis

The development uplift was not a direct accumulation of short-history winners.
Only three newly accepted development trades were short-history signals: IR
made 0.82R, DKNG lost 0.74R, and EXE made 0.25R. Their priority changed holding
capacity and subsequently produced 27 added versus 31 removed trades across the
whole path. The altered mature-trade sequence happened to admit ESI at +5.81R
and ADM at +7.20R. This is a large non-local portfolio-order effect, not clean
evidence that the young cohort itself supplied the incremental return.

In reused 2024, SN (+1.01R) and RDDT (+1.12R) received young-path priority, with
three total additions and four removals. In reused 2025, the only newly accepted
young trade was SARO at -1.00R. The 11.93R SNDK winner seen in the standalone
young path was not admitted by the additive primary portfolio. Its largest
winner remained the baseline's 23.51R RGLD trade, leaving the same 74.39%
outlier share.

Default ticker ordering slightly worsened development and exactly reproduced
baseline in the later periods. Explicit MODEL_0-first ordering reproduced the
baseline in all three periods. Therefore the apparent benefit exists only when
the scarce short-history signals are deliberately prioritized, and it is
unstable once their holding periods change subsequent capacity.

## Audit

- Preregistration: `bd96629`; gate-schema clarification: `1d30326`; final
  preregistration provenance commit: `83d36a9`.
- Clean implementation/run commit:
  `065dcfe094d86c5051a0149d570d2f44279ec322`; `run_git_dirty=false`.
- 15 result rows, 655 accepted-ledger rows, and 10,981 equity rows reconciled.
- Zero signal/outcome-boundary, next-session-entry, duplicate-key,
  earnings-blackout, risk, heat, position, left-censor, or missing-mark
  violations were found.
- Baseline and standalone-young signal counts, trades, return, drawdown,
  expectancy, and profit factor reproduced V1 within numeric serialization
  precision in all periods.
- All accepted additive-young candidates had an available first valid archive
  date; none was flagged as global-start left-censored. This remains an archive
  history proxy, not verified IPO provenance.

## Interpretation and decision

**REJECT.** The primary did not meet the complete preregistered gate, and both
ordering neighbors show that its attractive older-period result is path
dependent. All samples are reused, the archive is current-survivor biased, and
the earnings calendar is retrospective. Do not retune priority, age, volume,
or trend thresholds on these periods and do not promote the path to production.

The standalone short-history cohort may remain a labelled observation list for
newly arriving point-in-time evidence, but this backtest does not justify a
separate portfolio sleeve. The next credible research improvement is data:
point-in-time listing/universe history including delistings, immutable earnings
schedules, and point-in-time fundamental acceleration.
