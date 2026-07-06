"""
Diagnostic script — prints the raw net_score and per-signal detail for
each test case, so you can see exactly what the signals detected
before the band/label logic is applied on top of it.

Run with:
    python3 diagnose.py
"""

from pipeline import run_pipeline
from test_pipeline import TEST_CASES

for name, text in TEST_CASES.items():
    r = run_pipeline(text, domain="general")
    word_count = len(text.split())
    print(f"{name}: words={word_count}, net_score={r.net_score}, "
          f"band={r.confidence_band.value}, label={r.label!r}, ")
    for s in r.signals:
        print(f"    {s.name}: {s.direction.value} ({s.weight.name}) — {s.detail}")
    print()