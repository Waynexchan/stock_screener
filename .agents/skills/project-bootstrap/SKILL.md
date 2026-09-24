---
name: project-bootstrap
description: Safely customize a newly created template-derived repository for its real project without recreating the template or inventing project facts. Use after GitHub Use this template or an equivalent copy.
---

# Project bootstrap

Convert a newly created copy of this workflow template into a project-specific, AI-agent-enabled repository. Preserve the reusable workflow and customize only what evidence and the user's stated intent support.

If the request will modify files, use this skill within `project-dev-cycle`: complete that cycle's repository, dirty-work, and branch preflight before making any bootstrap edit, then continue its planning, verification, review, and approval boundaries. A read-only bootstrap assessment does not require an implementation branch.

## 1. Discover the new project

1. Inspect repository instructions, Git state, structure, manifests, configuration, existing code, and documentation before editing.
2. Establish the intended purpose, users, non-goals, architecture actually present, technology and tooling, operational constraints, business/domain rules, behavioural-spec location, durable project-memory location, and default branch conventions.
3. Locate template placeholders and distinguish reusable template rules from content that must become project-specific.
4. Identify the workflow template baseline from the template's version mechanism. Record it in the project's chosen status or governance document; this baseline is separate from any application or package version.

Do not invent commands, architecture, dependencies, or external integrations. Mark unknown information as unresolved.

## 2. Customize minimally

Update the project purpose and setup guidance, architecture overview, verified development and test commands, constraints, current status, durable project memory, behavioural specifications, important decisions, and project-specific `AGENTS.md` additions where appropriate. Reuse existing artifacts; if no suitable artifacts exist, adapt the status, memory, specification, and decision templates supplied here. Preserve reusable skills and workflow safety rules unless a documented project requirement supersedes them.

Where practical, identify or establish one canonical local validation command using the project's existing tooling and document it in repository instructions and status. It should aggregate the relevant health checks without fabricating unnecessary checks or duplicating a suitable existing entry point. If no single command is practical, document the required commands and the limitation.

Do not add unnecessary frameworks or dependencies, recreate files that already serve the purpose, configure external services automatically, or write secrets into repository files. Keep examples and placeholders clearly identifiable until replaced with verified facts.

## 3. Validate and report

Inspect the complete diff and verify that instructions, paths, and commands match the repository; a fresh agent can recover current state, durable context, decisions, specifications, tests, and validation guidance from repository artifacts; the core workflow remains discoverable; no secrets or runtime artifacts were introduced; and unresolved placeholders are listed.

Report what was customized, the recorded template baseline, verified commands, validation results, preserved template components, and unresolved information. Continue through the surrounding `project-dev-cycle` for review and any separately approved commit, merge, or push work.
