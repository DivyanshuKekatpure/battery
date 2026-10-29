"""Financial figures and per-strategy cost table (Phase 5 follow-up).

Uses the same inputs, renewal process and common random numbers as scripts/financial.py.
Writes outputs/tables/p5_cost_by_strategy.csv, outputs/tables/p5_cost_by_year.csv and
outputs/figures/p5_*.png.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_summary import OUT_DIR, write_csv  # noqa: E402
from financial import AFTERS, B_BOOT, BEFORE, SEED, STRATEGIES, load_costs, ownership_cost, replacements  # noqa: E402
from analyze import pick  # noqa: E402
from extract_summary import Report  # noqa: E402
from svgplot import Plot  # noqa: E402

FIGS = os.path.join(OUT_DIR, "figures")
TABLES = os.path.join(OUT_DIR, "tables")
ORDER = [BEFORE] + AFTERS
LABEL = {"normal_fast": "Fast 3C (CC-CV, 100%)", "limit_80pct": "80% limit (3C)", "multistage": "Multistage (3C)",
         "slow_2C": "Slower 2C", "slow_1C": "Slower 1C"}


def boot_mean(x, seed):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(B_BOOT, len(x)))
    m = x[idx].mean(1)
    return float(x.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def main():
    rep = Report()
    cost = load_costs(rep)
    if cost is None:
        return 1
    c = {k: v["value"] for k, v in cost.items()}
    sim = pd.read_csv(os.path.join(OUT_DIR, "sim_results.csv"))
    lives = {k: pick(sim, STRATEGIES[k])["cycles_to_80pct_health"].to_numpy() for k in ORDER}
    n = len(lives[BEFORE])
    horizon = c["cycles_per_year"] * c["ownership_years"]
    counts = {k: replacements(lives[k], horizon, SEED + 1, n) for k in ORDER}

    rows = []
    for k in ORDER:
        bat = ownership_cost(counts[k], c, k)
        ph = ownership_cost(counts[k], c, k, replace_phone=True)
        share = (counts[k] >= 1).astype(float)
        b, ph_, sh = boot_mean(bat, SEED + 3), boot_mean(ph, SEED + 3), boot_mean(share, SEED + 3)
        rows.append({"strategy": k, "label": LABEL[k], "mean_replacements": counts[k].mean(),
                     "cost_battery_case": b[0], "cost_battery_ci_lo": b[1], "cost_battery_ci_hi": b[2],
                     "cost_phone_case": ph_[0], "cost_phone_ci_lo": ph_[1], "cost_phone_ci_hi": ph_[2],
                     "share_with_replacement": sh[0], "share_ci_lo": sh[1], "share_ci_hi": sh[2]})
    tbl = pd.DataFrame(rows)
    write_csv(tbl, os.path.join(TABLES, "p5_cost_by_strategy.csv"))
    print(tbl.round(4).to_string(index=False))

    # cumulative replacement spend by year of ownership (battery case), fast 3C vs slower 1C/2C
    yrs = []
    for y in range(1, int(c["ownership_years"]) + 1):
        h = c["cycles_per_year"] * y
        for k in [BEFORE, "slow_2C", "slow_1C"]:
            cnt = replacements(lives[k], h, SEED + 1, n)
            spend = cnt * (c["battery_replacement_price"] + c["service_cost_per_replacement"])
            m, lo, hi = boot_mean(spend.astype(float), SEED + 4)
            yrs.append({"year": y, "cycles": h, "strategy": k, "mean_spend": m, "ci_lo": lo, "ci_hi": hi})
    yrs = pd.DataFrame(yrs)
    write_csv(yrs, os.path.join(TABLES, "p5_cost_by_year.csv"))
    print(yrs.round(3).to_string(index=False))

    diff = pd.read_csv(os.path.join(TABLES, "p5_ownership_cost.csv"))

    # Figure 1: mean 3-year ownership cost per owner by strategy
    pl = Plot("Expected 3-year cost per owner, by charging strategy", "Charging strategy", "USD per owner (3 years)",
              subtitle="Charger + battery replacements at $99; point = mean of 1,000 simulated owners, bar = bootstrap 95% CI")
    pl.categorical_x([LABEL[k] for k in ORDER])
    pl.errorbars(range(len(ORDER)), tbl.cost_battery_case, tbl.cost_battery_ci_lo, tbl.cost_battery_ci_hi, color="#2563eb")
    pl.ylim = (15, 30)
    pl.save(os.path.join(FIGS, "p5_1_cost_per_owner.png"))

    # Figure 2: savings vs fast charging (positive = saved), battery and phone cases
    s = diff[diff["after"].isin(["slow_2C", "slow_1C"])]
    pl = Plot("Savings per owner vs fast 3C charging, over 3 years", "Change", "USD saved per owner (3 years)",
              subtitle="Bootstrap 95% CI; 80% limit and multistage save $0 because their life effects are not modelled")
    pl.categorical_x(["Slower 2C", "Slower 1C"])
    for case, off, col in [("battery replacement", -0.12, "#2563eb"), ("phone replacement", 0.12, "#dc2626")]:
        d = s[s["case"] == case].set_index("after").loc[["slow_2C", "slow_1C"]]
        pl.errorbars(np.arange(2) + off, -d["difference"], -d["ci_hi"], -d["ci_lo"], color=col,
                     label=f"If the owner replaces the {case.split()[0]}")
    pl.hline(0, color="#4b5563")
    pl.ylim = (0, 65)
    pl.save(os.path.join(FIGS, "p5_2_savings_vs_fast.png"))

    # Figure 3: share of owners needing at least one replacement
    pl = Plot("Owners needing a battery replacement within 3 years", "Charging strategy", "Share of owners (%)",
              subtitle="766.5 equivalent full cycles (0.7 per day x 3 years); bootstrap 95% CI")
    pl.categorical_x([LABEL[k] for k in ORDER])
    pl.errorbars(range(len(ORDER)), 100 * tbl.share_with_replacement, 100 * tbl.share_ci_lo, 100 * tbl.share_ci_hi,
                 color="#2563eb")
    pl.ylim = (0, 9)
    pl.save(os.path.join(FIGS, "p5_3_share_needing_replacement.png"))

    # Figure 4: cumulative replacement spend by year
    pl = Plot("Cumulative battery-replacement spend per owner", "Year of ownership", "USD per owner",
              subtitle="Mean of 1,000 simulated owners with bootstrap 95% CI; $99 per replacement")
    for k, dash in [(BEFORE, None), ("slow_2C", "8,5"), ("slow_1C", "2,4")]:
        d = yrs[yrs.strategy == k]
        pl.line(d.year, d.mean_spend, label=LABEL[k], dash=dash, marker=True)
        pl.errorbars(d.year, d.mean_spend, d.ci_lo, d.ci_hi, color=pl.items[-1]["color"])
    pl.xlim = (0.6, 3.4)
    pl.ylim = (0, 9)
    pl.save(os.path.join(FIGS, "p5_4_cumulative_spend_by_year.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
