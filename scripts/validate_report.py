"""Validate report structure, row semantics, and cross-output decisions."""

from __future__ import annotations

import csv
import hashlib
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
CHART_QUALITY_COMPONENTS = (
    "Prior Advance Quality",
    "Trend Smoothness",
    "Distribution / Wide-Bar Penalty",
    "Overhead Supply",
    "Contraction Quality",
    "Support Respect",
    "Relative Strength Persistence",
)
CHART_QUALITY_STATUSES = {
    "AVAILABLE",
    "INSUFFICIENT_HISTORY",
    "MISSING_DATA",
    "NOT_APPLICABLE",
}
CHART_QUALITY_STATES = {
    "Prior Advance Quality": {"STRONG", "CONSTRUCTIVE", "MIXED", "WEAK"},
    "Trend Smoothness": {
        "SMOOTH_UPTREND",
        "ORDERLY_UPTREND",
        "FLAT_OR_DIRECTIONLESS",
        "ERRATIC",
        "WEAK_DOWNTREND",
    },
    "Distribution / Wide-Bar Penalty": {"NONE", "LIGHT", "MODERATE", "HEAVY"},
    "Overhead Supply": {"LOW", "MODERATE", "HEAVY", "NO_OBSERVED_OVERHEAD"},
    "Contraction Quality": {
        "STRONG_MULTI_DIMENSIONAL",
        "PRICE_CONTRACTION_ONLY",
        "VOLUME_DRY_UP_ONLY",
        "WEAK_OR_NONE",
        "EXPANDING",
        "PRICE_CONTRACTION_VOLUME_UNKNOWN",
    },
    "Support Respect": {"STRONG", "CONSTRUCTIVE", "AMBIGUOUS_PROXIMITY", "BROKEN"},
    "Relative Strength Persistence": {
        "PERSISTENTLY_STRONG",
        "IMPROVING",
        "STRONG_BUT_DETERIORATING",
        "INCONSISTENT",
        "WEAK",
    },
}


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


def numeric_state(value: object) -> tuple[str, float | None]:
    """Return MISSING, VALID_FINITE, or INVALID_PRESENT for report numerics."""
    if value is None:
        return "MISSING", None
    if isinstance(value, float) and math.isnan(value):
        return "MISSING", None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return "MISSING", None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return "INVALID_PRESENT", None
    if not math.isfinite(parsed):
        return "INVALID_PRESENT", None
    return "VALID_FINITE", parsed


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


def component_text(value: object) -> str:
    """Normalize missing values while preserving the valid state string NONE."""
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    parsed = str(value).strip()
    return "" if parsed.lower() == "nan" else parsed


