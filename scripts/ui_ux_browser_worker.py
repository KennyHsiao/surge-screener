#!/usr/bin/env python3
"""Sandboxed Playwright child for one UX-1B evidence capture.

The coordinator owns process launch, lifecycle state, artifact authentication,
and final evidence.  This child accepts one canonical NDJSON request on stdin,
writes two exclusive files below its browser-writable root, and emits one
canonical NDJSON response.  It never reads or writes a final manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import struct
import sys
import time
import urllib.parse
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence


WORKER_REQUEST_SCHEMA = "quant-radar-ui-ux-browser-request/v1"
WORKER_RESPONSE_SCHEMA = "quant-radar-ui-ux-browser-response/v1"
WORKER_REQUEST_V2_SCHEMA = "quant-radar-ui-ux-browser-request/v2"
WORKER_RESPONSE_V2_SCHEMA = "quant-radar-ui-ux-browser-response/v2"
RENDER_SCHEMA = "quant-radar-ui-ux-render/v1"
RENDER_V2_SCHEMA = "quant-radar-ui-ux-render/v2"
CASE_SEMANTIC_PROJECTION_SCHEMA = (
    "quant-radar-ui-ux-case-semantic-projection/v1"
)

# The worker must enforce a bound before it can safely import the evidence API.
# Keep the frozen asymmetric protocol limits here and then take the smaller of
# these and the evidence module's public limits after import.
_BOOTSTRAP_REQUEST_LIMIT = 64 * 1024
_BOOTSTRAP_RESPONSE_LIMIT = 256 * 1024
_DEFAULT_ERROR_LIMIT = 2 * 1024
_DEFAULT_PNG_LIMIT = 64 * 1024 * 1024
_DEFAULT_SIDECAR_LIMIT = 8 * 1024 * 1024
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | _NOFOLLOW | _CLOEXEC
_SAFE_ID = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._/-]{0,511}\Z")
_ALLOWED_FIXTURE_ENTRYPOINTS = frozenset(
    {
        "scripts/ui_ux_fixture_app.py",
        "scripts/ui_ux_selection_fixture_app.py",
        "scripts/ui_ux_theme_fixture_app.py",
    }
)
FULL_PAGE_COMPLETION_MARKER_ID = "ux1b-full-page-render-complete"
SELECTION_COMPLETION_MARKER_ID = "ux1b-selection-ready"
FOCUSED_INTERACTION_SCHEMA = "quant-radar-ui-ux-focused-interaction/v1"
FOCUSED_CONTROL_EVIDENCE_SCHEMA = "quant-radar-ui-ux-focused-controls/v1"
FOCUSED_CONTROL_EVIDENCE_V2_SCHEMA = "quant-radar-ui-ux-focused-controls/v2"
FOCUSED_CONTROL_EVIDENCE_V3_SCHEMA = "quant-radar-ui-ux-focused-controls/v3"
FOCUSED_SCREENSHOT_BINDING_SCHEMA = (
    "quant-radar-ui-ux-focused-screenshot-binding/v1"
)
_SELECTBOX_CLEAR_ACCESSIBLE_NAME = "Clear value"
_BENIGN_STREAMLIT_404_CONSOLE_TEXT = (
    "Failed to load resource: the server responded with a status of 404 (Not Found)"
)
_PLAYWRIGHT_CONSOLE_LOCATION_KEYS = frozenset(
    {"url", "line", "column", "lineNumber", "columnNumber"}
)

# Interaction is selected only after the evidence module has authenticated the
# exact fixture/case/route/viewport identity.  It is deliberately not a worker
# request field: an untrusted child request cannot choose an arbitrary action
# or locator.  The nine rows and eleven roots are part of the capture stack.
_FOCUSED_INTERACTION_ROWS = (
    (
        "risk-guard-controls",
        "ux1b-focused/risk-guard-controls/ready/v1",
        "none",
        (".st-key-rg_source",),
        None,
    ),
    (
        "institutions-controls",
        "ux1b-focused/institutions-controls/select-portfolio/v1",
        "select-institution-portfolio",
        (".st-key-inst_view",),
        "機構持倉 · 機構 → 它持有什麼",
    ),
    (
        "options-cockpit-controls",
        "ux1b-focused/options-cockpit-controls/ready/v1",
        "none",
        (".st-key-cockpit_price_view_NVDA",),
        None,
    ),
    (
        "radar-controls",
        "ux1b-focused/radar-controls/ready/v1",
        "none",
        (".st-key-radar_source", ".st-key-radar_view"),
        None,
    ),
    (
        "knowledge-graph-controls",
        "ux1b-focused/knowledge-graph-controls/ready/v1",
        "none",
        (".st-key-kg_view_mode", ".st-key-kg_label_mode"),
        None,
    ),
    (
        "ai-chat-settings-controls",
        "ux1b-focused/ai-chat-settings-controls/open-settings/v1",
        "open-ai-chat-settings",
        (".st-key-ai_chat_mode",),
        "快速問答",
    ),
    (
        "retro-controls",
        "ux1b-focused/retro-controls/ready/v1",
        "none",
        (".st-key-retro_validation_lane",),
        None,
    ),
    (
        "analytics-controls",
        "ux1b-focused/analytics-controls/ready/v1",
        "none",
        (".st-key-adb_table",),
        None,
    ),
    (
        "stock-checkup-controls",
        "ux1b-focused/stock-checkup-controls/ready/v1",
        "none",
        (".st-key-checkup_mode",),
        None,
    ),
)
_FOCUSED_INTERACTIONS = MappingProxyType(
    {
        case: MappingProxyType(
            {
                "schemaVersion": FOCUSED_INTERACTION_SCHEMA,
                "case": case,
                "interactionId": interaction_id,
                "action": action,
                "rootSelectors": roots,
                "selectedBusinessState": selected_state,
            }
        )
        for case, interaction_id, action, roots, selected_state in _FOCUSED_INTERACTION_ROWS
    }
)


# This is deliberately independent from the production modules.  The worker
# must fail closed if labels, order, selected state, or replacement widget
# differ from the reviewed migration contract.
_FOCUSED_CONTROL_ROWS = (
    (
        "risk-guard-controls",
        (
            (
                "rg_source",
                ".st-key-rg_source",
                "radio_horizontal",
                "來源",
                ("手動輸入", "Watchlist", "Screener 候選", "IBKR 持倉"),
                "Watchlist",
            ),
        ),
    ),
    (
        "institutions-controls",
        (
            (
                "inst_view",
                ".st-key-inst_view",
                "radio_horizontal",
                "檢視",
                (
                    "機構持股 · 股票 → 誰持有它",
                    "機構持倉 · 機構 → 它持有什麼",
                ),
                "機構持倉 · 機構 → 它持有什麼",
            ),
        ),
    ),
    (
        "options-cockpit-controls",
        (
            (
                "cockpit_price_view_NVDA",
                ".st-key-cockpit_price_view_NVDA",
                "radio_horizontal",
                "圖表模式",
                ("快照圖 + 預期波動錐", "互動圖 (TradingView)"),
                "快照圖 + 預期波動錐",
            ),
        ),
    ),
    (
        "radar-controls",
        (
            (
                "radar_source",
                ".st-key-radar_source",
                "radio_horizontal",
                "來源",
                (
                    "手動輸入",
                    "Watchlist",
                    "Screener 候選",
                    "反轉候選(掃描)",
                    "IBKR 持倉",
                ),
                "手動輸入",
            ),
            (
                "radar_view",
                ".st-key-radar_view",
                "radio_horizontal",
                "顯示",
                ("全部", "風險警示", "反轉候選", "兩者共現"),
                "全部",
            ),
        ),
    ),
    (
        "knowledge-graph-controls",
        (
            (
                "kg_view_mode",
                ".st-key-kg_view_mode",
                "radio_horizontal",
                "視圖",
                ("星雲圖", "驗證泳道"),
                "星雲圖",
            ),
            (
                "kg_label_mode",
                ".st-key-kg_label_mode",
                "radio_horizontal",
                "標籤",
                ("核心", "因子", "全部", "無"),
                "核心",
            ),
        ),
    ),
    (
        "ai-chat-settings-controls",
        (
            (
                "ai_chat_mode",
                ".st-key-ai_chat_mode",
                "radio_horizontal",
                "模式",
                ("快速問答", "深度研究"),
                "快速問答",
            ),
        ),
    ),
    (
        "retro-controls",
        (
            (
                "retro_validation_lane",
                ".st-key-retro_validation_lane",
                "radio_horizontal",
                "驗證類型",
                ("暴漲事件復盤", "續漲強者", "Playbook 驗證"),
                "暴漲事件復盤",
            ),
        ),
    ),
    (
        "analytics-controls",
        (
            (
                "adb_table",
                ".st-key-adb_table",
                "selectbox",
                "資料表",
                ("candidate_rankings", "iv_history"),
                "candidate_rankings",
            ),
        ),
    ),
    (
        "stock-checkup-controls",
        (
            (
                "checkup_mode",
                ".st-key-checkup_mode",
                "radio_horizontal",
                "模式",
                ("單檔", "批次"),
                "單檔",
            ),
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


def worker_interaction_catalog_rows() -> tuple[dict[str, Any], ...]:
    """Return a defensive, deterministic copy of the focused interaction rows."""

    return tuple(
        {
            "schemaVersion": row["schemaVersion"],
            "case": row["case"],
            "interactionId": row["interactionId"],
            "action": row["action"],
            "rootSelectors": tuple(row["rootSelectors"]),
            "selectedBusinessState": row["selectedBusinessState"],
        }
        for row in _FOCUSED_INTERACTIONS.values()
    )


def worker_control_contract_rows() -> tuple[dict[str, Any], ...]:
    """Return a defensive copy of the exact eleven-root AX contract."""

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


class WorkerBootstrapError(RuntimeError):
    """The request or owned worker environment is not trustworthy."""


class WorkerDependencyUnavailable(RuntimeError):
    """A required browser/runtime capability is unavailable."""


class _DuplicateKey(ValueError):
    pass


def _reject_duplicate_pairs(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey(key)
        result[key] = value
    return result


def _canonical_json(document: Mapping[str, Any]) -> bytes:
    try:
        encoded = json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise WorkerBootstrapError("worker JSON is not canonicalizable") from exc
    return encoded


def _read_one_record(stream: Any) -> bytes:
    raw = stream.read(_BOOTSTRAP_REQUEST_LIMIT + 1)
    if not isinstance(raw, bytes):
        raise WorkerBootstrapError("worker stdin is not a byte stream")
    if not raw or len(raw) > _BOOTSTRAP_REQUEST_LIMIT:
        raise WorkerBootstrapError("worker request is empty or oversized")
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise WorkerBootstrapError("worker request must be exactly one NDJSON record")
    return raw


def _bootstrap_request(raw: bytes) -> dict[str, Any]:
    try:
        text = raw[:-1].decode("utf-8", errors="strict")
        value = json.loads(text, object_pairs_hook=_reject_duplicate_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateKey) as exc:
        raise WorkerBootstrapError("worker request JSON is malformed") from exc
    if not isinstance(value, dict):
        raise WorkerBootstrapError("worker request must be an object")
    if _canonical_json(value) + b"\n" != raw:
        raise WorkerBootstrapError("worker request is not canonical NDJSON")
    return value


def _safe_request_id(candidate: Mapping[str, Any] | None, fallback: str) -> str:
    value = candidate.get("requestId") if isinstance(candidate, Mapping) else None
    if _is_safe_request_id(value):
        return value
    if _is_safe_request_id(fallback):
        return fallback
    return "unknown"


def _is_safe_request_id(value: Any) -> bool:
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        return False
    components = value.split("/")
    return all(component not in {"", ".", ".."} for component in components)


def _strict_components(value: str, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value:
        raise WorkerBootstrapError(f"{label} must be a non-empty relative path")
    if value.startswith("/") or "\\" in value or "\x00" in value:
        raise WorkerBootstrapError(f"{label} must be a POSIX relative path")
    components = tuple(value.split("/"))
    if any(component in {"", ".", ".."} for component in components):
        raise WorkerBootstrapError(f"{label} contains an ambiguous component")
    return components


def _parse_exact_origin(value: str) -> tuple[str, str, int, str]:
    if not isinstance(value, str):
        raise WorkerBootstrapError("app origin must be a string")
    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise WorkerBootstrapError("app origin is malformed") from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.username is not None
        or parsed.password is not None
        or port is None
        or not 1 <= port <= 65535
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise WorkerBootstrapError("app origin is not an exact HTTP IPv4 loopback origin")
    canonical = f"http://127.0.0.1:{port}"
    if value.rstrip("/") != canonical:
        raise WorkerBootstrapError("app origin is not canonical")
    return parsed.scheme, parsed.hostname, port, canonical


def _is_allowed_url(url: str, *, origin: tuple[str, str, int, str]) -> bool:
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError:
        return False
    scheme, host, expected_port, canonical = origin
    if parsed.scheme in {"about", "data"}:
        return True
    if parsed.scheme == "blob":
        prefix = "blob:"
        return url.startswith(prefix + canonical + "/")
    if parsed.username is not None or parsed.password is not None:
        return False
    if parsed.hostname != host or port != expected_port:
        return False
    if parsed.scheme == scheme:
        return True
    return scheme == "http" and parsed.scheme == "ws"


def _is_benign_streamlit_subroute_404_fields(
    status: object,
    url: object,
    method: object,
    *,
    origin: tuple[str, str, int, str],
    route: str,
) -> bool:
    """Recognize only Streamlit's two exact same-origin 404 probe fields."""

    try:
        if type(status) is not int or status != 404 or method != "GET":
            return False
        if not isinstance(url, str):
            return False
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except (TypeError, ValueError, UnicodeError):
        return False
    scheme, host, expected_port, _canonical = origin
    route_prefix = "" if route == "/" else route
    benign_paths = {
        f"{route_prefix}/_stcore/host-config",
        f"{route_prefix}/_stcore/health",
    }
    return (
        parsed.scheme == scheme
        and parsed.hostname == host
        and port == expected_port
        and parsed.username is None
        and parsed.password is None
        and parsed.path in benign_paths
        and not parsed.query
        and not parsed.fragment
    )


def _is_benign_streamlit_subroute_404(
    response_value: Any,
    *,
    origin: tuple[str, str, int, str],
    route: str,
) -> bool:
    """Recognize only Streamlit's two known same-origin subroute probes."""

    return _is_benign_streamlit_subroute_404_fields(
        getattr(response_value, "status", None),
        getattr(response_value, "url", None),
        getattr(getattr(response_value, "request", None), "method", None),
        origin=origin,
        route=route,
    )


def _benign_streamlit_subroute_404_console_url(
    message: Any,
    *,
    origin: tuple[str, str, int, str],
    route: str,
) -> str | None:
    """Return the exact probe URL for one correlatable Chromium console event."""

    try:
        message_type = message.type
        text = message.text
        location = message.location
    except (AttributeError, TypeError, ValueError):
        return None
    if (
        message_type != "error"
        or text != _BENIGN_STREAMLIT_404_CONSOLE_TEXT
        or not isinstance(location, Mapping)
        or set(location) != _PLAYWRIGHT_CONSOLE_LOCATION_KEYS
        or any(
            type(location[key]) is not int or location[key] != 0
            for key in ("line", "column", "lineNumber", "columnNumber")
        )
        or not _is_benign_streamlit_subroute_404_fields(
            404,
            location["url"],
            "GET",
            origin=origin,
            route=route,
        )
    ):
        return None
    return str(location["url"])


class _BenignStreamlit404Correlation:
    """Order-independent exact correlation for two benign Streamlit probes."""

    __slots__ = ("_origin", "_route", "_responses", "_consoles")

    def __init__(self, *, origin: tuple[str, str, int, str], route: str) -> None:
        self._origin = origin
        self._route = route
        self._responses: set[str] = set()
        self._consoles: set[str] = set()

    def observe_response(self, response_value: Any) -> bool:
        if not _is_benign_streamlit_subroute_404(
            response_value, origin=self._origin, route=self._route
        ):
            return False
        url = str(response_value.url)
        if url in self._responses:
            return False
        self._responses.add(url)
        return True

    def observe_console(self, message: Any) -> bool:
        url = _benign_streamlit_subroute_404_console_url(
            message, origin=self._origin, route=self._route
        )
        if url is None or url in self._consoles:
            return False
        self._consoles.add(url)
        return True

    def assert_complete(self) -> None:
        if not self._consoles.issubset(self._responses):
            raise WorkerBootstrapError(
                "Streamlit probe console lacks its exact correlated 404 response"
            )


def _absolute_environment_path(name: str) -> Path:
    raw = os.environ.get(name)
    if not isinstance(raw, str) or not raw or not os.path.isabs(raw) or "\x00" in raw:
        raise WorkerBootstrapError(f"{name} is not an absolute owned path")
    return Path(os.path.abspath(raw))


def _authenticate_directory_path(path: Path, *, exact_mode: int | None) -> os.stat_result:
    try:
        named = os.lstat(path)
        descriptor = os.open(path, _DIRECTORY_FLAGS)
    except OSError as exc:
        raise WorkerBootstrapError("owned worker directory is unavailable") from exc
    try:
        opened = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        stat.S_ISLNK(named.st_mode)
        or not stat.S_ISDIR(named.st_mode)
        or not stat.S_ISDIR(opened.st_mode)
        or (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
        or opened.st_uid != os.getuid()
        or (exact_mode is not None and stat.S_IMODE(opened.st_mode) != exact_mode)
    ):
        raise WorkerBootstrapError("owned worker directory identity is invalid")
    return opened


def _owned_roots() -> tuple[Path, Path, int]:
    if os.environ.get("QUANT_RADAR_UX1B_ROLE") != "browser":
        raise WorkerBootstrapError("worker is not running in the browser role")
    source_root = _absolute_environment_path("SOURCE_ROOT")
    home = _absolute_environment_path("HOME")
    if home.name != "home":
        raise WorkerBootstrapError("browser HOME does not identify its owned root")
    browser_root = home.parent
    source_stat = _authenticate_directory_path(source_root, exact_mode=None)
    browser_stat = _authenticate_directory_path(browser_root, exact_mode=0o700)
    home_stat = _authenticate_directory_path(home, exact_mode=0o700)
    if (source_stat.st_dev, source_stat.st_ino) == (
        browser_stat.st_dev,
        browser_stat.st_ino,
    ):
        raise WorkerBootstrapError("source and browser roots overlap")
    browser_fd = os.open(browser_root, _DIRECTORY_FLAGS)
    reopened_root = os.fstat(browser_fd)
    if (reopened_root.st_dev, reopened_root.st_ino) != (
        browser_stat.st_dev,
        browser_stat.st_ino,
    ):
        os.close(browser_fd)
        raise WorkerBootstrapError("browser root changed during authentication")
    try:
        reopened_home = os.stat("home", dir_fd=browser_fd, follow_symlinks=False)
    except OSError as exc:
        os.close(browser_fd)
        raise WorkerBootstrapError("browser HOME namespace is unavailable") from exc
    if (
        not stat.S_ISDIR(reopened_home.st_mode)
        or (reopened_home.st_dev, reopened_home.st_ino)
        != (home_stat.st_dev, home_stat.st_ino)
    ):
        os.close(browser_fd)
        raise WorkerBootstrapError("browser HOME changed during authentication")
    return source_root, browser_root, browser_fd


def _check_fixture_entrypoint(source_root: Path, relative_path: str) -> None:
    if relative_path not in _ALLOWED_FIXTURE_ENTRYPOINTS:
        raise WorkerBootstrapError("fixture entrypoint is not allowlisted")
    components = _strict_components(relative_path, label="fixture entrypoint")
    root_fd = os.open(source_root, _DIRECTORY_FLAGS)
    current_fd = root_fd
    opened_fds: list[int] = []
    try:
        for component in components[:-1]:
            child_fd = os.open(component, _DIRECTORY_FLAGS, dir_fd=current_fd)
            opened = os.fstat(child_fd)
            if not stat.S_ISDIR(opened.st_mode) or opened.st_uid != os.getuid():
                os.close(child_fd)
                raise WorkerBootstrapError("fixture parent identity is invalid")
            opened_fds.append(child_fd)
            current_fd = child_fd
        leaf_fd = os.open(
            components[-1], os.O_RDONLY | _NOFOLLOW | _CLOEXEC, dir_fd=current_fd
        )
        try:
            leaf = os.fstat(leaf_fd)
            if (
                not stat.S_ISREG(leaf.st_mode)
                or leaf.st_uid != os.getuid()
                or leaf.st_nlink != 1
                or stat.S_IMODE(leaf.st_mode) & 0o222
            ):
                raise WorkerBootstrapError("fixture entrypoint identity is invalid")
        finally:
            os.close(leaf_fd)
    except OSError as exc:
        raise WorkerBootstrapError("fixture entrypoint is unavailable") from exc
    finally:
        for descriptor in reversed(opened_fds):
            os.close(descriptor)
        os.close(root_fd)


def _open_staging_parent(root_fd: int, components: Sequence[str]) -> tuple[int, list[int]]:
    current_fd = root_fd
    opened_fds: list[int] = []
    try:
        for component in components:
            try:
                os.mkdir(component, mode=0o700, dir_fd=current_fd)
            except FileExistsError:
                pass
            child_fd = os.open(component, _DIRECTORY_FLAGS, dir_fd=current_fd)
            opened = os.fstat(child_fd)
            if (
                not stat.S_ISDIR(opened.st_mode)
                or opened.st_uid != os.getuid()
                or stat.S_IMODE(opened.st_mode) != 0o700
            ):
                os.close(child_fd)
                raise WorkerBootstrapError("staging directory identity is invalid")
            opened_fds.append(child_fd)
            current_fd = child_fd
    except BaseException:
        for descriptor in reversed(opened_fds):
            os.close(descriptor)
        raise
    return current_fd, opened_fds


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise WorkerBootstrapError("staging artifact write was short")
        view = view[written:]


def _write_exclusive(root_fd: int, relative_path: str, payload: bytes) -> None:
    components = _strict_components(relative_path, label="staging artifact")
    parent_fd, opened_fds = _open_staging_parent(root_fd, components[:-1])
    descriptor = -1
    try:
        descriptor = os.open(
            components[-1],
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC,
            0o600,
            dir_fd=parent_fd,
        )
        _write_all(descriptor, payload)
        os.fsync(descriptor)
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_uid != os.getuid()
            or observed.st_nlink != 1
            or stat.S_IMODE(observed.st_mode) != 0o600
            or observed.st_size != len(payload)
        ):
            raise WorkerBootstrapError("staging artifact identity is invalid")
    except FileExistsError as exc:
        raise WorkerBootstrapError("staging artifact already exists") from exc
    except OSError as exc:
        raise WorkerBootstrapError("staging artifact could not be written") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        for parent in reversed(opened_fds):
            os.close(parent)


def _png_dimensions(payload: bytes) -> tuple[int, int]:
    if len(payload) < 24 or payload[:8] != b"\x89PNG\r\n\x1a\n":
        raise WorkerBootstrapError("browser screenshot is not PNG")
    if payload[12:16] != b"IHDR":
        raise WorkerBootstrapError("browser screenshot lacks PNG IHDR")
    width, height = struct.unpack(">II", payload[16:24])
    if width <= 0 or height <= 0:
        raise WorkerBootstrapError("browser screenshot dimensions are invalid")
    return width, height


_READINESS_SCRIPT = """
() => {
  const visible = (el) => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  if (Array.from(document.querySelectorAll('[data-testid="stException"]')).some(visible)) return false;
  const busy = [
    ...document.querySelectorAll('[data-testid="stSkeleton"]'),
    ...document.querySelectorAll('[data-testid="stSpinner"]'),
    ...document.querySelectorAll('[data-testid="stStatusWidget"] [aria-busy="true"]')
  ];
  return !busy.some(visible);
}
"""


_STABLE_LAYOUT_SCRIPT = """
() => new Promise((resolve) => {
  const size = () => [document.documentElement.scrollWidth, document.documentElement.scrollHeight,
                       document.body ? document.body.scrollWidth : 0,
                       document.body ? document.body.scrollHeight : 0];
  const first = size();
  requestAnimationFrame(() => requestAnimationFrame(() => {
    const second = size();
    resolve(first.every((value, index) => value === second[index]));
  }));
})
"""


_PLOTLY_READY_SCRIPT = """
() => Array.from(document.querySelectorAll('.js-plotly-plot'))
  .filter((el) => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length))
  .every((el) => {
    const box = el.getBoundingClientRect();
    return box.width > 0 && box.height > 0 && !!el._fullLayout;
  })
"""


