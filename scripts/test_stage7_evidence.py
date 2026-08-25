#!/usr/bin/env python3
"""Regression tests for Stage 7 run-bound terminal evidence."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "stage7_evidence_under_test", ROOT / "scripts" / "stage7_evidence.py",
    )
    if spec is None or spec.loader is None:
        raise AssertionError("scripts/stage7_evidence.py is missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_ledger(path: Path, mod, rows: list[dict[str, str]]) -> None:
    fieldnames = ["scan_date", "ticker", "notes", *mod.FORWARD_FIELDS]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _row(mod, *, value: str = "") -> dict[str, str]:
    row = {field: "" for field in mod.FORWARD_FIELDS}
    row.update({"scan_date": "2026-08-01", "ticker": "AAA", "notes": "locked", "fwd_3d_return": value})
    return row


def _write_receipt(path: Path, sent: list[dict] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, "sent": sent or []}) + "\n", encoding="utf-8")


def _prepare(root: Path, mod, *, value: str = "") -> dict[str, Path]:
    paths = {
        "ledger": root / "performance_ledger.csv",
        "receipt": root / "no_picks_alerts.json",
        "baseline": root / "evidence" / "baseline.json",
        "verify_log": root / "evidence" / "verify.log",
        "checks": root / "checks.json",
        "gate": root / "evidence" / "prepublish.json",
        "publish": root / "evidence" / "publish.json",
        "verdict": root / "evidence" / "verdict.json",
    }
    _write_ledger(paths["ledger"], mod, [_row(mod, value=value)])
    _write_receipt(paths["receipt"])
    mod.capture_baseline(
        ledger=paths["ledger"],
        receipt=paths["receipt"],
        output=paths["baseline"],
        run_id="123",
        run_attempt="1",
        head_sha="a" * 40,
        event_name="schedule",
        schedule="0 13 * * 1-5",
    )
    paths["checks"].write_text(json.dumps({
        "as_of_date": "2026-08-20",
        "status": "WARN",
        "summary": {"pass": 54, "warn": 13, "block": 0},
    }), encoding="utf-8")
    paths["gate"].write_text(json.dumps({
        "state": "READY_NOOP",
        "analytics": {"scope": "github_runner_ephemeral", "authoritative_for_7f": False},
    }), encoding="utf-8")
    paths["publish"].write_text(json.dumps({
        "status": "nothing_to_commit", "attempts": 0, "paths": mod.PUBLISH_PATHS,
    }), encoding="utf-8")
    return paths


def _finalize(mod, paths: dict[str, Path], **overrides):
    arguments = {
        "baseline_path": paths["baseline"],
        "ledger": paths["ledger"],
        "receipt": paths["receipt"],
        "verify_log": paths["verify_log"],
        "gate_result": paths["gate"],
        "publish_result": paths["publish"],
        "verify_outcome": "success",
        "analytics_outcome": "success",
        "gate_outcome": "success",
        "publish_outcome": "success",
        "result_head_sha": "a" * 40,
        "output": paths["verdict"],
    }
    arguments.update(overrides)
    return mod.finalize_verdict(**arguments)


def _gate(mod, paths: dict[str, Path]):
    return mod.prepublish_gate(
        baseline_path=paths["baseline"], ledger=paths["ledger"], receipt=paths["receipt"],
        verify_log=paths["verify_log"], checks=paths["checks"],
        verify_outcome="success", analytics_outcome="success", output=paths["gate"],
    )


def test_noop_is_explicit_and_analytics_is_non_authoritative() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        paths = _prepare(Path(tmp), mod, value="4.2")
        paths["verify_log"].write_text(
            "[verify] Updated 0 rows in reports/performance_ledger.csv\n", encoding="utf-8",
        )
        gate, gate_code = _gate(mod, paths)
        if gate_code != 0 or gate["state"] != "READY_NOOP":
            raise AssertionError(gate)
        verdict, return_code = _finalize(mod, paths)
        if return_code != 0 or verdict["state"] != "PASS_NOOP":
            raise AssertionError(verdict)
        if not verdict["coverage"]["natural_noop_observed"]:
            raise AssertionError(verdict["coverage"])
        if verdict["coverage"]["positive_update_observed"]:
            raise AssertionError("no-op overclaimed positive update coverage")
        if verdict["analytics"]["authoritative_for_7f"] is not False:
            raise AssertionError("job-local Analytics was marked authoritative for 7F")


def test_blank_forward_cell_can_be_filled_without_overwriting_locked_data() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        paths = _prepare(Path(tmp), mod)
        _write_ledger(paths["ledger"], mod, [_row(mod, value="4.2")])
        _write_receipt(paths["receipt"], [{"key": "bucket-4", "sent_at": "2026-08-20T13:00:00Z"}])
        paths["verify_log"].write_text(
            "[verify] Updated 1 rows in reports/performance_ledger.csv\n", encoding="utf-8",
        )
        paths["publish"].write_text(json.dumps({
            "status": "pushed", "attempts": 2, "commit": "b" * 40,
            "paths": mod.PUBLISH_PATHS,
        }), encoding="utf-8")
        verdict, return_code = _finalize(mod, paths, result_head_sha="b" * 40)
        if return_code != 0 or verdict["state"] != "PASS_UPDATED":
            raise AssertionError(verdict)
        changes = verdict["ledger"]["comparison"]["changed_cells"]
        if changes != [{"key": "2026-08-01|AAA", "field": "fwd_3d_return", "value": "4.2"}]:
            raise AssertionError(changes)
        if verdict["receipt"]["comparison"]["appended_keys"] != ["bucket-4"]:
            raise AssertionError(verdict["receipt"])
        if not verdict["coverage"]["push_race_observed"]:
            raise AssertionError(verdict["coverage"])


def test_receipt_only_publication_is_an_explicit_update() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        paths = _prepare(Path(tmp), mod, value="4.2")
        _write_receipt(paths["receipt"], [
            {"key": "bucket-4", "sent_at": "2026-08-25T13:00:00Z"},
        ])
        paths["verify_log"].write_text(
            "[verify] Updated 0 rows in reports/performance_ledger.csv\n", encoding="utf-8",
        )
        gate, gate_code = _gate(mod, paths)
        if gate_code != 0 or gate["state"] != "READY_UPDATED":
            raise AssertionError(gate)
        paths["publish"].write_text(json.dumps({
            "status": "pushed", "attempts": 1, "commit": "b" * 40,
            "paths": mod.PUBLISH_PATHS,
        }), encoding="utf-8")
        verdict, return_code = _finalize(mod, paths, result_head_sha="b" * 40)
        if return_code != 0 or verdict["state"] != "PASS_UPDATED":
            raise AssertionError(verdict)
        if verdict["coverage"]["positive_update_observed"]:
            raise AssertionError("receipt-only publication overclaimed a ledger return update")
        if not verdict["coverage"]["receipt_update_observed"]:
            raise AssertionError(verdict["coverage"])


def test_previously_committed_return_overwrite_fails_integrity() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        paths = _prepare(Path(tmp), mod, value="9.9")
        _write_ledger(paths["ledger"], mod, [_row(mod, value="4.2")])
        paths["verify_log"].write_text(
            "[verify] Updated 1 rows in reports/performance_ledger.csv\n", encoding="utf-8",
        )
        gate, gate_code = _gate(mod, paths)
        if gate_code != 1 or gate["state"] != "FAIL_LEDGER_INTEGRITY":
            raise AssertionError("corrupt overwrite was not stopped before publication")
        _write_ledger(paths["ledger"], mod, [_row(mod, value="9.9"), {
            **_row(mod), "scan_date": "2026-08-02", "ticker": "NEW",
        }])
        gate, gate_code = _gate(mod, paths)
        if gate_code != 1 or not any("introduced new ledger rows" in e for e in gate["errors"]):
            raise AssertionError("Stage 7 append was not stopped before publication")
        _write_ledger(paths["ledger"], mod, [_row(mod, value="4.2")])
        verdict, return_code = _finalize(mod, paths)
        if return_code != 1 or verdict["state"] != "FAIL_LEDGER_INTEGRITY":
            raise AssertionError(verdict)
        if not any("was overwritten" in error for error in verdict["errors"]):
            raise AssertionError(verdict["errors"])


def test_step_failure_writes_terminal_fail_verdict() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        paths = _prepare(Path(tmp), mod, value="4.2")
        paths["publish"].unlink()
        verdict, return_code = _finalize(
            mod,
            paths,
            verify_outcome="failure",
            analytics_outcome="skipped",
            publish_outcome="skipped",
        )
        if return_code != 1 or verdict["state"] != "FAIL_JOB":
            raise AssertionError(verdict)
        persisted = json.loads(paths["verdict"].read_text(encoding="utf-8"))
        if persisted["state"] != "FAIL_JOB":
            raise AssertionError("terminal failure verdict was not persisted")
        paths["publish"].write_text(json.dumps({
            "status": "pushed", "attempts": "invalid", "commit": "c" * 40,
            "paths": mod.PUBLISH_PATHS,
        }), encoding="utf-8")
        verdict, return_code = _finalize(mod, paths)
        if return_code != 1 or verdict["state"] != "FAIL_EVIDENCE":
            raise AssertionError("malformed publisher evidence did not fail closed")


if __name__ == "__main__":
    tests = [
        test_noop_is_explicit_and_analytics_is_non_authoritative,
        test_blank_forward_cell_can_be_filled_without_overwriting_locked_data,
        test_receipt_only_publication_is_an_explicit_update,
        test_previously_committed_return_overwrite_fails_integrity,
        test_step_failure_writes_terminal_fail_verdict,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")
