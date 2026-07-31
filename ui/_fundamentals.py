"""個股總覽 · 基本面 — 規則式體質評分卡 + 可選 LLM 研判。

資料層 `scripts/fundamentals_free.gather_fundamentals`(免費 yfinance .info 單點快照,快取 6h):
估值 / 獲利率 / 成長 / 財務健康 / 分析師。**無同業比較、無歷史趨勢/CAGR**(那需付費 .financials),
所以 `classify()` 用絕對區間 band 判讀,且畫面**先亮此限制**。LLM 研判
`scripts/fundamentals_read.generate_fundamentals_read` 點擊才生成(verified-data-to-AI、非投資建議)。

對外:
  load(ticker)             — 快取的資料載入(None = 免費源無此檔)
  classify(data)           — 確定性 band 判讀(估值/品質/成長/健康 + 綜合體質 + 一句結論)
  invest_read_chips(d,spot)— 雙讀頭部用的「投資體質」chips(估值/體質/分析師上行)
  render_fundamentals(t)   — 分頁進入點(評分卡 + gated LLM 研判)
"""

import sys

import streamlit as st

from . import _shared

_SCRIPTS = str(_shared.DATA_DIR / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)


# ───────────────────────── data load ─────────────────────────
@st.cache_data(ttl=21600, show_spinner=False)
def load(ticker: str) -> dict | None:
    """Free fundamentals snapshot for a ticker (cached 6h). None on any failure."""
    try:
        import fundamentals_free as ff
        return ff.gather_fundamentals(ticker)
    except Exception:  # noqa: BLE001
        return None


@st.cache_data(ttl=86400, show_spinner=False)
def _generate_read(ticker: str) -> dict:
    """On-demand LLM 研判 (cached 24h so re-opening the tab doesn't re-bill)."""
    try:
        import fundamentals_read as fr
        return fr.generate_fundamentals_read(ticker)
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": str(e)}


# ───────────────────────── deterministic classification ─────────────────────────
def _num(x):
    return x if isinstance(x, (int, float)) else None


def _valuation(val: dict) -> dict:
    """Absolute-band richness vote (0 cheap … 3 expensive). Honest: no peer context."""
    votes = []
    pe = _num(val.get("forward_pe")) or _num(val.get("trailing_pe"))
    if pe is not None and pe > 0:
        votes.append(0 if pe < 15 else 1 if pe < 25 else 2 if pe < 40 else 3)
    peg = _num(val.get("peg_ratio"))
    if peg is not None and peg > 0:
        votes.append(0 if peg < 1 else 1 if peg < 2 else 3)
    ps = _num(val.get("price_to_sales"))
    if ps is not None and ps > 0:
        votes.append(0 if ps < 2 else 1 if ps < 6 else 2 if ps < 12 else 3)
    ev = _num(val.get("ev_to_ebitda"))
    if ev is not None and ev > 0:
        votes.append(0 if ev < 8 else 1 if ev < 12 else 2 if ev < 20 else 3)
    if not votes:
        return {"label": "—", "color": _shared.MUTED, "score": None}
    score = round(sum(votes) / len(votes))
    label, color = [("便宜", _shared.GREEN), ("合理", _shared.AMBER),
                    ("偏貴", _shared.RED), ("極貴", _shared.ACCENT)][min(score, 3)]
    return {"label": label, "color": color, "score": score}


def _quality(prof: dict) -> dict:
    """Margins + ROE → 強/中/弱."""
    s, seen = 0, False
    nm = _num(prof.get("profit_margin"))
    if nm is not None:
        seen = True
        s += 2 if nm > 20 else 1 if nm > 8 else 0 if nm > 0 else -2
    roe = _num(prof.get("return_on_equity"))
    if roe is not None:
        seen = True
        s += 2 if roe > 20 else 1 if roe > 10 else 0
    gm = _num(prof.get("gross_margin"))
    if gm is not None:
        seen = True
        s += 1 if gm > 50 else 0
    if not seen:
        return {"label": "—", "color": _shared.MUTED, "rank": None}
    label, color, rank = (("強", _shared.GREEN, 2) if s >= 3 else
                          ("中", _shared.AMBER, 1) if s >= 1 else
                          ("弱", _shared.RED, 0))
    return {"label": label, "color": color, "rank": rank}


def _growth(g: dict) -> dict:
    """Revenue growth primary, earnings as tiebreak → 高成長/穩健/趨緩/衰退."""
    rev = _num(g.get("revenue_growth"))
    eps = _num(g.get("earnings_growth"))
    base = rev if rev is not None else eps
    if base is None:
        return {"label": "—", "color": _shared.MUTED, "rank": None}
    if base > 20:
        return {"label": "高成長", "color": _shared.GREEN, "rank": 2}
    if base >= 5:
        return {"label": "穩健", "color": _shared.AMBER, "rank": 1}
    if base >= 0:
        return {"label": "趨緩", "color": _shared.MUTED, "rank": 0}
    return {"label": "衰退", "color": _shared.RED, "rank": -1}


