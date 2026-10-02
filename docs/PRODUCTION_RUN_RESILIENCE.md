# Production Run Resilience

Status: production operational contract.

## Purpose

The Daily Watchlist must not fail silently or expose a mixture of report files
from different runs.  This contract covers operational observability and report
publication only.  It does not change screening, decision, sizing, or research
logic.

## Runtime artifacts

- `logs/production_status.json` is the machine-readable status of the latest
  production attempt.  It records a unique run ID, `STARTED`, `SUCCEEDED`, or
  `FAILED`, the current/final stage, UTC start/completion times, exit code, and
  a bounded error summary.
- Every attempt has an independent UTF-8 log below `logs/production_runs/`.
  `logs/production.log` remains a UTF-8 compatibility log and identifies the
  independent run log.
- `daily_watchlist_publish.json` is published with the report bundle.  It
  records the expected trading date and SHA-256 hashes of the CSV, Markdown,
  HTML, and email summary that passed semantic validation.
- `data_failure_report.txt` describes the latest failure.  A successful
  production run replaces stale failure content with an explicit resolved
  marker.

All of these are ignored runtime files and must not be committed.

## Production wrapper behaviour

1. The wrapper records `STARTED` before verification and updates the stage
   before verification and Python orchestration.
2. Verification failure, a Python non-zero exit, or an unexpected PowerShell
   exception records `FAILED`, preserves the original non-zero exit code where
   available, writes a failure report, and attempts one failure notification.
3. A failure notification is deduplicated by incident/run key.  Its lifecycle
   is `PREPARED -> ATTEMPTED -> COMPLETE -> CLEARED`.  An exclusive filesystem
   claim is created before delivery; stale claims that never reached
   `ATTEMPTED` are recoverable, while `ATTEMPTED` is retained because SMTP
   outcome may be ambiguous.  Claim creation, state transitions, notification
   delivery, and recovery clearing are serialized by one cross-process alert
   lock.  A healthy watchdog may clear the active state and retired claims only
   after its observed status/report generation is revalidated under that lock;
   it cannot clear an in-flight notification.  A later independently observed
   recurrence can then alert.
4. A fully successful Python run records `SUCCEEDED` and resolves stale failure
   content.  Email-delivery failure is therefore a failed production attempt,
   even when a locally validated report exists.
5. The wrapper never retries the complete production run.
6. Before it writes status or starts verification, the wrapper owns one global
   project-specific Windows mutex for its complete lifetime.  A concurrent
   invocation exits with a distinct non-zero code and cannot overwrite the
   active run's status, reports, manifest, or email inputs.
7. Failure summaries are normalized and bounded before logging or fallback
   status handling.  The wrapper passes summary content through a unique UTF-8
   runtime file rather than a command-line payload, so long or special-character
   output cannot prevent the failure monitor process from starting.

## Atomic report publication

CSV, Markdown, HTML, and email-summary outputs are generated in a temporary
directory on the report filesystem.  Cross-output semantic validation must pass
against those staged files before any public report path is replaced.  Each
replacement uses an atomic same-filesystem operation.  The publish manifest is
written last.  Failure before replacement preserves the complete previous
bundle; failure during replacement is detected later because the previous
manifest hashes no longer match.

Forward snapshots, last-good copies, report history, and email delivery occur
only after the validated report bundle has been published.

## Independent freshness watchdog

`scripts/check_daily_run.ps1` is a separate entry point intended for a second
Scheduled Task or external automation after the normal production time.  It
must not be invoked only by the production task it monitors.

The watchdog fails closed and sends at most one alert per distinct incident
when any of these checks fail:

- the latest production attempt does not belong to the current expected US
  trading-session lifecycle;
- it did not finish with `SUCCEEDED` and exit code zero;
- the publish manifest trading date is not the latest completed regular US
  trading session;
- a required report is absent or its hash differs from the manifest; or
- CSV, HTML, and email semantic validation fails.

The accepted lifecycle begins shortly before the expected session's New York
close, permits completion after London midnight, and remains current until the
latest completed US session advances.  This avoids weekend, full-day US market
holiday, London-midnight, and daylight-saving false alerts.  Exceptional market
closures remain an explicit limitation.  A healthy watchdog check clears the
active alert state and retired claims without sending email.

## Acceptance criteria and risk-based scenarios

1. A simulated Python crash leaves the prior reports intact, writes `FAILED`
   status/failure detail, and makes exactly one notification attempt.
2. A second handler invocation for the same incident makes no second SMTP
   attempt.
3. A successful run records zero exit status, retains a unique UTF-8 log, and
   marks the previous failure resolved.
4. Report-generation or semantic-validation failure before publication leaves
   every existing public report and its publish manifest unchanged.
5. A valid staged bundle replaces all public outputs and publishes matching
   hashes only after validation.
6. The watchdog rejects missing, stale, incomplete, failed, hash-mismatched, or
   semantically inconsistent state and accepts a same-day successful run whose
   manifest names the latest expected trading session.
7. The watchdog notification uses the same incident deduplication rule and does
   not retry production.
8. Existing deterministic screening, decision, sizing, report semantics, safe
   dry-run isolation, and no-retry SMTP behaviour remain unchanged.
9. `unhealthy -> alert -> healthy -> clear -> same failure -> new alert` works,
   and a stale claim that crashed before delivery preparation can be reclaimed.
10. Cross-midnight, US/UK daylight-saving differences, weekends, and regular US
    market holidays do not make a valid latest-session run stale.
11. Two genuinely concurrent wrapper processes result in one mutex owner and
    one clear lock-contention exit; the loser performs no production work.
12. While one notifier is blocked, a concurrent healthy clear and second alert
    handler cannot remove or reacquire its claim; the incident produces at most
    one notification attempt, and stale health evidence cannot clear newer
    runtime state.
13. A failure summary far beyond the Windows command-line limit, including
    spaces, pipes, dashes, NULs, and non-ASCII text, reaches the monitor through
    a file, is normalized/bounded, and still produces failure status without
    argument splitting.

## Non-goals

- Creating or modifying Windows Scheduled Tasks.
- Retrying production or SMTP after an ambiguous result.
- Changing trading thresholds, candidate decisions, or research status.
- Claiming coverage for exceptional exchange closures not represented by the
  current calendar.
