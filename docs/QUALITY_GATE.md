# Behaviour specification: quality gate

## Identity and change control

- Specification: `docs/QUALITY_GATE.md`
- Revision: 4
- Status: reviewed
- Last updated: 2026-09-22
- Related decision record: none; this capability formalizes the existing local-validation checkpoint without changing approval policy.

## Intent and scope

`quality-gate` answers one question:

> Has the current working tree passed the required checks for this project?

It evaluates fresh, local validation evidence before normal independent review or human approval. It does not decide whether a change should be merged and does not authorize or perform a commit, merge, push, release, deployment, branch deletion, test weakening, or other repository mutation.

The gate is reusable across project toolchains. Each project remains responsible for defining its applicable checks and commands in repository-owned configuration or instructions. The template supplies the evidence model, result rules, FAST/FULL modes, reporting contract, and false-green protections; it does not impose a language, package manager, CI provider, dependency, or universal executable.

### Responsibility boundaries

- `quality-gate` discovers the project-defined gate profile, runs its local commands, validates the evidence, classifies each check, and calculates the gate result.
- `project-dev-cycle` owns specification, test-first implementation, the fix loop, durable write-back, review sequencing, and Git approval boundaries.
- `debug` owns evidence-led diagnosis and repair of a failure when a fix is requested.
- `dependency-security-check` owns dependency justification, package provenance, manifest/lockfile consistency, known-vulnerability evidence, changed-content secret exposure, ignore safety, and dependency-related install/build risk.
- `code-review` owns judgment about correctness, design, security, maintainability, and test adequacy beyond deterministic gate evidence.
- `release-check` owns readiness for a named commit, merge, push, release, or other operational boundary.

Passing the quality gate is evidence for review. It is neither technical review nor boundary readiness.

## Project-defined gate profile

The gate must recover the applicable profile from authoritative repository evidence such as `AGENTS.md`, project status, a manifest/task runner, CI configuration, or documented validation guidance. A profile should identify, for each check:

- a stable check name and category;
- whether it is required or advisory;
- the modes in which it applies;
- the exact command or existing aggregate command that runs it;
- the working directory and required environment when these differ from repository defaults;
- the evidence that proves meaningful execution, such as a success marker, test count, expected artifact, schema version, or invariant summary;
- permitted skips, exclusions, or minimum discovery expectations where relevant; and
- an explicit reason when the check or category is not applicable.

Relevant categories may include:

- **Static validation:** formatting, linting, syntax, and type checking.
- **Test validation:** unit, integration, regression, and smoke tests.
- **Domain validation:** data-quality invariants, schemas, point-in-time guarantees, research guardrails, financial calculations, migrations, or other project-specific rules.
- **Dependency/repository security:** a configured `dependency-security-check` result when trigger conditions or repository policy make it required.
- **Repository validation:** whitespace/error checks covering unstaged tracked, staged, and relevant untracked content; generated or runtime artifacts; and working-tree reporting.

No category is mandatory merely because it appears in this list. Required checks come from the project profile. An absent or ambiguous profile for checks that appear required results in `BLOCKED`; the gate must not invent commands or quietly assume that no checks apply.

### Standard local command contract

Projects should expose a small local interface equivalent to:

```text
check fast
check full
```

The spelling and implementation belong to the project and may use Python, PowerShell, shell, Make, npm scripts, or an existing task runner. A migrated project may place project-specific commands behind this interface when doing so reuses its existing tooling and improves consistency. The gate may instead run a documented command set directly when one aggregate entry point is impractical. It must not create a competing wrapper, add a dependency, or fabricate a command merely to match the preferred spelling.

The primary gate is local-first and should remain offline-capable whenever the project's own checks can run offline. Invoking an AI agent or network service is not part of ordinary gate execution. If a required project check genuinely depends on an unavailable external service, its result is `BLOCKED`, not silently skipped.

When repository policy configures `dependency-security-check`, the gate orchestrates or consumes that capability rather than reimplementing its security logic. FAST may omit heavyweight dependency evidence when no dependency/security trigger changed and policy permits the omission. FULL invokes the check when a trigger changed or the profile otherwise requires it. Map a required dependency-security `PASS` to gate `PASS`, `FINDINGS` to gate `FAIL`, `BLOCKED` to gate `BLOCKED`, and `NOT_APPLICABLE` to gate `NOT_APPLICABLE` only when authoritative policy establishes non-applicability. A missing required invocation or result is `BLOCKED`.

