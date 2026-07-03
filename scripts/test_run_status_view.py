#!/usr/bin/env python3
"""Tests for shared UI run-status reconciliation helpers."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui import _run_status_view as rv


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_pid_gone_interrupts_running_status() -> None:
    data = {
        "status": "running",
        "pid": 12345,
        "updated_at": "2026-07-02T09:39:23Z",
    }

    reason = rv.running_interrupt_reason(
        data,
        stale_after_seconds=600,
        stale_message="stale",
        pid_gone_message="pid gone",
        now=datetime(2026, 7, 2, 9, 40, tzinfo=timezone.utc),
        process_checker=lambda pid: False,
    )

    require(reason == "pid gone", reason or "missing reason")
    require(
        rv.running_status_is_active(
            data,
            stale_after_seconds=600,
            stale_message="stale",
            pid_gone_message="pid gone",
            now=datetime(2026, 7, 2, 9, 40, tzinfo=timezone.utc),
            process_checker=lambda pid: False,
        )
        is False,
        "missing PID should not keep a UI action disabled",
    )


def test_stale_running_status_uses_page_specific_message() -> None:
    data = {
        "status": "running",
        "pid": 12345,
        "updated_at": "2026-07-02T09:00:00Z",
    }

    reason = rv.running_interrupt_reason(
        data,
        stale_after_seconds=600,
        stale_message="本機候選刷新已超過 10 分鐘未更新，可能已中斷。",
        pid_gone_message="pid gone",
        now=datetime(2026, 7, 2, 9, 20, tzinfo=timezone.utc),
        process_checker=lambda pid: True,
    )

    require(reason == "本機候選刷新已超過 10 分鐘未更新，可能已中斷。", reason or "")


def test_interrupted_status_preserves_stage_order_and_records_error() -> None:
    data = {
        "status": "running",
        "stage": {"id": "source_refresh", "label": "刷新核心資料源", "progress_pct": 5},
        "stages": [
            {"id": "source_refresh", "label": "刷新核心資料源", "status": "running", "progress_pct": 5},
            {"id": "analytics_store", "label": "重建 Analytics DB", "status": "pending", "progress_pct": 0},
        ],
        "errors": [{"stage": "previous", "message": "old", "at": "2026-07-02T09:00:00Z"}],
    }

    fixed = rv.interrupted_status(
        data,
        "背景程序已不存在，這次資料刷新已中斷；可重新啟動。",
        default_label="資料刷新中斷",
        now=datetime(2026, 7, 2, 9, 48, tzinfo=timezone.utc),
    )

    require(fixed["status"] == "failed", fixed)
    require(fixed["finished_at"] == "2026-07-02T09:48:00Z", fixed)
    require([stage["id"] for stage in fixed["stages"]] == ["source_refresh", "analytics_store"], fixed["stages"])
    require(fixed["stages"][0]["status"] == "failed", fixed["stages"])
    require(fixed["stage"]["message"] == "背景程序已不存在，這次資料刷新已中斷；可重新啟動。", fixed["stage"])
    require(len(fixed["errors"]) == 2, fixed["errors"])


def main() -> None:
    tests = [
        test_pid_gone_interrupts_running_status,
        test_stale_running_status_uses_page_specific_message,
        test_interrupted_status_preserves_stage_order_and_records_error,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
