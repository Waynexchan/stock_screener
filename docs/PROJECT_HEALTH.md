# Behaviour specification: project health

## Identity and change control

- Specification: `docs/PROJECT_HEALTH.md`
- Revision: 2
- Status: implemented; independent review findings addressed
- Last updated: 2026-09-23
- Related decision record: none; this capability adds a read-only operational summary layer without changing existing workflow ownership or approval policy.

## Intent and scope

`project-health` answers:

> What is the current operational health of this repository, what needs attention, and what is the next safe action?

It is a lightweight, read-only triage capability. It inspects current repository state, consumes current evidence already owned by existing workflow capabilities, detects material staleness or inconsistency, assigns one overall health state, surfaces actionable issues, and names exactly one primary next safe action.

It does not reimplement or automatically execute validation, dependency-security analysis, code review, incident recovery, context reconstruction, research analysis, release readiness, or repository mutation. A project-health result is evidence for prioritization. It is not approval to commit, merge, push, release, deploy, resume an incident-affected operation, or cross another human-controlled boundary.

### In scope

- current branch, `HEAD`, working-tree categories, and verified remote divergence where available;
- current, stale, missing, failed, or blocked validation evidence;
- relevant dependency-security evidence and unresolved findings;
- active incident and recovery state;
- material freshness of project status, decisions, memory, specifications, research records, and handoffs;
- current task checkpoint where repository evidence establishes one;
- obvious contradictions or unsafe ambiguity across repository evidence;
- one aggregate `HEALTHY`, `ATTENTION`, or `BLOCKED` result; and
- one concrete, workflow-aware next safe action.

### Out of scope

- running a hidden FULL quality gate or reproducing any configured check;
- package, provenance, vulnerability, secret, ignore, or install-hook analysis;
- code or design review;
- incident containment, recovery, closure, or resumption;
- detailed session/task reconstruction already owned by `context-resume`;
- release, merge, deployment, or production-readiness claims;
- modifying project status, resolving stale evidence, switching branches, pulling, rebasing, merging, committing, pushing, deleting branches, or fixing issues;
- multi-repository discovery, MORNING orchestration, dashboards, monitoring services, background agents, schedules, CI, APIs, or persistent health databases; and
- independently evaluating investment or trading research.

## Responsibility boundaries

- `project-health` owns the concise current operational summary, issue triage, overall health aggregation, and one next safe action.
- `context-resume` owns detailed repository-backed Working Context reconstruction for a new or resumed agent/session. Project health may consume a current Working Context or recommend context recovery, but it does not replace or duplicate it.
- `quality-gate` owns deterministic execution and aggregation of project-defined checks. Project health may report its latest relevant result and freshness only.
- `dependency-security-check` owns dependency and repository-security analysis. Project health may report its current result, risk, findings, and freshness only.
- `incident-recovery` owns incident activation, containment, recovery, verification, and resumption. Project health reports the current governed state and cannot close or downgrade an incident.
- `task-handoff` owns one-task transfer across agents or sessions. Project health reports whether a handoff exists and appears current, stale, malformed, or unavailable.
- `code-review` owns independent technical assessment. Project health may report the review checkpoint or unresolved findings without reviewing the change.
- `release-check` owns readiness for a named repository or operational boundary. Good health never implies readiness for that boundary.
- `research-experiment` and its governed records own research validity and decisions. Project health reports established operational flags without performing research analysis.
- `project-dev-cycle` owns specification, implementation, validation, review sequencing, durable write-back, and Git approval boundaries.

No project-health conclusion overrides higher-authority repository evidence, a focused capability's result, a governed decision, or an existing approval requirement.

## Invocation and relationship to context recovery

Use project health when a user or workflow requests repository operational health, attention items, triage, or the next safe action. It may also supply a compact input to a future external aggregation workflow, but this capability operates on the current repository only.

The canonical relationship is acyclic:

1. When existing `context-resume` trigger conditions apply, run `context-resume` first as required by the repository workflow.
2. Project health may consume that current Working Context and verify only the targeted evidence needed for health classification.
3. When health inspection discovers that detailed active-task context is missing, stale, or conflicting, recommend `context-resume` as the next safe action rather than reconstructing the full task itself.

Project health does not automatically invoke `context-resume` on every call, and `context-resume` does not require project health. An unchanged active session may use current verified context; a new session with an active handoff still follows the receiving flow defined by `task-handoff`.

## Evidence and inspection model

Prefer current deterministic repository evidence and concise governed records over broad rereading or expensive execution. Inspect only the paths and history needed to establish the dimensions below. At minimum:

1. read applicable repository instructions;
2. verify repository root, branch, `HEAD`, staged, unstaged, and non-ignored untracked state;
3. inspect ahead/behind or divergence only from available tracking refs, and label remote freshness unverified unless policy-required fetch evidence is current;
4. locate relevant current-session or durable evidence for quality gate, dependency security, incidents, task state, handoff, project status, specifications, decisions, memory, and research governance;
5. compare claims with current Git and content identity where the owning capability provides one;
6. classify material issues as blocking, attention, or informational; and
7. aggregate the result and choose exactly one next safe action.

Missing optional artifacts are not defects by themselves. Missing or untrusted evidence is blocking only when repository policy or the intended next action requires it. Never infer that an unrecorded check passed, an absent incident record proves no incident exists, or an old positive result remains current.

### Evidence precedence

Use the repository's existing authority model. Current verified repository/filesystem state and governed records outrank status summaries, handoffs, and conversation. For a focused result such as quality, dependency security, incident state, review, or research status, the current evidence emitted under that capability's contract controls that claim. Surface conflicts rather than silently resolving or rewriting them.

## Health states

Use exactly one overall state:

- **HEALTHY** — No known operational blocker, unresolved integrity issue, or material unsafe ambiguity exists. The repository and required evidence are understood and current enough for the identified next action. HEALTHY does not mean clean, reviewed, releasable, production-safe, or authorized for any boundary.
- **ATTENTION** — Normal work may continue carefully and a safe next action exists, but one or more non-blocking issues materially require awareness for that action. Examples include attributable dirty work whose scope or checkpoint still needs attention, stale non-critical project status, unavailable optional evidence that is relevant enough to note, an ahead/behind condition that does not yet block the intended action, or current implementation awaiting its normal next checkpoint. A fully understood attributable dirty tree or unavailable optional evidence that is irrelevant to the named action may remain informational and does not by itself prevent `HEALTHY`.
- **BLOCKED** — Normal new implementation or the intended progression must not continue until a material blocker is resolved. Examples include an active unresolved incident, required blocked validation or dependency-security evidence, a governed research integrity block, contradictory or untrustworthy repository state, or critical required evidence that is stale or unavailable for the intended action.

Do not add intermediate overall states. Do not reduce aggregation to `dirty tree = BLOCKED` or `quality-gate PASS = HEALTHY`.

## Health dimensions

### 1. Git state

Report the current branch and full or unambiguous short `HEAD`; clean or dirty state; staged, unstaged, and non-ignored untracked categories; and ahead/behind/diverged tracking state when available. State whether remote freshness was verified.

Interpret a dirty tree in task context:

- intentional, attributable changes for the active task may be compatible with HEALTHY or ATTENTION;
- unknown or apparently unrelated changes require ATTENTION while ownership can be established;
- mixed changes, unsafe ownership ambiguity, or a branch mismatch that prevents safe continuation may be BLOCKED.

Never pull, switch, reset, restore, clean, rebase, merge, or otherwise change Git state during health inspection.

### 2. Validation state

Report the latest relevant quality-gate mode/result, the branch/`HEAD`/content it covers where known, and whether the evidence is current, stale, missing, or unavailable. A previous PASS is current only when trustworthy evidence binds it to the applicable current branch, `HEAD`, working-tree content, validation configuration, and required environment under the owning quality-gate contract.

