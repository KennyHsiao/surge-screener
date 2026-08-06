#!/usr/bin/env python3
"""Behavior tests for the Streamlit Options Flow feed API consumer."""

from __future__ import annotations

import ast
import asyncio
import gzip
import inspect
import json
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import get_args
from unittest.mock import patch

import httpx
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.models import OptionsFlowFeedData  # noqa: E402
from ui import _read_api, options_flow  # noqa: E402


OPTIONS_FLOW_URL = (
    "http://127.0.0.1:8000/api/v1/signals/options-flow/feed"
)
OPTIONS_FLOW_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
CLIENT_FAILURE_REASONS = (
    "transport_error",
    "deadline_exceeded",
    "http_status",
    "invalid_media_type",
    "invalid_cache_control",
    "invalid_envelope",
    "response_too_large",
)
UNAVAILABLE_DETAILS = {
    "missing": "找不到異常流資料。",
    "invalid_json": "異常流資料尚未完整寫入或 JSON 格式無效。",
    "invalid_shape": "異常流資料格式不符合預期。",
    "unreadable": "異常流資料目前無法讀取。",
}


def _signal(
    ticker: str = "NVDA",
    *,
    direction: str = "bullish",
    score: float = 91.5,
    tags: list[str] | None = None,
) -> dict[str, object]:
    return {
        "ticker": ticker,
        "direction": direction,
        "flow_score": score,
        "est_notional_usd": 12_500_000,
        "biggest": {"strike": 150.0, "notional": 3_200_000.0},
        "expiry": "2026-08-21",
        "max_voi": 8.5,
        "high_voi_strikes": 4,
        "call_put_ratio": 2.4,
        "put_call_ratio": 0.4,
        "tags": tags if tags is not None else ["高權利金", "V/OI 暴量"],
    }


def _feed(
    signals: list[dict[str, object]] | None = None,
    *,
    generated_at: str = "2026-07-15T06:30:00Z",
    as_of: str = "2026-07-15",
    signal_count: int | None = None,
    universe_size: int = 50,
) -> dict[str, object]:
    actual_signals = [_signal()] if signals is None else signals
    return {
        "generated_at": generated_at,
        "as_of": as_of,
        "provider": "yfinance",
        "universe_size": universe_size,
        "min_notional": 500_000,
        "signal_count": (
            len(actual_signals) if signal_count is None else signal_count
        ),
        "signals": actual_signals,
    }


def _available(
    data: dict[str, object] | None = None,
    *,
    source_id: str = "signals.options-flow.feed",
    meta_as_of: str | None = "2026-07-15",
    meta_generated_at: str | None = "2026-07-15T06:30:00Z",
) -> dict[str, object]:
    return {
        "available": True,
        "reason": "ok",
        "data": _feed() if data is None else data,
        "meta": {
            "sourceId": source_id,
            "asOf": meta_as_of,
            "generatedAt": meta_generated_at,
        },
    }


