# Research hypothesis

> Record prior outcome exposure before using this document to govern further
> evaluation. For prospective work, freeze the specification before inspecting
> relevant outcomes. For retrospective or hypothesis-generating work, preserve
> and disclose what was already known; never relabel it as preregistered.
> Preserve the original record and create a new experiment or version for
> material changes.

## Identity

- Experiment ID:
- Hypothesis version:
- Date recorded:
- Specification frozen at: <!-- Timestamp with timezone. -->
- Prospective preregistration timestamp: <!-- Required only for PROSPECTIVE posture; otherwise NOT APPLICABLE. -->
- Owner:
- `research/filter_registry.json` key/status:
- Research posture: <!-- PROSPECTIVE, RETROSPECTIVE, or HYPOTHESIS-GENERATING. -->

## Prior outcome exposure

- Relevant outcomes inspected before this record: <!-- YES, NO, or UNKNOWN. -->
- Evidence already seen: <!-- Results, summaries, charts, selected variants, tuned parameters, or NONE. -->
- Exposure date/time or best-known sequence:
- Affected data periods:
- Affected variants/parameters:
- How the exposure may have influenced this specification or criteria:
- Unknown exposure details and resulting limitations:
- Genuinely unobserved validation evidence available: <!-- YES, NO, or UNKNOWN. -->
- Planned genuinely unobserved validation period/source:
- If no untouched evidence remains, required interpretation limit:

## Hypothesis and mechanism

- Hypothesis:
- Economic/market intuition:
- Expected mechanism:
- Observable conditions:
- Known ambiguities:

## Specification

- Universe and point-in-time construction:
- Signal definition and availability time:
- Entry definition and earliest executable time:
- Exit definition:
- Holding horizon/periods:
- Portfolio construction/selection rules:
- Position sizing/capital allocation:
- Initial capital and cash handling:
- Long/short, borrow, and leverage assumptions:
- Concurrent/overlapping position handling:
- Rebalancing, limits, and portfolio aggregation:
- Risk assumptions/rules:
- Benchmark/baseline:

## Research design

- Dataset and version:
- Data-readiness status/evidence:
- Research label: <!-- For example, SURVIVORSHIP-BIASED RESEARCH where required. -->
- Information-availability and label/outcome timing:
- Discovery period and planned sample size:
- Validation period and planned sample size:
- Untouched holdout period and planned sample size:
- Initial validation status: <!-- Normally UNTOUCHED. -->
- Initial holdout status: <!-- Normally UNTOUCHED. -->
- Chronological ordering and non-overlap across both boundaries:
- Purge rule and size at each boundary:
- Gap/embargo rule, size, and rationale at each boundary:
- Walk-forward/cross-validation design, if any:
- Primary metric:
- Secondary metrics:
- Risk metrics:
- Transaction-cost assumptions:
- Slippage/fill assumptions:
- Validation acceptance/rejection criteria:
- Holdout confirmation/rejection criteria:

## Executable validation

> Map every material acceptance/rejection criterion to executable evidence where
> practical. Use the frozen research record as the domain specification; do not
> create a second contract that can drift.

- Acceptance-criteria-to-scenario mapping:
- Test and fixture paths:
- Frozen-baseline reproducibility scenario:
- Point-in-time availability and future-data/leakage scenarios:
- Discovery/validation/holdout boundary, purge, and embargo checks:
- Deterministic replay/idempotence checks:
- Missing, invalid, duplicate, and stale-data scenarios:
- Survivorship, delisting, and corporate-action scenarios:
- Signal, entry, fill, exit, cost, and portfolio-accounting scenarios:
- Production-isolation and immutable-output checks:
- Provenance, manifest, version, and payload-hash checks:
- Negative cases and counterexamples:
- Manual validation that cannot reasonably be automated, with reason:
- Unresolved test gaps, residual risk, and future automation recommendation:
- FAST/focused commands:
- Canonical focused research command: <!-- Normally: powershell -ExecutionPolicy Bypass -File .\scripts\verify_research.ps1 -->
- Canonical FULL command: <!-- powershell -ExecutionPolicy Bypass -File .\scripts\verify_project.ps1 -->
- Expected PASS/BLOCKED/FAIL semantics and required evidence:

## Integrity and limitations

- Point-in-time controls:
- Survivorship/delisting controls:
- Corporate-action handling:
- Timestamp/timezone/calendar handling:
- Missing/duplicate/stale-data handling:
- Known biases:
- Data limitations:
- Other assumptions and uncertainty:
- Intended `research/output/` path:
- Production-isolation scope:

## Evaluation record

> Complete these fields only after the frozen evaluation is run. Append evidence
> without rewriting the specification or prior-exposure record above. A
> retrospective or hypothesis-generating posture remains retrospective or
> hypothesis-generating after evaluation.

- Validation period actually evaluated:
- Validation actual sample size:
- Validation sample status: <!-- UNTOUCHED, EVALUATED_ONCE, CONTAMINATED, or UNAVAILABLE. -->
- Validation result:
- Validation decision:
- Holdout period actually evaluated:
- Holdout actual sample size:
- Holdout sample status: <!-- UNTOUCHED, EVALUATED_ONCE, CONTAMINATED, or UNAVAILABLE. -->
- Holdout result:
- Holdout decision:
