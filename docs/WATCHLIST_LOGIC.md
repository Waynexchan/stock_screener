# Watchlist Logic

Production has one authoritative candidate pipeline:

1. Validate critical stock, market, price-freshness, and portfolio data.
2. Require primary edge: valid Recent RS and trend, setup, entry, structural
   stop, observed structural target, actual R/R of at least 2, acceptable timing,
   liquidity, and no overextension.
3. Classify Setup Integrity as `PASS`, `MARGINAL`, or `FAIL` from deterministic
   setup fields.
4. Apply market, drawdown, open-position, portfolio-heat, industry-heat, and
   theme-heat hard gates.
5. Treat incomplete industry, sister-stock, and volume confirmation as secondary
   confirmation only after primary edge has passed.
6. Produce exactly one `FULL`, `HALF`, `WATCH`, or `NO TRADE` record.
7. Size only authorised FULL/HALF decisions, then apply configured candidate
   industry/sector concentration limits.
8. Export the unchanged canonical decision to CSV, Markdown, HTML, email, and
   the immutable forward snapshot.

`FULL` is actionable now at no more than 1R. `HALF` is actionable now at no more
than 0.5R. `WATCH` is interesting but not ready, with 0R and zero shares.
`NO TRADE` has failed a true hard gate and also has 0R and zero shares. Sizing
cannot upgrade WATCH or NO TRADE.

Final Score ranks and summarises edge quality; it is not a universal 75-point
permission cliff. A sound early leader can be HALF below 75 when only secondary
confirmation is incomplete. A score above 75 cannot override missing Recent RS,
an invalid stop, a synthetic model 2R target, R/R below 2, stale data, or another
hard gate.

A Loose label alone is not a permanent rejection. A Loose Developing Base is
Setup Integrity FAIL under the current deterministic rule, however, and cannot
become actionable merely because portfolio capacity exists. PASS can support
FULL or HALF; MARGINAL can support HALF but never FULL; FAIL supports WATCH only
unless another hard gate makes it NO TRADE.

Industry qualification uses only known metadata and reports the full-universe
coverage. When coverage is below `MIN_METADATA_COVERAGE_PCT`, industry data is
marked incomplete and cannot silently grant qualification or sister-stock
confidence. The USD 500m market-cap threshold is currently `NOT ENFORCED`
because complete reliable values are unavailable.

Price freshness is evaluated against the latest completed regular US trading
session, including weekends and regular full-day US holidays. `PRICE_STALE_HOURS`
is retained only as a fallback when session evaluation cannot be completed.
A daily bar later than that completed-session date is treated as incomplete or
future-dated and cannot be actionable. Exceptional exchange closures are not
represented by the current calendar.

Before a valid production run is preserved, the row-level validator verifies
state/risk/share/actionability semantics and confirms that CSV, HTML, and email
carry the same canonical manifest. Only after that succeeds is a unique bundle
written under `output/forward_snapshots`; existing bundles are never overwritten.

AI sees validated records only. It can rank or describe them, but it cannot
change decisions, setup integrity, confirmation, R/R, risk, or shares.
