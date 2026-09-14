# LEADER_COMPLETENESS_V2

Status: **PREREGISTERED ADAPTIVE ROBUSTNESS — NO UNTOUCHED HOLDOUT**

Production effect: **NONE**

## Hypothesis

Completing the observable technical-leadership specification before testing may
separate useful relative-strength, industry, and base/pivot mechanisms from the
overly restrictive composite used in V1. The expected mechanism is persistent
institutional demand: market-leading stocks, leadership relative to their own
groups, improving group breadth, contracting supply, and decisive pivot action
may produce better expectancy, MFE, payoff, and return/drawdown than the simple
MODEL_0 Stage 2 transition.

This experiment deliberately freezes exit and exposure. Every ordinary variant
uses the same 20-session-low initial stop, no fixed target, 40-session maximum
hold, and fixed 2R heat. The only timing variant waits for a causal three-session
post-breakout confirmation and enters on the following session. Exit and
exposure optimization remain separate research questions.

## Evidence status and blocks

- Every 2017-2025 price period has already been inspected. All stages are reused
  adaptive robustness, not independent validation or an untouched holdout.
- The current-symbol archive omits delistings and historical universe changes.
  Every result is survivorship-biased.
- Industry labels are current, not effective-dated.
- Earnings dates are retrospectively retrieved actual/revised dates, not
  immutable schedules known on historical signal dates.
- Point-in-time EPS, sales, margins, estimates, surprises, ownership,
  sponsorship, and cash-flow histories are unavailable. Fundamental
  acceleration remains `BLOCKED_DATA_NOT_READY`; no current or restated value
  may substitute for it.
- Base stage is an explicitly defined price-history proxy, not a discretionary
  Minervini base count.

## Completed MarketSmith-style proxy

V2 retains V1's non-proprietary four-quarter RS proxy. It is calculated before
Stage 2, sector, industry, or setup filtering for every current-archive symbol
with complete 63/126/189/252-session closes:

```text
Q1 = Close[T] / Close[T-63] - 1
Q2 = Close[T-63] / Close[T-126] - 1
Q3 = Close[T-126] / Close[T-189] - 1
Q4 = Close[T-189] / Close[T-252] - 1
Raw = 0.40*Q1 + 0.20*Q2 + 0.20*Q3 + 0.20*Q4
```

The daily cross-sectional score is an integer 1-99. Report the fixed buckets
1-69, 70-79, 80-89, 90-94, and 95-99 without selecting a threshold after
outcomes. Score changes are measured over 21 and 63 sessions.

The RS line is adjusted stock close divided by adjusted SPY close. A new
252-session RS-line high requires the current value to exceed the maximum of the
previous 251 sessions. `rs_line_leads_price_high` requires that event while the
stock price itself has not made a new 252-session closing high.

`stock_within_industry_score` is the signal-date 1-99 percentile rank of the
stock's RS proxy among at least five currently classified industry members.
Industry leadership remains the 1-99 cross-industry rank of each industry's
median stock proxy. Industry breadth is the percentage of valid members with
RS proxy >=80, plus its 21- and 63-session changes.

## Frozen base and pivot proxies

- Pivot: highest adjusted high in the 126 sessions before the signal.
- Base start: latest occurrence of that pivot high in the prior 126 sessions.
- Duration: trading sessions from base start through the signal.
- Depth: pivot-to-low decline from base start through the signal.
- Near pivot: close from 5% below through 2% above the pivot.
- Contraction count: number of strict range reductions across three consecutive
  20-session blocks, where range is `(max high - min low) / mean close`.
- Volume dry-up: mean volume in the latest 10 sessions divided by mean volume in
  the preceding 40 sessions; dry-up is <=0.80.
- Pivot supply: count in the latest 10 sessions of down closes on at least
  50-session-average volume while closing within 8% of the pivot; clear supply
  is at most one such day.
- Breakout quality: close above the prior pivot, volume/50-session average >=1.5,
  and close location in the daily range >=75%.
- Shakeout/reclaim: within the latest 10 sessions, low undercuts the prior
  20-session low and the same session closes back above that level.
- Base-stage proxy: one plus the count of distinct close crossings above a
  prior 63-session high on volume ratio >=1.2 during the previous 252 sessions.
  A value <=2 is the frozen early-stage proxy.
- Complete base quality: duration 15-65 sessions, depth 3%-35%, near pivot,
  at least one contraction, dry-up <=0.80, at most one pivot-supply day, and
  base-stage proxy <=2.

These fixed definitions are research proxies, not claims that discretionary
chart interpretation has been replicated.

## Frozen industry policies

Compare the same MODEL_0 candidates under five policies:

1. Secondary confirmation proxy: industry score >=80 receives 1R; otherwise
   0.5R. All candidates remain eligible.
2. Hard gate: accept only industry score >=80.
3. Rank only: retain all candidates, ordering same-day capacity by industry
   score, then stock-within-industry score, then market RS score.
4. Exceptional-stock override: accept industry score >=80 or market RS >=95.
5. Breadth acceleration hard gate: breadth >=20%, 21-session change >0, and
   63-session change >=0.

Missing required industry data fails closed for hard gates and ranking. The
secondary proxy assigns 0.5R when qualification is missing or false. All five
policies are classification-biased.

## Delayed follow-through variant

Only an original signal with breakout quality may qualify. In the next three
sessions, the first close above both the original signal close and the prior
session close, with close location >=60% and volume ratio >=0.8, becomes a new
confirmation signal after that close. Reapply the ten-calendar-day earnings
blackout to the confirmation date, rebuild the trailing 20-session structural
stop through that date, and enter no earlier than the next session open. The
confirmation date must remain within the frozen signal period and its outcome
must remain within the stage boundary.

## Variants and evaluation

The complete fixed list is stored in
`research/experiments/leader_completeness_v2.json`. It includes the baseline,
the five RS buckets, individual completed RS features, all five industry
policies, individual base/pivot mechanisms, one complete base-quality rule, one
complete technical-leader rule, a ranked version of that rule, and the delayed
follow-through entry.

Report all variants and the same balanced portfolio metrics used by V1,
including expectancy, MFE, MAE, payoff, drawdown, accepted-trade count, and
largest-winner contribution. Preserve the V1 stage gates. A shortlist requires
every stage gate, higher return and return/drawdown than baseline in at least two
periods, and no largest winner above 50% of positive P&L in any period.

Even a numeric pass ends at `HOLD`: data are biased and there is no independent
validation or untouched holdout. Do not change production or the immutable
forward journal.

