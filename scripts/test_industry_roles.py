#!/usr/bin/env python3
"""Self-contained tests for industry-chain role classification.

Run:  .venv/bin/python scripts/test_industry_roles.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent))

import industry_roles as ir  # noqa: E402


def test_suggest_roles_from_theme_baskets():
    taxonomy = {
        "roles": {
            "ai_server_odm": {
                "name": "AI Server / ODM",
                "theme_baskets": ["AI 伺服器 / ODM"],
            }
        }
    }
    baskets = {"themes": {"AI 伺服器 / ODM": {"tickers": ["DELL", "SMCI"]}}}

    suggestions = ir.suggest_roles(["DELL"], taxonomy=taxonomy, theme_baskets=baskets)

    assert suggestions[0]["ticker"] == "DELL", suggestions
    assert suggestions[0]["suggested_primary_role"] == "ai_server_odm", suggestions
    assert suggestions[0]["status"] == "suggested", suggestions
    assert suggestions[0]["confidence"] >= 0.8, suggestions
    assert "theme_baskets: AI 伺服器 / ODM" in suggestions[0]["evidence"], suggestions


def test_approved_override_wins_over_suggestion():
    taxonomy = {
        "roles": {
            "ai_server_odm": {"name": "AI Server / ODM"},
            "hbm_memory": {"name": "HBM / Memory"},
        }
    }
    overrides = {
        "tickers": {
            "DELL": {
                "primary_role": "ai_server_odm",
                "secondary_roles": [],
                "confidence": 0.95,
            }
        }
    }
    suggestions = [{
        "ticker": "DELL",
        "suggested_primary_role": "hbm_memory",
        "suggested_secondary_roles": [],
        "confidence": 0.81,
        "status": "suggested",
    }]

    row = ir.resolve_role("DELL", taxonomy=taxonomy, overrides=overrides, suggestions=suggestions)

    assert row["source"] == "approved", row
    assert row["status"] == "approved", row
    assert row["primary_role"] == "ai_server_odm", row
    assert row["primary_role_name"] == "AI Server / ODM", row
    assert row["display_role"] == "AI Server / ODM", row


def test_resolve_role_always_returns_display_tag_and_status():
    taxonomy = {
        "roles": {
            "robotics": {"name": "Robotics"},
        }
    }
    suggested = ir.resolve_role(
        "OUST",
        taxonomy=taxonomy,
        overrides={"tickers": {}},
        suggestions=[{
            "ticker": "OUST",
            "suggested_primary_role": "robotics",
            "suggested_secondary_roles": [],
            "confidence": 0.86,
            "status": "suggested",
        }],
    )
    assert suggested["display_role"] == "待審核: Robotics", suggested
    assert suggested["source"] == "suggested", suggested
    assert suggested["status"] == "suggested", suggested

    unclassified = ir.resolve_role(
        "XYZ",
        taxonomy=taxonomy,
        overrides={"tickers": {}},
        suggestions=[],
    )
    assert unclassified["display_role"] == "未分類", unclassified
    assert unclassified["source"] == "unclassified", unclassified
    assert unclassified["status"] == "unclassified", unclassified


def test_approve_suggestion_persists_override_and_marks_reviewed():
    with TemporaryDirectory() as td:
        root = Path(td)
        content = root / "content"
        reports = root / "reports"
        content.mkdir()
        reports.mkdir()
        (content / "industry_roles.json").write_text(json.dumps({
            "roles": {"ai_server_odm": {"name": "AI Server / ODM"}}
        }), encoding="utf-8")
        (reports / "industry_role_suggestions.json").write_text(json.dumps({
            "suggestions": [{
                "ticker": "DELL",
                "suggested_primary_role": "ai_server_odm",
                "suggested_secondary_roles": [],
                "confidence": 0.84,
                "evidence": ["theme_baskets: AI 伺服器 / ODM"],
                "status": "suggested",
            }]
        }), encoding="utf-8")

        result = ir.review_suggestion("DELL", "approve", content_dir=content, reports_dir=reports)

        assert result["status"] == "approved", result
        overrides = json.loads((content / "industry_role_overrides.json").read_text(encoding="utf-8"))
        assert overrides["tickers"]["DELL"]["primary_role"] == "ai_server_odm", overrides
        suggestions = json.loads((reports / "industry_role_suggestions.json").read_text(encoding="utf-8"))
        assert suggestions["suggestions"][0]["status"] == "approved", suggestions


def test_reject_and_defer_do_not_persist_override():
    with TemporaryDirectory() as td:
        root = Path(td)
        content = root / "content"
        reports = root / "reports"
        content.mkdir()
        reports.mkdir()
        (content / "industry_roles.json").write_text(json.dumps({
            "roles": {"hbm_memory": {"name": "HBM / Memory"}}
        }), encoding="utf-8")
        (reports / "industry_role_suggestions.json").write_text(json.dumps({
            "suggestions": [
                {"ticker": "MU", "suggested_primary_role": "hbm_memory", "status": "suggested"},
                {"ticker": "WDC", "suggested_primary_role": "hbm_memory", "status": "suggested"},
            ]
        }), encoding="utf-8")

        rejected = ir.review_suggestion("MU", "reject", content_dir=content, reports_dir=reports)
        deferred = ir.review_suggestion("WDC", "defer", content_dir=content, reports_dir=reports)

        assert rejected["status"] == "rejected", rejected
        assert deferred["status"] == "deferred", deferred
        overrides = ir.load_overrides(content)
        assert overrides["tickers"] == {}, overrides


def test_generate_suggestions_writes_review_queue():
    with TemporaryDirectory() as td:
        root = Path(td)
        content = root / "content"
        reports = root / "reports"
        content.mkdir()
        reports.mkdir()
        (content / "industry_roles.json").write_text(json.dumps({
            "roles": {
                "semi_equipment": {
                    "name": "Semi Equipment",
                    "theme_baskets": ["半導體設備"],
                }
            }
        }), encoding="utf-8")
        (content / "theme_baskets.json").write_text(json.dumps({
            "themes": {"半導體設備": {"tickers": ["AMAT"]}}
        }), encoding="utf-8")

        payload = ir.generate_suggestions(["AMAT"], content_dir=content, reports_dir=reports)

        assert payload["suggestions"][0]["ticker"] == "AMAT", payload
        assert (reports / "industry_role_suggestions.json").exists()


def test_generate_suggestions_preserves_reviewed_statuses():
    with TemporaryDirectory() as td:
        root = Path(td)
        content = root / "content"
        reports = root / "reports"
        content.mkdir()
        reports.mkdir()
        (content / "industry_roles.json").write_text(json.dumps({
            "roles": {
                "hbm_memory": {
                    "name": "HBM / Memory",
                    "theme_baskets": ["Memory"],
                }
            }
        }), encoding="utf-8")
        (content / "theme_baskets.json").write_text(json.dumps({
            "themes": {"Memory": {"tickers": ["MU", "WDC"]}}
        }), encoding="utf-8")
        (reports / "industry_role_suggestions.json").write_text(json.dumps({
            "generated_at": "2026-01-01T00:00:00Z",
            "suggestions": [
                {
                    "ticker": "MU",
                    "suggested_primary_role": "hbm_memory",
                    "suggested_secondary_roles": [],
                    "confidence": 0.86,
                    "evidence": ["old evidence"],
                    "status": "rejected",
                    "reviewed_at": "2026-01-02T00:00:00Z",
                },
                {
                    "ticker": "WDC",
                    "suggested_primary_role": "hbm_memory",
                    "suggested_secondary_roles": [],
                    "confidence": 0.86,
                    "evidence": ["old evidence"],
                    "status": "deferred",
                    "reviewed_at": "2026-01-03T00:00:00Z",
                },
            ],
        }), encoding="utf-8")

        payload = ir.generate_suggestions(["MU", "WDC"], content_dir=content, reports_dir=reports)

        statuses = {s["ticker"]: s["status"] for s in payload["suggestions"]}
        reviewed_at = {s["ticker"]: s.get("reviewed_at") for s in payload["suggestions"]}
        assert statuses == {"MU": "rejected", "WDC": "deferred"}, payload
        assert reviewed_at == {
            "MU": "2026-01-02T00:00:00Z",
            "WDC": "2026-01-03T00:00:00Z",
        }, payload


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS {test.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {test.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {test.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
