#!/usr/bin/env python3
"""Focused contracts for Phase 5B Options Cockpit Options Flow quick-picks."""

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


def _flow(*rows: tuple[str, str, float]) -> OptionsFlowFeedData:
    return OptionsFlowFeedData.model_validate(
        {
            "generated_at": "2026-08-02T02:03:04+00:00",
            "as_of": "2026-08-02",
            "provider": "fixture",
            "universe_size": max(len(rows), 1),
            "min_notional": 250_000,
            "signal_count": len(rows),
            "signals": [
                {
                    "ticker": ticker,
                    "direction": direction,
                    "flow_score": score,
                    "est_notional_usd": 1_000_000,
                    "biggest": None,
                    "expiry": None,
                    "max_voi": 2.0,
                    "high_voi_strikes": 1,
                    "call_put_ratio": 2.0,
                    "put_call_ratio": 0.5,
                    "tags": [],
                }
                for ticker, direction, score in rows
            ],
        },
        strict=True,
    )


def _scored_empty() -> ScoredCandidatesFeedData:
    return ScoredCandidatesFeedData.model_validate(
        {"scan_date": "2026-08-02", "candidates": []},
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


def _render(outcome: _read_api.OptionsFlowApiResult) -> tuple[AppTest, int]:
    with (
        patch(
            "ui.options_cockpit._read_api.load_scored_candidates",
            return_value=_read_api.ScoredCandidatesApiAvailable(_scored_empty()),
        ),
        patch(
            "ui.options_cockpit._read_api.load_social_intelligence",
            return_value=_read_api.SocialIntelligenceApiUnavailable("missing"),
        ),
        patch(
            "ui.options_cockpit._read_api.load_options_flow",
            return_value=outcome,
        ) as loader,
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


def test_available_uses_feed_order_caps_five_and_preserves_other_sources() -> None:
    outcome = _read_api.OptionsFlowApiAvailable(
        _flow(
            ("AAA", "bullish", 99.0),
            ("BBB", "bearish", 90.0),
            ("CCC", "bullish", 80.0),
            ("DDD", "bearish", 70.0),
            ("EEE", "bullish", 60.0),
            ("FFF", "bearish", 50.0),
        )
    )
    app, calls = _render(outcome)
    if app.exception or calls != 1 or not app.selectbox:
        raise AssertionError((app.exception, calls))
    options = "\n".join(str(option) for option in app.selectbox[0].options)
    for expected in ("IBKR", "SOCIAL", "AAA", "BBB", "EEE", "偏多", "偏空"):
        if expected not in options:
            raise AssertionError(options)
    if "FFF" in options or options.index("AAA") > options.index("BBB"):
        raise AssertionError(options)


def test_available_empty_is_authoritative_not_failure() -> None:
    app, calls = _render(_read_api.OptionsFlowApiAvailable(_flow()))
    if app.exception or calls != 1:
        raise AssertionError((app.exception, calls))
    rendered = _app_text(app)
    if "異常流 0" not in rendered:
        raise AssertionError(rendered)
    if "異常流資料目前無法使用" in rendered or "異常流服務目前無法使用" in rendered:
        raise AssertionError(rendered)


def test_unavailable_and_every_failure_keep_other_sources_with_safe_notice() -> None:
    outcomes: tuple[_read_api.OptionsFlowApiResult, ...] = (
        *(
            _read_api.OptionsFlowApiUnavailable(reason)
            for reason in sorted(_components.ARTIFACT_REASON_CODES)
        ),
        *(
            _read_api.OptionsFlowApiFailure(reason)
            for reason in sorted(_components.CLIENT_FAILURE_REASON_CODES)
        ),
    )
    for outcome in outcomes:
        app, calls = _render(outcome)
        if app.exception or calls != 1:
            raise AssertionError((outcome, app.exception, calls))
        options = "\n".join(str(option) for option in app.selectbox[0].options)
        rendered = _app_text(app)
        for expected in ("IBKR", "SOCIAL"):
            if expected not in options:
                raise AssertionError((outcome, options))
        expected_notice = (
            "異常流資料目前無法使用"
            if isinstance(outcome, _read_api.OptionsFlowApiUnavailable)
            else "異常流服務目前無法使用"
        )
        if expected_notice not in rendered or outcome.reason in rendered:
            raise AssertionError((outcome, rendered))


def test_source_has_one_fixed_client_no_local_fallback_and_embedded_isolation() -> None:
    path = ROOT / "ui" / "options_cockpit.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    quickpick = functions["_watchlist_quickpick"]
    if quickpick.count("load_options_flow()") != 1:
        raise AssertionError("Options Cockpit must load one fixed Options Flow feed")
    if 'reports / "options_flow" / "latest.json"' in quickpick:
        raise AssertionError("Options Cockpit retained local Options Flow quick picks")
    for preserved in (
        'reports / "watchlist.json"',
        "_read_api.load_social_intelligence()",
        'reports / "x_influencer_picks.json"',
        "_read_api.load_scored_candidates()",
    ):
        if preserved not in quickpick:
            raise AssertionError(f"Options Cockpit removed sibling source: {preserved}")
    if "_watchlist_quickpick" in functions["render_for"] or "load_options_flow" in functions["render_for"]:
        raise AssertionError("embedded cockpit must not load quick-pick Options Flow")


def main() -> None:
    tests = (
        test_available_uses_feed_order_caps_five_and_preserves_other_sources,
        test_available_empty_is_authoritative_not_failure,
        test_unavailable_and_every_failure_keep_other_sources_with_safe_notice,
        test_source_has_one_fixed_client_no_local_fallback_and_embedded_isolation,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
