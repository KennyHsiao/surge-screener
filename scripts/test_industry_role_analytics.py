#!/usr/bin/env python3
"""Self-contained tests for industry-role analytics snapshots.

Run:  .venv/bin/python scripts/test_industry_role_analytics.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent))

import industry_roles as ir  # noqa: E402


def test_build_and_write_role_assignment_snapshot() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        content = root / "content"
        reports = root / "reports"
        content.mkdir()
        reports.mkdir()
        (content / "industry_roles.json").write_text(json.dumps({
            "version": 3,
            "roles": {
                "advanced_packaging": {"name": "Advanced Packaging / OSAT"},
                "ai_server_odm": {"name": "AI Server / ODM"},
                "semi_equipment": {"name": "Semi Equipment"},
            },
        }), encoding="utf-8")
        (content / "industry_role_overrides.json").write_text(json.dumps({
            "version": 1,
            "tickers": {
                "DELL": {
                    "primary_role": "ai_server_odm",
                    "secondary_roles": ["semi_equipment"],
                    "confidence": 0.95,
                    "reviewed_at": "2026-07-01T01:00:00Z",
                    "evidence": ["manual review"],
                },
            },
        }), encoding="utf-8")
        (reports / "industry_role_suggestions.json").write_text(json.dumps({
            "generated_at": "2026-07-01T00:00:00Z",
            "suggestions": [
                {
                    "ticker": "FORM",
                    "suggested_primary_role": "advanced_packaging",
                    "suggested_secondary_roles": [],
                    "confidence": 0.86,
                    "evidence": ["theme_baskets: CoWoS / 先進封裝"],
                    "status": "suggested",
                },
                {
                    "ticker": "MU",
                    "suggested_primary_role": "semi_equipment",
                    "confidence": 0.8,
                    "evidence": ["old suggestion"],
                    "status": "rejected",
                },
            ],
        }), encoding="utf-8")

        snapshot = ir.build_role_assignment_snapshot(
            content_dir=content,
            reports_dir=reports,
            as_of_date="2026-07-01",
            generated_at="2026-07-01T02:00:00Z",
        )

        rows = {row["ticker"]: row for row in snapshot["rows"]}
        if set(rows) != {"DELL", "FORM"}:
            raise AssertionError(rows)
        if rows["DELL"]["status"] != "approved" or rows["DELL"]["source"] != "approved_override":
            raise AssertionError(rows["DELL"])
        if rows["DELL"]["primary_role_name"] != "AI Server / ODM":
            raise AssertionError(rows["DELL"])
        if json.loads(rows["DELL"]["secondary_role_ids_json"]) != ["semi_equipment"]:
            raise AssertionError(rows["DELL"])
        if rows["FORM"]["status"] != "suggested" or rows["FORM"]["source"] != "suggestion_engine":
            raise AssertionError(rows["FORM"])
        if rows["FORM"]["taxonomy_version"] != 3:
            raise AssertionError(rows["FORM"])

        out = ir.write_role_assignment_snapshot(snapshot, reports_dir=reports)
        latest = out.parent / "latest.json"
        if out.name != "2026-07-01.json" or not latest.is_file():
            raise AssertionError((out, latest))


def main() -> int:
    tests = [test_build_and_write_role_assignment_snapshot]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {test.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {test.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    if failed:
        return 1
    print("industry role analytics tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
