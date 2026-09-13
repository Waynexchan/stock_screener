# FILTER_AUDIT_V1 engineering discovery result

Run date: 2026-09-13. Historical decision: **HOLD**.

> **SURVIVORSHIP-BIASED RESEARCH — NOT PRODUCTION EVIDENCE**

## Dataset and execution

- Source: Yahoo Finance via yfinance, auto-adjusted daily OHLCV.
- Requested period: 2016-01-01 through 2026-09-12; latest completed bar was 2026-09-11.
- Current-universe symbols: 1,840 stocks plus a separate SPY benchmark.
- Stock rows: 4,129,390 downloaded; 4,129,390 includes SPY before separation and 4,126,702 stock rows were written to the price archive.
- Price archive SHA-256: `dbb63ab89bc1aba69a62452fe2d267aca9cdf6ef8ec9d3d214f8e847d9fa0f61`.
- Benchmark SHA-256: `2f23c2f096c0f712ab102a938b5aa0e04dad78b7345355b525a9b979a08e09f9`.
- Preregistered engineering discovery period: 2017-01-01 through 2023-12-31.
- Stage 2 transition signals: 30,129.
- The 2024–2025 period was not evaluated as a holdout. A post-run boundary audit found that late-2023 discovery signals used up to 40 sessions of early-2024 prices for their outcomes, so early 2024 is contaminated for this experiment version and may not be described as untouched. The numerical discovery results are preserved rather than rewritten.
- Execution: next-session open, 5 bps entry and exit slippage, signal-date 20-session structural low fixed after entry, stop-first ambiguity policy, 40-session maximum hold, USD 587 normalized initial risk, maximum four simultaneous positions.

The current-universe construction excludes historical failures and delistings. Utilities use today's sector mapping rather than effective-dated classifications. Results may therefore be materially optimistic or distorted and cannot validate, reject, add, or remove a production filter.

## Results

| Candidate rule | Signals kept | Portfolio trades | Expectancy R | Delta vs baseline R | Profit factor | Maximum drawdown R | Bootstrap 95% mean interval R |
|---|---:|---:|---:|---:|---:|---:|---:|
| MODEL_0 baseline | 30,129 | 259 | 0.348 | — | 1.644 | 22.284 | 0.087 to 0.659 |
| Recent RS ≥ 70 | 11,627 | 263 | 0.216 | -0.133 | 1.402 | 29.281 | 0.001 to 0.461 |
| Long-term RS ≥ 75 | 12,636 | 278 | 0.280 | -0.069 | 1.484 | 25.516 | 0.004 to 0.579 |
| Volume ratio ≥ 0.30 | 30,016 | 261 | 0.317 | -0.031 | 1.576 | 22.284 | 0.045 to 0.609 |
| ADR between 1% and 10% | 29,597 | 262 | 0.236 | -0.113 | 1.430 | 26.678 | 0.013 to 0.478 |
| Within current extension limits | 29,736 | 255 | 0.324 | -0.024 | 1.607 | 18.276 | 0.041 to 0.615 |
| Exclude rolling beta below 0.8 | 20,880 | 274 | 0.215 | -0.134 | 1.371 | 21.795 | 0.002 to 0.457 |
| Exclude Utilities | 29,239 | 256 | 0.414 | +0.065 | 1.758 | 18.276 | 0.119 to 0.729 |

Trade counts can rise after applying a filter because removing an earlier long-held position changes which later signals receive one of the four portfolio slots. Exposure was approximately 0.98–0.99 across variants. The ordinary bootstrap interval treats accepted trades as exchangeable and does not remove serial or regime dependence; it is uncertainty context, not a significance claim.

## Interpretation and decision

- This discovery does **not** support the claim that the current Recent RS ≥70, long-term RS ≥75, ADR, volume, or beta ≥0.8 rules improve MODEL_0 expectancy.
- Excluding low-beta stocks performed worse in this sample. The user's preference for high-beta opportunities remains a hypothesis, not an evidence-backed production rule.
- Excluding Utilities and enforcing extension limits are the only variants that improved the reported maximum drawdown; Utilities also improved discovery expectancy. Current classification and survivorship bias make that evidence insufficient for production.
- Industry qualification, sister confirmation, VCP, pullback quality, target structure, detailed entry timing, market regime, and drawdown-mode calibration were not historically evaluated because the free archive cannot reconstruct their required point-in-time inputs faithfully.
- Historical decision: **HOLD**. Acquire independent point-in-time validation data or accumulate forward evidence. Do not change production filters from this run.

## Forward-test state

`FORWARD_FILTER_AUDIT_V1` froze 208 candidates from the earliest complete snapshots across signal dates 2026-09-04, 2026-09-08, 2026-09-09, and 2026-09-11. As of the data cutoff, zero candidates had a complete five-session raw outcome. Raw 5/10/20/40-session returns, MFE, MAE, and rolling beta will populate as sessions mature.

The conservative plan simulator is active. Of the 208 frozen rows, 97 had no valid executable entry/stop plan, 71 valid shadow candidate plans did not trigger during their five-session entry window, and 40 triggered. Thirty-three triggered plans remain `OPEN_UNMATURED`; seven reached their stop, with realised results between -1.010R and -1.004R after the declared slippage model. All 40 triggered rows were frozen as WATCH or NO TRADE, so they are counterfactual filter evidence rather than authorized production trades. The only actionable row was HALF and did not trigger. There were no mature target or maximum-hold exits. This is only an operational sanity sample from four closely spaced signal dates, not an expectancy estimate: the preregistered review floor is 100 mature triggered observations, and temporal/ticker dependence must also be assessed.
