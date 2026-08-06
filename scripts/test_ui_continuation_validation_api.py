#!/usr/bin/env python3
"""Focused contracts for the Phase 6A-6C Continuation Validation slice."""

from __future__ import annotations

import ast
import asyncio
import json
import sys
import tempfile
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import yaml
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.artifacts import (  # noqa: E402
    ARTIFACTS,
    CONTINUATION_VALIDATION_SOURCE_ID,
    ArtifactSpec,
    ResolvedArtifactPath,
    read_artifact,
)
from api.main import create_app  # noqa: E402
from api.models import (  # noqa: E402
    ArtifactAvailable,
    ArtifactUnavailable,
    ContinuationValidationData,
)
from ui import _components, _read_api, continuation_validation  # noqa: E402


SOURCE_ID = "reports.continuation-validation.latest"
ROUTE = "/api/v1/reports/continuation-validation/latest"
URL = f"http://127.0.0.1:8000{ROUTE}"
ROW_FIELDS = {
    "ticker",
    "setup_date",
    "surge_start",
    "thresholds_hit",
    "magnitude_pct",
    "candidate_causes",
    "cause_certainty",
    "measurement_source",
    "resolved_30d",
    "fwd_30d_return",
    "fwd_30d_max_drawdown",
    "resolved_60d",
    "fwd_60d_return",
    "fwd_60d_max_drawdown",
    "continuation_label",
    "primary_horizon",
    "trade_value",
}


def _row(
    ticker: str = "NVDA",
    *,
    label: str = "strong_continuation",
) -> dict[str, object]:
    if label == "unresolved":
        return {
            "ticker": ticker,
            "setup_date": "2026-01-05",
            "surge_start": None,
            "thresholds_hit": [],
            "magnitude_pct": None,
            "candidate_causes": ["unknown"],
            "cause_certainty": "candidate_only",
            "measurement_source": "daily_bars",
            "resolved_30d": False,
            "fwd_30d_return": None,
            "fwd_30d_max_drawdown": None,
            "resolved_60d": False,
            "fwd_60d_return": None,
            "fwd_60d_max_drawdown": None,
            "continuation_label": "unresolved",
            "primary_horizon": None,
            "trade_value": "unknown",
        }
    if label == "normal_continuation":
        return {
            **_row(ticker, label="unresolved"),
            "resolved_30d": True,
            "fwd_30d_return": 0.05,
            "fwd_30d_max_drawdown": -0.08,
            "continuation_label": "normal_continuation",
            "primary_horizon": "30d",
            "trade_value": "medium",
        }
    return {
        **_row(ticker, label="unresolved"),
        "surge_start": "2026-01-02",
        "thresholds_hit": ["+30%/20d"],
        "magnitude_pct": 42.0,
        "candidate_causes": [
            "technical_volume_expansion",
            "relative_strength_leadership",
        ],
        "resolved_30d": True,
        "fwd_30d_return": 0.18,
        "fwd_30d_max_drawdown": -0.05,
        "resolved_60d": True,
        "fwd_60d_return": 0.34,
        "fwd_60d_max_drawdown": -0.13,
        "continuation_label": "strong_continuation",
        "primary_horizon": "30d",
        "trade_value": "high",
    }


def _source(status: str = "accumulating") -> dict[str, object]:
    generated_at = "2026-08-05T01:02:03+00:00"
    if status == "blocked":
        return {
            "generated_at": generated_at,
            "status": "blocked",
            "reason": "daily bars are missing at /private/reports/analytics",
            "resolved": 0,
            "min_resolved": 2,
            "summary": {},
            "rows": [],
        }
    rows = [
        _row(),
        _row(
            "MU",
            label="normal_continuation" if status == "ready" else "unresolved",
        ),
    ]
    resolved = 2 if status == "ready" else 1
    return {
        "generated_at": generated_at,
        "status": status,
        "resolved": resolved,
        "min_resolved": 2,
        "summary": {
            "strong_continuation": 1,
            "normal_continuation": 1 if status == "ready" else 0,
            "failed_breakout": 0,
            "unresolved": 0 if status == "ready" else 1,
            "rows_total": 2,
            "resolved": resolved,
            "min_resolved": 2,
        },
        "rows": rows,
        "note": "Candidate causes are labels, not causal proof.",
    }


