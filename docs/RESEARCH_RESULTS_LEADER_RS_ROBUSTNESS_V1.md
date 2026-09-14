# Leader and Relative-Strength Robustness V1

Status: **HOLD — RESEARCH_ONLY**

Production effect: **NONE**

Data label: **SURVIVORSHIP-, EARNINGS-SCHEDULE-, AND
CLASSIFICATION-BIASED RESEARCH — NO UNTOUCHED HOLDOUT**

## Question

Can a more Mark Minervini/Jesse Livermore-style technical-leadership layer
improve the existing earnings-eligible MODEL_0 swing strategy, and do fixed
low-beta or Utilities exclusions add value after first selecting technical
leaders?

This is an adaptive robustness study, not independent validation. Every
2017-2025 period had already been inspected by earlier work. Point-in-time
fundamentals were unavailable, so EPS/sales acceleration, margins, estimates,
ownership, and institutional sponsorship were explicitly
`BLOCKED_DATA_NOT_READY` rather than approximated with current data.

## Frozen design

The study was preregistered at commit `48512fb` and run from clean implementation
commit `d914f77`. It tested 17 fixed variants after the mandatory inclusive
zero-to-ten-calendar-day pre-earnings blackout.

The MarketSmith-style proxy is not MarketSmith's proprietary RS Rating. It uses
four non-overlapping 63-session returns with weights 40%, 20%, 20%, and 20%,
then ranks every eligible current-archive symbol cross-sectionally from 1 to 99
on each signal date before applying Stage 2 or candidate filters. Other causal
features were a stock/SPY RS line near its 252-session high, current-industry
median RS rank, a 50-session up/down-volume ratio, distance from the 252-session
price high, and the existing 126-session rolling beta.

All variants used next-session-open execution plus five basis points, a fixed
signal-date 20-session-low stop, no target, a 40-session exit, stop-first
same-bar handling, fixed 2R heat, 1R per trade, and at most four positions.

## Main results

| Period | Variant | Trades | Return | Max DD | Exp/trade | PF | Return/DD |
|---|---|---:|---:|---:|---:|---:|---:|
| 2017-2023 | Baseline | 124 | 42.78% | 9.75% | 0.345R | 1.69 | 4.39 |
| 2017-2023 | RS proxy >=80 | 142 | 18.77% | 16.87% | 0.132R | 1.20 | 1.11 |
| 2024 reused | Baseline | 12 | 9.93% | 3.93% | 0.828R | 3.31 | 2.53 |
| 2024 reused | RS proxy >=80 | 12 | 14.73% | 3.21% | 1.228R | 8.10 | 4.59 |
| 2025 reused | Baseline | 13 | 28.01% | 13.07% | 2.155R | 8.82 | 2.14 |
| 2025 reused | RS proxy >=80 | 15 | 31.48% | 14.62% | 2.099R | 4.82 | 2.15 |

`RS proxy >=80` was the only mixed-support variant: it beat baseline return and
return/drawdown in two periods. It nevertheless failed development badly, had
negative late-development return, breached the drawdown gate, and still derived
59.2% of 2025 positive P&L from its largest winner. It therefore did not enter
the cross-stage shortlist.

Threshold behavior was unstable rather than monotonic. `>=85` made 25.41% in
development but lost 1.27% in reused 2025. `>=90` lost 10.81% in development,
made 5.75% in reused 2024, and made 12.22% in reused 2025. This does not support
claiming that a higher RS cutoff reliably produces higher performance.

The standalone RS-line-near-high rule reduced development return to 23.81% and
had 16.00% drawdown in reused 2025. Industry RS >=80 reduced reused-2025
drawdown to 5.06%, but returned only 12.76% and failed development at 16.85%
drawdown. Up/down volume >=1.25 made 47.02% in development but lost 2.35% in
reused 2024 and reached 14.32% drawdown in reused 2025.

## Technical leader profile, Utilities, and beta

The full technical leader profile was too restrictive and did not improve
expectancy. It accepted 78, 6, and 12 trades across the three periods and
returned 6.33%, 2.72%, and 3.51%. Low drawdown came with very low opportunity
capture, and reused 2024 missed the frozen eight-trade floor.

Removing Utilities from that profile improved development return from 6.33% to
13.45% and slightly reduced development drawdown from 7.70% to 7.31%, but it
left only six reused-2024 trades and reduced reused-2025 return from 3.51% to
3.21%. This is too sparse and unstable for a production exclusion.

Requiring beta >=0.8 was clearly worse: 0.73% return and 10.48% drawdown in
development, 2.29% on five trades in reused 2024, and a 0.69% loss in reused
2025. Beta measures market sensitivity, not leadership, and this test supplies
no evidence for using it as an alpha gate. A no-low-beta or no-Utilities rule
may still be a personal mandate, but it should be labelled as such rather than
presented as validated performance logic.

## Audit and decision

The run produced all 51 expected stage/variant rows. Across 2,490 accepted
ledger rows there were zero earnings-blackout violations and zero missing daily
marks. Proxy scores stayed within 1-99 where available, signal keys were unique,
and the five mutually exclusive score buckets reconciled to all scored signals.
The baseline matched the earlier mandatory-blackout results exactly.

No variant passed every stage gate and the cross-stage shortlist count is zero.
Historical decision: **HOLD**. Do not change production or the immutable
forward journal.

The most defensible next research step is not another threshold search. It is to
obtain point-in-time universe/delisting coverage and fundamental histories,
then preregister one simpler leader model for genuinely unseen forward data.

