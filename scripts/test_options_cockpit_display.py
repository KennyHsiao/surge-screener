#!/usr/bin/env python3
"""Self-contained display-state tests for Options Cockpit UI helpers.

Run:  .venv/bin/python scripts/test_options_cockpit_display.py
"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stderr
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

with redirect_stderr(io.StringIO()):
    from ui import options_cockpit as oc  # noqa: E402


def test_single_iv_snapshot_uses_marker_and_accumulating_copy() -> None:
    iv_history = pd.DataFrame({
        "date": pd.to_datetime(["2026-07-01"]),
        "iv": [0.498],
    })

    state = oc._iv_history_display_state(
        iv_history,
        atm_iv=None,
        iv_rank_source="realized_vol_proxy",
        iv_rank_n_days=1,
        iv_rank_accumulating=True,
        is_demo=False,
    )

    assert state["show_section"] is True, state
    assert state["trace_mode"] == "lines+markers", state
    assert state["current_iv_pct"] == 49.8, state
    assert "快照累積中" in state["caption"], state
    assert "n=1d" in state["caption"], state


def test_missing_iv_history_still_surfaces_current_atm_iv() -> None:
    state = oc._iv_history_display_state(
        pd.DataFrame(columns=["date", "iv"]),
        atm_iv=0.5123,
        iv_rank_source="realized_vol_proxy",
        iv_rank_n_days=0,
        iv_rank_accumulating=True,
        is_demo=False,
    )

    assert state["show_section"] is True, state
    assert state["trace_mode"] is None, state
    assert state["current_iv_pct"] == 51.23, state
    assert "尚無 iv_history 快照" in state["caption"], state


def main() -> None:
    tests = [
        test_single_iv_snapshot_uses_marker_and_accumulating_copy,
        test_missing_iv_history_still_surfaces_current_atm_iv,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"  PASS {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  FAIL {test.__name__}: {exc}")
    if failures:
        raise SystemExit(1)
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
