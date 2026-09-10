# Historical Data Readiness

Audit date: 2026-09-10. This audit used only durable local files and performed no download.

Overall assessment: **NOT_READY**

Required label for any run that substitutes currently observed symbols for historical membership: **SURVIVORSHIP-BIASED RESEARCH**

| Data area | Status | Verified local state |
|---|---|---|
| Price history | NOT_READY | No durable long-form multi-symbol OHLCV research dataset exists. `.yfinance_cache` contains cookie/timezone databases, not price bars. Earliest/latest reliable research dates are therefore unknown. |
| Universe history | NOT_READY | `universe.csv` is one current snapshot of 1,840 unique symbols, not dated historical membership. |
| Delisted stocks | NOT_READY | No archived delisted membership or return history exists. |
| Sector/industry history | NOT_READY | `sector_industry_cache.csv` has 1,069 current mappings but no effective-date history. The current `universe.csv` itself has zero known sector/industry values. |
| Market-cap history | NOT_READY | The current universe has zero known market-cap values and no historical series. |
| Benchmark history | NOT_READY | Production downloads SPY/QQQ on demand; no durable benchmark archive exists. |
| Corporate actions | PARTIALLY_READY | Production asks Yahoo for auto-adjusted bars, but no split/dividend/delisting ledger is stored. |
| Split adjustment | PARTIALLY_READY | The research loader can consume provider-adjusted bars or apply an Adj Close ratio, but the local repository cannot independently audit splits. |
| Dividend adjustment | PARTIALLY_READY | Adj Close may include dividends, but dividend and split effects cannot be separated without an action ledger. |
| Forward snapshots | PARTIALLY_READY | Three candidate bundles cover signal dates 2026-09-04, 2026-09-08, and 2026-09-09 with 159 total candidate rows. They are forward evidence, not raw historical bars. |
| Completed trades | NOT_READY for inference | The journal schema exists but contains zero completed trades. |

## Bias classification

- **SURVIVORSHIP BIAS — HIGH:** no historical universe or delisted-symbol coverage.
- **LOOK-AHEAD BIAS — controlled by engine, not by provenance:** feature code slices bars at T and tests mutate future bars, but any supplied dataset still needs source/as-of verification.
- **CLASSIFICATION BIAS — HIGH:** historical sector/industry classifications are absent.
- **DATA AVAILABILITY BIAS — HIGH:** local evidence is limited to a current universe and three recent forward dates.

## Gate conclusion

The repository cannot currently support a trustworthy five-to-ten-year universe backtest. MODEL_0 therefore produces null empirical metrics and `BLOCKED_DATA_NOT_READY` unless a user explicitly supplies historical OHLCV and opts into a clearly labelled survivorship-biased engineering run. Such a run cannot validate a filter.

Readiness requires, at minimum, durable adjusted OHLCV and benchmark histories, point-in-time universe membership including delistings, source/as-of metadata, and corporate-action provenance. Industry, sister-stock, and market-cap experiments additionally require effective-dated historical classifications and market cap.
