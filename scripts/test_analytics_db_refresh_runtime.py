#!/usr/bin/env python3
"""Runtime helpers for Analytics DB refresh center.

Run: .venv/bin/python scripts/test_analytics_db_refresh_runtime.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui import analytics_db as adb  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_running_data_health_status_is_inactive_when_pid_is_gone() -> None:
    data = {
        "status": "running",
        "pid": 12345,
        "updated_at": "2026-07-02T09:39:23Z",
        "stage": {"id": "source_refresh", "label": "刷新核心資料源", "progress_pct": 5},
    }

    active = adb._data_health_refresh_is_active(
        data,
        now=datetime(2026, 7, 2, 9, 40, tzinfo=timezone.utc),
        process_checker=lambda pid: False,
    )

    require(active is False, "missing PID must not keep the heavy refresh button disabled")


def test_interrupted_data_health_status_marks_running_stage_failed() -> None:
    data = {
        "status": "running",
        "pid": 12345,
        "started_at": "2026-07-02T09:39:23Z",
        "updated_at": "2026-07-02T09:39:23Z",
        "stage": {
            "id": "source_refresh",
            "label": "刷新核心資料源",
            "status": "running",
            "progress_pct": 5,
            "message": "刷新 universe / daily bars / money flow，可能需要 10-25 分鐘。",
        },
        "stages": [
            {"id": "source_refresh", "label": "刷新核心資料源", "status": "running", "progress_pct": 5},
            {"id": "analytics_store", "label": "重建 Analytics DB", "status": "pending", "progress_pct": 0},
        ],
        "errors": [],
    }

    fixed = adb._interrupted_data_health_status(
        data,
        "背景程序已不存在，這次刷新已中斷。",
        now=datetime(2026, 7, 2, 9, 48, tzinfo=timezone.utc),
    )

    require(fixed["status"] == "failed", "interrupted run should be terminal failed")
    require(fixed["stage"]["status"] == "failed", "current stage should be failed")
    require(fixed["finished_at"] == "2026-07-02T09:48:00Z", fixed)
    require(fixed["errors"], "interrupted run should record an error message")
    require(fixed["stages"][0]["status"] == "failed", fixed["stages"])


def test_linux_launcher_uses_systemd_run_for_service_survival() -> None:
    command = ["/app/.venv/bin/python", "/app/current/scripts/data_source_refresh.py", "--json"]
    launcher, meta = adb._build_refresh_launcher(
        command,
        cwd=Path("/app/current"),
        log_path=Path("/app/shared/run_status/data-health-refresh.log"),
        platform="linux",
        systemd_run_path="/usr/bin/systemd-run",
        unit_name="surge-data-health-refresh-test",
    )

    joined = " ".join(launcher)
    require(launcher[:3] == ["/usr/bin/systemd-run", "--user", "--unit=surge-data-health-refresh-test"], launcher)
    require("--collect" in launcher, launcher)
    require(meta["launch_mode"] == "systemd-run", meta)
    require(meta["unit"] == "surge-data-health-refresh-test.service", meta)
    require("exec >>/app/shared/run_status/data-health-refresh.log 2>&1" in joined, launcher)
    require("/app/.venv/bin/python /app/current/scripts/data_source_refresh.py --json" in joined, launcher)


def test_launcher_falls_back_to_direct_popen_without_systemd() -> None:
    command = ["/app/.venv/bin/python", "/app/current/scripts/data_source_refresh.py", "--json"]
    launcher, meta = adb._build_refresh_launcher(
        command,
        cwd=Path("/app/current"),
        log_path=Path("/app/shared/run_status/data-health-refresh.log"),
        platform="darwin",
        systemd_run_path=None,
        unit_name="ignored",
    )

    require(launcher == command, launcher)
    require(meta["launch_mode"] == "popen", meta)


def main() -> None:
    tests = [
        test_running_data_health_status_is_inactive_when_pid_is_gone,
        test_interrupted_data_health_status_marks_running_stage_failed,
        test_linux_launcher_uses_systemd_run_for_service_survival,
        test_launcher_falls_back_to_direct_popen_without_systemd,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
