#!/usr/bin/env python3
"""Focused contracts for Phase 5E Options Cockpit IV-history adoption."""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import iv_history  # noqa: E402
from ui import _components, _read_api, options_cockpit  # noqa: E402


def _points(count: int) -> tuple[_read_api.IvHistoryPoint, ...]:
    dates = pd.bdate_range(end="2026-08-03", periods=count)
    return tuple(
        _read_api.IvHistoryPoint(day.date().isoformat(), 0.20 + index / 1000)
        for index, day in enumerate(dates)
    )


def test_available_points_use_one_api_read_and_the_pure_calculator() -> None:
    points = _points(40)
    outcome = _read_api.IvHistoryApiAvailable("NVDA", points)
    expected = iv_history.iv_percentile_from_series(
        {point.as_of: point.iv for point in points},
        0.25,
    )
    with (
        patch("ui.options_cockpit._read_api.load_iv_history", return_value=outcome) as loader,
        patch("scripts.iv_history._load", side_effect=AssertionError("local read")),
        patch("scripts.iv_history.iv_percentile", side_effect=AssertionError("local percentile")),
    ):
        state = options_cockpit._load_cockpit_iv_history("nvda", 0.25)
    if loader.call_args_list != [(("nvda",), {})]:
        raise AssertionError(loader.call_args_list)
    if state.status != "api_available" or state.reason is not None:
        raise AssertionError(state)
    if len(state.frame) != 40 or state.frame.iloc[-1]["iv"] != points[-1].iv:
        raise AssertionError(state.frame)
    for field in ("rank", "percentile", "n_days", "accumulating"):
        if getattr(state, field) != expected[field]:
            raise AssertionError((field, getattr(state, field), expected[field]))


def test_empty_unavailable_failure_invalid_and_unexpected_never_fallback() -> None:
    outcomes: tuple[tuple[object, str, str | None], ...] = (
        (_read_api.IvHistoryApiAvailable("NVDA", ()), "api_available", None),
        *(
            (_read_api.IvHistoryApiUnavailable("NVDA", reason), "api_unavailable", reason)
            for reason in sorted(_components.ARTIFACT_REASON_CODES)
        ),
        *(
            (_read_api.IvHistoryApiFailure("NVDA", reason), "api_failure", reason)
            for reason in sorted(_components.CLIENT_FAILURE_REASON_CODES)
        ),
        (_read_api.IvHistoryApiInvalidTicker(), "invalid_ticker", "invalid_ticker"),
        (object(), "api_failure", "invalid_envelope"),
    )
    for outcome, expected_status, expected_reason in outcomes:
        with (
            patch("ui.options_cockpit._read_api.load_iv_history", return_value=outcome),
            patch("ui.options_cockpit._shared.load_json", side_effect=AssertionError("fallback")),
            patch("scripts.iv_history._load", side_effect=AssertionError("local read")),
            patch("scripts.iv_history.iv_percentile", side_effect=AssertionError("local percentile")),
        ):
            state = options_cockpit._load_cockpit_iv_history("NVDA", 0.42)
        if (
            state.status != expected_status
            or state.reason != expected_reason
            or not state.frame.empty
            or not state.accumulating
            or state.rank is not None
            or state.percentile is not None
            or state.n_days != 0
        ):
            raise AssertionError((outcome, state))


