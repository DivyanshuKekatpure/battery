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
from analyze import STRATEGIES, pick  # noqa: E402
from extract_summary import OUT_DIR, ROOT, Report, write_csv  # noqa: E402

SEED = 20261028
B_BOOT = 2000
COST_FILE = os.path.join(ROOT, "data", "cost_inputs.csv")
TABLES = os.path.join(OUT_DIR, "tables")
REQUIRED = {
    "battery_replacement_price": "USD per replacement",
    "service_cost_per_replacement": "USD per replacement (labour, shipping, or 0 if included; cite it)",
    "charger_cost_before": "USD, charger used before the change",
    "charger_cost_after": "USD, charger used after the change",
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


def ownership_cost(counts, cost, when, replace_phone=False):
    per_event = cost["device_cost"] if replace_phone else (cost["battery_replacement_price"] +
                                                           cost["service_cost_per_replacement"])
    return cost[f"charger_cost_{when}"] + counts * per_event


def qi(counts_before, counts_after, cost, rng, replace_phone=False):
    """Bootstrap the difference in mean ownership cost (after - before) over simulated owners."""
    before = ownership_cost(counts_before, cost, "before", replace_phone)
    after = ownership_cost(counts_after, cost, "after", replace_phone)
    n = len(before)
    idx = rng.integers(0, n, size=(B_BOOT, n))
    boots = after[idx].mean(1) - before[idx].mean(1)
    return {"mean_before": before.mean(), "mean_after": after.mean(), "difference": after.mean() - before.mean(),
            "boot_median": float(np.median(boots)), "boot_se": float(boots.std(ddof=1)),
            "ci_lo": float(np.percentile(boots, 2.5)), "ci_hi": float(np.percentile(boots, 97.5))}


def main(before="normal_fast", after=None):
    rep = Report()
    os.makedirs(TABLES, exist_ok=True)
    rep(f"Phase 5 financial module. SEED={SEED}, B={B_BOOT}")
    if after is None:
        rep("STOP: the recommended change (the 'after' strategy) has not been chosen. Options: "
            + ", ".join(k for k in STRATEGIES if k != before) + ", or a slower charge rate scenario.")
    cost = load_costs(rep)
    if cost is None or after is None:
        rep.save(os.path.join(OUT_DIR, "financial_report.txt"))
        return 1

    rng = np.random.default_rng(SEED)
    sim = pd.read_csv(os.path.join(OUT_DIR, "sim_results.csv"))
    lives = {k: pick(sim, STRATEGIES[k])["cycles_to_80pct_health"].to_numpy() for k in (before, after)}
    horizon = cost["cycles_per_year"]["value"] * cost["ownership_years"]["value"]
    n = len(lives[before])
    point = {k: {f: v["value"] for f, v in cost.items()} for k in ["base"]}["base"]
    counts = {k: replacements(lives[k], horizon, rng, n) for k in lives}
    rep(f"Horizon = {horizon:g} cycles; mean replacements: {before}={counts[before].mean():.3f}, "
        f"{after}={counts[after].mean():.3f}")

    res = [{"case": "battery replacement", **qi(counts[before], counts[after], point, rng)},
           {"case": "phone replacement", **qi(counts[before], counts[after], point, rng, replace_phone=True)}]
    write_csv(pd.DataFrame(res), os.path.join(TABLES, "p5_ownership_cost.csv"))
    rep(pd.DataFrame(res).round(2).to_string(index=False))

    sens = []
    for item, v in cost.items():
        for bound in ("low", "high"):
            if np.isnan(v[bound]):
                continue
            c2 = dict(point, **{item: v[bound]})
            h2 = c2["cycles_per_year"] * c2["ownership_years"]
            cnt = counts if h2 == horizon else {k: replacements(lives[k], h2, rng, n) for k in lives}
            sens.append({"item": item, "bound": bound, "input_value": v[bound],
                         **qi(cnt[before], cnt[after], c2, rng)})
    if sens:
        write_csv(pd.DataFrame(sens), os.path.join(TABLES, "p5_sensitivity.csv"))
        rep(pd.DataFrame(sens)[["item", "bound", "input_value", "difference", "ci_lo", "ci_hi"]].round(2).to_string(index=False))
    else:
        rep("No low/high ranges supplied in cost_inputs.csv, so no sensitivity analysis was run.")
    rep.save(os.path.join(OUT_DIR, "financial_report.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main(after=sys.argv[1] if len(sys.argv) > 1 else None))
