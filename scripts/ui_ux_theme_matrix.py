#!/usr/bin/env python3
"""Fail-closed UX-1B semantic-theme state and contrast matrix."""

from __future__ import annotations

import argparse
import copy
import contextlib
import errno
import functools
import hashlib
import io
import json
import math
import os
import re
import secrets
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence


VERSION = "0.1.0"
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
# SOURCE_ROOT becomes the authenticated read-only mirror in Task 5.  Keeping a
# separate seam now prevents accidental reuse of the writable workspace root.
SOURCE_ROOT = WORKSPACE_ROOT
ROOT = WORKSPACE_ROOT
BROWSER_WORKER_PATH = WORKSPACE_ROOT / "scripts" / "ui_ux_browser_worker.py"
UX1B_ROOT = (ROOT / ".claude" / "ui_snapshots" / "ux1b").resolve()
UX1B_CAPTURE_STACK_CONTRACT_PATH = (
    ROOT / "docs" / "ui-ux" / "quant-radar-ui-v2-ux1b-capture-stack.json"
)
FIXTURE_APP = ROOT / "scripts" / "ui_ux_theme_fixture_app.py"
OWNER_FILE = ".quant-radar-ux1b-theme-owner"
THEME_WORKER_RICH_EVIDENCE_BLOCKER = (
    "frozen external browser worker lacks the per-selector computed-style/state "
    "evidence and three authenticated per-surface screenshots required by the "
    "3x3 theme matrix"
)
THEME_WORKER_EVIDENCE_SCHEMA = "quant-radar-ui-ux-theme-worker-evidence/v1"

APPROVED_TOKENS: Mapping[str, str] = MappingProxyType({
    "interactive.primary": "#2563eb",
    "interactive.hover": "#1d4ed8",
    "interactive.active": "#1e40af",
    "interactive.accent": "#60a5fa",
    "interactive.control": "#3b82f6",
    "interactive.disabled": "#6b7280",
    "text.on-primary": "#ffffff",
    "text.disabled": "#8b93a7",
    "border.focus": "#7fe3f0",
})

SURFACE_COLORS: Mapping[str, str] = MappingProxyType({
    "canvas": "#0e1117",
    "panel": "#1a1f2b",
    "elevated": "#232938",
})

VIEWPORTS: Mapping[str, tuple[int, int]] = MappingProxyType({
    "desktop": (1440, 900),
    "tablet": (768, 1024),
    "mobile": (390, 844),
})

REQUIRED_GALLERY_CASES = (
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

FOCUS_CASES = (
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

FOCUS_SIDES = ("top", "right", "bottom", "left")

PRIMARY_CASES = ("primary", "form_submit", "download", "link_button")

CASE_ACCESSIBLE_NAMES: Mapping[str, str] = MappingProxyType({
    "primary": "主要操作",
    "form_submit": "送出表單",
    "download": "下載固定資料",
    "link_button": "開啟本頁",
    "tertiary": "次要文字操作",
    "disabled": "停用操作",
    "tabs": "已選分頁",
    "markdown_link": "有底線的本頁連結",
    "checkbox": "核取方塊標籤",
    "radio": "已選項",
    "toggle": "切換標籤",
    "slider": "滑桿標籤",
    "radio_horizontal": "已選項",
    "selectbox": "下拉選單標籤",
})

CASE_ROLES: Mapping[str, str] = MappingProxyType({
    "primary": "button",
    "form_submit": "button",
    "download": "button",
    "link_button": "link",
    "tertiary": "button",
    "disabled": "button",
    "tabs": "tab",
    "markdown_link": "link",
    "checkbox": "checkbox",
    "radio": "radio",
    "toggle": "checkbox",
    "slider": "slider",
    "radio_horizontal": "radio",
    "selectbox": "combobox",
})

CONTRACT_KEYS = frozenset({"selector", "property", "owners", "states", "important"})
CONTRACT_STATES = frozenset({
    "default",
    "hover",
    "active",
    "focus-visible",
    "disabled",
    "selected",
    "checked",
    "visited-static",
})
STATE_PSEUDOS: Mapping[str, str] = MappingProxyType({
    "hover": ":hover",
    "active": ":active",
    "focus-visible": ":focus-visible",
    "visited-static": ":visited",
})

READY_MARKER = "#ux1b-theme-ready"
OWNER_PREFIX = "ux1b_owner_"
CHANNEL_TOLERANCE = 3
ACTION_TIMEOUT_MS = 8_000
NAVIGATION_TIMEOUT_MS = 30_000
MAX_DIAGNOSTIC_MESSAGE_CHARS = 1_024
MAX_DIAGNOSTIC_TYPE_CHARS = 128
_DIAGNOSTIC_INPUT_CHARS = MAX_DIAGNOSTIC_MESSAGE_CHARS * 4
_RUNTIME_CLEANUP_ATTEMPTS = 3
_TERMINAL_SIGNALS = (signal.SIGINT, signal.SIGTERM)

_CHILD_ENV_KEYS = frozenset({
    "COMSPEC",
    "LANG",
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
})
_CHILD_GUARD_PATH = "QUANT_RADAR_UX1B_THEME_GUARD_PATH"
_CHILD_STREAMLIT_PORT = "QUANT_RADAR_UX1B_THEME_STREAMLIT_PORT"
_CHILD_DENY_PROXY_PORT = "QUANT_RADAR_UX1B_THEME_DENY_PROXY_PORT"
_CREDENTIAL_ENV_RE = re.compile(
    r"(?i)(?:api[_-]?key|token|secret|password|"
    r"credential|cookie|authorization|database[_-]?url|dsn)"
)
_CREDENTIAL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{6,}"),
        "Bearer <redacted>",
    ),
    (
        re.compile(r"(?i)\b(?:sk|xox[baprs]|gh[pousr])-[a-z0-9_-]{6,}\b"),
        "<redacted-credential>",
    ),
    (
        re.compile(r"\beyJ[a-zA-Z0-9_-]{6,}\.[a-zA-Z0-9_-]{6,}\.[a-zA-Z0-9_-]{6,}\b"),
        "<redacted-credential>",
    ),
)
_CREDENTIAL_ASSIGNMENT_RE = re.compile(
    r"(?i)\b([a-z0-9_]*(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|secret|password|credential|cookie|authorization|database[_-]?url|dsn))\b"
    r"(\s*[\"']?\s*[:=]\s*[\"']?)([^\"'\s,;}]+)"
)
_URI_USERINFO_RE = re.compile(
    r"(?i)\b([a-z][a-z0-9+.-]*://)([^/@\s]+(?::[^/@\s]*)?)@"
)
_ABSOLUTE_PATH_RE = re.compile(
    r"(?i)(?:"
    r"(?<![a-z0-9:/])/(?:[^/\s,;]+/)+[^/\s,;]+|"
    r"(?<![a-z0-9])~[/\\][^\s,;]+|"
    r"(?<![a-z0-9])[a-z]:[\\/][^\s,;]+|"
    r"\\\\[^\\\s,;]+\\[^\s,;]+"
    r")"
)
_THEME_FIXED_CHILD_KEYS = frozenset({
    "HOME", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
    "TMPDIR", "TMP", "TEMP", "NO_PROXY", "no_proxy", "PYTHONPATH",
    "PYTHONUNBUFFERED", "STREAMLIT_BROWSER_GATHER_USAGE_STATS", "TZ",
    _CHILD_GUARD_PATH, _CHILD_STREAMLIT_PORT, _CHILD_DENY_PROXY_PORT,
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
    "http_proxy", "https_proxy", "all_proxy",
})

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_RGB_RE = re.compile(
    r"^rgba?\(\s*([0-9]{1,3})\s*,\s*([0-9]{1,3})\s*,\s*([0-9]{1,3})"
    r"(?:\s*,\s*(0(?:\.\d+)?|1(?:\.0+)?))?\s*\)$"
)
_DECLARATION_NAME_RE = re.compile(r"^(?:--)?[a-zA-Z_][a-zA-Z0-9_-]*$")
_GENERATED_CLASS_RE = re.compile(r"\.(?:st-emotion-cache|css)-[A-Za-z0-9_-]+")
_CAPTURE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,95}$")
_RETAINED_FAILED_THEME_RUNTIMES: list[Any] = []


class ThemeContractError(ValueError):
    """Raised whenever evidence cannot prove the complete theme contract."""


class DependencyUnavailable(RuntimeError):
    """Raised when mandatory local browser tooling is unavailable."""


class ServerExited(RuntimeError):
    """Raised when the owned gallery child exits before becoming healthy."""


class ThemeChildNetworkDenied(PermissionError):
    """Raised in the fixture child before an unowned destination is contacted."""


class RunnerInterrupted(KeyboardInterrupt):
    """The theme runner received an interrupt while it owned resources."""


class _RunnerFinalizationGrant:
    """Opaque, process-local authority for one terminal success transition."""

    __slots__ = ()

    def __new__(cls, *_args: Any, **_kwargs: Any) -> "_RunnerFinalizationGrant":
        raise TypeError("runner finalization grants cannot be constructed directly")

    def __copy__(self) -> "_RunnerFinalizationGrant":
        raise TypeError("runner finalization grants cannot be copied")

    def __deepcopy__(self, _memo: dict[int, Any]) -> "_RunnerFinalizationGrant":
        raise TypeError("runner finalization grants cannot be deep-copied")

    def __reduce__(self) -> Any:
        raise TypeError("runner finalization grants cannot be serialized")


class _RunSuccessAuthority:
    """Opaque authority registered only by one live ``run_matrix`` call."""

    __slots__ = ()

    def __new__(cls, *_args: Any, **_kwargs: Any) -> "_RunSuccessAuthority":
        raise TypeError("run success authorities cannot be constructed directly")

    def __copy__(self) -> "_RunSuccessAuthority":
        raise TypeError("run success authorities cannot be copied")

    def __deepcopy__(self, _memo: dict[int, Any]) -> "_RunSuccessAuthority":
        raise TypeError("run success authorities cannot be deep-copied")

    def __reduce__(self) -> Any:
        raise TypeError("run success authorities cannot be serialized")


_FINALIZATION_GRANTS_LOCK = threading.Lock()
_FINALIZATION_GRANTS: dict[
    int,
    tuple[
        _RunnerFinalizationGrant,
        _RunSuccessAuthority,
        int,
        dict[str, Any],
        Any,
        tuple[Any, ...],
        str,
    ],
] = {}
_RUN_SUCCESS_AUTHORITIES: dict[
    int,
    tuple[
        _RunSuccessAuthority,
        int,
        dict[str, Any],
        Any,
        tuple[Any, ...],
    ],
] = {}


def _ensure_workspace_import_path() -> None:
    """Make package imports deterministic when this file runs outside the repo cwd."""

    workspace = os.fspath(WORKSPACE_ROOT)
    if workspace not in sys.path:
        sys.path.insert(0, workspace)


def _evidence_api() -> Any:
    """Load the recovery evidence API in package and direct-script modes."""

    _ensure_workspace_import_path()
    from scripts import ui_ux_evidence

    return ui_ux_evidence


def _isolation_api() -> Any:
    """Load the recovery isolation coordinator in either execution mode."""

    _ensure_workspace_import_path()
    from scripts import ui_ux_isolation

    return ui_ux_isolation


def _snapshot_api() -> Any:
    """Load the authority runner that owns the accepted UX1B mirror policy."""

    _ensure_workspace_import_path()
    from scripts import ui_ux_snapshot_matrix

    return ui_ux_snapshot_matrix


def _expanded_ux1b_source_mirror_policy() -> tuple[str, ...]:
    """Use the exact file projection accepted by the shared UX1B runner."""

    snapshot = _snapshot_api()
    expanded = snapshot._expanded_ux1b_source_mirror_policy()
    if not isinstance(expanded, tuple) or not expanded:
        raise ThemeContractError("accepted UX1B source-mirror projection is invalid")
    return expanded


def build_browser_worker_command(*args: Any, **kwargs: Any) -> Any:
    """Expose the bounded external-worker command seam for Task 5."""

    normalized_args = list(args)
    normalized_kwargs = dict(kwargs)
    if len(normalized_args) >= 2 and Path(
        os.fspath(normalized_args[1])
    ) == BROWSER_WORKER_PATH:
        normalized_args[1] = "scripts/ui_ux_browser_worker.py"
    if "worker_path" in normalized_kwargs and Path(
        os.fspath(normalized_kwargs["worker_path"])
    ) == BROWSER_WORKER_PATH:
        normalized_kwargs["worker_path"] = "scripts/ui_ux_browser_worker.py"
    return _evidence_api().build_browser_worker_command(
        *normalized_args, **normalized_kwargs
    )


def capture_stack_digest(*args: Any, **kwargs: Any) -> Any:
    """Expose the frozen capture-stack digest seam for Task 5."""

    return _evidence_api().capture_stack_digest(*args, **kwargs)


def build_app_sandbox_profile(*args: Any, **kwargs: Any) -> Any:
    """Expose the app-profile builder without changing the legacy launch path."""

    _ensure_workspace_import_path()
    from scripts import ui_ux_isolation

    return ui_ux_isolation.build_app_sandbox_profile(*args, **kwargs)


def build_browser_sandbox_profile(*args: Any, **kwargs: Any) -> Any:
    """Expose the browser-profile builder without changing the legacy launch path."""

    _ensure_workspace_import_path()
    from scripts import ui_ux_isolation

    return ui_ux_isolation.build_browser_sandbox_profile(*args, **kwargs)


@dataclass(frozen=True, slots=True)
class CssRule:
    selector: str
    declarations: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class SelectorContractRecord:
    selector: str
    property: str
    owners: tuple[str, ...]
    states: tuple[str, ...]
    important: bool


@dataclass(frozen=True, slots=True)
class FocusSideSample:
    gap: tuple[int, int, int] | None
    ring: tuple[int, int, int]
    outer: tuple[int, int, int]
    clipped: bool


@dataclass(frozen=True, slots=True)
class OwnedThemeRun:
    run_dir: Path
    manifest_path: Path
    log_path: Path
    owner_path: Path
    run_id: str


@dataclass(slots=True)
class OwnedThemeServer:
    port: int
    process: subprocess.Popen[bytes]
    deny_proxy: Any
    guard_path: Path
    child_environment: Mapping[str, str]
    sandbox_calibration: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ThemeNetworkContract:
    streamlit_port: int
    deny_proxy_port: int


@dataclass(frozen=True, slots=True)
class ThemeBrowserWorkerSession:
    session_id: str
    source_root: Path
    browser_root: Path
    mirror_digest: str
    contract: Any
    profiles: Any
    calibration: Mapping[str, Any]
    environment: Mapping[str, str]


@dataclass(slots=True)
class ThemeOutputNamespace:
    path: Path
    leaf_name: str
    workspace_fd: int
    workspace_contract: tuple[str, int, int, int, int]
    ux1b_fd: int
    parent_fd: int
    parent_components: tuple[str, ...]
    base_contracts: tuple[tuple[str, int, int, int, int], ...]
    parent_contracts: tuple[tuple[str, int, int, int, int], ...]
    closed: bool = False

    def close(self) -> BaseException | None:
        if self.closed:
            return None
        self.closed = True
        first: BaseException | None = None
        for descriptor in (self.parent_fd, self.ux1b_fd, self.workspace_fd):
            try:
                os.close(descriptor)
            except BaseException as exc:
                first = first or exc
        return first


@dataclass(slots=True)
class ThemeFormalRuntime:
    namespace: ThemeOutputNamespace
    runtime: Any
    lease: Any
    final_root: Path
    app_root: Path
    browser_root: Path
    final_root_fd: int
    browser_root_fd: int
    lifecycle: Any


@dataclass(frozen=True, slots=True)
class ThemeStagedCapture:
    capture_id: str
    png_path: str
    raw_sidecar: Any
    raw_document: Mapping[str, Any]
    rich_evidence: Mapping[str, Any]
    browser_proof: Any


def _sanitize_diagnostic_text(value: Any, owned: OwnedThemeRun) -> str:
    text = str(value)[:_DIAGNOSTIC_INPUT_CHARS]
    replacements = (
        (str(owned.run_dir.resolve()), "<run-dir>"),
        (str(owned.run_dir), "<run-dir>"),
        (str(ROOT.resolve()), "<workspace>"),
        (str(ROOT), "<workspace>"),
    )
    for original, replacement in replacements:
        text = text.replace(original, replacement)
    for pattern, replacement in _CREDENTIAL_PATTERNS:
        text = pattern.sub(replacement, text)
    text = _URI_USERINFO_RE.sub(r"\1<redacted>@", text)
    text = _CREDENTIAL_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group(1)}{match.group(2)}<redacted>", text
    )
    text = _ABSOLUTE_PATH_RE.sub("<absolute-path>", text)
    return text[:MAX_DIAGNOSTIC_MESSAGE_CHARS]


def _terminal_diagnostic(
    exc: BaseException, owned: OwnedThemeRun
) -> dict[str, str]:
    sanitized_type = _sanitize_diagnostic_text(type(exc).__name__, owned)[
        :MAX_DIAGNOSTIC_TYPE_CHARS
    ]
    return {
        "type": sanitized_type or "Exception",
        "message": _sanitize_diagnostic_text(exc, owned),
    }


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def rgb(value: str) -> tuple[int, int, int]:
    parsed = parse_css_color(value)
    if parsed[3] != 1.0:
        raise ThemeContractError("opaque RGB value required")
    return parsed[:3]


def parse_css_color(value: str) -> tuple[int, int, int, float]:
    if not isinstance(value, str):
        raise ThemeContractError("CSS color must be a string")
    candidate = value.strip()
    if _HEX_RE.fullmatch(candidate):
        return (
            int(candidate[1:3], 16),
            int(candidate[3:5], 16),
            int(candidate[5:7], 16),
            1.0,
        )
    match = _RGB_RE.fullmatch(candidate)
    if match is None:
        raise ThemeContractError(f"unsupported or unresolved CSS color: {candidate!r}")
    channels = tuple(int(match.group(index)) for index in (1, 2, 3))
    if any(channel > 255 for channel in channels):
        raise ThemeContractError("CSS color channel is outside 0..255")
    alpha = 1.0 if match.group(4) is None else float(match.group(4))
    if not math.isfinite(alpha) or not 0.0 <= alpha <= 1.0:
        raise ThemeContractError("CSS alpha is outside 0..1")
    return channels[0], channels[1], channels[2], alpha


def composite_rgba(
    foreground: tuple[int, int, int, float],
    background: tuple[int, int, int, float],
) -> tuple[int, int, int, float]:
    if background[3] != 1.0:
        raise ThemeContractError("background must already be fully composited")
    alpha = foreground[3]
    channels = tuple(
        round(alpha * foreground[index] + (1.0 - alpha) * background[index])
        for index in range(3)
    )
    return channels[0], channels[1], channels[2], 1.0


def _linear(channel: int) -> float:
    normalized = channel / 255.0
    return (
        normalized / 12.92
        if normalized <= 0.04045
        else ((normalized + 0.055) / 1.055) ** 2.4
    )


def relative_luminance(value: str | tuple[int, int, int]) -> float:
    channels = rgb(value) if isinstance(value, str) else value
    return 0.2126 * _linear(channels[0]) + 0.7152 * _linear(channels[1]) + 0.0722 * _linear(channels[2])


def contrast_ratio(
    foreground: str | tuple[int, int, int],
    background: str | tuple[int, int, int],
) -> float:
    first = relative_luminance(foreground)
    second = relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def validate_palette_contract(
    tokens: Mapping[str, str], surfaces: Mapping[str, str]
) -> None:
    if dict(tokens) != dict(APPROVED_TOKENS):
        raise ThemeContractError("interaction token set differs from the approved palette")
    if dict(surfaces) != dict(SURFACE_COLORS):
        raise ThemeContractError("surface token projection differs from UX-1A")
    for role in ("interactive.primary", "interactive.hover", "interactive.active"):
        if contrast_ratio(tokens["text.on-primary"], tokens[role]) < 4.5:
            raise ThemeContractError(f"white text contrast failed on {role}")
    for surface_name, surface in surfaces.items():
        if contrast_ratio(tokens["interactive.accent"], surface) < 4.5:
            raise ThemeContractError(f"accent text failed on {surface_name}")
        if contrast_ratio(tokens["interactive.control"], surface) < 3.0:
            raise ThemeContractError(f"control graphic failed on {surface_name}")
        if contrast_ratio(tokens["border.focus"], surface) < 3.0:
            raise ThemeContractError(f"focus ring failed on {surface_name}")
    if contrast_ratio(tokens["text.on-primary"], tokens["interactive.control"]) < 3.0:
        raise ThemeContractError("white control mark failed on control fill")
    if contrast_ratio(tokens["border.focus"], tokens["interactive.control"]) >= 3.0:
        raise ThemeContractError("focus/control negative no longer proves the required gap")
    if any(value.casefold() in {"#ef4444", "#ef553b"} for value in tokens.values()):
        raise ThemeContractError("danger red entered the interaction token family")


def validate_design_token_contract(design: Any) -> None:
    color_tokens = getattr(design, "COLOR_TOKENS", None)
    if not isinstance(color_tokens, Mapping):
        raise ThemeContractError("production COLOR_TOKENS mapping is unavailable")
    expected = {
        **dict(APPROVED_TOKENS),
        **{f"surface.{name}": value for name, value in SURFACE_COLORS.items()},
        "signal.avoid": "#ef4444",
        "signal.bearish": "#ef553b",
        "feedback.error": "#ef553b",
    }
    for role, value in expected.items():
        actual = color_tokens.get(role)
        if not isinstance(actual, str) or actual.casefold() != value:
            raise ThemeContractError(
                f"production token differs: {role}={actual!r}, expected {value!r}"
            )


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def extract_theme_css(builder_output: Any) -> str:
    """Require the trusted builder to return exactly one static style element."""

    if not isinstance(builder_output, str):
        raise ThemeContractError("theme CSS builder must return a string")
    match = re.fullmatch(r"\s*<style>\s*(.*?)\s*</style>\s*", builder_output, re.DOTALL)
    if (
        match is None
        or not match.group(1).strip()
        or "<" in match.group(1)
    ):
        raise ThemeContractError("theme CSS builder must return exactly one non-empty <style>")
    return match.group(1).strip()


def _split_css_list(value: str, delimiter: str = ",") -> tuple[str, ...]:
    """Split a CSS list without breaking :where(...), attributes, or quotes."""

    parts: list[str] = []
    start = 0
    round_depth = 0
    square_depth = 0
    quote: str | None = None
    escaped = False
    for index, character in enumerate(value):
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if quote is not None:
            if character == quote:
                quote = None
            continue
        if character in {"'", '"'}:
            quote = character
        elif character == "(":
            round_depth += 1
        elif character == ")":
            round_depth -= 1
        elif character == "[":
            square_depth += 1
        elif character == "]":
            square_depth -= 1
        elif character == delimiter and round_depth == 0 and square_depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
        if round_depth < 0 or square_depth < 0:
            raise ThemeContractError("CSS selector has unbalanced delimiters")
    if quote is not None or round_depth or square_depth or escaped:
        raise ThemeContractError("CSS selector has an unterminated quote or delimiter")
    parts.append(value[start:].strip())
    if any(not part for part in parts):
        raise ThemeContractError("CSS selector list contains an empty selector")
    return tuple(parts)


def parse_css_rules(css: str) -> tuple[CssRule, ...]:
    if not isinstance(css, str) or not css.strip():
        raise ThemeContractError("theme CSS must be a non-empty static string")
    source = _strip_comments(css)
    if "@" in source:
        raise ThemeContractError("at-rules are outside the fixed theme contract")
    matches = list(re.finditer(r"([^{}]+)\{([^{}]*)\}", source, flags=re.DOTALL))
    residue = source
    for match in reversed(matches):
        residue = residue[:match.start()] + residue[match.end():]
    if residue.strip() or not matches:
        raise ThemeContractError("CSS contains nested, unparsed, or missing rules")

    rules: list[CssRule] = []
    for match in matches:
        selector_text, declaration_text = match.groups()
        declarations: dict[str, str] = {}
        for raw in declaration_text.split(";"):
            if not raw.strip():
                continue
            if ":" not in raw:
                raise ThemeContractError("CSS declaration is missing a colon")
            name, value = (part.strip() for part in raw.split(":", 1))
            if _DECLARATION_NAME_RE.fullmatch(name) is None or not value:
                raise ThemeContractError("CSS declaration is not fixed and parseable")
            if name in declarations:
                raise ThemeContractError(f"duplicate CSS property: {name}")
            declarations[name] = value
        if not declarations:
            raise ThemeContractError("CSS rule has no declarations")
        for selector in _split_css_list(selector_text):
            rules.append(CssRule(selector, MappingProxyType(dict(declarations))))
    return tuple(rules)


def validate_css_safety(css: str) -> tuple[CssRule, ...]:
    lowered = css.casefold()
    for forbidden in ("url(", "expression(", "javascript:", "@import", "<script"):
        if forbidden in lowered:
            raise ThemeContractError(f"forbidden CSS input: {forbidden}")
    if _GENERATED_CLASS_RE.search(css):
        raise ThemeContractError("generated Streamlit/emotion class is forbidden")
    rules = parse_css_rules(css)
    for rule in rules:
        selector = rule.selector.strip()
        base = re.sub(r":(?:link|visited|hover|active|focus|focus-visible)$", "", selector).strip()
        if base in {"*", "a", "button", "svg", "input", "body", "html", ":root"}:
            raise ThemeContractError(f"broad global selector is forbidden: {selector}")
        if not any(
            marker in selector
            for marker in ("[data-testid=", "[kind=", "[role=", "[aria-", ".st-key-")
        ):
            raise ThemeContractError(f"selector has no stable component scope: {selector}")
    return rules


def _decoration_is_underlined(declarations: Mapping[str, str]) -> bool:
    return "underline" in declarations.get("text-decoration", "").casefold() or "underline" in declarations.get("text-decoration-line", "").casefold()


def _declaration_core(value: str) -> str:
    return re.sub(r"\s*!important\s*$", "", value, flags=re.IGNORECASE).strip()


def validate_link_contract(css: str) -> None:
    rules = validate_css_safety(css)
    link_rules: dict[str, dict[str, str]] = {}
    visited_rules: dict[str, dict[str, str]] = {}
    for rule in rules:
        if rule.selector.endswith(":link"):
            bucket = link_rules.setdefault(rule.selector[:-5].strip(), {})
            if set(bucket) & set(rule.declarations):
                raise ThemeContractError("duplicate :link property declaration")
            bucket.update(rule.declarations)
        elif rule.selector.endswith(":visited"):
            bucket = visited_rules.setdefault(rule.selector[:-8].strip(), {})
            if set(bucket) & set(rule.declarations):
                raise ThemeContractError("duplicate :visited property declaration")
            bucket.update(rule.declarations)
    if not link_rules or set(link_rules) != set(visited_rules):
        raise ThemeContractError(":link and :visited selector bases must be equal and non-empty")
    for selector in sorted(link_rules):
        link = link_rules[selector]
        visited = visited_rules[selector]
        if _declaration_core(link.get("color", "")).casefold() != APPROVED_TOKENS["interactive.accent"]:
            raise ThemeContractError(":link must use the fixed accent token")
        if _declaration_core(visited.get("color", "")).casefold() != APPROVED_TOKENS["interactive.accent"]:
            raise ThemeContractError(":visited must use the same fixed accent token")
        if not _decoration_is_underlined(link) or not _decoration_is_underlined(visited):
            raise ThemeContractError(":link and :visited must both retain underline")


def validate_important_allowlist(
    css: str, allowed: set[tuple[str, str]]
) -> None:
    actual: set[tuple[str, str]] = set()
    for rule in parse_css_rules(css):
        for property_name, value in rule.declarations.items():
            if "!important" in value.casefold():
                if not value.casefold().endswith("!important"):
                    raise ThemeContractError("!important must terminate its declaration")
                actual.add((rule.selector, property_name))
    if actual != set(allowed):
        raise ThemeContractError(
            f"!important contract differs: actual={sorted(actual)!r} expected={sorted(allowed)!r}"
        )


def _parse_owner_id(owner: str) -> tuple[str, str]:
    if not isinstance(owner, str) or not owner.startswith(OWNER_PREFIX):
        raise ThemeContractError(f"invalid theme owner id: {owner!r}")
    remainder = owner[len(OWNER_PREFIX):]
    for surface in SURFACE_COLORS:
        prefix = f"{surface}_"
        if remainder.startswith(prefix):
            case = remainder[len(prefix):]
            if case not in REQUIRED_GALLERY_CASES:
                break
            return surface, case
    raise ThemeContractError(f"unknown theme owner id: {owner!r}")


def owner_id(surface: str, case: str) -> str:
    if surface not in SURFACE_COLORS or case not in REQUIRED_GALLERY_CASES:
        raise ThemeContractError("owner id requested outside the frozen gallery")
    return f"{OWNER_PREFIX}{surface}_{case}"


def validate_selector_contract(
    css: str, raw_contract: Any
) -> tuple[SelectorContractRecord, ...]:
    """Freeze every CSS selector/property and its exact gallery ownership."""

    if not isinstance(raw_contract, (tuple, list)) or not raw_contract:
        raise ThemeContractError("THEME_SELECTOR_CONTRACT must be a non-empty tuple/list")
    parsed_rules = parse_css_rules(css)
    actual_pairs: dict[tuple[str, str], bool] = {}
    for rule in parsed_rules:
        for property_name, value in rule.declarations.items():
            pair = (rule.selector, property_name)
            if pair in actual_pairs:
                raise ThemeContractError(f"duplicate selector/property declaration: {pair!r}")
            actual_pairs[pair] = "!important" in value.casefold()

    normalized: list[SelectorContractRecord] = []
    contract_pairs: dict[tuple[str, str], SelectorContractRecord] = {}
    selector_metadata: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
    for index, raw in enumerate(raw_contract):
        if not isinstance(raw, Mapping) or set(raw) != set(CONTRACT_KEYS):
            raise ThemeContractError(
                f"selector contract record {index} must have exact keys {sorted(CONTRACT_KEYS)!r}"
            )
        selector = raw["selector"]
        property_name = raw["property"]
        owners_value = raw["owners"]
        states_value = raw["states"]
        important = raw["important"]
        if not isinstance(selector, str) or not selector.strip() or selector != selector.strip():
            raise ThemeContractError(f"selector contract record {index} has an invalid selector")
        if (
            not isinstance(property_name, str)
            or _DECLARATION_NAME_RE.fullmatch(property_name) is None
        ):
            raise ThemeContractError(f"selector contract record {index} has an invalid property")
        if not isinstance(owners_value, (tuple, list)) or not owners_value:
            raise ThemeContractError(f"selector contract record {index} has no owners")
        if not isinstance(states_value, (tuple, list)) or not states_value:
            raise ThemeContractError(f"selector contract record {index} has no states")
        if not isinstance(important, bool):
            raise ThemeContractError(f"selector contract record {index} important must be bool")
        if any(not isinstance(value, str) for value in (*owners_value, *states_value)):
            raise ThemeContractError(f"selector contract record {index} contains non-string values")

        owners = tuple(sorted(owners_value))
        states = tuple(sorted(states_value))
        if len(set(owners)) != len(owners):
            raise ThemeContractError("selector contract owners must be unique")
        if len(set(states)) != len(states):
            raise ThemeContractError("selector contract states must be unique")
        if not set(states) <= CONTRACT_STATES:
            raise ThemeContractError(f"selector contract has unknown states: {states!r}")
        owner_parts = tuple(_parse_owner_id(value) for value in owners)
        if any(case == "signals" for _, case in owner_parts):
            raise ThemeContractError("interaction selectors may not own danger/signal fixtures")
        owned_cases = {case for _, case in owner_parts}
        for case in owned_cases:
            case_surfaces = {surface for surface, item in owner_parts if item == case}
            if case_surfaces != set(SURFACE_COLORS):
                raise ThemeContractError(
                    f"selector contract must own every surface for case {case!r}"
                )
        for state, pseudo in STATE_PSEUDOS.items():
            contains = pseudo in selector
            declared = state in states
            if contains != declared:
                raise ThemeContractError(
                    f"selector/state mismatch for {selector!r}: {state!r}"
                )

        record = SelectorContractRecord(selector, property_name, owners, states, important)
        pair = (selector, property_name)
        if pair in contract_pairs:
            raise ThemeContractError(f"duplicate selector contract record: {pair!r}")
        contract_pairs[pair] = record
        metadata = (owners, states)
        if selector in selector_metadata and selector_metadata[selector] != metadata:
            raise ThemeContractError(
                f"selector contract metadata differs across properties: {selector!r}"
            )
        selector_metadata[selector] = metadata
        normalized.append(record)

    if set(actual_pairs) != set(contract_pairs):
        missing = sorted(set(actual_pairs) - set(contract_pairs))
        extra = sorted(set(contract_pairs) - set(actual_pairs))
        raise ThemeContractError(
            f"selector/property contract differs: missing={missing!r} extra={extra!r}"
        )
    for pair, record in contract_pairs.items():
        if actual_pairs[pair] != record.important:
            raise ThemeContractError(f"!important boolean differs for {pair!r}")

    allowed_important = {
        (record.selector, record.property) for record in normalized if record.important
    }
    validate_important_allowlist(css, allowed_important)
    return tuple(sorted(normalized, key=lambda record: (record.selector, record.property)))


