#!/usr/bin/env python3
"""Serialize playbook decisions into a minimal validation ledger."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent


def _ids(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for item in items:
        if isinstance(item, dict) and item.get("id"):
            out.append(str(item["id"]))
    return out


def _list_str(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return []


def decision_row(context: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    """Return a stable, privacy-minimal row for later forward validation."""
    row = {
        "ticker": str(context.get("ticker") or "").upper(),
        "cockpit_verdict": context.get("cockpit_verdict"),
        "primary_playbook": decision.get("primary_playbook"),
        "actionability": decision.get("actionability"),
        "structure": decision.get("structure"),
        "cycle": context.get("cycle"),
        "cycle_source": context.get("cycle_source"),
        "dte": context.get("dte"),
        "iv_rank": context.get("iv_rank"),
        "warning_ids": _ids(decision.get("warnings")),
        "block_ids": _ids(decision.get("blocks")),
        "course_sources": _list_str(decision.get("course_sources")),
    }
    if context.get("as_of_date"):
        row["as_of_date"] = context.get("as_of_date")
    if decision.get("factor_ids"):
        row["factor_ids"] = _list_str(decision.get("factor_ids"))
    return row


def write_snapshot(
    rows: list[dict[str, Any]],
    out_dir: str | Path = "reports/playbook_decisions",
    *,
    generated_at: str | None = None,
) -> Path:
    """Write one ledger snapshot and return its path."""
    out_path = Path(out_dir)
    if not out_path.is_absolute():
        out_path = REPO / out_path
    out_path.mkdir(parents=True, exist_ok=True)

    stamp = generated_at or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = out_path / f"{stamp}.json"
    payload = {
        "generated_at": stamp,
        "row_count": len(rows),
        "rows": rows,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
