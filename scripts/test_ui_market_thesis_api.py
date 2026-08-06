#!/usr/bin/env python3
"""Focused API/client/page contracts for the Phase 4D Market Thesis slice."""

from __future__ import annotations

import ast
import json
import sys
import tempfile
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import datetime
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
    ArtifactSpec,
    ResolvedArtifactPath,
    read_artifact,
)
from api.main import create_app  # noqa: E402
from api.models import (  # noqa: E402
    ArtifactAvailable,
    ArtifactUnavailable,
    MarketThesisData,
)
from ui import _read_api, market_thesis  # noqa: E402


SOURCE_ID = "market-context.market-thesis.latest"
ROUTE = "/api/v1/market-context/market-thesis/latest"
URL = f"http://127.0.0.1:8000{ROUTE}"
PUBLIC_FIELDS = {
    "as_of",
    "generated_at",
    "direction",
    "bucket",
    "support_class",
    "manifest_status",
    "regime",
    "vix_bucket",
    "rationale",
    "label",
}
RATIONALE_FIELDS = {
    "analog",
    "manifest_missing",
    "manifest_stale",
    "manifest_events",
}
ANALOG_FIELDS = {
    "status",
    "resolved",
    "mean",
    "up_rate",
    "ci90",
    "p10",
    "worst_mdd",
}
EVENT_FIELDS = {
    "type",
    "source_id",
    "present",
    "fresh",
    "stale_reason",
    "value",
    "delta_1d",
    "last_rate",
    "next_meeting_at",
}


def _source(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "as_of": "2026-08-01",
        "generated_at": "2026-08-01T02:03:04.123456+00:00",
        "tier": 1,
        "method": "deterministic_baseline",
        "benchmark": "^GSPC",
        "direction": "盤整",
        "bucket": "mid",
        "support_class": "regime_only",
        "manifest_status": "degraded",
        "regime": "range",
        "vix_bucket": "normal",
        "rationale": {
            "analog": {
                "resolved": 491,
                "mean": 0.011,
                "median": 0.0305,
                "up_rate": 0.6578,
                "ci90": [0.006, 0.0158],
                "p10": -0.0841,
                "worst": -0.3259,
                "mean_mdd": -0.0627,
                "worst_mdd": -0.3259,
            },
            "bear_telemetry": None,
            "manifest_missing": ["CPI", "JOBS", "UST10Y"],
            "manifest_stale": ["FOMC"],
            "macro": {"FOMC": "3.50-3.75%", "DXY": 101.533},
            "manifest_events": [
                {
                    "type": "CPI",
                    "source_id": "fred:CPIAUCSL",
                    "present": False,
                    "fresh": False,
                    "stale_reason": "missing",
                },
                {
                    "type": "FOMC",
                    "source_id": "calendar:fomc",
                    "present": True,
                    "fresh": False,
                    "stale_reason": "decision_not_refreshed",
                    "last_decision_at": "2026-06-17",
                    "last_rate": "3.50-3.75%",
                    "next_meeting_at": "2026-08-12",
                    "rate_as_of": "2026-07-01",
                },
                {
                    "type": "DXY",
                    "source_id": "yf:DX-Y.NYB",
                    "present": True,
                    "fresh": True,
                    "stale_reason": None,
                    "released_at": "2026-08-01",
                    "value": 101.533,
                    "delta_1d": 0.063,
                },
            ],
        },
        "label": "探索性,未驗證,非投資建議",
    }
    payload.update(overrides)
    return payload


def _public(**overrides: object) -> dict[str, object]:
    source = _source()
    rationale = source["rationale"]
    if not isinstance(rationale, dict):
        raise AssertionError(rationale)
    analog = rationale["analog"]
    if not isinstance(analog, dict):
        raise AssertionError(analog)
    events = rationale["manifest_events"]
    if not isinstance(events, list):
        raise AssertionError(events)
    payload = {key: source[key] for key in PUBLIC_FIELDS}
    payload["rationale"] = {
        "analog": {key: analog.get(key) for key in ANALOG_FIELDS},
        "manifest_missing": rationale["manifest_missing"],
        "manifest_stale": rationale["manifest_stale"],
        "manifest_events": [
            {key: event.get(key) for key in EVENT_FIELDS}
            for event in events
            if isinstance(event, dict)
        ],
    }
    payload.update(overrides)
    return payload


