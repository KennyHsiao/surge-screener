#!/usr/bin/env python3
"""Atomic snapshot store for the Industry Roles review aggregate."""

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import re
import stat
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = 1
STATE_DIRECTORY = "industry_roles"
STATE_FILE = "review-state.json"
MAX_STATE_BYTES = 8 * 1024 * 1024
MAX_RECEIPTS = 256
MAX_AUDIT_ROWS = 1_000
LOCK_TIMEOUT_SECONDS = 0.5
_ETAG_RE = re.compile(r'^"r(?:0|[1-9][0-9]*)-[0-9a-f]{64}"$')
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")

Transform = Callable[[dict[str, Any], dict[str, Any]], tuple[dict[str, Any], dict[str, Any]]]
Failpoint = Callable[[str], None]


class ReviewStateError(RuntimeError):
    """Base class for bounded review-state failures."""


class StateInvalid(ReviewStateError):
    pass


class StateBusy(ReviewStateError):
    pass


class RevisionConflict(ReviewStateError):
    pass


class IdempotencyConflict(ReviewStateError):
    pass


@dataclass(frozen=True, slots=True)
class ReviewSnapshot:
    revision: int
    taxonomy_version: int
    updated_at: str | None
    overrides: dict[str, Any]
    suggestions: dict[str, Any]
    etag: str


@dataclass(frozen=True, slots=True)
class ReviewMutation:
    result: dict[str, Any]
    etag: str


@dataclass(frozen=True, slots=True)
class ReviewStateInspection:
    canonical_status: str
    canonical_revision: int | None
    canonical_etag: str | None
    backup_status: str
    backup_revision: int | None
    healthy: bool


@dataclass(frozen=True, slots=True)
class RestorePreview:
    backup_revision: int
    current_status: str
    current_etag: str | None
    proposed_revision: int
    proposed_etag: str


def canonical_state_path(reports_dir: Path | str) -> Path:
    return Path(reports_dir) / STATE_DIRECTORY / STATE_FILE


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _state_etag(
    revision: int,
    taxonomy_version: int,
    overrides: dict[str, Any],
    suggestions: dict[str, Any],
) -> str:
    digest = hashlib.sha256(
        _canonical_bytes(
            {
                "taxonomy_version": taxonomy_version,
                "overrides": overrides,
                "suggestions": suggestions,
            }
        )
    ).hexdigest()
    return f'"r{revision}-{digest}"'


def is_strong_etag(value: str) -> bool:
    return isinstance(value, str) and _ETAG_RE.fullmatch(value) is not None


def _read_regular_file(path: Path, maximum: int = MAX_STATE_BYTES) -> bytes | None:
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > maximum:
            os.close(descriptor)
            descriptor = None
            raise StateInvalid("state source is not a bounded regular file")
        handle = os.fdopen(descriptor, "rb")
        descriptor = None
        with handle:
            raw = handle.read(maximum + 1)
    except FileNotFoundError:
        if descriptor is not None:
            os.close(descriptor)
        if path.is_symlink():
            raise StateInvalid("state source is an unreadable link")
        return None
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        raise StateInvalid("state source is unreadable") from exc
    if len(raw) > maximum:
        raise StateInvalid("state source exceeds its size limit")
    return raw


