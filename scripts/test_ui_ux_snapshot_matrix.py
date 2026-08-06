#!/usr/bin/env python3
"""Focused tests for the UX-0 owned-process snapshot matrix."""

from __future__ import annotations

import ast
import copy
import importlib
import inspect
import json
import os
import hashlib
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent

UX1B_PROJECTION = (
    ("today-decision", "/", "今日決策", "today_decision.render"),
    ("trade-state", "/trade-state", "交易狀態", "trade_state.render"),
    ("us-screener", "/us-screener", "暴漲股篩選器", "us_screener.render"),
    ("options-flow", "/options-flow", "選擇權異常流", "options_flow.render"),
    ("stock-checkup", "/stock-checkup", "個股總覽", "stock_checkup.render"),
    ("options-cockpit", "/options-cockpit", "期權作戰台", "options_cockpit.render"),
    ("radar", "/radar", "雷達 (風險＋反轉)", "radar.render"),
    ("ibkr-reconcile", "/ibkr-reconcile", "IBKR 對帳", "ibkr_reconcile.render"),
    ("sector-rotation", "/sector-rotation", "熱錢板塊輪動", "sector_rotation.render"),
    ("theme-flow", "/theme-flow", "主題資金流", "theme_flow.render"),
    ("us-cot", "/us-cot", "COT / ES 週報", "us_cot.render"),
    ("market-thesis", "/market-thesis", "大盤行情研判", "market_thesis.render"),
    ("us-x", "/us-x", "X 社群情緒", "us_x"),
    ("retro-analysis", "/retro-analysis", "復盤分析", "retro_analysis.render"),
    ("analytics-db", "/analytics-db", "資料健康 / Analytics DB", "analytics_db.render"),
    ("knowledge-graph", "/knowledge-graph", "知識網路", "knowledge_graph.render"),
    ("us-options", "/us-options", "期權分析", "us_options.render"),
    ("analyst-views", "/analyst-views", "分析師評級", "analyst_views.render"),
    ("institutions", "/institutions", "機構面板", "institutions.render"),
    ("industry-roles", "/industry-roles", "產業鏈分類", "industry_roles.render"),
    ("watchlist-categorize", "/watchlist-categorize", "自選股分類", "watchlist_categorize.render"),
    ("influencers", "/influencers", "關注博主", "influencers.render"),
    ("schedules", "/schedules", "排程與結果", "sys_schedules.render"),
    ("ai-updates", "/ai-updates", "AI 重點更新", "sys_ai_updates.render"),
    ("crypto-universe", "/crypto-universe", "幣種清單", "crypto_universe.render"),
    ("crypto-screener", "/crypto-screener", "幣圈篩選", "crypto_screener.render"),
    ("crypto-x", "/crypto-x", "X 社群情緒", "crypto_x"),
)

UX1B_READY_MARKERS = (
    ("today-decision", 2, "今日決策", "exact"),
    ("trade-state", 2, "交易狀態", "exact"),
    ("us-screener", 2, "Layer 0 — 大盤環境", "exact"),
    ("options-flow", 1, "選擇權異常流", "contains"),
    ("stock-checkup", 2, "個股總覽", "contains"),
    ("options-cockpit", 2, "期權作戰台", "contains"),
    ("radar", 2, "雷達 / Radar", "contains"),
    ("ibkr-reconcile", 2, "IBKR 對帳", "contains"),
    ("sector-rotation", 2, "熱錢板塊輪動", "contains"),
    ("theme-flow", 2, "主題資金流", "contains"),
    ("us-cot", 2, "COT / ES 週報", "contains"),
    ("market-thesis", 2, "大盤行情研判", "contains"),
    ("us-x", 2, "X 社群情緒 — 美股", "contains"),
    ("retro-analysis", 1, "復盤分析", "contains"),
    ("analytics-db", 2, "資料健康 / Analytics DB", "exact"),
    ("knowledge-graph", 1, "知識網路", "exact"),
    ("us-options", 2, "完整期權鏈明細", "exact"),
    ("analyst-views", 2, "分析師評級", "contains"),
    ("institutions", 2, "機構面板", "contains"),
    ("industry-roles", 2, "產業鏈分類", "exact"),
    ("watchlist-categorize", 2, "自選股分類", "contains"),
    ("influencers", 2, "關注博主", "exact"),
    ("schedules", 2, "排程與執行結果", "contains"),
    ("ai-updates", 2, "AI Agent 重點更新", "contains"),
    ("crypto-universe", 2, "幣種清單 — 幣安 USDT 永續 (USDT.P)", "contains"),
    ("crypto-screener", 2, "幣圈篩選", "contains"),
    ("crypto-x", 2, "X 社群情緒 — 幣圈", "contains"),
)


def _runner():
    return importlib.import_module("ui_ux_snapshot_matrix")


def _browser_worker():
    return importlib.import_module("ui_ux_browser_worker")


def _call_leaf_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _ux1b_task3_contract_failures(module, manifest: dict) -> list[str]:
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(module.__file__))
    failures: list[str] = []

    for name in ("WORKSPACE_ROOT", "SOURCE_ROOT"):
        if not isinstance(getattr(module, name, None), Path):
            failures.append(f"{name} Path API is missing")
    workspace_root = getattr(module, "WORKSPACE_ROOT", None)
    if isinstance(workspace_root, Path) and workspace_root.resolve() != ROOT.resolve():
        failures.append("WORKSPACE_ROOT does not identify the original repository")

    worker_path = getattr(module, "BROWSER_WORKER_PATH", None)
    if not isinstance(worker_path, Path) or worker_path.name != "ui_ux_browser_worker.py":
        failures.append("external BROWSER_WORKER_PATH is missing")

    task3_helpers = (
        "build_browser_worker_command",
        "capture_stack_digest",
        "finalize_terminal_manifest",
        "build_app_sandbox_profile",
        "build_browser_sandbox_profile",
    )
    for name in task3_helpers:
        if not callable(getattr(module, name, None)):
            failures.append(f"{name} API is missing")

    if "captureStackDigest" not in manifest:
        failures.append("manifest captureStackDigest provisional field is missing")
    else:
        digest = manifest["captureStackDigest"]
        if digest is not None and not (
            isinstance(digest, str)
            and len(digest) == 64
            and set(digest) <= set("0123456789abcdef")
        ):
            failures.append("manifest captureStackDigest is neither provisional nor SHA-256")

    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    direct_pass_writers: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
        value = node.value
        writes_status = any(
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Name)
            and target.value.id == "manifest"
            and isinstance(target.slice, ast.Constant)
            and target.slice.value == "status"
            for target in targets
        )
        contains_passed = value is not None and any(
            isinstance(part, ast.Constant) and part.value == "passed"
            for part in ast.walk(value)
        )
        if not writes_status or not contains_passed:
            continue
        owner = parents.get(node)
        while owner is not None and not isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef)):
            owner = parents.get(owner)
        owner_name = owner.name if owner is not None else "<module>"
        if owner_name != "finalize_terminal_manifest":
            direct_pass_writers.add(owner_name)
    if direct_pass_writers:
        failures.append(
            "terminal passed state bypasses finalizer in "
            + ", ".join(sorted(direct_pass_writers))
        )

    run_matrix = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "run_matrix"
        ),
        None,
    )
    if run_matrix is None:
        failures.append("run_matrix is missing")
        return failures

    finalizer_lines = [
        node.lineno
        for node in ast.walk(run_matrix)
        if isinstance(node, ast.Call)
        and _call_leaf_name(node) == "finalize_terminal_manifest"
    ]
    if len(finalizer_lines) != 1:
        failures.append("run_matrix must have exactly one success finalizer call")
        return failures

    app_stop_lines = [
        node.lineno
        for node in ast.walk(run_matrix)
        if isinstance(node, ast.Call)
        and _call_leaf_name(node)
        in {"stop_owned_process", "terminate_owned_process_group"}
    ]
    source_close_lines: list[int] = []
    for node in ast.walk(run_matrix):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
        if any(
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Name)
            and target.value.id == "manifest"
            and isinstance(target.slice, ast.Constant)
            and target.slice.value == "sourceDigestEnd"
            for target in targets
        ):
            source_close_lines.append(node.lineno)
    proxy_close_lines = [
        node.lineno
        for node in ast.walk(run_matrix)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "close"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "deny_proxy"
    ]
    finalizer_line = finalizer_lines[0]
    if not any(line < finalizer_line for line in app_stop_lines):
        failures.append("snapshot success finalizer lacks a preceding app process-group stop")
    if not any(line < finalizer_line for line in source_close_lines):
        failures.append("snapshot success finalizer lacks preceding source-digest closure")
    if not any(line < finalizer_line for line in proxy_close_lines):
        failures.append("snapshot success finalizer lacks preceding deny-proxy closure")
    return failures


def _fake_ux1b_comparison_manifest(runner, phase: str) -> dict:
    contracts = runner.load_ux1b_fixture_contracts()
    captures = []
    for page in runner.UX1B_PAGE_PROJECTION:
        marker = runner.UX1B_READY_MARKERS[page.registry_key]
        counter = contracts["counters"][page.registry_key]
        positive = dict(counter["positive"])
        zero = sorted(counter["zero"])
        owned_paths = dict(contracts["ownedPaths"][page.registry_key])
        for viewport_name, width, height in runner.UX1B_VIEWPORTS:
            sidebar_overlap = viewport_name == "mobile"
            metrics = {
                "viewportWidth": width,
                "viewportHeight": height,
                "documentClientWidth": width,
                "documentScrollWidth": width,
                "documentScrollHeight": height + 200,
                "horizontalOverflow": False,
                "sidebar": {"visible": True, "width": 300},
                "main": {"visible": True, "width": width},
                "sidebarOverlapsMain": sidebar_overlap,
                "plotlyCharts": 0,
            }
            component_metrics = {
                "name": f"{page.registry_key}-main",
                "present": True,
                "bounds": {"x": 0, "y": 0, "width": width, "height": height},
                "clientWidth": width,
                "scrollWidth": width,
                "horizontalOverflow": False,
                "overflowPixels": 0,
                "overflowX": "visible",
            }
            captures.append(
                {
                    "profile": runner.UX1B_PROFILE,
                    "status": "passed",
                    "failureReasons": [],
                    "browser": "chromium",
                    "case": page.registry_key,
                    "focusedCase": False,
                    "page": page.registry_key,
                    "route": page.route,
                    "viewport": {
                        "name": viewport_name,
                        "width": width,
                        "height": height,
                    },
                    "heading": marker.text,
                    "headingReady": True,
                    "streamlitException": False,
                    "pageErrors": [],
                    "blockedExternalRequests": [],
                    "blockedServerNetwork": [],
                    "fixtureQuiescent": True,
                    "fixtureContractFailures": [],
                    "readyMarker": {
                        "role": "heading",
                        "level": marker.level,
                        "text": marker.text,
                        "match": marker.match,
                        "scope": "stMainBlockContainer",
                    },
                    "identity": {
                        "requestedRoute": page.route,
                        "finalBrowserPath": page.route,
                        "expectedRegistryKey": page.registry_key,
                        "selectedRegistryKey": page.registry_key,
                        "expectedCallable": page.callable_name,
                        "realCallable": page.callable_name,
                        "expectedNavTitle": page.nav_title,
                    },
                    "fixture": {
                        "counts": positive,
                        "blockedNetwork": [],
                        "identity": {
                            "selectedRegistryKey": page.registry_key,
                            "realCallable": page.callable_name,
                        },
                    },
                    "fixtureContract": {
                        "positiveCounters": positive,
                        "zeroCounters": zero,
                        "ownedPaths": owned_paths,
                        "resolvedOwnedPaths": owned_paths,
                    },
                    "metrics": metrics,
                    "componentMetrics": component_metrics,
                    "knownDebt": {
                        "expandedSidebarOverlapsMain": sidebar_overlap,
                        "pageHorizontalOverflow": False,
                        "floatingAiPresent": True,
                        "floatingAiOverlapsMain": True,
                    },
                    "screenshot": f"chromium/{page.registry_key}/{viewport_name}.png",
                }
            )
    digest = "a" * 64 if phase == "pretheme" else "b" * 64
    return {
        "schemaVersion": 1,
        "tool": {"name": "quant-radar-ui-ux-matrix", "version": runner.VERSION},
        "status": "passed",
        "fixtureRevision": runner.UX1B_EXPECTED_FIXTURE_REVISION,
        "environment": {
            "python": "3.12.0",
            "streamlit": "1.57.0",
            "playwright": "1.52.0",
            "platform": "darwin",
        },
        "mode": runner.UX1B_PROFILE,
        "phase": phase,
        "projectionSha256": runner.UX1B_PROJECTION_SHA256,
        "fixtureContractSchema": runner.UX1B_EXPECTED_CONTRACT_SCHEMA_VERSION,
        "sourceDigestStart": digest,
        "sourceDigestEnd": digest,
        "sourceDigestEqual": True,
        "pages": [page.registry_key for page in runner.UX1B_PAGE_PROJECTION],
        "cases": [
            {
                "name": page.registry_key,
                "page": page.registry_key,
                "route": page.route,
                "component": f"{page.registry_key}-main",
                "interaction": "none",
            }
            for page in runner.UX1B_PAGE_PROJECTION
        ],
        "viewports": [
            {"name": name, "width": width, "height": height}
            for name, width, height in runner.UX1B_VIEWPORTS
        ],
        "expectedCapturesPerBrowser": 81,
        "expectedCaptureCount": 81,
        "selectedBrowsers": ["chromium"],
        "pageIdentityCatalog": runner._projection_records(
            runner.UX1B_PAGE_PROJECTION
        ),
        "readyMarkers": runner._ux1b_ready_marker_catalog(),
        "captures": captures,
        "server": {
            "ownedProcess": True,
            "loopbackOnly": True,
            "exactPortContract": True,
            "allowedEndpointCount": 2,
            "denyProxyOwned": True,
            "denyProxyAttemptCount": 0,
            "kernelIsolation": "supported",
            "sandboxCalibration": {
                "capability": "supported",
                "passed": True,
                "exactPortContract": True,
                "allowedEndpointCount": 2,
                "streamlitAllowed": True,
                "denyProxyAllowed": True,
                "dummyLoopbackDenied": True,
                "api8000Denied": True,
                "testNetDenied": True,
                "dummyListenerBytes": 0,
            },
        },
    }


def test_cli_contract_and_defaults() -> None:
    runner = _runner()
    parser = runner.build_parser()
    args = parser.parse_args(["--no-prompt"])
    assert args.browser is None
    assert args.page is None
    assert args.case is None
    assert args.viewport is None
    assert args.no_prompt is True
    assert runner.DEFAULT_PAGES == (
        "today-decision",
        "trade-state",
        "stock-checkup",
        "options-cockpit",
        "institutions",
        "schedules",
        "ai-updates",
    )
    assert runner.DEFAULT_VIEWPORTS == {
        "desktop": (1440, 900),
        "tablet": (768, 1024),
        "mobile": (390, 844),
    }
    assert runner.FOCUSED_CASES == (
        "today-decision",
        "ai-chat-open",
        "ai-updates",
        "schedules",
        "institution-portfolio",
    )


def test_ux1b_recovery_task3_coordinator_seams_and_finalization_contract() -> None:
    runner = _runner()
    cases = tuple(runner.ux1b_page_capture_case(item) for item in runner.UX1B_PAGE_PROJECTION)
    with tempfile.TemporaryDirectory() as td:
        owned = runner.create_owned_run(Path(td) / "coordinator-contract")
        manifest = runner._manifest_template(
            owned,
            cases=cases,
            viewports=runner.UX1B_VIEWPORTS,
            profile=runner.UX1B_PROFILE,
            phase="precontrol",
        )
    failures = _ux1b_task3_contract_failures(runner, manifest)
    assert failures == [], "UX1B Task 3 snapshot gaps: " + "; ".join(failures)


def test_terminal_finalization_grant_is_opaque_bound_and_one_shot() -> None:
    runner = _runner()

    def finalizing_manifest() -> dict:
        return {"mode": "legacy-test", "status": "finalizing", "captures": []}

    def assert_type_error(callable_) -> None:
        try:
            callable_()
        except TypeError:
            return
        raise AssertionError("opaque finalization grant operation unexpectedly succeeded")

    assert_type_error(lambda: runner._RunnerFinalizationGrant())
    assert_type_error(lambda: runner._RunSuccessAuthority())
    forged = object.__new__(runner._RunnerFinalizationGrant)

    with tempfile.TemporaryDirectory() as td:
        persisted = Path(td) / "manifest.json"
        authority_index = 0

        def register_test_run_authority(manifest: dict):
            nonlocal authority_index
            authority_index += 1
            owned = runner.create_owned_run(
                Path(td) / f"grant-run-{authority_index}"
            )
            authority = object.__new__(runner._RunSuccessAuthority)
            with runner._FINALIZATION_GRANTS_LOCK:
                runner._RUN_SUCCESS_AUTHORITIES[id(authority)] = (
                    authority,
                    os.getpid(),
                    manifest,
                    owned,
                    runner._owned_run_binding(owned),
                )
            return authority

        forged_manifest = finalizing_manifest()
        forged_authority = object.__new__(runner._RunSuccessAuthority)
        try:
            runner._authorize_terminal_manifest(
                forged_manifest, authority=forged_authority
            )
        except runner.RunnerDataError:
            pass
        else:
            raise AssertionError("unregistered authority minted a finalization grant")
        try:
            runner._authorize_terminal_manifest(forged_manifest)
        except TypeError:
            pass
        else:
            raise AssertionError("mapping-only authorizer call unexpectedly succeeded")

        for candidate in (False, True, {}, {"authorized": True}, forged):
            manifest = finalizing_manifest()
            runner.atomic_write_json(persisted, manifest)
            persisted_before = persisted.read_bytes()
            manifest_before = copy.deepcopy(manifest)
            assert not runner.finalize_terminal_manifest(
                manifest, grant=candidate
            )
            assert manifest == manifest_before
            assert persisted.read_bytes() == persisted_before

        manifest = finalizing_manifest()
        authority = register_test_run_authority(manifest)
        grant = runner._authorize_terminal_manifest(
            manifest, authority=authority
        )
        assert_type_error(lambda: copy.copy(grant))
        assert_type_error(lambda: copy.deepcopy(grant))
        assert runner.finalize_terminal_manifest(manifest, grant=grant)
        passed_before = copy.deepcopy(manifest)
        assert not runner.finalize_terminal_manifest(manifest, grant=grant)
        assert manifest == passed_before

        first = finalizing_manifest()
        second = finalizing_manifest()
        cross_authority = register_test_run_authority(first)
        cross_grant = runner._authorize_terminal_manifest(
            first, authority=cross_authority
        )
        runner.atomic_write_json(persisted, first)
        persisted_before = persisted.read_bytes()
        first_before = copy.deepcopy(first)
        second_before = copy.deepcopy(second)
        assert not runner.finalize_terminal_manifest(second, grant=cross_grant)
        assert first == first_before and second == second_before
        assert persisted.read_bytes() == persisted_before
        assert not runner.finalize_terminal_manifest(first, grant=cross_grant)

        mutated = finalizing_manifest()
        mutation_authority = register_test_run_authority(mutated)
        mutation_grant = runner._authorize_terminal_manifest(
            mutated, authority=mutation_authority
        )
        runner.atomic_write_json(persisted, mutated)
        persisted_before = persisted.read_bytes()
        mutated["unexpected"] = "mutation"
        mutated_before = copy.deepcopy(mutated)
        assert not runner.finalize_terminal_manifest(
            mutated, grant=mutation_grant
        )
        assert mutated == mutated_before
        assert persisted.read_bytes() == persisted_before
        assert runner._RUN_SUCCESS_AUTHORITIES == {}
        assert runner._FINALIZATION_GRANTS == {}


def test_terminal_finalization_registry_transactions_are_linearizable() -> None:
    runner = _runner()

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        authority_index = 0

        def register(manifest: dict):
            nonlocal authority_index
            authority_index += 1
            owned = runner.create_owned_run(root / f"linear-{authority_index}")
            authority = object.__new__(runner._RunSuccessAuthority)
            with runner._FINALIZATION_GRANTS_LOCK:
                runner._RUN_SUCCESS_AUTHORITIES[id(authority)] = (
                    authority,
                    os.getpid(),
                    manifest,
                    owned,
                    runner._owned_run_binding(owned),
                )
            return authority

        original_closure = runner._has_snapshot_success_closure
        try:
            manifest = {
                "mode": "legacy-test",
                "status": "finalizing",
                "captures": [],
            }
            authority = register(manifest)
            entered = threading.Event()
            release = threading.Event()
            discard_started = threading.Event()
            discard_done = threading.Event()
            result: dict[str, object] = {}

            def blocked_authorization(candidate):
                entered.set()
                assert release.wait(2)
                return original_closure(candidate)

            runner._has_snapshot_success_closure = blocked_authorization

            def authorize() -> None:
                result["grant"] = runner._authorize_terminal_manifest(
                    manifest, authority=authority
                )

            def discard() -> None:
                discard_started.set()
                runner._discard_run_success_authority(authority)
                discard_done.set()

            authorizer = threading.Thread(target=authorize)
            revoker = threading.Thread(target=discard)
            authorizer.start()
            assert entered.wait(2)
            revoker.start()
            assert discard_started.wait(2)
            assert not discard_done.wait(0.05)
            release.set()
            authorizer.join(2)
            revoker.join(2)
            assert not authorizer.is_alive() and not revoker.is_alive()
            assert discard_done.is_set()
            assert not runner.finalize_terminal_manifest(
                manifest, grant=result["grant"]
            )
            assert manifest["status"] == "finalizing"
            assert runner._RUN_SUCCESS_AUTHORITIES == {}
            assert runner._FINALIZATION_GRANTS == {}

            runner._has_snapshot_success_closure = original_closure
            final_manifest = {
                "mode": "legacy-test",
                "status": "finalizing",
                "captures": [],
            }
            final_authority = register(final_manifest)
            final_grant = runner._authorize_terminal_manifest(
                final_manifest, authority=final_authority
            )
            final_entered = threading.Event()
            final_release = threading.Event()
            final_discard_started = threading.Event()
            final_discard_done = threading.Event()
            final_result: dict[str, object] = {}

            def blocked_finalization(candidate):
                final_entered.set()
                assert final_release.wait(2)
                return original_closure(candidate)

            runner._has_snapshot_success_closure = blocked_finalization

            def finalize() -> None:
                final_result["passed"] = runner.finalize_terminal_manifest(
                    final_manifest, grant=final_grant
                )

            def discard_final() -> None:
                final_discard_started.set()
                runner._discard_run_success_authority(final_authority)
                final_result["statusAtDiscardReturn"] = final_manifest["status"]
                final_discard_done.set()

            finalizer = threading.Thread(target=finalize)
            final_revoker = threading.Thread(target=discard_final)
            finalizer.start()
            assert final_entered.wait(2)
            final_revoker.start()
            assert final_discard_started.wait(2)
            assert not final_discard_done.wait(0.05)
            final_release.set()
            finalizer.join(2)
            final_revoker.join(2)
            assert not finalizer.is_alive() and not final_revoker.is_alive()
            assert final_result == {
                "passed": True,
                "statusAtDiscardReturn": "passed",
            }
            assert runner._RUN_SUCCESS_AUTHORITIES == {}
            assert runner._FINALIZATION_GRANTS == {}
        finally:
            runner._has_snapshot_success_closure = original_closure
            with runner._FINALIZATION_GRANTS_LOCK:
                runner._RUN_SUCCESS_AUTHORITIES.clear()
                runner._FINALIZATION_GRANTS.clear()


def test_worker_helper_imports_and_path_normalization_outside_repo_cwd() -> None:
    probe = r'''
import json
import runpy
import sys

namespace = runpy.run_path(sys.argv[1], run_name="snapshot_outside_cwd_probe")
command = namespace["build_browser_worker_command"](
    sys.executable,
    namespace["BROWSER_WORKER_PATH"],
    expected_origin="http://127.0.0.1:43111",
    expected_request_id="today-decision/desktop",
    allowed_staging_paths=("staging/capture.png", "staging/render.json"),
)
print(json.dumps(command))
'''
    with tempfile.TemporaryDirectory() as td:
        completed = subprocess.run(
            [sys.executable, "-c", probe, str(ROOT / "scripts" / "ui_ux_snapshot_matrix.py")],
            cwd=td,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            check=False,
        )
    assert completed.returncode == 0, completed.stderr
    command = json.loads(completed.stdout)
    assert command[0] == sys.executable
    assert command[1] == "scripts/ui_ux_browser_worker.py"


def test_ux1b_frozen_projection_and_ready_markers_are_exact() -> None:
    runner = _runner()
    projection = tuple(
        (item.registry_key, item.route, item.nav_title, item.callable_name)
        for item in runner.UX1B_PAGE_PROJECTION
    )
    assert projection == UX1B_PROJECTION
    canonical = [
        {
            "registry_key": registry_key,
            "route": route,
            "nav_title": nav_title,
            "callable": callable_name,
        }
        for registry_key, route, nav_title, callable_name in projection
    ]
    digest = hashlib.sha256(
        json.dumps(
            canonical,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert digest == "539bf737382a0f35aca3daaec681aa520152e1381a442904c73d3c61d416f015"
    assert runner.UX1B_PROJECTION_SHA256 == digest

    markers = tuple(
        (key, marker.level, marker.text, marker.match)
        for key, marker in runner.UX1B_READY_MARKERS.items()
    )
    assert markers == UX1B_READY_MARKERS
    assert tuple(item[0] for item in UX1B_PROJECTION) == tuple(
        item[0] for item in UX1B_READY_MARKERS
    )
    marker_records = [
        {"registry_key": key, "level": level, "text": text, "match": match}
        for key, level, text, match in markers
    ]
    marker_digest = hashlib.sha256(
        json.dumps(
            marker_records,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert marker_digest == "691c846199e3fbbb11340b8ed6211a3aa638a0c02c0c8c9202c85a7ae1ebef81"
    assert runner.UX1B_READY_MARKERS_SHA256 == marker_digest
    changed_markers = dict(runner.UX1B_READY_MARKERS)
    changed_markers["us-screener"] = runner.ReadyMarker(
        2, "still 27 but wrong", "exact"
    )
    try:
        runner.validate_ux1b_ready_markers(changed_markers)
    except runner.RunnerDataError as exc:
        assert "ready-marker" in str(exc).lower()
    else:
        raise AssertionError("runner accepted a mutated 27-marker catalog")

    live = runner.live_ux1b_projection()
    runner.validate_ux1b_projection(live)
    changed = [dict(item) for item in live]
    changed[2]["route"] = "/still-27-but-wrong"
    try:
        runner.validate_ux1b_projection(changed)
    except runner.RunnerDataError as exc:
        assert "projection" in str(exc).lower()
    else:
        raise AssertionError("runner accepted a mutated 27-page projection")


def test_ux1b_cli_profile_builds_exact_chromium_81_matrix() -> None:
    runner = _runner()
    parser = runner.build_parser()
    argv = [
        "--profile",
        "ux1b-full-pages",
        "--phase",
        "pretheme",
        "--browser",
        "chromium",
        "--no-prompt",
        "--json",
    ]
    args = parser.parse_args(argv)
    cases, viewports = runner._prepare_args(args)
    assert len(cases) == 27
    assert tuple(item.page for item in cases) == tuple(item[0] for item in UX1B_PROJECTION)
    assert viewports == (
        ("desktop", 1440, 900),
        ("tablet", 768, 1024),
        ("mobile", 390, 844),
    )
    assert runner.UX1B_VIEWPORTS == viewports
    assert len(cases) * len(viewports) == 81
    with tempfile.TemporaryDirectory() as td:
        owned = runner.create_owned_run(Path(td) / "manifest")
        manifest = runner._manifest_template(
            owned,
            cases=cases,
            viewports=viewports,
            profile=args.profile,
            phase=args.phase,
        )
    assert manifest["mode"] == "ux1b-full-pages"
    assert manifest["phase"] == "pretheme"
    assert manifest["projectionSha256"] == runner.UX1B_PROJECTION_SHA256
    assert manifest["expectedCapturesPerBrowser"] == 81
    assert len(manifest["cases"]) == 27

    invalid_argv = (
        ["--profile", "ux1b-full-pages", "--phase", "pretheme", "--no-prompt", "--json"],
        ["--profile", "ux1b-full-pages", "--phase", "pretheme", "--browser", "webkit", "--no-prompt", "--json"],
        ["--profile", "ux1b-full-pages", "--browser", "chromium", "--no-prompt", "--json"],
        ["--profile", "ux1b-full-pages", "--phase", "pretheme", "--browser", "chromium", "--json"],
        ["--profile", "ux1b-full-pages", "--phase", "pretheme", "--browser", "chromium", "--no-prompt"],
        ["--profile", "ux1b-full-pages", "--phase", "pretheme", "--browser", "chromium", "--no-prompt", "--json", "--page", "today-decision"],
        ["--profile", "ux1b-full-pages", "--phase", "pretheme", "--browser", "chromium", "--no-prompt", "--json", "--viewport", "desktop"],
    )
    for bad in invalid_argv:
        try:
            runner._prepare_args(parser.parse_args(bad))
        except runner.RunnerDataError:
            pass
        else:
            raise AssertionError(f"runner accepted invalid UX1B argv: {bad!r}")


def test_ux1b_recovery_profiles_freeze_both_phase_matrices() -> None:
    runner = _runner()
    parser = runner.build_parser()
    assert runner.UX1B_SOURCE_MIRROR_INCLUDE == (
        ".streamlit/config.toml",
        "app.py",
        "api/**/*.py",
        "scripts/**/*.py",
        "ui/**/*.py",
        "docs/ui-ux/quant-radar-ui-v2-baseline.json",
    )
    assert runner.UX1B_SOURCE_MIRROR_EXCLUDE == (
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

    def prepared(profile: str, phase: str):
        args = parser.parse_args(
            [
                "--profile",
                profile,
                "--phase",
                phase,
                "--browser",
                "chromium",
                "--no-prompt",
                "--json",
            ]
        )
        return runner._prepare_args(args)

    for phase in ("precontrol", "pretheme", "posttheme"):
        cases, viewports = prepared("ux1b-full-pages", phase)
        assert len(cases) == 27
        assert viewports == (
            ("desktop", 1440, 900),
            ("tablet", 768, 1024),
            ("mobile", 390, 844),
        )
        assert len(cases) * len(viewports) == 81

    for phase in ("precontrol", "postcontrol"):
        cases, viewports = prepared("ux1b-selection-controls", phase)
        assert len(cases) == 9
        assert viewports == (
            ("desktop", 1440, 900),
            ("tablet", 768, 1024),
            ("mobile", 390, 844),
            ("narrow", 320, 844),
        )
        assert len(cases) * len(viewports) == 36

    for profile, phase in (
        ("ux1b-full-pages", "postcontrol"),
        ("ux1b-selection-controls", "pretheme"),
        ("ux1b-selection-controls", "posttheme"),
    ):
        try:
            prepared(profile, phase)
        except runner.RunnerDataError:
            pass
        else:
            raise AssertionError(f"accepted incompatible UX1B phase: {profile}/{phase}")


def test_ux1b_recovery_dispatch_has_no_direct_browser_launch() -> None:
    runner = _runner()
    run_source = inspect.getsource(runner.run_matrix)
    recovery_source = inspect.getsource(runner._run_ux1b_recovery)
    assert run_source.index("_run_ux1b_recovery") < run_source.index("sync_playwright")
    assert ".launch(" not in recovery_source
    for required in (
        "build_source_mirror",
        "calibrate_darwin_profiles",
        "spawn_calibrated_child",
        "authenticate_counter_bundle",
        "authenticate_raw_render_sidecar",
        "publish_finalized_capture",
        "verify_capture_artifacts",
        "validate_live_capture_profile",
        "ManifestLifecycle",
        "finalize_terminal_manifest",
    ):
        assert required in recovery_source, required


def test_ux1b_control_discovery_is_exact_57_and_does_not_publish() -> None:
    runner = _runner()
    rows = runner.ux1b_control_discovery_rows()
    assert len(rows) == 57
    assert sum(
        row["fixtureEntrypoint"] == "scripts/ui_ux_fixture_app.py"
        for row in rows
    ) == 21
    assert sum(
        row["fixtureEntrypoint"]
        == "scripts/ui_ux_selection_fixture_app.py"
        for row in rows
    ) == 36
    discovery_source = inspect.getsource(runner.derive_ux1b_control_catalog)
    assert "derive_control_catalog" in discovery_source
    assert "publish_capture_stack_contract" not in discovery_source
    wrapper_source = inspect.getsource(runner.run_ux1b_control_discovery)
    runtime_source = inspect.getsource(runner._run_ux1b_nonterminal_capture)
    for required in (
        "calibrate_darwin_profiles",
        "spawn_calibrated_child",
        "authenticate_raw_render_sidecar",
    ):
        assert required in runtime_source, required
    for source in (wrapper_source, runtime_source):
        assert "ManifestLifecycle" not in source
        assert "publish_finalized_capture" not in source
        assert '"passed"' not in source

    evidence = runner._evidence_api()
    response = {
        "schemaVersion": evidence.WORKER_RESPONSE_SCHEMA,
        "requestId": "analytics-db/desktop",
        "status": "invalid_data",
        "error": {"type": "WorkerBootstrapError", "message": "bounded"},
    }
    with tempfile.TemporaryFile("w+b") as stream:
        stream.write(
            (
                json.dumps(
                    response,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
        )
        stream.flush()
        stdio = types.SimpleNamespace(stdout=stream)
        try:
            runner._raise_worker_exit(
                evidence,
                stdio,
                capture_id="analytics-db/desktop",
                allowed_paths=frozenset(("stage/capture.png", "stage/render.json")),
                cause=RuntimeError("nonzero"),
            )
        except runner.RunnerDataError as exc:
            assert "WorkerBootstrapError" in str(exc)
        else:
            raise AssertionError("invalid worker response was not classified")


def test_ux1b_real_smoke_is_exact_authenticated_1_plus_9() -> None:
    runner = _runner()
    rows = runner.ux1b_real_smoke_rows()
    expected_ids = tuple(
        f'{row["case"]}/{row["viewport"]["name"]}' for row in rows
    )
    assert len(rows) == 10
    assert expected_ids[0] == "stock-checkup/mobile"
    assert len(set(expected_ids[1:])) == 9
    assert all(
        row["viewport"] == {"name": "mobile", "width": 390, "height": 844}
        for row in rows
    )
    assert sum(
        row["fixtureEntrypoint"] == "scripts/ui_ux_fixture_app.py"
        for row in rows
    ) == 1
    assert sum(
        row["fixtureEntrypoint"]
        == "scripts/ui_ux_selection_fixture_app.py"
        for row in rows
    ) == 9

    runtime_source = inspect.getsource(runner._run_ux1b_nonterminal_capture)
    for required in (
        "decode_worker_response",
        "authenticate_raw_render_sidecar",
        "_authenticate_ux1b_smoke_png",
        "authenticate_counter_bundle",
        "consume_quiescent_process_exit_provenance",
        "capture_stack_digest",
        "authenticate_source_mirror",
    ):
        assert required in runtime_source, required
    for forbidden in (
        "ManifestLifecycle",
        "publish_finalized_capture",
        "finalize_terminal_manifest",
        "capture_stage.mkdir",
        '"passed"',
    ):
        assert forbidden not in runtime_source, forbidden
    assert "capture_stage.mkdir" not in inspect.getsource(runner._run_ux1b_recovery)

    fake_result = runner._UX1BNonterminalResult(
        base_capture_stack_digest="a" * 64,
        source_digest="b" * 64,
        capture_ids=expected_ids,
        sidecars=tuple(object() for _ in rows),
        pngs=tuple(
            {
                "captureId": capture_id,
                "path": f"smoke/{capture_id}/capture.png",
                "sha256": "c" * 64,
                "size": 1,
                "width": 390,
                "height": 844,
            }
            for capture_id in expected_ids
        ),
        counter_capture_ids=tuple(sorted(expected_ids)),
        quiescent_process_count=12,
    )
    with tempfile.TemporaryDirectory() as td:
        workspace_fd = os.open(td, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            with patch.object(
                runner,
                "_run_ux1b_nonterminal_capture",
                return_value=fake_result,
            ) as capture:
                observed = runner.run_ux1b_real_smoke(workspace_fd=workspace_fd)
        finally:
            os.close(workspace_fd)
    assert observed.capture_ids == expected_ids
    assert observed.counter_capture_ids == tuple(sorted(expected_ids))
    assert observed.quiescent_process_count == 12
    called_rows = capture.call_args.args[0]
    assert tuple(
        f'{row["case"]}/{row["viewport"]["name"]}' for row in called_rows
    ) == expected_ids
    assert capture.call_args.kwargs == {
        "label": "smoke",
        "expected_group_counts": {
            runner.UX1B_PROFILE: 1,
            runner.UX1B_SELECTION_PROFILE: 9,
        },
        "authenticate_pngs": True,
        "authenticate_counters": True,
        "workspace_fd": workspace_fd,
    }


def test_ux1b_nonterminal_cleanup_preserves_primary_failure() -> None:
    runner = _runner()
    primary = ValueError("capture-root-cause")
    cleanup = RuntimeError("cleanup-secondary")
    release = OSError("release-secondary")
    runner._finish_ux1b_nonterminal_cleanup(primary, cleanup, release)
    assert primary.__notes__ == [
        "process-family cleanup also failed: RuntimeError: cleanup-secondary",
        "nonterminal runtime release also failed: OSError: release-secondary",
    ]
    for first, second, expected in (
        (cleanup, release, cleanup),
        (None, release, release),
    ):
        try:
            runner._finish_ux1b_nonterminal_cleanup(None, first, second)
        except BaseException as exc:
            assert exc is expected
        else:
            raise AssertionError("successful capture suppressed a cleanup failure")


def test_freeze_ux1b_capture_stack_is_one_ordered_atomic_transaction() -> None:
    runner = _runner()
    call_order: list[str] = []
    base_digest = "a" * 64
    contract_digest = "b" * 64
    contract_sha256 = "c" * 64
    catalog = object()
    contract = {
        "schemaVersion": "quant-radar-ui-ux-ux1b-capture-stack/v1",
        "baseCaptureStackDigest": base_digest,
        "captureStackDigest": contract_digest,
    }
    discovery = runner.UX1BControlDiscovery(
        base_capture_stack_digest=base_digest,
        source_digest="d" * 64,
        sidecars=tuple(object() for _ in range(57)),
    )
    smoke = runner.UX1BRealSmoke(
        base_capture_stack_digest=base_digest,
        source_digest=discovery.source_digest,
        capture_ids=tuple(f"case-{index}/mobile" for index in range(10)),
        sidecars=tuple(object() for _ in range(10)),
        pngs=tuple({"width": 390, "height": 844} for _ in range(10)),
        counter_capture_ids=tuple(f"case-{index}/mobile" for index in range(10)),
        quiescent_process_count=12,
    )

    def digest(*_args, **_kwargs):
        call_order.append("digest")
        assert _kwargs["root_fd"] == destination_object.workspace_fd
        return base_digest

    def build(*_args, **_kwargs):
        call_order.append("build")
        assert _kwargs["root_fd"] == destination_object.workspace_fd
        return contract

    def publish(*_args, **_kwargs):
        call_order.append("publish")
        assert _kwargs["workspace_root_fd"] == destination_object.workspace_fd
        return {
            "path": "quant-radar-ui-v2-ux1b-capture-stack.json",
            "sha256": contract_sha256,
            "size": 321,
            "captureStackDigest": contract_digest,
        }

    def authenticate(*_args, **_kwargs):
        call_order.append("authenticate")
        assert _kwargs["expected_sha256"] == contract_sha256
        assert _kwargs["workspace_root_fd"] == destination_object.workspace_fd
        return contract, catalog, contract_sha256

    fake_evidence = types.SimpleNamespace(
        capture_stack_digest=digest,
        build_capture_stack_contract=build,
        publish_capture_stack_contract=publish,
        authenticate_capture_stack_contract=authenticate,
    )
    with tempfile.TemporaryDirectory() as td:
        root_fd = os.open(td, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        parent_fd = os.dup(root_fd)

        destination_object = types.SimpleNamespace(
            workspace_fd=root_fd,
            parent_fd=parent_fd,
            relative_path=(
                "docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json"
            ),
            leaf_name="quant-radar-ui-v2-ux1b-capture-stack.json",
        )

        def close_destination():
            os.close(destination_object.parent_fd)
            os.close(destination_object.workspace_fd)

        destination_object.close = close_destination

        def discover(*, workspace_fd):
            call_order.append("discovery")
            assert workspace_fd == destination_object.workspace_fd
            return discovery

        def run_smoke(*, workspace_fd):
            call_order.append("smoke")
            assert workspace_fd == destination_object.workspace_fd
            return smoke

        def derive(*_args, **_kwargs):
            call_order.append("derive")
            return catalog

        def destination():
            call_order.append("open-destination")
            return destination_object

        def reauthenticate(_destination):
            call_order.append("reauthenticate-destination")

        with (
            patch.object(runner, "_evidence_api", return_value=fake_evidence),
            patch.object(runner, "run_ux1b_control_discovery", side_effect=discover),
            patch.object(runner, "run_ux1b_real_smoke", side_effect=run_smoke),
            patch.object(runner, "derive_ux1b_control_catalog", side_effect=derive),
            patch.object(
                runner,
                "_open_ux1b_capture_stack_destination",
                side_effect=destination,
            ),
            patch.object(
                runner,
                "_reauthenticate_ux1b_capture_stack_destination",
                side_effect=reauthenticate,
            ),
        ):
            result = runner.freeze_ux1b_capture_stack()
        assert list(Path(td).iterdir()) == []

    assert call_order == [
        "open-destination",
        "reauthenticate-destination",
        "digest",
        "discovery",
        "smoke",
        "derive",
        "digest",
        "build",
        "publish",
        "reauthenticate-destination",
        "authenticate",
        "reauthenticate-destination",
    ]
    assert result == {
        "status": "frozen",
        "path": "docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json",
        "sha256": contract_sha256,
        "size": 321,
        "baseCaptureStackDigest": base_digest,
        "captureStackDigest": contract_digest,
        "sourceDigest": discovery.source_digest,
        "discoverySidecars": 57,
        "smokeCaptures": 10,
        "smokeQuiescentProcesses": 12,
    }


def _test_capture_stack_destination(
    root: Path,
    relative_path: str,
    *,
    payload: bytes | None = None,
    close_error: BaseException | None = None,
) -> types.SimpleNamespace:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if payload is not None:
        path.write_bytes(payload)
    workspace_fd = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    parent_fd = os.open(
        path.parent,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    destination = types.SimpleNamespace(
        workspace_fd=workspace_fd,
        parent_fd=parent_fd,
        relative_path=relative_path,
        leaf_name=path.name,
        closed=False,
        close_calls=0,
    )

    def close_destination() -> BaseException | None:
        destination.close_calls += 1
        if destination.closed:
            return None
        destination.closed = True
        os.close(destination.parent_fd)
        os.close(destination.workspace_fd)
        return close_error

    destination.close = close_destination
    return destination


def _run_capture_stack_rotation_wiring(
    *,
    fail_at: str | None = None,
    receipt_mutation: tuple[str, object] | None = None,
    close_failures: frozenset[str] = frozenset(),
):
    runner = _runner()
    call_order: list[str] = []
    base_digest = "a" * 64
    contract_digest = "b" * 64
    source_digest = "d" * 64
    old_raw = b"old canonical capture-stack contract\n"
    old_sha256 = hashlib.sha256(old_raw).hexdigest()
    old_contract = types.SimpleNamespace(
        leaf=types.SimpleNamespace(
            sha256=old_sha256,
            size=len(old_raw),
            mode=0o600,
            link_count=1,
        )
    )
    catalog = object()
    archive_name = f"superseded-capture-stack-{old_sha256}.json"
    contract = {
        "schemaVersion": "quant-radar-ui-ux-ux1b-capture-stack/v1",
        "baseCaptureStackDigest": base_digest,
        "captureStackDigest": contract_digest,
    }
    contract_raw = json.dumps(
        contract,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    contract_sha256 = hashlib.sha256(contract_raw).hexdigest()
    contract_size = len(contract_raw)
    discovery = runner.UX1BControlDiscovery(
        base_capture_stack_digest=base_digest,
        source_digest=source_digest,
        sidecars=tuple(object() for _ in range(57)),
    )
    smoke = runner.UX1BRealSmoke(
        base_capture_stack_digest=base_digest,
        source_digest=source_digest,
        capture_ids=tuple(f"case-{index}/mobile" for index in range(10)),
        sidecars=tuple(object() for _ in range(10)),
        pngs=tuple({"width": 390, "height": 844} for _ in range(10)),
        counter_capture_ids=tuple(f"case-{index}/mobile" for index in range(10)),
        quiescent_process_count=12,
    )
    receipt = {
        "path": "quant-radar-ui-v2-ux1b-capture-stack.json",
        "sha256": contract_sha256,
        "size": contract_size,
        "captureStackDigest": contract_digest,
        "previousSha256": old_sha256,
        "archiveName": archive_name,
        "archiveSha256": old_sha256,
        "archiveSize": len(old_raw),
    }
    if receipt_mutation is not None:
        receipt[receipt_mutation[0]] = receipt_mutation[1]
    failure = RuntimeError(f"{fail_at}-failed")
    durability_failure = runner._evidence_api().ManifestDurabilityUncertain(
        "rotate-durability-uncertain"
    )
    canonical_close_failure = RuntimeError("canonical-close-failed")
    archive_close_failure = RuntimeError("archive-close-failed")

    def stage(name: str, value):
        call_order.append(name)
        if fail_at == name:
            raise failure
        return value

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        canonical = _test_capture_stack_destination(
            root,
            "docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json",
            payload=old_raw,
            close_error=(
                canonical_close_failure
                if "canonical" in close_failures
                else None
            ),
        )
        archive = _test_capture_stack_destination(
            root,
            f".claude/ui_snapshots/ux1b/recovery/{archive_name}",
            close_error=(
                archive_close_failure
                if "archive" in close_failures
                else None
            ),
        )

        def freeze_old(root_fd, relative_path, *, expected_owner, max_bytes):
            assert root_fd == canonical.parent_fd
            assert relative_path == canonical.leaf_name
            assert expected_owner == os.getuid()
            assert max_bytes == 2 * 1024 * 1024
            return stage("freeze-old", old_contract)

        def digest(*_args, **kwargs):
            assert kwargs["root_fd"] == canonical.workspace_fd
            return stage("digest", base_digest)

        def build(*_args, **kwargs):
            assert kwargs["root_fd"] == canonical.workspace_fd
            return stage("build", contract)

        def rotate(output_dir_fd, output_name, document, **kwargs):
            assert output_dir_fd == canonical.parent_fd
            assert output_name == canonical.leaf_name
            assert document is contract
            assert kwargs == {
                "expected_existing_contract": old_contract,
                "expected_existing_sha256": old_sha256,
                "archive_dir_fd": archive.parent_fd,
                "archive_name": archive_name,
                "workspace_root_fd": canonical.workspace_fd,
            }
            if fail_at == "rotate-uncertain":
                call_order.append("rotate")
                raise durability_failure
            return stage("rotate", receipt)

        def authenticate(root_fd, relative_path, **kwargs):
            assert root_fd == canonical.workspace_fd
            assert relative_path == canonical.relative_path
            assert kwargs["expected_owner"] == os.getuid()
            assert kwargs["expected_sha256"] == contract_sha256
            assert kwargs["workspace_root_fd"] == canonical.workspace_fd
            return stage("authenticate", (contract, catalog, contract_sha256))

        fake_evidence = types.SimpleNamespace(
            MAX_CONTROL_CATALOG_BYTES=2 * 1024 * 1024,
            freeze_artifact_contract=freeze_old,
            capture_stack_digest=digest,
            build_capture_stack_contract=build,
            publish_capture_stack_contract=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("rotation used the create-only publisher")
            ),
            rotate_capture_stack_contract=rotate,
            authenticate_capture_stack_contract=authenticate,
        )

        def open_canonical():
            call_order.append("open-canonical")
            return canonical

        def open_archive(requested_name):
            call_order.append("open-archive")
            assert requested_name == archive_name
            return archive

        def reauthenticate(destination):
            label = "canonical" if destination is canonical else "archive"
            assert destination is canonical or destination is archive
            call_order.append(f"reauthenticate-{label}")

        def discover(*, workspace_fd):
            assert workspace_fd == canonical.workspace_fd
            return stage("discovery", discovery)

        def run_smoke(*, workspace_fd):
            assert workspace_fd == canonical.workspace_fd
            return stage("smoke", smoke)

        def derive(sidecars, *, base_capture_stack_digest):
            assert sidecars == discovery.sidecars
            assert base_capture_stack_digest == base_digest
            return stage("derive", catalog)

        observed_error = None
        result = None
        try:
            with (
                patch.object(runner, "_evidence_api", return_value=fake_evidence),
                patch.object(
                    runner,
                    "_open_ux1b_capture_stack_destination",
                    side_effect=open_canonical,
                ),
                patch.object(
                    runner,
                    "_open_ux1b_capture_stack_archive_destination",
                    side_effect=open_archive,
                    create=True,
                ),
                patch.object(
                    runner,
                    "_reauthenticate_ux1b_capture_stack_destination",
                    side_effect=reauthenticate,
                ),
                patch.object(
                    runner,
                    "run_ux1b_control_discovery",
                    side_effect=discover,
                ),
                patch.object(runner, "run_ux1b_real_smoke", side_effect=run_smoke),
                patch.object(
                    runner,
                    "derive_ux1b_control_catalog",
                    side_effect=derive,
                ),
            ):
                result = runner.freeze_ux1b_capture_stack(
                    expected_capture_stack_sha256=old_sha256
                )
        except BaseException as exc:
            observed_error = exc
        finally:
            if not archive.closed:
                archive.close()
            if not canonical.closed:
                canonical.close()

    return types.SimpleNamespace(
        call_order=call_order,
        result=result,
        error=observed_error,
        failure=failure,
        durability_failure=durability_failure,
        canonical_close_failure=canonical_close_failure,
        archive_close_failure=archive_close_failure,
        canonical_close_calls=canonical.close_calls,
        archive_close_calls=archive.close_calls,
        old_sha256=old_sha256,
        contract_sha256=contract_sha256,
        contract_digest=contract_digest,
        source_digest=source_digest,
        archive_name=archive_name,
        archive_size=len(old_raw),
        contract_size=contract_size,
    )


def test_freeze_existing_capture_stack_rotates_in_exact_authenticated_order() -> None:
    observed = _run_capture_stack_rotation_wiring()
    assert observed.error is None, observed.error
    assert (observed.canonical_close_calls, observed.archive_close_calls) == (1, 1)
    assert observed.call_order == [
        "open-canonical",
        "reauthenticate-canonical",
        "freeze-old",
        "open-archive",
        "reauthenticate-archive",
        "digest",
        "discovery",
        "smoke",
        "derive",
        "digest",
        "build",
        "reauthenticate-canonical",
        "reauthenticate-archive",
        "rotate",
        "reauthenticate-canonical",
        "reauthenticate-archive",
        "authenticate",
        "reauthenticate-canonical",
        "reauthenticate-archive",
    ]
    assert observed.result == {
        "status": "frozen",
        "path": "docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json",
        "sha256": observed.contract_sha256,
        "size": observed.contract_size,
        "baseCaptureStackDigest": "a" * 64,
        "captureStackDigest": observed.contract_digest,
        "sourceDigest": observed.source_digest,
        "discoverySidecars": 57,
        "smokeCaptures": 10,
        "smokeQuiescentProcesses": 12,
        "previousSha256": observed.old_sha256,
        "archivePath": (
            ".claude/ui_snapshots/ux1b/recovery/" + observed.archive_name
        ),
        "archiveSha256": observed.old_sha256,
        "archiveSize": observed.archive_size,
    }


def test_freeze_discovery_smoke_and_build_failures_never_rotate() -> None:
    for stage in ("discovery", "smoke", "build"):
        observed = _run_capture_stack_rotation_wiring(fail_at=stage)
        assert observed.error is observed.failure, (stage, observed.error)
        assert "rotate" not in observed.call_order, (stage, observed.call_order)
        assert "authenticate" not in observed.call_order, (stage, observed.call_order)


def test_freeze_destination_close_failures_are_not_suppressed() -> None:
    observed = _run_capture_stack_rotation_wiring(
        close_failures=frozenset({"canonical"})
    )
    assert observed.error is observed.canonical_close_failure, observed.error
    assert (observed.canonical_close_calls, observed.archive_close_calls) == (1, 1)

    observed = _run_capture_stack_rotation_wiring(
        fail_at="build",
        close_failures=frozenset({"canonical", "archive"}),
    )
    assert observed.error is observed.failure, observed.error
    assert getattr(observed.error, "__notes__", []) == [
        "capture-stack archive destination close also failed: "
        "RuntimeError: archive-close-failed",
        "capture-stack canonical destination close also failed: "
        "RuntimeError: canonical-close-failed",
    ]
    assert (observed.canonical_close_calls, observed.archive_close_calls) == (1, 1)

    observed = _run_capture_stack_rotation_wiring(
        fail_at="rotate-uncertain",
        close_failures=frozenset({"canonical", "archive"}),
    )
    assert observed.error is observed.durability_failure, observed.error
    assert getattr(observed.error, "__notes__", []) == [
        "capture-stack archive destination close also failed: "
        "RuntimeError: archive-close-failed",
        "capture-stack canonical destination close also failed: "
        "RuntimeError: canonical-close-failed",
    ]
    assert (observed.canonical_close_calls, observed.archive_close_calls) == (1, 1)


def test_freeze_rejects_rotation_receipt_metadata_drift() -> None:
    mutations = (
        ("path", "wrong.json"),
        ("sha256", "0" * 64),
        ("size", 322),
        ("captureStackDigest", "1" * 64),
        ("previousSha256", "2" * 64),
        ("archiveName", "wrong-archive.json"),
        ("archiveSha256", "3" * 64),
        ("archiveSize", 999),
    )
    for mutation in mutations:
        observed = _run_capture_stack_rotation_wiring(receipt_mutation=mutation)
        assert isinstance(observed.error, _runner().RunnerDataError), (
            mutation,
            observed.error,
        )
        assert "authenticate" not in observed.call_order, (
            mutation,
            observed.call_order,
        )


def test_freeze_expected_sha_is_required_exactly_for_existing_canonical() -> None:
    runner = _runner()
    old_raw = b"existing canonical\n"
    old_sha256 = hashlib.sha256(old_raw).hexdigest()
    for payload, expected_sha in ((old_raw, None), (None, old_sha256)):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            canonical = _test_capture_stack_destination(
                root,
                "docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json",
                payload=payload,
            )
            try:
                with (
                    patch.object(
                        runner,
                        "_open_ux1b_capture_stack_destination",
                        return_value=canonical,
                    ),
                    patch.object(
                        runner,
                        "_reauthenticate_ux1b_capture_stack_destination",
                    ),
                    patch.object(
                        runner,
                        "run_ux1b_control_discovery",
                        side_effect=AssertionError("mismatched SHA mode reached discovery"),
                    ),
                ):
                    try:
                        runner.freeze_ux1b_capture_stack(
                            expected_capture_stack_sha256=expected_sha
                        )
                    except runner.RunnerDataError:
                        pass
                    else:
                        raise AssertionError(
                            "capture-stack freeze accepted mismatched expected-SHA mode"
                        )
            finally:
                canonical.close()


def test_ux1b_special_cli_modes_are_json_only_and_capture_arg_exclusive() -> None:
    runner = _runner()
    parser = runner.build_parser()
    expected_sha256 = "e" * 64
    freeze_args = parser.parse_args(
        [
            "--freeze-capture-stack",
            "--expected-capture-stack-sha256",
            expected_sha256,
            "--json",
        ]
    )
    assert freeze_args.freeze_capture_stack is True
    assert freeze_args.ux1b_real_smoke is False
    assert freeze_args.expected_capture_stack_sha256 == expected_sha256
    smoke_args = parser.parse_args(["--ux1b-real-smoke", "--json"])
    assert smoke_args.ux1b_real_smoke is True
    assert smoke_args.freeze_capture_stack is False
    assert smoke_args.expected_capture_stack_sha256 is None

    for raw_args in (
        ["--freeze-capture-stack"],
        ["--ux1b-real-smoke"],
        ["--freeze-capture-stack", "--ux1b-real-smoke", "--json"],
        ["--freeze-capture-stack", "--profile", runner.UX1B_PROFILE, "--json"],
        ["--ux1b-real-smoke", "--viewport", "mobile", "--json"],
        [
            "--ux1b-real-smoke",
            "--expected-capture-stack-sha256",
            expected_sha256,
            "--json",
        ],
        ["--expected-capture-stack-sha256", expected_sha256, "--json"],
    ):
        parsed = parser.parse_args(raw_args)
        try:
            runner._ux1b_special_cli_mode(parsed, parser)
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError(f"special CLI accepted incompatible args: {raw_args}")

    frozen = {
        "status": "frozen",
        "path": "docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json",
    }
    with (
        patch.object(
            runner,
            "freeze_ux1b_capture_stack",
            return_value=frozen,
        ) as freeze,
        patch("builtins.print") as printed,
    ):
        assert runner.main(
            [
                "--freeze-capture-stack",
                "--expected-capture-stack-sha256",
                expected_sha256,
                "--json",
            ]
        ) == 0
    assert freeze.call_args.kwargs == {
        "expected_capture_stack_sha256": expected_sha256
    }
    emitted = json.loads(printed.call_args.args[0])
    assert emitted == frozen


def test_ux1b_namespace_rejects_legacy_and_external_outputs() -> None:
    runner = _runner()
    valid = ROOT / ".claude" / "ui_snapshots" / "ux1b" / "unit-contract"
    assert runner.validate_output_namespace(valid, profile="ux1b-full-pages") == valid.resolve()
    for bad in (
        ROOT / ".claude" / "ui_snapshots" / "ux0" / "wrong",
        ROOT / ".claude" / "ui_snapshots" / "ux1a" / "wrong",
        Path(tempfile.gettempdir()) / "quant-radar-ux1b-wrong",
    ):
        try:
            runner.validate_output_namespace(bad, profile="ux1b-full-pages")
        except runner.RunnerDataError as exc:
            assert "ux1b" in str(exc).lower()
        else:
            raise AssertionError(f"UX1B accepted output namespace {bad}")


def test_ux1b_output_namespace_rejects_writable_and_swapped_components() -> None:
    runner = _runner()
    ux1b_root = ROOT / ".claude" / "ui_snapshots" / "ux1b"
    ux1b_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ux1b_root) as td, tempfile.TemporaryDirectory() as external:
        scope = Path(td)
        safe_parent = scope / "safe"
        safe_parent.mkdir(mode=0o700)
        namespace = runner._open_ux1b_output_namespace(safe_parent / "capture")
        try:
            runner._reauthenticate_ux1b_output_namespace(namespace)
            detached = scope / "safe-detached"
            safe_parent.rename(detached)
            safe_parent.symlink_to(Path(external), target_is_directory=True)
            try:
                runner._reauthenticate_ux1b_output_namespace(namespace)
            except runner.RunnerDataError:
                pass
            else:
                raise AssertionError("swapped UX1B output parent was accepted")
        finally:
            namespace.close()

        reparent_scope = scope / "reparent"
        original_a = reparent_scope / "a"
        retained_b = original_a / "b"
        retained_b.mkdir(parents=True, mode=0o700)
        namespace = runner._open_ux1b_output_namespace(
            retained_b / "capture"
        )
        try:
            detached_a = reparent_scope / "a-old"
            original_a.rename(detached_a)
            original_a.mkdir(mode=0o700)
            (detached_a / "b").rename(original_a / "b")
            try:
                runner._reauthenticate_ux1b_output_namespace(namespace)
            except runner.RunnerDataError:
                pass
            else:
                raise AssertionError(
                    "same retained parent under a replacement ancestor was accepted"
                )
        finally:
            namespace.close()

        writable = scope / "writable"
        writable.mkdir(mode=0o770)
        writable.chmod(0o770)
        try:
            runner._open_ux1b_output_namespace(writable / "capture")
        except runner.RunnerDataError:
            pass
        else:
            raise AssertionError("group-writable output component was accepted")


def test_ux1b_capture_stack_destination_rejects_retained_parent_reparent() -> None:
    runner = _runner()
    with tempfile.TemporaryDirectory() as raw:
        workspace = Path(raw)
        docs = workspace / "docs"
        retained_parent = docs / "ui-ux"
        retained_parent.mkdir(parents=True, mode=0o700)
        contract_path = (
            retained_parent / "quant-radar-ui-v2-ux1b-capture-stack.json"
        )
        with (
            patch.object(runner, "WORKSPACE_ROOT", workspace),
            patch.object(
                runner,
                "UX1B_CAPTURE_STACK_CONTRACT_PATH",
                contract_path,
            ),
        ):
            destination = runner._open_ux1b_capture_stack_destination()
            try:
                detached_docs = workspace / "docs-old"
                docs.rename(detached_docs)
                docs.mkdir(mode=0o700)
                (detached_docs / "ui-ux").rename(docs / "ui-ux")
                try:
                    runner._reauthenticate_ux1b_capture_stack_destination(
                        destination
                    )
                except runner.RunnerDataError:
                    pass
                else:
                    raise AssertionError(
                        "capture-stack parent reparented under a new docs ancestor"
                    )
            finally:
                destination.close()


def test_ux1b_formal_contract_authentication_is_workspace_fd_bound() -> None:
    runner = _runner()
    relative_path = "docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json"
    contract = {
        "members": [
            {"path": path}
            for path in sorted(runner.UX1B_CAPTURE_STACK_MEMBERS)
        ]
    }

    def exercise(attack: str) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw)
            docs = workspace / "docs"
            retained_parent = docs / "ui-ux"
            retained_parent.mkdir(parents=True, mode=0o700)
            contract_path = workspace / relative_path
            contract_path.write_text("{}\n", encoding="utf-8")
            workspace_identity = os.stat(workspace)
            calls = 0

            def authenticate(root_fd, observed_path, **kwargs):
                nonlocal calls
                calls += 1
                retained_root = os.fstat(root_fd)
                assert (retained_root.st_dev, retained_root.st_ino) == (
                    workspace_identity.st_dev,
                    workspace_identity.st_ino,
                )
                assert observed_path == relative_path
                assert kwargs["workspace_root_fd"] == root_fd
                assert "workspace_root" not in kwargs
                detached_docs = workspace / "docs-old"
                docs.rename(detached_docs)
                if attack == "reparent":
                    docs.mkdir(mode=0o700)
                    (detached_docs / "ui-ux").rename(docs / "ui-ux")
                else:
                    docs.symlink_to(detached_docs, target_is_directory=True)
                return contract, object(), "a" * 64

            fake_evidence = types.SimpleNamespace(
                authenticate_capture_stack_contract=authenticate,
            )
            with (
                patch.object(runner, "WORKSPACE_ROOT", workspace),
                patch.object(
                    runner,
                    "UX1B_CAPTURE_STACK_CONTRACT_PATH",
                    contract_path,
                ),
                patch.object(runner, "_evidence_api", return_value=fake_evidence),
            ):
                try:
                    runner._authenticate_ux1b_capture_stack_contract()
                except runner.RunnerDataError:
                    pass
                else:
                    raise AssertionError(
                        f"formal contract accepted intermediate {attack}"
                    )
            assert calls == 1

    exercise("reparent")
    exercise("symlink")

    formal_source = "".join(inspect.getsource(runner._run_ux1b_recovery).split())
    nonterminal_source = "".join(
        inspect.getsource(runner._run_ux1b_nonterminal_capture).split()
    )
    assert (
        "_authenticate_ux1b_capture_stack_contract("
        "workspace_fd=owned_runtime.namespace.workspace_fd)"
    ) in formal_source
    assert (
        "isolation.build_source_mirror("
        "workspace_root_fd=owned_runtime.namespace.workspace_fd,"
    ) in formal_source
    assert (
        "isolation.build_source_mirror(workspace_root_fd=workspace_fd,"
    ) in nonterminal_source
    assert "isolation.build_source_mirror(workspace_root=WORKSPACE_ROOT," not in (
        formal_source + nonterminal_source
    )


def test_ux1b_export_is_inode_bound_and_durability_fail_closed() -> None:
    runner = _runner()
    isolation = runner._isolation_api()
    ux1b_root = ROOT / ".claude" / "ui_snapshots" / "ux1b"
    ux1b_root.mkdir(parents=True, exist_ok=True)

    def source_root():
        runtime = isolation.create_owned_run_root(
            Path(tempfile.gettempdir()),
            prefix="ux1b-export-test-",
        )
        final = runtime.path / "final"
        final.mkdir(mode=0o700)
        final_fd = runner._directory_fd(final)
        return runtime, final, final_fd

    with tempfile.TemporaryDirectory(dir=ux1b_root) as td:
        scope = Path(td)

        runtime, final, final_fd = source_root()
        namespace = runner._open_ux1b_output_namespace(scope / "stable")
        retained = os.fstat(final_fd)
        try:
            outcome = runner._export_ux1b_evidence(
                final,
                namespace,
                source_parent_fd=runtime.descriptor,
                final_root_fd=final_fd,
            )
            published = os.stat(
                namespace.leaf_name,
                dir_fd=namespace.parent_fd,
                follow_symlinks=False,
            )
            assert outcome.published is True
            assert outcome.durability_confirmed is True
            assert (published.st_dev, published.st_ino, published.st_uid) == (
                retained.st_dev,
                retained.st_ino,
                retained.st_uid,
            )
        finally:
            os.close(final_fd)
            namespace.close()
            isolation.remove_owned_run_root(runtime)

        runtime, final, final_fd = source_root()
        namespace = runner._open_ux1b_output_namespace(scope / "revoked")
        original_fsync = runner.os.fsync
        failed = False

        def fail_destination_once(descriptor):
            nonlocal failed
            if descriptor == namespace.parent_fd and not failed:
                failed = True
                raise OSError("simulated destination fsync failure")
            return original_fsync(descriptor)

        try:
            runner.os.fsync = fail_destination_once
            try:
                runner._export_ux1b_evidence(
                    final,
                    namespace,
                    source_parent_fd=runtime.descriptor,
                    final_root_fd=final_fd,
                )
            except runner.RunnerDataError as exc:
                assert "revoked" in str(exc)
            else:
                raise AssertionError("durability failure was accepted as durable")
            restored = os.stat(
                "final",
                dir_fd=runtime.descriptor,
                follow_symlinks=False,
            )
            assert restored.st_ino == os.fstat(final_fd).st_ino
            try:
                os.stat(
                    namespace.leaf_name,
                    dir_fd=namespace.parent_fd,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("revoked output remained referenceable")
        finally:
            runner.os.fsync = original_fsync
            os.close(final_fd)
            namespace.close()
            isolation.remove_owned_run_root(runtime)


def test_ux1b_family_cleanup_ignores_poll_and_attempts_every_process() -> None:
    runner = _runner()

    class Process:
        def __init__(self, value):
            self.value = value

        def poll(self):
            raise AssertionError("cleanup must not branch on poll")

    processes = [Process(None), Process(0), Process(9)]
    calls = []
    failed_once = False

    class Isolation:
        @staticmethod
        def terminate_owned_process_group(process):
            nonlocal failed_once
            calls.append(process.value)
            if process.value is None and not failed_once:
                failed_once = True
                raise RuntimeError("first cleanup failed")

    attempted = set()
    error = runner._cleanup_ux1b_process_families(
        Isolation,
        processes,
        attempted,
    )
    assert isinstance(error, RuntimeError)
    assert calls == [None, 0, 9]
    assert attempted == {id(processes[1]), id(processes[2])}
    assert runner._cleanup_ux1b_process_families(
        Isolation,
        processes,
        attempted,
    ) is None
    assert calls == [None, 0, 9, None]
    assert attempted == {id(process) for process in processes}


def test_ux1b_cleanup_retries_real_child_and_retains_persistent_runtimes() -> None:
    runner = _runner()
    isolation = runner._isolation_api()

    def marker_process(label: str):
        process = subprocess.Popen(
            (
                sys.executable,
                "-c",
                "import time; time.sleep(30)",
                label,
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
        time.sleep(0.05)
        assert process.poll() is None
        return process

    transient_runtime = runner._prepare_ux1b_nonterminal_runtime(isolation)
    transient_process = marker_process("ux1b-transient-cleanup-marker")
    transient_calls = 0

    class FailsOnce:
        @staticmethod
        def terminate_owned_process_group(process):
            nonlocal transient_calls
            transient_calls += 1
            if transient_calls == 1:
                raise RuntimeError("transient termination failure")
            return isolation.terminate_owned_process_group(process)

    transient_attempted: set[int] = set()
    try:
        first_error = runner._cleanup_ux1b_process_families(
            FailsOnce,
            (transient_process,),
            transient_attempted,
        )
        assert isinstance(first_error, RuntimeError)
        assert transient_attempted == set()
        assert transient_runtime.runtime.path.is_dir()
        second_error = runner._quiesce_or_retain_ux1b_runtime(
            FailsOnce,
            transient_runtime,
            (transient_process,),
            transient_attempted,
        )
        assert second_error is None
        assert transient_calls == 2
        assert transient_attempted == {id(transient_process)}
        assert transient_process.poll() is not None
        assert runner._release_ux1b_nonterminal_runtime(
            isolation,
            transient_runtime,
        ) is None
        assert not transient_runtime.runtime.path.exists()
    finally:
        if transient_process.poll() is None:
            isolation.terminate_owned_process_group(transient_process)

    nonterminal_runtime = runner._prepare_ux1b_nonterminal_runtime(isolation)
    nonterminal_process = marker_process("ux1b-nonterminal-persistent-marker")

    class NonterminalAlwaysFails:
        @staticmethod
        def terminate_owned_process_group(_process):
            raise RuntimeError("persistent nonterminal termination failure")

    try:
        nonterminal_error = runner._quiesce_or_retain_ux1b_runtime(
            NonterminalAlwaysFails,
            nonterminal_runtime,
            (nonterminal_process,),
            set(),
        )
        assert isinstance(nonterminal_error, RuntimeError)
        assert nonterminal_runtime.runtime.path.is_dir()
        assert id(nonterminal_runtime) in runner._UX1B_RETAINED_RUNTIMES
    finally:
        isolation.terminate_owned_process_group(nonterminal_process)
        with runner._UX1B_RETAINED_RUNTIMES_LOCK:
            runner._UX1B_RETAINED_RUNTIMES.pop(
                id(nonterminal_runtime),
                None,
            )
        assert runner._release_ux1b_nonterminal_runtime(
            isolation,
            nonterminal_runtime,
        ) is None

    snapshot_root = ROOT / ".claude" / "ui_snapshots" / "ux1b"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=snapshot_root) as output:
        formal_runtime = runner._prepare_ux1b_formal_runtime(
            runner._evidence_api(),
            isolation,
            destination=Path(output),
            profile=runner.UX1B_PROFILE,
            phase="precontrol",
            fixture_entrypoint=runner.UX1B_FIXTURE_ENTRYPOINTS[
                runner.UX1B_PROFILE
            ],
            expected_count=81,
            run_id="ux1b-" + "9" * 24,
        )
        persistent_process = marker_process("ux1b-persistent-cleanup-marker")
        persistent_calls = 0

        class AlwaysFails:
            @staticmethod
            def terminate_owned_process_group(_process):
                nonlocal persistent_calls
                persistent_calls += 1
                raise RuntimeError("persistent termination failure")

        persistent_attempted: set[int] = set()
        try:
            for _attempt in range(2):
                error = runner._quiesce_or_retain_ux1b_runtime(
                    AlwaysFails,
                    formal_runtime,
                    (persistent_process,),
                    persistent_attempted,
                )
                assert isinstance(error, RuntimeError)
                assert persistent_attempted == set()
                assert formal_runtime.runtime.path.is_dir()
                assert formal_runtime.lease._closed is False
                assert id(formal_runtime) in runner._UX1B_RETAINED_RUNTIMES
            assert persistent_calls == 2
        finally:
            isolation.terminate_owned_process_group(persistent_process)
            with runner._UX1B_RETAINED_RUNTIMES_LOCK:
                runner._UX1B_RETAINED_RUNTIMES.pop(
                    id(formal_runtime),
                    None,
                )
            assert runner._release_ux1b_formal_runtime(
                isolation,
                formal_runtime,
            ) is None
            assert not formal_runtime.runtime.path.exists()


def test_ux1b_exact_port_policy_preserves_legacy_loopback_behavior() -> None:
    runner = _runner()
    allowed_ports = frozenset((43111, 43112))
    assert runner.is_allowed_browser_url("http://127.0.0.1:8000/")
    for url in (
        "http://127.0.0.1:43111/",
        "https://127.0.0.1:43112/deny",
        "ws://127.0.0.1:43111/_stcore/stream",
        "data:image/png;base64,AA==",
        "blob:http://127.0.0.1:43111/id",
    ):
        assert runner.is_allowed_browser_url(url, allowed_ports=allowed_ports), url
    for url in (
        "http://127.0.0.1:8000/",
        "http://localhost:43111/",
        "http://localhost.localdomain:43111/",
        "http://[::1]:43111/",
        "http://127.0.0.2:43111/",
        "http://127.255.255.254:43112/",
        "http://localhost:43113/",
        "ws://[::1]:43113/socket",
        "ws://localhost:43112/socket",
        "blob:http://127.0.0.1:8000/id",
        "blob:http://localhost:43111/id",
        "https://example.invalid/",
    ):
        assert not runner.is_allowed_browser_url(url, allowed_ports=allowed_ports), url

    class FakeWebSocket:
        def __init__(self, url: str) -> None:
            self.url = url
            self.connected = False

        def connect_to_server(self) -> None:
            self.connected = True

    blocked: list[dict[str, str]] = []
    wrong_port = FakeWebSocket("ws://127.0.0.1:8000/socket?secret=yes")
    runner.handle_browser_web_socket(
        wrong_port,
        blocked,
        allowed_ports=allowed_ports,
    )
    assert wrong_port.connected is False
    assert blocked == [{"method": "WEBSOCKET", "url": "ws://127.0.0.1:8000/socket"}]


def test_ux1b_source_digest_and_capture_identity_are_fail_closed() -> None:
    runner = _runner()
    live_projection = {
        path.relative_to(ROOT).as_posix()
        for path in runner.ux1b_source_paths()
    }
    assert "scripts/fundamentals_read.py" in live_projection
    assert "api/artifacts.py" in live_projection
    assert ".venv" not in {Path(path).parts[0] for path in live_projection}
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        first = root / "a.py"
        second = root / "b.py"
        first.write_text("a = 1\n", encoding="utf-8")
        second.write_text("b = 2\n", encoding="utf-8")
        before = runner.compute_source_digest((first, second), root=root)
        second.write_text("b = 3\n", encoding="utf-8")
        after = runner.compute_source_digest((first, second), root=root)
        assert len(before) == 64
        assert before != after

    with tempfile.TemporaryDirectory() as td:
        source_root = Path(td).resolve()
        (source_root / ".streamlit").mkdir()
        (source_root / "ui").mkdir()
        (source_root / "scripts").mkdir()
        (source_root / "api").mkdir()
        (source_root / ".streamlit" / "config.toml").write_text(
            "[theme]\n", encoding="utf-8"
        )
        (source_root / "Makefile").write_text("test:\n", encoding="utf-8")
        (source_root / "requirements.txt").write_text("streamlit\n", encoding="utf-8")
        (source_root / "app.py").write_text("import scripts.provider\n", encoding="utf-8")
        (source_root / "ui" / "page.py").write_text("VALUE = 1\n", encoding="utf-8")
        omitted = source_root / "scripts" / "provider.py"
        omitted.write_text("VALUE = 1\n", encoding="utf-8")
        (source_root / "api" / "artifacts.py").write_text("VALUE = 1\n", encoding="utf-8")
        first_digest = runner.ux1b_source_digest(root=source_root)
        projected = tuple(
            path.relative_to(source_root).as_posix()
            for path in runner.ux1b_source_paths(root=source_root)
        )
        assert projected == tuple(sorted(projected))
        assert "scripts/provider.py" in projected
        assert "api/artifacts.py" in projected
        omitted.write_text("VALUE = 2\n", encoding="utf-8")
        assert runner.ux1b_source_digest(root=source_root) != first_digest

    evidence = {
        "profile": "ux1b-full-pages",
        "headingReady": True,
        "streamlitException": False,
        "pageErrors": [],
        "blockedExternalRequests": [],
        "blockedServerNetwork": [],
        "fixtureQuiescent": True,
        "metrics": {},
        "fixture": {"counts": {}, "blockedNetwork": []},
        "identity": {
            "requestedRoute": "/trade-state",
            "finalBrowserPath": "/trade-state",
            "expectedRegistryKey": "trade-state",
            "selectedRegistryKey": "trade-state",
            "expectedCallable": "trade_state.render",
            "realCallable": "trade_state.render",
        },
    }
    assert runner.capture_failure_reasons(evidence) == []
    evidence["identity"]["finalBrowserPath"] = "/"
    evidence["identity"]["selectedRegistryKey"] = "today-decision"
    evidence["identity"]["realCallable"] = "today_decision.render"
    assert runner.capture_failure_reasons(evidence) == [
        "final_route_mismatch",
        "fixture_registry_identity_mismatch",
        "fixture_callable_identity_mismatch",
    ]

    contracts = runner.load_ux1b_fixture_contracts()
    page = next(
        item for item in runner.UX1B_PAGE_PROJECTION if item.registry_key == "trade-state"
    )
    with tempfile.TemporaryDirectory() as td:
        owned = runner.create_owned_run(Path(td) / "fixture-contract")
        route_paths = contracts["ownedPaths"][page.registry_key]
        counter_contract = contracts["counters"][page.registry_key]
        bucket = {
            "identity": {
                "selectedRegistryKey": page.registry_key,
                "realCallable": page.callable_name,
                "resolvedOwnedPaths": {
                    label: str((owned.fixture_root / relative).resolve())
                    for label, relative in route_paths.items()
                },
            },
            "counts": dict(counter_contract["positive"]),
            "blockedNetwork": [],
        }
        assert runner.ux1b_fixture_contract_failures(
            bucket,
            page=page,
            owned=owned,
            contracts=contracts,
        ) == []
        bucket["counts"]["undeclared.provider"] = 1
        bucket["identity"]["resolvedOwnedPaths"][next(iter(route_paths))] = str(
            ROOT / "reports"
        )
        assert runner.ux1b_fixture_contract_failures(
            bucket,
            page=page,
            owned=owned,
            contracts=contracts,
        ) == [
            "fixture_owned_path_projection_mismatch",
            "fixture_undeclared_counter",
        ]


def test_ux1b_pre_post_comparator_passes_exact_contract_and_rejects_mutations() -> None:
    runner = _runner()
    pretheme = _fake_ux1b_comparison_manifest(runner, "pretheme")
    posttheme = _fake_ux1b_comparison_manifest(runner, "posttheme")
    result = runner.compare_ux1b_manifests(pretheme, posttheme)
    assert result["status"] == "passed"
    assert result["comparedCaptureCount"] == 81
    assert len(result["normalizedContractSha256"]) == 64

    def reject(mutator) -> None:
        changed = copy.deepcopy(posttheme)
        mutator(changed)
        try:
            runner.compare_ux1b_manifests(pretheme, changed)
        except runner.RunnerDataError as exc:
            assert "manifest contract" in str(exc).lower()
        else:
            raise AssertionError("UX1B comparator accepted a mutated posttheme manifest")

    mutations = (
        lambda value: value["captures"].pop(),
        lambda value: value["pageIdentityCatalog"][0].__setitem__("nav_title", "漂移"),
        lambda value: value["captures"][0]["identity"].__setitem__(
            "realCallable", "wrong.render"
        ),
        lambda value: value["captures"][0]["readyMarker"].__setitem__(
            "text", "錯誤 heading"
        ),
        lambda value: value["captures"][0]["fixture"]["counts"].__setitem__(
            next(iter(value["captures"][0]["fixture"]["counts"])), 999
        ),
        lambda value: value["captures"][0]["fixtureContract"][
            "resolvedOwnedPaths"
        ].__setitem__(
            next(
                iter(
                    value["captures"][0]["fixtureContract"][
                        "resolvedOwnedPaths"
                    ]
                )
            ),
            "production/reports",
        ),
        lambda value: value["captures"][0]["fixtureContract"][
            "zeroCounters"
        ].remove("mutator.production_read.attempt"),
        lambda value: value["captures"][0]["blockedExternalRequests"].append(
            {"method": "GET", "url": "https://example.invalid/"}
        ),
        lambda value: value["captures"][0]["metrics"].__setitem__(
            "documentScrollHeight", 9999
        ),
        lambda value: value["captures"][0]["knownDebt"].__setitem__(
            "floatingAiOverlapsMain", False
        ),
        lambda value: value.__setitem__("sourceDigestEnd", "c" * 64),
    )
    for mutate in mutations:
        reject(mutate)

    layout_changed = copy.deepcopy(posttheme)
    layout_changed["captures"][0]["metrics"]["horizontalOverflow"] = True
    layout_changed["captures"][0]["knownDebt"]["pageHorizontalOverflow"] = True
    reject(lambda value: value.update(layout_changed))


def test_ux1b_pretheme_authentication_is_hash_and_namespace_bound() -> None:
    runner = _runner()
    ux1b_root = ROOT / ".claude" / "ui_snapshots" / "ux1b"
    ux1b_root.mkdir(parents=True, exist_ok=True)
    manifest = _fake_ux1b_comparison_manifest(runner, "pretheme")
    try:
        runner.load_authenticated_pretheme_manifest(
            ux1b_root / "missing-theme-contract.json"
        )
    except runner.RunnerDataError:
        pass
    else:
        raise AssertionError("pretheme authentication accepted a missing contract")
    with tempfile.TemporaryDirectory(
        prefix="pretheme-auth-unit-", dir=ux1b_root
    ) as run_dir, tempfile.TemporaryDirectory() as contract_dir:
        manifest_path = Path(run_dir) / "manifest.json"
        manifest_bytes = (
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        manifest_path.write_bytes(manifest_bytes)
        relative = manifest_path.relative_to(ROOT).as_posix()
        digest = hashlib.sha256(manifest_bytes).hexdigest()
        contract_path = Path(contract_dir) / "theme-contract.json"

        def write_contract(path: str, sha256: str) -> None:
            contract_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "prethemeManifest": {"path": path, "sha256": sha256},
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

        write_contract(relative, digest)
        authenticated = runner.load_authenticated_pretheme_manifest(contract_path)
        assert authenticated.manifest_sha256 == digest
        assert authenticated.manifest["phase"] == "pretheme"

        for path, sha256 in (
            (relative, "0" * 64),
            ("Makefile", hashlib.sha256((ROOT / "Makefile").read_bytes()).hexdigest()),
            ("../manifest.json", digest),
        ):
            write_contract(path, sha256)
            try:
                runner.load_authenticated_pretheme_manifest(contract_path)
            except runner.RunnerDataError:
                pass
            else:
                raise AssertionError("pretheme authentication accepted a bad reference")

        contract_path.write_text("{half-written", encoding="utf-8")
        try:
            runner.load_authenticated_pretheme_manifest(contract_path)
        except runner.RunnerDataError:
            pass
        else:
            raise AssertionError("pretheme authentication accepted malformed JSON")

        manifest["phase"] = "posttheme"
        mutated_bytes = json.dumps(manifest, sort_keys=True).encode("utf-8")
        manifest_path.write_bytes(mutated_bytes)
        write_contract(relative, hashlib.sha256(mutated_bytes).hexdigest())
        try:
            runner.load_authenticated_pretheme_manifest(contract_path)
        except runner.RunnerDataError:
            pass
        else:
            raise AssertionError("pretheme authentication accepted the wrong phase")


def test_ux1b_fixture_metadata_and_child_calls_are_profile_specific() -> None:
    runner = _runner()
    fixtures = importlib.import_module("ui_ux_fixtures")
    metadata = runner.load_ux1b_fixture_contracts()
    assert metadata["counterSchemaVersion"] == 1
    assert metadata["contractSchemaVersion"] == 1
    assert metadata["fixtureRevision"] == "quant-radar-ux1b-2026-07-16.1"
    assert metadata["legacyFixtureRevision"] == "quant-radar-ux0-2026-07-16.2"

    ux1b_calls = {
        "schemaVersion": 1,
        "contractSchema": 1,
        "fixtureRevision": "quant-radar-ux1b-2026-07-16.1",
        "captures": {},
        "bootstrapBlockedNetwork": [],
    }
    validated = runner.validate_fixture_calls_contract(
        ux1b_calls,
        profile="ux1b-full-pages",
        fixture_contracts=metadata,
    )
    assert validated == {
        "fixtureRevision": "quant-radar-ux1b-2026-07-16.1",
        "contractSchema": 1,
    }
    invalid_calls = (
        {key: value for key, value in ux1b_calls.items() if key != "contractSchema"},
        {**ux1b_calls, "contractSchema": 2},
        {**ux1b_calls, "fixtureRevision": "quant-radar-ux0-2026-07-16.2"},
        {**ux1b_calls, "schemaVersion": 2},
    )
    for child_calls in invalid_calls:
        try:
            runner.validate_fixture_calls_contract(
                child_calls,
                profile="ux1b-full-pages",
                fixture_contracts=metadata,
            )
        except runner.RunnerDataError:
            pass
        else:
            raise AssertionError(f"runner accepted incompatible UX1B calls: {child_calls}")

    legacy_calls = {
        "schemaVersion": 1,
        "fixtureRevision": "quant-radar-ux0-2026-07-16.2",
        "captures": {},
        "bootstrapBlockedNetwork": [],
    }
    assert runner.validate_fixture_calls_contract(
        legacy_calls,
        profile=None,
        fixture_contracts=None,
    ) == {
        "fixtureRevision": "quant-radar-ux0-2026-07-16.2",
        "contractSchema": None,
    }

    mutations = (
        ("UX1B_FIXTURE_REVISION", fixtures.FIXTURE_REVISION),
        ("UX1B_FIXTURE_REVISION", None),
        ("UX1B_CONTRACT_SCHEMA_VERSION", 2),
        ("UX1B_CONTRACT_SCHEMA_VERSION", True),
        ("UX1B_CONTRACT_SCHEMA_VERSION", None),
    )
    for attribute, value in mutations:
        with patch.object(fixtures, attribute, value):
            try:
                runner.load_ux1b_fixture_contracts()
            except runner.RunnerDataError as exc:
                assert "ux1b fixture" in str(exc).lower()
            else:
                raise AssertionError(
                    f"runner accepted mutated fixture metadata {attribute}={value!r}"
                )


def test_ux1b_darwin_sandbox_contract_has_only_two_allowed_ports() -> None:
    runner = _runner()
    contract = runner.UX1BNetworkContract(
        streamlit_port=43111,
        deny_proxy_port=43112,
    )
    profile = runner.build_darwin_sandbox_profile(contract)
    assert profile.count("(allow network-outbound") == 2
    assert '(remote tcp "localhost:43111")' in profile
    assert '(remote tcp "localhost:43112")' in profile
    assert "8000" not in profile
    assert "network*" not in profile
    assert runner.ux1b_allowed_ports(contract) == frozenset((43111, 43112))
    if sys.platform != "darwin":
        return

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.end_headers()
            try:
                self.wfile.write(b"ok")
            except BrokenPipeError:
                pass

        def log_message(self, _fmt, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    proxy = runner.OwnedDenyProxy()
    try:
        calibration = runner.calibrate_darwin_sandbox_contract(
            runner.UX1BNetworkContract(server.server_port, proxy.port)
        )
        expected = {
            "capability": "supported",
            "passed": True,
            "exactPortContract": True,
            "allowedEndpointCount": 2,
            "streamlitAllowed": True,
            "denyProxyAllowed": True,
            "dummyLoopbackDenied": True,
            "api8000Denied": True,
            "testNetDenied": True,
            "dummyListenerBytes": 0,
        }
        assert {key: calibration.get(key) for key in expected} == expected
        assert all(
            isinstance(calibration.get(key), int) and calibration[key] > 0
            for key in (
                "dummyLoopbackErrno",
                "api8000Errno",
                "testNetErrno",
            )
        )
    finally:
        proxy.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=1.0)


def test_viewport_and_page_normalization() -> None:
    runner = _runner()
    assert runner.parse_viewport("desktop") == ("desktop", 1440, 900)
    assert runner.parse_viewport("421x777") == ("421x777", 421, 777)
    assert runner.route_for_page("") == "/"
    assert runner.route_for_page("today-decision") == "/"
    assert runner.route_for_page("/trade-state") == "/trade-state"
    for bad in ("0x900", "390x0", "390", "../../etc"):
        try:
            runner.parse_viewport(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted invalid viewport: {bad}")


def test_focused_cases_are_separate_from_routes_and_have_exact_matrix_sizes() -> None:
    runner = _runner()
    parser = runner.build_parser()
    focused_argv = [item for name in runner.FOCUSED_CASES for item in ("--case", name)]
    focused_argv += [
        "--viewport", "desktop",
        "--viewport", "tablet",
        "--viewport", "mobile",
        "--viewport", "320x844",
    ]
    focused_args = parser.parse_args(focused_argv)
    assert focused_args.profile is None and focused_args.phase is None
    cases, viewports = runner._prepare_args(focused_args)
    assert tuple(item.name for item in cases) == runner.FOCUSED_CASES
    assert len(cases) * len(viewports) == 20
    assert runner.normalize_case("ai-chat-open").page == "today-decision"
    assert runner.normalize_case("institution-portfolio").page == "institutions"
    assert all(item.focused for item in cases)

    default_args = parser.parse_args([])
    assert default_args.profile is None and default_args.phase is None
    default_cases, default_viewports = runner._prepare_args(default_args)
    assert tuple(item.name for item in default_cases) == runner.DEFAULT_PAGES
    assert len(default_cases) * len(default_viewports) == 21
    assert not any(item.focused for item in default_cases)

    with tempfile.TemporaryDirectory() as td:
        focused_owned = runner.create_owned_run(Path(td) / "focused")
        focused_manifest = runner._manifest_template(
            focused_owned,
            cases=cases,
            viewports=viewports,
            profile=None,
            phase=None,
        )
        assert focused_manifest["mode"] == "ux1a-focused"
        assert focused_manifest["expectedCapturesPerBrowser"] == 20
        assert "captureStackDigest" not in focused_manifest
        assert focused_manifest["cases"][1] == {
            "name": "ai-chat-open",
            "page": "today-decision",
            "route": "/",
            "component": "ai-chat-panel",
            "interaction": "open-ai-chat",
        }
        default_owned = runner.create_owned_run(Path(td) / "default")
        default_manifest = runner._manifest_template(
            default_owned,
            cases=default_cases,
            viewports=default_viewports,
            profile=None,
            phase=None,
        )
        assert default_manifest["mode"] == "ux0-pages"
        assert default_manifest["expectedCapturesPerBrowser"] == 21
        assert "captureStackDigest" not in default_manifest

    mixed = parser.parse_args(
        ["--case", "today-decision", "--page", "today-decision"]
    )
    try:
        runner._prepare_args(mixed)
    except runner.RunnerDataError as exc:
        assert "cannot be combined" in str(exc)
    else:
        raise AssertionError("runner accepted ambiguous --case plus --page")


def test_case_interactions_use_accessible_names_only() -> None:
    runner = _runner()

    class Locator:
        def __init__(self, calls, kind, value):
            self.calls = calls
            self.kind = kind
            self.value = value

        @property
        def first(self):
            return self

        def click(self, *, timeout):
            self.calls.append(("click", self.kind, self.value, timeout))

        def wait_for(self, *, state, timeout):
            self.calls.append(("wait", self.kind, self.value, state, timeout))

    class Page:
        def __init__(self):
            self.calls = []

        def get_by_role(self, role, *, name, exact):
            assert exact is True
            return Locator(self.calls, role, name)

        def get_by_text(self, text, *, exact):
            return Locator(self.calls, "text", (text, exact))

    page = Page()
    for case_name, expected_name in (
        ("ai-chat-open", "AI"),
        ("institution-portfolio", "機構持倉 · 機構 → 它持有什麼"),
    ):
        case = runner.normalize_case(case_name)
        record = runner._interaction_record(case)
        runner._perform_case_interaction(page, case, record, width=1440)
        assert record == {
            "type": case.interaction,
            "accessibleName": expected_name,
            "completed": True,
            "setupActions": [],
        }
    role_clicks = [item for item in page.calls if item[0] == "click"]
    assert [(item[1], item[2]) for item in role_clicks] == [
        ("button", "AI"),
        ("button", "機構持倉 · 機構 → 它持有什麼"),
    ]
    source = inspect.getsource(runner._perform_case_interaction)
    assert "locator(" not in source
    assert "evaluate(" not in source

    mobile_page = Page()
    mobile_case = runner.normalize_case("today-decision")
    mobile_record = runner._interaction_record(mobile_case)
    runner._perform_case_interaction(
        mobile_page, mobile_case, mobile_record, width=320
    )
    assert mobile_record["setupActions"] == [
        {
            "type": "collapse-sidebar",
            "accessibleName": "keyboard_double_arrow_left",
            "completed": True,
        }
    ]
    assert ("click", "button", "keyboard_double_arrow_left", 30_000) in mobile_page.calls


def test_loopback_url_policy_strips_external_queries() -> None:
    runner = _runner()
    for url in (
        "http://127.0.0.1:8501/",
        "http://localhost:8501/trade-state",
        "https://[::1]:8501/",
        "data:image/png;base64,AA==",
        "blob:http://127.0.0.1:8501/id",
    ):
        assert runner.is_allowed_browser_url(url), url
    assert not runner.is_allowed_browser_url("https://example.com/x?token=secret")
    assert runner.safe_url_label("https://example.com/x?token=secret") == "https://example.com/x"


def test_browser_selection_requires_chromium_by_default() -> None:
    runner = _runner()
    selected, capabilities = runner.select_browsers(
        None, {"chromium": True, "webkit": False}
    )
    assert selected == ("chromium",)
    assert capabilities == {"chromium": "supported", "webkit": "unsupported"}

    try:
        runner.select_browsers(None, {"chromium": False, "webkit": True})
    except runner.DependencyUnavailable as exc:
        assert exc.exit_code == 127
        assert "chromium" in str(exc).lower()
    else:
        raise AssertionError("default run accepted missing Chromium")

    try:
        runner.select_browsers(("webkit",), {"chromium": True, "webkit": False})
    except runner.DependencyUnavailable as exc:
        assert exc.exit_code == 127
    else:
        raise AssertionError("explicit missing WebKit was silently skipped")


def test_owned_run_paths_and_token_are_not_manifest_data() -> None:
    runner = _runner()
    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td) / "run"
        owned = runner.create_owned_run(run_dir)
        assert owned.run_dir == run_dir.resolve()
        assert owned.fixture_root.is_dir()
        assert owned.marker_path.name == ".quant-radar-ux0-owner"
        assert owned.marker_path.read_text(encoding="utf-8") == owned.run_token
        env = runner.fixture_environment(owned)
        assert env["QUANT_RADAR_UX0_RUN_TOKEN"] == owned.run_token
        public = runner.public_run_metadata(owned)
        assert owned.run_token not in json.dumps(public)
        assert "runToken" not in public
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-sensitive-sentinel",
                "DATABASE_URL": "postgres://user:password@example.invalid/private",
                "HTTP_PROXY": "http://user:password@example.invalid:8080",
            },
            clear=False,
        ):
            scrubbed = runner.fixture_environment(owned)
        assert "OPENAI_API_KEY" not in scrubbed
        assert "DATABASE_URL" not in scrubbed
        assert "HTTP_PROXY" not in scrubbed
        assert scrubbed["HOME"] == str(owned.fixture_root)

    with tempfile.TemporaryDirectory(dir=ROOT / "ui") as td:
        try:
            runner.create_owned_run(Path(td) / "capture")
        except runner.RunnerDataError:
            pass
        else:
            raise AssertionError("runner accepted a production source directory as owned output")


def test_atomic_manifest_and_sanitized_diagnostics() -> None:
    runner = _runner()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        token = "top-secret-run-token"
        payload = {
            "schemaVersion": 1,
            "status": "partial",
            "message": f"{root}/private.py token={token}",
        }
        sanitized = runner.sanitize_value(payload, workspace=ROOT, run_dir=root, secrets=(token,))
        encoded = json.dumps(sanitized)
        assert token not in encoded
        assert str(root) not in encoded
        target = root / "manifest.json"
        runner.atomic_write_json(target, sanitized)
        assert json.loads(target.read_text(encoding="utf-8")) == sanitized
        assert not list(root.glob("*.tmp"))
        credential_text = (
            "OPENAI_API_KEY=sk-sensitive-sentinel "
            "Authorization: Bearer abcdefghijklmnop "
            "jwt=eyJabcdefghi.eyJabcdefgh.abcdefghijk "
            "DATABASE_URL=postgres://dbuser:dbpass@example.invalid/private "
            "remote=https://urluser:urlpass@example.invalid/private "
            "trace=/Volumes/Private/build/source.py"
        )
        redacted = runner.sanitize_text(
            credential_text, workspace=ROOT, run_dir=root
        )
        assert "sk-sensitive" not in redacted
        assert "abcdefghijklmnop" not in redacted
        assert "eyJabcdefghi" not in redacted
        assert "dbuser" not in redacted
        assert "dbpass" not in redacted
        assert "urluser" not in redacted
        assert "urlpass" not in redacted
        assert "/Volumes/Private" not in redacted

        log_path = root / "owned.log"
        process = runner.start_owned_process(
            [sys.executable, "-c", "print('ok')"],
            env=None,
            log_path=log_path,
        )
        process.wait(timeout=5)
        runner.stop_owned_process(process)
        assert stat.S_IMODE(log_path.stat().st_mode) == 0o600


def test_web_socket_guard_allows_loopback_and_blocks_external() -> None:
    runner = _runner()

    class FakeWebSocket:
        def __init__(self, url: str) -> None:
            self.url = url
            self.connected = False
            self.closed: tuple[int | None, str | None] | None = None

        def connect_to_server(self) -> None:
            self.connected = True

        def close(self, *, code=None, reason=None) -> None:
            self.closed = (code, reason)

    blocked: list[dict[str, str]] = []
    local = FakeWebSocket("ws://127.0.0.1:8501/_stcore/stream")
    runner.handle_browser_web_socket(local, blocked)
    assert local.connected is True
    assert local.closed is None

    external = FakeWebSocket("wss://example.invalid/socket?token=secret")
    runner.handle_browser_web_socket(external, blocked)
    assert external.connected is False
    assert external.closed is None
    assert blocked == [
        {"method": "WEBSOCKET", "url": "wss://example.invalid/socket"}
    ]
    capture_source = inspect.getsource(runner._capture_one)
    assert 'service_workers="block"' in capture_source
    assert 'route_web_socket("**/*"' not in capture_source  # registration is callable-guarded
    assert 'route_web_socket(' in capture_source


def test_real_chromium_web_socket_block_is_bounded_and_makes_no_contact() -> None:
    runner = _runner()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(0.2)
    port = listener.getsockname()[1]
    blocked: list[dict[str, str]] = []
    try:
        with sync_playwright() as playwright:
            if not Path(playwright.chromium.executable_path).is_file():
                return
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(service_workers="block")
            # Deliberately apply the external-block branch to a loopback test
            # listener so zero server contact is directly observable.
            context.route_web_socket(
                "**/*",
                lambda web_socket: runner.block_browser_web_socket(
                    web_socket, blocked
                ),
            )
            page = context.new_page()
            page.set_content(
                "<script>window.blockedSocket = new WebSocket("
                f"'ws://127.0.0.1:{port}/must-not-connect');</script>",
                timeout=5_000,
            )
            page.wait_for_timeout(100)
            assert blocked == [
                {
                    "method": "WEBSOCKET",
                    "url": f"ws://127.0.0.1:{port}/must-not-connect",
                }
            ]
            context.close()
            browser.close()
        try:
            connection, _address = listener.accept()
        except socket.timeout:
            pass
        else:
            connection.close()
            raise AssertionError("blocked WebSocket contacted its server")
    finally:
        listener.close()


def test_changing_capture_counter_fails_quiescence() -> None:
    runner = _runner()
    original_read_calls = runner._read_calls
    counter = 0

    def changing(_path):
        nonlocal counter
        counter += 1
        return {
            "captures": {
                "changing": {
                    "counts": {"tick": counter},
                    "blockedNetwork": [],
                }
            }
        }

    runner._read_calls = changing
    try:
        try:
            runner.wait_for_capture_quiescence(
                Path("unused"), "changing", timeout=0.01
            )
        except runner.CaptureNotQuiescent as exc:
            assert exc.latest["counts"]["tick"] >= 1
        else:
            raise AssertionError("changing counter was accepted as quiescent")
    finally:
        runner._read_calls = original_read_calls


def test_streamlit_start_cleans_interrupt_and_retries_bind_race() -> None:
    runner = _runner()

    class FakeProcess:
        pass

    originals = {
        "choose_ephemeral_port": runner.choose_ephemeral_port,
        "start_owned_process": runner.start_owned_process,
        "stop_owned_process": runner.stop_owned_process,
        "wait_for_health": runner.wait_for_health,
        "_log_tail": runner._log_tail,
    }
    try:
        with tempfile.TemporaryDirectory() as td:
            owned = runner.create_owned_run(Path(td) / "interrupt")
            process = FakeProcess()
            stopped: list[FakeProcess] = []
            runner.choose_ephemeral_port = lambda: 43111
            runner.start_owned_process = lambda *args, **kwargs: process
            runner.stop_owned_process = lambda item, **kwargs: stopped.append(item)

            def interrupt_wait(*_args, **_kwargs):
                raise runner.RunnerInterrupted()

            runner.wait_for_health = interrupt_wait
            try:
                runner._start_streamlit(owned, attempts=1)
            except runner.RunnerInterrupted:
                pass
            else:
                raise AssertionError("startup interrupt was swallowed")
            assert stopped == [process]

        with tempfile.TemporaryDirectory() as td:
            owned = runner.create_owned_run(Path(td) / "bind-race")
            first, second = FakeProcess(), FakeProcess()
            processes = iter((first, second))
            ports = iter((43112, 43113))
            stopped = []
            waits = 0
            runner.choose_ephemeral_port = lambda: next(ports)
            runner.start_owned_process = lambda *args, **kwargs: next(processes)
            runner.stop_owned_process = lambda item, **kwargs: stopped.append(item)
            runner._log_tail = lambda _path: "Address already in use"

            def bind_wait(_port, _process, **_kwargs):
                nonlocal waits
                waits += 1
                if waits == 1:
                    raise runner.ServerExited(1)
                return True

            runner.wait_for_health = bind_wait
            selected_process, selected_port = runner._start_streamlit(owned, attempts=2)
            assert selected_process is second
            assert selected_port == 43113
            assert stopped == [first]
    finally:
        for name, value in originals.items():
            setattr(runner, name, value)


def test_matrix_cleans_owned_process_on_success_render_failure_and_interrupt() -> None:
    runner = _runner()

    class FakeBrowser:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    class FakeBrowserType:
        def __init__(self, executable_path: str) -> None:
            self.executable_path = executable_path
            self.instances: list[FakeBrowser] = []

        def launch(self, **_kwargs):
            browser = FakeBrowser()
            self.instances.append(browser)
            return browser

    class FakeManager:
        def __init__(self, playwright) -> None:
            self.playwright = playwright

        def __enter__(self):
            return self.playwright

        def __exit__(self, *_args):
            return False

    class FakeProcess:
        pass

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        chromium = FakeBrowserType(sys.executable)
        webkit = FakeBrowserType(str(root / "missing-webkit"))
        fake_playwright = types.SimpleNamespace(chromium=chromium, webkit=webkit)
        sync_module = types.ModuleType("playwright.sync_api")
        sync_module.sync_playwright = lambda: FakeManager(fake_playwright)

        sentinel = object()
        previous_sync_module = sys.modules.get("playwright.sync_api", sentinel)
        originals = {
            "_start_streamlit": runner._start_streamlit,
            "stop_owned_process": runner.stop_owned_process,
            "_capture_one": runner._capture_one,
            "_read_calls": runner._read_calls,
            "_discard_run_success_authority": runner._discard_run_success_authority,
        }
        original_signal = runner.signal.signal
        original_replace = runner.os.replace
        stopped: list[FakeProcess] = []
        process = FakeProcess()
        runner._start_streamlit = lambda _owned: (process, 43114)
        runner.stop_owned_process = lambda item, **_kwargs: stopped.append(item)
        runner._read_calls = lambda _path: {
            "schemaVersion": 1,
            "fixtureRevision": "unit-fixture-v1",
            "bootstrapBlockedNetwork": [],
        }
        sys.modules["playwright.sync_api"] = sync_module

        def args_for(name: str):
            return runner.build_parser().parse_args(
                [
                    "--out-dir",
                    str(root / name),
                    "--browser",
                    "chromium",
                    "--page",
                    "today-decision",
                    "--viewport",
                    "desktop",
                    "--quiet",
                ]
            )

        try:
            runner._capture_one = lambda *_args, **_kwargs: {
                "status": "passed",
                "failureReasons": [],
            }
            code, manifest = runner.run_matrix(args_for("success"))
            assert code == 0
            assert manifest["status"] == "passed"
            assert stopped == [process]
            assert chromium.instances[-1].closed is True

            diagnostic_secret = "sk-supersecret123"

            def render_failure(*_args, **_kwargs):
                raise RuntimeError(
                    f"{root}/private.json token={diagnostic_secret} "
                    + ("x" * 5_000)
                )

            runner._capture_one = render_failure
            code, manifest = runner.run_matrix(args_for("render-failure"))
            assert code == 1
            assert manifest["status"] == "failed"
            assert manifest["error"]["type"] == "RuntimeError"
            assert stopped == [process, process]
            persisted = json.loads(
                (root / "render-failure" / "manifest.json").read_text(encoding="utf-8")
            )
            assert persisted["status"] == "failed"
            assert diagnostic_secret not in json.dumps(persisted)
            assert str(root) not in json.dumps(persisted)
            assert (
                len(persisted["error"]["message"])
                <= runner.MAX_DIAGNOSTIC_MESSAGE_CHARS
            )

            def interrupted(*_args, **_kwargs):
                raise runner.RunnerInterrupted()

            runner._capture_one = interrupted
            code, manifest = runner.run_matrix(args_for("interrupted"))
            assert code == 130
            assert manifest["status"] == "interrupted"
            assert stopped == [process, process, process]
            persisted = json.loads(
                (root / "interrupted" / "manifest.json").read_text(encoding="utf-8")
            )
            assert persisted["status"] == "interrupted"

            runner._capture_one = lambda *_args, **_kwargs: {
                "status": "passed",
                "failureReasons": [],
            }
            discard_calls = 0

            def interrupted_discard(authority):
                nonlocal discard_calls
                discard_calls += 1
                originals["_discard_run_success_authority"](authority)
                if discard_calls == 1:
                    raise runner.RunnerInterrupted("late capability cleanup")

            runner._discard_run_success_authority = interrupted_discard
            prior_sigint = signal.getsignal(signal.SIGINT)
            prior_sigterm = signal.getsignal(signal.SIGTERM)
            prior_signal_mask = signal.pthread_sigmask(signal.SIG_BLOCK, ())
            code, manifest = runner.run_matrix(args_for("late-cleanup-interrupt"))
            persisted = json.loads(
                (root / "late-cleanup-interrupt" / "manifest.json").read_text()
            )
            assert code == 130
            assert manifest["status"] == "interrupted"
            assert persisted["status"] == "interrupted"
            assert discard_calls == 2
            assert signal.getsignal(signal.SIGINT) == prior_sigint
            assert signal.getsignal(signal.SIGTERM) == prior_sigterm
            assert runner._RUN_SUCCESS_AUTHORITIES == {}
            assert runner._FINALIZATION_GRANTS == {}

            runner._discard_run_success_authority = originals[
                "_discard_run_success_authority"
            ]
            signal_calls = 0

            def interrupted_signal_restore(signum, handler):
                nonlocal signal_calls
                signal_calls += 1
                if signal_calls == 3:
                    raise runner.RunnerInterrupted("late handler restoration")
                return original_signal(signum, handler)

            runner.signal.signal = interrupted_signal_restore
            try:
                code, manifest = runner.run_matrix(
                    args_for("late-handler-interrupt")
                )
            finally:
                runner.signal.signal = original_signal
            persisted = json.loads(
                (root / "late-handler-interrupt" / "manifest.json").read_text()
            )
            assert code == 130
            assert manifest["status"] == "interrupted"
            assert persisted["status"] == "interrupted"
            assert signal.getsignal(signal.SIGINT) == prior_sigint
            assert signal.getsignal(signal.SIGTERM) == prior_sigterm
            assert runner._RUN_SUCCESS_AUTHORITIES == {}
            assert runner._FINALIZATION_GRANTS == {}

            terminal_replaces = 0

            def interrupted_after_terminal_replace(source, destination):
                nonlocal terminal_replaces
                try:
                    pending = json.loads(Path(source).read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError):
                    pending = {}
                if pending.get("status") == "passed":
                    terminal_replaces += 1
                    current_mask = signal.pthread_sigmask(signal.SIG_BLOCK, ())
                    assert signal.SIGINT in current_mask
                    assert signal.SIGTERM in current_mask
                    assert signal.getsignal(signal.SIGINT) == prior_sigint
                    assert signal.getsignal(signal.SIGTERM) == prior_sigterm
                    assert runner._RUN_SUCCESS_AUTHORITIES == {}
                    assert runner._FINALIZATION_GRANTS == {}
                original_replace(source, destination)
                if pending.get("status") == "passed":
                    raise runner.RunnerInterrupted("after terminal replace")

            runner.os.replace = interrupted_after_terminal_replace
            try:
                code, manifest = runner.run_matrix(
                    args_for("replace-after-interrupt")
                )
            finally:
                runner.os.replace = original_replace
            persisted = json.loads(
                (root / "replace-after-interrupt" / "manifest.json").read_text()
            )
            assert code == 0
            assert manifest["status"] == "passed"
            assert persisted["status"] == "passed"
            assert terminal_replaces == 1
            assert signal.getsignal(signal.SIGINT) == prior_sigint
            assert signal.getsignal(signal.SIGTERM) == prior_sigterm
            assert signal.pthread_sigmask(signal.SIG_BLOCK, ()) == prior_signal_mask
            assert runner._RUN_SUCCESS_AUTHORITIES == {}
            assert runner._FINALIZATION_GRANTS == {}
        finally:
            runner.os.replace = original_replace
            runner.signal.signal = original_signal
            for name, value in originals.items():
                setattr(runner, name, value)
            if previous_sync_module is sentinel:
                sys.modules.pop("playwright.sync_api", None)
            else:
                sys.modules["playwright.sync_api"] = previous_sync_module


def test_ux1b_formal_contract_failure_is_terminal_and_never_legacy() -> None:
    runner = _runner()
    original_authenticate = runner._authenticate_ux1b_capture_stack_contract
    original_start = runner._start_streamlit
    snapshot_root = ROOT / ".claude" / "ui_snapshots" / "ux1b"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    direct_start_called = False

    def rejected_contract(*, workspace_fd=None):
        assert isinstance(workspace_fd, int) and workspace_fd >= 0
        raise runner.RunnerDataError("capture-stack contract unavailable")

    def forbidden_direct_start(*_args, **_kwargs):
        nonlocal direct_start_called
        direct_start_called = True
        raise AssertionError("formal UX1B reached the legacy direct app launch")

    try:
        runner._authenticate_ux1b_capture_stack_contract = rejected_contract
        runner._start_streamlit = forbidden_direct_start
        with tempfile.TemporaryDirectory(dir=snapshot_root) as td:
            args = runner.build_parser().parse_args(
                [
                    "--profile",
                    "ux1b-full-pages",
                    "--phase",
                    "pretheme",
                    "--browser",
                    "chromium",
                    "--out-dir",
                    td,
                    "--no-prompt",
                    "--json",
                ]
            )
            code, manifest = runner.run_matrix(args)
            persisted = json.loads((Path(td) / "manifest.json").read_text())
        assert code == 3
        assert manifest["status"] == "invalid_data"
        assert persisted["status"] == "invalid_data"
        assert direct_start_called is False
    finally:
        runner._authenticate_ux1b_capture_stack_contract = original_authenticate
        runner._start_streamlit = original_start


def test_ux1b_stale_recovery_uses_lease_and_public_idempotent_record() -> None:
    runner = _runner()
    evidence = runner._evidence_api()
    isolation = runner._isolation_api()
    prefix = "quant-radar-ux1b-"

    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        temp_parent = base / "tmp"
        recovery = base / "recovery"
        temp_parent.mkdir(mode=0o700)
        recovery.mkdir(mode=0o700)
        recovery_fd = os.open(
            recovery,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        with patch.object(isolation.secrets, "token_hex", return_value="a" * 32):
            runtime = isolation.create_owned_run_root(
                temp_parent,
                prefix=prefix,
            )
        lease = isolation.acquire_owned_run_lease(runtime)
        final = runtime.path / "final"
        final.mkdir(mode=0o700)
        final_fd = os.open(final, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        lifecycle = evidence.ManifestLifecycle(
            final_fd,
            "manifest.json",
            base_document={
                "schemaVersion": evidence.EVIDENCE_SCHEMA,
                "mode": runner.UX1B_PROFILE,
                "phase": "precontrol",
                "runId": "ux1b-" + "1" * 24,
                "fixtureEntrypoint": runner.UX1B_FIXTURE_ENTRYPOINTS[
                    runner.UX1B_PROFILE
                ],
                "expectedCaptureCount": 81,
            },
        )
        lifecycle.start()
        os.close(final_fd)
        del lifecycle
        manifest = final / "manifest.json"
        before_raw = manifest.read_bytes()
        before_stat = manifest.stat(follow_symlinks=False)

        try:
            assert runner._recover_stale_ux1b_formal_runtimes(
                evidence,
                isolation,
                temp_parent=temp_parent,
                recovery_dir_fd=recovery_fd,
            ) == ()
            assert list(recovery.iterdir()) == []

            lease.close()  # Simulated SIGKILL/host-loss lease release.
            first = runner._recover_stale_ux1b_formal_runtimes(
                evidence,
                isolation,
                temp_parent=temp_parent,
                recovery_dir_fd=recovery_fd,
            )
            second = runner._recover_stale_ux1b_formal_runtimes(
                evidence,
                isolation,
                temp_parent=temp_parent,
                recovery_dir_fd=recovery_fd,
            )
            assert len(first) == len(second) == 1
            assert first == second
            assert first[0]["status"] == "stale_nonterminal"
            assert first[0]["sourceStatus"] == "running"
            assert first[0]["referenceable"] is False
            records = list(recovery.iterdir())
            assert [path.name for path in records] == [
                f"stale-{runtime.leaf_name}.json"
            ]
            assert json.loads(records[0].read_text(encoding="utf-8")) == first[0]

            after_stat = manifest.stat(follow_symlinks=False)
            assert manifest.read_bytes() == before_raw
            assert (
                after_stat.st_dev,
                after_stat.st_ino,
                after_stat.st_uid,
                stat.S_IMODE(after_stat.st_mode),
                after_stat.st_nlink,
                after_stat.st_size,
                after_stat.st_mtime_ns,
            ) == (
                before_stat.st_dev,
                before_stat.st_ino,
                before_stat.st_uid,
                stat.S_IMODE(before_stat.st_mode),
                before_stat.st_nlink,
                before_stat.st_size,
                before_stat.st_mtime_ns,
            )
        finally:
            os.close(recovery_fd)
            isolation.remove_owned_run_root(runtime)


def test_ux1b_stale_final_open_skips_candidate_races_but_not_io_failure() -> None:
    runner = _runner()
    with tempfile.TemporaryDirectory() as raw:
        descriptor = os.open(raw, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        claim = types.SimpleNamespace(
            root=types.SimpleNamespace(descriptor=descriptor)
        )
        try:
            with patch.object(
                runner.os,
                "stat",
                side_effect=FileNotFoundError(runner.errno.ENOENT, "gone"),
            ):
                assert runner._open_ux1b_stale_final_root(claim) is None
            with patch.object(
                runner.os,
                "stat",
                side_effect=OSError(runner.errno.EIO, "io failure"),
            ):
                try:
                    runner._open_ux1b_stale_final_root(claim)
                except runner.RunnerDataError as exc:
                    assert "could not be authenticated" in str(exc)
                else:
                    raise AssertionError("stale scan hid a coordinator I/O failure")
        finally:
            os.close(descriptor)


def test_ux1b_lifecycle_start_uncertainty_is_terminal_and_cleans_runtime() -> None:
    runner = _runner()
    evidence = runner._evidence_api()
    isolation = runner._isolation_api()
    original_lifecycle = evidence.ManifestLifecycle
    original_remove = isolation.remove_owned_run_root
    removed = []

    class StartUncertainLifecycle:
        def __init__(self, *args, **kwargs):
            self.inner = original_lifecycle(*args, **kwargs)

        @property
        def state(self):
            return self.inner.state

        def start(self):
            self.inner.start()
            raise evidence.ManifestDurabilityUncertain("start fsync uncertain")

        def __getattr__(self, name):
            return getattr(self.inner, name)

    def tracked_remove(runtime):
        removed.append(runtime.path)
        return original_remove(runtime)

    snapshot_root = ROOT / ".claude" / "ui_snapshots" / "ux1b"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    try:
        evidence.ManifestLifecycle = StartUncertainLifecycle
        isolation.remove_owned_run_root = tracked_remove
        with tempfile.TemporaryDirectory(dir=snapshot_root) as td:
            args = runner.build_parser().parse_args(
                [
                    "--profile",
                    "ux1b-full-pages",
                    "--phase",
                    "pretheme",
                    "--browser",
                    "chromium",
                    "--out-dir",
                    td,
                    "--no-prompt",
                    "--json",
                ]
            )
            code, manifest = runner.run_matrix(args)
            persisted = json.loads((Path(td) / "manifest.json").read_text())
        assert code == 1
        assert manifest == persisted
        assert persisted["status"] == "failed"
        assert len(removed) == 1
        assert not removed[0].exists()
    finally:
        evidence.ManifestLifecycle = original_lifecycle
        isolation.remove_owned_run_root = original_remove


def test_ux1b_formal_success_orders_export_before_final_pass_write() -> None:
    runner = _runner()
    source = inspect.getsource(runner._run_ux1b_recovery)
    verify_index = source.index("evidence.verify_capture_artifacts")
    opaque_append_index = source.index("verified_captures.append", verify_index)
    payload_append_index = source.index(
        "partial_artifact_payloads.append", opaque_append_index
    )
    comparator_index = source.index("evidence.validate_live_capture_profile")
    assert (
        verify_index
        < opaque_append_index
        < payload_append_index
        < comparator_index
    )
    assert "copy.deepcopy(dict(verified))" in source[
        opaque_append_index:comparator_index
    ]
    assert "verified_captures," in source[comparator_index:]
    success = source[source.index("grant = evidence.authorize_success_closure") :]
    success = success[: success.index("    except BaseException as exc:")]
    materializer_index = success.index(
        "evidence.materialize_authorized_terminal_manifest"
    )
    export_index = success.index("publication = _export_ux1b_evidence")
    finalizer_index = success.index("evidence.finalize_terminal_manifest")
    authenticate_index = success.index("_authenticate_ux1b_passed_bundle")
    assert materializer_index < export_index < finalizer_index < authenticate_index
    assert "dict(closure)" not in success
    assert "lifecycle.mark_terminal" not in success
    assert "os.rename" not in success[finalizer_index:]
    failure = source[
        source.index("    except BaseException as exc:", comparator_index) :
    ]
    assert "partial_artifact_payloads=partial_artifact_payloads" in failure


def test_ux1b_partial_failure_terminalization_keeps_verified_artifacts() -> None:
    runner = _runner()
    evidence = runner._evidence_api()
    isolation = runner._isolation_api()
    observed = {}

    class Lifecycle:
        state = "running"

        def mark_terminal(self, status, updates):
            observed["status"] = status
            observed["updates"] = updates
            self.state = status
            return {"status": status, **updates}

    partial = [{"png": {"path": "captures/one.png"}}]
    expected_partial = copy.deepcopy(partial)
    code, manifest = runner._terminalize_ux1b_failure(
        evidence,
        isolation,
        Lifecycle(),
        runner.RunnerDataError("partial capture failed"),
        cleanup_error=RuntimeError("family cleanup failed"),
        partial_artifact_payloads=partial,
        private_roots=(),
        final_root_fd=-1,
    )
    assert code == 3
    assert manifest["status"] == "invalid_data"
    partial[0]["png"]["path"] = "mutated-after-terminalization.png"
    assert observed["updates"]["partialArtifacts"] == expected_partial
    assert observed["updates"]["error"]["type"] == "RuntimeError"


def test_ux1b_durability_retry_is_bounded() -> None:
    runner = _runner()
    original_fsync = runner.os.fsync
    calls = 0

    def always_fail(_descriptor):
        nonlocal calls
        calls += 1
        raise OSError("persistent fsync failure")

    try:
        runner.os.fsync = always_fail
        assert runner._retry_ux1b_directory_fsync(123, attempts=3) is False
        assert calls == 3
    finally:
        runner.os.fsync = original_fsync
def test_ephemeral_port_does_not_reclaim_unowned_listener() -> None:
    runner = _runner()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    occupied = listener.getsockname()[1]
    try:
        candidate = runner.choose_ephemeral_port()
        assert candidate != occupied
        listener.settimeout(0.05)
        assert listener.getsockname()[1] == occupied
    finally:
        listener.close()


def test_health_wait_is_bounded_and_checks_child_exit() -> None:
    runner = _runner()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/_stcore/health":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, _fmt, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    class Alive:
        @staticmethod
        def poll():
            return None

    try:
        assert runner.wait_for_health(server.server_port, Alive(), timeout=1.0)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)

    class Exited:
        @staticmethod
        def poll():
            return 9

    try:
        runner.wait_for_health(server.server_port, Exited(), timeout=0.2)
    except runner.ServerExited as exc:
        assert exc.returncode == 9
    else:
        raise AssertionError("child exit was ignored")


def test_ux1b_selection_streamlit_base_path_is_exact_and_health_uses_it() -> None:
    runner = _runner()
    full_entrypoint = runner.UX1B_FIXTURE_ENTRYPOINTS[runner.UX1B_PROFILE]
    selection_entrypoint = runner.UX1B_FIXTURE_ENTRYPOINTS[
        runner.UX1B_SELECTION_PROFILE
    ]

    assert runner._ux1b_streamlit_base_path(full_entrypoint) == ""
    assert (
        runner._ux1b_streamlit_base_path(selection_entrypoint)
        == "__selection__"
    )
    try:
        runner._ux1b_streamlit_base_path("scripts/not-an-owned-fixture.py")
    except runner.RunnerDataError:
        pass
    else:
        raise AssertionError("unknown fixture entrypoint received a base path")

    class Alive:
        @staticmethod
        def poll():
            return None

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, _type, _value, _traceback):
            return False

    requested: list[tuple[str, float]] = []

    def urlopen(url: str, *, timeout: float):
        requested.append((url, timeout))
        return Response()

    with patch.object(runner.urllib.request, "urlopen", side_effect=urlopen):
        assert runner.wait_for_health(
            43123,
            Alive(),
            timeout=0.1,
            base_path="__selection__",
        )
    assert requested == [
        ("http://127.0.0.1:43123/__selection__/_stcore/health", 0.5)
    ]

    try:
        runner.wait_for_health(
            43123,
            Alive(),
            timeout=0.1,
            base_path="selection/../escape",
        )
    except runner.RunnerDataError:
        pass
    else:
        raise AssertionError("unowned Streamlit base path was accepted")

    for capture_runner in (
        runner._run_ux1b_recovery,
        runner._run_ux1b_nonterminal_capture,
    ):
        source = inspect.getsource(capture_runner)
        assert "_ux1b_streamlit_base_path" in source
        assert '"--server.baseUrlPath"' in source
        assert "base_path=streamlit_base_path" in source.replace(" ", "")


def test_owned_process_group_cleanup_leaves_unowned_process_alive() -> None:
    runner = _runner()
    command = [sys.executable, "-c", "import time; time.sleep(60)"]
    unowned = subprocess.Popen(command)
    owned = runner.start_owned_process(command, env=None, log_path=None)
    try:
        assert unowned.poll() is None
        assert owned.poll() is None
        runner.stop_owned_process(owned, timeout=1.0)
        assert owned.poll() is not None
        assert unowned.poll() is None
    finally:
        if owned.poll() is None:
            runner.stop_owned_process(owned, timeout=1.0)
        if unowned.poll() is None:
            unowned.terminate()
            unowned.wait(timeout=2)


def test_capture_result_classification_keeps_console_as_evidence() -> None:
    runner = _runner()
    evidence = {
        "headingReady": True,
        "streamlitException": False,
        "pageErrors": [],
        "blockedExternalRequests": [],
        "console": [{"type": "error", "text": "current baseline noise"}],
        "httpErrors": [
            {
                "status": 404,
                "url": "http://127.0.0.1:8501/trade-state/_stcore/health",
            }
        ],
        "metrics": {"documentClientWidth": 390, "documentScrollWidth": 420},
        "fixture": {"counts": {}, "blockedNetwork": []},
        "fixtureQuiescent": True,
    }
    assert runner.capture_failure_reasons(evidence) == []
    evidence["pageErrors"] = [{"name": "Error", "message": "boom"}]
    assert runner.capture_failure_reasons(evidence) == ["page_exception"]
    evidence["pageErrors"] = []
    evidence["fixture"] = {}
    assert runner.capture_failure_reasons(evidence) == ["missing_fixture_capture"]
    evidence["fixture"] = {"counts": {}, "blockedNetwork": []}
    evidence["fixtureQuiescent"] = False
    assert runner.capture_failure_reasons(evidence) == ["fixture_counter_not_quiescent"]

    evidence["fixtureQuiescent"] = True
    evidence["focusedCase"] = True
    evidence["interaction"] = {"completed": True}
    evidence["componentMetrics"] = {
        "present": True,
        "horizontalOverflow": False,
    }
    assert runner.capture_failure_reasons(evidence) == []
    evidence["componentMetrics"]["horizontalOverflow"] = True
    assert runner.capture_failure_reasons(evidence) == ["component_horizontal_overflow"]
    evidence["componentMetrics"]["horizontalOverflow"] = False
    evidence["interaction"]["completed"] = False
    assert runner.capture_failure_reasons(evidence) == ["case_interaction_incomplete"]
    evidence["interaction"] = {
        "completed": True,
        "setupActions": [{"completed": False}],
    }
    assert runner.capture_failure_reasons(evidence) == ["case_setup_incomplete"]


def test_worker_benign_streamlit_404_is_exact_and_same_origin() -> None:
    worker = _browser_worker()
    origin = worker._parse_exact_origin("http://127.0.0.1:8501")

    class Response:
        def __init__(self, status: int, url: str) -> None:
            self.status = status
            self.url = url
            self.request = types.SimpleNamespace(method="GET")

    classify = lambda status, url, route="/analytics-db": (  # noqa: E731
        worker._is_benign_streamlit_subroute_404(
            Response(status, url),
            origin=origin,
            route=route,
        )
    )
    assert classify(
        404,
        "http://127.0.0.1:8501/analytics-db/_stcore/host-config",
    )
    assert classify(
        404,
        "http://127.0.0.1:8501/analytics-db/_stcore/health",
    )
    assert classify(404, "http://127.0.0.1:8501/_stcore/health", route="/")

    rejected = (
        (500, "http://127.0.0.1:8501/analytics-db/_stcore/health"),
        (404, "http://127.0.0.1:8501/analytics-db/_stcore/metrics"),
        (404, "http://127.0.0.1:8502/analytics-db/_stcore/health"),
        (404, "http://localhost:8501/analytics-db/_stcore/health"),
        (404, "https://127.0.0.1:8501/analytics-db/_stcore/health"),
        (404, "http://user@127.0.0.1:8501/analytics-db/_stcore/health"),
        (404, "http://127.0.0.1:8501/analytics-db/_stcore/health?probe=1"),
        (404, "http://127.0.0.1:8501/other/_stcore/health"),
    )
    assert all(not classify(status, url) for status, url in rejected)


def test_sequence12_discovery_uses_root_semantics_not_composite_capture() -> None:
    runner = _runner()
    digest = "a" * 64
    source = "b" * 64
    full_sidecars = tuple(f"page-{index}" for index in range(21))
    root_sidecars = tuple(f"root-{index}" for index in range(44))
    logical_sidecars = tuple(
        f"logical-{index}" for index in range(36)
    )
    full_result = runner._UX1BNonterminalResult(
        base_capture_stack_digest=digest,
        source_digest=source,
        capture_ids=tuple(
            f"page-id-{index}" for index in range(21)
        ),
        sidecars=full_sidecars,
        pngs=(),
        counter_capture_ids=(),
        quiescent_process_count=22,
    )
    root_smoke = runner.UX1BRealSmoke(
        base_capture_stack_digest=digest,
        source_digest=source,
        capture_ids=tuple(
            f"root-id-{index}" for index in range(44)
        ),
        sidecars=root_sidecars,
        pngs=tuple({"captureId": f"root-id-{index}"} for index in range(44)),
        counter_capture_ids=tuple(
            f"logical-id-{index}" for index in range(36)
        ),
        quiescent_process_count=37,
    )
    evidence_api = runner._evidence_api()
    def adapt_root_sidecars(sidecars):
        if tuple(sidecars) != root_sidecars:
            raise AssertionError("unexpected root sidecars")
        return logical_sidecars

    with (
        patch.object(
            runner,
            "_run_ux1b_nonterminal_capture",
            return_value=full_result,
        ) as run_capture,
        patch.object(
            runner,
            "run_ux1b_sequence12_root_smoke",
            return_value=root_smoke,
        ) as run_root,
        patch.object(
            evidence_api,
            "adapt_root_raw_sidecars_for_control_discovery",
            side_effect=adapt_root_sidecars,
        ),
    ):
        discovery, observed_smoke = (
            runner.run_ux1b_sequence12_control_discovery_and_smoke(
                workspace_fd=123,
            )
        )
    assert discovery.sidecars == (
        *full_sidecars,
        *logical_sidecars,
    )
    assert len(discovery.sidecars) == 57
    assert observed_smoke is root_smoke
    assert run_capture.call_count == 1
    kwargs = run_capture.call_args.kwargs
    assert kwargs["label"] == "discovery"
    assert kwargs["expected_group_counts"] == {
        runner.UX1B_PROFILE: 21,
        runner.UX1B_SELECTION_PROFILE: 0,
    }
    assert "root_capture" not in kwargs
    assert all(
        row["fixtureEntrypoint"]
        == runner.UX1B_FIXTURE_ENTRYPOINTS[
            runner.UX1B_PROFILE
        ]
        for row in run_capture.call_args.args[0]
    )
    run_root.assert_called_once_with(workspace_fd=123)


def test_sequence13_stack_selection_is_distinct_and_root_bound() -> None:
    """TEST-136: seq13 is a distinct focused-postcontrol root authority."""

    runner = _runner()
    assert runner.UX1B_CAPTURE_STACK_CHOICES == (
        "legacy",
        "seq12",
        "seq13",
    )
    expected = (
        runner.WORKSPACE_ROOT
        / "docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack-seq13.json"
    )
    assert runner._ux1b_capture_stack_contract_path("seq13") == expected
    parser = runner.build_parser()
    args = parser.parse_args(
        [
            "--profile",
            runner.UX1B_SELECTION_PROFILE,
            "--phase",
            "postcontrol",
            "--capture-stack",
            "seq13",
            "--browser",
            "chromium",
            "--no-prompt",
            "--json",
        ]
    )
    cases, viewports = runner._prepare_args(args)
    assert len(cases) * len(viewports) == 36
    args.phase = "precontrol"
    try:
        runner._prepare_args(args)
    except runner.RunnerDataError as exc:
        assert "root capture stack is focused-postcontrol only" in str(exc)
    else:
        raise AssertionError("seq13 accepted a precontrol phase")
    try:
        runner.freeze_ux1b_capture_stack(
            expected_capture_stack_sha256="0" * 64,
            selection="seq13",
        )
    except runner.RunnerDataError:
        pass
    else:
        raise AssertionError("seq13 accepted rotation authority")


TESTS = [
    test_cli_contract_and_defaults,
    test_ux1b_recovery_task3_coordinator_seams_and_finalization_contract,
    test_terminal_finalization_grant_is_opaque_bound_and_one_shot,
    test_terminal_finalization_registry_transactions_are_linearizable,
    test_worker_helper_imports_and_path_normalization_outside_repo_cwd,
    test_ux1b_frozen_projection_and_ready_markers_are_exact,
    test_ux1b_cli_profile_builds_exact_chromium_81_matrix,
    test_ux1b_recovery_profiles_freeze_both_phase_matrices,
    test_ux1b_recovery_dispatch_has_no_direct_browser_launch,
    test_ux1b_control_discovery_is_exact_57_and_does_not_publish,
    test_ux1b_real_smoke_is_exact_authenticated_1_plus_9,
    test_ux1b_nonterminal_cleanup_preserves_primary_failure,
    test_freeze_ux1b_capture_stack_is_one_ordered_atomic_transaction,
    test_freeze_existing_capture_stack_rotates_in_exact_authenticated_order,
    test_freeze_discovery_smoke_and_build_failures_never_rotate,
    test_freeze_destination_close_failures_are_not_suppressed,
    test_freeze_rejects_rotation_receipt_metadata_drift,
    test_freeze_expected_sha_is_required_exactly_for_existing_canonical,
    test_ux1b_special_cli_modes_are_json_only_and_capture_arg_exclusive,
    test_ux1b_namespace_rejects_legacy_and_external_outputs,
    test_ux1b_output_namespace_rejects_writable_and_swapped_components,
    test_ux1b_capture_stack_destination_rejects_retained_parent_reparent,
    test_ux1b_formal_contract_authentication_is_workspace_fd_bound,
    test_ux1b_export_is_inode_bound_and_durability_fail_closed,
    test_ux1b_family_cleanup_ignores_poll_and_attempts_every_process,
    test_ux1b_cleanup_retries_real_child_and_retains_persistent_runtimes,
    test_ux1b_exact_port_policy_preserves_legacy_loopback_behavior,
    test_ux1b_source_digest_and_capture_identity_are_fail_closed,
    test_ux1b_pre_post_comparator_passes_exact_contract_and_rejects_mutations,
    test_ux1b_pretheme_authentication_is_hash_and_namespace_bound,
    test_ux1b_fixture_metadata_and_child_calls_are_profile_specific,
    test_ux1b_darwin_sandbox_contract_has_only_two_allowed_ports,
    test_viewport_and_page_normalization,
    test_focused_cases_are_separate_from_routes_and_have_exact_matrix_sizes,
    test_case_interactions_use_accessible_names_only,
    test_loopback_url_policy_strips_external_queries,
    test_browser_selection_requires_chromium_by_default,
    test_owned_run_paths_and_token_are_not_manifest_data,
    test_atomic_manifest_and_sanitized_diagnostics,
    test_web_socket_guard_allows_loopback_and_blocks_external,
    test_real_chromium_web_socket_block_is_bounded_and_makes_no_contact,
    test_changing_capture_counter_fails_quiescence,
    test_ephemeral_port_does_not_reclaim_unowned_listener,
    test_health_wait_is_bounded_and_checks_child_exit,
    test_ux1b_selection_streamlit_base_path_is_exact_and_health_uses_it,
    test_owned_process_group_cleanup_leaves_unowned_process_alive,
    test_streamlit_start_cleans_interrupt_and_retries_bind_race,
    test_matrix_cleans_owned_process_on_success_render_failure_and_interrupt,
    test_ux1b_formal_contract_failure_is_terminal_and_never_legacy,
    test_ux1b_stale_recovery_uses_lease_and_public_idempotent_record,
    test_ux1b_stale_final_open_skips_candidate_races_but_not_io_failure,
    test_ux1b_lifecycle_start_uncertainty_is_terminal_and_cleans_runtime,
    test_ux1b_formal_success_orders_export_before_final_pass_write,
    test_ux1b_partial_failure_terminalization_keeps_verified_artifacts,
    test_ux1b_durability_retry_is_bounded,
    test_capture_result_classification_keeps_console_as_evidence,
    test_worker_benign_streamlit_404_is_exact_and_same_origin,
    test_sequence12_discovery_uses_root_semantics_not_composite_capture,
    test_sequence13_stack_selection_is_distinct_and_root_bound,
]


def main() -> int:
    failures = 0
    for test in TESTS:
        try:
            test()
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  FAIL {test.__name__}: {type(exc).__name__}: {exc}")
        else:
            print(f"  PASS {test.__name__}")
    print(f"\n{len(TESTS) - failures}/{len(TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
