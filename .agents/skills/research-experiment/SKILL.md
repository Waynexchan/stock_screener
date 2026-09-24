---
name: research-experiment
description: Govern systematic investment or trading research from prospective preregistration or disclosed retrospective assessment through point-in-time backtesting, separate validation, untouched holdout evaluation, robustness checks, forward testing, and production review. Use for domain-specific research, not ordinary software work, securities recommendations, brokerage actions, or automatic production promotion.
---

# Research experiment

Use this optional skill to make systematic investment and trading research auditable, reproducible where practical, and resistant to overfitting, look-ahead and survivorship bias, data leakage, selection bias, parameter mining, repeated-testing bias, unrealistic execution, and validation or holdout contamination. It governs research; it does not supply a strategy, recommend securities, place trades, connect brokerage accounts, or authorize production changes.

Keep four things distinct in every report: **hypothesis**, **evidence**, **interpretation**, and **decision**. State data limitations, biases, assumptions, and uncertainty. Research findings are evidence, not guarantees of future returns.

## Repository boundaries

`AGENTS.md` and `docs/RESEARCH_GOVERNANCE.md` remain authoritative. Before research work, read `docs/PROJECT_STATUS.md`, `docs/PROJECT_MEMORY.md`, `docs/DATA_READINESS.md`, the relevant experiment/config, and `research/filter_registry.json`.

- Every new strategy idea starts as `RESEARCH_ONLY`; never infer production approval from this skill.
- Keep research artifacts under `research/` and generated research results under `research/output/`. Do not let research fields gate or alter production decisions, risk, shares, reports, email, history, or forward snapshots.
- Respect the data-readiness gate. `BLOCKED_DATA_NOT_READY` is a valid result and is not performance evidence. Never claim point-in-time or survivorship-bias control that the data does not support.
- Use `powershell -ExecutionPolicy Bypass -File .\scripts\verify_research.ps1` for focused research verification and the project-required `powershell -ExecutionPolicy Bypass -File .\scripts\verify_project.ps1` before completing a meaningful repository change.
- A production promotion is a separate, explicitly authorized task through the canonical decision and verification paths. AI never becomes production decision authority.

## Governing rules

- Do not cherry-pick attractive results, hide failed experiments, or optimize for an appealing backtest.
- Do not begin parameter optimization before formalizing the hypothesis.
- Never describe a record created after outcome exposure as preregistered; disclose prior exposure and treat the work as retrospective or hypothesis-generating.
- Keep discovery, validation, and untouched holdout roles distinct. Do not repeatedly optimize against validation or holdout data, use the holdout as first validation, or silently reuse a contaminated sample.
- Do not claim causality from correlation or claim that a profitable backtest proves a strategy works.
- Do not equate statistical significance with tradability. Evaluate economic magnitude, execution, risk, capacity where relevant, and operational feasibility.
- Prefer reproducibility and simple, stable rules over unnecessary complexity or a sharp optimum.
- Track material variants and repeated tests; warn that parameter mining and repeated experimentation increase false-discovery and overfitting risk.
- Never modify production strategy logic during research unless a separate, explicitly authorized production-change workflow permits it. Never modify real trading accounts or place trades.

## 1. Formalize the investment logic

Translate the human-readable idea into a testable statement before inspecting any outcomes not already exposed or tuning parameters further. If prior outcomes have already been seen, do not pretend this ordering was followed; preserve and disclose their influence through Stage 2. Distinguish:

- economic or market intuition and expected mechanism;
- observable conditions and universe;
- entry and exit logic;
- holding horizon; and
- risk assumptions.

A useful conceptual form is: “When condition X occurs under regime Y, instruments satisfying Z may outperform over horizon H because mechanism M is expected to occur.” Identify unresolved ambiguity before testing; do not conceal discretionary choices behind parameters.

## 2. Preregister prospectively or disclose prior outcome exposure

First establish and record whether the researcher or agent has already seen
outcome data, result summaries, charts, selected variants, tuned parameters, or
other evidence that could have influenced the hypothesis or criteria. Unknown
prior exposure is a limitation; do not assume the work is prospective.

If relevant outcomes have already been seen, label the record **retrospective**
or **hypothesis-generating**, never preregistered. Record what evidence was
known, when it was seen, which data periods and variants were inspected, and how
that exposure may have influenced the specification. Treat exposed periods as
discovery or contaminated for the affected version. Freeze the candidate before
using genuinely unobserved validation evidence. If no untouched evidence exists,
state that limitation and do not present the assessment as confirmatory.

For prospective work, before inspecting outcomes, record the hypothesis, universe, signal, entry, exit, holding periods, portfolio construction and position sizing where applicable, benchmark, primary and secondary metrics, risk metrics, transaction costs, slippage, separate discovery, validation, and untouched holdout periods with planned sample sizes, temporal split and boundary controls, sample-status conventions, and stage-specific acceptance and rejection criteria. Assign an experiment ID and hypothesis version where practical. The primary metric and criteria must be chosen before results are known.

