#!/usr/bin/env python3
"""Focused Phase 6P-6R fixed theme-drill API and UI-boundary tests."""

from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import yaml
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.artifacts import read_theme_drill  # noqa: E402
from api.main import create_app  # noqa: E402
from api.models import ArtifactAvailable, ThemeDrillData  # noqa: E402
from ui import _read_api, sector_rotation  # noqa: E402


def _write_baskets(path: Path, themes: dict[str, object] | None = None) -> None:
    payload = {
        "_note": "private maintainer note",
        "themes": themes
        if themes is not None
        else {
            "Theme A": {
                "desc": "private description",
                "tickers": ["SECRET"],
                "reps_hint": ["SECRET"],
                "parent_sector_etfs": ["XLK", "XLI"],
            },
            "Theme B": {
                "desc": "second",
                "tickers": ["HIDDEN"],
                "reps_hint": [],
                "parent_sector_etfs": ["XLI"],
            },
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _response_transport(
    result: object,
    *,
    cache_control: str = "no-store",
) -> httpx.MockTransport:
    body = result.model_dump_json(by_alias=True).encode("utf-8")

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "application/json", "Cache-Control": cache_control},
            request=request,
        )

    return httpx.MockTransport(handler)


def test_reader_projects_exact_sorted_reverse_map_and_privacy() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "theme_baskets.json"
        _write_baskets(path)
        result = read_theme_drill(path)
        if not isinstance(result, ArtifactAvailable):
            raise AssertionError(result)
        if result.data.model_dump(mode="json") != {
            "sectors": [
                {"etf": "XLI", "themes": ["Theme A", "Theme B"]},
                {"etf": "XLK", "themes": ["Theme A"]},
            ]
        }:
            raise AssertionError(result.data)
        serialized = result.model_dump_json(by_alias=True)
        for private in ("private maintainer", "private description", "SECRET", "HIDDEN"):
            if private in serialized:
                raise AssertionError(serialized)

        _write_baskets(path, {})
        empty = read_theme_drill(path)
        if not empty.available or empty.data.sectors != []:
            raise AssertionError(empty)


def test_reader_fails_soft_on_invalid_sources_and_recovers() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "theme_baskets.json"
        if read_theme_drill(path).reason != "missing":
            raise AssertionError("missing reason drift")

        invalid_payloads = (
            b"\xff",
            b"{",
            json.dumps({"themes": [], "extra": True}).encode(),
            json.dumps({"themes": {"A": []}}).encode(),
            json.dumps({"themes": {"A": {}}}).encode(),
            json.dumps({"themes": {"A": {"parent_sector_etfs": "XLK"}}}).encode(),
            json.dumps({"themes": {"A": {"parent_sector_etfs": []}}}).encode(),
            json.dumps({"themes": {"A": {"parent_sector_etfs": ["BAD"]}}}).encode(),
            json.dumps({"themes": {"A": {"parent_sector_etfs": ["XLK", "XLK"]}}}).encode(),
            json.dumps(
                {
                    "themes": {
                        "AI": {"parent_sector_etfs": ["XLK"]},
                        "ai": {"parent_sector_etfs": ["XLI"]},
                    }
                }
            ).encode(),
            json.dumps(
                {
                    "themes": {
                        f"Theme {index}": {"parent_sector_etfs": ["XLK"]}
                        for index in range(101)
                    }
                }
            ).encode(),
        )
        for payload in invalid_payloads:
            path.write_bytes(payload)
            if read_theme_drill(path).reason != "invalid_shape":
                raise AssertionError(payload[:80])

        path.write_bytes(json.dumps({"_note": "x" * (70 * 1024), "themes": {}}).encode())
        if read_theme_drill(path).reason != "invalid_shape":
            raise AssertionError("source cap was not enforced")

        path.unlink()
        outside = root / "outside.json"
        _write_baskets(outside)
        path.symlink_to(outside)
        if read_theme_drill(path).reason != "unreadable":
            raise AssertionError("symlinked source was accepted")
        path.unlink()
        _write_baskets(path)
        if not read_theme_drill(path).available:
            raise AssertionError("valid source did not recover immediately")


def test_fixed_route_is_no_store_injected_and_non_mutating() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "theme_baskets.json"
        _write_baskets(path)
        before = path.read_bytes()
        app = create_app(theme_drill_path=path)
        with patch("api.main._is_loopback_peer", return_value=True):
            with TestClient(app) as client:
                response = client.get(
                    "/api/v1/market-context/theme-drill",
                    headers={"Host": "127.0.0.1"},
                )
        if response.status_code != 200 or response.headers.get("cache-control") != "no-store":
            raise AssertionError((response.status_code, response.headers, response.text))
        if response.json()["meta"] != {
            "sourceId": "market-context.theme-drill",
            "asOf": None,
            "generatedAt": None,
        }:
            raise AssertionError(response.json())
        if path.read_bytes() != before:
            raise AssertionError("GET changed the fixed source")