def _health(h: dict) -> dict:
    """Leverage + liquidity + FCF sign → 穩健/普通/承壓. (D/E is a percentage.)"""
    s, seen = 0, False
    de = _num(h.get("debt_to_equity"))
    if de is not None:
        seen = True
        s += 1 if de < 80 else 0 if de < 180 else -1
    cr = _num(h.get("current_ratio"))
    if cr is not None:
        seen = True
        s += 1 if cr > 1.5 else 0 if cr >= 1 else -1
    fcf = _num(h.get("free_cashflow"))
    if fcf is not None:
        seen = True
        s += 1 if fcf > 0 else -1
    if not seen:
        return {"label": "—", "color": _shared.MUTED, "rank": None}
    label, color, rank = (("穩健", _shared.GREEN, 2) if s >= 2 else
                          ("普通", _shared.AMBER, 1) if s >= 0 else
                          ("承壓", _shared.RED, 0))
    return {"label": label, "color": color, "rank": rank}


def classify(data: dict) -> dict:
    """Deterministic, free, instant fundamental read. Returns per-lens label+color
    and a composite 體質 (quality+growth+health) plus a one-line verdict."""
    valuation = _valuation(data.get("valuation") or {})
    quality = _quality(data.get("profitability_pct") or {})
    growth = _growth(data.get("growth_pct") or {})
    health = _health(data.get("health") or {})

    ranks = [x["rank"] for x in (quality, growth, health) if x.get("rank") is not None]
    if ranks:
        tot = sum(ranks)
        const = (("強", _shared.GREEN) if tot >= 4 else
                 ("中", _shared.AMBER) if tot >= 2 else ("弱", _shared.RED))
    else:
        const = ("—", _shared.MUTED)
    constitution = {"label": const[0], "color": const[1]}

    parts = []
    if growth["label"] != "—":
        parts.append(growth["label"])
    if constitution["label"] != "—":
        parts.append(f"體質{constitution['label']}")
    if valuation["label"] != "—":
        parts.append(f"估值{valuation['label']}")
    verdict = "、".join(parts) + "。" if parts else "免費源資料不足以判讀。"

    return {"valuation": valuation, "quality": quality, "growth": growth,
            "health": health, "constitution": constitution, "verdict": verdict}


# ───────────────────────── header chips (雙讀) ─────────────────────────
def invest_read_chips(data: dict | None, spot=None) -> list:
    """Chips for the two-read header's 投資體質 side: 估值 · 體質 · 分析師上行.

    Analyst upside uses ONLY the fundamentals snapshot's target_mean_price vs spot
    — no extra analyst network call on the always-on header path."""
    if not data:
        return []
    c = classify(data)
    chips = []
    if c["valuation"]["label"] != "—":
        chips.append((f"估值 {c['valuation']['label']}", c["valuation"]["color"]))
    if c["constitution"]["label"] != "—":
        chips.append((f"體質 {c['constitution']['label']}", c["constitution"]["color"]))
    tgt = (data.get("estimates") or {}).get("target_mean_price")
    if isinstance(tgt, (int, float)) and tgt > 0 and isinstance(spot, (int, float)) and spot > 0:
        up = (tgt - spot) / spot * 100
        chips.append((f"分析師 {up:+.0f}%", _shared.GREEN if up >= 0 else _shared.RED))
    return chips


# ───────────────────────── rendering ─────────────────────────
def _money(x) -> str:
    if not isinstance(x, (int, float)) or x <= 0:
        return "—"
    for div, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if x >= div:
            return f"${x / div:.2f}{suf}"
    return f"${x:,.0f}"


def _fmt(x, suffix="", mult=1.0, dp=1) -> str:
    return f"{x * mult:.{dp}f}{suffix}" if isinstance(x, (int, float)) else "—"


