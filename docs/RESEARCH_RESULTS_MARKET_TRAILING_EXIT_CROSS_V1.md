# MARKET_TRAILING_EXIT_CROSS_V1 Results

> **SURVIVORSHIP-AND-EARNINGS-SCHEDULE-BIASED RESEARCH — NO UNTOUCHED HOLDOUT**

## Decision

**HOLD.** Seven of 28 market-gate/trailing-exit cells passed the frozen numeric
gate in all three reused periods. Only one trailing rule increased total return
against its same-market no-trailing baseline in all three periods: require SPY
above its signal-date SMA50, then arm a ratcheting SMA20 minus 1 ATR20 stop after
the trade first reaches 2R.

That cell is promising risk-control evidence, not validation. It materially
reduced 2025 drawdown but also excluded the earlier 23.51R RGLD winner and
therefore earned much less than the unrestricted 2025 baseline. The 2024 result
also depended heavily on a single 10.22R ATEN trade. Production and the existing
forward journal remain unchanged.

## Frozen design

- Preregistration commit: `f534cc8`.
- Clean implementation/run commit: `1f654331a9ea5f2460b5f1bceb03329725a408ef`.
- Matrix: four SPY entry/heat policies by seven exits, or 28 cells per stage.
- Stages: boundary-purged 2017–2023 development, reused March–October 2024,
  and reused January–October 2025.
- Every signal first passes the inclusive ten-calendar-day pre-earnings blackout.
- Entry is the next available open plus five basis points adverse slippage.
- Initial stop is the signal-date 20-session low; maximum hold is 40 sessions;
  portfolio heat is 2R and each accepted trade risks 1R.
- Trailing variants arm at 2R or 3R. Starting only on the next session, the stop
  is the ratcheting maximum of the initial stop, its previous value, and prior-day
  SMA20 minus 0, 0.5, or 1 ATR20. Gap-through exits fill at the open, followed
  by five basis points adverse slippage.
- The three-state SPY policy uses 2R when close is above EMA20, SMA50, and
  SMA200; 1R when only above SMA200; and blocks new risk below SMA200. It is a
  SPY-only research proxy, not the production market-regime model.

## Baseline parity

The new unrestricted/no-trailing baseline exactly reproduced the mandatory
earnings-blackout result, including trade count, return, drawdown, expectancy,
and profit factor. This establishes that the new market/trailing paths did not
silently change the frozen baseline.

| Period | Trades | Return | Max DD | Expectancy | Profit factor |
|---|---:|---:|---:|---:|---:|
| 2017–2023 | 124 | 42.78% | 9.75% | 0.345R | 1.691 |
| Reused 2024 | 12 | 9.93% | 3.93% | 0.828R | 3.309 |
| Reused 2025 | 13 | 28.01% | 13.07% | 2.155R | 8.821 |

## Market gate without trailing protection

| Market policy | 2017–2023 return / DD / trades | Reused 2024 | Reused 2025 |
|---|---:|---:|---:|
| No gate | 42.78% / 9.75% / 124 | 9.93% / 3.93% / 12 | 28.01% / 13.07% / 13 |
| SPY above SMA50 | 58.21% / 8.01% / 105 | 9.59% / 4.54% / 13 | 6.58% / 5.95% / 12 |
| SPY above SMA200 | 47.53% / 11.47% / 108 | 9.93% / 3.93% / 12 | 1.71% / 6.20% / 14 |
| SPY three-state heat | 46.72% / 8.61% / 99 | 8.48% / 3.64% / 13 | 0.10% / 5.55% / 12 |

The SMA50 gate was the only market-only cell to pass every numeric stage gate.
It improved development return and drawdown, but did not improve return in the
two later reused periods. In 2025 it removed the large RGLD path that generated
both the original portfolio's exceptional return and its 13.07% mark-to-market
drawdown. The SMA200 and three-state policies did not provide a convincing
return trade-off.

## Only all-period same-market return improver

`spy_above_sma50__activate_2r_sma20_minus_1_0atr20`:

