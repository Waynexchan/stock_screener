# Project Changelog

## 2026-09-05 - Canonical production decision integrity

- Unified decision authority under one deterministic FULL/HALF/WATCH/NO TRADE
  pipeline; the sizing helper can only size an already-authorised state.
- Added PASS/MARGINAL/FAIL setup integrity, production portfolio and candidate
  concentration gates, session-aware price freshness, and semantic cross-output
  validation for CSV, HTML, and email.
- Made the USD 500m market-cap limitation explicit as `NOT ENFORCED`, added
  industry metadata coverage diagnostics/downgrades, and introduced immutable
  daily forward-test evidence bundles.
- Added regression coverage for loose developing bases, valid early leaders
  below a 75 score, invalid high-score setups, risk capacity, freshness, report
  consistency, and snapshot non-overwrite behaviour. No historical backtest or
  positive-expectancy claim was added.

## 2026-09-02 - Report readiness and invariant hardening

- Prevented Caution/Risk Off regimes from publishing contradictory HALF candidates.
- Replaced misleading binary trade readiness with READY, CONDITIONAL, and NO.
- Made missing Recent RS scores unavailable instead of accidentally scoring 100.
- Constrained AI labels to deterministic trade state, separated warning-message and
  affected-candidate counts, and added publication-blocking cross-field invariants.

## 2026-08-13 - Drawdown-first three-state sizing

- Replaced action grading with exactly `FULL` (1R), `HALF` (0.5R), and
  `NO TRADE`; incomplete secondary confirmation reduces size without admitting
  structurally invalid trades.
- Added equity high-water-mark drawdown modes, market/drawdown effective heat,
  a four-position hard cap, concentration-aware maximum shares, and explicit
  protection against automatic HALF-to-FULL upgrades.
- Added FULL/HALF journal analytics, deterministic entry timing, concise report
  fields, AI immutability boundaries, and regression/dry-run coverage for all
  drawdown and capacity states.

## 2026-08-10 - Production-depth logic audit

- Replaced placeholder market inputs with measured index slopes, breakout
  success/failure, leadership, high-volume breakdown, and volatility factors.
- Market confidence now discloses incomplete and thin-sample inputs instead of
  presenting placeholder zeros as complete high-confidence evidence.
- Reconciled raw industry candidate counts with qualifying setup counts.
- Prevented a model-generated 2R feasibility target from qualifying a ticker
  for Top Action without chart-confirmed resistance, and enforced minimum
  trade-plan confidence in both decision paths.
- Added system-level report warnings, target-source visibility, stable breakout
  failure calculation, and regression coverage for these production defects.
- Live production follow-up aligned canonical `Valid R/R` with the action and
  review mappings, exposed below-threshold Recent RS explicitly, and replaced
  contradictory negative-factor names with human-readable wording.

## 2026-08-06 - Decision-system regression correction

- Connected portfolio heat and position-data status to production output and final risk permission; missing or stale data is no longer represented as zero heat.
- Split industries into qualified current leaders, rotation watches, lagging long-term leaders, and explicit small-sample classifications. Only qualified leaders receive actionable rank/confirmation benefits.
- Added sample-quality labels, count-plus-percentage breadth, deterministic source-labelled trade plans, and explicit model-2R target labels.
- Final Score now retains all six components, base score, penalties, and hard-gate result for WATCH_ONLY and BLOCKED records.
- Loose/Poor-VCP consistency now updates category, quality, tier, confirmation, and decision rather than only appending text.
- Executive counters now use unique canonical tickers; added 2026-08-06 regression tests.

## 2026-08-06 - Daily Trading Decision System foundation

- Added deterministic position-risk, Portfolio Heat, market-regime, Recent RS,
  industry qualification, setup-consistency, real R/R, decision, concentration,
  and expectancy models in `decision_system.py`.
- Added the permanent auto-debug policy, offline 2026-08-05 regression fixture,
  105-test suite, dry-run report, verification command, and guarded production
  wrapper. Normal production requires a successful verification marker.
- Fixed the underlying defects: Recent RS was computed before metadata enrichment;
  missing Recent RS was not a hard gate; EMA reclaims could create confirmation;
  R/R was inferred without an entry, stop, and target; and weak candidate counts
  could create industry strength.
- Industry qualification now uses the eligible liquid universe and explicit
  absolute/relative momentum, breadth, size, and breakout-quality gates. Setup
  counts are quality-filtered and an unqualified industry supplies no bonus.
- Added configurable USD 587 standard risk, regime heat limits, per-trade/day,
  industry/theme and overnight-gap limits. No live-trading capability was added.
- Added user, risk-model, and watchlist-logic documentation and blank schemas for
  open positions and completed trades.
- Production audit follow-up: prevented candidate skip share from converting a
  Strong index regime into `Weak / Risk-Off`, made `Loose` an unconditional bar
  to formal Tight Consolidation, treated unavailable trade-plan R/R as Watch
  Later rather than weak R/R, and made Final Decision, Confirmed Setup, and
  Review Tier update together in the final guidance stage.

## Project Goal

Build a professional long-term Stage 2 swing trading assistant that helps a trader review the market in under 10 minutes using deterministic screening, industry ranking, risk-aware prioritisation, and optional AI commentary.

## Current Workflow

1. Check SPY and QQQ market status.
2. Load or rebuild the liquid common-stock universe.
3. Download Yahoo Finance price history.
4. Apply Stage 2 and liquidity filters.
5. Calculate Relative Strength.
6. Build candidate categories.
7. Rank industries.
8. Build the Top Action List and Daily Focus List.
9. Add optional AI commentary on the Top Action List only.
10. Export reports, append local summary history, and email the HTML watchlist.

## Current Features

- NASDAQ Trader universe construction.
- Yahoo Finance market data.
- Stage 2 trend filtering.
- Weighted Relative Strength scoring.
- Relative Strength trend labels for emerging and fading leadership.
- Price sanity screening and differentiated review-priority scoring.
- Top Action noise gate with review tiers and noise reasons.
- HTML executive summary panel, report summary history and trend view, no-network report preview, review badges, and Markdown review flags.
- ATR-based pullback and extension context.
- Industry Strength Score ranking.
- Top Action List.
- Daily Focus List.
- CSV, Markdown, HTML, and email summary output.
- Gmail SMTP email attachment support.
- Optional OpenAI commentary with secure API key loading.