def _unavailable(
    reason: str,
    *,
    source_id: str = "signals.options-flow.feed",
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
    return httpx.Response(
        status_code,
        json=payload,
        headers=response_headers,
    )


def _load_with_response(response: httpx.Response) -> object:
    return _read_api.load_options_flow(
        transport=httpx.MockTransport(lambda _request: response),
    )


def _feed_model(
    signals: list[dict[str, object]] | None = None,
    **kwargs: object,
) -> OptionsFlowFeedData:
    return OptionsFlowFeedData.model_validate(
        _feed(signals, **kwargs),
        strict=True,
    )


def _state(
    status: str,
    feed: OptionsFlowFeedData | None = None,
    reason: str | None = None,
) -> object:
    return options_flow.OptionsFlowPageState(
        status=status,
        feed=feed,
        reason=reason,
    )


def _app_text(app: AppTest) -> str:
    values: list[str] = []
    for elements in (
        app.title,
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


def _live_result() -> dict[str, object]:
    return {
        "spot_price": 152.25,
        "expiration_analyzed": "2026-08-21",
        "chain_summary": [
            {"strike": 150.0, "call_vol": 1200, "put_vol": 300},
            {"strike": 155.0, "call_vol": 900, "put_vol": 450},
        ],
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


def test_fixed_request_signature_configuration_and_raw_reader_boundary() -> None:
    signature = inspect.signature(_read_api.load_options_flow)
    parameters = list(signature.parameters.values())
    if len(parameters) != 1:
        raise AssertionError(signature)
    transport_parameter = parameters[0]
    if (
        transport_parameter.name != "transport"
        or transport_parameter.kind is not inspect.Parameter.KEYWORD_ONLY
        or transport_parameter.default is not None
    ):
        raise AssertionError(signature)

    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _json_response(_available())

    result = _read_api.load_options_flow(
        transport=httpx.MockTransport(handler),
    )
    if not isinstance(result, _read_api.OptionsFlowApiAvailable):
        raise AssertionError(result)
    if len(requests) != 1:
        raise AssertionError(requests)
    request = requests[0]
    if request.method != "GET" or str(request.url) != OPTIONS_FLOW_URL:
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
            lambda _request: _json_response(_available())
        )
        return real_client(*args, **kwargs)

    with patch("ui._read_api.httpx.AsyncClient", side_effect=record_client):
        configured = _read_api.load_options_flow()
    if not isinstance(configured, _read_api.OptionsFlowApiAvailable):
        raise AssertionError(configured)
    if len(options_seen) != 1:
        raise AssertionError(options_seen)
    options = options_seen[0]
    if (
        options.get("trust_env") is not False
        or options.get("follow_redirects") is not False
    ):
        raise AssertionError(options)

    async def raw_read() -> bytes | str:
        return await _read_api._read_fixed_json(
            url=OPTIONS_FLOW_URL,
            max_response_bytes=OPTIONS_FLOW_MAX_RESPONSE_BYTES,
            transport=httpx.MockTransport(
                lambda _request: _json_response(_available())
            ),
        )

    raw = asyncio.run(raw_read())
    if not isinstance(raw, bytes) or b'"available":true' not in raw:
        raise AssertionError(type(raw))


def test_available_values_order_metadata_and_invalid_envelope_matrix() -> None:
    signals = [
        _signal("NVDA", score=92.0),
        _signal("AAPL", direction="bearish", score=81.0),
    ]
    base_data = _feed(signals, generated_at="2026-07-15t06:30:00z")
    spellings = [
        ("2026-07-15t06:30:00z", "2026-07-15T08:30:00+02:00"),
    ]
    for digits in range(1, 7):
        fraction = "1" * digits
        normalized_fraction = fraction.ljust(6, "0")
        spellings.append(
            (
                f"2026-07-15T06:30:00.{fraction}Z",
                f"2026-07-15T08:30:00.{normalized_fraction}+02:00",
            )
        )
    for data_timestamp, meta_timestamp in spellings:
        data = dict(base_data)
        data["generated_at"] = data_timestamp
        result = _load_with_response(
            _json_response(
                _available(data, meta_generated_at=meta_timestamp)
            )
        )
        if not isinstance(result, _read_api.OptionsFlowApiAvailable):
            raise AssertionError((data_timestamp, meta_timestamp, result))
        if [signal.ticker for signal in result.feed.signals] != ["NVDA", "AAPL"]:
            raise AssertionError(result.feed.signals)
        if result.feed.model_dump(mode="python") != OptionsFlowFeedData.model_validate(
            data,
            strict=True,
        ).model_dump(mode="python"):
            raise AssertionError(result.feed)

    invalid_payloads: list[object] = []
    wrong_source = _available(base_data, source_id="signals.options-flow.latest")
    invalid_payloads.append(wrong_source)
    invalid_payloads.append(_available(base_data, meta_as_of="2026-07-14"))
    invalid_payloads.append(
        _available(
            base_data,
            meta_generated_at="2026-07-15T06:30:00.000001Z",
        )
    )
    invalid_payloads.append(
        _available(
            base_data,
            meta_generated_at="2026-07-15T06:30:00.0000001Z",
        )
    )
    microsecond_data = dict(base_data)
    microsecond_data["generated_at"] = "2026-07-15T06:30:00.123456Z"
    invalid_payloads.append(
        _available(
            microsecond_data,
            meta_generated_at="2026-07-15T06:30:00.1234567Z",
        )
    )
    extra_envelope = _available(base_data)
    extra_envelope["secret"] = "must-not-pass"
    invalid_payloads.append(extra_envelope)
    extra_data = dict(base_data)
    extra_data["secret"] = "must-not-pass"
    invalid_payloads.append(_available(extra_data))
    missing_data = dict(base_data)
    del missing_data["provider"]
    invalid_payloads.append(_available(missing_data))
    coercion = dict(base_data)
    coercion["signal_count"] = "2"
    invalid_payloads.append(_available(coercion))
    invalid_biggest = json.loads(json.dumps(base_data))
    invalid_biggest["signals"][0]["biggest"]["strike"] = 0.0
    invalid_payloads.append(_available(invalid_biggest))
    invalid_payloads.extend(
        _unavailable(reason, as_of="2026-07-15")
        for reason in ("missing", "invalid_json", "invalid_shape", "unreadable")
    )
    invalid_payloads.append(_unavailable("missing", generated_at="2026-07-15T06:30:00Z"))

    for payload in invalid_payloads:
        result = _load_with_response(_json_response(payload))
        if not isinstance(result, _read_api.OptionsFlowApiFailure):
            raise AssertionError((payload, result))
        if result.reason != "invalid_envelope":
            raise AssertionError(result)

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
    if not isinstance(malformed, _read_api.OptionsFlowApiFailure):
        raise AssertionError(malformed)
    if malformed.reason != "invalid_envelope":
        raise AssertionError(malformed)

    for reason in ("missing", "invalid_json", "invalid_shape", "unreadable"):
        unavailable = _load_with_response(_json_response(_unavailable(reason)))
        if not isinstance(unavailable, _read_api.OptionsFlowApiUnavailable):
            raise AssertionError((reason, unavailable))
        if unavailable.reason != reason:
            raise AssertionError((reason, unavailable))


def test_complete_failure_matrix_and_size_stream_cleanup() -> None:
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

    outcomes["transport_error"] = _read_api.load_options_flow(
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
        outcomes["deadline_exceeded"] = _read_api.load_options_flow()

    outcomes["http_status"] = _load_with_response(
        httpx.Response(302, headers={"Location": "http://evil.invalid/secret"})
    )
    outcomes["invalid_media_type"] = _load_with_response(
        httpx.Response(
            200,
            content=b"{}",
            headers={"Content-Type": "text/html", "Cache-Control": "no-store"},
        )
    )
    outcomes["invalid_cache_control"] = _load_with_response(
        httpx.Response(
            200,
            content=b"{}",
            headers={"Content-Type": "application/json"},
        )
    )
    outcomes["response_too_large"] = _load_with_response(
        httpx.Response(
            200,
            content=b"x" * (OPTIONS_FLOW_MAX_RESPONSE_BYTES + 1),
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-store",
            },
        )
    )
    outcomes["invalid_envelope"] = _load_with_response(_json_response({}))

    for expected, result in outcomes.items():
        if not isinstance(result, _read_api.OptionsFlowApiFailure):
            raise AssertionError((expected, result))
        if result.reason != expected:
            raise AssertionError((expected, result))
        if "transport-secret" in repr(result) or "evil.invalid" in repr(result):
            raise AssertionError(result)

    max_signals = []
    max_tags = [f"{tag:02d}" + ("😀" * 98) for tag in range(20)]
    for index in range(200):
        signal = _signal(
            f"T{index:014d}",
            score=100.0,
            tags=max_tags,
        )
        signal.update(
            {
                "est_notional_usd": 1_000_000_000_000_000,
                "biggest": {
                    "strike": sys.float_info.max,
                    "notional": 1_000_000_000_000_000.0,
                },
                "max_voi": 1_000_000_000.0,
                "high_voi_strikes": 100_000,
                "call_put_ratio": 1_000_000_000.0,
                "put_call_ratio": 1_000_000_000.0,
            }
        )
        max_signals.append(signal)
    maximum_timestamp = "2026-07-15T06:30:00.123456+00:00"
    maximum_data = _feed(
        max_signals,
        generated_at=maximum_timestamp,
        signal_count=10_000,
        universe_size=10_000,
    )
    maximum_data["provider"] = "p" * 64
    maximum_data["min_notional"] = 1_000_000_000_000
    maximum = _available(
        maximum_data,
        meta_generated_at=maximum_timestamp,
    )
    compact = json.dumps(
        maximum,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode()
    if len(compact) >= OPTIONS_FLOW_MAX_RESPONSE_BYTES:
        raise AssertionError(len(compact))
    maximum_result = _load_with_response(
        httpx.Response(
            200,
            content=compact,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-store",
            },
        )
    )
    if not isinstance(maximum_result, _read_api.OptionsFlowApiAvailable):
        raise AssertionError(maximum_result)

    exact_body = compact + b" " * (
        OPTIONS_FLOW_MAX_RESPONSE_BYTES - len(compact)
    )
    exact = _load_with_response(
        httpx.Response(
            200,
            content=exact_body,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-store",
            },
        )
    )
    if not isinstance(exact, _read_api.OptionsFlowApiAvailable):
        raise AssertionError(exact)

    stream = TrackingAsyncStream([exact_body, b" ", b"must-not-be-consumed"])
    oversized = _load_with_response(
        httpx.Response(
            200,
            stream=stream,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-store",
            },
        )
    )
    if not isinstance(oversized, _read_api.OptionsFlowApiFailure):
        raise AssertionError(oversized)
    if oversized.reason != "response_too_large":
        raise AssertionError(oversized)
    if stream.yielded != 2 or not stream.closed:
        raise AssertionError((stream.yielded, stream.closed))

    expanded_stream = TrackingAsyncStream(
        [gzip.compress(b"x" * (OPTIONS_FLOW_MAX_RESPONSE_BYTES + 1)), b"unused"]
    )
    compressed = _load_with_response(
        httpx.Response(
            200,
            stream=expanded_stream,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-store",
                "Content-Encoding": "gzip",
            },
        )
    )
    if not isinstance(compressed, _read_api.OptionsFlowApiFailure):
        raise AssertionError(compressed)
    if compressed.reason != "response_too_large":
        raise AssertionError(compressed)
    if expanded_stream.yielded != 1 or not expanded_stream.closed:
        raise AssertionError((expanded_stream.yielded, expanded_stream.closed))


