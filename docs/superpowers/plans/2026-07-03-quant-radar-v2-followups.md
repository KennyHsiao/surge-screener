# Quant Radar V2 Follow-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the valid follow-ups from the Quant Radar v2 review without rebuilding features that are already shipped.

**Architecture:** Treat the v2 review as an input, not a spec. First remove duplicated UI/business logic, then add one high-value options microstructure summary, then reduce operational fragility in cache/status helpers. Keep pages behavior-compatible and use existing self-contained script tests.

**Tech Stack:** Python 3.11, Streamlit, Plotly, existing JSON reports, yfinance-backed option chains, DuckDB/Analytics DB tests.

---

## Pre-Implementation Review

Do **not** implement these as new P0 work:

- Greeks panel: already present in `ui/options_cockpit.py` via `_strategy_greeks()` and `_render_greeks_panel()`.
- P&L Payoff chart: already present in `ui/options_cockpit.py` via `_payoff_stats()` and `_payoff_fig()`.
- IV Rank / IV Percentile cockpit UI: already present via `scripts/iv_history.py` and `ui/options_cockpit.py`.

Use these commands before starting:

```bash
rg -n "Greeks 面板|P&L Payoff|def _strategy_greeks|def _payoff_fig|iv_rank" ui/options_cockpit.py scripts/test_options_cockpit_display.py
.venv/bin/python scripts/test_options_cockpit_display.py
```

Expected:

- `ui/options_cockpit.py` contains `Greeks 面板`, `P&L Payoff`, `_strategy_greeks`, `_payoff_fig`.
- `scripts/test_options_cockpit_display.py` passes.

---

### Task 1: Analyst Section Convergence

**Files:**
- Modify: `scripts/test_dashboard_navigation.py`
- Modify: `ui/us_screener.py`

- [ ] **Step 1: Write the failing static contract test**

Add this constant near the other file snapshots in `scripts/test_dashboard_navigation.py`:

```python
US_SCREENER = (ROOT / "ui" / "us_screener.py").read_text(encoding="utf-8")
```

Add this test near the analyst/navigation tests:

```python
def test_us_screener_reuses_embeddable_analyst_renderer() -> None:
    assert_contains(US_SCREENER, "analyst_views.render_for(ticker)")
    assert_not_contains(US_SCREENER, "_shared.load_analyst_views(ticker)")
    assert_not_contains(US_SCREENER, "data.get(\"recent_actions\")")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python scripts/test_dashboard_navigation.py
```

Expected: FAIL with `missing: analyst_views.render_for(ticker)`.

- [ ] **Step 3: Replace duplicated renderer**

In `ui/us_screener.py`, change the import:

```python
from . import _shared, analyst_views
```

Replace the body of `_render_analyst_section()` with:

```python
def _render_analyst_section(ticker: str) -> None:
    """賣方分析師評級 — reuse the canonical embeddable analyst detail."""
    with st.expander("📊 賣方分析師評級", expanded=False):
        analyst_views.render_for(ticker)
```

