#!/usr/bin/env python3
"""Offline regression tests for lossless forward-return ledger merges."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    spec = importlib.util.spec_from_file_location(
        "verify_returns_under_test", ROOT / "scripts" / "07_verify_returns.py",
    )
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load 07_verify_returns.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_merge_forward_updates_retains_concurrently_appended_row() -> None:
    mod = load_module()
    latest_rows = [
        {"scan_date": "2026-08-01", "ticker": "AAA", "fwd_3d_return": ""},
        {"scan_date": "2026-08-17", "ticker": "NEW", "fwd_3d_return": ""},
    ]
    updates = {
        ("2026-08-01", "AAA"): {"fwd_3d_return": 4.2},
    }

    changed = mod.merge_forward_updates(latest_rows, updates)

    if changed != 1:
        raise AssertionError(changed)
    if latest_rows[0]["fwd_3d_return"] != 4.2:
        raise AssertionError(latest_rows)
    if latest_rows[1]["ticker"] != "NEW" or latest_rows[1]["fwd_3d_return"] != "":
        raise AssertionError("concurrent append was changed or lost")


def test_merge_never_overwrites_previously_committed_return() -> None:
    mod = load_module()
    rows = [{
        "scan_date": "2026-08-01",
        "ticker": "AAA",
        "fwd_3d_return": "9.9",
    }]
    changed = mod.merge_forward_updates(
        rows,
        {("2026-08-01", "AAA"): {"fwd_3d_return": 4.2}},
    )
    if changed != 0 or rows[0]["fwd_3d_return"] != "9.9":
        raise AssertionError(rows)


def main() -> None:
    tests = [
        test_merge_forward_updates_retains_concurrently_appended_row,
        test_merge_never_overwrites_previously_committed_return,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
