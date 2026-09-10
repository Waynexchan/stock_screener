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

Expected long-form price columns are `Date`, `Ticker`, `Open`, `High`, `Low`, `Close`, and `Volume`; `Adj Close` is optional. The loader validates and sorts bars, removes duplicate ticker/date rows deterministically, reports missing/invalid frequency, and records its adjustment method.

## Separation

- `engine/`: causal features, outcomes, execution, portfolio capacity, metrics, ablation, reporting, and manifests.
- `config/`: versioned research assumptions independent of production configuration.
- `experiments/`: predeclared future experiments. Recent RS is prepared, not run.
- `tests/`: anti-look-ahead, execution, accounting, reproducibility, and isolation tests.
- `output/`: generated local artifacts; ignored by Git.

The exact MODEL_0 definition and production-function reuse audit are in `docs/RESEARCH_ARCHITECTURE.md`. Current data limitations are in `docs/DATA_READINESS.md`.
