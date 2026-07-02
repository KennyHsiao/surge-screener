# Data Health Source Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Data Health able to generate the source artifacts that Analytics DB imports, so `universe_snapshots`, `daily_bars`, and `daily_money_flow` no longer stay at 0 rows after a rebuild.

**Architecture:** Keep JSON/Parquet reports as the write source of truth and DuckDB as the read model. Add a standalone source-refresh orchestrator that can be called from Data Health, deploy, and scheduled self-hosted automation; then keep low-frequency/private sources as separate explicit refresh actions. Do not expand Today Decision "完整刷新" into every research pipeline.

**Post-review amendment:** Push deploys should not call external market-data
providers. The deploy script exposes `RUN_SOURCE_REFRESH`; scheduled deploys and
opted-in manual deploys set it to `1`, while normal push deploys only rebuild
Analytics DB and publish checks from existing shared artifacts.

**Tech Stack:** Python scripts, Streamlit UI, DuckDB/Parquet Analytics Store, GitHub Actions, existing no-shell argv/background patterns.

---

## Scope

P0 fixes the current blocker:

- Generate or refresh `reports/universe/YYYY-MM-DD.json`
- Generate or refresh `reports/market_data/daily_bars/YYYY-MM-DD.parquet`
- Generate or refresh `reports/money_flow/YYYY-MM-DD.json`
- Refresh `trade_state` and `industry_roles` because they already sit in `refresh_data_artifacts()`
- Rebuild Analytics DB and publish `reports/analytics_checks/latest.json`
- Persist these generated source directories across test-server releases

P1 adds Data Health controls for low-frequency sources:

- Theme Flow verified snapshot
- Sector Rotation verified snapshot
- Risk Guard scan entry point
- IBKR reconcile remains manual/local-only

P2 makes the test server catch up automatically even when report-writing GitHub jobs use `GITHUB_TOKEN` commits that do not trigger normal push workflows.

## Files

- Create: `scripts/data_source_refresh.py`
  - Standalone orchestrator for core source refresh + Analytics DB rebuild/checks.
  - Imports `scripts.run_candidate_pipeline.refresh_data_artifacts()` instead of duplicating provider logic.
- Create: `scripts/test_data_source_refresh.py`
  - Offline unit tests using fake refresher/store/check modules.
- Modify: `ui/analytics_db.py`
  - Add a Data Health button: `刷新核心 Source + 重建 DB`.
  - Add separate low-frequency refresh buttons in P1.
- Modify: `scripts/test_dashboard_navigation.py`
  - Assert the Data Health center exposes the new source-refresh controls.
- Modify: `scripts/deploy_test_server.sh`
  - Preserve source report directories under `$APP_ROOT/shared`.
  - Run the new source refresh before `analytics_store.py refresh` only when
    `RUN_SOURCE_REFRESH=1`.
- Modify: `scripts/test_deploy_artifacts.py`
  - Assert source dirs are preserved and deploy gates source refresh before Analytics DB rebuild.
- Modify: `.github/workflows/deploy_test_server.yml`
  - Add a weekday scheduled self-hosted deploy/data-health refresh.
- Modify: `docs/analytics-checks-automation.md` or `docs/analytics-store-data-inventory.md`
  - Document what Data Health refreshes automatically vs what stays manual.

## Blocking-Issue Review

- No destructive actions are required.
- IBKR cannot be fully automated in GitHub/remote CI because it needs a local Gateway/TWS session. Keep it manual.
- Paid/LLM actions should not run silently on every page load or deploy. Keep Sector Rotation LLM read and Theme Flow AI read explicit.
- Deploy should not fail to restart the app just because a free provider has a temporary outage. The checks report should show `BLOCK`; a separate scheduled workflow can fail red if desired after P0.

---

### Task 1: Add Tests For Core Source Refresh Orchestrator

**Files:**
- Create: `scripts/test_data_source_refresh.py`
- No production code yet

- [ ] **Step 1: Write failing tests**

