#!/usr/bin/env python3
"""Fail-closed deterministic fixtures for the UX-0 Streamlit baseline.

This module intentionally imports only the Python standard library at module
load time.  The fixture entrypoint imports it before Streamlit so ownership and
the non-loopback network guard are established before any production app code.
UI/provider modules are imported lazily by :func:`install_provider_fixtures`,
after ``app.py`` has called ``st.set_page_config`` and built its page registry.
"""

from __future__ import annotations

import base64
import builtins
import copy
import functools
import hmac
import io
import ipaddress
import json
import os
import posix
import re
import socket
import sqlite3
import stat
import subprocess
import sys
import threading
import time
import webbrowser
import _socket
import _sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType, ModuleType
from typing import Any, Callable, Iterator, Mapping
from urllib.parse import urlsplit


COUNTER_SCHEMA_VERSION = 1
# UX-0/UX-1A evidence is a historical baseline and keeps its original
# revision.  UX-1B extends the fixture contract without changing the counter
# transport shape, so it receives a profile-specific revision and contract
# schema instead of rewriting history or bumping schemaVersion.
FIXTURE_REVISION = "quant-radar-ux0-2026-07-16.2"
UX1B_FIXTURE_REVISION = "quant-radar-ux1b-2026-07-16.1"
UX1B_CONTRACT_SCHEMA_VERSION = 1
OWNERSHIP_MARKER = ".quant-radar-ux0-owner"
FIXED_NOW = "2026-07-15T06:30:00Z"
UX1B_RUN_CONTRACT_FILENAME = ".quant-radar-ux1b-fixture-contract.json"
UX1B_RUN_CONTRACT_SCHEMA = "quant-radar-ui-ux-fixture-run/v1"
UX1B_FULL_PAGE_PROFILE = "ux1b-full-pages"
UX1B_SELECTION_PROFILE = "ux1b-selection-controls"
UX1B_THEME_PROFILE = "ux1b-theme"
UX1B_PROFILE_PHASES = MappingProxyType(
    {
        UX1B_FULL_PAGE_PROFILE: frozenset(
            {"precontrol", "pretheme", "posttheme"}
        ),
        UX1B_SELECTION_PROFILE: frozenset({"precontrol", "postcontrol"}),
        UX1B_THEME_PROFILE: frozenset({"posttheme"}),
    }
)
_MAX_RUN_CONTRACT_BYTES = 4096

# Root-level candidate artifacts are production runtime data when
# SURGE_CANDIDATE_OUTPUT_DIR is unset.  The five deployment artifacts are
# joined by the two legacy screeners and the crypto placeholder that current
# production/UI code still knows how to read.
PRODUCTION_ROOT_CANDIDATE_ARTIFACTS = frozenset(
    {
        "filtered_universe.json",
        "filtered_universe_sp1500.json",
        "filtered_nasdaq.json",
        "ranked_candidates.json",
        "scored_candidates.json",
        "layer2_results.json",
        "dd_results.json",
        "crypto_scored.json",
    }
)

TARGET_ROUTES = frozenset(
    {
        "today-decision",
        "trade-state",
        "us-screener",
        "options-flow",
        "stock-checkup",
        "options-cockpit",
        "radar",
        "ibkr-reconcile",
        "sector-rotation",
        "theme-flow",
        "us-cot",
        "market-thesis",
        "us-x",
        "retro-analysis",
        "analytics-db",
        "knowledge-graph",
        "us-options",
        "analyst-views",
        "institutions",
        "industry-roles",
        "watchlist-categorize",
        "influencers",
        "schedules",
        "ai-updates",
        "crypto-universe",
        "crypto-screener",
        "crypto-x",
    }
)

ROUTE_RENDER_CALLABLES = MappingProxyType(
    {
        "today-decision": "today_decision.render",
        "trade-state": "trade_state.render",
        "us-screener": "us_screener.render",
        "options-flow": "options_flow.render",
        "stock-checkup": "stock_checkup.render",
        "options-cockpit": "options_cockpit.render",
        "radar": "radar.render",
        "ibkr-reconcile": "ibkr_reconcile.render",
        "sector-rotation": "sector_rotation.render",
        "theme-flow": "theme_flow.render",
        "us-cot": "us_cot.render",
        "market-thesis": "market_thesis.render",
        "us-x": "us_x",
        "retro-analysis": "retro_analysis.render",
        "analytics-db": "analytics_db.render",
        "knowledge-graph": "knowledge_graph.render",
        "us-options": "us_options.render",
        "analyst-views": "analyst_views.render",
        "institutions": "institutions.render",
        "industry-roles": "industry_roles.render",
        "watchlist-categorize": "watchlist_categorize.render",
        "influencers": "influencers.render",
        "schedules": "sys_schedules.render",
        "ai-updates": "sys_ai_updates.render",
        "crypto-universe": "crypto_universe.render",
        "crypto-screener": "crypto_screener.render",
        "crypto-x": "crypto_x",
    }
)

_COMMON_OWNED_PATHS = {
    "runtime": ".",
    "reports": "reports",
    "content": "content",
    "candidates": "candidates",
    "chat": "ai-chat",
}


def _owned_paths(**extra: str) -> Mapping[str, str]:
    return MappingProxyType({**_COMMON_OWNED_PATHS, **extra})


ROUTE_OWNED_PATHS = MappingProxyType(
    {
        route: _owned_paths()
        for route in TARGET_ROUTES
    }
)


@dataclass(frozen=True, slots=True)
class SelectionCase:
    """One immutable real-render case in the focused control matrix."""

    route: str
    registry_key: str
    callable_name: str
    root_selectors: tuple[str, ...]
    session_keys: tuple[str, ...]


SELECTION_CASES: Mapping[str, SelectionCase] = MappingProxyType(
    {
        "risk-guard-controls": SelectionCase(
            "/__selection__/risk-guard",
            "risk-guard",
            "risk_guard.render",
            (".st-key-rg_source",),
            ("rg_source",),
        ),
        "institutions-controls": SelectionCase(
            "/__selection__/institutions",
            "institutions",
            "institutions.render",
            (".st-key-inst_view",),
            ("inst_view",),
        ),
        "options-cockpit-controls": SelectionCase(
            "/__selection__/options-cockpit",
            "options-cockpit",
            "options_cockpit.render",
            (".st-key-cockpit_price_view_NVDA",),
            ("cockpit_price_view_NVDA",),
        ),
        "radar-controls": SelectionCase(
            "/__selection__/radar",
            "radar",
            "radar.render",
            (".st-key-radar_source", ".st-key-radar_view"),
            ("radar_source", "radar_view"),
        ),
        "knowledge-graph-controls": SelectionCase(
            "/__selection__/knowledge-graph",
            "knowledge-graph",
            "knowledge_graph.render",
            (".st-key-kg_view_mode", ".st-key-kg_label_mode"),
            ("kg_view_mode", "kg_label_mode"),
        ),
        "ai-chat-settings-controls": SelectionCase(
            "/__selection__/ai-chat-settings",
            "today-decision",
            "today_decision.render",
            (".st-key-ai_chat_mode",),
            ("ai_chat_mode",),
        ),
        "retro-controls": SelectionCase(
            "/__selection__/retro-analysis",
            "retro-analysis",
            "retro_analysis.render",
            (".st-key-retro_validation_lane",),
            ("retro_validation_lane",),
        ),
        "analytics-controls": SelectionCase(
            "/__selection__/analytics-db",
            "analytics-db",
            "analytics_db.render",
            (".st-key-adb_table",),
            ("adb_table",),
        ),
        "stock-checkup-controls": SelectionCase(
            "/__selection__/stock-checkup",
            "stock-checkup",
            "stock_checkup.render",
            (".st-key-checkup_mode",),
            ("checkup_mode",),
        ),
    }
)
SELECTION_VIEWPORTS: Mapping[str, tuple[int, int]] = MappingProxyType(
    {
        "desktop": (1440, 900),
        "tablet": (768, 1024),
        "mobile": (390, 844),
        "narrow": (320, 844),
    }
)

_SELECTION_REGISTRY_CALLABLES: Mapping[str, str] = MappingProxyType(
    {
        **dict(ROUTE_RENDER_CALLABLES),
        "risk-guard": "risk_guard.render",
        "theme-gallery": "ui_ux_theme_fixture_app",
    }
)
# These routes have definition-bound or specialised roots in addition to the
# common runtime tree.  Values stay relative so the authenticated run root is
# the only authority that can resolve them.
ROUTE_OWNED_PATHS = MappingProxyType(
    {
        **dict(ROUTE_OWNED_PATHS),
        "radar": _owned_paths(oversold="reports/oversold_reversal"),
        "theme-flow": _owned_paths(theme_flow="reports/theme_flow"),
        "us-cot": _owned_paths(cot="reports/cot"),
        "market-thesis": _owned_paths(market_thesis="reports/market_thesis"),
        "us-x": _owned_paths(social="reports/social_intelligence", roster="content/influencers.json"),
        "retro-analysis": _owned_paths(retrospective="reports/retrospective"),
        "analytics-db": _owned_paths(analytics="analytics", status="reports/run_status"),
        "knowledge-graph": _owned_paths(vault="knowledge"),
        "industry-roles": _owned_paths(roles="content", suggestions="reports"),
        "watchlist-categorize": _owned_paths(watchlist="content/us_watchlist.txt"),
        "influencers": _owned_paths(roster="content/influencers.json"),
        "crypto-universe": _owned_paths(),
        "crypto-x": _owned_paths(social="reports/social_intelligence", roster="content/influencers.json"),
    }
)
_SELECTION_REGISTRY_OWNED_PATHS: Mapping[str, Mapping[str, str]] = MappingProxyType(
    {
        **dict(ROUTE_OWNED_PATHS),
        "risk-guard": _owned_paths(risk="reports/risk_guard"),
        "theme-gallery": _owned_paths(runtime="theme-gallery"),
    }
)
THEME_OWNED_PATHS: Mapping[str, str] = MappingProxyType(
    dict(_SELECTION_REGISTRY_OWNED_PATHS["theme-gallery"])
)

ZERO_MUTATOR_COUNTERS = frozenset(
    {
        "mutator.production_read.attempt",
        "mutator.production_write.attempt",
        "mutator.subprocess.popen.attempt",
        "mutator.external_browser.attempt",
        "mutator.login_auth.attempt",
        "mutator.runtime_write.attempt",
        "mutator.theme_flow.launch_background.attempt",
        "mutator.theme_flow.write.attempt",
        "mutator.analytics.write_status.attempt",
        "mutator.analytics.refresh.attempt",
        "mutator.ibkr.connect.attempt",
        "mutator.x.auto_refresh.attempt",
        "mutator.x.ai_summary.attempt",
        "mutator.x.snapshot_write.attempt",
        "mutator.industry_roles.write.attempt",
        "mutator.watchlist.write.attempt",
        "mutator.influencers.write.attempt",
    }
)


def _counter_contract(
    positive: Mapping[str, int] | None = None,
    zero: Iterator[str] = (),
) -> Mapping[str, Any]:
    exact_positive = {
        "session.setup": 1,
        "page.render.attempt": 1,
        **dict(positive or {}),
    }
    return MappingProxyType(
        {
            "positive": MappingProxyType(exact_positive),
            "zero": frozenset(ZERO_MUTATOR_COUNTERS | set(zero)),
        }
    )


# The semantic theme gallery does not execute a production page/provider.  Its
# single positive counter is recorded only after the complete gallery renders;
# the shared mutator set remains an explicit exact-zero contract.
THEME_COUNTER_CONTRACT: Mapping[str, Any] = MappingProxyType(
    {
        "positive": MappingProxyType({"theme.gallery.render": 1}),
        "zero": frozenset(ZERO_MUTATOR_COUNTERS),
    }
)


# Exact values are calibrated by the focused real-render matrix below.  They
# are public fixture contract data consumed by the UX-1B runner; unlisted calls
# are rejected by the runner rather than silently tolerated.
ROUTE_COUNTER_CONTRACTS = MappingProxyType(
    {
        "today-decision": _counter_contract(
            {
                "shared.ledger.execute": 1,
                "shared.reconciliation.execute": 1,
                "today.candidate_history.execute": 1,
                "today.candidate_status.execute": 3,
                "today.claude_pending.execute": 2,
                "today.daily_summary.execute": 1,
                "market_thesis.latest_api.execute": 1,
                "today.reversal_api.execute": 1,
                "market_thesis.validation_api.execute": 1,
                "options.options_flow_api.execute": 1,
                "radar.oversold_api.execute": 1,
                "today.ranked_candidates.execute": 1,
                "today.scored_candidates.execute": 1,
                "today.validation.execute": 2,
                "trade_state.build.execute": 1,
            }
        ),
        "trade-state": _counter_contract(
            {"trade_state.build.execute": 1, "trade_state.load.attempt": 1}
        ),
        "us-screener": _counter_contract(
            {
                "screener.scored_candidates.execute": 1,
                "shared.json.read": 3,
                "shared.ledger.execute": 1,
            }
        ),
        "options-flow": _counter_contract(
            {"options_flow.load.execute": 1},
            {"provider.options_flow.live_chain.attempt"},
        ),
        "stock-checkup": _counter_contract(
            {
                "fundamentals.load.execute": 2,
                "options.live_provider.execute": 2,
                "options.money_flow_api.execute": 1,
                "sector.rotation_api.execute": 1,
                "sector.ticker.execute": 2,
                "shared.reconciliation.execute": 1,
                "stock.live_factor_flags.execute": 1,
                "stock.score_surge.execute": 1,
                "trade_state.build.execute": 1,
            }
        ),
        "options-cockpit": _counter_contract(
            {
                "options.live_provider.execute": 1,
                "options.money_flow_api.execute": 1,
                "options.options_flow_api.execute": 1,
                "options.social_api.execute": 1,
                "shared.json.read": 2,
                "shared.reconciliation.execute": 1,
                "today.scored_candidates.execute": 1,
                "trade_state.build.execute": 1,
            }
        ),
        "radar": _counter_contract(
            {"radar.oversold_api.execute": 1, "risk_guard.source.read": 1},
            {"provider.radar.risk_scan.attempt", "provider.radar.reversal_scan.attempt"},
        ),
        "ibkr-reconcile": _counter_contract(
            {
                "ibkr.available.read": 1,
                "shared.reconciliation.execute": 1,
            }
        ),
        "sector-rotation": _counter_contract(
            {
                "sector.rotation_api.execute": 1,
                "sector.theme_drill_api.execute": 1,
                "sector.ticker.execute": 1,
                "shared.json.read": 1,
                "today.scored_candidates.execute": 1,
            },
        ),
        "theme-flow": _counter_contract(
            {
                "theme_flow.ai_payload.read": 1,
                "theme_flow.controls.read": 2,
                "theme_flow.insider.read": 1,
                "theme_flow.parent_quadrants.read": 1,
                "theme_flow.snapshot.read": 1,
                "theme_flow.snapshot_stale.read": 1,
                "theme_flow.status.ai_read.read": 1,
                "theme_flow.status.refresh_board.read": 2,
            }
        ),
        "us-cot": _counter_contract(
            {"cot.catalog.execute": 1, "cot.detail.execute": 1}
        ),
        "market-thesis": _counter_contract(
            {
                "market_thesis.latest_api.execute": 1,
                "market_thesis.regime_api.execute": 1,
                "market_thesis.validation_api.execute": 1,
            }
        ),
        "us-x": _counter_contract(
            {
                "x.agent_reach_config.read": 1,
                "x.analysis_status.read": 1,
                "x.roster.read": 1,
                "x.source_statuses.read": 2,
            }
        ),
        "retro-analysis": _counter_contract(
            {"retro_analysis.artifact.read": 6}
        ),
        "analytics-db": _counter_contract(
            {
                "analytics.catalog.read": 1,
                "analytics.checks.read": 1,
                "analytics.columns.read": 1,
                "analytics.root.read": 1,
                "analytics.status.read": 2,
                "analytics.table.read": 3,
                "analytics.tickers.read": 2,
                "today.ranked_candidates.execute": 1,
            }
        ),
        "knowledge-graph": _counter_contract(
            {"knowledge_graph.load.execute": 1}
        ),
        "us-options": _counter_contract(
            {
                "shared.json.read": 1,
                "today.scored_candidates.execute": 1,
            },
            {"provider.us_options.live.attempt"},
        ),
        "analyst-views": _counter_contract(
            {
                "provider.analyst_views.execute": 2,
                "today.scored_candidates.execute": 1,
            },
        ),
        "institutions": _counter_contract(
            {
                "institutions.stock.load.execute": 1,
                "today.scored_candidates.execute": 1,
            },
            {"institutions.catalog.execute", "institutions.portfolio.load.execute"},
        ),
        "industry-roles": _counter_contract(
            {
                "industry_roles.state.read": 1,
            }
        ),
        "watchlist-categorize": _counter_contract(
            {
                "ibkr.available.read": 1,
                "shared.json.read": 1,
                "shared.reconciliation.execute": 1,
            },
            {"watchlist.sectors.read"},
        ),
        "influencers": _counter_contract(
            {"influencers.roster.read": 1}
        ),
        "schedules": _counter_contract(
            {
                "schedules.load.execute": 1,
                "schedules.result.report_dir.execute": 1,
            }
        ),
        "ai-updates": _counter_contract({"ai_updates.load.execute": 1}),
        "crypto-universe": _counter_contract({"crypto_universe.load.execute": 1}),
        "crypto-screener": _counter_contract({"shared.json.read": 1}),
        "crypto-x": _counter_contract(
            {
                "x.agent_reach_config.read": 1,
                "x.analysis_status.read": 1,
                "x.roster.read": 1,
                "x.source_statuses.read": 2,
            }
        ),
    }
)

SELECTION_RENDER_CALLABLES: Mapping[str, str] = MappingProxyType(
    {name: item.callable_name for name, item in SELECTION_CASES.items()}
)
SELECTION_OWNED_PATHS: Mapping[str, Mapping[str, str]] = MappingProxyType(
    {
        name: _SELECTION_REGISTRY_OWNED_PATHS[item.registry_key]
        for name, item in SELECTION_CASES.items()
    }
)

