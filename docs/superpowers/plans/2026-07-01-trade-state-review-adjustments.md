# Trade State Review Adjustments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten the 交易狀態 page so CE/Proxy and Cycle signals do not overstate precision or misclassify bullish continuation setups.

**Architecture:** Keep the Streamlit page as a thin renderer and put trading semantics in `scripts/trade_state.py`. Add focused tests in `scripts/test_trade_state.py` before changing the logic. UI text should expose whether the row is real Chandelier Exit or a proxy.

**Tech Stack:** Python 3, Streamlit, pandas, self-contained script tests.

---

### Task 1: CE Semantics

**Files:**
- Modify: `scripts/test_trade_state.py`
- Modify: `scripts/trade_state.py`

- [ ] **Step 1: Write failing tests**

Add tests proving exact CE does not mark a price below the long stop as bullish, and proving builder uses exact CE when high/low fields exist:

```python
def test_ce_trend_exact_does_not_call_below_long_stop_bullish():
    ce = ts.compute_ce_trend(price=115.0, atr=4.0, highest_high=130.0, lowest_low=100.0)
    assert ce["long_stop"] == 118.0
    assert ce["short_stop"] == 112.0
    assert ce["trend"] == "neutral", ce
    assert ce["stop"] == 118.0


def test_build_rows_uses_chandelier_inputs_when_available():
    with TemporaryDirectory() as td:
        root = Path(td)
        reports = root / "reports"
        content = root / "content"
        reports.mkdir()
        content.mkdir()
        candidate_path = root / "ranked_candidates.json"
        candidate_path.write_text(json.dumps({
            "tickers": [{
                "ticker": "CEOK",
                "last_price": 125.0,
                "ma50": 100.0,
                "ma200": 90.0,
                "atr14": 4.0,
                "highest_high_22d": 130.0,
                "lowest_low_22d": 100.0,
                "macd_current": 1.2,
            }]
        }), encoding="utf-8")

        rows = ts.build_trade_state_rows(
            reports_dir=reports,
            content_dir=content,
            candidate_path=candidate_path,
            limit=10,
        )
    assert rows[0]["ce_source"] == "chandelier", rows
    assert rows[0]["ce_stop"] == 118.0, rows
```

- [ ] **Step 2: Verify tests fail**

Run: `.venv/bin/python scripts/test_trade_state.py`

Expected: new CE tests fail against current implementation.

- [ ] **Step 3: Implement CE fix**

Update `compute_ce_trend()` so exact CE returns:
- bullish only when price is above both exact stop references.
- bearish only when price is below both exact stop references.
- neutral when price sits between long and short references.

Add helper lookup for possible high/low keys and pass them from `build_trade_state_rows()`:

```python
highest_high = _first_num(tech, row, "highest_high_22d", "high_22d", "resistance_20d")
lowest_low = _first_num(tech, row, "lowest_low_22d", "low_22d", "support_20d")
```

- [ ] **Step 4: Verify tests pass**

Run: `.venv/bin/python scripts/test_trade_state.py`

Expected: all trade-state tests pass.

### Task 2: Cycle Boundary

**Files:**
- Modify: `scripts/test_trade_state.py`
- Modify: `scripts/trade_state.py`

- [ ] **Step 1: Write failing test**

Add a test proving an above-MA, MACD-positive zero-cross setup remains Cycle1:

```python
def test_cycle1_wins_when_breakout_is_above_mas_and_macd_positive():
    cycle = ts.classify_cycle({
        "last_price": 120.0,
        "ma50": 100.0,
        "ma200": 90.0,
        "macd_current": 0.2,
        "macd_zero_cross_10d": True,
    })
    assert cycle["cycle"] == "Cycle1", cycle
```

- [ ] **Step 2: Verify test fails**

Run: `.venv/bin/python scripts/test_trade_state.py`

Expected: the new Cycle test fails because Cycle5 currently precedes Cycle1.

- [ ] **Step 3: Implement Cycle fix**

Move the Cycle1 continuation check before Cycle5, and make Cycle5 require unresolved recovery conditions such as price below MA50 or MACD not yet positive.

- [ ] **Step 4: Verify tests pass**

Run: `.venv/bin/python scripts/test_trade_state.py`

Expected: all trade-state tests pass.

### Task 3: UI Labels And Story Output

**Files:**
- Modify: `scripts/test_trade_state.py`
- Modify: `scripts/trade_state.py`
- Modify: `ui/trade_state.py`
- Modify: `ui/today_decision.py`

- [ ] **Step 1: Write failing story test**

Add a test proving story output is a Markdown table and exposes proxy state:

```python
def test_story_copy_uses_markdown_table_and_source_label():
    story = ts.story_copy([{
        "ticker": "MU",
        "theme": "MEMORY",
        "mentions": 2,
        "atr_pct": 8.15,
        "cycle": "Cycle1",
        "ce_trend": "bullish",
        "ce_source": "trend_proxy",
        "signal": "holding",
    }])
    assert "| Ticker | 主題 | 提及 | ATR% | Cycle | 趨勢來源 | 訊號 |" in story
    assert "| MU | MEMORY | 2 | 8.2 | Cycle1 | bullish / proxy | holding |" in story
```

- [ ] **Step 2: Verify test fails**

Run: `.venv/bin/python scripts/test_trade_state.py`

Expected: story test fails because output is fixed-width text.

- [ ] **Step 3: Implement label changes**

Change UI labels from ambiguous `CE` to `CE/Proxy` where rows can be proxy. Keep exact rows labeled `CE`, and proxy rows labeled `Proxy`.

- [ ] **Step 4: Verify targeted and navigation tests pass**

Run:

```bash
.venv/bin/python scripts/test_trade_state.py
.venv/bin/python scripts/test_dashboard_navigation.py
```

Expected: both pass.

### Task 4: Upstream CE Inputs

**Files:**
- Modify: `scripts/test_momentum_options.py`
- Modify: `scripts/momentum_options.py`
- Modify: `scripts/test_hard_filter_yfinance.py`
- Modify: `scripts/01_hard_filter.py`
- Modify: `scripts/risk_guard.py`
- Modify: `Makefile` if a new risk guard test is added.

- [ ] **Step 1: Write failing source tests**

Add a test proving `_technical()` emits `highest_high_22d`, `lowest_low_22d`, and `support_20d`.

- [ ] **Step 2: Verify source test fails**

Run: `.venv/bin/python scripts/test_momentum_options.py`

Expected: the new source test fails because the fields are missing.

- [ ] **Step 3: Implement source fields**

Compute ATR/high/low fields from the same underlying OHLCV windows used by existing technical analysis. Preserve them through hard-filter candidates and risk guard technical summary so newly generated artifacts can feed exact CE.

- [ ] **Step 4: Verify source tests pass**

Run: `.venv/bin/python scripts/test_momentum_options.py`

Expected: all momentum-options tests pass.

### Task 5: Regression

**Files:**
- Verify only.

- [ ] **Step 1: Run full relevant checks**

Run:

```bash
make test
.venv/bin/python -m py_compile scripts/trade_state.py scripts/test_trade_state.py ui/trade_state.py ui/today_decision.py app.py
```

Expected: all checks pass.
