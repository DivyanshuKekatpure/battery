"""Phase 1: build outputs/parameters.csv for the fast-charging Six Sigma simulation.

Every value is either read from a file in papers/ or data/ (method=read_from_paper) or
fitted to a dataset in data/ (method=fitted_to_dataset). Values that cannot be verified
from a provided file are listed with a blank value and verified=no (UNVERIFIED) and must
not be used by the simulation.

Inputs (read-only):
  data/DOE_Cap_v4.mat                  Diao et al. (2019) LCO capacity data, 24 conditions x 8 cells
  data/raw/*.mat                       Severson et al. (2019) LFP batch files (raw charge traces)
  data/calce_pl/*.zip                  CALCE PL SOC-window cells (only the Readme text is readable)
  outputs/cell_summary.csv             per-cell summary from scripts/extract_summary.py
  papers/Severson_2019_NatureEnergy.pdf, papers/Tahir_2024_JEnergyStorage_MSCC.pdf,
  papers/Apple_battery_service_and_recycling_retrieved_2026-10-28.html
Outputs:
  outputs/parameters.csv
  outputs/tables/diao_condition_fits.csv
  outputs/tables/severson_charge_rate_fit.csv
  outputs/tables/severson_charge_temperature_rise_by_cell.csv
  outputs/parameters_log.txt

No random numbers are drawn in this phase (all fits are deterministic); SEED is logged
for consistency with later phases.
"""
import glob
import os
import sys

import h5py
import numpy as np
import pandas as pd
import scipy.io
from scipy import optimize, special, stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_summary import OUT_DIR, ROOT, Report, write_csv  # noqa: E402

SEED = 20261028
TABLE_DIR = os.path.join(OUT_DIR, "tables")
DIAO_FILE = os.path.join(ROOT, "data", "DOE_Cap_v4.mat")
SEVERSON_NOMINAL_AH = 1.1          # Severson et al. (2019), Methods
SEVERSON_80PCT_AH = 0.8 * SEVERSON_NOMINAL_AH
TEMP_CYCLES = range(10, 101, 10)   # cycles sampled for the charge-phase temperature rise

CITE = {
    "apple": "Apple Inc. (n.d.). Battery service and recycling. Retrieved October 28, 2026, from "
             "https://www.apple.com/batteries/service-and-recycling/",
    "severson": "Severson, K. A., Attia, P. M., Jin, N., Perkins, N., Jiang, B., Yang, Z., Chen, M. H., "
                "Aykol, M., Herring, P. K., Fraggedakis, D., Bazant, M. Z., Harris, S. J., Chueh, W. C., & "
                "Braatz, R. D. (2019). Data-driven prediction of battery cycle life before capacity "
                "degradation. Nature Energy, 4(5), 383-391. https://doi.org/10.1038/s41560-019-0356-8",
    "tahir": "Tahir, M. U., Sangwongwanich, A., Stroe, D.-I., & Blaabjerg, F. (2024). Multi-objective "
             "optimization for multi-stage constant current charging for Li-ion batteries. Journal of "
             "Energy Storage, 86(Part A), 111313. https://doi.org/10.1016/j.est.2024.111313",
    "diao": "Diao, W., Saxena, S., & Pecht, M. (2019). Accelerated cycle life testing and capacity "
            "degradation modeling of LiCoO2-graphite cells. Journal of Power Sources, 435, 226830. "
            "https://doi.org/10.1016/j.jpowsour.2019.226830 (data: Mendeley Data, "
            "https://doi.org/10.17632/c35zbmn7j8.1)",
    "calce_pl": "Center for Advanced Life Cycle Engineering. (n.d.). PL sample battery data [Data set]. "
                "University of Maryland. https://calce.umd.edu/battery-data; experiments described in "
                "Saxena, S., Hendricks, C., & Pecht, M. (2016). Cycle life testing and modeling of "
                "graphite/LiCoO2 cells under different state of charge ranges. Journal of Power Sources, "
                "327, 394-400.",
    "saxena": "Saxena, S., Hendricks, C., & Pecht, M. (2016). Cycle life testing and modeling of "
              "graphite/LiCoO2 cells under different state of charge ranges. Journal of Power Sources, "
              "327, 394-400.",
    "keil": "Keil, P., & Jossen, A. (2016). Charging protocols for lithium-ion batteries and their impact "
            "on cycle life - An experimental study with different 18650 high-power cells. Journal of "
            "Energy Storage, 6, 125-141. https://doi.org/10.1016/j.est.2016.02.005",
    "huang": "Huang, S., Wu, X., Cavalheiro, G. M., Du, X., Liu, B., Du, Z., & Zhang, G. (2019). In situ "
             "measurement of lithium-ion cell internal temperatures during extreme fast charging. Journal "
             "of The Electrochemical Society, 166(14).",
    "liu": "Liu, Y.-H., & Luo, Y.-F. (2010). Search for an optimal rapid-charging pattern for Li-ion "
           "batteries using the Taguchi approach. IEEE Transactions on Industrial Electronics, 57(12), "
           "3963-3971.",
}

