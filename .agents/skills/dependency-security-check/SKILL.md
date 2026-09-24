---
name: dependency-security-check
description: Review dependency and repository-security changes for justification, manifest/lockfile consistency, provenance, known-vulnerability evidence, secret exposure, ignore safety, and install/build risk. Use when dependency or security-sensitive configuration changes, or when repository policy requires it; do not use as a general security audit.
---

# Dependency security check

Evaluate dependency and directly related repository-security changes under the [dependency-security-check specification](../../../docs/DEPENDENCY_SECURITY_CHECK.md). Keep the check local-first, ecosystem-aware, evidence-driven, and read-only unless the user separately authorized implementation or remediation.

This skill owns dependency-change justification, manifest/lockfile consistency, package identity and source, available known-vulnerability evidence, changed-content secret exposure, relevant ignore rules, and dependency-related install/build execution. It does not replace application-security reasoning in `code-review`, incident handling in `incident-recovery`, orchestration in `quality-gate`, release readiness in `release-check`, or any human approval gate.

## 1. Decide applicability and establish scope

Run when a dependency is added, removed, or updated; a manifest, lockfile, package-manager configuration, registry, index, VCS/path/direct-URL source, environment/credential handling rule, authentication storage configuration, or dependency-related install/build hook changes; or repository policy requires the check before review.

Do not force a heavyweight audit for an ordinary source-only edit unless policy requires one. Report `NOT_APPLICABLE` with the authoritative reason when no trigger applies. Missing tools, unclear scope, or unavailable required evidence are not non-applicability.

Identify the exact review basis and relevant staged, unstaged, untracked, or commit-range changes. Inspect applicable repository instructions, manifests, lockfiles, package-manager configuration, ignore rules, existing security tools, and changed install/build mechanisms. Do not invent an ecosystem, lockfile requirement, scanner, command, or network dependency.

## 2. Review dependency need and scope

For each newly added direct dependency, record:

- name, ecosystem, and expected package manager;
- purpose and required functionality;
- standard-library or native alternatives considered;
- existing dependencies that might already provide the capability;
- runtime or development-only scope;
- known or observable transitive impact; and
- essential or optional status.

Challenge convenience-only additions and prefer the smallest adequate change, but do not reject a dependency solely because an alternative exists. Judge correctness, maintenance, compatibility, complexity, and risk proportionately. Never install, remove, or upgrade a package merely to complete this read-only check.

## 3. Check identity, provenance, and dependency state

Use local metadata and existing tooling where available to verify the expected package name, ecosystem, registry/source, and integrity metadata. Flag unusual names, new alternate indexes or registries, registry-to-VCS/path/direct-URL changes, arbitrary download URLs, and unexplained source or integrity changes for explicit review. Describe evidence without claiming malicious intent that it does not establish.

Apply the repository's actual dependency convention. Determine whether a lockfile is expected, then review:

- manifest changes without the required lockfile update;
- lockfile changes without an understandable manifest or resolver reason;
- unexpectedly large or unrelated lockfile churn;
- declared constraints versus resolved versions;
- removals that remain unexpectedly in resolution state;
- duplicate or conflicting declarations; and
- package source, integrity, or metadata changes inconsistent with the intended change.

An unresolved required inconsistency is `FINDINGS`, never `PASS`. Do not delete a lockfile or regenerate state merely to silence the result.

## 4. Gather known-vulnerability evidence

Use a repository-configured scanner or standard package-manager audit command only when already available and applicable. Do not add a scanner, package manager, dependency, SaaS, or external platform solely for this check. Do not disable warnings, narrow configured scope, or automatically upgrade dependencies.

Classify the vulnerability sub-check:

- `PASS` — the available tool and data reported no known vulnerability in the configured scope;
- `FINDINGS` — the tool reported a relevant known vulnerability;
- `BLOCKED` — required evidence is unavailable or untrusted because the tool, network, advisory data, ecosystem support, configuration, or result is unavailable or ambiguous; or
- `NOT_APPLICABLE` — authoritative policy establishes that this evidence does not apply.

A clean scan says only that the available tool and data reported no known vulnerability. It never establishes that a dependency or application is secure.

## 5. Protect secrets and credentials

Inspect relevant changed content, tracked/staged file names, ignore behaviour, and existing tooling for API keys, passwords, access tokens, private keys, cloud/database credentials, authentication cookies, signing secrets, and equivalent values. Prefer configured deterministic tooling, while still reviewing likely sensitive changed files and lines. Never print a detected value; report only the path/location, finding type, and `[REDACTED]`.

