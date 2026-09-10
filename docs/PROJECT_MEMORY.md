# Project Memory

This is durable engineering and research context, not a chat transcript. Read `AGENTS.md` first.

## Mission and trading style

Maintain a disciplined US-stock swing-trading decision system for approximate one-to-two-month holding periods. Judge the system by positive expectancy, risk/reward, maximum drawdown, exposure, and robust out-of-sample behavior. Do not optimise for signal volume, win rate alone, or rule complexity. Prefer simpler rules when their performance is comparable.

## Risk model

- Standard `1R`: USD 587.
- `FULL`: maximum `1R` initial risk.
- `HALF`: maximum `0.5R` initial risk.
- `WATCH` and `NO TRADE`: zero risk and zero shares.
- Default maximum open positions: four, subject to the canonical configuration.
- Market heat, portfolio heat, industry/theme concentration, drawdown, and simultaneous positions take precedence over producing frequent trades.

`docs/RISK_MODEL.md` contains the current calculation definitions.

## Current architecture

```text
scripts/run_daily_production.ps1
  -> scripts/verify_project.ps1
  -> SCREENER_VERIFIED=1
  -> run_screener.py:main
     -> market/universe/data validation
     -> screen_stocks and category discovery
     -> export_results
        -> build_decision_context
        -> apply_canonical_decision_pipeline
           -> decision_system.canonical_candidate_decision
           -> concentration limits and invariant validation
        -> CSV / Markdown / HTML / email summary
        -> cross-output semantic validation
        -> immutable forward snapshot / last-good files / summary history
     -> send_email.py
```

AI commentary is optional. It receives the validated Top Action List and may assist presentation/prioritisation, but it is not decision authority.

Compatibility functions (`size_trade_candidate`, `decide_candidate`) and older review/ranking helpers remain. Production exports currently overwrite preliminary guidance with the canonical pipeline and validate the result, but this extra surface is a maintenance risk and should not be allowed to become an alternate decision path.

The research layer is separate from production:

```text
research data + point-in-time membership
  -> research/engine causal FEATURES at T
  -> MODEL_0 EOD signal
  -> next available session execution
  -> conservative simulated exit and initial-risk R
  -> position-capacity simulation
  -> metrics / fixed ablation / isolated report
```

Future OUTCOMES are created after features and are never inputs to feature generation. Research outputs are restricted to `research/output/`; the research verifier hashes production source, reports, portfolio data, and forward snapshots before and after execution.

## Canonical commands

```powershell
# Full verification
powershell -ExecutionPolicy Bypass -File .\scripts\verify_project.ps1

# Verified, offline sample dry run
powershell -ExecutionPolicy Bypass -File .\scripts\run_daily_dry_run.ps1

# Verified production run; may use network, AI, and email according to configuration
powershell -ExecutionPolicy Bypass -File .\scripts\run_daily_production.ps1

# Research checks, gated MODEL_0 report, and production-isolation hashes
powershell -ExecutionPolicy Bypass -File .\scripts\verify_research.ps1

# Inspect latest logs
Get-Content .\logs\verify_project.log -Tail 100
Get-Content .\logs\production.log -Tail 100
```

## Key files

- `config.py`: thresholds, risk constants, data paths, and feature flags.
- `decision_system.py`: canonical decision/sizing, portfolio risk, drawdown, market regime, industry qualification, scoring, and expectancy helpers.
- `run_screener.py`: universe/data pipeline, candidate discovery, production orchestration, reports, semantic invariants, snapshots, and history.
- `ai_analysis.py`: optional AI commentary and ranking guardrails.
- `send_email.py`: Gmail SMTP delivery of the generated HTML report and failure notices.
- `scripts/verify_project.ps1`: authoritative verification workflow.
- `scripts/validate_report.py`: CSV/HTML/email manifest and semantic validation.
- `sample_daily_run.py`: deterministic offline sample report.
- `tests/` and `test_data_quality.py`: behavior, regression, integration, data-quality, and production-integrity coverage.
- `research/filter_registry.json`: evidence/status registry for strategy features and core controls.
- `research/engine/`: point-in-time features, separated outcomes, execution, R accounting, portfolio capacity, metrics, ablation, reporting, and reproducibility manifests.
- `research/config/model_0.json`: versioned minimal baseline assumptions; it is independent of production configuration.
- `research/experiments/recent_rs.json`: predeclared Recent RS buckets and horizons; prepared but not run.
- `docs/RESEARCH_ARCHITECTURE.md` and `docs/DATA_READINESS.md`: dependency/reuse audit and verified data limitations.
- `scripts/verify_research.ps1`: focused research verification and production-file hash-isolation gate.
- `BACKTEST_REQUIREMENTS.md`: requirements for a future point-in-time replay engine; it is not an implemented backtest.

