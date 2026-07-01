# Options Workflow Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make 個股總覽 search feel like the single ticker refresh entry point while clearly separating 期權作戰台 as a decision cockpit and 完整期權鏈明細 as the evidence/detail page.

**Architecture:** Keep existing Streamlit pages and data providers. `ui/stock_checkup.py` owns the user-facing search workflow and load-status copy; `ui/options_cockpit.py` owns decision-summary visuals; `ui/us_options.py` owns full option-chain analysis. Static contract tests protect the information architecture, and `scripts/test_options_cockpit_display.py` protects sparse IV display behavior.

**Tech Stack:** Python 3, Streamlit, pandas, Plotly, self-contained script tests, local UI snapshot.

---

### Task 1: Protect Sparse IV Display

**Files:**
- Create: `scripts/test_options_cockpit_display.py`
- Modify: `ui/options_cockpit.py`
- Modify: `Makefile`

- [x] **Step 1: Write the failing test**

Add `scripts/test_options_cockpit_display.py` with:

```python
def test_single_iv_snapshot_uses_marker_and_accumulating_copy() -> None:
    iv_history = pd.DataFrame({"date": pd.to_datetime(["2026-07-01"]), "iv": [0.498]})
    state = oc._iv_history_display_state(
        iv_history,
        atm_iv=None,
        iv_rank_source="realized_vol_proxy",
        iv_rank_n_days=1,
        iv_rank_accumulating=True,
        is_demo=False,
    )
    assert state["trace_mode"] == "lines+markers"
    assert "快照累積中" in state["caption"]

def test_missing_iv_history_still_surfaces_current_atm_iv() -> None:
    state = oc._iv_history_display_state(
        pd.DataFrame(columns=["date", "iv"]),
        atm_iv=0.5123,
        iv_rank_source="realized_vol_proxy",
        iv_rank_n_days=0,
        iv_rank_accumulating=True,
        is_demo=False,
    )
    assert state["show_section"] is True
    assert "尚無 iv_history 快照" in state["caption"]
```

- [x] **Step 2: Verify the test fails**

Run: `.venv/bin/python scripts/test_options_cockpit_display.py`

Expected: FAIL because `_iv_history_display_state` does not exist.

- [x] **Step 3: Implement sparse IV display state**

Add `_iv_history_display_state()` in `ui/options_cockpit.py`, use `lines+markers` for one-point history, show current ATM IV when history is empty, and add copy explaining `快照累積中`.

- [x] **Step 4: Add test to Makefile and verify**

Run:

```bash
.venv/bin/python scripts/test_options_cockpit_display.py
make test
```

Expected: all tests pass.

### Task 2: Make 個股總覽 Search A Clear Refresh Workflow

**Files:**
- Modify: `scripts/test_dashboard_navigation.py`
- Modify: `ui/stock_checkup.py`

- [x] **Step 1: Write failing static UI contract**

Add `STOCK_CHECKUP = (ROOT / "ui" / "stock_checkup.py").read_text(encoding="utf-8")`.

Add:

```python
def test_stock_checkup_search_refreshes_core_trade_data_and_gates_deep_options() -> None:
    assert_contains(STOCK_CHECKUP, "def _render_trade_data_status")
    assert_contains(STOCK_CHECKUP, "搜尋後已刷新")
    assert_contains(STOCK_CHECKUP, "作戰台核心")
    assert_contains(STOCK_CHECKUP, "ATM IV")
    assert_contains(STOCK_CHECKUP, "完整期權鏈明細")
    assert_contains(STOCK_CHECKUP, "_lazy(\"options\", ticker, uo.render_for, label=\"載入完整期權鏈明細\")")
```

Run: `.venv/bin/python scripts/test_dashboard_navigation.py`

Expected: FAIL because the status helper and wording are not present.

- [x] **Step 2: Implement trade-data status strip**

In `ui/stock_checkup.py`, add `_render_trade_data_status(ticker, cockpit)` that renders a bordered status container with chips/captions:

```python
def _render_trade_data_status(ticker: str, cockpit) -> None:
    with st.container(border=True):
        st.caption(f"{ticker} 搜尋後已刷新")
        rows = [
            ("因子體檢", "已載入", _shared.GREEN),
            ("作戰台核心", "已嘗試抓取期權鏈 / ATM IV / 建議合約", _shared.GREEN if cockpit else _shared.AMBER),
            ("完整期權鏈明細", "按需載入", _shared.BLUE),
        ]
        _shared.chips_row([(f"{name}: {state}", color) for name, state, color in rows])
        st.caption("作戰台先給交易決策；完整期權鏈明細保留履約價分佈、最活躍 call、波動率結構。")
```

Call `_render_trade_data_status(ticker, cockpit)` immediately after the header.

- [x] **Step 3: Rename deep options tab and loader**

Change tab label from `③ 期權分析` to `③ 完整期權鏈明細`.

Change options lazy call to:

```python
_lazy("options", ticker, uo.render_for, label="載入完整期權鏈明細")
```

Run: `.venv/bin/python scripts/test_dashboard_navigation.py`

Expected: all static contract tests pass.

### Task 3: Separate Cockpit Summary From Full Option-Chain Detail

**Files:**
- Modify: `scripts/test_dashboard_navigation.py`
- Modify: `ui/options_cockpit.py`
- Modify: `ui/us_options.py`

- [x] **Step 1: Write failing static UI contract**

Add:

```python
def test_options_pages_split_decision_summary_from_full_chain_detail() -> None:
    assert_contains(COCKPIT, "期權鏈量分佈摘要")
    assert_contains(COCKPIT, "完整期權鏈明細")
    assert_contains(COCKPIT, "作戰台只顯示流動性與方向佐證")
    assert_contains(US_OPTIONS, "完整期權鏈明細")
    assert_contains(US_OPTIONS, "證據頁")
    assert_contains(US_OPTIONS, "最活躍 call 履約價")
```

Add `US_OPTIONS = (ROOT / "ui" / "us_options.py").read_text(encoding="utf-8")`.

Run: `.venv/bin/python scripts/test_dashboard_navigation.py`

Expected: FAIL because cockpit still uses the generic chain title and full options page is still called 期權分析.

- [x] **Step 2: Update cockpit expander copy**

In `ui/options_cockpit.py`, change:

```python
with st.expander("📊 期權鏈量分佈(依履約價)", expanded=False):
```

to:

```python
with st.expander("期權鏈量分佈摘要(作戰台)", expanded=False):
    st.caption("作戰台只顯示流動性與方向佐證；完整履約價熱圖、最活躍 call、波動率結構請看「完整期權鏈明細」。")
```

- [x] **Step 3: Update full options page copy**

In `ui/us_options.py`, change page header to `完整期權鏈明細`, add a caption describing it as the evidence page, and keep the existing chain distribution / most active call / vol surface sections.

Run: `.venv/bin/python scripts/test_dashboard_navigation.py`

Expected: all static contract tests pass.

### Task 4: Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-07-01-options-workflow-convergence.md`

- [x] **Step 1: Run focused checks**

```bash
.venv/bin/python scripts/test_options_cockpit_display.py
.venv/bin/python scripts/test_dashboard_navigation.py
.venv/bin/python -m py_compile ui/stock_checkup.py ui/options_cockpit.py ui/us_options.py scripts/test_options_cockpit_display.py scripts/test_dashboard_navigation.py
git diff --check
```

- [x] **Step 2: Run full tests**

```bash
make test
```

- [x] **Step 3: Run UI snapshot**

Start Streamlit and run:

```bash
.venv/bin/python scripts/ui_snapshot.py --page stock-checkup --port 8502 --out /private/tmp/surge-stock-checkup-options-workflow.png --width 1440 --height 1300 --settle-ms 2500
```

- [x] **Step 4: Mark checklist complete**

Update this plan checklist with completed steps and include the exact verification commands that passed.

Verification completed:

- `.venv/bin/python scripts/test_options_cockpit_display.py` -> 2/2 passed
- `.venv/bin/python scripts/test_dashboard_navigation.py` -> 31/31 passed
- `.venv/bin/python -m py_compile ui/stock_checkup.py ui/options_cockpit.py ui/us_options.py scripts/test_options_cockpit_display.py scripts/test_dashboard_navigation.py`
- `git diff --check`
- `make test`
- `.venv/bin/python scripts/ui_snapshot.py --page stock-checkup --port 8502 --out /private/tmp/surge-stock-checkup-options-workflow.png --width 1440 --height 1300 --settle-ms 2500`
