"""Phase 4: analysis of outputs/sim_results.csv.

Writes tables to outputs/tables/ and figures to outputs/figures/, and prints every number to
outputs/analysis_report.txt.

1. Descriptive statistics by scenario
2. Factorial ANOVA (type III, effect coding, all interactions) on each response and on log life
3. Regression of log life on all factors with two-way interactions
4. Strategy comparison with paired bootstrap 95% CIs
5. Weibull reliability summary per strategy
6. Individuals (I-MR) control chart and capability on health at 500 cycles for the best strategy
"""
import itertools
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_parameters import weibull_derived, weibull_mle  # noqa: E402
from extract_summary import OUT_DIR, Report, write_csv  # noqa: E402
from svgplot import Plot, box_stats  # noqa: E402

SEED = 20261028
B_BOOT = 2000
TABLES = os.path.join(OUT_DIR, "tables")
FIGS = os.path.join(OUT_DIR, "figures")
FACTORS = ["charge_rate_C", "ambient_C", "charge_limit_pct", "method"]
SHORT = {"charge_rate_C": "rate", "ambient_C": "ambient", "charge_limit_pct": "limit", "method": "method"}
BASE = {"charge_rate_C": 1.0, "ambient_C": 25, "charge_limit_pct": 100, "method": "CCCV"}
LSL = 0.80                 # health spec: 80% at the rated cycle count
RATED_CYCLES = 500         # P01, Apple, iPhone 14 and earlier (matches the health_at_500 response)
STRATEGIES = {             # all at 3C and 25 degC ambient
    "normal_fast": {"charge_rate_C": 3.0, "ambient_C": 25, "charge_limit_pct": 100, "method": "CCCV"},
    "limit_80pct": {"charge_rate_C": 3.0, "ambient_C": 25, "charge_limit_pct": 80, "method": "CCCV"},
    "multistage": {"charge_rate_C": 3.0, "ambient_C": 25, "charge_limit_pct": 100, "method": "MSCC"},
}


# --------------------------------------------------------------------------- design matrices
def effect_columns(df, f):
    levels = sorted(df[f].unique(), key=str)
    last = levels[-1]
    return {f"{SHORT[f]}[{lv}]": np.where(df[f] == lv, 1.0, np.where(df[f] == last, -1.0, 0.0)) for lv in levels[:-1]}


def design(df, max_order, coding="effect"):
    """Columns grouped by term. coding='effect' (sum-to-zero) or 'treatment' (BASE levels)."""
    main = {}
    for f in FACTORS:
        if coding == "effect":
            main[f] = effect_columns(df, f)
        else:
            lv = [v for v in sorted(df[f].unique(), key=str) if v != BASE[f]]
            main[f] = {f"{SHORT[f]}[{v}]": (df[f] == v).astype(float).to_numpy() for v in lv}
    terms = {"Intercept": {"Intercept": np.ones(len(df))}}
    for k in range(1, max_order + 1):
        for combo in itertools.combinations(FACTORS, k):
            cols = {}
            for parts in itertools.product(*[main[f].items() for f in combo]):
                name = ":".join(p[0] for p in parts)
                cols[name] = np.prod([p[1] for p in parts], axis=0)
            terms[":".join(SHORT[f] for f in combo)] = cols
    return terms


def sse(X, y):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    return float(r @ r), beta


def anova_type3(df, response):
    d = df.dropna(subset=[response])
    y = d[response].to_numpy(float)
    terms = design(d, max_order=4)
    names = list(terms)
    X = np.column_stack([c for t in names for c in terms[t].values()])
    sse_full, _ = sse(X, y)
    df_err = len(y) - np.linalg.matrix_rank(X)
    out = []
    for t in names[1:]:
        Xr = np.column_stack([c for u in names if u != t for c in terms[u].values()])
        ss = max(sse(Xr, y)[0] - sse_full, 0.0)
        dft = len(terms[t])
        F = (ss / dft) / (sse_full / df_err) if sse_full > 0 else np.nan
        out.append({"response": response, "term": t, "df": dft, "SS": ss, "F": F,
                    "p": stats.f.sf(F, dft, df_err) if np.isfinite(F) else np.nan,
                    "partial_eta_sq": ss / (ss + sse_full) if (ss + sse_full) > 0 else np.nan,
                    "n_obs": len(y), "df_error": df_err, "SS_error": sse_full})
    return pd.DataFrame(out)


