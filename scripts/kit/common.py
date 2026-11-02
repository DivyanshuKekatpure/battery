"""Shared paths and provenance helpers for the KIT pipeline."""
from pathlib import Path
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs' / 'kit'
SEED = 20261101

def save_json(name, data):
    (OUT / name).parent.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, allow_nan=False, default=lambda x: x.item() if isinstance(x, np.generic) else str(x))+'\n')

def decision(id_, text):
    p=ROOT/'docs'/'decision_log.md'
    if f'| {id_} |' not in p.read_text():
        with p.open('a') as f:f.write(f'| {id_} | 2026-11-01 | {text} |\n')
