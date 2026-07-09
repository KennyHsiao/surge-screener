"""Renderer for strong continuation validation."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from . import _shared

REPORT = _shared.REPORTS_DIR / "retrospective" / "continuation_strength.json"


def render() -> None:
    st.subheader("續漲強者")
    st.caption("驗證突破或確認後是否還能續漲；原因只顯示為候選原因，不宣稱因果。")
    if not Path(REPORT).exists():
        st.info("尚未累積續漲驗證資料。平台會用 forward return 與最大回撤自動分類 strong / normal / failed / unresolved。")
        return

    data = json.loads(Path(REPORT).read_text(encoding="utf-8"))
    rows = data.get("rows") or []
    if not rows:
        st.info("續漲樣本仍在累積中。")
        return

    summary = data.get("summary") or {}
    c1, c2, c3 = st.columns(3)
    c1.metric("Strong", summary.get("strong_continuation", 0))
    c2.metric("Normal", summary.get("normal_continuation", 0))
    c3.metric("Failed", summary.get("failed_breakout", 0))

    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