_ai_selection_counts = dict(ROUTE_COUNTER_CONTRACTS["today-decision"]["positive"])
_ai_selection_counts["session.setup"] = 1
for _counter_name in tuple(_ai_selection_counts):
    if _counter_name != "session.setup":
        _ai_selection_counts[_counter_name] *= 5

_analytics_selection_counts = dict(
    ROUTE_COUNTER_CONTRACTS["analytics-db"]["positive"]
)
_analytics_selection_counts["session.setup"] = 1
for _counter_name in tuple(_analytics_selection_counts):
    if _counter_name != "session.setup":
        _analytics_selection_counts[_counter_name] *= 3

SELECTION_COUNTER_CONTRACTS: Mapping[str, Mapping[str, Any]] = MappingProxyType(
    {
        "risk-guard-controls": _counter_contract(
            {
                "risk_guard.snapshot.read": 1,
                "risk_guard.source.read": 1,
            }
        ),
        "institutions-controls": _counter_contract(
            {
                "page.render.attempt": 2,
                "institutions.stock.load.execute": 1,
                "institutions.catalog.execute": 1,
                "institutions.portfolio.load.execute": 1,
                "today.scored_candidates.execute": 1,
            }
        ),
        "options-cockpit-controls": ROUTE_COUNTER_CONTRACTS["options-cockpit"],
        "radar-controls": ROUTE_COUNTER_CONTRACTS["radar"],
        "knowledge-graph-controls": ROUTE_COUNTER_CONTRACTS["knowledge-graph"],
        "ai-chat-settings-controls": _counter_contract(_ai_selection_counts),
        "retro-controls": ROUTE_COUNTER_CONTRACTS["retro-analysis"],
        "analytics-controls": _counter_contract(_analytics_selection_counts),
        "stock-checkup-controls": ROUTE_COUNTER_CONTRACTS["stock-checkup"],
    }
)
del _ai_selection_counts
del _analytics_selection_counts

_REPO_ROOT = Path(__file__).resolve().parent.parent
_APPROVED_REPOSITORY_OUTPUT_ROOT = (
    _REPO_ROOT / ".claude" / "ui_snapshots"
).resolve()
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
_CAPTURE_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}(?:/[A-Za-z0-9][A-Za-z0-9._-]{0,95})?$"
)
_COUNTER_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_CAPTURE_STATE_KEY = "_quant_radar_ux0_capture"
_ROUTE_STATE_KEY = "_quant_radar_ux0_route"
_NAV_SENTINEL = "_quant_radar_ux0_navigation_state"
_WRAPPER_MARKER = "_quant_radar_ux0_fixture_wrapper"


class FixtureConfigurationError(RuntimeError):
    """Raised when the fixture environment is not explicitly runner-owned."""


class BlockedExternalNetworkError(RuntimeError):
    """Raised before a non-loopback DNS or socket operation can execute."""


class BlockedProductionArtifactError(RuntimeError):
    """Raised before fixture code can touch a production runtime artifact."""


class BlockedFixtureMutationError(RuntimeError):
    """Raised before a subprocess, browser, login, or writer can execute."""


@dataclass(frozen=True, slots=True)
class FixtureEnvironment:
    fixture_root: Path
    calls_path: Path
    run_dir: Path
    run_token: str
    fixed_now: str
    source_root: Path | None = None
    profile: str | None = None
    phase: str | None = None
    streamlit_port: int | None = None
    deny_proxy_port: int | None = None


@dataclass(slots=True)
class _PatchRecord:
    module: Any
    attribute: str
    original: Any
    replacement: Any
    factory: Callable[[Any], Any]


_ACTIVE_ENVIRONMENT: FixtureEnvironment | None = None
_COUNTER_LOCK = threading.RLock()
_CAPTURE_LOCAL = threading.local()
_PATCH_LOCK = threading.RLock()
_PATCH_RECORDS: dict[tuple[str, str], _PatchRecord] = {}
_PROVIDER_CONTEXT_DEPTH = 0


def _configuration_error(message: str) -> FixtureConfigurationError:
    return FixtureConfigurationError(f"UX-0 fixture configuration error: {message}")


def _hide_security_wrapper_target(value: Any) -> Any:
    """Keep wrapper metadata without exporting functools' bypass handle."""

    try:
        delattr(value, "__wrapped__")
    except AttributeError:
        pass
    return value


def _required(environ: Mapping[str, str], name: str) -> str:
    value = str(environ.get(name) or "")
    if not value:
        raise _configuration_error(f"missing {name}")
    return value


def _parse_token(raw: str) -> str:
    if _TOKEN_RE.fullmatch(raw) is None:
        raise _configuration_error("run token must be a 256-bit URL-safe value")
    try:
        decoded = base64.b64decode(raw + "=", altchars=b"-_", validate=True)
    except (ValueError, TypeError) as exc:
        raise _configuration_error("run token is not valid URL-safe base64") from exc
    if len(decoded) != 32:
        raise _configuration_error("run token must decode to 256 bits")
    return raw


def _validated_ux1b_profile_phase(profile: str, phase: str) -> tuple[str, str]:
    normalized_profile = str(profile or "").strip()
    normalized_phase = str(phase or "").strip()
    phases = UX1B_PROFILE_PHASES.get(normalized_profile)
    if phases is None:
        raise _configuration_error("unsupported UX-1B fixture profile")
    if normalized_phase not in phases:
        raise _configuration_error(
            f"UX-1B phase is incompatible with {normalized_profile}"
        )
    return normalized_profile, normalized_phase


def _validated_ux1b_ports(streamlit_port: Any, deny_proxy_port: Any) -> tuple[int, int]:
    try:
        app_port = int(streamlit_port)
        proxy_port = int(deny_proxy_port)
    except (TypeError, ValueError) as exc:
        raise _configuration_error("UX-1B ports must be decimal integers") from exc
    if any(port < 1024 or port > 65535 for port in (app_port, proxy_port)):
        raise _configuration_error("UX-1B ports must be in the unprivileged TCP range")
    if app_port == proxy_port or 8000 in {app_port, proxy_port}:
        raise _configuration_error(
            "UX-1B ports must be distinct and must not use the API port"
        )
    return app_port, proxy_port


def build_owned_run_contract(
    *,
    run_token: str,
    profile: str,
    phase: str,
    streamlit_port: int,
    deny_proxy_port: int,
) -> dict[str, Any]:
    """Return the exact file payload consumed by the sandboxed app child."""

    token = _parse_token(run_token)
    selected_profile, selected_phase = _validated_ux1b_profile_phase(profile, phase)
    app_port, proxy_port = _validated_ux1b_ports(
        streamlit_port, deny_proxy_port
    )
    return {
        "schemaVersion": UX1B_RUN_CONTRACT_SCHEMA,
        "profile": selected_profile,
        "phase": selected_phase,
        "streamlitPort": app_port,
        "denyProxyPort": proxy_port,
        "runToken": token,
        "fixedNow": FIXED_NOW,
    }


def _absolute_path(environ: Mapping[str, str], name: str) -> Path:
    raw = Path(_required(environ, name)).expanduser()
    if not raw.is_absolute():
        raise _configuration_error(f"{name} must be absolute")
    return raw.resolve()


def _parse_ux1b_profile(
    source: Mapping[str, str],
) -> tuple[str | None, str | None, int | None, int | None]:
    names = (
        "QUANT_RADAR_UX1B_PROFILE",
        "QUANT_RADAR_UX1B_PHASE",
        "QUANT_RADAR_UX1B_STREAMLIT_PORT",
        "QUANT_RADAR_UX1B_DENY_PROXY_PORT",
    )
    raw = {name: str(source.get(name) or "").strip() for name in names}
    if not any(raw.values()):
        return None, None, None, None
    if not all(raw.values()):
        missing = next(name for name in names if not raw[name])
        raise _configuration_error(f"missing {missing}")
    profile, phase = _validated_ux1b_profile_phase(
        raw["QUANT_RADAR_UX1B_PROFILE"], raw["QUANT_RADAR_UX1B_PHASE"]
    )
    streamlit_port, deny_proxy_port = _validated_ux1b_ports(
        raw["QUANT_RADAR_UX1B_STREAMLIT_PORT"],
        raw["QUANT_RADAR_UX1B_DENY_PROXY_PORT"],
    )
    return profile, phase, streamlit_port, deny_proxy_port


