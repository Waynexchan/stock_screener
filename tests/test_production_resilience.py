from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Barrier, Event, Thread
import time

import pytest

import production_monitor
import run_screener


def _write_report_bundle(
    root: Path,
    signal_date: str,
    run_id: str = "run-3",
    published_at: str = "2026-10-01T19:00:00+00:00",
) -> None:
    reports = {
        "csv": root / "daily_watchlist.csv",
        "markdown": root / "daily_watchlist.md",
        "html": root / "daily_watchlist.html",
        "email": root / "email_summary.txt",
    }
    for name, path in reports.items():
        path.write_text(f"{name} report\n", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "signal_trading_date": signal_date,
        "run_id": run_id,
        "published_at": published_at,
        "files": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in reports.values()
        },
    }
    (root / run_screener.REPORT_PUBLISH_MANIFEST).write_text(
        json.dumps(manifest), encoding="utf-8"
    )


def test_failed_run_records_status_report_and_only_one_alert(tmp_path: Path):
    attempts: list[str] = []
    now = datetime(2026, 10, 1, 18, 5, tzinfo=timezone.utc)

    production_monitor.start_run(
        tmp_path, "run-1", "logs/production_runs/run-1.log", now
    )
    first = production_monitor.fail_run(
        tmp_path,
        "run-1",
        "python",
        7,
        "RuntimeError: exploded",
        now=now,
        notifier=lambda report: (
            attempts.append(report.read_text(encoding="utf-8")) or 0
        ),
    )
    second = production_monitor.fail_run(
        tmp_path,
        "run-1",
        "python",
        7,
        "RuntimeError: exploded",
        now=now,
        notifier=lambda report: attempts.append("duplicate") or 0,
    )

    status = json.loads(
        (tmp_path / production_monitor.STATUS_PATH).read_text(encoding="utf-8")
    )
    assert status["state"] == "FAILED"
    assert status["stage"] == "python"
    assert status["exit_code"] == 7
    assert status["completed_at"] == now.isoformat()
    assert "RuntimeError: exploded" in (
        tmp_path / production_monitor.FAILURE_REPORT_PATH
    ).read_text(encoding="utf-8")
    assert first.notification_attempted is True
    assert second.notification_attempted is False
    assert len(attempts) == 1


def test_failure_cli_accepts_base64_summary_without_argument_splitting(tmp_path: Path):
    summary = "Set-Content failed | path with spaces | --looks-like-an-option"
    encoded = base64.b64encode(summary.encode("utf-8")).decode("ascii")
    assert (
        production_monitor.main(
            [
                "--root",
                str(tmp_path),
                "start",
                "--run-id",
                "cli-run",
                "--log-path",
                "logs/cli.log",
            ]
        )
        == 0
    )

    assert (
        production_monitor.main(
            [
                "--root",
                str(tmp_path),
                "fail",
                "--run-id",
                "cli-run",
                "--stage",
                "verification",
                "--exit-code",
                "1",
                "--summary-base64",
                encoded,
            ]
        )
        == 0
    )
    status = json.loads(
        (tmp_path / production_monitor.STATUS_PATH).read_text(encoding="utf-8")
    )
    assert status["error_summary"] == summary


