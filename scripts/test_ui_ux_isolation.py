#!/usr/bin/env python3
"""Red contracts for the UX-1B source mirror and dual Seatbelt boundary.

These tests intentionally import the planned ``scripts.ui_ux_isolation``
module.  Task 1 is red until Task 2 supplies that implementation; failures
must come from the missing or incomplete isolation contract, not from this
test file's syntax.
"""

from __future__ import annotations

import contextlib
import copy
import errno
import hashlib
import json
import os
import select
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import ui_ux_isolation as isolation  # noqa: E402


MIRROR_SCHEMA = "quant-radar-ui-ux-ux1b-source-mirror/v1"
CALIBRATION_SCHEMA = "quant-radar-ui-ux-ux1b-isolation-calibration/v1"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def raises_isolation(callable_) -> BaseException:
    try:
        callable_()
    except isolation.IsolationContractError as exc:
        return exc
    raise AssertionError("isolation contract accepted an unsafe input")


def raises_dependency(callable_) -> BaseException:
    try:
        callable_()
    except isolation.DependencyUnavailable as exc:
        return exc
    raise AssertionError("unsupported isolation backend did not fail closed")


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _workspace_fixture(root: Path) -> tuple[str, ...]:
    included = (
        "app.py",
        "requirements.txt",
        ".streamlit/config.toml",
        "ui/__init__.py",
        "ui/page.py",
        "scripts/fixture.py",
        "scripts/ui_ux_browser_worker.py",
        "api/main.py",
    )
    for relative in included:
        _write(root / relative, f"# fixed source: {relative}\n")
    for relative in (
        ".env",
        ".git/config",
        ".agents/private.md",
        ".claude/ui_snapshots/ux1b/manifest.json",
        "data/production.json",
        "reports/private.json",
        "__pycache__/app.cpython-311.pyc",
        "ui/__pycache__/page.cpython-311.pyc",
        "runtime/chat/session.json",
    ):
        _write(root / relative, "SECRET-MUST-NOT-CROSS\n")
    return included


def _mirror_policy() -> object:
    return isolation.SourceMirrorPolicy(
        include=(
            "app.py",
            "requirements.txt",
            ".streamlit/config.toml",
            "ui",
            "scripts",
            "api",
        ),
        exclude=(
            ".git",
            ".claude",
            ".agents",
            ".env",
            "data",
            "reports",
            "runtime",
            "__pycache__",
        ),
    )


def _regular_file_mode(path: Path) -> int:
    return stat.S_IMODE(path.stat(follow_symlinks=False).st_mode)


def _owned_run_path(value: object) -> Path:
    path = value if isinstance(value, Path) else getattr(value, "path", None)
    require(isinstance(path, Path), "owned run root does not expose a Path")
    return path


def _tree_snapshot(root: Path) -> tuple[tuple[str, str, int, bytes], ...]:
    rows: list[tuple[str, str, int, bytes]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        observed = path.lstat()
        relative = path.relative_to(root).as_posix()
        mode = stat.S_IMODE(observed.st_mode)
        if stat.S_ISDIR(observed.st_mode):
            rows.append((relative, "directory", mode, b""))
        elif stat.S_ISREG(observed.st_mode):
            rows.append((relative, "file", mode, path.read_bytes()))
        elif stat.S_ISLNK(observed.st_mode):
            rows.append((relative, "symlink", mode, os.readlink(path).encode("utf-8")))
        else:
            rows.append((relative, "special", mode, b""))
    return tuple(rows)


def _passing_probe_raw(
    allowed_names: frozenset[str], denied_names: frozenset[str]
) -> dict[str, object]:
    details = {
        name: {"errno": errno.EBADF if name == "productionFdRead" else errno.EPERM}
        for name in denied_names
    }
    return {
        "allowed": {name: True for name in allowed_names},
        "denied": {name: True for name in denied_names},
        "details": details,
        "observations": {
            "acceptedBytes": 1,
            "assignedPortBytes": 1,
            "deniedListenerBytes": 0,
            "productionFdBytes": 0,
            "unexpectedContacts": [],
        },
    }


def _process_ids_with_marker(marker: str) -> set[int]:
    completed = subprocess.run(
        ("/bin/ps", "-axo", "pid=,command="),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    result: set[int] = set()
    for row in completed.stdout.splitlines():
        pid_text, _separator, command = row.strip().partition(" ")
        if marker in command:
            result.add(int(pid_text))
    return result


def _wait_for_marker_processes(marker: str, *, timeout: float = 3.0) -> set[int]:
    deadline = time.monotonic() + timeout
    while True:
        remaining = _process_ids_with_marker(marker)
        if not remaining or time.monotonic() >= deadline:
            return remaining
        time.sleep(0.05)


def _cleanup_test_processes(process_ids: set[int]) -> None:
    for pid in process_ids:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(pid, signal.SIGKILL)
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGKILL)


def _make_mirror(workspace: Path, run_root: Path):
    return isolation.build_source_mirror(
        workspace_root=workspace,
        run_root=run_root,
        policy=_mirror_policy(),
    )


def _test_family_identity(
    *,
    session_id: str,
    process_id: str,
    role: str,
    process_token: str | None = None,
):
    token = process_token or isolation._new_process_token()
    return isolation._ProcessFamilyIdentity(
        session_id=session_id,
        process_id=process_id,
        process_token=token,
        role=role,
        launch_identity_sha256=hashlib.sha256(
            f"{session_id}\0{role}\0{process_id}\0{token}".encode("utf-8")
        ).hexdigest(),
        owner_uid=os.getuid(),
    )


def _spawn_process_family(
    command,
    *,
    session_id: str,
    process_id: str,
    role: str = "browser",
    stdout=subprocess.DEVNULL,
):
    identity = _test_family_identity(
        session_id=session_id,
        process_id=process_id,
        role=role,
    )
    registration = isolation._reserve_process_family(identity)
    environment = dict(os.environ)
    environment[isolation.PROCESS_TOKEN_ENV_KEY] = identity.process_token
    try:
        process = subprocess.Popen(
            tuple(command),
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=subprocess.DEVNULL,
            env=environment,
            close_fds=True,
            pass_fds=(),
            start_new_session=True,
        )
    except BaseException:
        isolation._release_reserved_process_family(registration)
        raise
    try:
        isolation._attach_process_family(registration, process)
    except BaseException:
        try:
            isolation._cleanup_unregistered_process(process, registration)
        finally:
            isolation._release_process_family(registration)
        raise
    return process, registration


def test_source_mirror_is_exact_stable_read_only_and_new_inode() -> None:
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        workspace = base / "workspace"
        workspace.mkdir(mode=0o700)
        included = _workspace_fixture(workspace)

        first = _make_mirror(workspace, base / "run-one")
        second = _make_mirror(workspace, base / "run-two")

        require(first.source_root.is_dir(), "source mirror root is missing")
        require(first.manifest_path.is_file(), "source mirror manifest is missing")
        require(first.digest == second.digest, "mirror digest depends on run path")
        require(
            len(first.digest) == 64
            and all(character in "0123456789abcdef" for character in first.digest),
            "mirror digest is not canonical SHA-256",
        )

        manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
        require(manifest["schemaVersion"] == MIRROR_SCHEMA, "mirror schema differs")
        require(manifest["digest"] == first.digest, "manifest digest differs")
        require(
            [row["path"] for row in manifest["files"]] == sorted(included),
            "mirror file projection is not exact and sorted",
        )
        encoded = json.dumps(manifest, sort_keys=True)
        require(str(workspace) not in encoded, "manifest leaked original workspace path")
        require("SECRET-MUST-NOT-CROSS" not in encoded, "manifest leaked excluded data")

        for relative in included:
            source = workspace / relative
            copied = first.source_root / relative
            require(copied.is_file(), f"allowlisted source missing: {relative}")
            source_stat = source.stat(follow_symlinks=False)
            copied_stat = copied.stat(follow_symlinks=False)
            require(
                (source_stat.st_dev, source_stat.st_ino)
                != (copied_stat.st_dev, copied_stat.st_ino),
                f"source mirror reused source inode: {relative}",
            )
            require(copied_stat.st_nlink == 1, f"mirror file is linked: {relative}")
            require(
                stat.S_IMODE(copied_stat.st_mode) & 0o222 == 0,
                f"mirror file remains writable: {relative}",
            )
            require(
                source.read_bytes() == copied.read_bytes(),
                f"mirror bytes differ: {relative}",
            )

        for relative in (
            ".env",
            ".git",
            ".agents",
            ".claude",
            "data",
            "reports",
            "runtime",
            "__pycache__",
            "ui/__pycache__",
        ):
            require(
                not (first.source_root / relative).exists(),
                f"excluded runtime root crossed mirror: {relative}",
            )
        for directory in (
            first.source_root,
            first.source_root / "ui",
            first.source_root / "scripts",
            first.source_root / "api",
            first.source_root / ".streamlit",
        ):
            require(
                _regular_file_mode(directory) & 0o222 == 0,
                f"mirror directory remains writable: {directory.name}",
            )

        verified = isolation.authenticate_source_mirror(
            first,
            expected_digest=first.digest,
        )
        require(verified["passed"] is True, "fresh source mirror did not authenticate")
        require(verified["fileCount"] == len(included), "authenticated count differs")

        victim = first.source_root / "ui" / "page.py"
        os.chmod(victim, 0o600)
        victim.write_text("# mutated after mirror finalization\n", encoding="utf-8")
        raises_isolation(
            lambda: isolation.authenticate_source_mirror(
                first,
                expected_digest=first.digest,
            )
        )


def test_source_mirror_fd_authority_ignores_replacement_path() -> None:
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        workspace = base / "workspace"
        workspace.mkdir(mode=0o700)
        _workspace_fixture(workspace)
        original_app = (workspace / "app.py").read_bytes()
        workspace_fd = os.open(workspace, isolation._SAFE_DIRECTORY_FLAGS)
        try:
            workspace.rename(base / "detached-workspace")
            replacement = base / "workspace"
            replacement.mkdir(mode=0o700)
            _workspace_fixture(replacement)
            (replacement / "app.py").write_text(
                "# replacement path must not be mirrored\n", encoding="utf-8"
            )
            mirror = isolation.build_source_mirror(
                workspace_root_fd=workspace_fd,
                run_root=base / "fd-run",
                policy=_mirror_policy(),
            )
            require(
                (mirror.source_root / "app.py").read_bytes() == original_app,
                "source mirror followed a replacement workspace pathname",
            )
            raises_isolation(
                lambda: isolation.build_source_mirror(
                    run_root=base / "missing-authority",
                    policy=_mirror_policy(),
                )
            )
            raises_isolation(
                lambda: isolation.build_source_mirror(
                    workspace_root=replacement,
                    workspace_root_fd=workspace_fd,
                    run_root=base / "two-authorities",
                    policy=_mirror_policy(),
                )
            )
        finally:
            os.close(workspace_fd)


def _unsafe_workspace(kind: str, base: Path) -> tuple[Path, object]:
    workspace = base / f"workspace-{kind}"
    workspace.mkdir(mode=0o700)
    _workspace_fixture(workspace)
    unsafe = workspace / "ui" / f"unsafe_{kind}.py"
    if kind == "symlink":
        unsafe.symlink_to(workspace / "data" / "production.json")
    elif kind == "hardlink":
        os.link(workspace / "app.py", unsafe)
    elif kind == "fifo":
        os.mkfifo(unsafe, 0o600)
    elif kind == "socket":
        unix_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        unix_socket.bind(str(unsafe))
        return workspace, unix_socket
    else:  # pragma: no cover - the closed test catalog controls this helper.
        raise AssertionError(kind)
    return workspace, None


def test_source_mirror_rejects_symlink_hardlink_fifo_and_socket() -> None:
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        for kind in ("symlink", "hardlink", "fifo", "socket"):
            workspace, resource = _unsafe_workspace(kind, base)
            try:
                error = raises_isolation(
                    lambda workspace=workspace, kind=kind: _make_mirror(
                        workspace,
                        base / f"run-{kind}",
                    )
                )
                require(kind in str(error).casefold(), f"{kind} failure is not classified")
            finally:
                if resource is not None:
                    resource.close()


def test_source_mirror_rejects_escaping_or_ambiguous_policy_paths() -> None:
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        workspace = base / "workspace"
        workspace.mkdir(mode=0o700)
        _workspace_fixture(workspace)
        policies = (
            isolation.SourceMirrorPolicy(include=("../outside.py",), exclude=()),
            isolation.SourceMirrorPolicy(include=(str((base / "absolute.py").resolve()),), exclude=()),
            isolation.SourceMirrorPolicy(include=("ui//page.py",), exclude=()),
            isolation.SourceMirrorPolicy(include=("ui/./page.py",), exclude=()),
            isolation.SourceMirrorPolicy(include=("ui/page.py", "ui/page.py"), exclude=()),
        )
        for index, policy in enumerate(policies):
            raises_isolation(
                lambda policy=policy, index=index: isolation.build_source_mirror(
                    workspace_root=workspace,
                    run_root=base / f"unsafe-policy-{index}",
                    policy=policy,
                )
            )


def _child_environment(role: str, source_root: Path, writable_root: Path) -> dict[str, str]:
    parent = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
        "OPENAI_API_KEY": "sk-production-secret",
        "DATABASE_URL": "sqlite:////production/private.db",
        "AUTHORIZATION": "Bearer production-secret",
        "HTTP_PROXY": "http://user:password@example.invalid:8080",
        "RANDOM_PARENT_VALUE": "must-not-cross",
        "WORKSPACE_ROOT": "/production/workspace",
    }
    return isolation.build_child_environment(
        role=role,
        source_root=source_root,
        writable_root=writable_root,
        inherited=parent,
    )


