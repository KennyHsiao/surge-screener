#!/usr/bin/env python3
"""Phase 6X protected Industry Roles client and page-boundary tests."""

from __future__ import annotations

import ast
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import httpx
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clients import private_api as _private_api  # noqa: E402


TOKEN = "private-ui-token-0123456789-abcdef"
URL = "http://127.0.0.1:8000/api/v1/private/industry-roles/review-board"
ACTION_URL = f"{URL}/actions"
ETAG = '"r0-0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"'


def _body() -> dict[str, object]:
    return {
        "available": True,
        "reason": "ok",
        "data": {
            "operator": "operator",
            "taxonomy_version": 1,
            "generated_at": "2026-08-06T01:02:03Z",
            "roles": [{"id": "ai_accelerator", "name": "AI Accelerator"}],
            "approved": [],
            "suggestions": [
                {
                    "ticker": "NVDA",
                    "suggested_primary_role": "ai_accelerator",
                    "suggested_primary_role_name": "AI Accelerator",
                    "suggested_secondary_roles": [],
                    "confidence": 0.9,
                    "evidence": ["theme_baskets: AI"],
                    "status": "suggested",
                    "reviewed_at": None,
                }
            ],
        },
        "meta": {
            "sourceId": "private.industry-roles.review-board",
            "asOf": None,
            "generatedAt": "2026-08-06T01:02:03Z",
        },
    }


@contextmanager
def _credential(value: str | None):
    previous = os.environ.get("SURGE_INTERNAL_API_TOKEN")
    if value is None:
        os.environ.pop("SURGE_INTERNAL_API_TOKEN", None)
    else:
        os.environ["SURGE_INTERNAL_API_TOKEN"] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("SURGE_INTERNAL_API_TOKEN", None)
        else:
            os.environ["SURGE_INTERNAL_API_TOKEN"] = previous


def _transport(status: int = 200, body: dict[str, object] | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) != URL or request.method != "GET":
            raise AssertionError(request)
        if request.headers.get("Authorization") != f"Bearer {TOKEN}":
            raise AssertionError("protected client omitted service credential")
        if "authorization" in request.url.params:
            raise AssertionError("credential appeared in query string")
        return httpx.Response(
            status,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-store",
                "ETag": ETAG,
            },
            content=json.dumps(body or _body()).encode(),
        )

    return httpx.MockTransport(handler)


def test_client_injects_header_and_validates_private_envelope() -> None:
    with _credential(TOKEN):
        result = _private_api.load_industry_role_review_board(transport=_transport())
    if not isinstance(result, _private_api.IndustryRoleReviewBoardApiAvailable):
        raise AssertionError(result)
    if result.board.operator != "operator" or result.board.roles[0].id != "ai_accelerator":
        raise AssertionError(result)
    if result.etag != ETAG:
        raise AssertionError(result)


def test_mutation_client_sends_one_conditional_idempotent_request() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if str(request.url) != ACTION_URL or request.method != "POST":
            raise AssertionError(request)
        if request.headers.get("Authorization") != f"Bearer {TOKEN}":
            raise AssertionError(request.headers)
        if request.headers.get("If-Match") != ETAG:
            raise AssertionError(request.headers)
        if request.headers.get("Idempotency-Key") != "approve-request-key-0001":
            raise AssertionError(request.headers)
        if json.loads(request.content) != {
            "action": "approve",
            "ticker": "NVDA",
            "primaryRole": "ai_accelerator",
            "secondaryRoles": [],
        }:
            raise AssertionError(request.content)
        return httpx.Response(
            200,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-store",
                "ETag": '"r1-abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"',
            },
            json={
                "operator": "operator",
                "action": "approve",
                "ticker": "NVDA",
                "transactionId": "00000000-0000-4000-8000-000000000001",
                "revision": 1,
                "replayed": False,
            },
        )

    with _credential(TOKEN):
        result = _private_api.mutate_industry_role_review_board(
            {
                "action": "approve",
                "ticker": "NVDA",
                "primaryRole": "ai_accelerator",
                "secondaryRoles": [],
            },
            etag=ETAG,
            idempotency_key="approve-request-key-0001",
            transport=httpx.MockTransport(handler),
        )
    if not isinstance(result, _private_api.IndustryRoleMutationApiSuccess):
        raise AssertionError(result)
    if result.result.revision != 1 or calls != 1:
        raise AssertionError((result, calls))


