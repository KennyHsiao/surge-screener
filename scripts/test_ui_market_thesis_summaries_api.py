#!/usr/bin/env python3
"""Focused API/client/page contracts for Phase 5G/5H Market Thesis summaries."""

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
    ArtifactSpec,
    ResolvedArtifactPath,
    read_artifact,
)
from api.main import create_app  # noqa: E402
from api.models import (  # noqa: E402
    ArtifactAvailable,
    ArtifactUnavailable,
    MarketThesisRegimeHistoryData,
    MarketThesisValidationData,
)
from ui import _read_api  # noqa: E402


VALIDATION_SOURCE_ID = "market-context.market-thesis.validation"
REGIME_SOURCE_ID = "market-context.market-thesis.regime-history"
VALIDATION_ROUTE = "/api/v1/market-context/market-thesis/validation"
REGIME_ROUTE = "/api/v1/market-context/market-thesis/regime-history"


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(path)
    return payload


def _write(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _spec(source_id: str, path: Path) -> ArtifactSpec:
    return replace(
        ARTIFACTS[source_id],
        resolver=lambda: ResolvedArtifactPath(path),
    )


def _client(registry: dict[str, ArtifactSpec]) -> TestClient:
    target = create_app(registry)

    async def with_loopback(scope, receive, send):
        if scope["type"] == "http":
            scope = {**scope, "client": ("127.0.0.1", 50000)}
        await target(scope, receive, send)

    return TestClient(with_loopback, base_url="http://127.0.0.1")


def _envelope(source_id: str, data: dict[str, object] | None) -> dict[str, object]:
    return {
        "available": data is not None,
        "reason": "ok" if data is not None else "missing",
        "data": data,
        "meta": {"sourceId": source_id, "asOf": None, "generatedAt": None},
    }


def _response(payload: object) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        content=json.dumps(payload).encode("utf-8"),
    )


def _regime_source() -> dict[str, object]:
    window = {
        "resolved": 10,
        "mean": 0.02,
        "median": 0.01,
        "up_rate": 0.6,
        "ci90": [0.01, 0.03],
        "p10": -0.05,
        "worst": -0.2,
        "mean_mdd": -0.03,
        "worst_mdd": -0.25,
    }
    regime = {
        "days": 10,
        "fwd_20d": deepcopy(window),
        "fwd_40d": deepcopy(window),
        "fwd_60d": deepcopy(window),
    }
    return {
        "generated_at": "2026-08-04T02:03:04+00:00",
        "benchmark": "^GSPC",
        "vix": "^VIX",
        "lookback_period": "20y",
        "rules": {"private": True},
        "forward_windows_sessions": [20, 40, 60],
        "note": "private regime note",
        "regime_summary": {
            "rally": deepcopy(regime),
            "correction": deepcopy(regime),
            "range": deepcopy(regime),
        },
        "correction_episodes": [],
        "regime_runs": [],
        "daily": [],
    }


def test_real_artifacts_project_only_bounded_public_summaries() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        fixtures = (
            (
                VALIDATION_SOURCE_ID,
                ROOT / "reports/market_thesis/validation_summary.json",
                MarketThesisValidationData,
                {
                    "validation_status",
                    "resolved",
                    "matured",
                    "min_resolved_for_verdict",
                    "reject_count",
                    "invalid_count",
                    "by_key",
                },
                (
                    "benchmark",
                    "theta_dir",
                    "buckets",
                    "invalid_records",
                    "rejected_ledgers",
                    "note",
                ),
            ),
            (
                REGIME_SOURCE_ID,
                _write(Path(tmp) / "regime.json", _regime_source()),
                MarketThesisRegimeHistoryData,
                {"regime_summary"},
                (
                    "daily",
                    "regime_runs",
                    "correction_episodes",
                    "rules",
                    "vix",
                    "benchmark",
                    "note",
                ),
            ),
        )
        for source_id, path, model, fields, private_fields in fixtures:
            result = read_artifact(_spec(source_id, path))
            if not isinstance(result, ArtifactAvailable) or set(result.data) != fields:
                raise AssertionError((source_id, result))
            model.model_validate(result.data, strict=True)
            rendered = json.dumps(result.data)
            for private in private_fields:
                if f'"{private}"' in rendered:
                    raise AssertionError((source_id, private))
            if len(rendered.encode("utf-8")) >= 128 * 1024:
                raise AssertionError((source_id, len(rendered)))


