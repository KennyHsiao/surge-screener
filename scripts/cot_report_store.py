#!/usr/bin/env python3
"""Promote durable COT report pairs through an atomic shared generation."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable


_REPORT_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(\.md|\.verified\.json)$")
_MARKDOWN_MAX_BYTES = 256 * 1024
_VERIFIED_MAX_BYTES = 64 * 1024


@dataclass(frozen=True)
class CotPair:
    markdown: bytes
    verified: bytes
    retrieved_at: datetime


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _parse_retrieved_at(value: object, *, report_date: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"COT {report_date} is missing price.retrieved_at")
    normalized = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"COT {report_date} has invalid price.retrieved_at") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"COT {report_date} price.retrieved_at must include a timezone")
    return parsed.astimezone(timezone.utc)


def _read_pairs(directory: Path, *, missing_ok: bool = False) -> dict[str, CotPair]:
    if not directory.exists():
        if missing_ok:
            return {}
        raise ValueError(f"COT source directory is missing: {directory}")
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError(f"COT source must be a physical directory: {directory}")

    candidates: dict[str, set[str]] = {}
    for path in directory.iterdir():
        match = _REPORT_RE.fullmatch(path.name)
        if match is None:
            continue
        report_date, suffix = match.groups()
        candidates.setdefault(report_date, set()).add(suffix)

    pairs: dict[str, CotPair] = {}
    expected = {".md", ".verified.json"}
    for report_date, suffixes in sorted(candidates.items()):
        if suffixes != expected:
            raise ValueError(f"COT {report_date} must be a complete pair")
        try:
            date.fromisoformat(report_date)
        except ValueError as exc:
            raise ValueError(f"COT report filename is not a real date: {report_date}") from exc

        markdown_path = directory / f"{report_date}.md"
        verified_path = directory / f"{report_date}.verified.json"
        for path in (markdown_path, verified_path):
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"COT pair member must be a physical file: {path.name}")
        markdown = markdown_path.read_bytes()
        verified = verified_path.read_bytes()
        if not markdown.strip() or len(markdown) > _MARKDOWN_MAX_BYTES:
            raise ValueError(f"COT {report_date} markdown is empty or oversized")
        if not verified or len(verified) > _VERIFIED_MAX_BYTES:
            raise ValueError(f"COT {report_date} verified sidecar is empty or oversized")
        try:
            payload = json.loads(verified)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"COT {report_date} verified sidecar is invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"COT {report_date} verified sidecar must be an object")
        price = payload.get("price")
        if not isinstance(price, dict) or price.get("friday_date") != report_date:
            raise ValueError(f"COT {report_date} must match price.friday_date")
        retrieved_at = _parse_retrieved_at(price.get("retrieved_at"), report_date=report_date)
        pairs[report_date] = CotPair(markdown, verified, retrieved_at)
    return pairs


def _read_current(store: Path, generations: Path) -> tuple[str | None, dict[str, CotPair]]:
    current = store / "current"
    if not current.exists() and not current.is_symlink():
        return None, {}
    if not current.is_symlink():
        raise ValueError("COT current must be a generation symlink")
    try:
        target = current.resolve(strict=True)
    except OSError as exc:
        raise ValueError("COT current generation symlink is broken") from exc
    generations_root = generations.resolve(strict=True)
    if target.parent != generations_root or not target.is_dir():
        raise ValueError("COT current generation escapes the shared store")
    return target.name, _read_pairs(target)


def _merge_pairs(
    current: dict[str, CotPair], source: dict[str, CotPair],
) -> dict[str, CotPair]:
    merged = dict(current)
    for report_date, candidate in source.items():
        existing = merged.get(report_date)
        if existing is None or candidate.retrieved_at > existing.retrieved_at:
            merged[report_date] = candidate
        elif candidate.retrieved_at == existing.retrieved_at and candidate != existing:
            raise ValueError(
                f"COT {report_date} has conflicting content at the same retrieval time"
            )
    return merged


def _tree_hash(pairs: dict[str, CotPair]) -> str:
    digest = hashlib.sha256()
    for report_date, pair in sorted(pairs.items()):
        for suffix, content in ((".md", pair.markdown), (".verified.json", pair.verified)):
            digest.update(f"{report_date}{suffix}".encode("ascii"))
            digest.update(b"\0")
            digest.update(content)
            digest.update(b"\0")
    return digest.hexdigest()


def _write_file(path: Path, content: bytes) -> None:
    with path.open("xb") as handle:
        os.chmod(path, 0o600)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _prepare_generation(
    generations: Path, generation: str, pairs: dict[str, CotPair],
) -> Path:
    final = generations / generation
    if final.exists():
        if final.is_symlink() or not final.is_dir() or _read_pairs(final) != pairs:
            raise ValueError(f"COT generation collision: {generation}")
        return final

    prepared = generations / f".prepare-{uuid.uuid4().hex}"
    prepared.mkdir(mode=0o700)
    try:
        for report_date, pair in sorted(pairs.items()):
            _write_file(prepared / f"{report_date}.md", pair.markdown)
            _write_file(prepared / f"{report_date}.verified.json", pair.verified)
        _fsync_directory(prepared)
        os.rename(prepared, final)
        _fsync_directory(generations)
    finally:
        if prepared.exists():
            shutil.rmtree(prepared)
    return final


def promote_cot_reports(
    source_dir: str | Path,
    store_dir: str | Path,
    *,
    replace_fn: Callable[[os.PathLike[str], os.PathLike[str]], Any] = os.replace,
) -> dict[str, object]:
    """Merge complete pairs and atomically expose one last-known-good generation."""

    source = Path(source_dir).resolve()
    store = Path(store_dir).resolve()
    store.mkdir(parents=True, exist_ok=True, mode=0o700)
    generations = store / "generations"
    generations.mkdir(mode=0o700, exist_ok=True)

    lock_path = store / ".lock"
    with lock_path.open("a+b") as lock:
        os.chmod(lock_path, 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        current_name, current_pairs = _read_current(store, generations)
        source_pairs = _read_pairs(source, missing_ok=True)
        merged = _merge_pairs(current_pairs, source_pairs)
        tree_hash = _tree_hash(merged)
        latest_date = max(merged) if merged else "empty"
        generation = f"{latest_date}-{tree_hash}"
        _prepare_generation(generations, generation, merged)

        if current_name == generation:
            return {
                "status": "unchanged",
                "generation": generation,
                "pair_count": len(merged),
                "latest_date": None if not merged else latest_date,
                "tree_hash": tree_hash,
            }

        current = store / "current"
        temporary = store / f".current-next-{uuid.uuid4().hex}"
        os.symlink(f"generations/{generation}", temporary)
        try:
            replace_fn(temporary, current)
            _fsync_directory(store)
        finally:
            if temporary.is_symlink() or temporary.exists():
                temporary.unlink()
        return {
            "status": "promoted",
            "generation": generation,
            "pair_count": len(merged),
            "latest_date": None if not merged else latest_date,
            "tree_hash": tree_hash,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--store-dir", required=True)
    args = parser.parse_args(argv)
    result = promote_cot_reports(args.source_dir, args.store_dir)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
