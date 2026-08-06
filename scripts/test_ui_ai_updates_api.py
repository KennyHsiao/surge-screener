#!/usr/bin/env python3
"""Behavior tests for the Streamlit AI Updates read-API consumer."""

from __future__ import annotations

import ast
import asyncio
import copy
import inspect
import json
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace
from typing import get_args
from unittest.mock import patch

import httpx
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.models import (  # noqa: E402
    AiUpdateItem,
    AiUpdatesData,
)
from ui import _components, _read_api, sys_ai_updates  # noqa: E402


AI_UPDATES_URL = "http://127.0.0.1:8000/api/v1/system/ai-updates"
AI_UPDATES_MAX_RESPONSE_BYTES = 16 * 1024 * 1024
_AS_OF_DEFAULT = object()


def _update(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "date": "2026-07-15",
        "title": "AI Update",
        "summary": "A safe public summary.",
        "link": "https://example.com/deepen",
        "tags": ["agent", "research"],
    }
    item.update(overrides)
    return item


def _available(
    updates: list[dict[str, object]],
    *,
    as_of: object = _AS_OF_DEFAULT,
    source_id: str = "system.ai-updates",
    generated_at: str | None = None,
) -> dict[str, object]:
    if as_of is _AS_OF_DEFAULT:
        as_of = max((str(item["date"]) for item in updates), default=None)
    return {
        "available": True,
        "reason": "ok",
        "data": {"updates": updates},
        "meta": {
            "sourceId": source_id,
            "asOf": as_of,
            "generatedAt": generated_at,
        },
    }


def _unavailable(
    reason: str,
    *,
    as_of: str | None = None,
    source_id: str = "system.ai-updates",
    generated_at: str | None = None,
) -> dict[str, object]:
    return {
        "available": False,
        "reason": reason,
        "data": None,
        "meta": {
            "sourceId": source_id,
            "asOf": as_of,
            "generatedAt": generated_at,
        },
    }


def _json_response(
    payload: object,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    response_headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "private, NO-STORE",
    }
    if headers is not None:
        response_headers = headers
    return httpx.Response(status_code, json=payload, headers=response_headers)


def _load_with_response(response: httpx.Response) -> object:
    return _read_api.load_ai_updates(
        transport=httpx.MockTransport(lambda _request: response)
    )


def _item(**overrides: object) -> AiUpdateItem:
    return AiUpdateItem.model_validate(_update(**overrides), strict=True)


