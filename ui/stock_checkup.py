"""美股 · 個股總覽 — 一站式個股研究中心。

輸入一檔(或一批)代碼,一頁看齊。**單檔**模式:最上方固定一條**雙讀頭部**(同時給交易者與
投資者結論),其下用分頁籤切換七個面向,並以**交易面 → 投資面**排序:
  ① 因子體檢 — 即時套用復盤「已驗證」因子,標出符合/未達/資料不足 + 符合的交易者原型
  ② 期權作戰台 — 判定 → 方向 → 波動 → 圖 → 合約/損益 → 檢查清單(嵌入期權作戰台)
  ③ 完整期權鏈明細 — 免費期權鏈 Dim 6a/6d、鏈分佈、波動結構
  ④ 板塊定位 — 這檔所屬 SPDR 板塊在 RRG 的象限(領漲/醞釀/落後/轉弱)+ 量化層級
                (RS-Ratio / RS-Momentum / 板塊熱度 / 20日超額 + 旋轉軌跡)
  ⑤ 基本面 — 估值 / 獲利品質 / 成長 / 財務健康 規則式體質評分卡 + 可選 LLM 研判
  ⑥ 分析師評級 — 賣方共識、目標價、升降評、預估修正
  ⑦ 機構 — 機構 / 內部人持股、前大戶、Form-4 內部人買賣

雙讀頭部:身份行(代號 · 現價/日漲跌 · 市值 · 板塊)+ 交易傾向(暴漲傾向/作戰台判定/大盤)
+ 投資體質(估值/體質/分析師上行)。① – ④ 為交易面、⑤ – ⑦ 為投資面。

批次模式:貼一批代碼 → 只跑輕量「因子體檢 + 傾向」排序表,點某檔再展開完整七分頁。

效能:st.tabs 會一次渲染全部分頁,故較重的網路面向(期權分析/分析師/機構)用按鈕閘門延遲載入;
判定列已暖好的 cockpit + 板塊資料,讓 ②/⑥ 分頁可即時開啟。重複查同代碼第二次秒開(快取)。

重要:暴漲傾向繼承復盤的 fail-closed 閘門(survivorship/樣本不足 → blocked),為**方向性參考、
非交易訊號**。傾向 = 已驗證因子的 lift 加權覆蓋,不是校準機率。所以畫面一律**先亮限制、再給分數**。
"""

import sys

import pandas as pd
import streamlit as st

from . import _fundamentals as fund
from . import _shared