Do not run or recreate quality checks. Reuse demonstrably current evidence; otherwise mark it stale or unavailable and recommend the canonical gate when the intended action requires it. A current required `FAIL` is established negative evidence, not stale or missing evidence: it makes the affected progression `BLOCKED`, preserves the reported failure, and routes repair through `project-dev-cycle` with `debug` when defect diagnosis or a fix is requested. Do not recommend rerunning the same unchanged failing gate as the primary action. Authoritative `NOT_APPLICABLE`, including the absence of a product test harness in an instruction-only repository, is not a health defect.

### 3. Security state

When dependency/security triggers or repository policy make the evidence relevant, report the current dependency-security result, risk, unresolved findings, and freshness. `FINDINGS` is at least ATTENTION and becomes BLOCKED when policy or the intended progression requires resolution. Required `BLOCKED`, missing, or stale evidence blocks the affected intended progression. A likely real secret exposure remains a critical finding and follows the incident route owned by `dependency-security-check` and `incident-recovery`; project health does not inspect or reproduce the value.

When no trigger or policy applies, report authoritative `NOT_APPLICABLE` or concise non-applicability rather than inventing a PASS.

### 4. Incident state

Report no active known incident, an active incident state, recovery pending, verification pending, or escalation required according to current governed evidence. `SUSPECTED`, `CONFIRMED`, `CONTAINED`, `RECOVERY_PLANNED`, `RECOVERING`, `RECOVERED_PENDING_VERIFICATION`, and incident `BLOCKED` prevent overall HEALTHY and normally make overall health BLOCKED. `DISPROVED` is a terminal false alarm, not an active incident. `RECOVERY_VERIFIED` removes the incident blocker only; any required revalidation, review, or authorization remains independently visible.

Project health never creates an incident solely from an ordinary warning and never declares recovery complete.

### 5. Documentation and state freshness

Inspect relevant durable artifacts only when present and applicable: project status, decisions, project memory, governing specifications, active task records, incident records, research records, and handoff. Compare material claims with current Git and newer governed evidence.

Do not require every document to change on every commit. Report staleness only when a claim material to current work is contradicted, superseded, bound to an older repository state, or too ambiguous to trust. Stale project status is normally ATTENTION; it becomes BLOCKED only when the contradiction prevents safe interpretation of the active state.

### 6. Task state

Where evidence permits, report one concise checkpoint such as no active task, specification/test design, active implementation, validation pending, review-ready, review findings pending, blocked, or active handoff. Preserve distinctions among implemented, validated, reviewed, committed, merged, pushed, released, and deployed. A healthy active task still directs the next action to its current workflow checkpoint rather than starting unrelated work.

### 7. Research state

For an applicable research/investment repository, consume governed research evidence for holdout contamination, stale experiment status, frozen-baseline mismatch, incomplete ledger, or reproducibility concern. Do not inspect outcomes or independently judge a strategy. A material holdout/provenance/integrity flag blocks the affected research workflow; non-critical record freshness may be ATTENTION. For ordinary repositories, report `Not applicable`.

## Staleness model

Staleness is evidence-to-current-state mismatch, not age alone. Timestamps may help order records but cannot establish validity.

- **Quality evidence** is stale when relevant code, tests, configuration, dependency, specification, validation logic, branch, `HEAD`, or covered working-tree content changed, unless the owning evidence explicitly and trustworthily establishes continued applicability.
- **Dependency-security evidence** is stale when a dependency, manifest, lockfile, package source, install/build hook, credential/environment handling rule, authentication storage configuration, relevant ignore rule, or covered change scope changed afterward.
- **Handoff evidence** may be stale when repository identity, branch, `HEAD`, content fingerprint, relevant specification/decision, task prerequisite, or validation freshness differs. Project health reports the handoff as stale and does not treat it as authoritative.
- **Project status** is stale when a material branch, `HEAD`, active task, checkpoint, incident, validation, completion, or next-step claim conflicts with current higher-authority evidence.
- **Review evidence** is stale for progression when the reviewed diff or a validation-relevant artifact changed afterward.
- **Research evidence** is stale or invalid when its governed version, frozen specification, dataset/provenance binding, experiment ledger, or contamination status no longer matches the affected workflow state.