def test_authoritative_unavailable_messages_are_exact() -> None:
    for reason, detail in UNAVAILABLE_DETAILS.items():
        api_result = _read_api.OptionsFlowApiUnavailable(reason)
        with patch(
            "ui.options_flow._read_api.load_options_flow",
            return_value=api_result,
        ):
            state = options_flow._load_options_flow()
        if state.status != "api_unavailable" or state.feed is not None:
            raise AssertionError(state)
        if options_flow._unavailable_message(reason) != (
            f"異常流資料目前無法使用：{detail}"
        ):
            raise AssertionError((reason, options_flow._unavailable_message(reason)))


def test_all_client_failures_are_api_only_and_fail_soft() -> None:
    expected_statuses = {
        "api_available",
        "api_unavailable",
        "api_failure",
    }
    if set(get_args(options_flow.OptionsFlowPageStatus)) != expected_statuses:
        raise AssertionError(get_args(options_flow.OptionsFlowPageStatus))

    for reason in CLIENT_FAILURE_REASONS:
        failure = _read_api.OptionsFlowApiFailure(reason)
        with patch(
            "ui.options_flow._read_api.load_options_flow",
            return_value=failure,
        ):
            state = options_flow._load_options_flow()
        if (
            state.status != "api_failure"
            or state.feed is not None
            or state.reason != reason
        ):
            raise AssertionError((reason, state))

    with patch(
        "ui.options_flow._read_api.load_options_flow",
        return_value=object(),
    ):
        unexpected = options_flow._load_options_flow()
    if unexpected != _state("api_failure", None, "invalid_envelope"):
        raise AssertionError(unexpected)

    resolver_source = inspect.getsource(options_flow._load_options_flow)
    for forbidden in (
        "read_artifact",
        "ARTIFACTS",
        "ArtifactAvailable",
        "OptionsFlowFeedData.model_validate",
        "_read_local_options_flow",
        "_LOCAL_OPTIONS_FLOW_FALLBACK_REASONS",
        "local_fallback",
        "all_unavailable",
        "LOGGER",
    ):
        if forbidden in resolver_source:
            raise AssertionError((forbidden, resolver_source))


def test_failed_and_unavailable_reads_recover_on_next_call() -> None:
    api_feed = _feed_model([_signal("AAPL")])
    results = [
        _read_api.OptionsFlowApiFailure("transport_error"),
        _read_api.OptionsFlowApiAvailable(api_feed),
    ]
    with (
        patch(
            "ui.options_flow._read_api.load_options_flow",
            side_effect=results,
        ) as api_read,
        patch("ui.options_flow._live_chain") as live_chain,
    ):
        failed = options_flow._load_options_flow()
        repaired = options_flow._load_options_flow()
    if failed.status != "api_failure" or repaired.status != "api_available":
        raise AssertionError((failed, repaired))
    if repaired.feed is None or repaired.feed.signals[0].ticker != "AAPL":
        raise AssertionError(repaired)
    if api_read.call_count != 2:
        raise AssertionError(api_read.call_count)
    live_chain.assert_not_called()

    unavailable_then_repaired = [
        _read_api.OptionsFlowApiUnavailable("missing"),
        _read_api.OptionsFlowApiAvailable(api_feed),
    ]
    with patch(
        "ui.options_flow._read_api.load_options_flow",
        side_effect=unavailable_then_repaired,
    ):
        unavailable = options_flow._load_options_flow()
        available = options_flow._load_options_flow()
    if unavailable.status != "api_unavailable" or available.status != "api_available":
        raise AssertionError((unavailable, available))


