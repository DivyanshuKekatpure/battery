# Fast-charging battery degradation: data extraction

Per-cell and per-cycle tables extracted from the Severson et al. (2019) and Attia et al. (2020)
fast-charging datasets: A123 APR18650M1A LFP/graphite cells, 1.1 Ah nominal, cycled at 30 °C
with a 4C discharge.

## Data

The raw files (~11 GB) are not in this repo. Download them from data.matr.io into `data/raw/`:

```bash
mkdir -p data/raw
curl -L -o data/raw/2017-05-12_batchdata_updated_struct_errorcorrect.mat https://data.matr.io/1/api/v1/file/5c86c0b5fa2ede00015ddf66/download
curl -L -o data/raw/2017-06-30_batchdata_updated_struct_errorcorrect.mat https://data.matr.io/1/api/v1/file/5c86bf13fa2ede00015ddd82/download
curl -L -o data/raw/2018-04-12_batchdata_updated_struct_errorcorrect.mat https://data.matr.io/1/api/v1/file/5c86bd64fa2ede00015ddbb2/download
curl -L -o data/raw/2019-01-24_batchdata_updated_struct_errorcorrect.mat https://data.matr.io/1/api/v1/file/5dcef152110002c7215b2c90/download
```

Reference code from the authors (used to confirm conventions, not run here):
- https://github.com/rdbraatz/data-driven-prediction-of-battery-cycle-life-before-capacity-degradation (official loaders and paper curation)
- https://github.com/chueh-ermon/BMS-autoanalysis (how `cycle_life`, `chargetime` and the summary fields were computed)
- https://github.com/chueh-ermon/automate-Arbin-schedule-file-creation (4-step policy format)
- https://github.com/petermattia/battery-parameter-spaces (2019-01-24 validation batch; `Validation/final_results.csv`)

## Run

```bash
python3 -m venv .venv
.venv/bin/pip install h5py numpy pandas scipy
.venv/bin/python scripts/inspect_structure.py data/raw/2017-05-12_batchdata_updated_struct_errorcorrect.mat
.venv/bin/python scripts/extract_summary.py   # cell_summary, capacity_curves, batch_report
.venv/bin/python scripts/extract_full.py      # cycle_summary, early_features, discharge_curves.h5, full_report
```

## Outputs

| File | Contents |
|---|---|
| `outputs/cell_summary.csv` | One row per cell (185): policy (parsed), stored and checked cycle life, curation status, cycle 2–100 means of charge time, temperature and IR |
| `outputs/capacity_curves.csv` | Long format: batch, cell_id, cycle, discharge_capacity_Ah, merged_cell_id, merged_cycle |
| `outputs/cycle_summary.csv` | Every summary field for every cycle of every cell, with merged ids/cycles |
| `outputs/early_features.csv` | Early-life features per cell (ΔQ₁₀₀₋₁₀(V) statistics, fade slopes, charge time, IR, temperature) |
| `outputs/batch_report.txt`, `outputs/full_report.txt` | Checks, missing-data counts and extraction notes |
| `outputs/discharge_curves.h5` | *Not in git (142 MB).* Qdlin / Tdlin / dQdV on the 1000-point voltage grid for cycles 1–100, every 50th cycle and the last cycle |

Cell ids are `b<batch>c<index>`: b1 = 2017-05-12, b2 = 2017-06-30, b3 = 2018-04-12, b4 = 2019-01-24.

## Conventions and caveats

- **Nothing is filled or estimated.** Missing values stay blank and are listed in the reports.
- **Zeros are placeholders.** Cycle 1 is all zeros in b1–b3, and IR is all zeros in every b4 cell. Zeros are excluded from means and fits.
- **`chargetime`** is the time for charge capacity to reach 0.88 Ah (80% of nominal), in minutes. 20 min means "never reached" and is excluded.
- **`cycle_life_check`** uses the authors' rule: the first cycle below 0.88 Ah whose next cycle is lower still.
- **Paper curation**, in the `paper_status` column:
  - `used_merged`: b1c0–4 continue in batch 2 as b2c7, 8, 9, 15, 16 (`continuation_of_*`). `cycle_life_merged`, `merged_cell_id` and `merged_cycle` join them.
  - `removed_no_eol`: b1c8, 10, 12, 13, 22.
  - `removed_noisy`: b3c2, 23, 32, 37, 42, 43.
  - `used` + `used_merged` = the 124 cells of Severson et al. (2019). `attia2020_validation` = the 45 cells of the 2019-01-24 batch.
- **Policies.** Two-step policies, including `-newstructure` ones, fill `step1_rate_C`, `switch_soc_percent` and `step2_rate_C`. Four-step b4 policies fill `CC1_C`–`CC4_C` (each step covers 20% SOC, from 0 to 80%). Six b2 policy strings are truncated in the source and are left unparsed.
- **b1c18:** raw within-cycle time appears to be in seconds, so its temperature integral is blank.