def _state(
    status: str,
    updates: tuple[AiUpdateItem, ...] = (),
    reason: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(status=status, updates=updates, reason=reason)


def _app_text(app: AppTest) -> str:
    values: list[str] = []
    for elements in (app.header, app.caption, app.warning, app.info, app.markdown):
        values.extend(str(element.value) for element in elements)
    return "\n".join(values)


class TrackingAsyncStream(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.yielded = 0
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            self.yielded += 1
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


def _assert_transport_only_signature(function: object) -> None:
    signature = inspect.signature(function)
    parameters = list(signature.parameters.values())
    if len(parameters) != 1:
        raise AssertionError(signature)
    parameter = parameters[0]
    if (
        parameter.name != "transport"
        or parameter.kind is not inspect.Parameter.KEYWORD_ONLY
        or parameter.default is not None
    ):
        raise AssertionError(signature)


def test_public_and_private_signatures_keep_the_fixed_trust_boundary() -> None:
    _assert_transport_only_signature(_read_api.load_schedules)
    _assert_transport_only_signature(_read_api.load_ai_updates)

    helper = _read_api._read_fixed_json
    if not inspect.iscoroutinefunction(helper):
        raise AssertionError("_read_fixed_json must remain async")
    signature = inspect.signature(helper)
    parameters = list(signature.parameters.values())
    if [parameter.name for parameter in parameters] != [
        "url",
        "max_response_bytes",
        "transport",
    ]:
        raise AssertionError(signature)
    if any(
        parameter.kind is not inspect.Parameter.KEYWORD_ONLY
        or parameter.default is not inspect.Parameter.empty
        for parameter in parameters
    ):
        raise AssertionError(signature)


def test_shared_reader_returns_raw_bytes_and_endpoints_validate_them() -> None:
    raw = json.dumps(
        {
            "available": True,
            "reason": "ok",
            "data": {"unexpected": ["body-secret"]},
            "meta": {
                "sourceId": "system.ai-updates",
                "asOf": None,
                "generatedAt": None,
            },
        }
    ).encode()

    async def read_raw() -> object:
        return await _read_api._read_fixed_json(
            url=AI_UPDATES_URL,
            max_response_bytes=1024,
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    content=raw,
                    headers={
                        "Content-Type": "application/json",
                        "Cache-Control": "no-store",
                    },
                )
            ),
        )

    shared_result = asyncio.run(read_raw())
    if shared_result != raw or not isinstance(shared_result, bytes):
        raise AssertionError(shared_result)

    def response() -> httpx.Response:
        return httpx.Response(
            200,
            content=raw,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-store",
            },
        )

    schedules = _read_api.load_schedules(
        transport=httpx.MockTransport(lambda _request: response())
    )
    ai_updates = _read_api.load_ai_updates(
        transport=httpx.MockTransport(lambda _request: response())
    )
    if not isinstance(schedules, _read_api.SchedulesApiFailure):
        raise AssertionError(schedules)
    if schedules.reason != "invalid_envelope":
        raise AssertionError(schedules)
    if not isinstance(ai_updates, _read_api.AiUpdatesApiFailure):
        raise AssertionError(ai_updates)
    if ai_updates.reason != "invalid_envelope" or "body-secret" in repr(ai_updates):
        raise AssertionError(ai_updates)