def _public(source: dict[str, object]) -> dict[str, object]:
    blocked = source["status"] == "blocked"
    return {
        "generated_at": source["generated_at"],
        "status": source["status"],
        "resolved": source["resolved"],
        "min_resolved": source["min_resolved"],
        "summary": (
            {
                "strong_continuation": 0,
                "normal_continuation": 0,
                "failed_breakout": 0,
                "unresolved": 0,
                "rows_total": 0,
                "resolved": 0,
                "min_resolved": source["min_resolved"],
            }
            if blocked
            else source["summary"]
        ),
        "rows": source["rows"],
    }


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _spec(path: Path) -> ArtifactSpec:
    return replace(
        ARTIFACTS[SOURCE_ID],
        resolver=lambda: ResolvedArtifactPath(path),
    )


def _envelope(
    data: dict[str, object] | None,
    *,
    available: bool = True,
    reason: str = "ok",
    source_id: str = SOURCE_ID,
    as_of: str | None = None,
    generated_at: str | None = "2026-08-05T01:02:03+00:00",
) -> dict[str, object]:
    return {
        "available": available,
        "reason": reason,
        "data": data if available else None,
        "meta": {
            "sourceId": source_id,
            "asOf": as_of,
            "generatedAt": generated_at if available else None,
        },
    }


def _response(payload: object) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )


def _client(registry: dict[str, ArtifactSpec]) -> TestClient:
    target = create_app(registry)

    async def with_loopback(scope, receive, send):
        if scope["type"] == "http":
            scope = {**scope, "client": ("127.0.0.1", 50_000)}
        await target(scope, receive, send)

    return TestClient(with_loopback, base_url="http://127.0.0.1")


def test_source_families_projection_and_row_invariants_are_strict() -> None:
    if CONTINUATION_VALIDATION_SOURCE_ID != SOURCE_ID:
        raise AssertionError(CONTINUATION_VALIDATION_SOURCE_ID)
    spec = ARTIFACTS[SOURCE_ID]
    if spec.data_model is not ContinuationValidationData:
        raise AssertionError(spec.data_model)
    if spec.data_validator is None or spec.data_projector is None:
        raise AssertionError(spec)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "continuation_strength.json"
        for source in (_source("blocked"), _source(), _source("ready")):
            outcome = read_artifact(_spec(_write(path, source)))
            if not isinstance(outcome, ArtifactAvailable):
                raise AssertionError(outcome)
            if outcome.data != _public(source):
                raise AssertionError(outcome.data)
            for row in outcome.data["rows"]:
                if set(row) != ROW_FIELDS:
                    raise AssertionError(row)
            serialized = json.dumps(outcome.data)
            for private in ("daily bars are missing", "/private/", '"note"'):
                if private in serialized:
                    raise AssertionError((private, serialized))

        source = _source()
        invalid: list[dict[str, object]] = [{**source, "secret": True}]
        missing_note = deepcopy(source)
        missing_note.pop("note")
        invalid.append(missing_note)
        wrong_status = deepcopy(source)
        wrong_status["status"] = "ready"
        invalid.append(wrong_status)
        wrong_count = deepcopy(source)
        wrong_count["summary"]["unresolved"] = 0  # type: ignore[index]
        invalid.append(wrong_count)
        wrong_resolved = deepcopy(source)
        wrong_resolved["resolved"] = 2
        invalid.append(wrong_resolved)
        duplicate = deepcopy(source)
        duplicate["rows"].append(deepcopy(duplicate["rows"][0]))  # type: ignore[union-attr,index]
        invalid.append(duplicate)
        bad_pair = deepcopy(source)
        bad_pair["rows"][1]["fwd_30d_return"] = 0.0  # type: ignore[index]
        invalid.append(bad_pair)
        bad_label = deepcopy(source)
        bad_label["rows"][0]["continuation_label"] = "normal_continuation"  # type: ignore[index]
        invalid.append(bad_label)
        private_row = deepcopy(source)
        private_row["rows"][0]["flags"] = {"secret": True}  # type: ignore[index]
        invalid.append(private_row)
        too_many = deepcopy(source)
        too_many["rows"] = [_row(f"T{index}", label="unresolved") for index in range(5_001)]
        too_many["summary"] = {
            "strong_continuation": 0,
            "normal_continuation": 0,
            "failed_breakout": 0,
            "unresolved": 5_001,
            "rows_total": 5_001,
            "resolved": 0,
            "min_resolved": 2,
        }
        too_many["resolved"] = 0
        invalid.append(too_many)
        blocked = _source("blocked")
        blocked["reason"] = "x" * 4_001
        invalid.append(blocked)

        for payload in invalid:
            outcome = read_artifact(_spec(_write(path, payload)))
            if not isinstance(outcome, ArtifactUnavailable) or outcome.reason != "invalid_shape":
                raise AssertionError(outcome)


