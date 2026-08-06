#!/usr/bin/env python3
"""Focused contracts for Phase 4H institutional scored-context adoption."""

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
from ui import _components, _read_api, institutional_holdings  # noqa: E402


def _feed(*tickers: str) -> ScoredCandidatesFeedData:
    return ScoredCandidatesFeedData.model_validate(
        {
            "scan_date": "2026-08-01",
            "candidates": [
                {
                    "ticker": ticker,
                    "verdict": "NEEDS_LAYER_2" if index == 0 else "WATCHLIST",
                    "composite_score": 80.0 - index,
                    "regime_adjusted_score": 80.0 - index,
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
                    "key_signals": ["機構持股改善", "technical alignment"],
                    "key_risks": [],
                    "suggested_entry_zone": "$95-$100",
                }
                for index, ticker in enumerate(tickers)
            ],
        },
        strict=True,
    )


def _app_text(app: AppTest) -> str:
    values = [
        str(element.value)
        for collection in (app.caption, app.warning, app.info, app.error, app.markdown)
        for element in collection
    ]
    values.extend(str(element.label) for element in app.expander)
    return "\n".join(values)


def _provider_data() -> dict[str, object]:
    return {
        "ownership_pct": {
            "institutions_held": 75.0,
            "institutions_float_held": 77.0,
            "insiders_held": 1.0,
        },
        "insider_6m": {},
        "source": "fixture-provider",
    }


def test_available_match_no_match_and_empty_are_distinct() -> None:
    available = _read_api.ScoredCandidatesApiAvailable(_feed("NVDA", "AMD"))
    with patch(
        "ui.institutional_holdings._read_api.load_scored_candidates",
        return_value=available,
    ) as loader:
        app = AppTest.from_string(
            "from ui.institutional_holdings import _render_score_context\n"
            "_render_score_context('nvda')\n",
            default_timeout=10,
        ).run()
    if app.exception or loader.call_count != 1:
        raise AssertionError((app.exception, loader.call_count))
    rendered = _app_text(app)
    for expected in ("7.0/10", "NEEDS_LAYER_2", "機構持股改善"):
        if expected not in rendered:
            raise AssertionError(rendered)

    for feed in (_feed("AMD"), _feed()):
        with patch(
            "ui.institutional_holdings._read_api.load_scored_candidates",
            return_value=_read_api.ScoredCandidatesApiAvailable(feed),
        ):
            app = AppTest.from_string(
                "from ui.institutional_holdings import _render_score_context\n"
                "_render_score_context('NVDA')\n",
                default_timeout=10,
            ).run()
        if app.exception or _app_text(app):
            raise AssertionError((app.exception, _app_text(app)))


def test_unavailable_and_every_client_failure_are_safe_and_optional() -> None:
    outcomes: tuple[_read_api.ScoredCandidatesApiResult, ...] = (
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
        with patch(
            "ui.institutional_holdings._read_api.load_scored_candidates",
            return_value=outcome,
        ):
            app = AppTest.from_string(
                "from ui.institutional_holdings import _render_score_context\n"
                "_render_score_context('NVDA')\n",
                default_timeout=10,
            ).run()
        if app.exception:
            raise AssertionError((outcome, app.exception))
        rendered = _app_text(app)
        if "籌碼評分脈絡暫時無法使用" not in rendered:
            raise AssertionError((outcome, rendered))
        if str(outcome.reason) in rendered:
            raise AssertionError(f"raw reason leaked: {outcome.reason}")


def test_provider_and_embedded_detail_continue_when_score_feed_fails() -> None:
    outcome = _read_api.ScoredCandidatesApiFailure("deadline_exceeded")
    with (
        patch("ui.institutional_holdings._load", return_value=_provider_data()) as provider,
        patch(
            "ui.institutional_holdings._read_api.load_scored_candidates",
            return_value=outcome,
        ) as score_loader,
    ):
        app = AppTest.from_string(
            "from ui.institutional_holdings import render_for\n"
            "render_for('nvda')\n",
            default_timeout=10,
        ).run()
    if app.exception:
        raise AssertionError(app.exception)
    if provider.call_count != 1 or score_loader.call_count != 1:
        raise AssertionError((provider.call_count, score_loader.call_count))
    rendered = _app_text(app)
    for expected in ("NVDA 持股結構", "fixture-provider", "籌碼評分脈絡暫時無法使用"):
        if expected not in rendered:
            raise AssertionError(rendered)


def test_source_has_one_fixed_client_call_and_no_local_scored_fallback() -> None:
    path = ROOT / "ui" / "institutional_holdings.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_render_score_context"
    )
    segment = ast.get_source_segment(source, function) or ""
    if 'candidate_output_path("scored_candidates.json")' in segment:
        raise AssertionError("institutional context retained local scored fallback")
    if segment.count("load_scored_candidates()") != 1:
        raise AssertionError("institutional context must load one fixed scored feed")


def main() -> None:
    tests = (
        test_available_match_no_match_and_empty_are_distinct,
        test_unavailable_and_every_client_failure_are_safe_and_optional,
        test_provider_and_embedded_detail_continue_when_score_feed_fails,
        test_source_has_one_fixed_client_call_and_no_local_scored_fallback,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
