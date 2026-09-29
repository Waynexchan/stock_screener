"""Validate report structure, row semantics, and cross-output decisions."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import re
import sys


STATES = {"FULL", "HALF", "WATCH", "NO TRADE"}
REPORT_SECTIONS = {"Actionable Now", "Pattern Watchlist", "Avoid / Failed"}
LANES = (
    "Tight Base / VCP",
    "Pullback to Support",
    "Breakout Retest / High Flag",
)


def truth(value: object) -> bool:
    return value is True or str(value).strip().lower() == "true"


def number(value: object) -> float | None:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def is_present_nonfinite_number(value: object) -> bool:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return False
    return not math.isnan(parsed) and not math.isfinite(parsed)


def rank_number(value: object) -> int | None:
    parsed = number(value)
    if parsed is None:
        return None
    return int(parsed) if parsed.is_integer() else -1


def report_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    parsed = str(value).strip()
    return "" if parsed.lower() in {"nan", "none"} else parsed


def has_pattern_failure_evidence(row: dict[str, object]) -> bool:
    freshness = report_text(row.get("Price Freshness Status")).upper()
    if freshness != "CURRENT":
        return True
    if report_text(row.get("Price Data Warning")):
        return True
    if is_present_nonfinite_number(row.get("Planned Entry")) or (
        is_present_nonfinite_number(row.get("Initial Stop"))
    ):
        return True
    entry = number(row.get("Planned Entry"))
    stop = number(row.get("Initial Stop"))
    if entry is not None and stop is not None and stop >= entry:
        return True
    if report_text(row.get("Extension Status")) in {"Extended", "Overextended"}:
        return True
    return report_text(row.get("Setup Integrity")).upper() == "FAIL"


def manifest_record(row: dict[str, object]) -> dict[str, object]:
    risk = number(row.get("Maximum Risk R", row.get("maximum_risk_r")))
    risk_dollars = number(
        row.get("Maximum Risk Dollars", row.get("maximum_risk_dollars"))
    )
    shares = number(row.get("Maximum Shares", row.get("maximum_shares")))
    lane_members_raw = row.get("lane_members")
    lane_scores_raw = row.get("lane_scores")
    lane_ranks_raw = row.get("lane_ranks")
    lane_reasons_raw = row.get("lane_reasons")
    lane_missing_raw = row.get("lane_missing")
    lane_members = {
        lane: truth(
            lane_members_raw.get(lane, False)
            if isinstance(lane_members_raw, dict)
            else row.get(f"{lane} Member", False)
        )
        for lane in LANES
    }
    lane_scores = {
        lane: number(
            lane_scores_raw.get(lane)
            if isinstance(lane_scores_raw, dict)
            else row.get(f"{lane} Score")
        )
        for lane in LANES
    }
    lane_ranks = {
        lane: rank_number(
            lane_ranks_raw.get(lane)
            if isinstance(lane_ranks_raw, dict)
            else row.get(f"{lane} Rank")
        )
        for lane in LANES
    }
    lane_reasons = {
        lane: str(
            lane_reasons_raw.get(lane, "")
            if isinstance(lane_reasons_raw, dict)
            else row.get(f"{lane} Reason", "")
        )
        for lane in LANES
    }
    lane_missing = {
        lane: str(
            lane_missing_raw.get(lane, "")
            if isinstance(lane_missing_raw, dict)
            else row.get(f"{lane} Missing", "")
        )
        for lane in LANES
    }
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
        "report_section": str(row.get("Report Section", row.get("report_section", ""))),
        "pattern_discovery_status": str(
            row.get("Pattern Discovery Status", row.get("pattern_discovery_status", ""))
        ),
        "pattern_discovery_reason": str(
            row.get("Pattern Discovery Reason", row.get("pattern_discovery_reason", ""))
        ),
        "setup_lanes": str(row.get("Setup Lanes", row.get("setup_lanes", ""))),
        "lane_members": lane_members,
        "lane_scores": lane_scores,
        "lane_ranks": lane_ranks,
        "lane_reasons": lane_reasons,
        "lane_missing": lane_missing,
        "pullback_lane_quality": str(
            row.get("Pullback Lane Quality", row.get("pullback_lane_quality", ""))
        ),
        "breakout_lane_state": str(
            row.get("Breakout Lane State", row.get("breakout_lane_state", ""))
        ),
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
    normalized = [manifest_record(row) for row in rows]
    tickers = [str(row.get("ticker", "")) for row in normalized]
    if len(tickers) != len(set(tickers)):
        errors.append("duplicate tickers in decision manifest")
    for row in normalized:
        ticker = row["ticker"] or "<missing ticker>"
        state = row["decision"]
        risk = row["maximum_risk_r"]
        risk_dollars = row["maximum_risk_dollars"]
        shares = row["maximum_shares"]
        actionable = bool(row["actionable"])
        confirmed = bool(row["confirmed_setup"])
        report_section = str(row["report_section"])
        pattern_status = str(row["pattern_discovery_status"])
        pattern_reason = str(row["pattern_discovery_reason"]).strip()
        setup_lanes = {
            item.strip() for item in str(row["setup_lanes"]).split(";") if item.strip()
        }
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
        if report_section not in REPORT_SECTIONS:
            errors.append(f"{ticker}: unsupported or missing report section")
        if state in {"FULL", "HALF"}:
            if report_section != "Actionable Now":
                errors.append(
                    f"{ticker}: canonical actionable state must be in Actionable Now"
                )
            if pattern_status != "NOT_APPLICABLE":
                errors.append(
                    f"{ticker}: actionable state has invalid pattern discovery status"
                )
        else:
            if report_section == "Actionable Now":
                errors.append(
                    f"{ticker}: non-actionable state cannot be in Actionable Now"
                )
            if pattern_status != "RESEARCH_ONLY":
                errors.append(
                    f"{ticker}: non-actionable report section must be RESEARCH_ONLY"
                )
        if not pattern_reason:
            errors.append(f"{ticker}: pattern discovery reason missing")
        unknown_lanes = setup_lanes.difference(LANES)
        if unknown_lanes:
            errors.append(f"{ticker}: unsupported setup lane")
        for lane in LANES:
            member = bool(row["lane_members"][lane])
            score = row["lane_scores"][lane]
            rank = row["lane_ranks"][lane]
            reason = str(row["lane_reasons"][lane]).strip()
            if member != (lane in setup_lanes):
                errors.append(
                    f"{ticker}: setup lane summary contradicts {lane} membership"
                )
            if member and report_section != "Pattern Watchlist":
                errors.append(
                    f"{ticker}: lane membership is only valid in Pattern Watchlist"
                )
            if member and (score is None or rank is None or rank < 1 or not reason):
                errors.append(f"{ticker}: {lane} member lacks score/rank/reason")
            if not member and (score is not None or rank is not None):
                errors.append(f"{ticker}: non-member has {lane} score or rank")
            if report_section != "Pattern Watchlist" and reason:
                errors.append(f"{ticker}: non-pattern row has {lane} reason")
    for lane in LANES:
        ranks = sorted(
            int(row["lane_ranks"][lane])
            for row in normalized
            if row["lane_members"][lane] and row["lane_ranks"][lane] is not None
        )
        if ranks != list(range(1, len(ranks) + 1)):
            errors.append(f"{lane}: ranks must be unique and contiguous")
    return errors


def validate_csv_semantics(rows: list[dict[str, object]]) -> list[str]:
    errors = validate_manifest([manifest_record(row) for row in rows])
    for row in rows:
        ticker = str(row.get("Ticker", "<missing ticker>"))
        actionable = str(row.get("Final Decision", "")) in {"FULL", "HALF"}
        if not actionable:
            report_section = report_text(row.get("Report Section"))
            failure_evidence = has_pattern_failure_evidence(row)
            if failure_evidence and report_section != "Avoid / Failed":
                errors.append(
                    f"{ticker}: explicit failure evidence must be in Avoid / Failed"
                )
            if not failure_evidence and report_section != "Pattern Watchlist":
                errors.append(
                    f"{ticker}: non-actionable row without explicit failure evidence "
                    "must be in Pattern Watchlist"
                )
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
        "Pattern Watchlist",
        "Tight Base / VCP",
        "Pullback to Support",
        "Breakout Retest / High Flag",
        "Unassigned / Insufficient Lane Evidence",
        "Actionable Now",
        "Avoid / Failed",
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
