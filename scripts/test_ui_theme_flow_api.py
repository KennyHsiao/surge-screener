#!/usr/bin/env python3
"""Focused contracts for Phase 4V Theme Flow read-side separation."""

from __future__ import annotations

import ast
import json
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.artifacts import ARTIFACTS, ArtifactSpec, ResolvedArtifactPath, read_artifact  # noqa: E402
from api.models import (  # noqa: E402
    ArtifactAvailable,
    ArtifactUnavailable,
    ThemeFlowAnalysisData,
    ThemeFlowData,
)
from scripts.theme_rotation import board_fingerprint  # noqa: E402
from ui import _components, _read_api, theme_flow  # noqa: E402


SNAPSHOT_SOURCE_ID = "market-context.theme-flow.latest"
ANALYSIS_SOURCE_ID = "market-context.theme-flow.analysis"
SNAPSHOT_URL = "http://127.0.0.1:8000/api/v1/market-context/theme-flow/latest"
ANALYSIS_URL = "http://127.0.0.1:8000/api/v1/market-context/theme-flow/analysis"
ROOT_FIELDS = {
    "as_of",
    "generated_at",
    "benchmark",
    "n_failed_download",
    "buckets",
    "shared_mega_caps",
    "themes",
    "board_fingerprint",
}
THEME_FIELDS = {
    "theme",
    "desc",
    "parent_sector_etfs",
    "flow_5d",
    "flow_20d",
    "accel",
    "flow_5d_norm",
    "flow_20d_norm",
    "accel_norm",
    "ret_5d",
    "top_share",
    "high_concentration",
    "breadth_inflow_ratio",
    "positive_flow_count",
    "negative_flow_count",
    "n_used",
    "n_total",
    "reps",
    "raw_heat_score",
    "signal_quality",
    "heat_score",
    "capital_state",
    "bottom_fishing",
}
ANALYSIS_FIELDS = {"status", "as_of", "generated_at", "board_fingerprint", "read"}
READ_FIELDS = {
    "headline",
    "confidence",
    "accelerating_in",
    "rotating_out",
    "bottom_fishing",
    "insider_divergence",
    "next_thesis",
    "caveats",
}


def _theme_row(name: str = "AI 基礎設施") -> dict[str, object]:
    return {
        "theme": name,
        "desc": "fixture theme",
        "parent_sector_etfs": ["XLK"],
        "flow_5d": 1_000_000.0,
        "flow_20d": 2_000_000.0,
        "accel": 500_000.0,
        "flow_5d_norm": 1.5,
        "flow_20d_norm": 2.5,
        "accel_norm": 0.5,
        "rvol": 1.2,
        "ret_5d": 3.0,
        "excess_5d": 1.0,
        "top_share": 0.4,
        "high_concentration": False,
        "breadth_inflow_ratio": 0.7,
        "positive_flow_count": 2,
        "negative_flow_count": 1,
        "n_used": 3,
        "n_total": 3,
        "n_failed": 0,
        "reps": [
            {
                "ticker": "NVDA",
                "flow_20d": 1_500_000.0,
                "flow_5d": 800_000.0,
                "ret_5d": 4.0,
            }
        ],
        "raw_heat_score": 80.0,
        "signal_quality": 0.9,
        "heat_score": 72.0,
        "capital_state": "加速流入(推估)",
        "bottom_fishing": False,
        "eastmoney_main_net_5d": None,
        "eastmoney_main_net_20d": None,
        "eastmoney_main_pct_latest": None,
        "money_flow_source": "price_volume_proxy",
        "money_flow_caveat": "private source caveat",
    }


