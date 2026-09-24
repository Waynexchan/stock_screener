# Behaviour specification: <!-- short name -->

> Define what must be true before production implementation. Keep this proportionate to risk and link tests rather than duplicating implementation details. Update this record when behaviour intentionally changes; preserve important rationale in the decision log when needed.

## Identity and change control

- Specification ID / path:
- Version or revision:
- Status: <!-- draft, reviewed, accepted, or superseded -->
- Last updated:
- Supersedes / superseded by:
- Related decision record:

## Intent and scope

- Purpose / business intent:
- In scope:
- Out of scope:
- Relevant domain constraints and terminology:
- Compatibility expectations:

## Behavioural contract

- Inputs and preconditions:
- Outputs and observable effects:
- Valid cases:
- Invalid cases and error behaviour:
- Boundary behaviour:
- Missing-data behaviour:
- State transitions / persistence:
- Important invariants:
- Point-in-time, risk, compliance, or operational constraints:

## Acceptance criteria

1. <!-- Verifiable outcome. -->

## Test scenarios derived from the specification

| ID | Acceptance criterion / risk | Scenario and inputs | Expected observable outcome | Test level |
| --- | --- | --- | --- | --- |
| S-01 | <!-- AC or risk --> | <!-- normal, boundary, invalid, missing, failure, regression, or invariant case --> | <!-- outcome, not implementation detail --> | <!-- unit/integration/system/manual --> |

## Test-design review

- [ ] Every acceptance criterion has practical coverage or a documented reason it does not.
- [ ] Relevant boundaries, missing/invalid values, failure modes, invariants, and prior regressions are covered.
- [ ] Business/domain rules and compatibility expectations are represented correctly.
- [ ] Tests assert observable outcomes rather than mirror implementation structure.
- [ ] Shared assumptions that could make the implementation and tests wrong in the same way were challenged.
- [ ] Interactions with existing behaviour and missing scenarios were considered.
- Human checkpoint / reviewer: <!-- Required when project rules or change risk call for it. -->
- Unresolved questions: <!-- Stop rather than guess about material business behaviour. -->

## Validation and traceability

- Automated test locations:
- Targeted validation command:
- Affected regression command:
- Canonical repository validation command:
- Manual validation and residual risk: <!-- Explain any important unautomated behaviour and future automation recommendation. -->
- Related decisions / project memory:
