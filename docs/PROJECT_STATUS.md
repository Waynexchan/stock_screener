# Project Status

Fast handoff as of 2026-09-24. Read `AGENTS.md` before this file and `docs/PROJECT_MEMORY.md` for durable context.

## Current state

- `PATTERN_DISCOVERY_REPORTING_PHASE_1` separates the post-canonical report into
  Actionable Now, Pattern Watchlist, and Avoid / Failed. The latter two are
  explicitly `RESEARCH_ONLY`; missing plan values remain missing, and the
  classifier owns only report section/status/reason fields. Canonical
  `FULL/HALF/WATCH/NO TRADE`, actionability, risk, shares, trade-plan values,
  capacity, and concentration remain owned by the existing decision pipeline.
  The three report-only fields are excluded from the discovery and forward-
  snapshot schemas, and semantic validation rejects non-actionable rows placed
  on the wrong side of the explicit failure-evidence boundary. Classifier and
  validator agree that present non-finite entry/stop values are failures while
  genuinely missing plan values remain eligible for Pattern Watchlist.
  `PATTERN_DISCOVERY_SETUP_LANES_PHASE_2` adds three independent post-canonical
  `RESEARCH_ONLY` chart-review lanes: Tight Base / VCP, Pullback to Support, and
  Breakout Retest / High Flag. Each has separate membership, fixed score,
  missing-last deterministic rank, reason, and missing-factor evidence. The
  bounded breakout lookback distinguishes same-day unconfirmed breakouts from
  held/consolidating or invalidated recent breakouts; a persistent Phase 4 state
  machine is not implemented. Lane inputs/outputs are excluded from forward
  snapshots and cannot alter canonical decisions, production score, allocation,
  risk, shares, or trade-plan values. No trading-edge claim or production
  promotion is made.
- `PORTFOLIO_RANKING_PHASE_A_V1` has substantially implemented engineering
  infrastructure, but formal Phase A infrastructure is not complete and no
  evidence study has run. Phase B and Phase C are not implemented. Production
  capacity ordering now uses the explicit business key Final Score descending,
  then ticker ascending; input row order is no longer a tie-break. The
  research-only interface freezes eligibility before ranking, provides the
  production, deterministic-random, four single-factor, exact 25% composite,
  and four equal-weight leave-one-out arms, and evaluates all arms through the
  shared exit-aware portfolio state with a row-level heat audit. Non-finite
  scores are missing-last, canonical eligibility blocks are included in metrics,
  and a research runner can calculate the four frozen causal factors from a
  valid pre-allocation candidate journal. Existing post-allocation reports
  cannot reconstruct capacity-rejected candidates and are not valid runner
  inputs. Formal future development/validation/holdout windows and the Phase B
  shortlist gate are frozen in the preregistration. Stage outcomes crossing an
  observation cutoff are censored and cannot count as mature; both baseline and
  challenger must meet the sample floor. Candidate concentration is reapplied
  after each ranker orders candidates, using the frozen production industry,
  high-conviction, and sector limits. Formal execution fails before loading
  current classifications while the data gate is blocked. Historical data
  remains `NOT_READY`, no champion was selected, and production thresholds,
  eligibility, entry/stop/exit rules, heat, and market regime are unchanged.
