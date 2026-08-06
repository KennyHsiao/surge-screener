#!/usr/bin/env python3
"""Focused contracts for Phase 4I Analytics DB ranked defaults."""

from __future__ import annotations

import ast
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.models import RankedCandidatesFeedData  # noqa: E402
from ui import _components, _read_api, analytics_db  # noqa: E402


def _feed(count: int = 12) -> RankedCandidatesFeedData:
    return RankedCandidatesFeedData.model_validate(
        {
            "scan_date": "2026-08-01",
            "generated_at": "2026-08-01T02:03:04+00:00",
            "candidates": [
                {
                    "ticker": f"T{index:02d}",
                    "rank_score": 100.0 - index,
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
                for index in range(count)
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


def _center_patches() -> ExitStack:
    stack = ExitStack()
    stack.enter_context(
        patch("ui.analytics_db._load_data_health_status", return_value=None)
    )
    stack.enter_context(
        patch("ui.analytics_db._data_health_refresh_is_active", return_value=False)
    )
    stack.enter_context(patch("ui.analytics_db._render_refresh_result", return_value=None))
    stack.enter_context(
        patch("ui.analytics_db._render_data_health_refresh_status", return_value=None)
    )
    return stack


def test_ranked_defaults_use_validated_order_and_limit() -> None:
    available = _read_api.RankedCandidatesApiAvailable(_feed())
    if analytics_db._ranked_tickers(available, limit=10) != [
        f"T{index:02d}" for index in range(10)
    ]:
        raise AssertionError("ranked order/limit was not preserved")
    if analytics_db._ranked_tickers(available, limit=0):
        raise AssertionError("zero limit must return no defaults")
    if analytics_db._ranked_tickers(
        _read_api.RankedCandidatesApiAvailable(_feed(0)), limit=10
    ):
        raise AssertionError("available-empty must return no defaults")


def test_unavailable_and_every_failure_keep_manual_input_without_fallback() -> None:
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
            _center_patches(),
            patch(
                "ui.analytics_db._read_api.load_ranked_candidates",
                return_value=outcome,
            ) as loader,
        ):
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from ui.analytics_db import _render_refresh_center\n"
                "_render_refresh_center(Path('/tmp/analytics-fixture'))\n",
                default_timeout=10,
            ).run()
        if app.exception or loader.call_count != 1:
            raise AssertionError((outcome, app.exception, loader.call_count))
        rendered = _app_text(app)
        if "仍可手動輸入 ticker" not in rendered:
            raise AssertionError((outcome, rendered))
        if str(outcome.reason) in rendered:
            raise AssertionError(f"raw reason leaked: {outcome.reason}")
        if not app.text_input or app.text_input[0].value:
            raise AssertionError("manual ticker field must remain present with empty default")


def test_manual_fundamental_refresh_remains_operational() -> None:
    available = _read_api.RankedCandidatesApiAvailable(_feed(2))
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        with (
            _center_patches(),
            patch(
                "ui.analytics_db._read_api.load_ranked_candidates",
                return_value=available,
            ) as loader,
            patch(
                "ui.analytics_db._refresh_fundamentals",
                return_value={"updated": 2},
            ) as refresh,
            patch("ui.analytics_db.st.rerun", return_value=None),
        ):
            app = AppTest.from_string(
                "from pathlib import Path\n"
                "from ui.analytics_db import _render_refresh_center\n"
                f"_render_refresh_center(Path({str(root)!r}))\n",
                default_timeout=10,
            ).run()
            app.text_input[0].input("nvda, amd")
            next(button for button in app.button if button.label == "刷新基本面").click()
            app = app.run()
    if app.exception:
        raise AssertionError(app.exception)
    if loader.call_count != 2:
        raise AssertionError(f"expected one ranked request per rerun, got {loader.call_count}")
    refresh.assert_called_once_with(root, ["NVDA", "AMD"])


def test_success_and_database_error_page_branches_load_once() -> None:
    available = _read_api.RankedCandidatesApiAvailable(_feed(1))
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for catalog in ([], RuntimeError("db unavailable")):
            with ExitStack() as stack:
                stack.enter_context(_center_patches())
                stack.enter_context(patch("ui.analytics_db._analytics_root", return_value=root))
                catalog_patch = patch("ui.analytics_db._catalog")
                catalog_mock = stack.enter_context(catalog_patch)
                if isinstance(catalog, Exception):
                    catalog_mock.side_effect = catalog
                else:
                    catalog_mock.return_value = catalog
                for name in (
                    "_render_checks",
                    "_status",
                    "_catalog_table",
                    "_table_browser",
                    "_iv_chart",
                    "_performance",
                    "_sql_console",
                ):
                    stack.enter_context(patch(f"ui.analytics_db.{name}", return_value=None))
                loader = stack.enter_context(
                    patch(
                        "ui.analytics_db._read_api.load_ranked_candidates",
                        return_value=available,
                    )
                )
                app = AppTest.from_string(
                    "from ui.analytics_db import render\nrender()\n",
                    default_timeout=10,
                ).run()
            if app.exception or loader.call_count != 1:
                raise AssertionError((catalog, app.exception, loader.call_count))


def test_source_has_one_fixed_call_and_no_local_ranked_fallback() -> None:
    path = ROOT / "ui" / "analytics_db.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"_ranked_tickers", "_render_refresh_center"}
    }
    if 'candidate_output_path("ranked_candidates.json")' in functions["_ranked_tickers"]:
        raise AssertionError("Analytics DB defaults retained local ranked fallback")
    if functions["_render_refresh_center"].count("load_ranked_candidates()") != 1:
        raise AssertionError("refresh center must load one fixed ranked feed")


def main() -> None:
    tests = (
        test_ranked_defaults_use_validated_order_and_limit,
        test_unavailable_and_every_failure_keep_manual_input_without_fallback,
        test_manual_fundamental_refresh_remains_operational,
        test_success_and_database_error_page_branches_load_once,
        test_source_has_one_fixed_call_and_no_local_ranked_fallback,
    )
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
