"""Bounded protected reader for the singleton Industry Roles review board."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import ValidationError

from api.models import (
    ArtifactAvailable,
    ArtifactMeta,
    ArtifactUnavailable,
    IndustryRoleReviewBoardData,
)
from scripts import industry_role_store as review_store


SOURCE_ID = "private.industry-roles.review-board"
TAXONOMY_MAX_BYTES = 512 * 1024
OVERRIDES_MAX_BYTES = 2 * 1024 * 1024
SUGGESTIONS_MAX_BYTES = 4 * 1024 * 1024
ReadReason: TypeAlias = Literal[
    "missing",
    "invalid_json",
    "invalid_shape",
    "unreadable",
]
JsonRead: TypeAlias = dict[str, object] | ReadReason


@dataclass(frozen=True, slots=True)
class IndustryRoleReviewBoardSnapshot:
    envelope: ArtifactAvailable[IndustryRoleReviewBoardData] | ArtifactUnavailable
    etag: str | None


def _read_json_object(path: Path, maximum: int) -> JsonRead:
    descriptor: int | None = None
    try:
        if path.is_symlink():
            return "unreadable"
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            descriptor = None
            return "unreadable"
        handle = os.fdopen(descriptor, "rb")
        descriptor = None
        with handle:
            raw = handle.read(maximum + 1)
    except FileNotFoundError:
        if descriptor is not None:
            os.close(descriptor)
        return "missing"
    except OSError:
        if descriptor is not None:
            os.close(descriptor)
        return "unreadable"
    if len(raw) > maximum:
        return "invalid_shape"
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "invalid_json"
    return payload if isinstance(payload, dict) else "invalid_shape"


def _unavailable(reason: ReadReason) -> ArtifactUnavailable:
    return ArtifactUnavailable(
        available=False,
        reason=reason,
        data=None,
        meta=ArtifactMeta(sourceId=SOURCE_ID, asOf=None, generatedAt=None),
    )


def _source_reason(value: JsonRead) -> ReadReason | None:
    return value if isinstance(value, str) else None


def _project_roles(payload: dict[str, object]) -> tuple[int, list[dict[str, object]]]:
    version = payload.get("version")
    roles = payload.get("roles")
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError("invalid taxonomy version")
    if not isinstance(roles, dict) or len(roles) > 200:
        raise ValueError("invalid role taxonomy")
    projected: list[dict[str, object]] = []
    for role_id, config in sorted(roles.items()):
        if not isinstance(role_id, str) or not isinstance(config, dict):
            raise ValueError("invalid role definition")
        projected.append({"id": role_id, "name": config.get("name")})
    return version, projected


def _project_approved(
    payload: dict[str, object],
    taxonomy_version: int,
) -> list[dict[str, object]]:
    if payload.get("version") != taxonomy_version:
        raise ValueError("override taxonomy version mismatch")
    tickers = payload.get("tickers")
    if not isinstance(tickers, dict) or len(tickers) > 5_000:
        raise ValueError("invalid approved assignments")
    projected: list[dict[str, object]] = []
    for ticker, config in sorted(tickers.items()):
        if not isinstance(ticker, str) or not isinstance(config, dict):
            raise ValueError("invalid approved assignment")
        projected.append(
            {
                "ticker": ticker,
                "primary_role": config.get("primary_role"),
                "secondary_roles": config.get("secondary_roles", []),
                "confidence": config.get("confidence"),
                "reviewed_at": config.get("reviewed_at"),
            }
        )
    return projected


def _project_suggestions(
    payload: dict[str, object],
) -> tuple[str | None, list[dict[str, object]]]:
    generated_at = payload.get("generated_at")
    suggestions = payload.get("suggestions")
    if generated_at is not None and not isinstance(generated_at, str):
        raise ValueError("invalid suggestion timestamp")
    if not isinstance(suggestions, list) or len(suggestions) > 5_000:
        raise ValueError("invalid suggestions")
    projected: list[dict[str, object]] = []
    for item in suggestions:
        if not isinstance(item, dict):
            raise ValueError("invalid suggestion row")
        projected.append(
            {
                "ticker": item.get("ticker"),
                "suggested_primary_role": item.get("suggested_primary_role"),
                "suggested_primary_role_name": item.get(
                    "suggested_primary_role_name"
                ),
                "suggested_secondary_roles": item.get(
                    "suggested_secondary_roles", []
                ),
                "confidence": item.get("confidence"),
                "evidence": item.get("evidence", []),
                "status": item.get("status", "suggested"),
                "reviewed_at": item.get("reviewed_at"),
            }
        )
    return generated_at, projected


def _generated_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    return datetime.fromisoformat(normalized)


def read_industry_role_review_board_snapshot(
    taxonomy_path: Path,
    overrides_path: Path,
    suggestions_path: Path,
    state_path: Path | None = None,
) -> IndustryRoleReviewBoardSnapshot:
    """Read and cross-validate three fixed resources without exposing raw fields."""

    taxonomy = _read_json_object(taxonomy_path, TAXONOMY_MAX_BYTES)
    taxonomy_reason = _source_reason(taxonomy)
    if taxonomy_reason is not None:
        return IndustryRoleReviewBoardSnapshot(_unavailable(taxonomy_reason), None)
    if not isinstance(taxonomy, dict):
        return IndustryRoleReviewBoardSnapshot(_unavailable("invalid_shape"), None)
    try:
        taxonomy_version, roles = _project_roles(taxonomy)
        canonical_path = state_path or review_store.canonical_state_path(
            suggestions_path.parent
        )
        if canonical_path.exists() or canonical_path.is_symlink():
            state = review_store.read_review_state(
                canonical_path,
                taxonomy_version,
                {"version": taxonomy_version, "tickers": {}},
                {"generated_at": None, "suggestions": []},
            )
        else:
            overrides = _read_json_object(overrides_path, OVERRIDES_MAX_BYTES)
            suggestions = _read_json_object(suggestions_path, SUGGESTIONS_MAX_BYTES)
            for source in (overrides, suggestions):
                reason = _source_reason(source)
                if reason is not None and reason != "missing":
                    return IndustryRoleReviewBoardSnapshot(_unavailable(reason), None)
            if overrides == "missing":
                overrides = {"version": taxonomy_version, "tickers": {}}
            if suggestions == "missing":
                suggestions = {"generated_at": None, "suggestions": []}
            if not isinstance(overrides, dict) or not isinstance(suggestions, dict):
                raise ValueError("invalid optional review state")
            state = review_store.read_review_state(
                canonical_path,
                taxonomy_version,
                overrides,
                suggestions,
            )
        approved = _project_approved(state.overrides, taxonomy_version)
        generated_at, suggestion_rows = _project_suggestions(state.suggestions)
        data = IndustryRoleReviewBoardData.model_validate(
            {
                "operator": "operator",
                "taxonomy_version": taxonomy_version,
                "generated_at": generated_at,
                "roles": roles,
                "approved": approved,
                "suggestions": suggestion_rows,
            },
            strict=True,
        )
        meta_generated_at = _generated_datetime(generated_at)
    except (TypeError, ValueError, ValidationError, review_store.StateInvalid):
        return IndustryRoleReviewBoardSnapshot(_unavailable("invalid_shape"), None)
    return IndustryRoleReviewBoardSnapshot(
        ArtifactAvailable(
            available=True,
            reason="ok",
            data=data,
            meta=ArtifactMeta(
                sourceId=SOURCE_ID,
                asOf=None,
                generatedAt=meta_generated_at,
            ),
        ),
        state.etag,
    )


def read_industry_role_review_board(
    taxonomy_path: Path,
    overrides_path: Path,
    suggestions_path: Path,
    state_path: Path | None = None,
) -> ArtifactAvailable[IndustryRoleReviewBoardData] | ArtifactUnavailable:
    """Compatibility wrapper returning only the protected envelope."""

    return read_industry_role_review_board_snapshot(
        taxonomy_path,
        overrides_path,
        suggestions_path,
        state_path,
    ).envelope
