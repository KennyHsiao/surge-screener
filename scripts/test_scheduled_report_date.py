#!/usr/bin/env python3
"""Regression tests for logical dates of delayed scheduled producers."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "scheduled_report_date_under_test",
    ROOT / "scripts" / "scheduled_report_date.py",
)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


def test_delayed_eod_keeps_the_logical_schedule_date() -> None:
    started = datetime(2026, 8, 27, 3, 24, 52, tzinfo=timezone.utc)
    assert MOD.resolve_report_date(
        schedule="30 22 * * 1-5",
        started_at=started,
    ).isoformat() == "2026-08-26"


def test_same_day_eod_after_slot_uses_the_current_utc_date() -> None:
    started = datetime(2026, 8, 27, 22, 31, tzinfo=timezone.utc)
    assert MOD.resolve_report_date(
        schedule="30 22 * * 1-5",
        started_at=started,
    ).isoformat() == "2026-08-27"


def test_manual_eod_uses_the_actual_utc_date() -> None:
    started = datetime(2026, 8, 27, 3, 24, 52, tzinfo=timezone.utc)
    assert MOD.resolve_report_date(schedule=None, started_at=started).isoformat() == "2026-08-27"


def test_unsupported_schedule_fails_closed() -> None:
    try:
        MOD.resolve_report_date(
            schedule="0 22 * * 1-5",
            started_at=datetime(2026, 8, 27, tzinfo=timezone.utc),
        )
    except ValueError as exc:
        assert "unsupported schedule" in str(exc)
    else:
        raise AssertionError("unsupported schedule must not guess a report date")


def test_runtime_override_propagates_the_logical_date() -> None:
    assert MOD.runtime_report_date(
        environment={"SURGE_REPORT_DATE": "2026-08-26"},
        now=datetime(2026, 8, 27, 3, 24, tzinfo=timezone.utc),
    ).isoformat() == "2026-08-26"


def test_invalid_runtime_override_fails_closed() -> None:
    try:
        MOD.runtime_report_date(environment={"SURGE_REPORT_DATE": "2026-02-30"})
    except ValueError as exc:
        assert "invalid SURGE_REPORT_DATE" in str(exc)
    else:
        raise AssertionError("invalid runtime date override must fail closed")


def test_cli_prints_only_the_resolved_date() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "scheduled_report_date.py"),
            "--schedule",
            "30 22 * * 1-5",
            "--started-at",
            "2026-08-27T03:24:52Z",
        ],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.stdout == "2026-08-26\n"
    assert result.stderr == ""


if __name__ == "__main__":
    test_delayed_eod_keeps_the_logical_schedule_date()
    test_same_day_eod_after_slot_uses_the_current_utc_date()
    test_manual_eod_uses_the_actual_utc_date()
    test_unsupported_schedule_fails_closed()
    test_runtime_override_propagates_the_logical_date()
    test_invalid_runtime_override_fails_closed()
    test_cli_prints_only_the_resolved_date()
    print("scheduled report date tests: 7 passed")
