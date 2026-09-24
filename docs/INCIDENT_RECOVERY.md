# Behaviour specification: incident recovery

## Identity and change control

- Specification: `docs/INCIDENT_RECOVERY.md`
- Revision: 2
- Status: reviewed
- Last updated: 2026-09-22
- Related decision record: none; this capability supplies the previously missing containment and trustworthy-resumption path without changing existing operational or Git authority.

## Intent and scope

`incident-recovery` coordinates evidence preservation, containment, recovery, and verified resumption when repository, runtime, data, or production state may be unsafe or materially uncertain.

Its governing rule is:

> Stop normal progression, preserve trustworthy evidence, contain further harm with the least invasive safe action, and resume only after the affected state is verified.

An incident is not merely a failing check. It is a credible indication that integrity, persisted state, side effects, or impact scope cannot yet be trusted. Examples include many unrelated regressions after an uncertain change, a partially written production artifact, possible data loss or corruption, uncontrolled repeated side effects, a compromised validation environment, or conflicting evidence about what an operation changed.

### Trigger conditions

Activate the capability when available evidence supports at least one of these conditions:

- repository, build, runtime, data, or production integrity may be compromised;
- a write or external operation completed only partially and its resulting state is uncertain;
- failures are broad, unrelated, or disproportionate enough that a local defect assumption is unsafe;
- the affected scope or side effects cannot be bounded with ordinary debugging evidence;
- continued execution, retries, deployment, review progression, or cleanup could worsen harm or destroy evidence; or
- the user or an applicable runbook declares an incident.

A single scoped unit-test, lint, type, build, or validation failure does not activate incident recovery without broader evidence. Route ordinary defects to `debug` within `project-dev-cycle`, and ordinary validation failures to the configured quality-gate failure path.

When evidence is incomplete but a credible high-impact integrity risk exists, prefer a provisional `SUSPECTED` incident and read-only assessment over continued mutation. Do not inflate low-impact uncertainty into an incident merely to add process.

### In scope

- declaring and classifying an incident without overstating certainty;
- pausing unsafe normal progression;
- preserving secret-safe evidence and an event timeline;
- choosing and verifying the least invasive containment available within current authority;
- bounding affected systems, repositories, artifacts, data, operations, and time windows;
- coordinating technical diagnosis through `debug` without duplicating its root-cause method;
- defining a recovery plan, prerequisites, authorization needs, rollback or forward-repair choice, verification, and abort conditions;
- tracking recovery state and recording durable incident evidence;
- verifying recovery and deciding whether normal workflow may resume; and
- handing an active incident across an agent or session through `task-handoff` when transfer is necessary.

### Out of scope

- treating every failed check or ordinary bug as an incident;
- replacing emergency, security, privacy, compliance, disaster-recovery, or service-specific runbooks;
- independently diagnosing and repairing a technical defect when `debug` owns that work;
- asserting quality-gate PASS, technical review, release readiness, or production safety;
- authorizing or silently performing production mutations, rollback, restore, failover, replay, reprocessing, customer communication, secret rotation, destructive cleanup, or data correction;
- committing, merging, pushing, releasing, deploying, force-pushing, rewriting history, or deleting branches; and
- concealing evidence, deleting logs or artifacts, or rewriting incident history after the fact.

## Responsibility boundaries

- `incident-recovery` owns incident activation, containment coordination, evidence preservation, recovery planning, recovery-state tracking, and verified resumption criteria.
- `debug` owns focused reproduction, hypothesis testing, root-cause diagnosis, and minimal technical repair. During an incident it operates inside the containment and evidence-preservation constraints.
- `quality-gate` supplies deterministic validation evidence for the current content; its PASS neither closes an incident nor proves runtime or data integrity.
- `context-resume` reconstructs current repository state. It does not declare recovery complete, but it consumes current incident records when they affect the next safe action.
- `task-handoff` transfers the incident task when necessary. It does not replace the incident record or authorize containment or recovery actions.
- `code-review` independently evaluates a proposed or completed repair.
- `release-check` assesses readiness for one named boundary only after recovery evidence supports reaching that boundary.
- Project runbooks and authorized operators own live operational commands and service-specific emergency actions.
- Human approvers retain every existing Git and operational approval boundary.

