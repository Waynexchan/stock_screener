# Point-in-Time Research Architecture

This layer is research-only. It is not imported by the production screener and may write only below `research/output/`.

## Dependency map

```text
durable adjusted historical OHLCV + point-in-time universe membership
  -> validated bars sliced to date T
  -> point-in-time features (FEATURES only)
  -> deterministic MODEL_0 signal after the close of T
  -> earliest entry at the first available session after T
  -> conservative stop/time/optional-target exit simulation
  -> initial-risk trade result in R + MFE_R + MAE_R
  -> chronological position-capacity simulation
  -> expectancy, profit factor, drawdown, exposure, and uncertainty metrics
  -> fixed WITH/WITHOUT or predeclared bucket comparison
```

Outcome labels are created only after feature records are frozen:

```text
FEATURES: signal_date, data_as_of, price/volume, tradability, Stage 2, structural stop
OUTCOMES: next-session entry date, future 5/10/20/40-session return, MFE, and MAE
```

Feature construction rejects columns beginning with `future_`. Every feature call slices the supplied history to `index <= signal_date` before invoking a calculation.

## Production-function reuse audit

| Production capability | Research use | Reason / constraint |
|---|---|---|
| `run_screener.add_indicators` | Reused behind an as-of slice | Rolling/shift calculations are causal when the input is first limited to date T. |
| `decision_system.calculate_recent_rs_frame` | Candidate for the next experiment | It accepts `as_of`, but its cross-section must contain only point-in-time universe members. Not used by MODEL_0. |
| `decision_system.construct_trade_plan` | Potential later reuse | It accepts `as_of`; it is excluded from MODEL_0 because its setup-specific logic is not part of the minimal baseline. |
| `decision_system.calculate_reward_risk` | Pure helper candidate | It is deterministic, but its production 2R threshold is not a MODEL_0 alpha gate. |
| `decision_system.market_regime_from_metrics` | Potential later reuse | Only safe after all component metrics are reconstructed at T. Not used by MODEL_0. |
| `decision_system.qualify_industries` and `sister_stock_confirmation` | Not currently usable for historical claims | They require point-in-time classifications and member cross-sections that are unavailable. |
| `run_screener.passes_filters` | Not used by MODEL_0 | It combines the intermediate trend with ADR, distance, and extension thresholds, making it too broad for the deliberately minimal baseline. |
| `run_screener.download_price_histories` | Not a research archive | It requests a rolling current period from Yahoo with `auto_adjust=True`; it does not preserve source/as-of history, delisted coverage, or membership. |
| `run_screener.build_universe` / `load_universe` | Not point-in-time safe | They construct/reuse the current listed universe, not historical membership. |
| `run_screener.screen_stocks`, candidate/category helpers, score, canonical production decision | Not used | They contain production filters, current metadata, scoring, and final-decision semantics explicitly excluded from this task. |
| Forward snapshots | Evidence/reconciliation only | Three recent signal-date bundles cannot substitute for raw multi-year OHLCV and historical universe data. |
| Completed-trade journal helpers | Conceptually compatible | Current journal has no completed trades and does not provide a research universe; research metrics therefore use isolated reusable implementations. |

## MODEL_0 baseline

MODEL_0 includes only:

- adjusted and validated OHLCV;
- minimum price of USD 10 and 50-session average volume of 500,000, matching the existing basic tradability policy but stored in research configuration;
- intermediate uptrend: `Close > MA50 > MA150 > MA200` and MA200 above its value 20 sessions earlier;
- a signal on the first false-to-true eligibility transition after the close;
- trailing 20-session low as the structural initial stop;
- entry at the next available session open;
- normalized USD 587 initial-risk sizing;
- stop exit or time exit after 40 sessions; no default profit target.

It excludes Recent RS, industry qualification, sister-stock confirmation, VCP, pullback quality, complex setup scoring, candidate Final Score, market regime, and AI commentary as alpha filters.

These are research assumptions, not production changes and not evidence that the baseline is profitable.

## Execution semantics

- An EOD signal on T cannot enter on T; the first bar with a date greater than T is eligible.
- Entry and exit slippage default to 5 basis points each; commissions default to zero and are configurable.
- A later open below the stop exits at that open, less exit slippage.
- A later open above an optional target fills at the target by default, avoiding favorable gap credit.
- If stop and target are both touched in one bar, the stop is assumed first.
- MODEL_0 has no target and exits at its stop or the 40th available session close.
- Gross P&L uses reference market prices; `costs` contain modeled entry/exit slippage and commissions; net P&L and realised R are after costs.
- MFE_R is non-negative and MAE_R is signed non-positive, both normalized by initial risk per share.
- Historical initial-risk R is separate from production current giveback/effective-open-risk calculations.

## Isolation and reproducibility

`scripts/verify_research.ps1` hashes production source/config, Daily Watchlist outputs, email summary, history, portfolio/trade data, and forward snapshots before and after the research command. Any addition, removal, or content change fails verification.

Every run records run ID, UTC timestamp, Git commit and dirty flag, research-config hash, experiment ID, data period, universe definition, execution assumptions, feature configuration, seed, research label, and known limitations.

Generated artifacts live under `research/output/` and are ignored by Git. The command rejects output paths outside that tree.

## Future Recent RS experiment

`research/experiments/recent_rs.json` predeclares 0–50, 50–60, 60–70, 70–80, 80–90, and 90–100 buckets over 5/10/20/40-session horizons. It is prepared but not run. No threshold search or production promotion is authorised.
