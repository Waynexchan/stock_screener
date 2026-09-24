---
name: project-dev-cycle
description: Carry out spec-driven, test-first repository implementation from safe Git preflight through focused changes, project-defined regression verification, independent review, and separately approved commit, merge, push, and branch cleanup boundaries. Do not use for read-only questions, code-review-only requests, Git-only operations, or production execution; scale down for trivial documentation-only edits.
---

# Project development cycle

Use this workflow for features, bug fixes, refactors, and other implementation tasks. Repository instructions and project-defined commands take precedence over this generic skill.

## Route the request

- For a read-only question, inspect and answer without creating a branch or changing files.
- For code review, report findings independently; do not implement fixes unless asked.
- For a Git-only operation, perform only the requested Git work and retain all applicable safety and approval boundaries.
- For production or operational execution, follow the project's runbooks and authorization requirements instead of treating it as software implementation.
- For a truly trivial documentation-only change, use a proportionate version of this cycle. A short plan, documentation checks, and diff review may replace full implementation ceremony when project rules allow, but all Git mutation approvals remain separate.

## 1. Preflight and branch

1. Read applicable `AGENTS.md` files and the repository's relevant status, decisions, architecture, and task context. Reconcile documentation with Git and current files.
2. Inspect the working tree, current branch, HEAD, recent history, remotes when relevant, and existing branches.
3. When a remote-backed decision depends on remote state, refresh the affected remote-tracking refs with a non-destructive fetch before creating a branch, judging divergence, merging, or pushing. If the fetch cannot be completed, label remote freshness unverified and do not claim that a tracking ref is current or synchronized.
4. Identify dirty files before editing. Preserve unrelated user work; do not reset, restore, clean, overwrite, stage, or commit it. Stop for user direction if safe isolation is not possible.
5. For meaningful work, begin from a clean default branch and create a focused development branch, or reuse an existing branch that clearly belongs to the task. Follow repository branch naming. Do not switch branches when doing so would endanger local changes.
6. Recover the requested outcome, business/domain context, constraints, affected surfaces, and current behavioural contract from repository artifacts. After context compression, restart, handoff, or a long interruption, repeat this recovery rather than trusting conversational memory. If a material assumption is undocumented and cannot be established safely, stop and ask instead of guessing.

## 2. Specify and design the tests

Before production implementation for a meaningful behavioural change:

1. Write or update the authoritative specification. State the purpose or business intent, observable behaviour, inputs and outputs, valid and invalid cases, boundaries, missing-data and error behaviour, important invariants, domain constraints, compatibility and point-in-time expectations where relevant, and explicit non-goals. Specify what must be true; prescribe implementation only when the constraint is itself required.
2. Define explicit, verifiable acceptance criteria.
3. Derive risk-based test scenarios from the specification. Cover every acceptance criterion where practical, plus material boundaries, invalid or missing values, failure modes, invariants, state transitions, historical defects, and business, financial, ranking, filtering, or point-in-time semantics that could regress. Prefer observable outcomes over implementation details; do not add tests merely to increase counts or coverage.
4. Review the specification and scenarios before production code. Check requirement-to-test coverage, boundary and failure cases, business-rule accuracy, shared mistakes that could make code and tests agree incorrectly, interaction with existing behaviour, and obvious omissions. Present this checkpoint to a human before implementation when the change is complex, business-critical, or otherwise high impact.
5. Implement or update the tests before production code when the repository supports practical automation. A bug fix should first reproduce the defect with a focused regression test when the repository supports it. Do not weaken or delete a valid test merely because intended behaviour changed; first establish whether the specification, test, or implementation is wrong, then update the specification and rationale for intentional changes.

An existing authoritative specification may be reused when it fully covers the request. Trivial or clearly non-behavioural work may skip this ceremony. When an important behaviour cannot reasonably be automated, plan and later record the reason, manual validation, supporting evidence, residual risk, and automation recommendation.

Create a concise implementation plan. Discover the repository's canonical local validation command and underlying build, test, lint, type-check, schema, data-quality, and documentation checks from instructions and configuration; never assume a language or toolchain or fabricate a command. Reuse an existing aggregate command. If none is practical, record the project-required commands and the limitation.

Run a relevant baseline check when it helps distinguish pre-existing failures from regressions. If the baseline is unavailable, too costly, or already known to fail, record that fact and continue only when the remaining verification can still support a responsible change.

## 3. Implement and verify

After the specification and test-design checkpoint, make the smallest coherent production change that satisfies the contract. Prefer deterministic, testable boundaries for important logic over unnecessary dependence on networks, mutable global state, uncontrolled systems, or timing, without over-engineering solely for tests. Follow existing design and conventions, keep generated/runtime data out of source control, and do not add unrelated cleanup.

Validate in this order where practical:

1. narrow tests for the changed behaviour;
2. affected module or package regression tests; and
3. the canonical repository validation command, or all project-required gates when no aggregate command exists.