def has_pattern_failure_evidence(row: dict[str, object]) -> bool:
    freshness = report_text(row.get("Price Freshness Status")).upper()
    if freshness != "CURRENT":
        return True
    if report_text(row.get("Price Data Warning")):
        return True
    plan_states = {
        field: numeric_state(row.get(field))[0]
        for field in (
            "Planned Entry",
            "Initial Stop",
            "Realistic Target",
            "Reward/Risk Ratio",
        )
    }
    if "INVALID_PRESENT" in plan_states.values():
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
    chart_quality_raw = row.get("chart_quality")
    chart_quality: dict[str, dict[str, object]] = {}
    for component in CHART_QUALITY_COMPONENTS:
        raw = (
            chart_quality_raw.get(component, {})
            if isinstance(chart_quality_raw, dict)
            else {}
        )
        chart_quality[component] = {
            "status": component_text(
                raw.get("status")
                if isinstance(raw, dict)
                else row.get(f"CQ {component} Status")
            )
            if isinstance(chart_quality_raw, dict)
            else component_text(row.get(f"CQ {component} Status")),
            "state": component_text(
                raw.get("state")
                if isinstance(raw, dict)
                else row.get(f"CQ {component} State")
            )
            if isinstance(chart_quality_raw, dict)
            else component_text(row.get(f"CQ {component} State")),
            "value": number(
                raw.get("value")
                if isinstance(raw, dict)
                else row.get(f"CQ {component} Value")
            )
            if isinstance(chart_quality_raw, dict)
            else number(row.get(f"CQ {component} Value")),
            "evidence": component_text(
                raw.get("evidence")
                if isinstance(raw, dict)
                else row.get(f"CQ {component} Evidence")
            )
            if isinstance(chart_quality_raw, dict)
            else component_text(row.get(f"CQ {component} Evidence")),
            "warnings": component_text(
                raw.get("warnings")
                if isinstance(raw, dict)
                else row.get(f"CQ {component} Warnings")
            )
            if isinstance(chart_quality_raw, dict)
            else component_text(row.get(f"CQ {component} Warnings")),
            "reason": component_text(
                raw.get("reason")
                if isinstance(raw, dict)
                else row.get(f"CQ {component} Reason")
            )
            if isinstance(chart_quality_raw, dict)
            else component_text(row.get(f"CQ {component} Reason")),
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
        "chart_quality_summary": report_text(
            row.get("Chart Quality Summary", row.get("chart_quality_summary", ""))
        ),
        "chart_quality": chart_quality,
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


def read_markdown_manifest(
    text: str,
) -> tuple[list[dict[str, object]], str]:
    match = re.search(
        r"<!-- decision-manifest\s*(\{.*?\})\s*-->",
        text,
        flags=re.DOTALL,
    )
    if not match:
        raise ValueError("Markdown decision manifest missing")
    if text[match.end() :].strip():
        raise ValueError("Markdown decision manifest must be terminal content")
    payload = json.loads(match.group(1))
    body_hash = payload.get("body_sha256")
    records = payload.get("records")
    if not isinstance(body_hash, str) or not body_hash:
        raise ValueError("Markdown body hash missing")
    if not isinstance(records, list):
        raise ValueError("Markdown decision records missing")
    actual_hash = hashlib.sha256(text[: match.start()].encode("utf-8")).hexdigest()
    if actual_hash != body_hash:
        raise ValueError("Markdown body hash mismatch")
    body_records = read_markdown_body_records(text[: match.start()])
    normalized_records = [manifest_record(row) for row in records]
    if body_records != normalized_records:
        raise ValueError("Markdown visible decisions differ from manifest")
    return records, body_hash


def _markdown_table_rows(section: str) -> list[dict[str, str]]:
    lines = section.splitlines()
    rows: list[dict[str, str]] = []
    index = 0
    while index + 1 < len(lines):
        header_line = lines[index].strip()
        separator_line = lines[index + 1].strip()
        if not header_line.startswith("|") or not separator_line.startswith("|"):
            index += 1
            continue
        headers = [cell.strip() for cell in header_line.strip("|").split("|")]
        separators = [cell.strip() for cell in separator_line.strip("|").split("|")]
        if len(headers) != len(separators) or not all(
            re.fullmatch(r":?-{3,}:?", cell) for cell in separators
        ):
            index += 1
            continue
        index += 2
        while index < len(lines) and lines[index].strip().startswith("|"):
            values = [
                cell.strip() for cell in lines[index].strip().strip("|").split("|")
            ]
            if len(values) != len(headers):
                raise ValueError("Markdown table row has an unexpected column count")
            rows.append(dict(zip(headers, values, strict=True)))
            index += 1
    return rows


def read_markdown_body_records(body: str) -> list[dict[str, object]]:
    """Reconstruct canonical records from the visible Phase 1 section tables."""
    section_names = ("Actionable Now", "Pattern Watchlist", "Avoid / Failed")
    visible_to_source = {
        "Pattern Status": "Pattern Discovery Status",
        "Pattern / Waiting Reason": "Pattern Discovery Reason",
        "Chart Quality (RESEARCH_ONLY)": "Chart Quality Summary",
    }
    by_ticker: dict[str, dict[str, object]] = {}
    for offset, section_name in enumerate(section_names):
        start_marker = f"## {section_name}"
        try:
            start = body.index(start_marker) + len(start_marker)
        except ValueError as exc:
            raise ValueError(f"Markdown section missing: {section_name}") from exc
        next_markers = [
            body.find(f"## {later}", start) for later in section_names[offset + 1 :]
        ]
        next_markers.append(body.find("## AI Commentary", start))
        ends = [position for position in next_markers if position >= 0]
        end = min(ends) if ends else len(body)
        for visible_row in _markdown_table_rows(body[start:end]):
            if "Ticker" not in visible_row:
                continue
            source_row = {
                visible_to_source.get(key, key): value
                for key, value in visible_row.items()
            }
            normalized = manifest_record(source_row)
            if normalized["report_section"] != section_name:
                raise ValueError(
                    "Markdown visible section conflicts with row classification: "
                    f"{normalized['ticker']}"
                )
            ticker = str(normalized["ticker"])
            if ticker in by_ticker:
                raise ValueError(f"Markdown duplicate visible ticker: {ticker}")
            by_ticker[ticker] = normalized

    # Phase 1 tables deliberately keep chart quality concise.  The component
    # evidence remains visible in the later category tables, so reconstruct it
    # from those rows before comparing the visible Markdown with its manifest.
    component_status_columns = {
        f"CQ {component} Status" for component in CHART_QUALITY_COMPONENTS
    }
    for visible_row in _markdown_table_rows(body):
        if "Ticker" not in visible_row or not component_status_columns.intersection(
            visible_row
        ):
            continue
        ticker = str(visible_row["Ticker"])
        if ticker not in by_ticker:
            continue
        source_row = {
            visible_to_source.get(key, key): value for key, value in visible_row.items()
        }
        detailed = manifest_record(source_row)
        by_ticker[ticker]["chart_quality_summary"] = detailed["chart_quality_summary"]
        by_ticker[ticker]["chart_quality"] = detailed["chart_quality"]
    return [by_ticker[ticker] for ticker in sorted(by_ticker)]


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
        chart_quality_summary = str(row["chart_quality_summary"])
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
        has_chart_quality = bool(chart_quality_summary) or any(
            component["value"] is not None
            or any(
                str(component[key]).strip()
                for key in ("status", "state", "evidence", "warnings", "reason")
            )
            for component in row["chart_quality"].values()
        )
        if has_chart_quality:
            expected_summary = "; ".join(
                ["RESEARCH_ONLY"]
                + [
                    f"{component_name}: {component['state']}"
                    for component_name, component in row["chart_quality"].items()
                ]
            )
            if chart_quality_summary != expected_summary:
                errors.append(f"{ticker}: chart quality summary contradicts components")
            for component_name, component in row["chart_quality"].items():
                status = str(component["status"])
                state = str(component["state"])
                reason = str(component["reason"])
                value = component["value"]
                evidence = str(component["evidence"])
                warnings = str(component["warnings"])
                if not status or not state or not reason or not evidence:
                    errors.append(
                        f"{ticker}: incomplete chart quality component {component_name}"
                    )
                    continue
                allowed_statuses = CHART_QUALITY_STATUSES.copy()
                if component_name != "Support Respect":
                    allowed_statuses.remove("NOT_APPLICABLE")
                if status not in allowed_statuses:
                    errors.append(
                        f"{ticker}: unsupported chart quality status: {component_name}"
                    )
                available_states = CHART_QUALITY_STATES[component_name]
                valid_states = available_states.union(
                    {"INSUFFICIENT_HISTORY", "MISSING_DATA"}
                )
                if component_name == "Support Respect":
                    valid_states.add("NOT_APPLICABLE")
                if state not in valid_states:
                    errors.append(
                        f"{ticker}: unsupported chart quality state: {component_name}"
                    )
                if status == "AVAILABLE" and state not in available_states:
                    errors.append(
                        f"{ticker}: chart quality status/state contradiction: {component_name}"
                    )
                if (
                    status in {"INSUFFICIENT_HISTORY", "NOT_APPLICABLE"}
                    and state != status
                ):
                    errors.append(
                        f"{ticker}: chart quality status/state contradiction: {component_name}"
                    )
                if status == "MISSING_DATA" and not (
                    state == "MISSING_DATA"
                    or (
                        component_name == "Contraction Quality"
                        and state
                        in {
                            "PRICE_CONTRACTION_VOLUME_UNKNOWN",
                            "EXPANDING",
                            "WEAK_OR_NONE",
                        }
                    )
                ):
                    errors.append(
                        f"{ticker}: chart quality status/state contradiction: {component_name}"
                    )
                if status == "AVAILABLE" and value is None:
                    errors.append(
                        f"{ticker}: available chart quality component lacks value: {component_name}"
                    )
                if status != "AVAILABLE" and value is not None:
                    errors.append(
                        f"{ticker}: unavailable chart quality component has value: {component_name}"
                    )
                if value is not None and not 0.0 <= value <= 100.0:
                    errors.append(
                        f"{ticker}: chart quality value outside 0-100: {component_name}"
                    )
                if (
                    component_name == "Distribution / Wide-Bar Penalty"
                    and status == "AVAILABLE"
                    and "Penalty direction: higher is worse." not in warnings
                ):
                    errors.append(
                        f"{ticker}: distribution penalty direction warning missing"
                    )
                try:
                    parsed_evidence = json.loads(evidence)
                except (TypeError, ValueError):
                    parsed_evidence = None
                if not isinstance(parsed_evidence, dict):
                    errors.append(
                        f"{ticker}: invalid chart quality evidence: {component_name}"
                    )
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
        target = number(row.get("Realistic Target"))
        rr = number(row.get("Reward/Risk Ratio"))
        if recent is None:
            errors.append(f"{ticker}: Missing Recent RS is actionable")
        if row.get("Realistic Target Source") == "model 2R feasibility target":
            errors.append(f"{ticker}: synthetic model 2R target is actionable")
        if row.get("Price Freshness Status") != "CURRENT":
            errors.append(f"{ticker}: stale price data is actionable")
        if entry is None or stop is None or stop >= entry:
            errors.append(f"{ticker}: invalid stop is actionable")
        if target is None or entry is None or target <= entry:
            errors.append(f"{ticker}: invalid target is actionable")
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
    markdown_path = Path(args[3]) if len(args) > 3 else html_path.with_suffix(".md")
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

    if markdown_path.exists():
        try:
            markdown_manifest, _ = read_markdown_manifest(
                markdown_path.read_text(encoding="utf-8")
            )
            normalized_markdown = [manifest_record(row) for row in markdown_manifest]
            errors.extend(validate_manifest(normalized_markdown))
            if normalized_markdown != html_manifest:
                errors.append("Markdown and HTML decisions differ")
        except (ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
    else:
        errors.append(f"missing Markdown: {markdown_path}")

    if errors:
        print("Report semantic validation FAIL: " + "; ".join(dict.fromkeys(errors)))
        return 1
    print(f"Report semantic validation PASS: {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
