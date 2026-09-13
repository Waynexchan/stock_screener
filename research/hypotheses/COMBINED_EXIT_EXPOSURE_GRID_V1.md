# COMBINED_EXIT_EXPOSURE_GRID_V1 preregistration

Date preregistered: 2026-09-13. Status: **RESEARCH_ONLY**.

## Hypothesis

Exit timing and portfolio capacity interact because a stop or target changes when scarce risk slots become available. Testing exit rules and exposure overlays separately may therefore miss combinations that keep daily mark-to-market drawdown at or below 10% while retaining positive expectancy and a usable trade sample.

## Fixed experiment

Cross all five previously declared initial stops and four targets with all nine previously declared exposure policies: 5 x 4 x 9 = 180 cells. Signals form after the close and execute at the next available open with 5 bps adverse entry and exit slippage. Stops are fixed at entry, favorable target gaps fill only at the target, same-bar stop/target ambiguity is stop-first, and maximum holding time is 40 sessions. The portfolio starts at 100R, permits at most four positions, charges allocated initial R until exit, prevents same-ticker overlap, and does not allow a same-session exit to fund an earlier entry.

Discovery signals end on 2023-11-01 and every outcome must end by 2023-12-29. This boundary was chosen before inspecting combined outcomes and preserves 2024–2025 for later use. Results remain survivorship-biased because the archive is built from current symbols and lacks delisted coverage, point-in-time membership, effective-dated classifications, and a cash/notional model.

## Gate and interpretation

A discovery shortlist cell must have no more than 10% daily open/close mark-to-market drawdown, positive total return and expectancy, profit factor of at least 1.20, at least 150 accepted trades, no missing marks, and positive return on both sides of the fixed 2020-12-31 discovery stability split. Passing cells rank by CAGR-to-drawdown, then expectancy per allocated R, then lower rule complexity, then stable cell ID. Every one of the 180 cells will be reported.

Multiple testing makes the best in-sample cell optimistic. A shortlist result does not validate the rule, authorize production, spend the untouched holdout, or start a new forward strategy. The historical decision remains **HOLD** until an independently sourced point-in-time validation sample is available.