A branch change requires explicit reevaluation even when `HEAD` happens to match. A positive result is never reused blindly. If the available record lacks enough identity to prove freshness, report `unknown` or `stale for the intended action` rather than current.

## Overall aggregation

Evaluate health relative to the repository's current active task and intended next action when those are known. If no active task is established, evaluate whether normal task entry is safe.

1. Overall is `BLOCKED` when any material dimension establishes an active incident, governed research-integrity stop, current required quality-gate `FAIL`, required validation/security block, critical stale evidence needed now, repository inconsistency, or unsafe ambiguity that prevents the intended action.
2. Otherwise overall is `ATTENTION` when one or more non-blocking conditions materially require awareness for the named next action. Examples include attributable dirty work whose scope or checkpoint still needs attention, unavailable optional evidence that is relevant enough to note, stale non-critical documentation, non-blocking remote divergence, or a normal active-task checkpoint requiring awareness.
3. Otherwise overall is `HEALTHY` when no blocker or attention item exists and evidence is sufficiently current for the named next action. A fully understood attributable dirty tree that needs no additional awareness and unavailable optional evidence that is irrelevant to the named action remain informational and do not prevent `HEALTHY`.

A focused PASS cannot erase another dimension's blocker. A warning does not become BLOCKED merely because it exists, and a fact does not become an attention item merely because it belongs to a category that sometimes needs awareness. Classify each condition by its actual consequence for the named action. When uncertainty affects required evidence, classify according to its consequence for the intended action; when task intent itself is materially unknown, the next safe action is context reconstruction and health is at least ATTENTION, or BLOCKED if continuing would be unsafe.

## Next-safe-action contract

Return exactly one primary next safe action. It must name a concrete workflow step and its target, not vague advice such as “check the repository.” Select the earliest prerequisite that safely advances or clarifies the current state.

Use this precedence when multiple issues exist:

1. preserve/continue active incident or critical integrity/security handling;
2. stop affected research progression and follow its governed integrity path;
3. resolve repository identity, branch, mixed-work, or ownership ambiguity;
4. reconstruct detailed context when an active task or handoff cannot be trusted, before running any check whose branch, scope, applicability, or checkpoint depends on that context;
5. for a current required quality-gate `FAIL`, return to `project-dev-cycle` and use `debug` when diagnosis or repair is requested;
6. obtain missing, stale, or blocked required dependency-security or quality-gate evidence through its canonical skill after the applicable task scope is trusted;
7. continue the active task's next normal checkpoint, such as implementation, FULL validation, independent review, review-finding repair, or the separately governed approval step;
8. refresh stale durable status after confirming current state; or
9. start a new task through the normal development workflow.

The action may recommend another canonical skill when its evidence is required and the user's request permits that workflow. Project health does not silently invoke the skill, perform the action, or claim authorization.

## Output contract

Produce a concise report. Omit empty detail while preserving every material blocker, stale item, and limitation.

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

For later multi-project aggregation, keep the repository, overall result, active task, primary blocker, stale evidence, and next action explicit and compact. Do not scan other repositories or add a registry/configuration mechanism in this capability.

## Efficiency and execution policy

Project health should be materially cheaper than a full repository review. Prefer small Git queries, targeted governed records, a current Working Context when available, and content-bound evidence already produced by canonical skills. Do not reread the entire codebase, run expensive suites by default, add a cache/database, or generate large narrative analysis when concise deterministic evidence exists.

