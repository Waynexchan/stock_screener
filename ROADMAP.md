# Project Roadmap

## Version 2.0

### Completed

✓ Stable Rule Engine

Priority: High

Status: Completed

Description:
Deterministic Stage 2 screening, trend filters, RS calculation, ATR context, candidate categories, and report export are operational.

Estimated Complexity:
High.

Estimated Benefit:
Provides a repeatable base workflow for daily review.

Dependencies:
Yahoo Finance historical price data, NASDAQ Trader symbol files.

Suggested Version:
2.0.

✓ Industry Ranking

Priority: High

Status: Completed

Description:
Industry ranking exists through Industry Strength Score, candidate breadth, and average RS, but metadata quality needs improvement.

Estimated Complexity:
Medium.

Estimated Benefit:
Helps focus review on leadership groups.

Dependencies:
Reliable sector and industry metadata.

Suggested Version:
2.0.

✓ ATR Extension

Priority: High

Status: Completed

Description:
Extension and support distance are measured in ATR units instead of fixed percentages.

Estimated Complexity:
Medium.

Estimated Benefit:
Improves risk/reward context across stocks with different volatility profiles.

Dependencies:
Clean OHLCV data.

Suggested Version:
2.0.

✓ AI Commentary

Priority: Medium

Status: Completed

Description:
AI commentary analyses only the Top Action List after deterministic screening.

Estimated Complexity:
Medium.

Estimated Benefit:
Improves review speed and daily briefing quality.

Dependencies:
OpenAI API key and accessible model.

Suggested Version:
2.0.

✓ Daily Email

Priority: Medium

Status: Completed

Description:
HTML watchlist and summary email are generated after valid runs.

Estimated Complexity:
Low.

Estimated Benefit:
Supports consistent after-close workflow.

Dependencies:
Gmail app password environment variables.

Suggested Version:
2.0.

✓ Data Validation

Priority: High

Status: Completed

Description:
Invalid Yahoo runs are rejected before reports are overwritten.

Estimated Complexity:
Medium.

Estimated Benefit:
Prevents empty reports from being mistaken for market conclusions.

Dependencies:
Universe count, SPY/QQQ validation, download success rate.

Suggested Version:
2.0.

✓ Universe Protection

Priority: High

Status: Completed

Description:
Universe refreshes are validated before replacement and last-known-good reports are preserved.

Estimated Complexity:
Medium.

Estimated Benefit:
Protects production workflow from partial provider failures.

Dependencies:
NASDAQ Trader listings and Yahoo historical data.

Suggested Version:
2.0.

## Version 2.1

### In Progress

⏳ Better Industry Rotation

Priority: High

Status: In Progress

Description:
Improve sector and industry metadata quality so the screener can distinguish real group leadership instead of collapsing candidates into Unknown. Unknown industries are now excluded from leadership ranking, but metadata coverage still needs improvement.

Estimated Complexity:
Medium.

Estimated Benefit:
Higher quality sector and industry selection.

Dependencies:
Reliable metadata cache or maintained industry map.

Suggested Version:
2.1.

⏳ Quality-First Review Priority

Priority: High

Status: In Progress

Description:
Prioritise stocks by individual Stage 2 quality, setup quality, volume confirmation, RS 75+ leadership, and risk/reward before using industry strength and market context. Industry context now gives extra credit when multiple stocks in the same known industry have active setups. Review scoring has been rebalanced to avoid easy 100-point saturation and penalise poor VCP, loose action, weak confirmation, and price-data warnings.

Estimated Complexity:
Medium.

Estimated Benefit:
Focuses review on stocks with volume, setup quality, and Stage 2 structure.

Dependencies:
Existing RS, volume ratio, pullback quality, extension status, VCP label, and industry rank.

Suggested Version:
2.1.

### Planned

☐ Better Market Regime Detection

Priority: High

Status: Planned

Description:
Add broader market context beyond SPY/QQQ moving average status.

Estimated Complexity:
Medium.