_DOM_PROJECTION_SCRIPT = r"""
(contract) => {
  const normalize = (value) => String(value == null ? '' : value).replace(/\s+/g, ' ').trim();
  const requestedRoots = Array.isArray(contract && contract.rootSelectors)
    ? contract.rootSelectors.slice() : [];
  const affectedRoots = Array.isArray(contract && contract.affectedRootSelectors)
    ? contract.affectedRootSelectors.slice() : [];
  const affectedSelectors = new Set(affectedRoots);
  const visible = (element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' &&
      Number(style.opacity || 1) !== 0 && rect.width > 0 && rect.height > 0;
  };
  const implicitRole = (element) => {
    const explicit = normalize(element.getAttribute('role'));
    if (explicit) return explicit;
    const tag = element.tagName.toLowerCase();
    if (/^h[1-6]$/.test(tag)) return 'heading';
    if (tag === 'button') return 'button';
    if (tag === 'a' && element.hasAttribute('href')) return 'link';
    if (tag === 'select') return element.multiple ? 'listbox' : 'combobox';
    if (tag === 'textarea') return 'textbox';
    if (tag === 'progress') return 'progressbar';
    if (tag === 'table') return 'table';
    if (tag === 'img') return 'img';
    if (tag === 'input') {
      const type = String(element.type || 'text').toLowerCase();
      if (type === 'checkbox') return 'checkbox';
      if (type === 'radio') return 'radio';
      if (type === 'range') return 'slider';
      if (type === 'button' || type === 'submit' || type === 'reset') return 'button';
      if (type !== 'hidden') return 'textbox';
    }
    return '';
  };
  const stableClass = (element) => Array.from(element.classList || [])
    .find((name) => name.startsWith('st-key-')) || null;
  const ownRootSelector = (element) => {
    const keyed = stableClass(element);
    const selector = keyed ? '.' + keyed : null;
    return selector && affectedSelectors.has(selector) ? selector : null;
  };
  const elementSegment = (element) => {
    const keyed = stableClass(element);
    if (keyed) return '.' + keyed;
    const testid = normalize(element.getAttribute('data-testid'));
    const tag = element.tagName.toLowerCase();
    let ordinal = 1;
    for (let sibling = element.previousElementSibling; sibling; sibling = sibling.previousElementSibling) {
      if (sibling.tagName === element.tagName &&
          normalize(sibling.getAttribute('data-testid')) === testid) ordinal += 1;
    }
    return testid ? `${tag}[data-testid=${JSON.stringify(testid)}]:nth(${ordinal})`
                  : `${tag}:nth(${ordinal})`;
  };
  const elementPath = (element) => {
    const parts = [];
    for (let current = element; current && current !== document.documentElement;
         current = current.parentElement) {
      parts.push(elementSegment(current));
      if (stableClass(current)) break;
    }
    return parts.reverse().join('>');
  };
  const accessibleName = (element, role) => {
    const aria = normalize(element.getAttribute('aria-label'));
    if (aria) return aria;
    const labelled = normalize(element.getAttribute('aria-labelledby'));
    if (labelled) {
      const text = labelled.split(/\s+/).map((id) => document.getElementById(id))
        .filter(Boolean).map((node) => normalize(node.innerText || node.textContent)).join(' ');
      if (text) return text;
    }
    if (element.labels && element.labels.length) {
      const text = Array.from(element.labels).map((label) => normalize(label.innerText || label.textContent)).join(' ');
      if (text) return text;
    }
    const alt = normalize(element.getAttribute('alt'));
    if (alt) return alt;
    const title = normalize(element.getAttribute('title'));
    if (title) return title;
    const value = normalize(element.value);
    if (role === 'button' && value) return value;
    return normalize(element.innerText || element.textContent);
  };
  const directText = (element) => normalize(Array.from(element.childNodes)
    .filter((node) => node.nodeType === Node.TEXT_NODE).map((node) => node.nodeValue).join(' '));
  const all = Array.from(document.body ? document.body.querySelectorAll('*') : []);
  const targetRoots = new Map();
  for (const selector of requestedRoots) {
    const matches = all.filter((element) => ownRootSelector(element) === selector);
    if (matches.length === 1) targetRoots.set(selector, matches[0]);
  }
  const selectorList = requestedRoots.join(',');
  const horizontalBoundary = new Map();
  const syntheticBoundary = new Map();
  const actualBoundaries = new Set();
  for (const [selector, root] of targetRoots.entries()) {
    const block = root.closest('[data-testid="stHorizontalBlock"]');
    if (block && block !== root) {
      horizontalBoundary.set(selector, block);
      actualBoundaries.add(block);
    } else {
      syntheticBoundary.set(selector, `${elementPath(root)}::layout-boundary`);
    }
  }
  const selected = all.filter((element) => {
    if (!visible(element)) return false;
    return actualBoundaries.has(element) || !!implicitRole(element) ||
      !!stableClass(element) || !!directText(element);
  });
  const selectedSet = new Set(selected);
  const targetOwner = (element) => selectorList ? element.closest(selectorList) : null;
  const boundaryElementFor = (element) => {
    if (actualBoundaries.has(element)) return element;
    const block = element.closest('[data-testid="stHorizontalBlock"]');
    return block && actualBoundaries.has(block) ? block : null;
  };
  const boundaryPathFor = (element) => {
    const actual = boundaryElementFor(element);
    if (actual) return elementPath(actual);
    const owner = targetOwner(element);
    const selector = owner ? ownRootSelector(owner) : null;
    return selector ? syntheticBoundary.get(selector) || null : null;
  };
  const flowScopeFor = (element) => element.closest('[data-testid="stSidebar"]') ? 'sidebar' :
    (element.closest('[data-testid="stHeader"]') ? 'header' :
     (element.closest('[data-testid="stMainBlockContainer"]') ? 'main' : 'document'));
  const rows = [];
  for (const element of selected) {
    const role = implicitRole(element) || 'generic';
    const rect = element.getBoundingClientRect();
    const rootSelector = ownRootSelector(element);
    const flowScope = flowScopeFor(element);
    let parent = element.parentElement;
    while (parent && !selectedSet.has(parent)) parent = parent.parentElement;
    let parentPath = parent ? elementPath(parent) : null;
    const syntheticPath = rootSelector ? syntheticBoundary.get(rootSelector) : null;
    if (syntheticPath) {
      const parentRect = (element.closest('[data-testid="stElementContainer"]') || element)
        .getBoundingClientRect();
      rows.push({
        path: syntheticPath,
        parentPath,
        flowScope,
        boundaryPath: syntheticPath,
        rootSelector: null,
        role: 'generic',
        name: '',
        text: '',
        state: {},
        visible: true,
        bounds: {
          x: Math.round(parentRect.x), y: Math.round(parentRect.y),
          width: Math.round(parentRect.width), height: Math.round(parentRect.height)
        }
      });
      parentPath = syntheticPath;
    }
    const state = {};
    const booleanAria = {
      expanded: 'aria-expanded', pressed: 'aria-pressed', selected: 'aria-selected',
      checked: 'aria-checked', disabled: 'aria-disabled', required: 'aria-required'
    };
    for (const [key, attribute] of Object.entries(booleanAria)) {
      const raw = element.getAttribute(attribute);
      if (raw === 'true' || raw === 'false') state[key] = raw === 'true';
    }
    for (const key of ['checked', 'disabled', 'required', 'selected']) {
      if (key in element && typeof element[key] === 'boolean') state[key] = !!element[key];
    }
    if ('value' in element && ['textbox', 'combobox', 'slider'].includes(role)) {
      state.value = normalize(element.value);
    }
    if (role === 'heading') state.level = Number(element.getAttribute('aria-level')) ||
      Number(element.tagName.substring(1)) || 0;
    state.tabIndex = Number(element.tabIndex);
    rows.push({
      path: elementPath(element),
      parentPath,
      flowScope,
      boundaryPath: boundaryPathFor(element),
      rootSelector,
      role,
      name: accessibleName(element, role),
      text: directText(element),
      state,
      visible: true,
      bounds: {
        x: Math.round(rect.x), y: Math.round(rect.y),
        width: Math.round(rect.width), height: Math.round(rect.height)
      }
    });
  }
  return rows;
}
"""


def _stable_node_id(path: str) -> str:
    return "dom-" + hashlib.sha256(path.encode("utf-8")).hexdigest()[:24]