def test_failure_cli_reads_very_large_special_summary_from_utf8_file(
    tmp_path: Path,
):
    summary = ("failure | --option Ω 漢字 \x00 with spaces\n" * 4000) + "tail"
    summary_path = tmp_path / "failure-summary.txt"
    summary_path.write_text(summary, encoding="utf-8")
    production_monitor.start_run(
        tmp_path, "large-summary-run", "logs/large-summary.log"
    )

    result = subprocess.run(
        [
            sys.executable,
            str(Path(production_monitor.__file__).resolve()),
            "--root",
            str(tmp_path),
            "fail",
            "--run-id",
            "large-summary-run",
            "--stage",
            "verification",
            "--exit-code",
            "1",
            "--summary-file",
            str(summary_path),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )

    status = json.loads(
        (tmp_path / production_monitor.STATUS_PATH).read_text(encoding="utf-8")
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(status["error_summary"]) == production_monitor.MAX_ERROR_SUMMARY_LENGTH
    assert "\x00" not in status["error_summary"]
    assert "failure | --option Ω 漢字 with spaces" in status["error_summary"]


def test_powershell_failure_summary_normalizer_bounds_special_text(tmp_path: Path):
    summary_path = tmp_path / "summary-input.txt"
    result_path = tmp_path / "summary-output.txt"
    summary_path.write_text(
        ("failure | --option Ω 漢字 \x00 with spaces\n" * 4000) + "tail",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(
        {
            "SUMMARY_INPUT_PATH": str(summary_path),
            "SUMMARY_OUTPUT_PATH": str(result_path),
            "WRAPPER_PATH": str(Path("scripts/run_daily_production.ps1").resolve()),
        }
    )
    command = "\n".join(
        [
            "$tokens = $null",
            "$errors = $null",
            "$ast = [System.Management.Automation.Language.Parser]::ParseFile($env:WRAPPER_PATH, [ref]$tokens, [ref]$errors)",
            "$functionAst = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'ConvertTo-BoundedFailureSummary' }, $true)",
            "Invoke-Expression $functionAst.Extent.Text",
            "$script:maxFailureSummaryLength = 1000",
            "$summary = [System.IO.File]::ReadAllText($env:SUMMARY_INPUT_PATH, [System.Text.Encoding]::UTF8)",
            "$result = ConvertTo-BoundedFailureSummary $summary",
            "[System.IO.File]::WriteAllText($env:SUMMARY_OUTPUT_PATH, $result, [System.Text.UTF8Encoding]::new($false))",
        ]
    )

    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    bounded = result_path.read_text(encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(bounded) == production_monitor.MAX_ERROR_SUMMARY_LENGTH
    assert "\x00" not in bounded
    assert "\n" not in bounded
    assert "failure | --option Ω 漢字 with spaces" in bounded


def test_watchdog_for_same_failed_run_cannot_send_a_second_alert(tmp_path: Path):
    attempts: list[str] = []
    now = datetime(2026, 10, 1, 18, 5, tzinfo=timezone.utc)
    production_monitor.start_run(tmp_path, "same-run", "logs/run.log", now)
    production_monitor.fail_run(
        tmp_path,
        "same-run",
        "python",
        1,
        "crash",
        now=now,
        notifier=lambda _: attempts.append("production") or 0,
    )

    result = production_monitor._alert_once(
        tmp_path,
        "different-watchdog-key",
        lambda _: attempts.append("watchdog") or 0,
        now,
        related_run_id="same-run",
    )

    assert result.notification_attempted is False
    assert attempts == ["production"]


def test_legacy_attempted_alert_state_remains_deduplicated(tmp_path: Path):
    now = datetime(2026, 10, 1, 18, 5, tzinfo=timezone.utc)
    state_path = tmp_path / production_monitor.ALERT_STATE_PATH
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "active_incident_key": "old-key",
                "attempted_at": now.isoformat(),
                "notification_succeeded": True,
                "related_run_id": "old-run",
                "schema_version": 1,
            }
        ),
        encoding="utf-8",
    )

    result = production_monitor._alert_once(
        tmp_path,
        "new-watchdog-key",
        lambda _: (_ for _ in ()).throw(AssertionError("must not send")),
        now,
        related_run_id="old-run",
    )

    assert result.notification_attempted is False


def test_concurrent_alert_attempts_make_one_atomic_claim(tmp_path: Path):
    attempts: list[str] = []
    now = datetime(2026, 10, 1, 18, 5, tzinfo=timezone.utc)
    (tmp_path / production_monitor.FAILURE_REPORT_PATH).write_text(
        "failure", encoding="utf-8"
    )

    def attempt(_index: int):
        return production_monitor._alert_once(
            tmp_path,
            "incident",
            lambda _: attempts.append("sent") or 0,
            now,
            related_run_id="one-run",
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(attempt, range(16)))

    assert sum(result.notification_attempted for result in results) == 1
    assert attempts == ["sent"]


def test_healthy_clear_cannot_race_inflight_alert_or_replay_stale_failure(
    tmp_path: Path,
):
    now = datetime(2026, 10, 1, 19, 0, tzinfo=timezone.utc)
    expected_session = date(2026, 9, 30)
    production_monitor.start_run(tmp_path, "failed-run", "logs/failed.log", now)
    production_monitor.fail_run(
        tmp_path,
        "failed-run",
        "python",
        1,
        "failed",
        now=now,
        notifier=None,
    )
    _write_report_bundle(tmp_path, expected_session.isoformat(), "failed-run")
    unhealthy = production_monitor.check_daily_run(
        tmp_path,
        now=now,
        expected_session_provider=lambda _: expected_session,
        semantic_validator=lambda *_: None,
    )
    assert unhealthy.healthy is False

    attempts: list[str] = []
    notifier_started = Event()
    release_notifier = Event()
    first_done = Event()

    def blocked_notifier(_path: Path) -> int:
        attempts.append("first")
        notifier_started.set()
        assert release_notifier.wait(timeout=5)
        return 0

    def send_first() -> None:
        production_monitor.apply_watchdog_outcome(
            tmp_path, unhealthy, now, notifier=blocked_notifier
        )
        first_done.set()

    first = Thread(target=send_first)
    first.start()
    assert notifier_started.wait(timeout=5)

    good_started = now + timedelta(minutes=1)
    production_monitor.start_run(
        tmp_path, "healthy-run", "logs/healthy.log", good_started
    )
    status_path = tmp_path / production_monitor.STATUS_PATH
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status.update(
        {
            "state": "SUCCEEDED",
            "stage": "complete",
            "completed_at": (good_started + timedelta(minutes=1)).isoformat(),
            "exit_code": 0,
        }
    )
    status_path.write_text(json.dumps(status), encoding="utf-8")
    _write_report_bundle(
        tmp_path,
        expected_session.isoformat(),
        "healthy-run",
        (good_started + timedelta(seconds=30)).isoformat(),
    )
    healthy = production_monitor.check_daily_run(
        tmp_path,
        now=good_started + timedelta(minutes=2),
        expected_session_provider=lambda _: expected_session,
        semantic_validator=lambda *_: None,
    )
    assert healthy.healthy is True

    clear_done = Event()

    def clear_health() -> None:
        production_monitor.apply_watchdog_outcome(
            tmp_path,
            healthy,
            good_started + timedelta(minutes=2),
            notifier=lambda _: attempts.append("unexpected-clear") or 0,
        )
        clear_done.set()

    clear = Thread(target=clear_health)
    clear.start()
    clear_finished_while_notifier_blocked = clear_done.wait(timeout=0.2)
    release_notifier.set()
    first.join(timeout=5)
    clear.join(timeout=5)
    assert first_done.is_set()
    assert clear_done.is_set()

    replay = production_monitor.apply_watchdog_outcome(
        tmp_path,
        unhealthy,
        good_started + timedelta(minutes=3),
        notifier=lambda _: attempts.append("second") or 0,
    )

    assert clear_finished_while_notifier_blocked is False
    assert replay.notification_attempted is False
    assert attempts == ["first"]


def test_atomic_json_writers_do_not_share_temporary_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    target = tmp_path / "state.json"
    barrier = Barrier(2)
    original_replace = Path.replace
    errors: list[BaseException] = []
    replace_sources: list[Path] = []

    def synchronized_replace(self: Path, destination: Path):
        if destination == target:
            replace_sources.append(self)
            barrier.wait(timeout=5)
        return original_replace(self, destination)

    monkeypatch.setattr(Path, "replace", synchronized_replace)

    def write(value: int) -> None:
        try:
            production_monitor._atomic_write_json(target, {"value": value})
        except BaseException as exc:  # pragma: no branch - collected for assertion
            errors.append(exc)

    writers = [Thread(target=write, args=(value,)) for value in (1, 2)]
    for writer in writers:
        writer.start()
    for writer in writers:
        writer.join(timeout=5)

    assert len(set(replace_sources)) == 2
    assert not errors
    assert json.loads(target.read_text(encoding="utf-8"))["value"] in {1, 2}


def test_alert_lifecycle_lock_serializes_separate_processes(tmp_path: Path):
    holder_code = (
        "from pathlib import Path; import time; import production_monitor as p; "
        "root=Path(r'%s'); "
        "ctx=p._alert_lifecycle_lock(root); ctx.__enter__(); "
        "(root/'holder-ready').write_text('ready'); "
        "\nwhile not (root/'release-holder').exists(): time.sleep(0.02)\n"
        "ctx.__exit__(None,None,None)" % tmp_path
    )
    waiter_code = (
        "from pathlib import Path; import production_monitor as p; "
        "root=Path(r'%s'); "
        "\nwith p._alert_lifecycle_lock(root): "
        "(root/'waiter-acquired').write_text('acquired')" % tmp_path
    )
    holder = subprocess.Popen(
        [sys.executable, "-c", holder_code],
        cwd=Path.cwd(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    waiter: subprocess.Popen[str] | None = None
    try:
        deadline = time.monotonic() + 5
        while not (tmp_path / "holder-ready").exists():
            assert time.monotonic() < deadline
            time.sleep(0.02)
        waiter = subprocess.Popen(
            [sys.executable, "-c", waiter_code],
            cwd=Path.cwd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        time.sleep(0.2)
        assert not (tmp_path / "waiter-acquired").exists()
    finally:
        (tmp_path / "release-holder").write_text("release", encoding="utf-8")
        holder_stdout, holder_stderr = holder.communicate(timeout=5)
    assert holder.returncode == 0, holder_stdout + holder_stderr
    assert waiter is not None
    waiter_stdout, waiter_stderr = waiter.communicate(timeout=5)
    assert waiter.returncode == 0, waiter_stdout + waiter_stderr
    assert (tmp_path / "waiter-acquired").read_text() == "acquired"


def test_alert_lifecycle_clears_after_health_and_allows_same_incident_again(
    tmp_path: Path,
):
    attempts: list[str] = []
    now = datetime(2026, 10, 1, 18, 5, tzinfo=timezone.utc)
    unhealthy = production_monitor.WatchdogResult(False, ("same incident",))
    healthy = production_monitor.WatchdogResult(True, ())

    production_monitor.apply_watchdog_outcome(
        tmp_path,
        unhealthy,
        now,
        notifier=lambda _: attempts.append("first") or 0,
    )
    production_monitor.apply_watchdog_outcome(
        tmp_path,
        healthy,
        now + timedelta(minutes=1),
        notifier=lambda _: attempts.append("unexpected") or 0,
    )
    cleared = json.loads(
        (tmp_path / production_monitor.ALERT_STATE_PATH).read_text(encoding="utf-8")
    )
    assert cleared["delivery_phase"] == "CLEARED"
    assert cleared["active_incident_key"] is None
    assert not list(
        (tmp_path / production_monitor.ALERT_CLAIM_DIRECTORY).glob("*.claimed")
    )
    production_monitor.apply_watchdog_outcome(
        tmp_path,
        unhealthy,
        now + timedelta(minutes=2),
        notifier=lambda _: attempts.append("second") or 0,
    )

    state = json.loads(
        (tmp_path / production_monitor.ALERT_STATE_PATH).read_text(encoding="utf-8")
    )
    assert attempts == ["first", "second"]
    assert state["delivery_phase"] == "COMPLETE"


def test_healthy_clear_revalidates_runtime_generation(tmp_path: Path):
    now = datetime(2026, 10, 1, 19, 0, tzinfo=timezone.utc)
    expected_session = date(2026, 9, 30)
    production_monitor.start_run(tmp_path, "healthy-run", "logs/healthy.log", now)
    production_monitor.succeed_run(tmp_path, "healthy-run", now=now)
    _write_report_bundle(tmp_path, expected_session.isoformat(), "healthy-run")
    healthy = production_monitor.check_daily_run(
        tmp_path,
        now=now,
        expected_session_provider=lambda _: expected_session,
        semantic_validator=lambda *_: None,
    )
    assert healthy.healthy is True
    production_monitor._alert_once(
        tmp_path,
        "incident-after-check",
        lambda _: 0,
        now,
    )

    production_monitor.start_run(
        tmp_path,
        "new-run-started-after-health-check",
        "logs/new.log",
        now + timedelta(minutes=1),
    )
    production_monitor.apply_watchdog_outcome(
        tmp_path,
        healthy,
        now + timedelta(minutes=1),
        notifier=lambda _: (_ for _ in ()).throw(AssertionError("must not notify")),
    )

    state = json.loads(
        (tmp_path / production_monitor.ALERT_STATE_PATH).read_text(encoding="utf-8")
    )
    assert state["active_incident_key"] == "incident-after-check"
    assert state["delivery_phase"] == "COMPLETE"


def test_stale_prepared_claim_is_recovered_before_delivery(tmp_path: Path):
    attempts: list[str] = []
    now = datetime(2026, 10, 1, 18, 5, tzinfo=timezone.utc)
    incident_key = "claim-only-crash"
    claim = production_monitor._alert_claim_path(tmp_path, incident_key, None)
    claim.parent.mkdir(parents=True, exist_ok=True)
    claim.write_text(
        json.dumps(
            {
                "created_at": (
                    now
                    - timedelta(
                        seconds=production_monitor.ALERT_PREPARED_TTL_SECONDS + 1
                    )
                ).isoformat(),
                "incident_key": incident_key,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / production_monitor.FAILURE_REPORT_PATH).write_text(
        "failure", encoding="utf-8"
    )

    result = production_monitor._alert_once(
        tmp_path,
        incident_key,
        lambda _: attempts.append("recovered") or 0,
        now,
    )

    assert result.notification_attempted is True
    assert attempts == ["recovered"]


def test_success_records_completion_and_resolves_stale_failure(tmp_path: Path):
    now = datetime(2026, 10, 1, 18, 5, tzinfo=timezone.utc)
    production_monitor.start_run(tmp_path, "run-2", "logs/run-2.log", now)
    (tmp_path / production_monitor.FAILURE_REPORT_PATH).write_text(
        "old failure", encoding="utf-8"
    )

    production_monitor.succeed_run(tmp_path, "run-2", now=now)

    status = json.loads(
        (tmp_path / production_monitor.STATUS_PATH).read_text(encoding="utf-8")
    )
    assert status["state"] == "SUCCEEDED"
    assert status["exit_code"] == 0
    assert "RESOLVED" in (tmp_path / production_monitor.FAILURE_REPORT_PATH).read_text(
        encoding="utf-8"
    )


def test_validation_failure_preserves_entire_public_report_bundle(tmp_path: Path):
    public = {}
    staged = {}
    for name in ("csv", "markdown", "html", "email"):
        public[name] = tmp_path / f"public-{name}"
        public[name].write_text(f"old-{name}", encoding="utf-8")
        staged[name] = tmp_path / f"staged-{name}"
        staged[name].write_text(f"new-{name}", encoding="utf-8")
    manifest = tmp_path / "publish.json"
    manifest.write_text("old-manifest", encoding="utf-8")

    with pytest.raises(RuntimeError, match="semantic mismatch"):
        run_screener.publish_staged_reports(
            staged,
            public,
            manifest,
            "2026-09-30",
            validator=lambda: (_ for _ in ()).throw(RuntimeError("semantic mismatch")),
        )

    assert {
        name: path.read_text(encoding="utf-8") for name, path in public.items()
    } == {name: f"old-{name}" for name in public}
    assert manifest.read_text(encoding="utf-8") == "old-manifest"


def test_validated_report_bundle_publishes_matching_manifest_last(tmp_path: Path):
    public = {}
    staged = {}
    for name in ("csv", "markdown", "html", "email"):
        public[name] = tmp_path / f"public-{name}"
        public[name].write_text(f"old-{name}", encoding="utf-8")
        staged[name] = tmp_path / f"staged-{name}"
        staged[name].write_text(f"new-{name}", encoding="utf-8")
    manifest = tmp_path / "publish.json"

    run_screener.publish_staged_reports(
        staged,
        public,
        manifest,
        "2026-09-30",
        validator=lambda: None,
        generated_at=datetime(2026, 10, 1, 18, 5, tzinfo=timezone.utc),
        run_id="publish-run",
    )

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["signal_trading_date"] == "2026-09-30"
    assert payload["published_at"] == "2026-10-01T18:05:00+00:00"
    assert payload["run_id"] == "publish-run"
    for name, path in public.items():
        assert path.read_text(encoding="utf-8") == f"new-{name}"
        assert (
            payload["files"][path.name] == hashlib.sha256(path.read_bytes()).hexdigest()
        )


def test_watchdog_accepts_current_complete_consistent_run(tmp_path: Path):
    now = datetime(2026, 10, 1, 19, 0, tzinfo=timezone.utc)
    production_monitor.start_run(tmp_path, "run-3", "logs/run-3.log", now)
    production_monitor.succeed_run(tmp_path, "run-3", now=now)
    _write_report_bundle(tmp_path, "2026-09-30")

    result = production_monitor.check_daily_run(
        tmp_path,
        now=now,
        expected_session_provider=lambda _: date(2026, 9, 30),
        semantic_validator=lambda *_: None,
    )

    assert result.healthy is True
    assert result.reasons == ()


@pytest.mark.parametrize(
    "now, started, completed, expected_session",
    [
        (
            datetime(2026, 10, 1, 23, 10, tzinfo=timezone.utc),
            datetime(2026, 10, 1, 22, 55, tzinfo=timezone.utc),
            datetime(2026, 10, 1, 23, 5, tzinfo=timezone.utc),
            date(2026, 10, 1),
        ),
        (
            datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 10, 2, 21, 0, tzinfo=timezone.utc),
            datetime(2026, 10, 2, 21, 20, tzinfo=timezone.utc),
            date(2026, 10, 2),
        ),
        (
            datetime(2026, 11, 26, 22, 0, tzinfo=timezone.utc),
            datetime(2026, 11, 25, 21, 30, tzinfo=timezone.utc),
            datetime(2026, 11, 25, 22, 0, tzinfo=timezone.utc),
            date(2026, 11, 25),
        ),
    ],
)
def test_watchdog_accepts_cross_midnight_weekend_and_holiday_session_lifecycle(
    tmp_path: Path,
    now: datetime,
    started: datetime,
    completed: datetime,
    expected_session: date,
):
    production_monitor.start_run(tmp_path, "session-run", "logs/run.log", started)
    production_monitor.succeed_run(tmp_path, "session-run", now=completed)
    published = completed - timedelta(minutes=1)
    _write_report_bundle(
        tmp_path,
        expected_session.isoformat(),
        "session-run",
        published.isoformat(),
    )

    result = production_monitor.check_daily_run(
        tmp_path,
        now=now,
        expected_session_provider=lambda _: expected_session,
        semantic_validator=lambda *_: None,
    )

    assert result.healthy is True


def test_session_close_window_respects_new_york_daylight_saving_time():
    winter = production_monitor._default_session_close(date(2026, 1, 5))
    summer = production_monitor._default_session_close(date(2026, 7, 1))

    assert (winter.hour, winter.minute) == (21, 15)
    assert (summer.hour, summer.minute) == (20, 15)


@pytest.mark.parametrize(
    "mutation, expected_reason",
    [
        ("missing_status", "production status is missing"),
        ("failed_status", "latest production state is FAILED"),
        (
            "stale_run",
            "production started before the expected trading-session window",
        ),
        ("stale_session", "publish trading date 2026-09-29"),
        ("hash_mismatch", "hash mismatch for daily_watchlist.csv"),
        ("semantic_failure", "semantic validation failed"),
        ("run_mismatch", "report publish run ID does not match"),
        ("missing_run_id", "production run ID is missing or invalid"),
        ("invalid_completion", "production completion time is missing or invalid"),
        ("missing_publish_run_id", "report publish run ID is missing or invalid"),
        ("publish_before_start", "report publish time precedes production start"),
    ],
)
def test_watchdog_fails_closed_for_unhealthy_state(
    tmp_path: Path, mutation: str, expected_reason: str
):
    now = datetime(2026, 10, 1, 19, 0, tzinfo=timezone.utc)
    started = (
        now
        if mutation != "stale_run"
        else datetime(2026, 9, 29, 19, tzinfo=timezone.utc)
    )
    production_monitor.start_run(tmp_path, "run-4", "logs/run-4.log", started)
    if mutation == "failed_status":
        production_monitor.fail_run(
            tmp_path, "run-4", "python", 1, "failed", now=now, notifier=None
        )
    else:
        production_monitor.succeed_run(tmp_path, "run-4", now=now)
    _write_report_bundle(
        tmp_path,
        "2026-09-29" if mutation == "stale_session" else "2026-09-30",
        (
            "wrong-run"
            if mutation == "run_mismatch"
            else ""
            if mutation == "missing_publish_run_id"
            else "run-4"
        ),
        (
            "2026-09-30T19:00:00+00:00"
            if mutation == "publish_before_start"
            else "2026-10-01T19:00:00+00:00"
        ),
    )
    if mutation == "missing_status":
        (tmp_path / production_monitor.STATUS_PATH).unlink()
    if mutation == "hash_mismatch":
        (tmp_path / "daily_watchlist.csv").write_text("changed", encoding="utf-8")
    if mutation in {"missing_run_id", "invalid_completion"}:
        status_path = tmp_path / production_monitor.STATUS_PATH
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if mutation == "missing_run_id":
            status["run_id"] = ""
        else:
            status["completed_at"] = "not-a-time"
        status_path.write_text(json.dumps(status), encoding="utf-8")

    def validate(*_):
        if mutation == "semantic_failure":
            raise RuntimeError("reports differ")

    result = production_monitor.check_daily_run(
        tmp_path,
        now=now,
        expected_session_provider=lambda _: date(2026, 9, 30),
        semantic_validator=validate,
    )

    assert result.healthy is False
    assert any(expected_reason in reason for reason in result.reasons)


def test_production_wrapper_has_status_failure_and_unique_utf8_log_contract():
    text = Path("scripts/run_daily_production.ps1").read_text(encoding="utf-8")

    assert text.index("[System.Threading.Mutex]::new") < text.index(
        'Invoke-Monitor @("start"'
    )
    assert text.index("function Invoke-ProductionWorkflow") < text.index(
        "New-Item -ItemType Directory"
    )
    assert "Production run already active; lock contention exit 75." in text
    assert 'Invoke-Monitor @("start"' in text
    assert 'Invoke-Monitor @("stage"' in text
    assert "production_monitor.py fail" in text
    assert "ConvertTo-BoundedFailureSummary" in text
    assert "--summary-file" in text
    assert "--summary-base64" not in text
    assert 'Invoke-Monitor @("success"' in text
    assert "production_runs" in text
    assert "-Encoding utf8" in text
    assert "Tee-Object" not in text
    assert "catch" in text


def test_watchdog_wrapper_is_independent_entry_point():
    text = Path("scripts/check_daily_run.ps1").read_text(encoding="utf-8")

    assert "production_monitor.py watchdog" in text
    assert "run_daily_production.ps1" not in text


def test_two_parallel_production_wrappers_have_one_mutex_owner(tmp_path: Path):
    source = Path("scripts/run_daily_production.ps1").resolve()
    script = tmp_path / "scripts" / source.name
    script.parent.mkdir(parents=True)
    script.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    status = tmp_path / production_monitor.STATUS_PATH
    status.parent.mkdir(parents=True)
    status.write_text("sentinel-status\n", encoding="utf-8")
    env = os.environ.copy()
    env["SCREENER_MUTEX_PROBE"] = "1"
    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-MutexProbe",
    ]
    first = subprocess.Popen(
        command,
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        assert first.stdout is not None
        assert first.stdout.readline().strip() == "MUTEX_PROBE_ACQUIRED"
        second = subprocess.run(
            command,
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert second.returncode == production_monitor.PRODUCTION_LOCKED_EXIT_CODE
        assert "already active" in (second.stdout + second.stderr)
    finally:
        first.wait(timeout=10)
    assert first.returncode == 0
    assert status.read_text(encoding="utf-8") == "sentinel-status\n"
    assert not (tmp_path / "logs" / "production.log").exists()