def test_route_openapi_and_fixed_client_are_strict_and_bounded() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _write(Path(tmp) / "continuation_strength.json", _source())
        registry = dict(ARTIFACTS)
        registry[SOURCE_ID] = _spec(path)
        with _client(registry) as client:
            response = client.get(ROUTE)
            generated = client.get("/openapi.json").json()
    if response.status_code != 200 or response.headers.get("cache-control") != "no-store":
        raise AssertionError((response.status_code, response.headers))
    payload = response.json()
    if payload["meta"] != {
        "sourceId": SOURCE_ID,
        "asOf": None,
        "generatedAt": "2026-08-05T01:02:03Z",
    }:
        raise AssertionError(payload)
    ContinuationValidationData.model_validate(payload["data"], strict=True)

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return _response(_envelope(_public(_source())))

    result = _read_api.load_continuation_validation(
        transport=httpx.MockTransport(handler)
    )
    if not isinstance(result, _read_api.ContinuationValidationApiAvailable):
        raise AssertionError(result)
    if seen != [URL]:
        raise AssertionError(seen)

    operation = generated["paths"][ROUTE]["get"]
    examples = operation["responses"]["200"]["content"]["application/json"]["examples"]
    if set(examples) != {"available", "blocked", "unavailable"}:
        raise AssertionError(examples)
    draft = yaml.safe_load((ROOT / "docs/api/quant-radar-v1.openapi.yaml").read_text())
    if draft["info"]["version"] != "1.23.0-draft" or ROUTE not in draft["paths"]:
        raise AssertionError(draft["info"])

    oversized = json.dumps(_envelope(_public(_source()))).encode("utf-8")
    oversized += b" " * (4 * 1024 * 1024)
    too_large = _read_api.load_continuation_validation(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
                content=oversized,
            )
        )
    )
    if too_large != _read_api.ContinuationValidationApiFailure("response_too_large"):
        raise AssertionError(too_large)


def test_client_failure_matrix_metadata_and_recovery_are_exact() -> None:
    valid = _envelope(_public(_source()))
    cases: tuple[tuple[str, httpx.Response | Exception], ...] = (
        ("transport_error", httpx.ConnectError("private")),
        ("http_status", httpx.Response(503)),
        ("invalid_media_type", httpx.Response(200, headers={"Content-Type": "text/plain", "Cache-Control": "no-store"}, text="{}")),
        ("invalid_cache_control", httpx.Response(200, headers={"Content-Type": "application/json"}, json=valid)),
        ("invalid_envelope", _response(_envelope(_public(_source()), source_id="wrong.source"))),
        ("invalid_envelope", _response(_envelope(_public(_source()), as_of="2026-08-05"))),
        ("invalid_envelope", _response(_envelope(_public(_source()), generated_at="2026-08-05T01:02:04+00:00"))),
    )
    for expected, response_or_error in cases:
        def handler(_request: httpx.Request) -> httpx.Response:
            if isinstance(response_or_error, Exception):
                raise response_or_error
            return response_or_error

        result = _read_api.load_continuation_validation(
            transport=httpx.MockTransport(handler)
        )
        if result != _read_api.ContinuationValidationApiFailure(expected):
            raise AssertionError((expected, result))

    for reason in sorted(_components.ARTIFACT_REASON_CODES):
        unavailable = _read_api.load_continuation_validation(
            transport=httpx.MockTransport(
                lambda _request, reason=reason: _response(
                    _envelope(None, available=False, reason=reason, generated_at=None)
                )
            )
        )
        if unavailable != _read_api.ContinuationValidationApiUnavailable(reason):
            raise AssertionError(unavailable)

    with patch(
        "ui._read_api._request_continuation_validation",
        new=AsyncMock(side_effect=[_read_api.ContinuationValidationApiFailure("transport_error"), _read_api.ContinuationValidationApiAvailable(ContinuationValidationData.model_validate(_public(_source()), strict=True))]),
    ):
        first = asyncio.run(_read_api._request_continuation_validation_with_deadline(None))
        second = asyncio.run(_read_api._request_continuation_validation_with_deadline(None))
    if not isinstance(first, _read_api.ContinuationValidationApiFailure) or not isinstance(second, _read_api.ContinuationValidationApiAvailable):
        raise AssertionError((first, second))


