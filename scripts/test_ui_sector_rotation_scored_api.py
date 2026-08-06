#!/usr/bin/env python3
"""Focused contracts for Phase 4R Sector Rotation scored-seed adoption."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.models import ScoredCandidatesFeedData, SectorRotationData  # noqa: E402
from ui import _components, _read_api, sector_rotation  # noqa: E402


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


def _flow() -> dict[str, object]:
    return {
        "as_of": "2026-08-03",
        "benchmark": "SPY",
        "sectors": [
            {
                "etf": "XLK",
                "name_zh": "科技",
                "group": "主板塊",
                "theme": None,
                "quadrant": "Leading",
                "quadrant_zh": "領漲",
                "rs_ratio": 101.0,
                "rs_momentum": 101.0,
                "heat_score": 90.0,
                "ret_5d": 2.0,
                "ret_20d": 5.0,
                "ret_60d": 8.0,
                "excess_20d": 3.0,
                "pct_vs_ma50": 4.0,
                "pct_vs_ma200": 6.0,
                "pct_from_52w_high": -2.0,
                "rvol": 1.2,
            },
            {
                "etf": "XLF",
                "name_zh": "金融",
                "group": "主板塊",
                "theme": None,
                "quadrant": "Lagging",
                "quadrant_zh": "落後",
                "rs_ratio": 99.0,
                "rs_momentum": 99.0,
                "heat_score": 30.0,
                "ret_5d": -1.0,
                "ret_20d": -2.0,
                "ret_60d": -3.0,
                "excess_20d": -4.0,
                "pct_vs_ma50": -1.0,
                "pct_vs_ma200": -2.0,
                "pct_from_52w_high": -8.0,
                "rvol": 0.8,
            },
        ],
    }


def _board() -> SectorRotationData:
    return SectorRotationData.model_validate(_flow(), strict=True)


def _app_text(app: AppTest) -> str:
    return "\n".join(
        str(element.value)
        for collection in (app.caption, app.warning, app.info, app.error, app.markdown)
        for element in collection
    )


def test_available_mapping_keeps_cached_sector_fanout() -> None:
    outcome = _read_api.ScoredCandidatesApiAvailable(
        _feed(("NVDA", "NEEDS_LAYER_2", 90.0), ("JPM", "WATCHLIST", 80.0))
    )
    sectors = {"NVDA": "XLK", "JPM": "XLF"}
    with (
        patch(
            "ui.sector_rotation._read_api.load_scored_candidates",
            return_value=outcome,
        ) as loader,
        patch(
            "ui.sector_rotation._shared.ticker_sector_etf",
            side_effect=lambda ticker: sectors[ticker],
        ) as provider,
    ):
        state = sector_rotation._candidate_mapping_state()
        rows = sector_rotation._candidate_mapping_rows(_flow(), state.candidates)
    if loader.call_count != 1 or provider.call_count != 2:
        raise AssertionError((loader.call_count, provider.call_count))
    if [row["代號"] for row in rows] != ["NVDA", "JPM"]:
        raise AssertionError(rows)
    if [row["板塊象限"] for row in rows] != ["領漲", "落後"]:
        raise AssertionError(rows)


def test_empty_unavailable_and_every_failure_are_distinct_without_provider_work() -> None:
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
                "ui.sector_rotation._read_api.load_scored_candidates",
                return_value=outcome,
            ) as loader,
            patch(
                "ui.sector_rotation._shared.load_json",
                side_effect=AssertionError("local scored fallback"),
            ),
            patch("ui.sector_rotation._shared.ticker_sector_etf") as provider,
        ):
            state = sector_rotation._candidate_mapping_state()
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


def test_page_failure_copy_preserves_sector_and_ai_siblings() -> None:
    state = sector_rotation.SectorCandidateState(
        "api_failure", (), "deadline_exceeded"
    )
    with (
        patch("ui.sector_rotation._candidate_mapping_state", return_value=state),
        patch(
            "ui.sector_rotation._board_state",
            return_value=sector_rotation.SectorRotationBoardState(
                "api_available",
                _board(),
            ),
        ),
        patch("ui.sector_rotation._shared.load_json", return_value=None) as local_read,
        patch("ui.sector_rotation._render_rrg"),
        patch("ui.sector_rotation._render_heat_table"),
        patch("ui.sector_rotation._render_sector_themes_drill"),
    ):
        app = AppTest.from_string(
            "from ui.sector_rotation import render\nrender()\n",
            default_timeout=10,
        ).run()
    if app.exception:
        raise AssertionError(app.exception)
    rendered = _app_text(app)
    if "候選排行服務目前無法使用" not in rendered:
        raise AssertionError(rendered)
    if "尚無 AI 研判" not in rendered or local_read.call_count != 1:
        raise AssertionError((rendered, local_read.call_count))
    if state.reason in rendered:
        raise AssertionError("raw failure reason leaked")


def test_source_uses_one_client_and_preserves_local_siblings() -> None:
    path = ROOT / "ui" / "sector_rotation.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    state = functions["_candidate_mapping_state"]
    board_state = functions["_board_state"]
    render_read = functions["_render_read_and_candidates"]
    if 'candidate_output_path("scored_candidates.json")' in source:
        raise AssertionError("Sector Rotation retained local scored source")
    if state.count("load_scored_candidates()") != 1:
        raise AssertionError("Sector Rotation must load one fixed scored feed")
    if board_state.count("load_sector_rotation()") != 1:
        raise AssertionError("Sector Rotation must load one fixed board")
    if "load_sector_flow" in source:
        raise AssertionError("Sector Rotation retained local/live board fallback")
    for preserved in (
        "ticker_sector_etf",
        'REPORTS_DIR / "sector_rotation.json"',
        "generate_rotation_read",
        "ticker_action_buttons",
    ):
        if preserved not in source:
            raise AssertionError(f"Sector Rotation removed sibling boundary: {preserved}")
    if "load_scored_candidates" in render_read:
        raise AssertionError("render helper must reuse the page-level candidate state")


def main() -> None:
    tests = (
        test_available_mapping_keeps_cached_sector_fanout,
        test_empty_unavailable_and_every_failure_are_distinct_without_provider_work,
        test_page_failure_copy_preserves_sector_and_ai_siblings,
        test_source_uses_one_client_and_preserves_local_siblings,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
