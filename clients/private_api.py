"""Fail-closed frontend client for credential-protected loopback reads."""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, TypeAlias

import httpx
from pydantic import TypeAdapter, ValidationError

from api.models import (
    ArtifactAvailable,
    ArtifactUnavailable,
    IndustryRoleActionRequest,
    IndustryRoleMutationResult,
    IndustryRoleReviewBoardData,
    UnavailableReason,
)


_REVIEW_BOARD_URL = (
    "http://127.0.0.1:8000/api/v1/private/industry-roles/review-board"
)
_REVIEW_BOARD_ACTION_URL = f"{_REVIEW_BOARD_URL}/actions"
_TOKEN_ENV = "SURGE_INTERNAL_API_TOKEN"
_TOKEN_MIN_LENGTH = 32
_TOKEN_MAX_LENGTH = 256
_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
_DEADLINE_SECONDS = 1.0
_TIMEOUT = httpx.Timeout(connect=0.25, read=0.25, write=0.25, pool=0.25)
_RFC3339_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt](?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d"
    r"(?:\.\d{1,6})?(?:[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)$"
)
_ENVELOPE = TypeAdapter(
    ArtifactAvailable[IndustryRoleReviewBoardData] | ArtifactUnavailable
)
_ACTION = TypeAdapter(IndustryRoleActionRequest)

PrivateClientFailureReason: TypeAlias = Literal[
    "transport_error",
    "deadline_exceeded",
    "http_status",
    "invalid_media_type",
    "invalid_cache_control",
    "response_too_large",
    "invalid_envelope",
    "authentication_unavailable",
    "invalid_etag",
]


@dataclass(frozen=True, slots=True)
class FixedReadPayload:
    body: bytes
    etag: str | None


FixedReadResult: TypeAlias = FixedReadPayload | PrivateClientFailureReason


@dataclass(frozen=True, slots=True)
class IndustryRoleReviewBoardApiAvailable:
    board: IndustryRoleReviewBoardData
    etag: str


@dataclass(frozen=True, slots=True)
class IndustryRoleReviewBoardApiUnavailable:
    reason: UnavailableReason


@dataclass(frozen=True, slots=True)
class IndustryRoleReviewBoardApiFailure:
    reason: PrivateClientFailureReason


IndustryRoleReviewBoardApiResult: TypeAlias = (
    IndustryRoleReviewBoardApiAvailable
    | IndustryRoleReviewBoardApiUnavailable
    | IndustryRoleReviewBoardApiFailure
)

PrivateMutationFailureReason: TypeAlias = Literal[
    "transport_error",
    "deadline_exceeded",
    "http_status",
    "conflict",
    "precondition_failed",
    "invalid_media_type",
    "invalid_cache_control",
    "response_too_large",
    "invalid_envelope",
    "authentication_unavailable",
    "invalid_etag",
    "invalid_request",
]


@dataclass(frozen=True, slots=True)
class IndustryRoleMutationApiSuccess:
    result: IndustryRoleMutationResult
    etag: str


@dataclass(frozen=True, slots=True)
class IndustryRoleMutationApiFailure:
    reason: PrivateMutationFailureReason


IndustryRoleMutationApiResult: TypeAlias = (
    IndustryRoleMutationApiSuccess | IndustryRoleMutationApiFailure
)


def _internal_api_token() -> str | None:
    token = os.environ.get(_TOKEN_ENV)
    if token is None or not (_TOKEN_MIN_LENGTH <= len(token) <= _TOKEN_MAX_LENGTH):
        return None
    try:
        encoded = token.encode("ascii")
    except UnicodeEncodeError:
        return None
    return token if all(0x21 <= byte <= 0x7E for byte in encoded) else None


def _is_json_media_type(value: str) -> bool:
    media_type, _, _parameters = value.partition(";")
    return media_type.strip().casefold() == "application/json"


def _has_no_store(value: str) -> bool:
    return any(
        directive.strip().casefold() == "no-store" for directive in value.split(",")
    )


def _is_strong_etag(value: str | None) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(r'^"r(?:0|[1-9][0-9]*)-[0-9a-f]{64}"$', value) is not None
    )


def _valid_idempotency_key(value: str) -> bool:
    if not isinstance(value, str) or not (16 <= len(value) <= 128):
        return False
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError:
        return False
    return all(0x21 <= byte <= 0x7E for byte in encoded)


def _parse_timestamp(value: str) -> datetime | None:
    if _RFC3339_RE.fullmatch(value) is None:
        return None
    normalized = f"{value[:10]}T{value[11:]}"
    if normalized.endswith(("Z", "z")):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


async def _read_fixed_json(
    token: str,
    transport: httpx.AsyncBaseTransport | None,
) -> FixedReadResult:
    options: dict[str, object] = {
        "trust_env": False,
        "follow_redirects": False,
        "timeout": _TIMEOUT,
    }
    if transport is not None:
        options["transport"] = transport
    try:
        async with httpx.AsyncClient(**options) as client:
            async with client.stream(
                "GET",
                _REVIEW_BOARD_URL,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {token}",
                },
            ) as response:
                if response.status_code != 200:
                    return "http_status"
                if not _is_json_media_type(response.headers.get("Content-Type", "")):
                    return "invalid_media_type"
                if not _has_no_store(response.headers.get("Cache-Control", "")):
                    return "invalid_cache_control"
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > _MAX_RESPONSE_BYTES:
                        return "response_too_large"
                    body.extend(chunk)
    except httpx.RequestError:
        return "transport_error"
    return FixedReadPayload(bytes(body), response.headers.get("ETag"))


