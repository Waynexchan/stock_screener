# EASY_EXECUTION_CROSS_VALIDATION_V1 preregistration

Date preregistered: 2026-09-13. Status: **RESEARCH_ONLY**.

## Hypothesis

A simple stop, exit, and exposure combination may preserve positive expectancy while keeping daily mark-to-market drawdown at or below 10%. If the discovery selection rule identifies such a candidate without future-informed ranking, its behavior should remain positive on post-2023 validation data before any 2025 holdout is spent.

## Complete matrix

The fixed matrix contains six initial stops: signal-date 20-day low, entry minus 1 ATR, signal-day low minus 0.5 or 1 ATR, signal-date 10-day low, and the tighter of the 20-day low or entry minus 1 ATR. Because entry is at the next session open, signal-day low is the previous trading day's low at entry time.

Seven exits cover fixed 2R, 2.5R, 3R, and 4R targets with a 40-session backstop plus no-target time exits at 20, 30, and 40 sessions. Including 2.5R tests target-neighborhood stability; the no-target time exits test whether letting winners run remains superior at one-month, six-week, and two-month horizons. Four exposure policies cover fixed 2R, 3R, and 4R heat plus a permanent earned ladder that starts at 2R and unlocks 3R/4R at realised-profit high-water marks of +2R/+4R. The full cross is 6 x 7 x 4 = 168 cells.

All trades use next-session execution, declared slippage, fixed initial stops, conservative stop-first same-bar handling, no same-ticker overlap, and daily open/close mark-to-market portfolio accounting. The design deliberately excludes partial exits, discretionary trailing stops, and complicated reset rules to keep every candidate executable and auditable.

## Staged evaluation

The 2017–2023 sample is iterative discovery because earlier results have already been inspected. It ends signals on 2023-11-01 and outcomes in 2023. A fixed rule selects at most three candidates using drawdown, expectancy, profit factor, sample size, two-subperiod stability, neighboring support, and simplicity.

Early 2024 is excluded because older late-2023 outcome calculations contaminated that boundary. Selected candidates are frozen before evaluation on signals from 2024-03-01 through 2024-10-31, with all outcomes ending in 2024. Only candidates passing the preregistered validation gate may be evaluated once on 2025 signals through 2025-10-31, with outcomes ending in 2025. Validation results must be written before holdout access.

The archive uses current symbols and lacks delisted coverage, point-in-time membership, cash/notional constraints, and independent corporate-action provenance. Therefore even a positive holdout remains survivorship-biased engineering evidence and cannot authorize production or a forward-test rule change.
