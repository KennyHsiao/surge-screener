#!/usr/bin/env python3
"""Browser regression for all UX-1B primary-action focus/disabled states."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "scripts" / "ui_ux_primary_action_fixture_app.py"
SURFACES = ("canvas", "panel", "elevated")
FOCUS_CASES = ("primary", "form", "download", "link")
DISABLED_CASES = ("primary", "form", "download", "link")
DISABLED_CHECKED_CASES = ("checkbox", "toggle", "radio")
FOCUS_COLOR = "rgb(127, 227, 240)"
HOVER_COLOR = "rgb(29, 78, 216)"
ACTIVE_COLOR = "rgb(30, 64, 175)"
CONTROL_COLOR = "rgb(59, 130, 246)"
DISABLED_COLOR = "rgb(107, 114, 128)"
DISABLED_TEXT = "rgb(139, 147, 167)"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _ephemeral_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_health(process: subprocess.Popen[bytes], port: int) -> None:
    deadline = time.monotonic() + 20.0
    health = f"http://127.0.0.1:{port}/_stcore/health"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError("primary-action fixture exited before health readiness")
        try:
            with urllib.request.urlopen(health, timeout=0.5) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)
    raise AssertionError("primary-action fixture health readiness timed out")


def _clean_child_environment(home: str) -> dict[str, str]:
    prohibited = ("TOKEN", "KEY", "SECRET", "PASSWORD", "COOKIE", "AUTH")
    environment = {
        name: value
        for name, value in os.environ.items()
        if not any(part in name.upper() for part in prohibited)
    }
    environment.update(
        {
            "HOME": home,
            "NO_PROXY": "127.0.0.1,localhost",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(ROOT),
        }
    )
    return environment


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def _style_snapshot(locator: Any) -> dict[str, Any]:
    value = locator.evaluate(
        "element => { const style = getComputedStyle(element); return {"
        " backgroundColor: style.backgroundColor, color: style.color,"
        " borderColors: [style.borderTopColor, style.borderRightColor,"
        "   style.borderBottomColor, style.borderLeftColor],"
        " outlineColor: style.outlineColor, outlineOffset: style.outlineOffset,"
        " outlineStyle: style.outlineStyle, outlineWidth: style.outlineWidth,"
        " pointerEvents: style.pointerEvents, tabIndex: element.tabIndex,"
        " disabledAttribute: element.hasAttribute('disabled'),"
        " ariaDisabled: element.getAttribute('aria-disabled')}; }"
    )
    require(isinstance(value, dict), "computed-style payload is malformed")
    return value


def _assert_focus(page: Any, surface: str, case: str) -> None:
    locator = page.get_by_role(
        "link" if case == "link" else "button",
        name=f"{surface} focus {case}",
        exact=True,
    )
    require(locator.count() == 1, f"focus target differs: {surface}/{case}")
    locator.scroll_into_view_if_needed()
    locator.focus()
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    require(
        locator.evaluate("element => document.activeElement === element"),
        f"keyboard focus did not return to {surface}/{case}",
    )
    style = _style_snapshot(locator)
    require(style["outlineColor"] == FOCUS_COLOR, f"focus color differs: {surface}/{case}")
    require(style["outlineStyle"] == "solid", f"focus style differs: {surface}/{case}")
    require(float(style["outlineWidth"].removesuffix("px")) >= 3.0, f"focus width differs: {surface}/{case}")
    require(float(style["outlineOffset"].removesuffix("px")) >= 2.0, f"focus offset differs: {surface}/{case}")
    locator.hover()
    hover_style = _style_snapshot(locator)
    require(
        hover_style["outlineColor"] == FOCUS_COLOR,
        f"hover removed visible focus: {surface}/{case}",
    )
    require(
        hover_style["backgroundColor"] == HOVER_COLOR,
        f"visible focus overrode hover fill: {surface}/{case}: {hover_style!r}",
    )
    page.mouse.down()
    try:
        active_style = _style_snapshot(locator)
        require(
            active_style["backgroundColor"] == ACTIVE_COLOR,
            f"visible focus overrode active fill: {surface}/{case}: {active_style!r}",
        )
    finally:
        # Release outside the target so the active-state probe cannot click a
        # Streamlit button and race its rerun against the following locator.
        page.mouse.move(0, 0)
        page.mouse.up()


def _assert_disabled(page: Any, surface: str, case: str) -> None:
    role = "link" if case == "link" else "button"
    locator = page.get_by_role(role, name=f"{surface} disabled {case}", exact=True)
    require(locator.count() == 1, f"disabled target differs: {surface}/{case}")
    style = _style_snapshot(locator)
    require(style["disabledAttribute"] is True, f"disabled attribute missing: {surface}/{case}")
    require(
        style["backgroundColor"] == DISABLED_COLOR,
        f"disabled fill differs: {surface}/{case}: {style!r}",
    )
    require(
        style["color"] == DISABLED_TEXT,
        f"disabled text differs: {surface}/{case}: {style!r}",
    )
    require(
        all(color == DISABLED_COLOR for color in style["borderColors"]),
        f"disabled border differs: {surface}/{case}",
    )
    aria_style = locator.evaluate(
        "element => { element.removeAttribute('disabled');"
        " element.setAttribute('aria-disabled', 'true');"
        " const style = getComputedStyle(element); return {"
        " backgroundColor: style.backgroundColor, color: style.color,"
        " borderColors: [style.borderTopColor, style.borderRightColor,"
        " style.borderBottomColor, style.borderLeftColor],"
        " pointerEvents: style.pointerEvents}; }"
    )
    require(
        aria_style["backgroundColor"] == DISABLED_COLOR
        and aria_style["color"] == DISABLED_TEXT
        and all(color == DISABLED_COLOR for color in aria_style["borderColors"])
        and aria_style["pointerEvents"] == "none",
        f"aria-disabled fallback differs: {surface}/{case}: {aria_style!r}",
    )
    locator.evaluate(
        "element => { element.removeAttribute('aria-disabled');"
        " element.setAttribute('disabled', ''); }"
    )
    if case == "link":
        require(style["tabIndex"] == -1, f"disabled link remains in tab order: {surface}")
        require(style["pointerEvents"] == "none", f"disabled link accepts pointer input: {surface}")
        return
    require(
        style["pointerEvents"] == "auto",
        f"native disabled button cannot expose hover evidence: {surface}/{case}",
    )
    accepted = locator.evaluate(
        "element => { element.focus(); return document.activeElement === element; }"
    )
    require(accepted is False, f"disabled button accepted focus: {surface}/{case}")
    events = locator.evaluate(
        "element => { let count = 0; const listener = () => { count += 1; };"
        " element.addEventListener('click', listener); element.click();"
        " element.removeEventListener('click', listener); return count; }"
    )
    require(events == 0, f"disabled button dispatched click: {surface}/{case}")


def _assert_checked_disabled(page: Any, surface: str, case: str) -> None:
    test_id = "stRadio" if case == "radio" else "stCheckbox"
    input_type = "radio" if case == "radio" else "checkbox"
    label = f"{surface} disabled checked {case}"
    root = page.locator(f'[data-testid="{test_id}"]').filter(has_text=label)
    require(root.count() == 1, f"disabled checked target differs: {surface}/{case}")
    control = root.locator(f'input[type="{input_type}"]:checked').first
    require(control.count() == 1, f"checked input missing: {surface}/{case}")
    require(control.is_disabled(), f"checked input is enabled: {surface}/{case}")
    fill = control.evaluate(
        "element => getComputedStyle(element.previousElementSibling).backgroundColor"
    )
    require(
        fill != CONTROL_COLOR,
        f"disabled checked control looks enabled: {surface}/{case}: {fill}",
    )


def test_all_primary_action_focus_and_disabled_states() -> None:
    from playwright.sync_api import sync_playwright

    source = FIXTURE.read_text(encoding="utf-8")
    require("ui._shared" not in source, "fixture imports a production data provider")
    require("requests" not in source and "urllib" not in source, "fixture has network code")
    port = _ephemeral_port()
    with tempfile.TemporaryDirectory(prefix="ux1b-primary-home-") as private_home:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(FIXTURE),
                "--server.address",
                "127.0.0.1",
                "--server.port",
                str(port),
                "--server.headless",
                "true",
                "--browser.gatherUsageStats",
                "false",
            ],
            cwd=ROOT,
            env=_clean_child_environment(private_home),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            _wait_for_health(process, port)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 900})
                    page.goto(
                        f"http://127.0.0.1:{port}",
                        wait_until="networkidle",
                        timeout=30_000,
                    )
                    page.get_by_text("UX-1B Primary Action State Fixture", exact=True).wait_for()
                    for surface in SURFACES:
                        for case in FOCUS_CASES:
                            _assert_focus(page, surface, case)
                        for case in DISABLED_CASES:
                            _assert_disabled(page, surface, case)
                        for case in DISABLED_CHECKED_CASES:
                            _assert_checked_disabled(page, surface, case)
                finally:
                    browser.close()
        finally:
            _stop_process(process)


def main() -> int:
    test_all_primary_action_focus_and_disabled_states()
    print("PASS test_all_primary_action_focus_and_disabled_states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
