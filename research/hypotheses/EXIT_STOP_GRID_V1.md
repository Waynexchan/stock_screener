# EXIT_STOP_GRID_V1 preregistration

Date preregistered: 2026-09-13. Status: **RESEARCH_ONLY**.

## Hypothesis

The MODEL_0 Stage 2 transition may benefit from explicit asymmetric profit targets and volatility-scaled initial stops. Tighter ATR stops may improve capital efficiency but can also increase stop-outs; 2R to 3R targets may improve payoff while reducing win rate. The useful region, if any, should be stable across adjacent fixed settings rather than depend on one isolated optimum.

## Frozen discovery grid

Use only 2017-01-01 through 2023-12-31 from the current-universe Yahoo engineering archive. Preserve 2024-2025 as untouched and do not claim point-in-time or survivorship-bias control. Generate the existing MODEL_0 false-to-true Stage 2 signal after the close and enter at the next available session open with 5 bps adverse slippage.

ATR20 is the simple mean of True Range over the 20 sessions ending on the signal date. Test five fixed initial stops: signal-date 20-session low; slipped entry minus 0.5 ATR; slipped entry minus 1 ATR; signal-day low minus 0.5 ATR; and signal-day low minus 1 ATR. Here signal-day low is the prior session's low at next-session entry. Test no target, 2R, 2.5R, and 3R for every stop. Each stop remains fixed after entry. Maximum holding time is 40 sessions.

Stops gap through at the open. Favorable target gaps fill only at the target. If a daily bar touches both stop and target, assume stop first. Apply 5 bps adverse exit slippage, USD 587 normalized initial risk, and a maximum of four simultaneous positions.

## Decision boundary

Report all 20 combinations. A discovery-only shortlist requires at least +0.10R expectancy versus the no-target/20-day-low baseline, no reduction in profit factor, no increase in maximum drawdown, and directional support from an adjacent stop or target setting. Multiple comparisons and repeated use of the same biased discovery data prevent validation or production promotion regardless of the result.

The portfolio permits at most four simultaneous positions and normalizes each accepted trade to USD 587 initial risk. It does not model account cash or impose a maximum notional exposure, so especially tight ATR stops may imply unrealistic share counts; interpret those variants conservatively.
