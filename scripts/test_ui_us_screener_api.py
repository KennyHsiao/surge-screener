#!/usr/bin/env python3
"""Focused contracts for Phase 4S US Screener scored-slice adoption."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from unittest.mock import patch

import httpx

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.models import ScoredCandidatesScreenerData  # noqa: E402
from ui import _components, _read_api, us_screener  # noqa: E402


def _snapshot(*tickers: str) -> ScoredCandidatesScreenerData:
    return ScoredCandidatesScreenerData.model_validate(
        {
            "scan_date": "2026-08-03",
            "needs_layer2_count": len(tickers),
            "watchlist_count": 0,
            "regime_context": {
                "spy_vs_50dma": "above",
                "spy_vs_200dma": "above",
                "vix_level": 17.5,
                "vix_regime": "normal",
                "global_score_multiplier": 1.0,
                "active_themes": ["AI"],
                "regime_warnings": [],
            },
            "candidates": [
                {
                    "ticker": ticker,
                    "verdict": "NEEDS_LAYER_2",
                    "regime_adjusted_score": 90.0 - index,
                    "scores": {
                        "technical": 25.0,
                        "catalyst": 12.0,
                        "sentiment": 8.0,
                        "institutional": 7.0,
                        "sector_market": 2.0,
                        "options_flow": 16.0,
                        "analyst": 6.0,
                    },
                    "key_signals": ["fixture signal"],
                    "key_risks": ["fixture risk"],
                    "suggested_entry_zone": "$95-$100",
                    "suggested_stop": "$90",
                    "suggested_size_pct": 5.0,
                    "anti_example_warning": None,
                    "data_missing": [],
                    "technical_breakdown": {
                        "pattern_type": "breakout",
                        "macd_state": "bullish",
                    },
                }
                for index, ticker in enumerate(tickers)
            ],
        },
        strict=True,
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
    source_id: str = "candidates.scored.screener",
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


def test_fixed_client_validates_url_provenance_unavailable_and_cap() -> None:
    snapshot = _snapshot("NVDA")
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return _response(_envelope(snapshot.model_dump(mode="json")))

    result = _read_api.load_scored_candidates_screener(
        transport=httpx.MockTransport(handler)
    )
    if not isinstance(result, _read_api.ScoredCandidatesScreenerApiAvailable):
        raise AssertionError(result)
    if seen != ["http://127.0.0.1:8000/api/v1/candidates/scored/screener"]:
        raise AssertionError(seen)

    unavailable = _read_api.load_scored_candidates_screener(
        transport=httpx.MockTransport(
            lambda _request: _response(
                _envelope(None, available=False, reason="missing", as_of=None)
            )
        )
    )
    if unavailable != _read_api.ScoredCandidatesScreenerApiUnavailable("missing"):
        raise AssertionError(unavailable)

    for payload in (
        _envelope(snapshot.model_dump(mode="json"), source_id="candidates.scored.feed"),
        _envelope(snapshot.model_dump(mode="json"), as_of="2026-08-02"),
        _envelope(
            snapshot.model_dump(mode="json"),
            generated_at="2026-08-03T01:02:03Z",
        ),
    ):
        invalid = _read_api.load_scored_candidates_screener(
            transport=httpx.MockTransport(
                lambda _request, payload=payload: _response(payload)
            )
        )
        if invalid != _read_api.ScoredCandidatesScreenerApiFailure(
            "invalid_envelope"
        ):
            raise AssertionError(invalid)

    oversized = httpx.Response(
        200,
        headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
        content=b"x"
        * (_read_api._SCORED_CANDIDATES_SCREENER_MAX_RESPONSE_BYTES + 1),
    )
    too_large = _read_api.load_scored_candidates_screener(
        transport=httpx.MockTransport(lambda _request: oversized)
    )
    if too_large != _read_api.ScoredCandidatesScreenerApiFailure(
        "response_too_large"
    ):
        raise AssertionError(too_large)


def test_available_and_available_empty_are_typed_without_local_fallback() -> None:
    for snapshot in (_snapshot("NVDA", "AMD"), _snapshot()):
        outcome = _read_api.ScoredCandidatesScreenerApiAvailable(snapshot)
        with (
            patch(
                "ui.us_screener._read_api.load_scored_candidates_screener",
                return_value=outcome,
            ) as loader,
            patch(
                "ui.us_screener._shared.load_json",
                side_effect=AssertionError("state helper attempted a local fallback"),
            ),
        ):
            state = us_screener._scored_state()
        if loader.call_count != 1:
            raise AssertionError(loader.call_count)
        if state.status != "api_available" or state.snapshot != snapshot:
            raise AssertionError(state)


def test_unavailable_and_every_failure_are_distinct_without_local_fallback() -> None:
    outcomes: tuple[_read_api.ScoredCandidatesScreenerApiResult, ...] = (
        *(
            _read_api.ScoredCandidatesScreenerApiUnavailable(reason)
            for reason in sorted(_components.ARTIFACT_REASON_CODES)
        ),
        *(
            _read_api.ScoredCandidatesScreenerApiFailure(reason)
            for reason in sorted(_components.CLIENT_FAILURE_REASON_CODES)
        ),
    )
    for outcome in outcomes:
        with patch(
            "ui.us_screener._read_api.load_scored_candidates_screener",
            return_value=outcome,
        ) as loader:
            state = us_screener._scored_state()
        expected = (
            "api_unavailable"
            if isinstance(outcome, _read_api.ScoredCandidatesScreenerApiUnavailable)
            else "api_failure"
        )
        if loader.call_count != 1:
            raise AssertionError((outcome, loader.call_count))
        if state.status != expected or state.snapshot is not None:
            raise AssertionError((outcome, state))
        if state.reason != outcome.reason:
            raise AssertionError((outcome, state))


def test_state_helpers_preserve_layer2_regime_fallback_and_counts() -> None:
    snapshot = _snapshot("NVDA")
    available = us_screener.ScreenerScoredState("api_available", snapshot)
    fallback = {"regime_context": {"spy_vs_50dma": "below"}}
    if us_screener._regime_context(available, fallback) != snapshot.regime_context:
        raise AssertionError("available API regime was not selected")
    if us_screener._scored_counts(available) != (1, 0):
        raise AssertionError(us_screener._scored_counts(available))
    if us_screener._scored_candidates(available) != tuple(snapshot.candidates):
        raise AssertionError(us_screener._scored_candidates(available))

    for state in (
        us_screener.ScreenerScoredState("api_available", _snapshot()),
        us_screener.ScreenerScoredState("api_unavailable", None, "missing"),
        us_screener.ScreenerScoredState(
            "api_failure", None, "deadline_exceeded"
        ),
    ):
        expected_regime = (
            state.snapshot.regime_context
            if state.snapshot is not None
            else fallback["regime_context"]
        )
        if us_screener._regime_context(state, fallback) != expected_regime:
            raise AssertionError(state)


def test_source_uses_one_fixed_client_and_preserves_every_local_sibling() -> None:
    path = ROOT / "ui" / "us_screener.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    state = functions["_scored_state"]
    render = functions["render"]
    if 'candidate_output_path("scored_candidates.json")' in source:
        raise AssertionError("US Screener retained a local scored source/status check")
    if state.count("load_scored_candidates_screener()") != 1:
        raise AssertionError("US Screener must load one fixed screener projection")
    if "load_scored_candidates_screener" in render:
        raise AssertionError("render must reuse the page-level typed state")
    for preserved in (
        'candidate_output_path("filtered_universe.json")',
        'DATA_DIR / "filtered_nasdaq.json"',
        'DATA_DIR / "layer2_results.json"',
        'DATA_DIR / "dd_results.json"',
        'REPORTS_DIR / selected_date / "summary.json"',
        "_shared.load_ledger()",
        "analyst_views.render_for(ticker)",
        "_shared.ticker_action_buttons(ticker, \"scr\")",
    ):
        if preserved not in source:
            raise AssertionError(f"US Screener removed local sibling: {preserved}")


def main() -> None:
    tests = (
        test_fixed_client_validates_url_provenance_unavailable_and_cap,
        test_available_and_available_empty_are_typed_without_local_fallback,
        test_unavailable_and_every_failure_are_distinct_without_local_fallback,
        test_state_helpers_preserve_layer2_regime_fallback_and_counts,
        test_source_uses_one_fixed_client_and_preserves_every_local_sibling,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
