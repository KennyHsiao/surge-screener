#!/usr/bin/env python3
"""Offline runner/schema regressions for the UX-1B theme-state matrix."""

from __future__ import annotations

import ast
import contextlib
import copy
import hashlib
import io
import inspect
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import types
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import ui_ux_theme_matrix as matrix  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def raises_contract(callable_) -> None:
    try:
        callable_()
    except matrix.ThemeContractError:
        return
    raise AssertionError("theme matrix accepted an invalid contract")


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

    run_calls = {
        _call_leaf_name(node)
        for node in ast.walk(run_matrix)
        if isinstance(node, ast.Call)
    }
    if run_calls != {"_run_formal_theme_matrix"}:
        failures.append("run_matrix does not delegate only to the formal pipeline")
        return failures

    formal = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "_run_formal_theme_matrix"
        ),
        None,
    )
    if formal is None:
        failures.append("formal theme pipeline is missing")
        return failures
    finalizer_lines = [
        node.lineno
        for node in ast.walk(formal)
        if isinstance(node, ast.Call)
        and _call_leaf_name(node) == "finalize_terminal_manifest"
    ]
    if len(finalizer_lines) != 1:
        failures.append("formal theme pipeline must have exactly one success finalizer call")
        return failures
    formal_calls = {
        _call_leaf_name(node)
        for node in ast.walk(formal)
        if isinstance(node, ast.Call)
    }
    required_formal_calls = {
        "start",
        "build_source_mirror",
        "calibrate_darwin_profiles",
        "authorize_calibrated_launch",
        "spawn_calibrated_child",
        "wait_for_clean_owned_process_group_exit",
        "authenticate_counter_bundle",
        "publish_finalized_capture",
        "publish_derived_artifact",
        "verify_capture_artifacts",
        "validate_success_closure",
        "authorize_success_closure",
        "finalize_terminal_manifest",
    }
    missing = required_formal_calls - formal_calls
    if missing:
        failures.append(
            "formal theme pipeline calls differ: " + ", ".join(sorted(missing))
        )
    if "_owned_gallery_server" in formal_calls:
        failures.append("formal theme pipeline still uses the legacy gallery server")
    return failures


def test_parser_is_chromium_mandatory_and_noninteractive() -> None:
    parser = matrix.build_parser()
    args = parser.parse_args(["--browser", "chromium", "--no-prompt", "--json"])
    require(matrix._select_browsers(args.browser) == ("chromium",), "Chromium selection")
    require(matrix._select_browsers(None) == ("chromium",), "default browser")
    require(
        matrix._select_browsers(("chromium", "chromium")) == ("chromium",),
        "browser dedupe",
    )
    raises_contract(lambda: matrix._select_browsers(("webkit",)))


def test_formal_mirror_projection_and_staged_capture_schema_are_shared_exactly() -> None:
    from scripts import ui_ux_snapshot_matrix as snapshot

    projection = matrix._expanded_ux1b_source_mirror_policy()
    require(
        projection == snapshot._expanded_ux1b_source_mirror_policy(),
        "theme mirror projection differs from the authority runner",
    )
    require(
        projection == tuple(sorted(projection))
        and len(projection) == len(set(projection))
        and all((ROOT / relative).is_file() for relative in projection),
        "theme mirror projection is not an exact file set",
    )
    staged = matrix.ThemeStagedCapture(
        capture_id="theme-gallery/desktop",
        png_path="staging/theme-gallery-desktop.png",
        raw_sidecar=object(),
        raw_document={"stableState": {"diagnostics": {}}},
        rich_evidence={"sha256": "a" * 64},
        browser_proof={"quiescent": True},
    )
    require(
        staged.raw_document["stableState"]["diagnostics"] == {},
        "formal staged capture lost its raw sidecar document",
    )
    tree = ast.parse(
        Path(matrix.__file__).read_text(encoding="utf-8"),
        filename=str(matrix.__file__),
    )
    formal = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_run_formal_theme_matrix"
    )
    namespace_lines = sorted(
        node.lineno
        for node in ast.walk(formal)
        if isinstance(node, ast.Call)
        and _call_leaf_name(node) == "_reauthenticate_theme_output_namespace"
    )
    stack_lines = sorted(
        node.lineno
        for node in ast.walk(formal)
        if isinstance(node, ast.Call)
        and _call_leaf_name(node) == "_authenticate_theme_capture_stack"
    )
    require(
        len(namespace_lines) == len(stack_lines) == 2
        and all(before < authenticate for before, authenticate in zip(namespace_lines, stack_lines)),
        "capture-stack start/end auth lacks fresh namespace reauthentication",
    )

    stack_auth = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_authenticate_theme_capture_stack"
    )
    authenticate_call = next(
        node
        for node in ast.walk(stack_auth)
        if isinstance(node, ast.Call)
        and _call_leaf_name(node) == "authenticate_capture_stack_contract"
    )
    keywords = {keyword.arg: keyword.value for keyword in authenticate_call.keywords}
    require(
        "workspace_root" not in keywords
        and isinstance(keywords.get("workspace_root_fd"), ast.Name)
        and keywords["workspace_root_fd"].id == "workspace_fd",
        "theme capture-stack member authentication must use the retained workspace FD",
    )

    mirror_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _call_leaf_name(node) == "build_source_mirror"
    ]
    require(len(mirror_calls) == 2, "theme source-mirror call set differs")
    for call in mirror_calls:
        mirror_keywords = {keyword.arg: keyword.value for keyword in call.keywords}
        require(
            "workspace_root" not in mirror_keywords
            and "workspace_root_fd" in mirror_keywords,
            "theme source mirror must use a retained workspace FD",
        )


def test_persisted_audit_evidence_is_complete_and_digest_bound() -> None:
    def calibration_row(prefix: str) -> dict:
        return {
            "passed": True,
            "profileSha256": prefix * 64,
            "allowed": {"owned": True},
            "denied": {"unowned": True},
            "observations": {"unexpectedContacts": []},
            "details": {"unowned": {"errno": 1}},
        }

    calibration = {
        "schemaVersion": "quant-radar-ui-ux-ux1b-isolation-calibration/v1",
        "capability": "supported",
        "platform": "darwin",
        "passed": True,
        "profilesAreDistinct": True,
        "inheritedFdProbeExplicit": True,
        "launchIdentitySha256": "c" * 64,
        "app": calibration_row("a"),
        "browser": calibration_row("b"),
    }
    request_digests = {
        "theme-gallery/desktop": "d" * 64,
        "theme-gallery/mobile": "e" * 64,
        "theme-gallery/tablet": "f" * 64,
    }
    audit = matrix._theme_persisted_audit_evidence(
        calibration=calibration,
        worker_request_sha256=request_digests,
        app_origin="http://127.0.0.1:43121",
        app_port=43121,
        denied_port=43122,
        browser_executable_sha256="9" * 64,
    )
    report_raw = matrix._theme_canonical_ndjson(
        audit["calibration"]["report"]
    ).rstrip(b"\n")
    require(
        audit["calibration"]["sha256"]
        == hashlib.sha256(report_raw).hexdigest(),
        "persisted calibration digest is not replay-verifiable",
    )
    require(
        audit["networkAssignment"]
        == {
            "appOrigin": "http://127.0.0.1:43121",
            "appPort": 43121,
            "deniedPort": 43122,
        }
        and [row["captureId"] for row in audit["workerRequests"]]
        == sorted(request_digests),
        "persisted network/request audit closure differs",
    )
    incomplete = copy.deepcopy(calibration)
    incomplete["browser"]["observations"] = {}
    raises_contract(
        lambda: matrix._theme_persisted_audit_evidence(
            calibration=incomplete,
            worker_request_sha256=request_digests,
            app_origin="http://127.0.0.1:43121",
            app_port=43121,
            denied_port=43122,
            browser_executable_sha256="9" * 64,
        )
    )


def test_post_screenshot_geometry_is_remeasured_and_shift_closed() -> None:
    from scripts import ui_ux_browser_worker as worker

    rich = copy.deepcopy(
        _rich_theme_worker_fixture("desktop")["sidecar"]["stableState"][
            "themeEvidence"
        ]
    )
    geometry = {
        surface["name"]: copy.deepcopy(surface["geometry"])
        for surface in rich["surfaces"]
    }

    class Page:
        @staticmethod
        def evaluate(_script, arg):
            require(arg == [1440, 900], "post-screenshot full-page query differs")
            return copy.deepcopy(rich["fullPage"])

    with patch.object(
        matrix,
        "_surface_worker_crop_geometry",
        side_effect=lambda _page, surface: copy.deepcopy(geometry[surface]),
    ):
        matrix.verify_external_worker_theme_geometry_after_screenshot(Page(), rich)

    shifted = copy.deepcopy(geometry)
    shifted["panel"]["crop"]["y"] += 1
    with patch.object(
        matrix,
        "_surface_worker_crop_geometry",
        side_effect=lambda _page, surface: copy.deepcopy(shifted[surface]),
    ):
        raises_contract(
            lambda: matrix.verify_external_worker_theme_geometry_after_screenshot(
                Page(), rich
            )
        )

    request = {"case": "theme-gallery"}
    worker._verify_theme_screenshot_dimensions(
        request,
        rich,
        png_width=rich["fullPage"]["width"],
        png_height=rich["fullPage"]["height"],
    )
    for dimensions in (
        (rich["fullPage"]["width"] + 1, rich["fullPage"]["height"]),
        (rich["fullPage"]["width"], rich["fullPage"]["height"] + 1),
    ):
        try:
            worker._verify_theme_screenshot_dimensions(
                request,
                rich,
                png_width=dimensions[0],
                png_height=dimensions[1],
            )
        except worker.WorkerBootstrapError:
            pass
        else:
            raise AssertionError("theme PNG/full-page dimension mismatch passed")

    worker_source = Path(worker.__file__).read_text(encoding="utf-8")
    tree = ast.parse(worker_source, filename=str(worker.__file__))
    capture = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_capture"
    )
    screenshot_line = min(
        node.lineno
        for node in ast.walk(capture)
        if isinstance(node, ast.Call) and _call_leaf_name(node) == "screenshot"
    )
    geometry_line = min(
        node.lineno
        for node in ast.walk(capture)
        if isinstance(node, ast.Call)
        and _call_leaf_name(node) == "_verify_theme_geometry_after_screenshot"
    )
    require(
        screenshot_line < geometry_line,
        "theme geometry is not verified after the authoritative screenshot",
    )
    dimension_line = min(
        node.lineno
        for node in ast.walk(capture)
        if isinstance(node, ast.Call)
        and _call_leaf_name(node) == "_verify_theme_screenshot_dimensions"
    )
    require(
        screenshot_line < dimension_line < geometry_line,
        "theme PNG dimensions are not bound before post-screenshot geometry",
    )


def test_ux1b_recovery_task3_coordinator_seams_and_finalization_contract() -> None:
    matrix.UX1B_ROOT.mkdir(parents=True, exist_ok=True)
    run_dir = matrix.UX1B_ROOT / "theme-coordinator-contract"
    shutil.rmtree(run_dir, ignore_errors=True)
    try:
        owned = matrix.create_owned_run(run_dir)
        manifest = matrix._manifest_template(owned, ("chromium",))
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
    failures = _ux1b_task3_contract_failures(matrix, manifest)
    require(
        failures == [],
        "UX1B Task 3 theme gaps: " + "; ".join(failures),
    )


def test_terminal_finalization_grant_is_opaque_bound_and_one_shot() -> None:
    def finalizing_manifest() -> dict:
        return {
            "status": "finalizing",
            "sourceDigestStart": "a" * 64,
            "sourceDigestEnd": "a" * 64,
            "server": {
                "terminated": True,
                "denyProxyAttemptCount": 0,
                "pythonSocketGuard": {"attemptCount": 0},
            },
            "summary": {"passed": 9, "failed": 0, "total": 9},
            "expectedCaptureTotal": 9,
            "blockedNetwork": [],
            "exceptions": [],
        }

    def assert_type_error(callable_) -> None:
        try:
            callable_()
        except TypeError:
            return
        raise AssertionError("opaque finalization grant operation unexpectedly succeeded")

    assert_type_error(lambda: matrix._RunnerFinalizationGrant())
    assert_type_error(lambda: matrix._RunSuccessAuthority())
    forged_grant = object.__new__(matrix._RunnerFinalizationGrant)
    matrix.UX1B_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=matrix.UX1B_ROOT) as td:
        persisted = Path(td) / "manifest.json"
        authority_index = 0

        def register_test_run_authority(manifest: dict):
            nonlocal authority_index
            authority_index += 1
            owned = matrix.create_owned_run(
                Path(td) / f"grant-run-{authority_index}"
            )
            authority = object.__new__(matrix._RunSuccessAuthority)
            with matrix._FINALIZATION_GRANTS_LOCK:
                matrix._RUN_SUCCESS_AUTHORITIES[id(authority)] = (
                    authority,
                    os.getpid(),
                    manifest,
                    owned,
                    matrix._owned_run_binding(owned),
                )
            return authority

        forged_manifest = finalizing_manifest()
        forged_authority = object.__new__(matrix._RunSuccessAuthority)
        raises_contract(
            lambda: matrix._authorize_terminal_manifest(
                forged_manifest, authority=forged_authority
            )
        )
        try:
            matrix._authorize_terminal_manifest(forged_manifest)
        except TypeError:
            pass
        else:
            raise AssertionError("mapping-only authorizer call unexpectedly succeeded")

        for candidate in (False, True, {}, {"authorized": True}, forged_grant):
            manifest = finalizing_manifest()
            matrix.atomic_write_json(persisted, manifest)
            persisted_before = persisted.read_bytes()
            manifest_before = copy.deepcopy(manifest)
            require(
                not matrix.finalize_terminal_manifest(
                    manifest, grant=candidate
                ),
                "forgeable grant was accepted",
            )
            require(manifest == manifest_before, "rejection mutated manifest")
            require(
                persisted.read_bytes() == persisted_before,
                "rejection changed persisted bytes",
            )

        manifest = finalizing_manifest()
        authority = register_test_run_authority(manifest)
        grant = matrix._authorize_terminal_manifest(
            manifest, authority=authority
        )
        assert_type_error(lambda: copy.copy(grant))
        assert_type_error(lambda: copy.deepcopy(grant))
        require(
            matrix.finalize_terminal_manifest(manifest, grant=grant),
            "registered grant did not finalize",
        )
        passed_before = copy.deepcopy(manifest)
        require(
            not matrix.finalize_terminal_manifest(manifest, grant=grant),
            "one-shot grant was reused",
        )
        require(manifest == passed_before, "reuse mutated terminal manifest")

        first = finalizing_manifest()
        second = finalizing_manifest()
        cross_authority = register_test_run_authority(first)
        cross_grant = matrix._authorize_terminal_manifest(
            first, authority=cross_authority
        )
        matrix.atomic_write_json(persisted, first)
        persisted_before = persisted.read_bytes()
        first_before = copy.deepcopy(first)
        second_before = copy.deepcopy(second)
        require(
            not matrix.finalize_terminal_manifest(second, grant=cross_grant),
            "cross-manifest grant was accepted",
        )
        require(first == first_before and second == second_before, "cross-use mutation")
        require(persisted.read_bytes() == persisted_before, "cross-use persisted mutation")
        require(
            not matrix.finalize_terminal_manifest(first, grant=cross_grant),
            "rejected cross-use grant remained reusable",
        )

        mutated = finalizing_manifest()
        mutation_authority = register_test_run_authority(mutated)
        mutation_grant = matrix._authorize_terminal_manifest(
            mutated, authority=mutation_authority
        )
        matrix.atomic_write_json(persisted, mutated)
        persisted_before = persisted.read_bytes()
        mutated["unexpected"] = "mutation"
        mutated_before = copy.deepcopy(mutated)
        require(
            not matrix.finalize_terminal_manifest(
                mutated, grant=mutation_grant
            ),
            "digest-mutated manifest was accepted",
        )
        require(mutated == mutated_before, "digest rejection mutated manifest")
        require(
            persisted.read_bytes() == persisted_before,
            "digest rejection changed persisted bytes",
        )


def test_terminal_finalization_registry_transactions_are_linearizable() -> None:
    def finalizing_manifest() -> dict:
        return {
            "status": "finalizing",
            "sourceDigestStart": "a" * 64,
            "sourceDigestEnd": "a" * 64,
            "server": {
                "terminated": True,
                "denyProxyAttemptCount": 0,
                "pythonSocketGuard": {"attemptCount": 0},
            },
            "summary": {"passed": 9, "failed": 0, "total": 9},
            "expectedCaptureTotal": 9,
            "blockedNetwork": [],
            "exceptions": [],
        }

    matrix.UX1B_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=matrix.UX1B_ROOT) as td:
        root = Path(td)
        authority_index = 0

        def register(manifest: dict):
            nonlocal authority_index
            authority_index += 1
            owned = matrix.create_owned_run(root / f"linear-{authority_index}")
            authority = object.__new__(matrix._RunSuccessAuthority)
            with matrix._FINALIZATION_GRANTS_LOCK:
                matrix._RUN_SUCCESS_AUTHORITIES[id(authority)] = (
                    authority,
                    os.getpid(),
                    manifest,
                    owned,
                    matrix._owned_run_binding(owned),
                )
            return authority

        original_closure = matrix._has_theme_success_closure
        try:
            manifest = finalizing_manifest()
            authority = register(manifest)
            entered = threading.Event()
            release = threading.Event()
            discard_started = threading.Event()
            discard_done = threading.Event()
            result: dict[str, object] = {}

            def blocked_authorization(candidate):
                entered.set()
                require(release.wait(2), "authorization barrier timed out")
                return original_closure(candidate)

            matrix._has_theme_success_closure = blocked_authorization

            def authorize() -> None:
                result["grant"] = matrix._authorize_terminal_manifest(
                    manifest, authority=authority
                )

            def discard() -> None:
                discard_started.set()
                matrix._discard_run_success_authority(authority)
                discard_done.set()

            authorizer = threading.Thread(target=authorize)
            revoker = threading.Thread(target=discard)
            authorizer.start()
            require(entered.wait(2), "authorization did not enter closure")
            revoker.start()
            require(discard_started.wait(2), "revoker did not start")
            require(not discard_done.wait(0.05), "discard bypassed authorization lock")
            release.set()
            authorizer.join(2)
            revoker.join(2)
            require(not authorizer.is_alive() and not revoker.is_alive(), "race threads stuck")
            require(discard_done.is_set(), "discard did not finish")
            require(
                not matrix.finalize_terminal_manifest(
                    manifest, grant=result["grant"]
                ),
                "grant remained valid after discard returned",
            )
            require(manifest["status"] == "finalizing", "discard race passed manifest")
            require(matrix._RUN_SUCCESS_AUTHORITIES == {}, "authority registry leak")
            require(matrix._FINALIZATION_GRANTS == {}, "grant registry leak")

            matrix._has_theme_success_closure = original_closure
            final_manifest = finalizing_manifest()
            final_authority = register(final_manifest)
            final_grant = matrix._authorize_terminal_manifest(
                final_manifest, authority=final_authority
            )
            final_entered = threading.Event()
            final_release = threading.Event()
            final_discard_started = threading.Event()
            final_discard_done = threading.Event()
            final_result: dict[str, object] = {}

            def blocked_finalization(candidate):
                final_entered.set()
                require(final_release.wait(2), "finalization barrier timed out")
                return original_closure(candidate)

            matrix._has_theme_success_closure = blocked_finalization

            def finalize() -> None:
                final_result["passed"] = matrix.finalize_terminal_manifest(
                    final_manifest, grant=final_grant
                )

            def discard_final() -> None:
                final_discard_started.set()
                matrix._discard_run_success_authority(final_authority)
                final_result["statusAtDiscardReturn"] = final_manifest["status"]
                final_discard_done.set()

            finalizer = threading.Thread(target=finalize)
            final_revoker = threading.Thread(target=discard_final)
            finalizer.start()
            require(final_entered.wait(2), "finalizer did not enter closure")
            final_revoker.start()
            require(final_discard_started.wait(2), "final revoker did not start")
            require(
                not final_discard_done.wait(0.05),
                "discard bypassed finalization lock",
            )
            final_release.set()
            finalizer.join(2)
            final_revoker.join(2)
            require(
                not finalizer.is_alive() and not final_revoker.is_alive(),
                "final race threads stuck",
            )
            require(
                final_result
                == {"passed": True, "statusAtDiscardReturn": "passed"},
                f"finalization linearization differs: {final_result!r}",
            )
            require(matrix._RUN_SUCCESS_AUTHORITIES == {}, "authority registry leak")
            require(matrix._FINALIZATION_GRANTS == {}, "grant registry leak")
        finally:
            matrix._has_theme_success_closure = original_closure
            with matrix._FINALIZATION_GRANTS_LOCK:
                matrix._RUN_SUCCESS_AUTHORITIES.clear()
                matrix._FINALIZATION_GRANTS.clear()


