#!/usr/bin/env python3
"""Phase 6V-6X protected Industry Roles read-contract tests."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import yaml
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.industry_roles import read_industry_role_review_board  # noqa: E402
from api.main import _internal_api_token_from_file, create_app  # noqa: E402
from api.models import ArtifactAvailable, ArtifactUnavailable  # noqa: E402


ROUTE = "/api/v1/private/industry-roles/review-board"
ACTION_ROUTE = f"{ROUTE}/actions"
TOKEN = "private-test-token-0123456789-abcdef"


def _write(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _paths(root: Path) -> tuple[Path, Path, Path]:
    taxonomy = root / "industry_roles.json"
    overrides = root / "industry_role_overrides.json"
    suggestions = root / "industry_role_suggestions.json"
    _write(
        taxonomy,
        {
            "version": 3,
            "_note": "server-only note",
            "roles": {
                "ai_accelerator": {
                    "name": "AI Accelerator",
                    "desc": "server-only description",
                    "keywords": ["GPU"],
                },
                "power_cooling": {"name": "Power / Cooling"},
            },
        },
    )
    _write(
        overrides,
        {
            "version": 3,
            "tickers": {
                "NVDA": {
                    "primary_role": "ai_accelerator",
                    "secondary_roles": ["power_cooling"],
                    "confidence": 0.95,
                    "reviewed_at": "2026-08-05T01:02:03Z",
                    "reviewed_by": "platform",
                    "evidence": ["server-only approved evidence"],
                }
            },
        },
    )
    _write(
        suggestions,
        {
            "generated_at": "2026-08-06T01:02:03Z",
            "suggestions": [
                {
                    "ticker": "AMD",
                    "suggested_primary_role": "ai_accelerator",
                    "suggested_primary_role_name": "AI Accelerator",
                    "suggested_secondary_roles": [],
                    "confidence": 0.88,
                    "evidence": ["theme_baskets: AI"],
                    "status": "suggested",
                },
                {
                    "ticker": "ORCL",
                    "suggested_primary_role": "classification_pending",
                    "suggested_primary_role_name": "待分類",
                    "suggested_secondary_roles": [],
                    "confidence": 0.0,
                    "evidence": ["fallback: no taxonomy/theme match yet"],
                    "status": "deferred",
                    "reviewed_at": "2026-08-05T03:04:05Z",
                },
            ],
        },
    )
    return taxonomy, overrides, suggestions


def _client(
    paths: tuple[Path, Path, Path],
    *,
    token: str | None = TOKEN,
    client_address: tuple[str, int] = ("127.0.0.1", 50000),
    base_url: str = "http://127.0.0.1",
) -> TestClient:
    target = create_app(
        industry_role_taxonomy_path=paths[0],
        industry_role_overrides_path=paths[1],
        industry_role_suggestions_path=paths[2],
        internal_api_token=token,
    )

    async def with_client_address(scope, receive, send):
        if scope["type"] == "http":
            scope = {**scope, "client": client_address}
        await target(scope, receive, send)

    return TestClient(with_client_address, base_url=base_url)


def test_reader_projects_only_bounded_review_fields() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = read_industry_role_review_board(*_paths(Path(tmp)))
    if not isinstance(result, ArtifactAvailable):
        raise AssertionError(result)
    payload = result.model_dump(mode="json", by_alias=True)
    if payload["meta"] != {
        "sourceId": "private.industry-roles.review-board",
        "asOf": None,
        "generatedAt": "2026-08-06T01:02:03Z",
    }:
        raise AssertionError(payload["meta"])
    data = payload["data"]
    if data["operator"] != "operator" or data["taxonomy_version"] != 3:
        raise AssertionError(data)
    if [role["id"] for role in data["roles"]] != [
        "ai_accelerator",
        "power_cooling",
    ]:
        raise AssertionError(data["roles"])
    serialized = json.dumps(payload, ensure_ascii=False)
    for forbidden in (
        "server-only note",
        "server-only description",
        "server-only approved evidence",
        "keywords",
        str(ROOT),
    ):
        if forbidden in serialized:
            raise AssertionError(f"private projection leaked {forbidden!r}")


def test_reader_is_fail_soft_for_missing_invalid_and_cross_reference_drift() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = _paths(root)
        paths[1].unlink()
        paths[2].unlink()
        empty = read_industry_role_review_board(*paths)
        if not isinstance(empty, ArtifactAvailable):
            raise AssertionError(empty)
        if empty.data.approved or empty.data.suggestions:
            raise AssertionError(empty.data)

        paths = _paths(root)
        paths[0].unlink()
        missing_taxonomy = read_industry_role_review_board(*paths)
        if (
            not isinstance(missing_taxonomy, ArtifactUnavailable)
            or missing_taxonomy.reason != "missing"
        ):
            raise AssertionError(missing_taxonomy)

        paths = _paths(root)
        paths[2].write_text("{", encoding="utf-8")
        invalid_json = read_industry_role_review_board(*paths)
        if (
            not isinstance(invalid_json, ArtifactUnavailable)
            or invalid_json.reason != "invalid_json"
        ):
            raise AssertionError(invalid_json)

        paths = _paths(root)
        payload = json.loads(paths[1].read_text(encoding="utf-8"))
        payload["tickers"]["NVDA"]["primary_role"] = "unknown_role"
        _write(paths[1], payload)
        drift = read_industry_role_review_board(*paths)
        if not isinstance(drift, ArtifactUnavailable) or drift.reason != "invalid_shape":
            raise AssertionError(drift)

        _paths(root)
        recovered = read_industry_role_review_board(*paths)
        if not isinstance(recovered, ArtifactAvailable):
            raise AssertionError(recovered)


def test_private_route_fails_closed_and_public_health_remains_available() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = _paths(Path(tmp))
        with _client(paths, token=None) as disabled:
            unavailable = disabled.get(ROUTE, headers={"Authorization": f"Bearer {TOKEN}"})
            health = disabled.get("/healthz")
        with _client(paths) as client:
            missing = client.get(ROUTE)
            malformed = client.get(ROUTE, headers={"Authorization": TOKEN})
            wrong = client.get(ROUTE, headers={"Authorization": "Bearer wrong-token-value-0123456789"})
            duplicate = client.get(
                ROUTE,
                headers=[
                    ("Authorization", f"Bearer {TOKEN}"),
                    ("Authorization", f"Bearer {TOKEN}"),
                ],
            )
            correct = client.get(ROUTE, headers={"Authorization": f"Bearer {TOKEN}"})

    if unavailable.status_code != 503 or health.status_code != 200:
        raise AssertionError((unavailable.status_code, health.status_code))
    expected_unauthorized = {
        "type": "about:blank",
        "title": "Unauthorized",
        "status": 401,
    }
    for response in (missing, malformed, wrong, duplicate):
        if response.status_code != 401 or response.json() != expected_unauthorized:
            raise AssertionError((response.status_code, response.text))
        if response.headers.get("www-authenticate") != "Bearer":
            raise AssertionError(response.headers)
    for response in (unavailable, missing, malformed, wrong, duplicate, correct):
        if response.headers.get("cache-control") != "no-store":
            raise AssertionError(response.headers)
        if TOKEN in response.text:
            raise AssertionError("credential leaked in response")
    if correct.status_code != 200 or correct.json()["data"]["operator"] != "operator":
        raise AssertionError((correct.status_code, correct.text))
    etag = correct.headers.get("etag", "")
    if not etag.startswith('"r0-') or not etag.endswith('"'):
        raise AssertionError(correct.headers)


def test_mutation_route_is_conditional_atomic_and_idempotent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = _paths(root)
        headers = {"Authorization": f"Bearer {TOKEN}"}
        with _client(paths) as client:
            initial = client.get(ROUTE, headers=headers)
            etag = initial.headers["etag"]
            action_headers = {
                **headers,
                "If-Match": etag,
                "Idempotency-Key": "approve-amd-request-0001",
            }
            request = {
                "action": "approve",
                "ticker": "AMD",
                "primaryRole": "ai_accelerator",
                "secondaryRoles": [],
            }
            committed = client.post(ACTION_ROUTE, headers=action_headers, json=request)
            replay = client.post(ACTION_ROUTE, headers=action_headers, json=request)
            stale = client.post(
                ACTION_ROUTE,
                headers={
                    **headers,
                    "If-Match": etag,
                    "Idempotency-Key": "reject-amd-request-0002",
                },
                json={"action": "reject", "ticker": "AMD"},
            )
            reused = client.post(
                ACTION_ROUTE,
                headers=action_headers,
                json={"action": "defer", "ticker": "AMD"},
            )
            current = client.get(ROUTE, headers=headers)

        if committed.status_code != 200 or replay.status_code != 200:
            raise AssertionError((committed.status_code, committed.text, replay.text))
        if committed.json()["revision"] != 1 or committed.json()["replayed"]:
            raise AssertionError(committed.json())
        if not replay.json()["replayed"] or replay.json()["transactionId"] != committed.json()["transactionId"]:
            raise AssertionError(replay.json())
        if replay.headers.get("etag") != committed.headers.get("etag"):
            raise AssertionError((replay.headers, committed.headers))
        if stale.status_code != 412 or reused.status_code != 409:
            raise AssertionError((stale.status_code, stale.text, reused.status_code, reused.text))
        if current.headers.get("etag") != committed.headers.get("etag"):
            raise AssertionError((current.headers, committed.headers))
        if current.json()["data"]["approved"][0]["ticker"] != "AMD":
            raise AssertionError(current.json())
        state_path = root / "industry_roles" / "review-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state["revision"] != 1 or len(state["audit"]) != 1:
            raise AssertionError(state)


def test_mutation_auth_and_preconditions_precede_side_effects() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = _paths(root)
        with _client(paths) as client:
            unauthenticated = client.post(
                ACTION_ROUTE,
                content=b"{",
                headers={"Content-Type": "application/json"},
            )
            authenticated = {"Authorization": f"Bearer {TOKEN}"}
            missing = client.post(
                ACTION_ROUTE,
                headers=authenticated,
                json={"action": "reject", "ticker": "NVDA"},
            )
            initial = client.get(ROUTE, headers=authenticated)
            invalid = client.post(
                ACTION_ROUTE,
                headers={
                    **authenticated,
                    "If-Match": initial.headers["etag"],
                    "Idempotency-Key": "invalid-request-key-0001",
                },
                json={"action": "reject", "ticker": "nvda", "extra": True},
            )
        if unauthenticated.status_code != 401:
            raise AssertionError((unauthenticated.status_code, unauthenticated.text))
        if missing.status_code != 428 or invalid.status_code != 422:
            raise AssertionError((missing.status_code, missing.text, invalid.status_code, invalid.text))
        if (root / "industry_roles" / "review-state.json").exists():
            raise AssertionError("failed mutation created canonical state")
        for response in (unauthenticated, missing, invalid):
            if response.headers.get("cache-control") != "no-store":
                raise AssertionError(response.headers)
            if response.headers.get("content-type", "").split(";", 1)[0] != "application/problem+json":
                raise AssertionError(response.headers)


def test_loopback_boundary_precedes_private_authentication() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = _paths(Path(tmp))
        with _client(paths, client_address=("203.0.113.5", 50000)) as remote:
            remote_response = remote.get(
                ROUTE,
                headers={"Authorization": f"Bearer {TOKEN}"},
            )
        with _client(paths, base_url="http://evil.example") as wrong_host:
            host_response = wrong_host.get(
                ROUTE,
                headers={"Authorization": f"Bearer {TOKEN}"},
            )
    for response in (remote_response, host_response):
        if response.status_code != 403 or response.json()["title"] != "Forbidden":
            raise AssertionError((response.status_code, response.text))


def test_systemd_credential_file_parser_is_exact_and_secret_safe() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "internal-api.env"
        path.write_bytes(f"SURGE_INTERNAL_API_TOKEN={TOKEN}\n".encode("ascii"))
        if _internal_api_token_from_file(str(path)) != TOKEN:
            raise AssertionError("valid systemd credential was rejected")
        for malformed in (
            f"SURGE_INTERNAL_API_TOKEN={TOKEN}",
            f"OTHER={TOKEN}\n",
            "SURGE_INTERNAL_API_TOKEN=short\n",
            f"SURGE_INTERNAL_API_TOKEN={TOKEN}\nEXTRA=value\n",
        ):
            path.write_text(malformed, encoding="utf-8")
            if _internal_api_token_from_file(str(path)) is not None:
                raise AssertionError("malformed credential file was accepted")
        path.write_bytes(b"X" * 1_024)
        if _internal_api_token_from_file(str(path)) is not None:
            raise AssertionError("oversized credential file was accepted")
        path.unlink()
        target = Path(tmp) / "credential-target.env"
        target.write_bytes(f"SURGE_INTERNAL_API_TOKEN={TOKEN}\n".encode("ascii"))
        path.symlink_to(target)
        if _internal_api_token_from_file(str(path)) is not None:
            raise AssertionError("symlink credential file was accepted")
        if _internal_api_token_from_file(tmp) is not None:
            raise AssertionError("non-regular credential source was accepted")


def test_openapi_declares_route_level_bearer_security_and_static_parity() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = _paths(Path(tmp))
        with _client(paths) as client:
            generated = client.get("/openapi.json").json()
    static = yaml.safe_load(
        (ROOT / "docs/api/quant-radar-v1.openapi.yaml").read_text(encoding="utf-8")
    )
    for label, schema in (("generated", generated), ("static", static)):
        operation = schema["paths"][ROUTE]["get"]
        if operation.get("operationId") != "getIndustryRoleReviewBoard":
            raise AssertionError((label, operation))
        if operation.get("security") != [{"InternalServiceBearer": []}]:
            raise AssertionError((label, operation.get("security")))
        if set(operation["responses"]) != {"200", "401", "500", "503"}:
            raise AssertionError((label, operation["responses"]))
        success = operation["responses"]["200"]
        if "$ref" in success:
            success = schema["components"]["responses"][success["$ref"].rsplit("/", 1)[-1]]
        if "ETag" not in success["headers"]:
            raise AssertionError((label, success))
        mutation = schema["paths"][ACTION_ROUTE]["post"]
        if mutation.get("operationId") != "mutateIndustryRoleReviewBoard":
            raise AssertionError((label, mutation))
        if mutation.get("security") != [{"InternalServiceBearer": []}]:
            raise AssertionError((label, mutation.get("security")))
        if set(mutation["responses"]) != {
            "200", "401", "409", "412", "422", "428", "500", "503"
        }:
            raise AssertionError((label, mutation["responses"]))
        scheme = schema["components"]["securitySchemes"]["InternalServiceBearer"]
        if scheme.get("type") != "http" or scheme.get("scheme") != "bearer":
            raise AssertionError((label, scheme))
    if generated["info"]["version"] != "1.23.0-draft":
        raise AssertionError(generated["info"])
    if static["info"]["version"] != generated["info"]["version"]:
        raise AssertionError((static["info"], generated["info"]))


def main() -> None:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
