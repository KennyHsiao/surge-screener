# Candidates Local Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show progress for `make candidates-local` through a single latest JSON status file that the Streamlit UI reads.

**Architecture:** Add a small `scripts/run_status.py` helper that writes `reports/run_status/candidates-local.json` atomically. `01_hard_filter.py` and `02_llm_score.py` update that file when `--status-file` is passed by the Makefile. `ui/today_decision.py` renders a read-only progress panel from the JSON.

**Tech Stack:** Python stdlib JSON/file IO, existing script-style tests, Streamlit progress rendering.

---

### Task 1: Status Writer

**Files:**
- Create: `scripts/run_status.py`
- Create: `scripts/test_run_status.py`

- [ ] Write a failing test that imports `scripts/run_status.py`, writes a running stage to a temporary JSON file, and asserts `status`, `stage`, `metrics`, and `outputs`.
- [ ] Run `.venv/bin/python scripts/test_run_status.py` and confirm it fails because `scripts/run_status.py` does not exist.
- [ ] Implement `RunStatus` with atomic JSON writes and merge-preserving stage updates.
- [ ] Run `.venv/bin/python scripts/test_run_status.py` and confirm it passes.

### Task 2: Hard Filter Progress

**Files:**
- Modify: `scripts/01_hard_filter.py`
- Modify: `scripts/test_hard_filter_yfinance.py`

- [ ] Add a failing test that calls `fetch_batch_data(..., progress_callback=callback)` and asserts each batch reports `completed_batches`, `total_batches`, and `downloaded_tickers`.
- [ ] Run `.venv/bin/python scripts/test_hard_filter_yfinance.py` and confirm it fails because `progress_callback` is not supported.
- [ ] Add `progress_callback` support to `fetch_batch_data`.
- [ ] Add `--status-file` to `01_hard_filter.py` and update `hard_filter.fetch_ohlcv`, `hard_filter.info`, `hard_filter.apply_filters`, failure, and completion states.
- [ ] Run `.venv/bin/python scripts/test_hard_filter_yfinance.py`.

### Task 3: LLM Score Progress

**Files:**
- Modify: `scripts/02_llm_score.py`
- Modify: `Makefile`
- Modify: `scripts/test_dashboard_navigation.py`

- [ ] Add static assertions that `Makefile` passes `--status-file $(CANDIDATES_STATUS)` to both scripts.
- [ ] Add `CANDIDATES_STATUS ?= reports/run_status/candidates-local.json` to `Makefile`.
- [ ] Add `--status-file` support to `02_llm_score.py` and update `llm_score.regime`, `llm_score.candidates`, and final success/failure summary.
- [ ] Run `.venv/bin/python scripts/test_dashboard_navigation.py`.

### Task 4: Today Decision UI

**Files:**
- Modify: `ui/today_decision.py`
- Modify: `scripts/test_dashboard_navigation.py`

- [ ] Add static assertions that `ui/today_decision.py` reads `reports/run_status/candidates-local.json`, defines `_render_local_refresh_status`, and uses `st.progress`.
- [ ] Implement a compact read-only status panel near the top of 今日決策.
- [ ] Run `.venv/bin/python scripts/test_dashboard_navigation.py`.

### Task 5: Verification

**Files:**
- Modify: `Makefile`

- [ ] Add `scripts/test_run_status.py` to `make test`.
- [ ] Run `.venv/bin/python scripts/test_run_status.py`.
- [ ] Run `.venv/bin/python scripts/test_hard_filter_yfinance.py`.
- [ ] Run `.venv/bin/python scripts/test_dashboard_navigation.py`.
- [ ] Run `make test`.
