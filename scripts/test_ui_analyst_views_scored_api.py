#!/usr/bin/env python3
"""Focused contracts for Phase 4Q Analyst Views scored-grid adoption."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.models import ScoredCandidatesFeedData  # noqa: E402
from ui import _components, _read_api, analyst_views  # noqa: E402


def _feed(*rows: tuple[str, str, float]) -> ScoredCandidatesFeedData:
    return ScoredCandidatesFeedData.model_validate(
        {
            "scan_date": "2026-08-03",
            "candidates": [
                {
                    "ticker": ticker,
                    "verdict": verdict,
                    "composite_score": score - 1.0,
                    "regime_adjusted_score": score,
                    "scores": {
                        "technical": 25.0,
                        "catalyst": 12.0,
                        "sentiment": 8.0,
                        "institutional": 7.0,
                        "sector_market": 2.0,
                        "options_flow": 16.0,
                        "analyst": 6.0,
                    },
                    "data_missing": [],
                    "due_diligence_required": False,
                    "key_signals": [],
                    "key_risks": [],
                    "suggested_entry_zone": "$95-$100",
                }
                for ticker, verdict, score in rows
            ],
        },
        strict=True,
    )


def _analyst_data(ticker: str) -> dict[str, object]:
    upside = {"NVDA": 20.0, "AMD": 10.0}.get(ticker, 5.0)
    return {
        "consensus": {
            "recommendation": "buy",
            "num_analysts": 12,
            "mean_rating_score": 2.0,
        },
        "price_targets": {
            "spot": 100.0,
            "mean": 100.0 + upside,
            "median": 110.0,
            "high": 130.0,
            "low": 90.0,
            "upside_pct": upside,
        },
        "rating_distribution": {},
        "recent_actions": [],
        "estimate_revisions": {},
    }


def _app_text(app: AppTest) -> str:
    return "\n".join(
        str(element.value)
        for collection in (app.caption, app.warning, app.info, app.error, app.markdown)
        for element in collection
    )


def test_available_grid_keeps_one_local_analyst_lookup_per_candidate() -> None:
    outcome = _read_api.ScoredCandidatesApiAvailable(
        _feed(("NVDA", "NEEDS_LAYER_2", 90.0), ("AMD", "WATCHLIST", 80.0))
    )
    with (
        patch(
            "ui.analyst_views._read_api.load_scored_candidates",
            return_value=outcome,
        ) as loader,
        patch(
            "ui.analyst_views._shared.load_analyst_views",
            side_effect=_analyst_data,
        ) as provider,
    ):
        state = analyst_views._candidate_grid_state()
        rows = analyst_views._grid_rows(state.candidates)
    if loader.call_count != 1 or provider.call_count != 2:
        raise AssertionError((loader.call_count, provider.call_count))
    if state.status != "api_available":
        raise AssertionError(state)
    if [row["代號"] for row in rows] != ["NVDA", "AMD"]:
        raise AssertionError(rows)


def test_empty_unavailable_and_every_failure_are_distinct_without_fallback() -> None:
    outcomes: tuple[_read_api.ScoredCandidatesApiResult, ...] = (
        _read_api.ScoredCandidatesApiAvailable(_feed()),
        *(
            _read_api.ScoredCandidatesApiUnavailable(reason)
            for reason in sorted(_components.ARTIFACT_REASON_CODES)
        ),
        *(
            _read_api.ScoredCandidatesApiFailure(reason)
            for reason in sorted(_components.CLIENT_FAILURE_REASON_CODES)
        ),
    )
    for outcome in outcomes:
        with (
            patch(
                "ui.analyst_views._read_api.load_scored_candidates",
                return_value=outcome,
            ) as loader,
            patch(
                "ui.analyst_views._shared.load_json",
                side_effect=AssertionError("local scored fallback"),
            ),
            patch("ui.analyst_views._shared.load_analyst_views") as provider,
        ):
            state = analyst_views._candidate_grid_state()
        expected = (
            "api_available"
            if isinstance(outcome, _read_api.ScoredCandidatesApiAvailable)
            else "api_unavailable"
            if isinstance(outcome, _read_api.ScoredCandidatesApiUnavailable)
            else "api_failure"
        )
        if loader.call_count != 1 or provider.call_count != 0:
            raise AssertionError((outcome, loader.call_count, provider.call_count))
        if state.status != expected or state.candidates:
            raise AssertionError((outcome, state))


def test_page_copy_and_default_detail_behavior_are_preserved() -> None:
    cases = (
        (analyst_views.AnalystGridState("api_available", ()), "今日候選清單為空"),
        (
            analyst_views.AnalystGridState("api_unavailable", (), "missing"),
            "候選排行資料目前無法使用",
        ),
        (
            analyst_views.AnalystGridState("api_failure", (), "deadline_exceeded"),
            "候選排行服務目前無法使用",
        ),
    )
    for state, expected in cases:
        with patch("ui.analyst_views._candidate_grid_state", return_value=state):
            app = AppTest.from_string(
                "from ui.analyst_views import render\nrender()\n",
                default_timeout=10,
            ).run()
        if app.exception:
            raise AssertionError((state, app.exception))
        rendered = _app_text(app)
        if expected not in rendered:
            raise AssertionError((state, rendered))
        if state.reason and state.reason in rendered:
            raise AssertionError(f"raw reason leaked: {state.reason}")

    state = analyst_views.AnalystGridState(
        "api_available",
        tuple(_feed(("NVDA", "NEEDS_LAYER_2", 90.0)).candidates),
    )
    with (
        patch("ui.analyst_views._candidate_grid_state", return_value=state),
        patch(
            "ui.analyst_views._shared.load_analyst_views",
            side_effect=_analyst_data,
        ) as provider,
    ):
        app = AppTest.from_string(
            "from ui.analyst_views import render\nrender()\n",
            default_timeout=10,
        ).run()
    if app.exception or provider.call_count != 2:
        raise AssertionError((app.exception, provider.call_count))


def test_source_uses_one_client_no_local_scored_fallback_and_embedded_isolation() -> None:
    path = ROOT / "ui" / "analyst_views.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    state = functions["_candidate_grid_state"]
    embedded = functions["_render_detail"]
    if 'candidate_output_path("scored_candidates.json")' in source:
        raise AssertionError("Analyst Views retained local scored source")
    if state.count("load_scored_candidates()") != 1:
        raise AssertionError("Analyst Views must load one fixed scored feed")
    if "load_scored_candidates" in embedded or "_candidate_grid_state" in embedded:
        raise AssertionError("embedded analyst detail must remain provider-only")
    if "_shared.load_analyst_views(ticker)" not in embedded:
        raise AssertionError("embedded analyst provider boundary was removed")


def main() -> None:
    tests = (
        test_available_grid_keeps_one_local_analyst_lookup_per_candidate,
        test_empty_unavailable_and_every_failure_are_distinct_without_fallback,
        test_page_copy_and_default_detail_behavior_are_preserved,
        test_source_uses_one_client_no_local_scored_fallback_and_embedded_isolation,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
