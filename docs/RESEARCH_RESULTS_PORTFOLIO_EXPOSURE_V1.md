# PORTFOLIO_EXPOSURE_V1 engineering discovery result

Run date: 2026-09-13. Historical decision: **HOLD**.

> **SURVIVORSHIP-BIASED RESEARCH — NOT PRODUCTION EVIDENCE**

## Hypothesis and fixed design

The hypothesis was that limiting simultaneous initial risk, earning permission to expand exposure, or reducing new risk during drawdowns could reduce MODEL_0's portfolio drawdown without destroying its positive expectancy. Signals and exits were held fixed: next-session open with 5 bps adverse entry and exit slippage, signal-date 20-session-low initial stop, no target, and a maximum 40-session hold.

The simulation starts with an abstract 100R account (USD 58,700 at USD 587 per R). It marks open positions at each session open and close using only prices available by that time. Maximum drawdown percent is measured from the running mark-to-market equity high-water, not from closed trades alone. Initial risk remains charged until exit, same-session exits cannot fund earlier entries, the same ticker cannot overlap, and entry-date/signal-date/ticker order resolves excess candidates without looking at future performance.

To prevent outcome leakage, discovery signals stop on 2023-11-01 and all 40-session outcomes end by 2023-12-29. This leaves 2024–2025 untouched for this experiment. The purged sample contained 29,452 signals and 29,376 independently executable trades. The fixed 4R result was checked against the pre-existing four-position capacity allocator and selected the same trades.

## Evidence

| Portfolio rule | Trades | Avg risk/trade R | Expectancy/trade R | PF | Total return | CAGR | Daily MTM Max DD | Max DD R | Avg heat R | Stop-new-risk sessions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Fixed 1R heat | 57 | 1.000 | 0.633 | 2.299 | 36.09% | 4.51% | 8.34% | 10.068 | 0.990 | 0 |
| Fixed 2R heat | 123 | 1.000 | 0.593 | 2.198 | 72.96% | 8.16% | 6.97% | 12.742 | 1.975 | 0 |
| Fixed 3R heat | 189 | 1.000 | 0.388 | 1.721 | 73.26% | 8.19% | 16.82% | 26.854 | 2.949 | 0 |
| Fixed 4R heat baseline | 254 | 1.000 | 0.347 | 1.635 | 88.24% | 9.48% | 20.31% | 35.940 | 3.944 | 0 |
| Start 2R; unlock 3R/4R at +1R/+2R | 248 | 1.000 | 0.328 | 1.611 | 81.40% | 8.90% | 16.97% | 27.429 | 3.898 | 0 |
| Start 2R; unlock 3R/4R at +2R/+4R | 248 | 1.000 | 0.328 | 1.611 | 81.40% | 8.90% | 16.97% | 27.429 | 3.898 | 0 |
| DD modes at 2R/4R/6R | 27 | 0.796 | 0.782 | 3.134 | 21.11% | 2.78% | 5.41% | 6.890 | 0.362 | 1,482 |
| DD modes at 3R/6R/9R | 52 | 0.837 | 0.548 | 2.299 | 28.50% | 3.66% | 7.04% | 9.727 | 0.722 | 1,331 |
| Start 2R (+2R/+4R unlock) plus 2R/4R/6R DD modes | 26 | 0.865 | 0.964 | 4.743 | 25.05% | 3.25% | 5.82% | 7.629 | 0.409 | 1,413 |

The preregistered shortlist gate required no more than 10% daily mark-to-market drawdown, positive return, profit factor at least 1.20, at least 150 accepted trades, and no missing marks. No variant passed every condition. Fixed 1R and 2R missed only the 150-trade floor. The drawdown variants remained under 10% but stopped accepting risk for most of the later sample after reaching their fixed-R stop thresholds.

## Interpretation

- The current fixed-4-position baseline is not an unlimited buy-every-signal test, but it operated near full capacity and produced a 20.31% daily mark-to-market drawdown in this sample.
- Fixed 2R was the most useful discovery trade-off: it retained 72.96% total return with a 6.97% maximum drawdown. It did not pass the evidence gate because only 123 trades were accepted.
- Fixed 3R and both permanent earned-exposure ladders remained above the 10% drawdown objective. Both ladders reached 4R on 2017-03-03, so the different unlock thresholds produced identical later allocations; a brief successful opening period was not enough to control subsequent exposure.
- The drawdown modes controlled measured loss by stopping new risk, but became path-dependent shutdown rules rather than productive exposure controls. Their high expectancy and profit factor come from only 26–52 accepted trades and must not be compared as if they represented the full opportunity stream.
- Counts are not nested fixed cohorts: changing capacity changes which later signals receive a slot. That is why lower heat does not mechanically imply a monotonic return or drawdown sequence.

## Decision and limitations

Historical decision: **HOLD**. Fixed 2R is a research candidate worth testing on independent point-in-time data and in forward testing, but it is not validated and has not changed production. The current-symbol universe omits historical failures and delistings; no cash/notional, liquidity, sector concentration, or effective-dated universe model is included. Repeated use of this biased discovery sample increases overfitting risk, and a 10% historical result is not a future drawdown guarantee.

Boundary audit also found that the earlier `FILTER_AUDIT_V1` and `EXIT_STOP_GRID_V1` allowed late-2023 signals whose 40-session outcomes used early-2024 prices. Their numerical discovery results are preserved, but early 2024 is contaminated for those experiment versions and may not be called untouched. This V1 corrected the boundary before inspecting portfolio-overlay results.