- Forward-test hardening on 2026-09-16 keeps the six-date, 313-row history as
  `ENGINEERING_PILOT_NOT_FORMAL`. Future schema-v2 snapshots include verifiable
  payload hashes, provider version, explicit earnings/market-cap enforcement
  state, ranking rules, and a strategy-cohort ID. The research runner now audits
  frozen cohort fields, fails closed on hash corruption, treats missing/Unknown
  sector as ineligible for a no-Utilities rule, separates raw rows from
  non-overlapping ticker episodes and production-accepted candidates, applies
  shared portfolio heat/capacity/order rules to declared variants, reports
  ticker-cluster intervals, and writes immutable per-run outputs plus an
  append-only manifest. The hardened audit found 102 unique tickers, 40
  triggered plans, 27 non-overlapping episodes, and only six mature independent
  episodes; the sole production-accepted candidate did not trigger. The formal
  champion/challenger epoch remains
  `DRAFT_BLOCKED`: its fixed commit/config/universe/provider fields and an actual
  challenger must be preregistered, and any manual earnings policy requires an
  append-only review/exclusion journal. Production strategy thresholds are
  unchanged.
  A second independent review found six remaining fail-open paths; they are now
  closed in code and regression coverage. Frozen execution settings are
  validated and passed to the simulator. Formal snapshots require all payload
  hashes plus an internally reproducible cohort ID and exact ranking rules.
  Earnings exclusions are applied before all evidence accounting, and review
  timestamps must predate the signal snapshot. Candidate and SPY inputs are
  hashed, diagnosed, and required to contain valid signal-date bars. Every
  champion and challenger must independently reach the mature accepted-episode
  floor, and boolean eligibility parses strings strictly. The formal template
  remains `DRAFT_BLOCKED`; these controls do not start an epoch.
  A subsequent review found duplicate variant IDs, optional/invalid portfolio
  ordering, and permissive policy/numeric parsing. Formal configs now require
  case-insensitively unique variant IDs, a non-empty validated ordering for
  every variant, existing ordering/risk columns, an exact supported earnings
  policy, and finite positive portfolio limits. Invalid ordering directions,
  missing ordering columns, blank earnings evidence fields, and non-finite
  slippage fail closed. `DRAFT_BLOCKED` remains unchanged.
  The final visible P2 is also closed: `unresolved_policy` is now a required
  simulator argument backed by the execution engine's canonical constant.
  Formal `plan_execution` rejects unimplemented extra fields, and run metadata
  records only the normalized contract actually passed to the simulator rather
  than echoing an unchecked raw config.
  The latest counterexamples are also fail-closed: the formal mature-episode
  sample floor is an immutable minimum of 100, session and portfolio position
  counts (including a declared industry cap) must be exact positive integers
  rather than values truncated by `int()`, and every earnings exclusion must
  match exactly one frozen signal-date/ticker candidate.
- `FILTER_EDGE_SEQUENCED_V1` separated filter quality from fixed-2R portfolio
  scarcity. Development contained 25,413 executable signals and 14,083
  non-overlapping ticker episodes before cross-stock constraints, versus only
  124 trades in the earlier fixed-2R path. No one of 80 variants achieved alpha
  support. Strong industry and pivot/supply received risk/quality support, and
  five combinations passed leave-one-out, but none had matching prior portfolio
  support. A two-position industry cap was exactly redundant at 1R/trade under
  2R heat; at 0.5R/trade it bound only three times in development, did not
  reduce drawdown, and had no 2024/2025 effect. Historical decision: `REJECT`;
  production is unchanged. The corrected clean run was `c8f1692`.
- `FILTER_COMBINATION_AUDIT_V1` froze 80 variants: every subset of six core
  filter components plus 16 supplemental individual filters. The baseline had
  25,413 executable development candidates but admitted only 124; 25,200 were
  rejected for fixed-2R maximum heat. Seven combinations passed all absolute
  stage gates, but none passed the relative-performance, largest-winner, and
  leave-one-out shortlist rules. The full six-filter funnel retained only
  7 / 0 / 0 signals across development / reused 2024 / reused 2025. Historical
  decision: `REJECT`; production is unchanged. The successful clean run at
  `9fce57e` produced 240 result rows, 8,079 ledger rows, and 166,543 equity rows
  with zero audit violation.
