"""Renderer for automated course Playbook validation."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from api.models import PlaybookValidationData

from . import _read_api

_STATUS_LABEL = {
    "ready": "已驗證",
    "accumulating": "累積中",
    "blocked": "封鎖",
}


def _status_message(data: PlaybookValidationData) -> tuple[str, str]:
    status = data.status
    label = _STATUS_LABEL.get(status, "探索性")
    resolved = data.resolved
    min_resolved = data.min_resolved
    if status == "blocked":
        return label, "Playbook 驗證來源尚不可用。"
    if status == "ready":
        return label, f"已解析 {resolved}/{min_resolved} 筆，可作為驗證支持參考。"
    return label, f"已解析 {resolved}/{min_resolved} 筆；樣本尚未成熟，只能顯示探索性結果。"


def _table(rows: list[dict[str, object]], rename: dict[str, str]) -> None:
    if not rows:
        st.info("尚無可顯示樣本。")
        return
    df = pd.DataFrame(rows).rename(columns=rename)
    st.dataframe(df, hide_index=True, width="stretch")


def render() -> None:
    st.subheader("Playbook 驗證")
    st.caption("自動讀取 Playbook decision ledger，追蹤後續 forward return。未成熟前不回寫決策權重。")

    result = _read_api.load_playbook_validation()
    if isinstance(result, _read_api.PlaybookValidationApiUnavailable):
        st.info("Playbook 驗證資料目前無法使用；可稍後重試或查看 Data Health。")
        return
    if not isinstance(result, _read_api.PlaybookValidationApiAvailable):
        st.info("Playbook 驗證服務目前無法使用；可稍後重試或查看 Data Health。")
        return
    data = result.summary

    label, message = _status_message(data)
    if data.status == "blocked":
        st.error(f"{label}：{message}")
    elif data.status == "ready":
        st.success(f"{label}：{message}")
    else:
        st.warning(f"{label}：{message}")
    st.caption(f"最近更新：{data.generated_at}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Decision rows", data.decision_count)
    c2.metric("Resolved", data.resolved)
    c3.metric("Min resolved", data.min_resolved)

    st.markdown("**Playbook 層級**")
    _table(
        [row.model_dump(mode="json") for row in data.playbooks],
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
        [row.model_dump(mode="json") for row in data.factors],
        {
            "factor_id": "Factor ID",
            "resolved": "已解析",
            "mean_fwd_7d_return": "7D 平均報酬",
            "hit_rate_7d": "7D 勝率",
            "verdict": "狀態",
        },
    )
