#!/usr/bin/env python3
"""Behavior tests for the Streamlit single-ticker IV-history API consumer."""

from __future__ import annotations

import ast
import asyncio
import gzip
import inspect
import json
import socket
import sys
import threading
import time
from dataclasses import FrozenInstanceError
from datetime import date, timedelta
from pathlib import Path
from typing import get_args
from unittest.mock import patch

import httpx
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.models import ScoredCandidatesFeedData  # noqa: E402
from scripts import iv_history  # noqa: E402
from ui import _read_api, us_options  # noqa: E402


IV_HISTORY_URL_PREFIX = "http://127.0.0.1:8000/api/v1/options/iv-history/"
IV_HISTORY_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_AS_OF_DEFAULT = object()


def _series(count: int, *, start: date = date(2025, 1, 1)) -> dict[str, float]:
    return {
        (start + timedelta(days=index)).isoformat(): round(
            0.2 + (index % 137) / 1000,
            4,
        )
        for index in range(count)
    }


def _available(
    ticker: str,
    series: dict[str, float],
    *,
    source_id: str = "options.iv-history",
    as_of: object = _AS_OF_DEFAULT,
    generated_at: str | None = None,
) -> dict[str, object]:
    if as_of is _AS_OF_DEFAULT:
        as_of = max(series, default=None)
    return {
        "available": True,
        "reason": "ok",
        "data": {"ticker": ticker, "series": series},
        "meta": {
            "sourceId": source_id,
            "asOf": as_of,
            "generatedAt": generated_at,
        },
    }


