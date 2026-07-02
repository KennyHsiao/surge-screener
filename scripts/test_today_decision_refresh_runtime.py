#!/usr/bin/env python3
"""Runtime helpers for Today Decision local candidate refresh.

Run: .venv/bin/python scripts/test_today_decision_refresh_runtime.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui import today_decision as td  # noqa: E402


def require(condition: bool, message) -> None:
    if not condition:
        raise AssertionError(message)


def test_running_candidate_status_is_inactive_when_pid_is_gone() -> None:
    data = {
        "job": "candidates-local",
        "status": "running",
        "pid": 284712,
        "updated_at": "2026-07-02T08:07:55Z",
        "stage": {
            "id": "hard_filter.info",
            "label": "補 market cap / earnings",
            "status": "running",
            "progress_pct": 78.5,
            "message": "Fetched info 1180/1503",
        },
    }

    active = td._status_is_active(
        data,
        now=datetime(2026, 7, 2, 8, 8, tzinfo=timezone.utc),
        process_checker=lambda pid: False,
    )

    require(active is False, "missing PID must not keep candidate refresh running")


def test_interrupted_candidate_status_marks_stage_failed() -> None:
    data = {
        "job": "candidates-local",
        "run_id": "candidates-local-2026-07-02T07:54:27Z",
        "status": "running",
        "pid": 284712,
        "started_at": "2026-07-02T07:54:27Z",
        "updated_at": "2026-07-02T08:07:55Z",
        "stage": {
            "id": "hard_filter.info",
            "label": "補 market cap / earnings",
            "status": "running",
            "progress_pct": 78.5,
            "message": "Fetched info 1180/1503",
        },
        "stages": [
            {"id": "preflight", "label": "本機流程初始化", "status": "succeeded", "progress_pct": 100},
            {"id": "hard_filter.info", "label": "補 market cap / earnings", "status": "running", "progress_pct": 78.5},
            {"id": "rank_candidates", "label": "程式排序候選", "status": "pending", "progress_pct": 0},
        ],
        "errors": [],
    }

    fixed = td._interrupted_candidate_status(
        data,
        "背景程序已不存在，這次本機候選刷新已中斷。",
        now=datetime(2026, 7, 2, 8, 20, tzinfo=timezone.utc),
    )

    require(fixed["status"] == "failed", fixed)
    require(fixed["stage"]["status"] == "failed", fixed["stage"])
    require(fixed["finished_at"] == "2026-07-02T08:20:00Z", fixed)
    require(fixed["stages"][1]["status"] == "failed", fixed["stages"])
    require(fixed["errors"][-1]["stage"] == "hard_filter.info", fixed["errors"])


def main() -> None:
    tests = [
        test_running_candidate_status_is_inactive_when_pid_is_gone,
        test_interrupted_candidate_status_marks_stage_failed,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
