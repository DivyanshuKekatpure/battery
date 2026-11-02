# ISU-ILCC local data audit

Source: the downloaded `data/README_V2.0.pdf`, archive inventories, all supplied
capacity-fade CSVs, and sampled raw JSON schemas. No LFP results were replaced.

Run `python3 scripts/audit_isu.py` to regenerate the three CSV inventories. Requires
Python's standard library and `pdftotext`. The audit reads the small capacity archive
in place, without extracting the approximately 66 GB uncompressed cycling archive.
Inventory matching does not constitute a full integrity check of the raw archives.

## Findings

- All four data archives contain the same 251 unique cells as `Valid_cells.csv`.
- The README supplies 63 conditions (group IDs 1–64, excluding 15).
- All 251 capacity trajectories cross 80% of their own first measured capacity;
  245 cross 80% of the rated 0.250 Ah capacity (0.200 Ah).
- The derived crossing columns bracket the first measured crossing between
  observations, in the authors' supplied time-on-test weeks. They are not cycle
  lifetimes, interpolated point estimates, or sustained-crossing checks.
- Typical initial capacities exceed rated capacity. A consistent health denominator
  must be chosen before refitting the model. Do not mix 80% initial with 80% rated.
- The documented and sampled raw fields are Q, V, I, E and time. No cell-temperature
  field was found. All experiments used 30 °C incubators; peak-temperature predictions
  are unsupported by these files as inspected.

## Most useful direct comparisons

All groups below have four cells and a 0.5C discharge rate. DoD is the README's
group mean, not an exact match or an upper SOC limit.

| Group | Charge rate (C) | Mean DoD (%) |
|---|---:|---:|
| 2 | 0.5 | 46.11 |
| 4 | 1.0 | 47.27 |
| 7 | 2.0 | 46.86 |
| 10 | 2.5 | 47.21 |
| 13 | 3.0 | 47.26 |

Groups 3, 17, 8, 19 and 14 provide another comparison at roughly 66–68% DoD for
0.5, 1, 2, 2.5 and 3C respectively. There is no documented 3C near-full-DoD group.
Groups 16, 5, 9 and 11 cover roughly 96–98% DoD at 0.5, 1, 2 and 2.5C.

## Implications for the replacement model

1. Start with matched-condition comparisons at approximately 47% DoD, or restrict
   near-full-DoD comparisons to the available charge rates.
2. Use the small capacity tables for an initial trajectory review. To obtain life
   in equivalent full cycles, link RPT timestamps with actual charge throughput
   from cycling and RPT records; weeks and partial cycles cannot be treated as EFC.
3. Account for residual DoD differences and substantial cell variation. Four cells
   per group are insufficient to justify precise independent life-distribution
   parameters for every group. Do not assume the LFP rate slope or distribution.
4. Retain missing RPTs as missing. The README reports week-4 RPT loss in groups
   20–29 and additional losses for G25C1 and group 26 at weeks 23–24.
5. The release's supplied processor imputes some missing durations and uses older
   pandas interfaces. Do not run it unchanged as an authoritative new extractor.
6. No multistage comparison or measured peak-temperature output is supported here.
   Depth of discharge must not be relabeled as an 80% charge cap.

## Files

- `archive_inventory.csv`: per-archive cell counts and compressed/uncompressed sizes.
- `conditions.csv`: all README conditions with actual cell counts.
- `capacity_inventory.csv`: per-cell coverage, initial/final capacities and two
  definitions of the 80% capacity crossing brackets.