| Period | Trades | Return | Max DD | Expectancy | PF | Win rate | Payoff | Trail exits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2017–2023 | 104 | 65.63% | 7.54% | 0.631R | 2.255 | 46.2% | 2.631 | 9 |
| Reused 2024 | 13 | 11.41% | 4.54% | 0.878R | 3.197 | 61.5% | 1.998 | 1 |
| Reused 2025 | 12 | 8.81% | 3.98% | 0.734R | 3.179 | 66.7% | 1.589 | 1 |

Against the same SMA50 gate without trailing protection, return changed by
`+7.43`, `+1.81`, and `+2.23` percentage points, while drawdown changed by
`-0.47`, `0.00`, and `-1.97` points. Against the unrestricted/no-trailing
baseline, however, the 2025 return was 19.21 points lower even though drawdown
was 9.08 points lower. It is therefore a better controlled path, not a universal
return improvement.

The cell was not dominated by one winner in development or 2025: removing its
largest winner left +50.46R and +5.55R respectively. Reused 2024 is weaker
evidence: its largest winner contributed +10.22R out of +11.41R total.

## Neighbor stability and alternative risk trade-off

The exact moving-average stop was too tight in development under the SMA50 gate:
the 2R-activated SMA20 variant returned only 0.43% and drew down 11.99%. Moving
the stop to SMA20 minus 0.5 ATR20 improved it to 37.37% / 10.54%, while minus
1 ATR20 reached 65.63% / 7.54%. This large sensitivity means the apparent
optimum is not yet robust.

Without any market gate, the 3R-activated SMA20 minus 0.5 ATR20 variant was the
cleanest pure profit-protection risk trade-off:

| Period | Trades | Return | Max DD | Expectancy | PF |
|---|---:|---:|---:|---:|---:|
| 2017–2023 | 125 | 68.53% | 6.60% | 0.548R | 2.261 |
| Reused 2024 | 11 | 4.33% | 2.55% | 0.393R | 2.077 |
| Reused 2025 | 17 | 7.79% | 7.05% | 0.458R | 2.290 |

It kept drawdown below 10% in all periods, but later-period returns were much
lower than the unrestricted no-trailing baseline. It is risk reduction rather
than evidence of higher return.

## Complete numeric passes

Seven cells passed every frozen stage gate:

- no market gate + 3R activation + SMA20 minus 0.5 ATR20;
- SPY above SMA50 + no trailing stop;
- SPY above SMA50 + 2R activation + SMA20 minus 1 ATR20;
- SPY above SMA50 + 3R activation + SMA20 minus 1 ATR20;
- SPY above SMA200 + 2R activation + SMA20;
- SPY above SMA200 + 2R activation + SMA20 minus 0.5 ATR20;
- SPY above SMA200 + 3R activation + SMA20 minus 0.5 ATR20.

Passing an absolute numeric gate does not establish incremental value. Several
of these cells produced only 0.99%–4.33% return in a reused later period, and
only the SMA50 plus 2R/SMA20-minus-1ATR20 cell improved its matching market
baseline's return in every period.

## Integrity audit and limitations

- 84 stage-cell rows were produced: all 28 cells in each of three stages.
- 4,007 accepted ledger rows were checked.
- Earnings-blackout violations: zero.
- Market-blocked admissions: zero.
- Missing daily marks: zero.
- The unrestricted/no-trailing 2025 baseline matched the prior result exactly.
- Generated detailed ledgers, equity curves, CSV summaries, and the run manifest
  are under `research/output/market_trailing_exit_cross_v1/` and remain ignored
  runtime research artifacts.

The current-symbol archive is survivorship-biased and excludes historical
failures and delistings. Earnings dates are retrospective rather than the
schedules known at each historical signal date. The 2024 and 2025 periods have
already been inspected repeatedly. There is no fresh validation or untouched
holdout, and 28 related cells increase false-discovery risk. These findings
support continued forward observation of a frozen candidate only after a
separate forward-test design review; they do not justify a production change.

