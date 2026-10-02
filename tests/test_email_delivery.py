from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd
import pytest

import run_screener
import send_email
from ai_analysis import AIAnalysisResult


class RecordingSMTP:
    instances: list["RecordingSMTP"] = []

    def __init__(self, host: str, port: int, *, timeout: int):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.logins: list[tuple[str, str]] = []
        self.messages = []
        self.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def login(self, address: str, password: str) -> None:
        self.logins.append((address, password))

    def send_message(self, message) -> None:
        self.messages.append(message)


class FailingSMTP(RecordingSMTP):
    def __enter__(self):
        raise OSError("connection failed")


def test_normal_email_uses_implicit_tls_once(tmp_path: Path, monkeypatch):
    RecordingSMTP.instances.clear()
    (tmp_path / send_email.HTML_ATTACHMENT).write_text(
        "<html><body>Watchlist</body></html>", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GMAIL_ADDRESS", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-password")
    monkeypatch.setattr(send_email.smtplib, "SMTP_SSL", RecordingSMTP)

    assert send_email.send_email() == 0

    assert len(RecordingSMTP.instances) == 1
    smtp = RecordingSMTP.instances[0]
    assert (smtp.host, smtp.port, smtp.timeout) == (
        "smtp.gmail.com",
        465,
        send_email.SMTP_TIMEOUT_SECONDS,
    )
    assert smtp.logins == [("sender@example.com", "app-password")]
    assert len(smtp.messages) == 1


def test_data_failure_email_uses_implicit_tls_once(monkeypatch):
    RecordingSMTP.instances.clear()
    monkeypatch.setenv("GMAIL_ADDRESS", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-password")
    monkeypatch.setattr(send_email.smtplib, "SMTP_SSL", RecordingSMTP)

    assert send_email.send_data_failure_email() == 0

    assert len(RecordingSMTP.instances) == 1
    smtp = RecordingSMTP.instances[0]
    assert (smtp.host, smtp.port, smtp.timeout) == (
        "smtp.gmail.com",
        465,
        send_email.SMTP_TIMEOUT_SECONDS,
    )
    assert len(smtp.messages) == 1


def test_operational_failure_email_uses_report_body_once(tmp_path: Path, monkeypatch):
    RecordingSMTP.instances.clear()
    report = tmp_path / "failure.txt"
    report.write_text("production crashed at python stage", encoding="utf-8")
    monkeypatch.setenv("GMAIL_ADDRESS", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-password")
    monkeypatch.setattr(send_email.smtplib, "SMTP_SSL", RecordingSMTP)

    assert send_email.send_operational_failure_email(report) == 0

    assert len(RecordingSMTP.instances) == 1
    message = RecordingSMTP.instances[0].messages[0]
    assert message["Subject"] == send_email.OPERATIONAL_FAILURE_SUBJECT
    assert "production crashed at python stage" in message.get_content()


def test_smtp_failure_propagates_without_retry(tmp_path: Path, monkeypatch):
    FailingSMTP.instances.clear()
    (tmp_path / send_email.HTML_ATTACHMENT).write_text(
        "<html><body>Watchlist</body></html>", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GMAIL_ADDRESS", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-password")
    monkeypatch.setattr(send_email.smtplib, "SMTP_SSL", FailingSMTP)

    with pytest.raises(OSError, match="connection failed"):
        send_email.send_email()

    assert len(FailingSMTP.instances) == 1


def test_watchlist_sender_returns_failure_to_production(monkeypatch):
    monkeypatch.setattr(run_screener.config, "EMAIL_ENABLED", True)

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(run_screener.subprocess, "run", fail)

    assert run_screener.send_watchlist_email() == 1


def test_disabled_email_is_successful_no_op(monkeypatch):
    monkeypatch.setattr(run_screener.config, "EMAIL_ENABLED", False)

    def unexpected(*args, **kwargs):
        raise AssertionError("email subprocess must not run")

    monkeypatch.setattr(run_screener.subprocess, "run", unexpected)

    assert run_screener.send_watchlist_email() == 0


def test_main_returns_failure_when_email_delivery_fails(monkeypatch):
    empty = pd.DataFrame()
    market = run_screener.MarketConditionResult(
        frame=empty,
        status="Neutral",
        spy_valid=True,
        qqq_valid=True,
        data_failure=False,
        stats=run_screener.DownloadStats(),
        metrics={},
    )
    universe = run_screener.UniverseLoadResult(empty, 0, 0)
    quality = run_screener.RunQualityResult(
        valid=True,
        reason="",
        universe_count=0,
        requested_tickers=0,
        successful_downloads=0,
        failed_downloads=0,
        success_rate=1.0,
        spy_valid=True,
        qqq_valid=True,
        fallback_used=False,
    )
    ai_result = AIAnalysisResult(
        commentary="",
        top_action_list=empty,
        enabled=False,
        api_key_loaded=False,
        model="",
        tickers_analysed=0,
    )

    monkeypatch.setenv("SCREENER_VERIFIED", "1")
    monkeypatch.setattr(run_screener, "get_market_condition", lambda **kwargs: market)
    monkeypatch.setattr(run_screener, "load_universe", lambda **kwargs: universe)
    monkeypatch.setattr(
        run_screener,
        "screen_stocks",
        lambda *args, **kwargs: ({}, empty, 0, run_screener.DownloadStats()),
    )
    monkeypatch.setattr(
        run_screener, "validate_run_quality", lambda *args, **kwargs: quality
    )
    monkeypatch.setattr(run_screener, "print_data_quality_check", lambda *args: None)
    monkeypatch.setattr(
        run_screener,
        "export_results",
        lambda *args: (empty, empty, empty, {}, ai_result),
    )
    monkeypatch.setattr(run_screener, "print_ai_status", lambda *args: None)
    monkeypatch.setattr(run_screener, "print_category_summary", lambda *args: None)
    monkeypatch.setattr(run_screener, "send_watchlist_email", lambda: 1)

    assert run_screener.main([]) == 1
