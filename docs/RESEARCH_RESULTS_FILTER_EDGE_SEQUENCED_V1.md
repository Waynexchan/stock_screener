# FILTER_EDGE_SEQUENCED_V1 results

## Decision

**REJECT** the exact legacy hard-filter matrix as a source of demonstrated
alpha. No production rule changed. The useful sequencing conclusion is that
filter quality must be measured before a fixed-2R portfolio is allowed to hide
almost every signal, and portfolio concentration must then be tested as a
separate risk overlay.

This is reused, survivorship-, earnings-schedule-, and classification-biased
research. There is no untouched holdout. The preregistration was frozen at
`42ea515`, its provenance at `f924b78`, and the clean corrected run used
`c8f1692bfd5edfbecd12c384730967e226dae844`.

## Why the earlier portfolio had so few transactions

The opportunity sample is large. For each variant, signals were simulated with
the same next-session execution and exit, then reduced to one open episode per
ticker. No cross-stock heat, position, or industry limit was used at this
stage.

| Period | After earnings blackout | Executable | Non-overlapping ticker episodes | Earlier fixed-2R portfolio trades |
|---|---:|---:|---:|---:|
| 2017-2023 development | 25,456 | 25,413 | 14,083 | 124 |
| Reused 2024 | 3,759 | 3,755 | 2,101 | 12 |
| Reused 2025 | 3,764 | 3,757 | 2,295 | 13 |

The drop from 25,413 executable development candidates to 124 portfolio trades
was therefore a capacity effect, not a small input sample. At 1R per trade,
fixed 2R heat normally permits only two simultaneous positions. A daily signal
count also overstates independent evidence, so 11,330 overlapping same-ticker
development signals were removed before assessing trade quality.

## Individual filter audit before portfolio capacity

The values below are expectancy changes versus the same-period unfiltered
opportunity baseline, in R per episode. Baseline expectancy was 0.155R / 0.300R
/ 0.094R across development / reused 2024 / reused 2025.

| Frozen filter proxy | Label | Expectancy delta: dev / 2024 / 2025 |
|---|---|---:|
| Dual RS | MIXED | -0.085 / -0.089 / -0.037 |
| Extension limits | MIXED | -0.002 / +0.002 / -0.008 |
| Strong industry | RISK_QUALITY_SUPPORT | +0.010 / +0.027 / +0.150 |
| Pivot near price with low supply | RISK_QUALITY_SUPPORT | +0.011 / +0.087 / +0.106 |
| Breakout demand | INCONCLUSIVE_SPARSE | -0.045 / -0.147 / +0.258 |
| SPY above SMA50 | MIXED | +0.015 / -0.048 / +0.080 |
| Recent RS >=70 | MIXED | -0.088 / -0.027 / -0.040 |
| Long-term RS >=75 | MIXED | -0.107 / -0.109 / -0.016 |
| Volume ratio >=0.30 | MIXED | +0.000 / +0.003 / -0.002 |
| ADR 1%-10% | MIXED | -0.004 / +0.007 / +0.003 |
| Rolling beta >=0.8 | MIXED | +0.016 / -0.116 / -0.060 |
| Exclude Utilities | MIXED | -0.000 / -0.017 / -0.015 |
| MarketSmith-style proxy >=80 | MIXED | -0.105 / -0.084 / +0.071 |
| RS proxy rising over 21 and 63 sessions | MIXED | -0.051 / +0.264 / +0.015 |
| RS line leads price high | INCONCLUSIVE_SPARSE | -0.133 / +0.459 / -0.089 |
| Stock within industry >=80 | MIXED | -0.046 / -0.012 / +0.005 |
| Accelerating industry breadth | MIXED | -0.060 / +0.007 / +0.256 |
| Up/down volume >=1.25 | MIXED | -0.009 / +0.051 / +0.059 |
| Base duration and depth | MIXED | +0.006 / +0.007 / -0.137 |
| Contraction plus volume dry-up | MIXED | +0.006 / +0.083 / +0.143 |
| Shakeout/reclaim | MIXED | +0.022 / +0.131 / -0.097 |
| Early base-stage proxy | MIXED | -0.022 / +0.271 / -0.072 |

No individual filter or combination achieved `ALPHA_SUPPORT`: every
development calendar-month block-bootstrap lower confidence bound failed to
clear zero. Strong industry and pivot/supply received only
`RISK_QUALITY_SUPPORT`. Strong industry improved profit factor in all three
periods and MAE/MFE in two; pivot/supply improved profit factor and MAE in all
three but reduced average MFE. Both results retain only 14%-32% of baseline
episodes and use reused data, so they are ranking hypotheses, not validated
hard gates.

