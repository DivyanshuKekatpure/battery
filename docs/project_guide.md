# Project guide: battery charging and degradation

This guide explains the ideas behind the project and walks through it as a Six Sigma DMAIC project. The numbers live in the reports (`outputs/reports/`) and tables (`outputs/tables/`), which are generated from the data, so this guide describes rather than repeats them.

## Key concepts

**Capacity.** How much charge a battery can hold, measured in ampere-hours (Ah). The KIT cells are rated at 3.0 Ah. As a battery ages, its capacity shrinks. That shrinking is the "degradation" we study.

**Capacity left (state of health).** Today's capacity divided by the capacity when new. A battery at 85% holds 85% of what it held at the start.

**End of life at 80%.** By common industry convention, a battery is worn out once it falls below 80% of its starting capacity. Phone makers use the same rule for battery-health warnings. It is a definition we choose; the KIT data does not set it.

**Equivalent full cycle.** One full charge plus one full discharge of the rated 3 Ah. Two half charges count as one cycle. Counting cycles this way lets us compare cells that were cycled differently.

**Charge rate (C-rate).** How fast a battery charges, relative to its capacity. 1C fills it in about an hour, 1/3C in about three hours, and 5/3C in about 36 minutes. Phone "fast charging" is in the 1C to 5/3C range.

**Charge limit (cap).** How full the battery is charged. KIT charged one group to 4.2 V, which is 100% full, and the other to 4.09 V, about 90% full. Phones offer this as "optimized" or "80%/90% limit" charging.

## Why batteries wear out: three mechanisms

1. **High voltage stress.** A cell sitting near 100% is at its highest voltage. That speeds up side reactions which permanently use up lithium and damage the electrodes. Capping at 90% avoids the most stressful part of each cycle. In our data, this is why the cap helps in every condition.
2. **Lithium plating.** When a cell is charged fast, lithium ions arrive at the negative electrode faster than they can move inside it. Some of them deposit as metallic lithium on the surface instead, and much of that lithium is lost for good. Cold makes the electrode slower to absorb lithium, so **fast charging in the cold** is the worst case. In our data, cells at 0°C charged at 5/3C wear out within tens of cycles.
3. **Heat-driven aging.** Heat speeds up all chemical reactions, including the slow ones that age a battery. That is why slow-charged cells last *less* at 40°C than at 25°C. But heat also makes lithium plating less likely, so for *fast* charging, 40°C beats 25°C. The two effects pull in opposite directions, and our results show both.

A fourth effect, **calendar aging** (aging with time even when unused), is not part of this analysis. That is why very long battery lives, beyond about five years, should be read with care.

## The project as DMAIC

### Define
- **Problem:** phone batteries lose capacity and need replacing too early.
- **Quality target (CTQ):** equivalent full cycles until the battery falls below 80% capacity. More cycles is better.
- **Scope:** charging behaviour the user or the phone can control, namely charge rate and charge limit, across operating temperatures.

### Measure
- **Data:** the KIT battery aging dataset, version 2 (Luh & Blank, 2024). It is a designed experiment with 3 charge rates × 2 charge limits × 4 temperatures, 3 cells each, so 72 cells, with discharge fixed at 1C.
- **What was measured:** a standard capacity check-up every few weeks (a full slow discharge at room temperature), plus how much charge passed through each cell.
- **Data checks:** the download is verified against its own checksums. Check-ups not done at room temperature, and the last check-up done after the lab's temperature control failed, are left out (`outputs/tables/dropped_checkups.csv`). Cells stopped by equipment errors are kept up to the point they stopped, and are marked × in plots.

### Analyze
- **Capacity fade curves** for every cell (`outputs/figures/fade_all_conditions.png`).
- **Battery life per cell**: the midpoint between the last check above 80% and the first check below it (`outputs/tables/cell_life.csv`).
- **Median of the 3 cells** per condition, and a direct cap-versus-no-cap comparison (`outputs/tables/cap_vs_no_cap.csv`, `outputs/figures/life_cap_vs_no_cap.png`).
- **Main effects chart**: the overall influence of charge rate, charge limit and temperature (`outputs/figures/main_effects.png`).
- **Fishbone diagram** of possible causes, including the ones held fixed or not tested (`outputs/figures/fishbone.png`).

### Improve
- **Change tested:** charge to 90% instead of 100%, and charge more slowly when possible.
- **Evidence:** the cap gives more cycles in every rate–temperature pair tested. The biggest gains are for fast charging.
- **Value:** yearly battery wear cost, which is replacement price × cycles used per year ÷ battery life. This is shown for several daily-usage scenarios (`outputs/tables/cost_per_year.csv`).

### Control
How the gain would be held in practice:
- Make a **90% charge limit the default** for users who regularly fast-charge, with an easy override for long days.
- **Slow down charging when the phone is cold** (below about 10°C), where fast charging does the most damage.
- **Monitor** battery health in the field: track the share of phones below 80% capacity by age, and compare phones with the cap on and off.
- **Validate on phone cells** before promising savings. The KIT cells are cylindrical 3 Ah cells, not phone batteries.

## What comes from where

| Input | Source |
|---|---|
| Capacities, cycle counts, test conditions, stop reasons | KIT dataset (`data2/`) |
| 3.0 Ah rated capacity, temperature-control failure date | KIT dataset readme |
| 80% end-of-life threshold | Industry convention (a definition) |
| $99 replacement price | External: Burkhardt (2024), 9to5Mac |
| 0.5 / 1 / 1.5 cycles per day | Scenarios, not data |
