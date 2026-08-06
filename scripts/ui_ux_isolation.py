#!/usr/bin/env python3
"""Darwin isolation primitives for authenticated UX-1B browser evidence.

The trusted coordinator uses this module to build an immutable source mirror,
construct credential-free child processes, and calibrate two independent
Seatbelt profiles.  The browser production entrypoint is the immutable mirrored
worker plus the calibrated Playwright/Chromium runtime; process-group and token
checks attest its operational shutdown, while Seatbelt remains the isolation
boundary.  Python guards may add telemetry elsewhere, but none of the security
decisions in this module depend on monkeypatches.
"""

from __future__ import annotations

import contextlib
import errno
import fcntl
import hashlib
import json
import math
import os
import re
import select
import secrets
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterator, Mapping, Sequence


_POPEN_CLASS = subprocess.Popen
MIRROR_SCHEMA = "quant-radar-ui-ux-ux1b-source-mirror/v1"
CALIBRATION_SCHEMA = "quant-radar-ui-ux-ux1b-isolation-calibration/v1"
SANDBOX_EXEC = Path("/usr/bin/sandbox-exec")
MAX_MIRROR_MANIFEST_BYTES = 256 * 1024
MAX_CALIBRATION_RECORD_BYTES = 256 * 1024
MAX_CALIBRATION_CAPTURE_BYTES = 512 * 1024
MAX_PROCESS_TABLE_BYTES = 4 * 1024 * 1024
MAX_PROCESS_TABLE_ERROR_BYTES = 64 * 1024
MAX_LAUNCH_GRANTS = 256
MAX_PROCESS_FAMILIES = 256
MAX_PROCESS_EXIT_PROOFS = 512
OWNED_RUN_LEASE_NAME = ".lease"
MAX_STALE_OWNED_RUN_CANDIDATES = 64
PROCESS_TOKEN_ENV_KEY = "QUANT_RADAR_UX1B_PROCESS_TOKEN"
BROWSER_WORKER_ENTRYPOINT = "scripts/ui_ux_browser_worker.py"
BROWSER_WORKER_TIMEOUT_MIN_MS = 1_000
BROWSER_WORKER_TIMEOUT_MAX_MS = 90_000

_SESSION_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_PROCESS_TOKEN_PATTERN = re.compile(r"ux1b_[0-9a-f]{64}\Z")
_PROCESS_STATE_PATTERN = re.compile(r"[A-Za-z?][A-Za-z?+<>]{0,15}\Z")
_HEX_WAIT_STATUS_PATTERN = re.compile(r"[0-9A-Fa-f]{1,8}\Z")

_DIRECTORY_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_SAFE_DIRECTORY_FLAGS = _DIRECTORY_FLAGS | _NOFOLLOW | _CLOEXEC
_SAFE_READ_FLAGS = os.O_RDONLY | _NOFOLLOW | _CLOEXEC

_SYSTEM_READ_ROOTS = tuple(
    Path(path)
    for path in (
        "/System",
        "/usr",
        "/Library/Apple/System/Library",
        "/Library/Fonts",
        "/private/etc",
        "/private/var/db/timezone",
    )
    if Path(path).exists()
)
_SYSTEM_READ_FILES = tuple(
    Path(path)
    for path in ("/", "/dev/null", "/dev/urandom", "/dev/random", "/dev/dtracehelper")
    if Path(path).exists()
)


class IsolationContractError(RuntimeError):
    """Raised when an input or observed result violates the isolation contract."""


class DependencyUnavailable(IsolationContractError):
    """Raised when the mandatory platform isolation backend is unavailable."""


@dataclass(frozen=True)
class SourceMirrorPolicy:
    """Repository-relative source inclusion and exclusion rules."""

    include: tuple[str, ...]
    exclude: tuple[str, ...]


@dataclass(frozen=True)
class SourceMirror:
    """An immutable, run-owned source projection and its authenticated digest."""

    source_root: Path
    manifest_path: Path
    digest: str
    run_identity: tuple[int, int]
    source_identity: tuple[int, int]
    manifest_identity: tuple[int, int]


@dataclass
class OwnedRunRoot:
    """Collision-safe directory retained through authenticated descriptors."""

    path: Path
    leaf_name: str
    parent_descriptor: int = field(repr=False)
    descriptor: int = field(repr=False)
    parent_device: int
    parent_inode: int
    device: int
    inode: int
    owner_uid: int
    _closed: bool = field(default=False, init=False, repr=False)

    def close(self) -> None:
        """Close retained descriptors without deleting the directory."""

        if self._closed:
            return
        self._closed = True
        for descriptor in (self.descriptor, self.parent_descriptor):
            with contextlib.suppress(OSError):
                os.close(descriptor)

    def __enter__(self) -> "OwnedRunRoot":
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()


@dataclass
class OwnedRunLease:
    """Retained exclusive lease bound to one authenticated owned run root."""

    descriptor: int = field(repr=False)
    root_device: int
    root_inode: int
    device: int
    inode: int
    owner_uid: int
    _closed: bool = field(default=False, init=False, repr=False)

    def close(self) -> None:
        """Release the advisory lock by closing its retained descriptor."""

        if self._closed:
            return
        self._closed = True
        with contextlib.suppress(OSError):
            os.close(self.descriptor)

    def __enter__(self) -> "OwnedRunLease":
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()


@dataclass
class StaleOwnedRunClaim:
    """Retained, exclusively claimed candidate; closing never mutates its root."""

    root: OwnedRunRoot
    lease: OwnedRunLease
    _closed: bool = field(default=False, init=False, repr=False)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.lease.close()
        self.root.close()

    def __enter__(self) -> "StaleOwnedRunClaim":
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()


@dataclass(frozen=True, repr=False)
class CalibratedLaunchGrant:
    """Opaque, process-local authorization consumed by one production spawn."""

    _token: str = field(repr=False)

    def __repr__(self) -> str:
        return "CalibratedLaunchGrant(<opaque>)"

    def __copy__(self) -> "CalibratedLaunchGrant":
        raise TypeError("calibrated launch grants cannot be copied")

    def __deepcopy__(self, _memo: object) -> "CalibratedLaunchGrant":
        raise TypeError("calibrated launch grants cannot be copied")


@dataclass(frozen=True, repr=False)
class QuiescentProcessExit:
    """Opaque proof that one owned process group exited cleanly on its own."""

    _token: str = field(repr=False)

    def __repr__(self) -> str:
        return "QuiescentProcessExit(<opaque>)"

    def __copy__(self) -> "QuiescentProcessExit":
        raise TypeError("process-exit attestations cannot be copied")

    def __deepcopy__(self, _memo: object) -> "QuiescentProcessExit":
        raise TypeError("process-exit attestations cannot be copied")


@dataclass(frozen=True)
class OwnedChildStdio:
    """Private regular-file standard streams owned by one child role."""

    stdin: Any
    stdout: Any
    stderr: Any


class _NamedOwnedStream:
    """Small file-object proxy retaining an authenticated human-readable path."""

    def __init__(self, stream: Any, path: Path) -> None:
        self._stream = stream
        self.name = str(path)

    def fileno(self) -> int:
        return int(self._stream.fileno())

    @property
    def closed(self) -> bool:
        return bool(self._stream.closed)

    def close(self) -> None:
        self._stream.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


@dataclass(frozen=True)
class DarwinIsolationContract:
    """All paths and endpoints needed to construct the two Darwin profiles."""

    workspace_root: Path
    source_root: Path
    app_writable_root: Path
    browser_writable_root: Path
    final_evidence_root: Path
    python_executable: Path
    python_runtime_roots: tuple[Path, ...]
    browser_executable: Path
    browser_runtime_roots: tuple[Path, ...]
    production_probe_path: Path
    app_port: int
    denied_port: int


@dataclass(frozen=True)
class DarwinProfiles:
    """Exact Seatbelt source for the app and browser process trees."""

    app: str
    browser: str


@dataclass(frozen=True)
class _LaunchAuthorization:
    session_id: str
    process_id: str
    process_token: str
    role: str
    input_contract: DarwinIsolationContract
    contract: DarwinIsolationContract
    contract_identity: tuple[tuple[Any, ...], ...]
    profiles: DarwinProfiles
    profile_sha256: str
    calibration_sha256: str
    command: tuple[str, ...]
    cwd: Path
    cwd_identity: tuple[int, int, int, int]
    input_environment: tuple[tuple[str, str], ...]
    environment: tuple[tuple[str, str], ...]
    stdio_identity: tuple[tuple[int, int, int, int, int], ...]
    launch_identity_sha256: str


@dataclass(frozen=True)
class _LaunchGrantRegistration:
    grant: CalibratedLaunchGrant
    authorization: _LaunchAuthorization


@dataclass(frozen=True)
class _ProcessFamilyIdentity:
    session_id: str
    process_id: str
    process_token: str
    role: str
    launch_identity_sha256: str
    owner_uid: int


@dataclass
class _ProcessFamilyRegistration:
    identity: _ProcessFamilyIdentity
    state: str
    process: subprocess.Popen[Any] | None = field(default=None, repr=False)
    leader_pid: int | None = None
    process_group: int | None = None


@dataclass(frozen=True)
class _ProcessObservationRow:
    pid: int
    uid: int
    process_group: int
    state: str
    wait_status: int
    has_family_token: bool


@dataclass(frozen=True)
class _ProcessTableObservation:
    rows: tuple[_ProcessObservationRow, ...]


_LAUNCH_GRANTS: dict[str, _LaunchGrantRegistration] = {}
_LAUNCH_GRANTS_LOCK = threading.Lock()
_CALIBRATION_REPORTS: dict[int, Mapping[str, Any]] = {}
_CALIBRATION_REPORT_DIGESTS: dict[int, str] = {}
_CALIBRATION_REPORTS_LOCK = threading.Lock()
_OWNED_STDIO: dict[
    int,
    tuple[
        OwnedChildStdio,
        str,
        Path,
        tuple[int, int, int, int],
        tuple[tuple[int, int, int, int, int], ...],
    ],
] = {}
_OWNED_STDIO_LOCK = threading.Lock()
_PROCESS_FAMILIES_BY_TOKEN: dict[str, _ProcessFamilyRegistration] = {}
_PROCESS_FAMILIES_BY_PROCESS: dict[int, _ProcessFamilyRegistration] = {}
_PROCESS_FAMILIES_LOCK = threading.Lock()
_TERMINATION_ONLY_PROCESS_GROUPS: dict[int, tuple[subprocess.Popen[Any], int]] = {}
_TERMINATION_ONLY_PROCESS_GROUPS_LOCK = threading.Lock()
_QUIESCENT_PROCESS_EXITS: dict[
    str,
    tuple[
        QuiescentProcessExit,
        _ProcessFamilyIdentity,
        Mapping[str, Any],
        str,
    ],
] = {}
_QUIESCENT_PROCESS_EXITS_LOCK = threading.Lock()
_RUNTIME_FILE_DIGESTS: dict[tuple[int, ...], str] = {}
_RUNTIME_FILE_DIGESTS_LOCK = threading.Lock()


_COMMON_CHILD_ENV_KEYS = frozenset(
    {
        "PATH",
        "LANG",
        "LC_ALL",
        "TZ",
        "SOURCE_ROOT",
        "QUANT_RADAR_UX1B_ROLE",
        "PYTHONNOUSERSITE",
        "PYTHONPATH",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONHASHSEED",
        "HOME",
        "TMPDIR",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
    }
)
CHILD_ENV_KEYS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "app": _COMMON_CHILD_ENV_KEYS,
        "browser": _COMMON_CHILD_ENV_KEYS | {"MAC_CHROMIUM_TMPDIR"},
    }
)


def _contract_error(message: str) -> IsolationContractError:
    return IsolationContractError(f"UX-1B isolation contract: {message}")


def _validated_session_id(value: object) -> str:
    if not isinstance(value, str) or _SESSION_ID_PATTERN.fullmatch(value) is None:
        raise _contract_error("process-family session id is invalid")
    return value


def _validated_process_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 512
        or any(
            not (
                character.isascii()
                and (character.isalnum() or character in "._/-")
            )
            for character in value
        )
        or any(component in {"", ".", ".."} for component in value.split("/"))
    ):
        raise _contract_error("process-family process id is invalid")
    return value


def _new_process_token() -> str:
    token = f"ux1b_{secrets.token_hex(32)}"
    if _PROCESS_TOKEN_PATTERN.fullmatch(token) is None:
        raise _contract_error("generated process-family token is invalid")
    return token


def _validated_process_token(value: object) -> str:
    if not isinstance(value, str) or _PROCESS_TOKEN_PATTERN.fullmatch(value) is None:
        raise _contract_error("process-family token is invalid")
    return value


def _validated_timeout(value: object, *, label: str, maximum: float = 120.0) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or not 0 < float(value) <= maximum
    ):
        raise _contract_error(f"{label} timeout is invalid")
    return float(value)


def _validate_relative_component_path(value: str, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value:
        raise _contract_error(f"{label} path must be a non-empty string")
    if "\\" in value or value.startswith("/"):
        raise _contract_error(f"{label} path must be repository-relative")
    components = tuple(value.split("/"))
    if any(component in {"", ".", ".."} for component in components):
        raise _contract_error(f"{label} path has an ambiguous component: {value!r}")
    return components


def _normalize_policy(policy: SourceMirrorPolicy) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not isinstance(policy, SourceMirrorPolicy):
        raise _contract_error("source mirror policy has the wrong type")
    includes: list[str] = []
    excludes: list[str] = []
    for label, values, target in (
        ("include", policy.include, includes),
        ("exclude", policy.exclude, excludes),
    ):
        if not isinstance(values, tuple):
            raise _contract_error(f"{label} rules must be an immutable tuple")
        for raw in values:
            _validate_relative_component_path(raw, label=label)
            target.append(raw)
        if len(target) != len(set(target)):
            raise _contract_error(f"{label} policy contains duplicate paths")
    if not includes:
        raise _contract_error("source mirror include policy is empty")
    for index, left in enumerate(includes):
        for right in includes[index + 1 :]:
            if left.startswith(right + "/") or right.startswith(left + "/"):
                raise _contract_error("source mirror include policy overlaps")
    return tuple(sorted(includes)), tuple(sorted(excludes))


def _relative_is_excluded(relative: str, excludes: Sequence[str]) -> bool:
    parts = relative.split("/")
    for excluded in excludes:
        if excluded.endswith("*"):
            prefix = excluded[:-1]
            if not prefix:
                raise _contract_error("source mirror exclusion cannot be a bare wildcard")
            if "/" not in excluded and any(part.startswith(prefix) for part in parts):
                return True
            if relative.startswith(prefix):
                return True
        excluded_parts = excluded.split("/")
        if len(excluded_parts) == 1 and excluded_parts[0] in parts:
            return True
        if relative == excluded or relative.startswith(excluded + "/"):
            return True
    return False


def _relative_selection(relative: str, includes: Sequence[str]) -> tuple[bool, bool]:
    selected = any(relative == item or relative.startswith(item + "/") for item in includes)
    ancestor = any(item.startswith(relative + "/") for item in includes)
    return selected, ancestor


def _same_stat_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev,
        left.st_ino,
        stat.S_IFMT(left.st_mode),
        left.st_nlink,
        left.st_size,
        left.st_mtime_ns,
        left.st_ctime_ns,
    ) == (
        right.st_dev,
        right.st_ino,
        stat.S_IFMT(right.st_mode),
        right.st_nlink,
        right.st_size,
        right.st_mtime_ns,
        right.st_ctime_ns,
    )


def _kind_label(mode: int) -> str:
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISCHR(mode):
        return "character-device"
    if stat.S_ISBLK(mode):
        return "block-device"
    return "special-file"


