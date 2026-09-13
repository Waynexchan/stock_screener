# EARNINGS_EXPOSURE_ROBUSTNESS_V1 result

Run date: 2026-09-13. Decision: **HOLD**.

> **SURVIVORSHIP-AND-EARNINGS-SCHEDULE-BIASED RESEARCH — NOT PRODUCTION EVIDENCE**

## Hypothesis and frozen rules

The user clarified that exposure should behave as a disciplined two-state process, not a permanent cumulative-profit ladder. The new experiment was committed as `9545103` before the strategy outcomes were calculated; implementation was committed as `acb23be`.

- Start with at most two simultaneous 1R positions.
- Sum allocated realised R for every position closing on one session.
- A positive exit batch permits at most three 1R positions beginning next session.
- A zero or negative exit batch restores the two-position limit beginning next session.
- A session without an exit does not change state.
- Never permit a fourth position, never use an exit to fund an earlier same-session entry, and do not force-liquidate an otherwise valid open trade.
- Reject a signal if an earnings event falls from the signal date through ten calendar days later, inclusive.

The frozen trade plan retained the 20-session signal-date low stop, no fixed profit target, 40-session maximum hold, next-session-open entry, 5 bps adverse entry/exit slippage, and daily open/close mark-to-market drawdown. All test accounts restarted at 100R.

The four variants isolate the two changes: fixed 2R and dynamic 2R/3R exposure, each with and without the earnings blackout.

## Data and evidence status

The Yahoo earnings downloader completed 463 non-overlapping seven-day windows from 2017-01-01 through 2025-11-10 with no failed window. It retained 134,382 event rows across 5,691 symbols; 1,737 of the 1,840 current-universe symbols had at least one event in the requested period. The other 103 symbols had no returned event and were treated as having no listed event within each globally covered date window, which may still reflect provider omission.

The calendar is retrospective. It records actual/revised event dates retrieved in 2026, not immutable schedule snapshots captured before each historical signal. Yahoo's calendar interface supports date-range event retrieval, while Nasdaq explains that displayed earnings dates may be algorithmically derived from historical reporting dates and supplied by Zacks. This makes the blackout a useful engineering proxy but not a point-in-time validation.

All price periods were already inspected in the preceding experiment. Therefore 2017–2023 is reused development robustness and March 2024–October 2025 is reused post-2023 robustness. There is no untouched historical holdout.

## Results

### Reused 2017–2023 development

| Variant | Trades | Return | CAGR | Max DD | Exp/trade | PF | Payoff | Win rate | Expanded / contracted | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Fixed 2R, no blackout | 123 | 72.96% | 8.16% | 6.97% | 0.593R | 2.198 | 3.001 | 42.28% | 0 / 0 | PASS |
| Win-to-3/loss-to-2, no blackout | 160 | 14.20% | 1.92% | 22.06% | 0.089R | 1.151 | 2.137 | 35.00% | 32 / 31 | FAIL |
| Fixed 2R + earnings blackout | 124 | 42.78% | 5.23% | 9.75% | 0.345R | 1.691 | 2.342 | 41.94% | 0 / 0 | PASS |
| Win-to-3/loss-to-2 + blackout | 159 | 57.10% | 6.68% | 13.38% | 0.359R | 1.602 | 2.716 | 37.11% | 32 / 32 | **FAIL: DD** |

The blackout removed 3,963 of 29,376 independent executable trade paths (13.49%). Because portfolio slots are scarce, removing candidates can admit different replacements; the blackout variant therefore accepted 124 trades versus 123 without the filter. This is not a matched-trade comparison.

### Reused March 2024–October 2025 robustness

| Variant | Trades | Return | CAGR | Max DD | Exp/trade | PF | Payoff | Win rate | Expanded / contracted | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Fixed 2R, no blackout | 31 | 3.95% | 2.15% | 7.26% | 0.127R | 1.252 | 1.335 | 48.39% | 0 / 0 | PASS |
| Win-to-3/loss-to-2, no blackout | 37 | 19.56% | 10.29% | 6.93% | 0.529R | 2.395 | 1.824 | 56.76% | 6 / 5 | PASS |
| Fixed 2R + earnings blackout | 27 | 13.13% | 7.00% | 4.84% | 0.486R | 2.285 | 1.571 | 59.26% | 0 / 0 | PASS |
| Win-to-3/loss-to-2 + blackout | 35 | 12.86% | 6.86% | 9.75% | 0.367R | 1.788 | 1.894 | 48.57% | 5 / 4 | PASS |

The blackout removed 1,486 of 9,864 independent executable trade paths (15.06%). Every accepted blackout ledger row was checked against the event calendar and had zero violations. Dynamic equity curves never exceeded three simultaneous positions or 3R initial heat.

## Interpretation

The clarified dynamic exposure rule is implemented exactly as a 2/3-position state machine, but it is regime-unstable. Without the blackout it was much better than fixed 2R after 2023, yet materially worse in 2017–2023, with 22.06% drawdown. Combining it with the blackout improved the older period but still reached 13.38% drawdown and retained only 78.26% of the fixed-2R development return, below the frozen 80% requirement.

The simpler fixed-2R earnings blackout is more interesting as a risk hypothesis: it remained below 10% drawdown in both reused periods and improved the post-2023 metrics. However, it reduced development return by 41.37% and increased development drawdown from 6.97% to 9.75%. The direction therefore changes by period, and retrospective schedule bias prevents a validation claim.

## Decision

The combined dynamic-exposure-plus-blackout candidate is **HOLD**. It failed the development drawdown and return-retention gates. The fixed-2R earnings blackout is worth prospective observation, but is not `VALIDATED` and is not promoted to production.

A trustworthy next step requires immutable future earnings schedule snapshots captured daily, including changes/cancellations and announcement timing. The production rule should remain unchanged until the forward sample matures; missing or stale earnings schedule data must not silently authorize a trade.

Hashes:

- Earnings events: `237e3937b0aba3ba514c4a1e6231d556747079016cf08546f6699369bf64e353`
- Earnings metadata: `59a04b0c40c985fe20758780bf0feb7d1a5840edb853d04788426683e7d8a0b0`
- All results: `be6fefcc75e969c9f16c6c423d04b57beb350c9a7e46b440508a062ca0292340`
- Result payload: `d2cfc4bf980eb8486978a87fa62f7bf364d48a27027a2874af3cd47105fa4151`
- Generated report: `5df3da0b0325a7b812bf11a19d0f0b671d39266686324f8fcdce5a2cc81d1227`
