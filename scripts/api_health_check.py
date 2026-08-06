#!/usr/bin/env python3
"""Validate the loopback API health response and listener ownership."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


EXPECTED_HEALTH = {"status": "ok", "apiVersion": "v1"}
MAX_HEALTH_BYTES = 64 * 1024
_PID_RE = re.compile(r"\bpid=(\d+),")
_SOCKET_INODE_RE = re.compile(r"^socket:\[(\d+)\]$")
_TCP_LISTEN = "0A"
_PROC_ROOT = Path("/proc")


class _RejectRedirects(HTTPRedirectHandler):
    """Keep health validation bound to the requested endpoint."""

    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


_DIRECT_OPENER = build_opener(ProxyHandler({}), _RejectRedirects())


def is_expected_health_response(
    status: int | None,
    content_type: str,
    payload: bytes,
) -> bool:
    """Return true only for the exact v1 process-health contract."""

    if status != 200 or content_type.partition(";")[0].strip().lower() != "application/json":
        return False
    if len(payload) > MAX_HEALTH_BYTES:
        return False
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return decoded == EXPECTED_HEALTH


def listener_is_owned(output: str, main_pid: int, host: str, port: int) -> bool:
    """Validate one numeric ss listener owned by the systemd MainPID."""

    rows = [line.split() for line in output.splitlines() if line.strip()]
    if main_pid <= 0 or len(rows) != 1 or len(rows[0]) < 5:
        return False
    row = rows[0]
    if row[3] != f"{host}:{port}":
        return False
    listener_pids = {int(value) for value in _PID_RE.findall(" ".join(row[5:]))}
    return listener_pids == {main_pid}


def listener_endpoint_is_exact(output: str, host: str, port: int) -> bool:
    """Return true only for one ss listener on the exact IPv4 endpoint."""

    rows = [line.split() for line in output.splitlines() if line.strip()]
    return len(rows) == 1 and len(rows[0]) >= 5 and rows[0][3] == f"{host}:{port}"


def _proc_listeners(proc_root: Path, port: int) -> list[tuple[str, str, str, str]] | None:
    """Read TCP listeners as (family, address, port, inode) tuples."""

    listeners: list[tuple[str, str, str, str]] = []
    for family, relative_path in (("ipv4", "net/tcp"), ("ipv6", "net/tcp6")):
        try:
            lines = (proc_root / relative_path).read_text(encoding="ascii").splitlines()[1:]
        except (OSError, UnicodeError):
            return None
        for line in lines:
            fields = line.split()
            if len(fields) < 10:
                return None
            try:
                address, raw_port = fields[1].rsplit(":", 1)
                parsed_port = int(raw_port, 16)
            except (ValueError, IndexError):
                return None
            if fields[3] == _TCP_LISTEN and parsed_port == port:
                listeners.append((family, address.upper(), raw_port.upper(), fields[9]))
    return listeners


def _process_socket_inodes(proc_root: Path, main_pid: int) -> set[str] | None:
    """Return socket inodes directly held by the systemd MainPID."""

    try:
        descriptors = list((proc_root / str(main_pid) / "fd").iterdir())
    except OSError:
        return None
    inodes: set[str] = set()
    for descriptor in descriptors:
        try:
            target = os.readlink(descriptor)
        except OSError:
            return None
        match = _SOCKET_INODE_RE.fullmatch(target)
        if match:
            inodes.add(match.group(1))
    return inodes


def proc_listener_is_owned(
    main_pid: int,
    host: str,
    port: int,
    *,
    proc_root: Path = _PROC_ROOT,
) -> bool:
    """Correlate the sole loopback TCP listener inode with MainPID via procfs."""

    if main_pid <= 0:
        return False
    try:
        address = socket.inet_aton(host)[::-1].hex().upper()
    except OSError:
        return False
    listeners = _proc_listeners(proc_root, port)
    owned_inodes = _process_socket_inodes(proc_root, main_pid)
    if listeners is None or owned_inodes is None or len(listeners) != 1:
        return False
    family, endpoint_address, endpoint_port, inode = listeners[0]
    return (
        family == "ipv4"
        and endpoint_address == address
        and endpoint_port == f"{port:04X}"
        and inode in owned_inodes
    )


def _listener_output(port: int) -> str | None:
    try:
        result = subprocess.run(
            ["ss", "-H", "-ltnp", f"sport = :{port}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def _health_response(url: str) -> tuple[int | None, str, bytes] | None:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with _DIRECT_OPENER.open(request, timeout=3) as response:
            return (
                getattr(response, "status", None),
                response.headers.get("Content-Type", ""),
                response.read(MAX_HEALTH_BYTES + 1),
            )
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return None


def _listener_ownership_is_confirmed(
    main_pid: int,
    host: str,
    port: int,
    *,
    listener_probe: Callable[[int], str | None],
    proc_probe: Callable[[int, str, int], bool],
) -> bool:
    """Prefer ss PID data and use procfs only when ss cannot expose a PID."""

    output = listener_probe(port)
    if output is not None and listener_is_owned(output, main_pid, host, port):
        return True
    if output is not None:
        if not listener_endpoint_is_exact(output, host, port):
            return False
        if _PID_RE.search(output):
            return False
    return proc_probe(main_pid, host, port)


def api_is_ready(
    url: str,
    main_pid: int,
    host: str,
    port: int,
    *,
    listener_probe: Callable[[int], str | None] = _listener_output,
    response_probe: Callable[[str], tuple[int | None, str, bytes] | None] = _health_response,
    proc_probe: Callable[[int, str, int], bool] = proc_listener_is_owned,
) -> bool:
    if not _listener_ownership_is_confirmed(
        main_pid,
        host,
        port,
        listener_probe=listener_probe,
        proc_probe=proc_probe,
    ):
        return False
    response = response_probe(url)
    if response is None or not is_expected_health_response(*response):
        return False
    return _listener_ownership_is_confirmed(
        main_pid,
        host,
        port,
        listener_probe=listener_probe,
        proc_probe=proc_probe,
    )


def readiness_diagnostics(url: str, main_pid: int, host: str, port: int) -> dict[str, object]:
    """Collect bounded, credential-free evidence for a failed readiness gate."""

    listener_output = _listener_output(port)
    response = _health_response(url)
    health: dict[str, object]
    if response is None:
        health = {"available": False}
    else:
        status, content_type, payload = response
        health = {
            "available": True,
            "status": status,
            "contentType": content_type,
            "payload": payload[:512].decode("utf-8", errors="replace"),
            "exact": is_expected_health_response(status, content_type, payload),
        }
    return {
        "mainPid": main_pid,
        "endpoint": f"{host}:{port}",
        "ss": {"available": listener_output is not None, "output": listener_output or ""},
        "procOwned": proc_listener_is_owned(main_pid, host, port),
        "health": health,
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    ready_check: Callable[[str, int, str, int], bool] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("main_pid", type=int)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--diagnose", action="store_true")
    args = parser.parse_args(argv)
    check = api_is_ready if ready_check is None else ready_check
    ready = check(args.url, args.main_pid, args.host, args.port)
    if not ready and args.diagnose and ready_check is None:
        print(
            json.dumps(
                readiness_diagnostics(args.url, args.main_pid, args.host, args.port),
                sort_keys=True,
            ),
            file=sys.stderr,
        )
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
