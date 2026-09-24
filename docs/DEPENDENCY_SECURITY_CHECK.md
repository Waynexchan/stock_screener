# Behaviour specification: dependency security check

## Identity and change control

- Specification: `docs/DEPENDENCY_SECURITY_CHECK.md`
- Revision: 1
- Status: reviewed
- Last updated: 2026-09-22
- Related decision record: none; the capability extends the reusable workflow without changing existing approval policy.

## Intent and scope

`dependency-security-check` gives an AI coding agent a lightweight, local-first way to review dependency and repository-security changes. It gathers deterministic evidence where the repository or ecosystem provides it, applies proportionate judgment, and reports whether the defined check passed, found issues, was blocked, or did not apply.

It owns:

- dependency additions, removals, version changes, and their justification;
- dependency manifest, lockfile, and package-manager configuration consistency;
- package identity, source, provenance, and unexpected transitive-impact review;
- known-vulnerability evidence from already available project or ecosystem tooling;
- accidental secret or credential exposure checks for relevant repository changes;
- ignore-rule safety for likely sensitive local files;
- dependency-related install, build-hook, downloaded-script, and arbitrary-command risk; and
- security-sensitive repository configuration changes directly related to dependencies, credentials, or package acquisition.

It does not become a general security-audit framework. It does not own application-security reasoning, incident containment or recovery, release readiness, project health, monitoring, CI infrastructure, vulnerability dashboards, dependency-update bots, deployment security, package installation, automatic upgrades, secret rotation, Git-history rewriting, or any Git/release approval.

### Responsibility boundaries

- `dependency-security-check` owns the evidence and judgment listed above and emits its four-state result plus a proportionate risk classification.
- `quality-gate` remains the validation orchestrator. It may invoke or consume this check when repository policy makes it required, but it does not duplicate dependency or secret-review logic.
- `code-review` owns application and design security, including authentication, authorization, injection, unsafe execution, dangerous code patterns, and security flaws unrelated to dependency/repository configuration.
- `incident-recovery` owns evidence preservation, containment, recovery, and verified resumption for likely real secret exposure, suspected compromise, corrupted state, or another security incident.
- `release-check` owns readiness for a named commit, merge, push, release, or other operational boundary.
- `project-dev-cycle` owns specification, implementation, validation, review sequencing, and the separate human approval gates.

A dependency-security result is evidence for quality-gate and review. It is not a claim that the code is secure or safe for production.

## Applicability and trigger contract

Run the check when the requested change or repository policy includes one or more of:

- a dependency addition, removal, version or constraint change;
- a dependency manifest, lockfile, package-manager configuration, resolution file, or package source change;
- environment/configuration handling or authentication/credential-storage configuration changes;
- a new or changed registry, package index, VCS/path dependency, direct URL, or downloaded executable source;
- dependency-related pre-install, post-install, build hook, bootstrap action, or arbitrary command changes; or
- a configured pre-review policy that requires this check.

Ordinary source-only edits do not require a heavyweight dependency audit unless repository policy says otherwise. When no trigger or policy applies, the result is `NOT_APPLICABLE` with the reason. A missing tool, ambiguous scope, or unavailable required check is never a reason for `NOT_APPLICABLE`.

Before evaluating, identify the review basis and relevant staged, unstaged, untracked, or commit-range changes; current manifests, lockfiles, package-manager configuration, ignore rules, and existing project security tooling; and the authoritative repository policy. Do not invent a package manager, lockfile requirement, scanner, or network dependency.

## Dependency justification contract

Every newly added direct dependency requires an explicit record of:

- dependency name and expected ecosystem/package manager;
- purpose and the functionality that requires it;
- whether the standard library or native tooling could reasonably satisfy the need;
- whether an existing direct dependency already provides the capability;
- runtime or development-only scope;
- known or observable transitive-dependency impact; and
- whether it is essential or optional.

Challenge convenience-only additions and require the smallest adequate dependency change. An alternative's existence does not automatically reject a dependency; use proportional judgment about correctness, maintenance, complexity, compatibility, and implementation risk. Do not add, remove, install, or upgrade a package as part of this check unless separately authorized through the normal development workflow.

## Package identity and provenance

Where local metadata and available tooling permit, verify the expected package name, ecosystem, source, and registry. Compare the change with repository conventions and flag for explicit review:

- names unusually similar to a known or intended package;
- a registry package changing to a VCS, local/path, or direct-URL dependency;
- a newly introduced alternate registry, index, mirror, or source;
- arbitrary download URLs or install-time executable retrieval; and
- unexplained source or integrity-metadata changes.