The present RS thresholds, beta exclusion, Utilities exclusion, early-base
rule, and breakout conjunction have no support as hard alpha filters. This does
not establish that the underlying continuous features are useless; it says the
tested binary cutoffs did not provide robust incremental value.

## Combination and leave-one-factor-out audit

Six of 80 variants received `RISK_QUALITY_SUPPORT`. Five also passed the frozen
component leave-one-out rule and the maximum-three-component rule:

| Candidate | Dev / 2024 / 2025 expectancy | Leave-one-out periods | Earlier portfolio shortlist |
|---|---:|---|---|
| Strong industry | 0.165 / 0.327 / 0.244 | industry 3/3 | No |
| Pivot/supply | 0.166 / 0.387 / 0.199 | pivot 3/3 | No |
| Extension + pivot/supply | 0.166 / 0.393 / 0.205 | extension 2/3; pivot 3/3 | No |
| Pivot/supply + SPY/SMA50 | 0.189 / 0.366 / 0.227 | market 2/3; pivot 3/3 | No |
| Extension + pivot/supply + SPY/SMA50 | 0.188 / 0.373 / 0.234 | extension 2/3; market 2/3; pivot 3/3 | No |

None had supporting fixed-2R portfolio evidence from the already frozen prior
audit, so sequential-plus-portfolio support was zero. SPY/SMA50 and extension
remain exposure/risk hypotheses rather than stock-selection alpha.

## Maximum two simultaneous positions per industry

The comparison used only rows with a known, non-blank current industry on both
sides. Coverage was 66.12% / 62.97% / 62.25%. Missing classifications were
8,624 / 1,392 / 1,421 signals, and the labels were current rather than
effective-dated, so the result is classification-biased.

| Period | Risk per trade | No-cap return / DD / trades | Cap-2 return / DD / trades | Cap rejections |
|---|---:|---:|---:|---:|
| Development | 1.0R | 61.13% / 9.07% / 128 | identical | 0 |
| Reused 2024 | 1.0R | 11.17% / 7.70% / 12 | identical | 0 |
| Reused 2025 | 1.0R | 0.61% / 3.65% / 15 | identical | 0 |
| Development | 0.5R | 61.73% / 7.63% / 255 | 53.27% / 7.63% / 262 | 3 |
| Reused 2024 | 0.5R | 3.96% / 4.67% / 27 | identical | 0 |
| Reused 2025 | 0.5R | 3.33% / 4.20% / 32 | identical | 0 |

With fixed 2R heat and 1R trades, a cap of two per industry is mathematically
redundant because only two positions can be open in total. At 0.5R per trade it
can bind, but it did so only three times in development, changed the later
capacity path, reduced return by 8.46 percentage points, and did not improve
drawdown. It had no effect in either reused period. The cap may still be a
declared diversification control, but this test does not establish alpha or
drawdown benefit. If the intended rule is that two total portfolio positions
must never be from the same industry, the relevant constraint is cap one, not
cap two.

## Research implication

Do not add or stack more historical hard thresholds. The next valid test is a
small prospective candidate-order experiment using newly arriving data:

1. default deterministic order;
2. MarketSmith-style proxy rank;
3. industry-strength rank;
4. setup/pivot rank;
5. volume-quality rank;
6. one frozen composite plus leave-one-feature-out neighbors.

Apply the portfolio heat and declared industry constraint only after comparing
the one-factor ranks. Do not use 2017-2025 again to choose weights or cutoffs.
Point-in-time fundamentals, historical listing/delisting membership,
effective-dated industry, and point-in-time earnings schedules remain required
before testing fundamental acceleration.

## Audit

The clean run produced 240 opportunity rows, 80 variant decisions, 22
individual-filter summaries, 12 concentration rows, and 240 episode ledgers.
Counts reconciled; there were zero same-ticker overlap, frozen-boundary,
earnings-blackout, heat, position, industry-cap, or missing-mark violations.
The industry cap never exceeded two positions. Production and the immutable
forward journal were unchanged. Generated artifacts are under
`research/output/filter_edge_sequenced_v1/` and are intentionally untracked.
Focused research verification passed 128 tests, the expected data-readiness
block, and production isolation. Full verification passed 317 pytest tests, 118
legacy unittest tests, and every integration, invariant, offline dry-run, and
semantic-validation stage.
