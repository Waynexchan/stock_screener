# FILTER_COMBINATION_AUDIT_V1 results

## Decision

**REJECT** the frozen hard-filter matrix. None of the 80 variants entered the
preregistered shortlist. This is an adaptive diagnostic on reused,
survivorship-biased data, not an untouched validation and not evidence for a
production change.

The main transaction bottleneck is portfolio capacity, not a shortage of raw
signals. With fixed 2R maximum heat, 1R per trade, and a 40-session maximum
hold, the portfolio can normally carry only two simultaneous positions even
though the configured position-count ceiling is four.

## Frozen design

- 64 complete subsets of six components: dual RS, extension, strong industry,
  pivot/supply, breakout demand, and signal-close SPY above SMA50.
- 16 additional single filters covering RS, volume, ADR, beta, Utilities,
  industry, base, contraction, shakeout, and base stage.
- Signal at close; next available session open plus 5 bps; 20-session-low
  initial stop; no target; 40-session maximum hold; 5 bps exit slippage;
  stop-first same-bar rule.
- Mandatory retrospective zero-to-ten-calendar-day pre-earnings blackout.
- Fixed 2R heat, 1R per trade, maximum four positions, and default
  entry-date/signal-date/ticker candidate order.
- Development required at least 75 trades, positive return and expectancy,
  profit factor at least 1.2, maximum drawdown at most 10%, positive early and
  late returns, and zero missing marks. Each reused period required at least
  eight trades, positive return and expectancy, profit factor at least 1.1,
  maximum drawdown at most 10%, and zero missing marks.
- A combination could shortlist only with at most three components, every
  stage gate passed, return and return/drawdown above baseline in at least two
  periods, no period with the largest winner above 50% of positive P&L, and
  every included component adding return and return/drawdown versus its
  leave-one-out parent in at least two periods.

Preregistration commit: `3f8d0a6`. The successful clean run used
`9fce57ee3c2e5d902037edcdeb3e1933f124b109`.

This is the complete audit of the 22 frozen, mechanically observable filter
proxies in this experiment, not literal production parity for every canonical
decision field. Stage 2 is part of MODEL_0 signal construction rather than an
optional overlay here. Minimum price/volume, stale-data checks, valid stops,
portfolio permission, heat, and position count are safety or execution
constraints rather than alpha filters. The richer production market state,
manual setup integrity, sister-stock confirmation, observed structural target,
and fundamental acceleration could not be reconstructed point in time. Those
distinct rules remain unassessed; a failed proxy is not grounds to remove a
production safety control.

## Why accepted transaction count is low

| Period | Raw MODEL_0 signals | After earnings blackout | Executable candidates | Accepted trades | Acceptance of candidates |
|---|---:|---:|---:|---:|---:|
| 2017–2023 development | 29,452 | 25,456 | 25,413 | 124 | 0.49% |
| Reused 2024 | 4,445 | 3,759 | 3,755 | 12 | 0.32% |
| Reused 2025 | 4,509 | 3,764 | 3,757 | 13 | 0.35% |

In development, 25,200 candidates were rejected for `MAX_HEAT` and 89 for an
already-open same ticker. The corresponding counts were 3,735/8 in 2024 and
3,733/11 in 2025. The baseline is therefore capacity constrained: it has many
signals but very few free portfolio slots. A hard filter changes which trades
enter the path and can even increase accepted trades by admitting shorter-lived
positions; accepted count is not a monotonic measure of signal abundance.

Increasing heat is not a free remedy. The already-completed mandatory-blackout
exposure audit increased development trades from 124 at fixed 2R to 253 at
fixed 4R, but maximum drawdown rose from 9.75% to 16.18%. Reused-2025 fixed 4R
accepted 32 trades and reached 13.91% drawdown.

## Baseline

| Period | Trades | Return | Max DD | Expectancy | Profit factor | Return/DD | Largest winner share |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2017–2023 development | 124 | 42.78% | 9.75% | 0.345R | 1.691 | 4.388 | 12.44% |
| Reused 2024 | 12 | 9.93% | 3.93% | 0.828R | 3.309 | 2.527 | 25.12% |
| Reused 2025 | 13 | 28.01% | 13.07% | 2.155R | 8.821 | 2.144 | 74.39% |

