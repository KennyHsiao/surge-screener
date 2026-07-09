#!/usr/bin/env python3
"""Self-contained tests for strong continuation outcome labels.

Run:  .venv/bin/python scripts/test_continuation_strength.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_strong_continuation_requires_return_and_controlled_drawdown() -> None:
    from scripts import continuation_strength as cont

    row = cont.classify_continuation({
        "ticker": "NVDA",
        "setup_date": "2026-01-02",
        "fwd_30d_return": 0.18,
        "fwd_30d_max_drawdown": -0.07,
        "resolved_30d": True,
        "fwd_60d_return": 0.34,
        "fwd_60d_max_drawdown": -0.13,
        "resolved_60d": True,
    })

    assert row["continuation_label"] == "strong_continuation"
    assert row["primary_horizon"] == "30d"
    assert row["trade_value"] == "high"


def test_continuation_unresolved_window_does_not_guess() -> None:
    from scripts import continuation_strength as cont

    row = cont.classify_continuation({
        "ticker": "AAA",
        "setup_date": "2026-01-02",
        "fwd_30d_return": None,
        "fwd_30d_max_drawdown": None,
        "resolved_30d": False,
    })

    assert row["continuation_label"] == "unresolved"
    assert row["trade_value"] == "unknown"


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
