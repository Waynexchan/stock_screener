# SUPERPERFORMANCE_PATHS_V1 results

Historical decision: **REJECT**

Production effect: **NONE**

Research label: **SURVIVORSHIP- AND EARNINGS-SCHEDULE-BIASED RESEARCH; ALL PERIODS REUSED; NO UNTOUCHED HOLDOUT**

## Hypothesis

Separately defined causal breakout, pullback, tight-base, and short-history
leader paths might retain more large winners than either the generic MODEL_0
transition or one overconstrained conjunction. A blue-sky breakout was also
tested as an exception to the requirement for an observed resistance level at
least 2R above the signal close.

## Evidence

The clean run used commit `fddb565f05eda65a6ea641167a5df9c70e6db691`
after preregistration commits `f6b9741`, `6579c5a`, and `4ab979a`. It reported
all 18 frozen variants in all three periods. No variant entered the frozen
cross-stage shortlist.

| Variant | Development return / DD / trades | Reused 2024 | Reused 2025 | Result |
|---|---:|---:|---:|---|
| MODEL_0 | 42.78% / 9.75% / 124 | 9.93% / 3.93% / 12 | 28.01% / 13.07% / 13 | Reference; 2025 outlier/risk failure |
| Observed-2R breakout | 4.86% / 2.61% / 5 | -1.10% / 1.18% / 1 | 0.82% / 2.34% / 4 | Far too sparse |
| Blue-sky breakout | 6.04% / 6.68% / 96 | -0.61% / 3.35% / 11 | 5.74% / 2.08% / 11 | Not stable |
| Quality breakout | 0.70% / 11.91% / 85 | 1.21% / 2.93% / 10 | 2.93% / 2.47% / 11 | Failed development |
| Tight-base breakout | -4.12% / 6.15% / 18 | 1.28% / 1.43% / 2 | -1.29% / 2.35% / 2 | Sparse and unstable |
| Constructive pullback | 39.37% / 11.72% / 133 | 8.89% / 3.09% / 11 | -12.21% / 16.06% / 20 | 2025 regime failure |
| Short-history leader | 15.21% / 4.66% / 48 | 6.07% / 1.28% / 8 | 13.16% / 5.46% / 7 | Mixed, underpowered |
| Multi-path + production RS | 47.10% / 12.45% / 116 | 12.85% / 4.47% / 10 | -5.74% / 9.49% / 17 | 2025 regime failure |
| Frozen superperformance rank | 12.98% / 24.10% / 123 | -0.09% / 5.39% / 12 | -9.14% / 11.31% / 16 | Rejected |

The observed-2R rule selected only 7, 1, and 5 signals. Adding the blue-sky
exception restored 6,315, 882, and 613 signals, but did not create stable
portfolio edge. This demonstrates that the mechanical observed-resistance
proxy is an extreme opportunity constraint; it does not prove that the
distinct production structural-R/R gate should be removed.

The short-history leader path was the only distinct entry path with positive
return, expectancy, and profit factor in all three periods and with low
drawdown. Its return/drawdown exceeded MODEL_0 in reused 2024 and 2025, but it
accepted only 48, 8, and 7 trades. In reused 2025, SNDK contributed 11.93R and
77.25% of positive P&L; total P&L excluding the largest winner was only 1.23R.
The path measures 90-219 valid sessions in this archive, not verified IPO age.
An accepted-trade audit found archive ages of 128-313 calendar days and no
missing first date, but ticker-history and listing provenance remain imperfect.

The frozen RS and superperformance rankings did not add value. RS ranking
reduced later-period quality-breakout returns, and the composite rank materially
worsened the multi-path portfolio. A 2R-activated SMA20-minus-1ATR stop improved
blue-sky return only in reused 2025; it reduced development return and made no
difference in 2024.

## Audit

- MODEL_0 exactly matched `LEADER_COMPLETENESS_V2` on signal count, accepted
  trades, return, drawdown, expectancy, and profit factor in every period.
- 54 result rows, 1,984 accepted-ledger rows, and 38,141 equity rows reconciled.
- Zero signal/outcome-boundary, next-session-entry, duplicate-key,
  earnings-blackout, risk, heat, position, or missing-mark violations were
  found.
- Maximum reported initial heat was 2R and maximum concurrent positions was
  two under the shared fixed-2R allocator.

## Interpretation

The experiment rejects the exact 18-variant specification. It does not establish
that technical superperformance selection is impossible. Current-symbol Yahoo
history creates high survivorship bias; earnings dates are retrospective;
fundamentals, delistings, historical membership, effective-dated industries,
and historical manual decisions are missing. Every result period had already
been inspected in earlier research, so apparent stability is adaptive evidence
only.

The one justified follow-up is narrow: test whether the frozen short-history
leader path adds portfolio value to MODEL_0 under the same allocator, without
retuning its thresholds. That is a new experiment, not a revision of this
rejected result. Any positive result can be no stronger than `HOLD` until it has
newly arriving, point-in-time evidence.

## Decision

**REJECT.** Do not promote any V1 path, rank, target exception, or exit to
production. Preserve the short-history leader path as `RESEARCH_ONLY` for one
predeclared additive-sleeve test and future forward observation.