COLUMNS = ["id", "name", "value", "unit", "uncertainty_or_CI", "source_citation", "location_in_source",
           "method", "verified", "extrapolation_note"]
rows = []


def add(id_, name, value, unit, unc, cite, loc, method, verified, note=""):
    rows.append(dict(zip(COLUMNS, [id_, name, value, unit, unc, CITE[cite], loc, method, verified, note])))


def fmt(x, nd=4):
    return "" if x is None or (isinstance(x, float) and not np.isfinite(x)) else float(f"{x:.{nd}g}")


# --------------------------------------------------------------------------- Weibull MLE
def weibull_mle(fail, cens):
    """Right-censored two-parameter Weibull MLE. Returns dict with beta, eta, SEs and covariance
    of (log beta, log eta) from the observed information, or None if < 2 failures."""
    fail, cens = np.asarray(fail, float), np.asarray(cens, float)
    if fail.size < 2:
        return None

    def nll(p):
        lb, le = p
        b, e = np.exp(lb), np.exp(le)
        ll = np.sum(np.log(b) - np.log(e) + (b - 1) * (np.log(fail) - np.log(e)) - (fail / e) ** b)
        ll -= np.sum((cens / e) ** b)
        return -ll

    x0 = np.array([np.log(2.0), np.log(np.concatenate([fail, cens]).mean())])
    res = optimize.minimize(nll, x0, method="Nelder-Mead", options={"xatol": 1e-10, "fatol": 1e-10,
                                                                    "maxiter": 20000})
    p = res.x
    h = 1e-4
    H = np.zeros((2, 2))
    for i in range(2):
        for j in range(2):
            ei, ej = np.eye(2)[i] * h, np.eye(2)[j] * h
            H[i, j] = (nll(p + ei + ej) - nll(p + ei - ej) - nll(p - ei + ej) + nll(p - ei - ej)) / (4 * h * h)
    try:
        cov = np.linalg.inv(H)
        if np.any(np.diag(cov) <= 0):
            cov = None
    except np.linalg.LinAlgError:
        cov = None
    b, e = np.exp(p)
    out = {"beta": b, "eta": e, "cov_log": cov, "converged": bool(res.success), "n_fail": fail.size,
           "n_cens": cens.size}
    if cov is not None:
        se_lb, se_le = np.sqrt(np.diag(cov))
        out.update(beta_se=b * se_lb, eta_se=e * se_le,
                   beta_ci=(np.exp(p[0] - 1.96 * se_lb), np.exp(p[0] + 1.96 * se_lb)),
                   eta_ci=(np.exp(p[1] - 1.96 * se_le), np.exp(p[1] + 1.96 * se_le)))
    return out


def weibull_derived(w, t_list=(500, 1000)):
    """MTTF and R(t) with delta-method SEs on (log beta, log eta)."""
    def f_mttf(p):
        b, e = np.exp(p)
        return e * special.gamma(1 + 1 / b)

    def f_R(p, t):
        b, e = np.exp(p)
        return np.exp(-(t / e) ** b)

    p = np.log([w["beta"], w["eta"]])
    out = {"mttf": f_mttf(p)}
    for t in t_list:
        out[f"R{t}"] = f_R(p, t)
    if w.get("cov_log") is not None:
        def se(fn):
            g = np.array([(fn(p + d) - fn(p - d)) / 2e-6 for d in np.eye(2) * 1e-6])
            return float(np.sqrt(g @ w["cov_log"] @ g))
        out["mttf_se"] = se(f_mttf)
        for t in t_list:
            out[f"R{t}_se"] = se(lambda q, t=t: f_R(q, t))
    return out


# --------------------------------------------------------------------------- Diao
def crossing(cyc, ret, thr):
    """Linear interpolation of the first crossing below thr; (time, failed?)."""
    below = np.flatnonzero(ret < thr)
    if not below.size:
        return cyc[-1], False
    i = below[0]
    if i == 0:
        return cyc[0], True
    c0, c1, r0, r1 = cyc[i - 1], cyc[i], ret[i - 1], ret[i]
    return c0 + (r0 - thr) * (c1 - c0) / (r0 - r1), True