Describe suspicious or unusual evidence without asserting malicious intent that the evidence does not establish. Missing required provenance evidence is `BLOCKED`; unusual but inspectable provenance is `FINDINGS` until explicitly resolved.

## Manifest and lockfile consistency

Use the project's actual ecosystem and repository conventions. Determine whether a lockfile is expected rather than assuming every project needs one. Check, where applicable:

- manifest changes without the required lockfile update;
- lockfile changes without an understandable manifest or resolver reason;
- unexpectedly large or unrelated lockfile churn;
- declared constraints versus resolved versions;
- dependencies removed from manifests but retained unexpectedly in resolution state;
- duplicate or conflicting declarations; and
- package source, integrity, or metadata changes inconsistent with the intended dependency change.

An unresolved required manifest/lockfile inconsistency cannot produce `PASS`. Do not delete a lockfile or regenerate dependency state merely to silence the check.

## Known-vulnerability evidence

Use an appropriate repository-configured scanner or standard package-manager audit capability only when it is already available and applicable. Do not introduce a security SaaS, external platform, dependency, package manager, or scanner solely to run this skill.

For the vulnerability-evidence sub-check:

- `PASS` means the available tool and data reported no known vulnerability in its configured scope;
- `FINDINGS` means the tool reported one or more relevant known vulnerabilities;
- `BLOCKED` means required evidence could not be obtained or trusted because a tool, network, advisory database, ecosystem support, configuration, or execution result was unavailable or ambiguous; and
- `NOT_APPLICABLE` requires an authoritative reason that vulnerability scanning does not apply to this invocation.

A clean result means only that the available tool and data reported no known vulnerability. It never means the dependency or application is secure. Do not suppress warnings, disable scanning, or automatically change versions to obtain a clean result.

## Secret and credential exposure

Inspect relevant changed content, tracked/staged file names, ignore behaviour, and existing repository tooling for accidental exposure of API keys, passwords, access tokens, private keys, cloud/database credentials, authentication cookies, signing secrets, and equivalent sensitive values. Prefer existing deterministic secret-scanning tooling when configured, but do not add a scanner dependency solely for this skill. Review likely sensitive files and changed lines even when no specialized scanner exists.

Never reproduce a detected value. Report only a redacted file/location and finding type, for example `config.py:18 — potential API credential [REDACTED]`. Synthetic examples must be unmistakably fake and must not resemble a usable credential.

When a likely real secret is detected:

1. stop displaying, copying, or further testing the value;
2. identify affected tracked, staged, or untracked paths without reproducing it;
3. determine through secret-safe Git evidence whether it may have entered history;
4. do not claim that working-tree deletion resolves historical or external exposure;
5. classify the check as `FINDINGS` with `CRITICAL` risk and activate or recommend `incident-recovery` according to repository policy;
6. require the appropriate human/operator decision for rotation or revocation; and
7. never rotate credentials, rewrite history, or destructively remove evidence automatically.

If a required secret-scanning command fails or its evidence cannot be safely reported, the sub-check is `BLOCKED`, never `PASS`. A local `.env` or equivalent file that is ignored and untracked is not by itself a finding; report only the relevant confirmation without reading or reproducing its contents.

## Ignore-file and install/build safety

When relevant sensitive-file handling changes, inspect ignore rules for likely local environment, credential, generated authentication, and temporary key material. Do not add broad patterns that could conceal source, configuration, examples, schemas, or other reviewable files. A safe example/template exception must contain placeholders only.

Inspect changed dependency-related lifecycle scripts and configuration for pre-install, post-install, build hooks, bootstrap commands, arbitrary shell execution, and downloaded executable scripts. Install hooks are not categorically prohibited, but newly introduced execution requires visibility, purpose, source, scope, and risk justification.

## AI-agent dependency rules

The agent must not:

- install random packages for trivial functionality;
- add a dependency without the required justification;
- suppress dependency-security warnings or disable required scanning;
- delete or omit a required lockfile to avoid resolution conflicts;
- add secrets or real credentials to source, tests, examples, documentation, or logs;
- silently change a registry or package source; or
- automatically make unrelated or major dependency upgrades.

When a new dependency is justified, the normal development workflow must explain the need and alternatives, make the smallest dependency change, update the lockfile when repository convention requires it, and rerun relevant validation. The check itself remains read-only unless the user separately requested implementation or remediation.

## Risk classification

Assign the highest evidence-supported level and explain it without sensationalizing:

