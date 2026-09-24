# AI-assisted development workflow

This project uses a stock-screener-specific adaptation of
`Waynexchan/ai-agent-workflow-template` v1.8.1. `AGENTS.md`, project
specifications, tests, and the production/research governance documents override
generic skill defaults. The workflow baseline is separate from application and
research versions.

## Skill routing

Use the smallest workflow that fits the request:

- `context-resume` reconstructs a repository-backed Working Context at entry,
  resume, handoff, context loss, or uncertainty about chat freshness.
- `project-health` provides a read-only operational summary and one next safe
  action without rerunning the checks it consumes.
- `project-dev-cycle` governs meaningful implementation from safe preflight
  through specification, tests, verification, review, and approval boundaries.
- `debug` investigates a scoped defect through reproduction, root cause, minimal
  repair, and regression coverage.
- `dependency-security-check` handles dependency and directly related
  repository-security changes.
- `quality-gate` records FAST or FULL deterministic validation evidence.
- `task-handoff` transfers one active task across a meaningful agent/session
  boundary; it never replaces context recovery or current repository checks.
- `code-review` performs independent technical review without edits by default.
- `release-check` assesses readiness for a named commit, merge, push, or release
  boundary but grants no authority to perform it.
- `incident-recovery` is the exception path for credible repository, runtime,
  artifact, data, production-integrity, persisted-state, external-side-effect,
  or unbounded-impact incidents.
- `project-bootstrap` customizes a new template-derived repository.
- `project-migrate` upgrades an existing repository non-destructively.
- `research-experiment` governs systematic investment/trading research and
  composes with the repository workflow when implementation is required.

Read-only questions, review-only work, Git-only operations, production
execution, and truly trivial documentation edits use proportionate handling.
Not every task needs every skill.

## Normal implementation lifecycle

```text
CONTEXT -> BASELINE -> SPECIFY -> REVIEW TEST DESIGN -> TEST
-> IMPLEMENT -> FAST -> FULL -> INDEPENDENT REVIEW
-> FIX/REVERIFY -> DOCUMENT -> EXPLICIT GIT BOUNDARIES
```

### CONTEXT

Read `AGENTS.md`, then reconcile `docs/PROJECT_STATUS.md`,
`docs/PROJECT_MEMORY.md`, relevant specifications, tests, decisions, research
records, incidents, handoffs, and Git state. Repository evidence outranks stale
status notes and conversational memory. State unresolved material ambiguity
instead of guessing.

### BASELINE

Record branch, commit, remotes, dirty state, and relevant remote freshness.
Preserve all user work. The default branch is `main`; new agent-led work normally
uses `codex/<short-task-name>`. Meaningful work should begin from a clean default
branch and focused development branch, or reuse a clearly associated branch. Do
not switch branches if uncommitted work would be endangered. Run the smallest
useful baseline check; for broad or production-sensitive work, use the FULL
verifier.

### SPECIFY

Before meaningful behavioural implementation, create or update the authoritative
contract: purpose, observable inputs/outputs, valid and invalid cases, boundaries,
missing-data and error behaviour, invariants, domain constraints, compatibility,
point-in-time expectations, non-goals, and explicit acceptance criteria.

For systematic research, the frozen hypothesis/experiment record is the domain
specification. Do not create a second contract that can drift.

### REVIEW TEST DESIGN

Derive risk-based scenarios from every acceptance criterion where practical.
Cover boundaries, invalid/missing values, failures, state transitions, historical
defects, deterministic replay, business/financial semantics, ranking/filtering,
point-in-time leakage, and production/research isolation. Review whether code and
tests could share the same mistaken assumption. Expose this checkpoint to the
user before complex or business-critical implementation when needed.

### TEST AND IMPLEMENT

Implement tests first where practical, including a focused failing regression
for a confirmed bug. Then make the smallest coherent source change. Fix source
logic, not generated reports; keep missing data explicit; preserve one canonical
decision path; and never let research or AI commentary alter deterministic
production decisions.

### FAST AND FULL QUALITY GATES

`FAST` is the smallest relevant deterministic test command set plus affected
Ruff/mypy checks where practical. Record exact commands and results. It is
implementation feedback only.

