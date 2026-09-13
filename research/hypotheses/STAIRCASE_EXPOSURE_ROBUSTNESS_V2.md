# STAIRCASE_EXPOSURE_ROBUSTNESS_V2

Status: **PREREGISTERED ADAPTIVE ROBUSTNESS — NO UNTOUCHED HOLDOUT**

Production effect: **NONE**

## Corrected hypothesis

The prior V1 interpretation was too restrictive because it used only 2R and 3R states. The intended behavior is a performance-responsive staircase: start at 2R/two 1R positions, add another 1R slot after each net-profitable realised exit batch, and reduce available capacity after a non-positive batch.

Unlimited exposure is not compatible with the project's explicit heat and maximum-position controls. V2 therefore reports separate hard ceilings of 4R, 6R, and 8R rather than selecting an unbounded path after seeing results.

Two simple contraction disciplines are frozen:

- `STEP`: a non-positive exit batch reduces capacity by 1R, with a 2R floor.
- `RESET`: a non-positive exit batch immediately restores capacity to 2R.

All state changes become effective next session. A session with no exit leaves state unchanged. Multiple same-session exits use net allocated realised R. Existing valid positions are not force-liquidated, but no new trade is admitted until actual heat fits the reduced limit.

## Controlled comparison

Every cell uses the 20-day-low stop, no fixed target, 40-session maximum hold, and the inclusive ten-calendar-day retrospective earnings blackout. Compare the fixed-2R baseline with all six combinations of ceiling and contraction mode. Report all seven cells in both reused periods.

## Evidence status

The 2017–2023 and March 2024–October 2025 price periods have already been inspected. The earnings events were also retrieved retrospectively. This experiment can measure engineering behavior and historical robustness but has no untouched validation or holdout evidence.

Only a candidate meeting the frozen gate in both reused periods may be proposed for prospective forward observation. Production promotion remains prohibited.
