"""Offline FULL/HALF/WATCH/NO TRADE decision and drawdown scenario dry run."""

from __future__ import annotations

from html import escape
import json
from pathlib import Path

import pandas as pd

from decision_system import (
    PortfolioRisk,
    calculate_drawdown_state,
    size_trade_candidate,
)

OUTPUT = Path("daily_watchlist_dry_run.html")
OUTPUT_CSV = Path("daily_watchlist_dry_run.csv")
OUTPUT_EMAIL = Path("daily_watchlist_dry_run_email.txt")


def _candidate(ticker: str, **updates: object) -> dict[str, object]:
    row: dict[str, object] = {
        "Ticker": ticker,
        "Category": "Pullback Candidates",
        "Recent RS Score": 88.0,
        "RS Trend": "Improving",
        "Industry": "Software",
        "Theme": "Industry: Software",
        "Industry Qualified": True,
        "Sister Confirmation": True,
        "Planned Entry": 100.0,
        "Initial Stop": 95.0,
        "Realistic Target": 110.0,
        "Realistic Target Source": "prior high resistance",
        "Extension Status": "Not Extended",
        "Entry Timing": "OPTIMAL",
        "Volume Ratio": 1.0,
        "Tightness Label": "Normal",
        "VCP Label": "Good VCP",
        "Pullback Quality": "B - Healthy Pullback",
        "Trade Plan Confidence": "High",
        "Price Freshness Status": "CURRENT",
        "Price Data Warning": "",
    }
    row.update(updates)
    return row


def build_sample_report(output: Path = OUTPUT) -> tuple[pd.DataFrame, str]:
    normal = calculate_drawdown_state(100_000, 100_000)
    reduced = calculate_drawdown_state(100_000 - 2 * 587, 100_000)
    defensive = calculate_drawdown_state(100_000 - 4 * 587, 100_000)
    stopped = calculate_drawdown_state(100_000 - 6 * 587, 100_000)
    open_portfolio = PortfolioRisk((), 0.0, 3.0, 3.0, {}, {}, {}, ())
    exhausted = PortfolioRisk((), 3.0, 3.0, 0.0, {}, {}, {}, ())
    industry_blocked = PortfolioRisk(
        (), 1.75, 3.0, 1.25, {"Software": 1.75}, {}, {}, ()
    )
    theme_blocked = PortfolioRisk(
        (), 1.75, 3.0, 1.25, {}, {}, {"Industry: Software": 1.75}, ()
    )
    scenarios = [
        ("FULL_SAMPLE", _candidate("FULL_SAMPLE"), normal, open_portfolio, 0),
        (
            "HALF_SAMPLE",
            _candidate("HALF_SAMPLE", Sister_Confirmation=False),
            normal,
            open_portfolio,
            0,
        ),
        (
            "EARLY_LEADER_HALF",
            _candidate(
                "EARLY_LEADER_HALF",
                **{"Industry Qualified": False, "Sister Confirmation": False},
            ),
            normal,
            open_portfolio,
            0,
        ),
        (
            "LOOSE_DEVELOPING_WATCH",
            _candidate(
                "LOOSE_DEVELOPING_WATCH",
                **{
                    "Category": "Developing Base Candidates",
                    "Tightness Label": "Loose",
                    "Industry Qualified": False,
                    "Sister Confirmation": False,
                },
            ),
            normal,
            open_portfolio,
            0,
        ),
        (
            "NO_TRADE_SAMPLE",
            _candidate("NO_TRADE_SAMPLE", Initial_Stop=101.0),
            normal,
            open_portfolio,
            0,
        ),
        (
            "MAX_POSITION_BLOCK",
            _candidate("MAX_POSITION_BLOCK"),
            normal,
            open_portfolio,
            4,
        ),
        ("HEAT_BLOCK", _candidate("HEAT_BLOCK"), normal, exhausted, 0),
        (
            "INDUSTRY_HEAT_BLOCK",
            _candidate("INDUSTRY_HEAT_BLOCK"),
            normal,
            industry_blocked,
            0,
        ),
        (
            "THEME_HEAT_BLOCK",
            _candidate("THEME_HEAT_BLOCK"),
            normal,
            theme_blocked,
            0,
        ),
        (
            "STALE_DATA_BLOCK",
            _candidate("STALE_DATA_BLOCK", **{"Price Freshness Status": "STALE"}),
            normal,
            open_portfolio,
            0,
        ),
        (
            "REDUCED_MODE",
            _candidate("REDUCED_MODE"),
            reduced,
            PortfolioRisk((), 0, 1.5, 1.5, {}, {}, {}, ()),
            0,
        ),
        (
            "DEFENSIVE_MODE",
            _candidate("DEFENSIVE_MODE"),
            defensive,
            PortfolioRisk((), 0, 0.5, 0.5, {}, {}, {}, ()),
            0,
        ),
        ("STOP_NEW_RISK", _candidate("STOP_NEW_RISK"), stopped, exhausted, 0),
    ]
    records = []
    for label, row, drawdown, portfolio, count in scenarios:
        # Convert readable fixture override names back to production field names.
        row["Sister Confirmation"] = row.pop(
            "Sister_Confirmation", row["Sister Confirmation"]
        )
        row["Initial Stop"] = row.pop("Initial_Stop", row["Initial Stop"])
        result = size_trade_candidate(row, "Strong", drawdown, portfolio, count)
        review_tier = (
            "Review Now"
            if result.actionable
            else "Watch Later"
            if result.state == "WATCH"
            else "Skip Today"
        )
        records.append(
            {
                "Scenario": label,
                "Ticker": row["Ticker"],
                "Final Decision": result.state,
                "Actionable": result.actionable,
                "Confirmed Setup": result.actionable,
                "Setup Integrity": result.setup_integrity,
                "Review Tier": review_tier,
                "Action": "Actionable now" if result.actionable else review_tier,
                "Maximum Risk R": result.maximum_risk_r,
                "Maximum Risk Dollars": result.maximum_risk_dollars,
                "Maximum Shares": result.maximum_shares,
                "Drawdown Mode": drawdown.mode,
                "Current Drawdown R": drawdown.drawdown_r,
                "Reasons": "; ".join(result.reasons),
                "Missing Confirmation": "; ".join(result.missing_confirmations),
                "Recent RS Score": row["Recent RS Score"],
                "Planned Entry": row["Planned Entry"],
                "Initial Stop": row["Initial Stop"],
                "Realistic Target": row["Realistic Target"],
                "Realistic Target Source": row["Realistic Target Source"],
                "Reward/Risk Ratio": 2.0,
                "Extension Status": row["Extension Status"],
                "Price Freshness Status": row["Price Freshness Status"],
            }
        )
    frame = pd.DataFrame(records)
    full = frame[frame["Final Decision"] == "FULL"]
    half = frame[frame["Final Decision"] == "HALF"]
    watch = frame[frame["Final Decision"] == "WATCH"]
    no_trade = frame[frame["Final Decision"] == "NO TRADE"]
    manifest = [
        {
            "ticker": row["Ticker"],
            "decision": row["Final Decision"],
            "maximum_risk_r": row["Maximum Risk R"],
            "maximum_risk_dollars": row["Maximum Risk Dollars"],
            "maximum_shares": row["Maximum Shares"],
            "actionable": row["Actionable"],
            "confirmed_setup": row["Confirmed Setup"],
            "setup_integrity": row["Setup Integrity"],
            "review_tier": row["Review Tier"],
            "action": row["Action"],
        }
        for row in frame.sort_values("Ticker").to_dict("records")
    ]
    html = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Dry Run</title></head><body>"
        "<h2>Executive Summary</h2><p>Four-state decision and sizing regression.</p>"
        "<h2>Market Status</h2><p>Strong deterministic fixture.</p>"
        "<h2>Portfolio Risk</h2><p>Market, drawdown, heat, and position-count caps applied.</p>"
        "<h2>Top Industries</h2><p>Fixture industry support.</p>"
        "<h2>FULL</h2>"
        + full.to_html(index=False)
        + "<h2>HALF</h2>"
        + half.to_html(index=False)
        + "<h2>WATCH</h2>"
        + watch.to_html(index=False)
        + "<h2>NO TRADE</h2>"
        + no_trade.to_html(index=False)
        + "<h2>Data and Logic Warnings</h2><p>Thresholds are configurable and not claimed optimal.</p>"
        "<h2>Expectancy</h2><p>Insufficient sample</p>"
        + '<script type="application/json" id="decision-manifest">'
        + json.dumps(manifest, sort_keys=True, separators=(",", ":"))
        + "</script></body></html>"
    )
    output.write_text(html, encoding="utf-8")
    csv_output = output.with_suffix(".csv")
    email_output = output.with_name(output.stem + "_email.txt")
    frame.to_csv(csv_output, index=False)
    email_lines = (
        ["Decision Manifest"]
        + [
            json.dumps(record, sort_keys=True, separators=(",", ":"))
            for record in manifest
        ]
        + ["End Decision Manifest"]
    )
    email_output.write_text("\n".join(email_lines), encoding="utf-8")
    return frame, html