def knee_ratio(cyc, ret, min_pts=3):
    """Two-segment least-squares fit; ratio of post- to pre-breakpoint fade slope."""
    best = None
    for k in range(min_pts, len(cyc) - min_pts + 1):
        s1 = np.polyfit(cyc[:k], ret[:k], 1)
        s2 = np.polyfit(cyc[k - 1:], ret[k - 1:], 1)
        sse = (np.sum((np.polyval(s1, cyc[:k]) - ret[:k]) ** 2) +
               np.sum((np.polyval(s2, cyc[k - 1:]) - ret[k - 1:]) ** 2))
        if best is None or sse < best[0]:
            best = (sse, s1[0], s2[0], cyc[k - 1])
    if best is None or best[1] >= 0:
        return None, None
    return best[2] / best[1], best[3]


def diao_fits(rep):
    d = scipy.io.loadmat(DIAO_FILE)["DOE_Cap"]
    rep(f"Diao DOE_Cap: {d.shape[0]} conditions x {d.shape[1]} cells; each entry (cycle, capacity)")
    out, notes = [], []
    for m in range(d.shape[0]):
        cond = m + 1  # 1-based condition ID as in the Mendeley description ("Cell (m,n)")
        t80, c80, t90, c90, knees, n_used, excluded = [], [], [], [], [], 0, []
        for n in range(d.shape[1]):
            e = d[m, n]
            valid = np.isfinite(e[:, 1]) & (e[:, 1] > 0)  # 0 = not measured
            cyc, cap = e[valid, 0], e[valid, 1]
            if cyc.size < 3 or cyc[0] != 0:
                excluded.append(f"cell {n + 1} ({cyc.size} valid points)")
                continue
            n_used += 1
            ret = cap / cap[0]
            for thr, ft, ct in [(0.8, t80, c80), (0.9, t90, c90)]:
                t, failed = crossing(cyc, ret, thr)
                (ft if failed else ct).append(t)
            if cyc.size >= 7:
                r, _ = knee_ratio(cyc, ret)
                if r is not None:
                    knees.append(r)
        if excluded:
            notes.append(f"condition {cond}: excluded {', '.join(excluded)} (no data after cycle 0)")
        row = {"condition_id": cond, "n_cells_used": n_used,
               "n_fail_80": len(t80), "n_cens_80": len(c80), "n_fail_90": len(t90), "n_cens_90": len(c90),
               "max_cycle_observed": max([*t80, *c80, *t90, *c90], default=np.nan),
               # only when every cell crossed, so censoring cannot bias the median
               "empirical_median_cycles_to_90pct": float(np.median(t90)) if t90 and len(t90) == n_used else np.nan,
               "knee_slope_ratio_median": float(np.median(knees)) if knees else np.nan,
               "n_cells_knee": len(knees)}
        for lab, ft, ct in [("80", t80, c80), ("90", t90, c90)]:
            w = weibull_mle(ft, ct)
            if w is None:
                continue
            row.update({f"beta_{lab}": w["beta"], f"beta_{lab}_se": w.get("beta_se"),
                        f"eta_{lab}": w["eta"], f"eta_{lab}_se": w.get("eta_se"),
                        f"beta_{lab}_ci_lo": w.get("beta_ci", (np.nan,))[0],
                        f"beta_{lab}_ci_hi": w.get("beta_ci", (np.nan, np.nan))[1],
                        f"eta_{lab}_ci_lo": w.get("eta_ci", (np.nan,))[0],
                        f"eta_{lab}_ci_hi": w.get("eta_ci", (np.nan, np.nan))[1],
                        f"converged_{lab}": w["converged"]})
            dv = weibull_derived(w)
            row.update({f"mttf_{lab}": dv["mttf"], f"mttf_{lab}_se": dv.get("mttf_se"),
                        f"R500_{lab}": dv["R500"], f"R500_{lab}_se": dv.get("R500_se"),
                        f"R1000_{lab}": dv["R1000"], f"R1000_{lab}_se": dv.get("R1000_se")})
        out.append(row)
    return pd.DataFrame(out), notes


