"""Production run status, failure notification, and freshness watchdog."""

from __future__ import annotations

import argparse
import binascii
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time, timedelta, timezone
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Lock
import time
from typing import Any, Callable, Iterator
from zoneinfo import ZoneInfo


STATUS_PATH = Path("logs/production_status.json")
ALERT_STATE_PATH = Path("logs/production_alert_state.json")
ALERT_CLAIM_DIRECTORY = Path("logs/production_alert_claims")
ALERT_LOCK_PATH = Path("logs/production_alert.lock")
FAILURE_REPORT_PATH = Path("data_failure_report.txt")
PUBLISH_MANIFEST_PATH = Path("daily_watchlist_publish.json")
MAX_ERROR_SUMMARY_LENGTH = 1000
ALERT_PREPARED_TTL_SECONDS = 300
PRODUCTION_SESSION_START_LEAD_HOURS = 2
PRODUCTION_LOCKED_EXIT_CODE = 75
REQUIRED_REPORTS = (
    "daily_watchlist.csv",
    "daily_watchlist.md",
    "daily_watchlist.html",
    "email_summary.txt",
)
_ALERT_THREAD_LOCK = Lock()


@dataclass(frozen=True)
class NotificationResult:
    notification_attempted: bool
    notification_succeeded: bool | None
    lifecycle_cleared: bool | None = None


@dataclass(frozen=True)
class WatchdogResult:
    healthy: bool
    reasons: tuple[str, ...]
    generation: str | None = None
    alert_revision: int | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_time(value: datetime | None) -> datetime:
    current = value or _utc_now()
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _alert_lifecycle_lock(root: Path) -> Iterator[None]:
    """Serialize alert claims, delivery state, and recovery across processes."""
    lock_path = root / ALERT_LOCK_PATH
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with _ALERT_THREAD_LOCK, lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl: Any = __import__("fcntl")

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _runtime_generation(root: Path) -> str:
    """Fingerprint every runtime input that determines watchdog health."""
    digest = hashlib.sha256()
    relative_paths = (
        STATUS_PATH,
        PUBLISH_MANIFEST_PATH,
        *(Path(name) for name in REQUIRED_REPORTS),
    )
    for relative_path in relative_paths:
        digest.update(str(relative_path).encode("utf-8"))
        digest.update(b"\0")
        try:
            content = (root / relative_path).read_bytes()
        except FileNotFoundError:
            digest.update(b"<missing>")
        except OSError as exc:
            digest.update(f"<error:{type(exc).__name__}:{exc.errno}>".encode("ascii"))
        else:
            digest.update(hashlib.sha256(content).digest())
        digest.update(b"\0")
    return digest.hexdigest()


def _bounded_summary(summary: str) -> str:
    normalized = " ".join(str(summary).replace("\x00", "").split())
    return normalized[:MAX_ERROR_SUMMARY_LENGTH] or "No error summary was available."


def _alert_revision(state: dict[str, object]) -> int:
    value = state.get("lifecycle_revision", 0)
    return value if isinstance(value, int) and value >= 0 else 0


def _current_alert_revision(root: Path) -> int:
    state_path = root / ALERT_STATE_PATH
    try:
        state = _read_json(state_path) if state_path.exists() else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return 0
    return _alert_revision(state)


def start_run(
    root: str | Path,
    run_id: str,
    log_path: str,
    now: datetime | None = None,
) -> None:
    current = _normalize_time(now)
    payload: dict[str, object] = {
        "schema_version": 1,
        "run_id": run_id,
        "state": "STARTED",
        "stage": "initialization",
        "started_at": current.isoformat(),
        "completed_at": None,
        "exit_code": None,
        "error_summary": "",
        "log_path": log_path,
    }
    _atomic_write_json(Path(root) / STATUS_PATH, payload)


