#!/usr/bin/env python3
"""Focused contracts for Phase 4N Industry Roles ranked-seed adoption."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.models import IndustryRoleReviewBoardData, RankedCandidatesFeedData  # noqa: E402
from clients import private_api as _private_api  # noqa: E402
from ui import _components, _read_api, industry_roles  # noqa: E402


def _feed(*tickers: str) -> RankedCandidatesFeedData:
    return RankedCandidatesFeedData.model_validate(
        {
            "scan_date": "2026-08-02",
            "generated_at": "2026-08-02T02:03:04+00:00",
            "candidates": [
                {
                    "ticker": ticker,
                    "rank_score": 90.0 - index,
                    "last_price": 100.0,
                    "rank_bucket": "priority",
                    "ret_5d": 3.0,
                    "ret_20d": 8.0,
                    "score_components": {
                        "technical_trend": 20.0,
                        "momentum_strength": 18.0,
                        "launch_signal": 17.0,
                        "liquidity_tradability": 19.0,
                        "overheat_risk_control": 16.0,
                    },
                    "options_tradability": None,
                    "warnings": [],
                }
                for index, ticker in enumerate(tickers)
            ],
        },
        strict=True,
    )


def _x_picks(path: str) -> dict[str, object]:
    if not path.endswith("reports/x_influencer_picks.json"):
        raise AssertionError(f"unexpected local read: {path}")
    return {
        "tickers": [
            {"ticker": "amd"},
            {"symbol": "$TSLA"},
        ]
    }


def _state_payload() -> _private_api.IndustryRoleReviewBoardApiAvailable:
    return _private_api.IndustryRoleReviewBoardApiAvailable(
        IndustryRoleReviewBoardData.model_validate(
            {
                "operator": "operator",
                "taxonomy_version": 1,
                "generated_at": None,
                "roles": [],
                "approved": [],
                "suggestions": [],
            },
            strict=True,
        ),
        '"r0-0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"',
    )


def _app_text(app: AppTest) -> str:
    return "\n".join(
        str(element.value)
        for collection in (app.caption, app.warning, app.info, app.error, app.markdown)
        for element in collection
    )


def test_available_and_available_empty_merge_only_local_x_picks() -> None:
    for feed, expected in (
        (_feed("NVDA", "AMD"), ("AMD", "NVDA", "TSLA")),
        (_feed(), ("AMD", "TSLA")),
    ):
        with (
            patch(
                "ui.industry_roles._read_api.load_ranked_candidates",
                return_value=_read_api.RankedCandidatesApiAvailable(feed),
            ) as loader,
            patch("ui.industry_roles._shared.load_json", side_effect=_x_picks) as local,
        ):
            state = industry_roles._candidate_tickers()
        if loader.call_count != 1 or local.call_count != 1:
            raise AssertionError((loader.call_count, local.call_count))
        if state.status != "api_available" or state.tickers != expected:
            raise AssertionError(state)


def test_unavailable_and_every_failure_preserve_x_only_partial_state() -> None:
    outcomes: tuple[_read_api.RankedCandidatesApiResult, ...] = (
        *(
            _read_api.RankedCandidatesApiUnavailable(reason)
            for reason in sorted(_components.ARTIFACT_REASON_CODES)
        ),
        *(
            _read_api.RankedCandidatesApiFailure(reason)
            for reason in sorted(_components.CLIENT_FAILURE_REASON_CODES)
        ),
    )
    for outcome in outcomes:
        with (
            patch(
                "ui.industry_roles._read_api.load_ranked_candidates",
                return_value=outcome,
            ) as loader,
            patch("ui.industry_roles._shared.load_json", side_effect=_x_picks),
        ):
            state = industry_roles._candidate_tickers()
        expected_status = (
            "api_unavailable"
            if isinstance(outcome, _read_api.RankedCandidatesApiUnavailable)
            else "api_failure"
        )
        if loader.call_count != 1:
            raise AssertionError((outcome, loader.call_count))
        if state.status != expected_status or state.tickers != ("AMD", "TSLA"):
            raise AssertionError((outcome, state))
        if state.reason != outcome.reason:
            raise AssertionError((outcome, state))


def test_page_surfaces_partial_state_and_keeps_generation_available() -> None:
    outcome = _read_api.RankedCandidatesApiFailure("deadline_exceeded")
    with (
        patch("ui.industry_roles._load_state", return_value=_state_payload()),
        patch(
            "ui.industry_roles._read_api.load_ranked_candidates",
            return_value=outcome,
        ) as loader,
        patch("ui.industry_roles._shared.load_json", side_effect=_x_picks),
        patch("ui.industry_roles._private_api.mutate_industry_role_review_board") as mutate,
        patch("ui.industry_roles.engine.approved_rows", return_value=[]),
    ):
        app = AppTest.from_string(
            "from ui.industry_roles import render\nrender()\n",
            default_timeout=10,
        ).run()
    if app.exception or loader.call_count != 1:
        raise AssertionError((app.exception, loader.call_count))
    rendered = _app_text(app)
    if "排名候選服務目前無法使用；仍可使用 X picks 產生建議" not in rendered:
        raise AssertionError(rendered)
    if outcome.reason in rendered:
        raise AssertionError(f"raw reason leaked: {outcome.reason}")
    if not any(button.label == "重新產生建議" for button in app.button):
        raise AssertionError("X-only generation button disappeared")
    mutate.assert_not_called()


def test_source_has_one_fixed_client_no_ranked_or_writer_fallback() -> None:
    path = ROOT / "ui" / "industry_roles.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_candidate_tickers"
    )
    segment = ast.get_source_segment(source, function) or ""
    if 'candidate_output_path("ranked_candidates.json")' in segment:
        raise AssertionError("Industry Roles retained local ranked fallback")
    if segment.count("load_ranked_candidates()") != 1:
        raise AssertionError("Industry Roles must load one fixed ranked feed")
    for preserved in (
        'REPORTS_DIR / "x_influencer_picks.json"',
        "mutate_industry_role_review_board(",
    ):
        if preserved not in source:
            raise AssertionError(f"Industry Roles removed local boundary: {preserved}")
    for forbidden in ("engine.generate_suggestions(", "engine.review_suggestion("):
        if forbidden in source:
            raise AssertionError(f"Industry Roles retained local writer: {forbidden}")


def main() -> None:
    tests = (
        test_available_and_available_empty_merge_only_local_x_picks,
        test_unavailable_and_every_failure_preserve_x_only_partial_state,
        test_page_surfaces_partial_state_and_keeps_generation_available,
        test_source_has_one_fixed_client_no_ranked_or_writer_fallback,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