Use [RESEARCH_HYPOTHESIS.md](../../../templates/RESEARCH_HYPOTHESIS.md) when the project has no equivalent record. Preserve the original record. A material change to logic, inputs, universe, execution, metrics, periods, or criteria creates a new experiment or version rather than rewriting history.

## 3. Establish point-in-time data integrity

Before trusting results, inspect and document:

- point-in-time availability and future-information or target leakage;
- survivorship bias, historical universe construction, and delisted instruments where relevant;
- corporate actions, splits, and dividends where relevant;
- timestamp, timezone, release-time, and market-calendar correctness;
- missing, duplicate, or stale observations; and
- dataset provenance and version.

Never treat current index or universe membership as historical membership without evidence. State all known data limitations in the research report and explain how they affect interpretation.

For temporally ordered observations, place discovery before validation and validation before the untouched holdout. Keep observations and outcomes non-overlapping across both boundaries. Do not use an ordinary random split unless the research design justifies it and demonstrates that no future information can cross a boundary. Define sample membership from information-availability time and label/outcome end time, not row timestamp alone. Purge observations whose labels, holding periods, or derived windows cross either boundary, and apply an appropriate gap or embargo when feature lookbacks, forecast horizons, overlapping positions, publication delays, or repeated walk-forward folds could leak information. Record the sizes and rationale for these controls; do not assume adjacent date ranges are independent.

## 4. Define the backtest and execution model

Specify the complete causal sequence where applicable:

```text
signal information available -> eligibility and portfolio construction
-> capital allocation and position sizing -> earliest executable entry
-> fill assumption -> portfolio aggregation -> exit rule -> costs and slippage
```

Never fill at a price that was not knowable and tradable after the signal became available. A completed 10:00 bar cannot justify entry at that bar's 09:55 open; end-of-day information cannot justify execution earlier that day. Define timing, calendars, order/fill assumptions, transaction costs, slippage, liquidity or capacity constraints where material, and behavior for missing or untradeable observations.

Where applicable, also define initial capital and cash handling; instrument selection or ranking; allocation and position-sizing rules; long/short treatment and borrow availability/cost; leverage, gross/net exposure, concentration, and position limits; rebalancing, order netting, and capital reuse; concurrent positions and overlapping trades; and the method for aggregating instrument-level outcomes into portfolio returns. Apply compatible portfolio assumptions to the candidate and baseline. Do not infer these settings from signal rules or choose them after seeing outcomes.

## 5. Conduct discovery with a ledger

Use only the discovery sample for hypothesis exploration, feature investigation, threshold or parameter development, and failure analysis. Track every material variant, not only the winner. Record experiment ID, hypothesis/version, prospective or retrospective status and prior outcome exposure, parameters, code commit, dependency or environment version, immutable artifact identifier where available, dataset version, sample period and size, results, decision, and notes. Use [EXPERIMENT_LOG.md](../../../templates/EXPERIMENT_LOG.md) when no equivalent ledger exists.

Report the breadth of the search and any repeated use of the same data. Treat unexplained sensitivity and unusually successful isolated variants as warning signs.

## 6. Evaluate a separate validation sample

After discovery, freeze the selected candidate version before evaluating it on a separate validation sample. Validation is an intermediate out-of-sample check; it is not the untouched holdout. Compare **Candidate vs Baseline** on the same validation period and compatible assumptions.

Record the validation period, actual sample size, sample status, result, and decision. Use an explicit sample status such as `UNTOUCHED`, `EVALUATED_ONCE`, `CONTAMINATED`, or `UNAVAILABLE`, with an explanation when contaminated or unavailable. Record an inconclusive evaluation as the result, not as sample status. If validation evidence changes the strategy, parameters, universe, execution, metrics, or criteria, create a new version and do not present the used validation result as independent evidence for that revision. Where feasible, give the revised version a new untouched validation sample.

Advance to the untouched holdout only when the validation sample was not used to design the current version and the validation result meets the preregistered gate. If fresh validation evidence is unavailable, contaminated, or inconclusive, use `HOLD`, `REVISE`, or `REJECT` as appropriate instead of spending the holdout. Never use the untouched holdout as the first validation sample or as a substitute for missing validation evidence.

## 7. Preserve and evaluate the untouched holdout

Keep holdout data isolated from discovery, validation, and strategy development. Evaluate it only after the candidate specification is fixed and the separate validation result has been recorded. Compare **Candidate vs Baseline** on the same holdout period and compatible assumptions. Record the holdout period, actual sample size, status, result, and decision.

Do not repeatedly inspect holdout results and modify the strategy until it passes. If holdout evidence influences design, label the original holdout `CONTAMINATED` for the revised version. Treat the revision as a new experiment/version and, where feasible, give it new validation and untouched holdout periods. Never relabel a used sample as untouched.

## 8. Evaluate a balanced metric set

Do not judge a strategy from one metric. Select metrics appropriate to the design, including where relevant: sample size, mean and median return, win rate, payoff ratio, expectancy, cumulative return, drawdown, volatility, Sharpe-like risk-adjusted measures, maximum favorable and adverse excursion (MFE/MAE), turnover, exposure, benchmark-relative return, regime dependence, concentration, and tail outcomes.