# live_factors lives in scripts/; put it on the path and import directly (same
# pattern momentum_options / retro_* use among themselves).
_SCRIPTS = str(_shared.DATA_DIR / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import live_factors as lf  # noqa: E402
import quote_fallback  # noqa: E402

# band level 0..4 → 語意色(很低/低=muted, 中=amber, 中偏高/高=green)
_BAND_COLOR = [_shared.MUTED, _shared.MUTED, _shared.AMBER, _shared.GREEN, _shared.GREEN]
_STATUS_COLOR = {"✓ 符合": _shared.GREEN, "✗ 未達": _shared.MUTED, "— 資料不足": _shared.AMBER}
_LABEL_COLOR = {"很低": _shared.MUTED, "低": _shared.MUTED, "中": _shared.AMBER,
                "中偏高": _shared.GREEN, "高": _shared.GREEN, "無資料": _shared.MUTED}

# RRG quadrant → semantic colour. 領漲=green, 醞釀=cyan(輪入中,非警示故不用 amber),
# 轉弱=red, 落後=muted(只是退流行,非警報)。
_QUADRANT_COLOR = {"Leading": _shared.GREEN, "Improving": _shared.CYAN,
                   "Weakening": _shared.RED, "Lagging": _shared.MUTED}


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


def _provenance_locked(res: dict) -> bool:
    """HARD lock (Codex r20 #2): a provenance-bad lift (provenance_ok False = stale / cross-run /
    floor-less / forged factor_lift) yields a MEANINGLESS band — suppress band/score/lift entirely
    on EVERY surface (single + batch), not merely warn. Renders the lock + returns True when locked.
    A merely DIRECTIONAL run (provenance_ok True but blocked) keeps the directional band + _caveat."""
    if res.get("provenance_ok") is False:
        st.error("🔒 **來源失效 — factor_lift 與當前 surge_events／特徵不同跑次或缺流動性門檻**,"
                 "暴漲傾向／覆蓋計分／因子判定皆不可信,已隱藏。請重跑 retro 管線後再看。")
        return True
    return False


# ───────────────────────── sector positioning (RRG) ─────────────────────────
def _sector_lookup(ticker: str):
    """(etf, sector_dict) for a ticker; sector_dict is None if unmapped / not in
    the rotation board. Cheap — both loaders are @st.cache_data, shared with the
    判定列 chip and the ⑥ 板塊定位 panel so the network cost is paid once."""
    etf = _shared.ticker_sector_etf(ticker)        # 快取 6h;免費源無 .info[sector] → None
    flow = _shared.load_sector_flow()              # 快取 1h
    if not etf or not flow or not flow.get("sectors"):
        return etf, None
    sec = {s["etf"]: s for s in flow["sectors"]}.get(etf)
    return etf, sec


def _sector_tail_chart(sec: dict, color: str) -> None:
    """RRG rotation trajectory from the sector's stored ~8-point tail."""
    tail = sec.get("tail") or []
    if len(tail) < 2:
        return
    xs = [p.get("rs_ratio") for p in tail]
    ys = [p.get("rs_momentum") for p in tail]
    if any(v is None for v in xs + ys):
        return
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_vline(x=100, line_color="#555", line_width=1)
    fig.add_hline(y=100, line_color="#555", line_width=1)
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers",
                             line=dict(color=color, width=2), marker=dict(size=5),
                             showlegend=False,
                             hovertext=[p.get("date", "") for p in tail]))
    fig.add_trace(go.Scatter(x=[xs[-1]], y=[ys[-1]], mode="markers",
                             marker=dict(size=13, color=color), showlegend=False,
                             hovertext=tail[-1].get("date", "")))
    fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10),
                      xaxis_title="RS-Ratio", yaxis_title="RS-Momentum",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font={"color": "#e6e9ef"})
    st.plotly_chart(fig, width="stretch")
    st.caption("RRG 旋轉軌跡(~週取樣);大點為最新。理想順時針:醞釀→領漲→轉弱→落後。")


def _sector_positioning(ticker: str) -> None:
    etf, sec = _sector_lookup(ticker)
    if not etf:
        st.caption("無法判定板塊定位(免費源無產業別;ETF / 海外 / 小型股常見)。")
        return
    if sec is None:
        st.caption(f"{ticker} 對應板塊 ETF {etf},但該 ETF 不在輪動板塊清單中。")
        return
    q = sec["quadrant"]
    color = _QUADRANT_COLOR.get(q, _shared.MUTED)
    st.markdown(f"**{sec['name_zh']}**（{etf}）　"
                + _shared.chip(f"{sec['quadrant_zh']}（RRG {q}）", color),
                unsafe_allow_html=True)
    cols = st.columns(4)                            # ← 量化層級
    _shared.metric_card(cols[0], "RS-Ratio", f"{sec['rs_ratio']:.1f}",
                        help="相對 SPY 強度,中軸 100;>100 強於大盤")
    _shared.metric_card(cols[1], "RS-Momentum", f"{sec['rs_momentum']:.1f}",
                        help="相對強度的動能,中軸 100;>100 加速")
    heat = sec.get("heat_score")
    _shared.metric_card(cols[2], "板塊熱度", f"{heat:.0f}" if heat is not None else "—",
                        help="跨板塊資金流熱度 0-100(綜合排名)")
    ex = sec.get("excess_20d")
    _shared.metric_card(cols[3], "20日超額", f"{ex:+.1f}%" if ex is not None else "—",
                        help="板塊近 20 日報酬減 SPY")
    _sector_tail_chart(sec, color)

    def _p(v):
        return f"{v:+.1f}%" if isinstance(v, (int, float)) else "—"
    st.caption(f"板塊近 5/20/60 日報酬:{_p(sec.get('ret_5d'))} / {_p(sec.get('ret_20d'))} "
               f"/ {_p(sec.get('ret_60d'))}　"
               "(板塊定位 = 這檔所屬 SPDR 板塊在 RRG 的位置,非個股本身的相對強度)。"
               "完整全板塊輪動見「熱錢板塊輪動」頁。")


