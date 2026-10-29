"""Phase 5: ownership cost before vs after the recommended charging change.

Adapts the structure of timothyfraser/sysen code/ZZ_financial_analysis.py: count failure events,
multiply by a cost, bootstrap the total (median, SE, 2.5/97.5 percentiles), and wrap it in a qi()
function that compares a baseline system with a changed system.

Here a failure event is a battery reaching 80% health (cycles_to_80pct_health from
outputs/sim_results.csv). Over an ownership horizon of H equivalent full cycles, each simulated
owner replaces the battery every time it reaches end of life; successive batteries draw their lives
from the same scenario's simulated pool (renewal process).

Reads data/cost_inputs.csv (written by the user, read-only here). Every row needs a numeric value
and a source_citation, otherwise the script stops and lists what is missing.
Writes outputs/tables/p5_*.csv and outputs/financial_report.txt.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze import STRATEGIES as P4_STRATEGIES, pick  # noqa: E402
from extract_summary import OUT_DIR, ROOT, Report, write_csv  # noqa: E402

SEED = 20261028
B_BOOT = 2000
COST_FILE = os.path.join(ROOT, "data", "cost_inputs.csv")
# Phase 4 strategies plus slower charging (decision D015: compare all against normal_fast)
STRATEGIES = dict(P4_STRATEGIES,
                  slow_2C={"charge_rate_C": 2.0, "ambient_C": 25, "charge_limit_pct": 100, "method": "CCCV"},
                  slow_1C={"charge_rate_C": 1.0, "ambient_C": 25, "charge_limit_pct": 100, "method": "CCCV"})
BEFORE = "normal_fast"
AFTERS = ["limit_80pct", "multistage", "slow_2C", "slow_1C"]
NOT_MODELLED_LIFE = {"limit_80pct", "multistage"}
TABLES = os.path.join(OUT_DIR, "tables")
REQUIRED = {
    "battery_replacement_price": "USD per replacement",
    "service_cost_per_replacement": "USD per replacement (labour, shipping, or 0 if included; cite it)",
    **{f"charger_cost_{k}": f"USD, charger used for {k}" for k in ["normal_fast", "limit_80pct", "multistage",
                                                                    "slow_2C", "slow_1C"]},
    "device_cost": "USD (used only in the replace-the-phone sensitivity case)",
    "cycles_per_year": "equivalent full cycles per year of phone use",
    "ownership_years": "years of ownership",
}
COLUMNS = ["item", "value", "low", "high", "unit", "source_citation", "location_in_source"]


def load_costs(rep):
    if not os.path.exists(COST_FILE):
        rep(f"STOP: {os.path.relpath(COST_FILE, ROOT)} does not exist. Required rows: {', '.join(REQUIRED)}")
        return None
    c = pd.read_csv(COST_FILE)
    problems = [f"missing column '{col}'" for col in COLUMNS if col not in c.columns]
    if problems:
        rep("STOP: " + "; ".join(problems))
        return None
    c = c.set_index("item")
    for item in REQUIRED:
        if item not in c.index:
            problems.append(f"{item}: row missing")
            continue
        r = c.loc[item]
        if pd.isna(pd.to_numeric(r["value"], errors="coerce")):
            problems.append(f"{item}: value missing or not numeric")
        if pd.isna(r["source_citation"]) or not str(r["source_citation"]).strip():
            problems.append(f"{item}: no source_citation")
        for b in ("low", "high"):
            if pd.notna(r[b]) and pd.isna(pd.to_numeric(r[b], errors="coerce")):
                problems.append(f"{item}: {b} is not numeric")
    if problems:
        rep("STOP: cost inputs incomplete:\n  " + "\n  ".join(problems))
        return None
    return {k: {f: (float(c.loc[k, f]) if pd.notna(c.loc[k, f]) else np.nan) for f in ("value", "low", "high")}
            for k in REQUIRED}


def replacements(lives, horizon, rng, n_owners):
    """Renewal process: count end-of-life events within `horizon` cycles per simulated owner."""
    counts = np.zeros(n_owners, int)
    used = np.zeros(n_owners)
    alive = np.ones(n_owners, bool)
    while alive.any():
        draw = rng.choice(lives, size=alive.sum(), replace=True)
        used[alive] += draw
        hit = used[alive] <= horizon
        idx = np.flatnonzero(alive)
        counts[idx[hit]] += 1
        alive[idx[~hit]] = False
    return counts


def ownership_cost(counts, cost, strategy, replace_phone=False):
    per_event = cost["device_cost"] if replace_phone else (cost["battery_replacement_price"] +
                                                           cost["service_cost_per_replacement"])
    return cost[f"charger_cost_{strategy}"] + counts * per_event


def qi(counts_before, counts_after, cost, rng, replace_phone=False, before_s=BEFORE, after_s="slow_1C"):
    """Bootstrap the difference in mean ownership cost (after - before) over simulated owners."""
    before = ownership_cost(counts_before, cost, before_s, replace_phone)
    after = ownership_cost(counts_after, cost, after_s, replace_phone)
    n = len(before)
    idx = rng.integers(0, n, size=(B_BOOT, n))
    boots = after[idx].mean(1) - before[idx].mean(1)
    return {"mean_before": before.mean(), "mean_after": after.mean(), "difference": after.mean() - before.mean(),
            "boot_median": float(np.median(boots)), "boot_se": float(boots.std(ddof=1)),
            "ci_lo": float(np.percentile(boots, 2.5)), "ci_hi": float(np.percentile(boots, 97.5))}


def main():
    rep = Report()
    os.makedirs(TABLES, exist_ok=True)
    rep(f"Phase 5 financial module. SEED={SEED}, B={B_BOOT}; before={BEFORE}; after={', '.join(AFTERS)}")
    cost = load_costs(rep)
    if cost is None:
        rep.save(os.path.join(OUT_DIR, "financial_report.txt"))
        return 1

    rng = np.random.default_rng(SEED)
    sim = pd.read_csv(os.path.join(OUT_DIR, "sim_results.csv"))
    lives = {k: pick(sim, STRATEGIES[k])["cycles_to_80pct_health"].to_numpy() for k in [BEFORE] + AFTERS}
    point = {k: v["value"] for k, v in cost.items()}
    n = len(lives[BEFORE])

    def run(c):
        horizon = c["cycles_per_year"] * c["ownership_years"]
        counts = {k: replacements(lives[k], horizon, rng, n) for k in lives}
        out = []
        for a in AFTERS:
            for phone in (False, True):
                out.append({"after": a, "case": "phone replacement" if phone else "battery replacement",
                            "horizon_cycles": horizon, "mean_replacements_before": counts[BEFORE].mean(),
                            "mean_replacements_after": counts[a].mean(),
                            "life_effect_modelled": a not in NOT_MODELLED_LIFE,
                            **qi(counts[BEFORE], counts[a], c, rng, phone, BEFORE, a)})
        return out

    res = pd.DataFrame(run(point))
    write_csv(res, os.path.join(TABLES, "p5_ownership_cost.csv"))
    rep(res.round(3).to_string(index=False))
    rep("limit_80pct and multistage: life effect not modelled (D009), so only charger costs can differ.")

    sens = []
    for item, v in cost.items():
        for bound in ("low", "high"):
            if not np.isnan(v[bound]):
                for r in run(dict(point, **{item: v[bound]})):
                    sens.append({"item": item, "bound": bound, "input_value": v[bound], **r})
    if sens:
        sens = pd.DataFrame(sens)
        write_csv(sens, os.path.join(TABLES, "p5_sensitivity.csv"))
        rep(sens[["item", "bound", "input_value", "after", "case", "difference", "ci_lo", "ci_hi"]].round(2)
            .to_string(index=False))
    else:
        rep("No low/high ranges supplied in cost_inputs.csv, so no sensitivity analysis was run.")
    rep.save(os.path.join(OUT_DIR, "financial_report.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
