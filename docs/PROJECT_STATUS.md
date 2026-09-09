# Project Status

Fast handoff as of 2026-09-09. Read `AGENTS.md` before this file and `docs/PROJECT_MEMORY.md` for durable context.

## Current state

- Branch: `main`, tracking `origin/main`.
- Remote confirmed: `https://github.com/Waynexchan/stock_screener.git`; it was not changed.
- Verified source baseline: `aaa7a7ddffa09e7d5f99836ded784c34e9676e97`.
- Worktree: substantially dirty before this framework task. Existing modified/untracked source, tests, scripts, docs, and runtime outputs are preserved and are not owned by this checkpoint.
- Production status: post-framework verification passed; no production trading logic or output behavior was intentionally changed by the agent-framework task.
- Canonical production command: `powershell -ExecutionPolicy Bypass -File .\scripts\run_daily_production.ps1`.
- Canonical verification command: `powershell -ExecutionPolicy Bypass -File .\scripts\verify_project.ps1`.
- Safe dry run: `powershell -ExecutionPolicy Bypass -File .\scripts\run_daily_dry_run.ps1`.

## Last verification result

Post-framework run on 2026-09-09: PASS.

- Python syntax: PASS.
- Ruff format and lint: PASS.
- mypy: PASS.
- pytest: 170 passed.
- legacy unittest: 118 passed.
- industry integration tests: PASS.
- report invariants: PASS.
- offline sample Daily Watchlist dry run: PASS.
- generated HTML/CSV/email semantic validation: PASS.

The framework checkpoint hash is recorded in the task handoff because a commit cannot contain its own hash.

## High-priority known issues

- There is not yet enough valid historical evidence to claim positive expectancy.
- The point-in-time research/backtest and filter-ablation framework is not implemented.
- Historical universe/classification/market-cap survivorship controls are incomplete.
- Market-cap enforcement remains disabled due to incomplete reliable coverage.
- Compatibility decision and preliminary review/ranking functions remain architectural surface area, although production exports currently use and validate the canonical path.
- No matching Windows Scheduled Task or repository task-registration script was found during inspection; any scheduler must call the production wrapper.

## Research status

The initial registry records identifiable components without fabricating results. Strategy features are `UNASSESSED`; operational data, stop, heat, position-count, and drawdown protections are `CORE_RISK_CONTROL`. No feature is marked `VALIDATED`, and no research result has been promoted.

## Next recommended task

Build the evidence-based research/ablation framework and test existing filters before simplifying production.

Do not execute that strategy/research task without explicit instruction.
