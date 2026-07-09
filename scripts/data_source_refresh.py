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


DATA_HEALTH_STAGES = [
    ("source_refresh", "刷新核心資料源"),
    ("analytics_store", "重建 Analytics DB"),
    ("analytics_checks", "資料健康檢查"),
    ("done", "完成"),
]


def default_status_path(reports_root: str | Path | None = None) -> Path:
    reports = Path(reports_root) if reports_root is not None else _default_reports_root()
    return reports / "run_status" / "data-health-refresh.json"


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


def _status_writer(path: str | Path | None):
    if path is None:
        return None
    try:
        from scripts.run_status import RunStatus
    except ImportError:
        from run_status import RunStatus  # type: ignore
    return RunStatus(path, job="data-health-refresh", stages=DATA_HEALTH_STAGES)


def _checks_metrics(checks: dict[str, Any]) -> dict[str, Any]:
    summary = checks.get("summary") if isinstance(checks.get("summary"), dict) else {}
    readiness = (
        checks.get("today_signal_readiness")
        if isinstance(checks.get("today_signal_readiness"), dict)
        else {}
    )
    return {
        "checks_status": checks.get("status"),
        "recommended_action": checks.get("recommended_action"),
        "warnings": int(summary.get("warn") or 0),
        "blockers": int(summary.get("block") or 0),
        "today_signal_can_publish": readiness.get("can_publish"),
        "today_signal_status": readiness.get("status"),
    }


