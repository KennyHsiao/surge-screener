"""美股 · 壓縮基底 ⚡ (測試) — coiled-base blind-spot lane.

EXPLORATORY lane. The surge retrospective's 超賣反轉 archetype scored lift 4.17, but the
runway-NEUTRAL re-validation (ATR-normalized target) showed that — and the volume-ignition
rule it became — are %-RUNWAY ARTIFACTS: under a volatility-neutral target the old
'!200DMA & !25%high & rvol' rule collapses (6.31 → 0.84). The ONLY signal that holds across
BOTH the %-target and the ATR-neutral target, with real support, is the pair bb_squeeze &
rsi_40_65 (2.47 → 2.39, support 51). So this lane now surfaces QUIET COILED BASES (Bollinger
squeeze) with healthy momentum (RSI 40–65) — and still scans the full universe the screener's
200DMA hard filter throws away.

Display-only — NOT scored picks, NOT recommendations; forward-validated over time (反轉驗證
tab), never auto-applied. Data: scripts/oversold_reversal_scan.py (legacy filename; coiled-base lane).
"""

import pandas as pd
import streamlit as st

from . import _shared

OVERSOLD_DIR = _shared.REPORTS_DIR / "oversold_reversal"


def _load_latest() -> dict | None:
    return _shared.load_json(str(OVERSOLD_DIR / "latest.json"))


def render() -> None:
    st.title("壓縮基底 ⚡ (測試)")
    st.caption("布林壓縮 + 健康 RSI(40–65)+ 不在低點(距52週低≥30%)的盲區掃描 — "
               "**非篩選器評分、非投資建議**。%-目標與 ATR-中性 lift 完全相同(3.19),零漲幅假象。")

    data = _load_latest()
    if not data:
        st.info(
            "尚無掃描結果。先跑一次掃描:\n\n"
            "```\npython scripts/oversold_reversal_scan.py --universe sp1500\n```\n\n"
            "會寫入 `reports/oversold_reversal/latest.json`,本頁即顯示。")
        return

    v = data.get("validation", {}) or {}
    # Honest framing — why this lane gates on the coiled-base pair, not rvol/oversold.
    st.error(
        "**⚠ runway 修正(已settled)**:復盤的「超賣反轉」lift 4.17、以及它演化成的「放量+超跌」規則,"
        "在 **ATR-中性目標**(波動正規化)下**垮掉**(`!200DMA & !25%high & rvol`:%-lift 6.31 → "
        "ATR 0.84,無 edge;單獨放量 1.36 → 0.67)。便宜/跌深股容易達固定 +X%,是漲幅量測假象。",
        icon="⚠️")
    caveats = data.get("validation_caveats") or []
    msg = (f"`bb_squeeze & rsi_40_65 & above_30pct_of_low`(壓縮基底 + 健康動能 + 不在低點)—— "
           f"%-lift {v.get('pct_lift','—')} ≈ **ATR-中性 {v.get('atr_neutral_lift','—')}**(零漲幅膨脹),"
           f"support {v.get('support','—')}(數字讀自 `lane_runway.json`,可由 `lane_runway_check.py` 重現)。")
    if data.get("runway_independent"):
        st.success("✅ **可行動**:" + msg + "安靜蓄勢、不是已放量或盤在谷底的股票。", icon="⚡")
    else:
        st.warning("🔬 **僅探索性 — 以前向命中率為準,勿直接下注**:" + msg
                   + "\n\n原因:" + "; ".join(caveats), icon="🔬")

    c1, c2, c3, c4 = st.columns(4)
    _shared.metric_card(c1, "符合標的", f"{data.get('match_count', 0)}",
                        help="同時滿足:布林壓縮(bb_squeeze)+ RSI 40–65 + 距52週低≥30%")
    _shared.metric_card(c2, "已掃描", f"{data.get('scanned', 0)}",
                        help=f"宇宙 {data.get('universe', '?')}(全量,未經硬濾網)")
    _shared.metric_card(c3, "資料日期", data.get("as_of_date", "—"))
    _shared.metric_card(c4, "ATR-中性 lift", f"{v.get('atr_neutral_lift', '—')}×",
                        help="驗證樣本上波動正規化後仍 >1(舊放量 lane 在此垮成 0.84);"
                             "來源樣本若 blocked/stale 則僅探索性")

    st.caption(f"定義:{data.get('definition', '')}")

    cands = data.get("candidates", [])
    if not cands:
        st.success("目前宇宙內沒有符合壓縮基底條件的標的(逐日稀疏,屬正常)。")
    else:
        df = pd.DataFrame(cands)
        cols = ["ticker", "last_price", "rsi14", "bb_width_pct", "pct_vs_ma200",
                "pct_from_52w_high", "avg_dollar_vol_m"]
        df = df[[c for c in cols if c in df.columns]]
        df = df.rename(columns={
            "ticker": "代號", "last_price": "現價", "rsi14": "RSI", "bb_width_pct": "布林寬度%",
            "pct_vs_ma200": "距200線%", "pct_from_52w_high": "距52週高%",
            "avg_dollar_vol_m": "日均額(M)",
        })
        st.dataframe(df, hide_index=True, use_container_width=True,
                     column_config={
                         "RSI": st.column_config.NumberColumn(format="%.0f"),
                         "布林寬度%": st.column_config.NumberColumn(format="%.1f%%",
                             help="布林帶寬 / 中軌 —— 越小=壓縮越緊(基底越成熟)"),
                     })
        st.caption("依「布林寬度」排序(越緊越前)。距200線% / 距52週高% 僅作 context,非 gate。")

    st.divider()
    _render_forward_validation()
    st.caption("⚠️ " + (data.get("note", "")))


def _render_forward_validation() -> None:
    """Forward realized hit-rate accumulator (oversold_reversal_forward.py)."""
    st.subheader("壓縮基底驗證 — 前向命中率")
    val = _shared.load_json(str(OVERSOLD_DIR / "validation_summary.json"))
    if not val:
        st.caption(
            "尚未累積前向資料。每日跑 `oversold_reversal_scan.py` 後,"
            "`oversold_reversal_forward.py` 會追蹤每筆訊號的後續報酬,在此顯示各門檻命中率。")
        return
    prov = "PROVISIONAL" in (val.get("verdict") or "")
    # The forward harness now reports min_resolved_across_tiers (the conservative verdict basis)
    # + price_resolvable; the old total_resolved was removed — read the new field, with a
    # back-compat fallback, so the headline doesn't show 0 settled on a real run (Codex review).
    _resolved = val.get("min_resolved_across_tiers", val.get("total_resolved", 0))
    (st.warning if prov else st.success)(
        f"{val.get('verdict')} — 累積 {val.get('entries_accumulated', 0)} 筆,"
        f"已結算 {_resolved} 筆(門檻 {val.get('min_resolved_for_verdict')} 筆)。"
        "命中率為前向實現值,非 lift。")
    rows = []
    for label, t in (val.get("by_tier") or {}).items():
        ci = t.get("wilson90") or [None, None]
        rows.append({"門檻": label, "已結算": t.get("resolved"), "命中": t.get("hits"),
                     "命中率": t.get("hit_rate"),
                     "90% CI": f"[{ci[0]}, {ci[1]}]" if ci[0] is not None else "—"})
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("⚠ 改寫前累積的是舊『放量+超跌』lane 的資料;清掉 "
               "`reports/oversold_reversal/scan_*.json` 可重新累積乾淨的壓縮基底基線。")