def test_available_request_is_fixed_configured_and_source_ordered() -> None:
    requests: list[httpx.Request] = []
    ordered = [
        _update(
            date="2026-07-13",
            title="First source item",
            summary="來源順序第一筆",
            link="",
            tags=["first"],
        ),
        _update(
            date="2026-07-15",
            title="Second source item",
            summary="來源順序第二筆",
            tags=["second", "unicode-測試"],
        ),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _json_response(_available(ordered))

    result = _read_api.load_ai_updates(transport=httpx.MockTransport(handler))
    if not isinstance(result, _read_api.AiUpdatesApiAvailable):
        raise AssertionError(result)
    if [item.title for item in result.updates] != [
        "First source item",
        "Second source item",
    ]:
        raise AssertionError(result)
    if [item.model_dump() for item in result.updates] != ordered:
        raise AssertionError(result)
    if len(requests) != 1:
        raise AssertionError(requests)
    request = requests[0]
    if request.method != "GET" or str(request.url) != AI_UPDATES_URL:
        raise AssertionError((request.method, request.url))
    if request.url.query or request.headers.get("accept") != "application/json":
        raise AssertionError((request.url, request.headers))
    if request.extensions.get("timeout") != {
        "connect": 0.25,
        "read": 0.25,
        "write": 0.25,
        "pool": 0.25,
    }:
        raise AssertionError(request.extensions)
    if _read_api._DEADLINE_SECONDS != 1.0:
        raise AssertionError(_read_api._DEADLINE_SECONDS)

    real_client = httpx.AsyncClient
    recorded: list[dict[str, object]] = []

    def recorder(*args, **kwargs):
        recorded.append(dict(kwargs))
        kwargs["transport"] = httpx.MockTransport(
            lambda _request: _json_response(_available([]))
        )
        return real_client(*args, **kwargs)

    with patch("ui._read_api.httpx.AsyncClient", side_effect=recorder):
        configured = _read_api.load_ai_updates()
    if not isinstance(configured, _read_api.AiUpdatesApiAvailable):
        raise AssertionError(configured)
    if len(recorded) != 1:
        raise AssertionError(recorded)
    options = recorded[0]
    if options.get("trust_env") is not False or options.get("follow_redirects") is not False:
        raise AssertionError(options)
    timeout = options.get("timeout")
    if not isinstance(timeout, httpx.Timeout):
        raise AssertionError(timeout)
    if (timeout.connect, timeout.read, timeout.write, timeout.pool) != (
        0.25,
        0.25,
        0.25,
        0.25,
    ):
        raise AssertionError(timeout)


def test_metadata_empty_unavailable_and_strict_dto_contracts() -> None:
    valid = _load_with_response(
        _json_response(
            _available(
                [
                    _update(date="2026-07-12", title="Older"),
                    _update(date="2026-07-15", title="Newest"),
                    _update(date="2026-07-14", title="Middle"),
                ]
            )
        )
    )
    if not isinstance(valid, _read_api.AiUpdatesApiAvailable):
        raise AssertionError(valid)

    empty = _load_with_response(_json_response(_available([])))
    if not isinstance(empty, _read_api.AiUpdatesApiAvailable) or empty.updates:
        raise AssertionError(empty)

    for reason in ("missing", "invalid_json", "invalid_shape", "unreadable"):
        result = _load_with_response(_json_response(_unavailable(reason)))
        if not isinstance(result, _read_api.AiUpdatesApiUnavailable):
            raise AssertionError((reason, result))
        if result.reason != reason:
            raise AssertionError((reason, result))

    invalid_payloads: list[tuple[str, object]] = [
        (
            "wrong-source",
            _available([_update()], source_id="system.schedules"),
        ),
        (
            "generated-at",
            _available(
                [_update()],
                generated_at="2026-07-15T00:00:00Z",
            ),
        ),
        (
            "wrong-as-of",
            _available([_update(date="2026-07-15")], as_of="2026-07-14"),
        ),
        (
            "null-as-of-nonempty",
            _available([_update(date="2026-07-15")], as_of=None),
        ),
        (
            "non-null-empty-as-of",
            _available([], as_of="2026-07-15"),
        ),
        (
            "unavailable-as-of",
            _unavailable("missing", as_of="2026-07-15"),
        ),
    ]

    data_note = _available([_update()])
    data_note["data"]["_note"] = "body-secret"  # type: ignore[index]
    invalid_payloads.append(("data-note", data_note))

    item_extra = _available([_update()])
    item_extra["data"]["updates"][0]["extra"] = "body-secret"  # type: ignore[index]
    invalid_payloads.append(("item-extra", item_extra))
    invalid_payloads.extend(
        [
            (
                "invalid-calendar-date",
                _available([_update(date="2026-02-30")]),
            ),
            (
                "unsafe-link",
                _available([_update(link="http://evil.invalid/body-secret")]),
            ),
            (
                "duplicate-tags",
                _available([_update(tags=["same", "same"])]),
            ),
        ]
    )

    for label, payload in invalid_payloads:
        result = _load_with_response(_json_response(payload))
        if not isinstance(result, _read_api.AiUpdatesApiFailure):
            raise AssertionError((label, result))
        if result.reason != "invalid_envelope":
            raise AssertionError((label, result))
        if "body-secret" in repr(result) or "evil.invalid" in repr(result):
            raise AssertionError((label, result))

    malformed = _load_with_response(
        httpx.Response(
            200,
            content=b'{"available":',
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-store",
            },
        )
    )
    if not isinstance(malformed, _read_api.AiUpdatesApiFailure):
        raise AssertionError(malformed)
    if malformed.reason != "invalid_envelope":
        raise AssertionError(malformed)