## Current Version

Version: 0.3.17

## Roadmap

- Add automated tests for ranking and report generation.
- Add command-line flags for no-email and no-AI runs.
- Add historical tracking for watchlist outcomes.
- Add richer market and breadth context.
- Add optional exclusion lists.

## Changelog Entries

### 2026-08-05 - Version 0.4.0

Root cause: the previous industry model used only RS 75+ Stage 2 stocks that already appeared in a setup category. It excluded weak industry members, added raw candidate-count credit, and had no recent return, SPY-relative, median, minimum-size, or full-universe breadth input. This allowed Healthcare/Biotechnology groups with many historically strong survivors to remain persistently high ranked during recent underperformance.

Previous formula: `70% × Average RS Score + 1.5 × min(raw Candidate Count, 20)`; internal ranks separately sorted average long-term RS then raw count.

Changes:

- Added separate Recent RS Score: 15% 5D, 45% 20D, 30% 60D, and 10% 126D percentile-ranked relative returns versus SPY.
- Kept the existing long-term RS model and core Stage 2 filters unchanged.
- Added Industry Momentum Score: 15% median 5D relative return, 35% median 20D, 20% median 60D, 10% median Recent RS, 10% 20D outperformance breadth, 5% above 20EMA, and 5% acceleration percentiles.
- Added Industry Leadership Score: 40% median long-term RS, 20% average long-term RS, 15% Stage 2 breadth, 10% within 15% of the 52-week high, 10% leader quality, and 5% candidate breadth.
- Added Final Industry Score: 65% Momentum plus 35% Leadership, with separate ranks and status labels.
- Normalised candidate influence as Candidate Count / Total Eligible Stocks and removed raw count from the score.
- Required three eligible stocks for formal Top Industries and added an isolated/emerging section.
- Ranked leaders by Recent RS, long-term RS, then Review Priority.
- Fixed operational ordering to use Review Tier, confirmed setup, Review Priority, Recent RS, Industry Rank, then AI only as a tie-breaker.
- Added deterministic market-character classification; Strong Breakout requires multiple confirmed, volume-supported breakouts.
- Moved loose/poor-compression bases to Developing Base / Watch Later instead of formal Tight Consolidation.
- Deduplicated Support Signal display values while preserving order.
- Expanded AI inputs and instructions to compare supplied metrics without overriding deterministic order or claiming fund flows.
- Added `--industry-test` and `--report-test` lightweight modes; neither sends email.

Tests completed: Python compilation, 39 existing unit tests, synthetic industry tests, and report-integrity tests. No production screener or email was run during development.

Breaking changes: Top Industry report columns and ranking semantics changed. Core Stage 2 filters and personal trade-management rules remain unchanged.

### 2026-07-24 - Version 0.3.17

Files Modified:

- `README.md`
- `CHANGELOG.md`

Reason:

- Make the GitHub README clearer as a public-facing repository landing page.

Changes:

- Added a GitHub quick-start section.
- Added concise "What This Project Does" and "What This Project Does Not Do" sections.
- Added a prominent GitHub safety notice for generated files, secrets, credentials, and private local data.
- Added a daily report usage section explaining how to read Executive Summary, Daily Review Plan, Top Action, High Priority Watch, Daily Focus, and Skip Today rows.

Impact:

- New developers and GitHub viewers can understand the project, run it safely, and avoid committing private runtime files.
- Daily report usage is easier to understand directly from the README.
- No screening logic, scoring logic, Yahoo Finance behavior, AI behavior, email behavior, or Task Scheduler behavior changed.

Breaking Changes:

- None.

Future Suggestions:

- Add sanitized screenshots or fake example report snippets under `examples/` for GitHub readers.

### 2026-07-24 - Version 0.3.16

Files Modified:

- `run_screener.py`
- `test_data_quality.py`
- `PROJECT_GUIDE.md`
- `README.md`
- `ROADMAP.md`
- `CHANGELOG.md`

Reason:

- Make the daily report easier to use as a first-pass trading review list without requiring the trader to reinterpret every report column.

Changes:

- Added a `Daily Review Plan` section to HTML reports.
- Added the same daily review plan to Markdown reports and email summaries.
- The plan identifies which tickers to open first, which names are secondary tracking only, and when no clean first-review setups are present.
- Added market-context wording so caution markets explicitly reduce urgency without changing stock selection.
- Added regression tests for review-plan rendering and empty Top Action behavior.

Impact:

- The report now tells the trader how to use the list before the detailed tables.
- Top Action remains the first-pass decision list, while Daily Focus remains the broader tracking pool.
- Screening logic, scoring logic, Yahoo Finance behavior, AI behavior, email sending, and Task Scheduler behavior are unchanged.

Breaking Changes:

- None.

Future Suggestions:

- Add a compact `Clean Setup Score` or column-level score breakdown so each row shows why it passed or missed the first-review gate.

### 2026-07-24 - Version 0.3.15

Files Modified:

- `run_screener.py`
- `test_data_quality.py`
- `PROJECT_GUIDE.md`
- `README.md`
- `ROADMAP.md`
- `CHANGELOG.md`

Reason:

- Tighten the first-review list after valid reports showed `Review Now` and `High Priority Watch` rows with poor VCP, loose action, wait-only actions, or weak pullback quality.

Changes:

- Changed `Review Tier` logic so Top Action rows must be clean enough for first-pass chart review.
- Added `weak pullback quality` as a deterministic noise reason for C/D pullback quality rows.
- Excluded poor VCP, loose action, far support distance, thin confirmation volume, isolated industry setup, and wait-only actions from Top Action eligibility.
- Kept these lower-quality but still valid candidates in Daily Focus and category sections for secondary review.
- Added regression tests proving noisy confirmed setups, watch-only rows, and weak pullback-quality rows no longer enter the Top Action List.

