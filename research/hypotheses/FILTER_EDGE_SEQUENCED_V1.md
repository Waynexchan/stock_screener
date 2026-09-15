# FILTER_EDGE_SEQUENCED_V1

Status: **PREREGISTERED_ADAPTIVE_DIAGNOSTIC_NO_UNTOUCHED_HOLDOUT**

Production effect: **NONE**

## Questions

1. Before portfolio heat and cross-stock competition, does each existing
   mechanical filter improve the quality of non-overlapping same-ticker trade
   opportunities?
2. Does any bounded combination add opportunity-level expectancy, profit
   factor, MFE, or MAE beyond both MODEL_0 and its leave-one-filter-out parents?
3. After opportunity-level evidence is reported, does the previously calculated
   fixed-2R portfolio evidence agree or contradict it?
4. Under a fixed 2R total-heat budget, what does a maximum of two simultaneous
   positions per industry change when four 0.5R positions are possible?

This experiment separates filter quality from portfolio capacity. Individual
filters and all frozen combinations are both declared before the new
opportunity-level outcomes are inspected. The combination set is not selected
after seeing the individual results.

## Interpretation boundary

Every historical period has already been used by earlier research. This is an
adaptive engineering diagnosis, not validation or an untouched holdout. The
universe contains current survivors, industry labels are current rather than
effective-dated, and earnings dates were retrieved retrospectively. No result
may change production or be called validated.

## Frozen features and execution

- Reuse exactly the 80 variants from `FILTER_COMBINATION_AUDIT_V1`: all 64
  subsets of its six core components, including baseline, and its 16
  supplemental individual filters. No threshold changes are permitted.
- MODEL_0 signal and ten-calendar-day pre-earnings blackout are unchanged.
- Signal forms after the close; entry is the next available session open plus
  5 bps adverse slippage.
- Initial stop is the signal-date 20-session low; no fixed target; maximum hold
  40 sessions; exit slippage 5 bps; stop-first same-bar ambiguity.

## Layer A: opportunity-level filter test

For each variant independently:

1. Apply the variant to earnings-eligible MODEL_0 signals.
2. Simulate every executable signal using the frozen entry and exit rules.
3. Within each ticker, sort by entry date, signal date, then ticker and accept
   the first opportunity. Reject another opportunity while the prior accepted
   trade remains open; a new entry must occur strictly after the previous exit.
4. Do not apply cross-stock position count, portfolio heat, industry cap, or
   candidate competition.

This is not an unlimited-money portfolio return. It is a cohort test of trade
quality with one open trade per ticker, designed to prevent repeated daily
signals from masquerading as independent trades.

Report candidate signals, executable trades, accepted same-ticker episodes,
overlap rejections, unique tickers, expectancy, median R, standard deviation,
win rate, average win/loss, payoff, profit factor, average MFE/MAE, holding
period, total R, largest-winner contribution, and retention versus baseline.

Uncertainty for expectancy change versus baseline uses 2,000 deterministic
paired calendar-month block-bootstrap samples. All signals entering in the same
calendar month remain together to preserve broad contemporaneous dependence.

## Frozen opportunity-level classifications

An individual filter or combination is `ALPHA_SUPPORT` only if:

- development has at least 500 non-overlapping episodes and each reused period
  has at least 50;
- expectancy is positive in every period;
- expectancy beats baseline by at least 0.05R in at least two periods;
- development's paired calendar-month bootstrap 95% lower bound for expectancy
  change is above zero;
- profit factor and average MFE each beat baseline in at least two periods; and
- every period retains at least 5% of baseline episodes.

It is `RISK_QUALITY_SUPPORT` only if the sample floors and positive expectancy
hold, expectancy is no more than 0.02R below baseline in every period, average
MAE is less adverse in at least two periods, and profit factor beats baseline in
at least two periods. A row below a sample floor is `INCONCLUSIVE_SPARSE`; a row
with non-positive expectancy in at least two periods is `NEGATIVE`; all other
rows are `MIXED`.

A factorial combination may enter the sequential candidate list only when it
contains one to three components, receives `ALPHA_SUPPORT` or
`RISK_QUALITY_SUPPORT`, and every component improves expectancy versus the
combination with that component removed in at least two periods. Filters the
user already excluded from promotion—beta >=0.8, dual RS, early base stage, and
the current breakout-demand conjunction—remain reported but cannot advance.

## Layer B: portfolio cross-check

Join the opportunity-level results to the already frozen fixed-2R portfolio
results from `FILTER_COMBINATION_AUDIT_V1`. No historical portfolio result is
hidden or relabelled as new validation. A sequentially supported result must
also have passed that experiment's portfolio shortlist; otherwise the layers
are recorded as conflicting or unsupported.

## Layer C: industry concentration diagnostic

Industry concentration is a portfolio risk control, not an alpha filter.
Compare four MODEL_0 portfolios on the same subset with a non-missing current
industry classification:

1. fixed 2R heat, 1R per trade, maximum four positions, no industry cap;
2. the same with maximum two simultaneous positions per industry;
3. fixed 2R heat, 0.5R per trade, maximum four positions, no industry cap;
4. the same with maximum two simultaneous positions per industry.

The first pair is a deliberate invariant: because 2R heat at 1R per trade
already permits only two positions in total, the industry cap must produce an
identical path and zero industry-cap rejections. The second pair isolates the
cap where it can bind without increasing total heat. Report return, drawdown,
expectancy, profit factor, accepted trades, rejection reasons, maximum heat,
maximum total positions, and maximum same-industry positions.

Missing industries are not imputed. The concentration comparison excludes them
from both capped and uncapped sides and reports the excluded count. Because the
remaining classifications are current, the result remains classification-biased
and cannot validate the production industry control.

## Periods and decision

- Development signals: 2017-01-01 through 2023-11-01; outcomes end 2023-12-29.
- Reused 2024 signals: 2024-03-01 through 2024-10-31; outcomes end 2024-12-31.
- Reused 2025 signals: 2025-01-02 through 2025-10-31; outcomes end 2025-12-31.

The historical decision is `HOLD` only if at least one non-excluded factorial
combination enters the sequential candidate list and also passed the prior
portfolio shortlist. Otherwise it is `REJECT`. Even `HOLD` would mean only that
a frozen rule deserves genuinely new point-in-time observation; it would not
authorize production.

Point-in-time fundamentals, historical/delisted universe membership,
effective-dated industries, sister-stock history, immutable earnings schedules,
manual setup integrity, and chart-confirmed structural reward/risk remain
unavailable.
