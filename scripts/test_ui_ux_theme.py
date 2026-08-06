#!/usr/bin/env python3
"""Offline contract tests for the UX-1B theme oracle and state gallery."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import ui_ux_theme_matrix as theme  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def raises_contract(callable_) -> None:
    try:
        callable_()
    except theme.ThemeContractError:
        return
    raise AssertionError("theme contract accepted an invalid value")


def test_approved_palette_has_role_specific_contrast() -> None:
    expected = {
        "interactive.primary": "#2563eb",
        "interactive.hover": "#1d4ed8",
        "interactive.active": "#1e40af",
        "interactive.accent": "#60a5fa",
        "interactive.control": "#3b82f6",
        "interactive.disabled": "#6b7280",
        "text.on-primary": "#ffffff",
        "text.disabled": "#8b93a7",
        "border.focus": "#7fe3f0",
    }
    require(dict(theme.APPROVED_TOKENS) == expected, "approved token drift")
    require(
        dict(theme.SURFACE_COLORS)
        == {
            "canvas": "#0e1117",
            "panel": "#1a1f2b",
            "elevated": "#232938",
        },
        "surface projection drift",
    )
    theme.validate_palette_contract(theme.APPROVED_TOKENS, theme.SURFACE_COLORS)
    require(
        2.47 < theme.contrast_ratio("#7fe3f0", "#3b82f6") < 2.49,
        "focus/control direct-adjacency negative changed",
    )


def test_css_color_parser_and_alpha_composition_fail_closed() -> None:
    require(theme.parse_css_color("#60a5fa") == (96, 165, 250, 1.0), "hex parse")
    require(theme.parse_css_color("rgb(96, 165, 250)") == (96, 165, 250, 1.0), "rgb parse")
    require(theme.parse_css_color("rgba(96, 165, 250, 0.5)") == (96, 165, 250, 0.5), "rgba parse")
    require(
        theme.composite_rgba((255, 255, 255, 0.5), (0, 0, 0, 1.0))
        == (128, 128, 128, 1.0),
        "alpha composition",
    )
    for invalid in ("", "transparent", "var(--unknown)", "#fff", "rgb(1 2)", "url(x)"):
        raises_contract(lambda invalid=invalid: theme.parse_css_color(invalid))


def test_static_link_and_selector_contracts_are_exact() -> None:
    css = """
    [data-testid="stMarkdownContainer"] a:link {
      color: #60a5fa;
      text-decoration: underline;
    }
    [data-testid="stMarkdownContainer"] a:visited {
      color: #60a5fa;
      text-decoration: underline;
    }
    [data-testid="stButton"] button[kind="primary"] {
      background-color: #2563eb;
      color: #ffffff;
    }
    """
    theme.validate_link_contract(css)
    rules = theme.validate_css_safety(css)
    require(len(rules) == 3, f"wrong parsed rule count: {rules!r}")

    raises_contract(
        lambda: theme.validate_link_contract(
            css.replace(
                "a:visited {\n      color: #60a5fa",
                "a:visited {\n      color: #c084fc",
            )
        )
    )
    for unsafe in (
        "button { color:#fff; }",
        "a { color:#60a5fa; }",
        ".st-emotion-cache-abc button { color:#fff; }",
        "[data-testid='x'] { background:url(https://example.com/x); }",
        "@import 'https://example.com/x.css';",
    ):
        raises_contract(lambda unsafe=unsafe: theme.validate_css_safety(unsafe))


def test_builder_wrapper_and_selector_record_schema_are_exact() -> None:
    selector = ':where([data-testid="stButton"], [data-testid="stFormSubmitButton"]) button[kind="primary"]'
    wrapped = f"<style>{selector} {{ color: #ffffff !important; }}</style>"
    css = theme.extract_theme_css(wrapped)
    rules = theme.validate_css_safety(css)
    require(len(rules) == 1 and rules[0].selector == selector, ":where comma split")
    owners = tuple(sorted(
        theme.owner_id(surface, "primary") for surface in theme.SURFACE_COLORS
    ))
    record = {
        "selector": selector,
        "property": "color",
        "owners": owners,
        "states": ("default",),
        "important": True,
    }
    normalized = theme.validate_selector_contract(css, (record,))
    require(len(normalized) == 1, "selector contract normalization")
    require(
        theme.selector_owner_contract(normalized)[selector] == owners,
        "selector owner projection",
    )

    for invalid_wrapper in (
        css,
        f'<style media="screen">{css}</style>',
        f"<style>{css}</style><style>{css}</style>",
        f"<div></div><style>{css}</style>",
    ):
        raises_contract(lambda value=invalid_wrapper: theme.extract_theme_css(value))
    for invalid in (
        ({key: value for key, value in record.items() if key != "states"},),
        (record, record),
        ({**record, "owners": owners[:-1]},),
        ({**record, "important": False},),
        ({**record, "states": ("hover",)},),
        ({**record, "owners": (*owners, theme.owner_id("canvas", "signals"))},),
    ):
        raises_contract(lambda value=invalid: theme.validate_selector_contract(css, value))


def test_production_token_projection_is_not_self_derived() -> None:
    tokens = {
        **dict(theme.APPROVED_TOKENS),
        **{f"surface.{name}": value for name, value in theme.SURFACE_COLORS.items()},
        "signal.avoid": "#ef4444",
        "signal.bearish": "#ef553b",
        "feedback.error": "#ef553b",
    }
    theme.validate_design_token_contract(SimpleNamespace(COLOR_TOKENS=tokens))
    bad = dict(tokens)
    bad["interactive.primary"] = "#ef4444"
    raises_contract(
        lambda: theme.validate_design_token_contract(SimpleNamespace(COLOR_TOKENS=bad))
    )


def test_owner_sets_and_important_allowlist_fail_closed() -> None:
    expected = {
        '[data-testid="stButton"] button[kind="primary"]': {
            "canvas-primary",
            "panel-primary",
        }
    }
    actual = {
        '[data-testid="stButton"] button[kind="primary"]': {
            "panel-primary",
            "canvas-primary",
        }
    }
    theme.require_exact_owner_sets(actual, expected)
    raises_contract(
        lambda: theme.require_exact_owner_sets(
            {next(iter(actual)): {"canvas-primary", "orphan-danger"}},
            expected,
        )
    )
    css = '[data-testid="stButton"] button[kind="primary"] { color:#fff !important; }'
    theme.validate_important_allowlist(
        css,
        {('[data-testid="stButton"] button[kind="primary"]', "color")},
    )
    raises_contract(lambda: theme.validate_important_allowlist(css, set()))


def test_focus_gap_requires_real_surface_pixels_on_all_sides() -> None:
    surface = theme.rgb("#232938")
    focus = theme.rgb("#7fe3f0")
    control = theme.rgb("#3b82f6")
    good = {
        side: theme.FocusSideSample(gap=surface, ring=focus, outer=surface, clipped=False)
        for side in theme.FOCUS_SIDES
    }
    theme.validate_focus_adjacency(
        samples=good,
        component_color=control,
        expected_surface=surface,
        expected_ring=focus,
    )

    direct = dict(good)
    direct["left"] = theme.FocusSideSample(
        gap=None,
        ring=focus,
        outer=surface,
        clipped=False,
    )
    raises_contract(
        lambda: theme.validate_focus_adjacency(
            samples=direct,
            component_color=control,
            expected_surface=surface,
            expected_ring=focus,
        )
    )
    clipped = dict(good)
    clipped["bottom"] = theme.FocusSideSample(
        gap=surface,
        ring=focus,
        outer=surface,
        clipped=True,
    )
    raises_contract(
        lambda: theme.validate_focus_adjacency(
            samples=clipped,
            component_color=control,
            expected_surface=surface,
            expected_ring=focus,
        )
    )


def _valid_part_rows(case: str, surface: str) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    surface_rgb = list(theme.rgb(theme.SURFACE_COLORS[surface]))
    for name, spec in theme._SELECTED_PART_SPECS[case].items():
        role = spec["role"]
        actual = (
            list(theme.rgb(theme.APPROVED_TOKENS[role]))
            if role is not None
            else list(theme.rgb(
                theme.APPROVED_TOKENS[
                    "text.on-primary" if float(spec["minimum"]) >= 4.5 else "interactive.disabled"
                ]
            ))
        )
        adjacent_role = spec["adjacent"]
        adjacent = (
            surface_rgb
            if adjacent_role == "surface"
            else list(theme.rgb(theme.APPROVED_TOKENS[adjacent_role]))
        )
        rows[name] = {
            "node": spec["node"],
            "paint": spec["paint"],
            "actual": actual,
            "adjacent": adjacent,
            "composited": True,
            "source": "rendered-pixel" if spec["paint"] in {"mark", "rendered-pixel"} else "computed-style",
        }
    return rows


def test_selected_controls_require_exact_dom_parts_and_composited_contrast() -> None:
    horizontal_radio_state = {
        "groupRole": "radiogroup",
        "groupName": "水平單選標籤",
        "optionRole": "radio",
        "optionLabels": ["已選項", "其他項"],
        "checkedLabels": ["已選項"],
        "tabSequenceLabels": ["已選項"],
        "afterArrowRight": "其他項",
        "afterArrowLeft": "已選項",
    }
    theme.validate_radio_horizontal_semantic_state(horizontal_radio_state)
    for mutation in (
        {**horizontal_radio_state, "groupRole": "group"},
        {**horizontal_radio_state, "groupName": "其他標籤"},
        {**horizontal_radio_state, "optionLabels": ["其他項", "已選項"]},
        {**horizontal_radio_state, "checkedLabels": ["已選項", "其他項"]},
        {**horizontal_radio_state, "tabSequenceLabels": ["已選項", "其他項"]},
        {**horizontal_radio_state, "afterArrowRight": "已選項"},
        {**horizontal_radio_state, "afterArrowLeft": "其他項"},
    ):
        raises_contract(
            lambda mutation=mutation: theme.validate_radio_horizontal_semantic_state(
                mutation
            )
        )

    selectbox_state = {
        "role": "combobox",
        "accessibleName": "下拉選單標籤",
        "optionLabels": ["已選項", "其他項"],
        "selectedText": "已選項",
        "afterArrowDown": "其他項",
        "afterArrowUp": "已選項",
    }
    theme.validate_selectbox_semantic_state(selectbox_state)
    for mutation in (
        {**selectbox_state, "role": "listbox"},
        {**selectbox_state, "accessibleName": "其他標籤"},
        {**selectbox_state, "optionLabels": ["其他項", "已選項"]},
        {**selectbox_state, "selectedText": "其他項"},
        {**selectbox_state, "afterArrowDown": "已選項"},
        {**selectbox_state, "afterArrowUp": "其他項"},
    ):
        raises_contract(
            lambda mutation=mutation: theme.validate_selectbox_semantic_state(mutation)
        )

    for case in ("checkbox", "radio", "radio_horizontal", "toggle", "slider"):
        rows = _valid_part_rows(case, "canvas")
        evidence = theme.validate_selected_part_measurements(case, "canvas", rows)
        require(set(evidence) == set(theme._SELECTED_PART_SPECS[case]), f"{case} parts")
        require(all(row["contrast"] >= row["minimumContrast"] for row in evidence.values()), f"{case} contrast")

    unrelated = _valid_part_rows("checkbox", "canvas")
    unrelated["box"] = {**unrelated["box"], "node": "unrelated-descendant-with-control-token"}
    raises_contract(
        lambda: theme.validate_selected_part_measurements("checkbox", "canvas", unrelated)
    )

    extra_hit = _valid_part_rows("radio", "canvas")
    extra_hit["unrelatedTokenHit"] = dict(extra_hit["dot"])
    raises_contract(
        lambda: theme.validate_selected_part_measurements("radio", "canvas", extra_hit)
    )

    low_graphic = _valid_part_rows("slider", "canvas")
    low_graphic["unselectedTrack"] = {
        **low_graphic["unselectedTrack"],
        "actual": list(theme.rgb("#161a22")),
    }
    raises_contract(
        lambda: theme.validate_selected_part_measurements("slider", "canvas", low_graphic)
    )

    low_horizontal_radio = _valid_part_rows("radio_horizontal", "canvas")
    low_horizontal_radio["boundary"] = {
        **low_horizontal_radio["boundary"],
        "actual": list(theme.rgb("#161a22")),
    }
    raises_contract(
        lambda: theme.validate_selected_part_measurements(
            "radio_horizontal", "canvas", low_horizontal_radio
        )
    )


def test_gallery_source_is_fixture_only_complete_and_uses_native_replacements() -> None:
    source = (ROOT / "scripts" / "ui_ux_theme_fixture_app.py").read_text(encoding="utf-8")
    runner_source = Path(theme.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    expected_cases = (
        "primary",
        "form_submit",
        "download",
        "link_button",
        "tertiary",
        "disabled",
        "tabs",
        "markdown_link",
        "checkbox",
        "radio",
        "toggle",
        "slider",
        "radio_horizontal",
        "selectbox",
        "alerts",
        "signals",
    )
    require(theme.REQUIRED_GALLERY_CASES == expected_cases, "gallery case drift")
    require(
        theme.FOCUS_CASES
        == (
            "primary",
            "link_button",
            "tertiary",
            "tabs",
            "markdown_link",
            "checkbox",
            "radio",
            "toggle",
            "slider",
            "radio_horizontal",
            "selectbox",
        ),
        "focus case drift",
    )
    for surface in theme.SURFACE_COLORS:
        require(f'("{surface}",' in source, f"missing gallery surface: {surface}")
    for case in theme.REQUIRED_GALLERY_CASES:
        require(f'"{case}"' in source, f"missing gallery case: {case}")
    require("segmented" not in theme.REQUIRED_GALLERY_CASES, "synthetic case survived")
    require("segmented_control" not in source, "synthetic widget survived")
    require(
        "validate_segmented_semantic_state" not in runner_source
        and "segmented_controlActive" not in runner_source,
        "synthetic segmented oracle survived",
    )
    require("radio_horizontal" in theme.REQUIRED_GALLERY_CASES, "horizontal radio case")
    require("selectbox" in theme.REQUIRED_GALLERY_CASES, "selectbox case")
    require(
        ">ux1b-theme-ready</span>" in source,
        "external worker readiness marker text differs",
    )

    owner_calls: dict[str, list[ast.Call]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.With) or len(node.items) != 1:
            continue
        context = node.items[0].context_expr
        if (
            not isinstance(context, ast.Call)
            or not isinstance(context.func, ast.Name)
            or context.func.id != "_owner"
            or len(context.args) != 2
            or not isinstance(context.args[1], ast.Constant)
            or not isinstance(context.args[1].value, str)
        ):
            continue
        owner_calls[context.args[1].value] = [
            item
            for statement in node.body
            for item in ast.walk(statement)
            if isinstance(item, ast.Call)
            and isinstance(item.func, ast.Attribute)
            and isinstance(item.func.value, ast.Name)
            and item.func.value.id == "st"
        ]

    horizontal_radios = owner_calls.get("radio_horizontal", [])
    selectboxes = owner_calls.get("selectbox", [])
    require(
        len(horizontal_radios) == 1
        and horizontal_radios[0].func.attr == "radio",
        "radio_horizontal owner must contain one st.radio",
    )
    require(
        len(selectboxes) == 1 and selectboxes[0].func.attr == "selectbox",
        "selectbox owner must contain one st.selectbox",
    )
    require(
        any(
            keyword.arg == "horizontal"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in horizontal_radios[0].keywords
        ),
        "horizontal radio must set horizontal=True",
    )
    for node in (*horizontal_radios, *selectboxes):
        options = next(
            (keyword.value for keyword in node.keywords if keyword.arg == "options"),
            None,
        )
        require(
            isinstance(options, ast.Tuple)
            and len(options.elts) == 2
            and all(isinstance(item, ast.Constant) for item in options.elts)
            and [item.value for item in options.elts]
            == ["已選項", "其他項"],
            "replacement option order differs",
        )
        index = next(
            (keyword.value for keyword in node.keywords if keyword.arg == "index"),
            None,
        )
        require(
            isinstance(index, ast.Constant) and index.value == 0,
            "fixture replacement must select the first option",
        )
    require(
        all(not any(keyword.arg == "width" for keyword in node.keywords)
            for node in (*horizontal_radios, *selectboxes)),
        "recovery widgets must remain compatible without the newer width argument",
    )
    require('data-owner-count="48"' in source, "16 cases x 3 surfaces marker")
    for forbidden in ("yfinance", "_read_api", "subprocess", "requests.", "http://127.0.0.1:8000"):
        require(forbidden not in source, f"gallery gained provider/runtime boundary: {forbidden}")
    require("_design.build_global_theme_css" not in source, "builder must be resolved without faking availability")
    require('getattr(_design, "build_global_theme_css", None)' in source, "fail-closed builder lookup missing")
    require('id="ux1b-theme-ready"' in source, "gallery ready marker missing")
    require(
        source.index("fixtures.bootstrap_fixture_environment()")
        < source.index("import streamlit as st"),
        "fixture bootstrap guards must install before Streamlit imports",
    )
    require(
        source.index("fixtures.record_theme_gallery_render(st)")
        < source.index('id="ux1b-theme-ready"'),
        "gallery readiness must follow the real completed-render counter",
    )


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"PASS all {len(tests)} UX-1B theme contract tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
