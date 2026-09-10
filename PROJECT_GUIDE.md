# Project Guide

## Daily Trading Decision Boundary

The project targets long-only momentum swings lasting several days to under two
months. Recent market-relative behaviour is primary; long-term RS is structural
context and cannot substitute for missing Recent RS. One deterministic engine
classifies each canonical ticker as `FULL`, `HALF`, `WATCH`, or `NO TRADE`
before AI receives validated fields. Report generation and sizing consume that
record and cannot recalculate or promote the decision.

Portfolio Heat is effective open risk including an overnight gap-risk floor.
Market Regime controls maximum Heat and new-risk permission. AI cannot override
these limits, rule confirmation, missing data, or a blocking reason. Technical
rotation and breadth describe price behaviour, not institutional fund flows.

## Project Philosophy

The goal is to help a Stage 2 swing trader review the market in under 10 minutes.

This project is not designed to predict the market. It is designed to identify high-probability opportunities that deserve human chart review.

The screener favours deterministic rules, repeatable outputs, and focused daily workflow over complex prediction systems.

## Stage 2 Philosophy

Stage 2 is used because sustained advances usually occur after a stock has moved out of a base and into an organised uptrend. The project therefore looks for price above key moving averages, moving average alignment, a rising 200-day moving average, proximity to highs, and sufficient liquidity.

Trend is important because it reduces the number of structurally weak stocks under review. A trader still needs discretion, but the screener should start from stocks already showing evidence of institutional demand.

Relative Strength matters because the best opportunities often come from stocks outperforming the broader universe before they become obvious. The project uses a MarketSmith-style percentile ranking approximation based on weighted 3-month, 6-month, and 12-month performance to prioritise leadership. This is not the proprietary MarketSmith RS Rating formula, but it follows the same practical objective: focus review on stocks outperforming most of the market.

RS Trend is used to find new leadership. The screener compares today's weighted RS percentile with the same calculation roughly 21 trading days earlier. Improving and Emerging Leader labels help identify stocks moving into leadership, while Weakening and Fading labels reduce review priority for names losing relative momentum. This remains deterministic and does not predict future price.

## Risk Management Philosophy

ATR is used because volatility differs meaningfully between stocks. A fixed percentage can make a calm stock look acceptable while underestimating risk in a volatile stock, or reject a volatile leader that is behaving normally for its own range.

Fixed extension percentages were removed from the core pullback quality model because they are too blunt. The current design measures distance from key moving averages in ATR units so extension is judged relative to the stock's own volatility.

Extension is measured using volatility because a stock two ATRs above support is very different from one six ATRs above support, even when the percentage move looks similar. This supports better risk/reward review.

Price-data sanity is required before interpreting technical signals. A stock with a latest close that is inconsistent with recent medians or an extreme one-day move may reflect a data adjustment problem rather than a tradable setup. The screener rejects obvious anomalies before candidate generation so bad data cannot become a high-priority watchlist item.

## Industry Ranking Philosophy

The system is designed for a discretionary one-to-two-month holding period. Recent RS therefore prioritises 20-day market-relative performance, with 60-day performance confirming durability. Five-day relative performance is used mainly for acceleration and timing, while 126-day and the existing long-term RS model remain structural confirmation rather than the dominant current-opportunity signal.

Industry Momentum and Industry Leadership are separate concepts. Momentum measures recent median market-relative returns, acceleration, and participation across the full eligible liquid universe. Leadership measures durable long-term RS, Stage 2 breadth, proximity to highs, leader quality, and normalised candidate breadth. The final rank weights Momentum at 65% and Leadership at 35%.

Median relative returns are the primary industry measure because they resist distortion from a single gap-up or extreme winner. Averages remain visible as supporting context. Formal industries require at least three eligible members; smaller groups are shown separately as isolated or emerging leaders.

Technical rotation, relative momentum, and breadth improvement are price-based observations. They are not evidence of fund flows, capital inflows, or institutional money flow unless a genuine flow dataset is added.

Industry leadership matters because strong stocks often cluster. One isolated leader can work, but multiple strong candidates in the same group can indicate broader institutional sponsorship.

Leadership rotates between industries. Ranking industries helps the trader focus on improving market-relative performance instead of treating every stock as an unrelated opportunity.

Industry context is important, but it cannot rescue a weak individual setup. The screener therefore displays separate Industry Momentum, Industry Leadership, and Final Industry scores instead of one opaque strength score.

The review workflow is quality-first. The rule engine first identifies individual stocks with Stage 2 structure, liquidity, Relative Strength of 75 or higher, constructive setup behavior, and acceptable risk/reward. Industry strength is then used to prioritise leadership groups, not to rescue weak individual charts. Market status provides context for aggressiveness, but it does not override stock quality or the deterministic setup rules.

Review priority must separate high-quality setups from merely valid setups. Scores should not easily saturate at 100. Tightness, VCP quality, confirmation signals, and volume context are used to distinguish immediate review candidates from quiet watchlist names.

The Top Action List is intentionally stricter than the broader candidate lists. It is the daily human-review shortlist, so valid but noisy setups should remain visible in Daily Focus or their category section instead of occupying the first list. `Review Tier` and `Noise Filter Reason` make this explicit: the rule engine still finds the setup, but the report tells the trader whether it deserves immediate chart review or should wait. Poor VCP, loose action, wait-only actions, weak pullback quality, thin confirmation volume, far support distance, and isolated industry context are treated as reasons to keep a stock out of the first-review list even when the underlying Stage 2 trend remains valid.

Reports should be optimised for scanning. The HTML report starts with an executive summary panel so the trader can immediately see the count of Top Action candidates, confirmed setups, emerging leaders, caution rows, and price warnings. A Daily Review Plan then translates the deterministic tiers into an operating sequence: open `Review Now` first, review `High Priority Watch` second, use Daily Focus as a tracking pool, and avoid forcing trades when no clean first-review setups exist. Valid reports also append a local summary-history snapshot so the next report can compare daily changes in Top Action tickers, Top Industries, and setup-quality counts. A recent summary trend table and mini bar view helps the trader judge whether the current list is arriving in an improving, deteriorating, or mixed opportunity environment. This improves review reliability without changing deterministic selection rules or pretending to predict market direction. Visual flags for confirmed setups, emerging leadership, weak VCP/tightness, extension risk, and price-data warnings then help the trader decide which charts to open first.

Report layout development should be testable without market data. `--report-preview` rebuilds a local HTML preview from last-known-good report data and summary history so visual/report changes can be inspected without Yahoo Finance downloads, OpenAI calls, email sending, or history mutation.

Industry rotation gets more credit when several stocks in the same known industry are also producing valid setup candidates. This is stronger evidence than a single isolated stock because leadership groups often move together when institutional money is rotating into them.

Unknown industry metadata is not treated as an industry group. Stocks with missing metadata may still appear when their individual Stage 2 quality is strong, but `Unknown` cannot appear in Top Industries, cannot receive an Industry Rank, and cannot earn hot-industry priority credit. This avoids mistaking missing data for institutional rotation.

## AI Philosophy

AI must not select stocks.

Rule-based screening always selects stocks. The AI module analyses only the Top Action List after screening is complete.

AI only:

- Prioritises
- Summarises
- Explains

AI must not:

- Analyse the full universe
- Add tickers not already selected
- Override deterministic screening
- Make buy or sell decisions
- Predict market direction
- Override a confirmed rule-based setup or the deterministic Review Tier order

The human trader always makes the final decision.

## Project Design Principles

- Keep logic deterministic.
- Minimise false positives.
- Optimise for long-term expectancy instead of prediction.
- Preserve modular code.
- Avoid unnecessary complexity.
- Optimise for daily workflow.
- Keep AI outside the stock-selection path.
- Preserve backward compatibility whenever possible.
- Keep reports readable without requiring external services.
- Fail gracefully when optional services such as email or AI are unavailable.

## Current Architecture

`run_screener.py` owns the main workflow:

1. Read SPY and QQQ for market status.
2. Load or rebuild the stock universe.
3. Download price history.
4. Apply Stage 2 filters.
5. Calculate Relative Strength.
6. Build category candidates.
7. Rank industries.
8. Dedupe and build the Top Action List.
9. Generate optional AI commentary from the Top Action List.
10. Export CSV, Markdown, HTML, and email summary reports.
11. Append local summary history after successful valid report export.
12. Call `send_email.py`.

`ai_analysis.py` is intentionally separate so AI remains an optional report-layer assistant.

`send_email.py` is separate so SMTP concerns do not complicate screening logic.

`config.py` keeps deterministic screening thresholds, AI settings, email enablement, and debug flags centralised. Configuration should not be hardcoded elsewhere because this project is intended to remain maintainable as a long-term production assistant.

The AI prompt is deliberately narrow. It receives only Market Status, Top Industries, and the Top Action List, with each stock reduced to the fields needed for prioritisation, including RS Score and RS Trend. This keeps cost controlled and protects the rule-based selection boundary.

AI ranking is a review aid, not a stock-selection system. `AI Conviction Score` describes how well a Top Action List ticker matches the defined Stage 2 swing trading system today. It is not a probability of profit, not a buy signal, and not a replacement for chart review. `AI Priority Rank` and `AI Reason` exist to reduce review time by helping the trader decide what to inspect first.

AI commentary must state both the bull case and the concern. A generic positive summary is not useful for discretionary review. The AI output therefore asks for the main positive, the main weakness, and the confirmation the trader should verify manually.

AI testing is separated from the full Yahoo Finance workflow because OpenAI connectivity and JSON-ranking behavior should be diagnosable without downloading thousands of tickers, exporting reports, or sending email. `test_openai.py` verifies only the Responses API connection, while `--ai-test` verifies the real AI analysis module using fixed mock Top Action List rows. This keeps debugging fast, lowers provider cost, prevents accidental report churn, and preserves the rule that AI never participates in market-wide screening.

## Data Reliability Philosophy

An empty report caused by missing Yahoo Finance data is not a valid market conclusion. The project must distinguish "no stocks passed the rules" from "the data source failed." A normal report is exported only after universe size, market data, and price download success rate pass validation.

The universe cache is treated as a last-known-good asset. Refreshes are built into a temporary file and validated before replacement so a partial Yahoo failure cannot overwrite a usable cache. Successful reports are also saved as last-known-good outputs so a later data failure cannot replace a useful watchlist with an empty one.

Universe construction deliberately separates listing discovery from liquidity validation. NASDAQ Trader listed-symbol files define the raw common-stock universe, while Yahoo Finance historical price data is used only to verify price and volume liquidity. Company-profile data such as market cap, sector, and industry is useful when reliable, but it must not be a single point of failure for rebuilding the tradable universe. The USD 500m market-cap policy is currently shown as `NOT ENFORCED` because complete reliable metadata is not available; missing values are never fabricated.

Sector and industry metadata is enriched after deterministic filtering through a local cache and best-effort metadata lookup. Every run reports mapped/unmapped counts, coverage percentage, and cache date. Coverage below the configured minimum disables high-confidence industry qualification and sister-stock confirmation rather than extrapolating from a partial subset.

Runtime is also part of reliability. Yahoo Finance calls are bounded by per-call timeouts, finite retry attempts, and a maximum full-run duration. If the screener cannot obtain enough data inside those limits, it should produce a clear data-failure result and exit normally. Lightweight `--data-test` and universe-only `--refresh-universe` modes exist so data-source issues can be diagnosed without repeatedly sending emails or running the full trading workflow.

## Future Roadmap

- Add unit tests for ranking, category selection, and AI prompt boundaries.
- Add a no-email command-line flag for local dry runs.
- Add a no-network report mode that reuses cached data.
- Add richer market regime context.
- Add optional portfolio/watchlist exclusion lists.
- Add historical outcome tracking for candidates.
- Add stricter logging for scheduled runs.
- Add alternate market data provider fallback if Yahoo Finance remains unavailable.
