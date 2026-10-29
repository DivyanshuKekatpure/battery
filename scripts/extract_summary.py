"""Extract a per-cell summary table and long-format capacity curves from the
Severson et al. (2019) / Attia et al. (2020) MATLAB v7.3 batch files.

Reads data/raw/*.mat (read-only), writes:
  outputs/cell_summary.csv
  outputs/capacity_curves.csv
  outputs/batch_report.txt

Conventions (confirmed by inspecting the files with scripts/inspect_structure.py):
  - batch/summary/<field> arrays are (1, n_cycles); summary/cycle holds the cycle number.
  - Exact 0 is used as a 'not measured' placeholder: cycle 1 is all zeros in the
    2017/2018 batches, and IR is all zeros in every 2019-01-24 cell. Zeros are
    therefore excluded from means and from the 80% crossing search (and counted).
    An all-zero field is treated as not recorded and left blank.
  - summary/chargetime is in minutes (no unit metadata; inferred from magnitude:
    a 3.6C-to-80% step gives 0.8/3.6 h = 13.33 min, matching stored values).
  - If summary/cycle is shorter than the data arrays, trailing data values with no
    cycle number are dropped (and reported) rather than assigned a guessed cycle.
  - Values are never filled or estimated; missing/empty/all-NaN fields stay blank.
"""
import glob
import os
import re
import sys

import h5py
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "raw")
OUT_DIR = os.path.join(ROOT, "outputs")

NOMINAL_AH = 1.1
EOL_AH = 0.8 * NOMINAL_AH  # 0.88 Ah
WINDOW = (2, 100)
DISAGREE_FRAC = 0.05

TWO_STEP_RE = re.compile(r"^(\d+(?:\.\d+)?)C\((\d+(?:\.\d+)?)%\)-(\d+(?:\.\d+)?)C$")

SUMMARY_COLUMNS = [
    "batch", "cell_id", "charge_policy_raw", "step1_rate_C", "switch_soc_percent",
    "step2_rate_C", "cycle_life", "cycle_life_check", "n_cycles_recorded",
    "mean_charge_time_min", "mean_Tmax_C", "max_Tmax_C", "mean_Tavg_C", "mean_IR_ohm",
    "temperature_available",
]


class Report:
    """Print to stdout and collect lines for outputs/batch_report.txt."""

    def __init__(self):
        self.lines = []

    def __call__(self, *parts):
        line = " ".join(str(p) for p in parts)
        print(line)
        self.lines.append(line)

    def save(self, path):
        write_text(path, "\n".join(self.lines) + "\n")


