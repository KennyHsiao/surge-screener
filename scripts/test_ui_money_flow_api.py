#!/usr/bin/env python3
"""Focused contracts for Phase 4W/4Y Money Flow read separation."""

from __future__ import annotations

import ast
import json
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import httpx
import yaml
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.artifacts import ARTIFACTS, ArtifactSpec, ResolvedArtifactPath, read_artifact  # noqa: E402
from api.models import ArtifactAvailable, ArtifactUnavailable, MoneyFlowData  # noqa: E402
from api.main import create_app  # noqa: E402
from ui import _components, _read_api, options_cockpit  # noqa: E402


SOURCE_ID = "market-context.money-flow.latest"
ROUTE = "/api/v1/market-context/money-flow/latest"
URL = f"http://127.0.0.1:8000{ROUTE}"
ROOT_FIELDS = {
    "as_of_date",
    "generated_at",
    "source",
    "publishable",
    "coverage",
    "rows",
}
COVERAGE_FIELDS = {
    "requested",
    "resolved",
    "unavailable",
    "coverage_ratio",
    "min_coverage",
}
ROW_FIELDS = {
    "ticker",
    "date",
    "main_net",
    "main_pct",
    "small_net",
    "source",
}


def _source(**overrides: object) -> dict[str, object]:
    rows = [
        {
            "ticker": "NVDA",
            "secid": "105.NVDA",
            "date": "2026-08-01",
            "close": 180.0,
            "change_pct": 2.5,
            "main_net": 2_000_000.0,
            "main_pct": 4.2,
            "super_big_net": 1_000_000.0,
            "big_net": 1_000_000.0,
            "mid_net": -500_000.0,
            "small_net": -1_500_000.0,
            "source": "eastmoney_push2his",
            "raw_row": {"private": "provider payload"},
        },
        {
            "ticker": "NVDA",
            "secid": "105.NVDA",
            "date": "2026-07-31",
            "close": 176.0,
            "change_pct": 1.0,
            "main_net": 500_000.0,
            "main_pct": 1.2,
            "super_big_net": 300_000.0,
            "big_net": 200_000.0,
            "mid_net": -100_000.0,
            "small_net": -400_000.0,
            "source": "eastmoney_push2his",
            "raw_row": {"private": "older provider payload"},
        },
    ]
    payload: dict[str, object] = {
        "as_of_date": "2026-08-01",
        "generated_at": "2026-08-01T02:03:04.123456+00:00",
        "source": "eastmoney_push2his",
        "publishable": True,
        "coverage": {
            "requested": 1,
            "resolved": 1,
            "unavailable": 0,
            "coverage_ratio": 1.0,
            "min_coverage": 0.7,
        },
        "rows": rows,
    }
    payload.update(overrides)
    return payload


def _public() -> dict[str, object]:
    source = _source()
    rows = source["rows"]
    return {
        "as_of_date": source["as_of_date"],
        "generated_at": source["generated_at"],
        "source": source["source"],
        "publishable": source["publishable"],
        "coverage": source["coverage"],
        "rows": [
            {field: row[field] for field in ROW_FIELDS}
            for row in rows  # type: ignore[union-attr]
        ],
    }


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _spec(path: Path) -> ArtifactSpec:
    return replace(
        ARTIFACTS[SOURCE_ID],
        resolver=lambda: ResolvedArtifactPath(path),
    )


def _response(payload: object) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        content=json.dumps(payload).encode("utf-8"),
    )


