"""Audit the downloaded ISU release without unpacking the large raw archives.

Uses only the standard library and pdftotext (to read the supplied conditions).
Outputs are separate from the existing LFP analysis. Run: python3 scripts/audit_isu.py
"""

import csv
import io
import re
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "outputs" / "isu_audit"


def write_csv(name, rows):
    with (OUT / name).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def crossing(points, threshold):
    """Bracket first observed crossing; do not interpolate or invent cycle counts."""
    for i, (week, capacity) in enumerate(points):
        if capacity <= threshold:
            return (points[i - 1][0] if i else week), week
    return "", ""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    readme = subprocess.check_output(
        ["pdftotext", "-layout", str(DATA / "README_V2.0.pdf"), "-"], text=True
    )
    conditions = {}
    for line in readme.splitlines():
        match = re.fullmatch(r"\s*(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)%\s*", line)
        if match:
            group, charge, discharge, dod = match.groups()
            conditions[int(group)] = dict(
                group=int(group), charge_rate_C=float(charge),
                discharge_rate_C=float(discharge), mean_DoD_percent=float(dod)
            )
    if len(conditions) != 63:
        raise ValueError(f"Expected 63 documented conditions, found {len(conditions)}")
    # This release contains literal escaped CRLF sequences rather than CSV newlines.
    valid_text = (DATA / "Valid_cells.csv").read_text().replace("\\r\\n", "\n")
    valid = set(valid_text.splitlines()[1:]) - {""}
    inventory = []
    for archive in sorted(DATA.glob("*.zip")):
        with zipfile.ZipFile(archive) as z:
            files = [f for f in z.infolist() if not f.is_dir()]
            cell_ids = [Path(f.filename).stem for f in files if re.fullmatch(r"G\d+C\d+", Path(f.filename).stem)]
            if set(cell_ids) != valid or len(cell_ids) != len(valid):
                raise ValueError(f"Cell inventory differs from valid list: {archive.name}")
            inventory.append(dict(archive=archive.name, cells=len(cell_ids),
                                  compressed_bytes=archive.stat().st_size,
                                  uncompressed_bytes=sum(f.file_size for f in files)))
    rows = []
    with zipfile.ZipFile(DATA / "capacity_fade.zip") as z:
        for filename in sorted(z.namelist()):
            cell = Path(filename).stem
            if cell not in valid:
                continue
            points = []
            for row in csv.DictReader(io.StringIO(z.read(filename).decode())):
                week, capacity = float(row["Time"]), float(row["Capacity"])
                if not (week >= 0 and capacity > 0):
                    raise ValueError(f"Invalid capacity point in {filename}")
                points.append((week, capacity))
            if not points or any(b[0] < a[0] for a, b in zip(points, points[1:])):
                raise ValueError(f"Missing or unordered trajectory: {filename}")
            group = int(re.match(r"G(\d+)C", cell)[1])
            lower, upper = crossing(points, 0.8 * points[0][1])
            nominal_lower, nominal_upper = crossing(points, 0.8 * 0.250)
            rows.append(dict(cell=cell, **conditions[group], release=Path(filename).parent.name,
                             measurements=len(points), initial_capacity_Ah=points[0][1],
                             last_week=points[-1][0], last_capacity_Ah=points[-1][1],
                             first_80pct_initial_crossing_lower_week=lower,
                             first_80pct_initial_crossing_upper_week=upper,
                             first_80pct_rated_crossing_lower_week=nominal_lower,
                             first_80pct_rated_crossing_upper_week=nominal_upper))
    write_csv("archive_inventory.csv", inventory)
    write_csv("conditions.csv", [dict(**conditions[g], cells=sum(r["group"] == g for r in rows))
                                 for g in sorted(conditions)])
    write_csv("capacity_inventory.csv", rows)
    print(f"Audited {len(rows)} cells, {len(conditions)} conditions, {len(inventory)} archives.")
    print(f"80% initial-capacity crossings observed: {sum(r['first_80pct_initial_crossing_upper_week'] != '' for r in rows)}")
    print(f"80% rated-capacity crossings observed: {sum(r['first_80pct_rated_crossing_upper_week'] != '' for r in rows)}")
    print(f"Outputs: {OUT}")


if __name__ == "__main__":
    main()
