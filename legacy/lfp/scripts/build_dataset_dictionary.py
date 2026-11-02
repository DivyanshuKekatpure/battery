"""Data dictionary for the project dataset (outputs/sim_results.csv plus its inputs).

One row per variable, grouped as in the dataset doc: operating variables (scenario factors),
life-model variables (simulated outputs), policy/decision variables and economic variables.
Levels and ranges are computed from the files, never typed in, so the dictionary always matches
the current run. Definitions and sources are fixed text that point at parameter IDs in
outputs/parameters.csv and items in outputs/cost_inputs_used.csv.

Writes outputs/dataset_dictionary.csv.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_summary import OUT_DIR, write_csv  # noqa: E402


def levels(s):
    return ", ".join(str(v).rstrip("0").rstrip(".") if isinstance(v, float) else str(v)
                     for v in sorted(s.dropna().unique()))


def span(s, fmt=".3g"):
    s = s.dropna()
    return f"{s.min():{fmt}} to {s.max():{fmt}} (median {s.median():{fmt}}; n = {len(s):,})"


def main():
    sim = pd.read_csv(os.path.join(OUT_DIR, "sim_results.csv"))
    prm = pd.read_csv(os.path.join(OUT_DIR, "parameters.csv")).set_index("id")
    cost = pd.read_csv(os.path.join(OUT_DIR, "cost_inputs_used.csv")).set_index("item")
    p = lambda i: f"{prm.loc[i, 'value']} {prm.loc[i, 'unit']}"  # noqa: E731
    c = lambda i: cost.loc[i, "value"]  # noqa: E731
    n_scen, n_bat = sim.scenario_id.nunique(), sim.battery.nunique()

    rows = [
        # 1. Operating variables
        ("operating", "Charge rate", "charge_rate_C", "C", levels(sim.charge_rate_C),
         "Nominal charging current as a multiple of capacity. The only factor with a modelled life effect.",
         "Design choice; life effect from P26-P28", "life effect modelled"),
        ("operating", "Ambient temperature", "ambient_C", "degC", levels(sim.ambient_C),
         "Surroundings while charging. Changes multistage charge time (Tahir 25/35 degC ratios) and peak temperature only.",
         "Design choice; P22, P23", "no life effect modelled (U01-U03 unverified)"),
        ("operating", "Charge limit", "charge_limit_pct", "% SOC", levels(sim.charge_limit_pct),
         "Upper charge limit. Carried as a factor but changes no output.",
         "Design choice", "no effect modelled (U04 unverified)"),
        ("operating", "Charging method", "method", "category", levels(sim.method),
         "CCCV = constant current, constant voltage. MSCC = five-stage multistage constant current at the same average rate.",
         "Design choice; P22, P23 (Tahir 2024)", "charge-time effect only; no life effect (U07 unverified)"),
        ("operating", "Scenario", "scenario_id", "id", f"1 to {n_scen}",
         "One combination of the four factors (full factorial).", "simulate.py", ""),
        ("operating", "Battery", "battery", "id", f"1 to {n_bat}",
         "Simulated battery within a scenario. Battery i uses the same random draws in every scenario (common random numbers, seed 20261028).",
         "simulate.py", ""),
        # 2. Life-model variables
        ("life_model", "Minutes to 80%", "minutes_to_80pct", "min", span(sim.minutes_to_80pct),
         "Time from empty to 80% charge: k x 0.8 x 60 / rate, k ~ Normal; times the Tahir ratio for MSCC.",
         "P09; P22, P23", "extrapolated: LFP, 3.6-8C data applied at 1-3C"),
        ("life_model", "Peak battery temperature", "peak_temp_C", "degC", span(sim.peak_temp_C),
         "Ambient plus charge-phase temperature rise. Reported only at 3C; blank below.",
         "P10, P11; P16, P17, P20, P21", "weak fit (R2 = 0.07); blank below 3C"),
        ("life_model", "Cycles to 80% health", "cycles_to_80pct_health", "cycles", span(sim.cycles_to_80pct_health, ",.0f"),
         "Weibull life draw; scale falls exponentially with charge rate.",
         "P26, P27, P28", "baseline 5-10x Apple's rating; use as relative effect only"),
        ("life_model", "Health at 500 cycles", "health_at_500", "fraction of 1.1 Ah", span(sim.health_at_500),
         "Capacity / nominal at cycle 500 from the normalised fade curve. Blank if the battery is past end of life.",
         "P29", "fade curve defined only down to 80% health"),
        ("life_model", "Past end of life at 500", "past_eol_at_500", "true/false",
         f"{sim.past_eol_at_500.mean():.1%} true",
         "Battery reached 80% health before cycle 500.", "P26-P29", ""),
        ("life_model", "Health at 1000 cycles", "health_at_1000", "fraction of 1.1 Ah", span(sim.health_at_1000),
         "As health_at_500, at cycle 1000.", "P29", "fade curve defined only down to 80% health"),
        ("life_model", "Past end of life at 1000", "past_eol_at_1000", "true/false",
         f"{sim.past_eol_at_1000.mean():.1%} true",
         "Battery reached 80% health before cycle 1000.", "P26-P29", ""),
        # 3. Policy / decision variables
        ("policy", "End-of-life threshold", "", "% of nominal capacity", "80",
         "A battery fails when health drops below this.", "Severson cycle-life definition; Apple P01, P02", ""),
        ("policy", "Rated life, iPhone 14 and earlier", "", "cycles", str(prm.loc["P01", "value"]),
         "Apple's design rating to 80% capacity; used to check the baseline and as the control-chart spec.", "P01", ""),
        ("policy", "Rated life, iPhone 15 models", "", "cycles", str(prm.loc["P02", "value"]),
         "Apple's design rating to 80% capacity.", "P02", "stated for iPhone 15 models only"),
        ("policy", "Usage intensity", "cycles_per_year", "cycles/year", f"{c('cycles_per_year'):g}",
         "Full charge cycles per year (0.7 per day).", "cost_inputs_used.csv (ITdaily)", "weak source, not peer reviewed"),
        ("policy", "Ownership horizon", "ownership_years", "years", f"{c('ownership_years'):g}",
         f"Years of use per owner; {c('cycles_per_year') * c('ownership_years'):g} cycles in total.",
         "cost_inputs_used.csv (Apple iPhone 16 environmental report)", ""),
        ("policy", "Simulation size", "", "batteries x scenarios", f"{n_bat:,} x {n_scen}",
         "Monte Carlo sample.", "simulate.py", ""),
        # 4. Economic variables
        ("economic", "Battery replacement price", "battery_replacement_price", "USD",
         f"{c('battery_replacement_price'):g} (high {cost.loc['battery_replacement_price', 'high']:g}, Pro models)",
         "Out-of-warranty battery service.", "cost_inputs_used.csv (9to5Mac citing Apple)", ""),
        ("economic", "Service cost per replacement", "service_cost_per_replacement", "USD",
         f"{c('service_cost_per_replacement'):g}", "Extra fee for in-store service.", "cost_inputs_used.csv (Apple Support)", ""),
        ("economic", "Charger cost", "charger_cost_*", "USD", f"{c('charger_cost_normal_fast'):g} for every strategy",
         "Apple 20W USB-C adapter.", "cost_inputs_used.csv", ""),
        ("economic", "Device price", "device_cost", "USD", f"{c('device_cost'):g}",
         "iPhone 16 128GB; used in the phone-replacement case.", "cost_inputs_used.csv (Apple Store)", ""),
    ]
    out = pd.DataFrame(rows, columns=["section", "variable", "column", "unit", "levels_or_range",
                                      "definition", "source", "status_or_caveat"])
    write_csv(out, os.path.join(OUT_DIR, "dataset_dictionary.csv"))
    print(f"Wrote outputs/dataset_dictionary.csv: {len(out)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
