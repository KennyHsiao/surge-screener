#!/usr/bin/env python3
"""Authenticated evidence primitives for the UX-1B recovery pipeline.

The module deliberately keeps worker claims, filesystem authentication, and
terminal-manifest authorization as separate steps.  A browser child may stage
bytes, but only the coordinator can authenticate them and only the finalizer
can issue ``status: passed``.
"""

from __future__ import annotations

import argparse
import copy
import errno
import fcntl
import hashlib
import io
import json
import math
import os
import re
import secrets
import stat
import struct
import sys
import threading
import weakref
import zlib
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any
from urllib.parse import urlsplit

if __package__ in {None, ""}:
    # ``python scripts/ui_ux_evidence.py`` puts ``scripts/`` rather than the
    # repository root on sys.path.  Add the lexical parent solely for module
    # discovery; all security-sensitive filesystem decisions below remain
    # descriptor-rooted.
    _IMPORT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    if _IMPORT_ROOT not in sys.path:
        sys.path.insert(0, _IMPORT_ROOT)

from scripts import ui_ux_isolation as isolation


EVIDENCE_SCHEMA = "quant-radar-ui-ux-evidence/v1"
RENDER_SCHEMA = "quant-radar-ui-ux-render/v1"
RENDER_V2_SCHEMA = "quant-radar-ui-ux-render/v2"
FOCUSED_CONTROL_EVIDENCE_SCHEMA = "quant-radar-ui-ux-focused-controls/v1"
FOCUSED_CONTROL_EVIDENCE_V2_SCHEMA = "quant-radar-ui-ux-focused-controls/v2"
FOCUSED_CONTROL_EVIDENCE_V3_SCHEMA = "quant-radar-ui-ux-focused-controls/v3"
FOCUSED_SCREENSHOT_BINDING_SCHEMA = (
    "quant-radar-ui-ux-focused-screenshot-binding/v1"
)
CASE_SEMANTIC_PROJECTION_SCHEMA = (
    "quant-radar-ui-ux-case-semantic-projection/v1"
)
CONTROL_CATALOG_SCHEMA = "quant-radar-ui-ux-control-catalog/v1"
CAPTURE_STACK_SCHEMA = "quant-radar-ui-ux-ux1b-capture-stack/v1"
WORKER_REQUEST_SCHEMA = "quant-radar-ui-ux-browser-request/v1"
WORKER_RESPONSE_SCHEMA = "quant-radar-ui-ux-browser-response/v1"
WORKER_REQUEST_V2_SCHEMA = "quant-radar-ui-ux-browser-request/v2"
WORKER_RESPONSE_V2_SCHEMA = "quant-radar-ui-ux-browser-response/v2"
THEME_WORKER_EVIDENCE_SCHEMA = "quant-radar-ui-ux-theme-worker-evidence/v1"

ROOT_CAPTURE_EXPANSION_ROWS = 44
ROOT_CAPTURE_EXPANSION_SIZE = 16_576
ROOT_CAPTURE_EXPANSION_SHA256 = (
    "13c0d601a5587cb2e05acda7d40209b4f3dc8f1d77c7bb619243eeebd241d2ca"
)

MAX_WORKER_REQUEST_BYTES = 64 * 1024
MAX_WORKER_RESPONSE_BYTES = 256 * 1024
# Compatibility bound used by the worker bootstrap.  Direction-specific
# decoders retain the tighter request limit above.
MAX_WORKER_JSON_BYTES = MAX_WORKER_RESPONSE_BYTES
MAX_RENDER_SIDECAR_BYTES = 8 * 1024 * 1024
MAX_PNG_BYTES = 64 * 1024 * 1024
MAX_AUTHENTICATED_ARTIFACT_BYTES = MAX_PNG_BYTES
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_MANIFEST_ERROR_BYTES = 2 * 1024
MAX_ERROR_BYTES = MAX_MANIFEST_ERROR_BYTES
MAX_VERIFIED_CAPTURE_AUTHORITIES = 256
MAX_VALIDATED_SUCCESS_CLOSURES = 256
MAX_SUCCESS_FINALIZATION_GRANTS = 256
MAX_CAPTURE_ROOT_DEPTH = 64
MAX_CAPTURE_PARENT_ENTRIES = 4096

_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_ALLOWED_FIXTURE_ENTRYPOINTS = frozenset(
    {
        "scripts/ui_ux_fixture_app.py",
        "scripts/ui_ux_selection_fixture_app.py",
        "scripts/ui_ux_theme_fixture_app.py",
    }
)
CAPTURE_STACK_MEMBERS = (
    "scripts/ui_ux_isolation.py",
    "scripts/ui_ux_evidence.py",
    "scripts/ui_ux_browser_worker.py",
    "scripts/ui_ux_fixtures.py",
    "scripts/ui_ux_fixture_app.py",
    "scripts/ui_ux_selection_fixture_app.py",
    "scripts/ui_ux_snapshot_matrix.py",
    "scripts/ui_ux_theme_fixture_app.py",
    "scripts/ui_ux_theme_matrix.py",
)
_SORTED_CAPTURE_STACK_MEMBERS = tuple(sorted(CAPTURE_STACK_MEMBERS))

_THEME_GALLERY_CASES = (
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
_THEME_FOCUS_CASES = (
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
)
_THEME_PRIMARY_CASES = ("primary", "form_submit", "download", "link_button")
_THEME_SELECTED_CASES = (
    "checkbox",
    "radio",
    "radio_horizontal",
    "toggle",
    "slider",
    "selectbox",
)
_THEME_SURFACES = (
    ("canvas", "#0e1117", (14, 17, 23)),
    ("panel", "#1a1f2b", (26, 31, 43)),
    ("elevated", "#232938", (35, 41, 56)),
)
_THEME_FOCUS_RGB = (127, 227, 240)
_THEME_FOCUS_SIDES = ("top", "right", "bottom", "left")
_THEME_OWNER_RE = re.compile(r"\Aux1b_owner_(?:canvas|panel|elevated)_[a-z0-9_]+\Z")
_THEME_SELECTOR_STATES = frozenset(
    {
        "default",
        "hover",
        "active",
        "focus-visible",
        "disabled",
        "selected",
        "checked",
        "visited-static",
    }
)

_FULL_PAGE_IDENTITIES = (
    ("today-decision", "/", "today_decision.render", 2, "今日決策", "exact"),
    ("trade-state", "/trade-state", "trade_state.render", 2, "交易狀態", "exact"),
    ("us-screener", "/us-screener", "us_screener.render", 2, "Layer 0 — 大盤環境", "exact"),
    ("options-flow", "/options-flow", "options_flow.render", 1, "選擇權異常流", "contains"),
    ("stock-checkup", "/stock-checkup", "stock_checkup.render", 2, "個股總覽", "contains"),
    ("options-cockpit", "/options-cockpit", "options_cockpit.render", 2, "期權作戰台", "contains"),
    ("radar", "/radar", "radar.render", 2, "雷達 / Radar", "contains"),
    ("ibkr-reconcile", "/ibkr-reconcile", "ibkr_reconcile.render", 2, "IBKR 對帳", "contains"),
    ("sector-rotation", "/sector-rotation", "sector_rotation.render", 2, "熱錢板塊輪動", "contains"),
    ("theme-flow", "/theme-flow", "theme_flow.render", 2, "主題資金流", "contains"),
    ("us-cot", "/us-cot", "us_cot.render", 2, "COT / ES 週報", "contains"),
    ("market-thesis", "/market-thesis", "market_thesis.render", 2, "大盤行情研判", "contains"),
    ("us-x", "/us-x", "us_x", 2, "X 社群情緒 — 美股", "contains"),
    ("retro-analysis", "/retro-analysis", "retro_analysis.render", 1, "復盤分析", "contains"),
    ("analytics-db", "/analytics-db", "analytics_db.render", 2, "資料健康 / Analytics DB", "exact"),
    ("knowledge-graph", "/knowledge-graph", "knowledge_graph.render", 1, "知識網路", "exact"),
    ("us-options", "/us-options", "us_options.render", 2, "完整期權鏈明細", "exact"),
    ("analyst-views", "/analyst-views", "analyst_views.render", 2, "分析師評級", "contains"),
    ("institutions", "/institutions", "institutions.render", 2, "機構面板", "contains"),
    ("industry-roles", "/industry-roles", "industry_roles.render", 2, "產業鏈分類", "exact"),
    ("watchlist-categorize", "/watchlist-categorize", "watchlist_categorize.render", 2, "自選股分類", "contains"),
    ("influencers", "/influencers", "influencers.render", 2, "關注博主", "exact"),
    ("schedules", "/schedules", "sys_schedules.render", 2, "排程與執行結果", "contains"),
    ("ai-updates", "/ai-updates", "sys_ai_updates.render", 2, "AI Agent 重點更新", "contains"),
    ("crypto-universe", "/crypto-universe", "crypto_universe.render", 2, "幣種清單 — 幣安 USDT 永續 (USDT.P)", "contains"),
    ("crypto-screener", "/crypto-screener", "crypto_screener.render", 2, "幣圈篩選", "contains"),
    ("crypto-x", "/crypto-x", "crypto_x", 2, "X 社群情緒 — 幣圈", "contains"),
)
_STANDARD_VIEWPORTS = (
    ("desktop", 1440, 900),
    ("tablet", 768, 1024),
    ("mobile", 390, 844),
)
_FOCUSED_VIEWPORTS = _STANDARD_VIEWPORTS + (("narrow", 320, 844),)
_FOCUSED_IDENTITIES = (
    ("risk-guard-controls", "/__selection__/risk-guard", "risk-guard", "risk_guard.render"),
    ("institutions-controls", "/__selection__/institutions", "institutions", "institutions.render"),
    ("options-cockpit-controls", "/__selection__/options-cockpit", "options-cockpit", "options_cockpit.render"),
    ("radar-controls", "/__selection__/radar", "radar", "radar.render"),
    ("knowledge-graph-controls", "/__selection__/knowledge-graph", "knowledge-graph", "knowledge_graph.render"),
    ("ai-chat-settings-controls", "/__selection__/ai-chat-settings", "today-decision", "today_decision.render"),
    ("retro-controls", "/__selection__/retro-analysis", "retro-analysis", "retro_analysis.render"),
    ("analytics-controls", "/__selection__/analytics-db", "analytics-db", "analytics_db.render"),
    ("stock-checkup-controls", "/__selection__/stock-checkup", "stock-checkup", "stock_checkup.render"),
)
_FOCUSED_ROOT_SELECTORS = {
    "risk-guard-controls": (".st-key-rg_source",),
    "institutions-controls": (".st-key-inst_view",),
    "options-cockpit-controls": (".st-key-cockpit_price_view_NVDA",),
    "radar-controls": (".st-key-radar_source", ".st-key-radar_view"),
    "knowledge-graph-controls": (".st-key-kg_view_mode", ".st-key-kg_label_mode"),
    "ai-chat-settings-controls": (".st-key-ai_chat_mode",),
    "retro-controls": (".st-key-retro_validation_lane",),
    "analytics-controls": (".st-key-adb_table",),
    "stock-checkup-controls": (".st-key-checkup_mode",),
}
_FOCUSED_CONTROL_ROWS = (
    (
        "risk-guard-controls",
        (
            ("rg_source", ".st-key-rg_source", "radio_horizontal", "來源", ("手動輸入", "Watchlist", "Screener 候選", "IBKR 持倉"), "Watchlist"),
        ),
    ),
    (
        "institutions-controls",
        (
            ("inst_view", ".st-key-inst_view", "radio_horizontal", "檢視", ("機構持股 · 股票 → 誰持有它", "機構持倉 · 機構 → 它持有什麼"), "機構持倉 · 機構 → 它持有什麼"),
        ),
    ),
    (
        "options-cockpit-controls",
        (
            ("cockpit_price_view_NVDA", ".st-key-cockpit_price_view_NVDA", "radio_horizontal", "圖表模式", ("快照圖 + 預期波動錐", "互動圖 (TradingView)"), "快照圖 + 預期波動錐"),
        ),
    ),
    (
        "radar-controls",
        (
            ("radar_source", ".st-key-radar_source", "radio_horizontal", "來源", ("手動輸入", "Watchlist", "Screener 候選", "反轉候選(掃描)", "IBKR 持倉"), "手動輸入"),
            ("radar_view", ".st-key-radar_view", "radio_horizontal", "顯示", ("全部", "風險警示", "反轉候選", "兩者共現"), "全部"),
        ),
    ),
    (
        "knowledge-graph-controls",
        (
            ("kg_view_mode", ".st-key-kg_view_mode", "radio_horizontal", "視圖", ("星雲圖", "驗證泳道"), "星雲圖"),
            ("kg_label_mode", ".st-key-kg_label_mode", "radio_horizontal", "標籤", ("核心", "因子", "全部", "無"), "核心"),
        ),
    ),
    (
        "ai-chat-settings-controls",
        (
            ("ai_chat_mode", ".st-key-ai_chat_mode", "radio_horizontal", "模式", ("快速問答", "深度研究"), "快速問答"),
        ),
    ),
    (
        "retro-controls",
        (
            ("retro_validation_lane", ".st-key-retro_validation_lane", "radio_horizontal", "驗證類型", ("暴漲事件復盤", "續漲強者", "Playbook 驗證"), "暴漲事件復盤"),
        ),
    ),
    (
        "analytics-controls",
        (
            ("adb_table", ".st-key-adb_table", "selectbox", "資料表", ("candidate_rankings", "iv_history"), "candidate_rankings"),
        ),
    ),
    (
        "stock-checkup-controls",
        (
            ("checkup_mode", ".st-key-checkup_mode", "radio_horizontal", "模式", ("單檔", "批次"), "單檔"),
        ),
    ),
)
_FOCUSED_CONTROL_CONTRACTS = MappingProxyType(
    {
        case: tuple(
            MappingProxyType(
                {
                    "sessionKey": session_key,
                    "rootSelector": root_selector,
                    "replacementWidget": replacement_widget,
                    "accessibleName": accessible_name,
                    "optionLabels": option_labels,
                    "selectedLabel": selected_label,
                    "auxiliaryButtons": (
                        ("Help for 模式",) if session_key == "ai_chat_mode" else ()
                    ),
                }
            )
            for (
                session_key,
                root_selector,
                replacement_widget,
                accessible_name,
                option_labels,
                selected_label,
            ) in controls
        )
        for case, controls in _FOCUSED_CONTROL_ROWS
    }
)
_FULL_PAGE_ROOT_SELECTORS = {
    "stock-checkup": (".st-key-checkup_mode",),
    "options-cockpit": (".st-key-cockpit_price_view_NVDA",),
    "radar": (".st-key-radar_source", ".st-key-radar_view"),
    "retro-analysis": (".st-key-retro_validation_lane",),
    "analytics-db": (".st-key-adb_table",),
    "knowledge-graph": (".st-key-kg_view_mode", ".st-key-kg_label_mode"),
    "institutions": (".st-key-inst_view",),
}
_AFFECTED_ROOT_SELECTORS = tuple(
    sorted(
        {
            selector
            for selectors in _FOCUSED_ROOT_SELECTORS.values()
            for selector in selectors
        }
    )
)


def _build_worker_identity_rows() -> dict[tuple[object, ...], dict[str, Any]]:
    rows: dict[tuple[object, ...], dict[str, Any]] = {}

    def add(key: tuple[object, ...], row: dict[str, Any]) -> None:
        if key in rows:
            raise RuntimeError(f"duplicate frozen worker identity row: {key!r}")
        rows[key] = row

    for case, route, callable_name, level, marker, match in _FULL_PAGE_IDENTITIES:
        for viewport_name, width, height in _STANDARD_VIEWPORTS:
            key = (
                "scripts/ui_ux_fixture_app.py",
                case,
                route,
                viewport_name,
                width,
                height,
            )
            add(key, {
                "fixtureEntrypoint": key[0],
                "case": case,
                "route": route,
                "viewport": {
                    "name": viewport_name,
                    "width": width,
                    "height": height,
                },
                "registryKey": case,
                "callable": callable_name,
                "rootSelectors": _FULL_PAGE_ROOT_SELECTORS.get(case, ()),
                "affectedRootSelectors": _AFFECTED_ROOT_SELECTORS,
                "readiness": {
                    "kind": "heading",
                    "level": level,
                    "text": marker,
                    "match": match,
                },
            })
    for case, route, registry_key, callable_name in _FOCUSED_IDENTITIES:
        for viewport_name, width, height in _FOCUSED_VIEWPORTS:
            key = (
                "scripts/ui_ux_selection_fixture_app.py",
                case,
                route,
                viewport_name,
                width,
                height,
            )
            add(key, {
                "fixtureEntrypoint": key[0],
                "case": case,
                "route": route,
                "viewport": {
                    "name": viewport_name,
                    "width": width,
                    "height": height,
                },
                "registryKey": registry_key,
                "callable": callable_name,
                "rootSelectors": _FOCUSED_ROOT_SELECTORS[case],
                "affectedRootSelectors": _AFFECTED_ROOT_SELECTORS,
                "readiness": {
                    "kind": "selector",
                    "selector": "#ux1b-selection-ready",
                    "text": case,
                    "match": "exact",
                },
            })
    for viewport_name, width, height in _STANDARD_VIEWPORTS:
        key = (
            "scripts/ui_ux_theme_fixture_app.py",
            "theme-gallery",
            "/",
            viewport_name,
            width,
            height,
        )
        add(key, {
            "fixtureEntrypoint": key[0],
            "case": "theme-gallery",
            "route": "/",
            "viewport": {
                "name": viewport_name,
                "width": width,
                "height": height,
            },
            "registryKey": "theme-gallery",
            "callable": "ui_ux_theme_fixture_app",
            "rootSelectors": (),
            "affectedRootSelectors": _AFFECTED_ROOT_SELECTORS,
            "readiness": {
                "kind": "selector",
                "selector": "#ux1b-theme-ready",
                "text": "ux1b-theme-ready",
                "match": "exact",
                "title": "Quant Radar UX-1B Theme States",
            },
        })
    return rows


_WORKER_IDENTITY_ROWS = MappingProxyType(_build_worker_identity_rows())


def _build_counter_profile_capture_ids() -> Mapping[str, frozenset[str]]:
    profiles: dict[str, set[str]] = {}
    for row in _WORKER_IDENTITY_ROWS.values():
        profiles.setdefault(row["fixtureEntrypoint"], set()).add(
            f'{row["case"]}/{row["viewport"]["name"]}'
        )
    return MappingProxyType(
        {entrypoint: frozenset(capture_ids) for entrypoint, capture_ids in profiles.items()}
    )


_COUNTER_PROFILE_CAPTURE_IDS = _build_counter_profile_capture_ids()


def worker_capture_profile_rows(
    fixture_entrypoint: str,
) -> tuple[dict[str, Any], ...]:
    """Return a defensive copy of one frozen complete capture profile."""

    if fixture_entrypoint not in _COUNTER_PROFILE_CAPTURE_IDS:
        raise _error("worker fixture profile is not frozen")
    rows = [
        row
        for row in _WORKER_IDENTITY_ROWS.values()
        if row["fixtureEntrypoint"] == fixture_entrypoint
    ]
    rows.sort(
        key=lambda row: (
            row["case"],
            row["viewport"]["name"],
            row["viewport"]["width"],
            row["viewport"]["height"],
        )
    )
    return tuple(copy.deepcopy(row) for row in rows)


def focused_control_contract_rows() -> tuple[dict[str, Any], ...]:
    """Return a defensive copy of the trusted eleven-root AX contract."""

    return tuple(
        {
            "case": case,
            "controls": tuple(
                {
                    **dict(control),
                    "optionLabels": tuple(control["optionLabels"]),
                }
                for control in controls
            ),
        }
        for case, controls in _FOCUSED_CONTROL_CONTRACTS.items()
    )


def worker_capture_catalog_summary() -> dict[str, object]:
    rows = [
        _WORKER_IDENTITY_ROWS[key]
        for key in sorted(_WORKER_IDENTITY_ROWS, key=lambda item: tuple(map(str, item)))
    ]
    return {
        "fullPageRows": len(_FULL_PAGE_IDENTITIES) * len(_STANDARD_VIEWPORTS),
        "focusedRows": len(_FOCUSED_IDENTITIES) * len(_FOCUSED_VIEWPORTS),
        "themeRows": len(_STANDARD_VIEWPORTS),
        "totalRows": len(rows),
        "sha256": hashlib.sha256(_canonical_json_bytes(rows)).hexdigest(),
    }


class EvidenceContractError(RuntimeError):
    """Raised when evidence fails a closed contract boundary."""


class DependencyUnavailable(EvidenceContractError):
    """Raised when a required capture dependency is unavailable."""


class InvalidEvidence(EvidenceContractError):
    """Raised when captured bytes are present but invalid."""


class ManifestDurabilityUncertain(EvidenceContractError):
    """Raised after publication when its directory fsync could not be confirmed."""


def _error(message: str, *, cause: BaseException | None = None) -> EvidenceContractError:
    error = EvidenceContractError(message)
    if cause is not None:
        error.__cause__ = cause
    return error


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _error(f"{label} must be a mapping")
    if not all(isinstance(key, str) for key in value):
        raise _error(f"{label} keys must be strings")
    return value


def _require_exact_keys(
    value: Mapping[str, Any], expected: set[str] | frozenset[str], label: str
) -> None:
    observed = set(value)
    if observed != set(expected):
        missing = sorted(set(expected) - observed)
        extra = sorted(observed - set(expected))
        raise _error(f"{label} keys differ (missing={missing}, extra={extra})")


def _canonical_json_bytes(value: object, *, newline: bool = False) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise _error("value is not canonical JSON", cause=exc)
    return (text + ("\n" if newline else "")).encode("utf-8")


def root_capture_expansion_rows() -> tuple[dict[str, Any], ...]:
    """Return the exact catalog-derived Sequence 12 root expansion."""

    rows: list[dict[str, Any]] = []
    for identity in worker_capture_profile_rows(
        "scripts/ui_ux_selection_fixture_app.py"
    ):
        logical_capture_id = (
            f'{identity["case"]}/{identity["viewport"]["name"]}'
        )
        for ordinal, selector in enumerate(
            identity["rootSelectors"],
            start=1,
        ):
            rows.append(
                {
                    "callable": identity["callable"],
                    "case": identity["case"],
                    "fixtureEntrypoint": identity["fixtureEntrypoint"],
                    "logicalCaptureId": logical_capture_id,
                    "rootCaptureId": (
                        f"{logical_capture_id}/root-{ordinal:02d}"
                    ),
                    "rootOrdinal": ordinal,
                    "rootSelector": selector,
                    "route": identity["route"],
                    "viewport": copy.deepcopy(identity["viewport"]),
                }
            )
    raw = _canonical_json_bytes(rows)
    if (
        len(rows) != ROOT_CAPTURE_EXPANSION_ROWS
        or len(raw) != ROOT_CAPTURE_EXPANSION_SIZE
        or hashlib.sha256(raw).hexdigest()
        != ROOT_CAPTURE_EXPANSION_SHA256
    ):
        raise _error("root-capture expansion differs from its frozen contract")
    return tuple(copy.deepcopy(row) for row in rows)


def _root_capture_rows_for_logical(
    logical_capture_id: str,
) -> tuple[dict[str, Any], ...]:
    rows = tuple(
        row
        for row in root_capture_expansion_rows()
        if row["logicalCaptureId"] == logical_capture_id
    )
    if len(rows) not in {1, 2}:
        raise _error("logical root-capture identity is not frozen")
    return rows


def _validate_root_artifact_path(
    value: object,
    *,
    case: str,
    viewport: str,
    ordinal: int,
    leaf: str,
    label: str,
) -> str:
    components = _safe_relative_components(value, label=label)
    expected_tail = (
        case,
        viewport,
        f"root-{ordinal:02d}",
        leaf,
    )
    if len(components) < len(expected_tail) or tuple(
        components[-len(expected_tail) :]
    ) != expected_tail:
        raise _error(f"{label} differs from its root-capture identity")
    return str(value)


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _error(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _decode_json_bytes(raw: bytes, *, maximum: int, label: str) -> Any:
    if not isinstance(raw, bytes):
        raise _error(f"{label} must be bytes")
    if len(raw) > maximum:
        raise _error(f"{label} exceeds {maximum} bytes")
    try:
        text = raw.decode("utf-8", errors="strict")
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                _error(f"{label} contains non-finite number {value}")
            ),
        )
    except EvidenceContractError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _error(f"{label} is not valid UTF-8 JSON", cause=exc)


def _decode_canonical_json_line(raw: bytes, *, maximum: int, label: str) -> dict[str, Any]:
    if not isinstance(raw, bytes):
        raise _error(f"{label} must be bytes")
    if len(raw) > maximum:
        raise _error(f"{label} exceeds {maximum} bytes")
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise _error(f"{label} must contain exactly one newline-terminated record")
    value = _decode_json_bytes(raw[:-1], maximum=maximum - 1, label=label)
    document = dict(_require_mapping(value, label))
    if _canonical_json_bytes(document, newline=True) != raw:
        raise _error(f"{label} is not canonical NDJSON")
    return document


def _safe_relative_components(path: object, *, label: str) -> tuple[str, ...]:
    if not isinstance(path, str) or not path or "\\" in path or path.startswith("/"):
        raise _error(f"{label} must be a safe relative path")
    if path.endswith("/"):
        raise _error(f"{label} must not end with a slash")
    components = tuple(path.split("/"))
    if any(component in {"", ".", ".."} for component in components):
        raise _error(f"{label} contains an unsafe component")
    if any("\x00" in component for component in components):
        raise _error(f"{label} contains NUL")
    return components


def _safe_leaf_name(name: object, *, label: str) -> str:
    components = _safe_relative_components(name, label=label)
    if len(components) != 1:
        raise _error(f"{label} must be a single leaf name")
    return components[0]


def _validate_viewport(value: object, *, label: str) -> dict[str, Any]:
    viewport = _require_mapping(value, label)
    _require_exact_keys(viewport, {"name", "width", "height"}, label)
    if not isinstance(viewport["name"], str) or not viewport["name"]:
        raise _error(f"{label}.name must be non-empty")
    for key in ("width", "height"):
        item = viewport[key]
        if not _is_int(item) or not 1 <= item <= 32_768:
            raise _error(f"{label}.{key} is invalid")
    return dict(viewport)


def _validate_loopback_origin(value: object, *, expected: str) -> None:
    if not isinstance(value, str) or value != expected:
        raise _error("worker appOrigin differs from the coordinator assignment")
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise _error("worker appOrigin has an invalid port", cause=exc)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.username is not None
        or parsed.password is not None
        or port is None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise _error("worker appOrigin is not an exact IPv4 loopback origin")


def _validate_route(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or value.startswith("//")
        or "\\" in value
        or "?" in value
        or "#" in value
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    ):
        raise _error(f"{label} is invalid")
    if value != "/":
        components = value[1:].split("/")
        if any(component in {"", ".", ".."} for component in components):
            raise _error(f"{label} has an ambiguous path component")
    return value


def validate_worker_capture_identity(
    request: Mapping[str, object],
) -> dict[str, Any]:
    """Return the one frozen capture row matching an exact worker request."""

    value = _require_mapping(request, "worker capture identity")
    fixture = value.get("fixtureEntrypoint")
    case = value.get("case")
    route = value.get("route")
    viewport = _validate_viewport(
        value.get("viewport"), label="worker capture identity viewport"
    )
    _validate_route(route, label="worker capture identity route")
    key = (
        fixture,
        case,
        route,
        viewport["name"],
        viewport["width"],
        viewport["height"],
    )
    row = _WORKER_IDENTITY_ROWS.get(key)
    if row is None:
        raise _error("worker capture identity is not in the frozen catalog")
    if value.get("requestId") != f'{case}/{viewport["name"]}':
        raise _error("worker capture identity requestId differs")
    return copy.deepcopy(row)


def decode_worker_request(
    raw: bytes,
    *,
    expected_origin: str,
    allowed_staging_paths: frozenset[str] | set[str],
) -> dict[str, Any]:
    """Decode one exact, canonical browser-worker request record."""

    document = _decode_canonical_json_line(
        raw, maximum=MAX_WORKER_REQUEST_BYTES, label="worker request"
    )
    schema_version = document.get("schemaVersion")
    if schema_version == WORKER_REQUEST_V2_SCHEMA:
        _require_exact_keys(
            document,
            {
                "schemaVersion",
                "requestId",
                "fixtureEntrypoint",
                "case",
                "route",
                "viewport",
                "appOrigin",
                "rootOutputs",
            },
            "worker request",
        )
        for key in ("requestId", "case", "route"):
            if not isinstance(document[key], str) or not document[key]:
                raise _error(f"worker request {key} is invalid")
        _validate_route(document["route"], label="worker request route")
        _safe_relative_components(
            document["fixtureEntrypoint"], label="fixtureEntrypoint"
        )
        if document["fixtureEntrypoint"] not in _ALLOWED_FIXTURE_ENTRYPOINTS:
            raise _error("worker fixtureEntrypoint is not allowlisted")
        viewport = _validate_viewport(
            document["viewport"], label="worker request viewport"
        )
        if document["requestId"] != f'{document["case"]}/{viewport["name"]}':
            raise _error("worker requestId differs from case/viewport identity")
        _validate_loopback_origin(document["appOrigin"], expected=expected_origin)
        validate_worker_capture_identity(document)

        expected_rows = _root_capture_rows_for_logical(document["requestId"])
        root_outputs = document["rootOutputs"]
        if (
            not isinstance(root_outputs, list)
            or len(root_outputs) != len(expected_rows)
        ):
            raise _error("worker request rootOutputs cardinality differs")
        allowed = set(allowed_staging_paths)
        observed_paths: set[str] = set()
        for index, (output_value, expected_row) in enumerate(
            zip(root_outputs, expected_rows, strict=True)
        ):
            output = _require_mapping(
                output_value, f"worker request rootOutputs[{index}]"
            )
            _require_exact_keys(
                output,
                {"rootCaptureId", "rootOrdinal", "rootSelector", "staging"},
                f"worker request rootOutputs[{index}]",
            )
            for key in ("rootCaptureId", "rootOrdinal", "rootSelector"):
                if output[key] != expected_row[key]:
                    raise _error(
                        f"worker request rootOutputs[{index}].{key} differs"
                    )
            staging = _require_mapping(
                output["staging"],
                f"worker request rootOutputs[{index}].staging",
            )
            _require_exact_keys(
                staging,
                {"png", "renderSidecar"},
                f"worker request rootOutputs[{index}].staging",
            )
            ordinal = expected_row["rootOrdinal"]
            png = _validate_root_artifact_path(
                staging["png"],
                case=document["case"],
                viewport=viewport["name"],
                ordinal=ordinal,
                leaf="capture.png",
                label=f"worker request rootOutputs[{index}].staging.png",
            )
            sidecar = _validate_root_artifact_path(
                staging["renderSidecar"],
                case=document["case"],
                viewport=viewport["name"],
                ordinal=ordinal,
                leaf="render.json",
                label=(
                    f"worker request rootOutputs[{index}]"
                    ".staging.renderSidecar"
                ),
            )
            if png == sidecar:
                raise _error("worker request staging paths must be distinct")
            observed_paths.update((png, sidecar))
        if len(observed_paths) != 2 * len(expected_rows):
            raise _error("worker request staging paths are duplicated")
        if observed_paths != allowed:
            raise _error("worker request staging plan is not exactly allowlisted")
        return document

    _require_exact_keys(
        document,
        {
            "schemaVersion",
            "requestId",
            "fixtureEntrypoint",
            "case",
            "route",
            "viewport",
            "appOrigin",
            "staging",
        },
        "worker request",
    )
    if schema_version != WORKER_REQUEST_SCHEMA:
        raise _error("worker request schema is unsupported")
    for key in ("requestId", "case", "route"):
        if not isinstance(document[key], str) or not document[key]:
            raise _error(f"worker request {key} is invalid")
    _validate_route(document["route"], label="worker request route")
    _safe_relative_components(document["fixtureEntrypoint"], label="fixtureEntrypoint")
    if document["fixtureEntrypoint"] not in _ALLOWED_FIXTURE_ENTRYPOINTS:
        raise _error("worker fixtureEntrypoint is not allowlisted")
    viewport = _validate_viewport(document["viewport"], label="worker request viewport")
    if document["requestId"] != f'{document["case"]}/{viewport["name"]}':
        raise _error("worker requestId differs from case/viewport identity")
    _validate_loopback_origin(document["appOrigin"], expected=expected_origin)
    staging = _require_mapping(document["staging"], "worker request staging")
    _require_exact_keys(staging, {"png", "renderSidecar"}, "worker request staging")
    allowed = set(allowed_staging_paths)
    for key in ("png", "renderSidecar"):
        _safe_relative_components(staging[key], label=f"worker request staging.{key}")
        if staging[key] not in allowed:
            raise _error(f"worker request staging.{key} is not allowlisted")
    if staging["png"] == staging["renderSidecar"]:
        raise _error("worker request staging paths must be distinct")
    validate_worker_capture_identity(document)
    return document


def decode_worker_response(
    raw: bytes,
    *,
    expected_request_id: str,
    allowed_artifact_paths: frozenset[str] | set[str],
) -> dict[str, Any]:
    """Decode one exact, non-terminal browser-worker response record."""

    document = _decode_canonical_json_line(
        raw, maximum=MAX_WORKER_RESPONSE_BYTES, label="worker response"
    )
    schema_version = document.get("schemaVersion")
    if schema_version not in {
        WORKER_RESPONSE_SCHEMA,
        WORKER_RESPONSE_V2_SCHEMA,
    }:
        raise _error("worker response schema is unsupported")
    if document.get("requestId") != expected_request_id:
        raise _error("worker response requestId differs")
    status = document.get("status")
    if schema_version == WORKER_RESPONSE_V2_SCHEMA and status == "staged":
        _require_exact_keys(
            document,
            {"schemaVersion", "requestId", "status", "rootArtifacts"},
            "worker staged response",
        )
        expected_rows = _root_capture_rows_for_logical(expected_request_id)
        artifacts = document["rootArtifacts"]
        if not isinstance(artifacts, list) or len(artifacts) != len(expected_rows):
            raise _error("worker response rootArtifacts cardinality differs")
        allowed = set(allowed_artifact_paths)
        observed_paths: set[str] = set()
        case, viewport = expected_request_id.split("/", 1)
        for index, (artifact_value, expected_row) in enumerate(
            zip(artifacts, expected_rows, strict=True)
        ):
            artifact = _require_mapping(
                artifact_value, f"worker response rootArtifacts[{index}]"
            )
            _require_exact_keys(
                artifact,
                {
                    "rootCaptureId",
                    "logicalCaptureId",
                    "rootOrdinal",
                    "rootSelector",
                    "png",
                    "renderSidecar",
                },
                f"worker response rootArtifacts[{index}]",
            )
            for key in (
                "rootCaptureId",
                "logicalCaptureId",
                "rootOrdinal",
                "rootSelector",
            ):
                if artifact[key] != expected_row[key]:
                    raise _error(
                        f"worker response rootArtifacts[{index}].{key} differs"
                    )
            ordinal = expected_row["rootOrdinal"]
            png = _validate_root_artifact_path(
                artifact["png"],
                case=case,
                viewport=viewport,
                ordinal=ordinal,
                leaf="capture.png",
                label=f"worker response rootArtifacts[{index}].png",
            )
            sidecar = _validate_root_artifact_path(
                artifact["renderSidecar"],
                case=case,
                viewport=viewport,
                ordinal=ordinal,
                leaf="render.json",
                label=(
                    f"worker response rootArtifacts[{index}].renderSidecar"
                ),
            )
            observed_paths.update((png, sidecar))
        if len(observed_paths) != 2 * len(expected_rows):
            raise _error("worker response artifact paths are duplicated")
        if observed_paths != allowed:
            raise _error("worker response artifacts are not exactly allowlisted")
        return document

    if status == "staged":
        if schema_version != WORKER_RESPONSE_SCHEMA:
            raise _error("worker staged response schema is unsupported")
        _require_exact_keys(
            document,
            {"schemaVersion", "requestId", "status", "artifacts"},
            "worker staged response",
        )
        artifacts = _require_mapping(document["artifacts"], "worker response artifacts")
        _require_exact_keys(artifacts, {"png", "renderSidecar"}, "worker response artifacts")
        allowed = set(allowed_artifact_paths)
        for key in ("png", "renderSidecar"):
            _safe_relative_components(artifacts[key], label=f"worker response artifacts.{key}")
            if artifacts[key] not in allowed:
                raise _error(f"worker response artifacts.{key} is not allowlisted")
        if artifacts["png"] == artifacts["renderSidecar"]:
            raise _error("worker response artifact paths must be distinct")
    elif status in {"failed", "dependency_unavailable", "invalid_data", "interrupted"}:
        _require_exact_keys(
            document,
            {"schemaVersion", "requestId", "status", "error"},
            "worker failure response",
        )
        failure = _require_mapping(document["error"], "worker response error")
        _require_exact_keys(failure, {"type", "message"}, "worker response error")
        if (
            not isinstance(failure["type"], str)
            or not failure["type"]
            or not isinstance(failure["message"], str)
            or len(_canonical_json_bytes(dict(failure))) > MAX_MANIFEST_ERROR_BYTES
        ):
            raise _error("worker response error is invalid or oversized")
    else:
        raise _error("worker response has an unsupported status")
    return document


@dataclass(frozen=True, slots=True)
class PathComponentContract:
    name: str
    device: int
    inode: int
    owner_uid: int
    mode: int


@dataclass(frozen=True, slots=True)
class ArtifactLeafContract:
    name: str
    device: int
    inode: int
    owner_uid: int
    mode: int
    link_count: int
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ArtifactContract:
    relative_path: str
    root: PathComponentContract
    parents: tuple[PathComponentContract, ...]
    leaf: ArtifactLeafContract
    max_bytes: int


def _directory_contract(name: str, observed: os.stat_result, *, expected_owner: int) -> PathComponentContract:
    if not stat.S_ISDIR(observed.st_mode) or observed.st_uid != expected_owner:
        raise _error(f"artifact directory {name!r} is not an owned directory")
    return PathComponentContract(
        name=name,
        device=observed.st_dev,
        inode=observed.st_ino,
        owner_uid=observed.st_uid,
        mode=stat.S_IMODE(observed.st_mode),
    )


def _matches_directory(observed: os.stat_result, contract: PathComponentContract) -> bool:
    return (
        stat.S_ISDIR(observed.st_mode)
        and observed.st_dev == contract.device
        and observed.st_ino == contract.inode
        and observed.st_uid == contract.owner_uid
        and stat.S_IMODE(observed.st_mode) == contract.mode
    )


def _open_directory_at(directory_fd: int, name: str) -> int:
    try:
        return os.open(
            name,
            os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC,
            dir_fd=directory_fd,
        )
    except OSError as exc:
        raise _error(f"could not open artifact directory {name!r}", cause=exc)


def _open_leaf_at(directory_fd: int, name: str) -> int:
    try:
        return os.open(
            name,
            os.O_RDONLY | os.O_NONBLOCK | _O_NOFOLLOW | _O_CLOEXEC,
            dir_fd=directory_fd,
        )
    except OSError as exc:
        raise _error(f"could not open artifact leaf {name!r}", cause=exc)


def _hash_descriptor(descriptor: int, *, maximum: int) -> tuple[bytes, str, os.stat_result]:
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode) or before.st_size < 0 or before.st_size > maximum:
        raise _error("artifact is not a bounded regular file")
    chunks: list[bytes] = []
    digest = hashlib.sha256()
    offset = 0
    while offset < before.st_size:
        chunk = os.pread(descriptor, min(1024 * 1024, before.st_size - offset), offset)
        if not chunk:
            raise _error("artifact became shorter while reading")
        chunks.append(chunk)
        digest.update(chunk)
        offset += len(chunk)
    after = os.fstat(descriptor)
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_uid,
        stat.S_IMODE(before.st_mode),
        before.st_nlink,
        before.st_size,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_uid,
        stat.S_IMODE(after.st_mode),
        after.st_nlink,
        after.st_size,
    )
    if identity_after != identity_before:
        raise _error("artifact identity changed while reading")
    return b"".join(chunks), digest.hexdigest(), after


def _leaf_matches(observed: os.stat_result, contract: ArtifactLeafContract) -> bool:
    return (
        stat.S_ISREG(observed.st_mode)
        and observed.st_dev == contract.device
        and observed.st_ino == contract.inode
        and observed.st_uid == contract.owner_uid
        and stat.S_IMODE(observed.st_mode) == contract.mode
        and observed.st_nlink == contract.link_count == 1
        and observed.st_size == contract.size
    )


def freeze_artifact_contract(
    root_fd: int,
    relative_path: str,
    *,
    expected_owner: int,
    max_bytes: int = MAX_AUTHENTICATED_ARTIFACT_BYTES,
) -> ArtifactContract:
    """Freeze every directory component and the final regular-file inode."""

    if not _is_int(expected_owner) or not _is_int(max_bytes) or max_bytes < 0:
        raise _error("artifact owner or size bound is invalid")
    components = _safe_relative_components(relative_path, label="artifact path")
    try:
        root_observed = os.fstat(root_fd)
    except OSError as exc:
        raise _error("artifact root descriptor is invalid", cause=exc)
    root_contract = _directory_contract(".", root_observed, expected_owner=expected_owner)
    current = os.dup(root_fd)
    parents: list[PathComponentContract] = []
    try:
        for component in components[:-1]:
            child = _open_directory_at(current, component)
            try:
                observed = os.fstat(child)
                contract = _directory_contract(
                    component, observed, expected_owner=expected_owner
                )
            except BaseException:
                os.close(child)
                raise
            os.close(current)
            current = child
            parents.append(contract)
        leaf_fd = _open_leaf_at(current, components[-1])
        try:
            raw, sha256, observed = _hash_descriptor(leaf_fd, maximum=max_bytes)
            del raw
            if (
                not stat.S_ISREG(observed.st_mode)
                or observed.st_uid != expected_owner
                or observed.st_nlink != 1
            ):
                raise _error("artifact leaf must be an owned one-link regular file")
            leaf = ArtifactLeafContract(
                name=components[-1],
                device=observed.st_dev,
                inode=observed.st_ino,
                owner_uid=observed.st_uid,
                mode=stat.S_IMODE(observed.st_mode),
                link_count=observed.st_nlink,
                size=observed.st_size,
                sha256=sha256,
            )
        finally:
            os.close(leaf_fd)
    finally:
        os.close(current)
    return ArtifactContract(
        relative_path=relative_path,
        root=root_contract,
        parents=tuple(parents),
        leaf=leaf,
        max_bytes=max_bytes,
    )


_AUTHENTICATED_ARTIFACT_KEY = object()
_AUTHENTICATED_ARTIFACTS: dict[int, AuthenticatedArtifact] = {}
_AUTHENTICATED_ARTIFACTS_LOCK = threading.Lock()


class AuthenticatedArtifact:
    """A retained, authenticated leaf descriptor."""

    __slots__ = ("descriptor", "contract", "_closed")

    def __init__(
        self, descriptor: int, contract: ArtifactContract, *, _key: object
    ) -> None:
        if _key is not _AUTHENTICATED_ARTIFACT_KEY:
            raise _error("authenticated artifacts can only be created by descriptor authentication")
        self.descriptor = descriptor
        self.contract = contract
        self._closed = False

    def __copy__(self) -> AuthenticatedArtifact:
        raise TypeError("authenticated artifacts cannot be copied")

    def __deepcopy__(self, _memo: object) -> AuthenticatedArtifact:
        raise TypeError("authenticated artifacts cannot be copied")

    def __enter__(self) -> AuthenticatedArtifact:
        if self._closed:
            raise _error("authenticated artifact is already closed")
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            with _AUTHENTICATED_ARTIFACTS_LOCK:
                registered = _AUTHENTICATED_ARTIFACTS.get(id(self))
                if registered is self:
                    _AUTHENTICATED_ARTIFACTS.pop(id(self), None)
            os.close(self.descriptor)
            self._closed = True

    def _require_open(self) -> None:
        if self._closed:
            raise _error("authenticated artifact is closed")


def open_authenticated_artifact(
    root_fd: int, contract: ArtifactContract
) -> AuthenticatedArtifact:
    if not isinstance(contract, ArtifactContract):
        raise _error("artifact contract has the wrong type")
    try:
        root_observed = os.fstat(root_fd)
    except OSError as exc:
        raise _error("artifact root descriptor is invalid", cause=exc)
    if not _matches_directory(root_observed, contract.root):
        raise _error("artifact root identity changed")
    components = _safe_relative_components(contract.relative_path, label="artifact path")
    if tuple(component.name for component in contract.parents) != components[:-1]:
        raise _error("artifact parent contract differs from its path")
    if contract.leaf.name != components[-1]:
        raise _error("artifact leaf contract differs from its path")
    current = os.dup(root_fd)
    try:
        for expected in contract.parents:
            child = _open_directory_at(current, expected.name)
            observed = os.fstat(child)
            if not _matches_directory(observed, expected):
                os.close(child)
                raise _error(f"artifact directory {expected.name!r} identity changed")
            os.close(current)
            current = child
        leaf_fd = _open_leaf_at(current, contract.leaf.name)
        try:
            raw, sha256, observed = _hash_descriptor(leaf_fd, maximum=contract.max_bytes)
            del raw
            if not _leaf_matches(observed, contract.leaf) or sha256 != contract.leaf.sha256:
                raise _error("artifact leaf identity or digest changed")
        except BaseException:
            os.close(leaf_fd)
            raise
    finally:
        os.close(current)
    artifact = AuthenticatedArtifact(
        leaf_fd, contract, _key=_AUTHENTICATED_ARTIFACT_KEY
    )
    with _AUTHENTICATED_ARTIFACTS_LOCK:
        _AUTHENTICATED_ARTIFACTS[id(artifact)] = artifact
    return artifact


def _write_all(descriptor: int, raw: bytes) -> None:
    offset = 0
    while offset < len(raw):
        written = os.write(descriptor, raw[offset:])
        if written <= 0:
            raise _error("short write while copying evidence")
        offset += written


def copy_authenticated_artifact(
    artifact: AuthenticatedArtifact,
    output_dir_fd: int,
    output_name: str,
) -> dict[str, object]:
    """Copy from a retained descriptor and publish with no-replace semantics."""

    if not isinstance(artifact, AuthenticatedArtifact):
        raise _error("artifact has the wrong type")
    with _AUTHENTICATED_ARTIFACTS_LOCK:
        if _AUTHENTICATED_ARTIFACTS.get(id(artifact)) is not artifact:
            raise _error("artifact lacks live descriptor provenance")
    artifact._require_open()
    name = _safe_leaf_name(output_name, label="output name")
    output_stat = os.fstat(output_dir_fd)
    if not stat.S_ISDIR(output_stat.st_mode) or output_stat.st_uid != os.getuid():
        raise _error("output descriptor is not an owned directory")
    before = os.fstat(artifact.descriptor)
    if not _leaf_matches(before, artifact.contract.leaf):
        raise _error("authenticated source identity changed before copy")
    temporary = f".{name}.{secrets.token_hex(12)}.tmp"
    temporary_fd: int | None = None
    published = False
    try:
        temporary_fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW | _O_CLOEXEC,
            0o600,
            dir_fd=output_dir_fd,
        )
        digest = hashlib.sha256()
        offset = 0
        while offset < artifact.contract.leaf.size:
            chunk = os.pread(
                artifact.descriptor,
                min(1024 * 1024, artifact.contract.leaf.size - offset),
                offset,
            )
            if not chunk:
                raise _error("authenticated source became shorter during copy")
            _write_all(temporary_fd, chunk)
            digest.update(chunk)
            offset += len(chunk)
        os.fsync(temporary_fd)
        _rehash_raw, rehash, rehash_stat = _hash_descriptor(
            artifact.descriptor, maximum=artifact.contract.max_bytes
        )
        del _rehash_raw
        after = os.fstat(artifact.descriptor)
        if (
            not _leaf_matches(after, artifact.contract.leaf)
            or not _leaf_matches(rehash_stat, artifact.contract.leaf)
            or digest.hexdigest() != artifact.contract.leaf.sha256
            or rehash != artifact.contract.leaf.sha256
            or offset != artifact.contract.leaf.size
        ):
            raise _error("authenticated source changed during copy")
        os.close(temporary_fd)
        temporary_fd = None
        try:
            os.link(
                temporary,
                name,
                src_dir_fd=output_dir_fd,
                dst_dir_fd=output_dir_fd,
                follow_symlinks=False,
            )
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                raise _error("final evidence output already exists", cause=exc)
            raise _error("could not publish final evidence output", cause=exc)
        os.unlink(temporary, dir_fd=output_dir_fd)
        temporary = ""
        os.fsync(output_dir_fd)
        published = True
        return {
            "path": name,
            "sha256": digest.hexdigest(),
            "size": offset,
        }
    finally:
        if temporary_fd is not None:
            os.close(temporary_fd)
        try:
            if temporary:
                os.unlink(temporary, dir_fd=output_dir_fd)
        except FileNotFoundError:
            pass
        if not published:
            # The exclusive hard-link publish either succeeded completely or
            # left the caller's pre-existing destination untouched.
            pass


def _normalize_owned_path(
    value: str, roots: tuple[tuple[str, str], ...]
) -> str:
    if value.startswith("$OWNED_ROOT_"):
        token, separator, suffix_value = value.partition("/")
        if token not in {item[1] for item in roots} and roots:
            raise _error("canonical runtime path uses an unknown owned-root role")
        suffix = f"/{suffix_value}" if separator else ""
        if suffix and (not suffix.startswith("/") or "/../" in f"{suffix}/"):
            raise _error("canonical runtime path has an unsafe suffix")
        return value
    if not os.path.isabs(value):
        raise _error("runtime projection path must be absolute")
    normalized = os.path.normpath(value)
    for root, token in sorted(roots, key=lambda item: len(item[0]), reverse=True):
        try:
            common = os.path.commonpath((normalized, root))
        except ValueError:
            continue
        if common == root:
            relative = os.path.relpath(normalized, root)
            return token if relative == "." else f"{token}/{relative}"
    raise _error("runtime projection contains an unowned absolute path")


def _validate_json_tree(value: object, *, label: str) -> None:
    if value is None or isinstance(value, (str, bool)) or _is_int(value):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise _error(f"{label} contains a non-finite number")
        return
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise _error(f"{label} has a non-string key")
        for key, item in value.items():
            _validate_json_tree(item, label=f"{label}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_json_tree(item, label=f"{label}[{index}]")
        return
    raise _error(f"{label} contains a non-JSON value")


def _validate_counters(value: object, *, label: str) -> dict[str, int]:
    counters = _require_mapping(value, label)
    result: dict[str, int] = {}
    for key, item in counters.items():
        if not key or not _is_int(item) or item < 0:
            raise _error(f"{label} contains an invalid counter")
        result[key] = item
    return result


def _theme_number(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _error(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise _error(f"{label} must be a finite number")
    return result


def _theme_rgb(
    value: object,
    *,
    label: str,
    expected: tuple[int, int, int] | None = None,
    tolerance: int = 0,
) -> tuple[int, int, int]:
    if (
        not isinstance(value, list)
        or len(value) != 3
        or any(not _is_int(channel) or not 0 <= channel <= 255 for channel in value)
    ):
        raise _error(f"{label} must be exact RGB")
    result = tuple(value)
    if expected is not None and any(
        abs(actual - wanted) > tolerance
        for actual, wanted in zip(result, expected)
    ):
        raise _error(f"{label} differs from its exact color role")
    return result  # type: ignore[return-value]


def _validate_theme_selector_evidence(
    value: object, *, viewport_name: str
) -> None:
    selector_evidence = _require_mapping(value, "theme selector evidence")
    _require_exact_keys(
        selector_evidence,
        {"browser", "viewport", "selectors", "sha256"},
        "theme selector evidence",
    )
    if (
        selector_evidence["browser"] != "chromium"
        or selector_evidence["viewport"] != viewport_name
        or not _is_sha256(selector_evidence["sha256"])
    ):
        raise _error("theme selector evidence identity differs")
    selector_digest_payload = {
        key: selector_evidence[key]
        for key in selector_evidence
        if key != "sha256"
    }
    if hashlib.sha256(_canonical_json_bytes(selector_digest_payload)).hexdigest() != selector_evidence["sha256"]:
        raise _error("theme selector evidence digest differs")
    selectors = _require_mapping(
        selector_evidence["selectors"], "theme selector observations"
    )
    if not selectors:
        raise _error("theme selector observations are empty")
    signature_keys = {
        "owner",
        "node",
        "tag",
        "testid",
        "kind",
        "role",
        "ariaSelected",
        "ariaChecked",
    }
    for css_selector, raw_row in selectors.items():
        if not isinstance(css_selector, str) or not css_selector.strip():
            raise _error("theme selector observation has an invalid selector")
        row = _require_mapping(raw_row, f"theme selector {css_selector}")
        _require_exact_keys(
            row,
            {
                "states",
                "owners",
                "nodes",
                "signatures",
                "observations",
                "visitedComputedStyleClaimed",
            },
            f"theme selector {css_selector}",
        )
        states = row["states"]
        owners = row["owners"]
        nodes = row["nodes"]
        signatures = row["signatures"]
        observations = row["observations"]
        if (
            not isinstance(states, list)
            or not states
            or any(not isinstance(state, str) for state in states)
            or len(states) != len(set(states))
            or not set(states).issubset(_THEME_SELECTOR_STATES)
            or not isinstance(owners, list)
            or not owners
            or any(not isinstance(owner, str) for owner in owners)
            or owners != sorted(set(owners))
            or any(_THEME_OWNER_RE.fullmatch(owner) is None for owner in owners)
            or nodes != sorted(f"{owner}::0" for owner in owners)
            or not isinstance(signatures, list)
            or len(signatures) != len(owners)
            or not isinstance(observations, list)
            or not observations
            or row["visitedComputedStyleClaimed"] is not False
        ):
            raise _error(f"theme selector observation differs: {css_selector}")
        for owner, raw_signature in zip(owners, signatures):
            signature = _require_mapping(
                raw_signature, f"theme selector signature {css_selector}"
            )
            _require_exact_keys(
                signature, signature_keys, f"theme selector signature {css_selector}"
            )
            if (
                signature["owner"] != owner
                or signature["node"] != f"{owner}::0"
                or not isinstance(signature["tag"], str)
                or not signature["tag"]
                or any(
                    signature[key] is not None
                    and not isinstance(signature[key], str)
                    for key in (
                        "testid",
                        "kind",
                        "role",
                        "ariaSelected",
                        "ariaChecked",
                    )
                )
            ):
                raise _error(f"theme selector signature differs: {css_selector}")
        observed_owners: set[str] = set()
        for raw_observation in observations:
            observation = _require_mapping(
                raw_observation, f"theme selector transition {css_selector}"
            )
            if set(observation) == {"owner", "matches"}:
                owner = observation["owner"]
                if owner not in owners or observation["matches"] != 1:
                    raise _error(f"theme selector transition differs: {css_selector}")
                observed_owners.add(owner)
            elif set(observation) == {"owners", "matches"}:
                if (
                    not isinstance(observation["owners"], list)
                    or any(
                        not isinstance(owner, str)
                        for owner in observation["owners"]
                    )
                    or len(observation["owners"]) != len(set(observation["owners"]))
                    or set(observation["owners"]) != set(owners)
                    or observation["matches"] != len(owners)
                ):
                    raise _error(f"theme selector transition differs: {css_selector}")
                observed_owners.update(owners)
            else:
                raise _error(f"theme selector transition schema differs: {css_selector}")
        if observed_owners != set(owners):
            raise _error(f"theme selector transition owners differ: {css_selector}")


def _validate_theme_selected_controls(value: object, *, surface: str) -> None:
    controls = _require_mapping(value, f"theme selected controls {surface}")
    _require_exact_keys(
        controls, set(_THEME_SELECTED_CASES), f"theme selected controls {surface}"
    )
    part_names = {
        "checkbox": {"box", "mark"},
        "radio": {"boundary", "dot"},
        "radio_horizontal": {"boundary", "dot"},
        "toggle": {"track", "thumb"},
        "slider": {"selectedTrack", "unselectedTrack", "thumb", "valueLabel"},
        "selectbox": set(),
    }
    for case in _THEME_SELECTED_CASES:
        row = _require_mapping(controls[case], f"theme selected {surface}/{case}")
        _require_exact_keys(
            row,
            {"semantics", "label", "parts", "domParts", "owner"},
            f"theme selected {surface}/{case}",
        )
        if row["owner"] != f"ux1b_owner_{surface}_{case}":
            raise _error(f"theme selected owner differs: {surface}/{case}")
        label = _require_mapping(row["label"], f"theme selected label {surface}/{case}")
        if _theme_number(label.get("textContrast"), label=f"theme selected label {surface}/{case}") < 4.5:
            raise _error(f"theme selected label contrast differs: {surface}/{case}")
        if not isinstance(row["domParts"], Mapping):
            raise _error(f"theme selected DOM parts differ: {surface}/{case}")
        parts = _require_mapping(row["parts"], f"theme selected parts {surface}/{case}")
        _require_exact_keys(parts, part_names[case], f"theme selected parts {surface}/{case}")
        for name, raw_part in parts.items():
            part = _require_mapping(raw_part, f"theme selected part {surface}/{case}/{name}")
            _require_exact_keys(
                part,
                {
                    "node",
                    "paint",
                    "actual",
                    "adjacent",
                    "composited",
                    "source",
                    "expectedRole",
                    "adjacentRole",
                    "minimumContrast",
                    "contrast",
                },
                f"theme selected part {surface}/{case}/{name}",
            )
            _theme_rgb(part["actual"], label=f"theme selected actual {surface}/{case}/{name}")
            _theme_rgb(part["adjacent"], label=f"theme selected adjacent {surface}/{case}/{name}")
            minimum = 4.5 if case == "slider" and name == "valueLabel" else 3.0
            if (
                not isinstance(part["node"], str)
                or not part["node"]
                or not isinstance(part["paint"], str)
                or not part["paint"]
                or part["composited"] is not True
                or part["source"] not in {"computed-style", "rendered-pixel"}
                or _theme_number(
                    part["minimumContrast"],
                    label=f"theme selected minimum {surface}/{case}/{name}",
                )
                != minimum
                or _theme_number(
                    part["contrast"],
                    label=f"theme selected contrast {surface}/{case}/{name}",
                )
                < minimum
            ):
                raise _error(f"theme selected part differs: {surface}/{case}/{name}")
        semantics = _require_mapping(
            row["semantics"], f"theme selected semantics {surface}/{case}"
        )
        if case == "radio_horizontal":
            _require_exact_keys(
                semantics,
                {
                    "groupRole",
                    "groupName",
                    "optionRole",
                    "optionLabels",
                    "checkedLabels",
                    "tabSequenceLabels",
                    "afterArrowRight",
                    "afterArrowLeft",
                    "layout",
                    "selectionBasis",
                },
                f"theme horizontal-radio semantics {surface}",
            )
            expected = {
                "groupRole": "radiogroup",
                "groupName": "水平單選標籤",
                "optionRole": "radio",
                "optionLabels": ["已選項", "其他項"],
                "checkedLabels": ["已選項"],
                "tabSequenceLabels": ["已選項"],
                "afterArrowRight": "其他項",
                "afterArrowLeft": "已選項",
                "selectionBasis": "native-radio/one-checked/roving-tabstop",
            }
            if any(semantics[key] != expected[key] for key in expected):
                raise _error(f"theme horizontal-radio semantics differ: {surface}")
            layout = semantics["layout"]
            if not isinstance(layout, list) or len(layout) != 2:
                raise _error(f"theme horizontal-radio layout differs: {surface}")
            normalized_layout: list[dict[str, float]] = []
            for raw_geometry in layout:
                geometry = _require_mapping(
                    raw_geometry, f"theme horizontal-radio layout {surface}"
                )
                _require_exact_keys(
                    geometry,
                    {"left", "right", "top", "bottom", "width", "height"},
                    f"theme horizontal-radio layout {surface}",
                )
                normalized_layout.append(
                    {
                        key: _theme_number(
                            geometry[key],
                            label=f"theme horizontal-radio layout {surface}.{key}",
                        )
                        for key in geometry
                    }
                )
            if (
                normalized_layout[1]["left"] <= normalized_layout[0]["left"]
                or abs(normalized_layout[1]["top"] - normalized_layout[0]["top"]) > 1.0
                or min(
                    normalized_layout[0]["width"],
                    normalized_layout[0]["height"],
                    normalized_layout[1]["width"],
                    normalized_layout[1]["height"],
                )
                < 24.0
            ):
                raise _error(f"theme horizontal-radio layout differs: {surface}")
        elif case == "selectbox":
            _require_exact_keys(
                semantics,
                {
                    "role",
                    "accessibleName",
                    "optionLabels",
                    "selectedText",
                    "afterArrowDown",
                    "afterArrowUp",
                    "selectionBasis",
                    "selectedValue",
                },
                f"theme selectbox semantics {surface}",
            )
            expected = {
                "role": "combobox",
                "accessibleName": "下拉選單標籤",
                "optionLabels": ["已選項", "其他項"],
                "selectedText": "已選項",
                "afterArrowDown": "其他項",
                "afterArrowUp": "已選項",
                "selectionBasis": "combobox/exact-option-order/keyboard",
            }
            if any(semantics[key] != expected[key] for key in expected):
                raise _error(f"theme selectbox semantics differ: {surface}")
            selected_value = _require_mapping(
                semantics["selectedValue"], f"theme selectbox selected value {surface}"
            )
            if _theme_number(
                selected_value.get("textContrast"),
                label=f"theme selectbox selected value {surface}",
            ) < 4.5:
                raise _error(f"theme selectbox value contrast differs: {surface}")


def _validate_theme_focus(value: object, *, surface: str, surface_rgb: tuple[int, int, int]) -> None:
    focus = _require_mapping(value, f"theme focus {surface}")
    _require_exact_keys(focus, set(_THEME_FOCUS_CASES), f"theme focus {surface}")
    for case in _THEME_FOCUS_CASES:
        row = _require_mapping(focus[case], f"theme focus {surface}/{case}")
        _require_exact_keys(
            row,
            {
                "keyboard",
                "outlineWidth",
                "outlineOffset",
                "outlineColor",
                "deviceScaleFactor",
                "samples",
            },
            f"theme focus {surface}/{case}",
        )
        if (
            row["keyboard"] != "Tab then Shift+Tab"
            or row["outlineColor"] != "rgb(127, 227, 240)"
            or row["deviceScaleFactor"] != 1
            or _theme_number(row["outlineWidth"], label=f"theme focus width {surface}/{case}") < 3.0
            or _theme_number(row["outlineOffset"], label=f"theme focus offset {surface}/{case}") < 1.0
        ):
            raise _error(f"theme focus identity differs: {surface}/{case}")
        samples = _require_mapping(row["samples"], f"theme focus samples {surface}/{case}")
        _require_exact_keys(
            samples, set(_THEME_FOCUS_SIDES), f"theme focus samples {surface}/{case}"
        )
        for side in _THEME_FOCUS_SIDES:
            sample = _require_mapping(
                samples[side], f"theme focus sample {surface}/{case}/{side}"
            )
            _require_exact_keys(
                sample,
                {"gap", "ring", "outer", "clipped"},
                f"theme focus sample {surface}/{case}/{side}",
            )
            _theme_rgb(
                sample["gap"],
                label=f"theme focus gap {surface}/{case}/{side}",
                expected=surface_rgb,
                tolerance=3,
            )
            _theme_rgb(
                sample["ring"],
                label=f"theme focus ring {surface}/{case}/{side}",
                expected=_THEME_FOCUS_RGB,
                tolerance=3,
            )
            _theme_rgb(
                sample["outer"],
                label=f"theme focus outer {surface}/{case}/{side}",
                expected=surface_rgb,
                tolerance=3,
            )
            if sample["clipped"] is not False:
                raise _error(f"theme focus is clipped: {surface}/{case}/{side}")


def _validate_theme_surface_states(
    value: object, *, surface: str, surface_rgb: tuple[int, int, int]
) -> None:
    states = _require_mapping(value, f"theme states {surface}")
    _require_exact_keys(
        states,
        {
            "primary",
            "tertiary",
            "disabled",
            "tabs",
            "markdownLink",
            "selectedControls",
            "alerts",
            "signals",
            "focus",
        },
        f"theme states {surface}",
    )
    primary = _require_mapping(states["primary"], f"theme primary {surface}")
    _require_exact_keys(primary, set(_THEME_PRIMARY_CASES), f"theme primary {surface}")
    for case in _THEME_PRIMARY_CASES:
        row = _require_mapping(primary[case], f"theme primary {surface}/{case}")
        _require_exact_keys(
            row, {"default", "hover", "active"}, f"theme primary {surface}/{case}"
        )
        for snapshot in row.values():
            _require_mapping(snapshot, f"theme primary snapshot {surface}/{case}")
    tertiary = _require_mapping(states["tertiary"], f"theme tertiary {surface}")
    _require_exact_keys(
        tertiary, {"default", "hover", "active"}, f"theme tertiary {surface}"
    )
    disabled = _require_mapping(states["disabled"], f"theme disabled {surface}")
    _require_exact_keys(disabled, {"semantics", "default"}, f"theme disabled {surface}")
    disabled_semantics = _require_mapping(
        disabled["semantics"], f"theme disabled semantics {surface}"
    )
    _require_exact_keys(
        disabled_semantics,
        {
            "disabled",
            "ariaDisabled",
            "programmaticClickEvents",
            "focusAccepted",
            "inactiveContrastException",
        },
        f"theme disabled semantics {surface}",
    )
    if (
        disabled_semantics["disabled"] is not True
        or disabled_semantics["programmaticClickEvents"] != 0
        or disabled_semantics["focusAccepted"] is not False
        or disabled_semantics["inactiveContrastException"] is not True
    ):
        raise _error(f"theme disabled semantics differ: {surface}")
    tabs = _require_mapping(states["tabs"], f"theme tabs {surface}")
    _require_exact_keys(tabs, {"active", "hover", "semantics"}, f"theme tabs {surface}")
    tab_semantics = _require_mapping(tabs["semantics"], f"theme tab semantics {surface}")
    _require_exact_keys(tab_semantics, {"ariaSelected", "underline"}, f"theme tab semantics {surface}")
    if tab_semantics["ariaSelected"] != "true" or not isinstance(tab_semantics["underline"], list) or not tab_semantics["underline"]:
        raise _error(f"theme tab semantics differ: {surface}")
    markdown = _require_mapping(states["markdownLink"], f"theme markdown link {surface}")
    _require_exact_keys(markdown, {"default", "hover", "visited"}, f"theme markdown link {surface}")
    if markdown["visited"] != "static-only; no protected-history claim":
        raise _error(f"theme markdown visited claim differs: {surface}")
    _validate_theme_selected_controls(states["selectedControls"], surface=surface)
    alerts = states["alerts"]
    expected_alerts = ("資訊狀態", "成功狀態", "警告狀態", "錯誤狀態")
    if not isinstance(alerts, list) or len(alerts) != len(expected_alerts):
        raise _error(f"theme alerts differ: {surface}")
    for meaning, raw_alert in zip(expected_alerts, alerts):
        alert = _require_mapping(raw_alert, f"theme alert {surface}/{meaning}")
        _require_exact_keys(alert, {"role", "meaning", "hasIcon", "style"}, f"theme alert {surface}/{meaning}")
        if alert["role"] != "alert" or alert["meaning"] != meaning or alert["hasIcon"] is not True:
            raise _error(f"theme alert semantics differ: {surface}/{meaning}")
        _require_mapping(alert["style"], f"theme alert style {surface}/{meaning}")
    signals = states["signals"]
    expected_signals = (("AVOID", "#ef4444"), ("Bearish", "#ef553b"))
    if not isinstance(signals, list) or len(signals) != len(expected_signals):
        raise _error(f"theme signals differ: {surface}")
    for (meaning, color), raw_signal in zip(expected_signals, signals):
        signal = _require_mapping(raw_signal, f"theme signal {surface}/{meaning}")
        _require_exact_keys(signal, {"meaning", "color", "hasIcon", "text"}, f"theme signal {surface}/{meaning}")
        if (
            signal["meaning"] != meaning
            or signal["color"] != color
            or signal["hasIcon"] is not True
            or not isinstance(signal["text"], str)
            or meaning not in signal["text"]
        ):
            raise _error(f"theme signal semantics differ: {surface}/{meaning}")
    _validate_theme_focus(states["focus"], surface=surface, surface_rgb=surface_rgb)


def validate_theme_worker_evidence(
    value: object, *, expected_viewport: Mapping[str, object]
) -> dict[str, Any]:
    """Validate the exact rich theme envelope embedded in a raw sidecar."""

    viewport_identity = _validate_viewport(
        expected_viewport, label="theme expected viewport"
    )
    rich = _require_mapping(value, "theme worker evidence")
    _require_exact_keys(
        rich,
        {
            "schemaVersion",
            "browser",
            "viewport",
            "fullPage",
            "caseContract",
            "selectorContractSha256",
            "selectorEvidence",
            "surfaces",
            "sourceDigest",
            "sha256",
        },
        "theme worker evidence",
    )
    if rich["schemaVersion"] != THEME_WORKER_EVIDENCE_SCHEMA or not _is_sha256(rich["sha256"]):
        raise _error("theme worker evidence identity differs")
    digest_payload = {key: rich[key] for key in rich if key != "sha256"}
    if hashlib.sha256(_canonical_json_bytes(digest_payload)).hexdigest() != rich["sha256"]:
        raise _error("theme worker evidence digest differs")
    browser = _require_mapping(rich["browser"], "theme worker browser")
    _require_exact_keys(browser, {"name", "version"}, "theme worker browser")
    if browser["name"] != "chromium" or not isinstance(browser["version"], str) or not browser["version"]:
        raise _error("theme worker browser differs")
    viewport = _require_mapping(rich["viewport"], "theme worker viewport")
    _require_exact_keys(
        viewport,
        {"name", "width", "height", "deviceScaleFactor"},
        "theme worker viewport",
    )
    if dict(viewport) != {**viewport_identity, "deviceScaleFactor": 1}:
        raise _error("theme worker viewport differs")
    full_page = _require_mapping(rich["fullPage"], "theme worker full page")
    _require_exact_keys(
        full_page, {"width", "height", "deviceScaleFactor"}, "theme worker full page"
    )
    if (
        not _is_int(full_page["width"])
        or not _is_int(full_page["height"])
        or full_page["width"] != viewport_identity["width"]
        or full_page["height"] < viewport_identity["height"]
        or full_page["deviceScaleFactor"] != 1
    ):
        raise _error("theme worker full-page geometry differs")
    case_contract = _require_mapping(rich["caseContract"], "theme case contract")
    _require_exact_keys(
        case_contract,
        {"galleryCases", "focusCases", "ownerCount", "sha256"},
        "theme case contract",
    )
    case_payload = {key: case_contract[key] for key in case_contract if key != "sha256"}
    if (
        case_contract["galleryCases"] != list(_THEME_GALLERY_CASES)
        or case_contract["focusCases"] != list(_THEME_FOCUS_CASES)
        or case_contract["ownerCount"] != len(_THEME_SURFACES) * len(_THEME_GALLERY_CASES)
        or not _is_sha256(case_contract["sha256"])
        or hashlib.sha256(_canonical_json_bytes(case_payload)).hexdigest() != case_contract["sha256"]
    ):
        raise _error("theme case contract differs")
    if not _is_sha256(rich["selectorContractSha256"]) or not _is_sha256(rich["sourceDigest"]):
        raise _error("theme worker source or selector digest differs")
    _validate_theme_selector_evidence(
        rich["selectorEvidence"], viewport_name=viewport_identity["name"]
    )
    surfaces = rich["surfaces"]
    if not isinstance(surfaces, list) or len(surfaces) != len(_THEME_SURFACES):
        raise _error("theme worker surface set differs")
    prior_bottom = 0
    for (expected_name, expected_color, surface_rgb), raw_surface in zip(
        _THEME_SURFACES, surfaces
    ):
        surface = _require_mapping(raw_surface, f"theme surface {expected_name}")
        _require_exact_keys(
            surface,
            {"name", "color", "geometry", "states", "overflow"},
            f"theme surface {expected_name}",
        )
        if surface["name"] != expected_name or surface["color"] != expected_color:
            raise _error(f"theme surface identity differs: {expected_name}")
        geometry = _require_mapping(
            surface["geometry"], f"theme surface geometry {expected_name}"
        )
        _require_exact_keys(
            geometry,
            {
                "selector",
                "coordinateSpace",
                "deviceScaleFactor",
                "scrollOffset",
                "cssRect",
                "crop",
            },
            f"theme surface geometry {expected_name}",
        )
        scroll = _require_mapping(
            geometry["scrollOffset"], f"theme surface scroll {expected_name}"
        )
        rect = _require_mapping(
            geometry["cssRect"], f"theme surface rect {expected_name}"
        )
        crop = _require_mapping(
            geometry["crop"], f"theme surface crop {expected_name}"
        )
        _require_exact_keys(scroll, {"x", "y"}, f"theme surface scroll {expected_name}")
        _require_exact_keys(
            rect,
            {"left", "top", "right", "bottom", "width", "height"},
            f"theme surface rect {expected_name}",
        )
        _require_exact_keys(
            crop, {"x", "y", "width", "height"}, f"theme surface crop {expected_name}"
        )
        scroll_x = _theme_number(scroll["x"], label=f"theme scroll x {expected_name}")
        scroll_y = _theme_number(scroll["y"], label=f"theme scroll y {expected_name}")
        normalized_rect = {
            key: _theme_number(rect[key], label=f"theme rect {expected_name}.{key}")
            for key in rect
        }
        if (
            geometry["selector"] != f".st-key-ux1b_surface_{expected_name}"
            or geometry["coordinateSpace"] != "full-page-css-pixels"
            or geometry["deviceScaleFactor"] != 1
            or normalized_rect["width"] <= 0
            or normalized_rect["height"] <= 0
            or abs(normalized_rect["right"] - normalized_rect["left"] - normalized_rect["width"]) > 0.1
            or abs(normalized_rect["bottom"] - normalized_rect["top"] - normalized_rect["height"]) > 0.1
            or any(not _is_int(crop[key]) for key in crop)
        ):
            raise _error(f"theme surface geometry differs: {expected_name}")
        expected_box = (
            math.floor(normalized_rect["left"] + scroll_x),
            math.floor(normalized_rect["top"] + scroll_y),
            math.ceil(normalized_rect["right"] + scroll_x),
            math.ceil(normalized_rect["bottom"] + scroll_y),
        )
        actual_box = (
            crop["x"],
            crop["y"],
            crop["x"] + crop["width"],
            crop["y"] + crop["height"],
        )
        if (
            actual_box != expected_box
            or actual_box[0] < 0
            or actual_box[1] < prior_bottom
            or actual_box[2] > full_page["width"]
            or actual_box[3] > full_page["height"]
            or crop["width"] <= 0
            or crop["height"] <= 0
        ):
            raise _error(f"theme surface crop differs: {expected_name}")
        prior_bottom = actual_box[3]
        _validate_theme_surface_states(
            surface["states"], surface=expected_name, surface_rgb=surface_rgb
        )
        overflow = _require_mapping(
            surface["overflow"], f"theme overflow {expected_name}"
        )
        _require_exact_keys(
            overflow,
            {"surface", "document", "overflowOwners"},
            f"theme overflow {expected_name}",
        )
        if overflow["overflowOwners"] != []:
            raise _error(f"theme overflow owners differ: {expected_name}")
        surface_overflow = _require_mapping(
            overflow["surface"], f"theme surface overflow {expected_name}"
        )
        document_overflow = _require_mapping(
            overflow["document"], f"theme document overflow {expected_name}"
        )
        _require_exact_keys(
            surface_overflow,
            {"clientWidth", "scrollWidth", "left", "right", "backgroundColor"},
            f"theme surface overflow {expected_name}",
        )
        _require_exact_keys(
            document_overflow,
            {"clientWidth", "scrollWidth"},
            f"theme document overflow {expected_name}",
        )
        if (
            _theme_number(surface_overflow["scrollWidth"], label=f"theme surface scroll width {expected_name}")
            > _theme_number(surface_overflow["clientWidth"], label=f"theme surface client width {expected_name}") + 1.0
            or _theme_number(document_overflow["scrollWidth"], label=f"theme document scroll width {expected_name}")
            > _theme_number(document_overflow["clientWidth"], label=f"theme document client width {expected_name}") + 1.0
        ):
            raise _error(f"theme overflow differs: {expected_name}")
    return copy.deepcopy(dict(rich))


def _focused_number(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _error(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise _error(f"{label} must be a finite number")
    return result


def _focused_rect(value: object, *, label: str) -> dict[str, float]:
    rect = _require_mapping(value, label)
    _require_exact_keys(rect, {"x", "y", "width", "height"}, label)
    result = {
        key: _focused_number(rect[key], label=f"{label}.{key}")
        for key in ("x", "y", "width", "height")
    }
    if result["width"] < 0 or result["height"] < 0:
        raise _error(f"{label} has negative dimensions")
    return result


def _focused_rect_inside(
    inner: Mapping[str, float], outer: Mapping[str, float]
) -> bool:
    tolerance = 1.0
    return (
        inner["x"] >= outer["x"] - tolerance
        and inner["y"] >= outer["y"] - tolerance
        and inner["x"] + inner["width"]
        <= outer["x"] + outer["width"] + tolerance
        and inner["y"] + inner["height"]
        <= outer["y"] + outer["height"] + tolerance
    )


def _focused_geometry_decimal(value: float) -> Decimal:
    return Decimal(str(value))


def _focused_rects_overlap(
    first: Mapping[str, float],
    second: Mapping[str, float],
    *,
    tolerance: float,
) -> bool:
    first_x = _focused_geometry_decimal(first["x"])
    first_y = _focused_geometry_decimal(first["y"])
    first_right = first_x + _focused_geometry_decimal(first["width"])
    first_bottom = first_y + _focused_geometry_decimal(first["height"])
    second_x = _focused_geometry_decimal(second["x"])
    second_y = _focused_geometry_decimal(second["y"])
    second_right = second_x + _focused_geometry_decimal(second["width"])
    second_bottom = second_y + _focused_geometry_decimal(second["height"])
    allowed = _focused_geometry_decimal(tolerance)
    return (
        min(first_right, second_right) - max(first_x, second_x) > allowed
        and min(first_bottom, second_bottom) - max(first_y, second_y) > allowed
    )


def _validate_focused_control_layout(
    value: object,
    targets: Sequence[dict[str, Any]],
    *,
    viewport_width: int,
    viewport_height: int,
    target_overlap_tolerance: float,
    label: str,
) -> dict[str, Any]:
    layout = _require_mapping(value, label)
    _require_exact_keys(
        layout,
        {
            "rootRect",
            "viewportWidth",
            "viewportHeight",
            "targetOverlapTolerance",
            "documentClientWidth",
            "documentScrollWidth",
            "rootClientWidth",
            "rootScrollWidth",
            "rootClipping",
            "targetClipping",
            "targetOverlap",
            "documentHorizontalOverflow",
            "rootHorizontalOverflow",
        },
        label,
    )
    root = _focused_rect(layout["rootRect"], label=f"{label}.rootRect")
    observed_overlap_tolerance = _focused_number(
        layout["targetOverlapTolerance"],
        label=f"{label}.targetOverlapTolerance",
    )
    if observed_overlap_tolerance != target_overlap_tolerance:
        raise _error(f"{label} target overlap tolerance differs")
    integer_keys = (
        "viewportWidth",
        "viewportHeight",
        "documentClientWidth",
        "documentScrollWidth",
        "rootClientWidth",
        "rootScrollWidth",
    )
    if any(
        not _is_int(layout[key]) or int(layout[key]) < 0 for key in integer_keys
    ):
        raise _error(f"{label} dimensions are invalid")
    if (
        layout["viewportWidth"] != viewport_width
        or layout["viewportHeight"] != viewport_height
    ):
        raise _error(f"{label} viewport dimensions differ")
    if (
        layout["documentClientWidth"] <= 0
        or layout["rootClientWidth"] <= 0
        or layout["documentScrollWidth"] < layout["documentClientWidth"]
        or layout["rootScrollWidth"] < layout["rootClientWidth"]
    ):
        raise _error(f"{label} width relations are impossible")
    boolean_keys = (
        "rootClipping",
        "targetClipping",
        "targetOverlap",
        "documentHorizontalOverflow",
        "rootHorizontalOverflow",
    )
    if any(not isinstance(layout[key], bool) for key in boolean_keys):
        raise _error(f"{label} overflow flags are invalid")
    if any(layout[key] for key in boolean_keys):
        raise _error(f"{label} reports clipping, overlap, or overflow")
    if (
        layout["documentScrollWidth"] > layout["documentClientWidth"] + 1
        or layout["rootScrollWidth"] > layout["rootClientWidth"] + 1
        or root["x"] < -1.0
        or root["x"] + root["width"] > viewport_width + 1.0
        or root["y"] < -1.0
        or root["y"] + root["height"] > viewport_height + 1.0
    ):
        raise _error(f"{label} geometry contradicts its overflow flags")
    for target in targets:
        if (
            not _focused_rect_inside(target, root)
            or target["x"] < -1.0
            or target["x"] + target["width"] > viewport_width + 1.0
            or target["y"] < -1.0
            or target["y"] + target["height"] > viewport_height + 1.0
        ):
            raise _error(f"{label} target clips its root or viewport")
    if any(
        _focused_rects_overlap(
            target,
            other,
            tolerance=target_overlap_tolerance,
        )
        for index, target in enumerate(targets)
        for other in targets[index + 1 :]
    ):
        raise _error(f"{label} targets overlap")
    return {
        "rootRect": root,
        "targetOverlapTolerance": observed_overlap_tolerance,
        **{key: int(layout[key]) for key in integer_keys},
        **{key: bool(layout[key]) for key in boolean_keys},
    }


def _validate_focused_screenshot_binding(
    value: object,
    controls: Sequence[Mapping[str, Any]],
    *,
    expected_viewport: Mapping[str, Any],
) -> dict[str, Any]:
    binding = _require_mapping(value, "focused screenshot binding")
    _require_exact_keys(
        binding,
        {
            "schemaVersion",
            "mode",
            "viewport",
            "roots",
            "scrollEntries",
            "prePostExact",
        },
        "focused screenshot binding",
    )
    raw_viewport = _require_mapping(
        binding["viewport"],
        "focused screenshot binding viewport",
    )
    _require_exact_keys(
        raw_viewport,
        {"width", "height"},
        "focused screenshot binding viewport",
    )
    if any(
        not _is_int(raw_viewport[key]) or raw_viewport[key] <= 0
        for key in ("width", "height")
    ):
        raise _error("focused screenshot binding viewport is invalid")
    viewport = {
        "width": int(raw_viewport["width"]),
        "height": int(raw_viewport["height"]),
    }
    if (
        binding["schemaVersion"] != FOCUSED_SCREENSHOT_BINDING_SCHEMA
        or binding["mode"] != "viewport"
        or binding["prePostExact"] is not True
        or viewport
        != {
            "width": expected_viewport["width"],
            "height": expected_viewport["height"],
        }
    ):
        raise _error("focused screenshot binding identity differs")
    roots_value = binding["roots"]
    if not isinstance(roots_value, list) or len(roots_value) != len(controls):
        raise _error("focused screenshot binding root count differs")
    roots: list[dict[str, Any]] = []
    root_selectors: list[str] = []
    for index, (raw_root, control) in enumerate(
        zip(roots_value, controls, strict=True)
    ):
        root = _require_mapping(
            raw_root,
            f"focused screenshot binding roots[{index}]",
        )
        _require_exact_keys(
            root,
            {"rootSelector", "rect"},
            f"focused screenshot binding roots[{index}]",
        )
        selector = root["rootSelector"]
        rect = _focused_rect(
            root["rect"],
            label=f"focused screenshot binding roots[{index}].rect",
        )
        if (
            selector != control["rootSelector"]
            or rect != control["layout"]["rootRect"]
            or rect["x"] < -1
            or rect["y"] < -1
            or rect["x"] + rect["width"] > viewport["width"] + 1
            or rect["y"] + rect["height"] > viewport["height"] + 1
        ):
            raise _error("focused screenshot binding root geometry differs")
        root_selectors.append(selector)
        roots.append({"rootSelector": selector, "rect": rect})
    if len(root_selectors) != len(set(root_selectors)):
        raise _error("focused screenshot binding roots are duplicated")

    entries_value = binding["scrollEntries"]
    if not isinstance(entries_value, list) or not entries_value:
        raise _error("focused screenshot binding scroll entries are missing")
    entries: list[dict[str, Any]] = []
    next_chain_index = {selector: 0 for selector in root_selectors}
    for index, raw_entry in enumerate(entries_value):
        entry = _require_mapping(
            raw_entry,
            f"focused screenshot binding scrollEntries[{index}]",
        )
        _require_exact_keys(
            entry,
            {
                "rootSelector",
                "chainIndex",
                "left",
                "top",
                "clientWidth",
                "clientHeight",
                "scrollWidth",
                "scrollHeight",
            },
            f"focused screenshot binding scrollEntries[{index}]",
        )
        selector = entry["rootSelector"]
        chain_index = entry["chainIndex"]
        if (
            selector not in next_chain_index
            or not _is_int(chain_index)
            or chain_index != next_chain_index[selector]
        ):
            raise _error("focused screenshot binding scroll chain differs")
        numeric: dict[str, float] = {}
        for key in (
            "left",
            "top",
            "clientWidth",
            "clientHeight",
            "scrollWidth",
            "scrollHeight",
        ):
            numeric[key] = _focused_number(
                entry[key],
                label=f"focused screenshot binding scrollEntries[{index}].{key}",
            )
            if numeric[key] < 0:
                raise _error("focused screenshot binding scroll metric is negative")
        if (
            numeric["clientWidth"] <= 0
            or numeric["clientHeight"] <= 0
            or numeric["scrollWidth"] < numeric["clientWidth"]
            or numeric["scrollHeight"] < numeric["clientHeight"]
            or numeric["left"]
            > numeric["scrollWidth"] - numeric["clientWidth"] + 1
            or numeric["top"]
            > numeric["scrollHeight"] - numeric["clientHeight"] + 1
        ):
            raise _error("focused screenshot binding scroll relations differ")
        next_chain_index[selector] += 1
        entries.append(
            {
                "rootSelector": selector,
                "chainIndex": chain_index,
                **numeric,
            }
        )
    if any(index == 0 for index in next_chain_index.values()):
        raise _error("focused screenshot binding lacks a root scroll chain")
    return {
        "schemaVersion": FOCUSED_SCREENSHOT_BINDING_SCHEMA,
        "mode": "viewport",
        "viewport": viewport,
        "roots": roots,
        "scrollEntries": entries,
        "prePostExact": True,
    }


def _validate_focused_control_evidence(
    value: object,
    *,
    expected_case: str,
    expected_viewport: Mapping[str, Any],
    require_screenshot_binding: bool = False,
    expected_root_selector: str | None = None,
) -> dict[str, Any]:
    evidence = _require_mapping(value, "focused control evidence")
    schema_version = evidence.get("schemaVersion")
    evidence_keys = {"schemaVersion", "case", "projection", "controls"}
    if schema_version in {
        FOCUSED_CONTROL_EVIDENCE_V2_SCHEMA,
        FOCUSED_CONTROL_EVIDENCE_V3_SCHEMA,
    }:
        evidence_keys.add("screenshotBinding")
    _require_exact_keys(
        evidence,
        evidence_keys,
        "focused control evidence",
    )
    case_contracts = _FOCUSED_CONTROL_CONTRACTS.get(expected_case)
    if case_contracts is None:
        raise _error("non-focused render cannot contain focused control evidence")
    contracts = case_contracts
    if schema_version == FOCUSED_CONTROL_EVIDENCE_V3_SCHEMA:
        if (
            not isinstance(expected_root_selector, str)
            or not expected_root_selector
        ):
            raise _error("root-only focused evidence lacks an expected selector")
        contracts = tuple(
            contract
            for contract in case_contracts
            if contract["rootSelector"] == expected_root_selector
        )
        if len(contracts) != 1:
            raise _error("root-only focused selector is not in the frozen catalog")
    elif expected_root_selector is not None:
        raise _error("case-level focused evidence cannot bind one root selector")
    projection = evidence["projection"]
    if (
        schema_version
        not in {
            FOCUSED_CONTROL_EVIDENCE_SCHEMA,
            FOCUSED_CONTROL_EVIDENCE_V2_SCHEMA,
            FOCUSED_CONTROL_EVIDENCE_V3_SCHEMA,
        }
        or evidence["case"] != expected_case
        or projection not in {"legacy-segmented", "accessible-required"}
    ):
        raise _error("focused control evidence identity differs")
    if (
        require_screenshot_binding
        and schema_version
        not in {
            FOCUSED_CONTROL_EVIDENCE_V2_SCHEMA,
            FOCUSED_CONTROL_EVIDENCE_V3_SCHEMA,
        }
    ):
        raise _error("corrected focused evidence lacks screenshot binding")
    controls = evidence["controls"]
    if not isinstance(controls, list) or len(controls) != len(contracts):
        raise _error("focused control evidence count differs")
    required = {
        "sessionKey",
        "rootSelector",
        "widget",
        "role",
        "accessibleName",
        "optionRole",
        "optionLabels",
        "auxiliaryButtons",
        "selectedLabel",
        "checkedLabels",
        "tabSequenceLabels",
        "afterArrowRight",
        "afterArrowLeft",
        "afterSpace",
        "afterArrowDown",
        "afterArrowUp",
        "targets",
        "layout",
        "selectionBasis",
    }
    canonical_controls: list[dict[str, Any]] = []
    for index, (raw_control, contract) in enumerate(zip(controls, contracts, strict=True)):
        label = f"focused control evidence controls[{index}]"
        control = _require_mapping(raw_control, label)
        _require_exact_keys(control, required, label)
        options = list(contract["optionLabels"])
        selected = contract["selectedLabel"]
        if (
            control["sessionKey"] != contract["sessionKey"]
            or control["rootSelector"] != contract["rootSelector"]
            or control["accessibleName"] != contract["accessibleName"]
            or control["optionLabels"] != options
            or control["auxiliaryButtons"]
            != list(contract["auxiliaryButtons"])
            or control["selectedLabel"] != selected
        ):
            raise _error(f"{label} differs from its frozen selector contract")
        target_values = control["targets"]
        expected_target_labels = (
            [selected]
            if projection == "accessible-required"
            and contract["replacementWidget"] == "selectbox"
            else options
        )
        if (
            not isinstance(target_values, list)
            or len(target_values) != len(expected_target_labels)
        ):
            raise _error(f"{label} target count differs")
        targets: list[dict[str, Any]] = []
        for target_index, (raw_target, target_label) in enumerate(
            zip(target_values, expected_target_labels, strict=True)
        ):
            target_name = f"{label}.targets[{target_index}]"
            target = _require_mapping(raw_target, target_name)
            _require_exact_keys(
                target, {"label", "x", "y", "width", "height"}, target_name
            )
            if target["label"] != target_label:
                raise _error(f"{target_name} label differs")
            rect = _focused_rect(
                {key: target[key] for key in ("x", "y", "width", "height")},
                label=target_name,
            )
            targets.append({"label": target_label, **rect})
        layout = _validate_focused_control_layout(
            control["layout"],
            targets,
            viewport_width=int(expected_viewport["width"]),
            viewport_height=int(expected_viewport["height"]),
            target_overlap_tolerance=(
                1.0 if projection == "legacy-segmented" else 0.5
            ),
            label=f"{label}.layout",
        )
        if projection == "legacy-segmented":
            expected_semantics = {
                "widget": "segmented_control",
                "role": "group",
                "optionRole": "button",
                "checkedLabels": [selected],
                "tabSequenceLabels": [],
                "afterArrowRight": None,
                "afterArrowLeft": None,
                "afterSpace": None,
                "afterArrowDown": None,
                "afterArrowUp": None,
                "selectionBasis": "segmented-buttons/one-active",
            }
        elif contract["replacementWidget"] == "radio_horizontal":
            selected_index = options.index(selected)
            expected_semantics = {
                "widget": "radio_horizontal",
                "role": "radiogroup",
                "optionRole": "radio",
                "checkedLabels": [selected],
                "tabSequenceLabels": [selected],
                "afterArrowRight": options[(selected_index + 1) % len(options)],
                "afterArrowLeft": selected,
                "afterSpace": selected,
                "afterArrowDown": None,
                "afterArrowUp": None,
                "selectionBasis": "native-radio/one-checked/roving-tabstop/keyboard",
            }
        else:
            expected_semantics = {
                "widget": "selectbox",
                "role": "combobox",
                "optionRole": "option",
                "checkedLabels": [],
                "tabSequenceLabels": [],
                "afterArrowRight": None,
                "afterArrowLeft": None,
                "afterSpace": None,
                "afterArrowDown": options[1],
                "afterArrowUp": selected,
                "selectionBasis": "combobox/exact-option-order/keyboard/restore",
            }
        if any(control[key] != expected for key, expected in expected_semantics.items()):
            raise _error(f"{label} semantic result differs")
        if projection == "accessible-required" and any(
            target["width"] < 24.0 or target["height"] < 24.0
            for target in targets
        ):
            raise _error(f"{label} target is smaller than 24 by 24")
        canonical_controls.append(
            {
                key: copy.deepcopy(control[key])
                for key in required
                if key not in {"targets", "layout"}
            }
            | {"targets": targets, "layout": layout}
        )
    canonical = {
        "schemaVersion": schema_version,
        "case": expected_case,
        "projection": projection,
        "controls": canonical_controls,
    }
    if schema_version in {
        FOCUSED_CONTROL_EVIDENCE_V2_SCHEMA,
        FOCUSED_CONTROL_EVIDENCE_V3_SCHEMA,
    }:
        canonical["screenshotBinding"] = (
            _validate_focused_screenshot_binding(
                evidence["screenshotBinding"],
                canonical_controls,
                expected_viewport=expected_viewport,
            )
        )
    return canonical


def _validate_focused_screenshot_binding_nodes(
    control_evidence: Mapping[str, Any],
    nodes: Sequence[Mapping[str, Any]],
) -> None:
    if (
        control_evidence.get("schemaVersion")
        not in {
            FOCUSED_CONTROL_EVIDENCE_V2_SCHEMA,
            FOCUSED_CONTROL_EVIDENCE_V3_SCHEMA,
        }
    ):
        return
    binding = _require_mapping(
        control_evidence.get("screenshotBinding"),
        "focused screenshot binding",
    )
    roots = binding.get("roots")
    if not isinstance(roots, list):
        raise _error("focused screenshot binding roots are malformed")
    for root in roots:
        selector = root["rootSelector"]
        matches = [
            node
            for node in nodes
            if node.get("rootSelector") == selector
        ]
        if (
            len(matches) != 1
            or matches[0].get("visible") is not True
            or matches[0].get("bounds") != root["rect"]
        ):
            raise _error(
                "focused screenshot binding differs from its projected root"
            )


def _canonicalize_render_v2_sidecar(
    value: Mapping[str, Any],
    *,
    owned_roots: Sequence[str],
) -> bytes:
    """Canonicalize one closed root-capture render sidecar."""

    _require_exact_keys(
        value,
        {
            "schemaVersion",
            "identity",
            "viewport",
            "readiness",
            "nodes",
            "stableState",
            "providerCounters",
            "mutatorCounters",
            "runtimeProjection",
            "counterProvenance",
            "rootCapture",
            "controlEvidence",
            "caseSemanticProjection",
        },
        "root render sidecar",
    )
    if value["schemaVersion"] != RENDER_V2_SCHEMA:
        raise _error("root render sidecar schema is unsupported")

    root_capture = _require_mapping(
        value["rootCapture"], "root render capture identity"
    )
    _require_exact_keys(
        root_capture,
        {
            "logicalCaptureId",
            "rootCaptureId",
            "rootOrdinal",
            "rootSelector",
            "rootExpansionSha256",
        },
        "root render capture identity",
    )
    logical_capture_id = root_capture["logicalCaptureId"]
    if (
        not isinstance(logical_capture_id, str)
        or root_capture["rootExpansionSha256"]
        != ROOT_CAPTURE_EXPANSION_SHA256
    ):
        raise _error("root render capture expansion identity differs")
    expected_rows = _root_capture_rows_for_logical(logical_capture_id)
    matching_rows = tuple(
        row
        for row in expected_rows
        if row["rootCaptureId"] == root_capture["rootCaptureId"]
    )
    if len(matching_rows) != 1:
        raise _error("root render capture ID is not in the frozen expansion")
    expected_row = matching_rows[0]
    for key in ("logicalCaptureId", "rootCaptureId", "rootOrdinal", "rootSelector"):
        if root_capture[key] != expected_row[key]:
            raise _error(f"root render capture {key} differs")

    base_document: dict[str, Any] = {
        "schemaVersion": RENDER_SCHEMA,
        "identity": value["identity"],
        "viewport": value["viewport"],
        "readiness": value["readiness"],
        "nodes": value["nodes"],
        "stableState": value["stableState"],
        "providerCounters": value["providerCounters"],
        "mutatorCounters": value["mutatorCounters"],
        "runtimeProjection": value["runtimeProjection"],
    }
    if value["counterProvenance"] is not None:
        base_document["counterProvenance"] = value["counterProvenance"]
    normalized_base = _decode_json_bytes(
        canonicalize_render_sidecar(base_document, owned_roots=owned_roots),
        maximum=MAX_RENDER_SIDECAR_BYTES,
        label="root render base",
    )
    identity = _require_mapping(normalized_base["identity"], "root render identity")
    if (
        identity
        != {
            "case": expected_row["case"],
            "route": expected_row["route"],
            "callable": expected_row["callable"],
        }
        or normalized_base["viewport"] != expected_row["viewport"]
    ):
        raise _error("root render identity differs from the frozen expansion")
    focused = _validate_focused_control_evidence(
        value["controlEvidence"],
        expected_case=expected_row["case"],
        expected_viewport=expected_row["viewport"],
        require_screenshot_binding=True,
        expected_root_selector=expected_row["rootSelector"],
    )
    _validate_focused_screenshot_binding_nodes(
        focused,
        normalized_base["nodes"],
    )

    semantic = _require_mapping(
        value["caseSemanticProjection"],
        "case semantic projection",
    )
    _require_exact_keys(
        semantic,
        {
            "schemaVersion",
            "identity",
            "readiness",
            "nodes",
            "stableState",
            "providerCounters",
            "mutatorCounters",
            "runtimeProjection",
            "counterProvenance",
            "controlEvidence",
        },
        "case semantic projection",
    )
    semantic_identity = _require_mapping(
        semantic["identity"], "case semantic projection identity"
    )
    _require_exact_keys(
        semantic_identity,
        {
            "fixtureEntrypoint",
            "logicalCaptureId",
            "case",
            "route",
            "callable",
            "viewport",
        },
        "case semantic projection identity",
    )
    expected_semantic_identity = {
        "fixtureEntrypoint": expected_row["fixtureEntrypoint"],
        "logicalCaptureId": expected_row["logicalCaptureId"],
        "case": expected_row["case"],
        "route": expected_row["route"],
        "callable": expected_row["callable"],
        "viewport": expected_row["viewport"],
    }
    if (
        semantic["schemaVersion"] != CASE_SEMANTIC_PROJECTION_SCHEMA
        or dict(semantic_identity) != expected_semantic_identity
    ):
        raise _error("case semantic projection identity differs")
    semantic_document: dict[str, Any] = {
        "schemaVersion": RENDER_SCHEMA,
        "identity": {
            "case": expected_row["case"],
            "route": expected_row["route"],
            "callable": expected_row["callable"],
        },
        "viewport": expected_row["viewport"],
        "readiness": semantic["readiness"],
        "nodes": semantic["nodes"],
        "stableState": semantic["stableState"],
        "providerCounters": semantic["providerCounters"],
        "mutatorCounters": semantic["mutatorCounters"],
        "runtimeProjection": semantic["runtimeProjection"],
        "controlEvidence": semantic["controlEvidence"],
    }
    if semantic["counterProvenance"] is not None:
        semantic_document["counterProvenance"] = semantic["counterProvenance"]
    normalized_semantic_base = _decode_json_bytes(
        canonicalize_render_sidecar(
            semantic_document,
            owned_roots=owned_roots,
        ),
        maximum=MAX_RENDER_SIDECAR_BYTES,
        label="case semantic projection base",
    )
    if (
        normalized_semantic_base["controlEvidence"].get("schemaVersion")
        != FOCUSED_CONTROL_EVIDENCE_SCHEMA
    ):
        raise _error("case semantic projection must retain case-level v1 evidence")
    for key in (
        "providerCounters",
        "mutatorCounters",
    ):
        if normalized_semantic_base[key] != normalized_base[key]:
            raise _error("root and case-semantic counters differ")
    if normalized_semantic_base.get("counterProvenance") != normalized_base.get(
        "counterProvenance"
    ):
        raise _error("root and case-semantic counter provenance differs")

    canonical_semantic = {
        "schemaVersion": CASE_SEMANTIC_PROJECTION_SCHEMA,
        "identity": copy.deepcopy(expected_semantic_identity),
        "readiness": normalized_semantic_base["readiness"],
        "nodes": normalized_semantic_base["nodes"],
        "stableState": normalized_semantic_base["stableState"],
        "providerCounters": normalized_semantic_base["providerCounters"],
        "mutatorCounters": normalized_semantic_base["mutatorCounters"],
        "runtimeProjection": normalized_semantic_base["runtimeProjection"],
        "counterProvenance": normalized_semantic_base.get("counterProvenance"),
        "controlEvidence": normalized_semantic_base["controlEvidence"],
    }
    canonical = {
        "schemaVersion": RENDER_V2_SCHEMA,
        "identity": normalized_base["identity"],
        "viewport": normalized_base["viewport"],
        "readiness": normalized_base["readiness"],
        "nodes": normalized_base["nodes"],
        "stableState": normalized_base["stableState"],
        "providerCounters": normalized_base["providerCounters"],
        "mutatorCounters": normalized_base["mutatorCounters"],
        "runtimeProjection": normalized_base["runtimeProjection"],
        "counterProvenance": normalized_base.get("counterProvenance"),
        "rootCapture": copy.deepcopy(dict(root_capture)),
        "controlEvidence": focused,
        "caseSemanticProjection": canonical_semantic,
    }
    raw = _canonical_json_bytes(canonical)
    if len(raw) > MAX_RENDER_SIDECAR_BYTES:
        raise _error("canonical root render sidecar exceeds its byte bound")
    return raw


def canonicalize_render_sidecar(
    document: Mapping[str, object],
    *,
    owned_roots: Sequence[str],
) -> bytes:
    """Project a render observation into deterministic, non-color JSON."""

    value = _require_mapping(document, "render sidecar")
    if value.get("schemaVersion") == RENDER_V2_SCHEMA:
        return _canonicalize_render_v2_sidecar(
            value,
            owned_roots=owned_roots,
        )
    required = {
        "schemaVersion",
        "identity",
        "viewport",
        "readiness",
        "nodes",
        "stableState",
        "providerCounters",
        "mutatorCounters",
        "runtimeProjection",
    }
    optional_volatile = {"capturedAt", "runId"}
    optional_semantic = {"counterProvenance", "controlEvidence"}
    if not required.issubset(value) or not set(value).issubset(
        required | optional_volatile | optional_semantic
    ):
        _require_exact_keys(
            value,
            required
            | (set(value) & optional_volatile)
            | (set(value) & optional_semantic),
            "render sidecar",
        )
    if value["schemaVersion"] != RENDER_SCHEMA:
        raise _error("render sidecar schema is unsupported")
    identity = _require_mapping(value["identity"], "render identity")
    _require_exact_keys(identity, {"case", "route", "callable"}, "render identity")
    if any(not isinstance(identity[key], str) or not identity[key] for key in identity):
        raise _error("render identity fields must be non-empty strings")
    viewport = _validate_viewport(value["viewport"], label="render viewport")
    readiness = _require_mapping(value["readiness"], "render readiness")
    _require_exact_keys(readiness, {"ready", "marker"}, "render readiness")
    if readiness["ready"] is not True or not isinstance(readiness["marker"], str):
        raise _error("render readiness is not a ready marker")
    stable_state = _require_mapping(value["stableState"], "render stableState")
    _validate_json_tree(stable_state, label="render stableState")
    provider = _validate_counters(value["providerCounters"], label="providerCounters")
    mutator = _validate_counters(value["mutatorCounters"], label="mutatorCounters")
    counter_provenance: dict[str, Any] | None = None
    if "counterProvenance" in value:
        provenance = _require_mapping(
            value["counterProvenance"], "counterProvenance"
        )
        _require_exact_keys(
            provenance,
            {
                "schemaVersion",
                "counterDocumentSha256",
                "captureId",
                "registryKey",
            },
            "counterProvenance",
        )
        if (
            provenance["schemaVersion"]
            != "quant-radar-ui-ux-counter-enrichment/v1"
            or not _is_sha256(provenance["counterDocumentSha256"])
            or not isinstance(provenance["captureId"], str)
            or not provenance["captureId"]
            or not isinstance(provenance["registryKey"], str)
            or not provenance["registryKey"]
        ):
            raise _error("counterProvenance is invalid")
        counter_provenance = dict(provenance)
    control_evidence: dict[str, Any] | None = None
    if "controlEvidence" in value:
        control_evidence = _validate_focused_control_evidence(
            value["controlEvidence"],
            expected_case=identity["case"],
            expected_viewport=viewport,
        )

    normalized_roots: list[str] = []
    for root in owned_roots:
        if not isinstance(root, str) or not os.path.isabs(root):
            raise _error("owned root must be an absolute path")
        normalized = os.path.normpath(root)
        if normalized == "/":
            raise _error("filesystem root cannot be an owned evidence root")
        normalized_roots.append(normalized)
    if len(set(normalized_roots)) != len(normalized_roots):
        raise _error("owned evidence roots must be distinct")
    for index, root in enumerate(normalized_roots):
        for other in normalized_roots[index + 1 :]:
            if os.path.commonpath((root, other)) in {root, other}:
                raise _error("owned evidence roots must not overlap")
    rooted_roles = tuple(
        (root, f"$OWNED_ROOT_{index}")
        for index, root in enumerate(normalized_roots)
    )
    runtime = _require_mapping(value["runtimeProjection"], "runtimeProjection")
    normalized_runtime: dict[str, str] = {}
    for key, item in runtime.items():
        if not key or not isinstance(item, str):
            raise _error("runtimeProjection entries must be path strings")
        normalized_runtime[key] = _normalize_owned_path(item, rooted_roles)

    nodes_value = value["nodes"]
    if not isinstance(nodes_value, list):
        raise _error("render nodes must be a list")
    canonical_nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    required_node = {
        "id",
        "parentId",
        "flowScope",
        "boundaryId",
        "rootSelector",
        "role",
        "name",
        "text",
        "state",
        "visible",
        "bounds",
    }
    for index, raw_node in enumerate(nodes_value):
        node = _require_mapping(raw_node, f"render node {index}")
        observed_keys = set(node)
        if observed_keys not in (required_node, required_node | {"browserNodeId"}):
            raise _error(f"render node {index} keys differ")
        for key in ("id", "flowScope", "role", "name", "text"):
            if not isinstance(node[key], str) or (key in {"id", "flowScope", "role"} and not node[key]):
                raise _error(f"render node {index}.{key} is invalid")
        if node["id"] in node_ids:
            raise _error("render node IDs must be unique")
        node_ids.add(node["id"])
        for key in ("parentId", "boundaryId", "rootSelector"):
            if node[key] is not None and not isinstance(node[key], str):
                raise _error(f"render node {index}.{key} is invalid")
        if not isinstance(node["visible"], bool):
            raise _error(f"render node {index}.visible is invalid")
        if "browserNodeId" in node and (
            not isinstance(node["browserNodeId"], str) or not node["browserNodeId"]
        ):
            raise _error(f"render node {index}.browserNodeId is invalid")
        state_value = _require_mapping(node["state"], f"render node {index}.state")
        _validate_json_tree(state_value, label=f"render node {index}.state")
        bounds = _require_mapping(node["bounds"], f"render node {index}.bounds")
        _require_exact_keys(bounds, {"x", "y", "width", "height"}, f"render node {index}.bounds")
        for key in ("x", "y", "width", "height"):
            if not _is_int(bounds[key]):
                raise _error(f"render node {index}.bounds.{key} must be an integer")
        if bounds["width"] < 0 or bounds["height"] < 0:
            raise _error("render node dimensions cannot be negative")
        canonical_nodes.append(
            {
                key: copy.deepcopy(node[key])
                for key in required_node
            }
        )
    for node in canonical_nodes:
        if node["parentId"] is not None and node["parentId"] not in node_ids:
            raise _error("render node parentId is not present")
        if node["boundaryId"] is not None and node["boundaryId"] not in node_ids:
            raise _error("render node boundaryId is not present")
    if control_evidence is not None:
        _validate_focused_screenshot_binding_nodes(
            control_evidence,
            canonical_nodes,
        )

    canonical = {
        "schemaVersion": RENDER_SCHEMA,
        "identity": dict(identity),
        "viewport": viewport,
        "readiness": dict(readiness),
        "nodes": canonical_nodes,
        "stableState": copy.deepcopy(dict(stable_state)),
        "providerCounters": provider,
        "mutatorCounters": mutator,
        "runtimeProjection": normalized_runtime,
    }
    if counter_provenance is not None:
        canonical["counterProvenance"] = counter_provenance
    if control_evidence is not None:
        canonical["controlEvidence"] = control_evidence
    raw = _canonical_json_bytes(canonical)
    if len(raw) > MAX_RENDER_SIDECAR_BYTES:
        raise _error("canonical render sidecar exceeds its byte bound")
    return raw


def canonicalize_worker_render_sidecar(
    document: Mapping[str, object],
    *,
    owned_roots: Sequence[str],
) -> bytes:
    """Canonicalize a browser-staged sidecar with no trusted counters."""

    value = _require_mapping(document, "worker render sidecar")
    if value.get("providerCounters") != {} or value.get("mutatorCounters") != {}:
        raise _error("worker render sidecar counters must be exactly empty")
    if value.get("schemaVersion") == RENDER_V2_SCHEMA:
        semantic = _require_mapping(
            value.get("caseSemanticProjection"),
            "worker case semantic projection",
        )
        if (
            value.get("counterProvenance") is not None
            or semantic.get("providerCounters") != {}
            or semantic.get("mutatorCounters") != {}
            or semantic.get("counterProvenance") is not None
        ):
            raise _error(
                "worker root render sidecar cannot claim counter enrichment"
            )
    elif "counterProvenance" in value:
        raise _error("worker render sidecar cannot claim coordinator enrichment")
    return canonicalize_render_sidecar(value, owned_roots=owned_roots)


MAX_COUNTER_DOCUMENT_BYTES = 8 * 1024 * 1024
COUNTER_DOCUMENT_SCHEMA = 1
COUNTER_DOCUMENT_REVISION = "quant-radar-ux1b-2026-07-16.1"
COUNTER_CONTRACT_SCHEMA = 1


class AuthenticatedCounterBundle(Mapping[str, Any]):
    """Opaque result of descriptor-authenticated matrix counter validation."""

    __slots__ = ("_data",)

    def __init__(self, data: Mapping[str, Any], *, _key: object) -> None:
        if _key is not _OPAQUE_KEY:
            raise _error("counter attestations are minted internally")
        self._data = MappingProxyType(copy.deepcopy(dict(data)))

    def __getitem__(self, key: str) -> Any:
        return copy.deepcopy(self._data[key])

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __copy__(self) -> AuthenticatedCounterBundle:
        raise TypeError("authenticated counter bundles cannot be copied")

    def __deepcopy__(self, _memo: object) -> AuthenticatedCounterBundle:
        raise TypeError("authenticated counter bundles cannot be copied")


class AuthenticatedRawRenderSidecar(Mapping[str, Any]):
    """Opaque descriptor-authenticated browser-staged render sidecar."""

    __slots__ = ("_data",)

    def __init__(self, data: Mapping[str, Any], *, _key: object) -> None:
        if _key is not _OPAQUE_KEY:
            raise _error("raw render attestations are minted internally")
        self._data = MappingProxyType(copy.deepcopy(dict(data)))

    def __getitem__(self, key: str) -> Any:
        return copy.deepcopy(self._data[key])

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __copy__(self) -> AuthenticatedRawRenderSidecar:
        raise TypeError("authenticated raw sidecars cannot be copied")

    def __deepcopy__(self, _memo: object) -> AuthenticatedRawRenderSidecar:
        raise TypeError("authenticated raw sidecars cannot be copied")


# Transitional compatibility name.  Grants minted by the legacy single-row
# helper are explicitly barred from final-sidecar authorization below.
AuthenticatedCounterDocument = AuthenticatedCounterBundle


_AUTHENTICATED_COUNTERS: dict[
    int, tuple[AuthenticatedCounterBundle, dict[str, Any]]
] = {}
_AUTHENTICATED_COUNTERS_LOCK = threading.Lock()
_AUTHENTICATED_RAW_SIDECARS: dict[
    int, tuple[AuthenticatedRawRenderSidecar, dict[str, Any]]
] = {}
_AUTHENTICATED_RAW_SIDECARS_LOCK = threading.Lock()
_FINALIZED_RENDER_SIDECARS: dict[str, bytes] = {}
_FINALIZED_RENDER_SIDECARS_LOCK = threading.Lock()


def _exact_worker_identity_row(value: object) -> dict[str, Any]:
    row = _require_mapping(value, "worker identity row")
    _require_exact_keys(
        row,
        {
            "fixtureEntrypoint",
            "case",
            "route",
            "viewport",
            "registryKey",
            "callable",
            "rootSelectors",
            "affectedRootSelectors",
            "readiness",
        },
        "worker identity row",
    )
    viewport = _validate_viewport(row["viewport"], label="worker identity viewport")
    key = (
        row["fixtureEntrypoint"],
        row["case"],
        row["route"],
        viewport["name"],
        viewport["width"],
        viewport["height"],
    )
    frozen = _WORKER_IDENTITY_ROWS.get(key)
    if frozen is None or dict(row) != frozen:
        raise _error("worker identity row differs from the frozen catalog")
    return copy.deepcopy(frozen)


def _registered_counter_payload(value: object) -> dict[str, Any]:
    if not isinstance(value, AuthenticatedCounterBundle):
        raise _error("counter bundle is not authenticated")
    with _AUTHENTICATED_COUNTERS_LOCK:
        registered = _AUTHENTICATED_COUNTERS.get(id(value))
    if registered is None or registered[0] is not value:
        raise _error("counter bundle lacks live provenance")
    return copy.deepcopy(registered[1])


def _registered_raw_sidecar_payload(value: object) -> dict[str, Any]:
    if not isinstance(value, AuthenticatedRawRenderSidecar):
        raise _error("raw render sidecar is not descriptor-authenticated")
    with _AUTHENTICATED_RAW_SIDECARS_LOCK:
        registered = _AUTHENTICATED_RAW_SIDECARS.get(id(value))
    if registered is None or registered[0] is not value:
        raise _error("raw render sidecar lacks live descriptor provenance")
    return copy.deepcopy(registered[1])


def authenticate_counter_document(
    app_root_fd: int,
    relative_path: str,
    *,
    expected_owner: int,
    expected_capture_id: str,
    identity_row: Mapping[str, object],
    expected_positive_counters: Mapping[str, int],
    expected_zero_counters: Sequence[str],
    expected_owned_paths: Mapping[str, str],
) -> AuthenticatedCounterDocument:
    """Authenticate the app-owned counter file and its exact capture bucket."""

    if not isinstance(expected_capture_id, str) or not expected_capture_id:
        raise _error("expected counter capture ID is invalid")
    frozen_identity = _exact_worker_identity_row(identity_row)
    positives = _validate_counters(
        expected_positive_counters, label="expected positive counters"
    )
    if not positives or any(value <= 0 for value in positives.values()):
        raise _error("expected positive counters must be explicitly positive")
    zero_names = tuple(expected_zero_counters)
    if (
        not zero_names
        or any(not isinstance(name, str) or not name for name in zero_names)
        or len(set(zero_names)) != len(zero_names)
        or set(zero_names) & set(positives)
    ):
        raise _error("expected zero counters are invalid")
    owned_paths = _require_mapping(expected_owned_paths, "expected owned paths")
    if not owned_paths or any(
        not key
        or not isinstance(path, str)
        or not os.path.isabs(path)
        for key, path in owned_paths.items()
    ):
        raise _error("expected owned paths are invalid")
    contract = freeze_artifact_contract(
        app_root_fd,
        relative_path,
        expected_owner=expected_owner,
        max_bytes=MAX_COUNTER_DOCUMENT_BYTES,
    )
    with open_authenticated_artifact(app_root_fd, contract) as artifact:
        raw, document_sha256, _observed = _hash_descriptor(
            artifact.descriptor, maximum=MAX_COUNTER_DOCUMENT_BYTES
        )
    document = _require_mapping(
        _decode_json_bytes(
            raw, maximum=MAX_COUNTER_DOCUMENT_BYTES, label="fixture counter document"
        ),
        "fixture counter document",
    )
    _require_exact_keys(
        document,
        {
            "schemaVersion",
            "fixtureRevision",
            "contractSchema",
            "captures",
            "bootstrapBlockedNetwork",
        },
        "fixture counter document",
    )
    if (
        document["schemaVersion"] != COUNTER_DOCUMENT_SCHEMA
        or document["fixtureRevision"] != COUNTER_DOCUMENT_REVISION
        or document["contractSchema"] != COUNTER_CONTRACT_SCHEMA
        or document["bootstrapBlockedNetwork"] != []
    ):
        raise _error("fixture counter schema, revision, or bootstrap network record differs")
    captures = _require_mapping(document["captures"], "fixture counter captures")
    if set(captures) != {expected_capture_id}:
        raise _error("fixture counter capture ID set differs")
    bucket = _require_mapping(
        captures[expected_capture_id], "fixture counter capture bucket"
    )
    _require_exact_keys(
        bucket, {"counts", "blockedNetwork", "identity"}, "fixture counter capture bucket"
    )
    if bucket["blockedNetwork"] != []:
        raise _error("fixture counter capture recorded blocked network")
    counts = _validate_counters(bucket["counts"], label="fixture counters")
    declared = set(positives) | set(zero_names)
    if (
        any(counts.get(name) != count for name, count in positives.items())
        or any(counts.get(name, 0) != 0 for name in zero_names)
        or set(counts) - declared
    ):
        raise _error("fixture counters differ from their exact declared contract")
    counts = {**positives, **{name: 0 for name in zero_names}}
    identity = _require_mapping(bucket["identity"], "fixture counter identity")
    _require_exact_keys(
        identity,
        {"selectedRegistryKey", "realCallable", "resolvedOwnedPaths"},
        "fixture counter identity",
    )
    resolved = _require_mapping(
        identity["resolvedOwnedPaths"], "fixture resolved owned paths"
    )
    if (
        identity["selectedRegistryKey"] != frozen_identity["registryKey"]
        or identity["realCallable"] != frozen_identity["callable"]
        or dict(resolved) != dict(owned_paths)
    ):
        raise _error("fixture counter route, callable, or owned paths differ")
    provider_counters = {
        name: count for name, count in counts.items() if not name.startswith("mutator.")
    }
    mutator_counters = {
        name: count for name, count in counts.items() if name.startswith("mutator.")
    }
    if any(mutator_counters.values()):
        raise _error("fixture counter document records a mutator operation")
    payload = {
        "completeMatrix": False,
        "captureId": expected_capture_id,
        "identityRow": frozen_identity,
        "providerCounters": provider_counters,
        "mutatorCounters": mutator_counters,
        "counterDocumentSha256": document_sha256,
        "counterDocumentSize": len(raw),
    }
    authenticated = AuthenticatedCounterDocument(payload, _key=_OPAQUE_KEY)
    with _AUTHENTICATED_COUNTERS_LOCK:
        _AUTHENTICATED_COUNTERS[id(authenticated)] = (
            authenticated,
            copy.deepcopy(payload),
        )
    return authenticated


def _expected_counter_capture_contract(
    capture_id: str, value: object
) -> dict[str, Any]:
    if not isinstance(capture_id, str) or not capture_id:
        raise _error("expected counter capture ID is invalid")
    contract = _require_mapping(value, f"expected counter capture {capture_id}")
    _require_exact_keys(
        contract,
        {"identityRow", "positiveCounters", "zeroCounters", "ownedPaths"},
        f"expected counter capture {capture_id}",
    )
    identity = _exact_worker_identity_row(contract["identityRow"])
    if capture_id != f'{identity["case"]}/{identity["viewport"]["name"]}':
        raise _error("counter capture ID differs from its frozen identity row")
    positives = _validate_counters(
        contract["positiveCounters"],
        label=f"expected positive counters {capture_id}",
    )
    if not positives or any(count <= 0 for count in positives.values()):
        raise _error("expected positive counters must be explicitly positive")
    raw_zero = contract["zeroCounters"]
    if not isinstance(raw_zero, (list, tuple, set, frozenset)):
        raise _error("expected zero counters must be a finite sequence")
    zero_names = tuple(raw_zero)
    if (
        not zero_names
        or any(not isinstance(name, str) or not name for name in zero_names)
        or len(set(zero_names)) != len(zero_names)
        or set(zero_names) & set(positives)
    ):
        raise _error("expected zero counters are invalid")
    owned_paths = _require_mapping(
        contract["ownedPaths"], f"expected owned paths {capture_id}"
    )
    if not owned_paths or any(
        not key or not isinstance(path, str) or not os.path.isabs(path)
        for key, path in owned_paths.items()
    ):
        raise _error("expected owned paths are invalid")
    return {
        "identityRow": identity,
        "positiveCounters": positives,
        "zeroCounters": tuple(sorted(zero_names)),
        "ownedPaths": dict(owned_paths),
    }


def authenticate_counter_bundle(
    app_root_fd: int,
    relative_path: str,
    *,
    expected_owner: int,
    expected_captures: Mapping[str, Mapping[str, object]],
) -> AuthenticatedCounterBundle:
    """Authenticate one cumulative counter document for the exact matrix."""

    expected_value = _require_mapping(expected_captures, "expected counter captures")
    if not expected_value:
        raise _error("expected counter capture matrix cannot be empty")
    expected = {
        capture_id: _expected_counter_capture_contract(capture_id, row)
        for capture_id, row in expected_value.items()
    }
    entrypoints = {
        row["identityRow"]["fixtureEntrypoint"] for row in expected.values()
    }
    profile = next(iter(entrypoints)) if len(entrypoints) == 1 else None
    complete_matrix = (
        profile is not None
        and set(expected) == set(_COUNTER_PROFILE_CAPTURE_IDS[profile])
    )
    contract = freeze_artifact_contract(
        app_root_fd,
        relative_path,
        expected_owner=expected_owner,
        max_bytes=MAX_COUNTER_DOCUMENT_BYTES,
    )
    with open_authenticated_artifact(app_root_fd, contract) as artifact:
        raw, document_sha256, _observed = _hash_descriptor(
            artifact.descriptor, maximum=MAX_COUNTER_DOCUMENT_BYTES
        )
    document = _require_mapping(
        _decode_json_bytes(
            raw, maximum=MAX_COUNTER_DOCUMENT_BYTES, label="fixture counter bundle"
        ),
        "fixture counter bundle",
    )
    _require_exact_keys(
        document,
        {
            "schemaVersion",
            "fixtureRevision",
            "contractSchema",
            "captures",
            "bootstrapBlockedNetwork",
        },
        "fixture counter bundle",
    )
    if (
        document["schemaVersion"] != COUNTER_DOCUMENT_SCHEMA
        or document["fixtureRevision"] != COUNTER_DOCUMENT_REVISION
        or document["contractSchema"] != COUNTER_CONTRACT_SCHEMA
        or document["bootstrapBlockedNetwork"] != []
    ):
        raise _error("fixture counter bundle schema, revision, or blocked record differs")
    captures = _require_mapping(document["captures"], "fixture counter captures")
    if set(captures) != set(expected):
        raise _error("fixture counter capture ID set differs")
    capture_payloads: dict[str, dict[str, Any]] = {}
    for capture_id, expected_row in expected.items():
        bucket = _require_mapping(
            captures[capture_id], f"fixture counter capture bucket {capture_id}"
        )
        _require_exact_keys(
            bucket,
            {"counts", "blockedNetwork", "identity"},
            f"fixture counter capture bucket {capture_id}",
        )
        if bucket["blockedNetwork"] != []:
            raise _error("fixture counter capture recorded blocked network")
        observed_counts = _validate_counters(
            bucket["counts"], label=f"fixture counters {capture_id}"
        )
        positives = expected_row["positiveCounters"]
        zero_names = expected_row["zeroCounters"]
        declared = set(positives) | set(zero_names)
        if (
            any(observed_counts.get(name) != count for name, count in positives.items())
            or any(observed_counts.get(name, 0) != 0 for name in zero_names)
            or set(observed_counts) - declared
        ):
            raise _error("fixture counters differ from their exact declared contract")
        counts = {**positives, **{name: 0 for name in zero_names}}
        identity = _require_mapping(
            bucket["identity"], f"fixture counter identity {capture_id}"
        )
        _require_exact_keys(
            identity,
            {"selectedRegistryKey", "realCallable", "resolvedOwnedPaths"},
            f"fixture counter identity {capture_id}",
        )
        resolved = _require_mapping(
            identity["resolvedOwnedPaths"],
            f"fixture resolved owned paths {capture_id}",
        )
        frozen_identity = expected_row["identityRow"]
        if (
            identity["selectedRegistryKey"] != frozen_identity["registryKey"]
            or identity["realCallable"] != frozen_identity["callable"]
            or dict(resolved) != expected_row["ownedPaths"]
        ):
            raise _error("fixture counter route, callable, or owned paths differ")
        provider_counters = {
            name: count
            for name, count in counts.items()
            if not name.startswith("mutator.")
        }
        mutator_counters = {
            name: count
            for name, count in counts.items()
            if name.startswith("mutator.")
        }
        if any(mutator_counters.values()):
            raise _error("fixture counter bundle records a mutator operation")
        capture_payloads[capture_id] = {
            "identityRow": frozen_identity,
            "providerCounters": provider_counters,
            "mutatorCounters": mutator_counters,
        }
    payload = {
        "completeMatrix": complete_matrix,
        "profileEntrypoint": profile if complete_matrix else None,
        "captures": capture_payloads,
        "counterDocumentSha256": document_sha256,
        "counterDocumentSize": len(raw),
    }
    authenticated = AuthenticatedCounterBundle(payload, _key=_OPAQUE_KEY)
    with _AUTHENTICATED_COUNTERS_LOCK:
        _AUTHENTICATED_COUNTERS[id(authenticated)] = (
            authenticated,
            copy.deepcopy(payload),
        )
    return authenticated


def authenticate_raw_render_sidecar(
    browser_root_fd: int,
    relative_path: str,
    *,
    expected_owner: int,
    identity_row: Mapping[str, object],
) -> AuthenticatedRawRenderSidecar:
    """Authenticate one browser-staged, counter-empty canonical sidecar."""

    frozen_identity = _exact_worker_identity_row(identity_row)
    contract = freeze_artifact_contract(
        browser_root_fd,
        relative_path,
        expected_owner=expected_owner,
        max_bytes=MAX_RENDER_SIDECAR_BYTES,
    )
    with open_authenticated_artifact(browser_root_fd, contract) as artifact:
        raw, sha256, _observed = _hash_descriptor(
            artifact.descriptor, maximum=MAX_RENDER_SIDECAR_BYTES
        )
    document = _require_mapping(
        _decode_json_bytes(
            raw, maximum=MAX_RENDER_SIDECAR_BYTES, label="raw render sidecar"
        ),
        "raw render sidecar",
    )
    if canonicalize_worker_render_sidecar(document, owned_roots=()) != raw:
        raise _error("raw render sidecar is not canonical")
    if document.get("runtimeProjection") != {
        "sourceRoot": "$OWNED_ROOT_0",
        "browserScratchRoot": "$OWNED_ROOT_1",
    }:
        raise _error("raw render sidecar runtime roles differ from the frozen contract")
    if document.get("readiness") != {
        "ready": True,
        "marker": frozen_identity["readiness"]["text"],
    }:
        raise _error("raw render sidecar readiness differs from the frozen contract")
    identity = _require_mapping(document["identity"], "raw render identity")
    if (
        identity.get("case") != frozen_identity["case"]
        or identity.get("route") != frozen_identity["route"]
        or identity.get("callable") != frozen_identity["callable"]
        or document.get("viewport") != frozen_identity["viewport"]
    ):
        raise _error("raw render sidecar differs from its frozen identity")
    if frozen_identity["fixtureEntrypoint"] == "scripts/ui_ux_selection_fixture_app.py":
        if "controlEvidence" not in document:
            raise _error("focused raw sidecar lacks control evidence")
        if document.get("schemaVersion") == RENDER_V2_SCHEMA:
            root_capture = _require_mapping(
                document.get("rootCapture"),
                "raw root render capture identity",
            )
            if (
                root_capture.get("logicalCaptureId")
                != f'{frozen_identity["case"]}/{frozen_identity["viewport"]["name"]}'
            ):
                raise _error("raw root render logical identity differs")
            _validate_focused_control_evidence(
                document["controlEvidence"],
                expected_case=frozen_identity["case"],
                expected_viewport=frozen_identity["viewport"],
                require_screenshot_binding=True,
                expected_root_selector=root_capture.get("rootSelector"),
            )
        else:
            _validate_focused_control_evidence(
                document["controlEvidence"],
                expected_case=frozen_identity["case"],
                expected_viewport=frozen_identity["viewport"],
            )
    elif "controlEvidence" in document:
        raise _error("non-focused raw sidecar contains control evidence")
    stable_state = _require_mapping(
        document["stableState"], "raw render stableState"
    )
    if frozen_identity["case"] == "theme-gallery":
        _require_exact_keys(
            stable_state,
            {
                "finalPath",
                "controls",
                "diagnostics",
                "registryKey",
                "themeEvidence",
            },
            "theme raw render stableState",
        )
        diagnostics = _require_mapping(
            stable_state["diagnostics"], "theme raw diagnostics"
        )
        _require_exact_keys(
            diagnostics,
            {
                "blockedRequestCount",
                "failedRequestCount",
                "httpErrorCount",
                "pageErrorCount",
                "consoleErrorCount",
                "dialogCount",
                "downloadCount",
                "popupCount",
                "crashCount",
            },
            "theme raw diagnostics",
        )
        if (
            stable_state["finalPath"] != "/"
            or stable_state["controls"] != {}
            or stable_state["registryKey"] != "theme-gallery"
            or any(value != 0 for value in diagnostics.values())
            or document["nodes"] != []
        ):
            raise _error("theme raw render stable state differs")
        validate_theme_worker_evidence(
            stable_state["themeEvidence"],
            expected_viewport=frozen_identity["viewport"],
        )
    elif "themeEvidence" in stable_state:
        raise _error("non-theme raw sidecar cannot contain theme evidence")
    observed_roots = [
        node.get("rootSelector")
        for node in document["nodes"]
        if node.get("rootSelector") is not None
    ]
    if (
        len(observed_roots) != len(set(observed_roots))
        or set(observed_roots) != set(frozen_identity["rootSelectors"])
    ):
        raise _error("raw render sidecar root-selector set differs")
    payload = {
        "document": copy.deepcopy(dict(document)),
        "identityRow": frozen_identity,
        "sha256": sha256,
        "size": len(raw),
        "path": relative_path,
    }
    authenticated = AuthenticatedRawRenderSidecar(payload, _key=_OPAQUE_KEY)
    with _AUTHENTICATED_RAW_SIDECARS_LOCK:
        _AUTHENTICATED_RAW_SIDECARS[id(authenticated)] = (
            authenticated,
            copy.deepcopy(payload),
        )
    return authenticated


def finalize_render_sidecar(
    authenticated_raw_sidecar: AuthenticatedRawRenderSidecar,
    *,
    authenticated_counters: AuthenticatedCounterBundle,
    capture_id: str,
) -> bytes:
    """Author the counter-complete sidecar in the coordinator process."""

    counter_payload = _registered_counter_payload(authenticated_counters)
    if counter_payload.get("completeMatrix") is not True:
        raise _error("counter bundle does not cover a complete capture matrix")
    raw_payload = _registered_raw_sidecar_payload(authenticated_raw_sidecar)
    captures = counter_payload["captures"]
    if not isinstance(capture_id, str) or capture_id not in captures:
        raise _error("final render capture ID is not in the counter bundle")
    capture_payload = captures[capture_id]
    raw_value = copy.deepcopy(raw_payload["document"])
    identity = _require_mapping(raw_value["identity"], "worker render identity")
    identity_row = capture_payload["identityRow"]
    if (
        identity.get("case") != identity_row["case"]
        or identity.get("route") != identity_row["route"]
        or identity.get("callable") != identity_row["callable"]
        or raw_value.get("viewport") != identity_row["viewport"]
        or capture_id
        != f'{identity_row["case"]}/{identity_row["viewport"]["name"]}'
    ):
        raise _error("worker render identity differs from authenticated counters")
    raw_value["providerCounters"] = capture_payload["providerCounters"]
    raw_value["mutatorCounters"] = capture_payload["mutatorCounters"]
    raw_value["counterProvenance"] = {
        "schemaVersion": "quant-radar-ui-ux-counter-enrichment/v1",
        "counterDocumentSha256": counter_payload["counterDocumentSha256"],
        "captureId": capture_id,
        "registryKey": identity_row["registryKey"],
    }
    if raw_value.get("schemaVersion") == RENDER_V2_SCHEMA:
        semantic = _require_mapping(
            raw_value.get("caseSemanticProjection"),
            "worker case semantic projection",
        )
        semantic["providerCounters"] = copy.deepcopy(
            capture_payload["providerCounters"]
        )
        semantic["mutatorCounters"] = copy.deepcopy(
            capture_payload["mutatorCounters"]
        )
        semantic["counterProvenance"] = copy.deepcopy(
            raw_value["counterProvenance"]
        )
    final_raw = canonicalize_render_sidecar(raw_value, owned_roots=())
    final_digest = hashlib.sha256(final_raw).hexdigest()
    with _FINALIZED_RENDER_SIDECARS_LOCK:
        prior = _FINALIZED_RENDER_SIDECARS.get(final_digest)
        if prior is not None and prior != final_raw:
            raise _error("final render sidecar digest collision")
        _FINALIZED_RENDER_SIDECARS[final_digest] = final_raw
    return final_raw


def publish_finalized_capture(
    browser_root_fd: int,
    output_dir_fd: int,
    *,
    expected_owner: int,
    staged_png_path: str,
    authenticated_raw_sidecar: AuthenticatedRawRenderSidecar,
    authenticated_counters: AuthenticatedCounterBundle,
    capture_id: str,
    output_png_name: str = "capture.png",
    output_sidecar_name: str = "render.json",
) -> dict[str, Any]:
    """Publish one coordinator-finalized PNG/sidecar pair exclusively.

    The PNG is copied from a retained browser-staging descriptor.  The render
    sidecar is authored only from descriptor-authenticated worker bytes and the
    complete app counter bundle.  Both destination names are leaf-only and the
    returned claims are suitable for :func:`verify_capture_artifacts`.
    """

    if not _is_int(expected_owner):
        raise _error("finalized capture owner is invalid")
    png_name = _safe_leaf_name(output_png_name, label="final PNG name")
    sidecar_name = _safe_leaf_name(
        output_sidecar_name, label="final render-sidecar name"
    )
    if png_name == sidecar_name:
        raise _error("final capture artifact names must be distinct")
    output_identity = _owned_directory_identity(
        output_dir_fd,
        expected_owner=expected_owner,
        label="final capture output",
    )
    png_contract = freeze_artifact_contract(
        browser_root_fd,
        staged_png_path,
        expected_owner=expected_owner,
        max_bytes=MAX_PNG_BYTES,
    )
    with open_authenticated_artifact(browser_root_fd, png_contract) as png_artifact:
        png_raw, png_sha256, _png_stat = _hash_descriptor(
            png_artifact.descriptor, maximum=MAX_PNG_BYTES
        )
        width, height = _png_dimensions(png_raw)
        png_claim = copy_authenticated_artifact(
            png_artifact,
            output_dir_fd,
            png_name,
        )
    sidecar_raw = finalize_render_sidecar(
        authenticated_raw_sidecar,
        authenticated_counters=authenticated_counters,
        capture_id=capture_id,
    )
    sidecar_schema = _finalized_render_schema(
        sidecar_raw,
        require_live_provenance=True,
    )
    sidecar_sha256 = hashlib.sha256(sidecar_raw).hexdigest()
    _exclusive_write_at(output_dir_fd, sidecar_name, sidecar_raw)
    if (
        _owned_directory_identity(
            output_dir_fd,
            expected_owner=expected_owner,
            label="final capture output",
        )
        != output_identity
    ):
        raise _error("final capture output directory changed during publication")
    return {
        "png": {
            "path": png_name,
            "sha256": png_sha256,
            "size": png_claim["size"],
            "width": width,
            "height": height,
        },
        "renderSidecar": {
            "path": sidecar_name,
            "sha256": sidecar_sha256,
            "size": len(sidecar_raw),
            "schemaVersion": sidecar_schema,
        },
    }


def publish_derived_artifact(
    parent_png: AuthenticatedArtifact,
    output_dir_fd: int,
    *,
    expected_owner: int,
    artifact_id: str,
    output_name: str,
    crop: Mapping[str, object],
    theme_evidence_sha256: str,
) -> dict[str, Any]:
    """Publish one exact PNG crop derived from a retained parent descriptor."""

    if not isinstance(parent_png, AuthenticatedArtifact):
        raise _error("derived artifact parent is not descriptor-authenticated")
    with _AUTHENTICATED_ARTIFACTS_LOCK:
        if _AUTHENTICATED_ARTIFACTS.get(id(parent_png)) is not parent_png:
            raise _error("derived artifact parent lacks live descriptor provenance")
    parent_png._require_open()
    if artifact_id not in {"canvas", "panel", "elevated"}:
        raise _error("derived artifact surface is invalid")
    name = _safe_leaf_name(output_name, label="derived artifact name")
    if not _is_sha256(theme_evidence_sha256):
        raise _error("derived artifact theme evidence digest is invalid")
    crop_row = _require_mapping(crop, "derived artifact crop")
    _require_exact_keys(
        crop_row,
        {"x", "y", "width", "height"},
        "derived artifact crop",
    )
    if (
        any(not _is_int(crop_row[key]) for key in crop_row)
        or crop_row["x"] < 0
        or crop_row["y"] < 0
        or crop_row["width"] <= 0
        or crop_row["height"] <= 0
    ):
        raise _error("derived artifact crop geometry is invalid")
    output_identity = _owned_directory_identity(
        output_dir_fd,
        expected_owner=expected_owner,
        label="derived artifact output",
    )
    parent_raw, parent_sha256, parent_stat = _hash_descriptor(
        parent_png.descriptor,
        maximum=MAX_PNG_BYTES,
    )
    if (
        not _leaf_matches(parent_stat, parent_png.contract.leaf)
        or parent_sha256 != parent_png.contract.leaf.sha256
    ):
        raise _error("derived artifact parent changed before crop")
    try:
        from PIL import Image

        with Image.open(io.BytesIO(parent_raw)) as source_image:
            if source_image.format != "PNG":
                raise _error("derived artifact parent is not PNG")
            if (
                getattr(source_image, "is_animated", False)
                or getattr(source_image, "n_frames", 1) != 1
                or source_image.info.get("icc_profile") is not None
            ):
                raise _error(
                    "derived artifact parent must be a static single-frame PNG without an ICC profile"
                )
            source_image.load()
            image = source_image.copy()
        box = (
            crop_row["x"],
            crop_row["y"],
            crop_row["x"] + crop_row["width"],
            crop_row["y"] + crop_row["height"],
        )
        if box[2] > image.width or box[3] > image.height:
            raise _error("derived artifact crop exceeds its parent")
        cropped = image.crop(box)
        buffer = io.BytesIO()
        cropped.save(buffer, format="PNG")
        raw = buffer.getvalue()
    except EvidenceContractError:
        raise
    except BaseException as exc:
        raise _error("derived artifact crop could not be encoded", cause=exc)
    digest = hashlib.sha256(raw).hexdigest()
    _rehash_retained_artifact(parent_png)
    _exclusive_write_at(output_dir_fd, name, raw)
    contract = freeze_artifact_contract(
        output_dir_fd,
        name,
        expected_owner=expected_owner,
        max_bytes=MAX_PNG_BYTES,
    )
    with open_authenticated_artifact(output_dir_fd, contract) as artifact:
        observed_raw, observed_digest, observed_stat = _hash_descriptor(
            artifact.descriptor,
            maximum=MAX_PNG_BYTES,
        )
    if (
        _owned_directory_identity(
            output_dir_fd,
            expected_owner=expected_owner,
            label="derived artifact output",
        )
        != output_identity
        or observed_raw != raw
        or observed_digest != digest
        or not _leaf_matches(observed_stat, contract.leaf)
    ):
        raise _error("derived artifact changed during publication")
    _rehash_retained_artifact(parent_png)
    _require_exact_png_crop(
        parent_raw,
        raw,
        crop_row,
        label=f"derived artifact {artifact_id}",
    )
    width, height = _png_dimensions(raw)
    return {
        "id": artifact_id,
        "path": name,
        "sha256": digest,
        "size": len(raw),
        "width": width,
        "height": height,
        "source": {
            "parentPngSha256": parent_sha256,
            "themeEvidenceSha256": theme_evidence_sha256,
            "crop": copy.deepcopy(dict(crop_row)),
            "cropSha256": digest,
            "coordinateSpace": "full-page-css-pixels",
            "derivedWithoutResampling": True,
        },
    }


def _require_finalized_render_sidecar(
    raw: bytes, *, require_live_provenance: bool
) -> Mapping[str, Any]:
    digest = hashlib.sha256(raw).hexdigest()
    if require_live_provenance:
        with _FINALIZED_RENDER_SIDECARS_LOCK:
            registered = _FINALIZED_RENDER_SIDECARS.get(digest)
        if registered != raw:
            raise _error("render sidecar lacks coordinator finalization provenance")
    document = _require_mapping(
        _decode_json_bytes(
            raw, maximum=MAX_RENDER_SIDECAR_BYTES, label="final render sidecar"
        ),
        "final render sidecar",
    )
    if "counterProvenance" not in document:
        raise _error("render sidecar is not counter-enriched")
    if canonicalize_render_sidecar(document, owned_roots=()) != raw:
        raise _error("final render sidecar is not canonical")
    return document


def _finalized_render_schema(
    raw: bytes, *, require_live_provenance: bool
) -> str:
    """Return the schema authenticated by the exact finalized sidecar bytes."""

    document = _require_finalized_render_sidecar(
        raw,
        require_live_provenance=require_live_provenance,
    )
    schema = document.get("schemaVersion")
    if schema not in {RENDER_SCHEMA, RENDER_V2_SCHEMA}:
        raise _error("final render sidecar schema is unsupported")
    return schema


def _render_manifest_capture_id(
    document: Mapping[str, Any],
) -> str:
    provenance = _require_mapping(
        document.get("counterProvenance"),
        "render counter provenance",
    )
    logical_capture_id = provenance.get("captureId")
    if not isinstance(logical_capture_id, str) or not logical_capture_id:
        raise _error("render provenance has an invalid logical capture ID")
    if document.get("schemaVersion") != RENDER_V2_SCHEMA:
        return logical_capture_id
    root_capture = _require_mapping(
        document.get("rootCapture"),
        "render root capture identity",
    )
    root_capture_id = root_capture.get("rootCaptureId")
    if (
        not isinstance(root_capture_id, str)
        or not root_capture_id
        or root_capture.get("logicalCaptureId") != logical_capture_id
    ):
        raise _error("render root and logical capture identities differ")
    return root_capture_id


def _require_manifest_capture_id(
    capture_id: object,
    document: Mapping[str, Any],
) -> None:
    if capture_id != _render_manifest_capture_id(document):
        raise _error("manifest capture ID differs from its render sidecar")


def _png_dimensions(raw: bytes) -> tuple[int, int]:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_PNG_BYTES:
        raise _error("PNG bytes are empty or oversized")
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise _error("artifact is not a PNG")
    position = 8
    width: int | None = None
    height: int | None = None
    bit_depth: int | None = None
    color_type: int | None = None
    idat_parts: list[bytes] = []
    saw_iend = False
    chunk_index = 0
    while position < len(raw):
        if len(raw) - position < 12:
            raise _error("PNG has a truncated chunk")
        length = struct.unpack(">I", raw[position : position + 4])[0]
        kind = raw[position + 4 : position + 8]
        end = position + 12 + length
        if end > len(raw):
            raise _error("PNG chunk exceeds the artifact")
        payload = raw[position + 8 : position + 8 + length]
        checksum = struct.unpack(">I", raw[position + 8 + length : end])[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != checksum:
            raise _error("PNG chunk checksum is invalid")
        if chunk_index == 0 and kind != b"IHDR":
            raise _error("PNG IHDR must be first")
        if kind == b"IHDR":
            if chunk_index != 0 or length != 13 or width is not None:
                raise _error("PNG IHDR is invalid")
            (
                width,
                height,
                bit_depth,
                color_type,
                compression,
                filtering,
                interlace,
            ) = struct.unpack(">IIBBBBB", payload)
            if (
                width <= 0
                or height <= 0
                or width > 32_768
                or height > 32_768
                or width * height > 100_000_000
                or compression != 0
                or filtering != 0
                or interlace != 0
            ):
                raise _error("PNG dimensions or encoding are unsupported")
            allowed_depths = {
                0: {1, 2, 4, 8, 16},
                2: {8, 16},
                3: {1, 2, 4, 8},
                4: {8, 16},
                6: {8, 16},
            }
            if color_type not in allowed_depths or bit_depth not in allowed_depths[color_type]:
                raise _error("PNG color encoding is unsupported")
        elif kind == b"IDAT":
            if width is None or saw_iend:
                raise _error("PNG IDAT order is invalid")
            idat_parts.append(payload)
        elif kind == b"IEND":
            if length != 0 or not idat_parts:
                raise _error("PNG IEND is invalid")
            saw_iend = True
            position = end
            if position != len(raw):
                raise _error("PNG contains bytes after IEND")
            break
        position = end
        chunk_index += 1
    if width is None or height is None or bit_depth is None or color_type is None or not saw_iend:
        raise _error("PNG is incomplete")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    row_bytes = (width * channels * bit_depth + 7) // 8
    expected_decoded = height * (row_bytes + 1)
    decompressor = zlib.decompressobj()
    try:
        decoded = decompressor.decompress(b"".join(idat_parts), expected_decoded + 1)
    except zlib.error as exc:
        raise _error("PNG IDAT cannot be decoded", cause=exc)
    if (
        len(decoded) != expected_decoded
        or not decompressor.eof
        or decompressor.unused_data
        or decompressor.unconsumed_tail
    ):
        raise _error("PNG decoded raster length is invalid")
    return width, height


def _require_png_matches_render_viewport(
    dimensions: tuple[int, int],
    sidecar_document: Mapping[str, object],
    *,
    label: str,
) -> dict[str, Any]:
    """Bind a full-page PNG to the viewport authenticated by its sidecar."""

    viewport = _validate_viewport(
        sidecar_document.get("viewport"),
        label=f"{label} render viewport",
    )
    width, height = dimensions
    if width != viewport["width"] or height < viewport["height"]:
        raise _error(f"{label} PNG dimensions differ from its render viewport")
    identity = sidecar_document.get("identity")
    if isinstance(identity, Mapping) and identity.get("case") == "theme-gallery":
        stable_state = _require_mapping(
            sidecar_document.get("stableState"),
            f"{label} theme stable state",
        )
        theme_evidence = _require_mapping(
            stable_state.get("themeEvidence"),
            f"{label} theme evidence",
        )
        full_page = _require_mapping(
            theme_evidence.get("fullPage"),
            f"{label} theme full-page geometry",
        )
        if (
            set(full_page) != {"width", "height", "deviceScaleFactor"}
            or full_page.get("deviceScaleFactor") != 1
            or (width, height)
            != (full_page.get("width"), full_page.get("height"))
        ):
            raise _error(
                f"{label} theme PNG dimensions differ from full-page evidence"
            )
    return viewport


_OPAQUE_KEY = object()


class VerifiedCaptureArtifacts(Mapping[str, Any]):
    """Read-only view of independently authenticated PNG and render bytes."""

    __slots__ = ("_data", "__weakref__")

    def __init__(self, data: Mapping[str, Any], *, _key: object) -> None:
        if _key is not _OPAQUE_KEY:
            raise _error("verified capture objects are minted internally")
        self._data = MappingProxyType(copy.deepcopy(dict(data)))

    def __getitem__(self, key: str) -> Any:
        return copy.deepcopy(self._data[key])

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __copy__(self) -> VerifiedCaptureArtifacts:
        raise TypeError("verified capture objects cannot be copied")

    def __deepcopy__(self, _memo: object) -> VerifiedCaptureArtifacts:
        raise TypeError("verified capture objects cannot be copied")

    def close(self) -> None:
        _release_verified_capture(self)

    def __enter__(self) -> VerifiedCaptureArtifacts:
        _registered_capture_payload(self)
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()


@dataclass(frozen=True, slots=True)
class _VerifiedCaptureRecord:
    capture_ref: weakref.ReferenceType[VerifiedCaptureArtifacts]
    payload: dict[str, Any]
    capture_id: str
    run_directory_identity: tuple[int, int, int, int]
    capture_root_identity: tuple[int, int, int, int]
    capture_root_components: tuple[str, ...]
    png_contract: ArtifactContract
    sidecar_contract: ArtifactContract
    supplemental_contracts: tuple[ArtifactContract, ...]
    width: int
    height: int
    sidecar_schema: str
    authority_token: str


@dataclass(frozen=True, slots=True)
class _CaptureAuthorityBinding:
    capture: VerifiedCaptureArtifacts
    capture_id: str
    authority_token: str


_VERIFIED_CAPTURES: dict[int, _VerifiedCaptureRecord] = {}
_VERIFIED_CAPTURES_LOCK = threading.Lock()
_CLAIMED_CAPTURE_AUTHORITIES: set[str] = set()


def _capture_authority_snapshot(
    value: object,
) -> tuple[
    dict[str, Any],
    tuple[int, int, int, int],
    _CaptureAuthorityBinding,
]:
    if not isinstance(value, VerifiedCaptureArtifacts):
        raise _error("capture artifacts are not authenticated")
    with _VERIFIED_CAPTURES_LOCK:
        registered = _VERIFIED_CAPTURES.get(id(value))
        if registered is None or registered.capture_ref() is not value:
            raise _error("capture artifacts lack live provenance")
        return (
            copy.deepcopy(registered.payload),
            registered.run_directory_identity,
            _CaptureAuthorityBinding(
                capture=value,
                capture_id=registered.capture_id,
                authority_token=registered.authority_token,
            ),
        )


def _release_verified_capture(value: object) -> None:
    if not isinstance(value, VerifiedCaptureArtifacts):
        raise _error("capture artifacts are not authenticated")
    with _VERIFIED_CAPTURES_LOCK:
        registered = _VERIFIED_CAPTURES.get(id(value))
        if registered is None or registered.capture_ref() is not value:
            return
        if registered.authority_token in _CLAIMED_CAPTURE_AUTHORITIES:
            raise _error("capture artifacts are reserved for finalization")
        _VERIFIED_CAPTURES.pop(id(value), None)


def _capture_record_for_binding_locked(
    binding: _CaptureAuthorityBinding,
) -> _VerifiedCaptureRecord:
    registered = _VERIFIED_CAPTURES.get(id(binding.capture))
    if (
        registered is None
        or registered.capture_ref() is not binding.capture
        or registered.capture_id != binding.capture_id
        or registered.authority_token != binding.authority_token
    ):
        raise _error("capture finalization authority changed")
    return registered


def _release_capture_bindings_locked(
    bindings: Sequence[_CaptureAuthorityBinding],
) -> None:
    for binding in bindings:
        registered = _VERIFIED_CAPTURES.get(id(binding.capture))
        if (
            registered is not None
            and registered.capture_ref() is binding.capture
            and registered.authority_token == binding.authority_token
        ):
            _VERIFIED_CAPTURES.pop(id(binding.capture), None)
        _CLAIMED_CAPTURE_AUTHORITIES.discard(binding.authority_token)


def _registered_capture_payload(value: object) -> dict[str, Any]:
    payload, _run_identity, _binding = _capture_authority_snapshot(value)
    return payload


def _registered_capture_id(value: object) -> str:
    _payload, _run_identity, binding = _capture_authority_snapshot(value)
    return binding.capture_id


def _registered_capture_run_directory_identity(
    value: object,
) -> tuple[int, int, int, int]:
    _payload, run_identity, _binding = _capture_authority_snapshot(value)
    return run_identity


def _owned_directory_identity(
    descriptor: int, *, expected_owner: int, label: str
) -> tuple[int, int, int, int]:
    try:
        observed = os.fstat(descriptor)
    except OSError as exc:
        raise _error(f"{label} cannot be inspected", cause=exc)
    if not stat.S_ISDIR(observed.st_mode) or observed.st_uid != expected_owner:
        raise _error(f"{label} is not an owned directory")
    return (
        observed.st_dev,
        observed.st_ino,
        observed.st_uid,
        stat.S_IMODE(observed.st_mode),
    )


def _capture_root_components(
    directory_fd: int,
    run_root_fd: int,
    *,
    expected_owner: int,
) -> tuple[str, ...]:
    """Derive a bounded run-relative directory path only from live descriptors."""

    run_identity = _owned_directory_identity(
        run_root_fd,
        expected_owner=expected_owner,
        label="capture run root",
    )
    _owned_directory_identity(
        directory_fd,
        expected_owner=expected_owner,
        label="capture artifact root",
    )
    try:
        current_fd = os.dup(directory_fd)
    except OSError as exc:
        raise _error("capture artifact root cannot be duplicated", cause=exc)
    reversed_components: list[str] = []
    try:
        for _depth in range(MAX_CAPTURE_ROOT_DEPTH + 1):
            current = os.fstat(current_fd)
            current_identity = (
                current.st_dev,
                current.st_ino,
                current.st_uid,
                stat.S_IMODE(current.st_mode),
            )
            if current_identity == run_identity:
                return tuple(reversed(reversed_components))
            if not stat.S_ISDIR(current.st_mode) or current.st_uid != expected_owner:
                raise _error("capture artifact ancestry is not an owned directory")
            parent_fd = os.open(
                "..",
                os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC,
                dir_fd=current_fd,
            )
            keep_parent = False
            try:
                parent = os.fstat(parent_fd)
                if (parent.st_dev, parent.st_ino) == (
                    current.st_dev,
                    current.st_ino,
                ):
                    raise _error(
                        "capture artifact root is outside its run-root namespace"
                    )
                entries = os.listdir(parent_fd)
                if len(entries) > MAX_CAPTURE_PARENT_ENTRIES:
                    raise _error(
                        "capture artifact parent directory exceeds its entry bound"
                    )
                matches: list[str] = []
                for name in entries:
                    if not isinstance(name, str) or name in {"", ".", ".."}:
                        continue
                    child_fd: int | None = None
                    try:
                        child_fd = os.open(
                            name,
                            os.O_RDONLY
                            | _O_DIRECTORY
                            | _O_NOFOLLOW
                            | _O_CLOEXEC,
                            dir_fd=parent_fd,
                        )
                        child = os.fstat(child_fd)
                    except OSError:
                        continue
                    finally:
                        if child_fd is not None:
                            os.close(child_fd)
                    if (child.st_dev, child.st_ino) == (
                        current.st_dev,
                        current.st_ino,
                    ):
                        matches.append(
                            _safe_leaf_name(
                                name,
                                label="capture root component",
                            )
                        )
                if len(matches) != 1:
                    raise _error(
                        "capture artifact ancestry changed while resolving its name"
                    )
                reversed_components.append(matches[0])
                os.close(current_fd)
                current_fd = parent_fd
                keep_parent = True
            finally:
                if not keep_parent:
                    os.close(parent_fd)
        raise _error("capture artifact root ancestry exceeds its depth bound")
    except OSError as exc:
        raise _error("capture artifact root ancestry cannot be authenticated", cause=exc)
    finally:
        os.close(current_fd)


def _contract_binds_capture_root(
    contract: ArtifactContract,
    root_components: tuple[str, ...],
    root_identity: tuple[int, int, int, int],
) -> bool:
    if root_components:
        if len(contract.parents) < len(root_components):
            return False
        component = contract.parents[len(root_components) - 1]
        if tuple(parent.name for parent in contract.parents[: len(root_components)]) != (
            root_components
        ):
            return False
    else:
        component = contract.root
    return (
        component.device,
        component.inode,
        component.owner_uid,
        component.mode,
    ) == root_identity


def _validate_capture_record(
    record: object,
    *,
    allow_supplemental: bool = False,
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    value = _require_mapping(record, "capture artifact record")
    expected_keys = {"png", "renderSidecar"}
    if allow_supplemental and "supplementalArtifacts" in value:
        expected_keys.add("supplementalArtifacts")
    _require_exact_keys(value, expected_keys, "capture artifact record")
    png = _require_mapping(value["png"], "capture PNG record")
    _require_exact_keys(
        png, {"path", "sha256", "size", "width", "height"}, "capture PNG record"
    )
    sidecar = _require_mapping(value["renderSidecar"], "capture render record")
    _require_exact_keys(
        sidecar,
        {"path", "sha256", "size", "schemaVersion"},
        "capture render record",
    )
    for label, descriptor in (("PNG", png), ("render", sidecar)):
        _safe_relative_components(descriptor["path"], label=f"capture {label} path")
        if not _is_sha256(descriptor["sha256"]):
            raise _error(f"capture {label} digest is invalid")
        if not _is_int(descriptor["size"]) or descriptor["size"] < 0:
            raise _error(f"capture {label} size is invalid")
    for key in ("width", "height"):
        if not _is_int(png[key]) or png[key] <= 0:
            raise _error(f"capture PNG {key} is invalid")
    if sidecar["schemaVersion"] not in {
        RENDER_SCHEMA,
        RENDER_V2_SCHEMA,
    }:
        raise _error("capture render schema is unsupported")
    if png["path"] == sidecar["path"]:
        raise _error("capture artifact paths must be distinct")
    return png, sidecar


def _validate_supplemental_artifact_claims(
    value: object,
) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        raise _error("supplemental artifacts must be a finite sequence")
    claims: list[dict[str, Any]] = []
    for index, raw_claim in enumerate(value):
        claim = _require_mapping(raw_claim, f"supplemental artifact {index}")
        _require_exact_keys(
            claim,
            {"id", "path", "sha256", "size", "width", "height", "source"},
            f"supplemental artifact {index}",
        )
        if claim["id"] not in {"canvas", "panel", "elevated"}:
            raise _error("supplemental artifact surface is invalid")
        _safe_relative_components(
            claim["path"], label=f"supplemental artifact {index} path"
        )
        if not _is_sha256(claim["sha256"]):
            raise _error("supplemental artifact digest is invalid")
        for key in ("size", "width", "height"):
            if (
                not _is_int(claim[key])
                or claim[key] <= 0
            ):
                raise _error(f"supplemental artifact {key} is invalid")
        source = _require_mapping(
            claim["source"], f"supplemental artifact {index} source"
        )
        _require_exact_keys(
            source,
            {
                "parentPngSha256",
                "themeEvidenceSha256",
                "crop",
                "cropSha256",
                "coordinateSpace",
                "derivedWithoutResampling",
            },
            f"supplemental artifact {index} source",
        )
        crop = _require_mapping(
            source["crop"], f"supplemental artifact {index} crop"
        )
        _require_exact_keys(
            crop,
            {"x", "y", "width", "height"},
            f"supplemental artifact {index} crop",
        )
        if (
            not _is_sha256(source["parentPngSha256"])
            or not _is_sha256(source["themeEvidenceSha256"])
            or not _is_sha256(source["cropSha256"])
            or source["coordinateSpace"] != "full-page-css-pixels"
            or source["derivedWithoutResampling"] is not True
            or any(not _is_int(crop[key]) for key in crop)
            or crop["x"] < 0
            or crop["y"] < 0
            or crop["width"] <= 0
            or crop["height"] <= 0
            or (claim["width"], claim["height"])
            != (crop["width"], crop["height"])
        ):
            raise _error("supplemental artifact source binding is invalid")
        claims.append(copy.deepcopy(dict(claim)))
    if claims and tuple(claim["id"] for claim in claims) != (
        "canvas",
        "panel",
        "elevated",
    ):
        raise _error("supplemental artifact surface order differs")
    paths = [claim["path"] for claim in claims]
    if len(paths) != len(set(paths)):
        raise _error("supplemental artifact paths are not unique")
    return tuple(claims)


def _require_exact_png_crop(
    parent_raw: bytes,
    crop_raw: bytes,
    crop: Mapping[str, int],
    *,
    label: str,
) -> None:
    """Require decoded pixels to equal one exact, unscaled parent PNG crop."""

    try:
        from PIL import Image

        with Image.open(io.BytesIO(parent_raw)) as parent_image:
            if parent_image.format != "PNG":
                raise _error(f"{label} parent is not PNG")
            if (
                getattr(parent_image, "is_animated", False)
                or getattr(parent_image, "n_frames", 1) != 1
                or parent_image.info.get("icc_profile") is not None
            ):
                raise _error(
                    f"{label} parent must be a static single-frame PNG without an ICC profile"
                )
            parent_image.load()
            parent = parent_image.convert("RGBA")
        with Image.open(io.BytesIO(crop_raw)) as crop_image:
            if crop_image.format != "PNG":
                raise _error(f"{label} is not PNG")
            if (
                getattr(crop_image, "is_animated", False)
                or getattr(crop_image, "n_frames", 1) != 1
                or crop_image.info.get("icc_profile") is not None
            ):
                raise _error(
                    f"{label} must be a static single-frame PNG without an ICC profile"
                )
            crop_image.load()
            observed = crop_image.convert("RGBA")
    except EvidenceContractError:
        raise
    except BaseException as exc:
        raise _error(f"{label} PNG pixels cannot be decoded", cause=exc)
    box = (
        crop["x"],
        crop["y"],
        crop["x"] + crop["width"],
        crop["y"] + crop["height"],
    )
    if (
        box[2] > parent.width
        or box[3] > parent.height
        or observed.size != (crop["width"], crop["height"])
    ):
        raise _error(f"{label} crop geometry exceeds its parent")
    expected = parent.crop(box)
    if observed.tobytes() != expected.tobytes():
        raise _error(f"{label} pixels differ from the authenticated parent crop")


def verify_capture_artifacts(
    root_fd: int,
    record: Mapping[str, object],
    *,
    expected_owner: int,
    run_root_fd: int,
    supplemental_artifacts: Sequence[Mapping[str, object]] = (),
) -> VerifiedCaptureArtifacts:
    """Authenticate one authority capture and optional descriptor-bound crops."""

    run_directory_identity = _owned_directory_identity(
        run_root_fd,
        expected_owner=expected_owner,
        label="capture run root",
    )
    capture_root_identity = _owned_directory_identity(
        root_fd,
        expected_owner=expected_owner,
        label="capture artifact root",
    )
    capture_root_components = _capture_root_components(
        root_fd,
        run_root_fd,
        expected_owner=expected_owner,
    )
    png_claim, sidecar_claim = _validate_capture_record(record)
    supplemental_claims = _validate_supplemental_artifact_claims(
        supplemental_artifacts
    )
    png_components = _safe_relative_components(
        png_claim["path"], label="capture PNG path"
    )
    sidecar_components = _safe_relative_components(
        sidecar_claim["path"], label="capture render path"
    )
    png_relative_path = "/".join((*capture_root_components, *png_components))
    sidecar_relative_path = "/".join(
        (*capture_root_components, *sidecar_components)
    )
    png_contract = freeze_artifact_contract(
        run_root_fd,
        png_relative_path,
        expected_owner=expected_owner,
        max_bytes=MAX_PNG_BYTES,
    )
    sidecar_contract = freeze_artifact_contract(
        run_root_fd,
        sidecar_relative_path,
        expected_owner=expected_owner,
        max_bytes=MAX_RENDER_SIDECAR_BYTES,
    )
    supplemental_contracts = tuple(
        freeze_artifact_contract(
            run_root_fd,
            "/".join(
                (
                    *capture_root_components,
                    *_safe_relative_components(
                        claim["path"],
                        label=f"supplemental {claim['id']} path",
                    ),
                )
            ),
            expected_owner=expected_owner,
            max_bytes=MAX_PNG_BYTES,
        )
        for claim in supplemental_claims
    )
    all_contracts = (png_contract, sidecar_contract, *supplemental_contracts)
    if any(
        (
            contract.root.device,
            contract.root.inode,
            contract.root.owner_uid,
            contract.root.mode,
        )
        != run_directory_identity
        for contract in all_contracts
    ) or not _contract_binds_capture_root(
        png_contract,
        capture_root_components,
        capture_root_identity,
    ) or not _contract_binds_capture_root(
        sidecar_contract,
        capture_root_components,
        capture_root_identity,
    ) or any(
        not _contract_binds_capture_root(
            contract,
            capture_root_components,
            capture_root_identity,
        )
        for contract in supplemental_contracts
    ):
        raise _error("capture artifacts escaped their authenticated capture root")
    with open_authenticated_artifact(run_root_fd, png_contract) as png_artifact:
        png_raw, png_sha256, _png_stat = _hash_descriptor(
            png_artifact.descriptor, maximum=MAX_PNG_BYTES
        )
    with open_authenticated_artifact(
        run_root_fd, sidecar_contract
    ) as sidecar_artifact:
        sidecar_raw, sidecar_sha256, _sidecar_stat = _hash_descriptor(
            sidecar_artifact.descriptor, maximum=MAX_RENDER_SIDECAR_BYTES
        )
    supplemental_observations: list[tuple[bytes, str, os.stat_result]] = []
    for contract in supplemental_contracts:
        with open_authenticated_artifact(run_root_fd, contract) as artifact:
            supplemental_observations.append(
                _hash_descriptor(artifact.descriptor, maximum=MAX_PNG_BYTES)
            )
    if (
        png_sha256 != png_claim["sha256"]
        or len(png_raw) != png_claim["size"]
        or sidecar_sha256 != sidecar_claim["sha256"]
        or len(sidecar_raw) != sidecar_claim["size"]
    ):
        raise _error("capture artifact digest or size differs from its record")
    width, height = _png_dimensions(png_raw)
    if (width, height) != (png_claim["width"], png_claim["height"]):
        raise _error("capture PNG dimensions differ from its record")
    sidecar_document = _require_finalized_render_sidecar(
        sidecar_raw, require_live_provenance=True
    )
    _require_png_matches_render_viewport(
        (width, height),
        sidecar_document,
        label="capture artifact",
    )
    focused_evidence = sidecar_document.get("controlEvidence")
    if (
        isinstance(focused_evidence, Mapping)
        and focused_evidence.get("schemaVersion")
        in {
            FOCUSED_CONTROL_EVIDENCE_V2_SCHEMA,
            FOCUSED_CONTROL_EVIDENCE_V3_SCHEMA,
        }
        and (width, height)
        != (
            sidecar_document["viewport"]["width"],
            sidecar_document["viewport"]["height"],
        )
    ):
        raise _error(
            "focused screenshot dimensions differ from its bound viewport"
        )
    if sidecar_document.get("schemaVersion") != sidecar_claim["schemaVersion"]:
        raise _error("capture render schema differs from its record")
    capture_id = _render_manifest_capture_id(sidecar_document)
    identity = _require_mapping(sidecar_document["identity"], "capture identity")
    is_theme = identity.get("case") == "theme-gallery"
    if bool(supplemental_claims) != is_theme:
        raise _error(
            "theme captures require exactly three supplements and non-theme captures forbid them"
        )
    supplemental_payloads: list[dict[str, Any]] = []
    if supplemental_claims:
        stable_state = _require_mapping(
            sidecar_document["stableState"], "theme capture stable state"
        )
        rich = validate_theme_worker_evidence(
            stable_state.get("themeEvidence"),
            expected_viewport=sidecar_document["viewport"],
        )
        surface_rows = _require_mapping(
            {row["name"]: row for row in rich["surfaces"]},
            "theme surface rows",
        )
        for claim, contract, observation in zip(
            supplemental_claims,
            supplemental_contracts,
            supplemental_observations,
        ):
            raw, digest, observed = observation
            surface = _require_mapping(
                surface_rows.get(claim["id"]),
                f"theme surface {claim['id']}",
            )
            geometry = _require_mapping(
                surface["geometry"], f"theme geometry {claim['id']}"
            )
            source = claim["source"]
            if (
                digest != claim["sha256"]
                or len(raw) != claim["size"]
                or source["parentPngSha256"] != png_sha256
                or source["themeEvidenceSha256"] != rich["sha256"]
                or source["crop"] != geometry["crop"]
                or source["coordinateSpace"] != geometry["coordinateSpace"]
                or source["cropSha256"] != digest
                or not _leaf_matches(observed, contract.leaf)
                or _png_dimensions(raw) != (claim["width"], claim["height"])
            ):
                raise _error(
                    f"supplemental artifact binding differs: {claim['id']}"
                )
            _require_exact_png_crop(
                png_raw,
                raw,
                source["crop"],
                label=f"supplemental artifact {claim['id']}",
            )
            supplement = copy.deepcopy(claim)
            supplement["path"] = contract.relative_path
            supplemental_payloads.append(supplement)
    if (
        _owned_directory_identity(
            run_root_fd,
            expected_owner=expected_owner,
            label="capture run root",
        )
        != run_directory_identity
        or _owned_directory_identity(
            root_fd,
            expected_owner=expected_owner,
            label="capture artifact root",
        )
        != capture_root_identity
        or _capture_root_components(
            root_fd,
            run_root_fd,
            expected_owner=expected_owner,
        )
        != capture_root_components
    ):
        raise _error("capture artifact root changed during authentication")
    payload = {
        "png": {
            "path": png_relative_path,
            "sha256": png_sha256,
            "size": len(png_raw),
            "width": width,
            "height": height,
        },
        "renderSidecar": {
            "path": sidecar_relative_path,
            "sha256": sidecar_sha256,
            "size": len(sidecar_raw),
            "schemaVersion": sidecar_claim["schemaVersion"],
        },
    }
    if supplemental_payloads:
        payload["supplementalArtifacts"] = supplemental_payloads
    verified = VerifiedCaptureArtifacts(payload, _key=_OPAQUE_KEY)
    capture_key = id(verified)
    authority_token = secrets.token_hex(32)

    def expire_unclaimed_capture(
        _reference: weakref.ReferenceType[VerifiedCaptureArtifacts],
    ) -> None:
        try:
            with _VERIFIED_CAPTURES_LOCK:
                registered = _VERIFIED_CAPTURES.get(capture_key)
                if (
                    registered is not None
                    and registered.authority_token == authority_token
                    and authority_token not in _CLAIMED_CAPTURE_AUTHORITIES
                ):
                    _VERIFIED_CAPTURES.pop(capture_key, None)
        except BaseException:
            pass

    capture_ref = weakref.ref(verified, expire_unclaimed_capture)
    with _VERIFIED_CAPTURES_LOCK:
        if len(_VERIFIED_CAPTURES) >= MAX_VERIFIED_CAPTURE_AUTHORITIES:
            raise _error("verified capture authority registry is full")
        _VERIFIED_CAPTURES[capture_key] = _VerifiedCaptureRecord(
            capture_ref=capture_ref,
            payload=copy.deepcopy(payload),
            capture_id=capture_id,
            run_directory_identity=run_directory_identity,
            capture_root_identity=capture_root_identity,
            capture_root_components=capture_root_components,
            png_contract=png_contract,
            sidecar_contract=sidecar_contract,
            supplemental_contracts=supplemental_contracts,
            width=width,
            height=height,
            sidecar_schema=sidecar_claim["schemaVersion"],
            authority_token=authority_token,
        )
    return verified


def _open_reauthenticated_capture_record(
    run_root_fd: int,
    run_directory_identity: tuple[int, int, int, int],
    record: _VerifiedCaptureRecord,
    stack: ExitStack,
) -> tuple[AuthenticatedArtifact, ...]:
    """Reopen one verified capture and retain every exact leaf descriptor."""

    if record.run_directory_identity != run_directory_identity:
        raise _error("capture finalization run-root binding changed")
    if _owned_directory_identity(
        run_root_fd,
        expected_owner=run_directory_identity[2],
        label="capture finalization run root",
    ) != run_directory_identity:
        raise _error("capture finalization run root identity changed")
    for contract in (
        record.png_contract,
        record.sidecar_contract,
        *record.supplemental_contracts,
    ):
        if (
            (
                contract.root.device,
                contract.root.inode,
                contract.root.owner_uid,
                contract.root.mode,
            )
            != run_directory_identity
            or not _contract_binds_capture_root(
                contract,
                record.capture_root_components,
                record.capture_root_identity,
            )
        ):
            raise _error("capture finalization ancestry binding changed")
    png_artifact = stack.enter_context(
        open_authenticated_artifact(run_root_fd, record.png_contract)
    )
    sidecar_artifact = stack.enter_context(
        open_authenticated_artifact(run_root_fd, record.sidecar_contract)
    )
    supplemental_artifacts = tuple(
        stack.enter_context(open_authenticated_artifact(run_root_fd, contract))
        for contract in record.supplemental_contracts
    )
    png_raw, png_sha256, png_stat = _hash_descriptor(
        png_artifact.descriptor, maximum=MAX_PNG_BYTES
    )
    sidecar_raw, sidecar_sha256, sidecar_stat = _hash_descriptor(
        sidecar_artifact.descriptor, maximum=MAX_RENDER_SIDECAR_BYTES
    )
    supplemental_observations = tuple(
        _hash_descriptor(artifact.descriptor, maximum=MAX_PNG_BYTES)
        for artifact in supplemental_artifacts
    )
    png_payload = record.payload.get("png")
    sidecar_payload = record.payload.get("renderSidecar")
    if not isinstance(png_payload, Mapping) or not isinstance(
        sidecar_payload, Mapping
    ):
        raise _error("capture finalization payload changed")
    if (
        png_payload.get("path") != record.png_contract.relative_path
        or png_payload.get("sha256") != png_sha256
        or png_payload.get("size") != len(png_raw)
        or sidecar_payload.get("path") != record.sidecar_contract.relative_path
        or sidecar_payload.get("sha256") != sidecar_sha256
        or sidecar_payload.get("size") != len(sidecar_raw)
        or not _leaf_matches(png_stat, record.png_contract.leaf)
        or not _leaf_matches(sidecar_stat, record.sidecar_contract.leaf)
    ):
        raise _error("capture artifact changed before terminal finalization")
    width, height = _png_dimensions(png_raw)
    if (
        (width, height) != (record.width, record.height)
        or png_payload.get("width") != width
        or png_payload.get("height") != height
    ):
        raise _error("capture dimensions changed before terminal finalization")
    sidecar_document = _require_finalized_render_sidecar(
        sidecar_raw, require_live_provenance=True
    )
    if (
        sidecar_document.get("schemaVersion") != record.sidecar_schema
        or sidecar_payload.get("schemaVersion") != record.sidecar_schema
        or _render_manifest_capture_id(sidecar_document) != record.capture_id
    ):
        raise _error("capture sidecar changed before terminal finalization")
    raw_supplemental_payloads = record.payload.get("supplementalArtifacts", ())
    if not isinstance(raw_supplemental_payloads, (list, tuple)) or len(
        raw_supplemental_payloads
    ) != len(record.supplemental_contracts):
        raise _error("capture supplemental payload changed before finalization")
    if record.supplemental_contracts:
        rich = validate_theme_worker_evidence(
            _require_mapping(
                sidecar_document["stableState"], "theme finalization stable state"
            ).get("themeEvidence"),
            expected_viewport=sidecar_document["viewport"],
        )
        surfaces = {row["name"]: row for row in rich["surfaces"]}
        for payload, contract, observation in zip(
            raw_supplemental_payloads,
            record.supplemental_contracts,
            supplemental_observations,
        ):
            claim = _require_mapping(payload, "capture supplemental payload")
            raw, digest, observed = observation
            source = _require_mapping(
                claim.get("source"), "capture supplemental source"
            )
            surface = _require_mapping(
                surfaces.get(claim.get("id")), "capture supplemental surface"
            )
            geometry = _require_mapping(
                surface.get("geometry"), "capture supplemental geometry"
            )
            if (
                claim.get("path") != contract.relative_path
                or claim.get("sha256") != digest
                or claim.get("size") != len(raw)
                or source.get("parentPngSha256") != png_sha256
                or source.get("themeEvidenceSha256") != rich["sha256"]
                or source.get("crop") != geometry["crop"]
                or source.get("coordinateSpace") != geometry["coordinateSpace"]
                or source.get("cropSha256") != digest
                or source.get("derivedWithoutResampling") is not True
                or _png_dimensions(raw)
                != (claim.get("width"), claim.get("height"))
                or not _leaf_matches(observed, contract.leaf)
            ):
                raise _error("capture supplemental changed before finalization")
            _require_exact_png_crop(
                png_raw,
                raw,
                source["crop"],
                label=f"capture supplemental {claim.get('id')}",
            )
    return (png_artifact, sidecar_artifact, *supplemental_artifacts)


def _reauthenticate_artifact_path(
    root_fd: int,
    contract: ArtifactContract,
) -> None:
    """Authenticate one current path without retaining another leaf FD."""

    with open_authenticated_artifact(root_fd, contract):
        pass


def _rehash_retained_artifact(
    artifact: AuthenticatedArtifact,
) -> None:
    """Perform the last byte/inode check immediately before pass publication."""

    artifact._require_open()
    _raw, sha256, observed = _hash_descriptor(
        artifact.descriptor, maximum=artifact.contract.max_bytes
    )
    if (
        not _leaf_matches(observed, artifact.contract.leaf)
        or sha256 != artifact.contract.leaf.sha256
    ):
        raise _error("authenticated artifact changed during terminal finalization")


def _manifest_bytes(document: Mapping[str, Any]) -> bytes:
    raw = _canonical_json_bytes(document, newline=True)
    if len(raw) > MAX_MANIFEST_BYTES:
        raise _error("manifest exceeds its byte bound")
    return raw


def _exclusive_write_at(directory_fd: int, name: str, raw: bytes) -> None:
    """Compatibility seam: all new-leaf writes use atomic no-replace publish."""

    _exclusive_publish_bytes_at(directory_fd, name, raw)


def _exclusive_publish_bytes_at(
    directory_fd: int,
    name: str,
    raw: bytes,
    *,
    before_link: Callable[[], None] | None = None,
) -> None:
    """Publish complete bytes under a new leaf without an observable partial file."""

    leaf = _safe_leaf_name(name, label="evidence output name")
    temporary = f".{leaf}.{secrets.token_hex(12)}.tmp"
    descriptor: int | None = None
    linked = False
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW | _O_CLOEXEC,
            0o600,
            dir_fd=directory_fd,
        )
        _write_all(descriptor, raw)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        if before_link is not None:
            before_link()
        os.link(
            temporary,
            leaf,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
            follow_symlinks=False,
        )
        linked = True
        os.unlink(temporary, dir_fd=directory_fd)
        temporary = ""
        try:
            os.fsync(directory_fd)
        except OSError as exc:
            error = ManifestDurabilityUncertain(
                f"evidence output {leaf!r} was published but directory durability is uncertain"
            )
            error.__cause__ = exc
            raise error
    except ManifestDurabilityUncertain:
        raise
    except OSError as exc:
        if linked:
            error = ManifestDurabilityUncertain(
                f"evidence output {leaf!r} was published but link cleanup is uncertain"
            )
            error.__cause__ = exc
            raise error
        raise _error(f"could not atomically create evidence output {leaf!r}", cause=exc)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary:
            try:
                os.unlink(temporary, dir_fd=directory_fd)
            except OSError:
                pass


def _atomic_replace_at(directory_fd: int, name: str, raw: bytes) -> None:
    leaf = _safe_leaf_name(name, label="manifest name")
    temporary = f".{leaf}.{secrets.token_hex(12)}.tmp"
    descriptor: int | None = None
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW | _O_CLOEXEC,
            0o600,
            dir_fd=directory_fd,
        )
        _write_all(descriptor, raw)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.replace(
            temporary,
            leaf,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
        temporary = ""
        try:
            os.fsync(directory_fd)
        except OSError as exc:
            error = ManifestDurabilityUncertain(
                f"manifest {leaf!r} was published but directory durability is uncertain"
            )
            error.__cause__ = exc
            raise error
    except OSError as exc:
        raise _error(f"could not checkpoint manifest {leaf!r}", cause=exc)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary:
            try:
                os.unlink(temporary, dir_fd=directory_fd)
            except FileNotFoundError:
                pass


def _materialize_json(value: object) -> Any:
    if isinstance(value, VerifiedCaptureArtifacts):
        return _registered_capture_payload(value)
    if isinstance(value, Mapping):
        return {str(key): _materialize_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_materialize_json(item) for item in value]
    _validate_json_tree(value, label="manifest value")
    return copy.deepcopy(value)


def _bounded_terminal_error(
    exc: BaseException,
    *,
    secrets_to_redact: Sequence[str],
    private_roots: Sequence[os.PathLike[str] | str],
) -> dict[str, str]:
    message = str(exc)
    redactions = [str(value) for value in secrets_to_redact if str(value)]
    redactions.extend(str(value) for value in private_roots if str(value))
    for value in sorted(set(redactions), key=len, reverse=True):
        message = message.replace(value, "[REDACTED]")
    raw_type = type(exc).__name__
    error_type = "".join(
        character
        for character in raw_type
        if character.isascii() and (character.isalnum() or character == "_")
    )
    error_type = error_type[:128] or "Error"
    result = {"type": error_type, "message": message}
    while len(_canonical_json_bytes(result)) > MAX_MANIFEST_ERROR_BYTES and message:
        encoded = message.encode("utf-8", errors="replace")
        encoded = encoded[: max(0, len(encoded) - max(1, len(encoded) // 8))]
        message = encoded.decode("utf-8", errors="ignore")
        result["message"] = message
    if len(_canonical_json_bytes(result)) > MAX_MANIFEST_ERROR_BYTES:
        raise _error("terminal error metadata cannot fit its bound")
    return result


class ManifestLifecycle:
    """Monotonic, atomically checkpointed manifest state machine."""

    __slots__ = (
        "_output_dir_fd",
        "_manifest_name",
        "_base_document",
        "_directory_identity",
        "_state",
        "_document",
        "_contract",
        "_lock",
        "_closed",
    )

    def __init__(
        self,
        output_dir_fd: int,
        manifest_name: str,
        *,
        base_document: Mapping[str, object],
    ) -> None:
        safe_manifest_name = _safe_leaf_name(manifest_name, label="manifest name")
        base = _require_mapping(base_document, "manifest base document")
        if "status" in base:
            raise _error("manifest base document cannot supply status")
        materialized_base = _materialize_json(base)
        directory_identity = _owned_directory_identity(
            output_dir_fd,
            expected_owner=os.getuid(),
            label="manifest output",
        )
        try:
            owned_output_fd = os.dup(output_dir_fd)
        except OSError as exc:
            raise _error("manifest output descriptor cannot be duplicated", cause=exc)
        try:
            if _owned_directory_identity(
                owned_output_fd,
                expected_owner=directory_identity[2],
                label="owned manifest output",
            ) != directory_identity:
                raise _error("manifest output identity changed during construction")
        except BaseException:
            os.close(owned_output_fd)
            raise
        self._output_dir_fd = owned_output_fd
        self._manifest_name = safe_manifest_name
        self._base_document = materialized_base
        self._directory_identity = directory_identity
        self._state = "new"
        self._document: dict[str, Any] | None = None
        self._contract: ArtifactContract | None = None
        self._lock = threading.RLock()
        self._closed = False

    @property
    def state(self) -> str:
        return self._state

    @property
    def directory_identity(self) -> tuple[int, int, int, int]:
        return self._directory_identity

    @property
    def manifest_name(self) -> str:
        return self._manifest_name

    def _close_output_descriptor(self) -> None:
        if not self._closed:
            self._closed = True
            try:
                os.close(self._output_dir_fd)
            except OSError as exc:
                raise _error("manifest output descriptor could not be closed", cause=exc)

    def __del__(self) -> None:
        try:
            self._close_output_descriptor()
        except BaseException:
            pass

    def _refresh_contract(self) -> None:
        self._contract = freeze_artifact_contract(
            self._output_dir_fd,
            self._manifest_name,
            expected_owner=os.getuid(),
            max_bytes=MAX_MANIFEST_BYTES,
        )

    def _read_current(self) -> tuple[dict[str, Any], bytes]:
        if self._closed:
            raise _error("manifest output descriptor is closed")
        if self._contract is None:
            raise _error("manifest has not started")
        if _owned_directory_identity(
            self._output_dir_fd,
            expected_owner=self._directory_identity[2],
            label="manifest output",
        ) != self._directory_identity:
            raise _error("manifest output directory identity changed")
        with open_authenticated_artifact(
            self._output_dir_fd, self._contract
        ) as artifact:
            raw, _sha256, _observed = _hash_descriptor(
                artifact.descriptor, maximum=MAX_MANIFEST_BYTES
            )
        value = _decode_json_bytes(raw, maximum=MAX_MANIFEST_BYTES, label="manifest")
        document = dict(_require_mapping(value, "manifest"))
        if _manifest_bytes(document) != raw:
            raise _error("manifest checkpoint is not canonical")
        if document.get("status") != self._state:
            raise _error("manifest state differs from lifecycle state")
        return document, raw

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._state != "new":
                raise _error("manifest lifecycle already started")
            document = copy.deepcopy(self._base_document)
            document["status"] = "running"
            durability_error: ManifestDurabilityUncertain | None = None
            try:
                _exclusive_write_at(
                    self._output_dir_fd,
                    self._manifest_name,
                    _manifest_bytes(document),
                )
            except ManifestDurabilityUncertain as exc:
                durability_error = exc
            self._state = "running"
            self._document = document
            self._refresh_contract()
            if durability_error is not None:
                raise durability_error
            return copy.deepcopy(document)

    def _transition(
        self,
        status: str,
        updates: Mapping[str, object],
    ) -> dict[str, Any]:
        if status == "passed":
            raise _error("passed transition is unavailable through the lifecycle API")
        update_value = _require_mapping(updates, "manifest updates")
        if "status" in update_value:
            raise _error("manifest updates cannot supply status")
        current, _raw = self._read_current()
        document = copy.deepcopy(current)
        document.update(_materialize_json(update_value))
        document["status"] = status
        durability_error: ManifestDurabilityUncertain | None = None
        try:
            _atomic_replace_at(
                self._output_dir_fd,
                self._manifest_name,
                _manifest_bytes(document),
            )
        except ManifestDurabilityUncertain as exc:
            durability_error = exc
        self._state = status
        self._document = document
        if status == "finalizing":
            self._refresh_contract()
        else:
            self._close_output_descriptor()
        if durability_error is not None:
            raise durability_error
        return copy.deepcopy(document)

    def mark_finalizing(self, updates: Mapping[str, object]) -> dict[str, Any]:
        with self._lock:
            if self._state != "running":
                raise _error("manifest can only finalize from running")
            return self._transition("finalizing", updates)

    def mark_terminal(
        self, status: str, updates: Mapping[str, object]
    ) -> dict[str, Any]:
        with self._lock:
            if status == "passed":
                raise _error("passed is finalizer-only")
            if status not in {
                "failed",
                "dependency_unavailable",
                "invalid_data",
                "interrupted",
            }:
                raise _error("terminal manifest status is unsupported")
            if self._state not in {"running", "finalizing"}:
                raise _error("terminal manifest is immutable")
            try:
                return self._transition(status, updates)
            finally:
                if self._state == status:
                    _revoke_lifecycle_finalization_authorities(self)

    @contextmanager
    def capture_failures(
        self,
        *,
        partial_artifacts: Sequence[VerifiedCaptureArtifacts] = (),
        secrets: Sequence[str] = (),
        private_roots: Sequence[os.PathLike[str] | str] = (),
    ) -> Iterator[None]:
        try:
            yield
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                status = "interrupted"
            elif isinstance(exc, DependencyUnavailable):
                status = "dependency_unavailable"
            elif isinstance(exc, InvalidEvidence):
                status = "invalid_data"
            else:
                status = "failed"
            updates: dict[str, Any] = {
                "error": _bounded_terminal_error(
                    exc,
                    secrets_to_redact=secrets,
                    private_roots=private_roots,
                )
            }
            if partial_artifacts:
                updates["partialArtifacts"] = [
                    _registered_capture_payload(item) for item in partial_artifacts
                ]
            if self._state in {"running", "finalizing"}:
                self.mark_terminal(status, updates)
            raise


def verify_referenceable_manifest(
    source_dir_fd: int,
    manifest_name: str,
    *,
    expected_owner: int,
    require_passed: bool = True,
) -> dict[str, Any]:
    contract = freeze_artifact_contract(
        source_dir_fd,
        manifest_name,
        expected_owner=expected_owner,
        max_bytes=MAX_MANIFEST_BYTES,
    )
    with open_authenticated_artifact(source_dir_fd, contract) as artifact:
        raw, _sha256, _observed = _hash_descriptor(
            artifact.descriptor, maximum=MAX_MANIFEST_BYTES
        )
    document = dict(
        _require_mapping(
            _decode_json_bytes(raw, maximum=MAX_MANIFEST_BYTES, label="manifest"),
            "manifest",
        )
    )
    if _manifest_bytes(document) != raw:
        raise _error("referenceable manifest is not canonical")
    if document.get("schemaVersion") != EVIDENCE_SCHEMA:
        raise _error("referenceable manifest schema is unsupported")
    if require_passed and document.get("status") != "passed":
        raise _error("manifest is not a referenceable passed run")
    return document


_FORMAL_STALE_RUN_ID_RE = re.compile(r"ux1b-(?:[0-9a-f]{24}|[0-9a-f]{32})")
_FORMAL_STALE_RUN_IDENTITIES = MappingProxyType(
    {
        ("ux1b-full-pages", "precontrol"): (
            "scripts/ui_ux_fixture_app.py",
            81,
        ),
        ("ux1b-full-pages", "pretheme"): (
            "scripts/ui_ux_fixture_app.py",
            81,
        ),
        ("ux1b-full-pages", "posttheme"): (
            "scripts/ui_ux_fixture_app.py",
            81,
        ),
        ("ux1b-selection-controls", "precontrol"): (
            "scripts/ui_ux_selection_fixture_app.py",
            36,
        ),
        ("ux1b-selection-controls", "postcontrol"): (
            "scripts/ui_ux_selection_fixture_app.py",
            36,
        ),
        ("ux1b-theme", "posttheme"): (
            "scripts/ui_ux_theme_fixture_app.py",
            3,
        ),
    }
)


def _formal_stale_run_identity(source: Mapping[str, object]) -> dict[str, object]:
    if source.get("schemaVersion") != EVIDENCE_SCHEMA:
        raise _error("stale manifest schema is unsupported")
    run_id = source.get("runId")
    mode = source.get("mode")
    phase = source.get("phase")
    fixture_entrypoint = source.get("fixtureEntrypoint")
    expected_count = source.get("expectedCaptureCount")
    if not isinstance(run_id, str) or _FORMAL_STALE_RUN_ID_RE.fullmatch(run_id) is None:
        raise _error("stale manifest run identity is invalid")
    if not isinstance(mode, str) or not isinstance(phase, str):
        raise _error("stale manifest mode or phase is invalid")
    expected = _FORMAL_STALE_RUN_IDENTITIES.get((mode, phase))
    if expected is None:
        raise _error("stale manifest mode and phase are not a formal UX1B run")
    if (
        (mode, phase) == ("ux1b-selection-controls", "postcontrol")
        and source.get("rootExpansionSha256")
        == ROOT_CAPTURE_EXPANSION_SHA256
    ):
        expected = (expected[0], ROOT_CAPTURE_EXPANSION_ROWS)
    if (
        fixture_entrypoint != expected[0]
        or not _is_int(expected_count)
        or expected_count != expected[1]
    ):
        raise _error("stale manifest fixture or expected capture count differs")
    return {
        "schemaVersion": EVIDENCE_SCHEMA,
        "mode": mode,
        "phase": phase,
        "runId": run_id,
        "fixtureEntrypoint": fixture_entrypoint,
        "expectedCaptureCount": expected_count,
    }


def classify_formal_stale_run_identity(
    source: Mapping[str, object],
) -> dict[str, object]:
    """Validate and return one public, immutable formal stale-run identity."""

    return copy.deepcopy(_formal_stale_run_identity(source))


def _accept_existing_recovery_record(
    recovery_dir_fd: int,
    recovery_name: str,
    expected_raw: bytes,
    *,
    publication_error: EvidenceContractError,
) -> None:
    try:
        contract = freeze_artifact_contract(
            recovery_dir_fd,
            recovery_name,
            expected_owner=os.getuid(),
            max_bytes=MAX_MANIFEST_BYTES,
        )
        with open_authenticated_artifact(recovery_dir_fd, contract) as artifact:
            observed_raw, _sha256, _observed = _hash_descriptor(
                artifact.descriptor,
                maximum=MAX_MANIFEST_BYTES,
            )
    except EvidenceContractError:
        raise publication_error
    if observed_raw != expected_raw:
        raise _error(
            "recovery classification output already exists with different bytes",
            cause=publication_error,
        )
    try:
        os.fsync(recovery_dir_fd)
    except OSError as exc:
        error = ManifestDurabilityUncertain(
            "existing recovery classification directory durability is uncertain"
        )
        error.__cause__ = exc
        raise error


def record_stale_nonterminal(
    source_dir_fd: int,
    manifest_name: str,
    recovery_dir_fd: int,
    recovery_name: str,
    *,
    expected_owner: int,
) -> dict[str, Any]:
    contract = freeze_artifact_contract(
        source_dir_fd,
        manifest_name,
        expected_owner=expected_owner,
        max_bytes=MAX_MANIFEST_BYTES,
    )
    with open_authenticated_artifact(source_dir_fd, contract) as artifact:
        raw, sha256, _observed = _hash_descriptor(
            artifact.descriptor, maximum=MAX_MANIFEST_BYTES
        )
    source = dict(
        _require_mapping(
            _decode_json_bytes(raw, maximum=MAX_MANIFEST_BYTES, label="stale manifest"),
            "stale manifest",
        )
    )
    if _manifest_bytes(source) != raw:
        raise _error("stale manifest is not canonical")
    source_status = source.get("status")
    if source_status not in {"running", "finalizing"}:
        raise _error("only a nonterminal manifest can be classified stale")
    identity = _formal_stale_run_identity(source)
    record = {
        **identity,
        "status": "stale_nonterminal",
        "sourceStatus": source_status,
        "referenceable": False,
        "sourceManifest": {
            "path": manifest_name,
            "sha256": sha256,
            "size": len(raw),
        },
    }
    record_raw = _manifest_bytes(record)
    try:
        _exclusive_publish_bytes_at(
            recovery_dir_fd,
            recovery_name,
            record_raw,
        )
    except ManifestDurabilityUncertain:
        raise
    except EvidenceContractError as exc:
        _accept_existing_recovery_record(
            recovery_dir_fd,
            recovery_name,
            record_raw,
            publication_error=exc,
        )
    return record


@dataclass(frozen=True, slots=True)
class _ComparatorReportRecord:
    report: dict[str, Any]
    snapshot: dict[str, Any]
    sha256: str
    kind: str
    covered_profiles: tuple[str, ...]
    capture_stack_digest: str | None


_COMPARATOR_REPORTS: dict[int, _ComparatorReportRecord] = {}
_COMPARATOR_REPORTS_LOCK = threading.Lock()


def _register_comparator_report(
    report: dict[str, Any], *, kind: str
) -> dict[str, Any]:
    raw = _canonical_json_bytes(report)
    snapshot = dict(
        _require_mapping(
            _decode_json_bytes(
                raw,
                maximum=MAX_MANIFEST_BYTES,
                label="comparator report",
            ),
            "comparator report",
        )
    )
    if snapshot.get("status") != "passed":
        raise _error("comparator report is not passing")
    raw_profiles = snapshot.get("coveredProfiles", [])
    if not isinstance(raw_profiles, list):
        raise _error("comparator report coveredProfiles are invalid")
    profiles = tuple(raw_profiles)
    if (
        len(set(profiles)) != len(profiles)
        or any(profile not in _COUNTER_PROFILE_CAPTURE_IDS for profile in profiles)
    ):
        raise _error("comparator report coveredProfiles differ")
    stack_digest = snapshot.get("captureStackDigest")
    if profiles and not _is_sha256(stack_digest):
        raise _error("profile comparator report lacks a capture-stack digest")
    record = _ComparatorReportRecord(
        report=report,
        snapshot=snapshot,
        sha256=hashlib.sha256(raw).hexdigest(),
        kind=kind,
        covered_profiles=profiles,
        capture_stack_digest=(stack_digest if isinstance(stack_digest, str) else None),
    )
    with _COMPARATOR_REPORTS_LOCK:
        _COMPARATOR_REPORTS[id(report)] = record
    return report


def compare_theme_render_pair(
    *,
    before_sidecar: Mapping[str, object],
    after_sidecar: Mapping[str, object],
    before_png: bytes,
    after_png: bytes,
    before_owned_roots: Sequence[str],
    after_owned_roots: Sequence[str],
) -> dict[str, Any]:
    """Require an exact non-color render projection and a real theme delta."""

    before_canonical = canonicalize_render_sidecar(
        before_sidecar, owned_roots=before_owned_roots
    )
    after_canonical = canonicalize_render_sidecar(
        after_sidecar, owned_roots=after_owned_roots
    )
    if before_canonical != after_canonical:
        raise _error("theme pair changed canonical non-color render evidence")
    before_dimensions = _png_dimensions(before_png)
    after_dimensions = _png_dimensions(after_png)
    if before_dimensions != after_dimensions:
        raise _error("theme pair PNG dimensions differ")
    if before_png == after_png:
        raise _error("theme pair PNG bytes do not demonstrate a visual delta")
    report: dict[str, Any] = {
        "status": "passed",
        "canonicalSidecarsEqual": True,
        "pngBytesDiffer": True,
        "dimensions": {
            "width": before_dimensions[0],
            "height": before_dimensions[1],
        },
        "canonicalSidecarSha256": hashlib.sha256(before_canonical).hexdigest(),
        "beforePngSha256": hashlib.sha256(before_png).hexdigest(),
        "afterPngSha256": hashlib.sha256(after_png).hexdigest(),
    }
    return _register_comparator_report(report, kind="theme")


class _OpaqueAttestation:
    __slots__ = ()

    def __init__(self, *, _key: object) -> None:
        if _key is not _OPAQUE_KEY:
            raise _error("attestations are minted internally")

    def __copy__(self) -> _OpaqueAttestation:
        raise TypeError("attestations cannot be copied")

    def __deepcopy__(self, _memo: object) -> _OpaqueAttestation:
        raise TypeError("attestations cannot be copied")

    def __repr__(self) -> str:
        return f"<{type(self).__name__} opaque>"


class CalibrationAttestation(_OpaqueAttestation):
    __slots__ = ()


class ComparatorAttestation(_OpaqueAttestation):
    __slots__ = ()


_CALIBRATION_ATTESTATIONS: dict[int, tuple[CalibrationAttestation, str]] = {}
_COMPARATOR_ATTESTATIONS: dict[
    int, tuple[ComparatorAttestation, str, tuple[str, ...], str | None]
] = {}
_ATTESTATION_LOCK = threading.Lock()


def mint_calibration_attestation(
    live_calibration_report: Mapping[str, object],
) -> CalibrationAttestation:
    """Mint from the exact live report registered by the isolation layer."""

    try:
        digest = isolation.validate_live_calibration_provenance(
            live_calibration_report
        )
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        raise _error("calibration report lacks live provenance", cause=exc)
    if not _is_sha256(digest):
        raise _error("calibration provenance digest is invalid")
    attestation = CalibrationAttestation(_key=_OPAQUE_KEY)
    with _ATTESTATION_LOCK:
        _CALIBRATION_ATTESTATIONS[id(attestation)] = (attestation, digest)
    return attestation


def mint_comparator_attestation(
    comparator_report: Mapping[str, object],
) -> ComparatorAttestation:
    if not isinstance(comparator_report, dict):
        raise _error("comparator report has the wrong type")
    with _COMPARATOR_REPORTS_LOCK:
        registered = _COMPARATOR_REPORTS.get(id(comparator_report))
        if registered is None or registered.report is not comparator_report:
            raise _error("comparator report lacks live provenance")
        # Claim the exact registered snapshot while holding the registry lock.
        # Nothing below this line reads the caller-owned dictionary again.
        _COMPARATOR_REPORTS.pop(id(comparator_report), None)
        digest = registered.sha256
        profiles = registered.covered_profiles
        stack_digest = registered.capture_stack_digest
    attestation = ComparatorAttestation(_key=_OPAQUE_KEY)
    with _ATTESTATION_LOCK:
        _COMPARATOR_ATTESTATIONS[id(attestation)] = (
            attestation,
            digest,
            profiles,
            stack_digest,
        )
    return attestation


def _attestation_digest(value: object, *, calibration: bool) -> str:
    registry: Mapping[int, tuple[object, str]] = (
        _CALIBRATION_ATTESTATIONS if calibration else _COMPARATOR_ATTESTATIONS
    )
    expected_type: type[object] = (
        CalibrationAttestation if calibration else ComparatorAttestation
    )
    if not isinstance(value, expected_type):
        raise _error("success closure attestation has the wrong type")
    with _ATTESTATION_LOCK:
        registered = registry.get(id(value))
    if registered is None or registered[0] is not value:
        raise _error("success closure attestation lacks live provenance")
    return registered[1]


def _comparator_attestation_profile_binding(
    value: object,
) -> tuple[tuple[str, ...], str | None]:
    if not isinstance(value, ComparatorAttestation):
        raise _error("success closure comparator attestation has the wrong type")
    with _ATTESTATION_LOCK:
        registered = _COMPARATOR_ATTESTATIONS.get(id(value))
    if registered is None or registered[0] is not value:
        raise _error("success closure comparator attestation lacks live provenance")
    return registered[2], registered[3]


class ValidatedSuccessClosure:
    __slots__ = ("__weakref__",)

    def __init__(self, *, _key: object) -> None:
        if _key is not _OPAQUE_KEY:
            raise _error("validated closures are minted internally")

    def __copy__(self) -> ValidatedSuccessClosure:
        raise TypeError("validated closures cannot be copied")

    def __deepcopy__(self, _memo: object) -> ValidatedSuccessClosure:
        raise TypeError("validated closures cannot be copied")


@dataclass(frozen=True, slots=True)
class _ValidatedClosureRecord:
    closure_ref: weakref.ReferenceType[ValidatedSuccessClosure]
    closure_token: str
    lifecycle: ManifestLifecycle
    directory_identity: tuple[int, int, int, int]
    output_descriptor: int
    manifest_name: str
    manifest_contract: ArtifactContract
    manifest_sha256: str
    run_id: object
    capture_authorities: tuple[_CaptureAuthorityBinding, ...]
    snapshot: dict[str, Any]
    sha256: str


_VALIDATED_CLOSURES: dict[int, _ValidatedClosureRecord] = {}
_VALIDATED_CLOSURES_LOCK = threading.Lock()


def _snapshot_success_closure_value(value: object) -> object:
    """Copy caller-owned containers once while retaining opaque authorities."""

    if isinstance(value, VerifiedCaptureArtifacts):
        return value
    if isinstance(value, Mapping):
        try:
            items = tuple(value.items())
        except (RuntimeError, TypeError, ValueError) as exc:
            raise _error("success closure changed while taking its entry snapshot", cause=exc)
        return {
            key: _snapshot_success_closure_value(item)
            for key, item in items
        }
    if isinstance(value, list):
        return [_snapshot_success_closure_value(item) for item in tuple(value)]
    if isinstance(value, tuple):
        return tuple(_snapshot_success_closure_value(item) for item in value)
    return value


def _validate_counter_closure(value: object, *, label: str) -> dict[str, Any]:
    row = _require_mapping(value, label)
    _require_exact_keys(row, {"expected", "actual"}, label)
    expected = _validate_counters(row["expected"], label=f"{label}.expected")
    actual = _validate_counters(row["actual"], label=f"{label}.actual")
    if actual != expected:
        raise _error(f"{label} actual counters differ from expected")
    return {"expected": expected, "actual": actual}


def validate_success_closure(
    document: Mapping[str, object],
    *,
    lifecycle: ManifestLifecycle,
    expected_fixture_entrypoint: str,
    expected_capture_stack_digest: str,
    expected_source_digest: str,
    expected_app_origin: str,
    calibration_attestation: object,
    comparator_attestation: object,
) -> ValidatedSuccessClosure:
    """Validate every observation required before a pass can be authorized."""

    if not isinstance(lifecycle, ManifestLifecycle):
        raise _error("success closure lifecycle has the wrong type")
    source_value = _require_mapping(document, "success closure")
    value = _require_mapping(
        _snapshot_success_closure_value(source_value),
        "success closure entry snapshot",
    )
    _require_exact_keys(
        value,
        {
            "status",
            "captureStackDigest",
            "sourceDigestStart",
            "sourceDigestEnd",
            "captures",
            "providerCounters",
            "mutatorCounters",
            "prohibitedCounters",
            "processes",
            "network",
        },
        "success closure",
    )
    if expected_fixture_entrypoint not in _COUNTER_PROFILE_CAPTURE_IDS:
        raise _error("success closure fixture profile is not frozen")
    for expected, label in (
        (expected_capture_stack_digest, "capture-stack"),
        (expected_source_digest, "source"),
    ):
        if not _is_sha256(expected):
            raise _error(f"expected {label} digest is invalid")
    network_entry = _require_mapping(value["network"], "success network")
    network_raw = _canonical_json_bytes(network_entry)
    network = dict(
        _require_mapping(
            _decode_json_bytes(
                network_raw,
                maximum=MAX_WORKER_REQUEST_BYTES,
                label="success network",
            ),
            "success network",
        )
    )
    _require_exact_keys(network, {"appOrigin", "appPort"}, "success network")
    parsed = urlsplit(expected_app_origin)
    try:
        expected_port = parsed.port
    except ValueError as exc:
        raise _error("expected app origin has an invalid port", cause=exc)
    _validate_loopback_origin(expected_app_origin, expected=expected_app_origin)
    if network != {"appOrigin": expected_app_origin, "appPort": expected_port}:
        raise _error("success closure network assignment differs")
    expected_modes = {
        "scripts/ui_ux_fixture_app.py": "ux1b-full-pages",
        "scripts/ui_ux_selection_fixture_app.py": "ux1b-selection-controls",
        "scripts/ui_ux_theme_fixture_app.py": "ux1b-theme",
    }
    with lifecycle._lock:
        if lifecycle.state != "finalizing":
            raise _error("success closure requires a finalizing lifecycle")
        current_manifest, current_manifest_raw = lifecycle._read_current()
        if current_manifest.get("status") != "finalizing":
            raise _error("success closure lifecycle checkpoint is not finalizing")
        if current_manifest.get("mode") != expected_modes[expected_fixture_entrypoint]:
            raise _error("success closure fixture profile differs from lifecycle mode")
        lifecycle_directory_identity = lifecycle.directory_identity
        lifecycle_output_descriptor = lifecycle._output_dir_fd
        lifecycle_manifest_name = lifecycle._manifest_name
        lifecycle_manifest_contract = lifecycle._contract
        if lifecycle_manifest_contract is None:
            raise _error("success closure lifecycle manifest contract is missing")
        lifecycle_manifest_sha256 = hashlib.sha256(current_manifest_raw).hexdigest()
        lifecycle_run_id = current_manifest.get("runId")
        if not isinstance(lifecycle_run_id, str) or not lifecycle_run_id:
            raise _error("success closure lifecycle run ID is invalid")
        root_lifecycle_fields = {
            "plannedLogicalRequests",
            "plannedRootCaptures",
            "completedLogicalRequests",
            "completedRootCaptures",
            "rootExpansionSha256",
        }
        observed_root_lifecycle_fields = root_lifecycle_fields & set(
            current_manifest
        )
        is_root_capture_lifecycle = bool(observed_root_lifecycle_fields)
        if is_root_capture_lifecycle and (
            observed_root_lifecycle_fields != root_lifecycle_fields
            or expected_fixture_entrypoint
            != "scripts/ui_ux_selection_fixture_app.py"
            or current_manifest.get("plannedLogicalRequests") != 36
            or current_manifest.get("plannedRootCaptures") != 44
            or current_manifest.get("completedLogicalRequests") != 36
            or current_manifest.get("completedRootCaptures") != 44
            or current_manifest.get("expectedCaptureCount") != 44
            or current_manifest.get("capturedCount") != 44
            or current_manifest.get("rootExpansionSha256")
            != ROOT_CAPTURE_EXPANSION_SHA256
        ):
            raise _error("success closure root lifecycle accounting differs")
    calibration_digest = _attestation_digest(
        calibration_attestation, calibration=True
    )
    comparator_digest = _attestation_digest(
        comparator_attestation, calibration=False
    )
    comparator_profiles, comparator_stack_digest = _comparator_attestation_profile_binding(
        comparator_attestation
    )
    if expected_fixture_entrypoint not in comparator_profiles:
        raise _error("success closure comparator does not cover its fixture profile")
    if value["status"] != "finalizing":
        raise _error("success closure must describe a finalizing run")
    if value["captureStackDigest"] != expected_capture_stack_digest:
        raise _error("success closure capture-stack digest differs")
    if comparator_stack_digest != expected_capture_stack_digest:
        raise _error("success closure comparator capture-stack digest differs")
    if (
        value["sourceDigestStart"] != expected_source_digest
        or value["sourceDigestEnd"] != expected_source_digest
    ):
        raise _error("success closure source digest changed")
    logical_ids = tuple(
        sorted(_COUNTER_PROFILE_CAPTURE_IDS[expected_fixture_entrypoint])
    )
    expected_ids = (
        tuple(sorted(row["rootCaptureId"] for row in root_capture_expansion_rows()))
        if is_root_capture_lifecycle
        else logical_ids
    )
    captures = value["captures"]
    if not isinstance(captures, list) or len(captures) != len(expected_ids):
        raise _error("success closure capture count differs")
    observed_ids: list[str] = []
    materialized_captures: list[dict[str, Any]] = []
    capture_authorities: list[_CaptureAuthorityBinding] = []
    for index, raw_capture in enumerate(captures):
        capture = _require_mapping(raw_capture, f"success capture {index}")
        _require_exact_keys(capture, {"id", "status", "artifacts"}, f"success capture {index}")
        if not isinstance(capture["id"], str) or capture["status"] != "passed":
            raise _error("success closure contains a non-passing capture")
        artifact_payload, artifact_run_identity, authority = (
            _capture_authority_snapshot(capture["artifacts"])
        )
        if authority.capture_id != capture["id"]:
            raise _error("success closure capture ID differs from its verified sidecar")
        if artifact_run_identity != lifecycle_directory_identity:
            raise _error("success closure capture belongs to another run root")
        observed_ids.append(capture["id"])
        capture_authorities.append(authority)
        materialized_captures.append(
            {
                "id": capture["id"],
                "status": "passed",
                "artifacts": artifact_payload,
            }
        )
    if len(set(observed_ids)) != len(observed_ids) or set(observed_ids) != set(expected_ids):
        raise _error("success closure capture IDs differ")
    provider = _validate_counter_closure(
        value["providerCounters"], label="providerCounters"
    )
    mutator = _validate_counter_closure(
        value["mutatorCounters"], label="mutatorCounters"
    )
    prohibited = _validate_counters(
        value["prohibitedCounters"], label="prohibitedCounters"
    )
    if set(prohibited) != {"production.read", "production.write", "network.outbound"}:
        raise _error("success closure prohibited counter set differs")
    if any(prohibited.values()):
        raise _error("success closure observed a prohibited operation")
    processes = _require_mapping(value["processes"], "success processes")
    _require_exact_keys(processes, {"app", "browsers"}, "success processes")
    browser_proofs = _require_mapping(
        processes["browsers"], "success browser processes"
    )
    if set(browser_proofs) != set(logical_ids):
        raise _error("success browser process set differs from the frozen profile")
    profile_names = {
        "scripts/ui_ux_fixture_app.py": "full-pages",
        "scripts/ui_ux_selection_fixture_app.py": "selection-controls",
        "scripts/ui_ux_theme_fixture_app.py": "theme",
    }
    app_capture_id = f'app/{profile_names[expected_fixture_entrypoint]}'
    try:
        app_row, app_digest = isolation.consume_quiescent_process_exit_provenance(
            processes["app"],
            expected_session_id=lifecycle_run_id,
            expected_role="app",
            expected_process_id=app_capture_id,
        )
        materialized_browsers: dict[str, Any] = {}
        browser_digests: dict[str, str] = {}
        for capture_id in logical_ids:
            row, digest = isolation.consume_quiescent_process_exit_provenance(
                browser_proofs[capture_id],
                expected_session_id=lifecycle_run_id,
                expected_role="browser",
                expected_process_id=capture_id,
            )
            materialized_browsers[capture_id] = row
            browser_digests[capture_id] = digest
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        raise _error("success process exit lacks quiescent provenance", cause=exc)
    materialized_processes = {
        "app": app_row,
        "browsers": materialized_browsers,
        "attestationDigests": {
            "app": app_digest,
            "browsers": browser_digests,
        },
    }
    snapshot = {
        "status": "finalizing",
        "fixtureEntrypoint": expected_fixture_entrypoint,
        "captureStackDigest": expected_capture_stack_digest,
        "sourceDigestStart": expected_source_digest,
        "sourceDigestEnd": expected_source_digest,
        "captures": materialized_captures,
        "providerCounters": provider,
        "mutatorCounters": mutator,
        "prohibitedCounters": prohibited,
        "processes": materialized_processes,
        "network": {"appOrigin": expected_app_origin, "appPort": expected_port},
        "attestations": {
            "calibrationSha256": calibration_digest,
            "comparatorSha256": comparator_digest,
        },
    }
    closure = ValidatedSuccessClosure(_key=_OPAQUE_KEY)
    closure_key = id(closure)
    closure_token = secrets.token_hex(32)

    def expire_abandoned_closure(
        _reference: weakref.ReferenceType[ValidatedSuccessClosure],
    ) -> None:
        try:
            with _VALIDATED_CLOSURES_LOCK:
                abandoned = _VALIDATED_CLOSURES.get(closure_key)
                if (
                    abandoned is not None
                    and abandoned.closure_token == closure_token
                ):
                    _VALIDATED_CLOSURES.pop(closure_key, None)
        except BaseException:
            pass

    closure_ref = weakref.ref(closure, expire_abandoned_closure)
    closure_digest = hashlib.sha256(_canonical_json_bytes(snapshot)).hexdigest()
    with lifecycle._lock:
        if lifecycle.state != "finalizing":
            raise _error("success closure lifecycle changed during validation")
        final_manifest, final_manifest_raw = lifecycle._read_current()
        if (
            lifecycle.directory_identity != lifecycle_directory_identity
            or lifecycle._output_dir_fd != lifecycle_output_descriptor
            or lifecycle._manifest_name != lifecycle_manifest_name
            or lifecycle._contract != lifecycle_manifest_contract
            or hashlib.sha256(final_manifest_raw).hexdigest()
            != lifecycle_manifest_sha256
            or final_manifest.get("runId") != lifecycle_run_id
        ):
            raise _error("success closure lifecycle binding changed during validation")
        with _VALIDATED_CLOSURES_LOCK:
            if len(_VALIDATED_CLOSURES) >= MAX_VALIDATED_SUCCESS_CLOSURES:
                raise _error("validated success closure registry is full")
            _VALIDATED_CLOSURES[closure_key] = _ValidatedClosureRecord(
                closure_ref=closure_ref,
                closure_token=closure_token,
                lifecycle=lifecycle,
                directory_identity=lifecycle_directory_identity,
                output_descriptor=lifecycle_output_descriptor,
                manifest_name=lifecycle_manifest_name,
                manifest_contract=lifecycle_manifest_contract,
                manifest_sha256=lifecycle_manifest_sha256,
                run_id=lifecycle_run_id,
                capture_authorities=tuple(capture_authorities),
                snapshot=copy.deepcopy(snapshot),
                sha256=closure_digest,
            )
    return closure


class SuccessFinalizationGrant:
    __slots__ = ("__weakref__",)

    def __init__(self, *, _key: object) -> None:
        if _key is not _OPAQUE_KEY:
            raise _error("success finalization grants are minted internally")

    def __copy__(self) -> SuccessFinalizationGrant:
        raise TypeError("success finalization grants cannot be copied")

    def __deepcopy__(self, _memo: object) -> SuccessFinalizationGrant:
        raise TypeError("success finalization grants cannot be copied")

    def __repr__(self) -> str:
        return "<SuccessFinalizationGrant opaque>"


@dataclass(frozen=True, slots=True)
class _GrantRecord:
    grant_ref: weakref.ReferenceType[SuccessFinalizationGrant]
    grant_token: str
    lifecycle: ManifestLifecycle
    directory_identity: tuple[int, int, int, int]
    output_descriptor: int
    manifest_name: str
    manifest_contract: ArtifactContract
    manifest_sha256: str
    run_id: object
    capture_authorities: tuple[_CaptureAuthorityBinding, ...]
    closure_snapshot: dict[str, Any]
    closure_sha256: str


_SUCCESS_GRANTS: dict[int, _GrantRecord] = {}
_SUCCESS_GRANTS_LOCK = threading.Lock()


def _revoke_lifecycle_finalization_authorities(
    lifecycle: ManifestLifecycle,
) -> None:
    """Discard closure/grant authority when a lifecycle ends without passing."""

    with (
        _VALIDATED_CLOSURES_LOCK,
        _SUCCESS_GRANTS_LOCK,
        _VERIFIED_CAPTURES_LOCK,
    ):
        for closure_id, closure_record in tuple(_VALIDATED_CLOSURES.items()):
            if closure_record.lifecycle is lifecycle:
                _VALIDATED_CLOSURES.pop(closure_id, None)
        for grant_id, grant_record in tuple(_SUCCESS_GRANTS.items()):
            if grant_record.lifecycle is lifecycle:
                _SUCCESS_GRANTS.pop(grant_id, None)
                _release_capture_bindings_locked(
                    grant_record.capture_authorities
                )


def authorize_success_closure(
    lifecycle: ManifestLifecycle,
    *,
    validated_closure: ValidatedSuccessClosure,
) -> SuccessFinalizationGrant:
    if not isinstance(lifecycle, ManifestLifecycle):
        raise _error("success authorization lifecycle has the wrong type")
    if not isinstance(validated_closure, ValidatedSuccessClosure):
        raise _error("success authorization requires a validated closure")
    expected_modes = {
        "scripts/ui_ux_fixture_app.py": "ux1b-full-pages",
        "scripts/ui_ux_selection_fixture_app.py": "ux1b-selection-controls",
        "scripts/ui_ux_theme_fixture_app.py": "ux1b-theme",
    }
    with (
        lifecycle._lock,
        _VALIDATED_CLOSURES_LOCK,
        _SUCCESS_GRANTS_LOCK,
        _VERIFIED_CAPTURES_LOCK,
    ):
        registered = _VALIDATED_CLOSURES.get(id(validated_closure))
        if registered is None or registered.closure_ref() is not validated_closure:
            raise _error("validated closure lacks unused live provenance")
        if registered.lifecycle is not lifecycle:
            raise _error("validated closure belongs to another lifecycle")
        if lifecycle.state != "finalizing":
            raise _error("success authorization requires a finalizing lifecycle")
        current, raw = lifecycle._read_current()
        if (
            lifecycle.directory_identity != registered.directory_identity
            or lifecycle._output_dir_fd != registered.output_descriptor
            or lifecycle._manifest_name != registered.manifest_name
            or lifecycle._contract != registered.manifest_contract
            or hashlib.sha256(raw).hexdigest() != registered.manifest_sha256
            or current.get("runId") != registered.run_id
        ):
            raise _error("validated closure lifecycle binding changed")
        fixture_entrypoint = registered.snapshot.get("fixtureEntrypoint")
        if current.get("mode") != expected_modes.get(fixture_entrypoint):
            raise _error("success closure fixture profile differs from lifecycle mode")
        if hashlib.sha256(
            _canonical_json_bytes(registered.snapshot)
        ).hexdigest() != registered.sha256:
            raise _error("validated closure snapshot changed")
        snapshot_captures = registered.snapshot.get("captures")
        if not isinstance(snapshot_captures, list) or len(snapshot_captures) != len(
            registered.capture_authorities
        ):
            raise _error("validated closure capture authority set changed")
        tokens: list[str] = []
        for binding, capture_row in zip(
            registered.capture_authorities,
            snapshot_captures,
            strict=True,
        ):
            capture_record = _capture_record_for_binding_locked(binding)
            if (
                capture_record.run_directory_identity
                != registered.directory_identity
                or not isinstance(capture_row, Mapping)
                or capture_row.get("id") != binding.capture_id
                or capture_row.get("artifacts") != capture_record.payload
                or binding.authority_token in _CLAIMED_CAPTURE_AUTHORITIES
            ):
                raise _error("validated closure capture authority changed")
            tokens.append(binding.authority_token)
        if len(set(tokens)) != len(tokens):
            raise _error("validated closure reuses a capture authority")
        if len(_SUCCESS_GRANTS) >= MAX_SUCCESS_FINALIZATION_GRANTS:
            raise _error("success finalization grant registry is full")
        grant = SuccessFinalizationGrant(_key=_OPAQUE_KEY)
        grant_key = id(grant)
        grant_token = secrets.token_hex(32)

        def expire_abandoned_grant(
            _reference: weakref.ReferenceType[SuccessFinalizationGrant],
        ) -> None:
            try:
                with _SUCCESS_GRANTS_LOCK, _VERIFIED_CAPTURES_LOCK:
                    abandoned = _SUCCESS_GRANTS.get(grant_key)
                    if (
                        abandoned is not None
                        and abandoned.grant_token == grant_token
                    ):
                        _SUCCESS_GRANTS.pop(grant_key, None)
                        _release_capture_bindings_locked(
                            abandoned.capture_authorities
                        )
            except BaseException:
                pass

        grant_ref = weakref.ref(grant, expire_abandoned_grant)
        record = _GrantRecord(
            grant_ref=grant_ref,
            grant_token=grant_token,
            lifecycle=lifecycle,
            directory_identity=registered.directory_identity,
            output_descriptor=registered.output_descriptor,
            manifest_name=registered.manifest_name,
            manifest_contract=registered.manifest_contract,
            manifest_sha256=registered.manifest_sha256,
            run_id=registered.run_id,
            capture_authorities=registered.capture_authorities,
            closure_snapshot=copy.deepcopy(registered.snapshot),
            closure_sha256=registered.sha256,
        )
        for token in tokens:
            _CLAIMED_CAPTURE_AUTHORITIES.add(token)
        _VALIDATED_CLOSURES.pop(id(validated_closure), None)
        _SUCCESS_GRANTS[grant_key] = record
        return grant


def _authorized_terminal_manifest_locked(
    lifecycle: ManifestLifecycle,
    grant: SuccessFinalizationGrant,
) -> tuple[_GrantRecord, dict[str, Any], bytes]:
    """Validate one live grant and materialize its exact passed document."""

    record = _SUCCESS_GRANTS.get(id(grant))
    if record is None or record.grant_ref() is not grant:
        raise _error("finalization grant lacks unused live provenance")
    if record.lifecycle is not lifecycle:
        raise _error("finalization grant belongs to another lifecycle")
    if lifecycle.state != "finalizing":
        raise _error("finalization grant lifecycle is not finalizing")
    if (
        lifecycle.directory_identity != record.directory_identity
        or lifecycle._output_dir_fd != record.output_descriptor
        or lifecycle._manifest_name != record.manifest_name
        or lifecycle._contract != record.manifest_contract
    ):
        raise _error("finalization lifecycle destination binding changed")
    current, raw = lifecycle._read_current()
    if (
        hashlib.sha256(raw).hexdigest() != record.manifest_sha256
        or current.get("runId") != record.run_id
        or hashlib.sha256(
            _canonical_json_bytes(record.closure_snapshot)
        ).hexdigest()
        != record.closure_sha256
    ):
        raise _error("finalization grant binding changed")
    updates = copy.deepcopy(record.closure_snapshot)
    updates.pop("status", None)
    document = copy.deepcopy(current)
    document.update(_materialize_json(updates))
    document["status"] = "passed"
    return record, document, _manifest_bytes(document)


def materialize_authorized_terminal_manifest(
    lifecycle: ManifestLifecycle,
    *,
    grant: SuccessFinalizationGrant,
) -> dict[str, Any]:
    """Preview one authorized pass without consuming its grant or authority."""

    if not isinstance(lifecycle, ManifestLifecycle):
        raise _error("terminal materializer lifecycle has the wrong type")
    if not isinstance(grant, SuccessFinalizationGrant):
        raise _error("terminal materializer grant has the wrong type")
    with lifecycle._lock, _SUCCESS_GRANTS_LOCK:
        _record, document, _terminal_raw = _authorized_terminal_manifest_locked(
            lifecycle,
            grant,
        )
        return copy.deepcopy(document)


def finalize_terminal_manifest(
    lifecycle: ManifestLifecycle,
    *,
    grant: SuccessFinalizationGrant,
) -> dict[str, Any]:
    """Consume one exact grant and perform the sole authorized pass commit."""

    if not isinstance(lifecycle, ManifestLifecycle):
        raise _error("finalizer lifecycle has the wrong type")
    if not isinstance(grant, SuccessFinalizationGrant):
        raise _error("finalizer grant has the wrong type")
    durability_error: ManifestDurabilityUncertain | None = None
    published = False
    with lifecycle._lock, _SUCCESS_GRANTS_LOCK:
        record, document, terminal_raw = _authorized_terminal_manifest_locked(
            lifecycle,
            grant,
        )
        with _VERIFIED_CAPTURES_LOCK:
            try:
                capture_records = [
                    _capture_record_for_binding_locked(binding)
                    for binding in record.capture_authorities
                ]
                if any(
                    binding.authority_token not in _CLAIMED_CAPTURE_AUTHORITIES
                    for binding in record.capture_authorities
                ):
                    raise _error("finalization capture authority is not reserved")
                with ExitStack() as stack:
                    manifest_artifact = stack.enter_context(
                        open_authenticated_artifact(
                            record.output_descriptor,
                            record.manifest_contract,
                        )
                    )
                    retained_artifacts: list[AuthenticatedArtifact] = []
                    for capture_record in capture_records:
                        retained_artifacts.extend(
                            _open_reauthenticated_capture_record(
                                record.output_descriptor,
                                record.directory_identity,
                                capture_record,
                                stack,
                            )
                        )
                    if (
                        lifecycle._output_dir_fd != record.output_descriptor
                        or lifecycle._manifest_name != record.manifest_name
                        or lifecycle._contract != record.manifest_contract
                    ):
                        raise _error(
                            "finalization lifecycle destination changed during reauthentication"
                        )
                    _rehash_retained_artifact(manifest_artifact)
                    for artifact in retained_artifacts:
                        _rehash_retained_artifact(artifact)
                    # The first retained descriptor set authenticates exact
                    # inodes and stays open through publication, but a rename
                    # can detach one of those inodes from its manifest path.
                    # Resolve every path again after the last retained-FD hash,
                    # closing each second-pass descriptor before opening the
                    # next one so the exact 81-capture profile stays within the
                    # process descriptor limit.  The consumed quiescent-process
                    # proofs are the namespace synchronization boundary: no
                    # artifact writer remains authorized during this pass.
                    _reauthenticate_artifact_path(
                        record.output_descriptor,
                        record.manifest_contract,
                    )
                    for capture_record in capture_records:
                        _reauthenticate_artifact_path(
                            record.output_descriptor,
                            capture_record.png_contract,
                        )
                        _reauthenticate_artifact_path(
                            record.output_descriptor,
                            capture_record.sidecar_contract,
                        )
                        for supplemental_contract in (
                            capture_record.supplemental_contracts
                        ):
                            _reauthenticate_artifact_path(
                                record.output_descriptor,
                                supplemental_contract,
                            )
                    try:
                        _atomic_replace_at(
                            record.output_descriptor,
                            record.manifest_name,
                            terminal_raw,
                        )
                    except ManifestDurabilityUncertain as exc:
                        durability_error = exc
                    published = True
            except BaseException:
                _SUCCESS_GRANTS.pop(id(grant), None)
                _release_capture_bindings_locked(record.capture_authorities)
                if published:
                    lifecycle._state = "passed"
                    lifecycle._document = document
                    lifecycle._contract = None
                    lifecycle._close_output_descriptor()
                raise
            _SUCCESS_GRANTS.pop(id(grant), None)
            _release_capture_bindings_locked(record.capture_authorities)
        lifecycle._state = "passed"
        lifecycle._document = document
        lifecycle._contract = None
        lifecycle._close_output_descriptor()
        if durability_error is not None:
            raise durability_error
        return copy.deepcopy(document)


@dataclass(frozen=True, slots=True)
class _BundleCaptureContract:
    capture_id: str
    png: ArtifactContract
    render_sidecar: ArtifactContract
    supplemental: tuple[ArtifactContract, ...]


@dataclass(frozen=True, slots=True)
class ManifestBundleContract:
    manifest: ArtifactContract
    captures: tuple[_BundleCaptureContract, ...]
    manifest_sha256: str


class AuthenticatedManifestBundle:
    """Opaque, live descriptor-reauthenticated passed manifest bundle."""

    __slots__ = ("_manifest", "_manifest_sha256", "_captures")

    def __init__(
        self,
        *,
        manifest: Mapping[str, Any],
        manifest_sha256: str,
        captures: Sequence[Mapping[str, Any]],
        _key: object,
    ) -> None:
        if _key is not _OPAQUE_KEY:
            raise _error("authenticated manifest bundles are minted internally")
        self._manifest = copy.deepcopy(dict(manifest))
        self._manifest_sha256 = manifest_sha256
        self._captures = tuple(copy.deepcopy(dict(row)) for row in captures)

    @property
    def manifest(self) -> dict[str, Any]:
        return copy.deepcopy(self._manifest)

    @property
    def manifest_sha256(self) -> str:
        return self._manifest_sha256

    @property
    def captures(self) -> tuple[dict[str, Any], ...]:
        return tuple(copy.deepcopy(row) for row in self._captures)

    def __copy__(self) -> AuthenticatedManifestBundle:
        raise TypeError("authenticated manifest bundles cannot be copied")

    def __deepcopy__(self, _memo: object) -> AuthenticatedManifestBundle:
        raise TypeError("authenticated manifest bundles cannot be copied")


_MANIFEST_BUNDLES: dict[
    int, tuple[ManifestBundleContract, dict[str, Any]]
] = {}
_MANIFEST_BUNDLES_LOCK = threading.Lock()
_AUTHENTICATED_MANIFEST_BUNDLES: dict[
    int, tuple[AuthenticatedManifestBundle, dict[str, Any], str]
] = {}
_AUTHENTICATED_MANIFEST_BUNDLES_LOCK = threading.Lock()


def _registered_manifest_bundle(value: object) -> dict[str, Any]:
    if not isinstance(value, AuthenticatedManifestBundle):
        raise _error("manifest bundle is not authenticated")
    with _AUTHENTICATED_MANIFEST_BUNDLES_LOCK:
        registered = _AUTHENTICATED_MANIFEST_BUNDLES.get(id(value))
    if registered is None or registered[0] is not value:
        raise _error("manifest bundle lacks live descriptor provenance")
    payload = registered[1]
    if hashlib.sha256(_canonical_json_bytes(payload)).hexdigest() != registered[2]:
        raise _error("authenticated manifest bundle registry changed")
    return copy.deepcopy(payload)


def _bundle_capture_rows(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if document.get("schemaVersion") != EVIDENCE_SCHEMA or document.get("status") != "passed":
        raise _error("manifest bundle is not a passed evidence manifest")
    captures = document.get("captures")
    if not isinstance(captures, list) or not captures:
        raise _error("manifest bundle has no captures")
    rows: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    artifact_paths: set[str] = set()
    for index, raw_capture in enumerate(captures):
        capture = _require_mapping(raw_capture, f"manifest capture {index}")
        if set(capture) != {"id", "status", "artifacts"}:
            raise _error("manifest bundle capture keys differ")
        capture_id = capture["id"]
        if (
            not isinstance(capture_id, str)
            or not capture_id
            or capture_id in seen
            or capture["status"] != "passed"
        ):
            raise _error("manifest bundle capture identity or status is invalid")
        artifacts = _require_mapping(
            capture["artifacts"], f"manifest capture artifacts {index}"
        )
        png_claim, sidecar_claim = _validate_capture_record(
            artifacts,
            allow_supplemental=True,
        )
        supplemental = _validate_supplemental_artifact_claims(
            artifacts.get("supplementalArtifacts", ())
        )
        paths = {
            png_claim["path"],
            sidecar_claim["path"],
            *(claim["path"] for claim in supplemental),
        }
        if artifact_paths & paths:
            raise _error("manifest bundle reuses an artifact path across captures")
        artifact_paths.update(paths)
        seen.add(capture_id)
        rows.append(capture)
    return rows


def freeze_manifest_bundle_contract(
    root_fd: int,
    manifest_name: str,
    *,
    expected_owner: int,
    expected_manifest_sha256: str | None = None,
) -> ManifestBundleContract:
    """Freeze a passed manifest and every artifact inode it references."""

    if not _is_sha256(expected_manifest_sha256):
        raise _error("manifest bundle requires an external expected SHA-256")

    manifest_contract = freeze_artifact_contract(
        root_fd,
        manifest_name,
        expected_owner=expected_owner,
        max_bytes=MAX_MANIFEST_BYTES,
    )
    with open_authenticated_artifact(root_fd, manifest_contract) as artifact:
        manifest_raw, manifest_sha256, _observed = _hash_descriptor(
            artifact.descriptor, maximum=MAX_MANIFEST_BYTES
        )
    if manifest_sha256 != expected_manifest_sha256:
        raise _error("manifest bundle differs from its external expected SHA-256")
    document = dict(
        _require_mapping(
            _decode_json_bytes(
                manifest_raw, maximum=MAX_MANIFEST_BYTES, label="manifest bundle"
            ),
            "manifest bundle",
        )
    )
    if _manifest_bytes(document) != manifest_raw:
        raise _error("manifest bundle is not canonical")
    rows = _bundle_capture_rows(document)
    capture_contracts: list[_BundleCaptureContract] = []
    for capture in rows:
        artifact_claims = _require_mapping(
            capture["artifacts"], "manifest capture artifacts"
        )
        png_claim, sidecar_claim = _validate_capture_record(
            artifact_claims,
            allow_supplemental=True,
        )
        supplemental_claims = _validate_supplemental_artifact_claims(
            artifact_claims.get("supplementalArtifacts", ())
        )
        # Persisted passed bundles are intentionally re-openable in another
        # process.  Validate canonical/hash/schema claims from descriptors,
        # without depending on this process's finalizer registry.
        png_contract = freeze_artifact_contract(
            root_fd,
            png_claim["path"],
            expected_owner=expected_owner,
            max_bytes=MAX_PNG_BYTES,
        )
        sidecar_contract = freeze_artifact_contract(
            root_fd,
            sidecar_claim["path"],
            expected_owner=expected_owner,
            max_bytes=MAX_RENDER_SIDECAR_BYTES,
        )
        supplemental_contracts = tuple(
            freeze_artifact_contract(
                root_fd,
                claim["path"],
                expected_owner=expected_owner,
                max_bytes=MAX_PNG_BYTES,
            )
            for claim in supplemental_claims
        )
        with ExitStack() as stack:
            png_artifact = stack.enter_context(
                open_authenticated_artifact(root_fd, png_contract)
            )
            sidecar_artifact = stack.enter_context(
                open_authenticated_artifact(root_fd, sidecar_contract)
            )
            supplemental_artifacts = tuple(
                stack.enter_context(
                    open_authenticated_artifact(root_fd, contract)
                )
                for contract in supplemental_contracts
            )
            png_raw, _png_sha, _png_stat = _hash_descriptor(
                png_artifact.descriptor, maximum=MAX_PNG_BYTES
            )
            sidecar_raw, _sidecar_sha, _sidecar_stat = _hash_descriptor(
                sidecar_artifact.descriptor, maximum=MAX_RENDER_SIDECAR_BYTES
            )
            supplemental_raw = tuple(
                _hash_descriptor(
                    artifact.descriptor,
                    maximum=MAX_PNG_BYTES,
                )[0]
                for artifact in supplemental_artifacts
            )
            _artifacts, sidecar_document = _validate_open_capture_bytes(
                png_raw,
                sidecar_raw,
                artifact_claims,
                supplemental_raw=supplemental_raw,
            )
            _require_manifest_capture_id(capture["id"], sidecar_document)
        capture_contracts.append(
            _BundleCaptureContract(
                capture_id=capture["id"],
                png=png_contract,
                render_sidecar=sidecar_contract,
                supplemental=supplemental_contracts,
            )
        )
    contract = ManifestBundleContract(
        manifest=manifest_contract,
        captures=tuple(capture_contracts),
        manifest_sha256=manifest_sha256,
    )
    with _MANIFEST_BUNDLES_LOCK:
        _MANIFEST_BUNDLES[id(contract)] = (contract, copy.deepcopy(document))
    return contract


def _validate_open_capture_bytes(
    png_raw: bytes,
    sidecar_raw: bytes,
    record: Mapping[str, object],
    *,
    supplemental_raw: Sequence[bytes] = (),
) -> tuple[dict[str, Any], dict[str, Any]]:
    record_row = _require_mapping(record, "manifest capture artifacts")
    png_claim, sidecar_claim = _validate_capture_record(
        record_row,
        allow_supplemental=True,
    )
    supplemental_claims = _validate_supplemental_artifact_claims(
        record_row.get("supplementalArtifacts", ())
    )
    png_sha256 = hashlib.sha256(png_raw).hexdigest()
    sidecar_sha256 = hashlib.sha256(sidecar_raw).hexdigest()
    if (
        png_sha256 != png_claim["sha256"]
        or len(png_raw) != png_claim["size"]
        or sidecar_sha256 != sidecar_claim["sha256"]
        or len(sidecar_raw) != sidecar_claim["size"]
    ):
        raise _error("manifest bundle artifact claims differ")
    dimensions = _png_dimensions(png_raw)
    if dimensions != (png_claim["width"], png_claim["height"]):
        raise _error("manifest bundle PNG dimensions differ")
    sidecar_document = dict(
        _require_finalized_render_sidecar(
            sidecar_raw, require_live_provenance=False
        )
    )
    sidecar_schema = sidecar_document.get("schemaVersion")
    if (
        sidecar_schema not in {RENDER_SCHEMA, RENDER_V2_SCHEMA}
        or sidecar_claim["schemaVersion"] != sidecar_schema
    ):
        raise _error("manifest render schema differs from its record")
    _require_png_matches_render_viewport(
        dimensions,
        sidecar_document,
        label="manifest bundle",
    )
    artifacts = {
        "png": {
            "path": png_claim["path"],
            "sha256": png_sha256,
            "size": len(png_raw),
            "width": dimensions[0],
            "height": dimensions[1],
        },
        "renderSidecar": {
            "path": sidecar_claim["path"],
            "sha256": sidecar_sha256,
            "size": len(sidecar_raw),
            "schemaVersion": sidecar_schema,
        },
    }
    identity = _require_mapping(sidecar_document["identity"], "manifest identity")
    is_theme = identity.get("case") == "theme-gallery"
    if bool(supplemental_claims) != is_theme or len(supplemental_raw) != len(
        supplemental_claims
    ):
        raise _error("manifest theme supplemental artifact set differs")
    if supplemental_claims:
        rich = validate_theme_worker_evidence(
            _require_mapping(
                sidecar_document["stableState"], "manifest theme stable state"
            ).get("themeEvidence"),
            expected_viewport=sidecar_document["viewport"],
        )
        surfaces = {row["name"]: row for row in rich["surfaces"]}
        materialized: list[dict[str, Any]] = []
        for claim, raw in zip(supplemental_claims, supplemental_raw):
            digest = hashlib.sha256(raw).hexdigest()
            source = claim["source"]
            surface = surfaces[claim["id"]]
            geometry = surface["geometry"]
            if (
                digest != claim["sha256"]
                or len(raw) != claim["size"]
                or _png_dimensions(raw) != (claim["width"], claim["height"])
                or source["parentPngSha256"] != png_sha256
                or source["themeEvidenceSha256"] != rich["sha256"]
                or source["crop"] != geometry["crop"]
                or source["cropSha256"] != digest
                or source["coordinateSpace"] != geometry["coordinateSpace"]
            ):
                raise _error("manifest supplemental artifact binding differs")
            _require_exact_png_crop(
                png_raw,
                raw,
                source["crop"],
                label=f"manifest supplemental {claim['id']}",
            )
            materialized.append(copy.deepcopy(claim))
        artifacts["supplementalArtifacts"] = materialized
    return artifacts, sidecar_document


def reauthenticate_manifest_bundle(
    root_fd: int,
    contract: ManifestBundleContract,
) -> AuthenticatedManifestBundle:
    """Reopen the frozen bundle and retain descriptors for one validation pass."""

    if not isinstance(contract, ManifestBundleContract):
        raise _error("manifest bundle contract has the wrong type")
    with _MANIFEST_BUNDLES_LOCK:
        registered = _MANIFEST_BUNDLES.get(id(contract))
    if registered is None or registered[0] is not contract:
        raise _error("manifest bundle contract lacks live provenance")
    frozen_document = registered[1]
    with ExitStack() as stack:
        manifest_artifact = stack.enter_context(
            open_authenticated_artifact(root_fd, contract.manifest)
        )
        manifest_raw, manifest_sha256, _manifest_stat = _hash_descriptor(
            manifest_artifact.descriptor, maximum=MAX_MANIFEST_BYTES
        )
        if manifest_sha256 != contract.manifest_sha256:
            raise _error("manifest bundle digest changed")
        document = dict(
            _require_mapping(
                _decode_json_bytes(
                    manifest_raw,
                    maximum=MAX_MANIFEST_BYTES,
                    label="manifest bundle",
                ),
                "manifest bundle",
            )
        )
        if document != frozen_document:
            raise _error("manifest bundle document changed")
        rows = _bundle_capture_rows(document)
        by_id = {capture.capture_id: capture for capture in contract.captures}
        if set(by_id) != {row["id"] for row in rows}:
            raise _error("manifest bundle capture set changed")
        authenticated_rows: list[dict[str, Any]] = []
        for row in rows:
            frozen = by_id[row["id"]]
            png_artifact = stack.enter_context(
                open_authenticated_artifact(root_fd, frozen.png)
            )
            sidecar_artifact = stack.enter_context(
                open_authenticated_artifact(root_fd, frozen.render_sidecar)
            )
            supplemental_artifacts = tuple(
                stack.enter_context(
                    open_authenticated_artifact(root_fd, contract)
                )
                for contract in frozen.supplemental
            )
            png_raw, _png_sha, _png_stat = _hash_descriptor(
                png_artifact.descriptor, maximum=MAX_PNG_BYTES
            )
            sidecar_raw, _sidecar_sha, _sidecar_stat = _hash_descriptor(
                sidecar_artifact.descriptor, maximum=MAX_RENDER_SIDECAR_BYTES
            )
            supplemental_raw = tuple(
                _hash_descriptor(
                    artifact.descriptor,
                    maximum=MAX_PNG_BYTES,
                )[0]
                for artifact in supplemental_artifacts
            )
            artifacts, sidecar_document = _validate_open_capture_bytes(
                png_raw,
                sidecar_raw,
                row["artifacts"],
                supplemental_raw=supplemental_raw,
            )
            _require_manifest_capture_id(row["id"], sidecar_document)
            authenticated_rows.append(
                {
                    "id": row["id"],
                    "status": "passed",
                    "artifacts": artifacts,
                    "renderDocument": sidecar_document,
                }
            )
    authenticated = AuthenticatedManifestBundle(
        manifest=copy.deepcopy(document),
        manifest_sha256=manifest_sha256,
        captures=tuple(authenticated_rows),
        _key=_OPAQUE_KEY,
    )
    payload = {
        "manifest": copy.deepcopy(document),
        "manifestSha256": manifest_sha256,
        "captures": authenticated_rows,
    }
    digest = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    with _AUTHENTICATED_MANIFEST_BUNDLES_LOCK:
        _AUTHENTICATED_MANIFEST_BUNDLES[id(authenticated)] = (
            authenticated,
            copy.deepcopy(payload),
            digest,
        )
    return authenticated


def _profile_rows_by_capture_id(
    fixture_entrypoint: str,
) -> dict[str, dict[str, Any]]:
    return {
        f'{row["case"]}/{row["viewport"]["name"]}': row
        for row in worker_capture_profile_rows(fixture_entrypoint)
    }


def _migration_document_from_authenticated_bundle(
    value: object,
    *,
    fixture_entrypoint: str,
    expected_mode: str,
    expected_phase: str | None = None,
    require_focused_v2: bool = False,
    label: str,
) -> dict[str, Any]:
    payload = _registered_manifest_bundle(value)
    manifest = _require_mapping(payload["manifest"], f"{label} manifest")
    if manifest.get("mode") != expected_mode:
        raise _error(f"{label} manifest mode differs")
    if expected_phase is not None and manifest.get("phase") != expected_phase:
        raise _error(f"{label} manifest phase differs")
    for key in ("captureStackDigest", "sourceDigestStart", "sourceDigestEnd"):
        if not _is_sha256(manifest.get(key)):
            raise _error(f"{label} manifest {key} is invalid")
    if manifest["sourceDigestStart"] != manifest["sourceDigestEnd"]:
        raise _error(f"{label} source digest is not closed")
    expected_rows = _profile_rows_by_capture_id(fixture_entrypoint)
    capture_rows = payload["captures"]
    if not isinstance(capture_rows, list):
        raise _error(f"{label} authenticated captures are invalid")
    by_id = {
        row.get("id"): row
        for row in capture_rows
        if isinstance(row, Mapping) and isinstance(row.get("id"), str)
    }
    if len(by_id) != len(capture_rows) or set(by_id) != set(expected_rows):
        raise _error(f"{label} does not cover its exact frozen capture profile")
    captures: list[dict[str, Any]] = []
    for capture_id in sorted(expected_rows):
        row = by_id[capture_id]
        if row.get("status") != "passed":
            raise _error(f"{label} contains a non-passing capture")
        sidecar = _require_mapping(
            row.get("renderDocument"), f"{label} render sidecar {capture_id}"
        )
        frozen = expected_rows[capture_id]
        identity = _require_mapping(
            sidecar.get("identity"), f"{label} render identity {capture_id}"
        )
        if dict(identity) != {
            "case": frozen["case"],
            "route": frozen["route"],
            "callable": frozen["callable"],
        } or sidecar.get("viewport") != frozen["viewport"]:
            raise _error(f"{label} render identity differs from the frozen catalog")
        observed_roots = [
            node.get("rootSelector")
            for node in sidecar.get("nodes", ())
            if isinstance(node, Mapping) and node.get("rootSelector") is not None
        ]
        if (
            len(observed_roots) != len(set(observed_roots))
            or set(observed_roots) != set(frozen["rootSelectors"])
        ):
            raise _error(f"{label} render roots differ from the frozen catalog")
        if sidecar.get("runtimeProjection") != {
            "sourceRoot": "$OWNED_ROOT_0",
            "browserScratchRoot": "$OWNED_ROOT_1",
        }:
            raise _error(f"{label} runtime roles differ")
        provenance = _require_mapping(
            sidecar.get("counterProvenance"),
            f"{label} counter provenance {capture_id}",
        )
        if (
            provenance.get("captureId") != capture_id
            or provenance.get("registryKey") != frozen["registryKey"]
        ):
            raise _error(f"{label} counter provenance differs")
        control_evidence: dict[str, Any] | None = None
        if fixture_entrypoint == "scripts/ui_ux_selection_fixture_app.py":
            phase = manifest.get("phase")
            expected_projection = {
                "precontrol": "legacy-segmented",
                "postcontrol": "accessible-required",
            }.get(phase)
            if expected_projection is None:
                raise _error(f"{label} focused manifest phase is unsupported")
            if "controlEvidence" not in sidecar:
                raise _error(f"{label} focused render lacks control evidence")
            control_evidence = _validate_focused_control_evidence(
                sidecar["controlEvidence"],
                expected_case=frozen["case"],
                expected_viewport=frozen["viewport"],
                require_screenshot_binding=require_focused_v2,
            )
            if control_evidence["projection"] != expected_projection:
                raise _error(f"{label} focused control phase projection differs")
        elif "controlEvidence" in sidecar:
            raise _error(f"{label} non-focused render contains control evidence")
        captures.append(
            {
                "id": capture_id,
                "case": frozen["case"],
                "viewport": copy.deepcopy(frozen["viewport"]),
                "identity": {
                    "route": frozen["route"],
                    "callable": frozen["callable"],
                },
                "providerCounters": copy.deepcopy(sidecar["providerCounters"]),
                "mutatorCounters": copy.deepcopy(sidecar["mutatorCounters"]),
                "stableState": copy.deepcopy(sidecar["stableState"]),
                "controlEvidence": copy.deepcopy(control_evidence),
                "render": {"nodes": copy.deepcopy(sidecar["nodes"])},
            }
        )
    return {
        "status": "passed",
        "mode": expected_mode,
        "captureStackDigest": manifest["captureStackDigest"],
        "sourceDigestStart": manifest["sourceDigestStart"],
        "sourceDigestEnd": manifest["sourceDigestEnd"],
        "captures": captures,
    }


def adapt_root_capture_bundle_for_legacy_migration(
    value: object,
    *,
    oracle_capture_stack_digest: str,
) -> tuple[AuthenticatedManifestBundle, dict[str, Any]]:
    """Adapt 44 authenticated root captures to 36 legacy semantic inputs.

    The returned bundle is an in-memory semantic adapter, not a second artifact
    publication.  Its render documents come only from the closed,
    descriptor-authenticated ``caseSemanticProjection`` embedded in each root
    sidecar.  Sibling projections must be byte-identical before one logical
    capture is minted for the frozen migration oracle.
    """

    if not _is_sha256(oracle_capture_stack_digest):
        raise _error("legacy migration oracle stack digest is invalid")
    payload = _registered_manifest_bundle(value)
    manifest = _require_mapping(
        payload["manifest"], "root migration manifest"
    )
    required_lifecycle = {
        "mode": "ux1b-selection-controls",
        "phase": "postcontrol",
        "fixtureEntrypoint": "scripts/ui_ux_selection_fixture_app.py",
        "status": "passed",
        "expectedCaptureCount": ROOT_CAPTURE_EXPANSION_ROWS,
        "plannedLogicalRequests": 36,
        "plannedRootCaptures": ROOT_CAPTURE_EXPANSION_ROWS,
        "completedLogicalRequests": 36,
        "completedRootCaptures": ROOT_CAPTURE_EXPANSION_ROWS,
        "capturedCount": ROOT_CAPTURE_EXPANSION_ROWS,
        "rootExpansionSha256": ROOT_CAPTURE_EXPANSION_SHA256,
    }
    if any(manifest.get(key) != expected for key, expected in required_lifecycle.items()):
        raise _error("root migration manifest lifecycle differs")
    for key in ("captureStackDigest", "sourceDigestStart", "sourceDigestEnd"):
        if not _is_sha256(manifest.get(key)):
            raise _error(f"root migration manifest {key} is invalid")
    if manifest["sourceDigestStart"] != manifest["sourceDigestEnd"]:
        raise _error("root migration manifest source digest is not closed")
    if manifest["captureStackDigest"] == oracle_capture_stack_digest:
        raise _error("root migration requires a distinct corrected stack")

    expected_rows = root_capture_expansion_rows()
    expected_by_root = {row["rootCaptureId"]: row for row in expected_rows}
    capture_rows = payload["captures"]
    if not isinstance(capture_rows, list):
        raise _error("root migration authenticated captures are invalid")
    by_root = {
        row.get("id"): row
        for row in capture_rows
        if isinstance(row, Mapping) and isinstance(row.get("id"), str)
    }
    if (
        len(by_root) != len(capture_rows)
        or set(by_root) != set(expected_by_root)
        or len(capture_rows) != ROOT_CAPTURE_EXPANSION_ROWS
    ):
        raise _error("root migration capture set differs from the frozen expansion")

    semantic_by_logical: dict[str, tuple[bytes, dict[str, Any]]] = {}
    root_audit_rows: list[dict[str, Any]] = []
    png_authorities: set[tuple[str, str, int]] = set()
    sidecar_authorities: set[tuple[str, str, int]] = set()
    counter_claims: dict[
        str, tuple[bytes, bytes, bytes]
    ] = {}
    for expected in expected_rows:
        root_capture_id = expected["rootCaptureId"]
        row = by_root[root_capture_id]
        if row.get("status") != "passed":
            raise _error("root migration contains a non-passing capture")
        artifacts = _require_mapping(
            row.get("artifacts"),
            f"root migration artifacts {root_capture_id}",
        )
        png = _require_mapping(
            artifacts.get("png"),
            f"root migration PNG {root_capture_id}",
        )
        sidecar_artifact = _require_mapping(
            artifacts.get("renderSidecar"),
            f"root migration sidecar {root_capture_id}",
        )
        for artifact, label, authorities in (
            (png, "PNG", png_authorities),
            (sidecar_artifact, "sidecar", sidecar_authorities),
        ):
            path = artifact.get("path")
            sha256 = artifact.get("sha256")
            size = artifact.get("size")
            authority = (path, sha256, size)
            if (
                not isinstance(path, str)
                or not path
                or not _is_sha256(sha256)
                or not _is_int(size)
                or size <= 0
                or authority in authorities
            ):
                raise _error(
                    f"root migration {label} authority is invalid or reused"
                )
            authorities.add(authority)
        viewport = expected["viewport"]
        if (
            png.get("width") != viewport["width"]
            or png.get("height") != viewport["height"]
        ):
            raise _error("root migration PNG dimensions differ from the catalog")

        sidecar = _require_mapping(
            row.get("renderDocument"),
            f"root migration render sidecar {root_capture_id}",
        )
        if sidecar.get("schemaVersion") != RENDER_V2_SCHEMA:
            raise _error("root migration sidecar schema differs")
        root_identity = _require_mapping(
            sidecar.get("rootCapture"),
            f"root migration capture identity {root_capture_id}",
        )
        if any(
            root_identity.get(key) != expected[key]
            for key in (
                "logicalCaptureId",
                "rootCaptureId",
                "rootOrdinal",
                "rootSelector",
            )
        ) or root_identity.get(
            "rootExpansionSha256"
        ) != ROOT_CAPTURE_EXPANSION_SHA256:
            raise _error("root migration capture identity differs")
        focused = _validate_focused_control_evidence(
            sidecar.get("controlEvidence"),
            expected_case=expected["case"],
            expected_viewport=viewport,
            require_screenshot_binding=True,
            expected_root_selector=expected["rootSelector"],
        )
        if (
            focused["schemaVersion"] != FOCUSED_CONTROL_EVIDENCE_V3_SCHEMA
            or focused["projection"] != "accessible-required"
            or len(focused["controls"]) != 1
            or focused["screenshotBinding"]["prePostExact"] is not True
        ):
            raise _error("root migration screenshot binding differs")
        _validate_focused_screenshot_binding_nodes(
            focused,
            sidecar.get("nodes", ()),
        )

        semantic = _require_mapping(
            sidecar.get("caseSemanticProjection"),
            f"root migration semantic projection {root_capture_id}",
        )
        semantic_raw = _canonical_json_bytes(semantic)
        logical_capture_id = expected["logicalCaptureId"]
        existing = semantic_by_logical.get(logical_capture_id)
        if existing is not None and existing[0] != semantic_raw:
            raise _error("root migration sibling semantic projections differ")
        semantic_by_logical.setdefault(
            logical_capture_id,
            (semantic_raw, copy.deepcopy(dict(semantic))),
        )
        counter_projection = (
            _canonical_json_bytes(sidecar.get("providerCounters")),
            _canonical_json_bytes(sidecar.get("mutatorCounters")),
            _canonical_json_bytes(sidecar.get("counterProvenance")),
        )
        prior_counter_projection = counter_claims.setdefault(
            logical_capture_id,
            counter_projection,
        )
        if prior_counter_projection != counter_projection:
            raise _error("root migration sibling counter projections differ")
        provenance = _require_mapping(
            sidecar.get("counterProvenance"),
            f"root migration counter provenance {root_capture_id}",
        )
        if provenance.get("captureId") != logical_capture_id:
            raise _error("root migration counter provenance is not logical")

        root_audit_rows.append(
            {
                "logicalCaptureId": logical_capture_id,
                "rootCaptureId": root_capture_id,
                "rootOrdinal": expected["rootOrdinal"],
                "rootSelector": expected["rootSelector"],
                "viewport": copy.deepcopy(viewport),
                "png": copy.deepcopy(dict(png)),
                "renderSidecar": copy.deepcopy(dict(sidecar_artifact)),
                "caseSemanticProjectionSha256": hashlib.sha256(
                    semantic_raw
                ).hexdigest(),
                "prePostExact": True,
            }
        )
    if (
        len(semantic_by_logical) != 36
        or len(counter_claims) != 36
        or len(root_audit_rows) != ROOT_CAPTURE_EXPANSION_ROWS
    ):
        raise _error("root migration logical/root cardinality differs")

    logical_rows: list[dict[str, Any]] = []
    for logical_capture_id in sorted(semantic_by_logical):
        semantic = semantic_by_logical[logical_capture_id][1]
        semantic_identity = _require_mapping(
            semantic.get("identity"),
            f"root migration semantic identity {logical_capture_id}",
        )
        if semantic_identity.get("logicalCaptureId") != logical_capture_id:
            raise _error("root migration semantic logical identity differs")
        render_document = {
            "schemaVersion": RENDER_SCHEMA,
            "identity": {
                "case": semantic_identity["case"],
                "route": semantic_identity["route"],
                "callable": semantic_identity["callable"],
            },
            "viewport": copy.deepcopy(semantic_identity["viewport"]),
            "readiness": copy.deepcopy(semantic["readiness"]),
            "nodes": copy.deepcopy(semantic["nodes"]),
            "stableState": copy.deepcopy(semantic["stableState"]),
            "providerCounters": copy.deepcopy(semantic["providerCounters"]),
            "mutatorCounters": copy.deepcopy(semantic["mutatorCounters"]),
            "runtimeProjection": copy.deepcopy(semantic["runtimeProjection"]),
            "counterProvenance": copy.deepcopy(
                semantic["counterProvenance"]
            ),
            "controlEvidence": copy.deepcopy(semantic["controlEvidence"]),
        }
        canonical_render = _decode_json_bytes(
            canonicalize_render_sidecar(render_document, owned_roots=()),
            maximum=MAX_RENDER_SIDECAR_BYTES,
            label="root migration adapted render",
        )
        representative = by_root[
            _root_capture_rows_for_logical(logical_capture_id)[0][
                "rootCaptureId"
            ]
        ]
        logical_rows.append(
            {
                "id": logical_capture_id,
                "status": "passed",
                "artifacts": copy.deepcopy(representative["artifacts"]),
                "renderDocument": canonical_render,
            }
        )

    adapted_manifest = copy.deepcopy(dict(manifest))
    adapted_manifest["captureStackDigest"] = oracle_capture_stack_digest
    adapted_manifest["expectedCaptureCount"] = 36
    adapted_manifest["capturedCount"] = 36
    adapted_manifest["captures"] = [
        {
            "id": row["id"],
            "status": "passed",
            "artifacts": copy.deepcopy(row["artifacts"]),
        }
        for row in logical_rows
    ]
    for key in (
        "plannedLogicalRequests",
        "plannedRootCaptures",
        "completedLogicalRequests",
        "completedRootCaptures",
        "rootExpansionSha256",
    ):
        adapted_manifest.pop(key, None)
    adapted_manifest_raw = _canonical_json_bytes(adapted_manifest)
    adapted = AuthenticatedManifestBundle(
        manifest=adapted_manifest,
        manifest_sha256=hashlib.sha256(adapted_manifest_raw).hexdigest(),
        captures=logical_rows,
        _key=_OPAQUE_KEY,
    )
    adapted_payload = {
        "manifest": copy.deepcopy(adapted_manifest),
        "manifestSha256": adapted.manifest_sha256,
        "captures": copy.deepcopy(logical_rows),
    }
    adapted_digest = hashlib.sha256(
        _canonical_json_bytes(adapted_payload)
    ).hexdigest()
    with _AUTHENTICATED_MANIFEST_BUNDLES_LOCK:
        _AUTHENTICATED_MANIFEST_BUNDLES[id(adapted)] = (
            adapted,
            adapted_payload,
            adapted_digest,
        )
    audit = {
        "status": "passed",
        "correctedCaptureStackDigest": manifest["captureStackDigest"],
        "sourceDigest": manifest["sourceDigestStart"],
        "logicalCaptureCount": len(logical_rows),
        "rootCaptureCount": len(root_audit_rows),
        "logicalCounterClaims": len(counter_claims),
        "rootExpansion": {
            "rows": ROOT_CAPTURE_EXPANSION_ROWS,
            "size": ROOT_CAPTURE_EXPANSION_SIZE,
            "sha256": ROOT_CAPTURE_EXPANSION_SHA256,
        },
        "passedRootCaptures": ROOT_CAPTURE_EXPANSION_ROWS,
        "unboundRootCaptures": 0,
        "exactPrePostProjections": ROOT_CAPTURE_EXPANSION_ROWS * 2,
        "roots": root_audit_rows,
    }
    return adapted, audit


def validate_baseline_evidence(
    bundle: AuthenticatedManifestBundle,
    *,
    fixture_entrypoint: str,
) -> dict[str, Any]:
    """Mint a comparator-grade report for an exact pre-control baseline."""

    expected_modes = {
        "scripts/ui_ux_fixture_app.py": "ux1b-full-pages",
        "scripts/ui_ux_selection_fixture_app.py": "ux1b-selection-controls",
        "scripts/ui_ux_theme_fixture_app.py": "ux1b-theme",
    }
    if fixture_entrypoint not in expected_modes:
        raise _error("baseline fixture profile is not frozen")
    document = _migration_document_from_authenticated_bundle(
        bundle,
        fixture_entrypoint=fixture_entrypoint,
        expected_mode=expected_modes[fixture_entrypoint],
        label="baseline",
    )
    _digest, captures = _migration_manifest(
        document,
        expected_mode=expected_modes[fixture_entrypoint],
        label="baseline",
    )
    bundle_payload = _registered_manifest_bundle(bundle)
    report = {
        "status": "passed",
        "kind": "baseline",
        "coveredProfiles": [fixture_entrypoint],
        "fixtureEntrypoint": fixture_entrypoint,
        "captureCount": len(captures),
        "captureStackDigest": document["captureStackDigest"],
        "sourceDigest": document["sourceDigestStart"],
        "manifestSha256": bundle_payload["manifestSha256"],
    }
    return _register_comparator_report(report, kind="baseline")


def validate_live_capture_profile(
    captures: Sequence[VerifiedCaptureArtifacts],
    *,
    fixture_entrypoint: str,
    capture_stack_digest: str,
) -> dict[str, Any]:
    """Register the exact live profile as the run's completeness comparator.

    This check runs before the terminal manifest exists.  A second,
    descriptor-reopened baseline verification is still required after the pass
    commit; this function only supplies the live comparator closure needed by
    the sole success finalizer.
    """

    if fixture_entrypoint not in _COUNTER_PROFILE_CAPTURE_IDS:
        raise _error("live capture fixture profile is not frozen")
    if not _is_sha256(capture_stack_digest):
        raise _error("live capture profile lacks a capture-stack digest")
    expected_ids = set(_COUNTER_PROFILE_CAPTURE_IDS[fixture_entrypoint])
    observed: list[str] = []
    artifact_digests: list[dict[str, Any]] = []
    for capture in tuple(captures):
        capture_id = _registered_capture_id(capture)
        payload = _registered_capture_payload(capture)
        observed.append(capture_id)
        artifact_digests.append(
            {
                "id": capture_id,
                "pngSha256": payload["png"]["sha256"],
                "renderSidecarSha256": payload["renderSidecar"]["sha256"],
                "supplementalSha256": [
                    row["sha256"]
                    for row in payload.get("supplementalArtifacts", ())
                ],
            }
        )
    observed_set = set(observed)
    is_root_profile = (
        fixture_entrypoint == "scripts/ui_ux_selection_fixture_app.py"
        and observed_set
        == {row["rootCaptureId"] for row in root_capture_expansion_rows()}
    )
    if (
        len(observed) != len(observed_set)
        or (
            not is_root_profile
            and observed_set != expected_ids
        )
    ):
        raise _error("live capture profile identity set differs")
    artifact_digests.sort(key=lambda row: row["id"])
    report = {
        "status": "passed",
        "kind": (
            "live-root-capture-profile"
            if is_root_profile
            else "live-capture-profile"
        ),
        "coveredProfiles": [fixture_entrypoint],
        "fixtureEntrypoint": fixture_entrypoint,
        "captureCount": len(observed),
        "captureStackDigest": capture_stack_digest,
        "artifactProjectionSha256": hashlib.sha256(
            _canonical_json_bytes(artifact_digests)
        ).hexdigest(),
    }
    if is_root_profile:
        report["logicalCaptureCount"] = len(expected_ids)
        report["rootExpansion"] = {
            "rows": ROOT_CAPTURE_EXPANSION_ROWS,
            "size": ROOT_CAPTURE_EXPANSION_SIZE,
            "sha256": ROOT_CAPTURE_EXPANSION_SHA256,
        }
    return _register_comparator_report(report, kind=report["kind"])


def _expected_catalog_cases(
    expected: Mapping[str, Sequence[tuple[str, str]]],
    *,
    label: str,
) -> dict[str, tuple[tuple[str, str], ...]]:
    result: dict[str, tuple[tuple[str, str], ...]] = {}
    for case, roots in expected.items():
        if not isinstance(case, str) or not case:
            raise _error(f"{label} contains an invalid case")
        normalized = tuple(roots)
        if (
            not normalized
            or any(
                not isinstance(item, tuple)
                or len(item) != 2
                or not all(isinstance(part, str) and part for part in item)
                for item in normalized
            )
            or len(set(normalized)) != len(normalized)
        ):
            raise _error(f"{label} case {case!r} has invalid expected roots")
        result[case] = normalized
    return result


def _frozen_control_catalog_roots(
    source: Mapping[str, Sequence[str]],
) -> dict[str, tuple[tuple[str, str], ...]]:
    result: dict[str, tuple[tuple[str, str], ...]] = {}
    for case, selectors in source.items():
        result[case] = tuple(
            (
                selector.removeprefix(".st-key-"),
                selector,
            )
            for selector in selectors
        )
    return result


_FROZEN_FOCUSED_CONTROL_CATALOG = _frozen_control_catalog_roots(
    _FOCUSED_ROOT_SELECTORS
)
_FROZEN_FULL_PAGE_CONTROL_CATALOG = _frozen_control_catalog_roots(
    _FULL_PAGE_ROOT_SELECTORS
)


def _validate_catalog_section(
    value: object,
    expected: Mapping[str, tuple[tuple[str, str], ...]],
    *,
    label: str,
) -> set[tuple[str, str]]:
    section = _require_mapping(value, label)
    if set(section) != set(expected):
        raise _error(f"{label} case set differs")
    observed_all: set[tuple[str, str]] = set()
    for case, expected_roots in expected.items():
        row = _require_mapping(section[case], f"{label}.{case}")
        _require_exact_keys(row, {"roots"}, f"{label}.{case}")
        roots = row["roots"]
        if not isinstance(roots, list) or len(roots) != len(expected_roots):
            raise _error(f"{label}.{case} root count differs")
        observed: list[tuple[str, str, str, str]] = []
        for index, raw_root in enumerate(roots):
            root = _require_mapping(raw_root, f"{label}.{case}.roots[{index}]")
            _require_exact_keys(
                root,
                {"sessionKey", "rootSelector", "flowScope", "boundaryId"},
                f"{label}.{case}.roots[{index}]",
            )
            if (
                not isinstance(root["sessionKey"], str)
                or not root["sessionKey"]
                or not isinstance(root["rootSelector"], str)
                or not root["rootSelector"].startswith(".st-key-")
                or not isinstance(root["flowScope"], str)
                or not root["flowScope"]
                or not isinstance(root["boundaryId"], str)
                or not root["boundaryId"]
            ):
                raise _error(f"{label}.{case} contains an invalid root")
            observed.append(
                (
                    root["sessionKey"],
                    root["rootSelector"],
                    root["flowScope"],
                    root["boundaryId"],
                )
            )
        observed_identities = tuple(
            (session, selector)
            for session, selector, _flow, _boundary in observed
        )
        if (
            observed_identities != expected_roots
            or len(set(observed)) != len(observed)
        ):
            raise _error(f"{label}.{case} roots differ")
        observed_all.update((session, selector) for session, selector, _flow, _boundary in observed)
    return observed_all


MAX_CONTROL_CATALOG_BYTES = 2 * 1024 * 1024


class AuthenticatedControlCatalog(Mapping[str, Any]):
    """Opaque catalog derived from, or reopened as, authenticated discovery."""

    __slots__ = ("_data",)

    def __init__(self, data: Mapping[str, Any], *, _key: object) -> None:
        if _key is not _OPAQUE_KEY:
            raise _error("control catalogs are minted internally")
        self._data = MappingProxyType(copy.deepcopy(dict(data)))

    def __getitem__(self, key: str) -> Any:
        return copy.deepcopy(self._data[key])

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __copy__(self) -> AuthenticatedControlCatalog:
        raise TypeError("authenticated control catalogs cannot be copied")

    def __deepcopy__(self, _memo: object) -> AuthenticatedControlCatalog:
        raise TypeError("authenticated control catalogs cannot be copied")


_AUTHENTICATED_CONTROL_CATALOGS: dict[
    int, tuple[AuthenticatedControlCatalog, dict[str, Any], str]
] = {}
_AUTHENTICATED_CONTROL_CATALOGS_LOCK = threading.Lock()


def control_catalog_digest(catalog: Mapping[str, object]) -> str:
    value = _require_mapping(catalog, "control catalog digest input")
    payload_keys = {
        "schemaVersion",
        "baseCaptureStackDigest",
        "viewports",
        "focusedCases",
        "fullPageCases",
    }
    if not payload_keys.issubset(value) or set(value) - (
        payload_keys | {"captureStackDigest"}
    ):
        raise _error("control catalog digest input keys differ")
    payload = {key: copy.deepcopy(value[key]) for key in payload_keys}
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _mint_control_catalog(document: Mapping[str, Any]) -> AuthenticatedControlCatalog:
    value = copy.deepcopy(dict(document))
    authenticated = AuthenticatedControlCatalog(value, _key=_OPAQUE_KEY)
    digest = hashlib.sha256(_canonical_json_bytes(value)).hexdigest()
    with _AUTHENTICATED_CONTROL_CATALOGS_LOCK:
        _AUTHENTICATED_CONTROL_CATALOGS[id(authenticated)] = (
            authenticated,
            copy.deepcopy(value),
            digest,
        )
    return authenticated


def _registered_control_catalog(value: object) -> dict[str, Any]:
    if not isinstance(value, AuthenticatedControlCatalog):
        raise _error("control catalog is not authenticated")
    with _AUTHENTICATED_CONTROL_CATALOGS_LOCK:
        registered = _AUTHENTICATED_CONTROL_CATALOGS.get(id(value))
    if registered is None or registered[0] is not value:
        raise _error("control catalog lacks live descriptor provenance")
    document = registered[1]
    if hashlib.sha256(_canonical_json_bytes(document)).hexdigest() != registered[2]:
        raise _error("authenticated control catalog registry changed")
    return copy.deepcopy(document)


def validate_control_catalog(
    catalog: Mapping[str, object],
    *,
    expected_focused_roots: Mapping[str, Sequence[tuple[str, str]]],
    expected_full_page_roots: Mapping[str, Sequence[tuple[str, str]]],
    expected_viewports: Sequence[tuple[str, int, int]],
    expected_base_capture_stack_digest: str,
) -> dict[str, int]:
    value = _require_mapping(catalog, "control catalog")
    _require_exact_keys(
        value,
        {
            "schemaVersion",
            "baseCaptureStackDigest",
            "captureStackDigest",
            "viewports",
            "focusedCases",
            "fullPageCases",
        },
        "control catalog",
    )
    if (
        value["schemaVersion"] != CONTROL_CATALOG_SCHEMA
        or not _is_sha256(expected_base_capture_stack_digest)
        or value["baseCaptureStackDigest"]
        != expected_base_capture_stack_digest
        or value["captureStackDigest"] != control_catalog_digest(value)
    ):
        raise _error("control catalog schema or stack digest is invalid")
    expected_viewport_rows = tuple(expected_viewports)
    if (
        not expected_viewport_rows
        or len(set(expected_viewport_rows)) != len(expected_viewport_rows)
    ):
        raise _error("expected control viewports are invalid")
    viewports = value["viewports"]
    if not isinstance(viewports, list) or len(viewports) != len(expected_viewport_rows):
        raise _error("control catalog viewport count differs")
    observed_viewports: list[tuple[str, int, int]] = []
    for index, raw_viewport in enumerate(viewports):
        viewport = _validate_viewport(
            raw_viewport, label=f"control catalog viewport {index}"
        )
        observed_viewports.append(
            (viewport["name"], viewport["width"], viewport["height"])
        )
    if tuple(observed_viewports) != expected_viewport_rows:
        raise _error("control catalog viewports differ")
    focused_expected = _expected_catalog_cases(
        expected_focused_roots, label="expected focused roots"
    )
    full_expected = _expected_catalog_cases(
        expected_full_page_roots, label="expected full-page roots"
    )
    focused_roots = _validate_catalog_section(
        value["focusedCases"], focused_expected, label="focusedCases"
    )
    full_roots = _validate_catalog_section(
        value["fullPageCases"], full_expected, label="fullPageCases"
    )
    return {
        "focusedCaseCount": len(focused_expected),
        "fullPageCaseCount": len(full_expected),
        "stableRootCount": len(focused_roots | full_roots),
        "viewportCount": len(expected_viewport_rows),
    }


def _expected_discovery_rows() -> dict[tuple[str, str, str], dict[str, Any]]:
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in _WORKER_IDENTITY_ROWS.values():
        entrypoint = row["fixtureEntrypoint"]
        if entrypoint == "scripts/ui_ux_fixture_app.py":
            if row["case"] not in _FULL_PAGE_ROOT_SELECTORS:
                continue
        elif entrypoint != "scripts/ui_ux_selection_fixture_app.py":
            continue
        key = (entrypoint, row["case"], row["viewport"]["name"])
        result[key] = row
    return result


def derive_control_catalog(
    discovery_sidecars: Sequence[AuthenticatedRawRenderSidecar],
    *,
    base_capture_stack_digest: str,
) -> AuthenticatedControlCatalog:
    """Derive the 57-row viewport-invariant control catalog."""

    if not _is_sha256(base_capture_stack_digest):
        raise _error("base capture-stack digest is invalid")
    expected = _expected_discovery_rows()
    observed: dict[tuple[str, str, str], dict[str, Any]] = {}
    invariants: dict[tuple[str, str, str], tuple[str, str]] = {}
    for raw_attestation in discovery_sidecars:
        payload = _registered_raw_sidecar_payload(raw_attestation)
        identity = payload["identityRow"]
        key = (
            identity["fixtureEntrypoint"],
            identity["case"],
            identity["viewport"]["name"],
        )
        if key not in expected or key in observed:
            raise _error("control discovery row set has an extra or duplicate row")
        document = payload["document"]
        by_selector = {
            node["rootSelector"]: node
            for node in document["nodes"]
            if node["rootSelector"] is not None
        }
        records: list[dict[str, str]] = []
        for selector in identity["rootSelectors"]:
            node = by_selector[selector]
            flow = node["flowScope"]
            boundary = node["boundaryId"]
            if not isinstance(flow, str) or not flow or not isinstance(boundary, str) or not boundary:
                raise _error("control discovery root lacks a flow or DOM boundary")
            invariant_key = (identity["fixtureEntrypoint"], identity["case"], selector)
            invariant = (flow, boundary)
            prior = invariants.setdefault(invariant_key, invariant)
            if prior != invariant:
                raise _error("control discovery tuple changes across viewports")
            records.append(
                {
                    "sessionKey": selector.removeprefix(".st-key-"),
                    "rootSelector": selector,
                    "flowScope": flow,
                    "boundaryId": boundary,
                }
            )
        observed[key] = {"roots": records}
    if set(observed) != set(expected):
        raise _error("control discovery does not cover exact 7x3 + 9x4 rows")

    def cases(
        entrypoint: str, source: Mapping[str, Sequence[str]]
    ) -> dict[str, Any]:
        return {
            case: copy.deepcopy(
                observed[(entrypoint, case, _STANDARD_VIEWPORTS[0][0])]
            )
            for case in source
        }

    document: dict[str, Any] = {
        "schemaVersion": CONTROL_CATALOG_SCHEMA,
        "baseCaptureStackDigest": base_capture_stack_digest,
        "captureStackDigest": "0" * 64,
        "viewports": [
            {"name": name, "width": width, "height": height}
            for name, width, height in _FOCUSED_VIEWPORTS
        ],
        "focusedCases": cases(
            "scripts/ui_ux_selection_fixture_app.py", _FOCUSED_ROOT_SELECTORS
        ),
        "fullPageCases": cases(
            "scripts/ui_ux_fixture_app.py", _FULL_PAGE_ROOT_SELECTORS
        ),
    }
    document["captureStackDigest"] = control_catalog_digest(document)
    validate_control_catalog(
        document,
        expected_focused_roots=_FROZEN_FOCUSED_CONTROL_CATALOG,
        expected_full_page_roots=_FROZEN_FULL_PAGE_CONTROL_CATALOG,
        expected_viewports=_FOCUSED_VIEWPORTS,
        expected_base_capture_stack_digest=base_capture_stack_digest,
    )
    return _mint_control_catalog(document)


def authenticate_control_catalog(
    root_fd: int,
    relative_path: str,
    *,
    expected_owner: int,
    expected_base_capture_stack_digest: str,
    expected_capture_stack_digest: str,
    expected_catalog_sha256: str,
) -> AuthenticatedControlCatalog:
    """Descriptor-authenticate a persisted discovery-derived catalog."""

    if not _is_sha256(expected_capture_stack_digest):
        raise _error("expected control-catalog aggregate digest is invalid")
    if not _is_sha256(expected_catalog_sha256):
        raise _error("expected control-catalog file digest is invalid")
    contract = freeze_artifact_contract(
        root_fd,
        relative_path,
        expected_owner=expected_owner,
        max_bytes=MAX_CONTROL_CATALOG_BYTES,
    )
    with open_authenticated_artifact(root_fd, contract) as artifact:
        raw, catalog_sha256, _observed = _hash_descriptor(
            artifact.descriptor, maximum=MAX_CONTROL_CATALOG_BYTES
        )
    if catalog_sha256 != expected_catalog_sha256:
        raise _error("control-catalog file digest differs from its external anchor")
    document = dict(
        _require_mapping(
            _decode_json_bytes(raw, maximum=MAX_CONTROL_CATALOG_BYTES, label="control catalog"),
            "control catalog",
        )
    )
    if _canonical_json_bytes(document) != raw:
        raise _error("control catalog is not canonical")
    if document.get("captureStackDigest") != expected_capture_stack_digest:
        raise _error("control-catalog aggregate differs from its external anchor")
    validate_control_catalog(
        document,
        expected_focused_roots=_FROZEN_FOCUSED_CONTROL_CATALOG,
        expected_full_page_roots=_FROZEN_FULL_PAGE_CONTROL_CATALOG,
        expected_viewports=_FOCUSED_VIEWPORTS,
        expected_base_capture_stack_digest=expected_base_capture_stack_digest,
    )
    return _mint_control_catalog(document)


def adapt_root_raw_sidecars_for_control_discovery(
    sidecars: Sequence[AuthenticatedRawRenderSidecar],
) -> tuple[AuthenticatedRawRenderSidecar, ...]:
    """Deduplicate 44 root sidecars into 36 logical discovery authorities."""

    rows = root_capture_expansion_rows()
    expected_by_root = {row["rootCaptureId"]: row for row in rows}
    by_root: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for sidecar in tuple(sidecars):
        payload = _registered_raw_sidecar_payload(sidecar)
        document = _require_mapping(
            payload.get("document"),
            "root discovery render document",
        )
        root_capture = _require_mapping(
            document.get("rootCapture"),
            "root discovery capture identity",
        )
        root_capture_id = root_capture.get("rootCaptureId")
        if (
            document.get("schemaVersion") != RENDER_V2_SCHEMA
            or not isinstance(root_capture_id, str)
            or root_capture_id not in expected_by_root
            or root_capture_id in by_root
        ):
            raise _error(
                "root discovery sidecar set has an extra or duplicate row"
            )
        expected = expected_by_root[root_capture_id]
        if any(
            root_capture.get(key) != expected[key]
            for key in (
                "logicalCaptureId",
                "rootCaptureId",
                "rootOrdinal",
                "rootSelector",
            )
        ) or root_capture.get(
            "rootExpansionSha256"
        ) != ROOT_CAPTURE_EXPANSION_SHA256:
            raise _error("root discovery capture identity differs")
        if (
            document.get("providerCounters") != {}
            or document.get("mutatorCounters") != {}
            or document.get("counterProvenance") is not None
        ):
            raise _error("root discovery sidecar contains finalized counters")
        by_root[root_capture_id] = (payload, dict(document))
    if set(by_root) != set(expected_by_root):
        raise _error("root discovery does not cover the frozen expansion")

    semantic_by_logical: dict[
        str, tuple[bytes, dict[str, Any], dict[str, Any]]
    ] = {}
    for expected in rows:
        payload, document = by_root[expected["rootCaptureId"]]
        semantic = _require_mapping(
            document.get("caseSemanticProjection"),
            "root discovery case semantic projection",
        )
        semantic_raw = _canonical_json_bytes(semantic)
        logical_capture_id = expected["logicalCaptureId"]
        prior = semantic_by_logical.get(logical_capture_id)
        if prior is not None and prior[0] != semantic_raw:
            raise _error(
                "root discovery sibling semantic projections differ"
            )
        semantic_by_logical.setdefault(
            logical_capture_id,
            (semantic_raw, copy.deepcopy(dict(semantic)), payload),
        )
    if len(semantic_by_logical) != 36:
        raise _error("root discovery logical cardinality differs")

    logical_sidecars: list[AuthenticatedRawRenderSidecar] = []
    for identity in worker_capture_profile_rows(
        "scripts/ui_ux_selection_fixture_app.py"
    ):
        logical_capture_id = (
            f'{identity["case"]}/{identity["viewport"]["name"]}'
        )
        semantic_raw, semantic, representative = (
            semantic_by_logical[logical_capture_id]
        )
        semantic_identity = _require_mapping(
            semantic.get("identity"),
            "root discovery semantic identity",
        )
        expected_identity = {
            "fixtureEntrypoint": identity["fixtureEntrypoint"],
            "logicalCaptureId": logical_capture_id,
            "case": identity["case"],
            "route": identity["route"],
            "callable": identity["callable"],
            "viewport": identity["viewport"],
        }
        if (
            dict(semantic_identity) != expected_identity
            or semantic.get("providerCounters") != {}
            or semantic.get("mutatorCounters") != {}
            or semantic.get("counterProvenance") is not None
        ):
            raise _error(
                "root discovery semantic identity or counters differ"
            )
        document = {
            "schemaVersion": RENDER_SCHEMA,
            "identity": {
                "case": identity["case"],
                "route": identity["route"],
                "callable": identity["callable"],
            },
            "viewport": copy.deepcopy(identity["viewport"]),
            "readiness": copy.deepcopy(semantic["readiness"]),
            "nodes": copy.deepcopy(semantic["nodes"]),
            "stableState": copy.deepcopy(semantic["stableState"]),
            "providerCounters": {},
            "mutatorCounters": {},
            "runtimeProjection": copy.deepcopy(
                semantic["runtimeProjection"]
            ),
            "controlEvidence": copy.deepcopy(
                semantic["controlEvidence"]
            ),
        }
        raw = canonicalize_worker_render_sidecar(
            document,
            owned_roots=(),
        )
        normalized = _require_mapping(
            _decode_json_bytes(
                raw,
                maximum=MAX_RENDER_SIDECAR_BYTES,
                label="root discovery semantic adapter",
            ),
            "root discovery semantic adapter",
        )
        adapter_payload = {
            "document": copy.deepcopy(dict(normalized)),
            "identityRow": copy.deepcopy(identity),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size": len(raw),
            "path": (
                str(representative["path"])
                + "#caseSemanticProjection"
            ),
            "rootProjectionSha256": hashlib.sha256(
                semantic_raw
            ).hexdigest(),
        }
        authenticated = AuthenticatedRawRenderSidecar(
            adapter_payload,
            _key=_OPAQUE_KEY,
        )
        with _AUTHENTICATED_RAW_SIDECARS_LOCK:
            _AUTHENTICATED_RAW_SIDECARS[id(authenticated)] = (
                authenticated,
                copy.deepcopy(adapter_payload),
            )
        logical_sidecars.append(authenticated)
    if len(logical_sidecars) != 36:
        raise _error("root discovery adapter cardinality differs")
    return tuple(logical_sidecars)


def _migration_nodes(value: object, *, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise _error(f"{label} must be a list")
    required = {
        "id",
        "parentId",
        "flowScope",
        "boundaryId",
        "rootSelector",
        "role",
        "name",
        "text",
        "state",
        "visible",
        "bounds",
    }
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw_node in enumerate(value):
        node = _require_mapping(raw_node, f"{label}[{index}]")
        _require_exact_keys(node, required, f"{label}[{index}]")
        for key in ("id", "flowScope", "role", "name", "text"):
            if not isinstance(node[key], str) or (key in {"id", "flowScope", "role"} and not node[key]):
                raise _error(f"{label}[{index}].{key} is invalid")
        if node["id"] in seen:
            raise _error(f"{label} node IDs are not unique")
        seen.add(node["id"])
        for key in ("parentId", "boundaryId", "rootSelector"):
            if node[key] is not None and not isinstance(node[key], str):
                raise _error(f"{label}[{index}].{key} is invalid")
        if not isinstance(node["visible"], bool):
            raise _error(f"{label}[{index}].visible is invalid")
        state_value = _require_mapping(node["state"], f"{label}[{index}].state")
        _validate_json_tree(state_value, label=f"{label}[{index}].state")
        bounds = _require_mapping(node["bounds"], f"{label}[{index}].bounds")
        _require_exact_keys(bounds, {"x", "y", "width", "height"}, f"{label}[{index}].bounds")
        if any(not _is_int(bounds[key]) for key in bounds):
            raise _error(f"{label}[{index}] bounds are not integers")
        if bounds["width"] < 0 or bounds["height"] < 0:
            raise _error(f"{label}[{index}] dimensions are negative")
        result.append(copy.deepcopy(dict(node)))
    for node in result:
        if node["parentId"] is not None and node["parentId"] not in seen:
            raise _error(f"{label} contains an unknown parentId")
        if node["boundaryId"] is not None and node["boundaryId"] not in seen:
            raise _error(f"{label} contains an unknown boundaryId")
    return result


def _migration_manifest(
    value: object, *, expected_mode: str, label: str
) -> tuple[str, dict[str, dict[str, Any]]]:
    document = _require_mapping(value, label)
    _require_exact_keys(
        document,
        {
            "status",
            "mode",
            "captureStackDigest",
            "sourceDigestStart",
            "sourceDigestEnd",
            "captures",
        },
        label,
    )
    if document["status"] != "passed" or document["mode"] != expected_mode:
        raise _error(f"{label} status or mode is invalid")
    digest = document["captureStackDigest"]
    if not _is_sha256(digest):
        raise _error(f"{label} capture stack digest is invalid")
    if (
        not _is_sha256(document["sourceDigestStart"])
        or document["sourceDigestStart"] != document["sourceDigestEnd"]
    ):
        raise _error(f"{label} source digest is not closed")
    captures = document["captures"]
    if not isinstance(captures, list) or not captures:
        raise _error(f"{label} captures are missing")
    result: dict[str, dict[str, Any]] = {}
    for index, raw_capture in enumerate(captures):
        capture = _require_mapping(raw_capture, f"{label}.captures[{index}]")
        _require_exact_keys(
            capture,
            {
                "id",
                "case",
                "viewport",
                "identity",
                "providerCounters",
                "mutatorCounters",
                "stableState",
                "controlEvidence",
                "render",
            },
            f"{label}.captures[{index}]",
        )
        if (
            not isinstance(capture["id"], str)
            or not capture["id"]
            or not isinstance(capture["case"], str)
            or not capture["case"]
            or capture["id"] in result
        ):
            raise _error(f"{label} capture identity is invalid")
        viewport = _validate_viewport(
            capture["viewport"], label=f"{label} capture viewport"
        )
        identity = _require_mapping(capture["identity"], f"{label} capture identity")
        _require_exact_keys(identity, {"route", "callable"}, f"{label} capture identity")
        if any(not isinstance(identity[key], str) or not identity[key] for key in identity):
            raise _error(f"{label} capture identity fields are invalid")
        providers = _validate_counters(
            capture["providerCounters"], label=f"{label} providerCounters"
        )
        mutators = _validate_counters(
            capture["mutatorCounters"], label=f"{label} mutatorCounters"
        )
        if any(mutators.values()):
            raise _error(f"{label} mutatorCounters are not all zero")
        stable = _require_mapping(capture["stableState"], f"{label} stableState")
        _validate_json_tree(stable, label=f"{label} stableState")
        control_evidence = capture["controlEvidence"]
        if control_evidence is not None:
            control_evidence = _validate_focused_control_evidence(
                control_evidence,
                expected_case=capture["case"],
                expected_viewport=viewport,
            )
        render = _require_mapping(capture["render"], f"{label} render")
        _require_exact_keys(render, {"nodes"}, f"{label} render")
        result[capture["id"]] = {
            "id": capture["id"],
            "case": capture["case"],
            "viewport": viewport,
            "identity": dict(identity),
            "providerCounters": providers,
            "mutatorCounters": mutators,
            "stableState": copy.deepcopy(dict(stable)),
            "controlEvidence": copy.deepcopy(control_evidence),
            "nodes": _migration_nodes(
                render["nodes"], label=f"{label} capture nodes"
            ),
        }
    return digest, result


def _catalog_roots_for_case(
    section: Mapping[str, Any], case: str, *, label: str
) -> list[dict[str, str]]:
    if case not in section:
        raise _error(f"{label} does not map case {case!r}")
    case_row = _require_mapping(section[case], f"{label}.{case}")
    _require_exact_keys(case_row, {"roots"}, f"{label}.{case}")
    roots = case_row["roots"]
    if not isinstance(roots, list) or not roots:
        raise _error(f"{label}.{case} roots are missing")
    result: list[dict[str, str]] = []
    selectors: set[str] = set()
    sessions: set[str] = set()
    for index, raw_root in enumerate(roots):
        root = _require_mapping(raw_root, f"{label}.{case}.roots[{index}]")
        _require_exact_keys(
            root,
            {"sessionKey", "rootSelector", "flowScope", "boundaryId"},
            f"{label}.{case}.roots[{index}]",
        )
        if any(not isinstance(root[key], str) or not root[key] for key in root):
            raise _error(f"{label}.{case} contains an invalid root")
        if root["rootSelector"] in selectors or root["sessionKey"] in sessions:
            raise _error(f"{label}.{case} contains duplicate roots")
        selectors.add(root["rootSelector"])
        sessions.add(root["sessionKey"])
        result.append(dict(root))
    return result


def _node_map(nodes: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {node["id"]: node for node in nodes}


def _descendant_owner(
    node: dict[str, Any],
    nodes: Mapping[str, dict[str, Any]],
    root_ids: set[str],
) -> str | None:
    parent = node["parentId"]
    visited: set[str] = set()
    while parent is not None:
        if parent in visited:
            raise _error("migration node ancestry contains a cycle")
        visited.add(parent)
        if parent in root_ids:
            return parent
        parent_node = nodes.get(parent)
        if parent_node is None:
            raise _error("migration node ancestry is incomplete")
        parent = parent_node["parentId"]
    return None


def _box_inside(inner: Mapping[str, int], outer: Mapping[str, int]) -> bool:
    return (
        inner["x"] >= outer["x"]
        and inner["y"] >= outer["y"]
        and inner["x"] + inner["width"] <= outer["x"] + outer["width"]
        and inner["y"] + inner["height"] <= outer["y"] + outer["height"]
    )


def _boxes_overlap(first: Mapping[str, int], second: Mapping[str, int]) -> bool:
    if not first["width"] or not first["height"] or not second["width"] or not second["height"]:
        return False
    return not (
        first["x"] + first["width"] <= second["x"]
        or second["x"] + second["width"] <= first["x"]
        or first["y"] + first["height"] <= second["y"]
        or second["y"] + second["height"] <= first["y"]
    )


def _project_stable_state_controls(
    stable_state: Mapping[str, Any], allowed_node_ids: set[str]
) -> dict[str, Any]:
    projected = copy.deepcopy(dict(stable_state))
    if "controls" not in projected:
        return projected
    controls = projected["controls"]
    if isinstance(controls, Mapping):
        projected["controls"] = {
            key: value
            for key, value in controls.items()
            if key not in allowed_node_ids
        }
    elif isinstance(controls, list):
        projected["controls"] = [
            value
            for value in controls
            if not (
                isinstance(value, Mapping)
                and isinstance(value.get("id"), str)
                and value["id"] in allowed_node_ids
            )
        ]
    return projected


def _box_horizontally_inside_viewport(
    box: Mapping[str, int], viewport_width: int
) -> bool:
    return box["x"] >= 0 and box["x"] + box["width"] <= viewport_width


def _node_is_ancestor(
    ancestor_id: str,
    descendant: Mapping[str, Any],
    nodes: Mapping[str, dict[str, Any]],
) -> bool:
    parent = descendant["parentId"]
    visited: set[str] = set()
    while parent is not None:
        if parent in visited:
            raise _error("migration node ancestry contains a cycle")
        visited.add(parent)
        if parent == ancestor_id:
            return True
        parent_node = nodes.get(parent)
        if parent_node is None:
            raise _error("migration node ancestry is incomplete")
        parent = parent_node["parentId"]
    return False


def _nearest_node_ancestor_in(
    descendant: Mapping[str, Any],
    nodes: Mapping[str, dict[str, Any]],
    candidate_ids: set[str],
) -> str | None:
    parent = descendant["parentId"]
    visited: set[str] = set()
    while parent is not None:
        if parent in visited:
            raise _error("migration node ancestry contains a cycle")
        visited.add(parent)
        if parent in candidate_ids:
            return parent
        parent_node = nodes.get(parent)
        if parent_node is None:
            raise _error("migration node ancestry is incomplete")
        parent = parent_node["parentId"]
    return None


def _assert_visible_ancestor_containment(
    node: Mapping[str, Any],
    nodes: Mapping[str, dict[str, Any]],
    *,
    label: str,
) -> None:
    if not node["visible"]:
        return
    parent = node["parentId"]
    visited: set[str] = {node["id"]}
    while parent is not None:
        if parent in visited:
            raise _error("migration node ancestry contains a cycle")
        visited.add(parent)
        ancestor = nodes.get(parent)
        if ancestor is None:
            raise _error("migration node ancestry is incomplete")
        if ancestor["visible"] and not _box_inside(
            node["bounds"], ancestor["bounds"]
        ):
            raise _error(f"{label} clips its visible ancestor")
        parent = ancestor["parentId"]


def _compare_capture_migration(
    before: dict[str, Any],
    after: dict[str, Any],
    roots: Sequence[dict[str, str]],
) -> list[dict[str, Any]]:
    for key in (
        "id",
        "case",
        "viewport",
        "identity",
        "providerCounters",
        "mutatorCounters",
    ):
        if before[key] != after[key]:
            raise _error(f"migration capture {before['id']!r} changed stable {key}")
    before_nodes = before["nodes"]
    after_nodes = after["nodes"]
    before_map = _node_map(before_nodes)
    after_map = _node_map(after_nodes)
    selectors = {root["rootSelector"] for root in roots}
    for nodes in (before_nodes, after_nodes):
        observed_selectors = [
            node["rootSelector"] for node in nodes if node["rootSelector"] is not None
        ]
        if set(observed_selectors) != selectors or len(observed_selectors) != len(selectors):
            raise _error("migration capture has unmapped or duplicate control roots")
    before_roots = {
        node["rootSelector"]: node
        for node in before_nodes
        if node["rootSelector"] is not None
    }
    after_roots = {
        node["rootSelector"]: node
        for node in after_nodes
        if node["rootSelector"] is not None
    }
    root_ids_before = {node["id"] for node in before_roots.values()}
    root_ids_after = {node["id"] for node in after_roots.values()}
    boundary_rows: dict[tuple[str, str], dict[str, Any]] = {}
    for root in roots:
        before_root = before_roots[root["rootSelector"]]
        after_root = after_roots[root["rootSelector"]]
        if (
            before_root["id"] != after_root["id"]
            or before_root["flowScope"] != root["flowScope"]
            or after_root["flowScope"] != root["flowScope"]
            or before_root["boundaryId"] != root["boundaryId"]
            or after_root["boundaryId"] != root["boundaryId"]
        ):
            raise _error("migration control root identity differs from catalog")
        boundary_key = (root["flowScope"], root["boundaryId"])
        before_boundary = before_map.get(root["boundaryId"])
        after_boundary = after_map.get(root["boundaryId"])
        if before_boundary is None or after_boundary is None:
            raise _error("migration shared boundary node is missing")
        if not _node_is_ancestor(
            root["boundaryId"], before_root, before_map
        ) or not _node_is_ancestor(root["boundaryId"], after_root, after_map):
            raise _error("migration catalog boundary is not a control-root ancestor")
        delta = after_boundary["bounds"]["height"] - before_boundary["bounds"]["height"]
        if delta < 0:
            raise _error("migration shared boundary shrank")
        prior = boundary_rows.get(boundary_key)
        if prior is not None and prior["deltaY"] != delta:
            raise _error("migration shared boundary delta is inconsistent")
        boundary_rows[boundary_key] = {
            "case": before["case"],
            "captureId": before["id"],
            "flowScope": root["flowScope"],
            "boundaryId": root["boundaryId"],
            "deltaY": delta,
            "before": before_boundary,
            "after": after_boundary,
        }
        for key in ("id", "parentId", "flowScope", "boundaryId", "rootSelector", "role", "name", "text", "state", "visible"):
            if before_boundary[key] != after_boundary[key]:
                raise _error("migration changed shared-boundary semantics")
        for key in ("x", "y", "width"):
            if before_boundary["bounds"][key] != after_boundary["bounds"][key]:
                raise _error("migration changed shared-boundary geometry")
        for key in ("id", "parentId", "flowScope", "boundaryId", "rootSelector", "name", "text", "visible"):
            if before_root[key] != after_root[key]:
                raise _error("migration changed stable control-root identity")
        for key in ("x", "y", "width"):
            if before_root["bounds"][key] != after_root["bounds"][key]:
                raise _error("migration changed control-root geometry")
        if after_root["bounds"]["height"] < before_root["bounds"]["height"]:
            raise _error("migration control root shrank")
        if not _box_inside(before_root["bounds"], before_boundary["bounds"]):
            raise _error("migration control root escaped its before boundary")
        if not _box_inside(after_root["bounds"], after_boundary["bounds"]):
            raise _error("migration control root escaped its after boundary")

    before_owners = {
        node["id"]: _descendant_owner(node, before_map, root_ids_before)
        for node in before_nodes
    }
    after_owners = {
        node["id"]: _descendant_owner(node, after_map, root_ids_after)
        for node in after_nodes
    }
    before_allowed_ids = root_ids_before | {
        node_id for node_id, owner in before_owners.items() if owner is not None
    }
    after_allowed_ids = root_ids_after | {
        node_id for node_id, owner in after_owners.items() if owner is not None
    }
    if _project_stable_state_controls(
        before["stableState"], before_allowed_ids
    ) != _project_stable_state_controls(after["stableState"], after_allowed_ids):
        raise _error("migration changed stable state outside allowed control subtrees")
    boundary_ids = {row["boundaryId"] for row in roots}
    ordinary_before = [
        node
        for node in before_nodes
        if before_owners[node["id"]] is None
        and node["id"] not in root_ids_before
        and node["id"] not in boundary_ids
    ]
    ordinary_after = [
        node
        for node in after_nodes
        if after_owners[node["id"]] is None
        and node["id"] not in root_ids_after
        and node["id"] not in boundary_ids
    ]
    if [node["id"] for node in ordinary_before] != [node["id"] for node in ordinary_after]:
        raise _error("migration changed stable DOM order")
    for before_node, after_node in zip(ordinary_before, ordinary_after, strict=True):
        for key in ("id", "parentId", "flowScope", "boundaryId", "rootSelector", "role", "name", "text", "state", "visible"):
            if before_node[key] != after_node[key]:
                raise _error("migration changed an unauthorized stable node")
        for key in ("x", "width", "height"):
            if before_node["bounds"][key] != after_node["bounds"][key]:
                raise _error("migration changed stable node geometry")
        expected_y = before_node["bounds"]["y"]
        for (_flow, boundary_id), boundary in boundary_rows.items():
            before_boundary = boundary["before"]
            if (
                not _node_is_ancestor(
                    boundary_id,
                    before_node,
                    before_map,
                )
                and before_node["bounds"]["y"]
                >= before_boundary["bounds"]["y"] + before_boundary["bounds"]["height"]
                and max(
                    before_node["bounds"]["x"],
                    before_boundary["bounds"]["x"],
                )
                < min(
                    before_node["bounds"]["x"]
                    + before_node["bounds"]["width"],
                    before_boundary["bounds"]["x"]
                    + before_boundary["bounds"]["width"],
                )
            ):
                expected_y += boundary["deltaY"]
        if after_node["bounds"]["y"] != expected_y:
            raise _error("migration stable-flow translation is unauthorized")

    for nodes, owners, node_map, roots_map, capture in (
        (before_nodes, before_owners, before_map, before_roots, before),
        (after_nodes, after_owners, after_map, after_roots, after),
    ):
        visible_roots = [node for node in roots_map.values() if node["visible"]]
        for root_node in visible_roots:
            bounds = root_node["bounds"]
            if not _box_horizontally_inside_viewport(
                bounds, capture["viewport"]["width"]
            ):
                raise _error("migration control root overflows viewport width")
        for index, root_node in enumerate(visible_roots):
            for other_root in visible_roots[index + 1 :]:
                if _boxes_overlap(root_node["bounds"], other_root["bounds"]):
                    raise _error("migration control roots overlap")
        visible_allowed: list[dict[str, Any]] = list(visible_roots)
        descendant_boxes: list[tuple[str, dict[str, Any]]] = []
        for node in nodes:
            owner = owners[node["id"]]
            if owner is None:
                continue
            root_node = node_map[owner]
            if (
                node["flowScope"] != root_node["flowScope"]
                or node["boundaryId"] != root_node["boundaryId"]
            ):
                raise _error("migration control descendant escaped its flow boundary")
            if node["visible"]:
                if not _box_inside(node["bounds"], root_node["bounds"]):
                    raise _error("migration control descendant clips its root")
                if not _box_horizontally_inside_viewport(
                    node["bounds"], capture["viewport"]["width"]
                ):
                    raise _error(
                        "migration control descendant overflows viewport width"
                    )
                descendant_boxes.append((owner, node))
                visible_allowed.append(node)
        for index, (owner, node) in enumerate(descendant_boxes):
            for other_owner, other_node in descendant_boxes[index + 1 :]:
                if owner != other_owner and _boxes_overlap(
                    node["bounds"], other_node["bounds"]
                ):
                    raise _error("migration control subtrees overlap")

        ordinary_nodes = [
            node
            for node in nodes
            if owners[node["id"]] is None
            and node["id"] not in {
                root_node["id"] for root_node in roots_map.values()
            }
            and node["id"] not in boundary_ids
        ]
        for boundary_id in boundary_ids:
            boundary = node_map[boundary_id]
            if boundary["visible"]:
                if not _box_horizontally_inside_viewport(
                    boundary["bounds"], capture["viewport"]["width"]
                ):
                    raise _error("migration shared boundary overflows viewport width")
                _assert_visible_ancestor_containment(
                    boundary,
                    node_map,
                    label="migration shared boundary",
                )
        for ordinary in ordinary_nodes:
            ordinary_boundary_id = ordinary["boundaryId"]
            if ordinary_boundary_id is not None and (
                ordinary_boundary_id not in node_map
                or not _node_is_ancestor(
                    ordinary_boundary_id,
                    ordinary,
                    node_map,
                )
            ):
                raise _error(
                    "migration ordinary node declares a non-ancestor boundary"
                )
            actual_boundary_id = _nearest_node_ancestor_in(
                ordinary,
                node_map,
                boundary_ids,
            )
            if actual_boundary_id is None:
                if ordinary_boundary_id in boundary_ids:
                    raise _error(
                        "migration ordinary node declares a non-ancestor boundary"
                    )
            elif ordinary_boundary_id != actual_boundary_id:
                raise _error(
                    "migration ordinary node omits or changes its actual boundary"
                )
            if not ordinary["visible"]:
                continue
            if actual_boundary_id is not None:
                boundary = node_map[actual_boundary_id]
                if not _box_inside(ordinary["bounds"], boundary["bounds"]):
                    raise _error("migration ordinary boundary node clips its boundary")
                if not _box_horizontally_inside_viewport(
                    ordinary["bounds"], capture["viewport"]["width"]
                ):
                    raise _error("migration ordinary boundary node overflows viewport width")
            for allowed in visible_allowed:
                ordinary_contains = _node_is_ancestor(
                    ordinary["id"], allowed, node_map
                )
                allowed_contains = _node_is_ancestor(
                    allowed["id"], ordinary, node_map
                )
                if ordinary_contains:
                    if not _box_inside(allowed["bounds"], ordinary["bounds"]):
                        raise _error("migration allowed subtree clips its stable ancestor")
                elif allowed_contains:
                    if not _box_inside(ordinary["bounds"], allowed["bounds"]):
                        raise _error("migration stable descendant clips its allowed ancestor")
                elif _boxes_overlap(ordinary["bounds"], allowed["bounds"]):
                    raise _error("migration allowed subtree overlaps a stable sibling")
    return [
        {key: value for key, value in row.items() if key not in {"before", "after"}}
        for row in boundary_rows.values()
    ]


def _validate_migration_profile(
    captures: Mapping[str, dict[str, Any]],
    *,
    fixture_entrypoint: str,
    label: str,
) -> None:
    expected = _profile_rows_by_capture_id(fixture_entrypoint)
    if set(captures) != set(expected):
        raise _error(f"{label} capture set differs from its frozen profile")
    for capture_id, frozen in expected.items():
        capture = captures[capture_id]
        if (
            capture["id"] != capture_id
            or capture["case"] != frozen["case"]
            or capture["viewport"] != frozen["viewport"]
            or capture["identity"]
            != {"route": frozen["route"], "callable": frozen["callable"]}
        ):
            raise _error(f"{label} capture identity differs from its frozen profile")


def compare_control_migration(
    *,
    before_pages: AuthenticatedManifestBundle,
    after_pages: AuthenticatedManifestBundle,
    before_controls: AuthenticatedManifestBundle,
    after_controls: AuthenticatedManifestBundle,
    catalog: AuthenticatedControlCatalog,
) -> dict[str, Any]:
    """Compare exact authenticated matrices around a control migration."""

    catalog_value = _registered_control_catalog(catalog)
    validate_control_catalog(
        catalog_value,
        expected_focused_roots=_FROZEN_FOCUSED_CONTROL_CATALOG,
        expected_full_page_roots=_FROZEN_FULL_PAGE_CONTROL_CATALOG,
        expected_viewports=_FOCUSED_VIEWPORTS,
        expected_base_capture_stack_digest=catalog_value[
            "baseCaptureStackDigest"
        ],
    )
    page_before_document = _migration_document_from_authenticated_bundle(
        before_pages,
        fixture_entrypoint="scripts/ui_ux_fixture_app.py",
        expected_mode="ux1b-full-pages",
        expected_phase="precontrol",
        label="before pages",
    )
    page_after_document = _migration_document_from_authenticated_bundle(
        after_pages,
        fixture_entrypoint="scripts/ui_ux_fixture_app.py",
        expected_mode="ux1b-full-pages",
        expected_phase="pretheme",
        label="after pages",
    )
    control_before_document = _migration_document_from_authenticated_bundle(
        before_controls,
        fixture_entrypoint="scripts/ui_ux_selection_fixture_app.py",
        expected_mode="ux1b-selection-controls",
        expected_phase="precontrol",
        label="before controls",
    )
    control_after_document = _migration_document_from_authenticated_bundle(
        after_controls,
        fixture_entrypoint="scripts/ui_ux_selection_fixture_app.py",
        expected_mode="ux1b-selection-controls",
        expected_phase="postcontrol",
        label="after controls",
    )
    page_before_digest, page_before = _migration_manifest(
        page_before_document,
        expected_mode="ux1b-full-pages",
        label="before pages",
    )
    page_after_digest, page_after = _migration_manifest(
        page_after_document,
        expected_mode="ux1b-full-pages",
        label="after pages",
    )
    control_before_digest, control_before = _migration_manifest(
        control_before_document,
        expected_mode="ux1b-selection-controls",
        label="before controls",
    )
    control_after_digest, control_after = _migration_manifest(
        control_after_document,
        expected_mode="ux1b-selection-controls",
        label="after controls",
    )
    _validate_migration_profile(
        page_before,
        fixture_entrypoint="scripts/ui_ux_fixture_app.py",
        label="before pages",
    )
    _validate_migration_profile(
        page_after,
        fixture_entrypoint="scripts/ui_ux_fixture_app.py",
        label="after pages",
    )
    _validate_migration_profile(
        control_before,
        fixture_entrypoint="scripts/ui_ux_selection_fixture_app.py",
        label="before controls",
    )
    _validate_migration_profile(
        control_after,
        fixture_entrypoint="scripts/ui_ux_selection_fixture_app.py",
        label="after controls",
    )
    digests = {
        catalog_value["captureStackDigest"],
        page_before_digest,
        page_after_digest,
        control_before_digest,
        control_after_digest,
    }
    if len(digests) != 1:
        raise _error("migration capture-stack digests differ")
    translations: list[dict[str, Any]] = []
    compared = 0
    for before_set, after_set, section_name, allow_unaffected in (
        (page_before, page_after, "fullPageCases", True),
        (control_before, control_after, "focusedCases", False),
    ):
        if set(before_set) != set(after_set):
            raise _error("migration capture ID set differs")
        section = _require_mapping(catalog_value[section_name], section_name)
        observed_cases = {capture["case"] for capture in before_set.values()}
        if allow_unaffected:
            if not set(section).issubset(observed_cases):
                raise _error("full-page catalog cases lack viewport coverage")
        elif set(section) != observed_cases:
            raise _error("focused catalog case set differs from captures")
        for capture_id, before_capture in before_set.items():
            after_capture = after_set[capture_id]
            if before_capture["case"] != after_capture["case"]:
                raise _error("migration capture case changed")
            case = before_capture["case"]
            if case not in section:
                if not allow_unaffected or before_capture != after_capture:
                    raise _error("migration changed an unaffected full-page capture")
            else:
                roots = _catalog_roots_for_case(section, case, label=section_name)
                translations.extend(
                    _compare_capture_migration(before_capture, after_capture, roots)
                )
            compared += 1
    report = {
        "status": "passed",
        "kind": "control-migration",
        "coveredProfiles": [
            "scripts/ui_ux_fixture_app.py",
            "scripts/ui_ux_selection_fixture_app.py",
        ],
        "comparedCaptures": compared,
        "captureStackDigest": next(iter(digests)),
        "allowedBoundaryTranslations": translations,
    }
    return _register_comparator_report(report, kind="control-migration")


def _capture_stack_records(
    paths: Sequence[str | os.PathLike[str]],
    *,
    root: str | os.PathLike[str] | None = None,
    root_fd: int | None = None,
) -> list[dict[str, Any]]:
    """Descriptor-authenticate and return the exact capture-stack members."""

    if (root is None) == (root_fd is None):
        raise _error("capture-stack requires exactly one root authority")
    if root_fd is not None and (not _is_int(root_fd) or root_fd < 0):
        raise _error("capture-stack root descriptor is invalid")
    frozen_root: os.stat_result | None = None
    if root_fd is None:
        root_path = Path(root)  # type: ignore[arg-type]
        if not root_path.is_absolute():
            raise _error("capture-stack root must be an absolute real directory")
        try:
            frozen_root = os.stat(root_path, follow_symlinks=False)
        except OSError as exc:
            raise _error("capture-stack root cannot be inspected safely", cause=exc)
        if not stat.S_ISDIR(frozen_root.st_mode):
            raise _error("capture-stack root must be an absolute real directory")
        try:
            authority_fd = os.open(
                root_path, os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC
            )
        except OSError as exc:
            raise _error("capture-stack root cannot be opened safely", cause=exc)
    else:
        try:
            authority_fd = os.dup(root_fd)
        except OSError as exc:
            raise _error("capture-stack root descriptor is invalid", cause=exc)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        opened_root = os.fstat(authority_fd)
        if not stat.S_ISDIR(opened_root.st_mode):
            raise _error("capture-stack root descriptor is not a directory")
        if frozen_root is not None and (
            frozen_root.st_dev,
            frozen_root.st_ino,
            frozen_root.st_uid,
            stat.S_IMODE(frozen_root.st_mode),
        ) != (
            opened_root.st_dev,
            opened_root.st_ino,
            opened_root.st_uid,
            stat.S_IMODE(opened_root.st_mode),
        ):
            raise _error("capture-stack root changed while opening")
        if stat.S_IMODE(opened_root.st_mode) & _CLI_UNSAFE_MODE_BITS:
            raise _error("capture-stack root is group/world writable")
        expected_owner = opened_root.st_uid
        normalized_paths: list[str] = []
        for raw_path in paths:
            relative = os.fspath(raw_path)
            components = _safe_relative_components(
                relative, label="capture-stack path"
            )
            normalized = "/".join(components)
            if normalized in seen:
                raise _error("capture-stack paths must be unique")
            seen.add(normalized)
            normalized_paths.append(normalized)

        contracts: list[ArtifactContract] = []
        frozen_components: dict[
            tuple[str, ...], tuple[int, int, int, int]
        ] = {}
        for normalized in normalized_paths:
            contract = freeze_artifact_contract(
                authority_fd,
                normalized,
                expected_owner=expected_owner,
                max_bytes=MAX_AUTHENTICATED_ARTIFACT_BYTES,
            )
            for component in (contract.root, *contract.parents):
                if component.mode & _CLI_UNSAFE_MODE_BITS:
                    raise _error("capture-stack directory is group/world writable")
            if contract.leaf.mode & _CLI_UNSAFE_MODE_BITS:
                raise _error("capture-stack member is group/world writable")
            prefix: tuple[str, ...] = ()
            for component in contract.parents:
                prefix = (*prefix, component.name)
                identity = (
                    component.device,
                    component.inode,
                    component.owner_uid,
                    component.mode,
                )
                prior = frozen_components.setdefault(prefix, identity)
                if prior != identity:
                    raise _error("capture-stack directory namespace changed while freezing")
            contracts.append(contract)

        for normalized, contract in zip(normalized_paths, contracts):
            with open_authenticated_artifact(authority_fd, contract) as artifact:
                first_raw, first_digest, first_stat = _hash_descriptor(
                    artifact.descriptor,
                    maximum=MAX_AUTHENTICATED_ARTIFACT_BYTES,
                )
                second_raw, second_digest, second_stat = _hash_descriptor(
                    artifact.descriptor,
                    maximum=MAX_AUTHENTICATED_ARTIFACT_BYTES,
                )
            if (
                first_digest != second_digest
                or first_raw != second_raw
                or (
                    first_stat.st_dev,
                    first_stat.st_ino,
                    first_stat.st_uid,
                    stat.S_IMODE(first_stat.st_mode),
                    first_stat.st_nlink,
                    first_stat.st_size,
                )
                != (
                    second_stat.st_dev,
                    second_stat.st_ino,
                    second_stat.st_uid,
                    stat.S_IMODE(second_stat.st_mode),
                    second_stat.st_nlink,
                    second_stat.st_size,
                )
            ):
                raise _error("capture-stack file changed while hashing")
            records.append(
                {
                    "path": normalized,
                    "size": len(first_raw),
                    "sha256": first_digest,
                    "mode": stat.S_IMODE(first_stat.st_mode),
                }
            )
        for contract in contracts:
            with open_authenticated_artifact(authority_fd, contract) as artifact:
                _raw, digest, _observed = _hash_descriptor(
                    artifact.descriptor,
                    maximum=MAX_AUTHENTICATED_ARTIFACT_BYTES,
                )
            if digest != contract.leaf.sha256:
                raise _error("capture-stack member changed during final reauthentication")
        closing_root = os.fstat(authority_fd)
        if (
            closing_root.st_dev,
            closing_root.st_ino,
            closing_root.st_uid,
            stat.S_IMODE(closing_root.st_mode),
        ) != (
            opened_root.st_dev,
            opened_root.st_ino,
            opened_root.st_uid,
            stat.S_IMODE(opened_root.st_mode),
        ):
            raise _error("capture-stack root identity changed")
    finally:
        os.close(authority_fd)
    if not records:
        raise _error("capture-stack path set cannot be empty")
    records.sort(key=lambda row: row["path"])
    return records


def capture_stack_digest(
    paths: Sequence[str | os.PathLike[str]],
    *,
    root: str | os.PathLike[str] | None = None,
    root_fd: int | None = None,
) -> str:
    """Hash an exact, root-relative capture implementation stack."""

    records = _capture_stack_records(paths, root=root, root_fd=root_fd)
    return hashlib.sha256(_canonical_json_bytes(records)).hexdigest()


def _require_exact_capture_stack_members(
    paths: Sequence[str | os.PathLike[str]],
) -> tuple[str, ...]:
    try:
        normalized = tuple(os.fspath(path) for path in paths)
    except TypeError as exc:
        raise _error("capture-stack member paths are invalid", cause=exc)
    if (
        any(not isinstance(path, str) for path in normalized)
        or len(normalized) != len(set(normalized))
        or tuple(sorted(normalized)) != _SORTED_CAPTURE_STACK_MEMBERS
    ):
        raise _error("capture-stack member set differs from the frozen contract")
    return normalized


def build_capture_stack_contract(
    paths: Sequence[str | os.PathLike[str]],
    *,
    root: str | os.PathLike[str] | None = None,
    root_fd: int | None = None,
    control_catalog: AuthenticatedControlCatalog,
    root_expansion_sha256: str | None = None,
) -> dict[str, Any]:
    """Bind exact implementation members to a real discovery-derived catalog."""

    catalog = _registered_control_catalog(control_catalog)
    exact_paths = _require_exact_capture_stack_members(paths)
    records = _capture_stack_records(exact_paths, root=root, root_fd=root_fd)
    base_digest = hashlib.sha256(_canonical_json_bytes(records)).hexdigest()
    if catalog.get("baseCaptureStackDigest") != base_digest:
        raise _error("control catalog does not bind the live capture-stack members")
    validate_control_catalog(
        catalog,
        expected_focused_roots=_FROZEN_FOCUSED_CONTROL_CATALOG,
        expected_full_page_roots=_FROZEN_FULL_PAGE_CONTROL_CATALOG,
        expected_viewports=_FOCUSED_VIEWPORTS,
        expected_base_capture_stack_digest=base_digest,
    )
    contract = {
        "schemaVersion": CAPTURE_STACK_SCHEMA,
        "members": records,
        "baseCaptureStackDigest": base_digest,
        "captureStackDigest": catalog["captureStackDigest"],
        "controlCatalog": catalog,
        "workerCatalog": worker_capture_catalog_summary(),
    }
    if root_expansion_sha256 is not None:
        if root_expansion_sha256 != ROOT_CAPTURE_EXPANSION_SHA256:
            raise _error("capture-stack root expansion digest differs")
        contract["rootExpansionSha256"] = root_expansion_sha256
    return contract


def validate_capture_stack_contract(
    document: Mapping[str, object],
    *,
    root: str | os.PathLike[str] | None = None,
    root_fd: int | None = None,
) -> dict[str, Any]:
    """Rehash every member and validate the nested discovery catalog."""

    value = _require_mapping(document, "capture-stack contract")
    expected_keys = {
        "schemaVersion",
        "members",
        "baseCaptureStackDigest",
        "captureStackDigest",
        "controlCatalog",
        "workerCatalog",
    }
    if "rootExpansionSha256" in value:
        expected_keys.add("rootExpansionSha256")
    _require_exact_keys(
        value,
        expected_keys,
        "capture-stack contract",
    )
    if value["schemaVersion"] != CAPTURE_STACK_SCHEMA:
        raise _error("capture-stack contract schema is unsupported")
    members = value["members"]
    if not isinstance(members, list) or not members:
        raise _error("capture-stack contract members are invalid")
    paths: list[str] = []
    for index, raw_member in enumerate(members):
        member = _require_mapping(raw_member, f"capture-stack member {index}")
        _require_exact_keys(
            member,
            {"path", "size", "sha256", "mode"},
            f"capture-stack member {index}",
        )
        _safe_relative_components(member["path"], label="capture-stack member path")
        if (
            not _is_int(member["size"])
            or member["size"] < 0
            or not _is_sha256(member["sha256"])
            or not _is_int(member["mode"])
            or member["mode"] < 0
        ):
            raise _error("capture-stack member metadata is invalid")
        paths.append(member["path"])
    if len(paths) != len(set(paths)) or paths != sorted(paths):
        raise _error("capture-stack member paths are duplicate or noncanonical")
    _require_exact_capture_stack_members(paths)
    observed = _capture_stack_records(paths, root=root, root_fd=root_fd)
    if observed != members:
        raise _error("capture-stack member bytes or metadata changed")
    base_digest = hashlib.sha256(_canonical_json_bytes(observed)).hexdigest()
    if value["baseCaptureStackDigest"] != base_digest:
        raise _error("capture-stack base digest differs")
    catalog = dict(_require_mapping(value["controlCatalog"], "control catalog"))
    if (
        catalog.get("baseCaptureStackDigest") != base_digest
        or value["captureStackDigest"] != catalog.get("captureStackDigest")
    ):
        raise _error("capture-stack control-catalog binding differs")
    validate_control_catalog(
        catalog,
        expected_focused_roots=_FROZEN_FOCUSED_CONTROL_CATALOG,
        expected_full_page_roots=_FROZEN_FULL_PAGE_CONTROL_CATALOG,
        expected_viewports=_FOCUSED_VIEWPORTS,
        expected_base_capture_stack_digest=base_digest,
    )
    if value["workerCatalog"] != worker_capture_catalog_summary():
        raise _error("capture-stack worker catalog differs")
    if (
        "rootExpansionSha256" in value
        and value["rootExpansionSha256"]
        != ROOT_CAPTURE_EXPANSION_SHA256
    ):
        raise _error("capture-stack root expansion digest differs")
    return copy.deepcopy(dict(value))


def publish_capture_stack_contract(
    output_dir_fd: int,
    output_name: str,
    document: Mapping[str, object],
    *,
    workspace_root: str | os.PathLike[str] | None = None,
    workspace_root_fd: int | None = None,
) -> dict[str, Any]:
    """Exclusively publish one already discovery-bound capture-stack contract."""

    value = validate_capture_stack_contract(
        document, root=workspace_root, root_fd=workspace_root_fd
    )
    raw = _canonical_json_bytes(value)

    def revalidate_before_link() -> None:
        closing = validate_capture_stack_contract(
            document, root=workspace_root, root_fd=workspace_root_fd
        )
        if _canonical_json_bytes(closing) != raw:
            raise _error("capture-stack contract changed before publication")

    _exclusive_publish_bytes_at(
        output_dir_fd,
        output_name,
        raw,
        before_link=revalidate_before_link,
    )
    return {
        "path": _safe_leaf_name(output_name, label="capture-stack output name"),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
        "captureStackDigest": value["captureStackDigest"],
    }


def _require_rotation_directory(
    directory_fd: int,
    *,
    expected_owner: int,
    label: str,
) -> os.stat_result:
    try:
        observed = os.fstat(directory_fd)
    except OSError as exc:
        raise _error(f"{label} descriptor is invalid", cause=exc)
    if (
        not stat.S_ISDIR(observed.st_mode)
        or observed.st_uid != expected_owner
        or stat.S_IMODE(observed.st_mode) & 0o022
    ):
        raise _error(f"{label} must be an owned non-writable directory")
    return observed


def _authenticate_rotation_archive(
    archive_dir_fd: int,
    archive_name: str,
    *,
    expected_owner: int,
    expected_raw: bytes,
    expected_sha256: str,
) -> ArtifactContract:
    contract = freeze_artifact_contract(
        archive_dir_fd,
        archive_name,
        expected_owner=expected_owner,
        max_bytes=MAX_CONTROL_CATALOG_BYTES,
    )
    if (
        contract.leaf.mode != 0o600
        or contract.leaf.link_count != 1
        or contract.leaf.sha256 != expected_sha256
        or contract.leaf.size != len(expected_raw)
    ):
        raise _error("superseded capture-stack archive metadata differs")
    with open_authenticated_artifact(archive_dir_fd, contract) as artifact:
        raw, sha256, observed = _hash_descriptor(
            artifact.descriptor,
            maximum=MAX_CONTROL_CATALOG_BYTES,
        )
    if (
        raw != expected_raw
        or sha256 != expected_sha256
        or not _leaf_matches(observed, contract.leaf)
    ):
        raise _error("superseded capture-stack archive bytes differ")
    return contract


def _ensure_rotation_archive(
    archive_dir_fd: int,
    archive_name: str,
    *,
    expected_owner: int,
    expected_raw: bytes,
    expected_sha256: str,
) -> ArtifactContract:
    try:
        os.stat(archive_name, dir_fd=archive_dir_fd, follow_symlinks=False)
    except FileNotFoundError:
        _exclusive_publish_bytes_at(
            archive_dir_fd,
            archive_name,
            expected_raw,
        )
    except OSError as exc:
        raise _error("superseded capture-stack archive cannot be inspected", cause=exc)
    contract = _authenticate_rotation_archive(
        archive_dir_fd,
        archive_name,
        expected_owner=expected_owner,
        expected_raw=expected_raw,
        expected_sha256=expected_sha256,
    )
    try:
        os.fsync(archive_dir_fd)
    except OSError as exc:
        raise _error(
            "superseded capture-stack archive directory durability is unconfirmed",
            cause=exc,
        )
    return contract


def rotate_capture_stack_contract(
    output_dir_fd: int,
    output_name: str,
    document: Mapping[str, object],
    *,
    expected_existing_contract: ArtifactContract,
    expected_existing_sha256: str,
    archive_dir_fd: int,
    archive_name: str,
    workspace_root: str | os.PathLike[str] | None = None,
    workspace_root_fd: int | None = None,
) -> dict[str, Any]:
    """CAS-rotate one contract while preserving an exact immutable old copy."""

    leaf = _safe_leaf_name(output_name, label="capture-stack output name")
    archive_leaf = _safe_leaf_name(
        archive_name, label="superseded capture-stack archive name"
    )
    if (
        not isinstance(expected_existing_contract, ArtifactContract)
        or not _is_sha256(expected_existing_sha256)
        or expected_existing_contract.relative_path != leaf
        or expected_existing_contract.parents
        or expected_existing_contract.leaf.name != leaf
        or expected_existing_contract.leaf.sha256 != expected_existing_sha256
        or expected_existing_contract.leaf.link_count != 1
        or expected_existing_contract.leaf.mode & 0o022
        or archive_leaf
        != f"superseded-capture-stack-{expected_existing_sha256}.json"
    ):
        raise _error("capture-stack rotation authority is invalid")

    expected_owner = expected_existing_contract.leaf.owner_uid
    output_observed = _require_rotation_directory(
        output_dir_fd,
        expected_owner=expected_owner,
        label="capture-stack canonical directory",
    )
    archive_observed = _require_rotation_directory(
        archive_dir_fd,
        expected_owner=expected_owner,
        label="capture-stack archive directory",
    )
    if output_observed.st_dev != archive_observed.st_dev:
        raise _error("capture-stack canonical and archive directories differ by device")

    value = validate_capture_stack_contract(
        document,
        root=workspace_root,
        root_fd=workspace_root_fd,
    )
    raw = _canonical_json_bytes(value)
    if len(raw) > MAX_CONTROL_CATALOG_BYTES:
        raise _error("capture-stack contract exceeds its byte bound")
    new_sha256 = hashlib.sha256(raw).hexdigest()

    lock_fd = -1
    temporary_fd = -1
    temporary = f".{leaf}.{secrets.token_hex(12)}.rotate.tmp"
    replaced = False
    try:
        try:
            lock_fd = os.open(
                ".",
                os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC,
                dir_fd=output_dir_fd,
            )
            locked_observed = os.fstat(lock_fd)
            if (
                locked_observed.st_dev,
                locked_observed.st_ino,
                locked_observed.st_uid,
                stat.S_IMODE(locked_observed.st_mode),
            ) != (
                output_observed.st_dev,
                output_observed.st_ino,
                output_observed.st_uid,
                stat.S_IMODE(output_observed.st_mode),
            ):
                raise _error("capture-stack canonical lock directory changed")
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise _error("capture-stack rotation lock is busy or unavailable", cause=exc)

        with open_authenticated_artifact(
            output_dir_fd, expected_existing_contract
        ) as old_artifact:
            old_raw, old_sha256, old_observed = _hash_descriptor(
                old_artifact.descriptor,
                maximum=MAX_CONTROL_CATALOG_BYTES,
            )
            if (
                old_sha256 != expected_existing_sha256
                or not _leaf_matches(
                    old_observed, expected_existing_contract.leaf
                )
            ):
                raise _error("capture-stack canonical CAS precondition differs")

            archive_contract = _ensure_rotation_archive(
                archive_dir_fd,
                archive_leaf,
                expected_owner=expected_owner,
                expected_raw=old_raw,
                expected_sha256=expected_existing_sha256,
            )

            try:
                temporary_fd = os.open(
                    temporary,
                    os.O_RDWR
                    | os.O_CREAT
                    | os.O_EXCL
                    | _O_NOFOLLOW
                    | _O_CLOEXEC,
                    0o600,
                    dir_fd=output_dir_fd,
                )
                _write_all(temporary_fd, raw)
                os.fsync(temporary_fd)
                staged_raw, staged_sha256, staged_observed = _hash_descriptor(
                    temporary_fd,
                    maximum=MAX_CONTROL_CATALOG_BYTES,
                )
            except OSError as exc:
                raise _error("capture-stack replacement could not be staged", cause=exc)
            if (
                staged_raw != raw
                or staged_sha256 != new_sha256
                or not stat.S_ISREG(staged_observed.st_mode)
                or staged_observed.st_uid != expected_owner
                or stat.S_IMODE(staged_observed.st_mode) != 0o600
                or staged_observed.st_nlink != 1
            ):
                raise _error("capture-stack staged replacement differs")

            closing = validate_capture_stack_contract(
                document,
                root=workspace_root,
                root_fd=workspace_root_fd,
            )
            if _canonical_json_bytes(closing) != raw:
                raise _error("capture-stack contract changed before rotation")

            closing_old_raw, closing_old_sha256, closing_old_observed = (
                _hash_descriptor(
                    old_artifact.descriptor,
                    maximum=MAX_CONTROL_CATALOG_BYTES,
                )
            )
            if (
                closing_old_raw != old_raw
                or closing_old_sha256 != expected_existing_sha256
                or not _leaf_matches(
                    closing_old_observed, expected_existing_contract.leaf
                )
            ):
                raise _error("capture-stack canonical changed before rotation")
            with open_authenticated_artifact(
                output_dir_fd, expected_existing_contract
            ):
                pass
            _authenticate_rotation_archive(
                archive_dir_fd,
                archive_leaf,
                expected_owner=expected_owner,
                expected_raw=old_raw,
                expected_sha256=expected_existing_sha256,
            )

            try:
                os.replace(
                    temporary,
                    leaf,
                    src_dir_fd=output_dir_fd,
                    dst_dir_fd=output_dir_fd,
                )
                replaced = True
                temporary = ""
                os.fsync(output_dir_fd)
            except OSError as exc:
                if replaced:
                    error = ManifestDurabilityUncertain(
                        "capture-stack rotation committed but directory durability is uncertain"
                    )
                    error.__cause__ = exc
                    raise error
                try:
                    with open_authenticated_artifact(
                        output_dir_fd, expected_existing_contract
                    ):
                        pass
                except BaseException as probe_error:
                    error = ManifestDurabilityUncertain(
                        "capture-stack canonical replacement outcome is uncertain"
                    )
                    error.add_note(
                        "old canonical probe failed after replace error: "
                        f"{type(probe_error).__name__}: {probe_error}"
                    )
                    error.__cause__ = exc
                    raise error
                raise _error("capture-stack canonical replacement failed", cause=exc)

            authenticated, _catalog, authenticated_sha256 = (
                authenticate_capture_stack_contract(
                    output_dir_fd,
                    leaf,
                    workspace_root=workspace_root,
                    workspace_root_fd=workspace_root_fd,
                    expected_owner=expected_owner,
                    expected_sha256=new_sha256,
                )
            )
            _authenticate_rotation_archive(
                archive_dir_fd,
                archive_leaf,
                expected_owner=expected_owner,
                expected_raw=old_raw,
                expected_sha256=expected_existing_sha256,
            )
            if authenticated != value or authenticated_sha256 != new_sha256:
                raise _error("rotated capture-stack contract differs on reopen")

        return {
            "path": leaf,
            "sha256": new_sha256,
            "size": len(raw),
            "captureStackDigest": value["captureStackDigest"],
            "previousSha256": expected_existing_sha256,
            "archiveName": archive_leaf,
            "archiveSha256": archive_contract.leaf.sha256,
            "archiveSize": archive_contract.leaf.size,
        }
    except ManifestDurabilityUncertain:
        raise
    except BaseException as exc:
        if replaced:
            error = ManifestDurabilityUncertain(
                "capture-stack rotation committed but reopen is uncertain"
            )
            error.__cause__ = exc
            raise error
        raise
    finally:
        if temporary_fd >= 0:
            try:
                os.close(temporary_fd)
            except OSError:
                pass
        if temporary:
            try:
                os.unlink(temporary, dir_fd=output_dir_fd)
            except FileNotFoundError:
                pass
            except OSError:
                pass
        if lock_fd >= 0:
            try:
                os.close(lock_fd)
            except OSError:
                pass


def authenticate_capture_stack_contract(
    contract_root_fd: int,
    relative_path: str,
    *,
    workspace_root: str | os.PathLike[str] | None = None,
    workspace_root_fd: int | None = None,
    expected_owner: int,
    expected_sha256: str | None = None,
) -> tuple[dict[str, Any], AuthenticatedControlCatalog, str]:
    """Descriptor-authenticate a persisted stack contract and its live members."""

    if expected_sha256 is not None and not _is_sha256(expected_sha256):
        raise _error("expected capture-stack contract digest is invalid")
    contract = freeze_artifact_contract(
        contract_root_fd,
        relative_path,
        expected_owner=expected_owner,
        max_bytes=MAX_CONTROL_CATALOG_BYTES,
    )
    for component in (contract.root, *contract.parents):
        if component.mode & _CLI_UNSAFE_MODE_BITS:
            raise _error("capture-stack contract directory is group/world writable")
    if contract.leaf.mode & _CLI_UNSAFE_MODE_BITS:
        raise _error("capture-stack contract leaf is group/world writable")
    with open_authenticated_artifact(contract_root_fd, contract) as artifact:
        raw, sha256, _observed = _hash_descriptor(
            artifact.descriptor,
            maximum=MAX_CONTROL_CATALOG_BYTES,
        )
    if expected_sha256 is not None and sha256 != expected_sha256:
        raise _error("capture-stack contract file digest differs")
    value = dict(
        _require_mapping(
            _decode_json_bytes(
                raw,
                maximum=MAX_CONTROL_CATALOG_BYTES,
                label="capture-stack contract",
            ),
            "capture-stack contract",
        )
    )
    if _canonical_json_bytes(value) != raw:
        raise _error("capture-stack contract is not canonical")
    validated = validate_capture_stack_contract(
        value, root=workspace_root, root_fd=workspace_root_fd
    )
    with open_authenticated_artifact(contract_root_fd, contract) as artifact:
        closing_raw, closing_sha256, _closing_observed = _hash_descriptor(
            artifact.descriptor,
            maximum=MAX_CONTROL_CATALOG_BYTES,
        )
    if closing_raw != raw or closing_sha256 != sha256:
        raise _error("capture-stack contract changed during member validation")
    catalog = _mint_control_catalog(
        _require_mapping(validated["controlCatalog"], "control catalog")
    )
    return validated, catalog, sha256


def build_browser_worker_command(
    python_executable: str | os.PathLike[str],
    worker_path: str | os.PathLike[str],
    *,
    expected_origin: str,
    expected_request_id: str,
    allowed_staging_paths: Sequence[str],
    browser_executable: str | os.PathLike[str] | None = None,
    timeout_ms: int = 30_000,
) -> tuple[str, ...]:
    """Build the common external-worker command with strict relative paths."""

    python_value = os.fspath(python_executable)
    worker_value = os.fspath(worker_path)
    if not os.path.isabs(python_value) or not python_value:
        raise _error("worker Python executable must be absolute")
    if worker_value != "scripts/ui_ux_browser_worker.py":
        raise _error("browser worker path is not the frozen relative entrypoint")
    _safe_relative_components(worker_value, label="browser worker path")
    _validate_loopback_origin(expected_origin, expected=expected_origin)
    request_components = _safe_relative_components(
        expected_request_id, label="worker request ID"
    )
    if len(request_components) != 2:
        raise _error("worker request ID must be case/viewport")
    if not _is_int(timeout_ms) or not 1_000 <= timeout_ms <= 90_000:
        raise _error("worker timeout is outside the fixed range")
    staging = tuple(allowed_staging_paths)
    if len(staging) not in {2, 4} or len(set(staging)) != len(staging):
        raise _error("worker command requires one or two root artifact pairs")
    for path in staging:
        _safe_relative_components(path, label="worker staging path")
    command: list[str] = [
        python_value,
        worker_value,
        "--expected-origin",
        expected_origin,
        "--expected-request-id",
        expected_request_id,
    ]
    for path in sorted(staging):
        command.extend(("--allow-staging-path", path))
    if browser_executable is not None:
        browser_value = os.fspath(browser_executable)
        if not os.path.isabs(browser_value):
            raise _error("browser executable must be absolute")
        command.extend(("--browser-executable", browser_value))
    command.extend(("--timeout-ms", str(timeout_ms)))
    return tuple(command)


_DEFAULT_WORKSPACE_ROOT = Path(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
)
_DEFAULT_CAPTURE_STACK_CONTRACT = Path(
    "docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json"
)
_PRECHANGE_SCHEMA = "quant-radar-ui-ux-ux1b-recovery-prechange/v1"
_BUNDLE_SCHEMA = "quant-radar-ui-ux-ux1b-recovery-bundle/v1"
_CLI_UNSAFE_MODE_BITS = 0o022


@dataclass(frozen=True, slots=True)
class _CliArtifactBinding:
    contract: ArtifactContract
    owner_gid: int


def _workspace_relative_path(value: Path, *, label: str) -> str:
    try:
        raw = os.fspath(value)
    except TypeError as exc:
        raise _error(f"{label} is not a path", cause=exc)
    if not isinstance(raw, str) or os.path.isabs(raw):
        raise _error(f"{label} must be workspace-relative")
    components = _safe_relative_components(raw, label=label)
    return "/".join(components)


def _require_cli_safe_contract(contract: ArtifactContract, *, label: str) -> None:
    for component in (contract.root, *contract.parents):
        if component.mode & _CLI_UNSAFE_MODE_BITS:
            raise _error(f"{label} directory {component.name!r} is group/world writable")
    if contract.leaf.mode & _CLI_UNSAFE_MODE_BITS:
        raise _error(f"{label} leaf is group/world writable")


@contextmanager
def _cli_workspace_descriptor() -> Iterator[int]:
    root_path = os.fspath(_DEFAULT_WORKSPACE_ROOT)
    if not os.path.isabs(root_path):
        raise _error("workspace root must be absolute")
    try:
        descriptor = os.open(
            root_path,
            os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC,
        )
    except OSError as exc:
        raise _error("workspace root cannot be opened safely", cause=exc)
    try:
        observed = os.fstat(descriptor)
        contract = _directory_contract(
            ".", observed, expected_owner=os.getuid()
        )
        if contract.mode & _CLI_UNSAFE_MODE_BITS:
            raise _error("workspace root is group/world writable")
        yield descriptor
    finally:
        os.close(descriptor)


def _read_cli_artifact(
    workspace_fd: int,
    relative_path: str,
    *,
    label: str,
    maximum: int,
    expected_sha256: str | None = None,
) -> tuple[bytes, str, os.stat_result, _CliArtifactBinding]:
    if expected_sha256 is not None and not _is_sha256(expected_sha256):
        raise _error(f"{label} expected digest is invalid")
    contract = freeze_artifact_contract(
        workspace_fd,
        relative_path,
        expected_owner=os.getuid(),
        max_bytes=maximum,
    )
    _require_cli_safe_contract(contract, label=label)
    with open_authenticated_artifact(workspace_fd, contract) as artifact:
        raw, digest, observed = _hash_descriptor(
            artifact.descriptor, maximum=maximum
        )
    if expected_sha256 is not None and digest != expected_sha256:
        raise _error(f"{label} digest differs")
    return raw, digest, observed, _CliArtifactBinding(contract, observed.st_gid)


def _reauthenticate_cli_bindings(
    workspace_fd: int, bindings: Sequence[_CliArtifactBinding]
) -> None:
    for binding in bindings:
        with open_authenticated_artifact(workspace_fd, binding.contract) as artifact:
            _raw, digest, observed = _hash_descriptor(
                artifact.descriptor, maximum=binding.contract.max_bytes
            )
        if observed.st_gid != binding.owner_gid or digest != binding.contract.leaf.sha256:
            raise _error("authenticated CLI artifact owner or digest changed")


def _open_contract_parent(
    workspace_fd: int, contract: ArtifactContract
) -> int:
    if not _matches_directory(os.fstat(workspace_fd), contract.root):
        raise _error("workspace root identity changed")
    current = os.dup(workspace_fd)
    try:
        for expected in contract.parents:
            child = _open_directory_at(current, expected.name)
            observed = os.fstat(child)
            if (
                not _matches_directory(observed, expected)
                or expected.mode & _CLI_UNSAFE_MODE_BITS
            ):
                os.close(child)
                raise _error(
                    f"workspace directory {expected.name!r} identity or mode changed"
                )
            os.close(current)
            current = child
        return current
    except BaseException:
        os.close(current)
        raise


def _open_or_create_cli_parent(
    workspace_fd: int, relative_path: str
) -> tuple[int, str, tuple[PathComponentContract, ...]]:
    components = _safe_relative_components(relative_path, label="migration report")
    root_observed = os.fstat(workspace_fd)
    root_contract = _directory_contract(
        ".", root_observed, expected_owner=os.getuid()
    )
    if root_contract.mode & _CLI_UNSAFE_MODE_BITS:
        raise _error("migration workspace root is group/world writable")
    contracts: list[PathComponentContract] = [root_contract]
    current = os.dup(workspace_fd)
    try:
        for component in components[:-1]:
            try:
                child = os.open(
                    component,
                    os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC,
                    dir_fd=current,
                )
            except FileNotFoundError:
                try:
                    os.mkdir(component, mode=0o700, dir_fd=current)
                    os.fsync(current)
                    child = os.open(
                        component,
                        os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC,
                        dir_fd=current,
                    )
                except OSError as exc:
                    raise _error(
                        f"could not create migration directory {component!r}",
                        cause=exc,
                    )
            except OSError as exc:
                raise _error(
                    f"could not open migration directory {component!r}", cause=exc
                )
            observed = os.fstat(child)
            contract = _directory_contract(
                component, observed, expected_owner=os.getuid()
            )
            if contract.mode & _CLI_UNSAFE_MODE_BITS:
                os.close(child)
                raise _error(
                    f"migration directory {component!r} is group/world writable"
                )
            os.close(current)
            current = child
            contracts.append(contract)
        return current, components[-1], tuple(contracts)
    except BaseException:
        os.close(current)
        raise


def _reauthenticate_cli_directories(
    workspace_fd: int, contracts: Sequence[PathComponentContract]
) -> None:
    if not contracts or not _matches_directory(os.fstat(workspace_fd), contracts[0]):
        raise _error("workspace output root identity changed")
    current = os.dup(workspace_fd)
    try:
        for expected in contracts[1:]:
            child = _open_directory_at(current, expected.name)
            observed = os.fstat(child)
            if not _matches_directory(observed, expected):
                os.close(child)
                raise _error("workspace output directory identity changed")
            os.close(current)
            current = child
    finally:
        os.close(current)


def _decode_cli_json(raw: bytes, *, label: str, maximum: int) -> dict[str, Any]:
    return dict(
        _require_mapping(
            _decode_json_bytes(raw, maximum=maximum, label=label), label
        )
    )


def _validate_contract_file_record(
    value: object,
    *,
    label: str,
    metadata: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    row = dict(_require_mapping(value, label))
    allowed = {"path", "sha256"} | set(metadata)
    if not {"path", "sha256"}.issubset(row) or not set(row).issubset(allowed):
        raise _error(f"{label} keys differ")
    _safe_relative_components(row["path"], label=f"{label}.path")
    if not _is_sha256(row["sha256"]):
        raise _error(f"{label}.sha256 is invalid")
    for key in set(row) - {"path", "sha256"}:
        if row[key] is not True:
            raise _error(f"{label}.{key} must be true when present")
    return row


def _validate_contract_file_list(
    value: object,
    *,
    label: str,
    expected_count: int,
    metadata: frozenset[str] = frozenset(),
) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list) or len(value) != expected_count:
        raise _error(f"{label} must contain exactly {expected_count} records")
    rows = tuple(
        _validate_contract_file_record(
            row, label=f"{label}[{index}]", metadata=metadata
        )
        for index, row in enumerate(value)
    )
    paths = tuple(row["path"] for row in rows)
    if len(set(paths)) != len(paths):
        raise _error(f"{label} contains duplicate paths")
    return rows


def _validate_prechange_contract(value: object) -> dict[str, Any]:
    document = dict(_require_mapping(value, "prechange contract"))
    _require_exact_keys(
        document,
        {
            "schemaVersion",
            "capturedAt",
            "workspaceRoot",
            "acceptedDocuments",
            "runtime",
            "sourceMirrorPolicy",
            "protectedFiles",
            "productionSelectorFiles",
            "existingToolingFiles",
            "plannedCreatedFiles",
            "rollbackBundle",
            "dirtyWorktree",
            "selfHash",
        },
        "prechange contract",
    )
    if (
        document["schemaVersion"] != _PRECHANGE_SCHEMA
        or not isinstance(document["capturedAt"], str)
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", document["capturedAt"])
        is None
        or document["workspaceRoot"] != os.fspath(_DEFAULT_WORKSPACE_ROOT)
        or document["selfHash"] is not None
    ):
        raise _error("prechange contract identity differs")

    accepted = _require_mapping(document["acceptedDocuments"], "accepted documents")
    _require_exact_keys(
        accepted,
        {"parentPlan", "recoveryArchitecture", "recoveryPlan"},
        "accepted documents",
    )
    for key in ("parentPlan", "recoveryArchitecture", "recoveryPlan"):
        row = _require_mapping(accepted[key], f"accepted documents.{key}")
        _require_exact_keys(row, {"path", "sha256"}, f"accepted documents.{key}")
        _validate_contract_file_record(row, label=f"accepted documents.{key}")

    runtime = _require_mapping(document["runtime"], "prechange runtime")
    _require_exact_keys(
        runtime,
        {"chromium", "darwin", "platform", "playwright", "python", "sandboxExec", "streamlit"},
        "prechange runtime",
    )
    for key in ("darwin", "platform", "playwright", "streamlit"):
        if not isinstance(runtime[key], str) or not runtime[key]:
            raise _error(f"prechange runtime.{key} is invalid")
    for key, expected in (
        ("chromium", {"executable", "version"}),
        ("python", {"executable", "version"}),
        ("sandboxExec", {"path", "smokeExitCode"}),
    ):
        row = _require_mapping(runtime[key], f"prechange runtime.{key}")
        _require_exact_keys(row, expected, f"prechange runtime.{key}")
    if (
        any(
            not isinstance(runtime[key][field], str) or not runtime[key][field]
            for key in ("chromium", "python")
            for field in ("executable", "version")
        )
        or not isinstance(runtime["sandboxExec"]["path"], str)
        or not _is_int(runtime["sandboxExec"]["smokeExitCode"])
    ):
        raise _error("prechange runtime executables are invalid")

    mirror = _require_mapping(document["sourceMirrorPolicy"], "source mirror policy")
    _require_exact_keys(
        mirror,
        {"schemaVersion", "include", "exclude", "fileKinds", "forbidden"},
        "source mirror policy",
    )
    if not isinstance(mirror["schemaVersion"], str) or not mirror["schemaVersion"]:
        raise _error("source mirror policy schema is invalid")
    for key in ("include", "exclude", "fileKinds", "forbidden"):
        rows = mirror[key]
        if (
            not isinstance(rows, list)
            or not rows
            or any(not isinstance(row, str) or not row for row in rows)
            or len(set(rows)) != len(rows)
        ):
            raise _error(f"source mirror policy.{key} is invalid")

    metadata = frozenset({"userOwnedDirty", "userOwnedUntracked"})
    _validate_contract_file_list(
        document["protectedFiles"],
        label="protected files",
        expected_count=6,
        metadata=metadata,
    )
    _validate_contract_file_list(
        document["productionSelectorFiles"],
        label="production selector files",
        expected_count=9,
        metadata=metadata,
    )
    _validate_contract_file_list(
        document["existingToolingFiles"],
        label="existing tooling files",
        expected_count=12,
        metadata=metadata,
    )
    planned = document["plannedCreatedFiles"]
    if not isinstance(planned, list) or len(planned) != 12:
        raise _error("planned created files must contain exactly 12 records")
    planned_paths: list[str] = []
    for index, raw_row in enumerate(planned):
        row = _require_mapping(raw_row, f"planned created files[{index}]")
        _require_exact_keys(
            row, {"existsAtSnapshot", "path"}, f"planned created files[{index}]"
        )
        if row["existsAtSnapshot"] is not False:
            raise _error("planned created file existed at the snapshot")
        _safe_relative_components(row["path"], label="planned created file path")
        planned_paths.append(row["path"])
    if len(set(planned_paths)) != len(planned_paths):
        raise _error("planned created files contain duplicate paths")

    rollback = _require_mapping(document["rollbackBundle"], "rollback bundle")
    _require_exact_keys(rollback, {"archive", "manifest", "owner"}, "rollback bundle")
    for key in ("archive", "manifest"):
        row = _require_mapping(rollback[key], f"rollback bundle.{key}")
        _require_exact_keys(
            row, {"path", "sha256", "size"}, f"rollback bundle.{key}"
        )
        _safe_relative_components(row["path"], label=f"rollback bundle.{key}.path")
        if not _is_sha256(row["sha256"]) or not _is_int(row["size"]) or row["size"] < 0:
            raise _error(f"rollback bundle.{key} metadata is invalid")
    owner = _require_mapping(rollback["owner"], "rollback bundle.owner")
    _require_exact_keys(owner, {"gid", "uid"}, "rollback bundle.owner")
    if not _is_int(owner["uid"]) or not _is_int(owner["gid"]):
        raise _error("rollback bundle owner is invalid")

    dirty = _require_mapping(document["dirtyWorktree"], "dirty worktree")
    _require_exact_keys(
        dirty, {"porcelainV1NulSha256", "policy", "entries"}, "dirty worktree"
    )
    if (
        not _is_sha256(dirty["porcelainV1NulSha256"])
        or not isinstance(dirty["policy"], str)
        or not dirty["policy"]
        or not isinstance(dirty["entries"], list)
        or any(not isinstance(row, str) or not row for row in dirty["entries"])
    ):
        raise _error("dirty worktree record is invalid")
    return document


def _load_prechange_contract(
    workspace_fd: int, path: Path
) -> tuple[dict[str, Any], _CliArtifactBinding]:
    relative = _workspace_relative_path(path, label="prechange contract")
    raw, _digest, _observed, binding = _read_cli_artifact(
        workspace_fd,
        relative,
        label="prechange contract",
        maximum=MAX_MANIFEST_BYTES,
    )
    return _validate_prechange_contract(
        _decode_cli_json(raw, label="prechange contract", maximum=MAX_MANIFEST_BYTES)
    ), binding


def _load_stack_contract_path(
    workspace_fd: int, path: Path
) -> tuple[dict[str, Any], AuthenticatedControlCatalog, str]:
    relative = _workspace_relative_path(path, label="capture-stack contract")
    return authenticate_capture_stack_contract(
        workspace_fd,
        relative,
        workspace_root_fd=workspace_fd,
        expected_owner=os.getuid(),
    )


def _authenticate_manifest_path(
    workspace_fd: int, path: Path
) -> AuthenticatedManifestBundle:
    relative = _workspace_relative_path(path, label="manifest")
    _raw, expected_sha256, _observed, binding = _read_cli_artifact(
        workspace_fd,
        relative,
        label="manifest",
        maximum=MAX_MANIFEST_BYTES,
    )
    parent_fd = _open_contract_parent(workspace_fd, binding.contract)
    try:
        contract = freeze_manifest_bundle_contract(
            parent_fd,
            binding.contract.leaf.name,
            expected_owner=os.getuid(),
            expected_manifest_sha256=expected_sha256,
        )
        _require_cli_safe_contract(contract.manifest, label="manifest bundle")
        for capture in contract.captures:
            _require_cli_safe_contract(capture.png, label="manifest PNG")
            _require_cli_safe_contract(
                capture.render_sidecar, label="manifest render sidecar"
            )
            for supplemental in capture.supplemental:
                _require_cli_safe_contract(
                    supplemental, label="manifest supplemental artifact"
                )
        result = reauthenticate_manifest_bundle(parent_fd, contract)
        _reauthenticate_cli_bindings(workspace_fd, (binding,))
        return result
    finally:
        os.close(parent_fd)


def _verify_accepted_documents(
    workspace_fd: int,
    contract: Mapping[str, Any],
    *,
    required_parent_sha256: str,
    bindings: list[_CliArtifactBinding],
) -> dict[str, str]:
    if not _is_sha256(required_parent_sha256):
        raise _error("required parent plan digest is invalid")
    accepted = _require_mapping(contract["acceptedDocuments"], "accepted documents")
    parent = _require_mapping(accepted["parentPlan"], "accepted parent plan")
    if parent["sha256"] != required_parent_sha256:
        raise _error("required parent plan digest differs from the contract")
    observed: dict[str, str] = {}
    for key in ("parentPlan", "recoveryArchitecture", "recoveryPlan"):
        record = _require_mapping(accepted[key], f"accepted documents.{key}")
        _raw, digest, _stat, binding = _read_cli_artifact(
            workspace_fd,
            record["path"],
            label=f"accepted documents.{key}",
            maximum=MAX_MANIFEST_BYTES,
            expected_sha256=record["sha256"],
        )
        bindings.append(binding)
        observed[key] = digest
    if observed["parentPlan"] != required_parent_sha256:
        raise _error("live parent plan digest differs from the required digest")
    return observed


def _verify_protected_files(
    workspace_fd: int,
    contract: Mapping[str, Any],
    *,
    bindings: list[_CliArtifactBinding],
) -> dict[str, str]:
    observed: dict[str, str] = {}
    for index, raw_record in enumerate(contract["protectedFiles"]):
        record = _require_mapping(raw_record, f"protected files[{index}]")
        _raw, digest, _stat, binding = _read_cli_artifact(
            workspace_fd,
            record["path"],
            label=f"protected file {record['path']}",
            maximum=MAX_AUTHENTICATED_ARTIFACT_BYTES,
            expected_sha256=record["sha256"],
        )
        bindings.append(binding)
        observed[record["path"]] = digest
    return observed


def _verify_historical_bundle(
    workspace_fd: int,
    contract: Mapping[str, Any],
    *,
    bindings: list[_CliArtifactBinding],
) -> dict[str, Any]:
    rollback = _require_mapping(contract["rollbackBundle"], "rollback bundle")
    owner = dict(_require_mapping(rollback["owner"], "rollback bundle owner"))
    if owner != {"uid": os.getuid(), "gid": os.getgid()}:
        raise _error("rollback bundle owner differs from the executing owner")

    artifacts: dict[str, tuple[bytes, os.stat_result, Mapping[str, Any]]] = {}
    for key, maximum in (
        ("archive", MAX_AUTHENTICATED_ARTIFACT_BYTES),
        ("manifest", MAX_MANIFEST_BYTES),
    ):
        record = _require_mapping(rollback[key], f"rollback bundle.{key}")
        if record["size"] > maximum:
            raise _error(f"rollback bundle.{key} exceeds its bound")
        raw, digest, observed, binding = _read_cli_artifact(
            workspace_fd,
            record["path"],
            label=f"rollback bundle.{key}",
            maximum=maximum,
            expected_sha256=record["sha256"],
        )
        if (
            len(raw) != record["size"]
            or digest != record["sha256"]
            or observed.st_uid != owner["uid"]
            or observed.st_gid != owner["gid"]
        ):
            raise _error(f"rollback bundle.{key} size or owner differs")
        bindings.append(binding)
        artifacts[key] = (raw, observed, record)

    manifest_raw, _manifest_stat, manifest_record = artifacts["manifest"]
    bundle = _decode_cli_json(
        manifest_raw, label="rollback bundle manifest", maximum=MAX_MANIFEST_BYTES
    )
    _require_exact_keys(
        bundle,
        {
            "schemaVersion",
            "createdAt",
            "owner",
            "archive",
            "restorePolicy",
            "productionControlRecords",
        },
        "rollback bundle manifest",
    )
    if (
        bundle["schemaVersion"] != _BUNDLE_SCHEMA
        or not isinstance(bundle["createdAt"], str)
        or not bundle["createdAt"]
        or bundle["owner"] != owner
        or not isinstance(bundle["productionControlRecords"], list)
    ):
        raise _error("rollback bundle manifest identity differs")
    archive_claim = _require_mapping(bundle["archive"], "bundle manifest archive")
    _require_exact_keys(
        archive_claim, {"mode", "path", "sha256", "size"}, "bundle manifest archive"
    )
    archive_record = artifacts["archive"][2]
    archive_components = _safe_relative_components(
        archive_record["path"], label="rollback archive path"
    )
    manifest_components = _safe_relative_components(
        manifest_record["path"], label="rollback manifest path"
    )
    if archive_components[:-1] != manifest_components[:-1]:
        raise _error("rollback archive and manifest are not in one owned bundle")
    try:
        claimed_mode = int(archive_claim["mode"], 8)
    except (TypeError, ValueError) as exc:
        raise _error("bundle manifest archive mode is invalid", cause=exc)
    archive_stat = artifacts["archive"][1]
    if (
        archive_claim["path"] != archive_components[-1]
        or archive_claim["sha256"] != archive_record["sha256"]
        or archive_claim["size"] != archive_record["size"]
        or claimed_mode != stat.S_IMODE(archive_stat.st_mode)
    ):
        raise _error("bundle manifest archive claim differs from prechange evidence")
    restore = _require_mapping(bundle["restorePolicy"], "bundle restore policy")
    _require_exact_keys(
        restore,
        {"createdFileDelete", "production", "tooling"},
        "bundle restore policy",
    )
    if any(not isinstance(value, str) or not value for value in restore.values()):
        raise _error("bundle restore policy is invalid")
    return {
        "archiveSha256": archive_record["sha256"],
        "manifestSha256": manifest_record["sha256"],
        "owner": owner,
    }


def _verify_prechange_command(args: argparse.Namespace) -> dict[str, Any]:
    with _cli_workspace_descriptor() as workspace_fd:
        contract, contract_binding = _load_prechange_contract(
            workspace_fd, args.contract
        )
        bindings = [contract_binding]
        accepted = _verify_accepted_documents(
            workspace_fd,
            contract,
            required_parent_sha256=args.require_parent_sha,
            bindings=bindings,
        )
        protected: dict[str, str] | None = None
        historical: dict[str, Any] | None = None
        if args.verify_protected:
            protected = _verify_protected_files(
                workspace_fd, contract, bindings=bindings
            )
        if args.verify_historical:
            historical = _verify_historical_bundle(
                workspace_fd, contract, bindings=bindings
            )
        _reauthenticate_cli_bindings(workspace_fd, bindings)
    return {
        "status": "passed",
        "contract": _workspace_relative_path(args.contract, label="prechange contract"),
        "acceptedDocuments": accepted,
        "protectedFilesVerified": 0 if protected is None else len(protected),
        "historicalVerified": historical is not None,
        "rollbackBundle": historical,
    }


def _verify_scope_command(args: argparse.Namespace) -> dict[str, Any]:
    with _cli_workspace_descriptor() as workspace_fd:
        contract, contract_binding = _load_prechange_contract(
            workspace_fd, args.contract
        )
        bindings = [contract_binding]
        parent_sha = contract["acceptedDocuments"]["parentPlan"]["sha256"]
        _verify_accepted_documents(
            workspace_fd,
            contract,
            required_parent_sha256=parent_sha,
            bindings=bindings,
        )
        _verify_protected_files(workspace_fd, contract, bindings=bindings)

        records = tuple(contract["productionSelectorFiles"])
        expected_paths = tuple(record["path"] for record in records)
        allowed_paths = tuple(
            _workspace_relative_path(path, label="allowed selector file")
            for path in args.allow_selector_files
        )
        if (
            len(allowed_paths) != len(set(allowed_paths))
            or set(allowed_paths) != set(expected_paths)
        ):
            raise _error(
                "allowed selector files must be the exact production selector set"
            )
        by_path = {record["path"]: record for record in records}
        observed: dict[str, str] = {}
        changed: list[str] = []
        for path in sorted(allowed_paths):
            _raw, digest, _stat, binding = _read_cli_artifact(
                workspace_fd,
                path,
                label=f"allowed selector file {path}",
                maximum=MAX_AUTHENTICATED_ARTIFACT_BYTES,
            )
            bindings.append(binding)
            observed[path] = digest
            if digest != by_path[path]["sha256"]:
                changed.append(path)
        _reauthenticate_cli_bindings(workspace_fd, bindings)
    return {
        "status": "passed",
        "contract": _workspace_relative_path(args.contract, label="prechange contract"),
        "allowedSelectorFiles": sorted(observed),
        "changedSelectorFiles": changed,
        "selectorFileCount": len(observed),
    }


def _verify_manifest_command(args: argparse.Namespace) -> dict[str, Any]:
    with _cli_workspace_descriptor() as workspace_fd:
        stack, _catalog, stack_sha256 = _load_stack_contract_path(
            workspace_fd, args.capture_stack_contract
        )
        bundle = _authenticate_manifest_path(workspace_fd, args.manifest)
    manifest = bundle.manifest
    captures = bundle.captures
    if manifest.get("mode") != args.expected_mode:
        raise _error("verified manifest mode differs")
    if manifest.get("phase") != args.expected_phase:
        raise _error("verified manifest phase differs")
    if (
        len(captures) != args.expected_count
        or manifest.get("captureStackDigest") != stack["captureStackDigest"]
        or manifest.get("status") != "passed"
    ):
        raise _error("verified manifest count, stack, or status differs")
    entrypoints = {
        "ux1b-full-pages": "scripts/ui_ux_fixture_app.py",
        "ux1b-selection-controls": "scripts/ui_ux_selection_fixture_app.py",
        "ux1b-theme": "scripts/ui_ux_theme_fixture_app.py",
    }
    fixture_entrypoint = entrypoints.get(args.expected_mode)
    if fixture_entrypoint is None:
        raise _error("verified manifest mode is unsupported")
    baseline = validate_baseline_evidence(
        bundle,
        fixture_entrypoint=fixture_entrypoint,
    )
    return {
        "status": "passed",
        "manifest": str(args.manifest),
        "mode": args.expected_mode,
        "phase": args.expected_phase,
        "captureCount": len(captures),
        "captureStackDigest": stack["captureStackDigest"],
        "captureStackContractSha256": stack_sha256,
        "baseline": copy.deepcopy(baseline),
    }


def _compare_control_migration_command(args: argparse.Namespace) -> dict[str, Any]:
    with _cli_workspace_descriptor() as workspace_fd:
        _stack, catalog, _stack_sha256 = _load_stack_contract_path(
            workspace_fd, args.capture_stack_contract
        )
        report = compare_control_migration(
            before_pages=_authenticate_manifest_path(workspace_fd, args.before_pages),
            after_pages=_authenticate_manifest_path(workspace_fd, args.after_pages),
            before_controls=_authenticate_manifest_path(
                workspace_fd, args.before_controls
            ),
            after_controls=_authenticate_manifest_path(
                workspace_fd, args.after_controls
            ),
            catalog=catalog,
        )
        output_relative = _workspace_relative_path(args.out, label="migration report")
        output_fd, output_name, directory_contracts = _open_or_create_cli_parent(
            workspace_fd, output_relative
        )
        try:
            raw = _canonical_json_bytes(report)
            _exclusive_write_at(output_fd, output_name, raw)
            output_contract = freeze_artifact_contract(
                output_fd,
                output_name,
                expected_owner=os.getuid(),
                max_bytes=MAX_MANIFEST_BYTES,
            )
            _require_cli_safe_contract(output_contract, label="migration report")
            with open_authenticated_artifact(output_fd, output_contract) as artifact:
                reopened, digest, _observed = _hash_descriptor(
                    artifact.descriptor, maximum=MAX_MANIFEST_BYTES
                )
            if reopened != raw or digest != hashlib.sha256(raw).hexdigest():
                raise _error("migration report publication differs")
        finally:
            os.close(output_fd)
        _reauthenticate_cli_directories(workspace_fd, directory_contracts)
    return copy.deepcopy(report)


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify authenticated Quant Radar UX-1B evidence."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    prechange = commands.add_parser("verify-prechange")
    prechange.add_argument("--contract", required=True, type=Path)
    prechange.add_argument("--require-parent-sha", required=True)
    prechange.add_argument("--verify-protected", action="store_true")
    prechange.add_argument("--verify-historical", action="store_true")

    scope = commands.add_parser("verify-scope")
    scope.add_argument("--contract", required=True, type=Path)
    scope.add_argument(
        "--allow-selector-files", required=True, nargs="+", type=Path
    )

    verify = commands.add_parser("verify-manifest")
    verify.add_argument("--manifest", required=True, type=Path)
    verify.add_argument(
        "--expected-mode",
        required=True,
        choices=("ux1b-full-pages", "ux1b-selection-controls", "ux1b-theme"),
    )
    verify.add_argument("--expected-phase", required=True)
    verify.add_argument("--expected-count", required=True, type=int)
    verify.add_argument(
        "--capture-stack-contract",
        type=Path,
        default=_DEFAULT_CAPTURE_STACK_CONTRACT,
    )

    compare_parser = commands.add_parser("compare-control-migration")
    compare_parser.add_argument("--before-pages", required=True, type=Path)
    compare_parser.add_argument("--after-pages", required=True, type=Path)
    compare_parser.add_argument("--before-controls", required=True, type=Path)
    compare_parser.add_argument("--after-controls", required=True, type=Path)
    compare_parser.add_argument("--out", required=True, type=Path)
    compare_parser.add_argument(
        "--capture-stack-contract",
        type=Path,
        default=_DEFAULT_CAPTURE_STACK_CONTRACT,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_cli_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "verify-prechange":
            result = _verify_prechange_command(args)
        elif args.command == "verify-scope":
            result = _verify_scope_command(args)
        elif args.command == "verify-manifest":
            result = _verify_manifest_command(args)
        elif args.command == "compare-control-migration":
            result = _compare_control_migration_command(args)
        else:  # pragma: no cover - argparse keeps this unreachable.
            raise _error("evidence command is unsupported")
    except EvidenceContractError as exc:
        print(
            json.dumps(
                {"status": "failed", "error": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