def test_projection_uses_api_history_or_explicit_realized_proxy_only() -> None:
    complete = options_cockpit.CockpitIvHistoryState(
        status="api_available",
        frame=pd.DataFrame(columns=["date", "iv"]),
        rank=25.0,
        percentile=35.0,
        accumulating=False,
        n_days=252,
        reason=None,
    )
    projection = options_cockpit._cockpit_iv_projection(
        complete,
        {"iv_percentile": 99.0, "iv_percentile_source": "iv_history (252d)"},
    )
    if projection != (25.0, 35.0, "iv_history", False, 252):
        raise AssertionError(projection)

    accumulating = options_cockpit.CockpitIvHistoryState(
        status="api_available",
        frame=pd.DataFrame(columns=["date", "iv"]),
        rank=None,
        percentile=None,
        accumulating=True,
        n_days=3,
        reason=None,
    )
    proxy = options_cockpit._cockpit_iv_projection(
        accumulating,
        {"iv_percentile": 47.0, "iv_percentile_source": "realized_vol_proxy"},
    )
    if proxy != (None, 47.0, "realized_vol_proxy", True, 3):
        raise AssertionError(proxy)
    forbidden_local = options_cockpit._cockpit_iv_projection(
        accumulating,
        {"iv_percentile": 91.0, "iv_percentile_source": "iv_history (60d)"},
    )
    if forbidden_local != (None, None, "iv_history_accumulating", True, 3):
        raise AssertionError(forbidden_local)

    unavailable = options_cockpit.CockpitIvHistoryState(
        status="api_failure",
        frame=pd.DataFrame(columns=["date", "iv"]),
        rank=None,
        percentile=None,
        accumulating=True,
        n_days=0,
        reason="connect_error",
    )
    no_fallback = options_cockpit._cockpit_iv_projection(
        unavailable,
        {"iv_percentile": 91.0, "iv_percentile_source": "iv_history (60d)"},
    )
    if no_fallback != (None, None, "iv_history_unavailable", True, 0):
        raise AssertionError(no_fallback)


def test_display_copy_distinguishes_safe_states_without_raw_reason() -> None:
    base = pd.DataFrame(columns=["date", "iv"])
    cases = (
        ("api_available", None, "尚無 iv_history 快照"),
        ("api_unavailable", "missing", "IV 歷史資料目前無法使用"),
        ("api_failure", "connect_error", "IV 歷史服務目前無法使用"),
        ("api_failure", "response_too_large", "IV 歷史資料超過安全讀取上限"),
        ("invalid_ticker", "invalid_ticker", "此代號無法讀取 IV 歷史"),
    )
    for status, reason, expected in cases:
        display = options_cockpit._iv_history_display_state(
            base,
            atm_iv=None,
            iv_rank_source="realized_vol_proxy",
            iv_rank_n_days=0,
            iv_rank_accumulating=True,
            is_demo=False,
            iv_history_status=status,
            iv_history_reason=reason,
        )
        if expected not in display["caption"]:
            raise AssertionError((status, display))
        if not display["show_section"]:
            raise AssertionError((status, display))
        if reason and reason in display["caption"]:
            raise AssertionError(display)


def test_demo_and_provider_cache_contracts_are_preserved() -> None:
    demo = options_cockpit._demo_provider("NVDA")
    if demo.iv_history.empty or demo.iv_history_status != "api_available":
        raise AssertionError(demo)
    source = inspect.getsource(options_cockpit._live_provider)
    if "ttl=900" not in source or source.count("_load_cockpit_iv_history(") != 1:
        raise AssertionError(source)
    for preserved in ("mo.analyze(ticker)", "of.analyze_options(ticker)", "mo_ui._chart_data(ticker)"):
        if preserved not in source:
            raise AssertionError(f"missing preserved provider: {preserved}")


def test_source_has_fixed_client_pure_calculator_and_no_direct_local_read() -> None:
    path = ROOT / "ui" / "options_cockpit.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if "_load_iv_series" in functions:
        raise AssertionError("Cockpit retained its direct IV artifact reader")
    resolver = functions["_load_cockpit_iv_history"]
    if resolver.count("_read_api.load_iv_history(ticker)") != 1:
        raise AssertionError(resolver)
    if "iv_percentile_from_series" not in resolver:
        raise AssertionError("Cockpit does not reuse the pure IV calculator")
    live = functions["_live_provider"]
    for forbidden in (
        "_load_iv_series",
        "ivh.iv_percentile(",
        'REPORTS_DIR / "iv_history"',
        "_shared.load_json",
    ):
        if forbidden in resolver or forbidden in live:
            raise AssertionError(f"Cockpit retained local IV presentation read: {forbidden}")


def main() -> None:
    tests = (
        test_available_points_use_one_api_read_and_the_pure_calculator,
        test_empty_unavailable_failure_invalid_and_unexpected_never_fallback,
        test_projection_uses_api_history_or_explicit_realized_proxy_only,
        test_display_copy_distinguishes_safe_states_without_raw_reason,
        test_demo_and_provider_cache_contracts_are_preserved,
        test_source_has_fixed_client_pure_calculator_and_no_direct_local_read,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
