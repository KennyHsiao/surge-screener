# Industry Role Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a platform-operated industry-chain role review workflow and surface approved roles in 交易狀態.

**Architecture:** Put role taxonomy, suggestions, approvals, and review actions in `scripts/industry_roles.py`. Keep Streamlit as a thin review UI in `ui/industry_roles.py`. `scripts/trade_state.py` reads approved/suggested role labels as an overlay; suggested roles are explicitly marked `待審核`.

**Tech Stack:** Python 3, Streamlit, pandas, local JSON artifacts, self-contained script tests.

---

### Task 1: Role Engine Data Model

**Files:**
- Create: `content/industry_roles.json`
- Create: `scripts/test_industry_roles.py`
- Create: `scripts/industry_roles.py`

- [ ] **Step 1: Write failing tests**

Add tests for taxonomy loading, theme-basket suggestions, and approved override precedence:

```python
def test_suggest_roles_from_theme_baskets():
    taxonomy = {"roles": {"ai_server_odm": {"name": "AI Server / ODM", "theme_baskets": ["AI 伺服器 / ODM"]}}}
    baskets = {"themes": {"AI 伺服器 / ODM": {"tickers": ["DELL", "SMCI"]}}}
    suggestions = ir.suggest_roles(["DELL"], taxonomy=taxonomy, theme_baskets=baskets)
    assert suggestions[0]["ticker"] == "DELL"
    assert suggestions[0]["suggested_primary_role"] == "ai_server_odm"
    assert suggestions[0]["status"] == "suggested"


def test_approved_override_wins_over_suggestion():
    taxonomy = {"roles": {"ai_server_odm": {"name": "AI Server / ODM"}, "hbm_memory": {"name": "HBM / Memory"}}}
    overrides = {"tickers": {"DELL": {"primary_role": "ai_server_odm", "secondary_roles": [], "confidence": 0.95}}}
    row = ir.resolve_role("DELL", taxonomy=taxonomy, overrides=overrides, suggestions=[])
    assert row["source"] == "approved"
    assert row["primary_role_name"] == "AI Server / ODM"
```

- [ ] **Step 2: Verify tests fail**

Run: `.venv/bin/python scripts/test_industry_roles.py`

Expected: import or function errors because `scripts/industry_roles.py` does not exist.

- [ ] **Step 3: Implement minimal engine**

Implement:

- `load_taxonomy(content_dir=None)`
- `load_overrides(content_dir=None)`
- `load_suggestions(reports_dir=None)`
- `suggest_roles(tickers, taxonomy, theme_baskets, social=None)`
- `resolve_role(ticker, taxonomy, overrides, suggestions)`

- [ ] **Step 4: Verify tests pass**

Run: `.venv/bin/python scripts/test_industry_roles.py`

Expected: all industry-role tests pass.

### Task 2: Review Actions

**Files:**
- Modify: `scripts/test_industry_roles.py`
- Modify: `scripts/industry_roles.py`

- [ ] **Step 1: Write failing tests**

Add tests for platform actions:

```python
def test_approve_suggestion_persists_override_and_marks_reviewed():
    with TemporaryDirectory() as td:
        root = Path(td)
        content = root / "content"
        reports = root / "reports"
        content.mkdir()
        reports.mkdir()
        (content / "industry_roles.json").write_text(json.dumps({"roles": {"ai_server_odm": {"name": "AI Server / ODM"}}}), encoding="utf-8")
        (reports / "industry_role_suggestions.json").write_text(json.dumps({"suggestions": [{
            "ticker": "DELL",
            "suggested_primary_role": "ai_server_odm",
            "suggested_secondary_roles": [],
            "confidence": 0.84,
            "status": "suggested",
        }]}), encoding="utf-8")
        result = ir.review_suggestion("DELL", "approve", content_dir=content, reports_dir=reports)
        assert result["status"] == "approved"
        overrides = json.loads((content / "industry_role_overrides.json").read_text(encoding="utf-8"))
        assert overrides["tickers"]["DELL"]["primary_role"] == "ai_server_odm"
```

- [ ] **Step 2: Verify tests fail**

Run: `.venv/bin/python scripts/test_industry_roles.py`

Expected: `review_suggestion` missing.

- [ ] **Step 3: Implement review action persistence**

Implement `review_suggestion(ticker, action, primary_role=None, secondary_roles=None, content_dir=None, reports_dir=None)` for `approve`, `reject`, and `defer`.

- [ ] **Step 4: Verify tests pass**

Run: `.venv/bin/python scripts/test_industry_roles.py`

Expected: all industry-role tests pass.

### Task 3: Trade State Integration

**Files:**
- Modify: `scripts/test_trade_state.py`
- Modify: `scripts/trade_state.py`
- Modify: `ui/trade_state.py`

- [ ] **Step 1: Write failing test**

Add a test proving trade-state rows expose an approved role label:

```python
def test_build_rows_includes_approved_industry_role():
    with TemporaryDirectory() as td:
        root = Path(td)
        reports = root / "reports"
        content = root / "content"
        reports.mkdir()
        content.mkdir()
        candidate_path = root / "ranked_candidates.json"
        candidate_path.write_text(json.dumps({"tickers": [{"ticker": "DELL", "last_price": 100.0, "ma50": 90.0, "ma200": 80.0, "macd_current": 1.0}]}), encoding="utf-8")
        (content / "industry_roles.json").write_text(json.dumps({"roles": {"ai_server_odm": {"name": "AI Server / ODM"}}}), encoding="utf-8")
        (content / "industry_role_overrides.json").write_text(json.dumps({"tickers": {"DELL": {"primary_role": "ai_server_odm", "secondary_roles": [], "confidence": 0.95}}}), encoding="utf-8")
        rows = ts.build_trade_state_rows(reports_dir=reports, content_dir=content, candidate_path=candidate_path)
    assert rows[0]["industry_role"] == "AI Server / ODM"
    assert rows[0]["industry_role_source"] == "approved"
```

- [ ] **Step 2: Verify test fails**

Run: `.venv/bin/python scripts/test_trade_state.py`

Expected: role fields are missing.

- [ ] **Step 3: Add role overlay**

Call `industry_roles.resolve_role()` inside `build_trade_state_rows()` and add `industry_role`, `industry_role_source`, and `industry_role_confidence` fields. Add a `產業鏈角色` column in `ui/trade_state.py`.

- [ ] **Step 4: Verify tests pass**

Run: `.venv/bin/python scripts/test_trade_state.py`

Expected: all trade-state tests pass.

### Task 4: Review Page And Navigation

**Files:**
- Create: `ui/industry_roles.py`
- Modify: `app.py`
- Modify: `scripts/test_dashboard_navigation.py`

- [ ] **Step 1: Write failing navigation tests**

Add tests that `產業鏈分類` exists under `資料維護`, imports `industry_roles`, and uses url path `industry-roles`.

- [ ] **Step 2: Verify test fails**

Run: `.venv/bin/python scripts/test_dashboard_navigation.py`

Expected: missing import/page assertions fail.

- [ ] **Step 3: Implement Streamlit page**

Build a dense operational page with:

- summary cards
- pending suggestions table
- selected suggestion evidence
- approve / reject / defer buttons
- approved role map table

- [ ] **Step 4: Verify navigation tests pass**

Run: `.venv/bin/python scripts/test_dashboard_navigation.py`

Expected: all navigation tests pass.

### Task 5: Regression

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Add tests to `make test`**

Add `$(PY) scripts/test_industry_roles.py` near the other domain tests.

- [ ] **Step 2: Run checks**

Run:

```bash
.venv/bin/python scripts/test_industry_roles.py
.venv/bin/python scripts/test_trade_state.py
.venv/bin/python scripts/test_dashboard_navigation.py
.venv/bin/python -m py_compile scripts/industry_roles.py scripts/test_industry_roles.py ui/industry_roles.py scripts/trade_state.py ui/trade_state.py app.py
make test
```

Expected: all commands pass.

### Task 6: Review Feedback Tightening

**Files:**
- Modify: `scripts/test_industry_roles.py`
- Modify: `scripts/industry_roles.py`
- Modify: `scripts/test_trade_state.py`
- Modify: `scripts/trade_state.py`
- Modify: `scripts/test_dashboard_navigation.py`
- Modify: `ui/trade_state.py`
- Modify: `ui/industry_roles.py`

- [ ] **Step 1: Write failing tests**

Add regression tests that:

- `generate_suggestions()` preserves existing `approved`, `rejected`, and `deferred` review states when suggestions are regenerated.
- `resolve_role()` always returns a displayable tag and explicit `status`, including `unclassified`.
- `build_trade_state_rows()` always emits `industry_role`, `industry_role_source`, and `industry_role_status`.
- `ui/trade_state.py` exposes an industry-role filter and renders role chips in the detail view.

- [ ] **Step 2: Verify tests fail**

Run:

```bash
.venv/bin/python scripts/test_industry_roles.py
.venv/bin/python scripts/test_trade_state.py
.venv/bin/python scripts/test_dashboard_navigation.py
```

Expected: new tests fail because status preservation, role status, and UI filter contracts are not implemented.

- [ ] **Step 3: Implement tightening changes**

Implement:

- merge regenerated suggestions with prior reviewed state instead of overwriting the review queue
- explicit `status` in `resolve_role()` for approved/suggested/unclassified outcomes
- `industry_role_status` in trade-state rows
- role filter and role chip display in `交易狀態`
- search/status/missing-classification views in `產業鏈分類`

- [ ] **Step 4: Verify**

Run the targeted tests, py_compile, and `make test`.