# ───────────────────────── two-read header ─────────────────────────
def _money(x) -> str:
    if not isinstance(x, (int, float)) or x <= 0:
        return "—"
    for div, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if x >= div:
            return f"${x / div:.2f}{suf}"
    return f"${x:,.0f}"


def _quote_source_chip(quote: dict | None, source_label: str | None = None) -> str:
    text = source_label or quote_fallback.quote_source_text(quote)
    color = _shared.AMBER if "fallback" in text.lower() else _shared.MUTED
    return _shared.chip(text, color)


def _header(res: dict, cockpit, fdata, ticker: str, quote: dict | None = None) -> None:
    """Two-read header — an identity line, then 交易傾向 (trader) and 投資體質 (investor)
    side by side, so the page leads with a conclusion for BOTH personas."""
    val = (fdata or {}).get("valuation") or {}
    parts = [f"**{ticker}**"]
    source_chip = None
    live_cockpit = cockpit is not None and not getattr(cockpit, "is_demo", False)
    if live_cockpit:
        col = _shared.GREEN if cockpit.day_change_pct >= 0 else _shared.RED
        parts.append(f"${cockpit.spot:,.2f}")
        parts.append(f"<span style='color:{col}'>{cockpit.day_change_pct:+.2f}%</span>")
        source_chip = _quote_source_chip(None, getattr(cockpit, "quote_source_label", "來源：yfinance"))
    elif isinstance(quote, dict) and quote.get("status") == "ok":
        parts.append(f"${float(quote['price']):,.2f}")
        source_chip = _quote_source_chip(quote)
    mc = _money(val.get("market_cap"))
    if mc != "—":
        parts.append(f"市值 {mc}")
    # Escape '$' so Streamlit markdown doesn't read "$213.17 … $5.16T" as a LaTeX
    # math span (which would swallow the inline day-change <span>). The chip HTML
    # appended afterwards has no '$', so escape only the text portion.
    line = "　·　".join(parts).replace("$", "\\$")
    _etf, sec = _sector_lookup(ticker)
    if sec is not None:
        line += "　" + _shared.chip(sec["name_zh"], _QUADRANT_COLOR.get(sec["quadrant"], _shared.MUTED))
    if source_chip:
        line += "　" + source_chip
    st.markdown(line, unsafe_allow_html=True)

    _locked = res.get("provenance_ok") is False    # Codex r20: garbage lift → suppress the band
    if _locked:
        _provenance_locked(res)
    else:
        _caveat(res)                                # fail-closed gate before the surge band
    t_col, i_col = st.columns(2)
    with t_col:
        st.caption("📈 交易傾向")
        if _locked:
            # band is from the untrusted lift — hide it; the fundamentals column below is independent.
            st.markdown(_shared.chip("🔒 來源失效", _shared.MUTED), unsafe_allow_html=True)
        else:
            chips = [(f"{_dots(res['band_level'])} {res['band_label']}", _BAND_COLOR[res["band_level"]])]
            if cockpit is not None:
                chips.append((cockpit.verdict, _shared.verdict_color(cockpit.verdict)))
                regime_zh = {"risk_on": "偏多", "risk_off": "偏空"}.get(cockpit.regime, "中性")
                chips.append((f"大盤{regime_zh}", _shared.MUTED))
            _shared.chips_row(chips)
            if cockpit is None:
                st.caption("期權作戰台資料暫無。")
    with i_col:
        st.caption("💰 投資體質")
        spot = cockpit.spot if live_cockpit else (quote.get("price") if isinstance(quote, dict) else None)
        ichips = fund.invest_read_chips(fdata, spot)
        if ichips:
            _shared.chips_row(ichips)
        else:
            st.markdown(_shared.chip("基本面資料暫無", _shared.MUTED), unsafe_allow_html=True)


# ───────────────────────── single-stock sections ─────────────────────────


def _scorecard(res: dict) -> None:
    if _provenance_locked(res):                     # garbage lift → suppress the whole scorecard
        return
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
        styled, hide_index=True, width="stretch",
        column_config={
            "狀態": "狀態", "因子": "因子", "維度": "維度",
            "lift": st.column_config.NumberColumn("lift", format="%.2f",
                                                  help="暴漲前出現率 / 隨機出現率"),
            "判定": "復盤判定",
        })


