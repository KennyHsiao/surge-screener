#!/usr/bin/env python3
"""Offline regression for the C-1b dataset-mismatch guard (adversarial review).

Pins that retro_report._universe_mismatch is FAIL-CLOSED: it blocks on any universe
asymmetry, including the case the original guard let slip — a lift missing coverage.universe
paired with a real dataset's events.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import retro_report as rr

mm = rr._universe_mismatch


def test_matched_passes():
    assert mm({"coverage": {"universe": "sp1500"}}, {"universe": "sp1500"}) is None
    assert mm({"coverage": {"universe": "sp500_pit"}}, {"universe": "sp500_pit"}) is None
    assert mm({"universe": "sp1500"}, {"universe": "sp1500"}) is None  # top-level fallback


def test_value_mismatch_blocks():
    assert mm({"coverage": {"universe": "sp1500"}}, {"universe": "sp500_pit"}) == ("sp1500", "sp500_pit")


def test_asymmetric_missing_blocks():
    """The original-guard escape: lift has NO universe, events does -> must block, not pass."""
    assert mm({"coverage": {}}, {"universe": "sp500_pit"}) == (None, "sp500_pit")
    assert mm({}, {"universe": "sp500_pit"}) == (None, "sp500_pit")
    # reverse asymmetry blocks too
    assert mm({"coverage": {"universe": "sp500_pit"}}, {}) == ("sp500_pit", None)


def test_both_absent_passes_leniently():
    assert mm({"coverage": {}}, {}) is None     # legacy↔legacy, nothing to contradict


if __name__ == "__main__":
    for _n, _f in sorted(globals().items()):
        if _n.startswith("test_") and callable(_f):
            _f()
            print(f"  ok {_n}")
    print("all retro_report guard tests passed")
