# Incident record: mutex probe entered production wrapper

## Identity and current state

- Incident title: Mutex regression probe entered the real production wrapper.
- Current state: RECOVERY_VERIFIED
- Impact or severity: One unintended verification-only wrapper run and one
  false production-failure email; no production report publication was observed.
- Owner / authorized operator: Codex task agent; user is the repository operator.
- Opened at: 2026-10-01T22:35:40+01:00
- Last updated at: 2026-10-02T13:26:15+01:00
- Affected environment, repository, service, data, artifact, or operation:
  local `stock_screener` checkout, production wrapper runtime status/logs, and
  configured Gmail failure-notification delivery.

## Signals and scope

- Directly observed signals: the new parallel-wrapper regression invoked
  `scripts/run_daily_production.ps1 -MutexProbe` before that parameter existed;
  Windows PowerShell ignored the unbound argument and entered verification.
  PIDs 32088 and 40820 remained active after the test timeout. Runtime status
  showed `STARTED / verification`. A later failure record showed
  `notification_succeeded: true` for one failure email.
- Agent/operator inference: no normal watchlist email or report publication ran
  because verification failed or was stopped before `run_screener.py`.
- Known affected scope: two wrapper attempt logs, `logs/production.log`,
  `logs/verify_project.log`, `logs/production_status.json`,
  `logs/production_alert_state.json`, `data_failure_report.txt`, and one false
  failure email.
- Explicitly unknown scope: whether the recipient read or acted on the false
  email. No email retry will be attempted.
- Last known trustworthy state: the report CSV, Markdown, HTML, and email
  summary last modified on 2026-09-29 before the incident.
- First known unsafe or uncertain state: 2026-10-01T22:35:40+01:00 when the
  unguarded mutex probe launched the wrapper.

## Disproving evidence and false-alarm disposition

- Evidence establishing that no incident occurred: Not applicable; the false
  external email was confirmed.
- Why recovery is not required: Not applicable.
- Incident-only constraints lifted: repository repair, focused verification,
  FULL verification, research-isolation verification, and code review may
  proceed normally. Real production execution remains outside this recovery.
- Independent constraints still in force: no production execution, retry,
  email, Scheduled Task mutation, commit, merge, or push is authorized.
- Prior normal-workflow checkpoint that may resume: Not applicable until
  recovery verification.
- Disposition authority / evidence: user review plus repository incident policy.

## Stabilization and evidence

- Actions paused or prohibited: production execution, wrapper integration tests
  without an enforced probe guard, review advancement, and Git boundaries.
- Running or scheduled actions assessed: exact incident PIDs 32088 and 40820.
- Evidence preserved and location/reference: ignored runtime logs/status named
  above and this sanitized incident record.
- Evidence collection limits: Win32 process command-line inspection was denied;
  process identity was bounded by start time, executable, status run ID, and the
  corresponding wrapper/child logs.
- Secret/privacy handling: no credentials, email address, or message transport
  secrets were copied into this record.

## Containment

- Containment action: stopped PIDs 40820 and 32088 without deleting logs or
  runtime evidence.
- Target and expected effect: stop only the verification child and wrapper
  created by the failed test.
- Authority / approval: agent-created processes were stopped as the
  least-invasive action preventing an unauthorized production continuation.
- Result and independent verification: `Get-Process -Id 40820,32088` returned no
  remaining process; report output modification times remained 2026-09-29.
- Reversibility and evidence impact: processes cannot be resumed; logs and
  runtime status were preserved.
- Known limitations: the false email cannot be recalled; runtime status and the
  failure report currently describe this contained false production attempt.

## Recovery plan

- Recovery source or forward-fix basis: current focused branch plus the reviewed
  resilience contract and failing regression scenarios.
- Targets and exclusions: repair alert lifecycle, session freshness, and wrapper
  mutual exclusion; do not run production, send email, modify reports, or alter
  Scheduled Tasks.
- Prerequisites: guarded mutex probe must exit before any status/log/verification
  action; focused tests must not recurse into the production workflow.
- Required approvals: no new approval for repository repair; production retry,
  Scheduled Task mutation, and Git boundaries remain separately unauthorized.
- Planned operations: implement lifecycle clear/stale-claim recovery, session
  windows, global mutex, and a guarded probe; run focused tests, FULL, research
  isolation, and code review.
- Expected outcomes: one mutex owner, no real production action from tests,
  correct overnight/session freshness, and reusable alert lifecycle.