```python
#!/usr/bin/env python3
"""Self-contained tests for Data Health source refresh orchestration.

Run: .venv/bin/python scripts/test_data_source_refresh.py
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "data_source_refresh_under_test",
        ROOT / "scripts" / "data_source_refresh.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_refresh_core_sources_then_analytics_in_order() -> None:
    mod = _load_module()
    calls: list[str] = []

    class FakeStore:
        @staticmethod
        def analytics_dir():
            calls.append("analytics_dir")
            return Path("/tmp/surge-analytics")

        @staticmethod
        def refresh_all(*, reports_root, analytics_root):
            calls.append("analytics_store")
            return {
                "universe_snapshots": {"rows": 1500},
                "daily_bars": {"rows": 120000},
                "daily_money_flow": {"rows": 500},
            }

    class FakeChecks:
        @staticmethod
        def run_checks(*, analytics_root, output_path):
            calls.append("analytics_checks")
            return {
                "status": "PASS",
                "recommended_action": "USE_TODAY_SIGNALS",
                "warning_codes": [],
            }

    def fake_refresher(*, reports_root, content_root, as_of_date=None):
        calls.append("source_refresh")
        return {
            "tickers": ["NVDA", "AMD"],
            "steps": [
                {"name": "universe", "status": "ok"},
                {"name": "daily_bars", "status": "ok"},
                {"name": "money_flow", "status": "ok"},
            ],
        }

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        result = mod.refresh_core_sources_and_analytics(
            reports_root=root / "reports",
            content_root=root / "content",
            analytics_root=root / "analytics",
            checks_output=root / "reports" / "analytics_checks" / "latest.json",
            data_refresher=fake_refresher,
            analytics_store_module=FakeStore,
            analytics_checks_module=FakeChecks,
        )

    if calls != ["source_refresh", "analytics_store", "analytics_checks"]:
        raise AssertionError(calls)
    if result["checks"]["status"] != "PASS":
        raise AssertionError(result)
    if result["tables"]["daily_bars"] != 120000:
        raise AssertionError(result)


def test_source_error_is_reported_without_skipping_analytics() -> None:
    mod = _load_module()
    calls: list[str] = []

    class FakeStore:
        @staticmethod
        def refresh_all(*, reports_root, analytics_root):
            calls.append("analytics_store")
            return {"daily_bars": {"rows": 0}}

    class FakeChecks:
        @staticmethod
        def run_checks(*, analytics_root, output_path):
            calls.append("analytics_checks")
            return {"status": "BLOCK", "recommended_action": "BLOCK_TODAY_SIGNALS"}

    def fake_refresher(*, reports_root, content_root, as_of_date=None):
        calls.append("source_refresh")
        return {
            "tickers": [],
            "steps": [
                {"name": "universe", "status": "error", "error": "provider unavailable"},
                {"name": "daily_bars", "status": "error", "error": "no tickers"},
            ],
        }

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        result = mod.refresh_core_sources_and_analytics(
            reports_root=root / "reports",
            content_root=root / "content",
            analytics_root=root / "analytics",
            checks_output=root / "reports" / "analytics_checks" / "latest.json",
            data_refresher=fake_refresher,
            analytics_store_module=FakeStore,
            analytics_checks_module=FakeChecks,
        )

    if calls != ["source_refresh", "analytics_store", "analytics_checks"]:
        raise AssertionError(calls)
    if result["source_status"] != "error":
        raise AssertionError(result)
    if result["checks"]["status"] != "BLOCK":
        raise AssertionError(result)


if __name__ == "__main__":
    tests = [
        test_refresh_core_sources_then_analytics_in_order,
        test_source_error_is_reported_without_skipping_analytics,
    ]
    for test in tests:
        test()
    print(f"data source refresh tests: {len(tests)} passed")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
.venv/bin/python scripts/test_data_source_refresh.py
```

Expected: FAIL with `FileNotFoundError` for `scripts/data_source_refresh.py`.

- [ ] **Step 3: Commit test only if using incremental commits**

```bash
git add scripts/test_data_source_refresh.py
git commit -m "test: cover data health source refresh orchestration"
```

---

### Task 2: Implement Core Source Refresh Orchestrator

**Files:**
- Create: `scripts/data_source_refresh.py`
- Test: `scripts/test_data_source_refresh.py`

- [ ] **Step 1: Add the implementation**

