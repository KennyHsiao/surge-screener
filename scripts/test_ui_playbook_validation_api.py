#!/usr/bin/env python3
"""Focused contracts for the Phase 5Y-5Z Playbook Validation API slice."""

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
    PLAYBOOK_VALIDATION_SOURCE_ID,
    ArtifactPathUnavailable,
    ArtifactSpec,
    ResolvedArtifactPath,
    read_artifact,
)
from api.main import create_app  # noqa: E402
from api.models import (  # noqa: E402
    ArtifactAvailable,
    ArtifactUnavailable,
    PlaybookValidationData,
)
from ui import _components, _read_api, playbook_validation  # noqa: E402


SOURCE_ID = "reports.playbook-validation.latest"
ROUTE = "/api/v1/reports/playbook-validation/latest"
URL = f"http://127.0.0.1:8000{ROUTE}"
ROOT_FIELDS = {
    "generated_at",
    "status",
    "decision_count",
    "resolved",
    "min_resolved",
    "playbooks",
    "factors",
}
PLAYBOOK_ROW_FIELDS = {
    "playbook",
    "resolved",
    "mean_fwd_7d_return",
    "hit_rate_7d",
    "verdict",
}
FACTOR_ROW_FIELDS = {
    "factor_id",
    "resolved",
    "mean_fwd_7d_return",
    "hit_rate_7d",
    "verdict",
}


def _source(status: str = "accumulating") -> dict[str, object]:
    generated_at = "2026-08-05T01:02:03+00:00"
    if status == "blocked":
        return {
            "generated_at": generated_at,
            "status": "blocked",
            "reason": "decision source not found: /private/reports/playbook_decisions",
            "resolved": 0,
            "min_resolved": 100,
            "playbooks": [],
            "factors": [],
        }
    ready = status == "ready"
    resolved = 100 if ready else 5
    decision_count = 120 if ready else 12
    return {
        "generated_at": generated_at,
        "status": status,
        "resolved": resolved,
        "min_resolved": 100,
        "decision_count": decision_count,
        "outcome_count": decision_count,
        "playbooks": [
            {
                "playbook": "Momentum",
                "resolved": resolved,
                "mean_fwd_7d_return": 0.031,
                "hit_rate_7d": 0.6,
                "verdict": "validated" if ready else "exploratory",
            }
        ],
        "factors": [
            {
                "factor_id": "technical_breakout",
                "resolved": 80 if ready else 3,
                "mean_fwd_7d_return": 0.025,
                "hit_rate_7d": 0.625 if ready else 0.6667,
                "verdict": "exploratory",
            },
            {
                "factor_id": "volume_confirmation",
                "resolved": 0,
                "mean_fwd_7d_return": None,
                "hit_rate_7d": None,
                "verdict": "exploratory",
            },
        ],
    }


