#!/usr/bin/env python3
"""Focused contracts for Phase 4O Options Cockpit scored quick-picks."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.models import OptionsFlowFeedData, ScoredCandidatesFeedData  # noqa: E402
from ui import _components, _read_api  # noqa: E402


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


def _options_flow() -> OptionsFlowFeedData:
    return OptionsFlowFeedData.model_validate(
        {
            "generated_at": "2026-08-02T02:03:04+00:00",
            "as_of": "2026-08-02",
            "provider": "fixture",
            "universe_size": 1,
            "min_notional": 250_000,
            "signal_count": 1,
            "signals": [
                {
                    "ticker": "FLOW",
                    "direction": "bullish",
                    "flow_score": 88.0,
                    "est_notional_usd": 1_000_000,
                    "biggest": None,
                    "expiry": None,
                    "max_voi": 2.0,
                    "high_voi_strikes": 1,
                    "call_put_ratio": 2.0,
                    "put_call_ratio": 0.5,
                    "tags": [],
                }
            ],
        },
        strict=True,
    )


def _local_sources(path: str) -> dict[str, object]:
    if path.endswith("reports/watchlist.json"):
        return {"tickers": [{"ticker": "IBKR", "scan_kinds": ["gain"]}]}
    if path.endswith("reports/x_influencer_picks.json"):
        return {
            "tickers": [
                {
                    "symbol": "SOCIAL",
                    "mentioned_by": ["fixture"],
                    "count": 1,
                    "skew": "bullish",
                }
            ]
        }
    raise AssertionError(f"unexpected local read: {path}")


def _render(outcome: _read_api.ScoredCandidatesApiResult) -> tuple[AppTest, int]:
    with (
        patch(
            "ui.options_cockpit._read_api.load_scored_candidates",
            return_value=outcome,
        ) as loader,
        patch(
            "ui.options_cockpit._read_api.load_options_flow",
            return_value=_read_api.OptionsFlowApiAvailable(_options_flow()),
        ),
        patch(
            "ui.options_cockpit._read_api.load_social_intelligence",
            return_value=_read_api.SocialIntelligenceApiUnavailable("missing"),
        ),
        patch("ui.options_cockpit._shared.load_json", side_effect=_local_sources),
    ):
        app = AppTest.from_string(
            "from ui.options_cockpit import _watchlist_quickpick\n"
            "_watchlist_quickpick()\n",
            default_timeout=10,
        ).run()
    return app, loader.call_count


def _app_text(app: AppTest) -> str:
    values = [
        str(element.value)
        for collection in (app.caption, app.warning, app.info, app.error, app.markdown)
        for element in collection
    ]
    values.extend(str(element.label) for element in app.expander)
    return "\n".join(values)


def test_available_official_rows_use_feed_order_and_preserve_other_sources() -> None:
    outcome = _read_api.ScoredCandidatesApiAvailable(
        _feed(
            ("REJECTED", "REJECT", 99.0),
            ("NVDA", "NEEDS_LAYER_2", 90.0),
            ("AMD", "WATCHLIST", 80.0),
        )
    )
    app, calls = _render(outcome)
    if app.exception or calls != 1:
        raise AssertionError((app.exception, calls))
    if not app.selectbox:
        raise AssertionError("quick-pick selector did not render")
    options = list(app.selectbox[0].options)
    rendered_options = "\n".join(str(option) for option in options)
    for expected in ("IBKR", "SOCIAL", "FLOW", "NVDA", "AMD", "2026-08-02"):
        if expected not in rendered_options:
            raise AssertionError(rendered_options)
    if "REJECTED" in rendered_options:
        raise AssertionError("official scored rows included a REJECT candidate")
    if rendered_options.index("NVDA") > rendered_options.index("AMD"):
        raise AssertionError("strict scored feed order was not preserved")


def test_reject_only_feed_is_labeled_and_available_empty_is_not_failure() -> None:
    rejected = _read_api.ScoredCandidatesApiAvailable(
        _feed(
            ("TSLA", "REJECT", 90.0),
            ("AMD", "REJECT", 80.0),
        )
    )
    app, calls = _render(rejected)
    if app.exception or calls != 1:
        raise AssertionError((app.exception, calls))
    rendered = _app_text(app)
    options = "\n".join(str(option) for option in app.selectbox[0].options)
    if "❌REJECT" not in options or "非推薦" not in rendered:
        raise AssertionError((options, rendered))

    empty, calls = _render(_read_api.ScoredCandidatesApiAvailable(_feed()))
    if empty.exception or calls != 1:
        raise AssertionError((empty.exception, calls))
    rendered = _app_text(empty)
    if "篩選器 0" not in rendered:
        raise AssertionError(rendered)
    if "候選資料目前無法使用" in rendered or "候選服務目前無法使用" in rendered:
        raise AssertionError("available-empty was rendered as a failure")


def test_unavailable_and_every_failure_keep_other_quickpick_sources() -> None:
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
        app, calls = _render(outcome)
        if app.exception or calls != 1:
            raise AssertionError((outcome, app.exception, calls))
        rendered = _app_text(app)
        options = "\n".join(str(option) for option in app.selectbox[0].options)
        for expected in ("IBKR", "SOCIAL", "FLOW"):
            if expected not in options:
                raise AssertionError((outcome, options))
        expected = (
            "篩選候選資料目前無法使用"
            if isinstance(outcome, _read_api.ScoredCandidatesApiUnavailable)
            else "篩選候選服務目前無法使用"
        )
        if expected not in rendered:
            raise AssertionError((outcome, rendered))
        if outcome.reason in rendered:
            raise AssertionError(f"raw reason leaked: {outcome.reason}")


def test_source_has_one_fixed_client_no_scored_fallback_and_embedded_isolation() -> None:
    path = ROOT / "ui" / "options_cockpit.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    quickpick = functions["_watchlist_quickpick"]
    embedded = functions["render_for"]
    if 'candidate_output_path("scored_candidates.json")' in quickpick:
        raise AssertionError("Options Cockpit retained local scored fallback")
    if quickpick.count("load_scored_candidates()") != 1:
        raise AssertionError("Options Cockpit must load one fixed scored feed")
    if "_watchlist_quickpick" in embedded or "load_scored_candidates" in embedded:
        raise AssertionError("embedded cockpit must not load quick-pick candidates")
    for preserved in (
        'reports / "watchlist.json"',
        "_read_api.load_social_intelligence()",
        'reports / "x_influencer_picks.json"',
        "_read_api.load_options_flow()",
    ):
        if preserved not in quickpick:
            raise AssertionError(f"Options Cockpit removed sibling source: {preserved}")


def main() -> None:
    tests = (
        test_available_official_rows_use_feed_order_and_preserve_other_sources,
        test_reject_only_feed_is_labeled_and_available_empty_is_not_failure,
        test_unavailable_and_every_failure_keep_other_quickpick_sources,
        test_source_has_one_fixed_client_no_scored_fallback_and_embedded_isolation,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