def test_child_environment_is_allowlisted_private_and_role_scoped() -> None:
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        source = base / "source"
        source.mkdir()
        app_root = base / "app-owned"
        browser_root = base / "browser-owned"
        app_root.mkdir(mode=0o700)
        browser_root.mkdir(mode=0o700)

        app_environment = _child_environment("app", source, app_root)
        browser_environment = _child_environment("browser", source, browser_root)
        required_parent = {"PATH", "LANG", "LC_ALL", "TZ"}
        for role, environment, writable in (
            ("app", app_environment, app_root),
            ("browser", browser_environment, browser_root),
        ):
            require(required_parent <= set(environment), f"{role} locale/path keys missing")
            require(environment["SOURCE_ROOT"] == str(source), f"{role} source root differs")
            require(environment["QUANT_RADAR_UX1B_ROLE"] == role, f"{role} marker differs")
            require(environment["PYTHONNOUSERSITE"] == "1", f"{role} user site is enabled")
            require(environment["PYTHONDONTWRITEBYTECODE"] == "1", f"{role} writes bytecode")
            require(Path(environment["HOME"]).is_relative_to(writable), f"{role} HOME escaped")
            require(Path(environment["TMPDIR"]).is_relative_to(writable), f"{role} TMPDIR escaped")
            if role == "browser":
                require(
                    Path(environment["MAC_CHROMIUM_TMPDIR"]).is_relative_to(writable),
                    "browser Chromium temp escaped",
                )
            else:
                require("MAC_CHROMIUM_TMPDIR" not in environment, "app knows Chromium temp")
            require(
                set(environment) == set(isolation.CHILD_ENV_KEYS[role]),
                f"{role} child environment allowlist is not exact",
            )
            encoded = json.dumps(environment, sort_keys=True)
            for forbidden in (
                "OPENAI_API_KEY",
                "DATABASE_URL",
                "AUTHORIZATION",
                "RANDOM_PARENT_VALUE",
                "production-secret",
                "example.invalid",
                "/production/workspace",
            ):
                require(forbidden not in encoded, f"{role} environment leaked {forbidden}")
        require(str(browser_root) not in json.dumps(app_environment), "app knows browser root")
        require(str(app_root) not in json.dumps(browser_environment), "browser knows app root")


def test_child_spawn_closes_descriptors_and_uses_owned_stdio() -> None:
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        source = base / "source"
        source.mkdir()
        writable = base / "app-owned"
        writable.mkdir(mode=0o700)
        environment = _child_environment("app", source, writable)

        with isolation.owned_child_stdio(base / "stdio", role="app") as stdio:
            kwargs = isolation.child_popen_kwargs(
                cwd=source,
                environment=environment,
                stdio=stdio,
            )
            require(kwargs["close_fds"] is True, "child inherited arbitrary descriptors")
            require(kwargs["pass_fds"] == (), "child pass_fds is not empty")
            require(kwargs["start_new_session"] is True, "child lacks an owned process group")
            require(Path(kwargs["cwd"]) == source, "child cwd is not SOURCE_ROOT")
            require(kwargs["env"] == environment, "child environment was widened")
            for stream_name in ("stdin", "stdout", "stderr"):
                stream = kwargs[stream_name]
                stream_path = Path(stream.name).resolve()
                require(
                    stream_path.is_relative_to((base / "stdio").resolve()),
                    f"{stream_name} is not runner-owned",
                )
                stream_stat = os.fstat(stream.fileno())
                require(stat.S_ISREG(stream_stat.st_mode), f"{stream_name} is not regular")
                require(stream_stat.st_nlink == 1, f"{stream_name} is linked")
                require(
                    stat.S_IMODE(stream_stat.st_mode) & 0o077 == 0,
                    f"{stream_name} permissions are not private",
                )

            fake_process = SimpleNamespace(pid=43210)
            command = (sys.executable, "-c", "raise SystemExit(0)")
            raises_isolation(
                lambda: isolation.spawn_owned_child(
                    command,
                    cwd=source,
                    environment=environment,
                    stdio=stdio,
                )
            )
            with patch.object(isolation.subprocess, "Popen", return_value=fake_process) as popen:
                result = isolation.spawn_owned_child(
                    command,
                    cwd=source,
                    environment=environment,
                    stdio=stdio,
                    test_only=True,
                )
            require(result is fake_process, "spawn wrapper did not return owned child")
            require(popen.call_count == 1, "spawn wrapper did not call Popen exactly once")
            positional, actual_kwargs = popen.call_args
            require(tuple(positional[0]) == command, "spawn command differs")
            for key, value in kwargs.items():
                require(actual_kwargs.get(key) == value, f"spawn widened or dropped {key}")


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _chromium_executable() -> Path:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - dependency gate classifies this.
        raise isolation.DependencyUnavailable("Playwright is unavailable") from exc
    with sync_playwright() as playwright:
        executable = Path(playwright.chromium.executable_path)
    if not executable.is_file():
        raise isolation.DependencyUnavailable("Playwright Chromium is unavailable")
    return executable


def _darwin_contract(base: Path):
    workspace = base / "original-workspace"
    workspace.mkdir(mode=0o700)
    _workspace_fixture(workspace)
    run_root = base / "run"
    run_root.mkdir(mode=0o700)
    mirror = _make_mirror(workspace, run_root / "mirror-build")
    app_root = run_root / "app"
    browser_root = run_root / "browser"
    final_root = run_root / "final"
    for root in (app_root, browser_root, final_root):
        root.mkdir(mode=0o700)
    app_port = _free_loopback_port()
    denied_port = _free_loopback_port()
    while denied_port == app_port:
        denied_port = _free_loopback_port()
    production_probe = workspace / "data" / "production.json"
    return isolation.DarwinIsolationContract(
        workspace_root=workspace,
        source_root=mirror.source_root,
        app_writable_root=app_root,
        browser_writable_root=browser_root,
        final_evidence_root=final_root,
        python_executable=Path(sys.executable).resolve(),
        python_runtime_roots=(Path(sys.prefix).resolve(),),
        browser_executable=_chromium_executable(),
        browser_runtime_roots=(Path.home() / "Library" / "Caches" / "ms-playwright",),
        production_probe_path=production_probe,
        app_port=app_port,
        denied_port=denied_port,
    )


def _sandbox_run(profile: str, command: tuple[str, ...], *, environment: dict[str, str]):
    return subprocess.run(
        (str(isolation.SANDBOX_EXEC), "-p", profile, *command),
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=True,
        timeout=10.0,
        check=False,
    )


def test_profiles_deny_ambient_home_reads_and_browser_arbitrary_exec() -> None:
    if sys.platform != "darwin":
        return
    with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory(
        prefix="ux1b-ambient-", dir=Path.home()
    ) as ambient_raw:
        contract = _darwin_contract(Path(raw))
        profiles = isolation.build_darwin_profiles(contract)
        require(
            "(deny file-read-data" in profiles.app,
            "app profile lacks a default file-read-data denial",
        )
        require(
            "(deny file-read-data" in profiles.browser,
            "browser profile lacks a default file-read-data denial",
        )
        require(
            "(deny process-exec)" in profiles.browser,
            "browser profile lacks a default process-exec denial",
        )
        sentinel = Path(ambient_raw) / "sentinel.txt"
        sentinel.write_text("AMBIENT-SECRET\n", encoding="utf-8")
        os.chmod(sentinel, 0o600)

        for role, profile, writable in (
            ("app", profiles.app, contract.app_writable_root),
            ("browser", profiles.browser, contract.browser_writable_root),
        ):
            environment = isolation.build_child_environment(
                role=role,
                source_root=contract.source_root,
                writable_root=writable,
                inherited=os.environ,
            )
            attempted_read = _sandbox_run(
                profile,
                (
                    str(contract.python_executable),
                    "-c",
                    "from pathlib import Path; Path(__import__('sys').argv[1]).read_bytes()",
                    str(sentinel),
                ),
                environment=environment,
            )
            require(
                attempted_read.returncode != 0 and b"AMBIENT-SECRET" not in attempted_read.stdout,
                f"{role} profile read an ambient home sentinel",
            )

        arbitrary_exec = _sandbox_run(
            profiles.browser,
            ("/usr/bin/true",),
            environment=isolation.build_child_environment(
                role="browser",
                source_root=contract.source_root,
                writable_root=contract.browser_writable_root,
                inherited=os.environ,
            ),
        )
        require(arbitrary_exec.returncode != 0, "browser profile executed /usr/bin/true")


