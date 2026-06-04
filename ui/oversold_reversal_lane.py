"""美股 · 超賣反轉 ⚡ (測試) — oversold-reversal blind-spot lane.

EXPLORATORY lane built directly from the surge retrospective's one VALIDATED archetype:
the 超賣反轉 module scored lift 4.17 (validated across all thresholds) while the screener's
own momentum-continuation template (Minervini) is CONTRARIAN at 0.47 — and the live hard
filter REJECTS below-200DMA names without a reversal pattern. So this lane surfaces the
setups the screener structurally throws away: oversold (below 200DMA, far off the 52-week
high) names with a recent volume ignition (rvol≥2).

Display-only. These are NOT scored picks and NOT recommendations — the retro is
survivorship-blocked, so the lane is forward-validated over time (反轉驗證 tab in 復盤分析),
never auto-applied. Data comes from scripts/oversold_reversal_scan.py.
"""

import pandas as pd
import streamlit as st

from . import _shared

OVERSOLD_DIR = _shared.REPORTS_DIR / "oversold_reversal"


def _load_latest() -> dict | None:
    return _shared.load_json(str(OVERSOLD_DIR / "latest.json"))


def render() -> None:
    st.title("放量點火 ⚡ (測試)")
    st.caption("放量(rvol≥2)+ 超賣位置的盲區掃描 — **非篩選器評分、非投資建議**。"
               "真正經驗證的訊號是**放量**;超賣位置大部分是 %-漲幅假象,僅作 context。")

    data = _load_latest()
    if not data:
        st.info(
            "尚無掃描結果。先跑一次掃描:\n\n"
            "```\npython scripts/oversold_reversal_scan.py --universe sp1500\n```\n\n"
            "會寫入 `reports/oversold_reversal/latest.json`,本頁即顯示。")
        return

    # Honest framing — the runway confound up front, then what's actually real.
    st.error(
        "**⚠ 重要修正**:復盤原本顯示「超賣反轉」組合 lift **4.17**,但 runway 對照檢定"
        "(`retro_confound_check.py`)證實這 **大部分是 %-漲幅量測假象** —— 跌深的便宜股要漲到固定的"
        "「+30/40/50%」本來就比較容易,並非真有反轉優勢。在「距高點相近」的同組內比較時,這個優勢會"
        "消失甚至反轉。**唯一跨組都站得住的真訊號是『放量』(rvol≥2)**。", icon="⚠️")
    st.info(
        "所以本頁定位為**放量點火**掃描:以放量為核心訊號,超賣/位置欄位僅作 context(非已驗證優勢)。"
        "仍掃描篩選器因 200 日線硬濾網丟掉的盲區;EXPLORATORY,僅供**前向驗證**,不自動套用。", icon="⚡")

    c1, c2, c3, c4 = st.columns(4)
    _shared.metric_card(c1, "符合標的", f"{data.get('match_count', 0)}",
                        help="目前同時滿足:跌破200日線 + 距高>25% + 近期放量≥2×")
    _shared.metric_card(c2, "已掃描", f"{data.get('scanned', 0)}",
                        help=f"宇宙 {data.get('universe', '?')}(全量,未經硬濾網)")
    _shared.metric_card(c3, "資料日期", data.get("as_of_date", "—"))
    _shared.metric_card(c4, "模組 lift ⚠", f"{data.get('module_lift_runway_inflated', '—')}×",
                        help="原 4.17×,但 runway 檢定證實大部分為 %-漲幅假象,非真實優勢")

    st.caption(f"定義:{data.get('definition', '')}")

    cands = data.get("candidates", [])
    if not cands:
        st.success("目前宇宙內沒有符合超賣反轉條件的標的(放量點火是逐日稀疏的,屬正常)。")
    else:
        df = pd.DataFrame(cands)
        cols = ["ticker", "last_price", "pct_below_ma200", "pct_from_52w_high",
                "ignition_rvol", "ignition_date", "avg_dollar_vol_m", "ma200"]
        df = df[[c for c in cols if c in df.columns]]
        df = df.rename(columns={
            "ticker": "代號", "last_price": "現價", "pct_below_ma200": "距200線%",
            "pct_from_52w_high": "距52週高%", "ignition_rvol": "點火rvol",
            "ignition_date": "點火日", "avg_dollar_vol_m": "日均額(M)", "ma200": "200日線",
        })
        st.dataframe(df, hide_index=True, use_container_width=True,
                     column_config={"點火rvol": st.column_config.NumberColumn(format="%.2f×")})
        st.caption("依「點火 rvol」(真訊號)排序。距200線% / 距52週高% 僅作 context —— "
                   "這些位置欄位受 %-漲幅假象影響,非已驗證優勢。")

    st.divider()
    _render_forward_validation()
    st.caption("⚠️ " + (data.get("note", "")))


def _render_forward_validation() -> None:
    """Forward realized hit-rate accumulator (oversold_reversal_forward.py)."""
    st.subheader("反轉驗證 — 前向命中率")
    val = _shared.load_json(str(OVERSOLD_DIR / "validation_summary.json"))
    if not val:
        st.caption(
            "尚未累積前向資料。每日跑 `oversold_reversal_scan.py` 後,"
            "`oversold_reversal_forward.py` 會追蹤每筆訊號的後續報酬,在此顯示各門檻命中率。")
        return
    prov = "PROVISIONAL" in (val.get("verdict") or "")
    (st.warning if prov else st.success)(
        f"{val.get('verdict')} — 累積 {val.get('entries_accumulated', 0)} 筆,"
        f"已結算 {val.get('total_resolved', 0)} 筆(門檻 {val.get('min_resolved_for_verdict')} 筆)。"
        "命中率非 lift,且**不可**與復盤 4.17×(本身為漲幅假象)直接比較。")
    rows = []
    for label, t in (val.get("by_tier") or {}).items():
        ci = t.get("wilson90") or [None, None]
        rows.append({"門檻": label, "已結算": t.get("resolved"), "命中": t.get("hits"),
                     "命中率": t.get("hit_rate"),
                     "90% CI": f"[{ci[0]}, {ci[1]}]" if ci[0] is not None else "—"})
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("命中率為前向實現值,尚非 lift(需 live 非訊號 baseline,屬後續工作)。")
