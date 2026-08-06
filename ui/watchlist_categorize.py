"""美股 · 自選股分類 — 合併 TradingView + IBKR 清單,依板塊/主題分類.

Merges the user's TradingView watchlist (content/us_watchlist.txt, paste/upload)
with the IBKR scanner watchlist (reports/watchlist.json) and IBKR positions
(reports/reconciliation.json, or a live read-only pull), de-dupes, enriches each
ticker with GICS sector via scripts/sector_free (yfinance, cached) and theme tags
via scripts/theme_classify (LLM, cached), and renders grouped by 板塊/主題 with
source chips. Exports a sector-sectioned TradingView .txt. Strictly read-only —
never places orders. v1 importance filter: market-cap >= $2B AND avg dollar volume >= $20M (exchange-agnostic).
"""

import sys
from collections import defaultdict
from pathlib import Path

import streamlit as st

from . import _read_api, _shared

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_TV_FILE = _shared.CONTENT_DIR / "us_watchlist.txt"
_THEMES_FILE = _shared.CONTENT_DIR / "themes.json"  # fixture seam; never read here
_UNCLASSIFIED = "其他 / 未分類"
_NO_THEME = "(無主題)"
# Source chip colours: CYAN for TradingView, MUTED for IBKR scanner (avoid
# overloading BLUE/PURPLE which carry signal/overlay meaning on sibling pages),
# GREEN for IBKR positions (confirmed holdings → bullish/pass semantics).
_SOURCE_CHIP = {
    "tradingview": ("TV", _shared.CYAN),
    "ibkr_scanner": ("IBKR掃描", _shared.MUTED),
    "ibkr_positions": ("IBKR持倉", _shared.GREEN),
}


def _load_taxonomy() -> tuple[dict[str, str], bool]:
    result = _read_api.load_theme_taxonomy()
    if isinstance(result, _read_api.ThemeTaxonomyApiAvailable):
        return {theme.name: theme.description for theme in result.themes}, True
    return {}, False


# ── cached enrichment ─────────────────────────────────────────────────────────
@st.cache_data(ttl=604800, show_spinner=False)
def _sectors(tickers: tuple) -> dict:
    from scripts import sector_free
    return sector_free.gather_sectors(list(tickers))


# ── inputs ────────────────────────────────────────────────────────────────────
def _render_tv_input() -> list[dict]:
    from scripts import sector_free
    # Collapse expander once the watchlist file already exists (set-and-forget).
    tv_exists = _TV_FILE.exists() and _TV_FILE.stat().st_size > 0
    with st.expander("📥 TradingView 自選股清單", expanded=not tv_exists):
        up = st.file_uploader("上傳 TradingView 匯出 .txt", type=["txt"], key="tv_up")
        if "tv_text" not in st.session_state:
            st.session_state["tv_text"] = (
                _TV_FILE.read_text(encoding="utf-8") if _TV_FILE.exists() else "")
        if up is not None and st.session_state.get("_tv_up_id") != up.file_id:
            st.session_state["tv_text"] = up.getvalue().decode("utf-8", "ignore")
            st.session_state["_tv_up_id"] = up.file_id
        text = st.text_area("或貼上(一行一檔,或 EXCHANGE:SYMBOL)", key="tv_text", height=140)
        items = sector_free.parse_tv_watchlist(text)
        c1, c2 = st.columns([1, 4])
        if c1.button("💾 存檔", help=f"寫回 {_TV_FILE.name}"):
            _TV_FILE.write_text(text, encoding="utf-8")
            st.toast(f"已存 {_TV_FILE.name}")
        c2.caption(f"解析到 {len(items)} 檔 · TradingView 無讀取 API,清單由你維護/匯入")
    return items


def _positions_tickers() -> list[str]:
    rec = _shared.load_reconciliation() or {}
    out = []
    for bucket in ("matched", "held_not_in_ledger"):
        for row in rec.get(bucket, []) or []:
            t = row.get("ticker")
            if t:
                out.append(str(t).upper())
    return out


