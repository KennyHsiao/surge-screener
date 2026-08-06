#!/usr/bin/env python3
"""Focused contracts for Phase 4F ranked/scored candidate feeds."""

from __future__ import annotations

import ast
import json
import sys
import tempfile
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
    MarketThesisData,
    MarketThesisValidationData,
    OptionsFlowFeedData,
    OversoldReversalData,
    OversoldReversalValidationData,
    RankedCandidatesFeedData,
    ReversalRadarData,
    ReversalRadarValidationData,
    ScoredCandidatesFeedData,
)
from ui import _read_api, today_decision  # noqa: E402


RANKED_SOURCE_ID = "candidates.ranked.feed"
SCORED_SOURCE_ID = "candidates.scored.feed"
RANKED_ROUTE = "/api/v1/candidates/ranked/feed"
SCORED_ROUTE = "/api/v1/candidates/scored/feed"
RANKED_URL = f"http://127.0.0.1:8000{RANKED_ROUTE}"
SCORED_URL = f"http://127.0.0.1:8000{SCORED_ROUTE}"
RANKED_FIELDS = {"scan_date", "generated_at", "candidates"}
RANKED_ITEM_FIELDS = {
    "ticker",
    "rank_score",
    "last_price",
    "rank_bucket",
    "ret_5d",
    "ret_20d",
    "score_components",
    "options_tradability",
    "warnings",
}
RANKED_COMPONENT_FIELDS = {
    "technical_trend",
    "momentum_strength",
    "launch_signal",
    "liquidity_tradability",
    "overheat_risk_control",
}
RANKED_OPTIONS_FIELDS = {
    "status",
    "iv_percentile",
    "spread_pct",
    "flow_score",
    "warnings",
}
SCORED_FIELDS = {"scan_date", "candidates"}
SCORED_ITEM_FIELDS = {
    "ticker",
    "verdict",
    "composite_score",
    "regime_adjusted_score",
    "scores",
    "data_missing",
    "due_diligence_required",
    "key_signals",
    "key_risks",
    "suggested_entry_zone",
}
SCORE_FIELDS = {
    "technical",
    "catalyst",
    "sentiment",
    "institutional",
    "sector_market",
    "options_flow",
    "analyst",
}


def _options_flow_feed(*, populated: bool) -> OptionsFlowFeedData:
    signals = []
    if populated:
        signals = [
            {
                "ticker": "NVDA",
                "direction": "bullish",
                "flow_score": 82.0,
                "est_notional_usd": 12_500_000,
                "biggest": None,
                "expiry": None,
                "max_voi": 7.2,
                "high_voi_strikes": 3,
                "call_put_ratio": 1.8,
                "put_call_ratio": None,
                "tags": ["sweep", "high conviction"],
            }
        ]
    return OptionsFlowFeedData.model_validate(
        {
            "generated_at": "2026-08-05T01:02:03Z",
            "as_of": "2026-08-05",
            "provider": "phase5t_test",
            "universe_size": 1,
            "min_notional": 1_000_000,
            "signal_count": len(signals),
            "signals": signals,
        }
    )


def _reversal_snapshot() -> ReversalRadarData:
    return ReversalRadarData.model_validate(
        {
            "as_of_date": "2026-08-05",
            "generated_at": "2026-08-05T01:02:03Z",
            "lane_id": "reversal_radar.v1",
            "universe": "us_options",
            "match_count": 1,
            "candidates": [{"ticker": "NVDA"}],
        }
    )


def _oversold_empty_snapshot() -> OversoldReversalData:
    return OversoldReversalData.model_validate(
        {
            "as_of_date": "2026-08-05",
            "generated_at": "2026-08-05T01:02:03Z",
            "lane_id": "oversold_reversal.v1",
            "universe": "us_options",
            "runway_independent": True,
            "match_count": 0,
            "scanned": 100,
            "definition": "phase5s empty fixture",
            "validation": {
                "pct_lift": 0.0,
                "atr_neutral_lift": 0.0,
                "support": 0,
            },
            "validation_caveats": [],
            "candidates": [],
            "note": "",
        }
    )


def _ranked_row(
    ticker: str,
    score: float,
    *,
    options: bool = True,
) -> dict[str, object]:
    row: dict[str, object] = {
        "ticker": ticker,
        "rank_score": score,
        "last_price": 100.0,
        "rank_bucket": "priority" if score >= 80 else "candidate",
        "ret_5d": 3.2,
        "ret_20d": 9.4,
        "score_components": {
            "technical_trend": 23.0,
            "momentum_strength": 16.0,
            "launch_signal": 11.0,
            "liquidity_tradability": 17.0,
            "overheat_risk_control": 15.0,
            "large_order_flow_confirmation": 0.0,
        },
        "warnings": ["source-only warning"],
        "atr14": 2.5,
        "money_flow_evidence": {"private": True},
    }
    if options:
        row["options_tradability"] = {
            "status": "watch",
            "iv_percentile": 72.8,
            "spread_pct": 108.7,
            "flow_score": -3.0,
            "warnings": ["IV percentile is proxy"],
            "open_interest": 42,
            "data_missing": ["sweeps"],
        }
    return row


