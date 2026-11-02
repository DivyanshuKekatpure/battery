# KIT version 2 local audit

Sources: files in `data2/data/dataset`, supplied BagIt manifests, `Readme v2.pdf`,
`Data Structure v05.3.xlsx`, and the Cycling Experiment Cell Overview.
Run `python3 scripts/audit_kit.py` with Python's standard library to reproduce CSVs.
Existing simulation, financial outputs, and ISU audit remain unchanged.

## Release and integrity

- The download is **version 2 result data**, DOI 10.35097/1969. It is not the
  separate continuous-log release (DOI 10.35097/kww7jv8ajuvchcah).
- All **16 supplied checksum entries** passed (14 payload and 2 tag entries).
- Configuration, EOC, EIS and pulse archives each cover all **228 main cells**,
  with 76 parameter sets and three replicates each.
- There are 48 calendar, 144 cyclic, and 36 profile-aging cells.
- Extra P000/S20 records belong to the reversible-loss side experiment and must
  not be counted as 12 additional independent cells. Its real-cell mapping is in
  the version 2 README; this audit excludes those extra channels.
- CSV files are semicolon-delimited. Archives are read in place, not extracted.

## Capacity extraction and coverage

The audit extracted **3,999 standardized full-discharge check-up records**, with
2–29 measurements per cell. Records span October 13, 2022 to May 31, 2024 (UTC).
There are no duplicate `(cell, checkup_counter)` keys in these extracted records.

Selection: EOC `cyc_condition=2` (room-temperature check-up), `cyc_charged=0`,
voltage targets 4.2/2.5 V, discharge current -1 A and cut-off -0.15 A. Capacity
is the absolute measured `delta_q_dischg_Ah`, rather than the SOC-extrapolated
`cap_aged_est_Ah`. Median initial capacity is **2.923564 Ah**.

**Do not use `soh_cap` as ordinary percentage capacity retention.** The data
dictionary defines a custom scale with zero at the experiment's lower capacity
limit. This audit computes retention both against first reference capacity and
against the rated 3 Ah instead.

First observed crossings of 80% initial reference capacity:

| Aging type | Cells | Observed crossings | No observed crossing |
|---|---:|---:|---:|
| Cyclic | 144 | 130 | 14 |
| Calendar | 48 | 6 | 42 |
| Profile | 36 | 36 | 0 |

Crossings are bracketed between adjacent reference measurements, not interpolated
or fitted life estimates, and are not required to persist on later measurements.
Uncrossed cells require censoring at their last valid observation; do not assign
them that observation as a failure life. Termination can reflect equipment or
safety faults rather than capacity failure, so review the supplied overview's
failure reasons before survival fitting. Independent censoring is not established.

**Temperature quality flag:** three reference discharge records (P026_1/2/3,
check-up counter 11) end at only 2.16/3.05/1.79 °C despite the room-temperature
check-up label. They are retained and flagged for review, not silently removed.
The 20–30 °C screen is an audit heuristic, not a sourced instrument tolerance.

## Matched charging-cap comparisons

There are **16 matched cyclic parameter-set pairs**, each with three cells per
arm: four rate combinations at each of 0, 10, 25 and 40 °C. Pairing holds the lower
voltage, temperature, charging current and discharging current constant. Upper
voltage changes from **4.200 V to 4.092 V**, corresponding approximately to
10–100% versus 10–90% operation for new cells. SOC limits are approximate and
voltage-controlled; they are not an adaptive phone SOC cap.

At **25 °C**:

| Charging C | Discharging C | 90% parameter | 100% parameter | Cells crossing 80% initial (90% / 100%) |
|---|---|---|---|---|
| 1/3 | 1/3 | P049 | P045 | 0/3 / 3/3 |
| 1/3 | 1 | P050 | P046 | 0/3 / 3/3 |
| 1 | 1 | P051 | P047 | 3/3 / 3/3 |
| 5/3 | 1 | P052 | P048 | 3/3 / 2/3 |

These counts show threshold coverage, not a treatment-effect estimate. Three
replicates per condition give limited precision, and endpoint coverage differs.
The clean charging-rate series at 25 °C and 1C discharge is P046/P047/P048 for
100% charging and P050/P051/P052 for 90% charging: **18 cells total**. P045/P049
provide an additional cap comparison with a slower discharge rate.

Both cap arms receive periodic **full 0–100% reference cycles** and diagnostic
operations. The intervention is a cap during regular cycling, not an absolute
prohibition on ever reaching 100%.

## EFC and analysis cautions

- Total nominal EFC = `(total_q_chg_sum_Ah + total_q_dischg_sum_Ah) / (2*3 Ah)`.
  This follows the supplied README's throughput convention and includes check-ups.
  Operating EFC is also extracted separately from the operating-throughput fields.
- Lifetime crossing brackets use the provided cumulative total EFC at each check-up.
  They include initial preparation; subtract baseline EFC for a baseline-zero plot.
- The two-second/30-second logs are absent. End-of-run durations and start/end
  temperatures are present, but they do not identify within-charge time to 80%
  or peak temperature. Get the log release for those outputs.
- The final manual check-up followed a thermal-management failure on May 27, 2024
  and used room air cooling. Review the final measurement separately in sensitivity
  analysis. Calendar cells also had a reversible-loss side experiment.
- EIS/pulse cell inventories are checked, but every diagnostic measurement was not
  validated. Their quality needs a separate check if they enter the fitted model.
- The cap changes both the upper SOC and the cycle depth. It estimates the effect
  of that operating strategy, not an isolated chemical mechanism.
- These are NMC/graphite-SiO cylindrical cells with controlled cooling. Phone
  lifetimes and thermal behavior still require external validation.

## Outputs

- `checksums.csv`: expected and actual hashes.
- `archive_inventory.csv`: archive sizes and main-cell coverage.
- `cell_conditions.csv`: 228 main-cell configurations.
- `capacity_checkups.csv`: standardized capacities, EFC, retention and temperature flags.
- `capacity_inventory.csv`: per-cell coverage and two definitions of 80% crossings.
- `matched_cap_comparisons.csv`: all 16 matched cyclic cap comparisons.
