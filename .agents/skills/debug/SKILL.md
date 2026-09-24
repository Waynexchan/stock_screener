---
name: debug
description: Diagnose defects and, when the user requests a fix, repair them through reproduction, evidence, root-cause analysis, and regression verification. Use for known or suspected bugs; do not use for unrelated feature work.
---

# Debug

Use this workflow for defects, regressions, failing checks, and unexpected behavior. Repository instructions, operational safeguards, and project-defined commands take precedence.

## Route the request

- For diagnosis-only requests, perform investigation and report the evidence, supported root cause, and uncertainty without modifying files.
- When the user requests a fix, use this skill within `project-dev-cycle` and complete its Git preflight and branch protections before editing code or tests.
- If the requested scope is unclear, investigate read-only first. Do not infer permission to modify files from a request to explain, diagnose, or identify a cause.
- A scoped defect remains in this workflow. If evidence indicates possible corruption, partially written durable state, uncontrolled external side effects, broad unrelated regressions, or impact that cannot be bounded safely, stop ordinary repair progression and activate `incident-recovery`; continue technical diagnosis only within its containment and evidence-preservation constraints.

## 1. Establish the problem

1. Read the relevant repository instructions, context, and recent changes.
2. Recover the expected behaviour from the governing specification, acceptance criteria, tests, decisions, and durable project context. Record the observed symptom, expected behavior, affected environment, inputs, and available error output. Separate these observations from interpretations; if the expected business behaviour is undocumented or ambiguous, request clarification instead of guessing.
3. Reproduce the problem with the smallest safe case practical. Do not alter production or runtime data without explicit authorization, and do not reproduce by repeating an uncertain external write unless idempotency or an authorized incident plan makes the retry safe.
4. If reproduction is unsafe or unsuccessful, document the attempts and evidence. Do not present an unverified guess as the root cause.

## 2. Gather evidence and test hypotheses

Inspect the failing path in context: inputs, state transitions, logs, configuration, dependencies, recent diffs, and relevant tests. Form a small set of falsifiable hypotheses, ordered by the evidence, and test them one at a time with the least invasive checks available.

Distinguish the triggering condition, visible symptom, contributing factors, and supported root cause. Stop expanding the investigation once the evidence adequately explains the defect and its scope.

## 3. Capture and repair the defect

Perform this section only when the user has requested implementation of a fix.

1. Update the specification or acceptance criteria when the defect reveals a missing or incorrect behavioural contract. Derive and review the regression scenario from that contract.
2. Add or identify a focused failing regression check when the project supports it and doing so is practical. Confirm it fails for the expected reason before relying on it.
3. Apply the smallest coherent fix at the supported root cause. Preserve behavior outside the confirmed defect and avoid unrelated refactoring.
4. Do not weaken, delete, or bypass valid tests merely to make the suite pass. Never hide failures.
5. Run focused checks for the repaired path, then relevant regression checks and the canonical repository validation command, or all project-required gates when no aggregate command exists.

If a safe fix cannot be supported by evidence, stop and report the uncertainty rather than making speculative production changes.

## 4. Report

State what was inspected, whether and how the issue was reproduced, the evidence supporting the root cause, commands and results, and any residual risk or uncertainty. For an implemented fix, also report regression coverage and the minimal change made. Clearly label an issue that was not reproduced or a root cause that remains unconfirmed.
