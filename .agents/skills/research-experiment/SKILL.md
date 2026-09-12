---
name: research-experiment
description: Govern systematic investment or trading research from a preregistered hypothesis through point-in-time backtesting, isolated holdout validation, robustness checks, forward testing, and production review. Use for domain-specific research, not ordinary software work, securities recommendations, brokerage actions, or automatic production promotion.
---

# Research experiment

Use this optional skill to make systematic investment and trading research auditable, reproducible where practical, and resistant to overfitting, look-ahead and survivorship bias, data leakage, selection bias, parameter mining, repeated-testing bias, unrealistic execution, and holdout contamination. It governs research; it does not supply a strategy, recommend securities, place trades, connect brokerage accounts, or authorize production changes.

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
- Do not repeatedly optimize against holdout data or silently reuse a contaminated holdout.
- Do not claim causality from correlation or claim that a profitable backtest proves a strategy works.
- Do not equate statistical significance with tradability. Evaluate economic magnitude, execution, risk, capacity where relevant, and operational feasibility.
- Prefer reproducibility and simple, stable rules over unnecessary complexity or a sharp optimum.
- Track material variants and repeated tests; warn that parameter mining and repeated experimentation increase false-discovery and overfitting risk.
- Never modify production strategy logic during research unless a separate, explicitly authorized production-change workflow permits it. Never modify real trading accounts or place trades.

## 1. Formalize the investment logic

Translate the human-readable idea into a testable statement before inspecting outcome results or tuning parameters. Distinguish:

- economic or market intuition and expected mechanism;
- observable conditions and universe;
- entry and exit logic;
- holding horizon; and
- risk assumptions.

A useful conceptual form is: “When condition X occurs under regime Y, instruments satisfying Z may outperform over horizon H because mechanism M is expected to occur.” Identify unresolved ambiguity before testing; do not conceal discretionary choices behind parameters.

## 2. Preregister the hypothesis

Before inspecting outcomes, record the hypothesis, universe, signal, entry, exit, holding periods, portfolio construction and position sizing where applicable, benchmark, primary and secondary metrics, risk metrics, transaction costs, slippage, discovery and holdout periods, temporal split and boundary controls, and acceptance and rejection criteria. Assign an experiment ID and hypothesis version where practical. The primary metric and criteria must be chosen before results are known.

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

For temporally ordered observations, place discovery before holdout and keep their observations and outcomes non-overlapping. Do not use an ordinary random split unless the research design justifies it and demonstrates that no future information can cross the boundary. Define sample membership from information-availability time and label/outcome end time, not row timestamp alone. Purge observations whose labels, holding periods, or derived windows cross a boundary, and apply an appropriate gap or embargo when feature lookbacks, forecast horizons, overlapping positions, publication delays, or repeated walk-forward folds could leak information. Record the sizes and rationale for these controls; do not assume adjacent date ranges are independent.

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

Use only the discovery sample for hypothesis exploration, feature investigation, threshold or parameter development, and failure analysis. Track every material variant, not only the winner. Record experiment ID, hypothesis/version, parameters, sample period and size, results, decision, and notes. Use [EXPERIMENT_LOG.md](../../../templates/EXPERIMENT_LOG.md) when no equivalent ledger exists.

Report the breadth of the search and any repeated use of the same data. Treat unexplained sensitivity and unusually successful isolated variants as warning signs.

## 6. Preserve and evaluate the holdout

Keep holdout data isolated from strategy development. Evaluate the preregistered candidate only after its specification is fixed, and compare **Candidate vs Baseline** on the same holdout period.

Do not repeatedly inspect holdout results and modify the strategy until it passes. If holdout evidence influences design, label the original holdout contaminated. Treat the revised strategy as a new version and, where feasible, validate it on a new untouched period. Never relabel a used sample as untouched.

## 7. Evaluate a balanced metric set

Do not judge a strategy from one metric. Select metrics appropriate to the design, including where relevant: sample size, mean and median return, win rate, payoff ratio, expectancy, cumulative return, drawdown, volatility, Sharpe-like risk-adjusted measures, maximum favorable and adverse excursion (MFE/MAE), turnover, exposure, benchmark-relative return, regime dependence, concentration, and tail outcomes.