def _hash_fd(descriptor: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    os.lseek(descriptor, 0, os.SEEK_SET)
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        size += len(chunk)
    os.lseek(descriptor, 0, os.SEEK_SET)
    return digest.hexdigest(), size


def _copy_regular_file(
    source_directory_fd: int,
    target_directory_fd: int,
    name: str,
    relative: str,
    observed: os.stat_result,
) -> dict[str, Any]:
    if observed.st_nlink != 1:
        raise _contract_error(f"hardlink source rejected: {relative}")
    try:
        source_fd = os.open(name, _SAFE_READ_FLAGS, dir_fd=source_directory_fd)
    except OSError as exc:
        raise _contract_error(f"source file could not be opened safely: {relative}") from exc
    target_fd = -1
    try:
        opened = os.fstat(source_fd)
        if not stat.S_ISREG(opened.st_mode) or not _same_stat_identity(observed, opened):
            raise _contract_error(f"source file changed during open: {relative}")
        target_fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC,
            0o600,
            dir_fd=target_directory_fd,
        )
        digest = hashlib.sha256()
        copied_size = 0
        while True:
            chunk = os.read(source_fd, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            copied_size += len(chunk)
            view = memoryview(chunk)
            while view:
                written = os.write(target_fd, view)
                if written <= 0:
                    raise _contract_error(f"short mirror write: {relative}")
                view = view[written:]
        os.fsync(target_fd)
        after = os.fstat(source_fd)
        if not _same_stat_identity(opened, after) or copied_size != opened.st_size:
            raise _contract_error(f"source file changed while copying: {relative}")
        copied = os.fstat(target_fd)
        if not stat.S_ISREG(copied.st_mode) or copied.st_nlink != 1:
            raise _contract_error(f"mirror destination is not a private regular file: {relative}")
        if (copied.st_dev, copied.st_ino) == (opened.st_dev, opened.st_ino):
            raise _contract_error(f"mirror reused source inode: {relative}")
        copied_mode = 0o555 if opened.st_mode & 0o111 else 0o444
        os.fchmod(target_fd, copied_mode)
        return {
            "path": relative,
            "sha256": digest.hexdigest(),
            "size": copied_size,
            "mode": f"{copied_mode:04o}",
        }
    finally:
        if target_fd >= 0:
            os.close(target_fd)
        os.close(source_fd)


def _copy_projection_directory(
    source_fd: int,
    target_fd: int,
    *,
    relative_parent: str,
    includes: Sequence[str],
    excludes: Sequence[str],
    records: list[dict[str, Any]],
) -> None:
    try:
        names = sorted(os.listdir(source_fd))
    except OSError as exc:
        raise _contract_error("source directory could not be enumerated") from exc
    for name in names:
        if not name or name in {".", ".."} or "/" in name or "\\" in name:
            raise _contract_error("source directory contains an ambiguous name")
        relative = f"{relative_parent}/{name}" if relative_parent else name
        if _relative_is_excluded(relative, excludes):
            continue
        selected, ancestor = _relative_selection(relative, includes)
        if not selected and not ancestor:
            continue
        try:
            observed = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
        except OSError as exc:
            raise _contract_error(f"source entry could not be inspected: {relative}") from exc
        if stat.S_ISLNK(observed.st_mode):
            raise _contract_error(f"symlink source rejected: {relative}")
        if stat.S_ISDIR(observed.st_mode):
            try:
                child_source_fd = os.open(name, _SAFE_DIRECTORY_FLAGS, dir_fd=source_fd)
            except OSError as exc:
                raise _contract_error(f"source directory could not be opened: {relative}") from exc
            child_target_fd = -1
            try:
                opened = os.fstat(child_source_fd)
                if not _same_stat_identity(observed, opened):
                    raise _contract_error(f"source directory changed during open: {relative}")
                os.mkdir(name, 0o700, dir_fd=target_fd)
                child_target_fd = os.open(name, _SAFE_DIRECTORY_FLAGS, dir_fd=target_fd)
                _copy_projection_directory(
                    child_source_fd,
                    child_target_fd,
                    relative_parent=relative,
                    includes=includes,
                    excludes=excludes,
                    records=records,
                )
                after = os.fstat(child_source_fd)
                if not _same_stat_identity(opened, after):
                    raise _contract_error(f"source directory changed while copying: {relative}")
                os.fchmod(child_target_fd, 0o555)
            finally:
                if child_target_fd >= 0:
                    os.close(child_target_fd)
                os.close(child_source_fd)
            continue
        if stat.S_ISREG(observed.st_mode):
            if not selected:
                raise _contract_error(f"include ancestor is not a directory: {relative}")
            records.append(
                _copy_regular_file(source_fd, target_fd, name, relative, observed)
            )
            continue
        raise _contract_error(f"{_kind_label(observed.st_mode)} source rejected: {relative}")


def _safe_existing_directory(path: Path, *, label: str) -> Path:
    unresolved = path.expanduser()
    try:
        observed = unresolved.lstat()
    except OSError as exc:
        raise _contract_error(f"{label} is unavailable") from exc
    if stat.S_ISLNK(observed.st_mode) or not stat.S_ISDIR(observed.st_mode):
        raise _contract_error(f"{label} must be a real directory")
    resolved = unresolved.resolve()
    reopened = resolved.stat(follow_symlinks=False)
    if (observed.st_dev, observed.st_ino) != (reopened.st_dev, reopened.st_ino):
        raise _contract_error(f"{label} changed during authentication")
    return resolved


def _validate_owned_root_handle(handle: OwnedRunRoot) -> None:
    if not isinstance(handle, OwnedRunRoot) or handle._closed:
        raise _contract_error("owned run-root handle is closed or invalid")
    parent = os.fstat(handle.parent_descriptor)
    root = os.fstat(handle.descriptor)
    try:
        named_parent = handle.path.parent.stat(follow_symlinks=False)
    except OSError as exc:
        raise _contract_error("owned run-root parent namespace is unavailable") from exc
    if (
        not stat.S_ISDIR(parent.st_mode)
        or (parent.st_dev, parent.st_ino)
        != (handle.parent_device, handle.parent_inode)
        or not stat.S_ISDIR(named_parent.st_mode)
        or (named_parent.st_dev, named_parent.st_ino)
        != (handle.parent_device, handle.parent_inode)
    ):
        raise _contract_error("owned run-root parent identity changed")
    if (
        not stat.S_ISDIR(root.st_mode)
        or (root.st_dev, root.st_ino) != (handle.device, handle.inode)
        or root.st_uid != handle.owner_uid
        or stat.S_IMODE(root.st_mode) != 0o700
    ):
        raise _contract_error("owned run-root identity or mode changed")
    named = os.stat(
        handle.leaf_name,
        dir_fd=handle.parent_descriptor,
        follow_symlinks=False,
    )
    if (
        not stat.S_ISDIR(named.st_mode)
        or (named.st_dev, named.st_ino) != (handle.device, handle.inode)
    ):
        raise _contract_error("owned run-root namespace entry changed")


def _create_owned_root(
    parent: Path,
    *,
    prefix: str | None = None,
    leaf_name: str | None = None,
) -> OwnedRunRoot:
    if (prefix is None) == (leaf_name is None):
        raise _contract_error("owned run root needs exactly one naming strategy")
    requested_parent = Path(parent).expanduser().absolute()
    parent_path = _safe_existing_directory(requested_parent, label="run-root parent")
    parent_descriptor = os.open(parent_path, _SAFE_DIRECTORY_FLAGS)
    root_descriptor = -1
    created_name: str | None = None
    try:
        parent_stat = os.fstat(parent_descriptor)
        if leaf_name is not None:
            candidates: Iterator[str] = iter((leaf_name,))
        else:
            if (
                not isinstance(prefix, str)
                or not prefix
                or len(prefix) > 100
                or "/" in prefix
                or "\\" in prefix
                or prefix in {".", ".."}
                or "\x00" in prefix
            ):
                raise _contract_error("owned run-root prefix is invalid")
            candidates = (f"{prefix}{secrets.token_hex(16)}" for _ in range(128))
        for candidate in candidates:
            if (
                not candidate
                or candidate in {".", ".."}
                or "/" in candidate
                or "\\" in candidate
                or "\x00" in candidate
            ):
                raise _contract_error("owned run-root leaf name is invalid")
            try:
                os.mkdir(candidate, mode=0o700, dir_fd=parent_descriptor)
            except FileExistsError:
                if leaf_name is not None:
                    raise _contract_error("source-mirror run root already exists")
                continue
            created_name = candidate
            break
        if created_name is None:
            raise _contract_error("could not allocate a collision-safe run root")
        root_descriptor = os.open(
            created_name,
            _SAFE_DIRECTORY_FLAGS,
            dir_fd=parent_descriptor,
        )
        os.fchmod(root_descriptor, 0o700)
        root_stat = os.fstat(root_descriptor)
        if (
            not stat.S_ISDIR(root_stat.st_mode)
            or root_stat.st_uid != os.getuid()
            or stat.S_IMODE(root_stat.st_mode) != 0o700
        ):
            raise _contract_error("new run root is not an owned mode-0700 directory")
        return OwnedRunRoot(
            # Preserve the caller's authenticated absolute spelling for API
            # ergonomics (Darwin commonly aliases /var to /private/var).
            # All security operations continue through the retained FDs.
            path=requested_parent / created_name,
            leaf_name=created_name,
            parent_descriptor=parent_descriptor,
            descriptor=root_descriptor,
            parent_device=parent_stat.st_dev,
            parent_inode=parent_stat.st_ino,
            device=root_stat.st_dev,
            inode=root_stat.st_ino,
            owner_uid=root_stat.st_uid,
        )
    except BaseException:
        if root_descriptor >= 0:
            with contextlib.suppress(OSError):
                os.close(root_descriptor)
        if created_name is not None:
            with contextlib.suppress(OSError):
                os.rmdir(created_name, dir_fd=parent_descriptor)
        with contextlib.suppress(OSError):
            os.close(parent_descriptor)
        raise


def create_owned_run_root(
    parent: Path,
    *,
    prefix: str = "ux1b-run-",
) -> OwnedRunRoot:
    """Create a collision-safe mode-0700 root and retain both namespace FDs."""

    return _create_owned_root(Path(parent), prefix=prefix)


def _validate_owned_run_prefix(prefix: str) -> str:
    if (
        not isinstance(prefix, str)
        or not prefix
        or len(prefix) > 100
        or prefix in {".", ".."}
        or "/" in prefix
        or "\\" in prefix
        or "\x00" in prefix
        or re.search(r"[^A-Za-z0-9._-]", prefix) is not None
    ):
        raise _contract_error("owned run-root prefix is invalid")
    return prefix


def _lease_identity_matches(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev,
        left.st_ino,
        left.st_uid,
        stat.S_IFMT(left.st_mode),
        stat.S_IMODE(left.st_mode),
        left.st_nlink,
    ) == (
        right.st_dev,
        right.st_ino,
        right.st_uid,
        stat.S_IFMT(right.st_mode),
        stat.S_IMODE(right.st_mode),
        right.st_nlink,
    )


def _validate_owned_run_lease(
    root: OwnedRunRoot,
    lease: OwnedRunLease,
) -> None:
    _validate_owned_root_handle(root)
    if not isinstance(lease, OwnedRunLease) or lease._closed:
        raise _contract_error("owned run lease is closed or invalid")
    opened = os.fstat(lease.descriptor)
    try:
        named = os.stat(
            OWNED_RUN_LEASE_NAME,
            dir_fd=root.descriptor,
            follow_symlinks=False,
        )
    except OSError as exc:
        raise _contract_error("owned run lease namespace is unavailable") from exc
    if (
        (root.device, root.inode) != (lease.root_device, lease.root_inode)
        or not stat.S_ISREG(opened.st_mode)
        or opened.st_uid != root.owner_uid
        or stat.S_IMODE(opened.st_mode) != 0o600
        or opened.st_nlink != 1
        or (opened.st_dev, opened.st_ino) != (lease.device, lease.inode)
        or not _lease_identity_matches(named, opened)
    ):
        raise _contract_error("owned run lease identity or mode changed")


def acquire_owned_run_lease(root: OwnedRunRoot) -> OwnedRunLease:
    """Create and retain a mode-0600 exclusive lease inside a new run root."""

    _validate_owned_root_handle(root)
    descriptor = -1
    created_identity: tuple[int, int] | None = None
    try:
        descriptor = os.open(
            OWNED_RUN_LEASE_NAME,
            os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | _NOFOLLOW
            | _CLOEXEC,
            0o600,
            dir_fd=root.descriptor,
        )
        os.set_inheritable(descriptor, False)
        os.fchmod(descriptor, 0o600)
        opened = os.fstat(descriptor)
        created_identity = (opened.st_dev, opened.st_ino)
        named = os.stat(
            OWNED_RUN_LEASE_NAME,
            dir_fd=root.descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_uid != root.owner_uid
            or stat.S_IMODE(opened.st_mode) != 0o600
            or opened.st_nlink != 1
            or not _lease_identity_matches(named, opened)
        ):
            raise _contract_error("new owned run lease is unsafe")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise _contract_error("new owned run lease cannot be locked") from exc
        os.fsync(descriptor)
        os.fsync(root.descriptor)
        lease = OwnedRunLease(
            descriptor=descriptor,
            root_device=root.device,
            root_inode=root.inode,
            device=opened.st_dev,
            inode=opened.st_ino,
            owner_uid=opened.st_uid,
        )
        _validate_owned_run_lease(root, lease)
        descriptor = -1
        return lease
    except BaseException as exc:
        if descriptor >= 0:
            with contextlib.suppress(OSError):
                os.close(descriptor)
        if created_identity is not None:
            try:
                named = os.stat(
                    OWNED_RUN_LEASE_NAME,
                    dir_fd=root.descriptor,
                    follow_symlinks=False,
                )
                if (named.st_dev, named.st_ino) == created_identity:
                    os.unlink(OWNED_RUN_LEASE_NAME, dir_fd=root.descriptor)
                    os.fsync(root.descriptor)
            except OSError:
                pass
        if isinstance(exc, OSError):
            raise _contract_error("owned run lease cannot be created safely") from exc
        raise


def _open_stale_owned_run_claim(
    parent_path: Path,
    parent_fd: int,
    leaf_name: str,
) -> StaleOwnedRunClaim | None:
    claim_parent_fd = -1
    root_fd = -1
    lease_fd = -1
    try:
        named_root = os.stat(
            leaf_name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISDIR(named_root.st_mode)
            or named_root.st_uid != os.getuid()
            or stat.S_IMODE(named_root.st_mode) != 0o700
        ):
            return None
        claim_parent_fd = os.dup(parent_fd)
        os.set_inheritable(claim_parent_fd, False)
        root_fd = os.open(
            leaf_name,
            _SAFE_DIRECTORY_FLAGS,
            dir_fd=claim_parent_fd,
        )
        os.set_inheritable(root_fd, False)
        opened_root = os.fstat(root_fd)
        if (
            not stat.S_ISDIR(opened_root.st_mode)
            or (opened_root.st_dev, opened_root.st_ino)
            != (named_root.st_dev, named_root.st_ino)
            or opened_root.st_uid != os.getuid()
            or stat.S_IMODE(opened_root.st_mode) != 0o700
        ):
            return None
        named_lease = os.stat(
            OWNED_RUN_LEASE_NAME,
            dir_fd=root_fd,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(named_lease.st_mode)
            or named_lease.st_uid != os.getuid()
            or stat.S_IMODE(named_lease.st_mode) != 0o600
            or named_lease.st_nlink != 1
        ):
            return None
        lease_fd = os.open(
            OWNED_RUN_LEASE_NAME,
            os.O_RDWR | _NOFOLLOW | _CLOEXEC,
            dir_fd=root_fd,
        )
        os.set_inheritable(lease_fd, False)
        opened_lease = os.fstat(lease_fd)
        if not _lease_identity_matches(named_lease, opened_lease):
            return None
        try:
            fcntl.flock(lease_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                return None
            raise
        after_root = os.stat(
            leaf_name,
            dir_fd=claim_parent_fd,
            follow_symlinks=False,
        )
        after_lease = os.stat(
            OWNED_RUN_LEASE_NAME,
            dir_fd=root_fd,
            follow_symlinks=False,
        )
        if (
            (after_root.st_dev, after_root.st_ino)
            != (opened_root.st_dev, opened_root.st_ino)
            or not _lease_identity_matches(after_lease, opened_lease)
        ):
            return None
        root = OwnedRunRoot(
            path=parent_path / leaf_name,
            leaf_name=leaf_name,
            parent_descriptor=claim_parent_fd,
            descriptor=root_fd,
            parent_device=os.fstat(claim_parent_fd).st_dev,
            parent_inode=os.fstat(claim_parent_fd).st_ino,
            device=opened_root.st_dev,
            inode=opened_root.st_ino,
            owner_uid=opened_root.st_uid,
        )
        lease = OwnedRunLease(
            descriptor=lease_fd,
            root_device=opened_root.st_dev,
            root_inode=opened_root.st_ino,
            device=opened_lease.st_dev,
            inode=opened_lease.st_ino,
            owner_uid=opened_lease.st_uid,
        )
        _validate_owned_run_lease(root, lease)
        claim_parent_fd = -1
        root_fd = -1
        lease_fd = -1
        return StaleOwnedRunClaim(root=root, lease=lease)
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError as exc:
        if exc.errno in {
            errno.EACCES,
            errno.EAGAIN,
            errno.ELOOP,
            errno.ENOENT,
            errno.ENOTDIR,
        }:
            return None
        raise _contract_error("stale owned run candidate cannot be opened") from exc
    finally:
        for descriptor in (lease_fd, root_fd, claim_parent_fd):
            if descriptor >= 0:
                with contextlib.suppress(OSError):
                    os.close(descriptor)


def claim_stale_owned_run_roots(
    parent: Path,
    *,
    prefix: str,
    max_candidates: int = MAX_STALE_OWNED_RUN_CANDIDATES,
) -> tuple[StaleOwnedRunClaim, ...]:
    """Claim inactive exact-prefix roots without mutating or deleting them."""

    normalized_prefix = _validate_owned_run_prefix(prefix)
    if (
        not isinstance(max_candidates, int)
        or isinstance(max_candidates, bool)
        or not 1 <= max_candidates <= MAX_STALE_OWNED_RUN_CANDIDATES
    ):
        raise _contract_error("stale owned run candidate bound is invalid")
    parent_path = _safe_existing_directory(
        Path(parent).expanduser().absolute(),
        label="stale run-root parent",
    )
    parent_fd = os.open(parent_path, _SAFE_DIRECTORY_FLAGS)
    claims: list[StaleOwnedRunClaim] = []
    try:
        pattern = re.compile(rf"\A{re.escape(normalized_prefix)}[0-9a-f]{{32}}\Z")
        candidates = tuple(
            sorted(name for name in os.listdir(parent_fd) if pattern.fullmatch(name))
        )
        if len(candidates) > max_candidates:
            raise _contract_error("stale owned run candidate bound was exceeded")
        for leaf_name in candidates:
            claim = _open_stale_owned_run_claim(
                parent_path,
                parent_fd,
                leaf_name,
            )
            if claim is not None:
                claims.append(claim)
        return tuple(claims)
    except BaseException:
        for claim in claims:
            claim.close()
        raise
    finally:
        os.close(parent_fd)


def _remove_tree_contents_fd(directory_fd: int, *, owner_uid: int) -> None:
    os.fchmod(directory_fd, 0o700)
    for name in os.listdir(directory_fd):
        observed = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if stat.S_ISDIR(observed.st_mode):
            child_fd = os.open(
                name,
                _SAFE_DIRECTORY_FLAGS,
                dir_fd=directory_fd,
            )
            try:
                opened = os.fstat(child_fd)
                if (
                    (opened.st_dev, opened.st_ino)
                    != (observed.st_dev, observed.st_ino)
                    or opened.st_uid != owner_uid
                ):
                    raise _contract_error("cleanup directory identity or owner changed")
                _remove_tree_contents_fd(child_fd, owner_uid=owner_uid)
            finally:
                os.close(child_fd)
            os.rmdir(name, dir_fd=directory_fd)
            continue
        os.unlink(name, dir_fd=directory_fd)


def remove_owned_run_root(handle: OwnedRunRoot) -> None:
    """Delete one authenticated owned root without following child links."""

    _validate_owned_root_handle(handle)
    try:
        _remove_tree_contents_fd(handle.descriptor, owner_uid=handle.owner_uid)
        _validate_owned_root_handle(handle)
        os.rmdir(handle.leaf_name, dir_fd=handle.parent_descriptor)
    finally:
        handle.close()


@contextlib.contextmanager
def owned_run_root(
    parent: Path,
    *,
    prefix: str = "ux1b-run-",
) -> Iterator[OwnedRunRoot]:
    """Yield a collision-safe private root and descriptor-clean it on exit."""

    handle = create_owned_run_root(parent, prefix=prefix)
    try:
        yield handle
    finally:
        if not handle._closed:
            remove_owned_run_root(handle)


def build_source_mirror(
    *,
    workspace_root: Path | None = None,
    workspace_root_fd: int | None = None,
    run_root: Path,
    policy: SourceMirrorPolicy,
) -> SourceMirror:
    """Copy an allowlisted projection into new, immutable run-owned inodes."""

    if (workspace_root is None) == (workspace_root_fd is None):
        raise _contract_error("source mirror requires exactly one workspace authority")
    if workspace_root_fd is not None and (
        not isinstance(workspace_root_fd, int)
        or isinstance(workspace_root_fd, bool)
        or workspace_root_fd < 0
    ):
        raise _contract_error("source mirror workspace descriptor is invalid")
    includes, excludes = _normalize_policy(policy)
    workspace = (
        _safe_existing_directory(Path(workspace_root), label="workspace root")
        if workspace_root is not None
        else None
    )
    requested_run = Path(run_root).expanduser().absolute()
    handle = _create_owned_root(
        requested_run.parent,
        leaf_name=requested_run.name,
    )
    target_run = handle.path
    source_root = target_run / "source"
    manifest_path = target_run / "mirror-manifest.json"
    try:
        os.mkdir("source", mode=0o700, dir_fd=handle.descriptor)
        try:
            if workspace is not None:
                source_fd = os.open(workspace, _SAFE_DIRECTORY_FLAGS)
            else:
                assert workspace_root_fd is not None
                source_fd = os.dup(workspace_root_fd)
        except OSError as exc:
            raise _contract_error("workspace root cannot be opened safely") from exc
        if not stat.S_ISDIR(os.fstat(source_fd).st_mode):
            os.close(source_fd)
            raise _contract_error("workspace root descriptor is not a directory")
        target_fd = -1
        try:
            target_fd = os.open(
                "source", _SAFE_DIRECTORY_FLAGS, dir_fd=handle.descriptor
            )
            records: list[dict[str, Any]] = []
            _copy_projection_directory(
                source_fd,
                target_fd,
                relative_parent="",
                includes=includes,
                excludes=excludes,
                records=records,
            )
            os.fchmod(target_fd, 0o555)
            source_stat = os.fstat(target_fd)
        finally:
            if target_fd >= 0:
                os.close(target_fd)
            os.close(source_fd)
        records.sort(key=lambda row: row["path"])
        missing = [
            item
            for item in includes
            if not any(
                row["path"] == item or row["path"].startswith(item + "/")
                for row in records
            )
        ]
        if missing:
            raise _contract_error(f"source mirror include paths are missing: {missing!r}")
        digest_payload = {
            "schemaVersion": MIRROR_SCHEMA,
            "files": records,
        }
        digest = hashlib.sha256(
            json.dumps(
                digest_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        manifest = {**digest_payload, "digest": digest}
        payload = (
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")
        if len(payload) > MAX_MIRROR_MANIFEST_BYTES:
            raise _contract_error("source mirror manifest exceeds its size limit")
        descriptor = os.open(
            "mirror-manifest.json",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC,
            0o600,
            dir_fd=handle.descriptor,
        )
        try:
            view = memoryview(payload)
            while view:
                view = view[os.write(descriptor, view) :]
            os.fsync(descriptor)
            os.fchmod(descriptor, 0o400)
            manifest_stat = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        os.fsync(handle.descriptor)
        run_stat = os.fstat(handle.descriptor)
        return SourceMirror(
            source_root=source_root,
            manifest_path=manifest_path,
            digest=digest,
            run_identity=(run_stat.st_dev, run_stat.st_ino),
            source_identity=(source_stat.st_dev, source_stat.st_ino),
            manifest_identity=(manifest_stat.st_dev, manifest_stat.st_ino),
        )
    except BaseException as exc:
        try:
            remove_owned_run_root(handle)
        except BaseException as cleanup_exc:
            handle.close()
            raise cleanup_exc from exc
        raise
    finally:
        handle.close()


def _walk_mirror_files(directory_fd: int, relative_parent: str = "") -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for name in sorted(os.listdir(directory_fd)):
        relative = f"{relative_parent}/{name}" if relative_parent else name
        observed = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if stat.S_ISLNK(observed.st_mode):
            raise _contract_error(f"authenticated mirror contains a symlink: {relative}")
        if stat.S_ISDIR(observed.st_mode):
            if stat.S_IMODE(observed.st_mode) & 0o222:
                raise _contract_error(f"authenticated mirror directory is writable: {relative}")
            child_fd = os.open(name, _SAFE_DIRECTORY_FLAGS, dir_fd=directory_fd)
            try:
                opened = os.fstat(child_fd)
                if not _same_stat_identity(observed, opened):
                    raise _contract_error(f"mirror directory changed during authentication: {relative}")
                records.extend(_walk_mirror_files(child_fd, relative))
                if not _same_stat_identity(opened, os.fstat(child_fd)):
                    raise _contract_error(f"mirror directory changed while authenticating: {relative}")
            finally:
                os.close(child_fd)
            continue
        if not stat.S_ISREG(observed.st_mode):
            raise _contract_error(f"authenticated mirror contains {_kind_label(observed.st_mode)}: {relative}")
        if observed.st_nlink != 1:
            raise _contract_error(f"authenticated mirror contains hardlink: {relative}")
        if stat.S_IMODE(observed.st_mode) & 0o222:
            raise _contract_error(f"authenticated mirror file is writable: {relative}")
        file_fd = os.open(name, _SAFE_READ_FLAGS, dir_fd=directory_fd)
        try:
            opened = os.fstat(file_fd)
            if not _same_stat_identity(observed, opened):
                raise _contract_error(f"mirror file changed during authentication: {relative}")
            digest, size = _hash_fd(file_fd)
            if not _same_stat_identity(opened, os.fstat(file_fd)):
                raise _contract_error(f"mirror file changed while authenticating: {relative}")
            records.append(
                {
                    "path": relative,
                    "sha256": digest,
                    "size": size,
                    "mode": f"{stat.S_IMODE(opened.st_mode):04o}",
                }
            )
        finally:
            os.close(file_fd)
    return records


def authenticate_source_mirror(
    mirror: SourceMirror,
    *,
    expected_digest: str,
) -> dict[str, Any]:
    """Reopen and authenticate a finalized mirror without following links."""

    if not isinstance(mirror, SourceMirror):
        raise _contract_error("source mirror handle has the wrong type")
    if not isinstance(expected_digest, str) or len(expected_digest) != 64:
        raise _contract_error("expected mirror digest is invalid")
    try:
        run_root = _safe_existing_directory(
            mirror.source_root.parent,
            label="source mirror run root",
        )
        source_root = _safe_existing_directory(
            mirror.source_root,
            label="source mirror root",
        )
    except OSError as exc:
        raise _contract_error("source mirror namespace is unavailable") from exc
    run_stat = run_root.stat(follow_symlinks=False)
    root_stat = source_root.stat(follow_symlinks=False)
    if (
        not stat.S_ISDIR(run_stat.st_mode)
        or run_stat.st_uid != os.getuid()
        or stat.S_IMODE(run_stat.st_mode) != 0o700
        or (run_stat.st_dev, run_stat.st_ino) != mirror.run_identity
    ):
        raise _contract_error("source mirror run-root identity changed")
    if (
        not stat.S_ISDIR(root_stat.st_mode)
        or root_stat.st_uid != os.getuid()
        or stat.S_IMODE(root_stat.st_mode) != 0o555
        or (root_stat.st_dev, root_stat.st_ino) != mirror.source_identity
    ):
        raise _contract_error("source mirror root identity changed")
    if mirror.manifest_path.parent.resolve() != run_root:
        raise _contract_error("source mirror manifest escaped its run root")
    try:
        manifest_observed = mirror.manifest_path.stat(follow_symlinks=False)
    except OSError as exc:
        raise _contract_error("source mirror manifest is unavailable") from exc
    if (
        not stat.S_ISREG(manifest_observed.st_mode)
        or manifest_observed.st_nlink != 1
        or manifest_observed.st_uid != os.getuid()
        or stat.S_IMODE(manifest_observed.st_mode) != 0o400
        or (manifest_observed.st_dev, manifest_observed.st_ino)
        != mirror.manifest_identity
        or manifest_observed.st_size > MAX_MIRROR_MANIFEST_BYTES
    ):
        raise _contract_error("source mirror manifest identity, type, or size changed")
    try:
        manifest_fd = os.open(mirror.manifest_path, _SAFE_READ_FLAGS)
    except OSError as exc:
        raise _contract_error("source mirror manifest could not be opened safely") from exc
    try:
        manifest_opened = os.fstat(manifest_fd)
        if (
            not stat.S_ISREG(manifest_opened.st_mode)
            or manifest_opened.st_nlink != 1
            or manifest_opened.st_uid != os.getuid()
            or stat.S_IMODE(manifest_opened.st_mode) != 0o400
            or (manifest_opened.st_dev, manifest_opened.st_ino)
            != mirror.manifest_identity
            or manifest_opened.st_size > MAX_MIRROR_MANIFEST_BYTES
        ):
            raise _contract_error("source mirror manifest changed while opening")
        manifest_bytes = b""
        while True:
            remaining = MAX_MIRROR_MANIFEST_BYTES + 1 - len(manifest_bytes)
            if remaining <= 0:
                raise _contract_error("source mirror manifest exceeds its size limit")
            chunk = os.read(manifest_fd, min(64 * 1024, remaining))
            if not chunk:
                break
            manifest_bytes += chunk
        if not _same_stat_identity(manifest_opened, os.fstat(manifest_fd)):
            raise _contract_error("source mirror manifest changed while reading")
    finally:
        os.close(manifest_fd)
    try:
        manifest = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _contract_error("source mirror manifest is malformed") from exc
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != MIRROR_SCHEMA:
        raise _contract_error("source mirror manifest schema differs")
    if manifest.get("digest") != expected_digest or mirror.digest != expected_digest:
        raise _contract_error("source mirror digest reference differs")
    root_fd = os.open(source_root, _SAFE_DIRECTORY_FLAGS)
    try:
        opened_root = os.fstat(root_fd)
        if (
            not stat.S_ISDIR(opened_root.st_mode)
            or opened_root.st_uid != os.getuid()
            or stat.S_IMODE(opened_root.st_mode) != 0o555
            or (opened_root.st_dev, opened_root.st_ino) != mirror.source_identity
            or not _same_stat_identity(root_stat, opened_root)
        ):
            raise _contract_error("source mirror root changed while opening")
        records = _walk_mirror_files(root_fd)
        final_root = os.fstat(root_fd)
        if not _same_stat_identity(opened_root, final_root):
            raise _contract_error("source mirror root changed while authenticating")
    finally:
        os.close(root_fd)
    records.sort(key=lambda row: row["path"])
    digest_payload = {"schemaVersion": MIRROR_SCHEMA, "files": records}
    actual_digest = hashlib.sha256(
        json.dumps(
            digest_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if actual_digest != expected_digest or manifest.get("files") != records:
        raise _contract_error("source mirror content or metadata changed")
    return {
        "schemaVersion": MIRROR_SCHEMA,
        "passed": True,
        "digest": actual_digest,
        "fileCount": len(records),
    }


def _private_child_directory(parent: Path, name: str) -> Path:
    child = parent / name
    child.mkdir(mode=0o700, exist_ok=True)
    observed = child.stat(follow_symlinks=False)
    if not stat.S_ISDIR(observed.st_mode) or stat.S_IMODE(observed.st_mode) & 0o077:
        raise _contract_error(f"child private directory is not mode 0700: {name}")
    return child


def _python_site_package_roots(runtime_roots: Sequence[Path]) -> tuple[Path, ...]:
    candidates: set[Path] = set()
    for raw_root in runtime_roots:
        root = Path(raw_root).expanduser().absolute()
        if root.name in {"site-packages", "dist-packages"} and root.is_dir():
            candidates.add(root.resolve())
        for pattern in (
            "lib/python*/site-packages",
            "lib/python*/dist-packages",
            "Lib/site-packages",
        ):
            for candidate in root.glob(pattern):
                if candidate.is_dir():
                    candidates.add(candidate.resolve())
    return tuple(sorted(candidates, key=str))


def build_child_environment(
    *,
    role: str,
    source_root: Path,
    writable_root: Path,
    inherited: Mapping[str, str],
    python_runtime_roots: Sequence[Path] = (),
) -> dict[str, str]:
    """Construct a role-scoped child environment from a four-key allowlist."""

    if role not in CHILD_ENV_KEYS:
        raise _contract_error("child role is not app or browser")
    source_input = Path(source_root).expanduser().absolute()
    writable_input = Path(writable_root).expanduser().absolute()
    source_authenticated = _safe_existing_directory(
        source_input, label="child source root"
    )
    writable_authenticated = _safe_existing_directory(
        writable_input, label="child writable root"
    )
    if (
        source_authenticated == writable_authenticated
        or source_authenticated.is_relative_to(writable_authenticated)
        or writable_authenticated.is_relative_to(source_authenticated)
    ):
        raise _contract_error("child source and writable roots overlap")
    # Keep the caller's authenticated absolute spelling.  On Darwin, tempfile
    # paths commonly use ``/var`` while the kernel canonical path is
    # ``/private/var``; changing that spelling would break the child's explicit
    # SOURCE_ROOT/cwd identity even though both descriptors name the same inode.
    source = source_input
    writable = writable_input
    if not isinstance(inherited, Mapping):
        raise _contract_error("inherited child environment is not a mapping")
    runtime_roots = tuple(python_runtime_roots) or (Path(sys.prefix),)
    site_packages = _python_site_package_roots(runtime_roots)
    if not site_packages:
        raise DependencyUnavailable("child Python site-packages are unavailable")
    home = _private_child_directory(writable, "home")
    temporary = _private_child_directory(writable, "tmp")
    cache = _private_child_directory(writable, "cache")
    config = _private_child_directory(writable, "config")
    data = _private_child_directory(writable, "data")
    environment = {
        # Commands are always absolute.  A fixed system PATH avoids forwarding
        # workspace shims, user package managers, or credential-bearing parent
        # configuration into either child.
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
        "SOURCE_ROOT": str(source),
        "QUANT_RADAR_UX1B_ROLE": role,
        "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": os.pathsep.join(str(path) for path in site_packages),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "HOME": str(home),
        "TMPDIR": str(temporary),
        "XDG_CACHE_HOME": str(cache),
        "XDG_CONFIG_HOME": str(config),
        "XDG_DATA_HOME": str(data),
    }
    if role == "browser":
        chromium_temporary = _private_child_directory(writable, "chromium-tmp")
        longest_singleton_path = chromium_temporary / (
            "com.google.chrome.for.testing." + "X" * 6
        ) / "SingletonSocket"
        if len(os.fsencode(str(longest_singleton_path))) > 253:
            raise _contract_error("browser Chromium singleton path is too long")
        environment["MAC_CHROMIUM_TMPDIR"] = str(chromium_temporary)
    if set(environment) != set(CHILD_ENV_KEYS[role]):
        raise _contract_error("child environment does not match its exact allowlist")
    return environment


def _runtime_child_environment(
    environment: Mapping[str, str], *, process_token: str
) -> dict[str, str]:
    if not isinstance(environment, Mapping):
        raise _contract_error("process-family environment is not a mapping")
    role = environment.get("QUANT_RADAR_UX1B_ROLE")
    if role not in CHILD_ENV_KEYS or set(environment) != set(CHILD_ENV_KEYS[role]):
        raise _contract_error("process-family base environment is not an exact role allowlist")
    token = _validated_process_token(process_token)
    runtime = dict(environment)
    runtime[PROCESS_TOKEN_ENV_KEY] = token
    return runtime


@contextlib.contextmanager
def owned_child_stdio(root: Path, *, role: str) -> Iterator[OwnedChildStdio]:
    """Open private regular-file stdio without inheriting coordinator streams."""

    if role not in CHILD_ENV_KEYS:
        raise _contract_error("stdio role is not app or browser")
    stdio_root = Path(root)
    if stdio_root.exists() or stdio_root.is_symlink():
        raise _contract_error("owned stdio root already exists")
    parent = _safe_existing_directory(stdio_root.parent, label="stdio parent")
    stdio_root = parent / stdio_root.name
    stdio_root.mkdir(mode=0o700)
    descriptors: list[int] = []
    streams: list[Any] = []
    try:
        for name in ("stdin", "stdout", "stderr"):
            descriptor = os.open(
                stdio_root / f"{role}-{name}.log",
                os.O_RDWR | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC,
                0o600,
            )
            descriptors.append(descriptor)
        raw_streams = [
            os.fdopen(descriptors[0], "rb", buffering=0),
            os.fdopen(descriptors[1], "ab", buffering=0),
            os.fdopen(descriptors[2], "ab", buffering=0),
        ]
        streams = [
            _NamedOwnedStream(stream, stdio_root / f"{role}-{name}.log")
            for stream, name in zip(raw_streams, ("stdin", "stdout", "stderr"))
        ]
        descriptors.clear()
        owned = OwnedChildStdio(*streams)
        root_stat = stdio_root.stat(follow_symlinks=False)
        root_identity = (
            root_stat.st_dev,
            root_stat.st_ino,
            root_stat.st_uid,
            stat.S_IMODE(root_stat.st_mode),
        )
        stream_identities = tuple(
            (
                observed.st_dev,
                observed.st_ino,
                observed.st_uid,
                stat.S_IMODE(observed.st_mode),
                observed.st_nlink,
            )
            for observed in (os.fstat(stream.fileno()) for stream in streams)
        )
        with _OWNED_STDIO_LOCK:
            _OWNED_STDIO[id(owned)] = (
                owned,
                role,
                stdio_root,
                root_identity,
                stream_identities,
            )
        try:
            yield owned
        finally:
            with _OWNED_STDIO_LOCK:
                _OWNED_STDIO.pop(id(owned), None)
    finally:
        for stream in streams:
            with contextlib.suppress(Exception):
                stream.close()
        for descriptor in descriptors:
            with contextlib.suppress(OSError):
                os.close(descriptor)


def child_popen_kwargs(
    *,
    cwd: Path,
    environment: Mapping[str, str],
    stdio: OwnedChildStdio,
) -> dict[str, Any]:
    """Return the single allowed Popen shape for evidence children."""

    source_input = Path(cwd).expanduser().absolute()
    _safe_existing_directory(source_input, label="child cwd")
    if not isinstance(stdio, OwnedChildStdio):
        raise _contract_error("child stdio handle has the wrong type")
    if not isinstance(environment, Mapping):
        raise _contract_error("child environment has the wrong type")
    role = environment.get("QUANT_RADAR_UX1B_ROLE")
    allowed_keys = set(CHILD_ENV_KEYS.get(role, ()))
    observed_keys = set(environment)
    if role not in CHILD_ENV_KEYS or frozenset(observed_keys) not in {
        frozenset(allowed_keys),
        frozenset((*allowed_keys, PROCESS_TOKEN_ENV_KEY)),
    }:
        raise _contract_error("child environment is not an exact role allowlist")
    if PROCESS_TOKEN_ENV_KEY in environment:
        _validated_process_token(environment[PROCESS_TOKEN_ENV_KEY])
    _owned_stdio_identity(stdio, expected_role=role)
    return {
        "cwd": str(source_input),
        "env": dict(environment),
        "stdin": stdio.stdin,
        "stdout": stdio.stdout,
        "stderr": stdio.stderr,
        "close_fds": True,
        "pass_fds": (),
        "start_new_session": True,
    }


def spawn_owned_child(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    stdio: OwnedChildStdio,
    test_only: bool = False,
) -> subprocess.Popen[Any]:
    """Exercise the low-level spawn shape in tests; production uses a grant."""

    if test_only is not True:
        raise _contract_error(
            "direct owned-child spawn is test-only; use spawn_calibrated_child"
        )

    if not isinstance(command, (tuple, list)) or not command:
        raise _contract_error("owned child command is empty")
    if any(not isinstance(argument, str) or "\x00" in argument for argument in command):
        raise _contract_error("owned child command contains an invalid argument")
    process = subprocess.Popen(
        list(command),
        **child_popen_kwargs(cwd=cwd, environment=environment, stdio=stdio),
    )
    if isinstance(process, _POPEN_CLASS):
        _register_owned_process_group(process)
    return process


def _owned_stdio_identity(
    stdio: OwnedChildStdio,
    *,
    expected_role: str,
    allowed_root: Path | None = None,
) -> tuple[tuple[int, int, int, int, int], ...]:
    if not isinstance(stdio, OwnedChildStdio):
        raise _contract_error("calibrated launch stdio is not coordinator-owned")
    with _OWNED_STDIO_LOCK:
        registration = _OWNED_STDIO.get(id(stdio))
    if registration is None or registration[0] is not stdio:
        raise _contract_error("calibrated launch stdio lacks coordinator provenance")
    _owned, registered_role, root, expected_root_identity, expected_identities = registration
    if registered_role != expected_role:
        raise _contract_error("calibrated launch stdio role differs")
    try:
        root_stat = root.stat(follow_symlinks=False)
    except OSError as exc:
        raise _contract_error("calibrated launch stdio root is unavailable") from exc
    root_identity = (
        root_stat.st_dev,
        root_stat.st_ino,
        root_stat.st_uid,
        stat.S_IMODE(root_stat.st_mode),
    )
    if (
        not stat.S_ISDIR(root_stat.st_mode)
        or root_identity != expected_root_identity
        or root_identity[2] != os.getuid()
        or root_identity[3] != 0o700
    ):
        raise _contract_error("calibrated launch stdio root identity changed")
    if allowed_root is not None:
        allowed = _safe_existing_directory(allowed_root, label="stdio allowed root")
        authenticated_root = _safe_existing_directory(root, label="stdio root")
        if authenticated_root == allowed or not authenticated_root.is_relative_to(allowed):
            raise _contract_error("calibrated launch stdio escaped its role root")
    identities: list[tuple[int, int, int, int, int]] = []
    for name, stream in (
        ("stdin", stdio.stdin),
        ("stdout", stdio.stdout),
        ("stderr", stdio.stderr),
    ):
        try:
            observed = os.fstat(stream.fileno())
        except (AttributeError, OSError, ValueError) as exc:
            raise _contract_error(f"calibrated launch {name} is unavailable") from exc
        mode = stat.S_IMODE(observed.st_mode)
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_nlink != 1
            or observed.st_uid != os.getuid()
            or mode & 0o077
        ):
            raise _contract_error(
                f"calibrated launch {name} is not an owned private regular file"
            )
        identities.append(
            (
                observed.st_dev,
                observed.st_ino,
                observed.st_uid,
                mode,
                observed.st_nlink,
            )
        )
    if len({identity[:2] for identity in identities}) != 3:
        raise _contract_error("calibrated launch stdio files are not distinct")
    result = tuple(identities)
    if result != expected_identities:
        raise _contract_error("calibrated launch stdio identity changed")
    return result


def _launch_calibration_sha256(
    calibration: Mapping[str, Any],
    *,
    role: str,
    profile: str,
) -> str:
    if not isinstance(calibration, Mapping):
        raise _contract_error("calibrated launch report has the wrong type")
    with _CALIBRATION_REPORTS_LOCK:
        registered = _CALIBRATION_REPORTS.get(id(calibration))
        frozen_digest = _CALIBRATION_REPORT_DIGESTS.get(id(calibration))
    if registered is not calibration:
        raise _contract_error("calibrated launch report lacks live provenance")
    row = calibration.get(role)
    expected_sha256 = hashlib.sha256(profile.encode("utf-8")).hexdigest()
    if (
        calibration.get("schemaVersion") != CALIBRATION_SCHEMA
        or calibration.get("capability") != "supported"
        or calibration.get("passed") is not True
        or calibration.get("profilesAreDistinct") is not True
        or not isinstance(calibration.get("launchIdentitySha256"), str)
        or len(calibration["launchIdentitySha256"]) != 64
        or any(
            character not in "0123456789abcdef"
            for character in calibration["launchIdentitySha256"]
        )
        or not isinstance(row, Mapping)
        or row.get("passed") is not True
        or row.get("profileSha256") != expected_sha256
        or not isinstance(row.get("allowed"), Mapping)
        or set(row["allowed"])
        != (_APP_ALLOWED if role == "app" else _BROWSER_ALLOWED)
        or not all(value is True for value in row["allowed"].values())
        or not isinstance(row.get("denied"), Mapping)
        or set(row["denied"])
        != (_APP_DENIED if role == "app" else _BROWSER_DENIED)
        or not all(value is True for value in row["denied"].values())
    ):
        raise _contract_error("calibrated launch report is not a passing exact profile")
    try:
        payload = json.dumps(
            calibration,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise _contract_error("calibrated launch report is not canonical JSON") from exc
    current_digest = hashlib.sha256(payload).hexdigest()
    if frozen_digest != current_digest:
        raise _contract_error("calibrated launch report changed after registration")
    return current_digest


def validate_live_calibration_provenance(
    calibration: Mapping[str, Any],
) -> str:
    """Return the digest of an exact, live calibration report object.

    Evidence finalization needs to attest that a calibration document came
    from this process's successful calibration run, without weakening the
    role-specific checks performed by ``_launch_calibration_sha256``.  The
    object-identity registry is authoritative; a copied or reconstructed
    mapping is rejected even when its bytes are identical.
    """

    if not isinstance(calibration, Mapping):
        raise _contract_error("calibration report has the wrong type")
    with _CALIBRATION_REPORTS_LOCK:
        registered = _CALIBRATION_REPORTS.get(id(calibration))
        frozen_digest = _CALIBRATION_REPORT_DIGESTS.get(id(calibration))
    if registered is not calibration:
        raise _contract_error("calibration report lacks live provenance")
    def is_sha256(value: object) -> bool:
        return (
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
        )

    if (
        calibration.get("schemaVersion") != CALIBRATION_SCHEMA
        or calibration.get("capability") != "supported"
        or calibration.get("passed") is not True
        or calibration.get("profilesAreDistinct") is not True
        or not is_sha256(calibration.get("launchIdentitySha256"))
    ):
        raise _contract_error("calibration report is not passing")
    for role in ("app", "browser"):
        row = calibration.get(role)
        allowed_keys = _APP_ALLOWED if role == "app" else _BROWSER_ALLOWED
        denied_keys = _APP_DENIED if role == "app" else _BROWSER_DENIED
        if (
            not isinstance(row, Mapping)
            or row.get("passed") is not True
            or not is_sha256(row.get("profileSha256"))
            or not isinstance(row.get("allowed"), Mapping)
            or set(row["allowed"]) != allowed_keys
            or not all(value is True for value in row["allowed"].values())
            or not isinstance(row.get("denied"), Mapping)
            or set(row["denied"]) != denied_keys
            or not all(value is True for value in row["denied"].values())
        ):
            raise _contract_error(f"calibration report {role} row is not passing")
    try:
        payload = json.dumps(
            calibration,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise _contract_error("calibration report is not canonical JSON") from exc
    current_digest = hashlib.sha256(payload).hexdigest()
    if frozen_digest != current_digest:
        raise _contract_error("calibration report changed after live registration")
    return current_digest


def _runtime_file_digest(descriptor: int, opened: os.stat_result) -> str:
    cache_key = (
        opened.st_dev,
        opened.st_ino,
        stat.S_IFMT(opened.st_mode),
        opened.st_nlink,
        opened.st_size,
        opened.st_mtime_ns,
        opened.st_ctime_ns,
    )
    with _RUNTIME_FILE_DIGESTS_LOCK:
        cached = _RUNTIME_FILE_DIGESTS.get(cache_key)
    if cached is not None:
        return cached
    digest, size = _hash_fd(descriptor)
    if size != opened.st_size or not _same_stat_identity(opened, os.fstat(descriptor)):
        raise _contract_error("runtime file changed while hashing")
    with _RUNTIME_FILE_DIGESTS_LOCK:
        if len(_RUNTIME_FILE_DIGESTS) >= 65536:
            _RUNTIME_FILE_DIGESTS.clear()
        _RUNTIME_FILE_DIGESTS[cache_key] = digest
    return digest


def _runtime_tree_pass(root: Path) -> str:
    digest = hashlib.sha256()
    try:
        walker = os.fwalk(root, topdown=True, follow_symlinks=False)
        for directory_path, directory_names, file_names, directory_fd in walker:
            directory_names.sort()
            file_names.sort()
            directory = Path(directory_path)
            relative_directory = directory.relative_to(root).as_posix()
            if relative_directory == ".":
                relative_directory = ""
            before = os.fstat(directory_fd)
            if not stat.S_ISDIR(before.st_mode):
                raise _contract_error("runtime tree contains a non-directory walk root")
            directory_record = (
                "directory",
                relative_directory,
                before.st_dev,
                before.st_ino,
                before.st_uid,
                stat.S_IMODE(before.st_mode),
                before.st_nlink,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            digest.update(
                json.dumps(directory_record, separators=(",", ":")).encode("utf-8")
                + b"\n"
            )
            for name in sorted(set(directory_names) | set(file_names)):
                observed = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                relative = (
                    f"{relative_directory}/{name}" if relative_directory else name
                )
                if stat.S_ISDIR(observed.st_mode):
                    continue
                if stat.S_ISLNK(observed.st_mode):
                    target = os.readlink(name, dir_fd=directory_fd)
                    record = (
                        "symlink",
                        relative,
                        observed.st_dev,
                        observed.st_ino,
                        observed.st_uid,
                        stat.S_IMODE(observed.st_mode),
                        observed.st_nlink,
                        observed.st_mtime_ns,
                        observed.st_ctime_ns,
                        target,
                    )
                elif stat.S_ISREG(observed.st_mode):
                    descriptor = os.open(name, _SAFE_READ_FLAGS, dir_fd=directory_fd)
                    try:
                        opened = os.fstat(descriptor)
                        if not _same_stat_identity(observed, opened):
                            raise _contract_error("runtime file changed while opening")
                        file_digest = _runtime_file_digest(descriptor, opened)
                        if not _same_stat_identity(opened, os.fstat(descriptor)):
                            raise _contract_error("runtime file changed while freezing")
                    finally:
                        os.close(descriptor)
                    record = (
                        "file",
                        relative,
                        opened.st_dev,
                        opened.st_ino,
                        opened.st_uid,
                        stat.S_IMODE(opened.st_mode),
                        opened.st_nlink,
                        opened.st_size,
                        opened.st_mtime_ns,
                        opened.st_ctime_ns,
                        file_digest,
                    )
                else:
                    raise _contract_error(
                        f"runtime tree contains an unsupported entry: {relative}"
                    )
                digest.update(
                    json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode(
                        "utf-8"
                    )
                    + b"\n"
                )
            if not _same_stat_identity(before, os.fstat(directory_fd)):
                raise _contract_error("runtime directory changed while freezing")
    except OSError as exc:
        raise _contract_error("runtime tree could not be frozen") from exc
    return digest.hexdigest()


def _runtime_tree_sha256(root: Path) -> str:
    authenticated = _safe_existing_directory(root, label="runtime digest root")
    first = _runtime_tree_pass(authenticated)
    second = _runtime_tree_pass(authenticated)
    if first != second:
        raise _contract_error("runtime tree changed between identity passes")
    return first


def _bound_contract_identity(
    contract: DarwinIsolationContract,
) -> tuple[tuple[Any, ...], ...]:
    rows: list[tuple[Any, ...]] = []
    directory_items = (
        ("workspace", contract.workspace_root),
        ("source", contract.source_root),
        ("app", contract.app_writable_root),
        ("browser", contract.browser_writable_root),
        ("final", contract.final_evidence_root),
        *((f"python-runtime-{index}", path) for index, path in enumerate(contract.python_runtime_roots)),
        *((f"browser-runtime-{index}", path) for index, path in enumerate(contract.browser_runtime_roots)),
    )
    for label, path in directory_items:
        authenticated = _safe_existing_directory(Path(path), label=f"bound {label}")
        observed = authenticated.stat(follow_symlinks=False)
        runtime_digest = (
            _runtime_tree_sha256(authenticated)
            if label.startswith(("python-runtime-", "browser-runtime-"))
            else None
        )
        rows.append(
            (
                "directory",
                label,
                str(authenticated),
                observed.st_dev,
                observed.st_ino,
                observed.st_uid,
                stat.S_IMODE(observed.st_mode),
                runtime_digest,
            )
        )
    file_items: list[tuple[str, Path]] = [
        ("python-executable", contract.python_executable),
        ("browser-executable", contract.browser_executable),
        ("production-probe", contract.production_probe_path),
    ]
    file_items.extend(
        (f"playwright-driver-{index}", path)
        for index, path in enumerate(
            _playwright_driver_executables(contract.python_runtime_roots)
        )
    )
    file_items.extend(
        (f"browser-bundle-executable-{index}", path)
        for index, path in enumerate(
            _browser_bundle_executable_files(
                _browser_bundle_root(contract.browser_executable)
            )
        )
    )
    seen_files: set[Path] = set()
    for label, path in file_items:
        resolved = Path(path).resolve()
        if resolved in seen_files:
            continue
        seen_files.add(resolved)
        try:
            descriptor = os.open(resolved, _SAFE_READ_FLAGS)
        except OSError as exc:
            raise _contract_error(f"bound {label} is unavailable") from exc
        try:
            observed = os.fstat(descriptor)
            if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
                raise _contract_error(f"bound {label} is not a one-link regular file")
            digest, size = _hash_fd(descriptor)
            if not _same_stat_identity(observed, os.fstat(descriptor)):
                raise _contract_error(f"bound {label} changed while hashing")
        finally:
            os.close(descriptor)
        rows.append(
            (
                "file",
                label,
                str(resolved),
                observed.st_dev,
                observed.st_ino,
                observed.st_uid,
                stat.S_IMODE(observed.st_mode),
                size,
                digest,
            )
        )
    return tuple(rows)


def _identity_rows_sha256(rows: Sequence[Sequence[Any]]) -> str:
    payload = json.dumps(
        rows,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _contract_identity_sha256(contract: DarwinIsolationContract) -> str:
    return _identity_rows_sha256(_bound_contract_identity(contract))


def _launch_identity_sha256(
    *,
    session_id: str,
    process_id: str,
    process_token: str,
    role: str,
    contract_identity: Sequence[Sequence[Any]],
    command: Sequence[str],
    cwd: Path,
    cwd_identity: Sequence[int],
    input_environment: Sequence[Sequence[str]],
    environment: Sequence[Sequence[str]],
    stdio_identity: Sequence[Sequence[int]],
) -> str:
    payload = {
        "sessionId": session_id,
        "processId": process_id,
        "processToken": process_token,
        "role": role,
        "contractIdentity": contract_identity,
        "command": command,
        "cwd": str(cwd),
        "cwdIdentity": cwd_identity,
        "inputEnvironment": input_environment,
        "runtimeEnvironment": environment,
        "stdioIdentity": stdio_identity,
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _validated_browser_relative_argument(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 512
        or value.startswith(("/", "-"))
        or "\\" in value
        or "\x00" in value
        or any(
            not (character.isascii() and (character.isalnum() or character in "._/-"))
            for character in value
        )
        or any(component in {"", ".", ".."} for component in value.split("/"))
    ):
        raise _contract_error(f"browser worker {label} is not a safe relative value")
    return value


def _validated_role_launch_command(
    contract: DarwinIsolationContract,
    profiles: DarwinProfiles,
    *,
    role: str,
    command: Sequence[str],
) -> tuple[str, ...]:
    """Validate the exact interpreter boundary before any runtime discovery.

    App commands retain their existing calibrated Python entrypoint because the
    app profile denies process creation.  The browser profile permits its
    calibrated descendants, so its production Python process is restricted to
    the one frozen mirrored worker and that worker's fixed argument grammar.
    """

    if not isinstance(contract, DarwinIsolationContract):
        raise _contract_error("calibrated launch contract has the wrong type")
    if not isinstance(profiles, DarwinProfiles):
        raise _contract_error("calibrated launch profiles have the wrong type")
    if role not in CHILD_ENV_KEYS:
        raise _contract_error("calibrated launch role is not app or browser")
    if not isinstance(command, (tuple, list)) or len(command) < 4:
        raise _contract_error("calibrated launch command is incomplete")
    exact_command = tuple(command)
    if any(
        not isinstance(argument, str) or "\x00" in argument
        for argument in exact_command
    ):
        raise _contract_error("calibrated launch command contains an invalid argument")
    profile = profiles.app if role == "app" else profiles.browser
    expected_prefix = (
        str(SANDBOX_EXEC),
        "-p",
        profile,
        str(contract.python_executable),
    )
    if exact_command[:4] != expected_prefix:
        raise _contract_error("calibrated launch command is not the exact role profile")
    if role == "app":
        return exact_command

    if len(exact_command) not in {15, 17, 19, 21}:
        raise _contract_error("browser launch is not the fixed worker command")
    if exact_command[4] != BROWSER_WORKER_ENTRYPOINT:
        raise _contract_error("browser launch entrypoint is not the frozen relative worker")
    arguments = exact_command[5:]
    if (
        arguments[0] != "--expected-origin"
        or arguments[2] != "--expected-request-id"
    ):
        raise _contract_error("browser launch worker arguments are not in fixed order")
    expected_origin = f"http://127.0.0.1:{contract.app_port}"
    if arguments[1] != expected_origin:
        raise _contract_error("browser launch origin differs from the calibrated app port")
    _validated_browser_relative_argument(arguments[3], label="request id")
    cursor = 4
    staging_values: list[str] = []
    while (
        cursor + 1 < len(arguments)
        and arguments[cursor] == "--allow-staging-path"
        and len(staging_values) < 4
    ):
        staging_values.append(
            _validated_browser_relative_argument(
                arguments[cursor + 1],
                label="staging path",
            )
        )
        cursor += 2
    staging_paths = tuple(staging_values)
    if (
        len(staging_paths) not in {2, 4}
        or len(set(staging_paths)) != len(staging_paths)
        or staging_paths != tuple(sorted(staging_paths))
    ):
        raise _contract_error("browser launch staging paths are not distinct and canonical")
    if (
        cursor + 1 < len(arguments)
        and arguments[cursor] == "--browser-executable"
    ):
        if (
            arguments[cursor + 1] != str(contract.browser_executable)
        ):
            raise _contract_error(
                "browser launch executable differs from calibrated Chromium"
            )
        cursor += 2
    if (
        cursor + 2 != len(arguments)
        or arguments[cursor] != "--timeout-ms"
    ):
        raise _contract_error("browser launch timeout argument is missing")
    timeout_text = arguments[cursor + 1]
    if (
        not timeout_text.isascii()
        or not timeout_text.isdecimal()
    ):
        raise _contract_error("browser launch timeout is outside the fixed range")
    timeout_ms = int(timeout_text, 10)
    if (
        str(timeout_ms) != timeout_text
        or not (
            BROWSER_WORKER_TIMEOUT_MIN_MS
            <= timeout_ms
            <= BROWSER_WORKER_TIMEOUT_MAX_MS
        )
    ):
        raise _contract_error("browser launch timeout is outside the fixed range")
    return exact_command


def _browser_worker_identity(source_root: Path) -> tuple[Any, ...]:
    """Authenticate and hash the frozen worker through mirror-relative fds."""

    components = tuple(BROWSER_WORKER_ENTRYPOINT.split("/"))
    root_descriptor = os.open(source_root, _SAFE_DIRECTORY_FLAGS)
    parent_descriptor = root_descriptor
    opened_directories: list[int] = []
    leaf_descriptor = -1
    try:
        for component in components[:-1]:
            child_descriptor = os.open(
                component,
                _SAFE_DIRECTORY_FLAGS,
                dir_fd=parent_descriptor,
            )
            opened = os.fstat(child_descriptor)
            if (
                not stat.S_ISDIR(opened.st_mode)
                or opened.st_uid != os.getuid()
                or stat.S_IMODE(opened.st_mode) & 0o222
            ):
                os.close(child_descriptor)
                raise _contract_error("browser worker parent is not immutable")
            opened_directories.append(child_descriptor)
            parent_descriptor = child_descriptor
        leaf = components[-1]
        named = os.stat(leaf, dir_fd=parent_descriptor, follow_symlinks=False)
        leaf_descriptor = os.open(leaf, _SAFE_READ_FLAGS, dir_fd=parent_descriptor)
        opened = os.fstat(leaf_descriptor)
        if (
            not stat.S_ISREG(named.st_mode)
            or not stat.S_ISREG(opened.st_mode)
            or not _same_stat_identity(named, opened)
            or opened.st_uid != os.getuid()
            or opened.st_nlink != 1
            or stat.S_IMODE(opened.st_mode) & 0o222
        ):
            raise _contract_error("browser worker is not an immutable one-link file")
        digest, size = _hash_fd(leaf_descriptor)
        after = os.fstat(leaf_descriptor)
        if size != opened.st_size or not _same_stat_identity(opened, after):
            raise _contract_error("browser worker changed while binding launch")
        return (
            "file",
            "browser-worker-entrypoint",
            BROWSER_WORKER_ENTRYPOINT,
            opened.st_dev,
            opened.st_ino,
            opened.st_uid,
            stat.S_IMODE(opened.st_mode),
            opened.st_nlink,
            size,
            digest,
        )
    except OSError as exc:
        raise _contract_error("browser worker entrypoint is unavailable") from exc
    finally:
        if leaf_descriptor >= 0:
            os.close(leaf_descriptor)
        for descriptor in reversed(opened_directories):
            os.close(descriptor)
        os.close(root_descriptor)


def _launch_contract_identity(
    contract: DarwinIsolationContract,
    *,
    role: str,
) -> tuple[tuple[Any, ...], ...]:
    rows = _bound_contract_identity(contract)
    if role == "browser":
        return (*rows, _browser_worker_identity(contract.source_root))
    return rows


def _build_launch_authorization(
    *,
    session_id: str,
    process_id: str,
    contract: DarwinIsolationContract,
    profiles: DarwinProfiles,
    calibration: Mapping[str, Any],
    role: str,
    command: Sequence[str],
    cwd: Path,
    environment: Mapping[str, str],
    stdio: OwnedChildStdio,
) -> _LaunchAuthorization:
    bound_session_id = _validated_session_id(session_id)
    bound_process_id = _validated_process_id(process_id)
    process_token = _new_process_token()
    exact_command = _validated_role_launch_command(
        contract,
        profiles,
        role=role,
        command=command,
    )
    value = _validated_contract(contract)
    if profiles != build_darwin_profiles(value):
        raise _contract_error("calibrated launch profiles differ from production")
    profile = profiles.app if role == "app" else profiles.browser
    exact_command = _validated_role_launch_command(
        value,
        profiles,
        role=role,
        command=exact_command,
    )
    cwd_input = Path(cwd).expanduser().absolute()
    cwd_authenticated = _safe_existing_directory(cwd_input, label="calibrated launch cwd")
    if cwd_authenticated != value.source_root:
        raise _contract_error("calibrated launch cwd is not the source mirror")
    cwd_stat = cwd_authenticated.stat(follow_symlinks=False)
    cwd_identity = (
        cwd_stat.st_dev,
        cwd_stat.st_ino,
        cwd_stat.st_uid,
        stat.S_IMODE(cwd_stat.st_mode),
    )
    if (
        cwd_stat.st_uid != os.getuid()
        or not stat.S_ISDIR(cwd_stat.st_mode)
        or cwd_identity[3] & 0o222
    ):
        raise _contract_error("calibrated launch cwd is not an owned read-only mirror")
    if (
        not isinstance(environment, Mapping)
        or set(environment) != set(CHILD_ENV_KEYS[role])
        or environment.get("QUANT_RADAR_UX1B_ROLE") != role
        or environment.get("SOURCE_ROOT") != str(cwd_input)
        or any(not isinstance(key, str) or not isinstance(item, str) for key, item in environment.items())
    ):
        raise _contract_error("calibrated launch environment differs from its role")
    profile_sha256 = hashlib.sha256(profile.encode("utf-8")).hexdigest()
    calibrated_contract_identity = _bound_contract_identity(value)
    if calibration.get("launchIdentitySha256") != _identity_rows_sha256(
        calibrated_contract_identity
    ):
        raise _contract_error("calibration runtime identity differs from launch")
    contract_identity = calibrated_contract_identity
    if role == "browser":
        contract_identity = (
            *calibrated_contract_identity,
            _browser_worker_identity(value.source_root),
        )
    input_environment = tuple(sorted(environment.items()))
    runtime_environment = tuple(
        sorted(
            _runtime_child_environment(
                environment,
                process_token=process_token,
            ).items()
        )
    )
    stdio_identity = _owned_stdio_identity(
        stdio,
        expected_role=role,
        allowed_root=(
            value.app_writable_root
            if role == "app"
            else value.browser_writable_root
        ),
    )
    launch_identity_sha256 = _launch_identity_sha256(
        session_id=bound_session_id,
        process_id=bound_process_id,
        process_token=process_token,
        role=role,
        contract_identity=contract_identity,
        command=exact_command,
        cwd=cwd_input,
        cwd_identity=cwd_identity,
        input_environment=input_environment,
        environment=runtime_environment,
        stdio_identity=stdio_identity,
    )
    return _LaunchAuthorization(
        session_id=bound_session_id,
        process_id=bound_process_id,
        process_token=process_token,
        role=role,
        input_contract=contract,
        contract=value,
        contract_identity=contract_identity,
        profiles=profiles,
        profile_sha256=profile_sha256,
        calibration_sha256=_launch_calibration_sha256(
            calibration,
            role=role,
            profile=profile,
        ),
        command=exact_command,
        cwd=cwd_input,
        cwd_identity=cwd_identity,
        input_environment=input_environment,
        environment=runtime_environment,
        stdio_identity=stdio_identity,
        launch_identity_sha256=launch_identity_sha256,
    )


def authorize_calibrated_launch(
    *,
    session_id: str,
    process_id: str,
    contract: DarwinIsolationContract,
    profiles: DarwinProfiles,
    calibration: Mapping[str, Any],
    role: str,
    command: Sequence[str],
    cwd: Path,
    environment: Mapping[str, str],
    stdio: OwnedChildStdio,
) -> CalibratedLaunchGrant:
    """Bind a passing calibration and exact spawn inputs to one opaque grant."""

    authorization = _build_launch_authorization(
        session_id=session_id,
        process_id=process_id,
        contract=contract,
        profiles=profiles,
        calibration=calibration,
        role=role,
        command=command,
        cwd=cwd,
        environment=environment,
        stdio=stdio,
    )
    with _LAUNCH_GRANTS_LOCK:
        if len(_LAUNCH_GRANTS) >= MAX_LAUNCH_GRANTS:
            raise _contract_error("calibrated launch-grant registry is full")
        while True:
            token = secrets.token_urlsafe(32)
            if token not in _LAUNCH_GRANTS:
                break
        grant = CalibratedLaunchGrant(token)
        _LAUNCH_GRANTS[token] = _LaunchGrantRegistration(
            grant=grant,
            authorization=authorization,
        )
        return grant


def _verify_bound_launch(
    expected: _LaunchAuthorization,
    *,
    session_id: str,
    process_id: str,
    contract: DarwinIsolationContract,
    profiles: DarwinProfiles,
    calibration: Mapping[str, Any],
    role: str,
    command: Sequence[str],
    cwd: Path,
    environment: Mapping[str, str],
    stdio: OwnedChildStdio,
) -> None:
    if (
        _validated_session_id(session_id) != expected.session_id
        or _validated_process_id(process_id) != expected.process_id
    ):
        raise _contract_error("calibrated launch process identity differs from its grant")
    if contract != expected.input_contract:
        raise _contract_error("calibrated launch contract differs from its grant")
    if profiles != expected.profiles or role != expected.role:
        raise _contract_error("calibrated launch role or profiles differ from their grant")
    profile = profiles.app if role == "app" else profiles.browser
    if hashlib.sha256(profile.encode("utf-8")).hexdigest() != expected.profile_sha256:
        raise _contract_error("calibrated launch profile fingerprint differs")
    if (
        _launch_calibration_sha256(calibration, role=role, profile=profile)
        != expected.calibration_sha256
    ):
        raise _contract_error("calibrated launch report differs from its grant")
    if not isinstance(command, (tuple, list)) or tuple(command) != expected.command:
        raise _contract_error("calibrated launch command differs from its grant")
    cwd_input = Path(cwd).expanduser().absolute()
    cwd_authenticated = _safe_existing_directory(cwd_input, label="bound launch cwd")
    cwd_stat = cwd_authenticated.stat(follow_symlinks=False)
    cwd_identity = (
        cwd_stat.st_dev,
        cwd_stat.st_ino,
        cwd_stat.st_uid,
        stat.S_IMODE(cwd_stat.st_mode),
    )
    if cwd_input != expected.cwd or cwd_identity != expected.cwd_identity:
        raise _contract_error("calibrated launch cwd identity differs from its grant")
    if (
        not isinstance(environment, Mapping)
        or tuple(sorted(environment.items())) != expected.input_environment
    ):
        raise _contract_error("calibrated launch environment differs from its grant")
    runtime_environment = tuple(
        sorted(
            _runtime_child_environment(
                environment,
                process_token=expected.process_token,
            ).items()
        )
    )
    if runtime_environment != expected.environment:
        raise _contract_error("calibrated launch process-family environment differs")
    if _owned_stdio_identity(
        stdio,
        expected_role=role,
        allowed_root=(
            expected.contract.app_writable_root
            if role == "app"
            else expected.contract.browser_writable_root
        ),
    ) != expected.stdio_identity:
        raise _contract_error("calibrated launch stdio identity differs from its grant")
    if (
        _launch_contract_identity(expected.contract, role=expected.role)
        != expected.contract_identity
    ):
        raise _contract_error("calibrated launch filesystem identities changed")
    if _launch_identity_sha256(
        session_id=expected.session_id,
        process_id=expected.process_id,
        process_token=expected.process_token,
        role=expected.role,
        contract_identity=expected.contract_identity,
        command=expected.command,
        cwd=expected.cwd,
        cwd_identity=expected.cwd_identity,
        input_environment=expected.input_environment,
        environment=expected.environment,
        stdio_identity=expected.stdio_identity,
    ) != expected.launch_identity_sha256:
        raise _contract_error("calibrated launch identity changed after authorization")


def spawn_calibrated_child(
    *,
    authorization: CalibratedLaunchGrant,
    session_id: str,
    process_id: str,
    contract: DarwinIsolationContract,
    profiles: DarwinProfiles,
    calibration: Mapping[str, Any],
    role: str,
    command: Sequence[str],
    cwd: Path,
    environment: Mapping[str, str],
    stdio: OwnedChildStdio,
) -> subprocess.Popen[Any]:
    """Consume one grant and spawn only the byte-for-byte bound launch.

    Browser grants can name only the immutable mirrored worker.  Its normal
    calibrated Chromium descendants are observed by the operational PGID/token
    closure below; hostile arbitrary descendant tracing is outside this trusted
    capture-stack contract and Seatbelt supplies the resource boundary.
    """

    if not isinstance(authorization, CalibratedLaunchGrant):
        raise _contract_error("calibrated launch authorization is invalid")
    with _LAUNCH_GRANTS_LOCK:
        registered = _LAUNCH_GRANTS.get(authorization._token)
        if registered is None or registered.grant is not authorization:
            registered = None
        else:
            _LAUNCH_GRANTS.pop(authorization._token, None)
    if registered is None:
        raise _contract_error("calibrated launch authorization is unknown or already used")
    expected = registered.authorization
    _verify_bound_launch(
        expected,
        session_id=session_id,
        process_id=process_id,
        contract=contract,
        profiles=profiles,
        calibration=calibration,
        role=role,
        command=command,
        cwd=cwd,
        environment=environment,
        stdio=stdio,
    )
    family = _reserve_process_family(
        _ProcessFamilyIdentity(
            session_id=expected.session_id,
            process_id=expected.process_id,
            process_token=expected.process_token,
            role=expected.role,
            launch_identity_sha256=expected.launch_identity_sha256,
            owner_uid=os.getuid(),
        )
    )
    try:
        process = subprocess.Popen(
            list(expected.command),
            **child_popen_kwargs(
                cwd=expected.cwd,
                environment=dict(expected.environment),
                stdio=stdio,
            ),
        )
    except BaseException:
        _release_reserved_process_family(family)
        raise
    try:
        _attach_process_family(family, process)
    except BaseException:
        retention_error: BaseException | None = None
        try:
            _retain_unregistered_process_family(family, process)
        except BaseException as exc:
            retention_error = exc
        try:
            _cleanup_unregistered_process(process, family)
        except BaseException:
            raise
        _release_process_family(family)
        if retention_error is not None:
            raise retention_error
        raise
    return process


def _scheme_literal(value: Path | str) -> str:
    text = str(value)
    if "\x00" in text:
        raise _contract_error("Seatbelt literal contains NUL")
    return json.dumps(text, ensure_ascii=False)


def _playwright_chromium_identity() -> tuple[Path, str]:
    """Return the installed Playwright Chromium path and authenticated bytes."""

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise DependencyUnavailable("Playwright is unavailable") from exc
    try:
        with sync_playwright() as playwright:
            executable = Path(playwright.chromium.executable_path).resolve()
    except Exception as exc:  # noqa: BLE001 - dependency boundary is fail-closed.
        raise DependencyUnavailable("Playwright Chromium identity is unavailable") from exc
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise DependencyUnavailable("Playwright Chromium executable is unavailable")
    descriptor = os.open(executable, _SAFE_READ_FLAGS)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise DependencyUnavailable("Playwright Chromium executable is not regular")
        digest, _size = _hash_fd(descriptor)
        if not _same_stat_identity(opened, os.fstat(descriptor)):
            raise DependencyUnavailable("Playwright Chromium changed during identity check")
    finally:
        os.close(descriptor)
    return executable, digest


def _browser_bundle_root(executable: Path) -> Path:
    for candidate in (executable, *executable.parents):
        if candidate.name.endswith(".app") and candidate.is_dir():
            return candidate.resolve()
    raise DependencyUnavailable("Playwright Chromium app bundle is unavailable")


def _playwright_browser_cache_root(executable: Path) -> Path:
    for candidate in executable.parents:
        if candidate.name == "ms-playwright" and candidate.is_dir():
            return candidate.resolve()
    raise DependencyUnavailable("Playwright Chromium cache root is unavailable")


def _playwright_driver_executables(runtime_roots: Sequence[Path]) -> tuple[Path, ...]:
    candidates: set[Path] = set()
    patterns = (
        "lib/python*/site-packages/playwright/driver/node",
        "lib/python*/site-packages/playwright/driver/node.exe",
    )
    for root in runtime_roots:
        if not root.is_dir():
            continue
        for pattern in patterns:
            for candidate in root.glob(pattern):
                resolved = candidate.resolve()
                if resolved.is_file() and os.access(resolved, os.X_OK):
                    candidates.add(resolved)
    if not candidates:
        raise DependencyUnavailable("Playwright Node driver executable is unavailable")
    return tuple(sorted(candidates, key=str))


def _browser_bundle_executable_files(bundle_root: Path) -> tuple[Path, ...]:
    candidates: set[Path] = set()
    for candidate in bundle_root.rglob("*"):
        try:
            observed = candidate.stat(follow_symlinks=False)
        except OSError:
            continue
        if (
            stat.S_ISREG(observed.st_mode)
            and observed.st_nlink == 1
            and stat.S_IMODE(observed.st_mode) & 0o111
        ):
            candidates.add(candidate.resolve())
    if not candidates:
        raise DependencyUnavailable("Playwright Chromium bundle executables are unavailable")
    return tuple(sorted(candidates, key=str))


def _require_private_directory(path: Path, *, label: str, writable: bool) -> Path:
    resolved = _safe_existing_directory(path, label=label)
    observed = resolved.stat(follow_symlinks=False)
    if observed.st_uid != os.getuid():
        raise _contract_error(f"{label} is not coordinator-owned")
    mode = stat.S_IMODE(observed.st_mode)
    if writable:
        if mode != 0o700:
            raise _contract_error(f"{label} must be exact mode 0700")
    elif mode & 0o222:
        raise _contract_error(f"{label} must be read-only")
    return resolved


def _validate_runtime_root(
    path: Path,
    *,
    label: str,
    workspace: Path,
    common_run: Path,
) -> Path:
    resolved = _safe_existing_directory(path, label=label)
    forbidden = {Path("/").resolve(), Path.home().resolve(), workspace, common_run}
    if (
        resolved in forbidden
        or workspace.is_relative_to(resolved)
        or common_run.is_relative_to(resolved)
        or resolved.is_relative_to(common_run)
    ):
        raise _contract_error(f"{label} is an over-broad runtime root")
    if resolved.is_relative_to(workspace):
        relative = resolved.relative_to(workspace)
        if not relative.parts or relative.parts[0] != ".venv":
            raise _contract_error(f"{label} exposes non-venv workspace data")
    return resolved


def _validated_contract(contract: DarwinIsolationContract) -> DarwinIsolationContract:
    if not isinstance(contract, DarwinIsolationContract):
        raise _contract_error("Darwin isolation contract has the wrong type")
    directories = {
        "workspace": contract.workspace_root,
        "source": contract.source_root,
        "app writable": contract.app_writable_root,
        "browser writable": contract.browser_writable_root,
        "final evidence": contract.final_evidence_root,
    }
    normalized: dict[str, Path] = {}
    for label, value in directories.items():
        normalized[label] = _safe_existing_directory(Path(value), label=label)
    if len(set(normalized.values())) != len(normalized):
        raise _contract_error("Darwin isolation roots are not distinct")
    common_run = Path(
        os.path.commonpath(
            [
                str(normalized["source"]),
                str(normalized["app writable"]),
                str(normalized["browser writable"]),
                str(normalized["final evidence"]),
            ]
        )
    ).resolve()
    _require_private_directory(common_run, label="owned run root", writable=True)
    _require_private_directory(
        normalized["source"], label="source mirror root", writable=False
    )
    for label in ("app writable", "browser writable", "final evidence"):
        _require_private_directory(normalized[label], label=label, writable=True)
    role_roots = (
        normalized["source"],
        normalized["app writable"],
        normalized["browser writable"],
        normalized["final evidence"],
    )
    for index, left in enumerate(role_roots):
        if not left.is_relative_to(common_run) or left == common_run:
            raise _contract_error("Darwin role root escaped its owned run root")
        for right in role_roots[index + 1 :]:
            if left.is_relative_to(right) or right.is_relative_to(left):
                raise _contract_error("Darwin role roots overlap")
    workspace = normalized["workspace"]
    if workspace.is_relative_to(common_run) or common_run.is_relative_to(workspace):
        raise _contract_error("owned run root overlaps the original workspace")
    for label, executable in (
        ("Python executable", contract.python_executable),
        ("browser executable", contract.browser_executable),
    ):
        path = Path(executable).expanduser().absolute().resolve()
        if not path.is_file() or not os.access(path, os.X_OK):
            raise DependencyUnavailable(f"{label} is unavailable")
    for label, port in (("app", contract.app_port), ("denied", contract.denied_port)):
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise _contract_error(f"{label} port is invalid")
    if contract.app_port == contract.denied_port:
        raise _contract_error("Darwin isolation ports must be distinct")
    production = Path(contract.production_probe_path).resolve()
    if not production.is_file() or not production.is_relative_to(workspace):
        raise _contract_error("production probe is not a workspace file")
    production_stat = production.stat(follow_symlinks=False)
    if (
        not stat.S_ISREG(production_stat.st_mode)
        or production_stat.st_nlink != 1
        or production_stat.st_uid != os.getuid()
    ):
        raise _contract_error("production probe must be an owned one-link regular file")
    python_input = Path(contract.python_executable).expanduser().absolute()
    python_target = python_input.resolve()
    expected_python_input = Path(sys.executable).expanduser().absolute()
    if not os.path.samefile(python_input, expected_python_input):
        raise DependencyUnavailable(
            "Python executable is not the coordinator's authenticated runtime"
        )
    trusted_python_runtime_roots = {
        Path(sys.prefix).resolve(),
        Path(sys.base_prefix).resolve(),
        python_target.parent.parent.resolve(),
    }
    supplied_python_runtime_roots = tuple(
        Path(path).expanduser().absolute().resolve()
        for path in contract.python_runtime_roots
    )
    if any(
        root not in trusted_python_runtime_roots
        for root in supplied_python_runtime_roots
    ):
        raise _contract_error("Python runtime root is not coordinator-authenticated")
    raw_python_runtime_roots = tuple(
        dict.fromkeys(
            [
                *supplied_python_runtime_roots,
                *sorted(trusted_python_runtime_roots, key=str),
            ]
        )
    )
    python_runtime_roots = tuple(
        _validate_runtime_root(
            root,
            label="Python runtime root",
            workspace=workspace,
            common_run=common_run,
        )
        for root in raw_python_runtime_roots
    )
    expected_browser, _browser_sha256 = _playwright_chromium_identity()
    supplied_browser = Path(contract.browser_executable).resolve()
    if supplied_browser != expected_browser or not os.path.samefile(
        supplied_browser, expected_browser
    ):
        raise DependencyUnavailable(
            "browser executable is not Playwright's authenticated Chromium"
        )
    browser_bundle = _browser_bundle_root(supplied_browser)
    browser_cache = _playwright_browser_cache_root(supplied_browser)
    trusted_browser_runtime_roots = {browser_bundle, browser_cache}
    supplied_browser_runtime_roots = tuple(
        Path(path).expanduser().absolute().resolve()
        for path in contract.browser_runtime_roots
    )
    if any(
        root not in trusted_browser_runtime_roots
        for root in supplied_browser_runtime_roots
    ):
        raise _contract_error("browser runtime root is not Playwright-authenticated")
    # The browser needs only its exact signed-layout bundle at runtime; the
    # broader version cache is accepted as input identity but never granted.
    browser_runtime_roots = (
        _validate_runtime_root(
            browser_bundle,
            label="browser runtime root",
            workspace=workspace,
            common_run=common_run,
        ),
    )
    _playwright_driver_executables(python_runtime_roots)
    return DarwinIsolationContract(
        workspace_root=workspace,
        source_root=normalized["source"],
        app_writable_root=normalized["app writable"],
        browser_writable_root=normalized["browser writable"],
        final_evidence_root=normalized["final evidence"],
        # Preserve a venv launcher spelling so Python discovers pyvenv.cfg;
        # separately allow its authenticated target/runtime in the profile.
        python_executable=python_input,
        python_runtime_roots=python_runtime_roots,
        browser_executable=supplied_browser,
        browser_runtime_roots=browser_runtime_roots,
        production_probe_path=production,
        app_port=contract.app_port,
        denied_port=contract.denied_port,
    )


def _allow_read_rules(paths: Sequence[Path]) -> list[str]:
    rules: list[str] = []
    for path in dict.fromkeys(Path(item).resolve() for item in paths):
        operator = "subpath" if path.is_dir() and path != Path("/") else "literal"
        rules.append(f"(allow file-read* ({operator} {_scheme_literal(path)}))")
    return rules


def _path_filter(path: Path) -> str:
    resolved = Path(path).resolve()
    operator = (
        "subpath" if resolved.is_dir() and resolved != Path("/") else "literal"
    )
    return f"({operator} {_scheme_literal(resolved)})"


def _deny_global_read_except(
    paths: Sequence[Path],
) -> str:
    filters = list(dict.fromkeys(_path_filter(Path(path)) for path in paths))
    if not filters:
        raise _contract_error("global read allowlist is empty")
    allowed = filters[0] if len(filters) == 1 else "(require-any " + " ".join(filters) + ")"
    return f"(deny file-read-data (require-not {allowed}))"


def _deny_read_except(root: Path, exceptions: Sequence[Path]) -> str:
    filters = [f"(subpath {_scheme_literal(Path(path).resolve())})" for path in exceptions]
    if not filters:
        return f"(deny file-read-data (subpath {_scheme_literal(root)}))"
    allowed = filters[0] if len(filters) == 1 else "(require-any " + " ".join(filters) + ")"
    return (
        "(deny file-read-data (require-all "
        f"(subpath {_scheme_literal(root)}) (require-not {allowed})))"
    )


def _common_run_root(contract: DarwinIsolationContract) -> Path:
    return Path(
        os.path.commonpath(
            [
                str(contract.source_root),
                str(contract.app_writable_root),
                str(contract.browser_writable_root),
                str(contract.final_evidence_root),
            ]
        )
    ).resolve()


def build_darwin_profiles(contract: DarwinIsolationContract) -> DarwinProfiles:
    """Build distinct least-privilege Seatbelt profiles from escaped literals."""

    value = _validated_contract(contract)
    common_run = _common_run_root(value)
    app_read_roots = (
        value.source_root,
        value.app_writable_root,
        value.python_executable,
        value.python_executable.resolve(),
        *value.python_runtime_roots,
        *_SYSTEM_READ_ROOTS,
        *_SYSTEM_READ_FILES,
    )
    app_rules = [
        "(version 1)",
        "(allow default)",
        "(deny process-fork)",
        "(deny process-exec)",
        f"(allow process-exec (literal {_scheme_literal(value.python_executable)}))",
        f"(allow process-exec (literal {_scheme_literal(value.python_executable.resolve())}))",
        "(deny network-outbound)",
        "(deny network-bind)",
        "(deny network-inbound)",
        "(deny file-write*)",
        _deny_global_read_except(app_read_roots),
        _deny_read_except(value.workspace_root, app_read_roots),
        _deny_read_except(common_run, app_read_roots),
        f"(allow file-read* (subpath {_scheme_literal(value.source_root)}))",
        f"(allow file-read* (subpath {_scheme_literal(value.app_writable_root)}))",
        f"(allow file-write* (subpath {_scheme_literal(value.app_writable_root)}))",
        '(allow file-write-data (literal "/dev/null"))',
        f'(allow network-bind (local tcp "localhost:{value.app_port}"))',
        f'(allow network-inbound (local tcp "localhost:{value.app_port}"))',
    ]
    app_rules.extend(
        _allow_read_rules(
            (
                value.python_executable,
                *value.python_runtime_roots,
            )
        )
    )
    browser_read_roots = (
        value.source_root,
        value.browser_writable_root,
        value.python_executable,
        value.python_executable.resolve(),
        *value.python_runtime_roots,
        value.browser_executable,
        _browser_bundle_root(value.browser_executable),
        *value.browser_runtime_roots,
        *_SYSTEM_READ_ROOTS,
        *_SYSTEM_READ_FILES,
    )
    browser_exec_roots = (
        value.python_executable,
        value.python_executable.resolve(),
        value.browser_executable,
        _browser_bundle_root(value.browser_executable),
        *_playwright_driver_executables(value.python_runtime_roots),
    )
    browser_rules = [
        "(version 1)",
        "(allow default)",
        "(deny process-exec)",
        *(
            f"(allow process-exec {_path_filter(path)})"
            for path in dict.fromkeys(browser_exec_roots)
        ),
        "(deny network-outbound)",
        # Chromium requires a local Unix ProcessSingleton socket.  Deny the
        # operations broadly, then restore only local Unix coordination; TCP
        # and UDP listeners remain denied.
        "(deny network-bind)",
        "(deny network-inbound)",
        "(allow network-bind (local unix))",
        "(allow network-inbound (local unix))",
        "(deny file-write*)",
        _deny_global_read_except(browser_read_roots),
        _deny_read_except(value.workspace_root, browser_read_roots),
        _deny_read_except(common_run, browser_read_roots),
        f"(deny file-read-data (subpath {_scheme_literal(value.app_writable_root)}))",
        f"(deny file-read-data (subpath {_scheme_literal(value.final_evidence_root)}))",
        f"(allow file-read* (subpath {_scheme_literal(value.source_root)}))",
        f"(allow file-read* (subpath {_scheme_literal(value.browser_writable_root)}))",
        f"(allow file-write* (subpath {_scheme_literal(value.browser_writable_root)}))",
        '(allow file-write-data (literal "/dev/null"))',
        f'(allow network-outbound (remote tcp "localhost:{value.app_port}"))',
    ]
    browser_rules.extend(
        _allow_read_rules(
            (
                value.python_executable,
                *value.python_runtime_roots,
                value.browser_executable,
                *value.browser_runtime_roots,
            )
        )
    )
    return DarwinProfiles(
        app="\n".join(app_rules) + "\n",
        browser="\n".join(browser_rules) + "\n",
    )


def build_app_sandbox_profile(contract: DarwinIsolationContract) -> str:
    """Return the app profile after the full isolation contract is validated."""

    value = _validated_contract(contract)
    return build_darwin_profiles(value).app


def build_browser_sandbox_profile(contract: DarwinIsolationContract) -> str:
    """Return the browser profile after the full isolation contract is validated."""

    value = _validated_contract(contract)
    return build_darwin_profiles(value).browser


_APP_CALIBRATION_SCRIPT = r'''
import _socket
import builtins
import errno
import json
import os
import socket
import sqlite3
import subprocess
import sys

source_path, production_path, sqlite_path, symlink_path, outside_path = sys.argv[1:6]
app_port, other_bind_port, denied_port, inherited_fd = map(int, sys.argv[6:])
allowed = {}
denied = {}
details = {}

def expect_eperm(name, action):
    try:
        action()
    except OSError as exc:
        details[name] = {"errno": getattr(exc, "errno", None)}
        denied[name] = getattr(exc, "errno", None) in (errno.EPERM, errno.EACCES)
    except Exception as exc:
        details[name] = {"type": type(exc).__name__}
        denied[name] = False
    else:
        denied[name] = False

with open(source_path, "rb") as handle:
    allowed["sourceRead"] = bool(handle.read(1))

for key, root_name in (
    ("fixtureWrite", "fixture"),
    ("streamlitWrite", "streamlit"),
    ("temporaryWrite", "tmp"),
):
    root = os.path.join(os.environ["HOME"], "..", root_name)
    root = os.path.abspath(root)
    os.makedirs(root, mode=0o700, exist_ok=True)
    path = os.path.join(root, "probe.txt")
    with open(path, "wb") as handle:
        handle.write(b"owned")
    allowed[key] = os.path.getsize(path) == 5

listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listener.bind(("127.0.0.1", app_port))
listener.listen(2)
listener.settimeout(10.0)
allowed["assignedBind"] = True
print(json.dumps({"ready": True}), flush=True)
connection, _address = listener.accept()
with connection:
    accepted = connection.recv(4096)
allowed["assignedAccept"] = bool(accepted)

captured_open = builtins.open
captured_sqlite = sqlite3.connect
expect_eperm("productionPathRead", lambda: open(production_path, "rb").read(1))
expect_eperm("symlinkTraversalRead", lambda: open(symlink_path, "rb").read(1))

production_fd_bytes = 0
try:
    payload = os.read(inherited_fd, 4096)
except OSError as exc:
    details["productionFdRead"] = {"errno": getattr(exc, "errno", None)}
    denied["productionFdRead"] = getattr(exc, "errno", None) in (errno.EPERM, errno.EACCES, errno.EBADF)
else:
    production_fd_bytes = len(payload)
    denied["productionFdRead"] = False

expect_eperm("sourceWrite", lambda: open(source_path, "ab").write(b"x"))
expect_eperm("writeOutsideRoots", lambda: open(outside_path, "ab").write(b"x"))
expect_eperm("rawFileRead", lambda: os.close(os.open(production_path, os.O_RDONLY)))
expect_eperm("closureFileRead", lambda: captured_open(production_path, "rb").read(1))

def sqlite_read():
    connection = captured_sqlite("file:" + sqlite_path + "?mode=ro", uri=True)
    try:
        connection.execute("select value from probe").fetchone()
    finally:
        connection.close()
try:
    sqlite_read()
except sqlite3.OperationalError as exc:
    message = str(exc).casefold()
    details["closureSqliteRead"] = {
        "type": "OperationalError",
        "policyDenied": "unable to open database" in message or "not authorized" in message,
    }
    denied["closureSqliteRead"] = details["closureSqliteRead"]["policyDenied"]
except OSError as exc:
    details["closureSqliteRead"] = {"errno": getattr(exc, "errno", None)}
    denied["closureSqliteRead"] = getattr(exc, "errno", None) in (errno.EPERM, errno.EACCES)
except Exception as exc:
    details["closureSqliteRead"] = {"type": type(exc).__name__}
    denied["closureSqliteRead"] = False
else:
    denied["closureSqliteRead"] = False

def attempt_fork():
    pid = os.fork()
    if pid == 0:
        os._exit(0)
    os.waitpid(pid, 0)
expect_eperm("fork", attempt_fork)

def attempt_exec():
    pid = os.posix_spawn("/usr/bin/true", ["/usr/bin/true"], os.environ)
    os.waitpid(pid, 0)
expect_eperm("exec", attempt_exec)

def connect(target):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(1.0)
    try:
        client.connect(target)
        client.sendall(b"UNEXPECTED")
    finally:
        client.close()

expect_eperm("assignedOutbound", lambda: connect(("127.0.0.1", app_port)))

def other_bind():
    candidate = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        candidate.bind(("127.0.0.1", other_bind_port))
    finally:
        candidate.close()
expect_eperm("otherBind", other_bind)
expect_eperm("otherLoopbackOutbound", lambda: connect(("127.0.0.1", denied_port)))
expect_eperm("externalOutbound", lambda: connect(("203.0.113.1", 9)))

def raw_connect():
    client = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    client.settimeout(1.0)
    try:
        client.connect(("127.0.0.1", denied_port))
        client.sendall(b"UNEXPECTED-RAW")
    finally:
        client.close()
expect_eperm("rawSocketOutbound", raw_connect)

def mro_connect():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(1.0)
    try:
        socket.socket.__mro__[1].connect(client, ("127.0.0.1", denied_port))
        client.sendall(b"UNEXPECTED-MRO")
    finally:
        client.close()
expect_eperm("socketMroOutbound", mro_connect)
listener.close()
print(json.dumps({
    "allowed": allowed,
    "denied": denied,
    "details": details,
    "acceptedBytes": len(accepted),
    "productionFdBytes": production_fd_bytes,
}, sort_keys=True), flush=True)
'''


_BROWSER_CALIBRATION_SCRIPT = r'''
import _socket
import errno
import json
import os
import socket
import stat
import sys
import time
from playwright.sync_api import sync_playwright

source_path, production_path, app_fixture_path, final_path, browser_executable, handshake_token, symlink_path, outside_path = sys.argv[1:9]
app_port, denied_port, other_bind_port = map(int, sys.argv[9:])
allowed = {}
denied = {}
details = {}

def expect_eperm(name, action):
    try:
        action()
    except OSError as exc:
        details[name] = {"errno": getattr(exc, "errno", None)}
        denied[name] = getattr(exc, "errno", None) in (errno.EPERM, errno.EACCES)
    except Exception as exc:
        details[name] = {"type": type(exc).__name__}
        denied[name] = False
    else:
        denied[name] = False

with open(source_path, "rb") as handle:
    allowed["sourceRead"] = bool(handle.read(1))

browser_root = os.path.abspath(os.path.join(os.environ["HOME"], ".."))
chromium_temp = os.path.realpath(os.environ["MAC_CHROMIUM_TMPDIR"])
singleton_prefix = "com.google.chrome.for.testing."

def singleton_names():
    return sorted(
        name for name in os.listdir(chromium_temp)
        if name.startswith(singleton_prefix)
    )

for key, root_name in (
    ("captureWrite", "capture"),
    ("cacheWrite", "cache"),
    ("temporaryWrite", "tmp"),
):
    root = os.path.join(browser_root, root_name)
    os.makedirs(root, mode=0o700, exist_ok=True)
    path = os.path.join(root, "probe.txt")
    with open(path, "wb") as handle:
        handle.write(b"owned")
    allowed[key] = os.path.getsize(path) == 5

browser = None
try:
    with sync_playwright() as playwright:
        identity_matches = os.path.realpath(playwright.chromium.executable_path) == os.path.realpath(browser_executable)
        browser = playwright.chromium.launch(
            executable_path=browser_executable,
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
        connected_at_launch = bool(browser.is_connected())
        allowed["chromiumLaunch"] = connected_at_launch
        live_singletons = singleton_names()
        singleton_paths = [os.path.join(chromium_temp, name) for name in live_singletons]
        socket_exact = False
        cookie_exact = False
        if len(singleton_paths) == 1:
            socket_path = os.path.join(singleton_paths[0], "SingletonSocket")
            cookie_path = os.path.join(singleton_paths[0], "SingletonCookie")
            try:
                socket_exact = stat.S_ISSOCK(os.lstat(socket_path).st_mode)
                cookie_target = os.readlink(cookie_path)
                cookie_exact = bool(
                    stat.S_ISLNK(os.lstat(cookie_path).st_mode)
                    and cookie_target.isdigit()
                    and "/" not in cookie_target
                    and cookie_target not in (".", "..")
                )
            except OSError:
                pass
        owned_singleton = bool(
            len(singleton_paths) == 1
            and os.path.isdir(singleton_paths[0])
            and os.path.commonpath((chromium_temp, os.path.realpath(singleton_paths[0])))
                == chromium_temp
            and socket_exact
            and cookie_exact
        )
        allowed["chromiumSingletonOwned"] = owned_singleton
        details["chromium"] = {
            "connectedAtLaunch": connected_at_launch,
            "playwrightIdentityMatches": identity_matches,
            "singletonCountAtLaunch": len(live_singletons),
            "singletonOwned": owned_singleton,
        }
        page = browser.new_page()
        response = page.goto(
            "http://127.0.0.1:%d/ux1b-calibration" % app_port,
            wait_until="domcontentloaded",
            timeout=10000,
        )
        marker = page.locator("#ux1b-calibration")
        dom_handshake = bool(
            response is not None
            and response.ok
            and marker.get_attribute("data-token") == handshake_token
            and marker.text_content() == "UX1B-DOM-READY"
        )
        allowed["chromiumDomHandshake"] = dom_handshake
        allowed["assignedConnect"] = dom_handshake
        browser.close()
        browser = None
        cleanup_deadline = time.monotonic() + 2.0
        while singleton_names() and time.monotonic() < cleanup_deadline:
            time.sleep(0.02)
        allowed["chromiumSingletonCleanup"] = not singleton_names()
except Exception as exc:
    details["chromium"] = {"type": type(exc).__name__}
    allowed.setdefault("chromiumLaunch", False)
    allowed.setdefault("chromiumDomHandshake", False)
    allowed.setdefault("assignedConnect", False)
    allowed.setdefault("chromiumSingletonOwned", False)
    allowed.setdefault("chromiumSingletonCleanup", False)
finally:
    if browser is not None:
        try:
            browser.close()
        except Exception:
            pass

def connect(target, payload):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(2.0)
    try:
        client.connect(target)
        client.sendall(payload)
    finally:
        client.close()

expect_eperm("productionPathRead", lambda: open(production_path, "rb").read(1))
expect_eperm("symlinkTraversalRead", lambda: open(symlink_path, "rb").read(1))
expect_eperm("appFixtureRead", lambda: open(app_fixture_path, "rb").read(1))
expect_eperm("finalEvidenceRead", lambda: open(final_path, "rb").read(1))
expect_eperm("appFixtureWrite", lambda: open(app_fixture_path, "ab").write(b"x"))
expect_eperm("finalEvidenceWrite", lambda: open(final_path, "ab").write(b"x"))
expect_eperm("sourceWrite", lambda: open(source_path, "ab").write(b"x"))
expect_eperm("writeOutsideRoots", lambda: open(outside_path, "ab").write(b"x"))

def attempt_exec():
    pid = os.posix_spawn("/usr/bin/true", ["/usr/bin/true"], os.environ)
    os.waitpid(pid, 0)
expect_eperm("exec", attempt_exec)

def other_bind():
    candidate = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        candidate.bind(("127.0.0.1", other_bind_port))
    finally:
        candidate.close()
expect_eperm("otherBind", other_bind)
expect_eperm("otherLoopbackOutbound", lambda: connect(("127.0.0.1", denied_port), b"UNEXPECTED"))
expect_eperm("externalOutbound", lambda: connect(("203.0.113.1", 9), b"UNEXPECTED"))

def raw_connect():
    client = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    client.settimeout(1.0)
    try:
        client.connect(("127.0.0.1", denied_port))
        client.sendall(b"UNEXPECTED-RAW")
    finally:
        client.close()
expect_eperm("rawSocketOutbound", raw_connect)

def mro_connect():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(1.0)
    try:
        socket.socket.__mro__[1].connect(client, ("127.0.0.1", denied_port))
        client.sendall(b"UNEXPECTED-MRO")
    finally:
        client.close()
expect_eperm("socketMroOutbound", mro_connect)

print(json.dumps({"allowed": allowed, "denied": denied, "details": details}, sort_keys=True))
'''


class _ProbeListener:
    def __init__(self, port: int, *, response: bytes | None = None) -> None:
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind(("127.0.0.1", port))
        self._listener.listen(8)
        self._listener.settimeout(0.1)
        self._stop = threading.Event()
        self._response = response
        self._payloads: list[bytes] = []
        self._thread = threading.Thread(target=self._serve, daemon=True)
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
                connection.settimeout(0.5)
                try:
                    payload = connection.recv(4096)
                except OSError:
                    payload = b""
                self._payloads.append(payload)
                if self._response is not None:
                    with contextlib.suppress(OSError):
                        connection.sendall(self._response)

    @property
    def total_bytes(self) -> int:
        return sum(len(payload) for payload in self._payloads)

    def close(self) -> None:
        self._stop.set()
        with contextlib.suppress(OSError):
            self._listener.close()
        self._thread.join(timeout=2.0)


class _BoundedJsonLineReader:
    """Read newline-delimited child records without unbounded buffering."""

    def __init__(
        self,
        stream: Any,
        *,
        limit: int = MAX_CALIBRATION_RECORD_BYTES,
    ) -> None:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            raise _contract_error("calibration record limit is invalid")
        try:
            descriptor = int(stream.fileno())
        except (AttributeError, OSError, TypeError, ValueError) as exc:
            raise _contract_error("calibration output stream is invalid") from exc
        if descriptor < 0:
            raise _contract_error("calibration output descriptor is invalid")
        self._stream = stream
        self._descriptor = descriptor
        self._limit = limit
        self._buffer = bytearray()

    def read_object(self, *, timeout: float, label: str) -> dict[str, Any]:
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
            raise _contract_error(f"{label} timeout is invalid")
        deadline = time.monotonic() + float(timeout)
        while True:
            newline = self._buffer.find(b"\n")
            if newline >= 0:
                if newline > self._limit:
                    raise _contract_error(f"{label} exceeded its byte limit")
                raw = bytes(self._buffer[:newline])
                del self._buffer[: newline + 1]
                return _decode_calibration_record(raw, label=label)
            if len(self._buffer) > self._limit:
                raise _contract_error(f"{label} exceeded its byte limit")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _contract_error(f"{label} timed out")
            ready, _writable, _errors = select.select(
                [self._descriptor],
                [],
                [],
                remaining,
            )
            if not ready:
                raise _contract_error(f"{label} timed out")
            try:
                chunk = os.read(self._descriptor, 4096)
            except OSError as exc:
                raise _contract_error(f"{label} could not be read") from exc
            if not chunk:
                if not self._buffer:
                    raise _contract_error(f"{label} produced no output")
                raw = bytes(self._buffer)
                self._buffer.clear()
                return _decode_calibration_record(raw, label=label)
            self._buffer.extend(chunk)

    def finish_exact(self, *, timeout: float, label: str) -> None:
        """Require EOF after the expected records, rejecting any extra byte."""

        if self._buffer:
            raise _contract_error(f"{label} produced an extra record")
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
            raise _contract_error(f"{label} timeout is invalid")
        deadline = time.monotonic() + float(timeout)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _contract_error(f"{label} timed out before EOF")
            ready, _writable, _errors = select.select(
                [self._descriptor],
                [],
                [],
                remaining,
            )
            if not ready:
                raise _contract_error(f"{label} timed out before EOF")
            try:
                chunk = os.read(self._descriptor, 4096)
            except OSError as exc:
                raise _contract_error(f"{label} could not be read") from exc
            if not chunk:
                return
            raise _contract_error(f"{label} produced an extra record")


def _decode_calibration_record(raw: bytes, *, label: str) -> dict[str, Any]:
    if len(raw) > MAX_CALIBRATION_RECORD_BYTES:
        raise _contract_error(f"{label} exceeded its byte limit")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _contract_error(f"{label} output is malformed") from exc
    if not isinstance(value, dict):
        raise _contract_error(f"{label} output is not an object")
    return value


def _bounded_communicate(
    process: subprocess.Popen[bytes],
    *,
    timeout: float,
    stdout_limit: int = MAX_CALIBRATION_CAPTURE_BYTES,
    stderr_limit: int = MAX_CALIBRATION_CAPTURE_BYTES,
) -> tuple[bytes, bytes]:
    """Drain both child pipes concurrently while enforcing live byte limits."""

    if not isinstance(process, _POPEN_CLASS):
        raise _contract_error("bounded child handle has the wrong type")
    if process.stdout is None or process.stderr is None:
        raise _contract_error("bounded child pipes are missing")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise _contract_error("bounded child timeout is invalid")
    for value, label in ((stdout_limit, "stdout"), (stderr_limit, "stderr")):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise _contract_error(f"bounded child {label} limit is invalid")

    stdout_fd = int(process.stdout.fileno())
    stderr_fd = int(process.stderr.fileno())
    stdout_buffer = bytearray()
    stderr_buffer = bytearray()
    active: dict[int, tuple[str, bytearray, int]] = {
        stdout_fd: ("stdout", stdout_buffer, stdout_limit),
        stderr_fd: ("stderr", stderr_buffer, stderr_limit),
    }
    deadline = time.monotonic() + float(timeout)
    while active:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _contract_error("bounded child output timed out")
        try:
            ready, _writable, _errors = select.select(
                tuple(active),
                [],
                [],
                remaining,
            )
        except (OSError, ValueError) as exc:
            raise _contract_error("bounded child output polling failed") from exc
        if not ready:
            raise _contract_error("bounded child output timed out")
        for descriptor in ready:
            label, buffer, limit = active[descriptor]
            try:
                chunk = os.read(descriptor, min(65536, limit - len(buffer) + 1))
            except OSError as exc:
                raise _contract_error(f"bounded child {label} read failed") from exc
            if not chunk:
                del active[descriptor]
                continue
            buffer.extend(chunk)
            if len(buffer) > limit:
                raise _contract_error(f"bounded child {label} exceeded its byte limit")

    return bytes(stdout_buffer), bytes(stderr_buffer)


def _fresh_unbound_port(excluded: Sequence[int]) -> int:
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
            candidate.bind(("127.0.0.1", 0))
            port = int(candidate.getsockname()[1])
        if port not in excluded:
            return port


def _create_calibration_symlink(
    handle: OwnedRunRoot,
    *,
    name: str,
    target: Path,
) -> Path:
    if (
        not isinstance(name, str)
        or not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or "\x00" in name
    ):
        raise _contract_error("calibration symlink name is invalid")
    _validate_owned_root_handle(handle)
    os.symlink(str(Path(target).absolute()), name, dir_fd=handle.descriptor)
    observed = os.stat(name, dir_fd=handle.descriptor, follow_symlinks=False)
    if not stat.S_ISLNK(observed.st_mode) or observed.st_uid != handle.owner_uid:
        raise _contract_error("calibration symlink identity differs")
    return handle.path / name


@dataclass
class _EphemeralCalibrationProbe:
    path: Path
    leaf_name: str
    root_descriptor: int = field(repr=False)
    root_device: int
    root_inode: int
    device: int
    inode: int
    owner_uid: int
    expected_size: int
    expected_sha256: str
    _closed: bool = field(default=False, init=False, repr=False)

    def authenticate(self, *, expected_root: Path) -> None:
        if self._closed:
            raise _contract_error("calibration probe is already closed")
        opened_root = os.fstat(self.root_descriptor)
        named_root = Path(expected_root).stat(follow_symlinks=False)
        expected_identity = (self.root_device, self.root_inode)
        if (
            not stat.S_ISDIR(opened_root.st_mode)
            or not stat.S_ISDIR(named_root.st_mode)
            or (opened_root.st_dev, opened_root.st_ino) != expected_identity
            or (named_root.st_dev, named_root.st_ino) != expected_identity
            or opened_root.st_uid != self.owner_uid
            or named_root.st_uid != self.owner_uid
        ):
            raise _contract_error("calibration probe root identity changed")
        observed = os.stat(
            self.leaf_name,
            dir_fd=self.root_descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(observed.st_mode)
            or (observed.st_dev, observed.st_ino) != (self.device, self.inode)
            or observed.st_uid != self.owner_uid
            or observed.st_nlink != 1
            or stat.S_IMODE(observed.st_mode) != 0o600
        ):
            raise _contract_error("calibration probe identity changed")
        descriptor = os.open(
            self.leaf_name,
            _SAFE_READ_FLAGS,
            dir_fd=self.root_descriptor,
        )
        try:
            opened = os.fstat(descriptor)
            if not _same_stat_identity(observed, opened):
                raise _contract_error("calibration probe changed while opening")
            digest, size = _hash_fd(descriptor)
            final = os.fstat(descriptor)
            if (
                not _same_stat_identity(opened, final)
                or size != self.expected_size
                or digest != self.expected_sha256
            ):
                raise _contract_error("calibration probe bytes changed")
        finally:
            os.close(descriptor)

    def remove(self) -> None:
        if self._closed:
            return
        integrity_error: BaseException | None = None
        try:
            try:
                self.authenticate(expected_root=self.path.parent)
            except BaseException as exc:  # noqa: BLE001 - exact cleanup still proceeds.
                integrity_error = exc
            observed = os.stat(
                self.leaf_name,
                dir_fd=self.root_descriptor,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISREG(observed.st_mode)
                or (observed.st_dev, observed.st_ino) != (self.device, self.inode)
                or observed.st_uid != self.owner_uid
                or observed.st_nlink != 1
            ):
                raise _contract_error("calibration probe identity changed before cleanup")
            os.unlink(self.leaf_name, dir_fd=self.root_descriptor)
        finally:
            self._closed = True
            os.close(self.root_descriptor)
        if integrity_error is not None:
            raise integrity_error


@dataclass(frozen=True)
class _CalibrationFiles:
    source_probe: Path
    sqlite_probe: Path
    app_private: Path
    final_private: Path
    outside_private: Path
    ephemeral_probes: tuple[_EphemeralCalibrationProbe, ...] = field(repr=False)


def _create_ephemeral_calibration_probe(
    root: Path,
    *,
    label: str,
    payload: bytes,
) -> _EphemeralCalibrationProbe:
    root_path = _safe_existing_directory(root, label=f"{label} probe root")
    root_descriptor = os.open(root_path, _SAFE_DIRECTORY_FLAGS)
    descriptor = -1
    leaf_name: str | None = None
    try:
        root_observed = os.fstat(root_descriptor)
        for _attempt in range(128):
            candidate = f".ux1b-{label}-{secrets.token_hex(16)}.probe"
            try:
                descriptor = os.open(
                    candidate,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC,
                    0o600,
                    dir_fd=root_descriptor,
                )
            except FileExistsError:
                continue
            leaf_name = candidate
            break
        if descriptor < 0 or leaf_name is None:
            raise _contract_error("could not allocate an ephemeral calibration probe")
        view = memoryview(payload)
        while view:
            view = view[os.write(descriptor, view) :]
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o600)
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_uid != os.getuid()
            or observed.st_nlink != 1
            or stat.S_IMODE(observed.st_mode) != 0o600
        ):
            raise _contract_error("ephemeral calibration probe identity differs")
        os.close(descriptor)
        descriptor = -1
        return _EphemeralCalibrationProbe(
            path=root_path / leaf_name,
            leaf_name=leaf_name,
            root_descriptor=root_descriptor,
            root_device=root_observed.st_dev,
            root_inode=root_observed.st_ino,
            device=observed.st_dev,
            inode=observed.st_ino,
            owner_uid=observed.st_uid,
            expected_size=len(payload),
            expected_sha256=hashlib.sha256(payload).hexdigest(),
        )
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        if leaf_name is not None:
            with contextlib.suppress(OSError):
                os.unlink(leaf_name, dir_fd=root_descriptor)
        os.close(root_descriptor)
        raise


def _prepare_calibration_files(
    contract: DarwinIsolationContract,
    calibration_root: Path,
) -> _CalibrationFiles:
    source_probe = contract.source_root / "app.py"
    if not source_probe.is_file():
        candidates = sorted(contract.source_root.rglob("*.py"))
        if not candidates:
            raise _contract_error("source mirror has no Python calibration probe")
        source_probe = candidates[0]
    probes: list[_EphemeralCalibrationProbe] = []
    try:
        probes.append(
            _create_ephemeral_calibration_probe(
                contract.app_writable_root,
                label="app-private",
                payload=b"app-private-decoy\n",
            )
        )
        probes.append(
            _create_ephemeral_calibration_probe(
                contract.final_evidence_root,
                label="final-private",
                payload=b"final-private-decoy\n",
            )
        )
        probes.append(
            _create_ephemeral_calibration_probe(
                calibration_root,
                label="outside-private",
                payload=b"outside-private-decoy\n",
            )
        )
        sqlite_probe = _create_sqlite_probe(calibration_root)
        return _CalibrationFiles(
            source_probe=source_probe,
            sqlite_probe=sqlite_probe,
            app_private=probes[0].path,
            final_private=probes[1].path,
            outside_private=probes[2].path,
            ephemeral_probes=tuple(probes),
        )
    except BaseException:
        for probe in reversed(probes):
            with contextlib.suppress(Exception):
                probe.remove()
        raise


def _create_sqlite_probe(calibration_root: Path) -> Path:
    import sqlite3

    path = calibration_root / "sqlite-decoy.sqlite3"
    if path.exists() or path.is_symlink():
        raise _contract_error("calibration SQLite decoy already exists")
    connection = sqlite3.connect(path)
    try:
        connection.execute("create table if not exists probe(value text not null)")
        connection.execute("delete from probe")
        connection.execute("insert into probe(value) values ('production-private')")
        connection.commit()
    finally:
        connection.close()
    return path


def _calibration_environment(
    role: str,
    contract: DarwinIsolationContract,
    *,
    writable_root: Path | None = None,
) -> dict[str, str]:
    writable = writable_root or (
        contract.app_writable_root if role == "app" else contract.browser_writable_root
    )
    return build_child_environment(
        role=role,
        source_root=contract.source_root,
        writable_root=writable,
        inherited=os.environ,
        python_runtime_roots=contract.python_runtime_roots,
    )


def _register_owned_process_group(process: subprocess.Popen[Any]) -> None:
    """Register a calibration/test process for termination only.

    These legacy registrations can never mint a clean-exit attestation.  The
    production calibrated path uses the pre-spawn process-family registry.
    """

    if not isinstance(process, _POPEN_CLASS):
        raise _contract_error("owned process handle has the wrong type")
    pid = int(process.pid)
    if pid <= 1 or process.returncode is not None:
        raise _contract_error("owned process leader is unavailable")
    try:
        process_group = os.getpgid(pid)
    except ProcessLookupError as exc:
        raise _contract_error("owned process leader exited before registration") from exc
    if process_group != pid:
        raise _contract_error("child does not own its process group")
    with _TERMINATION_ONLY_PROCESS_GROUPS_LOCK:
        if (
            len(_TERMINATION_ONLY_PROCESS_GROUPS) >= MAX_PROCESS_FAMILIES
            and id(process) not in _TERMINATION_ONLY_PROCESS_GROUPS
        ):
            raise _contract_error("owned process-group registry is full")
        _TERMINATION_ONLY_PROCESS_GROUPS[id(process)] = (process, process_group)


def _forget_owned_process_group(process: subprocess.Popen[Any]) -> None:
    with _TERMINATION_ONLY_PROCESS_GROUPS_LOCK:
        registered = _TERMINATION_ONLY_PROCESS_GROUPS.get(id(process))
        if registered is not None and registered[0] is process:
            _TERMINATION_ONLY_PROCESS_GROUPS.pop(id(process), None)


def _reserve_process_family(
    identity: _ProcessFamilyIdentity,
) -> _ProcessFamilyRegistration:
    if not isinstance(identity, _ProcessFamilyIdentity):
        raise _contract_error("process-family identity has the wrong type")
    _validated_session_id(identity.session_id)
    _validated_process_id(identity.process_id)
    _validated_process_token(identity.process_token)
    if identity.role not in {"app", "browser"}:
        raise _contract_error("process-family role is invalid")
    if identity.owner_uid != os.getuid():
        raise _contract_error("process-family owner differs from the coordinator")
    if re.fullmatch(r"[0-9a-f]{64}", identity.launch_identity_sha256) is None:
        raise _contract_error("process-family launch identity is invalid")
    registration = _ProcessFamilyRegistration(identity=identity, state="reserved")
    with _PROCESS_FAMILIES_LOCK:
        if len(_PROCESS_FAMILIES_BY_TOKEN) >= MAX_PROCESS_FAMILIES:
            raise _contract_error("process-family registry is full")
        if identity.process_token in _PROCESS_FAMILIES_BY_TOKEN:
            raise _contract_error("process-family token is already registered")
        if any(
            row.identity.session_id == identity.session_id
            and row.identity.role == identity.role
            and row.identity.process_id == identity.process_id
            for row in _PROCESS_FAMILIES_BY_TOKEN.values()
        ):
            raise _contract_error("process-family identity is already registered")
        _PROCESS_FAMILIES_BY_TOKEN[identity.process_token] = registration
    return registration


def _release_reserved_process_family(
    registration: _ProcessFamilyRegistration,
) -> None:
    with _PROCESS_FAMILIES_LOCK:
        current = _PROCESS_FAMILIES_BY_TOKEN.get(
            registration.identity.process_token
        )
        if current is registration and registration.state == "reserved":
            _PROCESS_FAMILIES_BY_TOKEN.pop(
                registration.identity.process_token, None
            )


def _release_process_family(registration: _ProcessFamilyRegistration) -> None:
    with _PROCESS_FAMILIES_LOCK:
        current = _PROCESS_FAMILIES_BY_TOKEN.get(
            registration.identity.process_token
        )
        if current is registration:
            _PROCESS_FAMILIES_BY_TOKEN.pop(
                registration.identity.process_token, None
            )
        process = registration.process
        if process is not None:
            by_process = _PROCESS_FAMILIES_BY_PROCESS.get(id(process))
            if by_process is registration:
                _PROCESS_FAMILIES_BY_PROCESS.pop(id(process), None)
        registration.state = "released"


def _parse_process_table(
    raw: bytes, *, process_token: str
) -> _ProcessTableObservation:
    token = _validated_process_token(process_token)
    if not isinstance(raw, bytes) or len(raw) > MAX_PROCESS_TABLE_BYTES:
        raise _contract_error("process-table observation exceeded its byte limit")
    needle = f"{PROCESS_TOKEN_ENV_KEY}={token}".encode("ascii")
    rows: list[_ProcessObservationRow] = []
    seen_pids: set[int] = set()
    for raw_line in raw.splitlines():
        if not raw_line.strip():
            continue
        fields = raw_line.split(None, 5)
        if len(fields) != 6:
            raise _contract_error("process-table observation output is malformed")
        try:
            pid_text, uid_text, pgid_text, state_text, xstat_text = (
                value.decode("ascii", errors="strict") for value in fields[:5]
            )
        except UnicodeDecodeError as exc:
            raise _contract_error(
                "process-table observation output is malformed"
            ) from exc
        if (
            not pid_text.isdecimal()
            or not uid_text.isdecimal()
            or not pgid_text.isdecimal()
            or _PROCESS_STATE_PATTERN.fullmatch(state_text) is None
            or _HEX_WAIT_STATUS_PATTERN.fullmatch(xstat_text) is None
        ):
            raise _contract_error("process-table observation output is malformed")
        pid = int(pid_text, 10)
        uid = int(uid_text, 10)
        process_group = int(pgid_text, 10)
        wait_status = int(xstat_text, 16)
        if (
            not 0 < pid <= 2**31 - 1
            or not 0 <= uid <= 2**32 - 1
            or not 0 <= process_group <= 2**31 - 1
            or pid in seen_pids
        ):
            raise _contract_error("process-table observation output is malformed")
        seen_pids.add(pid)
        padded_command = b" " + fields[5] + b" "
        rows.append(
            _ProcessObservationRow(
                pid=pid,
                uid=uid,
                process_group=process_group,
                state=state_text,
                wait_status=wait_status,
                has_family_token=b" " + needle + b" " in padded_command,
            )
        )
    return _ProcessTableObservation(rows=tuple(sorted(rows, key=lambda row: row.pid)))


def _bounded_process_table_observation(
    process_token: str,
) -> _ProcessTableObservation:
    """Take one bounded Darwin process/environment snapshot."""

    token = _validated_process_token(process_token)
    if sys.platform != "darwin":
        raise DependencyUnavailable("process-family observation requires Darwin")
    ps = Path("/bin/ps")
    if not ps.is_file():
        raise DependencyUnavailable("process-family observation requires /bin/ps")
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            (
                str(ps),
                "eww",
                "-axo",
                "pid=,uid=,pgid=,stat=,xstat=,command=",
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                "LANG": "C",
                "LC_ALL": "C",
            },
            close_fds=True,
            pass_fds=(),
            start_new_session=True,
        )
        stdout, _stderr = _bounded_communicate(
            process,
            timeout=2.0,
            stdout_limit=MAX_PROCESS_TABLE_BYTES,
            stderr_limit=MAX_PROCESS_TABLE_ERROR_BYTES,
        )
        if process.wait(timeout=0.5) != 0:
            raise _contract_error("process-table observation failed")
        return _parse_process_table(stdout, process_token=token)
    except IsolationContractError:
        raise
    except (OSError, subprocess.SubprocessError) as exc:
        raise _contract_error("process-table observation failed") from exc
    finally:
        if process is not None:
            if process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(int(process.pid), signal.SIGKILL)
                with contextlib.suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=0.5)
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    with contextlib.suppress(Exception):
                        stream.close()


def _attach_process_family(
    registration: _ProcessFamilyRegistration,
    process: subprocess.Popen[Any],
) -> None:
    if not isinstance(process, _POPEN_CLASS):
        raise _contract_error("process-family child handle has the wrong type")
    pid = int(process.pid)
    if pid <= 1 or process.returncode is not None:
        raise _contract_error("process-family leader is unavailable")
    try:
        process_group = os.getpgid(pid)
    except ProcessLookupError as exc:
        if sys.platform != "darwin":
            raise _contract_error(
                "process-family leader exited before registration"
            ) from exc
        observation = _bounded_process_table_observation(
            registration.identity.process_token
        )
        leader = next((row for row in observation.rows if row.pid == pid), None)
        if (
            leader is None
            or leader.uid != registration.identity.owner_uid
            or leader.process_group != pid
            or not leader.state.startswith("Z")
        ):
            raise _contract_error(
                "process-family leader exited before safe registration"
            ) from exc
        process_group = pid
    if process_group != pid:
        raise _contract_error("process-family leader does not own its process group")
    with _PROCESS_FAMILIES_LOCK:
        current = _PROCESS_FAMILIES_BY_TOKEN.get(
            registration.identity.process_token
        )
        if current is not registration or registration.state != "reserved":
            raise _contract_error("process-family reservation is not live")
        if id(process) in _PROCESS_FAMILIES_BY_PROCESS:
            raise _contract_error("process-family child is already registered")
        registration.process = process
        registration.leader_pid = pid
        registration.process_group = process_group
        registration.state = "live"
        _PROCESS_FAMILIES_BY_PROCESS[id(process)] = registration


def _retain_unregistered_process_family(
    registration: _ProcessFamilyRegistration,
    process: subprocess.Popen[Any],
) -> None:
    """Keep a failed attachment reachable until cleanup is proven complete."""

    if not isinstance(process, _POPEN_CLASS):
        raise _contract_error("failed process-family child has the wrong type")
    pid = int(process.pid)
    if pid <= 1:
        raise _contract_error("failed process-family leader is invalid")
    with _PROCESS_FAMILIES_LOCK:
        current = _PROCESS_FAMILIES_BY_TOKEN.get(
            registration.identity.process_token
        )
        if current is not registration or registration.state == "released":
            raise _contract_error("failed process-family reservation is not live")
        by_process = _PROCESS_FAMILIES_BY_PROCESS.get(id(process))
        if by_process is not None and by_process is not registration:
            raise _contract_error("failed process-family child identity collided")
        registration.process = process
        registration.leader_pid = pid
        registration.process_group = pid
        registration.state = "cleanup-pending"
        _PROCESS_FAMILIES_BY_PROCESS[id(process)] = registration


def _claim_process_family(
    process: subprocess.Popen[Any],
) -> _ProcessFamilyRegistration:
    if not isinstance(process, _POPEN_CLASS):
        raise _contract_error("clean-exit process handle has the wrong type")
    with _PROCESS_FAMILIES_LOCK:
        registration = _PROCESS_FAMILIES_BY_PROCESS.get(id(process))
        if (
            registration is None
            or registration.process is not process
            or registration.state != "live"
        ):
            raise _contract_error(
                "clean-exit process family is unknown, claimed, or already used"
            )
        if process.returncode is not None:
            raise _contract_error("owned process leader was already reaped")
        registration.state = "claimed"
        return registration


def _signal_process_family_observation(
    identity: _ProcessFamilyIdentity,
    *,
    process_group: int,
    observation: _ProcessTableObservation,
    signum: int,
    allow_original_group: bool,
) -> None:
    """Signal only groups proven family-exclusive, otherwise exact token PIDs."""

    token_rows = tuple(
        row
        for row in observation.rows
        if row.uid == identity.owner_uid and row.has_family_token
    )
    original_group_rows = tuple(
        row
        for row in observation.rows
        if allow_original_group and row.process_group == process_group
    )
    target_rows = tuple(
        sorted(
            {row.pid: row for row in (*token_rows, *original_group_rows)}.values(),
            key=lambda row: row.pid,
        )
    )
    target_pids = {row.pid for row in target_rows if not row.state.startswith("Z")}
    covered_pids: set[int] = set()
    for candidate_group in sorted(
        {row.process_group for row in target_rows if row.process_group > 1}
    ):
        group_rows = tuple(
            row
            for row in observation.rows
            if row.process_group == candidate_group
        )
        acting_rows = tuple(
            row for row in group_rows if not row.state.startswith("Z")
        )
        is_exclusive_token_group = bool(acting_rows) and all(
            row.uid == identity.owner_uid and row.has_family_token
            for row in acting_rows
        )
        may_signal_group = (
            candidate_group == process_group and allow_original_group
        ) or is_exclusive_token_group
        if not may_signal_group:
            continue
        try:
            os.killpg(candidate_group, signum)
        except ProcessLookupError:
            pass
        except PermissionError:
            # Darwin can reject killpg across a descendant's new session even
            # though same-UID exact-PID signals remain permitted.  Leaving the
            # rows uncovered below performs that narrower authenticated
            # fallback; an exact-PID permission failure still fails closed.
            continue
        else:
            covered_pids.update(row.pid for row in acting_rows)
    for row in target_rows:
        if row.pid in covered_pids or row.pid not in target_pids or row.pid <= 1:
            continue
        try:
            os.kill(row.pid, signum)
        except ProcessLookupError:
            continue
        except PermissionError as exc:
            raise _contract_error(
                "owned process family could not be signalled"
            ) from exc


def _cleanup_unregistered_process(
    process: subprocess.Popen[Any],
    registration: _ProcessFamilyRegistration,
) -> None:
    pid = int(process.pid)
    if pid <= 1:
        raise _contract_error("unregistered process-family leader is invalid")
    deadline = time.monotonic() + 2.0
    first_cleanup_error: Exception | None = None

    def remember_cleanup_error(exc: Exception) -> None:
        nonlocal first_cleanup_error
        if first_cleanup_error is None:
            first_cleanup_error = exc

    if sys.platform == "darwin":
        for signum in (signal.SIGTERM, signal.SIGKILL):
            try:
                observation = _bounded_process_table_observation(
                    registration.identity.process_token
                )
                _signal_process_family_observation(
                    registration.identity,
                    process_group=pid,
                    observation=observation,
                    signum=signum,
                    allow_original_group=process.returncode is None,
                )
            except Exception as exc:
                remember_cleanup_error(exc)
            if process.returncode is None:
                try:
                    os.killpg(pid, signum)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    try:
                        os.kill(pid, signum)
                    except ProcessLookupError:
                        pass
                    except OSError as exact_error:
                        remember_cleanup_error(exact_error)
                except OSError as group_error:
                    remember_cleanup_error(group_error)
                    try:
                        os.kill(pid, signum)
                    except ProcessLookupError:
                        pass
                    except OSError as exact_error:
                        remember_cleanup_error(exact_error)
            if signum == signal.SIGTERM:
                time.sleep(0.02)
    elif process.returncode is None and pid > 1:
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError as exc:
            remember_cleanup_error(exc)
    if process.returncode is None:
        try:
            process.wait(timeout=max(0.01, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(pid, signal.SIGKILL)
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired as exc:
                raise _contract_error(
                    "unregistered process-family leader could not be reaped"
                ) from exc
    if sys.platform == "darwin":
        while True:
            try:
                observation = _bounded_process_table_observation(
                    registration.identity.process_token
                )
            except Exception as exc:
                remember_cleanup_error(exc)
                break
            survivors = tuple(
                row
                for row in observation.rows
                if row.uid == registration.identity.owner_uid
                and row.has_family_token
            )
            if not survivors:
                break
            if time.monotonic() >= deadline:
                raise _contract_error(
                    "unregistered process family retained acting descendants"
                )
            _signal_process_family_observation(
                registration.identity,
                process_group=pid,
                observation=observation,
                signum=signal.SIGKILL,
                allow_original_group=False,
            )
            time.sleep(min(0.02, deadline - time.monotonic()))
    if first_cleanup_error is not None:
        raise _contract_error(
            "unregistered process-family cleanup could not prove closure after "
            "reaping its leader"
        ) from first_cleanup_error


def _wait_for_unreaped_exit(
    registration: _ProcessFamilyRegistration, *, timeout: float
) -> tuple[int, int | None, _ProcessTableObservation]:
    timeout_value = _validated_timeout(timeout, label="clean-exit")
    if sys.platform != "darwin":
        raise DependencyUnavailable(
            "clean process-family exit requires Darwin process observation"
        )
    if (
        registration.process is None
        or registration.leader_pid is None
        or registration.process_group is None
    ):
        raise _contract_error("process-family registration is incomplete")
    deadline = time.monotonic() + timeout_value
    while True:
        observation = _bounded_process_table_observation(
            registration.identity.process_token
        )
        leader = next(
            (
                row
                for row in observation.rows
                if row.pid == registration.leader_pid
            ),
            None,
        )
        if leader is None:
            raise _contract_error(
                "owned process leader disappeared before family closure"
            )
        if (
            leader.uid != registration.identity.owner_uid
            or leader.process_group != registration.process_group
        ):
            raise _contract_error("owned process leader identity changed")
        if leader.state.startswith("Z"):
            if os.WIFEXITED(leader.wait_status):
                return os.WEXITSTATUS(leader.wait_status), None, observation
            if os.WIFSIGNALED(leader.wait_status):
                exit_signal = os.WTERMSIG(leader.wait_status)
                return -exit_signal, exit_signal, observation
            raise _contract_error("owned process leader wait status is unsupported")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _contract_error(
                "owned process leader did not exit before timeout"
            )
        time.sleep(min(0.02, remaining))


def _assert_pre_reap_family_closed(
    registration: _ProcessFamilyRegistration,
    observation: _ProcessTableObservation,
) -> None:
    assert registration.leader_pid is not None
    assert registration.process_group is not None
    group_rows = tuple(
        row
        for row in observation.rows
        if row.process_group == registration.process_group
    )
    if not (
        len(group_rows) == 1
        and group_rows[0].pid == registration.leader_pid
        and group_rows[0].uid == registration.identity.owner_uid
        and group_rows[0].state.startswith("Z")
    ):
        raise _contract_error(
            "owned process group retained descendants after leader exit"
        )
    token_descendants = tuple(
        row
        for row in observation.rows
        if row.uid == registration.identity.owner_uid
        and row.has_family_token
        and row.pid != registration.leader_pid
    )
    if token_descendants:
        raise _contract_error(
            "owned process family retained descendants outside its original group"
        )


def _assert_post_reap_family_closed(
    registration: _ProcessFamilyRegistration,
    observation: _ProcessTableObservation,
) -> None:
    assert registration.process_group is not None
    if any(
        row.process_group == registration.process_group
        or (
            row.uid == registration.identity.owner_uid
            and row.has_family_token
        )
        for row in observation.rows
    ):
        raise _contract_error("owned process family remained present after reap")


def _process_exit_digest(
    identity: _ProcessFamilyIdentity, payload: Mapping[str, Any]
) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "identity": {
                    "sessionId": identity.session_id,
                    "role": identity.role,
                    "processId": identity.process_id,
                    "processToken": identity.process_token,
                    "launchIdentitySha256": identity.launch_identity_sha256,
                    "ownerUid": identity.owner_uid,
                },
                "payload": dict(payload),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def wait_for_clean_owned_process_group_exit(
    process: subprocess.Popen[Any],
    *,
    timeout: float = 10.0,
) -> QuiescentProcessExit:
    """Mint one proof for the bound PGID plus token-bearing descendants.

    This is an operational shutdown assertion for the trusted, frozen browser
    worker and its per-run calibrated runtime.  It intentionally does not claim
    to discover an adversarial descendant that both changes process group and
    removes its inherited token; Seatbelt prevents such a process from reaching
    production or coordinator-only evidence roots.
    """

    timeout_value = _validated_timeout(timeout, label="clean-exit")
    registration = _claim_process_family(process)
    return_code, exit_signal, observation = _wait_for_unreaped_exit(
        registration, timeout=timeout_value
    )
    _assert_pre_reap_family_closed(registration, observation)
    try:
        reaped = int(process.wait(timeout=timeout_value))
    except subprocess.TimeoutExpired as exc:
        raise _contract_error("owned process leader could not be reaped") from exc
    post_reap = _bounded_process_table_observation(
        registration.identity.process_token
    )
    _assert_post_reap_family_closed(registration, post_reap)
    _release_process_family(registration)
    if reaped != return_code or return_code != 0 or exit_signal is not None:
        raise _contract_error("owned process leader did not exit cleanly")
    payload: Mapping[str, Any] = MappingProxyType(
        {
            "sessionId": registration.identity.session_id,
            "role": registration.identity.role,
            "processId": registration.identity.process_id,
            "launchIdentitySha256": registration.identity.launch_identity_sha256,
            "returnCode": return_code,
            "signal": exit_signal,
            "quiescent": True,
        }
    )
    digest = _process_exit_digest(registration.identity, payload)
    with _QUIESCENT_PROCESS_EXITS_LOCK:
        if len(_QUIESCENT_PROCESS_EXITS) >= MAX_PROCESS_EXIT_PROOFS:
            raise _contract_error("process-exit attestation registry is full")
        while True:
            token = secrets.token_hex(32)
            if token not in _QUIESCENT_PROCESS_EXITS:
                break
        attestation = QuiescentProcessExit(token)
        _QUIESCENT_PROCESS_EXITS[token] = (
            attestation,
            registration.identity,
            payload,
            digest,
        )
    return attestation


def consume_quiescent_process_exit_provenance(
    attestation: QuiescentProcessExit,
    *,
    expected_session_id: str,
    expected_role: str,
    expected_process_id: str,
) -> tuple[dict[str, Any], str]:
    """Atomically authenticate and consume one opaque clean-exit proof."""

    session_id = _validated_session_id(expected_session_id)
    process_id = _validated_process_id(expected_process_id)
    if expected_role not in {"app", "browser"}:
        raise _contract_error("process-exit expected role is invalid")
    if not isinstance(attestation, QuiescentProcessExit):
        raise _contract_error("process-exit attestation has the wrong type")
    with _QUIESCENT_PROCESS_EXITS_LOCK:
        registered = _QUIESCENT_PROCESS_EXITS.get(attestation._token)
        if registered is None or registered[0] is not attestation:
            raise _contract_error("process-exit attestation lacks live provenance")
        _proof, identity, payload, digest = registered
        if (
            identity.session_id != session_id
            or identity.role != expected_role
            or identity.process_id != process_id
        ):
            raise _contract_error("process-exit attestation identity differs")
        if _process_exit_digest(identity, payload) != digest:
            raise _contract_error(
                "process-exit attestation changed after registration"
            )
        _QUIESCENT_PROCESS_EXITS.pop(attestation._token, None)
        return dict(payload), digest


def validate_quiescent_process_exit_provenance(
    attestation: QuiescentProcessExit,
    *,
    expected_session_id: str,
    expected_role: str,
    expected_process_id: str,
) -> tuple[dict[str, Any], str]:
    """Compatibility name for the mandatory one-shot consume operation."""

    return consume_quiescent_process_exit_provenance(
        attestation,
        expected_session_id=expected_session_id,
        expected_role=expected_role,
        expected_process_id=expected_process_id,
    )


def terminate_owned_process_group(
    process: subprocess.Popen[Any],
    *,
    timeout: float = 3.0,
) -> None:
    """Make an unreaped child group non-acting, then reap its leader safely."""

    if not isinstance(process, _POPEN_CLASS):
        raise _contract_error("owned process handle has the wrong type")
    timeout_value = _validated_timeout(timeout, label="owned process-group")
    pid = int(process.pid)
    if pid <= 1:
        raise _contract_error("owned process-group id is invalid")
    with _PROCESS_FAMILIES_LOCK:
        family = _PROCESS_FAMILIES_BY_PROCESS.get(id(process))
        if family is not None and family.process is not process:
            family = None
    if family is not None:
        deadline = time.monotonic() + timeout_value

        def signal_family(signum: int) -> None:
            observation = _bounded_process_table_observation(
                family.identity.process_token
            )
            assert family.process_group is not None
            _signal_process_family_observation(
                family.identity,
                process_group=family.process_group,
                observation=observation,
                signum=signum,
                allow_original_group=process.returncode is None,
            )

        signal_family(signal.SIGTERM)
        time.sleep(min(0.05, timeout_value / 4.0))
        signal_family(signal.SIGKILL)
        if process.returncode is None:
            remaining = max(0.01, deadline - time.monotonic())
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired as exc:
                raise _contract_error(
                    "owned process leader did not become quiescent"
                ) from exc
        while True:
            observation = _bounded_process_table_observation(
                family.identity.process_token
            )
            try:
                _assert_post_reap_family_closed(family, observation)
            except IsolationContractError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(min(0.02, deadline - time.monotonic()))
                continue
            break
        _release_process_family(family)
        return

    with _TERMINATION_ONLY_PROCESS_GROUPS_LOCK:
        registered = _TERMINATION_ONLY_PROCESS_GROUPS.get(id(process))
    if process.returncode is not None:
        _forget_owned_process_group(process)
        return
    if registered is None or registered[0] is not process:
        _register_owned_process_group(process)
        process_group = pid
    else:
        process_group = registered[1]
    for signum in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process_group, signum)
        except ProcessLookupError:
            pass
        except PermissionError:
            # Seatbelt can make a group signal fail even while exact same-UID
            # member signals remain allowed.  The unreaped session leader
            # still reserves this original PGID, so a fresh Darwin snapshot
            # safely identifies the exact fallback members.
            if sys.platform == "darwin":
                observation = _bounded_process_table_observation(
                    _new_process_token()
                )
                member_pids = tuple(
                    row.pid
                    for row in observation.rows
                    if row.process_group == process_group
                    and row.uid == os.getuid()
                    and not row.state.startswith("Z")
                )
            else:
                member_pids = (pid,)
            for member_pid in member_pids:
                try:
                    os.kill(member_pid, signum)
                except ProcessLookupError:
                    continue
                except PermissionError as exc:
                    raise _contract_error(
                        "owned process group could not be signalled"
                    ) from exc
        if signum == signal.SIGTERM:
            time.sleep(min(0.05, timeout_value / 4.0))
    try:
        process.wait(timeout=timeout_value)
    except subprocess.TimeoutExpired as exc:
        raise _contract_error("owned process leader did not become quiescent") from exc
    finally:
        _forget_owned_process_group(process)


def _run_app_calibration(
    contract: DarwinIsolationContract,
    profile: str,
    files: _CalibrationFiles,
    *,
    timeout: float,
) -> dict[str, Any]:
    session_root = create_owned_run_root(
        contract.app_writable_root,
        prefix=".ux1b-calibration-",
    )
    process: subprocess.Popen[bytes] | None = None
    denied_listener: _ProbeListener | None = None
    production_fd: int | None = None
    try:
        other_bind_port = _fresh_unbound_port((contract.app_port, contract.denied_port))
        denied_listener = _ProbeListener(contract.denied_port)
        production_fd = os.open(contract.production_probe_path, _SAFE_READ_FLAGS)
        os.set_inheritable(production_fd, True)
        outside_probe = files.ephemeral_probes[2]
        outside_probe.authenticate(expected_root=files.outside_private.parent)
        symlink_probe = _create_calibration_symlink(
            session_root,
            name="production-symlink-probe",
            target=contract.production_probe_path,
        )
        command = [
            str(SANDBOX_EXEC),
            "-p",
            profile,
            str(contract.python_executable),
            "-c",
            _APP_CALIBRATION_SCRIPT,
            str(files.source_probe),
            str(contract.production_probe_path),
            str(files.sqlite_probe),
            str(symlink_probe),
            str(files.outside_private),
            str(contract.app_port),
            str(other_bind_port),
            str(contract.denied_port),
            str(production_fd),
        ]
        process = subprocess.Popen(
            command,
            cwd=contract.source_root,
            env=_calibration_environment(
                "app",
                contract,
                writable_root=session_root.path,
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            # Deliberately make the coordinator descriptor inheritable, then
            # use the exact production spawn contract.  The child receives the
            # numeric probe value but close_fds + empty pass_fds must make it
            # EBADF; explicitly passing it would test a configuration that the
            # production launcher forbids and macOS cannot retroactively revoke.
            pass_fds=(),
            start_new_session=True,
        )
        _register_owned_process_group(process)
        if process.stdout is None:  # pragma: no cover - fixed Popen.
            raise _contract_error("app calibration output pipe is missing")
        reader = _BoundedJsonLineReader(process.stdout)
        try:
            ready = reader.read_object(
                timeout=timeout,
                label="app calibration ready",
            )
        except IsolationContractError as exc:
            returncode = process.poll()
            raise _contract_error(
                f"app calibration failed before ready (exit={returncode})"
            ) from exc
        if ready != {"ready": True}:
            raise _contract_error("app calibration ready record differs")
        with socket.create_connection(("127.0.0.1", contract.app_port), timeout=3.0) as client:
            client.sendall(b"owned-app-probe")
        result = reader.read_object(timeout=timeout, label="app calibration result")
        reader.finish_exact(timeout=timeout, label="app calibration output")
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise _contract_error("app calibration child timed out") from exc
        if returncode != 0:
            raise _contract_error(f"app calibration child failed (exit={returncode})")
        time.sleep(0.15)
        observations = {
            "acceptedBytes": int(result.get("acceptedBytes") or 0),
            "assignedPortBytes": 0,
            "deniedListenerBytes": denied_listener.total_bytes,
            "productionFdBytes": int(result.get("productionFdBytes") or 0),
            "unexpectedContacts": [],
        }
        return {
            "allowed": result.get("allowed"),
            "denied": result.get("denied"),
            "details": result.get("details"),
            "observations": observations,
        }
    finally:
        cleanup_error: BaseException | None = None
        if process is not None and process.poll() is None:
            try:
                terminate_owned_process_group(process)
            except BaseException as exc:  # noqa: BLE001 - cleanup must continue.
                cleanup_error = exc
        if process is not None and process.stdout is not None:
            try:
                process.stdout.close()
            except BaseException as exc:  # noqa: BLE001 - cleanup must continue.
                if cleanup_error is None:
                    cleanup_error = exc
        if production_fd is not None:
            try:
                os.close(production_fd)
            except BaseException as exc:  # noqa: BLE001 - cleanup must continue.
                if cleanup_error is None:
                    cleanup_error = exc
        if denied_listener is not None:
            try:
                denied_listener.close()
            except BaseException as exc:  # noqa: BLE001 - cleanup must continue.
                if cleanup_error is None:
                    cleanup_error = exc
        if not session_root._closed:
            try:
                remove_owned_run_root(session_root)
            except BaseException as exc:  # noqa: BLE001 - cleanup must continue.
                if cleanup_error is None:
                    cleanup_error = exc
        if process is not None:
            _forget_owned_process_group(process)
        if cleanup_error is not None:
            raise cleanup_error


def _run_browser_calibration(
    contract: DarwinIsolationContract,
    profile: str,
    files: _CalibrationFiles,
    *,
    timeout: float,
) -> dict[str, Any]:
    session_root = create_owned_run_root(
        contract.browser_writable_root,
        prefix=".ux1b-calibration-",
    )
    process: subprocess.Popen[bytes] | None = None
    assigned_listener: _ProbeListener | None = None
    denied_listener: _ProbeListener | None = None
    try:
        other_bind_port = _fresh_unbound_port(
            (contract.app_port, contract.denied_port)
        )
        handshake_token = secrets.token_hex(24)
        html = (
            '<!doctype html><html><body><div id="ux1b-calibration" data-token="'
            + handshake_token
            + '">UX1B-DOM-READY</div></body></html>'
        ).encode("utf-8")
        response = (
            b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
            + f"Content-Length: {len(html)}\r\n".encode("ascii")
            + b"Connection: close\r\n\r\n"
            + html
        )
        assigned_listener = _ProbeListener(contract.app_port, response=response)
        denied_listener = _ProbeListener(contract.denied_port)
        app_probe, final_probe, outside_probe = files.ephemeral_probes
        app_probe.authenticate(expected_root=contract.app_writable_root)
        final_probe.authenticate(expected_root=contract.final_evidence_root)
        outside_probe.authenticate(expected_root=files.outside_private.parent)
        symlink_probe = _create_calibration_symlink(
            session_root,
            name="production-symlink-probe",
            target=contract.production_probe_path,
        )
        command = [
            str(SANDBOX_EXEC),
            "-p",
            profile,
            str(contract.python_executable),
            "-c",
            _BROWSER_CALIBRATION_SCRIPT,
            str(files.source_probe),
            str(contract.production_probe_path),
            str(files.app_private),
            str(files.final_private),
            str(contract.browser_executable),
            handshake_token,
            str(symlink_probe),
            str(files.outside_private),
            str(contract.app_port),
            str(contract.denied_port),
            str(other_bind_port),
        ]
        process = subprocess.Popen(
            command,
            cwd=contract.source_root,
            env=_calibration_environment(
                "browser",
                contract,
                writable_root=session_root.path,
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            pass_fds=(),
            start_new_session=True,
        )
        _register_owned_process_group(process)
        stdout, stderr = _bounded_communicate(
            process,
            timeout=timeout,
        )
        terminate_owned_process_group(process, timeout=timeout)
        returncode = process.returncode
        if returncode != 0:
            raise _contract_error(
                "browser calibration child failed: "
                + stderr[-500:].decode("utf-8", errors="replace")
            )
        try:
            result = json.loads(stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise _contract_error("browser calibration output is malformed") from exc
        if not isinstance(result, dict):
            raise _contract_error("browser calibration output is not an object")
        time.sleep(0.15)
        observations = {
            "acceptedBytes": 0,
            "assignedPortBytes": assigned_listener.total_bytes,
            "deniedListenerBytes": denied_listener.total_bytes,
            "productionFdBytes": 0,
            "unexpectedContacts": [],
            "appFixtureProbeRootExact": True,
            "finalEvidenceProbeRootExact": True,
            "domHandshake": bool(
                isinstance(result.get("allowed"), dict)
                and result["allowed"].get("chromiumDomHandshake") is True
            ),
        }
        return {
            "allowed": result.get("allowed"),
            "denied": result.get("denied"),
            "details": result.get("details"),
            "observations": observations,
        }
    finally:
        cleanup_error: BaseException | None = None
        if process is not None:
            try:
                terminate_owned_process_group(process)
            except BaseException as exc:  # noqa: BLE001 - cleanup must continue.
                cleanup_error = exc
        if process is not None:
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except BaseException as exc:  # noqa: BLE001 - cleanup must continue.
                        if cleanup_error is None:
                            cleanup_error = exc
        if assigned_listener is not None:
            try:
                assigned_listener.close()
            except BaseException as exc:  # noqa: BLE001 - cleanup must continue.
                if cleanup_error is None:
                    cleanup_error = exc
        if denied_listener is not None:
            try:
                denied_listener.close()
            except BaseException as exc:  # noqa: BLE001 - cleanup must continue.
                if cleanup_error is None:
                    cleanup_error = exc
        if not session_root._closed:
            try:
                remove_owned_run_root(session_root)
            except BaseException as exc:  # noqa: BLE001 - cleanup must continue.
                if cleanup_error is None:
                    cleanup_error = exc
        if cleanup_error is not None:
            raise cleanup_error


def _finalize_probe_row(
    raw: Mapping[str, Any],
    *,
    profile: str,
    allowed_names: frozenset[str],
    denied_names: frozenset[str],
) -> dict[str, Any]:
    allowed = raw.get("allowed")
    denied = raw.get("denied")
    observations = raw.get("observations")
    details = raw.get("details")
    if not isinstance(allowed, dict) or set(allowed) != allowed_names:
        raise _contract_error("calibration positive probe set differs")
    if not isinstance(denied, dict) or set(denied) != denied_names:
        raise _contract_error("calibration negative probe set differs")
    if not isinstance(observations, dict):
        raise _contract_error("calibration observations are missing")
    if not isinstance(details, dict):
        raise _contract_error("calibration denial details are missing")
    for name in denied_names:
        detail = details.get(name)
        if not isinstance(detail, dict):
            raise _contract_error(f"calibration denial detail is missing: {name}")
        if "type" in detail:
            if not (
                name == "closureSqliteRead"
                and detail.get("type") == "OperationalError"
                and detail.get("policyDenied") is True
            ):
                raise _contract_error(
                    f"calibration probe raised an unexpected exception: {name}"
                )
            continue
        expected_errnos = {getattr(errno, "EPERM", 1), getattr(errno, "EACCES", 13)}
        if name == "productionFdRead":
            expected_errnos.add(getattr(errno, "EBADF", 9))
        if detail.get("errno") not in expected_errnos:
            raise _contract_error(f"calibration denial errno differs: {name}")
    browser_probe_roots_exact = bool(
        allowed_names != _BROWSER_ALLOWED
        or (
            observations.get("appFixtureProbeRootExact") is True
            and observations.get("finalEvidenceProbeRootExact") is True
        )
    )
    passed = bool(
        all(value is True for value in allowed.values())
        and all(value is True for value in denied.values())
        and observations.get("deniedListenerBytes") == 0
        and observations.get("productionFdBytes") == 0
        and observations.get("unexpectedContacts") == []
        and browser_probe_roots_exact
    )
    return {
        "passed": passed,
        "profileSha256": hashlib.sha256(profile.encode("utf-8")).hexdigest(),
        "allowed": dict(sorted(allowed.items())),
        "denied": dict(sorted(denied.items())),
        "observations": observations,
        "details": details,
    }


_APP_ALLOWED = frozenset(
    {
        "sourceRead",
        "fixtureWrite",
        "streamlitWrite",
        "temporaryWrite",
        "assignedBind",
        "assignedAccept",
    }
)
_APP_DENIED = frozenset(
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
_BROWSER_ALLOWED = frozenset(
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
_BROWSER_DENIED = frozenset(
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


def calibrate_darwin_profiles(
    contract: DarwinIsolationContract,
    *,
    profiles: DarwinProfiles,
    timeout: float = 45.0,
) -> dict[str, Any]:
    """Run positive and adversarial probes inside the exact production profiles."""

    if sys.platform != "darwin":
        raise DependencyUnavailable(
            "Darwin Seatbelt is the only implemented UX-1B isolation backend"
        )
    if not SANDBOX_EXEC.is_file() or not os.access(SANDBOX_EXEC, os.X_OK):
        raise DependencyUnavailable("Darwin sandbox-exec Seatbelt backend is unavailable")
    value = _validated_contract(contract)
    if not isinstance(profiles, DarwinProfiles):
        raise _contract_error("Darwin profiles have the wrong type")
    expected = build_darwin_profiles(value)
    if profiles != expected:
        raise _contract_error("calibration profile differs from production profile")
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise _contract_error("calibration timeout must be positive")
    launch_identity_sha256 = _contract_identity_sha256(value)
    calibration_root = create_owned_run_root(
        _common_run_root(value),
        prefix=".ux1b-calibration-",
    )
    files: _CalibrationFiles | None = None
    try:
        files = _prepare_calibration_files(value, calibration_root.path)
        app_raw = _run_app_calibration(
            value,
            profiles.app,
            files,
            timeout=float(timeout),
        )
        app = _finalize_probe_row(
            app_raw,
            profile=profiles.app,
            allowed_names=_APP_ALLOWED,
            denied_names=_APP_DENIED,
        )
        browser_raw = _run_browser_calibration(
            value,
            profiles.browser,
            files,
            timeout=float(timeout),
        )
        browser = _finalize_probe_row(
            browser_raw,
            profile=profiles.browser,
            allowed_names=_BROWSER_ALLOWED,
            denied_names=_BROWSER_DENIED,
        )
    finally:
        cleanup_error: BaseException | None = None
        if files is not None:
            for probe in reversed(files.ephemeral_probes):
                try:
                    probe.remove()
                except BaseException as exc:  # noqa: BLE001 - finish all cleanup.
                    if cleanup_error is None:
                        cleanup_error = exc
        if not calibration_root._closed:
            try:
                remove_owned_run_root(calibration_root)
            except BaseException as exc:  # noqa: BLE001 - preserve cleanup failure.
                if cleanup_error is None:
                    cleanup_error = exc
        if cleanup_error is not None:
            raise cleanup_error
    if _contract_identity_sha256(value) != launch_identity_sha256:
        raise _contract_error("runtime identity changed during calibration")
    passed = bool(app["passed"] and browser["passed"])
    if not passed:
        failures = {
            "app": {
                "allowed": [key for key, value in app["allowed"].items() if not value],
                "denied": [key for key, value in app["denied"].items() if not value],
                "details": app["details"],
            },
            "browser": {
                "allowed": [key for key, value in browser["allowed"].items() if not value],
                "denied": [key for key, value in browser["denied"].items() if not value],
                "details": browser["details"],
            },
        }
        raise _contract_error(
            "Darwin dual-profile calibration failed: "
            + json.dumps(failures, ensure_ascii=False, sort_keys=True)
        )
    report = {
        "schemaVersion": CALIBRATION_SCHEMA,
        "capability": "supported",
        "platform": "darwin",
        "passed": True,
        "profilesAreDistinct": profiles.app != profiles.browser,
        "inheritedFdProbeExplicit": True,
        "launchIdentitySha256": launch_identity_sha256,
        "app": app,
        "browser": browser,
    }
    report_payload = json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    report_digest = hashlib.sha256(report_payload).hexdigest()
    with _CALIBRATION_REPORTS_LOCK:
        if len(_CALIBRATION_REPORTS) >= 128:
            oldest = next(iter(_CALIBRATION_REPORTS))
            _CALIBRATION_REPORTS.pop(oldest, None)
            _CALIBRATION_REPORT_DIGESTS.pop(oldest, None)
        _CALIBRATION_REPORTS[id(report)] = report
        _CALIBRATION_REPORT_DIGESTS[id(report)] = report_digest
    return report