`FULL` is:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_project.ps1
```

FULL must pass before normal independent review and before a meaningful change
is declared complete. Missing, failed, blocked, stale, narrowed, or unexpectedly
skipped required evidence cannot be called PASS. If dependency/security-sensitive
changes triggered `dependency-security-check`, FULL consumes its current result
without duplicating or weakening that review.

### INDEPENDENT REVIEW AND FIX LOOP

Review the governing specification, acceptance criteria, scenarios, complete
diff, tests, affected interfaces, integration/compatibility risk, security,
domain correctness, data integrity, point-in-time boundaries, operational failure
modes, maintainability, and risks not fully covered by automation. Passing tests
do not prove that requirements or tests are complete.

Resolve P0/P1 findings, rerun affected checks and FULL, reinspect the diff, and
return blocking fixes for confirmation when practical. Do not begin ordinary
review while required automated checks are failing unless the review is
explicitly diagnostic.

### DOCUMENT

Write normative behaviour to specifications and tests; important choices and
rationale to a decision record; stable non-normative context and pointers to
project memory; current execution state to project status; and research evidence
to the hypothesis, ledger, forward-test plan, results, and filter registry. Never
record invented evidence or duplicate an authoritative rule across artifacts.

### EXPLICIT GIT BOUNDARIES

Commit, merge, push, release/deploy, local branch deletion, and each remote
branch deletion require distinct explicit approval immediately before the exact
operation. Stage exact files, not broad unrelated work. Approval does not
transfer across boundaries. Retain branches by default and never force-push by
default.

## Task categories

### BUG FIX

Use `debug`: recover the expected contract, reproduce or establish evidence,
add a focused regression where practical, diagnose root cause, fix without
changing unrelated strategy semantics, and run affected plus FULL verification.
A scoped failure remains a bug; broad uncertain integrity or effects enter
`incident-recovery`.

### STRATEGY RESEARCH

Load `.agents/skills/research-experiment/SKILL.md`, register the hypothesis, keep
it `RESEARCH_ONLY`, use `docs/RESEARCH_GOVERNANCE.md`, and write generated
results under ignored `research/output/`. The project deliberately retains the
stricter discovery + separate validation + untouched holdout lifecycle even
though the generic v1.8.1 upstream skill was simplified. Research never promotes
itself into production.

### PRODUCTION CHANGE

Requires explicit intended behaviour, authoritative specification and acceptance
criteria, reviewed risk-based scenarios, regression coverage, invariant review,
FULL verification, independent review, and documentation. A plausible hypothesis
or research result is not production approval.

### DATA PIPELINE CHANGE

Define source/as-of semantics, missing/stale behaviour, point-in-time limits,
cache effects, fallback behaviour, and data-quality tests. Never let missing data
look valid.

### REPORT CHANGE

Preserve the canonical manifest across internal records, CSV, HTML, Markdown,
and email. Test semantics and render/output validity; never patch only a generated
artifact.

### AUTOMATION CHANGE

Preserve `scripts/run_daily_production.ps1`, repository-root execution, logs,
non-zero failure behaviour, and the rule that failed verification blocks normal
reporting/email. Do not modify the Windows Scheduled Task without explicit
authority.

### REFACTOR

Freeze behaviour with tests, retain one canonical decision path, use small
reviewable moves, and prove output invariants are unchanged.

## Incident and handoff boundaries

Use `incident-recovery` only for a credible broader integrity or state risk. It
preserves evidence, bounds impact, coordinates only authorized containment and
recovery, and requires affected-state verification before resumption. It does
not authorize rollback, restore, replay, retry, data correction, cleanup,
release, or deployment.

Use `task-handoff` only when unfinished, blocked, review-ready, reviewed, or
otherwise meaningful work must transfer. The ignored root `/HANDOFF.md` may hold
one transient active handoff. The receiver must run `context-resume` and verify
repository identity, branch, HEAD, working-tree fingerprint, decisions, and
validation freshness. A handoff validates and authorizes nothing.

## Failure protocol

When verification fails:

1. Find the first meaningful failure and separate root cause from cascade.
2. Reproduce it with the smallest relevant test.
3. Inspect inputs, intermediate canonical records, and outputs.
4. Fix the implementation; do not weaken the assertion or change a threshold to
   hide the problem.
5. Rerun the focused test, affected suites, and FULL before completion.

For semantic contradictions, trace:

```text
canonical internal record -> CSV -> HTML -> email
```

Stop normal production generation while a required verification stage is
failing.

## Safety boundaries

The workflow never authorizes force pushes, destructive Git cleanup, history
rewriting, broad staging when exact paths are practical, overwriting unrelated
work, committing secrets/runtime data, silently changing package sources,
deleting lockfiles to avoid conflicts, automatic dependency upgrades, strategy
promotion, production execution, or brokerage actions. Project-health,
dependency-security, quality-gate, review, release-readiness, incident, and
handoff results are evidence, not authority.