Impact:

- The Top Action List should be shorter, cleaner, and more reliable for daily review.
- The broader screener still preserves valid Stage 2 candidates outside the first-priority list.
- Screening thresholds, Yahoo Finance behavior, AI behavior, email behavior, and Task Scheduler behavior are unchanged.

Breaking Changes:

- Top Action may be materially smaller on caution days because valid-but-noisy candidates are now filtered down to Daily Focus or category sections.

Future Suggestions:

- Add an optional `Clean Setup Score` column to explain exactly how much score was lost to VCP, tightness, support distance, volume, and industry confirmation.

### 2026-07-23 - Version 0.3.14

Files Modified:

- `config.py`
- `run_screener.py`
- `ai_analysis.py`
- `test_data_quality.py`
- `PROJECT_GUIDE.md`
- `README.md`
- `ROADMAP.md`
- `CHANGELOG.md`

Reason:

- Reduce first-pass review noise so the trader can focus on a shorter, more actionable daily Top Action List.

Changes:

- Added configurable Top Action noise-gate thresholds in `config.py`.
- Added `Review Tier` with values such as `Review Now`, `High Priority Watch`, `Watch Later`, and `Skip Today`.
- Added `Noise Filter Reason` to explain why a valid candidate is not suitable for first-pass review.
- Changed Top Action List construction so only `Review Now` and `High Priority Watch` rows appear in the first list.
- Preserved broader valid candidates in Daily Focus and category sections for secondary review.
- Added Review Tier badges and summary counts to HTML reports.
- Added Review Tier and Noise Filter Reason to compact AI Top Action input so AI explanations inherit the deterministic gate context.
- Added regression tests for review tiers, Top Action noise filtering, and compact AI context.

Impact:

- The first list should contain fewer noisy candidates and more closely match the user's daily workflow: open the report, review only the strongest setups first, then decide manually.
- Existing deterministic setup detection remains intact; lower-priority valid candidates are still visible outside the Top Action List.
- Yahoo Finance behavior, market data validation, email behavior, Task Scheduler behavior, and AI stock-selection boundaries are unchanged.

Breaking Changes:

- The Top Action List can now contain fewer rows than before when candidates are valid but not actionable enough for immediate review.

Future Suggestions:

- Add optional preview fixtures under `examples/` so report-layout and noise-gate tests can run even before a machine has generated a last-known-good report.

### 2026-07-23 - Version 0.3.13

Files Modified:

- `run_screener.py`
- `test_data_quality.py`
- `PROJECT_GUIDE.md`
- `README.md`
- `ROADMAP.md`
- `CHANGELOG.md`

Reason:

- Add a no-network report preview mode so HTML layout and summary-history presentation can be tested without running the full screener.

Changes:

- Added `python run_screener.py --report-preview`.
- Added `daily_watchlist_preview.html` output generated from `daily_watchlist_last_good.csv` and optional `summary_history.csv`.
- Rebuilds Top Action List, Daily Focus List, Top Industries, Executive Summary, Daily Change, and Summary Trend from local files only.
- Explicitly disables Yahoo Finance downloads, OpenAI calls, email sending, production report overwrite, and summary-history appending in preview mode.
- Added regression test proving preview generation uses local files and does not append history.

Impact:

- HTML report changes can now be reviewed quickly and safely without provider/network/API/email side effects.
- Production `python run_screener.py` behavior is unchanged.

Breaking Changes:

- None.

Future Suggestions:

- Add optional preview fixtures under `examples/` so layout tests can run even before a machine has generated a last-known-good report.

### 2026-07-23 - Version 0.3.12

Files Modified:

- `run_screener.py`
- `test_data_quality.py`
- `PROJECT_GUIDE.md`
- `README.md`
- `ROADMAP.md`
- `CHANGELOG.md`

Reason:

- Add a recent summary trend view so report-to-report history can show whether opportunity quality is improving, deteriorating, or mixed.

Changes:

- Added recent summary-history loading for the latest valid report snapshots.
- Added deterministic `Opportunity Quality Score` using confirmed setups and emerging leaders as positive context, and caution rows plus price warnings as negative context.
- Added trend assessment labels: improving opportunity quality, deteriorating opportunity quality, mixed/stable opportunity quality, or collecting history.
- Added HTML `Summary Trend` mini table with visual bars for the latest valid reports.
- Added Markdown `Summary Trend` table for non-HTML review.
- Added regression tests for trend calculation, HTML trend rendering, and Markdown trend rendering.

Impact:

- Reports now make the current filtered list more useful by showing whether setup quality is expanding or weakening across recent valid sessions.
- The trend view is context only and does not change stock selection, scoring, screening thresholds, AI behavior, Yahoo Finance behavior, email sending, or Task Scheduler behavior.

Breaking Changes:

- None.

Future Suggestions:

- Add a future no-network report-preview mode so HTML layout changes can be inspected from stored history and last-good reports without downloading market data.

### 2026-07-23 - Version 0.3.11

Files Modified:

- `run_screener.py`
- `test_data_quality.py`
- `.gitignore`
- `PROJECT_GUIDE.md`
- `README.md`
- `ROADMAP.md`
- `CHANGELOG.md`

Reason:

- Persist report summary history so valid reports can compare daily setup-quality, stock, and industry changes.

Changes:

- Added local `summary_history.csv` snapshots after successful valid report exports.
- Added report-to-report comparison for Top Action count, confirmed setups, emerging leaders, caution rows, and price warnings.
- Added new/removed Top Action ticker comparison versus the previous valid report.
- Added new/removed Top Industry comparison versus the previous valid report.
- Added `Daily Change` sections to HTML and Markdown reports.
- Added `summary_history.csv` to `.gitignore` because it is a local runtime output.
- Added regression tests for history delta calculation, append/load behavior, and HTML daily-change rendering.

Impact:

- The trader can now see whether leadership and setup quality are improving, deteriorating, or rotating between valid reports.
- Data-failure runs do not append history because the feature is attached only to the successful report export path.
- No screening thresholds, scoring logic, industry ranking logic, Yahoo Finance behavior, AI behavior, email sending, or Task Scheduler behavior changed.

Breaking Changes:

- None.

Future Suggestions:

- Add a compact chart of summary-history trends once enough valid report snapshots have accumulated.

### 2026-07-23 - Version 0.3.10

Files Modified:

- `run_screener.py`
- `test_data_quality.py`
- `PROJECT_GUIDE.md`
- `README.md`
- `ROADMAP.md`
- `CHANGELOG.md`

Reason:

- Add a compact HTML report summary so the trader can judge daily setup quality immediately when opening the watchlist.

Changes:

- Added a top-of-report `Executive Summary` panel to `daily_watchlist.html`.
- Added counts for Top Action tickers, confirmed setups, emerging leaders, caution rows, and price warnings.
- Kept the summary panel presentation-only; it reads existing Top Action List review flags and does not affect screening, scoring, ranking, AI, Yahoo Finance, email, or Task Scheduler behavior.
- Added regression tests for summary-count calculation and HTML panel rendering.

Impact:

- The HTML report now gives a faster first-read view of whether the day has clean actionable setups, emerging leadership, or cautionary data/setup flags.
- CSV and Markdown exports remain structurally unchanged.

Breaking Changes:

- None.

Future Suggestions:

- Persist summary counts over time so the trader can review whether market opportunity quality is improving or deteriorating across sessions.

### 2026-07-23 - Version 0.3.9

Files Modified:

- `run_screener.py`
- `test_data_quality.py`
- `PROJECT_GUIDE.md`
- `README.md`
- `ROADMAP.md`
- `CHANGELOG.md`

Reason:

- Improve report scan speed by visually highlighting confirmed pullbacks, emerging leaders, weak VCP/tightness, extension risk, and price-data warnings.

Changes:

- Added presentation-only `Review Flags` to Markdown and HTML tables.
- Added HTML badge rendering for `Confirmed`, `Emerging Leader`, `Improving RS`, `Poor VCP`, `Loose`, extension risk, and price warnings.
- Added row highlighting for priority, caution, and risk contexts.
- Added sticky HTML table headers for easier scanning of wide reports.
- Kept CSV exports unchanged so downstream data workflows remain stable.
- Added regression tests for review flags, HTML badge rendering, and Markdown flag output.

Impact:

- Daily reports should be faster to scan visually.
- The trader can more quickly separate immediate review candidates from watch-only or cautionary names.
- No screening thresholds, Yahoo Finance behavior, AI scope, email behavior, or Task Scheduler behavior changed.

Breaking Changes:

- None.

Future Suggestions:

- Add a compact executive-summary panel at the top of the HTML report showing counts for confirmed setups, emerging leaders, caution flags, and price warnings.

### 2026-07-23 - Version 0.3.8

Files Modified:

- `run_screener.py`
- `ai_analysis.py`
- `test_data_quality.py`
- `PROJECT_GUIDE.md`
- `README.md`
- `ROADMAP.md`
- `CHANGELOG.md`

Reason:

- Improve report quality after review showed priority-score saturation, weak separation between confirmed and quiet pullbacks, low-quality VCP/tightness setups ranking too highly, and AI commentary that was too generic.

Changes:

- Added price sanity warnings for missing/insufficient/invalid price history, extreme latest-close changes, and latest close inconsistent with recent medians.
- Excluded obvious price-data anomalies from screening before candidate generation.
- Added `Price Data Warning` to candidate rows for explicit report traceability.
- Rebalanced `Review Priority Score` to avoid easy 100-point saturation.
- Increased penalties for `Poor VCP`, `Loose` tightness, extended status, weak/fading RS trend, and poor risk/reward.
- Kept individual stock quality first, but made tightness, VCP quality, and confirmation more important inside setup quality.
- Split pullback actions into `Confirmed pullback entry review`, `Monitor quiet pullback`, and `Wait for cleaner entry`.
- Added explicit actions for breakout and volume-surge candidates.
- Expanded AI structured output with `bull_case`, `concern`, and `confirmation`.
- Updated AI prompt to require both positives and concerns, and to avoid high conviction scores for poor VCP, loose, weak-confirmation, or price-warning setups.
- Added regression tests for score saturation, VCP/tightness penalties, pullback action labels, price sanity warnings, and AI schema requirements.

Impact:

- Top Action List ordering should now be more selective and less likely to show many identical 100.0 scores.
- Loose/Poor VCP pullbacks can still appear when they pass deterministic rules, but should rank below cleaner setups.
- Reports and AI commentary should better distinguish immediate review candidates from quiet watchlist names.

Breaking Changes:

- None.

Future Suggestions:

- Add report styling for `Confirmed pullback entry review`, `Emerging Leader`, and price-data warnings.
- Persist rejected price-data warnings to a safe local diagnostic file for data-quality audits.

### 2026-07-22 - Version 0.3.7

Files Modified:

- `run_screener.py`
- `ai_analysis.py`
- `test_data_quality.py`
- `PROJECT_GUIDE.md`
- `README.md`
- `ROADMAP.md`
- `CHANGELOG.md`

Reason:

- Add RS Trend so the screener can identify emerging leaders instead of relying only on point-in-time RS Score.

Changes:

- Added MarketSmith-style RS trend metrics by comparing current weighted RS percentile against the same percentile calculation roughly 21 trading days earlier.
- Added `RS Trend` and `RS Trend Delta` columns to candidate rows and reports.
- Added RS trend labels: `Emerging Leader`, `Improving`, `Stable Leader`, `Stable`, `Weakening`, `Fading`, and `Unknown`.
- Added review-priority bonus for `Emerging Leader`, `Improving`, and `Stable Leader` stocks.
- Added review-priority penalty for `Weakening` and `Fading` stocks.
- Kept `calculate_rs_scores()` backward compatible by deriving the original ticker-to-score mapping from the new RS metrics.
- Added `RS Trend` and `RS Trend Delta` to the compact AI Top Action List input only.
- Added regression tests for RS trend labels and review-priority bonus.

Impact:

- The screener can now surface stocks moving into leadership, not only stocks that already have a high static RS Score.
- Fading leaders are still allowed if they pass deterministic rules, but receive lower review priority.
- AI cost increases only slightly because two compact fields are added for Top Action List tickers only.

Breaking Changes:

- None.

Future Suggestions:

- Persist daily RS snapshots to improve trend accuracy beyond the current in-run 21-trading-day approximation.
- Add report styling to visually flag `Emerging Leader` rows.

### 2026-07-22 - Version 0.3.6

Files Modified:

- `config.py`
- `run_screener.py`
- `test_data_quality.py`
- `PROJECT_GUIDE.md`
- `README.md`
- `ROADMAP.md`
- `CHANGELOG.md`

Reason:

- Align the screener more closely with a MarketSmith-style leadership workflow: focus on RS 75+ stocks, then reward industries where multiple high-quality Stage 2 stocks have active setups.

Changes:

- Raised `config.MIN_RS_SCORE` from 60 to 75.
- Added `Industry Setup Count` to candidate rows and reports.
- Changed industry context so Industry Rank and Top Industries are calculated from stocks that have an actual setup candidate row, not merely every Stage 2 stock.
- Added review-priority bonus when the same known industry has multiple setup candidates.
- Kept industry rank as a secondary bonus after individual stock quality, setup quality, volume, extension, and risk/reward.
- Added regression tests for RS 75 minimum and industry setup cluster bonus.
- Updated documentation to clarify that the RS score is a MarketSmith-style percentile approximation, not the proprietary MarketSmith RS Rating formula.

Impact:

- The screener should produce a narrower, higher-quality candidate list.
- Individual stocks with strong Stage 2 structure, volume, and setup quality remain the first priority.
- Industry leadership now gets more credit when several stocks in the same known industry are also setting up.

Breaking Changes:

- The stricter RS threshold may reduce the number of candidates versus prior reports.

Future Suggestions:

- Add RS trend tracking so the screener can identify stocks moving into leadership, not only stocks already ranked highly.
- Add maintained sector/industry metadata to improve industry cluster detection coverage.

### 2026-07-22 - Version 0.3.5

Files Modified:

- `run_screener.py`
- `test_data_quality.py`
- `PROJECT_GUIDE.md`
- `README.md`
- `ROADMAP.md`
- `CHANGELOG.md`

Reason:

- Fix the remaining Unknown industry ranking bug where missing metadata could appear as the strongest Top Industry and receive hot-industry priority credit.

Changes:

- Excluded `Unknown`, blank, `nan`, `none`, and `n/a` industry values from Top Industries.
- Excluded unknown industries from industry-rank calculation so missing metadata cannot receive an Industry Rank.
- Fixed review-priority numeric bounds so missing `Industry Rank` defaults to 999 instead of rank 1.
- Fixed review-priority numeric bounds so missing support distance defaults conservatively instead of being treated as near support.
- Added regression tests proving Unknown industries are excluded from Top Industries and cannot receive rank-based priority bonus.
- Updated documentation to clarify that Unknown metadata is reportable on individual rows but cannot be treated as industry leadership.

Impact:

- Top Industries should now show only real known industries.
- Top Action List priority still focuses on individual stock quality, setup quality, volume context, Stage 2 behavior, and risk/reward first.
- Stocks with unknown metadata can still appear if they pass deterministic stock filters, but they no longer benefit from fake industry leadership.

Breaking Changes:

- None.

Future Suggestions:

- Build or import a maintained ticker-to-industry seed file so fewer qualified stocks remain Unknown.
- Add a metadata refresh report showing which Top Action List tickers still need sector/industry enrichment.

### 2026-07-21 - Version 0.3.4

Files Created:

- `ROADMAP.md`
- `docs/PROJECT_LOGIC.md`
- `examples/sample_top_action_list.csv`

Files Modified:

- `.gitignore`
- `ai_analysis.py`
- `config.py`
- `run_screener.py`
- `test_data_quality.py`
- `test_openai.py`
- `PROJECT_GUIDE.md`
- `README.md`
- `CHANGELOG.md`

Files Removed:

- `test_gpt5.py`

Git Tracking Changes:

- Removed generated report and universe files from Git tracking while preserving local files.

Reason:

- Fix project hygiene, roadmap workflow, generated-file tracking, industry metadata degradation, quality-first review priority, AI model selection consistency, and AI conviction-score clarity.

Changes:

- Created `ROADMAP.md` using the required priority, status, benefit, complexity, dependency, and suggested-version format.
- Added `docs/PROJECT_LOGIC.md` with GitHub privacy safety guidance.
- Added a fake sample Top Action List under `examples/` so future commits can include representative data without private trading, job, credential, or tracker records.
- Expanded `.gitignore` for runtime reports, universe caches, metadata cache, local data/output/cache/log folders, private documents, credentials, virtual environments, and Python cache files.
- Removed tracked runtime outputs from Git index with `git rm --cached`; local files remain available.
- Removed temporary `test_gpt5.py`.
- Removed production AI model discovery based on `client.models.list()`; AI now uses `config.AI_MODEL` directly.
- Simplified `test_openai.py` to direct-call the configured model instead of relying on model-list availability.
- Added `sector_industry_cache.csv` support for best-effort sector and industry metadata enrichment after deterministic filtering.
- Added `Review Priority Score` to prioritise individual stock quality, setup quality, volume context, support distance, and risk/reward before using industry rank as a secondary factor.
- Expanded Top Action List selection to include all rule-engine candidate categories, including breakout and volume surge setups, then rank by review priority.
- Clarified AI conviction-score rubric to encourage differentiated 1-10 scoring.
- Added unit tests for quality-first priority and metadata cache enrichment.
- Updated README and project guide for roadmap, Git safety, metadata enrichment, and quality-first review philosophy.

Impact:

- GitHub Desktop should no longer show daily reports and universe CSV files as source-code changes after committing the index removals.
- Daily review now focuses first on high-quality individual Stage 2 setups with volume and risk/reward support, then industry leadership.
- Industry ranking can improve as metadata cache fills without making metadata lookup a hard dependency for universe refresh.
- Trading thresholds, Stage 2 filters, breakout/pullback/tight/extended/volume-surge detection rules, Yahoo validation behavior, email behavior, and Task Scheduler behavior are preserved.

Breaking Changes:

- Generated runtime files are no longer intended to be tracked in Git.

Future Suggestions:

- Add a maintained sector/industry seed file to reduce reliance on metadata lookups.
- Add no-email and no-AI CLI flags for safer local dry runs.
- Add report fixture tests for Top Action List ordering.

### 2026-07-12 - Version 0.3.3

Files Modified:

- `config.py`
- `ai_analysis.py`
- `test_openai.py`
- `README.md`
- `CHANGELOG.md`

Reason:

- Identify an OpenAI model actually available to the current project/key and configure AI diagnostics to use it safely.

Changes:

- Added safe OpenAI model availability selection through `client.models.list()`.
- Added `select_available_ai_model()` to choose the configured model when available, otherwise the highest-priority available compatible fallback.
- Filtered model output to compatible text/reasoning model IDs only.
- Updated `test_openai.py` to print configured model, selected model, fallback status, available preferred models, available compatible models, and safe plain-text API result.
- Discovered that none of the preferred models `gpt-5.6`, `gpt-5`, `gpt-5-mini`, `gpt-4.1`, or `gpt-4.1-mini` are available to this project/key.
- Discovered `gpt-4o-mini` is available and compatible.
- Updated `config.AI_MODEL` from `gpt-5.6` to `gpt-4o-mini`.
- Updated README configuration example to `gpt-4o-mini`.

Impact:

- OpenAI plain-text connection testing now succeeds with the configured model.
- AI analysis test mode now reaches the structured Responses API and returns parsed rankings.
- No trading logic, Yahoo Finance logic, email behavior, report generation, or Task Scheduler settings were changed.

Security Protections:

- API key, project ID, organisation ID, request headers, raw model list response, and unrelated model metadata are not printed.
- Model discovery output is limited to compatible model IDs and safe status fields.

Test Results:

- `python -m py_compile config.py` passed.
- `python -m py_compile ai_analysis.py` passed.
- `python -m py_compile test_openai.py` passed.
- `python test_openai.py` passed using `gpt-4o-mini`.
- `python run_screener.py --ai-test` passed using `gpt-4o-mini`.
- `--ai-test` parsed JSON, returned AI rankings, and reported token usage: 1,451 input tokens, 387 output tokens, 1,838 total tokens.

Breaking Changes:

- None.

Future Suggestions:

- If the OpenAI project later gains access to stronger preferred models, rerun `python test_openai.py` and update `config.AI_MODEL` after a successful plain-text test.

### 2026-07-12 - Version 0.3.2

Files Modified:

- `config.py`
- `ai_analysis.py`
- `test_openai.py`
- `run_screener.py`
- `README.md`
- `CHANGELOG.md`

Reason:

- Fix the OpenAI request path by using the configured model only, simplifying the plain-text connection test, and aligning the structured Responses API schema with strict JSON Schema requirements.

Changes:

- Changed `config.AI_MODEL` from `gpt-5.5` to `gpt-5.6`.
- Updated `test_openai.py` to send a minimal plain-text Responses API request with only `model`, `input`, and `max_output_tokens`.
- Updated `test_openai.py` safe output to show only plain-text call status, model used, safe error type, safe error code, and HTTP status.
- Removed hardcoded model fallback behavior from `ai_analysis.py`; AI calls now use `config.AI_MODEL` only.
- Removed optional `temperature` from the structured Responses API request.
- Updated structured output schema to use `market_summary`, `industry_rotation_summary`, `market_character`, `rankings`, `stocks_to_wait`, and `reminder`.
- Ensured every object in the structured schema has `additionalProperties: false`.
- Ensured every expected structured output property appears in `required`.
- Updated structured JSON parsing to use `response.output_text` followed by `json.loads`.
- Updated AI ranking mapping to read `priority_rank`, `conviction_score`, and `reason`.
- Added safe error code and HTTP status reporting to `--ai-test`.
- Updated README configuration example for `AI_MODEL`.

Impact:

- Plain-text OpenAI connectivity can now be tested before structured output.
- Structured AI analysis uses the requested Responses API `text.format` JSON schema shape.
- No trading logic, Yahoo Finance logic, scoring logic, industry ranking, email behavior, or Task Scheduler settings were changed.

Security Protections:

- API keys, request headers, request bodies, authorization headers, raw exception bodies, and `.env` contents are not printed.
- OpenAI failures expose only safe exception class, safe error code, and HTTP status.

Test Results:

- `python -m py_compile config.py` passed.
- `python -m py_compile ai_analysis.py` passed.
- `python -m py_compile test_openai.py` passed.
- `python -m py_compile run_screener.py` passed.
- `python test_openai.py` reached the OpenAI API but failed safely: `PermissionDeniedError`, safe error code `model_not_found`, HTTP status `403`, configured model `gpt-5.6`.
- `python run_screener.py --ai-test` was not run because the plain-text prerequisite test did not succeed.

Breaking Changes:

- None.

Future Suggestions:

- Confirm which OpenAI API model IDs are enabled for the current project/key.
- Update `config.AI_MODEL` to an accessible Responses API model if `gpt-5.6` is not available to this account.

### 2026-07-11 - Version 0.3.1

Files Created:

- `test_openai.py`

Files Modified:

- `ai_analysis.py`
- `run_screener.py`
- `README.md`
- `PROJECT_GUIDE.md`
- `CHANGELOG.md`

Reason:

- Add safe, fast AI diagnostics that verify OpenAI connectivity and AI ranking behavior without running the full Yahoo Finance screener.

Changes:

