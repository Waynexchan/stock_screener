# Project Changelog

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
10. Export reports and email the HTML watchlist.

## Current Features

- NASDAQ Trader universe construction.
- Yahoo Finance market data.
- Stage 2 trend filtering.
- Weighted Relative Strength scoring.
- ATR-based pullback and extension context.
- Industry Strength Score ranking.
- Top Action List.
- Daily Focus List.
- CSV, Markdown, HTML, and email summary output.
- Gmail SMTP email attachment support.
- Optional OpenAI commentary with secure API key loading.

## Current Version

Version: 0.3.3

## Roadmap

- Add automated tests for ranking and report generation.
- Add command-line flags for no-email and no-AI runs.
- Add historical tracking for watchlist outcomes.
- Add richer market and breadth context.
- Add optional exclusion lists.

## Changelog Entries

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
