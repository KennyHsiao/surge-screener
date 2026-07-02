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
