"""Write both course reports (Markdown + Word) from the analysis tables.

Every number in the text is read from outputs/tables or outputs/results.json,
so the reports always match the data. Run after scripts.analysis:
    .venv/bin/python -m scripts.reports
"""
import json
import re
from pathlib import Path

import pandas as pd
from docx import Document
from docx.shared import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
T = OUT / "tables"
REPORTS = OUT / "reports"
RATE = {1: "1/3C", 3: "1C", 5: "5/3C"}

f = json.loads((OUT / "results.json").read_text())
life = pd.read_csv(T / "condition_life.csv")
comp = pd.read_csv(T / "cap_vs_no_cap.csv")
eff = pd.read_csv(T / "main_effects.csv")
cost = pd.read_csv(T / "cost_per_year.csv")
cells = pd.read_csv(T / "cell_life.csv")


def n(x):
    return f"{x:,.0f}"


def life_txt(row, cap):
    v = row[f"life_{cap}"]
    return ("≥" if row[f"life_{cap}_at_least"] else "") + n(v)


def money(x):
    return f"${x:,.0f}"


def L(temp, rate, cap):
    r = life[(life.temp == temp) & (life.rate == rate) & (life.cap == cap)].iloc[0]
    return ("at least " if r.at_least else "") + n(r.median_life)


def E(factor, level):
    return n(eff[(eff.factor == factor) & (eff.level == level)].median_life.iloc[0])


def C(u, rate, cap, col="cost_per_year"):
    return cost[(cost.usage_per_day == u) & (cost.rate == rate) & (cost.cap == cap)][col].iloc[0]


c25 = comp[comp.temp == 25].set_index("rate")
fast_err = cells[(cells.temp == 25) & (cells.rate == 5) & (cells.cap == 100)]

REF_DATA = ("Luh, M., & Blank, T. (2024). Comprehensive battery aging dataset: capacity and impedance fade "
            "measurements of a lithium-ion NMC/C-SiO cell. Scientific Data, 11, 1004. "
            "https://doi.org/10.1038/s41597-024-03831-x. Version 2 result data: https://doi.org/10.35097/1969 (CC BY 4.0).")
REF_PRICE = ("Burkhardt, M. (2024, September 15). iPhone 16 Pro battery replacements will cost even more than last year. "
             "9to5Mac. https://9to5mac.com/2024/09/15/iphone-16-pro-battery-replacement/")

# ------------------------------------------------------------------ Preliminary report
measures = f"""Our outcome is **battery life**: the number of equivalent full cycles until a cell first measures below 80% of its starting capacity. One equivalent full cycle means 3 Ah charged and 3 Ah discharged, the cell's nominal capacity. Capacity comes from KIT's standard check-up, a full slow discharge done every few weeks at room temperature. Because checks are periodic, each cell's life is taken as the midpoint between the last check above 80% and the first check below it. Cells still above 80% when testing ended get an "at least" value. We compare three charge rates (1/3C, 1C, 5/3C), two charge limits (4.09 V, about 90% full, versus 4.2 V, 100%) and four temperatures (0, 10, 25 and 40°C)."""

assumptions = f"""We assume the 80% threshold is a fair definition of a worn-out battery; it is an industry convention, not a value from the data. We drop {f['checkups_dropped_cold']} check-ups measured outside room temperature and the {f['checkups_dropped_final']} measurements from the final check-up, which KIT ran after its temperature control failed. Missing measurements are left missing. We treat the three cells in each condition as fair repeats, although they shared one temperature bath. {f['cells_stopped_by_error']} of {f['cells']} cells stopped early because of an equipment error code; we keep their measurements up to that point. The test cells are 3 Ah cylindrical cells, so applying results to phones is an assumption."""

model = f"""We follow the Six Sigma DMAIC steps. **Define:** batteries lose capacity too fast; the quality characteristic is cycles until 80% capacity. **Measure:** we read every capacity check-up for the {f['cells']} KIT cells in a full 3 × 2 × 4 factorial design, three cells per condition, with discharge fixed at 1C. **Analyze:** we plot capacity fade, find each cell's life, take the median of the three cells in each condition, and compare 90% versus 100% at matching rate and temperature. A main-effects chart shows each factor's overall influence, and a fishbone diagram lists other possible causes. **Improve:** we test whether a 90% cap and slower charging extend life. **Control:** we suggest a default charging policy to hold the gain. We use no fitted statistical model; every result is a direct measurement or simple arithmetic on measurements."""

rows = [[f"{t}°C", RATE[r], life_txt(row, 100), life_txt(row, 90), f"{row.times_longer:.1f}×"]
        for (t, r), row in comp.set_index(["temp", "rate"]).iterrows()]