The 2025 baseline failed the 10% drawdown and 50% largest-winner-contribution
controls. Its headline return is heavily dependent on one winner.

## Individual-filter findings

The return triplets below are development / reused 2024 / reused 2025. Labels
describe this frozen proxy only; they do not validate or invalidate a distinct
manual or production implementation.

| Filter | Return triplet | Finding |
|---|---:|---|
| Recent RS >=70 | 3.62% / 10.03% / 25.96% | Mixed and much worse in development; not a supported hard gate. |
| Long-term RS >=75 | 17.28% / 11.04% / 8.27% | Mixed; improved 2024 only. |
| Recent RS >=70 plus long-term RS >=75 | -2.28% / 3.83% / 6.19% | Negative/no value; negative development expectancy. |
| MarketSmith-style proxy >=80 | 18.77% / 14.73% / 31.48% | Only single filter to beat baseline return and return/DD in two periods, but failed development, 2025 drawdown, and outlier controls. It remains a ranking hypothesis, not a hard gate or proprietary MarketSmith score. |
| RS proxy rising over 21 and 63 sessions | -6.71% / 7.32% / 28.58% | Mixed; negative development expectancy and 22.51% drawdown. |
| RS line leads price high | 12.34% / 3.43% / -2.31% | Inconclusive and sparse: 67 / 4 / 10 trades. |
| Volume ratio >=0.30 | 31.69% / 9.93% / 28.01% | Retained 99.6% or more of signals and added no stable value; ineffective threshold. |
| ADR 1%–10% | 46.47% / 9.93% / 26.13% | Retained 98% or more of signals; little discrimination and no robust risk-adjusted gain. |
| Rolling beta >=0.8 | 43.68% / -4.37% / -7.34% | Harmful in both reused periods; do not add as an alpha gate. |
| Exclude Utilities | 55.82% / 9.93% / 26.04% | Improved development, had no 2024 effect, and weakened 2025. Not robust; it may remain a personal mandate only. |
| Strong industry >=80 | 14.75% / 7.73% / 12.76% | Reduced 2025 drawdown but surrendered return; no consistent hard-gate edge. |
| Stock within industry >=80 | 30.28% / -1.61% / 3.94% | Negative/no value as a hard gate. |
| Accelerating industry breadth | 9.02% / 7.64% / -1.22% | Negative/no value and highly selective. |
| Up/down volume >=1.25 | 47.02% / -2.35% / 16.90% | Mixed; failed risk gates and 2025 was 86.7% dependent on the largest winner. |
| Extension limits | 46.82% / 9.93% / 23.64% | Small development improvement, no 2024 change, lower 2025 return; useful as a possible risk preference, not proven alpha. |
| Pivot near price with low supply | 39.12% / 6.71% / 6.33% | Passed every absolute numeric stage gate but underperformed baseline return and return/DD in all periods. |
| Breakout demand | 15.36% / -2.43% / 5.49% | Inconclusive/sparse and adverse in the factorial contexts; current proxy is too restrictive. |
| Base duration and depth | 13.27% / 8.24% / 2.64% | Negative/no value; development drawdown was 20.76%. |
| Contraction plus volume dry-up | 4.40% / 7.73% / 66.94% | Seductive but unstable: development drawdown was 51.71% and one winner supplied 75.05% of 2025 positive P&L. |
| Shakeout/reclaim | 31.07% / 14.71% / -9.32% | Reversed sharply in 2025. |
| Early base-stage proxy | 8.41% / -6.16% / -3.67% | Negative/no value. |
| SPY above SMA50 | 58.21% / 9.59% / 6.58% | Passed absolute stage gates and controlled 2025 drawdown, but beat baseline only in development and the 2024 result was outlier-dependent. Better framed as exposure/risk research than stock alpha. |

