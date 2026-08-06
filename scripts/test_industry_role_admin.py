#!/usr/bin/env python3
"""Phase 7B-7D Industry Roles recovery CLI tests."""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent))

import industry_role_admin as admin  # noqa: E402
import industry_role_store as store  # noqa: E402


def _seed(root: Path) -> tuple[Path, Path]:
    content = root / "content"
    reports = root / "reports"
    content.mkdir(parents=True)
    reports.mkdir(parents=True)
    (content / "industry_roles.json").write_text(json.dumps({
        "version": 3,
        "roles": {"ai_accelerator": {"name": "AI Accelerator"}},
    }), encoding="utf-8")
    (content / "industry_role_overrides.json").write_text(json.dumps({
        "version": 3,
        "tickers": {},
    }), encoding="utf-8")
    (reports / "industry_role_suggestions.json").write_text(json.dumps({
        "generated_at": "2026-08-06T01:00:00Z",
        "suggestions": [{
            "ticker": "NVDA",
            "suggested_primary_role": "ai_accelerator",
            "status": "suggested",
        }],
    }), encoding="utf-8")
    return content, reports


def _commit(content: Path, reports: Path, *, second: bool = False) -> None:
    state_path = store.canonical_state_path(reports)
    legacy_overrides = json.loads(
        (content / "industry_role_overrides.json").read_text(encoding="utf-8")
    )
    legacy_suggestions = json.loads(
        (reports / "industry_role_suggestions.json").read_text(encoding="utf-8")
    )
    current = store.read_review_state(
        state_path,
        3,
        legacy_overrides,
        legacy_suggestions,
    )

    def transition(overrides: dict, suggestions: dict) -> tuple[dict, dict]:
        if second:
            suggestions["suggestions"][0]["status"] = "deferred"
        else:
            overrides["tickers"]["NVDA"] = {"primary_role": "ai_accelerator"}
            suggestions["suggestions"][0]["status"] = "approved"
        return overrides, suggestions

    store.mutate_review_state(
        state_path=state_path,
        taxonomy_version=3,
        legacy_overrides=legacy_overrides,
        legacy_suggestions=legacy_suggestions,
        expected_etag=current.etag,
        idempotency_key=(
            "admin-test-request-2222" if second else "admin-test-request-1111"
        ),
        request={
            "action": "defer" if second else "approve",
            "ticker": "NVDA",
        },
        action="defer" if second else "approve",
        ticker="NVDA",
        transform=transition,
        now="2026-08-06T03:00:00Z" if second else "2026-08-06T02:00:00Z",
    )


def _run(*arguments: str) -> tuple[int, dict]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = admin.main(list(arguments))
    return result, json.loads(output.getvalue())


def test_status_is_machine_readable_and_side_effect_free() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        content = root / "content"
        reports = root / "reports"
        content.mkdir()
        taxonomy_path = content / "industry_roles.json"
        taxonomy_path.write_text(json.dumps({
            "version": 3,
            "roles": {},
        }), encoding="utf-8")
        before = taxonomy_path.read_bytes()
        result, payload = _run(
            "--content-dir", str(content),
            "--reports-dir", str(reports),
            "status",
        )
        assert result == 0, payload
        assert payload["canonical"]["status"] == "missing", payload
        assert payload["healthy"] is True, payload
        assert taxonomy_path.read_bytes() == before
        assert sorted(content.iterdir()) == [taxonomy_path]
        assert not reports.exists()


def test_export_requires_explicit_apply_and_status_proves_current_hashes() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        content, reports = _seed(root)
        _commit(content, reports)
        legacy_before = (content / "industry_role_overrides.json").read_bytes()

        result, preview = _run(
            "--content-dir", str(content),
            "--reports-dir", str(reports),
            "export-legacy",
        )
        assert result == 0 and preview["applied"] is False, preview
        assert (content / "industry_role_overrides.json").read_bytes() == legacy_before
        assert not store.legacy_export_manifest_path(
            store.canonical_state_path(reports)
        ).exists()

        result, applied = _run(
            "--content-dir", str(content),
            "--reports-dir", str(reports),
            "export-legacy",
            "--apply",
        )
        assert result == 0 and applied["applied"] is True, applied
        result, status = _run(
            "--content-dir", str(content),
            "--reports-dir", str(reports),
            "status",
            "--require-canonical",
        )
        assert result == 0, status
        assert status["legacy_export"]["status"] == "current", status


def test_restore_preview_and_apply_are_separate_operations() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        content, reports = _seed(root)
        _commit(content, reports)
        _commit(content, reports, second=True)
        state_path = store.canonical_state_path(reports)
        before = state_path.read_bytes()

        result, preview = _run(
            "--content-dir", str(content),
            "--reports-dir", str(reports),
            "restore-backup",
        )
        assert result == 0 and preview["applied"] is False, preview
        assert preview["proposed_revision"] == 3, preview
        assert state_path.read_bytes() == before

        result, conflict = _run(
            "--content-dir", str(content),
            "--reports-dir", str(reports),
            "restore-backup",
            "--apply",
            "--expected-etag", '"r999-' + ("0" * 64) + '"',
        )
        assert result == 1 and conflict["error"] == "revision_conflict", conflict
        assert state_path.read_bytes() == before

        result, restored = _run(
            "--content-dir", str(content),
            "--reports-dir", str(reports),
            "restore-backup",
            "--apply",
            "--expected-etag", preview["current_etag"],
        )
        assert result == 0 and restored["applied"] is True, restored
        assert restored["revision"] == 3, restored


def test_invalid_canonical_returns_sanitized_nonzero_status() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        content, reports = _seed(root)
        state_path = store.canonical_state_path(reports)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text("{", encoding="utf-8")

        result, payload = _run(
            "--content-dir", str(content),
            "--reports-dir", str(reports),
            "status",
        )
        assert result == 1, payload
        assert payload["canonical"]["status"] == "invalid", payload
        assert "traceback" not in json.dumps(payload).lower()


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  FAIL {test.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
