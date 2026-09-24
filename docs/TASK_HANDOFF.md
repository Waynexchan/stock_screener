# Behaviour specification: task handoff

## Identity and change control

- Specification: `docs/TASK_HANDOFF.md`
- Revision: 2
- Status: reviewed
- Last updated: 2026-09-22
- Related decision record: none; this capability operationalizes task transfer without changing repository authority, validation, review, or Git approval policy.

## Intent and scope

`task-handoff` creates or consumes a concise, repository-grounded description of one active task at a meaningful work boundary so another agent or session can continue safely without relying on chat history.

Its governing rule is:

> Current repository state and documented decisions outrank the handoff, and both outrank conversational memory.

A handoff is supporting evidence, not repository state, durable project knowledge, validation, review, or authorization. A receiving agent must run `context-resume`, inspect the handoff, verify the current repository state, surface conflicts, and then choose the next safe action.

### Trigger conditions

Use the capability when at least one meaningful transfer condition applies:

- an agent finishes a meaningful work session and another agent or session will continue;
- implementation is complete locally but uncommitted;
- implementation is ready for independent review;
- implementation is partial or blocked;
- a reviewer is transferring findings to a fixing agent;
- review fixes have been applied and require confirmation;
- independent review has passed and the task is waiting for an explicitly approved Git boundary;
- context compression, restart, or conversation loss makes continuation risky; or
- the user explicitly asks another agent or session to continue.

Do not create a handoff after every trivial edit, during an unchanged uninterrupted session, or merely to restate information already owned by an authoritative repository artifact. The capability is optional; the normal development workflow does not require multiple agents.

### In scope

- classifying the current state of one task;
- recording concise, source-linked task, Git, validation, decision, risk, and next-action evidence;
- distinguishing verified facts, documented decisions, agent inference, and unknown information;
- creating an ephemeral rendered handoff or, when cross-session persistence is needed, one transient active handoff file;
- checking whether a received handoff is current, stale, malformed, missing, or in conflict with higher-authority evidence; and
- preserving every existing specification, quality-gate, review, release-check, and Git approval boundary.

### Out of scope

- replacing `context-resume`, repository inspection, project status, project memory, decision records, specifications, tests, or quality-gate evidence;
- certifying technical correctness, production safety, merge readiness, release readiness, or deployment readiness;
- authorizing or performing a commit, merge, push, release, deployment, branch deletion, force push, or destructive cleanup;
- performing incident recovery, establishing recovery verification, dependency security, project health, orchestration, messaging, agent databases, or unrelated workflow functionality; a handoff may reference and transfer an incident task without owning those actions; and
- retaining a permanent archive of routine handoffs.

## Responsibility boundaries

- `PROJECT_STATUS` owns the longer-lived project snapshot and milestones.
- `PROJECT_MEMORY` owns stable, non-normative domain and operational context plus pointers to authoritative records.
- `DECISIONS` owns durable choices and rationale that must survive the task.
- Specifications and tests own required behaviour, rules, invariants, and regression protection.
- `context-resume` reconstructs current state from repository evidence and resolves authority conflicts.
- `quality-gate` executes configured checks and supplies deterministic validation evidence for the current content.
- `incident-recovery` owns incident activation, containment coordination, durable incident evidence, recovery planning, and verified resumption.
- `code-review` supplies independent technical findings or a review conclusion.
- `release-check` evaluates readiness for a named operational boundary.
- `task-handoff` describes the state and next safe action of one active task at one transfer boundary and references, rather than copies, durable records.

Material knowledge discovered during a task must be written to its authoritative artifact before handoff when practical. A handoff must not become the only durable copy of a behavioural rule, decision, or long-lived project fact.

## Task states

Every valid handoff uses exactly one of these states:

- **COMPLETE_UNCOMMITTED** — The implementation appears complete in the local working tree and no task commit contains it, but required pre-review validation is missing, stale, failed, blocked, or otherwise does not establish `REVIEW_READY`. The handoff must state the validation condition and must not imply readiness for review or merge.
- **PARTIAL** — Work has started but one or more specified acceptance criteria, tests, implementation items, or required records remain incomplete. The handoff identifies completed and outstanding work without claiming completion.
- **REVIEW_READY** — The specification, planned implementation, and required pre-review checks appear complete; the repository-defined FULL quality gate passed for the identical branch, `HEAD`, and working-tree fingerprint; and independent review is the next action. This state does not mean ready to commit, merge, push, release, or deploy.
- **BLOCKED** — Work cannot proceed safely because of a known blocker. The handoff records the blocker, evidence, attempted safe checks, and the authority or state change required to continue. A failed quality gate may be `BLOCKED` when it prevents safe progress; an actionable failure that can still be fixed within the task may remain `PARTIAL`.
- **REVIEW_FINDINGS** — An independent reviewer completed review and is handing actionable findings to a fixing agent. Each finding includes severity, location or affected surface, evidence or reasoning, and remediation direction; the handoff does not claim that findings are resolved.
- **FIXES_APPLIED** — Review findings have been addressed, affected checks and the repository-required FULL quality gate have been rerun successfully for the identical current content, and review confirmation is the next action. This state does not itself close the review or authorize later Git operations.
- **REVIEW_CONFIRMED** — Independent review has passed or confirmed the fixes with no unresolved finding that blocks the next intended boundary, and required validation remains current for the identical content. The Git section states whether the work is uncommitted or committed and names the next boundary that still requires its own readiness evidence and explicit approval. This state does not authorize commit, merge, push, release, deployment, or branch deletion.

Do not use vague states such as `DONE`, `COMPLETE`, or `READY` that conceal whether work is committed, reviewed, merged, pushed, released, or deployed. Committed versus uncommitted state remains an explicit Git fact rather than an implication of the task state.

## Handoff contract

