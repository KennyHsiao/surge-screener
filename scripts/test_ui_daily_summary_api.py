#!/usr/bin/env python3
"""Focused contracts for the Phase 5V-5W Daily Summary API-only slice."""

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
    DAILY_SUMMARY_SOURCE_ID,
    ArtifactPathUnavailable,
    ArtifactSpec,
    ResolvedArtifactPath,
    read_artifact,
    resolve_latest_daily_summary,
)
from api.main import create_app  # noqa: E402
from api.models import (  # noqa: E402
    ArtifactAvailable,
    ArtifactUnavailable,
    DailySummaryData,
)
from ui import _read_api, today_decision  # noqa: E402


SOURCE_ID = "reports.daily-summary.latest"
ROUTE = "/api/v1/reports/daily-summary/latest"
URL = f"http://127.0.0.1:8000{ROUTE}"
ROOT_FIELDS = {"as_of_date", "regime_summary", "candidates"}
ROW_FIELDS = {"ticker", "verdict"}


def _source(
    report_date: str = "2026-08-01",
    *,
    populated: bool = True,
    include_watchlist: bool = False,
) -> dict[str, object]:
    ranked_picks: list[dict[str, object]] = []
    if populated:
        ranked_picks = [
            {
                "rank": 1,
                "ticker": "NVDA",
                "final_score": 87,
                "verdict": "STRONG_BUY",
                "thesis": "AI demand remains resilient.",
                "entry_zone": "165-170",
                "stop_loss": "158",
                "position_size_pct": 2.5,
                "key_risk": "Crowded positioning.",
            },
            {
                "rank": 2,
                "ticker": "MU",
                "final_score": 72.5,
                "verdict": "BUY",
                "thesis": "Memory pricing is improving.",
                "entry_zone": "130-135",
                "stop_loss": "124",
                "position_size_pct": 2,
                "key_risk": "Cyclical demand.",
            },
        ]
    payload: dict[str, object] = {
        "report_date": report_date,
        "regime_summary": "Constructive but selective risk-on regime.",
        "total_confirmed": len(ranked_picks),
        "ranked_picks": ranked_picks,
        "cross_candidate_commentary": "Avoid excess semiconductor concentration.",
        "portfolio_notes": "Scale only after confirmation.",
    }
    if include_watchlist:
        payload["watchlist_picks"] = [
            {
                "ticker": "AMD",
                "score": 61,
                "verdict": "WATCHLIST",
                "note": "Wait for volume confirmation.",
            }
        ]
    return payload


def _public(
    source: dict[str, object] | None = None,
) -> dict[str, object]:
    payload = source or _source()
    rows = payload["ranked_picks"]
    if not isinstance(rows, list):
        raise AssertionError(rows)
    return {
        "as_of_date": payload["report_date"],
        "regime_summary": payload["regime_summary"],
        "candidates": [
            {"ticker": row["ticker"], "verdict": row["verdict"]}
            for row in rows
            if isinstance(row, dict)
        ],
    }


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _spec(path: Path, as_of: str = "2026-08-01") -> ArtifactSpec:
    return replace(
        ARTIFACTS[SOURCE_ID],
        resolver=lambda: ResolvedArtifactPath(path, as_of=as_of),
    )