Estimated Benefit:
Improves trading aggressiveness and review framing.

Dependencies:
Market breadth and index trend data.

Suggested Version:
2.1.

☑ Cleaner HTML Reports

Priority: Medium

Status: Completed

Description:
Improve report layout for faster scanning and clearer priority sections. HTML reports now include an executive summary panel, review badges, row highlighting, and sticky table headers; Markdown reports include a `Review Flags` column.

Estimated Complexity:
Medium.

Estimated Benefit:
Reduces daily review time.

Dependencies:
Stable report columns and ranking logic.

Suggested Version:
2.1.

☑ Report Summary History

Priority: Medium

Status: Completed

Description:
Persist local summary snapshots after valid reports so the next report can compare setup-quality counts, new and removed Top Action tickers, and new and removed Top Industries. HTML reports now include a recent mini trend table/bar view for opportunity-quality context.

Estimated Complexity:
Low.

Estimated Benefit:
Helps identify changing leadership and rotation between daily reports without adding prediction logic.

Dependencies:
Valid Top Action List and Top Industries report output.

Suggested Version:
2.1.

☑ No-Network Report Preview

Priority: Medium

Status: Completed

Description:
Add `--report-preview` so HTML report layout can be rebuilt from last-known-good report data and local summary history without downloading market data, calling AI, sending email, overwriting production reports, or appending history.

Estimated Complexity:
Low.

Estimated Benefit:
Speeds report-layout development and reduces provider/API/email risk during UI improvements.

Dependencies:
Last-known-good CSV report and optional summary history.

Suggested Version:
2.1.

☑ Top Action Noise Gate

Priority: High

Status: Completed

Description:
Add `Review Tier` and `Noise Filter Reason` so the Top Action List only shows clean immediate or high-priority review candidates, while valid but noisy setups remain available in Daily Focus and category sections. Poor VCP, loose action, wait-only actions, weak pullback quality, thin confirmation volume, far support distance, and isolated industry context should explain why a stock is downgraded from first-pass review.

Estimated Complexity:
Medium.

Estimated Benefit:
Reduces daily chart-review noise and keeps the first list focused on stocks most likely to deserve manual inspection.

Dependencies:
Review Priority Score, RS Trend, support distance, extension status, VCP/tightness labels, volume ratio, risk/reward quality, and industry setup count.

Suggested Version:
2.1.

☑ Daily Review Plan

Priority: High

Status: Completed

Description:
Add a short report section that converts Top Action and Daily Focus tiers into a practical daily review sequence: open `Review Now` first, review `High Priority Watch` second, treat Daily Focus as tracking only, and avoid forcing trades when no clean first-review setups exist.

Estimated Complexity:
Low.

Estimated Benefit:
Reduces decision fatigue and makes the generated list easier to use as a daily operating tool.

Dependencies:
Review Tier, Top Action List, Daily Focus List, and Market Status.

Suggested Version:
2.1.

☐ Better Candidate Deduplication

Priority: Medium

Status: Planned

Description:
Refine how stocks appearing in multiple categories are assigned to the most useful review bucket.

Estimated Complexity:
Low.

Estimated Benefit:
Cleaner reports and less duplicate chart review.

Dependencies:
Category priority rules.

Suggested Version:
2.1.

## Version 2.2

### Planned

☐ VCP Detection

Priority: High

Status: Planned

Description:
Improve volatility contraction pattern detection using range contraction, volume dry-up, and pivot context.

Estimated Complexity:
Medium.

Estimated Benefit:
Better identification of high-quality bases.

Dependencies:
Historical OHLCV data and current VCP labels.

Suggested Version:
2.2.

☐ Relative Volume Ranking

Priority: Medium

Status: Planned

Description:
Rank candidates by meaningful volume expansion and dry-up context.

Estimated Complexity:
Medium.

Estimated Benefit:
Improves detection of institutional demand.

Dependencies:
Volume history and category context.

Suggested Version:
2.2.