A handoff must remain concise but contain enough evidence for safe continuation. Use the standard template and include the following sections.

### Identity

- task title and objective;
- handoff state;
- repository identity;
- repository-root path as an informational hint only;
- creation date/time with timezone;
- current branch and `HEAD`;
- relevant base or start commit when known; and
- working-tree fingerprint and fingerprint method/version.

### Current task and scope

- what the user requested;
- scope intentionally included;
- scope explicitly excluded; and
- governing specification, acceptance criteria, task record, or review reference.

### Work completed and remaining

- implemented or reviewed changes;
- relevant files changed;
- specifications and tests created or updated;
- important architectural choices, referencing durable decisions rather than duplicating them; and
- exact outstanding work for `PARTIAL`, `BLOCKED`, or `REVIEW_FINDINGS` states.

### Validation

- quality-gate mode and `PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`, or not-run result;
- secret-safe commands and concise evidence, including meaningful counts where available;
- checks not run and why;
- the branch, `HEAD`, and fingerprint covered by the evidence; and
- whether the validation is current, stale, or unknown.

Never infer `PASS` from missing output, an old run, partial checks, or agent confidence. `REVIEW_READY`, `FIXES_APPLIED`, and `REVIEW_CONFIRMED` require a current repository-defined FULL `PASS`.

### Git state

- clean or dirty working tree;
- staged, unstaged, and non-ignored untracked files by category;
- committed versus uncommitted distinction;
- task commit identifier when one exists; and
- divergence or remote freshness only when verified.

### Decisions, evidence, risks, and omissions

- relevant durable decision references;
- decisions made during the task and where they were recorded;
- decisions that must not be reopened without new evidence;
- known risks, assumptions, edge cases, suspected defects, and environment limitations;
- explicit unknowns; and
- an **Explicitly not done** section whenever any applicable operation remains unperformed, including commit, review, merge, push, release, deployment, version bump, release check, or external validation.

### Next safe action

State one recommended next workflow step, such as continue implementation, diagnose a failure, rerun FULL, perform independent review, confirm fixes, or request human approval. The recommendation must respect current evidence and must not bypass specification, validation, review, release-check, or Git approval gates.

## Evidence classification

Every substantive claim that could affect continuation must be identifiable as one of:

- **Verified fact** — directly checked against the current repository, filesystem, Git state, or fresh validation evidence;
- **Documented decision** — explicitly recorded in an authoritative decision or governed record;
- **Agent inference** — a reasoned interpretation supported by named evidence but not directly established; or
- **Unknown / needs verification** — missing, stale, malformed, conflicting, or unsupported information.

Do not describe local completion as production safety, gate success as independent review, or implementation completion as commit/merge/push completion. When a concise section contains several claims of different types, label individual bullets rather than applying one ambiguous label to the whole section.

Task titles, requests, included or excluded scope, completed work, and outstanding work do not have a universal evidence class. Their labels must reflect their actual source: current repository evidence may be a **Verified fact**, governed records may establish a **Documented decision**, chat-only interpretation normally remains an **Agent inference**, and missing or conflicting scope is **Unknown / needs verification**. The standard template therefore uses a required `[evidence label]` placeholder for these fields; a completed handoff must replace every placeholder with exactly one supported label.

## Persistent and ephemeral lifecycle

The standard format lives at `templates/HANDOFF.md`.

- For an immediate transfer where the rendered response will be reliably delivered, the agent may emit the standard handoff without creating a file.
- For a restart, new conversation, context-loss risk, or another transfer that must not depend on chat history, first inspect the canonical index manifest. If any tracked root path is filesystem-equivalent to `HANDOFF.md`, do not write the default path: report persistent default storage unavailable and return the rendered handoff or request an explicit project-specific location. Otherwise write the current handoff to the repository-root `/HANDOFF.md`.
- `/HANDOFF.md` is transient local task state and is ignored by Git by default. It must not be committed routinely.
- There is only one default active handoff. Do not create an automatic archive or a directory of historical handoffs.
- Replace `/HANDOFF.md` only when it represents the same active task at a newer meaningful boundary. If an existing unconsumed handoff appears to concern another task, do not overwrite it silently; surface the conflict and obtain direction.
- Once a handoff is no longer active, remove or replace it only with appropriate user awareness. Durable facts, decisions, specifications, and validation records must already live in their authoritative locations.
- A project with a demonstrated cross-machine or audit requirement may define a tracked task-specific handoff location, but that is an explicit project choice rather than the template default.

The active handoff is current only provisionally. Its metadata and fingerprint identify the repository state it describes; the receiving agent determines whether that evidence still matches.

## Safe Git bootstrap and process isolation

Repository identity and fingerprint commands use this shared bootstrap. It permits a repository-specific protected `safe.directory` value without trusting ambient Git redirection or writing persistent configuration.

