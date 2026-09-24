---
name: quality-gate
description: Evaluate project-configured local checks for the current working tree in FAST or FULL mode and report trustworthy PASS, FAIL, BLOCKED, or NOT_APPLICABLE evidence before review. Do not use it for code review, release readiness, or authorization.
---

# Quality gate

Answer only:

> Has the current working tree passed the required checks for this project?

Use project-defined deterministic validation and the contract in the [quality-gate specification](../../../docs/QUALITY_GATE.md). This skill evaluates evidence. It does not fix failures, judge whether a change should merge, or authorize or perform a commit, merge, push, release, deployment, or branch deletion.

## 1. Select the mode and current state

Run the mode the request or workflow requires:

- **FAST** gives quick implementation feedback using the project's FAST profile.
- **FULL** validates the complete project-defined pre-review profile. Run it before normal independent review and again after any relevant fix or other change that invalidates earlier evidence.

A FAST pass is not a FULL pass. If the project uses one command for both, its configuration must explicitly establish that the command satisfies the FULL profile; do not relabel old FAST evidence.

Before running checks, record the repository root, branch, and `HEAD`. Capture content-sensitive fingerprints for the complete staged diff, complete unstaged diff, and every relevant untracked file. A path list or `git status` categories alone are insufficient because an already modified or untracked file can be rewritten without changing its status category. A dirty tree may be validated and must be reported. It fails only when project policy makes cleanliness a required check.

## 2. Resolve the project gate profile

Read authoritative repository instructions and existing configuration to identify:

- each check's name, category, required or advisory status, and applicable modes;
- the exact command or aggregate command, working directory, and required environment;
- evidence of meaningful execution, such as test counts, expected artifacts, invariant summaries, or success markers;
- expected scope plus permitted skips, exclusions, and minimum discovery where documented; and
- explicit reasons for checks or categories that are not applicable.

When repository policy configures `dependency-security-check`, resolve its applicability from the configured triggers and profile. FAST may omit heavyweight dependency evidence only when policy permits and no trigger changed. FULL invokes or consumes the check when a dependency/security trigger changed or the profile otherwise requires it. Do not reproduce its dependency, provenance, vulnerability, secret, ignore, or install-script analysis inside quality-gate.

Typical categories are static validation (formatting, lint, syntax, and type checks), tests (unit, integration, regression, and smoke), domain validation, and repository consistency, but no category is automatically required. Do not invent a command, dependency, minimum count, or applicability rule.

Prefer an existing local interface equivalent to `check fast` and `check full`. When no aggregate command exists, run the documented command set directly. If required checks or their commands cannot be determined reliably, the gate is `BLOCKED`.

Keep normal execution local-first and offline when the project permits. An unavailable required external check is `BLOCKED`, not skipped or NOT_APPLICABLE.

## 3. Run without weakening

Run the exact configured command or command set from the documented location. Do not:

- add flags that skip, tolerate, or narrow required coverage;
- substitute a focused test, one file, changed-tests-only selection, or newly added tests for a required FULL suite;
- remove or disable tests or checks;
- change expected values merely to obtain PASS; or
- reuse a previous PASS that is not trustworthily bound to the identical current code, diff, relevant untracked content, configuration, and environment.

For every check, preserve a secret-safe representation of the exact command, exit status, concise sanitized output, counts and skips where available, and failure or blocked evidence. Keep executable names, flags, paths, and non-sensitive arguments, but replace credential values, tokens, sensitive environment values, authenticated URL components, headers, keys, and similar material with an explicit placeholder such as `<redacted>`. If evidence cannot be sanitized without losing its validation meaning, retain only a restricted artifact reference and non-sensitive summary and classify the report `BLOCKED`. An aggregate exit code is insufficient when the profile requires evidence that its component checks actually ran.

## 4. Validate the evidence

Do not equate exit zero with PASS. Confirm the expected validation occurred:

- A normally completed required test command that discovers zero tests when tests are expected is `FAIL`. Incomplete or untrustworthy discovery is `BLOCKED`.
- Reliable explicit failure evidence is `FAIL` even if the process exits zero. Unresolved contradictory output or missing configured success evidence is `BLOCKED`.
- A missing required check, tool, dependency, artifact, or expected sub-check is `BLOCKED`.
- A configured skip allowance that is exceeded is `FAIL`. Unexpected skips with unclear effect on required coverage are `BLOCKED`. Always report skip counts.
- A required `dependency-security-check` result maps `PASS` to PASS, `FINDINGS` to FAIL, `BLOCKED` to BLOCKED, and `NOT_APPLICABLE` to NOT_APPLICABLE only when authoritative policy establishes non-applicability. A missing invocation or result is `BLOCKED`.
- A crash, timeout, interrupted command, wrong environment, or unverified/narrowed scope is `BLOCKED` unless reliable evidence already establishes a validation failure; report both facts when relevant.

After execution, recompute the staged-diff, unstaged-diff, and relevant-untracked-file fingerprints and compare them with the starting values, then recheck branch and `HEAD`. An unexpected relevant content change makes affected results stale even when `git status` looks identical. Rerun against the final content or mark the gate `BLOCKED`. If the available tools cannot fingerprint all relevant content reliably, the gate is `BLOCKED`.

## 5. Classify checks and the gate

Assign every configured check one state:

- **PASS** — applicable, freshly executed for the current state, successful, and supported by the required evidence;
- **FAIL** — executed sufficiently to prove a violation or configured coverage failure;
- **BLOCKED** — required evidence could not be obtained or trusted; or
- **NOT_APPLICABLE** — authoritative project configuration explicitly says the check is irrelevant.

Missing configuration, commands, tools, or results are never NOT_APPLICABLE. Keep advisory checks visible, but calculate the overall result from required checks:

1. `FAIL` when any required check fails, while still listing concurrent blockers.
2. Otherwise `BLOCKED` when any required check is blocked, missing, stale, or unclassified.
3. Otherwise `PASS` when at least one required check exists and all required checks pass.
4. Otherwise `NOT_APPLICABLE` only when authoritative configuration explicitly defines no required checks for the selected mode.

Never silently weaken a profile or convert a required failure, block, absence, or skip into PASS.

## 6. Report the evidence

Report:

- mode, repository root, branch, `HEAD`, and working-tree state;
- every configured or attempted check with category, required/advisory status, state, important counts, and concise evidence;
- skipped and NOT_APPLICABLE checks with reasons;
- failed and blocked checks;
- secret-safe command representations and exit status;
- the deterministic overall state; and
- stable machine-readable lines `QUALITY_GATE_MODE=<FAST|FULL>` and `QUALITY_GATE_RESULT=<PASS|FAIL|BLOCKED|NOT_APPLICABLE>`.

For a FULL pass, finish with:

```text
Quality gate passed; ready for independent review.
```

Do not output `READY TO MERGE`. FAST PASS and any non-PASS state must not claim readiness for independent review.

## 7. Handle failure without bypassing it

Preserve useful sanitized failure output and classify the likely cause only when evidence supports one of: product/code regression, test defect, environment/tooling issue, expected intentional behaviour change, or unknown. Never expose a secret merely to make the failure easier to reproduce; identify the required secret by variable or credential name, not value. Do not call a failure flaky without evidence.

Stop progression to normal independent review or human approval when a required check fails or blocks. If implementation changes are requested, return to `project-dev-cycle` and use `debug` for defect diagnosis where applicable. After a justified fix, rerun affected checks and then FULL before final review. The quality gate itself does not edit code or tests.

Do not treat every failure as an incident. If the evidence instead indicates possible corruption, partially written durable state, broad unrelated regressions, uncertain external side effects, a compromised validation environment, or impact that cannot safely be bounded, stop ordinary failure progression and activate `incident-recovery`. The gate result remains FAIL or BLOCKED as determined here; incident recovery owns containment and resumption, not reclassification of validation evidence.

Likewise, dependency-security remediation returns to `project-dev-cycle`, while a likely real secret exposure or suspected compromise routes to `incident-recovery`. Application-security reasoning remains with `code-review`, and release readiness remains with `release-check`. The gate only orchestrates and aggregates configured evidence.