Reuse evidence only when currentness is demonstrable. Mark stale evidence instead of repairing it. Recommend rerunning the owning skill when evidence is required but insufficient. Invoke another skill only under the normal workflow and user authority; project health itself remains read-only.

## Architecture decision

The initial capability is instruction-driven and consists of this authoritative specification plus one repository skill. No script is justified because the evidence locations and applicability rules are project-specific, the repository has no executable product/tooling layer, and the current Git queries are already available through normal agent operation. This keeps the capability portable, dependency-free, non-destructive, and compatible with downstream projects.

## Acceptance criteria

1. The capability returns one concise current operational summary, one of three overall states, material issues, and exactly one concrete next safe action for the current repository.
2. Git reporting distinguishes branch, `HEAD`, staged, unstaged, untracked, tracking divergence, and remote freshness without automatically treating every dirty tree as unhealthy or changing Git state.
3. Quality evidence is reported with mode, result, scope binding, and freshness; stale, missing, or blocked required evidence cannot be reused as PASS; a current required FAIL blocks the affected progression and routes to repair rather than an unchanged rerun; and no quality logic is duplicated.
4. Relevant dependency-security evidence is consumed without reperforming analysis; findings and blockers affect health proportionately and likely real exposure retains incident routing.
5. Active or pending-verification incidents prevent HEALTHY, while `DISPROVED` and `RECOVERY_VERIFIED` retain their existing semantics and independent remaining checkpoints.
6. Material status, handoff, specification, decision, memory, review, and research staleness is detected from repository/content mismatch rather than timestamps alone.
7. Task state preserves implemented, validated, reviewed, committed, merged, pushed, released, and deployed distinctions and selects the active task's next checkpoint when applicable.
8. Research integrity flags are surfaced from governed evidence without performing research analysis; material holdout or provenance contamination blocks the affected workflow.
9. Aggregation is multi-dimensional: a focused PASS cannot erase another blocker, a warning is not automatically BLOCKED, and dirty state alone is not determinative; attributable dirty work remains `HEALTHY` when it is fully understood and needs no additional awareness for the named action.
10. Missing optional artifacts or authoritative `NOT_APPLICABLE` checks do not falsely degrade health; unavailable optional evidence that is irrelevant to the named action remains informational, while missing required evidence is classified according to the intended action.
11. The capability remains read-only, does not silently fix or refresh state, and never authorizes or performs commit, merge, push, release, deployment, recovery, or branch deletion.
12. The relationship with `context-resume` is acyclic and preserves detailed context reconstruction, handoff receiving, and existing session-entry policy; untrusted task/handoff context is restored before any gate whose branch, scope, applicability, or checkpoint depends on it.
13. Output remains compact enough to expose repository, result, active task, blocker, stale evidence, and next action to a future external aggregator without implementing MORNING or cross-repository discovery.
14. The implementation adds no dependency, script, scanner, service, database, scheduler, background agent, dashboard, API, CI infrastructure, or unrelated capability.
15. Existing context-resume, quality-gate, task-handoff, incident-recovery, dependency-security-check, debug, code-review, release-check, SDD, research governance, and human approval behaviour remains unchanged.

## Validation scenarios

