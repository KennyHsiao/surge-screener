#!/usr/bin/env python3
"""Focused API/client/page contracts for the Crypto Universe API-only slice."""

from __future__ import annotations

import ast
import json
import sys
import tempfile
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.artifacts import (  # noqa: E402
    ARTIFACTS,
    CRYPTO_UNIVERSE_SOURCE_ID,
    ArtifactSpec,
    ResolvedArtifactPath,
    read_artifact,
)
from api.main import create_app  # noqa: E402
from api.models import (  # noqa: E402
    ArtifactAvailable,
    ArtifactUnavailable,
    CryptoUniverseData,
)
from ui import _read_api, crypto_universe  # noqa: E402


CRYPTO_ROUTE = "/api/v1/crypto/universe"
CRYPTO_URL = f"http://127.0.0.1:8000{CRYPTO_ROUTE}"
PUBLIC_FIELDS = {
    "date",
    "source",
    "source_status",
    "stale",
    "stale_source_date",
    "count",
    "universe",
    "added",
    "removed",
    "compared_to",
}


def _source(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "date": "2026-08-01",
        "source": "binance_fapi_exchangeInfo",
        "source_status": "live",
        "stale": False,
        "stale_source_date": None,
        "fetch_error": None,
        "count": 2,
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "universe": [
            {
                "symbol": "BTCUSDT",
                "base": "BTC",
                "tv_symbol": "BINANCE:BTCUSDT.P",
                "onboard_date": "2019-09-25",
            },
            {
                "symbol": "ETHUSDT",
                "base": "ETH",
                "tv_symbol": "BINANCE:ETHUSDT.P",
                "onboard_date": None,
            },
        ],
        "added": ["ETHUSDT"],
        "removed": ["SOLUSDT"],
        "compared_to": "2026-07-31",
    }
    payload.update(overrides)
    return payload


def _public(**overrides: object) -> dict[str, object]:
    payload = {key: value for key, value in _source().items() if key in PUBLIC_FIELDS}
    payload.update(overrides)
    return payload


def _envelope(
    data: dict[str, object] | None = None,
    *,
    available: bool = True,
    reason: str = "ok",
    source_id: str = CRYPTO_UNIVERSE_SOURCE_ID,
    as_of: str | None = "2026-08-01",
    generated_at: str | None = None,
) -> dict[str, object]:
    return {
        "available": available,
        "reason": reason,
        "data": data if available else None,
        "meta": {
            "sourceId": source_id,
            "asOf": as_of,
            "generatedAt": generated_at,
        },
    }


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _spec(path: Path) -> ArtifactSpec:
    return replace(
        ARTIFACTS[CRYPTO_UNIVERSE_SOURCE_ID],
        resolver=lambda: ResolvedArtifactPath(path),
    )


def _client(registry: dict[str, ArtifactSpec]) -> TestClient:
    target = create_app(registry)

    async def with_loopback(scope, receive, send):
        if scope["type"] == "http":
            scope = {**scope, "client": ("127.0.0.1", 50000)}
        await target(scope, receive, send)

    return TestClient(with_loopback, base_url="http://127.0.0.1")


def _http_response(payload: object, **overrides: object) -> httpx.Response:
    options: dict[str, object] = {
        "status_code": 200,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
        },
        "content": json.dumps(payload).encode("utf-8"),
    }
    options.update(overrides)
    return httpx.Response(**options)


