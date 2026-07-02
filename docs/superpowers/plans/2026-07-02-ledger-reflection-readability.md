# Ledger Reflection Readability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make monthly reflection useful to humans and fill performance ledger audit fields from already-produced daily report artifacts.

**Architecture:** Keep the daily decision pipeline unchanged. `scripts/06_append_ledger.py` enriches confirmed picks by reading sibling `full.json` when present, and `ui/sys_schedules.py` renders the existing reflection Markdown as a human-readable summary while preserving raw Markdown/JSON access.

**Tech Stack:** Python stdlib, Streamlit, existing script-level tests.

---

### Task 1: Ledger Enrichment From `full.json`

**Files:**
- Modify: `scripts/06_append_ledger.py`
- Test: `scripts/test_append_ledger.py`

- [ ] **Step 1: Write failing tests**

Create tests that build a temporary `summary.json` plus sibling `full.json`, call `extract_picks_from_report`, and assert the ledger row copies:

```python
assert row["regime_multiplier"] == 0.85
assert row["tech_score"] == 24
assert row["pattern_type"] == "breakout"
assert row["layer2_path"] == "BREADTH → DEPTH"
assert row["dd_short_thesis_strength"] == "MODERATE"
```

Also test that missing `full.json` leaves the current blank-field behavior intact.

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/python scripts/test_append_ledger.py`

Expected: FAIL because `scripts/06_append_ledger.py` does not yet read `full.json`.

- [ ] **Step 3: Implement minimal enrichment**

Add helpers that safely load sibling `full.json`, index `scored_data.all_scored`, `layer2_data.all_results`, and `dd_data.all_dd_results` by ticker, then overlay only currently blank audit fields.

- [ ] **Step 4: Verify GREEN**

Run: `.venv/bin/python scripts/test_append_ledger.py`

Expected: PASS.

### Task 2: Human-Readable Monthly Reflection UI

**Files:**
- Modify: `ui/sys_schedules.py`
- Test: `scripts/test_dashboard_navigation.py`

- [ ] **Step 1: Write failing static contract**

Extend the schedules-page contract to require a readable reflection parser and UI labels:

```python
assert_contains(SYS_SCHEDULES, "def _extract_llm_reflection_json")
assert_contains(SYS_SCHEDULES, "人讀摘要")
assert_contains(SYS_SCHEDULES, "資料缺口")
assert_contains(SYS_SCHEDULES, "建議行動")
assert_contains(SYS_SCHEDULES, "原始 LLM JSON")
assert_contains(SYS_SCHEDULES, "完整 Markdown 原文")
```

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/python scripts/test_dashboard_navigation.py`

Expected: FAIL because the page currently only dumps full Markdown and a download button.

- [ ] **Step 3: Implement readable rendering**

Add a JSON extractor for the `## LLM Reflection` block. In the reflection expander, render key human sections first: warning/status, narrative summary, data quality flags, and proposed actions. Keep raw JSON and Markdown behind nested expanders and keep the Markdown download button.

- [ ] **Step 4: Verify GREEN**

Run: `.venv/bin/python scripts/test_dashboard_navigation.py`

Expected: PASS.

### Task 3: Verification

**Files:**
- Check changed files and related tests only.

- [ ] Run `.venv/bin/python scripts/test_append_ledger.py`
- [ ] Run `.venv/bin/python scripts/test_dashboard_navigation.py`
- [ ] Run `.venv/bin/python scripts/test_self_reflection.py`
- [ ] Run `.venv/bin/python -m py_compile scripts/06_append_ledger.py ui/sys_schedules.py`
- [ ] Compare actual diff against this plan and fix any unexplained scope drift.