- `YOUNG_LEADER_ADDITIVE_V1` followed the only mixed V1 lead without retuning
  its signal. Young-first priority improved development to 58.70% return / 8.92%
  drawdown and reused 2024 to 12.30% / 3.92%, but reused 2025 returned 27.00%
  with 13.07% drawdown and 74.39% of positive P&L from one winner. Default and
  MODEL_0-first ordering did not support the direction. Only three newly
  accepted development trades were young; most uplift came from downstream
  capacity reshuffling into mature winners. Historical decision: `REJECT`.
  The clean run at `065dcfe` reconciled 15 results, 655 ledger rows, and 10,981
  equity rows with zero audit violation. Post-result focused verification passed
  114 research tests; full verification passed 303 pytest and 118 legacy tests
  plus all isolation/invariant stages. Production remains unchanged.
- `SUPERPERFORMANCE_PATHS_V1` froze 18 causal mechanical breakout, blue-sky,
  quality, tight-base, pullback, short-history leader, RS/ranking, union, and
  trailing variants. No variant entered the cross-stage shortlist; historical
  decision: `REJECT`. The observed-2R resistance proxy selected only 7/1/5
  signals, while the blue-sky exception restored opportunity without stable
  edge. The short-history leader path was positive with low drawdown in all
  three reused periods, but accepted only 48/8/7 trades and depended on SNDK for
  77.25% of reused-2025 positive P&L. It remains `RESEARCH_ONLY` for one narrow
  additive-sleeve follow-up, not production. The clean run at `fddb565` audited
  54 result rows, 1,984 ledger rows, and 38,141 equity rows with zero boundary,
  blackout, risk, heat, position, or missing-mark violations.
- Research update on 2026-09-13: `FILTER_AUDIT_V1` and
  `FORWARD_FILTER_AUDIT_V1` are implemented as production-isolated workflows.
  A Yahoo current-universe engineering archive contains 4,126,702 stock bars
  plus 2,688 SPY bars from 2016-01-04 through 2026-09-11. The preregistered
  2017-2023 discovery produced 30,129 MODEL_0 signals; results remain explicitly
  survivorship-biased and the 2024-2025 period was not evaluated as a holdout.
  A later boundary audit found that late-2023 signals used early-2024 outcome
  prices, so early 2024 is contaminated for that experiment version. The forward
  journal froze 208 candidates across four immutable signal dates; zero had a
  mature five-session raw outcome at the data cutoff. Its conservative
  plan-trigger simulator found 40 triggered shadow candidate plans: 33 remain
  open/unmatured and seven stopped out. None was an actionable FULL/HALF trade;
  the sole actionable HALF row did not trigger. This is far below the
  100-mature-plan review floor and is not an expectancy conclusion. No
  production filter changed. `EXIT_STOP_GRID_V1` also tested 20 fixed
  target/initial-stop combinations on the same biased 2017–2023 discovery
  sample. None beat the no-target/20-day-low baseline or met the preregistered
  shortlist gate. `PORTFOLIO_EXPOSURE_V1` corrected that boundary by ending
  signals on 2023-11-01 and all outcomes in 2023. Its existing four-position
  baseline had 20.31% daily mark-to-market maximum drawdown; fixed 2R heat cut
  this to 6.97% while retaining 72.96% total return, but accepted only 123 trades
  and missed the preregistered 150-trade floor. Drawdown-stop variants accepted
  only 26–52 trades and then spent 1,331–1,482 sessions blocking new risk. No
  variant passed the complete gate, 2024–2025 remains untouched for this new
  experiment, and production did not change.
  `COMBINED_EXIT_EXPOSURE_GRID_V1` subsequently crossed all 20 exit/stop
  definitions with all nine exposure overlays after preregistration commit
  `04365b7`. One of 180 cells passed the complete discovery gate: 20-day-low
  stop, 2R target, and the earned-2R plus 2R/4R/6R drawdown overlay produced 170
  trades, 0.194R expectancy, 1.573 profit factor, 33.02% return, and 4.65% daily
  MTM maximum drawdown. It was an isolated, complex optimum: the same policy at
  2.5R/3R targets accepted only 31/43 trades and made no later-period gain. The
  decision remains HOLD; no new forward test or production change was made.
