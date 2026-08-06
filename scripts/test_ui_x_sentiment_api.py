#!/usr/bin/env python3
"""Focused contracts for Phase 4T/4U X Sentiment read separation."""

from __future__ import annotations

import ast
import json
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import httpx
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.artifacts import ARTIFACTS, ArtifactSpec, ResolvedArtifactPath, read_artifact  # noqa: E402
from api.models import (  # noqa: E402
    ArtifactAvailable,
    ArtifactUnavailable,
    RankedCandidatesFeedData,
    SocialIntelligenceData,
)
from ui import _components, _read_api, x_sentiment  # noqa: E402


SOURCE_ID = "social.intelligence.latest"
ROUTE = "/api/v1/social/intelligence/latest"
URL = f"http://127.0.0.1:8000{ROUTE}"
ROOT_FIELDS = {"as_of_date", "generated_at", "market", "source_statuses", "tickers"}
TICKER_FIELDS = {
    "ticker",
    "mentioned_by",
    "citations",
    "skew",
    "conviction",
    "note",
    "platform_validation",
    "labels",
}
VALIDATION_FIELDS = {
    "in_ranked_candidates",
    "rank_score",
    "rank_bucket",
    "last_price",
    "options_flow_score",
    "options_direction",
}
LABEL_FIELDS = {
    "x_mentioned",
    "agent_reach",
    "retail_heat",
    "crowded",
    "early_signal",
    "paid_data_needed",
}


def _social_source(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "as_of_date": "2026-08-03",
        "generated_at": "2026-08-03T01:02:03.123456+00:00",
        "source": "social_intelligence",
        "schema_version": 1,
        "market": "US",
        "source_statuses": {
            "codex_web_research": {
                "label": "Codex web research",
                "cost_mode": "chatgpt_subscription",
                "status": "available",
                "note": "private sibling status",
            },
            "x_official_api": {
                "label": "X official API",
                "cost_mode": "paid_optional",
                "status": "unavailable",
                "note": "private sibling status",
            },
            "agent_reach": {
                "label": "Agent Reach",
                "cost_mode": "auth_required",
                "status": "available",
                "note": "fixture reach",
            },
            "stocktwits": {
                "label": "StockTwits",
                "cost_mode": "free",
                "status": "available",
                "note": "private sibling status",
            },
            "apewisdom": {
                "label": "ApeWisdom",
                "cost_mode": "free",
                "status": "available",
                "note": "private sibling status",
            },
        },
        "tickers": [
            {
                "ticker": "NVDA",
                "mentioned_by": ["fixture_author"],
                "citations": ["https://example.test/post/1"],
                "discovery_sources": ["agent_reach"],
                "cost_modes": ["auth_required"],
                "skew": "bullish",
                "conviction": "high",
                "note": "fixture candidate",
                "heat_baseline": {"private": True},
                "platform_validation": {
                    "in_ranked_candidates": True,
                    "rank_score": 88.0,
                    "rank_bucket": "priority",
                    "last_price": 180.0,
                    "options_flow_score": 72.0,
                    "options_direction": "bullish",
                },
                "labels": {
                    "x_mentioned": False,
                    "agent_reach": True,
                    "retail_heat": True,
                    "crowded": False,
                    "early_signal": True,
                    "paid_data_needed": False,
                },
            }
        ],
        "limitations": ["private producer caveat"],
    }
    payload.update(overrides)
    return payload


def _social_public(market: str = "US") -> dict[str, object]:
    source = _social_source(market=market)
    row = source["tickers"][0]  # type: ignore[index]
    return {
        "as_of_date": source["as_of_date"],
        "generated_at": source["generated_at"],
        "market": market,
        "source_statuses": {
            "agent_reach": {"status": "available", "note": "fixture reach"}
        },
        "tickers": [
            {
                key: row[key]  # type: ignore[index]
                for key in TICKER_FIELDS
            }
        ],
    }


