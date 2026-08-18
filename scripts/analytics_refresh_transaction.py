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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator


UTC = timezone.utc


class AnalyticsGateError(RuntimeError):
    """Raised when a staged Analytics generation fails its publication gate."""


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
                    raise TimeoutError(f"Analytics writer lock timed out: {path}") from None
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
    finally:
        temporary.unlink(missing_ok=True)


def _backup_file_with_link_or_copy(source: Path, destination: Path) -> None:
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def _promote_generation(staging: Path, target: Path, checks: Path, checks_output: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    staged_db = staging / "analytics.duckdb"
    staged_parquet = staging / "parquet"
    if not staged_db.is_file() or not staged_parquet.is_dir():
        raise AnalyticsGateError("staged Analytics generation is incomplete")

    backup = Path(tempfile.mkdtemp(prefix=".analytics-backup-", dir=target.parent))
    target_db = target / "analytics.duckdb"
    target_parquet = target / "parquet"
    backup_db = backup / "analytics.duckdb"
    backup_parquet = backup / "parquet"
    old_db = target_db.is_file()
    old_parquet = target_parquet.is_dir()
    new_parquet_promoted = False
    new_db_promoted = False
    try:
        if old_db:
            _backup_file_with_link_or_copy(target_db, backup_db)
        if old_parquet:
            os.replace(target_parquet, backup_parquet)
        os.replace(staged_parquet, target_parquet)
        new_parquet_promoted = True
        os.replace(staged_db, target_db)
        new_db_promoted = True
        _atomic_copy(checks, checks_output)
    except Exception:
        if new_db_promoted:
            if old_db and backup_db.is_file():
                os.replace(backup_db, target_db)
            elif not old_db:
                target_db.unlink(missing_ok=True)
        if new_parquet_promoted and target_parquet.is_dir():
            shutil.rmtree(target_parquet)
        if old_parquet and backup_parquet.is_dir():
            os.replace(backup_parquet, target_parquet)
        raise
    finally:
        shutil.rmtree(backup, ignore_errors=True)


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

    analytics = Path(analytics_root).resolve()
    output = Path(checks_output).resolve()
    analytics.parent.mkdir(parents=True, exist_ok=True)
    with analytics_writer_lock(lock_path, timeout_seconds=lock_timeout_seconds):
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
            if not staged_checks.is_file():
                staged_checks.parent.mkdir(parents=True, exist_ok=True)
                staged_checks.write_text(
                    json.dumps(checks, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            _promote_generation(staging, analytics, staged_checks, output)
            return {
                "tables": tables,
                "checks": checks,
                "database": file_identity(analytics / "analytics.duckdb"),
                "promoted_at": iso_utc(),
            }
        finally:
            shutil.rmtree(staging, ignore_errors=True)


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