Remove the now-unused duplicated block inside `_render_analyst_section()` only. Do not remove imports that are used elsewhere in `ui/us_screener.py`.

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/python scripts/test_dashboard_navigation.py
```

Expected: `34/34 passed` or the updated total if more tests exist.

- [ ] **Step 5: Commit**

```bash
git add ui/us_screener.py scripts/test_dashboard_navigation.py
git commit -m "Converge screener analyst renderer"
```

---

### Task 2: Shared Run-Status UI Helpers

**Files:**
- Create: `ui/_run_status_view.py`
- Create: `scripts/test_run_status_view.py`
- Modify: `ui/today_decision.py`
- Modify: `ui/analytics_db.py`

- [ ] **Step 1: Write the failing helper tests**

Create `scripts/test_run_status_view.py`:

```python
#!/usr/bin/env python3
"""Tests for shared Streamlit run-status view helpers.

Run: .venv/bin/python scripts/test_run_status_view.py
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ui import _run_status_view as rsv  # noqa: E402


def test_interrupt_reason_detects_dead_pid() -> None:
    data = {"status": "running", "pid": 999, "updated_at": "2026-07-03T00:00:00Z"}
    reason = rsv.interrupt_reason(
        data,
        stale_after_seconds=600,
        dead_pid_message="dead",
        stale_message="stale",
        process_checker=lambda _pid: False,
        now=datetime(2026, 7, 3, 0, 1, tzinfo=timezone.utc),
    )
    assert reason == "dead", reason


def test_interrupt_reason_detects_stale_update() -> None:
    data = {"status": "running", "pid": 999, "updated_at": "2026-07-03T00:00:00Z"}
    reason = rsv.interrupt_reason(
        data,
        stale_after_seconds=600,
        dead_pid_message="dead",
        stale_message="stale",
        process_checker=lambda _pid: True,
        now=datetime(2026, 7, 3, 0, 11, tzinfo=timezone.utc),
    )
    assert reason == "stale", reason


def test_interrupted_status_merges_current_stage_and_appends_error() -> None:
    data = {
        "status": "running",
        "stage": {"id": "rank", "label": "排名", "progress_pct": 50},
        "stages": [{"id": "rank", "status": "running"}],
        "errors": [],
    }
    out = rsv.interrupted_status(
        data,
        reason="stopped",
        fallback_label="中斷",
        now=datetime(2026, 7, 3, 0, 0, tzinfo=timezone.utc),
    )
    assert out["status"] == "failed", out
    assert out["stage"]["status"] == "failed", out
    assert out["stages"][0]["message"] == "stopped", out
    assert out["errors"][-1]["message"] == "stopped", out


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  FAIL {test.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python scripts/test_run_status_view.py
```

Expected: FAIL with `ImportError` or missing module `ui._run_status_view`.

- [ ] **Step 3: Implement shared helper module**

Create `ui/_run_status_view.py`:

```python
"""Shared helpers for rendering/reconciling local run-status JSON in Streamlit pages."""

from __future__ import annotations

import copy
import os
from datetime import datetime, timezone
from typing import Any, Callable


def parse_utc(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def utc_iso(value: datetime | None = None) -> str:
    dt = value or datetime.now(timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def pid_is_running(pid: object) -> bool | None:
    try:
        value = int(pid)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return False
    try:
        os.kill(value, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def interrupt_reason(
    data: dict[str, Any] | None,
    *,
    stale_after_seconds: int,
    dead_pid_message: str,
    stale_message: str,
    now: datetime | None = None,
    process_checker: Callable[[object], bool | None] = pid_is_running,
) -> str | None:
    if not isinstance(data, dict) or data.get("status") != "running":
        return None
    pid_state = process_checker(data.get("pid"))
    if pid_state is False:
        return dead_pid_message
    updated = parse_utc(data.get("updated_at"))
    if updated is None:
        return None
    age = ((now or datetime.now(timezone.utc)) - updated).total_seconds()
    if age > stale_after_seconds:
        return stale_message
    return None


def merge_stage(stages: list[Any], stage: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen = False
    stage_id = stage.get("id")
    for item in stages:
        if not isinstance(item, dict):
            continue
        if item.get("id") == stage_id:
            merged = dict(item)
            merged.update(stage)
            out.append(merged)
            seen = True
        else:
            out.append(item)
    if not seen:
        out.append(stage)
    return out


def interrupted_status(
    data: dict[str, Any],
    *,
    reason: str,
    fallback_label: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    fixed = copy.deepcopy(data)
    current = fixed.get("stage") if isinstance(fixed.get("stage"), dict) else {}
    stage_id = str(current.get("id") or "interrupted")
    stage = dict(current)
    stage.update({
        "id": stage_id,
        "label": stage.get("label") or fallback_label,
        "status": "failed",
        "progress_pct": stage.get("progress_pct", 0),
        "message": reason,
    })
    finished_at = utc_iso(now)
    fixed["status"] = "failed"
    fixed["updated_at"] = finished_at
    fixed["finished_at"] = finished_at
    fixed["stage"] = stage
    fixed["stages"] = merge_stage(
        fixed.get("stages") if isinstance(fixed.get("stages"), list) else [],
        stage,
    )
    errors = fixed.get("errors") if isinstance(fixed.get("errors"), list) else []
    fixed["errors"] = [*errors, {"stage": stage_id, "message": reason, "at": finished_at}]
    return fixed
```

- [ ] **Step 4: Replace duplicate code in `ui/today_decision.py`**

Import the helper:

```python
from . import _run_status_view as run_status_view
```

Change `_candidate_interrupt_reason()` to delegate:

```python
def _candidate_interrupt_reason(
    data: dict | None,
    *,
    now: datetime | None = None,
    process_checker=run_status_view.pid_is_running,
) -> str | None:
    return run_status_view.interrupt_reason(
        data,
        stale_after_seconds=600,
        dead_pid_message="背景程序已不存在，這次本機候選刷新已中斷。",
        stale_message="本機候選刷新已超過 10 分鐘未更新，可能已中斷。",
        now=now,
        process_checker=process_checker,
    )
```

Change `_interrupted_candidate_status()` to delegate:

```python
def _interrupted_candidate_status(
    data: dict,
    reason: str,
    *,
    now: datetime | None = None,
) -> dict:
    return run_status_view.interrupted_status(
        data,
        reason=reason,
        fallback_label="本機候選刷新中斷",
        now=now,
    )
```

Remove local `_pid_is_running()` and `_merge_interrupted_stage()` from `ui/today_decision.py`.

- [ ] **Step 5: Replace duplicate code in `ui/analytics_db.py`**

Import the helper:

```python
from . import _run_status_view as run_status_view
```

Change `_data_health_interrupt_reason()` to delegate:

```python
def _data_health_interrupt_reason(
    data: dict | None,
    *,
    now: datetime | None = None,
    process_checker=run_status_view.pid_is_running,
) -> str | None:
    return run_status_view.interrupt_reason(
        data,
        stale_after_seconds=_DATA_HEALTH_RUNNING_TTL_SECONDS,
        dead_pid_message="背景程序已不存在，這次資料刷新已中斷；可重新啟動。",
        stale_message="這次刷新狀態已超過 3 小時未更新，可能已中斷；可重新啟動。",
        now=now,
        process_checker=process_checker,
    )
```

Change `_interrupted_data_health_status()` to delegate:

```python
def _interrupted_data_health_status(
    data: dict,
    reason: str,
    *,
    now: datetime | None = None,
) -> dict:
    return run_status_view.interrupted_status(
        data,
        reason=reason,
        fallback_label="資料刷新中斷",
        now=now,
    )
```

Remove local `_pid_is_running()` and `_merge_interrupted_stage()` from `ui/analytics_db.py`.

- [ ] **Step 6: Run tests**

Run:

```bash
.venv/bin/python scripts/test_run_status_view.py
.venv/bin/python scripts/test_dashboard_navigation.py
.venv/bin/python scripts/test_candidate_pipeline_controls.py
.venv/bin/python scripts/test_analytics_db_refresh_runtime.py
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add ui/_run_status_view.py ui/today_decision.py ui/analytics_db.py scripts/test_run_status_view.py
git commit -m "Share run status view helpers"
```

---

### Task 3: Options Cockpit Microstructure Summary

**Files:**
- Modify: `ui/options_cockpit.py`
- Modify: `scripts/test_options_cockpit_display.py`
- Modify: `scripts/test_dashboard_navigation.py`

This is the correct replacement for the outdated P0 recommendation. Do not rebuild Greeks/Payoff/IV Rank. Add a compact Max Pain / GEX-proxy / wall summary beside the existing cockpit.

- [ ] **Step 1: Write failing option-chain summary tests**

Add to `scripts/test_options_cockpit_display.py`:

```python
def test_chain_microstructure_summary_computes_max_pain_and_gex_proxy() -> None:
    chain = pd.DataFrame({
        "strike": [95.0, 100.0, 105.0],
        "call_oi": [200, 1000, 300],
        "put_oi": [1200, 400, 100],
        "call_vol": [100, 300, 80],
        "put_vol": [200, 100, 40],
    })

    summary = oc._chain_microstructure_summary(chain, spot=100.0)

    assert summary["max_pain"] == 100.0, summary
    assert summary["call_wall"] == 100.0, summary
    assert summary["put_wall"] == 95.0, summary
    assert summary["gex_regime"] == "negative_proxy", summary
```

Add this function to the `tests = [...]` list in `main()`.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python scripts/test_options_cockpit_display.py
```

Expected: FAIL with `AttributeError: module 'ui.options_cockpit' has no attribute '_chain_microstructure_summary'`.

- [ ] **Step 3: Implement summary helper**

Add this helper to `ui/options_cockpit.py` near other option-chain helpers:

```python
def _chain_microstructure_summary(chain: pd.DataFrame, spot: float) -> dict:
    if chain is None or chain.empty or not spot:
        return {"available": False}
    df = chain.copy()
    for col in ("strike", "call_oi", "put_oi"):
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df = df[df["strike"] > 0]
    if df.empty or (df["call_oi"].sum() + df["put_oi"].sum()) <= 0:
        return {"available": False}

    strikes = df["strike"].tolist()
    pains = []
    for price in strikes:
        call_pain = (df["call_oi"] * (price - df["strike"]).clip(lower=0)).sum()
        put_pain = (df["put_oi"] * (df["strike"] - price).clip(lower=0)).sum()
        pains.append((float(price), float(call_pain + put_pain)))
    max_pain = min(pains, key=lambda item: item[1])[0]

    call_wall = float(df.loc[df["call_oi"].idxmax(), "strike"]) if df["call_oi"].sum() else None
    put_wall = float(df.loc[df["put_oi"].idxmax(), "strike"]) if df["put_oi"].sum() else None
    near = df[(df["strike"] >= spot * 0.95) & (df["strike"] <= spot * 1.05)]
    near_call_oi = float(near["call_oi"].sum())
    near_put_oi = float(near["put_oi"].sum())
    if near_put_oi > near_call_oi * 1.5:
        gex_regime = "negative_proxy"
    elif near_call_oi > near_put_oi * 1.5:
        gex_regime = "positive_proxy"
    else:
        gex_regime = "neutral_proxy"

    return {
        "available": True,
        "max_pain": round(max_pain, 2),
        "call_wall": call_wall,
        "put_wall": put_wall,
        "gex_regime": gex_regime,
        "near_call_oi": near_call_oi,
        "near_put_oi": near_put_oi,
        "source": "free_yfinance_oi_proxy",
    }
```

- [ ] **Step 4: Render compact cockpit panel**

Add a renderer:

```python
def _render_microstructure_summary(d: CockpitData) -> None:
    summary = _chain_microstructure_summary(d.chain, d.spot)
    if not summary.get("available"):
        return
    st.markdown("##### 鏈微結構摘要")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Max Pain", f"${summary['max_pain']:g}")
    c2.metric("Call Wall", f"${summary['call_wall']:g}" if summary.get("call_wall") else "—")
    c3.metric("Put Wall", f"${summary['put_wall']:g}" if summary.get("put_wall") else "—")
    c4.metric("GEX Proxy", str(summary.get("gex_regime") or "—").replace("_proxy", ""))
    st.caption("OI 來自免費 yfinance；GEX/Max Pain 為 proxy，盤中 OI 可能延遲，需搭配完整期權分析頁確認。")
```

Call `_render_microstructure_summary(d)` inside the existing cockpit render flow after `_render_contract_and_payoff(d)` and before the full chain distribution section.

- [ ] **Step 5: Add static UI contract**

In `scripts/test_dashboard_navigation.py`, extend `test_options_cockpit_contract_panel_is_tradeability_first()` with:

```python
"鏈微結構摘要",
"Max Pain",
"GEX Proxy",
```

- [ ] **Step 6: Run tests**

Run:

```bash
.venv/bin/python scripts/test_options_cockpit_display.py
.venv/bin/python scripts/test_dashboard_navigation.py
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add ui/options_cockpit.py scripts/test_options_cockpit_display.py scripts/test_dashboard_navigation.py
git commit -m "Add options cockpit microstructure summary"
```

---

### Task 4: Cache TTL Constants And First Safe Migration

**Files:**
- Create: `scripts/cache_policy.py`
- Create: `scripts/test_cache_policy.py`
- Modify: `ui/momentum_options.py`

Scope boundary: do **not** route fail-closed forward-validation scanners through a shared cache. The existing `scripts/_yfinance.py` warning is correct.

- [ ] **Step 1: Write failing cache-policy tests**

Create `scripts/test_cache_policy.py`:

```python
#!/usr/bin/env python3
"""Tests for shared cache TTL policy constants.

