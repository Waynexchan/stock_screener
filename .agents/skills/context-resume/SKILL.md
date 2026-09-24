---
name: context-resume
description: Reconstruct a concise repository-backed Working Context when entering or resuming an existing project after a new session, time away, context compression, prior-agent work, or uncertainty about chat freshness. Do not rerun repeatedly during the same unchanged task.
---

# Context resume

Reconstruct project state before continuing work. The governing principle is:

> Repository state and documented project decisions outrank conversational memory.

This skill is read-only. It reports current evidence and uncertainty; it does not authorize or perform implementation, Git mutation, validation gates, handoff creation, incident recovery, or other workflow actions. See the [context-resume specification](../../../docs/CONTEXT_RESUME.md) for the behavioural contract and validation scenarios.

## When to run

Use this skill when a new agent or session enters an existing repository, the user asks to continue or resume work, conversation context may be incomplete or compressed, another agent may have changed the project, or chat memory may be stale.

Do not rerun it during the same uninterrupted task when the applicable instructions, branch, HEAD, working tree, and relevant records have not materially changed. Reuse the current Working Context until one of those conditions changes or context becomes uncertain.

## 1. Reconstruct from repository evidence

Read only what is needed to recover the active project and task. Use equivalent project-specific paths when documented. When available, inspect in approximately this order:

1. root `AGENTS.md`;
2. more-specific agent instructions applicable to the working area;
3. current project status, commonly `PROJECT_STATUS.md`;
4. decision records, commonly `DECISIONS.md`;
5. durable project memory, commonly `PROJECT_MEMORY.md`;
6. business-rule records, commonly `BUSINESS_RULES.md`;
7. research governance, hypotheses, experiment ledgers, and frozen plans when relevant;
8. active incident records, recovery constraints, and applicable operational runbooks when relevant;
9. current Git branch and HEAD;
10. staged, unstaged, and untracked working-tree state;
11. recent relevant commits;
12. staged and unstaged diffs;
13. latest available validation or test evidence and canonical validation guidance; and
14. relevant task, specification, and existing handoff records.

Only applicable agent instructions are required. Missing optional records do not cause failure. Mark material absences unavailable or unknown; do not invent their contents or create placeholders merely to complete recovery.

Follow repository policy when remote freshness matters. Do not claim a remote or tracking ref is current without evidence. Do not rerun validation solely to fill the summary; report the latest evidence and identify verification as a next action when necessary.

## 2. Reconcile conflicts and stale records

Applicable system, user, and repository instructions retain their normal authority. For factual project state, use this evidence precedence:

1. current verified repository and filesystem state;
2. explicit documented decisions;
3. current project status and governing specifications;
4. relevant Git history;
5. current validation evidence bound to the exact branch, `HEAD`, configuration, and working-tree content it covered;
6. previous handoff documentation; and
7. conversational memory.

Never silently resolve a conflict. State what disagrees, cite the evidence on each side, use the higher-precedence evidence provisionally, and mark material ambiguity for verification. Current files show what exists, but local code alone does not prove that work is approved, validated, committed, or complete. A documented rejection or superseding decision is not reopened solely because chat memory says otherwise.

Apply the hierarchy to the kind of claim being evaluated. For validation status, fresh content-bound evidence for the current state outranks validation summaries in project status, Git history, handoffs, or chat. Validation evidence does not override a documented decision or governing specification, prove review or release readiness, or authorize a repository operation.

For incident status, treat a current `DISPROVED` record as a terminal false-alarm disposition, not an active incident and not a recovered incident. Report the disproving evidence reference, lifted incident-only constraints, any independent constraints that remain, and the normal-workflow checkpoint that may resume. Do not carry stale `SUSPECTED` restrictions forward or describe `DISPROVED` as `RECOVERY_VERIFIED`.

Treat project status as a snapshot that may be stale. Compare its branch, HEAD, dates, completed items, and validation claims with current files and Git history. Tie validation evidence to the commit or working-tree state it covered. Distinguish committed history from staged, unstaged, and untracked work, and distinguish completed actions from planned, attempted, or unverified ones.

## 3. Produce the Working Context

Return one concise summary using this structure. Prefix each substantive value or item with exactly one evidence label: **Fact**, **Documented decision**, **Inference**, or **Unknown / needs verification**.

```markdown
## Working Context

- Current objective:
- Current production/baseline state:
- Active task/change:
- Current branch and HEAD:
- Working tree state:
- Important business/domain rules:
- Decisions that must not be revisited without new evidence:
- Known risks/issues:
- Active incident/recovery state:
- Latest validation state:
- Actions already completed:
- Actions explicitly not completed:
- Next safe action:
```

Use **Fact** only for directly verified repository, filesystem, Git, or validation evidence. Use **Documented decision** only for an explicit governed choice. Use **Inference** for a reasoned interpretation supported by named evidence. Use **Unknown / needs verification** for missing, stale, conflicting, or unsupported information.

Do not fabricate a value to fill the structure. Keep the result compact while retaining material conflicts, dirty state, research restrictions, validation limitations, and the single next action needed to continue safely. After reporting, route subsequent work through the repository's applicable workflow and approval rules.