def _envelope(
    data: dict[str, object] | None,
    *,
    source_id: str = SOURCE_ID,
    available: bool = True,
    reason: str = "ok",
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


def test_registry_projects_exact_bounded_contract_and_fails_soft() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "latest.json"
        result = read_artifact(_spec(_write(path, _source())))
        if not isinstance(result, ArtifactAvailable):
            raise AssertionError(result)
        if set(result.data) != ROOT_FIELDS:
            raise AssertionError(result.data)
        if set(result.data["coverage"]) != COVERAGE_FIELDS:
            raise AssertionError(result.data["coverage"])
        if any(set(row) != ROW_FIELDS for row in result.data["rows"]):
            raise AssertionError(result.data["rows"])
        serialized = json.dumps(result.data)
        for private in (
            "secid",
            "raw_row",
            "provider payload",
            "super_big_net",
            "big_net",
            "mid_net",
            "close",
            "change_pct",
        ):
            if private in serialized:
                raise AssertionError((private, result.data))

        invalid_sources = [
            _source(extra="secret"),
            _source(source="other"),
            _source(publishable=False),
        ]
        bad_coverage = _source()
        bad_coverage["coverage"]["coverage_ratio"] = 0.5  # type: ignore[index]
        invalid_sources.append(bad_coverage)
        bad_row = _source()
        bad_row["rows"][0]["private"] = True  # type: ignore[index]
        invalid_sources.append(bad_row)
        duplicate = _source()
        duplicate["rows"].append(dict(duplicate["rows"][0]))  # type: ignore[union-attr,index]
        invalid_sources.append(duplicate)
        wrong_resolved = _source()
        wrong_resolved["coverage"] = {
            "requested": 2,
            "resolved": 2,
            "unavailable": 0,
            "coverage_ratio": 1.0,
            "min_coverage": 0.7,
        }
        invalid_sources.append(wrong_resolved)
        for invalid in invalid_sources:
            outcome = read_artifact(_spec(_write(path, invalid)))
            if not isinstance(outcome, ArtifactUnavailable) or outcome.reason != "invalid_shape":
                raise AssertionError((invalid, outcome))

        missing = read_artifact(_spec(Path(tmp) / "missing.json"))
        if not isinstance(missing, ArtifactUnavailable) or missing.reason != "missing":
            raise AssertionError(missing)


def test_client_validates_fixed_url_provenance_metadata_and_cap() -> None:
    public = MoneyFlowData.model_validate(_public(), strict=True)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return _response(_envelope(public.model_dump(mode="json")))

    result = _read_api.load_money_flow(transport=httpx.MockTransport(handler))
    if not isinstance(result, _read_api.MoneyFlowApiAvailable):
        raise AssertionError(result)
    if result.snapshot != public or seen != [URL]:
        raise AssertionError((result, seen))

    unavailable = _read_api.load_money_flow(
        transport=httpx.MockTransport(
            lambda _request: _response(
                _envelope(
                    None,
                    available=False,
                    reason="missing",
                    as_of=None,
                    generated_at=None,
                )
            )
        )
    )
    if unavailable != _read_api.MoneyFlowApiUnavailable("missing"):
        raise AssertionError(unavailable)

    for payload in (
        _envelope(public.model_dump(mode="json"), source_id="market-context.money-flow.other"),
        _envelope(public.model_dump(mode="json"), as_of="2026-07-31"),
        _envelope(public.model_dump(mode="json"), generated_at="2026-08-01T02:03:05Z"),
    ):
        outcome = _read_api.load_money_flow(
            transport=httpx.MockTransport(
                lambda _request, payload=payload: _response(payload)
            )
        )
        if outcome != _read_api.MoneyFlowApiFailure("invalid_envelope"):
            raise AssertionError(outcome)

    oversized = httpx.Response(
        200,
        headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        content=b"x" * (_read_api._MONEY_FLOW_MAX_RESPONSE_BYTES + 1),
    )
    outcome = _read_api.load_money_flow(
        transport=httpx.MockTransport(lambda _request: oversized)
    )
    if outcome != _read_api.MoneyFlowApiFailure("response_too_large"):
        raise AssertionError(outcome)


def test_http_route_and_openapi_are_additive_strict_and_fail_soft() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _write(Path(tmp) / "latest.json", _source())
        registry = dict(ARTIFACTS)
        registry[SOURCE_ID] = _spec(path)
        app = create_app(registry)

        async def with_loopback(scope, receive, send):
            if scope["type"] == "http":
                scope = {**scope, "client": ("127.0.0.1", 50_000)}
            await app(scope, receive, send)

        with TestClient(with_loopback, base_url="http://127.0.0.1") as client:
            available = client.get(ROUTE)
            generated = client.get("/openapi.json").json()
            path.unlink()
            missing = client.get(ROUTE)
    if available.status_code != 200 or available.headers.get("cache-control") != "no-store":
        raise AssertionError((available.status_code, available.headers))
    payload = available.json()
    if not payload["available"] or set(payload["data"]) != ROOT_FIELDS:
        raise AssertionError(payload)
    if payload["meta"] != {
        "sourceId": SOURCE_ID,
        "asOf": "2026-08-01",
        "generatedAt": "2026-08-01T02:03:04.123456Z",
    }:
        raise AssertionError(payload["meta"])
    if missing.json() != {
        "available": False,
        "reason": "missing",
        "data": None,
        "meta": {"sourceId": SOURCE_ID, "asOf": None, "generatedAt": None},
    }:
        raise AssertionError(missing.json())

    static = yaml.safe_load(
        (ROOT / "docs" / "api" / "quant-radar-v1.openapi.yaml").read_text(
            encoding="utf-8"
        )
    )
    if generated["info"]["version"] != "1.23.0-draft" or static["info"][
        "version"
    ] != "1.23.0-draft":
        raise AssertionError((generated["info"], static["info"]))
    operation = static["paths"][ROUTE]["get"]
    if (
        operation.get("operationId") != "getLatestMoneyFlow"
        or operation.get("tags") != ["Market Context"]
        or operation.get("parameters") not in (None, [])
        or operation["responses"] != {
            "200": {"$ref": "#/components/responses/MoneyFlowResponse"},
            "500": {"$ref": "#/components/responses/InternalProblem"},
        }
    ):
        raise AssertionError(operation)
    for label, document in (("generated", generated), ("static", static)):
        schemas = document["components"]["schemas"]
        data = schemas["MoneyFlowData"]
        coverage = schemas["MoneyFlowCoverage"]
        row = schemas["MoneyFlowRow"]
        if data.get("additionalProperties") is not False or set(data["properties"]) != ROOT_FIELDS:
            raise AssertionError((label, data))
        if data["properties"]["rows"].get("maxItems") != 50_000:
            raise AssertionError((label, data["properties"]["rows"]))
        if coverage.get("additionalProperties") is not False or set(coverage["properties"]) != COVERAGE_FIELDS:
            raise AssertionError((label, coverage))
        if row.get("additionalProperties") is not False or set(row["properties"]) != ROW_FIELDS:
            raise AssertionError((label, row))


def test_typed_state_distinguishes_all_outcomes_without_local_fallback() -> None:
    public = MoneyFlowData.model_validate(_public(), strict=True)
    outcomes: tuple[_read_api.MoneyFlowApiResult, ...] = (
        _read_api.MoneyFlowApiAvailable(public),
        *(
            _read_api.MoneyFlowApiUnavailable(reason)
            for reason in sorted(_components.ARTIFACT_REASON_CODES)
        ),
        *(
            _read_api.MoneyFlowApiFailure(reason)
            for reason in sorted(_components.CLIENT_FAILURE_REASON_CODES)
        ),
    )
    for outcome in outcomes:
        with patch(
            "ui.options_cockpit._read_api.load_money_flow",
            return_value=outcome,
        ) as loader:
            state = options_cockpit._load_money_flow_state()
            signal = options_cockpit._money_flow_signal_from_state("NVDA", state)
        if loader.call_count != 1:
            raise AssertionError((outcome, loader.call_count))
        if isinstance(outcome, _read_api.MoneyFlowApiAvailable):
            if state.status != "api_available" or signal["state"] != "positive":
                raise AssertionError((state, signal))
        elif isinstance(outcome, _read_api.MoneyFlowApiUnavailable):
            if state.status != "api_unavailable" or signal["label"] != "資金流資料不可用":
                raise AssertionError((state, signal))
        elif state.status != "api_failure" or signal["label"] != "資金流服務暫不可用":
            raise AssertionError((state, signal))
        if not isinstance(outcome, _read_api.MoneyFlowApiAvailable):
            if outcome.reason in json.dumps(signal, ensure_ascii=False):
                raise AssertionError((outcome, signal))


def test_future_and_stale_rows_keep_existing_fail_closed_semantics() -> None:
    future = _public()
    future["as_of_date"] = "2026-07-31"
    future["rows"] = [dict(future["rows"][0], date="2026-08-01")]  # type: ignore[index]
    future_state = options_cockpit.MoneyFlowReadState(
        "api_available",
        MoneyFlowData.model_validate(future, strict=True),
        None,
    )
    future_signal = options_cockpit._money_flow_signal_from_state("NVDA", future_state)
    if future_signal["label"] != "無個股資金流":
        raise AssertionError(future_signal)

    stale = _public()
    stale["as_of_date"] = "2026-08-05"
    stale["rows"] = [dict(stale["rows"][0], date="2026-08-01")]  # type: ignore[index]
    stale_state = options_cockpit.MoneyFlowReadState(
        "api_available",
        MoneyFlowData.model_validate(stale, strict=True),
        None,
    )
    stale_signal = options_cockpit._money_flow_signal_from_state("NVDA", stale_state)
    if stale_signal["label"] != "資金流過期":
        raise AssertionError(stale_signal)


def test_source_requires_one_api_state_per_entry_and_removes_local_reader() -> None:
    path = ROOT / "ui" / "options_cockpit.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    standalone = functions["render"]
    embedded = functions["render_for"]
    external = functions["_render_external_confirmation"]
    state_loader = functions["_load_money_flow_state"]
    if standalone.count("_load_money_flow_state()") != 1:
        raise AssertionError("standalone must load one Money Flow API state")
    if embedded.count("_load_money_flow_state()") != 1:
        raise AssertionError("embedded cockpit must load one Money Flow API state")
    if "_load_money_flow_artifact" in functions or "_load_money_flow_artifact" in source:
        raise AssertionError("Options Cockpit retained the local Money Flow reader")
    if "MoneyFlowReadState | None" in external or "money_flow_state is None" in external:
        raise AssertionError("external confirmation retained an implicit local/default state")
    if "_money_flow_signal_from_state" not in external:
        raise AssertionError("external confirmation does not require the typed API state")
    if "_load_money_flow_artifact" in state_loader:
        raise AssertionError("Money Flow API state retained a local fallback")


def main() -> None:
    tests = (
        test_registry_projects_exact_bounded_contract_and_fails_soft,
        test_client_validates_fixed_url_provenance_metadata_and_cap,
        test_http_route_and_openapi_are_additive_strict_and_fail_soft,
        test_typed_state_distinguishes_all_outcomes_without_local_fallback,
        test_future_and_stale_rows_keep_existing_fail_closed_semantics,
        test_source_requires_one_api_state_per_entry_and_removes_local_reader,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
