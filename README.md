# Professional Stage 2 Swing Trading Screener

> A deterministic US stock screening and daily review assistant for Stage 2 swing traders.

## Verified daily commands

```powershell
.\scripts\verify_project.ps1
.\scripts\run_daily_dry_run.ps1
.\scripts\run_daily_production.ps1
```

The production wrapper verifies first. On failure it returns non-zero, preserves
the log, and does not generate or email a normal watchlist. The dry run is offline
and never sends email. Maintain open positions in `data/open_positions.csv` and
completed trades in `data/completed_trades.csv`; see `docs/USER_GUIDE.md`,
`docs/RISK_MODEL.md`, and `docs/WATCHLIST_LOGIC.md`.

Maintain current account equity and its latest high-water mark in
`data/account_equity.csv`. The decision engine uses only `FULL` (1R / $587),
`HALF` (0.5R / $293.50), and `NO TRADE`. It caps active positions at four by
default and combines market heat, drawdown heat, concentration, and portfolio
heat before calculating maximum shares.

This repository is designed for a discretionary trader who wants a focused daily watchlist after market close. The rule engine finds and ranks stocks; optional AI commentary only summarises and prioritises the final Top Action List.

This project is not financial advice, does not predict prices, and does not generate automatic buy or sell signals.

## GitHub Quick Start

```bash
git clone <your-repo-url>
cd stock_screener
pip install -r requirements.txt
copy .env.example .env
python run_screener.py --self-test
python run_screener.py
```

For safe local checks without running the full screener:

```bash
python run_screener.py --report-preview
python run_screener.py --data-test
python run_screener.py --ai-test
python test_openai.py
```

## What This Project Does

- Builds a liquid US common-stock universe.
- Filters for Stage 2 trend structure.
- Scores Relative Strength using a MarketSmith-style percentile approximation.
- Tracks RS Trend to detect emerging leadership.
- Ranks industries from the full eligible liquid universe using separate recent Momentum and structural Leadership scores.
- Separates clean first-review setups from noisy watchlist names.
- Generates HTML, Markdown, CSV, and email reports.
- Adds optional AI commentary without allowing AI to select stocks.

## What This Project Does Not Do

- It does not predict tomorrow's price.
- It does not make trading decisions.
- It does not analyse the full universe with AI.
- It does not replace chart review, risk management, or trader discretion.
- It does not commit generated watchlists, caches, secrets, or private local data.

## GitHub Safety Notice

Only commit source code, documentation, requirements, and fake examples. Do not commit generated reports, universe caches, API keys, Gmail credentials, logs, private tracker files, CVs, cover letters, PDFs, or personal data.

## How To Use The Daily Report

Use the report in this order:

1. Read `Executive Summary` to judge whether the day has enough clean setups.
2. Read `Daily Review Plan` for the exact review sequence.
3. Review `FULL` candidates first, then `HALF` candidates.
4. Use `NO TRADE` rows only to understand what confirmation or repair is missing.
5. Treat the diagnostic appendix as audit detail, not as a trading list.
6. Never exceed the report's maximum shares or risk budget.
7. Use AI commentary as a briefing aid only.

If the Top Action List is empty, the correct workflow is usually to avoid forcing trades and wait for cleaner setups.

## Project Overview

This project is a professional Stage 2 swing trading screener for reducing the US stock universe into a focused daily watchlist. It uses deterministic, rule-based screening to identify high-probability opportunities and optional AI commentary to summarise the final Top Action List.

The screener does not generate buy signals, does not predict the market, and does not let AI select stocks. The trader remains responsible for the final decision.

## Main Features

- Builds a liquid US common-stock universe from NASDAQ Trader listings.
- Filters for Stage 2 trend structure using price, moving averages, volume, Relative Strength, ADR, and extension controls.
- Calculates Relative Strength from weighted 3-month, 6-month, and 12-month performance.
- Tracks RS Trend to identify emerging, improving, stable, weakening, and fading leadership.
- Rejects obvious price-data anomalies before candidate generation.
- Measures extension and pullback quality using ATR-based volatility context.
- Separates candidates into breakout, pullback, tight consolidation, extended, and volume surge sections.
- Ranks top industries by candidate breadth and average Relative Strength.
- Produces a compact Top Action List for the daily review.
- Applies a configurable Top Action noise gate so the first list contains only immediate or high-priority review candidates.
- Shows an HTML executive summary panel with setup-quality and warning counts.
- Tracks local summary history so reports can compare daily stock, industry, and setup-quality trend changes.
- Adds a Daily Review Plan so the report explains what to open first and what to track only.
- Highlights review flags in HTML and Markdown reports for faster scanning.
- Exports CSV, Markdown, HTML, and email summary reports.
- Optionally adds AI commentary for summarising and prioritising the Top Action List only.