- Added standalone `python test_openai.py` Responses API connection test.
- Added `python run_screener.py --ai-test` using five fixed mock Top Action List rows.
- Added `python run_screener.py --self-test` for lightweight system health checks.
- Added safe AI metadata reporting for input tokens, output tokens, total tokens, response time, JSON parsing status, and safe OpenAI error type.
- Added `get_last_ai_analysis_result()` so test mode can inspect the real `generate_ai_commentary()` result without making a second API call.
- Kept all AI test paths separate from Yahoo universe refresh, full screening, report export, email sending, and Task Scheduler behavior.
- Installed the declared `openai` SDK dependency in the active Python environment for test execution.
- Updated README and project guide with AI diagnostic usage and design rationale.

Impact:

- OpenAI connectivity can now be tested independently from market data.
- AI ranking JSON behavior can now be tested with deterministic mock inputs.
- Self-test can identify whether the system is healthy or needs attention without running the full production screener.
- Screening logic, scoring logic, industry ranking, email settings, and Task Scheduler behavior are unchanged.

Security Protections:

- API keys, Gmail passwords, Gmail address values, request headers, authorization headers, `.env` contents, and raw exception bodies are never printed.
- Test output shows only Loaded/Missing, Success/Failed, response timing, token counts when available, and safe exception class names.

Test Results:

- `python -m py_compile config.py` passed.
- `python -m py_compile ai_analysis.py` passed.
- `python -m py_compile run_screener.py` passed.
- `python -m py_compile test_openai.py` passed.
- `python test_openai.py` reached the OpenAI API but failed safely with `PermissionDeniedError` for configured model `gpt-5.5`.
- `python run_screener.py --ai-test` failed safely before JSON parsing with `BadRequestError`; no rankings were fabricated.
- `python run_screener.py --self-test` completed in under 2 minutes and reported `Attention Required` because OpenAI connection and AI analysis failed while config, universe, Yahoo SPY/QQQ, reports folder, and Gmail configuration checks passed.

Breaking Changes:

- None.

Future Suggestions:

- Verify that the configured OpenAI project has access to `config.AI_MODEL`.
- Consider changing `config.AI_MODEL` to an available Responses API model after confirming account access.
- Add a local fixture test for AI JSON parsing that does not require an API call.

### 2026-07-11 - Version 0.3.0

Files Modified:

- `config.py`
- `run_screener.py`
- `send_email.py`
- `test_data_quality.py`
- `README.md`
- `PROJECT_GUIDE.md`
- `CHANGELOG.md`

Reason:

- Prevent partial Yahoo Finance failures from overwriting valid universe caches or reports with empty outputs.

Changes:

- Added universe refresh protection using `universe_temp.csv`.
- Added `universe_raw_temp.csv` creation from NASDAQ Trader listed-symbol files before historical liquidity filtering.
- Rebuilt the universe without relying on Yahoo company-profile calls.
- Added validation before replacing `universe.csv`: required columns, minimum 1,500 tickers, no duplicate tickers, usable ticker column, valid SPY and QQQ data, and minimum 70% Yahoo historical-price download success rate.
- Added `universe_backup.csv` creation after a valid universe replacement.
- Added automatic renaming of an invalid existing universe cache to `universe_invalid_<count>_backup.csv` before replacing it with a validated universe.
- Added data-quality tracking for requested tickers, successful downloads, failed downloads, and download success rate.
- Added retrying Yahoo Finance history downloads with smaller fallback chunk sizes.
- Capped fallback chunk sizes at 25 and 10 to avoid hundreds of individual ticker requests during provider outages.
- Added per-call Yahoo Finance timeout configuration and finite maximum retry attempts.
- Added a 30-minute maximum screener runtime that routes expired runs to the DATA FAILURE path.
- Added `python run_screener.py --data-test` for a quick Nasdaq/Yahoo validation run with email and AI disabled.
- Added `python run_screener.py --refresh-universe` to rebuild and validate the universe without screening, AI, reports, or email.
- Suppressed noisy Yahoo Finance error logging so data failures produce the project's safe summary instead of flooding scheduled-run output.
- Disabled yfinance background threading in the protected download helper to prevent failed provider calls from leaving the process alive after reporting data failure.
- Removed the temporary `os._exit()` workaround from `run_screener.py` and `send_email.py`; both scripts now use normal process termination.
- Added SPY/QQQ validation with retry delays before accepting market status.
- Added full-run validation before report export or normal email sending.
- Added `data_failure_report.txt` for safe diagnostics when a run is rejected.
- Added warning email mode with subject `Stock Screener Data Failure` and no watchlist attachment.
- Added last-known-good report copies after successful runs.
- Added safe console `Data Quality Check` summary.
- Added controlled simulation tests for universe validation, market-data failure, low download success rate, fallback behavior, report preservation, and warning email construction.
- Updated README and project guide for data reliability behavior.

Impact:

- A Yahoo Finance outage or partial response can no longer overwrite valid watchlist files with an empty normal report.
- Partial universe refreshes are rejected instead of replacing a valid cache.
- A 589-row invalid universe cache can be preserved as an invalid backup and replaced only after a validated rebuild.
- Universe rebuilds no longer fail solely because market-cap or company-profile data is unavailable.
- Data-source diagnostics can be run without repeated full screener runs or repeated test emails.
- Data failures are reported as operational failures rather than market conclusions.
- Trading logic, AI ranking logic, and screening thresholds are unchanged.

Breaking Changes:

- None.

Future Suggestions:

- Add a secondary market data source fallback.
- Add persistent run logs for scheduled Windows Task Scheduler runs.
- Add a manual command to restore `universe_backup.csv` when needed.

### 2026-07-10 - Version 0.2.3

Files Modified:

- `ai_analysis.py`
- `CHANGELOG.md`

Reason:

- Debug and fix the OpenAI request path without changing screening logic or adding trading features.

Changes:

- Replaced the deprecated Chat Completions fallback with Responses API only.
- Added structured `text.format` JSON schema enforcement for AI commentary and rankings.
- Added safe SDK/version, model-used, token, response-time, and parsing metadata to `AIAnalysisResult`.
- Added safe DEBUG-only OpenAI request lifecycle messages and error type reporting.
- Added safe model fallback from a configured invalid model to `gpt-5.5`.
- Added explicit `OpenAINotInstalledError` classification when the OpenAI SDK is missing.
- Improved response text extraction from Responses API output.
- Improved JSON recovery for fenced or mixed text responses.
- Kept AI failure behavior sanitized with `AI Commentary failed safely.`

