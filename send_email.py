"""Send the generated daily watchlist by Gmail SMTP."""

from __future__ import annotations

import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path


HTML_ATTACHMENT = "daily_watchlist.html"
EMAIL_SUMMARY = "email_summary.txt"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SUBJECT = "Daily US Stock Watchlist"
DATA_FAILURE_SUBJECT = "Stock Screener Data Failure"
DATA_FAILURE_BODY = (
    "The stock screener could not obtain enough valid Yahoo Finance data.\n"
    "The previous valid watchlist has been preserved.\n"
    "No trading watchlist was generated from incomplete data."
)


def visible_email_body(summary: str) -> str:
    """Remove the machine-readable manifest from the user-facing plain-text body."""
    lines = summary.splitlines()
    start_marker = "Decision Manifest"
    end_marker = "End Decision Manifest"
    marker_count = (lines.count(start_marker), lines.count(end_marker))
    if marker_count == (0, 0):
        return summary
    if marker_count != (1, 1):
        raise ValueError("email decision manifest markers are malformed")

    start = lines.index(start_marker)
    end = lines.index(end_marker, start + 1)
    visible_lines = lines[:start] + lines[end + 1 :]
    return "\n".join(visible_lines).strip() + "\n"


def load_dotenv_if_available() -> None:
    """Load .env values when python-dotenv is installed; keep OS env support."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("python-dotenv not installed.")
        print("Run: pip install python-dotenv")
        return
    load_dotenv()


def build_message(sender: str, recipient: str, attachment_path: Path) -> EmailMessage:
    summary_path = Path(EMAIL_SUMMARY)
    summary = (
        summary_path.read_text(encoding="utf-8")
        if summary_path.exists()
        else (
            "Daily US Stock Watchlist is attached.\n\n"
            "Open daily_watchlist.html in a browser to view the full report."
        )
    )
    body = visible_email_body(summary)

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = SUBJECT
    message.set_content(body)

    message.add_attachment(
        attachment_path.read_bytes(),
        maintype="text",
        subtype="html",
        filename=attachment_path.name,
    )
    return message


def build_data_failure_message(sender: str, recipient: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = DATA_FAILURE_SUBJECT
    message.set_content(DATA_FAILURE_BODY)
    return message


def send_email(test_mode: bool = False) -> int:
    load_dotenv_if_available()

    attachment_path = Path(HTML_ATTACHMENT)
    if not attachment_path.exists():
        print(f"Error: {HTML_ATTACHMENT} does not exist.")
        return 1

    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_address or not gmail_app_password:
        print("Error: GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set.")
        return 1

    if test_mode:
        print("Email test passed.")
        return 0

    message = build_message(gmail_address, gmail_address, attachment_path)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(gmail_address, gmail_app_password)
        smtp.send_message(message)

    print("Email sent.")
    return 0


def send_data_failure_email(test_mode: bool = False) -> int:
    load_dotenv_if_available()

    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_address or not gmail_app_password:
        print("Error: GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set.")
        return 1

    if test_mode:
        print("Data failure email test passed.")
        return 0

    message = build_data_failure_message(gmail_address, gmail_address)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(gmail_address, gmail_app_password)
        smtp.send_message(message)

    print("Data failure email sent.")
    return 0


def main() -> int:
    args = set(sys.argv[1:])
    if "data_failure" in args:
        return send_data_failure_email(test_mode="test" in args)
    return send_email(test_mode="test" in args)


if __name__ == "__main__":
    raise SystemExit(main())
