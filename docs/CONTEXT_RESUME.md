# Behaviour specification: context resume

## Identity and change control

- Specification: `docs/CONTEXT_RESUME.md`
- Revision: 3
- Status: reviewed
- Last updated: 2026-09-22
- Related decision record: none; this capability operationalizes existing repository authority and context-recovery policy.

## Intent and scope

`context-resume` reconstructs a concise, repository-backed Working Context before an AI coding agent continues work in an existing project. Its core rule is:

> Repository state and documented project decisions outrank conversational memory.

The capability is read-only. It establishes what is known, what is decided, what is inferred, what remains unknown, and the next safe action. It does not perform implementation, create or transfer handoffs, diagnose incidents, introduce a quality gate, or authorize repository mutations.

### Trigger conditions

Use the skill when:

- a new agent or session enters an existing repository;
- the user asks to continue, resume, or pick up previous work;
- conversation context may be incomplete or compressed;
- another agent or an existing handoff may have changed the project; or
- the agent is uncertain whether conversational memory is current.

Do not rerun it repeatedly during the same unchanged task when the applicable instructions, branch, HEAD, working tree, and relevant project records have not materially changed and context remains intact.

## Behavioural contract

### Context reconstruction

When available, inspect evidence in approximately this order, adapting paths and names to the project without inventing missing records:

1. root `AGENTS.md`;
2. more-specific applicable agent instructions;
3. current project status, commonly `PROJECT_STATUS.md`;
4. decision records, commonly `DECISIONS.md`;
5. durable project memory, commonly `PROJECT_MEMORY.md`;
6. business-rule records, commonly `BUSINESS_RULES.md`;
7. research governance and experiment records when the task or repository is research-related;
8. active incident records, recovery constraints, and applicable operational runbooks when relevant;
9. current Git branch and HEAD;
10. staged, unstaged, and untracked working-tree state;
11. recent relevant commits;
12. the current staged and unstaged diff;
13. the latest available validation or test evidence and the repository's canonical validation guidance; and
14. relevant task, specification, and existing handoff records.

Only applicable instruction files are required. Missing optional status, decision, memory, business-rule, research, incident, task, specification, validation, or handoff records do not cause failure. Report material absences as unavailable or unknown, and do not create placeholder artifacts solely to complete context recovery.

Inspect only enough history and content to reconstruct the current task safely. Follow repository policy when remote freshness matters; do not describe remote state as current without evidence.

### Source-of-truth hierarchy and conflicts

Applicable system, user, and repository instructions retain their normal authority. For factual claims about project state, use this evidence precedence:

1. current verified repository and filesystem state, including branch, HEAD, tracked files, and staged, unstaged, or untracked changes;
2. explicit documented decisions;
3. the current project status and governing specifications;
4. relevant Git history;
5. current validation evidence bound to the exact branch, `HEAD`, configuration, and working-tree content it covered;
6. previous handoff documentation; and
7. conversational memory.

The hierarchy does not permit silent conflict resolution. When sources disagree, identify the conflict, describe the evidence on each side, use the higher-precedence evidence for the provisional Working Context, and mark any material ambiguity for verification. Existing local code proves that work exists; it does not by itself prove that the work is approved, validated, committed, or complete. A documented rejection or superseding decision must not be reopened solely because chat memory says otherwise.

Apply the hierarchy to the kind of claim being evaluated. For validation status, fresh content-bound evidence for the current state outranks validation summaries in project status, Git history, handoffs, or chat. Validation evidence does not override a documented decision or governing specification, prove review or release readiness, or authorize a repository operation.

For incident status, a current `DISPROVED` record is a terminal false-alarm disposition, not an active incident and not a recovered incident. The Working Context reports the disproving evidence reference, lifted incident-only constraints, any independent constraints still in force, and the normal-workflow checkpoint that may resume. It must not retain stale `SUSPECTED` restrictions or relabel `DISPROVED` as `RECOVERY_VERIFIED`.

