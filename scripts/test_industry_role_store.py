#!/usr/bin/env python3
"""Phase 6Y-6Z transaction-store tests."""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent))

import industry_role_store as store  # noqa: E402


def _legacy() -> tuple[dict, dict]:
    return (
        {"version": 3, "tickers": {}},
        {
            "generated_at": "2026-08-06T01:02:03Z",
            "suggestions": [
                {
                    "ticker": "NVDA",
                    "suggested_primary_role": "ai_accelerator",
                    "suggested_primary_role_name": "AI Accelerator",
                    "suggested_secondary_roles": [],
                    "confidence": 0.9,
                    "evidence": ["theme_baskets: AI"],
                    "status": "suggested",
                }
            ],
        },
    )


def _approve(overrides: dict, suggestions: dict) -> tuple[dict, dict]:
    if not suggestions["suggestions"]:
        suggestions = _legacy()[1]
    overrides["tickers"]["NVDA"] = {
        "primary_role": "ai_accelerator",
        "secondary_roles": [],
        "confidence": 0.9,
        "reviewed_at": "2026-08-06T02:00:00Z",
    }
    suggestions["suggestions"][0]["status"] = "approved"
    suggestions["suggestions"][0]["reviewed_at"] = "2026-08-06T02:00:00Z"
    return overrides, suggestions


def _commit(
    path: Path,
    *,
    expected_etag: str,
    key: str = "request-key-0123456789",
    request: dict | None = None,
    failpoint=None,
) -> store.ReviewMutation:
    return store.mutate_review_state(
        state_path=path,
        taxonomy_version=3,
        expected_etag=expected_etag,
        idempotency_key=key,
        request=request
        or {
            "action": "approve",
            "ticker": "NVDA",
            "primaryRole": "ai_accelerator",
            "secondaryRoles": [],
        },
        action="approve",
        ticker="NVDA",
        transform=_approve,
        now="2026-08-06T02:00:00Z",
        transaction_id="00000000-0000-4000-8000-000000000001",
        failpoint=failpoint,
    )


def test_missing_canonical_is_side_effect_free_revision_zero() -> None:
    with TemporaryDirectory() as tmp:
        path = store.canonical_state_path(Path(tmp))
        snapshot = store.read_review_state(path, 3)
        assert snapshot.revision == 0, snapshot
        assert snapshot.overrides == {"version": 3, "tickers": {}}
        assert snapshot.suggestions == {"generated_at": None, "suggestions": []}
        assert snapshot.etag.startswith('"r0-') and snapshot.etag.endswith('"')
        assert not path.exists() and not path.parent.exists()


def test_commit_is_atomic_revisioned_and_durably_idempotent() -> None:
    with TemporaryDirectory() as tmp:
        path = store.canonical_state_path(Path(tmp))
        initial = store.read_review_state(path, 3)
        committed = _commit(path, expected_etag=initial.etag)
        assert committed.result["revision"] == 1 and not committed.result["replayed"]
        assert committed.etag != initial.etag
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["overrides"]["tickers"]["NVDA"]["primary_role"] == "ai_accelerator"
        assert payload["suggestions"]["suggestions"][0]["status"] == "approved"
        serialized = path.read_text(encoding="utf-8")
        assert "request-key-0123456789" not in serialized
        assert len(payload["receipts"]) == 1 and len(payload["audit"]) == 1

        replay = _commit(path, expected_etag=initial.etag)
        assert replay.result["replayed"] is True
        assert replay.result["transactionId"] == committed.result["transactionId"]
        assert replay.etag == committed.etag

        try:
            _commit(
                path,
                expected_etag=committed.etag,
                request={"action": "reject", "ticker": "NVDA"},
            )
        except store.IdempotencyConflict:
            pass
        else:
            raise AssertionError("idempotency key reuse with another request was accepted")


def test_stale_validator_and_concurrent_writers_lose_no_updates() -> None:
    with TemporaryDirectory() as tmp:
        path = store.canonical_state_path(Path(tmp))
        initial = store.read_review_state(path, 3)

        def worker(index: int) -> str:
            try:
                _commit(
                    path,
                    expected_etag=initial.etag,
                    key=f"concurrent-request-{index:02d}",
                )
            except store.RevisionConflict:
                return "conflict"
            return "committed"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = sorted(pool.map(worker, (1, 2)))
        assert outcomes == ["committed", "conflict"], outcomes
        assert store.read_review_state(path, 3).revision == 1