def _ranked_feed(*tickers: str) -> RankedCandidatesFeedData:
    return RankedCandidatesFeedData.model_validate(
        {
            "scan_date": "2026-08-03",
            "generated_at": "2026-08-03T00:00:00+00:00",
            "candidates": [
                {
                    "ticker": ticker,
                    "rank_score": 90.0 - index,
                    "last_price": 100.0 + index,
                    "rank_bucket": "priority",
                    "ret_5d": 1.0,
                    "ret_20d": 2.0,
                    "score_components": {
                        "technical_trend": 1.0,
                        "momentum_strength": 1.0,
                        "launch_signal": 1.0,
                        "liquidity_tradability": 1.0,
                        "overheat_risk_control": 1.0,
                    },
                    "options_tradability": None,
                    "warnings": [],
                }
                for index, ticker in enumerate(tickers)
            ],
        },
        strict=True,
    )


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
    as_of: str | None = "2026-08-03",
    generated_at: str | None = "2026-08-03T01:02:03.123456+00:00",
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


def test_social_registry_is_strict_bounded_and_fail_soft() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "latest.json"
        result = read_artifact(_spec(_write(path, _social_source())))
        if not isinstance(result, ArtifactAvailable):
            raise AssertionError(result)
        data = result.data
        if set(data) != ROOT_FIELDS or set(data["tickers"][0]) != TICKER_FIELDS:
            raise AssertionError(data)
        row = data["tickers"][0]
        if set(row["platform_validation"]) != VALIDATION_FIELDS:
            raise AssertionError(row)
        if set(row["labels"]) != LABEL_FIELDS:
            raise AssertionError(row)
        if data["source_statuses"] != {
            "agent_reach": {"status": "available", "note": "fixture reach"}
        }:
            raise AssertionError(data["source_statuses"])
        if any(
            private in json.dumps(data)
            for private in ("private sibling status", "heat_baseline", "cost_modes")
        ):
            raise AssertionError(data)

        invalid_sources = [
            _social_source(schema_version=2),
            _social_source(source="other"),
            _social_source(extra="secret"),
            _social_source(tickers=_social_source()["tickers"] * 201),
        ]
        bad_labels = _social_source()
        del bad_labels["tickers"][0]["labels"]["early_signal"]  # type: ignore[index]
        invalid_sources.append(bad_labels)
        bad_price = _social_source()
        bad_price["tickers"][0]["platform_validation"]["last_price"] = -1.0  # type: ignore[index]
        invalid_sources.append(bad_price)
        for invalid in invalid_sources:
            outcome = read_artifact(_spec(_write(path, invalid)))
            if not isinstance(outcome, ArtifactUnavailable) or outcome.reason != "invalid_shape":
                raise AssertionError((invalid, outcome))

        missing = read_artifact(_spec(Path(tmp) / "missing.json"))
        if not isinstance(missing, ArtifactUnavailable) or missing.reason != "missing":
            raise AssertionError(missing)