Treat `PROJECT_STATUS.md` as potentially stale. Compare its branch, HEAD, dates, completed items, and validation claims with the current repository and relevant commits. Treat validation evidence as applicable only to the commit or working-tree state it actually covers.

### Required output

Produce one concise **Working Context** with these fields:

- Current objective
- Current production/baseline state
- Active task/change
- Current branch and HEAD
- Working tree state
- Important business/domain rules
- Decisions that must not be revisited without new evidence
- Known risks/issues
- Active incident/recovery state
- Latest validation state
- Actions already completed
- Actions explicitly not completed
- Next safe action

Label substantive entries as one of:

- **Fact** — directly verified from current repository, filesystem, Git, or validation evidence;
- **Documented decision** — explicitly recorded in an authoritative decision or governed record;
- **Inference** — a reasoned interpretation supported by named evidence but not explicitly recorded; or
- **Unknown / needs verification** — unavailable, stale, conflicting, or unsupported information.

Do not fabricate values to fill the structure. Use `Unknown / needs verification` when the evidence does not establish an answer. Explicitly distinguish committed history from staged, unstaged, and untracked work, and distinguish completed actions from planned, attempted, or unverified actions.

## Acceptance criteria

1. The skill is discoverable for every trigger condition and excludes repeated invocation during an unchanged, uninterrupted task.
2. Repository evidence and documented decisions take precedence over conversational memory without overriding higher-level instruction authority.
3. The skill follows the specified reconstruction order approximately and adapts to equivalent project paths.
4. Missing optional files never cause context reconstruction to fail and are not fabricated.
5. Conflicts and potentially stale records are surfaced explicitly rather than silently reconciled.
6. Dirty state is reported by staged, unstaged, and untracked category as applicable, and local work is not described as committed.
7. Validation claims are tied to the repository state they cover; fresh content-bound evidence controls the current validation status, while absent, stale, or conflicting evidence is labelled unknown or stale and cannot imply review or release readiness.
8. Research governance and holdout or experiment decisions are preserved when relevant.
9. The Working Context includes every required field and uses the four evidence labels.
10. The skill remains read-only and does not add quality-gate, task-handoff, incident-recovery, dependency, or unrelated workflow behaviour.
11. An active incident or incomplete recovery is surfaced with its state, containment and resumption constraints, record reference, uncertainty, and next safe action; context recovery never declares the incident resolved.
12. A current `DISPROVED` record is reported as a terminal false alarm with its evidence and constraint disposition; it is neither treated as active nor described as recovered.

## Validation scenarios

| ID | Scenario | Repository/chat evidence | Expected observable result |
| --- | --- | --- | --- |
| CR-01 | Normal resume | `AGENTS.md`, `PROJECT_STATUS.md`, and `DECISIONS.md` exist; working tree is clean. | Produces a compact, labelled Working Context that reflects the clean branch, current objective, decisions, validation evidence, and next safe action. |
| CR-02 | Missing optional files | `PROJECT_MEMORY.md` and/or `BUSINESS_RULES.md` do not exist. | Continues safely, reports material missing context as unavailable or unknown, and fabricates nothing. |
| CR-03 | Chat conflicts with repository | Chat says feature A is active; documented repository decision rejects feature A. | Uses the rejection provisionally, surfaces the conflict, and does not treat chat memory as current evidence. |
| CR-04 | Dirty working tree | Staged, unstaged, or untracked changes exist. | Reports each applicable category and does not imply the changes are committed, validated, or safe to overwrite. |
| CR-05 | Previous agent stopped before commit | Implementation exists in the working tree but no commit contains it. | Identifies local uncommitted implementation separately from completed/committed work and marks its validation/completion status accurately. |
| CR-06 | Stale project status | `PROJECT_STATUS.md` names an older HEAD or omits newer relevant commits. | Flags probable staleness, reconciles against current Git/files, and reports the conflict and any remaining uncertainty. |
| CR-07 | Compressed or incomplete conversation | Chat contains little usable context. | Reconstructs a usable Working Context from repository evidence alone and labels unsupported objective details unknown or inferred. |
| CR-08 | Research project | Research governance and an experiment ledger define holdout use or frozen research decisions. | Preserves those governed decisions, reports their status, and does not reopen or contaminate the holdout based on chat memory. |
| CR-09 | Validation conflict | Project status or a handoff reports PASS for earlier content, while fresh content-bound validation for the current state reports FAIL or BLOCKED. | Reports the current validation result, surfaces the stale summary conflict, and does not infer review, release, or authorization readiness. |
| CR-10 | Active incident | An incident record reports `CONTAINED` or `RECOVERED_PENDING_VERIFICATION`, while chat or stale status says normal work may continue. | Surfaces the active incident and its constraints, trusts current repository and incident evidence over chat, and names incident verification or authorized resumption as the next safe action. |
| CR-11 | Disproved incident after session transfer | A durable incident record was `SUSPECTED`, then current read-only evidence and the updated record establish `DISPROVED`. | Reports the terminal false alarm, evidence reference, lifted and remaining constraints, and resumable checkpoint; does not preserve stale incident restrictions or claim recovery occurred. |

