# Data Health Refresh UX V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Data Health refresh center understandable and recoverable for long-running source refreshes.

**Architecture:** Reuse `scripts/run_status.py` for a Data Health status JSON. `scripts/data_source_refresh.py` will write staged progress before and after source refresh, Analytics DB rebuild, and checks. `ui/analytics_db.py` will show clear task cost, latest status, progress, and disable heavy refresh while a current run is active.

**Tech Stack:** Python, Streamlit, existing JSON run-status writer, self-contained script tests.

---

### Task 1: RunStatus Custom Stages

**Files:**
- Modify: `scripts/run_status.py`
- Modify: `scripts/test_run_status.py`

- [x] **Step 1: Write failing test**

Add a test that constructs `RunStatus(path, job="data-health-refresh", stages=[("source", "刷新資料源"), ("done", "完成")])`, calls `start()`, and asserts the written `stages` contain exactly those custom labels instead of the default candidate pipeline stages.

- [x] **Step 2: Run RED**

Run: `.venv/bin/python scripts/test_run_status.py`

- [x] **Step 3: Implement custom stages**

Add optional `stages` to `RunStatus.__init__`; use it in `start()` and `_base()` with default fallback to `DEFAULT_STAGES`.

- [x] **Step 4: Run GREEN**

Run: `.venv/bin/python scripts/test_run_status.py`

### Task 2: Data Source Refresh Status

**Files:**
- Modify: `scripts/data_source_refresh.py`
- Modify: `scripts/test_data_source_refresh.py`

- [x] **Step 1: Write failing test**

Add a test that calls `refresh_core_sources_and_analytics(..., status_file=path)` with fakes and asserts:
- status file exists
- `job == "data-health-refresh"`
- terminal status is `succeeded`
- stages include `source_refresh`, `analytics_store`, `analytics_checks`
- metrics include ticker count and checks status

- [x] **Step 2: Run RED**

Run: `.venv/bin/python scripts/test_data_source_refresh.py`

- [x] **Step 3: Implement status writing**

Add:
- `DATA_HEALTH_STAGES`
- `default_status_path(reports_root)`
- optional `status_file` arg
- `_progress_writer(status_file)` helper
- stage updates before/after source refresh, Analytics DB rebuild, and checks
- terminal success/failure status

- [x] **Step 4: Run GREEN**

Run: `.venv/bin/python scripts/test_data_source_refresh.py`

### Task 3: Analytics DB UI Refresh Center UX

**Files:**
- Modify: `ui/analytics_db.py`
- Modify: `scripts/test_dashboard_navigation.py`

- [x] **Step 1: Write failing UI string test**

Assert the page contains:
- `完整刷新核心資料源（約 10-25 分鐘）`
- `只重建 Analytics DB + 檢查`
- `最近一次資料刷新`
- `stage.progress_pct`
- `data-health-refresh.json`
- `約 250 檔`

- [x] **Step 2: Run RED**

Run: `.venv/bin/python scripts/test_dashboard_navigation.py`

- [x] **Step 3: Implement UI**

Update refresh center:
- rename heavy button
- explain heavy vs quick task cost
- pass status file to `_refresh_core_sources`
- render latest Data Health status file
- show progress bar when running
- disable heavy button when non-stale running status exists
- show completion impact from `today_signal_readiness` and checks metrics when available

- [x] **Step 4: Run GREEN**

### Task 3b: Schedules Reflection Result UX

**Files:**
- Modify: `ui/sys_schedules.py`
- Modify: `scripts/test_dashboard_navigation.py`

- [x] Add a readable full Markdown expander for monthly reflection results.
- [x] Add a Markdown download button so the result is not trapped in a short preview.
- [x] Cover the entry points with the dashboard navigation contract test.

### Task 3c: Local Refresh Artifact Hygiene

**Files:**
- Modify: `.gitignore`
- Modify: `scripts/test_dashboard_navigation.py`

- [x] Ignore local `reports/theme_flow_snapshots/` archive output so refresh actions do not dirty git state.
- [x] Cover the ignore rule with the dashboard navigation contract test.

Run: `.venv/bin/python scripts/test_dashboard_navigation.py`

### Task 4: Final Verification

**Files:**
- Validate all touched files.

- [x] Run:

```bash
.venv/bin/python scripts/test_run_status.py
.venv/bin/python scripts/test_data_source_refresh.py
.venv/bin/python scripts/test_dashboard_navigation.py
.venv/bin/python -m py_compile scripts/run_status.py scripts/data_source_refresh.py ui/analytics_db.py scripts/test_run_status.py scripts/test_data_source_refresh.py scripts/test_dashboard_navigation.py
git diff --check
```

- [x] Confirm scope does not change provider behavior, DB schema, or candidate generation.
