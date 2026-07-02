# Refresh Data Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the data gaps that can be solved automatically after local candidate refresh, and make candidate refresh status represent the full wrapper lifecycle.

**Architecture:** Keep the existing artifact-first flow. Add fallback source rows when Eastmoney market list is empty, add ticker-level Eastmoney secid resolution for money flow, let candidate pipeline own the final status after analytics refresh, and ensure suggested role assignments can surface as role tags. Do not fake IBKR positions or performance outcomes.

**Tech Stack:** Python scripts, JSON artifacts under `reports/`, DuckDB/Parquet analytics store, Streamlit status readers, self-contained script tests.

---

### Task 1: Candidate Pipeline Final Status

**Files:**
- Modify: `scripts/run_candidate_pipeline.py`
- Test: `scripts/test_candidate_pipeline_controls.py`

- [ ] Add a failing test that wrapper marks `analytics_refresh` running after child scorer completes and only writes final `succeeded` after analytics refresh.
- [ ] Run `.venv/bin/python scripts/test_candidate_pipeline_controls.py` and verify the test fails.
- [ ] Update `run_candidate_pipeline.main()` to create a `RunStatus` for `args.status_file`, update `analytics_refresh` before `refresh_analytics_after_run()`, and call `succeed()` only after analytics checks finish.
- [ ] Run the test again and verify it passes.

### Task 2: Universe Fallback Rows

**Files:**
- Modify: `scripts/universe_refresh.py`
- Test: `scripts/test_universe_refresh.py`

- [ ] Add a failing test where Eastmoney market lists are empty but fallback platform tickers and SEC CIK map produce non-empty `securities`.
- [ ] Run `.venv/bin/python scripts/test_universe_refresh.py` and verify the test fails.
- [ ] Add fallback ticker collection from recent candidate rankings/ranked candidates/watchlist/theme baskets and SEC CIK map, with source metadata showing fallback.
- [ ] Run the test again and verify it passes.

### Task 3: Money Flow Secid Fallback

**Files:**
- Modify: `scripts/eastmoney_money_flow.py`
- Test: `scripts/test_eastmoney_money_flow.py`

- [ ] Add a failing test where `secid_map` is empty but Eastmoney search resolves `AAPL -> 105.AAPL` and money flow writes rows.
- [ ] Run `.venv/bin/python scripts/test_eastmoney_money_flow.py` and verify the test fails.
- [ ] Add optional search-based secid resolver with cache per build, used only for missing secids.
- [ ] Run the test again and verify it passes.

### Task 4: Role Tags For Current Tickers

**Files:**
- Modify: `scripts/industry_roles.py` and/or `scripts/trade_state.py`
- Test: `scripts/test_trade_state.py` / `scripts/test_trade_state_snapshots.py`

- [ ] Add a failing test proving suggested assignments are usable as role tags for trade state, not only approved overrides.
- [ ] Run the focused test and verify failure.
- [ ] Ensure role assignment snapshot and trade state resolution consume suggested assignments for display while preserving status as suggested.
- [ ] Run focused tests.

### Task 5: Verification And Deploy

**Files:** all modified files.

- [ ] Run focused tests: `test_universe_refresh`, `test_eastmoney_money_flow`, `test_candidate_pipeline_controls`, `test_data_source_refresh`, `test_analytics_store`, `test_analytics_checks`.
- [ ] Run `py_compile` on modified scripts.
- [ ] Run `git diff --check`.
- [ ] Review diff against this plan.
- [ ] Commit and push only relevant files.
- [ ] Verify test server checks after deploy.