results = f"""We used {f['checkups_used']} check-ups from {f['cells']} cells; {f['cells_reached_80']} cells fell below 80% during testing and {f['cells_not_reached_80']} did not.

**Capping at 90% extended life in all {f['pairs']} rate–temperature pairs** (Table 1, Figure 2). In {f['cap_clear_pairs']} pairs every capped cell outlasted every uncapped cell. The typical gain was {f['cap_times_longer_median']:.1f}× more cycles. At 25°C, capping raised median life from {L(25,1,100)} to {L(25,1,90)} cycles at 1/3C, {L(25,3,100)} to {L(25,3,90)} at 1C, and {L(25,5,100)} to {L(25,5,90)} at 5/3C (Figure 1).

**Why the cap helps.** Holding a cell near 4.2 V, completely full, stresses the electrodes and speeds up side reactions that consume lithium. Stopping at 4.09 V avoids the most stressful part of every cycle. Figure 1 also shows a "knee": capacity first fades slowly, then drops quickly. Capped cells reach that knee much later.

**Faster charging shortened life.** Across all cells, median life was {E('rate',1)} cycles at 1/3C, {E('rate',3)} at 1C and {E('rate',5)} at 5/3C (Figure 3).

**Temperature mattered most.** Median life was {E('temp',0)} cycles at 0°C, {E('temp',10)} at 10°C, {E('temp',25)} at 25°C and {E('temp',40)} at 40°C. Cold plus fast charging was worst: uncapped 5/3C cells at 0°C failed or stopped within {n(life[(life.temp==0)&(life.rate==5)&(life.cap==100)].highest.iloc[0])} cycles. Heat had mixed effects: at 1/3C, uncapped life fell from {L(25,1,100)} cycles at 25°C to {L(40,1,100)} at 40°C, but at 5/3C it rose from {L(25,5,100)} to {L(40,5,100)}. Warmth speeds slow chemical aging, but it also helps lithium enter the electrode quickly; in the cold, fast charging plates metallic lithium on the electrode instead, which destroys capacity.

**Data quality.** {f['cells_stopped_by_error']} cells stopped on error codes, marked × in the figures. The uncapped 5/3C cells at 25°C were all among them: two crossed 80% at their last check, and one stopped at {n(fast_err.life_cycles.max())} cycles without crossing. Their median is therefore uncertain, while the capped advantage there is still large. The three capped 1/3C cells at 25°C never reached 80%, so their life is a lower bound."""

prelim = [("Measures", measures, []), ("Assumptions", assumptions, []), ("Model / approach", model, []),
          ("Results", results,
           [("table", "Table 1. Median cycles until 80% capacity (3 cells each); ≥ means at least.",
             ["Temp", "Charge rate", "100% (no cap)", "90% cap", "Cap gain"], rows),
            ("figure", "Figure 1. Measured capacity at 25°C. × marks a test stopped by an equipment error.", "fade_25C.png"),
            ("figure", "Figure 2. Cycles until 80% capacity, cap versus no cap, for every condition.", "life_cap_vs_no_cap.png"),
            ("figure", "Figure 3. Main effects: median life of all cells at each factor level.", "main_effects.png")])]

# ------------------------------------------------------------------ Financial report
usage = f["usage_per_day"]
fin_rows = [[RATE[r], money(C(1.0, r, 100)), money(C(1.0, r, 90)), money(C(1.0, r, 90, 'saving_per_year_vs_no_cap'))] for r in (1, 3, 5)]
lo, hi = C(min(usage), 5, 90, 'saving_per_year_vs_no_cap'), C(max(usage), 5, 90, 'saving_per_year_vs_no_cap')

financial = f"""We estimate what battery wear costs a phone owner each year, and how much a 90% charge cap saves. The battery lives come from the KIT measurements at 25°C (Table 1 of our methods report). Only one input comes from outside the data: a ${f['price_usd']:.0f} battery replacement fee (Burkhardt, 2024).

The calculation is simple arithmetic. Yearly wear cost = replacement price × cycles used per year ÷ cycles the battery lasts. A battery that lasts 1,000 cycles, used once a day, is used up at 365/1,000 of a battery per year, which costs about $36 a year. We do not know how many full cycles a typical owner uses, so we show 0.5, 1 and 1.5 cycles per day as scenarios rather than claiming one value. The formula is proportional, so a higher replacement fee, such as a Pro model's, raises every cost and saving by the same percentage.

At one full charge a day, capping saves the most for fast chargers: wear cost falls from {money(C(1.0,5,100))} to {money(C(1.0,5,90))} a year, a saving of {money(C(1.0,5,90,'saving_per_year_vs_no_cap'))} (Table 2, Figure 1). Across our usage scenarios, that saving ranges from {money(lo)} to {money(hi)} a year. For 1C charging, the saving is {money(C(1.0,3,90,'saving_per_year_vs_no_cap'))} a year; for slow 1/3C charging it is at least {money(C(1.0,1,90,'saving_per_year_vs_no_cap'))}, since capped slow-charged cells never wore out during testing. The cap costs nothing to implement as a software setting. Its trade-off is about 10% less charge available each day.

These numbers have limits. They count cycling wear only; real batteries also age with time, so very long lives (over about five years) overstate the benefit. The fast-charging baseline rests on three cells that stopped on equipment errors. And the KIT cells are cylindrical 3 Ah cells, not phone batteries. We therefore recommend offering a 90% charge cap as a default for users who fast-charge, and confirming the savings on real phone batteries before promising a dollar figure."""

