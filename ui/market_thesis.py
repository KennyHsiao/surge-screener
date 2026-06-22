"""美股 · 大盤行情研判 (Market Thesis) — Tier-1 體制/事件研判 + 前向驗證.

Renders the market_thesis pipeline output that previously had NO UI page (the
one dangling artifact): the latest weekly forecast (direction / bucket /
support_class / regime / 類比歷史 / 巨觀事件 manifest) and the forward-validation
scoreboard (已鎖定預測的回顧命中率, PROVISIONAL until matured).

Read-only + fail-soft by design: every field is `.get`-guarded so the page never
crashes if the backend schema shifts (the pipeline is under active development).
Verified-data-to-AI: scripts/market_thesis*.py compute deterministically; this
page only displays. Honesty: 探索性、未驗證、非投資建議 — see the banner.
"""

import streamlit as st

from . import _shared

_DIR = _shared.REPORTS_DIR / "market_thesis"

_DIR_EMOJI = {"看多": "🟢", "看空": "🔴", "盤整": "🟡"}
_BUCKET_ZH = {"short": "短(20 會話)", "mid": "中(40 會話)", "long": "長(60 會話)"}
_SUPPORT_ZH = {
    "analog_supported": "類比支撐", "event_only": "僅事件", "regime_only": "僅體制",
}
_STATUS_ZH = {"ready": "✅ ready(可警報)", "degraded": "🟡 degraded(非事件驅動)"}


def _latest_forecast() -> dict | None:
    """Most recent forecast — ready (`forecast_*.json`) or degraded
    (`regime_only_forecast_*.json`), whichever is newest by the date in the name."""
    if not _DIR.exists():
        return None
    files = [p for p in _DIR.glob("*forecast_*.json")]
    if not files:
        return None
    # filenames end _YYYY-MM-DD.json → lexical sort on the stem is date order.
    latest = sorted(files, key=lambda p: p.stem, reverse=True)[0]
    return _shared.load_json(str(latest))


def _pct(v, nd: int = 2) -> str:
    """Fraction → signed percent string; '—' for None/non-numeric."""
    return f"{v * 100:+.{nd}f}%" if isinstance(v, (int, float)) else "—"


def _render_banner(fc: dict | None) -> None:
    degraded = (fc or {}).get("manifest_status") == "degraded"
    # Headline = the one fact that matters (scannable); detail goes to a caption.
    head = "⚠️ **探索性研判,非投資建議。**"
    if degraded:
        head += " 目前 **degraded — 不發任何警報**(預測僅鎖定累積、供日後驗證)。"
    st.warning(head)
    st.caption(
        "Tier-1 由程式碼決定論產生(非 LLM 研究);Tier-2 agentic 層尚未啟用。"
        + ("　degraded 原因:CPI/JOBS 事件源未接 FRED key。" if degraded else "")
        + "　下方「前向驗證」為已鎖定預測的**回顧命中率**(已發生、非未來預測精度),"
        "未達門檻前標 PROVISIONAL。"
    )


def _render_forecast(fc: dict | None) -> None:
    st.subheader("本期研判")
    if not fc:
        st.info("尚無大盤研判。管線每週一(23:00 UTC)產出,寫入 "
                "`reports/market_thesis/`,本頁即顯示。")
        return

    direction = fc.get("direction", "?")
    bucket = fc.get("bucket", "?")
    # 方向 is the signal — lead with it (largest), demote the date to a caption.
    st.caption(f"研判日期 {fc.get('as_of', '—')}")
    c = st.columns(4)
    _shared.metric_card(c[0], "方向研判", f"{_DIR_EMOJI.get(direction, '')} {direction}".strip(),
                        help="看多 / 看空 / 盤整(θ=±3% 方向門檻)")
    _shared.metric_card(c[1], "期程", _BUCKET_ZH.get(bucket, bucket))
    _shared.metric_card(c[2], "體制", fc.get("regime", "—"),
                        help="rally / correction / range(20年規則判定)")
    _shared.metric_card(c[3], "VIX 區間", fc.get("vix_bucket", "—"),
                        help="low / normal / elevated / panic 分位區間")

    _shared.chips_row([
        (_SUPPORT_ZH.get(fc.get("support_class"), fc.get("support_class", "?")), _shared.PURPLE),
        (_STATUS_ZH.get(fc.get("manifest_status"), fc.get("manifest_status", "?")),
         _shared.AMBER if fc.get("manifest_status") == "degraded" else _shared.GREEN),
    ])

    rat = fc.get("rationale") or {}
    analog = rat.get("analog") or {}
    if analog:
        st.markdown("**類比歷史**(同體制/VIX 區間的歷史前向報酬,非信號)")
        a = st.columns(4)
        _shared.metric_card(a[0], "平均前向報酬", _pct(analog.get("mean")),
                            help=f"CI90 [{_pct(analog.get('ci90', [None, None])[0])}, "
                                 f"{_pct(analog.get('ci90', [None, None])[1])}] · "
                                 f"n={analog.get('resolved', '?')}")
        _shared.metric_card(a[1], "上漲率", _pct(analog.get("up_rate"), 1))
        _shared.metric_card(a[2], "P10(下尾)", _pct(analog.get("p10")))
        _shared.metric_card(a[3], "最差回撤", _pct(analog.get("worst_mdd")))

    missing = rat.get("manifest_missing") or []
    stale = rat.get("manifest_stale") or []
    if missing or stale:
        st.caption(f"⚠ 缺事件:{', '.join(missing) or '—'}　舊事件:{', '.join(stale) or '—'}"
                   "　→ 故 degraded、不發警報。")

    events = rat.get("manifest_events") or []
    if events:
        with st.expander("📅 巨觀事件 manifest(資料源 + 新鮮度)", expanded=False):
            import pandas as pd
            rows = []
            for e in events:
                if not isinstance(e, dict):
                    continue
                detail = (e.get("stale_reason")
                          or (f"{e.get('value')}" + (f" (Δ{e.get('delta_1d')})"
                                                     if e.get("delta_1d") is not None else ""))
                          if e.get("value") is not None
                          else (f"{e.get('last_rate')} · 下次 {e.get('next_meeting_at')}"
                                if e.get("last_rate") else "—"))
                rows.append({
                    "事件": e.get("type", "?"),
                    "有資料": "✅" if e.get("present") else "❌",
                    "新鮮": "✅" if e.get("fresh") else "❌",
                    "來源": e.get("source_id", "—"),
                    "明細": detail,
                })
            if rows:
                st.dataframe(
                    pd.DataFrame(rows), hide_index=True, use_container_width=True,
                    column_config={
                        "事件": st.column_config.TextColumn(width="small"),
                        "有資料": st.column_config.TextColumn(width="small"),
                        "新鮮": st.column_config.TextColumn(width="small"),
                    })
    st.caption(f"標記:{fc.get('label', '探索性,未驗證,非投資建議')} · "
               f"產生於 {fc.get('generated_at', '—')}")