def test_complete_seven_reason_failure_matrix_is_stable_and_sanitized() -> None:
    expected_reasons = {
        "transport_error",
        "deadline_exceeded",
        "http_status",
        "invalid_media_type",
        "invalid_cache_control",
        "response_too_large",
        "invalid_envelope",
    }
    if set(get_args(_read_api.ClientFailureReason)) != expected_reasons:
        raise AssertionError(get_args(_read_api.ClientFailureReason))

    outcomes: dict[str, object] = {}

    def transport_error(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("transport-secret", request=request)

    outcomes["transport_error"] = _read_api.load_ai_updates(
        transport=httpx.MockTransport(transport_error)
    )

    async def slow_reader(
        *,
        url: str,
        max_response_bytes: int,
        transport: httpx.AsyncBaseTransport | None,
    ) -> bytes:
        _ = (url, max_response_bytes, transport)
        await asyncio.sleep(1)
        return b"{}"

    with (
        patch("ui._read_api._read_fixed_json", new=slow_reader),
        patch("ui._read_api._DEADLINE_SECONDS", 0.01),
    ):
        outcomes["deadline_exceeded"] = _read_api.load_ai_updates()

    redirect_calls = 0

    def redirect(_request: httpx.Request) -> httpx.Response:
        nonlocal redirect_calls
        redirect_calls += 1
        return httpx.Response(
            302,
            headers={"Location": "http://evil.invalid/body-secret"},
        )

    outcomes["http_status"] = _read_api.load_ai_updates(
        transport=httpx.MockTransport(redirect)
    )
    if redirect_calls != 1:
        raise AssertionError(redirect_calls)

    outcomes["invalid_media_type"] = _load_with_response(
        httpx.Response(
            200,
            content=json.dumps(_available([])).encode(),
            headers={"Content-Type": "text/html", "Cache-Control": "no-store"},
        )
    )
    outcomes["invalid_cache_control"] = _load_with_response(
        httpx.Response(
            200,
            content=json.dumps(_available([])).encode(),
            headers={"Content-Type": "application/json", "Cache-Control": "max-age=60"},
        )
    )

    oversized_stream = TrackingAsyncStream(
        [b"x" * (AI_UPDATES_MAX_RESPONSE_BYTES + 1), b"must-not-be-read"]
    )
    outcomes["response_too_large"] = _load_with_response(
        httpx.Response(
            200,
            stream=oversized_stream,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-store",
            },
        )
    )
    if oversized_stream.yielded != 1 or not oversized_stream.closed:
        raise AssertionError((oversized_stream.yielded, oversized_stream.closed))

    outcomes["invalid_envelope"] = _load_with_response(
        httpx.Response(
            200,
            content=b'{"body-secret": true}',
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-store",
            },
        )
    )

    for expected_reason, result in outcomes.items():
        if not isinstance(result, _read_api.AiUpdatesApiFailure):
            raise AssertionError((expected_reason, result))
        if result.reason != expected_reason:
            raise AssertionError((expected_reason, result))
        rendered = repr(result)
        for forbidden in ("transport-secret", "evil.invalid", "body-secret"):
            if forbidden in rendered:
                raise AssertionError((expected_reason, rendered))
    if set(outcomes) != expected_reasons:
        raise AssertionError(outcomes)