- `LOW` — a small, understood development-only dependency or equivalent low-impact configuration change.
- `MEDIUM` — a new runtime dependency, moderate transitive impact, or material but conventional dependency/security configuration change.
- `HIGH` — a security-sensitive dependency; custom registry, VCS, path, or direct-URL source; major replacement; unexplained large lockfile churn; install-time code execution; or a dependency affecting authentication, networking, parsing, deserialization, cryptography, or command execution.
- `CRITICAL` — likely real credential exposure, a known actively dangerous dependency state supported by evidence, or a change capable of serious compromise.

Risk level does not replace the four-state result and is not an authorization decision. Classify risk only when the check applies; an overall `NOT_APPLICABLE` result uses risk `NOT_APPLICABLE` rather than implying that an unassessed change is low risk.

## State model and aggregation

Use exactly one overall state:

- `PASS` — all required applicable dependency/security checks completed for the review scope and no unresolved finding remains.
- `FINDINGS` — checks ran sufficiently to identify one or more issues requiring review or remediation.
- `BLOCKED` — required evidence could not be obtained or trusted and no established finding already determines `FINDINGS`.
- `NOT_APPLICABLE` — authoritative scope and policy establish that no trigger applies.

Report concurrent blocked evidence even when `FINDINGS` controls the overall state. Never report `PASS` when a required vulnerability scan did not run, a required secret scan failed, dependency state is inconsistent, lockfile state is unresolved, the review scope is ambiguous, or required evidence is stale.

## Output contract

Produce a concise, secret-safe report using this shape or a project-defined equivalent that preserves all fields:

```text
DEPENDENCY SECURITY CHECK
Scope: <review basis and relevant files>

Dependency changes:
- Added: <names or none>
- Removed: <names or none>
- Updated: <name old -> new, or none>

Justification: <per-added-dependency summary or NOT_APPLICABLE>
Manifest/lockfile: <PASS|FINDINGS|BLOCKED|NOT_APPLICABLE> — <evidence>
Known vulnerability scan: <PASS|FINDINGS|BLOCKED|NOT_APPLICABLE> — <tool/data evidence>
Secret exposure check: <PASS|FINDINGS|BLOCKED|NOT_APPLICABLE> — <redacted evidence>
Package source/provenance: <PASS|FINDINGS|BLOCKED|NOT_APPLICABLE> — <evidence>
Install/build script review: <PASS|FINDINGS|BLOCKED|NOT_APPLICABLE> — <evidence>
Ignore-file safety: <PASS|FINDINGS|BLOCKED|NOT_APPLICABLE> — <evidence>

Risk classification: <LOW|MEDIUM|HIGH|CRITICAL|NOT_APPLICABLE> — <reason>
Overall: <PASS|FINDINGS|BLOCKED|NOT_APPLICABLE>
Notes: <limitations, review/incident routing, and unperformed actions>
DEPENDENCY_SECURITY_RESULT=<PASS|FINDINGS|BLOCKED|NOT_APPLICABLE>
DEPENDENCY_SECURITY_RISK=<LOW|MEDIUM|HIGH|CRITICAL|NOT_APPLICABLE>
```

Do not use `SECURE`, `SAFE FOR PRODUCTION`, `READY TO MERGE`, or equivalent language.

## Quality-gate integration

Repository policy decides whether and when `quality-gate` invokes this capability. FAST may omit heavyweight dependency checks unless dependency/security-sensitive triggers changed, while FULL should invoke it when such triggers changed or the repository profile otherwise requires it.

When the dependency-security check is required, `quality-gate` maps:

- dependency-security `PASS` to gate-check `PASS`;
- dependency-security `FINDINGS` to gate-check `FAIL`;
- dependency-security `BLOCKED` to gate-check `BLOCKED`; and
- dependency-security `NOT_APPLICABLE` to gate-check `NOT_APPLICABLE` only when authoritative policy confirms non-applicability.

A missing required invocation or result is `BLOCKED`. Required `FINDINGS` or `BLOCKED` prevents overall quality-gate `PASS`. Quality-gate consumes the result and evidence; it does not reimplement package, vulnerability, secret, provenance, or install-script logic.

The workflow is acyclic: dependency-security supplies evidence to quality-gate; ordinary remediation returns through `project-dev-cycle`; likely exposure or compromise routes to `incident-recovery`; application-security reasoning remains with `code-review`; and release readiness remains with `release-check`.

## Acceptance criteria