- Abort conditions: any new production path, SMTP attempt, report timestamp
  change, unexpected process, or loss of evidence.
- Partial-execution detection and handling: inspect process list, runtime log,
  report timestamps, status, and alert state after the guarded concurrency test.
- Fallback: stop exact test-created processes and remain CONTAINED.
- Verification and observation window: focused tests plus no unexpected report
  or email effects, final FULL gate, research isolation, and independent review.

## Timeline

- 2026-10-01T22:35:40+01:00 — regression test launched the first unguarded
  `-MutexProbe`; the wrapper entered verification.
- 2026-10-01T22:36:19+01:00 — recursive pytest launched another wrapper; it
  failed on the already-open verification log.
- 2026-10-01T22:36:24+01:00 — the first wrapper recorded verification failure
  and sent one failure notification.
- 2026-10-01T22:36:40+01:00 — running processes and `STARTED / verification`
  status were observed; unsafe progression was paused.
- 2026-10-01T22:36:45+01:00 — exact PIDs 40820 and 32088 were stopped and their
  absence verified.
- 2026-10-01T22:36:59+01:00 — report modification times confirmed no report
  publication; failure-email delivery evidence confirmed the external effect.
- 2026-10-01T22:42:00+01:00 — guarded mutex probe ran in an isolated temporary
  project root; one wrapper owned the mutex, the other exited `75`, and its
  sentinel status remained unchanged.
- 2026-10-01T22:50:57+01:00 — final FULL project verification passed on the
  repaired content.
- 2026-10-01T22:52:00+01:00 — final research verification and production
  isolation passed; incident recovery was verified without a production run.
- 2026-10-02T13:10:57+01:00 — a later code review invalidated the broad
  no-findings statement by identifying an alert-clear concurrency race and an
  unbounded command-line summary.  Neither finding created a new external
  incident; the original mutex-probe incident remains recovery-verified.
- 2026-10-02T13:26:15+01:00 — both follow-up P2 findings were repaired; focused,
  FULL, research-isolation, and post-fix review evidence passed without running
  production or changing preserved incident artifacts.

## Verification and resumption

- Containment status: verified; no incident wrapper or child remains.
- Repository/artifact/runtime/data integrity evidence: production report files
  were unchanged since 2026-09-29; current runtime failure artifacts are
  preserved and explicitly attributed to this incident.
- Root-cause repair or accepted recurrence control: the wrapper now rejects an
  unguarded probe, acquires its project-specific global mutex before status or
  log mutation, and the concurrency test copies the wrapper into an isolated
  temporary project root with a sentinel status. Initialization is also inside
  the unified failure path.
- Targeted and regression checks: `79 passed` across resilience, email, and
  production-decision tests with no production runtime hash changes; after the
  final initialization hardening, all `29` resilience tests passed again.
- FULL quality gate: PASS — Python syntax, Ruff, mypy for three production
  sources, `474 pytest`, `118 unittest`, integration/invariant checks, offline
  sample dry run, and generated-report semantic validation.
- Research isolation: PASS — `196 pytest`, expected gated MODEL_0
  `BLOCKED_DATA_NOT_READY`, and production isolation all passed.
- Independent review: the 2026-10-01 no-findings conclusion was superseded on
  2026-10-02 by two P2 findings concerning concurrent alert clearing and
  command-line summary size.  Both were repaired with cross-process lifecycle
  serialization, generation/revision revalidation, unique JSON temporary files,
  and file-based bounded summary transport.  Post-fix review found no remaining
  P0/P1/P2 issue; this follow-up did not reopen the contained external incident.
- Operational health / observation evidence: no running incident processes; no
  report publication. One false failure email is an irreversible residual fact.
- Residual risk and monitoring: unguarded test path must not be invoked again.
- Authorized resumption decision: repository development and review resumed at
  `RECOVERY_VERIFIED`; production execution, email, Scheduled Task mutation,
  and Git boundaries remain separately unauthorized.
- Earliest valid normal-workflow checkpoint: current repaired uncommitted
  working tree after final verification.

## Follow-up and explicit omissions

- Follow-up actions and owners: Codex repairs and validates the three reviewed
  P2 findings and this test-seam defect; user may disregard the single false
  failure email tied to this incident.
- Explicitly not performed: no production retry, email retry, report cleanup,
  runtime evidence deletion, Scheduled Task mutation, commit, merge, or push.
- Unknowns requiring external decision or evidence: none required for the code
  repair; actual production resumption remains an operator decision.
