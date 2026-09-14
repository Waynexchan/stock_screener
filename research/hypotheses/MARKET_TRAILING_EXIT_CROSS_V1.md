# MARKET_TRAILING_EXIT_CROSS_V1

## Hypothesis

Weak broad-market conditions may reduce the quality of otherwise valid MODEL_0
entries, while a profitable trade that has already advanced by 2R or 3R may
benefit from a causal moving-average profit-protection stop. Crossing the two
ideas can show whether either mechanism reduces portfolio drawdown without
destroying return, expectancy, or trade capacity.

This is an adaptive robustness experiment. Earlier development, 2024, and 2025
results have already been inspected. No period in this experiment is independent
validation or an untouched holdout.

## Frozen baseline and matrix

The baseline is the earnings-blackout MODEL_0 signal, next-session entry with
five basis points of adverse slippage, signal-date 20-session-low initial stop,
no fixed target, 40-session maximum hold, 1R per trade, and fixed 2R portfolio
heat. The matrix crosses four SPY entry/heat policies with seven exits: no
trailing stop, or a ratcheting SMA20 minus 0, 0.5, or 1.0 ATR20 stop activated
after the trade first reaches either 2R or 3R. All 28 combinations will be
reported.

The SPY-only normal/reduced/blocked policy is explicitly a research proxy, not
the production market-regime model. The archive does not contain every input
required to reproduce the production model, including QQQ and the complete
point-in-time breadth, breakout, leadership, and volatility state.

## Causal sequence

The earnings blackout is applied before execution, candidate ordering, and
capacity allocation. Market eligibility uses only the SPY adjusted close and
moving averages known on the signal date. A signal is entered no earlier than
the next available session open.

For a trailing variant, the first completed session whose high reaches the
activation price arms the trailing rule. The rule cannot exit on that activation
session. Beginning with the next session, the stop uses SMA20 and ATR20 calculated
only through the prior completed session. It is the maximum of the original
initial stop, the previous active trailing stop, and the new moving-average
candidate, so it never loosens. A gap through the active stop fills at the open;
an intraday touch fills at the stop; five basis points of adverse exit slippage
then applies.

## Evidence and decision rules

The development period is 2017 through the boundary-purged 2023 signal end.
March through October 2024 and January through October 2025 are reused robustness
periods. Each begins from a fresh 100R account. The primary risk objective is a
maximum daily open/close mark-to-market drawdown of at most 10%. Return,
expectancy, profit factor, payoff, win rate, accepted trades, holding time,
market-state admissions, exit reasons, and missing marks are also reported.

A claim that trailing protection improves return requires higher total return
than the no-trailing cell under the same market policy in all three periods.
Mixed period results are mixed evidence, not a pass. The development gate also
requires at least 100 trades, profit factor at least 1.20, positive expectancy
and both stability-split returns. Each reused period requires at least eight
trades, profit factor at least 1.10, and positive expectancy. No historical
result can authorize production or a new forward test because the current-symbol
price archive is survivorship-biased, the earnings dates are retrospective, and
all evaluation periods have already been reused.

## Known limitations

- Current-symbol membership omits historical failures and delistings.
- Earnings dates are retrospective actual/revised events, not immutable schedules
  known on each historical signal date.
- The normalized-R portfolio has no cash, notional, tax, or market-impact model.
- The SPY-only gate cannot reproduce the richer production market regime.
- Testing 28 related cells increases multiple-testing and false-discovery risk.

