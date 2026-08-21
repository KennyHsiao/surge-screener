#!/usr/bin/env python3
"""Focused tests for the unattended natural-validation observer."""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
import tempfile
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "natural_validation_observer_under_test",
    ROOT / "scripts" / "natural_validation_observer.py",
)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


def _window():
    return MOD.validation_window(date(2026, 8, 18))


def _data_health_fixture() -> tuple[dict, dict, dict, dict, dict]:
    status = {
        "status": "succeeded",
        "started_at": "2026-08-17T22:15:01Z",
        "finished_at": "2026-08-17T22:52:28Z",
        "metrics": {"blockers": 0, "today_signal_can_publish": True},
    }
    unit = {"ActiveState": "inactive", "Result": "success", "ExecMainStatus": "0"}
    analytics = {
        "generated_at": "2026-08-17T22:52:20Z",
        "as_of_date": "2026-08-18",
        "status": "WARN",
        "summary": {"block": 0},
        "today_signal_readiness": {"can_publish": True},
        "checks": [
            {"id": "table:daily_reports:latest_date", "status": "PASS", "value": "2026-08-15"},
            {
                "id": "table:portfolio_positions:row_count",
                "status": "PASS",
                "availability": "not_configured",
                "value": 0,
            },
            {
                "id": "performance:no_confirmed_picks_streak",
                "status": "WARN",
                "scan_state_counts": {
                    "successful_zero_pick": 14,
                    "successful_with_picks": 0,
                    "published_unclassified": 0,
                    "missing": None,
                    "failed": None,
                    "unpublished": None,
                },
            },
        ],
    }
    db = {"exists": True, "mtime": "2026-08-17T22:52:18Z"}
    risk = {
        "generated_at": "2026-08-17T22:45:00Z",
        "as_of": "2026-08-17",
        "summary": {"count": 10},
        "data_sources": {
            "regime": "live_yfinance",
            "regime_as_of": "2026-08-17",
            "regime_observed_on": "2026-08-17",
            "regime_fallback_reason": "stale_scored_regime",
        },
    }
    return status, unit, analytics, db, risk


def test_window_uses_utc_business_date() -> None:
    window = _window()
    assert window.local_date.isoformat() == "2026-08-18"
    assert window.eod_due.isoformat() == "2026-08-18T06:30:00+08:00"
    assert window.report_date.isoformat() == "2026-08-17"


def test_preflight_requires_exact_deployed_hash() -> None:
    with tempfile.TemporaryDirectory() as directory:
        app_root = Path(directory)
        target = app_root / "current/scripts/analytics_checks.py"
        target.parent.mkdir(parents=True)
        target.write_text("reviewed\n", encoding="utf-8")
        sha = MOD.hashlib.sha256(target.read_bytes()).hexdigest()
        systemd = {}
        for unit in (
            MOD.DATA_HEALTH_UNIT, MOD.DATA_HEALTH_TIMER, MOD.THEME_UNIT, MOD.THEME_TIMER,
        ):
            template = app_root / "current/deploy" / unit
            installed = app_root / "installed" / unit
            template.parent.mkdir(parents=True, exist_ok=True)
            installed.parent.mkdir(parents=True, exist_ok=True)
            template.write_text(f"unit={unit}\n", encoding="utf-8")
            installed.write_bytes(template.read_bytes())
            systemd[unit] = {
                "enabled": "enabled" if unit.endswith(".timer") else "disabled",
                "active": "active" if unit.endswith(".timer") else "inactive",
                "show": {"FragmentPath": str(installed), "NeedDaemonReload": "no"},
            }
        systemd[MOD.RUNNER_UNIT] = {"enabled": "enabled", "active": "active", "show": {}}
        result = MOD.evaluate_preflight(
            app_root=app_root,
            expected_hashes={"scripts/analytics_checks.py": sha},
            systemd=systemd,
            clock={"Timezone": "Asia/Taipei", "NTPSynchronized": "yes"},
            disk={"free_bytes": 6 * 1024**3, "free_inodes": 20_000},
            github_ok=True,
            github_error=None,
        )
        assert result["state"] == "PASS", result
        result = MOD.evaluate_preflight(
            app_root=app_root,
            expected_hashes={"scripts/analytics_checks.py": "0" * 64},
            systemd=systemd,
            clock={"Timezone": "Asia/Taipei", "NTPSynchronized": "yes"},
            disk={"free_bytes": 6 * 1024**3, "free_inodes": 20_000},
            github_ok=True,
            github_error=None,
        )
        assert result["state"] == "FAIL"