fin = [("Financial Impacts", financial,
        [("table", f"Table 2. Yearly battery wear cost at 25°C, one full cycle per day, ${f['price_usd']:.0f} replacement.",
          ["Charge rate", "100% (no cap)", "90% cap", "Saving per year"], fin_rows),
         ("figure", "Figure 1. Yearly battery wear cost at 25°C, one full cycle per day.", "cost_per_year_25C.png")])]


# ------------------------------------------------------------------ writers
def words(text):
    return len(re.findall(r"[A-Za-z0-9$%°×≥./–-]+", re.sub(r"\*\*", "", text)))


def section_words(body, extras):
    total = words(body)
    for kind, caption, *rest in extras:
        total += words(caption)
        if kind == "table":
            total += sum(words(c) for c in rest[0]) + sum(words(str(c)) for row in rest[1] for c in row)
    return total


def write_md(name, title, sections, refs):
    lines = [f"# {title}", ""]
    for head, body, extras in sections:
        lines += [f"## {head}", "", body, ""]
        for kind, caption, *rest in extras:
            if kind == "table":
                header, rows_ = rest
                lines += [caption, "", "| " + " | ".join(header) + " |", "|" + " --- |" * len(header)]
                lines += ["| " + " | ".join(map(str, r)) + " |" for r in rows_] + [""]
            else:
                lines += [f"![{caption}](../figures/{rest[0]})", ""]
    lines += ["## References", ""] + [r + "\n" for r in refs]
    (REPORTS / f"{name}.md").write_text("\n".join(lines))


def add_rich(paragraph, text):
    for i, part in enumerate(text.split("**")):
        run = paragraph.add_run(part)
        run.bold = i % 2 == 1


def write_docx(name, title, sections, refs):
    d = Document()
    d.styles["Normal"].font.name = "Calibri"; d.styles["Normal"].font.size = Pt(11)
    d.add_heading(title, 0)
    for head, body, extras in sections:
        d.add_heading(head, 1)
        for para in body.split("\n\n"):
            add_rich(d.add_paragraph(), para)
        for kind, caption, *rest in extras:
            if kind == "table":
                header, rows_ = rest
                d.add_paragraph(caption).runs[0].italic = True
                t = d.add_table(rows=1, cols=len(header)); t.style = "Light Grid Accent 1"
                for c, h in zip(t.rows[0].cells, header): c.text = h
                for r in rows_:
                    for c, v in zip(t.add_row().cells, r): c.text = str(v)
            else:
                d.add_picture(str(OUT / "figures" / rest[0]), width=Inches(6.3))
                d.add_paragraph(caption).runs[0].italic = True
    d.add_heading("References", 1)
    for r in refs:
        d.add_paragraph(r)
    d.save(REPORTS / f"{name}.docx")


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, title, sections, refs in [
            ("Preliminary_Methods_and_Results", "Preliminary Methods and Results", prelim, [REF_DATA]),
            ("Financial_Impacts", "Capping Fast Charging: Financial Impacts", fin, [REF_DATA, REF_PRICE])]:
        write_md(name, title, sections, refs)
        write_docx(name, title, sections, refs)
        for head, body, extras in sections:
            counts[head] = {"prose": words(body), "with_tables_and_captions": section_words(body, extras)}
    # Word limits from the assignment: Results 300-600, Financial Impacts 300-500 (prose minimum 300).
    assert 300 <= counts["Results"]["prose"] and counts["Results"]["with_tables_and_captions"] <= 600, counts["Results"]
    assert 300 <= counts["Financial Impacts"]["prose"] and counts["Financial Impacts"]["with_tables_and_captions"] <= 500, counts["Financial Impacts"]
    (OUT / "report_word_counts.json").write_text(json.dumps(counts, indent=2) + "\n")
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