## Incident states

Use exactly one current incident state:

- **SUSPECTED** — Credible evidence indicates a possible incident, but scope or integrity impact is not yet established. Unsafe normal progression is paused while read-only assessment continues.
- **DISPROVED** — Read-only or otherwise non-mutating evidence establishes that the suspected incident did not occur and no recovery is required. The record preserves the disproving evidence, identifies which incident-only constraints may be lifted, and states the normal-workflow checkpoint that may resume. This is a terminal false-alarm disposition, not recovery verification.
- **CONFIRMED** — Evidence establishes an integrity, state, side-effect, or impact incident. Containment is not yet established.
- **CONTAINED** — Further harm is stopped or bounded, the containment method and limitations are recorded, and evidence needed for investigation is preserved. Containment does not mean recovery.
- **RECOVERY_PLANNED** — A specific recovery path, prerequisites, authorization needs, verification, and abort conditions are documented. Execution has not necessarily begun.
- **RECOVERING** — An authorized recovery action is in progress. Partial results and deviations remain visible.
- **RECOVERED_PENDING_VERIFICATION** — The planned recovery action completed, but all resumption criteria have not yet been established.
- **RECOVERY_VERIFIED** — The affected state, required checks, and residual risks satisfy the documented resumption criteria. This state does not authorize a later Git, release, deployment, or production boundary.
- **BLOCKED** — Required evidence, access, expertise, authority, safe containment, or a recovery prerequisite is unavailable. State the blocker and the exact external decision or condition needed.

Use `DISPROVED` only when evidence establishes that no incident occurred; do not use it to avoid recovery verification after real integrity, state, or side-effect impact. Never use `RESOLVED`, `DONE`, or bare `RECOVERED` when verification or downstream approvals remain outstanding. Do not close an incident merely because the visible symptom disappeared or a quality gate passed.

## Incident record

Use the standard [incident record template](../templates/INCIDENT_RECORD.md) when an incident is confirmed, persists beyond the current interaction, affects durable or production state, requires a recovery mutation, or must be transferred. A provisional low-impact suspicion may remain in the current report if it is quickly disproved without mutation. When a durable record already exists, disproving evidence must transition its current state to `DISPROVED`; do not leave it stale at `SUSPECTED` or misclassify it as `RECOVERY_VERIFIED`.

The record must identify:

- incident title, state, severity or impact description, owner if known, and timestamps with timezone;
- directly observed signals separated from inference;
- affected and explicitly not-yet-known scope;
- actions already occurring at discovery and any stopped or prohibited actions;
- evidence sources, preservation locations, collection limits, and secret-safe handling;
- containment action, authority, result, limitations, and reversibility;
- recovery options considered and the selected plan with rationale;
- every required approval, prerequisite, abort condition, and fallback;
- recovery execution events without rewriting earlier entries;
- verification across affected state, data or artifacts, targeted checks, FULL quality gate where applicable, review, and operational health;
- residual risk, follow-up work, and the exact resumption decision; and
- actions explicitly not performed.

Record only the minimum sensitive information needed. Never copy secrets, credentials, private customer data, secret-bearing environment output, or unrestricted logs into the repository. Use sanitized summaries and restricted evidence references.

## Recovery workflow

### 1. Activate and stabilize

1. State the observed signal, current incident state, known impact, unknowns, and why ordinary debugging is insufficient.
2. Pause the affected normal workflow, including retries, review progression, release, deployment, cleanup, and repeated writes that could expand harm or destroy evidence.
3. Identify currently running or scheduled actions that may worsen the incident. Stop or isolate them only when doing so is already authorized and safer than allowing them to continue; otherwise request the required operator action immediately.
4. Prefer read-only inspection and reversible containment. Do not improvise destructive commands under time pressure.

