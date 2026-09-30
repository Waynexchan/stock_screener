# Email Delivery Contract

The production screener sends the already validated Daily Watchlist through
Gmail SMTP after report generation. Email delivery is an operational boundary:
a generated report is not evidence that the message was delivered.

## Required behaviour

- Gmail delivery uses implicit TLS on `smtp.gmail.com:465` with a finite
  connection timeout.
- The sender authenticates with `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD`; the
  recipient is the configured sender address.
- Normal delivery attaches the validated `daily_watchlist.html`. Data-quality
  failure delivery sends only the failure notice.
- When email is disabled, production may complete successfully without an
  SMTP attempt.
- When email is enabled, a missing credential, missing attachment, connection,
  authentication, or send failure must produce a non-zero process exit. The
  production wrapper and Windows Scheduled Task must therefore expose the
  failure instead of reporting a successful run.
- Delivery is attempted once. The sender must not automatically retry through
  another SMTP transport because a timeout after server acceptance could
  otherwise create a duplicate message.

## Acceptance criteria

1. Both normal and data-failure messages use Gmail implicit TLS port 465 with
   the configured finite timeout.
2. Successful delivery authenticates and sends exactly one message.
3. An SMTP or sender-process failure is visible to the production caller as a
   non-zero result.
4. Disabled email remains a successful no-op.
5. Tests never contact Gmail or send a real message.

## Non-goals

This contract does not change screening, ranking, decisions, risk, report
contents, credentials, recipients, the Windows Scheduled Task, or retry a
historical message automatically.
