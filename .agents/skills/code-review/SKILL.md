---
name: code-review
description: Independently review a proposed or current change for correctness, safety, regressions, and test adequacy without modifying it by default. Use for review-only requests and pre-merge technical assessment.
---

# Code review

Review evidence, not intentions alone. This skill is read-only by default: do not edit files unless the user explicitly asks for fixes. Repository instructions define the authoritative review constraints.

## 1. Establish the review scope

Determine whether this is a general or current-state review, or an explicit pre-merge review. For a change review, determine the intended change, repository, base branch, review branch or current branch, and exact diff. Note uncertainty when the intended base or scope cannot be established. Inspect changed files in their surrounding code and architecture, not only isolated diff lines.

Read the governing specification, acceptance criteria, proposed or implemented test scenarios, relevant tests, configuration, schemas, migrations, durable project context, and safety rules. Establish which behaviours are already protected by deterministic regression checks and which risks remain judgment-dependent. Run safe checks when useful, but do not treat passing tests as proof that the specification or tests are complete or correct.

## 2. Evaluate the change

Look for actionable defects involving:

- correctness, edge cases, regressions, and error handling;
- data integrity, security, secrets, and production safety;
- concurrency or race conditions where relevant;
- architecture consistency and API, schema, or compatibility breaks;
- requirement interpretation, specification correctness, business/domain rules, and important invariants;
- acceptance-criterion-to-test traceability, missing boundaries or failure modes, outcome-focused assertions, and the risk that tests mirror the same mistake as the implementation;
- point-in-time or research leakage, compliance constraints, operational failure modes, and unsafe assumptions where applicable;
- test adequacy and documentation or durable-knowledge drift; and
- unintended generated files, runtime data, or unrelated scope.

Distinguish blocking defects from optional improvements. Do not invent findings, convert style preferences into defects, or demand tooling the project does not use.

Focus review effort on the new or changed specification, tests, code, affected interfaces, integration risk, and risks that automation does not fully protect. Use passing deterministic regression checks as evidence for stable unchanged behaviour instead of manually re-deriving it, while still inspecting unchanged code when the change creates a meaningful interaction risk.

## 3. Report findings

Order findings by severity and include the affected file and location where possible, why the issue matters, the supporting evidence or reasoning, and a remediation direction.

- **P0 — Critical:** immediate severe impact, such as exploitable compromise, irreversible data loss, or a fundamentally unusable change.
- **P1 — High:** likely serious correctness, security, compatibility, or operational failure that should block progression.
- **P2 — Medium:** real defect or meaningful risk that should normally be fixed before release.
- **P3 — Low:** limited-impact defect or maintainability risk worth addressing but not normally blocking.

If there are no actionable findings, say **No findings**. Summarize any verification limitations separately from defects.

Finish with exactly one technical conclusion. For a general or current-state review, use:

```text
REVIEW: PASS
```

or

```text
REVIEW: FAIL
```

Use `REVIEW: FAIL` when a P0, P1, or P2 finding or another unmet review objective makes the reviewed state technically unacceptable; P3-only observations may accompany `REVIEW: PASS`.

Only for an explicit pre-merge review, use `MERGE: YES` or `MERGE: NO` instead. Provide a concise justification. Both verdict families express technical review only: they are not an operational-readiness conclusion and do not authorize a commit, merge, push, release, or deployment. Use `release-check` when readiness for a named repository or release boundary is the requested question.
