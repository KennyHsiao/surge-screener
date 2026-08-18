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
import os
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
    ("supplemental_refresh", "刷新其他自動資料"),
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


def _ranked_candidate_path() -> Path:
    output_dir = os.environ.get("SURGE_CANDIDATE_OUTPUT_DIR")
    if output_dir:
        return Path(output_dir) / "ranked_candidates.json"
    return REPO / "ranked_candidates.json"


def load_ranked_tickers(*, limit: int = 10, path: str | Path | None = None) -> list[str]:
    try:
        data = json.loads(Path(path or _ranked_candidate_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = data.get("ranked_candidates") if isinstance(data, dict) else []
    out: list[str] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper().lstrip("$")
        if ticker and ticker not in out:
            out.append(ticker)
        if len(out) >= max(0, int(limit)):
            break
    return out


def _supplement_step(name: str, fn) -> dict[str, Any]:
    try:
        return {"name": name, "status": "ok", "result": fn()}
    except Exception as e:  # noqa: BLE001 - one optional source must not block the remaining refreshes.
        return {"name": name, "status": "error", "error": str(e)}


def refresh_supplemental_artifacts(
    *,
    reports_root: str | Path | None = None,
    content_root: str | Path | None = None,
    ranked_tickers: list[str] | None = None,
    limit: int = 10,
    as_of_date: str | None = None,
    fundamental_metrics_module=None,
    sector_rotation_module=None,
    social_intelligence_module=None,
    social_outcomes_module=None,
    snapshot_iv_module=None,
    risk_guard_module=None,
) -> dict[str, Any]:
    """Refresh bounded, read-only datasets that should never require a UI click."""
    reports = Path(reports_root) if reports_root is not None else _default_reports_root()
    content = Path(content_root) if content_root is not None else _default_content_root()
    tickers = list(ranked_tickers or load_ranked_tickers(limit=limit))[:max(0, int(limit))]

    if fundamental_metrics_module is None:
        from scripts import fundamental_metrics_store as fundamental_metrics_module
    if sector_rotation_module is None:
        from scripts import sector_rotation as sector_rotation_module
    if social_intelligence_module is None:
        from scripts import social_intelligence as social_intelligence_module
    if social_outcomes_module is None:
        from scripts import social_intelligence_outcomes as social_outcomes_module
    if snapshot_iv_module is None:
        from scripts import snapshot_iv as snapshot_iv_module
    if risk_guard_module is None:
        from scripts import risk_guard as risk_guard_module

    steps: list[dict[str, Any]] = []
    if tickers:
        steps.append(_supplement_step(
            "fundamentals",
            lambda: fundamental_metrics_module.refresh_fundamental_metrics(
                tickers=tickers,
                reports_dir=reports,
                as_of_date=as_of_date,
            ),
        ))
    else:
        steps.append({"name": "fundamentals", "status": "skipped", "reason": "no ranked candidates"})

    def _sector_snapshot():
        result = sector_rotation_module.write_verified_rotation_snapshot(
            archive_dir=reports / "sector_rotation_snapshots",
        )
        if result.get("status") == "no_data":
            raise RuntimeError("sector rotation returned no usable data")
        return result

    steps.append(_supplement_step("sector_rotation", _sector_snapshot))
    steps.append(_supplement_step(
        "social_intelligence",
        lambda: social_intelligence_module.refresh_social_snapshot(
            market="US",
            as_of_date=as_of_date,
            reports_dir=reports,
            x_picks_path=reports / "x_influencer_picks.json",
            candidate_file=_ranked_candidate_path(),
            options_flow_path=reports / "options_flow" / "latest.json",
        ),
    ))
    steps.append(_supplement_step(
        "social_outcomes",
        lambda: social_outcomes_module.update_social_outcomes(
            snapshot_dir=reports / "social_intelligence",
            outcomes_dir=reports / "social_intelligence_outcomes",
            as_of_date=as_of_date,
        ),
    ))
    if tickers:
        steps.append(_supplement_step(
            "iv_history",
            lambda: snapshot_iv_module.refresh_iv_snapshots(tickers),
        ))
    else:
        steps.append({"name": "iv_history", "status": "skipped", "reason": "no ranked candidates"})

    def _risk_snapshot():
        risk_tickers = list(dict.fromkeys([
            *risk_guard_module.tickers_from_watchlist(),
            *tickers,
        ]))
        if not risk_tickers:
            raise RuntimeError("no watchlist or ranked tickers for Risk Guard")
        result = risk_guard_module.analyze_risk(
            risk_tickers,
            include_positions=(reports / "reconciliation.json").is_file(),
        )
        paths = risk_guard_module.write_report(result, reports / "risk_guard" / "latest.json")
        return {"tickers": len(risk_tickers), "paths": paths}

    steps.append(_supplement_step("risk_guard", _risk_snapshot))
    return {"tickers": tickers, "content_root": str(content), "steps": steps}


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
    include_supplemental: bool = False,
    supplemental_limit: int = 10,
    data_refresher=None,
    supplemental_refresher=None,
    analytics_store_module=None,
    analytics_checks_module=None,
    analytics_transaction_module=None,
    playbook_validation_module=None,
    continuation_strength_module=None,
    published_reports_root: str | Path | None = None,
    analytics_lock_path: str | Path | None = None,
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

    if analytics_transaction_module is None:
        try:
            from scripts import analytics_refresh_transaction
        except ImportError:
            import analytics_refresh_transaction  # type: ignore
        analytics_transaction_module = analytics_refresh_transaction

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
    published = (
        Path(published_reports_root)
        if published_reports_root is not None
        else Path(os.environ["SURGE_PUBLISHED_REPORTS_DIR"])
        if os.environ.get("SURGE_PUBLISHED_REPORTS_DIR")
        else None
    )
    lock_path = (
        Path(analytics_lock_path)
        if analytics_lock_path is not None
        else Path(os.environ["SURGE_ANALYTICS_LOCK"])
        if os.environ.get("SURGE_ANALYTICS_LOCK")
        else analytics.parent / "locks" / "analytics-refresh.lock"
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
            progress_pct=50,
            message=f"核心資料源刷新完成，處理 {ticker_count:,} 檔 ticker；狀態 {source_state}。",
            metrics={"tickers": ticker_count, "source_status": source_state},
        )
    supplemental_result: dict[str, Any] = {"tickers": [], "steps": []}
    supplemental_failure_count = 0
    if include_supplemental:
        if status is not None:
            status.update_stage(
                "supplemental_refresh",
                "刷新其他自動資料",
                progress_pct=55,
                message="更新基本面、板塊、社群、IV 歷史與 Risk Guard。",
            )
        supplemental_fn = supplemental_refresher or refresh_supplemental_artifacts
        try:
            supplemental_result = supplemental_fn(
                reports_root=reports,
                content_root=content,
                limit=supplemental_limit,
                as_of_date=as_of_date,
            )
        except Exception as e:  # noqa: BLE001 - Analytics must still rebuild and report the failure.
            supplemental_result = {
                "tickers": [],
                "steps": [{"name": "supplemental_orchestrator", "status": "error", "error": str(e)}],
            }
        supplemental_steps = supplemental_result.get("steps") if isinstance(supplemental_result, dict) else []
        supplemental_failures = [
            step for step in supplemental_steps
            if isinstance(step, dict) and step.get("status") == "error"
        ]
        supplemental_failure_count = len(supplemental_failures)
        if status is not None:
            status.update_stage(
                "supplemental_refresh",
                "刷新其他自動資料",
                status="failed" if supplemental_failures else "succeeded",
                progress_pct=72,
                message=(
                    f"其他自動資料完成，{len(supplemental_failures)} 個來源失敗。"
                    if supplemental_failures
                    else "其他自動資料刷新完成。"
                ),
                metrics={"supplemental_failures": supplemental_failure_count},
                warnings=[str(step.get("error")) for step in supplemental_failures],
            )
    elif status is not None:
        status.update_stage(
            "supplemental_refresh",
            "刷新其他自動資料",
            status="skipped",
            progress_pct=72,
            message="本次只刷新核心資料源。",
        )

    if status is not None:
        status.update_stage(
            "analytics_store",
            "重建 Analytics DB",
            progress_pct=78,
            message="將 reports 產物匯入 Analytics DuckDB。",
        )
    if status is not None:
        status.update_stage(
            "analytics_checks",
            "資料健康檢查",
            progress_pct=82,
            message="在 staging 產生 Analytics checks，通過後才提升新 DB。",
        )
    try:
        transaction = analytics_transaction_module.staged_analytics_refresh(
            reports_root=reports,
            published_reports_root=published,
            analytics_root=analytics,
            checks_output=checks_path,
            lock_path=lock_path,
            lock_timeout_seconds=3600,
            require_zero_block=False,
            analytics_store_module=analytics_store_module,
            analytics_checks_module=analytics_checks_module,
        )
    except Exception as e:  # noqa: BLE001
        if status is not None:
            status.fail(
                "analytics_store",
                "重建 Analytics DB",
                f"transactional Analytics refresh/check failed: {e}",
                metrics={"tickers": ticker_count},
            )
        raise
    tables = transaction["tables"]
    checks = transaction["checks"]
    table_rows = _table_rows(tables)
    if status is not None:
        status.update_stage(
            "analytics_store",
            "重建 Analytics DB",
            status="succeeded",
            progress_pct=90,
            message="Analytics DB 已通過 staging 並原子提升。",
            metrics={"tables": len(table_rows)},
        )
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
            message=(
                "核心與其他自動資料、Analytics DB、資料健康檢查與驗證報表已更新。"
                if include_supplemental
                else "核心資料源、Analytics DB、資料健康檢查與驗證報表已更新。"
            ),
            metrics={
                "tickers": ticker_count,
                "source_status": _source_status(source_result),
                "supplemental_failures": supplemental_failure_count,
                "playbook_validation_status": playbook_validation.get("status"),
                "continuation_strength_status": continuation_strength.get("status"),
                **checks_summary,
            },
            outputs={"checks": {"path": str(checks_path), "exists": checks_path.is_file()}},
        )
    return {
        "source_status": _source_status(source_result),
        "source": source_result,
        "supplemental": supplemental_result,
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
            "published_reports_root": str(published) if published is not None else None,
            "analytics_lock": str(lock_path),
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
    parser.add_argument("--published-reports-dir", default=None)
    parser.add_argument("--analytics-lock", default=None)
    parser.add_argument("--checks-output", default=None)
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--status-file", default=None)
    parser.add_argument("--include-supplemental", action="store_true")
    parser.add_argument("--supplemental-limit", type=int, default=10)
    parser.add_argument("--json", action="store_true", help="print full JSON result")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = refresh_core_sources_and_analytics(
        reports_root=args.reports_dir,
        content_root=args.content_dir,
        analytics_root=args.analytics_dir,
        published_reports_root=args.published_reports_dir,
        analytics_lock_path=args.analytics_lock,
        checks_output=args.checks_output,
        as_of_date=args.as_of_date,
        status_file=args.status_file,
        include_supplemental=args.include_supplemental,
        supplemental_limit=args.supplemental_limit,
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
