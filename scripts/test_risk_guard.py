#!/usr/bin/env python3
"""Offline tests for Risk Guard report persistence helpers."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_risk_guard():
    spec = importlib.util.spec_from_file_location(
        "risk_guard_under_test",
        ROOT / "scripts" / "risk_guard.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_write_report_writes_latest_and_dated_snapshot() -> None:
    risk_guard = _load_risk_guard()
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "reports" / "risk_guard" / "latest.json"
        payload = {
            "as_of": "2026-06-05",
            "generated_at": "2026-06-05T22:00:00Z",
            "rows": [{"ticker": "NVDA", "status": "REDUCE", "risk_score": 55}],
        }

        paths = risk_guard.write_report(payload, out)

        latest = json.loads(out.read_text(encoding="utf-8"))
        snapshot_path = out.with_name("2026-06-05.json")
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if latest != payload or snapshot != payload:
            raise AssertionError((latest, snapshot))
        if paths.get("latest") != str(out) or paths.get("snapshot") != str(snapshot_path):
            raise AssertionError(paths)


def test_write_report_uses_generated_date_when_as_of_missing() -> None:
    risk_guard = _load_risk_guard()
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "latest.json"
        payload = {
            "generated_at": "2026-06-06T01:23:45Z",
            "rows": [],
        }

        paths = risk_guard.write_report(payload, out)

        if not out.with_name("2026-06-06.json").is_file():
            raise AssertionError(paths)


def main() -> int:
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, test in tests:
        try:
            test()
            print(f"  PASS {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