| ID | Scenario | Expected observable result |
| --- | --- | --- |
| PH-01 | Clean healthy repository: clean synchronized `main`, current FULL PASS, no incident or security finding, and current documentation. | `HEALTHY`; next action is to start normal work through the development workflow. |
| PH-02 | Dirty tree with an active known task. | Reports every dirty category and task attribution. Fully understood attributable work that needs no additional awareness for the named action may remain `HEALTHY`; a non-blocking scope, ownership, or checkpoint concern that materially requires awareness is `ATTENTION`; dirtiness alone never makes it `BLOCKED`. |
| PH-03 | Unknown or unrelated dirty changes. | `ATTENTION` while ownership can safely be established, or `BLOCKED` when mixed/unsafe ambiguity prevents work; next action is to inspect and preserve the unexpected changes before unrelated implementation. |
| PH-04 | Stale quality-gate PASS after relevant content changed. | Does not reuse PASS; reports stale validation and recommends the canonical required gate when needed. |
| PH-05 | Required quality gate is `BLOCKED`. | Overall `BLOCKED`; next action is to resolve the named gate blocker or required environment/evidence through the quality-gate workflow. |
| PH-06 | Dependency-security returns `FINDINGS`. | At least `ATTENTION`, or `BLOCKED` when policy/current progression requires resolution; reports the existing findings without inventing an incident. |
| PH-07 | Required dependency-security evidence is `BLOCKED`. | Overall `BLOCKED` for the affected intended action; next action is to resolve the named evidence blocker through the canonical security check. |
| PH-08 | Active incident. | Overall `BLOCKED`; next action is to continue the current incident-recovery checkpoint, not start new implementation. |
| PH-09 | Incident is `RECOVERY_VERIFIED` but required revalidation or review is pending. | Does not retain the incident as active but reports the independent pending checkpoint; result is not falsely HEALTHY for progression and the next action is the earliest required revalidation/review step. |
| PH-10 | `PROJECT_STATUS` materially contradicts newer Git/project evidence. | Normally `ATTENTION`; `BLOCKED` only when the contradiction creates unsafe ambiguity. Reports the conflict and recommends refresh only after current state is confirmed. |
| PH-11 | Handoff branch, `HEAD`, fingerprint, decision, or validation evidence is stale. | Reports the handoff stale and non-authoritative; next action uses context recovery/verification rather than applying the old handoff. |
| PH-12 | Current branch contradicts the established active-task branch expectation. | `ATTENTION` when safe verification can resolve it; `BLOCKED` when work would risk the wrong branch or mixed state. No automatic switch occurs. |
| PH-13 | Local branch is ahead, behind, or diverged from its tracking ref. | Reports counts and remote freshness clearly, does not pull/rebase/merge automatically, and classifies impact relative to the intended action. |
| PH-14 | Active task is validated and review-ready but not independently reviewed. | Overall may be `HEALTHY` or `ATTENTION` operationally, but the one next action is independent review rather than unrelated new work. |
| PH-15 | Governed research evidence flags protected-holdout contamination. | Overall `BLOCKED` for the affected research workflow; next action follows research/incident governance and does not continue analysis silently. |
| PH-16 | Instruction-only template has structural checks but no executable product test harness. | Honors authoritative `NOT_APPLICABLE`; does not report unhealthy solely because product tests do not exist. |
| PH-17 | Optional non-required evidence is unavailable. | Evidence irrelevant to the named action remains informational and permits `HEALTHY`; relevant non-blocking unavailability that materially requires awareness is `ATTENTION`; optional absence is never automatically `BLOCKED`. |
| PH-18 | Quality/security evidence was current, then branch or relevant content changed. | Explicitly reevaluates freshness and does not reuse the prior result blindly. |
| PH-19 | New session receives an active handoff. | Project health may summarize it, but the next safe action still runs `context-resume` and verifies the handoff before detailed continuation. |
| PH-20 | Existing workflow regression. | Every existing skill and FULL repository check continues to pass; no frozen-layer behaviour, SDD rule, research control, or human approval gate is altered or weakened. |
| PH-21 | Current required quality gate reports `FAIL`. | Overall is `BLOCKED` for the affected progression; the existing failure remains current evidence; the next action returns to `project-dev-cycle` and uses `debug` when diagnosis or repair is requested instead of rerunning the unchanged gate. |
| PH-22 | Active task or handoff context is untrusted while scope-dependent validation is stale or missing. | Runs `context-resume` and verifies branch, task scope, and checkpoint before recommending or invoking the applicable quality/security evidence workflow. |

## Test-design review