## Gate modes

### FAST

FAST supplies quick implementation feedback. A project may include formatting, linting, type checks, critical unit tests, and high-value invariants. Its precise coverage is project-defined.

A FAST pass proves only that the FAST profile passed. It is not interchangeable with a FULL pass. A project that uses the same command for both modes must explicitly define that command as satisfying the FULL profile; prior FAST output is not relabelled as FULL evidence.

### FULL

FULL is the pre-review gate. It includes or supersedes every required FAST check and normally adds the full test suite, integration and regression checks, required domain invariants, and repository consistency checks. The configured FULL command may aggregate those checks, but the result must still show enough evidence to confirm their required coverage.

Run FULL before normal independent review. If relevant code, tests, configuration, specifications, or validation logic changes after a FULL pass, the old result is stale and FULL must run again before returning to review or human approval.

## Check states and overall result

Every configured check has a state:

- **PASS** — The check was applicable, executed for the current working-tree state, completed successfully, and produced the required trustworthy evidence.
- **FAIL** — The check executed sufficiently to establish a validation failure, such as a lint violation, failed assertion, violated invariant, or configured discovery/skip threshold.
- **BLOCKED** — A required result could not be obtained or trusted. Examples include a missing command or dependency, tool/configuration crash, timeout, wrong environment, unavailable artifact or service, ambiguous or contradictory output, unverified command scope, or a working-tree change that makes the captured evidence stale.
- **NOT_APPLICABLE** — Authoritative project configuration explicitly establishes that the check is irrelevant. Absence of a tool, command, result, or configuration is not evidence of non-applicability.

Checks must also be labelled `required` or `advisory`. Advisory results remain visible but do not determine the overall state. Projects must not mark a check advisory merely to bypass an existing requirement.

Calculate one deterministic overall state over the required checks:

1. `FAIL` if any required check is `FAIL`, while still reporting every concurrent blocked check.
2. Otherwise `BLOCKED` if any required check is `BLOCKED`, missing, stale, or unclassified.
3. Otherwise `PASS` if at least one required check exists and every required check is `PASS`.
4. Otherwise `NOT_APPLICABLE` only when authoritative project configuration explicitly states that the selected mode has no required checks.

`PASS` is impossible when a required check is failed, blocked, missing, stale, substituted with a narrower command, or silently skipped.

## Execution and evidence contract

For each invocation, the gate must:

1. Confirm the repository root, selected mode, current branch and `HEAD`, and capture a content-sensitive identity for the staged diff, unstaged diff, and every relevant untracked file. Path/status categories alone are insufficient because content can change without changing those categories.
2. Resolve the required and advisory checks from current authoritative project evidence. Record explicit non-applicability reasons.
3. Run the configured command or command set locally from the documented working directory without weakening flags, narrowed targets, or omitted required checks.
4. Preserve a secret-safe representation of the exact command, exit status, concise sanitized output, counts where available, and any failure or blocked evidence. Retain executable names, flags, paths, and non-sensitive arguments, but replace credential values, tokens, sensitive environment values, authenticated URL components, headers, keys, and similar material with an explicit placeholder such as `<redacted>`.
5. Verify that expected validation actually occurred rather than trusting exit status alone.
6. Recompute the staged-diff, unstaged-diff, and relevant-untracked-content identities after execution and compare them with the starting identities, in addition to rechecking branch and `HEAD`. If relevant content changed during the run, do not treat earlier results as current without rerunning against the final state.
7. Classify every check, calculate the overall result, and report limitations and advisory results without hiding them.

The report must be concise for humans and expose stable machine-readable fields. Use this shape or a project-defined equivalent that preserves the same information:

```text
QUALITY GATE
Mode: FULL
Repository: <root>
Branch / HEAD: <branch> / <commit>
Working tree: <clean or staged/unstaged/untracked summary>

Check                 Category     Required  State            Evidence
<name>                <category>   yes       PASS             <count or success evidence>
<name>                <category>   no        NOT_APPLICABLE   <configured reason>

Commands and evidence:
- <check>: `<secret-safe command representation>` -> exit <code>; <concise sanitized evidence>

Failed checks: <none or names and evidence>
Blocked checks: <none or names and evidence>
Skipped / not applicable: <none or names, counts, and reasons>
Advisory results: <none or results>
Overall: PASS
QUALITY_GATE_MODE=FULL
QUALITY_GATE_RESULT=PASS
```

When FULL passes, the safe conclusion is: `Quality gate passed; ready for independent review.` No result may say `READY TO MERGE` or imply authorization for a later boundary. FAST PASS, FAIL, BLOCKED, and NOT_APPLICABLE reports must not claim readiness for independent review.

## False-green protections

The gate validates execution semantics as well as process exit codes:

- **Freshness:** Run checks for the current invocation. Do not reuse an earlier PASS artifact unless the project provides a trustworthy content-addressed mechanism proving it covers the identical `HEAD`, tracked diff, staged diff, relevant untracked content, configuration, and environment. Otherwise rerun.
- **Stable content:** Before and after validation, compare content-sensitive fingerprints of the staged diff, unstaged diff, and each relevant untracked file, as well as branch and `HEAD`. Merely comparing `git status` categories is insufficient: rewriting a file already marked modified or untracked may leave status output unchanged. An unexpected relevant content change makes affected evidence `BLOCKED` until rerun against the final state. A dirty tree at the start is reported but is not itself a validation failure unless project policy defines a required cleanliness check.
- **Discovery:** When a profile expects tests, a normal runner result with zero tests discovered is `FAIL`. If discovery did not complete or the zero result cannot be trusted because of a runner/configuration problem, it is `BLOCKED`.
- **Scope:** Run the exact configured FULL scope. A focused command, single-file target, changed-tests-only selection, or newly added tests cannot substitute for required regression coverage. An unverified or accidentally narrowed scope is `BLOCKED`.
- **Contradictory output:** Explicit valid failure evidence is `FAIL` even when the command exits zero. A zero exit with error text, missing success evidence, or another unresolved contradiction is `BLOCKED`, not PASS.
- **Skips and exclusions:** Record skip counts. Exceeding a configured allowance or contradicting an established no-skip expectation is `FAIL`. Unexpected skips whose effect on required coverage cannot be determined are `BLOCKED`. Documented allowed skips may remain PASS but must stay visible.
- **Expected checks:** Compare observed checks with the current profile. A required check or expected artifact that silently disappears is `BLOCKED`.
- **Dependency-security mapping:** When configured as required, dependency-security `FINDINGS`, `BLOCKED`, a missing invocation, or unjustified `NOT_APPLICABLE` cannot produce overall PASS. Consume its result and secret-safe evidence; do not duplicate its package, provenance, vulnerability, secret, ignore, or install-script analysis inside the gate.
- **Environment:** Run from the correct root/directory and record required environment identity where configured. A missing tool, dependency, service, or incompatible environment is `BLOCKED`; it is not NOT_APPLICABLE.
- **Crashes and timeouts:** A tool/configuration crash, interrupted run, or timeout is `BLOCKED` unless reliable output already establishes a check failure, in which case that check is `FAIL` and the incomplete evidence is also reported.
- **Aggregate commands:** When an aggregate command is used, require enough sub-check evidence to establish that every required component ran. Aggregate exit zero alone is insufficient when configured components are missing.
- **Secret-safe evidence:** Never place raw secrets, credentials, private keys, sensitive environment values, authenticated URLs, or secret-bearing headers in the report or durable validation artifacts. Sanitize command representations and output while preserving the command structure and failure meaning. If safe sanitization cannot be established, retain only a restricted artifact reference and non-sensitive summary; exposed secret material makes the report `BLOCKED` until it is handled safely.
- **Patch-integrity scope:** A repository whitespace check must cover unstaged tracked changes, staged changes, and every relevant non-ignored untracked file. `git diff --check` alone covers only unstaged tracked changes and cannot establish PASS for the complete working tree.
- **Markdown link forms:** A required local-link check must resolve every supported relative target form it claims to cover, including valid angle-bracket destinations such as `[doc](<path with spaces/file.md>)` and reference-style definitions. Strip angle wrappers before resolving; do not treat an unparsed valid form as a successful check.