1. The capability is reusable, ecosystem-aware, tool-agnostic, local-first, and does not add a dependency, external service, CI system, update bot, monitoring system, or general security framework.
2. Trigger rules cover dependency, manifest, lockfile, source, install/build, environment/credential handling, and configured pre-review changes without forcing heavyweight scans for every source-only edit.
3. Every added dependency receives the complete justification record and unnecessary additions are challenged proportionately rather than automatically rejected.
4. Package identity, ecosystem, provenance, registry/source changes, VCS/path/direct-URL dependencies, and suspicious naming are reviewed without unsupported claims of malicious intent.
5. Manifest and lockfile expectations follow repository convention; stale, unexplained, conflicting, or unexpectedly broad dependency state cannot pass.
6. Available configured vulnerability tooling supplies limited known-vulnerability evidence; unavailable required tooling is `BLOCKED`, and no result claims general security.
7. Relevant changes are checked for secret exposure without printing values; likely real exposure produces a redacted `CRITICAL` finding and incident-recovery escalation without automatic rotation or history rewriting.
8. Ignore rules and dependency-related install/build execution receive focused review without blindly hiding files or banning justified hooks.
9. The result uses only `PASS`, `FINDINGS`, `BLOCKED`, or `NOT_APPLICABLE`, includes `LOW` through `CRITICAL` risk, follows deterministic aggregation, and never substitutes positive-sounding security or production-readiness language.
10. Quality-gate may orchestrate a configured invocation and must prevent overall PASS for required `FINDINGS`, `BLOCKED`, missing, or unjustified `NOT_APPLICABLE` results without duplicating security logic.
11. Code-review, incident-recovery, release-check, task-handoff, SDD, research governance, and every human approval boundary retain their existing responsibilities.
12. The implementation and documentation introduce no unrelated functionality and all existing repository validation continues to pass.

## Validation scenarios

| ID | Scenario | Expected observable result |
| --- | --- | --- |
| DSC-01 | No dependency changes: an ordinary source-only change has no configured security-check requirement. | Reports `NOT_APPLICABLE` or the explicitly configured lightweight result; no unnecessary heavyweight vulnerability scan runs. |
| DSC-02 | Valid new development dependency: a legitimate test/lint package is introduced with normal registry metadata. | Records the full justification, confirms manifest/lockfile consistency, runs available required evidence, and reports the supported result with `LOW` risk when no issue remains. |
| DSC-03 | Unnecessary dependency: a package duplicates adequate standard-library or existing-project capability. | Reports `FINDINGS` requiring justification or reconsideration; does not automatically remove the package. |
| DSC-04 | Runtime dependency added. | Applies greater provenance, transitive-impact, manifest/lockfile, and vulnerability scrutiny and assigns at least `MEDIUM` risk when otherwise conventional. |
| DSC-05 | Manifest changed but an expected lockfile is stale. | Reports `FINDINGS`; never `PASS`. |
| DSC-06 | A small manifest edit creates large unexplained lockfile churn. | Reports `FINDINGS` for investigation instead of silently accepting the change. |
| DSC-07 | A required vulnerability scanner, network source, or advisory database is unavailable. | Vulnerability evidence and overall result are `BLOCKED` when no finding already controls the overall state; never `PASS`. |
| DSC-08 | An available scanner reports a known vulnerability. | Reports `FINDINGS` with affected package and non-secret evidence; does not upgrade automatically. |
| DSC-09 | A tracked configuration change contains a likely real API key or token. | Stops reproducing the value, reports a redacted `CRITICAL` finding, checks history exposure safely, and activates or recommends incident-recovery without rotation or history rewriting. |
| DSC-10 | A local `.env` exists but is ignored and untracked. | Confirms the relevant ignore/untracked state without reading or printing the contents and does not raise a false exposure finding. |
| DSC-11 | A credential or private-key file is staged. | Reports a redacted `FINDINGS` result with `CRITICAL` risk and incident-recovery routing; performs no destructive cleanup. |
| DSC-12 | A new custom package index, VCS dependency, or direct URL is introduced. | Reports `FINDINGS` with `HIGH` risk until package identity, source, and reason receive explicit review. |
| DSC-13 | Dependency setup introduces a pre/post-install shell action or downloaded executable. | Reports `FINDINGS` requiring purpose, source, scope, and execution-risk justification. |
| DSC-14 | Dependency evidence passes but unrelated application code contains a security flaw. | Does not claim the application is secure; routes application-level reasoning to code-review. |
| DSC-15 | Repository policy requires the check; dependency files change and the result is `FINDINGS`. | FULL quality-gate maps it to required `FAIL` and cannot report overall `PASS`. |
| DSC-16 | The new capability is added to the template. | Existing context-resume, quality-gate, task-handoff, incident-recovery, SDD, code-review, release-check, research governance, and approval boundaries remain intact. |