# ───────────────────────── lazy facet gate ─────────────────────────
def _lazy(key: str, ticker: str, render_fn, *, auto: bool = False,
          label: str = "載入此面板") -> None:
    """Gate a heavy facet behind a per-(ticker, facet) button so st.tabs' eager
    render doesn't fire every network loader at once. Once loaded for this ticker
    it stays loaded (session flag + each loader's own @st.cache_data). A facet that
    errors shows a caption rather than blanking the whole page.

    (st.fragment is NOT used: it scopes reruns but does NOT prevent the initial
    eager render of all tab bodies, so it wouldn't defer the first cold fetch.)"""
    flag = f"load_{key}_{ticker}"
    if auto or st.session_state.get(flag):
        try:
            render_fn(ticker)
        except Exception as exc:  # noqa: BLE001 — one facet must not blank the page
            st.caption(f"此面板暫時無法載入({exc}).")
        return
    st.caption("此面板需抓取即時資料(首次較慢)。")
    if st.button(label, key=f"btn_{flag}"):
        st.session_state[flag] = True
        st.rerun()


def _render_trade_data_status(ticker: str, cockpit, quote: dict | None = None) -> None:
    with st.container(border=True):
        st.caption(f"{ticker} 搜尋後已刷新")
        cockpit_color = _shared.GREEN if cockpit is not None else _shared.AMBER
        chips = [
            ("因子體檢: 已載入", _shared.GREEN),
            ("作戰台核心: 已嘗試抓取期權鏈 / ATM IV / 建議合約", cockpit_color),
            ("完整期權鏈明細: 按需載入", _shared.BLUE),
        ]
        if isinstance(quote, dict) and quote.get("status") == "ok":
            chips.append((quote_fallback.quote_source_text(quote), _shared.AMBER))
        elif cockpit is not None and getattr(cockpit, "quote_source_label", None):
            chips.append((cockpit.quote_source_label, _shared.MUTED))
        _shared.chips_row(chips)
        st.caption(
            "作戰台先給交易決策；完整期權鏈明細保留履約價分佈、最活躍 call、波動率結構。"
        )


