#!/usr/bin/env python3
"""Tests for background theme-flow refresh controls."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_controls():
    spec = importlib.util.spec_from_file_location(
        "theme_flow_controls_under_test",
        ROOT / "scripts" / "theme_flow_controls.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_refresh_command_runs_worker_for_requested_mode() -> None:
    mod = _load_controls()
    cmd = mod.build_command("refresh_board")

    if cmd[0] != sys.executable:
        raise AssertionError(cmd)
    if not any(part.endswith("scripts/theme_flow_background.py") for part in cmd):
        raise AssertionError(cmd)
    if "--mode" not in cmd or "refresh_board" not in cmd:
        raise AssertionError(cmd)


def test_launch_background_starts_detached_process_and_records_status() -> None:
    mod = _load_controls()
    launched = {}

    class FakeProcess:
        pid = 789

    def fake_process_factory(command, **kwargs):
        launched["command"] = command
        launched["kwargs"] = kwargs
        return FakeProcess()

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        status_path = tmp / "status.json"
        log_path = tmp / "theme-flow.log"
        meta = mod.launch_background(
            "refresh_board",
            status_path=status_path,
            log_path=log_path,
            process_factory=fake_process_factory,
        )
        status = json.loads(status_path.read_text(encoding="utf-8"))

    if meta["pid"] != 789 or meta["mode"] != "refresh_board":
        raise AssertionError(meta)
    if launched["kwargs"].get("start_new_session") is not True:
        raise AssertionError(launched)
    if launched["kwargs"].get("stdout") is None or launched["kwargs"].get("stderr") is None:
        raise AssertionError(launched)
    if status["status"] != "running" or status["pid"] != 789:
        raise AssertionError(status)


def test_read_snapshot_uses_snapshot_before_stale_cache() -> None:
    mod = _load_controls()
    fresh = {
        "schema_version": 4,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": "2026-06-26",
        "themes": [{"theme": "fresh"}],
    }
    stale = {
        "generated_at": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
        "as_of": "2026-06-23",
        "themes": [{"theme": "stale"}],
    }

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        snapshot_path = tmp / "theme_flow_snapshot.json"
        cache_path = tmp / "theme_flow_cache.json"
        snapshot_path.write_text(json.dumps(fresh), encoding="utf-8")
        cache_path.write_text(json.dumps(stale), encoding="utf-8")

        got = mod.read_snapshot(snapshot_path=snapshot_path, cache_reader=lambda: stale)

    if got["themes"][0]["theme"] != "fresh":
        raise AssertionError(got)
    if mod.snapshot_is_stale(got, ttl_seconds=3600):
        raise AssertionError(got)


def test_write_snapshot_also_writes_dated_archive() -> None:
    mod = _load_controls()
    flow = {
        "schema_version": 4,
        "generated_at": "2026-06-26T21:00:00Z",
        "as_of": "2026-06-26",
        "themes": [{"theme": "archive"}],
    }

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        snapshot_path = tmp / "theme_flow_snapshot.json"
        archive_dir = tmp / "theme_flow_snapshots"

        mod.write_snapshot(flow, snapshot_path=snapshot_path, archive_dir=archive_dir)

        latest = json.loads(snapshot_path.read_text(encoding="utf-8"))
        archived = json.loads((archive_dir / "2026-06-26.json").read_text(encoding="utf-8"))

    if latest["themes"][0]["theme"] != "archive":
        raise AssertionError(latest)
    if archived != latest:
        raise AssertionError((latest, archived))


def test_write_snapshot_preserves_latest_symlink_target() -> None:
    mod = _load_controls()
    flow = {
        "schema_version": 4,
        "generated_at": "2026-06-27T21:00:00Z",
        "as_of": "2026-06-27",
        "themes": [{"theme": "shared"}],
    }

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        release_reports = tmp / "current" / "reports"
        shared = tmp / "shared"
        release_reports.mkdir(parents=True)
        shared.mkdir()
        snapshot_path = release_reports / "theme_flow_snapshot.json"
        target_path = shared / "theme_flow_snapshot.json"
        snapshot_path.symlink_to(target_path)

        mod.write_snapshot(flow, snapshot_path=snapshot_path, archive_dir=None)

        written = json.loads(target_path.read_text(encoding="utf-8"))
        symlink_preserved = snapshot_path.is_symlink()

    if not symlink_preserved:
        raise AssertionError("write_snapshot replaced the release symlink")
    if written["themes"][0]["theme"] != "shared":
        raise AssertionError(written)


def test_read_snapshot_ignores_legacy_schema_before_cache() -> None:
    mod = _load_controls()
    legacy = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": "2026-06-25",
        "themes": [{"theme": "legacy"}],
    }
    current = {
        "schema_version": 4,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": "2026-06-26",
        "themes": [{"theme": "current"}],
    }

    with tempfile.TemporaryDirectory() as d:
        snapshot_path = Path(d) / "theme_flow_snapshot.json"
        snapshot_path.write_text(json.dumps(legacy), encoding="utf-8")

        got = mod.read_snapshot(snapshot_path=snapshot_path, cache_reader=lambda: current)

    if got["themes"][0]["theme"] != "current":
        raise AssertionError(got)


def test_snapshot_stale_when_generated_at_is_old_or_missing() -> None:
    mod = _load_controls()
    old = {"generated_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()}

    if not mod.snapshot_is_stale(old, ttl_seconds=3600):
        raise AssertionError(old)
    if not mod.snapshot_is_stale({}, ttl_seconds=3600):
        raise AssertionError("missing generated_at should be stale")


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
    sys.exit(main())