def render_scorecard(data: dict) -> None:
    c = classify(data)
    # limitation FIRST (house "先亮限制" pattern), then the read
    st.caption("⚠ 免費 yfinance 單點快照,無同業比較與歷史趨勢;區間判讀為絕對值參考、非投資建議。")
    _shared.chips_row([
        (f"估值 {c['valuation']['label']}", c["valuation"]["color"]),
        (f"體質 {c['constitution']['label']}", c["constitution"]["color"]),
        (f"成長 {c['growth']['label']}", c["growth"]["color"]),
        (f"財務 {c['health']['label']}", c["health"]["color"]),
    ])
    st.markdown(f"**基本面結論**　{c['verdict']}")

    val = data.get("valuation") or {}
    prof = data.get("profitability_pct") or {}
    gro = data.get("growth_pct") or {}
    hea = data.get("health") or {}

    st.markdown("##### 估值")
    r = st.columns(4)
    _shared.metric_card(r[0], "市值", _money(val.get("market_cap")))
    _shared.metric_card(r[1], "預估本益比", _fmt(val.get("forward_pe"), "x"),
                        help="forward P/E;缺則見下方 trailing")
    _shared.metric_card(r[2], "PEG", _fmt(val.get("peg_ratio"), "", dp=2),
                        help="本益成長比 <1 便宜、>2 偏貴")
    _shared.metric_card(r[3], "EV/EBITDA", _fmt(val.get("ev_to_ebitda"), "x"))
    r2 = st.columns(4)
    _shared.metric_card(r2[0], "本益比(TTM)", _fmt(val.get("trailing_pe"), "x"))
    _shared.metric_card(r2[1], "股價淨值比", _fmt(val.get("price_to_book"), "x"))
    _shared.metric_card(r2[2], "股價營收比", _fmt(val.get("price_to_sales"), "x"))
    _shared.metric_card(r2[3], "估值判讀", c["valuation"]["label"])

    st.markdown("##### 獲利品質")
    q = st.columns(4)
    _shared.metric_card(q[0], "毛利率", _fmt(prof.get("gross_margin"), "%"))
    _shared.metric_card(q[1], "營業利益率", _fmt(prof.get("operating_margin"), "%"))
    _shared.metric_card(q[2], "淨利率", _fmt(prof.get("profit_margin"), "%"))
    _shared.metric_card(q[3], "ROE", _fmt(prof.get("return_on_equity"), "%"))

    st.markdown("##### 成長")
    g = st.columns(3)
    _shared.metric_card(g[0], "營收成長(YoY)", _fmt(gro.get("revenue_growth"), "%"))
    _shared.metric_card(g[1], "盈餘成長(YoY)", _fmt(gro.get("earnings_growth"), "%"))
    _shared.metric_card(g[2], "單季盈餘 YoY", _fmt(gro.get("earnings_q_growth_yoy"), "%"))

    st.markdown("##### 財務健康")
    h = st.columns(4)
    _shared.metric_card(h[0], "負債/股東權益", _fmt(hea.get("debt_to_equity"), "%"),
                        help="yfinance 以百分比表示,如 150 = 1.5x")
    _shared.metric_card(h[1], "流動比", _fmt(hea.get("current_ratio"), "x", dp=2))
    _shared.metric_card(h[2], "自由現金流", _money(hea.get("free_cashflow")))
    _shared.metric_card(h[3], "現金 / 負債",
                        f"{_money(hea.get('total_cash'))} / {_money(hea.get('total_debt'))}")
    st.caption(f"來源:`{data.get('source', 'yfinance_free')}`。基本面變動慢,快取 6 小時。")


_CONF_COLOR = {"high": _shared.GREEN, "medium": _shared.AMBER, "low": _shared.RED}


def render_read_card(read: dict) -> None:
    """LLM 研判 card — mirrors ui/sector_rotation.py's 輪動研判 layout."""
    if read.get("headline"):
        st.markdown(f"### {read['headline']}")
    conf = (read.get("confidence") or "—").lower()
    _shared.chips_row([(f"信心 {read.get('confidence', '—')}", _CONF_COLOR.get(conf, _shared.MUTED))])
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**🟢 強項**")
        for it in read.get("strengths", []) or []:
            st.markdown(f"- **{it.get('metric', '')}** {it.get('why', '')}")
        if not read.get("strengths"):
            st.caption("—")
    with c2:
        st.markdown("**🔴 關注**")
        for it in read.get("concerns", []) or []:
            st.markdown(f"- **{it.get('metric', '')}** {it.get('why', '')}")
        if not read.get("concerns"):
            st.caption("—")
    if read.get("thesis"):
        with st.container(border=True):
            st.markdown(f"**投資論述**\n\n{read['thesis']}")
    for cav in read.get("caveats", []) or []:
        st.caption(f"⚠️ {cav}")


def render_fundamentals(ticker: str) -> None:
    """Tab entry: deterministic scorecard (auto) + on-demand LLM 研判 (gated button)."""
    data = load(ticker)
    if not data:
        st.caption("免費源無此檔基本面資料(常見於 ETF / 海外 / 小型股)。")
        return
    render_scorecard(data)

    st.divider()
    flag = f"fund_llm_{ticker}"
    if st.session_state.get(flag):
        with st.spinner(f"生成 {ticker} 基本面研判…(LLM,首次較慢)"):
            res = _generate_read(ticker)
        if res.get("status") == "ready":
            render_read_card(res.get("read") or {})
        elif res.get("status") == "no_data":
            st.caption("基本面研判:免費源無足夠資料。")
        else:
            st.caption(f"基本面研判暫無({res.get('error') or res.get('status')})。"
                       "請先完成 Codex ChatGPT 訂閱登入。")
        if st.button("🔄 重新生成", key=f"fund_llm_regen_{ticker}"):
            _generate_read.clear()
            st.rerun()
    else:
        st.caption("把上述已驗證數字交給 LLM 寫一段投資論述(verified-data-to-AI、非投資建議)。")
        if st.button("🧠 生成基本面研判 (LLM)", key=f"fund_llm_btn_{ticker}"):
            st.session_state[flag] = True
            st.rerun()
