# Research Layer

This package is isolated from production. It exists to discover whether strategy components add value, not to prove that they do.

## Commands

```powershell
# Full research verification, gated baseline, and production hash isolation
powershell -ExecutionPolicy Bypass -File .\scripts\verify_research.ps1

# Generate the current DATA_READINESS-gated MODEL_0 report
python -m research.run_baseline --output-dir research/output/baseline
```

An explicitly supplied engineering dataset can be exercised with:

```powershell
python -m research.run_baseline --prices <long-form-ohclv.csv> --allow-survivorship-biased
```

That option does not repair historical membership. Its report remains labelled `SURVIVORSHIP-BIASED RESEARCH` and cannot validate a filter.

The reproducible free-data engineering workflow is:

```powershell
python -m research.download_yahoo --start 2016-01-01 --end 2026-09-13
python -m research.run_filter_audit --prices research/output/yahoo_engineering/prices.csv --benchmark research/output/yahoo_engineering/benchmark.csv
python -m research.run_forward_test --prices research/output/yahoo_engineering/prices.csv --benchmark research/output/yahoo_engineering/benchmark.csv

# Preregistered 20-cell target/initial-stop discovery grid
python -m research.run_exit_stop_grid --prices research/output/yahoo_engineering/prices.csv

# Preregistered portfolio heat, earned-exposure, and drawdown-overlay study
python -m research.run_portfolio_exposure --prices research/output/yahoo_engineering/prices.csv --benchmark research/output/yahoo_engineering/benchmark.csv

# Preregistered full 20 exit/stop x 9 exposure cross (180 cells)
python -m research.run_combined_exit_exposure_grid --prices research/output/yahoo_engineering/prices.csv --benchmark research/output/yahoo_engineering/benchmark.csv

# Frozen 6 stop x 7 exit x 4 exposure discovery, 2024 validation, and conditional 2025 holdout
python -m research.run_easy_execution_cross_validation --prices research/output/yahoo_engineering/prices.csv --benchmark research/output/yahoo_engineering/benchmark.csv
```

`download_yahoo` records source, date range, coverage, failures, and hashes. It uses the current universe and never claims delisted or historical-membership coverage. `run_filter_audit` evaluates only the preregistered 2017–2023 engineering discovery sample and refuses to describe 2024–2025 as evaluated holdout evidence. `run_forward_test` freezes the earliest complete immutable production snapshot per signal date, calculates raw horizons when mature, and conservatively simulates frozen entry/stop/target plans while leaving open immature outcomes missing.

`run_easy_execution_cross_validation` writes all 168 discovery cells, freezes at most three candidates before calculating 2024 validation, and only accesses the 2025 signal/outcome stage when a candidate passes the frozen validation gate. Each stage resets to 100R. The generated results remain `HOLD` because the archive is survivorship-biased.

Expected long-form price columns are `Date`, `Ticker`, `Open`, `High`, `Low`, `Close`, and `Volume`; `Adj Close` is optional. The loader validates and sorts bars, removes duplicate ticker/date rows deterministically, reports missing/invalid frequency, and records its adjustment method.

## Separation

- `engine/`: causal features, outcomes, execution, portfolio capacity, metrics, ablation, reporting, and manifests.
- `config/`: versioned research assumptions independent of production configuration.
- `experiments/`: predeclared future experiments. Recent RS is prepared, not run.
- `tests/`: anti-look-ahead, execution, accounting, reproducibility, and isolation tests.
- `output/`: generated local artifacts; ignored by Git.

The exact MODEL_0 definition and production-function reuse audit are in `docs/RESEARCH_ARCHITECTURE.md`. Current data limitations are in `docs/DATA_READINESS.md`.
