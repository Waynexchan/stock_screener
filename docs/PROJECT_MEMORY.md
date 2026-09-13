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
- unfinished or future-dated daily bars being treated as current;
- current-run market labels being mistaken for persisted prior-regime state;
- missing, blank, or unsupported position status being interpreted as zero open
  positions;
- market or portfolio stop-new-risk permission being omitted from canonical
  decisions;
- candidates independently reusing portfolio position/heat capacity or exceeding
  the aggregate daily new-initial-risk cap, including by resetting that cap on a
  same-day rerun;
- compatibility callers bypassing a fail-closed permission or status check at
  the canonical/domain boundary.

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

## 2026-09-13 filter-audit evidence

`FILTER_AUDIT_V1` is a preregistered, production-isolated engineering discovery
using the current 1,840-symbol universe and Yahoo adjusted OHLCV. It is labelled
`SURVIVORSHIP-BIASED RESEARCH`; it did not evaluate the reserved 2024-2025
holdout. Across the 2017-2023 discovery period it found 30,129 MODEL_0 Stage 2
transition signals and 259 capacity-limited baseline trades. Full results and
dataset hashes are preserved in `docs/RESEARCH_RESULTS_FILTER_AUDIT_V1.md`.

The discovery did not support the fixed Recent RS >=70, long-term RS >=75, ADR,
volume, or rolling beta >=0.8 rules as expectancy improvements over MODEL_0.
Excluding Utilities was promising for expectancy and drawdown, and current
extension limits reduced drawdown, but neither result is validation because the
universe excludes historical failures and Utilities use current classifications.
No production rule changed. `FORWARD_FILTER_AUDIT_V1` freezes the earliest
complete immutable snapshot per signal date and accumulates 5/10/20/40-session
raw return, MFE, MAE, and signal-date rolling beta as outcomes mature. Its
conservative five-session plan-trigger simulator applies declared slippage,
gap, same-bar stop-first, target, and 40-session maximum-hold rules without
turning an open immature trade into a result. The initial four signal dates
contain 40 triggered shadow candidate plans, of which 33 remain open/unmatured
and seven stopped out. None was an actionable FULL/HALF trade; the sole
actionable HALF row did not trigger. This is below the 100-mature-plan review
floor and is not performance evidence.

`EXIT_STOP_GRID_V1` preregistered and reported all 20 combinations of no target,
2R, 2.5R, and 3R with a fixed signal-date 20-day low, entry minus 0.5/1 ATR, or
signal-day low minus 0.5/1 ATR. The original no-target/20-day-low baseline was
strongest at 0.348R expectancy, 1.644 profit factor, and 22.284R maximum
drawdown. No variant met the discovery shortlist gate. The result reuses the
survivorship-biased 2017–2023 sample, leaves the 2024–2025 holdout untouched,
and changes no production rule.

## Decisions already made

- Production decisions are deterministic; AI cannot override them.
- New strategy ideas default to `RESEARCH_ONLY`.
- Systematic investment/trading research uses the optional project-local
  `.agents/skills/research-experiment/SKILL.md` governance workflow; loading the
  skill does not authorise production changes.
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

- Date: 2026-09-12 (Europe/London).
- Research-skill upstream repository:
  `https://github.com/Waynexchan/ai-agent-workflow-template.git`.
- Upstream version/source: `VERSION` 1.1.0 at commit
  `b088397622cf8fb0013396162e7a909b63937d34`. No Git tag points at that commit;
  `VERSION` is the verifiable release marker used by the template.
- Exact upstream Git blob IDs at that source commit:
  - `.agents/skills/research-experiment/SKILL.md`:
    `216013d78b8d220e50dcbc9ef5c2fb88f10df5c8`
  - `templates/RESEARCH_HYPOTHESIS.md`:
    `d7c23c5015e3eafd4fd45d6fe785b2778cb5fd78`
  - `templates/EXPERIMENT_LOG.md`:
    `877432920dc6b8863a07b074ee8248835d797499`
  - `templates/FORWARD_TEST_PLAN.md`:
    `41783591dfc3b261ec41b9257764b94c98156dbb`
