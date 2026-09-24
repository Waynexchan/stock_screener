# Task handoff

> Supporting evidence for one active task. Current repository state and documented decisions outrank this handoff, and both outrank conversational memory. The receiving agent must run `context-resume` and verify every material claim before continuing. Do not include secrets or unnecessary personal information.
>
> Replace every `[evidence label]` placeholder with exactly one of `Verified fact`, `Documented decision`, `Agent inference`, or `Unknown / needs verification` according to the claim's actual source. Do not leave the placeholder in a completed handoff or promote chat-only task content to a verified fact.

## Identity

- **[evidence label] — Task title:** <!-- concise task name -->
- **Agent inference — State:** <!-- COMPLETE_UNCOMMITTED, PARTIAL, REVIEW_READY, BLOCKED, REVIEW_FINDINGS, FIXES_APPLIED, or REVIEW_CONFIRMED -->
- **Verified fact — Created:** <!-- ISO 8601 date/time with timezone -->
- **Verified fact — Repository identity:** <!-- task-handoff-repository-v1;origin=<digest-or-unavailable>;roots=<digest-or-unavailable> -->
- **Unknown / needs verification — Unavailable identity components:** <!-- none, or exact unavailable components/reason -->
- **Verified fact — Repository path hint:** <!-- informational only; never an identity match criterion -->
- **Verified fact — Branch:**
- **Verified fact — HEAD:**
- **Verified fact — Base/start commit:** <!-- exact commit, or move unavailable information to the unknown field -->
- **Verified fact — Working-tree fingerprint:** <!-- task-handoff-worktree-sha256-v1:<lowercase-digest> -->
- **Unknown / needs verification — Unavailable fingerprint:** <!-- none, or unavailable reason; never invent a digest -->

## Objective and scope

- **[evidence label] — Request:**
- **[evidence label] — Included scope:**
- **[evidence label] — Explicitly excluded scope:**
- **Verified fact — Governing specification / acceptance criteria:**

## Work completed and remaining

- **[evidence label] — Completed work:**
- **Verified fact — Relevant files changed:**
- **Verified fact — Specifications/tests created or updated:**
- **[evidence label] — Outstanding work:** <!-- exact remaining work, or none -->
- **Agent inference — Implementation assessment:** <!-- keep distinct from verified completion -->

## Validation

- **Verified fact — Quality-gate mode/result:** <!-- FAST/FULL and PASS/FAIL/BLOCKED/NOT_APPLICABLE, or not run when verified -->
- **Unknown / needs verification — Quality-gate result:** <!-- none, or exact unavailable/uncertain result and reason -->
- **Verified fact — Secret-safe commands and evidence:**
- **Verified fact — Counts/skips where available:**
- **Verified fact — Checks not run and reason:**
- **Verified fact — Covered branch / HEAD / fingerprint:**
- **Verified fact — Freshness:** <!-- current, stale, or not run when verified -->
- **Unknown / needs verification — Validation freshness:** <!-- none, or exact freshness uncertainty and reason -->

## Git state

- **Verified fact — Working tree:** <!-- clean or dirty -->
- **Verified fact — Staged files:**
- **Verified fact — Unstaged files:**
- **Verified fact — Non-ignored untracked files:**
- **Verified fact — Commit state:** <!-- uncommitted, or exact task commit -->
- **Verified fact — Remote freshness/divergence:** <!-- verified evidence only, or none -->
- **Unknown / needs verification — Remote freshness/divergence:** <!-- none, or exact unverified state and reason -->

## Decisions and review evidence

- **Documented decision — Relevant records:** <!-- references, not copied decisions -->
- **Documented decision — Decisions not to reopen without new evidence:**
- **Verified fact — Review result/findings:** <!-- result or severity/location/evidence/remediation for each finding -->
- **Unknown / needs verification:**

## Known risks and issues

- **Verified fact:**
- **Agent inference:**
- **Unknown / needs verification:**

## Active incident / recovery

- **Verified fact — Incident record:** <!-- path/reference, or not applicable -->
- **Verified fact — Incident state and containment:** <!-- current verified state, or not applicable -->
- **Unknown / needs verification — Recovery constraints:** <!-- outstanding integrity, authority, verification, or resumption conditions -->

## Explicitly not done

- <!-- List every applicable unperformed operation: containment, recovery, resumption, validation, review, commit, merge, push, release, deployment, version bump, release check, external validation, branch deletion, etc. -->

## Next safe action

<!-- Exactly one workflow step that does not bypass specification, validation, review, release-check, or Git approval gates. -->