def test_both_valid_empty_semantics_keep_provenance_and_skip_live_chain() -> None:
    wrapper = "from ui.options_flow import render\nrender()\n"
    empty_feeds = (
        _feed_model([], signal_count=0, universe_size=0),
        _feed_model([], signal_count=5, universe_size=50),
    )
    for feed in empty_feeds:
        state = _state("api_available", feed)
        with (
            patch("ui.options_flow._load_options_flow", return_value=state),
            patch("ui.options_flow._live_chain") as live_chain,
        ):
            app = AppTest.from_string(wrapper, default_timeout=10).run()
        if app.exception:
            raise AssertionError((feed, app.exception))
        rendered = _app_text(app)
        expected_provenance = (
            f"資料 {feed.as_of} · 來源 {feed.provider} · "
            f"掃描 {feed.universe_size} 檔 · 偵測 {feed.signal_count} 筆"
        )
        if expected_provenance not in rendered:
            raise AssertionError(rendered)
        if "目前沒有可顯示的異常流訊號。" not in rendered:
            raise AssertionError(rendered)
        if app.tabs or app.dataframe:
            raise AssertionError((app.tabs, app.dataframe))
        live_chain.assert_not_called()

    state_cases = [
        (
            _state("api_unavailable", None, "invalid_json"),
            "異常流資料目前無法使用：異常流資料尚未完整寫入或 JSON 格式無效。",
            None,
        ),
        (
            _state("api_failure", None, "transport_error"),
            "異常流資料暫時無法使用；請稍後重試。",
            "異常流 API 暫時無法使用。",
        ),
        (
            _state("api_failure", None, "response_too_large"),
            "異常流資料暫時無法使用；請稍後重試。",
            "異常流 API 回應超過安全讀取上限。",
        ),
    ]
    for state, expected, expected_warning in state_cases:
        with (
            patch("ui.options_flow._load_options_flow", return_value=state),
            patch("ui.options_flow._live_chain") as live_chain,
        ):
            app = AppTest.from_string(wrapper, default_timeout=10).run()
        if app.exception:
            raise AssertionError((state, app.exception))
        rendered = _app_text(app)
        if expected not in rendered:
            raise AssertionError((state, rendered))
        if expected_warning is not None and expected_warning not in rendered:
            raise AssertionError((state, rendered))
        live_chain.assert_not_called()


def test_populated_render_preserves_feed_detail_chart_handoff_and_provider_boundary() -> None:
    wrapper = "from ui.options_flow import render\nrender()\n"
    feed = _feed_model(
        [
            _signal("NVDA", score=92.0),
            _signal("AAPL", direction="bearish", score=81.0),
        ]
    )
    state = _state("api_available", feed)
    with (
        patch("ui.options_flow._load_options_flow", return_value=state),
        patch("ui.options_flow._live_chain", return_value=_live_result()) as live_chain,
    ):
        app = AppTest.from_string(wrapper, default_timeout=10).run()
    if app.exception:
        raise AssertionError(app.exception)
    live_chain.assert_called_once_with("NVDA")
    if app.warning:
        raise AssertionError([item.value for item in app.warning])
    if [tab.label for tab in app.tabs] != ["🔥 異常流排行", "🔎 個股明細"]:
        raise AssertionError([tab.label for tab in app.tabs])
    expected_columns = [
        "方向",
        "代號",
        "估權利金",
        "熱度",
        "V/OI峰值",
        "最活躍履約",
        "skew",
        "標籤",
    ]
    if len(app.dataframe) != 1:
        raise AssertionError(app.dataframe)
    if list(app.dataframe[0].value.columns) != expected_columns:
        raise AssertionError(list(app.dataframe[0].value.columns))
    rendered = _app_text(app)
    for label in ("估權利金", "最活躍履約價", "V/OI 峰值", "call/put 量比"):
        if label not in rendered:
            raise AssertionError((label, rendered))
    if len(app.get("plotly_chart")) != 1:
        raise AssertionError(app.get("plotly_chart"))
    if "到期 2026-08-21 的鏈成交量分布。" not in rendered:
        raise AssertionError(rendered)

    checkup_buttons = [button for button in app.button if button.label == "🔍 個股總覽"]
    if len(checkup_buttons) != 1:
        raise AssertionError([button.label for button in app.button])
    with (
        patch("ui.options_flow._load_options_flow", return_value=state),
        patch("ui.options_flow._live_chain", return_value=_live_result()),
    ):
        clicked = checkup_buttons[0].click().run()
    if clicked.exception:
        raise AssertionError(clicked.exception)
    if clicked.session_state["checkup_ticker"] != "NVDA":
        raise AssertionError(clicked.session_state)
    if clicked.session_state["checkup_handoff"] != "NVDA":
        raise AssertionError(clicked.session_state)

