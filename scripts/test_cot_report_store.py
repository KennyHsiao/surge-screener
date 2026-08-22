#!/usr/bin/env python3
"""Regression tests for durable COT runtime generation promotion."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    path = ROOT / "scripts" / "cot_report_store.py"
    spec = importlib.util.spec_from_file_location("cot_report_store_under_test", path)
    if spec is None or spec.loader is None:
        raise AssertionError("scripts/cot_report_store.py is missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_pair(
    directory: Path,
    report_date: str,
    marker: str,
    *,
    retrieved_at: str | None = None,
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{report_date}.md").write_text(
        f"# COT {report_date}\n\n{marker}\n", encoding="utf-8",
    )
    (directory / f"{report_date}.verified.json").write_text(
        json.dumps({
            "cot": {"as_of": report_date, "source": "test"},
            "price": {
                "friday_date": report_date,
                "friday_close": 7000.0,
                "retrieved_at": retrieved_at or f"{report_date}T12:00:00+00:00",
            },
            "marker": marker,
        }),
        encoding="utf-8",
    )


def _current(store: Path) -> Path:
    current = store / "current"
    if not current.is_symlink():
        raise AssertionError("current must be an atomic generation symlink")
    return current.resolve(strict=True)


def test_promote_builds_complete_generation_and_is_idempotent() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        source = root / "source"
        store = root / "store"
        _write_pair(source, "2026-08-21", "first")

        first = mod.promote_cot_reports(source, store)
        current = _current(store)

        if first["status"] != "promoted" or first["pair_count"] != 1:
            raise AssertionError(first)
        if (current / "2026-08-21.md").read_text(encoding="utf-8").find("first") < 0:
            raise AssertionError("promoted markdown is missing")
        json.loads((current / "2026-08-21.verified.json").read_text(encoding="utf-8"))

        second = mod.promote_cot_reports(source, store)
        if second["status"] != "unchanged" or _current(store) != current:
            raise AssertionError(second)


def test_older_source_cannot_remove_a_newer_current_pair() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        initial = root / "initial"
        older = root / "older"
        store = root / "store"
        _write_pair(initial, "2026-08-14", "old")
        _write_pair(initial, "2026-08-21", "new")
        mod.promote_cot_reports(initial, store)
        _write_pair(older, "2026-08-14", "old")

        result = mod.promote_cot_reports(older, store)
        current = _current(store)

        if result["pair_count"] != 2:
            raise AssertionError(result)
        if not (current / "2026-08-21.md").is_file():
            raise AssertionError("monotonic merge dropped the newer durable pair")


def test_older_same_date_source_cannot_replace_a_newer_current_pair() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        newest = root / "newest"
        stale = root / "stale"
        store = root / "store"
        _write_pair(
            newest, "2026-08-21", "newer",
            retrieved_at="2026-08-22T08:00:00+00:00",
        )
        _write_pair(
            stale, "2026-08-21", "older",
            retrieved_at="2026-08-22T07:00:00+00:00",
        )
        mod.promote_cot_reports(newest, store)

        result = mod.promote_cot_reports(stale, store)

        if result["status"] != "unchanged":
            raise AssertionError(result)
        if "newer" not in (_current(store) / "2026-08-21.md").read_text(encoding="utf-8"):
            raise AssertionError("same-date stale source replaced the newer current pair")


def test_invalid_source_pair_preserves_last_known_good() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        source = root / "source"
        invalid = root / "invalid"
        store = root / "store"
        _write_pair(source, "2026-08-21", "good")
        mod.promote_cot_reports(source, store)
        before = os.readlink(store / "current")
        invalid.mkdir()
        (invalid / "2026-08-22.md").write_text("# orphan\n", encoding="utf-8")

        try:
            mod.promote_cot_reports(invalid, store)
        except ValueError as exc:
            if "complete pair" not in str(exc):
                raise AssertionError(exc) from exc
        else:
            raise AssertionError("orphan COT report unexpectedly promoted")

        if os.readlink(store / "current") != before:
            raise AssertionError("invalid source changed current generation")
        if "good" not in (_current(store) / "2026-08-21.md").read_text(encoding="utf-8"):
            raise AssertionError("last-known-good pair changed")


def test_current_symlink_failure_keeps_previous_generation_visible() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        source = root / "source"
        update = root / "update"
        store = root / "store"
        _write_pair(source, "2026-08-14", "baseline")
        mod.promote_cot_reports(source, store)
        before = os.readlink(store / "current")
        _write_pair(update, "2026-08-21", "candidate")

        def fail_current_replace(source_path, destination_path):
            if Path(destination_path).name == "current":
                raise OSError("injected current promotion failure")
            os.replace(source_path, destination_path)

        try:
            mod.promote_cot_reports(update, store, replace_fn=fail_current_replace)
        except OSError as exc:
            if "injected current promotion failure" not in str(exc):
                raise AssertionError(exc) from exc
        else:
            raise AssertionError("injected promotion failure unexpectedly succeeded")

        if os.readlink(store / "current") != before:
            raise AssertionError("promotion failure changed current generation")
        if list(store.glob(".current-next-*")):
            raise AssertionError("failed promotion leaked a temporary current symlink")


def test_concurrent_promotions_serialize_without_losing_pairs() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        first = root / "first"
        second = root / "second"
        store = root / "store"
        _write_pair(first, "2026-08-14", "first")
        _write_pair(second, "2026-08-21", "second")
        command = [
            sys.executable,
            str(ROOT / "scripts" / "cot_report_store.py"),
        ]
        processes = [
            subprocess.Popen(
                command + ["--source-dir", str(source), "--store-dir", str(store)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for source in (first, second)
        ]
        for process in processes:
            stdout, stderr = process.communicate(timeout=15)
            if process.returncode != 0:
                raise AssertionError((process.returncode, stdout, stderr))

        current = _current(store)
        expected = {
            "2026-08-14.md",
            "2026-08-14.verified.json",
            "2026-08-21.md",
            "2026-08-21.verified.json",
        }
        if {path.name for path in current.iterdir()} != expected:
            raise AssertionError("concurrent promotion lost a complete report pair")


def main() -> None:
    tests = [
        test_promote_builds_complete_generation_and_is_idempotent,
        test_older_source_cannot_remove_a_newer_current_pair,
        test_older_same_date_source_cannot_replace_a_newer_current_pair,
        test_invalid_source_pair_preserves_last_known_good,
        test_current_symlink_failure_keeps_previous_generation_visible,
        test_concurrent_promotions_serialize_without_losing_pairs,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
