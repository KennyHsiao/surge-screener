#!/usr/bin/env python3
"""Self-contained tests for surge event taxonomy.

Run:  .venv/bin/python scripts/test_surge_event_taxonomy.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_surge_taxonomy_separates_result_from_candidate_causes() -> None:
    from scripts import surge_event_taxonomy as tax

    row = tax.classify_surge_event({
        "ticker": "NVDA",
        "thresholds_hit": ["+30%/20d", "+40%/40d"],
        "magnitude_pct": 47.0,
        "sessions_to_peak": 31,
        "gap_pct": 0.04,
        "volume_ratio_20d": 2.4,
        "rs_vs_spy_20d": 0.18,
        "sector_rs_20d": 0.11,
        "earnings_within_5d": False,
        "news_catalyst": None,
    })

    assert row["result_family"] == "multi_threshold_surge"
    assert row["price_structure"] == "trend_continuation"
    assert row["candidate_causes"] == [
        "technical_volume_expansion",
        "relative_strength_leadership",
        "sector_support",
    ]
    assert row["cause_certainty"] == "candidate_only"


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {test.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {test.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