These protections are evidence checks, not a mandate to build a CI platform. Prefer project-native counts, summaries, and artifacts, and add only expectations justified by the repository.

## Failure behaviour

When a required check fails or blocks:

1. Report it without weakening, substituting, disabling, or hiding the check.
2. Preserve useful sanitized output and distinguish, when the evidence supports it, a product/code regression, test defect, environment/tooling issue, expected intentional behaviour change, or unknown cause.
3. Do not label a failure flaky without reproducible evidence.
4. Do not alter tests or expected values merely to obtain PASS.
5. Stop progression to normal independent review or human approval on this evidence.
6. If a fix is requested, return to the applicable `project-dev-cycle`/`debug` workflow, establish the correct contract, implement the justified fix, and rerun affected checks.
7. Rerun FULL before final review after any relevant fix or other evidence-invalidating change.
8. Do not activate incident recovery for an ordinary scoped failure. When the evidence instead indicates possible corruption, partially written durable state, broad unrelated regressions, uncertain external effects, a compromised validation environment, or impact that cannot safely be bounded, retain the correct FAIL/BLOCKED result and route containment and resumption through `incident-recovery`.

The gate reports evidence; it does not implement fixes itself.

## Acceptance criteria

1. The skill answers whether the current working tree passed project-required checks and never answers merge or release readiness.
2. The skill discovers project-defined commands and applicability without inventing a toolchain, command, category requirement, or dependency.
3. FAST and FULL are distinct, clearly reported modes; FULL covers or supersedes required FAST checks and is required before normal independent review.
4. Every check and the overall gate use deterministic `PASS`, `FAIL`, `BLOCKED`, or `NOT_APPLICABLE` rules, with required/advisory status explicit.
5. Missing, stale, skipped, narrowed, unavailable, contradictory, or otherwise untrusted required evidence cannot produce PASS.
6. Reports include repository state, mode, every attempted or configured check, counts where available, skips/non-applicability, failures, blockers, secret-safe command representations, sanitized evidence, overall state, and machine-readable mode/result fields.
7. Dirty working state is reported and does not fail validation unless project policy requires cleanliness; before/after content fingerprints cover staged and unstaged diffs plus relevant untracked files, and unexpected content changes invalidate affected evidence even when Git status categories do not change.
8. Failure handling preserves evidence, does not weaken checks or rewrite expectations merely to pass, distinguishes supported cause classes, and returns fixes to the normal development workflow.
9. The primary design is local-first and offline-capable where project checks permit; unavailable required external checks block rather than disappear.
10. The capability remains separate from `code-review` and `release-check` and never authorizes or performs commit, merge, push, release, deployment, or branch deletion.
11. The template adds no validation framework, language-specific wrapper, dependency, CI system, or unrelated capability.
12. Existing template skill structure, documentation links, regression behaviour, and approval boundaries remain valid.
13. Commands, output, and durable evidence are redacted without concealing the command structure or validation meaning; evidence that cannot be made secret-safe blocks reporting.
14. Repository patch-integrity validation covers unstaged tracked, staged, and relevant non-ignored untracked files; omitted working-tree categories cannot produce PASS.
15. Relative Markdown link validation resolves inline, angle-bracket, and reference-style local destinations rather than silently excluding valid syntax; reference definitions may have zero to three literal leading spaces, while a tab-indented definition is indented code and is not validated as a link target.
16. Markdown fence filtering follows the relevant fence boundaries: an opener or closer may be indented by zero to three literal spaces, a leading tab is not treated as one space, and a closer must use the opening marker with at least the opening length; invalid or short fence-like lines cannot hide links from validation.
17. Ordinary scoped failures remain in the normal failure/debug path, while credible broader integrity or state incidents preserve the gate result and route containment and verified resumption through `incident-recovery`.
18. A configured dependency-security check is conditionally invoked from the project profile, preserves its ownership boundary, and maps required `FINDINGS`, `BLOCKED`, missing, or unjustified non-applicability evidence so the overall gate cannot PASS.