def test_contract_rejects_unsafe_root_hierarchy_and_runtime_ancestors() -> None:
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        run_parent = base / "owned-runs"
        run_parent.mkdir(mode=0o700)
        collision = run_parent / f"ux1b-run-{'a' * 32}"
        collision.mkdir(mode=0o700)
        _write(collision / "owner.txt", "must-survive-collision\n")
        with patch.object(
            isolation.secrets,
            "token_hex",
            side_effect=("a" * 32, "b" * 32),
        ):
            first_handle = isolation.create_owned_run_root(parent=run_parent)
        second_handle = isolation.create_owned_run_root(parent=run_parent)
        first = _owned_run_path(first_handle)
        second = _owned_run_path(second_handle)
        require(first != second, "owned run-root allocation collided")
        require(
            (collision / "owner.txt").read_text(encoding="utf-8")
            == "must-survive-collision\n",
            "owned run-root allocation reused an existing collision",
        )
        for run_root in (first, second):
            require(run_root.parent == run_parent, "owned run root escaped its parent")
            require(run_root.is_dir(), "owned run root was not created")
            require(_regular_file_mode(run_root) == 0o700, "owned run root is not 0700")
        for handle in (first_handle, second_handle):
            close = getattr(handle, "close", None)
            require(callable(close), "owned run root lacks descriptor cleanup")
            close()

        if sys.platform != "darwin":
            return
        contract = _darwin_contract(base)
        run_root = contract.app_writable_root.parent

        os.chmod(run_root, 0o755)
        raises_isolation(lambda: isolation.build_darwin_profiles(contract))
        os.chmod(run_root, 0o700)

        production_root = contract.workspace_root / "data"
        os.chmod(production_root, 0o700)
        raises_isolation(
            lambda: isolation.build_darwin_profiles(
                replace(contract, app_writable_root=production_root)
            )
        )
        nested_browser = contract.app_writable_root / "nested-browser"
        nested_browser.mkdir(mode=0o700)
        raises_isolation(
            lambda: isolation.build_darwin_profiles(
                replace(contract, browser_writable_root=nested_browser)
            )
        )

        unsafe_run = contract.workspace_root / "unsafe-run"
        roots = [unsafe_run / name for name in ("source", "app", "browser", "final")]
        for root in roots:
            root.mkdir(parents=True, mode=0o700)
        raises_isolation(
            lambda: isolation.build_darwin_profiles(
                replace(
                    contract,
                    source_root=roots[0],
                    app_writable_root=roots[1],
                    browser_writable_root=roots[2],
                    final_evidence_root=roots[3],
                )
            )
        )

        user_secret = base / "user-secret"
        user_secret.mkdir(mode=0o700)
        unsafe_runtime_variants = (
            replace(contract, python_runtime_roots=(Path("/"),)),
            replace(contract, browser_runtime_roots=(Path.home(),)),
            replace(contract, python_runtime_roots=(contract.workspace_root,)),
            replace(contract, browser_runtime_roots=(run_root,)),
            replace(contract, python_runtime_roots=(user_secret,)),
            replace(contract, browser_runtime_roots=(user_secret,)),
            replace(
                contract,
                browser_runtime_roots=(run_root / "coordinator-private",),
            ),
        )
        (run_root / "coordinator-private").mkdir(mode=0o700)
        for unsafe in unsafe_runtime_variants:
            raises_isolation(lambda unsafe=unsafe: isolation.build_darwin_profiles(unsafe))

        current_uid = os.getuid()
        with patch.object(isolation.os, "getuid", return_value=current_uid + 1):
            raises_isolation(lambda: isolation.build_darwin_profiles(contract))


def test_owned_run_lease_and_bounded_stale_claims_are_descriptor_safe() -> None:
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        active_parent = base / "active"
        active_parent.mkdir(mode=0o700)
        prefix = "quant-radar-ux1b-"
        with patch.object(isolation.secrets, "token_hex", return_value="a" * 32):
            active_root = isolation.create_owned_run_root(
                active_parent,
                prefix=prefix,
            )
        lease = isolation.acquire_owned_run_lease(active_root)
        lease_path = active_root.path / isolation.OWNED_RUN_LEASE_NAME
        observed = lease_path.stat(follow_symlinks=False)
        require(stat.S_ISREG(observed.st_mode), "lease is not a regular file")
        require(observed.st_nlink == 1, "lease is hard-linked")
        require(stat.S_IMODE(observed.st_mode) == 0o600, "lease is not mode 0600")
        require(
            not os.get_inheritable(lease.descriptor),
            "lease descriptor is inheritable across exec",
        )
        raises_isolation(lambda: isolation.acquire_owned_run_lease(active_root))

        active_claims = isolation.claim_stale_owned_run_roots(
            active_parent,
            prefix=prefix,
        )
        require(active_claims == (), "active lease was classified stale")

        source = active_root.path / "source.bin"
        source.write_bytes(b"nonterminal-source-must-not-change")
        source_before = _tree_snapshot(active_root.path)
        lease.close()  # Simulates the automatic lease release after SIGKILL.
        stale_claims = isolation.claim_stale_owned_run_roots(
            active_parent,
            prefix=prefix,
        )
        require(len(stale_claims) == 1, "released lease was not claimed stale")
        claim = stale_claims[0]
        require(claim.root.leaf_name == active_root.leaf_name, "wrong root was claimed")
        require(
            _tree_snapshot(active_root.path) == source_before,
            "stale claim mutated its source root",
        )
        concurrent_claims = isolation.claim_stale_owned_run_roots(
            active_parent,
            prefix=prefix,
        )
        require(concurrent_claims == (), "one stale root was claimed concurrently")
        claim.close()
        reclaimed = isolation.claim_stale_owned_run_roots(
            active_parent,
            prefix=prefix,
        )
        require(len(reclaimed) == 1, "closed stale claim did not release its lock")
        require(
            not os.get_inheritable(reclaimed[0].lease.descriptor),
            "claimed lease descriptor is inheritable across exec",
        )
        reclaimed[0].close()

        child_script = (
            "import fcntl, os, sys, time; "
            "fd=os.open(sys.argv[1], os.O_RDWR); "
            "fcntl.flock(fd, fcntl.LOCK_EX); "
            "print('locked', flush=True); time.sleep(30)"
        )
        for _iteration in range(2):
            child = subprocess.Popen(
                (sys.executable, "-c", child_script, str(lease_path)),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                close_fds=True,
            )
            try:
                ready, _write_ready, _errors = select.select(
                    [child.stdout], [], [], 3.0
                )
                require(bool(ready), "multiprocess lease holder did not become ready")
                require(child.stdout.readline().strip() == "locked", "child lock failed")
                require(
                    isolation.claim_stale_owned_run_roots(
                        active_parent,
                        prefix=prefix,
                    )
                    == (),
                    "multiprocess active lease was classified stale",
                )
            finally:
                child.kill()
                child.wait(timeout=5)
                child.stdout.close()
                child.stderr.close()
            after_kill = isolation.claim_stale_owned_run_roots(
                active_parent,
                prefix=prefix,
            )
            require(
                len(after_kill) == 1,
                "SIGKILL did not release the multiprocess lease",
            )
            after_kill[0].close()
        isolation.remove_owned_run_root(active_root)

        unsafe_parent = base / "unsafe"
        unsafe_parent.mkdir(mode=0o700)
        target = unsafe_parent / "target"
        target.mkdir(mode=0o700)
        (target / isolation.OWNED_RUN_LEASE_NAME).write_bytes(b"")
        os.chmod(target / isolation.OWNED_RUN_LEASE_NAME, 0o600)
        os.symlink(target, unsafe_parent / f"{prefix}{'b' * 32}")

        wrong_root = unsafe_parent / f"{prefix}{'c' * 32}"
        wrong_root.mkdir(mode=0o755)
        (wrong_root / isolation.OWNED_RUN_LEASE_NAME).write_bytes(b"")
        os.chmod(wrong_root / isolation.OWNED_RUN_LEASE_NAME, 0o600)

        wrong_lease = unsafe_parent / f"{prefix}{'d' * 32}"
        wrong_lease.mkdir(mode=0o700)
        (wrong_lease / isolation.OWNED_RUN_LEASE_NAME).write_bytes(b"")
        os.chmod(wrong_lease / isolation.OWNED_RUN_LEASE_NAME, 0o644)

        linked_lease = unsafe_parent / f"{prefix}{'e' * 32}"
        linked_lease.mkdir(mode=0o700)
        lease_file = linked_lease / isolation.OWNED_RUN_LEASE_NAME
        lease_file.write_bytes(b"")
        os.chmod(lease_file, 0o600)
        os.link(lease_file, linked_lease / "lease-link")

        wrong_prefix = unsafe_parent / f"other-ux1b-{'f' * 32}"
        wrong_prefix.mkdir(mode=0o700)
        (wrong_prefix / isolation.OWNED_RUN_LEASE_NAME).write_bytes(b"")
        os.chmod(wrong_prefix / isolation.OWNED_RUN_LEASE_NAME, 0o600)
        require(
            isolation.claim_stale_owned_run_roots(
                unsafe_parent,
                prefix=prefix,
            )
            == (),
            "unsafe mode, link, symlink, or prefix candidate was claimed",
        )

        bounded_parent = base / "bounded"
        bounded_parent.mkdir(mode=0o700)
        for suffix in ("1" * 32, "2" * 32, "3" * 32):
            (bounded_parent / f"{prefix}{suffix}").mkdir(mode=0o700)
        raises_isolation(
            lambda: isolation.claim_stale_owned_run_roots(
                bounded_parent,
                prefix=prefix,
                max_candidates=2,
            )
        )


def test_dual_profiles_are_distinct_and_least_privilege() -> None:
    if sys.platform != "darwin":
        return
    with tempfile.TemporaryDirectory() as raw:
        contract = _darwin_contract(Path(raw))
        profiles = isolation.build_darwin_profiles(contract)
        require(profiles.app != profiles.browser, "app and browser share one profile")
        require(profiles.app.startswith("(version 1)"), "app profile lacks version")
        require(profiles.browser.startswith("(version 1)"), "browser profile lacks version")

        app = profiles.app
        browser = profiles.browser
        require("process-fork" in app and "process-exec" in app, "app can create processes")
        require("network-bind" in app and str(contract.app_port) in app, "app bind missing")
        require("network-inbound" in app and str(contract.app_port) in app, "app inbound missing")
        require("network-outbound" in app, "app outbound denial missing")
        require("network-outbound" in browser, "browser network boundary missing")
        require(str(contract.app_port) in browser, "browser exact app-port allow missing")
        require(str(contract.denied_port) not in browser, "browser allows denied port")
        require(str(contract.workspace_root) in app, "app production-read denial missing")
        require(str(contract.workspace_root) in browser, "browser production-read denial missing")
        require(str(contract.final_evidence_root) in browser, "browser final-evidence denial missing")
        require(str(contract.app_writable_root) in browser, "browser fixture-read denial missing")
        require(str(contract.browser_writable_root) not in app, "app knows browser writable root")
        require(str(contract.final_evidence_root) not in app, "app knows final evidence root")
        require(
            "com[.]google[.]chrome[.]for[.]testing" not in browser,
            "browser profile still grants global Chromium temp writes",
        )


APP_ALLOWED = frozenset(
    {
        "sourceRead",
        "fixtureWrite",
        "streamlitWrite",
        "temporaryWrite",
        "assignedBind",
        "assignedAccept",
    }
)
APP_DENIED = frozenset(
    {
        "productionPathRead",
        "symlinkTraversalRead",
        "productionFdRead",
        "sourceWrite",
        "writeOutsideRoots",
        "rawFileRead",
        "closureFileRead",
        "closureSqliteRead",
        "fork",
        "exec",
        "assignedOutbound",
        "otherBind",
        "otherLoopbackOutbound",
        "externalOutbound",
        "rawSocketOutbound",
        "socketMroOutbound",
    }
)
BROWSER_ALLOWED = frozenset(
    {
        "sourceRead",
        "captureWrite",
        "cacheWrite",
        "temporaryWrite",
        "chromiumLaunch",
        "chromiumSingletonOwned",
        "chromiumSingletonCleanup",
        "chromiumDomHandshake",
        "assignedConnect",
    }
)
BROWSER_DENIED = frozenset(
    {
        "productionPathRead",
        "symlinkTraversalRead",
        "appFixtureRead",
        "finalEvidenceRead",
        "appFixtureWrite",
        "finalEvidenceWrite",
        "sourceWrite",
        "writeOutsideRoots",
        "exec",
        "otherBind",
        "otherLoopbackOutbound",
        "externalOutbound",
        "rawSocketOutbound",
        "socketMroOutbound",
    }
)


def _assert_probe_matrix(
    row: object,
    *,
    allowed: frozenset[str],
    denied: frozenset[str],
    profile_sha256: str,
) -> None:
    require(row["passed"] is True, "profile calibration did not pass")
    require(row["profileSha256"] == profile_sha256, "calibration used a looser profile")
    require(set(row["allowed"]) == allowed, "positive calibration matrix differs")
    require(set(row["denied"]) == denied, "negative calibration matrix differs")
    require(all(row["allowed"].values()), "a required operation was not allowed")
    require(all(row["denied"].values()), "a prohibited operation escaped")
    require(row["observations"]["deniedListenerBytes"] == 0, "denied listener received bytes")
    require(row["observations"]["productionFdBytes"] == 0, "inherited fd leaked bytes")
    require(row["observations"]["unexpectedContacts"] == [], "undeclared contact occurred")


def test_real_darwin_calibration_covers_bypass_matrix_and_exact_ports() -> None:
    if sys.platform != "darwin":
        return
    with tempfile.TemporaryDirectory() as raw:
        contract = _darwin_contract(Path(raw))
        profiles = isolation.build_darwin_profiles(contract)
        report = isolation.calibrate_darwin_profiles(
            contract,
            profiles=profiles,
            timeout=45.0,
        )
        require(report["schemaVersion"] == CALIBRATION_SCHEMA, "calibration schema differs")
        require(report["capability"] == "supported", "Darwin isolation not supported")
        require(report["passed"] is True, "dual-profile calibration did not pass")
        require(report["platform"] == "darwin", "calibration platform differs")
        require(report["profilesAreDistinct"] is True, "profiles were merged")
        require(report["inheritedFdProbeExplicit"] is True, "inherited-fd bypass untested")
        require(
            isinstance(report.get("launchIdentitySha256"), str)
            and len(report["launchIdentitySha256"]) == 64,
            "calibration runtime identity is missing",
        )
        _assert_probe_matrix(
            report["app"],
            allowed=APP_ALLOWED,
            denied=APP_DENIED,
            profile_sha256=hashlib.sha256(profiles.app.encode("utf-8")).hexdigest(),
        )
        _assert_probe_matrix(
            report["browser"],
            allowed=BROWSER_ALLOWED,
            denied=BROWSER_DENIED,
            profile_sha256=hashlib.sha256(profiles.browser.encode("utf-8")).hexdigest(),
        )
        require(report["app"]["observations"]["acceptedBytes"] > 0, "app did not accept")
        require(report["browser"]["observations"]["assignedPortBytes"] > 0, "browser did not connect")
        require(
            report["browser"]["observations"]["appFixtureProbeRootExact"] is True,
            "browser app-fixture denial did not use the exact app root",
        )
        require(
            report["browser"]["observations"]["finalEvidenceProbeRootExact"] is True,
            "browser final-evidence denial did not use the exact final root",
        )


def test_calibration_uses_private_decoy_without_mutating_workspace_or_final() -> None:
    if sys.platform != "darwin":
        return
    with tempfile.TemporaryDirectory() as raw:
        contract = _darwin_contract(Path(raw))
        workspace_decoy = contract.workspace_root / "data" / "calibration.sqlite3"
        workspace_decoy.write_bytes(b"WORKSPACE-DECOY-MUST-STAY-BYTE-EXACT\n")
        os.chmod(workspace_decoy, 0o400)
        final_sentinel = contract.final_evidence_root / "existing-evidence.bin"
        final_sentinel.write_bytes(b"FINAL-EVIDENCE-MUST-STAY-BYTE-EXACT\n")
        os.chmod(final_sentinel, 0o400)
        before = (
            _tree_snapshot(contract.workspace_root),
            _tree_snapshot(contract.final_evidence_root),
        )
        profiles = isolation.build_darwin_profiles(contract)
        report = isolation.calibrate_darwin_profiles(contract, profiles=profiles)
        after = (
            _tree_snapshot(contract.workspace_root),
            _tree_snapshot(contract.final_evidence_root),
        )
        require(report["passed"] is True, "private-decoy calibration did not pass")
        require(after == before, "calibration mutated workspace or final evidence bytes")


def test_browser_identity_rejects_true_and_real_chromium_proves_dom_handshake() -> None:
    if sys.platform != "darwin":
        return
    with tempfile.TemporaryDirectory() as raw:
        contract = _darwin_contract(Path(raw))
        fake = replace(
            contract,
            browser_executable=Path("/usr/bin/true"),
            browser_runtime_roots=(Path("/usr/bin"),),
        )
        raises_dependency(lambda: isolation.build_darwin_profiles(fake))
        profiles = isolation.build_darwin_profiles(contract)
        report = isolation.calibrate_darwin_profiles(contract, profiles=profiles)
        browser = report["browser"]
        require(
            browser["allowed"].get("chromiumDomHandshake") is True,
            "real Chromium did not prove a DOM handshake",
        )
        require(
            browser["observations"].get("domHandshake") is True,
            "DOM handshake evidence is missing",
        )


def test_probe_oracle_rejects_unexpected_exception_and_uses_raw_socket() -> None:
    for script_name in ("_APP_CALIBRATION_SCRIPT", "_BROWSER_CALIBRATION_SCRIPT"):
        script = getattr(isolation, script_name)
        require("import _socket" in script, f"{script_name} does not import raw _socket")
        require("_socket.socket(" in script, f"{script_name} does not exercise raw _socket")

    raw = _passing_probe_raw(APP_ALLOWED, APP_DENIED)
    details = dict(raw["details"])
    details["rawSocketOutbound"] = {"type": "NameError"}
    raw["details"] = details
    raises_isolation(
        lambda: isolation._finalize_probe_row(
            raw,
            profile="profile",
            allowed_names=APP_ALLOWED,
            denied_names=APP_DENIED,
        )
    )


