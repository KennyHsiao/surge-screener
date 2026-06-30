#!/usr/bin/env python3
"""Tests for sector rotation snapshot persistence."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_rotation():
    spec = importlib.util.spec_from_file_location(
        "sector_rotation_under_test",
        ROOT / "scripts" / "sector_rotation.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_write_rotation_snapshot_writes_archive_and_preserves_latest_symlink() -> None:
    mod = _load_rotation()
    payload = {
        "status": "ready",
        "generated_at": "2026-06-28T21:00:00Z",
        "as_of": "2026-06-28",
        "benchmark": "SPY",
        "leaders": ["XLK"],
        "improving": ["XLI"],
        "sectors": [{"etf": "XLK", "quadrant": "Leading"}],
        "read": {"headline": "科技領漲", "confidence": "medium"},
    }

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        release_reports = tmp / "current" / "reports"
        shared = tmp / "shared"
        archive_dir = release_reports / "sector_rotation_snapshots"
        release_reports.mkdir(parents=True)
        shared.mkdir()
        snapshot_path = release_reports / "sector_rotation.json"
        target_path = shared / "sector_rotation.json"
        snapshot_path.symlink_to(target_path)

        mod._write_rotation_snapshot(payload, output=snapshot_path, archive_dir=archive_dir)

        latest = json.loads(target_path.read_text(encoding="utf-8"))
        archived = json.loads((archive_dir / "2026-06-28.json").read_text(encoding="utf-8"))
        symlink_preserved = snapshot_path.is_symlink()

    if not symlink_preserved:
        raise AssertionError("sector rotation writer replaced the release symlink")
    if latest["sectors"][0]["etf"] != "XLK":
        raise AssertionError(latest)
    if archived != latest:
        raise AssertionError((latest, archived))


def test_generate_rotation_read_persists_verified_sector_rows() -> None:
    mod = _load_rotation()

    class FakeLLMClient:
        def __init__(self, **_kwargs):
            pass

        def chat(self, _system, _user, max_tokens):
            if max_tokens != 2500:
                raise AssertionError(max_tokens)
            return json.dumps({
                "headline": "科技領漲",
                "hot_now": [{"etf": "XLK", "why": "heat"}],
                "rotating_into": [{"etf": "XLI", "why": "momentum"}],
                "next_rotation_thesis": "工業可能接棒。",
                "cycle_read": "risk-on",
                "confidence": "medium",
                "caveats": ["樣本短"],
            })

    original_payload = mod._verified_payload
    original_client = mod.LLMClient
    mod._verified_payload = lambda: {
        "as_of": "2026-06-29",
        "benchmark": "SPY",
        "leaders": ["XLK"],
        "improving": ["XLI"],
        "macro": {"spy_price": 612.0},
        "sectors": [{
            "etf": "XLK",
            "name_zh": "科技",
            "quadrant": "Leading",
            "rs_ratio": 104.2,
            "rs_momentum": 101.8,
        }],
    }
    mod.LLMClient = FakeLLMClient
    try:
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / "sector_rotation.json"

            result = mod.generate_rotation_read(output=str(output))

            latest = json.loads(output.read_text(encoding="utf-8"))
            archived = json.loads((output.parent / "sector_rotation_snapshots" / "2026-06-29.json").read_text(encoding="utf-8"))
    finally:
        mod._verified_payload = original_payload
        mod.LLMClient = original_client

    if result["sectors"][0]["etf"] != "XLK":
        raise AssertionError(result)
    if latest["benchmark"] != "SPY" or latest["sectors"][0]["rs_ratio"] != 104.2:
        raise AssertionError(latest)
    if archived != latest:
        raise AssertionError((latest, archived))


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
    if failed:
        print(f"{failed} failed")
        return 1
    print(f"{len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