def _snapshot_source(**overrides: object) -> dict[str, object]:
    row = _theme_row()
    payload: dict[str, object] = {
        "as_of": "2026-08-03",
        "generated_at": "2026-08-03T01:02:03.123456+00:00",
        "benchmark": "SPY",
        "schema_version": 5,
        "n_failed_download": 0,
        "params": {"private": True},
        "themes": [row],
        "buckets": {
            "加速流入(推估)": [row["theme"]],
            "流入趨緩": [],
            "中性": [],
            "流出(推估)": [],
        },
        "bottom_fishing": [],
        "shared_mega_caps": [{"ticker": "NVDA", "themes": 2}],
    }
    payload.update(overrides)
    return payload


def _snapshot_public() -> dict[str, object]:
    source = _snapshot_source()
    row = source["themes"][0]  # type: ignore[index]
    themes = [{key: row[key] for key in THEME_FIELDS}]  # type: ignore[index]
    return {
        "as_of": source["as_of"],
        "generated_at": source["generated_at"],
        "benchmark": source["benchmark"],
        "n_failed_download": source["n_failed_download"],
        "buckets": source["buckets"],
        "shared_mega_caps": source["shared_mega_caps"],
        "themes": themes,
        "board_fingerprint": board_fingerprint(source["as_of"], themes),
    }


def _analysis_source(
    *,
    fingerprint: str | None = None,
    **overrides: object,
) -> dict[str, object]:
    fp = fingerprint or str(_snapshot_public()["board_fingerprint"])
    payload: dict[str, object] = {
        "status": "ready",
        "generated_at": "2026-08-03T02:03:04.123456+00:00",
        "as_of": "2026-08-03",
        "board_fingerprint": fp,
        "validation_version": 8,
        "read": {
            "headline": "fixture headline",
            "confidence": "medium",
            "accelerating_in": [
                {"theme": "AI 基礎設施", "name": "AI", "why": "fixture why"}
            ],
            "rotating_out": [],
            "bottom_fishing": [],
            "insider_divergence": [],
            "next_thesis": "fixture next thesis",
            "caveats": ["fixture caveat"],
        },
        "bottom_fishing": [],
        "buckets": {"private": True},
        "macro": {"private": True},
    }
    payload.update(overrides)
    return payload


def _analysis_public(fingerprint: str | None = None) -> dict[str, object]:
    source = _analysis_source(fingerprint=fingerprint)
    return {
        "status": source["status"],
        "as_of": source["as_of"],
        "generated_at": source["generated_at"],
        "board_fingerprint": source["board_fingerprint"],
        "read": source["read"],
    }


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _spec(source_id: str, path: Path) -> ArtifactSpec:
    return replace(
        ARTIFACTS[source_id],
        resolver=lambda: ResolvedArtifactPath(path),
    )


def _response(payload: object) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        content=json.dumps(payload).encode("utf-8"),
    )


