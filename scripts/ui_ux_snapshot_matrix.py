#!/usr/bin/env python3
"""Capture deterministic UX-0/UX-1A/UX-1B evidence from an owned Streamlit process.

Playwright is an optional local test tool. The command never reuses or stops an
existing dashboard: it launches one fixture-only Streamlit child on an
ephemeral loopback port and owns that child's process group for the whole run.
"""

from __future__ import annotations

import argparse
import copy
import errno
import hashlib
import importlib.metadata
import json
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
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence


VERSION = "0.4.0"
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
# SOURCE_ROOT is deliberately a separate seam.  Task 5 replaces it with the
# authenticated read-only mirror without changing legacy UX-0/UX-1A callers.
SOURCE_ROOT = WORKSPACE_ROOT
ROOT = WORKSPACE_ROOT
BROWSER_WORKER_PATH = WORKSPACE_ROOT / "scripts" / "ui_ux_browser_worker.py"
UX1B_PROFILE = "ux1b-full-pages"
UX1B_SELECTION_PROFILE = "ux1b-selection-controls"
UX1B_PROFILES = (UX1B_PROFILE, UX1B_SELECTION_PROFILE)
UX1B_PROFILE_PHASES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        UX1B_PROFILE: ("precontrol", "pretheme", "posttheme"),
        UX1B_SELECTION_PROFILE: ("precontrol", "postcontrol"),
    }
)
UX1B_PHASES = tuple(
    dict.fromkeys(
        phase
        for profile_phases in UX1B_PROFILE_PHASES.values()
        for phase in profile_phases
    )
)
UX1B_CAPTURE_STACK_CONTRACT_PATH = (
    WORKSPACE_ROOT
    / "docs"
    / "ui-ux"
    / "quant-radar-ui-v2-ux1b-capture-stack.json"
)
UX1B_SEQUENCE12_CAPTURE_STACK_CONTRACT_PATH = (
    WORKSPACE_ROOT
    / "docs"
    / "ui-ux"
    / "quant-radar-ui-v2-ux1b-capture-stack-seq12.json"
)
UX1B_SEQUENCE13_CAPTURE_STACK_CONTRACT_PATH = (
    WORKSPACE_ROOT
    / "docs"
    / "ui-ux"
    / "quant-radar-ui-v2-ux1b-capture-stack-seq13.json"
)
UX1B_CAPTURE_STACK_CHOICES = ("legacy", "seq12", "seq13")
UX1B_FIXTURE_ENTRYPOINTS: Mapping[str, str] = MappingProxyType(
    {
        UX1B_PROFILE: "scripts/ui_ux_fixture_app.py",
        UX1B_SELECTION_PROFILE: "scripts/ui_ux_selection_fixture_app.py",
    }
)
UX1B_SELECTION_BASE_PATH = "__selection__"
UX1B_CAPTURE_STACK_MEMBERS = (
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
UX1B_SOURCE_MIRROR_INCLUDE = (
    ".streamlit/config.toml",
    "app.py",
    "api/**/*.py",
    "scripts/**/*.py",
    "ui/**/*.py",
    "docs/ui-ux/quant-radar-ui-v2-baseline.json",
)
UX1B_SOURCE_MIRROR_EXCLUDE = (
    ".agents/**",
    ".claude/**",
    ".git/**",
    ".venv/**",
    "**/.env*",
    "**/__pycache__/**",
    "**/*.db",
    "**/*.duckdb",
    "**/*.key",
    "**/*.pem",
    "**/*.pyc",
    "data/**",
    "reports/**",
)
LEGACY_COUNTER_SCHEMA_VERSION = 1
LEGACY_EXPECTED_FIXTURE_REVISION = "quant-radar-ux0-2026-07-16.2"
UX1B_EXPECTED_FIXTURE_REVISION = "quant-radar-ux1b-2026-07-16.1"
UX1B_EXPECTED_CONTRACT_SCHEMA_VERSION = 1
UX1B_THEME_CONTRACT_SCHEMA_VERSION = 1
UX1B_PROJECTION_SHA256 = "539bf737382a0f35aca3daaec681aa520152e1381a442904c73d3c61d416f015"
UX1B_READY_MARKERS_SHA256 = "691c846199e3fbbb11340b8ed6211a3aa638a0c02c0c8c9202c85a7ae1ebef81"
UX1B_THEME_CONTRACT_PATH = (
    ROOT / "docs" / "ui-ux" / "quant-radar-ui-v2-ux1b-theme-contract.json"
)
_CHILD_ENV_KEYS = {
    "COMSPEC",
    "LANG",
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
}
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
DEFAULT_PAGES = (
    "today-decision",
    "trade-state",
    "stock-checkup",
    "options-cockpit",
    "institutions",
    "schedules",
    "ai-updates",
)
FOCUSED_CASES = (
    "today-decision",
    "ai-chat-open",
    "ai-updates",
    "schedules",
    "institution-portfolio",
)
PAGE_HEADINGS = {
    "today-decision": "今日決策",
    "trade-state": "交易狀態",
    "stock-checkup": "個股總覽",
    "options-cockpit": "期權作戰台",
    "institutions": "機構面板",
    "schedules": "排程與執行結果",
    "ai-updates": "AI Agent 重點更新",
}
DEFAULT_VIEWPORTS = {
    "desktop": (1440, 900),
    "tablet": (768, 1024),
    "mobile": (390, 844),
}
UX1B_VIEWPORTS = (
    ("desktop", 1440, 900),
    ("tablet", 768, 1024),
    ("mobile", 390, 844),
)
UX1B_SELECTION_VIEWPORTS = UX1B_VIEWPORTS + (("narrow", 320, 844),)
_CAPTURE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,95}$")
_CUSTOM_VIEWPORT_RE = re.compile(r"^([1-9][0-9]{1,3})x([1-9][0-9]{1,3})$")
_OWNER_FILE = ".quant-radar-ux0-owner"
MAX_DIAGNOSTIC_MESSAGE_CHARS = 1_024
MAX_DIAGNOSTIC_TYPE_CHARS = 128
_DIAGNOSTIC_INPUT_CHARS = MAX_DIAGNOSTIC_MESSAGE_CHARS * 4
_RUNTIME_CLEANUP_ATTEMPTS = 3
_TERMINAL_SIGNALS = (signal.SIGINT, signal.SIGTERM)


class DependencyUnavailable(RuntimeError):
    """An optional local test dependency or requested browser is unavailable."""

    exit_code = 127


class ServerExited(RuntimeError):
    """The owned Streamlit process exited before becoming healthy."""

    def __init__(self, returncode: int):
        self.returncode = returncode
        super().__init__(f"owned Streamlit exited with code {returncode}")


class RunnerDataError(RuntimeError):
    """Fixture, inventory, or manifest data violated the runner contract."""


class CaptureNotQuiescent(RuntimeError):
    """A closed browser capture kept mutating its fixture counter bucket."""

    def __init__(self, latest: Mapping[str, Any]):
        self.latest = dict(latest)
        super().__init__("fixture capture counter did not quiesce before deadline")