def _render_ibkr_inputs() -> dict:
    out = {}
    # Collapsed by default — checkboxes have sensible defaults (set-and-forget).
    with st.expander("🧾 IBKR 來源(唯讀)", expanded=False):
        if st.checkbox("納入 IBKR 掃描清單", value=True,
                       help="reports/watchlist.json:gainers / hot_volume / high_iv"):
            wl = _shared.load_json(str(_shared.REPORTS_DIR / "watchlist.json")) or {}
            scanner_tickers = [r.get("ticker") for r in wl.get("tickers", []) if r.get("ticker")]
            if not scanner_tickers:
                st.caption("⚠ reports/watchlist.json 不存在或為空 — 尚無掃描資料")
            out["ibkr_scanner"] = scanner_tickers
        if st.checkbox("納入 IBKR 持倉", value=True, help="reports/reconciliation.json 的持有底層"):
            pos = _positions_tickers()
            if not pos:
                st.caption("⚠ reports/reconciliation.json 不存在或為空 — 尚無持倉資料")
            out["ibkr_positions"] = pos
        try:
            from scripts import ibkr_client
            if ibkr_client.available():
                if st.button("↻ 從 IBKR 即時更新持倉(唯讀)"):
                    with st.spinner("連線 IBKR Gateway(唯讀,約 10–15 秒)…"):
                        try:
                            rec = ibkr_client.reconcile()  # returns; does NOT persist
                        except Exception as e:  # noqa: BLE001
                            st.warning(f"IBKR 更新失敗:{e}")
                            rec = None
                    if rec is not None and not rec.get("reachable"):
                        st.warning("找不到可連線的 IBKR Gateway/TWS;請先開 Gateway 並啟用 API。")
                    elif rec is not None:
                        # reconcile() only returns — persist it ourselves so the
                        # rerun re-reads the FRESH holdings (else they'd be lost).
                        import json
                        try:
                            (_shared.REPORTS_DIR / "reconciliation.json").write_text(
                                json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
                        except Exception:  # noqa: BLE001
                            pass
                        _shared.load_reconciliation.clear()
                        _shared.load_json.clear()
                        st.toast("已更新 IBKR 持倉")
                        st.rerun()
            else:
                st.caption("ℹ️ 即時更新需本機 ib_async + Gateway;目前讀既有檔案(免連線)。"
                           "TWS 手動 watchlist 無 API、無法讀取。")
        except Exception:  # noqa: BLE001 — ibkr optional
            pass
    return out


# ── merge ─────────────────────────────────────────────────────────────────────
def _merge(tv_items: list[dict], src_lists: dict) -> dict:
    merged: dict[str, dict] = {}
    for it in tv_items:
        t = it["ticker"]
        row = merged.setdefault(t, {"ticker": t, "sources": [], "tv_symbol": it.get("tv_symbol") or t})
        if "tradingview" not in row["sources"]:
            row["sources"].append("tradingview")
    for src, tickers in src_lists.items():
        for t in tickers or []:
            t = str(t).upper().strip()
            if not t:
                continue
            row = merged.setdefault(t, {"ticker": t, "sources": [], "tv_symbol": t})
            if src not in row["sources"]:
                row["sources"].append(src)
    return merged


# ── render helpers ────────────────────────────────────────────────────────────
def _chips(row: dict) -> list[tuple]:
    out = [(_SOURCE_CHIP[s][0], _SOURCE_CHIP[s][1]) for s in row["sources"] if s in _SOURCE_CHIP]
    out += [(th, _shared.AMBER) for th in row.get("themes", [])]
    return out


def _row_html(row: dict) -> str:
    chips = "".join(_shared.chip(txt, col) for txt, col in _chips(row))
    bits = [b for b in (row.get("industry"),
                        f"${row['market_cap'] / 1e9:.0f}B" if row.get("market_cap") else None) if b]
    meta = f"<span style='color:{_shared.MUTED};font-size:.78rem'>· {' · '.join(bits)}</span>" if bits else ""
    return ("<div style='display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:3px 0'>"
            f"<span style='font-weight:700;font-family:ui-monospace,monospace;min-width:64px'>"
            f"{row['ticker']}</span>{chips}{meta}</div>")


def _render_summary(kept: dict, want_themes: bool) -> None:
    secs = {r["sector"] for r in kept.values() if r.get("sector")}
    by_src: dict[str, int] = defaultdict(int)
    for r in kept.values():
        for s in r["sources"]:
            by_src[s] += 1

    if want_themes:
        ai = sum(1 for r in kept.values() if "AI supercycle" in r.get("themes", []))
        cols = st.columns(4)
        _shared.metric_card(cols[0], "總代號", len(kept))
        _shared.metric_card(cols[1], "板塊數", len(secs))
        _shared.metric_card(cols[2], "主題: AI supercycle", ai)
    else:
        no_sector = sum(1 for r in kept.values() if not r.get("sector"))
        cols = st.columns(4)
        _shared.metric_card(cols[0], "總代號", len(kept))
        _shared.metric_card(cols[1], "板塊數", len(secs))
        _shared.metric_card(cols[2], "未分類", no_sector)

    # Fourth card: source breakdown as coloured chips instead of a truncated string.
    with cols[3]:
        with st.container(border=True):
            st.caption("來源明細")
            _shared.chips_row(
                [(f"{_SOURCE_CHIP[s][0]} {n}", _SOURCE_CHIP[s][1])
                 for s, n in by_src.items() if s in _SOURCE_CHIP]
            )


def _render_by_sector(kept: dict) -> None:
    buckets: dict[str, list] = defaultdict(list)
    for r in kept.values():
        buckets[r.get("sector") or _UNCLASSIFIED].append(r)
    first = True
    for name, rows in sorted(buckets.items(), key=lambda kv: (kv[0] == _UNCLASSIFIED, -len(kv[1]), kv[0])):
        if not first:
            st.divider()
        first = False
        st.markdown(f"#### {name} ({len(rows)})")
        for r in sorted(rows, key=lambda r: r["ticker"]):
            st.markdown(_row_html(r), unsafe_allow_html=True)


def _render_by_theme(kept: dict, taxonomy: dict) -> None:
    if not any(r.get("themes") for r in kept.values()):
        st.info("尚未分類主題。勾選上方「🏷 用 LLM 自動標主題」即可。")
        return
    buckets: dict[str, list] = defaultdict(list)
    for r in kept.values():
        ths = r.get("themes") or []
        if not ths:
            buckets[_NO_THEME].append(r)
        for th in ths:
            buckets[th].append(r)
    order = list(taxonomy.keys())

    def sort_k(name: str):
        if name == _NO_THEME:
            return (2, 0, name)
        return (0, order.index(name) if name in order else 1, name)

    first = True
    for name, rows in sorted(buckets.items(), key=lambda kv: sort_k(kv[0])):
        if not first:
            st.divider()
        first = False
        st.markdown(f"#### {name} ({len(rows)})")
        for r in sorted(rows, key=lambda r: r["ticker"]):
            st.markdown(_row_html(r), unsafe_allow_html=True)


def _render_export(kept: dict) -> None:
    buckets: dict[str, list] = defaultdict(list)
    for r in kept.values():
        buckets[r.get("sector") or _UNCLASSIFIED].append(r)
    lines = []
    for sector in sorted(buckets, key=lambda s: (s == _UNCLASSIFIED, s)):
        lines.append(f"###{sector},")
        lines += [r.get("tv_symbol") or r["ticker"] for r in sorted(buckets[sector], key=lambda r: r["ticker"])]
    st.download_button("⬇️ 匯出 TradingView 清單(依板塊分組 .txt)", "\n".join(lines) + "\n",
                       file_name="us_watchlist_by_sector.txt",
                       help="在 TradingView 的 Watchlist → Import list 匯入")


# ── page entry ────────────────────────────────────────────────────────────────
def render() -> None:
    st.header("🗂 自選股分類")
    st.caption("合併 TradingView 自選股 + IBKR 清單,依板塊/主題分類。唯讀、非投資建議。"
               "TradingView 無讀取 API → 清單由本機維護;最後可匯出分組版手動匯入回 TV。")

    taxonomy, taxonomy_available = _load_taxonomy()

    tv_items = _render_tv_input()
    src_lists = _render_ibkr_inputs()
    merged = _merge(tv_items, src_lists)
    if not merged:
        st.info("尚無代號。請在上方提供 TradingView 清單,或展開「IBKR 來源」並勾選來源。")
        return

    with st.spinner("補板塊資料中…(yfinance,首次較慢、之後快取)"):
        sectors = _sectors(tuple(sorted(merged)))

    # ── Filter controls — visually grouped ───────────────────────────────────
    with st.container(border=True):
        st.caption("重要性門檻(交易所無關;濾掉微型 / 低流動性)")
        fc1, fc2, fc3 = st.columns([1.2, 1.4, 1.4])
        apply_filter = fc1.toggle("啟用門檻", value=True)
        cap_min = fc2.number_input("市值下限 ($B)", min_value=0.0, value=2.0, step=0.5)
        dvol_min = fc3.number_input("日成交額下限 ($M)", min_value=0.0, value=20.0, step=5.0)

    kept, dropped = {}, []
    for t, row in merged.items():
        s = sectors.get(t) or {}
        row["sector"], row["industry"] = s.get("sector"), s.get("industry")
        row["market_cap"], row["dvol"], row["exchange"] = (
            s.get("market_cap"), s.get("avg_dollar_volume"), s.get("exchange"))
        if not apply_filter:
            kept[t] = row
        elif (row["market_cap"] or 0) >= cap_min * 1e9 and (row["dvol"] or 0) >= dvol_min * 1e6:
            kept[t] = row
        else:
            dropped.append(t)
    if apply_filter and dropped:
        shown = ", ".join(sorted(dropped)[:30])
        st.caption(f"🔻 未達門檻 / 資料不足,已濾 {len(dropped)} 檔:`{shown}`"
                   + ("…" if len(dropped) > 30 else ""))
    if not kept:
        st.warning("過濾後沒有達標的代號。可調低門檻或關閉「啟用門檻」。")
        return

    # ── LLM theme toggle + group-by radio — decide before seeing results ──────
    with st.container(border=True):
        if not taxonomy_available:
            st.warning("主題分類 API 暫時無法使用；板塊分類仍可正常使用。")
        want_themes = st.checkbox(
            "🏷 用 LLM 自動標主題(Codex 訂閱,首次約數十秒)", value=False,
            disabled=not taxonomy_available,
            help=("把每檔分到 content/themes.json 的主題(含 AI supercycle)。"
                  "Result cached 30 days by (tickers, themes); re-fires when cache expires or watchlist changes."))
        group_by = st.radio("分組方式", ["板塊", "主題"], horizontal=True)

    for row in kept.values():
        row.setdefault("themes", [])
    if want_themes:
        try:
            from scripts import theme_classify
            with st.spinner("LLM 主題分類中…"):
                tmap = theme_classify.classify_themes(list(kept), taxonomy, sectors)
            for t, row in kept.items():
                row["themes"] = tmap.get(t, [])
        except Exception as e:  # noqa: BLE001
            st.warning(f"主題分類暫不可用({type(e).__name__})— 需登入 Codex ChatGPT 訂閱;板塊分類不受影響。")

    _render_summary(kept, want_themes)
    st.divider()
    if group_by == "板塊":
        _render_by_sector(kept)
    else:
        _render_by_theme(kept, taxonomy)
    st.divider()
    _render_export(kept)