- `MARKET_TRAILING_EXIT_CROSS_V1` crossed four signal-date SPY entry/heat
  policies with seven causal 2R/3R-activated SMA20/ATR20 profit-protection exits.
  Seven of 28 cells passed all three reused numeric stage gates. Only SPY above
  SMA50 plus a 2R-activated SMA20-minus-1ATR20 ratchet improved its matching
  no-trailing return in all three periods: 65.63% return / 7.54% drawdown in
  reused 2017–2023, 11.41% / 4.54% in reused 2024, and 8.81% / 3.98% in reused
  2025. It did not beat the unrestricted 2025 baseline's 28.01% return because
  the market gate excluded the 23.51R RGLD outlier path. The exact SMA20 neighbor
  was unstable, and reused 2024 depended heavily on one 10.22R winner. Decision:
  HOLD; no production or immutable-forward-journal change.
- `LEADER_RS_ROBUSTNESS_V1` tested 17 preregistered MarketSmith-style RS,
  RS-line, current-industry, up/down-volume, technical-profile, Utilities, and
  beta variants after the mandatory earnings blackout. No variant passed every
  frozen stage gate. RS proxy >=80 was the sole mixed-support result: it beat
  baseline return and return/drawdown in reused 2024 and 2025, but development
  return fell from 42.78% to 18.77%, development drawdown rose from 9.75% to
  16.87%, and the 2025 result remained outlier-dependent. The combined profile
  was too sparse; beta >=0.8 weakened it in every period. Fundamental
  acceleration remains `BLOCKED_DATA_NOT_READY`. Decision: HOLD; production
  and the immutable forward journal are unchanged.
- `LEADER_COMPLETENESS_V2` completed the missing causal RS, industry-policy,
  base/pivot, and delayed follow-through features before evaluating 24 frozen
  variants. No variant improved both return and return/drawdown versus baseline
  in two periods; shortlist and mixed-support counts were zero. Pivot supply
  clear passed all absolute stage gates but underperformed baseline
  return/drawdown in every period. Contraction plus dry-up made an isolated
  66.94% in reused 2025 after 51.71% development drawdown. The complete leader
  conjunction selected zero eligible signals. Decision: REJECT; fundamentals
  remain `BLOCKED_DATA_NOT_READY`, and production is unchanged.
- Branch at workflow migration: `main` at
  `8d1b00dff6983cd2ba6a32e6b5493f4bc54a09da`. The working tree already
  contained preserved, uncommitted `PORTFOLIO_RANKING_PHASE_A_V1` source,
  tests, configuration, and documentation before the workflow files were
  changed. The five-commit `fix/production-risk-boundaries` series was merged
  through `432be57`.
- Agent workflow: migrated from the earlier research-only v1.1.0 integration to
  a project-adapted `Waynexchan/ai-agent-workflow-template` v1.8.1 baseline at
  commit `a4d2c6aec4a26c3e2d76b391f687266eb1c898d1`. The repository now includes
  context recovery, project health, spec-driven/test-first development,
  dependency-security review, FAST/FULL quality gates, incident recovery, task
  handoff, independent review, release checks, and explicit Git approval
  boundaries. Stock-screener production controls and the stricter local
  discovery + separate validation + untouched holdout research lifecycle remain
  authoritative intentional divergences. No strategy or production behaviour
  changed in this workflow migration.
- Remote confirmed: `https://github.com/Waynexchan/stock_screener.git`; it was not changed.
- Research-task starting commit: `ff44477d4918852ed81becc84890ce9add8b634c`.
- Worktree: intentionally dirty during this migration because the preserved
  Phase A work and the workflow upgrade are both uncommitted. No existing change
  was reset, restored, staged, committed, or pushed by the workflow migration.
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

