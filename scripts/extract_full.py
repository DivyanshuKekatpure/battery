"""Extract everything beyond the per-cell summary that a degradation / early-prediction
analysis needs from the Severson et al. (2019) / Attia et al. (2020) batch files.

Reads data/raw/*.mat (read-only), writes:
  outputs/cycle_summary.csv    every summary field for every recorded cycle of every cell
  outputs/early_features.csv   per-cell early-life features (Severson et al. 2019 style), cycles 2-100
  outputs/discharge_curves.h5  interpolated discharge curves on the shared 1000-point voltage grid
                               (Qdlin, Tdlin, dQdV) for cycles 1-100, every CURVE_STRIDE-th cycle
                               after that, and the last recorded cycle
  outputs/full_report.txt      extraction notes and missing-data counts

Not extracted: the raw within-cycle time series (V, I, T, Qc, Qd vs t). These are the bulk
of the 11 GB and stay in data/raw/; only the temperature integral below is derived from them.

Conventions (see also extract_summary.py, whose helpers and rules are reused):
  - Cycle-indexed entries in batch/cycles/* line up with batch/summary/cycle (index i -> cycle[i]).
  - Exact 0 is a 'not measured' placeholder: zeros are excluded from statistics and fits,
    and an all-zero field gives blank features. cycle_summary.csv keeps values as stored.
  - Units: capacity Ah, IR ohm, temperature degC, chargetime and raw t in minutes
    (no unit metadata in the files; inferred from magnitude).
  - Features that cannot be computed from the file (cycle missing, empty curve, too few
    valid points) are left blank and listed in the report. Nothing is filled or estimated.
"""
import glob
import os
import sys

import h5py
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_summary import (  # noqa: E402
    CHARGETIME_NOT_REACHED_MIN, OUT_DIR, RAW_DIR, Report, add_merged_cycles, apply_curation,
    is_empty, read_array, read_string, write_csv,
)

CURVE_STRIDE = 50
EARLY = (2, 100)
DQ_CYCLES = (10, 100)  # Delta Q(V) = Qdlin(cycle 100) - Qdlin(cycle 10)
MAX_CYCLE_SPAN_MIN = 300  # a full cycle is ~45-60 min; longer spans indicate a time-unit problem
SUMMARY_FIELDS = {
    "QCharge": "QCharge_Ah", "QDischarge": "QDischarge_Ah", "IR": "IR_ohm",
    "Tmax": "Tmax_C", "Tavg": "Tavg_C", "Tmin": "Tmin_C", "chargetime": "chargetime_min",
}

FEATURE_COLUMNS = [
    "batch", "cell_id", "charge_policy_raw", "cycle_life", "cycle_life_merged", "paper_status",
    # Delta Q(V) features (Qdlin cycle 100 minus cycle 10, 1000-point grid 3.5 -> 2.0 V)
    "dQ_100_10_min", "dQ_100_10_mean", "dQ_100_10_var", "dQ_100_10_skew", "dQ_100_10_kurt",
    "dQ_100_10_at_2V", "log10_abs_dQ_min", "log10_dQ_var",
    # discharge capacity fade features
    "Qd_cycle2_Ah", "Qd_cycle100_Ah", "Qd_max_minus_cycle2_Ah",
    "fade_slope_2_100_Ah_per_cycle", "fade_intercept_2_100_Ah",
    "fade_slope_91_100_Ah_per_cycle", "fade_intercept_91_100_Ah",
    # other features
    "chargetime_mean_cycles2_6_min", "IR_min_2_100_ohm", "IR_100_minus_2_ohm",
    "Tmax_max_2_100_C", "Tmin_min_2_100_C", "T_integral_2_100_degC_min",
]


def clean(a):
    """Finite, non-zero values only."""
    return a[np.isfinite(a) & (a != 0)]


def value_at(cycle, values, c):
    idx = np.flatnonzero(cycle == c)
    if not idx.size or values is None:
        return None
    v = values[idx[0]]
    return float(v) if np.isfinite(v) and v != 0 else None


def linfit(cycle, values, lo, hi):
    mask = (cycle >= lo) & (cycle <= hi) & np.isfinite(values) & (values != 0)
    if mask.sum() < 2:
        return None, None
    slope, intercept = np.polyfit(cycle[mask], values[mask], 1)
    return float(slope), float(intercept)