def test_calibrated_launch_authorization_is_opaque_bound_and_one_shot() -> None:
    if sys.platform != "darwin":
        return
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        contract = _darwin_contract(base)
        profiles = isolation.build_darwin_profiles(contract)
        calibration = isolation.calibrate_darwin_profiles(contract, profiles=profiles)
        environment = isolation.build_child_environment(
            role="app",
            source_root=contract.source_root,
            writable_root=contract.app_writable_root,
            inherited=os.environ,
        )
        command = (
            str(isolation.SANDBOX_EXEC),
            "-p",
            profiles.app,
            str(contract.python_executable),
            "-c",
            "raise SystemExit(0)",
        )
        forged_calibration = json.loads(json.dumps(calibration))
        with isolation.owned_child_stdio(
            contract.app_writable_root / "launch-stdio",
            role="app",
        ) as stdio:
            launch = {
                "session_id": "launch-session",
                "process_id": "app/immediate-exit",
                "contract": contract,
                "profiles": profiles,
                "calibration": calibration,
                "role": "app",
                "command": command,
                "cwd": contract.source_root,
                "environment": environment,
                "stdio": stdio,
            }
            real_bound_identity = isolation._bound_contract_identity

            def drifted_bound_identity(value):
                return (*real_bound_identity(value), ("runtime-drift",))

            with patch.object(
                isolation,
                "_bound_contract_identity",
                side_effect=drifted_bound_identity,
            ):
                raises_isolation(
                    lambda: isolation.authorize_calibrated_launch(**launch)
                )
            raises_isolation(
                lambda: isolation.authorize_calibrated_launch(
                    **{**launch, "calibration": forged_calibration}
                )
            )
            forged_streams = []
            try:
                for name in ("stdin", "stdout", "stderr"):
                    path = contract.final_evidence_root / f"forged-{name}.log"
                    forged_streams.append(open(path, "w+b"))
                forged_stdio = isolation.OwnedChildStdio(*forged_streams)
                raises_isolation(
                    lambda: isolation.authorize_calibrated_launch(
                        **{**launch, "stdio": forged_stdio}
                    )
                )
            finally:
                for stream in forged_streams:
                    stream.close()
            unowned = SimpleNamespace(
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            raises_isolation(
                lambda: isolation.authorize_calibrated_launch(
                    **{**launch, "stdio": unowned}
                )
            )
            mismatch = isolation.authorize_calibrated_launch(**launch)
            raises_isolation(
                lambda: isolation.spawn_calibrated_child(
                    authorization=mismatch,
                    **{**launch, "command": (*command, "unexpected")},
                )
            )
            authorization = isolation.authorize_calibrated_launch(**launch)
            require(
                not isinstance(authorization, (dict, list, str, bytes, tuple)),
                "calibrated launch authorization is forgeable data",
            )
            encoded = repr(authorization)
            require(
                str(contract.workspace_root) not in encoded and profiles.app not in encoded,
                "opaque authorization leaked bound security inputs",
            )
            result = isolation.spawn_calibrated_child(
                authorization=authorization,
                **launch,
            )
            proof = isolation.wait_for_clean_owned_process_group_exit(
                result, timeout=5.0
            )
            row, _digest = isolation.consume_quiescent_process_exit_provenance(
                proof,
                expected_session_id="launch-session",
                expected_role="app",
                expected_process_id="app/immediate-exit",
            )
            require(row["quiescent"] is True, "authorized spawn was not quiescent")
            raises_isolation(
                lambda: isolation.spawn_calibrated_child(
                    authorization=authorization,
                    **launch,
                )
            )

        browser_environment = isolation.build_child_environment(
            role="browser",
            source_root=contract.source_root,
            writable_root=contract.browser_writable_root,
            inherited=os.environ,
        )
        browser_prefix = (
            str(isolation.SANDBOX_EXEC),
            "-p",
            profiles.browser,
            str(contract.python_executable),
        )
        worker_arguments = (
            isolation.BROWSER_WORKER_ENTRYPOINT,
            "--expected-origin",
            f"http://127.0.0.1:{contract.app_port}",
            "--expected-request-id",
            "capture/mobile",
            "--allow-staging-path",
            "capture/mobile.png",
            "--allow-staging-path",
            "capture/mobile.render.json",
            "--browser-executable",
            str(contract.browser_executable),
            "--timeout-ms",
            "30000",
        )
        browser_command = (*browser_prefix, *worker_arguments)
        with isolation.owned_child_stdio(
            contract.browser_writable_root / "browser-launch-stdio",
            role="browser",
        ) as browser_stdio:
            browser_launch = {
                "session_id": "launch-session",
                "process_id": "browser/frozen-worker",
                "contract": contract,
                "profiles": profiles,
                "calibration": calibration,
                "role": "browser",
                "command": browser_command,
                "cwd": contract.source_root,
                "environment": browser_environment,
                "stdio": browser_stdio,
            }
            unsafe_commands = (
                (*browser_prefix, "-c", "raise SystemExit(0)"),
                (*browser_prefix, "-m", "scripts.ui_ux_browser_worker"),
                (*browser_prefix, "scripts/fixture.py", *worker_arguments[1:]),
                (
                    *browser_prefix,
                    str(contract.source_root / isolation.BROWSER_WORKER_ENTRYPOINT),
                    *worker_arguments[1:],
                ),
                (
                    *browser_prefix,
                    isolation.BROWSER_WORKER_ENTRYPOINT,
                    *worker_arguments[3:],
                ),
            )
            with patch.object(isolation.subprocess, "Popen") as popen:
                for unsafe_command in unsafe_commands:
                    error = raises_isolation(
                        lambda unsafe_command=unsafe_command: isolation.authorize_calibrated_launch(
                            **{**browser_launch, "command": unsafe_command}
                        )
                    )
                    require(
                        "browser" in str(error).casefold(),
                        "unsafe browser command was not classified at authorization",
                    )
            require(
                not popen.called
                and not any(
                    row.authorization.process_id == "browser/frozen-worker"
                    for row in isolation._LAUNCH_GRANTS.values()
                ),
                "arbitrary browser command reached Popen or received a launch grant",
            )

            mirrored_worker = (
                contract.source_root / isolation.BROWSER_WORKER_ENTRYPOINT
            )
            os.chmod(mirrored_worker, 0o644)
            try:
                immutable_error = raises_isolation(
                    lambda: isolation.authorize_calibrated_launch(**browser_launch)
                )
            finally:
                os.chmod(mirrored_worker, 0o444)
            require(
                "immutable" in str(immutable_error).casefold(),
                "writable browser worker was not rejected before grant creation",
            )

            browser_grant = isolation.authorize_calibrated_launch(**browser_launch)
            browser_process = isolation.spawn_calibrated_child(
                authorization=browser_grant,
                **browser_launch,
            )
            browser_proof = isolation.wait_for_clean_owned_process_group_exit(
                browser_process,
                timeout=5.0,
            )
            browser_row, _browser_digest = (
                isolation.consume_quiescent_process_exit_provenance(
                    browser_proof,
                    expected_session_id="launch-session",
                    expected_role="browser",
                    expected_process_id="browser/frozen-worker",
                )
            )
            require(
                browser_row["returnCode"] == 0
                and browser_row["quiescent"] is True,
                "exact frozen browser worker did not pass operational closure",
            )


def test_launch_grant_identity_copy_and_capacity_fail_closed() -> None:
    fake_authorization = SimpleNamespace()
    fake_launch = {
        "session_id": "grant-session",
        "process_id": "app/grant",
        "contract": SimpleNamespace(),
        "profiles": SimpleNamespace(),
        "calibration": {},
        "role": "app",
        "command": ("unused",),
        "cwd": ROOT,
        "environment": {},
        "stdio": SimpleNamespace(),
    }
    grant = None
    with patch.object(
        isolation,
        "_build_launch_authorization",
        return_value=fake_authorization,
    ), patch.object(isolation, "MAX_LAUNCH_GRANTS", 1):
        try:
            grant = isolation.authorize_calibrated_launch(**fake_launch)
            for operation in (copy.copy, copy.deepcopy):
                try:
                    operation(grant)
                except TypeError:
                    pass
                else:
                    raise AssertionError("opaque launch grant was copyable")
            forged = isolation.CalibratedLaunchGrant(grant._token)
            raises_isolation(
                lambda: isolation.spawn_calibrated_child(
                    authorization=forged,
                    **fake_launch,
                )
            )
            require(
                isolation._LAUNCH_GRANTS[grant._token].grant is grant,
                "reconstructed launch grant consumed the registered capability",
            )
            error = raises_isolation(
                lambda: isolation.authorize_calibrated_launch(**fake_launch)
            )
            require(
                "registry" in str(error).casefold()
                and len(isolation._LAUNCH_GRANTS) == 1,
                "launch-grant capacity did not fail closed",
            )
        finally:
            if grant is not None:
                with isolation._LAUNCH_GRANTS_LOCK:
                    isolation._LAUNCH_GRANTS.pop(grant._token, None)


def test_spawn_cleanup_error_reaps_leader_and_retains_registry() -> None:
    if sys.platform != "darwin":
        return
    process_token = isolation._new_process_token()
    grant = isolation.CalibratedLaunchGrant(
        f"cleanup-error-{time.time_ns()}"
    )
    expected = SimpleNamespace(
        session_id="cleanup-error-session",
        process_id="app/failed-attachment",
        process_token=process_token,
        role="app",
        launch_identity_sha256=hashlib.sha256(process_token.encode()).hexdigest(),
        command=(sys.executable, "-c", "import time; time.sleep(30)"),
        cwd=ROOT,
        environment={},
    )
    with isolation._LAUNCH_GRANTS_LOCK:
        isolation._LAUNCH_GRANTS[grant._token] = isolation._LaunchGrantRegistration(
            grant=grant,
            authorization=expected,
        )
    child_kwargs = {
        "cwd": str(ROOT),
        "env": dict(os.environ),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
        "pass_fds": (),
        "start_new_session": True,
    }
    registration = None
    try:
        with patch.object(isolation, "_verify_bound_launch"), patch.object(
            isolation, "child_popen_kwargs", return_value=child_kwargs
        ), patch.object(
            isolation,
            "_attach_process_family",
            side_effect=isolation.IsolationContractError(
                "injected attachment failure"
            ),
        ), patch.object(
            isolation,
            "_bounded_process_table_observation",
            side_effect=isolation.IsolationContractError(
                "injected process-table failure"
            ),
        ):
            error = raises_isolation(
                lambda: isolation.spawn_calibrated_child(
                    authorization=grant,
                    session_id="unused",
                    process_id="unused",
                    contract=SimpleNamespace(),
                    profiles=SimpleNamespace(),
                    calibration={},
                    role="app",
                    command=("unused",),
                    cwd=ROOT,
                    environment={},
                    stdio=SimpleNamespace(),
                )
            )
        registration = isolation._PROCESS_FAMILIES_BY_TOKEN.get(process_token)
        require(
            "could not prove closure" in str(error).casefold(),
            "cleanup observation failure was not propagated",
        )
        require(
            registration is not None
            and registration.state == "cleanup-pending"
            and registration.process is not None
            and registration.process.poll() is not None
            and isolation._PROCESS_FAMILIES_BY_PROCESS.get(
                id(registration.process)
            )
            is registration,
            "cleanup error left a live leader or released its registry entry",
        )
    finally:
        if registration is None:
            registration = isolation._PROCESS_FAMILIES_BY_TOKEN.get(process_token)
        if registration is not None:
            process = registration.process
            if process is not None and process.poll() is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                with contextlib.suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=2.0)
            isolation._release_process_family(registration)
        with isolation._LAUNCH_GRANTS_LOCK:
            isolation._LAUNCH_GRANTS.pop(grant._token, None)


def test_spawn_retention_error_reaps_leader_and_releases_registry() -> None:
    if sys.platform != "darwin":
        return
    process_token = isolation._new_process_token()
    grant = isolation.CalibratedLaunchGrant(
        f"retention-error-{time.time_ns()}"
    )
    expected = SimpleNamespace(
        session_id="retention-error-session",
        process_id="app/failed-retention",
        process_token=process_token,
        role="app",
        launch_identity_sha256=hashlib.sha256(process_token.encode()).hexdigest(),
        command=(sys.executable, "-c", "import time; time.sleep(30)"),
        cwd=ROOT,
        environment={},
    )
    with isolation._LAUNCH_GRANTS_LOCK:
        isolation._LAUNCH_GRANTS[grant._token] = isolation._LaunchGrantRegistration(
            grant=grant,
            authorization=expected,
        )
    child_kwargs = {
        "cwd": str(ROOT),
        "env": dict(os.environ),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
        "pass_fds": (),
        "start_new_session": True,
    }
    spawned: list[subprocess.Popen[bytes]] = []
    real_popen = isolation._POPEN_CLASS

    def capture_spawn(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        spawned.append(process)
        return process

    def successful_cleanup(process, _registration):
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=2.0)

    try:
        with patch.object(isolation, "_verify_bound_launch"), patch.object(
            isolation, "child_popen_kwargs", return_value=child_kwargs
        ), patch.object(
            isolation.subprocess, "Popen", side_effect=capture_spawn
        ), patch.object(
            isolation,
            "_attach_process_family",
            side_effect=isolation.IsolationContractError(
                "injected attachment failure"
            ),
        ), patch.object(
            isolation,
            "_retain_unregistered_process_family",
            side_effect=isolation.IsolationContractError(
                "injected retention failure"
            ),
        ), patch.object(
            isolation,
            "_cleanup_unregistered_process",
            side_effect=successful_cleanup,
        ):
            error = raises_isolation(
                lambda: isolation.spawn_calibrated_child(
                    authorization=grant,
                    session_id="unused",
                    process_id="unused",
                    contract=SimpleNamespace(),
                    profiles=SimpleNamespace(),
                    calibration={},
                    role="app",
                    command=("unused",),
                    cwd=ROOT,
                    environment={},
                    stdio=SimpleNamespace(),
                )
            )
        require(
            "retention failure" in str(error).casefold(),
            "retention failure was not propagated after successful cleanup",
        )
        require(
            len(spawned) == 1 and spawned[0].poll() is not None,
            "retention failure left the spawned leader acting",
        )
        require(
            process_token not in isolation._PROCESS_FAMILIES_BY_TOKEN
            and id(spawned[0]) not in isolation._PROCESS_FAMILIES_BY_PROCESS,
            "successful cleanup retained a reserved or process-bound registry row",
        )
    finally:
        for process in spawned:
            if process.poll() is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                with contextlib.suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=2.0)
        registration = isolation._PROCESS_FAMILIES_BY_TOKEN.get(process_token)
        if registration is not None:
            isolation._release_process_family(registration)
        with isolation._LAUNCH_GRANTS_LOCK:
            isolation._LAUNCH_GRANTS.pop(grant._token, None)


