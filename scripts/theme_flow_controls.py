#!/usr/bin/env python3
"""Background controls for the Streamlit theme-flow page.

The UI must not call slow yfinance/LLM work on the render thread. It reads the
latest persisted snapshot immediately, then asks this module to start a detached
worker when data is missing, stale, or manually refreshed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Callable
from typing import Literal


REPO = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO / "reports"
RUN_STATUS_DIR = REPORTS_DIR / "run_status"
SNAPSHOT_PATH = REPORTS_DIR / "theme_flow_snapshot.json"
SNAPSHOT_ARCHIVE_DIR = REPORTS_DIR / "theme_flow_snapshots"
WORKER_SCRIPT = REPO / "scripts" / "theme_flow_background.py"
SNAPSHOT_TTL_SECONDS = 3600

RunMode = Literal["refresh_board", "ai_read"]
MODE_LABELS = {
    "refresh_board": "theme flow refresh",
    "ai_read": "theme flow AI read",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_json(path: Path, data: dict) -> None:
    if path.is_symlink():
        path = path.resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _theme_flow_schema_version() -> int | None:
    try:
        try:
            from scripts import theme_flow
        except ImportError:
            import theme_flow  # type: ignore
        return getattr(theme_flow, "THEME_FLOW_CACHE_VERSION", None)
    except Exception:
        return None


def _has_current_schema(flow: dict | None) -> bool:
    version = _theme_flow_schema_version()
    return bool(flow and flow.get("themes") and version is not None
                and flow.get("schema_version") == version)


def build_command(mode: RunMode) -> list[str]:
    if mode not in MODE_LABELS:
        raise ValueError(f"unknown theme-flow background mode: {mode}")
    return [sys.executable, str(WORKER_SCRIPT), "--mode", mode]


def status_path_for(mode: RunMode) -> Path:
    return RUN_STATUS_DIR / f"theme-flow-{mode}.json"


def log_path_for(mode: RunMode) -> Path:
    return RUN_STATUS_DIR / f"theme-flow-{mode}.log"


def write_status(
    mode: RunMode,
    status: str,
    *,
    status_path: Path | None = None,
    pid: int | None = None,
    log_path: Path | None = None,
    error: str | None = None,
    result: dict | None = None,
) -> dict:
    data = {
        "mode": mode,
        "mode_label": MODE_LABELS.get(mode, mode),
        "status": status,
        "pid": pid or os.getpid(),
        "updated_at": _now_iso(),
        "log_path": str(log_path or log_path_for(mode)),
    }
    if status == "running":
        data["started_at"] = data["updated_at"]
    else:
        data["finished_at"] = data["updated_at"]
    if error:
        data["error"] = str(error)
    if result:
        data["result"] = result
    _write_json(status_path or status_path_for(mode), data)
    return data


def read_status(mode: RunMode = "refresh_board", *, status_path: Path | None = None) -> dict | None:
    return _read_json(status_path or status_path_for(mode))


def _pid_alive(pid) -> bool:
    try:
        pid_int = int(pid)
    except Exception:
        return False
    if pid_int <= 0:
        return False
    try:
        os.kill(pid_int, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def is_running(status: dict | None) -> bool:
    return bool(status and status.get("status") == "running" and _pid_alive(status.get("pid")))


def launch_background(
    mode: RunMode,
    *,
    cwd: Path = REPO,
    status_path: Path | None = None,
    log_path: Path | None = None,
    process_factory: Callable = subprocess.Popen,
) -> dict:
    status_path = status_path or status_path_for(mode)
    log_path = log_path or log_path_for(mode)
    current = read_status(mode, status_path=status_path)
    if is_running(current):
        return {**current, "already_running": True}

    command = build_command(mode)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log:
        proc = process_factory(
            command,
            cwd=str(cwd),
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    status = write_status(
        mode,
        "running",
        status_path=status_path,
        pid=proc.pid,
        log_path=log_path,
        result={"command": command},
    )
    return {**status, "command": command}


def _cached_theme_flow_reader() -> dict | None:
    try:
        try:
            from scripts import cache
            from scripts import theme_flow
        except ImportError:
            import cache  # type: ignore
            import theme_flow  # type: ignore
        params = {
            "v": theme_flow.THEME_FLOW_CACHE_VERSION,
            "baskets": theme_flow._baskets_fingerprint(),
        }
        return cache.read_cache("theme_flow", params, ttl=None)
    except Exception:
        return None


def read_snapshot(
    *,
    snapshot_path: Path = SNAPSHOT_PATH,
    cache_reader: Callable[[], dict | None] | None = None,
) -> dict | None:
    snapshot = _read_json(snapshot_path)
    if _has_current_schema(snapshot):
        return snapshot
    cached = (cache_reader or _cached_theme_flow_reader)()
    if _has_current_schema(cached):
        return cached
    return None


def _snapshot_archive_name(flow: dict) -> str | None:
    text = str(
        flow.get("as_of") or flow.get("as_of_date") or flow.get("generated_at") or ""
    )[:10]
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return f"{text}.json"
    return None


def write_snapshot(
    flow: dict,
    *,
    snapshot_path: Path = SNAPSHOT_PATH,
    archive_dir: Path | None = SNAPSHOT_ARCHIVE_DIR,
) -> None:
    _write_json(snapshot_path, flow)
    archive_name = _snapshot_archive_name(flow)
    if archive_dir is not None and archive_name:
        _write_json(archive_dir / archive_name, flow)


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def snapshot_age_seconds(flow: dict | None) -> float | None:
    dt = _parse_dt((flow or {}).get("generated_at"))
    if not dt:
        return None
    return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds())


def snapshot_is_stale(flow: dict | None, *, ttl_seconds: int = SNAPSHOT_TTL_SECONDS) -> bool:
    age = snapshot_age_seconds(flow)
    return age is None or age > ttl_seconds