def _envelope(
    data: dict[str, object] | None,
    *,
    available: bool = True,
    reason: str = "ok",
    source_id: str = SOURCE_ID,
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


def test_latest_resolver_is_exact_fail_closed_and_date_bound() -> None:
    if DAILY_SUMMARY_SOURCE_ID != SOURCE_ID:
        raise AssertionError(DAILY_SUMMARY_SOURCE_ID)
    with tempfile.TemporaryDirectory() as tmp:
        missing_root = resolve_latest_daily_summary(Path(tmp) / "missing")
        if missing_root != ArtifactPathUnavailable("missing"):
            raise AssertionError(missing_root)
    with tempfile.TemporaryDirectory() as tmp:
        reports = Path(tmp)
        older = _write(reports / "2026-07-31" / "summary.json", _source("2026-07-31"))
        newest = _write(reports / "2026-08-01" / "summary.json", _source())
        _write(reports / "latest" / "summary.json", {"private": True})
        _write(reports / "2026-02-30" / "summary.json", {"private": True})
        resolved = resolve_latest_daily_summary(reports)
        if not isinstance(resolved, ResolvedArtifactPath):
            raise AssertionError(resolved)
        if resolved.path != newest or resolved.as_of != "2026-08-01":
            raise AssertionError(resolved)

        mismatch = _source("2026-07-31")
        _write(newest, mismatch)
        outcome = read_artifact(
            replace(ARTIFACTS[SOURCE_ID], resolver=lambda: resolved)
        )
        if not isinstance(outcome, ArtifactUnavailable) or outcome.reason != "invalid_shape":
            raise AssertionError(outcome)

        newest.unlink()
        missing = read_artifact(
            replace(
                ARTIFACTS[SOURCE_ID],
                resolver=lambda: resolve_latest_daily_summary(reports),
            )
        )
        if not isinstance(missing, ArtifactUnavailable) or missing.reason != "missing":
            raise AssertionError(missing)
        if older == newest:
            raise AssertionError("resolver unexpectedly fell back to the older summary")

    with tempfile.TemporaryDirectory() as tmp:
        reports = Path(tmp)
        _write(reports / "2026-07-31" / "summary.json", _source("2026-07-31"))
        (reports / "2026-08-01").write_text("not a directory", encoding="utf-8")
        invalid = resolve_latest_daily_summary(reports)
        if invalid != ArtifactPathUnavailable("unreadable"):
            raise AssertionError(invalid)

    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
        reports = Path(tmp)
        outside_summary = _write(
            Path(outside) / "summary.json", _source("2026-08-01")
        )
        (reports / "2026-08-01").symlink_to(Path(outside), target_is_directory=True)
        escaped_directory = resolve_latest_daily_summary(reports)
        if escaped_directory != ArtifactPathUnavailable("unreadable"):
            raise AssertionError(escaped_directory)
        (reports / "2026-08-01").unlink()
        selected = reports / "2026-08-01"
        selected.mkdir()
        (selected / "summary.json").symlink_to(outside_summary)
        escaped_file = resolve_latest_daily_summary(reports)
        if escaped_file != ArtifactPathUnavailable("unreadable"):
            raise AssertionError(escaped_file)


def test_source_variants_projection_and_public_invariants_are_strict() -> None:
    spec = ARTIFACTS[SOURCE_ID]
    if spec.data_model is not DailySummaryData:
        raise AssertionError(spec.data_model)
    if spec.data_validator is None or spec.data_projector is None:
        raise AssertionError(spec)
    if not spec.require_resolved_as_of_match:
        raise AssertionError("Daily Summary must bind source date to selected folder")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "summary.json"
        for source in (_source(), _source(include_watchlist=True), _source(populated=False)):
            outcome = read_artifact(_spec(_write(path, source)))
            if not isinstance(outcome, ArtifactAvailable):
                raise AssertionError(outcome)
            if outcome.data != _public(source):
                raise AssertionError(outcome.data)
            if set(outcome.data) != ROOT_FIELDS or any(
                set(row) != ROW_FIELDS for row in outcome.data["candidates"]
            ):
                raise AssertionError(outcome.data)
            serialized = json.dumps(outcome.data)
            for private in ("final_score", "thesis", "position_size_pct", "watchlist_picks"):
                if private in serialized:
                    raise AssertionError((private, serialized))

        source = _source()
        invalid_sources: list[dict[str, object]] = [{**source, "private": True}]
        wrong_total = deepcopy(source)
        wrong_total["total_confirmed"] = 99
        invalid_sources.append(wrong_total)
        wrong_rank = deepcopy(source)
        wrong_rank["ranked_picks"][0]["rank"] = 2  # type: ignore[index]
        invalid_sources.append(wrong_rank)
        duplicate = deepcopy(source)
        duplicate["ranked_picks"][1]["ticker"] = "NVDA"  # type: ignore[index]
        invalid_sources.append(duplicate)
        wrong_bool = deepcopy(source)
        wrong_bool["ranked_picks"][0]["final_score"] = True  # type: ignore[index]
        invalid_sources.append(wrong_bool)
        wrong_position = deepcopy(source)
        wrong_position["ranked_picks"][0]["position_size_pct"] = 101  # type: ignore[index]
        invalid_sources.append(wrong_position)
        wrong_score = deepcopy(source)
        wrong_score["ranked_picks"][0]["final_score"] = 101  # type: ignore[index]
        invalid_sources.append(wrong_score)
        wrong_ticker = deepcopy(source)
        wrong_ticker["ranked_picks"][0]["ticker"] = "nvda"  # type: ignore[index]
        invalid_sources.append(wrong_ticker)
        long_regime = deepcopy(source)
        long_regime["regime_summary"] = "x" * 1_001
        invalid_sources.append(long_regime)
        wrong_verdict = deepcopy(source)
        wrong_verdict["ranked_picks"][0]["verdict"] = "REJECT"  # type: ignore[index]
        invalid_sources.append(wrong_verdict)
        for invalid in invalid_sources:
            outcome = read_artifact(_spec(_write(path, invalid)))
            if not isinstance(outcome, ArtifactUnavailable) or outcome.reason != "invalid_shape":
                raise AssertionError(outcome)

    public = _public()
    public["candidates"][0]["private"] = True  # type: ignore[index]
    try:
        DailySummaryData.model_validate(public, strict=True)
    except ValueError:
        pass
    else:
        raise AssertionError("public DTO accepted a private field")


def test_route_openapi_and_fixed_client_are_strict_and_bounded() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _write(Path(tmp) / "summary.json", _source())
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
        "asOf": "2026-08-01",
        "generatedAt": None,
    }:
        raise AssertionError(payload)
    public = DailySummaryData.model_validate(payload["data"], strict=True)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return _response(_envelope(public.model_dump(mode="json")))

    outcome = _read_api.load_daily_summary(transport=httpx.MockTransport(handler))
    if outcome != _read_api.DailySummaryApiAvailable(public) or seen != [URL]:
        raise AssertionError((outcome, seen))
    unavailable = _read_api.load_daily_summary(
        transport=httpx.MockTransport(
            lambda _request: _response(
                _envelope(None, available=False, reason="missing", generated_at=None)
            )
        )
    )
    if unavailable != _read_api.DailySummaryApiUnavailable("missing"):
        raise AssertionError(unavailable)
    for invalid in (
        _envelope(public.model_dump(mode="json"), source_id="private.source"),
        _envelope(public.model_dump(mode="json"), as_of="2026-07-31"),
        _envelope(public.model_dump(mode="json"), generated_at="2026-08-01T00:00:00Z"),
    ):
        result = _read_api.load_daily_summary(
            transport=httpx.MockTransport(
                lambda _request, invalid=invalid: _response(invalid)
            )
        )
        if result != _read_api.DailySummaryApiFailure("invalid_envelope"):
            raise AssertionError(result)
    oversized = httpx.Response(
        200,
        headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        content=b"x" * (_read_api._DAILY_SUMMARY_MAX_RESPONSE_BYTES + 1),
    )
    capped = _read_api.load_daily_summary(
        transport=httpx.MockTransport(lambda _request: oversized)
    )
    if capped != _read_api.DailySummaryApiFailure("response_too_large"):
        raise AssertionError(capped)

    def transport_error(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private diagnostic")

    client_failures = (
        (
            httpx.MockTransport(transport_error),
            "transport_error",
        ),
        (
            httpx.MockTransport(lambda _request: httpx.Response(503)),
            "http_status",
        ),
        (
            httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    headers={
                        "Content-Type": "text/plain",
                        "Cache-Control": "no-store",
                    },
                    content=b"{}",
                )
            ),
            "invalid_media_type",
        ),
        (
            httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    headers={
                        "Content-Type": "application/json",
                        "Cache-Control": "max-age=60",
                    },
                    content=b"{}",
                )
            ),
            "invalid_cache_control",
        ),
        (
            httpx.MockTransport(lambda _request: _response({"private": True})),
            "invalid_envelope",
        ),
    )
    for transport, reason in client_failures:
        result = _read_api.load_daily_summary(transport=transport)
        if result != _read_api.DailySummaryApiFailure(reason):
            raise AssertionError((reason, result))
    with patch(
        "ui._read_api._request_daily_summary_with_deadline",
        new=AsyncMock(side_effect=asyncio.TimeoutError),
    ):
        deadline = _read_api.load_daily_summary()
    if deadline != _read_api.DailySummaryApiFailure("deadline_exceeded"):
        raise AssertionError(deadline)

    for reason in ("missing", "invalid_json", "invalid_shape", "unreadable"):
        result = _read_api.load_daily_summary(
            transport=httpx.MockTransport(
                lambda _request, reason=reason: _response(
                    _envelope(
                        None,
                        available=False,
                        reason=reason,
                        generated_at=None,
                    )
                )
            )
        )
        if result != _read_api.DailySummaryApiUnavailable(reason):
            raise AssertionError(result)

    static = yaml.safe_load(
        (ROOT / "docs/api/quant-radar-v1.openapi.yaml").read_text(encoding="utf-8")
    )
    for label, document in (("generated", generated), ("static", static)):
        if document["info"]["version"] != "1.23.0-draft":
            raise AssertionError((label, document["info"]))
        operation = document["paths"][ROUTE]["get"]
        if operation.get("operationId") != "getLatestDailySummary":
            raise AssertionError((label, operation))
        if operation.get("parameters"):
            raise AssertionError((label, operation["parameters"]))
        response_200 = operation["responses"]["200"]
        if "$ref" in response_200:
            response_200 = document["components"]["responses"][
                response_200["$ref"].rsplit("/", 1)[-1]
            ]
        examples = response_200["content"]["application/json"].get("examples", {})
        if set(examples) != {"available", "empty", "unavailable"}:
            raise AssertionError((label, examples))
        data_schema = document["components"]["schemas"]["DailySummaryData"]
        row_schema = document["components"]["schemas"]["DailySummaryCandidateRef"]
        if data_schema.get("additionalProperties") is not False or set(data_schema["properties"]) != ROOT_FIELDS:
            raise AssertionError((label, data_schema))
        if row_schema.get("additionalProperties") is not False or set(row_schema["properties"]) != ROW_FIELDS:
            raise AssertionError((label, row_schema))


