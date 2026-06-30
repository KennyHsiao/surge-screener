#!/usr/bin/env python3
"""Focused tests for risk_guard technical artifact fields.

Run:  .venv/bin/python scripts/test_risk_guard_technical.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import risk_guard as rg  # noqa: E402


def test_technical_summary_keeps_chandelier_inputs():
    technical = {
        "price": 125.0,
        "ma20": 120.0,
        "ma50": 110.0,
        "ma200": 95.0,
        "vwap": 122.0,
        "atr14": 4.0,
        "rsi14": 62.0,
        "price_above_vwap": True,
        "resistance_20d": 130.0,
        "support_20d": 100.0,
        "highest_high_22d": 132.0,
        "lowest_low_22d": 98.0,
        "ignored": "not persisted",
    }

    summary = rg._technical_summary(technical)

    assert summary["highest_high_22d"] == 132.0, summary
    assert summary["lowest_low_22d"] == 98.0, summary
    assert summary["support_20d"] == 100.0, summary
    assert "ignored" not in summary


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS {test.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {test.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {test.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