def stage_run(root: str | Path, run_id: str, stage: str) -> None:
    path = Path(root) / STATUS_PATH
    payload = _read_json(path)
    if payload.get("run_id") != run_id:
        raise ValueError("run ID does not match the active production status")
    if payload.get("state") != "STARTED":
        raise ValueError("only a started production run can change stage")
    payload["stage"] = stage
    _atomic_write_json(path, payload)


def _incident_key(source: str, *parts: object) -> str:
    value = json.dumps([source, *parts], sort_keys=True, default=str)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _alert_claim_path(
    root: Path, incident_key: str, related_run_id: str | None
) -> Path:
    claim_identity = related_run_id or incident_key
    claim_digest = hashlib.sha256(claim_identity.encode("utf-8")).hexdigest()
    return root / ALERT_CLAIM_DIRECTORY / f"{claim_digest}.claimed"


def _clear_alert_lifecycle_locked(
    root: Path,
    now: datetime,
    expected_generation: str | None,
    expected_revision: int | None = None,
) -> bool:
    if (
        expected_generation is not None
        and _runtime_generation(root) != expected_generation
    ):
        return False

    state_path = root / ALERT_STATE_PATH
    try:
        state = _read_json(state_path) if state_path.exists() else {}
    except (OSError, ValueError, json.JSONDecodeError):
        state = {}
    if expected_revision is not None and _alert_revision(state) != expected_revision:
        return False
    next_revision = _alert_revision(state) + 1

    _atomic_write_json(
        state_path,
        {
            "schema_version": 1,
            "active_incident_key": None,
            "cleared_at": now.isoformat(),
            "delivery_phase": "CLEARED",
            "incident_generation": None,
            "lifecycle_revision": next_revision,
            "notification_succeeded": None,
            "related_run_id": None,
        },
    )
    claim_directory = root / ALERT_CLAIM_DIRECTORY
    if claim_directory.is_dir():
        for claim in claim_directory.glob("*.claimed"):
            claim.unlink(missing_ok=True)
    return True


def _clear_alert_lifecycle(
    root: Path,
    now: datetime,
    expected_generation: str | None = None,
    expected_revision: int | None = None,
) -> bool:
    with _alert_lifecycle_lock(root):
        return _clear_alert_lifecycle_locked(
            root,
            now,
            expected_generation,
            expected_revision,
        )


def _claim_is_stale(claim_path: Path, now: datetime) -> bool:
    try:
        claim = _read_json(claim_path)
        created_at = _parse_timestamp(claim.get("created_at"), "created_at")
    except (OSError, ValueError, json.JSONDecodeError):
        # Another process can observe the exclusive claim immediately after
        # creation but before its JSON payload has been flushed.  Treating an
        # incomplete payload as stale would let that process steal a live
        # claim (and fails on Windows while the owner still has it open).
        try:
            modified_at = datetime.fromtimestamp(
                claim_path.stat().st_mtime, tz=timezone.utc
            )
        except OSError:
            return False
        return (now - modified_at).total_seconds() > ALERT_PREPARED_TTL_SECONDS
    return (now - created_at).total_seconds() > ALERT_PREPARED_TTL_SECONDS


def _alert_once(
    root: Path,
    incident_key: str,
    notifier: Callable[[Path], int] | None,
    now: datetime,
    related_run_id: str | None = None,
    incident_generation: str | None = None,
) -> NotificationResult:
    with _alert_lifecycle_lock(root):
        return _alert_once_locked(
            root,
            incident_key,
            notifier,
            now,
            related_run_id=related_run_id,
            incident_generation=incident_generation,
        )


def _alert_once_locked(
    root: Path,
    incident_key: str,
    notifier: Callable[[Path], int] | None,
    now: datetime,
    related_run_id: str | None = None,
    incident_generation: str | None = None,
) -> NotificationResult:
    if notifier is None:
        return NotificationResult(False, None)
    if (
        incident_generation is not None
        and _runtime_generation(root) != incident_generation
    ):
        return NotificationResult(False, None)
    state_path = root / ALERT_STATE_PATH
    try:
        state = _read_json(state_path) if state_path.exists() else {}
    except (OSError, ValueError, json.JSONDecodeError):
        state = {}
    same_incident = bool(state.get("active_incident_key")) and (
        state.get("active_incident_key") == incident_key
        or (
            related_run_id is not None and state.get("related_run_id") == related_run_id
        )
    )
    delivery_phase = state.get("delivery_phase")
    if delivery_phase is None and state.get("attempted_at"):
        delivery_phase = (
            "COMPLETE"
            if state.get("notification_succeeded") is not None
            else "ATTEMPTED"
        )
    if same_incident and delivery_phase in {"ATTEMPTED", "COMPLETE"}:
        return NotificationResult(False, state.get("notification_succeeded"))

    next_revision = _alert_revision(state) + 1
    claim_path = _alert_claim_path(root, incident_key, related_run_id)
    claim_path.parent.mkdir(parents=True, exist_ok=True)
    if claim_path.exists():
        if not _claim_is_stale(claim_path, now):
            return NotificationResult(False, state.get("notification_succeeded"))
        try:
            claim_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            # A live Windows owner can keep the claim open even if a caller's
            # clock makes it appear old.  Failing closed avoids double delivery.
            return NotificationResult(False, state.get("notification_succeeded"))
    try:
        with claim_path.open("x", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "created_at": now.isoformat(),
                        "incident_generation": incident_generation,
                        "incident_key": incident_key,
                        "lifecycle_revision": next_revision,
                        "related_run_id": related_run_id,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    except FileExistsError:
        return NotificationResult(False, state.get("notification_succeeded"))

    state = {
        "schema_version": 1,
        "active_incident_key": incident_key,
        "delivery_phase": "PREPARED",
        "incident_generation": incident_generation,
        "lifecycle_revision": next_revision,
        "notification_succeeded": None,
        "prepared_at": now.isoformat(),
        "related_run_id": related_run_id,
    }
    _atomic_write_json(state_path, state)
    # Persist ATTEMPTED immediately before SMTP because a timeout can leave
    # delivery outcome unknown and must never trigger an automatic retry.
    state["attempted_at"] = now.isoformat()
    state["delivery_phase"] = "ATTEMPTED"
    _atomic_write_json(state_path, state)
    succeeded = False
    try:
        succeeded = notifier(root / FAILURE_REPORT_PATH) == 0
    except Exception:  # The production failure must survive notifier failures.
        succeeded = False
    state["completed_at"] = now.isoformat()
    state["delivery_phase"] = "COMPLETE"
    state["notification_succeeded"] = succeeded
    _atomic_write_json(state_path, state)
    return NotificationResult(True, succeeded)


def fail_run(
    root: str | Path,
    run_id: str,
    stage: str,
    exit_code: int,
    summary: str,
    *,
    now: datetime | None = None,
    notifier: Callable[[Path], int] | None = None,
) -> NotificationResult:
    project_root = Path(root)
    current = _normalize_time(now)
    status_path = project_root / STATUS_PATH
    try:
        payload = _read_json(status_path)
    except (OSError, ValueError, json.JSONDecodeError):
        payload = {
            "schema_version": 1,
            "run_id": run_id,
            "started_at": current.isoformat(),
            "log_path": "",
        }
    if payload.get("run_id") != run_id:
        payload = {
            "schema_version": 1,
            "run_id": run_id,
            "started_at": current.isoformat(),
            "log_path": "",
        }
    bounded = _bounded_summary(summary)
    payload.update(
        {
            "state": "FAILED",
            "stage": stage,
            "completed_at": current.isoformat(),
            "exit_code": int(exit_code) if int(exit_code) != 0 else 1,
            "error_summary": bounded,
        }
    )
    _atomic_write_json(status_path, payload)

    report = "\n".join(
        [
            "Stock Screener Production Failure",
            "",
            f"Run ID: {run_id}",
            f"Failed at: {current.isoformat()}",
            f"Stage: {stage}",
            f"Exit code: {payload['exit_code']}",
            f"Error summary: {bounded}",
            f"Run log: {payload.get('log_path', '')}",
        ]
    )
    (project_root / FAILURE_REPORT_PATH).write_text(report + "\n", encoding="utf-8")
    key = _incident_key("production", run_id, stage, payload["exit_code"], bounded)
    return _alert_once(
        project_root,
        key,
        notifier,
        current,
        related_run_id=run_id,
        incident_generation=_runtime_generation(project_root),
    )


def succeed_run(root: str | Path, run_id: str, *, now: datetime | None = None) -> None:
    project_root = Path(root)
    current = _normalize_time(now)
    status_path = project_root / STATUS_PATH
    payload = _read_json(status_path)
    if payload.get("run_id") != run_id:
        raise ValueError("run ID does not match the active production status")
    if payload.get("state") != "STARTED":
        raise ValueError("only a started production run can succeed")
    payload.update(
        {
            "state": "SUCCEEDED",
            "stage": "complete",
            "completed_at": current.isoformat(),
            "exit_code": 0,
            "error_summary": "",
        }
    )
    (project_root / FAILURE_REPORT_PATH).write_text(
        "\n".join(
            [
                "Stock Screener Production Failure: RESOLVED",
                "",
                f"Successful run ID: {run_id}",
                f"Resolved at: {current.isoformat()}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    # Publish terminal success only after all success-side runtime state exists.
    _atomic_write_json(status_path, payload)
    _clear_alert_lifecycle(
        project_root,
        current,
        expected_generation=_runtime_generation(project_root),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is missing")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"{field} has no timezone")
    return parsed


def _default_expected_session(now: datetime) -> date:
    from run_screener import expected_latest_us_session

    return expected_latest_us_session(now)


def _default_session_close(session: date) -> datetime:
    import config

    eastern = ZoneInfo("America/New_York")
    close = datetime.combine(
        session,
        datetime_time(16, config.US_MARKET_CLOSE_GRACE_MINUTES),
        tzinfo=eastern,
    )
    return close.astimezone(timezone.utc)


def _default_semantic_validator(html: Path, csv: Path, email: Path) -> None:
    validator = Path(__file__).resolve().parent / "scripts" / "validate_report.py"
    result = subprocess.run(
        [sys.executable, str(validator), str(html), str(csv), str(email)],
        cwd=Path(__file__).resolve().parent,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stdout + "\n" + result.stderr).strip()
        raise RuntimeError(detail or f"validator exited {result.returncode}")


def check_daily_run(
    root: str | Path,
    *,
    now: datetime | None = None,
    expected_session_provider: Callable[[datetime], date] = _default_expected_session,
    session_close_provider: Callable[[date], datetime] = _default_session_close,
    semantic_validator: Callable[
        [Path, Path, Path], None
    ] = _default_semantic_validator,
) -> WatchdogResult:
    project_root = Path(root)
    current = _normalize_time(now)
    generation_before = _runtime_generation(project_root)
    reasons: list[str] = []
    status_path = project_root / STATUS_PATH
    status: dict[str, object] = {}
    started_at: datetime | None = None
    completed_at: datetime | None = None
    expected_session = expected_session_provider(current)
    session_window_start = session_close_provider(expected_session) - timedelta(
        hours=PRODUCTION_SESSION_START_LEAD_HOURS
    )
    if not status_path.exists():
        reasons.append("production status is missing")
    else:
        try:
            status = _read_json(status_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            reasons.append(f"production status is invalid: {exc}")
    if status:
        if status.get("schema_version") != 1:
            reasons.append("production status schema version is invalid")
        run_id = status.get("run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            reasons.append("production run ID is missing or invalid")
        if status.get("state") != "SUCCEEDED":
            reasons.append(
                f"latest production state is {status.get('state', 'UNKNOWN')}"
            )
        if status.get("exit_code") != 0:
            reasons.append(f"latest production exit code is {status.get('exit_code')}")
        try:
            started_at = _parse_timestamp(status.get("started_at"), "started_at")
            if started_at < session_window_start:
                reasons.append(
                    "production started before the expected trading-session window"
                )
            if started_at > current:
                reasons.append("production start time is in the future")
        except (TypeError, ValueError):
            reasons.append("production start time is missing or invalid")
        try:
            completed_at = _parse_timestamp(status.get("completed_at"), "completed_at")
            if completed_at > current:
                reasons.append("production completion time is in the future")
        except (TypeError, ValueError):
            reasons.append("production completion time is missing or invalid")
        if (
            started_at is not None
            and completed_at is not None
            and completed_at < started_at
        ):
            reasons.append("production completion time precedes start time")

    manifest_path = project_root / PUBLISH_MANIFEST_PATH
    manifest: dict[str, object] = {}
    if not manifest_path.exists():
        reasons.append("report publish manifest is missing")
    else:
        try:
            manifest = _read_json(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            reasons.append(f"report publish manifest is invalid: {exc}")
    if manifest:
        if manifest.get("schema_version") != 1:
            reasons.append("report publish manifest schema version is invalid")
        manifest_run_id = manifest.get("run_id")
        if not isinstance(manifest_run_id, str) or not manifest_run_id.strip():
            reasons.append("report publish run ID is missing or invalid")
        expected = expected_session.isoformat()
        actual = str(manifest.get("signal_trading_date", ""))
        if actual != expected:
            reasons.append(
                f"publish trading date {actual or 'missing'} does not match expected {expected}"
            )
        if status and manifest.get("run_id") != status.get("run_id"):
            reasons.append("report publish run ID does not match production status")
        try:
            published_at = _parse_timestamp(
                manifest.get("published_at"), "published_at"
            )
            if started_at is not None and published_at < started_at:
                reasons.append("report publish time precedes production start time")
            if completed_at is not None and published_at > completed_at:
                reasons.append("report publish time follows production completion time")
        except (TypeError, ValueError):
            reasons.append("report publish time is missing or invalid")
        hashes = manifest.get("files")
        if not isinstance(hashes, dict):
            reasons.append("report publish hashes are missing or invalid")
        else:
            for name in REQUIRED_REPORTS:
                path = project_root / name
                if not path.is_file():
                    reasons.append(f"required report is missing: {name}")
                elif hashes.get(name) != _sha256(path):
                    reasons.append(f"hash mismatch for {name}")
    try:
        semantic_validator(
            project_root / "daily_watchlist.html",
            project_root / "daily_watchlist.csv",
            project_root / "email_summary.txt",
        )
    except Exception as exc:
        reasons.append(f"semantic validation failed: {_bounded_summary(str(exc))}")
    generation_after = _runtime_generation(project_root)
    if generation_after != generation_before:
        reasons.append("runtime artifacts changed during watchdog validation")
    return WatchdogResult(
        not reasons,
        tuple(dict.fromkeys(reasons)),
        generation_after,
        _current_alert_revision(project_root),
    )


def _email_notifier(report_path: Path) -> int:
    import config
    import send_email

    if not config.EMAIL_ENABLED:
        print("Production failure email disabled.")
        return 0
    return send_email.send_operational_failure_email(report_path)


def _configured_notifier() -> Callable[[Path], int] | None:
    import config

    return _email_notifier if config.EMAIL_ENABLED else None


def _write_watchdog_failure(
    root: Path, reasons: tuple[str, ...], now: datetime
) -> None:
    content = "\n".join(
        [
            "Stock Screener Freshness Watchdog Failure",
            "",
            f"Checked at: {now.isoformat()}",
            *[f"- {reason}" for reason in reasons],
        ]
    )
    (root / FAILURE_REPORT_PATH).write_text(content + "\n", encoding="utf-8")


def apply_watchdog_outcome(
    root: str | Path,
    result: WatchdogResult,
    now: datetime,
    *,
    notifier: Callable[[Path], int] | None,
) -> NotificationResult:
    project_root = Path(root)
    current = _normalize_time(now)
    with _alert_lifecycle_lock(project_root):
        if (
            result.generation is not None
            and _runtime_generation(project_root) != result.generation
        ):
            return NotificationResult(False, None, False)
        if (
            result.alert_revision is not None
            and _current_alert_revision(project_root) != result.alert_revision
        ):
            return NotificationResult(False, None, False)
        if result.healthy:
            cleared = _clear_alert_lifecycle_locked(
                project_root,
                current,
                result.generation,
                result.alert_revision,
            )
            return NotificationResult(False, None, cleared)

        _write_watchdog_failure(project_root, result.reasons, current)
        key = _incident_key("watchdog", *result.reasons)
        related_run_id = None
        try:
            status = _read_json(project_root / STATUS_PATH)
            value = status.get("run_id")
            related_run_id = value if isinstance(value, str) and value.strip() else None
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        return _alert_once_locked(
            project_root,
            key,
            notifier,
            current,
            related_run_id=related_run_id,
            incident_generation=result.generation,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    subparsers = parser.add_subparsers(dest="command", required=True)
    start = subparsers.add_parser("start")
    start.add_argument("--run-id", required=True)
    start.add_argument("--log-path", required=True)
    stage = subparsers.add_parser("stage")
    stage.add_argument("--run-id", required=True)
    stage.add_argument("--stage", required=True)
    fail = subparsers.add_parser("fail")
    fail.add_argument("--run-id", required=True)
    fail.add_argument("--stage", required=True)
    fail.add_argument("--exit-code", required=True, type=int)
    summary_group = fail.add_mutually_exclusive_group(required=True)
    summary_group.add_argument("--summary")
    summary_group.add_argument("--summary-base64")
    summary_group.add_argument("--summary-file")
    fail.add_argument("--notify", action="store_true")
    success = subparsers.add_parser("success")
    success.add_argument("--run-id", required=True)
    subparsers.add_parser("watchdog")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    if args.command == "start":
        start_run(root, args.run_id, args.log_path)
        return 0
    if args.command == "stage":
        stage_run(root, args.run_id, args.stage)
        return 0
    if args.command == "fail":
        notifier = _configured_notifier() if args.notify else None
        if args.summary is not None:
            summary = args.summary
        elif args.summary_base64 is not None:
            try:
                summary = base64.b64decode(args.summary_base64, validate=True).decode(
                    "utf-8"
                )
            except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
                parser.error(f"invalid --summary-base64: {exc}")
        else:
            try:
                summary = Path(args.summary_file).read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                parser.error(f"invalid --summary-file: {exc}")
        fail_run(
            root,
            args.run_id,
            args.stage,
            args.exit_code,
            summary,
            notifier=notifier,
        )
        return 0
    if args.command == "success":
        succeed_run(root, args.run_id)
        return 0

    current = _utc_now()
    result = check_daily_run(root, now=current)
    notification = apply_watchdog_outcome(
        root, result, current, notifier=_configured_notifier()
    )
    if result.healthy and notification.lifecycle_cleared:
        print("Daily production watchdog PASSED.")
        return 0
    if result.healthy:
        print(
            "Daily production watchdog FAILED: runtime artifacts changed "
            "before alert recovery could be committed."
        )
        return 1
    print("Daily production watchdog FAILED:")
    for reason in result.reasons:
        print(f"- {reason}")
    if notification.notification_attempted:
        print("Failure notification attempted once.")
    else:
        print(
            "Failure notification not sent because it was disabled or already attempted."
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
