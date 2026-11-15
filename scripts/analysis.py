"""Battery charging study: simple empirical analysis of the KIT dataset.

Everything here is read from the KIT v2 result data in data2/ (Luh & Blank, 2024,
DOI 10.35097/1969). The only number that does not come from the data is the
replacement price in PRICE_USD, which is used in the financial section.

Run:  .venv/bin/python -m scripts.analysis
"""
import csv
import hashlib
import io
import json
import math
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
BAG = ROOT / "data2"
DATA = BAG / "data" / "dataset"
OUT = ROOT / "outputs"
TABLES, FIGURES = OUT / "tables", OUT / "figures"

# ---------------------------------------------------------------- settings
NOMINAL_AH = 3.0          # nominal cell capacity, stated in KIT "Readme v2"
END_OF_LIFE = 0.80        # industry convention: battery is "worn out" below 80% of its starting capacity
CHECK_THRESHOLD = 0.70    # robustness check: does the conclusion change if "worn out" means 70%?
PRICE_USD = 99.0          # EXTERNAL: phone battery replacement fee (Burkhardt, 2024, 9to5Mac)
USAGE_PER_DAY = [0.5, 1.0, 1.5]   # SCENARIOS, not data: full charge cycles a phone owner uses per day
# KIT readme: temperature control failed on 27 May 2024; the last (manual) check-up ran without it.
MANUAL_CHECKUP_START = datetime(2024, 5, 29, tzinfo=timezone.utc).timestamp()

CELL_FILE = re.compile(r"_P(\d{3})_(\d)_S(\d{2})_C(\d{2})\.csv$")
RATE_LABEL = {1: "1/3C (slow)", 3: "1C (medium)", 5: "5/3C (fast)"}
CAP_LABEL = {90: "90% cap", 100: "100% (no cap)"}


