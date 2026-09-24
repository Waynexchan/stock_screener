---
name: release-check
description: Assess whether repository and change state are ready to cross a requested commit, merge, push, or release boundary. Use for operational readiness checks; it does not authorize crossing the boundary.
---

# Release check

Determine whether the current repository state is safe to advance across the boundary the user named. This differs from code review: code review evaluates technical soundness, while release check evaluates repository and operational readiness.

## 1. Define the boundary and evidence

State the exact boundary: commit, merge, push, release, or another explicitly requested point. Read repository instructions and use the project's documented commands and configuration; do not assume a language, test framework, CI provider, or release tool.

Confirm, where relevant:

- the repository, current branch, expected base, HEAD, and branch divergence;
- staged, unstaged, and untracked changes, plus the complete intended diff;
- the governing specification, acceptance criteria, intentional behaviour changes, and any required durable knowledge or decision updates;
- evidence that test scenarios were reviewed and trace to the acceptance criteria for meaningful behavioural work;
- targeted tests, affected regression checks, the canonical local validation command where available, and other required lint, formatting, type, schema, data-quality, or invariant checks;
- secrets exposure, security concerns, generated/runtime artifacts, and unrelated files;
- documentation, configuration, schema, and migration consistency;
- available CI status and unresolved review findings; and
- boundary-specific prerequisites such as an approved commit or a clean merge state.

Record unavailable or stale evidence explicitly. Do not claim readiness from assumed or unverified checks.

If important behaviour is not automated, require the documented reason, manual validation evidence, residual risk, and future-automation recommendation before treating the evidence as complete. Passing checks do not compensate for an incorrect or incomplete specification or test plan.

## 2. Classify readiness

A blocker is any unmet repository rule, required failed check, unresolved finding incompatible with the requested boundary, unsafe Git state, or missing evidence essential to responsible progression. Separate blockers from non-blocking observations and residual risks. If any blocker exists, the conclusion must be negative.

Finish with exactly one boundary-specific conclusion in this form:

```text
READY TO <BOUNDARY>
```

or:

```text
NOT READY TO <BOUNDARY>
```

Replace `<BOUNDARY>` with the requested boundary, such as `COMMIT`, `MERGE`, `PUSH`, or `RELEASE`. List exact blocking reasons when not ready, and summarize commands and evidence used in either case.

This check never authorizes or automatically performs a commit, merge, push, tag, deployment, branch deletion, release, or other remote-state change. Perform such actions only when separately and explicitly authorized.