## Installation

Use Python 3.10 or newer.

```bash
pip install -r requirements.txt
```

## Required Packages

The project dependencies are listed in `requirements.txt`:

- `yfinance`
- `pandas`
- `numpy`
- `tabulate`
- `python-dotenv`
- `openai`

If `python-dotenv` is not installed, the project prints:

```text
python-dotenv not installed.
Run: pip install python-dotenv
```

Existing Windows environment variables continue to work without `.env`.

## How To Run

```bash
python run_screener.py
```

Lightweight diagnostics and universe maintenance:

```bash
python run_screener.py --data-test
python run_screener.py --refresh-universe
python run_screener.py --ai-test
python run_screener.py --self-test
python run_screener.py --report-preview
python run_screener.py --industry-test
python run_screener.py --report-test
python test_openai.py
```

`--data-test` checks Nasdaq Trader source access, SPY, QQQ, 20 representative tickers, and validation logic with AI and email disabled. `--refresh-universe` rebuilds and validates `universe.csv` without running screening, AI, report export, or email.

`python test_openai.py` tests only the OpenAI Responses API connection using `config.AI_MODEL`. It does not download Yahoo Finance data, run the screener, generate reports, or send email.

`--ai-test` tests the real AI analysis workflow with five fixed mock Top Action List rows. It does not download Yahoo Finance data, refresh the universe, export reports, overwrite watchlist files, or send email.

`--self-test` runs lightweight health checks for configuration, environment loading, OpenAI key presence, Gmail variable presence, universe row count, SPY/QQQ data, OpenAI connection, AI analysis, and report-folder writability. It does not run the full screener or send email.

`--report-preview` rebuilds a local HTML layout preview from `daily_watchlist_last_good.csv` and `summary_history.csv`. It does not download Yahoo Finance data, call OpenAI, send email, append history, or overwrite `daily_watchlist.html`; it writes `daily_watchlist_preview.html`.

`--industry-test` runs synthetic ranking cases for candidate-count bias, median outlier protection, recent rotation, lagging former leaders, and one-stock exclusions. `--report-test` verifies deterministic review order, market character, tight-base integrity, support-signal deduplication, and email-preview ordering without sending email.

The script exports:

- `universe.csv`
- `universe_raw_temp.csv`
- `daily_watchlist.csv`
- `daily_watchlist.md`
- `daily_watchlist.html`
- `daily_watchlist_preview.html` when `--report-preview` is used
- `email_summary.txt`
- `summary_history.csv`

After a validated successful run, the script also saves last-known-good reports:

- `daily_watchlist_last_good.csv`
- `daily_watchlist_last_good.md`
- `daily_watchlist_last_good.html`

If Yahoo Finance data quality fails validation, the current daily watchlist files are not overwritten. The script writes `data_failure_report.txt` and sends a warning email instead of an empty watchlist.

Generated report and universe files are local runtime outputs and should not be committed to Git.

## Folder Structure

```text
stock_screener/
  ai_analysis.py          Optional AI commentary support
  config.py               Screening thresholds and data-source settings
  run_screener.py         Main universe, screening, ranking, and report pipeline
  send_email.py           Gmail SMTP sender for the generated HTML report
  test_openai.py          Safe standalone OpenAI Responses API connection test
  docs/                   Project logic and GitHub safety notes
  examples/               Fake sample files only
  requirements.txt        Python dependencies
  .env.example            Safe environment variable template
  .gitignore              Secret and cache exclusions
  README.md               Setup and usage documentation
  PROJECT_GUIDE.md        Design philosophy and architecture reasoning
  ROADMAP.md              Future development priorities
  CHANGELOG.md            Versioned project history
```

Generated files such as reports, preview reports, `summary_history.csv`, `universe.csv`, and `.yfinance_cache/` are runtime outputs.

## Environment Variables

Create a local `.env` file from `.env.example` or use Windows environment variables:

```text
OPENAI_API_KEY=your_openai_api_key_here
GMAIL_ADDRESS=your_email@gmail.com
GMAIL_APP_PASSWORD=your_app_password
```

Never commit real secrets. `.env` and `*.env` are ignored by Git.

## Configuration

Edit `config.py` to change deterministic screening thresholds such as:

- Minimum price
- Market-cap policy and its explicit enforcement status
- Minimum average volume
- ADR limits
- Relative Strength score
- Top Action noise-gate thresholds
- Universe refresh age
- Category limits

AI, email, and debug settings live in `config.py`:

```python
ENABLE_AI_COMMENTARY = True
AI_MODEL = "gpt-4o-mini"
AI_MAX_TICKERS = 15
AI_MAX_OUTPUT_TOKENS = 1200
AI_TEMPERATURE = 0.2
DEBUG = False
EMAIL_ENABLED = True
```

`AI_MAX_TICKERS` is capped at 15 by the AI module even if a higher value is accidentally configured.

Top Action noise-gate settings also live in `config.py`:

```python
MIN_REVIEW_NOW_SCORE = 55
MIN_HIGH_PRIORITY_SCORE = 50
MIN_HIGH_PRIORITY_RS_SCORE = 85
MIN_ACTIONABLE_INDUSTRY_SETUP_COUNT = 2
MIN_CONFIRMATION_VOLUME_RATIO = 0.30
MAX_ACTIONABLE_SUPPORT_DISTANCE_ATR = 2.5
```

## Universe

The screener does not use a hardcoded ticker list. It builds `universe_raw_temp.csv` from current NASDAQ and NYSE listings from NASDAQ Trader, removes ETFs, funds, warrants, units, preferred shares, and other identifiable non-common stocks, then uses Yahoo Finance historical price data to keep only stocks with:

- Price greater than 10
- 50-day average daily volume greater than 500,000

The configured USD 500m market-cap threshold is currently **not enforced** because complete reliable market-cap metadata is unavailable. Reports explicitly show `Market Cap Filter: NOT ENFORCED`; missing values are never fabricated or treated as passing values.

Daily runs reuse `universe.csv` when it is less than 7 days old. If the file is missing or at least 7 days old, the script rebuilds it automatically.

Universe refreshes are protected. A refresh is first written to `universe_temp.csv` and must pass validation before replacing `universe.csv`. The temporary universe must have the required columns, at least 1,500 tickers, no duplicate tickers, a usable ticker column, valid SPY and QQQ market data, and at least a 70% Yahoo historical-price download success rate. If the existing cache is invalid, it is renamed to `universe_invalid_<count>_backup.csv`; after a valid replacement, the new universe is also saved to `universe_backup.csv`. If validation fails, the temporary file is deleted and the existing universe is preserved.

Yahoo Finance calls are bounded by per-call timeouts, maximum retry attempts, and a 30-minute total screener runtime limit. If the limit is reached, the run enters the DATA FAILURE path and exits normally.

## Market Status

The report displays SPY and QQQ trend status at the top. It shows whether each ETF is above or below its:

- 10-day EMA
- 20-day EMA
- 50-day moving average

Market status does not change discovery, but the canonical trade-decision engine
uses the validated market regime as a new-risk gate. Caution and Risk Off can
therefore leave a stock visible while its final decision is `NO TRADE`.

SPY and QQQ data are mandatory for a valid run. If market data cannot be validated after retries, the run is treated as a data failure and no normal watchlist is exported.

## Data Quality Protection

Before exporting or emailing a normal watchlist, the screener validates:

- Universe count is at least 1,500.
- At least one of SPY or QQQ has valid market data.
- Price download success rate is at least 70%.

The console prints:

- Universe Count
- Requested Tickers
- Successful Downloads
- Failed Downloads
- Download Success Rate
- SPY Valid
- QQQ Valid
- Run Valid
- Fallback Used

If validation fails, `daily_watchlist.csv`, `daily_watchlist.md`, and `daily_watchlist.html` are preserved from the previous successful run.

## Filters

The screener first keeps liquid Stage 2-style stocks:

- Price greater than 10
- 50-day average volume greater than 500,000
- Relative Strength Score at least 75
- Price greater than the 50-day moving average
- 50-day moving average greater than the 150-day moving average
- 150-day moving average greater than the 200-day moving average
- 200-day moving average rising versus 20 trading days ago
- Price within 35% of the 52-week high
- 20-day ADR% between 1 and 10
- Price not more than 15% above the 10-day EMA
- Price not more than 20% above the 20-day EMA

## Report Sections