def refresh_core_sources_and_analytics(
    *,
    reports_root: str | Path | None = None,
    content_root: str | Path | None = None,
    analytics_root: str | Path | None = None,
    checks_output: str | Path | None = None,
    as_of_date: str | None = None,
    status_file: str | Path | None = None,
    data_refresher=None,
    analytics_store_module=None,
    analytics_checks_module=None,
    playbook_validation_module=None,
    continuation_strength_module=None,
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

    if playbook_validation_module is None:
        try:
            from scripts import playbook_validation
        except ImportError:
            import playbook_validation  # type: ignore
        playbook_validation_module = playbook_validation

    if continuation_strength_module is None:
        try:
            from scripts import continuation_strength
        except ImportError:
            import continuation_strength  # type: ignore
        continuation_strength_module = continuation_strength

    analytics = (
        Path(analytics_root)
        if analytics_root is not None
        else Path(analytics_store_module.analytics_dir())
    )
    checks_path = Path(checks_output) if checks_output is not None else _default_checks_output(reports)
    checks_path.parent.mkdir(parents=True, exist_ok=True)
    status = _status_writer(status_file)
    if status is not None:
        status.start(outputs={"checks": {"path": str(checks_path), "exists": False}})
        status.update_stage(
            "source_refresh",
            "刷新核心資料源",
            progress_pct=5,
            message="刷新 universe / daily bars / money flow，可能需要 10-25 分鐘。",
        )

    try:
        source_result = data_refresher(
            reports_root=reports,
            content_root=content,
            as_of_date=as_of_date,
        )
    except Exception as e:  # noqa: BLE001 - checks should still publish the observable blocker.
        source_result = {
            "tickers": [],
            "steps": [
                {
                    "name": "source_orchestrator",
                    "status": "error",
                    "error": str(e),
                }
            ],
        }
    tickers = source_result.get("tickers") if isinstance(source_result, dict) else []
    ticker_count = len(tickers) if isinstance(tickers, list) else 0
    if status is not None:
        source_state = _source_status(source_result)
        status.update_stage(
            "source_refresh",
            "刷新核心資料源",
            status="succeeded" if source_state == "ok" else "failed",
            progress_pct=55,
            message=f"核心資料源刷新完成，處理 {ticker_count:,} 檔 ticker；狀態 {source_state}。",
            metrics={"tickers": ticker_count, "source_status": source_state},
        )
        status.update_stage(
            "analytics_store",
            "重建 Analytics DB",
            progress_pct=70,
            message="將 reports 產物匯入 Analytics DuckDB。",
        )
    try:
        tables = analytics_store_module.refresh_all(
            reports_root=reports,
            analytics_root=analytics,
        )
    except Exception as e:  # noqa: BLE001
        if status is not None:
            status.fail("analytics_store", "重建 Analytics DB", str(e), metrics={"tickers": ticker_count})
        raise
    table_rows = _table_rows(tables)
    if status is not None:
        status.update_stage(
            "analytics_store",
            "重建 Analytics DB",
            status="succeeded",
            progress_pct=85,
            message="Analytics DB 重建完成。",
            metrics={"tables": len(table_rows)},
        )
        status.update_stage(
            "analytics_checks",
            "資料健康檢查",
            progress_pct=92,
            message="產生 Analytics checks 與今日訊號發布狀態。",
        )
    try:
        checks = analytics_checks_module.run_checks(
            analytics_root=analytics,
            output_path=checks_path,
        )
    except Exception as e:  # noqa: BLE001
        if status is not None:
            status.fail(
                "analytics_checks",
                "資料健康檢查",
                str(e),
                metrics={"tickers": ticker_count, "tables": len(table_rows)},
            )
        raise
    checks_summary = _checks_metrics(checks)
    try:
        playbook_validation = playbook_validation_module.run_validation(
            decisions=reports / "playbook_decisions",
            output=reports / "playbook_validation" / "latest.json",
            min_resolved=100,
        )
    except Exception as e:  # noqa: BLE001 - validation lane must not break core refresh.
        playbook_validation = {
            "status": "blocked",
            "reason": f"playbook validation failed: {e}",
            "resolved": 0,
            "min_resolved": 100,
        }
    try:
        continuation_strength = continuation_strength_module.run_report(
            features=reports / "retrospective" / "surge_features.json",
            output=reports / "retrospective" / "continuation_strength.json",
            reports_dir=reports,
            analytics_dir=analytics,
            min_resolved=30,
        )
    except Exception as e:  # noqa: BLE001 - validation lane must not break core refresh.
        continuation_strength = {
            "status": "blocked",
            "reason": f"continuation validation failed: {e}",
            "resolved": 0,
            "min_resolved": 30,
        }
    if status is not None:
        status.update_stage(
            "analytics_checks",
            "資料健康檢查",
            status="succeeded",
            progress_pct=98,
            message=f"檢查完成：{checks.get('status')}。",
            metrics=checks_summary,
            outputs={"checks": {"path": str(checks_path), "exists": checks_path.is_file()}},
        )
        status.succeed(
            message="核心資料源、Analytics DB、資料健康檢查與驗證報表已更新。",
            metrics={
                "tickers": ticker_count,
                "source_status": _source_status(source_result),
                "playbook_validation_status": playbook_validation.get("status"),
                "continuation_strength_status": continuation_strength.get("status"),
                **checks_summary,
            },
            outputs={"checks": {"path": str(checks_path), "exists": checks_path.is_file()}},
        )
    return {
        "source_status": _source_status(source_result),
        "source": source_result,
        "tables": table_rows,
        "checks": {
            "status": checks.get("status"),
            "recommended_action": checks.get("recommended_action"),
            "warning_codes": checks.get("warning_codes", []),
        },
        "playbook_validation": {
            "status": playbook_validation.get("status"),
            "resolved": playbook_validation.get("resolved"),
            "min_resolved": playbook_validation.get("min_resolved"),
            "reason": playbook_validation.get("reason"),
        },
        "continuation_strength": {
            "status": continuation_strength.get("status"),
            "resolved": continuation_strength.get("resolved"),
            "min_resolved": continuation_strength.get("min_resolved"),
            "reason": continuation_strength.get("reason"),
        },
        "paths": {
            "reports_root": str(reports),
            "analytics_root": str(analytics),
            "checks_output": str(checks_path),
            "playbook_validation": str(reports / "playbook_validation" / "latest.json"),
            "continuation_strength": str(reports / "retrospective" / "continuation_strength.json"),
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh Data Health sources and Analytics DB")
    parser.add_argument("--reports-dir", default=str(_default_reports_root()))
    parser.add_argument("--content-dir", default=str(_default_content_root()))
    parser.add_argument("--analytics-dir", default=None)
    parser.add_argument("--checks-output", default=None)
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--status-file", default=None)
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
        status_file=args.status_file,
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