def _public(source: dict[str, object] | None = None) -> dict[str, object]:
    payload = source or _source()
    return {
        "generated_at": payload["generated_at"],
        "status": payload["status"],
        "decision_count": payload.get("decision_count", 0),
        "resolved": payload["resolved"],
        "min_resolved": payload["min_resolved"],
        "playbooks": payload["playbooks"],
        "factors": payload["factors"],
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


def test_source_families_projection_and_invariants_are_strict() -> None:
    if PLAYBOOK_VALIDATION_SOURCE_ID != SOURCE_ID:
        raise AssertionError(PLAYBOOK_VALIDATION_SOURCE_ID)
    spec = ARTIFACTS[SOURCE_ID]
    if spec.data_model is not PlaybookValidationData:
        raise AssertionError(spec.data_model)
    if spec.data_validator is None or spec.data_projector is None:
        raise AssertionError(spec)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "latest.json"
        for source in (_source("blocked"), _source(), _source("ready")):
            outcome = read_artifact(_spec(_write(path, source)))
            if not isinstance(outcome, ArtifactAvailable):
                raise AssertionError(outcome)
            if outcome.data != _public(source) or set(outcome.data) != ROOT_FIELDS:
                raise AssertionError(outcome.data)
            for row in outcome.data["playbooks"]:
                if set(row) != PLAYBOOK_ROW_FIELDS:
                    raise AssertionError(row)
            for row in outcome.data["factors"]:
                if set(row) != FACTOR_ROW_FIELDS:
                    raise AssertionError(row)
            serialized = json.dumps(outcome.data)
            for private in ("outcome_count", "decision source not found", "/private/"):
                if private in serialized:
                    raise AssertionError((private, serialized))

        source = _source()
        invalid_sources: list[dict[str, object]] = [{**source, "private": True}]
        missing_root = deepcopy(source)
        missing_root.pop("outcome_count")
        invalid_sources.append(missing_root)
        wrong_status = deepcopy(source)
        wrong_status["status"] = "ready"
        invalid_sources.append(wrong_status)
        wrong_decisions = deepcopy(source)
        wrong_decisions["decision_count"] = 4
        invalid_sources.append(wrong_decisions)
        wrong_outcomes = deepcopy(source)
        wrong_outcomes["outcome_count"] = 4
        invalid_sources.append(wrong_outcomes)
        wrong_sum = deepcopy(source)
        wrong_sum["playbooks"][0]["resolved"] = 4  # type: ignore[index]
        invalid_sources.append(wrong_sum)
        null_mismatch = deepcopy(source)
        null_mismatch["factors"][1]["mean_fwd_7d_return"] = 0.0  # type: ignore[index]
        invalid_sources.append(null_mismatch)
        wrong_verdict = deepcopy(source)
        wrong_verdict["playbooks"][0]["verdict"] = "validated"  # type: ignore[index]
        invalid_sources.append(wrong_verdict)
        bad_hit_rate = deepcopy(source)
        bad_hit_rate["factors"][0]["hit_rate_7d"] = 1.1  # type: ignore[index]
        invalid_sources.append(bad_hit_rate)
        oversized_mean = deepcopy(source)
        oversized_mean["factors"][0]["mean_fwd_7d_return"] = 1e19  # type: ignore[index]
        invalid_sources.append(oversized_mean)
        oversized_playbooks = deepcopy(source)
        oversized_playbooks["playbooks"] = [
            {
                "playbook": f"Playbook {index:03d}",
                "resolved": 0,
                "mean_fwd_7d_return": None,
                "hit_rate_7d": None,
                "verdict": "exploratory",
            }
            for index in range(201)
        ]
        invalid_sources.append(oversized_playbooks)
        oversized_factors = deepcopy(source)
        oversized_factors["factors"] = [
            {
                "factor_id": f"factor_{index:03d}",
                "resolved": 0,
                "mean_fwd_7d_return": None,
                "hit_rate_7d": None,
                "verdict": "exploratory",
            }
            for index in range(501)
        ]
        invalid_sources.append(oversized_factors)
        oversized_reason = _source("blocked")
        oversized_reason["reason"] = "x" * 4_001
        invalid_sources.append(oversized_reason)
        duplicate_factor = deepcopy(source)
        duplicate_factor["factors"].append(deepcopy(duplicate_factor["factors"][0]))  # type: ignore[union-attr,index]
        invalid_sources.append(duplicate_factor)
        unsorted_factor = deepcopy(source)
        unsorted_factor["factors"].reverse()  # type: ignore[union-attr]
        invalid_sources.append(unsorted_factor)
        bad_label = deepcopy(source)
        bad_label["playbooks"][0]["playbook"] = " Momentum"  # type: ignore[index]
        invalid_sources.append(bad_label)
        blocked_rows = _source("blocked")
        blocked_rows["playbooks"] = deepcopy(source["playbooks"])
        invalid_sources.append(blocked_rows)
        blocked_without_reason = _source("blocked")
        blocked_without_reason.pop("reason")
        invalid_sources.append(blocked_without_reason)
        for invalid in invalid_sources:
            outcome = read_artifact(_spec(_write(path, invalid)))
            if not isinstance(outcome, ArtifactUnavailable) or outcome.reason != "invalid_shape":
                raise AssertionError(outcome)

    public = _public()
    public["private"] = True
    try:
        PlaybookValidationData.model_validate(public, strict=True)
    except ValueError:
        pass
    else:
        raise AssertionError("public Playbook DTO accepted a private field")


def test_route_openapi_and_fixed_client_are_strict_and_bounded() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _write(Path(tmp) / "latest.json", _source())
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
    public = PlaybookValidationData.model_validate(payload["data"], strict=True)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return _response(_envelope(public.model_dump(mode="json")))

    outcome = _read_api.load_playbook_validation(transport=httpx.MockTransport(handler))
    if outcome != _read_api.PlaybookValidationApiAvailable(public) or seen != [URL]:
        raise AssertionError((outcome, seen))
    blocked = PlaybookValidationData.model_validate(_public(_source("blocked")), strict=True)
    blocked_outcome = _read_api.load_playbook_validation(
        transport=httpx.MockTransport(
            lambda _request: _response(_envelope(blocked.model_dump(mode="json")))
        )
    )
    if blocked_outcome != _read_api.PlaybookValidationApiAvailable(blocked):
        raise AssertionError(blocked_outcome)

    for invalid in (
        _envelope(public.model_dump(mode="json"), source_id="private.source"),
        _envelope(public.model_dump(mode="json"), as_of="2026-08-05"),
        _envelope(public.model_dump(mode="json"), generated_at=None),
        _envelope(
            public.model_dump(mode="json"),
            generated_at="2026-08-05T01:02:04+00:00",
        ),
    ):
        result = _read_api.load_playbook_validation(
            transport=httpx.MockTransport(
                lambda _request, invalid=invalid: _response(invalid)
            )
        )
        if result != _read_api.PlaybookValidationApiFailure("invalid_envelope"):
            raise AssertionError(result)

    oversized = httpx.Response(
        200,
        headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        content=b"x" * (_read_api._PLAYBOOK_VALIDATION_MAX_RESPONSE_BYTES + 1),
    )
    capped = _read_api.load_playbook_validation(
        transport=httpx.MockTransport(lambda _request: oversized)
    )
    if capped != _read_api.PlaybookValidationApiFailure("response_too_large"):
        raise AssertionError(capped)

    def transport_error(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private diagnostic")

    client_failures = (
        (httpx.MockTransport(transport_error), "transport_error"),
        (httpx.MockTransport(lambda _request: httpx.Response(503)), "http_status"),
        (
            httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    headers={"Content-Type": "text/plain", "Cache-Control": "no-store"},
                    content=b"{}",
                )
            ),
            "invalid_media_type",
        ),
        (
            httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    headers={"Content-Type": "application/json", "Cache-Control": "max-age=60"},
                    content=b"{}",
                )
            ),
            "invalid_cache_control",
        ),
        (httpx.MockTransport(lambda _request: _response({"private": True})), "invalid_envelope"),
    )
    for transport, reason in client_failures:
        result = _read_api.load_playbook_validation(transport=transport)
        if result != _read_api.PlaybookValidationApiFailure(reason):
            raise AssertionError((reason, result))

    attempts = 0

    def recovering_handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503)
        return _response(_envelope(public.model_dump(mode="json")))

    recovering_transport = httpx.MockTransport(recovering_handler)
    first = _read_api.load_playbook_validation(transport=recovering_transport)
    second = _read_api.load_playbook_validation(transport=recovering_transport)
    if first != _read_api.PlaybookValidationApiFailure("http_status"):
        raise AssertionError(first)
    if second != _read_api.PlaybookValidationApiAvailable(public) or attempts != 2:
        raise AssertionError((second, attempts))
    with patch(
        "ui._read_api._request_playbook_validation_with_deadline",
        new=AsyncMock(side_effect=asyncio.TimeoutError),
    ):
        deadline = _read_api.load_playbook_validation()
    if deadline != _read_api.PlaybookValidationApiFailure("deadline_exceeded"):
        raise AssertionError(deadline)

    for reason in sorted(_components.ARTIFACT_REASON_CODES):
        result = _read_api.load_playbook_validation(
            transport=httpx.MockTransport(
                lambda _request, reason=reason: _response(
                    _envelope(None, available=False, reason=reason)
                )
            )
        )
        if result != _read_api.PlaybookValidationApiUnavailable(reason):
            raise AssertionError(result)

    static = yaml.safe_load(
        (ROOT / "docs/api/quant-radar-v1.openapi.yaml").read_text(encoding="utf-8")
    )
    for label, document in (("generated", generated), ("static", static)):
        if document["info"]["version"] != "1.23.0-draft":
            raise AssertionError((label, document["info"]))
        operation = document["paths"][ROUTE]["get"]
        if operation.get("operationId") != "getLatestPlaybookValidation":
            raise AssertionError((label, operation))
        if operation.get("parameters"):
            raise AssertionError((label, operation["parameters"]))
        response_200 = operation["responses"]["200"]
        if "$ref" in response_200:
            response_200 = document["components"]["responses"][
                response_200["$ref"].rsplit("/", 1)[-1]
            ]
        examples = response_200["content"]["application/json"].get("examples", {})
        if set(examples) != {"available", "blocked", "unavailable"}:
            raise AssertionError((label, examples))
        data_schema = document["components"]["schemas"]["PlaybookValidationData"]
        if data_schema.get("additionalProperties") is not False or set(data_schema["properties"]) != ROOT_FIELDS:
            raise AssertionError((label, data_schema))
        for private in ("outcome_count", "reason", "decision_snapshots", "ticker_outcomes"):
            if private in data_schema["properties"]:
                raise AssertionError((label, private))


