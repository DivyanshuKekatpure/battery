"""Tests for scripts/analysis.py.  Run: .venv/bin/python -m unittest discover -s tests -v

The first group uses tiny made-up cells where the right answer is known by hand.
The second group checks the real KIT data and is skipped if data2/ is missing.
"""
import os
import unittest

import pandas as pd

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
from scripts import analysis as a


def fake_cell(cell, cycles, retention, temp=25, rate=3, cap=100, stop="EOL_cap"):
    used = pd.DataFrame({"cell": cell, "cycles": cycles, "retention": retention})
    study = pd.DataFrame([{"cell": cell, "temp": temp, "rate": rate, "cap": cap, "stop_reason": stop}])
    return study, used


class CellLife(unittest.TestCase):
    def test_life_is_straight_line_crossing(self):
        study, used = fake_cell("A", [0, 100, 200, 300], [1.0, 0.9, 0.82, 0.78])
        row = a.cell_lives(study, used).iloc[0]
        self.assertTrue(row.reached_80)
        self.assertEqual((row.last_check_before, row.first_check_below), (200, 300))
        self.assertAlmostEqual(row.life_cycles, 250)
        # Uneven drop: 0.81 -> 0.71 over 100 cycles crosses 80% one tenth of the way in.
        study, used = fake_cell("A2", [0, 100, 200], [1.0, 0.81, 0.71])
        self.assertAlmostEqual(a.cell_lives(study, used).life_cycles.iloc[0], 110)

    def test_cell_that_never_crosses_is_a_lower_bound(self):
        study, used = fake_cell("B", [0, 100, 200], [1.0, 0.95, 0.9])
        row = a.cell_lives(study, used).iloc[0]
        self.assertFalse(row.reached_80)
        self.assertEqual(row.life_cycles, 200)          # "at least 200"

    def test_threshold_parameter(self):
        study, used = fake_cell("C", [0, 100, 200, 300], [1.0, 0.85, 0.75, 0.65])
        self.assertAlmostEqual(a.cell_lives(study, used, 0.8).life_cycles.iloc[0], 150)
        self.assertAlmostEqual(a.cell_lives(study, used, 0.7).life_cycles.iloc[0], 250)

    def test_error_stop_is_flagged(self):
        study, used = fake_cell("D", [0, 100], [1.0, 0.7], stop="dSoc+ err")
        self.assertTrue(a.cell_lives(study, used).stopped_by_error.iloc[0])


def fake_lives(cap, lives, reached):
    return pd.DataFrame({"cell": [f"{cap}_{i}" for i in range(3)], "temp": 25, "rate": 3, "cap": cap,
                         "life_cycles": lives, "reached_80": reached, "stopped_by_error": False})


class Summaries(unittest.TestCase):
    def test_median_is_lower_bound_only_if_middle_cell_never_crossed(self):
        s = a.condition_summary(fake_lives(100, [100, 200, 300], [True, True, False])).iloc[0]
        self.assertEqual(s.median_life, 200)
        self.assertFalse(s.at_least)                     # censored cell is the top one: median is exact
        s = a.condition_summary(fake_lives(100, [100, 200, 300], [True, False, False])).iloc[0]
        self.assertTrue(s.at_least)

    def test_cap_win_needs_measured_uncapped_life(self):
        exact = pd.concat([fake_lives(90, [400, 500, 600], [True] * 3), fake_lives(100, [100, 200, 300], [True] * 3)])
        row = a.cap_comparison(a.condition_summary(exact)).iloc[0]
        self.assertTrue(row.confirmed and row.clear and not row.undecided)
        self.assertEqual(row.times_longer, 2.5)
        bound = pd.concat([fake_lives(90, [400, 500, 600], [True] * 3), fake_lives(100, [100, 200, 300], [False] * 3)])
        row = a.cap_comparison(a.condition_summary(bound)).iloc[0]
        self.assertTrue(row.undecided and not row.confirmed)

    def test_cost_arithmetic(self):
        summary = pd.DataFrame({"temp": 25, "rate": [3, 3], "cap": [100, 90], "median_life": [1000.0, 2000.0], "at_least": False})
        c = a.costs(summary).query("usage_per_day == 1.0").set_index("cap")
        self.assertAlmostEqual(c.loc[100, "cost_per_year"], a.PRICE_USD * 365 / 1000)
        self.assertAlmostEqual(c.loc[90, "battery_years"], 2000 / 365)
        self.assertAlmostEqual(c.loc[90, "saving_per_year_vs_no_cap"], a.PRICE_USD * 365 / 2000)


@unittest.skipUnless((a.DATA / "cell_eocv2.zip").exists(), "KIT data not in data2/")
class RealData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.study, cls.checks, cls.used = a.prepare()
        cls.lives = a.cell_lives(cls.study, cls.used)

    def test_design_is_full_factorial(self):
        self.assertEqual(len(self.study), 72)
        self.assertTrue(self.study.groupby(["temp", "rate", "cap"]).size().eq(3).all())
        self.assertEqual(sorted(self.study.temp.unique()), [0, 10, 25, 40])

    def test_every_cell_starts_at_100_percent_and_has_data(self):
        first = self.used.sort_values("cycles").groupby("cell").first()
        self.assertTrue((first.retention == 1).all() and (first.cycles == 0).all())
        self.assertTrue((self.used.groupby("cell").size() >= 2).all())

    def test_capacities_are_physical(self):
        self.assertTrue(self.used.capacity_Ah.between(0.5, 3.3).all())
        self.assertTrue((self.used.sort_values(["cell", "time_s"]).groupby("cell").cycles.diff().dropna() >= 0).all())

    def test_dropped_checkups_have_reasons(self):
        dropped = self.checks[self.checks.dropped != ""]
        self.assertEqual(len(dropped), 14)
        self.assertEqual(len(self.used), 859)

    def test_storage_cells_and_no_extrapolation(self):
        checks, loss = a.storage_aging()
        self.assertEqual(checks.cell.nunique(), 48)
        last_day = checks.groupby("cell").days.max()
        self.assertTrue((loss.cells >= 1).all() and (loss.cells <= 3).all())
        self.assertLessEqual(loss.days.max(), last_day.max())
        # Every storage cell starts at 100% and only loses capacity overall.
        self.assertTrue((checks.groupby("cell").retention.last() < 1).all())

    def test_published_results_match_the_data(self):
        import json
        facts = json.loads((a.OUT / "results.json").read_text())
        self.assertEqual(facts["cells_reached_80"], int(self.lives.reached_80.sum()))
        self.assertEqual(facts["checkups_used"], len(self.used))


if __name__ == "__main__":
    unittest.main()