1. Start from the repository candidate supplied by the current workspace and `context-resume`. Resolve the candidate to a canonical absolute filesystem path without invoking a shell expansion. Do not discover it from `GIT_DIR`, `GIT_WORK_TREE`, or another ambient Git variable.
2. Build a child-process environment that removes `GIT_DIR`, `GIT_WORK_TREE`, `GIT_COMMON_DIR`, `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY`, `GIT_ALTERNATE_OBJECT_DIRECTORIES`, `GIT_NAMESPACE`, `GIT_REPLACE_REF_BASE`, `GIT_SHALLOW_FILE`, `GIT_GRAFT_FILE`, `GIT_CEILING_DIRECTORIES`, `GIT_DISCOVERY_ACROSS_FILESYSTEM`, `GIT_CONFIG_SYSTEM`, `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_COUNT`, every `GIT_CONFIG_KEY_*` and `GIT_CONFIG_VALUE_*` variable, `GIT_EXTERNAL_DIFF`, and `GIT_DIFF_OPTS`.
3. In that cleaned environment set `LC_ALL=C`, `LANG=C`, `GIT_PAGER=cat`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_ATTR_NOSYSTEM=1`, `GIT_NO_REPLACE_OBJECTS=1`, `GIT_OPTIONAL_LOCKS=0`, and `GIT_CONFIG_GLOBAL` to a zero-byte temporary file outside the repository. The temporary path never enters an identity or fingerprint payload.
4. With the child process working directory set to the canonical candidate, run the semantic argument array `git -c safe.directory=<canonical-candidate> rev-parse --show-toplevel`. Canonicalize the returned path and require it to equal the candidate exactly under the filesystem's path-comparison rules.
5. Define `git-safe` for the remaining protocol as the argument prefix `git -c safe.directory=<verified-root>` executed from that verified root with the same cleaned environment.

If the candidate is unavailable, escapes the intended workspace through resolution, the verification command fails, or the returned root differs, repository identity and fingerprint are unavailable. Never use `safe.directory=*`, never persist a global `safe.directory`, and never accept an ambient repository/index/object-directory override merely to make the command succeed.

## Repository identity

Use repository identity protocol `task-handoff-repository-v1`. It identifies a Git repository independently of the absolute checkout path and must be recorded with its protocol version.

### Identity inputs

1. Use the verified repository root from the safe bootstrap and record its normalized absolute path only as a non-authoritative path hint. A checkout moved or cloned to another path does not create an identity mismatch.
2. Read the stored local `origin` URL without rewrite processing by running `git-safe config --local --no-includes --get-all remote.origin.url`. Do not use `git remote get-url`, because `url.*.insteadOf` can rewrite its output. Exactly one value is accepted; zero values make the origin component unavailable and multiple values make it ambiguous/unavailable. Remove user information, credentials, query strings, and fragments before any persistence or hashing.
3. Canonicalize a network remote as `<lowercase-host>[:<non-default-port>]/<repository-path>`:
   - convert SCP-like `[user@]host:path` syntax to `host/path`;
   - discard the transport scheme and user information so equivalent SSH and HTTPS URLs compare consistently;
   - use `/` separators, collapse repeated separators, remove leading/trailing separators, and remove one terminal `.git` suffix; and
   - preserve repository-path case because not every Git host is case-insensitive.
4. Hash the UTF-8 bytes of the canonical remote with SHA-256 and store only the lowercase hexadecimal digest as `origin_digest`. A local-path or `file://` remote is not a stable network identity and is treated as unavailable for this field.
5. Determine shallowness with `git-safe rev-parse --is-shallow-repository`. When the result is exactly `false`, run `git-safe rev-list --max-parents=0 HEAD`, lowercase and ASCII-sort the returned full object IDs, join them with a single LF and no trailing LF, and SHA-256 hash the ASCII bytes. Store the lowercase hexadecimal digest as `root_set_digest`. When the result is `true`, unsupported, or ambiguous, or before an initial commit exists, record this component as unavailable rather than treating the shallow boundary or filesystem path as a history root.

Serialize the displayed identity as:

```text
task-handoff-repository-v1;origin=<digest-or-unavailable>;roots=<digest-or-unavailable>
```

### Identity comparison

- When both sides have `origin_digest`, they must match. Different origin digests are a repository mismatch even when history roots overlap, unless higher-authority evidence explicitly establishes an intentional remote migration or fork transfer.
- When both sides have `root_set_digest`, they must also match. A mismatch indicates different or rewritten reachable history and requires reconciliation.
- When neither side has a usable `origin_digest`, matching available root-set digests are the fallback identity.
- When only one side has a usable origin, matching available root-set digests may establish the fallback match, but remote identity remains explicitly unverified.
- When no comparable component is available, repository identity is `Unknown / needs verification`; do not claim a match.

Never persist a raw credential-bearing remote URL. The absolute repository path is diagnostic context only and is never a match criterion.

## Content-sensitive fingerprint

Use fingerprint protocol `task-handoff-worktree-sha256-v1` and record that exact identifier beside the lowercase hexadecimal digest. Implementations must hash bytes according to this section rather than a shell-rendered or platform-newline-dependent transcription.

### Canonical Git inputs

Use `git-safe` and the cleaned environment from the shared bootstrap for every command in this section. Capture NUL-delimited stdout as raw bytes without decoding or newline conversion. Do not use `git diff`, patch text, text conversion, external diff tools, or configured diff drivers as fingerprint input.

Read the repository object format with:

```text
git-safe rev-parse --show-object-format
```

Only `sha1` and `sha256` are supported by version 1. Any other, missing, or contradictory result makes the fingerprint unavailable.

Enumerate every Git index entry while preserving sparse-index directory entries with:

```text
git-safe -c core.quotepath=false -c core.precomposeunicode=false ls-files --stage --sparse -z
```

Parse each NUL-delimited entry as `<mode> SP <object-id> SP <stage> TAB <raw-path-bytes>`. Validate the mode, full lowercase object ID, and stage `0` through `3`; preserve all conflict stages. An entry with sparse-directory mode `040000` makes the fingerprint unavailable. Sort the remaining entries first by unsigned lexicographic raw path bytes and then by numeric stage. The index entry records staged content and mode independently of diff presentation.

Before writing persistent default storage, compare the unique tracked root paths from this manifest with `HANDOFF.md` under the verified filesystem's path-comparison rules. Any exact or filesystem-equivalent tracked collision makes the default persistent path unavailable and prohibits writing it. The ordinary fingerprint continues to include that tracked path; it must never exclude tracked repository content merely to avoid recursion.

Independently enumerate index path flags with:

```text
git-safe -c core.quotepath=false -c core.precomposeunicode=false ls-files -v -z
```