def _unavailable(
    reason: str,
    *,
    source_id: str = "options.iv-history",
    as_of: str | None = None,
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


def _load_with_response(ticker: str, response: httpx.Response) -> object:
    return _read_api.load_iv_history(
        ticker,
        transport=httpx.MockTransport(lambda _request: response),
    )


def _points(series: dict[str, float]) -> tuple[object, ...]:
    return tuple(
        _read_api.IvHistoryPoint(as_of=as_of, iv=value)
        for as_of, value in series.items()
    )


def _state(
    status: str,
    series: dict[str, float] | None = None,
    reason: str | None = None,
) -> object:
    return us_options.IvHistoryPageState(
        status=status,
        points=_points(series or {}),
        reason=reason,
    )


def _app_text(app: AppTest) -> str:
    values: list[str] = []
    for elements in (
        app.header,
        app.caption,
        app.warning,
        app.info,
        app.error,
        app.markdown,
        app.metric,
    ):
        values.extend(str(element.value) for element in elements)
    values.extend(str(element.label) for element in app.metric)
    return "\n".join(values)


def _options_result() -> dict[str, object]:
    return {
        "available": True,
        "source": "stubbed_options",
        "ticker": "NVDA",
        "spot_price": 123.45,
        "expiration_analyzed": "2026-08-21",
        "total_score": 3,
        "max_possible": 11,
        "scores": {
            "6a_unusual_call": 3,
            "6b_sweeps_blocks": 0,
            "6c_dark_pool": 0,
            "6d_gex_gamma": 0,
        },
        "details": {
            "6a": {
                "call_put_volume_ratio": 1.4,
                "put_call_ratio": 0.7,
                "otm_call_volume_5_20pct": 100,
                "total_call_volume": 200,
                "total_put_volume": 100,
                "signal": "STUB_SIGNAL",
            },
            "6d": {"gex_regime": "neutral_proxy"},
        },
        "chain_summary": [],
        "top_active_calls": [],
        "top_active_puts": [],
        "oi_available": False,
        "data_missing": [],
    }


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


def _legacy_percentile(
    series: dict[str, float],
    current_iv: float | None = None,
) -> dict[str, object]:
    items = sorted(series.items())[-iv_history.WINDOW_DAYS :]
    values = [value for _, value in items]
    count = len(values)
    current = current_iv if current_iv is not None else (
        values[-1] if values else None
    )
    if count < iv_history.MIN_DAYS or current is None:
        return {
            "percentile": None,
            "rank": None,
            "n_days": count,
            "accumulating": True,
            "current": current,
        }
    low, high = min(values), max(values)
    percentile = round(
        sum(1 for value in values if value <= current) / count * 100,
        1,
    )
    rank = (
        round((current - low) / (high - low) * 100, 1)
        if high > low
        else None
    )
    return {
        "percentile": percentile,
        "rank": rank,
        "n_days": count,
        "accumulating": False,
        "current": round(float(current), 4),
    }


def test_pure_calculator_preserves_all_window_and_boundary_semantics() -> None:
    cases: list[tuple[dict[str, float], float | None]] = [
        ({}, None),
        (_series(39), None),
        (_series(40), None),
        (_series(252), None),
        (_series(253), None),
        (_series(40), 0.2456),
        ({key: value for key, value in reversed(tuple(_series(253).items()))}, None),
        (_series(40) | {"2024-01-01": 0.999}, None),
        ({key: 0.5 for key in _series(40)}, None),
    ]
    for series, current in cases:
        expected = _legacy_percentile(series, current)
        actual = iv_history.iv_percentile_from_series(series, current)
        if actual != expected:
            raise AssertionError((len(series), current, expected, actual))

    sentinel = {
        "percentile": 12.3,
        "rank": 45.6,
        "n_days": 40,
        "accumulating": False,
        "current": 0.7,
    }
    stored = {"ticker": "NVDA", "series": _series(40)}
    with (
        patch("scripts.iv_history._load", return_value=stored),
        patch(
            "scripts.iv_history.iv_percentile_from_series",
            return_value=sentinel,
        ) as pure,
    ):
        delegated = iv_history.iv_percentile("nvda", 0.7)
    pure.assert_called_once_with(stored["series"], 0.7)
    if delegated is not sentinel:
        raise AssertionError(delegated)


def test_client_signature_fixed_urls_normalization_and_configuration() -> None:
    signature = inspect.signature(_read_api.load_iv_history)
    parameters = list(signature.parameters.values())
    if len(parameters) != 2:
        raise AssertionError(signature)
    ticker_parameter, transport_parameter = parameters
    if (
        ticker_parameter.name != "ticker"
        or ticker_parameter.kind is not inspect.Parameter.POSITIONAL_OR_KEYWORD
        or ticker_parameter.default is not inspect.Parameter.empty
    ):
        raise AssertionError(signature)
    if (
        transport_parameter.name != "transport"
        or transport_parameter.kind is not inspect.Parameter.KEYWORD_ONLY
        or transport_parameter.default is not None
    ):
        raise AssertionError(signature)

    for raw, normalized in (("nvda", "NVDA"), ("BRK.B", "BRK.B"), ("bf-b", "BF-B")):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _json_response(_available(normalized, {}))

        result = _read_api.load_iv_history(
            raw,
            transport=httpx.MockTransport(handler),
        )
        if not isinstance(result, _read_api.IvHistoryApiAvailable):
            raise AssertionError((raw, result))
        if result.ticker != normalized or result.points:
            raise AssertionError(result)
        if len(requests) != 1:
            raise AssertionError(requests)
        request = requests[0]
        if request.method != "GET" or str(request.url) != (
            IV_HISTORY_URL_PREFIX + normalized
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

    real_client = httpx.AsyncClient
    options_seen: list[dict[str, object]] = []

    def record_client(*args, **kwargs):
        options_seen.append(dict(kwargs))
        kwargs["transport"] = httpx.MockTransport(
            lambda _request: _json_response(_available("NVDA", {}))
        )
        return real_client(*args, **kwargs)

    with patch("ui._read_api.httpx.AsyncClient", side_effect=record_client):
        configured = _read_api.load_iv_history("NVDA")
    if not isinstance(configured, _read_api.IvHistoryApiAvailable):
        raise AssertionError(configured)
    if len(options_seen) != 1:
        raise AssertionError(options_seen)
    options = options_seen[0]
    if options.get("trust_env") is not False or options.get("follow_redirects") is not False:
        raise AssertionError(options)


def test_invalid_tickers_are_typed_sanitized_and_issue_no_request() -> None:
    invalid_values: list[object] = [
        "",
        " NVDA",
        "NVDA ",
        "$NVDA",
        "A_B",
        "AA..BB",
        ".AAPL",
        "AAPL.",
        "AA.-BB",
        "../AAPL",
        r"..\AAPL",
        "台積電",
        "ＡＡＰＬ",
        "ABCDEFGHIJKLMNOP",
        123,
        None,
    ]
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _json_response(_available("NVDA", {}))

    transport = httpx.MockTransport(handler)
    for raw in invalid_values:
        result = _read_api.load_iv_history(raw, transport=transport)  # type: ignore[arg-type]
        if not isinstance(result, _read_api.IvHistoryApiInvalidTicker):
            raise AssertionError((raw, result))
        exposed = repr(result)
        if raw not in ("", None) and str(raw) in exposed:
            raise AssertionError((raw, exposed))
    if requests:
        raise AssertionError(requests)

    page = us_options._load_iv_history("../TOP-SECRET")
    if page.status != "invalid_ticker" or page.points:
        raise AssertionError(page)
    if "TOP-SECRET" in repr(page):
        raise AssertionError(page)


def test_available_empty_unavailable_and_strict_envelope_contracts() -> None:
    ordered_series = {
        "2026-07-14": 0.42,
        "2026-07-12": 0.38,
        "2026-07-13": 0.4,
    }
    available = _load_with_response(
        "nvda",
        _json_response(_available("NVDA", ordered_series)),
    )
    if not isinstance(available, _read_api.IvHistoryApiAvailable):
        raise AssertionError(available)
    if available.ticker != "NVDA" or [
        (point.as_of, point.iv) for point in available.points
    ] != list(ordered_series.items()):
        raise AssertionError(available)

    empty = _load_with_response(
        "NVDA",
        _json_response(_available("NVDA", {})),
    )
    if not isinstance(empty, _read_api.IvHistoryApiAvailable) or empty.points:
        raise AssertionError(empty)

    for reason in ("missing", "invalid_json", "invalid_shape", "unreadable"):
        result = _load_with_response(
            "NVDA",
            _json_response(_unavailable(reason)),
        )
        if not isinstance(result, _read_api.IvHistoryApiUnavailable):
            raise AssertionError((reason, result))
        if result.ticker != "NVDA" or result.reason != reason:
            raise AssertionError((reason, result))

    invalid_payloads = [
        _available("AMD", ordered_series),
        _available("NVDA", ordered_series, source_id="system.ai-updates"),
        _available("NVDA", ordered_series, as_of="2026-07-13"),
        _available(
            "NVDA",
            ordered_series,
            generated_at="2026-07-15T00:00:00Z",
        ),
        {**_available("NVDA", ordered_series), "secret": "body-secret"},
        {
            **_available("NVDA", ordered_series),
            "data": {
                "ticker": "NVDA",
                "series": ordered_series,
                "path": "/private/body-secret",
            },
        },
        _available("nvda", ordered_series),
        _available("NVDA", {"2026-02-30": 0.4}),
        _available("NVDA", {"2026-07-14": 0.0}),
        _available("NVDA", {"2026-07-14": 10.0}),
        _available("NVDA", {"2026-07-14": "0.4"}),  # type: ignore[dict-item]
        _unavailable("missing", as_of="2026-07-14"),
        _unavailable("missing", source_id="system.schedules"),
        _unavailable("missing", generated_at="2026-07-15T00:00:00Z"),
    ]
    for payload in invalid_payloads:
        result = _load_with_response("NVDA", _json_response(payload))
        if not isinstance(result, _read_api.IvHistoryApiFailure):
            raise AssertionError(result)
        if result.ticker != "NVDA" or result.reason != "invalid_envelope":
            raise AssertionError(result)
        if "body-secret" in repr(result) or "/private" in repr(result):
            raise AssertionError(result)


def test_complete_client_failure_matrix_deadline_and_sanitization() -> None:
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

    outcomes["transport_error"] = _read_api.load_iv_history(
        "NVDA",
        transport=httpx.MockTransport(transport_error),
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
        outcomes["deadline_exceeded"] = _read_api.load_iv_history("NVDA")

    outcomes["http_status"] = _load_with_response(
        "NVDA",
        httpx.Response(302, headers={"Location": "http://evil.invalid/secret"}),
    )
    outcomes["invalid_media_type"] = _load_with_response(
        "NVDA",
        httpx.Response(
            200,
            content=b"{}",
            headers={"Content-Type": "text/html", "Cache-Control": "no-store"},
        ),
    )
    outcomes["invalid_cache_control"] = _load_with_response(
        "NVDA",
        httpx.Response(
            200,
            content=b"{}",
            headers={"Content-Type": "application/json"},
        ),
    )
    outcomes["response_too_large"] = _load_with_response(
        "NVDA",
        httpx.Response(
            200,
            content=b"x" * (IV_HISTORY_MAX_RESPONSE_BYTES + 1),
            headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        ),
    )
    outcomes["invalid_envelope"] = _load_with_response(
        "NVDA",
        httpx.Response(
            200,
            content=b'{"available":',
            headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        ),
    )

    for expected, result in outcomes.items():
        if not isinstance(result, _read_api.IvHistoryApiFailure):
            raise AssertionError((expected, result))
        if result.ticker != "NVDA" or result.reason != expected:
            raise AssertionError((expected, result))
        exposed = repr(result)
        if "transport-secret" in exposed or "evil.invalid" in exposed:
            raise AssertionError((expected, exposed))

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.settimeout(3)
    port = listener.getsockname()[1]
    disconnected = threading.Event()
    finished = threading.Event()

    def serve_slow_headers() -> None:
        connection: socket.socket | None = None
        try:
            connection, _ = listener.accept()
            connection.settimeout(2)
            request = b""
            while b"\r\n\r\n" not in request:
                request += connection.recv(4096)
            slow_header = b"HTTP/1.1 200 OK\r\nX-Slow: " + (b"x" * 200)
            for byte in slow_header:
                try:
                    connection.sendall(bytes([byte]))
                except OSError:
                    disconnected.set()
                    break
                time.sleep(0.05)
        except OSError:
            disconnected.set()
        finally:
            if connection is not None:
                connection.close()
            listener.close()
            finished.set()

    thread = threading.Thread(
        target=serve_slow_headers,
        name="iv-slow-header-server",
        daemon=True,
    )
    thread.start()
    started = time.monotonic()
    try:
        with patch(
            "ui._read_api._IV_HISTORY_URL_PREFIX",
            f"http://127.0.0.1:{port}/api/v1/options/iv-history/",
        ):
            slow_result = _read_api.load_iv_history("NVDA")
    finally:
        elapsed = time.monotonic() - started
        finished.wait(timeout=2)
        thread.join(timeout=1)
        try:
            listener.close()
        except OSError:
            pass
    if not isinstance(slow_result, _read_api.IvHistoryApiFailure):
        raise AssertionError(slow_result)
    if slow_result.reason != "deadline_exceeded":
        raise AssertionError(slow_result)
    if not 0.75 <= elapsed < 2.5:
        raise AssertionError(elapsed)
    if thread.is_alive() or not disconnected.is_set():
        raise AssertionError((thread.is_alive(), disconnected.is_set()))


def test_exact_two_mib_cap_and_cap_plus_one_close_the_stream() -> None:
    compact = json.dumps(
        _available("NVDA", {}),
        separators=(",", ":"),
    ).encode()
    exact_body = compact + b" " * (IV_HISTORY_MAX_RESPONSE_BYTES - len(compact))
    if len(exact_body) != IV_HISTORY_MAX_RESPONSE_BYTES:
        raise AssertionError(len(exact_body))

    exact = _load_with_response(
        "NVDA",
        httpx.Response(
            200,
            content=exact_body,
            headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        ),
    )
    if not isinstance(exact, _read_api.IvHistoryApiAvailable):
        raise AssertionError(exact)

    stream = TrackingAsyncStream([exact_body, b" ", b"must-not-be-consumed"])
    oversized = _load_with_response(
        "NVDA",
        httpx.Response(
            200,
            stream=stream,
            headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        ),
    )
    if not isinstance(oversized, _read_api.IvHistoryApiFailure):
        raise AssertionError(oversized)
    if oversized.reason != "response_too_large":
        raise AssertionError(oversized)
    if stream.yielded != 2 or not stream.closed:
        raise AssertionError((stream.yielded, stream.closed))

    expanded = b"x" * (IV_HISTORY_MAX_RESPONSE_BYTES + 1)
    compressed_stream = TrackingAsyncStream(
        [gzip.compress(expanded), b"must-not-be-consumed"]
    )
    compressed = _load_with_response(
        "NVDA",
        httpx.Response(
            200,
            stream=compressed_stream,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-store",
                "Content-Encoding": "gzip",
            },
        ),
    )
    if not isinstance(compressed, _read_api.IvHistoryApiFailure):
        raise AssertionError(compressed)
    if compressed.reason != "response_too_large":
        raise AssertionError(compressed)
    if compressed_stream.yielded != 1 or not compressed_stream.closed:
        raise AssertionError(
            (compressed_stream.yielded, compressed_stream.closed)
        )


def test_authoritative_unavailable_and_client_failures_are_api_only() -> None:
    for reason in ("missing", "invalid_json", "invalid_shape", "unreadable"):
        with patch(
            "ui.us_options._read_api.load_iv_history",
            return_value=_read_api.IvHistoryApiUnavailable(
                ticker="NVDA",
                reason=reason,
            ),
        ):
            state = us_options._load_iv_history("nvda")
        if state.status != "api_unavailable" or state.reason != reason or state.points:
            raise AssertionError((reason, state))

    failures = (
        "transport_error",
        "deadline_exceeded",
        "http_status",
        "invalid_media_type",
        "invalid_cache_control",
        "invalid_envelope",
        "response_too_large",
    )
    for reason in failures:
        with patch(
            "ui.us_options._read_api.load_iv_history",
            return_value=_read_api.IvHistoryApiFailure(
                ticker="NVDA",
                reason=reason,
            ),
        ):
            state = us_options._load_iv_history("nvda")
        if state.status != "api_failure" or state.reason != reason or state.points:
            raise AssertionError((reason, state))

    resolver_source = inspect.getsource(us_options._load_iv_history)
    for forbidden in (
        "read_artifact",
        "iv_history_spec",
        "ArtifactAvailable",
        "ArtifactUnavailable",
        "IvHistoryData",
        "_local_iv_points",
        "_LOCAL_IV_FALLBACK_REASONS",
        "local_fallback",
        "all_unavailable",
        "LOGGER",
    ):
        if forbidden in resolver_source:
            raise AssertionError((forbidden, resolver_source))


def test_oversize_and_unexpected_client_results_remain_fail_soft() -> None:
    cases = (
        (
            _read_api.IvHistoryApiFailure(
                ticker="NVDA",
                reason="response_too_large",
            ),
            "response_too_large",
        ),
        (object(), "invalid_envelope"),
    )
    for result, expected_reason in cases:
        with patch(
            "ui.us_options._read_api.load_iv_history",
            return_value=result,
        ):
            state = us_options._load_iv_history("NVDA")
        if (
            state.status != "api_failure"
            or state.reason != expected_reason
            or state.points
        ):
            raise AssertionError((result, state))


def test_page_status_union_is_api_only_and_failure_reason_is_sanitized() -> None:
    expected_statuses = {
        "api_available",
        "api_unavailable",
        "api_failure",
        "invalid_ticker",
    }
    if set(get_args(us_options.IvHistoryPageStatus)) != expected_statuses:
        raise AssertionError(get_args(us_options.IvHistoryPageStatus))

    failure = _read_api.IvHistoryApiFailure(
        ticker="NVDA",
        reason="transport_error",
    )
    with patch("ui.us_options._read_api.load_iv_history", return_value=failure):
        state = us_options._load_iv_history("NVDA")
    if state != _state("api_failure", {}, "transport_error"):
        raise AssertionError(state)


def test_api_points_and_rank_match_pure_calculator() -> None:
    series = {
        key: value
        for key, value in reversed(tuple(_series(40).items()))
    }
    api_result = _load_with_response(
        "NVDA",
        _json_response(_available("NVDA", series)),
    )
    if not isinstance(api_result, _read_api.IvHistoryApiAvailable):
        raise AssertionError(api_result)
    with patch(
        "ui.us_options._read_api.load_iv_history",
        return_value=api_result,
    ):
        page_state = us_options._load_iv_history("NVDA")
    if page_state.status != "api_available":
        raise AssertionError(page_state)
    if page_state.points != api_result.points:
        raise AssertionError((page_state.points, api_result.points))
    api_rank = iv_history.iv_percentile_from_series(
        {point.as_of: point.iv for point in api_result.points}
    )
    page_rank = iv_history.iv_percentile_from_series(
        {point.as_of: point.iv for point in page_state.points}
    )
    if api_rank != page_rank or api_rank["n_days"] != 40:
        raise AssertionError((api_rank, page_rank))


def test_direct_and_page_failures_recover_on_the_next_uncached_call() -> None:
    responses = iter(
        [
            _json_response(_unavailable("missing")),
            _json_response(_available("NVDA", _series(40))),
            httpx.Response(503),
            _json_response(_available("NVDA", _series(41))),
        ]
    )
    request_count = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return next(responses)

    transport = httpx.MockTransport(handler)
    direct_results = [
        _read_api.load_iv_history("NVDA", transport=transport)
        for _ in range(4)
    ]
    expected_types = (
        _read_api.IvHistoryApiUnavailable,
        _read_api.IvHistoryApiAvailable,
        _read_api.IvHistoryApiFailure,
        _read_api.IvHistoryApiAvailable,
    )
    if not all(
        isinstance(result, expected)
        for result, expected in zip(direct_results, expected_types)
    ):
        raise AssertionError(direct_results)
    if request_count != 4:
        raise AssertionError(request_count)

    api_results = [
        _read_api.IvHistoryApiFailure(
            ticker="NVDA",
            reason="transport_error",
        ),
        _read_api.IvHistoryApiAvailable(
            ticker="NVDA",
            points=_points(_series(40)),
        ),
    ]
    with patch(
        "ui.us_options._read_api.load_iv_history",
        side_effect=api_results,
    ) as api_read:
        first = us_options._load_iv_history("NVDA")
        second = us_options._load_iv_history("NVDA")
    if first.status != "api_failure" or second.status != "api_available":
        raise AssertionError((first, second))
    if api_read.call_count != 2:
        raise AssertionError(api_read.call_count)


def test_app_states_render_exact_safe_copy_rank_and_keep_chain_usable() -> None:
    rich_series = _series(40)
    state_cases = [
        (_state("api_available", rich_series), "IV Rank 100", None),
        (_state("api_available", {}), "IV Rank 累積中 n=0", None),
        (
            _state("api_unavailable", {}, "missing"),
            "IV Rank 累積中 n=0",
            "IV 歷史資料目前無法使用；即時期權分析仍可繼續。",
        ),
        (
            _state("api_failure", {}, "transport_error"),
            "IV Rank 累積中 n=0",
            "IV 歷史服務目前無法使用；即時期權分析仍可繼續。",
        ),
        (
            _state("api_failure", {}, "response_too_large"),
            "IV Rank 累積中 n=0",
            "IV 歷史資料超過安全讀取上限；即時期權分析仍可繼續。",
        ),
        (
            _state("invalid_ticker", {}),
            "IV Rank 累積中 n=0",
            "此代號無法讀取 IV 歷史；即時期權分析仍可繼續。",
        ),
    ]
    chip_wrapper = (
        "from ui.us_options import _render_bias_iv_chips\n"
        "_render_bias_iv_chips('NVDA', "
        "{'call_put_volume_ratio': 1.4, 'put_call_ratio': 0.7})\n"
    )
    for state, expected_chip, expected_copy in state_cases:
        with patch("ui.us_options._load_iv_history", return_value=state):
            app = AppTest.from_string(chip_wrapper, default_timeout=10).run()
        if app.exception:
            raise AssertionError((state, app.exception))
        rendered = _app_text(app)
        if "流向偏多" not in rendered or expected_chip not in rendered:
            raise AssertionError((state, rendered))
        if expected_copy is not None and expected_copy not in rendered:
            raise AssertionError((state, rendered))

    absent = _state("api_failure", {}, "transport_error")
    full_wrapper = "from ui.us_options import render_for\nrender_for('NVDA')\n"
    with (
        patch(
            "scripts.options_free.analyze_options",
            return_value=_options_result(),
        ) as provider,
        patch("ui.us_options._load_iv_history", return_value=absent),
    ):
        full = AppTest.from_string(full_wrapper, default_timeout=10).run()
    if full.exception:
        raise AssertionError(full.exception)
    provider.assert_called_once_with("NVDA")
    rendered = _app_text(full)
    if (
        "IV 歷史服務目前無法使用；即時期權分析仍可繼續。" not in rendered
        or "Call/Put 量比" not in rendered
        or "完整期權鏈明細是證據頁" not in rendered
    ):
        raise AssertionError(rendered)


def test_default_and_candidate_grid_stay_local_without_iv_api_n_plus_one() -> None:
    wrapper = "from ui.us_options import render\nrender()\n"
    with (
        patch(
            "ui.us_options._candidate_grid",
            return_value=us_options.CandidateGridState("api_available", None),
        ),
        patch("ui.us_options._read_api.load_iv_history") as history_api,
        patch("scripts.options_free.analyze_options") as provider,
    ):
        app = AppTest.from_string(wrapper, default_timeout=10).run()
    if app.exception:
        raise AssertionError(app.exception)
    history_api.assert_not_called()
    provider.assert_not_called()

    scored = ScoredCandidatesFeedData.model_validate(
        {
            "scan_date": "2026-08-02",
            "candidates": [
            {
                "ticker": "NVDA",
                "verdict": "WATCHLIST",
                "composite_score": 80.0,
                "regime_adjusted_score": 80.0,
                "scores": {
                    "technical": 25.0, "catalyst": 12.0, "sentiment": 8.0,
                    "institutional": 7.0, "sector_market": 2.0,
                    "options_flow": 5.0, "analyst": 6.0,
                },
                "data_missing": [], "due_diligence_required": False,
                "key_signals": [], "key_risks": [],
                "suggested_entry_zone": "$95-$100",
            },
            {
                "ticker": "AMD",
                "verdict": "NEEDS_LAYER_2",
                "composite_score": 70.0,
                "regime_adjusted_score": 70.0,
                "scores": {
                    "technical": 25.0, "catalyst": 12.0, "sentiment": 8.0,
                    "institutional": 7.0, "sector_market": 2.0,
                    "options_flow": 7.0, "analyst": 6.0,
                },
                "data_missing": [], "due_diligence_required": False,
                "key_signals": [], "key_risks": [],
                "suggested_entry_zone": "$95-$100",
            },
            ],
        },
        strict=True,
    )

    def local_json(path: str) -> object:
        return {"series": {"2026-07-14": 0.4}}

    with (
        patch(
            "ui.us_options._read_api.load_scored_candidates",
            return_value=_read_api.ScoredCandidatesApiAvailable(scored),
        ) as scored_api,
        patch("ui.us_options._shared.load_json", side_effect=local_json),
        patch(
            "scripts.iv_history.iv_percentile",
            return_value={
                "rank": 50.0,
                "n_days": 40,
                "accumulating": False,
                "percentile": 50.0,
                "current": 0.4,
            },
        ),
        patch("ui.us_options._read_api.load_iv_history") as history_api,
    ):
        grid = us_options._candidate_grid()
    history_api.assert_not_called()
    scored_api.assert_called_once_with()
    if grid.frame is None or list(grid.frame["代號"]) != ["NVDA", "AMD"]:
        raise AssertionError(grid)


def test_embedded_page_preserves_legacy_aliases_and_makes_one_history_read() -> None:
    wrapper = (
        "from ui.us_options import render_for\n"
        "render_for('  $$$nvda  ')\n"
    )
    available_state = _state("api_available", _series(40))
    with (
        patch(
            "scripts.options_free.analyze_options",
            return_value=_options_result(),
        ) as provider,
        patch(
            "ui.us_options._load_iv_history",
            return_value=available_state,
        ) as history_read,
    ):
        app = AppTest.from_string(wrapper, default_timeout=10).run()
    if app.exception:
        raise AssertionError(app.exception)
    provider.assert_called_once_with("NVDA")
    history_read.assert_called_once_with("NVDA")
    rendered = _app_text(app)
    if "IV Rank 100" not in rendered or "NVDA · 現價" not in rendered:
        raise AssertionError(rendered)


def test_outcomes_page_state_are_frozen_and_sources_are_python310_safe() -> None:
    point = _read_api.IvHistoryPoint(as_of="2026-07-14", iv=0.4)
    outcomes = (
        _read_api.IvHistoryApiAvailable(ticker="NVDA", points=(point,)),
        _read_api.IvHistoryApiUnavailable(ticker="NVDA", reason="missing"),
        _read_api.IvHistoryApiFailure(ticker="NVDA", reason="transport_error"),
        _read_api.IvHistoryApiInvalidTicker(),
        us_options.IvHistoryPageState(
            status="api_available",
            points=(point,),
            reason=None,
        ),
        us_options.CandidateGridState(status="api_available", frame=None),
    )
    for value in (point, *outcomes):
        field = next(iter(value.__dataclass_fields__))
        try:
            setattr(value, field, "changed")
        except FrozenInstanceError:
            pass
        else:
            raise AssertionError(value)

    paths = (
        ROOT / "ui" / "_read_api.py",
        ROOT / "ui" / "us_options.py",
        ROOT / "scripts" / "iv_history.py",
        Path(__file__),
    )
    for path in paths:
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path), feature_version=(3, 10))

    client_source = (ROOT / "ui" / "_read_api.py").read_text(encoding="utf-8")
    client_tree = ast.parse(client_source)
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(client_tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(client_tree)
        if isinstance(node, ast.ImportFrom)
    )
    if "streamlit" in imported_roots or "api.main" in imported_roots:
        raise AssertionError(imported_roots)
    if "st.cache_data" in client_source or "asyncio.timeout(" in client_source:
        raise AssertionError("client must be uncached and Python 3.10 compatible")

    page_source = (ROOT / "ui" / "us_options.py").read_text(encoding="utf-8")
    resolver_source = inspect.getsource(us_options._load_iv_history)
    if "st.cache_data" in resolver_source or "_shared.load_json" in resolver_source:
        raise AssertionError("page resolver must be uncached and API-only")
    for forbidden in (
        "read_artifact",
        "iv_history_spec",
        "ArtifactAvailable",
        "ArtifactUnavailable",
        "IvHistoryData",
    ):
        if forbidden in resolver_source:
            raise AssertionError((forbidden, resolver_source))
    candidate_source = inspect.getsource(us_options._iv_rank_spark)
    if "load_iv_history" in candidate_source or "_read_api" in candidate_source:
        raise AssertionError("candidate IV spark must remain local")
    if "options_cockpit" in page_source:
        raise AssertionError("Phase 3D must not couple the Options Cockpit")


