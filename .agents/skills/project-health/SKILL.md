---
name: project-health
description: Summarize the current repository's operational health, stale or blocking evidence, attention items, and one next safe action without rerunning or duplicating focused workflow checks.
---

# Project health

Answer:

> What is the current operational health of this repository, what needs attention, and what is the next safe action?

Use the contract in the [project-health specification](../../../docs/PROJECT_HEALTH.md). This capability is a lightweight, read-only operational summary. It consumes current evidence owned by other workflows; it does not reproduce their analysis, silently repair state, or authorize progression.

## 1. Establish the health question

Identify the current repository and, when evidence establishes them, the active task and intended next workflow action. Evaluate whether the repository is sufficiently understood and supported for that action. If no active task is established, evaluate whether normal task entry is safe.

When `context-resume` trigger conditions apply, follow the repository's existing entry/resume policy first. Reuse a current Working Context when available, then inspect only the targeted evidence needed for health. Do not turn project health into another detailed context reconstruction. If active-task context remains missing, stale, or conflicting, make `context-resume` the next safe action.

Do not automatically invoke another skill or rerun an expensive check merely to fill the report. If the user separately requested execution or the surrounding authorized workflow already requires a canonical check, run it under its owning skill and consume its result afterward. Otherwise mark insufficient evidence current, stale, missing, unavailable, or not applicable as supported.

## 2. Inspect current repository state

Use read-only inspection and authoritative repository evidence. At minimum, determine:

- repository name or identity, current branch, and `HEAD`;
- clean or dirty state, with staged, unstaged, and non-ignored untracked categories distinguished;
- ahead, behind, or divergence from an available tracking ref, plus whether remote freshness is verified;
- the latest relevant quality-gate mode/result and the exact state it covered where known;
- relevant dependency-security result, risk, findings, and covered scope where applicable;
- current governed incident/recovery state where present;
- material current-task, project-status, specification, decision, memory, review, research, and handoff evidence; and
- contradictions, missing required evidence, or unsafe ambiguity.

Prefer small Git queries, current deterministic evidence, and targeted governed records. Do not reread the whole codebase, run a full repository review, add a cache, or produce a large narrative when concise evidence is available.

Do not fetch, pull, switch branches, reset, restore, clean, rebase, merge, stage, commit, push, delete, edit, or otherwise mutate repository state during the health check. Use available tracking refs and label remote freshness unverified when current fetch evidence is absent. Missing optional artifacts are not defects by themselves.

## 3. Evaluate the seven dimensions

### Git

Report branch, `HEAD`, dirty categories, tracking divergence, and remote freshness. Interpret dirty state in context:

- attributable work for a known active task may remain `HEALTHY` or `ATTENTION`;
- unknown or apparently unrelated changes require at least `ATTENTION`; and
- mixed work, unsafe ownership ambiguity, or a branch mismatch that prevents safe continuation is `BLOCKED`.

Never use `dirty tree = BLOCKED` as a rule.

### Validation

Report the latest relevant quality-gate mode/result and whether it is current, stale, missing, unavailable, or authoritatively not applicable. Treat a result as current only when trustworthy evidence binds it to the applicable branch, `HEAD`, working-tree content, validation configuration, and required environment under the quality-gate contract.

Relevant later changes invalidate an unbound PASS. Do not recreate or execute quality checks here. Recommend the canonical quality gate when the intended action requires fresh evidence. A current required `FAIL` is established negative evidence rather than stale or missing evidence: it makes the affected progression `BLOCKED`, preserves the reported failure, and returns repair to `project-dev-cycle`, using `debug` when diagnosis or a fix is requested. Do not recommend rerunning the same unchanged failing gate as the primary action. An authoritative lack of a product test harness or another `NOT_APPLICABLE` category is not a health defect.

### Security

When dependency/security triggers or repository policy make the evidence relevant, report the current `dependency-security-check` result, risk, unresolved findings, and freshness. Consume its result without repeating package, provenance, vulnerability, secret, ignore, or install/build analysis.

- `FINDINGS` is at least `ATTENTION` and becomes `BLOCKED` when policy or the intended action requires resolution.
- Required `BLOCKED`, missing, or stale evidence blocks the affected intended action.
- A likely real secret exposure retains the owning skill's redacted critical finding and incident routing. Never inspect, print, test, rotate, or remove the value.

When no trigger or policy applies, report `NOT_APPLICABLE` with the reason rather than inventing PASS.

### Incident

Report the governed state without reclassifying or resolving it. `SUSPECTED`, `CONFIRMED`, `CONTAINED`, `RECOVERY_PLANNED`, `RECOVERING`, `RECOVERED_PENDING_VERIFICATION`, and incident `BLOCKED` normally make overall health `BLOCKED`. `DISPROVED` is a terminal false alarm. `RECOVERY_VERIFIED` removes only the incident blocker; pending validation, review, operational authority, or another checkpoint remains independent.

Do not create an incident from an ordinary warning, contain or recover an incident, or claim that a passing check closes one.

### Documentation and state freshness

Inspect only relevant present artifacts such as project status, decisions, project memory, governing specifications, task/incident/research records, review evidence, and handoff. Compare material claims with current Git and newer governed evidence.

Do not require every document to change for every commit. A status or record is stale when a material current claim is contradicted, superseded, bound to older state, or too ambiguous to trust. Stale non-critical status is usually `ATTENTION`; use `BLOCKED` only when the conflict prevents safe interpretation or progression.

### Task

When supported, report a concise checkpoint such as no active task, specification/test design, implementation, validation pending, review-ready, review findings pending, blocked, or active handoff. Keep implemented, validated, reviewed, committed, merged, pushed, released, and deployed distinct.

