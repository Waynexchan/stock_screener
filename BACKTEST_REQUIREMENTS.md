# Future Point-in-Time Backtest Requirements

The historical backtest is intentionally not implemented in this development
session. Production decision integrity and immutable forward evidence come first.

A later engine must replay the same canonical decision function without a second
research-only decision path. For every historical signal date it must use only
information available by that date: survivorship-bias-controlled universe
membership, delistings/corporate actions, point-in-time prices and volume,
point-in-time sector/industry and market cap, the contemporaneous metadata cache,
market regime, open portfolio state, and the versioned configuration.

Required architecture:

1. An immutable point-in-time data layer with source/as-of timestamps and data
   quality flags; no forward fill that makes unavailable data look valid.
2. A session calendar shared with production, including documented handling for
   exceptional closures and early closes.
3. Daily signal replay through `canonical_candidate_decision`, followed by the
   same sizing, portfolio heat, position count, industry/theme heat, and candidate
   concentration controls used in production.
4. An execution simulator with next-session eligibility, configurable slippage,
   gaps, partial fills, fees, stop/target ordering policy, and delisting outcomes.
5. Portfolio accounting based on the USD risk model, drawdown states, overlapping
   positions, and no use of closing data before it was observable.
6. Versioned result manifests containing git commit, config/data hashes, rejected
   candidates and reasons, fills, exits, and reproducible random seeds where used.
7. Walk-forward/out-of-sample evaluation, parameter stability checks, realistic
   baselines, and results split by regime, setup integrity, decision state,
   industry coverage, liquidity, and calendar period.

Minimum reporting should include sample size, expectancy in R after costs, win
rate, payoff ratio, profit factor, drawdown, exposure, turnover, capacity, and
confidence intervals. Results must distinguish signal quality from execution and
must not claim positive expectancy until sufficient out-of-sample evidence exists.

The immutable `output/forward_snapshots` bundles should later serve as the live
forward-test ledger and reconciliation source, not be rewritten into backtest
inputs after outcomes are known.