def test_ai_size_cap_accepts_maximum_valid_exact_cap_and_closes_cap_plus_one() -> None:
    astral = "\U0001f600"
    link_prefix = "https://example.com/"
    maximum_link = link_prefix + (astral * (2048 - len(link_prefix)))
    maximum_tags = [astral * 49 + chr(0x1F680 + index) for index in range(20)]
    maximum_update = _update(
        title=astral * 200,
        summary=astral * 2000,
        link=maximum_link,
        tags=maximum_tags,
    )
    maximum_updates = [copy.deepcopy(maximum_update) for _ in range(200)]
    parsed = AiUpdatesData.model_validate(
        {"updates": maximum_updates},
        strict=True,
    )
    if len(parsed.updates) != 200:
        raise AssertionError(len(parsed.updates))
    if len(maximum_link) != 2048 or any(len(tag) != 50 for tag in maximum_tags):
        raise AssertionError((len(maximum_link), [len(tag) for tag in maximum_tags]))

    maximum_body = json.dumps(
        _available(maximum_updates),
        ensure_ascii=True,
    ).encode()
    if len(maximum_body) >= AI_UPDATES_MAX_RESPONSE_BYTES:
        raise AssertionError((len(maximum_body), AI_UPDATES_MAX_RESPONSE_BYTES))
    maximum_result = _load_with_response(
        httpx.Response(
            200,
            content=maximum_body,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-store",
            },
        )
    )
    if not isinstance(maximum_result, _read_api.AiUpdatesApiAvailable):
        raise AssertionError(maximum_result)
    if len(maximum_result.updates) != 200:
        raise AssertionError(len(maximum_result.updates))

    exact_body = maximum_body + (
        b" " * (AI_UPDATES_MAX_RESPONSE_BYTES - len(maximum_body))
    )
    if len(exact_body) != AI_UPDATES_MAX_RESPONSE_BYTES:
        raise AssertionError(len(exact_body))
    exact_result = _load_with_response(
        httpx.Response(
            200,
            content=exact_body,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-store",
            },
        )
    )
    if not isinstance(exact_result, _read_api.AiUpdatesApiAvailable):
        raise AssertionError(exact_result)
    if len(exact_result.updates) != 200:
        raise AssertionError(len(exact_result.updates))

    cap_plus_one = TrackingAsyncStream([exact_body, b" ", b"must-not-be-read"])
    oversized = _load_with_response(
        httpx.Response(
            200,
            stream=cap_plus_one,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-store",
            },
        )
    )
    if not isinstance(oversized, _read_api.AiUpdatesApiFailure):
        raise AssertionError(oversized)
    if oversized.reason != "response_too_large":
        raise AssertionError(oversized)
    if cap_plus_one.yielded != 2 or not cap_plus_one.closed:
        raise AssertionError((cap_plus_one.yielded, cap_plus_one.closed))


def test_authoritative_unavailable_never_reads_local_artifact() -> None:
    for reason in ("missing", "invalid_json", "invalid_shape", "unreadable"):
        with patch(
            "ui.sys_ai_updates._read_api.load_ai_updates",
            return_value=_read_api.AiUpdatesApiUnavailable(reason),
        ):
            state = sys_ai_updates._load_updates()
        if state.status != "api_unavailable" or state.reason != reason:
            raise AssertionError((reason, state))
        if state.updates:
            raise AssertionError((reason, state))

    available = _read_api.AiUpdatesApiAvailable((_item(),))
    with patch("ui.sys_ai_updates._read_api.load_ai_updates", return_value=available):
        state = sys_ai_updates._load_updates()
    if state.status != "api_available" or len(state.updates) != 1:
        raise AssertionError(state)


def test_client_failure_is_api_only_and_never_reads_local_artifacts() -> None:
    for reason in get_args(_read_api.ClientFailureReason):
        with patch(
            "ui.sys_ai_updates._read_api.load_ai_updates",
            return_value=_read_api.AiUpdatesApiFailure(reason),
        ):
            state = sys_ai_updates._load_updates()
        if state.status != "api_failure" or state.reason != reason or state.updates:
            raise AssertionError((reason, state))

    source = (ROOT / "ui" / "sys_ai_updates.py").read_text(encoding="utf-8")
    for forbidden in (
        "read_artifact",
        "ARTIFACTS",
        "api.artifacts",
        "scripts.artifact_loader",
        "local_fallback",
    ):
        if forbidden in source:
            raise AssertionError(f"AI Updates retained a local bypass: {forbidden}")


