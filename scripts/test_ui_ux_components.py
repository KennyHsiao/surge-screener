#!/usr/bin/env python3
"""Offline contract tests for the UX-1A design and state foundations.

Run:  .venv/bin/python scripts/test_ui_ux_components.py
"""

from __future__ import annotations

import dataclasses
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_chip_text_and_color_are_closed_over_safe_values() -> None:
    from ui import _design, _shared

    malicious_text = "<script>alert(\"x\")</script><img onerror='x'>&"
    malicious_color = "red;position:fixed;background:url(javascript:alert(1))"
    rendered = _shared.chip(malicious_text, malicious_color)

    for raw in ("<script>", "<img", malicious_color):
        require(raw not in rendered, f"unsafe chip fragment survived: {raw!r}")
    for escaped in ("&lt;script&gt;", "&lt;img", "&#x27;x&#x27;", "&amp;"):
        require(escaped in rendered, f"chip label was not quote-escaped: {escaped!r}")
    require(
        _design.CHIP_COLORS["muted"] in rendered,
        "unknown chip colors must fall back to the fixed muted component token",
    )

    legacy = (
        _shared.GREEN,
        _shared.RED,
        _shared.LOSS,
        _shared.ACCENT,
        _shared.AMBER,
        _shared.BLUE,
        _shared.PURPLE,
        _shared.CYAN,
        _shared.MUTED,
    )
    for value in legacy:
        resolved = _design.resolve_chip_color(value)
        require(resolved in _design.CHIP_COLORS.values(), f"legacy color did not resolve safely: {value}")
        require(value not in _shared.chip("ok", value) or value == resolved,
                f"legacy color bypassed the component mapping: {value}")

    for token_name in _design.CHIP_TOKEN_NAMES:
        require(
            _design.resolve_chip_color(token_name) in _design.CHIP_COLORS.values(),
            f"semantic chip token was not accepted: {token_name}",
        )
    for unknown in (None, 7, object(), "", "#ffffff", "feedback.invented"):
        require(
            _design.resolve_chip_color(unknown) == _design.CHIP_COLORS["muted"],
            f"unknown chip value did not fail closed: {unknown!r}",
        )


def test_tokens_are_immutable_and_contrast_is_scoped_aa() -> None:
    from ui import _design

    preserved_registry_values = {
        "surface.canvas": "#0e1117",
        "surface.panel": "#1a1f2b",
        "text.primary": "#e6e9ef",
        "text.secondary": "#8b93a7",
        "feedback.info": "#636efa",
        "feedback.success": "#00cc96",
        "feedback.warning": "#ffa15a",
        "feedback.error": "#ef553b",
        "signal.bullish": "#00cc96",
        "signal.neutral": "#ffa15a",
        "signal.bearish": "#ef553b",
        "signal.avoid": "#ef4444",
    }
    for name, expected in preserved_registry_values.items():
        require(
            _design.COLOR_TOKENS[name] == expected,
            f"UX-1A changed an existing global/semantic token: {name}",
        )

    interaction = dict(_design.INTERACTIVE_TOKENS)
    require(
        interaction
        in (
            {
                "interactive.primary": "#ef4444",
                "interactive.hover": "#fb7185",
                "interactive.disabled": "#6b7280",
            },
            {
                "interactive.primary": "#2563eb",
                "interactive.hover": "#1d4ed8",
                "interactive.active": "#1e40af",
                "interactive.accent": "#60a5fa",
                "interactive.control": "#3b82f6",
                "interactive.disabled": "#6b7280",
            },
        ),
        "interaction tokens are neither the frozen UX-1A pretheme set nor the "
        "accepted UX-1B semantic set",
    )
    if "interactive.active" in interaction:
        require(
            _design.COLOR_TOKENS["text.on-primary"] == "#ffffff"
            and _design.COLOR_TOKENS["text.disabled"] == "#8b93a7",
            "UX-1B interaction text roles differ",
        )

    try:
        _design.COLOR_TOKENS["surface.canvas"] = "#ffffff"  # type: ignore[index]
    except TypeError:
        pass
    else:
        raise AssertionError("semantic tokens must be immutable")

    require(
        _design.contrast_ratio(
            _design.COLOR_TOKENS["border.focus"],
            _design.COLOR_TOKENS["surface.canvas"],
        ) >= 3.0,
        "focus token must reach 3:1 against canvas",
    )
    require(
        _design.contrast_ratio(
            _design.COLOR_TOKENS["border.focus"],
            _design.COLOR_TOKENS["surface.panel"],
        ) >= 3.0,
        "focus token must reach 3:1 against panel",
    )
    for name, foreground in _design.CHIP_COLORS.items():
        for surface_name in ("surface.canvas", "surface.panel"):
            surface = _design.COLOR_TOKENS[surface_name]
            fill = _design.composite_hex(foreground, surface, _design.CHIP_FILL_ALPHA)
            ratio = _design.contrast_ratio(foreground, fill)
            require(ratio >= 4.5, f"{name} chip contrast on {surface_name} is {ratio:.3f}")


def test_data_state_validates_closed_vocabularies_and_composition() -> None:
    from ui import _components

    state = _components.DataState(
        source="fallback",
        content="partial",
        freshness="stale",
        operation="failure",
        source_id="system.schedules",
        reason_code="transport_error",
        event_code="QR-SCHEDULES-RESULT-001",
        as_of=date(2026, 7, 16),
        recovery_key="retry",
    )
    require(dataclasses.is_dataclass(state), "DataState must remain a dataclass")
    try:
        state.source = "authoritative"  # type: ignore[misc]
    except (AttributeError, dataclasses.FrozenInstanceError):
        pass
    else:
        raise AssertionError("DataState must be immutable")

    severity, message = _components._compose_state(state)
    require(severity == "error", severity)
    for expected in ("備援", "部分", "過期", "失敗", "QR-SCHEDULES-RESULT-001"):
        require(expected in message, f"state dimension disappeared: {expected!r} from {message!r}")

    unavailable = _components.DataState(
        source="unavailable",
        content="unknown",
        freshness="unknown",
        operation="idle",
        source_id="system.ai-updates",
        reason_code="missing",
    )
    _, unavailable_message = _components._compose_state(unavailable)
    for expected in ("權威來源", "不可用", "內容狀態未知", "新鮮度未知"):
        require(expected in unavailable_message, unavailable_message)

    cases = [
        {"source": "invented"},
        {"content": "invented"},
        {"freshness": "invented"},
        {"operation": "invented"},
        {"source_id": "/tmp/private/source"},
        {"reason_code": "response body: secret"},
        {"event_code": "QR-UNKNOWN-999"},
        {"recovery_key": "curl http://127.0.0.1:9999"},
    ]
    base = {
        "source": "authoritative",
        "content": "populated",
        "freshness": "unknown",
        "operation": "idle",
        "source_id": "system.ai-updates",
    }
    for override in cases:
        try:
            _components.DataState(**(base | override))
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"DataState accepted untrusted vocabulary: {override}")

    for unsafe_as_of in ("2026-07-16", "/tmp/private.json", "http://127.0.0.1:8501"):
        try:
            _components.DataState(**(base | {"as_of": unsafe_as_of}))
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"DataState accepted string metadata: {unsafe_as_of!r}")

    for invalid_pair in (
        base | {"source": "fallback", "reason_code": "missing"},
        base | {"source": "authoritative", "reason_code": "transport_error"},
        base | {"source": "unavailable", "content": "unknown", "reason_code": None},
    ):
        try:
            _components.DataState(**invalid_pair)
        except ValueError:
            pass
        else:
            raise AssertionError(f"DataState accepted an invalid source/reason pair: {invalid_pair}")


def test_state_validity_rules_and_native_renderer_boundary() -> None:
    from ui import _components

    base = {
        "operation": "idle",
        "source_id": "today.trade-state",
    }
    invalid = [
        base | {"source": "unavailable", "content": "populated", "freshness": "unknown"},
        base | {"source": "unavailable", "content": "unknown", "freshness": "fresh",
                "as_of": date.today()},
        base | {"source": "authoritative", "content": "populated", "freshness": "fresh"},
    ]
    for values in invalid:
        try:
            _components.DataState(**values)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid state composition was accepted: {values}")

    valid = _components.DataState(
        source="authoritative",
        content="populated",
        freshness="fresh",
        operation="success",
        source_id="today.trade-state",
        as_of=datetime(2026, 7, 16, tzinfo=timezone.utc),
    )
    severity, message = _components._compose_state(valid)
    require(severity == "success", severity)
    require("2026-07-16" in _components._source_meta_text(valid), message)

    severity_cases = [
        ({"source": "unavailable", "content": "unknown", "freshness": "unknown",
          "operation": "idle", "reason_code": "missing"}, "warning"),
        ({"source": "fallback", "content": "empty", "freshness": "unknown",
          "operation": "idle", "reason_code": "transport_error"}, "warning"),
        ({"source": "authoritative", "content": "partial", "freshness": "unknown",
          "operation": "idle"}, "warning"),
        ({"source": "authoritative", "content": "populated", "freshness": "stale",
          "operation": "idle", "as_of": date(2026, 7, 15)}, "warning"),
        ({"source": "authoritative", "content": "empty", "freshness": "unknown",
          "operation": "idle"}, "info"),
        ({"source": "authoritative", "content": "unknown", "freshness": "unknown",
          "operation": "loading"}, "info"),
        ({"source": "authoritative", "content": "populated", "freshness": "unknown",
          "operation": "success"}, "success"),
        ({"source": "authoritative", "content": "populated", "freshness": "unknown",
          "operation": "idle"}, "info"),
    ]
    for values, expected_severity in severity_cases:
        state = _components.DataState(source_id="today.trade-state", **values)
        actual_severity, composed = _components._compose_state(state)
        require(actual_severity == expected_severity,
                f"wrong precedence for {values}: {actual_severity}")
        if values["source"] == "fallback" and values["content"] == "empty":
            require("備援" in composed and "沒有資料" in composed,
                    "fallback and empty dimensions must remain visible together")

    design_source = (ROOT / "ui" / "_design.py").read_text(encoding="utf-8")
    component_source = (ROOT / "ui" / "_components.py").read_text(encoding="utf-8")
    require("streamlit" not in design_source, "pure design tokens must not import Streamlit")
    require("unsafe_allow_html" not in component_source, "state renderers must use native semantics")
    for native in ("st.info", "st.warning", "st.error", "st.success", "st.caption"):
        require(native in component_source, f"missing native renderer: {native}")
    for forbidden in (".streamlit/config.toml", "primaryColor", "overflow-x"):
        require(forbidden not in design_source + component_source,
                f"shared foundations must not mutate global/reflow behavior: {forbidden}")


def test_native_tag_row_uses_literal_text_without_an_html_sink() -> None:
    from ui import _components

    with patch("ui._components.st.text") as text:
        _components.render_tag_row(["AI", "<script>alert(1)</script>", ""])
    text.assert_called_once_with("標籤：AI · <script>alert(1)</script>")

    with patch("ui._components.st.text") as text:
        _components.render_tag_row([])
    text.assert_not_called()


def test_shared_csv_and_report_directory_reads_fail_soft() -> None:
    from ui import _shared

    original_reports_dir = _shared.REPORTS_DIR
    try:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp)
            _shared.REPORTS_DIR = reports

            artifact = reports / "live.json"
            artifact.write_text('{"state":', encoding="utf-8")
            _shared.load_json.clear()
            require(_shared.load_json(str(artifact)) is None,
                    "half-written JSON must fail soft")
            artifact.write_text('{"state":"ready"}', encoding="utf-8")
            _shared.load_json.clear()
            require(_shared.load_json(str(artifact)) == {"state": "ready"},
                    "a repaired artifact must recover after cache clear")
            artifact.write_text('["legacy-list-root"]', encoding="utf-8")
            _shared.load_json.clear()
            require(_shared.load_json(str(artifact)) == ["legacy-list-root"],
                    "load_json must preserve its non-object compatibility contract")
            with patch("scripts.artifact_loader.Path.read_text",
                       side_effect=PermissionError("private path")):
                _shared.load_json.clear()
                require(_shared.load_json(str(artifact)) is None,
                        "unreadable JSON must fail soft")

            (reports / "2026-07-15").mkdir()
            (reports / "2026-07-16").mkdir()
            (reports / "reflections").mkdir()
            require(
                _shared.find_report_dates() == ["2026-07-16", "2026-07-15"],
                "report-date filtering/order changed",
            )

            ledger = reports / "performance_ledger.csv"
            ledger.write_text(
                "scan_date,composite_score,ticker\n2026-07-16,81.5,NVDA\n",
                encoding="utf-8",
            )
            _shared.load_ledger.clear()
            parsed = _shared.load_ledger()
            require(parsed is not None and parsed.iloc[0]["ticker"] == "NVDA",
                    "valid ledger no longer loads")

            ledger.write_text("unexpected_column\nvalue\n", encoding="utf-8")
            _shared.load_ledger.clear()
            require(_shared.load_ledger() is None, "wrong-shape ledger must fail soft")

            with patch("ui._shared.pd.read_csv", side_effect=PermissionError("private path")):
                _shared.load_ledger.clear()
                require(_shared.load_ledger() is None, "unreadable ledger must fail soft")

            with patch.object(Path, "iterdir", side_effect=PermissionError("private path")):
                require(_shared.find_report_dates() == [], "unreadable report directory must fail soft")
    finally:
        _shared.REPORTS_DIR = original_reports_dir
        _shared.load_json.clear()
        _shared.load_ledger.clear()


def main() -> None:
    tests = [
        test_chip_text_and_color_are_closed_over_safe_values,
        test_tokens_are_immutable_and_contrast_is_scoped_aa,
        test_data_state_validates_closed_vocabularies_and_composition,
        test_state_validity_rules_and_native_renderer_boundary,
        test_native_tag_row_uses_literal_text_without_an_html_sink,
        test_shared_csv_and_report_directory_reads_fail_soft,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
