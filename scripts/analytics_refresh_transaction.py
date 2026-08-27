#!/usr/bin/env python3
"""Transactional helpers for Analytics report ingestion.

The deployed release remains immutable.  A temporary overlay layers durable
published reports over that release, and a complete Analytics generation is
built and checked before it can replace the current materialized DuckDB.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator


UTC = timezone.utc
JOURNAL_SCHEMA_VERSION = 1
JOURNAL_FILENAME = "transaction.json"


class AnalyticsGateError(RuntimeError):
    """Raised when a staged Analytics generation fails its publication gate."""


class AnalyticsWriterLockTimeout(TimeoutError):
    """Raised only when the shared Analytics writer lock cannot be acquired."""


def iso_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_identity(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    stat = target.stat()
    return {
        "path": str(target),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": sha256_file(target),
    }


def _node_exists(path: Path) -> bool:
    return os.path.lexists(path)


def _link_node(source: Path, destination: Path) -> None:
    destination.symlink_to(source.resolve(), target_is_directory=source.is_dir())


def _merge_nodes(base: Path, published: Path, destination: Path) -> None:
    base_exists = _node_exists(base)
    published_exists = _node_exists(published)
    if not published_exists:
        if base_exists:
            _link_node(base, destination)
        return
    if not base_exists:
        _link_node(published, destination)
        return
    if base.is_dir() and published.is_dir():
        destination.mkdir()
        names = {item.name for item in base.iterdir()} | {item.name for item in published.iterdir()}
        for name in sorted(names):
            _merge_nodes(base / name, published / name, destination / name)
        return
    _link_node(published, destination)


@contextmanager
def report_overlay(
    reports_root: str | Path,
    published_reports_root: str | Path | None,
    *,
    temp_parent: str | Path | None = None,
) -> Iterator[Path]:
    """Yield a read-only union where published files override release files."""
    base = Path(reports_root).resolve()
    if published_reports_root is None:
        yield base
        return
    published = Path(published_reports_root)
    if not published.is_dir():
        yield base
        return
    parent = Path(temp_parent) if temp_parent is not None else base.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".reports-overlay-", dir=parent))
    for sibling_name in ("content", "ranked_candidates.json"):
        sibling = base.parent / sibling_name
        if _node_exists(sibling):
            _link_node(sibling, temporary / sibling_name)
    overlay = temporary / "reports"
    overlay.mkdir()
    try:
        names = {item.name for item in base.iterdir()} | {item.name for item in published.iterdir()}
        for name in sorted(names):
            _merge_nodes(base / name, published / name, overlay / name)
        yield overlay
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


@contextmanager
def analytics_writer_lock(
    lock_path: str | Path,
    *,
    timeout_seconds: float = 600,
) -> Iterator[Path]:
    """Serialize every writer that can replace Analytics materializations."""
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(0.0, float(timeout_seconds))
    with path.open("a+", encoding="utf-8") as handle:
        os.chmod(path, 0o600)
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise AnalyticsWriterLockTimeout(
                        f"Analytics writer lock timed out: {path}"
                    ) from None
                time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps({"pid": os.getpid(), "acquired_at": iso_utc()}) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        try:
            yield path
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        with source.open("rb") as source_handle:
            shutil.copyfileobj(source_handle, handle)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
        _fsync_directory(destination.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _backup_file_with_link_or_copy(source: Path, destination: Path) -> None:
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_tree(root: Path) -> None:
    directories: list[Path] = []
    for current, _names, files in os.walk(root):
        directory = Path(current)
        directories.append(directory)
        for name in files:
            path = directory / name
            if path.is_symlink():
                continue
            with path.open("rb") as handle:
                os.fsync(handle.fileno())
    for directory in reversed(directories):
        _fsync_directory(directory)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _remove_node(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def _remove_node_durable(path: Path) -> None:
    existed = _node_exists(path)
    _remove_node(path)
    if existed:
        _fsync_directory(path.parent)


def _journal_path(backup: Path) -> Path:
    return backup / JOURNAL_FILENAME


def _absolute_journal_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        raise RuntimeError(f"Analytics recovery journal has invalid {label}")
    return Path(value)


def _load_journal(backup: Path) -> dict[str, Any]:
    journal_path = _journal_path(backup)
    try:
        payload = json.loads(journal_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Analytics recovery journal is unreadable: {journal_path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != JOURNAL_SCHEMA_VERSION:
        raise RuntimeError(f"Analytics recovery journal schema is invalid: {journal_path}")
    if payload.get("state") not in {"preparing", "pending", "committed", "rolled_back"}:
        raise RuntimeError(f"Analytics recovery journal state is invalid: {journal_path}")
    analytics = payload.get("analytics")
    if not isinstance(analytics, dict):
        raise RuntimeError(f"Analytics recovery journal targets are invalid: {journal_path}")
    for key in ("target_db", "target_parquet", "checks_output"):
        _absolute_journal_path(analytics.get(key), key)
    for key in ("old_db", "old_parquet", "old_checks"):
        if type(analytics.get(key)) is not bool:
            raise RuntimeError(f"Analytics recovery journal has invalid {key}: {journal_path}")
    companion = payload.get("companion")
    if companion is not None:
        if not isinstance(companion, dict) or companion.get("kind") != "symlink":
            raise RuntimeError(f"Analytics recovery companion is invalid: {journal_path}")
        pointer = _absolute_journal_path(companion.get("pointer"), "companion pointer")
        promoted = _absolute_journal_path(
            companion.get("promoted_target"),
            "companion promoted target",
        )
        previous_value = companion.get("previous_target")
        previous = (
            _absolute_journal_path(previous_value, "companion previous target")
            if previous_value is not None
            else None
        )
        generations = pointer.parent / "generations"
        for target in (promoted, previous):
            if target is None:
                continue
            try:
                target.resolve().relative_to(generations.resolve())
            except ValueError:
                raise RuntimeError(
                    f"Analytics recovery companion target escapes generations: {journal_path}"
                ) from None
    failure_writes = payload.get("failure_writes", [])
    if not isinstance(failure_writes, list):
        raise RuntimeError(f"Analytics recovery failure writes are invalid: {journal_path}")
    for item in failure_writes:
        if not isinstance(item, dict) or not isinstance(item.get("payload"), dict):
            raise RuntimeError(f"Analytics recovery failure write is invalid: {journal_path}")
        _absolute_journal_path(item.get("path"), "failure-write path")
    return payload


def _replace_symlink(pointer: Path, target: Path) -> None:
    pointer.parent.mkdir(parents=True, exist_ok=True)
    temporary = pointer.parent / f".{pointer.name}.{os.getpid()}.{time.time_ns()}.tmp"
    temporary.symlink_to(os.path.relpath(target, pointer.parent), target_is_directory=True)
    try:
        os.replace(temporary, pointer)
        _fsync_directory(pointer.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_companion_state(journal: dict[str, Any]) -> None:
    companion = journal.get("companion")
    if not isinstance(companion, dict):
        return
    pointer = Path(companion["pointer"])
    previous = Path(companion["previous_target"]) if companion.get("previous_target") else None
    promoted = Path(companion["promoted_target"])
    if not _node_exists(pointer):
        return
    if not pointer.is_symlink():
        raise RuntimeError(f"Analytics recovery companion conflict: {pointer} is not a symlink")
    active = pointer.resolve()
    if previous is not None and active == previous.resolve():
        return
    if active != promoted.resolve():
        raise RuntimeError(f"Analytics recovery companion conflict at {pointer}: {active}")


def _restore_companion(journal: dict[str, Any]) -> None:
    companion = journal.get("companion")
    if not isinstance(companion, dict):
        return
    pointer = Path(companion["pointer"])
    previous = Path(companion["previous_target"]) if companion.get("previous_target") else None
    promoted = Path(companion["promoted_target"])
    if not _node_exists(pointer):
        if previous is not None:
            _replace_symlink(pointer, previous)
        return
    active = pointer.resolve()
    if previous is not None and active == previous.resolve():
        return
    if active != promoted.resolve():
        raise RuntimeError(f"Analytics recovery companion conflict at {pointer}: {active}")
    if previous is None:
        pointer.unlink()
        _fsync_directory(pointer.parent)
    else:
        _replace_symlink(pointer, previous)


def _restore_tree(backup_tree: Path, target: Path, backup: Path) -> None:
    temporary = backup / ".parquet-restore"
    _remove_node(temporary)
    shutil.copytree(backup_tree, temporary)
    _fsync_tree(temporary)
    _remove_node(target)
    os.replace(temporary, target)
    _fsync_directory(target.parent)


def _restore_analytics(backup: Path, journal: dict[str, Any]) -> None:
    analytics = journal["analytics"]
    target_db = Path(analytics["target_db"])
    target_parquet = Path(analytics["target_parquet"])
    checks_output = Path(analytics["checks_output"])
    backup_db = backup / "analytics.duckdb"
    backup_parquet = backup / "parquet"
    backup_checks = backup / "analytics-checks.json"

    if analytics["old_db"]:
        if not backup_db.is_file():
            raise RuntimeError(f"Analytics database backup is missing: {backup_db}")
        _atomic_copy(backup_db, target_db)
    else:
        _remove_node_durable(target_db)
    if analytics["old_checks"]:
        if not backup_checks.is_file():
            raise RuntimeError(f"Analytics checks backup is missing: {backup_checks}")
        _atomic_copy(backup_checks, checks_output)
    else:
        _remove_node_durable(checks_output)
    if analytics["old_parquet"]:
        if not backup_parquet.is_dir():
            raise RuntimeError(f"Analytics Parquet backup is missing: {backup_parquet}")
        _restore_tree(backup_parquet, target_parquet, backup)
    else:
        _remove_node_durable(target_parquet)


def _publish_recovery_failures(journal: dict[str, Any]) -> None:
    for item in journal.get("failure_writes", []):
        payload = dict(item["payload"])
        if "captured_at" in payload:
            payload["captured_at"] = iso_utc()
        _atomic_write_json(Path(item["path"]), payload)


def _recover_pending_backup(
    backup: Path,
    journal: dict[str, Any],
    *,
    publish_failure_evidence: bool,
    cleanup: bool,
) -> None:
    _validate_companion_state(journal)
    _restore_analytics(backup, journal)
    _restore_companion(journal)
    if publish_failure_evidence:
        _publish_recovery_failures(journal)
    if cleanup:
        journal["state"] = "rolled_back"
        journal["rolled_back_at"] = iso_utc()
        _atomic_write_json(_journal_path(backup), journal)
        _cleanup_backup_durable(backup)


def _cleanup_backup_durable(backup: Path) -> None:
    cleanup = backup.parent / backup.name.replace(
        ".analytics-backup-",
        ".analytics-cleanup-",
        1,
    )
    os.replace(backup, cleanup)
    _fsync_directory(cleanup.parent)
    shutil.rmtree(cleanup, ignore_errors=True)
    _fsync_directory(cleanup.parent)


def _cleanup_pretransaction_residue(parent: Path) -> None:
    for prefix in (
        ".analytics-staging-*",
        ".analytics-preparing-*",
        ".analytics-cleanup-*",
    ):
        for path in sorted(parent.glob(prefix)):
            shutil.rmtree(path)
            _fsync_directory(parent)


def recover_pending_analytics_promotions_locked(
    analytics_root: str | Path,
) -> list[dict[str, Any]]:
    """Recover abandoned promotions while the caller owns the writer lock."""
    analytics = Path(analytics_root).resolve()
    recovered: list[dict[str, Any]] = []
    _cleanup_pretransaction_residue(analytics.parent)
    for backup in sorted(analytics.parent.glob(".analytics-backup-*")):
        journal_path = _journal_path(backup)
        if not journal_path.is_file():
            raise RuntimeError(
                f"Analytics recovery journal is missing; backup retained: {journal_path}"
            )
        journal = _load_journal(backup)
        target_db = Path(journal["analytics"]["target_db"]).resolve()
        if target_db.parent != analytics:
            raise RuntimeError(
                f"Analytics recovery journal targets another root: {journal_path}: {target_db.parent}"
            )
        if journal["state"] == "preparing":
            shutil.rmtree(backup)
            _fsync_directory(backup.parent)
            continue
        if journal["state"] in {"committed", "rolled_back"}:
            _cleanup_backup_durable(backup)
            continue
        _recover_pending_backup(
            backup,
            journal,
            publish_failure_evidence=True,
            cleanup=True,
        )
        recovered.append({
            "backup": str(backup),
            "recovered_at": iso_utc(),
            "companion": journal.get("companion"),
            "failure_evidence_published": bool(journal.get("failure_writes")),
        })
    return recovered


def commit_pending_analytics_promotion_locked(
    analytics_root: str | Path,
    backup_path: str | Path,
) -> None:
    """Commit one exact provisional promotion left by a bounded worker.

    The caller must own the shared Analytics writer lock.  This validates the
    journal and companion pointer before making the durable commit marker.
    """
    analytics = Path(analytics_root).resolve()
    backup = Path(backup_path).resolve()
    if backup.parent != analytics.parent or not backup.name.startswith(
        ".analytics-backup-"
    ):
        raise RuntimeError("provisional Analytics backup is outside the expected root")
    journal = _load_journal(backup)
    if journal.get("state") != "pending":
        raise RuntimeError(
            f"provisional Analytics promotion is not pending: {journal.get('state')}"
        )
    target_db = Path(journal["analytics"]["target_db"]).resolve()
    target_parquet = Path(journal["analytics"]["target_parquet"]).resolve()
    checks_output = Path(journal["analytics"]["checks_output"]).resolve()
    if (
        target_db.parent != analytics
        or target_db != analytics / "analytics.duckdb"
        or target_parquet != analytics / "parquet"
        or not target_db.is_file()
        or not target_parquet.is_dir()
        or not checks_output.is_file()
    ):
        raise RuntimeError("provisional Analytics targets are incomplete or inconsistent")
    companion = journal.get("companion")
    if isinstance(companion, dict):
        pointer = Path(companion["pointer"])
        promoted = Path(companion["promoted_target"])
        if not pointer.is_symlink() or pointer.resolve() != promoted.resolve():
            raise RuntimeError("provisional Analytics companion is not promoted")
    promotion = AnalyticsPromotion(
        backup=backup,
        has_durable_companion=isinstance(companion, dict),
    )
    promotion.commit()


@dataclass
class AnalyticsPromotion:
    """A promoted Analytics generation whose old outputs remain recoverable."""

    backup: Path
    has_durable_companion: bool
    _state: str = field(default="pending", init=False)

    def commit(self) -> None:
        if self._state != "pending":
            raise RuntimeError(f"Analytics promotion is already {self._state}")
        journal = _load_journal(self.backup)
        if journal["state"] != "pending":
            raise RuntimeError(
                f"Analytics promotion journal cannot commit from {journal['state']}"
            )
        journal["state"] = "committed"
        journal["committed_at"] = iso_utc()
        _atomic_write_json(_journal_path(self.backup), journal)
        self._state = "committed"
        try:
            _cleanup_backup_durable(self.backup)
        except OSError:
            # The committed marker is authoritative. A later lock owner cleans
            # committed residue without rolling the promoted generation back.
            pass

    def rollback(self, companion_rollback: Callable[[], None] | None = None) -> None:
        if self._state == "rolled_back":
            return
        if self._state != "pending":
            raise RuntimeError(f"Analytics promotion cannot roll back after {self._state}")

        rollback_errors: list[str] = []
        try:
            journal = _load_journal(self.backup)
            _recover_pending_backup(
                self.backup,
                journal,
                publish_failure_evidence=False,
                cleanup=False,
            )
        except Exception as exc:  # noqa: BLE001 - retain every rollback failure.
            rollback_errors.append(f"durable state: {type(exc).__name__}: {exc}")
        if companion_rollback is not None and not self.has_durable_companion:
            try:
                companion_rollback()
            except Exception as exc:  # noqa: BLE001 - retain every rollback failure.
                rollback_errors.append(f"companion: {type(exc).__name__}: {exc}")

        if rollback_errors:
            self._state = "rollback_failed"
            raise RuntimeError(
                "Analytics rollback was incomplete; "
                f"backup retained at {self.backup}: {'; '.join(rollback_errors)}"
            )
        journal = _load_journal(self.backup)
        journal["state"] = "rolled_back"
        journal["rolled_back_at"] = iso_utc()
        _atomic_write_json(_journal_path(self.backup), journal)
        self._state = "rolled_back"
        _cleanup_backup_durable(self.backup)


@dataclass
class AnalyticsRefreshTransaction:
    """Combine provisional Analytics and companion state under one lifecycle."""

    evidence: dict[str, Any]
    analytics_promotion: AnalyticsPromotion
    companion_rollback: Callable[[], None] | None = None
    _state: str = field(default="pending", init=False)

    def __enter__(self) -> "AnalyticsRefreshTransaction":
        return self

    def __exit__(self, _exc_type, exc, _traceback) -> bool:
        if self._state != "pending":
            return False
        try:
            self.rollback()
        except Exception as rollback_error:
            if exc is not None:
                raise RuntimeError(
                    "Analytics transaction failed and rollback was incomplete: "
                    f"{type(exc).__name__}: {exc}; "
                    f"{type(rollback_error).__name__}: {rollback_error}"
                ) from rollback_error
            raise
        if exc is None:
            raise RuntimeError("Analytics transaction exited without commit")
        return False

    def commit(self) -> None:
        if self._state != "pending":
            raise RuntimeError(f"Analytics transaction is already {self._state}")
        self.analytics_promotion.commit()
        self._state = "committed"

    def rollback(self) -> None:
        if self._state == "rolled_back":
            return
        if self._state != "pending":
            raise RuntimeError(f"Analytics transaction cannot roll back after {self._state}")

        rollback_errors: list[str] = []
        try:
            self.analytics_promotion.rollback(self.companion_rollback)
        except Exception as exc:  # noqa: BLE001 - companion rollback must still run.
            rollback_errors.append(f"analytics: {type(exc).__name__}: {exc}")
        if rollback_errors:
            self._state = "rollback_failed"
            raise RuntimeError(
                "Analytics transaction rollback was incomplete: " + "; ".join(rollback_errors)
            )
        self._state = "rolled_back"


def _promote_generation(
    staging: Path,
    target: Path,
    checks: Path,
    checks_output: Path,
    *,
    promote_companion: Callable[[], Callable[[], None] | None] | None,
    recovery_context: dict[str, Any] | None,
) -> tuple[AnalyticsPromotion, Callable[[], None] | None]:
    target.mkdir(parents=True, exist_ok=True)
    staged_db = staging / "analytics.duckdb"
    staged_parquet = staging / "parquet"
    if not staged_db.is_file() or not staged_parquet.is_dir():
        raise AnalyticsGateError("staged Analytics generation is incomplete")

    preparing = Path(tempfile.mkdtemp(prefix=".analytics-preparing-", dir=target.parent))
    os.chmod(preparing, 0o700)
    target_db = target / "analytics.duckdb"
    target_parquet = target / "parquet"
    backup_db = preparing / "analytics.duckdb"
    backup_parquet = preparing / "parquet"
    backup_checks = preparing / "analytics-checks.json"
    old_db = target_db.is_file()
    old_parquet = target_parquet.is_dir()
    old_checks = checks_output.is_file()
    context = dict(recovery_context or {})
    journal = {
        "schema_version": JOURNAL_SCHEMA_VERSION,
        "state": "preparing",
        "created_at": iso_utc(),
        "analytics": {
            "target_db": str(target_db),
            "target_parquet": str(target_parquet),
            "checks_output": str(checks_output),
            "old_db": old_db,
            "old_parquet": old_parquet,
            "old_checks": old_checks,
        },
        "companion": context.get("companion"),
        "failure_writes": context.get("failure_writes", []),
    }
    _atomic_write_json(_journal_path(preparing), journal)
    backup = preparing.parent / preparing.name.replace(
        ".analytics-preparing-",
        ".analytics-backup-",
        1,
    )
    os.replace(preparing, backup)
    _fsync_directory(backup.parent)
    backup_db = backup / "analytics.duckdb"
    backup_parquet = backup / "parquet"
    backup_checks = backup / "analytics-checks.json"
    promotion = AnalyticsPromotion(
        backup=backup,
        has_durable_companion=isinstance(journal.get("companion"), dict),
    )
    companion_rollback: Callable[[], None] | None = None
    try:
        if old_db:
            _backup_file_with_link_or_copy(target_db, backup_db)
        if old_checks:
            _backup_file_with_link_or_copy(checks_output, backup_checks)
        if old_parquet:
            shutil.copytree(target_parquet, backup_parquet)
        _fsync_tree(backup)
        journal["state"] = "pending"
        journal["prepared_at"] = iso_utc()
        _atomic_write_json(_journal_path(backup), journal)

        companion_rollback = promote_companion() if promote_companion is not None else None
        if old_parquet:
            _remove_node_durable(target_parquet)
        os.replace(staged_parquet, target_parquet)
        _fsync_directory(target_parquet.parent)
        _atomic_copy(checks, checks_output)
        # DuckDB finishes the provisional data promotion. The caller retains
        # this rollback handle until all later transaction evidence is durable.
        os.replace(staged_db, target_db)
        _fsync_directory(target_db.parent)
    except Exception as promotion_error:
        try:
            journal_state = _load_journal(backup)["state"]
            if journal_state == "preparing":
                _cleanup_backup_durable(backup)
            else:
                promotion.rollback(companion_rollback)
        except Exception as rollback_error:
            raise RuntimeError(
                "Analytics promotion failed and rollback was incomplete; "
                f"{type(promotion_error).__name__}: {promotion_error}; "
                f"{type(rollback_error).__name__}: {rollback_error}"
            ) from rollback_error
        raise
    return promotion, companion_rollback


def _analytics_modules(analytics_store_module, analytics_checks_module):
    if analytics_store_module is None:
        try:
            from scripts import analytics_store as analytics_store_module
        except ImportError:
            import analytics_store as analytics_store_module  # type: ignore
    if analytics_checks_module is None:
        try:
            from scripts import analytics_checks as analytics_checks_module
        except ImportError:
            import analytics_checks as analytics_checks_module  # type: ignore
    return analytics_store_module, analytics_checks_module


def canonicalize_analytics_provenance(
    value: Any,
    *,
    staged_root: Path,
    canonical_root: Path,
) -> Any:
    """Rewrite staged path evidence to the durable promoted Analytics root."""
    staged = str(staged_root.resolve())
    canonical = str(canonical_root.resolve())
    if isinstance(value, dict):
        return {
            key: canonicalize_analytics_provenance(
                item,
                staged_root=staged_root,
                canonical_root=canonical_root,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            canonicalize_analytics_provenance(
                item,
                staged_root=staged_root,
                canonical_root=canonical_root,
            )
            for item in value
        ]
    if isinstance(value, str):
        return value.replace(staged, canonical)
    return value


def staged_analytics_refresh_transaction_locked(
    *,
    reports_root: str | Path,
    published_reports_root: str | Path | None,
    analytics_root: str | Path,
    checks_output: str | Path,
    analytics_store_module=None,
    analytics_checks_module=None,
    require_zero_block: bool = True,
    gate_validator: Callable[[dict[str, Any], dict[str, Any]], None] | None = None,
    promote_companion: Callable[[], Callable[[], None] | None] | None = None,
    recovery_context: dict[str, Any] | None = None,
) -> AnalyticsRefreshTransaction:
    """Build, gate, and provisionally promote under the caller-owned lock.

    ``promote_companion`` runs only after every Analytics gate passes and after
    a durable pending journal exists. It must return a rollback callback when
    it changes companion state. The returned transaction retains every
    rollback backup until the caller durably commits it.
    """
    analytics_store_module, analytics_checks_module = _analytics_modules(
        analytics_store_module,
        analytics_checks_module,
    )

    analytics = Path(analytics_root).resolve()
    output = Path(checks_output).resolve()
    analytics.parent.mkdir(parents=True, exist_ok=True)
    recover_pending_analytics_promotions_locked(analytics)
    staging = Path(tempfile.mkdtemp(prefix=".analytics-staging-", dir=analytics.parent))
    staged_checks = staging / ".analytics-checks.json"
    try:
        with report_overlay(
            reports_root,
            published_reports_root,
            temp_parent=analytics.parent,
        ) as effective_reports:
            tables = analytics_store_module.refresh_all(
                reports_root=effective_reports,
                analytics_root=staging,
            )
        checks = analytics_checks_module.run_checks(
            analytics_root=staging,
            output_path=staged_checks,
        )
        summary = checks.get("summary") if isinstance(checks, dict) else None
        blockers = summary.get("block") if isinstance(summary, dict) else None
        if require_zero_block and blockers != 0:
            raise AnalyticsGateError(f"staged Analytics has non-zero or unknown blockers: {blockers!r}")
        if gate_validator is not None:
            gate_validator(checks, tables)
        checks = canonicalize_analytics_provenance(
            checks,
            staged_root=staging,
            canonical_root=analytics,
        )
        staged_checks.parent.mkdir(parents=True, exist_ok=True)
        staged_checks.write_text(
            json.dumps(checks, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        # Compute all return evidence before changing durable state. Once the
        # database commit point succeeds, returning cannot expose a new failure.
        database = file_identity(staging / "analytics.duckdb")
        database["path"] = str(analytics / "analytics.duckdb")
        promoted_at = iso_utc()
        analytics_promotion, companion_rollback = _promote_generation(
            staging,
            analytics,
            staged_checks,
            output,
            promote_companion=promote_companion,
            recovery_context=recovery_context,
        )
        return AnalyticsRefreshTransaction(
            evidence={
                "tables": tables,
                "checks": checks,
                "database": database,
                "promoted_at": promoted_at,
            },
            analytics_promotion=analytics_promotion,
            companion_rollback=companion_rollback,
        )
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def staged_analytics_refresh_locked(
    *,
    reports_root: str | Path,
    published_reports_root: str | Path | None,
    analytics_root: str | Path,
    checks_output: str | Path,
    analytics_store_module=None,
    analytics_checks_module=None,
    require_zero_block: bool = True,
    gate_validator: Callable[[dict[str, Any], dict[str, Any]], None] | None = None,
    promote_companion: Callable[[], Callable[[], None] | None] | None = None,
) -> dict[str, Any]:
    """Build, gate, promote, and immediately finalize under a held lock."""
    transaction = staged_analytics_refresh_transaction_locked(
        reports_root=reports_root,
        published_reports_root=published_reports_root,
        analytics_root=analytics_root,
        checks_output=checks_output,
        analytics_store_module=analytics_store_module,
        analytics_checks_module=analytics_checks_module,
        require_zero_block=require_zero_block,
        gate_validator=gate_validator,
        promote_companion=promote_companion,
    )
    with transaction:
        evidence = transaction.evidence
        transaction.commit()
    return evidence


def staged_analytics_refresh(
    *,
    reports_root: str | Path,
    published_reports_root: str | Path | None,
    analytics_root: str | Path,
    checks_output: str | Path,
    lock_path: str | Path,
    analytics_store_module=None,
    analytics_checks_module=None,
    lock_timeout_seconds: float = 600,
    require_zero_block: bool = True,
    gate_validator: Callable[[dict[str, Any], dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Build and validate a complete generation before promoting it."""
    with analytics_writer_lock(lock_path, timeout_seconds=lock_timeout_seconds):
        return staged_analytics_refresh_locked(
            reports_root=reports_root,
            published_reports_root=published_reports_root,
            analytics_root=analytics_root,
            checks_output=checks_output,
            analytics_store_module=analytics_store_module,
            analytics_checks_module=analytics_checks_module,
            require_zero_block=require_zero_block,
            gate_validator=gate_validator,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and atomically promote an Analytics generation")
    parser.add_argument("--reports-dir", required=True)
    parser.add_argument("--published-reports-dir", default=None)
    parser.add_argument("--analytics-dir", required=True)
    parser.add_argument("--checks-output", required=True)
    parser.add_argument("--analytics-lock", required=True)
    parser.add_argument("--lock-timeout-seconds", type=int, default=600)
    parser.add_argument("--allow-block", action="store_true")
    args = parser.parse_args(argv)
    result = staged_analytics_refresh(
        reports_root=args.reports_dir,
        published_reports_root=args.published_reports_dir,
        analytics_root=args.analytics_dir,
        checks_output=args.checks_output,
        lock_path=args.analytics_lock,
        lock_timeout_seconds=args.lock_timeout_seconds,
        require_zero_block=not args.allow_block,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