Post-review-governance-fix verification on 2026-09-24: PASS — the canonical
FULL gate passed 386 pytest tests, 118 legacy unittest tests, Python syntax,
Ruff format/lint, mypy, industry and report invariants, the offline sample dry
run, and generated HTML semantic validation. The exact final run timestamp is
preserved in `logs/verify_project.log`. This evidence covers the workflow
governance fixes and current preserved Phase A working tree; it grants no Git,
release, production, or research-promotion authority.

Workflow-migration verification on 2026-09-23: PASS — the canonical FULL gate
completed against the dirty working tree at `main` /
`8d1b00dff6983cd2ba6a32e6b5493f4bc54a09da`. It passed 386 pytest tests, 118
legacy unittest tests, Python syntax, Ruff format/lint, mypy, industry and report
invariants, the offline sample dry run, and generated HTML semantic validation.
The result is recorded in `logs/verify_project.log` at
`2026-09-23T23:49:53.8416929+01:00`; it validates that exact then-current working
tree but does not authorize commit, merge, push, release, or production use.

Post-forward-hardening verification on 2026-09-16: PASS — focused research
verification passed Ruff, mypy, 133 research tests, the expected
`BLOCKED_DATA_NOT_READY` baseline gate, and production hash isolation. Full
project verification passed 322 pytest and 118 legacy tests plus every syntax,
formatting, typing, industry/report invariant, offline dry-run, and generated
HTML semantic-validation stage.

Post-sequenced-filter-audit verification on 2026-09-15: PASS — focused
research verification passed Ruff, mypy, 128 research tests, the expected
`BLOCKED_DATA_NOT_READY` baseline gate, and production hash isolation. Full
project verification passed with 317 pytest tests, 118 legacy unittest tests,
all formatting, typing, industry/report invariant, offline dry-run, and
generated HTML semantic-validation stages.

Post-filter-combination-audit result verification on 2026-09-15: PASS — focused
research verification passed Ruff, mypy, 120 research tests, the expected
`BLOCKED_DATA_NOT_READY` baseline gate, and production hash isolation. Full
project verification passed with 309 pytest tests, 118 legacy unittest tests,
all formatting, typing, industry/report invariant, offline dry-run, and
generated HTML semantic-validation stages.

Post-completed-leader-V2 result verification on 2026-09-14: PASS — focused
research verification passed Ruff, mypy, 103 research tests, the expected
`BLOCKED_DATA_NOT_READY` baseline gate, and production hash isolation. Full
project verification passed with 292 pytest tests, 118 legacy unittest tests,
all formatting, typing, industry/report invariant, offline dry-run, and
generated HTML semantic-validation stages.

Post-market/trailing-cross implementation on 2026-09-14: PASS — Ruff, mypy,
90 research tests, the expected `BLOCKED_DATA_NOT_READY` baseline gate, and
production hash isolation passed. Full project verification passed with 279
pytest tests, 118 legacy unittest tests, all formatting, typing, industry/report
invariant, offline dry-run, and generated HTML semantic-validation stages.

Post-combined-grid implementation on 2026-09-13: PASS — Ruff, mypy, 58
research tests, the expected `BLOCKED_DATA_NOT_READY` baseline gate, and
production hash isolation passed. Full project verification passed with 247
pytest tests, 118 legacy unittest tests, all formatting, typing, industry/report
invariant, offline dry-run, and generated HTML semantic-validation stages.

Post-portfolio-exposure implementation on 2026-09-13: PASS — Ruff, mypy, 54
research tests, the expected `BLOCKED_DATA_NOT_READY` baseline gate, and
production hash isolation passed. Full project verification passed with 243
pytest tests, 118 legacy unittest tests, all formatting, typing, industry/report
invariant, offline dry-run, and generated HTML semantic-validation stages.

Post-exit/stop-grid implementation on 2026-09-13: PASS — Ruff, mypy, and 47
research tests passed; the default MODEL_0 data gate remained the
expected `BLOCKED_DATA_NOT_READY`, and production hash isolation passed. Full
project verification passed with 236 pytest tests, 118 legacy unittest tests,
all formatting, typing, industry/report invariant, offline dry-run, and
generated HTML semantic-validation stages.

