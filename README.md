# Charging rate, charging cap, and battery degradation — KIT study

This repository now analyzes real KIT version 2 NMC/graphite–SiO aging measurements. The primary study contains 72 cells: three charging rates × two caps × four controlled bath temperatures × three replicates, with discharge fixed at 1C.

## Deliverables

- [Preliminary Methods and Results](outputs/reports/Preliminary_Methods_and_Results.docx) and [editable Markdown](outputs/reports/Preliminary_Methods_and_Results.md)
- [Financial Impacts](outputs/reports/Financial_Impacts.docx) and [editable Markdown](outputs/reports/Financial_Impacts.md)
- [Assignment](outputs/reports/task.txt)
- [Current decision log](docs/decision_log.md), [prespecified methods](docs/kit_methods.md), and [historical decisions](docs/old_decision_log.md)

## Reproduce

Requires Python 3.13, `pdftotext` for the historical ISU audit only, and the already-downloaded KIT v2 result package in `data2/`. The active pipeline does not require the 82 GB continuous logs or any network download.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m scripts.run_kit
```

The single command checks supplied checksums, extracts real reference capacities, fits censored lifetime models with 2,000 cell-bootstrap samples, calculates conditional financial projections, renders figures and both report formats, runs tests and acceptance checks, and publishes reports only after checks pass. The one-time historical archive has already been completed; do not rerun `scripts.kit.migrate`.

## Evidence and limitations

Observed capacities, source archive member names and original CSV row numbers are in `outputs/kit/observations.csv`. Derived lifetime intervals are in `endpoints_primary.csv`; predictions, regression, bootstrap fits and financial estimates are separate artifacts under `outputs/kit/`. Missing capacities are never filled and interval-censored failures are not replaced with guessed exact times. Synthetic fixtures and Monte Carlo samples are explicitly labeled software/numerical validation, never experimental observations.

The measured design has 63 observed crossings and nine right-censored cells. Weibull is the prespecified primary model, but lognormal performs substantially better on held-out interval likelihood. Reports disclose this model uncertainty. Temperature effects are conditional on shared bath apparatus. The phone-cost example assumes transfer from cylindrical, liquid-cooled KIT cells; that transfer has not been validated. Prices are explicitly dated scenarios, and usage is an assumption with weak evidence. Do not treat projections as observed or guaranteed smartphone savings.

Useful outputs include:

- `outputs/kit/preparation_summary.json`, `cell_inclusion.csv`, `descriptives.csv`: measured-data coverage and decisions.
- `regression.csv`, `interaction_tests.csv`, `predicted_life.csv`, `cap_contrasts.csv`: model estimates with nominal intervals.
- `cross_validation.csv`, `sensitivity_predictions.csv`: robustness and predictive checks.
- `financial_strategies.csv`, `financial_sensitivity.csv`, `annual_cost.csv`: conditional money calculations.
- `outputs/kit/sources/`: cited source register and explicitly classified monetary assumptions.
- `report_values.json`, `report_word_counts.json`, `acceptance_checks.json`: report provenance and checks.
- `outputs/kit_audit/`: full archive and 228-cell audit.

Raw downloads remain untracked. The supplied data are Luh & Blank (2024), KIT version 2 result data, DOI [10.35097/1969](https://doi.org/10.35097/1969), under CC BY 4.0. Cite the accompanying [Scientific Data paper](https://doi.org/10.1038/s41597-024-03831-x) and distinguish this project's derived analysis.

## History

The obsolete LFP pipeline/reports are preserved under `legacy/lfp/`; the alternative ISU audit is under `legacy/isu/`. [Archive manifest](legacy/archive_files.csv) records original paths and SHA256 hashes. These materials are historical, not active findings. Raw `data/` and `data2/` were not moved. Major implementation milestones are local Git commits; nothing has been pushed.
