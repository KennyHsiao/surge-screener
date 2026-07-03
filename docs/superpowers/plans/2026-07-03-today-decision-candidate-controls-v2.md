# Today Decision Candidate Controls Extraction v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract Today Decision's local candidate refresh controls into a focused module without splitting Claude auth, launch tracking, local run status, or history state.

**Architecture:** Create `ui/_candidate_controls.py` as the single owner of candidate refresh UI state. `ui/today_decision.py` remains the daily decision dashboard and calls `_candidate_controls.render()` before candidate results. Shared run-status reconciliation stays in `ui/_run_status_view.py`.

**Tech Stack:** Python, Streamlit fragments, existing `scripts.candidate_pipeline_controls`, static contract tests, local runtime helper tests.

---

## File Structure

- Create: `ui/_candidate_controls.py`
  - Owns candidate status file paths, candidate history, launch tracking, Claude auth status, candidate run buttons, and local refresh progress.
  - Exposes only `render()`.

- Create: `scripts/test_candidate_controls_view.py`
  - Runtime tests for helper behavior that should survive the move.

- Modify: `ui/today_decision.py`
  - Imports `_candidate_controls`.
  - Removes candidate-control-only imports, constants, and helper functions.
  - Replaces three render calls with `_candidate_controls.render()`.

- Modify: `scripts/test_dashboard_navigation.py`
  - Reads `ui/_candidate_controls.py` when present.
  - Moves candidate-controls static assertions from `TODAY` to `CANDIDATE_CONTROLS`.
  - Adds a guard that Today Decision delegates to `_candidate_controls.render()`.

---

### Task 1: Static Extraction Guard

**Files:**
- Modify: `scripts/test_dashboard_navigation.py`
- Test: `scripts/test_dashboard_navigation.py`

- [ ] **Step 1: Add candidate-controls source fixture**

Add this near the other UI source reads:

```python
CANDIDATE_CONTROLS_PATH = ROOT / "ui" / "_candidate_controls.py"
CANDIDATE_CONTROLS = (
    CANDIDATE_CONTROLS_PATH.read_text(encoding="utf-8")
    if CANDIDATE_CONTROLS_PATH.exists()
    else ""
)
```

- [ ] **Step 2: Add delegation contract test**

Add this test after `test_today_decision_renders_candidate_pipeline_controls` or near the Today Decision tests:

```python
def test_today_decision_delegates_candidate_controls_to_module() -> None:
    assert_contains(TODAY, "from . import _candidate_controls")
    assert_contains(TODAY, "_candidate_controls.render()")
    assert_not_contains(TODAY, "def _render_candidate_pipeline_controls")
    assert_not_contains(TODAY, "def _render_local_refresh_status")
    assert_not_contains(TODAY, "def _render_claude_auth_status")
    assert_contains(CANDIDATE_CONTROLS, "def render()")
    assert_contains(CANDIDATE_CONTROLS, "_render_candidate_pipeline_controls()")
    assert_contains(CANDIDATE_CONTROLS, "_render_claude_auth_status()")
    assert_contains(CANDIDATE_CONTROLS, "_render_local_refresh_status()")
```

- [ ] **Step 3: Move existing candidate-control static assertions to the new fixture**

In these tests, change the text source from `TODAY` to `CANDIDATE_CONTROLS`:

```python
test_today_decision_renders_candidate_pipeline_controls
test_today_decision_renders_local_refresh_progress
test_today_decision_history_falls_back_to_rank_source_candidates
test_today_decision_history_uses_plain_language_column_names
test_today_decision_history_shows_flow_instead_of_repeated_output_path
test_today_decision_launch_tracking_surfaces_status_and_log
test_today_decision_status_panel_uses_user_facing_language
```

For example:

```python
def test_today_decision_renders_candidate_pipeline_controls() -> None:
    for needle in [
        "def _render_candidate_pipeline_controls",
        "CandidateRunParams",
        "launch_background",
        "st.number_input",
        "排名 Top N",
        "期權檢查數",
        "LLM 深檢數",
        "RANK_LIMIT",
        "OPTIONS_GATE_LIMIT",
        "MIN_AVG_DOLLAR_VOL",
        "MIN_MARKET_CAP",
        "MAX_RET_5D",
        "MAX_RET_20D",
        "完整刷新",
        "只重排（進階）",
        "少量 LLM",
        "candidates-local-history.jsonl",
        "def _candidate_run_history",
        "篩選紀錄",
        "read_pending_claude_request",
        "resume_pending_claude_run",
        "candidate_pipeline_last_launch",
    ]:
        assert_contains(CANDIDATE_CONTROLS, needle)
```

- [ ] **Step 4: Run static test to verify it fails**

Run:

```bash
.venv/bin/python scripts/test_dashboard_navigation.py
```

Expected: FAIL because `ui/_candidate_controls.py` does not exist and Today Decision still owns the functions.

---

### Task 2: Runtime Helper Guard

**Files:**
- Create: `scripts/test_candidate_controls_view.py`

- [ ] **Step 1: Write failing runtime tests**

Create `scripts/test_candidate_controls_view.py`:

```python
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
```

- [ ] **Step 2: Run runtime test to verify it fails**

Run:

```bash
.venv/bin/python scripts/test_candidate_controls_view.py
```

Expected: FAIL with `ImportError: cannot import name '_candidate_controls'`.

---

### Task 3: Extract Candidate Controls Module

**Files:**
- Create: `ui/_candidate_controls.py`
- Modify: `ui/today_decision.py`

- [ ] **Step 1: Create module header and imports**

Create `ui/_candidate_controls.py` with this header:

```python
"""Today Decision local candidate refresh controls."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from . import _shared, _run_status_view as run_status_view
from scripts.candidate_pipeline_controls import (
    CandidateRunParams,
    RUN_MODE_LABELS,
    launch_background,
    read_pending_claude_request,
    refresh_claude_auth_status,
    resume_pending_claude_run,
)


_RUN_STATUS_PATH = _shared.REPORTS_DIR / "run_status" / "candidates-local.json"
_RUN_HISTORY_PATH = _shared.REPORTS_DIR / "run_status" / "candidates-local-history.jsonl"
_RANK_STAGE_ID = "rank_candidates"
```

- [ ] **Step 2: Move status reconciliation helpers exactly**

Move these functions from `ui/today_decision.py` into `ui/_candidate_controls.py`:

```python
_candidate_interrupt_reason
_interrupted_candidate_status
_write_candidate_status
_append_candidate_history
_load_candidate_status
_status_is_active
_candidate_run_history
```

Use `run_status_view.parse_utc()` inside `_render_local_refresh_status()` instead of depending on `today_decision._parse_utc`.

- [ ] **Step 3: Move display helper functions exactly**

Move these functions from `ui/today_decision.py` into `ui/_candidate_controls.py`:

```python
_history_flow
_status_zh
_scored_progress_label
_status_message_zh
_history_df
_tail_text
_render_launch_tracking
_render_claude_auth_status
_launch_candidate_run
_render_candidate_pipeline_controls
_render_local_refresh_status
```

Keep the existing Streamlit keys unchanged:

```python
candidate_rank_existing
candidate_full_refresh
candidate_llm_deep_check
candidate_pipeline_last_launch
```

- [ ] **Step 4: Add the public render entrypoint**

Add this at the bottom of `ui/_candidate_controls.py`:

```python
def render() -> None:
    _render_candidate_pipeline_controls()
    _render_claude_auth_status()
    _render_local_refresh_status()
```

- [ ] **Step 5: Wire Today Decision**

In `ui/today_decision.py`, change the imports from:

```python
import os
...
from . import _shared, _run_status_view as run_status_view
from scripts.candidate_pipeline_controls import (
    CandidateRunParams,
    RUN_MODE_LABELS,
    launch_background,
    read_pending_claude_request,
    refresh_claude_auth_status,
    resume_pending_claude_run,
)
```

to:

```python
from . import _shared, _candidate_controls
```

Keep `re`, `datetime`, `Path`, `pandas`, `streamlit`, `quote_fallback`, and `trade_state_engine` because Today Decision still uses them. Remove `json` and `timezone` if no remaining Today Decision code references them after extraction.

- [ ] **Step 6: Remove moved constants and functions from Today Decision**

Remove these constants from `ui/today_decision.py`:

```python
_RUN_STATUS_PATH
_RUN_HISTORY_PATH
_RANK_STAGE_ID
```

Remove the moved functions listed in Steps 2 and 3. Remove `_parse_utc` too if no remaining Today Decision code uses it after candidate status rendering moves to `_candidate_controls.py`.

- [ ] **Step 7: Replace render calls**

In `ui/today_decision.py`, replace:

```python
_render_candidate_pipeline_controls()
_render_claude_auth_status()
_render_local_refresh_status()
```

with:

```python
_candidate_controls.render()
```

- [ ] **Step 8: Run focused tests**

Run:

```bash
.venv/bin/python scripts/test_candidate_controls_view.py
.venv/bin/python scripts/test_dashboard_navigation.py
```

Expected:

```text
4/4 passed
36/36 passed
```

---

### Task 4: Cleanup, Verification, Commit

**Files:**
- Modify: `ui/today_decision.py`
- Modify: `ui/_candidate_controls.py`
- Test: `scripts/test_candidate_controls_view.py`
- Test: `scripts/test_dashboard_navigation.py`

- [ ] **Step 1: Check for stale imports and stale local symbols**

Run:

```bash
rg -n "CandidateRunParams|RUN_MODE_LABELS|launch_background|read_pending_claude_request|refresh_claude_auth_status|resume_pending_claude_run|_RUN_STATUS_PATH|_RUN_HISTORY_PATH|_RANK_STAGE_ID|_render_candidate_pipeline_controls|_render_local_refresh_status|_render_claude_auth_status|run_status_view|import os" ui/today_decision.py
```

Expected: no output.

- [ ] **Step 2: Run full relevant tests**

Run:

```bash
.venv/bin/python scripts/test_candidate_controls_view.py
.venv/bin/python scripts/test_dashboard_navigation.py
.venv/bin/python scripts/test_candidate_pipeline_controls.py
.venv/bin/python scripts/test_run_status_view.py
.venv/bin/python scripts/test_analytics_db_refresh_runtime.py
```

Expected:

```text
4/4 passed
36/36 passed
18/18 passed
3/3 passed
4/4 passed
```

- [ ] **Step 3: Check diff hygiene**

Run:

```bash
git diff --check
git status --short
```

Expected:

```text
git diff --check exits 0
```

`git status --short` should only show files from this task plus any pre-existing unrelated untracked files.

- [ ] **Step 4: Commit**

Run:

```bash
git add ui/_candidate_controls.py ui/today_decision.py scripts/test_candidate_controls_view.py scripts/test_dashboard_navigation.py
git commit -m "Extract today decision candidate controls"
```

---

## Self-Review

**Spec coverage:** This plan covers the full intended extraction and explicitly keeps candidate controls, Claude auth state, launch tracking, local status, and history in one module.

**Known non-goals:** This plan does not change candidate pipeline behavior, run command construction, Analytics refresh, rank scoring, or UI copy. It is a module-boundary refactor only.

**Risk areas:** Streamlit session state keys must remain unchanged. Fragment order must remain `controls → Claude auth → local refresh status`. Today Decision candidate result tables must remain in `ui/today_decision.py`.

**Verification boundary:** Static tests confirm ownership moved. Runtime tests confirm status reconciliation and labels survive the move. Existing candidate pipeline tests confirm launch command behavior is unchanged.