Parse each NUL-delimited flag record as one ASCII tag byte, one ASCII space, and raw path bytes. Uppercase the tag for comparison because `-v` lowercases tags for assume-unchanged entries. A resulting tag `S` indicates skip-worktree and makes the fingerprint unavailable. Require the flag-record path set to match the unique non-directory path set from the stage manifest exactly; missing, duplicate, extra, or malformed flag records make the fingerprint unavailable. Other valid tags do not enter the payload because the protocol hashes the index and filesystem bytes directly.

For every unique index path, inspect the working-tree object directly without Git filters or attribute-driven conversion:

- `missing` when no filesystem entry exists;
- `file` with the exact byte length, raw 32-byte SHA-256 of the file bytes, and an executable marker of `1` or `0` when owner-execute semantics are supported, otherwise `N`;
- `symlink` with the exact raw link-target bytes obtained without following the link; or
- unavailable for a gitlink/submodule, sparse or skip-worktree entry, special filesystem object, unreadable file, or platform API that cannot obtain the required bytes safely.

Sort tracked worktree entries by unsigned lexicographic raw path bytes. Reading the entire tracked worktree is intentional: together with the separately recorded `HEAD` and canonical index manifest, it captures staged and unstaged content without relying on a configured textual diff.

Enumerate untracked paths using repository-owned `.gitignore` files only:

```text
git-safe -c core.quotepath=false -c core.precomposeunicode=false ls-files --others --exclude-per-directory=.gitignore -z
```

Do not use `--exclude-standard`: repository-local `.git/info/exclude`, a user's global ignore file, and `core.excludesFile` must not affect the result. Treat each NUL-delimited path as the raw repository-relative Git path bytes returned by the command. Git repository paths use `/` separators. After the tracked-path collision check has established that the reserved active path is untracked, exclude the exact root path bytes `HANDOFF.md` before sorting, even if repository ignore configuration is missing or broken. Sort the remaining paths by unsigned lexicographic byte order. Every enumerated item must resolve within the repository to a regular file; otherwise the fingerprint is unavailable. Record its exact byte length and raw 32-byte SHA-256 content digest.

Within this protocol, **repository-visible untracked content** means precisely the paths returned by that command after the defensive `HANDOFF.md` exclusion. This is intentionally narrower and more reproducible than a user's checkout-specific `--exclude-standard` view.

For every Git command, a nonzero exit, unexpected stderr that makes the result untrustworthy, external mutation, malformed output, or inability to capture raw bytes makes the fingerprint unavailable rather than permitting a guessed value.

### Configuration isolation

Version 1 uses Git plumbing only for object format, index entries, index flags, and path enumeration; it hashes worktree file and symlink bytes directly. Consequently `diff.orderFile`, `diff.indentHeuristic`, `diff.submodule`, `core.attributesFile`, `.gitattributes` diff drivers, textconv, external diff commands, diff algorithms, color, prefixes, hunk context, and rename detection do not participate in the protocol.

The safe bootstrap suppresses injected repository/index/object paths, protected-configuration loss, system/global configuration, system attributes, and replace objects; the commands fix raw path quoting and Unicode precomposition behaviour while retaining local configuration required to locate the verified worktree and object database. Local diff and attribute settings cannot affect the selected plumbing/file-byte inputs. Skip-worktree and sparse-index state are rejected explicitly. If an implementation detects another local configuration value, repository extension, hook, filesystem monitor, clean/smudge process, replace-object rule, or platform behaviour that can alter an input and cannot be neutralized or bypassed, the fingerprint result is unavailable. It must not emit a different digest and call the handoff stale.

### Canonical payload

Define `u64(n)` as an unsigned 64-bit big-endian integer and `frame(tag, data)` as the one-byte ASCII `tag`, followed by `u64(length(data))`, followed by the exact `data` bytes.

Construct the payload in this order:

```text
ASCII("TASK-HANDOFF-WORKTREE-SHA256-V1\0")
frame("O", ASCII(object_format))
u64(index_entry_count)
for each sorted index entry:
    frame("P", raw_repository_relative_path_bytes)
    frame("M", ASCII(index_mode))
    frame("I", ASCII(lowercase_full_object_id))
    frame("G", one_byte_numeric_stage)
u64(tracked_worktree_entry_count)
for each sorted tracked worktree entry:
    frame("P", raw_repository_relative_path_bytes)
    frame("K", ASCII("missing" | "file" | "symlink"))
    if file:
        frame("L", u64(exact_file_byte_length))
        frame("H", 32_raw_bytes_of_SHA256(file_bytes))
        frame("X", ASCII("0" | "1" | "N"))
    if symlink:
        frame("T", raw_symlink_target_bytes)
u64(untracked_entry_count)
for each sorted untracked path:
    frame("P", raw_repository_relative_path_bytes)
    frame("L", u64(exact_file_byte_length))
    frame("H", 32_raw_bytes_of_SHA256(file_bytes))
```

The `L` frame payload is the eight bytes returned by `u64`, so the frame length for `L` is always eight. The fingerprint is the lowercase hexadecimal SHA-256 digest of the complete concatenated payload. No byte-order mark, textual hexadecimal file hash, platform newline, implicit separator, shell quoting, or locale-dependent path rendering is added.

Record the branch and `HEAD` separately rather than relying on this fingerprint to encode them. The sender and receiver independently recompute the protocol for comparison. Two computations over an unchanged repository state must produce the same digest; if repeated computation changes without an intended repository edit, report the evidence as unstable and do not trust the handoff.

When the reserved root path is untracked, its untracked-manifest exclusion prevents writing the active `/HANDOFF.md` from immediately invalidating itself. A tracked or filesystem-equivalent collision is never excluded: default persistent storage is refused instead. Other ignored files remain excluded because they are outside the normal repository working-tree evidence set; a project may add relevant content only through explicit repository policy.