def test_social_client_validates_url_provenance_metadata_and_cap() -> None:
    public = SocialIntelligenceData.model_validate(_social_public(), strict=True)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return _response(_envelope(public.model_dump(mode="json")))

    result = _read_api.load_social_intelligence(
        transport=httpx.MockTransport(handler)
    )
    if not isinstance(result, _read_api.SocialIntelligenceApiAvailable):
        raise AssertionError(result)
    if seen != [URL]:
        raise AssertionError(seen)

    unavailable = _read_api.load_social_intelligence(
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
    if unavailable != _read_api.SocialIntelligenceApiUnavailable("missing"):
        raise AssertionError(unavailable)

    for payload in (
        _envelope(public.model_dump(mode="json"), source_id="social.other"),
        _envelope(public.model_dump(mode="json"), as_of="2026-08-02"),
        _envelope(public.model_dump(mode="json"), generated_at="2026-08-03T01:02:04Z"),
    ):
        outcome = _read_api.load_social_intelligence(
            transport=httpx.MockTransport(
                lambda _request, payload=payload: _response(payload)
            )
        )
        if outcome != _read_api.SocialIntelligenceApiFailure("invalid_envelope"):
            raise AssertionError(outcome)

    oversized = httpx.Response(
        200,
        headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        content=b"x" * (_read_api._SOCIAL_INTELLIGENCE_MAX_RESPONSE_BYTES + 1),
    )
    outcome = _read_api.load_social_intelligence(
        transport=httpx.MockTransport(lambda _request: oversized)
    )
    if outcome != _read_api.SocialIntelligenceApiFailure("response_too_large"):
        raise AssertionError(outcome)


def test_ranked_refresh_seed_uses_api_once_without_local_ranked_fallback() -> None:
    for outcome, expected in (
        (
            _read_api.RankedCandidatesApiAvailable(_ranked_feed("NVDA", "AMD")),
            ["NVDA", "AMD"],
        ),
        (_read_api.RankedCandidatesApiAvailable(_ranked_feed()), []),
        (_read_api.RankedCandidatesApiUnavailable("missing"), None),
        (_read_api.RankedCandidatesApiFailure("transport_error"), None),
    ):
        with (
            patch(
                "ui.x_sentiment._read_api.load_ranked_candidates",
                return_value=outcome,
            ) as loader,
            patch(
                "ui.x_sentiment._shared.load_json",
                side_effect=AssertionError("ranked seed attempted a local fallback"),
            ),
        ):
            seed = x_sentiment._ranked_candidates_seed()
        if loader.call_count != 1:
            raise AssertionError(loader.call_count)
        if expected is None:
            if seed is not None:
                raise AssertionError(seed)
        else:
            tickers = [row["ticker"] for row in seed["ranked_candidates"]]
            if tickers != expected:
                raise AssertionError(seed)


def test_social_state_selects_market_and_distinguishes_failures() -> None:
    us = SocialIntelligenceData.model_validate(_social_public("US"), strict=True)
    cases: tuple[tuple[_read_api.SocialIntelligenceApiResult, str], ...] = (
        (_read_api.SocialIntelligenceApiAvailable(us), "api_available"),
        (
            _read_api.SocialIntelligenceApiAvailable(
                SocialIntelligenceData.model_validate(_social_public("CRYPTO"), strict=True)
            ),
            "api_other_market",
        ),
        *tuple(
            (_read_api.SocialIntelligenceApiUnavailable(reason), "api_unavailable")
            for reason in sorted(_components.ARTIFACT_REASON_CODES)
        ),
        *tuple(
            (_read_api.SocialIntelligenceApiFailure(reason), "api_failure")
            for reason in sorted(_components.CLIENT_FAILURE_REASON_CODES)
        ),
    )
    for outcome, expected in cases:
        with patch(
            "ui.x_sentiment._read_api.load_social_intelligence",
            return_value=outcome,
        ) as loader:
            state = x_sentiment._social_snapshot_state("US")
        if loader.call_count != 1 or state.status != expected:
            raise AssertionError((outcome, state, loader.call_count))
        if (expected == "api_available") != isinstance(state.snapshot, dict):
            raise AssertionError((outcome, state))


def _render_radar(
    outcome: _read_api.SocialIntelligenceApiResult,
    *,
    auto_snapshot: dict[str, object] | None = None,
) -> tuple[AppTest, int, list[str]]:
    reads: list[str] = []

    def local_read(path: str) -> dict[str, object] | None:
        reads.append(path)
        if path.endswith("reports/x_influencer_picks.json"):
            return {
                "market": "US",
                "window": "fixture",
                "generated_at": "fixture",
                "tickers": [
                    {
                        "symbol": "LEGACY",
                        "mentioned_by": ["fixture"],
                        "skew": "neutral",
                    }
                ],
                "citations": [],
            }
        raise AssertionError(f"unexpected local read: {path}")

    with (
        patch(
            "ui.x_sentiment._maybe_auto_refresh_radar",
            return_value=auto_snapshot,
        ),
        patch("ui.x_sentiment._render_radar_refresh"),
        patch(
            "ui.x_sentiment._read_api.load_social_intelligence",
            return_value=outcome,
        ) as loader,
        patch("ui.x_sentiment._shared.load_json", side_effect=local_read),
        patch("ui.x_sentiment._maybe_auto_generate_ai_summary", return_value={}),
        patch("ui.x_sentiment._render_ai_summary_body"),
    ):
        app = AppTest.from_string(
            "from ui.x_sentiment import _render_radar\n_render_radar('US')\n",
            default_timeout=10,
        ).run()
    return app, loader.call_count, reads


def test_radar_uses_api_or_independent_legacy_partial_state_without_social_fallback() -> None:
    available = _read_api.SocialIntelligenceApiAvailable(
        SocialIntelligenceData.model_validate(_social_public(), strict=True)
    )
    app, calls, reads = _render_radar(available)
    if app.exception or calls != 1 or reads:
        raise AssertionError((app.exception, calls, reads))
    dataframe_text = "\n".join(str(frame.value) for frame in app.dataframe)
    if "NVDA" not in dataframe_text:
        raise AssertionError((dataframe_text, _app_text(app)))

    outcomes: tuple[_read_api.SocialIntelligenceApiResult, ...] = (
        _read_api.SocialIntelligenceApiAvailable(
            SocialIntelligenceData.model_validate(_social_public("CRYPTO"), strict=True)
        ),
        _read_api.SocialIntelligenceApiUnavailable("missing"),
        _read_api.SocialIntelligenceApiFailure("transport_error"),
    )
    for outcome in outcomes:
        app, calls, reads = _render_radar(outcome)
        rendered = _app_text(app)
        dataframe_text = "\n".join(str(frame.value) for frame in app.dataframe)
        if app.exception or calls != 1:
            raise AssertionError((outcome, app.exception, calls))
        if reads != [str(x_sentiment._PICKS_PATH)] or "LEGACY" not in dataframe_text:
            raise AssertionError((outcome, reads, dataframe_text, rendered))
        if str(x_sentiment._SOCIAL_PATH) in reads:
            raise AssertionError("selected social path was read locally")
        expected = (
            "最新社群快照屬於其他市場"
            if isinstance(outcome, _read_api.SocialIntelligenceApiAvailable)
            else (
                "社群快照資料目前無法使用"
                if isinstance(outcome, _read_api.SocialIntelligenceApiUnavailable)
                else "社群快照服務目前無法使用"
            )
        )
        raw_reason = getattr(outcome, "reason", None)
        if expected not in rendered or (
            isinstance(raw_reason, str) and raw_reason in rendered
        ):
            raise AssertionError((outcome, rendered))


def test_same_rerun_refresh_result_bypasses_persisted_api_read() -> None:
    auto = _social_public()
    outcome = _read_api.SocialIntelligenceApiFailure("transport_error")
    app, calls, reads = _render_radar(outcome, auto_snapshot=auto)
    if app.exception or calls != 0 or reads:
        raise AssertionError((app.exception, calls, reads))


def test_source_has_one_ranked_and_social_client_without_selected_local_reads() -> None:
    path = ROOT / "ui" / "x_sentiment.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    writer = functions["_write_free_first_snapshot_from_ui"]
    radar = functions["_render_radar"]
    if writer.count("_ranked_candidates_seed()") != 1:
        raise AssertionError(writer)
    if "ranked_candidates.json" in writer or "social_intelligence.REPO" in writer:
        raise AssertionError("refresh writer retained a direct ranked artifact read")
    if radar.count("_social_snapshot_state(market)") != 1:
        raise AssertionError(radar)
    if "_SOCIAL_PATH" in radar:
        raise AssertionError("radar retained a local Social latest read")
    if "_PICKS_PATH" not in radar:
        raise AssertionError("independent legacy X-picks sibling was removed")


def main() -> int:
    tests = [
        test_social_registry_is_strict_bounded_and_fail_soft,
        test_social_client_validates_url_provenance_metadata_and_cap,
        test_ranked_refresh_seed_uses_api_once_without_local_ranked_fallback,
        test_social_state_selects_market_and_distinguishes_failures,
        test_radar_uses_api_or_independent_legacy_partial_state_without_social_fallback,
        test_same_rerun_refresh_result_bypasses_persisted_api_read,
        test_source_has_one_ranked_and_social_client_without_selected_local_reads,
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
