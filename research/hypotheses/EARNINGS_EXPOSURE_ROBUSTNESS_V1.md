# EARNINGS_EXPOSURE_ROBUSTNESS_V1

Status: **PREREGISTERED ADAPTIVE ROBUSTNESS — NO UNTOUCHED HOLDOUT**

Production effect: **NONE**

## Hypothesis

The user intends an exposure discipline rather than a permanent cumulative-profit ladder: begin with capacity for two 1R positions, allow a third only after a realised profitable exit, and revert to two after realised performance becomes non-positive. A separate ten-calendar-day pre-earnings signal blackout may reduce gap risk.

## Frozen state transition

- Start each test period at 2R heat and at most two 1R positions.
- Sum all allocated realised R from positions exiting on the same session.
- A positive exit batch sets the next session's heat/position capacity to 3R/three positions.
- A zero or negative exit batch sets the next session's capacity to 2R/two positions.
- Capacity is unchanged on sessions with no exit.
- Never permit a fourth position. Do not force-liquidate an otherwise valid open trade. Same-session exits cannot fund entries processed earlier that day.

This is compared with a permanent fixed-2R/two-position baseline using the already selected 20-day-low stop, no profit target, and 40-session maximum hold.

## Earnings blackout

Reject a signal when an earnings event for the ticker is dated from the signal date through ten calendar days later, inclusive. The historical data must include the actual event timestamp/date and explicit query-date coverage. A retrospective actual/revised earnings date is only a proxy for the schedule known on the signal date and therefore introduces schedule look-ahead/revision bias.

The four frozen variants are fixed-2R and dynamic exposure, each with and without the earnings blackout. Report all variants; do not select only the best.

## Evidence roles

- 2017-01-01 through 2023-11-01 signals, outcomes through 2023-12-29: reused development robustness.
- 2024-01-01 through 2024-02-29: excluded contaminated boundary gap.
- 2024-03-01 through 2025-10-31 signals, outcomes through 2025-12-31: reused/adaptive post-2023 robustness.
- Untouched holdout: unavailable. Future prospective observations are required.

Both historical periods have already influenced strategy discussion. Neither is independent validation for this version.

## Decision

The numeric gate in `research/experiments/earnings_exposure_robustness_v1.json` can support only `CONTINUE_FORWARD_OBSERVATION`. Survivorship bias, repeated price-sample use, small capacity-limited samples, and earnings schedule bias prohibit `VALIDATED` or production promotion.