Post-independent-review follow-up on 2026-09-12: PASS — the skill and templates
now enforce `discovery -> validation -> untouched holdout`, preserve explicit
validation/holdout sample status and results, and record verifiable upstream
provenance. Full verification passed with 216 pytest tests and 118 legacy
unittest tests plus all formatting, typing, integration, invariant, dry-run, and
semantic-validation stages. Focused research verification passed 28 tests, the
expected `BLOCKED_DATA_NOT_READY` gate, and production-file hash isolation.

Post-`research-experiment` integration full verification on 2026-09-12: PASS —
Python syntax, Ruff format and lint, mypy, 216 pytest tests, 118 legacy unittest
tests, industry/report invariants, the offline sample Daily Watchlist dry run,
and generated HTML semantic validation all passed.

Post-integration research verification on 2026-09-12: PASS — Ruff, mypy, 28
research tests, the expected `BLOCKED_DATA_NOT_READY` MODEL_0 gate, and
production-file hash isolation all passed.

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

Local validation-data audit result: **NOT_READY**. A Yahoo current-universe
engineering OHLCV/benchmark archive now exists, but there is no historical
universe membership, delisted coverage, effective-dated classifications, or
market-cap history. The current-symbol archive remains labelled
**SURVIVORSHIP-BIASED RESEARCH** and does not satisfy the validation gate. See
`docs/DATA_READINESS.md`.

The frozen `EASY_EXECUTION_CROSS_VALIDATION_V1` study completed all 168
discovery cells. One simple candidate—20-day-low stop, no target with a
40-session exit, and fixed 2R heat—passed discovery and the separate 2024
validation, then failed the conditional one-time 2025 holdout because maximum
daily mark-to-market drawdown reached 13.29% versus the frozen 10% ceiling.
The result remains `RESEARCH_ONLY` and `HOLD`; production and the existing
forward journal are unchanged. See
`docs/RESEARCH_RESULTS_EASY_EXECUTION_CROSS_VALIDATION_V1.md`.

The adaptive `EARNINGS_EXPOSURE_ROBUSTNESS_V1` study implemented the clarified
two-state exposure rule: start at two 1R positions, allow a third after a
net-profitable realised exit batch, and restore the two-position limit after a
zero/negative batch. The combined dynamic-plus-ten-calendar-day earnings
blackout failed reused 2017–2023 robustness at 13.38% maximum drawdown, although
it passed the reused post-2023 numeric gate at 9.75%. Fixed 2R plus the blackout
stayed below 10% in both reused periods but its direction and opportunity cost
were unstable. The Yahoo event dates are retrospective rather than point-in-time
schedule snapshots, so the decision remains `HOLD` and production is unchanged.
See `docs/RESEARCH_RESULTS_EARNINGS_EXPOSURE_ROBUSTNESS_V1.md`.

The corrected `STAIRCASE_EXPOSURE_ROBUSTNESS_V2` study removed the mistaken
three-position interpretation: it started at 2R, added one position slot after
each positive realised exit batch, and tested STEP or RESET contraction under
4R, 6R, and 8R hard ceilings. No dynamic variant passed both reused periods.
All reached 15.58%–16.59% maximum drawdown in reused 2017–2023 versus the 10%
gate. Fixed 2R was the only numeric two-period gate pass, at 9.75% and 4.84%
drawdown, but is not independently validated. Decision remains `HOLD`; no
production or immutable-forward-journal change. See
`docs/RESEARCH_RESULTS_STAIRCASE_EXPOSURE_ROBUSTNESS_V2.md`.