Impact:

- AI integration now uses the current Responses API request style.
- Raw OpenAI exceptions, request bodies, headers, and secrets remain hidden from reports, emails, and normal console output.
- Screening, ranking, report export, and email behavior are unchanged.

Breaking Changes:

- None.

Future Suggestions:

- Install or upgrade the `openai` Python package in the runtime environment with `pip install -r requirements.txt`.
- Add a lightweight fixture test for parsing a representative Responses API JSON payload.

### 2026-07-10 - Version 0.2.2

Files Modified:

- `ai_analysis.py`
- `run_screener.py`
- `README.md`
- `PROJECT_GUIDE.md`
- `CHANGELOG.md`

Reason:

- Make AI usage visible at runtime and add structured AI conviction ranking for the Top Action List only.

Changes:

- Added structured `AIAnalysisResult` metadata for safe console reporting.
- Added console output for AI enabled/disabled state, OpenAI API key loaded/missing state, AI model, and number of tickers analysed.
- Flushed AI console status output immediately so it is visible before email subprocess output.
- Added AI-generated `AI Conviction Score`, `AI Priority Rank`, and `AI Reason` columns to the Top Action List.
- Limited structured AI ranking to the Top Action List with a hard maximum of 15 tickers.
- Expanded compact AI input fields to include VCP Label and Distance From Pivot %.
- Updated the AI prompt to request strict JSON with commentary and per-ticker rankings.
- Sanitised AI failure behavior to show `AI Commentary failed safely.` without raw exception text.
- Preserved the existing AI commentary section in HTML, Markdown, and email body.
- Updated README and project guide to document AI conviction scoring and safe console status.

Impact:

- It is now clear from console output whether AI is enabled, whether the API key was loaded, which model is configured, and how many Top Action List tickers were analysed.
- Top Action List report tables can show AI ranking context when AI returns structured output.
- AI still cannot analyse the full universe or all candidates.
- Normal report export and email sending continue if AI is unavailable or fails.

Breaking Changes:

- None.

Future Suggestions:

- Add a small local fixture test for parsing AI JSON rankings.
- Add a no-email flag to simplify repeated AI integration tests.
- Add optional report styling for AI conviction columns.

### 2026-07-10 - Version 0.2.1

Files Modified:

- `config.py`
- `ai_analysis.py`
- `run_screener.py`
- `send_email.py`
- `.gitignore`
- `README.md`
- `PROJECT_GUIDE.md`
- `CHANGELOG.md`

Reason:

- Align AI configuration, prompt scope, and secret-handling behavior with the production project rules.

Changes:

- Centralised AI, debug, and email enablement settings in `config.py`.
- Set `ENABLE_AI_COMMENTARY`, `AI_MODEL`, `AI_MAX_TICKERS`, `AI_MAX_OUTPUT_TOKENS`, `AI_TEMPERATURE`, `DEBUG`, and `EMAIL_ENABLED` in configuration.
- Limited AI analysis to a maximum of 15 Top Action List stocks even if configuration is accidentally raised.
- Reduced AI prompt input to Market Status, Top Industries, and compact Top Action List fields only.
- Added Support Signal to candidate rows so AI commentary can reference support context without receiving unnecessary data.
- Changed missing OpenAI key behavior to display only `OPENAI_API_KEY not found.`
- Removed raw exception text from AI commentary failures to avoid leaking sensitive details into reports or emails.
- Stopped printing the Gmail address in email success and email test console output.
- Added broader credential-file ignore patterns to `.gitignore`.
- Updated README and project guide to reflect centralised configuration and the compact AI prompt boundary.

Impact:

- Existing screening, ranking, exports, and email flow are preserved.
- AI remains outside the stock-selection path.
- Secret-handling is stricter and avoids exposing credential-derived values in console output, reports, or email bodies.
- AI cost control is stronger because the prompt cannot exceed 15 Top Action List stocks.

Breaking Changes:

- None.

Future Suggestions:

- Add automated tests that assert AI prompt payloads never include full-universe or full-candidate data.
- Add a command-line flag to temporarily disable email without editing `config.py`.
- Add structured logging with secret redaction for scheduled runs.

### 2026-07-10 - Version 0.2.0

Files Modified:

- `README.md`
- `PROJECT_GUIDE.md`
- `CHANGELOG.md`
- `.env.example`
- `.gitignore`
- `requirements.txt`
- `ai_analysis.py`
- `run_screener.py`
- `send_email.py`

Reason:

- Add long-term project documentation, AI analysis support, secure API key handling, and environment-variable loading.

Changes:

- Created full README with setup, usage, folder structure, environment variables, Task Scheduler setup, email automation, AI commentary behavior, and daily workflow.
- Created project guide documenting Stage 2, risk management, industry ranking, AI, and project design philosophy.
- Created changelog to track future modifications.
- Added `.env.example` for OpenAI and Gmail configuration.
- Added `.gitignore` entries to prevent secret `.env` files from being committed.
- Added optional `python-dotenv` and `openai` dependencies to `requirements.txt`.
- Added `ai_analysis.py` with `load_openai_api_key()`, `build_ai_prompt()`, and `generate_ai_commentary()`.
- Integrated AI commentary into Markdown, HTML, and email summary reports after the Top Action List is generated.
- Added `.env` loading to `send_email.py` while preserving existing Windows environment variable support.
- Escaped AI commentary in HTML output.

Impact:

- Existing deterministic screening behavior is preserved.
- AI cannot affect stock selection because it only receives the Top Action List after screening.
- Missing AI dependencies, missing API keys, or AI request failures do not stop report generation.
- Email can now use either Windows environment variables or a local `.env` file.

Breaking Changes:

- None.

Future Suggestions:

- Add tests around AI prompt boundaries to prove the full universe is never passed to AI.
- Move optional AI enablement to environment variables or command-line flags.
- Add a dry-run mode that exports reports without sending email.