### 2. Preserve evidence and bound scope

1. Record a timeline using observed timestamps and label reconstructed timing as inference.
2. Preserve relevant logs, command results, identifiers, hashes, snapshots, and configuration references without exposing secrets or altering the evidence source unnecessarily.
3. Establish the last known trustworthy state and the first known unsafe or uncertain state when evidence permits.
4. Bound affected repositories, branches, commits, environments, services, artifacts, records, users, and time windows. Keep every unsupported boundary explicitly unknown.
5. Record evidence gaps and whether continued investigation could itself change state.

### 3. Contain

Choose the least invasive action that stops or bounds further harm while preserving evidence. Examples may include pausing a scheduled task, disabling a write path, isolating an artifact, or preventing further promotion, but the applicable runbook and authorization determine the actual action.

Before a mutating containment action, identify the exact target, expected effect, reversibility, blast radius, evidence impact, authorization, and verification. If authority is missing or the action is materially destructive, stop and request approval or an authorized operator. Verify containment from independent evidence where practical; absence of new alerts alone is insufficient when signals may be delayed.

### 4. Diagnose and plan recovery

Use `debug` for technical root-cause work when a defect is involved. Keep incident coordination focused on scope, integrity, containment, recovery choice, and resumption.

The recovery plan must state:

- the trustworthy recovery source or forward-fix basis;
- affected targets and exclusions;
- prerequisites and required backups, snapshots, checksums, or dry runs;
- exact operations at a safely reviewable level;
- required human or operator approvals;
- expected observable outcomes;
- abort conditions and a safe fallback;
- how partial execution will be detected and handled; and
- verification needed before resumption.

Prefer the path with the smallest justified blast radius. Do not assume rollback is safer than forward repair: compare evidence loss, schema or compatibility constraints, irreversible external effects, and the trustworthiness of the recovery source.

### 5. Execute within authority

Execute only the approved plan and only after its prerequisites are verified. Preserve a chronological record of commands or operator actions, sanitized results, unexpected deviations, and decisions. Stop at an abort condition, conflicting evidence, target mismatch, loss of containment, or unapproved scope expansion. A retry is a new state-changing action when it may duplicate external effects; do not retry automatically without idempotency evidence or authorization.

### 6. Verify and resume

Recovery may reach `RECOVERY_VERIFIED` only when all applicable criteria are established:

1. containment remains effective or is deliberately superseded by a verified safe state;
2. repository, artifact, runtime, and data integrity checks cover the affected scope;
3. the technical root cause is repaired or an explicitly accepted workaround prevents recurrence;
4. targeted and regression checks pass, and the repository-defined FULL quality gate passes for the final content when repository changes are involved;
5. independent review is complete for repair changes when the normal workflow requires it;
6. operational health and side effects are checked for an appropriate project-defined observation window when live state was affected;
7. residual risks, unverified areas, monitoring, and follow-up actions are explicit;
8. the incident record is current and no evidence was silently discarded; and
9. the person or runbook authorized to resume the affected operation has made that decision when operational authorization is required.

A quality-gate PASS is only one input. It cannot prove restored data, completed external effects, operational health, or authorization. After recovery is verified, return to the normal workflow at the earliest still-valid checkpoint; do not skip review, release checks, or explicit Git and production approvals.

## Acceptance criteria

