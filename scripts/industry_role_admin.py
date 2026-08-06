#!/usr/bin/env python3
"""Inspect, reconcile, and recover the Industry Roles canonical state."""

from __future__ import annotations

import argparse
import json
import stat
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

try:
    from scripts import industry_role_store as store
except ImportError:  # executed directly from the scripts directory
    import industry_role_store as store


REPO = Path(__file__).resolve().parent.parent
MAX_TAXONOMY_BYTES = 1024 * 1024


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _taxonomy_version(content_dir: Path) -> int:
    taxonomy_path = content_dir / "industry_roles.json"
    try:
        metadata = taxonomy_path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size > MAX_TAXONOMY_BYTES
        ):
            raise ValueError("invalid taxonomy source")
        payload = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid taxonomy source") from exc
    version = payload.get("version") if isinstance(payload, dict) else None
    roles = payload.get("roles") if isinstance(payload, dict) else None
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version < 1
        or not isinstance(roles, dict)
    ):
        raise ValueError("invalid taxonomy source")
    return version


def _paths(content_dir: Path, reports_dir: Path) -> dict[str, Path]:
    return {
        "state": store.canonical_state_path(reports_dir),
        "overrides": content_dir / "industry_role_overrides.json",
        "suggestions": reports_dir / "industry_role_suggestions.json",
    }


def _status(
    content_dir: Path,
    reports_dir: Path,
    *,
    require_canonical: bool,
) -> tuple[int, dict[str, object]]:
    version = _taxonomy_version(content_dir)
    paths = _paths(content_dir, reports_dir)
    inspection = store.inspect_review_state(
        paths["state"],
        taxonomy_version=version,
        overrides_path=paths["overrides"],
        suggestions_path=paths["suggestions"],
    )
    healthy = inspection.healthy and (
        not require_canonical or inspection.canonical_status == "valid"
    )
    payload: dict[str, object] = {
        "command": "status",
        "healthy": healthy,
        "taxonomy": {"status": "valid", "version": version},
        "canonical": {
            "status": inspection.canonical_status,
            "revision": inspection.canonical_revision,
            "etag": inspection.canonical_etag,
        },
        "backup": {
            "status": inspection.backup_status,
            "revision": inspection.backup_revision,
            "retainedCopies": 1,
        },
        "legacy_export": {"status": inspection.export_status},
        "retirement": {"verdict": "HOLD"},
    }
    return (0 if healthy else 1), payload


def _export(
    content_dir: Path,
    reports_dir: Path,
    *,
    apply: bool,
) -> tuple[int, dict[str, object]]:
    version = _taxonomy_version(content_dir)
    paths = _paths(content_dir, reports_dir)
    result = store.export_review_state_to_legacy(
        paths["state"],
        taxonomy_version=version,
        overrides_path=paths["overrides"],
        suggestions_path=paths["suggestions"],
        now=_now(),
        apply=apply,
    )
    return 0, {"command": "export-legacy", **asdict(result)}


def _restore(
    content_dir: Path,
    reports_dir: Path,
    *,
    apply: bool,
    expected_etag: str | None,
    allow_invalid_current: bool,
) -> tuple[int, dict[str, object]]:
    version = _taxonomy_version(content_dir)
    state_path = _paths(content_dir, reports_dir)["state"]
    if not apply:
        preview = store.preview_restore_review_state_from_backup(
            state_path,
            taxonomy_version=version,
        )
        return 0, {
            "command": "restore-backup",
            "applied": False,
            **asdict(preview),
        }
    restored = store.restore_review_state_from_backup(
        state_path,
        taxonomy_version=version,
        now=_now(),
        expected_etag=expected_etag,
        allow_invalid_current=allow_invalid_current,
    )
    return 0, {
        "command": "restore-backup",
        "applied": True,
        "revision": restored.revision,
        "etag": restored.etag,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content-dir", type=Path, default=REPO / "content")
    parser.add_argument("--reports-dir", type=Path, default=REPO / "reports")
    commands = parser.add_subparsers(dest="command", required=True)
    status_parser = commands.add_parser("status")
    status_parser.add_argument("--require-canonical", action="store_true")
    export_parser = commands.add_parser("export-legacy")
    export_parser.add_argument("--apply", action="store_true")
    restore_parser = commands.add_parser("restore-backup")
    restore_parser.add_argument("--apply", action="store_true")
    restore_parser.add_argument("--expected-etag")
    restore_parser.add_argument("--allow-invalid-current", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    content_dir = Path(args.content_dir)
    reports_dir = Path(args.reports_dir)
    command = str(args.command)
    try:
        if command == "status":
            result, payload = _status(
                content_dir,
                reports_dir,
                require_canonical=bool(args.require_canonical),
            )
        elif command == "export-legacy":
            result, payload = _export(
                content_dir,
                reports_dir,
                apply=bool(args.apply),
            )
        else:
            result, payload = _restore(
                content_dir,
                reports_dir,
                apply=bool(args.apply),
                expected_etag=args.expected_etag,
                allow_invalid_current=bool(args.allow_invalid_current),
            )
    except ValueError:
        result = 1
        payload = {"command": command, "status": "error", "error": "invalid_input"}
    except store.StateBusy:
        result = 1
        payload = {"command": command, "status": "error", "error": "state_busy"}
    except store.StateInvalid:
        result = 1
        payload = {"command": command, "status": "error", "error": "state_invalid"}
    except store.RevisionConflict:
        result = 1
        payload = {"command": command, "status": "error", "error": "revision_conflict"}
    except OSError:
        result = 1
        payload = {"command": command, "status": "error", "error": "io_error"}
    except store.ReviewStateError:
        result = 1
        payload = {"command": command, "status": "error", "error": "state_error"}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