For discrete trades, consider:

```text
Expectancy = P(win) x Average Win - P(loss) x Average Loss
```

A high win rate alone is not evidence of edge, and a tiny sample is not strong evidence. Report uncertainty and practical magnitude alongside statistical measures.

## 9. Test robustness

Before recommending a forward test, choose checks relevant to the hypothesis: nearby parameter values, alternate subperiods and market regimes, bull/bear/sideways or high/low-volatility environments, liquidity groups, sector dependence, outlier sensitivity, costs, slippage, and delayed entry.

Prefer a stable parameter region over one sharp optimum. Treat a cliff such as strong results at 1.99 and 2.00 but failure at 2.01 as suspicious unless a credible structural mechanism explains it. Report negative and mixed checks.

## 10. Compare with a meaningful baseline

Evaluate every candidate against a suitable baseline, such as an existing production strategy, buy-and-hold benchmark, random or unfiltered universe, simpler rule, or prior version. Use identical periods and compatible assumptions within discovery, validation, and holdout. Report candidate and baseline together; do not assess the candidate in isolation.

## 11. Make the historical-research decision

End historical research with exactly one status:

```text
REJECT
REVISE
HOLD
ADVANCE TO FORWARD TEST
```

Base it on discovery, separate validation, and untouched holdout evidence, robustness, sample size, data quality, execution realism, complexity, baseline improvement, and known limitations. Prefer the simpler candidate when performance is similar. `ADVANCE TO FORWARD TEST` never means production-ready.

## 12. Freeze the forward-test specification

Before forward testing, version and freeze strategy logic, parameters, universe and signal definitions, entry, exit and risk rules, data-source assumptions, code/config version, and research version. Freeze every material portfolio assumption defined in Stage 4, including construction and selection, position sizing and capital allocation, cash handling and capital reuse, long/short and borrow treatment, leverage and gross/net exposure, concentration and position limits, concurrent or overlapping positions, rebalancing and order netting, and portfolio-return aggregation. Record the frozen strategy/research version. Forward testing evaluates that complete specification, not a moving target. Use [FORWARD_TEST_PLAN.md](../../../templates/FORWARD_TEST_PLAN.md) when no equivalent plan exists.

## 13. Run the forward test on newly arriving data

Use data unavailable during historical research. Generate signals only from frozen rules; preserve timestamps; journal signals, expected entries, observable or actual execution assumptions, and later outcomes; retain failures, missing signals, and operational incidents; and never rewrite history. Compare forward evidence with backtest expectations. Track operational issues separately from strategy-performance issues.

Do not silently modify the strategy during the forward-test period.

## 14. Control changes during forward testing

Keep the current frozen version unchanged when a potential improvement appears. Route the idea through a new hypothesis, historical research, validation, and candidate version:

```text
current frozen version -> remains unchanged
new idea -> new experiment -> historical research -> validation -> candidate version
```

This boundary prevents continuous live overfitting.

## 15. Apply the production gate

Forward-test success does not authorize deployment. End with exactly one status:

```text
REJECT
CONTINUE FORWARD TEST
READY FOR PRODUCTION REVIEW
```

Never output `DEPLOY TO PRODUCTION` as the research decision. A separate human/release decision must assess forward sample sufficiency, consistency with historical expectations, drawdown, execution and data quality, operational reliability, drift, risk controls, and monitoring capability.

## 16. Preserve the audit trail

Maintain an auditable chain:

```text
hypothesis -> experiment ID -> dataset/version -> code/config version
-> dependency/environment version or immutable artifact -> discovery results
-> validation results -> untouched holdout results
-> decision -> frozen strategy version
-> forward signals -> forward outcomes -> production review
```

Make results reproducible where practical. Preserve losing, rejected, and inconclusive experiments; poor performance is not a reason to delete evidence.

## Relationship to repository workflows

This skill governs research decisions and evidence. When research requires repository implementation, use `research-experiment` for the domain lifecycle and `project-dev-cycle` for Git safety, implementation, verification, review, and approval boundaries. Use `code-review` for independent technical review and `release-check` for a separately requested boundary assessment. Use `debug` for scoped defects in research infrastructure, `incident-recovery` when an integrity incident threatens provenance, holdout isolation, experiment history, or production state, and `project-migrate` when adopting the workflow into this investment project.

The frozen hypothesis or strategy record supplies the domain specification for spec-driven implementation; do not create a duplicate general specification that can drift. Before production or research code, derive and review executable scenarios where practical for point-in-time availability, future-data leakage, deterministic replay, universe and baseline definitions, signal/entry/outcome timing, missing data, survivorship handling, validation/holdout isolation, metric semantics, experiment versioning, and research/production separation. Run focused scenarios, `powershell -ExecutionPolicy Bypass -File .\scripts\verify_research.ps1`, and the FULL repository gate `powershell -ExecutionPolicy Bypass -File .\scripts\verify_project.ps1` before independent review of meaningful changes.

Do not duplicate those workflow skills or treat their use as permission to commit, merge, push, release, deploy, change production strategy logic, modify runtime/private data, or interact with a brokerage.