def _valid_business_state(
    taxonomy_version: int,
    overrides: object,
    suggestions: object,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if isinstance(taxonomy_version, bool) or not isinstance(taxonomy_version, int):
        raise StateInvalid("invalid taxonomy version")
    if not isinstance(overrides, dict) or set(overrides) != {"version", "tickers"}:
        raise StateInvalid("invalid overrides")
    if overrides.get("version") != taxonomy_version or not isinstance(
        overrides.get("tickers"), dict
    ):
        raise StateInvalid("invalid overrides")
    if not isinstance(suggestions, dict) or set(suggestions) != {
        "generated_at",
        "suggestions",
    }:
        raise StateInvalid("invalid suggestions")
    if suggestions.get("generated_at") is not None and not isinstance(
        suggestions.get("generated_at"), str
    ):
        raise StateInvalid("invalid suggestions")
    rows = suggestions.get("suggestions")
    if not isinstance(rows, list) or len(rows) > 5_000:
        raise StateInvalid("invalid suggestions")
    if len(overrides["tickers"]) > 5_000:
        raise StateInvalid("invalid overrides")
    return copy.deepcopy(overrides), copy.deepcopy(suggestions)


def _decode_state(raw: bytes, taxonomy_version: int) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateInvalid("canonical state is not valid JSON") from exc
    required = {
        "schema_version",
        "revision",
        "taxonomy_version",
        "updated_at",
        "overrides",
        "suggestions",
        "receipts",
        "audit",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise StateInvalid("canonical state has an invalid shape")
    revision = payload.get("revision")
    if (
        payload.get("schema_version") != SCHEMA_VERSION
        or isinstance(revision, bool)
        or not isinstance(revision, int)
        or revision < 1
        or payload.get("taxonomy_version") != taxonomy_version
        or not isinstance(payload.get("updated_at"), str)
    ):
        raise StateInvalid("canonical state metadata is invalid")
    overrides, suggestions = _valid_business_state(
        taxonomy_version,
        payload.get("overrides"),
        payload.get("suggestions"),
    )
    receipts = payload.get("receipts")
    audit = payload.get("audit")
    if (
        not isinstance(receipts, list)
        or len(receipts) > MAX_RECEIPTS
        or not isinstance(audit, list)
        or len(audit) > MAX_AUDIT_ROWS
    ):
        raise StateInvalid("canonical histories are invalid")
    for receipt in receipts:
        if not isinstance(receipt, dict) or set(receipt) != {
            "key_hash",
            "request_hash",
            "etag",
            "result",
        }:
            raise StateInvalid("canonical receipt is invalid")
        result = receipt.get("result")
        if (
            _HASH_RE.fullmatch(str(receipt.get("key_hash") or "")) is None
            or _HASH_RE.fullmatch(str(receipt.get("request_hash") or "")) is None
            or not is_strong_etag(receipt.get("etag"))
            or not isinstance(result, dict)
            or set(result) != {
                "operator",
                "action",
                "ticker",
                "transactionId",
                "revision",
                "replayed",
            }
            or result.get("operator") != "operator"
            or result.get("action") not in {"generate", "approve", "reject", "defer"}
            or (result.get("ticker") is not None and not isinstance(result.get("ticker"), str))
            or isinstance(result.get("revision"), bool)
            or not isinstance(result.get("revision"), int)
            or not (1 <= result["revision"] <= revision)
            or result.get("replayed") is not False
        ):
            raise StateInvalid("canonical receipt is invalid")
        try:
            uuid.UUID(str(result.get("transactionId")))
        except (ValueError, AttributeError) as exc:
            raise StateInvalid("canonical receipt is invalid") from exc
        if not str(receipt["etag"]).startswith(f'"r{result["revision"]}-'):
            raise StateInvalid("canonical receipt revision is invalid")
    for row in audit:
        if not isinstance(row, dict) or set(row) != {
            "transaction_id",
            "action",
            "ticker",
            "revision",
            "committed_at",
            "request_hash",
        }:
            raise StateInvalid("canonical audit is invalid")
        if (
            row.get("action") not in {"generate", "approve", "reject", "defer", "restore"}
            or (row.get("ticker") is not None and not isinstance(row.get("ticker"), str))
            or isinstance(row.get("revision"), bool)
            or not isinstance(row.get("revision"), int)
            or not (1 <= row["revision"] <= revision)
            or not isinstance(row.get("committed_at"), str)
            or _HASH_RE.fullmatch(str(row.get("request_hash") or "")) is None
        ):
            raise StateInvalid("canonical audit is invalid")
        try:
            uuid.UUID(str(row.get("transaction_id")))
        except (ValueError, AttributeError) as exc:
            raise StateInvalid("canonical audit is invalid") from exc
    if not audit or audit[-1]["revision"] != revision:
        raise StateInvalid("canonical audit does not cover the current revision")
    payload["overrides"] = overrides
    payload["suggestions"] = suggestions
    return payload


def _snapshot(payload: dict[str, Any]) -> ReviewSnapshot:
    revision = payload["revision"]
    taxonomy_version = payload["taxonomy_version"]
    overrides = copy.deepcopy(payload["overrides"])
    suggestions = copy.deepcopy(payload["suggestions"])
    return ReviewSnapshot(
        revision=revision,
        taxonomy_version=taxonomy_version,
        updated_at=payload["updated_at"],
        overrides=overrides,
        suggestions=suggestions,
        etag=_state_etag(revision, taxonomy_version, overrides, suggestions),
    )


def _seed_state(
    taxonomy_version: int,
) -> dict[str, Any]:
    overrides, suggestions = _valid_business_state(
        taxonomy_version,
        {"version": taxonomy_version, "tickers": {}},
        {"generated_at": None, "suggestions": []},
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "revision": 0,
        "taxonomy_version": taxonomy_version,
        "updated_at": None,
        "overrides": overrides,
        "suggestions": suggestions,
        "receipts": [],
        "audit": [],
    }


def _load_state(
    state_path: Path,
    taxonomy_version: int,
) -> dict[str, Any]:
    raw = _read_regular_file(state_path)
    return (
        _seed_state(taxonomy_version)
        if raw is None
        else _decode_state(raw, taxonomy_version)
    )


def read_review_state(
    state_path: Path | str,
    taxonomy_version: int,
) -> ReviewSnapshot:
    """Read canonical state, or a side-effect-free empty revision-zero seed."""

    return _snapshot(_load_state(Path(state_path), taxonomy_version))


def _acquire_lock(state_path: Path) -> int:
    state_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = state_path.with_name(f"{state_path.name}.lock")
    try:
        descriptor = os.open(
            lock_path,
            os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
    except OSError as exc:
        raise StateBusy("review-state lock is unavailable") from exc
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise StateBusy("review-state lock is unavailable")
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return descriptor
        except BlockingIOError:
            if time.monotonic() >= deadline:
                os.close(descriptor)
                raise StateBusy("review-state lock acquisition timed out")
            time.sleep(0.01)


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write_bytes(
    path: Path,
    raw: bytes,
    *,
    failpoint: Failpoint | None = None,
) -> None:
    if len(raw) > MAX_STATE_BYTES:
        raise StateInvalid("canonical state exceeds its size limit")
    if path.is_symlink():
        raise StateInvalid("canonical state destination is a link")
    if path.exists() and not path.is_file():
        raise StateInvalid("canonical state destination is not a regular file")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        if failpoint is not None:
            failpoint("before_replace")
        os.replace(temporary, path)
        _fsync_directory(path.parent)
        if failpoint is not None:
            failpoint("after_replace")
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _write_state(
    state_path: Path,
    payload: dict[str, Any],
    *,
    previous_raw: bytes | None,
    failpoint: Failpoint | None,
) -> None:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8") + b"\n"
    if previous_raw is not None:
        _atomic_write_bytes(
            state_path.with_name(f"{state_path.name}.bak"),
            previous_raw,
        )
    _atomic_write_bytes(state_path, raw, failpoint=failpoint)


def _validate_key(value: str) -> None:
    if not isinstance(value, str) or not (16 <= len(value) <= 128):
        raise ValueError("invalid idempotency key")
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("invalid idempotency key") from exc
    if not all(0x21 <= byte <= 0x7E for byte in encoded):
        raise ValueError("invalid idempotency key")


def mutate_review_state(
    *,
    state_path: Path | str,
    taxonomy_version: int,
    expected_etag: str,
    idempotency_key: str,
    request: dict[str, Any],
    action: str,
    ticker: str | None,
    transform: Transform,
    now: str,
    transaction_id: str | None = None,
    failpoint: Failpoint | None = None,
) -> ReviewMutation:
    """Run one conditional transform and atomically commit its receipt and audit."""

    _validate_key(idempotency_key)
    if not is_strong_etag(expected_etag):
        raise RevisionConflict("a valid strong validator is required")
    if action not in {"generate", "approve", "reject", "defer"}:
        raise ValueError("invalid action")
    if not isinstance(request, dict):
        raise ValueError("invalid request")
    state_path = Path(state_path)
    lock_descriptor = _acquire_lock(state_path)
    try:
        previous_raw = _read_regular_file(state_path)
        state = (
            _seed_state(taxonomy_version)
            if previous_raw is None
            else _decode_state(previous_raw, taxonomy_version)
        )
        key_hash = hashlib.sha256(idempotency_key.encode("ascii")).hexdigest()
        request_hash = hashlib.sha256(_canonical_bytes(request)).hexdigest()
        for receipt in state["receipts"]:
            if receipt.get("key_hash") != key_hash:
                continue
            if receipt.get("request_hash") != request_hash:
                raise IdempotencyConflict("idempotency key was used for another request")
            stored_result = receipt.get("result")
            stored_etag = receipt.get("etag")
            if not isinstance(stored_result, dict) or not is_strong_etag(stored_etag):
                raise StateInvalid("idempotency receipt is invalid")
            replay = copy.deepcopy(stored_result)
            replay["replayed"] = True
            return ReviewMutation(replay, stored_etag)

        current = _snapshot(state)
        if expected_etag != current.etag:
            raise RevisionConflict("review state has changed")
        overrides, suggestions = transform(
            copy.deepcopy(current.overrides),
            copy.deepcopy(current.suggestions),
        )
        overrides, suggestions = _valid_business_state(
            taxonomy_version,
            overrides,
            suggestions,
        )
        revision = current.revision + 1
        try:
            transaction = str(uuid.UUID(transaction_id)) if transaction_id else str(uuid.uuid4())
        except (ValueError, AttributeError) as exc:
            raise ValueError("invalid transaction id") from exc
        result = {
            "operator": "operator",
            "action": action,
            "ticker": ticker,
            "transactionId": transaction,
            "revision": revision,
            "replayed": False,
        }
        etag = _state_etag(revision, taxonomy_version, overrides, suggestions)
        receipt = {
            "key_hash": key_hash,
            "request_hash": request_hash,
            "etag": etag,
            "result": copy.deepcopy(result),
        }
        audit_row = {
            "transaction_id": transaction,
            "action": action,
            "ticker": ticker,
            "revision": revision,
            "committed_at": now,
            "request_hash": request_hash,
        }
        committed = {
            "schema_version": SCHEMA_VERSION,
            "revision": revision,
            "taxonomy_version": taxonomy_version,
            "updated_at": now,
            "overrides": overrides,
            "suggestions": suggestions,
            "receipts": (state["receipts"] + [receipt])[-MAX_RECEIPTS:],
            "audit": (state["audit"] + [audit_row])[-MAX_AUDIT_ROWS:],
        }
        _write_state(
            state_path,
            committed,
            previous_raw=previous_raw,
            failpoint=failpoint,
        )
        return ReviewMutation(result, etag)
    finally:
        fcntl.flock(lock_descriptor, fcntl.LOCK_UN)
        os.close(lock_descriptor)


def _required_canonical_payload(
    state_path: Path,
    taxonomy_version: int,
) -> dict[str, Any]:
    raw = _read_regular_file(state_path)
    if raw is None:
        raise StateInvalid("canonical review state is missing")
    return _decode_state(raw, taxonomy_version)


def _inspect_snapshot_source(
    source_path: Path,
    taxonomy_version: int,
) -> tuple[str, ReviewSnapshot | None]:
    try:
        raw = _read_regular_file(source_path)
        if raw is None:
            return "missing", None
        return "valid", _snapshot(_decode_state(raw, taxonomy_version))
    except StateInvalid:
        return "invalid", None


def inspect_review_state(
    state_path: Path | str,
    *,
    taxonomy_version: int,
) -> ReviewStateInspection:
    """Inspect canonical and backup state without writing files."""

    state_path = Path(state_path)
    canonical_status, canonical = _inspect_snapshot_source(
        state_path,
        taxonomy_version,
    )
    backup_status, backup = _inspect_snapshot_source(
        state_path.with_name(f"{state_path.name}.bak"),
        taxonomy_version,
    )
    healthy = canonical_status != "invalid" and backup_status != "invalid"
    return ReviewStateInspection(
        canonical_status=canonical_status,
        canonical_revision=canonical.revision if canonical is not None else None,
        canonical_etag=canonical.etag if canonical is not None else None,
        backup_status=backup_status,
        backup_revision=backup.revision if backup is not None else None,
        healthy=healthy,
    )


def preview_restore_review_state_from_backup(
    state_path: Path | str,
    *,
    taxonomy_version: int,
) -> RestorePreview:
    """Validate the backup and calculate the next restore revision without writes."""

    state_path = Path(state_path)
    backup = _snapshot(
        _required_canonical_payload(
            state_path.with_name(f"{state_path.name}.bak"),
            taxonomy_version,
        )
    )
    current_revision = backup.revision
    current_status = "missing"
    current_etag: str | None = None
    try:
        current = _snapshot(_required_canonical_payload(state_path, taxonomy_version))
        current_revision = max(current_revision, current.revision)
        current_status = "valid"
        current_etag = current.etag
    except StateInvalid:
        if state_path.exists() or state_path.is_symlink():
            current_status = "invalid"
    proposed_revision = current_revision + 1
    return RestorePreview(
        backup_revision=backup.revision,
        current_status=current_status,
        current_etag=current_etag,
        proposed_revision=proposed_revision,
        proposed_etag=_state_etag(
            proposed_revision,
            taxonomy_version,
            backup.overrides,
            backup.suggestions,
        ),
    )


def restore_review_state_from_backup(
    state_path: Path | str,
    *,
    taxonomy_version: int,
    now: str,
    expected_etag: str | None,
    allow_invalid_current: bool = False,
    transaction_id: str | None = None,
) -> ReviewSnapshot:
    """Explicitly restore the last valid backup as a new audited revision."""

    state_path = Path(state_path)
    lock_descriptor = _acquire_lock(state_path)
    try:
        backup_path = state_path.with_name(f"{state_path.name}.bak")
        backup_raw = _read_regular_file(backup_path)
        if backup_raw is None:
            raise StateInvalid("review-state backup is missing")
        backup = _decode_state(backup_raw, taxonomy_version)
        current_revision = backup["revision"]
        previous_valid_raw: bytes | None = None
        current_raw = _read_regular_file(state_path)
        if current_raw is None:
            if not allow_invalid_current:
                raise RevisionConflict("current review state is missing")
        else:
            try:
                current = _snapshot(_decode_state(current_raw, taxonomy_version))
            except StateInvalid:
                if not allow_invalid_current:
                    raise
            else:
                if expected_etag != current.etag:
                    raise RevisionConflict("review state has changed")
                current_revision = max(current_revision, current.revision)
                previous_valid_raw = current_raw
        try:
            transaction = str(uuid.UUID(transaction_id)) if transaction_id else str(uuid.uuid4())
        except (ValueError, AttributeError) as exc:
            raise ValueError("invalid transaction id") from exc
        revision = current_revision + 1
        restored = copy.deepcopy(backup)
        restored["revision"] = revision
        restored["updated_at"] = now
        restored["audit"] = (
            restored["audit"]
            + [
                {
                    "transaction_id": transaction,
                    "action": "restore",
                    "ticker": None,
                    "revision": revision,
                    "committed_at": now,
                    "request_hash": hashlib.sha256(b"restore").hexdigest(),
                }
            ]
        )[-MAX_AUDIT_ROWS:]
        _write_state(
            state_path,
            restored,
            previous_raw=previous_valid_raw,
            failpoint=None,
        )
        return _snapshot(restored)
    finally:
        fcntl.flock(lock_descriptor, fcntl.LOCK_UN)
        os.close(lock_descriptor)
