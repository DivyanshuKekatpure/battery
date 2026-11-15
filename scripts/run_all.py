"""Run the whole project: analysis, reports, then tests. Usage: .venv/bin/python -m scripts.run_all"""
import os
import sys
import unittest

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
from scripts import analysis

analysis.main()
from scripts import reports  # imported after analysis so it reads fresh tables
reports.main()

result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover("tests", top_level_dir="."))
sys.exit(0 if result.wasSuccessful() else 1)