def validate_sample_report(frame: pd.DataFrame, html: str) -> list[str]:
    errors = [
        f"missing section: {section}"
        for section in (
            "Executive Summary",
            "Market Status",
            "Portfolio Risk",
            "FULL",
            "HALF",
            "WATCH",
            "NO TRADE",
            "Data and Logic Warnings",
            "Expectancy",
        )
        if section not in html
    ]
    if set(frame["Final Decision"]) != {"FULL", "HALF", "WATCH", "NO TRADE"}:
        errors.append("dry run does not demonstrate exactly four trade states")
    expected = {
        "FULL_SAMPLE": "FULL",
        "HALF_SAMPLE": "HALF",
        "EARLY_LEADER_HALF": "HALF",
        "LOOSE_DEVELOPING_WATCH": "WATCH",
        "NO_TRADE_SAMPLE": "NO TRADE",
        "MAX_POSITION_BLOCK": "NO TRADE",
        "HEAT_BLOCK": "NO TRADE",
        "INDUSTRY_HEAT_BLOCK": "NO TRADE",
        "THEME_HEAT_BLOCK": "NO TRADE",
        "STALE_DATA_BLOCK": "NO TRADE",
        "REDUCED_MODE": "HALF",
        "DEFENSIVE_MODE": "HALF",
        "STOP_NEW_RISK": "NO TRADE",
    }
    actual = frame.set_index("Scenario")["Final Decision"].to_dict()
    if actual != expected:
        errors.append(f"scenario decisions differ: {actual}")
    return errors


def main() -> int:
    frame, html = build_sample_report()
    errors = validate_sample_report(frame, html)
    print("Sample Daily Watchlist Dry Run")
    print(frame.to_string(index=False))
    print(f"HTML: {escape(str(OUTPUT))}")
    print(
        "Validation: PASS" if not errors else "Validation: FAIL - " + "; ".join(errors)
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
