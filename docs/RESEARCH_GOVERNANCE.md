# Research Governance

> Intuition generates hypotheses. Data decides whether a filter deserves production use.

Research exists to test whether a strategy feature adds economically meaningful value over a simpler baseline. It must not silently alter the Daily Watchlist.

## Status and approval

Every material feature belongs in `research/filter_registry.json` as `UNASSESSED`, `RESEARCH_ONLY`, `VALIDATED`, `REJECTED`, or `CORE_RISK_CONTROL`.

- New hypotheses begin as `RESEARCH_ONLY`.
- Existing production presence does not qualify a feature as `VALIDATED`.
- `VALIDATED` requires empirical incremental evidence on development and validation samples, plus holdout/walk-forward evidence where practical.
- `CORE_RISK_CONTROL` is reserved for operational safety rules such as valid critical data, valid stops, freshness, maximum positions, portfolio heat, and drawdown controls. It is not an alpha claim.
- Production promotion is a separate, explicit user-approved task with regression tests and full verification.

## Required experiment definition

Before running an experiment, record:

- whether the work is prospective, retrospective, or hypothesis-generating;
- any previously viewed outcomes, periods, variants, charts, or summaries that
  could influence the specification or criteria;
- hypothesis and economic rationale;
- exact baseline and one controlled change;
- feature calculation and point-in-time availability;
- universe definition and survivorship-bias limitations;
- discovery/development, validation, and untouched holdout periods where practical;
- entry/exit, next-session execution, position overlap, portfolio constraints, and holding rules;
- fees, slippage, gaps, partial fills, and stop/target ambiguity policy;
- primary decision metric and minimum economically meaningful improvement;
- config, code, and data versions/hashes.

Never call a record preregistered if relevant outcomes were already observed.
Treat affected evidence as discovery or contaminated for that version, freeze
the resulting candidate before using genuinely unobserved validation evidence,
and disclose when no untouched evidence remains. Do not select thresholds using
validation or holdout results. If sample size cannot support a conclusion,
record the result as inconclusive.

## Frozen benchmark-only parameter families

The following heavily explored families are frozen and may be reused only as
declared benchmarks. Do not rerun optimization, threshold search, or combination
mining over them in a ranking experiment:

- initial-stop and fixed-target grids;
- fixed, earned, staircase, and drawdown exposure/heat grids;
- earnings-blackout combinations;
- SMA and ATR trailing-stop offsets;
- Recent RS hard thresholds; and
- hard-filter combinations.

New candidate-order research must hold these non-ranking conditions constant
across every arm. Reopening a family requires a new preregistration, new data,
and an explicit rationale; it is not part of `PORTFOLIO_RANKING_PHASE_A_V1`.

For `PORTFOLIO_RANKING_PHASE_A_V1`, the primary Phase B-shortlist metric,
minimum improvement, sample floor, development/validation windows, untouched
holdout, drawdown/profit-factor guardrails, and maximum shortlist size are
frozen in `research/experiments/portfolio_ranking_phase_a_v1.json`. The random
control cannot advance. Applying that gate may produce candidates for human
review only; it cannot automatically select a champion or authorize Phase B,
holdout access, or production promotion.

The production baseline and every challenger must independently meet the
preregistered mature-sample floor. Outcomes beyond a stage observation cutoff
must be censored rather than counted as mature, while positions still open at
the cutoff continue to consume portfolio heat. Current sector/industry mappings
cannot support a formal industry-ranking arm; formal execution must fail closed
until effective-dated classifications and their loader are verified.

## Required comparisons and metrics

Compare the candidate feature with a simpler frozen baseline. At minimum report:

- signal count;
- triggered trades;
- win rate;
- average win in R;
- average loss in R;
- expectancy in R after costs;
- profit factor;
- maximum drawdown in R;
- maximum favourable excursion (MFE);
- maximum adverse excursion (MAE);
- trade frequency;
- exposure;
- average holding period.

Also report period/regime stability, rejected-trade opportunity cost, overlapping-position effects, parameter sensitivity, and uncertainty/confidence intervals where the sample permits.

## Data integrity

- Use only information observable by the signal calculation time.
- Use point-in-time universe membership, prices, volume, classifications, market cap, corporate actions, and delistings where claims depend on them.
- Never use future data, backfilled classifications, or revised values without explicit labelling.
- Disclose survivorship bias whenever the source cannot control it; do not claim it away.
- Missing historical fields remain missing and may make the experiment invalid.
- Keep immutable raw inputs and experiment manifests separate from derived results.
- Do not rewrite forward snapshots after outcomes are known.

## Execution realism

Signals formed after a close cannot assume that close as a fill. Use realistic next-session eligibility and documented fill rules. Include slippage and fees. Handle gaps, partial fills, halts, and delistings conservatively.

When stop and target could both be touched without intraday ordering evidence, use a conservative documented policy or mark the trade ambiguous; do not select the favorable outcome.

## Evaluation sequence

1. Establish and freeze the simpler baseline.
2. Run discovery/development analysis.
3. Freeze the feature and threshold.
4. Evaluate on validation data.
5. Evaluate on an untouched holdout where practical.
6. Use walk-forward testing where practical.
7. Review economic significance, complexity, stability, drawdown, and data limitations.
8. Update the registry without fabricating missing statistics.
9. If evidence supports promotion, propose a separate production-change task.

## Decision rule

A filter must demonstrate economically meaningful incremental value over the simpler baseline, not merely a higher in-sample win rate. Value may include higher after-cost expectancy, improved payoff/profit factor, materially lower drawdown, or better capacity/exposure at comparable expectancy.

If results are similar, choose the simpler model. If evidence conflicts or is underpowered, keep the feature `RESEARCH_ONLY` or `UNASSESSED`. A rejected feature should remain documented so it is not repeatedly reinvented.