def test_swaps_oversize_cleanup_and_timeout_leave_no_owned_artifacts() -> None:
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        workspace = base / "workspace"
        workspace.mkdir(mode=0o700)
        _workspace_fixture(workspace)

        parent_swap = _make_mirror(workspace, base / "parent-swap")
        original_parent = parent_swap.source_root.parent
        moved_parent = base / "parent-swap-original"
        original_parent.rename(moved_parent)
        shutil.copytree(moved_parent, original_parent)
        raises_isolation(
            lambda: isolation.authenticate_source_mirror(
                parent_swap, expected_digest=parent_swap.digest
            )
        )

        root_swap = _make_mirror(workspace, base / "root-swap")
        moved_root = root_swap.source_root.with_name("source-original")
        root_swap.source_root.rename(moved_root)
        shutil.copytree(moved_root, root_swap.source_root)
        raises_isolation(
            lambda: isolation.authenticate_source_mirror(
                root_swap, expected_digest=root_swap.digest
            )
        )

        raced_root = _make_mirror(workspace, base / "root-open-race")
        raced_original = raced_root.source_root.with_name("source-original")
        real_open = isolation.os.open
        swapped = False

        def swap_immediately_before_root_open(path, flags, *args, **kwargs):
            nonlocal swapped
            if (
                not swapped
                and kwargs.get("dir_fd") is None
                and Path(path).resolve() == raced_root.source_root.resolve()
                and flags == isolation._SAFE_DIRECTORY_FLAGS
            ):
                swapped = True
                raced_root.source_root.rename(raced_original)
                shutil.copytree(raced_original, raced_root.source_root)
            return real_open(path, flags, *args, **kwargs)

        with patch.object(isolation.os, "open", side_effect=swap_immediately_before_root_open):
            raises_isolation(
                lambda: isolation.authenticate_source_mirror(
                    raced_root, expected_digest=raced_root.digest
                )
            )
        require(swapped, "source-root race did not reach the descriptor-open boundary")

        manifest_swap = _make_mirror(workspace, base / "manifest-swap")
        manifest_bytes = manifest_swap.manifest_path.read_bytes()
        manifest_swap.manifest_path.rename(
            manifest_swap.manifest_path.with_name("manifest-original.json")
        )
        manifest_swap.manifest_path.write_bytes(manifest_bytes)
        os.chmod(manifest_swap.manifest_path, 0o400)
        raises_isolation(
            lambda: isolation.authenticate_source_mirror(
                manifest_swap, expected_digest=manifest_swap.digest
            )
        )

        writable_manifest = _make_mirror(workspace, base / "manifest-writable")
        os.chmod(writable_manifest.manifest_path, 0o600)
        raises_isolation(
            lambda: isolation.authenticate_source_mirror(
                writable_manifest, expected_digest=writable_manifest.digest
            )
        )

        nonregular = _make_mirror(workspace, base / "manifest-nonregular")
        nonregular.manifest_path.rename(nonregular.manifest_path.with_suffix(".saved"))
        nonregular.manifest_path.mkdir(mode=0o700)
        raises_isolation(
            lambda: isolation.authenticate_source_mirror(
                nonregular, expected_digest=nonregular.digest
            )
        )

        oversized = _make_mirror(workspace, base / "manifest-oversized")
        limit = isolation.MAX_MIRROR_MANIFEST_BYTES
        require(isinstance(limit, int) and 1024 <= limit <= 1024 * 1024, "manifest limit differs")
        document = json.loads(oversized.manifest_path.read_text(encoding="utf-8"))
        document["padding"] = "x" * (limit + 1)
        os.chmod(oversized.manifest_path, 0o600)
        oversized.manifest_path.write_text(json.dumps(document), encoding="utf-8")
        os.chmod(oversized.manifest_path, 0o400)
        raises_isolation(
            lambda: isolation.authenticate_source_mirror(
                oversized, expected_digest=oversized.digest
            )
        )

        cleanup_parent = base / "cleanup-parent-swap"
        cleanup_parent.mkdir(mode=0o700)
        handle = isolation.create_owned_run_root(parent=cleanup_parent)
        parent_owned_path = _owned_run_path(handle)
        moved_parent = base / "cleanup-parent-original"
        cleanup_parent.rename(moved_parent)
        cleanup_parent.mkdir(mode=0o700)
        _write(cleanup_parent / "replacement.txt", "replacement-parent-must-survive\n")
        raises_isolation(lambda: isolation.remove_owned_run_root(handle))
        handle.close()
        require(
            (moved_parent / parent_owned_path.name).is_dir(),
            "cleanup removed the original root after a parent swap",
        )
        require(
            (cleanup_parent / "replacement.txt").is_file(),
            "cleanup followed a replacement parent",
        )

        cleanup_parent = base / "cleanup-root-swap"
        cleanup_parent.mkdir(mode=0o700)
        handle = isolation.create_owned_run_root(parent=cleanup_parent)
        owned_path = _owned_run_path(handle)
        moved_owned = cleanup_parent / "moved-owned-root"
        owned_path.rename(moved_owned)
        owned_path.mkdir(mode=0o700)
        _write(owned_path / "replacement.txt", "replacement-must-survive\n")
        raises_isolation(lambda: isolation.remove_owned_run_root(handle))
        require(moved_owned.is_dir(), "cleanup removed the authenticated original after a swap")
        require((owned_path / "replacement.txt").is_file(), "cleanup followed a replacement root")

        if sys.platform != "darwin":
            return
        timeout_base = base / "timeout-case"
        timeout_base.mkdir(mode=0o700)
        contract = _darwin_contract(timeout_base)
        profiles = isolation.build_darwin_profiles(contract)
        marker = str(contract.browser_writable_root / "cache" / "chromium-profile")
        coordinator_marker = str(contract.source_root / "app.py")
        before_role_roots = tuple(
            _tree_snapshot(root)
            for root in (
                contract.app_writable_root,
                contract.browser_writable_root,
                contract.final_evidence_root,
            )
        )
        failure: BaseException | None = None
        with patch.object(
            isolation,
            "_run_app_calibration",
            return_value=_passing_probe_raw(APP_ALLOWED, APP_DENIED),
        ):
            try:
                isolation.calibrate_darwin_profiles(
                    contract, profiles=profiles, timeout=0.001
                )
            except BaseException as exc:  # noqa: BLE001 - cleanup precedes the oracle.
                failure = exc
        leaked = _wait_for_marker_processes(marker) | _wait_for_marker_processes(
            coordinator_marker
        )
        role_roots_changed = tuple(
            _tree_snapshot(root)
            for root in (
                contract.app_writable_root,
                contract.browser_writable_root,
                contract.final_evidence_root,
            )
        ) != before_role_roots
        _cleanup_test_processes(leaked)
        require(
            isinstance(failure, isolation.IsolationContractError),
            "browser timeout was not classified by the isolation boundary",
        )
        require(not leaked, "browser timeout left a child process alive")
        require(not role_roots_changed, "browser timeout left child runtime artifacts")


def test_mirror_failure_cleanup_refuses_parent_namespace_swap() -> None:
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        workspace = base / "workspace"
        workspace.mkdir(mode=0o700)
        _workspace_fixture(workspace)
        run_parent = base / "runs"
        run_parent.mkdir(mode=0o700)
        moved_parent = base / "runs-original"
        replacement = run_parent / "mirror"

        def swap_parent_then_fail(*_args, **_kwargs):
            run_parent.rename(moved_parent)
            run_parent.mkdir(mode=0o700)
            replacement.mkdir(mode=0o700)
            _write(replacement / "replacement.txt", "replacement-must-survive\n")
            raise RuntimeError("forced copy failure after parent swap")

        failure: BaseException | None = None
        with patch.object(
            isolation,
            "_copy_projection_directory",
            side_effect=swap_parent_then_fail,
        ):
            try:
                isolation.build_source_mirror(
                    workspace_root=workspace,
                    run_root=run_parent / "mirror",
                    policy=_mirror_policy(),
                )
            except BaseException as exc:  # noqa: BLE001 - verify cleanup first.
                failure = exc

        require(failure is not None, "forced mirror copy failure was swallowed")
        require(
            (replacement / "replacement.txt").is_file(),
            "mirror failure cleanup followed a swapped parent namespace",
        )
        require(
            (moved_parent / "mirror").is_dir(),
            "mirror failure cleanup destructively removed the authenticated partial root",
        )