def _render_single(ticker: str) -> None:
    if not ticker:
        st.info("輸入代碼後按「體檢」。")
        return
    st.session_state["checkup_ticker"] = ticker

    with st.spinner(f"體檢 {ticker} …"):
        flags = lf.live_factor_flags(ticker)
        res = lf.score_surge(flags) if flags is not None else None
    if res is None:
        st.error(f"{ticker} 無足夠歷史可體檢(需 ≥60 個交易日,且代碼有效)。")
        return

    # Cockpit feeds the always-visible verdict row (heaviest load but most
    # decision-relevant). Its own spinner paints the row before the tab loaders
    # fire; the cache it warms also makes the ② 期權作戰台 tab open instantly.
    cockpit = None
    try:
        from . import options_cockpit as oc
        with st.spinner(f"載入 {ticker} 作戰台判定…(抓取期權鏈,首次較慢)"):
            cockpit = oc._load_cockpit(ticker)
    except Exception:  # noqa: BLE001
        cockpit = None
    quote = None
    if cockpit is None or getattr(cockpit, "is_demo", False):
        try:
            quote = quote_fallback.get_quote(ticker)
        except Exception:  # noqa: BLE001
            quote = None
    fdata = fund.load(ticker)                       # cached 6h; feeds 投資體質 + 市值

    with st.container(border=True):
        _header(res, cockpit, fdata, ticker, quote=quote)
    _render_trade_data_status(ticker, cockpit, quote=quote)

    st.caption("分頁:① – ④ 交易面 ｜ ⑤ – ⑦ 投資面")
    tabs = st.tabs(["① 因子體檢", "② 期權作戰台", "③ 完整期權鏈明細", "④ 板塊定位",
                    "⑤ 基本面", "⑥ 分析師評級", "⑦ 機構"])
    with tabs[0]:                                   # local & instant (already computed)
        _scorecard(res)
    with tabs[1]:                                   # cache warm from the header
        from . import options_cockpit as oc
        _lazy("cockpit", ticker, oc.render_for, auto=True)
    with tabs[2]:                                   # genuinely-new cold fetch → gated
        from . import us_options as uo
        _lazy("options", ticker, uo.render_for, label="載入完整期權鏈明細")
    with tabs[3]:                                   # loaders warmed by the header chip
        _lazy("sector", ticker, _sector_positioning, auto=True)
    with tabs[4]:                                   # scorecard cheap (6h cache); LLM gated inside
        _lazy("fund", ticker, fund.render_fundamentals, auto=True)
    with tabs[5]:
        from . import analyst_views as av
        _lazy("analyst", ticker, av.render_for)
    with tabs[6]:
        from . import institutional_holdings as ih
        _lazy("inst", ticker, ih.render_for)


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
               "點下方選代碼即展開完整七分頁。傾向為方向性參考、非交易訊號。")
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
                # Carry the live force-block to the batch surface (Codex r20): a GARBAGE lift
                # (provenance_ok False = stale/cross-run/floor-less) must NOT rank or show a band;
                # a merely DIRECTIONAL one (survivorship/events-blocked, real tables) shows the band
                # but is marked 探索性 so it never reads as a validated ranking.
                _bad = not r.get("provenance_ok", False)
                _blk = bool(r.get("blocked"))
                results.append({
                    "代號": r["ticker"],
                    "傾向": ("🔒" if _bad else _dots(r["band_level"])),
                    "_lvl": (-1 if _bad else r["band_level"]),
                    "狀態": ("🔒 來源失效" if _bad else "探索性" if _blk else "✓ 可參考"),
                    "分級": ("封鎖" if _bad else r["band_label"]),
                    # ALL lift-derived fields blanked for a garbage row (Codex r20 round-3) — match
                    # counts / archetypes must not leak from the untrusted lift onto the triage table.
                    "符合": ("—" if _bad else f"{r['n_matched']}/{r['n_validated']}"),
                    "覆蓋%": (None if _bad else round(r["score"] * 100)),
                    "原型": (0 if _bad else len(r.get("archetypes", []))),
                })
            else:
                results.append({"代號": t, "傾向": "—", "_lvl": -1, "狀態": "無資料",
                                "分級": "無資料", "符合": "—", "覆蓋%": None, "原型": 0})
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
        styled, hide_index=True, width="stretch",
        column_config={"覆蓋%": st.column_config.ProgressColumn(
            "覆蓋%", min_value=0, max_value=100, format="%d%%")})

    valid = [r["代號"] for r in results if r["_lvl"] >= 0]
    if valid:
        st.divider()
        st.caption("選擇代號即展開完整七分頁(無需按鈕):")
        pick = st.selectbox("展開個股", ["—", *valid], key="checkup_batch_pick",
                            label_visibility="collapsed")
        if pick and pick != "—":
            _render_single(pick)


# ───────────────────────── entry ─────────────────────────
def render() -> None:
    st.header("🔍 個股總覽")
    # 跨頁 handoff:跳轉方寫入一次性的 checkup_handoff,本頁 pop 消費 — 明確
    # 旗標而非「值有沒有變」的比對,所以同代號重跳也會觸發。殘留的 widget
    # 狀態不能吃掉跳轉 — (a) 模式必須回「單檔」(批次殘留會讓 handoff 落在
    # 批次頁、代號未消費);(b) 代號輸入框必須換成 handoff 代號。兩個 widget
    # 都是單一來源:狀態由 session 預先播種,value=/default= 不再用(有 key 的
    # widget 一旦有狀態就會無視它們)。頁內打字/切模式不受影響。
    handoff = st.session_state.pop("checkup_handoff", None)
    if "checkup_mode" not in st.session_state or handoff:
        st.session_state["checkup_mode"] = "單檔"
    mode = st.segmented_control(
        "模式", ["單檔", "批次"],
        label_visibility="collapsed", key="checkup_mode")
    if mode == "批次":
        _render_batch()
        return
    if handoff:
        st.session_state["checkup_ticker_input"] = handoff
    elif "checkup_ticker_input" not in st.session_state:
        st.session_state["checkup_ticker_input"] = \
            st.session_state.get("checkup_ticker") or "NVDA"
    c1, c2 = st.columns([4, 1])
    ticker = c1.text_input("代號", key="checkup_ticker_input",
                           label_visibility="collapsed").strip().upper().lstrip("$")
    go = c2.button("體檢", width="stretch", key="checkup_go")
    if ticker:
        st.session_state["checkup_ticker"] = ticker
    if go or ticker:
        _render_single(ticker)