1. Ordinary scoped failures route to quality-gate failure handling or `debug`; incident recovery activates only on credible broader integrity, state, side-effect, or scope risk.
2. Activation pauses unsafe progression and makes the incident state, evidence, known impact, unknowns, and next safe action explicit.
3. Evidence is preserved chronologically, secret-safely, and without rewriting earlier events or presenting inference as observation.
4. Containment is least-invasive, scoped, authority-aware, evidence-preserving, and independently verified where practical.
5. Missing authority, unsafe targets, destructive recovery, or unbounded blast radius blocks mutation rather than being inferred from urgency.
6. Technical diagnosis and repair remain owned by `debug`; incident recovery owns containment, integrity, recovery coordination, and resumption.
7. A recovery plan identifies source/basis, targets, exclusions, prerequisites, approvals, expected outcomes, abort conditions, partial-execution handling, fallback, and verification.
8. Retries with possible external side effects require idempotency evidence or authorization and never occur automatically merely because an attempt was uncertain.
9. `RECOVERY_VERIFIED` requires affected-state integrity evidence and every applicable resumption criterion; symptom removal or quality-gate PASS alone is insufficient.
10. Recovery never implies commit, merge, push, release, deployment, production mutation, branch deletion, destructive cleanup, or another operational approval.
11. Active incidents survive context loss through a durable incident record and optional task handoff; receivers still run `context-resume` and verify current state.
12. Existing normal development, quality-gate, handoff, review, release, research, and approval workflows remain valid when no incident trigger exists.
13. A suspected incident that is disproved has the terminal state `DISPROVED`; any existing durable record preserves the disproving evidence, records lifted and remaining constraints, and names the prior normal-workflow checkpoint without claiming recovery occurred.

## Validation scenarios

| ID | Scenario | Expected observable result |
| --- | --- | --- |
| IR-01 | One new unit-test failure with a bounded code path | Routes to quality-gate failure handling and `debug`; no incident is declared without broader evidence. |
| IR-02 | Seventy-two previously unrelated failures after an uncertain environment or repository change | Declares at least `SUSPECTED`, pauses ordinary fix/review progression, preserves evidence, and bounds integrity and environment scope before repair. |
| IR-03 | Partially written production artifact | Stops further promotion or writes within authority, records the partial state, preserves the artifact and evidence, and requires an authorized recovery plan. |
| IR-04 | Retry after an uncertain external write | Does not retry until idempotency or deduplication is established or an authorized plan accepts the duplicate-effect risk. |
| IR-05 | Destructive rollback appears fastest | Names exact targets, blast radius, evidence loss, prerequisites, and authority; blocks execution until explicitly authorized. |
| IR-06 | Suspected incident is disproved by read-only evidence | Uses terminal state `DISPROVED`; if a durable record exists, updates it with the disproving evidence, lifted and remaining constraints, and resumable prior checkpoint; never leaves it `SUSPECTED` or labels it `RECOVERY_VERIFIED`. |
| IR-07 | Quality gate passes after a repository repair but persisted data remains unverified | Remains `RECOVERED_PENDING_VERIFICATION`; does not close the incident or resume affected operations. |
| IR-08 | Recovery action deviates from its plan | Stops at the deviation, records partial execution, reassesses containment and scope, and requires an updated authorized plan. |
| IR-09 | Evidence contains credentials or private customer data | Stores only sanitized summaries or restricted references and never writes the sensitive values into repository artifacts. |
| IR-10 | Incident crosses an agent or session boundary | Maintains the incident record, optionally creates a task handoff, and requires the receiver to run `context-resume` and verify the active state. |
| IR-11 | Containment removes the visible symptom | Remains contained rather than recovered until root-cause/workaround, affected-state integrity, checks, residual risk, and resumption criteria are established. |
| IR-12 | Recovery source or last known good state cannot be trusted | Enters `BLOCKED`, identifies the missing evidence or authority, and performs no speculative restore. |
| IR-13 | Research pipeline incident threatens holdout or experiment history | Preserves preregistration, frozen versions, timestamps, and append-only history; does not rewrite contaminated evidence as if it were clean. |
| IR-14 | Recovery is verified for a code change | Requires affected checks, final-content FULL PASS, applicable independent review, and then returns to the earliest valid normal checkpoint without granting Git approval. |
| IR-15 | Repository gains incident recovery | Every repository skill validates, relative links and structural contracts pass, version references agree, and existing non-incident routes remain unchanged. |

## Test-design review