def test_calibration_output_is_bounded_and_partial_records_time_out() -> None:
    limit = isolation.MAX_CALIBRATION_RECORD_BYTES
    require(
        isinstance(limit, int) and 1024 <= limit <= 1024 * 1024,
        "calibration record limit differs",
    )

    with tempfile.TemporaryFile(mode="w+b", buffering=0) as stream:
        stream.write(json.dumps({"ready": True}).encode("utf-8") + b"\n")
        stream.write(json.dumps({"result": "ok"}).encode("utf-8") + b"\n")
        stream.seek(0)
        reader = isolation._BoundedJsonLineReader(stream)
        require(
            reader.read_object(timeout=0.5, label="first record") == {"ready": True},
            "bounded reader changed the first JSON record",
        )
        require(
            reader.read_object(timeout=0.5, label="second record") == {"result": "ok"},
            "bounded reader discarded bytes after the first JSON line",
        )
        reader.finish_exact(timeout=0.5, label="exact records")

    with tempfile.TemporaryFile(mode="w+b", buffering=0) as stream:
        stream.write(b'{"ready":true}\n{"result":"ok"}\n{"extra":true}\n')
        stream.seek(0)
        reader = isolation._BoundedJsonLineReader(stream)
        reader.read_object(timeout=0.5, label="ready record")
        reader.read_object(timeout=0.5, label="result record")
        error = raises_isolation(
            lambda: reader.finish_exact(timeout=0.5, label="duplicate record")
        )
        require("extra" in str(error).casefold(), "duplicate record was accepted")

    read_fd, write_fd = os.pipe()
    try:
        with os.fdopen(read_fd, "rb", buffering=0, closefd=False) as stream:
            os.write(write_fd, b'{"ready":')
            reader = isolation._BoundedJsonLineReader(stream)
            error = raises_isolation(
                lambda: reader.read_object(timeout=0.01, label="partial record")
            )
            require("timed out" in str(error).casefold(), "partial record did not time out")
    finally:
        os.close(read_fd)
        os.close(write_fd)

    with tempfile.TemporaryFile(mode="w+b", buffering=0) as stream:
        stream.write(b"x" * (limit + 1) + b"\n")
        stream.seek(0)
        reader = isolation._BoundedJsonLineReader(stream)
        error = raises_isolation(
            lambda: reader.read_object(timeout=0.5, label="oversized record")
        )
        require("limit" in str(error).casefold(), "oversized record was misclassified")

    process = subprocess.Popen(
        (
            sys.executable,
            "-c",
            f"import os; os.write(1, b'x' * {limit + 1})",
        ),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=True,
        pass_fds=(),
        start_new_session=True,
    )
    try:
        error = raises_isolation(
            lambda: isolation._bounded_communicate(
                process,
                timeout=2.0,
                stdout_limit=limit,
                stderr_limit=limit,
            )
        )
        require("limit" in str(error).casefold(), "oversized pipe was misclassified")
    finally:
        if process.poll() is None:
            isolation.terminate_owned_process_group(process)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        os.chmod(root, 0o700)
        probe = isolation._create_ephemeral_calibration_probe(
            root,
            label="mutation-test",
            payload=b"original\n",
        )
        with open(probe.path, "ab") as handle:
            handle.write(b"mutated\n")
        error = raises_isolation(probe.remove)
        require("bytes changed" in str(error).casefold(), "probe mutation was misclassified")
        require(not probe.path.exists(), "mutated owned probe was not safely removed")

    with tempfile.TemporaryDirectory() as raw:
        runtime_root = Path(raw)
        runtime_file = runtime_root / "site-packages" / "mutable_module.py"
        _write(runtime_file, "VALUE = 1\n")
        before_stat = runtime_file.stat()
        before_digest = isolation._runtime_tree_sha256(runtime_root)
        _write(runtime_file, "VALUE = 2\n")
        os.utime(
            runtime_file,
            ns=(before_stat.st_atime_ns, before_stat.st_mtime_ns),
        )
        after_digest = isolation._runtime_tree_sha256(runtime_root)
        require(
            after_digest != before_digest,
            "in-place runtime source mutation preserved the frozen identity",
        )


def test_process_group_termination_is_quiescent_on_return() -> None:
    if not hasattr(os, "fork"):
        return
    script = r'''
import os
import signal
import time

child = os.fork()
if child == 0:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    while True:
        time.sleep(1.0)
signal.signal(signal.SIGTERM, signal.SIG_IGN)
print(child, flush=True)
while True:
    time.sleep(1.0)
'''
    process = subprocess.Popen(
        (sys.executable, "-c", script),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        pass_fds=(),
        start_new_session=True,
    )
    require(process.stdout is not None, "process-group readiness pipe is missing")
    child_pid = process.stdout.readline()
    require(child_pid.strip().isdigit(), "process-group child did not become ready")
    try:
        isolation.terminate_owned_process_group(process, timeout=2.0)
        ready, _writable, _errors = select.select([process.stdout], [], [], 2.0)
        require(bool(ready), "owned process-group pipe did not become quiescent")
        require(process.stdout.read(1) == b"", "owned descendant remained active")
    finally:
        if process.returncode is None:
            isolation.terminate_owned_process_group(process, timeout=2.0)
        process.stdout.close()


def test_process_table_observation_is_single_bounded_strict_and_exact() -> None:
    if sys.platform != "darwin":
        return
    token = isolation._new_process_token()
    marker = f"{isolation.PROCESS_TOKEN_ENV_KEY}={token}".encode("ascii")
    observation = isolation._parse_process_table(
        b"11 501 11 Z 700 /bin/child " + marker + b" OTHER=value\n"
        b"12 501 12 S 0 /bin/other " + marker + b"x\n",
        process_token=token,
    )
    require(observation.rows[0].has_family_token, "exact process token was missed")
    require(
        not observation.rows[1].has_family_token,
        "process token substring was accepted as an exact token",
    )
    for malformed in (
        b"11 501 11 Z 700\n",
        b"11 user 11 Z 700 command\n",
        b"11 501 11 S! 700 command\n",
        b"11 501 11 Z xyz command\n",
        b"11 501 11 Z 0 command\n11 501 11 Z 0 duplicate\n",
    ):
        raises_isolation(
            lambda malformed=malformed: isolation._parse_process_table(
                malformed, process_token=token
            )
        )
    raises_isolation(
        lambda: isolation._parse_process_table(
            b"x" * (isolation.MAX_PROCESS_TABLE_BYTES + 1),
            process_token=token,
        )
    )

    real_popen = isolation._POPEN_CLASS
    commands = []

    def tracked_popen(*args, **kwargs):
        commands.append(tuple(args[0]))
        return real_popen(*args, **kwargs)

    with patch.object(isolation.subprocess, "Popen", side_effect=tracked_popen):
        live = isolation._bounded_process_table_observation(token)
    require(bool(live.rows), "Darwin process table observation was empty")
    require(
        commands
        == [
            (
                "/bin/ps",
                "eww",
                "-axo",
                "pid=,uid=,pgid=,stat=,xstat=,command=",
            )
        ],
        "process closure did not use one exact bounded ps observation",
    )


def test_clean_exit_proof_is_bound_atomic_one_shot_and_uncopyable() -> None:
    if sys.platform != "darwin":
        return
    process, registration = _spawn_process_family(
        (sys.executable, "-c", "pass"),
        session_id="proof-session",
        process_id="capture/mobile",
    )
    proof = isolation.wait_for_clean_owned_process_group_exit(process, timeout=3.0)
    forged = isolation.QuiescentProcessExit(proof._token)
    raises_isolation(
        lambda: isolation.consume_quiescent_process_exit_provenance(
            forged,
            expected_session_id="proof-session",
            expected_role="browser",
            expected_process_id="capture/mobile",
        )
    )
    for operation in (copy.copy, copy.deepcopy):
        try:
            operation(proof)
        except TypeError:
            pass
        else:
            raise AssertionError("opaque process-exit proof was copyable")
    for session_id, role, process_id in (
        ("wrong-session", "browser", "capture/mobile"),
        ("proof-session", "app", "capture/mobile"),
        ("proof-session", "browser", "capture/desktop"),
    ):
        raises_isolation(
            lambda session_id=session_id, role=role, process_id=process_id: (
                isolation.consume_quiescent_process_exit_provenance(
                    proof,
                    expected_session_id=session_id,
                    expected_role=role,
                    expected_process_id=process_id,
                )
            )
        )
    row, digest = isolation.consume_quiescent_process_exit_provenance(
        proof,
        expected_session_id="proof-session",
        expected_role="browser",
        expected_process_id="capture/mobile",
    )
    require(
        row["sessionId"] == "proof-session"
        and row["role"] == "browser"
        and row["processId"] == "capture/mobile"
        and row["launchIdentitySha256"]
        == registration.identity.launch_identity_sha256
        and row["returnCode"] == 0
        and row["signal"] is None
        and row["quiescent"] is True,
        "clean process-exit proof lost its bound launch identity",
    )
    require(len(digest) == 64, "clean process-exit digest is invalid")
    raises_isolation(
        lambda: isolation.consume_quiescent_process_exit_provenance(
            proof,
            expected_session_id="proof-session",
            expected_role="browser",
            expected_process_id="capture/mobile",
        )
    )

    racing, _registration = _spawn_process_family(
        (sys.executable, "-c", "import time; time.sleep(0.15)"),
        session_id="race-session",
        process_id="capture/race",
    )
    barrier = threading.Barrier(3)
    proofs = []
    errors = []
    result_lock = threading.Lock()

    def waiter() -> None:
        barrier.wait()
        try:
            value = isolation.wait_for_clean_owned_process_group_exit(
                racing, timeout=3.0
            )
        except BaseException as exc:  # noqa: BLE001 - capture thread result.
            with result_lock:
                errors.append(exc)
        else:
            with result_lock:
                proofs.append(value)

    threads = [threading.Thread(target=waiter) for _index in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=5.0)
    require(
        len(proofs) == 1
        and len(errors) == 1
        and isinstance(errors[0], isolation.IsolationContractError),
        "concurrent waiters minted more than one process-exit proof",
    )
    isolation.consume_quiescent_process_exit_provenance(
        proofs[0],
        expected_session_id="race-session",
        expected_role="browser",
        expected_process_id="capture/race",
    )


def test_nonzero_signal_and_registry_capacity_fail_closed() -> None:
    if sys.platform != "darwin":
        return
    for process_id, source, expected_returncode in (
        ("exit/nonzero", "raise SystemExit(7)", 7),
        (
            "exit/signal",
            "import os, signal; os.kill(os.getpid(), signal.SIGTERM)",
            -signal.SIGTERM,
        ),
    ):
        process, registration = _spawn_process_family(
            (sys.executable, "-c", source),
            session_id="failure-session",
            process_id=process_id,
        )
        error = raises_isolation(
            lambda process=process: isolation.wait_for_clean_owned_process_group_exit(
                process, timeout=3.0
            )
        )
        require("cleanly" in str(error).casefold(), "bad exit was misclassified")
        require(
            process.returncode == expected_returncode,
            "bad-exit leader was not reaped with its exact status",
        )
        require(
            registration.identity.process_token
            not in isolation._PROCESS_FAMILIES_BY_TOKEN
            and id(process) not in isolation._PROCESS_FAMILIES_BY_PROCESS,
            "bad-exit registration leaked",
        )

    require(
        not isolation._PROCESS_FAMILIES_BY_TOKEN,
        "process-family registry was not empty before capacity test",
    )
    first_identity = _test_family_identity(
        session_id="capacity-session",
        process_id="one",
        role="app",
    )
    second_identity = _test_family_identity(
        session_id="capacity-session",
        process_id="two",
        role="app",
    )
    with patch.object(isolation, "MAX_PROCESS_FAMILIES", 1):
        first = isolation._reserve_process_family(first_identity)
        try:
            raises_isolation(
                lambda: isolation._reserve_process_family(second_identity)
            )
        finally:
            isolation._release_reserved_process_family(first)
    require(
        not isolation._PROCESS_FAMILIES_BY_TOKEN,
        "reserved process-family capacity did not clean up",
    )

    capped, capped_registration = _spawn_process_family(
        (sys.executable, "-c", "pass"),
        session_id="capacity-session",
        process_id="proof-capacity",
        role="app",
    )
    with patch.object(isolation, "MAX_PROCESS_EXIT_PROOFS", 0):
        error = raises_isolation(
            lambda: isolation.wait_for_clean_owned_process_group_exit(
                capped, timeout=3.0
            )
        )
    require("registry" in str(error).casefold(), "proof capacity was misclassified")
    require(
        capped_registration.identity.process_token
        not in isolation._PROCESS_FAMILIES_BY_TOKEN,
        "proof-capacity failure leaked a process family",
    )