def test_registry_projection_is_strict_public_and_source_preserving() -> None:
    spec = ARTIFACTS[CRYPTO_UNIVERSE_SOURCE_ID]
    if spec.data_model is not CryptoUniverseData:
        raise AssertionError(spec.data_model)
    if spec.data_validator is None or spec.data_projector is None:
        raise AssertionError(spec)
    if spec.as_of_extractor is None or spec.object_list_fields:
        raise AssertionError(spec)

    with tempfile.TemporaryDirectory() as tmp:
        path = _write(Path(tmp) / "universe_latest.json", _source())
        result = read_artifact(_spec(path))
    if not isinstance(result, ArtifactAvailable):
        raise AssertionError(result)
    if set(result.data) != PUBLIC_FIELDS:
        raise AssertionError(result.data)
    if "fetch_error" in result.data or "symbols" in result.data:
        raise AssertionError(result.data)
    if result.meta.source_id != CRYPTO_UNIVERSE_SOURCE_ID:
        raise AssertionError(result.meta)
    if result.meta.as_of is None or result.meta.as_of.isoformat() != "2026-08-01":
        raise AssertionError(result.meta)
    CryptoUniverseData.model_validate(result.data)

    unicode_payload = deepcopy(_source())
    unicode_payload["count"] = 3
    unicode_payload["symbols"] = ["BTCUSDT", "ETHUSDT", "币安人生USDT"]
    unicode_payload["universe"] = [
        *_source()["universe"],
        {
            "symbol": "币安人生USDT",
            "base": "币安人生",
            "tv_symbol": "BINANCE:币安人生USDT.P",
            "onboard_date": None,
        },
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path = _write(Path(tmp) / "universe_latest.json", unicode_payload)
        unicode_result = read_artifact(_spec(path))
    if not isinstance(unicode_result, ArtifactAvailable):
        raise AssertionError(unicode_result)
    if unicode_result.data["universe"][-1]["symbol"] != "币安人生USDT":
        raise AssertionError(unicode_result.data)


def test_source_and_public_invariants_fail_soft() -> None:
    invalid_sources: list[dict[str, object]] = []
    extra = _source(secret="private")
    invalid_sources.append(extra)
    reserved_symbol = deepcopy(_source())
    reserved_symbol["symbols"] = ["BTC:USDT", "ETHUSDT"]
    reserved_symbol["universe"][0]["symbol"] = "BTC:USDT"
    reserved_symbol["universe"][0]["tv_symbol"] = "BINANCE:BTC:USDT.P"
    invalid_sources.extend(
        [
            reserved_symbol,
            _source(fetch_error=["traceback"]),
            _source(count=3),
            _source(symbols=["ETHUSDT", "BTCUSDT"]),
            _source(added=["ETHUSDT", "ETHUSDT"]),
            _source(removed=["BTCUSDT"]),
            _source(source_status="live", stale=True),
            _source(compared_to="2026-08-02"),
        ]
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "universe_latest.json"
        for payload in invalid_sources:
            _write(path, payload)
            result = read_artifact(_spec(path))
            if not isinstance(result, ArtifactUnavailable) or result.reason != "invalid_shape":
                raise AssertionError((payload, result))

    invalid_public = _public()
    invalid_public["fetch_error"] = "must stay private"
    try:
        CryptoUniverseData.model_validate(invalid_public)
    except ValueError:
        pass
    else:
        raise AssertionError("strict public DTO accepted a private field")


def test_fixed_http_route_returns_typed_projection_without_private_fields() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _write(Path(tmp) / "universe_latest.json", _source())
        registry = dict(ARTIFACTS)
        registry[CRYPTO_UNIVERSE_SOURCE_ID] = _spec(path)
        with _client(registry) as client:
            response = client.get(CRYPTO_ROUTE)
            ignored_query = client.get(CRYPTO_ROUTE, params={"path": "/etc/passwd"})
    if response.status_code != 200 or response.headers.get("cache-control") != "no-store":
        raise AssertionError((response.status_code, response.headers, response.text))
    body = response.json()
    if set(body["data"]) != PUBLIC_FIELDS:
        raise AssertionError(body)
    if ignored_query.json() != body:
        raise AssertionError(ignored_query.json())
    if "fetch_error" in response.text or "symbols" in body["data"]:
        raise AssertionError(body)


def test_fixed_client_accepts_strict_available_and_authoritative_unavailable() -> None:
    seen: list[httpx.Request] = []

    def available_handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _http_response(_envelope(_public()))

    available = _read_api.load_crypto_universe(
        transport=httpx.MockTransport(available_handler)
    )
    if not isinstance(available, _read_api.CryptoUniverseApiAvailable):
        raise AssertionError(available)
    if available.snapshot.count != 2 or available.snapshot.universe[0].symbol != "BTCUSDT":
        raise AssertionError(available)
    if len(seen) != 1 or str(seen[0].url) != CRYPTO_URL:
        raise AssertionError(seen)
    if seen[0].method != "GET" or seen[0].headers.get("accept") != "application/json":
        raise AssertionError(seen[0])

    unavailable_payload = _envelope(
        available=False,
        reason="missing",
        as_of=None,
    )
    unavailable = _read_api.load_crypto_universe(
        transport=httpx.MockTransport(lambda _request: _http_response(unavailable_payload))
    )
    if unavailable != _read_api.CryptoUniverseApiUnavailable("missing"):
        raise AssertionError(unavailable)


def test_client_failure_matrix_cap_and_recovery_are_fail_soft() -> None:
    failures = [
        (httpx.Response(503), "http_status"),
        (
            httpx.Response(200, headers={"Content-Type": "text/plain", "Cache-Control": "no-store"}),
            "invalid_media_type",
        ),
        (
            httpx.Response(200, headers={"Content-Type": "application/json"}, json={}),
            "invalid_cache_control",
        ),
        (_http_response({"not": "an envelope"}), "invalid_envelope"),
        (
            _http_response(_envelope(_public(), source_id="crypto.private")),
            "invalid_envelope",
        ),
        (
            _http_response(_envelope(_public(), as_of="2026-07-31")),
            "invalid_envelope",
        ),
    ]
    for response, reason in failures:
        result = _read_api.load_crypto_universe(
            transport=httpx.MockTransport(lambda _request, response=response: response)
        )
        if result != _read_api.CryptoUniverseApiFailure(reason):
            raise AssertionError((reason, result))

    oversized = httpx.Response(
        200,
        headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        content=b"x" * (_read_api._CRYPTO_UNIVERSE_MAX_RESPONSE_BYTES + 1),
    )
    result = _read_api.load_crypto_universe(
        transport=httpx.MockTransport(lambda _request: oversized)
    )
    if result != _read_api.CryptoUniverseApiFailure("response_too_large"):
        raise AssertionError(result)

    responses = iter(
        [
            httpx.Response(503),
            _http_response(_envelope(_public())),
        ]
    )
    transport = httpx.MockTransport(lambda _request: next(responses))
    first = _read_api.load_crypto_universe(transport=transport)
    second = _read_api.load_crypto_universe(transport=transport)
    if first != _read_api.CryptoUniverseApiFailure("http_status"):
        raise AssertionError(first)
    if not isinstance(second, _read_api.CryptoUniverseApiAvailable):
        raise AssertionError(second)


def test_page_uses_validated_api_data_and_derived_tradingview_export() -> None:
    snapshot = CryptoUniverseData.model_validate(_public())
    expected_export = "BINANCE:BTCUSDT.P\nBINANCE:ETHUSDT.P\n"
    if crypto_universe._tradingview_export(snapshot) != expected_export:
        raise AssertionError(crypto_universe._tradingview_export(snapshot))

    wrapper = "from ui.crypto_universe import render\nrender()\n"
    with patch(
        "ui.crypto_universe._read_api.load_crypto_universe",
        return_value=_read_api.CryptoUniverseApiAvailable(snapshot),
    ):
        app = AppTest.from_string(wrapper, default_timeout=10).run()
    if app.exception:
        raise AssertionError(app.exception)
    metric_values = {(item.label, item.value) for item in app.metric}
    expected_metrics = {
        ("目前合約數", "2"),
        ("➕ 今日新增", "1"),
        ("➖ 今日下架", "1"),
    }
    if metric_values != expected_metrics:
        raise AssertionError(metric_values)
    if len(app.get("download_button")) != 1:
        raise AssertionError(app.get("download_button"))


def test_page_unavailable_states_never_read_local_files() -> None:
    wrapper = "from ui.crypto_universe import render\nrender()\n"
    cases = (
        _read_api.CryptoUniverseApiUnavailable("missing"),
        _read_api.CryptoUniverseApiFailure("transport_error"),
    )
    for result in cases:
        with patch(
            "ui.crypto_universe._read_api.load_crypto_universe",
            return_value=result,
        ):
            app = AppTest.from_string(wrapper, default_timeout=10).run()
        if app.exception or not app.warning:
            raise AssertionError((result, app.exception, app.warning))
        if app.metric or app.get("download_button") or app.dataframe:
            raise AssertionError((result, app))

    source = (ROOT / "ui" / "crypto_universe.py").read_text(encoding="utf-8")
    for forbidden in (
        "_shared",
        "pandas",
        "Path(",
        ".read_text(",
        ".exists(",
        "reports/crypto",
        "tradingview_watchlist.txt",
    ):
        if forbidden in source:
            raise AssertionError(f"Crypto Universe retained a local dependency: {forbidden}")
    tree = ast.parse(source, filename="ui/crypto_universe.py", feature_version=(3, 10))
    if any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open" for node in ast.walk(tree)):
        raise AssertionError("Crypto Universe retained a local open() call")


def test_outcomes_are_immutable_and_sources_are_python310_compatible() -> None:
    snapshot = CryptoUniverseData.model_validate(_public())
    outcomes = (
        (_read_api.CryptoUniverseApiAvailable(snapshot), "snapshot", snapshot),
        (_read_api.CryptoUniverseApiUnavailable("missing"), "reason", "unreadable"),
        (_read_api.CryptoUniverseApiFailure("transport_error"), "reason", "http_status"),
    )
    for outcome, field, value in outcomes:
        try:
            setattr(outcome, field, value)
        except FrozenInstanceError:
            continue
        raise AssertionError(outcome)

    for relative in (
        "api/models.py",
        "api/artifacts.py",
        "api/main.py",
        "ui/_read_api.py",
        "ui/crypto_universe.py",
        "scripts/test_ui_crypto_universe_api.py",
    ):
        path = ROOT / relative
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
            feature_version=(3, 10),
        )


def main() -> None:
    tests = [
        test_registry_projection_is_strict_public_and_source_preserving,
        test_source_and_public_invariants_fail_soft,
        test_fixed_http_route_returns_typed_projection_without_private_fields,
        test_fixed_client_accepts_strict_available_and_authoritative_unavailable,
        test_client_failure_matrix_cap_and_recovery_are_fail_soft,
        test_page_uses_validated_api_data_and_derived_tradingview_export,
        test_page_unavailable_states_never_read_local_files,
        test_outcomes_are_immutable_and_sources_are_python310_compatible,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