For a likely real secret:

1. stop displaying, copying, or testing the value;
2. identify affected paths without reproducing it;
3. use secret-safe Git evidence to determine whether it may have entered history;
4. do not claim working-tree deletion resolves historical or external exposure;
5. report `FINDINGS` with `CRITICAL` risk and activate or recommend `incident-recovery` according to repository policy; and
6. require human/operator action for rotation or revocation when relevant.

Never rotate a credential, rewrite Git history, or destructively remove evidence automatically. A failed required secret scan or evidence that cannot be sanitized is `BLOCKED`, not `PASS`. An ignored, untracked local `.env` is not by itself a finding; confirm only its Git state without reading its contents.

## 6. Review ignore and execution safety

When sensitive-file handling changes, verify that likely local environment, credential, generated-authentication, and temporary-key material is ignored where appropriate. Do not add broad patterns that conceal source or reviewable configuration. Confirm that allowed example/template files contain placeholders only.

Inspect changed pre-install, post-install, build-hook, bootstrap, arbitrary-shell, and downloaded-executable behaviour. Hooks are not categorically banned, but new install-time execution requires explicit purpose, source, scope, and risk justification.

## 7. Enforce AI-agent boundaries

Do not install random packages for trivial work, add an unjustified dependency, suppress warnings, disable required scanning, remove a lockfile to avoid conflicts, commit secret files, place real credentials in examples/tests/docs, change package sources silently, or make unrelated major upgrades.

When implementation separately requires a package, explain the need and alternatives, make the smallest dependency change, update the lockfile when required, and rerun relevant validation through `project-dev-cycle`.

## 8. Classify risk and result

Assign the highest supported risk:

- `LOW` — small, understood development-only scope;
- `MEDIUM` — new runtime dependency or moderate transitive/configuration impact;
- `HIGH` — security-sensitive dependency, custom/VCS/path/direct-URL source, major replacement, unexplained large lockfile churn, install-time execution, or authentication/network/parsing/deserialization/cryptography/command-execution impact; or
- `CRITICAL` — likely real credential exposure, evidence of an actively dangerous dependency state, or serious compromise potential.

Classify risk only for an applicable check. When the overall result is `NOT_APPLICABLE`, report risk as `NOT_APPLICABLE` rather than implying that an unassessed change is low risk.

Use exactly one overall state:

- `FINDINGS` when sufficient evidence establishes any unresolved issue;
- otherwise `BLOCKED` when required evidence is unavailable, stale, ambiguous, or untrusted;
- otherwise `PASS` when every required applicable check completed and no unresolved issue remains; or
- otherwise `NOT_APPLICABLE` only when authoritative scope and policy establish that no trigger applies.

Keep concurrent blockers visible when `FINDINGS` controls the overall state. Never pass a required but unrun vulnerability or secret scan, inconsistent dependency state, unresolved lockfile, ambiguous scope, or stale evidence.

## 9. Integrate without duplicating ownership

When repository policy makes this a quality-gate check, return the evidence to `quality-gate`. The gate maps required `PASS` to PASS, `FINDINGS` to FAIL, `BLOCKED` to BLOCKED, and `NOT_APPLICABLE` to NOT_APPLICABLE only with an authoritative reason. A missing required invocation blocks the gate. Quality-gate orchestrates and aggregates; it does not repeat this skill's security logic.

Route ordinary remediation through `project-dev-cycle`. Route likely real exposure, compromise, or unsafe state to `incident-recovery`. Leave application/design security to `code-review` and boundary readiness to `release-check`. No result authorizes a commit, merge, push, release, deployment, rotation, history rewrite, or branch deletion.

## 10. Report

Report the review scope; added, removed, and updated dependencies; each new dependency's justification; manifest/lockfile, vulnerability, secret, provenance, install/build, and ignore-rule sub-results with secret-safe evidence; risk level and reason; limitations; incident/review routing; and explicitly unperformed actions.

Finish with:

```text
Overall: <PASS|FINDINGS|BLOCKED|NOT_APPLICABLE>
DEPENDENCY_SECURITY_RESULT=<PASS|FINDINGS|BLOCKED|NOT_APPLICABLE>
DEPENDENCY_SECURITY_RISK=<LOW|MEDIUM|HIGH|CRITICAL|NOT_APPLICABLE>
```

Never report `SECURE`, `SAFE FOR PRODUCTION`, `READY TO MERGE`, or equivalent language.
