#!/usr/bin/env python3
"""Focused contracts for Phase 4M US Options scored-grid adoption."""

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
from ui import _components, _read_api, us_options  # noqa: E402


def _feed(*rows: tuple[str, str, float]) -> ScoredCandidatesFeedData:
    return ScoredCandidatesFeedData.model_validate(
        {
            "scan_date": "2026-08-02",
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


def _app_text(app: AppTest) -> str:
    return "\n".join(
        str(element.value)
        for collection in (app.caption, app.warning, app.info, app.error, app.markdown)
        for element in collection
    )


def test_available_grid_uses_canonical_verdicts_and_local_iv_rows() -> None:
    outcome = _read_api.ScoredCandidatesApiAvailable(
        _feed(
            ("TSLA", "REJECT", 99.0),
            ("NVDA", "NEEDS_LAYER_2", 90.0),
            ("AMD", "WATCHLIST", 80.0),
        )
    )
    iv_rows = {
        "AMD": (35.0, False, 50, [30.0, 35.0]),
        "NVDA": (20.0, False, 50, [18.0, 20.0]),
        "TSLA": (10.0, False, 50, [8.0, 10.0]),
    }
    with (
        patch(
            "ui.us_options._read_api.load_scored_candidates",
            return_value=outcome,
        ) as loader,
        patch(
            "ui.us_options._iv_rank_spark",
            side_effect=lambda ticker: iv_rows.get(ticker, (50.0, False, 50, [50.0])),
        ) as iv,
    ):
        state = us_options._candidate_grid()
    if loader.call_count != 1 or iv.call_count != 3:
        raise AssertionError((loader.call_count, iv.call_count))
    if state.status != "api_available" or state.frame is None:
        raise AssertionError(state)
    if state.frame["代號"].tolist() != ["NVDA", "AMD", "TSLA"]:
        raise AssertionError(state.frame)
    verdicts = state.frame["判定"].tolist()
    if verdicts != ["🟡 NEEDS_LAYER_2", "🟡 WATCHLIST", "🔴 REJECT"]:
        raise AssertionError(verdicts)
    if state.frame["選擇權流"].tolist() != [16.0, 16.0, 16.0]:
        raise AssertionError(state.frame)


def test_available_empty_unavailable_and_every_failure_are_distinct() -> None:
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
                "ui.us_options._read_api.load_scored_candidates",
                return_value=outcome,
            ) as loader,
            patch("ui.us_options._iv_rank_spark") as iv,
        ):
            state = us_options._candidate_grid()
        expected = (
            "api_available"
            if isinstance(outcome, _read_api.ScoredCandidatesApiAvailable)
            else "api_unavailable"
            if isinstance(outcome, _read_api.ScoredCandidatesApiUnavailable)
            else "api_failure"
        )
        if loader.call_count != 1 or iv.call_count != 0:
            raise AssertionError((outcome, loader.call_count, iv.call_count))
        if state.status != expected or state.frame is not None:
            raise AssertionError((outcome, state))


def test_page_copy_distinguishes_empty_unavailable_and_failure() -> None:
    cases = (
        (
            us_options.CandidateGridState("api_available", None),
            "今日候選清單為空",
        ),
        (
            us_options.CandidateGridState("api_unavailable", None, "missing"),
            "候選排行資料目前無法使用",
        ),
        (
            us_options.CandidateGridState("api_failure", None, "deadline_exceeded"),
            "候選排行服務目前無法使用",
        ),
    )
    for state, expected in cases:
        with patch("ui.us_options._candidate_grid", return_value=state):
            app = AppTest.from_string(
                "from ui.us_options import render\nrender()\n",
                default_timeout=10,
            ).run()
        if app.exception:
            raise AssertionError((state, app.exception))
        rendered = _app_text(app)
        if expected not in rendered:
            raise AssertionError((state, rendered))
        if state.reason and state.reason in rendered:
            raise AssertionError(f"raw reason leaked: {state.reason}")


def test_source_has_one_fixed_client_no_scored_fallback_and_embedded_isolation() -> None:
    path = ROOT / "ui" / "us_options.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    grid = functions["_candidate_grid"]
    embedded = functions["render_for"]
    if 'candidate_output_path("scored_candidates.json")' in grid:
        raise AssertionError("US Options grid retained local scored fallback")
    if grid.count("load_scored_candidates()") != 1:
        raise AssertionError("US Options grid must load one fixed scored feed")
    if "_candidate_grid" in embedded or "load_scored_candidates" in embedded:
        raise AssertionError("embedded per-ticker options must not load the scored grid")
    for preserved in ("def _iv_rank_spark", "from scripts import iv_history as ivh"):
        if preserved not in source:
            raise AssertionError(f"US Options removed local IV boundary: {preserved}")


def main() -> None:
    tests = (
        test_available_grid_uses_canonical_verdicts_and_local_iv_rows,
        test_available_empty_unavailable_and_every_failure_are_distinct,
        test_page_copy_distinguishes_empty_unavailable_and_failure,
        test_source_has_one_fixed_client_no_scored_fallback_and_embedded_isolation,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