def test_client_is_strict_immutable_and_recovers_without_cache() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "theme_baskets.json"
        _write_baskets(path)
        server = read_theme_drill(path)
        result = _read_api.load_theme_drill(transport=_response_transport(server))
        if not isinstance(result, _read_api.ThemeDrillApiAvailable):
            raise AssertionError(result)
        if tuple(sector.etf for sector in result.drill.sectors) != ("XLI", "XLK"):
            raise AssertionError(result)
        try:
            result.drill = result.drill  # type: ignore[misc]
        except FrozenInstanceError:
            pass
        else:
            raise AssertionError("theme-drill client outcome is mutable")

        invalid = server.model_copy(deep=True)
        invalid.meta.source_id = "wrong.source"
        if _read_api.load_theme_drill(
            transport=_response_transport(invalid)
        ) != _read_api.ThemeDrillApiFailure("invalid_envelope"):
            raise AssertionError("wrong source metadata was accepted")
        if _read_api.load_theme_drill(
            transport=_response_transport(server, cache_control="max-age=60")
        ) != _read_api.ThemeDrillApiFailure("invalid_cache_control"):
            raise AssertionError("cacheable response was accepted")
        recovered = _read_api.load_theme_drill(transport=_response_transport(server))
        if not isinstance(recovered, _read_api.ThemeDrillApiAvailable):
            raise AssertionError("client negative-cached a prior failure")

        async def oversized_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=b" " * (256 * 1024 + 1),
                headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
                request=request,
            )

        oversized = _read_api.load_theme_drill(
            transport=httpx.MockTransport(oversized_handler)
        )
        if oversized != _read_api.ThemeDrillApiFailure("response_too_large"):
            raise AssertionError(oversized)


def test_sector_drill_loads_once_and_has_no_local_fallback() -> None:
    drill = ThemeDrillData.model_validate(
        {"sectors": [{"etf": "XLK", "themes": ["Theme A", "Theme B"]}]},
        strict=True,
    )
    streamlit = MagicMock()
    streamlit.selectbox.return_value = "XLK"
    with (
        patch.object(sector_rotation, "st", streamlit),
        patch.object(
            sector_rotation._read_api,
            "load_theme_drill",
            return_value=_read_api.ThemeDrillApiAvailable(drill),
        ) as load,
    ):
        sector_rotation._render_sector_themes_drill(
            [{"etf": "XLK", "name_zh": "科技"}]
        )
    if load.call_count != 1:
        raise AssertionError(load.call_count)
    if streamlit.selectbox.call_args.args[1] != ["XLK"]:
        raise AssertionError(streamlit.selectbox.call_args)

    for outcome in (
        _read_api.ThemeDrillApiAvailable(ThemeDrillData(sectors=[])),
        _read_api.ThemeDrillApiUnavailable("missing"),
        _read_api.ThemeDrillApiFailure("transport_error"),
    ):
        failed_st = MagicMock()
        with (
            patch.object(sector_rotation, "st", failed_st),
            patch.object(sector_rotation._read_api, "load_theme_drill", return_value=outcome) as load,
        ):
            sector_rotation._render_sector_themes_drill([])
        if load.call_count != 1 or failed_st.selectbox.called:
            raise AssertionError((outcome, load.call_count, failed_st.mock_calls))

    source = (ROOT / "ui" / "sector_rotation.py").read_text(encoding="utf-8")
    if "load_baskets" in source or "from scripts.theme_flow" in source:
        raise AssertionError("Sector Rotation retained the local theme-drill fallback")


def test_static_and_generated_openapi_are_exact() -> None:
    static = yaml.safe_load(
        (ROOT / "docs" / "api" / "quant-radar-v1.openapi.yaml").read_text(
            encoding="utf-8"
        )
    )
    generated = create_app().openapi()
    if static["info"]["version"] != "1.23.0-draft" or generated["info"]["version"] != "1.23.0-draft":
        raise AssertionError((static["info"], generated["info"]))
    route = "/api/v1/market-context/theme-drill"
    for document in (static, generated):
        operation = document["paths"][route]["get"]
        if operation["operationId"] != "getThemeDrill" or operation.get("parameters") not in (None, []):
            raise AssertionError(operation)
        if set(operation["responses"]) != {"200", "500"}:
            raise AssertionError(operation["responses"])
    generated_examples = generated["paths"][route]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["examples"]
    static_examples = static["components"]["responses"]["ThemeDrillResponse"]["content"][
        "application/json"
    ]["examples"]
    if generated_examples != static_examples:
        raise AssertionError((static_examples, generated_examples))


TESTS = (
    test_reader_projects_exact_sorted_reverse_map_and_privacy,
    test_reader_fails_soft_on_invalid_sources_and_recovers,
    test_fixed_route_is_no_store_injected_and_non_mutating,
    test_client_is_strict_immutable_and_recovers_without_cache,
    test_sector_drill_loads_once_and_has_no_local_fallback,
    test_static_and_generated_openapi_are_exact,
)


if __name__ == "__main__":
    failures = 0
    for test in TESTS:
        try:
            test()
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  FAIL {test.__name__}: {type(exc).__name__}: {exc}")
        else:
            print(f"  PASS {test.__name__}")
    print(f"\n{len(TESTS) - failures}/{len(TESTS)} passed")
    raise SystemExit(1 if failures else 0)
