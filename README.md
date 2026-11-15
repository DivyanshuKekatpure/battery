# Charging rate, charge limit and battery life

A Six Sigma (DMAIC) project on how charging habits affect battery life, using the KIT battery aging dataset. We compare 72 lithium-ion cells tested at 3 charge rates, 2 charge limits (90% and 100%) and 4 temperatures. Results are direct measurements and simple arithmetic; there is no fitted statistical model.

**Main finding:** charging to 90% instead of 100% gave more cycles before the battery fell to 80% capacity in all 12 rate–temperature combinations tested. The gain was largest for fast charging. Cold plus fast charging was the most damaging condition.

## Deliverables

- [Preliminary Methods and Results](outputs/reports/Preliminary_Methods_and_Results.md) ([Word](outputs/reports/Preliminary_Methods_and_Results.docx))
- [Financial Impacts](outputs/reports/Financial_Impacts.md) ([Word](outputs/reports/Financial_Impacts.docx))
- [Project guide](docs/project_guide.md): key concepts, why batteries wear out, and the project step by step as DMAIC

## Data

All analysis inputs come from the KIT dataset, version 2 result data: Luh & Blank (2024), DOI [10.35097/1969](https://doi.org/10.35097/1969), CC BY 4.0. Paper: [Scientific Data 11, 1004](https://doi.org/10.1038/s41597-024-03831-x).

Download the result data package (`10.35097-1969.tar`, about 330 MB) and unpack it into `data2/`:

```bash
mkdir data2 && tar -xf 10.35097-1969.tar -C data2 --strip-components=1
```

The only values not taken from the data are:
- the 80% end-of-life threshold, which is an industry convention;
- the $99 replacement price, from Burkhardt (2024);
- the 0.5, 1 and 1.5 cycles-per-day usage scenarios.

All three are set at the top of `scripts/analysis.py`.

## Reproduce

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m scripts.run_all
```

This checks the download against its checksums, then rebuilds every table, figure and both reports. It takes under a minute.

## What's where

| Path | Contents |
|---|---|
| `scripts/analysis.py` | Reads the KIT data, finds each cell's life, builds tables and figures |
| `scripts/reports.py` | Writes both reports (Markdown and Word) from the tables |
| `outputs/tables/` | `cell_life.csv` (every cell), `condition_life.csv` (median of 3 cells), `cap_vs_no_cap.csv`, `main_effects.csv`, `cost_per_year.csv`, `capacity_checkups.csv` (every measurement used), `dropped_checkups.csv` (left out, with reason) |
| `outputs/figures/` | Capacity fade curves, cap vs no-cap chart, main effects, fishbone diagram, cost chart |
| `outputs/results.json` | Headline counts used in the reports |
