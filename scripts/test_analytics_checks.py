#!/usr/bin/env python3
"""Self-contained tests for analytics health and decision checks."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load_module(name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_store():
    return _load_module("analytics_store_for_checks_test", "scripts/analytics_store.py")


def _load_checks():
    return _load_module("analytics_checks_under_test", "scripts/analytics_checks.py")


def _write_reports(reports: Path) -> None:
    reports.mkdir()
    (reports / "performance_ledger.csv").write_text(
        "scan_date,ticker,verdict,composite_score,fwd_30d_return,hit_15pct_within_30d\n"
        "2026-06-01,NVDA,BUY,92,18,true\n"
        "2026-06-02,AMD,WATCH,76,-4,false\n",
        encoding="utf-8",
    )

    iv_dir = reports / "iv_history"
    iv_dir.mkdir()
    (iv_dir / "NVDA.json").write_text(
        json.dumps({"series": {"2026-06-01": 0.50, "2026-06-02": 0.55}}),
        encoding="utf-8",
    )

    options_dir = reports / "options_flow"
    options_dir.mkdir()
    for day, score, notional in (
        ("2026-06-01", 78, 1250000),
        ("2026-06-02", 91, 2200000),
    ):
        (options_dir / f"{day}.json").write_text(json.dumps({
            "as_of": day,
            "signals": [{
                "ticker": "NVDA",
                "direction": "bullish",
                "flow_score": score,
                "est_notional_usd": notional,
            }],
        }), encoding="utf-8")
    (options_dir / "latest.json").write_text(json.dumps({
        "as_of": "2026-06-02",
        "signals": [{"ticker": "SHOULD_NOT_LOAD", "flow_score": 100}],
    }), encoding="utf-8")

    reversal_dir = reports / "reversal_radar"
    reversal_dir.mkdir()
    for day, score in (("2026-06-01", 64), ("2026-06-02", 72)):
        (reversal_dir / f"scan_{day}.json").write_text(json.dumps({
            "as_of_date": day,
            "lane_id": "coiled-base",
            "exploratory": True,
            "candidates": [{
                "ticker": "AMD",
                "signal_date": day,
                "status": "TURNING",
                "reversal_score": score,
                "data_confidence": 92,
            }],
        }), encoding="utf-8")

    oversold_dir = reports / "oversold_reversal"
    oversold_dir.mkdir()
    (oversold_dir / "scan_2026-06-02.json").write_text(json.dumps({
        "as_of_date": "2026-06-02",
        "lane_id": "coiled-base",
        "exploratory": True,
        "candidates": [{
            "ticker": "TSLA",
            "signal_date": "2026-06-02",
            "rsi14": 44.2,
        }],
    }), encoding="utf-8")

    risk_dir = reports / "risk_guard"
    risk_dir.mkdir()
    for day, status, score in (
        ("2026-06-01", "REDUCE", 55),
        ("2026-06-02", "EXIT", 78),
    ):
        (risk_dir / f"{day}.json").write_text(json.dumps({
            "as_of": day,
            "generated_at": f"{day}T22:45:00Z",
            "market": {"status": "WATCH", "score": 32},
            "summary": {"count": 1, "high_risk": 1, "data_gaps": 0},
            "rows": [{
                "ticker": "NVDA",
                "status": status,
                "risk_score": score,
                "market_score": 8,
                "price_score": 20,
                "options_score": 12,
                "sector_score": 9,
                "position_score": 4,
                "cot_score": 1,
                "data_quality_score": 1,
                "primary_reasons": ["fixture high risk"],
                "data_gaps": [],
            }],
        }), encoding="utf-8")

    thesis_dir = reports / "market_thesis"
    thesis_dir.mkdir()
    (thesis_dir / "regime_only_forecast_2026-06-02.json").write_text(json.dumps({
        "as_of": "2026-06-02",
        "tier": 1,
        "method": "deterministic_baseline",
        "benchmark": "^GSPC",
        "direction": "bullish",
    }), encoding="utf-8")

    rankings_dir = reports / "candidate_rankings"
    rankings_dir.mkdir()
    (rankings_dir / "2026-06-02.json").write_text(json.dumps({
        "scan_date": "2026-06-02",
        "as_of_date": "2026-06-02",
        "universe": "sp1500",
        "rank_limit": 1,
        "ranked_candidates_count": 1,
        "ranked_candidates": [{
            "ticker": "NVDA",
            "rank_score": 88.0,
            "rank_bucket": "priority",
            "score_components": {"technical_trend": 25},
            "data_quality": {"status": "complete"},
        }],
    }), encoding="utf-8")

    (reports / "reconciliation.json").write_text(json.dumps({
        "as_of_date": "2026-06-02",
        "generated_at": "2026-06-02T22:10:00Z",
        "reachable": True,
        "matched": [{
            "ticker": "NVDA",
            "verdict": "BUY",
            "scan_date": "2026-06-01",
            "total_unrealized_pnl": -120.0,
            "legs": [{"secType": "STK", "qty": 2, "return_pct": -3.0, "unrealized_pnl": -120.0}],
        }],
        "ledger_not_held": [],
        "held_not_in_ledger": [],
    }), encoding="utf-8")

    run_dir = reports / "run_status"
    run_dir.mkdir()
    (run_dir / "candidates-local-history.jsonl").write_text(
        json.dumps({
            "run_id": "candidates-local-2026-06-02T22:00:00Z",
            "job": "candidates-local",
            "status": "succeeded",
            "started_at": "2026-06-02T22:00:00Z",
            "finished_at": "2026-06-02T22:08:00Z",
            "stage": {"id": "done", "label": "完成", "message": "Ranked top 50"},
            "metrics": {"ranked_candidates": 50, "options_watch": 10},
            "warnings": [],
            "errors": [],
        }) + "\n",
        encoding="utf-8",
    )


def test_missing_duckdb_blocks_today_signals() -> None:
    checks = _load_checks()
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "latest.json"

        result = checks.run_checks(
            analytics_root=Path(d) / "missing-analytics",
            output_path=out,
            today="2026-06-03",
        )

        if result["status"] != "BLOCK":
            raise AssertionError(result)
        if result["recommended_action"] != "BLOCK_TODAY_SIGNALS":
            raise AssertionError(result)
        if not out.is_file():
            raise AssertionError("checks output was not written")


def test_run_checks_publishes_health_and_signal_actions() -> None:
    store = _load_store()
    checks = _load_checks()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        reports = tmp / "reports"
        analytics_root = tmp / "analytics"
        out = tmp / "checks" / "latest.json"
        _write_reports(reports)
        store.refresh_all(reports_root=reports, analytics_root=analytics_root)

        result = checks.run_checks(
            analytics_root=analytics_root,
            output_path=out,
            today="2026-06-03",
        )
        loaded = json.loads(out.read_text(encoding="utf-8"))

        if loaded != result:
            raise AssertionError("written JSON does not match returned result")
        if result["status"] != "WARN":
            raise AssertionError(result)
        if result["summary"]["block"] != 0:
            raise AssertionError(result)
        table_checks = {c["id"]: c for c in result["checks"]}
        if table_checks["table:iv_history:row_count"]["status"] != "PASS":
            raise AssertionError(table_checks)
        if table_checks["table:candidate_scores:row_count"]["status"] != "WARN":
            raise AssertionError(table_checks)
        if table_checks["table:signal_outcomes:row_count"]["status"] != "WARN":
            raise AssertionError(table_checks)
        if table_checks["table:candidate_rankings:row_count"]["status"] != "PASS":
            raise AssertionError(table_checks)
        if table_checks["table:run_status_history:row_count"]["status"] != "PASS":
            raise AssertionError(table_checks)
        if table_checks["table:risk_guard_rows:row_count"]["status"] != "PASS":
            raise AssertionError(table_checks)
        if table_checks["table:portfolio_positions:row_count"]["status"] != "PASS":
            raise AssertionError(table_checks)
        if table_checks["table:options_flow_signals:no_latest_source"]["status"] != "PASS":
            raise AssertionError(table_checks)
        actions = {(s["category"], s["ticker"]): s["recommended_action"] for s in result["signals"]}
        if actions.get(("options_flow_repeats", "NVDA")) != "WATCHLIST_UPGRADE":
            raise AssertionError(result["signals"])
        if actions.get(("reversal_radar_repeats", "AMD")) != "REVIEW_REQUIRED":
            raise AssertionError(result["signals"])
        if actions.get(("risk_guard_repeats", "NVDA")) != "REVIEW_REQUIRED":
            raise AssertionError(result["signals"])
        if result["performance"]["status"] != "WARN":
            raise AssertionError(result["performance"])


def main() -> int:
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, test in tests:
        try:
            test()
            print(f"  PASS {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