def selector_owner_contract(
    records: Sequence[SelectorContractRecord],
) -> Mapping[str, tuple[str, ...]]:
    owners: dict[str, tuple[str, ...]] = {}
    for record in records:
        existing = owners.setdefault(record.selector, record.owners)
        if existing != record.owners:
            raise ThemeContractError("selector owner metadata is internally inconsistent")
    return MappingProxyType(owners)


def require_exact_owner_sets(
    actual: Mapping[str, Iterable[str]], expected: Mapping[str, Iterable[str]]
) -> None:
    actual_normalized = {key: frozenset(values) for key, values in actual.items()}
    expected_normalized = {key: frozenset(values) for key, values in expected.items()}
    if actual_normalized != expected_normalized:
        raise ThemeContractError(
            "selector owner sets differ: "
            f"actual={actual_normalized!r} expected={expected_normalized!r}"
        )


def _near(first: tuple[int, int, int], second: tuple[int, int, int], tolerance: int) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(first, second))


def validate_focus_adjacency(
    *,
    samples: Mapping[str, FocusSideSample],
    component_color: tuple[int, int, int],
    expected_surface: tuple[int, int, int],
    expected_ring: tuple[int, int, int],
    channel_tolerance: int = 3,
) -> None:
    if set(samples) != set(FOCUS_SIDES):
        raise ThemeContractError("focus samples must cover all four sides exactly")
    for side in FOCUS_SIDES:
        sample = samples[side]
        if sample.clipped:
            raise ThemeContractError(f"focus indicator is clipped on {side}")
        if not _near(sample.ring, expected_ring, channel_tolerance):
            raise ThemeContractError(f"focus ring pixel differs on {side}")
        if sample.gap is None:
            if contrast_ratio(sample.ring, component_color) < 3.0:
                raise ThemeContractError(
                    f"focus ring directly touches low-contrast component on {side}"
                )
        else:
            if not _near(sample.gap, expected_surface, channel_tolerance):
                raise ThemeContractError(f"focus gap is not the composited surface on {side}")
            if contrast_ratio(sample.ring, sample.gap) < 3.0:
                raise ThemeContractError(f"focus ring/gap contrast failed on {side}")
        if not _near(sample.outer, expected_surface, channel_tolerance):
            raise ThemeContractError(f"focus outer adjacency is not the surface on {side}")
        if contrast_ratio(sample.ring, sample.outer) < 3.0:
            raise ThemeContractError(f"focus ring/outer contrast failed on {side}")


