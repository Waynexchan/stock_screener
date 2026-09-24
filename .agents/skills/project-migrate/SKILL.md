---
name: project-migrate
description: Non-destructively migrate an existing repository toward a newer AI-agent workflow template baseline while preserving project-specific knowledge and safeguards. Use for gradual template adoption or upgrades.
---

# Project migration

Bring an existing project toward a target workflow template baseline through explicit comparison and minimal, additive changes. Application behavior is outside scope unless separately requested and approved.

If the request will modify files, use this skill within `project-dev-cycle`: complete that cycle's repository, dirty-work, and branch preflight before making any migration edit, then continue its planning, verification, review, and approval boundaries. A read-only migration assessment or plan does not require an implementation branch.

## 1. Inventory and compare

1. Inspect Git state, repository instructions, agent skills, workflow and governance documents, project structure, behavioural specifications and tests, durable project context, operational guidance, and verification commands.
2. Identify the current workflow template baseline if recorded and the requested target baseline. Treat an absent baseline as unknown, not as the oldest version.
3. Compare existing behavior and files with the target standard. Classify each difference as a reusable addition, a project-specific rule to preserve, an intentional local divergence, an obsolete template artifact supported by evidence, or a conflict requiring a decision.
4. Produce a migration plan before editing, including intended files, preserved rules, conflicts, validation, and rollback considerations.

Never blindly overwrite `AGENTS.md`, an existing skill, or project documentation. Never delete a local safety control merely because it is absent from the template.

## 2. Preserve project authority

Preserve project-specific production safeguards, specifications, business/domain knowledge, architecture decisions, data-integrity and research-governance rules, operational procedures, test and canonical validation commands, deployment and release constraints, and security requirements. Prefer additive or narrowly scoped edits and reuse existing structures.

When the target baseline calls for one-command local validation, reuse a suitable existing aggregate entry point or establish one through the project's existing tooling where practical, then document it in repository instructions and status. Do not invent irrelevant checks or create a competing entry point. If aggregation is impractical, document the required command set and limitation.

Report conflicts between existing and target rules explicitly. If resolving a conflict requires human judgment, stop that portion of the migration and request direction. Do not silently change CI, deployment, application or strategy behavior, production data, secrets, or external services.

## 3. Apply and validate

Apply only the approved, minimal migration. Record the target workflow baseline in the repository's chosen status or governance document without conflating it with the application/package version.

Run project-defined validation appropriate to changed files, inspect the complete diff, verify internal references and discovery, and check that no local knowledge, specification, safety rule, secret, runtime data, or unrelated file was lost or introduced. Confirm a fresh agent can recover the workflow and durable context after a restart. Review the migration against both the existing project rules and target standard.

Report additions, preserved local behavior, intentional divergences, unresolved conflicts, baseline changes, commands and results, and residual risk. Continue through the surrounding `project-dev-cycle` for review and any separately approved commit, merge, or push work.