- `Executive Summary`: HTML-only top panel showing Market Status, Top Action count, confirmed setups, emerging leaders, caution rows, and price warnings.
- `Daily Change`: HTML and Markdown section comparing the current valid report with the previous valid report, including setup-count changes, new/removed Top Action tickers, and new/removed Top Industries.
- `Summary Trend`: HTML mini trend table with bars, plus Markdown table, showing the latest valid reports for confirmed setups, emerging leaders, caution rows, price warnings, and opportunity-quality score.
- `Daily Review Plan`: short workflow instructions generated from Review Tier, Top Action, Daily Focus, and Market Status. It tells the trader what to open first, what to track second, and when there are no clean first-review setups.
- `Top Action List`: the compact daily review list built after rule-based screening and noise-gated to `Review Now` or `High Priority Watch` rows.
- `Daily Focus List`: broader valid candidates for the day, including `Watch Later` rows that are worth tracking but should not dominate first-pass review.
- `Breakout Candidates`: stocks breaking above the pivot or prior 50-day high with a strong bullish candle and volume ratio.
- `Pullback Candidates`: stocks near the 10EMA, 20EMA, or 50MA with A or B Pullback Quality. Actions distinguish confirmed pullback reviews from quiet pullback watches.
- `Tight Consolidation Candidates`: stocks near highs with tight range behavior, controlled distance from the 50MA, and VCP/tightness context.
- `Extended Candidates`: C or D quality pullbacks near key moving averages, separated from normal pullbacks.
- `Volume Surge Candidates`: stocks near highs with bullish price action and elevated volume.
- `Top Industries`: groups with at least three eligible stocks, ranked by 65% recent Momentum and 35% structural Leadership.
- `Isolated / Emerging Industry Leaders`: noteworthy groups with fewer than three eligible stocks, excluded from formal ranks.
- `Developing Base Candidates`: base-shaped names that do not meet formal Tight/Very Tight or acceptable compression/VCP requirements.
- `AI Commentary`: optional assistant commentary on the Top Action List only.

## Email Automation

`run_screener.py` writes `email_summary.txt` and calls `send_email.py`.

The email body includes:

- Market Status
- Top Industries
- Top Action List
- AI Commentary
- A note that the full HTML report is attached

The HTML attachment is `daily_watchlist.html`.

On data failure, the warning email subject is `Stock Screener Data Failure`. It does not attach a watchlist.

To test email prerequisites without sending:

```bash
python send_email.py test
```

## Task Scheduler Setup

On Windows Task Scheduler:

1. Create a basic task.
2. Trigger it after the daily market close or before your review session.
3. Set the action to start a program.
4. Program/script: path to `python.exe`.
5. Add arguments: `run_screener.py`.
6. Start in: the full path to this project folder.
7. Store secrets in Windows environment variables or a local `.env` file.

## How AI Commentary Works

AI commentary is optional and disabled by default.

When enabled, `run_screener.py` builds the Top Action List first, then passes only that list, Top Industries, and Market Status to `ai_analysis.py`.

The AI prompt is intentionally compact. For each Top Action List stock, it sends only ticker, category, action, focus reason, Review Tier, Noise Filter Reason, RS Score, RS Trend, RS Trend Delta, industry rank, risk/reward quality, pullback quality, extension status, VCP label, volume ratio, ATR distance, distance from pivot, and support signal.

The Top Action List is sorted quality-first: individual Stage 2 quality, setup quality, volume context, support distance, and risk/reward are prioritised before industry rank is used as a secondary factor. The screener also adds credit when multiple stocks in the same known industry have valid setups through `Industry Setup Count`. Market status remains context rather than a replacement for stock-level quality. Unknown industry metadata can appear on individual stock rows, but it is excluded from Top Industries and cannot receive hot-industry ranking credit.

Top Action uses a deterministic noise gate after candidates are generated. A row must qualify as `Review Now` or `High Priority Watch` to appear in the first list, and those tiers are reserved for clean first-review setups. Weak risk/reward, weak pullback quality, extension, weakening RS, price-data warnings, poor VCP, loose action, poor support distance, weak confirmation volume, wait-only actions, and isolated industry context are recorded in `Noise Filter Reason`. Valid but lower-quality candidates remain in Daily Focus and category sections for secondary review.

`Review Priority Score` is deliberately hard to max out. Poor VCP, loose price action, weak confirmation, extension risk, poor risk/reward, fading RS trend, and price-data warnings reduce priority even when a stock is technically valid.

HTML reports start with an executive summary panel showing the count of Top Action tickers, confirmed setups, emerging leaders, caution rows, and price warnings. They expose exactly four trade states: `FULL`, `HALF`, `WATCH`, and `NO TRADE`. `HALF` is actionable now at no more than 0.5R; `WATCH` is non-actionable with zero shares. Valid runs append summary history and a new immutable evidence bundle under `output/forward_snapshots/<signal-date>/<run-id>/`. The bundle contains candidates, market, portfolio, config, and run metadata and never overwrites an earlier run.