def _selector_tuple(value: Any, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise WorkerBootstrapError(f"capture {label} catalog is malformed")
    selectors = tuple(value)
    if (
        any(
            not isinstance(selector, str)
            or re.fullmatch(r"\.st-key-[A-Za-z0-9_-]{1,160}", selector) is None
            for selector in selectors
        )
        or len(set(selectors)) != len(selectors)
    ):
        raise WorkerBootstrapError(f"capture {label} catalog is invalid")
    return selectors


def _root_selectors(
    capture_identity: Mapping[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    expected = _selector_tuple(
        capture_identity.get("rootSelectors"), label="root-selector"
    )
    affected = _selector_tuple(
        capture_identity.get("affectedRootSelectors"),
        label="affected-root-selector",
    )
    if len(affected) != 11 or not set(expected).issubset(affected):
        raise WorkerBootstrapError("capture affected-root catalog is incomplete")
    return expected, affected


def _focused_interaction_contract(
    capture_identity: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    fixture = capture_identity.get("fixtureEntrypoint")
    if fixture != "scripts/ui_ux_selection_fixture_app.py":
        return None
    case = capture_identity.get("case")
    if not isinstance(case, str):
        raise WorkerBootstrapError("focused interaction case is malformed")
    contract = _FOCUSED_INTERACTIONS.get(case)
    if contract is None:
        raise WorkerBootstrapError("focused interaction case is not cataloged")
    identity_roots = _selector_tuple(
        capture_identity.get("rootSelectors"),
        label="focused interaction root-selector",
    )
    if identity_roots != tuple(contract["rootSelectors"]):
        raise WorkerBootstrapError(
            "focused interaction roots differ from the worker catalog"
        )
    return contract


def _focused_control_option_count(
    capture_identity: Mapping[str, Any], root_selector: str
) -> int:
    """Return one exact focused-control option count from the closed catalog."""

    case = capture_identity.get("case")
    controls = _FOCUSED_CONTROL_CONTRACTS.get(str(case), ())
    matches = tuple(
        control
        for control in controls
        if control.get("rootSelector") == root_selector
    )
    if len(matches) != 1:
        raise WorkerBootstrapError("focused control option catalog is ambiguous")
    option_labels = matches[0].get("optionLabels")
    if not isinstance(option_labels, tuple) or not option_labels:
        raise WorkerBootstrapError("focused control option catalog is malformed")
    return len(option_labels)


def _wait_for_unique_visible(
    locator: Any,
    *,
    label: str,
    timeout_ms: int,
) -> Any:
    locator.first.wait_for(state="visible", timeout=timeout_ms)
    if locator.count() != 1:
        raise WorkerBootstrapError(f"{label} is not a unique visible locator")
    return locator


def _selection_capture_id(capture_identity: Mapping[str, Any]) -> str:
    viewport = capture_identity.get("viewport")
    case = capture_identity.get("case")
    if (
        capture_identity.get("fixtureEntrypoint")
        != "scripts/ui_ux_selection_fixture_app.py"
        or not isinstance(viewport, Mapping)
        or not isinstance(case, str)
    ):
        raise WorkerBootstrapError("selection completion identity is malformed")
    capture_id = f'{case}/{viewport.get("name")}'
    if not _is_safe_request_id(capture_id):
        raise WorkerBootstrapError("selection completion capture ID is invalid")
    return capture_id


def _selection_render_generation(
    page: Any,
    capture_identity: Mapping[str, Any],
    *,
    timeout_ms: int,
) -> int:
    marker = page.locator(f"#{SELECTION_COMPLETION_MARKER_ID}")
    marker.wait_for(state="attached", timeout=timeout_ms)
    if marker.count() != 1:
        raise WorkerBootstrapError("selection completion marker is not unique")
    if marker.get_attribute("data-capture-id") != _selection_capture_id(
        capture_identity
    ):
        raise WorkerBootstrapError("selection completion capture ID differs")
    raw_generation = marker.get_attribute("data-render-generation")
    if (
        not isinstance(raw_generation, str)
        or re.fullmatch(r"[1-9][0-9]{0,6}", raw_generation) is None
    ):
        raise WorkerBootstrapError("selection completion generation is invalid")
    generation = int(raw_generation)
    if generation > 1_000_000:
        raise WorkerBootstrapError("selection completion generation is invalid")
    return generation


def _wait_for_selection_render_after(
    page: Any,
    capture_identity: Mapping[str, Any],
    previous_generation: int,
    *,
    timeout_ms: int,
) -> int:
    if (
        type(previous_generation) is not int
        or previous_generation < 1
        or previous_generation >= 1_000_000
    ):
        raise WorkerBootstrapError("selection completion baseline is invalid")
    deadline = time.monotonic() + (timeout_ms / 1000)
    while True:
        generation = _selection_render_generation(
            page,
            capture_identity,
            timeout_ms=timeout_ms,
        )
        if generation > previous_generation:
            return generation
        if generation < previous_generation:
            raise WorkerBootstrapError("selection completion generation regressed")
        remaining_ms = int((deadline - time.monotonic()) * 1000)
        if remaining_ms <= 0:
            raise WorkerBootstrapError("selection render did not complete after interaction")
        page.wait_for_timeout(min(50, remaining_ms))


_RADIO_LABEL_ASSOCIATION_SCRIPT = """
(node, expected) => {
  const normalize = value => String(value ?? '').replace(/\\s+/g, ' ').trim();
  const root = node.closest(expected.rootSelector);
  const group = node.closest('[role="radiogroup"]');
  const label = node.closest('label');
  const labels = node.labels ? Array.from(node.labels) : [];
  const labelRadios = label
    ? Array.from(label.querySelectorAll('input[type="radio"], [role="radio"]'))
    : [];
  const tree = node.getRootNode();
  const nativeName = node.name;
  const nativeNameAttribute = node.getAttribute('name');
  const groupRadios = group
    ? Array.from(group.querySelectorAll('input[type="radio"]'))
    : [];
  const rootRadios = root
    ? Array.from(root.querySelectorAll('input[type="radio"]'))
    : [];
  const nativePeers = nativeName.length > 0 &&
    tree && typeof tree.querySelectorAll === 'function'
    ? Array.from(tree.querySelectorAll('input[type="radio"]')).filter(
        candidate => candidate.name === nativeName && candidate.form === node.form
      )
    : [];
  if (!(
    node.tagName === 'INPUT' && node.type === 'radio' &&
    root && group && label &&
    typeof nativeName === 'string' &&
    nativeNameAttribute !== null && nativeNameAttribute === nativeName &&
    document.querySelectorAll(expected.rootSelector).length === 1 &&
    root.querySelectorAll('[role="radiogroup"]').length === 1 &&
    root.querySelector('[role="radiogroup"]') === group &&
    root.contains(group) && root.contains(label) && group.contains(label) &&
    label.contains(node) &&
    labels.length === 1 && labels[0] === label &&
    label.control === node &&
    labelRadios.length === 1 && labelRadios[0] === node &&
    groupRadios.length > 0 &&
    groupRadios.length === expected.optionCount &&
    rootRadios.length === groupRadios.length &&
    rootRadios.every(candidate => groupRadios.includes(candidate)) &&
    groupRadios.every(candidate =>
      candidate.getAttribute('name') === nativeName &&
      candidate.name === nativeName && candidate.form === node.form &&
      root.contains(candidate) && group.contains(candidate)
    ) &&
    (nativeName.length === 0 || (
      nativePeers.length === groupRadios.length &&
      nativePeers.every(candidate =>
        root.contains(candidate) && group.contains(candidate)
      )
    )) &&
    normalize(label.innerText) === expected.label
  )) return false;

  const chain = [];
  for (let current = node; current; current = current.parentElement) {
    chain.push(current);
    if (current === root) break;
  }
  if (chain[chain.length - 1] !== root) return false;
  if (chain.some(element => {
    const ariaDisabled = normalize(element.getAttribute('aria-disabled')).toLowerCase();
    const style = getComputedStyle(element);
    return element.matches(':disabled') ||
      element.hasAttribute('disabled') ||
      element.inert === true || element.hasAttribute('inert') ||
      ariaDisabled === 'true' ||
      style.pointerEvents === 'none';
  })) return false;

  const visualChain = [];
  for (let current = label; current; current = current.parentElement) {
    visualChain.push(current);
    if (current === root) break;
  }
  if (visualChain[visualChain.length - 1] !== root) return false;
  if (visualChain.some(element => {
    const style = getComputedStyle(element);
    const opacity = Number.parseFloat(style.opacity);
    return (
      style.display === 'none' ||
      style.visibility === 'hidden' || style.visibility === 'collapse' ||
      !Number.isFinite(opacity) || opacity <= 0 ||
      style.pointerEvents === 'none'
    );
  })) return false;

  const rect = label.getBoundingClientRect();
  return label.getClientRects().length > 0 && rect.width > 0 && rect.height > 0;
}
"""


def _validated_radio_label(
    radio: Any,
    *,
    root_selector: str,
    expected_label: str,
    expected_option_count: int,
    timeout_ms: int,
) -> Any:
    """Return the one visible wrapping label for one semantic native radio."""

    if radio.count() != 1:
        raise WorkerBootstrapError("focused radio option is not unique")
    label = radio.locator("xpath=ancestor::label[1]")
    try:
        label.first.wait_for(state="visible", timeout=timeout_ms)
        if label.count() != 1 or not label.is_visible():
            raise WorkerBootstrapError("focused radio label is not uniquely visible")
        associated = radio.evaluate(
            _RADIO_LABEL_ASSOCIATION_SCRIPT,
            {
                "rootSelector": root_selector,
                "label": expected_label,
                "optionCount": expected_option_count,
            },
        )
        box = label.bounding_box()
    except WorkerBootstrapError:
        raise
    except Exception as exc:
        raise WorkerBootstrapError(
            "focused radio label did not become uniquely actionable"
        ) from exc
    if associated is not True:
        raise WorkerBootstrapError("focused radio label association differs")
    if (
        not isinstance(box, dict)
        or set(box) != {"x", "y", "width", "height"}
        or type(box["width"]) not in {int, float}
        or type(box["height"]) not in {int, float}
        or not 0 < float(box["width"]) < float("inf")
        or not 0 < float(box["height"]) < float("inf")
    ):
        raise WorkerBootstrapError("focused radio label geometry is invalid")
    return label


def _exact_choice_locator(
    page: Any,
    root: Any,
    root_selector: str,
    name: str,
    *,
    expected_option_count: int,
    timeout_ms: int,
) -> tuple[str, Any, Any]:
    button = root.get_by_role("button", name=name, exact=True)
    radio = root.get_by_role("radio", name=name, exact=True)
    deadline = time.monotonic() + (timeout_ms / 1000)
    while True:
        button_count = button.count()
        radio_count = radio.count()
        raw_radio_count = root.locator(
            'input[type="radio"], [role="radio"]'
        ).count()
        if (
            raw_radio_count not in {0, expected_option_count}
            or root.locator(
                '[data-baseweb="select"], [role="combobox"]'
            ).count()
            != 0
        ):
            raise WorkerBootstrapError(
                "focused choice raw radio projection differs"
            )
        if (
            (button_count, radio_count) == (1, 0)
            and raw_radio_count == 0
            and button.is_visible()
        ):
            return "button", button, button
        if (
            (button_count, radio_count) == (0, 1)
            and raw_radio_count == expected_option_count
        ):
            label = _validated_radio_label(
                radio,
                root_selector=root_selector,
                expected_label=name,
                expected_option_count=expected_option_count,
                timeout_ms=timeout_ms,
            )
            return "radio", radio, label
        if button_count + radio_count > 1:
            raise WorkerBootstrapError(
                "focused choice is not exactly one pre-control button or post-control radio"
            )
        remaining_ms = int((deadline - time.monotonic()) * 1000)
        if remaining_ms <= 0:
            raise WorkerBootstrapError("focused choice did not become uniquely visible")
        page.wait_for_timeout(min(50, remaining_ms))


def _choice_is_selected(role: str, choice: Any) -> bool:
    if role == "radio":
        return choice.is_checked() is True
    if role == "button":
        return choice.get_attribute("kind") == "segmented_controlActive"
    raise WorkerBootstrapError("focused choice role is unsupported")


def _click_choice(role: str, action: Any, *, timeout_ms: int) -> None:
    try:
        if role == "radio":
            action.click(trial=True, timeout=timeout_ms)
        action.click(timeout=timeout_ms)
    except Exception as exc:
        raise WorkerBootstrapError("focused choice is not actionable") from exc


def _assert_selected_choice(
    page: Any,
    root_selector: str,
    name: str,
    *,
    expected_option_count: int,
    timeout_ms: int,
) -> None:
    deadline = time.monotonic() + (timeout_ms / 1000)
    while True:
        root = _wait_for_unique_visible(
            page.locator(root_selector),
            label="focused selected choice root",
            timeout_ms=timeout_ms,
        )
        role, choice, _action = _exact_choice_locator(
            page,
            root,
            root_selector,
            name,
            expected_option_count=expected_option_count,
            timeout_ms=timeout_ms,
        )
        if _choice_is_selected(role, choice):
            return
        remaining_ms = int((deadline - time.monotonic()) * 1000)
        if remaining_ms <= 0:
            raise WorkerBootstrapError("focused business state is not selected")
        page.wait_for_timeout(min(50, remaining_ms))


def _wait_for_catalog_roots(
    page: Any,
    roots: Sequence[str],
    *,
    timeout_ms: int,
) -> None:
    for selector in roots:
        _wait_for_unique_visible(
            page.locator(selector),
            label="catalog control root",
            timeout_ms=timeout_ms,
        )


def _wait_for_full_page_catalog_roots(
    page: Any,
    capture_identity: Mapping[str, Any],
    *,
    timeout_ms: int,
) -> None:
    """Wait for exact full-page roots after the terminal render marker."""

    fixture_entrypoint = capture_identity.get("fixtureEntrypoint")
    if fixture_entrypoint in {
        "scripts/ui_ux_selection_fixture_app.py",
        "scripts/ui_ux_theme_fixture_app.py",
    }:
        return
    if fixture_entrypoint != "scripts/ui_ux_fixture_app.py":
        raise WorkerBootstrapError("full-page root fixture identity is unsupported")
    roots, _affected = _root_selectors(capture_identity)
    _wait_for_catalog_roots(page, roots, timeout_ms=timeout_ms)


def _perform_capture_interaction(
    page: Any,
    capture_identity: Mapping[str, Any],
    *,
    timeout_ms: int,
) -> dict[str, Any] | None:
    """Reach one frozen focused state using only fixed public locators."""

    contract = _focused_interaction_contract(capture_identity)
    if contract is None:
        return None
    action = contract["action"]
    selected_state = contract["selectedBusinessState"]
    roots = tuple(contract["rootSelectors"])

    if action == "select-institution-portfolio":
        root_selector = ".st-key-inst_view"
        expected_option_count = _focused_control_option_count(
            capture_identity, root_selector
        )
        root = _wait_for_unique_visible(
            page.locator(root_selector),
            label="institution control root",
            timeout_ms=timeout_ms,
        )
        role, choice, choice_action = _exact_choice_locator(
            page,
            root,
            root_selector,
            str(selected_state),
            expected_option_count=expected_option_count,
            timeout_ms=timeout_ms,
        )
        if not _choice_is_selected(role, choice):
            generation = _selection_render_generation(
                page,
                capture_identity,
                timeout_ms=timeout_ms,
            )
            _click_choice(role, choice_action, timeout_ms=timeout_ms)
            _wait_for_selection_render_after(
                page,
                capture_identity,
                generation,
                timeout_ms=timeout_ms,
            )
        page.get_by_text("某機構 →", exact=False).first.wait_for(
            state="visible",
            timeout=timeout_ms,
        )
        _wait_for_catalog_roots(page, roots, timeout_ms=timeout_ms)
        _assert_selected_choice(
            page,
            root_selector,
            str(selected_state),
            expected_option_count=expected_option_count,
            timeout_ms=timeout_ms,
        )
    elif action == "open-ai-chat-settings":
        launcher = _wait_for_unique_visible(
            page.get_by_role("button", name="AI", exact=True),
            label="AI chat launcher",
            timeout_ms=timeout_ms,
        )
        generation = _selection_render_generation(
            page,
            capture_identity,
            timeout_ms=timeout_ms,
        )
        launcher.click(timeout=timeout_ms)
        _wait_for_selection_render_after(
            page,
            capture_identity,
            generation,
            timeout_ms=timeout_ms,
        )
        page.get_by_text("AI 對話", exact=True).first.wait_for(
            state="visible",
            timeout=timeout_ms,
        )
        settings = _wait_for_unique_visible(
            page.get_by_text("設定與歷史", exact=True),
            label="AI settings expander",
            timeout_ms=timeout_ms,
        )
        settings.click(timeout=timeout_ms)
        _wait_for_catalog_roots(page, roots, timeout_ms=timeout_ms)
        root_selector = ".st-key-ai_chat_mode"
        expected_option_count = _focused_control_option_count(
            capture_identity, root_selector
        )

        # Exercise the same deterministic state transition before and after the
        # segmented-control -> radio migration.  Pre-control starts blank while
        # the frozen radio pattern starts on Quick; Deep -> Quick produces two
        # real rerenders in either phase and ends at the contracted state.
        alternate_state = "深度研究"
        root = _wait_for_unique_visible(
            page.locator(root_selector),
            label="AI chat mode root",
            timeout_ms=timeout_ms,
        )
        role, alternate_choice, alternate_action = _exact_choice_locator(
            page,
            root,
            root_selector,
            alternate_state,
            expected_option_count=expected_option_count,
            timeout_ms=timeout_ms,
        )
        if _choice_is_selected(role, alternate_choice):
            raise WorkerBootstrapError("AI chat alternate mode is unexpectedly selected")
        generation = _selection_render_generation(
            page,
            capture_identity,
            timeout_ms=timeout_ms,
        )
        _click_choice(role, alternate_action, timeout_ms=timeout_ms)
        generation = _wait_for_selection_render_after(
            page,
            capture_identity,
            generation,
            timeout_ms=timeout_ms,
        )
        _assert_selected_choice(
            page,
            root_selector,
            alternate_state,
            expected_option_count=expected_option_count,
            timeout_ms=timeout_ms,
        )

        root = _wait_for_unique_visible(
            page.locator(root_selector),
            label="AI chat mode root after alternate",
            timeout_ms=timeout_ms,
        )
        role, choice, choice_action = _exact_choice_locator(
            page,
            root,
            root_selector,
            str(selected_state),
            expected_option_count=expected_option_count,
            timeout_ms=timeout_ms,
        )
        if _choice_is_selected(role, choice):
            raise WorkerBootstrapError("AI chat contracted mode changed without interaction")
        _click_choice(role, choice_action, timeout_ms=timeout_ms)
        _wait_for_selection_render_after(
            page,
            capture_identity,
            generation,
            timeout_ms=timeout_ms,
        )
        _assert_selected_choice(
            page,
            root_selector,
            str(selected_state),
            expected_option_count=expected_option_count,
            timeout_ms=timeout_ms,
        )
    elif action == "none":
        if selected_state is not None:
            raise WorkerBootstrapError("no-op focused interaction has business state")
        _wait_for_catalog_roots(page, roots, timeout_ms=timeout_ms)
    else:  # The immutable local catalog is closed above.
        raise WorkerBootstrapError("focused interaction action is unsupported")

    return {
        "schemaVersion": FOCUSED_INTERACTION_SCHEMA,
        "interactionId": contract["interactionId"],
        "action": action,
        "completed": True,
        "selectedBusinessState": selected_state,
    }


def _normalized_locator_text(locator: Any) -> str:
    return re.sub(r"\s+", " ", str(locator.inner_text())).strip()


def _rounded_rect(locator: Any, *, closest_label: bool = False) -> dict[str, float]:
    script = (
        "element => { const target=element.closest('label') || element.parentElement || element;"
        if closest_label
        else "element => { const target=element;"
    )
    raw = locator.evaluate(
        script
        + " const rect=target.getBoundingClientRect();"
        " return {x:rect.x,y:rect.y,width:rect.width,height:rect.height}; }"
    )
    if not isinstance(raw, dict) or set(raw) != {"x", "y", "width", "height"}:
        raise WorkerBootstrapError("focused control geometry is malformed")
    try:
        return {key: round(float(raw[key]), 3) for key in raw}
    except (TypeError, ValueError) as exc:
        raise WorkerBootstrapError("focused control geometry is malformed") from exc


def _rect_inside(inner: Mapping[str, float], outer: Mapping[str, float]) -> bool:
    tolerance = 1.0
    return (
        inner["x"] >= outer["x"] - tolerance
        and inner["y"] >= outer["y"] - tolerance
        and inner["x"] + inner["width"]
        <= outer["x"] + outer["width"] + tolerance
        and inner["y"] + inner["height"]
        <= outer["y"] + outer["height"] + tolerance
    )


def _geometry_decimal(value: float) -> Decimal:
    return Decimal(str(value))


def _rects_overlap(
    first: Mapping[str, float],
    second: Mapping[str, float],
    *,
    tolerance: float,
) -> bool:
    first_x = _geometry_decimal(first["x"])
    first_y = _geometry_decimal(first["y"])
    first_right = first_x + _geometry_decimal(first["width"])
    first_bottom = first_y + _geometry_decimal(first["height"])
    second_x = _geometry_decimal(second["x"])
    second_y = _geometry_decimal(second["y"])
    second_right = second_x + _geometry_decimal(second["width"])
    second_bottom = second_y + _geometry_decimal(second["height"])
    allowed = _geometry_decimal(tolerance)
    return (
        min(first_right, second_right) - max(first_x, second_x) > allowed
        and min(first_bottom, second_bottom) - max(first_y, second_y) > allowed
    )


_DOCUMENT_FONT_READY_SCRIPT = """
() => {
  const fonts = document.fonts;
  if (!fonts) return true;
  const ready = fonts.ready;
  if (!ready || typeof ready.then !== 'function') return false;
  return ready.then(() => true, () => false);
}
"""


_FOCUSED_SCROLL_STATE_SCRIPT = """
({root, targets}) => {
  if (!root || !root.isConnected || !Array.isArray(targets) ||
      targets.some(target => !target || !target.isConnected || !root.contains(target))) {
    throw new Error('focused layout retained nodes are invalid');
  }
  const nodes = [];
  for (let node = root; node; node = node.parentElement) nodes.push(node);
  const scrollingElement = document.scrollingElement;
  if (scrollingElement && !nodes.includes(scrollingElement)) nodes.push(scrollingElement);
  return {
    root,
    targets,
    scrollingElement,
    entries: nodes.map(node => ({
      node,
      left: node.scrollLeft,
      top: node.scrollTop,
      clientWidth: node.clientWidth,
      clientHeight: node.clientHeight,
      scrollWidth: node.scrollWidth,
      scrollHeight: node.scrollHeight
    }))
  };
}
"""


_FOCUSED_SCROLL_STATE_SNAPSHOT_SCRIPT = """
state => {
  const nodes = [];
  for (let node = state.root; node; node = node.parentElement) nodes.push(node);
  const scrollingElement = document.scrollingElement;
  if (scrollingElement && !nodes.includes(scrollingElement)) nodes.push(scrollingElement);
  const entries = state.entries.map(entry => ({
    left: entry.node.scrollLeft,
    top: entry.node.scrollTop,
    clientWidth: entry.node.clientWidth,
    clientHeight: entry.node.clientHeight,
    scrollWidth: entry.node.scrollWidth,
    scrollHeight: entry.node.scrollHeight
  }));
  return {
    rootConnected: !!state.root.isConnected,
    targetCount: state.targets.length,
    targetsConnected: state.targets.every(target => !!target.isConnected),
    targetsContained: state.targets.every(target => state.root.contains(target)),
    chainMatches: nodes.length === state.entries.length &&
      nodes.every((node, index) => node === state.entries[index].node),
    scrollingMatches: scrollingElement === state.scrollingElement,
    horizontalMatches: entries.every(
      (entry, index) => entry.left === state.entries[index].left
    ),
    offsetsMatch: entries.every(
      (entry, index) => entry.left === state.entries[index].left &&
        entry.top === state.entries[index].top
    ),
    metricsMatch: entries.every(
      (entry, index) => entry.clientWidth === state.entries[index].clientWidth &&
        entry.clientHeight === state.entries[index].clientHeight &&
        entry.scrollWidth === state.entries[index].scrollWidth &&
        entry.scrollHeight === state.entries[index].scrollHeight
    ),
    entries
  };
}
"""


_FOCUSED_RESTORE_SCROLL_SCRIPT = """
(state, horizontalOnly) => {
  for (const entry of [...state.entries].reverse()) {
    entry.node.scrollLeft = entry.left;
    if (!horizontalOnly) entry.node.scrollTop = entry.top;
  }
  return true;
}
"""


def _focused_layout_deadlines(timeout_ms: int) -> tuple[float, float]:
    if (
        not isinstance(timeout_ms, int)
        or isinstance(timeout_ms, bool)
        or timeout_ms <= 0
    ):
        raise WorkerBootstrapError("focused control layout timeout is invalid")
    cleanup_ms = min(5_000, max(50, timeout_ms // 3))
    audit_ms = max(1, timeout_ms - cleanup_ms)
    started = time.monotonic()
    return started + audit_ms / 1_000, started + timeout_ms / 1_000


def _focused_remaining_timeout_ms(deadline: float, *, label: str) -> int:
    remaining = int((deadline - time.monotonic()) * 1_000)
    if remaining <= 0:
        raise WorkerBootstrapError(f"{label} did not complete within its bound")
    return remaining


def _dispose_focused_handle(handle: Any, *, label: str) -> None:
    try:
        handle.dispose()
    except Exception as exc:
        raise WorkerBootstrapError(f"{label} could not be released") from exc


def _wait_for_focused_predicate(
    page: Any,
    script: str,
    *,
    deadline: float,
    label: str,
) -> None:
    handle = None
    try:
        handle = page.wait_for_function(
            script,
            timeout=_focused_remaining_timeout_ms(deadline, label=label),
        )
    except WorkerBootstrapError:
        raise
    except Exception as exc:
        raise WorkerBootstrapError(f"{label} did not stabilize") from exc
    finally:
        if handle is not None:
            _dispose_focused_handle(handle, label=f"{label} wait handle")


def _wait_for_focused_layout_prerequisites(
    page: Any,
    *,
    deadline: float,
) -> None:
    _wait_for_focused_predicate(
        page,
        _DOCUMENT_FONT_READY_SCRIPT,
        deadline=deadline,
        label="focused control fonts",
    )
    for script, label in (
        (_READINESS_SCRIPT, "focused control readiness"),
        (_STABLE_LAYOUT_SCRIPT, "focused control document geometry"),
    ):
        _wait_for_focused_predicate(
            page,
            script,
            deadline=deadline,
            label=label,
        )


def _wait_for_document_fonts(
    page: Any,
    *,
    timeout_ms: int,
    label: str,
) -> None:
    if (
        not isinstance(timeout_ms, int)
        or isinstance(timeout_ms, bool)
        or timeout_ms <= 0
    ):
        raise WorkerBootstrapError(f"{label} timeout is invalid")
    _wait_for_focused_predicate(
        page,
        _DOCUMENT_FONT_READY_SCRIPT,
        deadline=time.monotonic() + timeout_ms / 1_000,
        label=label,
    )


def _wait_for_focused_document_stability(
    page: Any,
    *,
    deadline: float,
) -> None:
    _wait_for_focused_predicate(
        page,
        _STABLE_LAYOUT_SCRIPT,
        deadline=deadline,
        label="focused control restored document geometry",
    )


def _focused_scroll_number(value: object, *, label: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not Decimal(str(value)).is_finite()
    ):
        raise WorkerBootstrapError(f"{label} is malformed")
    return float(value)


def _focused_scroll_state_snapshot(state_handle: Any) -> dict[str, Any]:
    try:
        raw = state_handle.evaluate(_FOCUSED_SCROLL_STATE_SNAPSHOT_SCRIPT)
    except Exception as exc:
        raise WorkerBootstrapError(
            "focused control retained scroll state is unavailable"
        ) from exc
    expected_keys = {
        "rootConnected",
        "targetCount",
        "targetsConnected",
        "targetsContained",
        "chainMatches",
        "scrollingMatches",
        "horizontalMatches",
        "offsetsMatch",
        "metricsMatch",
        "entries",
    }
    if not isinstance(raw, dict) or set(raw) != expected_keys:
        raise WorkerBootstrapError("focused control retained scroll state is malformed")
    boolean_keys = expected_keys - {"targetCount", "entries"}
    if any(not isinstance(raw[key], bool) for key in boolean_keys):
        raise WorkerBootstrapError("focused control retained scroll state is malformed")
    if (
        not isinstance(raw["targetCount"], int)
        or isinstance(raw["targetCount"], bool)
        or not isinstance(raw["entries"], list)
        or not raw["entries"]
    ):
        raise WorkerBootstrapError("focused control retained scroll state is malformed")
    entries: list[dict[str, float]] = []
    entry_keys = {
        "left",
        "top",
        "clientWidth",
        "clientHeight",
        "scrollWidth",
        "scrollHeight",
    }
    for index, entry in enumerate(raw["entries"]):
        if not isinstance(entry, dict) or set(entry) != entry_keys:
            raise WorkerBootstrapError(
                "focused control retained scroll entry is malformed"
            )
        entries.append(
            {
                key: _focused_scroll_number(
                    entry[key], label=f"focused control scroll entry {index}.{key}"
                )
                for key in sorted(entry_keys)
            }
        )
    return {
        **{key: raw[key] for key in sorted(boolean_keys)},
        "targetCount": raw["targetCount"],
        "entries": entries,
    }


def _focused_control_layout_snapshot(
    page: Any,
    state_handle: Any,
    root_handle: Any,
    target_handles: Sequence[Any],
    labels: Sequence[str],
    *,
    closest_label: bool,
) -> dict[str, Any]:
    if len(target_handles) != len(labels):
        raise WorkerBootstrapError("focused control target handles differ")
    root_rect = _rounded_rect(root_handle)
    dimensions = root_handle.evaluate(
        "element => ({clientWidth:element.clientWidth,"
        "scrollWidth:element.scrollWidth,clientHeight:element.clientHeight,"
        "scrollHeight:element.scrollHeight})"
    )
    document = page.evaluate(
        "() => ({clientWidth:document.documentElement.clientWidth,"
        "scrollWidth:Math.max(document.documentElement.scrollWidth,"
        "document.body ? document.body.scrollWidth : 0),"
        "clientHeight:document.documentElement.clientHeight,"
        "scrollHeight:Math.max(document.documentElement.scrollHeight,"
        "document.body ? document.body.scrollHeight : 0)})"
    )
    dimension_keys = {
        "clientWidth",
        "scrollWidth",
        "clientHeight",
        "scrollHeight",
    }
    if (
        not isinstance(dimensions, dict)
        or set(dimensions) != dimension_keys
        or not isinstance(document, dict)
        or set(document) != dimension_keys
        or any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in (*dimensions.values(), *document.values())
        )
    ):
        raise WorkerBootstrapError("focused control overflow evidence is malformed")
    target_rows = [
        {
            "label": label,
            **_rounded_rect(handle, closest_label=closest_label),
        }
        for label, handle in zip(labels, target_handles, strict=True)
    ]
    return {
        "rootRect": root_rect,
        "targets": target_rows,
        "rootDimensions": dict(dimensions),
        "document": dict(document),
        "scrollState": _focused_scroll_state_snapshot(state_handle),
    }


def _wait_for_stable_focused_layout_snapshot(
    page: Any,
    state_handle: Any,
    root_handle: Any,
    target_handles: Sequence[Any],
    labels: Sequence[str],
    *,
    closest_label: bool,
    deadline: float,
) -> dict[str, Any]:
    previous: dict[str, Any] | None = None
    while True:
        try:
            current = _focused_control_layout_snapshot(
                page,
                state_handle,
                root_handle,
                target_handles,
                labels,
                closest_label=closest_label,
            )
        except WorkerBootstrapError:
            raise
        except Exception as exc:
            raise WorkerBootstrapError(
                "focused control geometry snapshot is unavailable"
            ) from exc
        if previous == current:
            return current
        previous = current
        try:
            page.wait_for_timeout(
                min(
                    50,
                    _focused_remaining_timeout_ms(
                        deadline,
                        label="focused control geometry",
                    ),
                )
            )
        except WorkerBootstrapError:
            raise WorkerBootstrapError(
                "focused control geometry did not stabilize"
            ) from None
        except Exception as exc:
            raise WorkerBootstrapError(
                "focused control geometry did not stabilize"
            ) from exc


def _require_focused_scroll_state(
    snapshot: Mapping[str, Any],
    *,
    target_count: int,
    require_all_offsets: bool,
) -> None:
    required = (
        "rootConnected",
        "targetsConnected",
        "targetsContained",
        "chainMatches",
        "scrollingMatches",
        "horizontalMatches",
        "metricsMatch",
    )
    if (
        snapshot.get("targetCount") != target_count
        or any(snapshot.get(key) is not True for key in required)
        or (require_all_offsets and snapshot.get("offsetsMatch") is not True)
    ):
        raise WorkerBootstrapError("focused control retained scroll state changed")


def _restore_focused_scroll(
    state_handle: Any,
    *,
    horizontal_only: bool,
) -> None:
    try:
        restored = state_handle.evaluate(
            _FOCUSED_RESTORE_SCROLL_SCRIPT,
            horizontal_only,
        )
    except Exception as exc:
        raise WorkerBootstrapError("focused control scroll restoration failed") from exc
    if restored is not True:
        raise WorkerBootstrapError("focused control scroll restoration failed")


def _validate_focused_control_layout_snapshot(
    snapshot: Mapping[str, Any],
    *,
    viewport_width: int,
    viewport_height: int,
    target_overlap_tolerance: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root_rect = dict(snapshot["rootRect"])
    target_rows = [dict(row) for row in snapshot["targets"]]
    dimensions = dict(snapshot["rootDimensions"])
    document = dict(snapshot["document"])
    target_clipping = any(
        not _rect_inside(target, root_rect)
        or target["x"] < -1.0
        or target["x"] + target["width"] > viewport_width + 1.0
        or target["y"] < -1.0
        or target["y"] + target["height"] > viewport_height + 1.0
        for target in target_rows
    )
    target_overlap = any(
        _rects_overlap(
            target,
            other,
            tolerance=target_overlap_tolerance,
        )
        for index, target in enumerate(target_rows)
        for other in target_rows[index + 1 :]
    )
    layout = {
        "rootRect": root_rect,
        "viewportWidth": viewport_width,
        "viewportHeight": viewport_height,
        "targetOverlapTolerance": target_overlap_tolerance,
        "documentClientWidth": int(document["clientWidth"]),
        "documentScrollWidth": int(document["scrollWidth"]),
        "rootClientWidth": int(dimensions["clientWidth"]),
        "rootScrollWidth": int(dimensions["scrollWidth"]),
        "rootClipping": (
            root_rect["x"] < -1.0
            or root_rect["x"] + root_rect["width"] > viewport_width + 1.0
            or root_rect["y"] < -1.0
            or root_rect["y"] + root_rect["height"] > viewport_height + 1.0
        ),
        "targetClipping": target_clipping,
        "targetOverlap": target_overlap,
        "documentHorizontalOverflow": (
            int(document["scrollWidth"]) > int(document["clientWidth"]) + 1
        ),
        "rootHorizontalOverflow": (
            int(dimensions["scrollWidth"]) > int(dimensions["clientWidth"]) + 1
        ),
    }
    failed_layout_checks = tuple(
        key
        for key in (
            "rootClipping",
            "targetClipping",
            "targetOverlap",
            "documentHorizontalOverflow",
            "rootHorizontalOverflow",
        )
        if layout[key]
    )
    if failed_layout_checks:
        raise WorkerBootstrapError("focused control layout contract failed")
    return target_rows, layout


def _focused_control_layout(
    page: Any,
    root: Any,
    targets: Sequence[tuple[str, Any]],
    *,
    viewport_width: int,
    viewport_height: int,
    target_overlap_tolerance: float,
    closest_label: bool,
    trial_click_targets: bool = False,
    before_layout_audit: Callable[[float], None] | None = None,
    timeout_ms: int = 5_000,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if before_layout_audit is not None and not callable(before_layout_audit):
        raise WorkerBootstrapError("focused control layout audit callback is invalid")
    audit_deadline, cleanup_deadline = _focused_layout_deadlines(timeout_ms)
    labels = tuple(str(label) for label, _locator in targets)
    root_handle = None
    target_handles: list[Any] = []
    state_handle = None
    pre_snapshot: dict[str, Any] | None = None
    result: tuple[list[dict[str, Any]], dict[str, Any]] | None = None
    primary_error: BaseException | None = None
    cleanup_error: BaseException | None = None
    try:
        root_handle = root.element_handle(
            timeout=_focused_remaining_timeout_ms(
                audit_deadline,
                label="focused control root retention",
            )
        )
        if root_handle is None:
            raise WorkerBootstrapError("focused control root could not be retained")
        for _label, locator in targets:
            handle = locator.element_handle(
                timeout=_focused_remaining_timeout_ms(
                    audit_deadline,
                    label="focused control target retention",
                )
            )
            if handle is None:
                raise WorkerBootstrapError("focused control target could not be retained")
            target_handles.append(handle)

        _wait_for_focused_layout_prerequisites(
            page,
            deadline=audit_deadline,
        )
        try:
            state_handle = page.evaluate_handle(
                _FOCUSED_SCROLL_STATE_SCRIPT,
                {"root": root_handle, "targets": target_handles},
            )
        except Exception as exc:
            raise WorkerBootstrapError(
                "focused control scroll state could not be retained"
            ) from exc
        pre_snapshot = _wait_for_stable_focused_layout_snapshot(
            page,
            state_handle,
            root_handle,
            target_handles,
            labels,
            closest_label=closest_label,
            deadline=audit_deadline,
        )
        _require_focused_scroll_state(
            pre_snapshot["scrollState"],
            target_count=len(target_handles),
            require_all_offsets=True,
        )
        try:
            root_handle.scroll_into_view_if_needed(
                timeout=_focused_remaining_timeout_ms(
                    audit_deadline,
                    label="focused control audit scroll",
                )
            )
        except WorkerBootstrapError:
            raise
        except Exception as exc:
            raise WorkerBootstrapError(
                "focused control root could not enter the audit viewport"
            ) from exc
        _restore_focused_scroll(state_handle, horizontal_only=True)
        _wait_for_focused_layout_prerequisites(
            page,
            deadline=audit_deadline,
        )
        if before_layout_audit is not None:
            _require_focused_scroll_state(
                _focused_scroll_state_snapshot(state_handle),
                target_count=len(target_handles),
                require_all_offsets=False,
            )
            before_layout_audit(audit_deadline)
            _restore_focused_scroll(state_handle, horizontal_only=True)
            _wait_for_focused_layout_prerequisites(
                page,
                deadline=audit_deadline,
            )
        if trial_click_targets:
            for target_handle in target_handles:
                try:
                    target_handle.click(
                        trial=True,
                        timeout=_focused_remaining_timeout_ms(
                            audit_deadline,
                            label="focused control target actionability",
                        ),
                    )
                except WorkerBootstrapError:
                    raise
                except Exception as exc:
                    raise WorkerBootstrapError(
                        "focused control target is not actionable"
                    ) from exc
            _restore_focused_scroll(state_handle, horizontal_only=True)
            _wait_for_focused_layout_prerequisites(
                page,
                deadline=audit_deadline,
            )
        audit_snapshot = _wait_for_stable_focused_layout_snapshot(
            page,
            state_handle,
            root_handle,
            target_handles,
            labels,
            closest_label=closest_label,
            deadline=audit_deadline,
        )
        _require_focused_scroll_state(
            audit_snapshot["scrollState"],
            target_count=len(target_handles),
            require_all_offsets=False,
        )
        result = _validate_focused_control_layout_snapshot(
            audit_snapshot,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            target_overlap_tolerance=target_overlap_tolerance,
        )
    except BaseException as exc:
        primary_error = exc

    if state_handle is not None:
        try:
            _restore_focused_scroll(state_handle, horizontal_only=False)
            _wait_for_focused_document_stability(
                page,
                deadline=cleanup_deadline,
            )
            post_snapshot = _wait_for_stable_focused_layout_snapshot(
                page,
                state_handle,
                root_handle,
                target_handles,
                labels,
                closest_label=closest_label,
                deadline=cleanup_deadline,
            )
            _require_focused_scroll_state(
                post_snapshot["scrollState"],
                target_count=len(target_handles),
                require_all_offsets=True,
            )
            if pre_snapshot is not None and post_snapshot != pre_snapshot:
                raise WorkerBootstrapError(
                    "focused control scroll restoration differs"
                )
        except BaseException as exc:
            restoration_error = WorkerBootstrapError(
                "focused control scroll restoration failed"
            )
            restoration_error.__cause__ = exc
            cleanup_error = restoration_error

    disposal_handles = [
        handle
        for handle in (
            state_handle,
            *reversed(target_handles),
            root_handle,
        )
        if handle is not None
    ]
    for handle in disposal_handles:
        try:
            _dispose_focused_handle(
                handle,
                label="focused control retained handle",
            )
        except BaseException as exc:
            if cleanup_error is None:
                cleanup_error = exc
            else:
                cleanup_error.add_note(
                    "focused control retained handle cleanup also failed: "
                    f"{type(exc).__name__}: {exc}"
                )

    if primary_error is not None:
        if cleanup_error is not None:
            primary_error.add_note(
                "focused control scroll restoration also failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )
            raise primary_error from cleanup_error
        raise primary_error
    if cleanup_error is not None:
        raise cleanup_error
    if result is None:
        raise WorkerBootstrapError("focused control layout result is unavailable")
    return result


def _focused_rerendering_scroll_audit(
    page: Any,
    root: Any,
    audit: Callable[[float, float], Any],
    *,
    timeout_ms: int,
) -> Any:
    """Run a rerendering control audit and restore its original scroll chain."""

    if not callable(audit):
        raise WorkerBootstrapError("focused rerendering audit callback is invalid")
    audit_deadline, cleanup_deadline = _focused_layout_deadlines(timeout_ms)
    root_handle = None
    anchor_handle = None
    current_root_handle = None
    state_handle = None
    pre_snapshot: dict[str, Any] | None = None
    result: Any = None
    primary_error: BaseException | None = None
    cleanup_error: BaseException | None = None
    try:
        root_handle = root.element_handle(
            timeout=_focused_remaining_timeout_ms(
                audit_deadline,
                label="focused rerendering root retention",
            )
        )
        if root_handle is None:
            raise WorkerBootstrapError(
                "focused rerendering root could not be retained"
            )
        anchor_handle = root_handle.evaluate_handle(
            "node => node.parentElement || document.body"
        )
        if anchor_handle.evaluate("node => !!node && node.isConnected") is not True:
            raise WorkerBootstrapError(
                "focused rerendering scroll anchor is unavailable"
            )
        state_handle = page.evaluate_handle(
            _FOCUSED_SCROLL_STATE_SCRIPT,
            {"root": anchor_handle, "targets": []},
        )
        pre_snapshot = _focused_scroll_state_snapshot(state_handle)
        _require_focused_scroll_state(
            pre_snapshot,
            target_count=0,
            require_all_offsets=True,
        )
        result = audit(audit_deadline, cleanup_deadline)
    except BaseException as exc:
        primary_error = exc

    if state_handle is not None:
        try:
            _restore_focused_scroll(state_handle, horizontal_only=False)
            _wait_for_focused_document_stability(
                page,
                deadline=cleanup_deadline,
            )
            post_snapshot = _focused_scroll_state_snapshot(state_handle)
            _require_focused_scroll_state(
                post_snapshot,
                target_count=0,
                require_all_offsets=True,
            )
            if root.count() != 1:
                raise WorkerBootstrapError(
                    "focused rerendering current root is not unique"
                )
            current_root_handle = root.element_handle(
                timeout=_focused_remaining_timeout_ms(
                    cleanup_deadline,
                    label="focused rerendering current root retention",
                )
            )
            if current_root_handle is None or current_root_handle.evaluate(
                "(node, anchor) => node.isConnected &&"
                " node.parentElement === anchor",
                anchor_handle,
            ) is not True:
                raise WorkerBootstrapError(
                    "focused rerendering current root changed scroll chain"
                )
            if pre_snapshot is not None and post_snapshot != pre_snapshot:
                raise WorkerBootstrapError(
                    "focused rerendering scroll restoration differs"
                )
        except BaseException as exc:
            restoration_error = WorkerBootstrapError(
                "focused rerendering scroll restoration failed"
            )
            restoration_error.__cause__ = exc
            cleanup_error = restoration_error

    for handle in (
        current_root_handle,
        state_handle,
        anchor_handle,
        root_handle,
    ):
        if handle is None:
            continue
        try:
            _dispose_focused_handle(
                handle,
                label="focused rerendering retained handle",
            )
        except BaseException as exc:
            if cleanup_error is None:
                cleanup_error = exc
            else:
                cleanup_error.add_note(
                    "focused rerendering handle cleanup also failed: "
                    f"{type(exc).__name__}: {exc}"
                )

    if primary_error is not None:
        if cleanup_error is not None:
            primary_error.add_note(
                "focused rerendering scroll restoration also failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )
            raise primary_error from cleanup_error
        raise primary_error
    if cleanup_error is not None:
        raise cleanup_error
    if result is None:
        raise WorkerBootstrapError("focused rerendering audit result is unavailable")
    return result


_STREAMLIT_TOOLTIP_HELP_SIGNATURE_SCRIPT = """
(node, expected) => {
  const root = node.closest(expected.rootSelector);
  const hover = node.parentElement;
  const icon = hover && hover.parentElement;
  const label = icon && icon.closest('label[data-testid="stWidgetLabel"]');
  const svg = node.children.length === 1 ? node.children[0] : null;
  const primary = root && root.querySelector(expected.primarySelector);
  const normalizedLabel = label && label.innerText.replace(/\s+/g, ' ').trim();
  return !!(
    root && root.matches('[data-testid="stElementContainer"]') &&
    root.querySelectorAll(expected.primarySelector).length === 1 &&
    root.querySelectorAll('label[data-testid="stWidgetLabel"]').length === 1 &&
    node.tagName === 'BUTTON' && node.type === 'button' &&
    node.getAttribute('aria-label') === expected.accessibleName &&
    node.textContent.trim() === '' &&
    hover && hover.matches('span[data-testid="stTooltipHoverTarget"]') &&
    icon && icon.matches('span[data-testid="stTooltipIcon"]') &&
    label && label.matches('label[data-testid="stWidgetLabel"]') &&
    normalizedLabel === expected.widgetLabel &&
    svg && svg.tagName.toLowerCase() === 'svg' &&
    svg.getAttribute('aria-hidden') === 'true' &&
    svg.getAttribute('focusable') === 'false' &&
    primary && label !== primary &&
    !!(label.compareDocumentPosition(primary) & Node.DOCUMENT_POSITION_FOLLOWING)
  );
}
"""


_STREAMLIT_SELECT_CLEAR_SIGNATURE_SCRIPT = """
(node, expected) => {
  const normalize = value => String(value ?? '').replace(/\\s+/g, ' ').trim();
  const root = node.closest(expected.rootSelector);
  const select = node.closest('[data-baseweb="select"]');
  const combobox = select && select.querySelector('[role="combobox"]');
  const title = node.children.length === 2 ? node.children[0] : null;
  const path = node.children.length === 2 ? node.children[1] : null;
  if (!(
    root && select && combobox &&
    document.querySelectorAll(expected.rootSelector).length === 1 &&
    root.querySelectorAll('[data-baseweb="select"]').length === 1 &&
    root.querySelector('[data-baseweb="select"]') === select &&
    select.querySelectorAll('[role="combobox"]').length === 1 &&
    node.tagName.toLowerCase() === 'svg' &&
    node.getAttribute('data-baseweb') === 'icon' &&
    node.getAttribute('role') === 'button' &&
    node.getAttribute('aria-label') === expected.accessibleName &&
    node.getAttribute('title') === expected.accessibleName &&
    node.getAttribute('viewBox') === '0 0 24 24' &&
    title && title.tagName.toLowerCase() === 'title' &&
    normalize(title.textContent) === expected.accessibleName &&
    path && path.tagName.toLowerCase() === 'path' &&
    !!(combobox.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING)
  )) return false;

  const chain = [];
  for (let current = node; current; current = current.parentElement) {
    chain.push(current);
    if (current === root) break;
  }
  if (chain[chain.length - 1] !== root) return false;
  if (chain.some(element => {
    const style = getComputedStyle(element);
    const ariaDisabled = normalize(
      element.getAttribute('aria-disabled')
    ).toLowerCase();
    const opacity = Number.parseFloat(style.opacity);
    return element.matches(':disabled') ||
      element.hasAttribute('disabled') ||
      element.inert === true || element.hasAttribute('inert') ||
      ariaDisabled === 'true' ||
      style.display === 'none' ||
      style.visibility === 'hidden' || style.visibility === 'collapse' ||
      !Number.isFinite(opacity) || opacity <= 0 ||
      style.pointerEvents === 'none';
  })) return false;
  const rect = node.getBoundingClientRect();
  return node.getClientRects().length > 0 && rect.width > 0 && rect.height > 0;
}
"""


_STREAMLIT_SELECT_COMBOBOX_SIGNATURE_SCRIPT = """
(node, expected) => {
  const root = node.closest(expected.rootSelector);
  const select = node.closest('[data-baseweb="select"]');
  if (!(
    node.tagName === 'INPUT' && node.type === 'text' && node.value === '' &&
    node.getAttribute('role') === 'combobox' &&
    node.getAttribute('aria-label') === expected.accessibleName &&
    node.getAttribute('aria-labelledby') === null &&
    node.getAttribute('aria-autocomplete') === 'list' &&
    node.getAttribute('aria-expanded') === 'false' &&
    node.getAttribute('aria-haspopup') === 'listbox' &&
    node.getAttribute('aria-controls') === null &&
    node.getAttribute('aria-disabled') === null &&
    node.getAttribute('aria-readonly') === null &&
    node.getAttribute('aria-required') === null &&
    node.getAttribute('aria-invalid') === null &&
    node.getAttribute('readonly') === null && !node.readOnly &&
    node.getAttribute('required') === null && !node.required &&
    node.getAttribute('contenteditable') === null && !node.isContentEditable &&
    node.tabIndex === 0 && !node.disabled &&
    root && select &&
    document.querySelectorAll(expected.rootSelector).length === 1 &&
    root.querySelectorAll('[data-baseweb="select"]').length === 1 &&
    root.querySelector('[data-baseweb="select"]') === select &&
    select.querySelectorAll('[role="combobox"]').length === 1 &&
    select.querySelector('[role="combobox"]') === node
  )) return false;

  const chain = [];
  for (let current = node; current; current = current.parentElement) {
    chain.push(current);
    if (current === root) break;
  }
  if (chain[chain.length - 1] !== root) return false;
  if (chain.some(element => {
    const style = getComputedStyle(element);
    const opacity = Number.parseFloat(style.opacity);
    return element.matches(':disabled') ||
      element.hasAttribute('disabled') ||
      element.inert === true || element.hasAttribute('inert') ||
      element.getAttribute('aria-disabled') === 'true' ||
      style.display === 'none' ||
      style.visibility === 'hidden' || style.visibility === 'collapse' ||
      !Number.isFinite(opacity) || opacity <= 0 ||
      style.pointerEvents === 'none';
  })) return false;
  const rect = node.getBoundingClientRect();
  return node.getClientRects().length > 0 && rect.width > 0 && rect.height > 0;
}
"""


_STREAMLIT_SELECT_DROPDOWN_SIGNATURE_SCRIPT = """
(node, expected) => {
  const popover = node.closest('[data-baseweb="popover"]');
  const options = Array.from(node.querySelectorAll('[role="option"]'));
  const optionIds = options.map(option => option.id);
  if (!(
    node.tagName === 'UL' &&
    node.getAttribute('data-testid') === 'stSelectboxVirtualDropdown' &&
    node.getAttribute('role') === null &&
    popover &&
    document.querySelectorAll('[data-baseweb="popover"]').length === 1 &&
    document.querySelector('[data-baseweb="popover"]') === popover &&
    document.querySelectorAll(
      'ul[data-testid="stSelectboxVirtualDropdown"]'
    ).length === 1 &&
    popover.querySelectorAll(
      'ul[data-testid="stSelectboxVirtualDropdown"]'
    ).length === 1 &&
    popover.querySelector(
      'ul[data-testid="stSelectboxVirtualDropdown"]'
    ) === node &&
    options.length === expected.optionCount &&
    optionIds.every(id => typeof id === 'string' && id.length > 0) &&
    new Set(optionIds).size === optionIds.length &&
    options.every(option => {
      if (!(
        option.tagName === 'LI' &&
        option.getAttribute('role') === 'option' &&
        option.getAttribute('aria-label') === null &&
        option.getAttribute('aria-labelledby') === null &&
        option.getAttribute('title') === null &&
        option.getAttribute('aria-disabled') === 'false' &&
        option.getAttribute('tabindex') === null && option.tabIndex === -1 &&
        option.querySelectorAll(
          'button,a[href],input,select,textarea,summary,iframe,object,embed,' +
          'audio[controls],video[controls],[role],[tabindex],' +
          '[contenteditable]:not([contenteditable="false"])'
        ).length === 0 &&
        ['true', 'false'].includes(option.getAttribute('aria-selected')) &&
        node.contains(option)
      )) return false;
      const optionDescendants = Array.from(option.querySelectorAll('*'));
      if (optionDescendants.some(element => {
        const style = getComputedStyle(element);
        const opacity = Number.parseFloat(style.opacity);
        return element.hasAttribute('hidden') ||
          element.inert === true || element.hasAttribute('inert') ||
          element.hasAttribute('aria-label') ||
          element.hasAttribute('aria-labelledby') ||
          element.hasAttribute('aria-hidden') ||
          element.hasAttribute('title') || element.hasAttribute('alt') ||
          style.display === 'none' ||
          style.visibility === 'hidden' || style.visibility === 'collapse' ||
          !Number.isFinite(opacity) || opacity <= 0 ||
          style.pointerEvents === 'none';
      })) return false;
      const optionChain = [];
      for (let current = option; current; current = current.parentElement) {
        optionChain.push(current);
        if (current === node) break;
      }
      if (optionChain[optionChain.length - 1] !== node) return false;
      if (optionChain.some(element => {
        const style = getComputedStyle(element);
        const opacity = Number.parseFloat(style.opacity);
        return element.inert === true || element.hasAttribute('inert') ||
          element.getAttribute('aria-hidden') === 'true' ||
          style.display === 'none' ||
          style.visibility === 'hidden' || style.visibility === 'collapse' ||
          !Number.isFinite(opacity) || opacity <= 0 ||
          style.pointerEvents === 'none';
      })) return false;
      const optionRect = option.getBoundingClientRect();
      return option.getClientRects().length > 0 &&
        optionRect.width > 0 && optionRect.height > 0;
    }) &&
    options.filter(option => option.getAttribute('aria-selected') === 'true').length === 1 &&
    options.findIndex(
      option => option.getAttribute('aria-selected') === 'true'
    ) === expected.selectedIndex
  )) return false;

  const chain = [];
  for (let current = node; current; current = current.parentElement) {
    chain.push(current);
    if (current === popover) break;
  }
  if (chain[chain.length - 1] !== popover) return false;
  if (chain.some(element => {
    const style = getComputedStyle(element);
    const opacity = Number.parseFloat(style.opacity);
    return element.inert === true || element.hasAttribute('inert') ||
      element.getAttribute('aria-hidden') === 'true' ||
      style.display === 'none' ||
      style.visibility === 'hidden' || style.visibility === 'collapse' ||
      !Number.isFinite(opacity) || opacity <= 0 ||
      style.pointerEvents === 'none';
  })) return false;
  const rect = node.getBoundingClientRect();
  return node.getClientRects().length > 0 && rect.width > 0 && rect.height > 0;
}
"""


_FOCUSED_SELECTBOX_PRECOMMIT_QUIET_MS = 250
_FOCUSED_SELECTBOX_PRECOMMIT_POLL_MS = 50


_STREAMLIT_SELECT_PRECOMMIT_STATE_SCRIPT = """
(node, expected) => {
  const normalize = value => String(value ?? '').replace(/\s+/g, ' ').trim();
  const dropdown = expected.dropdown;
  const root = node.closest(expected.rootSelector);
  const select = node.closest('[data-baseweb="select"]');
  const popover = dropdown && dropdown.closest('[data-baseweb="popover"]');
  const marker = document.getElementById('ux1b-selection-ready');
  const options = dropdown
    ? Array.from(dropdown.querySelectorAll('[role="option"]')) : [];
  const optionIds = options.map(option => option.id);
  const selectedOption = options[expected.selectedIndex] || null;
  const visible = element => {
    if (!(element instanceof Element)) return false;
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    const opacity = Number.parseFloat(style.opacity);
    return style.display !== 'none' &&
      style.visibility !== 'hidden' && style.visibility !== 'collapse' &&
      Number.isFinite(opacity) && opacity > 0 &&
      element.getClientRects().length > 0 && rect.width > 0 && rect.height > 0;
  };
  const safeChain = (start, stop, popupChain) => {
    const chain = [];
    for (let current = start; current; current = current.parentElement) {
      chain.push(current);
      if (current === stop) break;
    }
    if (!stop || chain[chain.length - 1] !== stop) return false;
    return chain.every(element => {
      const style = getComputedStyle(element);
      const opacity = Number.parseFloat(style.opacity);
      return element.inert !== true && !element.hasAttribute('inert') &&
        element.getAttribute('aria-hidden') !== 'true' &&
        (popupChain || (
          !element.matches(':disabled') &&
          !element.hasAttribute('disabled') &&
          element.getAttribute('aria-disabled') !== 'true'
        )) &&
        style.display !== 'none' &&
        style.visibility !== 'hidden' && style.visibility !== 'collapse' &&
        Number.isFinite(opacity) && opacity > 0 &&
      style.pointerEvents !== 'none';
    });
  };
  const safeOptionDescendants = option =>
    Array.from(option.querySelectorAll('*')).every(element => {
      const style = getComputedStyle(element);
      const opacity = Number.parseFloat(style.opacity);
      return !element.hasAttribute('hidden') &&
        element.inert !== true && !element.hasAttribute('inert') &&
        !element.hasAttribute('aria-label') &&
        !element.hasAttribute('aria-labelledby') &&
        !element.hasAttribute('aria-hidden') &&
        !element.hasAttribute('title') && !element.hasAttribute('alt') &&
        style.display !== 'none' &&
        style.visibility !== 'hidden' && style.visibility !== 'collapse' &&
        Number.isFinite(opacity) && opacity > 0 &&
        style.pointerEvents !== 'none';
    });
  const animations = popover && typeof popover.getAnimations === 'function'
    ? popover.getAnimations({subtree: true}) : [];
  const motionFree = animations.every(
    animation => !['pending', 'running'].includes(animation.playState)
  );
  const generationExact = !!(
    marker &&
    document.querySelectorAll('#ux1b-selection-ready').length === 1 &&
    marker.getAttribute('data-capture-id') === expected.captureId &&
    marker.getAttribute('data-render-generation') === String(expected.generation)
  );
  const exact = !!(
    node.isConnected && dropdown && dropdown.isConnected &&
    node.tagName === 'INPUT' && node.type === 'text' && node.value === '' &&
    node.getAttribute('role') === 'combobox' &&
    node.getAttribute('aria-label') === expected.accessibleName &&
    node.getAttribute('aria-labelledby') === null &&
    node.getAttribute('aria-autocomplete') === 'list' &&
    node.getAttribute('aria-expanded') === 'true' &&
    node.getAttribute('aria-haspopup') === 'listbox' &&
    node.getAttribute('aria-controls') === expected.controls &&
    node.getAttribute('aria-activedescendant') === selectedOption?.id &&
    node.getAttribute('aria-disabled') === null &&
    node.getAttribute('aria-readonly') === null &&
    node.getAttribute('aria-required') === null &&
    node.getAttribute('aria-invalid') === null &&
    node.getAttribute('readonly') === null && !node.readOnly &&
    node.getAttribute('required') === null && !node.required &&
    node.getAttribute('contenteditable') === null && !node.isContentEditable &&
    node.tabIndex === 0 && !node.disabled &&
    document.activeElement === node &&
    root && select &&
    document.querySelectorAll(expected.rootSelector).length === 1 &&
    root.querySelectorAll('[data-baseweb="select"]').length === 1 &&
    root.querySelector('[data-baseweb="select"]') === select &&
    select.querySelectorAll('[role="combobox"]').length === 1 &&
    select.querySelector('[role="combobox"]') === node &&
    document.getElementById(expected.controls) === null &&
    dropdown.tagName === 'UL' &&
    dropdown.getAttribute('data-testid') === 'stSelectboxVirtualDropdown' &&
    dropdown.getAttribute('role') === null &&
    popover &&
    document.querySelectorAll('[data-baseweb="popover"]').length === 1 &&
    document.querySelector('[data-baseweb="popover"]') === popover &&
    document.querySelectorAll(
      'ul[data-testid="stSelectboxVirtualDropdown"]'
    ).length === 1 &&
    document.querySelector(
      'ul[data-testid="stSelectboxVirtualDropdown"]'
    ) === dropdown &&
    !Array.from(document.querySelectorAll('[role="listbox"]')).some(visible) &&
    options.length === expected.labels.length &&
    options.every((option, index) =>
      option.tagName === 'LI' &&
      option.getAttribute('role') === 'option' &&
      option.getAttribute('aria-label') === null &&
      option.getAttribute('aria-labelledby') === null &&
      option.getAttribute('title') === null &&
      option.getAttribute('aria-disabled') === 'false' &&
      option.getAttribute('tabindex') === null && option.tabIndex === -1 &&
      option.querySelectorAll(
        'button,a[href],input,select,textarea,summary,iframe,object,embed,' +
        'audio[controls],video[controls],[role],[tabindex],' +
        '[contenteditable]:not([contenteditable="false"])'
      ).length === 0 &&
      option.getAttribute('aria-selected') ===
        String(index === expected.selectedIndex) &&
      normalize(option.textContent) === expected.labels[index] &&
      safeChain(option, dropdown, true) &&
      safeOptionDescendants(option) && visible(option)
    ) &&
    optionIds.every(id => typeof id === 'string' && id.length > 0) &&
    new Set(optionIds).size === optionIds.length &&
    selectedOption &&
    document.getElementById(selectedOption.id) === selectedOption &&
    Array.from(document.querySelectorAll('[id]')).filter(
      element => element.id === selectedOption.id
    ).length === 1 &&
    safeChain(node, root, false) &&
    safeChain(dropdown, popover, true) &&
    visible(node) && visible(dropdown)
  );
  return {exact, generationExact, motionFree};
}
"""


def _validate_focused_button_projection(
    root: Any,
    contract: Mapping[str, Any],
    *,
    legacy_options: bool,
    primary_selector: str,
    trial_click_internal: bool = False,
    timeout_ms: int,
) -> list[str]:
    """Require every descendant button to belong to one closed projection."""

    option_names = tuple(str(value) for value in contract["optionLabels"])
    auxiliary_names = tuple(str(value) for value in contract["auxiliaryButtons"])
    projected_option_names = option_names if legacy_options else ()
    internal_names = (
        (_SELECTBOX_CLEAR_ACCESSIBLE_NAME,)
        if not legacy_options and contract["replacementWidget"] == "selectbox"
        else ()
    )
    all_names = option_names + auxiliary_names + internal_names
    if len(set(all_names)) != len(all_names):
        raise WorkerBootstrapError("focused button catalog is ambiguous")
    buttons = root.get_by_role("button")
    if buttons.count() != len(projected_option_names) + len(auxiliary_names) + len(
        internal_names
    ):
        raise WorkerBootstrapError("focused button projection is incomplete")
    for name in option_names:
        expected = 1 if legacy_options else 0
        if root.get_by_role("button", name=name, exact=True).count() != expected:
            raise WorkerBootstrapError("focused option button projection differs")
    for name in auxiliary_names:
        auxiliary_locator = root.get_by_role("button", name=name, exact=True)
        if auxiliary_locator.count() != 1:
            raise WorkerBootstrapError("focused auxiliary button projection differs")
        auxiliary = _wait_for_unique_visible(
            auxiliary_locator,
            label="focused auxiliary button",
            timeout_ms=timeout_ms,
        )
        if not auxiliary.evaluate(
            _STREAMLIT_TOOLTIP_HELP_SIGNATURE_SCRIPT,
            {
                "rootSelector": str(contract["rootSelector"]),
                "primarySelector": primary_selector,
                "accessibleName": name,
                "widgetLabel": str(contract["accessibleName"]),
            },
        ):
            raise WorkerBootstrapError("focused auxiliary button signature differs")
    for name in internal_names:
        internal_locator = root.get_by_role("button", name=name, exact=True)
        if internal_locator.count() != 1:
            raise WorkerBootstrapError("focused internal button projection differs")
        internal = _wait_for_unique_visible(
            internal_locator,
            label="focused internal select button",
            timeout_ms=timeout_ms,
        )
        if not internal.evaluate(
            _STREAMLIT_SELECT_CLEAR_SIGNATURE_SCRIPT,
            {
                "rootSelector": str(contract["rootSelector"]),
                "accessibleName": name,
            },
        ):
            raise WorkerBootstrapError("focused internal button signature differs")
        if trial_click_internal:
            try:
                internal.click(trial=True, timeout=timeout_ms)
            except Exception as exc:
                raise WorkerBootstrapError(
                    "focused internal button is not actionable"
                ) from exc
    return list(auxiliary_names)


def _legacy_primary_projection(
    root: Any,
    contract: Mapping[str, Any],
    *,
    timeout_ms: int,
) -> tuple[Any, tuple[Any, ...]]:
    """Authenticate the one inner BaseWeb group and its complete option order."""

    options = tuple(str(value) for value in contract["optionLabels"])
    primary_locator = root.locator(
        '[data-baseweb="button-group"][role="radiogroup"]'
    )
    if (
        primary_locator.count() != 1
        or root.get_by_role("radiogroup").count() != 1
        or root.locator('input[type="radio"], [role="radio"]').count() != 0
        or root.locator('[data-baseweb="select"], [role="combobox"]').count()
        != 0
    ):
        raise WorkerBootstrapError("legacy focused primary group differs")
    primary = _wait_for_unique_visible(
        primary_locator,
        label="legacy focused primary group",
        timeout_ms=timeout_ms,
    )
    buttons = primary.get_by_role("button")
    if buttons.count() != len(options):
        raise WorkerBootstrapError("legacy focused primary option count differs")
    observed_labels = tuple(
        _normalized_locator_text(buttons.nth(index))
        for index in range(buttons.count())
    )
    if observed_labels != options:
        raise WorkerBootstrapError("legacy focused option labels differ")
    option_locators = tuple(
        _wait_for_unique_visible(
            primary.get_by_role("button", name=label, exact=True),
            label="legacy focused option",
            timeout_ms=timeout_ms,
        )
        for label in options
    )
    return primary, option_locators


def _legacy_control_evidence(
    page: Any,
    capture_identity: Mapping[str, Any],
    contract: Mapping[str, Any],
    *,
    timeout_ms: int,
) -> dict[str, Any]:
    selector = str(contract["rootSelector"])
    options = tuple(str(value) for value in contract["optionLabels"])
    selected = str(contract["selectedLabel"])
    root = _wait_for_unique_visible(
        page.locator(selector), label="legacy focused control root", timeout_ms=timeout_ms
    )
    auxiliary_buttons = _validate_focused_button_projection(
        root,
        contract,
        legacy_options=True,
        primary_selector='[data-baseweb="button-group"][role="radiogroup"]',
        timeout_ms=timeout_ms,
    )
    primary, option_locators = _legacy_primary_projection(
        root, contract, timeout_ms=timeout_ms
    )
    selected_labels = [
        label
        for label, option in zip(options, option_locators, strict=True)
        if _choice_is_selected("button", option)
    ]
    if selected_labels != [selected]:
        raise WorkerBootstrapError("legacy focused selected state differs")

    # Analytics is the only dynamic replacement.  Exercise the same second /
    # first transition here that the post-control combobox performs so exact
    # provider counters remain equal across the migration.
    if contract["replacementWidget"] == "selectbox":
        generation = _selection_render_generation(
            page, capture_identity, timeout_ms=timeout_ms
        )
        primary.get_by_role("button", name=options[1], exact=True).click(
            timeout=timeout_ms
        )
        generation = _wait_for_selection_render_after(
            page, capture_identity, generation, timeout_ms=timeout_ms
        )
        root = _wait_for_unique_visible(
            page.locator(selector),
            label="legacy focused control root after alternate",
            timeout_ms=timeout_ms,
        )
        _wait_for_focused_projection(
            page,
            root,
            contract,
            timeout_ms=timeout_ms,
            expected_projection="legacy-segmented",
            expected_selected=options[1],
        )
        auxiliary_buttons = _validate_focused_button_projection(
            root,
            contract,
            legacy_options=True,
            primary_selector='[data-baseweb="button-group"][role="radiogroup"]',
            timeout_ms=timeout_ms,
        )
        primary, option_locators = _legacy_primary_projection(
            root, contract, timeout_ms=timeout_ms
        )
        alternate_selected = [
            label
            for label, option in zip(options, option_locators, strict=True)
            if _choice_is_selected("button", option)
        ]
        if alternate_selected != [options[1]]:
            raise WorkerBootstrapError("legacy focused alternate state differs")
        primary.get_by_role("button", name=selected, exact=True).click(
            timeout=timeout_ms
        )
        _wait_for_selection_render_after(
            page, capture_identity, generation, timeout_ms=timeout_ms
        )
        root = _wait_for_unique_visible(
            page.locator(selector),
            label="legacy focused control root after restore",
            timeout_ms=timeout_ms,
        )
        _wait_for_focused_projection(
            page,
            root,
            contract,
            timeout_ms=timeout_ms,
            expected_projection="legacy-segmented",
            expected_selected=selected,
        )
        auxiliary_buttons = _validate_focused_button_projection(
            root,
            contract,
            legacy_options=True,
            primary_selector='[data-baseweb="button-group"][role="radiogroup"]',
            timeout_ms=timeout_ms,
        )
        primary, option_locators = _legacy_primary_projection(
            root, contract, timeout_ms=timeout_ms
        )
        restored_selected = [
            label
            for label, option in zip(options, option_locators, strict=True)
            if _choice_is_selected("button", option)
        ]
        if restored_selected != [selected]:
            raise WorkerBootstrapError("legacy focused restore state differs")

    targets, layout = _focused_control_layout(
        page,
        root,
        tuple(zip(options, option_locators)),
        viewport_width=int(capture_identity["viewport"]["width"]),
        viewport_height=int(capture_identity["viewport"]["height"]),
        target_overlap_tolerance=1.0,
        closest_label=False,
        timeout_ms=timeout_ms,
    )
    return {
        "sessionKey": contract["sessionKey"],
        "rootSelector": selector,
        "widget": "segmented_control",
        "role": "group",
        "accessibleName": contract["accessibleName"],
        "optionRole": "button",
        "optionLabels": list(options),
        "auxiliaryButtons": auxiliary_buttons,
        "selectedLabel": selected,
        "checkedLabels": [selected],
        "tabSequenceLabels": [],
        "afterArrowRight": None,
        "afterArrowLeft": None,
        "afterSpace": None,
        "afterArrowDown": None,
        "afterArrowUp": None,
        "targets": targets,
        "layout": layout,
        "selectionBasis": "segmented-buttons/one-active",
    }


_RADIO_EVENT_GUARD_SCRIPT = """
nodes => {
  if (!Array.isArray(nodes) || nodes.length === 0 || nodes.some(
    node => !node || !node.isConnected || node.__ux1bFocusedGuard
  )) throw new Error('focused radio guard cannot be installed');
  for (const node of nodes) {
    const stop = event => event.stopPropagation();
    node.__ux1bFocusedGuard = stop;
    for (const type of ['keydown', 'input', 'change', 'click']) {
      node.addEventListener(type, stop, true);
    }
  }
  return true;
}
"""


_RADIO_EVENT_UNGUARD_SCRIPT = """
nodes => {
  if (!Array.isArray(nodes) || nodes.length === 0 || nodes.some(
    node => !node || !node.__ux1bFocusedGuard
  )) throw new Error('focused radio guard is missing');
  for (const node of nodes) {
    const stop = node.__ux1bFocusedGuard;
    for (const type of ['keydown', 'input', 'change', 'click']) {
      node.removeEventListener(type, stop, true);
    }
    delete node.__ux1bFocusedGuard;
  }
  return true;
}
"""


def _radio_control_evidence(
    page: Any,
    capture_identity: Mapping[str, Any],
    contract: Mapping[str, Any],
    *,
    timeout_ms: int,
) -> dict[str, Any]:
    selector = str(contract["rootSelector"])
    options = tuple(str(value) for value in contract["optionLabels"])
    selected = str(contract["selectedLabel"])
    root = _wait_for_unique_visible(
        page.locator(selector), label="focused radio root", timeout_ms=timeout_ms
    )
    if (
        root.get_by_role("radiogroup").count() != 1
        or root.get_by_role("radio").count() != len(options)
        or root.get_by_role("combobox").count() != 0
        or root.locator(
            '[data-baseweb="select"], [role="combobox"],'
            ' [data-baseweb="button-group"]'
        ).count()
        != 0
    ):
        raise WorkerBootstrapError("focused radio primary projection differs")
    group = root.get_by_role(
        "radiogroup", name=str(contract["accessibleName"]), exact=True
    )
    group = _wait_for_unique_visible(
        group, label="focused radiogroup", timeout_ms=timeout_ms
    )
    auxiliary_buttons = _validate_focused_button_projection(
        root,
        contract,
        legacy_options=False,
        primary_selector='[role="radiogroup"]',
        timeout_ms=timeout_ms,
    )
    radios = group.get_by_role("radio")
    if radios.count() != len(options):
        raise WorkerBootstrapError("focused radio option count differs")
    observed_labels = tuple(
        re.sub(r"\s+", " ", str(label)).strip()
        for label in radios.evaluate_all(
            "nodes => nodes.map(node => {"
            " const label=node.labels && node.labels[0];"
            " return String(label ? label.innerText : node.value); })"
        )
    )
    if observed_labels != options:
        raise WorkerBootstrapError("focused radio option order differs")
    option_locators = tuple(
        group.get_by_role("radio", name=label, exact=True) for label in options
    )
    option_labels = tuple(
        _validated_radio_label(
            option,
            root_selector=selector,
            expected_label=label,
            expected_option_count=len(options),
            timeout_ms=timeout_ms,
        )
        for label, option in zip(options, option_locators, strict=True)
    )
    checked = [
        label for label, option in zip(options, option_locators) if option.is_checked()
    ]
    if checked != [selected]:
        raise WorkerBootstrapError("focused radio checked state differs")
    selected_index = options.index(selected)
    next_index = (selected_index + 1) % len(options)
    generation = _selection_render_generation(
        page, capture_identity, timeout_ms=timeout_ms
    )
    audit_result: dict[str, Any] = {}

    def audit_native_keyboard(audit_deadline: float) -> None:
        radio_handles: list[Any] = []
        guard_installed = False
        primary_error: BaseException | None = None
        cleanup_error: BaseException | None = None
        try:
            for option in option_locators:
                handle = option.element_handle(
                    timeout=_focused_remaining_timeout_ms(
                        audit_deadline,
                        label="focused radio retention",
                    )
                )
                if handle is None:
                    raise WorkerBootstrapError(
                        "focused radio option could not be retained"
                    )
                radio_handles.append(handle)
            for label, handle in zip(options, radio_handles, strict=True):
                if handle.evaluate(
                    _RADIO_LABEL_ASSOCIATION_SCRIPT,
                    {
                        "rootSelector": selector,
                        "label": label,
                        "optionCount": len(options),
                    },
                ) is not True:
                    raise WorkerBootstrapError(
                        "focused radio retained association differs"
                    )

            def require_static_radio_tree() -> None:
                if (
                    _selection_render_generation(
                        page,
                        capture_identity,
                        timeout_ms=_focused_remaining_timeout_ms(
                            audit_deadline,
                            label="focused radio generation check",
                        ),
                    )
                    != generation
                ):
                    raise WorkerBootstrapError(
                        "focused native radio audit rerendered the app"
                    )
                retained = page.evaluate(
                    "nodes => nodes.length > 0 && nodes.every(node => node.isConnected)",
                    radio_handles,
                )
                if retained is not True:
                    raise WorkerBootstrapError(
                        "focused native radio audit replaced its retained options"
                    )
                for label, handle in zip(options, radio_handles, strict=True):
                    if handle.evaluate(
                        _RADIO_LABEL_ASSOCIATION_SCRIPT,
                        {
                            "rootSelector": selector,
                            "label": label,
                            "optionCount": len(options),
                        },
                    ) is not True:
                        raise WorkerBootstrapError(
                            "focused radio retained association changed"
                        )

            require_static_radio_tree()
            selected_handle = radio_handles[selected_index]
            next_handle = radio_handles[next_index]

            selected_handle.focus()
            require_static_radio_tree()
            selected_handle.press(
                "Shift+Tab",
                timeout=_focused_remaining_timeout_ms(
                    audit_deadline,
                    label="focused radio predecessor tab check",
                ),
            )
            require_static_radio_tree()
            if selected_handle.evaluate(
                "node => { const group=node.closest('[role=\"radiogroup\"]');"
                " return !!group && !!document.activeElement &&"
                " group.contains(document.activeElement); }"
            ):
                raise WorkerBootstrapError(
                    "focused radio exposes a predecessor tab stop"
                )
            page.keyboard.press("Tab")
            require_static_radio_tree()
            tabbed_label = selected_handle.evaluate(
                "(node, rootSelector) => { const root=node.closest(rootSelector);"
                " const active=document.activeElement;"
                " if (!root || !active || !root.contains(active) ||"
                " active.type!=='radio') return null;"
                " const label=active.labels && active.labels[0];"
                " return String(label ? label.innerText : active.value)"
                " .replace(/\\s+/g,' ').trim(); }",
                selector,
            )
            if tabbed_label != selected:
                raise WorkerBootstrapError("focused radio roving tab stop differs")
            page.keyboard.press("Tab")
            require_static_radio_tree()
            if selected_handle.evaluate(
                "node => { const group=node.closest('[role=\"radiogroup\"]');"
                " return !!group && !!document.activeElement &&"
                " group.contains(document.activeElement); }"
            ):
                raise WorkerBootstrapError("focused radio exposes a second tab stop")

            page.evaluate(_RADIO_EVENT_GUARD_SCRIPT, radio_handles)
            guard_installed = True
            selected_handle.focus()
            require_static_radio_tree()
            selected_handle.press(
                "ArrowRight",
                timeout=_focused_remaining_timeout_ms(
                    audit_deadline,
                    label="focused radio ArrowRight check",
                ),
            )
            require_static_radio_tree()
            if not next_handle.is_checked():
                raise WorkerBootstrapError("focused radio ArrowRight behavior differs")
            next_handle.press(
                "ArrowLeft",
                timeout=_focused_remaining_timeout_ms(
                    audit_deadline,
                    label="focused radio ArrowLeft check",
                ),
            )
            require_static_radio_tree()
            if not selected_handle.is_checked():
                raise WorkerBootstrapError(
                    "focused radio ArrowLeft did not restore state"
                )
            selected_handle.press(
                "Space",
                timeout=_focused_remaining_timeout_ms(
                    audit_deadline,
                    label="focused radio Space check",
                ),
            )
            require_static_radio_tree()
            if not selected_handle.is_checked():
                raise WorkerBootstrapError(
                    "focused radio Space removed required state"
                )
            final_checked = [
                label
                for label, handle in zip(options, radio_handles, strict=True)
                if handle.is_checked()
            ]
            if final_checked != [selected]:
                raise WorkerBootstrapError(
                    "focused radio audit did not restore state"
                )
            audit_result["tabbedLabel"] = str(tabbed_label)
        except BaseException as exc:
            if isinstance(exc, (WorkerBootstrapError, KeyboardInterrupt)):
                primary_error = exc
            else:
                wrapped = WorkerBootstrapError("focused native radio audit failed")
                wrapped.__cause__ = exc
                primary_error = wrapped

        if guard_installed:
            try:
                page.evaluate(_RADIO_EVENT_UNGUARD_SCRIPT, radio_handles)
            except BaseException as exc:
                wrapped = WorkerBootstrapError(
                    "focused radio event guard could not be released"
                )
                wrapped.__cause__ = exc
                cleanup_error = wrapped
        for handle in reversed(radio_handles):
            try:
                _dispose_focused_handle(
                    handle,
                    label="focused radio retained option",
                )
            except BaseException as exc:
                if cleanup_error is None:
                    cleanup_error = exc
                else:
                    cleanup_error.add_note(
                        "focused radio retained option cleanup also failed: "
                        f"{type(exc).__name__}: {exc}"
                    )
        if primary_error is not None:
            if cleanup_error is not None:
                raise primary_error from cleanup_error
            raise primary_error
        if cleanup_error is not None:
            raise cleanup_error

    targets, layout = _focused_control_layout(
        page,
        root,
        tuple(zip(options, option_labels, strict=True)),
        viewport_width=int(capture_identity["viewport"]["width"]),
        viewport_height=int(capture_identity["viewport"]["height"]),
        target_overlap_tolerance=0.5,
        closest_label=False,
        trial_click_targets=True,
        before_layout_audit=audit_native_keyboard,
        timeout_ms=timeout_ms,
    )
    tabbed_label = audit_result.get("tabbedLabel")
    if tabbed_label != selected:
        raise WorkerBootstrapError("focused native radio audit result is unavailable")
    if (
        _selection_render_generation(page, capture_identity, timeout_ms=timeout_ms)
        != generation
    ):
        raise WorkerBootstrapError("focused native radio audit rerendered the app")
    return {
        "sessionKey": contract["sessionKey"],
        "rootSelector": selector,
        "widget": "radio_horizontal",
        "role": group.get_attribute("role"),
        "accessibleName": contract["accessibleName"],
        "optionRole": "radio",
        "optionLabels": list(options),
        "auxiliaryButtons": auxiliary_buttons,
        "selectedLabel": selected,
        "checkedLabels": checked,
        "tabSequenceLabels": [str(tabbed_label)],
        "afterArrowRight": options[next_index],
        "afterArrowLeft": selected,
        "afterSpace": selected,
        "afterArrowDown": None,
        "afterArrowUp": None,
        "targets": targets,
        "layout": layout,
        "selectionBasis": "native-radio/one-checked/roving-tabstop/keyboard",
    }


def _selectbox_text(root: Any) -> str:
    select_root = root.locator('[data-baseweb="select"]')
    if select_root.count() != 1:
        raise WorkerBootstrapError("focused selectbox rendered root differs")
    return _normalized_locator_text(select_root)


def _selectbox_accessible_name(
    contract: Mapping[str, Any], selected: str
) -> str:
    options = tuple(str(value) for value in contract["optionLabels"])
    if selected not in options:
        raise WorkerBootstrapError("focused selectbox selection is not contracted")
    return f"Selected {selected}. {contract['accessibleName']}"


def _focused_selectbox_combobox(
    root: Any,
    contract: Mapping[str, Any],
    selected: str,
    *,
    timeout_ms: int,
    label: str,
) -> Any:
    combobox = _wait_for_unique_visible(
        root.get_by_role(
            "combobox",
            name=_selectbox_accessible_name(contract, selected),
            exact=True,
        ),
        label=label,
        timeout_ms=timeout_ms,
    )
    if combobox.evaluate(
        _STREAMLIT_SELECT_COMBOBOX_SIGNATURE_SCRIPT,
        {
            "rootSelector": str(contract["rootSelector"]),
            "accessibleName": _selectbox_accessible_name(
                contract,
                selected,
            ),
        },
    ) is not True:
        raise WorkerBootstrapError("focused combobox signature differs")
    return combobox


def _require_focused_selectbox_popup_absent(page: Any) -> None:
    if (
        page.locator('ul[data-testid="stSelectboxVirtualDropdown"]').count() != 0
        or page.locator('[data-baseweb="popover"]').count() != 0
        or page.locator('[role="listbox"]:visible').count() != 0
    ):
        raise WorkerBootstrapError("focused selectbox popup was already present")


def _require_focused_selectbox_option_accessible_names(
    dropdown: Any,
    expected_labels: Sequence[str],
) -> None:
    """Bind every exact computed option name to its contracted DOM position."""

    labels = tuple(str(value) for value in expected_labels)
    options = dropdown.get_by_role("option")
    if options.count() != len(labels):
        raise WorkerBootstrapError(
            "focused selectbox option accessible names are incomplete"
        )
    for index, expected_label in enumerate(labels):
        named_option = dropdown.get_by_role(
            "option",
            name=expected_label,
            exact=True,
        )
        if (
            named_option.count() != 1
            or named_option.get_attribute("id")
            != options.nth(index).get_attribute("id")
        ):
            raise WorkerBootstrapError(
                "focused selectbox option accessible name differs"
            )


def _focused_selectbox_dropdown(
    page: Any,
    combobox: Any,
    *,
    option_count: int,
    expected_labels: Sequence[str],
    selected_index: int,
    timeout_ms: int,
) -> Any:
    labels = tuple(str(value) for value in expected_labels)
    if (
        len(labels) != option_count
        or len(set(labels)) != option_count
        or any(not label for label in labels)
        or type(selected_index) is not int
        or selected_index < 0
        or selected_index >= option_count
    ):
        raise WorkerBootstrapError("focused selectbox selected index is invalid")
    deadline = time.monotonic() + timeout_ms / 1_000
    if (
        combobox.get_attribute("aria-expanded") != "true"
        or combobox.get_attribute("aria-haspopup") != "listbox"
    ):
        raise WorkerBootstrapError("focused selectbox popup state differs")
    controls = combobox.get_attribute("aria-controls")
    if (
        not isinstance(controls, str)
        or not controls
        or re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", controls) is None
    ):
        raise WorkerBootstrapError("focused selectbox popup identity differs")
    if page.locator('[role="listbox"]:visible').count() != 0:
        raise WorkerBootstrapError("focused selectbox rendered an unknown listbox")
    try:
        dropdown = _wait_for_unique_visible(
            page.locator('ul[data-testid="stSelectboxVirtualDropdown"]'),
            label="focused selectbox dropdown",
            timeout_ms=_focused_remaining_timeout_ms(
                deadline,
                label="focused selectbox dropdown",
            ),
        )
    except WorkerBootstrapError:
        raise
    except Exception as exc:
        raise WorkerBootstrapError(
            "focused selectbox dropdown did not become uniquely visible"
        ) from exc
    while True:
        try:
            matches = dropdown.evaluate(
                _STREAMLIT_SELECT_DROPDOWN_SIGNATURE_SCRIPT,
                {
                    "optionCount": option_count,
                    "selectedIndex": selected_index,
                },
            )
        except Exception as exc:
            raise WorkerBootstrapError(
                "focused selectbox dropdown signature is unavailable"
            ) from exc
        if matches is True:
            break
        remaining_ms = _focused_remaining_timeout_ms(
            deadline,
            label="focused selectbox dropdown signature",
        )
        page.wait_for_timeout(min(50, remaining_ms))
    _require_focused_selectbox_option_accessible_names(dropdown, labels)
    return dropdown


def _restore_focused_selectbox_closed_state(
    page: Any,
    combobox_handle: Any,
    *,
    timeout_ms: int,
) -> None:
    """Use the retained native keyboard path to close one failed-open popup."""

    deadline = time.monotonic() + min(timeout_ms, 1_000) / 1_000
    expanded = combobox_handle.evaluate(
        "node => node.isConnected ? node.getAttribute('aria-expanded') : null"
    )
    if expanded not in {"true", "false"}:
        raise WorkerBootstrapError(
            "focused selectbox failed-open control is unavailable"
        )
    if expanded == "true":
        active = combobox_handle.evaluate(
            "node => { node.focus({preventScroll:true});"
            " return node.isConnected && document.activeElement===node; }"
        )
        if active is not True:
            raise WorkerBootstrapError(
                "focused selectbox failed-open control is unavailable"
            )
        page.keyboard.press("Escape")
    while True:
        closed = combobox_handle.evaluate(
            "node => node.isConnected &&"
            " node.getAttribute('aria-expanded')==='false' &&"
            " node.getAttribute('aria-controls')===null"
        )
        if (
            closed is True
            and page.locator(
                'ul[data-testid="stSelectboxVirtualDropdown"]'
            ).count()
            == 0
            and page.locator('[data-baseweb="popover"]').count() == 0
            and page.locator('[role="listbox"]:visible').count() == 0
        ):
            return
        page.wait_for_timeout(
            min(
                25,
                _focused_remaining_timeout_ms(
                    deadline,
                    label="focused selectbox failed-open cleanup",
                ),
            )
        )


def _open_focused_selectbox_popup(
    page: Any,
    capture_identity: Mapping[str, Any],
    contract: Mapping[str, Any],
    combobox: Any,
    *,
    opening_key: str,
    option_count: int,
    selected_index: int,
    timeout_ms: int,
    cleanup_deadline: float,
) -> tuple[int, Any, Any, Any]:
    """Open one exact portal popup from one retained closed combobox."""

    if opening_key not in {"ArrowDown", "ArrowUp"}:
        raise WorkerBootstrapError("focused selectbox opening key is invalid")
    deadline = time.monotonic() + timeout_ms / 1_000

    def remaining(label: str) -> int:
        return _focused_remaining_timeout_ms(deadline, label=label)

    _require_focused_selectbox_popup_absent(page)
    generation = _selection_render_generation(
        page,
        capture_identity,
        timeout_ms=remaining("focused selectbox opening generation"),
    )
    combobox_handle = None
    dropdown_handle = None
    opening_sent = False
    try:
        combobox_handle = combobox.element_handle(
            timeout=remaining("focused selectbox opening retention")
        )
        if combobox_handle is None:
            raise WorkerBootstrapError("focused combobox could not be retained")
        focused = combobox_handle.evaluate(
            "(node, rootSelector) => {"
            " node.focus({preventScroll:true});"
            " const root=node.closest(rootSelector);"
            " return !!root && root.contains(node) && node.isConnected &&"
            " document.activeElement === node;"
            "}",
            str(contract["rootSelector"]),
        )
        if focused is not True:
            raise WorkerBootstrapError("focused combobox is not keyboard reachable")
        page.keyboard.press(opening_key)
        opening_sent = True
        if (
            _selection_render_generation(
                page,
                capture_identity,
                timeout_ms=remaining("focused selectbox opened generation"),
            )
            != generation
        ):
            raise WorkerBootstrapError(
                "focused selectbox popup opening rerendered the app"
            )
        popup_state = combobox_handle.evaluate(
            "(node, rootSelector) => {"
            " const root=node.closest(rootSelector);"
            " return {connected:node.isConnected,contained:!!root && root.contains(node),"
            " focused:document.activeElement===node,"
            " expanded:node.getAttribute('aria-expanded'),"
            " haspopup:node.getAttribute('aria-haspopup'),"
            " controls:node.getAttribute('aria-controls'),"
            " activeDescendant:node.getAttribute('aria-activedescendant')};"
            "}",
            str(contract["rootSelector"]),
        )
        if (
            not isinstance(popup_state, dict)
            or set(popup_state)
            != {
                "connected",
                "contained",
                "focused",
                "expanded",
                "haspopup",
                "controls",
                "activeDescendant",
            }
            or popup_state["connected"] is not True
            or popup_state["contained"] is not True
            or popup_state["focused"] is not True
            or popup_state["expanded"] != "true"
            or popup_state["haspopup"] != "listbox"
            or (
                popup_state["activeDescendant"] is not None
                and (
                    not isinstance(popup_state["activeDescendant"], str)
                    or re.fullmatch(
                        r"[A-Za-z0-9._:-]{1,128}",
                        popup_state["activeDescendant"],
                    )
                    is None
                )
            )
            or not isinstance(popup_state["controls"], str)
            or re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", popup_state["controls"])
            is None
            or page.evaluate(
                "token => document.getElementById(token) === null",
                popup_state["controls"],
            )
            is not True
        ):
            raise WorkerBootstrapError("focused selectbox popup state differs")
        dropdown = _focused_selectbox_dropdown(
            page,
            combobox_handle,
            option_count=option_count,
            expected_labels=tuple(
                str(value) for value in contract["optionLabels"]
            ),
            selected_index=selected_index,
            timeout_ms=remaining("focused selectbox opened dropdown"),
        )
        if popup_state["activeDescendant"] is not None:
            current_option_ids = tuple(
                dropdown.get_by_role("option").evaluate_all(
                    "options => options.map(option => option.id)"
                )
            )
            if (
                popup_state["activeDescendant"] in current_option_ids
                or page.evaluate(
                    "token => document.getElementById(token) !== null",
                    popup_state["activeDescendant"],
                )
                is not False
            ):
                raise WorkerBootstrapError(
                    "focused selectbox opening active descendant differs"
                )
        dropdown_handle = dropdown.element_handle(
            timeout=remaining("focused selectbox dropdown retention")
        )
        if dropdown_handle is None:
            raise WorkerBootstrapError(
                "focused selectbox dropdown could not be retained"
            )
        if (
            _selection_render_generation(
                page,
                capture_identity,
                timeout_ms=remaining(
                    "focused selectbox completed opening generation"
                ),
            )
            != generation
            or combobox_handle.evaluate(
                "node => node.isConnected && document.activeElement===node &&"
                " node.getAttribute('aria-expanded')==='true'"
            )
            is not True
            or dropdown_handle.evaluate("node => node.isConnected") is not True
        ):
            raise WorkerBootstrapError(
                "focused selectbox completed opening state differs"
            )
        return generation, combobox_handle, dropdown, dropdown_handle
    except BaseException as primary_error:
        cleanup_error: BaseException | None = None
        if opening_sent and combobox_handle is not None:
            try:
                cleanup_timeout_ms = _focused_remaining_timeout_ms(
                    cleanup_deadline,
                    label="focused selectbox failed-open cleanup",
                )
                _restore_focused_selectbox_closed_state(
                    page,
                    combobox_handle,
                    timeout_ms=cleanup_timeout_ms,
                )
                if (
                    _selection_render_generation(
                        page,
                        capture_identity,
                        timeout_ms=_focused_remaining_timeout_ms(
                            cleanup_deadline,
                            label=(
                                "focused selectbox failed-open cleanup generation"
                            ),
                        ),
                    )
                    != generation
                ):
                    raise WorkerBootstrapError(
                        "focused selectbox failed-open cleanup rerendered the app"
                    )
            except BaseException as exc:
                wrapped = WorkerBootstrapError(
                    "focused selectbox failed-open popup could not be closed"
                )
                wrapped.__cause__ = exc
                cleanup_error = wrapped
        for handle in (dropdown_handle, combobox_handle):
            if handle is not None:
                try:
                    _dispose_focused_handle(
                        handle,
                        label="focused selectbox failed-open handle",
                    )
                except BaseException as exc:
                    if cleanup_error is None:
                        cleanup_error = exc
                    else:
                        cleanup_error.add_note(
                            "focused selectbox failed-open handle cleanup also failed: "
                            f"{type(exc).__name__}: {exc}"
                        )
        if cleanup_error is not None:
            primary_error.add_note(
                "focused selectbox failed-open cleanup also failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )
            raise primary_error from cleanup_error
        raise primary_error


def _close_focused_selectbox_popup(
    page: Any,
    combobox_handle: Any,
    dropdown_handle: Any,
    *,
    cleanup_deadline: float,
    primary_error: BaseException | None = None,
) -> None:
    """Require one retained portal popup to detach, then release its handles."""

    cleanup_error: BaseException | None = None
    if primary_error is None:
        try:
            if (
                dropdown_handle.evaluate("node => !node.isConnected") is not True
                or page.locator(
                    'ul[data-testid="stSelectboxVirtualDropdown"]'
                ).count()
                != 0
                or page.locator('[data-baseweb="popover"]').count() != 0
                or page.locator('[role="listbox"]:visible').count() != 0
            ):
                raise WorkerBootstrapError(
                    "focused selectbox popup did not close causally"
                )
        except BaseException as exc:
            primary_error = exc
    if primary_error is not None:
        try:
            _restore_focused_selectbox_closed_state(
                page,
                combobox_handle,
                timeout_ms=_focused_remaining_timeout_ms(
                    cleanup_deadline,
                    label="focused selectbox popup cleanup",
                ),
            )
        except BaseException as exc:
            cleanup_error = exc
    for handle in (dropdown_handle, combobox_handle):
        try:
            _dispose_focused_handle(
                handle,
                label="focused selectbox retained popup handle",
            )
        except BaseException as exc:
            if cleanup_error is None:
                cleanup_error = exc
            else:
                cleanup_error.add_note(
                    "focused selectbox popup handle cleanup also failed: "
                    f"{type(exc).__name__}: {exc}"
                )
    if primary_error is not None:
        if cleanup_error is not None:
            primary_error.add_note(
                "focused selectbox popup cleanup also failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )
            raise primary_error from cleanup_error
        raise primary_error
    if cleanup_error is not None:
        raise cleanup_error


def _navigate_focused_selectbox_popup(
    page: Any,
    capture_identity: Mapping[str, Any],
    combobox_handle: Any,
    dropdown_handle: Any,
    *,
    generation: int,
    navigation_key: str,
    expected_labels: Sequence[str],
    selected_index: int,
    timeout_ms: int,
) -> tuple[Any, Any]:
    """Navigate and reauthenticate the latest popup before committing."""

    if navigation_key not in {"ArrowDown", "ArrowUp"}:
        raise WorkerBootstrapError("focused selectbox navigation key is invalid")
    deadline = time.monotonic() + timeout_ms / 1_000

    def remaining(label: str) -> int:
        return _focused_remaining_timeout_ms(deadline, label=label)

    current_dropdown_handle = None
    try:
        if combobox_handle.evaluate(
            "node => node.isConnected && document.activeElement===node &&"
            " node.getAttribute('aria-expanded')==='true'"
        ) is not True:
            raise WorkerBootstrapError(
                "focused selectbox pre-navigation state differs"
            )
        page.keyboard.press(navigation_key)
        if (
            _selection_render_generation(
                page,
                capture_identity,
                timeout_ms=remaining("focused selectbox navigation generation"),
            )
            != generation
        ):
            raise WorkerBootstrapError(
                "focused selectbox navigation rerendered the app"
            )
        current_dropdown = _focused_selectbox_dropdown(
            page,
            combobox_handle,
            option_count=len(expected_labels),
            expected_labels=expected_labels,
            selected_index=selected_index,
            timeout_ms=remaining("focused selectbox navigated dropdown"),
        )
        labels = tuple(
            re.sub(r"\s+", " ", text).strip()
            for text in current_dropdown.get_by_role("option").all_inner_texts()
        )
        active_descendant = combobox_handle.get_attribute(
            "aria-activedescendant"
        )
        selected_option_id = current_dropdown.get_by_role("option").nth(
            selected_index
        ).get_attribute("id")
        if (
            labels != tuple(expected_labels)
            or not isinstance(active_descendant, str)
            or not active_descendant
            or active_descendant != selected_option_id
            or re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", active_descendant) is None
            or combobox_handle.evaluate(
                "node => node.isConnected && document.activeElement===node &&"
                " node.getAttribute('aria-expanded')==='true'"
            )
            is not True
            or _selection_render_generation(
                page,
                capture_identity,
                timeout_ms=remaining(
                    "focused selectbox completed navigation generation"
                ),
            )
            != generation
        ):
            raise WorkerBootstrapError(
                "focused selectbox navigated popup state differs"
            )
        current_dropdown_handle = current_dropdown.element_handle(
            timeout=remaining("focused selectbox navigated dropdown retention")
        )
        if current_dropdown_handle is None:
            raise WorkerBootstrapError(
                "focused selectbox navigated dropdown could not be retained"
            )
        _dispose_focused_handle(
            dropdown_handle,
            label="focused selectbox superseded dropdown handle",
        )
        return current_dropdown, current_dropdown_handle
    except BaseException as primary_error:
        if current_dropdown_handle is not None:
            try:
                _dispose_focused_handle(
                    current_dropdown_handle,
                    label="focused selectbox failed navigation handle",
                )
            except BaseException as cleanup_error:
                primary_error.add_note(
                    "focused selectbox failed navigation cleanup also failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
                raise primary_error from cleanup_error
        raise primary_error


def _commit_focused_selectbox_popup(
    page: Any,
    capture_identity: Mapping[str, Any],
    combobox_handle: Any,
    dropdown_handle: Any,
    *,
    root_selector: str,
    expected_accessible_name: str,
    generation: int,
    expected_labels: Sequence[str],
    selected_index: int,
    timeout_ms: int,
) -> int:
    """Require one quiet exact popup window, then commit exactly one rerender."""

    if (
        not isinstance(root_selector, str)
        or not root_selector
        or not isinstance(expected_accessible_name, str)
        or not expected_accessible_name
        or type(generation) is not int
        or generation < 1
        or generation >= 1_000_000
        or type(selected_index) is not int
        or selected_index < 0
        or selected_index >= len(expected_labels)
        or not isinstance(timeout_ms, int)
        or isinstance(timeout_ms, bool)
        or timeout_ms <= 0
    ):
        raise WorkerBootstrapError(
            "focused selectbox precommit contract is invalid"
        )
    controls = combobox_handle.get_attribute("aria-controls")
    if (
        not isinstance(controls, str)
        or re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", controls) is None
    ):
        raise WorkerBootstrapError(
            "focused selectbox precommit popup identity differs"
        )
    deadline = time.monotonic() + timeout_ms / 1_000
    quiet_started: float | None = None
    expected = {
        "accessibleName": expected_accessible_name,
        "captureId": _selection_capture_id(capture_identity),
        "controls": controls,
        "dropdown": dropdown_handle,
        "generation": generation,
        "labels": tuple(str(value) for value in expected_labels),
        "rootSelector": root_selector,
        "selectedIndex": selected_index,
    }
    while True:
        try:
            state = combobox_handle.evaluate(
                _STREAMLIT_SELECT_PRECOMMIT_STATE_SCRIPT,
                expected,
            )
        except Exception as exc:
            raise WorkerBootstrapError(
                "focused selectbox precommit state is unavailable"
            ) from exc
        if (
            not isinstance(state, dict)
            or set(state) != {"exact", "generationExact", "motionFree"}
            or any(type(state[key]) is not bool for key in state)
        ):
            raise WorkerBootstrapError(
                "focused selectbox precommit state is malformed"
            )
        if state["generationExact"] is not True:
            raise WorkerBootstrapError(
                "focused selectbox navigation rerendered before commit"
            )
        if state["exact"] is not True:
            raise WorkerBootstrapError(
                "focused selectbox precommit popup state differs"
            )
        try:
            current_dropdown = page.locator(
                'ul[data-testid="stSelectboxVirtualDropdown"]'
            )
            if current_dropdown.count() != 1:
                raise WorkerBootstrapError(
                    "focused selectbox precommit dropdown is not unique"
                )
            _require_focused_selectbox_option_accessible_names(
                current_dropdown,
                expected_labels,
            )
        except WorkerBootstrapError:
            raise
        except Exception as exc:
            raise WorkerBootstrapError(
                "focused selectbox precommit option names are unavailable"
            ) from exc
        now = time.monotonic()
        if state["motionFree"] is True:
            if quiet_started is None:
                quiet_started = now
            elif (
                now - quiet_started
                >= _FOCUSED_SELECTBOX_PRECOMMIT_QUIET_MS / 1_000
            ):
                break
        else:
            quiet_started = None
        page.wait_for_timeout(
            min(
                _FOCUSED_SELECTBOX_PRECOMMIT_POLL_MS,
                _focused_remaining_timeout_ms(
                    deadline,
                    label="focused selectbox precommit quiet window",
                ),
            )
        )

    page.keyboard.press("Enter")
    committed_generation = _wait_for_selection_render_after(
        page,
        capture_identity,
        generation,
        timeout_ms=_focused_remaining_timeout_ms(
            deadline,
            label="focused selectbox commit generation",
        ),
    )
    if committed_generation != generation + 1:
        raise WorkerBootstrapError(
            "focused selectbox commit generation is not exact"
        )
    return committed_generation


def _selectbox_control_evidence(
    page: Any,
    capture_identity: Mapping[str, Any],
    contract: Mapping[str, Any],
    *,
    timeout_ms: int,
) -> dict[str, Any]:
    selector = str(contract["rootSelector"])
    options = tuple(str(value) for value in contract["optionLabels"])
    selected = str(contract["selectedLabel"])
    selected_index = options.index(selected)
    next_index = (selected_index + 1) % len(options)
    initial_root = _wait_for_unique_visible(
        page.locator(selector), label="focused selectbox root", timeout_ms=timeout_ms
    )

    def audit_selectbox(
        audit_deadline: float,
        cleanup_deadline: float,
    ) -> dict[str, Any]:
        def remaining(label: str) -> int:
            return _focused_remaining_timeout_ms(audit_deadline, label=label)

        root = _wait_for_unique_visible(
            page.locator(selector),
            label="focused selectbox root",
            timeout_ms=remaining("focused selectbox initial root"),
        )
        if (
            root.get_by_role("combobox").count() != 1
            or root.get_by_role("radiogroup").count() != 0
            or root.get_by_role("radio").count() != 0
            or root.locator(
                '[data-baseweb="button-group"], input[type="radio"],'
                ' [role="radio"]'
            ).count()
            != 0
        ):
            raise WorkerBootstrapError("focused selectbox primary projection differs")
        combobox = _focused_selectbox_combobox(
            root,
            contract,
            selected,
            timeout_ms=remaining("focused selectbox initial combobox"),
            label="focused combobox",
        )
        auxiliary_buttons = _validate_focused_button_projection(
            root,
            contract,
            legacy_options=False,
            primary_selector='[role="combobox"]',
            timeout_ms=remaining("focused selectbox initial buttons"),
        )
        if _selectbox_text(root) != selected:
            raise WorkerBootstrapError("focused selectbox initial state differs")

        generation, combobox_handle, dropdown, dropdown_handle = (
            _open_focused_selectbox_popup(
                page,
                capture_identity,
                contract,
                combobox,
                opening_key="ArrowDown",
                option_count=len(options),
                selected_index=selected_index,
                timeout_ms=remaining("focused selectbox initial popup"),
                cleanup_deadline=cleanup_deadline,
            )
        )
        popup_error: BaseException | None = None
        try:
            option_labels = tuple(
                re.sub(r"\s+", " ", text).strip()
                for text in dropdown.get_by_role("option").all_inner_texts()
            )
            if option_labels != options:
                raise WorkerBootstrapError("focused selectbox option labels differ")
            dropdown, dropdown_handle = _navigate_focused_selectbox_popup(
                page,
                capture_identity,
                combobox_handle,
                dropdown_handle,
                generation=generation,
                navigation_key="ArrowDown",
                expected_labels=options,
                selected_index=next_index,
                timeout_ms=remaining("focused selectbox alternate navigation"),
            )
            generation = _commit_focused_selectbox_popup(
                page,
                capture_identity,
                combobox_handle,
                dropdown_handle,
                root_selector=selector,
                expected_accessible_name=_selectbox_accessible_name(
                    contract,
                    selected,
                ),
                generation=generation,
                expected_labels=options,
                selected_index=next_index,
                timeout_ms=remaining("focused selectbox alternate commit"),
            )
        except BaseException as exc:
            popup_error = exc
        _close_focused_selectbox_popup(
            page,
            combobox_handle,
            dropdown_handle,
            cleanup_deadline=cleanup_deadline,
            primary_error=popup_error,
        )

        root = _wait_for_unique_visible(
            page.locator(selector),
            label="focused selectbox root after alternate",
            timeout_ms=remaining("focused selectbox alternate root"),
        )
        _wait_for_focused_projection(
            page,
            root,
            contract,
            timeout_ms=remaining("focused selectbox alternate projection"),
            expected_projection="accessible-required",
            expected_selected=options[1],
        )
        if (
            root.get_by_role("combobox").count() != 1
            or root.get_by_role("radiogroup").count() != 0
            or root.get_by_role("radio").count() != 0
            or root.locator(
                '[data-baseweb="button-group"], input[type="radio"],'
                ' [role="radio"]'
            ).count()
            != 0
        ):
            raise WorkerBootstrapError("focused selectbox alternate projection differs")
        if _validate_focused_button_projection(
            root,
            contract,
            legacy_options=False,
            primary_selector='[role="combobox"]',
            timeout_ms=remaining("focused selectbox alternate buttons"),
        ) != auxiliary_buttons:
            raise WorkerBootstrapError("focused selectbox auxiliary projection differs")
        if _selectbox_text(root) != options[1]:
            raise WorkerBootstrapError("focused selectbox ArrowDown behavior differs")
        combobox = _focused_selectbox_combobox(
            root,
            contract,
            options[1],
            timeout_ms=remaining("focused selectbox alternate combobox"),
            label="focused combobox after alternate",
        )

        restore_generation, combobox_handle, dropdown, dropdown_handle = (
            _open_focused_selectbox_popup(
                page,
                capture_identity,
                contract,
                combobox,
                opening_key="ArrowUp",
                option_count=len(options),
                selected_index=next_index,
                timeout_ms=remaining("focused selectbox restore popup"),
                cleanup_deadline=cleanup_deadline,
            )
        )
        if restore_generation != generation:
            _close_focused_selectbox_popup(
                page,
                combobox_handle,
                dropdown_handle,
                cleanup_deadline=cleanup_deadline,
                primary_error=WorkerBootstrapError(
                    "focused selectbox restore generation differs"
                ),
            )
        popup_error = None
        try:
            restore_option_labels = tuple(
                re.sub(r"\s+", " ", text).strip()
                for text in dropdown.get_by_role("option").all_inner_texts()
            )
            if restore_option_labels != options:
                raise WorkerBootstrapError(
                    "focused selectbox restore option labels differ"
                )
            dropdown, dropdown_handle = _navigate_focused_selectbox_popup(
                page,
                capture_identity,
                combobox_handle,
                dropdown_handle,
                generation=restore_generation,
                navigation_key="ArrowUp",
                expected_labels=options,
                selected_index=selected_index,
                timeout_ms=remaining("focused selectbox restore navigation"),
            )
            restored_generation = _commit_focused_selectbox_popup(
                page,
                capture_identity,
                combobox_handle,
                dropdown_handle,
                root_selector=selector,
                expected_accessible_name=_selectbox_accessible_name(
                    contract,
                    options[next_index],
                ),
                generation=restore_generation,
                expected_labels=options,
                selected_index=selected_index,
                timeout_ms=remaining("focused selectbox restore commit"),
            )
        except BaseException as exc:
            popup_error = exc
        _close_focused_selectbox_popup(
            page,
            combobox_handle,
            dropdown_handle,
            cleanup_deadline=cleanup_deadline,
            primary_error=popup_error,
        )

        root = _wait_for_unique_visible(
            page.locator(selector),
            label="focused selectbox root after restore",
            timeout_ms=remaining("focused selectbox restored root"),
        )
        _wait_for_focused_projection(
            page,
            root,
            contract,
            timeout_ms=remaining("focused selectbox restored projection"),
            expected_projection="accessible-required",
            expected_selected=selected,
        )
        if (
            root.get_by_role("combobox").count() != 1
            or root.get_by_role("radiogroup").count() != 0
            or root.get_by_role("radio").count() != 0
            or root.locator(
                '[data-baseweb="button-group"], input[type="radio"],'
                ' [role="radio"]'
            ).count()
            != 0
        ):
            raise WorkerBootstrapError("focused selectbox restore projection differs")
        if _selectbox_text(root) != selected:
            raise WorkerBootstrapError("focused selectbox ArrowUp did not restore state")
        if (
            _selection_render_generation(
                page,
                capture_identity,
                timeout_ms=remaining(
                    "focused selectbox restored generation"
                ),
            )
            != restored_generation
        ):
            raise WorkerBootstrapError(
                "focused selectbox restored generation differs"
            )
        combobox = _focused_selectbox_combobox(
            root,
            contract,
            selected,
            timeout_ms=remaining("focused selectbox restored combobox"),
            label="focused combobox after restore",
        )
        auxiliary_buttons = _validate_focused_button_projection(
            root,
            contract,
            legacy_options=False,
            primary_selector='[role="combobox"]',
            timeout_ms=remaining("focused selectbox restored buttons"),
        )
        select_target = _wait_for_unique_visible(
            root.locator('[data-baseweb="select"]'),
            label="focused selectbox trigger",
            timeout_ms=remaining("focused selectbox restored trigger"),
        )
        if (
            select_target.get_by_role("combobox").count() != 1
            or combobox.evaluate(
                "(node, rootSelector) => {"
                " const root = node.closest(rootSelector);"
                " const select = node.closest('[data-baseweb=\"select\"]');"
                " return !!root && !!select &&"
                " document.querySelectorAll(rootSelector).length === 1 &&"
                " root.querySelectorAll('[data-baseweb=\"select\"]').length === 1 &&"
                " root.querySelector('[data-baseweb=\"select\"]') === select &&"
                " select.querySelectorAll('[role=\"combobox\"]').length === 1 &&"
                " select.querySelector('[role=\"combobox\"]') === node;"
                "}",
                selector,
            )
            is not True
        ):
            raise WorkerBootstrapError("focused selectbox trigger association differs")

        def audit_internal_button(layout_deadline: float) -> None:
            if _validate_focused_button_projection(
                root,
                contract,
                legacy_options=False,
                primary_selector='[role="combobox"]',
                trial_click_internal=True,
                timeout_ms=_focused_remaining_timeout_ms(
                    layout_deadline,
                    label="focused selectbox internal actionability",
                ),
            ) != auxiliary_buttons:
                raise WorkerBootstrapError(
                    "focused selectbox internal projection differs"
                )

        targets, layout = _focused_control_layout(
            page,
            root,
            ((selected, select_target),),
            viewport_width=int(capture_identity["viewport"]["width"]),
            viewport_height=int(capture_identity["viewport"]["height"]),
            target_overlap_tolerance=0.5,
            closest_label=False,
            before_layout_audit=audit_internal_button,
            timeout_ms=remaining("focused selectbox layout"),
        )
        return {
            "sessionKey": contract["sessionKey"],
            "rootSelector": selector,
            "widget": "selectbox",
            "role": combobox.get_attribute("role"),
            "accessibleName": contract["accessibleName"],
            "optionRole": "option",
            "optionLabels": list(options),
            "auxiliaryButtons": auxiliary_buttons,
            "selectedLabel": selected,
            "checkedLabels": [],
            "tabSequenceLabels": [],
            "afterArrowRight": None,
            "afterArrowLeft": None,
            "afterSpace": None,
            "afterArrowDown": options[1],
            "afterArrowUp": selected,
            "targets": targets,
            "layout": layout,
            "selectionBasis": "combobox/exact-option-order/keyboard/restore",
        }

    return _focused_rerendering_scroll_audit(
        page,
        initial_root,
        audit_selectbox,
        timeout_ms=timeout_ms,
    )


_FOCUSED_SEMANTIC_SNAPSHOT_SCRIPT = """
element => {
  const normalize = value => String(value ?? '').replace(/\s+/g, ' ').trim();
  const visible = node => {
    if (!(node instanceof Element)) return false;
    for (let current = node; current; current = current.parentElement) {
      const style = getComputedStyle(current);
      if (
        current.getAttribute('aria-hidden') === 'true' ||
        style.display === 'none' ||
        style.visibility === 'hidden' ||
        style.visibility === 'collapse'
      ) return false;
    }
    return node.getClientRects().length > 0;
  };
  const nodes = selector =>
    Array.from(element.querySelectorAll(selector)).filter(visible);
  const accessibleName = node => {
    const ariaLabel = normalize(node.getAttribute('aria-label'));
    if (ariaLabel) return ariaLabel;
    const labelledBy = normalize(node.getAttribute('aria-labelledby'));
    if (labelledBy) {
      const text = labelledBy.split(' ').map(id => {
        const label = document.getElementById(id);
        return label ? normalize(label.innerText || label.textContent) : '';
      }).filter(Boolean).join(' ');
      if (text) return normalize(text);
    }
    if (node.labels && node.labels.length) {
      return normalize(node.labels[0].innerText || node.labels[0].textContent);
    }
    return normalize(node.innerText || node.textContent);
  };
  const buttons = nodes('button, [role="button"]');
  const radiogroups = nodes('[role="radiogroup"]');
  const primaryGroups = nodes(
    '[data-baseweb="button-group"][role="radiogroup"]'
  );
  const primaryButtons = primaryGroups.length === 1
    ? Array.from(
        primaryGroups[0].querySelectorAll('button, [role="button"]')
      ).filter(visible)
    : [];
  const radios = nodes('input[type="radio"], [role="radio"]');
  const comboboxes = nodes('[role="combobox"]');
  const selectRoots = nodes('[data-baseweb="select"]');
  return {
    buttonNames: buttons.map(accessibleName),
    radiogroupCount: radiogroups.length,
    radiogroupNames: radiogroups.map(accessibleName),
    primaryGroupCount: primaryGroups.length,
    primaryOptionLabels: primaryButtons.map(accessibleName),
    primaryKinds: primaryButtons.map(node => normalize(node.getAttribute('kind'))),
    radioCount: radios.length,
    radioLabels: radios.map(accessibleName),
    checkedRadioLabels: radios.filter(
      node => node.checked === true || node.getAttribute('aria-checked') === 'true'
    ).map(accessibleName),
    comboboxCount: comboboxes.length,
    comboboxNames: comboboxes.map(accessibleName),
    selectRootCount: selectRoots.length,
    selectText: selectRoots.length === 1
      ? normalize(selectRoots[0].innerText || selectRoots[0].textContent)
      : ''
  };
}
"""

_FOCUSED_SEMANTIC_LIST_FIELDS = frozenset(
    {
        "buttonNames",
        "radiogroupNames",
        "primaryOptionLabels",
        "primaryKinds",
        "radioLabels",
        "checkedRadioLabels",
        "comboboxNames",
    }
)
_FOCUSED_SEMANTIC_COUNT_FIELDS = frozenset(
    {
        "radiogroupCount",
        "primaryGroupCount",
        "radioCount",
        "comboboxCount",
        "selectRootCount",
    }
)
_FOCUSED_SEMANTIC_FIELDS = (
    _FOCUSED_SEMANTIC_LIST_FIELDS
    | _FOCUSED_SEMANTIC_COUNT_FIELDS
    | {"selectText"}
)


def _focused_projection_snapshot(
    root: Any,
    contract: Mapping[str, Any],
    *,
    expected_selected: str | None = None,
    observation_timeout_ms: int | None = None,
) -> tuple[str | None, str]:
    """Atomically observe and exactly classify one focused-control projection."""

    option_labels = tuple(str(value) for value in contract["optionLabels"])
    auxiliary_labels = tuple(str(value) for value in contract["auxiliaryButtons"])
    accessible_name = str(contract["accessibleName"])
    selected = (
        str(contract["selectedLabel"])
        if expected_selected is None
        else expected_selected
    )
    if selected not in option_labels:
        raise WorkerBootstrapError("focused semantic selection is not contracted")
    snapshot = root.evaluate(
        _FOCUSED_SEMANTIC_SNAPSHOT_SCRIPT,
        timeout=observation_timeout_ms,
    )
    if not isinstance(snapshot, dict) or set(snapshot) != _FOCUSED_SEMANTIC_FIELDS:
        raise WorkerBootstrapError("focused semantic snapshot is malformed")
    if any(
        not isinstance(snapshot[field], list)
        or any(not isinstance(value, str) for value in snapshot[field])
        for field in _FOCUSED_SEMANTIC_LIST_FIELDS
    ) or any(
        type(snapshot[field]) is not int or snapshot[field] < 0
        for field in _FOCUSED_SEMANTIC_COUNT_FIELDS
    ) or not isinstance(snapshot["selectText"], str):
        raise WorkerBootstrapError("focused semantic snapshot is malformed")

    fingerprint = json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    button_names = tuple(str(value) for value in snapshot["buttonNames"])
    legacy_buttons = tuple(sorted(option_labels + auxiliary_labels))
    accessible_buttons = tuple(sorted(auxiliary_labels))
    selectbox_buttons = tuple(
        sorted(auxiliary_labels + (_SELECTBOX_CLEAR_ACCESSIBLE_NAME,))
    )
    selected_kinds = tuple(
        "segmented_controlActive" if label == selected else "segmented_control"
        for label in option_labels
    )
    no_radios = (
        snapshot["radioCount"] == 0
        and snapshot["radioLabels"] == []
        and snapshot["checkedRadioLabels"] == []
    )
    legacy_exact = all(
        (
            tuple(sorted(button_names)) == legacy_buttons,
            snapshot["radiogroupCount"] == 1,
            snapshot["primaryGroupCount"] == 1,
            tuple(snapshot["primaryOptionLabels"]) == option_labels,
            tuple(snapshot["primaryKinds"]) == selected_kinds,
            no_radios,
            snapshot["comboboxCount"] == 0,
            snapshot["comboboxNames"] == [],
            snapshot["selectRootCount"] == 0,
            snapshot["selectText"] == "",
        )
    )
    if legacy_exact:
        return "legacy-segmented", fingerprint

    radio_exact = all(
        (
            contract["replacementWidget"] == "radio_horizontal",
            tuple(sorted(button_names)) == accessible_buttons,
            snapshot["radiogroupCount"] == 1,
            snapshot["radiogroupNames"] == [accessible_name],
            snapshot["primaryGroupCount"] == 0,
            snapshot["primaryOptionLabels"] == [],
            snapshot["primaryKinds"] == [],
            snapshot["radioCount"] == len(option_labels),
            tuple(snapshot["radioLabels"]) == option_labels,
            snapshot["checkedRadioLabels"] == [selected],
            snapshot["comboboxCount"] == 0,
            snapshot["comboboxNames"] == [],
            snapshot["selectRootCount"] == 0,
            snapshot["selectText"] == "",
        )
    )
    if radio_exact:
        return "accessible-required", fingerprint

    selectbox_exact = all(
        (
            contract["replacementWidget"] == "selectbox",
            tuple(sorted(button_names)) == selectbox_buttons,
            snapshot["radiogroupCount"] == 0,
            snapshot["radiogroupNames"] == [],
            snapshot["primaryGroupCount"] == 0,
            snapshot["primaryOptionLabels"] == [],
            snapshot["primaryKinds"] == [],
            no_radios,
            snapshot["comboboxCount"] == 1,
            snapshot["comboboxNames"]
            == [_selectbox_accessible_name(contract, selected)],
            snapshot["selectRootCount"] == 1,
            snapshot["selectText"] == selected,
        )
    )
    if selectbox_exact:
        return "accessible-required", fingerprint
    return None, fingerprint


def _wait_for_focused_projection(
    page: Any,
    root: Any,
    contract: Mapping[str, Any],
    *,
    timeout_ms: int,
    expected_projection: str | None = None,
    expected_selected: str | None = None,
) -> str:
    if expected_projection not in {None, "legacy-segmented", "accessible-required"}:
        raise WorkerBootstrapError("focused semantic projection is not contracted")
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    except ImportError as exc:
        raise WorkerDependencyUnavailable("Playwright is unavailable") from exc
    deadline = time.monotonic() + (timeout_ms / 1000)
    previous_exact: tuple[str, str] | None = None
    while True:
        remaining_ms = int((deadline - time.monotonic()) * 1000)
        if remaining_ms <= 0:
            raise WorkerBootstrapError(
                "focused control widget projection did not become ready"
            )
        try:
            projection, fingerprint = _focused_projection_snapshot(
                root,
                contract,
                expected_selected=expected_selected,
                observation_timeout_ms=max(1, remaining_ms),
            )
        except PlaywrightTimeoutError:
            raise WorkerBootstrapError(
                "focused control widget projection did not become ready"
            ) from None
        current_exact = (
            (projection, fingerprint)
            if projection is not None
            and (expected_projection is None or projection == expected_projection)
            else None
        )
        if current_exact is not None and current_exact == previous_exact:
            return current_exact[0]
        previous_exact = current_exact
        remaining_ms = int((deadline - time.monotonic()) * 1000)
        if remaining_ms <= 0:
            raise WorkerBootstrapError("focused control widget projection did not become ready")
        page.wait_for_timeout(min(50, remaining_ms))


def _collect_focused_control_evidence(
    page: Any,
    capture_identity: Mapping[str, Any],
    *,
    timeout_ms: int,
) -> dict[str, Any] | None:
    if (
        capture_identity.get("fixtureEntrypoint")
        != "scripts/ui_ux_selection_fixture_app.py"
    ):
        return None
    case = capture_identity.get("case")
    contracts = _FOCUSED_CONTROL_CONTRACTS.get(str(case))
    if contracts is None:
        raise WorkerBootstrapError("focused control case is not contracted")
    observations: list[dict[str, Any]] = []
    projections: set[str] = set()
    for contract in contracts:
        root = _wait_for_unique_visible(
            page.locator(str(contract["rootSelector"])),
            label="focused control root",
            timeout_ms=timeout_ms,
        )
        projection = _wait_for_focused_projection(
            page, root, contract, timeout_ms=timeout_ms
        )
        if projection == "legacy-segmented":
            projections.add("legacy-segmented")
            observations.append(
                _legacy_control_evidence(
                    page, capture_identity, contract, timeout_ms=timeout_ms
                )
            )
        elif contract["replacementWidget"] == "radio_horizontal":
            projections.add("accessible-required")
            observations.append(
                _radio_control_evidence(
                    page, capture_identity, contract, timeout_ms=timeout_ms
                )
            )
        elif contract["replacementWidget"] == "selectbox":
            projections.add("accessible-required")
            observations.append(
                _selectbox_control_evidence(
                    page, capture_identity, contract, timeout_ms=timeout_ms
                )
            )
        else:
            raise WorkerBootstrapError("focused control widget projection is unsupported")
    if len(projections) != 1:
        raise WorkerBootstrapError("focused control capture mixes migration phases")
    return {
        "schemaVersion": FOCUSED_CONTROL_EVIDENCE_SCHEMA,
        "case": case,
        "projection": next(iter(projections)),
        "controls": observations,
    }


_FOCUSED_SCREENSHOT_POSITION_SCRIPT = r"""
specs => {
  if (!Array.isArray(specs) || specs.length === 0) {
    throw new Error('focused screenshot specs are missing');
  }
  const visible = node => {
    if (!(node instanceof Element) || !node.isConnected) return false;
    const style = getComputedStyle(node);
    const rect = node.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' &&
      Number(style.opacity || 1) !== 0 && rect.width > 0 && rect.height > 0;
  };
  const radioTargets = (root, spec) => {
    const normalize = value => String(value == null ? '' : value)
      .replace(/\s+/g, ' ').trim();
    const radios = Array.from(
      root.querySelectorAll('input[type="radio"], [role="radio"]')
    );
    const labels = spec.targetLabels.map(expected => {
      const matches = radios.map(node =>
        node.labels && node.labels.length === 1
          ? node.labels[0]
          : node.closest('label')
      ).filter((label, index, rows) =>
        label && rows.indexOf(label) === index && visible(label) &&
        normalize(label.innerText || label.textContent) === expected
      );
      if (matches.length !== 1) {
        throw new Error('focused screenshot radio label differs');
      }
      return matches[0];
    });
    if (new Set(labels).size !== spec.targetLabels.length) {
      throw new Error('focused screenshot radio labels are not unique');
    }
    return labels;
  };
  const targets = (root, spec) => {
    let nodes;
    if (spec.widget === 'selectbox') {
      nodes = Array.from(root.querySelectorAll('[data-baseweb="select"]'));
    } else if (spec.widget === 'radio_horizontal') {
      nodes = radioTargets(root, spec);
    } else if (spec.widget === 'segmented_control') {
      const group = root.querySelector(
        '[data-baseweb="button-group"][role="radiogroup"]'
      );
      nodes = group ? Array.from(group.querySelectorAll('button,[role="button"]')) : [];
    } else {
      throw new Error('focused screenshot widget is unsupported');
    }
    nodes = nodes.filter(visible);
    if (nodes.length !== spec.targetLabels.length) {
      throw new Error('focused screenshot target count differs');
    }
    return nodes;
  };
  const roots = specs.map(spec => {
    const matches = Array.from(document.querySelectorAll(spec.rootSelector))
      .filter(visible);
    if (matches.length !== 1) {
      throw new Error('focused screenshot root is not unique and visible');
    }
    return matches[0];
  });
  const targetRows = roots.map((root, index) => targets(root, specs[index]));
  const documentScroller = document.scrollingElement || document.documentElement;
  const scrollable = node => {
    if (node === documentScroller) return true;
    const style = getComputedStyle(node);
    const overflowX = String(style.overflowX || '');
    const overflowY = String(style.overflowY || '');
    return (
      ((overflowX === 'auto' || overflowX === 'scroll') &&
       node.scrollWidth > node.clientWidth + 1) ||
      ((overflowY === 'auto' || overflowY === 'scroll') &&
       node.scrollHeight > node.clientHeight + 1)
    );
  };
  const chain = root => {
    const result = [];
    for (let node = root.parentElement; node; node = node.parentElement) {
      if (scrollable(node)) result.push(node);
    }
    if (!result.includes(documentScroller)) result.push(documentScroller);
    return result;
  };
  const chains = roots.map(chain);
  const common = chains[0].find(
    node => chains.every(candidate => candidate.includes(node))
  );
  if (!common) throw new Error('focused roots have no common scroll ancestor');
  const visibleRect = (() => {
    const viewport = {left: 0, top: 0, right: innerWidth, bottom: innerHeight};
    if (common === documentScroller) return viewport;
    const rect = common.getBoundingClientRect();
    return {
      left: Math.max(viewport.left, rect.left),
      top: Math.max(viewport.top, rect.top),
      right: Math.min(viewport.right, rect.right),
      bottom: Math.min(viewport.bottom, rect.bottom)
    };
  })();
  if (
    visibleRect.right <= visibleRect.left ||
    visibleRect.bottom <= visibleRect.top
  ) throw new Error('focused common scroll ancestor is outside the viewport');
  const rects = [
    ...roots.map(node => node.getBoundingClientRect()),
    ...targetRows.flat().map(node => node.getBoundingClientRect())
  ];
  const union = {
    left: Math.min(...rects.map(rect => rect.left)),
    top: Math.min(...rects.map(rect => rect.top)),
    right: Math.max(...rects.map(rect => rect.right)),
    bottom: Math.max(...rects.map(rect => rect.bottom))
  };
  const visibleWidth = visibleRect.right - visibleRect.left;
  const visibleHeight = visibleRect.bottom - visibleRect.top;
  if (
    union.right - union.left > visibleWidth + 1 ||
    union.bottom - union.top > visibleHeight + 1
  ) throw new Error('focused root group does not fit the viewport');
  const deltaX = (union.left + union.right - visibleRect.left - visibleRect.right) / 2;
  const deltaY = (union.top + union.bottom - visibleRect.top - visibleRect.bottom) / 2;
  if (common === documentScroller) {
    const maxLeft = Math.max(0, documentScroller.scrollWidth - innerWidth);
    const maxTop = Math.max(0, documentScroller.scrollHeight - innerHeight);
    window.scrollTo(
      Math.min(maxLeft, Math.max(0, window.scrollX + deltaX)),
      Math.min(maxTop, Math.max(0, window.scrollY + deltaY))
    );
  } else {
    const maxLeft = Math.max(0, common.scrollWidth - common.clientWidth);
    const maxTop = Math.max(0, common.scrollHeight - common.clientHeight);
    common.scrollLeft = Math.min(maxLeft, Math.max(0, common.scrollLeft + deltaX));
    common.scrollTop = Math.min(maxTop, Math.max(0, common.scrollTop + deltaY));
  }
  return true;
}
"""


_FOCUSED_SCREENSHOT_SNAPSHOT_SCRIPT = r"""
specs => {
  if (!Array.isArray(specs) || specs.length === 0) {
    throw new Error('focused screenshot specs are missing');
  }
  const round3 = value => Math.round(Number(value) * 1000) / 1000;
  const rect = (node, integer = false) => {
    const value = node.getBoundingClientRect();
    const convert = integer ? Math.round : round3;
    return {
      x: convert(value.x),
      y: convert(value.y),
      width: convert(value.width),
      height: convert(value.height)
    };
  };
  const inside = (inner, outer) =>
    inner.x >= outer.x - 1 && inner.y >= outer.y - 1 &&
    inner.x + inner.width <= outer.x + outer.width + 1 &&
    inner.y + inner.height <= outer.y + outer.height + 1;
  const visible = node => {
    if (!(node instanceof Element) || !node.isConnected) return false;
    const style = getComputedStyle(node);
    const value = node.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' &&
      Number(style.opacity || 1) !== 0 && value.width > 0 && value.height > 0;
  };
  const radioTargets = (root, spec) => {
    const normalize = value => String(value == null ? '' : value)
      .replace(/\s+/g, ' ').trim();
    const radios = Array.from(
      root.querySelectorAll('input[type="radio"], [role="radio"]')
    );
    const labels = spec.targetLabels.map(expected => {
      const matches = radios.map(node =>
        node.labels && node.labels.length === 1
          ? node.labels[0]
          : node.closest('label')
      ).filter((label, index, rows) =>
        label && rows.indexOf(label) === index && visible(label) &&
        normalize(label.innerText || label.textContent) === expected
      );
      if (matches.length !== 1) {
        throw new Error('focused screenshot radio label differs');
      }
      return matches[0];
    });
    if (new Set(labels).size !== spec.targetLabels.length) {
      throw new Error('focused screenshot radio labels are not unique');
    }
    return labels;
  };
  const targetNodes = (root, spec) => {
    let nodes;
    if (spec.widget === 'selectbox') {
      nodes = Array.from(root.querySelectorAll('[data-baseweb="select"]'));
    } else if (spec.widget === 'radio_horizontal') {
      nodes = radioTargets(root, spec);
    } else {
      const group = root.querySelector(
        '[data-baseweb="button-group"][role="radiogroup"]'
      );
      nodes = group ? Array.from(group.querySelectorAll('button,[role="button"]')) : [];
    }
    nodes = nodes.filter(visible);
    if (nodes.length !== spec.targetLabels.length) {
      throw new Error('focused screenshot target count differs');
    }
    return nodes;
  };
  const documentScroller = document.scrollingElement || document.documentElement;
  const scrollable = node => {
    if (node === documentScroller) return true;
    const style = getComputedStyle(node);
    return (
      ((style.overflowX === 'auto' || style.overflowX === 'scroll') &&
       node.scrollWidth > node.clientWidth + 1) ||
      ((style.overflowY === 'auto' || style.overflowY === 'scroll') &&
       node.scrollHeight > node.clientHeight + 1)
    );
  };
  const roots = [];
  const controls = [];
  const scrollEntries = [];
  for (const spec of specs) {
    const matches = Array.from(document.querySelectorAll(spec.rootSelector))
      .filter(visible);
    if (matches.length !== 1) {
      throw new Error('focused screenshot root is not unique and visible');
    }
    const root = matches[0];
    const rootRect = rect(root);
    const projectedRootRect = rect(root, true);
    const nodes = targetNodes(root, spec);
    const targets = nodes.map((node, index) => ({
      label: spec.targetLabels[index],
      ...rect(node)
    }));
    const viewportRect = {x: 0, y: 0, width: innerWidth, height: innerHeight};
    if (!inside(rootRect, viewportRect) ||
        targets.some(target => !inside(target, viewportRect) ||
          !inside(target, rootRect))) {
      throw new Error('focused screenshot geometry is outside the viewport');
    }
    const rootDimensions = {
      clientWidth: root.clientWidth,
      scrollWidth: root.scrollWidth,
      clientHeight: root.clientHeight,
      scrollHeight: root.scrollHeight
    };
    const documentDimensions = {
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: Math.max(
        document.documentElement.scrollWidth,
        document.body ? document.body.scrollWidth : 0
      ),
      clientHeight: document.documentElement.clientHeight,
      scrollHeight: Math.max(
        document.documentElement.scrollHeight,
        document.body ? document.body.scrollHeight : 0
      )
    };
    roots.push({rootSelector: spec.rootSelector, rect: projectedRootRect});
    controls.push({
      rootSelector: spec.rootSelector,
      targets,
      layout: {
        rootRect: projectedRootRect,
        viewportWidth: innerWidth,
        viewportHeight: innerHeight,
        targetOverlapTolerance: spec.targetOverlapTolerance,
        documentClientWidth: documentDimensions.clientWidth,
        documentScrollWidth: documentDimensions.scrollWidth,
        rootClientWidth: rootDimensions.clientWidth,
        rootScrollWidth: rootDimensions.scrollWidth,
        rootClipping: false,
        targetClipping: false,
        targetOverlap: false,
        documentHorizontalOverflow:
          documentDimensions.scrollWidth > documentDimensions.clientWidth + 1,
        rootHorizontalOverflow:
          rootDimensions.scrollWidth > rootDimensions.clientWidth + 1
      }
    });
    let chainIndex = 0;
    for (let node = root.parentElement; node; node = node.parentElement) {
      if (!scrollable(node)) continue;
      scrollEntries.push({
        rootSelector: spec.rootSelector,
        chainIndex,
        left: round3(node === documentScroller ? window.scrollX : node.scrollLeft),
        top: round3(node === documentScroller ? window.scrollY : node.scrollTop),
        clientWidth: node === documentScroller ? innerWidth : node.clientWidth,
        clientHeight: node === documentScroller ? innerHeight : node.clientHeight,
        scrollWidth: node.scrollWidth,
        scrollHeight: node.scrollHeight
      });
      chainIndex += 1;
    }
    if (!scrollEntries.some(
      row => row.rootSelector === spec.rootSelector &&
        row.chainIndex === chainIndex - 1 &&
        chainIndex > 0 &&
        (documentScroller === document.documentElement ||
         documentScroller === document.body)
    )) {
      scrollEntries.push({
        rootSelector: spec.rootSelector,
        chainIndex,
        left: round3(window.scrollX),
        top: round3(window.scrollY),
        clientWidth: innerWidth,
        clientHeight: innerHeight,
        scrollWidth: documentScroller.scrollWidth,
        scrollHeight: documentScroller.scrollHeight
      });
    }
  }
  return {
    binding: {
      schemaVersion: 'quant-radar-ui-ux-focused-screenshot-binding/v1',
      mode: 'viewport',
      viewport: {width: innerWidth, height: innerHeight},
      roots,
      scrollEntries,
      prePostExact: true
    },
    controls
  };
}
"""


def _focused_screenshot_specs(
    control_evidence: Mapping[str, Any],
) -> list[dict[str, Any]]:
    controls = control_evidence.get("controls")
    if (
        control_evidence.get("schemaVersion") != FOCUSED_CONTROL_EVIDENCE_SCHEMA
        or not isinstance(controls, list)
        or not controls
    ):
        raise WorkerBootstrapError("focused screenshot evidence input is malformed")
    specs: list[dict[str, Any]] = []
    for control in controls:
        if not isinstance(control, Mapping):
            raise WorkerBootstrapError("focused screenshot control is malformed")
        labels = (
            [control.get("selectedLabel")]
            if control.get("widget") == "selectbox"
            else control.get("optionLabels")
        )
        if (
            not isinstance(control.get("rootSelector"), str)
            or control.get("widget")
            not in {"segmented_control", "radio_horizontal", "selectbox"}
            or not isinstance(labels, list)
            or not labels
            or any(not isinstance(label, str) or not label for label in labels)
        ):
            raise WorkerBootstrapError("focused screenshot contract is malformed")
        specs.append(
            {
                "rootSelector": control["rootSelector"],
                "widget": control["widget"],
                "targetLabels": labels,
                "targetOverlapTolerance": (
                    1.0
                    if control["widget"] == "segmented_control"
                    else 0.5
                ),
            }
        )
    return specs


def _focused_screenshot_snapshot(
    page: Any,
    specs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    try:
        value = page.evaluate(
            _FOCUSED_SCREENSHOT_SNAPSHOT_SCRIPT,
            [dict(spec) for spec in specs],
        )
    except Exception as exc:
        raise WorkerBootstrapError(
            "focused screenshot geometry snapshot is unavailable"
        ) from exc
    if (
        not isinstance(value, dict)
        or set(value) != {"binding", "controls"}
        or not isinstance(value["binding"], dict)
        or not isinstance(value["controls"], list)
    ):
        raise WorkerBootstrapError("focused screenshot geometry is malformed")
    return value


def _prepare_focused_screenshot_evidence(
    page: Any,
    control_evidence: Mapping[str, Any],
    *,
    timeout_ms: int,
    schema_version: str = FOCUSED_CONTROL_EVIDENCE_V2_SCHEMA,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    if schema_version not in {
        FOCUSED_CONTROL_EVIDENCE_V2_SCHEMA,
        FOCUSED_CONTROL_EVIDENCE_V3_SCHEMA,
    }:
        raise WorkerBootstrapError(
            "focused screenshot evidence schema is unsupported"
        )
    specs = _focused_screenshot_specs(control_evidence)
    try:
        positioned = page.evaluate(
            _FOCUSED_SCREENSHOT_POSITION_SCRIPT,
            specs,
        )
    except Exception as exc:
        raise WorkerBootstrapError(
            "focused root group could not enter the screenshot viewport"
        ) from exc
    if positioned is not True:
        raise WorkerBootstrapError(
            "focused root group could not enter the screenshot viewport"
        )
    deadline = time.monotonic() + timeout_ms / 1_000
    _wait_for_focused_layout_prerequisites(page, deadline=deadline)
    previous: dict[str, Any] | None = None
    while True:
        current = _focused_screenshot_snapshot(page, specs)
        if current == previous:
            break
        previous = current
        page.wait_for_timeout(
            min(
                50,
                _focused_remaining_timeout_ms(
                    deadline,
                    label="focused screenshot geometry",
                ),
            )
        )
    if previous is None:
        raise WorkerBootstrapError("focused screenshot geometry is unavailable")
    controls = control_evidence.get("controls")
    assert isinstance(controls, list)
    snapshot_controls = previous["controls"]
    if len(snapshot_controls) != len(controls):
        raise WorkerBootstrapError("focused screenshot control count differs")
    updated_controls: list[dict[str, Any]] = []
    for control, snapshot in zip(controls, snapshot_controls, strict=True):
        if (
            not isinstance(control, Mapping)
            or not isinstance(snapshot, Mapping)
            or snapshot.get("rootSelector") != control.get("rootSelector")
            or set(snapshot) != {"rootSelector", "targets", "layout"}
        ):
            raise WorkerBootstrapError("focused screenshot control order differs")
        updated = dict(control)
        updated["targets"] = snapshot["targets"]
        updated["layout"] = snapshot["layout"]
        updated_controls.append(updated)
    evidence = {
        "schemaVersion": schema_version,
        "case": control_evidence["case"],
        "projection": control_evidence["projection"],
        "controls": updated_controls,
        "screenshotBinding": previous["binding"],
    }
    return evidence, previous, [dict(spec) for spec in specs]


def _project_nodes(
    raw_nodes: Any,
    *,
    expected_root_selectors: Sequence[str],
) -> list[dict[str, Any]]:
    if not isinstance(raw_nodes, list):
        raise WorkerBootstrapError("browser DOM projection is malformed")
    paths: dict[str, str] = {}
    node_ids: set[str] = set()
    for row in raw_nodes:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise WorkerBootstrapError("browser DOM node is malformed")
        path = row["path"]
        node_id = _stable_node_id(path)
        if not path or node_id in node_ids or path in paths:
            raise WorkerBootstrapError("browser DOM projection has duplicate identities")
        paths[path] = node_id
        node_ids.add(node_id)
    projected: list[dict[str, Any]] = []
    for row in raw_nodes:
        parent_path = row.get("parentPath")
        boundary_path = row.get("boundaryPath")
        bounds = row.get("bounds")
        state_value = row.get("state")
        if not isinstance(bounds, dict) or not isinstance(state_value, dict):
            raise WorkerBootstrapError("browser DOM node payload is malformed")
        if parent_path is not None and (
            not isinstance(parent_path, str) or parent_path not in paths
        ):
            raise WorkerBootstrapError("browser DOM parent identity is unresolved")
        if boundary_path is not None and (
            not isinstance(boundary_path, str) or boundary_path not in paths
        ):
            raise WorkerBootstrapError("browser DOM boundary identity is unresolved")
        projected.append(
            {
                "id": paths[row["path"]],
                "parentId": paths[parent_path] if isinstance(parent_path, str) else None,
                "flowScope": row.get("flowScope"),
                "boundaryId": (
                    paths[boundary_path] if isinstance(boundary_path, str) else None
                ),
                "rootSelector": row.get("rootSelector"),
                "role": row.get("role"),
                "name": row.get("name"),
                "text": row.get("text"),
                "state": state_value,
                "visible": row.get("visible"),
                "bounds": bounds,
            }
        )
    expected = tuple(expected_root_selectors)
    observed = [
        node["rootSelector"]
        for node in projected
        if node["rootSelector"] is not None
    ]
    if len(observed) != len(expected) or set(observed) != set(expected):
        raise WorkerBootstrapError(
            "browser DOM control roots differ from the frozen catalog"
        )
    by_id = {node["id"]: node for node in projected}
    for node in projected:
        selector = node["rootSelector"]
        if selector is None:
            continue
        boundary_id = node["boundaryId"]
        boundary = by_id.get(boundary_id)
        if (
            not isinstance(boundary_id, str)
            or boundary is None
            or boundary["id"] != boundary_id
            or boundary["flowScope"] != node["flowScope"]
        ):
            raise WorkerBootstrapError(
                "browser DOM control boundary is not a projected node"
            )
    return projected


def _wait_for_stable_focused_capture_projection(
    page: Any,
    *,
    expected_snapshot: Mapping[str, Any],
    specs: Sequence[Mapping[str, Any]],
    root_selectors: Sequence[str],
    affected_root_selectors: Sequence[str],
    timeout_ms: int,
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout_ms / 1_000
    previous_nodes: list[dict[str, Any]] | None = None
    quiet_started: float | None = None
    while True:
        if _focused_screenshot_snapshot(page, specs) != expected_snapshot:
            raise WorkerBootstrapError(
                "focused screenshot binding changed before capture"
            )
        nodes = _project_nodes(
            page.evaluate(
                _DOM_PROJECTION_SCRIPT,
                {
                    "rootSelectors": list(root_selectors),
                    "affectedRootSelectors": list(
                        affected_root_selectors
                    ),
                },
            ),
            expected_root_selectors=root_selectors,
        )
        now = time.monotonic()
        if nodes == previous_nodes:
            if quiet_started is None:
                quiet_started = now
            elif now - quiet_started >= 0.3:
                return nodes
        else:
            previous_nodes = nodes
            quiet_started = None
        page.wait_for_timeout(
            min(
                50,
                _focused_remaining_timeout_ms(
                    deadline,
                    label="focused screenshot DOM projection",
                ),
            )
        )


def _observe_readiness(
    page: Any,
    capture_identity: Mapping[str, Any],
    *,
    timeout_ms: int,
) -> str:
    readiness = capture_identity.get("readiness")
    if not isinstance(readiness, Mapping):
        raise WorkerBootstrapError("capture readiness contract is malformed")
    kind = readiness.get("kind")
    if kind == "selector":
        selector = readiness.get("selector")
        marker_name = readiness.get("text")
        match = readiness.get("match")
        title = readiness.get("title")
        if (
            not isinstance(selector, str)
            or not isinstance(marker_name, str)
            or match not in {"exact", "contains"}
            or (title is not None and not isinstance(title, str))
        ):
            raise WorkerBootstrapError("capture selector readiness is malformed")
        marker = page.locator(selector)
        marker.wait_for(state="attached", timeout=timeout_ms)
        if marker.count() != 1:
            raise WorkerBootstrapError("capture readiness marker is not unique")
        observed_text = re.sub(r"\s+", " ", marker.inner_text()).strip()
        text_matches = (
            observed_text == marker_name
            if match == "exact"
            else marker_name in observed_text
        )
        if not text_matches:
            raise WorkerBootstrapError("capture readiness marker text differs")
        if title is not None and page.title() != title:
            raise WorkerBootstrapError("capture fixture title differs from its contract")
        return marker_name
    if kind != "heading":
        raise WorkerBootstrapError("capture readiness kind is unsupported")
    level = readiness.get("level")
    marker_name = readiness.get("text")
    match = readiness.get("match")
    if (
        not isinstance(level, int)
        or isinstance(level, bool)
        or not isinstance(marker_name, str)
        or match not in {"exact", "contains"}
    ):
        raise WorkerBootstrapError("capture heading readiness is malformed")
    main = page.locator('[data-testid="stMainBlockContainer"]')
    heading = main.get_by_role(
        "heading",
        name=marker_name,
        exact=match == "exact",
        level=level,
    )
    heading.first.wait_for(state="visible", timeout=timeout_ms)
    if heading.count() != 1:
        raise WorkerBootstrapError("page readiness heading is not unique")
    return marker_name


def _wait_for_full_page_completion(
    page: Any,
    request: Mapping[str, Any],
    *,
    timeout_ms: int,
) -> None:
    """Keep the browser session alive until the complete real app returns."""

    if request.get("fixtureEntrypoint") != "scripts/ui_ux_fixture_app.py":
        return
    request_id = request.get("requestId")
    if not _is_safe_request_id(request_id):
        raise WorkerBootstrapError("full-page completion identity is invalid")
    marker = page.locator(f"#{FULL_PAGE_COMPLETION_MARKER_ID}")
    marker.wait_for(state="attached", timeout=timeout_ms)
    if marker.count() != 1:
        raise WorkerBootstrapError("full-page completion marker is not unique")
    observed = re.sub(r"\s+", " ", marker.inner_text()).strip()
    if observed != request_id:
        raise WorkerBootstrapError("full-page completion identity differs")


def _assert_final_url(
    url: str,
    *,
    origin: tuple[str, str, int, str],
    route: str,
    request_id: str,
) -> str:
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
        query = urllib.parse.parse_qsl(
            parsed.query,
            keep_blank_values=True,
            strict_parsing=True,
        )
    except (ValueError, UnicodeError) as exc:
        raise WorkerBootstrapError("browser final URL is malformed") from exc
    if (
        parsed.scheme != origin[0]
        or parsed.hostname != origin[1]
        or port != origin[2]
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != route
        or query != [("ux0_capture", request_id)]
        or parsed.fragment
    ):
        raise WorkerBootstrapError("browser final URL differs from its launch contract")
    return parsed.path or "/"


def _stable_state(
    nodes: Sequence[Mapping[str, Any]],
    final_path: str,
    diagnostics: Mapping[str, int],
) -> dict[str, Any]:
    controls: dict[str, Any] = {}
    for node in nodes:
        role = node.get("role")
        if role not in {
            "button",
            "checkbox",
            "combobox",
            "listbox",
            "radio",
            "radiogroup",
            "slider",
            "tab",
            "textbox",
        }:
            continue
        key = str(node.get("id"))
        controls[key] = {
            "rootSelector": node.get("rootSelector"),
            "role": role,
            "name": node.get("name"),
            "state": node.get("state"),
        }
    return {
        "finalPath": final_path,
        "controls": controls,
        "diagnostics": dict(diagnostics),
    }


def _collect_theme_evidence_for_capture(
    request: Mapping[str, Any],
    capture_identity: Mapping[str, Any],
    *,
    page: Any,
    browser: Any,
) -> dict[str, Any] | None:
    """Run the mirrored pure theme oracle only for the frozen gallery row."""

    if request.get("case") != "theme-gallery":
        return None
    expected_identity = {
        "fixtureEntrypoint": "scripts/ui_ux_theme_fixture_app.py",
        "case": "theme-gallery",
        "route": "/",
        "registryKey": "theme-gallery",
        "callable": "ui_ux_theme_fixture_app",
        "rootSelectors": (),
    }
    if any(
        capture_identity.get(key) != expected
        for key, expected in expected_identity.items()
    ) or request.get("fixtureEntrypoint") != expected_identity["fixtureEntrypoint"]:
        raise WorkerBootstrapError("theme collector identity differs from the frozen gallery")
    viewport = request.get("viewport")
    if not isinstance(viewport, Mapping):
        raise WorkerBootstrapError("theme collector viewport is malformed")
    browser_version = getattr(browser, "version", None)
    if not isinstance(browser_version, str) or not browser_version:
        raise WorkerDependencyUnavailable("Chromium version is unavailable")
    try:
        from scripts import ui_ux_theme_matrix as theme_matrix
    except (ImportError, SyntaxError) as exc:
        raise WorkerDependencyUnavailable("theme collector is unavailable") from exc
    collector = getattr(theme_matrix, "collect_external_worker_theme_evidence", None)
    if not callable(collector):
        raise WorkerDependencyUnavailable("theme collector API is unavailable")
    result = collector(
        page,
        viewport_name=viewport.get("name"),
        viewport=(viewport.get("width"), viewport.get("height")),
        browser_name="chromium",
        browser_version=browser_version,
    )
    if not isinstance(result, Mapping):
        raise WorkerBootstrapError("theme collector returned malformed evidence")
    return dict(result)


def _verify_theme_geometry_after_screenshot(
    request: Mapping[str, Any],
    theme_evidence: Mapping[str, Any] | None,
    *,
    page: Any,
) -> None:
    """Invoke the mirrored post-screenshot geometry oracle for theme only."""

    if theme_evidence is None:
        if request.get("case") == "theme-gallery":
            raise WorkerBootstrapError("theme capture lacks rich geometry evidence")
        return
    try:
        from scripts import ui_ux_theme_matrix as theme_matrix
    except (ImportError, SyntaxError) as exc:
        raise WorkerDependencyUnavailable("theme geometry verifier is unavailable") from exc
    verifier = getattr(
        theme_matrix,
        "verify_external_worker_theme_geometry_after_screenshot",
        None,
    )
    if not callable(verifier):
        raise WorkerDependencyUnavailable("theme geometry verifier API is unavailable")
    verifier(page, theme_evidence)


def _verify_theme_screenshot_dimensions(
    request: Mapping[str, Any],
    theme_evidence: Mapping[str, Any] | None,
    *,
    png_width: int,
    png_height: int,
) -> None:
    """Bind the authoritative theme PNG exactly to measured full-page geometry."""

    if theme_evidence is None:
        if request.get("case") == "theme-gallery":
            raise WorkerBootstrapError("theme capture lacks rich full-page evidence")
        return
    full_page = theme_evidence.get("fullPage")
    if (
        request.get("case") != "theme-gallery"
        or not isinstance(full_page, Mapping)
        or set(full_page) != {"width", "height", "deviceScaleFactor"}
        or full_page.get("deviceScaleFactor") != 1
        or (png_width, png_height)
        != (full_page.get("width"), full_page.get("height"))
    ):
        raise WorkerBootstrapError(
            "theme screenshot dimensions differ from measured full-page geometry"
        )


def _wait_for_stable_complete_projection(
    page: Any,
    *,
    root_selectors: Sequence[str],
    affected_root_selectors: Sequence[str],
    timeout_ms: int,
    label: str,
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout_ms / 1_000
    previous: list[dict[str, Any]] | None = None
    quiet_started: float | None = None
    while True:
        nodes = _project_nodes(
            page.evaluate(
                _DOM_PROJECTION_SCRIPT,
                {
                    "rootSelectors": list(root_selectors),
                    "affectedRootSelectors": list(affected_root_selectors),
                },
            ),
            expected_root_selectors=root_selectors,
        )
        now = time.monotonic()
        if nodes == previous:
            if quiet_started is None:
                quiet_started = now
            elif now - quiet_started >= 0.3:
                return nodes
        else:
            previous = nodes
            quiet_started = None
        page.wait_for_timeout(
            min(
                50,
                _focused_remaining_timeout_ms(deadline, label=label),
            )
        )


def _capture_root_outputs(
    request: Mapping[str, Any],
    *,
    page: Any,
    evidence: Any,
    capture_identity: Mapping[str, Any],
    control_evidence: Mapping[str, Any],
    root_selectors: Sequence[str],
    affected_root_selectors: Sequence[str],
    readiness_marker: str,
    final_path: str,
    interaction_record: Mapping[str, Any] | None,
    diagnostics: Mapping[str, int],
    source_root: Path,
    browser_root: Path,
    timeout_ms: int,
) -> list[tuple[bytes, bytes]]:
    """Capture one ordered root pair per frozen output without reloading."""

    if request.get("schemaVersion") != WORKER_REQUEST_V2_SCHEMA:
        raise WorkerBootstrapError("root output capture requires request v2")
    root_outputs = request.get("rootOutputs")
    controls = control_evidence.get("controls")
    if (
        not isinstance(root_outputs, list)
        or not root_outputs
        or not isinstance(controls, list)
        or not controls
    ):
        raise WorkerBootstrapError("root output capture contract is malformed")

    semantic_nodes = _wait_for_stable_complete_projection(
        page,
        root_selectors=root_selectors,
        affected_root_selectors=affected_root_selectors,
        timeout_ms=timeout_ms,
        label="case semantic DOM projection",
    )
    semantic_stable_state = _stable_state(
        semantic_nodes,
        final_path,
        diagnostics,
    )
    if interaction_record is not None:
        semantic_stable_state["interaction"] = dict(interaction_record)
    semantic_stable_state["registryKey"] = capture_identity["registryKey"]
    logical_capture_id = request["requestId"]
    runtime_projection = {
        "sourceRoot": str(source_root),
        "browserScratchRoot": str(browser_root),
    }
    case_semantic_projection = {
        "schemaVersion": CASE_SEMANTIC_PROJECTION_SCHEMA,
        "identity": {
            "fixtureEntrypoint": request["fixtureEntrypoint"],
            "logicalCaptureId": logical_capture_id,
            "case": request["case"],
            "route": request["route"],
            "callable": capture_identity["callable"],
            "viewport": dict(request["viewport"]),
        },
        "readiness": {
            "ready": True,
            "marker": readiness_marker,
        },
        "nodes": semantic_nodes,
        "stableState": semantic_stable_state,
        "providerCounters": {},
        "mutatorCounters": {},
        "runtimeProjection": runtime_projection,
        "counterProvenance": None,
        "controlEvidence": dict(control_evidence),
    }

    results: list[tuple[bytes, bytes]] = []
    semantic_bytes: bytes | None = None
    for output in root_outputs:
        if not isinstance(output, Mapping):
            raise WorkerBootstrapError("root output row is malformed")
        selector = output.get("rootSelector")
        matching_controls = [
            dict(control)
            for control in controls
            if isinstance(control, Mapping)
            and control.get("rootSelector") == selector
        ]
        if len(matching_controls) != 1:
            raise WorkerBootstrapError(
                "root output selector differs from audited controls"
            )
        root_control_evidence = {
            "schemaVersion": FOCUSED_CONTROL_EVIDENCE_SCHEMA,
            "case": control_evidence["case"],
            "projection": control_evidence["projection"],
            "controls": matching_controls,
        }
        (
            focused_evidence,
            focused_snapshot,
            focused_specs,
        ) = _prepare_focused_screenshot_evidence(
            page,
            root_control_evidence,
            timeout_ms=timeout_ms,
            schema_version=FOCUSED_CONTROL_EVIDENCE_V3_SCHEMA,
        )
        nodes = _wait_for_stable_focused_capture_projection(
            page,
            expected_snapshot=focused_snapshot,
            specs=focused_specs,
            root_selectors=root_selectors,
            affected_root_selectors=affected_root_selectors,
            timeout_ms=timeout_ms,
        )
        screenshot = page.screenshot(
            full_page=False,
            animations="disabled",
            caret="hide",
        )
        if not isinstance(screenshot, bytes):
            raise WorkerBootstrapError(
                "Playwright returned an invalid root screenshot"
            )
        png_width, png_height = _png_dimensions(screenshot)
        viewport = request["viewport"]
        if (
            png_width != viewport["width"]
            or png_height != viewport["height"]
        ):
            raise WorkerBootstrapError(
                "root screenshot dimensions differ from the viewport contract"
            )
        if (
            _focused_screenshot_snapshot(page, focused_specs)
            != focused_snapshot
        ):
            raise WorkerBootstrapError(
                "root screenshot focused binding changed after capture"
            )
        post_nodes = _project_nodes(
            page.evaluate(
                _DOM_PROJECTION_SCRIPT,
                {
                    "rootSelectors": list(root_selectors),
                    "affectedRootSelectors": list(
                        affected_root_selectors
                    ),
                },
            ),
            expected_root_selectors=root_selectors,
        )
        if post_nodes != nodes:
            raise WorkerBootstrapError(
                "root screenshot DOM projection changed after capture"
            )
        if any(diagnostics.values()):
            raise WorkerBootstrapError(
                "browser event contract changed during root capture"
            )
        root_capture = {
            "logicalCaptureId": logical_capture_id,
            "rootCaptureId": output["rootCaptureId"],
            "rootOrdinal": output["rootOrdinal"],
            "rootSelector": selector,
            "rootExpansionSha256": evidence.ROOT_CAPTURE_EXPANSION_SHA256,
        }
        sidecar_document = {
            "schemaVersion": RENDER_V2_SCHEMA,
            "identity": {
                "case": request["case"],
                "route": request["route"],
                "callable": capture_identity["callable"],
            },
            "viewport": dict(viewport),
            "readiness": {
                "ready": True,
                "marker": readiness_marker,
            },
            "nodes": nodes,
            "stableState": semantic_stable_state,
            "providerCounters": {},
            "mutatorCounters": {},
            "runtimeProjection": runtime_projection,
            "counterProvenance": None,
            "rootCapture": root_capture,
            "controlEvidence": focused_evidence,
            "caseSemanticProjection": case_semantic_projection,
        }
        sidecar = evidence.canonicalize_worker_render_sidecar(
            sidecar_document,
            owned_roots=(str(source_root), str(browser_root)),
        )
        if not isinstance(sidecar, bytes):
            raise WorkerBootstrapError(
                "canonical root sidecar encoder returned invalid data"
            )
        normalized = json.loads(sidecar)
        sibling_semantic = _canonical_json(
            normalized["caseSemanticProjection"]
        )
        if semantic_bytes is None:
            semantic_bytes = sibling_semantic
        elif sibling_semantic != semantic_bytes:
            raise WorkerBootstrapError(
                "sibling case semantic projections differ"
            )
        results.append((screenshot, sidecar))
    if len(results) != len(root_outputs):
        raise WorkerBootstrapError("root capture output count differs")
    return results


def _capture(
    request: Mapping[str, Any],
    *,
    capture_identity: Mapping[str, Any],
    evidence: Any,
    source_root: Path,
    browser_root: Path,
    browser_executable: str | None,
    timeout_ms: int,
) -> tuple[bytes, bytes] | list[tuple[bytes, bytes]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise WorkerDependencyUnavailable("Playwright is unavailable") from exc

    origin = _parse_exact_origin(str(request["appOrigin"]))
    viewport = request["viewport"]
    width = viewport["width"]
    height = viewport["height"]
    root_selectors, affected_root_selectors = _root_selectors(capture_identity)
    blocked_count = 0
    failed_request_count = 0
    http_error_count = 0
    page_error_count = 0
    console_error_count = 0
    dialog_count = 0
    download_count = 0
    popup_count = 0
    crash_count = 0
    browser = None
    context = None
    try:
        with sync_playwright() as playwright:
            executable = browser_executable or playwright.chromium.executable_path
            if not isinstance(executable, str) or not executable:
                raise WorkerDependencyUnavailable("Chromium executable is unavailable")
            try:
                executable_stat = os.lstat(executable)
            except OSError as exc:
                raise WorkerDependencyUnavailable("Chromium executable is unavailable") from exc
            if stat.S_ISLNK(executable_stat.st_mode) or not stat.S_ISREG(
                executable_stat.st_mode
            ):
                raise WorkerDependencyUnavailable("Chromium executable identity is invalid")
            browser = playwright.chromium.launch(
                executable_path=executable,
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-background-networking",
                    "--disable-breakpad",
                    "--disable-component-update",
                    "--disable-crash-reporter",
                    "--disable-sync",
                    "--metrics-recording-only",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
            context = browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
                service_workers="block",
                accept_downloads=False,
                locale="zh-TW",
                timezone_id="Asia/Taipei",
                reduced_motion="reduce",
                color_scheme="dark",
            )
            benign_404 = _BenignStreamlit404Correlation(
                origin=origin, route=request["route"]
            )

            def handle_route(route: Any, browser_request: Any) -> None:
                nonlocal blocked_count
                if _is_allowed_url(browser_request.url, origin=origin):
                    route.continue_()
                    return
                blocked_count += 1
                route.abort("blockedbyclient")

            context.route("**/*", handle_route)
            route_web_socket = getattr(context, "route_web_socket", None)
            if not callable(route_web_socket):
                raise WorkerDependencyUnavailable(
                    "installed Playwright lacks required WebSocket routing"
                )

            def handle_web_socket(web_socket: Any) -> None:
                nonlocal blocked_count
                if _is_allowed_url(web_socket.url, origin=origin):
                    web_socket.connect_to_server()
                    return
                blocked_count += 1

            route_web_socket("**/*", handle_web_socket)
            page = context.new_page()

            def request_failed(_request: Any) -> None:
                nonlocal failed_request_count
                failed_request_count += 1

            page.on("requestfailed", request_failed)

            def response_observed(response_value: Any) -> None:
                nonlocal http_error_count
                status = getattr(response_value, "status", None)
                if type(status) is not int:
                    http_error_count += 1
                    return
                if status < 400:
                    return
                if benign_404.observe_response(response_value):
                    return
                http_error_count += 1

            def page_error_observed(_error: Any) -> None:
                nonlocal page_error_count
                page_error_count += 1

            def console_observed(message: Any) -> None:
                nonlocal console_error_count
                if str(message.type).lower() == "error":
                    if not benign_404.observe_console(message):
                        console_error_count += 1

            def dialog_observed(dialog: Any) -> None:
                nonlocal dialog_count
                dialog_count += 1
                try:
                    dialog.dismiss()
                except Exception:
                    pass

            def download_observed(download: Any) -> None:
                nonlocal download_count
                download_count += 1
                try:
                    download.cancel()
                except Exception:
                    pass

            def popup_observed(popup: Any) -> None:
                nonlocal popup_count
                popup_count += 1
                try:
                    popup.close()
                except Exception:
                    pass

            def crash_observed(_page: Any) -> None:
                nonlocal crash_count
                crash_count += 1

            page.on("response", response_observed)
            page.on("pageerror", page_error_observed)
            page.on("console", console_observed)
            page.on("dialog", dialog_observed)
            page.on("download", download_observed)
            page.on("popup", popup_observed)
            page.on("crash", crash_observed)
            query = urllib.parse.urlencode({"ux0_capture": request["requestId"]})
            target = f"{origin[3]}{request['route']}?{query}"
            response = page.goto(target, wait_until="domcontentloaded", timeout=timeout_ms)
            if response is None or not response.ok:
                raise WorkerBootstrapError("application navigation did not return success")
            page.locator('[data-testid="stMainBlockContainer"]').wait_for(
                state="visible", timeout=timeout_ms
            )
            readiness_marker = _observe_readiness(
                page,
                capture_identity,
                timeout_ms=timeout_ms,
            )
            _wait_for_full_page_completion(
                page,
                request,
                timeout_ms=timeout_ms,
            )
            _wait_for_full_page_catalog_roots(
                page,
                capture_identity,
                timeout_ms=timeout_ms,
            )
            interaction_record = _perform_capture_interaction(
                page,
                capture_identity,
                timeout_ms=timeout_ms,
            )
            control_evidence = _collect_focused_control_evidence(
                page,
                capture_identity,
                timeout_ms=timeout_ms,
            )
            _wait_for_document_fonts(
                page,
                timeout_ms=timeout_ms,
                label="capture document fonts",
            )
            page.wait_for_function(_READINESS_SCRIPT, timeout=timeout_ms)
            page.wait_for_function(_STABLE_LAYOUT_SCRIPT, timeout=timeout_ms)
            page.wait_for_function(_PLOTLY_READY_SCRIPT, timeout=timeout_ms)
            page.wait_for_function(_STABLE_LAYOUT_SCRIPT, timeout=timeout_ms)
            final_path = _assert_final_url(
                page.url,
                origin=origin,
                route=request["route"],
                request_id=request["requestId"],
            )
            exception_count = page.locator('[data-testid="stException"]:visible').count()
            if exception_count:
                raise WorkerBootstrapError("Streamlit rendered an exception")
            if page_error_count:
                raise WorkerBootstrapError("browser page execution failed")
            if http_error_count:
                raise WorkerBootstrapError("application returned an HTTP error")
            if console_error_count:
                raise WorkerBootstrapError("browser console reported an error")
            if failed_request_count:
                raise WorkerBootstrapError("browser request failed")
            if blocked_count:
                raise WorkerBootstrapError("browser attempted a request outside the app origin")
            if any((dialog_count, download_count, popup_count, crash_count)):
                raise WorkerBootstrapError("browser emitted an unexpected event")
            diagnostics = {
                "blockedRequestCount": blocked_count,
                "failedRequestCount": failed_request_count,
                "httpErrorCount": http_error_count,
                "pageErrorCount": page_error_count,
                "consoleErrorCount": console_error_count,
                "dialogCount": dialog_count,
                "downloadCount": download_count,
                "popupCount": popup_count,
                "crashCount": crash_count,
            }
            if request.get("schemaVersion") == WORKER_REQUEST_V2_SCHEMA:
                if control_evidence is None:
                    raise WorkerBootstrapError(
                        "root capture request lacks focused control evidence"
                    )
                root_results = _capture_root_outputs(
                    request,
                    page=page,
                    evidence=evidence,
                    capture_identity=capture_identity,
                    control_evidence=control_evidence,
                    root_selectors=root_selectors,
                    affected_root_selectors=affected_root_selectors,
                    readiness_marker=readiness_marker,
                    final_path=final_path,
                    interaction_record=interaction_record,
                    diagnostics=diagnostics,
                    source_root=source_root,
                    browser_root=browser_root,
                    timeout_ms=timeout_ms,
                )
                if any(
                    (
                        blocked_count,
                        failed_request_count,
                        http_error_count,
                        page_error_count,
                        console_error_count,
                        dialog_count,
                        download_count,
                        popup_count,
                        crash_count,
                    )
                ):
                    raise WorkerBootstrapError(
                        "browser event contract changed during root capture"
                    )
                benign_404.assert_complete()
                return root_results
            focused_screenshot_snapshot: dict[str, Any] | None = None
            focused_screenshot_specs: list[dict[str, Any]] = []
            if control_evidence is not None:
                (
                    control_evidence,
                    focused_screenshot_snapshot,
                    focused_screenshot_specs,
                ) = _prepare_focused_screenshot_evidence(
                    page,
                    control_evidence,
                    timeout_ms=timeout_ms,
                )
            if focused_screenshot_snapshot is None:
                nodes = _project_nodes(
                    page.evaluate(
                        _DOM_PROJECTION_SCRIPT,
                        {
                            "rootSelectors": list(root_selectors),
                            "affectedRootSelectors": list(
                                affected_root_selectors
                            ),
                        },
                    ),
                    expected_root_selectors=root_selectors,
                )
            else:
                nodes = _wait_for_stable_focused_capture_projection(
                    page,
                    expected_snapshot=focused_screenshot_snapshot,
                    specs=focused_screenshot_specs,
                    root_selectors=root_selectors,
                    affected_root_selectors=affected_root_selectors,
                    timeout_ms=timeout_ms,
                )
            diagnostics = {
                "blockedRequestCount": blocked_count,
                "failedRequestCount": failed_request_count,
                "httpErrorCount": http_error_count,
                "pageErrorCount": page_error_count,
                "consoleErrorCount": console_error_count,
                "dialogCount": dialog_count,
                "downloadCount": download_count,
                "popupCount": popup_count,
                "crashCount": crash_count,
            }
            stable_state = _stable_state(nodes, final_path, diagnostics)
            if interaction_record is not None:
                stable_state["interaction"] = interaction_record
            theme_evidence = _collect_theme_evidence_for_capture(
                request,
                capture_identity,
                page=page,
                browser=browser,
            )
            if theme_evidence is not None:
                stable_state["themeEvidence"] = theme_evidence
                _wait_for_document_fonts(
                    page,
                    timeout_ms=timeout_ms,
                    label="post-theme capture document fonts",
                )
                page.wait_for_function(_READINESS_SCRIPT, timeout=timeout_ms)
                page.wait_for_function(_STABLE_LAYOUT_SCRIPT, timeout=timeout_ms)
                page.wait_for_function(_PLOTLY_READY_SCRIPT, timeout=timeout_ms)
                page.wait_for_function(_STABLE_LAYOUT_SCRIPT, timeout=timeout_ms)
            screenshot = page.screenshot(
                full_page=control_evidence is None,
                animations="disabled",
                caret="hide",
            )
            if not isinstance(screenshot, bytes):
                raise WorkerBootstrapError("Playwright returned an invalid screenshot")
            png_width, png_height = _png_dimensions(screenshot)
            if (
                png_width != width
                or (
                    png_height != height
                    if control_evidence is not None
                    else png_height < height
                )
            ):
                raise WorkerBootstrapError(
                    "browser screenshot dimensions differ from the viewport contract"
                )
            if control_evidence is not None:
                post_screenshot_snapshot = _focused_screenshot_snapshot(
                    page,
                    focused_screenshot_specs,
                )
                post_screenshot_nodes = _project_nodes(
                    page.evaluate(
                        _DOM_PROJECTION_SCRIPT,
                        {
                            "rootSelectors": list(root_selectors),
                            "affectedRootSelectors": list(
                                affected_root_selectors
                            ),
                        },
                    ),
                    expected_root_selectors=root_selectors,
                )
                if (
                    focused_screenshot_snapshot is None
                    or post_screenshot_snapshot
                    != focused_screenshot_snapshot
                    or post_screenshot_nodes != nodes
                ):
                    raise WorkerBootstrapError(
                        "focused screenshot pre/post evidence differs"
                    )
            _verify_theme_screenshot_dimensions(
                request,
                theme_evidence,
                png_width=png_width,
                png_height=png_height,
            )
            _verify_theme_geometry_after_screenshot(
                request,
                theme_evidence,
                page=page,
            )
            sidecar_document = {
                "schemaVersion": RENDER_SCHEMA,
                "identity": {
                    "case": request["case"],
                    "route": request["route"],
                    "callable": capture_identity["callable"],
                },
                "viewport": dict(viewport),
                "readiness": {
                    "ready": True,
                    "marker": readiness_marker,
                },
                "nodes": nodes,
                "stableState": {
                    **stable_state,
                    "registryKey": capture_identity["registryKey"],
                },
                # Counter files are app-private by design.  These must remain
                # empty in the untrusted staged observation; after both child
                # process groups quiesce, the coordinator descriptor-authenticates
                # the app counter file and authors the counter-complete final
                # canonical sidecar.  A staged sidecar is never final evidence.
                "providerCounters": {},
                "mutatorCounters": {},
                "runtimeProjection": {
                    "sourceRoot": str(source_root),
                    "browserScratchRoot": str(browser_root),
                },
            }
            if control_evidence is not None:
                sidecar_document["controlEvidence"] = control_evidence
            worker_sidecar_encoder = getattr(
                evidence, "canonicalize_worker_render_sidecar", None
            )
            if not callable(worker_sidecar_encoder):
                raise WorkerDependencyUnavailable(
                    "evidence API staged-sidecar encoder is unavailable"
                )
            sidecar = worker_sidecar_encoder(
                sidecar_document,
                owned_roots=(str(source_root), str(browser_root)),
            )
            if not isinstance(sidecar, bytes):
                raise WorkerBootstrapError("canonical sidecar encoder returned invalid data")
            if any(
                (
                    blocked_count,
                    failed_request_count,
                    http_error_count,
                    page_error_count,
                    console_error_count,
                    dialog_count,
                    download_count,
                    popup_count,
                    crash_count,
                )
            ):
                raise WorkerBootstrapError("browser event contract changed during capture")
            benign_404.assert_complete()
            return screenshot, sidecar
    except WorkerBootstrapError:
        raise
    except WorkerDependencyUnavailable:
        raise
    except KeyboardInterrupt:
        raise
    except evidence.EvidenceContractError:
        raise
    except Exception as exc:
        # Playwright's concrete error classes change across releases.  Missing
        # executable messages are dependency failures; all other runtime
        # failures retain the generic failed classification at the boundary.
        if type(exc).__name__ in {"ImportError", "ModuleNotFoundError"}:
            raise WorkerDependencyUnavailable("browser dependency is unavailable") from exc
        raise RuntimeError("browser capture failed") from exc
    finally:
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass


def _failure_status(exc: BaseException, evidence: Any | None) -> tuple[str, str, str]:
    dependency_types: tuple[type[BaseException], ...] = (WorkerDependencyUnavailable,)
    invalid_types: tuple[type[BaseException], ...] = (WorkerBootstrapError,)
    if evidence is not None:
        dependency = getattr(evidence, "DependencyUnavailable", None)
        invalid = getattr(evidence, "InvalidEvidence", None)
        contract = getattr(evidence, "EvidenceContractError", None)
        if isinstance(dependency, type) and issubclass(dependency, BaseException):
            dependency_types += (dependency,)
        for candidate in (invalid, contract):
            if isinstance(candidate, type) and issubclass(candidate, BaseException):
                invalid_types += (candidate,)
    if isinstance(exc, KeyboardInterrupt):
        return "interrupted", "KeyboardInterrupt", "browser capture was interrupted"
    if isinstance(exc, dependency_types):
        return "dependency_unavailable", type(exc).__name__, "browser dependency is unavailable"
    if isinstance(exc, invalid_types):
        return (
            "invalid_data",
            type(exc).__name__,
            "browser evidence input or output is invalid",
        )
    return "failed", type(exc).__name__, "browser capture failed"


def _bounded_message(message: str, limit: int) -> str:
    encoded = str(message).encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return encoded.decode("utf-8")
    clipped = encoded[:limit]
    while clipped:
        try:
            return clipped.decode("utf-8")
        except UnicodeDecodeError:
            clipped = clipped[:-1]
    return ""


def _safe_error_type(value: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", value):
        return value
    return "WorkerError"


def _response_bytes(document: Mapping[str, Any], *, maximum: int) -> bytes:
    payload = _canonical_json(document) + b"\n"
    if len(payload) > maximum:
        raise WorkerBootstrapError("worker response exceeds its fixed bound")
    return payload


def _negotiated_response_limit(evidence: Any | None, current: int) -> int:
    maximum = getattr(
        evidence,
        "MAX_WORKER_RESPONSE_BYTES",
        getattr(evidence, "MAX_WORKER_JSON_BYTES", current),
    )
    if not isinstance(maximum, int) or isinstance(maximum, bool):
        return current
    if not 1024 <= maximum <= _BOOTSTRAP_RESPONSE_LIMIT:
        return current
    return min(current, maximum)


def _emit(document: Mapping[str, Any], *, maximum: int) -> None:
    payload = _response_bytes(document, maximum=maximum)
    stream = sys.stdout.buffer
    stream.write(payload)
    stream.flush()


class _SilentArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        raise WorkerBootstrapError("worker launch arguments are invalid")

    def exit(self, _status: int = 0, _message: str | None = None) -> None:
        raise WorkerBootstrapError("worker launch arguments are invalid")


def _parser() -> argparse.ArgumentParser:
    parser = _SilentArgumentParser(add_help=False)
    parser.add_argument("--expected-origin", required=True)
    parser.add_argument("--expected-request-id", required=True)
    parser.add_argument("--allow-staging-path", action="append", required=True)
    parser.add_argument("--browser-executable")
    parser.add_argument("--timeout-ms", type=int, default=30_000)
    return parser


def _run(args: argparse.Namespace, raw: bytes, candidate: Mapping[str, Any]) -> dict[str, Any]:
    source_root, browser_root, browser_root_fd = _owned_roots()
    try:
        source_path = str(source_root)
        sys.path[:] = [item for item in sys.path if item != source_path]
        sys.path.insert(0, source_path)
        try:
            from scripts import ui_ux_evidence as evidence_module
        except (ImportError, SyntaxError) as exc:
            raise WorkerDependencyUnavailable("evidence API is unavailable") from exc
        evidence = evidence_module
        maximum = getattr(
            evidence,
            "MAX_WORKER_REQUEST_BYTES",
            getattr(evidence, "MAX_WORKER_JSON_BYTES", None),
        )
        if not isinstance(maximum, int) or not 1024 <= maximum <= 4 * 1024 * 1024:
            raise WorkerDependencyUnavailable("evidence API worker bound is invalid")
        if len(raw) > min(maximum, _BOOTSTRAP_REQUEST_LIMIT):
            raise WorkerBootstrapError("worker request exceeds its fixed bound")
        expected_origin = args.expected_origin
        _parse_exact_origin(expected_origin)
        if not _is_safe_request_id(args.expected_request_id):
            raise WorkerBootstrapError("worker expected request ID is invalid")
        candidate_schema = candidate.get("schemaVersion")
        if candidate_schema == WORKER_REQUEST_V2_SCHEMA:
            root_outputs = candidate.get("rootOutputs")
            if not isinstance(root_outputs, list) or len(root_outputs) not in {1, 2}:
                raise WorkerBootstrapError(
                    "worker root staging request is malformed"
                )
            candidate_path_values = [
                path
                for output in root_outputs
                if isinstance(output, Mapping)
                for staging in (output.get("staging"),)
                if isinstance(staging, Mapping)
                for path in (
                    staging.get("png"),
                    staging.get("renderSidecar"),
                )
                if isinstance(path, str)
            ]
            expected_path_count = 2 * len(root_outputs)
        else:
            staging = candidate.get("staging")
            if not isinstance(staging, Mapping):
                raise WorkerBootstrapError("worker staging request is malformed")
            candidate_path_values = [
                path
                for path in (staging.get("png"), staging.get("renderSidecar"))
                if isinstance(path, str)
            ]
            expected_path_count = 2
        candidate_paths = frozenset(candidate_path_values)
        if len(args.allow_staging_path) != expected_path_count:
            raise WorkerBootstrapError(
                "worker launch staging path count differs"
            )
        allowed_paths = frozenset(args.allow_staging_path)
        if (
            len(candidate_path_values) != expected_path_count
            or len(allowed_paths) != expected_path_count
            or allowed_paths != candidate_paths
        ):
            raise WorkerBootstrapError("worker staging paths differ from the launch contract")
        for path in allowed_paths:
            _strict_components(path, label="launch staging path")
        request = evidence.decode_worker_request(
            raw,
            expected_origin=expected_origin,
            allowed_staging_paths=allowed_paths,
        )
        expected_request_id = args.expected_request_id
        if request["requestId"] != expected_request_id:
            raise WorkerBootstrapError("worker request ID differs from its launch contract")
        _parse_exact_origin(request["appOrigin"])
        identity_validator = getattr(
            evidence, "validate_worker_capture_identity", None
        )
        if not callable(identity_validator):
            raise WorkerDependencyUnavailable(
                "evidence API capture catalog is unavailable"
            )
        capture_identity = identity_validator(request)
        if not isinstance(capture_identity, Mapping):
            raise WorkerDependencyUnavailable(
                "evidence API capture catalog returned invalid data"
            )
        _check_fixture_entrypoint(source_root, request["fixtureEntrypoint"])
        if not 1_000 <= args.timeout_ms <= 90_000:
            raise WorkerBootstrapError("browser timeout is outside the fixed range")
        capture_result = _capture(
            request,
            capture_identity=capture_identity,
            evidence=evidence,
            source_root=source_root,
            browser_root=browser_root,
            browser_executable=args.browser_executable,
            timeout_ms=args.timeout_ms,
        )
        png_limit = getattr(evidence, "MAX_PNG_BYTES", _DEFAULT_PNG_LIMIT)
        sidecar_limit = getattr(
            evidence, "MAX_RENDER_SIDECAR_BYTES", _DEFAULT_SIDECAR_LIMIT
        )
        if request.get("schemaVersion") == WORKER_REQUEST_V2_SCHEMA:
            if (
                not isinstance(capture_result, list)
                or len(capture_result) != len(request["rootOutputs"])
            ):
                raise WorkerBootstrapError("browser root capture result differs")
            root_artifacts: list[dict[str, Any]] = []
            for output, result in zip(
                request["rootOutputs"],
                capture_result,
                strict=True,
            ):
                if (
                    not isinstance(result, tuple)
                    or len(result) != 2
                    or not all(isinstance(item, bytes) for item in result)
                ):
                    raise WorkerBootstrapError(
                        "browser root artifact pair is malformed"
                    )
                screenshot, sidecar = result
                if not isinstance(png_limit, int) or len(screenshot) > png_limit:
                    raise WorkerBootstrapError(
                        "browser root screenshot exceeds its fixed bound"
                    )
                if (
                    not isinstance(sidecar_limit, int)
                    or len(sidecar) > sidecar_limit
                ):
                    raise WorkerBootstrapError(
                        "browser root render sidecar exceeds its fixed bound"
                    )
                staging = output["staging"]
                png_path = staging["png"]
                sidecar_path = staging["renderSidecar"]
                _write_exclusive(browser_root_fd, png_path, screenshot)
                _write_exclusive(browser_root_fd, sidecar_path, sidecar)
                root_artifacts.append(
                    {
                        "rootCaptureId": output["rootCaptureId"],
                        "logicalCaptureId": request["requestId"],
                        "rootOrdinal": output["rootOrdinal"],
                        "rootSelector": output["rootSelector"],
                        "png": png_path,
                        "renderSidecar": sidecar_path,
                    }
                )
            return {
                "schemaVersion": WORKER_RESPONSE_V2_SCHEMA,
                "requestId": request["requestId"],
                "status": "staged",
                "rootArtifacts": root_artifacts,
            }
        if (
            not isinstance(capture_result, tuple)
            or len(capture_result) != 2
        ):
            raise WorkerBootstrapError("browser capture result is malformed")
        screenshot, sidecar = capture_result
        if not isinstance(png_limit, int) or len(screenshot) > png_limit:
            raise WorkerBootstrapError("browser screenshot exceeds its fixed bound")
        if not isinstance(sidecar_limit, int) or len(sidecar) > sidecar_limit:
            raise WorkerBootstrapError("browser render sidecar exceeds its fixed bound")
        png_path = request["staging"]["png"]
        sidecar_path = request["staging"]["renderSidecar"]
        _write_exclusive(browser_root_fd, png_path, screenshot)
        # Failed leaves remain unclaimed in this disposable browser root.  A
        # pathname cleanup cannot atomically prove inode identity at unlink;
        # the coordinator removes the whole owned root only after process-group
        # quiescence and never authenticates artifacts from a failure response.
        _write_exclusive(browser_root_fd, sidecar_path, sidecar)
        return {
            "schemaVersion": WORKER_RESPONSE_SCHEMA,
            "requestId": request["requestId"],
            "status": "staged",
            "artifacts": {
                "png": png_path,
                "renderSidecar": sidecar_path,
            },
        }
    finally:
        os.close(browser_root_fd)


def main(argv: Sequence[str] | None = None) -> int:
    candidate: dict[str, Any] | None = None
    evidence = None
    response_limit = _BOOTSTRAP_RESPONSE_LIMIT
    request_id = "unknown"
    try:
        args = _parser().parse_args(argv)
        request_id = _safe_request_id(candidate, args.expected_request_id)
        raw = _read_one_record(sys.stdin.buffer)
        candidate = _bootstrap_request(raw)
        request_id = _safe_request_id(candidate, args.expected_request_id)
        result = _run(args, raw, candidate)
        loaded = sys.modules.get("scripts.ui_ux_evidence")
        evidence = loaded if loaded is not None else None
        response_limit = _negotiated_response_limit(evidence, response_limit)
        _emit(result, maximum=response_limit)
        return 0
    except BaseException as exc:  # The protocol must retain terminal child evidence.
        loaded = sys.modules.get("scripts.ui_ux_evidence")
        evidence = loaded if loaded is not None else evidence
        response_limit = _negotiated_response_limit(evidence, response_limit)
        status, error_type, message = _failure_status(exc, evidence)
        error_limit = getattr(evidence, "MAX_MANIFEST_ERROR_BYTES", _DEFAULT_ERROR_LIMIT)
        if not isinstance(error_limit, int) or error_limit <= 0:
            error_limit = _DEFAULT_ERROR_LIMIT
        failure = {
            "schemaVersion": (
                WORKER_RESPONSE_V2_SCHEMA
                if isinstance(candidate, Mapping)
                and candidate.get("schemaVersion") == WORKER_REQUEST_V2_SCHEMA
                else WORKER_RESPONSE_SCHEMA
            ),
            "requestId": request_id,
            "status": status,
            "error": {
                "type": _safe_error_type(error_type),
                # Reserve room for the canonical error object keys and type;
                # the evidence decoder bounds the whole error object.
                "message": _bounded_message(
                    message,
                    max(1, min(error_limit, _DEFAULT_ERROR_LIMIT) - 256),
                ),
            },
        }
        try:
            _emit(failure, maximum=response_limit)
        except BaseException:
            return 70
        return {
            "dependency_unavailable": 69,
            "invalid_data": 65,
            "interrupted": 130,
            "failed": 1,
        }[status]


if __name__ == "__main__":
    raise SystemExit(main())