def test_failed_rerun_recovers_immediately_without_negative_cache() -> None:
    api_item = _item(date="2026-07-16", title="Recovered API")
    api_results = [
        _read_api.AiUpdatesApiFailure("transport_error"),
        _read_api.AiUpdatesApiAvailable((api_item,)),
    ]
    with patch(
        "ui.sys_ai_updates._read_api.load_ai_updates",
        side_effect=api_results,
    ) as api_read:
        first = sys_ai_updates._load_updates()
        second = sys_ai_updates._load_updates()
    if first.status != "api_failure" or first.updates:
        raise AssertionError(first)
    if second.status != "api_available":
        raise AssertionError(second)
    if [item.title for item in second.updates] != ["Recovered API"]:
        raise AssertionError(second)
    if api_read.call_count != 2:
        raise AssertionError(api_read.call_count)


def test_client_failure_exposes_only_the_fixed_reason_code() -> None:
    state = sys_ai_updates.AiUpdatesFeedState(
        "api_failure",
        (),
        "transport_error",
    )
    wrapper = "from ui.sys_ai_updates import render\nrender()\n"
    with patch("ui.sys_ai_updates._load_updates", return_value=state):
        app = AppTest.from_string(wrapper, default_timeout=10).run()
    if app.exception:
        raise AssertionError(app.exception)
    if "連線暫時失敗" not in _app_text(app):
        raise AssertionError(_app_text(app))


def test_resolver_sorts_newest_first_stably_for_same_date_ties() -> None:
    source_order = (
        _item(date="2026-07-14", title="Tie first"),
        _item(date="2026-07-13", title="Older"),
        _item(date="2026-07-14", title="Tie second"),
        _item(date="2026-07-15", title="Newest"),
    )
    with patch(
        "ui.sys_ai_updates._read_api.load_ai_updates",
        return_value=_read_api.AiUpdatesApiAvailable(source_order),
    ):
        state = sys_ai_updates._load_updates()
    if state.status != "api_available":
        raise AssertionError(state)
    if [item.title for item in state.updates] != [
        "Newest",
        "Tie first",
        "Tie second",
        "Older",
    ]:
        raise AssertionError(state)


def test_tag_threshold_empty_default_and_intersection_or_filtering() -> None:
    wrapper = "from ui.sys_ai_updates import render\nrender()\n"
    three_tags = (
        _item(title="Three-tag item", tags=["alpha", "beta", "gamma"]),
    )
    with patch(
        "ui.sys_ai_updates._load_updates",
        return_value=_state("api_available", three_tags),
    ):
        app = AppTest.from_string(wrapper, default_timeout=10).run()
    if app.exception or app.multiselect:
        raise AssertionError((app.exception, app.multiselect))
    if "Three-tag item" not in _app_text(app):
        raise AssertionError(_app_text(app))

    four_tags = (
        _item(title="Alpha item", tags=["alpha"]),
        _item(title="Beta item", tags=["beta"]),
        _item(title="Gamma item", tags=["gamma"]),
        _item(title="Delta item", tags=["delta"]),
    )
    with patch(
        "ui.sys_ai_updates._load_updates",
        return_value=_state("api_available", four_tags),
    ):
        app = AppTest.from_string(wrapper, default_timeout=10).run()
        if app.exception or len(app.multiselect) != 1:
            raise AssertionError((app.exception, app.multiselect))
        selector = app.multiselect[0]
        if selector.value != []:
            raise AssertionError(selector.value)
        if selector.options != ["alpha", "beta", "delta", "gamma"]:
            raise AssertionError(selector.options)
        selector.set_value(["alpha", "gamma"])
        app = app.run()

    if app.exception:
        raise AssertionError(app.exception)
    markdown = [element.value for element in app.markdown]
    for expected in ("**Alpha item**", "**Gamma item**"):
        if expected not in markdown:
            raise AssertionError(markdown)
    for excluded in ("**Beta item**", "**Delta item**"):
        if excluded in markdown:
            raise AssertionError(markdown)


