#!/usr/bin/env python3
"""Runtime helper tests for Today Decision candidate controls."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui import _candidate_controls as cc  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_candidate_status_is_inactive_when_pid_is_gone() -> None:
    data = {
        "status": "running",
        "pid": 12345,
        "updated_at": "2026-07-03T06:00:00Z",
    }

    active = cc._status_is_active(
        data,
        now=datetime(2026, 7, 3, 6, 1, tzinfo=timezone.utc),
        process_checker=lambda pid: False,
    )

    require(active is False, "missing PID must not keep candidate controls disabled")


def test_interrupted_candidate_status_records_failed_stage() -> None:
    data = {
        "status": "running",
        "stage": {"id": "rank_candidates", "label": "程式排序候選", "progress_pct": 50},
        "stages": [
            {"id": "rank_candidates", "label": "程式排序候選", "status": "running", "progress_pct": 50},
        ],
        "errors": [],
    }

    fixed = cc._interrupted_candidate_status(
        data,
        "背景程序已不存在，這次本機候選刷新已中斷。",
        now=datetime(2026, 7, 3, 6, 10, tzinfo=timezone.utc),
    )

    require(fixed["status"] == "failed", str(fixed))
    require(fixed["stage"]["status"] == "failed", str(fixed["stage"]))
    require(fixed["finished_at"] == "2026-07-03T06:10:00Z", str(fixed))
    require(fixed["errors"][-1]["stage"] == "rank_candidates", str(fixed["errors"]))


def test_status_message_translates_llm_progress() -> None:
    message = cc._status_message_zh("7 candidates scored; 2 remaining")
    require(message == "LLM 已累積 7 檔；尚有 2 檔未深檢", message)


def test_history_flow_classifies_refresh_modes() -> None:
    require(
        cc._history_flow({"metrics": {"passed_hard_filters": 20}, "stage": {}}) == "完整刷新 + 排名",
        "full refresh history label mismatch",
    )
    require(
        cc._history_flow({"metrics": {"scored_candidates": 3}, "stage": {}}) == "少量 LLM",
        "LLM history label mismatch",
    )
    require(
        cc._history_flow({"metrics": {"ranked_candidates": 50}, "stage": {}}) == "只重排",
        "rank-only history label mismatch",
    )


def main() -> None:
    tests = [
        test_candidate_status_is_inactive_when_pid_is_gone,
        test_interrupted_candidate_status_records_failed_stage,
        test_status_message_translates_llm_progress,
        test_history_flow_classifies_refresh_modes,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