def test_expected_file_states_fail_soft_and_recover_without_cache() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "latest.json"
        spec = _spec(path)
        missing = read_artifact(spec)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{", encoding="utf-8")
        invalid_json = read_artifact(spec)
        _write(path, {"private": True})
        invalid_shape = read_artifact(spec)
        unreadable = read_artifact(
            replace(
                ARTIFACTS[SOURCE_ID],
                resolver=lambda: ArtifactPathUnavailable("unreadable"),
            )
        )
        _write(path, _source())
        recovered = read_artifact(spec)
    reasons = [missing, invalid_json, invalid_shape, unreadable]
    if [item.reason for item in reasons if isinstance(item, ArtifactUnavailable)] != [
        "missing",
        "invalid_json",
        "invalid_shape",
        "unreadable",
    ]:
        raise AssertionError(reasons)
    if not isinstance(recovered, ArtifactAvailable):
        raise AssertionError(recovered)


def _app_text(app: AppTest) -> str:
    return "\n".join(
        str(element.value)
        for collection in (app.caption, app.warning, app.info, app.error, app.success, app.markdown)
        for element in collection
    )


def test_renderer_uses_one_typed_result_and_safe_partial_states() -> None:
    wrapper = "from ui.playbook_validation import render\nrender()\n"
    available = _read_api.PlaybookValidationApiAvailable(
        PlaybookValidationData.model_validate(_public(), strict=True)
    )
    with patch(
        "ui.playbook_validation._read_api.load_playbook_validation",
        return_value=available,
    ) as loader:
        app = AppTest.from_string(wrapper, default_timeout=10).run()
    if app.exception or loader.call_count != 1:
        raise AssertionError((app.exception, loader.call_count))
    text = _app_text(app)
    for expected in ("累積中", "已解析 5/100 筆", "2026-08-05T01:02:03+00:00"):
        if expected not in text:
            raise AssertionError(text)
    metrics = {metric.label: metric.value for metric in app.metric}
    if metrics != {"Decision rows": "12", "Resolved": "5", "Min resolved": "100"}:
        raise AssertionError(metrics)
    if len(app.dataframe) != 2:
        raise AssertionError(app.dataframe)

    blocked = _read_api.PlaybookValidationApiAvailable(
        PlaybookValidationData.model_validate(_public(_source("blocked")), strict=True)
    )
    with patch(
        "ui.playbook_validation._read_api.load_playbook_validation",
        return_value=blocked,
    ):
        blocked_app = AppTest.from_string(wrapper, default_timeout=10).run()
    blocked_text = _app_text(blocked_app)
    if blocked_app.exception or "Playbook 驗證來源尚不可用" not in blocked_text:
        raise AssertionError((blocked_app.exception, blocked_text))
    if "/private/" in blocked_text or "decision source not found" in blocked_text:
        raise AssertionError(blocked_text)

    partials: tuple[_read_api.PlaybookValidationApiResult, ...] = (
        *(
            _read_api.PlaybookValidationApiUnavailable(reason)
            for reason in sorted(_components.ARTIFACT_REASON_CODES)
        ),
        *(
            _read_api.PlaybookValidationApiFailure(reason)
            for reason in sorted(_components.CLIENT_FAILURE_REASON_CODES)
        ),
    )
    for outcome in partials:
        with patch(
            "ui.playbook_validation._read_api.load_playbook_validation",
            return_value=outcome,
        ):
            partial = AppTest.from_string(wrapper, default_timeout=10).run()
        text = _app_text(partial)
        if partial.exception or "Playbook 驗證" not in text:
            raise AssertionError((outcome, partial.exception, text))
        if outcome.reason in text or "latest.json" in text:
            raise AssertionError((outcome, text))


def test_renderer_has_no_local_fallback_and_retro_lane_is_preserved() -> None:
    path = ROOT / "ui" / "playbook_validation.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    render = functions["render"]
    if render.count("load_playbook_validation()") != 1:
        raise AssertionError(render)
    for forbidden in ("REPORT", "_shared", "load_json", "latest.json"):
        if forbidden in source:
            raise AssertionError(f"Playbook renderer retained local state: {forbidden}")
    retro = (ROOT / "ui/retro_analysis.py").read_text(encoding="utf-8")
    if "playbook_validation.render()" not in retro or '"Playbook 驗證"' not in retro:
        raise AssertionError("Retro Analysis Playbook lane changed")


def test_outcomes_are_immutable_and_sources_are_python310_compatible() -> None:
    for outcome in (
        _read_api.PlaybookValidationApiUnavailable("missing"),
        _read_api.PlaybookValidationApiFailure("transport_error"),
    ):
        try:
            outcome.reason = "unreadable"  # type: ignore[misc]
        except FrozenInstanceError:
            pass
        else:
            raise AssertionError(outcome)
    for relative in (
        "api/models.py",
        "api/artifacts.py",
        "api/main.py",
        "ui/_read_api.py",
        "ui/playbook_validation.py",
        "scripts/test_ui_playbook_validation_api.py",
    ):
        path = ROOT / relative
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 10))


def main() -> None:
    tests = (
        test_source_families_projection_and_invariants_are_strict,
        test_route_openapi_and_fixed_client_are_strict_and_bounded,
        test_expected_file_states_fail_soft_and_recover_without_cache,
        test_renderer_uses_one_typed_result_and_safe_partial_states,
        test_renderer_has_no_local_fallback_and_retro_lane_is_preserved,
        test_outcomes_are_immutable_and_sources_are_python310_compatible,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