async def _request_review_board(
    transport: httpx.AsyncBaseTransport | None,
) -> IndustryRoleReviewBoardApiResult:
    token = _internal_api_token()
    if token is None:
        return IndustryRoleReviewBoardApiFailure("authentication_unavailable")
    payload = await _read_fixed_json(token, transport)
    if isinstance(payload, str):
        return IndustryRoleReviewBoardApiFailure(payload)
    try:
        envelope = _ENVELOPE.validate_json(payload.body, strict=True)
    except (ValidationError, ValueError):
        return IndustryRoleReviewBoardApiFailure("invalid_envelope")
    if envelope.meta.source_id != "private.industry-roles.review-board":
        return IndustryRoleReviewBoardApiFailure("invalid_envelope")
    if isinstance(envelope, ArtifactAvailable):
        if not _is_strong_etag(payload.etag):
            return IndustryRoleReviewBoardApiFailure("invalid_etag")
        generated_at = (
            _parse_timestamp(envelope.data.generated_at)
            if envelope.data.generated_at is not None
            else None
        )
        if (
            envelope.meta.as_of is not None
            or (envelope.data.generated_at is not None and generated_at is None)
            or envelope.meta.generated_at != generated_at
        ):
            return IndustryRoleReviewBoardApiFailure("invalid_envelope")
        return IndustryRoleReviewBoardApiAvailable(envelope.data, payload.etag)
    if payload.etag is not None:
        return IndustryRoleReviewBoardApiFailure("invalid_etag")
    if envelope.meta.as_of is not None or envelope.meta.generated_at is not None:
        return IndustryRoleReviewBoardApiFailure("invalid_envelope")
    return IndustryRoleReviewBoardApiUnavailable(envelope.reason)


async def _request_mutation(
    request_payload: dict[str, object],
    *,
    etag: str,
    idempotency_key: str,
    transport: httpx.AsyncBaseTransport | None,
) -> IndustryRoleMutationApiResult:
    token = _internal_api_token()
    if token is None:
        return IndustryRoleMutationApiFailure("authentication_unavailable")
    options: dict[str, object] = {
        "trust_env": False,
        "follow_redirects": False,
        "timeout": _TIMEOUT,
    }
    if transport is not None:
        options["transport"] = transport
    encoded = json.dumps(
        request_payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    try:
        async with httpx.AsyncClient(**options) as client:
            async with client.stream(
                "POST",
                _REVIEW_BOARD_ACTION_URL,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "If-Match": etag,
                    "Idempotency-Key": idempotency_key,
                },
                content=encoded,
            ) as response:
                if response.status_code == 409:
                    return IndustryRoleMutationApiFailure("conflict")
                if response.status_code == 412:
                    return IndustryRoleMutationApiFailure("precondition_failed")
                if response.status_code != 200:
                    return IndustryRoleMutationApiFailure("http_status")
                if not _is_json_media_type(response.headers.get("Content-Type", "")):
                    return IndustryRoleMutationApiFailure("invalid_media_type")
                if not _has_no_store(response.headers.get("Cache-Control", "")):
                    return IndustryRoleMutationApiFailure("invalid_cache_control")
                response_etag = response.headers.get("ETag")
                if not _is_strong_etag(response_etag):
                    return IndustryRoleMutationApiFailure("invalid_etag")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > _MAX_RESPONSE_BYTES:
                        return IndustryRoleMutationApiFailure("response_too_large")
                    body.extend(chunk)
    except httpx.RequestError:
        return IndustryRoleMutationApiFailure("transport_error")
    try:
        result = IndustryRoleMutationResult.model_validate_json(bytes(body), strict=True)
    except (ValidationError, ValueError):
        return IndustryRoleMutationApiFailure("invalid_envelope")
    expected_ticker = (
        None
        if request_payload.get("action") == "generate"
        else request_payload.get("ticker")
    )
    if result.action != request_payload.get("action") or result.ticker != expected_ticker:
        return IndustryRoleMutationApiFailure("invalid_envelope")
    return IndustryRoleMutationApiSuccess(result, response_etag)


def load_industry_role_review_board(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> IndustryRoleReviewBoardApiResult:
    """Read the protected singleton-operator board without a local fallback."""

    try:
        return asyncio.run(
            asyncio.wait_for(
                _request_review_board(transport),
                timeout=_DEADLINE_SECONDS,
            )
        )
    except asyncio.TimeoutError:
        return IndustryRoleReviewBoardApiFailure("deadline_exceeded")


def mutate_industry_role_review_board(
    request: dict[str, object],
    *,
    etag: str,
    idempotency_key: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> IndustryRoleMutationApiResult:
    """Send exactly one conditional mutation attempt; callers decide recovery."""

    if not _is_strong_etag(etag) or not _valid_idempotency_key(idempotency_key):
        return IndustryRoleMutationApiFailure("invalid_request")
    try:
        action = _ACTION.validate_python(request, strict=True)
    except (ValidationError, ValueError):
        return IndustryRoleMutationApiFailure("invalid_request")
    payload = action.model_dump(mode="json", by_alias=True)
    try:
        return asyncio.run(
            asyncio.wait_for(
                _request_mutation(
                    payload,
                    etag=etag,
                    idempotency_key=idempotency_key,
                    transport=transport,
                ),
                timeout=_DEADLINE_SECONDS,
            )
        )
    except asyncio.TimeoutError:
        return IndustryRoleMutationApiFailure("deadline_exceeded")
