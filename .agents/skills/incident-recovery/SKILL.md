---
name: incident-recovery
description: Contain and recover from credible repository, runtime, artifact, data, or production integrity incidents while preserving evidence and requiring verified resumption. Do not use for an ordinary scoped defect or isolated failing check.
---

# Incident recovery

Coordinate safe incident handling under the [incident-recovery specification](../../../docs/INCIDENT_RECOVERY.md). Use the standard [incident record template](../../../templates/INCIDENT_RECORD.md) when the incident must persist or affects durable state.

This skill owns containment, evidence preservation, recovery coordination, and resumption criteria. It does not create operational authority, replace service-specific runbooks, perform technical root-cause work owned by `debug`, or certify quality, review, release, or production readiness.

## 1. Decide whether this is an incident

Activate incident recovery when credible evidence indicates that integrity, persisted state, external side effects, or impact scope may be materially unsafe or untrustworthy. Examples include broad unrelated regressions, a partially completed write, possible corruption or data loss, uncontrolled repeated side effects, a compromised validation environment, or conflicting evidence about what an operation changed.

Do not activate it for one scoped unit-test, lint, type, build, or validation failure without broader risk. Route an ordinary defect to `debug` within `project-dev-cycle` and an ordinary check failure through the quality-gate failure path.

If a credible high-impact risk remains uncertain, use provisional state `SUSPECTED` and assess read-only. State why ordinary debugging is not yet safe enough.

## 2. Stabilize and preserve evidence

1. Report the observed signal, current incident state, known impact, unknowns, and next safe action.
2. Pause unsafe progression, retries, repeated writes, review advancement, release, deployment, or cleanup that could worsen harm or destroy evidence.
3. Identify running or scheduled actions that could expand the incident. Stop or isolate them only when already authorized and safer than continuation; otherwise request the required operator action.
4. Record a timestamped timeline. Separate direct observations from inference and do not rewrite earlier events.
5. Preserve the minimum necessary logs, command results, identifiers, hashes, snapshots, artifacts, and configuration references. Keep credentials, secrets, private data, and unrestricted logs out of repository records; use sanitized summaries and restricted references.
6. Establish the last known trustworthy state, first unsafe or uncertain state, affected scope, and explicitly unknown scope where evidence permits.

Prefer read-only inspection and reversible actions. Do not run destructive cleanup, rollback, restore, failover, replay, data correction, secret rotation, or another live mutation merely because the situation is urgent.

## 3. Contain with the least invasive safe action

Choose containment that stops or bounds further harm while preserving evidence. Before any mutating action, identify the exact target, expected effect, blast radius, reversibility, evidence impact, authorization, and verification method.

Use the applicable runbook and authorized operator for live systems. If authority is missing, targets are uncertain, or the action is materially destructive, enter `BLOCKED` and request the exact approval or operator action needed. Verify containment from independent evidence where practical; symptom disappearance or absence of a fresh alert may be delayed and is not enough by itself.

## 4. Plan and execute recovery

Use `debug` for focused reproduction, hypotheses, root-cause diagnosis, and technical repair. During an incident, debugging must respect containment and evidence-preservation constraints.

Before recovery mutation, document:

- the trustworthy recovery source or forward-fix basis;
- exact targets and exclusions;
- prerequisites, backups, snapshots, checksums, or dry runs;
- required approvals;
- planned operations and expected observable outcomes;
- abort conditions and fallback;
- partial-execution detection and handling; and
- verification required before resumption.

Compare rollback and forward repair rather than assuming either is safe. Select the smallest justified blast radius. Execute only the authorized plan after prerequisites pass, and keep a chronological secret-safe record of actions and results.

Stop on an abort condition, target mismatch, conflicting evidence, loss of containment, unexpected deviation, or scope expansion. Do not automatically retry an uncertain external write unless idempotency or deduplication is established or an authorized plan explicitly accepts the duplicate-effect risk.

## 5. Track state and transfer safely

Use exactly one state: `SUSPECTED`, `DISPROVED`, `CONFIRMED`, `CONTAINED`, `RECOVERY_PLANNED`, `RECOVERING`, `RECOVERED_PENDING_VERIFICATION`, `RECOVERY_VERIFIED`, or `BLOCKED`.

When non-mutating evidence establishes that the suspected incident did not occur and no recovery is required, transition to terminal state `DISPROVED`. If a durable record exists, preserve the disproving evidence, record which incident-only constraints are lifted and which independent constraints remain, and name the prior normal-workflow checkpoint that may resume; do not leave it at `SUSPECTED` or relabel it `RECOVERY_VERIFIED`. Use `DISPROVED` only for a false alarm, never when real integrity, state, or side-effect impact occurred.

Create or update the incident record when the incident is confirmed, persists beyond the interaction, affects durable or production state, requires a recovery mutation, or must be transferred. Use `task-handoff` only when another agent or session must continue the active incident; the incident record remains the durable evidence, and the receiver still runs `context-resume` and verifies current state.

## 6. Verify recovery before resuming

Use `RECOVERY_VERIFIED` only for an incident that actually occurred and when all applicable evidence establishes:

- containment is still effective or deliberately superseded by a verified safe state;
- repository, artifact, runtime, and data integrity cover the affected scope;
- root cause is repaired or an explicitly accepted control prevents recurrence;
- targeted and regression checks pass, plus the final-content FULL quality gate when repository changes are involved;
- required independent review of repair changes is complete;
- live operational health and side effects satisfy the project-defined observation window;
- residual risks, unverified areas, monitoring, and follow-up are explicit;
- the incident record is current; and
- an authorized person or runbook has approved resumption when required.

A disappeared symptom or quality-gate PASS alone cannot close the incident. `DISPROVED` means no recovery occurred or was required; `RECOVERY_VERIFIED` means a real incident completed the applicable recovery evidence. Resume the normal workflow at the earliest checkpoint whose evidence remains valid. Never infer commit, merge, push, release, deployment, production mutation, destructive cleanup, retry, or branch-deletion authority from incident state.

## 7. Report

Report the current state, observed evidence, known and unknown scope, containment status, actions taken and their authority, recovery plan or execution state, verification completed and outstanding, residual risk, explicitly unperformed actions, and one next safe action. Clearly distinguish an active, blocked, disproved, pending-verification, and verified incident.