For an active task, the one next action follows its current checkpoint rather than starting unrelated work. A new session with a handoff still runs `context-resume` and verifies the handoff under its owning contract.

### Research

For applicable investment/trading research, consume governed evidence for holdout contamination, stale experiment state, frozen-baseline mismatch, incomplete ledger, or reproducibility concern. Do not inspect outcomes, rerun analysis, or independently judge the strategy. A material holdout, provenance, or research-integrity flag blocks the affected workflow. For ordinary repositories report `Not applicable`.

## 4. Apply the staleness model

Staleness is a mismatch between evidence and current state, not age alone. Timestamps may order records but cannot prove validity.

- Quality evidence becomes stale after relevant code, test, configuration, dependency, specification, validation-logic, branch, `HEAD`, or covered working-tree changes unless the evidence proves continued applicability.
- Dependency-security evidence becomes stale after relevant dependency, manifest, lockfile, source, install/build, credential/environment, authentication-storage, ignore-rule, or covered-scope changes.
- A handoff may be stale after repository identity, branch, `HEAD`, fingerprint, specification, decision, task-prerequisite, or validation-freshness changes. Do not treat it as authoritative.
- Project status becomes stale when material branch, `HEAD`, active-task, checkpoint, incident, validation, completion, or next-step claims conflict with higher-authority evidence.
- Review evidence becomes stale for progression when the reviewed diff or another validation-relevant artifact changes.
- Research evidence becomes stale or invalid when governed version, frozen specification, provenance/dataset binding, ledger, or contamination status no longer matches.

Reevaluate positive evidence after a branch change even when `HEAD` matches. When evidence lacks sufficient identity, report `unknown` or `stale for the intended action`; never reuse it blindly.

## 5. Aggregate overall health

Use exactly one state:

- **HEALTHY** — No known operational blocker, unresolved integrity issue, or material unsafe ambiguity exists, and repository/evidence state is current enough for the named next action. This does not imply cleanliness, review, release readiness, production safety, or authorization.
- **ATTENTION** — Work may continue carefully and a safe next action exists, but non-blocking issues require awareness.
- **BLOCKED** — Normal new implementation or the intended progression must not continue until a material blocker is resolved.

Aggregate in this order:

1. `BLOCKED` if any dimension establishes an active incident, governed research-integrity stop, current required quality-gate `FAIL`, required validation/security block, critical stale evidence needed now, repository inconsistency, or unsafe ambiguity.
2. Otherwise `ATTENTION` if at least one non-blocking condition materially requires awareness for the named next action. Examples include attributable dirty work whose scope or checkpoint still needs attention, unavailable optional evidence that is relevant enough to note, stale non-critical documentation, non-blocking divergence, or an active workflow checkpoint needing awareness.
3. Otherwise `HEALTHY`. A fully understood attributable dirty tree that needs no additional awareness and unavailable optional evidence that is irrelevant to the named action remain informational and do not prevent `HEALTHY`.

A focused PASS cannot erase a blocker in another dimension. A warning is not automatically blocking, and a condition does not become an attention item merely because it belongs to a category that sometimes needs awareness. Classify every condition by its actual consequence for the named action. Classify missing evidence according to whether it is required for the intended action; optional absence may be informational.

## 6. Choose one next safe action

Return exactly one concrete primary action. Select the earliest applicable prerequisite:

1. continue or preserve active incident/critical integrity handling;
2. stop affected research progression and follow its governed integrity path;
3. resolve repository identity, branch, mixed-work, or ownership ambiguity;
4. run `context-resume` when active task or handoff context cannot be trusted, before any check whose branch, scope, applicability, or checkpoint depends on that context;
5. for a current required quality-gate `FAIL`, return to `project-dev-cycle` and use `debug` when diagnosis or repair is requested;
6. obtain missing, stale, or blocked required dependency-security or quality-gate evidence through the owning skill after the applicable task scope is trusted;
7. continue the active task's next normal checkpoint, such as implementation, FULL validation, independent review, review-finding repair, or the separately governed approval step;
8. refresh stale durable status after confirming current state; or
9. start a new task through the normal development workflow.

Name the target and workflow step. Do not say only “check the repository.” A recommendation does not perform the action or authorize a later boundary.

## 7. Report concisely

Use this shape, omitting empty detail but preserving every material blocker, stale item, and limitation:

```text
PROJECT HEALTH
Repository: <repository name>
Overall: <HEALTHY|ATTENTION|BLOCKED>

Repository: <branch / HEAD; clean or staged/unstaged/untracked; remote state/freshness>
Validation: <latest result and mode; current/stale/missing/not applicable>
Security: <result/freshness or not applicable>
Incident: <none known, current state, or unknown>
Project state: <status/spec/decision/memory freshness; active task; handoff>
Research: <result or not applicable>

Attention / blockers:
- <concise actionable item, or none>

Next safe action: <exactly one concrete workflow step>

PROJECT_HEALTH_RESULT=<HEALTHY|ATTENTION|BLOCKED>
```

Keep repository, overall result, active task, primary blocker, stale evidence, and next action explicit enough for a future external aggregator. Do not scan another repository, discover projects, or implement MORNING.

## 8. Preserve all boundaries

Project health is evidence and triage only. It does not:

- execute or duplicate quality/security logic;
- perform code review, context reconstruction, incident recovery, or research analysis;
- turn stale evidence current;
- silently fix any health issue;
- imply release readiness from good health; or
- authorize or perform commit, merge, push, release, deployment, production resumption, destructive cleanup, or branch deletion.
