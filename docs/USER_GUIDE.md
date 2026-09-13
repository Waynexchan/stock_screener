# Daily Trading Decision System User Guide

The report separates three independent questions: whether the market permits new risk, whether portfolio heat permits new risk, and whether an actionable setup exists. A supportive market and an empty portfolio do not force a trade.

The Executive Summary uses `READY` when a FULL setup is confirmed,
`CONDITIONAL` when an actionable reduced-risk HALF exists, and `NO` when market,
portfolio, or setup gates prohibit a new trade. HALF is actionable now; it never
means Watch Later or confirmation is still required before trading.
`System Warnings` counts distinct warning messages, while `Affected Candidates`
counts unique rows with price, incomplete-data, or model-target warnings.

Portfolio status always appears. Supported status values are `open` and
`closed` (case-insensitive, with surrounding whitespace ignored). An existing
position file with valid statuses and no rows marked `open` is a genuine
`0.00R`; a missing `status` column, blank or unsupported status value, stale
data, or invalid file is `Not Available` and blocks final new-risk permission.

The production decision pass treats market and portfolio permissions as hard
gates and allocates candidates in descending Final Score order. Every accepted
FULL/HALF candidate consumes the same projected open-position, heat, and daily
new-initial-risk capacity seen by later candidates; capacity is never reset per
row or production rerun. The configured 2R daily cap includes same-market-date
position entries plus prior authorisations recovered from immutable forward
snapshots for the same signal date. Repeated snapshots of the same ticker retain
its largest authorisation instead of double-counting it. If this ledger is
partial, incomplete, or unreadable, new risk is blocked rather than reset to
zero. An absent signal-date directory means no prior authorisation, but an
already-created empty signal-date directory is treated as an interrupted write
and blocks new risk. The same reconstructed ticker set also preserves the
Defensive-mode daily new-position count across reruns.

Only `Qualified Current Leaders` appear in actionable Top Industries. Rotation watches, lagging long-term leaders, and small-sample groups remain visible but do not grant normal industry or sister-stock confirmation.

Provisional entry, stop, and target values use observable price structure and show their source. A `model 2R feasibility target` is a planning test, not observed resistance or a prediction.
Observed resistance is reported at its actual price and is never clamped to an
artificial 2R value. Entry Timing is `NOT AVAILABLE` until entry, stop, and
target are all structurally available.

A candidate whose only target is the `model 2R feasibility target` cannot be
promoted to FULL or HALF. It remains NO TRADE until chart-supported resistance,
a prior high, or another validated structural target confirms the reward side.
Market Regime is marked complete only when index slopes, breadth, breakout
quality, leadership, and volatility inputs are all present. Thin breakout or
leadership samples reduce confidence and appear under Data and Logic Warnings.

## Purpose and limits

The system screens long-only US momentum swing opportunities, validates trade plans, monitors open risk, records completed trades, and reports evidence. It does not predict prices, guarantee profits, execute trades, invent missing values, or replace chart review.

## Daily workflow

1. Update `data/open_positions.csv` with ticker, entry date, entry price, initial stop, active stop, shares, and status.
2. Run `powershell -ExecutionPolicy Bypass -File .\scripts\run_daily_dry_run.ps1` after development changes.
3. Run `powershell -ExecutionPolicy Bypass -File .\scripts\run_daily_production.ps1` only for the verified production workflow.
4. Read Market Regime and Portfolio Risk before candidates.
5. Review `FULL`, then `HALF`, then `WATCH`, then the highest-quality `NO TRADE` reasons.
6. Make all trade decisions manually.

## Risk terms

Initial Risk is entry minus initial stop, multiplied by shares. It is fixed for trade R and expectancy. Current Open Risk is current price minus the active stop, multiplied by shares. P&L at Stop is the projected trade result if the active stop fills exactly. Portfolio Heat sums Effective Open Risk, including the overnight gap floor. Market Regime determines maximum heat and whether new risk is permitted.

## Decisions and sizing

- `FULL`: maximum initial risk 1.0R / USD 587. Core structure and R/R pass, entry timing is EARLY or OPTIMAL, and supporting confirmation plus market/drawdown capacity permit full risk.
- `HALF`: maximum initial risk 0.5R / USD 293.50. It is actionable now. Core structure and actual R/R pass, but secondary confirmation, marginal integrity, timing, or drawdown policy reduces size.
- HALF still requires either strong Recent RS or a clearly Improving/Emerging
  RS trend. Reduced size never admits a low and weakening RS candidate.