def safe_relative_output(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError as exc:
        raise ThemeContractError("evidence path escaped the repository") from exc


def is_allowed_browser_url(url: str, port: int) -> bool:
    try:
        parsed = urllib.parse.urlsplit(url)
        if parsed.username is not None or parsed.password is not None:
            return False
        if parsed.scheme in {"data", "blob", "about"}:
            return parsed.scheme != "blob" or parsed.path.startswith(
                f"http://127.0.0.1:{port}/"
            )
        if parsed.scheme not in {"http", "ws"}:
            return False
        return parsed.hostname == "127.0.0.1" and parsed.port == port
    except (TypeError, ValueError):
        return False


def safe_url_label(url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(url)
    except (TypeError, ValueError):
        return "invalid-url"
    host = (parsed.hostname or "").casefold()
    port = f":{parsed.port}" if parsed.port is not None else ""
    path = parsed.path if parsed.path.startswith("/") else "/"
    return f"{parsed.scheme.casefold()}://{host}{port}{path}"


def source_digest() -> str:
    paths = (
        ROOT / ".streamlit" / "config.toml",
        ROOT / "ui" / "_design.py",
        FIXTURE_APP,
        ROOT / "scripts" / "ui_ux_snapshot_matrix.py",
        Path(__file__).resolve(),
    )
    rows = []
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        payload = path.read_bytes()
        rows.append(
            f"{relative}\0{hashlib.sha256(payload).hexdigest()}\0{len(payload)}\n"
        )
    return hashlib.sha256("".join(sorted(rows)).encode("utf-8")).hexdigest()


def _browser_rgb(value: str) -> str:
    red, green, blue = rgb(value)
    return f"rgb({red}, {green}, {blue})"


def _composite_color(
    value: str,
    background: tuple[int, int, int, float],
    *,
    opacity: float = 1.0,
) -> tuple[int, int, int, float]:
    parsed = parse_css_color(value)
    effective = (parsed[0], parsed[1], parsed[2], parsed[3] * opacity)
    return composite_rgba(effective, background)


def _resolved_background(
    snapshot: Mapping[str, Any], surface: str
) -> tuple[int, int, int, float]:
    background = parse_css_color(SURFACE_COLORS[surface])
    target_rect = snapshot.get("rect")
    center: tuple[float, float] | None = None
    if isinstance(target_rect, Mapping):
        try:
            center = (
                (float(target_rect["left"]) + float(target_rect["right"])) / 2.0,
                (float(target_rect["top"]) + float(target_rect["bottom"])) / 2.0,
            )
        except (KeyError, TypeError, ValueError):
            center = None
    for layer in snapshot.get("backgroundLayers", ()):
        if not isinstance(layer, Mapping):
            raise ThemeContractError("computed background layer is malformed")
        layer_rect = layer.get("rect")
        if center is not None and isinstance(layer_rect, Mapping):
            try:
                covers_center = (
                    float(layer_rect["left"]) <= center[0] <= float(layer_rect["right"])
                    and float(layer_rect["top"]) <= center[1] <= float(layer_rect["bottom"])
                )
            except (KeyError, TypeError, ValueError):
                raise ThemeContractError("computed background layer rect is malformed")
            if not covers_center:
                continue
        opacity = float(layer.get("opacity", 1.0))
        if not math.isfinite(opacity) or not 0.0 <= opacity <= 1.0:
            raise ThemeContractError("computed element opacity is invalid")
        background = _composite_color(str(layer.get("color", "")), background, opacity=opacity)
    return background


def _resolved_foreground(
    snapshot: Mapping[str, Any], background: tuple[int, int, int, float]
) -> tuple[int, int, int, float]:
    opacity = float(snapshot.get("effectiveOpacity", 1.0))
    if not math.isfinite(opacity) or not 0.0 <= opacity <= 1.0:
        raise ThemeContractError("computed foreground opacity is invalid")
    return _composite_color(str(snapshot.get("color", "")), background, opacity=opacity)


def _exact_computed_color(actual: str, expected: str, label: str) -> None:
    parsed = parse_css_color(actual)
    if parsed[3] != 1.0 or parsed[:3] != rgb(expected):
        raise ThemeContractError(
            f"{label} differs: actual={actual!r} expected={expected!r}"
        )


def _text_contrast(snapshot: Mapping[str, Any], surface: str) -> float:
    background = _resolved_background(snapshot, surface)
    foreground = _resolved_foreground(snapshot, background)
    return contrast_ratio(foreground[:3], background[:3])


def _snapshot_for_manifest(snapshot: Mapping[str, Any], surface: str) -> dict[str, Any]:
    background = _resolved_background(snapshot, surface)
    foreground = _resolved_foreground(snapshot, background)
    return {
        "color": snapshot["color"],
        "backgroundColor": snapshot["backgroundColor"],
        "borderColors": snapshot["borderColors"],
        "borderWidths": snapshot["borderWidths"],
        "outlineColor": snapshot["outlineColor"],
        "outlineWidth": snapshot["outlineWidth"],
        "outlineOffset": snapshot["outlineOffset"],
        "textDecorationLine": snapshot["textDecorationLine"],
        "textDecorationThickness": snapshot["textDecorationThickness"],
        "opacity": snapshot["effectiveOpacity"],
        "resolvedForeground": list(foreground[:3]),
        "resolvedBackground": list(background[:3]),
        "textContrast": round(contrast_ratio(foreground[:3], background[:3]), 3),
        "rect": snapshot["rect"],
    }


_STYLE_SNAPSHOT_JS = """
(element) => {
  const surface = element.closest(
    '.st-key-ux1b_surface_canvas, .st-key-ux1b_surface_panel, .st-key-ux1b_surface_elevated'
  );
  if (!surface) throw new Error('element has no owned surface');
  const chain = [];
  let opacity = 1;
  for (let node = element; node && node !== surface; node = node.parentElement) {
    const style = getComputedStyle(node);
    const layerRect = node.getBoundingClientRect();
    const currentOpacity = Number.parseFloat(style.opacity);
    const normalizedOpacity = Number.isFinite(currentOpacity) ? currentOpacity : 1;
    opacity *= normalizedOpacity;
    chain.push({color: style.backgroundColor, opacity: normalizedOpacity,
      rect: {top: layerRect.top, right: layerRect.right, bottom: layerRect.bottom,
        left: layerRect.left}});
  }
  chain.reverse();
  const style = getComputedStyle(element);
  const rect = element.getBoundingClientRect();
  return {
    tag: element.tagName.toLowerCase(),
    color: style.color,
    backgroundColor: style.backgroundColor,
    backgroundLayers: chain,
    borderColors: [style.borderTopColor, style.borderRightColor,
      style.borderBottomColor, style.borderLeftColor],
    borderWidths: [style.borderTopWidth, style.borderRightWidth,
      style.borderBottomWidth, style.borderLeftWidth],
    outlineColor: style.outlineColor,
    outlineStyle: style.outlineStyle,
    outlineWidth: style.outlineWidth,
    outlineOffset: style.outlineOffset,
    boxShadow: style.boxShadow,
    textDecorationLine: style.textDecorationLine,
    textDecorationThickness: style.textDecorationThickness,
    fill: style.fill,
    stroke: style.stroke,
    effectiveOpacity: opacity,
    disabled: Boolean(element.disabled),
    ariaDisabled: element.getAttribute('aria-disabled'),
    ariaSelected: element.getAttribute('aria-selected'),
    ariaChecked: element.getAttribute('aria-checked'),
    ariaValueNow: element.getAttribute('aria-valuenow'),
    value: 'value' in element ? String(element.value) : null,
    checked: 'checked' in element ? Boolean(element.checked) : null,
    tabIndex: element.tabIndex,
    role: element.getAttribute('role'),
    rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height,
      top: rect.top, right: rect.right, bottom: rect.bottom, left: rect.left},
  };
}
"""


def _owner_locator(page: Any, surface: str, case: str) -> Any:
    locator = page.locator(f".st-key-{owner_id(surface, case)}")
    if locator.count() != 1:
        raise ThemeContractError(
            f"gallery owner must exist exactly once: {owner_id(surface, case)}"
        )
    return locator


def _case_locator(page: Any, surface: str, case: str) -> Any:
    if case not in CASE_ROLES:
        raise ThemeContractError(f"gallery case has no focusable semantic target: {case}")
    owner = _owner_locator(page, surface, case)
    locator = owner.get_by_role(
        CASE_ROLES[case], name=CASE_ACCESSIBLE_NAMES[case], exact=True
    )
    if locator.count() != 1:
        raise ThemeContractError(
            f"semantic target must exist exactly once: {surface}/{case}"
        )
    if not locator.is_visible():
        visible_proxy = case in {
            "checkbox", "radio", "radio_horizontal", "toggle"
        } and locator.evaluate(
            "input => { const proxy=input.previousElementSibling;"
            " if (!proxy || input.tagName !== 'INPUT') return false;"
            " const rect=proxy.getBoundingClientRect(), style=getComputedStyle(proxy);"
            " return rect.width > 0 && rect.height > 0 && style.display !== 'none'"
            "   && style.visibility !== 'hidden'; }"
        )
        if not visible_proxy:
            raise ThemeContractError(f"semantic target is not visible: {surface}/{case}")
    return locator


def _style_snapshot(locator: Any) -> Mapping[str, Any]:
    value = locator.evaluate(_STYLE_SNAPSHOT_JS)
    if not isinstance(value, Mapping):
        raise ThemeContractError("browser computed-style payload is malformed")
    return value


def _wait_for_color(page: Any, locator: Any, property_name: str, expected: str) -> None:
    handle = locator.element_handle()
    if handle is None:
        raise ThemeContractError("computed-style target detached")
    page.wait_for_function(
        "([element, propertyName, expected]) => "
        "getComputedStyle(element).getPropertyValue(propertyName).trim() === expected",
        arg=[handle, property_name, _browser_rgb(expected)],
        timeout=ACTION_TIMEOUT_MS,
    )


def _assert_rect_stable(
    before: Mapping[str, Any], after: Mapping[str, Any], label: str
) -> None:
    first = before["rect"]
    second = after["rect"]
    for key in ("x", "y", "width", "height"):
        if abs(float(first[key]) - float(second[key])) > 0.5:
            raise ThemeContractError(f"{label} caused layout shift in {key}")


def _validate_primary_snapshot(
    snapshot: Mapping[str, Any], surface: str, background_token: str, label: str
) -> dict[str, Any]:
    _exact_computed_color(snapshot["color"], APPROVED_TOKENS["text.on-primary"], f"{label} text")
    _exact_computed_color(snapshot["backgroundColor"], background_token, f"{label} fill")
    widths = tuple(float(str(value).removesuffix("px")) for value in snapshot["borderWidths"])
    if any(width < 1.0 for width in widths):
        raise ThemeContractError(f"{label} has no visible boundary on every side")
    for value in snapshot["borderColors"]:
        _exact_computed_color(value, APPROVED_TOKENS["interactive.control"], f"{label} border")
    text_ratio = _text_contrast(snapshot, surface)
    if text_ratio < 4.5:
        raise ThemeContractError(f"{label} text contrast failed: {text_ratio:.3f}")
    surface_rgb = rgb(SURFACE_COLORS[surface])
    for value in snapshot["borderColors"]:
        boundary = parse_css_color(value)
        composed = composite_rgba(boundary, (*surface_rgb, 1.0))
        if contrast_ratio(composed[:3], surface_rgb) < 3.0:
            raise ThemeContractError(f"{label} boundary contrast failed")
    return _snapshot_for_manifest(snapshot, surface)


def _primary_state_evidence(page: Any, surface: str, case: str) -> Mapping[str, Any]:
    locator = _case_locator(page, surface, case)
    locator.scroll_into_view_if_needed()
    _wait_for_color(page, locator, "background-color", APPROVED_TOKENS["interactive.primary"])
    default = _style_snapshot(locator)
    evidence: dict[str, Any] = {
        "default": _validate_primary_snapshot(
            default, surface, APPROVED_TOKENS["interactive.primary"], f"{surface}/{case}/default"
        )
    }

    locator.hover()
    _wait_for_color(page, locator, "background-color", APPROVED_TOKENS["interactive.hover"])
    hovered = _style_snapshot(locator)
    _assert_rect_stable(default, hovered, f"{surface}/{case}/hover")
    evidence["hover"] = _validate_primary_snapshot(
        hovered, surface, APPROVED_TOKENS["interactive.hover"], f"{surface}/{case}/hover"
    )

    page.mouse.down()
    try:
        _wait_for_color(page, locator, "background-color", APPROVED_TOKENS["interactive.active"])
        active = _style_snapshot(locator)
        _assert_rect_stable(default, active, f"{surface}/{case}/active")
        evidence["active"] = _validate_primary_snapshot(
            active, surface, APPROVED_TOKENS["interactive.active"], f"{surface}/{case}/active"
        )
    finally:
        try:
            page.mouse.move(0, 0)
        finally:
            page.mouse.up()
    return evidence


def _tertiary_state_evidence(page: Any, surface: str) -> Mapping[str, Any]:
    locator = _case_locator(page, surface, "tertiary")
    locator.scroll_into_view_if_needed()
    evidence: dict[str, Any] = {}
    baseline: Mapping[str, Any] | None = None
    for state in ("default", "hover", "active"):
        if state == "hover":
            locator.hover()
        elif state == "active":
            locator.hover()
            page.mouse.down()
        try:
            _wait_for_color(page, locator, "color", APPROVED_TOKENS["interactive.accent"])
            snapshot = _style_snapshot(locator)
            _exact_computed_color(
                snapshot["color"], APPROVED_TOKENS["interactive.accent"],
                f"{surface}/tertiary/{state}",
            )
            if _text_contrast(snapshot, surface) < 4.5:
                raise ThemeContractError(f"{surface}/tertiary/{state} text contrast failed")
            if baseline is None:
                baseline = snapshot
            else:
                _assert_rect_stable(baseline, snapshot, f"{surface}/tertiary/{state}")
            evidence[state] = _snapshot_for_manifest(snapshot, surface)
        finally:
            if state == "active":
                try:
                    page.mouse.move(0, 0)
                finally:
                    page.mouse.up()
    page.mouse.move(0, 0)
    return evidence


def _disabled_state_evidence(page: Any, surface: str) -> Mapping[str, Any]:
    locator = _case_locator(page, surface, "disabled")
    locator.scroll_into_view_if_needed()
    baseline = _style_snapshot(locator)
    if not baseline["disabled"] and baseline["ariaDisabled"] != "true":
        raise ThemeContractError(f"{surface}/disabled lacks native disabled semantics")
    _exact_computed_color(
        baseline["color"], APPROVED_TOKENS["text.disabled"], f"{surface}/disabled text"
    )
    disabled_colors = (baseline["backgroundColor"], *baseline["borderColors"])
    if not any(
        parse_css_color(value)[:3] == rgb(APPROVED_TOKENS["interactive.disabled"])
        for value in disabled_colors
    ):
        raise ThemeContractError(f"{surface}/disabled does not use the disabled role")

    clicks = locator.evaluate(
        "element => { let count = 0; const listener = () => { count += 1; }; "
        "element.addEventListener('click', listener); element.click(); "
        "element.removeEventListener('click', listener); return count; }"
    )
    if clicks != 0:
        raise ThemeContractError(f"{surface}/disabled dispatched a click")
    locator.evaluate("element => element.focus()")
    if locator.evaluate("element => document.activeElement === element"):
        raise ThemeContractError(f"{surface}/disabled accepted focus")

    locator.hover()
    hovered = _style_snapshot(locator)
    page.mouse.down()
    try:
        active = _style_snapshot(locator)
    finally:
        try:
            page.mouse.move(0, 0)
        finally:
            page.mouse.up()
    for changed, state in ((hovered, "hover"), (active, "active")):
        for property_name in ("color", "backgroundColor", "borderColors"):
            if changed[property_name] != baseline[property_name]:
                raise ThemeContractError(f"{surface}/disabled changed on {state}")
        _assert_rect_stable(baseline, changed, f"{surface}/disabled/{state}")
    return {
        "semantics": {
            "disabled": baseline["disabled"],
            "ariaDisabled": baseline["ariaDisabled"],
            "programmaticClickEvents": clicks,
            "focusAccepted": False,
            "inactiveContrastException": True,
        },
        "default": _snapshot_for_manifest(baseline, surface),
    }


def _visible_text_handle(owner: Any, text: str) -> Any:
    handle = owner.evaluate_handle(
        "(root, expected) => {"
        " const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();"
        " const candidates = Array.from(root.querySelectorAll('*')).filter(node => {"
        "   const rect = node.getBoundingClientRect();"
        "   const style = getComputedStyle(node);"
        "   return normalize(node.innerText) === expected && rect.width > 0 && rect.height > 0"
        "     && style.visibility !== 'hidden' && style.display !== 'none';"
        " });"
        " candidates.sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length"
        "   || a.getBoundingClientRect().width * a.getBoundingClientRect().height"
        "      - b.getBoundingClientRect().width * b.getBoundingClientRect().height);"
        " return candidates[0] || null;"
        "}",
        arg=text,
    )
    element = handle.as_element()
    if element is None:
        handle.dispose()
        raise ThemeContractError(f"visible exact text node is missing: {text!r}")
    return element


def _label_contrast_evidence(owner: Any, text: str, surface: str) -> Mapping[str, Any]:
    handle = _visible_text_handle(owner, text)
    try:
        snapshot = _style_snapshot(handle)
        ratio = _text_contrast(snapshot, surface)
        if ratio < 4.5:
            raise ThemeContractError(
                f"{surface} label contrast failed for {text!r}: {ratio:.3f}"
            )
        return _snapshot_for_manifest(snapshot, surface)
    finally:
        handle.dispose()


_SELECTED_PART_SPECS: Mapping[str, Mapping[str, Mapping[str, Any]]] = MappingProxyType({
    "checkbox": MappingProxyType({
        "box": MappingProxyType({"node": "checked-input<-box", "paint": "fill", "role": "interactive.control", "adjacent": "surface", "minimum": 3.0}),
        "mark": MappingProxyType({"node": "checked-input<-box::rendered-mark", "paint": "mark", "role": "text.on-primary", "adjacent": "interactive.control", "minimum": 3.0}),
    }),
    "radio": MappingProxyType({
        "boundary": MappingProxyType({"node": "checked-radio<-boundary", "paint": "fill", "role": "interactive.control", "adjacent": "surface", "minimum": 3.0}),
        "dot": MappingProxyType({"node": "checked-radio<-boundary>dot", "paint": "mark", "role": "text.on-primary", "adjacent": "interactive.control", "minimum": 3.0}),
    }),
    "toggle": MappingProxyType({
        "track": MappingProxyType({"node": "checked-toggle<-track", "paint": "fill", "role": "interactive.control", "adjacent": "surface", "minimum": 3.0}),
        "thumb": MappingProxyType({"node": "checked-toggle<-track>thumb", "paint": "mark", "role": "text.on-primary", "adjacent": "interactive.control", "minimum": 3.0}),
    }),
    "slider": MappingProxyType({
        "selectedTrack": MappingProxyType({"node": "slider-gradient-track@25%", "paint": "rendered-pixel", "role": "interactive.control", "adjacent": "surface", "minimum": 3.0}),
        "unselectedTrack": MappingProxyType({"node": "slider-gradient-track@80%", "paint": "rendered-pixel", "role": None, "adjacent": "surface", "minimum": 3.0}),
        "thumb": MappingProxyType({"node": "slider[aria-valuenow=60]", "paint": "fill", "role": "interactive.control", "adjacent": "surface", "minimum": 3.0}),
        "valueLabel": MappingProxyType({"node": "stSliderThumbValue:text=60", "paint": "text", "role": "interactive.accent", "adjacent": "surface", "minimum": 4.5}),
    }),
    "radio_horizontal": MappingProxyType({
        "boundary": MappingProxyType({"node": "checked-radio<-boundary", "paint": "fill", "role": "interactive.control", "adjacent": "surface", "minimum": 3.0}),
        "dot": MappingProxyType({"node": "checked-radio<-boundary>dot", "paint": "mark", "role": "text.on-primary", "adjacent": "interactive.control", "minimum": 3.0}),
    }),
})


def validate_radio_horizontal_semantic_state(state: Mapping[str, Any]) -> None:
    expected = {
        "groupRole": "radiogroup",
        "groupName": "水平單選標籤",
        "optionRole": "radio",
        "optionLabels": ["已選項", "其他項"],
        "checkedLabels": ["已選項"],
        "tabSequenceLabels": ["已選項"],
        "afterArrowRight": "其他項",
        "afterArrowLeft": "已選項",
    }
    actual = dict(state) if isinstance(state, Mapping) else state
    if actual != expected:
        raise ThemeContractError(
            f"horizontal-radio semantic state differs: actual={actual!r}"
        )


def validate_selectbox_semantic_state(state: Mapping[str, Any]) -> None:
    expected = {
        "role": "combobox",
        "accessibleName": "下拉選單標籤",
        "optionLabels": ["已選項", "其他項"],
        "selectedText": "已選項",
        "afterArrowDown": "其他項",
        "afterArrowUp": "已選項",
    }
    actual = dict(state) if isinstance(state, Mapping) else state
    if actual != expected:
        raise ThemeContractError(f"selectbox semantic state differs: actual={actual!r}")


def validate_selected_part_measurements(
    case: str,
    surface: str,
    measurements: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    """Validate only the exact rendered control parts, never owner-wide token hits."""

    if case not in _SELECTED_PART_SPECS or surface not in SURFACE_COLORS:
        raise ThemeContractError("selected-control measurement requested outside contract")
    specs = _SELECTED_PART_SPECS[case]
    if set(measurements) != set(specs):
        raise ThemeContractError(
            f"{case} selected-part set differs: {sorted(measurements)!r}"
        )
    result: dict[str, Any] = {}
    for name, spec in specs.items():
        row = measurements[name]
        if not isinstance(row, Mapping) or set(row) != {
            "node", "paint", "actual", "adjacent", "composited", "source"
        }:
            raise ThemeContractError(f"{case}/{name} measurement schema differs")
        if row["node"] != spec["node"] or row["paint"] != spec["paint"]:
            raise ThemeContractError(f"{case}/{name} measured an unrelated DOM part")
        source = row["source"]
        if (
            row["composited"] is not True
            or not isinstance(source, str)
            or source not in {"computed-style", "rendered-pixel"}
        ):
            raise ThemeContractError(f"{case}/{name} is not composited evidence")
        try:
            actual = tuple(int(value) for value in row["actual"])
            adjacent = tuple(int(value) for value in row["adjacent"])
        except (TypeError, ValueError) as exc:
            raise ThemeContractError(f"{case}/{name} color payload is malformed") from exc
        if (
            len(actual) != 3 or len(adjacent) != 3
            or any(not 0 <= value <= 255 for value in (*actual, *adjacent))
        ):
            raise ThemeContractError(f"{case}/{name} color payload is outside RGB")
        role = spec["role"]
        if role is not None and actual != rgb(APPROVED_TOKENS[role]):
            raise ThemeContractError(
                f"{case}/{name} differs from exact {role}: {actual!r}"
            )
        adjacent_role = spec["adjacent"]
        expected_adjacent = (
            rgb(SURFACE_COLORS[surface])
            if adjacent_role == "surface"
            else rgb(APPROVED_TOKENS[adjacent_role])
        )
        if adjacent != expected_adjacent:
            raise ThemeContractError(
                f"{case}/{name} adjacency differs: {adjacent!r}"
            )
        ratio = contrast_ratio(actual, adjacent)
        if ratio < float(spec["minimum"]):
            raise ThemeContractError(
                f"{surface}/{case}/{name} contrast failed: {ratio:.3f}"
            )
        result[name] = {
            **dict(row),
            "actual": list(actual),
            "adjacent": list(adjacent),
            "expectedRole": role,
            "adjacentRole": adjacent_role,
            "minimumContrast": spec["minimum"],
            "contrast": round(ratio, 3),
        }
    return MappingProxyType(result)


def _exact_related_handle(root: Any, script: str, label: str) -> Any:
    count = root.evaluate(
        "(owner, source) => { const value = Function('owner', source)(owner); "
        "return value ? 1 : 0; }",
        arg=script,
    )
    if count != 1:
        raise ThemeContractError(f"selected-control DOM part missing: {label}")
    handle = root.evaluate_handle(
        "(owner, source) => Function('owner', source)(owner)", arg=script
    )
    element = handle.as_element()
    if element is None:
        handle.dispose()
        raise ThemeContractError(f"selected-control DOM part detached: {label}")
    return element


def _computed_part_measurement(
    handle: Any,
    *,
    surface: str,
    node: str,
    paint: str,
    property_name: str,
    adjacent: tuple[int, int, int],
) -> Mapping[str, Any]:
    snapshot = _style_snapshot(handle)
    if property_name == "backgroundColor":
        parsed = parse_css_color(str(snapshot["backgroundColor"]))
        actual = composite_rgba(parsed, (*adjacent, 1.0))
    elif property_name == "color":
        background = _resolved_background(snapshot, surface)
        if background[:3] != adjacent:
            raise ThemeContractError(
                f"{surface}/{node} actual text background differs: {background[:3]!r}"
            )
        actual = _resolved_foreground(snapshot, background)
    else:
        raise ThemeContractError(f"unsupported selected-part property: {property_name}")
    return {
        "node": node,
        "paint": paint,
        "actual": list(actual[:3]),
        "adjacent": list(adjacent),
        "composited": True,
        "source": "computed-style",
    }


def _dom_part_snapshot(handle: Any) -> Mapping[str, Any]:
    value = handle.evaluate(
        "element => { const style=getComputedStyle(element);"
        " const rect=element.getBoundingClientRect();"
        " const image=style.backgroundImage || 'none';"
        " const imageKind=image === 'none' ? 'none'"
        "   : image.startsWith('url(\"data:image/svg+xml') ? 'data-svg'"
        "   : image.startsWith('linear-gradient') ? 'linear-gradient' : 'other';"
        " return {tag:element.tagName.toLowerCase(),"
        "   testid:element.getAttribute('data-testid'),kind:element.getAttribute('kind'),"
        "   role:element.getAttribute('role'),type:element.getAttribute('type'),"
        "   ariaChecked:element.getAttribute('aria-checked'),"
        "   ariaValueNow:element.getAttribute('aria-valuenow'),"
        "   checked:'checked' in element ? Boolean(element.checked) : null,"
        "   text:(element.innerText || '').replace(/\\s+/g,' ').trim(),"
        "   style:{color:style.color,backgroundColor:style.backgroundColor,"
        "     backgroundImageKind:imageKind,borderColors:[style.borderTopColor,"
        "       style.borderRightColor,style.borderBottomColor,style.borderLeftColor],"
        "     opacity:style.opacity},"
        "   rect:{top:rect.top,right:rect.right,bottom:rect.bottom,left:rect.left,"
        "     width:rect.width,height:rect.height}}; }"
    )
    if not isinstance(value, Mapping):
        raise ThemeContractError("selected-control DOM signature is malformed")
    return value


def _rendered_pixel_roles(
    handle: Any, expected: Mapping[str, tuple[int, int, int]]
) -> Mapping[str, tuple[int, int, int]]:
    from PIL import Image

    handle.evaluate("element => element.scrollIntoView({block:'center', inline:'center'})")
    payload = handle.screenshot(animations="disabled")
    image = Image.open(io.BytesIO(payload)).convert("RGB")
    pixels = [tuple(int(channel) for channel in value) for value in image.getdata()]
    result: dict[str, tuple[int, int, int]] = {}
    for name, target in expected.items():
        matches = [value for value in pixels if _near(value, target, CHANNEL_TOLERANCE)]
        if not matches:
            raise ThemeContractError(
                f"rendered selected-control part lacks expected pixel {name}: {target!r}"
            )
        result[name] = min(matches, key=lambda value: sum(abs(a - b) for a, b in zip(value, target)))
    return MappingProxyType(result)


def _slider_track_pixels(track: Any) -> Mapping[str, Any]:
    from PIL import Image

    track.evaluate("element => element.scrollIntoView({block:'center', inline:'center'})")
    payload = track.screenshot(animations="disabled")
    image = Image.open(io.BytesIO(payload)).convert("RGB")
    if image.width < 20 or image.height < 2:
        raise ThemeContractError(f"slider track screenshot is too small: {image.size!r}")
    y = image.height // 2
    return MappingProxyType({
        "selected": tuple(int(value) for value in image.getpixel((image.width // 4, y))),
        "unselected": tuple(int(value) for value in image.getpixel((image.width * 4 // 5, y))),
        "beforeValue": tuple(int(value) for value in image.getpixel((image.width * 59 // 100, y))),
        "afterValue": tuple(int(value) for value in image.getpixel((image.width * 61 // 100, y))),
        "width": image.width,
        "height": image.height,
    })


def _selected_control_evidence(page: Any, surface: str, case: str) -> Mapping[str, Any]:
    owner = _owner_locator(page, surface, case)
    surface_rgb = rgb(SURFACE_COLORS[surface])
    control_rgb = rgb(APPROVED_TOKENS["interactive.control"])
    white_rgb = rgb(APPROVED_TOKENS["text.on-primary"])
    measurements: dict[str, Mapping[str, Any]] = {}
    dom_parts: dict[str, Mapping[str, Any]] = {}
    semantics: dict[str, Any]
    handles: list[Any] = []
    try:
        if case in {"checkbox", "toggle"}:
            accessible_name = CASE_ACCESSIBLE_NAMES[case]
            locator = _case_locator(page, surface, case)
            semantic = _style_snapshot(locator)
            if semantic["checked"] is not True or semantic["ariaChecked"] != "true":
                raise ThemeContractError(f"{surface}/{case} lacks checked semantics")
            box = _exact_related_handle(
                owner,
                "const input=owner.querySelector('input[type=checkbox]:checked');"
                "return input && input.previousElementSibling;",
                f"{surface}/{case}/paint",
            )
            handles.append(box)
            dom_parts["paint"] = _dom_part_snapshot(box)
            if case == "checkbox":
                mark_structure = box.evaluate(
                    "box => { const style=getComputedStyle(box);"
                    " const image=(style.backgroundImage || '').toLowerCase();"
                    " const pseudoNames=['::before','::after'];"
                    " const pseudo=pseudoNames.map(name => { const paint=getComputedStyle(box,name);"
                    "   return {name,content:paint.content,backgroundColor:paint.backgroundColor,"
                    "     borderColors:[paint.borderTopColor,paint.borderRightColor,"
                    "       paint.borderBottomColor,paint.borderLeftColor],"
                    "     clipPath:paint.clipPath,width:paint.width,height:paint.height}; });"
                    " const svgPath=image.includes('data:image/svg+xml')"
                    "   && (image.includes('%3cpath') || image.includes('<path'));"
                    " const pseudoMark=pseudo.some(row => row.clipPath !== 'none'"
                    "   || (!['none','normal'].includes(row.content)"
                    "     && row.width !== 'auto' && row.height !== 'auto'));"
                    " return {svgPath,pseudoMark,pseudo}; }"
                )
                if not mark_structure["svgPath"] and not mark_structure["pseudoMark"]:
                    raise ThemeContractError(
                        f"{surface}/checkbox has white pixels but no check-mark paint"
                    )
                pixels = _rendered_pixel_roles(box, {"box": control_rgb, "mark": white_rgb})
                measurements.update({
                    "box": {"node": "checked-input<-box", "paint": "fill", "actual": list(pixels["box"]), "adjacent": list(surface_rgb), "composited": True, "source": "rendered-pixel"},
                    "mark": {"node": "checked-input<-box::rendered-mark", "paint": "mark", "actual": list(pixels["mark"]), "adjacent": list(pixels["box"]), "composited": True, "source": "rendered-pixel"},
                })
            else:
                thumb = _exact_related_handle(
                    owner,
                    "const input=owner.querySelector('input[type=checkbox]:checked');"
                    "return input && input.previousElementSibling && input.previousElementSibling.firstElementChild;",
                    f"{surface}/{case}/thumb",
                )
                handles.append(thumb)
                dom_parts["thumb"] = _dom_part_snapshot(thumb)
                track_pixels = _rendered_pixel_roles(box, {"track": control_rgb, "thumb": white_rgb})
                measurements.update({
                    "track": {"node": "checked-toggle<-track", "paint": "fill", "actual": list(track_pixels["track"]), "adjacent": list(surface_rgb), "composited": True, "source": "rendered-pixel"},
                    "thumb": {"node": "checked-toggle<-track>thumb", "paint": "mark", "actual": list(track_pixels["thumb"]), "adjacent": list(track_pixels["track"]), "composited": True, "source": "rendered-pixel"},
                })
            semantics = {
                "accessibleName": accessible_name,
                "role": CASE_ROLES[case],
                "checked": semantic["checked"],
                "ariaChecked": semantic["ariaChecked"],
            }
            if case == "checkbox":
                semantics["markStructure"] = mark_structure
        elif case in {"radio", "radio_horizontal"}:
            locator = _case_locator(page, surface, case)
            semantic = _style_snapshot(locator)
            if semantic["checked"] is not True:
                raise ThemeContractError(
                    f"{surface}/{case} lacks native checked semantics"
                )
            boundary = _exact_related_handle(
                owner,
                "const input=owner.querySelector('input[type=radio]:checked');"
                "return input && input.previousElementSibling;",
                f"{surface}/{case}/boundary",
            )
            handles.append(boundary)
            dom_parts["boundary"] = _dom_part_snapshot(boundary)
            dot = boundary.evaluate_handle("element => element.firstElementChild")
            dot_element = dot.as_element()
            if dot_element is None:
                dot.dispose()
                raise ThemeContractError(
                    f"{surface}/{case} rendered dot is missing"
                )
            handles.append(dot_element)
            dom_parts["dot"] = _dom_part_snapshot(dot_element)
            pixels = _rendered_pixel_roles(
                boundary, {"boundary": control_rgb, "dot": white_rgb}
            )
            measurements.update({
                "boundary": {"node": "checked-radio<-boundary", "paint": "fill", "actual": list(pixels["boundary"]), "adjacent": list(surface_rgb), "composited": True, "source": "rendered-pixel"},
                "dot": {"node": "checked-radio<-boundary>dot", "paint": "mark", "actual": list(pixels["dot"]), "adjacent": list(pixels["boundary"]), "composited": True, "source": "rendered-pixel"},
            })
            semantics = {
                "accessibleName": CASE_ACCESSIBLE_NAMES[case],
                "role": CASE_ROLES[case],
                "checked": semantic["checked"],
                "ariaChecked": semantic["ariaChecked"],
            }
            if case == "radio_horizontal":
                group = owner.get_by_role(
                    "radiogroup", name="水平單選標籤", exact=True
                )
                options = group.get_by_role("radio")
                selected_option = group.get_by_role(
                    "radio", name="已選項", exact=True
                )
                other_option = group.get_by_role(
                    "radio", name="其他項", exact=True
                )
                if (
                    group.count() != 1
                    or options.count() != 2
                    or selected_option.count() != 1
                    or other_option.count() != 1
                ):
                    raise ThemeContractError(
                        f"{surface}/radio_horizontal semantic node set differs"
                    )
                option_labels = ["已選項", "其他項"]
                checked_labels = [
                    label
                    for label, option in (
                        ("已選項", selected_option),
                        ("其他項", other_option),
                    )
                    if option.is_checked()
                ]
                selected_option.focus()
                selected_option.press("Shift+Tab")
                page.keyboard.press("Tab")
                tabbed_label = owner.evaluate(
                    "root => { const active=document.activeElement;"
                    " if (!active || !root.contains(active)"
                    "     || active.getAttribute('type') !== 'radio') return null;"
                    " const label=active.labels && active.labels[0];"
                    " return (label ? label.innerText : active.value)"
                    "   .replace(/\\s+/g,' ').trim(); }"
                )
                tab_sequence_labels = (
                    [str(tabbed_label)] if tabbed_label is not None else []
                )
                page.keyboard.press("Tab")
                if other_option.evaluate(
                    "element => document.activeElement === element"
                ):
                    raise ThemeContractError(
                        f"{surface}/radio_horizontal exposes two tab stops"
                    )
                layout = options.evaluate_all(
                    "nodes => nodes.map(node => {"
                    " const target=node.closest('label')"
                    "   || node.parentElement || node;"
                    " const rect=target.getBoundingClientRect();"
                    " return {left:rect.left,right:rect.right,top:rect.top,"
                    "   bottom:rect.bottom,width:rect.width,height:rect.height};"
                    "})"
                )
                if (
                    len(layout) != 2
                    or float(layout[1]["left"]) <= float(layout[0]["left"])
                    or abs(float(layout[1]["top"]) - float(layout[0]["top"])) > 1.0
                    or min(
                        float(layout[0]["width"]),
                        float(layout[0]["height"]),
                        float(layout[1]["width"]),
                        float(layout[1]["height"]),
                    ) < 24.0
                ):
                    raise ThemeContractError(
                        f"{surface}/radio_horizontal layout differs"
                    )
                selected_option.focus()
                selected_option.press("ArrowRight")
                if not other_option.is_checked():
                    raise ThemeContractError(
                        f"{surface}/radio_horizontal ArrowRight did not select other"
                    )
                after_arrow_right = "其他項"
                other_option.press("ArrowLeft")
                if not selected_option.is_checked():
                    raise ThemeContractError(
                        f"{surface}/radio_horizontal ArrowLeft did not restore selected"
                    )
                after_arrow_left = "已選項"
                semantic_state = {
                    "groupRole": group.get_attribute("role"),
                    "groupName": "水平單選標籤",
                    "optionRole": "radio",
                    "optionLabels": option_labels,
                    "checkedLabels": checked_labels,
                    "tabSequenceLabels": tab_sequence_labels,
                    "afterArrowRight": after_arrow_right,
                    "afterArrowLeft": after_arrow_left,
                }
                validate_radio_horizontal_semantic_state(semantic_state)
                semantics = {
                    **semantic_state,
                    "layout": layout,
                    "selectionBasis": "native-radio/one-checked/roving-tabstop",
                }
        elif case == "slider":
            locator = _case_locator(page, surface, case)
            semantic = _style_snapshot(locator)
            if semantic["ariaValueNow"] != "60":
                raise ThemeContractError(f"{surface}/slider aria-valuenow differs from 60")
            track = _exact_related_handle(
                owner,
                "const base=owner.querySelector('[data-baseweb=slider]');"
                "return base && base.firstElementChild && base.firstElementChild.firstElementChild"
                " && base.firstElementChild.firstElementChild.lastElementChild;",
                f"{surface}/slider/track",
            )
            value_label = _exact_related_handle(
                owner,
                "const value=owner.querySelector('[data-testid=stSliderThumbValue]');"
                "return value && value.textContent.trim()==='60' ? value : null;",
                f"{surface}/slider/value",
            )
            handles.extend((track, value_label))
            dom_parts.update({
                "track": _dom_part_snapshot(track),
                "thumb": _dom_part_snapshot(locator),
                "valueLabel": _dom_part_snapshot(value_label),
            })
            track_pixels = _slider_track_pixels(track)
            if (
                not _near(track_pixels["beforeValue"], control_rgb, CHANNEL_TOLERANCE)
                or not _near(
                    track_pixels["afterValue"], track_pixels["unselected"],
                    CHANNEL_TOLERANCE,
                )
            ):
                raise ThemeContractError(
                    f"{surface}/slider rendered track does not transition at value 60"
                )
            measurements.update({
                "selectedTrack": {"node": "slider-gradient-track@25%", "paint": "rendered-pixel", "actual": list(track_pixels["selected"]), "adjacent": list(surface_rgb), "composited": True, "source": "rendered-pixel"},
                "unselectedTrack": {"node": "slider-gradient-track@80%", "paint": "rendered-pixel", "actual": list(track_pixels["unselected"]), "adjacent": list(surface_rgb), "composited": True, "source": "rendered-pixel"},
                "thumb": _computed_part_measurement(locator, surface=surface, node="slider[aria-valuenow=60]", paint="fill", property_name="backgroundColor", adjacent=surface_rgb),
                "valueLabel": _computed_part_measurement(value_label, surface=surface, node="stSliderThumbValue:text=60", paint="text", property_name="color", adjacent=surface_rgb),
            })
            semantics = {
                "accessibleName": CASE_ACCESSIBLE_NAMES[case],
                "role": semantic["role"],
                "ariaValueNow": semantic["ariaValueNow"],
                "ariaValueText": locator.get_attribute("aria-valuetext"),
                "trackAdjacency": {
                    "beforeValue59": list(track_pixels["beforeValue"]),
                    "afterValue61": list(track_pixels["afterValue"]),
                    "selectedSample25": list(track_pixels["selected"]),
                    "unselectedSample80": list(track_pixels["unselected"]),
                    "width": track_pixels["width"],
                    "height": track_pixels["height"],
                },
            }
        elif case == "selectbox":
            locator = _case_locator(page, surface, case)
            semantic = _style_snapshot(locator)
            select_root = owner.locator('[data-baseweb="select"]')
            if select_root.count() != 1:
                raise ThemeContractError(
                    f"{surface}/selectbox rendered root differs"
                )
            selected_text = " ".join(select_root.inner_text().split())
            if selected_text != "已選項":
                raise ThemeContractError(
                    f"{surface}/selectbox initial selection differs"
                )
            locator.focus()
            locator.press("ArrowDown")
            listbox = page.get_by_role("listbox")
            if listbox.count() != 1:
                raise ThemeContractError(
                    f"{surface}/selectbox listbox did not open"
                )
            options = listbox.get_by_role("option")
            option_labels = [text.strip() for text in options.all_inner_texts()]
            if option_labels != ["已選項", "其他項"]:
                raise ThemeContractError(
                    f"{surface}/selectbox option labels differ"
                )
            locator.press("ArrowDown")
            locator.press("Enter")
            after_arrow_down = " ".join(select_root.inner_text().split())
            locator.press("ArrowUp")
            locator.press("ArrowUp")
            locator.press("Enter")
            after_arrow_up = " ".join(select_root.inner_text().split())
            semantic_state = {
                "role": semantic["role"],
                "accessibleName": CASE_ACCESSIBLE_NAMES[case],
                "optionLabels": option_labels,
                "selectedText": selected_text,
                "afterArrowDown": after_arrow_down,
                "afterArrowUp": after_arrow_up,
            }
            validate_selectbox_semantic_state(semantic_state)
            value_evidence = _label_contrast_evidence(
                owner, "已選項", surface
            )
            semantics = {
                **semantic_state,
                "selectionBasis": "combobox/exact-option-order/keyboard",
                "selectedValue": value_evidence,
            }
        else:
            raise ThemeContractError(f"unknown selected control: {case}")

        label_text = {
            "checkbox": "核取方塊標籤",
            "radio": "已選項",
            "toggle": "切換標籤",
            "slider": "滑桿標籤",
            "radio_horizontal": "水平單選標籤",
            "selectbox": "下拉選單標籤",
        }[case]
        label = _label_contrast_evidence(owner, label_text, surface)
        validated = (
            MappingProxyType({})
            if case == "selectbox"
            else validate_selected_part_measurements(case, surface, measurements)
        )
        return {
            "semantics": semantics,
            "label": label,
            "parts": {name: dict(row) for name, row in validated.items()},
            "domParts": {name: dict(row) for name, row in dom_parts.items()},
            "owner": owner_id(surface, case),
        }
    finally:
        for handle in handles:
            with contextlib.suppress(Exception):
                handle.dispose()


def _tab_state_evidence(page: Any, surface: str) -> Mapping[str, Any]:
    owner = _owner_locator(page, surface, "tabs")
    selected = _case_locator(page, surface, "tabs")
    snapshot = _style_snapshot(selected)
    if snapshot["ariaSelected"] != "true":
        raise ThemeContractError(f"{surface}/tabs active tab lacks aria-selected=true")
    _exact_computed_color(
        snapshot["color"], APPROVED_TOKENS["interactive.accent"], f"{surface}/tabs text"
    )
    if _text_contrast(snapshot, surface) < 4.5:
        raise ThemeContractError(f"{surface}/tabs active text contrast failed")

    underline = owner.evaluate(
        "(root, accent) => Array.from(root.querySelectorAll('*')).map(node => {"
        " const style = getComputedStyle(node); const rect = node.getBoundingClientRect();"
        " return {backgroundColor: style.backgroundColor, width: rect.width, height: rect.height,"
        "   testid: node.getAttribute('data-testid')};"
        " }).filter(row => row.backgroundColor === accent && row.width > 0 && row.height >= 2)",
        arg=_browser_rgb(APPROVED_TOKENS["interactive.accent"]),
    )
    if not isinstance(underline, list) or not underline:
        raise ThemeContractError(f"{surface}/tabs has no >=2px accent underline")
    if contrast_ratio(APPROVED_TOKENS["interactive.accent"], SURFACE_COLORS[surface]) < 3.0:
        raise ThemeContractError(f"{surface}/tabs underline contrast failed")

    other = owner.get_by_role("tab", name="其他分頁", exact=True)
    if other.count() != 1:
        raise ThemeContractError(f"{surface}/tabs hover target is missing")
    before = _style_snapshot(other)
    other.hover()
    _wait_for_color(page, other, "color", APPROVED_TOKENS["interactive.accent"])
    hovered = _style_snapshot(other)
    _exact_computed_color(
        hovered["color"], APPROVED_TOKENS["interactive.accent"], f"{surface}/tabs hover"
    )
    _assert_rect_stable(before, hovered, f"{surface}/tabs/hover")
    page.mouse.move(0, 0)
    return {
        "active": _snapshot_for_manifest(snapshot, surface),
        "hover": _snapshot_for_manifest(hovered, surface),
        "semantics": {"ariaSelected": "true", "underline": underline},
    }


def _markdown_link_evidence(page: Any, surface: str) -> Mapping[str, Any]:
    locator = _case_locator(page, surface, "markdown_link")
    locator.scroll_into_view_if_needed()
    _wait_for_color(page, locator, "color", APPROVED_TOKENS["interactive.accent"])
    default = _style_snapshot(locator)
    for state, snapshot in (("default", default),):
        _exact_computed_color(
            snapshot["color"], APPROVED_TOKENS["interactive.accent"],
            f"{surface}/markdown_link/{state}",
        )
        if "underline" not in str(snapshot["textDecorationLine"]).casefold():
            raise ThemeContractError(f"{surface}/markdown_link/{state} is not underlined")
        if _text_contrast(snapshot, surface) < 4.5:
            raise ThemeContractError(f"{surface}/markdown_link/{state} contrast failed")
    locator.hover()
    _wait_for_color(page, locator, "color", APPROVED_TOKENS["interactive.accent"])
    hovered = _style_snapshot(locator)
    _exact_computed_color(
        hovered["color"], APPROVED_TOKENS["interactive.accent"],
        f"{surface}/markdown_link/hover",
    )
    if "underline" not in str(hovered["textDecorationLine"]).casefold():
        raise ThemeContractError(f"{surface}/markdown_link/hover is not underlined")
    _assert_rect_stable(default, hovered, f"{surface}/markdown_link/hover")
    page.mouse.move(0, 0)
    return {
        "default": _snapshot_for_manifest(default, surface),
        "hover": _snapshot_for_manifest(hovered, surface),
        "visited": "static-only; no protected-history claim",
    }


def _alert_evidence(page: Any, surface: str) -> Sequence[Mapping[str, Any]]:
    owner = _owner_locator(page, surface, "alerts")
    alerts = owner.locator('[data-testid="stAlert"]')
    if alerts.count() != 4:
        raise ThemeContractError(f"{surface}/alerts must contain exactly four native alerts")
    expected = (
        ("資訊狀態", "ℹ"),
        ("成功狀態", "✅"),
        ("警告狀態", "⚠"),
        ("錯誤狀態", "⛔"),
    )
    rows: list[Mapping[str, Any]] = []
    for index, (meaning, icon) in enumerate(expected):
        alert = alerts.nth(index)
        text = " ".join(alert.inner_text().split())
        role = alert.get_attribute("role")
        if role != "alert" and alert.locator('[role="alert"]').count() == 0:
            raise ThemeContractError(f"{surface}/alerts/{index} lacks role=alert")
        if meaning not in text or icon not in text:
            raise ThemeContractError(f"{surface}/alerts/{index} lost text/icon meaning")
        text_handle = _visible_text_handle(alert, text)
        try:
            snapshot = _style_snapshot(text_handle)
            ratio = _text_contrast(snapshot, surface)
            if ratio < 4.5:
                raise ThemeContractError(
                    f"{surface}/alerts/{index} text contrast failed: {ratio:.3f}"
                )
            rows.append({
                "role": "alert",
                "meaning": meaning,
                "hasIcon": True,
                "style": _snapshot_for_manifest(snapshot, surface),
            })
        finally:
            text_handle.dispose()
    return tuple(rows)


def _signal_evidence(page: Any, surface: str) -> Sequence[Mapping[str, Any]]:
    owner = _owner_locator(page, surface, "signals")
    expected = (
        (".ux1b-avoid", "#ef4444", "⛔", "AVOID"),
        (".ux1b-bearish", "#ef553b", "▼", "Bearish"),
    )
    rows: list[Mapping[str, Any]] = []
    for selector, color, icon, meaning in expected:
        locator = owner.locator(selector)
        if locator.count() != 1 or not locator.is_visible():
            raise ThemeContractError(f"{surface}/signals missing {selector}")
        snapshot = _style_snapshot(locator)
        _exact_computed_color(snapshot["color"], color, f"{surface}/signals/{meaning}")
        text = locator.inner_text()
        if icon not in text or meaning not in text:
            raise ThemeContractError(f"{surface}/signals/{meaning} lost text/icon meaning")
        rows.append({
            "meaning": meaning,
            "color": color,
            "hasIcon": True,
            "text": text,
        })
    return tuple(rows)


_FOCUS_CANDIDATES_JS = """
(root, target) => {
  const candidates = [];
  const seen = new Set();
  const add = node => {
    if (!node || seen.has(node) || !root.contains(node)) return;
    seen.add(node);
    const style = getComputedStyle(node);
    const rect = node.getBoundingClientRect();
    const width = Number.parseFloat(style.outlineWidth);
    if (rect.width > 0 && rect.height > 0 && style.outlineStyle !== 'none'
        && Number.isFinite(width) && width >= 3
        && style.outlineColor === 'rgb(127, 227, 240)') candidates.push(node);
  };
  add(target);
  for (let node = target.parentElement; node && node !== root.parentElement;
       node = node.parentElement) add(node);
  for (const node of root.querySelectorAll('*')) add(node);
  return candidates;
}
"""


def _keyboard_focus(page: Any, locator: Any, surface: str, case: str) -> None:
    if locator.is_visible():
        locator.scroll_into_view_if_needed()
    else:
        locator.evaluate(
            "element => (element.closest('label') || element).scrollIntoView("
            "{block:'center', inline:'center'})"
        )
    locator.focus()
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    if not locator.evaluate(
        "element => element === document.activeElement || "
        "element.contains(document.activeElement)"
    ):
        raise ThemeContractError(f"keyboard Tab focus did not reach {surface}/{case}")


def _focus_ring_handle(owner: Any, target: Any, surface: str, case: str) -> Any:
    target_handle = target.element_handle()
    if target_handle is None:
        raise ThemeContractError(f"focus target detached: {surface}/{case}")
    count = owner.evaluate(
        f"(root, target) => ({_FOCUS_CANDIDATES_JS})(root, target).length",
        arg=target_handle,
    )
    if count != 1:
        raise ThemeContractError(
            f"{surface}/{case} must expose exactly one >=3px focus outline; found {count}"
        )
    handle = owner.evaluate_handle(
        f"(root, target) => ({_FOCUS_CANDIDATES_JS})(root, target)[0] || null",
        arg=target_handle,
    )
    element = handle.as_element()
    if element is None:
        handle.dispose()
        raise ThemeContractError(f"focus paint node missing: {surface}/{case}")
    return element


def _focus_geometry(handle: Any) -> Mapping[str, Any]:
    value = handle.evaluate(
        "element => {"
        " const style = getComputedStyle(element); const rect = element.getBoundingClientRect();"
        " const width = Number.parseFloat(style.outlineWidth);"
        " const offset = Number.parseFloat(style.outlineOffset);"
        " const expanded = width + offset; const clipped = new Set();"
        " for (let node = element.parentElement; node; node = node.parentElement) {"
        "   const ancestorStyle = getComputedStyle(node); const ancestor = node.getBoundingClientRect();"
        "   const clipsX = ['hidden', 'clip'].includes(ancestorStyle.overflowX);"
        "   const clipsY = ['hidden', 'clip'].includes(ancestorStyle.overflowY);"
        "   if (clipsY && rect.top - expanded < ancestor.top) clipped.add('top');"
        "   if (clipsX && rect.right + expanded > ancestor.right) clipped.add('right');"
        "   if (clipsY && rect.bottom + expanded > ancestor.bottom) clipped.add('bottom');"
        "   if (clipsX && rect.left - expanded < ancestor.left) clipped.add('left');"
        " }"
        " return {outlineColor: style.outlineColor, outlineStyle: style.outlineStyle,"
        "   outlineWidth: width, outlineOffset: offset, clippedSides: Array.from(clipped),"
        "   rect: {top: rect.top, right: rect.right, bottom: rect.bottom, left: rect.left,"
        "     width: rect.width, height: rect.height}};"
        "}"
    )
    if not isinstance(value, Mapping):
        raise ThemeContractError("focus geometry payload is malformed")
    return value


def _pixel_at(image: Any, x: float, y: float) -> tuple[tuple[int, int, int], bool]:
    column = math.floor(x)
    row = math.floor(y)
    clipped = column < 0 or row < 0 or column >= image.width or row >= image.height
    if clipped:
        return (0, 0, 0), True
    value = image.getpixel((column, row))
    return (int(value[0]), int(value[1]), int(value[2])), False


def _focus_samples_from_image(
    image: Any, geometry: Mapping[str, Any]
) -> Mapping[str, FocusSideSample]:
    rect = geometry["rect"]
    width = float(geometry["outlineWidth"])
    offset = float(geometry["outlineOffset"])
    center_x = (float(rect["left"]) + float(rect["right"])) / 2.0
    center_y = (float(rect["top"]) + float(rect["bottom"])) / 2.0
    points = {
        "top": (
            (center_x, float(rect["top"]) - offset / 2.0),
            (center_x, float(rect["top"]) - offset - width / 2.0),
            (center_x, float(rect["top"]) - offset - width - 1.5),
        ),
        "right": (
            (float(rect["right"]) + offset / 2.0, center_y),
            (float(rect["right"]) + offset + width / 2.0, center_y),
            (float(rect["right"]) + offset + width + 1.5, center_y),
        ),
        "bottom": (
            (center_x, float(rect["bottom"]) + offset / 2.0),
            (center_x, float(rect["bottom"]) + offset + width / 2.0),
            (center_x, float(rect["bottom"]) + offset + width + 1.5),
        ),
        "left": (
            (float(rect["left"]) - offset / 2.0, center_y),
            (float(rect["left"]) - offset - width / 2.0, center_y),
            (float(rect["left"]) - offset - width - 1.5, center_y),
        ),
    }
    clipped_sides = set(geometry["clippedSides"])
    result: dict[str, FocusSideSample] = {}
    for side, (gap_point, ring_point, outer_point) in points.items():
        gap, gap_clipped = _pixel_at(image, *gap_point)
        ring, ring_clipped = _pixel_at(image, *ring_point)
        outer, outer_clipped = _pixel_at(image, *outer_point)
        result[side] = FocusSideSample(
            gap=gap,
            ring=ring,
            outer=outer,
            clipped=(
                side in clipped_sides or gap_clipped or ring_clipped or outer_clipped
            ),
        )
    return MappingProxyType(result)


def _focus_evidence(
    page: Any, surface: str, case: str, viewport: tuple[int, int]
) -> Mapping[str, Any]:
    owner = _owner_locator(page, surface, case)
    target = _case_locator(page, surface, case)
    _keyboard_focus(page, target, surface, case)
    ring_handle = _focus_ring_handle(owner, target, surface, case)
    try:
        ring_handle.evaluate(
            "element => element.scrollIntoView({block: 'center', inline: 'center'})"
        )
        geometry = _focus_geometry(ring_handle)
        if geometry["outlineStyle"] != "solid":
            raise ThemeContractError(f"{surface}/{case} focus outline is not solid")
        if float(geometry["outlineWidth"]) < 3.0:
            raise ThemeContractError(f"{surface}/{case} focus outline is under 3px")
        if float(geometry["outlineOffset"]) < 1.0:
            raise ThemeContractError(f"{surface}/{case} has no full CSS-pixel focus gap")
        _exact_computed_color(
            str(geometry["outlineColor"]), APPROVED_TOKENS["border.focus"],
            f"{surface}/{case} focus outline",
        )

        from PIL import Image

        screenshot = page.screenshot(type="png", full_page=False, animations="disabled")
        image = Image.open(io.BytesIO(screenshot)).convert("RGB")
        if image.size != viewport:
            raise ThemeContractError(
                f"focus screenshot is not deviceScaleFactor=1: {image.size!r} != {viewport!r}"
            )
        samples = _focus_samples_from_image(image, geometry)
        ring_snapshot = _style_snapshot(ring_handle)
        component = _resolved_background(ring_snapshot, surface)[:3]
        validate_focus_adjacency(
            samples=samples,
            component_color=component,
            expected_surface=rgb(SURFACE_COLORS[surface]),
            expected_ring=rgb(APPROVED_TOKENS["border.focus"]),
            channel_tolerance=CHANNEL_TOLERANCE,
        )
        return {
            "keyboard": "Tab then Shift+Tab",
            "outlineWidth": geometry["outlineWidth"],
            "outlineOffset": geometry["outlineOffset"],
            "outlineColor": geometry["outlineColor"],
            "deviceScaleFactor": 1,
            "samples": {
                side: {
                    "gap": list(sample.gap) if sample.gap is not None else None,
                    "ring": list(sample.ring),
                    "outer": list(sample.outer),
                    "clipped": sample.clipped,
                }
                for side, sample in samples.items()
            },
        }
    finally:
        ring_handle.dispose()


def _selector_metadata(
    records: Sequence[SelectorContractRecord],
) -> Mapping[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    result: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
    for record in records:
        metadata = (record.owners, record.states)
        existing = result.setdefault(record.selector, metadata)
        if existing != metadata:
            raise ThemeContractError("selector contract metadata changed between properties")
    return MappingProxyType(result)


def _runtime_inventory_selector(selector: str, states: Sequence[str]) -> str:
    if "visited-static" in states:
        if ":visited" not in selector:
            raise ThemeContractError("visited-static selector lacks :visited")
        return selector.replace(":visited", ":link")
    return selector


def _query_selector_nodes(page: Any, selector: str) -> Sequence[Mapping[str, Any]]:
    value = page.evaluate(
        "selector => Array.from(document.querySelectorAll(selector)).map(node => {"
        " const owner = node.closest('[class*=\"st-key-ux1b_owner_\"]');"
        " const ownerClass = owner ? Array.from(owner.classList).find(name =>"
        "   name.startsWith('st-key-ux1b_owner_')) : null;"
        " const ownerId = ownerClass ? ownerClass.slice('st-key-'.length) : null;"
        " const within = owner ? Array.from(owner.querySelectorAll(selector)) : [];"
        " const index = within.indexOf(node);"
        " return {owner: ownerId, node: ownerId && index >= 0 ? `${ownerId}::${index}` : null,"
        "   tag: node.tagName.toLowerCase(), testid: node.getAttribute('data-testid'),"
        "   kind: node.getAttribute('kind'), role: node.getAttribute('role'),"
        "   ariaSelected: node.getAttribute('aria-selected'),"
        "   ariaChecked: node.getAttribute('aria-checked')};"
        "})",
        arg=selector,
    )
    if not isinstance(value, list) or any(not isinstance(row, Mapping) for row in value):
        raise ThemeContractError(f"selector inventory is malformed: {selector!r}")
    return tuple(value)


def _assert_selector_observation(
    *, selector: str, rows: Sequence[Mapping[str, Any]], expected_owners: Iterable[str]
) -> None:
    expected = frozenset(expected_owners)
    actual_owners = [row.get("owner") for row in rows]
    if any(owner is None for owner in actual_owners):
        raise ThemeContractError(f"selector has an orphan match: {selector!r}")
    counts = {owner: actual_owners.count(owner) for owner in set(actual_owners)}
    if set(counts) != set(expected) or any(count != 1 for count in counts.values()):
        raise ThemeContractError(
            f"selector owner/node observation differs for {selector!r}: "
            f"actual={counts!r} expected_one_each={sorted(expected)!r}"
        )
    expected_nodes = {f"{owner}::0" for owner in expected}
    actual_nodes = {str(row.get("node")) for row in rows}
    if actual_nodes != expected_nodes:
        raise ThemeContractError(
            f"selector node set differs for {selector!r}: "
            f"actual={sorted(actual_nodes)!r} expected={sorted(expected_nodes)!r}"
        )


def _observe_transient_selector(
    page: Any,
    selector: str,
    state: str,
    owner: str,
) -> Sequence[Mapping[str, Any]]:
    surface, case = _parse_owner_id(owner)
    target = _case_locator(page, surface, case)
    target.scroll_into_view_if_needed()
    if state == "hover":
        target.hover()
        rows = _query_selector_nodes(page, selector)
        page.mouse.move(0, 0)
        return rows
    if state == "active":
        target.hover()
        page.mouse.down()
        try:
            return _query_selector_nodes(page, selector)
        finally:
            try:
                page.mouse.move(0, 0)
            finally:
                page.mouse.up()
    if state == "focus-visible":
        _keyboard_focus(page, target, surface, case)
        return _query_selector_nodes(page, selector)
    raise ThemeContractError(f"unsupported transient selector state: {state}")


def _verify_selector_node_sets(
    page: Any, records: Sequence[SelectorContractRecord]
) -> Mapping[str, Any]:
    metadata = _selector_metadata(records)
    actual_owner_sets: dict[str, set[str]] = {}
    evidence: dict[str, Any] = {}
    for selector, (owners, states) in metadata.items():
        runtime_selector = _runtime_inventory_selector(selector, states)
        transient = [
            state for state in ("active", "focus-visible", "hover") if state in states
        ]
        if len(transient) > 1:
            raise ThemeContractError(
                f"selector combines unsupported transient states: {selector!r} {transient!r}"
            )
        collected: dict[str, Mapping[str, Any]] = {}
        observations: list[Mapping[str, Any]] = []
        if transient:
            state = transient[0]
            for expected_owner in owners:
                rows = _observe_transient_selector(
                    page, runtime_selector, state, expected_owner
                )
                _assert_selector_observation(
                    selector=selector, rows=rows, expected_owners=(expected_owner,)
                )
                for row in rows:
                    collected[str(row["node"])] = row
                observations.append({"owner": expected_owner, "matches": len(rows)})
        else:
            rows = _query_selector_nodes(page, runtime_selector)
            _assert_selector_observation(
                selector=selector, rows=rows, expected_owners=owners
            )
            for row in rows:
                collected[str(row["node"])] = row
            observations.append({"owners": list(owners), "matches": len(rows)})

        expected_nodes = {f"{owner}::0" for owner in owners}
        if set(collected) != expected_nodes:
            raise ThemeContractError(
                f"selector aggregate node set differs for {selector!r}: "
                f"actual={sorted(collected)!r} expected={sorted(expected_nodes)!r}"
            )
        actual_owner_sets[selector] = {str(row["owner"]) for row in collected.values()}
        evidence[selector] = {
            "states": list(states),
            "owners": sorted(actual_owner_sets[selector]),
            "nodes": sorted(collected),
            "signatures": [dict(collected[key]) for key in sorted(collected)],
            "observations": observations,
            "visitedComputedStyleClaimed": False,
        }

    require_exact_owner_sets(
        actual_owner_sets,
        {selector: set(owners) for selector, (owners, _) in metadata.items()},
    )
    return MappingProxyType(evidence)


def _assert_signal_selector_isolation(
    page: Any, records: Sequence[SelectorContractRecord]
) -> None:
    metadata = _selector_metadata(records)
    for selector, (_, states) in metadata.items():
        runtime_selector = _runtime_inventory_selector(selector, states)
        for surface in SURFACE_COLORS:
            signal_owner = _owner_locator(page, surface, "signals")
            matches = signal_owner.locator(runtime_selector).count()
            if matches:
                raise ThemeContractError(
                    f"interaction selector matched danger/signal fixture: {selector!r}"
                )
            if "hover" in states or "active" in states:
                signal = signal_owner.locator(".ux1b-signal-sample").first
                signal.hover()
                if "active" in states:
                    page.mouse.down()
                try:
                    if signal_owner.locator(runtime_selector).count():
                        raise ThemeContractError(
                            f"transient interaction selector matched signal: {selector!r}"
                        )
                finally:
                    if "active" in states:
                        try:
                            page.mouse.move(0, 0)
                        finally:
                            page.mouse.up()
                    else:
                        page.mouse.move(0, 0)


def _assert_gallery_ready(page: Any) -> None:
    page.locator(READY_MARKER).wait_for(state="attached", timeout=NAVIGATION_TIMEOUT_MS)
    expected_owner_count = len(SURFACE_COLORS) * len(REQUIRED_GALLERY_CASES)
    payload = page.evaluate(
        "([ownerPrefix, surfacePrefix]) => {"
        " const ownerClasses = Array.from(document.querySelectorAll('[class*=\"st-key-ux1b_owner_\"]'))"
        "   .map(node => Array.from(node.classList).find(name => name.startsWith(ownerPrefix)));"
        " const surfaces = Array.from(document.querySelectorAll('[class*=\"st-key-ux1b_surface_\"]'))"
        "   .map(node => Array.from(node.classList).find(name => name.startsWith(surfacePrefix)));"
        " return {ownerClasses, surfaces, markerCount: document.querySelectorAll('#ux1b-theme-ready').length,"
        "   exceptionCount: document.querySelectorAll('[data-testid=\"stException\"]').length};"
        "}",
        arg=["st-key-ux1b_owner_", "st-key-ux1b_surface_"],
    )
    if not isinstance(payload, Mapping):
        raise ThemeContractError("gallery readiness payload is malformed")
    owners = payload["ownerClasses"]
    surfaces = payload["surfaces"]
    if (
        len(owners) != expected_owner_count
        or len(set(owners)) != expected_owner_count
        or any(value is None for value in owners)
    ):
        raise ThemeContractError("gallery owner IDs are missing or duplicated")
    expected_owners = {
        f"st-key-{owner_id(surface, case)}"
        for surface in SURFACE_COLORS
        for case in REQUIRED_GALLERY_CASES
    }
    if set(owners) != expected_owners:
        raise ThemeContractError("gallery owner ID set differs from the frozen matrix")
    expected_surfaces = {f"st-key-ux1b_surface_{surface}" for surface in SURFACE_COLORS}
    if len(surfaces) != len(expected_surfaces) or set(surfaces) != expected_surfaces:
        raise ThemeContractError("gallery surface set differs from the frozen matrix")
    if payload["markerCount"] != 1 or payload["exceptionCount"] != 0:
        raise ThemeContractError("gallery ready marker or exception contract failed")


def _overflow_evidence(page: Any, surface: str) -> Mapping[str, Any]:
    surface_locator = page.locator(f".st-key-ux1b_surface_{surface}")
    if surface_locator.count() != 1:
        raise ThemeContractError(f"surface missing for overflow check: {surface}")
    payload = surface_locator.evaluate(
        "root => {"
        " const owners = Array.from(root.querySelectorAll('[class*=\"st-key-ux1b_owner_\"]')).map(node => ({"
        "   owner: Array.from(node.classList).find(name => name.startsWith('st-key-ux1b_owner_')) || null,"
        "   clientWidth: node.clientWidth, scrollWidth: node.scrollWidth}));"
        " const rect = root.getBoundingClientRect(); const style = getComputedStyle(root);"
        " return {surface: {clientWidth: root.clientWidth, scrollWidth: root.scrollWidth,"
        "   left: rect.left, right: rect.right, backgroundColor: style.backgroundColor}, owners,"
        "   document: {clientWidth: document.documentElement.clientWidth,"
        "     scrollWidth: document.documentElement.scrollWidth}};"
        "}"
    )
    if not isinstance(payload, Mapping):
        raise ThemeContractError("overflow payload is malformed")
    surface_row = payload["surface"]
    document_row = payload["document"]
    overflow_owners = [
        row["owner"] for row in payload["owners"]
        if float(row["scrollWidth"]) > float(row["clientWidth"]) + 1.0
    ]
    if float(surface_row["scrollWidth"]) > float(surface_row["clientWidth"]) + 1.0:
        raise ThemeContractError(f"{surface} has horizontal surface overflow")
    if float(document_row["scrollWidth"]) > float(document_row["clientWidth"]) + 1.0:
        raise ThemeContractError("gallery document has horizontal overflow")
    if overflow_owners:
        raise ThemeContractError(f"{surface} component owners overflow: {overflow_owners!r}")
    _exact_computed_color(
        surface_row["backgroundColor"], SURFACE_COLORS[surface], f"{surface} surface"
    )
    return {
        "surface": dict(surface_row),
        "document": dict(document_row),
        "overflowOwners": [],
    }


def _surface_state_evidence(
    page: Any, surface: str, viewport: tuple[int, int]
) -> Mapping[str, Any]:
    primary = {
        case: _primary_state_evidence(page, surface, case) for case in PRIMARY_CASES
    }
    selected = {
        case: _selected_control_evidence(page, surface, case)
        for case in (
            "checkbox",
            "radio",
            "radio_horizontal",
            "toggle",
            "slider",
            "selectbox",
        )
    }
    focus = {
        case: _focus_evidence(page, surface, case, viewport) for case in FOCUS_CASES
    }
    return {
        "primary": primary,
        "tertiary": _tertiary_state_evidence(page, surface),
        "disabled": _disabled_state_evidence(page, surface),
        "tabs": _tab_state_evidence(page, surface),
        "markdownLink": _markdown_link_evidence(page, surface),
        "selectedControls": selected,
        "alerts": list(_alert_evidence(page, surface)),
        "signals": list(_signal_evidence(page, surface)),
        "focus": focus,
    }


def _surface_worker_crop_geometry(page: Any, surface: str) -> Mapping[str, Any]:
    selector = f".st-key-ux1b_surface_{surface}"
    locator = page.locator(selector)
    if locator.count() != 1:
        raise ThemeContractError(f"theme worker surface differs: {surface}")
    observed = locator.evaluate(
        "root => { const rect=root.getBoundingClientRect();"
        " return {deviceScaleFactor:window.devicePixelRatio,"
        "   scrollOffset:{x:window.scrollX,y:window.scrollY},"
        "   cssRect:{left:rect.left,top:rect.top,right:rect.right,"
        "     bottom:rect.bottom,width:rect.width,height:rect.height}}; }"
    )
    if not isinstance(observed, Mapping):
        raise ThemeContractError(f"theme worker crop geometry malformed: {surface}")
    try:
        scale = float(observed["deviceScaleFactor"])
        scroll_x = float(observed["scrollOffset"]["x"])
        scroll_y = float(observed["scrollOffset"]["y"])
        css_rect = {
            key: float(observed["cssRect"][key])
            for key in ("left", "top", "right", "bottom", "width", "height")
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise ThemeContractError(
            f"theme worker crop geometry values malformed: {surface}"
        ) from exc
    if (
        scale != 1.0
        or any(not math.isfinite(value) for value in (scroll_x, scroll_y, *css_rect.values()))
        or css_rect["width"] <= 0
        or css_rect["height"] <= 0
        or abs(css_rect["right"] - css_rect["left"] - css_rect["width"]) > 0.1
        or abs(css_rect["bottom"] - css_rect["top"] - css_rect["height"]) > 0.1
    ):
        raise ThemeContractError(f"theme worker crop geometry differs: {surface}")
    document_left = css_rect["left"] + scroll_x
    document_top = css_rect["top"] + scroll_y
    crop_x = math.floor(document_left)
    crop_y = math.floor(document_top)
    crop_right = math.ceil(css_rect["right"] + scroll_x)
    crop_bottom = math.ceil(css_rect["bottom"] + scroll_y)
    if crop_x < 0 or crop_y < 0 or crop_right <= crop_x or crop_bottom <= crop_y:
        raise ThemeContractError(f"theme worker crop escaped document: {surface}")
    return {
        "selector": selector,
        "coordinateSpace": "full-page-css-pixels",
        "deviceScaleFactor": 1,
        "scrollOffset": {
            "x": round(scroll_x, 3),
            "y": round(scroll_y, 3),
        },
        "cssRect": {
            key: round(value, 3) for key, value in css_rect.items()
        },
        "crop": {
            "x": crop_x,
            "y": crop_y,
            "width": crop_right - crop_x,
            "height": crop_bottom - crop_y,
        },
    }


def collect_external_worker_theme_evidence(
    page: Any,
    *,
    viewport_name: str,
    viewport: tuple[int, int],
    browser_name: str,
    browser_version: str,
) -> Mapping[str, Any]:
    """Collect the real page/AX/style/pixel oracle inside the frozen worker.

    This function performs no filesystem writes.  The worker embeds the exact
    JSON result in its canonical raw sidecar and separately stages its existing
    full-page PNG; the coordinator later authenticates both before cropping.
    """

    if VIEWPORTS.get(viewport_name) != viewport:
        raise ThemeContractError("theme worker collector viewport differs")
    if browser_name != "chromium" or not isinstance(browser_version, str) or not browser_version:
        raise ThemeContractError("theme worker collector browser identity differs")
    from ui import _design

    builder = getattr(_design, "build_global_theme_css", None)
    if not callable(builder):
        raise ThemeContractError("production theme CSS builder is unavailable")
    validate_palette_contract(APPROVED_TOKENS, SURFACE_COLORS)
    validate_design_token_contract(_design)
    css = extract_theme_css(builder())
    validate_css_safety(css)
    validate_link_contract(css)
    records = validate_selector_contract(
        css, getattr(_design, "THEME_SELECTOR_CONTRACT", None)
    )
    contract_rows = _contract_manifest_rows(records)
    contract_payload = {
        "records": contract_rows,
        "owners": {
            selector: list(owners)
            for selector, owners in selector_owner_contract(records).items()
        },
        "important": sorted(
            [
                [record.selector, record.property]
                for record in records
                if record.important
            ]
        ),
    }
    selector_contract_sha256 = hashlib.sha256(
        canonical_json(contract_payload).encode("utf-8")
    ).hexdigest()
    _assert_gallery_ready(page)
    selector_evidence = _verify_selector_node_sets(page, records)
    _assert_signal_selector_isolation(page, records)
    selector_payload = {
        "browser": browser_name,
        "viewport": viewport_name,
        "selectors": dict(selector_evidence),
    }
    selector_payload["sha256"] = hashlib.sha256(
        canonical_json(selector_payload).encode("utf-8")
    ).hexdigest()

    surfaces: list[dict[str, Any]] = []
    for surface in SURFACE_COLORS:
        states = _surface_state_evidence(page, surface, viewport)
        overflow = _overflow_evidence(page, surface)
        page.evaluate("() => document.activeElement && document.activeElement.blur()")
        page.mouse.move(0, 0)
        surfaces.append(
            {
                "name": surface,
                "color": SURFACE_COLORS[surface],
                "geometry": dict(_surface_worker_crop_geometry(page, surface)),
                "states": states,
                "overflow": overflow,
            }
        )

    full_page = page.evaluate(
        "([minimumWidth, minimumHeight]) => ({"
        " width:Math.max(minimumWidth, document.documentElement.scrollWidth,"
        "   document.body ? document.body.scrollWidth : 0),"
        " height:Math.max(minimumHeight, document.documentElement.scrollHeight,"
        "   document.body ? document.body.scrollHeight : 0),"
        " deviceScaleFactor:window.devicePixelRatio})",
        arg=[viewport[0], viewport[1]],
    )
    if (
        not isinstance(full_page, Mapping)
        or full_page.get("deviceScaleFactor") != 1
        or not isinstance(full_page.get("width"), int)
        or not isinstance(full_page.get("height"), int)
        or full_page["width"] != viewport[0]
        or full_page["height"] < viewport[1]
    ):
        raise ThemeContractError("theme worker full-page geometry differs")
    case_contract = {
        "galleryCases": list(REQUIRED_GALLERY_CASES),
        "focusCases": list(FOCUS_CASES),
        "ownerCount": len(SURFACE_COLORS) * len(REQUIRED_GALLERY_CASES),
    }
    case_contract["sha256"] = hashlib.sha256(
        canonical_json(case_contract).encode("utf-8")
    ).hexdigest()
    payload: dict[str, Any] = {
        "schemaVersion": THEME_WORKER_EVIDENCE_SCHEMA,
        "browser": {"name": browser_name, "version": browser_version},
        "viewport": {
            "name": viewport_name,
            "width": viewport[0],
            "height": viewport[1],
            "deviceScaleFactor": 1,
        },
        "fullPage": {
            "width": full_page["width"],
            "height": full_page["height"],
            "deviceScaleFactor": 1,
        },
        "caseContract": case_contract,
        "selectorContractSha256": selector_contract_sha256,
        "selectorEvidence": selector_payload,
        "surfaces": surfaces,
        "sourceDigest": source_digest(),
    }
    payload["sha256"] = hashlib.sha256(
        canonical_json(payload).encode("utf-8")
    ).hexdigest()
    return payload


def verify_external_worker_theme_geometry_after_screenshot(
    page: Any,
    rich_evidence: Mapping[str, Any],
) -> None:
    """Require the screenshot to leave every measured crop coordinate unchanged."""

    rich = _exact_worker_mapping(
        rich_evidence,
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
        "theme worker post-screenshot evidence",
    )
    viewport = _exact_worker_mapping(
        rich["viewport"],
        {"name", "width", "height", "deviceScaleFactor"},
        "theme worker post-screenshot viewport",
    )
    surfaces = rich["surfaces"]
    if (
        not isinstance(surfaces, list)
        or len(surfaces) != len(SURFACE_COLORS)
    ):
        raise ThemeContractError("theme worker post-screenshot surfaces differ")
    for expected_name, raw_surface in zip(SURFACE_COLORS, surfaces, strict=True):
        surface = _exact_worker_mapping(
            raw_surface,
            {"name", "color", "geometry", "states", "overflow"},
            "theme worker post-screenshot surface",
        )
        if (
            surface["name"] != expected_name
            or dict(_surface_worker_crop_geometry(page, expected_name))
            != dict(surface["geometry"])
        ):
            raise ThemeContractError(
                f"theme worker geometry shifted during screenshot: {expected_name}"
            )
    observed_full_page = page.evaluate(
        "([minimumWidth, minimumHeight]) => ({"
        " width:Math.max(minimumWidth, document.documentElement.scrollWidth,"
        "   document.body ? document.body.scrollWidth : 0),"
        " height:Math.max(minimumHeight, document.documentElement.scrollHeight,"
        "   document.body ? document.body.scrollHeight : 0),"
        " deviceScaleFactor:window.devicePixelRatio})",
        arg=[viewport["width"], viewport["height"]],
    )
    if not isinstance(observed_full_page, Mapping) or dict(observed_full_page) != dict(
        rich["fullPage"]
    ):
        raise ThemeContractError("theme worker full-page geometry shifted during screenshot")


def _capture_surface(
    *,
    page: Any,
    owned: OwnedThemeRun,
    browser_name: str,
    browser_version: str,
    viewport_name: str,
    viewport: tuple[int, int],
    surface: str,
    selector_digest: str,
) -> Mapping[str, Any]:
    capture_id = f"{browser_name}-{viewport_name}-{surface}"
    start_digest = source_digest()
    state_evidence = _surface_state_evidence(page, surface, viewport)
    overflow = _overflow_evidence(page, surface)
    page.evaluate("() => document.activeElement && document.activeElement.blur()")
    page.mouse.move(0, 0)
    screenshot_path = owned.run_dir / f"{capture_id}.png"
    surface_locator = page.locator(f".st-key-ux1b_surface_{surface}")
    surface_locator.screenshot(
        path=str(screenshot_path),
        animations="disabled",
        caret="hide",
        scale="css",
        timeout=NAVIGATION_TIMEOUT_MS,
    )
    payload = screenshot_path.read_bytes()
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ThemeContractError(f"capture is not a PNG: {capture_id}")
    end_digest = source_digest()
    if start_digest != end_digest:
        raise ThemeContractError(f"source changed during capture: {capture_id}")
    return {
        "id": capture_id,
        "browser": browser_name,
        "browserVersion": browser_version,
        "viewport": {
            "name": viewport_name,
            "width": viewport[0],
            "height": viewport[1],
            "deviceScaleFactor": 1,
        },
        "surface": {"name": surface, "color": SURFACE_COLORS[surface]},
        "screenshot": safe_relative_output(screenshot_path),
        "screenshotSha256": hashlib.sha256(payload).hexdigest(),
        "screenshotBytes": len(payload),
        "selectorEvidenceDigest": selector_digest,
        "states": state_evidence,
        "overflow": overflow,
        "exception": None,
        "sourceDigestStart": start_digest,
        "sourceDigestEnd": end_digest,
        "status": "passed",
    }


def _default_run_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%Sz")
    return UX1B_ROOT / f"theme-states-{stamp}-{secrets.token_hex(4)}"


def create_owned_run(out_dir: Path | None) -> OwnedThemeRun:
    run_dir = (out_dir or _default_run_dir()).resolve()
    try:
        relative = run_dir.relative_to(UX1B_ROOT)
    except ValueError as exc:
        raise ThemeContractError("theme-state output must stay under the UX-1B namespace") from exc
    lowered_parts = {part.casefold() for part in relative.parts}
    if {"ux0", "ux1a"} & lowered_parts:
        raise ThemeContractError("theme-state output cannot use a historical namespace")
    if run_dir.exists() and any(run_dir.iterdir()):
        raise ThemeContractError("theme-state output directory must be new or empty")
    run_dir.mkdir(parents=True, exist_ok=True)
    run_id = run_dir.name
    if _CAPTURE_RE.fullmatch(run_id.replace(".", "_")) is None:
        raise ThemeContractError("theme-state run id is not stable")
    owner_path = run_dir / OWNER_FILE
    owner_path.write_text("quant-radar-ui-ux-ux1b-theme\n", encoding="utf-8")
    return OwnedThemeRun(
        run_dir=run_dir,
        manifest_path=run_dir / "manifest.json",
        log_path=run_dir / "streamlit.log",
        owner_path=owner_path,
        run_id=run_id,
    )


def _json_document(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(_json_document(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _atomic_terminal_manifest_commit(path: Path, value: Any) -> None:
    """Commit once, accepting an interrupt only when replace did not publish."""

    expected = _json_document(value)
    try:
        atomic_write_json(path, value)
    except (KeyboardInterrupt, Exception):
        try:
            committed = path.read_text(encoding="utf-8") == expected
        except (OSError, UnicodeError):
            committed = False
        if not committed:
            raise


def _commit_terminal_manifest(
    owned: OwnedThemeRun, manifest: dict[str, Any], code: int
) -> int:
    """Perform the sole terminal commit after capabilities and handlers retire."""

    try:
        _atomic_terminal_manifest_commit(owned.manifest_path, manifest)
    except KeyboardInterrupt as exc:
        if manifest.get("status") != "failed":
            manifest["status"] = "interrupted"
            manifest["interruption"] = _terminal_diagnostic(exc, owned)
            code = 130
        _atomic_terminal_manifest_commit(owned.manifest_path, manifest)
    except Exception as exc:
        if manifest.get("status") != "interrupted":
            manifest["status"] = "failed"
            manifest["finalizationError"] = _terminal_diagnostic(exc, owned)
            code = 1
        _atomic_terminal_manifest_commit(owned.manifest_path, manifest)
    return code


def _free_loopback_port() -> int:
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            listener.bind(("127.0.0.1", 0))
            port = int(listener.getsockname()[1])
        if port != 8000:
            return port


def _theme_directory_fd(path: Path) -> int:
    return os.open(
        path,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0),
    )


def _theme_directory_identity(named: os.stat_result, opened: os.stat_result) -> bool:
    return (
        stat.S_ISDIR(named.st_mode)
        and stat.S_ISDIR(opened.st_mode)
        and (named.st_dev, named.st_ino, named.st_uid)
        == (opened.st_dev, opened.st_ino, opened.st_uid)
    )


def _theme_stat_identity(observed: os.stat_result) -> tuple[int, int, int, int]:
    return (
        observed.st_dev,
        observed.st_ino,
        observed.st_uid,
        stat.S_IMODE(observed.st_mode),
    )


def _theme_directory_component_contract(
    name: str,
    observed: os.stat_result,
) -> tuple[str, int, int, int, int]:
    return (
        name,
        observed.st_dev,
        observed.st_ino,
        observed.st_uid,
        stat.S_IMODE(observed.st_mode),
    )


def _theme_component_matches_contract(
    observed: os.stat_result,
    contract: tuple[str, int, int, int, int],
) -> bool:
    return (
        stat.S_ISDIR(observed.st_mode)
        and (
            observed.st_dev,
            observed.st_ino,
            observed.st_uid,
            stat.S_IMODE(observed.st_mode),
        )
        == contract[1:]
    )


def _open_theme_directory_component(
    parent_fd: int,
    component: str,
    *,
    create: bool,
) -> int:
    if (
        not isinstance(component, str)
        or component in {"", ".", ".."}
        or "/" in component
        or "\\" in component
        or "\x00" in component
    ):
        raise ThemeContractError("theme output path contains an unsafe component")
    if create:
        try:
            os.mkdir(component, mode=0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
    try:
        named = os.stat(component, dir_fd=parent_fd, follow_symlinks=False)
        descriptor = os.open(
            component,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent_fd,
        )
    except OSError as exc:
        raise ThemeContractError("theme output directory component is unavailable") from exc
    opened = os.fstat(descriptor)
    if (
        not _theme_directory_identity(named, opened)
        or opened.st_uid != os.getuid()
        or stat.S_IMODE(opened.st_mode) & 0o022
    ):
        os.close(descriptor)
        raise ThemeContractError("theme output directory component is unsafe")
    return descriptor


def _open_theme_output_namespace(path: Path) -> ThemeOutputNamespace:
    destination = Path(os.path.abspath(os.path.expanduser(os.fspath(path))))
    try:
        relative = destination.relative_to(UX1B_ROOT)
    except ValueError as exc:
        raise ThemeContractError(
            "theme output must stay beneath .claude/ui_snapshots/ux1b"
        ) from exc
    if (
        not relative.parts
        or any(
            part in {"", ".", "..", "ux0", "ux1a", "recovery"}
            for part in relative.parts
        )
    ):
        raise ThemeContractError("theme output must use a new UX1B child")
    workspace_fd = _theme_directory_fd(WORKSPACE_ROOT)
    opened: list[int] = []
    base_contracts: list[tuple[str, int, int, int, int]] = []
    parent_contracts: list[tuple[str, int, int, int, int]] = []
    ux1b_fd = -1
    parent_fd = -1
    try:
        current = workspace_fd
        for component in (".claude", "ui_snapshots", "ux1b"):
            current = _open_theme_directory_component(
                current,
                component,
                create=True,
            )
            opened.append(current)
            base_contracts.append(
                _theme_directory_component_contract(
                    component,
                    os.fstat(current),
                )
            )
        ux1b_fd = opened.pop()
        for descriptor in reversed(opened):
            os.close(descriptor)
        opened.clear()
        parent_fd = os.dup(ux1b_fd)
        os.set_inheritable(parent_fd, False)
        for component in relative.parts[:-1]:
            child = _open_theme_directory_component(
                parent_fd,
                component,
                create=True,
            )
            os.close(parent_fd)
            parent_fd = child
            parent_contracts.append(
                _theme_directory_component_contract(
                    component,
                    os.fstat(parent_fd),
                )
            )
        return ThemeOutputNamespace(
            path=UX1B_ROOT.joinpath(*relative.parts),
            leaf_name=relative.parts[-1],
            workspace_fd=workspace_fd,
            workspace_contract=_theme_directory_component_contract(
                ".", os.fstat(workspace_fd)
            ),
            ux1b_fd=ux1b_fd,
            parent_fd=parent_fd,
            parent_components=tuple(relative.parts[:-1]),
            base_contracts=tuple(base_contracts),
            parent_contracts=tuple(parent_contracts),
        )
    except BaseException:
        for descriptor in reversed(opened):
            with contextlib.suppress(OSError):
                os.close(descriptor)
        for descriptor in (parent_fd, ux1b_fd, workspace_fd):
            if descriptor >= 0:
                with contextlib.suppress(OSError):
                    os.close(descriptor)
        raise


def _reauthenticate_theme_output_namespace(namespace: ThemeOutputNamespace) -> None:
    workspace_fd = _theme_directory_fd(WORKSPACE_ROOT)
    opened: list[int] = []
    try:
        if (
            namespace.workspace_contract[0] != "."
            or not _theme_component_matches_contract(
                os.fstat(workspace_fd), namespace.workspace_contract
            )
            or not _theme_component_matches_contract(
                os.fstat(namespace.workspace_fd), namespace.workspace_contract
            )
        ):
            raise ThemeContractError("retained theme workspace namespace changed")
        current = namespace.workspace_fd
        if tuple(contract[0] for contract in namespace.base_contracts) != (
            ".claude",
            "ui_snapshots",
            "ux1b",
        ):
            raise ThemeContractError("theme base component contract differs")
        for contract in namespace.base_contracts:
            current = _open_theme_directory_component(
                current,
                contract[0],
                create=False,
            )
            opened.append(current)
            if not _theme_component_matches_contract(os.fstat(current), contract):
                raise ThemeContractError("theme base output ancestor changed")
        if not _theme_directory_identity(
            os.fstat(current), os.fstat(namespace.ux1b_fd)
        ):
            raise ThemeContractError("retained theme UX1B namespace changed")
        for descriptor in reversed(opened):
            os.close(descriptor)
        opened.clear()
        current = namespace.ux1b_fd
        if tuple(contract[0] for contract in namespace.parent_contracts) != (
            namespace.parent_components
        ):
            raise ThemeContractError("theme parent component contract differs")
        for contract in namespace.parent_contracts:
            current = _open_theme_directory_component(
                current,
                contract[0],
                create=False,
            )
            opened.append(current)
            if not _theme_component_matches_contract(os.fstat(current), contract):
                raise ThemeContractError("theme output ancestor changed")
        if not _theme_directory_identity(
            os.fstat(current), os.fstat(namespace.parent_fd)
        ):
            raise ThemeContractError("retained theme output parent changed")
    finally:
        for descriptor in reversed(opened):
            with contextlib.suppress(OSError):
                os.close(descriptor)
        os.close(workspace_fd)


def _validate_theme_output_leaf(namespace: ThemeOutputNamespace) -> None:
    _reauthenticate_theme_output_namespace(namespace)
    try:
        named = os.stat(
            namespace.leaf_name,
            dir_fd=namespace.parent_fd,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return
    descriptor = -1
    try:
        descriptor = os.open(
            namespace.leaf_name,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=namespace.parent_fd,
        )
        opened = os.fstat(descriptor)
        if (
            not _theme_directory_identity(named, opened)
            or opened.st_uid != os.getuid()
            or stat.S_IMODE(opened.st_mode) & 0o022
            or bool(os.listdir(descriptor))
        ):
            raise ThemeContractError("theme output directory is not empty and safe")
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _theme_write_private_file(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0),
        0o600,
    )
    try:
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise ThemeContractError("theme private-file write was short")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _theme_canonical_ndjson(value: Mapping[str, Any]) -> bytes:
    try:
        return (
            json.dumps(
                dict(value),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ThemeContractError("theme worker request is not canonical JSON") from exc


def _authenticate_theme_capture_stack(
    workspace_fd: int,
) -> tuple[dict[str, Any], Any, str]:
    evidence = _evidence_api()
    relative_path = UX1B_CAPTURE_STACK_CONTRACT_PATH.relative_to(
        WORKSPACE_ROOT
    ).as_posix()
    try:
        contract, catalog, sha256 = evidence.authenticate_capture_stack_contract(
            workspace_fd,
            relative_path,
            workspace_root_fd=workspace_fd,
            expected_owner=os.getuid(),
        )
    except Exception as exc:
        raise ThemeContractError(
            "theme capture-stack contract failed descriptor authentication"
        ) from exc
    if tuple(member["path"] for member in contract["members"]) != tuple(
        sorted(evidence.CAPTURE_STACK_MEMBERS)
    ):
        raise ThemeContractError("theme capture-stack member set differs")
    return contract, catalog, sha256


def _open_theme_stale_final_root(claim: Any) -> int | None:
    descriptor = -1
    try:
        named = os.stat(
            "final",
            dir_fd=claim.root.descriptor,
            follow_symlinks=False,
        )
        descriptor = os.open(
            "final",
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=claim.root.descriptor,
        )
        opened = os.fstat(descriptor)
        if (
            not _theme_directory_identity(named, opened)
            or opened.st_uid != os.getuid()
            or stat.S_IMODE(opened.st_mode) != 0o700
        ):
            os.close(descriptor)
            return None
        return descriptor
    except OSError as exc:
        if descriptor >= 0:
            with contextlib.suppress(OSError):
                os.close(descriptor)
        if exc.errno in {
            errno.ENOENT,
            errno.ENOTDIR,
            errno.EACCES,
            errno.EPERM,
            errno.ELOOP,
        }:
            return None
        raise


def _theme_stale_candidate_is_formal(evidence: Any, final_fd: int) -> bool:
    try:
        contract = evidence.freeze_artifact_contract(
            final_fd,
            "manifest.json",
            expected_owner=os.getuid(),
            max_bytes=evidence.MAX_MANIFEST_BYTES,
        )
        with evidence.open_authenticated_artifact(final_fd, contract) as artifact:
            chunks: list[bytes] = []
            offset = 0
            while offset < contract.leaf.size:
                chunk = os.pread(
                    artifact.descriptor,
                    min(1024 * 1024, contract.leaf.size - offset),
                    offset,
                )
                if not chunk:
                    return False
                chunks.append(chunk)
                offset += len(chunk)
        raw = b"".join(chunks)
        document = json.loads(raw.decode("utf-8", errors="strict"))
        if (
            not isinstance(document, dict)
            or raw != _theme_canonical_ndjson(document)
            or document.get("status") not in {"running", "finalizing"}
        ):
            return False
        identity = evidence.classify_formal_stale_run_identity(document)
        return (
            identity["mode"] == "ux1b-theme"
            and identity["phase"] == "posttheme"
            and identity["fixtureEntrypoint"]
            == "scripts/ui_ux_theme_fixture_app.py"
            and identity["expectedCaptureCount"] == 3
        )
    except (
        evidence.EvidenceContractError,
        UnicodeError,
        json.JSONDecodeError,
    ):
        return False


def _recover_stale_theme_runtimes(
    evidence: Any,
    isolation: Any,
    *,
    namespace: ThemeOutputNamespace,
    temp_parent: Path | None = None,
) -> tuple[Mapping[str, Any], ...]:
    claims = isolation.claim_stale_owned_run_roots(
        temp_parent or Path(tempfile.gettempdir()),
        prefix="quant-radar-ux1b-theme-",
        max_candidates=isolation.MAX_STALE_OWNED_RUN_CANDIDATES,
    )
    if not claims:
        return ()
    recovery_fd = -1
    records: list[Mapping[str, Any]] = []
    try:
        _reauthenticate_theme_output_namespace(namespace)
        recovery_fd = _open_theme_directory_component(
            namespace.ux1b_fd,
            "recovery",
            create=True,
        )
        recovery_identity = _theme_stat_identity(os.fstat(recovery_fd))

        def reauthenticate_recovery() -> None:
            _reauthenticate_theme_output_namespace(namespace)
            fresh_fd = _open_theme_directory_component(
                namespace.ux1b_fd,
                "recovery",
                create=False,
            )
            try:
                if (
                    _theme_stat_identity(os.fstat(recovery_fd))
                    != recovery_identity
                    or _theme_stat_identity(os.fstat(fresh_fd))
                    != recovery_identity
                ):
                    raise ThemeContractError(
                        "theme recovery directory identity changed"
                    )
            finally:
                os.close(fresh_fd)

        for claim in claims:
            try:
                final_fd = _open_theme_stale_final_root(claim)
                if final_fd is None:
                    continue
                try:
                    if not _theme_stale_candidate_is_formal(evidence, final_fd):
                        continue
                    reauthenticate_recovery()
                    record = evidence.record_stale_nonterminal(
                        final_fd,
                        "manifest.json",
                        recovery_fd,
                        f"stale-{claim.root.leaf_name}.json",
                        expected_owner=os.getuid(),
                    )
                    reauthenticate_recovery()
                finally:
                    os.close(final_fd)
                records.append(record)
            finally:
                claim.close()
        return tuple(records)
    finally:
        for claim in claims:
            claim.close()
        if recovery_fd >= 0:
            os.close(recovery_fd)


def _prepare_theme_formal_runtime(
    *,
    destination: Path,
    run_id: str,
) -> ThemeFormalRuntime:
    evidence = _evidence_api()
    isolation = _isolation_api()
    namespace: ThemeOutputNamespace | None = None
    runtime: Any | None = None
    lease: Any | None = None
    final_fd = -1
    browser_fd = -1
    try:
        namespace = _open_theme_output_namespace(destination)
        _validate_theme_output_leaf(namespace)
        _recover_stale_theme_runtimes(
            evidence,
            isolation,
            namespace=namespace,
        )
        runtime = isolation.create_owned_run_root(
            Path(tempfile.gettempdir()),
            prefix="quant-radar-ux1b-theme-",
        )
        lease = isolation.acquire_owned_run_lease(runtime)
        final_root = runtime.path / "final"
        app_root = runtime.path / "app"
        browser_root = runtime.path / "browser"
        for root in (final_root, app_root, browser_root):
            root.mkdir(mode=0o700)
        final_fd = _theme_directory_fd(final_root)
        browser_fd = _theme_directory_fd(browser_root)
        lifecycle = evidence.ManifestLifecycle(
            final_fd,
            "manifest.json",
            base_document={
                "schemaVersion": evidence.EVIDENCE_SCHEMA,
                "mode": "ux1b-theme",
                "phase": "posttheme",
                "runId": run_id,
                "fixtureEntrypoint": "scripts/ui_ux_theme_fixture_app.py",
                "expectedCaptureCount": 3,
            },
        )
        return ThemeFormalRuntime(
            namespace=namespace,
            runtime=runtime,
            lease=lease,
            final_root=final_root,
            app_root=app_root,
            browser_root=browser_root,
            final_root_fd=final_fd,
            browser_root_fd=browser_fd,
            lifecycle=lifecycle,
        )
    except BaseException:
        for descriptor in (browser_fd, final_fd):
            if descriptor >= 0:
                with contextlib.suppress(OSError):
                    os.close(descriptor)
        if runtime is not None:
            try:
                isolation.remove_owned_run_root(runtime)
            except BaseException:
                with contextlib.suppress(BaseException):
                    runtime.close()
        if lease is not None:
            with contextlib.suppress(BaseException):
                lease.close()
        if namespace is not None:
            namespace.close()
        raise


def _release_theme_formal_runtime(owned: ThemeFormalRuntime) -> BaseException | None:
    isolation = _isolation_api()
    first: BaseException | None = None
    for descriptor in (owned.browser_root_fd, owned.final_root_fd):
        try:
            os.close(descriptor)
        except BaseException as exc:
            first = first or exc
    try:
        first = first or owned.namespace.close()
    except BaseException as exc:
        first = first or exc
    try:
        isolation.remove_owned_run_root(owned.runtime)
    except BaseException as exc:
        first = first or exc
        with contextlib.suppress(BaseException):
            owned.runtime.close()
    try:
        owned.lease.close()
    except BaseException as exc:
        first = first or exc
    return first


def _theme_destination_is_retained_root(
    namespace: ThemeOutputNamespace,
    retained: os.stat_result,
) -> bool:
    descriptor = -1
    try:
        _reauthenticate_theme_output_namespace(namespace)
        named = os.stat(
            namespace.leaf_name,
            dir_fd=namespace.parent_fd,
            follow_symlinks=False,
        )
        descriptor = os.open(
            namespace.leaf_name,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=namespace.parent_fd,
        )
        opened = os.fstat(descriptor)
        return _theme_directory_identity(named, opened) and (
            opened.st_dev,
            opened.st_ino,
            opened.st_uid,
        ) == (retained.st_dev, retained.st_ino, retained.st_uid)
    except (OSError, ThemeContractError):
        return False
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _export_theme_final_root(owned: ThemeFormalRuntime) -> None:
    namespace = owned.namespace
    _reauthenticate_theme_output_namespace(namespace)
    retained = os.fstat(owned.final_root_fd)
    named = os.stat(
        "final",
        dir_fd=owned.runtime.descriptor,
        follow_symlinks=False,
    )
    if not _theme_directory_identity(named, retained) or retained.st_uid != os.getuid():
        raise ThemeContractError("theme final root identity differs before export")
    try:
        existing = os.stat(
            namespace.leaf_name,
            dir_fd=namespace.parent_fd,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        existing = None
    if existing is not None:
        descriptor = os.open(
            namespace.leaf_name,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=namespace.parent_fd,
        )
        try:
            opened = os.fstat(descriptor)
            if (
                not _theme_directory_identity(existing, opened)
                or opened.st_uid != os.getuid()
                or bool(os.listdir(descriptor))
            ):
                raise ThemeContractError("theme output leaf is not empty and owned")
        finally:
            os.close(descriptor)
        os.rmdir(namespace.leaf_name, dir_fd=namespace.parent_fd)
    renamed = False
    try:
        os.rename(
            "final",
            namespace.leaf_name,
            src_dir_fd=owned.runtime.descriptor,
            dst_dir_fd=namespace.parent_fd,
        )
        renamed = True
        if not _theme_destination_is_retained_root(namespace, retained):
            raise ThemeContractError("theme export destination identity differs")
        os.fsync(owned.runtime.descriptor)
        os.fsync(namespace.parent_fd)
    except BaseException as exc:
        if renamed and _theme_destination_is_retained_root(namespace, retained):
            try:
                os.rename(
                    namespace.leaf_name,
                    "final",
                    src_dir_fd=namespace.parent_fd,
                    dst_dir_fd=owned.runtime.descriptor,
                )
                os.fsync(namespace.parent_fd)
                os.fsync(owned.runtime.descriptor)
            except BaseException:
                pass
        raise ThemeContractError("theme finalizing export failed or was revoked") from exc


def _read_theme_manifest(root_fd: int) -> dict[str, Any]:
    evidence = _evidence_api()
    raw = _read_descriptor_authenticated_worker_artifact(
        evidence,
        root_fd,
        "manifest.json",
        maximum=evidence.MAX_MANIFEST_BYTES,
        label="theme manifest",
    )
    try:
        document = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ThemeContractError("theme manifest is unreadable") from exc
    if not isinstance(document, dict):
        raise ThemeContractError("theme manifest is not an object")
    return document


def _make_theme_manifest_unreferenceable(root_fd: int) -> None:
    quarantine = f".unreferenceable-manifest-{secrets.token_hex(12)}.json"
    try:
        os.rename(
            "manifest.json",
            quarantine,
            src_dir_fd=root_fd,
            dst_dir_fd=root_fd,
        )
        os.fsync(root_fd)
    except OSError as exc:
        raise ThemeContractError(
            "untrusted theme passed manifest could not be quarantined"
        ) from exc


@contextlib.contextmanager
def _theme_browser_worker_session(
    app_port: int,
) -> Iterable[ThemeBrowserWorkerSession]:
    """Calibrate one private mirror-backed browser-worker session.

    Calibration must happen before Streamlit binds ``app_port`` because the
    app profile's positive probe temporarily owns that exact endpoint.
    """

    isolation = _isolation_api()
    parent = Path(tempfile.gettempdir()).expanduser().absolute()
    try:
        with isolation.owned_run_root(
            parent, prefix="quant-radar-ux1b-theme-"
        ) as run_root:
            policy = isolation.SourceMirrorPolicy(
                include=_expanded_ux1b_source_mirror_policy(),
                exclude=(
                    ".DS_Store",
                    ".mypy_cache",
                    ".pytest_cache",
                    ".ruff_cache",
                    "__pycache__",
                ),
            )
            workspace_fd = _theme_directory_fd(WORKSPACE_ROOT)
            try:
                mirror = isolation.build_source_mirror(
                    workspace_root_fd=workspace_fd,
                    run_root=run_root.path / "mirror-build",
                    policy=policy,
                )
            finally:
                os.close(workspace_fd)
            isolation.authenticate_source_mirror(
                mirror, expected_digest=mirror.digest
            )
            app_root = run_root.path / "app"
            browser_root = run_root.path / "browser"
            final_root = run_root.path / "final"
            for role_root in (app_root, browser_root, final_root):
                os.mkdir(role_root, mode=0o700)

            browser_executable, _browser_sha256 = (
                isolation._playwright_chromium_identity()
            )
            browser_cache = isolation._playwright_browser_cache_root(
                browser_executable
            )
            denied_port = _free_loopback_port()
            while denied_port == app_port:
                denied_port = _free_loopback_port()
            contract = isolation.DarwinIsolationContract(
                workspace_root=WORKSPACE_ROOT,
                source_root=mirror.source_root,
                app_writable_root=app_root,
                browser_writable_root=browser_root,
                final_evidence_root=final_root,
                python_executable=Path(sys.executable).expanduser().absolute(),
                python_runtime_roots=(Path(sys.prefix).resolve(),),
                browser_executable=browser_executable,
                browser_runtime_roots=(browser_cache,),
                production_probe_path=WORKSPACE_ROOT / "app.py",
                app_port=app_port,
                denied_port=denied_port,
            )
            profiles = isolation.build_darwin_profiles(contract)
            calibration = isolation.calibrate_darwin_profiles(
                contract, profiles=profiles
            )
            isolation.authenticate_source_mirror(
                mirror, expected_digest=mirror.digest
            )
            environment = isolation.build_child_environment(
                role="browser",
                source_root=mirror.source_root,
                writable_root=browser_root,
                inherited=os.environ,
                python_runtime_roots=contract.python_runtime_roots,
            )
            yield ThemeBrowserWorkerSession(
                session_id=f"theme-{secrets.token_hex(12)}",
                source_root=mirror.source_root,
                browser_root=browser_root,
                mirror_digest=mirror.digest,
                contract=contract,
                profiles=profiles,
                # Keep the exact registered object: calibrated launch grants
                # reject byte-identical copies without live provenance.
                calibration=calibration,
                environment=MappingProxyType(dict(environment)),
            )
    except isolation.DependencyUnavailable as exc:
        raise DependencyUnavailable(str(exc)) from exc


def _validate_theme_network_contract(contract: ThemeNetworkContract) -> None:
    ports = (contract.streamlit_port, contract.deny_proxy_port)
    if (
        len(set(ports)) != 2
        or 8000 in ports
        or any(isinstance(port, bool) or not 1 <= int(port) <= 65535 for port in ports)
    ):
        raise ThemeContractError("theme child requires two distinct owned non-API ports")


def is_allowed_python_endpoint(
    host: Any,
    port: Any,
    contract: ThemeNetworkContract,
) -> bool:
    """Accept only the literal owned IPv4 host and either exact owned port."""

    _validate_theme_network_contract(contract)
    if isinstance(host, bytes):
        try:
            host = host.decode("ascii")
        except UnicodeDecodeError:
            return False
    try:
        numeric_port = int(port)
    except (TypeError, ValueError):
        return False
    return str(host) == "127.0.0.1" and numeric_port in {
        contract.streamlit_port,
        contract.deny_proxy_port,
    }


def _safe_socket_target(host: Any, port: Any) -> str:
    if isinstance(host, bytes):
        host = host.decode("ascii", errors="replace")
    raw_label = str(host).strip().casefold()
    label = (
        raw_label
        if raw_label in {"127.0.0.1", "localhost", "::1", "[::1]"}
        else "<external>"
    )
    try:
        return f"{label}:{int(port)}"
    except (TypeError, ValueError):
        return f"{label}:invalid"


def _append_child_guard_event(
    path: Path,
    *,
    kind: str,
    host: Any,
    port: Any,
    allowed: bool,
) -> None:
    record = canonical_json({
        "allowed": bool(allowed),
        "kind": str(kind),
        "target": _safe_socket_target(host, port),
    }).encode("utf-8") + b"\n"
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, record)
    finally:
        os.close(descriptor)


def install_theme_child_network_guard() -> None:
    """Install the gallery child's exact-endpoint outbound guard pre-Streamlit."""

    sentinel = "_quant_radar_ux1b_theme_network_guard"
    if getattr(socket, sentinel, False):
        return
    required = {
        _CHILD_GUARD_PATH: os.environ.get(_CHILD_GUARD_PATH),
        _CHILD_STREAMLIT_PORT: os.environ.get(_CHILD_STREAMLIT_PORT),
        _CHILD_DENY_PROXY_PORT: os.environ.get(_CHILD_DENY_PROXY_PORT),
    }
    if not all(required.values()):
        if os.environ.get("QUANT_RADAR_UX1B_THEME_DOM_PROBE") == "1":
            return
        raise ThemeContractError("theme fixture child network contract is missing")
    try:
        contract = ThemeNetworkContract(
            int(required[_CHILD_STREAMLIT_PORT] or ""),
            int(required[_CHILD_DENY_PROXY_PORT] or ""),
        )
    except ValueError as exc:
        raise ThemeContractError("theme fixture child ports are invalid") from exc
    _validate_theme_network_contract(contract)
    guard_path = Path(required[_CHILD_GUARD_PATH] or "")
    if not guard_path.is_absolute() or not guard_path.parent.is_dir():
        raise ThemeContractError("theme fixture guard path is not an owned absolute path")

    original_socket = socket.socket
    original_getaddrinfo = socket.getaddrinfo
    original_gethostbyaddr = socket.gethostbyaddr
    original_gethostbyname = socket.gethostbyname
    original_gethostbyname_ex = socket.gethostbyname_ex
    original_getnameinfo = socket.getnameinfo
    original_create_connection = socket.create_connection

    def require(host: Any, port: Any, kind: str) -> None:
        allowed = is_allowed_python_endpoint(host, port, contract)
        _append_child_guard_event(
            guard_path, kind=kind, host=host, port=port, allowed=allowed
        )
        if not allowed:
            raise ThemeChildNetworkDenied(
                "UX-1B theme fixture blocked an unowned network destination"
            )

    @functools.wraps(original_getaddrinfo)
    def guarded_getaddrinfo(host, port, *args, **kwargs):
        flags = int(kwargs.get("flags", args[3] if len(args) > 3 else 0) or 0)
        if flags & getattr(socket, "AI_PASSIVE", 0):
            return original_getaddrinfo(host, port, *args, **kwargs)
        require(host, port, "dns")
        return original_getaddrinfo(host, port, *args, **kwargs)

    def deny_portless_dns(kind: str, host: Any) -> None:
        _append_child_guard_event(
            guard_path, kind=kind, host=host, port=None, allowed=False
        )
        raise ThemeChildNetworkDenied(
            "UX-1B theme fixture blocked portless DNS resolution"
        )

    @functools.wraps(original_gethostbyname)
    def guarded_gethostbyname(host):
        deny_portless_dns("dns", host)

    @functools.wraps(original_gethostbyname_ex)
    def guarded_gethostbyname_ex(host):
        deny_portless_dns("dns", host)

    @functools.wraps(original_gethostbyaddr)
    def guarded_gethostbyaddr(host):
        deny_portless_dns("dns_reverse", host)

    @functools.wraps(original_getnameinfo)
    def guarded_getnameinfo(sockaddr, *args, **kwargs):
        host = sockaddr[0] if isinstance(sockaddr, tuple) and sockaddr else sockaddr
        port = sockaddr[1] if isinstance(sockaddr, tuple) and len(sockaddr) > 1 else None
        require(host, port, "dns_reverse")
        return original_getnameinfo(sockaddr, *args, **kwargs)

    @functools.wraps(original_create_connection)
    def guarded_create_connection(address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) and address else address
        port = address[1] if isinstance(address, tuple) and len(address) > 1 else None
        require(host, port, "connect")
        return original_create_connection(address, *args, **kwargs)

    class GuardedSocket(original_socket):
        def _guard(self, address: Any, kind: str) -> None:
            if self.family == getattr(socket, "AF_UNIX", object()):
                return
            host = address[0] if isinstance(address, tuple) and address else address
            port = address[1] if isinstance(address, tuple) and len(address) > 1 else None
            require(host, port, kind)

        def connect(self, address):
            self._guard(address, "connect")
            return super().connect(address)

        def connect_ex(self, address):
            self._guard(address, "connect")
            return super().connect_ex(address)

        def sendto(self, data, *args):
            if args:
                self._guard(args[-1], "sendto")
            return super().sendto(data, *args)

    GuardedSocket.__name__ = "GuardedThemeSocket"
    setattr(socket, sentinel, True)
    socket.socket = GuardedSocket
    socket.getaddrinfo = guarded_getaddrinfo
    socket.gethostbyaddr = guarded_gethostbyaddr
    socket.gethostbyname = guarded_gethostbyname
    socket.gethostbyname_ex = guarded_gethostbyname_ex
    socket.getnameinfo = guarded_getnameinfo
    socket.create_connection = guarded_create_connection


def _theme_child_environment(
    owned: OwnedThemeRun,
    contract: ThemeNetworkContract,
) -> dict[str, str]:
    _validate_theme_network_contract(contract)
    private_root = owned.run_dir / "fixture-root"
    private_tmp = private_root / "tmp"
    for path in (
        private_root,
        private_root / ".cache",
        private_root / ".config",
        private_root / ".local" / "share",
        private_tmp,
    ):
        path.mkdir(parents=True, exist_ok=True)
    guard_path = owned.run_dir / "python-socket-attempts.jsonl"
    guard_path.touch(mode=0o600, exist_ok=True)
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in _CHILD_ENV_KEYS or key.startswith("LC_")
    }
    proxy = f"http://127.0.0.1:{contract.deny_proxy_port}"
    environment.update({
        "HOME": str(private_root),
        "XDG_CACHE_HOME": str(private_root / ".cache"),
        "XDG_CONFIG_HOME": str(private_root / ".config"),
        "XDG_DATA_HOME": str(private_root / ".local" / "share"),
        "TMPDIR": str(private_tmp),
        "TMP": str(private_tmp),
        "TEMP": str(private_tmp),
        "NO_PROXY": "127.0.0.1",
        "no_proxy": "127.0.0.1",
        "PYTHONPATH": str(ROOT),
        "PYTHONUNBUFFERED": "1",
        "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
        "TZ": "UTC",
        _CHILD_GUARD_PATH: str(guard_path),
        _CHILD_STREAMLIT_PORT: str(contract.streamlit_port),
        _CHILD_DENY_PROXY_PORT: str(contract.deny_proxy_port),
        "HTTP_PROXY": proxy,
        "HTTPS_PROXY": proxy,
        "ALL_PROXY": proxy,
        "http_proxy": proxy,
        "https_proxy": proxy,
        "all_proxy": proxy,
    })
    leaked = sorted(key for key in environment if _CREDENTIAL_ENV_RE.search(key))
    if leaked:
        raise ThemeContractError(f"credential-like child environment keys leaked: {leaked!r}")
    return environment


def _child_environment_evidence(
    environment: Mapping[str, str], owned: OwnedThemeRun
) -> Mapping[str, Any]:
    private_root = owned.run_dir / "fixture-root"
    private_paths = {
        "home": environment.get("HOME"),
        "cache": environment.get("XDG_CACHE_HOME"),
        "config": environment.get("XDG_CONFIG_HOME"),
        "data": environment.get("XDG_DATA_HOME"),
        "tmp": environment.get("TMPDIR"),
    }
    expected_paths = {
        "home": private_root,
        "cache": private_root / ".cache",
        "config": private_root / ".config",
        "data": private_root / ".local" / "share",
        "tmp": private_root / "tmp",
    }
    private = all(
        value == str(expected_paths[key]) and expected_paths[key].is_dir()
        for key, value in private_paths.items()
    )
    credential_keys = sorted(key for key in environment if _CREDENTIAL_ENV_RE.search(key))
    proxy_values = {
        environment.get(key)
        for key in (
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
            "http_proxy", "https_proxy", "all_proxy",
        )
    }
    expected_proxy = f"http://127.0.0.1:{environment[_CHILD_DENY_PROXY_PORT]}"
    inherited_keys = {
        key for key in os.environ
        if key in _CHILD_ENV_KEYS or key.startswith("LC_")
    }
    expected_keys = inherited_keys | set(_THEME_FIXED_CHILD_KEYS)
    return {
        "allowlistApplied": set(environment) == expected_keys,
        "credentialLikeKeys": credential_keys,
        "credentialFree": not credential_keys,
        "environmentKeyCount": len(environment),
        "environmentKeys": sorted(environment),
        "privateDirectories": private,
        "privatePaths": {
            key: safe_relative_output(Path(value))
            for key, value in private_paths.items() if value is not None
        },
        "proxyContractExact": proxy_values == {expected_proxy},
    }


def _read_child_guard_evidence(path: Path) -> Mapping[str, Any]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ThemeContractError("theme child socket evidence is unreadable") from exc
    rows: list[Mapping[str, Any]] = []
    for index, raw in enumerate(payload.splitlines()):
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ThemeContractError(
                f"theme child socket evidence line {index + 1} is malformed"
            ) from exc
        if (
            not isinstance(row, Mapping)
            or set(row) != {"allowed", "kind", "target"}
            or not isinstance(row["allowed"], bool)
            or not isinstance(row["kind"], str)
            or not isinstance(row["target"], str)
        ):
            raise ThemeContractError("theme child socket evidence schema differs")
        rows.append(dict(row))
    return {
        "path": safe_relative_output(path),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "attemptCount": len(rows),
        "allowedAttemptCount": sum(bool(row["allowed"]) for row in rows),
        "blockedAttemptCount": sum(not bool(row["allowed"]) for row in rows),
        "attempts": rows,
    }


def _safe_proxy_attempt_evidence(
    attempts: Iterable[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    result: list[Mapping[str, Any]] = []
    for raw in attempts:
        request = str(raw.get("request", ""))
        method = request.split(maxsplit=1)[0].upper() if request else "UNKNOWN"
        if re.fullmatch(r"[A-Z]{1,16}", method) is None:
            method = "UNKNOWN"
        result.append({
            "bytes": max(0, int(raw.get("bytes", 0))),
            "method": method,
        })
    return result


def _record_server_attempt_evidence(
    manifest: dict[str, Any], server: OwnedThemeServer
) -> tuple[list[Mapping[str, Any]], Mapping[str, Any]]:
    proxy_attempts = _safe_proxy_attempt_evidence(server.deny_proxy.attempts())
    socket_evidence = _read_child_guard_evidence(server.guard_path)
    server_manifest = manifest.get("server")
    if not isinstance(server_manifest, dict):
        raise ThemeContractError("theme server manifest is unavailable")
    server_manifest["denyProxyAttemptCount"] = len(proxy_attempts)
    server_manifest["denyProxyAttempts"] = proxy_attempts
    server_manifest["pythonSocketGuard"] = dict(socket_evidence)
    server_manifest["terminated"] = server.process.poll() is not None
    server_manifest["returnCode"] = server.process.poll()
    return proxy_attempts, socket_evidence


def _log_tail(path: Path, limit: int = 8_000) -> str:
    try:
        payload = path.read_bytes()[-limit:]
    except OSError:
        return ""
    return payload.decode("utf-8", errors="replace")


def _wait_for_owned_server(process: subprocess.Popen[bytes], port: int, log_path: Path) -> None:
    deadline = time.monotonic() + 30.0
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    health = f"http://127.0.0.1:{port}/_stcore/health"
    while time.monotonic() < deadline:
        code = process.poll()
        if code is not None:
            raise ServerExited(
                f"owned Streamlit gallery exited with {code}: {_log_tail(log_path)!r}"
            )
        try:
            with opener.open(health, timeout=0.5) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError, TimeoutError):
            pass
        time.sleep(0.05)
    raise ServerExited(f"owned Streamlit gallery health timed out: {_log_tail(log_path)!r}")


def _terminate_owned_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        group = os.getpgid(process.pid)
    except (AttributeError, ProcessLookupError):
        group = None
    try:
        if group is not None:
            os.killpg(group, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        if group is not None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(group, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=5.0)
    except ProcessLookupError:
        pass


@contextlib.contextmanager
def _owned_gallery_server(
    owned: OwnedThemeRun, *, port: int | None = None
) -> Iterable[OwnedThemeServer]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts import ui_ux_snapshot_matrix as snapshot_runner

    deny_proxy = snapshot_runner.OwnedDenyProxy()
    if port is not None:
        for _attempt in range(16):
            if deny_proxy.port != port:
                break
            deny_proxy.close()
            deny_proxy = snapshot_runner.OwnedDenyProxy()
        else:
            deny_proxy.close()
            raise ThemeContractError(
                "deny proxy repeatedly claimed the preselected gallery port"
            )
    process: subprocess.Popen[bytes] | None = None
    try:
        if port is None:
            while True:
                port = _free_loopback_port()
                if port != deny_proxy.port:
                    break
        elif (
            isinstance(port, bool)
            or not isinstance(port, int)
            or not 1 <= port <= 65535
            or port == 8000
        ):
            raise ThemeContractError(
                "preselected gallery port conflicts with the exact network contract"
            )
        contract = ThemeNetworkContract(port, deny_proxy.port)
        environment = _theme_child_environment(owned, contract)
        bootstrap = (
            "from scripts.ui_ux_theme_matrix import install_theme_child_network_guard;"
            "install_theme_child_network_guard();"
            "from streamlit.web.cli import main;"
            "raise SystemExit(main())"
        )
        command = [
            sys.executable,
            "-c",
            bootstrap,
            "run",
            str(FIXTURE_APP),
            "--server.address=127.0.0.1",
            f"--server.port={port}",
            "--server.headless=true",
            "--server.fileWatcherType=none",
            "--server.runOnSave=false",
            "--browser.gatherUsageStats=false",
        ]
        if sys.platform == "darwin":
            sandbox = Path("/usr/bin/sandbox-exec")
            if not sandbox.is_file():
                raise DependencyUnavailable(
                    "Darwin UX-1B theme gallery requires sandbox-exec"
                )
            try:
                profile = snapshot_runner.build_darwin_sandbox_profile(contract)
            except Exception as exc:
                raise ThemeContractError(
                    "theme gallery exact-two-port sandbox profile failed"
                ) from exc
            command = [str(sandbox), "-p", profile, *command]

        descriptor = os.open(
            owned.log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600
        )
        os.chmod(owned.log_path, 0o600)
        with os.fdopen(descriptor, "ab", buffering=0) as log:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            _wait_for_owned_server(process, port, owned.log_path)
            try:
                calibration = snapshot_runner.calibrate_darwin_sandbox_contract(
                    contract
                )
            except snapshot_runner.DependencyUnavailable as exc:
                raise DependencyUnavailable(str(exc)) from exc
            except Exception as exc:
                raise ThemeContractError(
                    "theme gallery exact-two-port sandbox calibration failed"
                ) from exc
            if sys.platform == "darwin":
                if not deny_proxy.wait_for_attempts(1):
                    raise ThemeContractError(
                        "sandbox calibration did not reach the owned deny proxy"
                    )
                deny_proxy.reset()
            yield OwnedThemeServer(
                port=port,
                process=process,
                deny_proxy=deny_proxy,
                guard_path=Path(environment[_CHILD_GUARD_PATH]),
                child_environment=MappingProxyType(dict(environment)),
                sandbox_calibration=MappingProxyType(dict(calibration)),
            )
    finally:
        cleanup_interrupt: KeyboardInterrupt | None = None
        cleanup_failure: Exception | None = None
        if process is not None:
            try:
                _terminate_owned_process(process)
            except KeyboardInterrupt as exc:
                cleanup_interrupt = exc
                try:
                    _terminate_owned_process(process)
                except KeyboardInterrupt as retry_exc:
                    cleanup_interrupt = cleanup_interrupt or retry_exc
                except Exception as retry_exc:
                    cleanup_failure = retry_exc
            except Exception as exc:
                cleanup_failure = exc
                try:
                    _terminate_owned_process(process)
                except KeyboardInterrupt as retry_exc:
                    cleanup_interrupt = retry_exc
                except Exception:
                    pass
        try:
            deny_proxy.close()
        except KeyboardInterrupt as exc:
            cleanup_interrupt = cleanup_interrupt or exc
            try:
                deny_proxy.close()
            except KeyboardInterrupt as retry_exc:
                cleanup_interrupt = cleanup_interrupt or retry_exc
            except Exception as retry_exc:
                cleanup_failure = cleanup_failure or retry_exc
        except Exception as exc:
            cleanup_failure = cleanup_failure or exc
            try:
                deny_proxy.close()
            except KeyboardInterrupt as retry_exc:
                cleanup_interrupt = cleanup_interrupt or retry_exc
            except Exception:
                pass
        if cleanup_interrupt is not None:
            raise cleanup_interrupt
        if cleanup_failure is not None:
            raise cleanup_failure


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture the owned UX-1B semantic-theme state matrix."
    )
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument(
        "--browser",
        action="append",
        choices=("chromium", "webkit"),
        help="browser to require; default and closure browser is Chromium",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-prompt", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def _manifest_template(owned: OwnedThemeRun, browsers: Sequence[str]) -> dict[str, Any]:
    expected_per_browser = len(SURFACE_COLORS) * len(VIEWPORTS)
    return {
        "schemaVersion": "quant-radar-ui-ux-ux1b-theme-states/v1",
        "mode": "ux1b-theme-states",
        "runId": owned.run_id,
        "manifestPath": safe_relative_output(owned.manifest_path),
        "sourceDigestStart": source_digest(),
        "sourceDigestEnd": None,
        # Filled only after Task 5 freezes the authenticated capture stack.
        "captureStackDigest": None,
        "selectedBrowsers": list(browsers),
        "expectedCapturesPerBrowser": expected_per_browser,
        "expectedCaptureTotal": expected_per_browser * len(browsers),
        "surfaces": [
            {"name": name, "color": color} for name, color in SURFACE_COLORS.items()
        ],
        "viewports": [
            {"name": name, "width": size[0], "height": size[1]}
            for name, size in VIEWPORTS.items()
        ],
        "captures": [],
        "selectorEvidence": [],
        "selectorContract": None,
        "network": [],
        "blockedNetwork": [],
        "exceptions": [],
        "streamlitLog": safe_relative_output(owned.log_path),
        "tools": {
            "runnerVersion": VERSION,
            "python": sys.version.split()[0],
        },
        "summary": {
            "passed": 0,
            "failed": expected_per_browser * len(browsers),
            "total": expected_per_browser * len(browsers),
        },
        "status": "running",
    }


def _manifest_finalization_digest(manifest: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(manifest).encode("utf-8")).hexdigest()


def _owned_run_binding(owned: OwnedThemeRun) -> tuple[Any, ...]:
    return (
        id(owned),
        owned.run_id,
        os.fspath(owned.run_dir),
        os.fspath(owned.manifest_path),
        os.fspath(owned.log_path),
        os.fspath(owned.owner_path),
    )


def _has_theme_success_closure(manifest: Mapping[str, Any]) -> bool:
    if manifest.get("status") != "finalizing":
        return False
    if manifest.get("sourceDigestEnd") != manifest.get("sourceDigestStart"):
        return False
    server = manifest.get("server")
    if not isinstance(server, Mapping):
        return False
    socket_guard = server.get("pythonSocketGuard")
    if (
        server.get("terminated") is not True
        or server.get("denyProxyAttemptCount") != 0
        or not isinstance(socket_guard, Mapping)
        or socket_guard.get("attemptCount") != 0
    ):
        return False
    summary = manifest.get("summary")
    if (
        not isinstance(summary, Mapping)
        or summary.get("passed") != manifest.get("expectedCaptureTotal")
        or summary.get("failed") != 0
        or manifest.get("blockedNetwork")
        or manifest.get("exceptions")
    ):
        return False
    return True


def _authorize_terminal_manifest(
    manifest: dict[str, Any], *, authority: object
) -> _RunnerFinalizationGrant:
    """Mint a digest-bound, one-use grant after all success closure facts exist."""

    if not isinstance(authority, _RunSuccessAuthority):
        raise ThemeContractError("theme run success authority is unavailable")
    with _FINALIZATION_GRANTS_LOCK:
        authority_record = _RUN_SUCCESS_AUTHORITIES.pop(id(authority), None)
        if authority_record is None:
            raise ThemeContractError(
                "theme run success authority is stale or unregistered"
            )
        (
            registered_authority,
            process_id,
            registered_manifest,
            owned,
            owned_binding,
        ) = authority_record
        if (
            registered_authority is not authority
            or process_id != os.getpid()
            or registered_manifest is not manifest
            or not isinstance(owned, OwnedThemeRun)
            or _owned_run_binding(owned) != owned_binding
        ):
            raise ThemeContractError("theme run success authority binding differs")
        if not _has_theme_success_closure(manifest):
            raise ThemeContractError("theme success closure was not authorized")
        digest = _manifest_finalization_digest(manifest)
        grant = object.__new__(_RunnerFinalizationGrant)
        _FINALIZATION_GRANTS[id(grant)] = (
            grant,
            authority,
            os.getpid(),
            manifest,
            owned,
            owned_binding,
            digest,
        )
    return grant


def _discard_terminal_manifest_grant(grant: object) -> None:
    if isinstance(grant, _RunnerFinalizationGrant):
        with _FINALIZATION_GRANTS_LOCK:
            _FINALIZATION_GRANTS.pop(id(grant), None)


def _discard_run_success_authority(authority: object) -> None:
    """Erase every capability associated with one run on every terminal path."""

    with _FINALIZATION_GRANTS_LOCK:
        if isinstance(authority, _RunSuccessAuthority):
            _RUN_SUCCESS_AUTHORITIES.pop(id(authority), None)
        stale_grants = [
            key
            for key, record in _FINALIZATION_GRANTS.items()
            if record[1] is authority
        ]
        for key in stale_grants:
            _FINALIZATION_GRANTS.pop(key, None)


def _retire_run_runtime(
    authority: object, old_handlers: Mapping[int, Any]
) -> BaseException | None:
    """Revoke capabilities and restore handlers, retrying catchable failures."""

    problem: BaseException | None = None

    def remember(exc: BaseException) -> None:
        nonlocal problem
        if problem is None or (
            isinstance(exc, KeyboardInterrupt)
            and not isinstance(problem, KeyboardInterrupt)
        ):
            problem = exc

    def retry(step: Any) -> None:
        for _attempt in range(_RUNTIME_CLEANUP_ATTEMPTS):
            try:
                step()
                return
            except (KeyboardInterrupt, Exception) as exc:
                remember(exc)

    retry(lambda: _discard_run_success_authority(authority))
    for signum, handler in old_handlers.items():
        retry(lambda signum=signum, handler=handler: signal.signal(signum, handler))
    return problem


def _block_terminal_signals() -> set[signal.Signals]:
    """Start the linearized handler-retirement and terminal-commit window."""

    masker = getattr(signal, "pthread_sigmask", None)
    if not callable(masker):
        raise RuntimeError("terminal signal masking is unavailable")
    return masker(signal.SIG_BLOCK, _TERMINAL_SIGNALS)


def _restore_terminal_signal_mask(previous_mask: set[signal.Signals]) -> None:
    masker = getattr(signal, "pthread_sigmask", None)
    if not callable(masker):
        raise RuntimeError("terminal signal masking is unavailable")
    masker(signal.SIG_SETMASK, previous_mask)


def finalize_terminal_manifest(
    manifest: dict[str, Any], *, grant: object
) -> bool:
    """Consume the sole opaque authority for the transition to ``passed``."""

    if not isinstance(grant, _RunnerFinalizationGrant):
        return False
    with _FINALIZATION_GRANTS_LOCK:
        record = _FINALIZATION_GRANTS.pop(id(grant), None)
        if record is None:
            return False
        (
            registered_grant,
            _authority,
            process_id,
            registered_manifest,
            owned,
            owned_binding,
            registered_digest,
        ) = record
        if (
            registered_grant is not grant
            or process_id != os.getpid()
            or registered_manifest is not manifest
            or not isinstance(owned, OwnedThemeRun)
            or _owned_run_binding(owned) != owned_binding
        ):
            return False
        if not _has_theme_success_closure(manifest):
            return False
        if _manifest_finalization_digest(manifest) != registered_digest:
            return False
        manifest["status"] = "passed"
        return True


def _select_browsers(requested: Sequence[str] | None) -> tuple[str, ...]:
    selected = tuple(dict.fromkeys(requested or ("chromium",)))
    if "chromium" not in selected:
        raise ThemeContractError("Chromium is mandatory for UX-1B closure")
    return selected


def _contract_manifest_rows(
    records: Sequence[SelectorContractRecord],
) -> Sequence[Mapping[str, Any]]:
    return tuple({
        "selector": record.selector,
        "property": record.property,
        "owners": list(record.owners),
        "states": list(record.states),
        "important": record.important,
    } for record in records)


def _network_counter(browser: str, viewport: str) -> dict[str, Any]:
    return {
        "browser": browser,
        "viewport": viewport,
        "allowedHttp": 0,
        "allowedWebSocket": 0,
        "blockedHttp": 0,
        "blockedWebSocket": 0,
        "allowedUrls": set(),
        "blockedUrls": set(),
    }


def _finalize_network_counter(counter: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "browser": counter["browser"],
        "viewport": counter["viewport"],
        "allowedHttp": counter["allowedHttp"],
        "allowedWebSocket": counter["allowedWebSocket"],
        "blockedHttp": counter["blockedHttp"],
        "blockedWebSocket": counter["blockedWebSocket"],
        "allowedUrls": sorted(counter["allowedUrls"]),
        "blockedUrls": sorted(counter["blockedUrls"]),
    }


def _install_exact_origin_routes(
    context: Any,
    *,
    port: int,
    counter: dict[str, Any],
    blocked: list[Mapping[str, Any]],
) -> None:
    def handle_http(route: Any) -> None:
        url = route.request.url
        label = safe_url_label(url)
        if is_allowed_browser_url(url, port):
            counter["allowedHttp"] += 1
            counter["allowedUrls"].add(label)
            route.continue_()
            return
        counter["blockedHttp"] += 1
        counter["blockedUrls"].add(label)
        blocked.append({
            "browser": counter["browser"],
            "viewport": counter["viewport"],
            "transport": "http",
            "method": route.request.method,
            "url": label,
        })
        route.abort("blockedbyclient")

    def handle_websocket(websocket: Any) -> None:
        url = websocket.url
        label = safe_url_label(url)
        if is_allowed_browser_url(url, port):
            counter["allowedWebSocket"] += 1
            counter["allowedUrls"].add(label)
            websocket.connect_to_server()
            return
        counter["blockedWebSocket"] += 1
        counter["blockedUrls"].add(label)
        blocked.append({
            "browser": counter["browser"],
            "viewport": counter["viewport"],
            "transport": "websocket",
            "url": label,
        })
        # A routed socket never reaches the network unless connect_to_server()
        # is called.  close() inside this sync callback can re-enter Playwright's
        # dispatcher, so returning here is the bounded fail-closed operation.

    context.route("**/*", handle_http)
    route_web_socket = getattr(context, "route_web_socket", None)
    if not callable(route_web_socket):
        raise DependencyUnavailable("Playwright WebSocket routing is unavailable")
    route_web_socket("**/*", handle_websocket)


def _capture_browser_viewport(
    *,
    browser: Any,
    browser_name: str,
    browser_version: str,
    viewport_name: str,
    viewport: tuple[int, int],
    port: int,
    process: subprocess.Popen[bytes],
    owned: OwnedThemeRun,
    records: Sequence[SelectorContractRecord],
    manifest: dict[str, Any],
) -> None:
    context = browser.new_context(
        viewport={"width": viewport[0], "height": viewport[1]},
        device_scale_factor=1,
        color_scheme="dark",
        reduced_motion="reduce",
        locale="zh-TW",
        timezone_id="Asia/Taipei",
        service_workers="block",
        accept_downloads=False,
    )
    context.set_default_timeout(ACTION_TIMEOUT_MS)
    counter = _network_counter(browser_name, viewport_name)
    try:
        _install_exact_origin_routes(
            context, port=port, counter=counter, blocked=manifest["blockedNetwork"]
        )
    except Exception:
        context.close()
        manifest["network"].append(dict(_finalize_network_counter(counter)))
        raise
    page_errors: list[str] = []
    console_errors: list[str] = []
    request_failures: list[Mapping[str, Any]] = []
    http_errors: list[Mapping[str, Any]] = []
    unexpected_events: list[str] = []

    def on_console(message: Any) -> None:
        if message.type == "error":
            console_errors.append(_sanitize_diagnostic_text(message.text, owned))

    def on_request_failed(request: Any) -> None:
        request_failures.append({
            "url": safe_url_label(request.url),
            "method": request.method,
            "failure": _sanitize_diagnostic_text(request.failure, owned),
        })

    def on_response(response: Any) -> None:
        if response.status >= 400:
            http_errors.append({"url": safe_url_label(response.url), "status": response.status})

    def on_dialog(dialog: Any) -> None:
        unexpected_events.append(f"dialog:{dialog.type}")
        dialog.dismiss()

    def on_download(download: Any) -> None:
        unexpected_events.append("download")
        with contextlib.suppress(Exception):
            download.cancel()

    def on_popup(popup: Any) -> None:
        unexpected_events.append("popup")
        with contextlib.suppress(Exception):
            popup.close()

    try:
        page = context.new_page()
    except Exception:
        context.close()
        manifest["network"].append(dict(_finalize_network_counter(counter)))
        raise
    page.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)
    page.on("console", on_console)
    page.on(
        "pageerror",
        lambda error: page_errors.append(_sanitize_diagnostic_text(error, owned)),
    )
    page.on("requestfailed", on_request_failed)
    page.on("response", on_response)
    page.on("dialog", on_dialog)
    page.on("download", on_download)
    page.on("popup", on_popup)
    try:
        response = page.goto(
            f"http://127.0.0.1:{port}/", wait_until="domcontentloaded",
            timeout=NAVIGATION_TIMEOUT_MS,
        )
        if response is None or response.status >= 400:
            raise ThemeContractError("gallery navigation did not return a successful response")
        _assert_gallery_ready(page)
        if page.title() != "Quant Radar UX-1B Theme States":
            raise ThemeContractError(f"gallery title differs: {page.title()!r}")
        final = urllib.parse.urlsplit(page.url)
        if (
            not is_allowed_browser_url(page.url, port)
            or final.scheme != "http"
            or final.hostname != "127.0.0.1"
            or final.port != port
            or final.path not in {"", "/"}
            or final.query
        ):
            raise ThemeContractError(f"gallery final URL escaped exact origin/root: {page.url!r}")

        selector_evidence = _verify_selector_node_sets(page, records)
        _assert_signal_selector_isolation(page, records)
        selector_payload = {
            "browser": browser_name,
            "viewport": viewport_name,
            "selectors": dict(selector_evidence),
        }
        selector_digest = hashlib.sha256(
            canonical_json(selector_payload).encode("utf-8")
        ).hexdigest()
        selector_payload["sha256"] = selector_digest
        manifest["selectorEvidence"].append(selector_payload)

        for surface in SURFACE_COLORS:
            manifest["captures"].append(_capture_surface(
                page=page,
                owned=owned,
                browser_name=browser_name,
                browser_version=browser_version,
                viewport_name=viewport_name,
                viewport=viewport,
                surface=surface,
                selector_digest=selector_digest,
            ))
        if process.poll() is not None:
            raise ServerExited(
                f"owned Streamlit gallery exited during capture: {_log_tail(owned.log_path)!r}"
            )
        if manifest["blockedNetwork"]:
            raise ThemeContractError("browser attempted external network access")
        if page_errors or console_errors or request_failures or http_errors or unexpected_events:
            details = {
                "browser": browser_name,
                "viewport": viewport_name,
                "pageErrors": page_errors,
                "consoleErrors": console_errors,
                "requestFailures": request_failures,
                "httpErrors": http_errors,
                "unexpectedEvents": unexpected_events,
            }
            manifest["exceptions"].append(details)
            raise ThemeContractError(f"browser exception/event contract failed: {details!r}")
    finally:
        context.close()
        manifest["network"].append(dict(_finalize_network_counter(counter)))


def _theme_worker_request(
    *,
    viewport_name: str,
    viewport: tuple[int, int],
    app_origin: str,
) -> dict[str, Any]:
    """Build one exact frozen theme-gallery worker request."""

    if VIEWPORTS.get(viewport_name) != viewport:
        raise ThemeContractError("theme worker viewport is outside the frozen matrix")
    width, height = viewport
    request_id = f"theme-gallery/{viewport_name}"
    return {
        "schemaVersion": "quant-radar-ui-ux-browser-request/v1",
        "requestId": request_id,
        "fixtureEntrypoint": "scripts/ui_ux_theme_fixture_app.py",
        "case": "theme-gallery",
        "route": "/",
        "viewport": {
            "name": viewport_name,
            "width": width,
            "height": height,
        },
        "appOrigin": app_origin,
        "staging": {
            "png": f"staging/theme-gallery-{viewport_name}.png",
            "renderSidecar": (
                f"staging/theme-gallery-{viewport_name}.render.json"
            ),
        },
    }


def _exact_worker_mapping(
    value: Any, expected_keys: set[str], label: str
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        raise ThemeContractError(f"{label} schema differs")
    return value


def adapt_external_worker_theme_evidence(
    *,
    request: Mapping[str, Any],
    response: Mapping[str, Any],
    sidecar: Mapping[str, Any],
    full_page_png: bytes | None = None,
    records: Sequence[SelectorContractRecord] = (),
    expected_selector_contract_sha256: str | None = None,
    expected_source_digest: str | None = None,
) -> Mapping[str, Any]:
    """Fail closed until the frozen worker can prove the rich theme contract.

    The current worker intentionally returns one full-gallery PNG and the
    phase-neutral render sidecar.  Neither can prove selector computed styles,
    interaction state transitions, focus contrast, or three distinct surface
    screenshots, so no capture row may be synthesized from that response.
    """

    request_row = _exact_worker_mapping(
        request,
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
        "theme worker request",
    )
    if (
        request_row["schemaVersion"]
        != "quant-radar-ui-ux-browser-request/v1"
        or request_row["case"] != "theme-gallery"
        or request_row["route"] != "/"
        or request_row["fixtureEntrypoint"]
        != "scripts/ui_ux_theme_fixture_app.py"
    ):
        raise ThemeContractError("theme worker request identity differs")
    response_row = _exact_worker_mapping(
        response,
        {"schemaVersion", "requestId", "status", "artifacts"},
        "theme worker response",
    )
    artifacts = _exact_worker_mapping(
        response_row["artifacts"],
        {"png", "renderSidecar"},
        "theme worker artifacts",
    )
    if (
        response_row["schemaVersion"]
        != "quant-radar-ui-ux-browser-response/v1"
        or response_row["requestId"] != request_row["requestId"]
        or response_row["status"] != "staged"
        or dict(artifacts) != dict(request_row["staging"])
    ):
        raise ThemeContractError("theme worker staged response differs")
    sidecar_row = _exact_worker_mapping(
        sidecar,
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
        },
        "theme worker generic sidecar",
    )
    identity = _exact_worker_mapping(
        sidecar_row["identity"],
        {"case", "route", "callable"},
        "theme worker sidecar identity",
    )
    readiness = _exact_worker_mapping(
        sidecar_row["readiness"],
        {"ready", "marker"},
        "theme worker readiness",
    )
    stable_state = sidecar_row["stableState"]
    if (
        sidecar_row["schemaVersion"] != "quant-radar-ui-ux-render/v1"
        or dict(identity)
        != {
            "case": "theme-gallery",
            "route": "/",
            "callable": "ui_ux_theme_fixture_app",
        }
        or dict(sidecar_row["viewport"]) != dict(request_row["viewport"])
        or dict(readiness)
        != {"ready": True, "marker": "ux1b-theme-ready"}
        or not isinstance(sidecar_row["nodes"], list)
        or not isinstance(stable_state, Mapping)
        or stable_state.get("registryKey") != "theme-gallery"
        or sidecar_row["providerCounters"] != {}
        or sidecar_row["mutatorCounters"] != {}
        or not isinstance(sidecar_row["runtimeProjection"], Mapping)
    ):
        raise ThemeContractError("theme worker generic sidecar identity differs")
    rich = stable_state.get("themeEvidence")
    if rich is None:
        raise ThemeContractError(THEME_WORKER_RICH_EVIDENCE_BLOCKER)
    if full_page_png is None:
        raise ThemeContractError("theme worker rich evidence lacks authenticated PNG")
    return _validate_external_worker_theme_evidence(
        rich,
        request=request_row,
        full_page_png=full_page_png,
        records=records,
        expected_selector_contract_sha256=expected_selector_contract_sha256,
        expected_source_digest=expected_source_digest,
    )


def _require_sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ThemeContractError(f"{label} is not SHA-256")
    return value


def _theme_png_dimensions(payload: bytes) -> tuple[int, int]:
    if not isinstance(payload, bytes) or not payload:
        raise ThemeContractError("theme worker full-page PNG is missing")
    try:
        from PIL import Image

        image = Image.open(io.BytesIO(payload))
        if image.format != "PNG":
            raise ThemeContractError("theme worker full-page artifact is not PNG")
        image.load()
        return int(image.width), int(image.height)
    except ThemeContractError:
        raise
    except Exception as exc:
        raise ThemeContractError("theme worker full-page PNG is malformed") from exc


def _worker_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ThemeContractError(f"{label} is not a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ThemeContractError(f"{label} is not a finite number")
    return result


def _worker_rgb(value: Any, label: str) -> tuple[int, int, int]:
    if (
        not isinstance(value, list)
        or len(value) != 3
        or any(
            not isinstance(channel, int)
            or isinstance(channel, bool)
            or not 0 <= channel <= 255
            for channel in value
        )
    ):
        raise ThemeContractError(f"{label} is not exact RGB")
    return tuple(value)


def _validate_worker_style_snapshot(
    value: Any, *, label: str, minimum_contrast: float
) -> Mapping[str, Any]:
    snapshot = _exact_worker_mapping(
        value,
        {
            "color",
            "backgroundColor",
            "borderColors",
            "borderWidths",
            "outlineColor",
            "outlineWidth",
            "outlineOffset",
            "textDecorationLine",
            "textDecorationThickness",
            "opacity",
            "resolvedForeground",
            "resolvedBackground",
            "textContrast",
            "rect",
        },
        label,
    )
    if (
        any(
            not isinstance(snapshot[key], str)
            for key in (
                "color",
                "backgroundColor",
                "outlineColor",
                "outlineWidth",
                "outlineOffset",
                "textDecorationLine",
                "textDecorationThickness",
            )
        )
        or not isinstance(snapshot["borderColors"], list)
        or len(snapshot["borderColors"]) != 4
        or any(not isinstance(item, str) for item in snapshot["borderColors"])
        or not isinstance(snapshot["borderWidths"], list)
        or len(snapshot["borderWidths"]) != 4
        or any(not isinstance(item, str) for item in snapshot["borderWidths"])
    ):
        raise ThemeContractError(f"{label} computed-style fields differ")
    opacity = _worker_number(snapshot["opacity"], f"{label} opacity")
    foreground = _worker_rgb(snapshot["resolvedForeground"], f"{label} foreground")
    background = _worker_rgb(snapshot["resolvedBackground"], f"{label} background")
    claimed = _worker_number(snapshot["textContrast"], f"{label} text contrast")
    actual = round(contrast_ratio(foreground, background), 3)
    if not 0.0 <= opacity <= 1.0 or claimed != actual or actual < minimum_contrast:
        raise ThemeContractError(f"{label} resolved contrast differs")
    rect = _exact_worker_mapping(
        snapshot["rect"],
        {"x", "y", "width", "height", "top", "right", "bottom", "left"},
        f"{label} rect",
    )
    normalized = {
        key: _worker_number(rect[key], f"{label} rect.{key}") for key in rect
    }
    if (
        normalized["width"] <= 0
        or normalized["height"] <= 0
        or abs(normalized["x"] - normalized["left"]) > 0.5
        or abs(normalized["y"] - normalized["top"]) > 0.5
        or abs(normalized["right"] - normalized["left"] - normalized["width"]) > 0.5
        or abs(normalized["bottom"] - normalized["top"] - normalized["height"]) > 0.5
    ):
        raise ThemeContractError(f"{label} rect differs")
    return snapshot


def _validate_worker_focus_payload(
    value: Any, *, surface: str, case: str
) -> None:
    row = _exact_worker_mapping(
        value,
        {
            "keyboard",
            "outlineWidth",
            "outlineOffset",
            "outlineColor",
            "deviceScaleFactor",
            "samples",
        },
        f"theme worker focus {surface}/{case}",
    )
    if (
        row["keyboard"] != "Tab then Shift+Tab"
        or row["deviceScaleFactor"] != 1
        or _worker_number(
            row["outlineWidth"], f"theme worker focus width {surface}/{case}"
        )
        < 3.0
        or _worker_number(
            row["outlineOffset"], f"theme worker focus offset {surface}/{case}"
        )
        < 1.0
    ):
        raise ThemeContractError(f"theme worker focus geometry differs: {surface}/{case}")
    _exact_computed_color(
        str(row["outlineColor"]),
        APPROVED_TOKENS["border.focus"],
        f"theme worker focus {surface}/{case}",
    )
    samples_raw = _exact_worker_mapping(
        row["samples"], set(FOCUS_SIDES), f"theme worker focus samples {surface}/{case}"
    )
    samples: dict[str, FocusSideSample] = {}
    for side in FOCUS_SIDES:
        sample = _exact_worker_mapping(
            samples_raw[side],
            {"gap", "ring", "outer", "clipped"},
            f"theme worker focus sample {surface}/{case}/{side}",
        )
        gap = (
            None
            if sample["gap"] is None
            else _worker_rgb(
                sample["gap"], f"theme worker focus gap {surface}/{case}/{side}"
            )
        )
        ring = _worker_rgb(
            sample["ring"], f"theme worker focus ring {surface}/{case}/{side}"
        )
        outer = _worker_rgb(
            sample["outer"], f"theme worker focus outer {surface}/{case}/{side}"
        )
        if (
            not isinstance(sample["clipped"], bool)
        ):
            raise ThemeContractError(
                f"theme worker focus pixels differ: {surface}/{case}/{side}"
            )
        samples[side] = FocusSideSample(
            gap=gap,
            ring=ring,
            outer=outer,
            clipped=sample["clipped"],
        )
    validate_focus_adjacency(
        samples=samples,
        component_color=rgb(SURFACE_COLORS[surface]),
        expected_surface=rgb(SURFACE_COLORS[surface]),
        expected_ring=rgb(APPROVED_TOKENS["border.focus"]),
        channel_tolerance=CHANNEL_TOLERANCE,
    )


def _validate_worker_selected_controls(value: Any, *, surface: str) -> None:
    controls = _exact_worker_mapping(
        value,
        {"checkbox", "radio", "radio_horizontal", "toggle", "slider", "selectbox"},
        f"theme worker selected controls {surface}",
    )
    for case, raw in controls.items():
        row = _exact_worker_mapping(
            raw,
            {"semantics", "label", "parts", "domParts", "owner"},
            f"theme worker selected control {surface}/{case}",
        )
        if row["owner"] != owner_id(surface, case):
            raise ThemeContractError(
                f"theme worker selected owner differs: {surface}/{case}"
            )
        _validate_worker_style_snapshot(
            row["label"],
            label=f"theme worker selected label {surface}/{case}",
            minimum_contrast=4.5,
        )
        parts = row["parts"]
        expected_parts = {} if case == "selectbox" else _SELECTED_PART_SPECS[case]
        if not isinstance(parts, Mapping) or set(parts) != set(expected_parts):
            raise ThemeContractError(
                f"theme worker selected parts differ: {surface}/{case}"
            )
        measurements: dict[str, Mapping[str, Any]] = {}
        for name, spec in expected_parts.items():
            part = _exact_worker_mapping(
                parts[name],
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
                f"theme worker selected part {surface}/{case}/{name}",
            )
            if (
                part["node"] != spec["node"]
                or part["paint"] != spec["paint"]
                or part["composited"] is not True
                or part["source"] not in {"computed-style", "rendered-pixel"}
                or part["expectedRole"] != spec["role"]
                or part["adjacentRole"] != spec["adjacent"]
                or _worker_number(
                    part["minimumContrast"],
                    f"theme worker selected minimum {surface}/{case}/{name}",
                )
                != float(spec["minimum"])
                or _worker_number(
                    part["contrast"],
                    f"theme worker selected contrast {surface}/{case}/{name}",
                )
                < float(spec["minimum"])
            ):
                raise ThemeContractError(
                    f"theme worker selected part contract differs: {surface}/{case}/{name}"
                )
            measurements[name] = {
                key: part[key]
                for key in (
                    "node",
                    "paint",
                    "actual",
                    "adjacent",
                    "composited",
                    "source",
                )
            }
        if expected_parts:
            validated = validate_selected_part_measurements(
                case, surface, measurements
            )
            for name, expected in validated.items():
                if any(
                    parts[name][key] != expected[key]
                    for key in (
                        "actual",
                        "adjacent",
                        "expectedRole",
                        "adjacentRole",
                        "minimumContrast",
                        "contrast",
                    )
                ):
                    raise ThemeContractError(
                        f"theme worker selected measurement differs: {surface}/{case}/{name}"
                    )
        semantics = row["semantics"]
        if case == "radio_horizontal":
            semantics = _exact_worker_mapping(
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
                "theme worker horizontal-radio semantics",
            )
            validate_radio_horizontal_semantic_state(
                {
                    key: semantics.get(key)
                    for key in (
                        "groupRole",
                        "groupName",
                        "optionRole",
                        "optionLabels",
                        "checkedLabels",
                        "tabSequenceLabels",
                        "afterArrowRight",
                        "afterArrowLeft",
                    )
                }
            )
            if semantics["selectionBasis"] != "native-radio/one-checked/roving-tabstop":
                raise ThemeContractError("theme worker horizontal-radio basis differs")
            layout = semantics["layout"]
            if not isinstance(layout, list) or len(layout) != 2:
                raise ThemeContractError("theme worker horizontal-radio layout differs")
            normalized_layout: list[dict[str, float]] = []
            for raw_geometry in layout:
                geometry = _exact_worker_mapping(
                    raw_geometry,
                    {"left", "right", "top", "bottom", "width", "height"},
                    "theme worker horizontal-radio layout",
                )
                normalized_layout.append(
                    {
                        key: _worker_number(
                            geometry[key], f"theme worker horizontal-radio {key}"
                        )
                        for key in geometry
                    }
                )
            if (
                normalized_layout[1]["left"] <= normalized_layout[0]["left"]
                or abs(
                    normalized_layout[1]["top"] - normalized_layout[0]["top"]
                )
                > 1.0
                or min(
                    normalized_layout[0]["width"],
                    normalized_layout[0]["height"],
                    normalized_layout[1]["width"],
                    normalized_layout[1]["height"],
                )
                < 24.0
            ):
                raise ThemeContractError("theme worker horizontal-radio layout differs")
        elif case == "selectbox":
            semantics = _exact_worker_mapping(
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
                "theme worker selectbox semantics",
            )
            validate_selectbox_semantic_state(
                {
                    key: semantics.get(key)
                    for key in (
                        "role",
                        "accessibleName",
                        "optionLabels",
                        "selectedText",
                        "afterArrowDown",
                        "afterArrowUp",
                    )
                }
            )
            if semantics["selectionBasis"] != "combobox/exact-option-order/keyboard":
                raise ThemeContractError("theme worker selectbox basis differs")
            _validate_worker_style_snapshot(
                semantics["selectedValue"],
                label=f"theme worker selectbox selected value {surface}",
                minimum_contrast=4.5,
            )


def _validate_worker_surface_state(value: Any, *, surface: str) -> None:
    states = _exact_worker_mapping(
        value,
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
        f"theme worker surface states {surface}",
    )
    if not isinstance(states["primary"], Mapping) or set(states["primary"]) != set(
        PRIMARY_CASES
    ):
        raise ThemeContractError(f"theme worker primary states differ: {surface}")
    primary_tokens = {
        "default": "interactive.primary",
        "hover": "interactive.hover",
        "active": "interactive.active",
    }
    for case in PRIMARY_CASES:
        row = _exact_worker_mapping(
            states["primary"][case],
            set(primary_tokens),
            f"theme worker primary {surface}/{case}",
        )
        for state, token in primary_tokens.items():
            snapshot = _validate_worker_style_snapshot(
                row[state],
                label=f"theme worker primary {surface}/{case}/{state}",
                minimum_contrast=4.5,
            )
            _exact_computed_color(
                snapshot["color"],
                APPROVED_TOKENS["text.on-primary"],
                f"theme worker primary text {surface}/{case}/{state}",
            )
            _exact_computed_color(
                snapshot["backgroundColor"],
                APPROVED_TOKENS[token],
                f"theme worker primary fill {surface}/{case}/{state}",
            )
    tertiary = _exact_worker_mapping(
        states["tertiary"],
        {"default", "hover", "active"},
        f"theme worker tertiary {surface}",
    )
    for state, value in tertiary.items():
        snapshot = _validate_worker_style_snapshot(
            value,
            label=f"theme worker tertiary {surface}/{state}",
            minimum_contrast=4.5,
        )
        _exact_computed_color(
            snapshot["color"],
            APPROVED_TOKENS["interactive.accent"],
            f"theme worker tertiary text {surface}/{state}",
        )
    disabled = _exact_worker_mapping(
        states["disabled"],
        {"semantics", "default"},
        f"theme worker disabled {surface}",
    )
    disabled_semantics = _exact_worker_mapping(
        disabled["semantics"],
        {
            "disabled",
            "ariaDisabled",
            "programmaticClickEvents",
            "focusAccepted",
            "inactiveContrastException",
        },
        f"theme worker disabled semantics {surface}",
    )
    if (
        disabled_semantics["disabled"] is not True
        or disabled_semantics["programmaticClickEvents"] != 0
        or disabled_semantics["focusAccepted"] is not False
        or disabled_semantics["inactiveContrastException"] is not True
    ):
        raise ThemeContractError(f"theme worker disabled semantics differ: {surface}")
    disabled_snapshot = _validate_worker_style_snapshot(
        disabled["default"],
        label=f"theme worker disabled {surface}/default",
        minimum_contrast=0.0,
    )
    _exact_computed_color(
        disabled_snapshot["color"],
        APPROVED_TOKENS["text.disabled"],
        f"theme worker disabled text {surface}",
    )
    tabs = _exact_worker_mapping(
        states["tabs"],
        {"active", "hover", "semantics"},
        f"theme worker tabs {surface}",
    )
    for state in ("active", "hover"):
        snapshot = _validate_worker_style_snapshot(
            tabs[state],
            label=f"theme worker tabs {surface}/{state}",
            minimum_contrast=4.5,
        )
        _exact_computed_color(
            snapshot["color"],
            APPROVED_TOKENS["interactive.accent"],
            f"theme worker tabs text {surface}/{state}",
        )
    tab_semantics = _exact_worker_mapping(
        tabs["semantics"],
        {"ariaSelected", "underline"},
        f"theme worker tab semantics {surface}",
    )
    if (
        tab_semantics["ariaSelected"] != "true"
        or not isinstance(tab_semantics["underline"], list)
        or not tab_semantics["underline"]
    ):
        raise ThemeContractError(f"theme worker tab semantics differ: {surface}")
    markdown = _exact_worker_mapping(
        states["markdownLink"],
        {"default", "hover", "visited"},
        f"theme worker markdown link {surface}",
    )
    if markdown["visited"] != "static-only; no protected-history claim":
        raise ThemeContractError(f"theme worker visited claim differs: {surface}")
    for state in ("default", "hover"):
        snapshot = _validate_worker_style_snapshot(
            markdown[state],
            label=f"theme worker markdown link {surface}/{state}",
            minimum_contrast=4.5,
        )
        _exact_computed_color(
            snapshot["color"],
            APPROVED_TOKENS["interactive.accent"],
            f"theme worker markdown text {surface}/{state}",
        )
        if "underline" not in snapshot["textDecorationLine"].casefold():
            raise ThemeContractError(
                f"theme worker markdown underline differs: {surface}/{state}"
            )
    _validate_worker_selected_controls(states["selectedControls"], surface=surface)
    alerts = states["alerts"]
    expected_alerts = ("資訊狀態", "成功狀態", "警告狀態", "錯誤狀態")
    if not isinstance(alerts, list) or len(alerts) != len(expected_alerts):
        raise ThemeContractError(f"theme worker alerts differ: {surface}")
    for meaning, value in zip(expected_alerts, alerts):
        alert = _exact_worker_mapping(
            value,
            {"role", "meaning", "hasIcon", "style"},
            f"theme worker alert {surface}/{meaning}",
        )
        if (
            alert["role"] != "alert"
            or alert["meaning"] != meaning
            or alert["hasIcon"] is not True
        ):
            raise ThemeContractError(f"theme worker alert differs: {surface}/{meaning}")
        _validate_worker_style_snapshot(
            alert["style"],
            label=f"theme worker alert style {surface}/{meaning}",
            minimum_contrast=4.5,
        )
    signals = states["signals"]
    expected_signals = (("AVOID", "#ef4444"), ("Bearish", "#ef553b"))
    if not isinstance(signals, list) or len(signals) != len(expected_signals):
        raise ThemeContractError(f"theme worker signals differ: {surface}")
    for (meaning, color), value in zip(expected_signals, signals):
        signal_row = _exact_worker_mapping(
            value,
            {"meaning", "color", "hasIcon", "text"},
            f"theme worker signal {surface}/{meaning}",
        )
        if (
            signal_row["meaning"] != meaning
            or signal_row["color"] != color
            or signal_row["hasIcon"] is not True
            or not isinstance(signal_row["text"], str)
            or meaning not in signal_row["text"]
        ):
            raise ThemeContractError(f"theme worker signal differs: {surface}/{meaning}")
    focus = _exact_worker_mapping(
        states["focus"], set(FOCUS_CASES), f"theme worker focus set {surface}"
    )
    for case in FOCUS_CASES:
        _validate_worker_focus_payload(focus[case], surface=surface, case=case)


def _validate_external_worker_theme_evidence(
    value: Any,
    *,
    request: Mapping[str, Any],
    full_page_png: bytes,
    records: Sequence[SelectorContractRecord],
    expected_selector_contract_sha256: str | None,
    expected_source_digest: str | None,
) -> Mapping[str, Any]:
    rich = _exact_worker_mapping(
        value,
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
        "theme worker rich evidence",
    )
    if rich["schemaVersion"] != THEME_WORKER_EVIDENCE_SCHEMA:
        raise ThemeContractError("theme worker rich evidence schema differs")
    claimed_sha256 = _require_sha256(rich["sha256"], "theme worker rich evidence")
    digest_payload = {key: rich[key] for key in rich if key != "sha256"}
    if hashlib.sha256(canonical_json(digest_payload).encode("utf-8")).hexdigest() != claimed_sha256:
        raise ThemeContractError("theme worker rich evidence digest differs")
    browser = _exact_worker_mapping(
        rich["browser"], {"name", "version"}, "theme worker browser identity"
    )
    if browser["name"] != "chromium" or not isinstance(browser["version"], str) or not browser["version"]:
        raise ThemeContractError("theme worker browser identity differs")
    viewport = _exact_worker_mapping(
        rich["viewport"],
        {"name", "width", "height", "deviceScaleFactor"},
        "theme worker rich viewport",
    )
    expected_viewport = {
        **dict(request["viewport"]),
        "deviceScaleFactor": 1,
    }
    if dict(viewport) != expected_viewport:
        raise ThemeContractError("theme worker rich viewport differs")
    full_page = _exact_worker_mapping(
        rich["fullPage"],
        {"width", "height", "deviceScaleFactor"},
        "theme worker full-page identity",
    )
    png_width, png_height = _theme_png_dimensions(full_page_png)
    if (
        any(
            not isinstance(full_page[key], int)
            or isinstance(full_page[key], bool)
            for key in ("width", "height", "deviceScaleFactor")
        )
        or full_page["deviceScaleFactor"] != 1
        or full_page["width"] != viewport["width"]
        or full_page["height"] < viewport["height"]
        or (png_width, png_height) != (full_page["width"], full_page["height"])
    ):
        raise ThemeContractError("theme worker full-page PNG dimensions differ")
    case_contract = _exact_worker_mapping(
        rich["caseContract"],
        {"galleryCases", "focusCases", "ownerCount", "sha256"},
        "theme worker case contract",
    )
    case_digest_payload = {
        key: case_contract[key] for key in case_contract if key != "sha256"
    }
    if (
        case_contract["galleryCases"] != list(REQUIRED_GALLERY_CASES)
        or case_contract["focusCases"] != list(FOCUS_CASES)
        or case_contract["ownerCount"]
        != len(SURFACE_COLORS) * len(REQUIRED_GALLERY_CASES)
        or _require_sha256(case_contract["sha256"], "theme worker case contract")
        != hashlib.sha256(
            canonical_json(case_digest_payload).encode("utf-8")
        ).hexdigest()
    ):
        raise ThemeContractError("theme worker case contract differs")
    expected_contract = _require_sha256(
        expected_selector_contract_sha256,
        "expected theme selector contract",
    )
    if rich["selectorContractSha256"] != expected_contract:
        raise ThemeContractError("theme worker selector contract digest differs")
    if rich["sourceDigest"] != _require_sha256(
        expected_source_digest, "expected theme source digest"
    ):
        raise ThemeContractError("theme worker source digest differs")
    if not records:
        raise ThemeContractError("theme worker selector records are unavailable")
    selector = _exact_worker_mapping(
        rich["selectorEvidence"],
        {"browser", "viewport", "selectors", "sha256"},
        "theme worker selector evidence",
    )
    selector_digest_payload = {
        key: selector[key] for key in selector if key != "sha256"
    }
    if (
        selector["browser"] != "chromium"
        or selector["viewport"] != viewport["name"]
        or _require_sha256(selector["sha256"], "theme worker selector evidence")
        != hashlib.sha256(
            canonical_json(selector_digest_payload).encode("utf-8")
        ).hexdigest()
    ):
        raise ThemeContractError("theme worker selector evidence identity differs")
    selectors = _exact_worker_mapping(
        selector["selectors"],
        set(_selector_metadata(records)),
        "theme worker selector set",
    )
    for css_selector, (owners, states) in _selector_metadata(records).items():
        row = _exact_worker_mapping(
            selectors[css_selector],
            {
                "states",
                "owners",
                "nodes",
                "signatures",
                "observations",
                "visitedComputedStyleClaimed",
            },
            f"theme worker selector {css_selector}",
        )
        if (
            row["states"] != list(states)
            or row["owners"] != sorted(owners)
            or row["nodes"] != sorted(f"{owner}::0" for owner in owners)
            or row["visitedComputedStyleClaimed"] is not False
            or not isinstance(row["signatures"], list)
            or len(row["signatures"]) != len(owners)
        ):
            raise ThemeContractError(
                f"theme worker selector observation differs: {css_selector}"
            )
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
        for owner, raw_signature in zip(sorted(owners), row["signatures"]):
            signature = _exact_worker_mapping(
                raw_signature,
                signature_keys,
                f"theme worker selector signature {css_selector}",
            )
            if (
                signature["owner"] != owner
                or signature["node"] != f"{owner}::0"
                or not isinstance(signature["tag"], str)
                or not signature["tag"]
            ):
                raise ThemeContractError(
                    f"theme worker selector signature differs: {css_selector}"
                )
    surfaces = rich["surfaces"]
    if not isinstance(surfaces, list) or [row.get("name") for row in surfaces if isinstance(row, Mapping)] != list(SURFACE_COLORS):
        raise ThemeContractError("theme worker surface order differs")
    crops: list[tuple[int, int, int, int]] = []
    for raw_surface in surfaces:
        surface_row = _exact_worker_mapping(
            raw_surface,
            {"name", "color", "geometry", "states", "overflow"},
            "theme worker surface",
        )
        surface = str(surface_row["name"])
        if surface_row["color"] != SURFACE_COLORS[surface]:
            raise ThemeContractError(f"theme worker surface color differs: {surface}")
        geometry = _exact_worker_mapping(
            surface_row["geometry"],
            {
                "selector",
                "coordinateSpace",
                "deviceScaleFactor",
                "scrollOffset",
                "cssRect",
                "crop",
            },
            f"theme worker surface geometry {surface}",
        )
        scroll = _exact_worker_mapping(
            geometry["scrollOffset"], {"x", "y"}, f"theme worker scroll {surface}"
        )
        css_rect = _exact_worker_mapping(
            geometry["cssRect"],
            {"left", "top", "right", "bottom", "width", "height"},
            f"theme worker CSS rect {surface}",
        )
        crop = _exact_worker_mapping(
            geometry["crop"], {"x", "y", "width", "height"}, f"theme worker crop {surface}"
        )
        normalized_scroll = {
            key: _worker_number(
                scroll[key], f"theme worker scroll {surface}.{key}"
            )
            for key in scroll
        }
        normalized_rect = {
            key: _worker_number(
                css_rect[key], f"theme worker CSS rect {surface}.{key}"
            )
            for key in css_rect
        }
        if any(
            not isinstance(value, int) or isinstance(value, bool)
            for value in crop.values()
        ):
            raise ThemeContractError(f"theme worker crop values malformed: {surface}")
        expected_crop = (
            math.floor(normalized_rect["left"] + normalized_scroll["x"]),
            math.floor(normalized_rect["top"] + normalized_scroll["y"]),
            math.ceil(normalized_rect["right"] + normalized_scroll["x"]),
            math.ceil(normalized_rect["bottom"] + normalized_scroll["y"]),
        )
        actual_crop = (
            crop["x"],
            crop["y"],
            crop["x"] + crop["width"],
            crop["y"] + crop["height"],
        )
        if (
            geometry["selector"] != f".st-key-ux1b_surface_{surface}"
            or geometry["coordinateSpace"] != "full-page-css-pixels"
            or geometry["deviceScaleFactor"] != 1
            or normalized_rect["width"] <= 0
            or normalized_rect["height"] <= 0
            or abs(
                normalized_rect["right"]
                - normalized_rect["left"]
                - normalized_rect["width"]
            )
            > 0.1
            or abs(
                normalized_rect["bottom"]
                - normalized_rect["top"]
                - normalized_rect["height"]
            )
            > 0.1
            or actual_crop != expected_crop
            or actual_crop[0] < 0
            or actual_crop[1] < 0
            or actual_crop[2] > png_width
            or actual_crop[3] > png_height
            or crop["width"] <= 0
            or crop["height"] <= 0
        ):
            raise ThemeContractError(f"theme worker crop contract differs: {surface}")
        for prior in crops:
            overlaps = not (
                actual_crop[2] <= prior[0]
                or prior[2] <= actual_crop[0]
                or actual_crop[3] <= prior[1]
                or prior[3] <= actual_crop[1]
            )
            if overlaps:
                raise ThemeContractError("theme worker surface crops overlap")
        crops.append(actual_crop)
        _validate_worker_surface_state(surface_row["states"], surface=surface)
        overflow = _exact_worker_mapping(
            surface_row["overflow"],
            {"surface", "document", "overflowOwners"},
            f"theme worker overflow {surface}",
        )
        if overflow["overflowOwners"] != []:
            raise ThemeContractError(f"theme worker overflow differs: {surface}")
        surface_overflow = _exact_worker_mapping(
            overflow["surface"],
            {"clientWidth", "scrollWidth", "left", "right", "backgroundColor"},
            f"theme worker surface overflow {surface}",
        )
        document_overflow = _exact_worker_mapping(
            overflow["document"],
            {"clientWidth", "scrollWidth"},
            f"theme worker document overflow {surface}",
        )
        if (
            _worker_number(
                surface_overflow["scrollWidth"],
                f"theme worker surface scroll width {surface}",
            )
            > _worker_number(
                surface_overflow["clientWidth"],
                f"theme worker surface client width {surface}",
            )
            + 1.0
            or _worker_number(
                document_overflow["scrollWidth"],
                f"theme worker document scroll width {surface}",
            )
            > _worker_number(
                document_overflow["clientWidth"],
                f"theme worker document client width {surface}",
            )
            + 1.0
        ):
            raise ThemeContractError(f"theme worker overflow differs: {surface}")
        _exact_computed_color(
            surface_overflow["backgroundColor"],
            SURFACE_COLORS[surface],
            f"theme worker surface background {surface}",
        )
    return json.loads(canonical_json(dict(rich)))


def _write_worker_stdin(stdio: Any, payload: bytes) -> None:
    if not isinstance(payload, bytes) or not payload.endswith(b"\n"):
        raise ThemeContractError("theme worker request is not one canonical line")
    flags = os.O_WRONLY | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(os.fspath(stdio.stdin.name), flags)
    try:
        opened = os.fstat(descriptor)
        inherited = os.fstat(stdio.stdin.fileno())
        if (
            not stat.S_ISREG(opened.st_mode)
            or (opened.st_dev, opened.st_ino)
            != (inherited.st_dev, inherited.st_ino)
            or opened.st_uid != os.getuid()
            or opened.st_nlink != 1
            or stat.S_IMODE(opened.st_mode) != 0o600
        ):
            raise ThemeContractError("theme worker stdin identity differs")
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise ThemeContractError("theme worker stdin write was short")
            view = view[written:]
        os.fsync(descriptor)
        if os.fstat(descriptor).st_size != len(payload):
            raise ThemeContractError("theme worker stdin size differs")
    finally:
        os.close(descriptor)


def _read_worker_private_file(
    path: Path,
    *,
    root: Path,
    maximum: int,
    label: str,
) -> bytes:
    # Darwin exposes the same temp inode through ``/var`` and
    # ``/private/var``.  Canonicalize both sides before the containment test;
    # the leaf is still reopened with O_NOFOLLOW below.
    candidate = Path(path).expanduser().absolute().resolve()
    owned_root = Path(root).expanduser().absolute().resolve()
    if (
        not isinstance(maximum, int)
        or maximum <= 0
        or candidate == owned_root
        or not candidate.is_relative_to(owned_root)
    ):
        raise ThemeContractError(f"{label} path/bound differs")
    descriptor = os.open(
        candidate, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_uid != os.getuid()
            or observed.st_nlink != 1
            or stat.S_IMODE(observed.st_mode) != 0o600
            or observed.st_size > maximum
        ):
            raise ThemeContractError(f"{label} file identity differs")
        chunks: list[bytes] = []
        remaining = maximum + 1
        while remaining:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if len(payload) > maximum or len(payload) != observed.st_size:
            raise ThemeContractError(f"{label} byte bound differs")
        return payload
    finally:
        os.close(descriptor)


def _read_descriptor_authenticated_worker_artifact(
    evidence: Any,
    browser_root_fd: int,
    relative_path: str,
    *,
    maximum: int,
    label: str,
) -> bytes:
    """Read one worker artifact only through its frozen descriptor contract."""

    contract = evidence.freeze_artifact_contract(
        browser_root_fd,
        relative_path,
        expected_owner=os.getuid(),
        max_bytes=maximum,
    )
    with evidence.open_authenticated_artifact(browser_root_fd, contract) as artifact:
        expected = contract.leaf
        before = os.fstat(artifact.descriptor)
        chunks: list[bytes] = []
        offset = 0
        while offset < expected.size:
            chunk = os.pread(
                artifact.descriptor,
                min(1024 * 1024, expected.size - offset),
                offset,
            )
            if not chunk:
                raise ThemeContractError(f"{label} became shorter while reading")
            chunks.append(chunk)
            offset += len(chunk)
        payload = b"".join(chunks)
        after = os.fstat(artifact.descriptor)
        identity = lambda value: (
            value.st_dev,
            value.st_ino,
            value.st_uid,
            stat.S_IMODE(value.st_mode),
            value.st_nlink,
            value.st_size,
        )
        if (
            identity(before) != identity(after)
            or offset != expected.size
            or hashlib.sha256(payload).hexdigest() != expected.sha256
        ):
            raise ThemeContractError(f"{label} descriptor identity changed")
        return payload


def _write_owned_capture_png(path: Path, payload: bytes) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise ThemeContractError("theme surface PNG write was short")
            view = view[written:]
        os.fsync(descriptor)
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_uid != os.getuid()
            or observed.st_nlink != 1
            or stat.S_IMODE(observed.st_mode) != 0o600
            or observed.st_size != len(payload)
        ):
            raise ThemeContractError("theme surface PNG identity differs")
    finally:
        os.close(descriptor)


def _materialize_external_worker_theme_captures(
    *,
    rich: Mapping[str, Any],
    full_page_png: bytes,
    owned: OwnedThemeRun,
    source_digest_value: str,
) -> list[Mapping[str, Any]]:
    """Crop three authenticated surface images from one worker full-page PNG."""

    from PIL import Image

    with Image.open(io.BytesIO(full_page_png)) as source_image:
        if source_image.format != "PNG":
            raise ThemeContractError("theme worker full-page artifact is not PNG")
        source_image.load()
        image = source_image.copy()
    full_page_sha256 = hashlib.sha256(full_page_png).hexdigest()
    browser = rich["browser"]
    viewport = rich["viewport"]
    selector_digest = rich["selectorEvidence"]["sha256"]
    captures: list[Mapping[str, Any]] = []
    for surface_row in rich["surfaces"]:
        surface = surface_row["name"]
        crop = surface_row["geometry"]["crop"]
        box = (
            crop["x"],
            crop["y"],
            crop["x"] + crop["width"],
            crop["y"] + crop["height"],
        )
        cropped = image.crop(box)
        if cropped.size != (crop["width"], crop["height"]):
            raise ThemeContractError(f"theme worker crop size differs: {surface}")
        buffer = io.BytesIO()
        cropped.save(buffer, format="PNG")
        payload = buffer.getvalue()
        if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ThemeContractError(f"theme worker crop is not PNG: {surface}")
        capture_id = f"chromium-{viewport['name']}-{surface}"
        screenshot_path = owned.run_dir / f"{capture_id}.png"
        _write_owned_capture_png(screenshot_path, payload)
        if source_digest() != source_digest_value:
            raise ThemeContractError(
                f"source changed while publishing worker crop: {capture_id}"
            )
        captures.append(
            {
                "id": capture_id,
                "browser": "chromium",
                "browserVersion": browser["version"],
                "viewport": dict(viewport),
                "surface": {
                    "name": surface,
                    "color": SURFACE_COLORS[surface],
                },
                "screenshot": safe_relative_output(screenshot_path),
                "screenshotSha256": hashlib.sha256(payload).hexdigest(),
                "screenshotBytes": len(payload),
                "selectorEvidenceDigest": selector_digest,
                "states": surface_row["states"],
                "overflow": surface_row["overflow"],
                "workerProvenance": {
                    "themeEvidenceSha256": rich["sha256"],
                    "fullPagePngSha256": full_page_sha256,
                    "crop": dict(crop),
                    "coordinateSpace": surface_row["geometry"]["coordinateSpace"],
                    "derivedWithoutResampling": True,
                },
                "exception": None,
                "sourceDigestStart": source_digest_value,
                "sourceDigestEnd": source_digest_value,
                "status": "passed",
            }
        )
    return captures


def _theme_counter_expectations(
    rows: Sequence[Mapping[str, Any]],
    *,
    app_root: Path,
) -> dict[str, dict[str, Any]]:
    """Project the public fixture theme contract into three exact captures."""

    _ensure_workspace_import_path()
    from scripts import ui_ux_fixtures as fixtures

    if tuple(
        f'{row["case"]}/{row["viewport"]["name"]}' for row in rows
    ) != (
        "theme-gallery/desktop",
        "theme-gallery/mobile",
        "theme-gallery/tablet",
    ):
        raise ThemeContractError("theme counter identity matrix differs")
    counter = fixtures.THEME_COUNTER_CONTRACT
    if not counter["positive"] or not counter["zero"] or not fixtures.THEME_OWNED_PATHS:
        raise ThemeContractError("theme counter contract is incomplete")
    return {
        f'{row["case"]}/{row["viewport"]["name"]}': {
            "identityRow": dict(row),
            "positiveCounters": dict(counter["positive"]),
            "zeroCounters": tuple(sorted(counter["zero"])),
            "ownedPaths": {
                name: str((app_root / "fixture-root" / relative).resolve())
                for name, relative in fixtures.THEME_OWNED_PATHS.items()
            },
        }
        for row in rows
    }


def _sum_theme_counters(
    authenticated_bundle: Mapping[str, Any],
) -> tuple[dict[str, int], dict[str, int]]:
    provider: dict[str, int] = {}
    mutator: dict[str, int] = {}
    for capture in authenticated_bundle["captures"].values():
        for name, value in capture["providerCounters"].items():
            provider[name] = provider.get(name, 0) + int(value)
        for name, value in capture["mutatorCounters"].items():
            mutator[name] = mutator.get(name, 0) + int(value)
    return provider, mutator


def _theme_persisted_audit_evidence(
    *,
    calibration: Mapping[str, Any],
    worker_request_sha256: Mapping[str, str],
    app_origin: str,
    app_port: int,
    denied_port: int,
    browser_executable_sha256: str,
) -> dict[str, Any]:
    """Freeze the replay-auditable isolation and worker-request closure."""

    expected_capture_ids = {
        "theme-gallery/desktop",
        "theme-gallery/mobile",
        "theme-gallery/tablet",
    }
    if (
        set(worker_request_sha256) != expected_capture_ids
        or any(
            not isinstance(value, str)
            or not re.fullmatch(r"[0-9a-f]{64}", value)
            for value in worker_request_sha256.values()
        )
    ):
        raise ThemeContractError("theme canonical worker-request digest set differs")
    if (
        not isinstance(app_port, int)
        or not isinstance(denied_port, int)
        or app_port == denied_port
        or app_origin != f"http://127.0.0.1:{app_port}"
        or not re.fullmatch(r"[0-9a-f]{64}", browser_executable_sha256)
    ):
        raise ThemeContractError("theme persisted network/Chromium identity differs")
    required_calibration = {
        "schemaVersion",
        "capability",
        "platform",
        "passed",
        "profilesAreDistinct",
        "inheritedFdProbeExplicit",
        "launchIdentitySha256",
        "app",
        "browser",
    }
    if (
        set(calibration) != required_calibration
        or calibration.get("passed") is not True
        or calibration.get("profilesAreDistinct") is not True
        or not re.fullmatch(
            r"[0-9a-f]{64}", str(calibration.get("launchIdentitySha256", ""))
        )
    ):
        raise ThemeContractError("theme persisted calibration header differs")
    for role in ("app", "browser"):
        row = calibration.get(role)
        if not isinstance(row, Mapping) or set(row) != {
            "passed",
            "profileSha256",
            "allowed",
            "denied",
            "observations",
            "details",
        }:
            raise ThemeContractError(f"theme persisted {role} calibration row differs")
        allowed = row.get("allowed")
        denied = row.get("denied")
        observations = row.get("observations")
        details = row.get("details")
        if (
            row.get("passed") is not True
            or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("profileSha256", "")))
            or not isinstance(allowed, Mapping)
            or not allowed
            or any(value is not True for value in allowed.values())
            or not isinstance(denied, Mapping)
            or not denied
            or any(value is not True for value in denied.values())
            or not isinstance(observations, Mapping)
            or not observations
            or not isinstance(details, Mapping)
            or set(details) != set(denied)
        ):
            raise ThemeContractError(
                f"theme persisted {role} calibration closure is incomplete"
            )
    report = copy.deepcopy(dict(calibration))
    report_sha256 = hashlib.sha256(
        _theme_canonical_ndjson(report).rstrip(b"\n")
    ).hexdigest()
    return {
        "networkAssignment": {
            "appOrigin": app_origin,
            "appPort": app_port,
            "deniedPort": denied_port,
        },
        "calibration": {
            "sha256": report_sha256,
            "report": report,
        },
        "browserExecutableSha256": browser_executable_sha256,
        "workerRequests": [
            {
                "captureId": capture_id,
                "canonicalRequestSha256": worker_request_sha256[capture_id],
            }
            for capture_id in sorted(worker_request_sha256)
        ],
    }


def _theme_static_contract() -> tuple[
    tuple[SelectorContractRecord, ...],
    dict[str, Any],
]:
    from ui import _design

    builder = getattr(_design, "build_global_theme_css", None)
    if not callable(builder):
        raise ThemeContractError("production theme CSS builder is unavailable")
    validate_palette_contract(APPROVED_TOKENS, SURFACE_COLORS)
    validate_design_token_contract(_design)
    css = extract_theme_css(builder())
    validate_css_safety(css)
    validate_link_contract(css)
    records = validate_selector_contract(
        css,
        getattr(_design, "THEME_SELECTOR_CONTRACT", None),
    )
    contract_rows = _contract_manifest_rows(records)
    payload = {
        "records": contract_rows,
        "owners": {
            selector: list(owners)
            for selector, owners in selector_owner_contract(records).items()
        },
        "important": sorted(
            [record.selector, record.property]
            for record in records
            if record.important
        ),
    }
    return tuple(records), {
        **payload,
        "cssSha256": hashlib.sha256(css.encode("utf-8")).hexdigest(),
        "sha256": hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest(),
    }


def _wait_for_formal_theme_app(
    process: subprocess.Popen[Any],
    port: int,
    *,
    timeout: float = 45.0,
) -> None:
    deadline = time.monotonic() + timeout
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url = f"http://127.0.0.1:{port}/_stcore/health"
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise ServerExited(
                f"calibrated theme app exited before health with {return_code}"
            )
        try:
            with opener.open(url, timeout=0.5) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError, TimeoutError):
            pass
        time.sleep(0.05)
    raise ServerExited("calibrated theme app health timed out")


def _terminate_formal_processes(
    isolation: Any,
    processes: Sequence[subprocess.Popen[Any]],
    attempted: set[int],
) -> BaseException | None:
    first: BaseException | None = None
    for process in processes:
        if id(process) in attempted:
            continue
        try:
            isolation.terminate_owned_process_group(process)
            attempted.add(id(process))
        except BaseException as exc:
            first = first or exc
    return first


def _finalize_formal_theme_cleanup(
    isolation: Any,
    owned: ThemeFormalRuntime,
    *,
    processes: Sequence[subprocess.Popen[Any]],
    attempted: set[int],
    verified_captures: Sequence[Any],
) -> BaseException | None:
    """Retry quiescence, quarantining the full leased runtime if it persists."""

    cleanup_error: BaseException | None = None
    for _attempt in range(3):
        cleanup_error = _terminate_formal_processes(
            isolation,
            processes,
            attempted,
        )
        if cleanup_error is None:
            break
    for capture in tuple(verified_captures):
        with contextlib.suppress(BaseException):
            capture.close()
    if cleanup_error is not None:
        # Keep the lease/root descriptors live rather than authorizing cleanup
        # while a child family may still own writers.
        _RETAINED_FAILED_THEME_RUNTIMES.append(owned)
        return cleanup_error
    return _release_theme_formal_runtime(owned)


def _theme_public_error(
    exc: BaseException,
    private_roots: Sequence[Path],
) -> dict[str, str]:
    message = str(exc)
    for root in sorted((str(path) for path in private_roots), key=len, reverse=True):
        message = message.replace(root, "[REDACTED]")
    for pattern, replacement in _CREDENTIAL_PATTERNS:
        message = pattern.sub(replacement, message)
    message = _URI_USERINFO_RE.sub(r"\1<redacted>@", message)
    message = _ABSOLUTE_PATH_RE.sub("[REDACTED_PATH]", message)
    error_type = re.sub(r"[^A-Za-z0-9_]", "", type(exc).__name__)[
        :MAX_DIAGNOSTIC_TYPE_CHARS
    ] or "Error"
    return {"type": error_type, "message": message[:MAX_DIAGNOSTIC_MESSAGE_CHARS]}


def _run_formal_theme_matrix(
    args: argparse.Namespace,
) -> tuple[int, dict[str, Any]]:
    """Run the three authority captures through the shared UX1B lifecycle."""

    selected = _select_browsers(args.browser)
    if selected != ("chromium",):
        raise ThemeContractError("formal theme capture requires exact Chromium")
    evidence = _evidence_api()
    isolation = _isolation_api()
    _ensure_workspace_import_path()
    from scripts import ui_ux_fixtures as fixtures

    rows = evidence.worker_capture_profile_rows(
        "scripts/ui_ux_theme_fixture_app.py"
    )
    if len(rows) != 3:
        raise ThemeContractError("formal theme worker catalog must contain three rows")
    run_id = f"ux1b-{secrets.token_hex(16)}"
    destination = args.out_dir or _default_run_dir()
    owned = _prepare_theme_formal_runtime(
        destination=destination,
        run_id=run_id,
    )
    lifecycle = owned.lifecycle
    runtime = owned.runtime
    final_root = owned.final_root
    app_root = owned.app_root
    browser_root = owned.browser_root
    final_root_fd = owned.final_root_fd
    browser_root_fd = owned.browser_root_fd
    verified_captures: list[Any] = []
    partial_artifact_payloads: list[dict[str, Any]] = []
    owned_processes: list[subprocess.Popen[Any]] = []
    cleanup_attempted: set[int] = set()
    output_published = False
    manifest: dict[str, Any] = {}
    code = 1
    private_roots = (runtime.path, final_root, app_root, browser_root)
    try:
        lifecycle.start()
        # Production theme/token/selector validation is part of the guarded
        # lifecycle.  Any catchable post-theme defect therefore leaves a
        # terminal manifest instead of escaping before evidence exists.
        records, selector_contract = _theme_static_contract()
        theme_source_digest_start = source_digest()
        _reauthenticate_theme_output_namespace(owned.namespace)
        stack_contract, _stack_catalog, stack_contract_sha256 = (
            _authenticate_theme_capture_stack(owned.namespace.workspace_fd)
        )
        capture_stack_digest_value = stack_contract["captureStackDigest"]

        mirror = isolation.build_source_mirror(
            workspace_root_fd=owned.namespace.workspace_fd,
            run_root=runtime.path / "mirror",
            policy=isolation.SourceMirrorPolicy(
                include=_expanded_ux1b_source_mirror_policy(),
                exclude=(
                    ".agents",
                    ".claude",
                    ".git",
                    ".venv",
                    ".env*",
                    "__pycache__",
                    "data",
                    "reports",
                ),
            ),
        )
        source_start = isolation.authenticate_source_mirror(
            mirror,
            expected_digest=mirror.digest,
        )
        if source_start.get("digest") != mirror.digest:
            raise ThemeContractError("theme source mirror digest differs")

        browser_executable, browser_sha256 = (
            isolation._playwright_chromium_identity()
        )
        browser_cache = isolation._playwright_browser_cache_root(
            browser_executable
        )
        app_port = _free_loopback_port()
        denied_port = _free_loopback_port()
        while denied_port in {app_port, 8000} or app_port == 8000:
            app_port = _free_loopback_port()
            denied_port = _free_loopback_port()
        contract = isolation.DarwinIsolationContract(
            workspace_root=WORKSPACE_ROOT,
            source_root=mirror.source_root,
            app_writable_root=app_root,
            browser_writable_root=browser_root,
            final_evidence_root=final_root,
            python_executable=Path(sys.executable).expanduser().absolute(),
            python_runtime_roots=(Path(sys.prefix).resolve(),),
            browser_executable=browser_executable,
            browser_runtime_roots=(browser_cache,),
            production_probe_path=WORKSPACE_ROOT / "app.py",
            app_port=app_port,
            denied_port=denied_port,
        )
        profiles = isolation.build_darwin_profiles(contract)
        app_environment = isolation.build_child_environment(
            role="app",
            source_root=mirror.source_root,
            writable_root=app_root,
            inherited=os.environ,
            python_runtime_roots=contract.python_runtime_roots,
        )
        browser_environment = isolation.build_child_environment(
            role="browser",
            source_root=mirror.source_root,
            writable_root=browser_root,
            inherited=os.environ,
            python_runtime_roots=contract.python_runtime_roots,
        )
        (browser_root / "staging").mkdir(mode=0o700)
        (browser_root / "stdio").mkdir(mode=0o700)
        fixture_root = app_root / "fixture-root"
        fixture_root.mkdir(mode=0o700)
        for relative in (
            "candidates",
            "ai-chat",
            "analytics",
            "tmp",
            "theme-gallery",
        ):
            (fixture_root / relative).mkdir(mode=0o700)
        run_token = secrets.token_urlsafe(32)
        _theme_write_private_file(
            app_root / fixtures.OWNERSHIP_MARKER,
            (run_token + "\n").encode("utf-8"),
        )
        fixture_contract = fixtures.build_owned_run_contract(
            run_token=run_token,
            profile=fixtures.UX1B_THEME_PROFILE,
            phase="posttheme",
            streamlit_port=app_port,
            deny_proxy_port=denied_port,
        )
        _theme_write_private_file(
            Path(app_environment["HOME"])
            / fixtures.UX1B_RUN_CONTRACT_FILENAME,
            _theme_canonical_ndjson(fixture_contract).rstrip(b"\n"),
        )

        calibration = isolation.calibrate_darwin_profiles(
            contract,
            profiles=profiles,
        )
        calibration_attestation = evidence.mint_calibration_attestation(
            calibration
        )
        app_origin = f"http://127.0.0.1:{app_port}"
        staged: dict[str, ThemeStagedCapture] = {}
        browser_proofs: dict[str, Any] = {}
        worker_request_sha256: dict[str, str] = {}
        app_process: subprocess.Popen[Any] | None = None

        with contextlib.ExitStack() as app_stack:
            app_stdio = app_stack.enter_context(
                isolation.owned_child_stdio(
                    app_root / "app-stdio",
                    role="app",
                )
            )
            app_command = (
                str(isolation.SANDBOX_EXEC),
                "-p",
                profiles.app,
                str(contract.python_executable),
                "-m",
                "streamlit",
                "run",
                "scripts/ui_ux_theme_fixture_app.py",
                "--server.address",
                "127.0.0.1",
                "--server.port",
                str(app_port),
                "--server.headless",
                "true",
                "--server.fileWatcherType",
                "none",
                "--server.runOnSave",
                "false",
                "--browser.gatherUsageStats",
                "false",
            )
            app_launch_args = {
                "session_id": run_id,
                "process_id": "app/theme",
                "contract": contract,
                "profiles": profiles,
                "calibration": calibration,
                "role": "app",
                "command": app_command,
                "cwd": mirror.source_root,
                "environment": app_environment,
                "stdio": app_stdio,
            }
            app_authorization = isolation.authorize_calibrated_launch(
                **app_launch_args
            )
            app_process = isolation.spawn_calibrated_child(
                authorization=app_authorization,
                **app_launch_args,
            )
            owned_processes.append(app_process)
            _wait_for_formal_theme_app(app_process, app_port)

            for index, row in enumerate(rows):
                capture_id = f'{row["case"]}/{row["viewport"]["name"]}'
                request = _theme_worker_request(
                    viewport_name=row["viewport"]["name"],
                    viewport=(row["viewport"]["width"], row["viewport"]["height"]),
                    app_origin=app_origin,
                )
                request_raw = _theme_canonical_ndjson(request)
                worker_request_sha256[capture_id] = hashlib.sha256(
                    request_raw
                ).hexdigest()
                allowed_paths = frozenset(request["staging"].values())
                evidence.decode_worker_request(
                    request_raw,
                    expected_origin=app_origin,
                    allowed_staging_paths=allowed_paths,
                )
                worker_tail = evidence.build_browser_worker_command(
                    contract.python_executable,
                    "scripts/ui_ux_browser_worker.py",
                    expected_origin=app_origin,
                    expected_request_id=capture_id,
                    allowed_staging_paths=tuple(allowed_paths),
                    browser_executable=browser_executable,
                    timeout_ms=90_000,
                )
                browser_command = (
                    str(isolation.SANDBOX_EXEC),
                    "-p",
                    profiles.browser,
                    *worker_tail,
                )
                with isolation.owned_child_stdio(
                    browser_root / "stdio" / f"capture-{index:03d}",
                    role="browser",
                ) as browser_stdio:
                    _write_worker_stdin(browser_stdio, request_raw)
                    browser_launch_args = {
                        "session_id": run_id,
                        "process_id": capture_id,
                        "contract": contract,
                        "profiles": profiles,
                        "calibration": calibration,
                        "role": "browser",
                        "command": browser_command,
                        "cwd": mirror.source_root,
                        "environment": browser_environment,
                        "stdio": browser_stdio,
                    }
                    browser_authorization = isolation.authorize_calibrated_launch(
                        **browser_launch_args
                    )
                    browser_process = isolation.spawn_calibrated_child(
                        authorization=browser_authorization,
                        **browser_launch_args,
                    )
                    owned_processes.append(browser_process)
                    try:
                        browser_proof = (
                            isolation.wait_for_clean_owned_process_group_exit(
                                browser_process,
                                timeout=120.0,
                            )
                        )
                    except BaseException:
                        isolation.terminate_owned_process_group(browser_process)
                        cleanup_attempted.add(id(browser_process))
                        raise
                    isolation.terminate_owned_process_group(browser_process)
                    cleanup_attempted.add(id(browser_process))
                    response_raw = _read_worker_private_file(
                        Path(browser_stdio.stdout.name),
                        root=browser_root,
                        maximum=evidence.MAX_WORKER_RESPONSE_BYTES,
                        label="theme worker response",
                    )
                    response = evidence.decode_worker_response(
                        response_raw,
                        expected_request_id=capture_id,
                        allowed_artifact_paths=allowed_paths,
                    )
                    if response["status"] != "staged":
                        error_type = (response.get("error") or {}).get(
                            "type", "WorkerError"
                        )
                        raise ThemeContractError(
                            f"theme worker failed for {capture_id}: {error_type}"
                        )
                raw_sidecar = evidence.authenticate_raw_render_sidecar(
                    browser_root_fd,
                    request["staging"]["renderSidecar"],
                    expected_owner=os.getuid(),
                    identity_row=row,
                )
                full_page_png = _read_descriptor_authenticated_worker_artifact(
                    evidence,
                    browser_root_fd,
                    request["staging"]["png"],
                    maximum=evidence.MAX_PNG_BYTES,
                    label="theme worker full-page PNG",
                )
                raw_document = raw_sidecar["document"]
                rich = adapt_external_worker_theme_evidence(
                    request=request,
                    response=response,
                    sidecar=raw_document,
                    full_page_png=full_page_png,
                    records=records,
                    expected_selector_contract_sha256=selector_contract["sha256"],
                    expected_source_digest=theme_source_digest_start,
                )
                staged[capture_id] = ThemeStagedCapture(
                    capture_id=capture_id,
                    png_path=request["staging"]["png"],
                    raw_sidecar=raw_sidecar,
                    raw_document=copy.deepcopy(raw_document),
                    rich_evidence=copy.deepcopy(rich),
                    browser_proof=browser_proof,
                )
                browser_proofs[capture_id] = browser_proof

            if app_process.poll() is not None:
                raise ServerExited("theme app exited before matrix completion")
            os.killpg(app_process.pid, signal.SIGINT)
            app_proof = isolation.wait_for_clean_owned_process_group_exit(
                app_process,
                timeout=20.0,
            )
            isolation.terminate_owned_process_group(app_process)
            cleanup_attempted.add(id(app_process))
            app_process = None

        expected_counters = _theme_counter_expectations(
            rows,
            app_root=app_root,
        )
        app_root_fd = _theme_directory_fd(app_root)
        try:
            authenticated_counters = evidence.authenticate_counter_bundle(
                app_root_fd,
                "fixture-calls.json",
                expected_owner=os.getuid(),
                expected_captures=expected_counters,
            )
        finally:
            os.close(app_root_fd)
        if authenticated_counters["completeMatrix"] is not True:
            raise ThemeContractError("theme counter bundle is not a complete matrix")

        capture_records: list[dict[str, Any]] = []
        selector_evidence: list[Mapping[str, Any]] = []
        diagnostics: dict[str, Any] = {}
        supplement_count = 0
        for capture_id in sorted(staged):
            viewport_name = capture_id.split("/", 1)[1]
            capture_root = final_root / "captures" / "theme-gallery" / viewport_name
            capture_root.mkdir(parents=True, mode=0o700)
            capture_root_fd = _theme_directory_fd(capture_root)
            try:
                item = staged[capture_id]
                record = evidence.publish_finalized_capture(
                    browser_root_fd,
                    capture_root_fd,
                    expected_owner=os.getuid(),
                    staged_png_path=item.png_path,
                    authenticated_raw_sidecar=item.raw_sidecar,
                    authenticated_counters=authenticated_counters,
                    capture_id=capture_id,
                    output_png_name="capture.png",
                    output_sidecar_name="render.json",
                )
                parent_contract = evidence.freeze_artifact_contract(
                    capture_root_fd,
                    "capture.png",
                    expected_owner=os.getuid(),
                    max_bytes=evidence.MAX_PNG_BYTES,
                )
                with evidence.open_authenticated_artifact(
                    capture_root_fd,
                    parent_contract,
                ) as parent_png:
                    supplements = [
                        evidence.publish_derived_artifact(
                            parent_png,
                            capture_root_fd,
                            expected_owner=os.getuid(),
                            artifact_id=surface["name"],
                            output_name=f'surface-{surface["name"]}.png',
                            crop=surface["geometry"]["crop"],
                            theme_evidence_sha256=item.rich_evidence["sha256"],
                        )
                        for surface in item.rich_evidence["surfaces"]
                    ]
                verified = evidence.verify_capture_artifacts(
                    capture_root_fd,
                    record,
                    expected_owner=os.getuid(),
                    run_root_fd=final_root_fd,
                    supplemental_artifacts=supplements,
                )
            finally:
                os.close(capture_root_fd)
            verified_captures.append(verified)
            partial_artifact_payloads.append(copy.deepcopy(dict(verified)))
            capture_records.append(
                {"id": capture_id, "status": "passed", "artifacts": verified}
            )
            supplement_count += len(supplements)
            selector_evidence.append(
                copy.deepcopy(item.rich_evidence["selectorEvidence"])
            )
            diagnostics[capture_id] = copy.deepcopy(
                item.raw_document["stableState"]["diagnostics"]
            )

        source_end = isolation.authenticate_source_mirror(
            mirror,
            expected_digest=mirror.digest,
        )
        if source_end.get("digest") != source_start.get("digest"):
            raise ThemeContractError("theme source mirror changed during capture")
        if source_digest() != theme_source_digest_start:
            raise ThemeContractError("theme source projection changed during capture")
        _reauthenticate_theme_output_namespace(owned.namespace)
        closing_stack, _closing_catalog, closing_stack_sha256 = (
            _authenticate_theme_capture_stack(owned.namespace.workspace_fd)
        )
        if (
            closing_stack_sha256 != stack_contract_sha256
            or closing_stack["captureStackDigest"]
            != capture_stack_digest_value
        ):
            raise ThemeContractError("theme capture stack changed during capture")
        if (
            set(diagnostics)
            != {
                "theme-gallery/desktop",
                "theme-gallery/tablet",
                "theme-gallery/mobile",
            }
            or any(any(value != 0 for value in row.values()) for row in diagnostics.values())
            or supplement_count != 9
        ):
            raise ThemeContractError("theme diagnostics or supplement matrix differs")

        persisted_audit = _theme_persisted_audit_evidence(
            calibration=calibration,
            worker_request_sha256=worker_request_sha256,
            app_origin=app_origin,
            app_port=app_port,
            denied_port=denied_port,
            browser_executable_sha256=browser_sha256,
        )
        lifecycle.mark_finalizing(
            {
                "captureStackDigest": capture_stack_digest_value,
                "captureStackContract": {
                    "path": UX1B_CAPTURE_STACK_CONTRACT_PATH.relative_to(
                        WORKSPACE_ROOT
                    ).as_posix(),
                    "sha256": stack_contract_sha256,
                },
                "sourceDigestStart": mirror.digest,
                "sourceDigestEnd": mirror.digest,
                "themeSourceDigest": theme_source_digest_start,
                "selectorContract": selector_contract,
                "selectorEvidence": selector_evidence,
                **persisted_audit,
                "diagnostics": diagnostics,
                "childrenQuiescent": True,
                "capturedCount": 3,
                "supplementalArtifactCount": 9,
                "summary": {"passed": 3, "failed": 0, "total": 3},
            }
        )
        comparator_report = evidence.validate_live_capture_profile(
            verified_captures,
            fixture_entrypoint="scripts/ui_ux_theme_fixture_app.py",
            capture_stack_digest=capture_stack_digest_value,
        )
        comparator_attestation = evidence.mint_comparator_attestation(
            comparator_report
        )
        provider_counters, mutator_counters = _sum_theme_counters(
            authenticated_counters
        )
        closure = evidence.validate_success_closure(
            {
                "status": "finalizing",
                "captureStackDigest": capture_stack_digest_value,
                "sourceDigestStart": mirror.digest,
                "sourceDigestEnd": mirror.digest,
                "captures": capture_records,
                "providerCounters": {
                    "expected": provider_counters,
                    "actual": provider_counters,
                },
                "mutatorCounters": {
                    "expected": mutator_counters,
                    "actual": mutator_counters,
                },
                "prohibitedCounters": {
                    "production.read": 0,
                    "production.write": 0,
                    "network.outbound": 0,
                },
                "processes": {
                    "app": app_proof,
                    "browsers": browser_proofs,
                },
                "network": {"appOrigin": app_origin, "appPort": app_port},
            },
            lifecycle=lifecycle,
            expected_fixture_entrypoint="scripts/ui_ux_theme_fixture_app.py",
            expected_capture_stack_digest=capture_stack_digest_value,
            expected_source_digest=mirror.digest,
            expected_app_origin=app_origin,
            calibration_attestation=calibration_attestation,
            comparator_attestation=comparator_attestation,
        )
        grant = evidence.authorize_success_closure(
            lifecycle,
            validated_closure=closure,
        )
        _export_theme_final_root(owned)
        output_published = True
        finalized = evidence.finalize_terminal_manifest(
            lifecycle,
            grant=grant,
        )
        expected_manifest_sha256 = hashlib.sha256(
            _theme_canonical_ndjson(finalized)
        ).hexdigest()
        try:
            bundle_contract = evidence.freeze_manifest_bundle_contract(
                final_root_fd,
                "manifest.json",
                expected_owner=os.getuid(),
                expected_manifest_sha256=expected_manifest_sha256,
            )
            bundle = evidence.reauthenticate_manifest_bundle(
                final_root_fd,
                bundle_contract,
            )
            if bundle.manifest != finalized:
                raise ThemeContractError("theme passed bundle manifest differs")
        except BaseException:
            _make_theme_manifest_unreferenceable(final_root_fd)
            raise
        manifest = finalized
        code = 0
    except BaseException as exc:
        cleanup_error = _terminate_formal_processes(
            isolation,
            owned_processes,
            cleanup_attempted,
        )
        terminal_error = cleanup_error or exc
        if lifecycle.state == "passed":
            with contextlib.suppress(BaseException):
                _make_theme_manifest_unreferenceable(final_root_fd)
            manifest = {
                "status": "failed",
                "error": _theme_public_error(terminal_error, private_roots),
            }
            code = 1
        else:
            if isinstance(exc, KeyboardInterrupt):
                status, code = "interrupted", 130
            elif isinstance(
                exc,
                (
                    DependencyUnavailable,
                    evidence.DependencyUnavailable,
                    isolation.DependencyUnavailable,
                ),
            ):
                status, code = "dependency_unavailable", 127
            elif isinstance(exc, (ThemeContractError, evidence.InvalidEvidence)):
                status, code = "invalid_data", 3
            else:
                status, code = "failed", 1
            if lifecycle.state in {"running", "finalizing"}:
                updates: dict[str, Any] = {
                    "error": _theme_public_error(terminal_error, private_roots),
                }
                if partial_artifact_payloads:
                    updates["partialArtifacts"] = copy.deepcopy(
                        partial_artifact_payloads
                    )
                manifest = lifecycle.mark_terminal(status, updates)
            else:
                manifest = {"status": status, **updates} if "updates" in locals() else {
                    "status": status,
                    "error": _theme_public_error(terminal_error, private_roots),
                }
            if not output_published and lifecycle.state in {
                "failed",
                "invalid_data",
                "dependency_unavailable",
                "interrupted",
            }:
                try:
                    _export_theme_final_root(owned)
                    output_published = True
                except BaseException as export_error:
                    code = 1
                    manifest = {
                        "status": "failed",
                        "error": _theme_public_error(export_error, private_roots),
                    }
            if output_published:
                with contextlib.suppress(BaseException):
                    manifest = _read_theme_manifest(final_root_fd)
    finally:
        cleanup_error = _finalize_formal_theme_cleanup(
            isolation,
            owned,
            processes=owned_processes,
            attempted=cleanup_attempted,
            verified_captures=verified_captures,
        )
        if cleanup_error is not None:
            code = 1
    return code, manifest


def _run_browsers(
    *,
    selected: Sequence[str],
    port: int,
    process: subprocess.Popen[bytes],
    owned: OwnedThemeRun,
    records: Sequence[SelectorContractRecord],
    manifest: dict[str, Any],
    worker_session: ThemeBrowserWorkerSession,
) -> None:
    """Run only the frozen external worker through calibrated isolation."""

    if tuple(selected) != ("chromium",):
        raise ThemeContractError("theme external worker requires exact Chromium")
    if process.poll() is not None:
        raise ServerExited("owned Streamlit gallery exited before worker capture")
    try:
        from importlib.metadata import version as package_version

        manifest["tools"]["playwright"] = package_version("playwright")
    except Exception as exc:
        raise DependencyUnavailable(
            "Playwright is not installed in the project environment"
        ) from exc

    evidence = _evidence_api()
    isolation = _isolation_api()
    manifest["tools"]["themeSourceMirrorSha256"] = worker_session.mirror_digest
    app_origin = f"http://127.0.0.1:{port}"
    for viewport_name, viewport in VIEWPORTS.items():
        request = _theme_worker_request(
            viewport_name=viewport_name,
            viewport=viewport,
            app_origin=app_origin,
        )
        request_raw = (canonical_json(request) + "\n").encode("utf-8")
        allowed_paths = frozenset(request["staging"].values())
        evidence.decode_worker_request(
            request_raw,
            expected_origin=app_origin,
            allowed_staging_paths=allowed_paths,
        )
        worker_command = build_browser_worker_command(
            worker_session.contract.python_executable,
            BROWSER_WORKER_PATH,
            expected_origin=app_origin,
            expected_request_id=request["requestId"],
            allowed_staging_paths=tuple(allowed_paths),
            browser_executable=worker_session.contract.browser_executable,
            timeout_ms=90_000,
        )
        command = (
            str(isolation.SANDBOX_EXEC),
            "-p",
            worker_session.profiles.browser,
            *worker_command,
        )
        stdio_root = worker_session.browser_root / f"stdio-{viewport_name}"
        with isolation.owned_child_stdio(stdio_root, role="browser") as stdio:
            _write_worker_stdin(stdio, request_raw)
            launch = {
                "session_id": worker_session.session_id,
                "process_id": request["requestId"],
                "contract": worker_session.contract,
                "profiles": worker_session.profiles,
                "calibration": worker_session.calibration,
                "role": "browser",
                "command": command,
                "cwd": worker_session.source_root,
                "environment": worker_session.environment,
                "stdio": stdio,
            }
            authorization = isolation.authorize_calibrated_launch(**launch)
            worker_process: subprocess.Popen[Any] | None = None
            closed = False
            try:
                worker_process = isolation.spawn_calibrated_child(
                    authorization=authorization, **launch
                )
                exit_proof = isolation.wait_for_clean_owned_process_group_exit(
                    worker_process, timeout=120.0
                )
                closed = True
                exit_row, exit_digest = (
                    isolation.consume_quiescent_process_exit_provenance(
                        exit_proof,
                        expected_session_id=worker_session.session_id,
                        expected_role="browser",
                        expected_process_id=request["requestId"],
                    )
                )
            finally:
                if worker_process is not None and not closed:
                    with contextlib.suppress(Exception):
                        isolation.terminate_owned_process_group(worker_process)

            response_raw = _read_worker_private_file(
                Path(stdio.stdout.name),
                root=worker_session.browser_root,
                maximum=evidence.MAX_WORKER_RESPONSE_BYTES,
                label="theme worker response",
            )
            response = evidence.decode_worker_response(
                response_raw,
                expected_request_id=request["requestId"],
                allowed_artifact_paths=allowed_paths,
            )
            browser_root_fd = os.open(
                worker_session.browser_root,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
            )
            try:
                identity_row = evidence.validate_worker_capture_identity(request)
                authenticated_sidecar = evidence.authenticate_raw_render_sidecar(
                    browser_root_fd,
                    request["staging"]["renderSidecar"],
                    expected_owner=os.getuid(),
                    identity_row=identity_row,
                )
                full_page_png = _read_descriptor_authenticated_worker_artifact(
                    evidence,
                    browser_root_fd,
                    request["staging"]["png"],
                    maximum=evidence.MAX_PNG_BYTES,
                    label="theme worker full-page PNG",
                )
            finally:
                os.close(browser_root_fd)
            sidecar = authenticated_sidecar["document"]
            rich = adapt_external_worker_theme_evidence(
                request=request,
                response=response,
                sidecar=sidecar,
                full_page_png=full_page_png,
                records=records,
                expected_selector_contract_sha256=manifest["selectorContract"][
                    "sha256"
                ],
                expected_source_digest=manifest["sourceDigestStart"],
            )
            manifest["selectorEvidence"].append(
                dict(rich["selectorEvidence"])
            )
            manifest["captures"].extend(
                _materialize_external_worker_theme_captures(
                    rich=rich,
                    full_page_png=full_page_png,
                    owned=owned,
                    source_digest_value=manifest["sourceDigestStart"],
                )
            )
            manifest["tools"].setdefault("browserWorkerExit", []).append(
                {
                    **dict(exit_row),
                    "sha256": exit_digest,
                }
            )


def _run_legacy_theme_matrix(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    """Run the fail-closed owned browser matrix and persist canonical evidence."""

    selected = _select_browsers(args.browser)
    owned = create_owned_run(args.out_dir)
    manifest = _manifest_template(owned, selected)
    server: OwnedThemeServer | None = None
    atomic_write_json(owned.manifest_path, manifest)
    old_handlers: dict[int, Any] = {}

    def interrupted(_signum: int, _frame: Any) -> None:
        raise RunnerInterrupted()

    for signum in (signal.SIGINT, signal.SIGTERM):
        old_handlers[signum] = signal.getsignal(signum)
        signal.signal(signum, interrupted)
    run_authority: _RunSuccessAuthority | None = None
    runtime_closed = False
    terminal_commit_complete = False

    def close_runtime() -> BaseException | None:
        nonlocal runtime_closed
        if runtime_closed:
            return None
        problem = _retire_run_runtime(run_authority, old_handlers)
        runtime_closed = True
        return problem

    def apply_runtime_problem(
        problem: BaseException | None, code: int
    ) -> int:
        if isinstance(problem, KeyboardInterrupt):
            manifest["status"] = "interrupted"
            manifest["interruption"] = _terminal_diagnostic(problem, owned)
            return 130
        if isinstance(problem, Exception) and manifest.get("status") != "interrupted":
            manifest["status"] = "failed"
            manifest["finalizationError"] = _terminal_diagnostic(problem, owned)
            return 1
        return code

    def close_and_commit(code: int) -> int:
        """Retire runtime and commit while terminal signals stay blocked."""

        terminal_signal_mask: set[signal.Signals] | None = None
        try:
            try:
                terminal_signal_mask = _block_terminal_signals()
            except KeyboardInterrupt as exc:
                if manifest.get("status") != "failed":
                    manifest["status"] = "interrupted"
                    manifest["interruption"] = _terminal_diagnostic(exc, owned)
                    code = 130
            except Exception as exc:
                if manifest.get("status") != "interrupted":
                    manifest["status"] = "failed"
                    manifest["finalizationError"] = _terminal_diagnostic(exc, owned)
                    code = 1
            code = apply_runtime_problem(close_runtime(), code)
            return _commit_terminal_manifest(owned, manifest, code)
        finally:
            if terminal_signal_mask is not None:
                _restore_terminal_signal_mask(terminal_signal_mask)

    try:
        # Registered inline so caller-owned mappings cannot bootstrap a valid
        # success capability for this manifest or output run.
        run_authority = object.__new__(_RunSuccessAuthority)
        owned_binding = _owned_run_binding(owned)
        with _FINALIZATION_GRANTS_LOCK:
            _RUN_SUCCESS_AUTHORITIES[id(run_authority)] = (
                run_authority,
                os.getpid(),
                manifest,
                owned,
                owned_binding,
            )
        from ui import _design

        builder = getattr(_design, "build_global_theme_css", None)
        if not callable(builder):
            raise ThemeContractError("production theme CSS builder is unavailable")
        validate_palette_contract(APPROVED_TOKENS, SURFACE_COLORS)
        validate_design_token_contract(_design)
        css = extract_theme_css(builder())
        validate_css_safety(css)
        validate_link_contract(css)
        raw_contract = getattr(_design, "THEME_SELECTOR_CONTRACT", None)
        records = validate_selector_contract(css, raw_contract)
        contract_rows = _contract_manifest_rows(records)
        contract_payload = {
            "records": contract_rows,
            "owners": {
                selector: list(owners)
                for selector, owners in selector_owner_contract(records).items()
            },
            "important": sorted([
                [record.selector, record.property]
                for record in records if record.important
            ]),
        }
        manifest["selectorContract"] = {
            **contract_payload,
            "cssSha256": hashlib.sha256(css.encode("utf-8")).hexdigest(),
            "sha256": hashlib.sha256(
                canonical_json(contract_payload).encode("utf-8")
            ).hexdigest(),
        }
        atomic_write_json(owned.manifest_path, manifest)

        gallery_port = _free_loopback_port()
        with _theme_browser_worker_session(
            gallery_port
        ) as worker_session, _owned_gallery_server(
            owned, port=gallery_port
        ) as server:
            manifest["server"] = {
                "origin": f"http://127.0.0.1:{server.port}",
                "pid": server.process.pid,
                "owned": True,
                "externalNetworkAllowed": False,
                "allowedEndpoints": [
                    f"127.0.0.1:{server.port}",
                    f"127.0.0.1:{server.deny_proxy.port}",
                ],
                "allowedEndpointCount": 2,
                "api8000Allowed": False,
                "environment": dict(
                    _child_environment_evidence(server.child_environment, owned)
                ),
                "kernelIsolation": server.sandbox_calibration.get("capability"),
                "sandboxCalibration": dict(server.sandbox_calibration),
                "denyProxyAttemptCount": None,
                "denyProxyAttempts": None,
                "pythonSocketGuard": None,
                "terminated": None,
                "returnCode": None,
            }
            _run_browsers(
                selected=selected,
                port=server.port,
                process=server.process,
                owned=owned,
                records=records,
                manifest=manifest,
                worker_session=worker_session,
            )

        # Read attempt evidence only after the process is terminated, so a
        # background task cannot race the final zero-attempt claim.
        proxy_attempts, socket_evidence = _record_server_attempt_evidence(
            manifest, server
        )
        if not manifest["server"]["terminated"]:
            raise ThemeContractError("owned theme child did not terminate before evidence closure")
        environment_evidence = manifest["server"]["environment"]
        if not all((
            environment_evidence.get("allowlistApplied"),
            environment_evidence.get("credentialFree"),
            environment_evidence.get("privateDirectories"),
            environment_evidence.get("proxyContractExact"),
        )):
            raise ThemeContractError("theme child environment isolation evidence failed")
        if proxy_attempts:
            raise ThemeContractError("theme child contacted the owned deny proxy")
        if socket_evidence["attemptCount"] != 0:
            raise ThemeContractError("theme child attempted outbound socket or DNS access")

        manifest["sourceDigestEnd"] = source_digest()
        if manifest["sourceDigestEnd"] != manifest["sourceDigestStart"]:
            raise ThemeContractError("source digest changed while the matrix was running")
        expected_ids = {
            f"{browser}-{viewport}-{surface}"
            for browser in selected
            for viewport in VIEWPORTS
            for surface in SURFACE_COLORS
        }
        actual_ids = [row["id"] for row in manifest["captures"]]
        if (
            len(actual_ids) != len(expected_ids)
            or len(set(actual_ids)) != len(actual_ids)
            or set(actual_ids) != expected_ids
            or any(row.get("status") != "passed" for row in manifest["captures"])
        ):
            raise ThemeContractError("capture identity/status set differs from the exact matrix")
        if len(manifest["selectorEvidence"]) != len(selected) * len(VIEWPORTS):
            raise ThemeContractError("selector evidence viewport matrix is incomplete")
        if manifest["blockedNetwork"] or manifest["exceptions"]:
            raise ThemeContractError("matrix contains blocked network or browser exceptions")
        manifest["summary"] = {
            "passed": len(actual_ids),
            "failed": 0,
            "total": len(expected_ids),
        }
        manifest["status"] = "finalizing"
        atomic_write_json(owned.manifest_path, manifest)
        terminal_signal_mask = _block_terminal_signals()
        try:
            grant: _RunnerFinalizationGrant | None = None
            try:
                grant = _authorize_terminal_manifest(
                    manifest, authority=run_authority
                )
                if not finalize_terminal_manifest(manifest, grant=grant):
                    raise ThemeContractError("theme success closure was not authorized")
            finally:
                if grant is not None:
                    _discard_terminal_manifest_grant(grant)
            code = apply_runtime_problem(close_runtime(), 0)
            code = _commit_terminal_manifest(owned, manifest, code)
            terminal_commit_complete = True
        finally:
            _restore_terminal_signal_mask(terminal_signal_mask)
        return code, manifest
    except KeyboardInterrupt as exc:
        if terminal_commit_complete:
            raise
        if server is not None:
            with contextlib.suppress(BaseException):
                _record_server_attempt_evidence(manifest, server)
        with contextlib.suppress(BaseException):
            manifest["sourceDigestEnd"] = source_digest()
        if manifest.get("status") != "failed":
            manifest["status"] = "interrupted"
            manifest["interruption"] = _terminal_diagnostic(exc, owned)
        passed = sum(row.get("status") == "passed" for row in manifest["captures"])
        manifest["summary"] = {
            "passed": passed,
            "failed": manifest["expectedCaptureTotal"] - passed,
            "total": manifest["expectedCaptureTotal"],
        }
        code = 130 if manifest.get("status") == "interrupted" else 1
        code = close_and_commit(code)
        return code, manifest
    except Exception as exc:
        if terminal_commit_complete:
            raise
        late_interrupt: KeyboardInterrupt | None = None
        if server is not None:
            try:
                _record_server_attempt_evidence(manifest, server)
            except KeyboardInterrupt as interrupt_exc:
                late_interrupt = interrupt_exc
            except Exception:
                pass
        try:
            manifest["sourceDigestEnd"] = source_digest()
        except KeyboardInterrupt as interrupt_exc:
            late_interrupt = late_interrupt or interrupt_exc
        except Exception:
            pass
        if late_interrupt is not None:
            manifest["status"] = "interrupted"
            manifest["interruption"] = _terminal_diagnostic(
                late_interrupt, owned
            )
        elif manifest.get("status") != "interrupted":
            manifest["status"] = "failed"
            manifest["failure"] = _terminal_diagnostic(exc, owned)
        passed = sum(row.get("status") == "passed" for row in manifest["captures"])
        manifest["summary"] = {
            "passed": passed,
            "failed": manifest["expectedCaptureTotal"] - passed,
            "total": manifest["expectedCaptureTotal"],
        }
        code = 130 if late_interrupt is not None else (
            127 if isinstance(exc, DependencyUnavailable) else 1
        )
        code = close_and_commit(code)
        return code, manifest
    finally:
        if not runtime_closed:
            close_runtime()


def run_matrix(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    """Execute only the shared-lifecycle formal UX1B theme pipeline."""

    return _run_formal_theme_matrix(args)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    code, manifest = run_matrix(args)
    if args.json:
        print(canonical_json({"exitCode": code, "manifest": manifest}))
    elif not args.quiet:
        print(f"UX-1B theme matrix status={manifest['status']} exit={code}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