# --------------------------------------------------------------------------- Severson
def severson_rate_fit(rep):
    cs = pd.read_csv(os.path.join(OUT_DIR, "cell_summary.csv"))
    s = cs[cs["paper_status"].isin(["used", "used_merged"])].copy()
    s["avg_rate_to_80_C"] = 0.8 * 60 / s["mean_charge_time_min"]
    s["log_life"] = np.log(s["cycle_life_merged"])
    s = s.dropna(subset=["avg_rate_to_80_C", "log_life"])
    lr = stats.linregress(s["avg_rate_to_80_C"], s["log_life"])
    tcrit = stats.t.ppf(0.975, len(s) - 2)
    fit = {"n": len(s), "slope": lr.slope, "slope_se": lr.stderr, "slope_ci_lo": lr.slope - tcrit * lr.stderr,
           "slope_ci_hi": lr.slope + tcrit * lr.stderr, "intercept": lr.intercept, "r2": lr.rvalue ** 2,
           "p": lr.pvalue, "rate_min": s["avg_rate_to_80_C"].min(), "rate_max": s["avg_rate_to_80_C"].max()}
    rep(f"Severson log(cycle life) ~ avg charge rate to 80%: n={fit['n']}, slope={fit['slope']:.4f} "
        f"[{fit['slope_ci_lo']:.4f}, {fit['slope_ci_hi']:.4f}] per C, R2={fit['r2']:.3f}, p={fit['p']:.3g}, "
        f"tested rates {fit['rate_min']:.2f}-{fit['rate_max']:.2f} C")

    # CC time-to-80% check on constant-rate-to-80% policies (step1 == step2, or switch >= 80%)
    cc = cs[cs["switch_soc_percent"] >= 80].dropna(subset=["step1_rate_C", "mean_charge_time_min"])
    k = cc["mean_charge_time_min"] / (0.8 * 60 / cc["step1_rate_C"])
    kfit = {"n": len(k), "mean": k.mean(), "sd": k.std(ddof=1),
            "ci": stats.t.interval(0.95, len(k) - 1, loc=k.mean(), scale=k.std(ddof=1) / np.sqrt(len(k))),
            "rates": sorted(cc["step1_rate_C"].unique())}
    rep(f"CC time-to-80% ratio measured/(48/C): n={kfit['n']}, mean={kfit['mean']:.4f}, rates={kfit['rates']}")
    return s, fit, kfit


def severson_charge_temperature(rep, cells):
    """Charge-phase temperature rise: max can temperature while charge capacity <= 0.88 Ah minus
    temperature at charge start, averaged over cycles 10, 20, ..., 100."""
    batch_files = {"2017-05-12": 1, "2017-06-30": 2, "2018-04-12": 3}
    recs, notes = [], []
    for date, bi in batch_files.items():
        path = os.path.join(ROOT, "data", "raw", f"{date}_batchdata_updated_struct_errorcorrect.mat")
        ids = cells[cells["batch"] == date]
        with h5py.File(path, "r") as f:
            b = f["batch"]
            for _, r in ids.iterrows():
                ci = int(r.cell_id.split("c")[1])
                cyc = f[b["cycles"][ci, 0]]
                rises = []
                for c in TEMP_CYCLES:
                    j = c - 1
                    if j >= cyc["I"].shape[0]:
                        continue
                    arr = {k: f[cyc[k][j, 0]][()].flatten() for k in ["I", "T", "Qc"]}
                    if any(a.size < 2 for a in arr.values()):
                        continue
                    ch = np.flatnonzero((arr["I"] > 0) & (arr["Qc"] <= SEVERSON_80PCT_AH))
                    if ch.size < 2 or not np.all(np.isfinite(arr["T"][ch])):
                        continue
                    rises.append(arr["T"][ch].max() - arr["T"][ch[0]])
                if not rises:
                    notes.append(f"{r.cell_id}: no usable charge-phase temperature in cycles 10-100")
                    continue
                recs.append({"batch": date, "cell_id": r.cell_id, "avg_rate_to_80_C": r.avg_rate_to_80_C,
                             "charge_temp_rise_C": float(np.mean(rises)), "n_cycles": len(rises)})
    df = pd.DataFrame(recs)
    lr = stats.linregress(df["avg_rate_to_80_C"], df["charge_temp_rise_C"])
    tcrit = stats.t.ppf(0.975, len(df) - 2)
    fit = {"n": len(df), "slope": lr.slope, "slope_ci": (lr.slope - tcrit * lr.stderr, lr.slope + tcrit * lr.stderr),
           "intercept": lr.intercept, "intercept_se": lr.intercept_stderr, "r2": lr.rvalue ** 2,
           "mean_rise": df["charge_temp_rise_C"].mean(), "sd_rise": df["charge_temp_rise_C"].std(ddof=1)}
    rep(f"Severson charge-phase temperature rise ~ rate: n={fit['n']}, slope={fit['slope']:.3f} C/C-rate, "
        f"R2={fit['r2']:.3f}; mean rise={fit['mean_rise']:.2f} degC")
    return df, fit, notes


