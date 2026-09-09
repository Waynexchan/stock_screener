# AI Development Workflow

Read `AGENTS.md`, then `docs/PROJECT_STATUS.md`, before using this lifecycle:

```text
UNDERSTAND -> BASELINE -> REPRODUCE -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> DOCUMENT -> CHECKPOINT
```

## Lifecycle

### UNDERSTAND

Confirm the requested outcome, scope, production/research boundary, canonical entry points, schemas, and existing user changes. Identify what must not change.

### BASELINE

Record branch, commit, remote, and dirty state. Run the smallest relevant existing tests before editing; for broad or production-sensitive work, run the full verifier.

### REPRODUCE

For a bug, create the smallest deterministic reproduction and trace the authoritative inputs and outputs. For a research question, freeze the hypothesis, baseline, sample rules, and metrics before viewing results.

### PLAN

Choose a minimal coherent change. Name affected production and research surfaces, tests, documentation, data assumptions, and rollback boundary. Do not add a second decision path.

### IMPLEMENT

Fix source logic, not generated reports. Keep missing data explicit, protect point-in-time boundaries, and prevent research fields from gating production.

### TEST

Run the focused test after each fix, then affected suites. A production change requires regression coverage and the complete `scripts/verify_project.ps1` workflow.

### REVIEW

Inspect the diff and test behavior, not only exit codes. For semantic changes, compare the canonical record through CSV, HTML, and email. Check duplicates, decisions, confirmation, R/R, risk, shares, freshness, heat, counts, and warnings.

### DOCUMENT

Update user-facing docs for behavior changes, project memory/status for durable decisions or limitations, and the filter registry for research status. Never record invented evidence.

### CHECKPOINT

Verify again, stage only intended files, create a meaningful local commit when requested, record its hash, and report whether it was pushed. Never mix unrelated user work into the checkpoint.

## Task categories

### BUG FIX

Reproduce, diagnose root cause, add a regression test where practical, fix without changing unrelated strategy semantics, and run affected plus full required verification.

### STRATEGY RESEARCH

Register the hypothesis, keep it `RESEARCH_ONLY`, use the framework in `docs/RESEARCH_GOVERNANCE.md`, and write outputs outside production reports. Do not change production behavior unless the user explicitly requests a separate production change after reviewing results.

### PRODUCTION CHANGE

Requires explicit approval of the intended behavior, focused regression tests, invariant review, full verification, and documentation. A plausible hypothesis is not approval.

### DATA PIPELINE CHANGE

Define source/as-of semantics, missing/stale behavior, point-in-time limits, cache effects, fallback behavior, and data-quality tests. Never let missing data look valid.

### REPORT CHANGE

Preserve the canonical manifest across CSV, HTML, Markdown, and email. Test semantics and render/output validity; do not patch only a generated artifact.

### AUTOMATION CHANGE

Preserve the verified production wrapper, repository-root working directory, logs, non-zero failure behavior, and the rule that verification failure blocks normal reporting/email. Do not modify the Windows task without explicit authority.

### REFACTOR

Freeze behavior with tests, retain one canonical decision path, make small reviewable moves, and prove output invariants are unchanged.

## Failure protocol

When verification fails:

1. Find the first meaningful failure.
2. Separate root cause from cascade.
3. Reproduce with the smallest relevant test.
4. Inspect inputs, intermediate canonical records, and outputs.
5. Fix implementation; do not weaken the assertion or change a threshold to hide the problem.
6. Rerun the focused test.
7. Rerun affected suites.
8. Run full verification before completion.

For semantic contradictions, trace:

```text
canonical internal record -> CSV -> HTML -> email
```

Stop normal production generation while a required verification stage is failing.