## Runtime and historical artifacts

Runtime files include `daily_watchlist*`, `email_summary.txt`, `summary_history.csv`, universe and metadata caches, `.yfinance_cache/`, `logs/`, and `data/`. Immutable forward evidence is stored under `output/forward_snapshots/<signal-date>/<run-id>/`. Local open positions, account equity, and completed trades live under `data/`. These are ignored and must not be casually committed or rewritten.

## Important historical bugs and concerns

The project has previously identified or guarded against:

- duplicate or conflicting decision paths and cross-output contradictions;
- missing Recent RS becoming actionable;
- invalid stops, structural R/R, model-generated targets, or stale prices becoming actionable;
- market-cap enforcement being claimed without reliable coverage;
- incomplete/stale industry metadata and misleading qualification;
- portfolio/equity data being treated as zero risk when unavailable;
- generated reports diverging from the canonical record;
- historical snapshots being mutable or created before semantic validation.

Do not mark these permanently fixed merely because current tests pass. Preserve the tests and validate the relevant path after changes.

## Known limitations

- Historical data is insufficient to honestly claim positive expectancy; MODEL_0 currently has zero valid empirical signals/trades because execution is data-gated.
- The point-in-time engine exists, but the repository has no durable multi-year OHLCV archive to run through it.
- Survivorship-bias-controlled universe membership, historical industry/market-cap metadata, delistings, and corporate actions are not yet established.
- Benchmark history is not durably archived. Any current-symbol engineering run must be labelled `SURVIVORSHIP-BIASED RESEARCH` and cannot validate a filter.
- The configured USD 500m market-cap threshold is not enforced because reliable complete metadata is unavailable.
- Exceptional exchange closures are not fully represented by the current calendar.
- Compatibility decision/review surfaces remain and increase regression risk.
- No repository task-registration script exists, and no matching Windows Scheduled Task was visible during the 2026-09-09 inspection; the required scheduler target is nevertheless the production wrapper.

## Current research questions

- Which existing filters add economically meaningful incremental expectancy after costs?
- Which filters reduce maximum drawdown or improve payoff enough to justify their complexity?
- Which correlated filters are redundant?
- How stable are results across regimes, time periods, industries, and liquidity bands?
- What evidence sample is required before changing production?

## Decisions already made

- Production decisions are deterministic; AI cannot override them.
- New strategy ideas default to `RESEARCH_ONLY`.
- Existing implementation is not proof that a filter is validated.
- No missing critical value may be replaced with a plausible value.
- Report outputs must agree with the canonical decision record before publication/history/snapshot preservation.
- The production wrapper must verify before running.
- MODEL_0 is a deliberately minimal research reference, not a production recommendation. Its alpha exclusions include Recent RS, industry, sister confirmation, VCP, pullback quality, complex scores, Final Score, and AI commentary.
- Research Phase 1 changes no production logic, thresholds, sizing, watchlist, email, or schedule behavior.

## Do not casually change

Canonical decision ownership, the USD 587 risk unit, FULL/HALF semantics, maximum-position and heat controls, point-in-time requirements, freshness behavior, output semantic validation, safe dry-run isolation, last-good preservation, immutable forward snapshots, remote configuration, and ignored runtime/private-data boundaries.

## Next-step roadmap

1. Acquire provenance-auditable adjusted price and benchmark history plus point-in-time universe membership including delistings.
2. Re-run MODEL_0 through the data-readiness gate and review sample coverage and biases.
3. Run the predeclared Recent RS ablation across fixed buckets and 5/10/20/40-session horizons.
4. Test remaining filters one at a time and in correlated groups, then review evidence before classifying or simplifying production features.

Do not begin these steps without an explicit task.

## Last verified

- Date: 2026-09-10 (Europe/London).
- Research-task source baseline: `ff44477d4918852ed81becc84890ce9add8b634c` on `main`.
- Worktree note: verification also covered substantial preserved, pre-existing uncommitted source/tests/docs; the base commit alone does not describe the tested source state.
- Command: `powershell -ExecutionPolicy Bypass -File .\scripts\verify_project.ps1`.
- Post-research full-project result: PASS — 198 pytest tests, 118 legacy unittest tests, industry integration tests, report invariants, offline sample dry run, and generated HTML/CSV/email semantic validation.
- Focused research result: PASS — Ruff, mypy, 28 tests, a gated MODEL_0 report, and unchanged production-file hashes. Data status is `NOT_READY`; no baseline performance is claimed.

The framework checkpoint hash is recorded in the task handoff because a commit cannot contain its own hash.