def _ranked_source(**overrides: object) -> dict[str, object]:
    rows = [_ranked_row("AMD", 75.0, options=False), _ranked_row("NVDA", 82.0)]
    payload: dict[str, object] = {
        "all_ranked_count": 2,
        "as_of_date": "2026-08-01",
        "generated_at": "2026-08-01T02:03:04.123456+00:00",
        "markets": ["US"],
        "money_flow_scoring": {"enabled": True},
        "options_gate": {"enabled": True},
        "passed_hard_filters": 2,
        "rank_buckets": {"priority": 1, "candidate": 1},
        "rank_limit": 50,
        "ranked_candidates": rows,
        "ranked_candidates_count": 2,
        "scan_date": "2026-08-01",
        "score_weights": {"technical": 0.3},
        "scoring_model": "deterministic",
        "source": "hard_filter",
        "tickers": rows,
        "total_candidates": 2,
        "total_universe": 100,
        "universe": "US",
    }
    payload.update(overrides)
    return payload


def _scored_row(
    ticker: str,
    score: float,
    verdict: str = "WATCHLIST",
) -> dict[str, object]:
    return {
        "ticker": ticker,
        "verdict": verdict,
        "composite_score": score,
        "regime_adjusted_score": score,
        "scores": {
            "technical": 25.0,
            "catalyst": 7.0,
            "sentiment": 4.0,
            "institutional": 3.0,
            "sector_market": 5.0,
            "options_flow": 8.0,
            "analyst": None,
        },
        "data_missing": ["analyst"],
        "due_diligence_required": True,
        "key_signals": ["technical alignment"],
        "key_risks": ["missing analyst context"],
        "suggested_entry_zone": "$95-$100",
        "suggested_stop": "$90",
        "suggested_size_pct": 2.0,
        "technical_breakdown": {"private": True},
        "anti_example_warning": "private",
    }


def _scored_source(**overrides: object) -> dict[str, object]:
    priority = _scored_row("NVDA", 84.0, "NEEDS_LAYER_2")
    payload: dict[str, object] = {
        "all_scored": [
            _scored_row("AMD", 75.0),
            _scored_row("NVDA", 10.0, "REJECT"),
        ],
        "min_score_threshold": 65,
        "needs_layer2": [priority],
        "needs_layer2_count": 1,
        "passed_hard_filters": 2,
        "regime_context": {"private": True},
        "rejected_count": 0,
        "remaining_unscored": 0,
        "scan_date": "2026-08-01",
        "scored_candidates_count": 2,
        "total_candidates": 2,
        "universe_size": 100,
        "watchlist": [_scored_row("AMD", 75.0)],
        "watchlist_count": 1,
    }
    payload.update(overrides)
    return payload


