"""Shared helpers for UI run-status reconciliation."""

from __future__ import annotations

import copy
import os
from datetime import datetime, timezone
from typing import Callable


def parse_utc(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def utc_iso(value: datetime | None = None) -> str:
    dt = value or datetime.now(timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def pid_is_running(pid: object) -> bool | None:
    try:
        value = int(pid)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return False
    try:
        os.kill(value, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def merge_stage(stages: list, stage: dict) -> list:
    out = []
    seen = False
    stage_id = stage.get("id")
    for item in stages:
        if not isinstance(item, dict):
            continue
        if item.get("id") == stage_id:
            merged = dict(item)
            merged.update(stage)
            out.append(merged)
            seen = True
        else:
            out.append(item)
    if not seen:
        out.append(stage)
    return out


def running_interrupt_reason(
    data: dict | None,
    *,
    stale_after_seconds: int,
    stale_message: str,
    pid_gone_message: str,
    now: datetime | None = None,
    process_checker: Callable[[object], bool | None] = pid_is_running,
) -> str | None:
    if not isinstance(data, dict) or data.get("status") != "running":
        return None
    pid_state = process_checker(data.get("pid"))
    if pid_state is False:
        return pid_gone_message
    updated = parse_utc(data.get("updated_at"))
    if updated is None:
        return None
    age = ((now or datetime.now(timezone.utc)) - updated).total_seconds()
    if age > stale_after_seconds:
        return stale_message
    return None


def running_status_is_active(
    data: dict | None,
    *,
    stale_after_seconds: int,
    stale_message: str,
    pid_gone_message: str,
    now: datetime | None = None,
    process_checker: Callable[[object], bool | None] = pid_is_running,
) -> bool:
    if not isinstance(data, dict) or data.get("status") != "running":
        return False
    if running_interrupt_reason(
        data,
        stale_after_seconds=stale_after_seconds,
        stale_message=stale_message,
        pid_gone_message=pid_gone_message,
        now=now,
        process_checker=process_checker,
    ):
        return False
    updated = parse_utc(data.get("updated_at"))
    if updated is None:
        return True
    age = ((now or datetime.now(timezone.utc)) - updated).total_seconds()
    return age <= stale_after_seconds


def interrupted_status(
    data: dict,
    reason: str,
    *,
    default_label: str,
    now: datetime | None = None,
) -> dict:
    fixed = copy.deepcopy(data)
    current = fixed.get("stage") if isinstance(fixed.get("stage"), dict) else {}
    stage_id = str(current.get("id") or "interrupted")
    stage = dict(current)
    stage.update({
        "id": stage_id,
        "label": stage.get("label") or default_label,
        "status": "failed",
        "progress_pct": stage.get("progress_pct", 0),
        "message": reason,
    })
    finished_at = utc_iso(now)
    fixed["status"] = "failed"
    fixed["updated_at"] = finished_at
    fixed["finished_at"] = finished_at
    fixed["stage"] = stage
    fixed["stages"] = merge_stage(
        fixed.get("stages") if isinstance(fixed.get("stages"), list) else [],
        stage,
    )
    errors = fixed.get("errors") if isinstance(fixed.get("errors"), list) else []
    fixed["errors"] = [
        *errors,
        {"stage": stage_id, "message": reason, "at": finished_at},
    ]
    return fixed