def _envelope(
    data: dict[str, object] | None = None,
    *,
    available: bool = True,
    reason: str = "ok",
    source_id: str = SOURCE_ID,
    as_of: str | None = "2026-08-01",
    generated_at: str | None = "2026-08-01T02:03:04.123456+00:00",
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
        ARTIFACTS[SOURCE_ID],
        resolver=lambda: ResolvedArtifactPath(path, as_of="2026-08-01"),
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


def test_registry_projection_is_strict_bounded_and_private_fields_are_omitted() -> None:
    spec = ARTIFACTS[SOURCE_ID]
    if spec.data_model is not MarketThesisData:
        raise AssertionError(spec.data_model)
    if spec.data_validator is None or spec.data_projector is None:
        raise AssertionError(spec)
    if spec.object_list_fields or spec.string_fields or spec.date_fields:
        raise AssertionError(spec)

    with tempfile.TemporaryDirectory() as tmp:
        result = read_artifact(_spec(_write(Path(tmp) / "forecast.json", _source())))
    if not isinstance(result, ArtifactAvailable):
        raise AssertionError(result)
    if set(result.data) != PUBLIC_FIELDS:
        raise AssertionError(result.data)
    rationale = result.data["rationale"]
    if not isinstance(rationale, dict) or set(rationale) != RATIONALE_FIELDS:
        raise AssertionError(rationale)
    if set(rationale["analog"]) != ANALOG_FIELDS:
        raise AssertionError(rationale["analog"])
    if any(set(event) != EVENT_FIELDS for event in rationale["manifest_events"]):
        raise AssertionError(rationale["manifest_events"])
    rendered = json.dumps(result.data, ensure_ascii=False)
    for private in (
        "tier",
        "method",
        "benchmark",
        "macro",
        "bear_telemetry",
        "median",
        "mean_mdd",
        "last_decision_at",
        "released_at",
    ):
        if private in rendered:
            raise AssertionError((private, rendered))
    MarketThesisData.model_validate(result.data)


def test_source_and_public_invariants_fail_soft() -> None:
    invalid_sources = [
        _source(secret="private"),
        _source(direction="neutral"),
        _source(bucket="weekly"),
        _source(manifest_status="degraded", support_class="event_only"),
        _source(as_of="2026-02-30"),
        _source(generated_at="2026-08-01T02:03:04"),
    ]
    duplicate_event = deepcopy(_source())
    duplicate_event["rationale"]["manifest_events"].append(  # type: ignore[index]
        deepcopy(duplicate_event["rationale"]["manifest_events"][0])  # type: ignore[index]
    )
    invalid_sources.append(duplicate_event)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "forecast.json"
        for payload in invalid_sources:
            _write(path, payload)
            result = read_artifact(_spec(path))
            if not isinstance(result, ArtifactUnavailable) or result.reason != "invalid_shape":
                raise AssertionError((payload, result))

    invalid_public = _public()
    invalid_public["benchmark"] = "^GSPC"
    try:
        MarketThesisData.model_validate(invalid_public)
    except ValueError:
        pass
    else:
        raise AssertionError("strict Market Thesis DTO accepted a private field")


def test_fixed_route_returns_only_the_typed_projection() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _write(Path(tmp) / "forecast.json", _source())
        registry = dict(ARTIFACTS)
        registry[SOURCE_ID] = _spec(path)
        with _client(registry) as client:
            response = client.get(ROUTE)
            ignored_query = client.get(ROUTE, params={"path": "/etc/passwd"})
    if response.status_code != 200 or response.headers.get("cache-control") != "no-store":
        raise AssertionError((response.status_code, response.headers, response.text))
    body = response.json()
    if set(body["data"]) != PUBLIC_FIELDS or ignored_query.json() != body:
        raise AssertionError(body)
    if body["meta"]["asOf"] != body["data"]["as_of"]:
        raise AssertionError(body)
    meta_generated_at = datetime.fromisoformat(
        body["meta"]["generatedAt"].replace("Z", "+00:00")
    )
    data_generated_at = datetime.fromisoformat(
        body["data"]["generated_at"].replace("Z", "+00:00")
    )
    if meta_generated_at != data_generated_at:
        raise AssertionError(body)


def test_fixed_client_validates_provenance_and_failure_matrix() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _http_response(_envelope(_public()))

    available = _read_api.load_market_thesis(
        transport=httpx.MockTransport(handler)
    )
    if not isinstance(available, _read_api.MarketThesisApiAvailable):
        raise AssertionError(available)
    if available.forecast.direction != "盤整":
        raise AssertionError(available)
    if len(seen) != 1 or str(seen[0].url) != URL or seen[0].method != "GET":
        raise AssertionError(seen)

    unavailable_payload = _envelope(
        available=False,
        reason="missing",
        as_of=None,
        generated_at=None,
    )
    unavailable = _read_api.load_market_thesis(
        transport=httpx.MockTransport(
            lambda _request: _http_response(unavailable_payload)
        )
    )
    if unavailable != _read_api.MarketThesisApiUnavailable("missing"):
        raise AssertionError(unavailable)

    failures = [
        (httpx.Response(503), "http_status"),
        (
            httpx.Response(
                200,
                headers={"Content-Type": "text/plain", "Cache-Control": "no-store"},
            ),
            "invalid_media_type",
        ),
        (
            httpx.Response(200, headers={"Content-Type": "application/json"}, json={}),
            "invalid_cache_control",
        ),
        (_http_response({"not": "an envelope"}), "invalid_envelope"),
        (_http_response(_envelope(_public(), source_id="market.private")), "invalid_envelope"),
        (_http_response(_envelope(_public(), as_of="2026-07-31")), "invalid_envelope"),
        (
            _http_response(
                _envelope(_public(), generated_at="2026-08-01T02:03:05+00:00")
            ),
            "invalid_envelope",
        ),
    ]
    for response, reason in failures:
        result = _read_api.load_market_thesis(
            transport=httpx.MockTransport(
                lambda _request, response=response: response
            )
        )
        if result != _read_api.MarketThesisApiFailure(reason):
            raise AssertionError((reason, result))

    oversized = httpx.Response(
        200,
        headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        content=b"x" * (_read_api._MARKET_THESIS_MAX_RESPONSE_BYTES + 1),
    )
    result = _read_api.load_market_thesis(
        transport=httpx.MockTransport(lambda _request: oversized)
    )
    if result != _read_api.MarketThesisApiFailure("response_too_large"):
        raise AssertionError(result)


def test_page_latest_and_summary_resolvers_are_api_only() -> None:
    forecast = MarketThesisData.model_validate(_public())
    with patch(
        "ui.market_thesis._read_api.load_market_thesis",
        return_value=_read_api.MarketThesisApiAvailable(forecast),
    ):
        loaded = market_thesis._latest_forecast()
    if loaded is None or loaded.get("direction") != "盤整":
        raise AssertionError(loaded)

    for result in (
        _read_api.MarketThesisApiUnavailable("missing"),
        _read_api.MarketThesisApiFailure("transport_error"),
    ):
        with patch(
            "ui.market_thesis._read_api.load_market_thesis",
            return_value=result,
        ), patch(
            "ui.market_thesis._shared.load_json",
            side_effect=AssertionError("latest forecast attempted a local fallback"),
        ):
            if market_thesis._latest_forecast() is not None:
                raise AssertionError(result)

    source = (ROOT / "ui" / "market_thesis.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="ui/market_thesis.py", feature_version=(3, 10))
    resolver = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_latest_forecast"
    )
    resolver_source = ast.get_source_segment(source, resolver) or ""
    for forbidden in ("glob(", ".exists(", "read_artifact", "ARTIFACTS"):
        if forbidden in resolver_source:
            raise AssertionError((forbidden, resolver_source))
    if "_read_api.load_market_thesis()" not in resolver_source:
        raise AssertionError(resolver_source)
    for required in (
        "_read_api.load_market_thesis_validation()",
        "_read_api.load_market_thesis_regime_history()",
    ):
        if required not in source:
            raise AssertionError(required)
    for forbidden in ("validation_summary.json", "regime_history.json"):
        if forbidden in source:
            raise AssertionError(f"Market Thesis retained local read: {forbidden}")


def test_page_renders_available_and_unavailable_states_without_exception() -> None:
    forecast = MarketThesisData.model_validate(_public())
    wrapper = "from ui.market_thesis import render\nrender()\n"
    with patch(
        "ui.market_thesis._read_api.load_market_thesis",
        return_value=_read_api.MarketThesisApiAvailable(forecast),
    ), patch(
        "ui.market_thesis._read_api.load_market_thesis_validation",
        return_value=_read_api.MarketThesisValidationApiUnavailable("missing"),
    ), patch(
        "ui.market_thesis._read_api.load_market_thesis_regime_history",
        return_value=_read_api.MarketThesisRegimeHistoryApiUnavailable("missing"),
    ):
        app = AppTest.from_string(wrapper, default_timeout=10).run()
    if app.exception:
        raise AssertionError(app.exception)

    for result in (
        _read_api.MarketThesisApiUnavailable("missing"),
        _read_api.MarketThesisApiFailure("transport_error"),
    ):
        with patch(
            "ui.market_thesis._read_api.load_market_thesis",
            return_value=result,
        ), patch(
            "ui.market_thesis._read_api.load_market_thesis_validation",
            return_value=_read_api.MarketThesisValidationApiUnavailable("missing"),
        ), patch(
            "ui.market_thesis._read_api.load_market_thesis_regime_history",
            return_value=_read_api.MarketThesisRegimeHistoryApiUnavailable("missing"),
        ):
            app = AppTest.from_string(wrapper, default_timeout=10).run()
        if app.exception or not app.info:
            raise AssertionError((result, app.exception, app.info))


def test_outcomes_are_immutable_and_sources_are_python310_compatible() -> None:
    forecast = MarketThesisData.model_validate(_public())
    outcomes = (
        (_read_api.MarketThesisApiAvailable(forecast), "forecast", forecast),
        (_read_api.MarketThesisApiUnavailable("missing"), "reason", "unreadable"),
        (_read_api.MarketThesisApiFailure("transport_error"), "reason", "http_status"),
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
        "ui/market_thesis.py",
        "scripts/test_ui_market_thesis_api.py",
    ):
        path = ROOT / relative
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
            feature_version=(3, 10),
        )


def main() -> None:
    tests = [
        test_registry_projection_is_strict_bounded_and_private_fields_are_omitted,
        test_source_and_public_invariants_fail_soft,
        test_fixed_route_returns_only_the_typed_projection,
        test_fixed_client_validates_provenance_and_failure_matrix,
        test_page_latest_and_summary_resolvers_are_api_only,
        test_page_renders_available_and_unavailable_states_without_exception,
        test_outcomes_are_immutable_and_sources_are_python310_compatible,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