class RunnerInterrupted(KeyboardInterrupt):
    """The runner received an interrupt while an owned child was active."""


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
_UX1B_RETAINED_RUNTIMES_LOCK = threading.Lock()
_UX1B_RETAINED_RUNTIMES: dict[
    int,
    tuple[Any, tuple[subprocess.Popen[Any], ...], BaseException],
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
    """Expose the app-profile builder without changing legacy launch paths."""

    _ensure_workspace_import_path()
    from scripts import ui_ux_isolation

    return ui_ux_isolation.build_app_sandbox_profile(*args, **kwargs)


def build_browser_sandbox_profile(*args: Any, **kwargs: Any) -> Any:
    """Expose the browser-profile builder without changing legacy launch paths."""

    _ensure_workspace_import_path()
    from scripts import ui_ux_isolation

    return ui_ux_isolation.build_browser_sandbox_profile(*args, **kwargs)


@dataclass(frozen=True, slots=True)
class PageProjection:
    registry_key: str
    route: str
    nav_title: str
    callable_name: str


@dataclass(frozen=True, slots=True)
class ReadyMarker:
    level: int
    text: str
    match: str


@dataclass(frozen=True, slots=True)
class UX1BNetworkContract:
    streamlit_port: int
    deny_proxy_port: int


@dataclass(frozen=True, slots=True)
class AuthenticatedPretheme:
    contract_path: Path
    manifest_path: Path
    manifest_sha256: str
    manifest: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class UX1BControlDiscovery:
    """Non-terminal 57-row discovery result; it carries no success manifest."""

    base_capture_stack_digest: str
    source_digest: str
    sidecars: tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class UX1BRealSmoke:
    """Disposable ten-row real-profile smoke result with no terminal claim."""

    base_capture_stack_digest: str
    source_digest: str
    capture_ids: tuple[str, ...]
    sidecars: tuple[Any, ...]
    pngs: tuple[Mapping[str, Any], ...]
    counter_capture_ids: tuple[str, ...]
    quiescent_process_count: int


@dataclass(frozen=True, slots=True)
class _UX1BNonterminalResult:
    base_capture_stack_digest: str
    source_digest: str
    capture_ids: tuple[str, ...]
    sidecars: tuple[Any, ...]
    pngs: tuple[Mapping[str, Any], ...]
    counter_capture_ids: tuple[str, ...]
    quiescent_process_count: int


@dataclass(frozen=True, slots=True)
class UX1BDirectoryBinding:
    """Exact named directory identity retained across namespace reauthentication."""

    name: str
    device: int
    inode: int
    owner_uid: int
    mode: int


@dataclass(slots=True)
class UX1BOutputNamespace:
    """Retained descriptor chain for one lexical UX1B output destination."""

    path: Path
    leaf_name: str
    workspace_fd: int
    ux1b_fd: int
    parent_fd: int
    workspace_binding: UX1BDirectoryBinding
    namespace_bindings: tuple[UX1BDirectoryBinding, ...]
    parent_bindings: tuple[UX1BDirectoryBinding, ...]
    _closed: bool = False

    def close(self) -> BaseException | None:
        if self._closed:
            return None
        self._closed = True
        first_error: BaseException | None = None
        for descriptor in (self.parent_fd, self.ux1b_fd, self.workspace_fd):
            try:
                os.close(descriptor)
            except BaseException as exc:
                first_error = first_error or exc
        return first_error


@dataclass(slots=True)
class UX1BCaptureStackDestination:
    """Retained exact workspace-to-docs publication chain."""

    workspace_fd: int
    parent_fd: int
    relative_path: str
    leaf_name: str
    workspace_binding: UX1BDirectoryBinding
    parent_bindings: tuple[UX1BDirectoryBinding, ...]
    _closed: bool = False

    def close(self) -> BaseException | None:
        if self._closed:
            return None
        self._closed = True
        first_error: BaseException | None = None
        for descriptor in (self.parent_fd, self.workspace_fd):
            try:
                os.close(descriptor)
            except BaseException as exc:
                first_error = first_error or exc
        return first_error


@dataclass(frozen=True, slots=True)
class UX1BExportOutcome:
    """Descriptor-bound publication result before the terminal pass write."""

    published: bool
    durability_confirmed: bool


@dataclass(slots=True)
class UX1BFormalRuntime:
    namespace: UX1BOutputNamespace
    runtime: Any
    final_root: Path
    app_root: Path
    browser_root: Path
    final_root_fd: int
    browser_root_fd: int
    lease: Any
    lifecycle: Any


@dataclass(slots=True)
class UX1BNonterminalRuntime:
    runtime: Any
    app_root: Path
    browser_root: Path
    final_root: Path
    browser_root_fd: int


UX1B_PAGE_PROJECTION = (
    PageProjection("today-decision", "/", "今日決策", "today_decision.render"),
    PageProjection("trade-state", "/trade-state", "交易狀態", "trade_state.render"),
    PageProjection("us-screener", "/us-screener", "暴漲股篩選器", "us_screener.render"),
    PageProjection("options-flow", "/options-flow", "選擇權異常流", "options_flow.render"),
    PageProjection("stock-checkup", "/stock-checkup", "個股總覽", "stock_checkup.render"),
    PageProjection("options-cockpit", "/options-cockpit", "期權作戰台", "options_cockpit.render"),
    PageProjection("radar", "/radar", "雷達 (風險＋反轉)", "radar.render"),
    PageProjection("ibkr-reconcile", "/ibkr-reconcile", "IBKR 對帳", "ibkr_reconcile.render"),
    PageProjection("sector-rotation", "/sector-rotation", "熱錢板塊輪動", "sector_rotation.render"),
    PageProjection("theme-flow", "/theme-flow", "主題資金流", "theme_flow.render"),
    PageProjection("us-cot", "/us-cot", "COT / ES 週報", "us_cot.render"),
    PageProjection("market-thesis", "/market-thesis", "大盤行情研判", "market_thesis.render"),
    PageProjection("us-x", "/us-x", "X 社群情緒", "us_x"),
    PageProjection("retro-analysis", "/retro-analysis", "復盤分析", "retro_analysis.render"),
    PageProjection("analytics-db", "/analytics-db", "資料健康 / Analytics DB", "analytics_db.render"),
    PageProjection("knowledge-graph", "/knowledge-graph", "知識網路", "knowledge_graph.render"),
    PageProjection("us-options", "/us-options", "期權分析", "us_options.render"),
    PageProjection("analyst-views", "/analyst-views", "分析師評級", "analyst_views.render"),
    PageProjection("institutions", "/institutions", "機構面板", "institutions.render"),
    PageProjection("industry-roles", "/industry-roles", "產業鏈分類", "industry_roles.render"),
    PageProjection("watchlist-categorize", "/watchlist-categorize", "自選股分類", "watchlist_categorize.render"),
    PageProjection("influencers", "/influencers", "關注博主", "influencers.render"),
    PageProjection("schedules", "/schedules", "排程與結果", "sys_schedules.render"),
    PageProjection("ai-updates", "/ai-updates", "AI 重點更新", "sys_ai_updates.render"),
    PageProjection("crypto-universe", "/crypto-universe", "幣種清單", "crypto_universe.render"),
    PageProjection("crypto-screener", "/crypto-screener", "幣圈篩選", "crypto_screener.render"),
    PageProjection("crypto-x", "/crypto-x", "X 社群情緒", "crypto_x"),
)

UX1B_READY_MARKERS: Mapping[str, ReadyMarker] = MappingProxyType({
    "today-decision": ReadyMarker(2, "今日決策", "exact"),
    "trade-state": ReadyMarker(2, "交易狀態", "exact"),
    "us-screener": ReadyMarker(2, "Layer 0 — 大盤環境", "exact"),
    "options-flow": ReadyMarker(1, "選擇權異常流", "contains"),
    "stock-checkup": ReadyMarker(2, "個股總覽", "contains"),
    "options-cockpit": ReadyMarker(2, "期權作戰台", "contains"),
    "radar": ReadyMarker(2, "雷達 / Radar", "contains"),
    "ibkr-reconcile": ReadyMarker(2, "IBKR 對帳", "contains"),
    "sector-rotation": ReadyMarker(2, "熱錢板塊輪動", "contains"),
    "theme-flow": ReadyMarker(2, "主題資金流", "contains"),
    "us-cot": ReadyMarker(2, "COT / ES 週報", "contains"),
    "market-thesis": ReadyMarker(2, "大盤行情研判", "contains"),
    "us-x": ReadyMarker(2, "X 社群情緒 — 美股", "contains"),
    "retro-analysis": ReadyMarker(1, "復盤分析", "contains"),
    "analytics-db": ReadyMarker(2, "資料健康 / Analytics DB", "exact"),
    "knowledge-graph": ReadyMarker(1, "知識網路", "exact"),
    "us-options": ReadyMarker(2, "完整期權鏈明細", "exact"),
    "analyst-views": ReadyMarker(2, "分析師評級", "contains"),
    "institutions": ReadyMarker(2, "機構面板", "contains"),
    "industry-roles": ReadyMarker(2, "產業鏈分類", "exact"),
    "watchlist-categorize": ReadyMarker(2, "自選股分類", "contains"),
    "influencers": ReadyMarker(2, "關注博主", "exact"),
    "schedules": ReadyMarker(2, "排程與執行結果", "contains"),
    "ai-updates": ReadyMarker(2, "AI Agent 重點更新", "contains"),
    "crypto-universe": ReadyMarker(2, "幣種清單 — 幣安 USDT 永續 (USDT.P)", "contains"),
    "crypto-screener": ReadyMarker(2, "幣圈篩選", "contains"),
    "crypto-x": ReadyMarker(2, "X 社群情緒 — 幣圈", "contains"),
})


@dataclass(frozen=True, slots=True)
class OwnedRun:
    run_dir: Path
    fixture_root: Path
    calls_path: Path
    marker_path: Path
    log_path: Path
    manifest_path: Path
    run_token: str
    run_id: str


@dataclass(frozen=True, slots=True)
class CaptureCase:
    """One browser-visible state, kept separate from its underlying route."""

    name: str
    page: str
    component_name: str
    component_selector: str
    interaction: str | None = None
    focused: bool = False


_FOCUSED_CASE_DEFINITIONS: Mapping[str, CaptureCase] = {
    "today-decision": CaptureCase(
        name="today-decision",
        page="today-decision",
        component_name="today-decision-main",
        component_selector='[data-testid="stMainBlockContainer"]',
        focused=True,
    ),
    "ai-chat-open": CaptureCase(
        name="ai-chat-open",
        page="today-decision",
        component_name="ai-chat-panel",
        component_selector=".st-key-ai_chat_panel",
        interaction="open-ai-chat",
        focused=True,
    ),
    "ai-updates": CaptureCase(
        name="ai-updates",
        page="ai-updates",
        component_name="ai-updates-main",
        component_selector='[data-testid="stMainBlockContainer"]',
        focused=True,
    ),
    "schedules": CaptureCase(
        name="schedules",
        page="schedules",
        component_name="schedules-main",
        component_selector='[data-testid="stMainBlockContainer"]',
        focused=True,
    ),
    "institution-portfolio": CaptureCase(
        name="institution-portfolio",
        page="institutions",
        component_name="institution-portfolio-main",
        component_selector='[data-testid="stMainBlockContainer"]',
        interaction="select-institution-portfolio",
        focused=True,
    ),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture the deterministic Quant Radar UX-0 browser matrix."
    )
    parser.add_argument("--out-dir", type=Path, help="new/empty run output directory")
    parser.add_argument(
        "--profile",
        choices=UX1B_PROFILES,
        help="isolated evidence profile; omitted preserves UX-0/UX-1A behavior",
    )
    parser.add_argument(
        "--phase",
        choices=UX1B_PHASES,
        help="UX-1B evidence phase (validated against the selected profile)",
    )
    parser.add_argument(
        "--theme-contract",
        type=Path,
        help=(
            "post-theme pretheme-authentication contract override; "
            "default=docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json"
        ),
    )
    parser.add_argument(
        "--capture-stack",
        choices=UX1B_CAPTURE_STACK_CHOICES,
        default="legacy",
        help="fixed formal capture-stack authority (default=legacy)",
    )
    parser.add_argument(
        "--browser",
        action="append",
        choices=("chromium", "webkit"),
        help="browser to require (repeatable; default=Chromium + supported WebKit)",
    )
    parser.add_argument(
        "--page",
        action="append",
        help="critical url_path to capture (repeatable; today-decision maps to /)",
    )
    parser.add_argument(
        "--case",
        action="append",
        choices=FOCUSED_CASES,
        help="UX-1A browser case to capture (repeatable; cannot be combined with --page)",
    )
    parser.add_argument(
        "--viewport",
        action="append",
        help="desktop, tablet, mobile, or WIDTHxHEIGHT (repeatable)",
    )
    parser.add_argument(
        "--ux1b-real-smoke",
        action="store_true",
        help="run the contract-free exact-ten UX-1B mobile smoke gate",
    )
    parser.add_argument(
        "--freeze-capture-stack",
        action="store_true",
        help="discover, smoke, and atomically freeze the UX-1B capture stack",
    )
    parser.add_argument(
        "--expected-capture-stack-sha256",
        help="required old canonical SHA-256 when freeze rotates an existing stack",
    )
    parser.add_argument("--json", action="store_true", help="write final summary JSON to stdout")
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="accepted for automation; the command never prompts",
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument("--verbose", action="store_true")
    verbosity.add_argument("--quiet", action="store_true")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def parse_viewport(value: str) -> tuple[str, int, int]:
    name = value.strip().lower()
    if name in DEFAULT_VIEWPORTS:
        width, height = DEFAULT_VIEWPORTS[name]
        return name, width, height
    match = _CUSTOM_VIEWPORT_RE.fullmatch(name)
    if not match:
        raise ValueError(f"invalid viewport {value!r}; use a named viewport or WIDTHxHEIGHT")
    width, height = (int(match.group(1)), int(match.group(2)))
    if not 200 <= width <= 4096 or not 200 <= height <= 4096:
        raise ValueError("viewport dimensions must each be between 200 and 4096")
    return name, width, height


def route_for_page(page: str) -> str:
    normalized = page.strip().strip("/").lower()
    if normalized in ("", "today-decision"):
        return "/"
    return "/" + normalized


def normalize_page(value: str) -> str:
    normalized = value.strip().strip("/").lower()
    if normalized == "":
        normalized = "today-decision"
    if normalized not in PAGE_HEADINGS:
        raise ValueError(
            f"unsupported UX-0 page {value!r}; choose one of {', '.join(DEFAULT_PAGES)}"
        )
    return normalized


def page_capture_case(page: str) -> CaptureCase:
    """Build the historical non-interactive case for one UX-0 page."""

    normalized = normalize_page(page)
    return CaptureCase(
        name=normalized,
        page=normalized,
        component_name=f"{normalized}-main",
        component_selector='[data-testid="stMainBlockContainer"]',
    )


def ux1b_page_capture_case(page: PageProjection) -> CaptureCase:
    """Build one non-interactive full-page case from the frozen UX-1B record."""

    return CaptureCase(
        name=page.registry_key,
        page=page.registry_key,
        component_name=f"{page.registry_key}-main",
        component_selector='[data-testid="stMainBlockContainer"]',
    )


def ux1b_profile_rows(profile: str) -> tuple[dict[str, Any], ...]:
    """Return the descriptor-frozen worker identities for one formal profile."""

    try:
        entrypoint = UX1B_FIXTURE_ENTRYPOINTS[profile]
    except KeyError as exc:
        raise RunnerDataError("UX1B capture profile is not frozen") from exc
    try:
        rows = _evidence_api().worker_capture_profile_rows(entrypoint)
    except Exception as exc:
        raise RunnerDataError("UX1B worker capture catalog is unavailable") from exc
    return tuple(dict(row) for row in rows)


def ux1b_selection_capture_cases() -> tuple[CaptureCase, ...]:
    rows = ux1b_profile_rows(UX1B_SELECTION_PROFILE)
    cases: dict[str, CaptureCase] = {}
    for row in rows:
        case_name = str(row["case"])
        cases.setdefault(
            case_name,
            CaptureCase(
                name=case_name,
                page=str(row["registryKey"]),
                component_name=f"{case_name}-main",
                component_selector='[data-testid="stMainBlockContainer"]',
                focused=True,
            ),
        )
    if len(cases) != 9:
        raise RunnerDataError("UX1B focused worker catalog must contain nine cases")
    return tuple(cases.values())


def ux1b_control_discovery_rows() -> tuple[dict[str, Any], ...]:
    """Return the exact 7x3 + 9x4 raw-sidecar discovery projection."""

    full = tuple(
        row
        for row in ux1b_profile_rows(UX1B_PROFILE)
        if tuple(row.get("rootSelectors") or ())
    )
    focused = ux1b_profile_rows(UX1B_SELECTION_PROFILE)
    rows = (*full, *focused)
    if len(full) != 21 or len(focused) != 36 or len(rows) != 57:
        raise RunnerDataError("UX1B control discovery projection is not exact 7x3 + 9x4")
    return tuple(dict(row) for row in rows)


def ux1b_real_smoke_rows() -> tuple[dict[str, Any], ...]:
    """Freeze stock-checkup/mobile plus all nine focused mobile identities."""

    full = tuple(
        row
        for row in ux1b_profile_rows(UX1B_PROFILE)
        if row.get("case") == "stock-checkup"
        and row.get("viewport")
        == {"name": "mobile", "width": 390, "height": 844}
    )
    focused = tuple(
        row
        for row in ux1b_profile_rows(UX1B_SELECTION_PROFILE)
        if row.get("viewport")
        == {"name": "mobile", "width": 390, "height": 844}
    )
    rows = (*full, *focused)
    if (
        len(full) != 1
        or len(focused) != 9
        or len({str(row["case"]) for row in focused}) != 9
        or len(rows) != 10
    ):
        raise RunnerDataError("UX1B real smoke projection is not exact mobile 1 + 9")
    return tuple(dict(row) for row in rows)


def derive_ux1b_control_catalog(
    discovery_sidecars: Sequence[Any],
    *,
    base_capture_stack_digest: str,
) -> Any:
    """Derive, but deliberately never publish, the frozen control catalog."""

    return _evidence_api().derive_control_catalog(
        tuple(discovery_sidecars),
        base_capture_stack_digest=base_capture_stack_digest,
    )


def _projection_records(
    projection: Sequence[Mapping[str, Any] | PageProjection],
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for item in projection:
        if isinstance(item, PageProjection):
            record = {
                "registry_key": item.registry_key,
                "route": item.route,
                "nav_title": item.nav_title,
                "callable": item.callable_name,
            }
        elif isinstance(item, Mapping):
            try:
                record = {
                    "registry_key": str(item["registry_key"]),
                    "route": str(item["route"]),
                    "nav_title": str(item["nav_title"]),
                    "callable": str(item["callable"]),
                }
            except KeyError as exc:
                raise RunnerDataError(
                    f"UX1B page projection is missing {exc.args[0]!r}"
                ) from exc
        else:
            raise RunnerDataError("UX1B page projection records must be objects")
        records.append(record)
    return records


def _projection_digest(projection: Sequence[Mapping[str, Any] | PageProjection]) -> str:
    encoded = json.dumps(
        _projection_records(projection),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def live_ux1b_projection() -> list[dict[str, str]]:
    """Return the live inventory's location-free four-field page projection."""

    try:
        from ui_ux_inventory import build_inventory
    except ImportError as exc:  # pragma: no cover - script directory is normally importable.
        raise RunnerDataError("cannot import the UI inventory for UX1B") from exc
    inventory = build_inventory(ROOT)
    pages = inventory.get("pages")
    if not isinstance(pages, list):
        raise RunnerDataError("live UX1B inventory has no page projection")
    return [
        {
            "registry_key": str(item.get("registry_key")),
            "route": str(item.get("route")),
            "nav_title": str(item.get("title")),
            "callable": str(item.get("callable")),
        }
        for item in pages
        if isinstance(item, Mapping)
    ]


def _ready_marker_records(
    markers: Mapping[str, ReadyMarker | Mapping[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for registry_key, marker in markers.items():
        if isinstance(marker, ReadyMarker):
            level, text, match = marker.level, marker.text, marker.match
        elif isinstance(marker, Mapping):
            try:
                level = marker["level"]
                text = marker["text"]
                match = marker["match"]
            except KeyError as exc:
                raise RunnerDataError(
                    f"UX1B ready marker is missing {exc.args[0]!r}"
                ) from exc
        else:
            raise RunnerDataError("UX1B ready markers must be objects")
        if (
            not isinstance(level, int)
            or isinstance(level, bool)
            or level not in (1, 2)
            or not isinstance(text, str)
            or not text
            or match not in {"exact", "contains"}
        ):
            raise RunnerDataError(f"UX1B ready marker is invalid for {registry_key}")
        records.append(
            {
                "registry_key": str(registry_key),
                "level": level,
                "text": text,
                "match": str(match),
            }
        )
    return records


def validate_ux1b_ready_markers(
    markers: Mapping[str, ReadyMarker | Mapping[str, Any]],
) -> None:
    records = _ready_marker_records(markers)
    digest = hashlib.sha256(
        json.dumps(
            records,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    expected_keys = tuple(item.registry_key for item in UX1B_PAGE_PROJECTION)
    if (
        tuple(item["registry_key"] for item in records) != expected_keys
        or digest != UX1B_READY_MARKERS_SHA256
    ):
        raise RunnerDataError(
            "UX1B ready-marker catalog differs from the frozen ordered 27-page contract"
        )


def validate_ux1b_projection(
    projection: Sequence[Mapping[str, Any] | PageProjection],
) -> None:
    """Reject any drift from the accepted ordered 27-page identity oracle."""

    actual = _projection_records(projection)
    expected = _projection_records(UX1B_PAGE_PROJECTION)
    if actual != expected or _projection_digest(actual) != UX1B_PROJECTION_SHA256:
        raise RunnerDataError(
            "live UX1B page projection differs from the frozen ordered 27-page contract"
        )
    validate_ux1b_ready_markers(UX1B_READY_MARKERS)


def normalize_case(value: str) -> CaptureCase:
    normalized = str(value or "").strip().lower()
    try:
        return _FOCUSED_CASE_DEFINITIONS[normalized]
    except KeyError as exc:
        raise ValueError(
            f"unsupported UX-1A case {value!r}; choose one of {', '.join(FOCUSED_CASES)}"
        ) from exc


def ux1b_allowed_ports(contract: UX1BNetworkContract) -> frozenset[int]:
    return frozenset((contract.streamlit_port, contract.deny_proxy_port))


def is_allowed_browser_url(
    url: str,
    *,
    allowed_ports: frozenset[int] | None = None,
) -> bool:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme in ("data", "blob", "about"):
        if parsed.scheme == "blob" and parsed.path.startswith(("http://", "https://")):
            return is_allowed_browser_url(parsed.path, allowed_ports=allowed_ports)
        return True
    if parsed.scheme not in ("http", "https", "ws", "wss"):
        return False
    try:
        port = parsed.port
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if allowed_ports is not None:
        # UX-1B is an exact-origin contract, not a generic loopback policy.
        # Host aliases, IPv6 loopback, and the rest of 127/8 can resolve to a
        # different listener and therefore must not inherit either owned port.
        return host == "127.0.0.1" and port in allowed_ports
    if host == "localhost":
        return True
    try:
        return socket.inet_pton(socket.AF_INET, host) == socket.inet_pton(
            socket.AF_INET, "127.0.0.1"
        )
    except OSError:
        pass
    try:
        packed = socket.inet_pton(socket.AF_INET6, host)
        return packed == socket.inet_pton(socket.AF_INET6, "::1")
    except OSError:
        return False


def safe_url_label(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https", "ws", "wss"):
        return parsed.scheme + ":" if parsed.scheme else "unknown"
    netloc = parsed.hostname or "unknown"
    if parsed.port is not None:
        netloc += f":{parsed.port}"
    return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path or "/", "", ""))


def handle_browser_web_socket(
    web_socket: Any,
    blocked: list[dict[str, str]],
    *,
    allowed_ports: frozenset[int] | None = None,
) -> None:
    """Allow loopback WebSockets and block every other routed connection."""

    url = web_socket.url
    if is_allowed_browser_url(url, allowed_ports=allowed_ports):
        web_socket.connect_to_server()
        return
    block_browser_web_socket(web_socket, blocked)


def block_browser_web_socket(
    web_socket: Any, blocked: list[dict[str, str]]
) -> None:
    """Record a routed WebSocket and deliberately leave it disconnected.

    Playwright WebSocket routes do not contact the server unless
    ``connect_to_server()`` is called.  Calling the sync ``close()`` method from
    inside its own route callback can re-enter the dispatcher and deadlock, so
    returning without connecting is the bounded fail-closed operation.
    """

    url = web_socket.url
    blocked.append({"method": "WEBSOCKET", "url": safe_url_label(url)})


def select_browsers(
    requested: Sequence[str] | None,
    availability: Mapping[str, bool],
) -> tuple[tuple[str, ...], dict[str, str]]:
    capabilities = {
        name: "supported" if bool(availability.get(name)) else "unsupported"
        for name in ("chromium", "webkit")
    }
    if requested:
        selected = tuple(dict.fromkeys(requested))
        missing = [name for name in selected if not availability.get(name)]
        if missing:
            raise DependencyUnavailable(
                "requested Playwright browser unavailable: " + ", ".join(missing)
            )
        return selected, capabilities
    if not availability.get("chromium"):
        raise DependencyUnavailable("mandatory Playwright Chromium browser unavailable")
    selected = ["chromium"]
    if availability.get("webkit"):
        selected.append("webkit")
    return tuple(selected), capabilities


def _json_document(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(raw_tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(_json_document(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
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


def atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(raw_tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def _default_run_dir(
    *, profile: str | None = None, phase: str | None = None
) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if profile in UX1B_PROFILES:
        label = phase or "unphased"
        return (
            ROOT
            / ".claude"
            / "ui_snapshots"
            / "ux1b"
            / f"{label}-{stamp}-{secrets.token_hex(3)}"
        )
    return ROOT / ".claude" / "ui_snapshots" / "ux0" / f"{stamp}-{secrets.token_hex(3)}"


def _open_directory_component(
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
        raise RunnerDataError("UX1B output path contains an unsafe component")
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
        raise RunnerDataError("UX1B output directory component is unavailable") from exc
    opened = os.fstat(descriptor)
    if (
        not stat.S_ISDIR(named.st_mode)
        or not stat.S_ISDIR(opened.st_mode)
        or (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
        or opened.st_uid != os.getuid()
        or stat.S_IMODE(opened.st_mode) & 0o022
    ):
        os.close(descriptor)
        raise RunnerDataError("UX1B output directory component is unsafe")
    return descriptor


def _freeze_ux1b_directory_binding(
    name: str,
    descriptor: int,
) -> UX1BDirectoryBinding:
    observed = os.fstat(descriptor)
    if (
        not stat.S_ISDIR(observed.st_mode)
        or observed.st_uid != os.getuid()
        or stat.S_IMODE(observed.st_mode) & 0o022
    ):
        raise RunnerDataError("UX1B directory binding is unsafe")
    return UX1BDirectoryBinding(
        name=name,
        device=observed.st_dev,
        inode=observed.st_ino,
        owner_uid=observed.st_uid,
        mode=stat.S_IMODE(observed.st_mode),
    )


def _require_ux1b_directory_binding(
    descriptor: int,
    binding: UX1BDirectoryBinding,
) -> None:
    observed = os.fstat(descriptor)
    if (
        not stat.S_ISDIR(observed.st_mode)
        or (
            observed.st_dev,
            observed.st_ino,
            observed.st_uid,
            stat.S_IMODE(observed.st_mode),
        )
        != (
            binding.device,
            binding.inode,
            binding.owner_uid,
            binding.mode,
        )
    ):
        raise RunnerDataError(
            f"retained UX1B directory binding changed: {binding.name}"
        )


def _open_bound_ux1b_directory_component(
    parent_fd: int,
    binding: UX1BDirectoryBinding,
) -> int:
    descriptor = _open_directory_component(
        parent_fd,
        binding.name,
        create=False,
    )
    try:
        _require_ux1b_directory_binding(descriptor, binding)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _open_ux1b_output_namespace(path: Path) -> UX1BOutputNamespace:
    """Open the output namespace from retained workspace and UX1B dirfds."""

    ux1b_root = ROOT / ".claude" / "ui_snapshots" / "ux1b"
    run_dir = Path(os.path.abspath(os.path.expanduser(os.fspath(path))))
    try:
        relative = run_dir.relative_to(ux1b_root)
    except ValueError as exc:
        raise RunnerDataError(
            "UX1B output directory must be beneath .claude/ui_snapshots/ux1b"
        ) from exc
    if (
        not relative.parts
        or any(part in {"", ".", "..", "ux0", "ux1a"} for part in relative.parts)
    ):
        raise RunnerDataError(
            "UX1B output directory must use a new child in the ux1b namespace"
        )

    workspace_fd = -1
    ux1b_fd = -1
    parent_fd = -1
    intermediate: list[int] = []
    namespace_bindings: list[UX1BDirectoryBinding] = []
    parent_bindings: list[UX1BDirectoryBinding] = []
    try:
        workspace_fd = _directory_fd(WORKSPACE_ROOT)
        workspace_binding = _freeze_ux1b_directory_binding(
            ".",
            workspace_fd,
        )
        current_fd = workspace_fd
        for component in (".claude", "ui_snapshots", "ux1b"):
            child_fd = _open_directory_component(
                current_fd,
                component,
                create=True,
            )
            intermediate.append(child_fd)
            namespace_bindings.append(
                _freeze_ux1b_directory_binding(component, child_fd)
            )
            current_fd = child_fd
        ux1b_fd = intermediate.pop()
        for descriptor in reversed(intermediate):
            os.close(descriptor)
        intermediate.clear()

        parent_fd = os.dup(ux1b_fd)
        os.set_inheritable(parent_fd, False)
        for component in relative.parts[:-1]:
            child_fd = _open_directory_component(
                parent_fd,
                component,
                create=True,
            )
            os.close(parent_fd)
            parent_fd = child_fd
            parent_bindings.append(
                _freeze_ux1b_directory_binding(component, child_fd)
            )
        return UX1BOutputNamespace(
            path=ux1b_root.joinpath(*relative.parts),
            leaf_name=relative.parts[-1],
            workspace_fd=workspace_fd,
            ux1b_fd=ux1b_fd,
            parent_fd=parent_fd,
            workspace_binding=workspace_binding,
            namespace_bindings=tuple(namespace_bindings),
            parent_bindings=tuple(parent_bindings),
        )
    except BaseException:
        for descriptor in reversed(intermediate):
            try:
                os.close(descriptor)
            except OSError:
                pass
        for descriptor in (parent_fd, ux1b_fd, workspace_fd):
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        raise


def _reauthenticate_ux1b_output_namespace(
    namespace: UX1BOutputNamespace,
) -> None:
    opened_fds: list[int] = []
    try:
        _require_ux1b_directory_binding(
            namespace.workspace_fd,
            namespace.workspace_binding,
        )
        current_fd = namespace.workspace_fd
        for binding in namespace.namespace_bindings:
            current_fd = _open_bound_ux1b_directory_component(
                current_fd,
                binding,
            )
            opened_fds.append(current_fd)
        _require_ux1b_directory_binding(
            namespace.ux1b_fd,
            namespace.namespace_bindings[-1],
        )
        observed_ux1b = os.fstat(current_fd)
        retained_ux1b = os.fstat(namespace.ux1b_fd)
        if (
            observed_ux1b.st_dev,
            observed_ux1b.st_ino,
            observed_ux1b.st_uid,
            stat.S_IMODE(observed_ux1b.st_mode),
        ) != (
            retained_ux1b.st_dev,
            retained_ux1b.st_ino,
            retained_ux1b.st_uid,
            stat.S_IMODE(retained_ux1b.st_mode),
        ):
            raise RunnerDataError("retained UX1B output namespace changed")
        for descriptor in reversed(opened_fds):
            os.close(descriptor)
        opened_fds.clear()

        current_fd = namespace.ux1b_fd
        for binding in namespace.parent_bindings:
            current_fd = _open_bound_ux1b_directory_component(
                current_fd,
                binding,
            )
            opened_fds.append(current_fd)
        observed_parent = os.fstat(current_fd)
        retained_parent = os.fstat(namespace.parent_fd)
        if (
            observed_parent.st_dev,
            observed_parent.st_ino,
            observed_parent.st_uid,
            stat.S_IMODE(observed_parent.st_mode),
        ) != (
            retained_parent.st_dev,
            retained_parent.st_ino,
            retained_parent.st_uid,
            stat.S_IMODE(retained_parent.st_mode),
        ):
            raise RunnerDataError("retained UX1B output parent changed")
    finally:
        for descriptor in reversed(opened_fds):
            try:
                os.close(descriptor)
            except OSError:
                pass


def _validate_ux1b_output_leaf(namespace: UX1BOutputNamespace) -> None:
    _reauthenticate_ux1b_output_namespace(namespace)
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
            not stat.S_ISDIR(named.st_mode)
            or not stat.S_ISDIR(opened.st_mode)
            or named.st_uid != os.getuid()
            or stat.S_IMODE(opened.st_mode) & 0o022
            or (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
            or bool(os.listdir(descriptor))
        ):
            raise RunnerDataError(
                f"output directory is not empty: {namespace.path}"
            )
    except OSError as exc:
        raise RunnerDataError(
            f"output directory is not empty: {namespace.path}"
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def validate_output_namespace(path: Path, *, profile: str | None = None) -> Path:
    if profile in UX1B_PROFILES:
        namespace = _open_ux1b_output_namespace(path)
        try:
            _validate_ux1b_output_leaf(namespace)
            return namespace.path
        finally:
            namespace.close()
    return path.expanduser().resolve()


def create_owned_run(
    path: Path | None = None,
    *,
    profile: str | None = None,
    phase: str | None = None,
) -> OwnedRun:
    selected_path = path or _default_run_dir(profile=profile, phase=phase)
    run_dir = validate_output_namespace(selected_path, profile=profile)
    workspace = ROOT.resolve()
    allowed = workspace / ".claude" / "ui_snapshots"
    if run_dir == workspace or (
        workspace in run_dir.parents and run_dir != allowed and allowed not in run_dir.parents
    ):
        # A dedicated ignored subtree is expected; never make any production
        # source directory an owned fixture/output root.
        raise RunnerDataError("output directory must not be a repository source directory")
    if run_dir.exists() and any(run_dir.iterdir()):
        raise RunnerDataError(f"output directory is not empty: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    fixture_root = run_dir / "fixture-root"
    fixture_root.mkdir()
    (fixture_root / "candidates").mkdir()
    (fixture_root / "ai-chat").mkdir()
    (fixture_root / "tmp").mkdir()
    token = secrets.token_urlsafe(32)
    marker_path = run_dir / _OWNER_FILE
    run_id = run_dir.name
    atomic_write_text(marker_path, token)
    return OwnedRun(
        run_dir=run_dir,
        fixture_root=fixture_root,
        calls_path=run_dir / "fixture-calls.json",
        marker_path=marker_path,
        log_path=run_dir / "streamlit.log",
        manifest_path=run_dir / "manifest.json",
        run_token=token,
        run_id=run_id,
    )


def fixture_environment(
    owned: OwnedRun,
    *,
    profile: str | None = None,
    phase: str | None = None,
    network_contract: UX1BNetworkContract | None = None,
) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key in _CHILD_ENV_KEYS or key.startswith("LC_")
    }
    private_home = str(owned.fixture_root)
    private_tmp = str(owned.fixture_root / "tmp")
    env.update(
        {
            "HOME": private_home,
            "XDG_CACHE_HOME": str(owned.fixture_root / ".cache"),
            "XDG_CONFIG_HOME": str(owned.fixture_root / ".config"),
            "XDG_DATA_HOME": str(owned.fixture_root / ".local" / "share"),
            "TMPDIR": private_tmp,
            "TMP": private_tmp,
            "TEMP": private_tmp,
            "NO_PROXY": "127.0.0.1,localhost,::1",
            "QUANT_RADAR_UX0_FIXTURES": "1",
            "QUANT_RADAR_UX0_FIXTURE_ROOT": str(owned.fixture_root),
            "QUANT_RADAR_UX0_CALLS_PATH": str(owned.calls_path),
            "QUANT_RADAR_UX0_RUN_TOKEN": owned.run_token,
            "QUANT_RADAR_UX0_FIXED_NOW": "2026-07-15T06:30:00Z",
            "SURGE_RUNTIME_DIR": str(owned.fixture_root),
            "SURGE_CANDIDATE_OUTPUT_DIR": str(owned.fixture_root / "candidates"),
            "SURGE_AI_CHAT_DIR": str(owned.fixture_root / "ai-chat"),
            "TZ": "UTC",
            "PYTHONUNBUFFERED": "1",
        }
    )
    if profile == UX1B_PROFILE:
        if phase not in UX1B_PHASES or network_contract is None:
            raise RunnerDataError("UX1B fixture environment requires phase and network ports")
        proxy = f"http://127.0.0.1:{network_contract.deny_proxy_port}"
        env.update(
            {
                "QUANT_RADAR_UX1B_PROFILE": profile,
                "QUANT_RADAR_UX1B_PHASE": phase,
                "QUANT_RADAR_UX1B_STREAMLIT_PORT": str(
                    network_contract.streamlit_port
                ),
                "QUANT_RADAR_UX1B_DENY_PROXY_PORT": str(
                    network_contract.deny_proxy_port
                ),
                "SURGE_ANALYTICS_DIR": str(owned.fixture_root / "analytics"),
                "HTTP_PROXY": proxy,
                "HTTPS_PROXY": proxy,
                "ALL_PROXY": proxy,
            }
        )
    return env


def public_run_metadata(owned: OwnedRun) -> dict[str, str]:
    try:
        output_dir = owned.run_dir.relative_to(ROOT).as_posix()
    except ValueError:
        output_dir = owned.run_dir.name
    return {
        "runId": owned.run_id,
        "outputDir": output_dir,
        "manifest": "manifest.json",
        "streamlitLog": "streamlit.log",
        "fixtureCalls": "fixture-calls.json",
    }


def compute_source_digest(
    paths: Sequence[Path],
    *,
    root: Path,
    projection_sha256: str | None = None,
) -> str:
    """Hash an ordered repository-relative file projection and optional oracle."""

    base = root.resolve()
    projected: list[tuple[str, Path]] = []
    for item in paths:
        raw_path = Path(item).resolve()
        try:
            relative = raw_path.relative_to(base).as_posix()
        except ValueError as exc:
            raise RunnerDataError("source digest path is outside its declared root") from exc
        projected.append((relative, raw_path))
    projected.sort(key=lambda item: item[0])
    if len({relative for relative, _path in projected}) != len(projected):
        raise RunnerDataError("source digest projection contains duplicate paths")
    records: list[dict[str, str]] = []
    for relative, raw_path in projected:
        try:
            payload = raw_path.read_bytes()
        except OSError as exc:
            raise RunnerDataError(f"source digest cannot read {relative}") from exc
        records.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    aggregate = {
        "files": records,
        "projectionSha256": projection_sha256,
    }
    return hashlib.sha256(
        json.dumps(
            aggregate,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def ux1b_source_paths(*, root: Path = ROOT) -> tuple[Path, ...]:
    """Return the complete stable UX-1B render/tool source projection."""

    base = root.resolve()
    projected = {
        (base / ".streamlit" / "config.toml").resolve(),
        (base / "Makefile").resolve(),
        (base / "requirements.txt").resolve(),
    }
    projected.update(path.resolve() for path in base.glob("*.py") if path.is_file())
    for directory in ("ui", "scripts", "api"):
        source_root = base / directory
        if source_root.is_dir():
            projected.update(
                path.resolve() for path in source_root.rglob("*.py") if path.is_file()
            )
    return tuple(
        sorted(projected, key=lambda path: path.relative_to(base).as_posix())
    )


def ux1b_source_digest(*, root: Path = ROOT) -> str:
    base = root.resolve()
    return compute_source_digest(
        ux1b_source_paths(root=base),
        root=base,
        projection_sha256=UX1B_PROJECTION_SHA256,
    )


def _ux1b_ready_marker_catalog() -> list[dict[str, Any]]:
    return [
        {
            "registryKey": key,
            "role": "heading",
            "level": marker.level,
            "text": marker.text,
            "match": marker.match,
            "scope": "stMainBlockContainer",
        }
        for key, marker in UX1B_READY_MARKERS.items()
    ]


def _ux1b_manifest_error(message: str) -> RunnerDataError:
    return RunnerDataError(f"UX1B pre/post manifest contract: {message}")


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _ux1b_manifest_error(f"{label} must be an object")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise _ux1b_manifest_error(f"{label} must be an array")
    return value


def _first_contract_difference(left: Any, right: Any, path: str = "$.") -> str | None:
    if type(left) is not type(right):
        return path.rstrip(".")
    if isinstance(left, Mapping):
        if set(left) != set(right):
            return path.rstrip(".") + ".keys"
        for key in sorted(left):
            difference = _first_contract_difference(
                left[key], right[key], f"{path}{key}."
            )
            if difference is not None:
                return difference
        return None
    if isinstance(left, list):
        if len(left) != len(right):
            return path.rstrip(".") + ".length"
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            difference = _first_contract_difference(
                left_item, right_item, f"{path}[{index}]."
            )
            if difference is not None:
                return difference
        return None
    return None if left == right else path.rstrip(".")


def normalize_ux1b_manifest_contract(
    manifest: Mapping[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    """Validate and normalize the non-theme UX-1B 81-capture contract."""

    value = _require_mapping(manifest, phase)
    expected_pages = [item.registry_key for item in UX1B_PAGE_PROJECTION]
    expected_catalog = _projection_records(UX1B_PAGE_PROJECTION)
    expected_cases = [
        {
            "name": page.registry_key,
            "page": page.registry_key,
            "route": page.route,
            "component": f"{page.registry_key}-main",
            "interaction": "none",
        }
        for page in UX1B_PAGE_PROJECTION
    ]
    expected_viewports = [
        {"name": name, "width": width, "height": height}
        for name, width, height in UX1B_VIEWPORTS
    ]
    exact_top_level = {
        "schemaVersion": 1,
        "status": "passed",
        "mode": UX1B_PROFILE,
        "phase": phase,
        "projectionSha256": UX1B_PROJECTION_SHA256,
        "fixtureRevision": UX1B_EXPECTED_FIXTURE_REVISION,
        "fixtureContractSchema": UX1B_EXPECTED_CONTRACT_SCHEMA_VERSION,
        "selectedBrowsers": ["chromium"],
        "pages": expected_pages,
        "cases": expected_cases,
        "viewports": expected_viewports,
        "expectedCapturesPerBrowser": 81,
        "expectedCaptureCount": 81,
        "pageIdentityCatalog": expected_catalog,
        "readyMarkers": _ux1b_ready_marker_catalog(),
    }
    for key, expected in exact_top_level.items():
        if value.get(key) != expected:
            raise _ux1b_manifest_error(f"{phase}.{key} differs from the frozen contract")
    start = value.get("sourceDigestStart")
    end = value.get("sourceDigestEnd")
    if (
        not isinstance(start, str)
        or re.fullmatch(r"[0-9a-f]{64}", start) is None
        or end != start
        or value.get("sourceDigestEqual") is not True
    ):
        raise _ux1b_manifest_error(
            f"{phase} sourceDigestStart/sourceDigestEnd must be equal SHA-256 values"
        )
    if value.get("bootstrapBlockedNetwork", []) != []:
        raise _ux1b_manifest_error(f"{phase} bootstrap network evidence is not empty")

    server = _require_mapping(value.get("server"), f"{phase}.server")
    required_server = {
        "ownedProcess": True,
        "loopbackOnly": True,
        "exactPortContract": True,
        "allowedEndpointCount": 2,
        "denyProxyOwned": True,
        "denyProxyAttemptCount": 0,
    }
    for key, expected in required_server.items():
        if server.get(key) != expected:
            raise _ux1b_manifest_error(f"{phase}.server.{key} is invalid")
    calibration = _require_mapping(
        server.get("sandboxCalibration"), f"{phase}.server.sandboxCalibration"
    )
    capability = calibration.get("capability")
    if (
        capability not in {"supported", "not_applicable"}
        or server.get("kernelIsolation") != capability
        or calibration.get("passed") is not True
        or calibration.get("exactPortContract") is not True
        or calibration.get("dummyListenerBytes") != 0
    ):
        raise _ux1b_manifest_error(f"{phase} sandbox calibration did not pass")
    if capability == "supported" and any(
        calibration.get(key) != expected
        for key, expected in {
            "allowedEndpointCount": 2,
            "streamlitAllowed": True,
            "denyProxyAllowed": True,
            "dummyLoopbackDenied": True,
            "api8000Denied": True,
            "testNetDenied": True,
        }.items()
    ):
        raise _ux1b_manifest_error(f"{phase} exact-port sandbox evidence is incomplete")
    server_projection = {
        **required_server,
        "kernelIsolation": server.get("kernelIsolation"),
        "sandboxCalibration": {
            key: calibration.get(key)
            for key in (
                "capability",
                "passed",
                "exactPortContract",
                "allowedEndpointCount",
                "streamlitAllowed",
                "denyProxyAllowed",
                "dummyLoopbackDenied",
                "api8000Denied",
                "testNetDenied",
                "dummyListenerBytes",
            )
        },
    }

    fixture_contracts = load_ux1b_fixture_contracts()
    page_by_key = {item.registry_key: item for item in UX1B_PAGE_PROJECTION}
    marker_by_key = {
        item["registryKey"]: item for item in _ux1b_ready_marker_catalog()
    }
    expected_keys = {
        ("chromium", page.registry_key, viewport_name)
        for page in UX1B_PAGE_PROJECTION
        for viewport_name, _width, _height in UX1B_VIEWPORTS
    }
    captures = _require_list(value.get("captures"), f"{phase}.captures")
    if len(captures) != 81:
        raise _ux1b_manifest_error(f"{phase} must contain exactly 81 captures")
    normalized_captures: dict[tuple[str, str, str], dict[str, Any]] = {}
    viewport_by_name = {
        name: {"name": name, "width": width, "height": height}
        for name, width, height in UX1B_VIEWPORTS
    }
    for index, raw_capture in enumerate(captures):
        capture = _require_mapping(raw_capture, f"{phase}.captures[{index}]")
        viewport = _require_mapping(
            capture.get("viewport"), f"{phase}.captures[{index}].viewport"
        )
        identity_key = (
            capture.get("browser"),
            capture.get("page"),
            viewport.get("name"),
        )
        if identity_key not in expected_keys or identity_key in normalized_captures:
            raise _ux1b_manifest_error(
                f"{phase}.captures[{index}] has an unknown or duplicate identity"
            )
        _browser, page_key, viewport_name = identity_key
        page = page_by_key[page_key]
        expected_viewport = viewport_by_name[viewport_name]
        expected_marker = marker_by_key[page_key]
        if dict(viewport) != expected_viewport:
            raise _ux1b_manifest_error(
                f"{phase}.captures[{index}].viewport dimensions are invalid"
            )
        exact_capture = {
            "profile": UX1B_PROFILE,
            "status": "passed",
            "failureReasons": [],
            "browser": "chromium",
            "case": page_key,
            "focusedCase": False,
            "page": page_key,
            "route": page.route,
            "heading": expected_marker["text"],
            "headingReady": True,
            "streamlitException": False,
            "pageErrors": [],
            "blockedExternalRequests": [],
            "blockedServerNetwork": [],
            "fixtureQuiescent": True,
            "fixtureContractFailures": [],
            "readyMarker": {
                key: expected_marker[key]
                for key in ("role", "level", "text", "match", "scope")
            },
        }
        for key, expected in exact_capture.items():
            if capture.get(key) != expected:
                raise _ux1b_manifest_error(
                    f"{phase}.captures[{index}].{key} differs from the contract"
                )
        expected_identity = {
            "requestedRoute": page.route,
            "finalBrowserPath": page.route,
            "expectedRegistryKey": page_key,
            "selectedRegistryKey": page_key,
            "expectedCallable": page.callable_name,
            "realCallable": page.callable_name,
            "expectedNavTitle": page.nav_title,
        }
        identity = _require_mapping(
            capture.get("identity"), f"{phase}.captures[{index}].identity"
        )
        if dict(identity) != expected_identity:
            raise _ux1b_manifest_error(
                f"{phase}.captures[{index}].identity differs from the frozen route/title/callable contract"
            )

        counters = fixture_contracts["counters"][page_key]
        positive = dict(counters["positive"])
        zero = sorted(counters["zero"])
        owned_paths = dict(fixture_contracts["ownedPaths"][page_key])
        fixture = _require_mapping(
            capture.get("fixture"), f"{phase}.captures[{index}].fixture"
        )
        expected_fixture = {
            "counts": positive,
            "blockedNetwork": [],
            "identity": {
                "selectedRegistryKey": page_key,
                "realCallable": page.callable_name,
            },
        }
        if dict(fixture) != expected_fixture:
            raise _ux1b_manifest_error(
                f"{phase}.captures[{index}].fixture provider counters are invalid"
            )
        fixture_evidence = _require_mapping(
            capture.get("fixtureContract"),
            f"{phase}.captures[{index}].fixtureContract",
        )
        expected_fixture_evidence = {
            "positiveCounters": positive,
            "zeroCounters": zero,
            "ownedPaths": owned_paths,
            "resolvedOwnedPaths": owned_paths,
        }
        if dict(fixture_evidence) != expected_fixture_evidence:
            raise _ux1b_manifest_error(
                f"{phase}.captures[{index}].fixtureContract provider/root/read-write projection is invalid"
            )

        metrics = _require_mapping(
            capture.get("metrics"), f"{phase}.captures[{index}].metrics"
        )
        component = _require_mapping(
            capture.get("componentMetrics"),
            f"{phase}.captures[{index}].componentMetrics",
        )
        if (
            metrics.get("viewportWidth") != expected_viewport["width"]
            or metrics.get("viewportHeight") != expected_viewport["height"]
            or not isinstance(metrics.get("horizontalOverflow"), bool)
            or not isinstance(metrics.get("sidebarOverlapsMain"), bool)
            or not isinstance(component.get("horizontalOverflow"), bool)
        ):
            raise _ux1b_manifest_error(
                f"{phase}.captures[{index}] geometry/overflow evidence is invalid"
            )
        known_debt = _require_mapping(
            capture.get("knownDebt"), f"{phase}.captures[{index}].knownDebt"
        )
        expected_debt_projection = {
            "expandedSidebarOverlapsMain": metrics["sidebarOverlapsMain"],
            "pageHorizontalOverflow": metrics["horizontalOverflow"],
            "floatingAiPresent": known_debt.get("floatingAiPresent"),
            "floatingAiOverlapsMain": known_debt.get("floatingAiOverlapsMain"),
        }
        if (
            any(not isinstance(value, bool) for value in expected_debt_projection.values())
            or dict(known_debt) != expected_debt_projection
        ):
            raise _ux1b_manifest_error(
                f"{phase}.captures[{index}] known-debt classification is invalid"
            )
        normalized_captures[identity_key] = {
            "route": page.route,
            "navTitle": page.nav_title,
            "identity": expected_identity,
            "readyMarker": exact_capture["readyMarker"],
            "fixture": expected_fixture,
            "fixtureContract": expected_fixture_evidence,
            "network": {
                "blockedExternalRequests": [],
                "blockedServerNetwork": [],
            },
            "metrics": dict(metrics),
            "componentMetrics": dict(component),
            "knownDebt": dict(known_debt),
        }
    if set(normalized_captures) != expected_keys:
        raise _ux1b_manifest_error(f"{phase} capture identity set is incomplete")
    ordered_captures = [
        normalized_captures[("chromium", page.registry_key, viewport_name)]
        for page in UX1B_PAGE_PROJECTION
        for viewport_name, _width, _height in UX1B_VIEWPORTS
    ]
    return {
        "tool": dict(_require_mapping(value.get("tool"), f"{phase}.tool")),
        "environment": dict(
            _require_mapping(value.get("environment"), f"{phase}.environment")
        ),
        "projectionSha256": UX1B_PROJECTION_SHA256,
        "pageIdentityCatalog": expected_catalog,
        "readyMarkers": _ux1b_ready_marker_catalog(),
        "fixtureRevision": UX1B_EXPECTED_FIXTURE_REVISION,
        "fixtureContractSchema": UX1B_EXPECTED_CONTRACT_SCHEMA_VERSION,
        "server": server_projection,
        "captures": ordered_captures,
    }


def compare_ux1b_manifests(
    pretheme: Mapping[str, Any], posttheme: Mapping[str, Any]
) -> dict[str, Any]:
    """Require exact non-theme parity across authenticated pre/post manifests."""

    before = normalize_ux1b_manifest_contract(pretheme, phase="pretheme")
    after = normalize_ux1b_manifest_contract(posttheme, phase="posttheme")
    difference = _first_contract_difference(before, after)
    if difference is not None:
        raise _ux1b_manifest_error(f"pretheme/posttheme mismatch at {difference}")
    payload = json.dumps(
        before, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "status": "passed",
        "comparedCaptureCount": 81,
        "normalizedContractSha256": hashlib.sha256(payload).hexdigest(),
    }


def load_authenticated_pretheme_manifest(
    contract_path: Path = UX1B_THEME_CONTRACT_PATH,
) -> AuthenticatedPretheme:
    """Load the SHA-authenticated pretheme manifest frozen by Task 2."""

    unresolved_contract = contract_path.expanduser()
    if unresolved_contract.is_symlink():
        raise _ux1b_manifest_error("theme contract must not be a symlink")
    selected_contract = unresolved_contract.resolve()
    try:
        contract_bytes = selected_contract.read_bytes()
        contract = json.loads(contract_bytes)
    except (OSError, ValueError) as exc:
        raise _ux1b_manifest_error(
            f"theme contract is missing or malformed: {selected_contract.name}"
        ) from exc
    contract_object = _require_mapping(contract, "themeContract")
    if contract_object.get("schemaVersion") != UX1B_THEME_CONTRACT_SCHEMA_VERSION:
        raise _ux1b_manifest_error("theme contract schemaVersion is incompatible")
    reference = _require_mapping(
        contract_object.get("prethemeManifest"), "themeContract.prethemeManifest"
    )
    relative_text = reference.get("path")
    expected_sha = reference.get("sha256")
    if (
        not isinstance(relative_text, str)
        or not relative_text
        or Path(relative_text).is_absolute()
        or "\\" in relative_text
        or ".." in Path(relative_text).parts
        or not isinstance(expected_sha, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_sha) is None
    ):
        raise _ux1b_manifest_error("pretheme manifest reference is invalid")
    unresolved_manifest = ROOT / relative_text
    manifest_path = unresolved_manifest.resolve()
    ux1b_root = (ROOT / ".claude" / "ui_snapshots" / "ux1b").resolve()
    if (
        unresolved_manifest.is_symlink()
        or unresolved_manifest.parent.is_symlink()
        or manifest_path.name != "manifest.json"
        or manifest_path.parent.parent != ux1b_root
        or not manifest_path.parent.name.startswith("pretheme-")
    ):
        raise _ux1b_manifest_error(
            "pretheme manifest must be a direct pretheme-* UX1B manifest"
        )
    try:
        manifest_bytes = manifest_path.read_bytes()
    except OSError as exc:
        raise _ux1b_manifest_error("authenticated pretheme manifest is unreadable") from exc
    actual_sha = hashlib.sha256(manifest_bytes).hexdigest()
    if not secrets.compare_digest(actual_sha, expected_sha):
        raise _ux1b_manifest_error("authenticated pretheme manifest SHA-256 mismatch")
    try:
        manifest = json.loads(manifest_bytes)
    except (TypeError, ValueError) as exc:
        raise _ux1b_manifest_error("authenticated pretheme manifest JSON is malformed") from exc
    manifest_object = _require_mapping(manifest, "prethemeManifest")
    normalize_ux1b_manifest_contract(manifest_object, phase="pretheme")
    return AuthenticatedPretheme(
        contract_path=selected_contract,
        manifest_path=manifest_path,
        manifest_sha256=actual_sha,
        manifest=dict(manifest_object),
    )


def sanitize_text(
    value: str,
    *,
    workspace: Path,
    run_dir: Path,
    secrets: Iterable[str] = (),
) -> str:
    text = str(value)
    replacements = (
        (str(workspace), "<workspace>"),
        (str(workspace.resolve()), "<workspace>"),
        (str(run_dir), "<run-dir>"),
        (str(run_dir.resolve()), "<run-dir>"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "<redacted>")
    for pattern, replacement in _CREDENTIAL_PATTERNS:
        text = pattern.sub(replacement, text)
    text = _URI_USERINFO_RE.sub(r"\1<redacted>@", text)
    text = _CREDENTIAL_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group(1)}{match.group(2)}<redacted>",
        text,
    )
    text = _ABSOLUTE_PATH_RE.sub("<absolute-path>", text)
    return text


def sanitize_value(
    value: Any,
    *,
    workspace: Path,
    run_dir: Path,
    secrets: Iterable[str] = (),
) -> Any:
    if isinstance(value, str):
        return sanitize_text(value, workspace=workspace, run_dir=run_dir, secrets=secrets)
    if isinstance(value, list):
        return [
            sanitize_value(item, workspace=workspace, run_dir=run_dir, secrets=secrets)
            for item in value
        ]
    if isinstance(value, tuple):
        return [
            sanitize_value(item, workspace=workspace, run_dir=run_dir, secrets=secrets)
            for item in value
        ]
    if isinstance(value, dict):
        return {
            str(key): sanitize_value(item, workspace=workspace, run_dir=run_dir, secrets=secrets)
            for key, item in value.items()
        }
    return value


def _terminal_diagnostic_message(exc: BaseException, owned: OwnedRun) -> str:
    """Return one bounded, credential-free message for terminal evidence."""

    raw = str(exc)[:_DIAGNOSTIC_INPUT_CHARS]
    sanitized = sanitize_text(
        raw,
        workspace=ROOT,
        run_dir=owned.run_dir,
        secrets=(owned.run_token,),
    )
    return sanitized[:MAX_DIAGNOSTIC_MESSAGE_CHARS]


def _terminal_diagnostic(
    exc: BaseException, owned: OwnedRun
) -> dict[str, str]:
    raw_type = type(exc).__name__[: MAX_DIAGNOSTIC_TYPE_CHARS * 2]
    sanitized_type = sanitize_text(
        raw_type,
        workspace=ROOT,
        run_dir=owned.run_dir,
        secrets=(owned.run_token,),
    )[:MAX_DIAGNOSTIC_TYPE_CHARS]
    return {
        "type": sanitized_type or "Exception",
        "message": _terminal_diagnostic_message(exc, owned),
    }


def choose_ephemeral_port() -> int:
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            probe.bind(("127.0.0.1", 0))
            port = int(probe.getsockname()[1])
        if port != 8000:
            return port


class OwnedDenyProxy:
    """A run-owned endpoint that records and rejects every proxy connection."""

    def __init__(self) -> None:
        while True:
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            listener.bind(("127.0.0.1", 0))
            if int(listener.getsockname()[1]) != 8000:
                break
            listener.close()
        listener.listen(16)
        listener.settimeout(0.1)
        self._listener = listener
        self.port = int(listener.getsockname()[1])
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._attempts: list[dict[str, Any]] = []
        self._thread = threading.Thread(
            target=self._serve,
            name="ux1b-owned-deny-proxy",
            daemon=True,
        )
        self._thread.start()

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                connection, _address = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with connection:
                connection.settimeout(0.2)
                try:
                    payload = connection.recv(4096)
                except OSError:
                    payload = b""
                first_line = payload.splitlines()[0][:300] if payload else b""
                with self._lock:
                    self._attempts.append(
                        {
                            "bytes": len(payload),
                            "request": first_line.decode("ascii", errors="replace"),
                        }
                    )
                try:
                    connection.sendall(
                        b"HTTP/1.1 502 Bad Gateway\r\n"
                        b"Connection: close\r\nContent-Length: 0\r\n\r\n"
                    )
                except OSError:
                    pass

    def reset(self) -> None:
        with self._lock:
            self._attempts.clear()

    def attempts(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._attempts]

    def wait_for_attempts(self, minimum: int, *, timeout: float = 1.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if len(self.attempts()) >= minimum:
                return True
            time.sleep(0.01)
        return len(self.attempts()) >= minimum

    def close(self) -> None:
        self._stop.set()
        try:
            self._listener.close()
        finally:
            self._thread.join(timeout=1.0)


def build_darwin_sandbox_profile(contract: UX1BNetworkContract) -> str:
    """Return a Seatbelt profile with only the run's two outbound ports."""

    ports = ux1b_allowed_ports(contract)
    if len(ports) != 2 or 8000 in ports or any(not 1 <= port <= 65535 for port in ports):
        raise RunnerDataError("UX1B sandbox requires two distinct non-API ports")
    rules = [
        "(version 1)",
        "(allow default)",
        "(deny network-outbound)",
    ]
    rules.extend(
        f'(allow network-outbound (remote tcp "localhost:{port}"))'
        for port in (contract.streamlit_port, contract.deny_proxy_port)
    )
    return "\n".join(rules) + "\n"


_SANDBOX_CALIBRATION_SCRIPT = r"""
import json
import socket
import sys

ports = json.loads(sys.argv[1])

def attempt(host, port):
    try:
        with socket.create_connection((host, port), timeout=0.75) as connection:
            connection.sendall(b"GET /_stcore/health HTTP/1.0\r\nHost: calibration\r\n\r\n")
        return {"connected": True, "errno": None}
    except OSError as exc:
        return {"connected": False, "errno": getattr(exc, "errno", None)}

print(json.dumps({
    "streamlit": attempt("127.0.0.1", ports["streamlit"]),
    "denyProxy": attempt("127.0.0.1", ports["denyProxy"]),
    "dummyLoopback": attempt("127.0.0.1", ports["dummyLoopback"]),
    "api8000": attempt("127.0.0.1", 8000),
    "testNet": attempt("203.0.113.1", 9),
}, sort_keys=True))
"""


def calibrate_darwin_sandbox_contract(
    contract: UX1BNetworkContract,
    *,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Prove Darwin's kernel profile allows two ports and contacts no dummy."""

    if sys.platform != "darwin":
        return {
            "capability": "not_applicable",
            "passed": True,
            "exactPortContract": True,
            "dummyListenerBytes": 0,
        }
    sandbox = Path("/usr/bin/sandbox-exec")
    if not sandbox.is_file():
        raise DependencyUnavailable(
            "Darwin UX1B requires /usr/bin/sandbox-exec kernel isolation"
        )
    while True:
        dummy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dummy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        dummy.bind(("127.0.0.1", 0))
        dummy_port = int(dummy.getsockname()[1])
        if dummy_port not in ux1b_allowed_ports(contract) and dummy_port != 8000:
            break
        dummy.close()
    dummy.listen(1)
    dummy.settimeout(0.1)
    payload = json.dumps(
        {
            "streamlit": contract.streamlit_port,
            "denyProxy": contract.deny_proxy_port,
            "dummyLoopback": dummy_port,
        },
        sort_keys=True,
    )
    try:
        completed = subprocess.run(
            [
                str(sandbox),
                "-p",
                build_darwin_sandbox_profile(contract),
                sys.executable,
                "-c",
                _SANDBOX_CALIBRATION_SCRIPT,
                payload,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            text=True,
        )
        try:
            connection, _address = dummy.accept()
        except socket.timeout:
            dummy_bytes = 0
            dummy_contact = False
        else:
            dummy_contact = True
            with connection:
                connection.settimeout(0.1)
                try:
                    dummy_bytes = len(connection.recv(4096))
                except OSError:
                    dummy_bytes = 0
    finally:
        dummy.close()
    if completed.returncode != 0:
        raise RunnerDataError(
            "Darwin UX1B sandbox calibration child failed: "
            + sanitize_text(
                completed.stderr[-600:],
                workspace=ROOT,
                run_dir=ROOT / ".claude" / "ui_snapshots" / "ux1b",
            )
        )
    try:
        attempts = json.loads(completed.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RunnerDataError("Darwin UX1B sandbox calibration output is invalid") from exc
    passed = bool(
        attempts.get("streamlit", {}).get("connected")
        and attempts.get("denyProxy", {}).get("connected")
        and not attempts.get("dummyLoopback", {}).get("connected")
        and not attempts.get("api8000", {}).get("connected")
        and not attempts.get("testNet", {}).get("connected")
        and not dummy_contact
        and dummy_bytes == 0
    )
    result = {
        "capability": "supported",
        "passed": passed,
        "exactPortContract": True,
        "allowedEndpointCount": 2,
        "streamlitAllowed": bool(attempts.get("streamlit", {}).get("connected")),
        "denyProxyAllowed": bool(attempts.get("denyProxy", {}).get("connected")),
        "dummyLoopbackDenied": not bool(
            attempts.get("dummyLoopback", {}).get("connected")
        ),
        "dummyLoopbackErrno": attempts.get("dummyLoopback", {}).get("errno"),
        "api8000Denied": not bool(attempts.get("api8000", {}).get("connected")),
        "api8000Errno": attempts.get("api8000", {}).get("errno"),
        "testNetDenied": not bool(attempts.get("testNet", {}).get("connected")),
        "testNetErrno": attempts.get("testNet", {}).get("errno"),
        "dummyListenerBytes": dummy_bytes,
    }
    if not passed:
        raise RunnerDataError("Darwin UX1B exact-two-port sandbox calibration failed")
    return result


def start_owned_process(
    command: Sequence[str],
    *,
    env: Mapping[str, str] | None,
    log_path: Path | None,
    cwd: Path | None = None,
) -> subprocess.Popen[bytes]:
    log_handle: Any
    if log_path is None:
        log_handle = open(os.devnull, "wb")  # noqa: SIM115 - kept until child cleanup
    else:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        os.chmod(log_path, 0o600)
        log_handle = os.fdopen(descriptor, "ab", buffering=0)
    kwargs: dict[str, Any] = {
        "cwd": str(cwd) if cwd else None,
        "env": dict(env) if env is not None else None,
        "stdin": subprocess.DEVNULL,
        "stdout": log_handle,
        "stderr": subprocess.STDOUT,
    }
    if os.name == "posix":
        kwargs["start_new_session"] = True
    elif hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        process = subprocess.Popen(list(command), **kwargs)
    except Exception:
        log_handle.close()
        raise
    setattr(process, "_ux0_log_handle", log_handle)
    return process


def _close_process_log(process: subprocess.Popen[Any]) -> None:
    handle = getattr(process, "_ux0_log_handle", None)
    if handle is not None and not handle.closed:
        handle.close()


def stop_owned_process(process: subprocess.Popen[Any], *, timeout: float = 5.0) -> None:
    if process.poll() is None:
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            except ProcessLookupError:
                pass
            process.wait(timeout=max(1.0, timeout))
    _close_process_log(process)


def _ux1b_streamlit_base_path(fixture_entrypoint: str) -> str:
    if fixture_entrypoint == UX1B_FIXTURE_ENTRYPOINTS[UX1B_PROFILE]:
        return ""
    if fixture_entrypoint == UX1B_FIXTURE_ENTRYPOINTS[UX1B_SELECTION_PROFILE]:
        return UX1B_SELECTION_BASE_PATH
    raise RunnerDataError("fixture entrypoint has no owned Streamlit base path")


def wait_for_health(
    port: int,
    process: Any,
    *,
    timeout: float = 30.0,
    base_path: str = "",
) -> bool:
    if base_path not in {"", UX1B_SELECTION_BASE_PATH}:
        raise RunnerDataError("Streamlit health base path is not owned")
    deadline = time.monotonic() + timeout
    prefix = f"/{base_path}" if base_path else ""
    url = f"http://127.0.0.1:{port}{prefix}/_stcore/health"
    while time.monotonic() < deadline:
        code = process.poll()
        if code is not None:
            raise ServerExited(int(code))
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    return True
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.1)
    raise TimeoutError(f"owned Streamlit health deadline exceeded on loopback port {port}")


def _log_tail(path: Path, *, limit: int = 60) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-limit:])


def _is_bind_race(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in ("address already in use", "errno 48", "errno 98", "port is already in use")
    )


def _start_streamlit(
    owned: OwnedRun,
    *,
    attempts: int = 3,
    profile: str | None = None,
    phase: str | None = None,
    deny_proxy_port: int | None = None,
) -> tuple[subprocess.Popen[bytes], int]:
    for attempt in range(attempts):
        port = choose_ephemeral_port()
        if profile == UX1B_PROFILE and port == deny_proxy_port:
            continue
        network_contract = (
            UX1BNetworkContract(port, int(deny_proxy_port))
            if profile == UX1B_PROFILE and deny_proxy_port is not None
            else None
        )
        env = fixture_environment(
            owned,
            profile=profile,
            phase=phase,
            network_contract=network_contract,
        )
        command = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "scripts/ui_ux_fixture_app.py",
            "--server.address",
            "127.0.0.1",
            "--server.port",
            str(port),
            "--server.headless",
            "true",
            "--server.fileWatcherType",
            "none",
            "--browser.gatherUsageStats",
            "false",
        ]
        if profile == UX1B_PROFILE and sys.platform == "darwin":
            sandbox = Path("/usr/bin/sandbox-exec")
            if not sandbox.is_file() or network_contract is None:
                raise DependencyUnavailable(
                    "Darwin UX1B requires sandbox-exec and an exact port contract"
                )
            command = [
                str(sandbox),
                "-p",
                build_darwin_sandbox_profile(network_contract),
                *command,
            ]
        process = start_owned_process(command, env=env, log_path=owned.log_path, cwd=ROOT)
        try:
            wait_for_health(port, process, timeout=30.0)
            return process, port
        except ServerExited:
            stop_owned_process(process)
            if attempt + 1 < attempts and _is_bind_race(_log_tail(owned.log_path)):
                continue
            raise
        except BaseException:
            # Signal handlers raise RunnerInterrupted (a KeyboardInterrupt
            # subclass).  Cleanup must happen before the caller can assign the
            # returned process handle, and therefore cannot be Exception-only.
            stop_owned_process(process)
            raise
    raise RuntimeError("unreachable Streamlit start retry state")


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _browser_availability(playwright: Any) -> dict[str, bool]:
    return {
        name: Path(getattr(playwright, name).executable_path).is_file()
        for name in ("chromium", "webkit")
    }


def _read_calls(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        raise RunnerDataError(f"invalid fixture counter data: {type(exc).__name__}") from exc
    if not isinstance(data, dict):
        raise RunnerDataError("fixture counter root must be an object")
    return data


def load_ux1b_fixture_contracts() -> dict[str, Any]:
    """Load and validate the fixture's public per-route contract tables."""

    try:
        import ui_ux_fixtures as fixtures
    except ImportError as exc:  # pragma: no cover - script directory is normally importable.
        raise RunnerDataError("cannot import UX1B fixture contracts") from exc
    expected_keys = {item.registry_key for item in UX1B_PAGE_PROJECTION}
    render = dict(getattr(fixtures, "ROUTE_RENDER_CALLABLES", {}))
    counters = dict(getattr(fixtures, "ROUTE_COUNTER_CONTRACTS", {}))
    owned_paths = dict(getattr(fixtures, "ROUTE_OWNED_PATHS", {}))
    counter_schema_version = getattr(fixtures, "COUNTER_SCHEMA_VERSION", None)
    legacy_fixture_revision = getattr(fixtures, "FIXTURE_REVISION", None)
    fixture_revision = getattr(fixtures, "UX1B_FIXTURE_REVISION", None)
    contract_schema_version = getattr(
        fixtures, "UX1B_CONTRACT_SCHEMA_VERSION", None
    )
    if (
        isinstance(counter_schema_version, bool)
        or isinstance(contract_schema_version, bool)
        or counter_schema_version != LEGACY_COUNTER_SCHEMA_VERSION
        or legacy_fixture_revision != LEGACY_EXPECTED_FIXTURE_REVISION
        or fixture_revision != UX1B_EXPECTED_FIXTURE_REVISION
        or contract_schema_version != UX1B_EXPECTED_CONTRACT_SCHEMA_VERSION
        or fixture_revision == legacy_fixture_revision
    ):
        raise RunnerDataError("UX1B fixture schema/revision contract is invalid")
    if set(render) != expected_keys or set(counters) != expected_keys or set(owned_paths) != expected_keys:
        raise RunnerDataError("UX1B fixture contract route projection is incomplete")
    expected_render = {
        item.registry_key: item.callable_name for item in UX1B_PAGE_PROJECTION
    }
    if render != expected_render:
        raise RunnerDataError("UX1B fixture callable projection differs from the frozen pages")
    normalized_counters: dict[str, Any] = {}
    normalized_paths: dict[str, Any] = {}
    for key in expected_keys:
        counter = counters[key]
        if not isinstance(counter, Mapping):
            raise RunnerDataError(f"UX1B fixture counter contract is invalid for {key}")
        positive = counter.get("positive")
        zero = counter.get("zero")
        if not isinstance(positive, Mapping) or not isinstance(zero, (set, frozenset, tuple, list)):
            raise RunnerDataError(f"UX1B fixture counter contract is incomplete for {key}")
        normalized_positive = dict(positive)
        if any(
            not isinstance(name, str)
            or not isinstance(value, int)
            or isinstance(value, bool)
            or value <= 0
            for name, value in normalized_positive.items()
        ):
            raise RunnerDataError(f"UX1B fixture positive counters are invalid for {key}")
        normalized_zero = frozenset(str(name) for name in zero)
        if set(normalized_positive) & normalized_zero:
            raise RunnerDataError(f"UX1B fixture counter roles overlap for {key}")
        route_paths = owned_paths[key]
        if not isinstance(route_paths, Mapping) or any(
            not isinstance(label, str) or not isinstance(path, str)
            for label, path in route_paths.items()
        ):
            raise RunnerDataError(f"UX1B fixture owned-path contract is invalid for {key}")
        normalized_counters[key] = {
            "positive": normalized_positive,
            "zero": normalized_zero,
        }
        normalized_paths[key] = dict(route_paths)
    return {
        "counterSchemaVersion": counter_schema_version,
        "contractSchemaVersion": contract_schema_version,
        "fixtureRevision": fixture_revision,
        "legacyFixtureRevision": legacy_fixture_revision,
        "render": render,
        "counters": normalized_counters,
        "ownedPaths": normalized_paths,
    }


def validate_fixture_calls_contract(
    calls: Mapping[str, Any],
    *,
    profile: str | None,
    fixture_contracts: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Validate child counter transport without rewriting the legacy contract."""

    if not isinstance(calls, Mapping):
        raise RunnerDataError("fixture counter root must be an object")
    if profile == UX1B_PROFILE:
        if fixture_contracts is None:
            raise RunnerDataError("UX1B fixture profile contract is unavailable")
        expected_schema = fixture_contracts.get("counterSchemaVersion")
        expected_contract_schema = fixture_contracts.get("contractSchemaVersion")
        expected_revision = fixture_contracts.get("fixtureRevision")
        if (
            expected_schema != LEGACY_COUNTER_SCHEMA_VERSION
            or expected_contract_schema
            != UX1B_EXPECTED_CONTRACT_SCHEMA_VERSION
            or expected_revision != UX1B_EXPECTED_FIXTURE_REVISION
            or calls.get("schemaVersion") != expected_schema
            or calls.get("contractSchema") != expected_contract_schema
            or calls.get("fixtureRevision") != expected_revision
        ):
            raise RunnerDataError(
                "UX1B child fixture schema/revision is missing or incompatible"
            )
        return {
            "fixtureRevision": expected_revision,
            "contractSchema": expected_contract_schema,
        }
    revision = calls.get("fixtureRevision")
    if (
        calls.get("schemaVersion") != LEGACY_COUNTER_SCHEMA_VERSION
        or not isinstance(revision, str)
    ):
        raise RunnerDataError("fixture counter schema/revision is missing or incompatible")
    return {"fixtureRevision": revision, "contractSchema": None}


def ux1b_fixture_contract_failures(
    bucket: Mapping[str, Any],
    *,
    page: PageProjection,
    owned: OwnedRun,
    contracts: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    identity = bucket.get("identity")
    if not isinstance(identity, Mapping):
        return ["missing_fixture_identity"]
    selected = identity.get("selectedRegistryKey")
    real_callable = identity.get("realCallable")
    if selected != page.registry_key:
        failures.append("fixture_registry_identity_mismatch")
    if real_callable != page.callable_name:
        failures.append("fixture_callable_identity_mismatch")
    resolved = identity.get("resolvedOwnedPaths")
    expected_paths = contracts["ownedPaths"][page.registry_key]
    if not isinstance(resolved, Mapping) or set(resolved) != set(expected_paths):
        failures.append("fixture_owned_path_projection_mismatch")
    else:
        for label, relative in expected_paths.items():
            try:
                actual = Path(str(resolved[label])).resolve()
            except (OSError, ValueError):
                failures.append("fixture_owned_path_projection_mismatch")
                break
            expected = (owned.fixture_root / str(relative)).resolve()
            if actual != expected or (
                actual != owned.fixture_root and owned.fixture_root not in actual.parents
            ):
                failures.append("fixture_owned_path_projection_mismatch")
                break
    counts = bucket.get("counts")
    contract = contracts["counters"][page.registry_key]
    if not isinstance(counts, Mapping):
        failures.append("missing_fixture_capture")
    else:
        positive = contract["positive"]
        zero = contract["zero"]
        if any(counts.get(name) != value for name, value in positive.items()):
            failures.append("fixture_positive_counter_mismatch")
        if any(counts.get(name, 0) != 0 for name in zero):
            failures.append("fixture_zero_counter_mismatch")
        declared = set(positive) | set(zero)
        if any(name not in declared for name in counts):
            failures.append("fixture_undeclared_counter")
    return list(dict.fromkeys(failures))


def ux1b_fixture_contract_evidence(
    bucket: Mapping[str, Any],
    *,
    page: PageProjection,
    owned: OwnedRun,
    contracts: Mapping[str, Any],
) -> dict[str, Any]:
    """Project provider/root contracts without persisting absolute run paths."""

    contract = contracts["counters"][page.registry_key]
    expected_paths = dict(contracts["ownedPaths"][page.registry_key])
    identity = bucket.get("identity")
    resolved = identity.get("resolvedOwnedPaths") if isinstance(identity, Mapping) else None
    resolved_projection: dict[str, str] = {}
    if isinstance(resolved, Mapping):
        for label in expected_paths:
            try:
                relative = Path(str(resolved[label])).resolve().relative_to(
                    owned.fixture_root.resolve()
                )
            except (KeyError, OSError, ValueError):
                resolved_projection[label] = "<invalid-owned-path>"
            else:
                resolved_projection[label] = relative.as_posix()
    return {
        "positiveCounters": dict(contract["positive"]),
        "zeroCounters": sorted(contract["zero"]),
        "ownedPaths": expected_paths,
        "resolvedOwnedPaths": resolved_projection,
    }


def _capture_bucket(data: Mapping[str, Any], capture_id: str) -> dict[str, Any]:
    captures = data.get("captures")
    if not isinstance(captures, dict):
        return {}
    bucket = captures.get(capture_id)
    return dict(bucket) if isinstance(bucket, dict) else {}


def wait_for_capture_quiescence(path: Path, capture_id: str, *, timeout: float = 3.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    previous: str | None = None
    stable = 0
    latest: dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = _capture_bucket(_read_calls(path), capture_id)
        signature = json.dumps(latest, ensure_ascii=False, sort_keys=True)
        if signature == previous and latest:
            stable += 1
            if stable >= 2:
                return latest
        else:
            stable = 0
            previous = signature
        time.sleep(0.1)
    raise CaptureNotQuiescent(latest)


def capture_failure_reasons(evidence: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not evidence.get("headingReady"):
        reasons.append("heading_not_ready")
    if evidence.get("streamlitException"):
        reasons.append("streamlit_exception")
    if evidence.get("pageErrors"):
        reasons.append("page_exception")
    if evidence.get("blockedExternalRequests"):
        reasons.append("external_browser_request")
    if evidence.get("blockedServerNetwork"):
        reasons.append("external_server_request")
    if evidence.get("profile") == UX1B_PROFILE:
        identity = evidence.get("identity")
        if not isinstance(identity, Mapping):
            reasons.append("missing_capture_identity")
        else:
            if identity.get("finalBrowserPath") != identity.get("requestedRoute"):
                reasons.append("final_route_mismatch")
            if identity.get("selectedRegistryKey") != identity.get(
                "expectedRegistryKey"
            ):
                reasons.append("fixture_registry_identity_mismatch")
            if identity.get("realCallable") != identity.get("expectedCallable"):
                reasons.append("fixture_callable_identity_mismatch")
        contract_failures = evidence.get("fixtureContractFailures")
        if isinstance(contract_failures, list):
            reasons.extend(str(item) for item in contract_failures)
    if evidence.get("fixtureQuiescent") is False:
        reasons.append("fixture_counter_not_quiescent")
    if not isinstance(evidence.get("metrics"), dict):
        reasons.append("missing_structural_metrics")
    if evidence.get("focusedCase"):
        component = evidence.get("componentMetrics")
        if not isinstance(component, dict) or not component.get("present"):
            reasons.append("missing_component_metrics")
        elif component.get("horizontalOverflow") is True:
            reasons.append("component_horizontal_overflow")
        interaction = evidence.get("interaction")
        if not isinstance(interaction, dict) or not interaction.get("completed"):
            reasons.append("case_interaction_incomplete")
        elif any(
            not isinstance(action, dict) or not action.get("completed")
            for action in interaction.get("setupActions") or []
        ):
            reasons.append("case_setup_incomplete")
    fixture = evidence.get("fixture")
    if not isinstance(fixture, dict) or not isinstance(fixture.get("counts"), dict):
        reasons.append("missing_fixture_capture")
    return list(dict.fromkeys(reasons))


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

_METRICS_SCRIPT = """
() => {
  const rect = (selector) => {
    const el = document.querySelector(selector);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return {x:r.x, y:r.y, width:r.width, height:r.height,
            visible: style.display !== 'none' && style.visibility !== 'hidden' && r.width > 0 && r.height > 0};
  };
  const doc = document.documentElement;
  const body = document.body;
  const sidebar = rect('[data-testid="stSidebar"]');
  const main = rect('[data-testid="stMain"]') || rect('[data-testid="stAppViewContainer"]');
  let overlap = false;
  if (sidebar && main && sidebar.visible && main.visible) {
    overlap = sidebar.x < main.x + main.width && sidebar.x + sidebar.width > main.x &&
              sidebar.y < main.y + main.height && sidebar.y + sidebar.height > main.y;
  }
  return {
    viewportWidth: window.innerWidth,
    viewportHeight: window.innerHeight,
    documentClientWidth: doc.clientWidth,
    documentScrollWidth: Math.max(doc.scrollWidth, body ? body.scrollWidth : 0),
    documentScrollHeight: Math.max(doc.scrollHeight, body ? body.scrollHeight : 0),
    horizontalOverflow: Math.max(doc.scrollWidth, body ? body.scrollWidth : 0) > doc.clientWidth + 1,
    sidebar,
    main,
    sidebarOverlapsMain: overlap,
    plotlyCharts: document.querySelectorAll('.js-plotly-plot').length
  };
}
"""

_COMPONENT_METRICS_SCRIPT = """
({selector, name}) => {
  const el = document.querySelector(selector);
  if (!el) {
    return {name, present: false, bounds: null, clientWidth: null,
            scrollWidth: null, horizontalOverflow: null, overflowPixels: null};
  }
  const r = el.getBoundingClientRect();
  const style = getComputedStyle(el);
  const clientWidth = el.clientWidth;
  const scrollWidth = el.scrollWidth;
  return {
    name,
    present: style.display !== 'none' && style.visibility !== 'hidden' &&
             r.width > 0 && r.height > 0,
    bounds: {x:r.x, y:r.y, width:r.width, height:r.height},
    clientWidth,
    scrollWidth,
    horizontalOverflow: scrollWidth > clientWidth + 1,
    overflowPixels: Math.max(0, scrollWidth - clientWidth),
    overflowX: style.overflowX
  };
}
"""

_FLOATING_AI_DEBT_SCRIPT = """
() => {
  const visible = (el) => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  const overlap = (left, right) => {
    if (!visible(left) || !visible(right)) return false;
    const a = left.getBoundingClientRect();
    const b = right.getBoundingClientRect();
    return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
  };
  const floating = document.querySelector('.st-key-ai_chat_float');
  const main = document.querySelector('[data-testid="stMainBlockContainer"]');
  return {
    floatingAiPresent: visible(floating),
    floatingAiOverlapsMain: overlap(floating, main)
  };
}
"""

def _interaction_record(capture_case: CaptureCase) -> dict[str, Any]:
    if capture_case.interaction is None:
        return {
            "type": "none",
            "accessibleName": None,
            "completed": True,
            "setupActions": [],
        }
    accessible_names = {
        "open-ai-chat": "AI",
        "select-institution-portfolio": "機構持倉 · 機構 → 它持有什麼",
    }
    return {
        "type": capture_case.interaction,
        "accessibleName": accessible_names[capture_case.interaction],
        "completed": False,
        "setupActions": [],
    }


def _perform_case_interaction(
    page: Any,
    capture_case: CaptureCase,
    record: dict[str, Any],
    *,
    width: int,
) -> None:
    """Reach an interactive state using only public accessibility locators."""

    if capture_case.focused and width <= 390:
        collapse_name = "keyboard_double_arrow_left"
        setup_action = {
            "type": "collapse-sidebar",
            "accessibleName": collapse_name,
            "completed": False,
        }
        record["setupActions"].append(setup_action)
        collapse = page.get_by_role("button", name=collapse_name, exact=True)
        collapse.click(timeout=30_000)
        page.get_by_role(
            "button", name="keyboard_double_arrow_right", exact=True
        ).wait_for(state="visible", timeout=30_000)
        setup_action["completed"] = True
    if capture_case.interaction is None:
        return
    if capture_case.interaction == "open-ai-chat":
        page.get_by_role("button", name="AI", exact=True).click(timeout=30_000)
        page.get_by_text("AI 對話", exact=True).first.wait_for(
            state="visible", timeout=30_000
        )
    elif capture_case.interaction == "select-institution-portfolio":
        page.get_by_role(
            "button",
            name="機構持倉 · 機構 → 它持有什麼",
            exact=True,
        ).click(timeout=30_000)
        page.get_by_text("某機構 →", exact=False).first.wait_for(
            state="visible", timeout=30_000
        )
    else:  # pragma: no cover - CaptureCase definitions are closed above.
        raise RunnerDataError(f"unsupported case interaction: {capture_case.interaction}")
    record["completed"] = True


def _capture_one(
    browser: Any,
    *,
    browser_name: str,
    capture_case: CaptureCase,
    viewport_name: str,
    width: int,
    height: int,
    port: int,
    owned: OwnedRun,
    profile: str | None = None,
    page_projection: PageProjection | None = None,
    ready_marker: ReadyMarker | None = None,
    network_contract: UX1BNetworkContract | None = None,
    fixture_contracts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    case_name = capture_case.name
    page_name = capture_case.page
    capture_id = f"{browser_name}-{case_name}-{viewport_name}-{secrets.token_hex(3)}"
    if not _CAPTURE_RE.fullmatch(capture_id):
        raise RunnerDataError("generated invalid capture identifier")
    context = browser.new_context(
        viewport={"width": width, "height": height},
        reduced_motion="reduce",
        color_scheme="dark",
        service_workers="block",
    )
    blocked: list[dict[str, str]] = []
    console: list[dict[str, str]] = []
    page_errors: list[dict[str, str]] = []
    failed_requests: list[dict[str, str]] = []
    http_errors: list[dict[str, Any]] = []
    allowed_ports = (
        ux1b_allowed_ports(network_contract)
        if profile == UX1B_PROFILE and network_contract is not None
        else None
    )

    def route_handler(route: Any) -> None:
        url = route.request.url
        if is_allowed_browser_url(url, allowed_ports=allowed_ports):
            route.continue_()
            return
        blocked.append({"method": route.request.method, "url": safe_url_label(url)})
        route.abort("blockedbyclient")

    context.route("**/*", route_handler)

    route_web_socket = getattr(context, "route_web_socket", None)
    if not callable(route_web_socket):
        context.close()
        raise DependencyUnavailable(
            "installed Playwright lacks WebSocket routing required by UX-0"
        )
    route_web_socket(
        "**/*",
        lambda web_socket: handle_browser_web_socket(
            web_socket,
            blocked,
            allowed_ports=allowed_ports,
        ),
    )
    page = context.new_page()
    page.on(
        "console",
        lambda message: console.append(
            {
                "type": message.type,
                "text": sanitize_text(
                    message.text,
                    workspace=ROOT,
                    run_dir=owned.run_dir,
                    secrets=(owned.run_token,),
                )[:1000],
            }
        ),
    )
    page.on(
        "pageerror",
        lambda error: page_errors.append(
            {
                "name": type(error).__name__,
                "message": sanitize_text(
                    str(error),
                    workspace=ROOT,
                    run_dir=owned.run_dir,
                    secrets=(owned.run_token,),
                )[:1000],
            }
        ),
    )

    def on_request_failed(request: Any) -> None:
        failure = request.failure
        failed_requests.append(
            {
                "method": request.method,
                "url": safe_url_label(request.url),
                "error": str(failure or "request_failed")[:300],
            }
        )

    page.on("requestfailed", on_request_failed)

    def on_response(response: Any) -> None:
        if response.status < 400:
            return
        http_errors.append(
            {
                "status": response.status,
                "statusText": str(response.status_text or "")[:120],
                "method": response.request.method,
                "resourceType": response.request.resource_type,
                "url": safe_url_label(response.url),
            }
        )

    page.on("response", on_response)
    relative_dir = Path(browser_name) / case_name
    screenshot_rel = relative_dir / f"{viewport_name}.png"
    screenshot_path = owned.run_dir / screenshot_rel
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    requested_route = (
        page_projection.route
        if profile == UX1B_PROFILE and page_projection is not None
        else route_for_page(page_name)
    )
    heading = (
        ready_marker.text
        if profile == UX1B_PROFILE and ready_marker is not None
        else PAGE_HEADINGS[page_name]
    )
    evidence: dict[str, Any] = {
        "captureId": capture_id,
        "browser": browser_name,
        "case": case_name,
        "focusedCase": capture_case.focused,
        "page": page_name,
        "route": requested_route,
        "viewport": {"name": viewport_name, "width": width, "height": height},
        "heading": heading,
        "headingReady": False,
        "streamlitException": False,
        "console": console,
        "pageErrors": page_errors,
        "failedRequests": failed_requests,
        "httpErrors": http_errors,
        "blockedExternalRequests": blocked,
        "blockedServerNetwork": [],
        "metrics": None,
        "componentMetrics": None,
        "interaction": _interaction_record(capture_case),
        "fixture": {},
        "fixtureQuiescent": None,
        "screenshot": screenshot_rel.as_posix(),
        "status": "failed",
        "failureReasons": [],
    }
    if profile == UX1B_PROFILE:
        if (
            page_projection is None
            or ready_marker is None
            or network_contract is None
            or fixture_contracts is None
        ):
            context.close()
            raise RunnerDataError(
                "UX1B capture is missing its page, fixture, or network contract"
            )
        evidence["profile"] = profile
        evidence["readyMarker"] = {
            "role": "heading",
            "level": ready_marker.level,
            "text": ready_marker.text,
            "match": ready_marker.match,
            "scope": "stMainBlockContainer",
        }
        evidence["identity"] = {
            "requestedRoute": requested_route,
            "finalBrowserPath": None,
            "expectedRegistryKey": page_projection.registry_key,
            "selectedRegistryKey": None,
            "expectedCallable": page_projection.callable_name,
            "realCallable": None,
            "expectedNavTitle": page_projection.nav_title,
        }
        evidence["fixtureContractFailures"] = []
        evidence["fixtureContract"] = {}
        evidence["knownDebt"] = None
    query = urllib.parse.urlencode({"ux0_capture": capture_id})
    url = f"http://127.0.0.1:{port}{requested_route}?{query}"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        if profile == UX1B_PROFILE:
            evidence["identity"]["finalBrowserPath"] = (
                urllib.parse.urlsplit(page.url).path or "/"
            )
        page.locator('[data-testid="stSidebarNav"]').wait_for(state="visible", timeout=30_000)
        if profile == UX1B_PROFILE:
            main = page.locator('[data-testid="stMainBlockContainer"]')
            main.get_by_role(
                "heading",
                name=ready_marker.text,
                exact=ready_marker.match == "exact",
                level=ready_marker.level,
            ).first.wait_for(state="visible", timeout=30_000)
        else:
            page.get_by_role(
                "heading", name=PAGE_HEADINGS[page_name], exact=False
            ).first.wait_for(state="visible", timeout=30_000)
        evidence["headingReady"] = True
        _perform_case_interaction(
            page,
            capture_case,
            evidence["interaction"],
            width=width,
        )
        page.evaluate("() => document.fonts ? document.fonts.ready : Promise.resolve()")
        page.wait_for_function(_READINESS_SCRIPT, timeout=30_000)
        page.wait_for_function(_STABLE_LAYOUT_SCRIPT, timeout=30_000)
        page.wait_for_function(_PLOTLY_READY_SCRIPT, timeout=30_000)
        evidence["streamlitException"] = bool(
            page.locator('[data-testid="stException"]:visible').count()
        )
        evidence["metrics"] = page.evaluate(_METRICS_SCRIPT)
        evidence["componentMetrics"] = page.evaluate(
            _COMPONENT_METRICS_SCRIPT,
            {
                "selector": capture_case.component_selector,
                "name": capture_case.component_name,
            },
        )
        if profile == UX1B_PROFILE:
            floating_debt = page.evaluate(_FLOATING_AI_DEBT_SCRIPT)
            evidence["knownDebt"] = {
                "expandedSidebarOverlapsMain": evidence["metrics"][
                    "sidebarOverlapsMain"
                ],
                "pageHorizontalOverflow": evidence["metrics"][
                    "horizontalOverflow"
                ],
                "floatingAiPresent": floating_debt["floatingAiPresent"],
                "floatingAiOverlapsMain": floating_debt[
                    "floatingAiOverlapsMain"
                ],
            }
        page.screenshot(path=str(screenshot_path), full_page=True, animations="disabled")
    except Exception as exc:  # Playwright exposes version-specific error subclasses.
        diagnostic = _terminal_diagnostic(exc, owned)
        page_errors.append(
            {"name": diagnostic["type"], "message": diagnostic["message"]}
        )
        try:
            if not screenshot_path.exists():
                page.screenshot(path=str(screenshot_path), full_page=True, animations="disabled")
        except Exception:
            pass
    finally:
        context.close()

    try:
        bucket = wait_for_capture_quiescence(owned.calls_path, capture_id)
    except CaptureNotQuiescent as exc:
        bucket = exc.latest
        evidence["fixtureQuiescent"] = False
    else:
        evidence["fixtureQuiescent"] = True
    public_bucket = dict(bucket)
    bucket_identity = bucket.get("identity") if isinstance(bucket, Mapping) else None
    if profile == UX1B_PROFILE and isinstance(bucket_identity, Mapping):
        evidence["identity"]["selectedRegistryKey"] = bucket_identity.get(
            "selectedRegistryKey"
        )
        evidence["identity"]["realCallable"] = bucket_identity.get("realCallable")
        public_bucket["identity"] = {
            "selectedRegistryKey": bucket_identity.get("selectedRegistryKey"),
            "realCallable": bucket_identity.get("realCallable"),
        }
    evidence["fixture"] = public_bucket
    blocked_server = bucket.get("blockedNetwork") if isinstance(bucket, dict) else None
    if isinstance(blocked_server, list):
        evidence["blockedServerNetwork"] = blocked_server
    if (
        profile == UX1B_PROFILE
        and page_projection is not None
        and fixture_contracts is not None
    ):
        evidence["fixtureContractFailures"] = ux1b_fixture_contract_failures(
            bucket,
            page=page_projection,
            owned=owned,
            contracts=fixture_contracts,
        )
        evidence["fixtureContract"] = ux1b_fixture_contract_evidence(
            bucket,
            page=page_projection,
            owned=owned,
            contracts=fixture_contracts,
        )
    evidence["failureReasons"] = capture_failure_reasons(evidence)
    evidence["status"] = "passed" if not evidence["failureReasons"] else "failed"
    return evidence


def _manifest_template(
    owned: OwnedRun,
    *,
    cases: Sequence[CaptureCase],
    viewports: Sequence[tuple[str, int, int]],
    profile: str | None = None,
    phase: str | None = None,
) -> dict[str, Any]:
    pages = tuple(dict.fromkeys(capture_case.page for capture_case in cases))
    manifest = {
        "schemaVersion": 1,
        "tool": {"name": "quant-radar-ui-ux-matrix", "version": VERSION},
        "status": "running",
        "run": public_run_metadata(owned),
        "fixtureRevision": None,
        "startedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "environment": {
            "python": ".".join(str(part) for part in sys.version_info[:3]),
            "streamlit": _package_version("streamlit"),
            "playwright": _package_version("playwright"),
            "platform": sys.platform,
        },
        "mode": "ux1a-focused" if any(item.focused for item in cases) else "ux0-pages",
        "pages": list(pages),
        "cases": [
            {
                "name": item.name,
                "page": item.page,
                "route": route_for_page(item.page),
                "component": item.component_name,
                "interaction": item.interaction or "none",
            }
            for item in cases
        ],
        "viewports": [
            {"name": name, "width": width, "height": height}
            for name, width, height in viewports
        ],
        "expectedCapturesPerBrowser": len(cases) * len(viewports),
        "browserCapabilities": {},
        "captures": [],
        "server": {"ownedProcess": True, "loopbackOnly": True, "log": "streamlit.log"},
        "manual": {"safari": "NOT_CHECKED", "humanUsability": "NOT_RUN"},
    }
    if profile == UX1B_PROFILE:
        manifest.update(
            {
                "mode": UX1B_PROFILE,
                "phase": phase,
                "projectionSha256": UX1B_PROJECTION_SHA256,
                "fixtureContractSchema": None,
                "sourceDigestStart": None,
                "sourceDigestEnd": None,
                "sourceDigestEqual": None,
                # Provisional until Task 5 freezes the authenticated capture
                # stack.  Legacy UX-0/UX-1A manifests intentionally omit it.
                "captureStackDigest": None,
                "pageIdentityCatalog": _projection_records(UX1B_PAGE_PROJECTION),
                "readyMarkers": _ux1b_ready_marker_catalog(),
            }
        )
        page_by_key = {item.registry_key: item for item in UX1B_PAGE_PROJECTION}
        manifest["cases"] = [
            {
                "name": item.name,
                "page": item.page,
                "route": page_by_key[item.page].route,
                "component": item.component_name,
                "interaction": item.interaction or "none",
            }
            for item in cases
        ]
        manifest["server"] = {
            "ownedProcess": True,
            "loopbackOnly": True,
            "log": "streamlit.log",
            "exactPortContract": True,
            "allowedEndpointCount": 2,
            "denyProxyOwned": True,
            "kernelIsolation": "pending" if sys.platform == "darwin" else "not_applicable",
        }
    return manifest


def _manifest_finalization_digest(manifest: Mapping[str, Any]) -> str:
    raw = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _owned_run_binding(owned: OwnedRun) -> tuple[Any, ...]:
    return (
        id(owned),
        owned.run_id,
        os.fspath(owned.run_dir),
        os.fspath(owned.manifest_path),
        os.fspath(owned.fixture_root),
        os.fspath(owned.calls_path),
    )


def _has_snapshot_success_closure(manifest: Mapping[str, Any]) -> bool:
    if manifest.get("status") != "finalizing":
        return False
    if manifest.get("mode") == UX1B_PROFILE:
        if manifest.get("sourceDigestEqual") is not True:
            return False
        server = manifest.get("server")
        if not isinstance(server, Mapping) or server.get("denyProxyAttemptCount") != 0:
            return False
        phase = manifest.get("phase")
        if phase == "pretheme":
            validation = manifest.get("manifestContractValidation")
            if not isinstance(validation, Mapping) or validation.get("status") != "passed":
                return False
        elif phase == "posttheme":
            comparison = manifest.get("prethemeComparison")
            if not isinstance(comparison, Mapping) or comparison.get("status") != "passed":
                return False
        else:
            # Recovery phases must use the authenticated lifecycle once Task 5
            # enables them; a provisional legacy manifest may never pass.
            return False
    return True


def _authorize_terminal_manifest(
    manifest: dict[str, Any], *, authority: object
) -> _RunnerFinalizationGrant:
    """Mint a digest-bound, one-use grant after all success closure facts exist."""

    if not isinstance(authority, _RunSuccessAuthority):
        raise RunnerDataError("snapshot run success authority is unavailable")
    with _FINALIZATION_GRANTS_LOCK:
        authority_record = _RUN_SUCCESS_AUTHORITIES.pop(id(authority), None)
        if authority_record is None:
            raise RunnerDataError(
                "snapshot run success authority is stale or unregistered"
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
            or not isinstance(owned, OwnedRun)
            or _owned_run_binding(owned) != owned_binding
        ):
            raise RunnerDataError("snapshot run success authority binding differs")
        if not _has_snapshot_success_closure(manifest):
            raise RunnerDataError("snapshot success closure was not authorized")
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
            or not isinstance(owned, OwnedRun)
            or _owned_run_binding(owned) != owned_binding
        ):
            return False
        if not _has_snapshot_success_closure(manifest):
            return False
        if _manifest_finalization_digest(manifest) != registered_digest:
            return False
        manifest["status"] = "passed"
        return True


def _public_manifest(owned: OwnedRun, manifest: Mapping[str, Any]) -> dict[str, Any]:
    public = sanitize_value(
        dict(manifest), workspace=ROOT, run_dir=owned.run_dir, secrets=(owned.run_token,)
    )
    if not isinstance(public, dict):  # pragma: no cover - dict input stays a dict.
        raise RunnerDataError("public manifest sanitization changed the root type")
    return public


def _write_manifest(owned: OwnedRun, manifest: Mapping[str, Any]) -> None:
    atomic_write_json(owned.manifest_path, _public_manifest(owned, manifest))


def _commit_terminal_manifest(
    owned: OwnedRun, manifest: dict[str, Any], code: int
) -> int:
    """Persist one terminal state without overwriting an already-published commit."""

    try:
        _atomic_terminal_manifest_commit(
            owned.manifest_path, _public_manifest(owned, manifest)
        )
    except KeyboardInterrupt as exc:
        if manifest.get("status") != "failed":
            manifest["status"] = "interrupted"
            manifest["interruption"] = _terminal_diagnostic(exc, owned)
            code = 130
        _atomic_terminal_manifest_commit(
            owned.manifest_path, _public_manifest(owned, manifest)
        )
    except Exception as exc:
        if manifest.get("status") != "interrupted":
            manifest["status"] = "failed"
            manifest["finalizationError"] = _terminal_diagnostic(exc, owned)
            code = 1
        _atomic_terminal_manifest_commit(
            owned.manifest_path, _public_manifest(owned, manifest)
        )
    return code


def _print_progress(message: str, args: argparse.Namespace) -> None:
    if args.quiet or args.json:
        return
    print(message, file=sys.stderr)


def _prepare_args(
    args: argparse.Namespace,
) -> tuple[tuple[CaptureCase, ...], tuple[tuple[str, int, int], ...]]:
    try:
        profile = getattr(args, "profile", None)
        phase = getattr(args, "phase", None)
        theme_contract = getattr(args, "theme_contract", None)
        capture_stack = getattr(args, "capture_stack", "legacy")
        if profile in UX1B_PROFILES:
            allowed_phases = UX1B_PROFILE_PHASES[profile]
            if phase not in allowed_phases:
                raise ValueError(
                    f"{profile} requires --phase " + "|".join(allowed_phases)
                )
            if list(args.browser or []) != ["chromium"]:
                raise ValueError("UX1B profile requires exactly --browser chromium")
            if not args.no_prompt or not args.json:
                raise ValueError("UX1B profile requires --no-prompt and --json")
            if args.case or args.page or args.viewport:
                raise ValueError(
                    "UX1B profile fixes its complete case and viewport matrix"
                )
            if not (
                profile == UX1B_PROFILE and phase == "posttheme"
            ) and theme_contract is not None:
                raise ValueError("--theme-contract is only valid for UX1B posttheme")
            if capture_stack in {"seq12", "seq13"} and not (
                profile == UX1B_SELECTION_PROFILE
                and phase == "postcontrol"
            ):
                raise ValueError(
                    "root capture stack is focused-postcontrol only"
                )
            if profile == UX1B_PROFILE:
                validate_ux1b_projection(live_ux1b_projection())
                cases = tuple(
                    ux1b_page_capture_case(item) for item in UX1B_PAGE_PROJECTION
                )
                viewports = UX1B_VIEWPORTS
            else:
                cases = ux1b_selection_capture_cases()
                viewports = UX1B_SELECTION_VIEWPORTS
            return cases, viewports
        if phase is not None:
            raise ValueError("--phase is only valid with a UX1B profile")
        if theme_contract is not None:
            raise ValueError("--theme-contract is only valid for UX1B posttheme")
        if capture_stack != "legacy":
            raise ValueError(
                "non-legacy capture stack requires focused postcontrol"
            )
        if args.case and args.page:
            raise ValueError("--case cannot be combined with --page")
        if args.case:
            selected_cases = tuple(normalize_case(item) for item in args.case)
            cases = tuple({item.name: item for item in selected_cases}.values())
        else:
            pages = tuple(
                dict.fromkeys(normalize_page(item) for item in (args.page or DEFAULT_PAGES))
            )
            cases = tuple(page_capture_case(page) for page in pages)
        viewport_values = args.viewport or list(DEFAULT_VIEWPORTS)
        viewports = tuple(dict.fromkeys(parse_viewport(item) for item in viewport_values))
    except ValueError as exc:
        raise RunnerDataError(str(exc)) from exc
    if not cases or not viewports:
        raise RunnerDataError("at least one case/page and viewport are required")
    return cases, viewports


def _isolation_api() -> Any:
    _ensure_workspace_import_path()
    from scripts import ui_ux_isolation

    return ui_ux_isolation


def _fixtures_api() -> Any:
    _ensure_workspace_import_path()
    from scripts import ui_ux_fixtures

    return ui_ux_fixtures


def _expanded_ux1b_source_mirror_policy() -> tuple[str, ...]:
    """Materialize the accepted glob policy for the strict mirror primitive."""

    expanded: list[str] = []
    for rule in UX1B_SOURCE_MIRROR_INCLUDE:
        if "*" not in rule:
            candidate = WORKSPACE_ROOT / rule
            if not candidate.is_file() or candidate.is_symlink():
                raise RunnerDataError(
                    f"accepted source-mirror include is unavailable: {rule}"
                )
            expanded.append(rule)
            continue
        matches = sorted(WORKSPACE_ROOT.glob(rule))
        if not matches:
            raise RunnerDataError(
                f"accepted source-mirror include matched no files: {rule}"
            )
        for candidate in matches:
            if not candidate.is_file() or candidate.is_symlink():
                raise RunnerDataError(
                    f"accepted source-mirror include is unsafe: {rule}"
                )
            relative = candidate.relative_to(WORKSPACE_ROOT).as_posix()
            if "__pycache__" in candidate.parts or candidate.suffix != ".py":
                raise RunnerDataError(
                    f"accepted source-mirror include escaped its Python projection: {relative}"
                )
            expanded.append(relative)
    if len(expanded) != len(set(expanded)):
        raise RunnerDataError("accepted source-mirror projection contains duplicates")
    return tuple(sorted(expanded))


def _directory_fd(path: Path) -> int:
    return os.open(
        path,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0),
    )


def _write_private_file(path: Path, raw: bytes) -> None:
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
                raise RunnerDataError("owned private-file write was short")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _canonical_ndjson(value: Mapping[str, Any]) -> bytes:
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
        raise RunnerDataError("worker request is not canonical JSON") from exc


def _ux1b_capture_stack_contract_path(selection: str) -> Path:
    if selection == "legacy":
        return UX1B_CAPTURE_STACK_CONTRACT_PATH
    if selection == "seq12":
        return UX1B_SEQUENCE12_CAPTURE_STACK_CONTRACT_PATH
    if selection == "seq13":
        return UX1B_SEQUENCE13_CAPTURE_STACK_CONTRACT_PATH
    raise RunnerDataError("formal UX1B capture-stack selection is invalid")


def _authenticate_ux1b_capture_stack_contract(
    *,
    workspace_fd: int | None = None,
    selection: str = "legacy",
) -> tuple[dict[str, Any], Any, str]:
    evidence = _evidence_api()
    contract_path = _ux1b_capture_stack_contract_path(selection)
    if workspace_fd is not None:
        relative_path = contract_path.relative_to(
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
            raise RunnerDataError(
                "formal UX1B capture-stack contract failed descriptor authentication"
            ) from exc
        observed_paths = tuple(member["path"] for member in contract["members"])
        if observed_paths != tuple(sorted(UX1B_CAPTURE_STACK_MEMBERS)):
            raise RunnerDataError("formal UX1B capture-stack member set differs")
        if (
            selection in {"seq12", "seq13"}
            and contract.get("rootExpansionSha256")
            != evidence.ROOT_CAPTURE_EXPANSION_SHA256
        ) or (
            selection == "legacy"
            and "rootExpansionSha256" in contract
        ):
            raise RunnerDataError(
                "formal UX1B capture-stack root expansion binding differs"
            )
        return contract, catalog, sha256

    if selection in {"seq12", "seq13"}:
        owned_workspace_fd = _directory_fd(WORKSPACE_ROOT)
        try:
            return _authenticate_ux1b_capture_stack_contract(
                workspace_fd=owned_workspace_fd,
                selection=selection,
            )
        finally:
            os.close(owned_workspace_fd)

    destination: UX1BCaptureStackDestination | None = None
    try:
        destination = _open_ux1b_capture_stack_destination()
        _reauthenticate_ux1b_capture_stack_destination(destination)
        contract, catalog, sha256 = evidence.authenticate_capture_stack_contract(
            destination.workspace_fd,
            destination.relative_path,
            workspace_root_fd=destination.workspace_fd,
            expected_owner=os.getuid(),
        )
        _reauthenticate_ux1b_capture_stack_destination(destination)
    except Exception as exc:
        raise RunnerDataError(
            "formal UX1B capture-stack contract failed descriptor authentication"
        ) from exc
    finally:
        if destination is not None:
            destination.close()
    observed_paths = tuple(member["path"] for member in contract["members"])
    if observed_paths != tuple(sorted(UX1B_CAPTURE_STACK_MEMBERS)):
        raise RunnerDataError("formal UX1B capture-stack member set differs")
    if "rootExpansionSha256" in contract:
        raise RunnerDataError(
            "legacy UX1B capture-stack unexpectedly binds root expansion"
        )
    return contract, catalog, sha256


def _ux1b_counter_expectations(
    rows: Sequence[Mapping[str, Any]],
    *,
    fixture_entrypoint: str,
    app_root: Path,
) -> dict[str, dict[str, Any]]:
    fixtures = _fixtures_api()
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        capture_id = f'{row["case"]}/{row["viewport"]["name"]}'
        if fixture_entrypoint == "scripts/ui_ux_fixture_app.py":
            counter = fixtures.ROUTE_COUNTER_CONTRACTS[row["case"]]
            owned = fixtures.ROUTE_OWNED_PATHS[row["registryKey"]]
        elif fixture_entrypoint == "scripts/ui_ux_selection_fixture_app.py":
            counter = fixtures.SELECTION_COUNTER_CONTRACTS[row["case"]]
            owned = fixtures.SELECTION_OWNED_PATHS[row["case"]]
        else:
            raise RunnerDataError("UX1B fixture counter profile is not supported")
        result[capture_id] = {
            "identityRow": dict(row),
            "positiveCounters": dict(counter["positive"]),
            "zeroCounters": tuple(sorted(counter["zero"])),
            "ownedPaths": {
                name: str((app_root / "fixture-root" / relative).resolve())
                for name, relative in owned.items()
            },
        }
    return result


def _sum_ux1b_counters(
    authenticated_bundle: Mapping[str, Any],
) -> tuple[dict[str, int], dict[str, int]]:
    provider: dict[str, int] = {}
    mutator: dict[str, int] = {}
    for capture in authenticated_bundle["captures"].values():
        for name, value in capture["providerCounters"].items():
            provider[name] = provider.get(name, 0) + int(value)
        for name, value in capture["mutatorCounters"].items():
            mutator[name] = mutator.get(name, 0) + int(value)
    return dict(sorted(provider.items())), dict(sorted(mutator.items()))


def _read_owned_stdio(stream: Any, *, maximum: int) -> bytes:
    descriptor = stream.fileno()
    observed = os.fstat(descriptor)
    if observed.st_size < 0 or observed.st_size > maximum:
        raise RunnerDataError("owned child output exceeded its fixed bound")
    raw = os.pread(descriptor, observed.st_size, 0)
    if len(raw) != observed.st_size:
        raise RunnerDataError("owned child output changed while reading")
    return raw


def _raise_worker_exit(
    evidence: Any,
    stdio: Any,
    *,
    capture_id: str,
    allowed_paths: frozenset[str],
    cause: BaseException,
) -> None:
    """Classify an authenticated worker failure after its leader was reaped."""

    try:
        response = evidence.decode_worker_response(
            _read_owned_stdio(
                stdio.stdout,
                maximum=evidence.MAX_WORKER_RESPONSE_BYTES,
            ),
            expected_request_id=capture_id,
            allowed_artifact_paths=allowed_paths,
        )
    except Exception:
        raise cause
    status = response.get("status")
    error = response.get("error") or {}
    error_type = str(error.get("type") or "WorkerError")
    if status == "dependency_unavailable":
        raise DependencyUnavailable(
            f"browser worker dependency unavailable for {capture_id}: {error_type}"
        ) from cause
    if status == "invalid_data":
        raise RunnerDataError(
            f"browser worker evidence invalid for {capture_id}: {error_type}"
        ) from cause
    if status == "interrupted":
        raise RunnerInterrupted(
            f"browser worker interrupted for {capture_id}: {error_type}"
        ) from cause
    raise RuntimeError(
        f"browser worker failed for {capture_id}: {error_type}"
    ) from cause


def _directory_identity_matches(
    named: os.stat_result,
    opened: os.stat_result,
) -> bool:
    return (
        stat.S_ISDIR(named.st_mode)
        and stat.S_ISDIR(opened.st_mode)
        and (named.st_dev, named.st_ino, named.st_uid)
        == (opened.st_dev, opened.st_ino, opened.st_uid)
    )


def _read_ux1b_manifest_document(
    root_fd: int,
    *,
    require_terminal: bool,
) -> dict[str, Any]:
    descriptor = -1
    try:
        named = os.stat("manifest.json", dir_fd=root_fd, follow_symlinks=False)
        descriptor = os.open(
            "manifest.json",
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=root_fd,
        )
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(named.st_mode)
            or not stat.S_ISREG(opened.st_mode)
            or named.st_uid != os.getuid()
            or (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
            or opened.st_size <= 0
            or opened.st_size > 4 * 1024 * 1024
        ):
            raise RunnerDataError("formal UX1B terminal manifest identity differs")
        stable_before = (
            opened.st_dev,
            opened.st_ino,
            opened.st_uid,
            opened.st_mode,
            opened.st_nlink,
            opened.st_size,
            opened.st_mtime_ns,
        )
        raw = os.pread(descriptor, opened.st_size, 0)
        raw_recheck = os.pread(descriptor, opened.st_size, 0)
        after = os.fstat(descriptor)
        stable_after = (
            after.st_dev,
            after.st_ino,
            after.st_uid,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
        )
        if (
            len(raw) != opened.st_size
            or len(raw_recheck) != opened.st_size
            or stable_after != stable_before
            or hashlib.sha256(raw_recheck).digest()
            != hashlib.sha256(raw).digest()
        ):
            raise RunnerDataError("formal UX1B terminal manifest changed while reading")
        document = json.loads(raw.decode("utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RunnerDataError("formal UX1B terminal manifest is unreadable") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    terminal_states = {
        "passed",
        "failed",
        "invalid_data",
        "dependency_unavailable",
        "interrupted",
    }
    if not isinstance(document, dict) or (
        require_terminal and document.get("status") not in terminal_states
    ):
        raise RunnerDataError("formal UX1B manifest has an invalid state")
    return document


def _read_ux1b_terminal_manifest(root_fd: int) -> dict[str, Any]:
    return _read_ux1b_manifest_document(root_fd, require_terminal=True)


def _make_ux1b_manifest_unreferenceable(root_fd: int) -> None:
    quarantine = f".unreferenceable-manifest-{secrets.token_hex(12)}.json"
    try:
        os.rename(
            "manifest.json",
            quarantine,
            src_dir_fd=root_fd,
            dst_dir_fd=root_fd,
        )
        os.fsync(root_fd)
        return
    except OSError:
        pass
    try:
        os.unlink("manifest.json", dir_fd=root_fd)
        os.fsync(root_fd)
    except OSError as exc:
        raise RunnerDataError(
            "untrusted UX1B passed manifest could not be made unreferenceable"
        ) from exc


def _authenticate_ux1b_passed_bundle(
    evidence: Any,
    root_fd: int,
    expected_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    expected_raw = _canonical_ndjson(expected_manifest)
    expected_sha256 = hashlib.sha256(expected_raw).hexdigest()
    contract = evidence.freeze_manifest_bundle_contract(
        root_fd,
        "manifest.json",
        expected_owner=os.getuid(),
        expected_manifest_sha256=expected_sha256,
    )
    bundle = evidence.reauthenticate_manifest_bundle(root_fd, contract)
    manifest = bundle.manifest
    if manifest != dict(expected_manifest):
        raise RunnerDataError("published UX1B passed manifest differs")
    return manifest


def _retry_ux1b_directory_fsync(
    descriptor: int,
    *,
    attempts: int = 3,
) -> bool:
    if attempts < 1 or attempts > 5:
        raise RunnerDataError("UX1B fsync retry bound is invalid")
    for attempt in range(attempts):
        try:
            os.fsync(descriptor)
            return True
        except OSError:
            if attempt + 1 < attempts:
                time.sleep(0.01)
    return False


def _ux1b_destination_is_retained_root(
    namespace: UX1BOutputNamespace,
    retained: os.stat_result,
) -> bool:
    descriptor = -1
    try:
        _reauthenticate_ux1b_output_namespace(namespace)
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
    except (OSError, RunnerDataError):
        return False
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return (
        _directory_identity_matches(named, opened)
        and (opened.st_dev, opened.st_ino, opened.st_uid)
        == (retained.st_dev, retained.st_ino, retained.st_uid)
        and stat.S_IFMT(opened.st_mode) == stat.S_IFMT(retained.st_mode)
    )


def _export_ux1b_evidence(
    source: Path,
    namespace: UX1BOutputNamespace,
    *,
    source_parent_fd: int,
    final_root_fd: int,
) -> UX1BExportOutcome:
    """Atomically move the exact lifecycle root into the UX1B namespace."""

    if source.name != "final":
        raise RunnerDataError("formal UX1B lifecycle root name differs")
    _reauthenticate_ux1b_output_namespace(namespace)
    retained = os.fstat(final_root_fd)
    source_named = os.stat(
        source.name,
        dir_fd=source_parent_fd,
        follow_symlinks=False,
    )
    if (
        not _directory_identity_matches(source_named, retained)
        or retained.st_uid != os.getuid()
    ):
        raise RunnerDataError("formal UX1B lifecycle root identity differs")
    target_parent = os.fstat(namespace.parent_fd)
    if not stat.S_ISDIR(target_parent.st_mode) or target_parent.st_uid != os.getuid():
        raise RunnerDataError("retained UX1B output parent identity differs")

    renamed = False
    try:
        try:
            existing = os.stat(
                namespace.leaf_name,
                dir_fd=namespace.parent_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            existing = None
        if existing is not None:
            existing_fd = -1
            try:
                existing_fd = os.open(
                    namespace.leaf_name,
                    os.O_RDONLY
                    | getattr(os, "O_DIRECTORY", 0)
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_CLOEXEC", 0),
                    dir_fd=namespace.parent_fd,
                )
                opened = os.fstat(existing_fd)
                unsafe = (
                    not stat.S_ISDIR(existing.st_mode)
                    or existing.st_uid != os.getuid()
                    or (existing.st_dev, existing.st_ino)
                    != (opened.st_dev, opened.st_ino)
                    or bool(os.listdir(existing_fd))
                )
            except OSError:
                unsafe = True
            finally:
                if existing_fd >= 0:
                    os.close(existing_fd)
            if unsafe:
                raise RunnerDataError(
                    f"output directory is not empty: {namespace.path}"
                )
            os.rmdir(namespace.leaf_name, dir_fd=namespace.parent_fd)
        os.rename(
            source.name,
            namespace.leaf_name,
            src_dir_fd=source_parent_fd,
            dst_dir_fd=namespace.parent_fd,
        )
        renamed = True
        if not _ux1b_destination_is_retained_root(namespace, retained):
            raise RunnerDataError("formal UX1B export destination identity differs")
        os.fsync(source_parent_fd)
        os.fsync(namespace.parent_fd)
        return UX1BExportOutcome(
            published=True,
            durability_confirmed=True,
        )
    except BaseException as exc:
        if not renamed:
            raise
        revoked = False
        if _ux1b_destination_is_retained_root(namespace, retained):
            try:
                os.rename(
                    namespace.leaf_name,
                    source.name,
                    src_dir_fd=namespace.parent_fd,
                    dst_dir_fd=source_parent_fd,
                )
                restored = os.stat(
                    source.name,
                    dir_fd=source_parent_fd,
                    follow_symlinks=False,
                )
                if not _directory_identity_matches(restored, retained):
                    raise RunnerDataError(
                        "formal UX1B export rollback identity differs"
                    )
                os.fsync(namespace.parent_fd)
                os.fsync(source_parent_fd)
                revoked = True
            except BaseException:
                revoked = False
        if revoked:
            raise RunnerDataError(
                "formal UX1B export was revoked after durability failure"
            ) from exc
        if not _ux1b_destination_is_retained_root(namespace, retained):
            raise RunnerDataError(
                "formal UX1B export lost its retained destination identity"
            ) from exc
        return UX1BExportOutcome(
            published=True,
            durability_confirmed=False,
        )


def _ux1b_public_error(exc: BaseException, private_roots: Sequence[Path]) -> dict[str, str]:
    message = str(exc)
    for private_root in sorted(
        (str(path) for path in private_roots), key=len, reverse=True
    ):
        if private_root:
            message = message.replace(private_root, "[REDACTED]")
    message = _CREDENTIAL_ASSIGNMENT_RE.sub(r"\1\2<redacted>", message)
    for pattern, replacement in _CREDENTIAL_PATTERNS:
        message = pattern.sub(replacement, message)
    message = _URI_USERINFO_RE.sub(r"\1<redacted>@", message)
    message = _ABSOLUTE_PATH_RE.sub("[REDACTED_PATH]", message)
    message = message[:MAX_DIAGNOSTIC_MESSAGE_CHARS]
    error_type = re.sub(r"[^A-Za-z0-9_]", "", type(exc).__name__)[
        :MAX_DIAGNOSTIC_TYPE_CHARS
    ] or "Error"
    return {"type": error_type, "message": message}


def _open_ux1b_stale_final_root(claim: Any) -> int | None:
    """Open one claimed candidate's exact private final directory no-follow."""

    descriptor = -1
    try:
        named = os.stat(
            "final",
            dir_fd=claim.root.descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISDIR(named.st_mode)
            or named.st_uid != os.getuid()
            or stat.S_IMODE(named.st_mode) != 0o700
        ):
            return None
        descriptor = os.open(
            "final",
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=claim.root.descriptor,
        )
        os.set_inheritable(descriptor, False)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
            or opened.st_uid != os.getuid()
            or stat.S_IMODE(opened.st_mode) != 0o700
        ):
            os.close(descriptor)
            descriptor = -1
            return None
        return descriptor
    except OSError as exc:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError as close_exc:
                raise RunnerDataError(
                    "stale UX1B final descriptor could not be closed"
                ) from close_exc
        if exc.errno in {
            errno.EACCES,
            errno.ELOOP,
            errno.ENOENT,
            errno.ENOTDIR,
            errno.EPERM,
        }:
            return None
        raise RunnerDataError(
            "stale UX1B final directory could not be authenticated"
        ) from exc


def _is_ux1b_stale_formal_manifest_candidate(
    evidence: Any,
    document: Mapping[str, Any],
) -> bool:
    """Check only immutable formal identity fields; evidence owns classification."""

    mode = document.get("mode")
    phase = document.get("phase")
    run_id = document.get("runId")
    if not isinstance(mode, str) or not isinstance(phase, str):
        return False
    expected = {
        (UX1B_PROFILE, candidate_phase): (
            UX1B_FIXTURE_ENTRYPOINTS[UX1B_PROFILE],
            81,
        )
        for candidate_phase in UX1B_PROFILE_PHASES[UX1B_PROFILE]
    }
    expected.update(
        {
            (UX1B_SELECTION_PROFILE, candidate_phase): (
                UX1B_FIXTURE_ENTRYPOINTS[UX1B_SELECTION_PROFILE],
                36,
            )
            for candidate_phase in UX1B_PROFILE_PHASES[UX1B_SELECTION_PROFILE]
        }
    )
    formal = expected.get((mode, phase))
    if (
        formal
        == (
            UX1B_FIXTURE_ENTRYPOINTS[UX1B_SELECTION_PROFILE],
            36,
        )
        and phase == "postcontrol"
        and document.get("rootExpansionSha256")
        == evidence.ROOT_CAPTURE_EXPANSION_SHA256
    ):
        formal = (formal[0], evidence.ROOT_CAPTURE_EXPANSION_ROWS)
    return bool(
        document.get("schemaVersion") == evidence.EVIDENCE_SCHEMA
        and document.get("status") in {"running", "finalizing"}
        and isinstance(run_id, str)
        and re.fullmatch(r"ux1b-[0-9a-f]{24}", run_id) is not None
        and formal is not None
        and document.get("fixtureEntrypoint") == formal[0]
        and type(document.get("expectedCaptureCount")) is int
        and document.get("expectedCaptureCount") == formal[1]
    )


def _recover_stale_ux1b_formal_runtimes(
    evidence: Any,
    isolation: Any,
    *,
    temp_parent: Path | None = None,
    recovery_dir_fd: int | None = None,
) -> tuple[Mapping[str, Any], ...]:
    """Classify only inactive canonical formal roots into a separate namespace."""

    claims = isolation.claim_stale_owned_run_roots(
        temp_parent or Path(tempfile.gettempdir()),
        prefix="quant-radar-ux1b-",
        max_candidates=isolation.MAX_STALE_OWNED_RUN_CANDIDATES,
    )
    if not claims:
        return ()
    recovery_namespace: UX1BOutputNamespace | None = None
    records: list[Mapping[str, Any]] = []
    try:
        if recovery_dir_fd is None:
            recovery_namespace = _open_ux1b_output_namespace(
                WORKSPACE_ROOT
                / ".claude"
                / "ui_snapshots"
                / "ux1b"
                / "recovery"
                / ".stale-record-anchor"
            )
            active_recovery_fd = recovery_namespace.parent_fd
        else:
            active_recovery_fd = recovery_dir_fd
        for claim in claims:
            try:
                final_fd = _open_ux1b_stale_final_root(claim)
                if final_fd is None:
                    continue
                try:
                    if recovery_namespace is not None:
                        _reauthenticate_ux1b_output_namespace(
                            recovery_namespace
                        )
                    try:
                        source_document = evidence.verify_referenceable_manifest(
                            final_fd,
                            "manifest.json",
                            expected_owner=os.getuid(),
                            require_passed=False,
                        )
                    except evidence.EvidenceContractError:
                        continue
                    if not _is_ux1b_stale_formal_manifest_candidate(
                        evidence,
                        source_document,
                    ):
                        continue
                    try:
                        record = evidence.record_stale_nonterminal(
                            final_fd,
                            "manifest.json",
                            active_recovery_fd,
                            f"stale-{claim.root.leaf_name}.json",
                            expected_owner=os.getuid(),
                        )
                    except evidence.ManifestDurabilityUncertain:
                        raise
                    except evidence.EvidenceContractError as exc:
                        raise RunnerDataError(
                            "stale UX1B source changed or recovery publication failed"
                        ) from exc
                finally:
                    os.close(final_fd)
                records.append(record)
            finally:
                claim.close()
        return tuple(records)
    finally:
        for claim in claims:
            claim.close()
        if recovery_namespace is not None:
            namespace_error = recovery_namespace.close()
            if namespace_error is not None and sys.exc_info()[1] is None:
                raise namespace_error


def _prepare_ux1b_formal_runtime(
    evidence: Any,
    isolation: Any,
    *,
    destination: Path,
    profile: str,
    phase: str,
    fixture_entrypoint: str,
    expected_count: int,
    run_id: str,
    root_expansion_sha256: str | None = None,
) -> UX1BFormalRuntime:
    """Construct every formal runtime resource under one cleanup guard."""

    namespace: UX1BOutputNamespace | None = None
    runtime: Any | None = None
    lease: Any | None = None
    final_root_fd = -1
    browser_root_fd = -1
    try:
        namespace = _open_ux1b_output_namespace(destination)
        _validate_ux1b_output_leaf(namespace)
        _recover_stale_ux1b_formal_runtimes(evidence, isolation)
        runtime = isolation.create_owned_run_root(
            Path(tempfile.gettempdir()), prefix="quant-radar-ux1b-"
        )
        lease = isolation.acquire_owned_run_lease(runtime)
        final_root = runtime.path / "final"
        app_root = runtime.path / "app"
        browser_root = runtime.path / "browser"
        for root in (final_root, app_root, browser_root):
            root.mkdir(mode=0o700)
        final_root_fd = _directory_fd(final_root)
        browser_root_fd = _directory_fd(browser_root)
        base_document: dict[str, Any] = {
            "schemaVersion": evidence.EVIDENCE_SCHEMA,
            "mode": profile,
            "phase": phase,
            "runId": run_id,
            "fixtureEntrypoint": fixture_entrypoint,
            "expectedCaptureCount": expected_count,
        }
        if root_expansion_sha256 is not None:
            if (
                profile != UX1B_SELECTION_PROFILE
                or phase != "postcontrol"
                or expected_count != evidence.ROOT_CAPTURE_EXPANSION_ROWS
                or root_expansion_sha256
                != evidence.ROOT_CAPTURE_EXPANSION_SHA256
            ):
                raise RunnerDataError(
                    "formal root-capture lifecycle identity differs"
                )
            base_document.update(
                {
                    "plannedLogicalRequests": 36,
                    "plannedRootCaptures": evidence.ROOT_CAPTURE_EXPANSION_ROWS,
                    "completedLogicalRequests": 0,
                    "completedRootCaptures": 0,
                    "rootExpansionSha256": root_expansion_sha256,
                }
            )
        lifecycle = evidence.ManifestLifecycle(
            final_root_fd,
            "manifest.json",
            base_document=base_document,
        )
        return UX1BFormalRuntime(
            namespace=namespace,
            runtime=runtime,
            final_root=final_root,
            app_root=app_root,
            browser_root=browser_root,
            final_root_fd=final_root_fd,
            browser_root_fd=browser_root_fd,
            lease=lease,
            lifecycle=lifecycle,
        )
    except BaseException:
        for descriptor in (browser_root_fd, final_root_fd):
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        if runtime is not None:
            try:
                isolation.remove_owned_run_root(runtime)
            except BaseException:
                try:
                    runtime.close()
                except BaseException:
                    pass
        if lease is not None:
            try:
                lease.close()
            except BaseException:
                pass
        if namespace is not None:
            namespace.close()
        raise


def _terminate_ux1b_process_family(
    isolation: Any,
    process: subprocess.Popen[Any],
    attempted: set[int],
) -> None:
    """Mark a family closed only after termination proves successful."""

    isolation.terminate_owned_process_group(process)
    attempted.add(id(process))


def _cleanup_ux1b_process_families(
    isolation: Any,
    processes: Sequence[subprocess.Popen[Any]],
    attempted: set[int],
) -> BaseException | None:
    first_error: BaseException | None = None
    for process in processes:
        identity = id(process)
        if identity in attempted:
            continue
        try:
            # The family registry, not ``poll()``, decides whether cleanup is
            # still required.  An already-reaped leader remains a valid call.
            isolation.terminate_owned_process_group(process)
        except BaseException as exc:
            first_error = first_error or exc
        else:
            attempted.add(identity)
    return first_error


def _retain_ux1b_runtime_after_cleanup_failure(
    owned: Any,
    processes: Sequence[subprocess.Popen[Any]],
    error: BaseException,
) -> None:
    """Keep writable roots and leases live until coordinator process exit."""

    with _UX1B_RETAINED_RUNTIMES_LOCK:
        _UX1B_RETAINED_RUNTIMES[id(owned)] = (
            owned,
            tuple(processes),
            error,
        )


def _quiesce_or_retain_ux1b_runtime(
    isolation: Any,
    owned: Any,
    processes: Sequence[subprocess.Popen[Any]],
    attempted: set[int],
) -> BaseException | None:
    """Prove all families closed or retain every writable runtime resource."""

    cleanup_error = _cleanup_ux1b_process_families(
        isolation,
        processes,
        attempted,
    )
    if cleanup_error is not None:
        _retain_ux1b_runtime_after_cleanup_failure(
            owned,
            processes,
            cleanup_error,
        )
    return cleanup_error


def _release_ux1b_formal_runtime(
    isolation: Any,
    owned: UX1BFormalRuntime,
) -> BaseException | None:
    """Attempt every descriptor/namespace/root cleanup independently."""

    first_error: BaseException | None = None
    for descriptor in (owned.browser_root_fd, owned.final_root_fd):
        try:
            os.close(descriptor)
        except BaseException as exc:
            first_error = first_error or exc
    try:
        namespace_error = owned.namespace.close()
        first_error = first_error or namespace_error
    except BaseException as exc:
        first_error = first_error or exc
    try:
        isolation.remove_owned_run_root(owned.runtime)
    except BaseException as exc:
        first_error = first_error or exc
        try:
            owned.runtime.close()
        except BaseException as close_exc:
            first_error = first_error or close_exc
    try:
        owned.lease.close()
    except BaseException as exc:
        first_error = first_error or exc
    return first_error


def _prepare_ux1b_nonterminal_runtime(isolation: Any) -> UX1BNonterminalRuntime:
    runtime: Any | None = None
    browser_root_fd = -1
    try:
        runtime = isolation.create_owned_run_root(
            Path(tempfile.gettempdir()), prefix="quant-radar-ux1b-nonterminal-"
        )
        app_root = runtime.path / "app"
        browser_root = runtime.path / "browser"
        final_root = runtime.path / "final"
        for root in (app_root, browser_root, final_root):
            root.mkdir(mode=0o700)
        browser_root_fd = _directory_fd(browser_root)
        return UX1BNonterminalRuntime(
            runtime=runtime,
            app_root=app_root,
            browser_root=browser_root,
            final_root=final_root,
            browser_root_fd=browser_root_fd,
        )
    except BaseException:
        if browser_root_fd >= 0:
            try:
                os.close(browser_root_fd)
            except OSError:
                pass
        if runtime is not None:
            try:
                isolation.remove_owned_run_root(runtime)
            except BaseException:
                try:
                    runtime.close()
                except BaseException:
                    pass
        raise


def _release_ux1b_nonterminal_runtime(
    isolation: Any,
    owned: UX1BNonterminalRuntime,
) -> BaseException | None:
    first_error: BaseException | None = None
    try:
        os.close(owned.browser_root_fd)
    except BaseException as exc:
        first_error = first_error or exc
    try:
        isolation.remove_owned_run_root(owned.runtime)
    except BaseException as exc:
        first_error = first_error or exc
        try:
            owned.runtime.close()
        except BaseException as close_exc:
            first_error = first_error or close_exc
    return first_error


def _terminalize_ux1b_failure(
    evidence: Any,
    isolation: Any,
    lifecycle: Any,
    exc: BaseException,
    *,
    cleanup_error: BaseException | None,
    partial_artifact_payloads: Sequence[Mapping[str, Any]],
    private_roots: Sequence[Path],
    final_root_fd: int,
) -> tuple[int, dict[str, Any]]:
    terminal_error = cleanup_error or exc
    if isinstance(exc, KeyboardInterrupt):
        status = "interrupted"
        code = 130
    elif isinstance(
        exc,
        (
            DependencyUnavailable,
            evidence.DependencyUnavailable,
            isolation.DependencyUnavailable,
        ),
    ):
        status = "dependency_unavailable"
        code = 127
    elif isinstance(exc, (RunnerDataError, evidence.InvalidEvidence)):
        status = "invalid_data"
        code = 3
    else:
        status = "failed"
        code = 1
    if lifecycle.state in {"running", "finalizing"}:
        updates: dict[str, Any] = {
            "error": _ux1b_public_error(terminal_error, private_roots),
        }
        if partial_artifact_payloads:
            updates["partialArtifacts"] = copy.deepcopy(
                list(partial_artifact_payloads)
            )
        try:
            manifest = lifecycle.mark_terminal(status, updates)
        except evidence.ManifestDurabilityUncertain:
            if lifecycle.state != status:
                raise
            manifest = _read_ux1b_terminal_manifest(final_root_fd)
    else:
        manifest = {
            "status": status,
            "error": _ux1b_public_error(terminal_error, private_roots),
        }
    return code, manifest


def _run_ux1b_recovery(
    args: argparse.Namespace,
    *,
    cases: Sequence[CaptureCase],
    viewports: Sequence[tuple[str, int, int]],
) -> tuple[int, dict[str, Any]]:
    """Run a formal UX1B matrix without a coordinator-side browser launch.

    The closure intentionally names every security boundary used below:
    ``build_source_mirror``, ``calibrate_darwin_profiles``,
    ``spawn_calibrated_child``, ``authenticate_counter_bundle``,
    ``authenticate_raw_render_sidecar``, ``publish_finalized_capture``,
    ``verify_capture_artifacts``, ``validate_live_capture_profile``,
    ``ManifestLifecycle``, and ``finalize_terminal_manifest``.
    """

    evidence = _evidence_api()
    isolation = _isolation_api()
    fixtures = _fixtures_api()
    profile = str(args.profile)
    phase = str(args.phase)
    capture_stack_selection = str(args.capture_stack)
    capture_stack_path = _ux1b_capture_stack_contract_path(
        capture_stack_selection
    )
    fixture_entrypoint = UX1B_FIXTURE_ENTRYPOINTS[profile]
    streamlit_base_path = _ux1b_streamlit_base_path(fixture_entrypoint)
    rows = ux1b_profile_rows(profile)
    logical_request_count = 81 if profile == UX1B_PROFILE else 36
    is_root_capture = capture_stack_selection in {"seq12", "seq13"}
    if is_root_capture and (
        profile != UX1B_SELECTION_PROFILE or phase != "postcontrol"
    ):
        raise RunnerDataError(
            "root capture stack requires focused postcontrol"
        )
    root_expansion = (
        evidence.root_capture_expansion_rows()
        if is_root_capture
        else ()
    )
    expected_count = (
        evidence.ROOT_CAPTURE_EXPANSION_ROWS
        if is_root_capture
        else logical_request_count
    )
    if (
        len(rows) != logical_request_count
        or len(cases) * len(viewports) != logical_request_count
        or (
            is_root_capture
            and (
                len(root_expansion) != expected_count
                or len(
                    {
                        row["logicalCaptureId"]
                        for row in root_expansion
                    }
                )
                != logical_request_count
            )
        )
    ):
        raise RunnerDataError("formal UX1B matrix differs from its frozen profile")

    run_id = f"ux1b-{secrets.token_hex(12)}"
    owned_runtime = _prepare_ux1b_formal_runtime(
        evidence,
        isolation,
        destination=args.out_dir
        or _default_run_dir(profile=profile, phase=phase),
        profile=profile,
        phase=phase,
        fixture_entrypoint=fixture_entrypoint,
        expected_count=expected_count,
        run_id=run_id,
        root_expansion_sha256=(
            evidence.ROOT_CAPTURE_EXPANSION_SHA256
            if is_root_capture
            else None
        ),
    )
    output_dir = owned_runtime.namespace.path
    runtime = owned_runtime.runtime
    final_root = owned_runtime.final_root
    app_root = owned_runtime.app_root
    browser_root = owned_runtime.browser_root
    final_root_fd = owned_runtime.final_root_fd
    browser_root_fd = owned_runtime.browser_root_fd
    lifecycle = owned_runtime.lifecycle
    app_process: subprocess.Popen[Any] | None = None
    browser_process: subprocess.Popen[Any] | None = None
    owned_processes: list[subprocess.Popen[Any]] = []
    cleanup_attempted: set[int] = set()
    verified_captures: list[Any] = []
    partial_artifact_payloads: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {}
    code = 1
    private_roots = (runtime.path, app_root, browser_root, final_root)
    output_published = False

    try:
        lifecycle.start()
        _reauthenticate_ux1b_output_namespace(owned_runtime.namespace)
        if capture_stack_selection == "legacy":
            stack_contract, _control_catalog, stack_contract_sha256 = (
                _authenticate_ux1b_capture_stack_contract(
                    workspace_fd=owned_runtime.namespace.workspace_fd
                )
            )
        else:
            stack_contract, _control_catalog, stack_contract_sha256 = (
                _authenticate_ux1b_capture_stack_contract(
                    workspace_fd=owned_runtime.namespace.workspace_fd,
                    selection=capture_stack_selection,
                )
            )
        capture_stack_digest_value = stack_contract["captureStackDigest"]

        mirror = isolation.build_source_mirror(
            workspace_root_fd=owned_runtime.namespace.workspace_fd,
            run_root=runtime.path / "mirror",
            policy=isolation.SourceMirrorPolicy(
                include=_expanded_ux1b_source_mirror_policy(),
                # Includes are materialized to exact accepted files above;
                # these component rules retain the accepted deny roots for
                # the mirror primitive's non-glob grammar.
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
            mirror, expected_digest=mirror.digest
        )
        if source_start.get("digest") != mirror.digest:
            raise RunnerDataError("authenticated source mirror digest differs")

        browser_executable, _browser_sha256 = (
            isolation._playwright_chromium_identity()
        )
        browser_cache = isolation._playwright_browser_cache_root(
            browser_executable
        )
        app_port = choose_ephemeral_port()
        denied_port = choose_ephemeral_port()
        while denied_port in {app_port, 8000} or app_port == 8000:
            app_port = choose_ephemeral_port()
            denied_port = choose_ephemeral_port()
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
            python_runtime_roots=(Path(sys.prefix).resolve(),),
        )
        browser_environment = isolation.build_child_environment(
            role="browser",
            source_root=mirror.source_root,
            writable_root=browser_root,
            inherited=os.environ,
            python_runtime_roots=(Path(sys.prefix).resolve(),),
        )
        (browser_root / "stdio").mkdir(mode=0o700)
        fixture_root = app_root / "fixture-root"
        fixture_root.mkdir(mode=0o700)
        for relative in (
            "candidates",
            "ai-chat",
            "analytics",
            "tmp",
        ):
            (fixture_root / relative).mkdir(mode=0o700)
        run_token = secrets.token_urlsafe(32)
        _write_private_file(
            app_root / fixtures.OWNERSHIP_MARKER,
            (run_token + "\n").encode("utf-8"),
        )
        fixture_contract = fixtures.build_owned_run_contract(
            run_token=run_token,
            profile=profile,
            phase=phase,
            streamlit_port=app_port,
            deny_proxy_port=denied_port,
        )
        _write_private_file(
            Path(app_environment["HOME"])
            / fixtures.UX1B_RUN_CONTRACT_FILENAME,
            _canonical_ndjson(fixture_contract).rstrip(b"\n"),
        )

        calibration = isolation.calibrate_darwin_profiles(
            contract,
            profiles=profiles,
        )
        calibration_attestation = evidence.mint_calibration_attestation(
            calibration
        )
        app_origin = f"http://127.0.0.1:{app_port}"
        session_id = run_id
        app_profile_name = (
            "full-pages" if profile == UX1B_PROFILE else "selection-controls"
        )
        app_process_id = f"app/{app_profile_name}"
        browser_proofs: dict[str, Any] = {}
        staged: dict[str, tuple[str, Any, str]] = {}
        staged_semantic_by_logical: dict[str, bytes] = {}

        with ExitStack() as app_stack:
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
                fixture_entrypoint,
                "--server.address",
                "127.0.0.1",
                "--server.port",
                str(app_port),
                *(
                    ("--server.baseUrlPath", streamlit_base_path)
                    if streamlit_base_path
                    else ()
                ),
                "--server.headless",
                "true",
                "--browser.gatherUsageStats",
                "false",
            )
            app_launch = isolation.authorize_calibrated_launch(
                session_id=session_id,
                process_id=app_process_id,
                contract=contract,
                profiles=profiles,
                calibration=calibration,
                role="app",
                command=app_command,
                cwd=mirror.source_root,
                environment=app_environment,
                stdio=app_stdio,
            )
            app_process = isolation.spawn_calibrated_child(
                authorization=app_launch,
                session_id=session_id,
                process_id=app_process_id,
                contract=contract,
                profiles=profiles,
                calibration=calibration,
                role="app",
                command=app_command,
                cwd=mirror.source_root,
                environment=app_environment,
                stdio=app_stdio,
            )
            owned_processes.append(app_process)
            wait_for_health(
                app_port,
                app_process,
                timeout=45.0,
                base_path=streamlit_base_path,
            )

            for index, row in enumerate(rows):
                capture_id = f'{row["case"]}/{row["viewport"]["name"]}'
                if is_root_capture:
                    logical_root_rows = [
                        root_row
                        for root_row in root_expansion
                        if root_row["logicalCaptureId"] == capture_id
                    ]
                    root_outputs: list[dict[str, Any]] = []
                    allowed_path_values: list[str] = []
                    for root_row in logical_root_rows:
                        capture_stage = (
                            browser_root
                            / "staging"
                            / str(row["case"])
                            / str(row["viewport"]["name"])
                            / f'root-{root_row["rootOrdinal"]:02d}'
                        )
                        png_path = (
                            capture_stage / "capture.png"
                        ).relative_to(browser_root).as_posix()
                        render_path = (
                            capture_stage / "render.json"
                        ).relative_to(browser_root).as_posix()
                        allowed_path_values.extend((png_path, render_path))
                        root_outputs.append(
                            {
                                "rootCaptureId": root_row[
                                    "rootCaptureId"
                                ],
                                "rootOrdinal": root_row["rootOrdinal"],
                                "rootSelector": root_row["rootSelector"],
                                "staging": {
                                    "png": png_path,
                                    "renderSidecar": render_path,
                                },
                            }
                        )
                    allowed_paths = frozenset(allowed_path_values)
                    request = {
                        "schemaVersion": evidence.WORKER_REQUEST_V2_SCHEMA,
                        "requestId": capture_id,
                        "fixtureEntrypoint": fixture_entrypoint,
                        "case": row["case"],
                        "route": row["route"],
                        "viewport": dict(row["viewport"]),
                        "appOrigin": app_origin,
                        "rootOutputs": root_outputs,
                    }
                else:
                    capture_stage = (
                        browser_root
                        / "staging"
                        / str(row["case"])
                        / str(row["viewport"]["name"])
                    )
                    png_path = (
                        capture_stage / "capture.png"
                    ).relative_to(browser_root).as_posix()
                    render_path = (
                        capture_stage / "render.json"
                    ).relative_to(browser_root).as_posix()
                    allowed_paths = frozenset((png_path, render_path))
                    request = {
                        "schemaVersion": evidence.WORKER_REQUEST_SCHEMA,
                        "requestId": capture_id,
                        "fixtureEntrypoint": fixture_entrypoint,
                        "case": row["case"],
                        "route": row["route"],
                        "viewport": dict(row["viewport"]),
                        "appOrigin": app_origin,
                        "staging": {
                            "png": png_path,
                            "renderSidecar": render_path,
                        },
                    }
                request_raw = _canonical_ndjson(request)
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
                    timeout_ms=60_000,
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
                    os.pwrite(browser_stdio.stdin.fileno(), request_raw, 0)
                    os.ftruncate(browser_stdio.stdin.fileno(), len(request_raw))
                    os.fsync(browser_stdio.stdin.fileno())
                    browser_launch = isolation.authorize_calibrated_launch(
                        session_id=session_id,
                        process_id=capture_id,
                        contract=contract,
                        profiles=profiles,
                        calibration=calibration,
                        role="browser",
                        command=browser_command,
                        cwd=mirror.source_root,
                        environment=browser_environment,
                        stdio=browser_stdio,
                    )
                    browser_process = isolation.spawn_calibrated_child(
                        authorization=browser_launch,
                        session_id=session_id,
                        process_id=capture_id,
                        contract=contract,
                        profiles=profiles,
                        calibration=calibration,
                        role="browser",
                        command=browser_command,
                        cwd=mirror.source_root,
                        environment=browser_environment,
                        stdio=browser_stdio,
                    )
                    owned_processes.append(browser_process)
                    try:
                        browser_proof = (
                            isolation.wait_for_clean_owned_process_group_exit(
                                browser_process,
                                timeout=90.0,
                            )
                        )
                    except BaseException as exit_error:
                        try:
                            _terminate_ux1b_process_family(
                                isolation,
                                browser_process,
                                cleanup_attempted,
                            )
                        except BaseException as cleanup_error:
                            exit_error.add_note(
                                "browser cleanup also failed: "
                                f"{type(cleanup_error).__name__}: {cleanup_error}"
                            )
                        _raise_worker_exit(
                            evidence,
                            browser_stdio,
                            capture_id=capture_id,
                            allowed_paths=allowed_paths,
                            cause=exit_error,
                        )
                    _terminate_ux1b_process_family(
                        isolation,
                        browser_process,
                        cleanup_attempted,
                    )
                    browser_process = None
                    response_raw = _read_owned_stdio(
                        browser_stdio.stdout,
                        maximum=evidence.MAX_WORKER_RESPONSE_BYTES,
                    )
                    response = evidence.decode_worker_response(
                        response_raw,
                        expected_request_id=capture_id,
                        allowed_artifact_paths=allowed_paths,
                    )
                    if response["status"] != "staged":
                        raise RunnerDataError(
                            f"browser worker failed for {capture_id}: "
                            f'{response["error"]["type"]}'
                        )
                browser_proofs[capture_id] = browser_proof
                if is_root_capture:
                    for artifact in response["rootArtifacts"]:
                        authenticated_sidecar = (
                            evidence.authenticate_raw_render_sidecar(
                                browser_root_fd,
                                artifact["renderSidecar"],
                                expected_owner=os.getuid(),
                                identity_row=row,
                            )
                        )
                        semantic_raw = evidence._canonical_json_bytes(
                            authenticated_sidecar["document"][
                                "caseSemanticProjection"
                            ]
                        )
                        prior_semantic = staged_semantic_by_logical.setdefault(
                            capture_id,
                            semantic_raw,
                        )
                        if prior_semantic != semantic_raw:
                            raise RunnerDataError(
                                "sibling case semantic projections differ"
                            )
                        if artifact["rootCaptureId"] in staged:
                            raise RunnerDataError(
                                "browser worker reused a root capture ID"
                            )
                        staged[artifact["rootCaptureId"]] = (
                            artifact["png"],
                            authenticated_sidecar,
                            capture_id,
                        )
                else:
                    authenticated_sidecar = (
                        evidence.authenticate_raw_render_sidecar(
                            browser_root_fd,
                            render_path,
                            expected_owner=os.getuid(),
                            identity_row=row,
                        )
                    )
                    staged[capture_id] = (
                        png_path,
                        authenticated_sidecar,
                        capture_id,
                    )

            if (
                len(browser_proofs) != logical_request_count
                or len(staged) != expected_count
                or (
                    is_root_capture
                    and len(staged_semantic_by_logical)
                    != logical_request_count
                )
            ):
                raise RunnerDataError(
                    "formal logical/root staging cardinality differs"
                )
            os.killpg(app_process.pid, signal.SIGINT)
            app_proof = isolation.wait_for_clean_owned_process_group_exit(
                app_process,
                timeout=20.0,
            )
            _terminate_ux1b_process_family(
                isolation,
                app_process,
                cleanup_attempted,
            )
            app_process = None

        expected_counters = _ux1b_counter_expectations(
            rows,
            fixture_entrypoint=fixture_entrypoint,
            app_root=app_root,
        )
        app_root_fd = _directory_fd(app_root)
        try:
            authenticated_counters = evidence.authenticate_counter_bundle(
                app_root_fd,
                "fixture-calls.json",
                expected_owner=os.getuid(),
                expected_captures=expected_counters,
            )
        finally:
            os.close(app_root_fd)

        capture_records: list[dict[str, Any]] = []
        for capture_id in sorted(staged):
            capture_components = capture_id.split("/")
            if len(capture_components) not in {2, 3}:
                raise RunnerDataError("staged capture identity is malformed")
            if is_root_capture and len(capture_components) != 3:
                raise RunnerDataError("root capture identity is incomplete")
            if not is_root_capture and len(capture_components) != 2:
                raise RunnerDataError("legacy capture identity changed")
            capture_root = final_root / "captures"
            for component in capture_components:
                capture_root /= component
            capture_root.mkdir(parents=True, mode=0o700)
            capture_root_fd = _directory_fd(capture_root)
            try:
                staged_png, raw_sidecar, logical_capture_id = staged[
                    capture_id
                ]
                record = evidence.publish_finalized_capture(
                    browser_root_fd,
                    capture_root_fd,
                    expected_owner=os.getuid(),
                    staged_png_path=staged_png,
                    authenticated_raw_sidecar=raw_sidecar,
                    authenticated_counters=authenticated_counters,
                    capture_id=logical_capture_id,
                    output_png_name="capture.png",
                    output_sidecar_name="render.json",
                )
                verified = evidence.verify_capture_artifacts(
                    capture_root_fd,
                    record,
                    expected_owner=os.getuid(),
                    run_root_fd=final_root_fd,
                )
            finally:
                os.close(capture_root_fd)
            verified_captures.append(verified)
            partial_artifact_payloads.append(copy.deepcopy(dict(verified)))
            capture_records.append(
                {"id": capture_id, "status": "passed", "artifacts": verified}
            )

        source_end = isolation.authenticate_source_mirror(
            mirror, expected_digest=mirror.digest
        )
        if source_end.get("digest") != source_start.get("digest"):
            raise RunnerDataError("source mirror changed during formal capture")
        _reauthenticate_ux1b_output_namespace(owned_runtime.namespace)
        if capture_stack_selection == "legacy":
            closing_stack, _closing_catalog, closing_contract_sha256 = (
                _authenticate_ux1b_capture_stack_contract(
                    workspace_fd=owned_runtime.namespace.workspace_fd
                )
            )
        else:
            closing_stack, _closing_catalog, closing_contract_sha256 = (
                _authenticate_ux1b_capture_stack_contract(
                    workspace_fd=owned_runtime.namespace.workspace_fd,
                    selection=capture_stack_selection,
                )
            )
        if (
            closing_contract_sha256 != stack_contract_sha256
            or closing_stack["captureStackDigest"]
            != capture_stack_digest_value
        ):
            raise RunnerDataError("capture stack changed during formal capture")
        finalizing_updates: dict[str, Any] = {
            "captureStackDigest": capture_stack_digest_value,
            "captureStackContract": {
                "path": capture_stack_path.relative_to(
                    WORKSPACE_ROOT
                ).as_posix(),
                "sha256": stack_contract_sha256,
            },
            "sourceDigestStart": mirror.digest,
            "sourceDigestEnd": mirror.digest,
            "childrenQuiescent": True,
            "capturedCount": len(capture_records),
        }
        if is_root_capture:
            finalizing_updates.update(
                {
                    "completedLogicalRequests": logical_request_count,
                    "completedRootCaptures": len(capture_records),
                    "rootExpansionSha256": (
                        evidence.ROOT_CAPTURE_EXPANSION_SHA256
                    ),
                }
            )
        lifecycle.mark_finalizing(finalizing_updates)
        comparator_report = evidence.validate_live_capture_profile(
            verified_captures,
            fixture_entrypoint=fixture_entrypoint,
            capture_stack_digest=capture_stack_digest_value,
        )
        comparator_attestation = evidence.mint_comparator_attestation(
            comparator_report
        )
        provider_counters, mutator_counters = _sum_ux1b_counters(
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
            expected_fixture_entrypoint=fixture_entrypoint,
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
        finalizing_document = _read_ux1b_manifest_document(
            final_root_fd,
            require_terminal=False,
        )
        if finalizing_document.get("status") != "finalizing":
            raise RunnerDataError("formal UX1B lifecycle is not finalizing")
        expected_passed = evidence.materialize_authorized_terminal_manifest(
            lifecycle,
            grant=grant,
        )

        publication = _export_ux1b_evidence(
            final_root,
            owned_runtime.namespace,
            source_parent_fd=runtime.descriptor,
            final_root_fd=final_root_fd,
        )
        output_published = publication.published
        if not publication.durability_confirmed:
            raise RunnerDataError(
                "formal UX1B finalizing publication durability is uncertain"
            )
        passed_durability_confirmed = True
        try:
            finalized_manifest = evidence.finalize_terminal_manifest(
                lifecycle,
                grant=grant,
            )
        except evidence.ManifestDurabilityUncertain as durability_error:
            if not _ux1b_destination_is_retained_root(
                owned_runtime.namespace,
                os.fstat(final_root_fd),
            ):
                _make_ux1b_manifest_unreferenceable(final_root_fd)
                raise RunnerDataError(
                    "durability-uncertain passed output lost its destination identity"
                ) from durability_error
            try:
                manifest = _authenticate_ux1b_passed_bundle(
                    evidence,
                    final_root_fd,
                    expected_passed,
                )
            except BaseException as authentication_error:
                _make_ux1b_manifest_unreferenceable(final_root_fd)
                raise RunnerDataError(
                    "durability-uncertain passed output is not fully referenceable"
                ) from authentication_error
            passed_durability_confirmed = _retry_ux1b_directory_fsync(
                final_root_fd,
            )
        else:
            if finalized_manifest != expected_passed or not (
                _ux1b_destination_is_retained_root(
                    owned_runtime.namespace,
                    os.fstat(final_root_fd),
                )
            ):
                _make_ux1b_manifest_unreferenceable(final_root_fd)
                raise RunnerDataError(
                    "published UX1B passed output differs from its final closure"
                )
            try:
                manifest = _authenticate_ux1b_passed_bundle(
                    evidence,
                    final_root_fd,
                    expected_passed,
                )
            except BaseException as authentication_error:
                _make_ux1b_manifest_unreferenceable(final_root_fd)
                raise RunnerDataError(
                    "published UX1B passed artifact bundle is not referenceable"
                ) from authentication_error
        code = 0 if passed_durability_confirmed else 1
    except BaseException as exc:
        cleanup_error = _cleanup_ux1b_process_families(
            isolation,
            owned_processes,
            cleanup_attempted,
        )
        code, manifest = _terminalize_ux1b_failure(
            evidence,
            isolation,
            lifecycle,
            exc,
            cleanup_error=cleanup_error,
            partial_artifact_payloads=partial_artifact_payloads,
            private_roots=private_roots,
            final_root_fd=final_root_fd,
        )
    finally:
        final_cleanup_error = _quiesce_or_retain_ux1b_runtime(
            isolation,
            owned_runtime,
            owned_processes,
            cleanup_attempted,
        )
        if final_cleanup_error is not None:
            code = 1
        else:
            if lifecycle.state in {
                "failed",
                "invalid_data",
                "dependency_unavailable",
                "interrupted",
            }:
                if not output_published:
                    try:
                        publication = _export_ux1b_evidence(
                            final_root,
                            owned_runtime.namespace,
                            source_parent_fd=runtime.descriptor,
                            final_root_fd=final_root_fd,
                        )
                        output_published = publication.published
                    except BaseException as export_error:
                        code = 1
                        manifest = {
                            "status": "failed",
                            "error": _ux1b_public_error(
                                export_error,
                                private_roots,
                            ),
                        }
                if output_published and _ux1b_destination_is_retained_root(
                    owned_runtime.namespace,
                    os.fstat(final_root_fd),
                ):
                    try:
                        manifest = _read_ux1b_terminal_manifest(final_root_fd)
                    except BaseException as read_error:
                        code = 1
                        manifest = {
                            "status": "failed",
                            "error": _ux1b_public_error(read_error, private_roots),
                        }
            release_error = _release_ux1b_formal_runtime(
                isolation,
                owned_runtime,
            )
            if release_error is not None:
                # A passed manifest is immutable and remains the only honest
                # returned document; the non-zero exit is the out-of-band
                # cleanup diagnostic and cannot rewrite the published bytes.
                code = 1
    return code, manifest


def _authenticate_ux1b_smoke_png(
    evidence: Any,
    browser_root_fd: int,
    png_path: str,
    *,
    identity_row: Mapping[str, Any],
    require_viewport_exact: bool = False,
) -> dict[str, Any]:
    contract = evidence.freeze_artifact_contract(
        browser_root_fd,
        png_path,
        expected_owner=os.getuid(),
        max_bytes=evidence.MAX_PNG_BYTES,
    )
    with evidence.open_authenticated_artifact(
        browser_root_fd,
        contract,
    ) as artifact:
        opened = os.fstat(artifact.descriptor)
        raw = os.pread(artifact.descriptor, opened.st_size, 0)
        after = os.fstat(artifact.descriptor)
    if (
        len(raw) != opened.st_size
        or (opened.st_dev, opened.st_ino, opened.st_uid, opened.st_size, opened.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_uid, after.st_size, after.st_mtime_ns)
    ):
        raise RunnerDataError("UX1B smoke PNG changed while descriptor-open")
    png_dimensions = getattr(evidence, "_png_dimensions", None)
    if not callable(png_dimensions):
        raise RunnerDataError("UX1B evidence PNG decoder is unavailable")
    width, height = png_dimensions(raw)
    viewport = identity_row.get("viewport")
    if (
        not isinstance(viewport, Mapping)
        or type(viewport.get("width")) is not int
        or type(viewport.get("height")) is not int
        or width != viewport["width"]
        or (
            height != viewport["height"]
            if require_viewport_exact
            else height < viewport["height"]
        )
    ):
        raise RunnerDataError("UX1B smoke PNG dimensions differ")
    return {
        "captureId": (
            f'{identity_row["case"]}/{viewport["name"]}'
        ),
        "path": png_path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size": len(raw),
        "width": width,
        "height": height,
    }


def _finish_ux1b_nonterminal_cleanup(
    active_error: BaseException | None,
    cleanup_error: BaseException | None,
    release_error: BaseException | None,
) -> None:
    """Preserve a capture failure while attaching secondary cleanup failures."""

    if active_error is not None:
        for label_name, secondary in (
            ("process-family cleanup", cleanup_error),
            ("nonterminal runtime release", release_error),
        ):
            if secondary is not None:
                active_error.add_note(
                    f"{label_name} also failed: "
                    f"{type(secondary).__name__}: {secondary}"
                )
        return
    if cleanup_error is not None:
        raise cleanup_error
    if release_error is not None:
        raise release_error


def _run_ux1b_nonterminal_capture(
    capture_rows: Sequence[Mapping[str, Any]],
    *,
    label: str,
    expected_group_counts: Mapping[str, int],
    authenticate_pngs: bool,
    authenticate_counters: bool,
    workspace_fd: int,
    root_capture: bool = False,
) -> _UX1BNonterminalResult:
    """Run a disposable real capture without lifecycle or final publication."""

    evidence = _evidence_api()
    isolation = _isolation_api()
    fixtures = _fixtures_api()
    rows = tuple(dict(row) for row in capture_rows)
    if not rows or label not in {"discovery", "smoke"}:
        raise RunnerDataError("UX1B nonterminal capture projection is invalid")
    if root_capture and (
        label != "smoke"
        or any(
            row.get("fixtureEntrypoint")
            != UX1B_FIXTURE_ENTRYPOINTS[UX1B_SELECTION_PROFILE]
            for row in rows
        )
    ):
        raise RunnerDataError(
            "root smoke requires the focused selection profile"
        )
    root_expansion = (
        evidence.root_capture_expansion_rows()
        if root_capture
        else ()
    )
    expected_artifact_captures = (
        len(root_expansion) if root_capture else len(rows)
    )
    base_digest = evidence.capture_stack_digest(
        UX1B_CAPTURE_STACK_MEMBERS,
        root_fd=workspace_fd,
    )
    owned_runtime = _prepare_ux1b_nonterminal_runtime(isolation)
    runtime = owned_runtime.runtime
    app_root = owned_runtime.app_root
    browser_root = owned_runtime.browser_root
    final_root = owned_runtime.final_root
    browser_root_fd = owned_runtime.browser_root_fd
    app_process: subprocess.Popen[Any] | None = None
    browser_process: subprocess.Popen[Any] | None = None
    owned_processes: list[subprocess.Popen[Any]] = []
    cleanup_attempted: set[int] = set()
    sidecars: list[Any] = []
    pngs: list[Mapping[str, Any]] = []
    counter_capture_ids: list[str] = []
    quiescent_process_count = 0
    try:
        mirror = isolation.build_source_mirror(
            workspace_root_fd=workspace_fd,
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
        browser_executable, _browser_sha256 = (
            isolation._playwright_chromium_identity()
        )
        browser_cache = isolation._playwright_browser_cache_root(
            browser_executable
        )
        app_port = choose_ephemeral_port()
        denied_port = choose_ephemeral_port()
        while app_port == 8000 or denied_port in {app_port, 8000}:
            app_port = choose_ephemeral_port()
            denied_port = choose_ephemeral_port()
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
            python_runtime_roots=(Path(sys.prefix).resolve(),),
        )
        browser_environment = isolation.build_child_environment(
            role="browser",
            source_root=mirror.source_root,
            writable_root=browser_root,
            inherited=os.environ,
            python_runtime_roots=(Path(sys.prefix).resolve(),),
        )
        (browser_root / "stdio").mkdir(mode=0o700)
        fixture_root = app_root / "fixture-root"
        fixture_root.mkdir(mode=0o700)
        for relative in ("candidates", "ai-chat", "analytics", "tmp"):
            (fixture_root / relative).mkdir(mode=0o700)
        run_token = secrets.token_urlsafe(32)
        _write_private_file(
            app_root / fixtures.OWNERSHIP_MARKER,
            (run_token + "\n").encode("utf-8"),
        )
        calibration = isolation.calibrate_darwin_profiles(
            contract,
            profiles=profiles,
        )
        session_id = f"ux1b-{label}-{secrets.token_hex(12)}"
        app_origin = f"http://127.0.0.1:{app_port}"
        contract_path = (
            Path(app_environment["HOME"])
            / fixtures.UX1B_RUN_CONTRACT_FILENAME
        )
        calls_path = app_root / "fixture-calls.json"
        capture_index = 0

        for profile, fixture_entrypoint, app_name in (
            (UX1B_PROFILE, UX1B_FIXTURE_ENTRYPOINTS[UX1B_PROFILE], "full-pages"),
            (
                UX1B_SELECTION_PROFILE,
                UX1B_FIXTURE_ENTRYPOINTS[UX1B_SELECTION_PROFILE],
                "selection-controls",
            ),
        ):
            streamlit_base_path = _ux1b_streamlit_base_path(fixture_entrypoint)
            group_rows = tuple(
                row
                for row in rows
                if row["fixtureEntrypoint"] == fixture_entrypoint
            )
            expected_group_count = expected_group_counts.get(profile)
            if len(group_rows) != expected_group_count:
                raise RunnerDataError("nonterminal fixture group count differs")
            if expected_group_count == 0:
                continue
            for path in (contract_path, calls_path):
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
            fixture_contract = fixtures.build_owned_run_contract(
                run_token=run_token,
                profile=profile,
                phase=(
                    "postcontrol"
                    if root_capture
                    and profile == UX1B_SELECTION_PROFILE
                    else "precontrol"
                ),
                streamlit_port=app_port,
                deny_proxy_port=denied_port,
            )
            _write_private_file(
                contract_path,
                _canonical_ndjson(fixture_contract).rstrip(b"\n"),
            )
            app_process_id = f"app/{label}-{app_name}"
            with ExitStack() as app_stack:
                app_stdio = app_stack.enter_context(
                    isolation.owned_child_stdio(
                        app_root / f"{label}-{app_name}-stdio",
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
                    fixture_entrypoint,
                    "--server.address",
                    "127.0.0.1",
                    "--server.port",
                    str(app_port),
                    *(
                        ("--server.baseUrlPath", streamlit_base_path)
                        if streamlit_base_path
                        else ()
                    ),
                    "--server.headless",
                    "true",
                    "--browser.gatherUsageStats",
                    "false",
                )
                app_launch = isolation.authorize_calibrated_launch(
                    session_id=session_id,
                    process_id=app_process_id,
                    contract=contract,
                    profiles=profiles,
                    calibration=calibration,
                    role="app",
                    command=app_command,
                    cwd=mirror.source_root,
                    environment=app_environment,
                    stdio=app_stdio,
                )
                app_process = isolation.spawn_calibrated_child(
                    authorization=app_launch,
                    session_id=session_id,
                    process_id=app_process_id,
                    contract=contract,
                    profiles=profiles,
                    calibration=calibration,
                    role="app",
                    command=app_command,
                    cwd=mirror.source_root,
                    environment=app_environment,
                    stdio=app_stdio,
                )
                owned_processes.append(app_process)
                wait_for_health(
                    app_port,
                    app_process,
                    timeout=45.0,
                    base_path=streamlit_base_path,
                )

                for row in group_rows:
                    capture_id = f'{row["case"]}/{row["viewport"]["name"]}'
                    if root_capture:
                        root_outputs: list[dict[str, Any]] = []
                        allowed_path_values: list[str] = []
                        for root_row in root_expansion:
                            if (
                                root_row["logicalCaptureId"]
                                != capture_id
                            ):
                                continue
                            capture_stage = (
                                browser_root
                                / label
                                / app_name
                                / str(row["case"])
                                / str(row["viewport"]["name"])
                                / (
                                    "root-"
                                    f'{root_row["rootOrdinal"]:02d}'
                                )
                            )
                            png_path = (
                                capture_stage / "capture.png"
                            ).relative_to(browser_root).as_posix()
                            render_path = (
                                capture_stage / "render.json"
                            ).relative_to(browser_root).as_posix()
                            allowed_path_values.extend(
                                (png_path, render_path)
                            )
                            root_outputs.append(
                                {
                                    "rootCaptureId": root_row[
                                        "rootCaptureId"
                                    ],
                                    "rootOrdinal": root_row[
                                        "rootOrdinal"
                                    ],
                                    "rootSelector": root_row[
                                        "rootSelector"
                                    ],
                                    "staging": {
                                        "png": png_path,
                                        "renderSidecar": render_path,
                                    },
                                }
                            )
                        allowed_paths = frozenset(allowed_path_values)
                        request = {
                            "schemaVersion": (
                                evidence.WORKER_REQUEST_V2_SCHEMA
                            ),
                            "requestId": capture_id,
                            "fixtureEntrypoint": fixture_entrypoint,
                            "case": row["case"],
                            "route": row["route"],
                            "viewport": dict(row["viewport"]),
                            "appOrigin": app_origin,
                            "rootOutputs": root_outputs,
                        }
                    else:
                        capture_stage = (
                            browser_root
                            / label
                            / app_name
                            / str(row["case"])
                            / str(row["viewport"]["name"])
                        )
                        png_path = (
                            capture_stage / "capture.png"
                        ).relative_to(browser_root).as_posix()
                        render_path = (
                            capture_stage / "render.json"
                        ).relative_to(browser_root).as_posix()
                        allowed_paths = frozenset((png_path, render_path))
                        request = {
                            "schemaVersion": evidence.WORKER_REQUEST_SCHEMA,
                            "requestId": capture_id,
                            "fixtureEntrypoint": fixture_entrypoint,
                            "case": row["case"],
                            "route": row["route"],
                            "viewport": dict(row["viewport"]),
                            "appOrigin": app_origin,
                            "staging": {
                                "png": png_path,
                                "renderSidecar": render_path,
                            },
                        }
                    request_raw = _canonical_ndjson(request)
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
                        timeout_ms=60_000,
                    )
                    browser_command = (
                        str(isolation.SANDBOX_EXEC),
                        "-p",
                        profiles.browser,
                        *worker_tail,
                    )
                    with isolation.owned_child_stdio(
                            browser_root
                            / "stdio"
                            / f"{label}-{capture_index:03d}",
                        role="browser",
                    ) as browser_stdio:
                        capture_index += 1
                        os.pwrite(browser_stdio.stdin.fileno(), request_raw, 0)
                        os.ftruncate(
                            browser_stdio.stdin.fileno(), len(request_raw)
                        )
                        os.fsync(browser_stdio.stdin.fileno())
                        browser_launch = isolation.authorize_calibrated_launch(
                            session_id=session_id,
                            process_id=capture_id,
                            contract=contract,
                            profiles=profiles,
                            calibration=calibration,
                            role="browser",
                            command=browser_command,
                            cwd=mirror.source_root,
                            environment=browser_environment,
                            stdio=browser_stdio,
                        )
                        browser_process = isolation.spawn_calibrated_child(
                            authorization=browser_launch,
                            session_id=session_id,
                            process_id=capture_id,
                            contract=contract,
                            profiles=profiles,
                            calibration=calibration,
                            role="browser",
                            command=browser_command,
                            cwd=mirror.source_root,
                            environment=browser_environment,
                            stdio=browser_stdio,
                        )
                        owned_processes.append(browser_process)
                        try:
                            proof = isolation.wait_for_clean_owned_process_group_exit(
                                browser_process,
                                timeout=90.0,
                            )
                        except BaseException as exit_error:
                            try:
                                _terminate_ux1b_process_family(
                                    isolation,
                                    browser_process,
                                    cleanup_attempted,
                                )
                            except BaseException as cleanup_error:
                                exit_error.add_note(
                                    "browser cleanup also failed: "
                                    f"{type(cleanup_error).__name__}: "
                                    f"{cleanup_error}"
                                )
                            _raise_worker_exit(
                                evidence,
                                browser_stdio,
                                capture_id=capture_id,
                                allowed_paths=allowed_paths,
                                cause=exit_error,
                            )
                        _terminate_ux1b_process_family(
                            isolation,
                            browser_process,
                            cleanup_attempted,
                        )
                        browser_process = None
                        isolation.consume_quiescent_process_exit_provenance(
                            proof,
                            expected_session_id=session_id,
                            expected_role="browser",
                            expected_process_id=capture_id,
                        )
                        quiescent_process_count += 1
                        response = evidence.decode_worker_response(
                            _read_owned_stdio(
                                browser_stdio.stdout,
                                maximum=evidence.MAX_WORKER_RESPONSE_BYTES,
                            ),
                            expected_request_id=capture_id,
                            allowed_artifact_paths=allowed_paths,
                        )
                        if response["status"] != "staged":
                            raise RunnerDataError(
                                f"nonterminal worker failed for {capture_id}"
                            )
                    if root_capture:
                        semantic_raw: bytes | None = None
                        for artifact in response["rootArtifacts"]:
                            sidecar = (
                                evidence.authenticate_raw_render_sidecar(
                                    browser_root_fd,
                                    artifact["renderSidecar"],
                                    expected_owner=os.getuid(),
                                    identity_row=row,
                                )
                            )
                            sibling_semantic = (
                                evidence._canonical_json_bytes(
                                    sidecar["document"][
                                        "caseSemanticProjection"
                                    ]
                                )
                            )
                            if semantic_raw is None:
                                semantic_raw = sibling_semantic
                            elif semantic_raw != sibling_semantic:
                                raise RunnerDataError(
                                    "root smoke sibling semantics differ"
                                )
                            sidecars.append(sidecar)
                            if authenticate_pngs:
                                png = _authenticate_ux1b_smoke_png(
                                    evidence,
                                    browser_root_fd,
                                    artifact["png"],
                                    identity_row=row,
                                    require_viewport_exact=True,
                                )
                                png["captureId"] = artifact[
                                    "rootCaptureId"
                                ]
                                pngs.append(png)
                    else:
                        sidecars.append(
                            evidence.authenticate_raw_render_sidecar(
                                browser_root_fd,
                                render_path,
                                expected_owner=os.getuid(),
                                identity_row=row,
                            )
                        )
                        if authenticate_pngs:
                            pngs.append(
                                _authenticate_ux1b_smoke_png(
                                    evidence,
                                    browser_root_fd,
                                    png_path,
                                    identity_row=row,
                                )
                            )

                os.killpg(app_process.pid, signal.SIGINT)
                app_exit = isolation.wait_for_clean_owned_process_group_exit(
                    app_process,
                    timeout=20.0,
                )
                _terminate_ux1b_process_family(
                    isolation,
                    app_process,
                    cleanup_attempted,
                )
                app_process = None
                isolation.consume_quiescent_process_exit_provenance(
                    app_exit,
                    expected_session_id=session_id,
                    expected_role="app",
                    expected_process_id=app_process_id,
                )
                quiescent_process_count += 1

            if authenticate_counters:
                app_root_fd = _directory_fd(app_root)
                try:
                    authenticated_counters = evidence.authenticate_counter_bundle(
                        app_root_fd,
                        "fixture-calls.json",
                        expected_owner=os.getuid(),
                        expected_captures=_ux1b_counter_expectations(
                            group_rows,
                            fixture_entrypoint=fixture_entrypoint,
                            app_root=app_root,
                        ),
                    )
                finally:
                    os.close(app_root_fd)
                counter_capture_ids.extend(
                    sorted(authenticated_counters["captures"])
                )

        source_end = isolation.authenticate_source_mirror(
            mirror,
            expected_digest=mirror.digest,
        )
        closing_base_digest = evidence.capture_stack_digest(
            UX1B_CAPTURE_STACK_MEMBERS,
            root_fd=workspace_fd,
        )
        if (
            source_start.get("digest") != source_end.get("digest")
            or closing_base_digest != base_digest
            or len(sidecars) != expected_artifact_captures
            or (
                authenticate_pngs
                and len(pngs) != expected_artifact_captures
            )
            or (
                authenticate_counters
                and set(counter_capture_ids)
                != {f'{row["case"]}/{row["viewport"]["name"]}' for row in rows}
            )
        ):
            raise RunnerDataError("nonterminal capture closure differs")
        return _UX1BNonterminalResult(
            base_capture_stack_digest=base_digest,
            source_digest=mirror.digest,
            capture_ids=(
                tuple(row["rootCaptureId"] for row in root_expansion)
                if root_capture
                else tuple(
                    f'{row["case"]}/{row["viewport"]["name"]}'
                    for row in rows
                )
            ),
            sidecars=tuple(sidecars),
            pngs=tuple(pngs),
            counter_capture_ids=tuple(sorted(counter_capture_ids)),
            quiescent_process_count=quiescent_process_count,
        )
    finally:
        active_error = sys.exc_info()[1]
        cleanup_error = _quiesce_or_retain_ux1b_runtime(
            isolation,
            owned_runtime,
            owned_processes,
            cleanup_attempted,
        )
        if cleanup_error is None:
            release_error = _release_ux1b_nonterminal_runtime(
                isolation,
                owned_runtime,
            )
        else:
            release_error = None
        _finish_ux1b_nonterminal_cleanup(
            active_error,
            cleanup_error,
            release_error,
        )


def run_ux1b_control_discovery(
    *, workspace_fd: int | None = None
) -> UX1BControlDiscovery:
    """Capture the exact nonterminal 57-row catalog-discovery projection."""

    owned_workspace_fd = _directory_fd(WORKSPACE_ROOT) if workspace_fd is None else None
    active_workspace_fd = owned_workspace_fd if owned_workspace_fd is not None else workspace_fd
    assert active_workspace_fd is not None
    try:
        result = _run_ux1b_nonterminal_capture(
            ux1b_control_discovery_rows(),
            label="discovery",
            expected_group_counts={
                UX1B_PROFILE: 21,
                UX1B_SELECTION_PROFILE: 36,
            },
            authenticate_pngs=False,
            authenticate_counters=False,
            workspace_fd=active_workspace_fd,
        )
    finally:
        if owned_workspace_fd is not None:
            os.close(owned_workspace_fd)
    if len(result.sidecars) != 57:
        raise RunnerDataError("UX1B control discovery did not return 57 sidecars")
    return UX1BControlDiscovery(
        base_capture_stack_digest=result.base_capture_stack_digest,
        source_digest=result.source_digest,
        sidecars=result.sidecars,
    )


def run_ux1b_sequence12_control_discovery_and_smoke(
    *,
    workspace_fd: int | None = None,
) -> tuple[UX1BControlDiscovery, UX1BRealSmoke]:
    """Derive the catalog from 21 pages plus 36 deduplicated root semantics."""

    owned_workspace_fd = (
        _directory_fd(WORKSPACE_ROOT)
        if workspace_fd is None
        else None
    )
    active_workspace_fd = (
        owned_workspace_fd
        if owned_workspace_fd is not None
        else workspace_fd
    )
    assert active_workspace_fd is not None
    full_rows = tuple(
        row
        for row in ux1b_control_discovery_rows()
        if row["fixtureEntrypoint"]
        == UX1B_FIXTURE_ENTRYPOINTS[UX1B_PROFILE]
    )
    if len(full_rows) != 21:
        raise RunnerDataError(
            "Sequence 12 full-page discovery is not exact 21"
        )
    try:
        full_discovery = _run_ux1b_nonterminal_capture(
            full_rows,
            label="discovery",
            expected_group_counts={
                UX1B_PROFILE: 21,
                UX1B_SELECTION_PROFILE: 0,
            },
            authenticate_pngs=False,
            authenticate_counters=False,
            workspace_fd=active_workspace_fd,
        )
        root_smoke = run_ux1b_sequence12_root_smoke(
            workspace_fd=active_workspace_fd,
        )
    finally:
        if owned_workspace_fd is not None:
            os.close(owned_workspace_fd)
    if (
        full_discovery.base_capture_stack_digest
        != root_smoke.base_capture_stack_digest
        or full_discovery.source_digest != root_smoke.source_digest
        or len(full_discovery.sidecars) != 21
    ):
        raise RunnerDataError(
            "Sequence 12 discovery/smoke provenance differs"
        )
    logical_controls = (
        _evidence_api().adapt_root_raw_sidecars_for_control_discovery(
            root_smoke.sidecars
        )
    )
    combined = (*full_discovery.sidecars, *logical_controls)
    if len(combined) != 57:
        raise RunnerDataError(
            "Sequence 12 control discovery is not exact 21 + 36"
        )
    return (
        UX1BControlDiscovery(
            base_capture_stack_digest=(
                full_discovery.base_capture_stack_digest
            ),
            source_digest=full_discovery.source_digest,
            sidecars=combined,
        ),
        root_smoke,
    )


def run_ux1b_real_smoke(*, workspace_fd: int | None = None) -> UX1BRealSmoke:
    """Run the contract-free exact-ten real mobile pre-freeze gate."""

    owned_workspace_fd = _directory_fd(WORKSPACE_ROOT) if workspace_fd is None else None
    active_workspace_fd = owned_workspace_fd if owned_workspace_fd is not None else workspace_fd
    assert active_workspace_fd is not None
    try:
        result = _run_ux1b_nonterminal_capture(
            ux1b_real_smoke_rows(),
            label="smoke",
            expected_group_counts={
                UX1B_PROFILE: 1,
                UX1B_SELECTION_PROFILE: 9,
            },
            authenticate_pngs=True,
            authenticate_counters=True,
            workspace_fd=active_workspace_fd,
        )
    finally:
        if owned_workspace_fd is not None:
            os.close(owned_workspace_fd)
    exact_ids = (
        "stock-checkup/mobile",
        *(
            f'{row["case"]}/mobile'
            for row in ux1b_profile_rows(UX1B_SELECTION_PROFILE)
            if row.get("viewport")
            == {"name": "mobile", "width": 390, "height": 844}
        ),
    )
    if (
        result.capture_ids != exact_ids
        or len(result.sidecars) != 10
        or len(result.pngs) != 10
        or result.counter_capture_ids != tuple(sorted(exact_ids))
        or result.quiescent_process_count != 12
    ):
        raise RunnerDataError("UX1B real smoke closure is not exact 1 + 9")
    return UX1BRealSmoke(
        base_capture_stack_digest=result.base_capture_stack_digest,
        source_digest=result.source_digest,
        capture_ids=result.capture_ids,
        sidecars=result.sidecars,
        pngs=result.pngs,
        counter_capture_ids=result.counter_capture_ids,
        quiescent_process_count=result.quiescent_process_count,
    )


def run_ux1b_sequence12_root_smoke(
    *,
    workspace_fd: int | None = None,
) -> UX1BRealSmoke:
    """Run all 36 logical requests and authenticate 44 root captures."""

    owned_workspace_fd = (
        _directory_fd(WORKSPACE_ROOT)
        if workspace_fd is None
        else None
    )
    active_workspace_fd = (
        owned_workspace_fd
        if owned_workspace_fd is not None
        else workspace_fd
    )
    assert active_workspace_fd is not None
    rows = ux1b_profile_rows(UX1B_SELECTION_PROFILE)
    try:
        result = _run_ux1b_nonterminal_capture(
            rows,
            label="smoke",
            expected_group_counts={
                UX1B_PROFILE: 0,
                UX1B_SELECTION_PROFILE: 36,
            },
            authenticate_pngs=True,
            authenticate_counters=True,
            workspace_fd=active_workspace_fd,
            root_capture=True,
        )
    finally:
        if owned_workspace_fd is not None:
            os.close(owned_workspace_fd)
    expansion = _evidence_api().root_capture_expansion_rows()
    expected_root_ids = tuple(row["rootCaptureId"] for row in expansion)
    expected_logical_ids = tuple(
        sorted(
            f'{row["case"]}/{row["viewport"]["name"]}'
            for row in rows
        )
    )
    if (
        result.capture_ids != expected_root_ids
        or len(result.sidecars) != 44
        or len(result.pngs) != 44
        or tuple(png["captureId"] for png in result.pngs)
        != expected_root_ids
        or result.counter_capture_ids != expected_logical_ids
        or result.quiescent_process_count != 37
    ):
        raise RunnerDataError(
            "Sequence 12 real smoke closure is not exact 36/44"
        )
    return UX1BRealSmoke(
        base_capture_stack_digest=result.base_capture_stack_digest,
        source_digest=result.source_digest,
        capture_ids=result.capture_ids,
        sidecars=result.sidecars,
        pngs=result.pngs,
        counter_capture_ids=result.counter_capture_ids,
        quiescent_process_count=result.quiescent_process_count,
    )


def _open_ux1b_capture_stack_destination(
    selection: str = "legacy",
) -> UX1BCaptureStackDestination:
    """Retain the workspace and exact contract-parent descriptors."""

    contract_path = Path(
        os.path.abspath(
            os.path.expanduser(
                os.fspath(_ux1b_capture_stack_contract_path(selection))
            )
        )
    )
    workspace = Path(os.path.abspath(os.fspath(WORKSPACE_ROOT)))
    try:
        relative = contract_path.relative_to(workspace)
    except ValueError as exc:
        raise RunnerDataError(
            "UX1B capture-stack contract escaped the workspace"
        ) from exc
    expected_relative = {
        "legacy": "docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json",
        "seq12": (
            "docs/ui-ux/"
            "quant-radar-ui-v2-ux1b-capture-stack-seq12.json"
        ),
        "seq13": (
            "docs/ui-ux/"
            "quant-radar-ui-v2-ux1b-capture-stack-seq13.json"
        ),
    }.get(selection)
    if relative.as_posix() != expected_relative:
        raise RunnerDataError("UX1B capture-stack contract path differs")

    workspace_fd = -1
    parent_fd = -1
    parent_bindings: list[UX1BDirectoryBinding] = []
    try:
        workspace_fd = _directory_fd(workspace)
        workspace_binding = _freeze_ux1b_directory_binding(
            ".",
            workspace_fd,
        )
        parent_fd = os.dup(workspace_fd)
        os.set_inheritable(parent_fd, False)
        for component in relative.parts[:-1]:
            child_fd = _open_directory_component(
                parent_fd,
                component,
                create=False,
            )
            os.close(parent_fd)
            parent_fd = child_fd
            parent_bindings.append(
                _freeze_ux1b_directory_binding(component, child_fd)
            )
        return UX1BCaptureStackDestination(
            workspace_fd=workspace_fd,
            parent_fd=parent_fd,
            relative_path=relative.as_posix(),
            leaf_name=relative.parts[-1],
            workspace_binding=workspace_binding,
            parent_bindings=tuple(parent_bindings),
        )
    except BaseException:
        for descriptor in (parent_fd, workspace_fd):
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        raise


def _open_ux1b_capture_stack_archive_destination(
    archive_name: str,
) -> UX1BCaptureStackDestination:
    """Retain the independent workspace-to-recovery archive chain."""

    if not isinstance(archive_name, str) or re.fullmatch(
        r"superseded-capture-stack-[0-9a-f]{64}\.json", archive_name
    ) is None:
        raise RunnerDataError("UX1B capture-stack archive name is invalid")
    workspace = Path(os.path.abspath(os.fspath(WORKSPACE_ROOT)))
    relative = Path(
        ".claude/ui_snapshots/ux1b/recovery"
    ) / archive_name
    workspace_fd = -1
    parent_fd = -1
    parent_bindings: list[UX1BDirectoryBinding] = []
    try:
        workspace_fd = _directory_fd(workspace)
        workspace_binding = _freeze_ux1b_directory_binding(
            ".",
            workspace_fd,
        )
        parent_fd = os.dup(workspace_fd)
        os.set_inheritable(parent_fd, False)
        for component in relative.parts[:-1]:
            child_fd = _open_directory_component(
                parent_fd,
                component,
                create=False,
            )
            os.close(parent_fd)
            parent_fd = child_fd
            parent_bindings.append(
                _freeze_ux1b_directory_binding(component, child_fd)
            )
        return UX1BCaptureStackDestination(
            workspace_fd=workspace_fd,
            parent_fd=parent_fd,
            relative_path=relative.as_posix(),
            leaf_name=archive_name,
            workspace_binding=workspace_binding,
            parent_bindings=tuple(parent_bindings),
        )
    except BaseException:
        for descriptor in (parent_fd, workspace_fd):
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        raise


def _reauthenticate_ux1b_capture_stack_destination(
    destination: UX1BCaptureStackDestination,
) -> None:
    opened_fds: list[int] = []
    try:
        _require_ux1b_directory_binding(
            destination.workspace_fd,
            destination.workspace_binding,
        )
        current_fd = destination.workspace_fd
        for binding in destination.parent_bindings:
            current_fd = _open_bound_ux1b_directory_component(
                current_fd,
                binding,
            )
            opened_fds.append(current_fd)
        observed_parent = os.fstat(current_fd)
        retained_parent = os.fstat(destination.parent_fd)
        if (
            observed_parent.st_dev,
            observed_parent.st_ino,
            observed_parent.st_uid,
            stat.S_IMODE(observed_parent.st_mode),
        ) != (
            retained_parent.st_dev,
            retained_parent.st_ino,
            retained_parent.st_uid,
            stat.S_IMODE(retained_parent.st_mode),
        ):
            raise RunnerDataError(
                "retained UX1B capture-stack parent changed"
            )
    finally:
        for descriptor in reversed(opened_fds):
            try:
                os.close(descriptor)
            except OSError:
                pass


def freeze_ux1b_capture_stack(
    *,
    expected_capture_stack_sha256: str | None = None,
    selection: str = "legacy",
) -> dict[str, Any]:
    """Discover, smoke, then create or authorized-CAS-rotate one stack."""

    if selection not in UX1B_CAPTURE_STACK_CHOICES:
        raise RunnerDataError("UX1B capture-stack selection is invalid")
    if (
        selection in {"seq12", "seq13"}
        and expected_capture_stack_sha256 is not None
    ):
        raise RunnerDataError(
            "versioned capture-stack publication does not rotate"
        )
    if expected_capture_stack_sha256 is not None and (
        not isinstance(expected_capture_stack_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_capture_stack_sha256) is None
    ):
        raise RunnerDataError("expected UX1B capture-stack SHA-256 is invalid")

    evidence = _evidence_api()
    destination: UX1BCaptureStackDestination | None = None
    archive_destination: UX1BCaptureStackDestination | None = None
    old_contract: Any | None = None
    archive_name: str | None = None
    try:
        destination = (
            _open_ux1b_capture_stack_destination()
            if selection == "legacy"
            else _open_ux1b_capture_stack_destination(selection)
        )
        _reauthenticate_ux1b_capture_stack_destination(destination)
        try:
            os.stat(
                destination.leaf_name,
                dir_fd=destination.parent_fd,
                follow_symlinks=False,
            )
            canonical_exists = True
        except FileNotFoundError:
            canonical_exists = False
        except OSError as exc:
            raise RunnerDataError(
                "UX1B capture-stack canonical leaf cannot be inspected"
            ) from exc
        if (
            selection == "legacy"
            and canonical_exists != (expected_capture_stack_sha256 is not None)
        ):
            raise RunnerDataError(
                "UX1B capture-stack expected SHA must match existing-leaf mode"
            )
        if selection in {"seq12", "seq13"} and canonical_exists:
            authenticated, _catalog, authenticated_sha256 = (
                evidence.authenticate_capture_stack_contract(
                    destination.workspace_fd,
                    destination.relative_path,
                    workspace_root_fd=destination.workspace_fd,
                    expected_owner=os.getuid(),
                )
            )
            if (
                authenticated.get("rootExpansionSha256")
                != evidence.ROOT_CAPTURE_EXPANSION_SHA256
            ):
                raise RunnerDataError(
                    "versioned stack lacks its root expansion binding"
                )
            canonical_raw = json.dumps(
                authenticated,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            return {
                "status": "verified",
                "path": destination.relative_path,
                "sha256": authenticated_sha256,
                "size": len(canonical_raw),
                "baseCaptureStackDigest": authenticated[
                    "baseCaptureStackDigest"
                ],
                "captureStackDigest": authenticated[
                    "captureStackDigest"
                ],
                "sourceDigest": None,
                "discoverySidecars": 0,
                "smokeCaptures": 0,
                "smokeQuiescentProcesses": 0,
            }
        if canonical_exists:
            old_contract = evidence.freeze_artifact_contract(
                destination.parent_fd,
                destination.leaf_name,
                expected_owner=os.getuid(),
                max_bytes=evidence.MAX_CONTROL_CATALOG_BYTES,
            )
            if (
                old_contract.leaf.sha256 != expected_capture_stack_sha256
                or old_contract.leaf.link_count != 1
                or old_contract.leaf.mode & 0o022
            ):
                raise RunnerDataError(
                    "UX1B existing capture-stack authority differs"
                )
            archive_name = (
                "superseded-capture-stack-"
                f"{expected_capture_stack_sha256}.json"
            )
            archive_destination = (
                _open_ux1b_capture_stack_archive_destination(archive_name)
            )
            _reauthenticate_ux1b_capture_stack_destination(
                archive_destination
            )

        stack_start = evidence.capture_stack_digest(
            UX1B_CAPTURE_STACK_MEMBERS,
            root_fd=destination.workspace_fd,
        )
        if selection in {"seq12", "seq13"}:
            discovery, smoke = (
                run_ux1b_sequence12_control_discovery_and_smoke(
                    workspace_fd=destination.workspace_fd
                )
            )
        else:
            discovery = run_ux1b_control_discovery(
                workspace_fd=destination.workspace_fd
            )
            smoke = run_ux1b_real_smoke(
                workspace_fd=destination.workspace_fd
            )
        if discovery.base_capture_stack_digest != stack_start:
            raise RunnerDataError("UX1B discovery capture stack changed before freeze")
        if (
            smoke.base_capture_stack_digest != stack_start
            or smoke.source_digest != discovery.source_digest
        ):
            raise RunnerDataError("UX1B real smoke differs from discovery provenance")
        control_catalog = derive_ux1b_control_catalog(
            discovery.sidecars,
            base_capture_stack_digest=stack_start,
        )
        stack_after_discovery = evidence.capture_stack_digest(
            UX1B_CAPTURE_STACK_MEMBERS,
            root_fd=destination.workspace_fd,
        )
        if stack_after_discovery != stack_start:
            raise RunnerDataError("UX1B capture stack changed during discovery or smoke")
        contract = evidence.build_capture_stack_contract(
            UX1B_CAPTURE_STACK_MEMBERS,
            root_fd=destination.workspace_fd,
            control_catalog=control_catalog,
            root_expansion_sha256=(
                evidence.ROOT_CAPTURE_EXPANSION_SHA256
                if selection in {"seq12", "seq13"}
                else None
            ),
        )
        if contract.get("baseCaptureStackDigest") != stack_start:
            raise RunnerDataError("UX1B built contract differs from the final rehash")

        if old_contract is not None:
            _reauthenticate_ux1b_capture_stack_destination(destination)
        if old_contract is not None and archive_destination is not None:
            _reauthenticate_ux1b_capture_stack_destination(
                archive_destination
            )
        try:
            if old_contract is None:
                publication = evidence.publish_capture_stack_contract(
                    destination.parent_fd,
                    destination.leaf_name,
                    contract,
                    workspace_root_fd=destination.workspace_fd,
                )
            else:
                assert archive_destination is not None
                assert archive_name is not None
                publication = evidence.rotate_capture_stack_contract(
                    destination.parent_fd,
                    destination.leaf_name,
                    contract,
                    expected_existing_contract=old_contract,
                    expected_existing_sha256=expected_capture_stack_sha256,
                    archive_dir_fd=archive_destination.parent_fd,
                    archive_name=archive_name,
                    workspace_root_fd=destination.workspace_fd,
                )
        except BaseException as publication_error:
            for label, retained in (
                ("canonical", destination),
                ("archive", archive_destination),
            ):
                if retained is None:
                    continue
                try:
                    _reauthenticate_ux1b_capture_stack_destination(retained)
                except BaseException as reauthentication_error:
                    publication_error.add_note(
                        f"capture-stack {label} destination post-publication "
                        "reauthentication also failed: "
                        f"{type(reauthentication_error).__name__}: "
                        f"{reauthentication_error}"
                    )
            raise

        _reauthenticate_ux1b_capture_stack_destination(destination)
        if archive_destination is not None:
            _reauthenticate_ux1b_capture_stack_destination(
                archive_destination
            )

        if old_contract is not None:
            expected_raw = json.dumps(
                contract,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            expected_receipt = {
                "path": destination.leaf_name,
                "sha256": hashlib.sha256(expected_raw).hexdigest(),
                "size": len(expected_raw),
                "captureStackDigest": contract["captureStackDigest"],
                "previousSha256": expected_capture_stack_sha256,
                "archiveName": archive_name,
                "archiveSha256": expected_capture_stack_sha256,
                "archiveSize": old_contract.leaf.size,
            }
            if publication != expected_receipt:
                raise RunnerDataError(
                    "UX1B capture-stack rotation receipt differs"
                )

        authenticated, _catalog, authenticated_sha256 = (
            evidence.authenticate_capture_stack_contract(
                destination.workspace_fd,
                destination.relative_path,
                workspace_root_fd=destination.workspace_fd,
                expected_owner=os.getuid(),
                expected_sha256=publication.get("sha256"),
            )
        )
        _reauthenticate_ux1b_capture_stack_destination(destination)
        if archive_destination is not None:
            _reauthenticate_ux1b_capture_stack_destination(
                archive_destination
            )
    finally:
        active_error = sys.exc_info()[1]
        close_errors: list[tuple[str, BaseException]] = []
        for label, retained in (
            ("archive", archive_destination),
            ("canonical", destination),
        ):
            if retained is None:
                continue
            try:
                close_error = retained.close()
            except BaseException as exc:
                close_error = exc
            if close_error is not None:
                close_errors.append((label, close_error))
        if active_error is not None:
            for label, close_error in close_errors:
                active_error.add_note(
                    f"capture-stack {label} destination close also failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        elif close_errors:
            first_label, first_error = close_errors[0]
            for label, close_error in close_errors[1:]:
                first_error.add_note(
                    f"capture-stack {label} destination close also failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
            raise first_error

    if (
        authenticated != contract
        or authenticated_sha256 != publication.get("sha256")
        or publication.get("captureStackDigest")
        != contract.get("captureStackDigest")
    ):
        raise RunnerDataError("UX1B published capture-stack contract differs on reopen")
    result = {
        "status": "frozen",
        "path": destination.relative_path,
        "sha256": authenticated_sha256,
        "size": publication.get("size"),
        "baseCaptureStackDigest": stack_start,
        "captureStackDigest": contract["captureStackDigest"],
        "sourceDigest": discovery.source_digest,
        "discoverySidecars": len(discovery.sidecars),
        "smokeCaptures": len(smoke.capture_ids),
        "smokeQuiescentProcesses": smoke.quiescent_process_count,
    }
    if old_contract is not None:
        assert archive_destination is not None
        result.update(
            {
                "previousSha256": publication["previousSha256"],
                "archivePath": archive_destination.relative_path,
                "archiveSha256": publication["archiveSha256"],
                "archiveSize": publication["archiveSize"],
            }
        )
    return result


def run_matrix(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    cases, viewports = _prepare_args(args)
    profile = getattr(args, "profile", None)
    phase = getattr(args, "phase", None)
    # Formal UX1B profiles leave the legacy Playwright block before it imports
    # or launches a browser.  UX-0/UX-1A retain the historical path below.
    if profile in UX1B_PROFILES:
        return _run_ux1b_recovery(
            args,
            cases=cases,
            viewports=viewports,
        )
    fixture_contracts = (
        load_ux1b_fixture_contracts() if profile == UX1B_PROFILE else None
    )
    authenticated_pretheme = (
        load_authenticated_pretheme_manifest(
            getattr(args, "theme_contract", None) or UX1B_THEME_CONTRACT_PATH
        )
        if profile == UX1B_PROFILE and phase == "posttheme"
        else None
    )
    owned = create_owned_run(args.out_dir, profile=profile, phase=phase)
    manifest = _manifest_template(
        owned,
        cases=cases,
        viewports=viewports,
        profile=profile,
        phase=phase,
    )
    _write_manifest(owned, manifest)
    process: subprocess.Popen[bytes] | None = None
    deny_proxy: OwnedDenyProxy | None = None
    deny_proxy_armed = False
    source_digest_started = False
    success_candidate = False
    code = 1
    old_handlers: dict[int, Any] = {}

    def interrupted(_signum: int, _frame: Any) -> None:
        raise RunnerInterrupted()

    for signum in (signal.SIGINT, signal.SIGTERM):
        old_handlers[signum] = signal.getsignal(signum)
        signal.signal(signum, interrupted)

    run_authority: _RunSuccessAuthority | None = None
    try:
        # This capability is intentionally minted and registered inline: no
        # caller-supplied mapping or public helper can manufacture success
        # authority for a different manifest/run.
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
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise DependencyUnavailable(
                "Playwright is not installed in this interpreter; UX-0 keeps it optional"
            ) from exc

        with sync_playwright() as playwright:
            availability = _browser_availability(playwright)
            manifest["browserCapabilities"] = {
                name: "supported" if available else "unsupported"
                for name, available in availability.items()
            }
            _write_manifest(owned, manifest)
            selected, capabilities = select_browsers(args.browser, availability)
            manifest["browserCapabilities"] = capabilities
            manifest["selectedBrowsers"] = list(selected)
            _write_manifest(owned, manifest)
            network_contract: UX1BNetworkContract | None = None
            if profile == UX1B_PROFILE:
                if selected != ("chromium",):
                    raise RunnerDataError(
                        "UX1B full-page manifest requires exactly one Chromium browser"
                    )
                deny_proxy = OwnedDenyProxy()
                manifest["sourceDigestStart"] = ux1b_source_digest()
                source_digest_started = True
                process, port = _start_streamlit(
                    owned,
                    profile=profile,
                    phase=phase,
                    deny_proxy_port=deny_proxy.port,
                )
                network_contract = UX1BNetworkContract(port, deny_proxy.port)
                calibration = calibrate_darwin_sandbox_contract(network_contract)
                manifest["server"]["kernelIsolation"] = calibration["capability"]
                manifest["server"]["sandboxCalibration"] = calibration
                if sys.platform == "darwin" and not deny_proxy.wait_for_attempts(1):
                    raise RunnerDataError(
                        "Darwin sandbox calibration did not reach the owned deny proxy"
                    )
                deny_proxy.reset()
                deny_proxy_armed = True
            else:
                process, port = _start_streamlit(owned)
            _print_progress(f"owned fixture app ready on 127.0.0.1:{port}", args)

            projection_by_key = {
                item.registry_key: item for item in UX1B_PAGE_PROJECTION
            }
            for browser_name in selected:
                browser_type = getattr(playwright, browser_name)
                browser = browser_type.launch(headless=True)
                try:
                    for capture_case in cases:
                        for viewport_name, width, height in viewports:
                            _print_progress(
                                f"capture {browser_name} {capture_case.name} {viewport_name}", args
                            )
                            capture_kwargs: dict[str, Any] = {
                                "browser_name": browser_name,
                                "capture_case": capture_case,
                                "viewport_name": viewport_name,
                                "width": width,
                                "height": height,
                                "port": port,
                                "owned": owned,
                            }
                            if profile == UX1B_PROFILE:
                                page_projection = projection_by_key[capture_case.page]
                                capture_kwargs.update(
                                    {
                                        "profile": profile,
                                        "page_projection": page_projection,
                                        "ready_marker": UX1B_READY_MARKERS[
                                            page_projection.registry_key
                                        ],
                                        "network_contract": network_contract,
                                        "fixture_contracts": fixture_contracts,
                                    }
                                )
                            evidence = _capture_one(browser, **capture_kwargs)
                            manifest["captures"].append(evidence)
                            _write_manifest(owned, manifest)
                finally:
                    browser.close()

            calls = _read_calls(owned.calls_path)
            calls_contract = validate_fixture_calls_contract(
                calls,
                profile=profile,
                fixture_contracts=fixture_contracts,
            )
            manifest["fixtureRevision"] = calls_contract["fixtureRevision"]
            if profile == UX1B_PROFILE:
                manifest["fixtureContractSchema"] = calls_contract[
                    "contractSchema"
                ]
            bootstrap_blocked = calls.get("bootstrapBlockedNetwork") if isinstance(calls, dict) else []
            if bootstrap_blocked:
                manifest["bootstrapBlockedNetwork"] = bootstrap_blocked
            failed = [item for item in manifest["captures"] if item.get("status") != "passed"]
            expected = len(selected) * len(cases) * len(viewports)
            manifest["expectedCaptureCount"] = expected
            if len(manifest["captures"]) != expected:
                failed.append({"failureReasons": ["capture_count_mismatch"]})
            if profile == UX1B_PROFILE:
                if expected != 81:
                    failed.append({"failureReasons": ["ux1b_expected_count_mismatch"]})
                capture_keys = [
                    (item.get("browser"), item.get("page"), item.get("viewport", {}).get("name"))
                    for item in manifest["captures"]
                ]
                exact_keys = {
                    ("chromium", page.registry_key, viewport_name)
                    for page in UX1B_PAGE_PROJECTION
                    for viewport_name, _width, _height in UX1B_VIEWPORTS
                }
                if len(capture_keys) != len(set(capture_keys)) or set(capture_keys) != exact_keys:
                    failed.append({"failureReasons": ["ux1b_capture_identity_mismatch"]})
                proxy_attempts = deny_proxy.attempts() if deny_proxy is not None else []
                manifest["server"]["denyProxyAttemptCount"] = len(proxy_attempts)
                if proxy_attempts:
                    failed.append({"failureReasons": ["deny_proxy_contact"]})
            if bootstrap_blocked:
                failed.append({"failureReasons": ["bootstrap_external_server_request"]})
            success_candidate = not failed
            manifest["status"] = "finalizing" if success_candidate else "failed"
            manifest["finishedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            _write_manifest(owned, manifest)
            code = 1 if failed else 0
    except KeyboardInterrupt as exc:
        manifest["status"] = "interrupted"
        manifest["interruption"] = _terminal_diagnostic(exc, owned)
        manifest["finishedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        _write_manifest(owned, manifest)
        code = 130
    except DependencyUnavailable as exc:
        manifest["status"] = "dependency_unavailable"
        manifest["error"] = _terminal_diagnostic(exc, owned)
        _write_manifest(owned, manifest)
        code = exc.exit_code
    except RunnerDataError as exc:
        manifest["status"] = "invalid_data"
        manifest["error"] = _terminal_diagnostic(exc, owned)
        _write_manifest(owned, manifest)
        code = 3
    except Exception as exc:  # runtime failure: preserve a sanitized partial manifest.
        manifest["status"] = "failed"
        manifest["error"] = _terminal_diagnostic(exc, owned)
        _write_manifest(owned, manifest)
        code = 1
    finally:
        closure_interrupt: KeyboardInterrupt | None = None
        closure_failure: Exception | None = None

        def remember_closure_problem(exc: BaseException) -> None:
            nonlocal closure_interrupt, closure_failure
            if isinstance(exc, KeyboardInterrupt):
                if closure_interrupt is None:
                    closure_interrupt = exc
            elif isinstance(exc, Exception) and closure_failure is None:
                closure_failure = exc

        if process is not None:
            try:
                stop_owned_process(process)
            except (KeyboardInterrupt, Exception) as exc:
                remember_closure_problem(exc)
                # A signal can interrupt process-group shutdown between TERM
                # and wait/handle close.  The bounded retry is intentionally
                # independent of all later evidence closure.
                try:
                    stop_owned_process(process)
                except (KeyboardInterrupt, Exception) as retry_exc:
                    remember_closure_problem(retry_exc)

        if source_digest_started:
            try:
                manifest["sourceDigestEnd"] = ux1b_source_digest()
                manifest["sourceDigestEqual"] = (
                    manifest.get("sourceDigestStart") == manifest["sourceDigestEnd"]
                )
                if not manifest["sourceDigestEqual"]:
                    manifest["status"] = "failed"
                    manifest["sourceContractFailure"] = (
                        "source_changed_while_child_active"
                    )
                    code = 1
            except KeyboardInterrupt as exc:
                manifest["sourceDigestEqual"] = False
                remember_closure_problem(exc)
            except Exception as exc:
                manifest["sourceDigestEqual"] = False
                manifest["sourceContractFailure"] = _terminal_diagnostic_message(
                    exc, owned
                )
                remember_closure_problem(exc)

        if deny_proxy is not None:
            if deny_proxy_armed:
                try:
                    final_proxy_attempts = deny_proxy.attempts()
                    manifest["server"]["denyProxyAttemptCount"] = len(
                        final_proxy_attempts
                    )
                    if final_proxy_attempts:
                        manifest["status"] = "failed"
                        reasons = manifest.setdefault("runFailureReasons", [])
                        if "deny_proxy_contact" not in reasons:
                            reasons.append("deny_proxy_contact")
                        code = 1
                except (KeyboardInterrupt, Exception) as exc:
                    remember_closure_problem(exc)
            try:
                deny_proxy.close()
            except (KeyboardInterrupt, Exception) as exc:
                remember_closure_problem(exc)
                try:
                    deny_proxy.close()
                except (KeyboardInterrupt, Exception) as retry_exc:
                    remember_closure_problem(retry_exc)

        if (
            closure_interrupt is None
            and closure_failure is None
            and profile == UX1B_PROFILE
            and phase == "pretheme"
        ):
            try:
                if manifest.get("status") == "finalizing" and manifest.get(
                    "sourceDigestEqual"
                ) is True:
                    try:
                        normalize_ux1b_manifest_contract(
                            {**manifest, "status": "passed"}, phase="pretheme"
                        )
                    except RunnerDataError as exc:
                        manifest["status"] = "failed"
                        manifest["manifestContractValidation"] = {
                            "status": "failed",
                            "failure": _terminal_diagnostic_message(exc, owned),
                        }
                        code = 1
                    else:
                        manifest["manifestContractValidation"] = {
                            "status": "passed",
                            "validatedCaptureCount": 81,
                        }
                else:
                    manifest["manifestContractValidation"] = {
                        "status": "not_run",
                        "failure": "pretheme_manifest_failed_before_validation",
                    }
                    code = 1
            except (KeyboardInterrupt, Exception) as exc:
                remember_closure_problem(exc)

        if (
            closure_interrupt is None
            and closure_failure is None
            and authenticated_pretheme is not None
        ):
            try:
                try:
                    contract_label = authenticated_pretheme.contract_path.relative_to(
                        ROOT
                    ).as_posix()
                except ValueError:
                    contract_label = authenticated_pretheme.contract_path.name
                try:
                    manifest_label = authenticated_pretheme.manifest_path.relative_to(
                        ROOT
                    ).as_posix()
                except ValueError:  # pragma: no cover - loader confines this to ROOT.
                    manifest_label = authenticated_pretheme.manifest_path.name
                authentication = {
                    "themeContract": contract_label,
                    "prethemeManifest": manifest_label,
                    "prethemeManifestSha256": authenticated_pretheme.manifest_sha256,
                }
                if manifest.get("status") == "finalizing" and manifest.get(
                    "sourceDigestEqual"
                ) is True:
                    try:
                        comparison = compare_ux1b_manifests(
                            authenticated_pretheme.manifest,
                            {**manifest, "status": "passed"},
                        )
                    except RunnerDataError as exc:
                        manifest["status"] = "failed"
                        manifest["prethemeComparison"] = {
                            **authentication,
                            "status": "failed",
                            "failure": _terminal_diagnostic_message(exc, owned),
                        }
                        code = 1
                    else:
                        manifest["prethemeComparison"] = {
                            **authentication,
                            **comparison,
                        }
                else:
                    manifest["prethemeComparison"] = {
                        **authentication,
                        "status": "not_run",
                        "failure": "posttheme_manifest_failed_before_comparison",
                    }
                    code = 1
            except (KeyboardInterrupt, Exception) as exc:
                remember_closure_problem(exc)

        if closure_interrupt is not None:
            if manifest.get("status") != "failed":
                manifest["status"] = "interrupted"
                manifest["interruption"] = _terminal_diagnostic(
                    closure_interrupt, owned
                )
                code = 130
        elif closure_failure is not None:
            if manifest.get("status") != "interrupted":
                manifest["status"] = "failed"
                manifest["finalizationError"] = _terminal_diagnostic(
                    closure_failure, owned
                )
                code = 1

        manifest["finishedAt"] = datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
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

            finalized = False
            grant: _RunnerFinalizationGrant | None = None
            if success_candidate and code == 0 and manifest.get("status") == "finalizing":
                try:
                    grant = _authorize_terminal_manifest(
                        manifest, authority=run_authority
                    )
                    finalized = finalize_terminal_manifest(manifest, grant=grant)
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
                finally:
                    if grant is not None:
                        _discard_terminal_manifest_grant(grant)
            if success_candidate and code == 0 and not finalized:
                manifest["status"] = "failed"
                manifest.setdefault(
                    "finalizationFailure", "success_closure_was_not_authorized"
                )
                code = 1

            runtime_problem = _retire_run_runtime(run_authority, old_handlers)
            if isinstance(runtime_problem, KeyboardInterrupt):
                if manifest.get("status") != "failed":
                    manifest["status"] = "interrupted"
                    manifest["interruption"] = _terminal_diagnostic(
                        runtime_problem, owned
                    )
                    code = 130
            elif isinstance(runtime_problem, Exception):
                if manifest.get("status") != "interrupted":
                    manifest["status"] = "failed"
                    manifest["finalizationError"] = _terminal_diagnostic(
                        runtime_problem, owned
                    )
                    code = 1

            code = _commit_terminal_manifest(owned, manifest, code)
        finally:
            if terminal_signal_mask is not None:
                _restore_terminal_signal_mask(terminal_signal_mask)
    return code, manifest


def _ux1b_special_cli_mode(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> tuple[int, dict[str, Any]] | None:
    smoke_requested = bool(getattr(args, "ux1b_real_smoke", False))
    freeze_requested = bool(getattr(args, "freeze_capture_stack", False))
    capture_stack_selection = str(
        getattr(args, "capture_stack", "legacy")
    )
    expected_capture_stack_sha256 = getattr(
        args, "expected_capture_stack_sha256", None
    )
    if expected_capture_stack_sha256 is not None and not freeze_requested:
        parser.error(
            "--expected-capture-stack-sha256 requires --freeze-capture-stack"
        )
    if not smoke_requested and not freeze_requested:
        return None
    if smoke_requested and freeze_requested:
        parser.error(
            "--ux1b-real-smoke and --freeze-capture-stack are mutually exclusive"
        )
    incompatible = {
        "--out-dir": args.out_dir,
        "--profile": args.profile,
        "--phase": args.phase,
        "--theme-contract": args.theme_contract,
        "--browser": args.browser,
        "--page": args.page,
        "--case": args.case,
        "--viewport": args.viewport,
        "--no-prompt": args.no_prompt,
        "--verbose": args.verbose,
        "--quiet": args.quiet,
    }
    selected = tuple(name for name, value in incompatible.items() if value)
    if selected:
        parser.error(
            "special UX1B capture mode cannot be combined with "
            + ", ".join(selected)
        )
    if not args.json:
        parser.error("special UX1B capture mode requires --json")
    if freeze_requested:
        if capture_stack_selection == "legacy":
            return 0, freeze_ux1b_capture_stack(
                expected_capture_stack_sha256=expected_capture_stack_sha256,
            )
        return 0, freeze_ux1b_capture_stack(
            expected_capture_stack_sha256=expected_capture_stack_sha256,
            selection=capture_stack_selection,
        )
    if capture_stack_selection != "legacy":
        parser.error("--ux1b-real-smoke requires --capture-stack legacy")

    smoke = run_ux1b_real_smoke()
    return 0, {
        "status": "observed",
        "mode": "ux1b-real-smoke",
        "baseCaptureStackDigest": smoke.base_capture_stack_digest,
        "sourceDigest": smoke.source_digest,
        "captureIds": list(smoke.capture_ids),
        "sidecars": len(smoke.sidecars),
        "pngs": len(smoke.pngs),
        "counterCaptureIds": list(smoke.counter_capture_ids),
        "quiescentProcesses": smoke.quiescent_process_count,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        special = _ux1b_special_cli_mode(args, parser)
        if special is not None:
            code, summary = special
            print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
            return code
        code, manifest = run_matrix(args)
    except RunnerDataError as exc:
        parser.error(str(exc))
    summary = {
        "status": manifest.get("status"),
        "run": manifest.get("run"),
        "captures": {
            "total": len(manifest.get("captures") or []),
            "passed": sum(
                1 for item in (manifest.get("captures") or []) if item.get("status") == "passed"
            ),
        },
        "browserCapabilities": manifest.get("browserCapabilities") or {},
        "manual": manifest.get("manual") or {},
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    elif not args.quiet:
        print(
            f"{summary['status']}: {summary['captures']['passed']}/"
            f"{summary['captures']['total']} captures; "
            f"manifest={summary['run']['outputDir'] + '/' + summary['run']['manifest'] if summary.get('run') else '-'}"
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
