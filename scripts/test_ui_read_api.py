#!/usr/bin/env python3
"""Behavior tests for the Streamlit schedules read-API consumer."""

from __future__ import annotations

import ast
import gzip
import json
import socket
import sys
import threading
import time
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

import httpx
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.models import ScheduleEntry  # noqa: E402
from ui import _read_api, sys_schedules  # noqa: E402


def _schedule(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "id": "job_one",
        "name": "Job One",
        "category": "系統",
        "cron": "0 1 * * *",
        "cron_note": "每天 01:00",
        "description": "Safe schedule",
        "result_type": "unknown_result",
    }
    item.update(overrides)
    return item


def _available(schedules: list[dict[str, object]]) -> dict[str, object]:
    return {
        "available": True,
        "reason": "ok",
        "data": {"schedules": schedules},
        "meta": {
            "sourceId": "system.schedules",
            "asOf": None,
            "generatedAt": None,
        },
    }


def _unavailable(reason: str) -> dict[str, object]:
    return {
        "available": False,
        "reason": reason,
        "data": None,
        "meta": {
            "sourceId": "system.schedules",
            "asOf": None,
            "generatedAt": None,
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
    return _read_api.load_schedules(
        transport=httpx.MockTransport(lambda _request: response)
    )


def _entry(**overrides: object) -> ScheduleEntry:
    return ScheduleEntry.model_validate(_schedule(**overrides), strict=True)


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


class FailingAsyncStream(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.closed = False

    async def __aiter__(self):
        raise httpx.ReadError("read-secret")
        yield b"unreachable"

    async def aclose(self) -> None:
        self.closed = True


def test_available_request_is_fixed_strict_and_ordered() -> None:
    requests: list[httpx.Request] = []
    ordered = [
        _schedule(id="first", name="First"),
        _schedule(id="second", name="Second"),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _json_response(_available(ordered))

    result = _read_api.load_schedules(transport=httpx.MockTransport(handler))
    if not isinstance(result, _read_api.SchedulesApiAvailable):
        raise AssertionError(result)
    if [item.id for item in result.schedules] != ["first", "second"]:
        raise AssertionError(result)
    if [item.model_dump() for item in result.schedules] != ordered:
        raise AssertionError(result)
    if len(requests) != 1:
        raise AssertionError(requests)
    request = requests[0]
    if request.method != "GET" or str(request.url) != (
        "http://127.0.0.1:8000/api/v1/system/schedules"
    ):
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


def test_async_client_configuration_is_explicit() -> None:
    real_client = httpx.AsyncClient
    recorded: list[dict[str, object]] = []

    def recorder(*args, **kwargs):
        recorded.append(dict(kwargs))
        kwargs["transport"] = httpx.MockTransport(
            lambda _request: _json_response(_available([]))
        )
        return real_client(*args, **kwargs)

    with patch("ui._read_api.httpx.AsyncClient", side_effect=recorder):
        result = _read_api.load_schedules()
    if not isinstance(result, _read_api.SchedulesApiAvailable):
        raise AssertionError(result)
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


def test_empty_and_all_unavailable_reasons_are_typed() -> None:
    empty = _load_with_response(_json_response(_available([])))
    if not isinstance(empty, _read_api.SchedulesApiAvailable) or empty.schedules:
        raise AssertionError(empty)

    for reason in ("missing", "invalid_json", "invalid_shape", "unreadable"):
        result = _load_with_response(_json_response(_unavailable(reason)))
        if not isinstance(result, _read_api.SchedulesApiUnavailable):
            raise AssertionError((reason, result))
        if result.reason != reason:
            raise AssertionError((reason, result))


def test_client_failure_matrix_is_stable_and_sanitized() -> None:
    invalid_envelopes = [
        b'{"available":',
        json.dumps({**_available([]), "secret": "body-secret"}).encode(),
        json.dumps(
            {
                **_available([]),
                "data": {"schedules": [], "_note": "body-secret"},
            }
        ).encode(),
        json.dumps(
            {
                **_available([]),
                "meta": {
                    "sourceId": "system.schedules",
                    "asOf": None,
                    "generatedAt": "2026-07-15T00:00:00Z",
                },
            }
        ).encode(),
        json.dumps(
            {
                **_available([]),
                "meta": {
                    "sourceId": "system.ai-updates",
                    "asOf": None,
                    "generatedAt": None,
                },
            }
        ).encode(),
        json.dumps(
            {
                **_available([]),
                "meta": {
                    "sourceId": "system.schedules",
                    "asOf": "2026-07-15",
                    "generatedAt": None,
                },
            }
        ).encode(),
    ]
    cases: list[tuple[str, httpx.Response, str]] = [
        (
            "redirect",
            httpx.Response(307, headers={"Location": "http://evil.invalid/"}),
            "http_status",
        ),
        ("not-found", httpx.Response(404), "http_status"),
        ("server", httpx.Response(500), "http_status"),
        (
            "media-missing",
            httpx.Response(
                200,
                content=json.dumps(_available([])).encode(),
                headers={"Cache-Control": "no-store"},
            ),
            "invalid_media_type",
        ),
        (
            "media",
            httpx.Response(
                200,
                content=json.dumps(_available([])).encode(),
                headers={"Content-Type": "text/html", "Cache-Control": "no-store"},
            ),
            "invalid_media_type",
        ),
        (
            "cache-missing",
            httpx.Response(
                200,
                content=json.dumps(_available([])).encode(),
                headers={"Content-Type": "application/json"},
            ),
            "invalid_cache_control",
        ),
        (
            "cache",
            httpx.Response(
                200,
                content=json.dumps(_available([])).encode(),
                headers={"Content-Type": "application/json", "Cache-Control": "max-age=60"},
            ),
            "invalid_cache_control",
        ),
    ]
    cases.extend(
        (
            f"envelope-{index}",
            httpx.Response(
                200,
                content=body,
                headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
            ),
            "invalid_envelope",
        )
        for index, body in enumerate(invalid_envelopes)
    )

    for label, response, expected_reason in cases:
        result = _load_with_response(response)
        if not isinstance(result, _read_api.SchedulesApiFailure):
            raise AssertionError((label, result))
        if result.reason != expected_reason:
            raise AssertionError((label, result))
        rendered = repr(result)
        if "body-secret" in rendered or "evil.invalid" in rendered:
            raise AssertionError((label, rendered))

    calls = 0

    def redirect_handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(302, headers={"Location": "http://127.0.0.1:8000/healthz"})

    result = _read_api.load_schedules(transport=httpx.MockTransport(redirect_handler))
    if not isinstance(result, _read_api.SchedulesApiFailure) or calls != 1:
        raise AssertionError((result, calls))

    def transport_error(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("transport-secret", request=request)

    result = _read_api.load_schedules(transport=httpx.MockTransport(transport_error))
    if not isinstance(result, _read_api.SchedulesApiFailure):
        raise AssertionError(result)
    if result.reason != "transport_error" or "transport-secret" in repr(result):
        raise AssertionError(result)

    failing_stream = FailingAsyncStream()
    read_failure = httpx.Response(
        200,
        stream=failing_stream,
        headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
    )
    result = _load_with_response(read_failure)
    if not isinstance(result, _read_api.SchedulesApiFailure):
        raise AssertionError(result)
    if result.reason != "transport_error" or "read-secret" in repr(result):
        raise AssertionError(result)
    if not failing_stream.closed:
        raise AssertionError("read-failing response stream was not closed")

    invalid_header_stream = TrackingAsyncStream([b"must-not-be-read"])
    invalid_header = httpx.Response(
        200,
        stream=invalid_header_stream,
        headers={"Content-Type": "text/plain", "Cache-Control": "no-store"},
    )
    result = _load_with_response(invalid_header)
    if not isinstance(result, _read_api.SchedulesApiFailure):
        raise AssertionError(result)
    if result.reason != "invalid_media_type":
        raise AssertionError(result)
    if invalid_header_stream.yielded != 0 or not invalid_header_stream.closed:
        raise AssertionError(
            (invalid_header_stream.yielded, invalid_header_stream.closed)
        )


def test_decoded_size_cap_accepts_maximum_and_closes_oversize_stream() -> None:
    edge = "a" + ("\x00" * 1998) + "b"
    note_edge = "a" + ("\x00" * 498) + "b"
    schedules = [
        _schedule(
            id=f"job_{index:03d}",
            name="n" * 100,
            category="c" * 50,
            cron="x" * 100,
            cron_note=note_edge,
            description=edge,
            result_type=f"result_{index:03d}",
        )
        for index in range(100)
    ]
    maximum_body = json.dumps(_available(schedules), ensure_ascii=True).encode()
    if len(maximum_body) >= _read_api._MAX_RESPONSE_BYTES:
        raise AssertionError((len(maximum_body), _read_api._MAX_RESPONSE_BYTES))
    maximum_body += b" " * (_read_api._MAX_RESPONSE_BYTES - len(maximum_body))
    if len(maximum_body) != _read_api._MAX_RESPONSE_BYTES:
        raise AssertionError(len(maximum_body))
    maximum = _load_with_response(
        httpx.Response(
            200,
            content=maximum_body,
            headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        )
    )
    if not isinstance(maximum, _read_api.SchedulesApiAvailable):
        raise AssertionError(maximum)
    if len(maximum.schedules) != 100:
        raise AssertionError(len(maximum.schedules))

    expanded = b"x" * (_read_api._MAX_RESPONSE_BYTES + 1)
    stream = TrackingAsyncStream([gzip.compress(expanded), b"must-not-be-read"])
    response = httpx.Response(
        200,
        stream=stream,
        headers={
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
            "Content-Encoding": "gzip",
        },
    )
    result = _load_with_response(response)
    if not isinstance(result, _read_api.SchedulesApiFailure):
        raise AssertionError(result)
    if result.reason != "response_too_large":
        raise AssertionError(result)
    if stream.yielded != 1 or not stream.closed:
        raise AssertionError((stream.yielded, stream.closed))

    raw_stream = TrackingAsyncStream(
        [b"x" * (_read_api._MAX_RESPONSE_BYTES + 1), b"must-not-be-read"]
    )
    raw_response = httpx.Response(
        200,
        stream=raw_stream,
        headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
    )
    raw_result = _load_with_response(raw_response)
    if not isinstance(raw_result, _read_api.SchedulesApiFailure):
        raise AssertionError(raw_result)
    if raw_result.reason != "response_too_large":
        raise AssertionError(raw_result)
    if raw_stream.yielded != 1 or not raw_stream.closed:
        raise AssertionError((raw_stream.yielded, raw_stream.closed))


def test_whole_request_deadline_cancels_slow_headers_and_closes_socket() -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.settimeout(3)
    port = listener.getsockname()[1]
    disconnected = threading.Event()
    finished = threading.Event()

    def serve() -> None:
        connection: socket.socket | None = None
        try:
            connection, _ = listener.accept()
            connection.settimeout(2)
            request = b""
            while b"\r\n\r\n" not in request:
                request += connection.recv(4096)
            for byte in b"HTTP/1.1 200 OK\r\nX-Slow: " + (b"x" * 200):
                try:
                    connection.sendall(bytes([byte]))
                except OSError:
                    disconnected.set()
                    break
                time.sleep(0.1)
        except OSError:
            disconnected.set()
        finally:
            if connection is not None:
                connection.close()
            listener.close()
            finished.set()

    thread = threading.Thread(target=serve, name="slow-header-server", daemon=True)
    thread.start()
    started = time.monotonic()
    try:
        with patch(
            "ui._read_api._SCHEDULES_URL",
            f"http://127.0.0.1:{port}/api/v1/system/schedules",
        ):
            result = _read_api.load_schedules()
    finally:
        elapsed = time.monotonic() - started
        finished.wait(timeout=2)
        thread.join(timeout=1)
        try:
            listener.close()
        except OSError:
            pass

    if not isinstance(result, _read_api.SchedulesApiFailure):
        raise AssertionError(result)
    if result.reason != "deadline_exceeded":
        raise AssertionError(result)
    if not 0.75 <= elapsed < 2.5:
        raise AssertionError(elapsed)
    if thread.is_alive() or not disconnected.is_set():
        raise AssertionError((thread.is_alive(), disconnected.is_set()))


def test_page_resolution_is_api_only_and_retries_without_negative_cache() -> None:
    entry = _entry()
    api_entry = _entry(id="api_job", name="API Job")

    available = _read_api.SchedulesApiAvailable((entry,))
    unavailable = _read_api.SchedulesApiUnavailable("missing")
    with patch("ui.sys_schedules._read_api.load_schedules", return_value=available):
        state = sys_schedules._load_schedules()
    if state.status != "api_available" or state.schedules != (entry,):
        raise AssertionError(state)

    with patch("ui.sys_schedules._read_api.load_schedules", return_value=unavailable):
        state = sys_schedules._load_schedules()
    if state.status != "api_unavailable" or state.reason != "missing":
        raise AssertionError(state)

    api_calls = [
        _read_api.SchedulesApiFailure("transport_error"),
        _read_api.SchedulesApiAvailable((api_entry,)),
    ]
    with patch(
        "ui.sys_schedules._read_api.load_schedules",
        side_effect=api_calls,
    ) as api_read:
        first = sys_schedules._load_schedules()
        second = sys_schedules._load_schedules()
    if first.status != "api_failure" or first.schedules:
        raise AssertionError(first)
    if second.status != "api_available" or second.schedules != (api_entry,):
        raise AssertionError(second)
    if api_read.call_count != 2:
        raise AssertionError(api_read.call_count)


def test_client_retries_after_unavailable_and_failure_without_cache() -> None:
    responses = [
        _json_response(_unavailable("missing")),
        _json_response(_available([_schedule(id="after_unavailable")])),
        httpx.Response(503),
        _json_response(_available([_schedule(id="after_failure")])),
    ]
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        response = responses[calls]
        calls += 1
        return response

    transport = httpx.MockTransport(handler)
    first = _read_api.load_schedules(transport=transport)
    second = _read_api.load_schedules(transport=transport)
    third = _read_api.load_schedules(transport=transport)
    fourth = _read_api.load_schedules(transport=transport)
    if not isinstance(first, _read_api.SchedulesApiUnavailable):
        raise AssertionError(first)
    if not isinstance(second, _read_api.SchedulesApiAvailable):
        raise AssertionError(second)
    if second.schedules[0].id != "after_unavailable":
        raise AssertionError(second)
    if not isinstance(third, _read_api.SchedulesApiFailure):
        raise AssertionError(third)
    if not isinstance(fourth, _read_api.SchedulesApiAvailable):
        raise AssertionError(fourth)
    if fourth.schedules[0].id != "after_failure" or calls != 4:
        raise AssertionError((fourth, calls))


def test_page_client_failure_is_fail_soft_without_local_artifact_state() -> None:
    failure = _read_api.SchedulesApiFailure("invalid_envelope")
    with patch("ui.sys_schedules._read_api.load_schedules", return_value=failure):
        state = sys_schedules._load_schedules()
    if state.status != "api_failure" or state.schedules:
        raise AssertionError(state)

    source = (ROOT / "ui" / "sys_schedules.py").read_text(encoding="utf-8")
    for forbidden in (
        "read_artifact",
        "api.artifacts",
        "scripts.artifact_loader",
        '"local_fallback"',
        '"all_unavailable"',
    ):
        if forbidden in source:
            raise AssertionError(f"Schedules registry is not API-only: {forbidden}")


def test_client_outcomes_are_immutable() -> None:
    mutations = [
        (_read_api.SchedulesApiAvailable((_entry(),)), "schedules", ()),
        (_read_api.SchedulesApiUnavailable("missing"), "reason", "unreadable"),
        (
            _read_api.SchedulesApiFailure("transport_error"),
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


def test_streamlit_app_renders_all_registry_states_without_exception() -> None:
    wrapper = "from ui.sys_schedules import render\nrender()\n"
    entry = _entry()
    states = [
        (
            sys_schedules.ScheduleRegistryState("api_available", (entry,), None),
            None,
            "Job One",
        ),
        (
            sys_schedules.ScheduleRegistryState("api_available", (), None),
            None,
            "目前沒有資料",
        ),
        (
            sys_schedules.ScheduleRegistryState("api_unavailable", (), "invalid_json"),
            "權威來源不可用",
            "資料尚未完整寫入或格式無效",
        ),
        (
            sys_schedules.ScheduleRegistryState("api_failure", (), "transport_error"),
            "權威來源不可用",
            "連線暫時失敗",
        ),
    ]
    for state, warning_text, expected_text in states:
        with patch("ui.sys_schedules._load_schedules", return_value=state):
            app = AppTest.from_string(wrapper, default_timeout=10).run()
        if app.exception:
            raise AssertionError((state, app.exception))
        warnings = [item.value for item in app.warning]
        infos = [item.value for item in app.info]
        markdown = [item.value for item in app.markdown]
        subheaders = [item.value for item in app.subheader]
        rendered = "\n".join(warnings + infos + markdown + subheaders)
        if warning_text is not None and warning_text not in rendered:
            raise AssertionError((state, rendered))
        if expected_text not in rendered:
            raise AssertionError((state, rendered))


def test_client_source_is_python310_compatible_and_framework_neutral() -> None:
    path = ROOT / "ui" / "_read_api.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    if "api.main" in imported or "streamlit" in imported:
        raise AssertionError(imported)
    if "st.cache_data" in source or "asyncio.timeout(" in source:
        raise AssertionError("client must be uncached and Python 3.10 compatible")


def main() -> None:
    tests = [
        test_available_request_is_fixed_strict_and_ordered,
        test_async_client_configuration_is_explicit,
        test_empty_and_all_unavailable_reasons_are_typed,
        test_client_failure_matrix_is_stable_and_sanitized,
        test_decoded_size_cap_accepts_maximum_and_closes_oversize_stream,
        test_whole_request_deadline_cancels_slow_headers_and_closes_socket,
        test_page_resolution_is_api_only_and_retries_without_negative_cache,
        test_client_retries_after_unavailable_and_failure_without_cache,
        test_page_client_failure_is_fail_soft_without_local_artifact_state,
        test_client_outcomes_are_immutable,
        test_streamlit_app_renders_all_registry_states_without_exception,
        test_client_source_is_python310_compatible_and_framework_neutral,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