??Relative Strength Trend

Priority: High

Status: Completed

Description:
Track whether RS is improving, stable, or deteriorating instead of using only point-in-time RS score. Current implementation compares today's weighted RS percentile with the same calculation roughly 21 trading days earlier.

Estimated Complexity:
Medium.

Estimated Benefit:
Helps distinguish emerging leaders from fading names.

Dependencies:
Historical RS snapshots or repeatable RS time series.

Suggested Version:
2.1.

☐ Earnings Calendar Filter

Priority: Medium

Status: Planned

Description:
Warn when candidates are near earnings dates.

Estimated Complexity:
Medium.

Estimated Benefit:
Improves risk management.

Dependencies:
Reliable earnings calendar data source.

Suggested Version:
2.2.

☐ Gap Detection

Priority: Medium

Status: Planned

Description:
Identify earnings gaps, breakaway gaps, and exhaustion-style gaps.

Estimated Complexity:
Medium.

Estimated Benefit:
Adds useful context for breakout and pullback review.

Dependencies:
Daily OHLCV history.

Suggested Version:
2.2.

## Version 2.3

### Planned

☐ Trade Journal

Priority: Medium

Status: Planned

Description:
Record reviewed setups, taken trades, notes, and outcomes.

Estimated Complexity:
High.

Estimated Benefit:
Improves feedback loop and discipline.

Dependencies:
Persistent local storage.

Suggested Version:
2.3.

☐ Portfolio Dashboard

Priority: Medium

Status: Planned

Description:
Track current positions, exposure, and watchlist-to-trade flow.

Estimated Complexity:
High.

Estimated Benefit:
Improves portfolio-level decision quality.

Dependencies:
Portfolio input and trade journal.

Suggested Version:
2.3.

☐ Win Rate Tracking

Priority: Medium

Status: Planned

Description:
Track trade outcomes by setup type and market regime.

Estimated Complexity:
Medium.

Estimated Benefit:
Improves expectancy analysis.

Dependencies:
Trade journal.

Suggested Version:
2.3.

☐ Performance Analytics

Priority: Medium

Status: Planned

Description:
Measure expectancy, drawdown, average gain/loss, and setup quality over time.

Estimated Complexity:
High.

Estimated Benefit:
Supports objective process improvement.

Dependencies:
Trade history.

Suggested Version:
2.3.

## Version 3.0

### Planned

☐ Position Sizing

Priority: High

Status: Planned

Description:
Calculate position size using risk per trade, stop distance, and portfolio constraints.

Estimated Complexity:
High.

Estimated Benefit:
Improves risk control.

Dependencies:
Portfolio dashboard and trade journal.

Suggested Version:
3.0.

☐ Portfolio Heat

Priority: High

Status: Planned

Description:
Measure aggregate risk across positions and correlated groups.

Estimated Complexity:
High.

Estimated Benefit:
Reduces portfolio concentration and emotional risk.

Dependencies:
Position sizing and portfolio dashboard.

Suggested Version:
3.0.

☐ AI Trade Review

Priority: Medium

Status: Planned

Description:
Use AI to summarise completed trades and identify process mistakes without changing rule-engine decisions.

Estimated Complexity:
Medium.

Estimated Benefit:
Improves decision review and discipline.

Dependencies:
Trade journal.

Suggested Version:
3.0.

☐ AI Weekly Market Review

Priority: Medium

Status: Planned

Description:
Summarise weekly market character, leadership changes, and review priorities.

Estimated Complexity:
Medium.

Estimated Benefit:
Improves planning.

Dependencies:
Daily report history.

Suggested Version:
3.0.

☐ AI Monthly Performance Review

Priority: Medium

Status: Planned

Description:
Summarise monthly process quality, recurring mistakes, and improvement opportunities.

Estimated Complexity:
Medium.

Estimated Benefit:
Improves long-term expectancy.

Dependencies:
Trade journal and performance analytics.

Suggested Version:
3.0.