def test_worker_helper_imports_and_path_normalization_outside_repo_cwd() -> None:
    probe = r'''
import json
import runpy
import sys

namespace = runpy.run_path(sys.argv[1], run_name="theme_outside_cwd_probe")
command = namespace["build_browser_worker_command"](
    sys.executable,
    namespace["BROWSER_WORKER_PATH"],
    expected_origin="http://127.0.0.1:43111",
    expected_request_id="theme-gallery/desktop",
    allowed_staging_paths=("staging/capture.png", "staging/render.json"),
)
print(json.dumps(command))
'''
    with tempfile.TemporaryDirectory() as td:
        completed = subprocess.run(
            [sys.executable, "-c", probe, str(ROOT / "scripts" / "ui_ux_theme_matrix.py")],
            cwd=td,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            check=False,
        )
    require(completed.returncode == 0, completed.stderr)
    command = json.loads(completed.stdout)
    require(command[0] == sys.executable, "worker Python path")
    require(command[1] == "scripts/ui_ux_browser_worker.py", "relative worker path")


def test_theme_worker_request_and_rich_evidence_adapter_fail_closed_exactly() -> None:
    origin = "http://127.0.0.1:43111"
    for viewport_name, (width, height) in matrix.VIEWPORTS.items():
        request = matrix._theme_worker_request(
            viewport_name=viewport_name,
            viewport=(width, height),
            app_origin=origin,
        )
        expected_request_id = f"theme-gallery/{viewport_name}"
        expected_paths = {
            "png": f"staging/theme-gallery-{viewport_name}.png",
            "renderSidecar": (
                f"staging/theme-gallery-{viewport_name}.render.json"
            ),
        }
        require(
            request
            == {
                "schemaVersion": "quant-radar-ui-ux-browser-request/v1",
                "requestId": expected_request_id,
                "fixtureEntrypoint": "scripts/ui_ux_theme_fixture_app.py",
                "case": "theme-gallery",
                "route": "/",
                "viewport": {
                    "name": viewport_name,
                    "width": width,
                    "height": height,
                },
                "appOrigin": origin,
                "staging": expected_paths,
            },
            f"theme worker request differs for {viewport_name}",
        )

        response = {
            "schemaVersion": "quant-radar-ui-ux-browser-response/v1",
            "requestId": expected_request_id,
            "status": "staged",
            "artifacts": expected_paths,
        }
        generic_sidecar = {
            "schemaVersion": "quant-radar-ui-ux-render/v1",
            "identity": {
                "case": "theme-gallery",
                "route": "/",
                "callable": "ui_ux_theme_fixture_app",
            },
            "viewport": dict(request["viewport"]),
            "readiness": {"ready": True, "marker": "ux1b-theme-ready"},
            "nodes": [],
            "stableState": {"registryKey": "theme-gallery"},
            "providerCounters": {},
            "mutatorCounters": {},
            "runtimeProjection": {
                "sourceRoot": "$OWNED_ROOT_0",
                "browserScratchRoot": "$OWNED_ROOT_1",
            },
        }
        try:
            matrix.adapt_external_worker_theme_evidence(
                request=request,
                response=response,
                sidecar=generic_sidecar,
            )
        except matrix.ThemeContractError as exc:
            require(
                str(exc) == matrix.THEME_WORKER_RICH_EVIDENCE_BLOCKER,
                f"rich-evidence blocker differs: {exc}",
            )
        else:
            raise AssertionError(
                "generic worker sidecar synthesized rich theme evidence"
            )