def read_curve(f, cycles_grp, key, i):
    if key not in cycles_grp or i >= cycles_grp[key].shape[0]:
        return None
    obj = f[cycles_grp[key][i, 0]]
    if is_empty(obj):
        return None
    a = np.asarray(obj[()], dtype=float).flatten()
    return a if a.size and np.any(np.isfinite(a)) else None


def dq_features(f, cyc, cycle, cell_id, notes):
    out = {}
    curves = []
    for c in DQ_CYCLES:
        idx = np.flatnonzero(cycle == c)
        q = read_curve(f, cyc, "Qdlin", idx[0]) if idx.size else None
        if q is None:
            notes.append(f"{cell_id}: Qdlin for cycle {c} missing or empty -> Delta Q features blank")
            return out
        curves.append(q)
    dq = curves[1] - curves[0]
    if not np.all(np.isfinite(dq)):
        notes.append(f"{cell_id}: Delta Q(V) has {int((~np.isfinite(dq)).sum())} non-finite points -> features blank")
        return out
    out.update({
        "dQ_100_10_min": float(dq.min()), "dQ_100_10_mean": float(dq.mean()),
        "dQ_100_10_var": float(np.var(dq)),
        # MATLAB conventions (as in the original papers): biased skewness, Pearson (non-excess) kurtosis
        "dQ_100_10_skew": float(stats.skew(dq)), "dQ_100_10_kurt": float(stats.kurtosis(dq, fisher=False)),
        "dQ_100_10_at_2V": float(dq[-1]),
        "log10_abs_dQ_min": float(np.log10(abs(dq.min()))) if dq.min() != 0 else None,
        "log10_dQ_var": float(np.log10(np.var(dq))) if np.var(dq) > 0 else None,
    })
    return out


def temperature_integral(f, cyc, cycle, cell_id, notes):
    """Sum over cycles 2-100 of the trapezoidal integral of raw T(t) (degC * min)."""
    total, missing, spans = 0.0, [], []
    for c in range(EARLY[0], EARLY[1] + 1):
        idx = np.flatnonzero(cycle == c)
        T = read_curve(f, cyc, "T", idx[0]) if idx.size else None
        t = read_curve(f, cyc, "t", idx[0]) if idx.size else None
        if T is None or t is None or T.size != t.size:
            missing.append(c)
            continue
        ok = np.isfinite(T) & np.isfinite(t)
        if ok.sum() < 2:
            missing.append(c)
            continue
        total += float(np.trapezoid(T[ok], t[ok]))
        spans.append(float(t[ok][-1] - t[ok][0]))
    long_spans = [s for s in spans if s > MAX_CYCLE_SPAN_MIN]
    if spans and np.median(spans) > MAX_CYCLE_SPAN_MIN:
        notes.append(f"{cell_id}: median raw t span over cycles 2-100 is {np.median(spans):.0f} "
                     f"(vs ~45-60 min for other cells); t may not be in minutes for this cell -> T_integral blank")
        return None
    if long_spans:
        notes.append(f"{cell_id}: {len(long_spans)} cycle(s) in 2-100 last longer than {MAX_CYCLE_SPAN_MIN} min "
                     f"(max {max(long_spans):.0f} min, likely a test pause); included in T_integral as recorded")
    if missing:
        notes.append(f"{cell_id}: raw T/t unusable for {len(missing)} of cycles 2-100 "
                     f"(e.g. {missing[:5]}) -> T_integral blank")
        return None
    return total


def curve_cycles(cycle):
    keep = (cycle <= EARLY[1]) | (cycle % CURVE_STRIDE == 0)
    keep[-1] = True
    return np.flatnonzero(keep)


