#!/usr/bin/env python3
"""Focused contracts for Phase 5F Options Cockpit Social quick-picks."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.models import (  # noqa: E402
    OptionsFlowFeedData,
    ScoredCandidatesFeedData,
    SocialIntelligenceData,
)
from ui import _components, _read_api  # noqa: E402


def _social(market: str = "US", *, empty: bool = False) -> SocialIntelligenceData:
    tickers = [] if empty else [
        {
            "ticker": "SOCIAL",
            "mentioned_by": ["fixture"],
            "citations": [],
            "skew": "bullish",
            "conviction": "high",
            "note": "bounded fixture",
            "platform_validation": {
                "in_ranked_candidates": True,
                "rank_score": 88.0,
                "rank_bucket": "priority",
                "last_price": 123.0,
                "options_flow_score": 77.0,
                "options_direction": "bullish",
            },
            "labels": {
                "x_mentioned": True,
                "agent_reach": True,
                "retail_heat": False,
                "crowded": False,
                "early_signal": True,
                "paid_data_needed": False,
            },
        }
    ]
    return SocialIntelligenceData.model_validate(
        {
            "as_of_date": "2026-08-04",
            "generated_at": "2026-08-04T02:03:04+00:00",
            "market": market,
            "source_statuses": {
                "agent_reach": {
                    "status": "ok",
                    "note": "fixture",
                },
            },
            "tickers": tickers,
        },
        strict=True,
    )


def _scored_empty() -> ScoredCandidatesFeedData:
    return ScoredCandidatesFeedData.model_validate(
        {"scan_date": "2026-08-04", "candidates": []},
        strict=True,
    )


def _flow_empty() -> OptionsFlowFeedData:
    return OptionsFlowFeedData.model_validate(
        {
            "generated_at": "2026-08-04T02:03:04+00:00",
            "as_of": "2026-08-04",
            "provider": "fixture",
            "universe_size": 1,
            "min_notional": 250_000,
            "signal_count": 0,
            "signals": [],
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
                    "symbol": "LEGACY",
                    "mentioned_by": ["legacy"],
                    "count": 1,
                    "skew": "bullish",
                }
            ]
        }
    raise AssertionError(f"unexpected local read: {path}")


def _render(outcome: _read_api.SocialIntelligenceApiResult) -> tuple[AppTest, int]:
    with (
        patch(
            "ui.options_cockpit._read_api.load_social_intelligence",
            return_value=outcome,
        ) as loader,
        patch(
            "ui.options_cockpit._read_api.load_scored_candidates",
            return_value=_read_api.ScoredCandidatesApiAvailable(_scored_empty()),
        ),
        patch(
            "ui.options_cockpit._read_api.load_options_flow",
            return_value=_read_api.OptionsFlowApiAvailable(_flow_empty()),
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


def test_available_us_uses_social_api_and_not_legacy() -> None:
    app, calls = _render(
        _read_api.SocialIntelligenceApiAvailable(_social())
    )
    if app.exception or calls != 1 or not app.selectbox:
        raise AssertionError((app.exception, calls))
    options = "\n".join(str(option) for option in app.selectbox[0].options)
    for expected in ("IBKR", "SOCIAL", "X Mentioned", "Agent Reach", "Early Signal"):
        if expected not in options:
            raise AssertionError(options)
    if "LEGACY" in options:
        raise AssertionError(options)


def test_available_empty_and_other_market_keep_legacy_without_failure_copy() -> None:
    for snapshot in (_social(empty=True), _social("CRYPTO")):
        app, calls = _render(_read_api.SocialIntelligenceApiAvailable(snapshot))
        if app.exception or calls != 1:
            raise AssertionError((snapshot.market, app.exception, calls))
        options = "\n".join(str(option) for option in app.selectbox[0].options)
        rendered = _app_text(app)
        if "IBKR" not in options or "LEGACY" not in options or "SOCIAL" in options:
            raise AssertionError((snapshot.market, options))
        if "社群快選資料目前無法使用" in rendered or "社群快選服務目前無法使用" in rendered:
            raise AssertionError((snapshot.market, rendered))


def test_unavailable_and_every_failure_keep_siblings_with_safe_notice() -> None:
    outcomes: tuple[_read_api.SocialIntelligenceApiResult, ...] = (
        *(
            _read_api.SocialIntelligenceApiUnavailable(reason)
            for reason in sorted(_components.ARTIFACT_REASON_CODES)
        ),
        *(
            _read_api.SocialIntelligenceApiFailure(reason)
            for reason in sorted(_components.CLIENT_FAILURE_REASON_CODES)
        ),
    )
    for outcome in outcomes:
        app, calls = _render(outcome)
        if app.exception or calls != 1:
            raise AssertionError((outcome, app.exception, calls))
        options = "\n".join(str(option) for option in app.selectbox[0].options)
        rendered = _app_text(app)
        if "IBKR" not in options or "LEGACY" not in options:
            raise AssertionError((outcome, options))
        expected = (
            "社群快選資料目前無法使用"
            if isinstance(outcome, _read_api.SocialIntelligenceApiUnavailable)
            else "社群快選服務目前無法使用"
        )
        if expected not in rendered or outcome.reason in rendered:
            raise AssertionError((outcome, rendered))


def test_source_has_one_fixed_client_no_local_social_and_embedded_isolation() -> None:
    path = ROOT / "ui" / "options_cockpit.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    quickpick = functions["_watchlist_quickpick"]
    if quickpick.count("load_social_intelligence()") != 1:
        raise AssertionError("Cockpit must issue one fixed Social read")
    if 'reports / "social_intelligence" / "latest.json"' in quickpick:
        raise AssertionError("Cockpit retained its local Social presentation read")
    for preserved in (
        'reports / "watchlist.json"',
        'reports / "x_influencer_picks.json"',
        "load_scored_candidates()",
        "load_options_flow()",
    ):
        if preserved not in quickpick:
            raise AssertionError(f"Cockpit removed sibling source: {preserved}")
    if "_watchlist_quickpick" in functions["render_for"] or "load_social_intelligence" in functions["render_for"]:
        raise AssertionError("embedded Cockpit must not load Social quick-picks")


def main() -> None:
    tests = (
        test_available_us_uses_social_api_and_not_legacy,
        test_available_empty_and_other_market_keep_legacy_without_failure_copy,
        test_unavailable_and_every_failure_keep_siblings_with_safe_notice,
        test_source_has_one_fixed_client_no_local_social_and_embedded_isolation,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