def test_optional_links_and_no_match_copy_are_preserved() -> None:
    wrapper = "from ui.sys_ai_updates import render\nrender()\n"
    linked = (
        _item(
            title="Linked",
            summary="Visible rendered summary",
            link="https://example.com/deepen?source=ai",
            tags=["one"],
        ),
        _item(title="No link", link="", tags=["two"]),
    )
    with patch(
        "ui.sys_ai_updates._load_updates",
        return_value=_state("api_available", linked),
    ):
        app = AppTest.from_string(wrapper, default_timeout=10).run()
    if app.exception:
        raise AssertionError(app.exception)
    markdown = [element.value for element in app.markdown]
    if "Visible rendered summary" not in markdown:
        raise AssertionError(markdown)
    if "標籤：one" not in [element.value for element in app.text]:
        raise AssertionError([element.value for element in app.text])
    if any("<span" in str(value) for value in markdown):
        raise AssertionError(markdown)
    links = app.get("link_button")
    if len(links) != 1:
        raise AssertionError(links)
    if links[0].proto.label != "深化連結":
        raise AssertionError(links[0].proto)
    if links[0].proto.url != "https://example.com/deepen?source=ai":
        raise AssertionError(links[0].proto)

    no_match_feed = (
        _item(title="Alpha", tags=["alpha"]),
        _item(title="Beta", tags=["beta"]),
        _item(title="Gamma", tags=["gamma"]),
        _item(title="Delta", tags=["delta"]),
    )
    with (
        patch(
            "ui.sys_ai_updates._load_updates",
            return_value=_state("api_available", no_match_feed),
        ),
        patch("ui.sys_ai_updates.st.multiselect", return_value=["absent"]),
    ):
        no_match = AppTest.from_string(wrapper, default_timeout=10).run()
    if no_match.exception:
        raise AssertionError(no_match.exception)
    if "沒有符合所選標籤的更新。" not in [item.value for item in no_match.info]:
        raise AssertionError([item.value for item in no_match.info])


def test_all_four_authoritative_unavailable_messages_are_exact() -> None:
    expected = {
        "missing": "找不到 AI 更新資料。",
        "invalid_json": "AI 更新資料尚未完整寫入或 JSON 格式無效。",
        "invalid_shape": "AI 更新資料格式不符合預期。",
        "unreadable": "AI 更新資料目前無法讀取。",
    }
    wrapper = "from ui.sys_ai_updates import render\nrender()\n"
    for reason, detail in expected.items():
        message = f"AI 更新資料目前無法使用：{detail}"
        if sys_ai_updates._unavailable_message(reason) != message:
            raise AssertionError((reason, sys_ai_updates._unavailable_message(reason)))
        with patch(
            "ui.sys_ai_updates._load_updates",
            return_value=_state("api_unavailable", reason=reason),
        ):
            app = AppTest.from_string(wrapper, default_timeout=10).run()
        if app.exception:
            raise AssertionError((reason, app.exception))
        state = sys_ai_updates._data_state(
            sys_ai_updates.AiUpdatesFeedState("api_unavailable", (), reason)
        )
        if (
            state.source,
            state.content,
            state.freshness,
            state.operation,
            state.reason_code,
        ) != ("unavailable", "unknown", "unknown", "idle", reason):
            raise AssertionError((reason, state))
        rendered = _app_text(app)
        for expected_text in (
            "權威來源不可用",
            "內容狀態未知",
            "新鮮度未知",
            _components.REASON_LABELS[reason],
        ):
            if expected_text not in rendered:
                raise AssertionError((reason, rendered))