- [x] Trigger boundaries cover ordinary failures, broad regressions, partial writes, external side effects, and false alarms with a durable terminal disposition.
- [x] Containment, evidence preservation, scope, authorization, recovery planning, partial execution, verification, transfer, and resumption are covered.
- [x] Quality-gate PASS cannot substitute for runtime, artifact, or data integrity.
- [x] Destructive actions, live operations, retries, and later Git or release boundaries retain separate authority.
- [x] `debug`, `quality-gate`, `context-resume`, `task-handoff`, review, release, and research responsibilities remain distinct.
- [x] Scenario outcomes are observable and do not prescribe a service, language, toolchain, or incident platform.
- Reviewer: revision 1 internal requirement-to-scenario review completed 2026-09-22; revision 2 addresses the human-reviewed false-alarm terminal-state finding and was independently reviewed and approved by the user on 2026-09-22.

## Validation and traceability

- Skill structure/frontmatter: bundled `skill-creator` quick validator.
- Specification coverage: structural check for the nine states, including the `DISPROVED` false-alarm terminal path, key approval and resumption invariants, and IR-01 through IR-15 definitions/results.
- Behaviour: manual trace of IR-01 through IR-15 against the implemented skill and integrated routing.
- Documentation and paths: repository-wide relative Markdown link check plus stale wording search.
- Existing regression: validate every repository skill and preserve existing non-incident workflow and approval behaviour.
- Repository tests: none currently exist; this instruction-only template has no executable product test harness.

### Manual scenario results

| Scenario | Result | Evidence in the implemented capability |
| --- | --- | --- |
| IR-01 | Pass | Trigger routing explicitly excludes a scoped ordinary failure without broader risk. |
| IR-02 | Pass | Broad disproportionate failures activate provisional containment and integrity assessment. |
| IR-03 | Pass | Partial writes are a trigger and the workflow preserves the artifact, stops unsafe progression, and plans authorized recovery. |
| IR-04 | Pass | Recovery execution prohibits automatic retries with uncertain external effects absent idempotency evidence or authority. |
| IR-05 | Pass | Mutating containment and recovery require exact targets, blast-radius assessment, reversibility/evidence impact, and applicable approval. |
| IR-06 | Pass | Read-only disproving evidence transitions any durable `SUSPECTED` record to terminal state `DISPROVED`, preserves the rationale and constraint changes, and returns to the prior checkpoint without claiming recovery. |
| IR-07 | Pass | FULL PASS is only one input and cannot establish persisted-state integrity or incident closure. |
| IR-08 | Pass | Plan deviations and abort conditions stop execution and force reassessment rather than silent scope expansion. |
| IR-09 | Pass | Evidence handling excludes secrets and private data in favor of sanitized summaries or restricted references. |
| IR-10 | Pass | Durable incident records and optional handoffs survive transfer, while receivers independently reconstruct state. |
| IR-11 | Pass | Containment and symptom removal remain distinct from recovery verification. |
| IR-12 | Pass | Untrusted recovery sources or missing prerequisites produce `BLOCKED`, not speculative mutation. |
| IR-13 | Pass | Research integration preserves governed, timestamped, append-only evidence and contamination history. |
| IR-14 | Pass | Final repository repair requires affected checks, FULL, applicable review, and a return to normal approval boundaries. |
| IR-15 | Pass | Covered by the repository FULL profile and final complete-diff inspection. |

### Repository check results

- Bundled quick validation: all eleven repository skills pass in Python UTF-8 mode.
- Incident contract: all nine states, the `DISPROVED` false-alarm transition, and IR-01 through IR-15 definitions/results pass structural checks.
- Repository-defined FULL profile: pass on 2026-09-22; patch integrity covers tracked, staged, and three non-ignored untracked files; 23 relative Markdown targets resolve; quality-gate and incident contracts pass; version references agree at `1.6.0`.
- Content freshness: the pre-write-back FULL run matched before/after at `f9e2bd066a2c7d5a88330ef2657053b3985ef627b9f018bf93d0186988f9bae6`; final post-write-back freshness is reported in the task result because embedding that digest would invalidate itself.
- Automated product tests: not applicable; this template intentionally has no executable product test harness.