def _write(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _spec(source_id: str, path: Path) -> ArtifactSpec:
    return replace(
        ARTIFACTS[source_id],
        resolver=lambda: ResolvedArtifactPath(path),
    )


def _candidate_feed_results() -> tuple[ArtifactAvailable, ArtifactAvailable]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ranked = read_artifact(_spec(
            RANKED_SOURCE_ID, _write(root / "ranked.json", _ranked_source()),
        ))
        scored = read_artifact(_spec(
            SCORED_SOURCE_ID, _write(root / "scored.json", _scored_source()),
        ))
    if not isinstance(ranked, ArtifactAvailable):
        raise AssertionError(ranked)
    if not isinstance(scored, ArtifactAvailable):
        raise AssertionError(scored)
    return ranked, scored


def _client(registry: dict[str, ArtifactSpec]) -> TestClient:
    target = create_app(registry)

    async def with_loopback(scope, receive, send):
        if scope["type"] == "http":
            scope = {**scope, "client": ("127.0.0.1", 50000)}
        await target(scope, receive, send)

    return TestClient(with_loopback, base_url="http://127.0.0.1")


def _http_response(payload: object) -> httpx.Response:
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


def test_registry_projects_strict_bounded_normalized_feeds() -> None:
    if ARTIFACTS[RANKED_SOURCE_ID].data_model is not RankedCandidatesFeedData:
        raise AssertionError(ARTIFACTS[RANKED_SOURCE_ID])
    if ARTIFACTS[SCORED_SOURCE_ID].data_model is not ScoredCandidatesFeedData:
        raise AssertionError(ARTIFACTS[SCORED_SOURCE_ID])

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ranked = read_artifact(
            _spec(RANKED_SOURCE_ID, _write(root / "ranked.json", _ranked_source()))
        )
        scored = read_artifact(
            _spec(SCORED_SOURCE_ID, _write(root / "scored.json", _scored_source()))
        )
        scored_current = read_artifact(
            _spec(
                SCORED_SOURCE_ID,
                _write(
                    root / "scored-current.json",
                    _scored_source(generated_at="2026-08-01T02:03:04Z"),
                ),
            )
        )

    if not isinstance(ranked, ArtifactAvailable) or set(ranked.data) != RANKED_FIELDS:
        raise AssertionError(ranked)
    if [row["ticker"] for row in ranked.data["candidates"]] != ["NVDA", "AMD"]:
        raise AssertionError(ranked.data)
    for row in ranked.data["candidates"]:
        if set(row) != RANKED_ITEM_FIELDS:
            raise AssertionError(row)
        if set(row["score_components"]) != RANKED_COMPONENT_FIELDS:
            raise AssertionError(row)
        if row["options_tradability"] is not None:
            if set(row["options_tradability"]) != RANKED_OPTIONS_FIELDS:
                raise AssertionError(row)

    if not isinstance(scored, ArtifactAvailable) or set(scored.data) != SCORED_FIELDS:
        raise AssertionError(scored)
    if not isinstance(scored_current, ArtifactAvailable):
        raise AssertionError("current producer root must remain feed-compatible")
    if scored_current.data != scored.data:
        raise AssertionError("private generated_at changed the public scored feed")
    if [row["ticker"] for row in scored.data["candidates"]] != ["NVDA", "AMD"]:
        raise AssertionError(scored.data)
    if scored.data["candidates"][0]["verdict"] != "NEEDS_LAYER_2":
        raise AssertionError("bucket-priority deduplication was not preserved")
    for row in scored.data["candidates"]:
        if set(row) != SCORED_ITEM_FIELDS or set(row["scores"]) != SCORE_FIELDS:
            raise AssertionError(row)
    rendered = json.dumps(scored.data)
    for private in ("suggested_stop", "suggested_size_pct", "technical_breakdown", "anti_example"):
        if private in rendered:
            raise AssertionError(private)


def test_invalid_sources_and_public_invariants_fail_soft() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ranked_extra = _ranked_source(private_root=True)
        scored_bad = _scored_source(scan_date="2026-02-30")
        scored_bad_timestamp = _scored_source(generated_at="2026-08-01T02:03:04")
        scored_extra = _scored_source(private_root=True)
        outcomes = (
            read_artifact(
                _spec(RANKED_SOURCE_ID, _write(root / "ranked.json", ranked_extra))
            ),
            read_artifact(
                _spec(SCORED_SOURCE_ID, _write(root / "scored.json", scored_bad))
            ),
            read_artifact(
                _spec(
                    SCORED_SOURCE_ID,
                    _write(root / "scored-time.json", scored_bad_timestamp),
                )
            ),
            read_artifact(
                _spec(
                    SCORED_SOURCE_ID,
                    _write(root / "scored-extra.json", scored_extra),
                )
            ),
        )
    for outcome in outcomes:
        if not isinstance(outcome, ArtifactUnavailable) or outcome.reason != "invalid_shape":
            raise AssertionError(outcome)

    ranked_row = _ranked_row("NVDA", 82.0)
    ranked = RankedCandidatesFeedData.model_validate(
        {
            "scan_date": "2026-08-01",
            "generated_at": "2026-08-01T02:03:04.123456+00:00",
            "candidates": [
                {
                    **{
                        key: value
                        for key, value in ranked_row.items()
                        if key in RANKED_ITEM_FIELDS
                    },
                    "score_components": {
                        key: ranked_row["score_components"][key]
                        for key in RANKED_COMPONENT_FIELDS
                    },
                    "options_tradability": None,
                }
            ],
        }
    )
    drifted = ranked.model_dump()
    drifted["candidates"][0]["private"] = True
    try:
        RankedCandidatesFeedData.model_validate(drifted)
    except ValueError:
        pass
    else:
        raise AssertionError("strict public DTO accepted an extra field")


def test_feed_routes_are_additive_and_compatibility_routes_are_preserved() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        ranked_path = _write(root / "ranked.json", _ranked_source())
        scored_path = _write(root / "scored.json", _scored_source())
        registry = dict(ARTIFACTS)
        for source_id, path in (
            ("candidates.ranked", ranked_path),
            (RANKED_SOURCE_ID, ranked_path),
            ("candidates.scored", scored_path),
            (SCORED_SOURCE_ID, scored_path),
        ):
            registry[source_id] = replace(
                registry[source_id], resolver=lambda path=path: ResolvedArtifactPath(path)
            )
        client = _client(registry)
        ranked_feed = client.get(RANKED_ROUTE)
        scored_feed = client.get(SCORED_ROUTE)
        ranked_compat = client.get("/api/v1/candidates/ranked")
        scored_compat = client.get("/api/v1/candidates/scored")

    for response in (ranked_feed, scored_feed, ranked_compat, scored_compat):
        if response.status_code != 200 or response.headers.get("cache-control") != "no-store":
            raise AssertionError(response.text)
    if set(ranked_feed.json()["data"]) != RANKED_FIELDS:
        raise AssertionError(ranked_feed.json())
    if set(scored_feed.json()["data"]) != SCORED_FIELDS:
        raise AssertionError(scored_feed.json())
    if "scoring_model" not in ranked_compat.json()["data"]:
        raise AssertionError("ranked compatibility route was narrowed")
    if "regime_context" not in scored_compat.json()["data"]:
        raise AssertionError("scored compatibility route was narrowed")


def test_fixed_clients_validate_urls_provenance_unavailable_and_caps() -> None:
    ranked_public, scored_public = _candidate_feed_results()
    payloads = {
        RANKED_URL: _envelope(
            RANKED_SOURCE_ID,
            ranked_public.data,
            as_of=ranked_public.data["scan_date"],
            generated_at=ranked_public.data["generated_at"],
        ),
        SCORED_URL: _envelope(
            SCORED_SOURCE_ID,
            scored_public.data,
            as_of=scored_public.data["scan_date"],
        ),
    }
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return _http_response(payloads[str(request.url)])

    transport = httpx.MockTransport(handler)
    ranked = _read_api.load_ranked_candidates(transport=transport)
    scored = _read_api.load_scored_candidates(transport=transport)
    if not isinstance(ranked, _read_api.RankedCandidatesApiAvailable):
        raise AssertionError(ranked)
    if not isinstance(scored, _read_api.ScoredCandidatesApiAvailable):
        raise AssertionError(scored)
    if seen != [RANKED_URL, SCORED_URL]:
        raise AssertionError(seen)

    unavailable = _read_api.load_scored_candidates(
        transport=httpx.MockTransport(
            lambda _request: _http_response(
                _envelope(
                    SCORED_SOURCE_ID,
                    None,
                    available=False,
                    reason="missing",
                    as_of=None,
                )
            )
        )
    )
    if unavailable != _read_api.ScoredCandidatesApiUnavailable("missing"):
        raise AssertionError(unavailable)

    wrong_meta = _read_api.load_ranked_candidates(
        transport=httpx.MockTransport(
            lambda _request: _http_response(
                _envelope(
                    RANKED_SOURCE_ID,
                    ranked_public.data,
                    as_of="2026-07-31",
                    generated_at=ranked_public.data["generated_at"],
                )
            )
        )
    )
    if wrong_meta != _read_api.RankedCandidatesApiFailure("invalid_envelope"):
        raise AssertionError(wrong_meta)

    for loader, failure_type, cap in (
        (
            _read_api.load_ranked_candidates,
            _read_api.RankedCandidatesApiFailure,
            _read_api._RANKED_CANDIDATES_MAX_RESPONSE_BYTES,
        ),
        (
            _read_api.load_scored_candidates,
            _read_api.ScoredCandidatesApiFailure,
            _read_api._SCORED_CANDIDATES_MAX_RESPONSE_BYTES,
        ),
    ):
        oversized = httpx.Response(
            200,
            headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
            content=b"x" * (cap + 1),
        )
        result = loader(transport=httpx.MockTransport(lambda _request: oversized))
        if result != failure_type("response_too_large"):
            raise AssertionError(result)


def test_today_decision_uses_one_api_result_each_without_local_fallback() -> None:
    ranked_result, scored_result = _candidate_feed_results()
    thesis_result = read_artifact(
        ARTIFACTS["market-context.market-thesis.latest"]
    )
    if not isinstance(thesis_result, ArtifactAvailable):
        raise AssertionError(thesis_result)
    ranked_feed = RankedCandidatesFeedData.model_validate(ranked_result.data)
    scored_feed = ScoredCandidatesFeedData.model_validate(scored_result.data)
    thesis = MarketThesisData.model_validate(thesis_result.data)
    if today_decision._market_thesis_view(
        _read_api.MarketThesisApiAvailable(thesis)
    ) != thesis.model_dump(mode="json"):
        raise AssertionError("Today did not preserve the strict Market Thesis DTO")
    for result in (
        *(
            _read_api.MarketThesisApiUnavailable(reason)
            for reason in ("missing", "invalid_json", "invalid_shape", "unreadable")
        ),
        *(
            _read_api.MarketThesisApiFailure(reason)
            for reason in (
                "transport_error",
                "deadline_exceeded",
                "http_status",
                "invalid_media_type",
                "invalid_cache_control",
                "response_too_large",
                "invalid_envelope",
            )
        ),
    ):
        if today_decision._market_thesis_view(result) is not None:
            raise AssertionError(result)
    captured: list[tuple[str, int, int]] = []
    gate_theses: list[dict | None] = []

    def candidate_results(
        ranked_rows,
        scored_rows,
        *,
        ranked_available,
        scored_available,
    ) -> None:
        if not ranked_available or not scored_available:
            raise AssertionError((ranked_available, scored_available))
        captured.append(("results", id(ranked_rows), id(scored_rows)))

    def opportunities(_summary, ranked_rows, scored_rows) -> None:
        captured.append(("opportunities", id(ranked_rows), id(scored_rows)))

    def gate(_summary_date, _summary, forecast) -> None:
        gate_theses.append(forecast)

    wrapper = "from ui.today_decision import render\nrender()\n"
    with patch(
        "ui.today_decision._read_api.load_ranked_candidates",
        return_value=_read_api.RankedCandidatesApiAvailable(ranked_feed),
    ) as ranked_loader, patch(
        "ui.today_decision._read_api.load_scored_candidates",
        return_value=_read_api.ScoredCandidatesApiAvailable(scored_feed),
    ) as scored_loader, patch(
        "ui.today_decision._candidate_controls.render"
    ), patch(
        "ui.today_decision._render_data_health_entry"
    ), patch(
        "ui.today_decision._render_trade_state_summary"
    ), patch(
        "ui.today_decision._render_candidate_results",
        side_effect=candidate_results,
    ), patch(
        "ui.today_decision._read_api.load_daily_summary",
        return_value=_read_api.DailySummaryApiUnavailable("missing"),
    ), patch(
        "ui.today_decision._read_api.load_market_thesis",
        return_value=_read_api.MarketThesisApiAvailable(thesis),
    ) as thesis_loader, patch(
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
    if app.exception:
        raise AssertionError(app.exception)
    if ranked_loader.call_count != 1 or scored_loader.call_count != 1:
        raise AssertionError((ranked_loader.call_count, scored_loader.call_count))
    if thesis_loader.call_count != 1:
        raise AssertionError(thesis_loader.call_count)
    if gate_theses != [thesis.model_dump(mode="json")]:
        raise AssertionError(gate_theses)
    if len(captured) != 2 or captured[0][1:] != captured[1][1:]:
        raise AssertionError(captured)

    source = (ROOT / "ui" / "today_decision.py").read_text(encoding="utf-8")
    if 'candidate_output_path("ranked_candidates.json")' in source:
        raise AssertionError("Today Decision retained a local ranked read")
    if 'candidate_output_path("scored_candidates.json")' in source:
        raise AssertionError("Today Decision retained a local scored read")
    tree = ast.parse(source, filename="ui/today_decision.py", feature_version=(3, 10))
    render = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "render"
    )
    render_source = ast.get_source_segment(source, render) or ""
    if render_source.count("load_ranked_candidates()") != 1:
        raise AssertionError(render_source)
    if render_source.count("load_scored_candidates()") != 1:
        raise AssertionError(render_source)
    if render_source.count("load_market_thesis()") != 1:
        raise AssertionError(render_source)
    for removed in (
        "_latest_market_thesis",
        "_MARKET_THESIS_DIR",
        "*forecast_*.json",
    ):
        if removed in source:
            raise AssertionError(
                f"Today Decision retained local Market Thesis source: {removed}"
            )


def test_today_decision_english_detail_detection_uses_only_public_text() -> None:
    from ui import today_decision

    if not today_decision._has_english_llm_detail(
        [
            {
                "key_signals": ["Strong catalyst confirmed"],
                "key_risks": ["風險仍待確認"],
                "suggested_entry_zone": "等待回測",
            }
        ]
    ):
        raise AssertionError("English key signal was not detected")
    if today_decision._has_english_llm_detail(
        [
            {
                "key_signals": ["催化事件已確認"],
                "key_risks": ["風險仍待確認"],
                "suggested_entry_zone": "等待回測",
                "suggested_stop": "Legacy private stop text",
            }
        ]
    ):
        raise AssertionError("private suggested_stop must not drive public UI state")


def test_today_decision_distinguishes_available_empty_from_unavailable() -> None:
    available_app = AppTest.from_string(
        "from ui.today_decision import _render_candidate_results\n"
        "_render_candidate_results([], [], ranked_available=True, scored_available=True)\n",
        default_timeout=10,
    ).run()
    unavailable_app = AppTest.from_string(
        "from ui.today_decision import _render_candidate_results\n"
        "_render_candidate_results([], [], ranked_available=False, scored_available=False)\n",
        default_timeout=10,
    ).run()
    if available_app.exception or unavailable_app.exception:
        raise AssertionError((available_app.exception, unavailable_app.exception))
    available_info = "\n".join(str(item.value) for item in available_app.info)
    unavailable_warning = "\n".join(
        str(item.value) for item in unavailable_app.warning
    )
    if "API 目前沒有資料" not in available_info:
        raise AssertionError(available_info)
    if "API 暫時無法提供資料；不會改讀本機檔案" not in unavailable_warning:
        raise AssertionError(unavailable_warning)


def test_today_decision_validation_trust_cards_are_api_only() -> None:
    market_validation = MarketThesisValidationData.model_validate(
        {
            "validation_status": "ok",
            "resolved": 12,
            "matured": 9,
            "min_resolved_for_verdict": 100,
            "reject_count": 0,
            "invalid_count": 0,
            "by_key": {},
        }
    )
    reversal_validation = ReversalRadarValidationData.model_validate(
        {
            "entries_accumulated": 7,
            "min_resolved_across_tiers": 3,
            "min_resolved_for_verdict": 100,
            "verdict": "PROVISIONAL — sample below threshold, indicative only",
            "by_tier": {
                tier: {
                    "resolved": resolved,
                    "hits": 0,
                    "hit_rate": 0.0,
                    "wilson90": [0.0, 1.0],
                }
                for tier, resolved in (
                    ("+10%/20d", 5),
                    ("+15%/40d", 4),
                    ("+20%/60d", 3),
                )
            },
        }
    )
    oversold_validation = OversoldReversalValidationData.model_validate(
        {
            "entries_accumulated": 8,
            "min_resolved_across_tiers": 4,
            "min_resolved_for_verdict": 100,
            "verdict": "PROVISIONAL — sample below threshold, indicative only",
            "by_tier": {
                tier: {
                    "resolved": resolved,
                    "hits": 0,
                    "hit_rate": 0.0,
                    "wilson90": [0.0, 1.0],
                }
                for tier, resolved in (
                    ("+30%/20d", 6),
                    ("+40%/40d", 5),
                    ("+50%/60d", 4),
                )
            },
        }
    )

    wrapper = (
        "from ui.today_decision import _render_trust_boundary\n"
        "_render_trust_boundary()\n"
    )
    with patch(
        "ui.today_decision._read_api.load_market_thesis_validation",
        return_value=_read_api.MarketThesisValidationApiAvailable(
            market_validation
        ),
    ) as market_loader, patch(
        "ui.today_decision._read_api.load_reversal_radar_validation",
        return_value=_read_api.ReversalRadarValidationApiAvailable(
            reversal_validation
        ),
    ) as reversal_loader, patch(
        "ui.today_decision._read_api.load_oversold_reversal_validation",
        return_value=_read_api.OversoldReversalValidationApiAvailable(
            oversold_validation
        ),
    ) as oversold_loader:
        app = AppTest.from_string(wrapper, default_timeout=10).run()
    call_counts = (
        market_loader.call_count,
        reversal_loader.call_count,
        oversold_loader.call_count,
    )
    if app.exception or call_counts != (1, 1, 1):
        raise AssertionError((app.exception, call_counts))
    rendered = "\n".join(
        str(item.value)
        for collection in (app.metric, app.caption)
        for item in collection
    )
    for expected in (
        "9/100",
        "3/100",
        "4/100",
        "已解決 12 筆",
        "7 筆累積",
        "8 筆累積",
    ):
        if expected not in rendered:
            raise AssertionError((expected, rendered))

    cases = (
        (
            "load_market_thesis_validation",
            _read_api.MarketThesisValidationApiUnavailable,
            _read_api.MarketThesisValidationApiFailure,
        ),
        (
            "load_reversal_radar_validation",
            _read_api.ReversalRadarValidationApiUnavailable,
            _read_api.ReversalRadarValidationApiFailure,
        ),
        (
            "load_oversold_reversal_validation",
            _read_api.OversoldReversalValidationApiUnavailable,
            _read_api.OversoldReversalValidationApiFailure,
        ),
    )
    for attribute, unavailable_type, failure_type in cases:
        failures = (
            unavailable_type("missing"),
            *(
                failure_type(reason)
                for reason in (
                    "transport_error",
                    "deadline_exceeded",
                    "http_status",
                    "invalid_media_type",
                    "invalid_cache_control",
                    "response_too_large",
                    "invalid_envelope",
                )
            ),
        )
        for result in failures:
            with patch(
                f"ui.today_decision._read_api.{attribute}",
                return_value=result,
            ) as loader:
                unavailable_app = AppTest.from_string(
                    wrapper, default_timeout=10
                ).run()
            if unavailable_app.exception or loader.call_count != 1:
                raise AssertionError(
                    (result, unavailable_app.exception, loader.call_count)
                )
            text = "\n".join(
                str(item.value) for item in unavailable_app.caption
            )
            if "API 暫無驗證摘要" not in text or result.reason in text:
                raise AssertionError((result, text))

    source = (ROOT / "ui" / "today_decision.py").read_text(encoding="utf-8")
    trust_source = source.split("def _render_trust_boundary", 1)[1].split(
        "def _ranked_result_df", 1
    )[0]
    if trust_source.count("load_market_thesis_validation()") != 1:
        raise AssertionError(trust_source)
    if trust_source.count("load_reversal_radar_validation()") != 1:
        raise AssertionError(trust_source)
    if trust_source.count("load_oversold_reversal_validation()") != 1:
        raise AssertionError(trust_source)
    if "_local_validation_summary" in source or "validation_summary.json" in source:
        raise AssertionError("Today Decision retained a local validation read")


def test_today_decision_latest_candidate_counts_are_api_only() -> None:
    reversal_available = _read_api.ReversalRadarApiAvailable(_reversal_snapshot())
    oversold_available = _read_api.OversoldReversalApiAvailable(
        _oversold_empty_snapshot()
    )
    wrapper = (
        "from ui.today_decision import _render_risk_and_research\n"
        "_render_risk_and_research()\n"
    )

    def render_counts(reversal_result, oversold_result):
        captured: list[tuple[str, object]] = []
        with patch(
            "ui.today_decision._read_api.load_reversal_radar",
            return_value=reversal_result,
        ) as reversal_loader, patch(
            "ui.today_decision._read_api.load_oversold_reversal",
            return_value=oversold_result,
        ) as oversold_loader, patch(
            "ui.today_decision._shared.load_reconciliation",
            return_value={
                "matched": [{"ticker": "NVDA"}],
                "held_not_in_ledger": [],
            },
        ) as reconciliation_loader, patch(
            "ui.today_decision._shared.load_ledger",
            return_value=[{"ticker": "NVDA"}, {"ticker": "AMD"}],
        ) as ledger_loader, patch(
            "ui.today_decision._shared.metric_card",
            side_effect=lambda _col, label, value, **_kwargs: captured.append(
                (label, value)
            ),
        ), patch("ui.today_decision._jump"):
            app = AppTest.from_string(wrapper, default_timeout=10).run()
        counts = (reversal_loader.call_count, oversold_loader.call_count)
        sibling_counts = (
            reconciliation_loader.call_count,
            ledger_loader.call_count,
        )
        if app.exception or counts != (1, 1) or sibling_counts != (1, 1):
            raise AssertionError(
                (app.exception, counts, sibling_counts, captured)
            )
        return dict(captured)

    available_metrics = render_counts(reversal_available, oversold_available)
    if available_metrics != {
        "IBKR 底層": 1,
        "反轉候選": 1,
        "蓄勢候選": 0,
        "Ledger 筆數": 2,
    }:
        raise AssertionError(available_metrics)

    failure_reasons = (
        "transport_error",
        "deadline_exceeded",
        "http_status",
        "invalid_media_type",
        "invalid_cache_control",
        "response_too_large",
        "invalid_envelope",
    )
    reversal_failures = (
        _read_api.ReversalRadarApiUnavailable("missing"),
        *(_read_api.ReversalRadarApiFailure(reason) for reason in failure_reasons),
    )
    for result in reversal_failures:
        metrics = render_counts(result, oversold_available)
        if metrics["反轉候選"] != "-" or result.reason in str(metrics):
            raise AssertionError((result, metrics))

    oversold_failures = (
        _read_api.OversoldReversalApiUnavailable("missing"),
        *(_read_api.OversoldReversalApiFailure(reason) for reason in failure_reasons),
    )
    for result in oversold_failures:
        metrics = render_counts(reversal_available, result)
        if metrics["蓄勢候選"] != "-" or result.reason in str(metrics):
            raise AssertionError((result, metrics))


def test_today_decision_options_flow_table_is_api_only() -> None:
    wrapper = (
        "from ui.today_decision import _render_opportunities\n"
        "_render_opportunities(None, [], [])\n"
    )

    def render_flow(result):
        with patch(
            "ui.today_decision._read_api.load_options_flow",
            return_value=result,
        ) as loader, patch(
            "ui.today_decision._shared.ticker_action_buttons"
        ) as actions, patch("ui.today_decision._jump"):
            app = AppTest.from_string(wrapper, default_timeout=10).run()
        if app.exception or loader.call_count != 1:
            raise AssertionError((result, app.exception, loader.call_count))
        return app, actions

    populated_app, actions = render_flow(
        _read_api.OptionsFlowApiAvailable(_options_flow_feed(populated=True))
    )
    if actions.call_args_list != [(('NVDA', 'td_flow'), {})]:
        raise AssertionError(actions.call_args_list)
    if len(populated_app.dataframe) != 1:
        raise AssertionError(populated_app.dataframe)
    frame = populated_app.dataframe[0].value
    if list(frame.columns) != [
        "代號",
        "方向",
        "熱度",
        "估權利金",
        "V/OI峰值",
        "標籤",
    ]:
        raise AssertionError(frame)
    first = frame.iloc[0].to_dict()
    if first != {
        "代號": "NVDA",
        "方向": "偏多",
        "熱度": 82.0,
        "估權利金": "$12.5M",
        "V/OI峰值": 7.2,
        "標籤": "sweep · high conviction",
    }:
        raise AssertionError(first)

    empty_app, empty_actions = render_flow(
        _read_api.OptionsFlowApiAvailable(_options_flow_feed(populated=False))
    )
    empty_text = "\n".join(str(item.value) for item in empty_app.info)
    if "Options Flow API 目前沒有訊號" not in empty_text or empty_actions.called:
        raise AssertionError((empty_text, empty_actions.call_args_list))

    failures = (
        _read_api.OptionsFlowApiUnavailable("missing"),
        *(
            _read_api.OptionsFlowApiFailure(reason)
            for reason in (
                "transport_error",
                "deadline_exceeded",
                "http_status",
                "invalid_media_type",
                "invalid_cache_control",
                "response_too_large",
                "invalid_envelope",
            )
        ),
    )
    for result in failures:
        app, failure_actions = render_flow(result)
        text = "\n".join(str(item.value) for item in app.info)
        if (
            "Options Flow API 暫時無法提供資料；不會改讀本機檔案" not in text
            or result.reason in text
            or failure_actions.called
        ):
            raise AssertionError((result, text, failure_actions.call_args_list))

    source = (ROOT / "ui" / "today_decision.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="ui/today_decision.py", feature_version=(3, 10))
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    if functions["_render_opportunities"].count("load_options_flow()") != 1:
        raise AssertionError(functions["_render_opportunities"])
    if functions["_render_risk_and_research"].count("load_reversal_radar()") != 1:
        raise AssertionError(functions["_render_risk_and_research"])
    if functions["_render_risk_and_research"].count("load_oversold_reversal()") != 1:
        raise AssertionError(functions["_render_risk_and_research"])
    for removed in (
        "_flow_signals",
        "_FLOW_DIR",
        "_REVERSAL_DIR",
        "_OVERSOLD_DIR",
        "options_flow/latest.json",
    ):
        if removed in source:
            raise AssertionError(f"Today Decision retained selected local source: {removed}")
    for preserved in (
        "load_daily_summary()",
        "load_market_thesis()",
        "_shared.load_reconciliation()",
        "_shared.load_ledger()",
        "trade_state_engine.build_trade_state_rows",
        "_candidate_controls.render()",
    ):
        if preserved not in source:
            raise AssertionError(f"Today Decision removed retained sibling: {preserved}")


def test_outcomes_are_immutable_and_sources_are_python310_compatible() -> None:
    ranked_result, scored_result = _candidate_feed_results()
    ranked = RankedCandidatesFeedData.model_validate(ranked_result.data)
    scored = ScoredCandidatesFeedData.model_validate(scored_result.data)
    outcomes = (
        (_read_api.RankedCandidatesApiAvailable(ranked), "feed", ranked),
        (_read_api.RankedCandidatesApiUnavailable("missing"), "reason", "unreadable"),
        (_read_api.RankedCandidatesApiFailure("transport_error"), "reason", "http_status"),
        (_read_api.ScoredCandidatesApiAvailable(scored), "feed", scored),
        (_read_api.ScoredCandidatesApiUnavailable("missing"), "reason", "unreadable"),
        (_read_api.ScoredCandidatesApiFailure("transport_error"), "reason", "http_status"),
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
        "ui/today_decision.py",
        "scripts/test_ui_candidate_feeds_api.py",
    ):
        path = ROOT / relative
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
            feature_version=(3, 10),
        )


def main() -> None:
    tests = [
        test_registry_projects_strict_bounded_normalized_feeds,
        test_invalid_sources_and_public_invariants_fail_soft,
        test_feed_routes_are_additive_and_compatibility_routes_are_preserved,
        test_fixed_clients_validate_urls_provenance_unavailable_and_caps,
        test_today_decision_uses_one_api_result_each_without_local_fallback,
        test_today_decision_english_detail_detection_uses_only_public_text,
        test_today_decision_distinguishes_available_empty_from_unavailable,
        test_today_decision_validation_trust_cards_are_api_only,
        test_today_decision_latest_candidate_counts_are_api_only,
        test_today_decision_options_flow_table_is_api_only,
        test_outcomes_are_immutable_and_sources_are_python310_compatible,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