def test_malformed_sources_fail_soft_and_public_models_are_closed() -> None:
    validation = _load_json(ROOT / "reports/market_thesis/validation_summary.json")
    regime = _regime_source()
    invalid = (
        (VALIDATION_SOURCE_ID, {**validation, "private": True}),
        (VALIDATION_SOURCE_ID, {**validation, "matured": validation["resolved"] + 1}),
        (REGIME_SOURCE_ID, {**regime, "forward_windows_sessions": [20, 40]}),
        (
            REGIME_SOURCE_ID,
            {
                **regime,
                "regime_summary": {
                    **regime["regime_summary"],
                    "rally": {**regime["regime_summary"]["rally"], "days": -1},
                },
            },
        ),
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "source.json"
        for source_id, payload in invalid:
            result = read_artifact(_spec(source_id, _write(path, payload)))
            if not isinstance(result, ArtifactUnavailable) or result.reason != "invalid_shape":
                raise AssertionError((source_id, result))

    for model, payload in (
        (MarketThesisValidationData, {"private": True}),
        (MarketThesisRegimeHistoryData, {"daily": []}),
    ):
        try:
            model.model_validate(payload, strict=True)
        except ValueError:
            continue
        raise AssertionError((model, payload))


def test_fixed_routes_and_clients_preserve_exact_contracts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        registry = dict(ARTIFACTS)
        validation_path = ROOT / "reports/market_thesis/validation_summary.json"
        regime_path = _write(Path(tmp) / "regime.json", _regime_source())
        registry[VALIDATION_SOURCE_ID] = _spec(VALIDATION_SOURCE_ID, validation_path)
        registry[REGIME_SOURCE_ID] = _spec(REGIME_SOURCE_ID, regime_path)
        with _client(registry) as client:
            validation_response = client.get(VALIDATION_ROUTE)
            regime_response = client.get(REGIME_ROUTE)
    for response in (validation_response, regime_response):
        if response.status_code != 200 or response.headers.get("cache-control") != "no-store":
            raise AssertionError((response.status_code, response.headers, response.text))
        if response.json()["meta"]["asOf"] is not None or response.json()["meta"]["generatedAt"] is not None:
            raise AssertionError(response.json())

    validation_data = validation_response.json()["data"]
    regime_data = regime_response.json()["data"]
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.path == VALIDATION_ROUTE:
            return _response(_envelope(VALIDATION_SOURCE_ID, validation_data))
        if request.url.path == REGIME_ROUTE:
            return _response(_envelope(REGIME_SOURCE_ID, regime_data))
        raise AssertionError(request.url)

    transport = httpx.MockTransport(handler)
    validation_result = _read_api.load_market_thesis_validation(transport=transport)
    regime_result = _read_api.load_market_thesis_regime_history(transport=transport)
    if not isinstance(validation_result, _read_api.MarketThesisValidationApiAvailable):
        raise AssertionError(validation_result)
    if not isinstance(regime_result, _read_api.MarketThesisRegimeHistoryApiAvailable):
        raise AssertionError(regime_result)
    if seen != [
        f"http://127.0.0.1:8000{VALIDATION_ROUTE}",
        f"http://127.0.0.1:8000{REGIME_ROUTE}",
    ]:
        raise AssertionError(seen)

    for loader, source_id, data, available_type, unavailable_type, failure_type, cap in (
        (
            _read_api.load_market_thesis_validation,
            VALIDATION_SOURCE_ID,
            validation_data,
            _read_api.MarketThesisValidationApiAvailable,
            _read_api.MarketThesisValidationApiUnavailable,
            _read_api.MarketThesisValidationApiFailure,
            _read_api._MARKET_THESIS_VALIDATION_MAX_RESPONSE_BYTES,
        ),
        (
            _read_api.load_market_thesis_regime_history,
            REGIME_SOURCE_ID,
            regime_data,
            _read_api.MarketThesisRegimeHistoryApiAvailable,
            _read_api.MarketThesisRegimeHistoryApiUnavailable,
            _read_api.MarketThesisRegimeHistoryApiFailure,
            _read_api._MARKET_THESIS_REGIME_HISTORY_MAX_RESPONSE_BYTES,
        ),
    ):
        unavailable = loader(
            transport=httpx.MockTransport(lambda _request: _response(_envelope(source_id, None)))
        )
        if unavailable != unavailable_type("missing"):
            raise AssertionError(unavailable)
        wrong_source = deepcopy(_envelope(source_id, data))
        wrong_source["meta"]["sourceId"] = "private.source"
        invalid = loader(transport=httpx.MockTransport(lambda _request: _response(wrong_source)))
        if invalid != failure_type("invalid_envelope"):
            raise AssertionError(invalid)
        oversized = httpx.Response(
            200,
            headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
            content=b"x" * (cap + 1),
        )
        too_large = loader(transport=httpx.MockTransport(lambda _request: oversized))
        if too_large != failure_type("response_too_large"):
            raise AssertionError(too_large)
        if not isinstance(loader(transport=transport), available_type):
            raise AssertionError(loader)


def test_page_resolvers_are_api_only_and_render_fail_soft() -> None:
    validation_data = MarketThesisValidationData.model_validate(
        read_artifact(
            _spec(
                VALIDATION_SOURCE_ID,
                ROOT / "reports/market_thesis/validation_summary.json",
            )
        ).data,
        strict=True,
    )
    with tempfile.TemporaryDirectory() as tmp:
        regime_data = MarketThesisRegimeHistoryData.model_validate(
            read_artifact(
                _spec(
                    REGIME_SOURCE_ID,
                    _write(Path(tmp) / "regime.json", _regime_source()),
                )
            ).data,
            strict=True,
        )
    with (
        patch(
            "ui.market_thesis._read_api.load_market_thesis_validation",
            return_value=_read_api.MarketThesisValidationApiAvailable(validation_data),
        ) as validation_loader,
        patch(
            "ui.market_thesis._read_api.load_market_thesis_regime_history",
            return_value=_read_api.MarketThesisRegimeHistoryApiAvailable(regime_data),
        ) as regime_loader,
    ):
        app = AppTest.from_string(
            "from ui.market_thesis import _render_regime_reference, _render_validation, "
            "_validation_summary, _regime_history_summary\n"
            "_render_validation(_validation_summary())\n"
            "_render_regime_reference(_regime_history_summary())\n",
            default_timeout=10,
        ).run()
    if app.exception or validation_loader.call_count != 1 or regime_loader.call_count != 1:
        raise AssertionError((app.exception, validation_loader.call_count, regime_loader.call_count))

    with (
        patch(
            "ui.market_thesis._read_api.load_market_thesis_validation",
            return_value=_read_api.MarketThesisValidationApiFailure("transport_error"),
        ),
        patch(
            "ui.market_thesis._read_api.load_market_thesis_regime_history",
            return_value=_read_api.MarketThesisRegimeHistoryApiUnavailable("missing"),
        ),
        patch(
            "ui.market_thesis._shared.load_json",
            side_effect=AssertionError("summary resolver attempted local fallback"),
        ),
    ):
        app = AppTest.from_string(
            "from ui.market_thesis import _render_regime_reference, _render_validation, "
            "_validation_summary, _regime_history_summary\n"
            "_render_validation(_validation_summary())\n"
            "_render_regime_reference(_regime_history_summary())\n",
            default_timeout=10,
        ).run()
    if app.exception or not app.info or not app.caption:
        raise AssertionError((app.exception, app.info, app.caption))

    path = ROOT / "ui/market_thesis.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    if "load_market_thesis_validation()" not in functions["_validation_summary"]:
        raise AssertionError(functions["_validation_summary"])
    if "load_market_thesis_regime_history()" not in functions["_regime_history_summary"]:
        raise AssertionError(functions["_regime_history_summary"])
    for forbidden in ("validation_summary.json", "regime_history.json"):
        if forbidden in source:
            raise AssertionError((forbidden, source))


def test_outcomes_are_immutable_and_sources_are_python310_compatible() -> None:
    outcomes = (
        (_read_api.MarketThesisValidationApiUnavailable("missing"), "reason", "unreadable"),
        (_read_api.MarketThesisValidationApiFailure("transport_error"), "reason", "http_status"),
        (_read_api.MarketThesisRegimeHistoryApiUnavailable("missing"), "reason", "unreadable"),
        (_read_api.MarketThesisRegimeHistoryApiFailure("transport_error"), "reason", "http_status"),
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
        "scripts/test_ui_market_thesis_summaries_api.py",
    ):
        path = ROOT / relative
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 10))


def main() -> None:
    tests = (
        test_real_artifacts_project_only_bounded_public_summaries,
        test_malformed_sources_fail_soft_and_public_models_are_closed,
        test_fixed_routes_and_clients_preserve_exact_contracts,
        test_page_resolvers_are_api_only_and_render_fail_soft,
        test_outcomes_are_immutable_and_sources_are_python310_compatible,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