def test_streamlit_app_renders_all_four_api_only_feed_states_without_exception() -> None:
    wrapper = "from ui.sys_ai_updates import render\nrender()\n"
    item = _item(title="Rendered update", link="", tags=["safe"])
    cases = [
        (
            _state("api_available", (item,)),
            None,
            "Rendered update",
        ),
        (
            _state("api_available"),
            None,
            "目前沒有資料",
        ),
        (
            _state("api_unavailable", reason="missing"),
            "權威來源不可用",
            "找不到資料",
        ),
        (
            _state("api_failure", reason="invalid_envelope"),
            "權威來源不可用",
            "服務回應格式不符",
        ),
    ]
    for state, expected_warning, expected_text in cases:
        with patch("ui.sys_ai_updates._load_updates", return_value=state):
            app = AppTest.from_string(wrapper, default_timeout=10).run()
        if app.exception:
            raise AssertionError((state, app.exception))
        warnings = [item.value for item in app.warning]
        rendered = _app_text(app)
        if expected_warning is None and warnings:
            raise AssertionError((state, warnings))
        if expected_warning is not None and not any(
            expected_warning in str(value) for value in warnings
        ):
            raise AssertionError((state, warnings))
        if expected_text not in rendered:
            raise AssertionError((state, rendered))


def test_ai_client_outcomes_are_immutable() -> None:
    mutations = [
        (_read_api.AiUpdatesApiAvailable((_item(),)), "updates", ()),
        (_read_api.AiUpdatesApiUnavailable("missing"), "reason", "unreadable"),
        (
            _read_api.AiUpdatesApiFailure("transport_error"),
            "reason",
            "http_status",
        ),
    ]
    for outcome, field, value in mutations:
        try:
            setattr(outcome, field, value)
        except FrozenInstanceError:
            continue
        raise AssertionError(outcome)


def test_sources_are_python310_compatible_and_client_is_framework_neutral() -> None:
    paths = [
        ROOT / "ui" / "_read_api.py",
        ROOT / "ui" / "sys_ai_updates.py",
        ROOT / "scripts" / "test_ui_ai_updates_api.py",
    ]
    for path in paths:
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
            feature_version=(3, 10),
        )

    client_path = ROOT / "ui" / "_read_api.py"
    client_source = client_path.read_text(encoding="utf-8")
    client_tree = ast.parse(
        client_source,
        filename=str(client_path),
        feature_version=(3, 10),
    )
    imported: set[str] = set()
    for node in ast.walk(client_tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    if "api.main" in imported or "streamlit" in imported:
        raise AssertionError(imported)
    if "st.cache_data" in client_source or "asyncio.timeout(" in client_source:
        raise AssertionError("client must be uncached and Python 3.10 compatible")

    page_source = (ROOT / "ui" / "sys_ai_updates.py").read_text(encoding="utf-8")
    for forbidden in (
        "st.cache_data",
        "_shared",
        "_shared.load_json",
        "read_artifact",
        "scripts.artifact_loader",
    ):
        if forbidden in page_source:
            raise AssertionError(f"page resolver must be API-only: {forbidden}")


def main() -> None:
    tests = [
        test_public_and_private_signatures_keep_the_fixed_trust_boundary,
        test_shared_reader_returns_raw_bytes_and_endpoints_validate_them,
        test_available_request_is_fixed_configured_and_source_ordered,
        test_metadata_empty_unavailable_and_strict_dto_contracts,
        test_complete_seven_reason_failure_matrix_is_stable_and_sanitized,
        test_ai_size_cap_accepts_maximum_valid_exact_cap_and_closes_cap_plus_one,
        test_authoritative_unavailable_never_reads_local_artifact,
        test_client_failure_is_api_only_and_never_reads_local_artifacts,
        test_failed_rerun_recovers_immediately_without_negative_cache,
        test_client_failure_exposes_only_the_fixed_reason_code,
        test_resolver_sorts_newest_first_stably_for_same_date_ties,
        test_tag_threshold_empty_default_and_intersection_or_filtering,
        test_optional_links_and_no_match_copy_are_preserved,
        test_all_four_authoritative_unavailable_messages_are_exact,
        test_streamlit_app_renders_all_four_api_only_feed_states_without_exception,
        test_ai_client_outcomes_are_immutable,
        test_sources_are_python310_compatible_and_client_is_framework_neutral,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
