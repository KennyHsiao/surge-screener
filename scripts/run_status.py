#!/usr/bin/env python3
"""Small atomic writer for local pipeline run-status JSON files."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_STAGES = [
    ("preflight", "本機流程初始化"),
    ("hard_filter.fetch_ohlcv", "抓取 yfinance OHLCV"),
    ("hard_filter.info", "補 market cap / earnings"),
    ("hard_filter.apply_filters", "套用硬篩選"),
    ("rank_candidates", "程式排序候選"),
    ("options_gate", "檢查 options 可交易性"),
    ("llm_score.regime", "計算大盤 regime"),
    ("llm_score.candidates", "Claude 評分候選"),
    ("done", "完成"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_id_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class RunStatus:
    """Merge-preserving writer for one latest status file.

    The writer intentionally has no process-management behavior. It only records
    what the current CLI process knows, and Streamlit reads the JSON later.
    """

    def __init__(self, path: str | Path, *, job: str = "candidates-local") -> None:
        self.path = Path(path)
        self.job = job
        existing = self._read_existing()
        self.run_id = existing.get("run_id") or f"{job}-{utc_now()}"
        self.started_at = existing.get("started_at") or utc_now()

    def start(self, *, metrics: dict[str, Any] | None = None,
              outputs: dict[str, Any] | None = None) -> None:
        self.run_id = f"{self.job}-{run_id_now()}"
        self.started_at = utc_now()
        data = {
            "run_id": self.run_id,
            "job": self.job,
            "status": "running",
            "started_at": self.started_at,
            "updated_at": utc_now(),
            "pid": os.getpid(),
            "stage": {},
            "stages": [
                {"id": sid, "label": label, "status": "pending", "progress_pct": 0}
                for sid, label in DEFAULT_STAGES
            ],
            "metrics": {},
            "outputs": {},
            "warnings": [],
            "errors": [],
        }
        data["stage"] = {
            "id": "preflight",
            "label": "本機流程初始化",
            "status": "succeeded",
            "progress_pct": 100,
            "message": "local pipeline initialized",
        }
        data["stages"] = self._merge_stage(data.get("stages", []), data["stage"])
        if metrics:
            data["metrics"].update(metrics)
        if outputs:
            data["outputs"].update(outputs)
        self._write(data)

    def update_stage(self, stage_id: str, label: str, *, status: str = "running",
                     progress_pct: float = 0.0, message: str = "",
                     metrics: dict[str, Any] | None = None,
                     outputs: dict[str, Any] | None = None,
                     warnings: list[str] | None = None) -> None:
        data = self._base()
        data["status"] = "running"
        data["stage"] = {
            "id": stage_id,
            "label": label,
            "status": status,
            "progress_pct": round(max(0.0, min(100.0, float(progress_pct))), 1),
            "message": message,
        }
        data["stages"] = self._merge_stage(data.get("stages", []), data["stage"])
        if metrics:
            data["metrics"].update(metrics)
        if outputs:
            data["outputs"].update(outputs)
        if warnings:
            data["warnings"].extend(warnings)
        self._write(data)

    def succeed(self, *, message: str = "completed",
                metrics: dict[str, Any] | None = None,
                outputs: dict[str, Any] | None = None) -> None:
        data = self._base()
        now = utc_now()
        data["status"] = "succeeded"
        data["updated_at"] = now
        data["finished_at"] = now
        data["stage"] = {
            "id": "done",
            "label": "完成",
            "status": "succeeded",
            "progress_pct": 100,
            "message": message,
        }
        data["stages"] = self._merge_stage(data.get("stages", []), data["stage"])
        if metrics:
            data["metrics"].update(metrics)
        if outputs:
            data["outputs"].update(outputs)
        self._write(data)
        self._append_history(data)

    def fail(self, stage_id: str, label: str, message: str, *,
             metrics: dict[str, Any] | None = None) -> None:
        data = self._base()
        now = utc_now()
        data["status"] = "failed"
        data["updated_at"] = now
        data["finished_at"] = now
        data["stage"] = {
            "id": stage_id,
            "label": label,
            "status": "failed",
            "progress_pct": data.get("stage", {}).get("progress_pct", 0),
            "message": message,
        }
        data["stages"] = self._merge_stage(data.get("stages", []), data["stage"])
        if metrics:
            data["metrics"].update(metrics)
        data["errors"].append({"stage": stage_id, "message": message})
        self._write(data)
        self._append_history(data)

    def _base(self) -> dict[str, Any]:
        data = self._read_existing()
        now = utc_now()
        base = {
            "run_id": self.run_id,
            "job": self.job,
            "status": data.get("status", "running"),
            "started_at": self.started_at,
            "updated_at": now,
            "pid": os.getpid(),
            "stage": data.get("stage", {}),
            "stages": data.get("stages") or [
                {"id": sid, "label": label, "status": "pending", "progress_pct": 0}
                for sid, label in DEFAULT_STAGES
            ],
            "metrics": data.get("metrics") or {},
            "outputs": data.get("outputs") or {},
            "warnings": data.get("warnings") or [],
            "errors": data.get("errors") or [],
        }
        return base

    def _read_existing(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def _history_path(self) -> Path:
        return self.path.with_name(f"{self.path.stem}-history.jsonl")

    def _append_history(self, data: dict[str, Any]) -> None:
        record = {
            "run_id": data.get("run_id"),
            "job": data.get("job"),
            "status": data.get("status"),
            "started_at": data.get("started_at"),
            "finished_at": data.get("finished_at"),
            "stage": data.get("stage") or {},
            "metrics": data.get("metrics") or {},
            "outputs": data.get("outputs") or {},
            "warnings": data.get("warnings") or [],
            "errors": data.get("errors") or [],
        }
        history = self._history_path()
        history.parent.mkdir(parents=True, exist_ok=True)
        with history.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    @staticmethod
    def _merge_stage(stages: list[dict[str, Any]], stage: dict[str, Any]) -> list[dict[str, Any]]:
        out = []
        seen = False
        for item in stages:
            if item.get("id") == stage["id"]:
                merged = dict(item)
                merged.update(stage)
                out.append(merged)
                seen = True
            else:
                out.append(item)
        if not seen:
            out.append(stage)
        return out
