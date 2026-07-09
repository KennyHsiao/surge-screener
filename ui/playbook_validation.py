"""Renderer for automated course Playbook validation."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from . import _shared

REPORT = _shared.REPORTS_DIR / "playbook_validation" / "latest.json"

_STATUS_LABEL = {
    "ready": "已驗證",
    "accumulating": "累積中",
    "blocked": "封鎖",
}


def _status_message(data: dict) -> tuple[str, str]:
    status = str(data.get("status") or "accumulating")
    label = _STATUS_LABEL.get(status, "探索性")
    resolved = data.get("resolved", 0)
    min_resolved = data.get("min_resolved", 100)
    if status == "blocked":
        return label, str(data.get("reason") or "Playbook 驗證來源尚不可用。")
    if status == "ready":
        return label, f"已解析 {resolved}/{min_resolved} 筆，可作為驗證支持參考。"
    return label, f"已解析 {resolved}/{min_resolved} 筆；樣本尚未成熟，只能顯示探索性結果。"


def _table(rows: list[dict], rename: dict[str, str]) -> None:
    if not rows:
        st.info("尚無可顯示樣本。")
        return
    df = pd.DataFrame(rows).rename(columns=rename)
    st.dataframe(df, hide_index=True, width="stretch")


def render() -> None:
    st.subheader("Playbook 驗證")
    st.caption("自動讀取 Playbook decision ledger，追蹤後續 forward return。未成熟前不回寫決策權重。")

    data = _shared.load_json(str(REPORT)) or {}
    if not data:
        st.info("尚未產生 Playbook 驗證資料。Data Health refresh 會寫入 reports/playbook_validation/latest.json。")
        return

    label, message = _status_message(data)
    if data.get("status") == "blocked":
        st.error(f"{label}：{message}")
    elif data.get("status") == "ready":
        st.success(f"{label}：{message}")
    else:
        st.warning(f"{label}：{message}")
    if data.get("generated_at"):
        st.caption(f"最近更新：{data.get('generated_at')}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Decision rows", data.get("decision_count", 0))
    c2.metric("Resolved", data.get("resolved", 0))
    c3.metric("Min resolved", data.get("min_resolved", 100))

    st.markdown("**Playbook 層級**")
    _table(
        data.get("playbooks") or [],
        {
            "playbook": "Playbook",
            "resolved": "已解析",
            "mean_fwd_7d_return": "7D 平均報酬",
            "hit_rate_7d": "7D 勝率",
            "verdict": "狀態",
        },
    )

    st.markdown("**因子層級**")
    _table(
        data.get("factors") or [],
        {
            "factor_id": "Factor ID",
            "resolved": "已解析",
            "mean_fwd_7d_return": "7D 平均報酬",
            "hit_rate_7d": "7D 勝率",
            "verdict": "狀態",
        },
    )