Run: .venv/bin/python scripts/test_cache_policy.py
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import cache_policy as cp  # noqa: E402


def test_cache_ttl_tiers_are_named_and_ordered() -> None:
    assert cp.HOT_TTL_SECONDS == 60
    assert cp.WARM_TTL_SECONDS == 900
    assert cp.COLD_TTL_SECONDS == 21600
    assert cp.LONG_TTL_SECONDS == 604800
    assert cp.HOT_TTL_SECONDS < cp.WARM_TTL_SECONDS < cp.COLD_TTL_SECONDS < cp.LONG_TTL_SECONDS


def main() -> int:
    try:
        test_cache_ttl_tiers_are_named_and_ordered()
        print("  PASS test_cache_ttl_tiers_are_named_and_ordered")
        print("\n1/1 passed")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"  FAIL test_cache_ttl_tiers_are_named_and_ordered: {exc}")
        print("\n0/1 passed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python scripts/test_cache_policy.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'cache_policy'`.

- [ ] **Step 3: Implement constants**

Create `scripts/cache_policy.py`:

```python
"""Shared cache TTL policy for UI/data-fetch paths.

These constants name existing cache horizons before broad migration. They do not
change fail-closed research/forward-validation fetches, which must see outages.
"""

HOT_TTL_SECONDS = 60          # quotes / current status
WARM_TTL_SECONDS = 900        # option chains / short-lived market panels
COLD_TTL_SECONDS = 21600      # fundamentals / analyst / institution snapshots
LONG_TTL_SECONDS = 604800     # slow static classifications
```

- [ ] **Step 4: Migrate one safe UI cache**

In `ui/momentum_options.py`, import the constants:

```python
from scripts import cache_policy
```

Change:

```python
@st.cache_data(ttl=900, show_spinner=False)
```

to:

```python
@st.cache_data(ttl=cache_policy.WARM_TTL_SECONDS, show_spinner=False)
```

- [ ] **Step 5: Run tests**

Run:

```bash
.venv/bin/python scripts/test_cache_policy.py
.venv/bin/python scripts/test_options_cockpit_display.py
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/cache_policy.py scripts/test_cache_policy.py ui/momentum_options.py
git commit -m "Introduce cache TTL policy constants"
```

---

### Task 5: Today Decision Candidate Controls Extraction

**Files:**
- Create: `ui/_candidate_controls.py`
- Modify: `ui/today_decision.py`
- Modify: `scripts/test_dashboard_navigation.py`

This is P2 maintainability. Do it after Tasks 1-4 because it moves more code.

- [ ] **Step 1: Write static extraction guard**

Add to `scripts/test_dashboard_navigation.py`:

```python
CANDIDATE_CONTROLS = (ROOT / "ui" / "_candidate_controls.py").read_text(encoding="utf-8")
```

Add:

```python
def test_today_decision_candidate_controls_are_extracted() -> None:
    assert_contains(TODAY, "_candidate_controls.render(")
    assert_contains(CANDIDATE_CONTROLS, "def render(")
    assert_contains(CANDIDATE_CONTROLS, "完整刷新")
    assert_contains(CANDIDATE_CONTROLS, "少量 LLM")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python scripts/test_dashboard_navigation.py
```

Expected: FAIL because `ui/_candidate_controls.py` does not exist.

- [ ] **Step 3: Move controls code into new module**

Create `ui/_candidate_controls.py` and move these responsibilities from `ui/today_decision.py`:

- local candidate status path handling
- launch tracking
- `_launch_candidate_run`
- `_render_candidate_pipeline_controls`
- `_render_local_refresh_status`
- candidate run history table

Expose a single entry:

```python
def render() -> None:
    _render_candidate_pipeline_controls()
    _render_local_refresh_status()
```

Keep file-local helper names private. Import existing launch helpers from `scripts.candidate_pipeline_controls` directly in the new module.

- [ ] **Step 4: Wire Today Decision**

In `ui/today_decision.py`, import:

```python
from . import _candidate_controls
```

Replace:

```python
_render_candidate_pipeline_controls()
_render_local_refresh_status()
```

with:

```python
_candidate_controls.render()
```

Do not move `_render_candidate_results()` in this task; candidate display stays in `today_decision.py`.

- [ ] **Step 5: Run tests**

Run:

```bash
.venv/bin/python scripts/test_dashboard_navigation.py
.venv/bin/python scripts/test_candidate_pipeline_controls.py
.venv/bin/python scripts/test_run_status_view.py
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add ui/_candidate_controls.py ui/today_decision.py scripts/test_dashboard_navigation.py
git commit -m "Extract today decision candidate controls"
```

---

## Review Gates

After every task:

```bash
git diff --check
git status --short
```

Before final push:

```bash
.venv/bin/python scripts/test_dashboard_navigation.py
.venv/bin/python scripts/test_options_cockpit_display.py
.venv/bin/python scripts/test_candidate_pipeline_controls.py
.venv/bin/python scripts/test_analytics_checks.py
.venv/bin/python -m py_compile ui/us_screener.py ui/options_cockpit.py ui/today_decision.py ui/analytics_db.py
```

Expected: all tests pass. If `scripts/test_analytics_checks.py` emits Arrow `sysctlbyname` warnings under sandbox but exits 0, that is acceptable.

## Deliberately Deferred

- Full `analytics_db.py` split: useful, but lower value than status-helper extraction; defer until another Analytics UI change touches that file.
- Full yfinance migration: do not bulk-rewrite. Move one safe, staleness-tolerant UI path per PR and never cache fail-closed scanner/forward-validation paths.
- Portfolio Greeks aggregation: valid P1, but requires IBKR live/position schema work. Do it as a separate plan tied to IBKR reconciliation.
- Earnings calendar: partially present in Options Cockpit; platform-wide earnings countdown should be a separate small plan after source reliability is confirmed.