## Validation scenarios

| ID | Scenario | Required evidence/profile | Expected observable result |
| --- | --- | --- | --- |
| QG-01 | Everything passes | FAST and FULL required commands execute successfully with expected coverage evidence. | FAST reports `PASS`; a separate FULL run reports `PASS` and may conclude that the change is ready for independent review. |
| QG-02 | Lint failure | Required lint command executes and reports a violation. | Lint is `FAIL`; overall is `FAIL`; no later summary claims the gate passed. |
| QG-03 | Unit-test regression | Required unit suite executes and one existing test fails. | Unit tests and overall are `FAIL`, with the failed-test evidence preserved. |
| QG-04 | Missing required tool | Required type checker command is configured but its executable/dependency is unavailable. | Type check and overall are `BLOCKED`, never PASS or NOT_APPLICABLE. |
| QG-05 | Optional check absent | Authoritative configuration explicitly states that the project does not use a type checker. | Type checking is `NOT_APPLICABLE` with the reason; other required checks determine the overall result. |
| QG-06 | Unexpected zero-test discovery | The profile expects a nonzero suite; the runner completes normally with zero tests. | Test check and overall are `FAIL`. If discovery crashed or is ambiguous instead, they are `BLOCKED`; neither path passes. |
| QG-07 | Dirty working tree | Relevant uncommitted changes exist before the gate; policy does not require a clean tree. | Checks still run, dirty state is explicit, and results are based on that state. Dirtiness alone does not force FAIL. |
| QG-08 | FAST passes, FULL fails | FAST checks pass; a FULL-only integration or regression check fails. | FAST remains `PASS`; FULL is `FAIL`; FAST evidence is never presented as a FULL pass. |
| QG-09 | Domain invariant failure | Standard tests pass; a required project-specific invariant executes and fails. | Domain check and overall are `FAIL`. |
| QG-10 | Check command crashes | Required validator terminates because of tool/configuration failure before a trustworthy validation result. | Check and overall are `BLOCKED`, with crash evidence; never PASS. |
| QG-11 | Stale previous result | A prior artifact says PASS, but `HEAD`, diff, relevant untracked content, configuration, or environment changed and no trustworthy content binding exists. | Prior evidence is stale; checks rerun. If they cannot rerun, overall is `BLOCKED`. |
| QG-12 | Existing regression remains valid | The new capability is added to this template and all existing structural/template checks still pass. | Existing skills validate, links resolve, approval boundaries remain unchanged, and overall implementation validation passes. |
| QG-13 | Exit zero contradicts output | A required command exits zero but explicitly reports failed tests, errors, or omits configured proof of execution. | Reliable explicit failure is `FAIL`; otherwise the contradiction is `BLOCKED`; never PASS. |
| QG-14 | FULL scope accidentally narrowed | The configured FULL suite should cover all regressions, but only one file or newly added tests are run. | Required FULL coverage is untrusted and overall is `BLOCKED`. |
| QG-15 | Unexpected skipped-test increase | Required suite exceeds its configured skip allowance or adds unexplained skips that may remove required coverage. | Exceeded policy is `FAIL`; ambiguous coverage is `BLOCKED`; skip counts remain visible. |
| QG-16 | In-place content change | During validation, a file already marked `M` or an existing untracked file is rewritten without changing its Git status category. | Before/after diff and untracked-content fingerprints differ; earlier evidence is stale and overall cannot PASS until validation is rerun against the final content. |
| QG-17 | Secret-bearing command or output | A required check receives an inline token or prints a credential-like value. | The report replaces sensitive values with explicit redaction, preserves reproducible non-sensitive structure and failure meaning, and becomes `BLOCKED` if safe sanitization cannot be established. |
| QG-18 | Staged or untracked whitespace error | A staged-only file or non-ignored untracked file contains a trailing-whitespace error while the unstaged tracked diff is clean. | Patch integrity is `FAIL`; the gate cannot rely on `git diff --check` alone or report PASS. |
| QG-19 | Angle-bracket or reference-style missing link | Markdown contains `[doc](<missing path/doc.md>)` or a reference definition whose relative destination is missing. | Link validation reports the unresolved path and FAILs; valid target syntax is not skipped merely because it uses angle brackets or a reference definition. |
| QG-20 | Invalid or short Markdown fence | A four-space- or tab-indented fence-like line precedes a missing relative link, or a valid fence is followed by a same-marker closer shorter than its opener. | Four-space- and tab-indented syntax do not open a fence, and a short closer does not close one; links outside valid fences remain discoverable and links still inside a valid fence remain excluded. |
| QG-21 | Reference-definition indentation boundary | The fixture contains tab-indented bare and angle-bracket definitions plus three-literal-space bare and angle-bracket definitions. | Both tab-indented lines contribute no target, while both three-space definitions contribute their expected targets; neither false failures nor a regression to accepting only zero to two spaces can pass. |
| QG-22 | Incident boundary | One scoped test fails in one case, while another run produces many unrelated failures plus evidence that the environment or persisted state may be corrupt. | The scoped failure remains in normal debug handling; the broader integrity case retains its FAIL/BLOCKED gate evidence and activates `incident-recovery` before ordinary repair or review progression. |
| QG-23 | Required dependency-security result | Dependency/security-sensitive files changed, repository policy requires `dependency-security-check`, and it returns `FINDINGS`; separate cases return `BLOCKED`, omit the invocation, or claim `NOT_APPLICABLE` without policy support. | The gate maps `FINDINGS` to required `FAIL`, preserves `BLOCKED`, treats a missing result as `BLOCKED`, rejects unjustified non-applicability, and never reports overall `PASS`; it does not duplicate the security analysis. |

