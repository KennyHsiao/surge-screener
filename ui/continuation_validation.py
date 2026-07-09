"""Renderer for strong continuation validation."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from . import _shared

REPORT = _shared.REPORTS_DIR / "retrospective" / "continuation_strength.json"

_STATUS_LABEL = {
    "ready": "已驗證",
    "accumulating": "累積中",
    "blocked": "封鎖",
}


def _status_message(data: dict) -> tuple[str, str]:
    status = str(data.get("status") or "accumulating")
    label = _STATUS_LABEL.get(status, "探索性")
    resolved = data.get("resolved", 0)
    min_resolved = data.get("min_resolved", 30)
    if status == "blocked":
        return label, str(data.get("reason") or "續漲驗證來源尚不可用。")
    if status == "ready":
        return label, f"已解析 {resolved}/{min_resolved} 筆，可作為續漲分類參考。"
    return label, f"已解析 {resolved}/{min_resolved} 筆；樣本尚未成熟，只能顯示探索性結果。"


def render() -> None:
    st.subheader("續漲強者")
    st.caption("驗證突破或確認後是否還能續漲；原因只顯示為候選原因，不宣稱因果。")
    if not Path(REPORT).exists():
        st.info("尚未累積續漲驗證資料。平台會用 forward return 與最大回撤自動分類 strong / normal / failed / unresolved。")
        return

    data = json.loads(Path(REPORT).read_text(encoding="utf-8"))
    status = str(data.get("status") or "accumulating")
    label, message = _status_message(data)
    if status == "blocked":
        st.error(f"續漲驗證暫時封鎖：{message}")
    elif status == "ready":
        st.success(f"{label}：{message}")
    else:
        st.warning(f"{label}：{message}")
    if data.get("generated_at"):
        st.caption(f"最近更新：{data.get('generated_at')}")

    m1, m2, m3 = st.columns(3)
    m1.metric("Resolved", data.get("resolved", 0))
    m2.metric("Min resolved", data.get("min_resolved", 30))
    m3.metric("Rows", (data.get("summary") or {}).get("rows_total", len(data.get("rows") or [])))

    rows = data.get("rows") or []
    if not rows:
        if status != "blocked":
            st.info("續漲樣本仍在累積中。")
        return

    summary = data.get("summary") or {}
    c1, c2, c3 = st.columns(3)
    c1.metric("Strong", summary.get("strong_continuation", 0))
    c2.metric("Normal", summary.get("normal_continuation", 0))
    c3.metric("Failed", summary.get("failed_breakout", 0))

    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
