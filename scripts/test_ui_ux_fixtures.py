#!/usr/bin/env python3
"""Focused UX-0 fixture safety and real-render contract tests.

Run with::

    .venv/bin/python scripts/test_ui_ux_fixtures.py
"""

from __future__ import annotations

import _socket
import _sqlite3
import builtins
import json
import os
import posix
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Iterator
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import ui_ux_fixtures as fixtures  # noqa: E402


FROZEN_ROUTES = (
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
)
FROZEN_CALLABLES = {
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


def test_ux1b_fragment_schedule_is_disabled_without_replacing_body() -> None:
    module = ModuleType("fixture_streamlit")
    calls: list[tuple[object, object]] = []

    def fragment(func=None, *, run_every=None):
        calls.append((func, run_every))
        if func is None:
            return lambda candidate: candidate
        return func

    module.fragment = fragment
    fixtures._install_deterministic_fragment_schedule(module)
    installed = module.fragment

    @module.fragment(run_every="8s")
    def body() -> str:
        return "real fragment body"

    assert body() == "real fragment body"
    assert calls == [(None, None)]
    assert getattr(installed, "_quant_radar_ux1b_no_periodic_rerun", False) is True
    fixtures._install_deterministic_fragment_schedule(module)
    assert module.fragment is installed

    def environment(profile: str | None) -> fixtures.FixtureEnvironment:
        return fixtures.FixtureEnvironment(
            fixture_root=Path("/fixture"),
            calls_path=Path("/calls.json"),
            run_dir=Path("/run"),
            run_token="x" * 43,
            fixed_now=fixtures.FIXED_NOW,
            profile=profile,
        )

    legacy = ModuleType("legacy_streamlit")
    legacy.fragment = fragment
    legacy_fragment = legacy.fragment
    fixtures._configure_deterministic_fragment_schedule(environment(None), legacy)
    assert legacy.fragment is legacy_fragment

    for profile in fixtures.UX1B_PROFILE_PHASES:
        ux1b = ModuleType(f"{profile}_streamlit")
        ux1b.fragment = fragment
        fixtures._configure_deterministic_fragment_schedule(
            environment(profile),
            ux1b,
        )
        assert getattr(
            ux1b.fragment,
            "_quant_radar_ux1b_no_periodic_rerun",
            False,
        ) is True


REQUIRED_ZERO_SENTINELS = {
    "mutator.production_read.attempt",
    "mutator.production_write.attempt",
    "mutator.subprocess.popen.attempt",
    "mutator.external_browser.attempt",
    "mutator.theme_flow.launch_background.attempt",
    "mutator.analytics.write_status.attempt",
    "mutator.x.auto_refresh.attempt",
}


@contextmanager
def _owned_environment() -> Iterator[dict[str, str]]:
    with tempfile.TemporaryDirectory(prefix="surge-ux0-fixtures-") as temp:
        run_dir = Path(temp).resolve()
        fixture_root = run_dir / "fixture-root"
        fixture_root.mkdir()
        token = secrets.token_urlsafe(32)
        (run_dir / fixtures.OWNERSHIP_MARKER).write_text(token, encoding="utf-8")
        calls_path = run_dir / "fixture-calls.json"
        values = {
            "QUANT_RADAR_UX0_FIXTURES": "1",
            "QUANT_RADAR_UX0_FIXTURE_ROOT": str(fixture_root),
            "QUANT_RADAR_UX0_CALLS_PATH": str(calls_path),
            "QUANT_RADAR_UX0_RUN_TOKEN": token,
            "QUANT_RADAR_UX0_FIXED_NOW": "2026-07-15T06:30:00Z",
            "SURGE_RUNTIME_DIR": str(fixture_root),
            "SURGE_CANDIDATE_OUTPUT_DIR": str(fixture_root / "candidates"),
            "SURGE_AI_CHAT_DIR": str(fixture_root / "ai-chat"),
            "TZ": "UTC",
        }
        with patch.dict(os.environ, values, clear=False):
            yield values


def _ux1b_environment(values: dict[str, str]) -> dict[str, str]:
    fixture_root = Path(values["SURGE_RUNTIME_DIR"])
    proxy = "http://127.0.0.1:18502"
    return {
        **values,
        "QUANT_RADAR_UX1B_PROFILE": "ux1b-full-pages",
        "QUANT_RADAR_UX1B_PHASE": "pretheme",
        "QUANT_RADAR_UX1B_STREAMLIT_PORT": "18501",
        "QUANT_RADAR_UX1B_DENY_PROXY_PORT": "18502",
        "SURGE_ANALYTICS_DIR": str(fixture_root / "analytics"),
        "HTTP_PROXY": proxy,
        "HTTPS_PROXY": proxy,
        "ALL_PROXY": proxy,
    }


@contextmanager
def _owned_app_contract_environment(
    *,
    profile: str = "ux1b-full-pages",
    phase: str = "precontrol",
) -> Iterator[dict[str, str]]:
    """Build the file-carried contract used by the exact app sandbox env."""

    with tempfile.TemporaryDirectory(prefix="surge-ux1b-app-contract-") as temp:
        parent = Path(temp).resolve()
        app_root = parent / "app"
        app_root.mkdir(mode=0o700)
        home = app_root / "home"
        fixture_root = app_root / "fixture-root"
        for path in (home, fixture_root):
            path.mkdir(mode=0o700)
        token = secrets.token_urlsafe(32)
        marker = app_root / fixtures.OWNERSHIP_MARKER
        marker.write_text(token, encoding="utf-8")
        marker.chmod(0o600)
        contract_path = home / fixtures.UX1B_RUN_CONTRACT_FILENAME
        contract = fixtures.build_owned_run_contract(
            run_token=token,
            profile=profile,
            phase=phase,
            streamlit_port=18501,
            deny_proxy_port=18502,
        )
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        contract_path.chmod(0o600)
        values = {
            "HOME": str(home),
            "SOURCE_ROOT": str(fixtures._REPO_ROOT),
            "QUANT_RADAR_UX1B_ROLE": "app",
            "TZ": "UTC",
        }
        yield values


def test_owned_app_contract_replaces_legacy_fixture_environment_projection() -> None:
    with _owned_app_contract_environment() as values:
        parsed = fixtures.validate_fixture_environment(values)
        assert parsed.fixture_root == Path(values["HOME"]).parent / "fixture-root"
        assert parsed.calls_path == Path(values["HOME"]).parent / "fixture-calls.json"
        assert parsed.run_dir == Path(values["HOME"]).parent
        assert parsed.source_root == Path(values["SOURCE_ROOT"])
        assert parsed.profile == "ux1b-full-pages"
        assert parsed.phase == "precontrol"
        assert parsed.streamlit_port == 18501
        assert parsed.deny_proxy_port == 18502

        result = _run_fixture_bootstrap(values)
        assert result.returncode == 0, result.stdout + result.stderr
        counter = json.loads(parsed.calls_path.read_text(encoding="utf-8"))
        assert counter == {
            "schemaVersion": 1,
            "fixtureRevision": fixtures.UX1B_FIXTURE_REVISION,
            "contractSchema": fixtures.UX1B_CONTRACT_SCHEMA_VERSION,
            "captures": {},
            "bootstrapBlockedNetwork": [],
        }

        ambiguous = dict(values)
        ambiguous["QUANT_RADAR_UX0_FIXTURES"] = "1"
        try:
            fixtures.validate_fixture_environment(ambiguous)
        except fixtures.FixtureConfigurationError as exc:
            assert "legacy" in str(exc).lower() or "ambiguous" in str(exc).lower()
        else:
            raise AssertionError("owned app contract accepted legacy environment authority")


def test_ux1b_profile_phase_matrix_is_exact() -> None:
    accepted = {
        "ux1b-full-pages": {"precontrol", "pretheme", "posttheme"},
        "ux1b-selection-controls": {"precontrol", "postcontrol"},
        "ux1b-theme": {"posttheme"},
    }
    for profile, phases in accepted.items():
        for phase in phases:
            with _owned_app_contract_environment(profile=profile, phase=phase) as values:
                parsed = fixtures.validate_fixture_environment(values)
            assert (parsed.profile, parsed.phase) == (profile, phase)

    rejected = (
        ("ux1b-selection-controls", "pretheme"),
        ("ux1b-selection-controls", "posttheme"),
        ("ux1b-full-pages", "invented"),
        ("ux1b-theme", "pretheme"),
        ("invented", "precontrol"),
    )
    for profile, phase in rejected:
        try:
            fixtures.build_owned_run_contract(
                run_token=secrets.token_urlsafe(32),
                profile=profile,
                phase=phase,
                streamlit_port=18501,
                deny_proxy_port=18502,
            )
        except fixtures.FixtureConfigurationError:
            pass
        else:
            raise AssertionError(f"accepted invalid fixture phase {profile}/{phase}")


def test_theme_gallery_counter_contract_is_real_and_once_per_session() -> None:
    with _owned_app_contract_environment(
        profile="ux1b-theme",
        phase="posttheme",
    ) as values:
        result = _run_fixture_script(
            values,
            """
from types import SimpleNamespace
from scripts import ui_ux_fixtures as fixture

fixture.bootstrap_fixture_environment()
st = SimpleNamespace(
    query_params={"ux0_capture": "theme-gallery/desktop"},
    session_state={},
)
fixture.record_theme_gallery_render(st)
fixture.record_theme_gallery_render(st)
snapshot = fixture.assert_theme_counter_contract("theme-gallery/desktop")
if snapshot["counts"] != {"theme.gallery.render": 1}:
    raise SystemExit(f"theme render counter differs: {snapshot!r}")
identity = snapshot["identity"]
if identity["selectedRegistryKey"] != "theme-gallery":
    raise SystemExit("theme registry identity differs")
if identity["realCallable"] != "ui_ux_theme_fixture_app":
    raise SystemExit("theme callable identity differs")
if not identity["resolvedOwnedPaths"]:
    raise SystemExit("theme owned-path contract is empty")
""",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        calls_path = Path(values["HOME"]).parent / "fixture-calls.json"
        document = json.loads(calls_path.read_text(encoding="utf-8"))
    bucket = document["captures"]["theme-gallery/desktop"]
    assert bucket["counts"] == {"theme.gallery.render": 1}
    assert bucket["blockedNetwork"] == []
    assert bucket["identity"]["resolvedOwnedPaths"]


def test_owned_app_contract_rejects_mode_and_shape_drift() -> None:
    with _owned_app_contract_environment() as values:
        path = Path(values["HOME"]) / fixtures.UX1B_RUN_CONTRACT_FILENAME
        original = path.read_text(encoding="utf-8")
        path.chmod(0o644)
        try:
            fixtures.validate_fixture_environment(values)
        except fixtures.FixtureConfigurationError as exc:
            assert "identity" in str(exc).lower()
        else:
            raise AssertionError("owned app contract accepted a public file mode")

        path.chmod(0o600)
        malformed = json.loads(original)
        malformed["fixtureRoot"] = "/untrusted/authority"
        path.write_text(
            json.dumps(malformed, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        path.chmod(0o600)
        try:
            fixtures.validate_fixture_environment(values)
        except fixtures.FixtureConfigurationError as exc:
            assert "shape" in str(exc).lower()
        else:
            raise AssertionError("owned app contract accepted a path-bearing extra key")


def _run_fixture_bootstrap(values: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return _run_fixture_script(
        values,
        (
            "from scripts.ui_ux_fixtures import bootstrap_fixture_environment; "
            "bootstrap_fixture_environment()"
        ),
    )


def _run_fixture_script(
    values: dict[str, str],
    source: str,
) -> subprocess.CompletedProcess[str]:
    child_env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("QUANT_RADAR_UX0_", "QUANT_RADAR_UX1B_"))
    }
    child_env.update(values)
    return subprocess.run(
        [
            sys.executable,
            "-c",
            source,
        ],
        cwd=ROOT,
        env=child_env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_ux1b_network_allowlist_is_two_exact_ipv4_destinations() -> None:
    with _owned_environment() as values:
        profile = _ux1b_environment(values)
        result = _run_fixture_script(
            profile,
            """
import socket
from scripts import ui_ux_fixtures as fixture

fixture.bootstrap_fixture_environment()
for host, port in (("127.0.0.1", 18501), (b"127.0.0.1", 18502)):
    if not socket.getaddrinfo(host, port):
        raise SystemExit("owned destination did not resolve")

rejected = (
    ("localhost", 18501),
    ("localhost.localdomain", 18501),
    ("::1", 18501),
    ("127.0.0.2", 18501),
    ("127.255.255.254", 18501),
    ("127.0.0.1", 18503),
)
with fixture.capture_context("ux1b-exact-network"):
    for host, port in rejected:
        try:
            socket.getaddrinfo(host, port)
        except fixture.BlockedExternalNetworkError:
            pass
        else:
            raise SystemExit(f"unexpectedly allowed {host}:{port}")
    try:
        socket.gethostbyname("127.0.0.1")
    except fixture.BlockedExternalNetworkError:
        pass
    else:
        raise SystemExit("unexpectedly allowed a destination without an owned port")
""",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        document = json.loads(
            Path(values["QUANT_RADAR_UX0_CALLS_PATH"]).read_text(encoding="utf-8")
        )
    assert document["bootstrapBlockedNetwork"] == []
    assert document["captures"]["ux1b-exact-network"]["blockedNetwork"] == [
        {"kind": "dns", "target": "localhost:18501"},
        {"kind": "dns", "target": "localhost.localdomain:18501"},
        {"kind": "dns", "target": "::1:18501"},
        {"kind": "dns", "target": "127.0.0.2:18501"},
        {"kind": "dns", "target": "127.255.255.254:18501"},
        {"kind": "dns", "target": "127.0.0.1:18503"},
        {"kind": "dns", "target": "127.0.0.1"},
    ]


def test_symlink_and_directory_fd_production_bypasses_fail_closed() -> None:
    production_dir = ROOT / "reports"
    production_file = production_dir / "performance_ledger.csv"
    with _owned_environment() as values:
        alias = Path(values["QUANT_RADAR_UX0_FIXTURE_ROOT"]).parent / "report-alias"
        alias.symlink_to(production_dir, target_is_directory=True)
        profile = _ux1b_environment(values)
        result = _run_fixture_script(
            profile,
            f"""
import os
import posix
from pathlib import Path
from scripts import ui_ux_fixtures as fixture

directory_fd = os.open({str(production_dir)!r}, os.O_RDONLY)
fixture.bootstrap_fixture_environment()
cases = (
    ("symlink-read", lambda: Path({str(alias)!r}).exists(), fixture.BlockedProductionArtifactError),
    ("dirfd-read", lambda: os.stat("performance_ledger.csv", dir_fd=directory_fd), fixture.BlockedProductionArtifactError),
    ("dirfd-open", lambda: os.open("performance_ledger.csv", os.O_RDONLY, dir_fd=directory_fd), fixture.BlockedProductionArtifactError),
    ("dirfd-write", lambda: os.unlink("performance_ledger.csv", dir_fd=directory_fd), fixture.BlockedProductionArtifactError),
    ("posix-fstat", lambda: posix.fstat(directory_fd), fixture.BlockedProductionArtifactError),
    ("posix-fchmod", lambda: posix.fchmod(directory_fd, 0o755), fixture.BlockedProductionArtifactError),
)
try:
    for capture, action, expected in cases:
        with fixture.capture_context(capture):
            try:
                action()
            except expected:
                pass
            else:
                raise SystemExit(f"bypass was allowed: {{capture}}")
finally:
    os.close(directory_fd)
""",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        document = json.loads(
            Path(values["QUANT_RADAR_UX0_CALLS_PATH"]).read_text(encoding="utf-8")
        )
        assert production_file.is_file()
    captures = document["captures"]
    for capture in ("symlink-read", "dirfd-read", "dirfd-open", "posix-fstat"):
        assert captures[capture]["counts"] == {
            "mutator.production_read.attempt": 1
        }
    assert captures["dirfd-write"]["counts"] == {
        "mutator.production_write.attempt": 1
    }
    assert captures["posix-fchmod"]["counts"] == {
        "mutator.production_write.attempt": 1
    }


def test_low_level_module_aliases_are_guarded_and_idempotent() -> None:
    production_file = ROOT / "ranked_candidates.json"
    production_dir = ROOT / "reports"
    with _owned_environment() as values:
        profile = _ux1b_environment(values)
        result = _run_fixture_script(
            profile,
            f"""
import _socket
import _sqlite3
import builtins
import os
import posix
import socket
import sqlite3
import subprocess
from pathlib import Path
from scripts import ui_ux_fixtures as fixture

receiver = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
receiver.bind(("127.0.0.1", 0))
dummy_port = receiver.getsockname()[1]
if dummy_port in {{18501, 18502}}:
    raise SystemExit("dummy port collided with an owned port")
receiver.settimeout(0.15)

fixture.bootstrap_fixture_environment()

# Exercise idempotent repair after public aliases are overwritten.
_socket.socket = lambda *_args, **_kwargs: None
posix.open = lambda *_args, **_kwargs: None
_sqlite3.connect = lambda *_args, **_kwargs: None
fixture.install_network_guard()
fixture.install_filesystem_guard()

if not (socket.socket is socket.SocketType is _socket.socket is _socket.SocketType):
    raise SystemExit("socket constructor aliases diverged")
for name in (
    "getaddrinfo", "gethostbyaddr", "gethostbyname",
    "gethostbyname_ex", "getnameinfo",
):
    if getattr(socket, name) is not getattr(_socket, name):
        raise SystemExit(f"socket resolver alias diverged: {{name}}")
for name in (
    "open", "stat", "lstat", "listdir", "scandir", "access",
    "readlink", "unlink", "remove", "rename", "replace", "mkdir",
    "rmdir", "chmod", "truncate", "utime", "link", "symlink",
    "pathconf", "statvfs", "fpathconf", "fstat", "fstatvfs",
    "fchmod", "fchown", "ftruncate", "chflags", "lchflags",
    "lchmod", "lchown", "mkfifo", "mknod",
):
    if hasattr(posix, name) and getattr(os, name) is not getattr(posix, name):
        raise SystemExit(f"posix alias diverged: {{name}}")
if not (sqlite3.connect is sqlite3.dbapi2.connect is _sqlite3.connect):
    raise SystemExit("sqlite connect aliases diverged")
if not (sqlite3.Connection is sqlite3.dbapi2.Connection is _sqlite3.Connection):
    raise SystemExit("sqlite Connection aliases diverged")

network_state = getattr(socket, "_quant_radar_ux0_network_guard")
filesystem_state = getattr(builtins, "_quant_radar_ux1b_filesystem_guard")
if any("original" in key.lower() for key in network_state | filesystem_state):
    raise SystemExit("a guard sentinel exposed an original alias")
guarded_exports = [
    builtins.open,
    subprocess.Popen,
    sqlite3.connect,
    _sqlite3.connect,
    _socket.socketpair,
]
guarded_exports.extend(
    getattr(_socket, name)
    for name in (
        "getaddrinfo", "gethostbyaddr", "gethostbyname",
        "gethostbyname_ex", "getnameinfo",
    )
)
guarded_exports.extend(
    getattr(posix, name)
    for name in (
        "open", "chmod", "mkdir", "rename", "replace", "symlink",
        "truncate", "unlink",
    )
)
if any(hasattr(value, "__wrapped__") for value in guarded_exports):
    raise SystemExit("a guarded export exposed functools.__wrapped__")

with fixture.capture_context("low-socket-send"):
    sender = _socket.SocketType(_socket.AF_INET, _socket.SOCK_DGRAM)
    try:
        try:
            sender.sendto(b"must-not-arrive", ("127.0.0.1", dummy_port))
        except fixture.BlockedExternalNetworkError:
            pass
        else:
            raise SystemExit("raw socket alias delivered to a wrong port")
    finally:
        sender.close()
try:
    payload, _address = receiver.recvfrom(4096)
except (TimeoutError, _socket.timeout):
    payload = b""
finally:
    receiver.close()
if payload:
    raise SystemExit("dummy receiver got bytes from a blocked socket alias")

for constructor in (socket.fromfd,):
    left, right = socket.socketpair()
    try:
        duplicate = constructor(left.fileno(), left.family, left.type, left.proto)
        try:
            if not isinstance(duplicate, socket.socket):
                raise SystemExit("fromfd returned an unguarded socket")
        finally:
            duplicate.close()
    finally:
        left.close()
        right.close()
left, right = _socket.socketpair()
try:
    if not all(isinstance(item, socket.socket) for item in (left, right)):
        raise SystemExit("_socket.socketpair returned a raw socket")
finally:
    left.close()
    right.close()

run_dir = Path({str(Path(values['QUANT_RADAR_UX0_FIXTURE_ROOT']).parent)!r})
replace_source = run_dir / "low-level-replace-source.txt"
replace_source.write_text("owned", encoding="utf-8")
filesystem_cases = (
    ("low-posix-open", lambda: posix.open({str(production_file)!r}, os.O_RDONLY), fixture.BlockedProductionArtifactError, "mutator.production_read.attempt"),
    ("low-posix-stat", lambda: posix.stat({str(production_file)!r}), fixture.BlockedProductionArtifactError, "mutator.production_read.attempt"),
    ("low-posix-scandir", lambda: list(posix.scandir({str(production_dir)!r})), fixture.BlockedProductionArtifactError, "mutator.production_read.attempt"),
    ("low-posix-unlink", lambda: posix.unlink({str(production_file)!r}), fixture.BlockedProductionArtifactError, "mutator.production_write.attempt"),
    ("low-posix-rename", lambda: posix.rename({str(production_file)!r}, run_dir / "escaped.json"), fixture.BlockedProductionArtifactError, "mutator.production_write.attempt"),
    ("low-posix-replace", lambda: posix.replace(replace_source, {str(ROOT / 'scored_candidates.json')!r}), fixture.BlockedProductionArtifactError, "mutator.production_write.attempt"),
    ("low-sqlite-connect", lambda: _sqlite3.connect("file:{str(production_file)}?mode=ro", uri=True), fixture.BlockedProductionArtifactError, "mutator.production_read.attempt"),
    ("low-sqlite-connection", lambda: _sqlite3.Connection({str(ROOT / 'scored_candidates.json')!r}), fixture.BlockedProductionArtifactError, "mutator.production_write.attempt"),
)
for capture, action, expected_error, counter in filesystem_cases:
    with fixture.capture_context(capture):
        try:
            action()
        except expected_error:
            pass
        else:
            raise SystemExit(f"low-level alias bypassed guard: {{capture}}")
    if fixture.counter_snapshot(capture)["counts"] != {{counter: 1}}:
        raise SystemExit(f"low-level counter mismatch: {{capture}}")
if replace_source.read_text(encoding="utf-8") != "owned":
    raise SystemExit("blocked replace consumed its source")
network = fixture.counter_snapshot("low-socket-send")["blockedNetwork"]
if network != [{{"kind": "sendto", "target": f"127.0.0.1:{{dummy_port}}"}}]:
    raise SystemExit(f"low-level socket record mismatch: {{network}}")
""",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        document = json.loads(
            Path(values["QUANT_RADAR_UX0_CALLS_PATH"]).read_text(encoding="utf-8")
        )
        assert production_file.is_file()
    assert document["captures"]["low-socket-send"]["blockedNetwork"][0][
        "kind"
    ] == "sendto"


def _app_text(app: AppTest) -> str:
    values: list[str] = []
    for elements in (
        app.title,
        app.header,
        app.subheader,
        app.caption,
        app.warning,
        app.info,
        app.error,
        app.markdown,
        app.metric,
        app.dataframe,
        app.table,
    ):
        values.extend(str(element.value) for element in elements)
    values.extend(str(element.label) for element in app.metric)
    return "\n".join(values)


def _wrapper(module_name: str, route: str, capture: str) -> str:
    return (
        f"from ui import {module_name}\n"
        "from scripts.ui_ux_fixtures import render_for_app_test\n"
        f"render_for_app_test({route!r}, {capture!r}, {module_name}.render)\n"
    )


def _x_wrapper(market: str, route: str, capture: str) -> str:
    wrapper_name = "us_x" if market == "US" else "crypto_x"
    return (
        "from ui import x_sentiment\n"
        "from scripts.ui_ux_fixtures import render_for_app_test\n"
        f"def {wrapper_name}():\n"
        f"    return x_sentiment.render({market!r})\n"
        f"render_for_app_test({route!r}, {capture!r}, {wrapper_name})\n"
    )


def test_full_route_fixture_contract_is_frozen() -> None:
    expected = set(FROZEN_ROUTES)
    assert fixtures.TARGET_ROUTES == expected
    assert dict(fixtures.ROUTE_RENDER_CALLABLES) == FROZEN_CALLABLES
    assert set(fixtures.ROUTE_COUNTER_CONTRACTS) == expected
    assert set(fixtures.ROUTE_OWNED_PATHS) == expected

    for route in FROZEN_ROUTES:
        contract = fixtures.ROUTE_COUNTER_CONTRACTS[route]
        positive = contract["positive"]
        zero = set(contract["zero"])
        assert positive["session.setup"] == 1, (route, positive)
        assert positive["page.render.attempt"] == 1, (route, positive)
        assert all(isinstance(count, int) and count > 0 for count in positive.values())
        assert not (set(positive) & zero), route
        assert REQUIRED_ZERO_SENTINELS <= zero, (route, zero)

        owned = fixtures.ROUTE_OWNED_PATHS[route]
        assert owned, route
        for relative in owned.values():
            path = Path(relative)
            assert not path.is_absolute(), (route, relative)
            assert ".." not in path.parts, (route, relative)


def _root_candidate_artifacts(root: Path) -> set[str]:
    candidate_tokens = (
        "candidate",
        "universe",
        "filtered",
        "ranked",
        "scored",
        "layer2",
        "dd_results",
    )
    return {
        path.name
        for path in root.glob("*.json")
        if any(token in path.stem for token in candidate_tokens)
    }


def test_production_root_candidate_artifact_inventory_is_complete() -> None:
    deployed = {
        "filtered_universe.json",
        "ranked_candidates.json",
        "scored_candidates.json",
        "layer2_results.json",
        "dd_results.json",
    }
    known_legacy = {
        "filtered_universe_sp1500.json",
        "filtered_nasdaq.json",
        "crypto_scored.json",
    }
    assert fixtures.PRODUCTION_ROOT_CANDIDATE_ARTIFACTS == deployed | known_legacy

    discovered = _root_candidate_artifacts(ROOT)
    assert discovered <= fixtures.PRODUCTION_ROOT_CANDIDATE_ARTIFACTS
    assert {"filtered_universe.json", "ranked_candidates.json"} <= discovered

    with tempfile.TemporaryDirectory() as tmp:
        unknown = Path(tmp) / "candidate_unknown.json"
        unknown.write_text("{}", encoding="utf-8")
        probed = _root_candidate_artifacts(Path(tmp))
    assert probed == {unknown.name}
    assert not probed <= fixtures.PRODUCTION_ROOT_CANDIDATE_ARTIFACTS


def test_fixed_schema_regressions_are_closed() -> None:
    ledger = fixtures._fixed_ledger_frame()
    required_ledger = {
        "ticker",
        "scan_date",
        "fwd_30d_return",
        "max_drawdown_30d",
        "hit_15pct_within_30d",
    }
    assert required_ledger <= set(ledger.columns)
    assert ledger.loc[0, "ticker"] == "NVDA"
    assert ledger.loc[0, "fwd_30d_return"] == 12.5

    sector = fixtures._fixed_sector_flow()
    row = sector["sectors"][0]
    assert row["group"] == "主板塊"
    assert row["theme"] == "資訊科技"


def test_analytics_fixture_has_two_tables_and_fail_soft_empty_projection() -> None:
    catalog = fixtures._fixed_analytics_catalog()
    assert [row["table_name"] for row in catalog] == [
        "candidate_rankings",
        "iv_history",
    ]
    assert all(row["row_count"] > 0 and row["column_count"] > 0 for row in catalog)
    assert fixtures._fixed_analytics_catalog(empty=True) == []

    assert fixtures._fixed_analytics_columns("candidate_rankings") == [
        "ticker",
        "scan_date",
        "rank",
        "composite_score",
    ]
    assert fixtures._fixed_analytics_tickers("candidate_rankings") == ["NVDA", "AMD"]
    frame = fixtures._fixed_analytics_table("candidate_rankings")
    assert frame["ticker"].tolist() == ["NVDA", "AMD"]
    assert frame["scan_date"].tolist() == ["2026-07-15", "2026-07-15"]


def test_ux1b_profile_requires_exact_runtime_identity() -> None:
    with _owned_environment() as values:
        profile = _ux1b_environment(values)
        parsed = fixtures.validate_fixture_environment(profile)
        assert parsed.profile == "ux1b-full-pages"
        assert parsed.phase == "pretheme"
        assert parsed.streamlit_port == 18501
        assert parsed.deny_proxy_port == 18502

        missing_port = dict(profile)
        missing_port.pop("QUANT_RADAR_UX1B_DENY_PROXY_PORT")
        try:
            fixtures.validate_fixture_environment(missing_port)
        except fixtures.FixtureConfigurationError as exc:
            assert "deny" in str(exc).lower() or "port" in str(exc).lower()
        else:
            raise AssertionError("UX-1B profile accepted a missing deny-proxy port")


def test_counter_revision_is_profile_specific_and_schema_stays_compatible() -> None:
    assert fixtures.COUNTER_SCHEMA_VERSION == 1
    assert fixtures.FIXTURE_REVISION == "quant-radar-ux0-2026-07-16.2"
    assert fixtures.UX1B_FIXTURE_REVISION == "quant-radar-ux1b-2026-07-16.1"
    assert fixtures.UX1B_CONTRACT_SCHEMA_VERSION == 1

    with _owned_environment() as values:
        result = _run_fixture_bootstrap(values)
        assert result.returncode == 0, result.stdout + result.stderr
        legacy = json.loads(
            Path(values["QUANT_RADAR_UX0_CALLS_PATH"]).read_text(encoding="utf-8")
        )
    assert legacy == {
        "schemaVersion": 1,
        "fixtureRevision": "quant-radar-ux0-2026-07-16.2",
        "captures": {},
        "bootstrapBlockedNetwork": [],
    }

    with _owned_environment() as values:
        profile = _ux1b_environment(values)
        result = _run_fixture_bootstrap(profile)
        assert result.returncode == 0, result.stdout + result.stderr
        ux1b = json.loads(
            Path(values["QUANT_RADAR_UX0_CALLS_PATH"]).read_text(encoding="utf-8")
        )
    assert ux1b == {
        "schemaVersion": 1,
        "contractSchema": 1,
        "fixtureRevision": "quant-radar-ux1b-2026-07-16.1",
        "captures": {},
        "bootstrapBlockedNetwork": [],
    }


def test_existing_counter_profile_mismatches_fail_closed() -> None:
    base = {
        "schemaVersion": 1,
        "captures": {},
        "bootstrapBlockedNetwork": [],
    }
    cases = (
        (
            False,
            {
                **base,
                "fixtureRevision": fixtures.UX1B_FIXTURE_REVISION,
                "contractSchema": 1,
            },
            "revision is incompatible",
        ),
        (
            True,
            {**base, "fixtureRevision": fixtures.FIXTURE_REVISION},
            "revision is incompatible",
        ),
        (
            True,
            {**base, "fixtureRevision": fixtures.UX1B_FIXTURE_REVISION},
            "contract schema is incompatible",
        ),
        (
            True,
            {
                **base,
                "fixtureRevision": fixtures.UX1B_FIXTURE_REVISION,
                "contractSchema": 2,
            },
            "contract schema is incompatible",
        ),
        (
            False,
            {
                **base,
                "fixtureRevision": fixtures.FIXTURE_REVISION,
                "contractSchema": 1,
            },
            "must not declare",
        ),
    )
    for ux1b_profile, document, expected_error in cases:
        with _owned_environment() as values:
            calls = Path(values["QUANT_RADAR_UX0_CALLS_PATH"])
            calls.write_text(json.dumps(document), encoding="utf-8")
            environment = _ux1b_environment(values) if ux1b_profile else values
            result = _run_fixture_bootstrap(environment)
            combined = result.stdout + result.stderr
            assert result.returncode != 0, document
            assert expected_error in combined.lower(), (document, combined)
            assert values["QUANT_RADAR_UX0_RUN_TOKEN"] not in combined


def test_environment_validation_fails_closed() -> None:
    empty = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("QUANT_RADAR_UX0_")
    }
    try:
        fixtures.validate_fixture_environment(empty)
    except fixtures.FixtureConfigurationError as exc:
        assert "opt-in" in str(exc).lower()
    else:
        raise AssertionError("missing opt-in was accepted")

    with tempfile.TemporaryDirectory(prefix="surge-ux0-invalid-") as temp:
        run_dir = Path(temp).resolve()
        root = run_dir / "fixture-root"
        root.mkdir()
        calls = run_dir / "fixture-calls.json"
        token = secrets.token_urlsafe(32)
        (run_dir / fixtures.OWNERSHIP_MARKER).write_text("wrong-token", encoding="utf-8")
        invalid = {
            "QUANT_RADAR_UX0_FIXTURES": "1",
            "QUANT_RADAR_UX0_FIXTURE_ROOT": str(root),
            "QUANT_RADAR_UX0_CALLS_PATH": str(calls),
            "QUANT_RADAR_UX0_RUN_TOKEN": token,
            "QUANT_RADAR_UX0_FIXED_NOW": "2026-07-15T06:30:00Z",
            "SURGE_RUNTIME_DIR": str(root),
            "SURGE_CANDIDATE_OUTPUT_DIR": str(root / "candidates"),
            "SURGE_AI_CHAT_DIR": str(root / "ai-chat"),
            "TZ": "UTC",
        }
        try:
            fixtures.validate_fixture_environment(invalid)
        except fixtures.FixtureConfigurationError as exc:
            assert "ownership" in str(exc).lower()
            assert token not in str(exc)
        else:
            raise AssertionError("mismatched ownership marker was accepted")

    root = (ROOT / "ui").resolve()
    calls = ROOT / "fixture-calls.json"
    token = secrets.token_urlsafe(32)
    invalid = {
        "QUANT_RADAR_UX0_FIXTURES": "1",
        "QUANT_RADAR_UX0_FIXTURE_ROOT": str(root),
        "QUANT_RADAR_UX0_CALLS_PATH": str(calls),
        "QUANT_RADAR_UX0_RUN_TOKEN": token,
        "QUANT_RADAR_UX0_FIXED_NOW": "2026-07-15T06:30:00Z",
        "SURGE_RUNTIME_DIR": str(root),
        "SURGE_CANDIDATE_OUTPUT_DIR": str(root / "candidates"),
        "SURGE_AI_CHAT_DIR": str(root / "ai-chat"),
        "TZ": "UTC",
    }
    try:
        fixtures.validate_fixture_environment(invalid)
    except fixtures.FixtureConfigurationError as exc:
        assert "repository source" in str(exc).lower()
        assert token not in str(exc)
    else:
        raise AssertionError("fixture root inside repository source was accepted")


def test_entrypoint_fails_before_streamlit_without_opt_in() -> None:
    child_env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("QUANT_RADAR_UX0_")
    }
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "ui_ux_fixture_app.py")],
        cwd=ROOT,
        env=child_env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined
    assert "fixture opt-in" in combined.lower(), combined
    assert "ui.today_decision" not in combined
    assert "ui_ux_fixtures" not in (ROOT / "app.py").read_text(encoding="utf-8")


def test_owned_environment_and_atomic_counters(environment: fixtures.FixtureEnvironment) -> None:
    assert environment.fixture_root.name == "fixture-root"
    assert environment.calls_path.parent == environment.fixture_root.parent

    capture = "counter-thread-safety"
    workers = 8
    per_worker = 25

    def increment() -> None:
        for _ in range(per_worker):
            fixtures.increment_counter("unit.concurrent", capture_id=capture)

    threads = [threading.Thread(target=increment) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()

    snapshot = fixtures.counter_snapshot(capture)
    assert snapshot["counts"]["unit.concurrent"] == workers * per_worker
    raw = json.loads(environment.calls_path.read_text(encoding="utf-8"))
    assert raw["schemaVersion"] == 1
    assert raw["fixtureRevision"] == fixtures.FIXTURE_REVISION
    assert raw["captures"][capture]["blockedNetwork"] == []
    assert environment.run_token not in environment.calls_path.read_text(encoding="utf-8")


def test_network_guard_blocks_without_contacting_destination(
    environment: fixtures.FixtureEnvironment,
) -> None:
    before = json.loads(environment.calls_path.read_text(encoding="utf-8"))
    with fixtures.capture_context("network-guard"):
        try:
            socket.getaddrinfo("198.51.100.10", 443)
        except fixtures.BlockedExternalNetworkError as exc:
            assert "198.51.100.10" not in str(exc)
        else:
            raise AssertionError("external literal address was not blocked")
        outbound = socket.socket()
        try:
            try:
                outbound.connect(("198.51.100.11", 443))
            except fixtures.BlockedExternalNetworkError as exc:
                assert "198.51.100.11" not in str(exc)
            else:
                raise AssertionError("external socket connection was not blocked")
        finally:
            outbound.close()
        for kind, action in (
            ("dns_reverse", lambda: socket.gethostbyaddr("198.51.100.12")),
            (
                "dns_reverse",
                lambda: socket.getnameinfo(("198.51.100.13", 443), 0),
            ),
        ):
            try:
                action()
            except fixtures.BlockedExternalNetworkError:
                pass
            else:
                raise AssertionError(f"external {kind} lookup was not blocked")

        datagram = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sendmsg_supported = hasattr(datagram, "sendmsg")
        try:
            if sendmsg_supported:
                try:
                    datagram.sendmsg(
                        [b"ux0"], [], 0, ("198.51.100.14", 53)
                    )
                except fixtures.BlockedExternalNetworkError:
                    pass
                else:
                    raise AssertionError("external UDP sendmsg was not blocked")
        finally:
            datagram.close()

    for legacy_loopback in (
        "127.0.0.1",
        "127.0.0.2",
        "localhost",
        "localhost.localdomain",
        "::1",
    ):
        try:
            socket.getaddrinfo(legacy_loopback, 8501)
        except fixtures.BlockedExternalNetworkError as exc:
            raise AssertionError(
                f"legacy loopback behavior rejected {legacy_loopback}"
            ) from exc
        except socket.gaierror:
            # The legacy policy allows this name; the host resolver is not
            # required to define every conventional loopback alias.
            pass
    after = json.loads(environment.calls_path.read_text(encoding="utf-8"))
    records = after["captures"]["network-guard"]["blockedNetwork"]
    expected_records = [
        {"kind": "dns", "target": "198.51.100.10"},
        {"kind": "connect", "target": "198.51.100.11"},
        {"kind": "dns_reverse", "target": "198.51.100.12"},
        {"kind": "dns_reverse", "target": "198.51.100.13"},
    ]
    if sendmsg_supported:
        expected_records.append({"kind": "sendmsg", "target": "198.51.100.14"})
    assert records == expected_records
    assert before["bootstrapBlockedNetwork"] == after["bootstrapBlockedNetwork"]


def test_process_and_production_artifact_guards(
    environment: fixtures.FixtureEnvironment,
) -> None:
    def assert_blocked(
        capture: str,
        action,
        expected_error: type[Exception],
        counter: str,
    ) -> None:
        with fixtures.capture_context(capture):
            try:
                action()
            except expected_error:
                pass
            else:
                raise AssertionError(f"fixture guard allowed {capture}")
        assert fixtures.counter_snapshot(capture)["counts"] == {counter: 1}

    with fixtures.capture_context("process-guard"):
        try:
            subprocess.Popen([sys.executable, "-c", "raise SystemExit(99)"])
        except fixtures.BlockedFixtureMutationError:
            pass
        else:
            raise AssertionError("fixture subprocess guard allowed a child process")
    process = fixtures.counter_snapshot("process-guard")
    assert process["counts"] == {"mutator.subprocess.popen.attempt": 1}

    with fixtures.capture_context("production-read-guard"):
        try:
            (ROOT / "reports" / "performance_ledger.csv").read_text(encoding="utf-8")
        except fixtures.BlockedProductionArtifactError:
            pass
        else:
            raise AssertionError("fixture guard allowed a production artifact read")
    production = fixtures.counter_snapshot("production-read-guard")
    assert production["counts"] == {"mutator.production_read.attempt": 1}

    production_dir = ROOT / "reports"
    production_file = production_dir / "performance_ledger.csv"
    read_cases = (
        ("path-exists", production_file.exists),
        ("path-stat", production_file.stat),
        ("path-glob", lambda: list(production_dir.glob("*.csv"))),
        ("path-rglob", lambda: list(production_dir.rglob("*.csv"))),
        ("path-iterdir", lambda: list(production_dir.iterdir())),
        ("os-stat", lambda: os.stat(production_file)),
        ("os-lstat", lambda: os.lstat(production_file)),
        ("os-listdir", lambda: os.listdir(production_dir)),
        ("os-scandir", lambda: list(os.scandir(production_dir))),
        ("os-access", lambda: os.access(production_file, os.R_OK)),
        ("os-readlink", lambda: os.readlink(production_file)),
    )
    for capture, action in read_cases:
        assert_blocked(
            capture,
            action,
            fixtures.BlockedProductionArtifactError,
            "mutator.production_read.attempt",
        )

    for artifact in sorted(fixtures.PRODUCTION_ROOT_CANDIDATE_ARTIFACTS):
        slug = artifact.removesuffix(".json").replace("_", "-")
        artifact_path = ROOT / artifact
        assert_blocked(
            f"root-read-{slug}",
            artifact_path.read_bytes,
            fixtures.BlockedProductionArtifactError,
            "mutator.production_read.attempt",
        )
        assert_blocked(
            f"root-write-{slug}",
            lambda path=artifact_path: path.write_bytes(b"forbidden"),
            fixtures.BlockedProductionArtifactError,
            "mutator.production_write.attempt",
        )

    sqlite_cases = (
        (
            "sqlite-connect",
            lambda: sqlite3.connect(production_dir / "forbidden.sqlite"),
            "mutator.production_write.attempt",
        ),
        (
            "sqlite-uri-read",
            lambda: sqlite3.dbapi2.connect(
                f"file:{production_file}?mode=ro",
                uri=True,
            ),
            "mutator.production_read.attempt",
        ),
        (
            "sqlite-connection",
            lambda: sqlite3.Connection(production_dir / "forbidden-direct.sqlite"),
            "mutator.production_write.attempt",
        ),
        (
            "sqlite-positional-uri",
            lambda: sqlite3.connect(
                f"file:{production_file}?mode=ro",
                5.0,
                0,
                "",
                True,
                sqlite3.Connection,
                128,
                True,
            ),
            "mutator.production_read.attempt",
        ),
    )
    for capture, action, counter in sqlite_cases:
        assert_blocked(
            capture,
            action,
            fixtures.BlockedProductionArtifactError,
            counter,
        )
    memory = sqlite3.connect(":memory:")
    memory.close()

    replace_source = environment.run_dir / "replace-source.txt"
    replace_source.write_text("owned", encoding="utf-8")
    write_cases = (
        ("os-unlink", lambda: os.unlink(production_file)),
        ("os-remove", lambda: os.remove(production_file)),
        (
            "os-rename",
            lambda: os.rename(production_file, environment.run_dir / "renamed.csv"),
        ),
        (
            "os-replace",
            lambda: os.replace(replace_source, production_dir / "replacement.csv"),
        ),
    )
    for capture, action in write_cases:
        assert_blocked(
            capture,
            action,
            fixtures.BlockedProductionArtifactError,
            "mutator.production_write.attempt",
        )
    assert replace_source.read_text(encoding="utf-8") == "owned"

    owned = environment.fixture_root / "content" / "influencers.json"
    assert json.loads(owned.read_text(encoding="utf-8")) == {
        "categories_order": [],
        "influencers": [],
    }
    with fixtures.capture_context("runtime-write-guard"):
        try:
            (environment.fixture_root / "reports" / "forbidden.txt").write_text(
                "blocked",
                encoding="utf-8",
            )
        except fixtures.BlockedFixtureMutationError:
            pass
        else:
            raise AssertionError("fixture guard allowed a capture-time runtime write")
    runtime_write = fixtures.counter_snapshot("runtime-write-guard")
    assert runtime_write["counts"] == {"mutator.runtime_write.attempt": 1}


def test_navigation_proxy_is_idempotent_and_restorable() -> None:
    class Page:
        url_path = "today-decision"
        title = "今日決策"

        def __init__(self) -> None:
            self.runs = 0

        def run(self) -> str:
            self.runs += 1
            return "ran"

    class FakeStreamlit:
        def __init__(self) -> None:
            self.page = Page()
            self.navigation_calls = 0

        def navigation(self, *args, **kwargs):
            del args, kwargs
            self.navigation_calls += 1
            return self.page

    fake = FakeStreamlit()
    original = fake.navigation
    with fixtures.navigation_proxy_context(fake):
        first = fake.navigation
        fixtures.install_navigation_proxy(fake)
        assert fake.navigation is first
        wrapped = fake.navigation({"group": []})
        assert wrapped.url_path == "today-decision"
        assert wrapped.title == "今日決策"
        assert fake.navigation_calls == 1
    assert fake.navigation == original


def test_provider_patches_preserve_render_identity_and_rebind_paths(
    environment: fixtures.FixtureEnvironment,
) -> None:
    from ui import (
        _candidate_controls,
        _shared,
        analyst_views,
        analytics_db,
        crypto_screener,
        crypto_universe,
        ibkr_reconcile,
        industry_roles,
        influencers,
        institutions,
        knowledge_graph,
        market_thesis,
        options_flow,
        options_cockpit,
        radar,
        retro_analysis,
        sector_rotation,
        stock_checkup,
        sys_ai_updates,
        sys_schedules,
        theme_flow,
        today_decision,
        trade_state,
        us_cot,
        us_options,
        us_screener,
        watchlist_categorize,
        x_sentiment,
    )

    modules = (
        today_decision,
        trade_state,
        stock_checkup,
        options_cockpit,
        institutions,
        sys_schedules,
        sys_ai_updates,
        us_screener,
        options_flow,
        radar,
        ibkr_reconcile,
        sector_rotation,
        theme_flow,
        us_cot,
        market_thesis,
        x_sentiment,
        retro_analysis,
        analytics_db,
        knowledge_graph,
        us_options,
        analyst_views,
        industry_roles,
        watchlist_categorize,
        influencers,
        crypto_universe,
        crypto_screener,
    )
    identities = {module.__name__: module.render for module in modules}
    with fixtures.provider_fixture_context():
        for module in modules:
            assert module.render is identities[module.__name__]
        assert _shared.DATA_DIR == environment.fixture_root
        assert _shared.REPORTS_DIR == environment.fixture_root / "reports"
        assert not hasattr(today_decision, "_MARKET_THESIS_DIR")
        assert _candidate_controls._RUN_STATUS_PATH.is_relative_to(environment.fixture_root)
        assert us_screener.DATA_DIR == environment.fixture_root
        assert us_screener.REPORTS_DIR == environment.fixture_root / "reports"
        assert not hasattr(radar.oversold_reversal_lane, "OVERSOLD_DIR")
        assert not hasattr(us_cot, "_COT_DIR")
        assert not hasattr(market_thesis, "_DIR")
        assert x_sentiment._PICKS_PATH.is_relative_to(environment.fixture_root)
        assert retro_analysis.RETRO_DIR.is_relative_to(environment.fixture_root)
        assert analytics_db._DATA_HEALTH_STATUS_PATH.is_relative_to(environment.fixture_root)
        assert not hasattr(knowledge_graph, "kg")
        assert watchlist_categorize._TV_FILE.is_relative_to(environment.fixture_root)
        assert influencers.ROSTER_PATH.is_relative_to(environment.fixture_root)
        assert not hasattr(crypto_universe, "_LATEST")
        assert not hasattr(crypto_universe, "_TV_FILE")
    for module in modules:
        assert module.render is identities[module.__name__]


def test_provider_patch_rebinds_restoration_to_reloaded_module() -> None:
    first = ModuleType("ux0_reload_boundary")
    first.boundary = lambda: "first"
    fixtures._patch_attribute(first, "boundary", lambda _original: lambda: "fixture")
    assert first.boundary() == "fixture"

    second = ModuleType("ux0_reload_boundary")
    second_original = lambda: "second"
    second.boundary = second_original
    fixtures._patch_attribute(second, "boundary", lambda _original: lambda: "fixture")
    assert second.boundary() == "fixture"

    fixtures.restore_provider_fixtures()
    assert second.boundary is second_original


def test_runtime_callable_identity_is_measured_and_mutation_fails() -> None:
    from ui import today_decision

    assert fixtures._runtime_callable_identity(today_decision.render) == "today_decision.render"
    assert (
        fixtures._validated_runtime_callable("today-decision", today_decision.render)
        == "today_decision.render"
    )

    namespace: dict[str, object] = {"__name__": "__main__"}
    exec("def us_x():\n    return None\n", namespace)
    assert fixtures._validated_runtime_callable("us-x", namespace["us_x"]) == "us_x"

    runpy_namespace: dict[str, object] = {"__name__": "__quant_radar_real_app__"}
    exec("def crypto_x():\n    return None\n", runpy_namespace)
    assert (
        fixtures._validated_runtime_callable("crypto-x", runpy_namespace["crypto_x"])
        == "crypto_x"
    )

    wrong_namespace: dict[str, object] = {"__name__": "ui.wrong_page"}
    exec("def render():\n    return None\n", wrong_namespace)
    wrong_renderer = wrong_namespace["render"]

    try:
        fixtures._validated_runtime_callable("today-decision", wrong_renderer)
    except fixtures.FixtureConfigurationError as exc:
        message = str(exc)
        assert "callable mismatch" in message
        assert "today_decision.render" in message
    else:
        raise AssertionError("fixture accepted a mutated runtime page callable")

    class MissingRuntimeCallable:
        pass

    try:
        fixtures._streamlit_page_callable(MissingRuntimeCallable())
    except fixtures.FixtureConfigurationError as exc:
        assert "runtime callable" in str(exc)
    else:
        raise AssertionError("fixture self-declared identity without a runtime callable")


def test_real_render_matrix_and_named_boundaries() -> None:
    cases = (
        (
            "today_decision",
            "today-decision",
            "app-today",
            "UX-0 固定基準",
            ("today.daily_summary.execute", "trade_state.build.execute"),
        ),
        (
            "trade_state",
            "trade-state",
            "app-trade",
            "UX-0 固定樣本",
            ("trade_state.load.attempt", "trade_state.build.execute"),
        ),
        (
            "stock_checkup",
            "stock-checkup",
            "app-stock",
            "來源：UX-0 Fixture",
            (
                "stock.live_factor_flags.execute",
                "stock.score_surge.execute",
                "fundamentals.load.execute",
                "options.money_flow_api.execute",
            ),
        ),
        (
            "options_cockpit",
            "options-cockpit",
            "app-options",
            "來源：UX-0 Fixture",
            (
                "options.live_provider.execute",
                "options.money_flow_api.execute",
                "options.options_flow_api.execute",
            ),
        ),
        (
            "institutions",
            "institutions",
            "app-institutions-stock",
            "UX-0 Capital",
            ("institutions.stock.load.execute",),
        ),
        (
            "sys_schedules",
            "schedules",
            "app-schedules",
            "UX-0 固定排程",
            ("schedules.load.execute", "schedules.result.report_dir.execute"),
        ),
        (
            "sys_ai_updates",
            "ai-updates",
            "app-ai",
            "UX-0 固定更新",
            ("ai_updates.load.execute",),
        ),
    )

    with fixtures.provider_fixture_context():
        for module_name, route, capture, identity, expected_counts in cases:
            app = AppTest.from_string(
                _wrapper(module_name, route, capture),
                default_timeout=20,
            ).run()
            assert not app.exception, (route, app.exception)
            text = _app_text(app)
            assert identity in text, (route, identity, text)
            snapshot = fixtures.counter_snapshot(capture)
            counts = snapshot["counts"]
            assert snapshot["blockedNetwork"] == [], (route, snapshot)
            assert counts["session.setup"] == 1, (route, counts)
            for name in expected_counts:
                assert counts.get(name, 0) >= 1, (route, name, counts)
            if route == "stock-checkup":
                assert counts.get("institutions.stock.load.execute", 0) == 0, counts
            fixtures.assert_counter_contract(route, capture)

        alternate = AppTest.from_string(
            _wrapper("institutions", "institutions", "app-institutions-portfolio"),
            default_timeout=20,
        )
        alternate.session_state["inst_view"] = "機構持倉 · 機構 → 它持有什麼"
        alternate.run()
        assert not alternate.exception, alternate.exception
        alternate_text = _app_text(alternate)
        assert "UX-0 Fund" in alternate_text, alternate_text
        alt_snapshot = fixtures.counter_snapshot("app-institutions-portfolio")
        assert alt_snapshot["blockedNetwork"] == [], alt_snapshot
        alt_counts = alt_snapshot["counts"]
        assert alt_counts.get("institutions.catalog.execute") == 1, alt_counts
        assert alt_counts.get("institutions.portfolio.load.execute") == 1, alt_counts

        ai = AppTest.from_string(
            _wrapper("sys_ai_updates", "ai-updates", "app-ai-rerun"),
            default_timeout=20,
        ).run()
        assert not ai.exception, ai.exception
        ai.run()
        assert not ai.exception, ai.exception
        rerun_snapshot = fixtures.counter_snapshot("app-ai-rerun")
        assert rerun_snapshot["blockedNetwork"] == [], rerun_snapshot
        rerun_counts = rerun_snapshot["counts"]
        assert rerun_counts["session.setup"] == 1, rerun_counts
        assert rerun_counts["ai_updates.load.execute"] == 2, rerun_counts


def test_remaining_twenty_real_render_contracts() -> None:
    cases = (
        ("us_screener", "us-screener", "ux1b-us-screener", "Layer 0 — 大盤環境"),
        ("options_flow", "options-flow", "ux1b-options-flow", "選擇權異常流"),
        ("radar", "radar", "ux1b-radar", "雷達 / Radar"),
        ("ibkr_reconcile", "ibkr-reconcile", "ux1b-ibkr", "IBKR 對帳"),
        ("sector_rotation", "sector-rotation", "ux1b-sector", "熱錢板塊輪動"),
        ("theme_flow", "theme-flow", "ux1b-theme-flow", "主題資金流"),
        ("us_cot", "us-cot", "ux1b-us-cot", "COT / ES 週報"),
        ("market_thesis", "market-thesis", "ux1b-market-thesis", "大盤行情研判"),
        ("x:US", "us-x", "ux1b-us-x", "X 社群情緒 — 美股"),
        ("retro_analysis", "retro-analysis", "ux1b-retro", "復盤分析"),
        ("analytics_db", "analytics-db", "ux1b-analytics", "資料健康 / Analytics DB"),
        ("knowledge_graph", "knowledge-graph", "ux1b-knowledge", "知識網路"),
        ("us_options", "us-options", "ux1b-us-options", "完整期權鏈明細"),
        ("analyst_views", "analyst-views", "ux1b-analyst", "分析師評級"),
        ("industry_roles", "industry-roles", "ux1b-industry", "產業鏈分類"),
        ("watchlist_categorize", "watchlist-categorize", "ux1b-watchlist", "自選股分類"),
        ("influencers", "influencers", "ux1b-influencers", "關注博主"),
        ("crypto_universe", "crypto-universe", "ux1b-crypto-universe", "幣種清單"),
        ("crypto_screener", "crypto-screener", "ux1b-crypto-screener", "幣圈篩選"),
        ("x:CRYPTO", "crypto-x", "ux1b-crypto-x", "X 社群情緒 — 幣圈"),
    )

    with fixtures.provider_fixture_context():
        for module_name, route, capture, identity in cases:
            source = (
                _x_wrapper(module_name.split(":", 1)[1], route, capture)
                if module_name.startswith("x:")
                else _wrapper(module_name, route, capture)
            )
            app = AppTest.from_string(source, default_timeout=20).run()
            assert not app.exception, (route, app.exception)
            text = _app_text(app)
            assert identity in text, (route, identity, text)
            snapshot = fixtures.counter_snapshot(capture)
            assert snapshot["blockedNetwork"] == [], (route, snapshot)
            assert snapshot["identity"] == {
                "selectedRegistryKey": route,
                "realCallable": FROZEN_CALLABLES[route],
                "resolvedOwnedPaths": {
                    name: str((fixtures.current_environment().fixture_root / relative).resolve())
                    for name, relative in fixtures.ROUTE_OWNED_PATHS[route].items()
                },
            }, (route, snapshot["identity"])
            for sentinel in REQUIRED_ZERO_SENTINELS:
                assert snapshot["counts"].get(sentinel, 0) == 0, (route, snapshot)
            fixtures.assert_counter_contract(route, capture)


def main() -> int:
    tests_before_bootstrap = (
        test_ux1b_fragment_schedule_is_disabled_without_replacing_body,
        test_full_route_fixture_contract_is_frozen,
        test_production_root_candidate_artifact_inventory_is_complete,
        test_fixed_schema_regressions_are_closed,
        test_analytics_fixture_has_two_tables_and_fail_soft_empty_projection,
        test_ux1b_profile_requires_exact_runtime_identity,
        test_owned_app_contract_replaces_legacy_fixture_environment_projection,
        test_ux1b_profile_phase_matrix_is_exact,
        test_theme_gallery_counter_contract_is_real_and_once_per_session,
        test_owned_app_contract_rejects_mode_and_shape_drift,
        test_ux1b_network_allowlist_is_two_exact_ipv4_destinations,
        test_symlink_and_directory_fd_production_bypasses_fail_closed,
        test_low_level_module_aliases_are_guarded_and_idempotent,
        test_counter_revision_is_profile_specific_and_schema_stays_compatible,
        test_existing_counter_profile_mismatches_fail_closed,
        test_environment_validation_fails_closed,
        test_entrypoint_fails_before_streamlit_without_opt_in,
    )
    passed = 0
    for test in tests_before_bootstrap:
        test()
        passed += 1
        print(f"PASS {test.__name__}")

    with _owned_environment():
        environment = fixtures.bootstrap_fixture_environment()
        tests = (
            lambda: test_owned_environment_and_atomic_counters(environment),
            lambda: test_network_guard_blocks_without_contacting_destination(environment),
            test_navigation_proxy_is_idempotent_and_restorable,
            lambda: test_provider_patches_preserve_render_identity_and_rebind_paths(environment),
            test_provider_patch_rebinds_restoration_to_reloaded_module,
            test_runtime_callable_identity_is_measured_and_mutation_fails,
            test_real_render_matrix_and_named_boundaries,
            test_remaining_twenty_real_render_contracts,
            lambda: test_process_and_production_artifact_guards(environment),
        )
        names = (
            "test_owned_environment_and_atomic_counters",
            "test_network_guard_blocks_without_contacting_destination",
            "test_navigation_proxy_is_idempotent_and_restorable",
            "test_provider_patches_preserve_render_identity_and_rebind_paths",
            "test_provider_patch_rebinds_restoration_to_reloaded_module",
            "test_runtime_callable_identity_is_measured_and_mutation_fails",
            "test_real_render_matrix_and_named_boundaries",
            "test_remaining_twenty_real_render_contracts",
            "test_process_and_production_artifact_guards",
        )
        for name, test in zip(names, tests):
            test()
            passed += 1
            print(f"PASS {name}")

    print(f"PASS: {passed} fixture tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
