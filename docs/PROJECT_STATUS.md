# Project Status

Fast handoff as of 2026-09-11. Read `AGENTS.md` before this file and `docs/PROJECT_MEMORY.md` for durable context.

## Current state

- Branch: `main`, tracking `origin/main`. The five-commit
  `fix/production-risk-boundaries` series was merged through `432be57`.
- Remote confirmed: `https://github.com/Waynexchan/stock_screener.git`; it was not changed.
- Research-task starting commit: `ff44477d4918852ed81becc84890ce9add8b634c`.
- Worktree: clean after integration and verification. The former dirty `main`
  files were verified blob-for-blob against `origin/main` before integration;
  a local safety stash remains available as a recovery checkpoint.
- Production status: five fail-closed risk-boundary defects are corrected:
  unfinished/future-dated daily bars cannot be `CURRENT`; a current market label
  is not reused as the previous regime; missing, blank, or unsupported position
  status is invalid; market and portfolio stop-new-risk permissions are canonical
  hard gates; and accepted candidates share projected position, heat, and 2R
  daily new-initial-risk capacity in Final Score order.
- Canonical production command: `powershell -ExecutionPolicy Bypass -File .\scripts\run_daily_production.ps1`.
- Canonical verification command: `powershell -ExecutionPolicy Bypass -File .\scripts\verify_project.ps1`.
- Safe dry run: `powershell -ExecutionPolicy Bypass -File .\scripts\run_daily_dry_run.ps1`.
- Research verification: `powershell -ExecutionPolicy Bypass -File .\scripts\verify_research.ps1`.

## Last verification result

Pre-edit full-project baseline on 2026-09-10: PASS.

- Python syntax: PASS.
- Ruff format and lint: PASS.
- mypy: PASS.
- pytest: 170 passed.
- legacy unittest: 118 passed.
- industry integration tests: PASS.
- report invariants: PASS.
- offline sample Daily Watchlist dry run: PASS.
- generated HTML/CSV/email semantic validation: PASS.

Post-research full verification on 2026-09-10: PASS — 198 pytest tests, 118 legacy unittest tests, industry/report invariants, offline sample Daily Watchlist dry run, and generated HTML/CSV/email semantic validation all passed.

Focused research verification on 2026-09-10: PASS — Ruff, mypy, 28 research tests, gated MODEL_0 execution, and production-file hash isolation all passed. The gated run returned `BLOCKED_DATA_NOT_READY`, not performance evidence.

Post-P1-fix full verification on 2026-09-10: PASS — Python syntax, Ruff format
and lint, mypy, 204 pytest tests, 118 legacy unittest tests, industry/report
invariants, offline sample Daily Watchlist dry run, and generated HTML semantic
validation all passed.

Post-review P1 verification on 2026-09-10: PASS — 207 pytest tests cover the
additional market-permission, unknown-status, and aggregate 2R daily-risk
boundaries; 118 legacy unittest tests, industry/report invariants, the offline
sample dry run, and generated HTML semantic validation also passed. Focused
research verification remained at 28 tests and confirmed production isolation.

Follow-up risk-boundary work on 2026-09-11 makes missing canonical market or
portfolio permission fail closed, enforces the position-status allowlist inside
the portfolio domain, and persists the 2R daily allowance across production
reruns using same-day position entries plus immutable same-signal-date
authorisations. Full verification passed with 213 pytest tests, 118 legacy
unittest tests, industry/report invariants, the offline sample dry run, and
generated HTML semantic validation.

The subsequent independent-review findings are addressed: incomplete snapshot
directories can no longer make the daily ledger look empty, and Defensive-mode
same-day new-position usage is reconstructed rather than reset for each run.
Full verification passed with 215 pytest tests, 118 legacy unittest tests,
industry/report invariants, the offline sample dry run, and generated HTML
semantic validation.

The final empty-directory crash window is now covered: absence of a signal-date
directory means no prior ledger, while an existing signal-date directory with no
complete run fails closed. Full verification passed with 216 pytest tests, 118
legacy unittest tests, industry/report invariants, the offline sample dry run,
and generated HTML semantic validation.

Post-merge full verification on 2026-09-11: PASS — Python syntax, Ruff format
and lint, mypy, 216 pytest tests, 118 legacy unittest tests, industry/report
invariants, the offline sample Daily Watchlist dry run, and generated HTML
semantic validation all passed on `main`.

Post-merge research verification on 2026-09-11: PASS — Ruff, mypy, 28 research
tests, the expected `BLOCKED_DATA_NOT_READY` MODEL_0 gate, and production-file
hash isolation all passed.

## High-priority known issues

- There is not yet enough valid historical evidence to claim positive expectancy.
- The causal engine and fixed ablation infrastructure now exist, but no trustworthy historical dataset is available to exercise a five-to-ten-year universe study.
- Historical universe/classification/market-cap survivorship controls are incomplete.
- Market-cap enforcement remains disabled due to incomplete reliable coverage.
- Compatibility decision and preliminary review/ranking functions remain architectural surface area, although production exports currently use and validate the canonical path.
- No matching Windows Scheduled Task or repository task-registration script was found during inspection; any scheduler must call the production wrapper.

## Research status

The isolated `research/` layer now provides causal features, structurally separate outcomes, conservative next-session execution, R accounting, portfolio capacity, reusable metrics, manifests, reports, and fixed ablation helpers. MODEL_0 is implemented but its empirical run is blocked by the data-readiness gate. Strategy features remain `UNASSESSED`; operational data, stop, heat, position-count, and drawdown protections remain `CORE_RISK_CONTROL`. No feature is marked `VALIDATED`, and no research result has been promoted.

Local-data audit result: **NOT_READY**. There is no durable OHLCV archive, historical universe membership, delisted coverage, effective-dated classifications, market-cap history, or benchmark archive. Any current-symbol substitute must be labelled **SURVIVORSHIP-BIASED RESEARCH**. See `docs/DATA_READINESS.md`.

## Next recommended task

Acquire and provenance-check point-in-time price, benchmark, universe, and delisted-symbol history. Once the data gate is satisfied, run the predeclared **RECENT RS ABLATION** against MODEL_0 without changing production thresholds.

Do not run the Recent RS experiment or promote any result without explicit instruction and governance review.