def test_data_health_requires_fresh_db_and_explicit_states() -> None:
    status, unit, analytics, db, risk = _data_health_fixture()
    result = MOD.evaluate_data_health(
        _window(), status=status, unit=unit, analytics=analytics,
        db_evidence=db, risk_guard=risk,
    )
    assert result["state"] == "PASS", result
    assert [item["id"] for item in result["evidence"]["selected_checks"]] == [
        "table:daily_reports:latest_date",
        "table:portfolio_positions:row_count",
        "performance:no_confirmed_picks_streak",
    ]

    stale = dict(db, mtime="2026-08-16T22:52:18Z")
    result = MOD.evaluate_data_health(
        _window(), status=status, unit=unit, analytics=analytics,
        db_evidence=stale, risk_guard=risk,
    )
    assert result["state"] == "FAIL"
    assert any("DuckDB mtime" in reason for reason in result["reasons"])

    broken_analytics = json.loads(json.dumps(analytics))
    broken_analytics["checks"][1].pop("availability")
    broken_analytics["checks"][2]["scan_state_counts"]["missing"] = 1
    result = MOD.evaluate_data_health(
        _window(), status=status, unit=unit, analytics=broken_analytics,
        db_evidence=db, risk_guard=risk,
    )
    assert result["state"] == "FAIL"
    assert len(result["reasons"]) == 2

    broken_analytics = json.loads(json.dumps(analytics))
    broken_analytics["checks"][2]["scan_state_counts"]["published_unclassified"] = 1
    result = MOD.evaluate_data_health(
        _window(), status=status, unit=unit, analytics=broken_analytics,
        db_evidence=db, risk_guard=risk,
    )
    assert result["state"] == "FAIL"
    assert "published EOD reports contain unclassified outcomes" in result["reasons"]

    live_fallback = json.loads(json.dumps(risk))
    live_fallback["data_sources"]["regime_as_of"] = None
    result = MOD.evaluate_data_health(
        _window(), status=status, unit=unit, analytics=analytics,
        db_evidence=db, risk_guard=live_fallback,
    )
    assert result["state"] == "PASS", result
    live_fallback["data_sources"]["regime_fallback_reason"] = None
    result = MOD.evaluate_data_health(
        _window(), status=status, unit=unit, analytics=analytics,
        db_evidence=db, risk_guard=live_fallback,
    )
    assert result["state"] == "FAIL"
    assert any("fallback provenance" in reason for reason in result["reasons"])


def test_stale_data_health_remains_pending() -> None:
    status, unit, analytics, db, risk = _data_health_fixture()
    status["started_at"] = "2026-08-14T22:15:01Z"
    result = MOD.evaluate_data_health(
        _window(), status=status, unit=unit, analytics=analytics,
        db_evidence=db, risk_guard=risk,
    )
    assert result["state"] == "PENDING"


def test_theme_flow_is_independently_fresh() -> None:
    status = {
        "status": "ready",
        "finished_at": "2026-08-17T23:45:14Z",
        "result": {"themes": 2},
    }
    unit = {"ActiveState": "inactive", "Result": "success", "ExecMainStatus": "0"}
    snapshot = {
        "as_of": "2026-08-17",
        "generated_at": "2026-08-17T23:45:13Z",
        "themes": [{"theme": "A"}, {"theme": "B"}],
    }
    result = MOD.evaluate_theme(_window(), status=status, unit=unit, snapshot=snapshot)
    assert result["state"] == "PASS", result
    status["status"] = "error"
    assert MOD.evaluate_theme(_window(), status=status, unit=unit, snapshot=snapshot)["state"] == "FAIL"


def test_eod_discovery_uses_job_identity_not_nominal_minute() -> None:
    runs = [
        {"id": 1, "created_at": "2026-08-17T22:46:00Z"},
        {"id": 2, "created_at": "2026-08-17T23:01:00Z"},
    ]
    jobs = {
        1: [{"name": "surge_scan", "status": "queued", "conclusion": None}],
        2: [{"name": "reversal_radar", "status": "completed", "conclusion": "success"}],
    }
    run, job = MOD.select_eod_run(_window(), runs, lambda run_id: jobs[run_id])
    assert run and run["id"] == 1
    assert job and job["name"] == "surge_scan"


def test_eod_contract_accepts_zero_picks_without_fabrication() -> None:
    run = {
        "id": 10,
        "status": "completed",
        "conclusion": "success",
        "created_at": "2026-08-17T22:46:00Z",
        "head_sha": "a" * 40,
    }
    job = {
        "id": 11,
        "name": "surge_scan",
        "status": "completed",
        "conclusion": "success",
        "started_at": "2026-08-17T23:45:00Z",
        "completed_at": "2026-08-18T00:35:00Z",
    }
    summary = {"report_date": "2026-08-17", "total_confirmed": 0, "ranked_picks": []}
    candidate = {
        "scan_date": "2026-08-17",
        "cohort_type": "bounded_top_n",
        "ranked_universe_count": 864,
        "scored_cohort_count": 25,
        "selection_method": "deterministic_top_n",
        "rank_limit": 25,
        "remaining_unscored": 0,
        "all_scored": [{"ticker": f"T{i}"} for i in range(25)],
    }
    result = MOD.evaluate_eod(
        _window(), run=run, job=job, required_base_sha="b" * 40,
        ancestry_status="ahead", summary=summary, candidate_snapshot=candidate,
        report_commits=[{"sha": "c" * 40}], candidate_commits=[{"sha": "c" * 40}],
    )
    assert result["state"] == "PASS", result
    summary["report_date"] = "2026-08-18"
    assert MOD.evaluate_eod(
        _window(), run=run, job=job, required_base_sha="b" * 40,
        ancestry_status="ahead", summary=summary, candidate_snapshot=candidate,
        report_commits=[{"sha": "c" * 40}], candidate_commits=[{"sha": "c" * 40}],
    )["state"] == "FAIL"


def test_github_json_file_accepts_wrapped_base64() -> None:
    raw = json.dumps({"report_date": "2026-08-17"}).encode()
    encoded = base64.encodebytes(raw).decode()

    class Client:
        def get(self, path: str, params: dict[str, str]):
            assert path.endswith("summary.json")
            assert params == {"ref": "main"}
            return {"encoding": "base64", "content": encoded}

    assert MOD.github_json_file(Client(), "reports/2026-08-17/summary.json") == {
        "report_date": "2026-08-17"
    }


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"natural validation observer tests: {len(tests)} passed")
