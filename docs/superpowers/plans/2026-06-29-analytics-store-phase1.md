# Analytics Store Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small DuckDB + Parquet analytics layer for historical platform data without replacing existing JSON/CSV report flows.

**Architecture:** Keep existing reports as the write source of truth for now. Add `scripts/analytics_store.py` as an opt-in exporter/query helper that flattens selected historical artifacts into Parquet files and creates DuckDB views over those files. Local output defaults to `reports/analytics/`; deployed output can be redirected via `SURGE_ANALYTICS_DIR` or `SURGE_APP_ROOT/shared/data`.

**Tech Stack:** Python, pandas, pyarrow/Parquet, DuckDB, existing self-contained script tests.

---

### Task 1: Analytics Store Tests

**Files:**
- Create: `scripts/test_analytics_store.py`
- Later create: `scripts/analytics_store.py`

- [ ] **Step 1: Write the failing test**

Create `scripts/test_analytics_store.py` with tests for:
- exporting a sample `performance_ledger.csv` to `parquet/performance_ledger.parquet`
- exporting per-ticker `iv_history/*.json` files into `parquet/iv_history.parquet`
- querying both via DuckDB views in `analytics.duckdb`

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python scripts/test_analytics_store.py`

Expected: FAIL because `scripts/analytics_store.py` does not exist yet.

### Task 2: Analytics Store Helper

**Files:**
- Create: `scripts/analytics_store.py`
- Modify: `.gitignore`

- [ ] **Step 1: Implement path helpers**

Implement:
- `analytics_dir()`: uses `SURGE_ANALYTICS_DIR`, else `SURGE_APP_ROOT/shared/data`, else `reports/analytics`
- `parquet_dir()`
- `duckdb_path()`

- [ ] **Step 2: Implement exporters**

Implement:
- `export_performance_ledger(csv_path, analytics_root=None)`
- `export_iv_history(iv_dir, analytics_root=None)`

Both functions return metadata with row counts and output paths. They must handle missing sources by writing zero rows only when a schema can still be inferred; otherwise they return zero rows without raising.

- [ ] **Step 3: Implement DuckDB views**

Implement:
- `refresh_views(analytics_root=None)`
- `query(sql, analytics_root=None)`

Views:
- `performance_ledger`
- `iv_history`

- [ ] **Step 4: Ignore local generated analytics files**

Add `reports/analytics/` to `.gitignore`.

### Task 3: CLI And Verification

**Files:**
- Modify: `scripts/analytics_store.py`
- Test: `scripts/test_analytics_store.py`

- [ ] **Step 1: Add CLI**

CLI:
- `.venv/bin/python scripts/analytics_store.py refresh`
- `.venv/bin/python scripts/analytics_store.py query "select count(*) from performance_ledger"`

- [ ] **Step 2: Run focused tests**

Run: `.venv/bin/python scripts/test_analytics_store.py`

Expected: `analytics store tests: 3/3 passed`.

- [ ] **Step 3: Run repo checks**

Run:
- `.venv/bin/python scripts/test_deploy_artifacts.py`
- `git diff --check`

Expected: deploy artifact tests pass and no whitespace errors.

### Task 4: Test Server Installation And Connection Info

**Files:**
- Modify: `scripts/deploy_test_server.sh`
- Modify: `deploy/surge-screener.service`
- Modify: `scripts/test_deploy_artifacts.py`
- Create: `docs/analytics-store-connection.md`

- [ ] **Step 1: Write the failing deploy artifact checks**

Add assertions that the deploy script exports `SURGE_ANALYTICS_DIR`, refreshes
`scripts/analytics_store.py`, and that the systemd service exposes
`SURGE_ANALYTICS_DIR` for Streamlit-side readers.

- [ ] **Step 2: Implement deploy refresh**

Set `SURGE_ANALYTICS_DIR="$APP_ROOT/shared/data"` in the deploy script, create
`$SURGE_ANALYTICS_DIR/parquet`, and run:

```bash
"$VENV_DIR/bin/python" "$RELEASE_DIR/scripts/analytics_store.py" refresh \
  --reports-dir "$RELEASE_DIR/reports" \
  --analytics-dir "$SURGE_ANALYTICS_DIR"
```

- [ ] **Step 3: Document local-to-test-server query commands**

Create `docs/analytics-store-connection.md` explaining that DuckDB is embedded
and must be queried over SSH or copied/mounted as files, not connected to over
TCP like PostgreSQL.

- [ ] **Step 4: Verify**

Run:
- `.venv/bin/python scripts/test_deploy_artifacts.py`
- `.venv/bin/python scripts/test_analytics_store.py`
- `git diff --check`

Expected: both tests pass and no whitespace errors.

### Task 5: Out Of Scope For Phase 1

Do not migrate existing UI pages to read DuckDB yet. Do not replace JSON reports. Do not backfill all historical scan folders. Later phases can add:
- `options_flow_signals`
- `reversal_radar_signals`
- `oversold_reversal_signals`
- `market_thesis_forecasts`
- dashboard pages that query DuckDB for cross-date analytics