## Test-design review

- [x] Every acceptance criterion maps to one or more scenarios or an explicit structural check.
- [x] Normal, failure, blocked, non-applicable, dirty-state, content-staleness, patch-category coverage, Markdown syntax coverage, scope, skip, environment, secret-exposure, and domain-invariant risks are represented.
- [x] FAST and FULL cannot be conflated in either the contract or scenarios.
- [x] Zero discovery, exit-code contradictions, missing expected checks, narrowed scope, in-place content changes, staged/untracked whitespace, unparsed valid link forms, invalid fence boundaries, and tab-indented reference-definition false positives cannot distort the result.
- [x] Scenario outcomes are observable and do not prescribe a language-specific implementation.
- [x] Responsibility boundaries prevent overlap with dependency-security analysis, implementation, debugging, review, release readiness, and Git authorization.
- [x] Incident escalation is narrowly routed without making quality-gate own containment, recovery, or resumption.
- [x] Dependency-security integration is conditional and result-based; the gate does not absorb or duplicate its logic.
- [x] No scenario introduces task handoff, project health, or another excluded capability.
- Reviewer: revision 1 internal requirement-to-scenario review completed 2026-09-19; revision 2 incident-routing review was independently reviewed and approved by the user on 2026-09-22; revision 3 dependency-security integration review completed 2026-09-22; revision 4 removes duplicated secret-review ownership from generic repository validation and awaits final human review.

## Validation and traceability

- Skill structure/frontmatter: bundled `skill-creator` quick validator.
- Specification and scenario coverage: manual requirement-to-scenario review above.
- Behaviour: manual trace of QG-01 through QG-23 against the implemented skill and repository profile.
- Documentation and path consistency: repository-wide relative Markdown link check and search for stale workflow wording.
- Existing regression: validate every repository skill and preserve existing workflow/approval behaviour.
- Whitespace and patch integrity: repository-profile checks for unstaged tracked, staged, and all non-ignored untracked files.
- Repository tests: none currently exist; this instruction-only template has no executable product test harness.

### Manual scenario results