def test_setsid_descendant_and_grandchild_are_rejected_then_terminated() -> None:
    if sys.platform != "darwin" or not hasattr(os, "fork"):
        return
    script = r'''
import os
import signal
import time

def linger():
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    while True:
        time.sleep(1.0)

child = os.fork()
if child == 0:
    os.setsid()
    grandchild = os.fork()
    if grandchild == 0:
        os.setsid()
        linger()
    linger()
print("ready", flush=True)
time.sleep(0.3)
'''
    process, registration = _spawn_process_family(
        (sys.executable, "-c", script),
        session_id="escape-session",
        process_id="capture/setsid-tree",
        stdout=subprocess.PIPE,
    )
    require(process.stdout is not None, "setsid readiness pipe is missing")
    try:
        require(process.stdout.readline() == b"ready\n", "setsid family was not ready")
        live = isolation._bounded_process_table_observation(
            registration.identity.process_token
        )
        family_rows = tuple(
            row
            for row in live.rows
            if row.uid == os.getuid() and row.has_family_token
        )
        require(
            len({row.process_group for row in family_rows}) >= 3,
            "setsid descendant/grandchild did not escape into separate PGIDs",
        )
        error = raises_isolation(
            lambda: isolation.wait_for_clean_owned_process_group_exit(
                process, timeout=3.0
            )
        )
        require(
            "descendants" in str(error).casefold(),
            "separate-PGID descendants were accepted as quiescent",
        )
        require(
            registration.state == "claimed"
            and id(process) in isolation._PROCESS_FAMILIES_BY_PROCESS,
            "failed closure lost the family needed for bounded cleanup",
        )
        isolation.terminate_owned_process_group(process, timeout=3.0)
        after = isolation._bounded_process_table_observation(
            registration.identity.process_token
        )
        require(
            not any(
                row.uid == os.getuid() and row.has_family_token
                for row in after.rows
            )
            and id(process) not in isolation._PROCESS_FAMILIES_BY_PROCESS,
            "bounded termination retained a token-family process or registration",
        )
        ready, _writable, _errors = select.select([process.stdout], [], [], 2.0)
        require(bool(ready) and process.stdout.read(1) == b"", "setsid pipe stayed active")
    finally:
        if id(process) in isolation._PROCESS_FAMILIES_BY_PROCESS:
            isolation.terminate_owned_process_group(process, timeout=3.0)
        process.stdout.close()


def test_registration_failure_cleans_escaped_family_and_signals_safely() -> None:
    if sys.platform != "darwin":
        return
    identity = _test_family_identity(
        session_id="registration-session",
        process_id="failed-attach",
        role="app",
    )
    registration = isolation._reserve_process_family(identity)
    environment = dict(os.environ)
    environment[isolation.PROCESS_TOKEN_ENV_KEY] = identity.process_token
    script = r'''
import os
import time
child = os.fork()
if child == 0:
    os.setsid()
    while True:
        time.sleep(1.0)
print("ready", flush=True)
while True:
    time.sleep(1.0)
'''
    process = subprocess.Popen(
        (sys.executable, "-c", script),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=environment,
        close_fds=True,
        pass_fds=(),
        start_new_session=True,
    )
    require(process.stdout is not None, "failed-registration readiness pipe is missing")
    try:
        require(process.stdout.readline() == b"ready\n", "failed-registration family not ready")
        registration.state = "invalidated"
        raises_isolation(lambda: isolation._attach_process_family(registration, process))
        isolation._cleanup_unregistered_process(process, registration)
        isolation._release_process_family(registration)
        after = isolation._bounded_process_table_observation(identity.process_token)
        require(
            not any(row.uid == os.getuid() and row.has_family_token for row in after.rows),
            "registration failure leaked an escaped token descendant",
        )
    finally:
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=2.0)
        isolation._release_process_family(registration)
        process.stdout.close()

    synthetic_identity = _test_family_identity(
        session_id="signal-session",
        process_id="safe-targets",
        role="browser",
    )
    uid = os.getuid()
    synthetic = isolation._ProcessTableObservation(
        rows=(
            isolation._ProcessObservationRow(100, uid, 100, "S", 0, False),
            isolation._ProcessObservationRow(201, uid, 200, "S", 0, True),
            isolation._ProcessObservationRow(202, uid, 200, "S", 0, False),
            isolation._ProcessObservationRow(301, uid, 300, "S", 0, True),
            isolation._ProcessObservationRow(302, uid, 300, "S", 0, True),
        )
    )
    with patch.object(isolation.os, "killpg") as killpg, patch.object(
        isolation.os, "kill"
    ) as kill:
        isolation._signal_process_family_observation(
            synthetic_identity,
            process_group=100,
            observation=synthetic,
            signum=signal.SIGKILL,
            allow_original_group=True,
        )
    signalled_groups = {call.args[0] for call in killpg.call_args_list}
    signalled_pids = {call.args[0] for call in kill.call_args_list}
    require(
        signalled_groups == {100, 300}
        and signalled_pids == {201}
        and 200 not in signalled_groups
        and 202 not in signalled_pids,
        "foreign-group cleanup could signal unrelated processes",
    )

    stale_original_group = isolation._ProcessTableObservation(
        rows=(
            isolation._ProcessObservationRow(4242, uid, 100, "S", 0, False),
        )
    )
    with patch.object(isolation.os, "killpg") as killpg, patch.object(
        isolation.os, "kill"
    ) as kill:
        isolation._signal_process_family_observation(
            synthetic_identity,
            process_group=100,
            observation=stale_original_group,
            signum=signal.SIGKILL,
            allow_original_group=False,
        )
    require(
        not killpg.called and not kill.called,
        "allow_original_group=false signalled an untagged stale PGID row",
    )


def test_real_playwright_family_spans_pgids_and_closes() -> None:
    if sys.platform != "darwin":
        return
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        return
    script = r'''
import time
from playwright.sync_api import sync_playwright
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_content("<main>family-ready</main>")
    print("ready", flush=True)
    time.sleep(0.4)
    browser.close()
'''
    process, registration = _spawn_process_family(
        (sys.executable, "-c", script),
        session_id="playwright-session",
        process_id="capture/real-chromium",
        stdout=subprocess.PIPE,
    )
    require(process.stdout is not None, "Playwright readiness pipe is missing")
    try:
        require(process.stdout.readline() == b"ready\n", "real Playwright did not start")
        observation = isolation._bounded_process_table_observation(
            registration.identity.process_token
        )
        process_groups = {
            row.process_group
            for row in observation.rows
            if row.uid == os.getuid() and row.has_family_token
        }
        require(
            len(process_groups) >= 2,
            "real Chromium did not demonstrate its separate process group",
        )
        proof = isolation.wait_for_clean_owned_process_group_exit(
            process, timeout=10.0
        )
        isolation.consume_quiescent_process_exit_provenance(
            proof,
            expected_session_id="playwright-session",
            expected_role="browser",
            expected_process_id="capture/real-chromium",
        )
    finally:
        if id(process) in isolation._PROCESS_FAMILIES_BY_PROCESS:
            isolation.terminate_owned_process_group(process, timeout=5.0)
        process.stdout.close()


def test_non_darwin_and_missing_seatbelt_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        placeholder = SimpleNamespace()
        with patch.object(isolation.sys, "platform", "linux"):
            error = raises_dependency(
                lambda: isolation.calibrate_darwin_profiles(
                    placeholder,
                    profiles=placeholder,
                    timeout=1.0,
                )
            )
            lowered = str(error).casefold()
            require("darwin" in lowered or "unsupported" in lowered, "wrong platform class")

        if sys.platform == "darwin":
            contract = _darwin_contract(base)
            profiles = isolation.build_darwin_profiles(contract)
            with patch.object(isolation, "SANDBOX_EXEC", base / "missing-sandbox-exec"):
                error = raises_dependency(
                    lambda: isolation.calibrate_darwin_profiles(
                        contract,
                        profiles=profiles,
                        timeout=1.0,
                    )
                )
                require("sandbox" in str(error).casefold(), "missing Seatbelt is misclassified")


TESTS = (
    test_source_mirror_is_exact_stable_read_only_and_new_inode,
    test_source_mirror_fd_authority_ignores_replacement_path,
    test_source_mirror_rejects_symlink_hardlink_fifo_and_socket,
    test_source_mirror_rejects_escaping_or_ambiguous_policy_paths,
    test_child_environment_is_allowlisted_private_and_role_scoped,
    test_child_spawn_closes_descriptors_and_uses_owned_stdio,
    test_profiles_deny_ambient_home_reads_and_browser_arbitrary_exec,
    test_contract_rejects_unsafe_root_hierarchy_and_runtime_ancestors,
    test_owned_run_lease_and_bounded_stale_claims_are_descriptor_safe,
    test_dual_profiles_are_distinct_and_least_privilege,
    test_real_darwin_calibration_covers_bypass_matrix_and_exact_ports,
    test_calibration_uses_private_decoy_without_mutating_workspace_or_final,
    test_browser_identity_rejects_true_and_real_chromium_proves_dom_handshake,
    test_probe_oracle_rejects_unexpected_exception_and_uses_raw_socket,
    test_calibrated_launch_authorization_is_opaque_bound_and_one_shot,
    test_launch_grant_identity_copy_and_capacity_fail_closed,
    test_spawn_cleanup_error_reaps_leader_and_retains_registry,
    test_spawn_retention_error_reaps_leader_and_releases_registry,
    test_swaps_oversize_cleanup_and_timeout_leave_no_owned_artifacts,
    test_mirror_failure_cleanup_refuses_parent_namespace_swap,
    test_calibration_output_is_bounded_and_partial_records_time_out,
    test_process_group_termination_is_quiescent_on_return,
    test_process_table_observation_is_single_bounded_strict_and_exact,
    test_clean_exit_proof_is_bound_atomic_one_shot_and_uncopyable,
    test_nonzero_signal_and_registry_capacity_fail_closed,
    test_setsid_descendant_and_grandchild_are_rejected_then_terminated,
    test_registration_failure_cleans_escaped_family_and_signals_safely,
    test_real_playwright_family_spans_pgids_and_closes,
    test_non_darwin_and_missing_seatbelt_fail_closed,
)


def main() -> int:
    failures = 0
    for test in TESTS:
        try:
            test()
        except Exception as exc:  # noqa: BLE001 - plain-script test harness.
            failures += 1
            print(f"  FAIL {test.__name__}: {type(exc).__name__}: {exc}")
        else:
            print(f"  PASS {test.__name__}")
    print(f"\n{len(TESTS) - failures}/{len(TESTS)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
