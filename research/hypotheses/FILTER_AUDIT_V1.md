# FILTER_AUDIT_V1 preregistration

Date preregistered: 2026-09-12. Status: **RESEARCH_ONLY**.

## Hypothesis

Some current production alpha filters may improve 1–2 month swing-trade expectancy or drawdown relative to a simpler Stage 2 and liquidity baseline, while others may be redundant. Excluding Utilities or stocks with rolling beta below 0.8 may increase opportunity quality because the intended strategy seeks strong directional expansion, but either exclusion may instead discard useful low-correlation winners.

## Frozen design

Use `MODEL_0_BASELINE`, next-session execution, 5 bps entry and exit slippage, a trailing 20-session structural stop, a 40-session maximum hold, stop-first same-bar treatment, USD 587 normalized initial risk, and at most four simultaneous positions. Evaluate one fixed change at a time using `research/experiments/filter_audit_v1.json`.

The free Yahoo/current-universe run is engineering discovery only for 2017–2023. It has high survivorship and classification bias, cannot validate a filter, and must not inspect or describe 2024–2025 as holdout evidence. Formal validation requires point-in-time membership, delisted returns, benchmark history, and effective-dated classifications. Signals whose 40-session outcomes cross a formal sample boundary must be purged, with a 40-session embargo at both boundaries.

Primary metric is after-cost expectancy in R. Secondary metrics are profit factor, maximum drawdown in R, payoff ratio, exposure, signal/trade count, MFE, MAE, holding time, regime stability, and rejected-trade opportunity cost. No threshold search is authorized. A production removal or addition requires economically meaningful improvement on independent validation and untouched holdout evidence, followed by a separate production review.

## Initial sample status

- Engineering discovery: available only after a labelled current-universe dataset is downloaded.
- Validation: **UNAVAILABLE**.
- Untouched holdout: **UNTOUCHED**, not authorized for the biased engineering run.
- Production effect: **NONE**.