def _read_owned_run_contract(path: Path) -> dict[str, Any]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = -1
    try:
        named = os.lstat(path)
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (
            stat.S_ISLNK(named.st_mode)
            or not stat.S_ISREG(named.st_mode)
            or not stat.S_ISREG(opened.st_mode)
            or (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
            or opened.st_uid != os.getuid()
            or opened.st_nlink != 1
            or stat.S_IMODE(opened.st_mode) != 0o600
            or opened.st_size <= 0
            or opened.st_size > _MAX_RUN_CONTRACT_BYTES
        ):
            raise _configuration_error("owned app run contract identity is invalid")
        chunks: list[bytes] = []
        remaining = opened.st_size
        while remaining:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if remaining or len(payload) != opened.st_size:
            raise _configuration_error("owned app run contract changed while reading")
    except FixtureConfigurationError:
        raise
    except OSError as exc:
        raise _configuration_error("owned app run contract is unavailable") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    try:
        value = json.loads(
            payload.decode("utf-8", errors="strict"),
            object_pairs_hook=reject_duplicates,
        )
    except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise _configuration_error("owned app run contract is malformed") from exc
    expected_keys = {
        "schemaVersion",
        "profile",
        "phase",
        "streamlitPort",
        "denyProxyPort",
        "runToken",
        "fixedNow",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise _configuration_error("owned app run contract has an invalid shape")
    return value


def _owned_app_fixture_environment(source: Mapping[str, str]) -> FixtureEnvironment:
    legacy_authorities = tuple(
        key
        for key in source
        if key.startswith("QUANT_RADAR_UX0_")
        or key in {
            "QUANT_RADAR_UX1B_PROFILE",
            "QUANT_RADAR_UX1B_PHASE",
            "QUANT_RADAR_UX1B_STREAMLIT_PORT",
            "QUANT_RADAR_UX1B_DENY_PROXY_PORT",
        }
    )
    if legacy_authorities:
        raise _configuration_error(
            "owned app contract cannot be combined with legacy environment authority"
        )
    if source.get("QUANT_RADAR_UX1B_ROLE") != "app":
        raise _configuration_error("owned fixture contract requires the app role")
    if source.get("TZ") != "UTC":
        raise _configuration_error("TZ must be UTC")
    home = _absolute_path(source, "HOME")
    source_root = _absolute_path(source, "SOURCE_ROOT")
    if home.name != "home":
        raise _configuration_error("owned app HOME must identify its fixed home directory")
    run_dir = home.parent
    fixture_root = run_dir / "fixture-root"
    calls_path = run_dir / "fixture-calls.json"
    contract_path = home / UX1B_RUN_CONTRACT_FILENAME
    contract = _read_owned_run_contract(contract_path)
    if contract.get("schemaVersion") != UX1B_RUN_CONTRACT_SCHEMA:
        raise _configuration_error("owned app run contract schema is incompatible")
    profile, phase = _validated_ux1b_profile_phase(
        contract.get("profile"), contract.get("phase")
    )
    streamlit_port, deny_proxy_port = _validated_ux1b_ports(
        contract.get("streamlitPort"), contract.get("denyProxyPort")
    )
    run_token = _parse_token(str(contract.get("runToken") or ""))
    if contract.get("fixedNow") != FIXED_NOW:
        raise _configuration_error(f"fixed clock must be {FIXED_NOW}")
    for path, label, exact_mode in (
        (run_dir, "owned app root", 0o700),
        (home, "owned app HOME", 0o700),
        (fixture_root, "fixture root", 0o700),
        (source_root, "source root", None),
    ):
        try:
            named = os.lstat(path)
        except OSError as exc:
            raise _configuration_error(f"{label} is unavailable") from exc
        if (
            stat.S_ISLNK(named.st_mode)
            or not stat.S_ISDIR(named.st_mode)
            or named.st_uid != os.getuid()
            or (exact_mode is not None and stat.S_IMODE(named.st_mode) != exact_mode)
        ):
            raise _configuration_error(f"{label} must be a real directory")
    if source_root == run_dir or source_root in run_dir.parents or run_dir in source_root.parents:
        raise _configuration_error("owned app source and writable roots overlap")
    if source_root != _REPO_ROOT:
        raise _configuration_error("SOURCE_ROOT differs from the executing fixture mirror")
    if calls_path.exists() and (calls_path.is_symlink() or not calls_path.is_file()):
        raise _configuration_error("call output must be a regular file or not yet exist")
    marker = run_dir / OWNERSHIP_MARKER
    if not marker.is_file() or marker.is_symlink():
        raise _configuration_error("runner ownership marker is missing or invalid")
    try:
        marker_value = marker.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise _configuration_error("runner ownership marker is unreadable") from exc
    if len(marker_value) > 128 or not hmac.compare_digest(marker_value, run_token):
        raise _configuration_error("runner ownership marker does not match this invocation")
    return FixtureEnvironment(
        fixture_root=fixture_root,
        calls_path=calls_path,
        run_dir=run_dir,
        run_token=run_token,
        fixed_now=FIXED_NOW,
        source_root=source_root,
        profile=profile,
        phase=phase,
        streamlit_port=streamlit_port,
        deny_proxy_port=deny_proxy_port,
    )


def validate_fixture_environment(
    environ: Mapping[str, str] | None = None,
) -> FixtureEnvironment:
    """Parse and authenticate the exact runner-owned fixture environment."""

    source = os.environ if environ is None else environ
    if source.get("QUANT_RADAR_UX1B_ROLE") or source.get("SOURCE_ROOT"):
        return _owned_app_fixture_environment(source)
    if source.get("QUANT_RADAR_UX0_FIXTURES") != "1":
        raise _configuration_error("explicit fixture opt-in is required")

    fixture_root = _absolute_path(source, "QUANT_RADAR_UX0_FIXTURE_ROOT")
    calls_path = _absolute_path(source, "QUANT_RADAR_UX0_CALLS_PATH")
    run_token = _parse_token(_required(source, "QUANT_RADAR_UX0_RUN_TOKEN"))
    fixed_now = _required(source, "QUANT_RADAR_UX0_FIXED_NOW")
    if fixed_now != FIXED_NOW:
        raise _configuration_error(f"fixed clock must be {FIXED_NOW}")
    if source.get("TZ") != "UTC":
        raise _configuration_error("TZ must be UTC")
    profile, phase, streamlit_port, deny_proxy_port = _parse_ux1b_profile(source)

    if not fixture_root.is_dir():
        raise _configuration_error("fixture root must already exist as a directory")
    if Path(_required(source, "QUANT_RADAR_UX0_FIXTURE_ROOT")).is_symlink():
        raise _configuration_error("fixture root must not be a symlink")
    if calls_path.exists() and (calls_path.is_symlink() or not calls_path.is_file()):
        raise _configuration_error("call output must be a regular file or not yet exist")

    run_dir = fixture_root.parent
    if calls_path.parent != run_dir:
        raise _configuration_error("fixture root and call output must share one owned run directory")
    if calls_path.name != "fixture-calls.json":
        raise _configuration_error("call output filename must be fixture-calls.json")
    if run_dir == _REPO_ROOT or _REPO_ROOT in run_dir.parents:
        approved = (
            run_dir == _APPROVED_REPOSITORY_OUTPUT_ROOT
            or _APPROVED_REPOSITORY_OUTPUT_ROOT in run_dir.parents
        )
        if not approved:
            raise _configuration_error(
                "fixture directories must not resolve inside a repository source directory"
            )

    expected_paths = {
        "SURGE_RUNTIME_DIR": fixture_root,
        "SURGE_CANDIDATE_OUTPUT_DIR": fixture_root / "candidates",
        "SURGE_AI_CHAT_DIR": fixture_root / "ai-chat",
    }
    if profile in UX1B_PROFILE_PHASES:
        expected_paths["SURGE_ANALYTICS_DIR"] = fixture_root / "analytics"
    for name, expected in expected_paths.items():
        actual = _absolute_path(source, name)
        if actual != expected:
            raise _configuration_error(f"{name} must remain under the owned fixture root")
    if profile in UX1B_PROFILE_PHASES:
        expected_proxy = f"http://127.0.0.1:{deny_proxy_port}"
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
            if source.get(name) != expected_proxy:
                raise _configuration_error(f"{name} must use the owned deny proxy")

    marker = run_dir / OWNERSHIP_MARKER
    if not marker.is_file() or marker.is_symlink():
        raise _configuration_error("runner ownership marker is missing or invalid")
    try:
        marker_value = marker.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise _configuration_error("runner ownership marker is unreadable") from exc
    if len(marker_value) > 128 or not hmac.compare_digest(marker_value, run_token):
        raise _configuration_error("runner ownership marker does not match this invocation")

    return FixtureEnvironment(
        fixture_root=fixture_root,
        calls_path=calls_path,
        run_dir=run_dir,
        run_token=run_token,
        fixed_now=fixed_now,
        source_root=None,
        profile=profile,
        phase=phase,
        streamlit_port=streamlit_port,
        deny_proxy_port=deny_proxy_port,
    )


def _fixture_revision(environment: FixtureEnvironment) -> str:
    if environment.profile in UX1B_PROFILE_PHASES:
        return UX1B_FIXTURE_REVISION
    return FIXTURE_REVISION


def _empty_counter_document(environment: FixtureEnvironment) -> dict[str, Any]:
    document = {
        "schemaVersion": COUNTER_SCHEMA_VERSION,
        "fixtureRevision": _fixture_revision(environment),
        "captures": {},
        "bootstrapBlockedNetwork": [],
    }
    if environment.profile in UX1B_PROFILE_PHASES:
        document["contractSchema"] = UX1B_CONTRACT_SCHEMA_VERSION
    return document


def _validate_counter_document(
    value: Any,
    environment: FixtureEnvironment,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _configuration_error("fixture counter document must be an object")
    if value.get("schemaVersion") != COUNTER_SCHEMA_VERSION:
        raise _configuration_error("fixture counter schema is incompatible")
    if value.get("fixtureRevision") != _fixture_revision(environment):
        raise _configuration_error("fixture counter revision is incompatible")
    if environment.profile in UX1B_PROFILE_PHASES:
        if value.get("contractSchema") != UX1B_CONTRACT_SCHEMA_VERSION:
            raise _configuration_error("UX-1B fixture contract schema is incompatible")
    elif "contractSchema" in value:
        raise _configuration_error(
            "legacy fixture counter must not declare a UX-1B contract schema"
        )
    captures = value.get("captures")
    blocked = value.get("bootstrapBlockedNetwork")
    if not isinstance(captures, dict) or not isinstance(blocked, list):
        raise _configuration_error("fixture counter document has an invalid shape")
    for capture_id, bucket in captures.items():
        _validate_capture_id(str(capture_id))
        if not isinstance(bucket, dict):
            raise _configuration_error("fixture capture bucket must be an object")
        counts = bucket.get("counts")
        records = bucket.get("blockedNetwork")
        if not isinstance(counts, dict) or not isinstance(records, list):
            raise _configuration_error("fixture capture bucket has an invalid shape")
        if any(
            _COUNTER_RE.fullmatch(str(name)) is None
            or not isinstance(count, int)
            or isinstance(count, bool)
            or count < 0
            for name, count in counts.items()
        ):
            raise _configuration_error("fixture counter contains an invalid count")
        identity = bucket.get("identity")
        if identity is not None:
            if not isinstance(identity, dict):
                raise _configuration_error("fixture capture identity must be an object")
            selected = identity.get("selectedRegistryKey")
            real_callable = identity.get("realCallable")
            resolved = identity.get("resolvedOwnedPaths")
            if selected not in _SELECTION_REGISTRY_CALLABLES:
                raise _configuration_error("fixture capture identity has an unknown route")
            if real_callable != _SELECTION_REGISTRY_CALLABLES[selected]:
                raise _configuration_error("fixture capture identity has the wrong callable")
            if not isinstance(resolved, dict) or set(resolved) != set(
                _SELECTION_REGISTRY_OWNED_PATHS[selected]
            ):
                raise _configuration_error("fixture capture identity has invalid owned paths")
            if any(not isinstance(path, str) or not Path(path).is_absolute() for path in resolved.values()):
                raise _configuration_error("fixture owned paths must be absolute")
    return value


def _read_counter_document(environment: FixtureEnvironment) -> dict[str, Any]:
    if not environment.calls_path.exists():
        return _empty_counter_document(environment)
    try:
        value = json.loads(environment.calls_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise _configuration_error("fixture counter document is unreadable or malformed") from exc
    return _validate_counter_document(value, environment)


def _atomic_write_counter(
    environment: FixtureEnvironment,
    document: dict[str, Any],
) -> None:
    payload = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    suffix = f"{os.getpid()}-{threading.get_ident()}-{time.monotonic_ns()}"
    temporary = environment.calls_path.with_name(
        f".{environment.calls_path.name}.{suffix}.tmp"
    )
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            os.chmod(temporary, 0o600)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(environment.calls_path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _configure_environment(environment: FixtureEnvironment) -> None:
    global _ACTIVE_ENVIRONMENT
    with _COUNTER_LOCK:
        if _ACTIVE_ENVIRONMENT is not None and _ACTIVE_ENVIRONMENT != environment:
            raise _configuration_error("fixture environment changed inside one process")
        _ACTIVE_ENVIRONMENT = environment
        if not environment.calls_path.exists():
            _atomic_write_counter(environment, _empty_counter_document(environment))
        else:
            _read_counter_document(environment)


def current_environment() -> FixtureEnvironment:
    environment = _ACTIVE_ENVIRONMENT
    if environment is None:
        raise _configuration_error("fixture bootstrap has not completed")
    return environment


def _validate_capture_id(capture_id: str) -> str:
    value = str(capture_id or "")
    if _CAPTURE_RE.fullmatch(value) is None:
        raise _configuration_error("ux0_capture is missing or invalid")
    return value


def _capture_bucket(document: dict[str, Any], capture_id: str) -> dict[str, Any]:
    captures = document["captures"]
    bucket = captures.setdefault(capture_id, {"counts": {}, "blockedNetwork": []})
    return bucket


def _active_capture_id() -> str | None:
    local = getattr(_CAPTURE_LOCAL, "capture_id", None)
    if isinstance(local, str) and local:
        return local
    try:
        import streamlit as st  # lazy: never imported during stdlib bootstrap

        value = st.session_state.get(_CAPTURE_STATE_KEY)
    except Exception:
        return None
    return value if isinstance(value, str) and _CAPTURE_RE.fullmatch(value) else None


@contextmanager
def capture_context(capture_id: str) -> Iterator[str]:
    """Attribute provider and guard activity to one Streamlit capture thread."""

    validated = _validate_capture_id(capture_id)
    previous = getattr(_CAPTURE_LOCAL, "capture_id", None)
    _CAPTURE_LOCAL.capture_id = validated
    try:
        yield validated
    finally:
        if previous is None:
            try:
                del _CAPTURE_LOCAL.capture_id
            except AttributeError:
                pass
        else:
            _CAPTURE_LOCAL.capture_id = previous


def increment_counter(
    name: str,
    *,
    capture_id: str | None = None,
    amount: int = 1,
) -> int:
    """Increment one named per-capture boundary counter atomically."""

    if _COUNTER_RE.fullmatch(str(name)) is None:
        raise ValueError("invalid fixture counter name")
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        raise ValueError("counter amount must be a positive integer")
    resolved_capture = _validate_capture_id(capture_id or _active_capture_id() or "unscoped")
    environment = current_environment()
    with _COUNTER_LOCK:
        document = _read_counter_document(environment)
        counts = _capture_bucket(document, resolved_capture)["counts"]
        counts[name] = int(counts.get(name, 0)) + amount
        _atomic_write_counter(environment, document)
        return counts[name]


def counter_snapshot(capture_id: str) -> dict[str, Any]:
    """Return a detached snapshot of one capture bucket."""

    resolved = _validate_capture_id(capture_id)
    environment = current_environment()
    with _COUNTER_LOCK:
        document = _read_counter_document(environment)
        bucket = document["captures"].get(
            resolved,
            {"counts": {}, "blockedNetwork": []},
        )
        return copy.deepcopy(bucket)


def _resolved_owned_paths(route: str) -> dict[str, str]:
    environment = current_environment()
    resolved: dict[str, str] = {}
    try:
        contract = _SELECTION_REGISTRY_OWNED_PATHS[route]
    except KeyError as exc:
        raise _configuration_error("selected page has no owned-path contract") from exc
    for name, relative in contract.items():
        path = (environment.fixture_root / relative).resolve(strict=False)
        if not _path_is_within(path, environment.fixture_root):
            raise _configuration_error("route owned path escaped the fixture root")
        resolved[name] = str(path)
    return resolved


def _runtime_callable_identity(callable_value: Any) -> str:
    if not callable(callable_value):
        raise _configuration_error("selected page does not hold a callable")
    module = str(getattr(callable_value, "__module__", "") or "")
    qualname = str(getattr(callable_value, "__qualname__", "") or "")
    if not qualname or "<" in qualname or ">" in qualname:
        raise _configuration_error("selected page callable has no stable qualname")
    if module.startswith("ui."):
        return f"{module.rsplit('.', 1)[-1]}.{qualname}"
    if module in {"__main__", "app", "__quant_radar_real_app__"} and qualname in {
        "us_x",
        "crypto_x",
    }:
        return qualname
    return f"{module}.{qualname}" if module else qualname


def _validated_runtime_callable(route: str, callable_value: Any) -> str:
    measured = _runtime_callable_identity(callable_value)
    expected = ROUTE_RENDER_CALLABLES[route]
    if measured != expected:
        raise _configuration_error(
            f"selected page callable mismatch for {route}: expected {expected}, got {measured}"
        )
    return measured


def _streamlit_page_callable(page: Any) -> Any:
    # Streamlit 1.57 stores the actual callable supplied to st.Page on `_page`.
    # There is no public callable accessor.  Fail closed on a version/shape
    # change instead of falling back to the declared fixture contract.
    if not hasattr(page, "_page"):
        raise _configuration_error("selected Streamlit Page exposes no runtime callable")
    return getattr(page, "_page")


def _set_capture_identity(
    route: str,
    capture_id: str,
    real_callable: str,
) -> None:
    environment = current_environment()
    try:
        expected_callable = _SELECTION_REGISTRY_CALLABLES[route]
    except KeyError as exc:
        raise _configuration_error("capture route is outside the fixture contract") from exc
    if real_callable != expected_callable:
        raise _configuration_error("capture callable differs from the frozen route contract")
    identity = {
        "selectedRegistryKey": route,
        "realCallable": real_callable,
        "resolvedOwnedPaths": _resolved_owned_paths(route),
    }
    with _COUNTER_LOCK:
        document = _read_counter_document(environment)
        bucket = _capture_bucket(document, capture_id)
        existing = bucket.get("identity")
        if existing is not None and existing != identity:
            raise _configuration_error("capture identity changed during one session")
        bucket["identity"] = identity
        _atomic_write_counter(environment, document)


def assert_counter_contract(route: str, capture_id: str) -> dict[str, Any]:
    """Fail closed unless one capture exactly matches its declared call map."""

    normalized = str(route or "").strip("/") or "today-decision"
    if normalized not in ROUTE_COUNTER_CONTRACTS:
        raise _configuration_error("selected page has no counter contract")
    snapshot = counter_snapshot(capture_id)
    expected = ROUTE_COUNTER_CONTRACTS[normalized]
    counts = snapshot.get("counts") or {}
    positive = dict(expected["positive"])
    zero = set(expected["zero"])
    mismatches = {
        name: {"expected": count, "actual": int(counts.get(name, 0))}
        for name, count in positive.items()
        if int(counts.get(name, 0)) != count
    }
    mismatches.update(
        {
            name: {"expected": 0, "actual": int(counts.get(name, 0))}
            for name in zero
            if int(counts.get(name, 0)) != 0
        }
    )
    declared = set(positive) | zero
    undeclared = {name: count for name, count in counts.items() if name not in declared}
    if mismatches or undeclared:
        raise AssertionError(
            f"UX-1B fixture counter contract mismatch route={normalized} "
            f"mismatches={mismatches} undeclared={undeclared}"
        )
    expected_identity = {
        "selectedRegistryKey": normalized,
        "realCallable": ROUTE_RENDER_CALLABLES[normalized],
        "resolvedOwnedPaths": _resolved_owned_paths(normalized),
    }
    if snapshot.get("identity") != expected_identity:
        raise AssertionError("UX-1B fixture capture identity mismatch")
    if snapshot.get("blockedNetwork") != []:
        raise AssertionError("UX-1B fixture capture recorded blocked network attempts")
    return snapshot


def assert_selection_counter_contract(
    case_name: str,
    capture_id: str,
) -> dict[str, Any]:
    """Fail closed unless a focused interaction matches its exact call map."""

    try:
        definition = SELECTION_CASES[str(case_name)]
        expected = SELECTION_COUNTER_CONTRACTS[str(case_name)]
    except KeyError as exc:
        raise _configuration_error("selection case has no counter contract") from exc
    snapshot = counter_snapshot(capture_id)
    counts = snapshot.get("counts") or {}
    positive = dict(expected["positive"])
    zero = set(expected["zero"])
    mismatches = {
        name: {"expected": count, "actual": int(counts.get(name, 0))}
        for name, count in positive.items()
        if int(counts.get(name, 0)) != count
    }
    mismatches.update(
        {
            name: {"expected": 0, "actual": int(counts.get(name, 0))}
            for name in zero
            if int(counts.get(name, 0)) != 0
        }
    )
    declared = set(positive) | zero
    undeclared = {name: count for name, count in counts.items() if name not in declared}
    if mismatches or undeclared:
        raise AssertionError(
            f"UX-1B focused fixture counter mismatch case={case_name} "
            f"mismatches={mismatches} undeclared={undeclared}"
        )
    expected_identity = {
        "selectedRegistryKey": definition.registry_key,
        "realCallable": definition.callable_name,
        "resolvedOwnedPaths": _resolved_owned_paths(definition.registry_key),
    }
    if snapshot.get("identity") != expected_identity:
        raise AssertionError("UX-1B focused fixture capture identity mismatch")
    if snapshot.get("blockedNetwork") != []:
        raise AssertionError("UX-1B focused fixture recorded blocked network attempts")
    return snapshot


def _safe_network_target(host: Any) -> str:
    if isinstance(host, bytes):
        value = host.decode("ascii", errors="replace")
    else:
        value = str(host)
    value = value.strip().lower()
    if len(value) > 253:
        return value[:250] + "..."
    return value


def _record_blocked_network(kind: str, host: Any) -> None:
    record = {"kind": kind, "target": _safe_network_target(host)}
    environment = current_environment()
    capture_id = _active_capture_id()
    with _COUNTER_LOCK:
        document = _read_counter_document(environment)
        if capture_id is None:
            document["bootstrapBlockedNetwork"].append(record)
        else:
            _capture_bucket(document, capture_id)["blockedNetwork"].append(record)
        _atomic_write_counter(environment, document)


def _host_is_loopback(host: Any) -> bool:
    if host is None:
        return True
    if isinstance(host, bytes):
        try:
            host = host.decode("ascii")
        except UnicodeDecodeError:
            return False
    value = str(host).strip().lower().rstrip(".")
    if value in {"", "localhost", "localhost.localdomain"}:
        return True
    without_zone = value.split("%", 1)[0]
    try:
        return ipaddress.ip_address(without_zone).is_loopback
    except ValueError:
        return False


def _require_loopback(host: Any, kind: str) -> None:
    if _host_is_loopback(host):
        return
    _record_blocked_network(kind, host)
    raise BlockedExternalNetworkError(
        "UX-0 fixture blocked a non-loopback network attempt"
    )


def _network_destination_allowed(host: Any, port: Any = None) -> bool:
    environment = current_environment()
    if environment.profile not in UX1B_PROFILE_PHASES:
        return _host_is_loopback(host)
    if isinstance(host, bytes):
        try:
            host = host.decode("ascii")
        except UnicodeDecodeError:
            return False
    # UX-1B browser evidence owns exactly two IPv4 destinations.  Do not
    # broaden this to DNS aliases, the IPv6 loopback, or the 127/8 category:
    # those names/addresses can resolve or route differently across hosts.
    if host != "127.0.0.1":
        return False
    try:
        numeric_port = int(port)
    except (TypeError, ValueError):
        return False
    return numeric_port in {environment.streamlit_port, environment.deny_proxy_port}


def _network_record_target(host: Any, port: Any = None) -> str:
    safe_host = _safe_network_target(host)
    if _host_is_loopback(host) and port is not None:
        return f"{safe_host}:{port}"
    return safe_host


def install_network_guard() -> None:
    """Install an idempotent process-wide guard before Streamlit is imported."""

    sentinel_name = "_quant_radar_ux0_network_guard"
    existing = getattr(socket, sentinel_name, None)
    if isinstance(existing, dict):
        existing["recorder"] = _record_blocked_network
        reinstall = existing.get("reinstall")
        if not callable(reinstall):
            raise FixtureConfigurationError("UX-1B network guard sentinel is invalid")
        reinstall()
        return

    original_socket = socket.socket
    original_low_socket = _socket.socket
    # Capture the C functions.  `socket.getaddrinfo` is a Python wrapper that
    # calls `_socket.getaddrinfo` dynamically and would recurse after alias
    # replacement.
    original_getaddrinfo = _socket.getaddrinfo
    original_gethostbyaddr = _socket.gethostbyaddr
    original_gethostbyname = _socket.gethostbyname
    original_gethostbyname_ex = _socket.gethostbyname_ex
    original_getnameinfo = _socket.getnameinfo
    original_create_connection = socket.create_connection
    original_socketpair = getattr(_socket, "socketpair", None)
    state: dict[str, Any] = {"recorder": _record_blocked_network}

    def require(host: Any, kind: str, port: Any = None) -> None:
        if _network_destination_allowed(host, port):
            return
        recorder = state["recorder"]
        recorder(kind, _network_record_target(host, port))
        raise BlockedExternalNetworkError(
            "UX-1B fixture blocked an unapproved network attempt"
        )

    @functools.wraps(original_getaddrinfo)
    def guarded_getaddrinfo(host, *args, **kwargs):
        port = args[0] if args else kwargs.get("port")
        require(host, "dns", port)
        return original_getaddrinfo(host, *args, **kwargs)

    @functools.wraps(original_gethostbyname)
    def guarded_gethostbyname(host):
        require(host, "dns")
        return original_gethostbyname(host)

    @functools.wraps(original_gethostbyname_ex)
    def guarded_gethostbyname_ex(host):
        require(host, "dns")
        return original_gethostbyname_ex(host)

    @functools.wraps(original_gethostbyaddr)
    def guarded_gethostbyaddr(host):
        require(host, "dns_reverse")
        return original_gethostbyaddr(host)

    @functools.wraps(original_getnameinfo)
    def guarded_getnameinfo(sockaddr, *args, **kwargs):
        host = sockaddr[0] if isinstance(sockaddr, tuple) and sockaddr else sockaddr
        require(host, "dns_reverse")
        return original_getnameinfo(sockaddr, *args, **kwargs)

    @functools.wraps(original_create_connection)
    def guarded_create_connection(address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) and address else address
        port = address[1] if isinstance(address, tuple) and len(address) > 1 else None
        require(host, "connect", port)
        return original_create_connection(address, *args, **kwargs)

    class GuardedSocket(original_socket):
        def __init__(self, family=-1, type=-1, proto=-1, fileno=None):
            # `socket.socket.__init__` resolves `_socket.socket` dynamically.
            # Call the captured C constructor so replacing that public alias
            # with this guard cannot recurse.
            if fileno is None:
                if family == -1:
                    family = socket.AF_INET
                if type == -1:
                    type = socket.SOCK_STREAM
                if proto == -1:
                    proto = 0
            original_low_socket.__init__(self, family, type, proto, fileno)
            self._io_refs = 0
            self._closed = False

        def _guard_address(self, address: Any, kind: str) -> None:
            if self.family == getattr(socket, "AF_UNIX", object()):
                return
            host = address[0] if isinstance(address, tuple) and address else address
            port = address[1] if isinstance(address, tuple) and len(address) > 1 else None
            require(host, kind, port)

        def connect(self, address):
            self._guard_address(address, "connect")
            return super().connect(address)

        def connect_ex(self, address):
            self._guard_address(address, "connect")
            return super().connect_ex(address)

        def sendto(self, data, *args):
            if args:
                self._guard_address(args[-1], "sendto")
            return super().sendto(data, *args)

    GuardedSocket.__name__ = "GuardedSocket"
    if hasattr(original_socket, "sendmsg"):
        original_sendmsg = original_socket.sendmsg

        @functools.wraps(original_sendmsg)
        def guarded_sendmsg(self, buffers, *args):
            # ``address`` is the optional last positional argument.  When it is
            # omitted, a connected socket has already passed connect/connect_ex.
            if args and isinstance(args[-1], tuple):
                self._guard_address(args[-1], "sendmsg")
            return original_sendmsg(self, buffers, *args)

        setattr(GuardedSocket, "sendmsg", guarded_sendmsg)

    if original_socketpair is not None:
        @functools.wraps(original_socketpair)
        def guarded_socketpair(*args, **kwargs):
            left, right = original_socketpair(*args, **kwargs)
            return (
                GuardedSocket(fileno=left.detach()),
                GuardedSocket(fileno=right.detach()),
            )
    else:
        guarded_socketpair = None

    guarded_exports = (
        guarded_getaddrinfo,
        guarded_gethostbyaddr,
        guarded_gethostbyname,
        guarded_gethostbyname_ex,
        guarded_getnameinfo,
        guarded_create_connection,
        guarded_socketpair,
        getattr(GuardedSocket, "sendmsg", None),
    )
    for guarded_export in guarded_exports:
        if guarded_export is not None:
            _hide_security_wrapper_target(guarded_export)

    def reinstall() -> None:
        # Patch both Python's convenience module and the C extension aliases.
        # The sentinel retains only this guarded reinstaller, never a raw
        # constructor that application code could accidentally reuse.
        socket.socket = GuardedSocket
        socket.SocketType = GuardedSocket
        _socket.socket = GuardedSocket
        _socket.SocketType = GuardedSocket
        for module in (socket, _socket):
            module.getaddrinfo = guarded_getaddrinfo
            module.gethostbyaddr = guarded_gethostbyaddr
            module.gethostbyname = guarded_gethostbyname
            module.gethostbyname_ex = guarded_gethostbyname_ex
            module.getnameinfo = guarded_getnameinfo
        socket.create_connection = guarded_create_connection
        if guarded_socketpair is not None:
            _socket.socketpair = guarded_socketpair

    state["reinstall"] = reinstall
    setattr(socket, sentinel_name, state)
    setattr(_socket, sentinel_name, state)
    reinstall()


def _path_is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


_FILESYSTEM_CANONICALIZER: Callable[[Path], Path] | None = None
_FILESYSTEM_DIR_FD_RESOLVER: Callable[[int], Path] | None = None


def _directory_fd_path(fd: int) -> Path:
    """Resolve an open directory descriptor without using patched APIs."""

    resolver = _FILESYSTEM_DIR_FD_RESOLVER
    if resolver is not None:
        return resolver(fd)
    try:
        value = os.readlink(f"/proc/self/fd/{fd}")
    except OSError:
        # macOS exposes F_GETPATH (50) rather than a useful /proc/self/fd.
        try:
            import fcntl

            value = fcntl.fcntl(fd, 50, bytes(1024)).split(b"\0", 1)[0]
        except (ImportError, OSError, TypeError, ValueError) as exc:
            raise FixtureConfigurationError(
                "UX-1B fixture could not authenticate a directory descriptor"
            ) from exc
    return Path(os.fsdecode(value))


def _canonical_io_path(path: Path) -> Path:
    """Resolve symlinks with captured originals so the guard cannot recurse."""

    canonicalizer = _FILESYSTEM_CANONICALIZER
    if canonicalizer is not None:
        return canonicalizer(path)
    return _canonical_io_path_with(path, os.lstat, os.readlink)


def _canonical_io_path_with(
    path: Path,
    lstat_function: Callable[..., os.stat_result],
    readlink_function: Callable[..., str | bytes],
) -> Path:
    pending = list(path.parts[1:])
    resolved = Path(path.anchor)
    followed = 0
    while pending:
        part = pending.pop(0)
        candidate = resolved / part
        try:
            info = lstat_function(candidate)
        except (FileNotFoundError, NotADirectoryError):
            return Path(os.path.normpath(os.fspath(candidate.joinpath(*pending))))
        if not stat.S_ISLNK(info.st_mode):
            resolved = candidate
            continue
        followed += 1
        if followed > 40:
            raise FixtureConfigurationError(
                "UX-1B fixture rejected an indeterminate symlink chain"
            )
        target = Path(os.fsdecode(readlink_function(candidate)))
        if target.is_absolute():
            resolved = Path(target.anchor)
            pending = list(target.parts[1:]) + pending
        else:
            pending = list(target.parts) + pending
    return Path(os.path.normpath(os.fspath(resolved)))


def _resolved_io_path(
    value: Any,
    *,
    dir_fd: int | None = None,
    fd_is_path: bool = False,
) -> Path | None:
    if isinstance(value, int):
        if not fd_is_path:
            return None
        try:
            path = _directory_fd_path(value)
        except FixtureConfigurationError:
            # Socket/pipe descriptors do not name filesystem paths.
            return None
        return _canonical_io_path(path)
    try:
        path = Path(os.fspath(value)).expanduser()
    except (TypeError, ValueError):
        return None
    if not path.is_absolute():
        base = _directory_fd_path(dir_fd) if dir_fd is not None else Path.cwd()
        path = base / path
    return _canonical_io_path(Path(os.path.abspath(os.fspath(path))))


def _guard_production_artifact(
    path_value: Any,
    *,
    write: bool,
    dir_fd: int | None = None,
    fd_is_path: bool = False,
) -> None:
    path = _resolved_io_path(path_value, dir_fd=dir_fd, fd_is_path=fd_is_path)
    if path is None:
        return
    environment = current_environment()
    if _path_is_within(path, environment.run_dir):
        if (
            write
            and _path_is_within(path, environment.fixture_root)
            and isinstance(getattr(_CAPTURE_LOCAL, "capture_id", None), str)
        ):
            increment_counter("mutator.runtime_write.attempt")
            raise BlockedFixtureMutationError(
                "UX-1B fixture blocked a capture-time runtime write"
            )
        return
    production_roots = (
        _REPO_ROOT / "content",
        _REPO_ROOT / "data",
        _REPO_ROOT / "knowledge",
        _REPO_ROOT / "reports",
    )
    production_root_files = {
        _canonical_io_path(_REPO_ROOT / name)
        for name in PRODUCTION_ROOT_CANDIDATE_ARTIFACTS
    }
    if path not in production_root_files and not any(
        _path_is_within(path, _canonical_io_path(root)) for root in production_roots
    ):
        return
    counter = (
        "mutator.production_write.attempt"
        if write
        else "mutator.production_read.attempt"
    )
    increment_counter(counter)
    raise BlockedProductionArtifactError(
        "UX-1B fixture blocked a production runtime artifact access"
    )


def install_filesystem_guard() -> None:
    """Audit production runtime I/O, including metadata and C-level SQLite."""

    global _FILESYSTEM_CANONICALIZER, _FILESYSTEM_DIR_FD_RESOLVER
    sentinel_name = "_quant_radar_ux1b_filesystem_guard"
    existing = getattr(builtins, sentinel_name, None)
    if isinstance(existing, dict):
        canonicalizer = existing.get("canonicalize")
        dir_fd_resolver = existing.get("dirFdPath")
        reinstall = existing.get("reinstall")
        if not all(callable(value) for value in (canonicalizer, dir_fd_resolver, reinstall)):
            raise FixtureConfigurationError("UX-1B filesystem guard sentinel is invalid")
        _FILESYSTEM_CANONICALIZER = canonicalizer
        _FILESYSTEM_DIR_FD_RESOLVER = dir_fd_resolver
        reinstall()
        return
    originals = {
        "open": builtins.open,
        "io_open": io.open,
        "os_open": os.open,
        "os_stat": os.stat,
        "os_lstat": os.lstat,
        "os_listdir": os.listdir,
        "os_scandir": os.scandir,
        "os_access": os.access,
        "os_readlink": os.readlink,
        "sqlite_connect": sqlite3.connect,
        "sqlite_connection": sqlite3.Connection,
    }

    def resolve_directory_fd(fd: int) -> Path:
        try:
            value = originals["os_readlink"](f"/proc/self/fd/{fd}")
        except OSError:
            try:
                import fcntl

                value = fcntl.fcntl(fd, 50, bytes(1024)).split(b"\0", 1)[0]
            except (ImportError, OSError, TypeError, ValueError) as exc:
                raise FixtureConfigurationError(
                    "UX-1B fixture could not authenticate a directory descriptor"
                ) from exc
        return Path(os.fsdecode(value))

    def canonicalize(path: Path) -> Path:
        return _canonical_io_path_with(
            path,
            originals["os_lstat"],
            originals["os_readlink"],
        )

    _FILESYSTEM_CANONICALIZER = canonicalize
    _FILESYSTEM_DIR_FD_RESOLVER = resolve_directory_fd

    def mode_writes(mode: Any) -> bool:
        return any(flag in str(mode or "r") for flag in ("w", "a", "x", "+"))

    @functools.wraps(originals["open"])
    def guarded_open(file, mode="r", *args, **kwargs):
        _guard_production_artifact(file, write=mode_writes(mode))
        return originals["open"](file, mode, *args, **kwargs)

    @functools.wraps(originals["io_open"])
    def guarded_io_open(file, mode="r", *args, **kwargs):
        _guard_production_artifact(file, write=mode_writes(mode))
        return originals["io_open"](file, mode, *args, **kwargs)

    @functools.wraps(originals["os_open"])
    def guarded_os_open(path, flags, *args, **kwargs):
        write_flags = (
            os.O_WRONLY
            | os.O_RDWR
            | os.O_APPEND
            | os.O_CREAT
            | os.O_TRUNC
        )
        _guard_production_artifact(
            path,
            write=bool(flags & write_flags),
            dir_fd=kwargs.get("dir_fd"),
        )
        return originals["os_open"](path, flags, *args, **kwargs)

    def guarded_stat(path, *args, **kwargs):
        _guard_production_artifact(
            path,
            write=False,
            dir_fd=kwargs.get("dir_fd"),
            fd_is_path=True,
        )
        return originals["os_stat"](path, *args, **kwargs)

    def guarded_lstat(path, *args, **kwargs):
        _guard_production_artifact(
            path,
            write=False,
            dir_fd=kwargs.get("dir_fd"),
            fd_is_path=True,
        )
        return originals["os_lstat"](path, *args, **kwargs)

    def guarded_listdir(path="."):
        _guard_production_artifact(path, write=False, fd_is_path=True)
        return originals["os_listdir"](path)

    def guarded_scandir(path="."):
        _guard_production_artifact(path, write=False, fd_is_path=True)
        return originals["os_scandir"](path)

    def guarded_access(path, mode, *args, **kwargs):
        _guard_production_artifact(
            path,
            write=False,
            dir_fd=kwargs.get("dir_fd"),
        )
        return originals["os_access"](path, mode, *args, **kwargs)

    def guarded_readlink(path, *args, **kwargs):
        _guard_production_artifact(
            path,
            write=False,
            dir_fd=kwargs.get("dir_fd"),
        )
        return originals["os_readlink"](path, *args, **kwargs)

    def guard_single_write(original: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(original)
        def replacement(path, *args, **kwargs):
            _guard_production_artifact(
                path,
                write=True,
                dir_fd=kwargs.get("dir_fd"),
                fd_is_path=True,
            )
            return original(path, *args, **kwargs)

        return _hide_security_wrapper_target(replacement)

    def guard_single_read(original: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(original)
        def replacement(path, *args, **kwargs):
            _guard_production_artifact(
                path,
                write=False,
                dir_fd=kwargs.get("dir_fd"),
                fd_is_path=True,
            )
            return original(path, *args, **kwargs)

        return _hide_security_wrapper_target(replacement)

    def guard_descriptor(
        original: Callable[..., Any],
        *,
        write: bool,
    ) -> Callable[..., Any]:
        @functools.wraps(original)
        def replacement(fd, *args, **kwargs):
            _guard_production_artifact(fd, write=write, fd_is_path=True)
            return original(fd, *args, **kwargs)

        return _hide_security_wrapper_target(replacement)

    original_mkdir = os.mkdir

    @functools.wraps(original_mkdir)
    def guarded_mkdir(path, *args, **kwargs):
        resolved = _resolved_io_path(path, dir_fd=kwargs.get("dir_fd"))
        if resolved is not None:
            try:
                existing_info = originals["os_stat"](resolved)
            except (FileNotFoundError, NotADirectoryError):
                pass
            else:
                # pathlib's mkdir(exist_ok=True) deliberately calls os.mkdir
                # for an existing directory and handles FileExistsError.  It
                # is a metadata check, not a mutation attempt.
                if stat.S_ISDIR(existing_info.st_mode):
                    return original_mkdir(path, *args, **kwargs)
        _guard_production_artifact(
            path,
            write=True,
            dir_fd=kwargs.get("dir_fd"),
        )
        return original_mkdir(path, *args, **kwargs)

    def guard_two_path_write(original: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(original)
        def replacement(source, destination, *args, **kwargs):
            _guard_production_artifact(
                source,
                write=True,
                dir_fd=kwargs.get("src_dir_fd"),
            )
            _guard_production_artifact(
                destination,
                write=True,
                dir_fd=kwargs.get("dst_dir_fd"),
            )
            return original(source, destination, *args, **kwargs)

        return _hide_security_wrapper_target(replacement)

    def sqlite_target(database: Any, uri: bool) -> tuple[Any, bool]:
        try:
            value = os.fsdecode(os.fspath(database))
        except (TypeError, ValueError):
            return database, True
        if value == ":memory:" or value.startswith("file::memory:"):
            return None, False
        if not uri or not value.startswith("file:"):
            return database, True
        from urllib.parse import parse_qs, unquote, urlsplit

        parsed = urlsplit(value)
        query = parse_qs(parsed.query)
        mode = (query.get("mode") or [""])[0]
        return unquote(parsed.path), mode not in {"ro", "memory"}

    def guard_sqlite(database: Any, *, uri: bool) -> None:
        target, write = sqlite_target(database, uri)
        if target is not None:
            _guard_production_artifact(target, write=write)

    def sqlite_uri_argument(args: tuple[Any, ...], kwargs: Mapping[str, Any]) -> bool:
        # `uri` is the seventh positional parameter after `database` on the
        # supported Python 3.11 sqlite3 API.  Guard it even when callers avoid
        # the keyword form.
        value = kwargs.get("uri", args[6] if len(args) > 6 else False)
        return bool(value)

    @functools.wraps(originals["sqlite_connect"])
    def guarded_sqlite_connect(database, *args, **kwargs):
        guard_sqlite(database, uri=sqlite_uri_argument(args, kwargs))
        return originals["sqlite_connect"](database, *args, **kwargs)

    class GuardedSQLiteConnection(originals["sqlite_connection"]):
        def __init__(self, database, *args, **kwargs):
            guard_sqlite(database, uri=sqlite_uri_argument(args, kwargs))
            super().__init__(database, *args, **kwargs)

    single_write_guards: dict[str, Callable[..., Any]] = {}
    for name in (
        "chflags",
        "chmod",
        "chown",
        "lchown",
        "lchflags",
        "lchmod",
        "mkfifo",
        "mknod",
        "remove",
        "rmdir",
        "truncate",
        "unlink",
        "utime",
    ):
        if hasattr(os, name):
            single_write_guards[name] = guard_single_write(getattr(os, name))
    single_read_guards = {
        name: guard_single_read(getattr(os, name))
        for name in ("pathconf", "statvfs")
        if hasattr(os, name)
    }
    descriptor_read_guards = {
        name: guard_descriptor(getattr(os, name), write=False)
        for name in (
            "fpathconf",
            "fstat",
            "fstatvfs",
            "pread",
            "preadv",
            "read",
            "readv",
        )
        if hasattr(os, name)
    }
    descriptor_write_guards = {
        name: guard_descriptor(getattr(os, name), write=True)
        for name in (
            "fchmod",
            "fchown",
            "ftruncate",
            "pwrite",
            "pwritev",
            "write",
            "writev",
        )
        if hasattr(os, name)
    }
    two_path_write_guards: dict[str, Callable[..., Any]] = {}
    for name in ("link", "rename", "replace"):
        if hasattr(os, name):
            two_path_write_guards[name] = guard_two_path_write(getattr(os, name))
    original_symlink = os.symlink

    @functools.wraps(original_symlink)
    def guarded_symlink(source, destination, *args, **kwargs):
        _guard_production_artifact(
            destination,
            write=True,
            dir_fd=kwargs.get("dir_fd"),
        )
        return original_symlink(source, destination, *args, **kwargs)

    for guarded_export in (
        guarded_open,
        guarded_io_open,
        guarded_os_open,
        guarded_mkdir,
        guarded_symlink,
        guarded_sqlite_connect,
    ):
        _hide_security_wrapper_target(guarded_export)

    def reinstall() -> None:
        builtins.open = guarded_open
        io.open = guarded_io_open
        for module in (os, posix):
            module.open = guarded_os_open
            module.stat = guarded_stat
            module.lstat = guarded_lstat
            module.listdir = guarded_listdir
            module.scandir = guarded_scandir
            module.access = guarded_access
            module.readlink = guarded_readlink
            module.mkdir = guarded_mkdir
            module.symlink = guarded_symlink
            for name, replacement in single_write_guards.items():
                setattr(module, name, replacement)
            for name, replacement in single_read_guards.items():
                setattr(module, name, replacement)
            for name, replacement in descriptor_read_guards.items():
                setattr(module, name, replacement)
            for name, replacement in descriptor_write_guards.items():
                setattr(module, name, replacement)
            for name, replacement in two_path_write_guards.items():
                setattr(module, name, replacement)
        for module in (sqlite3, sqlite3.dbapi2, _sqlite3):
            module.connect = guarded_sqlite_connect
            module.Connection = GuardedSQLiteConnection

    state = {
        "canonicalize": canonicalize,
        "dirFdPath": resolve_directory_fd,
        "reinstall": reinstall,
    }
    setattr(builtins, sentinel_name, state)
    setattr(posix, sentinel_name, state)
    setattr(_sqlite3, sentinel_name, state)
    reinstall()


def install_mutation_guards() -> None:
    """Install process-wide subprocess and external-browser bomb seams."""

    sentinel_name = "_quant_radar_ux1b_mutation_guard"
    if getattr(subprocess, sentinel_name, False):
        return
    original_popen = subprocess.Popen

    @functools.wraps(original_popen)
    def guarded_popen(*_args, **_kwargs):
        increment_counter("mutator.subprocess.popen.attempt")
        raise BlockedFixtureMutationError(
            "UX-1B fixture blocked a subprocess launch"
        )

    def blocked_browser(*_args, **_kwargs):
        increment_counter("mutator.external_browser.attempt")
        raise BlockedFixtureMutationError(
            "UX-1B fixture blocked an external browser launch"
        )

    _hide_security_wrapper_target(guarded_popen)
    subprocess.Popen = guarded_popen
    webbrowser.open = blocked_browser
    webbrowser.open_new = blocked_browser
    webbrowser.open_new_tab = blocked_browser
    setattr(subprocess, sentinel_name, True)


def _prepare_preimport_owned_state(environment: FixtureEnvironment) -> None:
    """Seed only the files whose import-time path resolvers otherwise copy prod."""

    for relative in (
        "reports",
        "content",
        "candidates",
        "ai-chat",
        "analytics",
        "knowledge",
    ):
        (environment.fixture_root / relative).mkdir(parents=True, exist_ok=True)
    roster = environment.fixture_root / "content" / "influencers.json"
    if not roster.exists():
        roster.write_text(
            json.dumps(
                {"categories_order": [], "influencers": []},
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    os.environ["SURGE_RUNTIME_DIR"] = str(environment.fixture_root)
    os.environ["SURGE_CANDIDATE_OUTPUT_DIR"] = str(
        environment.fixture_root / "candidates"
    )
    os.environ["SURGE_AI_CHAT_DIR"] = str(environment.fixture_root / "ai-chat")
    os.environ["SURGE_ANALYTICS_DIR"] = str(environment.fixture_root / "analytics")
    os.environ["SURGE_INFLUENCERS_PATH"] = str(roster)


def _install_deterministic_fragment_schedule(
    st_module: ModuleType | Any | None = None,
) -> None:
    """Keep real fragment bodies while disabling periodic fixture reruns."""

    if st_module is None:
        import streamlit as st_module

    marker = "_quant_radar_ux1b_no_periodic_rerun"
    current = getattr(st_module, "fragment", None)
    if getattr(current, marker, False) is True:
        return
    if not callable(current):
        raise _configuration_error("Streamlit fragment API is unavailable")

    def deterministic_fragment(func=None, *, run_every=None):
        del run_every
        return current(func, run_every=None)

    setattr(deterministic_fragment, marker, True)
    st_module.fragment = deterministic_fragment


def _configure_deterministic_fragment_schedule(
    environment: FixtureEnvironment,
    st_module: ModuleType | Any | None = None,
) -> None:
    if environment.profile in UX1B_PROFILE_PHASES:
        _install_deterministic_fragment_schedule(st_module)


def bootstrap_fixture_environment() -> FixtureEnvironment:
    """Authenticate ownership, seed owned import roots, then install guards."""

    environment = validate_fixture_environment()
    _configure_environment(environment)
    _prepare_preimport_owned_state(environment)
    install_network_guard()
    install_filesystem_guard()
    install_mutation_guards()
    _configure_deterministic_fragment_schedule(environment)
    return environment


def _module_key(module: Any) -> str:
    return str(getattr(module, "__name__", f"object:{id(module)}"))


def _mark_wrapper(replacement: Any) -> None:
    try:
        setattr(replacement, _WRAPPER_MARKER, True)
    except (AttributeError, TypeError):
        pass


def _patch_attribute(
    module: Any,
    attribute: str,
    factory: Callable[[Any], Any],
) -> None:
    key = (_module_key(module), attribute)
    current = getattr(module, attribute)
    record = _PATCH_RECORDS.get(key)
    if record is not None and record.module is not module:
        # importlib.reload normally reuses a module object, but test runners and
        # alternate import paths can replace it.  The new module's value is the
        # real boundary and must also become the restoration target.
        record.module = module
        record.original = current
        record.replacement = factory(current)
        record.factory = factory
        _mark_wrapper(record.replacement)
        setattr(module, attribute, record.replacement)
        return
    if record is not None and current is record.replacement:
        return
    if record is not None and current is not record.original:
        # A target module was reloaded. Treat its new value as the real boundary.
        record.original = current
        record.replacement = factory(current)
        record.factory = factory
        _mark_wrapper(record.replacement)
        setattr(module, attribute, record.replacement)
        return
    if record is not None:
        setattr(module, attribute, record.replacement)
        return
    replacement = factory(current)
    _mark_wrapper(replacement)
    _PATCH_RECORDS[key] = _PatchRecord(
        module=module,
        attribute=attribute,
        original=current,
        replacement=replacement,
        factory=factory,
    )
    setattr(module, attribute, replacement)


def _constant(value: Any) -> Callable[[Any], Any]:
    def factory(_original: Any) -> Any:
        return value

    return factory


def _fixed_callable(
    counter_name: str,
    producer: Callable[..., Any],
) -> Callable[[Any], Any]:
    def factory(original: Any) -> Callable[..., Any]:
        @functools.wraps(original)
        def replacement(*args, **kwargs):
            increment_counter(counter_name)
            return producer(*args, **kwargs)

        return replacement

    return factory


def _attempt_wrapper(counter_name: str) -> Callable[[Any], Any]:
    def factory(original: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(original)
        def replacement(*args, **kwargs):
            increment_counter(counter_name)
            return original(*args, **kwargs)

        return replacement

    return factory


def _blocked_callable(counter_name: str) -> Callable[[Any], Any]:
    """Replace a mutating boundary with a counted fail-closed bomb."""

    def factory(original: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(original)
        def replacement(*_args, **_kwargs):
            increment_counter(counter_name)
            raise BlockedFixtureMutationError(
                "UX-1B fixture blocked a mutating provider boundary"
            )

        return replacement

    return factory


def _fixed_trade_rows(*_args, **kwargs) -> list[dict[str, Any]]:
    rows = [
        {
            "ticker": "NVDA",
            "theme": "UX-0 固定樣本",
            "industry_role": "AI Accelerator",
            "industry_role_source": "approved",
            "industry_role_status": "approved",
            "data_quality": ["完整"],
            "data_quality_label": "完整",
            "mentions": 7,
            "mentioned_by": ["fixture-desk"],
            "rank_score": 91.5,
            "price": 142.25,
            "atr_pct": 4.2,
            "cycle": "Cycle1",
            "cycle_label": "C1 趨勢延續",
            "cycle_note": "固定基準：趨勢延續。",
            "ce_trend": "bullish",
            "ce_source": "chandelier",
            "ce_distance_pct": 5.5,
            "risk_status": "NORMAL",
            "signal": "holding",
            "signal_reason": "固定基準：Cycle1 與 CE 同向。",
            "invalidation": "136.50",
            "flow_direction": "bullish",
            "flow_score": 82.0,
        },
        {
            "ticker": "AMD",
            "theme": "UX-0 固定樣本",
            "industry_role": "AI Compute",
            "industry_role_source": "suggested",
            "industry_role_status": "suggested",
            "data_quality": ["Proxy 訊號", "分類待審核"],
            "data_quality_label": "Proxy 訊號 / 分類待審核",
            "mentions": 3,
            "mentioned_by": [],
            "rank_score": 78.0,
            "price": 168.5,
            "atr_pct": 5.1,
            "cycle": "Cycle2/3",
            "cycle_label": "C2/3 轉換窗口",
            "cycle_note": "固定基準：等待趨勢確認。",
            "ce_trend": "neutral",
            "ce_source": "trend_proxy",
            "ce_distance_pct": 1.2,
            "risk_status": "WATCH",
            "signal": "none",
            "signal_reason": "固定基準：等待確認。",
            "invalidation": "160.00",
            "flow_direction": "neutral",
            "flow_score": 54.0,
        },
    ]
    limit = kwargs.get("limit")
    if limit is None and _args:
        limit = _args[0]
    return copy.deepcopy(rows[: int(limit or len(rows))])


def _fixed_ranked_candidates(*_args, **_kwargs) -> list[dict[str, Any]]:
    return [
        {
            "ticker": "NVDA",
            "rank_score": 91.5,
            "last_price": 142.25,
            "ret_5d": 4.2,
            "ret_20d": 11.8,
            "rank_bucket": "TRADEABLE",
            "score_components": {
                "technical_trend": 92,
                "momentum_strength": 88,
                "launch_signal": 83,
                "liquidity_tradability": 96,
                "overheat_risk_control": 72,
            },
            "options_tradability": {
                "status": "TRADEABLE",
                "iv_percentile": 42.0,
                "spread_pct": 3.1,
                "flow_score": 82.0,
                "warnings": [],
            },
            "warnings": [],
        }
    ]


def _fixed_scored_candidates(*_args, **_kwargs) -> list[dict[str, Any]]:
    return [
        {
            "ticker": "NVDA",
            "verdict": "NEEDS_LAYER_2",
            "regime_adjusted_score": 88,
            "composite_score": 87,
            "scores": {
                "technical": 9,
                "catalyst": 8,
                "sentiment": 7,
                "institutional": 9,
                "sector_market": 8,
                "options_flow": 8,
                "analyst": 7,
            },
            "key_signals": ["固定資料：趨勢與籌碼一致"],
            "key_risks": ["固定資料：財報風險需確認"],
            "suggested_entry_zone": "等待突破後回測",
            "data_missing": [],
            "due_diligence_required": False,
        }
    ]


def _fixed_analyst_views(*_args, **_kwargs) -> dict[str, Any]:
    return {
        "consensus": {
            "recommendation": "buy",
            "num_analysts": 12,
            "mean_rating_score": 2.0,
        },
        "price_targets": {
            "spot": 100.0,
            "mean": 120.0,
            "median": 115.0,
            "high": 130.0,
            "low": 90.0,
            "upside_pct": 20.0,
        },
        "rating_distribution": {},
        "recent_actions": [],
        "estimate_revisions": {},
    }


def _fixed_candidate_status(*_args, **_kwargs) -> dict[str, Any]:
    return {
        "run_id": "ux0-fixed-run",
        "job": "candidates-local",
        "status": "succeeded",
        "started_at": FIXED_NOW,
        "updated_at": FIXED_NOW,
        "finished_at": FIXED_NOW,
        "stage": {"id": "rank_candidates", "label": "固定排名完成", "progress_pct": 100},
        "metrics": {"ranked_candidates": 1, "rank_limit": 50, "options_gate_checked": 1},
        "warnings": [],
        "errors": [],
    }


def _fixed_candidate_history(*_args, **_kwargs) -> list[dict[str, Any]]:
    return [_fixed_candidate_status()]


def _fixed_score(*_args, **_kwargs) -> dict[str, Any]:
    matched = {
        "factor": "breakout",
        "dim": "技術",
        "subfactor": "1a",
        "desc": "固定突破因子",
        "lift": 2.1,
        "verdict": "VALIDATED",
        "support": 30,
    }
    unmatched = {
        "factor": "overheat",
        "dim": "風險",
        "subfactor": "5a",
        "desc": "固定過熱因子",
        "lift": 1.2,
        "verdict": "WATCH",
        "support": 25,
    }
    return {
        "threshold": "ALL",
        "score": 0.72,
        "band_level": 3,
        "band_label": "中偏高",
        "n_matched": 1,
        "n_validated": 2,
        "matched": [matched],
        "unmatched": [unmatched],
        "insufficient": [],
        "archetypes": [{"name": "UX-0 Momentum", "description": "固定原型"}],
        "blocked": True,
        "provenance_ok": True,
        "caveat": "UX-0 固定資料僅供基準擷取。",
    }


def _fixed_fundamentals(*_args, **_kwargs) -> dict[str, Any]:
    return {
        "source": "ux0_fixture",
        "valuation": {
            "market_cap": 3_500_000_000_000,
            "forward_pe": 28.0,
            "trailing_pe": 32.0,
            "peg_ratio": 1.4,
            "price_to_book": 18.0,
            "price_to_sales": 14.0,
            "ev_to_ebitda": 24.0,
        },
        "profitability_pct": {
            "gross_margin": 74.0,
            "operating_margin": 61.0,
            "profit_margin": 55.0,
            "return_on_equity": 85.0,
        },
        "growth_pct": {
            "revenue_growth": 42.0,
            "earnings_growth": 51.0,
            "earnings_q_growth_yoy": 48.0,
        },
        "health": {
            "debt_to_equity": 32.0,
            "current_ratio": 3.4,
            "free_cashflow": 58_000_000_000,
            "total_cash": 42_000_000_000,
            "total_debt": 11_000_000_000,
        },
        "estimates": {"target_mean_price": 165.0},
    }


def _fixed_sector_flow(*_args, **_kwargs) -> dict[str, Any]:
    return {
        "as_of": "2026-07-15",
        "benchmark": "SPY",
        "sectors": [
            {
                "etf": "XLK",
                "name_zh": "資訊科技",
                "group": "主板塊",
                "theme": "資訊科技",
                "quadrant": "Leading",
                "quadrant_zh": "領漲",
                "rs_ratio": 104.2,
                "rs_momentum": 102.8,
                "heat_score": 88.0,
                "excess_20d": 4.2,
                "ret_5d": 2.1,
                "ret_20d": 8.4,
                "ret_60d": 17.5,
                "pct_vs_ma50": 5.2,
                "pct_vs_ma200": 12.4,
                "pct_from_52w_high": -1.8,
                "rvol": 1.3,
            }
        ],
    }


def _fixed_ledger_frame(*_args, **_kwargs):
    import pandas as pd

    return pd.DataFrame(
        [
            {
                "scan_date": "2026-07-15",
                "ticker": "NVDA",
                "verdict": "NEEDS_LAYER_2",
                "composite_score": 87.0,
                "suggested_entry_low": 138.0,
                "suggested_entry_high": 143.0,
                "suggested_stop": 132.0,
                "fwd_3d_return": 2.5,
                "fwd_7d_return": 5.0,
                "fwd_14d_return": 8.0,
                "fwd_30d_return": 12.5,
                "max_drawdown_30d": -4.0,
                "hit_15pct_within_30d": False,
                "notes": "UX-1B deterministic fixture",
            }
        ]
    )


def _fixed_options_flow_feed():
    from api.models import OptionsFlowFeedData

    return OptionsFlowFeedData(
        generated_at=FIXED_NOW,
        as_of="2026-07-15",
        provider="ux1b_fixture",
        universe_size=1,
        min_notional=1_000_000,
        signal_count=0,
        signals=[],
    )


def _fixed_options_flow_state(options_flow: ModuleType):
    return options_flow.OptionsFlowPageState(
        "api_available",
        _fixed_options_flow_feed(),
    )


def _fixed_theme_flow(*_args, **_kwargs) -> dict[str, Any]:
    state = "加速流入(推估)"
    theme = {
        "theme": "AI 基礎設施",
        "desc": "UX-1B deterministic theme-flow fixture",
        "capital_state": state,
        "parent_sector_etfs": ["XLK"],
        "flow_5d": 25_000_000.0,
        "flow_20d": 80_000_000.0,
        "accel": 5_000_000.0,
        "flow_5d_norm": 0.25,
        "flow_20d_norm": 0.80,
        "accel_norm": 0.05,
        "ret_5d": 2.5,
        "heat_score": 82.0,
        "raw_heat_score": 88.0,
        "signal_quality": 0.93,
        "breadth_inflow_ratio": 1.0,
        "top_share": 0.45,
        "high_concentration": False,
        "positive_flow_count": 1,
        "negative_flow_count": 0,
        "n_used": 1,
        "n_total": 1,
        "bottom_fishing": False,
        "reps": [
            {
                "ticker": "NVDA",
                "flow_20d": 80_000_000.0,
                "ret_5d": 2.5,
            }
        ],
    }
    return {
        "as_of": "2026-07-15",
        "benchmark": "SPY",
        "n_failed_download": 0,
        "themes": [theme],
        "buckets": {
            "加速流入(推估)": ["AI 基礎設施"],
            "流入趨緩": [],
            "中性": [],
            "流出(推估)": [],
        },
        "shared_mega_caps": [],
    }


class _FixedThemeFlowControls:
    def read_snapshot(self, *_args, **_kwargs) -> dict[str, Any]:
        increment_counter("theme_flow.snapshot.read")
        return copy.deepcopy(_fixed_theme_flow())

    def read_status(self, mode="refresh_board", *_args, **_kwargs) -> dict[str, Any]:
        increment_counter(f"theme_flow.status.{mode}.read")
        return {
            "mode": mode,
            "status": "succeeded",
            "started_at": FIXED_NOW,
            "updated_at": FIXED_NOW,
            "finished_at": FIXED_NOW,
        }

    @staticmethod
    def is_running(_status: dict | None) -> bool:
        return False

    @staticmethod
    def snapshot_is_stale(_flow: dict | None, *_args, **_kwargs) -> bool:
        increment_counter("theme_flow.snapshot_stale.read")
        return False

    @staticmethod
    def launch_background(*_args, **_kwargs):
        increment_counter("mutator.theme_flow.launch_background.attempt")
        raise BlockedFixtureMutationError(
            "UX-1B fixture blocked Theme Flow background launch"
        )


_FIXED_THEME_FLOW_CONTROLS = _FixedThemeFlowControls()


def _fixed_knowledge_graph(*_args, **_kwargs) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": "Dim1",
                "label": "Dim1 技術",
                "type": "dimension",
                "dimension": "Dim1",
                "horizon": "",
                "status": "validated",
                "blocked": False,
                "path": "dimensions/Dim1.md",
            },
            {
                "id": "ux1b-breakout",
                "label": "固定突破因子",
                "type": "factor",
                "dimension": "Dim1",
                "horizon": "30d",
                "status": "exploratory",
                "blocked": True,
                "path": "factors/ux1b-breakout.md",
                "lift_exploratory": 2.1,
                "runway_verdict": "PROVISIONAL",
            },
        ],
        "edges": [
            {
                "source": "ux1b-breakout",
                "target": "Dim1",
                "type": "belongs_to_dimension",
            }
        ],
        "diagnostics": {"unresolved_links": [], "duplicate_ids": []},
    }


def _fixed_social_statuses(*_args, **_kwargs) -> dict[str, dict[str, Any]]:
    labels = {
        "stocktwits": "StockTwits",
        "apewisdom": "ApeWisdom",
        "agent_reach": "Agent Reach",
        "codex_web_research": "Codex web research",
        "x_official_api": "X official API",
    }
    return {
        key: {
            "label": label,
            "status": "unavailable",
            "cost_mode": "fixture",
        }
        for key, label in labels.items()
    }


def _fixed_roster(*_args, **_kwargs) -> dict[str, Any]:
    return {"categories_order": [], "influencers": []}


def _fixed_industry_state(*_args, **_kwargs) -> tuple[dict, dict, dict]:
    return (
        {"version": 1, "roles": {}},
        {"version": 1, "tickers": {}},
        {"generated_at": FIXED_NOW, "suggestions": []},
    )


def _fixed_quote(*_args, **_kwargs) -> dict[str, Any]:
    return {
        "status": "ok",
        "ticker": "NVDA",
        "price": 142.25,
        "source": "ux0_fixture",
        "source_label": "來源：UX-0 Fixture",
    }


def _fixed_reconciliation(*_args, **_kwargs) -> dict[str, Any]:
    return {"matched": [], "held_not_in_ledger": []}


def _fixed_institutional(*_args, **_kwargs) -> dict[str, Any]:
    return {
        "source": "ux0_fixture",
        "ownership_pct": {
            "institutions_held": 67.2,
            "institutions_float_held": 71.4,
            "insiders_held": 3.8,
        },
        "top_institutional_holders": [
            {"holder": "UX-0 Capital", "pct_held": 8.5, "value": 120_000_000_000, "pct_change": 1.2}
        ],
        "insider_6m": {
            "net_direction": "buying",
            "net_shares": 120_000,
            "purchase_shares": 180_000,
            "purchase_trans": 4,
            "sale_shares": 60_000,
            "sale_trans": 2,
        },
        "recent_insider_transactions": [
            {
                "date": "2026-07-10",
                "insider": "Fixture Officer",
                "position": "Director",
                "transaction": "Purchase",
                "shares": 5_000,
            }
        ],
    }


def _fixed_portfolio(*_args, **_kwargs) -> dict[str, Any]:
    return {
        "fund": "UX-0 Fund",
        "report_date": "2026-06-30",
        "filing_date": "2026-07-15",
        "lag_days": 15,
        "holdings_count": 2,
        "total_value": 2_500_000_000,
        "holdings": [
            {"issuer": "NVIDIA CORP", "pct": 60.0, "value": 1_500_000_000, "shares": 10_000_000, "put_call": ""},
            {"issuer": "ADVANCED MICRO DEVICES", "pct": 40.0, "value": 1_000_000_000, "shares": 5_000_000, "put_call": ""},
        ],
    }


def _fixed_cockpit(options_cockpit: ModuleType, ticker: str, *_args, **_kwargs):
    data = copy.deepcopy(options_cockpit._demo_provider(ticker))
    data.is_demo = False
    data.quote_source = "ux0_fixture"
    data.quote_source_label = "來源：UX-0 Fixture"
    return data


def _fixed_risk_snapshot(*_args, **_kwargs) -> dict[str, Any]:
    """Return a fresh, schema-complete Risk Guard sample for real renderers."""

    return {
        "as_of": "2026-07-15",
        "generated_at": FIXED_NOW,
        "disclaimer": "UX-1B deterministic fixture; non-investment advice.",
        "market": {
            "status": "WATCH",
            "score": 38,
            "regime": {
                "spy_vs_50dma": "above",
                "spy_vs_200dma": "above",
                "vix_level": 18.4,
                "sector_rotation": {"leaders": ["XLK"]},
            },
            "cot": {"delta_pct": -0.8, "as_of": "2026-07-11"},
            "weakening_sectors": [],
            "data_gaps": [],
            "reasons": ["UX-1B 固定市場風險樣本"],
        },
        "rows": [
            {
                "ticker": "NVDA",
                "status": "REDUCE",
                "risk_score": 62,
                "market_score": 12,
                "price_score": 18,
                "options_score": 12,
                "sector_score": 8,
                "position_score": 4,
                "cot_score": 3,
                "data_quality_score": 5,
                "primary_reasons": ["UX-1B 固定風險原因"],
                "data_gaps": [],
                "technical": {"price_vs_50dma": "below"},
                "options": {"put_call": 1.2},
                "sector": {"etf": "XLK"},
                "position": {},
            }
        ],
        "summary": {"high_risk": 1},
        "portfolio": {"available": False, "reachable": False},
        "data_sources": {
            "regime": "ux1b_fixture",
            "cot": "ux1b_fixture",
            "positions": "missing",
            "options_flow": "ux1b_fixture",
            "sector": "ux1b_fixture",
            "options": "ux1b_fixture",
        },
    }


def _fixed_reversal_snapshot(*_args, **_kwargs) -> dict[str, Any]:
    return {
        "rows": [
            {
                "ticker": "NVDA",
                "status": "TURNING",
                "reversal_score": 71,
                "data_confidence": "HIGH",
                "lead_vs_confirm": {"front_run": True},
                "primary_signals": ["UX-1B 固定反轉訊號"],
                "structure_score": 16,
                "momentum_score": 17,
                "options_score": 12,
                "sector_score": 10,
                "insider_score": 8,
                "analyst_score": 8,
            }
        ],
        "summary": {"reversal_or_turning": 1, "front_run": 1},
        "exploratory_gate": {
            "blocked": True,
            "reason": "UX-1B deterministic exploratory fixture",
        },
        "cot_confirmation": {"note": "UX-1B fixed confirmation"},
        "data_sources": {
            "technical": "ux1b_fixture",
            "reversal_signals": "ux1b_fixture",
            "options": "ux1b_fixture",
            "sector": "ux1b_fixture",
            "insider": "ux1b_fixture",
            "analyst": "ux1b_fixture",
            "cot": "ux1b_fixture",
        },
    }


def _prepare_fixture_directories(environment: FixtureEnvironment) -> None:
    for path in (
        environment.fixture_root / "reports",
        environment.fixture_root / "content",
        environment.fixture_root / "candidates",
        environment.fixture_root / "ai-chat",
        environment.fixture_root / "analytics",
        environment.fixture_root / "knowledge",
    ):
        path.mkdir(parents=True, exist_ok=True)


def _install_path_rebindings(environment: FixtureEnvironment) -> None:
    from scripts import (
        analytics_store,
        industry_roles as industry_roles_engine,
        influencer_roster_runtime,
        knowledge_graph as knowledge_graph_engine,
        runtime_paths,
    )
    from ui import (
        _candidate_controls,
        _shared,
        analytics_db,
        influencers,
        market_thesis,
        retro_analysis,
        today_decision,
        us_screener,
        watchlist_categorize,
        x_sentiment,
    )

    reports = environment.fixture_root / "reports"
    content = environment.fixture_root / "content"
    candidates = environment.fixture_root / "candidates"
    analytics = environment.fixture_root / "analytics"
    knowledge = environment.fixture_root / "knowledge"
    roster = content / "influencers.json"
    for module, attribute, value in (
        (_shared, "DATA_DIR", environment.fixture_root),
        (_shared, "REPORTS_DIR", reports),
        (_shared, "CONTENT_DIR", content),
        (_shared, "CANDIDATE_OUTPUT_DIR", candidates),
        (runtime_paths, "RUNTIME_DIR", environment.fixture_root),
        (runtime_paths, "CANDIDATE_OUTPUT_DIR", candidates),
        (_candidate_controls, "_RUN_STATUS_PATH", reports / "run_status" / "candidates-local.json"),
        (_candidate_controls, "_RUN_HISTORY_PATH", reports / "run_status" / "candidates-local-history.jsonl"),
        (us_screener, "DATA_DIR", environment.fixture_root),
        (us_screener, "REPORTS_DIR", reports),
        (x_sentiment, "_PICKS_PATH", reports / "x_influencer_picks.json"),
        (x_sentiment, "_SOCIAL_PATH", reports / "social_intelligence" / "latest.json"),
        (retro_analysis, "RETRO_DIR", reports / "retrospective"),
        (analytics_db, "_DATA_HEALTH_STATUS_PATH", reports / "run_status" / "data-health-refresh.json"),
        (analytics_db, "_DATA_HEALTH_LOG_PATH", reports / "run_status" / "data-health-refresh.log"),
        (analytics_store, "REPO", environment.fixture_root),
        (analytics_store, "REPORTS_DIR", reports),
        (knowledge_graph_engine, "ROOT", environment.fixture_root),
        (knowledge_graph_engine, "VAULT", knowledge),
        (industry_roles_engine, "REPO", environment.fixture_root),
        (watchlist_categorize, "_TV_FILE", content / "us_watchlist.txt"),
        (watchlist_categorize, "_THEMES_FILE", content / "themes.json"),
        (influencers, "DEFAULT_ROSTER_PATH", roster),
        (influencers, "ROSTER_PATH", roster),
        (influencer_roster_runtime, "REPO_ROOT", environment.fixture_root),
        (influencer_roster_runtime, "DEFAULT_ROSTER_PATH", roster),
    ):
        _patch_attribute(module, attribute, _constant(value))
    os.environ["SURGE_ANALYTICS_DIR"] = str(analytics)


def _install_common_and_trade_fixtures() -> None:
    from scripts import quote_fallback as scripts_quote_fallback
    from scripts import trade_state as trade_state_engine
    from ui import _shared, trade_state

    _patch_attribute(
        trade_state_engine,
        "build_trade_state_rows",
        _fixed_callable("trade_state.build.execute", _fixed_trade_rows),
    )
    _patch_attribute(
        trade_state,
        "_load_rows",
        _attempt_wrapper("trade_state.load.attempt"),
    )
    _patch_attribute(
        _shared,
        "load_reconciliation",
        _fixed_callable("shared.reconciliation.execute", _fixed_reconciliation),
    )
    _patch_attribute(
        _shared,
        "load_ledger",
        _fixed_callable("shared.ledger.execute", _fixed_ledger_frame),
    )
    _patch_attribute(
        _shared,
        "load_json",
        _attempt_wrapper("shared.json.read"),
    )
    _patch_attribute(
        scripts_quote_fallback,
        "get_quote",
        _fixed_callable("quote_fallback.execute", _fixed_quote),
    )


def _install_today_fixtures() -> None:
    from api.models import (
        DailySummaryData,
        OversoldReversalValidationData,
        RankedCandidatesFeedData,
        ReversalRadarData,
        ReversalRadarValidationData,
        ScoredCandidatesFeedData,
        ScoredCandidatesScreenerData,
    )
    from ui import _candidate_controls, _read_api

    ranked_feed = RankedCandidatesFeedData.model_validate({
        "scan_date": "2026-07-15",
        "generated_at": "2026-07-15T12:00:00+00:00",
        "candidates": _fixed_ranked_candidates(),
    })
    scored_feed = ScoredCandidatesFeedData.model_validate({
        "scan_date": "2026-07-15",
        "candidates": _fixed_scored_candidates(),
    })
    screener_snapshot = ScoredCandidatesScreenerData.model_validate({
        "scan_date": "2026-07-15",
        "needs_layer2_count": 0,
        "watchlist_count": 0,
        "regime_context": {
            "spy_vs_50dma": "above",
            "spy_vs_200dma": "above",
            "vix_level": 18.0,
            "vix_regime": "normal",
            "global_score_multiplier": 1.0,
            "active_themes": ["AI"],
            "regime_warnings": [],
        },
        "candidates": [],
    })
    reversal_validation = ReversalRadarValidationData.model_validate({
        "entries_accumulated": 24,
        "min_resolved_across_tiers": 12,
        "min_resolved_for_verdict": 30,
        "verdict": "PROVISIONAL — sample below threshold, indicative only",
        "by_tier": {
            tier: {
                "resolved": 12,
                "hits": 6,
                "hit_rate": 0.5,
                "wilson90": [0.25, 0.75],
            }
            for tier in ("+10%/20d", "+15%/40d", "+20%/60d")
        },
    })
    reversal_snapshot = ReversalRadarData.model_validate({
        "as_of_date": "2026-07-15",
        "generated_at": "2026-07-15T12:00:00Z",
        "lane_id": "reversal_radar.v1",
        "universe": "ux1b_fixture",
        "match_count": 1,
        "candidates": [{"ticker": "NVDA"}],
    })
    oversold_validation = OversoldReversalValidationData.model_validate({
        "entries_accumulated": 24,
        "min_resolved_across_tiers": 12,
        "min_resolved_for_verdict": 30,
        "verdict": "PROVISIONAL — sample below threshold, indicative only",
        "by_tier": {
            tier: {
                "resolved": 12,
                "hits": 6,
                "hit_rate": 0.5,
                "wilson90": [0.25, 0.75],
            }
            for tier in ("+30%/20d", "+40%/40d", "+50%/60d")
        },
    })
    daily_summary = DailySummaryData.model_validate({
        "as_of_date": "2026-07-15",
        "regime_summary": "UX-0 固定基準",
        "candidates": [{"ticker": "NVDA", "verdict": "BUY"}],
    })
    _patch_attribute(
        _read_api,
        "load_daily_summary",
        _fixed_callable(
            "today.daily_summary.execute",
            lambda *_a, **_k: _read_api.DailySummaryApiAvailable(daily_summary),
        ),
    )
    _patch_attribute(
        _read_api,
        "load_ranked_candidates",
        _fixed_callable(
            "today.ranked_candidates.execute",
            lambda *_a, **_k: _read_api.RankedCandidatesApiAvailable(ranked_feed),
        ),
    )
    _patch_attribute(
        _read_api,
        "load_scored_candidates",
        _fixed_callable(
            "today.scored_candidates.execute",
            lambda *_a, **_k: _read_api.ScoredCandidatesApiAvailable(scored_feed),
        ),
    )
    _patch_attribute(
        _read_api,
        "load_scored_candidates_screener",
        _fixed_callable(
            "screener.scored_candidates.execute",
            lambda *_a, **_k: _read_api.ScoredCandidatesScreenerApiAvailable(
                screener_snapshot
            ),
        ),
    )
    _patch_attribute(
        _read_api,
        "load_reversal_radar",
        _fixed_callable(
            "today.reversal_api.execute",
            lambda *_a, **_k: _read_api.ReversalRadarApiAvailable(
                reversal_snapshot
            ),
        ),
    )
    _patch_attribute(
        _read_api,
        "load_reversal_radar_validation",
        _fixed_callable(
            "today.validation.execute",
            lambda *_a, **_k: _read_api.ReversalRadarValidationApiAvailable(
                reversal_validation
            ),
        ),
    )
    _patch_attribute(
        _read_api,
        "load_oversold_reversal_validation",
        _fixed_callable(
            "today.validation.execute",
            lambda *_a, **_k: _read_api.OversoldReversalValidationApiAvailable(
                oversold_validation
            ),
        ),
    )

    for attribute, counter, producer in (
        ("_load_candidate_status", "today.candidate_status.execute", _fixed_candidate_status),
        ("_candidate_run_history", "today.candidate_history.execute", _fixed_candidate_history),
        ("read_pending_codex_request", "today.claude_pending.execute", lambda *_a, **_k: None),
        ("refresh_codex_auth_status", "today.claude_auth.execute", lambda *_a, **_k: {"ok": False, "state": "fixture"}),
    ):
        _patch_attribute(_candidate_controls, attribute, _fixed_callable(counter, producer))


def _install_stock_and_options_fixtures() -> None:
    from api.models import MoneyFlowData, SectorRotationData, ThemeDrillData
    from scripts import iv_history as scripts_iv_history
    from ui import _fundamentals, _read_api, _shared, options_cockpit, stock_checkup

    money_flow_snapshot = MoneyFlowData.model_validate(
        {
            "as_of_date": "2026-07-15",
            "generated_at": "2026-07-15T12:00:00Z",
            "source": "eastmoney_push2his",
            "publishable": True,
            "coverage": {
                "requested": 1,
                "resolved": 1,
                "unavailable": 0,
                "coverage_ratio": 1.0,
                "min_coverage": 0.7,
            },
            "rows": [
                {
                    "ticker": "NVDA",
                    "date": "2026-07-15",
                    "main_net": 12_500_000.0,
                    "main_pct": 3.2,
                    "small_net": -2_000_000.0,
                    "source": "eastmoney_push2his",
                }
            ],
        },
        strict=True,
    )
    sector_rotation_snapshot = SectorRotationData.model_validate(
        _fixed_sector_flow(),
        strict=True,
    )
    theme_drill = ThemeDrillData.model_validate(
        {
            "sectors": [
                {"etf": "XLK", "themes": ["AI 基礎設施"]},
            ]
        },
        strict=True,
    )

    _patch_attribute(
        scripts_iv_history,
        "iv_percentile",
        lambda *_a, **_k: {
            "rank": 42.0,
            "accumulating": False,
            "n_days": 60,
        },
    )

    _patch_attribute(
        stock_checkup.lf,
        "live_factor_flags",
        _fixed_callable(
            "stock.live_factor_flags.execute",
            lambda *_a, **_k: {"breakout": True, "overheat": False},
        ),
    )
    _patch_attribute(
        stock_checkup.lf,
        "score_surge",
        _fixed_callable("stock.score_surge.execute", _fixed_score),
    )
    _patch_attribute(
        _fundamentals,
        "load",
        _fixed_callable("fundamentals.load.execute", _fixed_fundamentals),
    )
    _patch_attribute(
        _shared,
        "ticker_sector_etf",
        _fixed_callable("sector.ticker.execute", lambda *_a, **_k: "XLK"),
    )
    _patch_attribute(
        _read_api,
        "load_sector_rotation",
        _fixed_callable(
            "sector.rotation_api.execute",
            lambda *_a, **_k: _read_api.SectorRotationApiAvailable(
                sector_rotation_snapshot
            ),
        ),
    )
    _patch_attribute(
        _read_api,
        "load_theme_drill",
        _fixed_callable(
            "sector.theme_drill_api.execute",
            lambda *_a, **_k: _read_api.ThemeDrillApiAvailable(theme_drill),
        ),
    )
    _patch_attribute(
        stock_checkup.quote_fallback,
        "get_quote",
        _fixed_callable("stock.quote_fallback.execute", _fixed_quote),
    )
    _patch_attribute(
        options_cockpit,
        "_live_provider",
        _fixed_callable(
            "options.live_provider.execute",
            lambda ticker, *_a, **_k: _fixed_cockpit(options_cockpit, ticker),
        ),
    )
    _patch_attribute(
        _read_api,
        "load_money_flow",
        _fixed_callable(
            "options.money_flow_api.execute",
            lambda *_a, **_k: _read_api.MoneyFlowApiAvailable(money_flow_snapshot),
        ),
    )
    _patch_attribute(
        _read_api,
        "load_options_flow",
        _fixed_callable(
            "options.options_flow_api.execute",
            lambda *_a, **_k: _read_api.OptionsFlowApiAvailable(
                _fixed_options_flow_feed()
            ),
        ),
    )
    _patch_attribute(
        _read_api,
        "load_social_intelligence",
        _fixed_callable(
            "options.social_api.execute",
            lambda *_a, **_k: _read_api.SocialIntelligenceApiUnavailable("missing"),
        ),
    )


def _install_institution_fixtures() -> None:
    from ui import _read_api, institution_portfolio, institutional_holdings

    _patch_attribute(
        institutional_holdings,
        "_load",
        _fixed_callable("institutions.stock.load.execute", _fixed_institutional),
    )

    def fixed_catalog(*_args, **_kwargs):
        return _read_api.FundCatalogApiAvailable(
            (_read_api.FundCatalogOption("UX-0 Fund", "1067983", "固定基準"),)
        )

    _patch_attribute(
        _read_api,
        "load_fund_catalog",
        _fixed_callable("institutions.catalog.execute", fixed_catalog),
    )
    _patch_attribute(
        institution_portfolio,
        "_load",
        _fixed_callable("institutions.portfolio.load.execute", _fixed_portfolio),
    )


def _install_schedule_and_ai_fixtures() -> None:
    from api.models import (
        AiUpdateItem,
        CotCatalogData,
        CotReportData,
        CryptoUniverseData,
        ScheduleEntry,
    )
    from ui import _read_api, sys_schedules

    def fixed_schedules(*_args, **_kwargs):
        entry = ScheduleEntry(
            id="ux0_fixed_report",
            name="UX-0 固定排程",
            category="系統",
            cron="30 6 * * 1-5",
            cron_note="UTC 固定基準",
            description="只供 UX-0 擷取，不觸發任何工作。",
            result_type="report_dir",
        )
        return _read_api.SchedulesApiAvailable((entry,))

    def fixed_updates(*_args, **_kwargs):
        item = AiUpdateItem(
            date="2026-07-15",
            title="UX-0 固定更新",
            summary="此卡片由固定 typed fixture 提供，不連線外部服務。",
            link="",
            tags=["UX-0", "基準"],
        )
        return _read_api.AiUpdatesApiAvailable((item,))

    def fixed_crypto_universe(*_args, **_kwargs):
        snapshot = CryptoUniverseData.model_validate(
            {
                "date": "2026-07-15",
                "source": "binance_fapi_exchangeInfo",
                "source_status": "live",
                "stale": False,
                "stale_source_date": None,
                "count": 1,
                "universe": [
                    {
                        "symbol": "BTCUSDT",
                        "base": "BTC",
                        "tv_symbol": "BINANCE:BTCUSDT.P",
                        "onboard_date": "2019-09-25",
                    }
                ],
                "added": [],
                "removed": [],
                "compared_to": None,
            }
        )
        return _read_api.CryptoUniverseApiAvailable(snapshot)

    cot_catalog = CotCatalogData.model_validate(
        {"reports": [{"report_date": "2026-07-10"}]}
    )
    cot_report = CotReportData.model_validate(
        {
            "report_date": "2026-07-10",
            "markdown": (
                "# UX-0 COT 週報\n\n**COT as-of** 2026-07-07\n\n"
                "## Section 1 — Positioning\n固定籌碼結構。\n\n"
                "## Section 2 — Institutions\n固定機構博弈。\n\n"
                "## Section 3 — Strategy\n固定交易策略。\n\n"
                "## Section 4 — Risks\n固定風險提示。"
            ),
            "verified": {
                "cot": {
                    "as_of": "2026-07-07",
                    "market": "E-MINI S&P 500",
                    "open_interest": 2_000_000,
                    "asset_manager": {
                        "long": 1_200_000,
                        "short": 200_000,
                        "net": 1_000_000,
                        "chg_long": 5_000,
                        "chg_short": 2_000,
                        "chg_net": 3_000,
                    },
                    "leveraged_funds": {
                        "long": 200_000,
                        "short": 600_000,
                        "net": -400_000,
                        "chg_long": 4_000,
                        "chg_short": -6_000,
                        "chg_net": 10_000,
                    },
                    "source": "UX-0 CFTC fixture",
                },
                "price": {
                    "symbol": "ES=F",
                    "friday_date": "2026-07-10",
                    "friday_open": 6_250.0,
                    "friday_high": 6_300.0,
                    "friday_low": 6_225.0,
                    "friday_close": 6_280.0,
                    "week_high": 6_300.0,
                    "week_low": 6_200.0,
                    "as_of_date": "2026-07-07",
                    "as_of_close": 6_250.0,
                    "cot_report_age_days": 5,
                    "cot_stale_warning": False,
                    "source": "UX-0 price fixture",
                    "retrieved_at": "2026-07-12T12:00:00+00:00",
                },
                "tuesday_vs_friday": {
                    "as_of_tuesday_close": 6_250.0,
                    "friday_close": 6_280.0,
                    "delta_points": 30.0,
                },
            },
        }
    )

    _patch_attribute(
        _read_api,
        "load_schedules",
        _fixed_callable("schedules.load.execute", fixed_schedules),
    )
    _patch_attribute(
        _read_api,
        "load_ai_updates",
        _fixed_callable("ai_updates.load.execute", fixed_updates),
    )
    _patch_attribute(
        _read_api,
        "load_crypto_universe",
        _fixed_callable("crypto_universe.load.execute", fixed_crypto_universe),
    )
    _patch_attribute(
        _read_api,
        "load_cot_catalog",
        _fixed_callable(
            "cot.catalog.execute",
            lambda *_a, **_k: _read_api.CotCatalogApiAvailable(cot_catalog),
        ),
    )
    _patch_attribute(
        _read_api,
        "load_cot_report",
        _fixed_callable(
            "cot.detail.execute",
            lambda *_a, **_k: _read_api.CotReportApiAvailable(cot_report),
        ),
    )

    fetchers: dict[str, Callable[[], str]] = {}
    for result_type in sys_schedules._RESULT_FETCHERS:
        counter_name = f"schedules.result.{result_type}.execute"

        def fetch(
            _counter_name: str = counter_name,
            _result_type: str = result_type,
        ) -> str:
            increment_counter(_counter_name)
            return f"UX-0 固定結果 · {_result_type} · 2026-07-15"

        fetchers[result_type] = fetch
    _patch_attribute(sys_schedules, "_RESULT_FETCHERS", _constant(fetchers))


def _install_extended_market_fixtures() -> None:
    from scripts import theme_flow as theme_flow_engine
    from ui import (
        _read_api,
        _shared,
        market_thesis,
        options_flow,
        oversold_reversal_lane,
        risk_guard,
        retro_analysis,
        theme_flow,
    )

    _patch_attribute(
        options_flow,
        "_load_options_flow",
        _fixed_callable(
            "options_flow.load.execute",
            lambda *_a, **_k: _fixed_options_flow_state(options_flow),
        ),
    )
    _patch_attribute(
        options_flow,
        "_live_chain",
        _blocked_callable("provider.options_flow.live_chain.attempt"),
    )
    _patch_attribute(
        _read_api,
        "load_oversold_reversal",
        _fixed_callable(
            "radar.oversold_api.execute",
            lambda *_a, **_k: _read_api.OversoldReversalApiUnavailable("missing"),
        ),
    )
    _patch_attribute(
        risk_guard,
        "_collect",
        _fixed_callable(
            "risk_guard.source.read",
            lambda *_a, **_k: (["NVDA"], False),
        ),
    )
    _patch_attribute(
        risk_guard,
        "_load_scheduled_risk_snapshot",
        _fixed_callable("risk_guard.snapshot.read", _fixed_risk_snapshot),
    )
    _patch_attribute(
        _read_api,
        "load_market_thesis",
        _fixed_callable(
            "market_thesis.latest_api.execute",
            lambda *_a, **_k: _read_api.MarketThesisApiUnavailable("missing"),
        ),
    )
    _patch_attribute(
        _read_api,
        "load_market_thesis_validation",
        _fixed_callable(
            "market_thesis.validation_api.execute",
            lambda *_a, **_k: _read_api.MarketThesisValidationApiUnavailable(
                "missing"
            ),
        ),
    )
    _patch_attribute(
        _read_api,
        "load_market_thesis_regime_history",
        _fixed_callable(
            "market_thesis.regime_api.execute",
            lambda *_a, **_k: _read_api.MarketThesisRegimeHistoryApiUnavailable(
                "missing"
            ),
        ),
    )
    _patch_attribute(
        _read_api,
        "load_playbook_validation",
        _fixed_callable(
            "playbook_validation.latest_api.execute",
            lambda *_a, **_k: _read_api.PlaybookValidationApiUnavailable(
                "missing"
            ),
        ),
    )
    _patch_attribute(
        _read_api,
        "load_continuation_validation",
        _fixed_callable(
            "continuation_validation.latest_api.execute",
            lambda *_a, **_k: _read_api.ContinuationValidationApiUnavailable(
                "missing"
            ),
        ),
    )
    _patch_attribute(
        retro_analysis,
        "_load",
        _fixed_callable("retro_analysis.artifact.read", lambda *_a, **_k: None),
    )
    _patch_attribute(
        theme_flow_engine,
        "load_baskets",
        _fixed_callable(
            "sector_rotation.baskets.read",
            lambda *_a, **_k: {
                "AI 基礎設施": {
                    "desc": "UX-1B fixture",
                    "tickers": ["NVDA"],
                    "reps_hint": ["NVDA"],
                    "parent_sector_etfs": ["XLK"],
                }
            },
        ),
    )
    _patch_attribute(
        theme_flow,
        "_background_controls",
        _fixed_callable(
            "theme_flow.controls.read",
            lambda *_a, **_k: _FIXED_THEME_FLOW_CONTROLS,
        ),
    )
    _patch_attribute(
        theme_flow,
        "_theme_flow_state",
        _fixed_callable(
            "theme_flow.snapshot.read",
            lambda *_a, **_k: theme_flow.ThemeFlowState(
                "api_available",
                copy.deepcopy(_fixed_theme_flow()),
            ),
        ),
    )
    _patch_attribute(
        theme_flow,
        "_theme_flow_analysis_state",
        _fixed_callable(
            "theme_flow.ai_payload.read",
            lambda *_a, **_k: theme_flow.ThemeFlowAnalysisState(
                "api_unavailable",
                None,
                "missing",
            ),
        ),
    )
    _patch_attribute(
        theme_flow,
        "_parent_quadrants",
        _fixed_callable(
            "theme_flow.parent_quadrants.read",
            lambda themes, *_a, **_k: {
                str(row.get("theme")): "XLK 領漲" for row in themes
            },
        ),
    )
    _patch_attribute(
        _shared,
        "load_theme_insider",
        _fixed_callable(
            "theme_flow.insider.read",
            lambda *_a, **_k: {
                "by_theme": {
                    "AI 基礎設施": {
                        "insider_net_usd": 1_000_000.0,
                        "n_buy": 1,
                        "n_sell": 0,
                        "n_cov": 1,
                        "n_total": 1,
                    }
                }
            },
        ),
    )


def _install_local_service_fixtures() -> None:
    from scripts import ibkr_client

    _patch_attribute(
        ibkr_client,
        "available",
        _fixed_callable("ibkr.available.read", lambda *_a, **_k: False),
    )
    _patch_attribute(
        ibkr_client,
        "reconcile",
        _blocked_callable("mutator.ibkr.connect.attempt"),
    )


def _install_x_fixtures() -> None:
    from scripts import agent_reach_auth, social_intelligence, x_analysis
    from ui import influencers, x_sentiment

    _patch_attribute(
        social_intelligence,
        "source_statuses",
        _fixed_callable("x.source_statuses.read", _fixed_social_statuses),
    )
    _patch_attribute(
        agent_reach_auth,
        "agent_reach_config_status",
        _fixed_callable(
            "x.agent_reach_config.read",
            lambda *_a, **_k: {
                "configured": False,
                "auth_token": "",
                "ct0": "",
            },
        ),
    )
    _patch_attribute(
        x_analysis,
        "get_status",
        _fixed_callable(
            "x.analysis_status.read",
            lambda *_a, **_k: {"x_token": False, "codex": False},
        ),
    )
    _patch_attribute(
        influencers,
        "for_market",
        _fixed_callable("x.roster.read", lambda *_a, **_k: []),
    )
    _patch_attribute(
        x_sentiment,
        "_maybe_auto_refresh_radar",
        _blocked_callable("mutator.x.auto_refresh.attempt"),
    )
    _patch_attribute(
        x_sentiment,
        "_maybe_auto_generate_ai_summary",
        _blocked_callable("mutator.x.ai_summary.attempt"),
    )
    _patch_attribute(
        x_sentiment,
        "_write_free_first_snapshot_from_ui",
        _blocked_callable("mutator.x.snapshot_write.attempt"),
    )
    for attribute in ("start_login_session", "update_config_from_running_session"):
        _patch_attribute(
            agent_reach_auth,
            attribute,
            _blocked_callable("mutator.login_auth.attempt"),
        )


def _fixed_analytics_status(*_args, **_kwargs) -> dict[str, Any]:
    return {
        "run_id": "ux1b-data-health",
        "status": "succeeded",
        "started_at": FIXED_NOW,
        "updated_at": FIXED_NOW,
        "finished_at": FIXED_NOW,
        "stage": {
            "id": "complete",
            "label": "固定資料完成",
            "progress_pct": 100,
            "message": "UX-1B deterministic fixture",
        },
        "metrics": {
            "tickers": 0,
            "today_signal_can_publish": True,
            "warnings": 0,
            "blockers": 0,
        },
        "stages": [],
    }


def _fixed_analytics_catalog(*_args, empty: bool = False, **_kwargs) -> list[dict[str, Any]]:
    if empty:
        return []
    return [
        {
            "table_name": "candidate_rankings",
            "table_type": "BASE TABLE",
            "row_count": 2,
            "column_count": 4,
        },
        {
            "table_name": "iv_history",
            "table_type": "BASE TABLE",
            "row_count": 2,
            "column_count": 3,
        },
    ]


def _fixed_analytics_columns(table: str, *_args, **_kwargs) -> list[str]:
    columns = {
        "candidate_rankings": ["ticker", "scan_date", "rank", "composite_score"],
        "iv_history": ["ticker", "as_of_date", "atm_iv"],
        "performance_ledger": [
            "ticker",
            "scan_date",
            "verdict",
            "composite_score",
            "fwd_30d_return",
            "max_drawdown_30d",
            "hit_15pct_within_30d",
        ],
    }
    return list(columns.get(str(table), ()))


def _fixed_analytics_tickers(table: str, *_args, **_kwargs) -> list[str]:
    if str(table) in {"candidate_rankings", "iv_history", "performance_ledger"}:
        return ["NVDA", "AMD"]
    return []


def _fixed_analytics_table(table: str, *_args, **_kwargs):
    import pandas as pd

    selected = str(table)
    if selected == "candidate_rankings":
        return pd.DataFrame(
            [
                {
                    "ticker": "NVDA",
                    "scan_date": "2026-07-15",
                    "rank": 1,
                    "composite_score": 88.0,
                },
                {
                    "ticker": "AMD",
                    "scan_date": "2026-07-15",
                    "rank": 2,
                    "composite_score": 81.0,
                },
            ]
        )
    if selected == "iv_history":
        return pd.DataFrame(
            [
                {"ticker": "NVDA", "as_of_date": "2026-07-14", "atm_iv": 0.43},
                {"ticker": "AMD", "as_of_date": "2026-07-15", "atm_iv": 0.39},
            ]
        )
    if selected == "performance_ledger":
        return _fixed_ledger_frame()
    return pd.DataFrame(columns=_fixed_analytics_columns(selected))


def _install_analytics_fixtures(environment: FixtureEnvironment) -> None:
    from ui import analytics_db

    root = environment.fixture_root / "analytics"
    _patch_attribute(
        analytics_db,
        "_analytics_root",
        _fixed_callable("analytics.root.read", lambda *_a, **_k: root),
    )
    _patch_attribute(
        analytics_db,
        "_catalog",
        _fixed_callable("analytics.catalog.read", _fixed_analytics_catalog),
    )
    _patch_attribute(
        analytics_db,
        "_columns",
        _fixed_callable(
            "analytics.columns.read",
            lambda _root, table, *_a, **_k: _fixed_analytics_columns(table),
        ),
    )
    _patch_attribute(
        analytics_db,
        "_load_checks",
        _fixed_callable("analytics.checks.read", lambda *_a, **_k: None),
    )
    _patch_attribute(
        analytics_db,
        "_load_data_health_status",
        _fixed_callable("analytics.status.read", _fixed_analytics_status),
    )
    _patch_attribute(
        analytics_db,
        "_tickers",
        _fixed_callable(
            "analytics.tickers.read",
            lambda _root, table, *_a, **_k: _fixed_analytics_tickers(table),
        ),
    )
    _patch_attribute(
        analytics_db,
        "_fetch_table",
        _fixed_callable(
            "analytics.table.read",
            lambda _root, table, *_a, **_k: _fixed_analytics_table(table),
        ),
    )
    _patch_attribute(
        analytics_db,
        "_write_data_health_status",
        _blocked_callable("mutator.analytics.write_status.attempt"),
    )
    for attribute in (
        "_launch_core_source_refresh",
        "_refresh_analytics_db",
        "_refresh_core_sources",
        "_refresh_fundamentals",
        "_refresh_theme_flow",
        "_refresh_sector_rotation_snapshot",
    ):
        _patch_attribute(
            analytics_db,
            attribute,
            _blocked_callable("mutator.analytics.refresh.attempt"),
        )


def _install_research_and_catalog_fixtures() -> None:
    from scripts import industry_roles as industry_roles_engine, options_free
    from ui import (
        _shared,
        industry_roles,
        influencers,
        knowledge_graph,
        watchlist_categorize,
    )

    _patch_attribute(
        knowledge_graph,
        "_load_graph",
        _fixed_callable("knowledge_graph.load.execute", _fixed_knowledge_graph),
    )
    _patch_attribute(
        industry_roles,
        "_load_state",
        _fixed_callable("industry_roles.state.read", _fixed_industry_state),
    )
    for attribute in ("generate_suggestions", "review_suggestion"):
        _patch_attribute(
            industry_roles_engine,
            attribute,
            _blocked_callable("mutator.industry_roles.write.attempt"),
        )
    _patch_attribute(
        watchlist_categorize,
        "_sectors",
        _fixed_callable("watchlist.sectors.read", lambda *_a, **_k: {}),
    )
    _patch_attribute(
        influencers,
        "load_roster",
        _fixed_callable("influencers.roster.read", _fixed_roster),
    )
    _patch_attribute(
        influencers,
        "save_roster",
        _blocked_callable("mutator.influencers.write.attempt"),
    )
    _patch_attribute(
        influencers,
        "lookup_x_preview",
        _blocked_callable("mutator.external_browser.attempt"),
    )
    _patch_attribute(
        options_free,
        "analyze_options",
        _blocked_callable("provider.us_options.live.attempt"),
    )
    _patch_attribute(
        _shared,
        "load_analyst_views",
        _fixed_callable(
            "provider.analyst_views.execute",
            _fixed_analyst_views,
        ),
    )


def install_provider_fixtures() -> None:
    """Install deterministic high-level seams without replacing any render."""

    environment = current_environment()
    executable_source = environment.source_root or _REPO_ROOT
    source_scripts = executable_source / "scripts"
    if not source_scripts.is_dir():
        raise _configuration_error("fixture source scripts directory is unavailable")
    if str(source_scripts) not in sys.path:
        sys.path.insert(0, str(source_scripts))
    with _PATCH_LOCK:
        _prepare_fixture_directories(environment)
        _install_path_rebindings(environment)
        _install_common_and_trade_fixtures()
        _install_today_fixtures()
        _install_stock_and_options_fixtures()
        _install_institution_fixtures()
        _install_schedule_and_ai_fixtures()
        _install_extended_market_fixtures()
        _install_local_service_fixtures()
        _install_x_fixtures()
        _install_analytics_fixtures(environment)
        _install_research_and_catalog_fixtures()


def restore_provider_fixtures() -> None:
    """Restore all patched boundaries; intended for isolated AppTest contexts."""

    with _PATCH_LOCK:
        for record in reversed(tuple(_PATCH_RECORDS.values())):
            if getattr(record.module, record.attribute, None) is record.replacement:
                setattr(record.module, record.attribute, record.original)
        _PATCH_RECORDS.clear()


@contextmanager
def provider_fixture_context() -> Iterator[None]:
    """Keep provider patches active across every rerun in one AppTest group."""

    global _PROVIDER_CONTEXT_DEPTH
    with _PATCH_LOCK:
        install_provider_fixtures()
        _PROVIDER_CONTEXT_DEPTH += 1
    try:
        yield
    finally:
        with _PATCH_LOCK:
            _PROVIDER_CONTEXT_DEPTH -= 1
            if _PROVIDER_CONTEXT_DEPTH == 0:
                restore_provider_fixtures()


def _seed_radar_capture_state(state: Any) -> None:
    state["radar_source"] = "手動輸入"
    state["radar_manual"] = "NVDA"
    state["radar_inc_pos"] = False
    state["radar_risk"] = _fixed_risk_snapshot()
    state["radar_rev"] = _fixed_reversal_snapshot()
    state["radar_run_key"] = ("手動輸入", ("NVDA",), False)


def prepare_capture_session(
    st_module: Any,
    route: str,
    capture_id: str,
    *,
    real_callable: str,
) -> None:
    """Clear global data caches and seed one new fixture session exactly once."""

    normalized_route = str(route or "").strip("/") or "today-decision"
    if normalized_route not in TARGET_ROUTES:
        raise _configuration_error("selected page is outside the UX-0 fixture matrix")
    capture = _validate_capture_id(capture_id)
    _set_capture_identity(normalized_route, capture, real_callable)
    state = st_module.session_state
    if state.get(_CAPTURE_STATE_KEY) == capture:
        return

    st_module.cache_data.clear()
    existing_view = state.get("inst_view")
    exact_clear = {
        "analytics_db_refresh_result",
        "cot_codex_auth_login",
        "ibkr_rev",
        "ibkr_risk",
        "ibkr_risk_for",
        "opt_ticker",
        "radar_detail_pick",
        "radar_handoff",
        "radar_inc_pos",
        "radar_manual",
        "radar_rev",
        "radar_risk",
        "radar_run_key",
        "radar_source",
        "radar_view",
        "retro_dataset",
        "social_ai_summary_codex_auth_login",
        "social_radar_auto_run",
        "social_ai_auto_summary",
        "theme_flow_focus_sector",
        "validation_lane",
        "influencer_last_deleted",
        "influencer_detail_key",
        "influencer_search_preview",
        "influencer_search_requested",
        "influencer_compact_search",
        "roster_detail_pick",
        "tv_text",
        "_tv_up_id",
    }
    prefix_clear = (
        "vol_surface_",
        "chainview_",
        "flow_feed_sel",
        "x_sentiment_view_",
        "radar_free_refresh_",
        "social_ai_",
    )
    for key in tuple(state):
        key_text = str(key)
        if key_text in exact_clear or key_text.startswith(prefix_clear):
            del state[key]
    state[_CAPTURE_STATE_KEY] = capture
    state[_ROUTE_STATE_KEY] = normalized_route
    state["cockpit_ticker"] = "NVDA"
    state["checkup_mode"] = "單檔"
    state["checkup_ticker"] = "NVDA"
    state["checkup_ticker_input"] = "NVDA"
    state["inst_ticker"] = "NVDA"
    state["ai_chat_open_panel"] = False
    if normalized_route == "watchlist-categorize":
        state["tv_text"] = ""
    if normalized_route == "retro-analysis":
        state["retro_validation_lane"] = "暴漲事件復盤"
    if normalized_route == "radar":
        _seed_radar_capture_state(state)
    institution_views = {
        "機構持股 · 股票 → 誰持有它",
        "機構持倉 · 機構 → 它持有什麼",
    }
    if existing_view in institution_views:
        state["inst_view"] = existing_view
    elif "inst_view" in state:
        del state["inst_view"]
    increment_counter("session.setup", capture_id=capture)


def _capture_from_query_params(st_module: Any) -> str:
    try:
        raw = st_module.query_params.get("ux0_capture")
    except Exception as exc:
        raise _configuration_error("ux0_capture query value is unavailable") from exc
    if isinstance(raw, list):
        if len(raw) != 1:
            raise _configuration_error("ux0_capture must occur exactly once")
        raw = raw[0]
    return _validate_capture_id(str(raw or ""))


def record_theme_gallery_render(st_module: Any) -> str:
    """Record one completed theme-gallery render for this Streamlit session."""

    environment = current_environment()
    if (
        environment.profile != UX1B_THEME_PROFILE
        or environment.phase != "posttheme"
    ):
        raise _configuration_error(
            "theme gallery requires the ux1b-theme/posttheme fixture profile"
        )
    capture_id = _capture_from_query_params(st_module)
    if capture_id not in {
        "theme-gallery/desktop",
        "theme-gallery/tablet",
        "theme-gallery/mobile",
    }:
        raise _configuration_error("theme gallery capture is outside its frozen matrix")

    state_key = "_quant_radar_ux1b_theme_gallery_capture"
    existing = st_module.session_state.get(state_key)
    if existing is not None and existing != capture_id:
        raise _configuration_error("theme gallery capture changed inside one session")
    _set_capture_identity(
        "theme-gallery",
        capture_id,
        "ui_ux_theme_fixture_app",
    )
    if existing is None:
        with capture_context(capture_id):
            increment_counter("theme.gallery.render")
        st_module.session_state[state_key] = capture_id
    return capture_id


def assert_theme_counter_contract(capture_id: str) -> dict[str, Any]:
    """Fail closed unless one gallery capture matches the exact theme contract."""

    snapshot = counter_snapshot(capture_id)
    counts = snapshot.get("counts") or {}
    positives = dict(THEME_COUNTER_CONTRACT["positive"])
    zero = set(THEME_COUNTER_CONTRACT["zero"])
    mismatches = {
        name: {"expected": count, "actual": int(counts.get(name, 0))}
        for name, count in positives.items()
        if int(counts.get(name, 0)) != count
    }
    mismatches.update(
        {
            name: {"expected": 0, "actual": int(counts.get(name, 0))}
            for name in zero
            if int(counts.get(name, 0)) != 0
        }
    )
    declared = set(positives) | zero
    undeclared = {name: count for name, count in counts.items() if name not in declared}
    if mismatches or undeclared:
        raise AssertionError(
            "UX-1B theme fixture counter mismatch "
            f"capture={capture_id} mismatches={mismatches} undeclared={undeclared}"
        )
    expected_identity = {
        "selectedRegistryKey": "theme-gallery",
        "realCallable": "ui_ux_theme_fixture_app",
        "resolvedOwnedPaths": _resolved_owned_paths("theme-gallery"),
    }
    if snapshot.get("identity") != expected_identity:
        raise AssertionError("UX-1B theme fixture capture identity mismatch")
    if snapshot.get("blockedNetwork") != []:
        raise AssertionError("UX-1B theme fixture recorded blocked network attempts")
    return snapshot


def selection_case_from_url(url: str) -> str:
    """Resolve only one frozen focused route from the owned loopback origin."""

    try:
        parsed = urlsplit(str(url or ""))
        port = parsed.port
    except ValueError as exc:
        raise _configuration_error("selection fixture URL is malformed") from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.username is not None
        or parsed.password is not None
        or port is None
        or not 1 <= port <= 65535
        or parsed.fragment
    ):
        raise _configuration_error("selection fixture URL is not owned loopback HTTP")
    by_route = {item.route: name for name, item in SELECTION_CASES.items()}
    try:
        return by_route[parsed.path]
    except KeyError as exc:
        raise _configuration_error("selection fixture route is outside its catalog") from exc


def selection_capture_catalog() -> tuple[dict[str, Any], ...]:
    """Project all 36 focused captures and their eleven stable DOM roots."""

    rows: list[dict[str, Any]] = []
    for case_name, definition in SELECTION_CASES.items():
        controls = tuple(
            {
                "sessionKey": session_key,
                "rootSelector": root_selector,
                "flowScope": "main",
                "boundaryPolicy": "nearest-horizontal-block-or-element-container",
            }
            for session_key, root_selector in zip(
                definition.session_keys, definition.root_selectors
            )
        )
        for viewport_name, (width, height) in SELECTION_VIEWPORTS.items():
            rows.append(
                {
                    "case": case_name,
                    "route": definition.route,
                    "registryKey": definition.registry_key,
                    "callable": definition.callable_name,
                    "viewport": {
                        "name": viewport_name,
                        "width": width,
                        "height": height,
                    },
                    "controls": controls,
                }
            )
    return tuple(rows)


def _prepare_direct_selection_session(
    st_module: Any,
    definition: SelectionCase,
    capture_id: str,
    *,
    real_callable: str,
) -> None:
    capture = _validate_capture_id(capture_id)
    _set_capture_identity(
        definition.registry_key,
        capture,
        real_callable,
    )
    state = st_module.session_state
    if state.get(_CAPTURE_STATE_KEY) == capture:
        return
    st_module.cache_data.clear()
    state[_CAPTURE_STATE_KEY] = capture
    state[_ROUTE_STATE_KEY] = definition.registry_key
    increment_counter("session.setup", capture_id=capture)


def _selection_renderer(case_name: str) -> tuple[Callable[[], Any], Callable[[], Any] | None]:
    from ui import (
        ai_chat,
        analytics_db,
        institutions,
        knowledge_graph,
        options_cockpit,
        radar,
        retro_analysis,
        risk_guard,
        stock_checkup,
        today_decision,
    )

    renderers: Mapping[str, tuple[Callable[[], Any], Callable[[], Any] | None]] = {
        "risk-guard-controls": (risk_guard.render, None),
        "institutions-controls": (institutions.render, None),
        "options-cockpit-controls": (options_cockpit.render, None),
        "radar-controls": (radar.render, None),
        "knowledge-graph-controls": (knowledge_graph.render, None),
        "ai-chat-settings-controls": (today_decision.render, ai_chat.render),
        "retro-controls": (retro_analysis.render, None),
        "analytics-controls": (analytics_db.render, None),
        "stock-checkup-controls": (stock_checkup.render, None),
    }
    try:
        return renderers[case_name]
    except KeyError as exc:
        raise _configuration_error("selection case is outside its frozen catalog") from exc


def render_selection_case(case_name: str, capture_id: str) -> Any:
    """Render one focused case through its real production callable."""

    try:
        definition = SELECTION_CASES[str(case_name)]
    except KeyError as exc:
        raise _configuration_error("selection case is outside its frozen catalog") from exc
    import streamlit as st

    install_provider_fixtures()
    renderer, trailing_renderer = _selection_renderer(str(case_name))
    measured = _runtime_callable_identity(renderer)
    if measured != definition.callable_name:
        raise _configuration_error("selection renderer differs from its frozen callable")
    if definition.registry_key == "risk-guard":
        _prepare_direct_selection_session(
            st,
            definition,
            capture_id,
            real_callable=measured,
        )
    else:
        prepare_capture_session(
            st,
            definition.registry_key,
            capture_id,
            real_callable=measured,
        )

    state = st.session_state
    if str(case_name) == "radar-controls":
        _seed_radar_capture_state(state)

    with capture_context(capture_id):
        increment_counter("page.render.attempt")
        result = renderer()
        if trailing_renderer is not None:
            trailing_renderer()
        return result


class _FixturePage:
    def __init__(self, page: Any, st_module: Any) -> None:
        self._page = page
        self._st = st_module

    def __getattr__(self, name: str) -> Any:
        return getattr(self._page, name)

    def run(self) -> Any:
        route = str(getattr(self._page, "url_path", "") or "today-decision")
        route = route.strip("/") or "today-decision"
        capture = _capture_from_query_params(self._st)
        real_callable = _validated_runtime_callable(
            route,
            _streamlit_page_callable(self._page),
        )
        install_provider_fixtures()
        prepare_capture_session(
            self._st,
            route,
            capture,
            real_callable=real_callable,
        )
        with capture_context(capture):
            increment_counter("page.render.attempt")
            return self._page.run()


def install_navigation_proxy(st_module: Any) -> Callable[..., Any]:
    """Install exactly one proxy while retaining the original navigation call."""

    state = getattr(st_module, _NAV_SENTINEL, None)
    if isinstance(state, dict):
        proxy = state["proxy"]
        if st_module.navigation is not proxy:
            st_module.navigation = proxy
        return proxy

    original = st_module.navigation

    @functools.wraps(original)
    def navigation_proxy(*args, **kwargs):
        selected = original(*args, **kwargs)
        return _FixturePage(selected, st_module)

    setattr(navigation_proxy, _WRAPPER_MARKER, True)
    setattr(st_module, _NAV_SENTINEL, {"original": original, "proxy": navigation_proxy})
    st_module.navigation = navigation_proxy
    return navigation_proxy


@contextmanager
def navigation_proxy_context(st_module: Any) -> Iterator[Callable[..., Any]]:
    """Install and then fully restore the navigation proxy for AppTests."""

    previous_navigation = st_module.navigation
    previous_state = getattr(st_module, _NAV_SENTINEL, None)
    proxy = install_navigation_proxy(st_module)
    try:
        yield proxy
    finally:
        st_module.navigation = previous_navigation
        if previous_state is None:
            try:
                delattr(st_module, _NAV_SENTINEL)
            except AttributeError:
                pass
        else:
            setattr(st_module, _NAV_SENTINEL, previous_state)


def render_for_app_test(
    route: str,
    capture_id: str,
    render_function: Callable[[], Any],
) -> Any:
    """Run one real page render with fixtures active across AppTest reruns."""

    import streamlit as st

    if getattr(render_function, _WRAPPER_MARKER, False):
        raise AssertionError("UX-0 must never replace a page render function")
    normalized_route = str(route or "").strip("/") or "today-decision"
    if normalized_route not in TARGET_ROUTES:
        raise _configuration_error("selected page is outside the UX-0 fixture matrix")
    real_callable = _validated_runtime_callable(normalized_route, render_function)
    install_provider_fixtures()
    prepare_capture_session(
        st,
        normalized_route,
        capture_id,
        real_callable=real_callable,
    )
    with capture_context(capture_id):
        increment_counter("page.render.attempt")
        return render_function()