def severson_weibull_regression(rep, s):
    """Weibull life regression on the 124 curated Severson cells (all reached EOL, no censoring):
    life ~ Weibull(beta, eta_i), ln eta_i = ln eta_ref + b * (rate_i - rate_ref)."""
    life = s["cycle_life_merged"].to_numpy(float)
    r = s["avg_rate_to_80_C"].to_numpy(float)
    r_ref = float(np.round(np.median(r), 2))

    def nll(p):
        lb, le, b = p
        beta = np.exp(lb)
        eta = np.exp(le + b * (r - r_ref))
        z = life / eta
        return -np.sum(np.log(beta) - np.log(eta) + (beta - 1) * np.log(z) - z ** beta)

    x0 = np.array([np.log(2.0), np.log(np.median(life)), -0.4])
    res = optimize.minimize(nll, x0, method="Nelder-Mead", options={"xatol": 1e-10, "fatol": 1e-10, "maxiter": 40000})
    p, h = res.x, 1e-4
    H = np.zeros((3, 3))
    for i in range(3):
        for j in range(3):
            ei, ej = np.eye(3)[i] * h, np.eye(3)[j] * h
            H[i, j] = (nll(p + ei + ej) - nll(p + ei - ej) - nll(p - ei + ej) + nll(p - ei - ej)) / (4 * h * h)
    se = np.sqrt(np.diag(np.linalg.inv(H)))
    out = {"n": len(life), "rate_ref": r_ref, "beta": np.exp(p[0]), "beta_ci": tuple(np.exp(p[0] + k * 1.96 * se[0]) for k in (-1, 1)),
           "eta_ref": np.exp(p[1]), "eta_ref_ci": tuple(np.exp(p[1] + k * 1.96 * se[1]) for k in (-1, 1)),
           "b": p[2], "b_se": se[2], "b_ci": (p[2] - 1.96 * se[2], p[2] + 1.96 * se[2]), "converged": bool(res.success)}
    rep(f"Severson Weibull regression: beta={out['beta']:.3f}, eta at {r_ref}C={out['eta_ref']:.1f}, "
        f"b={out['b']:.4f} (SE {out['b_se']:.4f}), converged={out['converged']}")
    return out


def severson_fade_curve(rep, s):
    """Median normalised fade curve: health = Q/Q_nominal (1.1 Ah) vs fraction of life n/L, f in [0, 1]."""
    cc = pd.read_csv(os.path.join(OUT_DIR, "capacity_curves.csv"))
    life = s.set_index("cell_id")["cycle_life_merged"]
    grid = np.round(np.arange(0, 1.0001, 0.05), 2)
    curves = []
    for cid, g in cc[cc["merged_cell_id"].isin(life.index)].groupby("merged_cell_id"):
        g = g[(g["discharge_capacity_Ah"] > 0) & np.isfinite(g["discharge_capacity_Ah"])].sort_values("merged_cycle")
        f = (g["merged_cycle"] - 1) / life[cid]  # cycle 1 -> f=0
        curves.append(np.interp(grid, f, g["discharge_capacity_Ah"] / SEVERSON_NOMINAL_AH))
    curves = np.array(curves)
    tbl = pd.DataFrame({"fraction_of_life": grid, "health_median": np.median(curves, 0),
                        "health_p05": np.percentile(curves, 5, 0), "health_p95": np.percentile(curves, 95, 0),
                        "n_cells": len(curves)})
    rep(f"Severson normalised fade curve: {len(curves)} cells; health at f=0 {tbl.health_median.iloc[0]:.4f}, "
        f"f=0.5 {tbl.health_median.iloc[10]:.4f}, f=1 {tbl.health_median.iloc[-1]:.4f}")
    return tbl


