"""API-only renderer for strong-continuation validation."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from api.models import ContinuationValidationData

from . import _read_api


_STATUS_LABEL = {
    "ready": "已驗證",
    "accumulating": "累積中",
    "blocked": "封鎖",
}


def _status_message(data: ContinuationValidationData) -> tuple[str, str]:
    label = _STATUS_LABEL[data.status]
    if data.status == "blocked":
        return label, "續漲驗證來源尚不可用。"
    if data.status == "ready":
        return (
            label,
            f"已解析 {data.resolved}/{data.min_resolved} 筆，可作為續漲分類參考。",
        )
    return (
        label,
        f"已解析 {data.resolved}/{data.min_resolved} 筆；樣本尚未成熟，只能顯示探索性結果。",
    )


def render() -> None:
    st.subheader("續漲強者")
    st.caption("驗證突破或確認後是否還能續漲；原因只顯示為候選原因，不宣稱因果。")

    result = _read_api.load_continuation_validation()
    if isinstance(result, _read_api.ContinuationValidationApiUnavailable):
        st.info("續漲驗證資料目前無法使用；可稍後重試或查看 Data Health。")
        return
    if not isinstance(result, _read_api.ContinuationValidationApiAvailable):
        st.info("續漲驗證服務目前無法使用；可稍後重試或查看 Data Health。")
        return
    data = result.report

    label, message = _status_message(data)
    if data.status == "blocked":
        st.error(f"續漲驗證暫時封鎖：{message}")
    elif data.status == "ready":
        st.success(f"{label}：{message}")
    else:
        st.warning(f"{label}：{message}")
    st.caption(f"最近更新：{data.generated_at}")

    m1, m2, m3 = st.columns(3)
    m1.metric("Resolved", data.resolved)
    m2.metric("Min resolved", data.min_resolved)
    m3.metric("Rows", data.summary.rows_total)

    if not data.rows:
        if data.status != "blocked":
            st.info("續漲樣本仍在累積中。")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Strong", data.summary.strong_continuation)
    c2.metric("Normal", data.summary.normal_continuation)
    c3.metric("Failed", data.summary.failed_breakout)
    st.caption(
        "Strong "
        f"{data.summary.strong_continuation} · Normal "
        f"{data.summary.normal_continuation} · Failed "
        f"{data.summary.failed_breakout}"
    )
    st.dataframe(
        pd.DataFrame([row.model_dump(mode="json") for row in data.rows]),
        hide_index=True,
        width="stretch",
    )
