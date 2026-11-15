"""Run the whole project: analysis, then reports. Usage: .venv/bin/python -m scripts.run_all"""
import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
from scripts import analysis

analysis.main()
from scripts import reports  # imported after analysis so it reads fresh tables
reports.main()