## Test-design review

- [x] Every acceptance criterion is covered by at least one scenario or an explicit structural check.
- [x] Normal, missing-data, conflict, dirty-state, stale-state, validation-conflict, active-incident, disproved-incident, incomplete-context, and research-governance risks are covered.
- [x] Expected results describe observable agent behaviour rather than wording or internal implementation.
- [x] The scenarios do not introduce excluded capabilities.
- [x] The specification does not duplicate Git approval, development, research, or release policy already owned elsewhere.
- Reviewer: revision 1 internal requirement-to-scenario review completed 2026-09-19; revision 2 validation-precedence changes and revision 3 false-alarm recovery semantics were independently reviewed and approved by the user on 2026-09-22.

## Validation and traceability

- Skill structure/frontmatter: bundled `skill-creator` quick validator.
- Documentation and path consistency: manual inspection and repository search.
- Behaviour: manual trace of CR-01 through CR-11 against the completed skill.
- Whitespace and patch integrity: `git diff --check`.
- Repository tests: none currently exist; no new dependency or test harness is planned for this instruction-only capability.

### Manual scenario results

| Scenario | Result | Evidence in the implemented skill |
| --- | --- | --- |
| CR-01 | Pass | Defines the ordered recovery workflow, clean/dirty Git inspection, evidence labels, and complete Working Context structure. |
| CR-02 | Pass | States that optional records may be absent, recovery must continue, and missing content must not be invented. |
| CR-03 | Pass | Places documented decisions above conversation, requires the disagreement to be surfaced, and prohibits reopening a rejection from chat alone. |
| CR-04 | Pass | Requires staged, unstaged, and untracked state to be distinguished and reported. |
| CR-05 | Pass | States that local code does not prove approval, validation, commit, or completion and separates committed from local work. |
| CR-06 | Pass | Requires status branch, HEAD, dates, completed items, and validation claims to be checked against current files and Git. |
| CR-07 | Pass | Makes repository evidence sufficient for recovery and requires unsupported details to remain unknown rather than fabricated. |
| CR-08 | Pass | Inspects research governance when relevant and retains research restrictions and decisions in the Working Context. |
| CR-09 | Pass | Gives fresh validation evidence claim-specific precedence over stale summaries while preventing validation from replacing specifications, review, release readiness, or authorization. |
| CR-10 | Pass | Requires relevant incident records and recovery constraints to be inspected and exposes the active state in the Working Context without performing or closing recovery. |
| CR-11 | Pass | Treats `DISPROVED` as a terminal false alarm, reports its evidence and constraint disposition, and prevents stale `SUSPECTED` or false recovery claims after transfer. |

### Repository check results

- Bundled quick validation for all eleven repository skills: pass in Python UTF-8 mode.
- Relative Markdown link resolution: 23 targets pass before final evidence write-back.
- `git diff --check`: pass.
- Automated repository tests: not applicable; this template intentionally has no test harness or executable product code.