`EARNINGS_BLACKOUT_FULL_RETEST_V1` now recalculates all 385 earlier settings
that lacked the user's mandatory zero-to-ten-calendar-day pre-earnings entry
blackout. The rule is applied before filters, execution, candidate order, and
portfolio allocation. No 180-cell combination passed. Two of the 168 simple
cells passed development and reused 2024—20-day-low stop, fixed 2R, and either
30- or 40-session no-target exits—but both exceeded 12.8% drawdown in reused
2025. The previous Utilities-exclusion benefit reversed and the low-beta
exclusion remained worse than baseline. Decision remains `HOLD`; all post-2023
evidence is reused/contaminated and production is unchanged. See
`docs/RESEARCH_RESULTS_EARNINGS_BLACKOUT_FULL_RETEST_V1.md`.

`LEADER_RS_ROBUSTNESS_V1` tested 17 frozen leader-selection variants across
boundary-purged 2017-2023 and reused 2024/2025. No variant reached the
cross-stage shortlist. A MarketSmith-style proxy >=80 showed mixed later-period
support but failed development and outlier controls; higher cutoffs were
non-monotonic. RS-line, current-industry, and up/down-volume confirmations were
unstable. The combined technical profile surrendered most baseline return, its
no-Utilities interaction was too sparse, and beta >=0.8 failed every stage
gate. The proxy is not MarketSmith's proprietary score, classifications are
current, and there is no untouched holdout. See
`docs/RESEARCH_RESULTS_LEADER_RS_ROBUSTNESS_V1.md`.

`LEADER_COMPLETENESS_V2` added 21-/63-session RS changes, exact RS-line lead,
stock-within-industry rank, breadth acceleration, five industry policy roles,
mechanical base/pivot quality, and a causal delayed follow-through entry. The
24-variant run produced no shortlist or mixed-support result. Pivot-supply-clear
was positive and below 10% drawdown in all three reused periods, but had lower
return and return/drawdown than baseline every time. Other promising-looking
single periods reversed elsewhere; the completed composite was unusably sparse.
Decision: REJECT. See
`docs/RESEARCH_RESULTS_LEADER_COMPLETENESS_V2.md`.

`FILTER_COMBINATION_AUDIT_V1` tested the complete 64-subset cross of six
mechanism filters plus 16 supplemental single filters. The scarcity funnel
showed that fixed 2R heat, not raw signal availability, is the binding
transaction constraint: only about 0.3%–0.5% of executable candidates entered.
No combination met the preregistered relative, outlier, and leave-one-out
shortlist. Decision: REJECT the exact hard-filter matrix. See
`docs/RESEARCH_RESULTS_FILTER_COMBINATION_AUDIT_V1.md`.

`FILTER_EDGE_SEQUENCED_V1` then removed cross-stock capacity while assessing
each frozen filter and combination, retaining only one open episode per ticker.
The baseline contained 14,083 / 2,101 / 2,295 opportunity episodes across the
three reused stages. No variant met the alpha gate; strong industry and
pivot/supply were the only individual risk/quality supports. Five bounded
combinations passed leave-one-out but none agreed with the earlier fixed-2R
portfolio shortlist. The separate industry-cap audit showed that cap two is
redundant when 2R heat already allows only two 1R positions. At 0.5R/trade it
did not improve drawdown and had no reused-2024/2025 effect. Decision: REJECT.
See `docs/RESEARCH_RESULTS_FILTER_EDGE_SEQUENCED_V1.md`.

## Next recommended task

Complete the remaining formal Phase A infrastructure and data-readiness work;
do not recreate the ranking interface that is already implemented. Acquire and
provenance-check point-in-time universe/listing history, delisted symbols,
effective-dated classifications, earnings schedules, and required fundamental
history, then verify the pre-allocation candidate journal and formal data gate.
Only after those inputs are `READY` may the already frozen one-factor,
deterministic-random, composite, and leave-one-out arms run on their declared
future development/validation windows. Production capacity ordering is Final
Score descending, then normalized ticker ascending; input row order is not a
tie-break. Do not retune filters or ranking weights on reused 2017-2025 history.

Do not retune the completed V1 paths or promote any result without explicit
instruction and governance review.
