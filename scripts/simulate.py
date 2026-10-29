"""Phase 3: full-factorial Monte Carlo of smartphone fast charging (see outputs/model_spec.md).

36 scenarios = charge rate {1,2,3}C x ambient {10,25,40} degC x limit {80,100}% x method {CCCV, MSCC},
1000 simulated batteries each. Uses only verified rows of outputs/parameters.csv.

Design choices (recorded in the decision log):
  - Common random numbers: battery i uses the same life draw U_i and charge-time draw Z_i in every
    scenario, so scenario differences are not sampling noise.
  - Parameters are held at their point estimates; parameter uncertainty is covered by a sensitivity
    run with the rate slope b at its 95% CI bounds (outputs/sim_results_sensitivity.csv).
  - Ambient temperature, charge limit and method have no verified life effect: they do not change
    life or health ('not modelled'). Peak temperature is only reported at 3C (model_spec D2).

Writes outputs/sim_results.csv, outputs/sim_results_sensitivity.csv, outputs/sim_log.txt.
"""
import itertools
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_summary import OUT_DIR, Report, write_csv  # noqa: E402

SEED = 20261028
N_BATTERIES = 1000
RATES = [1.0, 2.0, 3.0]
AMBIENTS = [10, 25, 40]
LIMITS = [80, 100]
METHODS = ["CCCV", "MSCC"]
R_REF = 4.74                 # reference rate of P27
TEMP_MIN_RATE = 3.0          # peak temperature reported only at >= 3C (D2)


def load_params():
    p = pd.read_csv(os.path.join(OUT_DIR, "parameters.csv")).set_index("id")
    used = ["P09", "P10", "P11", "P16", "P17", "P20", "P21", "P22", "P23", "P26", "P27", "P28", "P29"]
    bad = [i for i in used if p.loc[i, "verified"] != "yes"]
    if bad:
        raise SystemExit(f"Refusing to run: parameters {bad} are not verified")
    num = lambda i: float(p.loc[i, "value"])  # noqa: E731
    ci = lambda i: tuple(map(float, re.findall(r"\[(-?[\d.eE+-]+), (-?[\d.eE+-]+)\]", p.loc[i, "uncertainty_or_CI"])[0]))  # noqa: E731
    sd_k = float(re.search(r"SD=([\d.]+)", p.loc["P09", "uncertainty_or_CI"]).group(1))
    fade = pd.read_csv(os.path.join(OUT_DIR, "tables", "severson_normalized_fade_curve.csv"))
    return {
        "beta": num("P26"), "eta_ref": num("P27"), "b": num("P28"), "b_ci": ci("P28"),
        "k_mean": num("P09"), "k_sd": sd_k,
        "rho": {25: num("P22"), 35: num("P23")},
        "dT_slope": num("P10"), "dT_int": num("P11"),
        "ms_maxrise_ratio": {25: num("P17") / num("P16"), 35: num("P21") / num("P20")},
        "fade_f": fade["fraction_of_life"].to_numpy(), "fade_h": fade["health_median"].to_numpy(),
    }, p


def nearest_tested(t_amb):
    """Tahir tested 25 and 35 degC; other ambients use the nearest (assumption A6)."""
    return min((25, 35), key=lambda x: abs(x - t_amb))


def simulate(prm, u, z, b):
    rows = []
    for sid, (r, ta, lim, meth) in enumerate(itertools.product(RATES, AMBIENTS, LIMITS, METHODS), start=1):
        eta = prm["eta_ref"] * np.exp(b * (r - R_REF))
        life = eta * (-np.log(u)) ** (1 / prm["beta"])
        k = prm["k_mean"] + prm["k_sd"] * z
        t80 = k * 0.8 * 60 / r
        tt = nearest_tested(ta)
        if meth == "MSCC":
            t80 = t80 * prm["rho"][tt]
        if r >= TEMP_MIN_RATE:
            rise = prm["dT_int"] + prm["dT_slope"] * r
            if meth == "MSCC":
                rise *= prm["ms_maxrise_ratio"][tt]
            peak = np.full(u.size, ta + rise)
        else:
            peak = np.full(u.size, np.nan)
        health = {}
        for n in (500, 1000):
            ok = life >= n
            h = np.full(u.size, np.nan)
            h[ok] = np.interp(n / life[ok], prm["fade_f"], prm["fade_h"])
            health[n] = (h, ~ok)
        rows.append(pd.DataFrame({
            "scenario_id": sid, "charge_rate_C": r, "ambient_C": ta, "charge_limit_pct": lim, "method": meth,
            "battery": np.arange(1, u.size + 1), "minutes_to_80pct": t80, "peak_temp_C": peak,
            "cycles_to_80pct_health": life, "health_at_500": health[500][0], "past_eol_at_500": health[500][1],
            "health_at_1000": health[1000][0], "past_eol_at_1000": health[1000][1],
        }))
    return pd.concat(rows, ignore_index=True)


def main():
    rep = Report()
    prm, _ = load_params()
    rng = np.random.default_rng(SEED)
    u = rng.uniform(size=N_BATTERIES)
    z = rng.standard_normal(N_BATTERIES)
    rep(f"SEED={SEED} (numpy default_rng); N_BATTERIES={N_BATTERIES}; scenarios=36; common random numbers")
    rep(f"beta={prm['beta']}, eta_ref={prm['eta_ref']} at {R_REF}C, b={prm['b']} (CI {prm['b_ci']}), "
        f"k~N({prm['k_mean']}, {prm['k_sd']})")

    res = simulate(prm, u, z, prm["b"])
    write_csv(res, os.path.join(OUT_DIR, "sim_results.csv"))
    rep(f"Wrote outputs/sim_results.csv: {len(res):,} rows")

    sens = []
    for lab, b in [("b_ci_lower", prm["b_ci"][0]), ("b_point", prm["b"]), ("b_ci_upper", prm["b_ci"][1])]:
        s = simulate(prm, u, z, b)
        s.insert(0, "b_setting", lab)
        s.insert(1, "b_value", b)
        sens.append(s[["b_setting", "b_value", "scenario_id", "charge_rate_C", "ambient_C", "charge_limit_pct",
                       "method", "battery", "cycles_to_80pct_health", "health_at_500", "health_at_1000"]])
    sens = pd.concat(sens, ignore_index=True)
    write_csv(sens, os.path.join(OUT_DIR, "sim_results_sensitivity.csv"))
    rep(f"Wrote outputs/sim_results_sensitivity.csv: {len(sens):,} rows (b at CI bounds and point)")

    s = res.groupby(["charge_rate_C", "method"]).agg(
        median_life=("cycles_to_80pct_health", "median"), mean_t80=("minutes_to_80pct", "mean"),
        past_eol_500=("past_eol_at_500", "mean"), past_eol_1000=("past_eol_at_1000", "mean"))
    rep(s.round(4).to_string())
    rep.save(os.path.join(OUT_DIR, "sim_log.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
