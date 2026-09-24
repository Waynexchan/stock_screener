---
name: task-handoff
description: Create or consume a concise repository-grounded handoff for one active task at a meaningful agent, session, review, or fix boundary. Do not use for trivial uninterrupted work or as a substitute for context-resume, validation, review, or Git approval.
---

# Task handoff

Transfer one active task without relying on chat history. A handoff is supporting evidence only:

> Current repository state and documented decisions outrank the handoff, and both outrank conversational memory.

Use the contract in the [task-handoff specification](../../../docs/TASK_HANDOFF.md) and the standard [handoff template](../../../templates/HANDOFF.md). Keep the handoff concise and reference durable repository records instead of copying them.

## 1. Decide whether to hand off

Create a handoff only at a meaningful transfer boundary: another agent or session will continue, implementation is complete but uncommitted, work is partial or blocked, independent review is next, review findings need fixes, fixes need confirmation, review is confirmed and a Git boundary awaits separate approval, context loss makes continuation risky, or the user explicitly requests transfer.

Do not create one for every trivial edit or during an unchanged uninterrupted session. The workflow remains valid for one agent without a handoff.

## 2. Reconstruct and classify the task

Before creating a handoff, verify the repository, branch, `HEAD`, staged/unstaged/untracked state, governing specification, relevant decisions, current validation, active incident/recovery record when applicable, review evidence, and applicable approval state. Write durable behavioural knowledge, project context, incident evidence, and decisions to their authoritative artifacts first when practical.

Use exactly one state:

- `COMPLETE_UNCOMMITTED` — implementation appears locally complete and uncommitted, but current evidence does not establish review readiness;
- `PARTIAL` — specified work remains incomplete;
- `REVIEW_READY` — required FULL quality gate passed for identical content and independent review is next;
- `BLOCKED` — a known blocker prevents safe progress;
- `REVIEW_FINDINGS` — review findings are being transferred for repair;
- `FIXES_APPLIED` — findings were addressed, affected checks and FULL passed, and review confirmation is next; or
- `REVIEW_CONFIRMED` — independent review passed or confirmed fixes, while the next Git boundary still requires its own evidence and explicit approval.

Never use a vague state such as `DONE`. State committed versus uncommitted work separately.

## 3. Create the handoff

Use `templates/HANDOFF.md` and include task identity, intended and excluded scope, completed and outstanding work, changed files, specification/tests, validation evidence, Git state, decision references, risks, unknowns, applicable operations explicitly not done, and one next safe action.

Label substantive claims as **Verified fact**, **Documented decision**, **Agent inference**, or **Unknown / needs verification**. Never turn an assumption, old validation result, or agent confidence into fact or `PASS`.

Compute repository identity and the content-sensitive working-tree fingerprint exactly as specified in `docs/TASK_HANDOFF.md`. Record the protocol identifiers, values, and any unavailable component. Do not invent a digest or weaken an unavailable result. The active root `/HANDOFF.md` is excluded from its own fingerprint.

Sanitize commands and evidence. Never include credentials, tokens, private keys, secret-bearing environment values, authenticated URLs, full environment files, or unnecessary personal data. Use `<redacted>` or a restricted artifact reference when necessary.

For an immediate reliably delivered transfer, return the rendered handoff. When continuation must survive a restart, new conversation, or context loss, first inspect the canonical index manifest. If a tracked root path is filesystem-equivalent to `HANDOFF.md`, do not write the default path; report persistent default storage unavailable and return the rendered handoff or request an explicit project-specific location. Otherwise write the same content to the ignored repository-root `/HANDOFF.md`. Inspect an existing untracked file first: update it only for the same active task at a newer meaningful boundary, and never silently overwrite another task's handoff. Do not create an automatic archive or exclude tracked repository content from the fingerprint.

## 4. Receive a handoff

Run `context-resume` first. A missing handoff does not stop repository recovery. Treat a handoff with missing required fields, an unsupported state, internal contradictions, an unidentified repository, or unsafe evidence as malformed and untrusted; do not repair it by guessing.

Read the handoff as supporting evidence, then independently verify repository identity, branch, `HEAD`, Git categories, working-tree fingerprint, governing specifications and decisions, state prerequisites, validation freshness, and review evidence. Higher-authority evidence wins, and every conflict is surfaced.

When repository, branch, `HEAD`, content, decisions, specifications, or validation coverage may have changed, report exactly:

```text
Handoff may be stale; repository state changed after it was created.
```

Reconstruct current state before continuing. A matching fingerprint does not prove correctness, validation, review, remote freshness, or authorization.

## 5. Preserve workflow and approval boundaries

A handoff never performs or authorizes validation, independent review, commit, merge, push, release, deployment, branch deletion, force push, or destructive cleanup. `REVIEW_READY` means only that independent review is next. `FIXES_APPLIED` still needs review confirmation. `REVIEW_CONFIRMED` still needs the exact next Git boundary's evidence and explicit approval.

When the transferred task is an active incident, the handoff references the durable incident record, current containment/recovery state, and one incident-safe next action. It does not replace that record, establish `RECOVERY_VERIFIED`, authorize containment or recovery mutations, or allow normal workflow to resume.

Commit, merge, push, local branch deletion, and every remote branch deletion retain their separate explicit approvals. A failed, blocked, stale, or missing quality gate and an unresolved review finding remain visible and cannot be bypassed by handoff state.
