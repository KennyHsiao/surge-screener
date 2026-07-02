# Today Signal Readiness Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split Analytics DB health from the Today Signal publishing gate so review-only data-source gaps cannot incorrectly pause today's signal.

**Architecture:** `scripts/analytics_checks.py` will publish a dedicated `today_signal_readiness` object. Table health checks will classify only core signal prerequisites as blocking; optional evidence tables stay review-only. `ui/analytics_db.py` will render Today Signal readiness separately from the broader data-health summary.

**Tech Stack:** Python scripts, DuckDB read model via `scripts/analytics_store.py`, self-contained script tests, Streamlit UI string-contract tests.

---

### Task 1: Add Readiness Contract Tests

**Files:**
- Modify: `scripts/test_analytics_checks.py`

- [ ] **Step 1: Write failing tests**

Add tests that assert:

```python
def test_today_signal_readiness_allows_review_only_data_gaps() -> None:
    store = _load_store()
    checks = _load_checks()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        analytics_root = tmp / "analytics"
        out = tmp / "checks" / "latest.json"
        _write_reports(reports)
        shutil.rmtree(reports / "universe")
        shutil.rmtree(reports / "market_data")
        shutil.rmtree(reports / "money_flow")
        store.refresh_all(reports_root=reports, analytics_root=analytics_root)

        result = checks.run_checks(
            analytics_root=analytics_root,
            output_path=out,
            today="2026-06-03",
        )
        readiness = result["today_signal_readiness"]

        if readiness["can_publish"] is not True:
            raise AssertionError(readiness)
        if readiness["status"] != "WARN":
            raise AssertionError(readiness)
        if readiness["recommended_action"] != "REVIEW_REQUIRED":
            raise AssertionError(readiness)
        if any(item.get("action") == "BLOCK_TODAY_SIGNALS" for item in result["next_actions"]):
            raise AssertionError(result["next_actions"])
```

Add a second test:

```python
def test_today_signal_readiness_blocks_when_core_rankings_are_empty() -> None:
    store = _load_store()
    checks = _load_checks()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        analytics_root = tmp / "analytics"
        out = tmp / "checks" / "latest.json"
        _write_reports(reports)
        shutil.rmtree(reports / "candidate_rankings")
        store.refresh_all(reports_root=reports, analytics_root=analytics_root)

        result = checks.run_checks(
            analytics_root=analytics_root,
            output_path=out,
            today="2026-06-03",
        )
        readiness = result["today_signal_readiness"]

        if readiness["can_publish"] is not False:
            raise AssertionError(readiness)
        if readiness["status"] != "BLOCK":
            raise AssertionError(readiness)
        if readiness["recommended_action"] != "BLOCK_TODAY_SIGNALS":
            raise AssertionError(readiness)
        if "table:candidate_rankings:row_count" not in readiness["blocking_check_ids"]:
            raise AssertionError(readiness)
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
.venv/bin/python scripts/test_analytics_checks.py
```

Expected: the new tests fail because `today_signal_readiness` does not exist yet and candidate rankings are currently treated as maturity-only.

### Task 2: Implement Analytics Readiness Contract

**Files:**
- Modify: `scripts/analytics_checks.py`

- [ ] **Step 1: Define core tables**

Add:

```python
TODAY_SIGNAL_CORE_TABLES = {"candidate_rankings"}
```

- [ ] **Step 2: Make table health use the core-table policy**

In `_table_health_checks()`, missing or empty tables should block only when the table is in `TODAY_SIGNAL_CORE_TABLES`. Other tables should produce `WARN` + `REVIEW_REQUIRED`.

- [ ] **Step 3: Add readiness builder**

Add a helper that returns:

```python
{
    "can_publish": bool,
    "status": "PASS" | "WARN" | "BLOCK",
    "recommended_action": "NO_ACTION" | "REVIEW_REQUIRED" | "BLOCK_TODAY_SIGNALS",
    "message": str,
    "blocking_check_ids": list[str],
    "warning_check_ids": list[str],
}
```

Core blocker sources:
- `db:exists`
- `db:readable`
- any `table:{core}:exists`
- any `table:{core}:row_count`

Warnings are non-PASS checks that are not core blockers.

- [ ] **Step 4: Include readiness in result and next actions**

`run_checks()` must add `today_signal_readiness` to the published JSON. `_next_actions()` must add `BLOCK_TODAY_SIGNALS` only when readiness says `can_publish == False`.

- [ ] **Step 5: Run tests to verify GREEN**

Run:

```bash
.venv/bin/python scripts/test_analytics_checks.py
```

Expected: all tests pass.

### Task 3: Update Analytics UI Copy and Layout

**Files:**
- Modify: `ui/analytics_db.py`
- Modify: `scripts/test_dashboard_navigation.py`

- [ ] **Step 1: Add UI string-contract test**

Assert the UI contains:

```python
assert_contains(ANALYTICS_DB, "today_signal_readiness")
assert_contains(ANALYTICS_DB, "今日訊號發布狀態")
assert_contains(ANALYTICS_DB, "資料健康摘要")
assert_contains(ANALYTICS_DB, "可發布，需檢查")
assert_contains(ANALYTICS_DB, "核心候選排序")
```

- [ ] **Step 2: Run UI test to verify RED**

Run:

```bash
.venv/bin/python scripts/test_dashboard_navigation.py
```

Expected: UI test fails until the copy/layout exists.

- [ ] **Step 3: Render readiness separately**

Update `_health_summary()` so it accepts readiness and displays:
- Subheader: `今日訊號發布狀態`
- Status copy based on `today_signal_readiness`
- A separate subheader/container for `資料健康摘要`

Change the `BLOCK` status label from `今日訊號暫停使用` to `資料健康阻擋`.

- [ ] **Step 4: Run UI test to verify GREEN**

Run:

```bash
.venv/bin/python scripts/test_dashboard_navigation.py
```

Expected: all tests pass.

### Task 4: Final Verification

**Files:**
- Validate all touched files.

- [ ] **Step 1: Run focused checks**

Run:

```bash
.venv/bin/python scripts/test_analytics_checks.py
.venv/bin/python scripts/test_dashboard_navigation.py
.venv/bin/python -m py_compile scripts/analytics_checks.py scripts/test_analytics_checks.py ui/analytics_db.py scripts/test_dashboard_navigation.py
git diff --check
```

- [ ] **Step 2: Compare diff against plan**

Confirm only:
- analytics readiness contract
- related tests
- Analytics DB UI copy/layout

No data-fetching or DB migration code should be changed.

- [ ] **Step 3: Report result**

Explain that Analytics DB can still show data-health warnings, but Today Signal only pauses when core prerequisites fail.