```python
#!/usr/bin/env python3
"""Data Health source refresh orchestration.

This is the standalone entry point for sources that Analytics DB imports. The
candidate pipeline already knows how to fetch the core daily artifacts; this
module makes that same refresh callable from Data Health, deploy, and cron
without running candidate ranking/scoring.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _default_reports_root() -> Path:
    return REPO / "reports"


def _default_content_root() -> Path:
    return REPO / "content"


def _default_checks_output(reports_root: Path) -> Path:
    return reports_root / "analytics_checks" / "latest.json"


def _table_rows(tables: dict[str, Any]) -> dict[str, int]:
    return {
        name: int(meta.get("rows", 0)) if isinstance(meta, dict) else 0
        for name, meta in tables.items()
    }


def _source_status(source_result: dict[str, Any]) -> str:
    steps = source_result.get("steps") if isinstance(source_result, dict) else []
    if not isinstance(steps, list) or not steps:
        return "unknown"
    if any(isinstance(step, dict) and step.get("status") == "error" for step in steps):
        return "error"
    return "ok"


def refresh_core_sources_and_analytics(
    *,
    reports_root: str | Path | None = None,
    content_root: str | Path | None = None,
    analytics_root: str | Path | None = None,
    checks_output: str | Path | None = None,
    as_of_date: str | None = None,
    data_refresher=None,
    analytics_store_module=None,
    analytics_checks_module=None,
) -> dict[str, Any]:
    """Refresh core report sources, rebuild Analytics DB, and publish checks."""
    reports = Path(reports_root) if reports_root is not None else _default_reports_root()
    content = Path(content_root) if content_root is not None else _default_content_root()

    if data_refresher is None:
        try:
            from scripts import run_candidate_pipeline
        except ImportError:
            import run_candidate_pipeline  # type: ignore
        data_refresher = run_candidate_pipeline.refresh_data_artifacts

    if analytics_store_module is None:
        try:
            from scripts import analytics_store
        except ImportError:
            import analytics_store  # type: ignore
        analytics_store_module = analytics_store

    if analytics_checks_module is None:
        try:
            from scripts import analytics_checks
        except ImportError:
            import analytics_checks  # type: ignore
        analytics_checks_module = analytics_checks

    analytics = (
        Path(analytics_root)
        if analytics_root is not None
        else Path(analytics_store_module.analytics_dir())
    )
    checks_path = Path(checks_output) if checks_output is not None else _default_checks_output(reports)
    checks_path.parent.mkdir(parents=True, exist_ok=True)

    source_result = data_refresher(
        reports_root=reports,
        content_root=content,
        as_of_date=as_of_date,
    )
    tables = analytics_store_module.refresh_all(
        reports_root=reports,
        analytics_root=analytics,
    )
    checks = analytics_checks_module.run_checks(
        analytics_root=analytics,
        output_path=checks_path,
    )
    return {
        "source_status": _source_status(source_result),
        "source": source_result,
        "tables": _table_rows(tables),
        "checks": {
            "status": checks.get("status"),
            "recommended_action": checks.get("recommended_action"),
            "warning_codes": checks.get("warning_codes", []),
        },
        "paths": {
            "reports_root": str(reports),
            "analytics_root": str(analytics),
            "checks_output": str(checks_path),
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh Data Health sources and Analytics DB")
    parser.add_argument("--reports-dir", default=str(_default_reports_root()))
    parser.add_argument("--content-dir", default=str(_default_content_root()))
    parser.add_argument("--analytics-dir", default=None)
    parser.add_argument("--checks-output", default=None)
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--json", action="store_true", help="print full JSON result")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = refresh_core_sources_and_analytics(
        reports_root=args.reports_dir,
        content_root=args.content_dir,
        analytics_root=args.analytics_dir,
        checks_output=args.checks_output,
        as_of_date=args.as_of_date,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print(
            "source={source} checks={checks} action={action}".format(
                source=result.get("source_status"),
                checks=(result.get("checks") or {}).get("status"),
                action=(result.get("checks") or {}).get("recommended_action"),
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the orchestrator tests**

Run:

```bash
.venv/bin/python scripts/test_data_source_refresh.py
```

Expected: `data source refresh tests: 2 passed`

- [ ] **Step 3: Run the existing candidate-pipeline tests**

Run:

```bash
.venv/bin/python scripts/test_candidate_pipeline_controls.py
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add scripts/data_source_refresh.py scripts/test_data_source_refresh.py
git commit -m "feat: add data health source refresh orchestrator"
```

---

### Task 3: Add Data Health Core Refresh Button

**Files:**
- Modify: `ui/analytics_db.py`
- Modify: `scripts/test_dashboard_navigation.py`
- Test: `scripts/test_dashboard_navigation.py`

- [ ] **Step 1: Extend navigation/UI test**

In `test_data_health_entry_and_refresh_center_are_discoverable()`, add these assertions:

```python
    assert_contains(ANALYTICS_DB, "刷新核心 Source + 重建 DB")
    assert_contains(ANALYTICS_DB, "data_source_refresh")
    assert_contains(ANALYTICS_DB, "universe / daily bars / money flow")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