def test_client_fails_closed_without_valid_local_credential() -> None:
    for credential in (None, "short", "contains whitespace 012345678901234567890"):
        called = False

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal called
            called = True
            raise AssertionError("client called private API without valid credential")

        with _credential(credential):
            result = _private_api.load_industry_role_review_board(
                transport=httpx.MockTransport(handler)
            )
        if not isinstance(result, _private_api.IndustryRoleReviewBoardApiFailure):
            raise AssertionError(result)
        if result.reason != "authentication_unavailable" or called:
            raise AssertionError((result, called))


def test_client_maps_http_and_invalid_envelope_failures_without_leaking_token() -> None:
    invalid = _body()
    invalid["data"]["operator"] = "someone-else"  # type: ignore[index]
    with _credential(TOKEN):
        unauthorized = _private_api.load_industry_role_review_board(
            transport=_transport(status=401)
        )
        malformed = _private_api.load_industry_role_review_board(
            transport=_transport(body=invalid)
        )
    for result, reason in (
        (unauthorized, "http_status"),
        (malformed, "invalid_envelope"),
    ):
        if not isinstance(result, _private_api.IndustryRoleReviewBoardApiFailure):
            raise AssertionError(result)
        if result.reason != reason or TOKEN in repr(result):
            raise AssertionError(result)


def test_page_reads_and_mutates_review_state_only_through_private_api() -> None:
    path = ROOT / "ui/industry_roles.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    loader = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_load_state"
    )
    segment = ast.get_source_segment(source, loader) or ""
    if segment.count("load_industry_role_review_board()") != 1:
        raise AssertionError("Industry Roles must use one protected review-board read")
    for forbidden in (
        "engine.load_taxonomy",
        "engine.load_overrides",
        "engine.load_suggestions",
    ):
        if forbidden in source:
            raise AssertionError(f"Industry Roles retained local read: {forbidden}")
    for forbidden in (
        "engine.generate_suggestions(",
        "engine.review_suggestion(",
    ):
        if forbidden in source:
            raise AssertionError(f"Industry Roles retained local command: {forbidden}")
    if "mutate_industry_role_review_board(" not in source:
        raise AssertionError("Industry Roles did not adopt the private mutation client")


def test_unavailable_or_auth_failure_disables_private_board_commands() -> None:
    outcomes = (
        _private_api.IndustryRoleReviewBoardApiUnavailable("missing"),
        _private_api.IndustryRoleReviewBoardApiFailure(
            "authentication_unavailable"
        ),
    )
    for outcome in outcomes:
        with (
            patch("ui.industry_roles._load_state", return_value=outcome),
            patch("ui.industry_roles._candidate_tickers") as candidate_loader,
        ):
            app = AppTest.from_string(
                "from ui.industry_roles import render\nrender()\n",
                default_timeout=10,
            ).run()
        if app.exception:
            raise AssertionError(app.exception)
        if candidate_loader.called:
            raise AssertionError("private failure continued into candidate reads")
        forbidden_buttons = {"重新產生建議", "核准", "拒絕", "延後"}
        if any(button.label in forbidden_buttons for button in app.button):
            raise AssertionError("private failure left a review command enabled")
        rendered = "\n".join(str(item.value) for item in app.caption)
        if "已停用" not in rendered or outcome.reason in rendered:
            raise AssertionError(rendered)


def main() -> None:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