def _rich_theme_worker_fixture(viewport_name="mobile"):
    from PIL import Image

    viewport = matrix.VIEWPORTS[viewport_name]
    viewport_width, viewport_height = viewport
    request = matrix._theme_worker_request(
        viewport_name=viewport_name,
        viewport=viewport,
        app_origin="http://127.0.0.1:43111",
    )
    response = {
        "schemaVersion": "quant-radar-ui-ux-browser-response/v1",
        "requestId": request["requestId"],
        "status": "staged",
        "artifacts": dict(request["staging"]),
    }
    selector_record = matrix.SelectorContractRecord(
        selector='.st-key-ux1b_owner_canvas_primary [data-testid="stButton"] button',
        property="color",
        owners=(matrix.owner_id("canvas", "primary"),),
        states=("default",),
        important=False,
    )
    selector_row = {
        "states": ["default"],
        "owners": [matrix.owner_id("canvas", "primary")],
        "nodes": [f"{matrix.owner_id('canvas', 'primary')}::0"],
        "signatures": [
            {
                "owner": matrix.owner_id("canvas", "primary"),
                "node": f"{matrix.owner_id('canvas', 'primary')}::0",
                "tag": "button",
                "testid": None,
                "kind": None,
                "role": None,
                "ariaSelected": None,
                "ariaChecked": None,
            }
        ],
        "observations": [{"owners": [matrix.owner_id("canvas", "primary")], "matches": 1}],
        "visitedComputedStyleClaimed": False,
    }
    selector_evidence = {
        "browser": "chromium",
        "viewport": viewport_name,
        "selectors": {selector_record.selector: selector_row},
    }
    selector_evidence["sha256"] = hashlib.sha256(
        matrix.canonical_json(selector_evidence).encode()
    ).hexdigest()
    case_contract = {
        "galleryCases": list(matrix.REQUIRED_GALLERY_CASES),
        "focusCases": list(matrix.FOCUS_CASES),
        "ownerCount": len(matrix.SURFACE_COLORS) * len(matrix.REQUIRED_GALLERY_CASES),
    }
    case_contract["sha256"] = hashlib.sha256(
        matrix.canonical_json(case_contract).encode()
    ).hexdigest()
    surface_rgb = {
        name: list(matrix.rgb(color)) for name, color in matrix.SURFACE_COLORS.items()
    }
    ring_rgb = list(matrix.rgb(matrix.APPROVED_TOKENS["border.focus"]))

    def browser_color(value):
        red, green, blue = matrix.rgb(value)
        return f"rgb({red}, {green}, {blue})"

    def style_snapshot(
        surface,
        *,
        foreground="#ffffff",
        background=None,
        decoration="none",
    ):
        background = background or matrix.SURFACE_COLORS[surface]
        foreground_rgb = list(matrix.rgb(foreground))
        background_rgb = list(matrix.rgb(background))
        return {
            "color": browser_color(foreground),
            "backgroundColor": browser_color(background),
            "borderColors": [browser_color(matrix.APPROVED_TOKENS["interactive.control"])] * 4,
            "borderWidths": ["1px"] * 4,
            "outlineColor": browser_color(matrix.APPROVED_TOKENS["border.focus"]),
            "outlineWidth": "0px",
            "outlineOffset": "0px",
            "textDecorationLine": decoration,
            "textDecorationThickness": "auto",
            "opacity": 1,
            "resolvedForeground": foreground_rgb,
            "resolvedBackground": background_rgb,
            "textContrast": round(
                matrix.contrast_ratio(tuple(foreground_rgb), tuple(background_rgb)),
                3,
            ),
            "rect": {
                "x": 10,
                "y": 10,
                "width": 100,
                "height": 30,
                "top": 10,
                "right": 110,
                "bottom": 40,
                "left": 10,
            },
        }

    def selected_controls(surface):
        result = {}
        for case in (
            "checkbox",
            "radio",
            "radio_horizontal",
            "toggle",
            "slider",
            "selectbox",
        ):
            parts = {}
            for name, spec in matrix._SELECTED_PART_SPECS.get(case, {}).items():
                actual = (
                    list(matrix.rgb(matrix.APPROVED_TOKENS[spec["role"]]))
                    if spec["role"] is not None
                    else [255, 255, 255]
                )
                adjacent = (
                    surface_rgb[surface]
                    if spec["adjacent"] == "surface"
                    else list(matrix.rgb(matrix.APPROVED_TOKENS[spec["adjacent"]]))
                )
                parts[name] = {
                    "node": spec["node"],
                    "paint": spec["paint"],
                    "actual": actual,
                    "adjacent": adjacent,
                    "composited": True,
                    "source": "computed-style",
                    "expectedRole": spec["role"],
                    "adjacentRole": spec["adjacent"],
                    "minimumContrast": spec["minimum"],
                    "contrast": round(
                        matrix.contrast_ratio(tuple(actual), tuple(adjacent)), 3
                    ),
                }
            semantics = {}
            if case == "radio_horizontal":
                semantics = {
                    "groupRole": "radiogroup",
                    "groupName": "水平單選標籤",
                    "optionRole": "radio",
                    "optionLabels": ["已選項", "其他項"],
                    "checkedLabels": ["已選項"],
                    "tabSequenceLabels": ["已選項"],
                    "afterArrowRight": "其他項",
                    "afterArrowLeft": "已選項",
                    "layout": [
                        {
                            "left": 10,
                            "right": 40,
                            "top": 10,
                            "bottom": 40,
                            "width": 30,
                            "height": 30,
                        },
                        {
                            "left": 50,
                            "right": 80,
                            "top": 10,
                            "bottom": 40,
                            "width": 30,
                            "height": 30,
                        },
                    ],
                    "selectionBasis": "native-radio/one-checked/roving-tabstop",
                }
            elif case == "selectbox":
                semantics = {
                    "role": "combobox",
                    "accessibleName": "下拉選單標籤",
                    "optionLabels": ["已選項", "其他項"],
                    "selectedText": "已選項",
                    "afterArrowDown": "其他項",
                    "afterArrowUp": "已選項",
                    "selectionBasis": "combobox/exact-option-order/keyboard",
                    "selectedValue": style_snapshot(surface),
                }
            result[case] = {
                "semantics": semantics,
                "label": style_snapshot(surface),
                "parts": parts,
                "domParts": {},
                "owner": matrix.owner_id(surface, case),
            }
        return result

    def focus_payload(surface):
        sample = {
            side: {
                "gap": surface_rgb[surface],
                "ring": ring_rgb,
                "outer": surface_rgb[surface],
                "clipped": False,
            }
            for side in matrix.FOCUS_SIDES
        }
        return {
            case: {
                "keyboard": "Tab then Shift+Tab",
                "outlineWidth": 3,
                "outlineOffset": 1,
                "outlineColor": "rgb(127, 227, 240)",
                "deviceScaleFactor": 1,
                "samples": copy.deepcopy(sample),
            }
            for case in matrix.FOCUS_CASES
        }

    surfaces = []
    for index, (surface, color) in enumerate(matrix.SURFACE_COLORS.items()):
        y = index * 1_000
        primary_states = {
            case: {
                "default": style_snapshot(
                    surface,
                    background=matrix.APPROVED_TOKENS["interactive.primary"],
                ),
                "hover": style_snapshot(
                    surface,
                    background=matrix.APPROVED_TOKENS["interactive.hover"],
                ),
                "active": style_snapshot(
                    surface,
                    background=matrix.APPROVED_TOKENS["interactive.active"],
                ),
            }
            for case in matrix.PRIMARY_CASES
        }
        tertiary_states = {
            state: style_snapshot(
                surface,
                foreground=matrix.APPROVED_TOKENS["interactive.accent"],
            )
            for state in ("default", "hover", "active")
        }
        tab_style = style_snapshot(
            surface, foreground=matrix.APPROVED_TOKENS["interactive.accent"]
        )
        markdown_style = style_snapshot(
            surface,
            foreground=matrix.APPROVED_TOKENS["interactive.accent"],
            decoration="underline",
        )
        surfaces.append(
            {
                "name": surface,
                "color": color,
                "geometry": {
                    "selector": f".st-key-ux1b_surface_{surface}",
                    "coordinateSpace": "full-page-css-pixels",
                    "deviceScaleFactor": 1,
                    "scrollOffset": {"x": 0, "y": 0},
                    "cssRect": {
                        "left": 0,
                        "top": y,
                        "right": viewport_width,
                        "bottom": y + 900,
                        "width": viewport_width,
                        "height": 900,
                    },
                    "crop": {
                        "x": 0,
                        "y": y,
                        "width": viewport_width,
                        "height": 900,
                    },
                },
                "states": {
                    "primary": primary_states,
                    "tertiary": tertiary_states,
                    "disabled": {
                        "semantics": {
                            "disabled": True,
                            "ariaDisabled": None,
                            "programmaticClickEvents": 0,
                            "focusAccepted": False,
                            "inactiveContrastException": True,
                        },
                        "default": style_snapshot(
                            surface,
                            foreground=matrix.APPROVED_TOKENS["text.disabled"],
                        ),
                    },
                    "tabs": {
                        "active": tab_style,
                        "hover": copy.deepcopy(tab_style),
                        "semantics": {
                            "ariaSelected": "true",
                            "underline": [
                                {
                                    "backgroundColor": browser_color(
                                        matrix.APPROVED_TOKENS["interactive.accent"]
                                    ),
                                    "width": 20,
                                    "height": 2,
                                    "testid": None,
                                }
                            ],
                        },
                    },
                    "markdownLink": {
                        "default": markdown_style,
                        "hover": copy.deepcopy(markdown_style),
                        "visited": "static-only; no protected-history claim",
                    },
                    "selectedControls": selected_controls(surface),
                    "alerts": [
                        {
                            "role": "alert",
                            "meaning": meaning,
                            "hasIcon": True,
                            "style": style_snapshot(surface),
                        }
                        for meaning in (
                            "資訊狀態",
                            "成功狀態",
                            "警告狀態",
                            "錯誤狀態",
                        )
                    ],
                    "signals": [
                        {
                            "meaning": "AVOID",
                            "color": "#ef4444",
                            "hasIcon": True,
                            "text": "⛔ AVOID",
                        },
                        {
                            "meaning": "Bearish",
                            "color": "#ef553b",
                            "hasIcon": True,
                            "text": "▼ Bearish",
                        },
                    ],
                    "focus": focus_payload(surface),
                },
                "overflow": {
                    "surface": {
                        "clientWidth": viewport_width,
                        "scrollWidth": viewport_width,
                        "left": 0,
                        "right": viewport_width,
                        "backgroundColor": browser_color(color),
                    },
                    "document": {
                        "clientWidth": viewport_width,
                        "scrollWidth": viewport_width,
                    },
                    "overflowOwners": [],
                },
            }
        )
    source_digest = matrix.source_digest()
    selector_contract_sha256 = "a" * 64
    rich = {
        "schemaVersion": matrix.THEME_WORKER_EVIDENCE_SCHEMA,
        "browser": {"name": "chromium", "version": "test-chromium"},
        "viewport": {
            "name": viewport_name,
            "width": viewport_width,
            "height": viewport_height,
            "deviceScaleFactor": 1,
        },
        "fullPage": {
            "width": viewport_width,
            "height": 3_000,
            "deviceScaleFactor": 1,
        },
        "caseContract": case_contract,
        "selectorContractSha256": selector_contract_sha256,
        "selectorEvidence": selector_evidence,
        "surfaces": surfaces,
        "sourceDigest": source_digest,
    }
    rich["sha256"] = hashlib.sha256(matrix.canonical_json(rich).encode()).hexdigest()
    sidecar = {
        "schemaVersion": "quant-radar-ui-ux-render/v1",
        "identity": {
            "case": "theme-gallery",
            "route": "/",
            "callable": "ui_ux_theme_fixture_app",
        },
        "viewport": dict(request["viewport"]),
        "readiness": {"ready": True, "marker": "ux1b-theme-ready"},
        "nodes": [],
        "stableState": {
            "finalPath": "/",
            "controls": {},
            "diagnostics": {
                "blockedRequestCount": 0,
                "failedRequestCount": 0,
                "httpErrorCount": 0,
                "pageErrorCount": 0,
                "consoleErrorCount": 0,
                "dialogCount": 0,
                "downloadCount": 0,
                "popupCount": 0,
                "crashCount": 0,
            },
            "registryKey": "theme-gallery",
            "themeEvidence": rich,
        },
        "providerCounters": {},
        "mutatorCounters": {},
        "runtimeProjection": {
            "sourceRoot": "$OWNED_ROOT_0",
            "browserScratchRoot": "$OWNED_ROOT_1",
        },
    }
    image = Image.new("RGB", (viewport_width, 3_000), (0, 0, 0))
    for surface_row in surfaces:
        crop = surface_row["geometry"]["crop"]
        image.paste(
            matrix.rgb(surface_row["color"]),
            (
                crop["x"],
                crop["y"],
                crop["x"] + crop["width"],
                crop["y"] + crop["height"],
            ),
        )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return {
        "request": request,
        "response": response,
        "sidecar": sidecar,
        "png": buffer.getvalue(),
        "records": (selector_record,),
        "selectorContractSha256": selector_contract_sha256,
        "sourceDigest": source_digest,
    }


def test_theme_worker_rich_adapter_and_surface_crops_are_exact_and_fail_closed() -> None:
    fixture = _rich_theme_worker_fixture()
    rich = matrix.adapt_external_worker_theme_evidence(
        request=fixture["request"],
        response=fixture["response"],
        sidecar=fixture["sidecar"],
        full_page_png=fixture["png"],
        records=fixture["records"],
        expected_selector_contract_sha256=fixture["selectorContractSha256"],
        expected_source_digest=fixture["sourceDigest"],
    )
    require(len(rich["surfaces"]) == 3, "rich theme surface count")
    matrix.UX1B_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=matrix.UX1B_ROOT) as td:
        owned = matrix.create_owned_run(Path(td))
        captures = matrix._materialize_external_worker_theme_captures(
            rich=rich,
            full_page_png=fixture["png"],
            owned=owned,
            source_digest_value=fixture["sourceDigest"],
        )
        require(len(captures) == 3, "worker did not derive three surface captures")
        require(
            {row["id"] for row in captures}
            == {
                "chromium-mobile-canvas",
                "chromium-mobile-panel",
                "chromium-mobile-elevated",
            },
            "derived surface identities differ",
        )
        require(
            all((Path(td) / f"{row['id']}.png").is_file() for row in captures),
            "derived surface PNG is missing",
        )
        from PIL import Image

        for row in captures:
            surface = row["surface"]["name"]
            with Image.open(Path(td) / f"{row['id']}.png") as cropped:
                require(
                    cropped.size == (390, 900),
                    f"derived crop dimensions differ: {surface}",
                )
                require(
                    cropped.convert("RGB").getcolors(maxcolors=2)
                    == [(390 * 900, matrix.rgb(matrix.SURFACE_COLORS[surface]))],
                    f"derived crop pixels were resampled or offset: {surface}",
                )

    for mutation in ("digest", "crop", "semantics", "focus"):
        candidate = copy.deepcopy(fixture["sidecar"])
        theme = candidate["stableState"]["themeEvidence"]
        if mutation == "digest":
            theme["sha256"] = "0" * 64
        elif mutation == "crop":
            theme["surfaces"][1]["geometry"]["crop"]["y"] = 0
            theme["sha256"] = hashlib.sha256(
                matrix.canonical_json(
                    {key: value for key, value in theme.items() if key != "sha256"}
                ).encode()
            ).hexdigest()
        elif mutation == "semantics":
            semantics = theme["surfaces"][0]["states"]["selectedControls"][
                "radio_horizontal"
            ]["semantics"]
            semantics["checkedLabels"] = ["其他項"]
            theme["sha256"] = hashlib.sha256(
                matrix.canonical_json(
                    {key: value for key, value in theme.items() if key != "sha256"}
                ).encode()
            ).hexdigest()
        else:
            sample = theme["surfaces"][0]["states"]["focus"]["primary"][
                "samples"
            ]["top"]
            sample["ring"] = [0, 0, 0]
            theme["sha256"] = hashlib.sha256(
                matrix.canonical_json(
                    {key: value for key, value in theme.items() if key != "sha256"}
                ).encode()
            ).hexdigest()
        raises_contract(
            lambda candidate=candidate: matrix.adapt_external_worker_theme_evidence(
                request=fixture["request"],
                response=fixture["response"],
                sidecar=candidate,
                full_page_png=fixture["png"],
                records=fixture["records"],
                expected_selector_contract_sha256=fixture[
                    "selectorContractSha256"
                ],
                expected_source_digest=fixture["sourceDigest"],
            )
        )


def test_worker_theme_only_hook_reaches_mirrored_collector_and_missing_css_fails_closed() -> None:
    from scripts import ui_ux_browser_worker as worker
    from scripts import ui_ux_evidence as evidence
    from ui import _design

    fixture = _rich_theme_worker_fixture()
    request = fixture["request"]
    identity = evidence.validate_worker_capture_identity(request)

    class Browser:
        version = "controlled-chromium"

    observed = {}

    def collector(page, **kwargs):
        observed["page"] = page
        observed["kwargs"] = kwargs
        return fixture["sidecar"]["stableState"]["themeEvidence"]

    sentinel_page = object()
    with patch.object(matrix, "collect_external_worker_theme_evidence", collector):
        result = worker._collect_theme_evidence_for_capture(
            request,
            identity,
            page=sentinel_page,
            browser=Browser(),
        )
        require(result == fixture["sidecar"]["stableState"]["themeEvidence"], "worker theme hook result")
        require(observed["page"] is sentinel_page, "worker changed collector page")
        require(
            observed["kwargs"]
            == {
                "viewport_name": "mobile",
                "viewport": (390, 844),
                "browser_name": "chromium",
                "browser_version": "controlled-chromium",
            },
            "worker collector identity differs",
        )
        require(
            worker._collect_theme_evidence_for_capture(
                {"case": "knowledge-graph-controls"},
                {},
                page=object(),
                browser=Browser(),
            )
            is None,
            "non-theme capture invoked the theme collector",
        )

    invalid_identity = copy.deepcopy(identity)
    invalid_identity["registryKey"] = "other"
    try:
        worker._collect_theme_evidence_for_capture(
            request,
            invalid_identity,
            page=object(),
            browser=Browser(),
        )
    except worker.WorkerBootstrapError:
        pass
    else:
        raise AssertionError("worker accepted an unfrozen theme identity")

    with patch.object(_design, "build_global_theme_css", None, create=True):
        try:
            matrix.collect_external_worker_theme_evidence(
                object(),
                viewport_name="mobile",
                viewport=(390, 844),
                browser_name="chromium",
                browser_version="controlled-chromium",
            )
        except matrix.ThemeContractError as exc:
            require(
                str(exc) == "production theme CSS builder is unavailable",
                f"missing-CSS failure differs: {exc}",
            )
        else:
            raise AssertionError("theme collector passed without production CSS")


def test_theme_browser_path_uses_only_frozen_worker_and_isolation_coordinator() -> None:
    source = Path(matrix.__file__).read_text(encoding="utf-8")
    require("sync_playwright" not in source, "theme runner imports Playwright directly")
    tree = ast.parse(source, filename=str(matrix.__file__))
    run_browsers = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_run_formal_theme_matrix"
    )
    calls = {
        name
        for node in ast.walk(run_browsers)
        if isinstance(node, ast.Call)
        for name in (_call_leaf_name(node),)
        if name is not None
    }
    required_calls = {
        "build_browser_worker_command",
        "authorize_calibrated_launch",
        "spawn_calibrated_child",
        "wait_for_clean_owned_process_group_exit",
        "authenticate_raw_render_sidecar",
        "_read_descriptor_authenticated_worker_artifact",
        "adapt_external_worker_theme_evidence",
        "publish_derived_artifact",
    }
    require(
        required_calls <= calls,
        f"theme runner worker/coordinator calls differ: {sorted(calls)!r}",
    )
    require("launch" not in calls, "theme runner launches a browser directly")
    descriptor_reader = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_read_descriptor_authenticated_worker_artifact"
    )
    descriptor_calls = {
        name
        for node in ast.walk(descriptor_reader)
        if isinstance(node, ast.Call)
        for name in (_call_leaf_name(node),)
        if name is not None
    }
    require(
        {"freeze_artifact_contract", "open_authenticated_artifact"}
        <= descriptor_calls,
        f"theme PNG descriptor authentication differs: {sorted(descriptor_calls)!r}",
    )


def test_formal_static_contract_failures_checkpoint_terminal_manifest() -> None:
    from ui import _design

    matrix.UX1B_ROOT.mkdir(parents=True, exist_ok=True)
    cases = ("builder", "selector")
    for label in cases:
        destination = matrix.UX1B_ROOT / (
            f"theme-formal-{label}-{os.getpid()}-{id(cases)}"
        )
        shutil.rmtree(destination, ignore_errors=True)
        args = matrix.build_parser().parse_args(
            [
                "--out-dir",
                str(destination),
                "--browser",
                "chromium",
                "--no-prompt",
                "--json",
            ]
        )
        builder = None if label == "builder" else (lambda: "<style></style>")
        selector_side_effect = (
            matrix.ThemeContractError("injected selector failure")
            if label == "selector"
            else None
        )
        try:
            with (
                patch.object(
                    matrix,
                    "_recover_stale_theme_runtimes",
                    return_value=(),
                ),
                patch.object(
                    _design,
                    "build_global_theme_css",
                    builder,
                    create=True,
                ),
                patch.object(
                    matrix,
                    "validate_palette_contract",
                    return_value=None,
                ),
                patch.object(
                    matrix,
                    "validate_design_token_contract",
                    return_value=None,
                ),
                patch.object(matrix, "extract_theme_css", return_value=""),
                patch.object(matrix, "validate_css_safety", return_value=None),
                patch.object(matrix, "validate_link_contract", return_value=None),
                patch.object(
                    matrix,
                    "validate_selector_contract",
                    side_effect=selector_side_effect,
                    return_value=(),
                ),
            ):
                code, manifest = matrix.run_matrix(args)
            persisted = json.loads(
                (destination / "manifest.json").read_text(encoding="utf-8")
            )
            require(code == 3, f"{label} failure exit code differs: {code}")
            require(
                manifest["status"] == "invalid_data"
                and persisted["status"] == "invalid_data",
                f"{label} failure did not checkpoint invalid_data",
            )
            require(
                persisted["mode"] == "ux1b-theme"
                and persisted["phase"] == "posttheme"
                and persisted["expectedCaptureCount"] == 3,
                f"{label} terminal identity differs",
            )
        finally:
            shutil.rmtree(destination, ignore_errors=True)


def test_formal_cleanup_retries_transient_and_quarantines_persistent_failure() -> None:
    process = object()
    owned = object()

    class TransientIsolation:
        calls = 0

        @classmethod
        def terminate_owned_process_group(cls, observed) -> None:
            require(observed is process, "cleanup targeted the wrong process")
            cls.calls += 1
            if cls.calls == 1:
                raise RuntimeError("transient cleanup failure")

    attempted: set[int] = set()
    with patch.object(
        matrix,
        "_release_theme_formal_runtime",
        return_value=None,
    ) as release:
        result = matrix._finalize_formal_theme_cleanup(
            TransientIsolation,
            owned,
            processes=(process,),
            attempted=attempted,
            verified_captures=(),
        )
    require(result is None, "transient cleanup did not recover")
    require(
        TransientIsolation.calls == 2
        and attempted == {id(process)}
        and release.call_count == 1,
        "transient cleanup retry/release closure differs",
    )

    class PersistentIsolation:
        calls = 0

        @classmethod
        def terminate_owned_process_group(cls, _observed) -> None:
            cls.calls += 1
            raise RuntimeError("persistent cleanup failure")

    before = list(matrix._RETAINED_FAILED_THEME_RUNTIMES)
    try:
        with patch.object(
            matrix,
            "_release_theme_formal_runtime",
            side_effect=AssertionError("quarantined runtime was released"),
        ) as release:
            result = matrix._finalize_formal_theme_cleanup(
                PersistentIsolation,
                owned,
                processes=(process,),
                attempted=set(),
                verified_captures=(),
            )
        require(isinstance(result, RuntimeError), "persistent cleanup lost its error")
        require(
            PersistentIsolation.calls == 3
            and release.call_count == 0
            and matrix._RETAINED_FAILED_THEME_RUNTIMES[-1] is owned,
            "persistent cleanup did not retain the full leased runtime",
        )
    finally:
        matrix._RETAINED_FAILED_THEME_RUNTIMES[:] = before


def test_formal_theme_failure_uses_plain_partial_artifact_snapshots() -> None:
    source = inspect.getsource(matrix._run_formal_theme_matrix)
    verify_index = source.index("evidence.verify_capture_artifacts")
    opaque_append_index = source.index("verified_captures.append", verify_index)
    payload_append_index = source.index(
        "partial_artifact_payloads.append", opaque_append_index
    )
    comparator_index = source.index("evidence.validate_live_capture_profile")
    finalizer_index = source.index("evidence.finalize_terminal_manifest")
    failure_index = source.index("    except BaseException as exc:", finalizer_index)
    failure = source[failure_index:]

    require(
        verify_index
        < opaque_append_index
        < payload_append_index
        < comparator_index
        < finalizer_index,
        "theme plain payload snapshot is not captured immediately after verification",
    )
    require(
        "copy.deepcopy(dict(verified))"
        in source[opaque_append_index:comparator_index],
        "theme failure payload is not detached from opaque capture authority",
    )
    require(
        "verified_captures," in source[comparator_index:finalizer_index],
        "theme success closure no longer uses opaque verified captures",
    )
    require(
        'updates["partialArtifacts"] = copy.deepcopy(\n'
        "                        partial_artifact_payloads"
        in failure,
        "theme failure checkpoint still serializes opaque captures",
    )


def legacy_run_matrix_terminalizes_interrupts_and_cleanup_failures() -> None:
    from ui import _design

    class FakeProxy:
        port = 43112
        closed = False

        def close(self) -> None:
            self.closed = True

    class FakeProcess:
        pid = 43111

        @staticmethod
        def poll() -> int:
            return 0

    def fake_run_browsers(*, selected, manifest, **_kwargs) -> None:
        for browser in selected:
            for viewport in matrix.VIEWPORTS:
                manifest["selectorEvidence"].append(
                    {"browser": browser, "viewport": viewport}
                )
                for surface in matrix.SURFACE_COLORS:
                    manifest["captures"].append(
                        {
                            "id": f"{browser}-{viewport}-{surface}",
                            "status": "passed",
                        }
                    )

    def successful_attempt_evidence(manifest, server):
        manifest["server"].update(
            {
                "denyProxyAttemptCount": 0,
                "denyProxyAttempts": [],
                "pythonSocketGuard": {"attemptCount": 0},
                "terminated": True,
                "returnCode": 0,
            }
        )
        return [], {"attemptCount": 0}

    def run_case(kind: str) -> tuple[int, dict, dict, FakeProxy]:
        proxy = FakeProxy()
        diagnostic_secret = "sk-supersecret123"
        active_run_dir = ""
        server = matrix.OwnedThemeServer(
            port=43111,
            process=FakeProcess(),
            deny_proxy=proxy,
            guard_path=Path("unused"),
            child_environment={},
            sandbox_calibration=types.MappingProxyType(
                {"capability": "supported"}
            ),
        )

        @contextlib.contextmanager
        def fake_owned_server(_owned, **_kwargs):
            try:
                yield server
            finally:
                proxy.close()
                if kind == "context_interrupt":
                    raise matrix.RunnerInterrupted("context cleanup")

        @contextlib.contextmanager
        def fake_worker_session(_port):
            yield object()

        digest_calls = 0

        def digest():
            nonlocal digest_calls
            digest_calls += 1
            if kind == "digest_interrupt" and digest_calls >= 2:
                raise KeyboardInterrupt("digest closure")
            return "d" * 64

        def record(manifest, owned_server):
            if kind == "record_interrupt":
                raise matrix.RunnerInterrupted("proxy evidence")
            if kind == "record_failure":
                raise RuntimeError(
                    f"{active_run_dir}/private.json token={diagnostic_secret} "
                    + ("x" * 5_000)
                )
            return successful_attempt_evidence(manifest, owned_server)

        original_authorizer = matrix._authorize_terminal_manifest

        def authorize(manifest, **kwargs):
            if kind == "authorize_interrupt":
                raise KeyboardInterrupt("before pass")
            return original_authorizer(manifest, **kwargs)

        original_discard = matrix._discard_run_success_authority
        discard_calls = 0

        def discard(authority):
            nonlocal discard_calls
            discard_calls += 1
            original_discard(authority)
            if kind == "discard_interrupt" and discard_calls == 1:
                raise matrix.RunnerInterrupted("late capability cleanup")

        original_signal = matrix.signal.signal
        original_replace = matrix.os.replace
        signal_calls = 0
        terminal_replaces = 0

        def restore_signal(signum, handler):
            nonlocal signal_calls
            signal_calls += 1
            if kind == "restore_interrupt" and signal_calls == 3:
                raise matrix.RunnerInterrupted("late handler restoration")
            return original_signal(signum, handler)

        def replace_after_terminal_interrupt(source, destination):
            nonlocal terminal_replaces
            try:
                pending = json.loads(Path(source).read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                pending = {}
            if kind == "replace_interrupt" and pending.get("status") == "passed":
                terminal_replaces += 1
                current_mask = signal.pthread_sigmask(signal.SIG_BLOCK, ())
                require(signal.SIGINT in current_mask, "SIGINT commit mask")
                require(signal.SIGTERM in current_mask, "SIGTERM commit mask")
                require(
                    signal.getsignal(signal.SIGINT) == prior_sigint,
                    "SIGINT restored before commit",
                )
                require(
                    signal.getsignal(signal.SIGTERM) == prior_sigterm,
                    "SIGTERM restored before commit",
                )
                require(
                    matrix._RUN_SUCCESS_AUTHORITIES == {},
                    "authority revoked before commit",
                )
                require(
                    matrix._FINALIZATION_GRANTS == {},
                    "grant revoked before commit",
                )
            original_replace(source, destination)
            if kind == "replace_interrupt" and pending.get("status") == "passed":
                raise matrix.RunnerInterrupted("after terminal replace")

        matrix.UX1B_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=matrix.UX1B_ROOT) as td:
            active_run_dir = td
            args = matrix.build_parser().parse_args(
                ["--out-dir", td, "--browser", "chromium", "--no-prompt", "--json"]
            )
            prior_sigint = signal.getsignal(signal.SIGINT)
            prior_sigterm = signal.getsignal(signal.SIGTERM)
            prior_signal_mask = signal.pthread_sigmask(signal.SIG_BLOCK, ())
            with (
                patch.object(
                    _design, "build_global_theme_css", lambda: "", create=True
                ),
                patch.object(matrix, "validate_palette_contract", lambda *_a, **_k: None),
                patch.object(matrix, "validate_design_token_contract", lambda *_a, **_k: None),
                patch.object(matrix, "extract_theme_css", lambda _css: ""),
                patch.object(matrix, "validate_css_safety", lambda *_a, **_k: None),
                patch.object(matrix, "validate_link_contract", lambda *_a, **_k: None),
                patch.object(matrix, "validate_selector_contract", lambda *_a, **_k: ()),
                patch.object(
                    matrix,
                    "_theme_browser_worker_session",
                    fake_worker_session,
                ),
                patch.object(matrix, "_owned_gallery_server", fake_owned_server),
                patch.object(matrix, "_run_browsers", fake_run_browsers),
                patch.object(
                    matrix,
                    "_child_environment_evidence",
                    lambda *_a, **_k: {
                        "allowlistApplied": True,
                        "credentialFree": True,
                        "privateDirectories": True,
                        "proxyContractExact": True,
                    },
                ),
                patch.object(matrix, "_record_server_attempt_evidence", record),
                patch.object(matrix, "source_digest", digest),
                patch.object(matrix, "_authorize_terminal_manifest", authorize),
                patch.object(matrix, "_discard_run_success_authority", discard),
                patch.object(matrix.signal, "signal", restore_signal),
                patch.object(matrix.os, "replace", replace_after_terminal_interrupt),
            ):
                code, manifest = matrix.run_matrix(args)
            persisted = json.loads((Path(td) / "manifest.json").read_text())
            require(signal.getsignal(signal.SIGINT) == prior_sigint, "SIGINT restore")
            require(signal.getsignal(signal.SIGTERM) == prior_sigterm, "SIGTERM restore")
            require(
                signal.pthread_sigmask(signal.SIG_BLOCK, ()) == prior_signal_mask,
                "terminal signal mask restore",
            )
            if kind == "replace_interrupt":
                require(terminal_replaces == 1, "passed commit must replace once")
        return code, manifest, persisted, proxy

    for kind in (
        "context_interrupt",
        "digest_interrupt",
        "record_interrupt",
        "authorize_interrupt",
        "discard_interrupt",
        "restore_interrupt",
    ):
        code, manifest, persisted, proxy = run_case(kind)
        require(
            code == 130,
            f"{kind} exit code: code={code} manifest={manifest}",
        )
        require(manifest["status"] == "interrupted", f"{kind} in-memory status")
        require(persisted["status"] == "interrupted", f"{kind} persisted status")
        require(proxy.closed, f"{kind} proxy cleanup")

    code, manifest, persisted, proxy = run_case("record_failure")
    require(code == 1, "ordinary cleanup failure exit code")
    require(manifest["status"] == "failed", "ordinary cleanup in-memory status")
    require(persisted["status"] == "failed", "ordinary cleanup persisted status")
    require(proxy.closed, "ordinary cleanup proxy close")
    persisted_text = json.dumps(persisted)
    require("sk-supersecret123" not in persisted_text, "terminal secret leaked")
    require(str(matrix.ROOT) not in persisted_text, "workspace path leaked")
    require(
        len(persisted["failure"]["message"])
        <= matrix.MAX_DIAGNOSTIC_MESSAGE_CHARS,
        "terminal diagnostic is unbounded",
    )
    require(matrix._RUN_SUCCESS_AUTHORITIES == {}, "run authority registry cleanup")
    require(matrix._FINALIZATION_GRANTS == {}, "grant registry cleanup")

    code, manifest, persisted, proxy = run_case("replace_interrupt")
    require(code == 0, "post-replace interrupt must preserve committed success")
    require(manifest["status"] == "passed", "post-replace in-memory success")
    require(persisted["status"] == "passed", "post-replace persisted success")
    require(proxy.closed, "post-replace proxy close")


def test_output_ownership_and_manifest_shape_are_exact() -> None:
    matrix.UX1B_ROOT.mkdir(parents=True, exist_ok=True)
    require(
        matrix._CAPTURE_RE.fullmatch(matrix._default_run_dir().name.replace(".", "_")) is not None,
        "default run id must satisfy its own stable-id contract",
    )
    run_dir = matrix.UX1B_ROOT / "theme-states-unit-owned"
    shutil.rmtree(run_dir, ignore_errors=True)
    try:
        owned = matrix.create_owned_run(run_dir)
        require(owned.owner_path.read_text(encoding="utf-8") == "quant-radar-ui-ux-ux1b-theme\n", "owner marker")
        manifest = matrix._manifest_template(owned, ("chromium",))
        require(manifest["schemaVersion"] == "quant-radar-ui-ux-ux1b-theme-states/v1", "schema")
        require(manifest["mode"] == "ux1b-theme-states", "mode")
        require(manifest["expectedCapturesPerBrowser"] == 9, "3x3 matrix")
        require(manifest["expectedCaptureTotal"] == 9, "exact Chromium total")
        require(len(manifest["surfaces"]) == 3 and len(manifest["viewports"]) == 3, "axes")
        require(manifest["selectorContract"] is None, "selector contract must start pending")
        require(manifest["network"] == [] and manifest["blockedNetwork"] == [], "network starts empty")
        require(manifest["sourceDigestStart"] == matrix.source_digest(), "source start")
        require(manifest["sourceDigestEnd"] is None, "source end must be pending")
        raises_contract(lambda: matrix.create_owned_run(run_dir))
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)

    raises_contract(lambda: matrix.create_owned_run(ROOT / "reports" / "ux1b-theme"))
    raises_contract(lambda: matrix.create_owned_run(matrix.UX1B_ROOT / "ux0" / "bad"))
    raises_contract(lambda: matrix.create_owned_run(matrix.UX1B_ROOT / "ux1a" / "bad"))


def test_formal_output_namespace_freezes_workspace_and_every_ancestor() -> None:
    with tempfile.TemporaryDirectory() as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir(mode=0o700)
        ux1b_root = workspace / ".claude" / "ui_snapshots" / "ux1b"
        destination = ux1b_root / "nested" / "run"
        with (
            patch.object(matrix, "WORKSPACE_ROOT", workspace),
            patch.object(matrix, "ROOT", workspace),
            patch.object(matrix, "UX1B_ROOT", ux1b_root),
        ):
            namespace = matrix._open_theme_output_namespace(destination)
            try:
                matrix._reauthenticate_theme_output_namespace(namespace)
                os.chmod(workspace, 0o750)
                raises_contract(
                    lambda: matrix._reauthenticate_theme_output_namespace(namespace)
                )
                os.chmod(workspace, 0o700)
                matrix._reauthenticate_theme_output_namespace(namespace)

                snapshots = workspace / ".claude" / "ui_snapshots"
                snapshots.rename(workspace / ".claude" / "ui_snapshots-prior")
                (workspace / ".claude" / "ui_snapshots" / "ux1b").mkdir(
                    parents=True,
                    mode=0o700,
                )
                raises_contract(
                    lambda: matrix._reauthenticate_theme_output_namespace(namespace)
                )
            finally:
                namespace.close()


def test_formal_stale_recovery_rejects_symlink_conflict_and_ancestor_swap() -> None:
    from scripts import ui_ux_evidence as evidence
    from scripts import ui_ux_isolation as isolation

    def require_rejected(callable_) -> None:
        try:
            callable_()
        except (matrix.ThemeContractError, evidence.EvidenceContractError):
            return
        raise AssertionError("formal stale recovery accepted an unsafe namespace")

    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        symlink_root = base / "symlink-root"
        symlink_root.mkdir(mode=0o700)
        (symlink_root / "target").mkdir(mode=0o700)
        (symlink_root / "final").symlink_to("target", target_is_directory=True)
        symlink_fd = os.open(symlink_root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            claim = types.SimpleNamespace(
                root=types.SimpleNamespace(descriptor=symlink_fd)
            )
            require(
                matrix._open_theme_stale_final_root(claim) is None,
                "stale final symlink was not ignored safely",
            )
        finally:
            os.close(symlink_fd)

        class SetupClaim:
            def __init__(self) -> None:
                self.closed = 0

            def close(self) -> None:
                self.closed += 1

        setup_claims = (SetupClaim(), SetupClaim())

        class SetupIsolation:
            MAX_STALE_OWNED_RUN_CANDIDATES = 64

            @staticmethod
            def claim_stale_owned_run_roots(*_args, **_kwargs):
                return setup_claims

        with patch.object(
            matrix,
            "_reauthenticate_theme_output_namespace",
            side_effect=matrix.ThemeContractError("injected recovery setup failure"),
        ):
            require_rejected(
                lambda: matrix._recover_stale_theme_runtimes(
                    evidence,
                    SetupIsolation(),
                    namespace=object(),
                    temp_parent=base,
                )
            )
        require(
            all(claim.closed >= 1 for claim in setup_claims),
            "recovery setup failure leaked stale claims",
        )

        workspace = base / "workspace"
        workspace.mkdir(mode=0o700)
        ux1b_root = workspace / ".claude" / "ui_snapshots" / "ux1b"
        stale_parent = base / "stale"
        stale_parent.mkdir(mode=0o700)

        def make_stale() -> Path:
            runtime = isolation.create_owned_run_root(
                stale_parent,
                prefix="quant-radar-ux1b-theme-",
            )
            lease = isolation.acquire_owned_run_lease(runtime)
            path = runtime.path
            final = path / "final"
            final.mkdir(mode=0o700)
            manifest = {
                "schemaVersion": evidence.EVIDENCE_SCHEMA,
                "status": "running",
                "mode": "ux1b-theme",
                "phase": "posttheme",
                "runId": "ux1b-" + "a" * 32,
                "fixtureEntrypoint": "scripts/ui_ux_theme_fixture_app.py",
                "expectedCaptureCount": 3,
            }
            (final / "manifest.json").write_bytes(
                matrix._theme_canonical_ndjson(manifest)
            )
            os.chmod(final / "manifest.json", 0o600)
            lease.close()
            runtime.close()
            return path

        with (
            patch.object(matrix, "WORKSPACE_ROOT", workspace),
            patch.object(matrix, "ROOT", workspace),
            patch.object(matrix, "UX1B_ROOT", ux1b_root),
        ):
            namespace = matrix._open_theme_output_namespace(ux1b_root / "run")
            try:
                stale = make_stale()
                recovery = ux1b_root / "recovery"
                recovery.mkdir(mode=0o700)
                conflict = recovery / f"stale-{stale.name}.json"
                conflict.write_bytes(b"{}\n")
                os.chmod(conflict, 0o600)
                require_rejected(
                    lambda: matrix._recover_stale_theme_runtimes(
                        evidence,
                        isolation,
                        namespace=namespace,
                        temp_parent=stale_parent,
                    )
                )
                conflict.unlink()
                shutil.rmtree(stale, ignore_errors=True)

                make_stale()
                original_record = evidence.record_stale_nonterminal

                def record_then_swap(*args, **kwargs):
                    result = original_record(*args, **kwargs)
                    recovery.rename(ux1b_root / "recovery-prior")
                    recovery.mkdir(mode=0o700)
                    return result

                with patch.object(
                    evidence,
                    "record_stale_nonterminal",
                    side_effect=record_then_swap,
                ):
                    require_rejected(
                        lambda: matrix._recover_stale_theme_runtimes(
                            evidence,
                            isolation,
                            namespace=namespace,
                            temp_parent=stale_parent,
                        )
                    )
            finally:
                namespace.close()


def test_browser_allowlist_is_exact_origin_not_loopback_wildcard() -> None:
    port = 43129
    allowed = (
        f"http://127.0.0.1:{port}/",
        f"http://127.0.0.1:{port}/healthz?x=1#fragment",
        f"ws://127.0.0.1:{port}/_stcore/stream",
        "data:text/plain,owned",
        "about:blank",
    )
    for url in allowed:
        require(matrix.is_allowed_browser_url(url, port), f"owned URL denied: {url}")
    denied = (
        "http://127.0.0.1:8000/api/schedules",
        f"http://localhost:{port}/",
        f"http://[::1]:{port}/",
        f"http://user:secret@127.0.0.1:{port}/",
        "https://example.com/",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "http://127.0.0.1:bad/",
    )
    for url in denied:
        require(not matrix.is_allowed_browser_url(url, port), f"unowned URL allowed: {url}")
    require(
        matrix.safe_url_label("https://user:secret@example.com/private?q=token")
        == "https://example.com/private",
        "safe URL label leaked credentials/query",
    )


def test_source_digest_covers_theme_runtime_projection() -> None:
    first = matrix.source_digest()
    second = matrix.source_digest()
    require(first == second and len(first) == 64, "source digest is unstable")
    source = (ROOT / "scripts" / "ui_ux_theme_matrix.py").read_text(encoding="utf-8")
    for required in (
        "sourceDigestStart",
        "sourceDigestEnd",
        "expectedCapturesPerBrowser",
        "is_allowed_browser_url",
        "validate_focus_adjacency",
        "THEME_SELECTOR_CONTRACT",
        "route_web_socket",
        "device_scale_factor=1",
        "OwnedDenyProxy",
        "calibrate_darwin_sandbox_contract",
        "pythonSocketGuard",
        "credentialFree",
    ):
        require(required in source, f"runner source contract missing: {required}")
    for forbidden in ("time.sleep(60", "killall", "pkill", "--server.port 8501"):
        require(forbidden not in source, f"runner gained unsafe lifecycle behavior: {forbidden}")


def test_exact_selector_node_observation_rejects_extra_or_orphan_nodes() -> None:
    selector = '[data-testid="stButton"] button[kind="primary"]'
    owner = matrix.owner_id("canvas", "primary")
    good = ({"owner": owner, "node": f"{owner}::0"},)
    matrix._assert_selector_observation(
        selector=selector,
        rows=good,
        expected_owners=(owner,),
    )
    raises_contract(lambda: matrix._assert_selector_observation(
        selector=selector,
        rows=(*good, {"owner": owner, "node": f"{owner}::1"}),
        expected_owners=(owner,),
    ))
    raises_contract(lambda: matrix._assert_selector_observation(
        selector=selector,
        rows=({"owner": None, "node": None},),
        expected_owners=(owner,),
    ))


def test_network_counter_manifest_has_exact_http_and_websocket_fields() -> None:
    counter = matrix._network_counter("chromium", "mobile")
    counter["allowedHttp"] = 4
    counter["allowedWebSocket"] = 1
    counter["allowedUrls"].update({"http://127.0.0.1:1/", "ws://127.0.0.1:1/_stcore/stream"})
    row = matrix._finalize_network_counter(counter)
    require(row["allowedHttp"] == 4 and row["allowedWebSocket"] == 1, "allowed counters")
    require(row["blockedHttp"] == 0 and row["blockedWebSocket"] == 0, "blocked counters")
    require(row["allowedUrls"] == sorted(row["allowedUrls"]), "canonical URL order")
    proxy = matrix._safe_proxy_attempt_evidence(({
        "bytes": 99,
        "request": "GET https://user:secret@example.invalid/private?token=sensitive HTTP/1.1",
    },))
    encoded = json.dumps(proxy)
    require(proxy == [{"bytes": 99, "method": "GET"}], "proxy evidence schema")
    for secret in ("user", "secret", "example.invalid", "token", "sensitive"):
        require(secret not in encoded, f"proxy evidence leaked {secret}")


def test_child_environment_is_credential_free_private_and_exact_proxy() -> None:
    matrix.UX1B_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=matrix.UX1B_ROOT) as raw:
        owned = matrix.create_owned_run(Path(raw))
        contract = matrix.ThemeNetworkContract(43121, 43122)
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "sk-sensitive-sentinel",
            "DATABASE_URL": "postgres://user:password@example.invalid/private",
            "AUTHORIZATION": "Bearer sensitive-sentinel",
            "HTTP_PROXY": "http://user:password@example.invalid:8080",
            "RANDOM_PARENT_VALUE": "must-not-cross-boundary",
        }, clear=False):
            environment = matrix._theme_child_environment(owned, contract)
        encoded = json.dumps(environment, sort_keys=True)
        for forbidden in (
            "OPENAI_API_KEY", "DATABASE_URL", "AUTHORIZATION",
            "RANDOM_PARENT_VALUE", "sensitive-sentinel", "example.invalid",
        ):
            require(forbidden not in encoded, f"child environment leaked {forbidden}")
        proxy = "http://127.0.0.1:43122"
        for key in (
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
            "http_proxy", "https_proxy", "all_proxy",
        ):
            require(environment[key] == proxy, f"{key} is not the owned deny proxy")
        evidence = matrix._child_environment_evidence(environment, owned)
        expected_keys = {
            key for key in os.environ
            if key in matrix._CHILD_ENV_KEYS or key.startswith("LC_")
        } | set(matrix._THEME_FIXED_CHILD_KEYS)
        require(set(environment) == expected_keys, "child allowlist is not exact")
        require(evidence["credentialFree"], "credential-free evidence")
        require(evidence["privateDirectories"], "private directory evidence")
        require(evidence["proxyContractExact"], "proxy evidence")


def test_python_guard_allows_only_two_exact_owned_endpoints() -> None:
    matrix.UX1B_ROOT.mkdir(parents=True, exist_ok=True)
    listeners: list[socket.socket] = []
    for _index in range(3):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(2)
        listener.settimeout(0.2)
        listeners.append(listener)
    first, second, dummy = listeners
    contract = matrix.ThemeNetworkContract(
        int(first.getsockname()[1]), int(second.getsockname()[1])
    )
    try:
        require(matrix.is_allowed_python_endpoint("127.0.0.1", contract.streamlit_port, contract), "Streamlit port denied")
        require(matrix.is_allowed_python_endpoint(b"127.0.0.1", contract.deny_proxy_port, contract), "deny proxy denied")
        for host, port in (
            ("localhost", contract.streamlit_port),
            ("::1", contract.streamlit_port),
            ("127.0.0.1", 8000),
            ("127.0.0.1", int(dummy.getsockname()[1])),
            ("203.0.113.1", 9),
        ):
            require(
                not matrix.is_allowed_python_endpoint(host, port, contract),
                f"unowned endpoint allowed: {host}:{port}",
            )

        with tempfile.TemporaryDirectory(dir=matrix.UX1B_ROOT) as raw:
            owned = matrix.create_owned_run(Path(raw))
            environment = matrix._theme_child_environment(owned, contract)
            child = r'''
import json
import socket
import sys
from scripts.ui_ux_theme_matrix import ThemeChildNetworkDenied, install_theme_child_network_guard

streamlit_port, proxy_port, dummy_port = map(int, sys.argv[1:])
install_theme_child_network_guard()
for port in (streamlit_port, proxy_port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(1.0)
        client.connect(("127.0.0.1", port))
denied = []
for family, target in (
    (socket.AF_INET, ("localhost", streamlit_port)),
    (socket.AF_INET6, ("::1", streamlit_port)),
    (socket.AF_INET, ("127.0.0.1", 8000)),
    (socket.AF_INET, ("127.0.0.1", dummy_port)),
    (socket.AF_INET, ("203.0.113.1", 9)),
):
    try:
        with socket.socket(family, socket.SOCK_STREAM) as client:
            client.connect(target)
    except ThemeChildNetworkDenied:
        denied.append(target[0])
    else:
        raise SystemExit("unowned socket destination escaped guard")
try:
    socket.getaddrinfo("example.com", 443)
except ThemeChildNetworkDenied:
    denied.append("dns")
else:
    raise SystemExit("external DNS escaped guard")
print(json.dumps({"denied": denied}, sort_keys=True))
'''
            completed = subprocess.run(
                [
                    sys.executable, "-c", child,
                    str(contract.streamlit_port), str(contract.deny_proxy_port),
                    str(dummy.getsockname()[1]),
                ],
                cwd=ROOT,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=False,
            )
            require(completed.returncode == 0, f"guard child failed: {completed.stderr}")
            require(len(json.loads(completed.stdout)["denied"]) == 6, "denial matrix")
            evidence = matrix._read_child_guard_evidence(
                Path(environment[matrix._CHILD_GUARD_PATH])
            )
            require(evidence["allowedAttemptCount"] == 2, "exact owned connections")
            require(evidence["blockedAttemptCount"] == 6, "exact denied attempts")
            require(evidence["attemptCount"] == 8, "exact guard attempt count")
        for listener in (first, second):
            connection, _address = listener.accept()
            connection.close()
        try:
            connection, _address = dummy.accept()
        except socket.timeout:
            pass
        else:
            connection.close()
            raise AssertionError("dummy listener received a guarded connection")
    finally:
        for listener in listeners:
            listener.close()


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"PASS all {len(tests)} UX-1B theme matrix tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