# --------------------------------------------------------------------------- main
def main():
    os.makedirs(TABLE_DIR, exist_ok=True)
    rep = Report()
    rep(f"Phase 1 parameter build. SEED={SEED} (no random draws in this phase).")

    # Manufacturer ratings (Apple page saved in papers/)
    apple_loc = "papers/Apple_battery_service_and_recycling_retrieved_2026-10-28.html, 'iPhone Owners' section"
    add("P01", "rated_cycles_to_80pct_iphone14_and_earlier", 500, "complete charge cycles", "none stated",
        "apple", apple_loc, "read_from_paper", "yes",
        "Manufacturer rating 'under ideal conditions'; test conditions not disclosed")
    add("P02", "rated_cycles_to_80pct_iphone15_models", 1000, "complete charge cycles", "none stated",
        "apple", apple_loc, "read_from_paper", "yes",
        "Page says 'iPhone 15 models', not 'iPhone 15 and later'; applying to later models is an extrapolation")

    # Severson paper facts
    sev_loc = "papers/Severson_2019_NatureEnergy.pdf, Methods ('Cell cycling')"
    add("P03", "severson_nominal_capacity", 1.1, "Ah", "none stated", "severson", sev_loc, "read_from_paper", "yes",
        "LFP/graphite A123 APR18650M1A, not a smartphone LCO cell")
    add("P04", "severson_chamber_temperature", 30, "degC", "none stated", "severson", sev_loc,
        "read_from_paper", "yes", "Single ambient temperature; no temperature effect can be fitted from Severson")
    add("P05", "severson_charge_time_0_to_80pct_range", "9 to 13.3", "min", "range across policies",
        "severson", sev_loc, "read_from_paper", "yes", "LFP fast-charging policies (~3.6C-6C+)")

    s, fit, kfit = severson_rate_fit(rep)
    fit_tbl = pd.DataFrame([fit])
    write_csv(fit_tbl, os.path.join(TABLE_DIR, "severson_charge_rate_fit.csv"))
    loc_fit = ("data/raw/2017-05-12, 2017-06-30, 2018-04-12 batch files via outputs/cell_summary.csv "
               "(124 cells, paper_status used/used_merged); outputs/tables/severson_charge_rate_fit.csv")
    rng = f"tested average rates {fit['rate_min']:.2f}-{fit['rate_max']:.2f} C"
    add("P06", "log_cycle_life_slope_per_1C_avg_charge_rate", fmt(fit["slope"]), "ln(cycles) per C",
        f"SE={fmt(fit['slope_se'])}; 95% CI [{fmt(fit['slope_ci_lo'])}, {fmt(fit['slope_ci_hi'])}]; "
        f"R2={fmt(fit['r2'], 3)}; p={fmt(fit['p'], 3)}; n={fit['n']}",
        "severson", loc_fit, "fitted_to_dataset", "yes",
        f"LFP-to-LCO extrapolation; {rng}; policies differ in more than average rate (confounded)")
    for pid, dc in [("P07", 1), ("P08", 2)]:
        add(pid, f"relative_cycle_life_multiplier_{1 + dc}C_vs_1C", fmt(np.exp(fit["slope"] * dc)), "ratio",
            f"95% CI [{fmt(np.exp(fit['slope_ci_lo'] * dc))}, {fmt(np.exp(fit['slope_ci_hi'] * dc))}] "
            f"(from P06)", "severson", loc_fit, "fitted_to_dataset", "yes",
            f"LFP-to-LCO extrapolation AND rate extrapolation: 1C-3C lies below the {rng}")
    add("P09", "cc_time_to_80pct_ratio_measured_over_0.8h_per_C", fmt(kfit["mean"]), "ratio",
        f"SD={fmt(kfit['sd'])}; 95% CI [{fmt(kfit['ci'][0])}, {fmt(kfit['ci'][1])}]; n={kfit['n']} cells "
        f"at {', '.join(f'{r:g}C' for r in kfit['rates'])}", "severson",
        "outputs/cell_summary.csv (policies with constant rate to >= 80% SOC)", "fitted_to_dataset", "yes",
        "Checks t80 = 48/C min on LFP single-rate-to-80% policies; LFP-to-LCO and to 1C-3C rate extrapolation")

    temp_df, tfit, tnotes = severson_charge_temperature(rep, s)
    write_csv(temp_df, os.path.join(TABLE_DIR, "severson_charge_temperature_rise_by_cell.csv"))
    tloc = ("data/raw Severson batch files: cycles 10,20,...,100, samples with I>0 and Qc<=0.88 Ah; "
            "outputs/tables/severson_charge_temperature_rise_by_cell.csv")
    add("P10", "charge_phase_can_temp_rise_slope_per_1C", fmt(tfit["slope"]), "degC per C",
        f"95% CI [{fmt(tfit['slope_ci'][0])}, {fmt(tfit['slope_ci'][1])}]; R2={fmt(tfit['r2'], 3)}; n={tfit['n']}",
        "severson", tloc, "fitted_to_dataset", "yes",
        f"LFP 18650 can surface, 30 degC chamber (forced/natural convection not stated); {rng}; LFP-to-LCO "
        "phone-cell extrapolation")
    add("P11", "charge_phase_can_temp_rise_intercept", fmt(tfit["intercept"]), "degC",
        f"SE={fmt(tfit['intercept_se'])}", "severson", tloc, "fitted_to_dataset", "yes",
        "Intercept at 0C is far outside tested rates; use only with P10 inside/near the tested range")

    # Added in Phase 2 (after Phase 1 approval): baseline life distribution and fade-curve shape
    w = severson_weibull_regression(rep, s)
    wloc = ("outputs/cell_summary.csv (124 curated Severson cells, cycle_life_merged, avg rate to 80%); "
            "Weibull regression by MLE")
    wnote = (f"Added after Phase 1 approval. LFP 18650 at 30 degC chamber; tested average rates "
             f"{fit['rate_min']:.2f}-{fit['rate_max']:.2f} C; using it at 1C-3C, 10-40 degC and for LCO "
             "phone cells is an extrapolation")
    add("P26", "severson_weibull_shape_beta", fmt(w["beta"]), "-",
        f"95% CI [{fmt(w['beta_ci'][0])}, {fmt(w['beta_ci'][1])}]; n={w['n']} (no censoring)",
        "severson", wloc, "fitted_to_dataset", "yes", wnote)
    add("P27", f"severson_weibull_scale_eta_at_{w['rate_ref']:g}C_avg_rate", fmt(w["eta_ref"]), "cycles",
        f"95% CI [{fmt(w['eta_ref_ci'][0])}, {fmt(w['eta_ref_ci'][1])}]", "severson", wloc,
        "fitted_to_dataset", "yes", wnote)
    add("P28", "severson_weibull_ln_eta_slope_per_1C", fmt(w["b"]), "ln(cycles) per C",
        f"SE={fmt(w['b_se'])}; 95% CI [{fmt(w['b_ci'][0])}, {fmt(w['b_ci'][1])}]", "severson", wloc,
        "fitted_to_dataset", "yes", wnote + "; compare OLS slope P06")
    fade = severson_fade_curve(rep, s)
    write_csv(fade, os.path.join(TABLE_DIR, "severson_normalized_fade_curve.csv"))
    add("P29", "normalized_fade_curve_health_vs_fraction_of_life", "table (21 points, f = 0 to 1)",
        "health = Q / 1.1 Ah", "5th-95th percentile band in table", "severson",
        "outputs/capacity_curves.csv (merged cycles, 124 cells); outputs/tables/severson_normalized_fade_curve.csv",
        "fitted_to_dataset", "yes",
        "Added after Phase 1 approval. Defined only up to end of life (f <= 1): Severson cells stop cycling at "
        "EOL, so health after EOL is not available. LFP curve shape applied to LCO is an extrapolation")

    # Tahir 2024, Table 11 (CCCV vs 5SCC, LFP 2.6 Ah, average 2.262C)
    tloc11 = "papers/Tahir_2024_JEnergyStorage_MSCC.pdf, Table 11 (p. 10)"
    tnote = "LFP 2.6 Ah cylindrical cell (Table 1); LFP-to-LCO extrapolation; both profiles average 2.262C"
    for pid, name, val, unit, temp in [
        ("P12", "cccv_charge_time_2.262C_25C", 1758, "s", 25), ("P13", "mscc5_charge_time_2.262C_25C", 1578, "s", 25),
        ("P14", "cccv_charge_time_2.262C_35C", 1697, "s", 35), ("P15", "mscc5_charge_time_2.262C_35C", 1571, "s", 35),
        ("P16", "cccv_max_surface_temp_rise_25C", 7.8, "degC", 25), ("P17", "mscc5_max_surface_temp_rise_25C", 7.7, "degC", 25),
        ("P18", "cccv_avg_surface_temp_rise_25C", 4.1, "degC", 25), ("P19", "mscc5_avg_surface_temp_rise_25C", 5.5, "degC", 25),
        ("P20", "cccv_max_surface_temp_rise_35C", 7.3, "degC", 35), ("P21", "mscc5_max_surface_temp_rise_35C", 7.4, "degC", 35),
    ]:
        add(pid, name, val, unit, "single test; no replicate uncertainty reported", "tahir", tloc11,
            "read_from_paper", "yes", tnote)
    add("P22", "mscc5_to_cccv_charge_time_ratio_25C", fmt(1578 / 1758), "ratio",
        "derived from P12, P13; no uncertainty reported", "tahir", tloc11, "read_from_paper", "yes",
        tnote + "; text says 10.2% faster (consistent)")
    add("P23", "mscc5_to_cccv_charge_time_ratio_35C", fmt(1571 / 1697), "ratio",
        "derived from P14, P15; no uncertainty reported", "tahir", tloc11, "read_from_paper", "yes",
        tnote + "; NOTE: table values give 7.4% faster, paper text says 7.2%")

    # CALCE PL Readme facts
    plloc = "data/calce_pl/SOC_20-80_HalfC.zip and SOC_20-80_2C.zip, Readme.txt"
    add("P24", "calce_pl_test_ambient_temperature", "25 +/- 2", "degC", "+/- 2 degC as stated", "calce_pl", plloc,
        "read_from_paper", "yes", "LCO pouch 1.5 Ah (CALCE page); context for the charge-window effect")
    add("P25", "calce_pl_2C_cycling_temp_rise_lower_bound", "> 15", "degC above ambient", "lower bound only",
        "calce_pl", "data/calce_pl/SOC_20-80_2C.zip, Readme.txt", "read_from_paper", "yes",
        "2C DISCHARGE (charge at C/2), no cooling; not a charge-rate temperature rise")

    # Diao fits
    diao, dnotes = diao_fits(rep)
    write_csv(diao, os.path.join(TABLE_DIR, "diao_condition_fits.csv"))
    dloc = "data/DOE_Cap_v4.mat, condition {m} (row {m} of DOE_Cap); outputs/tables/diao_condition_fits.csv"
    dnote = ("Condition-to-stress mapping (temperature, charge/discharge extent) UNVERIFIED: Diao PDF not "
             "provided. Retention normalised to each cell's cycle-0 capacity; crossing by linear "
             "interpolation between 50-cycle checks. Do not use until mapping is verified.")
    i = 100
    for _, r in diao.iterrows():
        m = int(r.condition_id)
        for lab in ["80", "90"]:
            if pd.isna(r.get(f"beta_{lab}")):
                continue
            ext = dnote + " R(1000) extrapolates beyond the <=800-cycle test."
            unc_b = f"SE={fmt(r[f'beta_{lab}_se'])}; 95% CI [{fmt(r[f'beta_{lab}_ci_lo'])}, {fmt(r[f'beta_{lab}_ci_hi'])}]"
            unc_e = f"SE={fmt(r[f'eta_{lab}_se'])}; 95% CI [{fmt(r[f'eta_{lab}_ci_lo'])}, {fmt(r[f'eta_{lab}_ci_hi'])}]"
            cens = f"; failures {int(r[f'n_fail_{lab}'])}/{int(r.n_cells_used)} (rest right-censored)"
            add(f"D{i}", f"weibull_beta_cycles_to_{lab}pct_cond{m}", fmt(r[f"beta_{lab}"]), "-", unc_b + cens,
                "diao", dloc.format(m=m), "fitted_to_dataset", "no", ext)
            add(f"D{i + 1}", f"weibull_eta_cycles_to_{lab}pct_cond{m}", fmt(r[f"eta_{lab}"]), "cycles", unc_e + cens,
                "diao", dloc.format(m=m), "fitted_to_dataset", "no", ext)
            i += 2

    # UNVERIFIED (cannot be sourced from provided files)
    unv = [
        ("U01", "cycles_to_10pct_loss_by_ambient_temperature_10_to_60C", "diao", "Diao PDF condition matrix (not provided)",
         "Per-condition values exist (outputs/tables/diao_condition_fits.csv) but which condition is which temperature is unknown"),
        ("U02", "fade_rate_acceleration_after_knee_by_temperature", "diao", "Diao PDF (not provided)",
         "Per-condition knee slope ratios computed in diao_condition_fits.csv; mapping to temperature unknown"),
        ("U03", "temperature_x_charge_extent_interaction", "diao", "Diao PDF condition matrix (not provided)", ""),
        ("U04", "charge_window_effect_20_80_vs_0_100", "saxena", "Saxena 2016 PDF (not provided); CALCE PL .mat "
         "data stored as MATLAB table objects, not readable with h5py/numpy/pandas/scipy", ""),
        ("U05", "charge_rate_effect_on_cycle_life_18650", "keil", "Keil & Jossen 2016 PDF (not provided)", ""),
        ("U06", "cell_temp_rise_vs_C_rate_natural_vs_forced_convection", "huang", "Huang 2019 PDF (not provided)",
         "Huang cell is NMC622 2 Ah pouch at room temperature (per indexing pages), so LCO extrapolation would apply"),
        ("U07", "multistage_profile_effect_on_cycle_life", "liu", "Liu & Luo 2010 PDF (not provided)",
         "Tahir 2024 (provided) reports no ageing test, so it cannot supply this"),
        ("U08", "diao_cell_nominal_capacity_and_EOL_definition", "diao", "Diao PDF (not provided)",
         "Fits use each cell's own cycle-0 capacity as the reference"),
    ]
    for id_, name, cite, loc, note in unv:
        add(id_, name, "", "", "", cite, loc, "", "no", ("UNVERIFIED - do not use. " + note).strip())
    rows.append(dict(zip(COLUMNS, ["U09", "google_pixel_rated_cycles", "", "", "", "no primary source supplied",
                                   "", "", "no", "UNVERIFIED - do not use (no primary source provided)"])))

    params = pd.DataFrame(rows, columns=COLUMNS)
    write_csv(params, os.path.join(OUT_DIR, "parameters.csv"))
    rep(f"Wrote outputs/parameters.csv: {len(params)} rows "
        f"({(params.verified == 'yes').sum()} verified, {(params.verified == 'no').sum()} not verified)")
    for n in dnotes + tnotes:
        rep(f"NOTE: {n}")
    rep.save(os.path.join(OUT_DIR, "parameters_log.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