def _render_validation(summ: dict | None) -> None:
    st.subheader("前向驗證(已鎖定預測的回顧命中率,非未來精度)")
    if not summ:
        st.info("尚無驗證摘要。`market_thesis_forward.py` 會在預測鎖定後累積。")
        return

    status = summ.get("validation_status", "?")
    resolved = summ.get("resolved", 0)
    matured = summ.get("matured", 0)
    thr = summ.get("min_resolved_for_verdict", 100)
    c = st.columns(4)
    _shared.metric_card(c[0], "驗證狀態", status)
    _shared.metric_card(c[1], "已解決", str(resolved), help="已可比對結果的鎖定預測數")
    _shared.metric_card(c[2], "已成熟", str(matured))
    _shared.metric_card(c[3], "正式門檻", f"{thr} 筆",
                        help="非重疊成熟筆數達此值前,所有命中率標 PROVISIONAL")

    if status != "ok":
        st.error(f"⚠ 驗證不可發布:{status}(拒絕 {summ.get('reject_count', 0)} 筆 / "
                 f"無效 {summ.get('invalid_count', 0)} 筆)。")

    by_key = summ.get("by_key") or {}
    if not by_key:
        st.info(f"尚無非重疊成熟預測(已解決 {resolved} / 需 {thr})。系統累積中——"
                "命中率不對 support_class 跨類彙總(各類獨立分母)。")
        return

    import pandas as pd
    rows = []
    for key, m in sorted(by_key.items()):
        parts = key.split("|")
        d, b, sc = (parts + ["?", "?", "?"])[:3]
        ci = m.get("wilson90") or [None, None]
        rows.append({
            "方向": d, "期程": b, "支撐": _SUPPORT_ZH.get(sc, sc),
            "命中/總數": f"{m.get('hits', 0)}/{m.get('counted_N', 0)}",
            "命中率": _pct(m.get("hit_rate"), 1),
            "CI90": f"[{_pct(ci[0], 1)}, {_pct(ci[1], 1)}]" if ci[0] is not None else "—",
            "狀態": m.get("verdict", "?"),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("命中率為已鎖定預測的回顧實現值(非未來預測能力);依完整 "
               "(方向│期程│支撐) 鍵分列,各類不混算。")


def _render_regime_reference() -> None:
    """20y regime corpus (local-only, gitignored): show if present, else a note."""
    hist = _shared.load_json(str(_DIR / "regime_history.json"))
    if not hist:
        st.caption("體制歷史語料(20 年)為本機產生、未版控;跑 "
                   "`python scripts/market_regime_history.py` 後於此顯示前向報酬分布。")
        return
    summary = hist.get("regime_summary") or {}
    with st.expander("📈 20 年體制歷史前向報酬(類比參考,非信號)", expanded=False):
        import pandas as pd
        rows = []
        for name in ("rally", "correction", "range"):
            rd = summary.get(name) or {}
            if not rd:
                continue
            for bk in ("fwd_20d", "fwd_40d", "fwd_60d"):
                f = rd.get(bk) or {}
                if not f:
                    continue
                rows.append({
                    "體制": name, "天數": rd.get("days", "?"), "視窗": bk,
                    "平均": _pct(f.get("mean")), "上漲率": _pct(f.get("up_rate"), 1),
                    "P10": _pct(f.get("p10")), "最差": _pct(f.get("worst")),
                })
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def render() -> None:
    st.header("🧭 大盤行情研判")
    st.caption("Tier-1 體制/事件研判(每週鎖定 → 前向驗證)。資料由程式碼決定論產生,"
               "非 AI 編造;Tier-2 agentic 層尚未啟用。")

    fc = _latest_forecast()
    _render_banner(fc)
    st.divider()
    _render_forecast(fc)
    st.divider()
    _render_validation(_shared.load_json(str(_DIR / "validation_summary.json")))
    st.divider()
    _render_regime_reference()
    st.markdown("---")
    st.caption("⚠️ 僅供訊號生成,非投資建議。前向命中率為已發生事件的回顧驗證,非未來預測精度。")