def test_failure_before_replace_preserves_old_and_after_replace_replays() -> None:
    with TemporaryDirectory() as tmp:
        path = store.canonical_state_path(Path(tmp))
        initial = store.read_review_state(path, 3)

        def before(stage: str) -> None:
            if stage == "before_replace":
                raise RuntimeError("injected")

        try:
            _commit(path, expected_etag=initial.etag, failpoint=before)
        except RuntimeError:
            pass
        else:
            raise AssertionError("before-replace failure was not injected")
        assert not path.exists()

        def after(stage: str) -> None:
            if stage == "after_replace":
                raise RuntimeError("ambiguous")

        try:
            _commit(path, expected_etag=initial.etag, failpoint=after)
        except RuntimeError:
            pass
        else:
            raise AssertionError("after-replace failure was not injected")
        assert store.read_review_state(path, 3).revision == 1
        replay = _commit(path, expected_etag=initial.etag)
        assert replay.result["replayed"] is True


def test_invalid_or_symlink_canonical_fails_closed() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = store.canonical_state_path(root)
        path.parent.mkdir(parents=True)
        path.write_text("{}", encoding="utf-8")
        try:
            store.read_review_state(path, 3)
        except store.StateInvalid:
            pass
        else:
            raise AssertionError("invalid canonical state fell back to legacy")
        path.unlink()
        target = root / "target.json"
        target.write_text("{}", encoding="utf-8")
        path.symlink_to(target)
        try:
            store.read_review_state(path, 3)
        except store.StateInvalid:
            pass
        else:
            raise AssertionError("symlink canonical state was followed")


def test_backup_restore_creates_a_new_audited_revision() -> None:
    with TemporaryDirectory() as tmp:
        path = store.canonical_state_path(Path(tmp))
        initial = store.read_review_state(path, 3)
        first = _commit(path, expected_etag=initial.etag)

        def defer(overrides: dict, suggestions: dict) -> tuple[dict, dict]:
            suggestions["suggestions"][0]["status"] = "deferred"
            return overrides, suggestions

        second = store.mutate_review_state(
            state_path=path,
            taxonomy_version=3,
            expected_etag=first.etag,
            idempotency_key="request-key-2222222222",
            request={"action": "defer", "ticker": "NVDA"},
            action="defer",
            ticker="NVDA",
            transform=defer,
            now="2026-08-06T03:00:00Z",
            transaction_id="00000000-0000-4000-8000-000000000002",
        )
        assert second.result["revision"] == 2
        path.write_text("{", encoding="utf-8")
        restored = store.restore_review_state_from_backup(
            path,
            taxonomy_version=3,
            now="2026-08-06T04:00:00Z",
            expected_etag=None,
            allow_invalid_current=True,
            transaction_id="00000000-0000-4000-8000-000000000003",
        )
        assert restored.revision == 2
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["audit"][-1]["action"] == "restore"
        assert payload["revision"] == 2


def test_status_is_side_effect_free_and_export_fields_are_absent() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        state_path = store.canonical_state_path(root / "reports")
        inspection = store.inspect_review_state(
            state_path,
            taxonomy_version=3,
        )
        assert inspection.canonical_status == "missing", inspection
        assert inspection.backup_status == "missing", inspection
        assert not hasattr(inspection, "export_status"), inspection
        assert inspection.healthy is True, inspection
        assert not (root / "reports").exists()
        assert not (root / "content").exists()


def test_restore_preview_matches_explicit_apply_without_writes() -> None:
    with TemporaryDirectory() as tmp:
        path = store.canonical_state_path(Path(tmp))
        initial = store.read_review_state(path, 3)
        first = _commit(path, expected_etag=initial.etag)

        def defer(overrides: dict, suggestions: dict) -> tuple[dict, dict]:
            suggestions["suggestions"][0]["status"] = "deferred"
            return overrides, suggestions

        store.mutate_review_state(
            state_path=path,
            taxonomy_version=3,
            expected_etag=first.etag,
            idempotency_key="request-key-3333333333",
            request={"action": "defer", "ticker": "NVDA"},
            action="defer",
            ticker="NVDA",
            transform=defer,
            now="2026-08-06T03:00:00Z",
            transaction_id="00000000-0000-4000-8000-000000000004",
        )
        before = path.read_bytes()
        preview = store.preview_restore_review_state_from_backup(
            path,
            taxonomy_version=3,
        )
        assert preview.backup_revision == 1
        assert preview.proposed_revision == 3
        assert preview.proposed_etag.startswith('"r3-')
        assert path.read_bytes() == before

        restored = store.restore_review_state_from_backup(
            path,
            taxonomy_version=3,
            now="2026-08-06T04:00:00Z",
            expected_etag=preview.current_etag,
            transaction_id="00000000-0000-4000-8000-000000000005",
        )
        assert restored.revision == preview.proposed_revision
        assert restored.etag == preview.proposed_etag
        backup = store.read_review_state(
            path.with_name(f"{path.name}.bak"),
            3,
        )
        assert backup.revision == 2
        assert backup.suggestions["suggestions"][0]["status"] == "deferred"


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