Every candidate and run records the signal date, latest bar timestamp, and price-data as-of date. Freshness is checked against the latest completed regular US session using a weekend and regular full-day holiday calendar. Exceptional exchange closures are not available from the current dependency set and remain a documented limitation.

Industry metadata diagnostics show universe count, mapped count, unmapped count, coverage percentage, and cache date. If coverage is below `MIN_METADATA_COVERAGE_PCT`, industry qualification and sister-stock confidence cannot be presented as complete/high-confidence evidence.

The `Summary Trend` view uses recent valid reports to show whether opportunity quality is improving, deteriorating, or mixed. Its quality score is report context only: confirmed setups and emerging leaders add weight, while caution rows and price warnings subtract weight. It does not change filter output, select stocks, or predict market direction. CSV exports remain plain data without presentation-only badges or summary cards.

HTML reports also show review badges and row highlights for `Confirmed`, `Emerging Leader`, `Improving RS`, `Poor VCP`, `Loose`, extension risk, and price-data warnings. Markdown reports include the same information in a `Review Flags` column.

The RS Score is a MarketSmith-style percentile approximation based on weighted 3-month, 6-month, and 12-month returns. It is designed to focus review on RS 75+ leadership stocks, but it is not the proprietary MarketSmith RS Rating formula.

`RS Trend` compares the current RS percentile with the same calculation roughly 21 trading days earlier:

- `Emerging Leader`: RS 75+ and rising sharply
- `Improving`: RS rising meaningfully
- `Stable Leader`: already high RS and holding leadership
- `Stable`: little relative change
- `Weakening`: relative strength deteriorating
- `Fading`: relative strength deteriorating sharply

When AI returns structured rankings, the Top Action List includes:

- `AI Conviction Score`
- `AI Priority Rank`
- `AI Reason`
- `AI Bull Case`
- `AI Concern`
- `AI Confirmation`

The AI Conviction Score means how well the ticker matches the Stage 2 swing trading system today. It does not mean probability of profit.

AI commentary is required to include both positive evidence and concerns. High conviction should not be assigned to loose, Poor VCP, weak-confirmation, or price-warning setups unless the supplied rule-engine evidence is exceptional.

The console prints safe AI status without exposing secrets:

- AI Commentary: Enabled or Disabled
- OpenAI API Key: Loaded or Missing
- AI Model
- AI Tickers Analysed

AI diagnostics also print safe request metadata when available:

- API Call status
- JSON Parsed status
- Response Time
- Input Tokens
- Output Tokens
- Total Tokens
- Safe OpenAI error type on failure

AI can:

- Prioritise
- Summarise
- Explain

AI must not:

- Select stocks from the full universe
- Add new stocks
- Override rule-based screening
- Make final decisions
- Predict the market

If AI fails, reports still export and email still attempts to send.

If AI fails during analysis, reports and email use:

```text
AI Commentary failed safely.
```

If the OpenAI key is missing, the project displays only:

```text
OPENAI_API_KEY not found.
```

## Typical Daily Workflow

1. Run `python run_screener.py` or let Task Scheduler run it.
2. Review Market Status.
3. Check Top Industries for leadership and rotation.
4. Read `Daily Review Plan`.
5. Open `Review Now` tickers first.
6. Review `High Priority Watch` only after confirmed setups.
7. Use `Daily Focus List` as a tracking pool, not as the first decision list.
8. Skip rows marked `Skip Today` unless they reappear with cleaner setup quality later.
9. Use TradingView links for chart inspection.
10. Read AI Commentary as a summary aid only.
11. Make the final trading decision manually.

## Project Documentation Rule

Every future modification must begin by reading:

1. `PROJECT_GUIDE.md`
2. `ROADMAP.md`
3. `CHANGELOG.md`
4. `README.md`

Every successful code change must update:

1. `CHANGELOG.md`
2. `PROJECT_GUIDE.md` if design philosophy changes
3. `README.md` if setup or usage changes
4. `ROADMAP.md` if development direction changes

## Git Safety

Commit source code, documentation, requirements, and fake examples only.

Do not commit:

- `.env` or `*.env`
- Generated daily reports
- Universe CSV caches
- Yahoo Finance cache files
- Logs, local output, or data folders
- Credentials, tokens, CVs, cover letters, PDFs, or private tracker files