- `WATCH`: interesting but not ready. Risk is 0R, shares are zero, and actionability is false.
- `NO TRADE`: zero new risk because a structural, data, market, drawdown, heat, concentration, or position-count hard gate fails.
- `Caution` and `Risk Off` market regimes do not permit new positions, so otherwise
  valid structural plans remain `NO TRADE` instead of appearing as HALF candidates.
- Zero FULL/HALF candidates is valid. HALF is never an excuse for an invalid stop, unproven target, sub-2R plan, stale bar, or overextended entry. Final Score is a ranking summary, not a universal 75-point gate.

Maximum shares are `floor(risk budget dollars / (entry - structural stop))`.
The system never automatically upgrades an existing HALF position; any added
tranche needs its own new valid entry, stop, target, 2R plan, and available risk.

Update `data/account_equity.csv` with current equity and the latest high-water
mark. Missing equity data blocks new risk rather than assuming zero drawdown.

## Setup integrity and industries

Setup Integrity is `PASS`, `MARGINAL`, or `FAIL`. PASS may support FULL or HALF;
MARGINAL may support HALF but never FULL; FAIL is WATCH unless a separate hard
gate makes it NO TRADE. Under the current rule, a Loose Developing Base is FAIL
and cannot receive shares merely because market or portfolio capacity exists.

An industry must pass minimum size, positive absolute momentum, positive 20-day SPY-relative momentum, breadth, proximity-to-high, and breakout-quality gates. Raw member or candidate count does not create leadership. A blank rank means Not Qualified.

The report also shows universe member count, mapped and unmapped industry
metadata, coverage percentage, and cache date. Coverage below the configured
minimum marks industry evidence incomplete and prevents high-confidence
qualification/sister confirmation. The configured USD 500m market-cap filter is
currently shown as `NOT ENFORCED`; reliable values are not fabricated.

## Freshness and forward snapshots

Every candidate records generated time, signal date, price-data as-of date, and
latest bar timestamp. The gate expects the latest completed regular US session,
including weekends and regular full-day holidays. Exceptional exchange closures
are not covered by the current calendar; `PRICE_STALE_HOURS` is a fallback only
when session evaluation fails. A daily bar dated for the current session before
the close/grace boundary is `INCOMPLETE`, not `CURRENT`. Stale, future-dated, or
partial critical bars cannot be FULL or HALF.

After CSV, HTML, and email pass semantic cross-validation, each valid production
run creates a new evidence bundle under
`output/forward_snapshots/<signal-date>/<run-id>/`. It contains candidate inputs
and decisions, market, portfolio, config, hashes, metadata coverage, timestamps,
and reasons. Existing bundles are never overwritten.

## Positions and completed trades

For normal daily use, those seven trade facts are the only mandatory position
inputs. `theme`, `setup_type`, `stop_update_reason`, `notes`, and
`previous_stop` are optional. The screener derives current price, sector,
industry, and snapshot time from the same validated data used by the daily run.
It applies the configured standard R when a row has no historical override. A
missing theme is grouped conservatively under its industry for concentration
control. If a current price or classification cannot be derived, heat is shown
as unavailable rather than zero. Copy `data/open_positions_template.csv` as an
example and remove its EXAMPLE row before use.

The main HTML is deliberately short: read the Executive Summary, Market &
Portfolio Risk, FULL, HALF, WATCH, NO TRADE, and Qualified Current Industries. It
shows at most eight blocked names to explain the strongest rejected ideas. Full
candidate, industry, score, and history tables remain in the collapsed
**Diagnostic Appendix** for audit and debugging.
The email body contains only the human-readable summary. The machine-readable
decision manifest remains available to semantic validation and in the attached
HTML report, but is not printed as JSON in the message body.
The primary table separates incomplete secondary confirmation from genuine hard
invalidation and does not repeat the combined diagnostic reason text.

Never lower an active stop without a documented override reason. Record completed trades in `data/completed_trades.csv` using actual realised R, fees, and slippage. Expectancy remains `Insufficient sample` until the configured minimum sample is reached. One or two losses do not justify changing rules; rule changes require tests and an adequate completed-trade sample.

