# Pattern Discovery Reporting — Phase 1

## Status and scope

- Status: approved for Phase 1 implementation only.
- Classification: `RESEARCH_ONLY` reporting architecture.
- Production authority: unchanged. `decision_system.canonical_candidate_decision`,
  called through `run_screener.apply_canonical_decision_pipeline`, remains the
  sole authority for `FULL`, `HALF`, `WATCH`, `NO TRADE`, actionability, risk,
  shares, stop, target, and confirmation state.
- Non-goals: no new setup lane, factor, score, threshold, hard filter,
  cross-session state, label journal, performance evaluation, or production
  promotion.

## Behavioural contract

Phase 1 adds a post-decision report classification. It consumes completed
canonical candidate records and may add research/report fields, but it must not
mutate any canonical production field or feed back into production decisions.

### Actionable Now

- Contains exactly the candidates whose canonical `Final Decision` is `FULL` or
  `HALF`.
- Displays the canonical trade plan and risk values without reinterpretation.
- Research/report fields cannot add a candidate to this section.

### Pattern Watchlist

- Contains discovered candidates that are not canonically actionable and do not
  meet an existing explicit Avoid / Failed condition below.
- Is labelled `RESEARCH_ONLY` and is a chart-review list, not an alternative
  trade list.
- May contain `WATCH` or `NO TRADE` records and may legitimately have a missing
  entry, missing observed target, or unavailable/incomplete structural R/R.
- Missing values remain missing. Inclusion must never synthesize an entry, stop,
  target, R/R, decision, risk amount, or share count.
- The explanation uses existing canonical decision/missing-confirmation evidence
  and explicitly identifies absent plan elements where present.

### Avoid / Failed

- Contains non-actionable discovered candidates with existing explicit failure
  evidence: setup integrity `FAIL`, `Extended` or `Overextended` status, stale
  or incomplete critical price data, a non-empty critical price/data warning,
  present non-finite entry/stop values, or present finite entry/stop values whose
  stop is not below entry. Missing entry/stop values remain waiting evidence,
  not failure evidence.
- Uses only those existing states and values. Phase 1 introduces no new setup
  threshold or production gate.
- Is labelled `RESEARCH_ONLY` and remains zero-risk/non-actionable.

### Classification ownership and precedence

1. Existing discovery/category code owns membership in the candidate pool and
   the existing category/order fields.
2. The canonical decision pipeline owns all production decision and sizing
   fields.
3. The Phase 1 report classifier runs after the canonical pipeline and owns only
   `Report Section`, `Pattern Discovery Status`, and
   `Pattern Discovery Reason`.
4. Canonical `FULL`/`HALF` takes precedence and always maps to `Actionable Now`.
   Otherwise explicit Avoid / Failed evidence takes precedence over Pattern
   Watchlist.
5. Incoming values in the three research/report fields are untrusted and are
   overwritten from canonical and observable record fields.

## Outputs and compatibility

- CSV adds the three Phase 1 fields while preserving existing canonical columns
  and values.
- HTML, Markdown, and email expose the three sections clearly. Existing raw
  setup-category and four-state diagnostic views remain available in the
  diagnostic/detail portion of the report where applicable.
- The machine-readable decision manifest includes report classification so CSV,
  HTML, and email can be checked for cross-output agreement.
- Existing function return shapes, canonical state names, history schema,
  forward-snapshot schema version, and production entry points remain unchanged.
- Immutable forward snapshots continue to receive the untouched canonical
  production frame; the three research/report fields are not written into the
  snapshot candidate payload.
- An older saved CSV that lacks Phase 1 fields can be previewed by deriving the
  report classification from its existing canonical fields; no production
  decision is recalculated by preview.

## Acceptance criteria

1. A research-worthy candidate can appear in Pattern Watchlist while remaining
   canonically non-actionable and zero-risk.
2. Canonical `FULL` and `HALF` candidates appear in Actionable Now with their
   original production fields unchanged.
3. `WATCH` and `NO TRADE` records remain zero-risk with zero shares.
4. Pattern Watchlist can include a record with no observed target and unavailable
   R/R without fabricating either value.
5. Applying report classification to a canonical regression fixture leaves all
   canonical production output fields byte/value-equivalent.
6. Repeated classification of the same input produces the same ordered values
   and overwrites untrusted incoming research/report fields.
7. CSV, HTML, and email manifests agree on canonical decisions and Phase 1
   report classification; output validation rejects contradictory mappings,
   including a non-actionable row placed on the wrong side of the explicit
   Avoid / Failed evidence boundary.
8. Research/report fields cannot promote or resize a `WATCH`/`NO TRADE` record,
   demote a `FULL`/`HALF` record, or otherwise override canonical production
   fields.
9. The three report-only fields are absent from the pre-canonical discovery
   schema and immutable forward-snapshot candidate payload, including when the
   input candidate was constructed from the complete production discovery
   schema.

## Test scenarios and design review

| Scenario | Requirement covered | Expected observation |
| --- | --- | --- |
| Missing observed target | AC1, AC3, AC4 | `Pattern Watchlist`, `RESEARCH_ONLY`, target/R/R still missing, zero risk/shares. |
| Canonical FULL and HALF | AC2, AC5 | Both map to `Actionable Now`; canonical fields are unchanged. |
| WATCH and NO TRADE | AC1, AC3 | Both remain non-actionable and zero-risk; section depends only on explicit Phase 1 failure evidence. |
| Existing failure evidence | AC3 | Integrity failure, stale/warned data, excessive extension, and invalid present stop geometry map to `Avoid / Failed`. |
| Injected research override | AC6, AC8 | Incoming `Actionable Now`/favourable reason values are deterministically overwritten and cannot affect production fields. |
| Repeated classification | AC6 | Same input yields identical section/status/reason output and stable row order. |
| Cross-output fixture | AC7 | Updated semantic validator passes a consistent report and rejects a contradictory section/status mapping. |
| Failure-precedence tampering | AC7 | Validator rejects stale, warned, finite invalid-stop, non-finite entry/stop, extended, and failed-integrity rows mislabeled Pattern Watchlist, and rejects a capacity-only row mislabeled Avoid / Failed. |
| Real discovery-schema snapshot | AC9 | A candidate built from the complete `DISCOVERY_COLUMNS` schema passes through the canonical pipeline and snapshot writer without any report-only field in `candidates.csv`. |
| Legacy preview input | compatibility | Missing Phase 1 columns are derived from existing canonical fields without recalculating decisions. |

Test-design review:

- Every acceptance criterion is covered by at least one observable scenario.
- Missing entry/target/R/R is separated from invalid present stop geometry, so
  tests cannot accidentally encode favourable imputation.
- Production invariance is checked by comparing the full canonical field set,
  not merely the final state.
- The tests exercise both canonical states and report sections because one does
  not substitute for the other.
- Cross-output validation is updated so code and rendering cannot silently agree
  on a classification that contradicts canonical actionability.
- Classifier and validator boundary tests cover every Phase 1 failure predicate
  plus a non-failure capacity constraint to detect precedence drift in either
  direction.
- Snapshot coverage uses the complete production discovery schema rather than a
  reduced fixture, preventing report-field leakage from being hidden by test
  construction.
- No scenario introduces Phase 2 setup-lane semantics or claims discovery or
  trading performance.
