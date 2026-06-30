#!/usr/bin/env python3
"""Offline tests for crypto universe refresh failure handling."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_crypto_universe():
    spec = importlib.util.spec_from_file_location(
        "crypto_universe_under_test",
        ROOT / "scripts" / "crypto_universe.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_build_snapshot_uses_stale_previous_snapshot_when_fetch_fails() -> None:
    crypto = _load_crypto_universe()
    with tempfile.TemporaryDirectory() as d:
        out_dir = Path(d)
        previous = {
            "date": "2026-06-01",
            "source": "binance_fapi_exchangeInfo",
            "count": 2,
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "universe": [
                {"symbol": "BTCUSDT", "base": "BTC", "tv_symbol": "BINANCE:BTCUSDT.P"},
                {"symbol": "ETHUSDT", "base": "ETH", "tv_symbol": "BINANCE:ETHUSDT.P"},
            ],
            "added": [],
            "removed": [],
            "compared_to": None,
        }
        (out_dir / "2026-06-01.json").write_text(json.dumps(previous), encoding="utf-8")

        def failing_fetcher():
            raise RuntimeError("451 unavailable for legal reasons")

        snap = crypto.build_snapshot(out_dir, fetcher=failing_fetcher)

        if snap["source_status"] != "stale_fallback":
            raise AssertionError(snap)
        if snap["stale_source_date"] != "2026-06-01":
            raise AssertionError(snap)
        if snap["symbols"] != ["BTCUSDT", "ETHUSDT"] or snap["count"] != 2:
            raise AssertionError(snap)
        if snap["added"] or snap["removed"]:
            raise AssertionError(snap)
        if "451" not in snap["fetch_error"]:
            raise AssertionError(snap)


def test_build_snapshot_returns_unavailable_payload_without_previous_snapshot() -> None:
    crypto = _load_crypto_universe()
    with tempfile.TemporaryDirectory() as d:
        def failing_fetcher():
            raise RuntimeError("451 unavailable for legal reasons")

        snap = crypto.build_snapshot(Path(d), fetcher=failing_fetcher)

        if snap["source_status"] != "unavailable":
            raise AssertionError(snap)
        if snap["count"] != 0 or snap["symbols"] or snap["universe"]:
            raise AssertionError(snap)
        if "451" not in snap["fetch_error"]:
            raise AssertionError(snap)


def test_workflow_force_adds_gitignored_crypto_reports() -> None:
    workflow = (ROOT / ".github" / "workflows" / "surge_screener.yml").read_text(encoding="utf-8")
    if "git add -f reports/crypto/" not in workflow:
        raise AssertionError("crypto reports are gitignored; workflow must force-add generated outputs")


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