## Verification failures and configuration

If verification fails, do not run or email the normal report. Read `logs/verify_project.log`, correct the root cause, rerun the failed stage, then rerun the complete verification script. Change thresholds only in `config.py`, add tests explaining the intended behaviour, and rerun verification.

## Research-only portfolio backtest

The portfolio exposure study is separate from the Daily Watchlist and does not change live decisions. Run it only against an explicitly supplied research archive:

```powershell
python -m research.run_portfolio_exposure --prices research/output/yahoo_engineering/prices.csv --benchmark research/output/yahoo_engineering/benchmark.csv
```

It compares fixed 1R–4R heat, two 2R-start earned-exposure ladders, and drawdown-based risk modes. Results are written under `research/output/portfolio_exposure_v1/`; `summary.csv` contains all preregistered variants and each `equity__*.csv` contains the daily mark-to-market curve. These artifacts are research evidence only and cannot alter production sizing or permissions.

The complete exit/stop/exposure cross can be reproduced with:

```powershell
python -m research.run_combined_exit_exposure_grid --prices research/output/yahoo_engineering/prices.csv --benchmark research/output/yahoo_engineering/benchmark.csv
```

It reports all 180 preregistered cells in `research/output/combined_exit_exposure_grid_v1/grid_results.csv`, writes the complete gate passes to `shortlist.csv`, and preserves each numbered ledger and daily equity curve under `cells/`. A shortlist row is not production approval or permission to change the frozen forward test.

The simpler staged cross-validation study can be reproduced with:

```powershell
python -m research.run_easy_execution_cross_validation --prices research/output/yahoo_engineering/prices.csv --benchmark research/output/yahoo_engineering/benchmark.csv
```

It evaluates 168 frozen discovery combinations across six initial stops, seven target/time exits, and four exposure rules. It selects no more than three candidates before running the separate March–October 2024 validation. The 2025 holdout is calculated exactly once only when a candidate passes that validation gate. Discovery, validation, and holdout each restart at 100R; none of these research results changes the Daily Watchlist or the existing forward-test journal.

The separate earnings/exposure robustness runner accepts a long-form retrospective earnings calendar:

```powershell
python -m research.download_yahoo_earnings --start 2017-01-01 --end 2025-11-10
python -m research.run_earnings_exposure_robustness --prices research/output/yahoo_engineering/prices.csv --benchmark research/output/yahoo_engineering/benchmark.csv --earnings research/output/yahoo_earnings_engineering/earnings.csv --earnings-metadata research/output/yahoo_earnings_engineering/download_metadata.json
```

Its dynamic policy begins at two 1R positions, expands to at most three on the session after a net-profitable realised exit batch, and returns to two after a zero/negative batch. Its earnings variant rejects signals dated from zero through ten calendar days before the retrospective earnings event. These periods and earnings dates are not untouched point-in-time evidence, so the runner cannot change production decisions.

The corrected repeated-expansion experiment is:

```powershell
python -m research.run_staircase_exposure_robustness --prices research/output/yahoo_engineering/prices.csv --benchmark research/output/yahoo_engineering/benchmark.csv --earnings research/output/yahoo_earnings_engineering/earnings.csv --earnings-metadata research/output/yahoo_earnings_engineering/download_metadata.json
```

It starts at 2R and adds one 1R position slot after every net-profitable realised exit batch. It compares `STEP` loss contraction with an immediate `RESET` to 2R, under separate 4R, 6R, and 8R hard safety ceilings. State changes apply on the next session, existing positions are not forcibly sold after a contraction, and every cell uses the inclusive ten-calendar-day earnings blackout. The runner is research-only and uses already inspected, survivorship-biased prices plus retrospective earnings dates.

To regenerate every earlier filter, stop, exit, and exposure setting under the same earnings restriction:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_full_earnings_blackout_retest.ps1
```

This executes 385 settings across the filter audit, stop/exit grid, standalone exposure study, full 180-cell cross, and easy-execution 168-cell cross. The blackout is applied before candidate ranking and portfolio allocation. Outputs are separate from the preserved original studies and remain adaptive, survivorship-biased research; reused 2024/2025 data is not an untouched holdout.
