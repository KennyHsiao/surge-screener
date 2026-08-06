#!/usr/bin/env python3
"""Behavior tests for the Streamlit fund-catalog read-API consumer."""

from __future__ import annotations

import ast
import asyncio
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

from api.models import FundCatalogData  # noqa: E402
from ui import _read_api, institution_portfolio, institutional_holdings  # noqa: E402


FUND_CATALOG_URL = "http://127.0.0.1:8000/api/v1/institutions/funds"
FUND_CATALOG_MAX_RESPONSE_BYTES = 512 * 1024


def _fund(cik: str = "0001067983", note: str = "長期價值") -> dict[str, str]:
    return {"cik": cik, "note": note}


def _available(
    funds: dict[str, dict[str, str]],
    *,
    source_id: str = "institutions.funds",
    as_of: str | None = None,
    generated_at: str | None = None,
) -> dict[str, object]:
    return {
        "available": True,
        "reason": "ok",
        "data": {"funds": funds},
        "meta": {
            "sourceId": source_id,
            "asOf": as_of,
            "generatedAt": generated_at,
        },
    }


def _unavailable(
    reason: str,
    *,
    source_id: str = "institutions.funds",
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


def _load_with_response(response: httpx.Response) -> object:
    return _read_api.load_fund_catalog(
        transport=httpx.MockTransport(lambda _request: response)
    )


def _option(
    name: str = "Alpha Capital",
    cik: str = "0001067983",
    note: str = "First note",
) -> SimpleNamespace:
    return SimpleNamespace(display_name=name, cik=cik, note=note)


def _state(
    status: str,
    options: tuple[object, ...] = (),
    reason: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(status=status, options=options, reason=reason)


def _filing(
    *,
    fund: str | None = "SEC Legal Name",
    lag_days: int = 200,
    holdings: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    if holdings is None:
        holdings = [
            {
                "issuer": "Example Inc",
                "pct": 12.5,
                "value": 2_000_000_000.0,
                "shares": 10_000.0,
                "put_call": None,
            }
        ]
    return {
        "fund": fund,
        "cik": 1067983,
        "report_date": "2026-03-31",
        "filing_date": "2026-05-15",
        "lag_days": lag_days,
        "total_value": 2_000_000_000.0,
        "holdings_count": len(holdings),
        "holdings": holdings,
    }


def _app_text(app: AppTest) -> str:
    values: list[str] = []
    for elements in (
        app.header,
        app.caption,
        app.warning,
        app.info,
        app.error,
        app.markdown,
    ):
        values.extend(str(element.value) for element in elements)
    return "\n".join(values)


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


def test_fixed_client_request_signature_order_and_values() -> None:
    _assert_transport_only_signature(_read_api.load_schedules)
    _assert_transport_only_signature(_read_api.load_ai_updates)
    _assert_transport_only_signature(_read_api.load_fund_catalog)

    requests: list[httpx.Request] = []
    funds = {
        "Alpha Capital": _fund("0001067983", "First note"),
        "Beta Partners": _fund("1234567", "Second note"),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _json_response(_available(funds))

    result = _read_api.load_fund_catalog(transport=httpx.MockTransport(handler))
    if not isinstance(result, _read_api.FundCatalogApiAvailable):
        raise AssertionError(result)
    actual = [
        (option.display_name, option.cik, option.note)
        for option in result.options
    ]
    if actual != [
        ("Alpha Capital", "0001067983", "First note"),
        ("Beta Partners", "1234567", "Second note"),
    ]:
        raise AssertionError(actual)
    if len(requests) != 1:
        raise AssertionError(requests)
    request = requests[0]
    if request.method != "GET" or str(request.url) != FUND_CATALOG_URL:
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


def test_empty_unavailable_and_strict_metadata_contracts() -> None:
    empty = _load_with_response(_json_response(_available({})))
    if not isinstance(empty, _read_api.FundCatalogApiAvailable) or empty.options:
        raise AssertionError(empty)

    for reason in ("missing", "invalid_json", "invalid_shape", "unreadable"):
        result = _load_with_response(_json_response(_unavailable(reason)))
        if not isinstance(result, _read_api.FundCatalogApiUnavailable):
            raise AssertionError((reason, result))
        if result.reason != reason:
            raise AssertionError((reason, result))

    invalid_payloads = [
        _available({"Alpha": _fund()}, source_id="system.ai-updates"),
        _available({"Alpha": _fund()}, as_of="2026-07-15"),
        _available(
            {"Alpha": _fund()},
            generated_at="2026-07-15T00:00:00Z",
        ),
        {**_available({"Alpha": _fund()}), "secret": "body-secret"},
        {
            **_available({"Alpha": _fund()}),
            "data": {
                "funds": {"Alpha": _fund()},
                "_note": "body-secret",
            },
        },
        _available({" Alpha ": _fund()}),
        _available({"Alpha": {**_fund(), "secret": "body-secret"}}),
        _available({"Alpha": _fund(cik="not-cik")}),
        _available({"Alpha": _fund(note="x" * 201)}),
        _available({"Alpha": {"cik": "123", "note": 1}}),
        _unavailable("missing", as_of="2026-07-15"),
        _unavailable("missing", source_id="system.schedules"),
        _unavailable("missing", generated_at="2026-07-15T00:00:00Z"),
    ]
    for payload in invalid_payloads:
        result = _load_with_response(_json_response(payload))
        if not isinstance(result, _read_api.FundCatalogApiFailure):
            raise AssertionError(result)
        if result.reason != "invalid_envelope" or "body-secret" in repr(result):
            raise AssertionError(result)


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

    outcomes["transport_error"] = _read_api.load_fund_catalog(
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
        outcomes["deadline_exceeded"] = _read_api.load_fund_catalog()

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
            content=b"x" * (FUND_CATALOG_MAX_RESPONSE_BYTES + 1),
            headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        )
    )
    outcomes["invalid_envelope"] = _load_with_response(
        httpx.Response(
            200,
            content=b'{"available":',
            headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        )
    )

    for expected, result in outcomes.items():
        if not isinstance(result, _read_api.FundCatalogApiFailure):
            raise AssertionError((expected, result))
        if result.reason != expected:
            raise AssertionError((expected, result))
        exposed = repr(result)
        if "transport-secret" in exposed or "evil.invalid" in exposed:
            raise AssertionError((expected, exposed))


def test_maximum_catalog_exact_cap_and_cap_plus_one_stream_cleanup() -> None:
    funds = {
        "😀" * 119 + chr(0x1F680 + index): {
            "cik": str(1_000_000_000 + index),
            "note": "😀" * 200,
        }
        for index in range(100)
    }
    FundCatalogData.model_validate({"funds": funds}, strict=True)
    if len(funds) != 100 or len(set(funds)) != 100:
        raise AssertionError("maximum catalog keys are not unique")
    if {len(name) for name in funds} != {120}:
        raise AssertionError("maximum catalog names are not 120 codepoints")
    if {len(item["note"]) for item in funds.values()} != {200}:
        raise AssertionError("maximum catalog notes are not 200 codepoints")
    if {len(item["cik"]) for item in funds.values()} != {10}:
        raise AssertionError("maximum catalog CIKs are not 10 digits")

    compact = json.dumps(
        _available(funds),
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode()
    if len(compact) != 387_523:
        raise AssertionError(len(compact))
    accepted = _load_with_response(
        httpx.Response(
            200,
            content=compact,
            headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        )
    )
    if not isinstance(accepted, _read_api.FundCatalogApiAvailable):
        raise AssertionError(accepted)

    exact_body = compact + b" " * (FUND_CATALOG_MAX_RESPONSE_BYTES - len(compact))
    if len(exact_body) != FUND_CATALOG_MAX_RESPONSE_BYTES:
        raise AssertionError(len(exact_body))
    exact = _load_with_response(
        httpx.Response(
            200,
            content=exact_body,
            headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        )
    )
    if not isinstance(exact, _read_api.FundCatalogApiAvailable):
        raise AssertionError(exact)

    stream = TrackingAsyncStream([exact_body, b" ", b"must-not-be-consumed"])
    oversized = _load_with_response(
        httpx.Response(
            200,
            stream=stream,
            headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        )
    )
    if not isinstance(oversized, _read_api.FundCatalogApiFailure):
        raise AssertionError(oversized)
    if oversized.reason != "response_too_large":
        raise AssertionError(oversized)
    if stream.yielded != 2 or not stream.closed:
        raise AssertionError((stream.yielded, stream.closed))


def test_authoritative_unavailable_never_reads_local_and_keeps_reason() -> None:
    for reason in ("missing", "invalid_json", "invalid_shape", "unreadable"):
        with patch(
            "ui.institution_portfolio._read_api.load_fund_catalog",
            return_value=_read_api.FundCatalogApiUnavailable(reason),
        ):
            state = institution_portfolio._load_fund_catalog()
        if state.status != "api_unavailable" or state.reason != reason:
            raise AssertionError((reason, state))
        if state.options:
            raise AssertionError(state)


def test_client_failure_is_api_only_and_never_reads_local_catalog() -> None:
    with patch(
        "ui.institution_portfolio._read_api.load_fund_catalog",
        return_value=_read_api.FundCatalogApiFailure("transport_error"),
    ):
        state = institution_portfolio._load_fund_catalog()
    if (
        state.status != "api_failure"
        or state.reason != "transport_error"
        or state.options
    ):
        raise AssertionError(state)

    source = (ROOT / "ui" / "institution_portfolio.py").read_text(encoding="utf-8")
    for forbidden in (
        "read_artifact",
        "ARTIFACTS",
        "FundCatalogData",
        "scripts.artifact_loader",
        "_read_local_fund_catalog",
        '"local_fallback"',
        '"all_unavailable"',
    ):
        if forbidden in source:
            raise AssertionError(f"Fund Catalog API-only boundary contains {forbidden}")


def test_failed_rerun_recovers_immediately_without_negative_cache() -> None:
    requests = 0
    responses = iter(
        [
            _json_response(_unavailable("missing")),
            _json_response(_available({"First recovery": _fund("111", "API")})),
            httpx.Response(503),
            _json_response(_available({"Second recovery": _fund("222", "API")})),
        ]
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return next(responses)

    transport = httpx.MockTransport(handler)
    direct_results = [
        _read_api.load_fund_catalog(transport=transport)
        for _ in range(4)
    ]
    if not isinstance(direct_results[0], _read_api.FundCatalogApiUnavailable):
        raise AssertionError(direct_results)
    if not isinstance(direct_results[1], _read_api.FundCatalogApiAvailable):
        raise AssertionError(direct_results)
    if not isinstance(direct_results[2], _read_api.FundCatalogApiFailure):
        raise AssertionError(direct_results)
    if direct_results[2].reason != "http_status":
        raise AssertionError(direct_results)
    if not isinstance(direct_results[3], _read_api.FundCatalogApiAvailable):
        raise AssertionError(direct_results)
    if requests != 4:
        raise AssertionError(requests)

    api_results = [
        _read_api.FundCatalogApiFailure("transport_error"),
        _read_api.FundCatalogApiAvailable(
            (_read_api.FundCatalogOption("Recovered", "123", "API"),)
        ),
    ]
    with (
        patch(
            "ui.institution_portfolio._read_api.load_fund_catalog",
            side_effect=api_results,
        ) as api_read,
    ):
        first = institution_portfolio._load_fund_catalog()
        second = institution_portfolio._load_fund_catalog()
    if first.status != "api_failure" or second.status != "api_available":
        raise AssertionError((first, second))
    if api_read.call_count != 2:
        raise AssertionError(api_read.call_count)


def test_client_failure_state_is_sanitized_and_manual_cik_ready() -> None:
    state = _state("api_failure", reason="transport_error")
    adapted = institution_portfolio._catalog_data_state(state)
    if (
        adapted.source != "unavailable"
        or adapted.content != "unknown"
        or adapted.reason_code != "transport_error"
        or adapted.recovery_key != "manual-cik"
    ):
        raise AssertionError(adapted)


def test_target_resolution_preserves_cik_manual_precedence_and_friendly_copy() -> None:
    options = (
        _read_api.FundCatalogOption("Alpha Capital", "0001067983", "First"),
        _read_api.FundCatalogOption("Beta Partners", "1234567", "Second"),
    )
    quick = institution_portfolio._resolve_target(options, "Alpha Capital", "")
    if (
        quick is None
        or quick.query != "0001067983"
        or quick.label != "Alpha Capital"
        or quick.quick_pick_name != "Alpha Capital"
    ):
        raise AssertionError(quick)
    manual = institution_portfolio._resolve_target(options, "Alpha Capital", " 00999 ")
    if manual is None or (manual.query, manual.label, manual.quick_pick_name) != (
        "00999",
        "00999",
        None,
    ):
        raise AssertionError(manual)

    cached = _filing(fund="0001067983")
    displayed = institution_portfolio._display_data(cached, quick)
    if displayed is cached or displayed.get("fund") != "Alpha Capital":
        raise AssertionError(displayed)
    if cached.get("fund") != "0001067983":
        raise AssertionError("cached provider result was mutated")
    missing_name = _filing(fund=None)
    missing_displayed = institution_portfolio._display_data(missing_name, quick)
    if missing_displayed is missing_name or missing_displayed.get("fund") != "Alpha Capital":
        raise AssertionError(missing_displayed)
    real_name = _filing(fund="SEC Legal Name")
    if institution_portfolio._display_data(real_name, quick) is not real_name:
        raise AssertionError("real SEC name should be retained without a copy")
    manual_data = _filing(fund="00999")
    if institution_portfolio._display_data(manual_data, manual) is not manual_data:
        raise AssertionError("manual CIK data must not be renamed")


def test_numeric_edgar_path_does_not_depend_on_local_catalog_contents() -> None:
    from scripts import edgar_13f

    recorded: list[tuple[str, object]] = []

    def cached(namespace: str, params: object, ttl: float, compute: object) -> dict[str, object]:
        _ = (ttl, compute)
        recorded.append((namespace, params))
        return {"ok": True}

    with (
        patch("scripts.edgar_13f.load_funds", return_value={}) as local_catalog,
        patch("scripts.edgar_13f._cached", side_effect=cached),
    ):
        result = edgar_13f.get_13f("0001067983")
    local_catalog.assert_called_once()
    if result != {"ok": True}:
        raise AssertionError(result)
    if recorded != [("edgar13f", {"cik": 1067983})]:
        raise AssertionError(recorded)


def test_quick_pick_format_first_selection_and_manual_cik_override() -> None:
    wrapper = "from ui.institution_portfolio import render\nrender()\n"
    state = _state(
        "api_available",
        (
            _option("Alpha Capital", "0001067983", "First note"),
            _option("Beta Partners", "1234567", "Second note"),
        ),
    )
    with (
        patch("ui.institution_portfolio._load_fund_catalog", return_value=state),
        patch("ui.institution_portfolio._load", return_value=None) as provider,
    ):
        app = AppTest.from_string(wrapper, default_timeout=10).run()
        if app.exception:
            raise AssertionError(app.exception)
        if len(app.selectbox) != 1 or app.selectbox[0].value != "Alpha Capital":
            raise AssertionError(app.selectbox)
        if app.selectbox[0].options != [
            "Alpha Capital · First note",
            "Beta Partners · Second note",
        ]:
            raise AssertionError(app.selectbox[0].options)
        provider.assert_called_once_with("0001067983")
        if "查無 13F:`Alpha Capital`" not in _app_text(app):
            raise AssertionError(_app_text(app))

        app.text_input[0].set_value("00999")
        app = app.run()
        if app.exception:
            raise AssertionError(app.exception)
        if provider.call_args_list[-1].args != ("00999",):
            raise AssertionError(provider.call_args_list)


def test_api_failure_warns_and_manual_cik_reaches_exact_provider() -> None:
    wrapper = "from ui.institution_portfolio import render\nrender()\n"
    state = _state("api_failure", reason="transport_error")
    with (
        patch("ui.institution_portfolio._load_fund_catalog", return_value=state),
        patch("ui.institution_portfolio._load", return_value=None) as provider,
    ):
        app = AppTest.from_string(wrapper, default_timeout=10).run()
        if app.exception or len(app.text_input) != 1:
            raise AssertionError((app.exception, app.text_input))
        provider.assert_not_called()
        warning_values = [str(item.value) for item in app.warning]
        if not any("權威來源不可用" in value for value in warning_values):
            raise AssertionError(warning_values)
        app.text_input[0].set_value("0000012345")
        app = app.run()
    if app.exception or provider.call_args_list[-1].args != ("0000012345",):
        raise AssertionError((app.exception, provider.call_args_list))


def test_all_catalog_states_keep_manual_cik_usable_and_offline() -> None:
    wrapper = "from ui.institution_portfolio import render\nrender()\n"
    states = [
        _state("api_available"),
        _state("api_unavailable", reason="missing"),
        _state("api_unavailable", reason="invalid_json"),
        _state("api_unavailable", reason="invalid_shape"),
        _state("api_unavailable", reason="unreadable"),
        _state("api_failure", reason="transport_error"),
    ]
    for state in states:
        with (
            patch("ui.institution_portfolio._load_fund_catalog", return_value=state),
            patch("ui.institution_portfolio._load", return_value=None) as provider,
        ):
            app = AppTest.from_string(wrapper, default_timeout=10).run()
            if app.exception or len(app.text_input) != 1:
                raise AssertionError((state, app.exception, app.text_input))
            provider.assert_not_called()
            app.text_input[0].set_value("0000123456")
            app = app.run()
            if app.exception:
                raise AssertionError((state, app.exception))
            if provider.call_args_list[-1].args != ("0000123456",):
                raise AssertionError((state, provider.call_args_list))

            text = _app_text(app)
            info_values = [str(item.value) for item in app.info]
            warning_values = [str(item.value) for item in app.warning]
            adapted = institution_portfolio._catalog_data_state(state)
            if adapted.source_id != "institutions.funds" or adapted.freshness != "unknown":
                raise AssertionError((state, adapted))
            if "仍可手動輸入 CIK" not in text:
                raise AssertionError((state, text))
            if state.status == "api_unavailable":
                expected = {
                    "missing": "找不到資料",
                    "invalid_json": "資料尚未完整寫入或格式無效",
                    "invalid_shape": "資料格式不符合預期",
                    "unreadable": "資料目前無法讀取",
                }[state.reason]
                if not any(
                    "權威來源不可用" in value and expected in value
                    for value in warning_values
                ):
                    raise AssertionError((state, warning_values))
            elif state.status == "api_failure":
                if not any("權威來源不可用" in value for value in warning_values):
                    raise AssertionError((warning_values, info_values))
            elif state.status == "api_available":
                if not any(
                    "權威來源可用" in value and "目前沒有資料" in value
                    for value in info_values
                ):
                    raise AssertionError((text, info_values))


def test_holdings_failure_empty_and_nonempty_rendering_are_preserved() -> None:
    wrapper = "from ui.institution_portfolio import render\nrender()\n"
    state = _state("api_available", (_option(),))

    with (
        patch("ui.institution_portfolio._load_fund_catalog", return_value=state),
        patch("ui.institution_portfolio._load", return_value=None),
    ):
        failed = AppTest.from_string(wrapper, default_timeout=10).run()
    if failed.exception or "查無 13F:`Alpha Capital`" not in _app_text(failed):
        raise AssertionError((failed.exception, _app_text(failed)))

    with (
        patch("ui.institution_portfolio._load_fund_catalog", return_value=state),
        patch(
            "ui.institution_portfolio._load",
            return_value=_filing(holdings=[]),
        ),
        patch("ui.institution_portfolio._shared.metric_card") as empty_metrics,
    ):
        empty = AppTest.from_string(wrapper, default_timeout=10).run()
    if empty.exception or "此申報無持股明細" not in _app_text(empty):
        raise AssertionError((empty.exception, _app_text(empty)))
    if empty_metrics.call_count != 4 or empty.dataframe:
        raise AssertionError((empty_metrics.call_count, empty.dataframe))

    with (
        patch("ui.institution_portfolio._load_fund_catalog", return_value=state),
        patch(
            "ui.institution_portfolio._load",
            return_value=_filing(fund="0001067983", lag_days=200),
        ),
        patch("ui.institution_portfolio._shared.metric_card") as metrics,
    ):
        full = AppTest.from_string(wrapper, default_timeout=10).run()
    if full.exception or len(full.dataframe) != 1 or len(full.error) != 1:
        raise AssertionError((full.exception, full.dataframe, full.error))
    if metrics.call_count != 4:
        raise AssertionError(metrics.call_args_list)
    if metrics.call_args_list[0].args[2] != "Alpha Capital":
        raise AssertionError(metrics.call_args_list[0])


def test_default_inverse_child_view_does_not_eagerly_read_fund_catalog() -> None:
    wrapper = "from ui.institutions import render\nrender()\n"
    with (
        patch("ui.institutional_holdings._load", return_value=None) as inverse_provider,
        patch("ui.institution_portfolio._read_api.load_fund_catalog") as catalog_api,
    ):
        app = AppTest.from_string(wrapper, default_timeout=10).run()
    if app.exception:
        raise AssertionError(app.exception)
    inverse_provider.assert_called_once_with("NVDA")
    catalog_api.assert_not_called()


def test_client_outcomes_are_immutable_and_sources_are_python310_compatible() -> None:
    option = _read_api.FundCatalogOption("Alpha", "123", "note")
    results = (
        _read_api.FundCatalogApiAvailable((option,)),
        _read_api.FundCatalogApiUnavailable("missing"),
        _read_api.FundCatalogApiFailure("transport_error"),
    )
    for value in (option, *results):
        try:
            setattr(value, next(iter(value.__dataclass_fields__)), "changed")
        except FrozenInstanceError:
            pass
        else:
            raise AssertionError(value)

    for path in (
        ROOT / "ui" / "_read_api.py",
        ROOT / "ui" / "institution_portfolio.py",
        Path(__file__),
    ):
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path), feature_version=(3, 10))
    read_source = (ROOT / "ui" / "_read_api.py").read_text(encoding="utf-8")
    read_tree = ast.parse(read_source)
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(read_tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(read_tree)
        if isinstance(node, ast.ImportFrom)
    )
    if "streamlit" in imported_roots:
        raise AssertionError("fixed API client must remain framework-neutral")


def main() -> None:
    tests = [
        test_fixed_client_request_signature_order_and_values,
        test_empty_unavailable_and_strict_metadata_contracts,
        test_complete_seven_reason_failure_matrix_is_stable_and_sanitized,
        test_maximum_catalog_exact_cap_and_cap_plus_one_stream_cleanup,
        test_authoritative_unavailable_never_reads_local_and_keeps_reason,
        test_client_failure_is_api_only_and_never_reads_local_catalog,
        test_failed_rerun_recovers_immediately_without_negative_cache,
        test_client_failure_state_is_sanitized_and_manual_cik_ready,
        test_target_resolution_preserves_cik_manual_precedence_and_friendly_copy,
        test_numeric_edgar_path_does_not_depend_on_local_catalog_contents,
        test_quick_pick_format_first_selection_and_manual_cik_override,
        test_api_failure_warns_and_manual_cik_reaches_exact_provider,
        test_all_catalog_states_keep_manual_cik_usable_and_offline,
        test_holdings_failure_empty_and_nonempty_rendering_are_preserved,
        test_default_inverse_child_view_does_not_eagerly_read_fund_catalog,
        test_client_outcomes_are_immutable_and_sources_are_python310_compatible,
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