def test_expected_file_states_are_fail_soft_and_recover_without_cache() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "summary.json"
        spec = _spec(path)
        missing = read_artifact(spec)
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


def test_today_reuses_one_daily_result_without_local_fallback() -> None:
    populated = DailySummaryData.model_validate(_public(), strict=True)
    empty = DailySummaryData.model_validate(
        _public(_source(populated=False)), strict=True
    )
    cases = (
        (
            _read_api.DailySummaryApiAvailable(populated),
            (
                "2026-08-01",
                {
                    "regime_summary": populated.regime_summary,
                    "ranked_picks": [
                        candidate.model_dump(mode="json")
                        for candidate in populated.candidates
                    ],
                },
            ),
        ),
        (
            _read_api.DailySummaryApiAvailable(empty),
            (
                "2026-08-01",
                {"regime_summary": empty.regime_summary, "ranked_picks": []},
            ),
        ),
        (_read_api.DailySummaryApiUnavailable("missing"), (None, None)),
        (_read_api.DailySummaryApiFailure("transport_error"), (None, None)),
    )
    for result, expected in cases:
        if today_decision._daily_summary_view(result) != expected:
            raise AssertionError((result, today_decision._daily_summary_view(result)))

    captured: list[tuple[str, int, object]] = []

    def gate(summary_date, summary, _thesis) -> None:
        captured.append(("gate", id(summary), summary_date))

    def opportunities(summary, _ranked, _scored) -> None:
        captured.append(("opportunities", id(summary), summary))

    wrapper = "from ui.today_decision import render\nrender()\n"
    with patch(
        "ui.today_decision._read_api.load_daily_summary",
        return_value=_read_api.DailySummaryApiAvailable(populated),
    ) as daily_loader, patch(
        "ui.today_decision._read_api.load_ranked_candidates",
        return_value=_read_api.RankedCandidatesApiUnavailable("missing"),
    ), patch(
        "ui.today_decision._read_api.load_scored_candidates",
        return_value=_read_api.ScoredCandidatesApiUnavailable("missing"),
    ), patch(
        "ui.today_decision._read_api.load_market_thesis",
        return_value=_read_api.MarketThesisApiUnavailable("missing"),
    ), patch(
        "ui.today_decision._candidate_controls.render"
    ), patch(
        "ui.today_decision._render_data_health_entry"
    ), patch(
        "ui.today_decision._render_trade_state_summary"
    ), patch(
        "ui.today_decision._render_candidate_results"
    ), patch(
        "ui.today_decision._render_gate",
        side_effect=gate,
    ), patch(
        "ui.today_decision._render_trust_boundary"
    ), patch(
        "ui.today_decision._render_opportunities",
        side_effect=opportunities,
    ), patch(
        "ui.today_decision._render_risk_and_research"
    ):
        app = AppTest.from_string(wrapper, default_timeout=10).run()
    if app.exception or daily_loader.call_count != 1:
        raise AssertionError((app.exception, daily_loader.call_count))
    if len(captured) != 2 or captured[0][1] != captured[1][1]:
        raise AssertionError(captured)
    if captured[0][2] != "2026-08-01":
        raise AssertionError(captured)
    summary = captured[1][2]
    if not isinstance(summary, dict) or summary["ranked_picks"][0] != {
        "ticker": "NVDA",
        "verdict": "STRONG_BUY",
    }:
        raise AssertionError(summary)

    source = (ROOT / "ui" / "today_decision.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="ui/today_decision.py", feature_version=(3, 10))
    render = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "render"
    )
    render_source = ast.get_source_segment(source, render) or ""
    if render_source.count("load_daily_summary()") != 1:
        raise AssertionError(render_source)
    for removed in (
        "_latest_daily_summary",
        "_load_object",
        "find_report_dates",
        '"summary.json"',
    ):
        if removed in source:
            raise AssertionError(f"Today retained local Daily Summary state: {removed}")


def test_outcomes_are_immutable_and_sources_are_python310_compatible() -> None:
    for outcome in (
        _read_api.DailySummaryApiUnavailable("missing"),
        _read_api.DailySummaryApiFailure("transport_error"),
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
        "scripts/test_ui_daily_summary_api.py",
    ):
        path = ROOT / relative
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 10))


def main() -> None:
    tests = (
        test_latest_resolver_is_exact_fail_closed_and_date_bound,
        test_source_variants_projection_and_public_invariants_are_strict,
        test_route_openapi_and_fixed_client_are_strict_and_bounded,
        test_expected_file_states_are_fail_soft_and_recover_without_cache,
        test_today_reuses_one_daily_result_without_local_fallback,
        test_outcomes_are_immutable_and_sources_are_python310_compatible,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