# ---------------------------------------------------------------- 1. load
def verify_download():
    """Check every file against the MD5 checksums shipped with the download."""
    bad = []
    for line in (BAG / "manifest-md5.txt").read_text().splitlines():
        expected, rel = line.split(maxsplit=1)
        h = hashlib.md5()
        with (BAG / rel).open("rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        if h.hexdigest() != expected:
            bad.append(rel)
    if bad:
        raise SystemExit(f"Download is corrupted, re-download these files: {bad}")


def rows(z, name):
    with z.open(name) as f:
        yield from csv.DictReader(io.TextIOWrapper(f), delimiter=";")


def load_conditions():
    """Test conditions for every cell, from cfg.zip."""
    out = []
    with zipfile.ZipFile(DATA / "cfg.zip") as z:
        for name in z.namelist():
            m = CELL_FILE.search(name)
            if not m or int(m[1]) == 0:      # S20 = short side experiment, not extra cells
                continue
            p, rep, slave, channel = map(int, m.groups())
            c = next(rows(z, name))
            out.append(dict(
                cell=f"P{p:03}_{rep}", slave=slave, channel=channel,
                test_type={1: "calendar", 2: "cycling", 3: "profile"}[int(c["age_type"])],
                temp=int(float(c["age_temp"])),
                charge_C=float(c["I_chg_max_cyc_A"]) / NOMINAL_AH,
                discharge_C=abs(float(c["I_dischg_max_cyc_A"])) / NOMINAL_AH,
                v_min=float(c["V_min_cyc_V"]), v_max=float(c["V_max_cyc_V"])))
    return pd.DataFrame(out)


def load_stop_reasons():
    """Why each cell's test ended, from the KIT cell overview spreadsheet."""
    path = next(DATA.glob("Cycling*.xlsx"))
    sheet = load_workbook(path, read_only=True, data_only=True).worksheets[0]
    reasons = {}
    for row in sheet.values:      # the sheet lists cells in three side-by-side blocks
        for ident, reason in [(0, 2), (7, 10), (15, 19)]:
            v = row[ident]
            if isinstance(v, str) and (m := re.fullmatch(r"(\d{2}) - (\d{2})", v.strip())):
                reasons[tuple(map(int, m.groups()))] = str(row[reason] or "unknown")
    return reasons


def load_capacity_checks():
    """Standard capacity check-ups (full 1A discharge, 4.2V to 2.5V) for every cell."""
    def num(r, k):
        return float(r[k])
    out = []
    with zipfile.ZipFile(DATA / "cell_eocv2.zip") as z:
        for name in z.namelist():
            m = CELL_FILE.search(name)
            if not m or int(m[1]) == 0:
                continue
            cell = f"P{int(m[1]):03}_{int(m[2])}"
            for r in rows(z, name):
                is_reference = (math.isclose(num(r, "cyc_condition"), 2) and math.isclose(num(r, "cyc_charged"), 0)
                                and math.isclose(num(r, "v_min_target_V"), 2.5) and math.isclose(num(r, "v_max_target_V"), 4.2)
                                and math.isclose(num(r, "i_dischg_min_A"), -1) and math.isclose(num(r, "i_dischg_cutoff_A"), -0.15))
                if not is_reference:
                    continue
                out.append(dict(cell=cell, time_s=num(r, "timestamp_s"),
                                capacity_Ah=abs(num(r, "delta_q_dischg_Ah")),
                                # one equivalent full cycle = 3 Ah charged + 3 Ah discharged
                                cycles=(num(r, "total_q_chg_sum_Ah") + num(r, "total_q_dischg_sum_Ah")) / (2 * NOMINAL_AH),
                                temp_end=num(r, "t_end_degC")))
    return pd.DataFrame(out)


# ---------------------------------------------------------------- 2. prepare
def prepare():
    cond = load_conditions()
    reasons = load_stop_reasons()
    cond["stop_reason"] = [reasons[(s, c)] for s, c in zip(cond.slave, cond.channel)]
    # The study: cycling cells, fixed 1C discharge and fixed lower voltage, varying
    # charge rate x charge limit x temperature.
    study = cond[(cond.test_type == "cycling") & np.isclose(cond.discharge_C, 1) & np.isclose(cond.v_min, 3.249)].copy()
    study["rate"] = np.round(study.charge_C * 3).astype(int)            # 1, 3, 5 = 1/3C, 1C, 5/3C
    study["cap"] = np.where(study.v_max < 4.19, 90, 100)                # 4.092 V ~ 90% charge, 4.2 V = 100%
    assert len(study) == 72 and study.groupby(["temp", "rate", "cap"]).size().eq(3).all()

    checks = load_capacity_checks()
    checks = checks[checks.cell.isin(study.cell)].sort_values(["cell", "time_s"])
    checks["dropped"] = ""
    checks.loc[~checks.temp_end.between(20, 30), "dropped"] = "check-up not at room temperature"
    checks.loc[checks.time_s >= MANUAL_CHECKUP_START, "dropped"] = "final check-up after temperature-control failure"
    used = checks[checks.dropped == ""].copy()
    first = used.groupby("cell").first()
    used["cycles"] -= used.cell.map(first.cycles)                        # count from the first check-up
    used["retention"] = used.capacity_Ah / used.cell.map(first.capacity_Ah)
    used = used.merge(study[["cell", "temp", "rate", "cap", "stop_reason"]], on="cell")
    return study, checks, used


def cell_lives(study, used, threshold=END_OF_LIFE):
    """Cycles until each cell first measured below the threshold (default 80%) of its starting capacity."""
    out = []
    for cell, g in used.groupby("cell"):
        g = g.sort_values("cycles")
        below = np.flatnonzero(g.retention.to_numpy() < threshold)
        if len(below):
            i = below[0]
            lo, hi = g.cycles.iloc[i - 1], g.cycles.iloc[i]
            life, reached = (lo + hi) / 2, True
        else:
            lo, hi, life, reached = g.cycles.iloc[-1], np.nan, g.cycles.iloc[-1], False
        out.append(dict(cell=cell, last_check_before=lo, first_check_below=hi, life_cycles=life,
                        reached_80=reached, checkups=len(g), final_retention=g.retention.iloc[-1]))
    lives = study[["cell", "temp", "rate", "cap", "stop_reason"]].merge(pd.DataFrame(out), on="cell")
    lives["stopped_by_error"] = lives.stop_reason.str.contains("err", case=False)
    return lives


def condition_summary(lives):
    """Median of the 3 cells per condition. If a cell never reached 80% its life is
    'at least' its last check, so a median that depends on it is a lower bound."""
    out = []
    for (t, r, c), g in lives.groupby(["temp", "rate", "cap"]):
        g = g.sort_values("life_cycles")
        mid = g.iloc[1]
        out.append(dict(temp=t, rate=r, cap=c, median_life=mid.life_cycles, at_least=not mid.reached_80,
                        lowest=g.life_cycles.min(), highest=g.life_cycles.max(),
                        cells_reached_80=int(g.reached_80.sum()), cells_stopped_by_error=int(g.stopped_by_error.sum())))
    return pd.DataFrame(out)


def cap_comparison(summary):
    s = summary.set_index(["temp", "rate", "cap"])
    out = []
    for t in sorted(summary.temp.unique()):
        for r in (1, 3, 5):
            a, b = s.loc[(t, r, 90)], s.loc[(t, r, 100)]
            out.append(dict(temp=t, rate=r, life_90=a.median_life, life_90_at_least=a.at_least,
                            life_100=b.median_life, life_100_at_least=b.at_least,
                            extra_cycles=a.median_life - b.median_life,
                            times_longer=a.median_life / b.median_life,
                            clear=(not b.at_least) and a.lowest > b.highest,
                            # If the uncapped median is only a lower bound we cannot confirm which lasted longer.
                            confirmed=(not b.at_least) and a.median_life > b.median_life,
                            undecided=bool(b.at_least) and not (a.median_life < b.median_life and not a.at_least)))
    return pd.DataFrame(out)


def main_effects(lives):
    out = []
    for factor in ("rate", "cap", "temp"):
        for level, g in lives.groupby(factor):
            out.append(dict(factor=factor, level=level, cells=len(g), median_life=g.life_cycles.median(),
                            cells_not_reached_80=int((~g.reached_80).sum())))
    return pd.DataFrame(out)


def costs(summary, temp=25):
    """Yearly cost of battery wear = price x (cycles used per year / cycles the battery lasts)."""
    s = summary[summary.temp == temp]
    out = []
    for u in USAGE_PER_DAY:
        for row in s.itertuples():
            years = row.median_life / (u * 365)
            out.append(dict(usage_per_day=u, rate=row.rate, cap=row.cap, life_cycles=row.median_life,
                            at_least=row.at_least, battery_years=years, cost_per_year=PRICE_USD / years))
    df = pd.DataFrame(out)
    base = df.set_index(["usage_per_day", "rate", "cap"]).cost_per_year
    df["saving_per_year_vs_no_cap"] = [base[(u, r, 100)] - c for u, r, c in zip(df.usage_per_day, df.rate, df.cost_per_year)]
    return df


# ---------------------------------------------------------------- 3. figures
def figures(used, lives, summary, effects, cost):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    col = {90: "#1f77b4", 100: "#d62728"}
    FIGURES.mkdir(parents=True, exist_ok=True)

    # Fade curves, every condition
    fig, axes = plt.subplots(4, 3, figsize=(10, 10), sharey=True)
    for i, t in enumerate(sorted(used.temp.unique())):
        for j, r in enumerate((1, 3, 5)):
            ax = axes[i, j]
            for cell, g in used[(used.temp == t) & (used.rate == r)].groupby("cell"):
                c = int(g.cap.iloc[0])
                ax.plot(g.cycles, g.retention * 100, "-o", ms=2.5, lw=1, color=col[c],
                        label=CAP_LABEL[c] if cell.endswith("_1") else None)
                if "err" in g.stop_reason.iloc[0].lower():
                    ax.plot(g.cycles.iloc[-1], g.retention.iloc[-1] * 100, "x", color="k", ms=6)
            ax.axhline(80, color="grey", ls="--", lw=.8)
            ax.set_title(f"{t}°C, {RATE_LABEL[r]}")
            ax.set_ylim(50, 102)
            if j == 0: ax.set_ylabel("Capacity left (%)")
            if i == 3: ax.set_xlabel("Equivalent full cycles")
    axes[0, 0].legend(frameon=False)
    fig.suptitle("Measured capacity fade (dashed line = 80% end of life; x = test stopped by equipment error)")
    fig.tight_layout(); fig.savefig(FIGURES / "fade_all_conditions.png", dpi=150); plt.close(fig)

    # Fade curves at 25 C only (main report figure)
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.2), sharey=True)
    for j, r in enumerate((1, 3, 5)):
        ax = axes[j]
        for cell, g in used[(used.temp == 25) & (used.rate == r)].groupby("cell"):
            c = int(g.cap.iloc[0])
            ax.plot(g.cycles, g.retention * 100, "-o", ms=2.5, lw=1, color=col[c], label=CAP_LABEL[c] if cell.endswith("_1") else None)
            if "err" in g.stop_reason.iloc[0].lower():
                ax.plot(g.cycles.iloc[-1], g.retention.iloc[-1] * 100, "x", color="k", ms=6)
        ax.axhline(80, color="grey", ls="--", lw=.8); ax.set_title(f"25°C, {RATE_LABEL[r]}"); ax.set_xlabel("Equivalent full cycles")
    axes[0].set_ylabel("Capacity left (%)"); axes[0].legend(frameon=False)
    fig.tight_layout(); fig.savefig(FIGURES / "fade_25C.png", dpi=150); plt.close(fig)

    # Cycles to 80%: cap vs no cap, each dot a cell
    fig, axes = plt.subplots(1, 4, figsize=(11, 3.4), sharey=False)
    for i, t in enumerate(sorted(lives.temp.unique())):
        ax = axes[i]
        for k, r in enumerate((1, 3, 5)):
            for c, dx in ((100, -.15), (90, .15)):
                g = lives[(lives.temp == t) & (lives.rate == r) & (lives.cap == c)]
                m = summary[(summary.temp == t) & (summary.rate == r) & (summary.cap == c)].median_life.iloc[0]
                ax.bar(k + dx, m, width=.3, color=col[c], alpha=.35, label=CAP_LABEL[c] if (i, k) == (0, 0) else None)
                ax.scatter(np.full(len(g), k + dx), g.life_cycles, s=12, color=col[c],
                           marker=None, facecolors=[col[c] if x else "white" for x in g.reached_80], edgecolors=col[c], zorder=3)
        ax.set_xticks([0, 1, 2], ["1/3C", "1C", "5/3C"]); ax.set_title(f"{t}°C"); ax.set_xlabel("Charge rate")
    axes[0].set_ylabel("Cycles until 80% capacity"); axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Battery life by condition (bar = median of 3 cells; dot = one cell; hollow dot = never reached 80%, life is at least this)")
    fig.tight_layout(); fig.savefig(FIGURES / "life_cap_vs_no_cap.png", dpi=150); plt.close(fig)

    # Main effects
    fig, axes = plt.subplots(1, 3, figsize=(9, 3), sharey=True)
    names = {"rate": ("Charge rate", lambda v: {1: "1/3C", 3: "1C", 5: "5/3C"}[v]),
             "cap": ("Charge limit", lambda v: f"{v}%"), "temp": ("Temperature", lambda v: f"{v}°C")}
    for ax, f in zip(axes, ("rate", "cap", "temp")):
        e = effects[effects.factor == f]
        ax.plot(range(len(e)), e.median_life, "-o", color="#333")
        ax.set_xticks(range(len(e)), [names[f][1](v) for v in e.level]); ax.set_title(names[f][0])
    axes[0].set_ylabel("Median cycles until 80%")
    fig.suptitle("Main effects: median battery life of all cells at each level")
    fig.tight_layout(); fig.savefig(FIGURES / "main_effects.png", dpi=150); plt.close(fig)

    # Yearly battery cost at 25 C, 1 cycle/day
    c1 = cost[cost.usage_per_day == 1.0]
    fig, ax = plt.subplots(figsize=(6, 3.2))
    for k, r in enumerate((1, 3, 5)):
        for c, dx in ((100, -.18), (90, .18)):
            v = c1[(c1.rate == r) & (c1.cap == c)].cost_per_year.iloc[0]
            ax.bar(k + dx, v, width=.34, color=col[c], label=CAP_LABEL[c] if k == 0 else None)
            ax.text(k + dx, v, f"${v:.0f}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks([0, 1, 2], ["1/3C (slow)", "1C (medium)", "5/3C (fast)"])
    ax.set_ylabel("Battery wear cost per year (USD)"); ax.legend(frameon=False)
    ax.set_title(f"25°C, one full charge per day, ${PRICE_USD:.0f} replacement")
    fig.tight_layout(); fig.savefig(FIGURES / "cost_per_year_25C.png", dpi=150); plt.close(fig)

    # Fishbone (cause-and-effect) diagram for the Analyze phase
    fig, ax = plt.subplots(figsize=(10, 4.2)); ax.axis("off")
    ax.annotate("", xy=(8.6, 2), xytext=(0.3, 2), arrowprops=dict(arrowstyle="-|>", lw=2))
    ax.text(8.7, 2, "Battery loses\ncapacity early", va="center", fontsize=10, weight="bold")
    bones = [("Charging", ["Charge rate (tested)", "Charge limit 90/100% (tested)"], 1.5, 1),
             ("Environment", ["Temperature 0-40°C (tested)", "Shared temperature bath"], 4.5, 1),
             ("Use pattern", ["Discharge rate (fixed 1C)", "Depth of each cycle"], 7.0, 1),
             ("Cell", ["Cell-to-cell variation", "Cell chemistry NMC/SiO"], 1.5, -1),
             ("Measurement", ["Capacity check every few weeks", "Equipment errors stop tests"], 4.5, -1),
             ("Time", ["Calendar aging between cycles", "Test length limits"], 7.0, -1)]
    for name, causes, x, side in bones:
        ax.plot([x - 1, x], [2 + side * 1.6, 2], color="k", lw=1.2)
        ax.text(x - 1, 2 + side * 1.75, name, ha="center", va="center", weight="bold")
        for n, cause in enumerate(causes):
            h = 1.15 - .5 * n                      # height above/below the spine
            bone_x = x - h / 1.6                   # where the bone is at that height
            ax.plot([bone_x, bone_x + .25], [2 + side * h] * 2, color="k", lw=.8)
            ax.text(bone_x + .3, 2 + side * h, cause, va="center", fontsize=8)
    ax.set_xlim(0, 10); ax.set_ylim(0, 4)
    fig.tight_layout(); fig.savefig(FIGURES / "fishbone.png", dpi=150); plt.close(fig)


# ---------------------------------------------------------------- 4. run
def main():
    verify_download()
    study, checks, used = prepare()
    lives = cell_lives(study, used)
    summary = condition_summary(lives)
    compare = cap_comparison(summary)
    # Same comparison with 70% as the end-of-life point (robustness check only).
    compare70 = cap_comparison(condition_summary(cell_lives(study, used, CHECK_THRESHOLD)))
    compare = compare.merge(compare70[["temp", "rate", "times_longer", "life_90_at_least", "life_100_at_least", "clear", "confirmed", "undecided"]]
                            .rename(columns=lambda c: c if c in ("temp", "rate") else c + "_70"), on=["temp", "rate"])
    effects = main_effects(lives)
    cost = costs(summary)

    TABLES.mkdir(parents=True, exist_ok=True)
    used.to_csv(TABLES / "capacity_checkups.csv", index=False)
    checks[checks.dropped != ""].to_csv(TABLES / "dropped_checkups.csv", index=False)
    lives.to_csv(TABLES / "cell_life.csv", index=False)
    summary.to_csv(TABLES / "condition_life.csv", index=False)
    compare.to_csv(TABLES / "cap_vs_no_cap.csv", index=False)
    effects.to_csv(TABLES / "main_effects.csv", index=False)
    cost.to_csv(TABLES / "cost_per_year.csv", index=False)
    figures(used, lives, summary, effects, cost)

    facts = dict(
        cells=len(study), conditions=int(summary.shape[0]), checkups_used=len(used),
        checkups_dropped_cold=int((checks.dropped == "check-up not at room temperature").sum()),
        checkups_dropped_final=int((checks.dropped == "final check-up after temperature-control failure").sum()),
        cells_reached_80=int(lives.reached_80.sum()), cells_not_reached_80=int((~lives.reached_80).sum()),
        cells_stopped_by_error=int(lives.stopped_by_error.sum()),
        cap_longer_pairs=int(compare.confirmed.sum()), cap_undecided_pairs=int(compare.undecided.sum()),
        cap_shorter_pairs=int((compare.times_longer < 1).sum()), pairs=len(compare),
        cap_clear_pairs=int(compare.clear.sum()),
        cap_times_longer_median=float(compare.times_longer.median()),
        check70_cap_longer_pairs=int(compare.confirmed_70.sum()), check70_cap_undecided_pairs=int(compare.undecided_70.sum()),
        check70_cap_shorter_pairs=int((compare.times_longer_70 < 1).sum()),
        check70_cap_clear_pairs=int(compare.clear_70.sum()),
        check70_cap_times_longer_median=float(compare.times_longer_70.median()),
        check70_cells_reached=int(cell_lives(study, used, CHECK_THRESHOLD).reached_80.sum()),
        initial_capacity_median_Ah=float(used.groupby("cell").capacity_Ah.first().median()),
        price_usd=PRICE_USD, usage_per_day=USAGE_PER_DAY)
    (OUT / "results.json").write_text(json.dumps(facts, indent=2) + "\n")
    print(json.dumps(facts, indent=2))
    print(compare.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