def main() -> None:
    tests = [
        test_pure_calculator_preserves_all_window_and_boundary_semantics,
        test_client_signature_fixed_urls_normalization_and_configuration,
        test_invalid_tickers_are_typed_sanitized_and_issue_no_request,
        test_available_empty_unavailable_and_strict_envelope_contracts,
        test_complete_client_failure_matrix_deadline_and_sanitization,
        test_exact_two_mib_cap_and_cap_plus_one_close_the_stream,
        test_authoritative_unavailable_and_client_failures_are_api_only,
        test_oversize_and_unexpected_client_results_remain_fail_soft,
        test_page_status_union_is_api_only_and_failure_reason_is_sanitized,
        test_api_points_and_rank_match_pure_calculator,
        test_direct_and_page_failures_recover_on_the_next_uncached_call,
        test_app_states_render_exact_safe_copy_rank_and_keep_chain_usable,
        test_default_and_candidate_grid_stay_local_without_iv_api_n_plus_one,
        test_embedded_page_preserves_legacy_aliases_and_makes_one_history_read,
        test_outcomes_page_state_are_frozen_and_sources_are_python310_safe,
    ]
    discovered = sorted(
        name
        for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    )
    registered = sorted(test.__name__ for test in tests)
    if discovered != registered:
        raise AssertionError(
            f"focused runner drift: discovered={discovered}, registered={registered}"
        )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
