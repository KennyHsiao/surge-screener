#!/usr/bin/env python3
"""X login helper for Agent Reach cookies.

This module owns the user-triggered "open X login, then update Agent Reach
config" flow. It intentionally returns only redacted status objects; raw
cookies are written to the Agent Reach config file and are never displayed.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import shutil
import socket
import struct
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable


APP_ROOT = Path(os.environ.get("SURGE_APP_ROOT") or Path.home() / "apps" / "surge-screener")
DEFAULT_CONFIG = Path.home() / ".agent-reach" / "config.yaml"
DEFAULT_PROFILE_DIR = APP_ROOT / "shared" / "agent_reach_x_profile"
DEFAULT_STATE_PATH = APP_ROOT / "shared" / "run_status" / "agent_reach_x_login.json"
DEFAULT_PORT = int(os.environ.get("AGENT_REACH_LOGIN_PORT") or 9229)
X_LOGIN_URL = "https://x.com/login"
_BROWSER_CANDIDATES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "chrome",
)
_X_DOMAINS = {"x.com", ".x.com", "twitter.com", ".twitter.com"}

PopenFactory = Callable[..., Any]


def _mask_secret(value: str) -> str:
    value = str(value or "")
    if not value:
        return ""
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:2]}...{value[-2:]}"


def _safe_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def _config_path(path: str | Path | None = None) -> Path:
    return Path(path or os.environ.get("AGENT_REACH_CONFIG") or DEFAULT_CONFIG).expanduser()


def _state_path(path: str | Path | None = None) -> Path:
    return Path(path or os.environ.get("AGENT_REACH_LOGIN_STATE") or DEFAULT_STATE_PATH).expanduser()


def _profile_dir(path: str | Path | None = None) -> Path:
    return Path(path or os.environ.get("AGENT_REACH_LOGIN_PROFILE") or DEFAULT_PROFILE_DIR).expanduser()


def _is_x_domain(domain: Any) -> bool:
    value = str(domain or "").lower().strip()
    return value in _X_DOMAINS or value.endswith(".x.com") or value.endswith(".twitter.com")


def extract_x_credentials(cookies: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for cookie in cookies:
        if not isinstance(cookie, dict) or not _is_x_domain(cookie.get("domain")):
            continue
        name = str(cookie.get("name") or "")
        value = str(cookie.get("value") or "")
        if name == "auth_token" and value and "auth_token" not in out:
            out["auth_token"] = value
        elif name == "ct0" and value and "ct0" not in out:
            out["ct0"] = value
    return out if out.get("auth_token") and out.get("ct0") else {}


def _parse_simple_yaml(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return data
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        if key.strip():
            data[key.strip()] = value.strip().strip("'\"")
    return data


def _yaml_value(value: str) -> str:
    raw = str(value)
    if raw and not any(ch.isspace() for ch in raw) and not any(ch in raw for ch in ":#'\""):
        return raw
    escaped = raw.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def write_agent_reach_config(
    credentials: dict[str, str],
    *,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    auth = str(credentials.get("auth_token") or "").strip()
    ct0 = str(credentials.get("ct0") or "").strip()
    if not auth or not ct0:
        return {
            "status": "missing",
            "configured": False,
            "note": "Missing auth_token or ct0 from X login session",
        }

    path = _config_path(config_path)
    existing = _parse_simple_yaml(path)
    existing["twitter_auth_token"] = auth
    existing["twitter_ct0"] = ct0

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    lines = [f"{key}: {_yaml_value(value)}" for key, value in sorted(existing.items())]
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    os.chmod(path, 0o600)

    return {
        "status": "updated",
        "configured": True,
        "config_path": str(path),
        "auth_token": _mask_secret(auth),
        "ct0": _mask_secret(ct0),
        "updated_at": int(time.time()),
    }


def agent_reach_config_status(*, config_path: str | Path | None = None) -> dict[str, Any]:
    path = _config_path(config_path)
    data = _parse_simple_yaml(path)
    auth = data.get("twitter_auth_token", "")
    ct0 = data.get("twitter_ct0", "")
    configured = bool(auth and ct0)
    return {
        "configured": configured,
        "status": "configured" if configured else "missing",
        "config_path": str(path),
        "auth_token": _mask_secret(auth),
        "ct0": _mask_secret(ct0),
        "updated_at": int(path.stat().st_mtime) if path.exists() else None,
    }


def find_browser(
    *,
    env: dict[str, str] | None = None,
    which: Callable[[str], str | None] | None = None,
) -> str | None:
    env = env if env is not None else os.environ
    if env.get("AGENT_REACH_BROWSER_BIN"):
        return env["AGENT_REACH_BROWSER_BIN"]
    lookup = which or shutil.which
    for name in _BROWSER_CANDIDATES:
        found = lookup(name)
        if found:
            return found
    return None


def build_browser_command(
    browser_bin: str,
    *,
    profile_dir: str | Path,
    port: int = DEFAULT_PORT,
) -> list[str]:
    return [
        browser_bin,
        f"--user-data-dir={Path(profile_dir)}",
        "--remote-debugging-address=127.0.0.1",
        f"--remote-debugging-port={port}",
        "--no-first-run",
        "--no-default-browser-check",
        "--new-window",
        X_LOGIN_URL,
    ]


def _clean_browser_env(env: dict[str, str]) -> dict[str, str]:
    child_env = dict(env)
    for key in tuple(child_env):
        normalized = key.upper()
        if key == "CT0" or any(
            marker in normalized
            for marker in ("API_KEY", "AUTH_TOKEN", "BEARER_TOKEN", "PASSWORD", "SECRET")
        ):
            child_env.pop(key, None)
    return child_env


def _write_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read_state(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def start_login_session(
    *,
    profile_dir: str | Path | None = None,
    state_path: str | Path | None = None,
    port: int = DEFAULT_PORT,
    env: dict[str, str] | None = None,
    which: Callable[[str], str | None] | None = None,
    popen: PopenFactory | None = None,
) -> dict[str, Any]:
    env = env if env is not None else os.environ
    browser = find_browser(env=env, which=which)
    if not browser:
        return {
            "status": "unavailable",
            "note": "Chrome/Chromium is not installed or AGENT_REACH_BROWSER_BIN is not configured",
        }

    display = env.get("DISPLAY")
    if not display and not env.get("WAYLAND_DISPLAY") and os.name != "nt":
        return {
            "status": "unavailable",
            "note": "No DISPLAY/WAYLAND_DISPLAY available for the test-server browser session",
        }

    profile = _profile_dir(profile_dir)
    state = _state_path(state_path)
    profile.mkdir(parents=True, exist_ok=True)
    argv = build_browser_command(browser, profile_dir=profile, port=port)
    call = popen or subprocess.Popen
    try:
        proc = call(
            argv,
            env=_clean_browser_env(env),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as exc:
        return {"status": "failed", "note": _safe_error(exc)}

    payload = {
        "status": "running",
        "pid": int(getattr(proc, "pid", 0) or 0),
        "port": port,
        "profile_dir": str(profile),
        "login_url": X_LOGIN_URL,
        "started_at": int(time.time()),
    }
    _write_state(state, payload)
    return dict(payload)


def _http_json(url: str, *, timeout: float = 3) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _read_exact(sock: socket.socket, n: int) -> bytes:
    chunks: list[bytes] = []
    remaining = n
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise RuntimeError("WebSocket connection closed")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _ws_send_json(sock: socket.socket, payload: dict[str, Any]) -> None:
    data = json.dumps(payload).encode("utf-8")
    header = bytearray([0x81])
    if len(data) < 126:
        header.append(0x80 | len(data))
    elif len(data) < 65536:
        header.append(0x80 | 126)
        header.extend(struct.pack("!H", len(data)))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack("!Q", len(data)))
    mask = secrets.token_bytes(4)
    header.extend(mask)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    sock.sendall(bytes(header) + masked)


def _ws_recv_json(sock: socket.socket, *, timeout: float = 5) -> dict[str, Any]:
    sock.settimeout(timeout)
    while True:
        first = _read_exact(sock, 2)
        opcode = first[0] & 0x0F
        length = first[1] & 0x7F
        masked = bool(first[1] & 0x80)
        if length == 126:
            length = struct.unpack("!H", _read_exact(sock, 2))[0]
        elif length == 127:
            length = struct.unpack("!Q", _read_exact(sock, 8))[0]
        mask = _read_exact(sock, 4) if masked else b""
        data = _read_exact(sock, length) if length else b""
        if masked:
            data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        if opcode == 8:
            raise RuntimeError("WebSocket closed")
        if opcode == 9:
            continue
        if opcode == 1:
            parsed = json.loads(data.decode("utf-8"))
            return parsed if isinstance(parsed, dict) else {}


def _cdp_call(ws_url: str, method: str, *, timeout: float = 5) -> dict[str, Any]:
    if not ws_url.startswith("ws://"):
        raise ValueError("Only local ws:// CDP endpoints are supported")
    target = ws_url[len("ws://"):]
    host_port, path = target.split("/", 1)
    host, port_s = host_port.rsplit(":", 1)
    port = int(port_s)
    key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
    request = (
        f"GET /{path} HTTP/1.1\r\n"
        f"Host: {host_port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    )
    expected = base64.b64encode(
        hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
    ).decode("ascii")

    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            response += sock.recv(4096)
        header_text = response.decode("iso-8859-1", errors="replace")
        if " 101 " not in header_text or expected not in header_text:
            raise RuntimeError("CDP WebSocket handshake failed")
        _ws_send_json(sock, {"id": 1, "method": method})
        while True:
            msg = _ws_recv_json(sock, timeout=timeout)
            if msg.get("id") == 1:
                return msg


def select_cdp_ws_url(targets: list[dict[str, Any]], version: dict[str, Any]) -> str:
    pages = [
        target for target in targets
        if isinstance(target, dict)
        and str(target.get("type") or "") in {"page", "webview"}
        and target.get("webSocketDebuggerUrl")
    ]
    for target in pages:
        url = str(target.get("url") or "").lower()
        if "x.com" in url or "twitter.com" in url:
            return str(target["webSocketDebuggerUrl"])
    if pages:
        return str(pages[0]["webSocketDebuggerUrl"])
    return str(version.get("webSocketDebuggerUrl") or "")


def read_cdp_cookies(*, port: int = DEFAULT_PORT, timeout: float = 5) -> list[dict[str, Any]]:
    try:
        targets = _http_json(f"http://127.0.0.1:{port}/json", timeout=timeout)
    except Exception:
        targets = []
    version = _http_json(f"http://127.0.0.1:{port}/json/version", timeout=timeout)
    ws_url = select_cdp_ws_url(targets if isinstance(targets, list) else [], version)
    response = _cdp_call(ws_url, "Network.getAllCookies", timeout=timeout)
    if response.get("error"):
        response = _cdp_call(ws_url, "Storage.getCookies", timeout=timeout)
    cookies = ((response.get("result") or {}).get("cookies") or [])
    return cookies if isinstance(cookies, list) else []


def update_config_from_cookies(
    cookies: list[dict[str, Any]],
    *,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    credentials = extract_x_credentials(cookies)
    if not credentials:
        return {
            "status": "missing",
            "configured": False,
            "note": "X login cookies not found yet. Complete login in the dedicated browser session first.",
        }
    return write_agent_reach_config(credentials, config_path=config_path)


def update_config_from_running_session(
    *,
    state_path: str | Path | None = None,
    config_path: str | Path | None = None,
    timeout: float = 5,
) -> dict[str, Any]:
    state = _read_state(_state_path(state_path))
    port = int(state.get("port") or DEFAULT_PORT)
    try:
        cookies = read_cdp_cookies(port=port, timeout=timeout)
    except Exception as exc:
        return {
            "status": "unavailable",
            "configured": False,
            "note": f"Cannot read dedicated browser session: {_safe_error(exc)}",
        }
    result = update_config_from_cookies(cookies, config_path=config_path)
    if result.get("status") == "updated":
        result["profile_dir"] = state.get("profile_dir")
    return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Manage Agent Reach X login cookies")
    parser.add_argument("action", choices=["status", "start-login", "update-config"])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    if args.action == "status":
        payload = agent_reach_config_status(config_path=args.config)
    elif args.action == "start-login":
        payload = start_login_session(port=args.port)
    else:
        payload = update_config_from_running_session(config_path=args.config)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") in {"configured", "running", "updated"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