## Test-design review

- [x] Every acceptance criterion maps to one or more scenarios or an explicit structural check.
- [x] Normal, non-applicable, dependency-addition, unnecessary-dependency, runtime, stale-lockfile, lockfile-churn, unavailable-tool, known-vulnerability, secret-exposure, ignored-file, sensitive-file, custom-source, install-hook, application-security-boundary, and quality-gate-integration cases are covered.
- [x] Failure and missing-evidence cases cannot produce `PASS`.
- [x] Scenarios assert observable results rather than a language-specific implementation.
- [x] The design does not add or require an external service, dependency, scanner, CI system, bot, dashboard, or general security framework.
- [x] Responsibility boundaries and the acyclic workflow were checked against the existing skills.
- Reviewer: revision 1 internal requirement-to-scenario review completed 2026-09-22; final independent change review remains required.
- Unresolved questions: none.

## Validation and traceability

- Skill structure/frontmatter: bundled `skill-creator` quick validator.
- Specification and scenario coverage: manual requirement-to-scenario review above.
- Behaviour: manual trace of DSC-01 through DSC-16 against the implemented skill after implementation.
- Quality-gate integration: structural contract check and manual trace of required result mapping.
- Documentation and path consistency: repository-wide relative Markdown link check and stale-wording search.
- Existing regression: validate every repository skill and preserve workflow/approval behaviour.
- Whitespace and patch integrity: repository-profile checks for unstaged tracked, staged, and every non-ignored untracked file.
- Automated repository tests: not applicable; this instruction-only template intentionally has no executable product test harness, and adding one for prose-governed agent behaviour would add unjustified tooling.
- Manual validation and residual risk: agent behaviour is instruction-driven and remains partly judgment-dependent across ecosystems; manual scenario review is required now, and downstream projects should configure deterministic package-manager/security tools where appropriate rather than this template introducing a universal scanner.

### Manual scenario results

| Scenario | Result | Evidence in the implemented capability |
| --- | --- | --- |
| DSC-01 | Pass | Applicability rules make an untriggered source-only change `NOT_APPLICABLE` and prohibit a forced heavyweight audit unless policy requires one. |
| DSC-02 | Pass | The justification record covers purpose, alternatives, scope, transitive impact, and essential/optional status; ordinary development-only scope maps to `LOW` when no issue remains. |
| DSC-03 | Pass | Convenience-only additions are challenged and unresolved justification produces `FINDINGS`, while the read-only check cannot remove the dependency. |
| DSC-04 | Pass | Runtime scope requires provenance, transitive, dependency-state, and available vulnerability evidence and maps conventional runtime impact to at least `MEDIUM`. |
| DSC-05 | Pass | A manifest change with an expected stale lockfile is an unresolved dependency-state finding and cannot pass. |
| DSC-06 | Pass | Unexpected large or unrelated lockfile churn is explicitly reviewed and remains `FINDINGS` until explained. |
| DSC-07 | Pass | Missing or untrusted required tool, network, advisory-data, ecosystem, configuration, or result evidence is `BLOCKED`, never PASS or non-applicable. |
| DSC-08 | Pass | A reported known vulnerability produces `FINDINGS`; automatic upgrade and warning suppression are prohibited. |
| DSC-09 | Pass | Likely real secret handling stops reproduction, emits redacted path/location evidence, checks history safely, assigns `CRITICAL`, and routes to incident recovery without rotation or rewriting. |
| DSC-10 | Pass | The skill confirms only Git ignore/untracked state for a local `.env` and prohibits reading or printing its contents or treating that state alone as exposure. |
| DSC-11 | Pass | Tracked/staged sensitive-file review produces a redacted `CRITICAL` finding and incident routing without destructive cleanup. |
| DSC-12 | Pass | Alternate registries, VCS/path/direct URLs, and arbitrary downloads require explicit provenance review and support `HIGH` risk without unsupported malicious-intent claims. |
| DSC-13 | Pass | New lifecycle hooks, shell execution, bootstrap actions, and executable downloads require explicit purpose, source, scope, and risk justification. |
| DSC-14 | Pass | The skill explicitly limits clean evidence to its defined scope and assigns application/design security to `code-review`. |
| DSC-15 | Pass | Quality-gate integration maps required dependency-security `FINDINGS` to FAIL, `BLOCKED` or missing evidence to BLOCKED, and rejects unjustified non-applicability without duplicating logic. |
| DSC-16 | Pass | Workflow integration preserves context recovery, SDD, handoff, incident, review, release, research, and separate human approval boundaries and introduces no dependency or external system. |