The fingerprint proves content identity for these repository categories, not semantic correctness, completeness, validation, review, remote freshness, or authorization.

## Receiving and staleness checks

The receiving flow is:

```text
receive or discover handoff -> run context-resume -> read handoff as supporting evidence
-> verify repository, branch, HEAD, Git categories, and content fingerprint
-> reconcile specifications, decisions, status, validation, and current files
-> surface conflicts or staleness -> continue only with the verified next safe action
```

Compare at least:

- repository identity components and protocol version;
- branch;
- `HEAD`;
- staged, unstaged, and repository-visible untracked content fingerprint;
- relevant file paths and current specifications or decisions;
- task state prerequisites; and
- validation coverage identity and whether later relevant changes invalidate it.

Any branch, `HEAD`, or fingerprint mismatch, later relevant decision, changed specification, changed validation configuration, newer commit, or unbound validation result means the handoff may be stale. Report exactly:

```text
Handoff may be stale; repository state changed after it was created.
```

Then reconstruct current state before continuing. Do not silently update facts inside an old handoff or use matching filenames/status categories as a substitute for matching content.

A matching fingerprint does not override a newer authoritative decision or prove that a reported validation/review action occurred. Current repository evidence and documented decisions retain precedence.

## Missing or malformed handoffs

A missing handoff is not a context-resume failure. Continue reconstruction from repository evidence and report that task-specific transfer context is unavailable.

A handoff is malformed or untrusted when required identity, state, Git, validation, or next-action fields are absent; the state is unsupported; internal evidence conflicts; the repository cannot be identified; or secret-safe evidence cannot be established. Report the affected information as unknown, do not repair or complete the handoff by guessing, and continue from higher-authority repository evidence. If the missing information is essential to select a safe task action, stop and request clarification.

## Security and privacy

Never include secrets, API keys, passwords, tokens, private credentials, private keys, raw secret-bearing environment values, authenticated URLs, unnecessary personal information, or full environment files.

Use secret-safe command representations and concise sanitized evidence. Replace sensitive values with an explicit marker such as `<redacted>` while preserving non-sensitive command structure and failure meaning. When safe redaction cannot be established, include only a restricted artifact reference and a non-sensitive summary, mark the underlying detail unknown or blocked, and do not reproduce the value.

## Approval and workflow invariants

- Creating or receiving a handoff authorizes no repository or external mutation beyond the already authorized task.
- `REVIEW_READY` authorizes neither review findings nor commit/merge/push readiness; it only recommends independent review.
- `FIXES_APPLIED` requires review confirmation and authorizes no Git boundary.
- `REVIEW_CONFIRMED` records completed technical review but authorizes no Git boundary; the exact next boundary still requires its own evidence and explicit approval.
- A handoff must never claim that commit, review, merge, push, release, deployment, branch deletion, or external validation occurred without evidence.
- Commit, merge, push, local branch deletion, and each remote branch deletion retain their separate explicit approval requirements.
- A handoff must not weaken a failed or blocked quality gate, unresolved review finding, dirty-work protection, remote-freshness requirement, or release-check prerequisite.

## Acceptance criteria

1. The capability activates at meaningful transfer boundaries and remains optional for ordinary uninterrupted or trivial work.
2. Every valid handoff uses one supported explicit state with the specified prerequisites and does not use a vague completion state.
3. The format contains task identity, scope, work, validation, Git state, decision references, risks, omissions, and one next safe action sufficient for repository-backed continuation.
4. Substantive claims distinguish verified facts, documented decisions, agent inference, and unknown information.
5. The receiving agent runs `context-resume`, treats the handoff as supporting evidence, and never lets it override current repository state or documented decisions.
6. The default persistent design uses one transient ignored root `/HANDOFF.md`, avoids automatic archives, prevents silent overwrite of a different active task, and refuses the default path when a tracked filesystem-equivalent collision exists.
7. The versioned working-tree fingerprint has deterministic, configuration-isolated Git inputs and byte serialization, is content-sensitive across staged, unstaged, and repository-visible untracked content, excludes only an untracked reserved `/HANDOFF.md`, never omits tracked repository content, and either reproduces the same digest for identical state or reports unavailable when configuration influence cannot be neutralized.
8. Repository identity is checkout-path-independent, uses a secret-safe canonical origin digest with a non-shallow history-root fallback, and repository, branch, `HEAD`, content, relevant-document, or validation-freshness mismatches produce the required staleness warning and trigger reconstruction.
9. Missing or malformed handoffs are never completed by guessing and do not prevent recovery from higher-authority evidence.
10. Validation reports distinguish current, stale, failed, blocked, not applicable, not run, and unknown evidence; `REVIEW_READY`, `FIXES_APPLIED`, and `REVIEW_CONFIRMED` require a current FULL PASS for identical content.
11. Handoff commands and evidence are secret-safe, redact sensitive values, and never reproduce full secret-bearing environment files.
12. The format explicitly distinguishes committed from uncommitted work and lists applicable operations that were not performed.
13. The next safe action cannot bypass specification, quality-gate, review, release-check, or Git approval boundaries.
14. The capability does not add automation scripts, dependencies, databases, incident-recovery execution, dependency security, project health, or unrelated functionality.
15. Existing `context-resume`, `quality-gate`, project-development, review, release, and normal single-agent flows remain valid.
16. Git commands bootstrap one verified repository-specific `safe.directory` value, reject ambient repository/index/object redirection and injected configuration, and never require a wildcard or persistent safe-directory change.
17. Skip-worktree paths and sparse-index directory entries are detected through canonical plumbing output and make the fingerprint unavailable rather than appearing as ordinary missing files.
18. Repository identity reads the raw local origin value without `insteadOf` rewriting, so ambient URL rewrite configuration cannot change the identity digest.
19. An active incident handoff references the durable incident record and current recovery state, preserves incident constraints, and cannot itself establish recovery or authorize an operational action.

