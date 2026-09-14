# LEADER_RS_ROBUSTNESS_V1

Status: **PREREGISTERED ADAPTIVE ROBUSTNESS — NO UNTOUCHED HOLDOUT**

Production effect: **NONE**

## Hypothesis

Among causal MODEL_0 Stage 2 transition signals that pass the user's inclusive
ten-calendar-day pre-earnings blackout, a market-wide, twelve-month
MarketSmith-style relative-strength proxy, confirmation from a near-high
stock/SPY relative-strength line, current-classification industry leadership,
and price/volume leadership may identify a smaller set of potential
superperformance leaders with better portfolio return-to-drawdown and
expectancy than the unfiltered MODEL_0 baseline.

The economic mechanism is persistent institutional demand concentrated in
stocks already outperforming the broad market and their peers. Beta is not
treated as momentum. Utilities exclusion and beta >=0.8 are tested only as
incremental mandate overlays on the frozen technical-leader profile.

## Evidence status and limits

- The price archive contains current symbols and omits historical failures and
  delistings. Every result is survivorship-biased.
- Industry labels are today's cache, not effective-dated classifications.
- Earnings events are retrospectively retrieved actual/revised dates, not
  immutable schedules known on each historical signal date.
- All 2017-2025 price periods have already been inspected in earlier research.
  Development, reused 2024, and reused 2025 are adaptive robustness samples,
  not independent validation or an untouched holdout.
- Point-in-time EPS, sales, margins, estimates, ownership, and institutional
  sponsorship are unavailable. Fundamental acceleration is therefore
  `BLOCKED_DATA_NOT_READY` and is not silently approximated.

## Frozen MarketSmith-style proxy

This experiment does not claim to reproduce MarketSmith's proprietary RS
Rating. For every signal date, the research proxy is calculated for every
current-archive symbol with complete signal-date and 63/126/189/252-session
closes before applying Stage 2 or candidate filters.

The four non-overlapping quarterly returns are:

```text
Q1 = Close[T] / Close[T-63] - 1
Q2 = Close[T-63] / Close[T-126] - 1
Q3 = Close[T-126] / Close[T-189] - 1
Q4 = Close[T-189] / Close[T-252] - 1
Raw = 0.40*Q1 + 0.20*Q2 + 0.20*Q3 + 0.20*Q4
```

`marketsmith_proxy_score` is the daily cross-sectional percentile of `Raw`,
mapped to integer 1-99. The recent quarter receives twice the weight of each
earlier quarter. `marketsmith_proxy_delta_21d` is today's score minus the score
21 trading sessions earlier.

The RS line is adjusted stock close divided by adjusted SPY close. A
`rs_line_within_2pct_252d_high` observation is at least 98% of the trailing
252-session RS-line maximum through the signal date. No future bar is used.

Current-classification industry leadership is the cross-sectional 1-99 rank of
each industry's median proxy score on the signal date. An industry needs at
least five valid members. This field is explicitly classification-biased.

The 50-session up/down volume ratio is total volume on positive-close sessions
divided by total volume on negative-close sessions. Zero down-volume is missing,
not infinite. Price leadership is the percentage below the trailing 252-session
high through the signal date.

## Frozen variants

The baseline and all variants are declared in
`research/experiments/leader_rs_robustness_v1.json`. They comprise:

- MODEL_0 baseline;
- five mutually exclusive proxy-score buckets;
- fixed proxy thresholds of 80, 85, and 90;
- RS-line, industry, and up/down-volume rules one at a time;
- proxy >=85 combined separately with RS-line and industry confirmation;
- one technical-leader profile; and
- that identical profile with either Utilities excluded or rolling beta >=0.8.

No threshold will be optimized after inspecting outcomes. A material revision
creates a new experiment version.

## Execution and portfolio

- Signal: MODEL_0 false-to-true Stage 2 transition after the close.
- Earnings: reject signals from zero through ten calendar days before an event,
  inclusive, before filtering, execution, ordering, or capacity allocation.
- Entry: next available session open plus 5 bps adverse slippage.
- Initial stop: signal-date trailing 20-session low, fixed after entry.
- Exit: initial stop or 40 sessions; no fixed profit target.
- Exit slippage: 5 bps; stop gap fills at the open; same-bar ambiguity is
  stop-first.
- Portfolio: 100R starting equity, fixed 2R maximum heat, 1R per trade, at most
  four positions, no cash/notional constraint.
- Same-day candidates retain the existing deterministic entry-date,
  signal-date, ticker ordering. Ranking-policy research is outside V1.

## Periods

- Development signals: 2017-01-01 through 2023-11-01; outcomes end 2023-12-29;
  stability split 2020-12-31.
- Excluded contaminated gap: 2024-01-01 through 2024-02-29.
- Reused 2024 signals: 2024-03-01 through 2024-10-31; outcomes end 2024-12-31.
- Reused 2025 signals: 2025-01-02 through 2025-10-31; outcomes end 2025-12-31.

## Metrics and decision rule

Report every variant in every period: signal and candidate counts, accepted
trades, total return, CAGR, daily mark-to-market maximum drawdown, expectancy,
profit factor, win rate, payoff, MFE, MAE, holding time, exposure/heat, largest
winner contribution, early/late development return, and deltas versus the
period baseline.

The absolute stage gates are frozen in the experiment JSON. A historical
shortlist also requires higher total return and higher return/max-drawdown ratio
than the matching baseline in at least two of the three reused stages, positive
early and late development return, zero missing marks, and no largest winner
contributing more than 50% of total positive P&L in any stage.

Because there is no independent validation or untouched holdout, even a full
numeric pass ends at `HOLD`; it cannot start a new forward specification or
change production. Mixed, unstable, sparse, or outlier-dependent evidence ends
at `HOLD`, `REVISE`, or `REJECT` as appropriate.
