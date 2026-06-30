# Trade State Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated `交易狀態` page that combines social attention, Notion-derived Cycle phase, CE trend, ATR%, risk state, options-flow context, and a story-copy preview.

**Architecture:** Keep trade-state calculation in a testable script module and keep Streamlit rendering in a thin UI page. The first version reads existing local artifacts only; it does not install Notion MCP and does not require live network calls. `Cycle` is a local rule mapping based on the Notion course notes, while `CE` is a Chandelier Exit calculation when high/low/ATR inputs are available and a clearly labeled trend proxy otherwise.

**Tech Stack:** Python, Streamlit, pandas, existing `ui/_shared.py` loaders, JSON artifacts under `reports/`, static test scripts in `scripts/test_*.py`.

---

### Task 1: Trade-State Logic Tests

**Files:**
- Create: `scripts/test_trade_state.py`
- Create later: `scripts/trade_state.py`

- [ ] **Step 1: Write the failing tests**

Create `scripts/test_trade_state.py` with tests for:
- exact Chandelier Exit CE trend classification
- fallback CE proxy classification when high/low history is unavailable
- Cycle mapping from ranked-candidate style rows
- signal mapping for `holding`, `take_profit`, and `stop_loss`
- building rows when `x_influencer_picks.json` is missing

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python scripts/test_trade_state.py`

Expected: FAIL because `scripts/trade_state.py` does not exist yet.

### Task 2: Trade-State Data Builder

**Files:**
- Create: `scripts/trade_state.py`
- Test: `scripts/test_trade_state.py`

- [ ] **Step 1: Implement minimal data builder**

Implement:
- `compute_ce_trend(...)`
- `classify_cycle(row)`
- `map_trade_signal(row)`
- `theme_for_ticker(ticker, baskets)`
- `build_trade_state_rows(...)`
- `story_copy(rows, title=...)`

Rules:
- `Cycle1`: price above MA50/MA200 with positive MACD or strong MA stack.
- `Cycle4`: price below MA50 with weak/negative MACD or risk `REDUCE/EXIT`.
- `Cycle5`: recent MACD golden/zero cross while MACD is still near/below zero, interpreted as reversal test.
- `Cycle2/3`: transitional state when trend evidence is mixed.
- CE exact mode uses Chandelier Exit values from highest high, lowest low, and ATR.
- CE proxy mode is labeled `trend_proxy` and uses price vs MA50/VWAP evidence.

- [ ] **Step 2: Run test to verify it passes**

Run: `.venv/bin/python scripts/test_trade_state.py`

Expected: all tests pass.

### Task 3: Streamlit Trade State Page

**Files:**
- Create: `ui/trade_state.py`
- Modify: `app.py`
- Test: `scripts/test_dashboard_navigation.py`

- [ ] **Step 1: Add failing navigation contract**

Update `scripts/test_dashboard_navigation.py` to assert:
- `trade_state.render` is imported and registered in the `今日決策` group
- page title is `交易狀態`
- url path is `trade-state`
- order is after `today_decision.render` and before `us_screener.render`

- [ ] **Step 2: Run navigation test to verify it fails**

Run: `.venv/bin/python scripts/test_dashboard_navigation.py`

Expected: FAIL because `trade_state` is not registered.

- [ ] **Step 3: Implement page and navigation**

Add `ui/trade_state.py` with:
- top summary metrics
- filters for signal, Cycle, CE trend, and theme
- dense data table
- ticker detail panel
- story-copy preview

Update `app.py` to import and register the page under `今日決策`.

- [ ] **Step 4: Run navigation test to verify it passes**

Run: `.venv/bin/python scripts/test_dashboard_navigation.py`

Expected: PASS.

### Task 4: Today Decision Entry Point

**Files:**
- Modify: `ui/today_decision.py`
- Test: `scripts/test_dashboard_navigation.py`

- [ ] **Step 1: Add failing static assertions**

Extend `scripts/test_dashboard_navigation.py` to assert `today_decision.py` includes a trade-state summary helper and same-session jump to `trade-state`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python scripts/test_dashboard_navigation.py`

Expected: FAIL until the summary entry point exists.

- [ ] **Step 3: Add compact summary card**

Add a compact `交易狀態` card to `今日決策`, using `scripts.trade_state.build_trade_state_rows(limit=50)` and `_shared.switch_page("trade-state")`.

- [ ] **Step 4: Run tests**

Run:
- `.venv/bin/python scripts/test_dashboard_navigation.py`
- `.venv/bin/python scripts/test_trade_state.py`

Expected: PASS.

### Task 5: Final Verification

**Files:**
- All changed files

- [ ] **Step 1: Run focused tests**

Run:
- `.venv/bin/python scripts/test_trade_state.py`
- `.venv/bin/python scripts/test_dashboard_navigation.py`

Expected: PASS.

- [ ] **Step 2: Run import smoke check**

Run: `.venv/bin/python - <<'PY'
from scripts.trade_state import build_trade_state_rows
from ui import trade_state
rows = build_trade_state_rows(limit=5)
print(len(rows), hasattr(trade_state, "render"))
PY`

Expected: command exits 0 and prints a row count plus `True`.

- [ ] **Step 3: Start Streamlit**

Run: `.venv/bin/python -m streamlit run app.py --server.port 8501 --server.headless true --browser.gatherUsageStats false`

Expected: server starts and exposes `http://localhost:8501`.

---

### Plan Self-Review

- Spec coverage: covers new page, navigation placement, Today Decision summary, data logic, Story preview, and no Notion MCP installation.
- Placeholder scan: no TBD/TODO placeholders.
- Risk areas: CE exact calculation requires high/low/ATR inputs; when unavailable the UI must clearly label `trend_proxy`. Social mentions may be missing; page must degrade gracefully.