.venv/bin/python scripts/test_dashboard_navigation.py
```

Expected: FAIL because `刷新核心 Source + 重建 DB` is not present yet.

- [ ] **Step 3: Add the UI action**

In `ui/analytics_db.py`, add:

```python
def _refresh_core_sources(root: Path) -> dict:
    from scripts import data_source_refresh

    result = data_source_refresh.refresh_core_sources_and_analytics(
        reports_root=_shared.REPORTS_DIR,
        content_root=_shared.CONTENT_DIR,
        analytics_root=root,
        checks_output=_checks_path(),
    )
    _clear_cached_reads()
    return result
```

Then update `_render_refresh_center(root)` so the first row has three actions instead of two:

```python
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("刷新核心 Source + 重建 DB", key="analytics_refresh_core_sources", use_container_width=True):
                try:
                    with st.spinner("刷新 universe / daily bars / money flow，並重建 Analytics DB..."):
                        details = _refresh_core_sources(root)
                    st.session_state["analytics_db_refresh_result"] = {
                        "status": "ok",
                        "message": "核心 source、Analytics DB 與資料健康檢查已更新。",
                        "details": details,
                    }
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.session_state["analytics_db_refresh_result"] = {
                        "status": "error",
                        "message": f"核心 source 刷新失敗：{e}",
                    }
        with c2:
            if st.button("重建 Analytics DB + 檢查", key="analytics_refresh_db", use_container_width=True):
                ...
        with c3:
            ticker_text = st.text_input(...)
```

Keep the existing DB-only and fundamentals code; only move them into `c2` and `c3`.

- [ ] **Step 4: Run the UI/navigation test**

Run:

```bash
.venv/bin/python scripts/test_dashboard_navigation.py
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add ui/analytics_db.py scripts/test_dashboard_navigation.py
git commit -m "feat: expose core source refresh in data health"
```

---

### Task 4: Preserve Core Source Directories On Test Server Deploy

**Files:**
- Modify: `scripts/deploy_test_server.sh`
- Modify: `scripts/test_deploy_artifacts.py`
- Test: `scripts/test_deploy_artifacts.py`

- [ ] **Step 1: Extend deploy artifact tests**

In `test_deploy_script()`, add requirements:

```python
    require("$APP_ROOT/shared/universe" in script and "reports/universe" in script,
            "deploy script must preserve universe snapshots across releases")
    require("$APP_ROOT/shared/market_data/daily_bars" in script
            and "reports/market_data/daily_bars" in script,
            "deploy script must preserve daily bar snapshots across releases")
    require("$APP_ROOT/shared/money_flow" in script and "reports/money_flow" in script,
            "deploy script must preserve money-flow snapshots across releases")
    require("$APP_ROOT/shared/trade_state" in script and "reports/trade_state" in script,
            "deploy script must preserve trade-state snapshots across releases")
    require("$APP_ROOT/shared/industry_roles" in script and "reports/industry_roles" in script,
            "deploy script must preserve industry-role snapshots across releases")
    require("scripts/data_source_refresh.py" in script
            and script.find("scripts/data_source_refresh.py") < script.find("scripts/analytics_store.py"),
            "deploy script must refresh source artifacts before rebuilding Analytics DB")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
