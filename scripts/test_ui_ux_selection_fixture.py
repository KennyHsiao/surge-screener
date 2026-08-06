#!/usr/bin/env python3
"""Contract and real-render checks for the UX-1B selection fixture."""

from __future__ import annotations

import json
import os
import secrets
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import ui_ux_fixtures as fixtures  # noqa: E402


EXPECTED_CASES = {
    "risk-guard-controls": ("risk-guard", "risk_guard.render", (".st-key-rg_source",)),
    "institutions-controls": ("institutions", "institutions.render", (".st-key-inst_view",)),
    "options-cockpit-controls": (
        "options-cockpit",
        "options_cockpit.render",
        (".st-key-cockpit_price_view_NVDA",),
    ),
    "radar-controls": (
        "radar",
        "radar.render",
        (".st-key-radar_source", ".st-key-radar_view"),
    ),
    "knowledge-graph-controls": (
        "knowledge-graph",
        "knowledge_graph.render",
        (".st-key-kg_view_mode", ".st-key-kg_label_mode"),
    ),
    "ai-chat-settings-controls": (
        "today-decision",
        "today_decision.render",
        (".st-key-ai_chat_mode",),
    ),
    "retro-controls": (
        "retro-analysis",
        "retro_analysis.render",
        (".st-key-retro_validation_lane",),
    ),
    "analytics-controls": (
        "analytics-db",
        "analytics_db.render",
        (".st-key-adb_table",),
    ),
    "stock-checkup-controls": (
        "stock-checkup",
        "stock_checkup.render",
        (".st-key-checkup_mode",),
    ),
}

EXPECTED_VIEWPORTS = {
    "desktop": (1440, 900),
    "tablet": (768, 1024),
    "mobile": (390, 844),
    "narrow": (320, 844),
}


@contextmanager
def _owned_environment() -> Iterator[None]:
    with tempfile.TemporaryDirectory(prefix="surge-ux1b-selection-") as temp:
        run_dir = Path(temp).resolve()
        fixture_root = run_dir / "fixture-root"
        fixture_root.mkdir()
        token = secrets.token_urlsafe(32)
        (run_dir / fixtures.OWNERSHIP_MARKER).write_text(token, encoding="utf-8")
        values = {
            "QUANT_RADAR_UX0_FIXTURES": "1",
            "QUANT_RADAR_UX0_FIXTURE_ROOT": str(fixture_root),
            "QUANT_RADAR_UX0_CALLS_PATH": str(run_dir / "fixture-calls.json"),
            "QUANT_RADAR_UX0_RUN_TOKEN": token,
            "QUANT_RADAR_UX0_FIXED_NOW": fixtures.FIXED_NOW,
            "SURGE_RUNTIME_DIR": str(fixture_root),
            "SURGE_CANDIDATE_OUTPUT_DIR": str(fixture_root / "candidates"),
            "SURGE_AI_CHAT_DIR": str(fixture_root / "ai-chat"),
            "TZ": "UTC",
        }
        with patch.dict(os.environ, values, clear=False):
            fixtures.bootstrap_fixture_environment()
            yield


def _wrapper(case: str, capture: str) -> str:
    return (
        "from scripts.ui_ux_fixtures import render_selection_case\n"
        f"render_selection_case({case!r}, {capture!r})\n"
    )


def test_selection_catalog_is_exact_and_has_eleven_unique_roots() -> None:
    observed = {
        name: (item.registry_key, item.callable_name, item.root_selectors)
        for name, item in fixtures.SELECTION_CASES.items()
    }
    assert observed == EXPECTED_CASES
    assert dict(fixtures.SELECTION_VIEWPORTS) == EXPECTED_VIEWPORTS
    roots = [root for item in fixtures.SELECTION_CASES.values() for root in item.root_selectors]
    assert len(roots) == 11
    assert len(set(roots)) == 11
    assert len(fixtures.selection_capture_catalog()) == 9 * 4
    assert fixtures._validate_capture_id("radar-controls/desktop") == "radar-controls/desktop"
    for invalid in ("/desktop", "radar-controls/", "../desktop", "case//desktop"):
        try:
            fixtures._validate_capture_id(invalid)
        except fixtures.FixtureConfigurationError:
            pass
        else:
            raise AssertionError(f"accepted invalid capture identity: {invalid}")


def test_selection_routes_are_exact_and_reject_unknown_paths() -> None:
    for case, item in fixtures.SELECTION_CASES.items():
        assert fixtures.selection_case_from_url(f"http://127.0.0.1:18501{item.route}") == case
    for value in (
        "http://127.0.0.1:18501/",
        "http://127.0.0.1:18501/__selection__/invented",
        "https://127.0.0.1:18501/__selection__/radar",
        "http://example.test/__selection__/radar",
    ):
        try:
            fixtures.selection_case_from_url(value)
        except fixtures.FixtureConfigurationError:
            pass
        else:
            raise AssertionError(f"accepted unowned selection URL: {value}")


