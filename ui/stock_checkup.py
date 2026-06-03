"""美股 · 個股總覽 — 一站式個股體檢。

輸入一檔(或一批)代碼,一次看齊:
  ① 判定列 — 期權作戰台判定 + 暴漲傾向 + 當日/大盤
  ② 暴漲因子體檢 — 即時套用復盤「已驗證」因子,標出符合/未達/資料不足 + 符合的交易者原型
  ③ 期權摘要 — IV Rank / ATM IV / 預期波動(連到完整期權作戰台)
  ④ 機構籌碼 — 機構持股% / 前大戶 / 內部人淨買賣(連到機構面板)

批次模式:貼一批代碼 → 只跑輕量「因子體檢 + 傾向」排序表,點某檔再展開完整四面板。

重要:暴漲傾向繼承復盤的 fail-closed 閘門(survivorship/樣本不足 → blocked),為**方向性參考、
非交易訊號**。傾向 = 已驗證因子的 lift 加權覆蓋,不是校準機率。所以畫面一律**先亮限制、再給分數**。
"""

import sys

import pandas as pd
import streamlit as st

from . import _shared

# live_factors lives in scripts/; put it on the path and import directly (same
# pattern momentum_options / retro_* use among themselves).
_SCRIPTS = str(_shared.DATA_DIR / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import live_factors as lf  # noqa: E402

# band level 0..4 → 語意色(很低/低=muted, 中=amber, 中偏高/高=green)
_BAND_COLOR = [_shared.MUTED, _shared.MUTED, _shared.AMBER, _shared.GREEN, _shared.GREEN]
_STATUS_COLOR = {"✓ 符合": _shared.GREEN, "✗ 未達": _shared.MUTED, "— 資料不足": _shared.AMBER}
_LABEL_COLOR = {"很低": _shared.MUTED, "低": _shared.MUTED, "中": _shared.AMBER,
                "中偏高": _shared.GREEN, "高": _shared.GREEN, "無資料": _shared.MUTED}


def _dots(level: int) -> str:
    level = max(0, min(4, int(level)))
    return "●" * (level + 1) + "○" * (4 - level)


def _band_html(res: dict, prefix: str = "") -> str:
    lvl = res["band_level"]
    return _shared.chip(f"{prefix}{_dots(lvl)} {res['band_label']}", _BAND_COLOR[lvl])


def _caveat(res: dict) -> None:
    """Fail-closed gate — ALWAYS shown before the band/score it disclaims, leading
    with the conclusion so amber is never misread as mere 'caution'."""
    if res.get("blocked"):
        st.warning(f"**⚠ 非交易訊號 — 暴漲傾向僅為方向性參考**\n\n{res.get('caveat', '')}")


# ───────────────────────── single-stock sections ─────────────────────────
def _verdict_row(res: dict, cockpit) -> None:
    cols = st.columns(4)
    if cockpit is not None:
        _shared.metric_card(cols[0], "作戰台判定", cockpit.verdict)
        _shared.metric_card(cols[1], "現價", f"${cockpit.spot:,.2f}",
                            delta=f"{cockpit.day_change_pct:+.2f}%")
        regime_zh = {"risk_on": "🟢 偏多", "risk_off": "🔴 偏空"}.get(cockpit.regime, "⚪ 中性")
        _shared.metric_card(cols[2], "大盤環境", regime_zh)
    with cols[3]:
        st.caption("暴漲傾向")
        st.markdown(_band_html(res), unsafe_allow_html=True)
    if cockpit is None:
        st.caption("期權作戰台資料暫無(僅顯示因子體檢)。")


def _scorecard(res: dict) -> None:
    st.subheader("② 暴漲因子體檢")
    _caveat(res)                                    # limitation FIRST, then the band
    st.markdown("**暴漲傾向**　" + _band_html(res), unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    _shared.metric_card(c1, "符合已驗證因子", f"{res['n_matched']}/{res['n_validated']}")
    _shared.metric_card(c2, "覆蓋計分", f"{res['score']:.0%}",
                        help="符合因子的 lift 加權覆蓋率,非機率")

    arch = res.get("archetypes", [])
    if arch:
        st.caption("符合交易者原型:")
        _shared.chips_row([(a["name"], _shared.GREEN) for a in arch])
    else:
        st.caption("符合交易者原型:無")

    rows = ([("✓ 符合", e) for e in res["matched"]]
            + [("✗ 未達", e) for e in res["unmatched"]]
            + [("— 資料不足", e) for e in res["insufficient"]])
    if not rows:
        st.info("尚無已驗證因子可比對(先跑 retro 管線產生 factor_lift.json)。")
        return
    df = pd.DataFrame([{
        "狀態": s, "因子": e["desc"] or e["factor"], "維度": e["dim"],
        "lift": e["lift"], "判定": e["verdict"],
    } for s, e in rows])
    try:                                            # tinted bg so 未達/資料不足 stay legible on dark
        styled = df.style.map(
            lambda v: f"color:{_STATUS_COLOR.get(v, '')};background-color:{_STATUS_COLOR.get(v, '')}33",
            subset=["狀態"])
    except Exception:  # noqa: BLE001
        styled = df
    st.dataframe(
        styled, hide_index=True, use_container_width=True,
        column_config={
            "狀態": "狀態", "因子": "因子", "維度": "維度",
            "lift": st.column_config.NumberColumn("lift", format="%.2f",
                                                  help="暴漲前出現率 / 隨機出現率"),
            "判定": "復盤判定",
        })


def _options_summary(ticker: str) -> None:
    st.subheader("③ 期權摘要")
    try:
        from . import options_cockpit as oc
        data = oc._load_cockpit(ticker)
    except Exception as exc:  # noqa: BLE001 — degrade gracefully
        st.caption(f"期權資料暫無({exc}).")
        data = None
    if data is None:
        st.caption("期權資料暫無。")
    else:
        cols = st.columns(4)
        _shared.metric_card(cols[0], "作戰台判定", data.verdict)
        iv = f"{data.atm_iv * 100:.0f}%" if data.atm_iv else "—"
        _shared.metric_card(cols[1], "ATM IV", iv)
        ivr = f"{data.iv_rank:.0f}" if data.iv_rank is not None else "累積中"
        _shared.metric_card(cols[2], "IV Rank", ivr)
        rv = f"{data.realized_vol * 100:.0f}%" if data.realized_vol else "—"
        _shared.metric_card(cols[3], "已實現波動", rv)
        if data.atm_iv and data.contract is not None:
            try:
                from scripts import options_analytics as oa
                em = oa.expected_move(data.spot, data.atm_iv, data.contract.dte)
                st.caption(f"預期波動(1σ,到期 {data.contract.dte}d):±${em:,.2f} "
                           f"(±{em / data.spot * 100:.1f}%)")
            except Exception:  # noqa: BLE001
                pass
    st.link_button("🎯 完整期權作戰台 →", "/options-cockpit")


def _institutional(ticker: str) -> None:
    st.subheader("④ 機構籌碼")
    try:
        from scripts import institutional_free as inf
        data = inf.gather_institutional(ticker)
    except Exception as exc:  # noqa: BLE001
        st.caption(f"機構資料暫無({exc}).")
        data = None
    if not data:
        st.caption("機構資料暫無(小型股/ETF 常無 13F 揭露)。")
    else:
        own = data.get("ownership_pct") or {}
        ins = data.get("insider_6m") or {}
        cols = st.columns(3)
        inst_held = own.get("institutions_held")
        _shared.metric_card(cols[0], "機構持股%",
                            f"{inst_held:.1f}%" if inst_held is not None else "—")
        insiders = own.get("insiders_held")
        _shared.metric_card(cols[1], "內部人持股%",
                            f"{insiders:.1f}%" if insiders is not None else "—")
        nd = ins.get("net_direction")
        nd_zh = {"buying": "🟢 淨買進", "selling": "🔴 淨賣出"}.get(nd, "⚪ 中性/無資料")
        _shared.metric_card(cols[2], "內部人 6 月", nd_zh)
        top = data.get("top_institutional_holders") or []
        if top:
            st.caption("前大戶:")
            _shared.chips_row([
                (f"{h['holder']} {h['pct_held']:.1f}%" if h.get("pct_held") is not None
                 else h["holder"], _shared.BLUE)
                for h in top[:5]])
    st.link_button("🏢 機構面板 →", "/institutions")


def _render_single(ticker: str) -> None:
    if not ticker:
        st.info("輸入代碼後按「體檢」。")
        return
    # Pre-seed sibling pages so the deep-links land on this same ticker.
    st.session_state["cockpit_ticker"] = ticker
    st.session_state["inst_ticker"] = ticker

    with st.spinner(f"體檢 {ticker} …"):
        flags = lf.live_factor_flags(ticker)
        res = lf.score_surge(flags) if flags is not None else None
    if res is None:
        st.error(f"{ticker} 無足夠歷史可體檢(需 ≥60 個交易日,且代碼有效)。")
        return

    cockpit = None
    try:
        from . import options_cockpit as oc
        cockpit = oc._load_cockpit(ticker)
    except Exception:  # noqa: BLE001
        cockpit = None

    with st.container(border=True):
        st.subheader("① 判定列")
        _verdict_row(res, cockpit)
    with st.container(border=True):
        _scorecard(res)
    with st.container(border=True):
        _options_summary(ticker)
    with st.container(border=True):
        _institutional(ticker)


# ───────────────────────── batch ─────────────────────────
def _parse_tickers(text: str) -> list[str]:
    import re
    raw = re.split(r"[\s,;]+", (text or "").upper())
    seen, out = set(), []
    for t in raw:
        t = t.strip().lstrip("$")
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _render_batch() -> None:
    st.caption("貼一批代碼(逗號/空白/換行分隔)。批次只跑輕量「因子體檢 + 傾向」,"
               "點下方選代碼即展開完整四面板。傾向為方向性參考、非交易訊號。")
    text = st.text_area("代碼清單", value="NVDA, AVGO, PLTR", height=80, key="checkup_batch_input")
    tickers = _parse_tickers(text)
    if len(tickers) > 250:
        st.warning(f"清單 {len(tickers)} 檔,超過建議上限 250;只跑前 250 檔。")
        tickers = tickers[:250]

    if st.button(f"批次體檢({len(tickers)} 檔)", disabled=not tickers, key="checkup_batch_run"):
        lift = lf.load_lift()
        with st.spinner("抓取大盤基準(SPY/VIX)…"):
            spy, vix = lf.fetch_spy_vix()
        prog = st.progress(0.0, text="開始…")
        results = []
        for i, t in enumerate(tickers, 1):
            prog.progress(i / len(tickers), text=f"{i}/{len(tickers)} · {t}")
            try:
                r = lf.checkup(t, spy_close=spy, vix_close=vix, lift=lift)
            except Exception:  # noqa: BLE001
                r = None
            if r:
                results.append({
                    "代號": r["ticker"], "傾向": _dots(r["band_level"]),
                    "_lvl": r["band_level"], "分級": r["band_label"],
                    "符合": f"{r['n_matched']}/{r['n_validated']}",
                    "覆蓋%": round(r["score"] * 100),
                    "原型": len(r.get("archetypes", [])),
                })
            else:
                results.append({"代號": t, "傾向": "—", "_lvl": -1, "分級": "無資料",
                                "符合": "—", "覆蓋%": None, "原型": 0})
        prog.empty()
        st.session_state["checkup_batch"] = results

    results = st.session_state.get("checkup_batch")
    if not results:
        return
    df = (pd.DataFrame(results)
          .sort_values(["_lvl", "覆蓋%"], ascending=False)
          .drop(columns=["_lvl"]))

    def _tint(row):                                 # colour 傾向/分級 by band so highs pop
        c = _LABEL_COLOR.get(row["分級"], _shared.MUTED)
        return [f"background-color:{c}33" if col in ("傾向", "分級") else "" for col in row.index]
    try:
        styled = df.style.apply(_tint, axis=1)
    except Exception:  # noqa: BLE001
        styled = df
    st.dataframe(
        styled, hide_index=True, use_container_width=True,
        column_config={"覆蓋%": st.column_config.ProgressColumn(
            "覆蓋%", min_value=0, max_value=100, format="%d%%")})

    valid = [r["代號"] for r in results if r["_lvl"] >= 0]
    if valid:
        st.divider()
        st.caption("選擇代號即展開完整四面板(無需按鈕):")
        pick = st.selectbox("展開個股", ["—", *valid], key="checkup_batch_pick",
                            label_visibility="collapsed")
        if pick and pick != "—":
            _render_single(pick)


# ───────────────────────── entry ─────────────────────────
def render() -> None:
    st.header("🔍 個股總覽")
    mode = st.segmented_control(
        "模式", ["單檔", "批次"], default="單檔",
        label_visibility="collapsed", key="checkup_mode")
    if mode == "批次":
        _render_batch()
        return
    default = st.session_state.get("checkup_ticker", "NVDA")
    c1, c2 = st.columns([4, 1])
    ticker = c1.text_input("代號", value=default, key="checkup_ticker_input",
                           label_visibility="collapsed").strip().upper().lstrip("$")
    go = c2.button("體檢", use_container_width=True, key="checkup_go")
    if ticker:
        st.session_state["checkup_ticker"] = ticker
    if go or ticker:
        _render_single(ticker)
