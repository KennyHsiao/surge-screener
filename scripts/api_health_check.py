#!/usr/bin/env python3
"""Validate the loopback API health response and listener ownership."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


EXPECTED_HEALTH = {"status": "ok", "apiVersion": "v1"}
MAX_HEALTH_BYTES = 64 * 1024
_PID_RE = re.compile(r"\bpid=(\d+),")


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


def api_is_ready(
    url: str,
    main_pid: int,
    host: str,
    port: int,
    *,
    listener_probe: Callable[[int], str | None] = _listener_output,
    response_probe: Callable[[str], tuple[int | None, str, bytes] | None] = _health_response,
) -> bool:
    before = listener_probe(port)
    if before is None or not listener_is_owned(before, main_pid, host, port):
        return False
    response = response_probe(url)
    if response is None or not is_expected_health_response(*response):
        return False
    after = listener_probe(port)
    return after is not None and listener_is_owned(after, main_pid, host, port)


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
    args = parser.parse_args(argv)
    check = api_is_ready if ready_check is None else ready_check
    return 0 if check(args.url, args.main_pid, args.host, args.port) else 1


if __name__ == "__main__":
    sys.exit(main())