Across the six-component complete factorial, median marginal return was negative
for dual RS, pivot/supply, and breakout demand in every period. Breakout demand
was positive in only 1/32 development, 2/32 reused-2024, and 7/32 reused-2025
contexts. Industry strength was mixed, extension had a zero median effect, and
SPY/SMA50 primarily exchanged return for lower drawdown rather than adding
stable stock-selection alpha.

## Combination findings

Seven variants passed every absolute stage gate: pivot/supply, SPY/SMA50,
extension plus pivot, extension plus SPY/SMA50, pivot plus SPY/SMA50, dual RS
plus extension plus SPY/SMA50, and extension plus pivot plus SPY/SMA50. None met
the relative-performance, outlier, and leave-one-out requirements.

The most defensible-looking absolute result was SPY/SMA50: 58.21% / 8.01%
development return/drawdown, 9.59% / 4.54% in reused 2024, and 6.58% / 5.95%
in reused 2025. It still surrendered 21.44 percentage points of 2025 return and
did not demonstrate cross-stage alpha. Adding extension produced essentially
the same path. Pivot/supply controlled drawdown but had lower return and
return/drawdown than baseline in every period.

The cumulative six-filter conjunction demonstrates over-filtering directly:

| Period | Earnings-eligible | + dual RS | + extension | + industry | + pivot/supply | + breakout | + SPY/SMA50 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Development | 25,456 | 7,687 | 7,450 | 1,897 | 384 | 9 | 7 |
| Reused 2024 | 3,759 | 817 | 763 | 156 | 27 | 0 | 0 |
| Reused 2025 | 3,764 | 1,480 | 1,382 | 294 | 58 | 1 | 0 |

## What should change

No production trading rule should change from this experiment. The data cannot
support promotion, and several production concepts have only been approximated.

The next research design should change:

1. Stop adding hard filters to the reused archive. The dominant problem is
   choosing among thousands of candidates for two portfolio slots.
2. Treat RS, industry, base, and volume measures as candidate-ranking features
   first. Test simple one-factor orders and a small frozen composite against the
   current default ticker order, with leave-one-factor-out comparisons.
3. Keep volume >=0.30 and ADR 1%–10% out of the research alpha stack at their
   current thresholds because they barely filter anything. Do not add beta
   >=0.8, early-base, dual-RS, or the current breakout conjunction as hard
   alpha gates.
4. Continue treating SPY/SMA50 and extension as risk/exposure hypotheses, not
   proven stock-selection edge. The existing market-plus-trailing study remains
   `HOLD`, not production-ready.
5. Acquire point-in-time fundamentals, historical universe membership,
   delisted symbols, effective-dated classifications, and point-in-time earnings
   schedules. Fundamental acceleration cannot be tested honestly from current
   restated data.
6. Freeze any new ranking rule prospectively. All historical periods used here
   are contaminated by repeated analysis; further threshold mining cannot turn
   them into validation.

## Audit and limitations

The successful run produced 240 result rows, 8,079 accepted-ledger rows, and
166,543 daily equity rows. All accepted counts reconciled to ledgers. Audits
found zero period/outcome-boundary, next-ticker-session entry, earnings-blackout,
duplicate signal/ticker, allocated-risk, heat, position, or missing-equity-value
violations. Maximum observed heat was 2R and maximum positions was two. MODEL_0
matched `LEADER_COMPLETENESS_V2` on all audited baseline numeric metrics.

Every period is reused adaptive diagnosis. The current-symbol archive has
survivorship bias, industry labels are current rather than effective-dated,
earnings dates are retrospective, and no untouched holdout exists. Eight of 240
stage/variant rows had zero executable candidates. Testing 80 correlated
variants increases selection risk; no unadjusted best result should be read as
proof of edge.

Exact point-in-time fundamental acceleration, historical sister-stock
confirmation, manual setup integrity, and chart-confirmed structural
reward/risk were unavailable and remain unassessed. Production and the immutable
forward journal were unchanged.

Generated artifacts are under
`research/output/filter_combination_audit_v1/` and are intentionally untracked.