# --------------------------------------------------------------------------- helpers
def pick(df, spec):
    m = np.ones(len(df), bool)
    for k, v in spec.items():
        m &= df[k].to_numpy() == v
    return df[m].sort_values("battery").reset_index(drop=True)


def bootstrap_diff(a, b, stat, rng):
    """Paired bootstrap (common random numbers): resample battery indices jointly."""
    n = len(a)
    idx = rng.integers(0, n, size=(B_BOOT, n))
    d = np.array([stat(b[i]) - stat(a[i]) for i in idx])
    return float(stat(b) - stat(a)), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def main():
    os.makedirs(TABLES, exist_ok=True)
    os.makedirs(FIGS, exist_ok=True)
    rep = Report()
    rng = np.random.default_rng(SEED)
    rep(f"Phase 4 analysis. SEED={SEED} (bootstrap), B={B_BOOT}")
    df = pd.read_csv(os.path.join(OUT_DIR, "sim_results.csv"))
    df["log_cycles_to_80pct"] = np.log(df["cycles_to_80pct_health"])
    responses = ["minutes_to_80pct", "peak_temp_C", "cycles_to_80pct_health", "log_cycles_to_80pct",
                 "health_at_500", "health_at_1000"]

    # 1. descriptives ---------------------------------------------------------------
    def describe(g):
        row = {}
        for r in responses:
            v = g[r].dropna()
            row.update({f"{r}_n": len(v), f"{r}_mean": v.mean() if len(v) else np.nan,
                        f"{r}_sd": v.std(ddof=1) if len(v) > 1 else np.nan,
                        f"{r}_median": v.median() if len(v) else np.nan,
                        f"{r}_p05": v.quantile(0.05) if len(v) else np.nan,
                        f"{r}_p95": v.quantile(0.95) if len(v) else np.nan})
        row["pct_past_eol_at_500"] = 100 * g["past_eol_at_500"].mean()
        row["pct_past_eol_at_1000"] = 100 * g["past_eol_at_1000"].mean()
        return pd.Series(row)
    desc = df.groupby(["scenario_id"] + FACTORS).apply(describe, include_groups=False).reset_index()
    write_csv(desc, os.path.join(TABLES, "p4_1_descriptives_by_scenario.csv"))
    rep("\n1. DESCRIPTIVES (selected columns; full table in p4_1_descriptives_by_scenario.csv)")
    cols = FACTORS + ["minutes_to_80pct_mean", "peak_temp_C_mean", "cycles_to_80pct_health_median",
                      "health_at_500_mean", "pct_past_eol_at_500", "health_at_1000_mean", "pct_past_eol_at_1000"]
    rep(desc[desc["ambient_C"] == 25][cols].round(3).to_string(index=False))
    rep("(Ambient 10 and 40 degC rows differ only in MSCC charge time and in peak temperature at 3C.)")

    # 2. ANOVA ------------------------------------------------------------------------
    rep("\n2. ANOVA (type III, effect coding, all interactions)")
    an = pd.concat([anova_type3(df, r) for r in responses if r != "peak_temp_C"], ignore_index=True)
    write_csv(an, os.path.join(TABLES, "p4_2_anova.csv"))
    for r, g in an.groupby("response", sort=False):
        rep(f"-- {r} (n={g.n_obs.iloc[0]}, df_error={g.df_error.iloc[0]}, SS_error={g.SS_error.iloc[0]:.6g})")
        show = g[(g.partial_eta_sq > 1e-6) | g.term.isin(["rate", "ambient", "limit", "method"])]
        rep(show[["term", "df", "SS", "F", "p", "partial_eta_sq"]].to_string(index=False,
            formatters={"SS": "{:.6g}".format, "F": "{:.6g}".format, "p": "{:.3g}".format,
                        "partial_eta_sq": "{:.4f}".format}))
        hidden = g[~g.index.isin(show.index)]
        if len(hidden):
            rep(f"   {len(hidden)} further interaction terms have partial eta^2 <= 1e-6 (see CSV)")
    rep("-- peak_temp_C: no ANOVA. It is deterministic within a scenario and only defined at 3C (decision D009).")

    # 3. regression ---------------------------------------------------------------------
    rep("\n3. REGRESSION: log(cycles to 80%) ~ all factors + two-way interactions (treatment coding; "
        "baseline 1C, 25 degC, 100%, CCCV)")
    terms = design(df, max_order=2, coding="treatment")
    names = [c for t in terms for c in terms[t]]
    X = np.column_stack([c for t in terms for c in terms[t].values()])
    y = df["log_cycles_to_80pct"].to_numpy()
    s_full, beta = sse(X, y)
    n, p = X.shape
    rank = np.linalg.matrix_rank(X)
    sigma2 = s_full / (n - rank)
    cov = sigma2 * np.linalg.pinv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    tcrit = stats.t.ppf(0.975, n - rank)
    coef = pd.DataFrame({"term": names, "estimate": beta, "SE": se, "ci_lo": beta - tcrit * se,
                         "ci_hi": beta + tcrit * se,
                         "t": np.where(se > 0, beta / np.where(se > 0, se, 1), np.nan)})
    coef["p"] = 2 * stats.t.sf(np.abs(coef["t"]), n - rank)
    sst = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - s_full / sst
    adj = 1 - (1 - r2) * (n - 1) / (n - rank)
    write_csv(coef, os.path.join(TABLES, "p4_3_regression_log_life.csv"))
    rep(coef.round(5).to_string(index=False))
    fitted = X @ beta
    resid = y - fitted
    ad = stats.anderson(resid[rng.choice(n, 5000, replace=False)], dist="norm")
    lev = stats.levene(*[resid[df.scenario_id == s] for s in sorted(df.scenario_id.unique())])
    diag = {"n": n, "rank": rank, "R2": r2, "adj_R2": adj, "resid_sd": float(np.sqrt(sigma2)),
            "resid_skew": float(stats.skew(resid)), "resid_excess_kurtosis": float(stats.kurtosis(resid)),
            "anderson_darling_stat_n5000": float(ad.statistic), "AD_crit_1pct": float(ad.critical_values[-1]),
            "levene_W_across_scenarios": float(lev.statistic), "levene_p": float(lev.pvalue)}
    write_csv(pd.DataFrame([diag]), os.path.join(TABLES, "p4_3_regression_diagnostics.csv"))
    rep(f"R2={r2:.4f}, adj R2={adj:.4f}, residual SD={np.sqrt(sigma2):.4f}, skew={diag['resid_skew']:.3f}, "
        f"excess kurtosis={diag['resid_excess_kurtosis']:.3f}, Anderson-Darling (n=5000)={ad.statistic:.2f} "
        f"(1% critical {ad.critical_values[-1]:.3f}), Levene W={lev.statistic:.4g} p={lev.pvalue:.3g}")
    sub = rng.choice(n, 3000, replace=False)
    pl = Plot("Residuals vs fitted: log cycles-to-80% regression", "Fitted log(cycles)", "Residual log(cycles)",
              subtitle="3,000 of 36,000 points; three vertical bands = the three charge rates")
    pl.scatter(fitted[sub], resid[sub], color="#2563eb")
    pl.hline(0, label="0")
    pl.save(os.path.join(FIGS, "p4_3_residuals_vs_fitted.png"))
    q = np.sort(resid[sub])
    th = stats.norm.ppf((np.arange(1, q.size + 1) - 0.5) / q.size) * np.sqrt(sigma2)
    pl = Plot("Normal Q-Q plot of regression residuals", "Theoretical normal quantile (log cycles)",
              "Sample quantile (log cycles)", subtitle="Left tail falls below the line: Weibull life gives a skewed log residual")
    pl.scatter(th, q, color="#2563eb")
    pl.line([th.min(), th.max()], [th.min(), th.max()], color="#dc2626", dash="6,4", width=1.6)
    pl.save(os.path.join(FIGS, "p4_3_residual_qq.png"))

    # 4. strategy comparison ---------------------------------------------------------------
    rep("\n4. STRATEGY COMPARISON (3C, 25 degC; paired bootstrap, B=2000)")
    strat = {k: pick(df, v) for k, v in STRATEGIES.items()}
    rows = []
    for k in ["limit_80pct", "multistage"]:
        for resp, lab in [("cycles_to_80pct_health", "median cycles to 80%"), ("minutes_to_80pct", "median minutes to 80%")]:
            est, lo, hi = bootstrap_diff(strat["normal_fast"][resp].to_numpy(), strat[k][resp].to_numpy(), np.median, rng)
            rows.append({"comparison": f"{k} - normal_fast", "quantity": lab, "difference": est, "ci_lo": lo, "ci_hi": hi})
    cmp_ = pd.DataFrame(rows)
    write_csv(cmp_, os.path.join(TABLES, "p4_4_strategy_comparison.csv"))
    rep(cmp_.round(4).to_string(index=False))
    rep("Life differences are zero by construction: limit and method have no verified life effect (D009).")
    pl = Plot("Minutes to 80% charge by strategy (3C, 25 °C)", "Strategy", "Minutes to 80% charge",
              subtitle="Boxes: interquartile range; whiskers: 5th-95th percentile; 1000 batteries each")
    pl.categorical_x(["Normal fast (CC-CV, 100%)", "80% limit (CC-CV)", "Multistage (100%)"])
    pl.boxes([0, 1, 2], [box_stats(strat[k]["minutes_to_80pct"]) for k in STRATEGIES], color="#2563eb")
    pl.save(os.path.join(FIGS, "p4_4_strategy_charge_time.png"))

    # 5. reliability -------------------------------------------------------------------------
    rep("\n5. RELIABILITY (Weibull MLE on simulated cycles to 80%; no censoring)")
    rel = []
    for k, d in strat.items():
        w = weibull_mle(d["cycles_to_80pct_health"].to_numpy(), [])
        dv = weibull_derived(w)
        rel.append({"strategy": k, "beta": w["beta"], "beta_ci_lo": w["beta_ci"][0], "beta_ci_hi": w["beta_ci"][1],
                    "eta": w["eta"], "eta_ci_lo": w["eta_ci"][0], "eta_ci_hi": w["eta_ci"][1],
                    "MTTF": dv["mttf"], "MTTF_se": dv["mttf_se"], "R500": dv["R500"], "R500_se": dv["R500_se"],
                    "R1000": dv["R1000"], "R1000_se": dv["R1000_se"]})
    rel = pd.DataFrame(rel)
    write_csv(rel, os.path.join(TABLES, "p4_5_reliability_by_strategy.csv"))
    rep(rel.round(4).to_string(index=False))
    t = np.linspace(0, 4000, 200)
    pl = Plot("Reliability R(t): probability of staying above 80% health", "Cycles", "R(t)",
              subtitle="Weibull fits per strategy (3C, 25 °C); the three curves coincide because life effects of limit and method are not modelled")
    for (_, r), dash in zip(rel.iterrows(), [None, "8,5", "2,4"]):
        pl.line(t, np.exp(-(t / r.eta) ** r.beta), label=r.strategy.replace("_", " "), dash=dash)
    pl.hline(np.exp(-(RATED_CYCLES / rel.eta.iloc[0]) ** rel.beta.iloc[0]), label=None)
    pl.ylim = (0, 1.02)
    pl.save(os.path.join(FIGS, "p4_5_reliability_curves.png"))

    # 6. control chart and capability ---------------------------------------------------------------
    best = (pd.DataFrame({k: {"median_life": d["cycles_to_80pct_health"].median(),
                              "median_t80": d["minutes_to_80pct"].median()} for k, d in strat.items()}).T
            .sort_values(["median_life", "median_t80"], ascending=[False, True]))
    bname = best.index[0]
    rep(f"\n6. CONTROL CHART: best strategy = {bname} (highest median life; ties broken by shortest median charge time)")
    d = strat[bname]
    h = d["health_at_500"].to_numpy()
    past = d["past_eol_at_500"].to_numpy()
    x = h[~past]
    mr = np.abs(np.diff(x))
    center, mrbar = x.mean(), mr.mean()
    sig_w = mrbar / 1.128
    ucl, lcl = center + 3 * sig_w, center - 3 * sig_w
    beyond = int(((x > ucl) | (x < lcl)).sum())
    side = np.sign(x - center)
    run = longest = 1
    for i in range(1, len(side)):
        run = run + 1 if side[i] == side[i - 1] and side[i] != 0 else 1
        longest = max(longest, run)
    sig_o = x.std(ddof=1)
    cpk = (center - LSL) / (3 * sig_w)
    ppk = (center - LSL) / (3 * sig_o)
    nonconf = (int(past.sum()) + int((x < LSL).sum())) / len(h)
    cc = {"strategy": bname, "n_batteries": len(h), "n_past_eol_excluded": int(past.sum()), "n_charted": len(x),
          "center_mean": center, "MR_bar": mrbar, "sigma_within": sig_w, "sigma_overall": sig_o, "UCL": ucl, "LCL": lcl,
          "points_beyond_limits": beyond, "longest_run_one_side": longest,
          "stable_rule1_and_run8": beyond == 0 and longest < 8, "LSL": LSL, "rated_cycles_for_spec": RATED_CYCLES,
          "Cp": np.nan, "Cpk": cpk, "Pp": np.nan, "Ppk": ppk, "observed_fraction_nonconforming": nonconf,
          "shapiro_p_first_500": float(stats.shapiro(x[:500]).pvalue)}
    write_csv(pd.DataFrame([cc]), os.path.join(TABLES, "p4_6_control_chart_capability.csv"))
    for k_, v in cc.items():
        rep(f"  {k_}: {v:.5g}" if isinstance(v, float) else f"  {k_}: {v}")
    rep("  Cp and Pp are not defined: the spec has a lower limit only (80% health at the rated 500 cycles, "
        "Apple iPhone 14 and earlier, P01).")
    pl = Plot(f"Individuals chart: health at 500 cycles, {bname.replace('_', ' ')} (3C, 25 °C)", "Battery (simulation order)",
              "Health at 500 cycles (Q / Q_nominal)",
              subtitle=f"{int(past.sum())} batteries past end of life before 500 cycles are not charted; LSL = 0.80")
    idx = np.flatnonzero(~past) + 1
    pl.line(idx, x, color="#2563eb", width=1.0)
    pl.scatter(idx[(x > ucl) | (x < lcl)], x[(x > ucl) | (x < lcl)], color="#dc2626", r=3.5, opacity=1)
    pl.hline(center, label=f"CL {center:.4f}", color="#111827", dash="none")
    pl.hline(ucl, label=f"UCL {ucl:.4f}", color="#dc2626")
    pl.hline(lcl, label=f"LCL {lcl:.4f}", color="#dc2626")
    pl.hline(LSL, label="LSL 0.80", color="#9333ea", dash="2,4")
    pl.save(os.path.join(FIGS, "p4_6_individuals_chart_health500.png"))

    # extra figures: main effects and sensitivity ----------------------------------------------------
    pl = Plot("Cycles to 80% health by charge rate", "Charge rate", "Cycles to 80% health",
              subtitle="Boxes: IQR; whiskers 5th-95th percentile; identical across ambient, limit and method (not modelled)")
    pl.categorical_x(["1C", "2C", "3C"])
    pl.boxes([0, 1, 2], [box_stats(df[(df.charge_rate_C == r) & (df.scenario_id % 4 == 1)]["cycles_to_80pct_health"])
                         for r in (1.0, 2.0, 3.0)], color="#2563eb")
    pl.hline(1000, label="Apple 1000 (iPhone 15 models)", color="#16a34a")
    pl.hline(500, label="Apple 500 (iPhone 14 and earlier)", color="#dc2626")
    pl.save(os.path.join(FIGS, "p4_1_life_by_rate.png"))
    m = df.groupby(["charge_rate_C", "method"])["minutes_to_80pct"].mean().unstack()
    pl = Plot("Mean minutes to 80% charge: rate x method", "Charge rate", "Minutes to 80% charge",
              subtitle="25 °C and 10 °C use Tahir's 25 °C ratio; 40 °C uses the 35 °C ratio (averaged over ambients here)")
    pl.categorical_x(["1C", "2C", "3C"])
    pl.line([0, 1, 2], m["CCCV"].to_numpy(), label="CC-CV", marker=True)
    pl.line([0, 1, 2], m["MSCC"].to_numpy(), label="Multistage", marker=True, dash="8,5")
    pl.save(os.path.join(FIGS, "p4_2_charge_time_interaction.png"))
    sens = pd.read_csv(os.path.join(OUT_DIR, "sim_results_sensitivity.csv"))
    sm = sens[sens.scenario_id % 4 == 1].groupby(["charge_rate_C", "b_setting"])["cycles_to_80pct_health"].median().unstack()
    write_csv(sm.reset_index(), os.path.join(TABLES, "p4_sensitivity_median_life_by_b.csv"))
    rep("\nSENSITIVITY: median cycles to 80% by rate with b at its 95% CI bounds")
    rep(sm.round(0).to_string())
    pl = Plot("Median cycles to 80% health: sensitivity to the rate slope b", "Charge rate", "Median cycles to 80% health",
              subtitle="Point: b = -0.531; bar: b at its 95% CI bounds (-0.723, -0.339)")
    pl.categorical_x(["1C", "2C", "3C"])
    pl.errorbars([0, 1, 2], sm["b_point"], sm[["b_ci_lower", "b_ci_upper"]].min(axis=1),
                 sm[["b_ci_lower", "b_ci_upper"]].max(axis=1), color="#2563eb")
    pl.hline(1000, label="Apple 1000", color="#16a34a")
    pl.hline(500, label="Apple 500", color="#dc2626")
    pl.save(os.path.join(FIGS, "p4_sensitivity_median_life.png"))

    rep.save(os.path.join(OUT_DIR, "analysis_report.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
