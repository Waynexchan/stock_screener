# Stock Screener Agent Operating Manual

This file is the authoritative operating manual for coding agents in this repository. Read it before `docs/PROJECT_STATUS.md` and `docs/PROJECT_MEMORY.md`.

## Project purpose

Build and maintain a high-performance US-stock swing-trading decision system for an approximate one-to-two-month holding period. Optimise for positive expectancy, strong risk/reward, controlled maximum drawdown, limited simultaneous positions, and robust out-of-sample performance—not signal count, headline win rate, complexity, or plausible-sounding filters.

Performance must be established with evidence. Prefer the simpler rule when performance is comparable. Intuition may generate a research hypothesis; it does not authorise a production rule.

Risk philosophy:

- Standard `1R` is USD 587.
- `FULL` may risk at most `1R` initially.
- `HALF` may risk at most `0.5R` initially.
- Maximum positions, portfolio heat, concentration, and drawdown must remain explicit controls.

## Source of truth

Preserve one canonical path at each boundary:

- Production entry: `scripts/run_daily_production.ps1`.
- Python orchestration: `run_screener.py:main`.
- Candidate decision and sizing: `decision_system.canonical_candidate_decision`, called for production by `run_screener.apply_canonical_decision_pipeline`.
- Verification: `scripts/verify_project.ps1`.

Compatibility functions such as `size_trade_candidate` and `decide_candidate`, plus pre-decision review/ranking helpers in `run_screener.py`, remain architectural surface area. They must delegate to or be overwritten by the canonical decision pipeline; they may not silently become a second authority. Treat this as a known maintenance risk, not as proof that all historical ambiguity has been eliminated.

AI may describe or order already validated records. AI commentary must never change a deterministic final decision, actionability, risk, shares, stop, target, or confirmation state.

## Before every change

For every meaningful task:

1. Read this file, `docs/PROJECT_STATUS.md`, and the relevant project memory/docs.
2. Record `git status --short --branch`, current branch, commit, and remotes. Preserve all user changes.
3. Understand the requested behavior and classify the task as production, research, or both.
4. Find the authoritative implementation, entry point, schemas, callers, and relevant tests; do not edit the first matching function blindly.
5. Run the baseline tests appropriate to the scope and reproduce a reported issue where practical.
6. State any unresolved ambiguity instead of assuming it away.

## Development rules

- Diagnose root cause before fixing symptoms or generated reports.
- Make the smallest coherent change; do not duplicate decision logic.
- Never add ticker-specific fixes or change strategy semantics merely to satisfy a test.
- Do not silently replace missing or invalid data with a plausible value. Missing critical data must remain explicit and non-actionable.
- Keep production decisions deterministic. AI cannot override them.
- Never use market data after the calculation date. Research must be point-in-time aware and disclose unavailable point-in-time fields.
- Never claim survivorship-bias control unless the data actually supports it.
- Preserve backward compatibility unless the requested change explicitly requires otherwise.
- Add or update automated behavior tests for every behavior change and a regression test for every confirmed bug where practical.
- Update `docs/USER_GUIDE.md` whenever user-facing behavior changes and other documentation as applicable.

## Production versus research

`PRODUCTION` is only logic explicitly approved to control the live Daily Watchlist.

`RESEARCH` contains experimental signals, thresholds, filters, rankings, and models. Every new strategy idea defaults to `RESEARCH_ONLY` until its evidence is reviewed and production use is explicitly approved.

Research must not silently affect `FULL`, `HALF`, `WATCH`, `NO TRADE`, actionability, risk size, shares, production email, or production report. A research feature may be shown in a separately labelled research field or artifact without gating production.

Do not redesign the strategy or promote a research result as part of unrelated engineering work.

## Filter governance

Track important components in `research/filter_registry.json` using these statuses:

- `VALIDATED`: empirical evidence demonstrates meaningful incremental value over a simpler baseline, including validation evidence.
- `RESEARCH_ONLY`: an active hypothesis that cannot affect production.
- `REJECTED`: tested and not worth the incremental complexity.
- `CORE_RISK_CONTROL`: primarily protects operational safety, data validity, portfolio heat, maximum positions, stops, or stale-data prevention.
- `UNASSESSED`: present or proposed, but the repository lacks sufficient evidence to classify it.

Existing production presence is not evidence of validation. Do not fill unknown result fields with invented numbers.

## Testing and self-debugging

Use focused tests while developing. Before declaring any meaningful change complete, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_project.ps1
```

That script is the required verification entry and currently covers syntax compilation, Ruff format/lint, mypy where supported, pytest/unit/regression tests, the legacy unittest suite, industry integration tests, report invariants, the safe sample Daily Watchlist dry run, and generated HTML/CSV/email semantic validation.

When verification fails:

1. Stop normal production report/email generation.
2. Identify the first meaningful failure and decide whether later failures are cascades.
3. Reproduce it with the smallest relevant test and inspect its inputs/outputs.
4. Fix the implementation rather than weakening the assertion.
5. Rerun the focused test, then affected suites, then full verification.
6. Preserve `logs/verify_project.log`, return non-zero, and name the failed stage.

For semantic bugs, trace the canonical internal record through CSV, HTML, and email and proactively compare them for contradictions.

## Report semantic invariants

- One ticker has one canonical final decision.
- Canonical internal records, CSV, HTML, and email manifests agree.
- `FULL` equals at most `1R` / USD 587 initial risk; `HALF` equals at most `0.5R` / USD 293.50.
- `WATCH` and `NO TRADE` are non-actionable, have zero risk, and receive zero shares.
- Missing critical data, invalid stops, invalid structural R/R, stale bars, or synthetic model targets cannot silently become actionable.
- Synthetic research values may not masquerade as observed or validated structural values.
- Final output must have no duplicate tickers, contradictory decisions/confirmation, actionable rows with missing Recent RS, impossible heat, stale industry ranks, inconsistent counts, or omitted warnings.

Do not invent new trading thresholds while enforcing these invariants.

## Git safety

- Inspect status before and after work. Never discard, overwrite, stage, or commit unrelated user changes.
- Never use `git reset --hard` or change a remote without explicit instruction and a verified need.
- Use meaningful local commits/checkpoints and report the exact hash.
- Do not push unless the user explicitly requests it or the established project workflow unambiguously requires it.
- Runtime reports, caches, secrets, credentials, local portfolio/trade data, databases, and logs must not be committed. Do not remove already tracked files merely because they look generated without first reporting the impact.

## Windows and automation safety

- Production wrapper: `scripts/run_daily_production.ps1`.
- Safe development/dry-run wrapper: `scripts/run_daily_dry_run.ps1`.
- Both resolve the repository root from their own location and set it as the working directory.
- Production logs: `logs/production.log`; verification log: `logs/verify_project.log`.
- A Windows Scheduled Task must invoke the production wrapper, not `run_screener.py` directly. The wrapper verifies first and sets `SCREENER_VERIFIED=1` only after success; Python rejects an unverified normal run.
- Verification failure must block the normal report/email and write the failure notice/log. Scheduled runs may report failure but must never modify source.
- A safe sample dry run must never use network data, send email, call AI, overwrite production reports, append production history, or create production forward snapshots.
- Do not modify Windows Scheduled Tasks unless the task explicitly authorises it.

## Completion report

Report files changed, commands run, exact results, assumptions, limitations, remaining issues, Git status, and any checkpoint hash. Do not declare completion while a required check fails.
