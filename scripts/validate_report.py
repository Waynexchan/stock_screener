"""Validate report structure, row semantics, and cross-output decisions."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import re
import sys


STATES = {"FULL", "HALF", "WATCH", "NO TRADE"}


def truth(value: object) -> bool:
    return value is True or str(value).strip().lower() == "true"


def number(value: object) -> float | None:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def manifest_record(row: dict[str, object]) -> dict[str, object]:
    risk = number(row.get("Maximum Risk R", row.get("maximum_risk_r")))
    risk_dollars = number(
        row.get("Maximum Risk Dollars", row.get("maximum_risk_dollars"))
    )
    shares = number(row.get("Maximum Shares", row.get("maximum_shares")))
    return {
        "ticker": str(row.get("Ticker", row.get("ticker", ""))),
        "decision": str(row.get("Final Decision", row.get("decision", ""))),
        "maximum_risk_r": risk,
        "maximum_risk_dollars": risk_dollars,
        "maximum_shares": None if shares is None else int(shares),
        "actionable": truth(row.get("Actionable", row.get("actionable", False))),
        "confirmed_setup": truth(
            row.get("Confirmed Setup", row.get("confirmed_setup", False))
        ),
        "setup_integrity": str(
            row.get("Setup Integrity", row.get("setup_integrity", ""))
        ),
        "review_tier": str(row.get("Review Tier", row.get("review_tier", ""))),
        "action": str(row.get("Action", row.get("action", ""))),
    }


def read_html_manifest(text: str) -> list[dict[str, object]]:
    match = re.search(
        r'<script type="application/json" id="decision-manifest">(.*?)</script>',
        text,
        flags=re.DOTALL,
    )
    if not match:
        raise ValueError("HTML decision manifest missing")
    return json.loads(match.group(1).replace("<\\/", "</"))


def read_csv_rows(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_email_manifest(path: Path) -> list[dict[str, object]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index("Decision Manifest") + 1
        end = lines.index("End Decision Manifest", start)
    except ValueError as exc:
        raise ValueError("email decision manifest missing") from exc
    return [json.loads(line) for line in lines[start:end] if line.strip()]


def validate_manifest(rows: list[dict[str, object]]) -> list[str]:
    errors: list[str] = []
    tickers = [str(row.get("ticker", "")) for row in rows]
    if len(tickers) != len(set(tickers)):
        errors.append("duplicate tickers in decision manifest")
    for raw in rows:
        row = manifest_record(raw)
        ticker = row["ticker"] or "<missing ticker>"
        state = row["decision"]
        risk = row["maximum_risk_r"]
        risk_dollars = row["maximum_risk_dollars"]
        shares = row["maximum_shares"]
        actionable = bool(row["actionable"])
        confirmed = bool(row["confirmed_setup"])
        if state not in STATES:
            errors.append(f"{ticker}: unsupported state {state}")
            continue
        if state == "FULL" and (
            risk != 1.0 or risk_dollars != 587.0 or not shares or not actionable
        ):
            errors.append(f"{ticker}: FULL risk/shares/actionable invariant failed")
        if state == "HALF" and (
            risk != 0.5 or risk_dollars != 293.5 or not shares or not actionable
        ):
            errors.append(f"{ticker}: HALF risk/shares/actionable invariant failed")
        if state in {"WATCH", "NO TRADE"} and (
            risk not in {0, 0.0}
            or risk_dollars not in {0, 0.0}
            or shares not in {0, None}
            or actionable
        ):
            errors.append(f"{ticker}: non-actionable risk/share invariant failed")
        if actionable != confirmed:
            errors.append(f"{ticker}: confirmed setup contradicts actionability")
        if (
            actionable
            and "watch later"
            in (str(row["review_tier"]) + " " + str(row["action"])).lower()
        ):
            errors.append(f"{ticker}: Watch Later coexists with actionable state")
    return errors


def validate_csv_semantics(rows: list[dict[str, object]]) -> list[str]:
    errors = validate_manifest([manifest_record(row) for row in rows])
    for row in rows:
        ticker = str(row.get("Ticker", "<missing ticker>"))
        actionable = str(row.get("Final Decision", "")) in {"FULL", "HALF"}
        if not actionable:
            continue
        recent = number(row.get("Recent RS Score"))
        entry = number(row.get("Planned Entry"))
        stop = number(row.get("Initial Stop"))
        rr = number(row.get("Reward/Risk Ratio"))
        if recent is None:
            errors.append(f"{ticker}: Missing Recent RS is actionable")
        if row.get("Realistic Target Source") == "model 2R feasibility target":
            errors.append(f"{ticker}: synthetic model 2R target is actionable")
        if row.get("Price Freshness Status") != "CURRENT":
            errors.append(f"{ticker}: stale price data is actionable")
        if entry is None or stop is None or stop >= entry:
            errors.append(f"{ticker}: invalid stop is actionable")
        if rr is None or rr < 2:
            errors.append(f"{ticker}: invalid R/R is actionable")
        if row.get("Extension Status") == "Overextended":
            errors.append(f"{ticker}: overextended setup is actionable")
        if str(row.get("Concentration Exclusion Reason", "")).strip():
            errors.append(f"{ticker}: concentration violation received shares")
        reasons = (
            str(row.get("Invalidation Reason", ""))
            + " "
            + str(row.get("Decision Reasons", ""))
        ).lower()
        if any(
            phrase in reasons
            for phrase in (
                "portfolio heat exhausted",
                "maximum open-position count reached",
                "industry heat limit exceeded",
                "theme heat limit exceeded",
            )
        ):
            errors.append(f"{ticker}: portfolio violation received shares")
    return errors


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    html_path = Path(args[0] if args else "daily_watchlist_dry_run.html")
    csv_path = Path(args[1]) if len(args) > 1 else html_path.with_suffix(".csv")
    email_path = (
        Path(args[2])
        if len(args) > 2
        else html_path.with_name(html_path.stem + "_email.txt")
    )
    if not html_path.exists():
        print(f"Missing report: {html_path}")
        return 1
    text = html_path.read_text(encoding="utf-8")
    required = [
        "Executive Summary",
        "Market Status",
        "Portfolio Risk",
        "Top Industries",
        "FULL",
        "HALF",
        "WATCH",
        "NO TRADE",
        "Data and Logic Warnings",
        "Expectancy",
    ]
    errors = [f"missing section: {item}" for item in required if item not in text]
    try:
        html_manifest = [manifest_record(row) for row in read_html_manifest(text)]
        errors.extend(validate_manifest(html_manifest))
    except (ValueError, json.JSONDecodeError) as exc:
        html_manifest = []
        errors.append(str(exc))

    if csv_path.exists():
        csv_rows = read_csv_rows(csv_path)
        csv_manifest = sorted(
            (manifest_record(row) for row in csv_rows),
            key=lambda row: str(row["ticker"]),
        )
        errors.extend(validate_csv_semantics(csv_rows))
        if csv_manifest != html_manifest:
            errors.append("CSV and HTML decisions differ")
    elif len(args) > 1:
        errors.append(f"missing CSV: {csv_path}")

    if email_path.exists():
        try:
            email_manifest = [
                manifest_record(row) for row in read_email_manifest(email_path)
            ]
            errors.extend(validate_manifest(email_manifest))
            if email_manifest != html_manifest:
                errors.append("email and HTML decisions differ")
        except (ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
    elif len(args) > 2:
        errors.append(f"missing email: {email_path}")

    if errors:
        print("Report semantic validation FAIL: " + "; ".join(dict.fromkeys(errors)))
        return 1
    print(f"Report semantic validation PASS: {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