## Validation scenarios

| ID | Scenario | Repository and task evidence | Expected observable result |
| --- | --- | --- | --- |
| TH-01 | Completed but uncommitted | Implementation appears complete, FULL passes for the current dirty tree, and no task commit exists. | Uses `REVIEW_READY` when independent review is next, or `COMPLETE_UNCOMMITTED` when another prerequisite prevents review; explicitly states not committed, merged, pushed, released, or deployed. |
| TH-02 | Partial implementation | Some specifications, tests, or implementation exist while named acceptance criteria remain unfinished. | Uses `PARTIAL`; identifies exact completed and outstanding work and makes no completion claim. |
| TH-03 | Review handoff | Implementation and required FULL gate are complete; independent review has not occurred. | Uses `REVIEW_READY`; points the next agent to independent review and does not imply that review or merge readiness already exists. |
| TH-04 | Review findings handoff | Independent review identifies three findings with repository evidence. | Uses `REVIEW_FINDINGS`; lists each finding with severity, affected location, evidence/reasoning, and remediation direction; next action is fix and revalidation. |
| TH-05 | Fixes applied | Review findings are addressed and affected checks plus FULL pass for identical current content. | Uses `FIXES_APPLIED`; references the fixes and fresh evidence; next action is review confirmation, not commit or merge. |
| TH-06 | Known blocker or failed gate | A required test fails or another established blocker prevents safe progress. | Uses `BLOCKED` when progress cannot safely continue, otherwise `PARTIAL`; preserves failure evidence and recommends diagnosis/fix rather than review. |
| TH-07 | Quality gate not run | Implementation exists but no required validation has run. | Reports validation as not run or unknown, never PASS; cannot use `REVIEW_READY` or `FIXES_APPLIED`. |
| TH-08 | Stale `HEAD` | Handoff records commit A and the repository later moves to commit B. | Emits the required staleness warning, reconstructs state, and does not trust completion or validation claims from commit A. |
| TH-09 | Branch mismatch | Handoff records one branch while the receiving repository is on another. | Emits the required staleness warning and verifies whether the task exists on the current branch before acting. |
| TH-10 | In-place dirty-content change | A file already marked modified or untracked is rewritten after handoff creation without changing its Git status category. | Content fingerprint mismatch is detected; matching status categories do not prevent the staleness warning. |
| TH-11 | Untracked handoff self-exclusion | The reserved root `/HANDOFF.md` is untracked and creating it would otherwise add repository-local content. | After confirming no tracked collision, the active untracked handoff is excluded defensively from its own fingerprint, so writing only that file does not invalidate the recorded working-tree identity. |
| TH-12 | Stale validation | FULL passed, then code, tests, specification, configuration, or other validation-relevant content changed. | Validation is reported stale; `REVIEW_READY`, `FIXES_APPLIED`, or `REVIEW_CONFIRMED` is not retained until required checks and FULL pass again for the new fingerprint. |
| TH-13 | Context compression | The receiving session has almost no useful chat history but has the repository and valid active handoff. | `context-resume` plus the verified handoff establishes enough task state and next action to continue without conversational memory. |
| TH-14 | Conflict with newer decision | Handoff says a feature is enabled, but a later authoritative decision rejects it. | The newer decision wins, the conflict is reported, and the rejected feature is not continued from the handoff. |
| TH-15 | Sensitive value in evidence | A command or log contains a token-, password-, credential-, key-, or authenticated-URL value. | The value is not reproduced; evidence uses explicit redaction or a restricted reference and becomes unknown/blocked when it cannot be sanitized safely. |
| TH-16 | Malformed handoff | Required state, identity, Git, validation, or next-action information is absent or contradictory. | Reports the handoff as malformed/untrusted, does not guess missing values, and reconstructs from higher-authority evidence. |
| TH-17 | Missing handoff | `/HANDOFF.md` is absent and chat history is unavailable. | Context recovery continues from repository evidence; task-transfer details are reported unavailable rather than fabricated. |
| TH-18 | Different active task exists | Creating a handoff finds an existing `/HANDOFF.md` for another apparently active task. | Does not silently overwrite it; surfaces the conflict and obtains direction. |
| TH-19 | Git approval boundary | Handoff reports locally complete, reviewed, or fixes-applied work, but commit/merge/push/deletion approvals were not granted. | **Explicitly not done** lists each applicable operation; the next safe action requests only the next required approval or workflow step and performs none automatically. |
| TH-20 | Trivial uninterrupted edit | One agent makes a minor change and continues in the same intact session. | No handoff is required merely because a change occurred. |
| TH-21 | Existing workflow regression | `task-handoff` is added to the template. | Existing skills validate, FULL repository checks pass, normal single-agent work remains possible, and no approval or responsibility boundary is weakened. |
| TH-22 | Review passed, awaiting commit approval | Independent review reports `REVIEW: PASS`, required validation remains current, and the reviewed implementation is uncommitted. | Uses `REVIEW_CONFIRMED`; records the review evidence, states that commit/merge/push were not performed, and recommends requesting explicit commit approval without treating review as authorization. |
| TH-23 | Repository identity match across paths | Sender and receiver use different absolute checkout paths for clones with equivalent canonical origins and matching non-shallow root sets. | `task-handoff-repository-v1` matches; the differing path hints do not create a stale warning. |
| TH-24 | Repository identity mismatch | A handoff is opened in a repository with a different canonical origin digest or a conflicting available root-set digest. | Reports a repository mismatch and the required staleness warning, then reconstructs state without applying the foreign handoff. |
| TH-25 | Fingerprint reproducibility | Sender and receiver independently compute `task-handoff-worktree-sha256-v1` over identical index, tracked worktree, and repository-visible untracked bytes. | Both obtain the same lowercase digest; fixed raw-byte inputs, framing, sorting, and self-exclusion prevent platform or session formatting differences. |
| TH-26 | Repository without a network remote | Sender and receiver have no usable `origin` but have the same complete non-shallow history roots. | Matching `root_set_digest` values establish the fallback identity, while remote identity is reported unavailable rather than invented from checkout paths. |
| TH-27 | Differing output-affecting Git configuration | Identical repository content is inspected in checkouts whose `diff.orderFile`, `diff.indentHeuristic`, `diff.submodule`, `core.attributesFile`, diff drivers, textconv, global ignores, or related configuration differ. | Both compute the same digest because those settings do not enter the plumbing/file-byte protocol; if another configuration influence cannot be isolated, the fingerprint is unavailable and no false staleness claim is made. |
| TH-28 | Protected safe-directory bootstrap | The filesystem requires `safe.directory`; ambient `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, or injected `GIT_CONFIG_*` values point elsewhere. | The cleaned child process uses only `safe.directory=<verified-root>`, verifies the returned root, and computes against that repository; an unverifiable root returns unavailable without wildcard or persistent configuration. |
| TH-29 | Skip-worktree or sparse index | The index contains an `S`/`s` skip-worktree flag or a `040000` sparse-directory entry whose worktree path may be absent. | Canonical flag/stage enumeration detects the condition and returns fingerprint unavailable; it never serializes the path as an ordinary missing file. |
| TH-30 | Differing `insteadOf` configuration | Two sessions inspect the same stored `remote.origin.url`, but one has an injected `url.*.insteadOf` rewrite. | Both read the same raw local value with isolated `git config --local --no-includes`; the canonical origin digest matches, or the component is safely unavailable if the raw value is absent or ambiguous. |
| TH-31 | Tracked root handoff collision | The canonical index manifest contains a tracked root path that is filesystem-equivalent to `HANDOFF.md`. | The tracked path remains in the fingerprint, default persistent storage is reported unavailable, and the agent does not overwrite or recursively fingerprint a generated handoff at that path. |
| TH-32 | Chat-only task content | A task title, request, scope boundary, completion claim, or outstanding item is known only from conversation or agent interpretation and has not been verified against repository evidence or a governed record. | The completed handoff replaces the template placeholder with `Agent inference` or `Unknown / needs verification`; it does not pre-label the claim as `Verified fact`. |
| TH-33 | Active incident transfer | A contained or recovering incident must continue in another session. | The handoff references the incident record and state, the receiver runs `context-resume`, and no handoff claim closes recovery or grants mutation or resumption authority. |

## Test-design review

- [x] Every acceptance criterion maps to one or more scenarios or an explicit structural check.
- [x] All seven task states have observable prerequisites, limitations, and continuation behaviour.
- [x] Complete, partial, review, finding, fix, blocked, unvalidated, and stale-validation paths are covered.
- [x] Branch, `HEAD`, content-sensitive in-place changes, and handoff self-exclusion are covered independently.
- [x] A tracked or filesystem-equivalent root handoff collision is refused without omitting tracked repository content.
- [x] Repository identity is covered for cross-path matches, wrong-repository mismatches, remote-backed identity, and history-root fallback behaviour.
- [x] Fingerprint reproducibility is covered independently from ordinary content-mismatch detection.
- [x] Differing output-affecting Git configuration produces the same digest or a safe unavailable result rather than false staleness.
- [x] Protected `safe.directory`, ambient repository redirection, and injected Git configuration are covered without persistent configuration mutation.
- [x] Skip-worktree and sparse-index representations are detected canonically and cannot masquerade as ordinary missing files.
- [x] Ambient `insteadOf` rewriting cannot change the raw remote identity input.
- [x] Missing, malformed, conflicting, sensitive, and different-active-task evidence is covered.
- [x] Context compression and conflict with newer authoritative decisions preserve the source hierarchy.
- [x] Active-incident transfer preserves the durable incident record, recovery constraints, and operational authority boundary.
- [x] Every Git approval boundary remains explicit and non-transferable.
- [x] Existing workflow regression and non-trigger behaviour are covered.
- [x] Scenarios are judged by risk and acceptance-criterion coverage rather than a fixed count.
- Human checkpoint / reviewer: revision 1 approved by the user on 2026-09-21 after iterative specification review; revision 2 incident-transfer integration was independently reviewed and approved by the user on 2026-09-22.
- Unresolved questions: none identified from current repository evidence.

## Validation and traceability plan

- Skill structure/frontmatter: bundled `skill-creator` quick validator.
- Specification and scenario coverage: iterative human review completed before implementation.
- Behaviour: manual trace of every `TH-*` scenario against the completed skill and template.
- Fingerprint contract: independent manual fixture calculations for identical state plus index, tracked worktree, repository-visible untracked, in-place content change, deterministic framing, `/HANDOFF.md` self-exclusion, and differing Git-configuration cases.
- Git isolation: manual fixtures for protected safe-directory handling, cleaned repository/index/object overrides, injected `GIT_CONFIG_*` values, skip-worktree flags, and sparse-index entries.
- Repository identity: manual fixtures for equivalent network URLs, different checkout roots, raw local URLs under differing `insteadOf` rules, no-origin fallback, shallow-history limitations, and mismatched repositories.
- Secret safety: manual fixture using synthetic credential-like placeholders; no real secret values.
- Documentation and path consistency: repository-wide relative Markdown link check and search for stale workflow/version wording.
- Existing regression: validate every repository skill and preserve existing context-resume, quality-gate, approval, and single-agent behaviour.
- Whitespace and patch integrity: repository FULL quality-gate profile covering staged, unstaged, and non-ignored untracked content.
- Automated product tests: not applicable; this instruction-only template has no executable product code or test harness.

### Manual scenario results

| Scenario | Result | Evidence in the implemented capability |
| --- | --- | --- |
| TH-01 | Pass | `REVIEW_READY` and `COMPLETE_UNCOMMITTED` have distinct validation prerequisites; the template records dirty Git state and every applicable unperformed operation. |
| TH-02 | Pass | `PARTIAL` requires exact completed and outstanding work, and the template exposes both fields without a completion claim. |
| TH-03 | Pass | `REVIEW_READY` requires a current FULL pass and names independent review as the next action without implying review or merge readiness. |
| TH-04 | Pass | `REVIEW_FINDINGS` requires severity, affected surface, evidence/reasoning, and remediation; the review-evidence section carries those findings. |
| TH-05 | Pass | `FIXES_APPLIED` requires affected checks and FULL to pass for identical content, then directs the receiver to review confirmation. |
| TH-06 | Pass | `BLOCKED` and `PARTIAL` preserve failed-gate evidence and route to diagnosis/fix rather than normal review. |
| TH-07 | Pass | Missing validation is represented as not run or unknown and cannot satisfy `REVIEW_READY`, `FIXES_APPLIED`, or `REVIEW_CONFIRMED`. |
| TH-08 | Pass | Receiving checks compare `HEAD`; a mismatch emits the required staleness warning and forces reconstruction. |
| TH-09 | Pass | Receiving checks compare branch separately from content and treat a mismatch as potentially stale. |
| TH-10 | Pass | The protocol hashes tracked/untracked file bytes; a fixture rewrote an already tracked path and produced a different SHA-256 content digest without relying on status categories. |
| TH-11 | Pass | A missing-ignore fixture exposed untracked `HANDOFF.md`, then the protocol's defensive filter removed only that reserved path while retaining another untracked file. |
| TH-12 | Pass | Later validation-relevant changes invalidate `REVIEW_READY`, `FIXES_APPLIED`, and `REVIEW_CONFIRMED` until affected checks and FULL pass again. |
| TH-13 | Pass | The skill requires `context-resume` first and the template supplies task-specific state, evidence, omissions, and one continuation action without chat history. |
| TH-14 | Pass | Repository state and documented decisions outrank handoff evidence; conflicts are surfaced rather than silently accepted. |
| TH-15 | Pass | Skill and template prohibit secrets and require `<redacted>` or a restricted evidence reference when sanitization is necessary. |
| TH-16 | Pass | Missing required fields, unsupported state, contradictions, unidentified repository, or unsafe evidence make a handoff malformed and untrusted without guessed repairs. |
| TH-17 | Pass | A missing handoff does not stop `context-resume`; unavailable transfer detail remains unknown rather than fabricated. |
| TH-18 | Pass | The persistent lifecycle inspects an existing root handoff and prohibits silently overwriting a different active task. |
| TH-19 | Pass | The template makes **Explicitly not done** mandatory when applicable, while skill and workflow retain separate commit, merge, push, and deletion approvals. |
| TH-20 | Pass | Trigger guidance explicitly excludes trivial edits and unchanged uninterrupted sessions; normal single-agent operation remains valid. |
| TH-21 | Pass | All eleven repository skills validate, relative links and patch integrity pass, version references agree, and the repository FULL profile passes without weakening existing workflows. |
| TH-22 | Pass | `REVIEW_CONFIRMED` records completed review and current validation but directs the next agent to request the exact Git-boundary approval. |
| TH-23 | Pass | `task-handoff-repository-v1` excludes the checkout path from identity and compares canonical origin plus complete non-shallow root-set digests. |
| TH-24 | Pass | Different available origin or root-set digests produce repository mismatch and the required staleness warning. |
| TH-25 | Pass | Two independent canonical payload calculations over the implemented working tree produced the same lowercase SHA-256 digest, including after ambient Git-variable injection. |
| TH-26 | Pass | A temporary repository retained the same root-set input after removing `origin`, demonstrating the no-network-remote fallback. |
| TH-27 | Pass | Temporary-repository index and repository-visible untracked manifests remained identical under differing diff, attribute, and global-ignore configuration. |
| TH-28 | Pass | The target repository completed every isolated protocol command with only `-c safe.directory=<verified-root>` after ambient repository/config variables were cleared. |
| TH-29 | Pass | Temporary fixtures produced both an `S` skip-worktree tag and a `040000` sparse-directory entry; each matched the protocol's unavailable condition. |
| TH-30 | Pass | An injected `insteadOf` rule changed `remote get-url`, while isolated `config --local --no-includes` returned the unchanged stored origin value. |
| TH-31 | Pass | A tracked-root fixture exposed `HANDOFF.md` in the canonical index manifest; the collision rule retained it as repository content and refused default persistent storage. |
| TH-32 | Pass | The template requires an explicit evidence-label replacement for task title, request, scope, completed work, and outstanding work, and warns that chat-only content is not a verified fact. |
| TH-33 | Pass | Incident transfers reference the durable incident record and preserve recovery constraints; a handoff never establishes recovery verification or operational authority. |

### Repository check results

- Bundled quick validation: all eleven repository skills pass in Python UTF-8 mode.
- Protocol command availability: protected safe-directory bootstrap, raw origin, shallow-state, history-root, object-format, stage/sparse, flag, and untracked commands pass in the target repository.
- Fingerprint reproducibility: canonical calculations match with and without injected ambient repository and Git-configuration variables.
- Protocol fixtures: skip-worktree, sparse index, `insteadOf`, global-ignore isolation, index configuration isolation, in-place content change, untracked handoff self-exclusion, tracked-root collision refusal, and no-remote history fallback pass.
- Repository-defined FULL profile: pass on 2026-09-22 for the incident-transfer integration; all required checks executed and the before/after content fingerprints match.
- Automated product tests: not applicable; this template intentionally has no executable product test harness.