def write_text(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(text)
    os.replace(tmp, path)


def write_csv(df, path):
    # Write to a temp file and rename, so a failure never clobbers an earlier output.
    tmp = path + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


def is_empty(obj):
    return bool(obj.attrs.get("MATLAB_empty", 0))


def read_string(f, ref):
    obj = f[ref]
    if is_empty(obj):
        return None
    return "".join(chr(c) for c in obj[()].flatten())


def read_array(f, ref):
    obj = f[ref]
    if is_empty(obj):
        return np.array([], dtype=float)
    return np.asarray(obj[()], dtype=float).flatten()


def field_status(arr):
    """Classify a summary field for the missing-data check."""
    if arr is None:
        return "missing"
    if arr.size == 0:
        return "empty"
    if np.all(np.isnan(arr)):
        return "all_nan"
    if np.all((arr == 0) | np.isnan(arr)):
        return "all_zero"
    return "ok"


def parse_policy(policy):
    m = TWO_STEP_RE.match(policy or "")
    if not m:
        return None, None, None
    return float(m.group(1)), float(m.group(2)), float(m.group(3))


def window_values(cycle, values):
    if values is None or values.size == 0:
        return np.array([], dtype=float)
    mask = (cycle >= WINDOW[0]) & (cycle <= WINDOW[1])
    return values[mask]


def nanstat(func, arr):
    """Statistic over finite, non-zero values (0 is a placeholder in these files)."""
    valid = arr[np.isfinite(arr) & (arr != 0)] if arr.size else arr
    return float(func(valid)) if valid.size else None


def first_crossing(cycle, qd):
    """First recorded cycle whose discharge capacity is finite, non-zero and below 0.88 Ah.

    Returns (cycle or None, number of exact-zero placeholder values skipped, excluding cycle 1).
    """
    valid = np.isfinite(qd)
    zeros = valid & (qd == 0)
    candidates = valid & ~zeros & (qd < EOL_AH)
    idx = np.flatnonzero(candidates)
    return (float(cycle[idx[0]]) if idx.size else None), int((zeros & (cycle >= 2)).sum())


def extract_file(path, batch_index):
    rows, curves, notes = [], [], []
    with h5py.File(path, "r") as f:
        batch_date = read_string(f, f["batch_date"].ref) if "batch_date" in f else None
        file_date = os.path.basename(path)[:10]
        if batch_date != file_date:
            notes.append(f"batch_date in file ({batch_date!r}) differs from filename date ({file_date})")
        label = batch_date or file_date
        b = f["batch"]
        n_cells = b["summary"].shape[0]

        for i in range(n_cells):
            cell_id = f"b{batch_index}c{i}"
            policy = read_string(f, b["policy_readable"][i, 0]) if "policy_readable" in b else None
            s1, soc, s2 = parse_policy(policy)

            cl = read_array(f, b["cycle_life"][i, 0]) if "cycle_life" in b else np.array([])
            cycle_life = float(cl[0]) if cl.size and np.isfinite(cl[0]) else None

            summ = f[b["summary"][i, 0]]
            fields = {k: (np.asarray(summ[k][()], dtype=float).flatten() if k in summ else None)
                      for k in ["cycle", "QDischarge", "chargetime", "Tmax", "Tavg", "IR"]}
            if fields["cycle"] is None or fields["cycle"].size == 0:
                raise ValueError(f"{cell_id}: summary/cycle missing or empty; cannot assign cycle numbers")
            cycle = fields["cycle"]
            for k in ["QDischarge", "chargetime", "Tmax", "Tavg", "IR"]:
                a = fields[k]
                if a is not None and a.size > cycle.size:
                    notes.append(f"{cell_id}: {k} has {a.size} values but summary/cycle has {cycle.size}; "
                                 f"dropped trailing value(s) {a[cycle.size:].tolist()} with no cycle number")
                    fields[k] = a[:cycle.size]
                elif a is not None and 0 < a.size < cycle.size:
                    raise ValueError(f"{cell_id}: {k} shorter ({a.size}) than summary/cycle ({cycle.size})")
            n = len(fields["QDischarge"]) if fields["QDischarge"] is not None else 0

            qd = fields["QDischarge"] if fields["QDischarge"] is not None else np.array([])
            check, n_zero_qd = first_crossing(cycle, qd) if qd.size else (None, 0)
            if n_zero_qd:
                notes.append(f"{cell_id}: {n_zero_qd} cycle(s) >= 2 with QDischarge exactly 0 (excluded from 80% search)")
            qd_tail = qd[np.isfinite(qd) & (qd != 0)]
            last_qd = float(qd_tail[-1]) if qd_tail.size else None

            w = {k: window_values(cycle, fields[k]) for k in ["chargetime", "Tmax", "Tavg", "IR"]}
            temp_ok = any(field_status(fields[k]) == "ok" and np.any(np.isfinite(w[k]) & (w[k] != 0))
                          for k in ["Tmax", "Tavg"])

            rows.append({
                "batch": label, "cell_id": cell_id, "charge_policy_raw": policy,
                "step1_rate_C": s1, "switch_soc_percent": soc, "step2_rate_C": s2,
                "cycle_life": cycle_life, "cycle_life_check": check,
                "n_cycles_recorded": n,
                "mean_charge_time_min": nanstat(np.mean, w["chargetime"]),
                "mean_Tmax_C": nanstat(np.mean, w["Tmax"]),
                "max_Tmax_C": nanstat(np.max, w["Tmax"]),
                "mean_Tavg_C": nanstat(np.mean, w["Tavg"]),
                "mean_IR_ohm": nanstat(np.mean, w["IR"]),
                "temperature_available": temp_ok,
                # helper columns for the report only (dropped before writing)
                "_status": {k: field_status(fields[k]) for k in ["chargetime", "Tmax", "Tavg", "IR"]},
                "_window_n": int(((cycle >= WINDOW[0]) & (cycle <= WINDOW[1])).sum()),
                "_last_cycle": float(cycle[-1]),
                "_last_qd": last_qd,
                "_window_zeros": {k: int(np.sum(w[k] == 0)) for k in ["chargetime", "Tmax", "Tavg", "IR"]},
            })
            curves.append(pd.DataFrame({"batch": label, "cell_id": cell_id,
                                        "cycle": cycle.astype(int), "discharge_capacity_Ah": qd}))
    return rows, curves, notes


def run_checks(df, rep):
    def section(title, fn):
        rep("")
        rep("=" * 78)
        rep(title)
        rep("=" * 78)
        try:
            fn()
        except Exception as exc:  # keep going; never lose the other checks
            rep(f"CHECK FAILED: {type(exc).__name__}: {exc}")

    def c1():
        for batch, g in df.groupby("batch"):
            rep(f"{batch}: {len(g)} cells")
        rep(f"TOTAL: {len(df)} cells")

    def c2():
        both = df.dropna(subset=["cycle_life", "cycle_life_check"])
        rel = (both["cycle_life_check"] - both["cycle_life"]).abs() / both["cycle_life"]
        bad = both[rel > DISAGREE_FRAC]
        rep(f"Cells with both values: {len(both)}; disagreeing by > {DISAGREE_FRAC:.0%}: {len(bad)}")
        for _, r in bad.iterrows():
            rep(f"  {r.cell_id:7s} {r.batch}  cycle_life={r.cycle_life:g}  check={r.cycle_life_check:g}  "
                f"recorded={r.n_cycles_recorded}  policy={r.charge_policy_raw}")
        diffs = (both["cycle_life_check"] - both["cycle_life"]).value_counts().sort_index()
        rep("Distribution of (cycle_life_check - cycle_life) among agreeing+disagreeing cells (top 10):")
        for d, c in diffs.sort_values(ascending=False).head(10).items():
            rep(f"  diff {d:+g}: {c} cells")
        rep("")
        rep("Cells with cycle_life BLANK in the file:")
        for _, r in df[df["cycle_life"].isna()].iterrows():
            rep(f"  {r.cell_id:7s} {r.batch}  check={r.cycle_life_check}  recorded={r.n_cycles_recorded}  "
                f"last QDischarge={r._last_qd:.4f} Ah")

        # Cells whose capacity never drops below 0.88 Ah in the file but which have a stored cycle_life.
        nocross = df[df["cycle_life"].notna() & df["cycle_life_check"].isna()].copy()
        nocross["plus_one"] = nocross["cycle_life"] == nocross["_last_cycle"] + 1
        near = nocross[nocross["_last_qd"] < EOL_AH + 0.005]
        far = nocross[nocross["_last_qd"] >= EOL_AH + 0.005]
        rep("")
        rep(f"Cells never below {EOL_AH:.2f} Ah in the file but with a stored cycle_life: {len(nocross)} "
            f"(stored cycle_life == last recorded cycle + 1 for {int(nocross.plus_one.sum())} of them)")
        rep(f"  (a) data ends just above {EOL_AH:.2f} Ah (last value < {EOL_AH + 0.005:.3f}), i.e. the file stops "
            f"at the last cycle before EOL: {len(near)} cells")
        rep("      " + ", ".join(near.cell_id))
        rep(f"  (b) data ends well above {EOL_AH:.2f} Ah, so the stored cycle_life CANNOT be verified from this "
            f"file's capacity data: {len(far)} cells")
        for _, r in far.iterrows():
            rep(f"      {r.cell_id:7s} {r.batch}  cycle_life={r.cycle_life:g}  last cycle={r._last_cycle:g}  "
                f"last QDischarge={r._last_qd:.4f} Ah  policy={r.charge_policy_raw}")

    def c3():
        fields = ["Tmax", "Tavg", "chargetime", "IR"]
        for batch, g in df.groupby("batch"):
            rep(f"{batch} ({len(g)} cells):")
            for k in fields:
                st = g["_status"].map(lambda s: s[k]).value_counts().to_dict()
                zeros = int(g["_window_zeros"].map(lambda z: z[k] > 0).sum())
                rep(f"  {k:10s} status counts={st}  cells with some exact 0 in cycles 2-100 "
                    f"(excluded from means): {zeros}")
            short = g[g["_window_n"] < WINDOW[1] - WINDOW[0] + 1]
            if len(short):
                rep(f"  cells with fewer than 99 cycles in the 2-100 window: "
                    + ", ".join(f"{r.cell_id}({r._window_n})" for _, r in short.iterrows()))
            rep(f"  temperature_available: {int(g.temperature_available.sum())}/{len(g)} cells")

    def c4():
        stats = df.groupby("batch")["cycle_life"].agg(["count", "min", "median", "mean", "max", "std"])
        stats["n_blank"] = df.groupby("batch")["cycle_life"].apply(lambda s: s.isna().sum())
        rep(stats.round(1).to_string())

    def c5():
        g = df.assign(step1=df["step1_rate_C"].map(lambda v: "unparsed" if pd.isna(v) else f"{v:g}C"))
        out = g.groupby("step1").agg(n_cells=("cell_id", "size"),
                                     mean_charge_time_min=("mean_charge_time_min", "mean"),
                                     mean_Tmax_C=("mean_Tmax_C", "mean"),
                                     n_with_Tmax=("mean_Tmax_C", "count"))
        order = sorted(out.index, key=lambda s: (s == "unparsed", float(s[:-1]) if s != "unparsed" else 0))
        rep(out.loc[order].round(2).to_string())

    def c6():
        have = df.dropna(subset=["cycle_life"]).sort_values("cycle_life")
        cols = ["cell_id", "batch", "cycle_life", "cycle_life_check", "charge_policy_raw"]
        rep("Shortest (stored cycle_life):")
        rep(have[cols].head(3).to_string(index=False))
        rep("Longest (stored cycle_life):")
        rep(have[cols].tail(3).iloc[::-1].to_string(index=False))

    section("1. Cells per batch", c1)
    section(f"2. cycle_life vs cycle_life_check (first cycle with non-zero QDischarge < {EOL_AH:.2f} Ah)", c2)
    section("3. Missing / empty / all-NaN summary fields per batch (status per cell)", c3)
    section("4. cycle_life per batch (stored value, blanks excluded)", c4)
    section("5. Mean charge time and mean Tmax by step1_rate_C (cycles 2-100)", c5)
    section("6. Three shortest and longest lives", c6)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rep = Report()
    paths = sorted(glob.glob(os.path.join(RAW_DIR, "*.mat")))
    rep(f"Input files ({len(paths)}):")
    for p in paths:
        rep(f"  {os.path.basename(p)}  {os.path.getsize(p):,} bytes")

    rows, curves, notes = [], [], []
    for idx, p in enumerate(paths, start=1):
        try:
            r, c, n = extract_file(p, idx)
        except Exception as exc:
            rep(f"EXTRACTION FAILED for {os.path.basename(p)}: {type(exc).__name__}: {exc}")
            continue
        rows += r
        curves += c
        notes += [f"[{os.path.basename(p)[:10]}] {x}" for x in n]

    if not rows:
        rep("No cells extracted; nothing written.")
        rep.save(os.path.join(OUT_DIR, "batch_report.txt"))
        return 1

    df = pd.DataFrame(rows)
    write_csv(df[SUMMARY_COLUMNS], os.path.join(OUT_DIR, "cell_summary.csv"))
    write_csv(pd.concat(curves, ignore_index=True), os.path.join(OUT_DIR, "capacity_curves.csv"))
    rep(f"Wrote outputs/cell_summary.csv ({len(df)} rows) and outputs/capacity_curves.csv")
    rep("Units: chargetime stored in minutes (inferred from magnitude, no unit metadata); "
        "T in degC; IR in ohm; capacity in Ah.")

    run_checks(df, rep)

    rep("")
    rep("=" * 78)
    rep(f"Extraction notes ({len(notes)})")
    rep("=" * 78)
    for n in notes:
        rep(f"  {n}")
    unparsed = df[df["step1_rate_C"].isna()]["charge_policy_raw"].value_counts(dropna=False)
    rep(f"Policies not parsed as simple two-step ({unparsed.sum()} cells):")
    for pol, c in unparsed.items():
        rep(f"  {pol!r}: {c}")

    rep.save(os.path.join(OUT_DIR, "batch_report.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