def test_stale_selection_remains_safe() -> None:
    wrapper = "from ui.options_flow import render\nrender()\n"
    feed = _feed_model([_signal("NVDA")])
    state = _state("api_available", feed)
    app = AppTest.from_string(wrapper, default_timeout=10)
    app.session_state["flow_feed_sel"] = {
        "selection": {"rows": [99], "columns": [], "cells": []}
    }
    with (
        patch("ui.options_flow._load_options_flow", return_value=state),
        patch("ui.options_flow._live_chain", return_value=None),
    ):
        app.run()
    if app.exception:
        raise AssertionError(app.exception)
    if any("已選" in str(item.value) for item in app.markdown):
        raise AssertionError([item.value for item in app.markdown])


def test_sources_are_python310_fixed_and_scoped() -> None:
    feed = _feed_model()
    outcomes = (
        _read_api.OptionsFlowApiAvailable(feed),
        _read_api.OptionsFlowApiUnavailable("missing"),
        _read_api.OptionsFlowApiFailure("transport_error"),
        options_flow.OptionsFlowPageState("api_available", feed, None),
    )
    for outcome in outcomes:
        field = next(iter(outcome.__dataclass_fields__))
        try:
            setattr(outcome, field, "changed")
        except FrozenInstanceError:
            pass
        else:
            raise AssertionError(outcome)

    paths = (
        ROOT / "ui" / "_read_api.py",
        ROOT / "ui" / "options_flow.py",
        Path(__file__),
    )
    for path in paths:
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path), feature_version=(3, 10))

    client_source = (ROOT / "ui" / "_read_api.py").read_text(encoding="utf-8")
    client_tree = ast.parse(client_source)
    imported_modules = {
        alias.name
        for node in ast.walk(client_tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module or ""
        for node in ast.walk(client_tree)
        if isinstance(node, ast.ImportFrom)
    )
    imported_roots = {
        module.split(".", 1)[0]
        for module in imported_modules
        if module
    }
    if "streamlit" in imported_roots or "api.main" in imported_modules:
        raise AssertionError(imported_modules)
    if "st.cache_data" in client_source or "asyncio.timeout(" in client_source:
        raise AssertionError("client must be uncached and Python 3.10 compatible")

    page_source = (ROOT / "ui" / "options_flow.py").read_text(encoding="utf-8")
    resolver_source = inspect.getsource(options_flow._load_options_flow)
    if "st.cache_data" in resolver_source or "_shared.load_json" in resolver_source:
        raise AssertionError("resolver must be uncached and API-only")
    for forbidden in (
        "from api.artifacts",
        "read_artifact",
        "ARTIFACTS",
        "_read_local_options_flow",
        "scripts.artifact_loader",
    ):
        if forbidden in page_source:
            raise AssertionError((forbidden, page_source))
    live_source = inspect.getsource(options_flow._live_chain)
    if "options_free.analyze_options" not in live_source or "@st.cache_data" not in live_source:
        raise AssertionError("live provider boundary changed")


def main() -> None:
    tests = [
        test_fixed_request_signature_configuration_and_raw_reader_boundary,
        test_available_values_order_metadata_and_invalid_envelope_matrix,
        test_complete_failure_matrix_and_size_stream_cleanup,
        test_authoritative_unavailable_messages_are_exact,
        test_all_client_failures_are_api_only_and_fail_soft,
        test_failed_and_unavailable_reads_recover_on_next_call,
        test_both_valid_empty_semantics_keep_provenance_and_skip_live_chain,
        test_populated_render_preserves_feed_detail_chart_handoff_and_provider_boundary,
        test_stale_selection_remains_safe,
        test_sources_are_python310_fixed_and_scoped,
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
