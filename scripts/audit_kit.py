"""Audit KIT v2 results in data2/ with Python standard library only.

Reads ZIP members in place; validates supplied BagIt MD5 checksums and extracts
standardized check-up discharge capacities, without changing existing analyses.
Run: python3 scripts/audit_kit.py
"""

import csv
import hashlib
import io
import math
import re
import statistics
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BAG = ROOT / "data2"
DATA = BAG / "data" / "dataset"
OUT = ROOT / "outputs" / "kit_audit"
CELL = re.compile(r"_P(\d{3})_(\d)_S(\d{2})_C(\d{2})\.csv$")


def write_csv(name, rows):
    with (OUT / name).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def records(z, filename):
    with z.open(filename) as f:
        yield from csv.DictReader(io.TextIOWrapper(f), delimiter=";")


def number(row, key):
    return float(row[key])


def close(row, key, value):
    return math.isclose(number(row, key), value, abs_tol=1e-5)


def bracket(points, threshold):
    for i, p in enumerate(points):
        if p["capacity_Ah"] <= threshold:
            return (points[max(0, i - 1)]["total_EFC"], p["total_EFC"])
    return "", ""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    checksums = []
    for manifest in ("tagmanifest-md5.txt", "manifest-md5.txt"):
        for line in (BAG / manifest).read_text().splitlines():
            expected, relative = line.split(maxsplit=1)
            path = BAG / relative
            digest = hashlib.md5()
            with path.open("rb") as f:
                for block in iter(lambda: f.read(1024 * 1024), b""):
                    digest.update(block)
            checksums.append(dict(file=relative, expected_md5=expected,
                                  actual_md5=digest.hexdigest(), matches=digest.hexdigest() == expected))
    write_csv("checksums.csv", checksums)
    if not all(r["matches"] for r in checksums):
        raise ValueError("Download checksum mismatch; inspect checksums.csv")

    configs = {}
    with zipfile.ZipFile(DATA / "cfg.zip") as z:
        for fn in z.namelist():
            m = CELL.search(fn)
            if not m or int(m[1]) == 0:
                continue  # S20 side-experiment channels are not additional cells.
            p, replicate, slave, channel = map(int, m.groups())
            cfg = next(records(z, fn))
            assert int(cfg["parameter_id"]) == p and int(cfg["parameter_nr"]) == replicate
            configs[(p, replicate)] = dict(
                cell=f"P{p:03}_{replicate}", parameter_id=p, replicate=replicate,
                slave=slave, channel=channel,
                aging_type={1: "calendar", 2: "cyclic", 3: "profile"}[int(cfg["age_type"])],
                temperature_degC=number(cfg, "age_temp"),
                charge_rate_C=number(cfg, "I_chg_max_cyc_A") / 3,
                discharge_rate_C=abs(number(cfg, "I_dischg_max_cyc_A")) / 3,
                lower_voltage_V=number(cfg, "V_min_cyc_V"),
                upper_voltage_V=number(cfg, "V_max_cyc_V"),
            )
    assert len(configs) == 228
    assert Counter(c["parameter_id"] for c in configs.values()) == Counter({p: 3 for p in range(1, 77)})
    inventory = []
    for archive in sorted(DATA.glob("*.zip")):
        with zipfile.ZipFile(archive) as z:
            files = [f for f in z.infolist() if not f.is_dir()]
            ids = [tuple(map(int, m.groups()[:2])) for f in files
                   if (m := CELL.search(f.filename)) and int(m[1]) != 0]
            assert set(ids) == set(configs) and len(ids) == len(configs), archive.name
            inventory.append(dict(archive=archive.name, files=len(files), main_cells=len(ids),
                                  uncompressed_bytes=sum(f.file_size for f in files)))
    write_csv("archive_inventory.csv", inventory)
    write_csv("cell_conditions.csv", list(configs.values()))

    capacities, summaries = [], []
    with zipfile.ZipFile(DATA / "cell_eocv2.zip") as z:
        for fn in z.namelist():
            m = CELL.search(fn)
            if not m or int(m[1]) == 0:
                continue
            key = tuple(map(int, m.groups()[:2]))
            cfg, points, total_rows = configs[key], [], 0
            last_timestamp = float("-inf")
            for r in records(z, fn):
                total_rows += 1
                timestamp = number(r, "timestamp_s")
                if timestamp < last_timestamp:
                    raise ValueError(f"Unordered end-of-run timestamps: {fn}")
                last_timestamp = timestamp
                # Full reference discharge at room temperature, not cycling estimates
                # or preparatory discharges. Definitions from Data Structure v05.3.
                if not (close(r, "cyc_condition", 2) and close(r, "cyc_charged", 0)
                        and close(r, "v_min_target_V", 2.5) and close(r, "v_max_target_V", 4.2)
                        and close(r, "i_dischg_min_A", -1) and close(r, "i_dischg_cutoff_A", -0.15)):
                    continue
                capacity = abs(number(r, "delta_q_dischg_Ah"))
                if not math.isfinite(capacity) or capacity <= 0:
                    raise ValueError(f"Invalid reference capacity: {fn}")
                point = dict(cell=cfg["cell"], parameter_id=cfg["parameter_id"],
                             source_file=fn, source_row=total_rows+1,
                             timestamp_s=timestamp, checkup_counter=int(float(r["num_cycles_checkup"])),
                             capacity_Ah=capacity,
                             total_EFC=(number(r, "total_q_chg_sum_Ah") + number(r, "total_q_dischg_sum_Ah")) / 6,
                             operating_EFC=(number(r, "total_q_chg_cyc_OT_Ah") + number(r, "total_q_dischg_cyc_OT_Ah")) / 6,
                             discharge_end_temperature_degC=number(r, "t_end_degC"))
                points.append(point)
            if not points:
                raise ValueError(f"No standardized reference capacities: {fn}")
            initial = points[0]["capacity_Ah"]
            for p in points:
                p["retention_initial"] = p["capacity_Ah"] / initial
                p["retention_rated"] = p["capacity_Ah"] / 3
                # Audit screen, not an automatic exclusion or claimed tolerance.
                p["temperature_review_outside_20_30_degC"] = not (
                    20 <= p["discharge_end_temperature_degC"] <= 30)
            capacities.extend(points)
            lo, hi = bracket(points, 0.8 * initial)
            nominal_lo, nominal_hi = bracket(points, 2.4)
            summaries.append(dict(**cfg, eoc_rows=total_rows, capacity_measurements=len(points),
                                  first_timestamp_s=points[0]["timestamp_s"],
                                  last_capacity_timestamp_s=points[-1]["timestamp_s"],
                                  initial_capacity_Ah=initial, final_capacity_Ah=points[-1]["capacity_Ah"],
                                  final_retention_initial=points[-1]["retention_initial"],
                                  final_total_EFC=points[-1]["total_EFC"],
                                  last_logged_total_EFC=(number(r, "total_q_chg_sum_Ah") + number(r, "total_q_dischg_sum_Ah"))/6,
                                  last_logged_timestamp_s=last_timestamp,
                                  first_80pct_initial_lower_EFC=lo, first_80pct_initial_upper_EFC=hi,
                                  first_80pct_rated_lower_EFC=nominal_lo, first_80pct_rated_upper_EFC=nominal_hi))
    write_csv("capacity_checkups.csv", capacities)
    write_csv("capacity_inventory.csv", summaries)

    groups = defaultdict(list)
    for r in summaries:
        groups[r["parameter_id"]].append(r)
    pairs = []
    for p, members in sorted(groups.items()):
        a = members[0]
        if a["aging_type"] != "cyclic" or a["upper_voltage_V"] >= 4.19:
            continue
        matches = [q for q, ms in groups.items() if ms[0]["aging_type"] == "cyclic"
                   and ms[0]["upper_voltage_V"] == 4.2
                   and all(ms[0][k] == a[k] for k in
                           ("temperature_degC", "charge_rate_C", "discharge_rate_C", "lower_voltage_V"))]
        assert len(matches) == 1, (p, matches)
        q = matches[0]
        b = groups[q]
        pairs.append(dict(temperature_degC=a["temperature_degC"], charge_rate_C=a["charge_rate_C"],
                          discharge_rate_C=a["discharge_rate_C"], lower_voltage_V=a["lower_voltage_V"],
                          cap90_parameter=p, cap100_parameter=q, cells_per_arm=len(members),
                          cap90_upper_voltage_V=a["upper_voltage_V"], cap100_upper_voltage_V=4.2,
                          cap90_observed_80pct_initial=sum(r["first_80pct_initial_upper_EFC"] != "" for r in members),
                          cap100_observed_80pct_initial=sum(r["first_80pct_initial_upper_EFC"] != "" for r in b)))
    assert len(pairs) == 16
    write_csv("matched_cap_comparisons.csv", pairs)
    print(f"Checksums: {len(checksums)}/{len(checksums)} matched. Main cells: {len(configs)}.")
    print(f"Capacity check-ups extracted: {len(capacities)}. Matched cap comparisons: {len(pairs)}.")
    for typ in ("cyclic", "calendar", "profile"):
        rs = [r for r in summaries if r["aging_type"] == typ]
        print(typ, len(rs), 'cells;', sum(r['first_80pct_initial_upper_EFC'] != '' for r in rs), 'observed 80% initial crossings')
    print('25 C comparisons:', [r for r in pairs if r['temperature_degC'] == 25])
    print('Initial capacity median:', statistics.median(r['initial_capacity_Ah'] for r in summaries))


if __name__ == "__main__":
    main()