- [x] Every acceptance criterion maps to one or more scenarios or a named structural/integration check.
- [x] Clean, dirty-attributable, dirty-unknown, wrong-branch, divergence, stale evidence, missing optional evidence, blocked evidence, incident, recovery, handoff, review, research, and no-product-test cases are covered.
- [x] HEALTHY cannot be inferred from a focused PASS, and BLOCKED cannot be inferred from dirtiness or a warning alone.
- [x] PH-02 and PH-17 each preserve a reachable informational/HEALTHY branch as well as an ATTENTION branch based on actual relevance to the named action.
- [x] Staleness is content/repository-state based and covers branch, `HEAD`, working-tree content, configuration, scope, and governed-record changes.
- [x] Every scenario specifies an observable classification or workflow outcome without prescribing a script, dependency, service, or hidden execution.
- [x] Responsibility boundaries were checked against context-resume, quality-gate, task-handoff, incident-recovery, dependency-security-check, code-review, release-check, project-dev-cycle, and research-experiment.
- [x] Current required quality-gate FAIL and untrusted-context-plus-stale-validation regressions have explicit outcomes and cannot fall through to ATTENTION or premature gate execution.
- [x] The output exposes the compact fields needed by a future external aggregator without adding cross-repository behaviour.
- Reviewer: pre-implementation internal requirement-to-scenario and boundary review completed 2026-09-23; independent review findings for required quality-gate FAIL handling, context-before-scope precedence, ATTENTION aggregation reachability, and review-state freshness were addressed on 2026-09-23. Final confirmation for the current content is reported in the task result so a post-review write-back does not invalidate the reviewed content.
- Unresolved questions: none identified from current repository evidence or the user-provided contract.

## Validation and traceability plan

- Skill structure/frontmatter: bundled `skill-creator` quick validator.
- Specification and scenario coverage: manual review above plus a structural check that PH-01 through PH-22 each have one definition and, after implementation, one recorded passing result.
- Behaviour: manual trace of PH-01 through PH-22 against the completed skill.
- Integration boundaries: focused search and manual audit against the seven focused workflow skills plus SDD, research governance, and approval language.
- Existing regression: validate every repository skill and run the repository-defined FULL quality gate without altering its configured profile.
- Security/reliability contracts: run the existing dependency-security, incident-recovery, and quality-gate structural checks through FULL.
- Documentation and path consistency: repository-wide relative Markdown link validation.
- Whitespace and patch integrity: repository FULL profile plus `git diff --check` evidence.
- Automated product tests: not applicable; this template intentionally has no executable product code or test harness, and an instruction-driven capability does not justify adding one.
- Manual validation and residual risk: classifications depend on agents correctly assessing material relevance and intended action across downstream repositories. The specification constrains that judgment, but no universal deterministic script can prove every project-specific evidence relationship.

### Manual scenario results