| Scenario | Result | Evidence in the implemented capability |
| --- | --- | --- |
| QG-01 | Pass | Defines separate FAST and FULL execution, evidence, aggregation, and the FULL-only independent-review conclusion. |
| QG-02 | Pass | Static validation explicitly includes lint; any required validation violation is FAIL and controls the overall result. |
| QG-03 | Pass | Requires test failure evidence to be preserved and classifies an established required failure as FAIL. |
| QG-04 | Pass | Missing required tools or dependencies are BLOCKED and can never become NOT_APPLICABLE. |
| QG-05 | Pass | NOT_APPLICABLE requires an explicit authoritative reason and does not control other required checks. |
| QG-06 | Pass | A normal expected suite with zero tests is FAIL; incomplete or untrusted discovery is BLOCKED. |
| QG-07 | Pass | Captures and reports dirty state while making cleanliness a failure only when project policy requires it. |
| QG-08 | Pass | Prohibits relabelling FAST evidence as FULL and requires a separate FULL profile result. |
| QG-09 | Pass | Includes required domain validation in the same per-check and overall FAIL aggregation. |
| QG-10 | Pass | Classifies tool/configuration crashes, interruptions, and timeouts as BLOCKED unless reliable failure evidence exists. |
| QG-11 | Pass | Rejects stale PASS evidence unless it is trustworthily bound to identical code, diff, relevant untracked content, configuration, and environment. |
| QG-12 | Pass | All repository skills validate in Python UTF-8 mode, relative links resolve, and existing approval boundaries remain present. |
| QG-13 | Pass | Explicit failure output overrides exit zero; unresolved contradictions or missing success evidence are BLOCKED. |
| QG-14 | Pass | Focused, single-file, changed-only, or newly added tests cannot substitute for required FULL coverage. |
| QG-15 | Pass | Exceeded skip policy is FAIL; unexplained coverage-affecting skips are BLOCKED; counts remain visible. |
| QG-16 | Pass | Requires complete staged/unstaged diff and relevant untracked-content fingerprints before and after validation, so an in-place rewrite invalidates earlier evidence even when status categories remain unchanged. |
| QG-17 | Pass | Requires secret-safe command representations and sanitized output, uses explicit redaction placeholders, and blocks evidence that cannot be sanitized without losing validation meaning. |
| QG-18 | Pass | The repository profile runs separate unstaged and staged checks, enumerates every non-ignored untracked file, and checks each untracked file with `git diff --no-index --check`. |
| QG-19 | Pass | The parser recognizes angle-bracket targets containing spaces and reference definitions, excludes fenced/inline code examples without losing code-formatted link labels, and resolves every discovered relative target. |
| QG-20 | Pass | The parser fixture treats four-space- and tab-indented fence-like syntax as ordinary content and verifies that a closing fence must match the opening marker and be at least as long as the opener. |
| QG-21 | Pass | The parser fixture explicitly covers tab-indented bare and angle definitions as excluded, plus three-space bare and angle definitions as recognized with their two expected destinations. |
| QG-22 | Pass | Failure handling distinguishes a scoped defect from broader integrity evidence and preserves the gate classification while routing only the latter to incident recovery. |
| QG-23 | Pass | The profile conditionally invokes or consumes dependency-security evidence, maps required FINDINGS/BLOCKED/missing/unsupported non-applicability to a non-PASS gate state, and prohibits duplicate security analysis. |

### Repository check results

- Repository-defined FULL profile: pass after the staged/untracked patch-integrity, Markdown-target syntax, and Markdown fence-boundary review fixes.
- Patch integrity: pass for unstaged tracked, staged, and all current non-ignored untracked files.
- Markdown links: the angle-with-spaces, reference, space/tab indentation, tab-indented reference-definition, and fence-length parser fixtures pass, and all repository-relative targets resolve.
- Content freshness: complete staged/unstaged diff and relevant untracked-file fingerprints matched before and after the profile.
- Bundled quick validation: all twelve repository skills pass in Python UTF-8 mode.
- Quality-gate contract: all four states, both modes, machine-readable fields, and QG-01 through QG-23 definitions/results pass structural checks.
- Dependency-security contract: all four states, all four risk levels, both machine-readable fields, and DSC-01 through DSC-16 definitions/results pass structural checks.
- Incident-recovery contract: all nine states, the `DISPROVED` false-alarm transition, and IR-01 through IR-15 definitions/results pass structural checks.
- Version alignment: `VERSION`, README references, and the project-status baseline example agree on `1.7.1`.
- Automated repository tests: not applicable; this template intentionally has no executable product test harness.
- Final complete-diff inspection: recorded in the task report after the final working-tree validation run.