def test_all_selection_cases_call_real_renderers_and_expose_roots() -> None:
    for case, definition in fixtures.SELECTION_CASES.items():
        capture = f"{case}/desktop"
        app = AppTest.from_string(_wrapper(case, capture), default_timeout=30).run()
        assert not app.exception, (case, app.exception)
        if case == "institutions-controls":
            selectors = [
                widget
                for widget_type in ("button_group", "radio")
                for widget in app.get(widget_type)
                if widget.key == "inst_view"
            ]
            assert len(selectors) == 1, (case, selectors)
            app = selectors[0].set_value("機構持倉 · 機構 → 它持有什麼").run()
            assert not app.exception, (case, app.exception)
        if case == "ai-chat-settings-controls":
            open_buttons = [button for button in app.button if button.key == "ai_chat_open"]
            assert len(open_buttons) == 1, (case, [button.key for button in app.button])
            app = open_buttons[0].click().run()
            assert not app.exception, (case, app.exception)
            mode_controls = [
                widget
                for widget_type in ("button_group", "radio")
                for widget in app.get(widget_type)
                if widget.key == "ai_chat_mode"
            ]
            assert len(mode_controls) == 1, (case, mode_controls)
            app = mode_controls[0].set_value("深度研究").run()
            assert not app.exception, (case, app.exception)
            mode_controls = [
                widget
                for widget_type in ("button_group", "radio")
                for widget in app.get(widget_type)
                if widget.key == "ai_chat_mode"
            ]
            assert len(mode_controls) == 1, (case, mode_controls)
            app = mode_controls[0].set_value("快速問答").run()
            assert not app.exception, (case, app.exception)
        if case == "analytics-controls":
            table_controls = [
                widget
                for widget_type in ("button_group", "selectbox")
                for widget in app.get(widget_type)
                if widget.key == "adb_table"
            ]
            assert len(table_controls) == 1, (case, table_controls)
            app = table_controls[0].set_value("iv_history").run()
            assert not app.exception, (case, app.exception)
            table_controls = [
                widget
                for widget_type in ("button_group", "selectbox")
                for widget in app.get(widget_type)
                if widget.key == "adb_table"
            ]
            assert len(table_controls) == 1, (case, table_controls)
            app = table_controls[0].set_value("candidate_rankings").run()
            assert not app.exception, (case, app.exception)
        snapshot = fixtures.counter_snapshot(capture)
        assert snapshot["identity"]["selectedRegistryKey"] == definition.registry_key
        assert snapshot["identity"]["realCallable"] == definition.callable_name
        rendered_keys = {
            getattr(widget, "key", None)
            for widget_type in ("button_group", "radio", "selectbox")
            for widget in app.get(widget_type)
        }
        for session_key in definition.session_keys:
            assert session_key in app.session_state, (case, session_key)
            assert session_key in rendered_keys, (case, session_key, rendered_keys)
        if case == "radar-controls":
            assert app.session_state["radar_risk"]
            assert app.session_state["radar_rev"]
            assert app.session_state["radar_run_key"] == (
                "手動輸入",
                ("NVDA",),
                False,
            )
        if case == "analytics-controls":
            assert app.session_state["adb_table"] == "candidate_rankings"
            assert "找不到可瀏覽的資料表" not in "\n".join(
                str(item.value) for item in app.info
            )
        fixtures.assert_selection_counter_contract(case, capture)


def test_selection_entrypoint_is_present_and_uses_owned_bootstrap() -> None:
    source = (ROOT / "scripts/ui_ux_selection_fixture_app.py").read_text(encoding="utf-8")
    assert "bootstrap_fixture_environment" in source
    assert "selection_case_from_url" in source
    assert "render_selection_case" in source
    assert "ux1b-selection-ready" in source
    assert 'aria-hidden="true"' in source
    assert 'style="display:none"' in source
    assert "data-render-generation" in source
    assert "runpy.run_path" not in source


def test_analytics_empty_catalog_still_returns_fail_soft() -> None:
    app = AppTest.from_string(
        "from ui import analytics_db\nanalytics_db._table_browser('', [])\n",
        default_timeout=20,
    ).run()
    assert not app.exception, app.exception
    assert any("找不到可瀏覽的資料表" in str(item.value) for item in app.info)


def main() -> int:
    tests = (
        test_selection_catalog_is_exact_and_has_eleven_unique_roots,
        test_selection_routes_are_exact_and_reject_unknown_paths,
        test_selection_entrypoint_is_present_and_uses_owned_bootstrap,
    )
    passed = 0
    for test in tests:
        test()
        passed += 1
        print(f"PASS {test.__name__}")
    with _owned_environment():
        test_all_selection_cases_call_real_renderers_and_expose_roots()
        passed += 1
        print("PASS test_all_selection_cases_call_real_renderers_and_expose_roots")
        test_analytics_empty_catalog_still_returns_fail_soft()
        passed += 1
        print("PASS test_analytics_empty_catalog_still_returns_fail_soft")
    print(f"PASS: {passed} selection fixture tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