def _envelope(
    source_id: str,
    data: dict[str, object] | None,
    *,
    available: bool = True,
    reason: str = "ok",
    as_of: str | None = "2026-08-03",
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


def _app_text(app: AppTest) -> str:
    return "\n".join(
        str(element.value)
        for collection in (app.caption, app.warning, app.info, app.error, app.markdown)
        for element in collection
    )


def test_theme_registries_project_strict_current_contracts_and_fail_soft() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        snapshot_path = base / "snapshot.json"
        analysis_path = base / "analysis.json"

        snapshot = read_artifact(
            _spec(SNAPSHOT_SOURCE_ID, _write(snapshot_path, _snapshot_source()))
        )
        if not isinstance(snapshot, ArtifactAvailable):
            raise AssertionError(snapshot)
        if set(snapshot.data) != ROOT_FIELDS:
            raise AssertionError(snapshot.data)
        if set(snapshot.data["themes"][0]) != THEME_FIELDS:
            raise AssertionError(snapshot.data["themes"][0])
        expected_fp = board_fingerprint(
            snapshot.data["as_of"], snapshot.data["themes"]
        )
        if snapshot.data["board_fingerprint"] != expected_fp:
            raise AssertionError(snapshot.data)
        projected_theme = snapshot.data["themes"][0]
        for private in (
            "rvol",
            "excess_5d",
            "n_failed",
            "eastmoney_main_net_5d",
            "money_flow_source",
            "money_flow_caveat",
        ):
            if private in projected_theme:
                raise AssertionError(snapshot.data)

        analysis = read_artifact(
            _spec(ANALYSIS_SOURCE_ID, _write(analysis_path, _analysis_source()))
        )
        if not isinstance(analysis, ArtifactAvailable):
            raise AssertionError(analysis)
        if set(analysis.data) != ANALYSIS_FIELDS:
            raise AssertionError(analysis.data)
        if set(analysis.data["read"]) != READ_FIELDS:
            raise AssertionError(analysis.data["read"])
        if "macro" in json.dumps(analysis.data):
            raise AssertionError(analysis.data)

        invalid_snapshots = [
            _snapshot_source(schema_version=4),
            _snapshot_source(extra="secret"),
            _snapshot_source(themes=[]),
        ]
        invalid_analyses = [
            _analysis_source(validation_version=7),
            _analysis_source(status="error"),
            _analysis_source(extra="secret"),
        ]
        for source_id, path, invalids in (
            (SNAPSHOT_SOURCE_ID, snapshot_path, invalid_snapshots),
            (ANALYSIS_SOURCE_ID, analysis_path, invalid_analyses),
        ):
            for invalid in invalids:
                outcome = read_artifact(_spec(source_id, _write(path, invalid)))
                if not isinstance(outcome, ArtifactUnavailable) or outcome.reason != "invalid_shape":
                    raise AssertionError((source_id, invalid, outcome))


def test_theme_clients_validate_urls_provenance_metadata_and_caps() -> None:
    snapshot = ThemeFlowData.model_validate(_snapshot_public(), strict=True)
    analysis = ThemeFlowAnalysisData.model_validate(_analysis_public(), strict=True)
    cases = (
        (
            _read_api.load_theme_flow,
            _read_api.ThemeFlowApiAvailable,
            SNAPSHOT_URL,
            SNAPSHOT_SOURCE_ID,
            snapshot,
            _read_api._THEME_FLOW_MAX_RESPONSE_BYTES,
            "2026-08-03T01:02:03.123456+00:00",
        ),
        (
            _read_api.load_theme_flow_analysis,
            _read_api.ThemeFlowAnalysisApiAvailable,
            ANALYSIS_URL,
            ANALYSIS_SOURCE_ID,
            analysis,
            _read_api._THEME_FLOW_ANALYSIS_MAX_RESPONSE_BYTES,
            "2026-08-03T02:03:04.123456+00:00",
        ),
    )
    for loader, available_type, url, source_id, data, cap, generated_at in cases:
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            return _response(
                _envelope(
                    source_id,
                    data.model_dump(mode="json"),
                    generated_at=generated_at,
                )
            )

        outcome = loader(transport=httpx.MockTransport(handler))
        if not isinstance(outcome, available_type) or seen != [url]:
            raise AssertionError((outcome, seen))

        unavailable = loader(
            transport=httpx.MockTransport(
                lambda _request: _response(
                    _envelope(
                        source_id,
                        None,
                        available=False,
                        reason="missing",
                        as_of=None,
                    )
                )
            )
        )
        if not isinstance(
            unavailable,
            (
                _read_api.ThemeFlowApiUnavailable,
                _read_api.ThemeFlowAnalysisApiUnavailable,
            ),
        ) or unavailable.reason != "missing":
            raise AssertionError(unavailable)

        for payload in (
            _envelope("wrong.source", data.model_dump(mode="json"), generated_at=generated_at),
            _envelope(source_id, data.model_dump(mode="json"), as_of="2026-08-02", generated_at=generated_at),
            _envelope(source_id, data.model_dump(mode="json"), generated_at="2026-08-03T09:09:09Z"),
        ):
            invalid = loader(
                transport=httpx.MockTransport(
                    lambda _request, payload=payload: _response(payload)
                )
            )
            if not isinstance(
                invalid,
                (
                    _read_api.ThemeFlowApiFailure,
                    _read_api.ThemeFlowAnalysisApiFailure,
                ),
            ) or invalid.reason != "invalid_envelope":
                raise AssertionError(invalid)

        oversized = httpx.Response(
            200,
            headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
            content=b"x" * (cap + 1),
        )
        too_large = loader(transport=httpx.MockTransport(lambda _request: oversized))
        if too_large.reason != "response_too_large":
            raise AssertionError(too_large)


def test_theme_snapshot_state_distinguishes_every_outcome_once() -> None:
    snapshot = ThemeFlowData.model_validate(_snapshot_public(), strict=True)
    cases: tuple[tuple[_read_api.ThemeFlowApiResult, str], ...] = (
        (_read_api.ThemeFlowApiAvailable(snapshot), "api_available"),
        *tuple(
            (_read_api.ThemeFlowApiUnavailable(reason), "api_unavailable")
            for reason in sorted(_components.ARTIFACT_REASON_CODES)
        ),
        *tuple(
            (_read_api.ThemeFlowApiFailure(reason), "api_failure")
            for reason in sorted(_components.CLIENT_FAILURE_REASON_CODES)
        ),
    )
    for outcome, expected in cases:
        with patch(
            "ui.theme_flow._read_api.load_theme_flow", return_value=outcome
        ) as loader:
            state = theme_flow._theme_flow_state()
        if loader.call_count != 1 or state.status != expected:
            raise AssertionError((outcome, state, loader.call_count))
        if (expected == "api_available") != isinstance(state.flow, dict):
            raise AssertionError((outcome, state))


def _render_missing_snapshot(outcome: _read_api.ThemeFlowApiResult) -> AppTest:
    with (
        patch("ui.theme_flow._read_api.load_theme_flow", return_value=outcome),
        patch("ui.theme_flow._background_controls", return_value=None),
        patch(
            "ui.theme_flow._shared.load_theme_flow",
            side_effect=AssertionError("Theme snapshot attempted a local fallback"),
        ),
    ):
        return AppTest.from_string(
            "from ui.theme_flow import render\nrender()\n", default_timeout=10
        ).run()


def test_snapshot_unavailable_and_failure_are_visible_without_local_fallback() -> None:
    cases: tuple[tuple[_read_api.ThemeFlowApiResult, str], ...] = (
        (_read_api.ThemeFlowApiUnavailable("missing"), "主題資金流資料目前無法使用"),
        (_read_api.ThemeFlowApiFailure("transport_error"), "主題資金流服務目前無法使用"),
    )
    for outcome, expected in cases:
        app = _render_missing_snapshot(outcome)
        rendered = _app_text(app)
        if app.exception or expected not in rendered:
            raise AssertionError((outcome, app.exception, rendered))
        if outcome.reason in rendered:
            raise AssertionError(f"raw reason leaked: {outcome.reason}")


def test_only_artifact_unavailable_auto_launches_background_refresh() -> None:
    for outcome, expected_calls in (
        (_read_api.ThemeFlowApiUnavailable("missing"), 1),
        (_read_api.ThemeFlowApiFailure("transport_error"), 0),
    ):
        controls = MagicMock()
        controls.read_status.return_value = None
        controls.is_running.return_value = False
        controls.launch_background.return_value = {"status": "running"}
        with (
            patch("ui.theme_flow._read_api.load_theme_flow", return_value=outcome),
            patch("ui.theme_flow._background_controls", return_value=controls),
        ):
            app = AppTest.from_string(
                "from ui.theme_flow import render\nrender()\n", default_timeout=10
            ).run()
        if app.exception or controls.launch_background.call_count != expected_calls:
            raise AssertionError(
                (outcome, app.exception, controls.launch_background.call_count)
            )


def _render_analysis(outcome: _read_api.ThemeFlowAnalysisApiResult) -> tuple[AppTest, int]:
    flow = _snapshot_public()
    with (
        patch(
            "ui.theme_flow._read_api.load_theme_flow_analysis",
            return_value=outcome,
        ) as loader,
        patch("ui.theme_flow._background_controls", return_value=None),
    ):
        app = AppTest.from_string(
            "from ui.theme_flow import _render_bottom_and_read\n"
            f"_render_bottom_and_read({flow!r})\n",
            default_timeout=10,
        ).run()
    return app, loader.call_count


def test_analysis_requires_current_board_and_distinguishes_failures() -> None:
    current = ThemeFlowAnalysisData.model_validate(_analysis_public(), strict=True)
    app, calls = _render_analysis(_read_api.ThemeFlowAnalysisApiAvailable(current))
    if app.exception or calls != 1 or "fixture headline" not in _app_text(app):
        raise AssertionError((app.exception, calls, _app_text(app)))

    stale = ThemeFlowAnalysisData.model_validate(
        _analysis_public("0123456789abcdef"), strict=True
    )
    app, calls = _render_analysis(_read_api.ThemeFlowAnalysisApiAvailable(stale))
    rendered = _app_text(app)
    if app.exception or calls != 1 or "既有 AI 研判對應舊版主題資料" not in rendered:
        raise AssertionError((app.exception, calls, rendered))
    if "fixture headline" in rendered:
        raise AssertionError("stale analysis rendered")

    cases: tuple[tuple[_read_api.ThemeFlowAnalysisApiResult, str], ...] = (
        (
            _read_api.ThemeFlowAnalysisApiUnavailable("invalid_shape"),
            "AI 研判資料目前無法使用",
        ),
        (
            _read_api.ThemeFlowAnalysisApiFailure("transport_error"),
            "AI 研判服務目前無法使用",
        ),
    )
    for outcome, expected in cases:
        app, calls = _render_analysis(outcome)
        rendered = _app_text(app)
        if app.exception or calls != 1 or expected not in rendered:
            raise AssertionError((outcome, app.exception, calls, rendered))
        if outcome.reason in rendered:
            raise AssertionError(f"raw reason leaked: {outcome.reason}")


def test_source_has_two_fixed_clients_no_selected_local_read_and_preserved_mutations() -> None:
    path = ROOT / "ui" / "theme_flow.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    render = functions["render"]
    analysis = functions["_render_bottom_and_read"]
    if render.count("_theme_flow_state()") != 1:
        raise AssertionError(render)
    if "read_snapshot" in render or "load_theme_flow" in render:
        raise AssertionError("render retained a local Theme snapshot read")
    if analysis.count("_theme_flow_analysis_state(") != 1:
        raise AssertionError(analysis)
    for forbidden in ("_load_theme_flow_read_payload", "board_fingerprint", "is_current_read"):
        if forbidden in analysis:
            raise AssertionError(f"analysis retained local read boundary: {forbidden}")
    for preserved in (
        'launch_background("refresh_board")',
        'launch_background("ai_read")',
        "load_theme_insider",
    ):
        if preserved not in source:
            raise AssertionError(f"preserved local boundary missing: {preserved}")


def main() -> int:
    tests = [
        test_theme_registries_project_strict_current_contracts_and_fail_soft,
        test_theme_clients_validate_urls_provenance_metadata_and_caps,
        test_theme_snapshot_state_distinguishes_every_outcome_once,
        test_snapshot_unavailable_and_failure_are_visible_without_local_fallback,
        test_only_artifact_unavailable_auto_launches_background_refresh,
        test_analysis_requires_current_board_and_distinguishes_failures,
        test_source_has_two_fixed_clients_no_selected_local_read_and_preserved_mutations,
    ]
    failures: list[tuple[str, BaseException]] = []
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except BaseException as exc:  # noqa: BLE001
            failures.append((test.__name__, exc))
            print(f"FAIL {test.__name__}: {exc}")
    if failures:
        print(f"{len(failures)} failed, {len(tests) - len(failures)} passed")
        return 1
    print(f"{len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