Investigate failures, fix the underlying issue, and rerun the affected and appropriate regression checks before review. Do not begin normal independent review while required automated checks are failing; use review earlier only when its stated purpose is to diagnose those failures.

Before review:

1. Confirm implementation and tests trace to the specification and acceptance criteria.
2. Run all verification gates the project defines as required for the affected change.
3. Inspect the complete working-tree diff and status, including untracked files.
4. Check for accidental changes, secrets, credentials, debug artifacts, runtime output, and unrelated files.
5. Write normative business rules, clarified behavioural semantics, assumptions that affect behaviour, important exceptions, invariants, failure behaviour, and test expectations to the authoritative specification and tests. Record important choices and rationale in the decision log. Store only stable, non-normative domain or operational context and pointers to those authoritative records in project memory. Do not duplicate a normative rule across artifacts or store transient session notes.
6. Record commands run, results, and any limitations, manual checks, or skipped automation.

## 4. Independent review and fix loop

Hand the completed diff, governing specification, acceptance criteria, test scenarios, and verification evidence to a reviewer that did not implement the change when an independent reviewer is available. Ask the reviewer to focus on requirement interpretation, specification correctness, test adequacy and missing scenarios, changed code, affected interfaces, integration and compatibility risk, unsafe assumptions, architecture, data integrity, security, compliance, business/domain correctness, point-in-time or research leakage, operational failure modes, unintended effects, maintainability, and violations of repository instructions.

Deterministic passing checks protect known behaviour but do not prove that the requirements or tests are complete. Reviewers should not mechanically re-perform strongly covered stable behaviour or re-review the whole repository; they should inspect unchanged areas when the change creates meaningful interaction risk.

The implementer may address review findings. After fixes, rerun affected targeted checks and every project-required gate invalidated by the changes, then reinspect the diff. Blocking findings should return to independent review for confirmation when practical. Continue until no P0/P1 finding remains, or stop and disclose an unresolved blocker.

Meaningful behavioural work is normally complete only when context was recovered; the specification, acceptance criteria, and reviewed tests cover the change; targeted, affected regression, and canonical repository validation pass where available; independent review is complete; findings are resolved or explicitly accepted; and durable knowledge and important decisions are recorded. Approval boundaries below still apply.

## 5. Commit only with approval

Present the final scope, review outcome, verification evidence, and intended commit contents. Obtain explicit user approval immediately before committing; earlier approval to implement is not commit approval, and commit approval authorizes only the commit.

After approval:

1. Confirm the diff has not changed unexpectedly.
2. Stage exact intended paths. Avoid broad staging such as `git add .` when exact-file staging is practical.
3. Inspect staged status and diff, and verify no secret or unrelated file is included.
4. Commit with a focused message. Do not amend or rewrite history unless the user explicitly requests it and the operation is safe.

## 6. Merge, push, and clean up with separate approvals

After a successful approved commit, present the exact source branch, target branch, and intended merge method, then obtain a new explicit user approval immediately before merging. Commit approval never implies merge approval.

After merge approval, refresh relevant remote-tracking refs when remote state affects safety, then recheck repository status immediately before switching branches. Stop if the working tree is not clean; preserve unexpected or unrelated work and do not clean or reset it. Switch to the default branch only from that clean state, confirm the default branch's working tree is also clean, and then merge the completed branch safely. Prefer a fast-forward merge when the repository permits it. If the default branch moved, remote freshness is unverified, conflicts exist, required checks are unclear, or merging would create an unapproved extra commit, stop and choose a safe repository-approved path with the user.

Run a post-merge sanity check appropriate to the change and confirm status and history. Do not push yet.

Describe the exact local ref, remote, and destination ref to be pushed and obtain a separate explicit user approval immediately before pushing. Earlier commit or merge approval never implies push approval. Refresh the affected remote-tracking refs before the decision when possible; if remote freshness cannot be verified, disclose that limitation and do not claim push readiness. Never force-push by default.

After a successful push, retain development branches by default. Before deleting any local or remote branch, name the exact ref, confirm that it is merged, no longer needed, and safe to remove, and obtain explicit user approval for that deletion. Treat each remote branch deletion as a separate remote-state change: commit, merge, push, or local-cleanup approval never implies permission to delete a remote branch. Retain the branch when deletion is not approved, push fails, work remains, merge status is uncertain, or remote freshness is unverified.

## Safety invariants

- Never intentionally commit secrets, credentials, environment files, private keys, local logs, or runtime data.
- Never destroy unrelated user work with reset, restore, checkout, clean, branch deletion, or file overwrites.
- Never claim verification, review, merge, or push occurred without evidence.
- Keep user approval points explicit and non-transferable: commit, merge, push, and branch deletion are distinct actions. Remote branch deletion always requires its own explicit approval.
