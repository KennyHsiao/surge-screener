# Trade State UI Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten the 交易狀態 page so the status table, single-ticker detail, and Story output read like a professional trader workflow instead of raw Streamlit data dumps.

**Architecture:** Keep `scripts/trade_state.py` as the data/text assembly layer and `ui/trade_state.py` as the rendering layer. Add small, testable helpers for Chinese labels, data-quality tags, story template filtering, and detail layout text; avoid touching unrelated analytics workflow changes currently present in the worktree.

**Tech Stack:** Python 3, Streamlit, pandas, self-contained script tests, local UI snapshot verification.

---

### Task 1: Story Copy Semantics And Templates

**Files:**
- Modify: `scripts/test_trade_state.py`
- Modify: `scripts/trade_state.py`

- [x] **Step 1: Write failing tests**

Add tests proving `story_copy()` emits Chinese-facing labels and supports story templates:

```python
def test_story_copy_uses_trader_chinese_labels_and_role_column():
    story = ts.story_copy([{
        "ticker": "FORM",
        "theme": "CoWoS / 先進封裝",
        "industry_role": "待審核: Advanced Packaging / OSAT",
        "mentions": 0,
        "atr_pct": None,
        "cycle": "Cycle1",
        "ce_trend": "bullish",
        "ce_source": "trend_proxy",
        "signal": "holding",
    }])
    assert "| Ticker | 主題 | 產業鏈角色 | 提及 | ATR% | Cycle | 趨勢來源 | 訊號 |" in story
    assert "| FORM | CoWoS / 先進封裝 | 待審核: Advanced Packaging / OSAT | 0 | - | Cycle1 | 偏多 / Proxy | 持有 |" in story
    assert "bullish / proxy" not in story
    assert "holding" not in story
```

Add a second test for template filtering:

```python
def test_story_copy_supports_ai_infra_template_filter():
    rows = [
        {"ticker": "FORM", "theme": "CoWoS / 先進封裝", "industry_role": "Advanced Packaging / OSAT", "mentions": 0, "atr_pct": None, "cycle": "Cycle1", "ce_trend": "bullish", "ce_source": "trend_proxy", "signal": "holding"},
        {"ticker": "BALL", "theme": "未分類", "industry_role": "未分類", "mentions": 0, "atr_pct": None, "cycle": "Cycle1", "ce_trend": "bullish", "ce_source": "trend_proxy", "signal": "holding"},
    ]
    story = ts.story_copy(rows, template="ai_infra")
    assert "AI infra" in story
    assert "| FORM |" in story
    assert "| BALL |" not in story
```

- [x] **Step 2: Verify tests fail**

Run: `.venv/bin/python scripts/test_trade_state.py`

Expected: failures because story output currently has no role column, no Chinese labels, and no template filtering.

- [x] **Step 3: Implement minimal story helpers**

Add `story_rows(rows, template="all")`, `_signal_zh()`, `_ce_zh()`, and template keyword filtering inside `scripts/trade_state.py`. Keep default behavior backwards-compatible except for improved labels and role column.

- [x] **Step 4: Verify tests pass**

Run: `.venv/bin/python scripts/test_trade_state.py`

Expected: all trade-state tests pass.

### Task 2: Trade State Table Review Tightening

**Files:**
- Modify: `scripts/test_trade_state.py`
- Modify: `scripts/trade_state.py`
- Modify: `scripts/test_dashboard_navigation.py`
- Modify: `ui/trade_state.py`

- [x] **Step 1: Write failing tests**

Add tests that every row exposes data-quality tags:

```python
def test_build_rows_marks_proxy_and_missing_atr_data_quality():
    rows = ts.build_trade_state_rows(...)
    assert "Proxy 訊號" in rows[0]["data_quality"]
    assert "缺 ATR%" in rows[0]["data_quality"]
```

Add static UI assertions that the table/detail render data quality:

```python
assert_contains(TRADE_STATE, '"資料狀態"')
assert_contains(TRADE_STATE, "_quality_color")
assert_contains(TRADE_STATE, "_render_detail_header")
```

- [x] **Step 2: Verify tests fail**

Run:

```bash
.venv/bin/python scripts/test_trade_state.py
.venv/bin/python scripts/test_dashboard_navigation.py
```

Expected: failures because `data_quality` and detail header helpers do not exist yet.

- [x] **Step 3: Implement data-quality row fields and UI columns**

In `scripts/trade_state.py`, add `data_quality` list and `data_quality_label` string per row:

- `Proxy 訊號` when `ce_source == "trend_proxy"`
- `缺 ATR%` when `atr_pct is None`
- `未分類` when `industry_role_status == "unclassified"`

In `ui/trade_state.py`, add a compact `資料狀態` column and use `_quality_color()` chips near the signal/detail area.

- [x] **Step 4: Verify tests pass**

Run the two targeted tests again.

### Task 3: Single-Ticker Detail Layout

**Files:**
- Modify: `ui/trade_state.py`
- Modify: `scripts/test_dashboard_navigation.py`

- [x] **Step 1: Write failing static test**

Assert the detail view uses dedicated helpers and no longer puts the long industry role inside the narrow left column:

```python
assert_contains(TRADE_STATE, "def _render_detail_header")
assert_contains(TRADE_STATE, "def _render_compact_facts")
assert_contains(TRADE_STATE, "分類tag")
assert_not_contains(TRADE_STATE, "top = st.columns([1, 2, 2, 2])")
```

- [x] **Step 2: Verify static test fails**

Run: `.venv/bin/python scripts/test_dashboard_navigation.py`

Expected: failure because the helper functions do not exist and the old narrow-column layout is still present.

- [x] **Step 3: Implement compact detail layout**

Refactor `_render_detail()` to:

- render a full-width header row with ticker, theme, role, role status, and data-quality chips
- render three decision columns for Cycle, CE/Proxy, and Signal
- render compact facts in a dense table-like row instead of five large metric cards

- [x] **Step 4: Verify static test passes**

Run: `.venv/bin/python scripts/test_dashboard_navigation.py`

Expected: all navigation/UI contract tests pass.

### Task 4: Story UI Preview And Copy Area

**Files:**
- Modify: `ui/trade_state.py`
- Modify: `scripts/test_dashboard_navigation.py`

- [x] **Step 1: Write failing static test**

Assert Story tab has a template selector and separates preview from copy text:

```python
assert_contains(TRADE_STATE, "story_template = st.selectbox")
assert_contains(TRADE_STATE, "_story_preview_df")
assert_contains(TRADE_STATE, "複製文字")
assert_contains(TRADE_STATE, "預覽")
```

- [x] **Step 2: Verify static test fails**

Run: `.venv/bin/python scripts/test_dashboard_navigation.py`

Expected: failure because the current Story tab only renders a textarea.

- [x] **Step 3: Implement Story tab controls**

Add template options:

- `全部`
- `半導體 / AI infra`
- `機器人 / Physical AI`
- `Space`
- `自訂主題`

Render a dataframe preview from `engine.story_rows()` and a separate text area from `engine.story_copy()`.

- [x] **Step 4: Verify**

Run targeted tests, `py_compile`, `make test`, and UI snapshots for `trade-state`.

Verification completed:

- `.venv/bin/python -m py_compile scripts/trade_state.py scripts/test_trade_state.py ui/trade_state.py scripts/test_dashboard_navigation.py`
- `.venv/bin/python scripts/test_trade_state.py` -> 13/13 passed
- `.venv/bin/python scripts/test_dashboard_navigation.py` -> 29/29 passed
- `make test` -> all configured script tests passed
- `.venv/bin/python scripts/ui_snapshot.py --page trade-state --port 8502 --out /private/tmp/surge-trade-state-converged-final.png --width 1440 --height 1100 --settle-ms 2000`
