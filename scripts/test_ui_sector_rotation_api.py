#!/usr/bin/env python3
"""Focused contracts for Phase 5I-5K Sector Rotation API-only slices."""

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
import yaml
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.artifacts import (  # noqa: E402
    ARTIFACTS,
    ArtifactSpec,
    ResolvedArtifactPath,
    read_artifact,
    resolve_latest_sector_rotation,
)
from api.main import create_app  # noqa: E402
from api.models import (  # noqa: E402
    ArtifactAvailable,
    ArtifactUnavailable,
    SectorRotationData,
)
from ui import _components, _read_api, sector_rotation, stock_checkup  # noqa: E402


SOURCE_ID = "market-context.sector-rotation.latest"
ROUTE = "/api/v1/market-context/sector-rotation/latest"
URL = f"http://127.0.0.1:8000{ROUTE}"
ARCHIVE = ROOT / "reports/sector_rotation_snapshots/2026-07-01.json"
ROOT_FIELDS = {"as_of", "benchmark", "sectors"}
ROW_FIELDS = {
    "etf",
    "name_zh",
    "group",
    "theme",
    "quadrant",
    "quadrant_zh",
    "rs_ratio",
    "rs_momentum",
    "heat_score",
    "ret_5d",
    "ret_20d",
    "ret_60d",
    "excess_20d",
    "pct_vs_ma50",
    "pct_vs_ma200",
    "pct_from_52w_high",
    "rvol",
}


def _source() -> dict[str, object]:
    payload = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(payload)
    return payload


def _public(source: dict[str, object] | None = None) -> dict[str, object]:
    payload = source or _source()
    rows = payload["sectors"]
    if not isinstance(rows, list):
        raise AssertionError(rows)
    return {
        "as_of": payload["as_of"],
        "benchmark": payload["benchmark"],
        "sectors": [
            {field: row[field] for field in ROW_FIELDS}
            for row in rows
            if isinstance(row, dict)
        ],
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


def _response(payload: object) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )


def _envelope(
    data: dict[str, object] | None,
    *,
    source_id: str = SOURCE_ID,
    available: bool = True,
    reason: str = "ok",
    as_of: str | None = "2026-07-01",
    generated_at: str | None = "2026-07-02T09:11:44.023777Z",
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


def _client(registry: dict[str, ArtifactSpec]) -> TestClient:
    target = create_app(registry)

    async def with_loopback(scope, receive, send):
        if scope["type"] == "http":
            scope = {**scope, "client": ("127.0.0.1", 50_000)}
        await target(scope, receive, send)

    return TestClient(with_loopback, base_url="http://127.0.0.1")


def test_real_archive_projects_exact_public_board_and_latest_is_fail_closed() -> None:
    result = read_artifact(ARTIFACTS[SOURCE_ID])
    if not isinstance(result, ArtifactAvailable):
        raise AssertionError(result)
    if set(result.data) != ROOT_FIELDS:
        raise AssertionError(result.data)
    if any(set(row) != ROW_FIELDS for row in result.data["sectors"]):
        raise AssertionError(result.data["sectors"])
    serialized = json.dumps(result.data, ensure_ascii=False)
    for private in ("macro", "leaders", "improving", "status", "read"):
        if f'"{private}"' in serialized:
            raise AssertionError((private, result.data))
    SectorRotationData.model_validate(result.data, strict=True)

    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp)
        older = _source()
        older["as_of"] = "2026-06-30"
        older["generated_at"] = "2026-07-01T01:02:03+00:00"
        _write(archive / "2026-06-30.json", older)
        latest = deepcopy(_source())
        latest["status"] = "ready"
        latest["read"] = {
            "headline": "輪動摘要",
            "confidence": "medium",
            "hot_now": [{"etf": "KRE", "name": "區域銀行", "why": "相對強度居前"}],
            "rotating_into": [],
            "next_rotation_thesis": "觀察輪動延續。",
            "cycle_read": "中性",
            "caveats": ["資料為日頻快照。"],
        }
        latest_path = _write(archive / "2026-07-01.json", latest)
        _write(archive / "latest.json", {"private": True})
        resolved = resolve_latest_sector_rotation(archive)
        if not isinstance(resolved, ResolvedArtifactPath) or resolved.path != latest_path:
            raise AssertionError(resolved)
        selected = read_artifact(replace(ARTIFACTS[SOURCE_ID], resolver=lambda: resolved))
        if not isinstance(selected, ArtifactAvailable):
            raise AssertionError(selected)
        latest["sectors"] = "invalid"
        _write(latest_path, latest)
        failed = read_artifact(
            replace(
                ARTIFACTS[SOURCE_ID],
                resolver=lambda: resolve_latest_sector_rotation(archive),
            )
        )
        if not isinstance(failed, ArtifactUnavailable) or failed.reason != "invalid_shape":
            raise AssertionError(failed)


def test_complete_source_variants_and_public_invariants_are_strict() -> None:
    source = _source()
    invalid_sources: list[dict[str, object]] = []
    invalid_sources.append({**source, "private": True})
    ready_without_read = deepcopy(source)
    ready_without_read["status"] = "ready"
    invalid_sources.append(ready_without_read)
    verified_with_read = deepcopy(source)
    verified_with_read["read"] = {}
    invalid_sources.append(verified_with_read)
    wrong_macro = deepcopy(source)
    wrong_macro["macro"]["secret"] = True  # type: ignore[index]
    invalid_sources.append(wrong_macro)
    duplicate = deepcopy(source)
    duplicate["sectors"][1]["etf"] = duplicate["sectors"][0]["etf"]  # type: ignore[index]
    invalid_sources.append(duplicate)
    wrong_label = deepcopy(source)
    wrong_label["sectors"][0]["quadrant_zh"] = "落後"  # type: ignore[index]
    invalid_sources.append(wrong_label)
    wrong_order = deepcopy(source)
    wrong_order["sectors"][1]["heat_score"] = 101.0  # type: ignore[index]
    invalid_sources.append(wrong_order)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "source.json"
        for invalid in invalid_sources:
            outcome = read_artifact(_spec(_write(path, invalid)))
            if not isinstance(outcome, ArtifactUnavailable) or outcome.reason != "invalid_shape":
                raise AssertionError(outcome)

    public = _public()
    public["sectors"][0]["tail"] = []  # type: ignore[index]
    try:
        SectorRotationData.model_validate(public, strict=True)
    except ValueError:
        pass
    else:
        raise AssertionError("public DTO accepted a non-public tail")


def test_fixed_route_openapi_and_client_preserve_provenance_and_cap() -> None:
    registry = dict(ARTIFACTS)
    registry[SOURCE_ID] = _spec(ARCHIVE)
    with _client(registry) as client:
        response = client.get(ROUTE)
        generated = client.get("/openapi.json").json()
    if response.status_code != 200 or response.headers.get("cache-control") != "no-store":
        raise AssertionError((response.status_code, response.headers))
    payload = response.json()
    if payload["meta"] != {
        "sourceId": SOURCE_ID,
        "asOf": "2026-07-01",
        "generatedAt": "2026-07-02T09:11:44.023777Z",
    }:
        raise AssertionError(payload)

    public = SectorRotationData.model_validate(payload["data"], strict=True)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return _response(_envelope(public.model_dump(mode="json")))

    outcome = _read_api.load_sector_rotation(transport=httpx.MockTransport(handler))
    if not isinstance(outcome, _read_api.SectorRotationApiAvailable):
        raise AssertionError(outcome)
    if outcome.snapshot != public or seen != [URL]:
        raise AssertionError((outcome, seen))

    unavailable = _read_api.load_sector_rotation(
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
    if unavailable != _read_api.SectorRotationApiUnavailable("missing"):
        raise AssertionError(unavailable)
    for invalid in (
        _envelope(public.model_dump(mode="json"), source_id="private.source"),
        _envelope(public.model_dump(mode="json"), as_of="2026-06-30"),
        _envelope(public.model_dump(mode="json"), generated_at=None),
    ):
        result = _read_api.load_sector_rotation(
            transport=httpx.MockTransport(
                lambda _request, invalid=invalid: _response(invalid)
            )
        )
        if result != _read_api.SectorRotationApiFailure("invalid_envelope"):
            raise AssertionError(result)
    oversized = httpx.Response(
        200,
        headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        content=b"x" * (_read_api._SECTOR_ROTATION_MAX_RESPONSE_BYTES + 1),
    )
    result = _read_api.load_sector_rotation(
        transport=httpx.MockTransport(lambda _request: oversized)
    )
    if result != _read_api.SectorRotationApiFailure("response_too_large"):
        raise AssertionError(result)

    static = yaml.safe_load(
        (ROOT / "docs/api/quant-radar-v1.openapi.yaml").read_text(encoding="utf-8")
    )
    for label, document in (("generated", generated), ("static", static)):
        if document["info"]["version"] != "1.23.0-draft":
            raise AssertionError((label, document["info"]))
        operation = document["paths"][ROUTE]["get"]
        if operation.get("operationId") != "getLatestSectorRotation":
            raise AssertionError((label, operation))
        data_schema = document["components"]["schemas"]["SectorRotationData"]
        row_schema = document["components"]["schemas"]["SectorRotationSector"]
        if data_schema.get("additionalProperties") is not False or set(data_schema["properties"]) != ROOT_FIELDS:
            raise AssertionError((label, data_schema))
        if row_schema.get("additionalProperties") is not False or set(row_schema["properties"]) != ROW_FIELDS:
            raise AssertionError((label, row_schema))


def test_page_states_are_api_only_and_stock_reuses_one_injected_board() -> None:
    public = SectorRotationData.model_validate(_public(), strict=True)
    outcomes: tuple[_read_api.SectorRotationApiResult, ...] = (
        _read_api.SectorRotationApiAvailable(public),
        *(
            _read_api.SectorRotationApiUnavailable(reason)
            for reason in sorted(_components.ARTIFACT_REASON_CODES)
        ),
        *(
            _read_api.SectorRotationApiFailure(reason)
            for reason in sorted(_components.CLIENT_FAILURE_REASON_CODES)
        ),
    )
    for outcome in outcomes:
        with patch(
            "ui.sector_rotation._read_api.load_sector_rotation",
            return_value=outcome,
        ) as standalone_loader:
            standalone_state = sector_rotation._board_state()
        with patch(
            "ui.stock_checkup._read_api.load_sector_rotation",
            return_value=outcome,
        ) as stock_loader:
            stock_state = stock_checkup._sector_board_state()
        expected = (
            "api_available"
            if isinstance(outcome, _read_api.SectorRotationApiAvailable)
            else "api_unavailable"
            if isinstance(outcome, _read_api.SectorRotationApiUnavailable)
            else "api_failure"
        )
        if standalone_loader.call_count != 1 or stock_loader.call_count != 1:
            raise AssertionError((standalone_loader.call_count, stock_loader.call_count))
        if standalone_state.status != expected or stock_state.status != expected:
            raise AssertionError((outcome, standalone_state, stock_state))

    state = stock_checkup._sector_board_state_from_result(
        _read_api.SectorRotationApiAvailable(public)
    )
    with patch("ui.stock_checkup._shared.ticker_sector_etf", return_value="KRE") as provider:
        first = stock_checkup._sector_lookup("JPM", state)
        second = stock_checkup._sector_lookup("JPM", state)
    if first[1] is None or second[1] is None or provider.call_count != 2:
        raise AssertionError((first, second, provider.call_count))

    shared_source = (ROOT / "ui/_shared.py").read_text(encoding="utf-8")
    standalone_source = (ROOT / "ui/sector_rotation.py").read_text(encoding="utf-8")
    stock_source = (ROOT / "ui/stock_checkup.py").read_text(encoding="utf-8")
    if "def load_sector_flow(" in shared_source or "load_sector_flow" in standalone_source + stock_source:
        raise AssertionError("local/live Sector Rotation board fallback remains")
    stock_functions = {
        node.name: ast.get_source_segment(stock_source, node) or ""
        for node in ast.parse(stock_source).body
        if isinstance(node, ast.FunctionDef)
    }
    if stock_functions["_render_single"].count("_sector_board_state()") != 1:
        raise AssertionError("single-ticker render must resolve one board state")
    if "_sector_board_state()" in stock_functions["_render_batch"]:
        raise AssertionError("batch mode must not read the Sector Rotation API")


def test_outcomes_are_immutable_and_sources_are_python310_compatible() -> None:
    for outcome in (
        _read_api.SectorRotationApiUnavailable("missing"),
        _read_api.SectorRotationApiFailure("transport_error"),
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
        "ui/sector_rotation.py",
        "ui/stock_checkup.py",
        "scripts/test_ui_sector_rotation_api.py",
    ):
        path = ROOT / relative
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 10))


def main() -> None:
    tests = (
        test_real_archive_projects_exact_public_board_and_latest_is_fail_closed,
        test_complete_source_variants_and_public_invariants_are_strict,
        test_fixed_route_openapi_and_client_preserve_provenance_and_cap,
        test_page_states_are_api_only_and_stock_reuses_one_injected_board,
        test_outcomes_are_immutable_and_sources_are_python310_compatible,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