- Stock-screener integration base:
  `ca4b2df5c0130360d302e70970ba7e873a493163`. The first project-adapted
  integration checkpoint is `8e44ce4afff57747eba3ee0c234df17a6626fb6b`;
  local files intentionally add repository-specific boundaries and therefore
  are not expected to match the upstream blobs byte-for-byte.
- Post-integration full-project and focused research verification both passed;
  the focused gate remained `BLOCKED_DATA_NOT_READY`, with no performance claim.
- Research-task source baseline: `ff44477d4918852ed81becc84890ce9add8b634c` on `main`.
- Worktree note: verification also covered substantial preserved, pre-existing uncommitted source/tests/docs; the base commit alone does not describe the tested source state.
- Command: `powershell -ExecutionPolicy Bypass -File .\scripts\verify_project.ps1`.
- Integrated-main result: PASS after merging the five production-risk commits
  through merge commit `432be57` — 216 pytest tests, 118 legacy unittest tests,
  Ruff, mypy, industry/report invariants, the offline sample dry run, and
  generated HTML semantic validation.
- Post-merge research verification: PASS — Ruff, mypy, 28 research tests, the
  expected `BLOCKED_DATA_NOT_READY` MODEL_0 gate, and production-file hash
  isolation.
- Post-research full-project result: PASS — 198 pytest tests, 118 legacy unittest tests, industry integration tests, report invariants, offline sample dry run, and generated HTML/CSV/email semantic validation.
- Focused research result: PASS — Ruff, mypy, 28 tests, a gated MODEL_0 report, and unchanged production-file hashes. Data status is `NOT_READY`; no baseline performance is claimed.
- Production-risk boundary fix result: PASS — 204 pytest tests, 118 legacy
  unittest tests, industry/report invariants, offline sample dry run, and generated
  HTML semantic validation. Six regression tests cover the five corrected P1
  findings, including separate shared position-count and heat-capacity cases.
- Post-review boundary result: 207 pytest tests pass after adding direct
  regressions for market permission, unsupported position status, and the 2R
  aggregate daily new-initial-risk cap. The 118-test legacy suite, industry and
  report invariants, offline dry run, HTML semantic validation, and focused
  research production-isolation verification also pass.

Daily new-initial-risk usage is reconstructed from current-market-date position
entries and immutable forward snapshots for the same signal date. Snapshot
authorisations are deduplicated by ticker using the largest prior risk amount;
an unreadable existing authorisation ledger blocks new risk. This is operational
risk state, not research evidence or a strategy filter.

Snapshot-ledger discovery must enumerate every run directory and require the
complete candidates/market/portfolio/config/metadata artifact set plus matching
signal date and candidate count. Merely globbing existing `candidates.csv` files
can silently ignore a partial write and must not be used. The reconstructed
same-day ticker set supplies both used initial R and the Defensive-mode daily
new-position count.

For snapshot-ledger state, a missing signal-date directory means no prior
authorisation. An existing but empty signal-date directory can be left by an
interrupted first write and must make the ledger unavailable; it must never be
interpreted as a zero balance.

The 2026-09-11 empty signal-date directory follow-up passed full verification
with 216 pytest tests, 118 legacy unittest tests, industry/report invariants,
the offline sample dry run, and generated HTML semantic validation.

The 2026-09-11 partial-snapshot and Defensive-counter follow-up passed full
verification with 215 pytest tests, 118 legacy unittest tests, industry/report
invariants, the offline sample dry run, and generated HTML semantic validation.

The 2026-09-11 follow-up full verification passed with 213 pytest tests, 118
legacy unittest tests, industry/report invariants, the offline sample dry run,
and generated HTML semantic validation.

The framework checkpoint hash is recorded in the task handoff because a commit cannot contain its own hash.