For discrete trades, consider:

```text
Expectancy = P(win) x Average Win - P(loss) x Average Loss
```

A high win rate alone is not evidence of edge, and a tiny sample is not strong evidence. Report uncertainty and practical magnitude alongside statistical measures.

## 8. Test robustness

Before recommending a forward test, choose checks relevant to the hypothesis: nearby parameter values, alternate subperiods and market regimes, bull/bear/sideways or high/low-volatility environments, liquidity groups, sector dependence, outlier sensitivity, costs, slippage, and delayed entry.

Prefer a stable parameter region over one sharp optimum. Treat a cliff such as strong results at 1.99 and 2.00 but failure at 2.01 as suspicious unless a credible structural mechanism explains it. Report negative and mixed checks.

## 9. Compare with a meaningful baseline

Evaluate every candidate against a suitable baseline, such as an existing production strategy, buy-and-hold benchmark, random or unfiltered universe, simpler rule, or prior version. Use identical periods and compatible assumptions. Report candidate and baseline together; do not assess the candidate in isolation.

## 10. Make the historical-research decision

End historical research with exactly one status:

```text
REJECT
REVISE
HOLD
ADVANCE TO FORWARD TEST
```

Base it on discovery and holdout evidence, robustness, sample size, data quality, execution realism, complexity, baseline improvement, and known limitations. Prefer the simpler candidate when performance is similar. `ADVANCE TO FORWARD TEST` never means production-ready.

## 11. Freeze the forward-test specification

Before forward testing, version and freeze strategy logic, parameters, universe and signal definitions, entry, exit and risk rules, data-source assumptions, code/config version, and research version. Freeze every material portfolio assumption defined in Stage 4, including construction and selection, position sizing and capital allocation, cash handling and capital reuse, long/short and borrow treatment, leverage and gross/net exposure, concentration and position limits, concurrent or overlapping positions, rebalancing and order netting, and portfolio-return aggregation. Record the frozen strategy/research version. Forward testing evaluates that complete specification, not a moving target. Use [FORWARD_TEST_PLAN.md](../../../templates/FORWARD_TEST_PLAN.md) when no equivalent plan exists.

## 12. Run the forward test on newly arriving data

Use data unavailable during historical research. Generate signals only from frozen rules; preserve timestamps; journal signals, expected entries, observable or actual execution assumptions, and later outcomes; retain failures, missing signals, and operational incidents; and never rewrite history. Compare forward evidence with backtest expectations. Track operational issues separately from strategy-performance issues.

Do not silently modify the strategy during the forward-test period.

## 13. Control changes during forward testing

Keep the current frozen version unchanged when a potential improvement appears. Route the idea through a new hypothesis, historical research, validation, and candidate version:

```text
current frozen version -> remains unchanged
new idea -> new experiment -> historical research -> validation -> candidate version
```

This boundary prevents continuous live overfitting.

## 14. Apply the production gate

Forward-test success does not authorize deployment. End with exactly one status:

```text
REJECT
CONTINUE FORWARD TEST
READY FOR PRODUCTION REVIEW
```

Never output `DEPLOY TO PRODUCTION` as the research decision. A separate human/release decision must assess forward sample sufficiency, consistency with historical expectations, drawdown, execution and data quality, operational reliability, drift, risk controls, and monitoring capability.

## 15. Preserve the audit trail

Maintain an auditable chain:

```text
hypothesis -> experiment ID -> dataset/version -> code/config version
-> discovery results -> holdout results -> decision -> frozen strategy version
-> forward signals -> forward outcomes -> production review
```

Make results reproducible where practical. Preserve losing, rejected, and inconclusive experiments; poor performance is not a reason to delete evidence.

## Relationship to repository workflows

This skill governs research decisions and evidence. Use `docs/AI_WORKFLOW.md` for the repository development lifecycle, `docs/RESEARCH_GOVERNANCE.md` for filter status and evidence requirements, and `AGENTS.md` for Git, production, safety, and completion rules. Diagnose research-infrastructure defects before fixing them, independently review meaningful changes, and keep commit/push/release authority separate from research decisions.

Do not treat this skill as permission to commit, merge, push, release, deploy, change production strategy logic, modify runtime/private data, or interact with a brokerage.