def extract_file(path, batch_index, h5out, notes):
    summary_rows, feature_rows = [], []
    with h5py.File(path, "r") as f:
        label = read_string(f, f["batch_date"].ref) if "batch_date" in f else os.path.basename(path)[:10]
        b = f["batch"]
        if "Vdlin" in h5out:
            vd = read_array(f, b["Vdlin"][0, 0])
            if not np.array_equal(vd, h5out["Vdlin"][()]):
                notes.append(f"[{label}] Vdlin grid differs from the first batch's grid")
        else:
            h5out.create_dataset("Vdlin", data=read_array(f, b["Vdlin"][0, 0]))
            h5out["Vdlin"].attrs["units"] = "V"

        for i in range(b["summary"].shape[0]):
            cell_id = f"b{batch_index}c{i}"
            policy = read_string(f, b["policy_readable"][i, 0])
            cl = read_array(f, b["cycle_life"][i, 0])
            cycle_life = float(cl[0]) if cl.size and np.isfinite(cl[0]) else None

            summ = f[b["summary"][i, 0]]
            cycle = np.asarray(summ["cycle"][()], dtype=float).flatten()
            fields = {}
            for k in SUMMARY_FIELDS:
                if k not in summ:
                    notes.append(f"{cell_id}: summary/{k} missing")
                    fields[k] = np.full(cycle.size, np.nan)
                    continue
                a = np.asarray(summ[k][()], dtype=float).flatten()
                if a.size > cycle.size:
                    notes.append(f"{cell_id}: summary/{k} has {a.size - cycle.size} trailing value(s) with no "
                                 f"cycle number {a[cycle.size:].tolist()} -> dropped")
                    a = a[:cycle.size]
                elif a.size < cycle.size:
                    raise ValueError(f"{cell_id}: summary/{k} shorter ({a.size}) than summary/cycle ({cycle.size})")
                fields[k] = a

            summary_rows.append(pd.DataFrame({"batch": label, "cell_id": cell_id, "cycle": cycle.astype(int),
                                              **{SUMMARY_FIELDS[k]: fields[k] for k in SUMMARY_FIELDS}}))

            cyc = f[b["cycles"][i, 0]]
            if cyc["Qdlin"].shape[0] != cycle.size:
                notes.append(f"{cell_id}: cycles/Qdlin has {cyc['Qdlin'].shape[0]} entries vs "
                             f"{cycle.size} summary cycles; curves aligned by index for the common range")

            feat = {"batch": label, "cell_id": cell_id, "charge_policy_raw": policy, "cycle_life": cycle_life,
                    "n_cycles_recorded": cycle.size}
            if cycle.max() < EARLY[1]:
                notes.append(f"{cell_id}: only {int(cycle.max())} cycles recorded (< {EARLY[1]}) -> "
                             f"early features using cycle {EARLY[1]} blank")
            feat.update(dq_features(f, cyc, cycle, cell_id, notes))

            qd, ir, ct = fields["QDischarge"], fields["IR"], fields["chargetime"]
            early = (cycle >= EARLY[0]) & (cycle <= EARLY[1])
            q2, q100 = value_at(cycle, qd, 2), value_at(cycle, qd, 100)
            qe = clean(qd[early])
            s, c0 = linfit(cycle, qd, *EARLY)
            s91, c91 = linfit(cycle, qd, 91, 100)
            ct26 = clean(ct[(cycle >= 2) & (cycle <= 6)])
            ct26 = ct26[ct26 != CHARGETIME_NOT_REACHED_MIN]  # 'never reached 0.88 Ah' placeholder
            ire = clean(ir[early])
            ir2, ir100 = value_at(cycle, ir, 2), value_at(cycle, ir, 100)
            tmax, tmin = clean(fields["Tmax"][early]), clean(fields["Tmin"][early])
            feat.update({
                "Qd_cycle2_Ah": q2, "Qd_cycle100_Ah": q100,
                "Qd_max_minus_cycle2_Ah": float(qe.max() - q2) if qe.size and q2 is not None else None,
                "fade_slope_2_100_Ah_per_cycle": s, "fade_intercept_2_100_Ah": c0,
                "fade_slope_91_100_Ah_per_cycle": s91, "fade_intercept_91_100_Ah": c91,
                "chargetime_mean_cycles2_6_min": float(ct26.mean()) if ct26.size else None,
                "IR_min_2_100_ohm": float(ire.min()) if ire.size else None,
                "IR_100_minus_2_ohm": ir100 - ir2 if ir2 is not None and ir100 is not None else None,
                "Tmax_max_2_100_C": float(tmax.max()) if tmax.size else None,
                "Tmin_min_2_100_C": float(tmin.min()) if tmin.size else None,
                "T_integral_2_100_degC_min": temperature_integral(f, cyc, cycle, cell_id, notes),
            })
            feature_rows.append(feat)

            # interpolated curves for the selected cycles
            n_entries = min(cyc["Qdlin"].shape[0], cycle.size)
            sel = [j for j in curve_cycles(cycle) if j < n_entries]
            g = h5out.create_group(cell_id)
            g.attrs.update({"batch": label, "charge_policy_raw": policy or "",
                            "cycle_life": cycle_life if cycle_life is not None else np.nan})
            g.create_dataset("cycle", data=cycle[sel].astype(int))
            for key, name in [("Qdlin", "Qdlin_Ah"), ("Tdlin", "Tdlin_C"), ("discharge_dQdV", "dQdV_Ah_per_V")]:
                arr = np.full((len(sel), h5out["Vdlin"].size), np.nan, dtype=np.float32)
                n_missing = 0
                for row, j in enumerate(sel):
                    a = read_curve(f, cyc, key, j)
                    if a is None or a.size != arr.shape[1]:
                        n_missing += 1
                        continue
                    arr[row] = a
                if n_missing:
                    notes.append(f"{cell_id}: {key} empty/missing for {n_missing} of {len(sel)} exported cycles "
                                 f"(left as NaN rows)")
                g.create_dataset(name, data=arr, compression="gzip", compression_opts=4, shuffle=True)
    return summary_rows, feature_rows


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rep = Report()
    notes = []
    paths = sorted(glob.glob(os.path.join(RAW_DIR, "*.mat")))
    h5_path = os.path.join(OUT_DIR, "discharge_curves.h5")
    h5_tmp = h5_path + ".tmp"
    summary_rows, feature_rows = [], []
    with h5py.File(h5_tmp, "w") as h5out:
        h5out.attrs["description"] = (
            "Interpolated discharge curves on the shared Vdlin grid (3.5 -> 2.0 V, 1000 points). "
            f"Per cell group: cycle, Qdlin_Ah, Tdlin_C, dQdV_Ah_per_V for cycles 1-{EARLY[1]}, every "
            f"{CURVE_STRIDE}th cycle after that, and the last recorded cycle. NaN rows = empty in source.")
        for idx, p in enumerate(paths, start=1):
            rep(f"Reading {os.path.basename(p)} ...")
            try:
                s, fe = extract_file(p, idx, h5out, notes)
            except Exception as exc:
                rep(f"EXTRACTION FAILED for {os.path.basename(p)}: {type(exc).__name__}: {exc}")
                continue
            summary_rows += s
            feature_rows += fe
    if not feature_rows:
        rep("No cells extracted; existing outputs left untouched.")
        os.remove(h5_tmp)
        rep.save(os.path.join(OUT_DIR, "full_report.txt"))
        return 1
    os.replace(h5_tmp, h5_path)

    feats = apply_curation(pd.DataFrame(feature_rows))
    cs = add_merged_cycles(pd.concat(summary_rows, ignore_index=True),
                           feats.set_index("cell_id")["n_cycles_recorded"])
    feats = feats.reindex(columns=FEATURE_COLUMNS)
    write_csv(cs, os.path.join(OUT_DIR, "cycle_summary.csv"))
    write_csv(feats, os.path.join(OUT_DIR, "early_features.csv"))

    rep("")
    rep(f"cycle_summary.csv:   {len(cs):,} rows, {cs.cell_id.nunique()} cells")
    rep(f"early_features.csv:  {len(feats)} rows, {len(FEATURE_COLUMNS) - 6} features")
    rep(f"discharge_curves.h5: {os.path.getsize(h5_path) / 1e6:,.1f} MB")
    rep("")
    rep("Blank features per batch (count of cells):")
    blanks = feats.drop(columns=["cell_id", "charge_policy_raw"]).groupby("batch").agg(lambda s: s.isna().sum())
    blanks = blanks.loc[:, blanks.sum() > 0]
    rep(blanks.to_string() if blanks.size else "  none")
    rep("")
    rep(f"Extraction notes ({len(notes)}):")
    for n in notes:
        rep(f"  {n}")
    rep.save(os.path.join(OUT_DIR, "full_report.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