def _app_text(app: AppTest) -> str:
    return "\n".join(
        str(element.value)
        for collection in (app.caption, app.warning, app.info, app.error, app.success, app.markdown)
        for element in collection
    )


def test_renderer_uses_one_typed_result_and_safe_states() -> None:
    data = ContinuationValidationData.model_validate(_public(_source()), strict=True)
    with patch(
        "ui.continuation_validation._read_api.load_continuation_validation",
        return_value=_read_api.ContinuationValidationApiAvailable(data),
    ) as loader:
        app = AppTest.from_string(
            "from ui.continuation_validation import render\nrender()\n",
            default_timeout=10,
        ).run()
    if app.exception or loader.call_count != 1:
        raise AssertionError((app.exception, loader.call_count))
    text = _app_text(app)
    for expected in ("累積中", "最近更新", "Strong", "Normal", "Failed"):
        if expected not in text:
            raise AssertionError((expected, text))
    if len(app.dataframe) != 1:
        raise AssertionError(app.dataframe)

    blocked = ContinuationValidationData.model_validate(
        _public(_source("blocked")), strict=True
    )
    outcomes: tuple[object, ...] = (
        _read_api.ContinuationValidationApiAvailable(blocked),
        *(
            _read_api.ContinuationValidationApiUnavailable(reason)
            for reason in sorted(_components.ARTIFACT_REASON_CODES)
        ),
        *(
            _read_api.ContinuationValidationApiFailure(reason)
            for reason in sorted(_components.CLIENT_FAILURE_REASON_CODES)
        ),
    )
    for outcome in outcomes:
        with patch(
            "ui.continuation_validation._read_api.load_continuation_validation",
            return_value=outcome,
        ):
            app = AppTest.from_string(
                "from ui.continuation_validation import render\nrender()\n",
                default_timeout=10,
            ).run()
        if app.exception:
            raise AssertionError((outcome, app.exception))
        text = _app_text(app)
        if "/private/" in text or "daily bars are missing" in text:
            raise AssertionError(text)


def test_renderer_has_no_local_fallback_and_sources_are_python310_compatible() -> None:
    paths = (
        ROOT / "api/models.py",
        ROOT / "api/artifacts.py",
        ROOT / "api/main.py",
        ROOT / "ui/_read_api.py",
        ROOT / "ui/continuation_validation.py",
    )
    for path in paths:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 10))
    source = (ROOT / "ui/continuation_validation.py").read_text(encoding="utf-8")
    tree = ast.parse(source, feature_version=(3, 10))
    render = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "render"
    )
    render_source = ast.get_source_segment(source, render) or ""
    if render_source.count("load_continuation_validation()") != 1:
        raise AssertionError(render_source)
    for retired in ("_shared", "REPORT", "Path(", "json.loads", "continuation_strength.json"):
        if retired in source:
            raise AssertionError(f"Continuation renderer retained local read: {retired}")

    value = _read_api.ContinuationValidationApiFailure("transport_error")
    try:
        value.reason = "http_status"  # type: ignore[misc]
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("Continuation client outcome is mutable")


def main() -> None:
    tests = (
        test_source_families_projection_and_row_invariants_are_strict,
        test_route_openapi_and_fixed_client_are_strict_and_bounded,
        test_client_failure_matrix_metadata_and_recovery_are_exact,
        test_renderer_uses_one_typed_result_and_safe_states,
        test_renderer_has_no_local_fallback_and_sources_are_python310_compatible,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