| Scenario | Result | Evidence in the implemented capability |
| --- | --- | --- |
| PH-01 | Pass | Defines HEALTHY as no known blocker or material ambiguity with evidence current enough for the named action, then selects normal task entry when no earlier prerequisite exists. |
| PH-02 | Pass | Git inspection distinguishes dirty categories, and aggregation promotes attributable work only when it materially needs awareness; fully understood task work can therefore reach HEALTHY while a non-blocking concern reaches ATTENTION. |
| PH-03 | Pass | Unknown or unrelated changes require ATTENTION, while mixed or unsafe ownership ambiguity becomes BLOCKED; the next-action precedence resolves that ambiguity before unrelated work. |
| PH-04 | Pass | Validation and staleness rules invalidate unbound PASS evidence after relevant content or configuration changes and recommend the owning gate when required. |
| PH-05 | Pass | Required blocked validation is an explicit overall BLOCKED condition and routes to the canonical quality-gate evidence path. |
| PH-06 | Pass | Dependency-security FINDINGS is at least ATTENTION and becomes BLOCKED only when policy or the intended action requires resolution; incident state is not invented. |
| PH-07 | Pass | Required blocked, missing, or stale dependency-security evidence blocks only the affected progression and routes to the owning skill. |
| PH-08 | Pass | Every active or pending-verification incident state makes health BLOCKED and takes first next-action precedence. |
| PH-09 | Pass | RECOVERY_VERIFIED removes only the incident blocker; independent validation, review, operational authority, and workflow checkpoints remain visible and control the next action. |
| PH-10 | Pass | Project-status staleness requires a material contradiction, is normally ATTENTION, and becomes BLOCKED only when it prevents safe interpretation; refresh follows state confirmation. |
| PH-11 | Pass | Repository, branch, HEAD, fingerprint, specification, decision, prerequisite, and validation changes can stale a handoff; the skill refuses to treat it as authoritative and routes a new session through context recovery. |
| PH-12 | Pass | A branch mismatch is classified by safety impact, never repaired automatically, and is resolved before progression when it threatens the active task. |
| PH-13 | Pass | Git reporting includes tracking divergence and remote freshness while explicitly prohibiting fetch, pull, rebase, merge, or branch switching during health inspection. |
| PH-14 | Pass | Task-state rules preserve review-ready as a distinct checkpoint and require the one next action to follow the active task, making independent review precede unrelated work. |
| PH-15 | Pass | Research consumes governed contamination/provenance evidence only; a material flag blocks the affected workflow without inspecting outcomes or continuing analysis. |
| PH-16 | Pass | Validation rules treat authoritative NOT_APPLICABLE, including this instruction-only repository's absent product harness, as non-defective. |
| PH-17 | Pass | Aggregation leaves irrelevant optional unavailability informational so HEALTHY remains reachable, while relevant non-blocking unavailability can become ATTENTION and never automatically BLOCKED. |
| PH-18 | Pass | The staleness model explicitly reevaluates branch, HEAD, covered content, configuration, and scope before reusing quality or security evidence. |
| PH-19 | Pass | The context relationship is acyclic; a new-session handoff still requires context-resume and verification before detailed continuation. |
| PH-20 | Pass | All thirteen repository skills validate, the implementation-state FULL profile passes, frozen skill/spec paths remain unchanged, and no approval, SDD, research, or focused-workflow boundary is weakened. |
| PH-21 | Pass | Validation and aggregation rules classify a current required quality-gate FAIL as BLOCKED, preserve its failure evidence, and route diagnosis/repair through project-dev-cycle and debug instead of an unchanged rerun. |
| PH-22 | Pass | Next-action precedence restores untrusted task/handoff context before any quality/security action whose branch, scope, applicability, or checkpoint depends on that context. |

### Integration audit results

- `context-resume`: unchanged; project health consumes a current Working Context when available and restores untrusted task/handoff context before recommending any scope-dependent gate.
- `quality-gate`: unchanged; project health reports result, mode, binding, and freshness but contains no validation command or check implementation; a current required FAIL blocks the affected progression and returns repair to project-dev-cycle/debug.
- `task-handoff`: unchanged; project health reports existence/freshness while the receiver still uses context-resume and the handoff's own verification contract.
- `incident-recovery`: unchanged; active/pending incident states block health, while project health cannot activate, downgrade, close, recover, or authorize resumption.
- `dependency-security-check`: unchanged; project health consumes its result/risk/freshness without package, vulnerability, provenance, secret, ignore, or install-script analysis.
- `code-review`: unchanged; project health reports only the review checkpoint or existing findings and performs no review.
- `release-check`: unchanged; HEALTHY explicitly does not imply boundary readiness or authorization.
- SDD, research governance, and human approval gates: unchanged; project health selects the earliest existing checkpoint and grants no repository, release, deployment, recovery, or production authority.
- Scope: no frozen skill/spec file, dependency, manifest, script, scanner, service, database, scheduler, dashboard, CI configuration, API, or cross-repository orchestration was added or changed.