.venv/bin/python scripts/test_deploy_artifacts.py
```

Expected: FAIL because the deploy script does not preserve these dirs or run `data_source_refresh.py`.

- [ ] **Step 3: Update shared directory creation**

In `scripts/deploy_test_server.sh`, expand the `mkdir -p` block to include:

```bash
"$APP_ROOT/shared/universe" \
"$APP_ROOT/shared/market_data/daily_bars" \
"$APP_ROOT/shared/money_flow" \
"$APP_ROOT/shared/trade_state" \
"$APP_ROOT/shared/industry_roles" \
```

Use the same style as existing shared dirs, keeping the command readable.

- [ ] **Step 4: Seed shared dirs from release reports when empty**

After the existing sector snapshot seed block, add:

```bash
if [ -d "$RELEASE_DIR/reports/universe" ] && [ -z "$(find "$APP_ROOT/shared/universe" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/universe/." "$APP_ROOT/shared/universe/"
fi
if [ -d "$RELEASE_DIR/reports/market_data/daily_bars" ] && [ -z "$(find "$APP_ROOT/shared/market_data/daily_bars" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/market_data/daily_bars/." "$APP_ROOT/shared/market_data/daily_bars/"
fi
if [ -d "$RELEASE_DIR/reports/money_flow" ] && [ -z "$(find "$APP_ROOT/shared/money_flow" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/money_flow/." "$APP_ROOT/shared/money_flow/"
fi
if [ -d "$RELEASE_DIR/reports/trade_state" ] && [ -z "$(find "$APP_ROOT/shared/trade_state" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/trade_state/." "$APP_ROOT/shared/trade_state/"
fi
if [ -d "$RELEASE_DIR/reports/industry_roles" ] && [ -z "$(find "$APP_ROOT/shared/industry_roles" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/industry_roles/." "$APP_ROOT/shared/industry_roles/"
fi
```

- [ ] **Step 5: Symlink release reports to shared dirs**

After the existing candidate/risk/theme/sector symlinks, add:

```bash
rm -rf "$RELEASE_DIR/reports/universe"
ln -s "$APP_ROOT/shared/universe" "$RELEASE_DIR/reports/universe"
mkdir -p "$RELEASE_DIR/reports/market_data"
rm -rf "$RELEASE_DIR/reports/market_data/daily_bars"
ln -s "$APP_ROOT/shared/market_data/daily_bars" "$RELEASE_DIR/reports/market_data/daily_bars"
rm -rf "$RELEASE_DIR/reports/money_flow"
ln -s "$APP_ROOT/shared/money_flow" "$RELEASE_DIR/reports/money_flow"
rm -rf "$RELEASE_DIR/reports/trade_state"
ln -s "$APP_ROOT/shared/trade_state" "$RELEASE_DIR/reports/trade_state"
rm -rf "$RELEASE_DIR/reports/industry_roles"
ln -s "$APP_ROOT/shared/industry_roles" "$RELEASE_DIR/reports/industry_roles"
```

- [ ] **Step 6: Run source refresh before Analytics DB rebuild**

Immediately before the existing `analytics_store.py refresh` call, add:

```bash
"$VENV_DIR/bin/python" "$RELEASE_DIR/scripts/data_source_refresh.py" \
  --reports-dir "$RELEASE_DIR/reports" \
  --content-dir "$RELEASE_DIR/content" \
  --analytics-dir "$SURGE_ANALYTICS_DIR" \
  --checks-output "$RELEASE_DIR/reports/analytics_checks/latest.json" \
  --json || true
```

Keep the existing `analytics_store.py refresh` and `analytics_checks.py run --allow-block` after this. The `|| true` keeps deploy from failing on a transient free-provider outage; the checks report remains the visible health gate.

- [ ] **Step 7: Run deploy artifact tests**

Run:

```bash
.venv/bin/python scripts/test_deploy_artifacts.py
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add scripts/deploy_test_server.sh scripts/test_deploy_artifacts.py
git commit -m "fix: preserve and refresh analytics source artifacts on deploy"
```

---

### Task 5: Add Scheduled Test-Server Data Health Catch-Up

**Files:**
- Modify: `.github/workflows/deploy_test_server.yml`
- Modify: `scripts/test_deploy_artifacts.py`
- Test: `scripts/test_deploy_artifacts.py`

- [ ] **Step 1: Extend workflow test**

Add a new test in `scripts/test_deploy_artifacts.py`:

```python
def test_deploy_workflow_schedules_data_health_refresh() -> None:
    workflow = read(".github/workflows/deploy_test_server.yml")
    require("schedule:" in workflow, "deploy workflow must have a scheduled catch-up path")
    require("'55 23 * * 1-5'" in workflow,
            "deploy workflow must refresh test server after weekday report-writing jobs")
    require("workflow_dispatch:" in workflow,
            "deploy workflow must remain manually runnable")
```

Add it to the `tests = [...]` list at the bottom.

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
.venv/bin/python scripts/test_deploy_artifacts.py
```

Expected: FAIL because the deploy workflow has no schedule.

- [ ] **Step 3: Add the schedule**

Update `.github/workflows/deploy_test_server.yml`:

```yaml
on:
  push:
    branches: [main]
  schedule:
    # Weekdays 23:55 UTC — catch up test-server reports after report-writing jobs.
    - cron: '55 23 * * 1-5'
  workflow_dispatch:
```

This works because `deploy_test_server.sh` now refreshes core sources and rebuilds Analytics DB.

- [ ] **Step 4: Run deploy artifact tests**

Run:

```bash
.venv/bin/python scripts/test_deploy_artifacts.py
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/deploy_test_server.yml scripts/test_deploy_artifacts.py
git commit -m "ci: schedule test server data health refresh"
```

---

### Task 6: Add Low-Frequency Data Health Actions

**Files:**
- Modify: `ui/analytics_db.py`
- Modify: `scripts/test_dashboard_navigation.py`
- Optional: Modify `scripts/sector_rotation.py`

- [ ] **Step 1: Extend UI test**

Add assertions:

```python
    assert_contains(ANALYTICS_DB, "刷新主題資金流")
    assert_contains(ANALYTICS_DB, "刷新板塊輪動快照")
    assert_contains(ANALYTICS_DB, "IBKR 持倉需在本機對帳")
```

- [ ] **Step 2: Implement Theme Flow verified refresh**

Add to `ui/analytics_db.py`:

```python
def _refresh_theme_flow(root: Path) -> dict:
    from scripts import theme_flow
    from scripts import theme_flow_controls

    flow = theme_flow.gather_theme_flow()
    if not flow or not flow.get("themes"):
        raise RuntimeError("theme flow refresh returned no usable themes")
    theme_flow_controls.write_snapshot(flow)
    analytics = _refresh_analytics_db(root)
    return {
        "theme_flow": {
            "as_of": flow.get("as_of"),
            "themes": len(flow.get("themes") or []),
            "snapshot_path": str(theme_flow_controls.SNAPSHOT_PATH),
        },
        "analytics": analytics,
    }
```

- [ ] **Step 3: Implement Sector Rotation verified snapshot**

Prefer adding a public non-LLM writer in `scripts/sector_rotation.py`:

```python
def write_verified_rotation_snapshot(
    *,
    archive_dir: str | Path = SNAPSHOT_ARCHIVE_DIR,
) -> dict:
    verified = _verified_payload()
    if not verified:
        return {"status": "no_data", "generated_at": datetime.now(timezone.utc).isoformat()}
    payload = {
        "status": "verified_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **verified,
    }
    as_of = _snapshot_date(payload)
    _write_json(Path(archive_dir) / f"{as_of}.json", payload)
    return payload
```

Then add to `ui/analytics_db.py`:

```python
def _refresh_sector_rotation_snapshot(root: Path) -> dict:
    from scripts import sector_rotation

    result = sector_rotation.write_verified_rotation_snapshot()
    if result.get("status") == "no_data":
        raise RuntimeError("sector rotation refresh returned no usable sectors")
    analytics = _refresh_analytics_db(root)
    return {
        "sector_rotation": {
            "status": result.get("status"),
            "as_of": result.get("as_of"),
            "sectors": len(result.get("sectors") or []),
        },
        "analytics": analytics,
    }
```

- [ ] **Step 4: Add buttons below core refresh**

In `_render_refresh_center(root)`, add a second row:

```python
        l1, l2, l3 = st.columns(3)
        with l1:
            if st.button("刷新主題資金流", key="analytics_refresh_theme_flow", use_container_width=True):
                ...
        with l2:
            if st.button("刷新板塊輪動快照", key="analytics_refresh_sector_rotation", use_container_width=True):
                ...
        with l3:
            st.caption("IBKR 持倉需在本機對帳；請到「IBKR 對帳」執行。")
```

Use the same `st.session_state["analytics_db_refresh_result"]` pattern as existing actions.

- [ ] **Step 5: Run tests**

Run:

```bash
.venv/bin/python scripts/test_dashboard_navigation.py
.venv/bin/python scripts/test_sector_rotation_archive.py
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add ui/analytics_db.py scripts/test_dashboard_navigation.py scripts/sector_rotation.py
git commit -m "feat: add low-frequency data health refresh actions"
```

---

### Task 7: Documentation And End-To-End Verification

**Files:**
- Modify: `docs/analytics-store-data-inventory.md`
- Modify: `docs/analytics-checks-automation.md` if present and relevant

- [ ] **Step 1: Document refresh ownership**

Add a short table:

```markdown
## Data Health Refresh Ownership

| Source | Automatic path | Manual path | Notes |
| --- | --- | --- | --- |
| Core source artifacts (`universe`, `daily_bars`, `money_flow`, `trade_state`, `industry_roles`) | Test-server deploy schedule + candidate pipeline post-run refresh | Data Health → 刷新核心 Source + 重建 DB | Required for 今日訊號 unblock. |
| Fundamentals | None by default | Data Health → 刷新基本面 | Low-frequency, ticker-scoped. |
| Theme Flow verified snapshot | Theme Flow page background refresh; optional Data Health action | Data Health → 刷新主題資金流 | Does not run AI read. |
| Sector Rotation verified snapshot | Scheduled deploy can import existing snapshots | Data Health → 刷新板塊輪動快照 | Non-LLM snapshot; AI read remains explicit. |
| Risk Guard | None by default | Risk Guard page → 掃描風險 | Manual scan writes dated snapshots and refreshes analytics. |
| IBKR positions | None | IBKR 對帳 page | Requires local Gateway/TWS. |
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
.venv/bin/python scripts/test_data_source_refresh.py
.venv/bin/python scripts/test_candidate_pipeline_controls.py
.venv/bin/python scripts/test_dashboard_navigation.py
.venv/bin/python scripts/test_deploy_artifacts.py
.venv/bin/python scripts/test_sector_rotation_archive.py
```

Expected: all pass.

- [ ] **Step 3: Run a dry local source refresh**

Run:

```bash
.venv/bin/python scripts/data_source_refresh.py --reports-dir reports --content-dir content --json
```

Expected:

- `source_status` is `ok`, or any provider errors are visible under `source.steps`.
- `tables.universe_snapshots`, `tables.daily_bars`, and `tables.daily_money_flow` are nonzero when providers return data.
- `checks.status` is no longer `BLOCK` for the three original 0-row blockers.

- [ ] **Step 4: Deploy verification**

After deploying to the test server, verify:

```bash
ssh antigravity 'python3 - <<PY
import json
from pathlib import Path
base = Path("/home/kenny/apps/surge-screener/current/reports")
for rel in ["universe", "market_data/daily_bars", "money_flow"]:
    p = base / rel
    print(rel, sum(1 for _ in p.rglob("*") if _.is_file()) if p.exists() else "missing")
checks = json.loads((base / "analytics_checks/latest.json").read_text())
print(checks["status"], checks["summary"])
for item in checks["checks"]:
    if item.get("status") == "BLOCK":
        print(item["id"], item["message"])
PY'
```

Expected: the three source dirs have files and the old blockers are gone. Other warnings may remain.

- [ ] **Step 5: Commit docs**

```bash
git add docs/analytics-store-data-inventory.md docs/analytics-checks-automation.md
git commit -m "docs: document data health refresh ownership"
```

---

## Acceptance Criteria

- Data Health has a one-click action that refreshes core source artifacts and rebuilds Analytics DB.
- Deploy preserves generated core source dirs under shared storage.
- Deploy runs source refresh before Analytics DB refresh.
- Test-server scheduled deploy/data-health catch-up runs on weekdays after report-writing jobs.
- `universe_snapshots`, `daily_bars`, and `daily_money_flow` no longer remain 0 rows after a successful source refresh.
- IBKR remains explicitly manual/local-only.
- LLM/paid reads remain explicit and are not triggered silently by DB rebuild.

## Recommended Execution Order

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Verify remote blocker is gone
6. Task 5
7. Task 6
8. Task 7

P0 is Tasks 1-5. Stop after P0 if the only objective is to unblock 今日訊號.
