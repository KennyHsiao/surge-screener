#!/usr/bin/env python3
"""Shared lossless CSV storage primitives for the performance ledger."""

from __future__ import annotations

import csv
import fcntl
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class LedgerLockTimeout(TimeoutError):
    pass


def lock_path_for(ledger_path: str | Path) -> Path:
    ledger = Path(ledger_path)
    return ledger.with_name(f"{ledger.name}.lock")


@contextmanager
def ledger_lock(ledger_path: str | Path, *, timeout_seconds: float = 30.0) -> Iterator[None]:
    """Hold the shared advisory lock used by every local ledger writer."""
    ledger = Path(ledger_path)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    lock_path = lock_path_for(ledger)
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    deadline = time.monotonic() + max(0.0, float(timeout_seconds))
    try:
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if time.monotonic() >= deadline:
                    raise LedgerLockTimeout(
                        f"timed out waiting for ledger lock {lock_path}"
                    ) from exc
                time.sleep(0.05)
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def read_ledger(ledger_path: str | Path) -> tuple[list[str] | None, list[dict[str, str]]]:
    ledger = Path(ledger_path)
    if not ledger.exists() or ledger.stat().st_size == 0:
        return None, []
    with ledger.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames) if reader.fieldnames is not None else None
        return fieldnames, list(reader)


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write_ledger(
    ledger_path: str | Path,
    fieldnames: list[str],
    rows: list[dict],
) -> None:
    """Write a complete CSV beside the target, fsync it, then replace atomically."""
    ledger = Path(ledger_path)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    descriptor, tmp_name = tempfile.mkstemp(
        dir=ledger.parent,
        prefix=f".{ledger.name}.tmp-",
        text=True,
    )
    tmp_path = Path(tmp_name)
    try:
        if ledger.exists():
            os.fchmod(descriptor, ledger.stat().st_mode & 0o777)
        with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as handle:
            descriptor = -1
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, ledger)
        _fsync_directory(ledger.parent)
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise
