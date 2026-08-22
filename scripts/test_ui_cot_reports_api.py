#!/usr/bin/env python3
"""Focused contracts for the Phase 6D-6F persisted COT report slices."""

from __future__ import annotations

import ast
import json
import sys
import tempfile
from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

import httpx
import yaml
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.artifacts import (  # noqa: E402
    ARTIFACTS,
    COT_CATALOG_SOURCE_ID,
    COT_DETAIL_SOURCE_ID,
    read_cot_catalog,
    read_cot_report,
)
from api.main import create_app  # noqa: E402
from api.models import (  # noqa: E402
    ArtifactAvailable,
    ArtifactUnavailable,
    CotCatalogData,
    CotReportData,
    ScheduleEntry,
)
from scripts.cot_report_store import promote_cot_reports  # noqa: E402
from ui import _components, _read_api, sys_schedules, us_cot  # noqa: E402


CATALOG_ROUTE = "/api/v1/reports/cot"
DETAIL_ROUTE = "/api/v1/reports/cot/{report_date}"
CATALOG_URL = f"http://127.0.0.1:8000{CATALOG_ROUTE}"
DETAIL_URL = "http://127.0.0.1:8000/api/v1/reports/cot/2026-06-12"


def _verified(report_date: str = "2026-06-12") -> dict[str, object]:
    return {
        "cot": {
            "as_of": "2026-06-09",
            "market": "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
            "open_interest": 2_203_164,
            "asset_manager": {
                "long": 1_205_065,
                "short": 220_979,
                "net": 984_086,
                "chg_long": 5_762,
                "chg_short": 3_535,
                "chg_net": 2_227,
            },
            "leveraged_funds": {
                "long": 168_247,
                "short": 619_833,
                "net": -451_586,
                "chg_long": 8_609,
                "chg_short": -40_537,
                "chg_net": 49_146,
            },
            "source": "CFTC publicreporting.cftc.gov (TFF futures-only, gpe5-46if)",
        },
        "price": {
            "symbol": "ES=F (continuous front-month, == TradingView ES1!)",
            "friday_date": report_date,
            "friday_open": 7_397.5,
            "friday_high": 7_461.75,
            "friday_low": 7_366.5,
            "friday_close": 7_435.0,
            "week_high": 7_461.75,
            "week_low": 7_232.25,
            "as_of_date": "2026-06-09",
            "as_of_close": 7_392.75,
            "cot_report_age_days": 5,
            "cot_stale_warning": False,
            "source": "Yahoo Finance via yfinance",
            "retrieved_at": "2026-06-14T12:09:20.318228+00:00",
        },
        "tuesday_vs_friday": {
            "as_of_tuesday_close": 7_392.75,
            "friday_close": 7_435.0,
            "delta_points": 42.25,
        },
    }


def _markdown() -> str:
    return """# COT weekly report

**COT as-of** 2026-06-09

## Section 1 — Positioning
Asset managers remain net long.

## Section 2 — Price test
Tuesday to Friday was positive.

## Section 3 — Strategy
Use bounded risk.

## Section 4 — Risks
Research only.
"""


def _write_pair(directory: Path, report_date: str = "2026-06-12") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{report_date}.verified.json").write_text(
        json.dumps(_verified(report_date), ensure_ascii=False),
        encoding="utf-8",
    )
    (directory / f"{report_date}.md").write_text(_markdown(), encoding="utf-8")


def _catalog_envelope(*dates: str) -> dict[str, object]:
    return {
        "available": True,
        "reason": "ok",
        "data": {"reports": [{"report_date": value} for value in dates]},
        "meta": {
            "sourceId": COT_CATALOG_SOURCE_ID,
            "asOf": dates[0] if dates else None,
            "generatedAt": None,
        },
    }


def _detail_data(report_date: str = "2026-06-12", markdown: str | None = None) -> dict[str, object]:
    return {
        "report_date": report_date,
        "markdown": _markdown() if markdown is None else markdown,
        "verified": _verified(report_date),
    }


def _detail_envelope(report_date: str = "2026-06-12", markdown: str | None = None) -> dict[str, object]:
    return {
        "available": True,
        "reason": "ok",
        "data": _detail_data(report_date, markdown),
        "meta": {
            "sourceId": COT_DETAIL_SOURCE_ID,
            "asOf": report_date,
            "generatedAt": "2026-06-14T12:09:20.318228+00:00",
        },
    }


def _response(payload: object, **headers: str) -> httpx.Response:
    return httpx.Response(
        200,
        headers={
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
            **headers,
        },
        content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )


def _client(directory: Path) -> TestClient:
    target = create_app(ARTIFACTS, cot_reports_directory=directory)

    async def with_loopback(scope, receive, send):
        if scope["type"] == "http":
            scope = {**scope, "client": ("127.0.0.1", 50_000)}
        await target(scope, receive, send)

    return TestClient(with_loopback, base_url="http://127.0.0.1")


def test_catalog_and_detail_sources_are_bounded_strict_and_private() -> None:
    if COT_CATALOG_SOURCE_ID != "reports.cot.catalog":
        raise AssertionError(COT_CATALOG_SOURCE_ID)
    if COT_DETAIL_SOURCE_ID != "reports.cot.detail":
        raise AssertionError(COT_DETAIL_SOURCE_ID)
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp) / "cot"
        _write_pair(directory, "2026-06-05")
        _write_pair(directory, "2026-06-12")
        (directory / "_last_error.txt").write_text("private provider error", encoding="utf-8")
        (directory / "README.md").write_text("private notes", encoding="utf-8")

        catalog = read_cot_catalog(directory)
        if not isinstance(catalog, ArtifactAvailable):
            raise AssertionError(catalog)
        if catalog.data != {
            "reports": [
                {"report_date": "2026-06-12"},
                {"report_date": "2026-06-05"},
            ]
        }:
            raise AssertionError(catalog.data)
        if "private" in json.dumps(catalog.data):
            raise AssertionError(catalog.data)
        CotCatalogData.model_validate(catalog.data, strict=True)

        detail = read_cot_report("2026-06-12", directory)
        if not isinstance(detail, ArtifactAvailable):
            raise AssertionError(detail)
        if detail.data != _detail_data():
            raise AssertionError(detail.data)
        CotReportData.model_validate(detail.data, strict=True)
        serialized = json.dumps(detail.data)
        for private in ("_last_error", str(directory), "private provider error"):
            if private in serialized:
                raise AssertionError((private, serialized))

        invalid_payloads: list[dict[str, object]] = []
        extra = _verified()
        extra["secret"] = True
        invalid_payloads.append(extra)
        bad_position = deepcopy(_verified())
        bad_position["cot"]["asset_manager"]["net"] = 1  # type: ignore[index]
        invalid_payloads.append(bad_position)
        bad_delta = deepcopy(_verified())
        bad_delta["tuesday_vs_friday"]["delta_points"] = 1  # type: ignore[index]
        invalid_payloads.append(bad_delta)
        bad_date = deepcopy(_verified())
        bad_date["price"]["friday_date"] = "2026-06-11"  # type: ignore[index]
        invalid_payloads.append(bad_date)
        bad_range = deepcopy(_verified())
        bad_range["price"]["friday_high"] = 1  # type: ignore[index]
        invalid_payloads.append(bad_range)
        bad_stale = deepcopy(_verified())
        bad_stale["price"]["cot_stale_warning"] = True  # type: ignore[index]
        invalid_payloads.append(bad_stale)
        bad_tuesday_friday = deepcopy(_verified())
        bad_tuesday_friday["cot"]["as_of"] = "2026-06-08"  # type: ignore[index]
        bad_tuesday_friday["price"]["as_of_date"] = "2026-06-08"  # type: ignore[index]
        bad_tuesday_friday["price"]["cot_report_age_days"] = 6  # type: ignore[index]
        invalid_payloads.append(bad_tuesday_friday)
        bad_age = deepcopy(_verified())
        bad_age["price"]["cot_report_age_days"] = 4  # type: ignore[index]
        invalid_payloads.append(bad_age)
        for payload in invalid_payloads:
            (directory / "2026-06-12.verified.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            outcome = read_cot_report("2026-06-12", directory)
            if not isinstance(outcome, ArtifactUnavailable) or outcome.reason != "invalid_shape":
                raise AssertionError(outcome)


def test_missing_invalid_partial_oversized_and_recovery_states_are_fail_soft() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp) / "cot"
        missing_catalog = read_cot_catalog(directory)
        if not isinstance(missing_catalog, ArtifactUnavailable) or missing_catalog.reason != "missing":
            raise AssertionError(missing_catalog)
        directory.mkdir()
        empty = read_cot_catalog(directory)
        if not isinstance(empty, ArtifactAvailable) or empty.data != {"reports": []}:
            raise AssertionError(empty)
        (directory / "2026-02-30.md").write_text("bad date", encoding="utf-8")
        invalid_catalog = read_cot_catalog(directory)
        if not isinstance(invalid_catalog, ArtifactUnavailable) or invalid_catalog.reason != "invalid_shape":
            raise AssertionError(invalid_catalog)
        (directory / "2026-02-30.md").unlink()

        (directory / "2026-06-12.md").write_text(_markdown(), encoding="utf-8")
        missing_sidecar = read_cot_report("2026-06-12", directory)
        if not isinstance(missing_sidecar, ArtifactUnavailable) or missing_sidecar.reason != "missing":
            raise AssertionError(missing_sidecar)
        (directory / "2026-06-12.verified.json").write_text("{", encoding="utf-8")
        malformed = read_cot_report("2026-06-12", directory)
        if not isinstance(malformed, ArtifactUnavailable) or malformed.reason != "invalid_json":
            raise AssertionError(malformed)
        (directory / "2026-06-12.verified.json").write_text(" " * (64 * 1024 + 1), encoding="utf-8")
        oversized_json = read_cot_report("2026-06-12", directory)
        if not isinstance(oversized_json, ArtifactUnavailable) or oversized_json.reason != "invalid_shape":
            raise AssertionError(oversized_json)
        _write_pair(directory)
        (directory / "2026-06-12.md").write_text("x" * (256 * 1024 + 1), encoding="utf-8")
        oversized_markdown = read_cot_report("2026-06-12", directory)
        if not isinstance(oversized_markdown, ArtifactUnavailable) or oversized_markdown.reason != "invalid_shape":
            raise AssertionError(oversized_markdown)
        _write_pair(directory)
        recovered = read_cot_report("2026-06-12", directory)
        if not isinstance(recovered, ArtifactAvailable):
            raise AssertionError(recovered)


def test_generation_symlink_tracks_atomic_current_without_file_symlinks() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "source"
        store = root / "store"
        app_link = root / "reports-cot"
        _write_pair(source, "2026-06-12")
        promote_cot_reports(source, store)
        app_link.symlink_to(store / "current", target_is_directory=True)

        catalog = read_cot_catalog(app_link)
        detail = read_cot_report("2026-06-12", app_link)
        if not isinstance(catalog, ArtifactAvailable) or not isinstance(detail, ArtifactAvailable):
            raise AssertionError((catalog, detail))

        _write_pair(source, "2026-06-19")
        verified_path = source / "2026-06-19.verified.json"
        verified = json.loads(verified_path.read_text(encoding="utf-8"))
        verified["cot"]["as_of"] = "2026-06-16"
        verified["price"]["as_of_date"] = "2026-06-16"
        verified["price"]["retrieved_at"] = "2026-06-21T12:09:20.318228+00:00"
        verified_path.write_text(json.dumps(verified), encoding="utf-8")
        promote_cot_reports(source, store)

        advanced = read_cot_catalog(app_link)
        if not isinstance(advanced, ArtifactAvailable) or advanced.data != {
            "reports": [
                {"report_date": "2026-06-19"},
                {"report_date": "2026-06-12"},
            ]
        }:
            raise AssertionError(advanced)


def test_routes_openapi_parameters_examples_and_clients_are_exact() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp) / "cot"
        _write_pair(directory)
        with _client(directory) as client:
            catalog_response = client.get(CATALOG_ROUTE)
            detail_response = client.get("/api/v1/reports/cot/2026-06-12")
            invalid_response = client.get("/api/v1/reports/cot/2026-02-30")
            traversal_response = client.get("/api/v1/reports/cot/..%2Fsecret")
            generated = client.get("/openapi.json").json()
    if catalog_response.status_code != 200 or detail_response.status_code != 200:
        raise AssertionError((catalog_response.text, detail_response.text))
    if catalog_response.headers.get("cache-control") != "no-store" or detail_response.headers.get("cache-control") != "no-store":
        raise AssertionError((catalog_response.headers, detail_response.headers))
    if invalid_response.status_code != 422 or traversal_response.status_code != 422:
        raise AssertionError((invalid_response.status_code, traversal_response.status_code))
    CotCatalogData.model_validate(catalog_response.json()["data"], strict=True)
    CotReportData.model_validate(detail_response.json()["data"], strict=True)
    if detail_response.json()["meta"] != {
        "sourceId": COT_DETAIL_SOURCE_ID,
        "asOf": "2026-06-12",
        "generatedAt": "2026-06-14T12:09:20.318228Z",
    }:
        raise AssertionError(detail_response.json())

    if CATALOG_ROUTE not in generated["paths"] or DETAIL_ROUTE not in generated["paths"]:
        raise AssertionError(generated["paths"])
    parameter = generated["paths"][DETAIL_ROUTE]["get"]["parameters"][0]
    if parameter["name"] != "report_date" or parameter["in"] != "path":
        raise AssertionError(parameter)
    for route, expected_examples in (
        (CATALOG_ROUTE, {"available", "empty", "unavailable"}),
        (DETAIL_ROUTE, {"available", "unavailable"}),
    ):
        examples = generated["paths"][route]["get"]["responses"]["200"]["content"]["application/json"]["examples"]
        if set(examples) != expected_examples:
            raise AssertionError((route, examples))

    draft = yaml.safe_load((ROOT / "docs/api/quant-radar-v1.openapi.yaml").read_text())
    if draft["info"]["version"] != "1.23.0-draft":
        raise AssertionError(draft["info"])
    for route in (CATALOG_ROUTE, DETAIL_ROUTE):
        if route not in draft["paths"]:
            raise AssertionError(route)

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return _response(
            _catalog_envelope("2026-06-12")
            if str(request.url) == CATALOG_URL
            else _detail_envelope()
        )

    transport = httpx.MockTransport(handler)
    catalog = _read_api.load_cot_catalog(transport=transport)
    detail = _read_api.load_cot_report("2026-06-12", transport=transport)
    if not isinstance(catalog, _read_api.CotCatalogApiAvailable):
        raise AssertionError(catalog)
    if not isinstance(detail, _read_api.CotReportApiAvailable):
        raise AssertionError(detail)
    if seen != [CATALOG_URL, DETAIL_URL]:
        raise AssertionError(seen)
    invalid = _read_api.load_cot_report("../../secret", transport=transport)
    if not isinstance(invalid, _read_api.CotReportApiInvalidDate) or seen != [CATALOG_URL, DETAIL_URL]:
        raise AssertionError((invalid, seen))


def test_client_failure_matrix_caps_metadata_and_immutability_are_strict() -> None:
    for loader, payload, max_bytes in (
        (_read_api.load_cot_catalog, _catalog_envelope("2026-06-12"), 64 * 1024),
        (lambda **kwargs: _read_api.load_cot_report("2026-06-12", **kwargs), _detail_envelope(), 512 * 1024),
    ):
        failures = (
            ("transport_error", httpx.ConnectError("private")),
            ("http_status", httpx.Response(503)),
            ("invalid_media_type", httpx.Response(200, headers={"Content-Type": "text/plain", "Cache-Control": "no-store"}, text="{}")),
            ("invalid_cache_control", httpx.Response(200, headers={"Content-Type": "application/json"}, json=payload)),
        )
        for expected, response_or_error in failures:
            def handler(_request: httpx.Request) -> httpx.Response:
                if isinstance(response_or_error, Exception):
                    raise response_or_error
                return response_or_error

            result = loader(transport=httpx.MockTransport(handler))
            if result.reason != expected:  # type: ignore[union-attr]
                raise AssertionError((expected, result))
        too_large = loader(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
                    content=b"{" + b" " * max_bytes,
                )
            )
        )
        if too_large.reason != "response_too_large":  # type: ignore[union-attr]
            raise AssertionError(too_large)

    for reason in sorted(_components.ARTIFACT_REASON_CODES):
        catalog_payload = {
            "available": False,
            "reason": reason,
            "data": None,
            "meta": {"sourceId": COT_CATALOG_SOURCE_ID, "asOf": None, "generatedAt": None},
        }
        catalog = _read_api.load_cot_catalog(
            transport=httpx.MockTransport(lambda _request, payload=catalog_payload: _response(payload))
        )
        if catalog != _read_api.CotCatalogApiUnavailable(reason):
            raise AssertionError(catalog)
        detail_payload = {
            "available": False,
            "reason": reason,
            "data": None,
            "meta": {"sourceId": COT_DETAIL_SOURCE_ID, "asOf": "2026-06-12", "generatedAt": None},
        }
        detail = _read_api.load_cot_report(
            "2026-06-12",
            transport=httpx.MockTransport(lambda _request, payload=detail_payload: _response(payload)),
        )
        if detail != _read_api.CotReportApiUnavailable("2026-06-12", reason):
            raise AssertionError(detail)

    value = _read_api.CotCatalogApiFailure("transport_error")
    try:
        value.reason = "http_status"  # type: ignore[misc]
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("COT outcome is mutable")


def _schedule(identifier: str) -> ScheduleEntry:
    return ScheduleEntry.model_validate(
        {
            "id": identifier,
            "name": f"COT report {identifier}",
            "category": "美股",
            "cron": "0 1 * * 6",
            "cron_note": "weekly",
            "description": "COT report",
            "result_type": "cot",
        },
        strict=True,
    )


def _app_text(app: AppTest) -> str:
    return "\n".join(
        str(element.value)
        for collection in (app.caption, app.warning, app.info, app.error, app.success, app.markdown)
        for element in collection
    )


def test_schedules_reuses_catalog_and_cot_page_is_api_only_and_sanitized() -> None:
    catalog_data = CotCatalogData.model_validate(
        {"reports": [{"report_date": "2026-06-12"}]}, strict=True
    )
    with patch(
        "ui.sys_schedules._read_api.load_cot_catalog",
        return_value=_read_api.CotCatalogApiAvailable(catalog_data),
    ) as loader:
        content, reason = sys_schedules._latest_cot_result()
    if loader.call_count != 1 or reason is not None or content != "📑 最新週報:`2026-06-12.md`":
        raise AssertionError((loader.call_count, content, reason))

    state = sys_schedules.ScheduleRegistryState(
        "api_available", (_schedule("cot_a"), _schedule("cot_b")), None
    )
    with (
        patch("ui.sys_schedules._load_schedules", return_value=state),
        patch(
            "ui.sys_schedules._read_api.load_cot_catalog",
            return_value=_read_api.CotCatalogApiAvailable(catalog_data),
        ) as loader,
    ):
        app = AppTest.from_string(
            "from ui.sys_schedules import render\nrender()\n", default_timeout=10
        ).run()
    if app.exception or loader.call_count != 1:
        raise AssertionError((app.exception, loader.call_count))
    if _app_text(app).count("2026-06-12.md") != 2:
        raise AssertionError(_app_text(app))

    unsafe_markdown = (
        _markdown()
        + "\n<script>alert(1)</script>"
        + "\n[bad](javascript:alert(1))"
        + "\n![x](data:text/html,bad)"
        + "\n[reference][private-target]"
        + "\n![reference image][private-target]"
        + "\n[private-target]: file:///private/report"
        + "\nhttps://private.example/report"
    )
    report = CotReportData.model_validate(
        _detail_data(markdown=unsafe_markdown), strict=True
    )
    with (
        patch(
            "ui.us_cot._read_api.load_cot_catalog",
            return_value=_read_api.CotCatalogApiAvailable(catalog_data),
        ) as catalog_loader,
        patch(
            "ui.us_cot._read_api.load_cot_report",
            return_value=_read_api.CotReportApiAvailable(report),
        ) as detail_loader,
        patch("ui.us_cot._render_generate"),
    ):
        app = AppTest.from_string(
            "from ui.us_cot import render\nrender()\n", default_timeout=10
        ).run()
    if app.exception or catalog_loader.call_count != 1 or detail_loader.call_count != 1:
        raise AssertionError((app.exception, catalog_loader.call_count, detail_loader.call_count))
    passed_markdown = "\n".join(str(element.value) for element in app.markdown)
    for forbidden in (
        "<script>",
        "javascript:",
        "data:text/html",
        "file:///private/report",
        "https://private.example/report",
        "private-target",
    ):
        if forbidden in passed_markdown:
            raise AssertionError((forbidden, passed_markdown))
    for expected in ("ES 週五收盤", "COT as-of", "籌碼結構", "風險提示"):
        if expected not in _app_text(app):
            raise AssertionError((expected, _app_text(app)))

    for outcome in (
        _read_api.CotCatalogApiUnavailable("missing"),
        _read_api.CotCatalogApiFailure("transport_error"),
    ):
        with (
            patch("ui.us_cot._read_api.load_cot_catalog", return_value=outcome),
            patch("ui.us_cot._render_generate"),
        ):
            app = AppTest.from_string(
                "from ui.us_cot import render\nrender()\n", default_timeout=10
            ).run()
        if app.exception or "private" in _app_text(app):
            raise AssertionError((outcome, app.exception, _app_text(app)))


def test_consumers_have_no_persisted_local_fallback_and_python310_ast() -> None:
    for path in (
        ROOT / "api/models.py",
        ROOT / "api/artifacts.py",
        ROOT / "api/main.py",
        ROOT / "ui/_read_api.py",
        ROOT / "ui/sys_schedules.py",
        ROOT / "ui/us_cot.py",
    ):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 10))

    schedules = (ROOT / "ui/sys_schedules.py").read_text(encoding="utf-8")
    functions = {
        node.name: ast.get_source_segment(schedules, node) or ""
        for node in ast.parse(schedules).body
        if isinstance(node, ast.FunctionDef)
    }
    cot_result = functions["_latest_cot_result"]
    if cot_result.count("load_cot_catalog()") != 1:
        raise AssertionError(cot_result)
    for forbidden in ("REPORTS_DIR", ".glob(", "_shared.load_json"):
        if forbidden in cot_result:
            raise AssertionError((forbidden, cot_result))
    if '"cot"' not in functions["render"] or "result_cache" not in functions["render"]:
        raise AssertionError(functions["render"])

    source = (ROOT / "ui/us_cot.py").read_text(encoding="utf-8")
    render = next(
        node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == "render"
    )
    render_source = ast.get_source_segment(source, render) or ""
    if render_source.count("load_cot_catalog()") != 1 or render_source.count("load_cot_report(chosen)") != 1:
        raise AssertionError(render_source)
    for forbidden in ("_COT_DIR", '.glob("*.md")', 'f"{chosen}.md"', 'f"{chosen}.verified.json"', "_shared.load_json"):
        if forbidden in source:
            raise AssertionError(f"COT page retained persisted local read: {forbidden}")
    for preserved in ("codex_auth_flow", "cot_es.generate_report", "_read_text"):
        if preserved not in source:
            raise AssertionError(f"COT page removed local mutation/auth sibling: {preserved}")


def main() -> None:
    tests = (
        test_catalog_and_detail_sources_are_bounded_strict_and_private,
        test_missing_invalid_partial_oversized_and_recovery_states_are_fail_soft,
        test_generation_symlink_tracks_atomic_current_without_file_symlinks,
        test_routes_openapi_parameters_examples_and_clients_are_exact,
        test_client_failure_matrix_caps_metadata_and_immutability_are_strict,
        test_schedules_reuses_catalog_and_cot_page_is_api_only_and_sanitized,
        test_consumers_have_no_persisted_local_fallback_and_python310_ast,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
