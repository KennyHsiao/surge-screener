"""X 社群情緒/博主分析 — shared page, used by both 美股 and 幣圈.

Free-first social intelligence: free baseline first, paid X/Grok automation
explicitly marked as optional. The page reads reports/social_intelligence/latest.json
when present and falls back to reports/x_influencer_picks.json for compatibility.

Two tabs:
  1. 單帳號 / 關鍵字 — fetch one handle's or keyword's posts (X API) + Claude
     sentiment. Backend: scripts/x_analysis.py.
  2. 博主雷達 — roster-wide read of the followed influencers (content/influencers
     .json) via Grok x_search, extracting the tickers they're discussing into a
     candidate list. Backend: scripts/x_influencers.py (xAI dev API, local-only;
     see memory x-premium-grok-not-api). The picks also feed the cockpit quick-pick.

render(market) parameterizes labels/presets/roster for US vs CRYPTO.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from . import _shared
from . import influencers as influencers_mod

# Make repo-root `scripts` importable when run via `streamlit run app.py`.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_PICKS_PATH = _shared.REPORTS_DIR / "x_influencer_picks.json"
_SOCIAL_PATH = _shared.REPORTS_DIR / "social_intelligence" / "latest.json"

_PRESETS = {
    "US": {
        "label": "美股",
        "handles": ["DeItaone", "unusual_whales", "Stocktwits"],
        "keyword": "$NVDA",
    },
    "CRYPTO": {
        "label": "幣圈",
        "handles": ["WatcherGuru", "CryptoHayes", "documentingbtc"],
        "keyword": "$BTC",
    },
}


def render(market: str = "US") -> None:
    cfg = _PRESETS.get(market, _PRESETS["US"])
    st.header(f"🐦 X 社群情緒 — {cfg['label']}")
    _render_free_first_status(market)

    tab_single, tab_radar = st.tabs(["單帳號 / 關鍵字", "📡 博主雷達"])
    with tab_single:
        _render_single(market, cfg)
    with tab_radar:
        _render_radar(market)


def _render_free_first_status(market: str) -> None:
    from scripts import social_intelligence

    statuses = social_intelligence.source_statuses()
    with st.container(border=True):
        st.caption("Free-first social intelligence · reports/social_intelligence/latest.json")
        items = []
        for key in ("stocktwits", "apewisdom", "agent_reach", "xai_grok", "x_official_api"):
            src = statuses.get(key, {})
            status = src.get("status", "unknown")
            cost = src.get("cost_mode", "unknown")
            color = _shared.GREEN if status in {"available", "configured"} else _shared.MUTED
            if status == "degraded":
                color = _shared.AMBER
            items.append((f"{src.get('label', key)} · {cost} · {status}", color))
        _shared.chips_row(items)
        st.caption(
            "X/Grok subscription 可用於人工研究，但不能替代 XAI_API_KEY / X_BEARER_TOKEN；"
            "自動化 Grok 分析屬付費增強。"
        )

        manual_grok_prompt = (
            f"請用繁中分析 {market} 市場近 3 天被高品質 X/Agent Reach 來源提到的 ticker，"
            "判斷是否仍是 early signal，或已被 StockTwits/ApeWisdom 擠成 crowded trade；"
            "每個 ticker 請列引用、敘事、反證、需要平台驗證的因子。"
        )
        with st.expander("複製到 Grok 的研究 prompt", expanded=False):
            st.code(manual_grok_prompt, language="text")

        with st.expander("Agent Reach 狀態 / Cookie 更新指引", expanded=False):
            from scripts import agent_reach_auth

            cfg_status = agent_reach_auth.agent_reach_config_status()
            cfg_color = _shared.GREEN if cfg_status.get("configured") else _shared.AMBER
            _shared.chips_row([
                (
                    "Agent Reach Cookie "
                    + ("configured" if cfg_status.get("configured") else "missing"),
                    cfg_color,
                )
            ])
            st.markdown(
                "**X 登入 / 更新 Agent Reach Cookie**\n\n"
                "平台會在測試機開 dedicated browser/session 到 X 登入頁；"
                "登入完成後，只會寫入 `auth_token` / `ct0` 到測試機 Agent Reach config："
                "`/home/kenny/.agent-reach/config.yaml`。"
            )
            st.markdown(
                "1. 按「開啟測試機 X 登入視窗」。\n"
                "2. 在 noVNC / 測試機桌面完成 X 登入。\n"
                "3. 回平台按「登入完成，更新 Agent Reach Cookie」。\n"
                "4. 之後 Agent Reach bridge 會自動讀 config，不需要手動填 token。"
            )
            if cfg_status.get("configured"):
                st.caption(
                    "目前 config 內已有遮蔽後的 cookie："
                    f"auth_token={cfg_status.get('auth_token') or '—'} · "
                    f"ct0={cfg_status.get('ct0') or '—'}"
                )

            c_start, c_update, c_status = st.columns([1, 1, 1])
            if c_start.button("開啟測試機 X 登入視窗", type="primary", key="agent_reach_x_login_start"):
                with st.spinner("正在啟動測試機 dedicated browser/session…"):
                    result = agent_reach_auth.start_login_session()
                if result.get("status") == "running":
                    st.success("X 登入視窗已在測試機桌面開啟；請在 noVNC 內完成登入。")
                    st.caption(
                        f"CDP port: {result.get('port')} · profile: {result.get('profile_dir')}"
                    )
                else:
                    st.warning(result.get("note") or "無法啟動測試機 X 登入視窗。")

            if c_update.button(
                "登入完成，更新 Agent Reach Cookie",
                key="agent_reach_x_login_update",
            ):
                with st.spinner("正在從 dedicated browser/session 讀取 X cookie…"):
                    result = agent_reach_auth.update_config_from_running_session()
                if result.get("status") == "updated":
                    st.success("Agent Reach Cookie 已更新。")
                    st.caption(
                        f"auth_token={result.get('auth_token')} · ct0={result.get('ct0')}"
                    )
                else:
                    st.warning(result.get("note") or "尚未讀到 X 登入 cookie。")

            if c_status.button("檢查 Agent Reach Cookie 狀態", key="agent_reach_x_login_status"):
                latest = agent_reach_auth.agent_reach_config_status()
                if latest.get("configured"):
                    st.success(
                        "Agent Reach config 已設定；"
                        f"auth_token={latest.get('auth_token')} · ct0={latest.get('ct0')}"
                    )
                else:
                    st.warning("Agent Reach config 尚未包含 X cookie。")
            st.caption(
                "不顯示 auth_token / ct0 明文；不要把 cookie 貼到 repo、issue、chat log。"
                "Cookie 過期時重跑這個登入/更新流程即可。"
            )

        with st.expander("付費增強 / 下次優化", expanded=False):
            st.markdown(
                "- xAI API (`XAI_API_KEY`): 自動 Grok x_search 與引用。\n"
                "- X official API (`X_BEARER_TOKEN`): 原始貼文查詢與完整 mention 補強。\n"
                "- 完整 X mention count: 付費 optional，不作為免費核心成功條件。"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Tab 1 — single handle / keyword (existing X-API + Claude flow)
# ─────────────────────────────────────────────────────────────────────────────
def _render_single(market: str, cfg: dict) -> None:
    from scripts import x_analysis  # lazy so the page loads even if import fails

    status = x_analysis.get_status()
    if not status["x_token"]:
        st.warning("尚未設定 `X_BEARER_TOKEN`:可瀏覽/選擇下方清單,但**抓取與分析**需設定後才能使用。")
    elif not status["anthropic"]:
        st.info("未設定 `ANTHROPIC_API_KEY`:可抓貼文,但不會做 LLM 情緒分析。")

    # ── Query panel: controls grouped together, not scattered full-width ──────
    with st.container(border=True):
        st.caption("查詢設定")
        col_mode, col_limit, col_target = st.columns([1, 1, 2])
        with col_mode:
            mode = st.radio("分析模式", ["博主帳號", "關鍵字/代號"], horizontal=False)
        with col_limit:
            limit = st.slider("抓取貼文數", 5, 50, 20, step=5)
        with col_target:
            if mode == "博主帳號":
                roster = influencers_mod.for_market(market)
                if roster:
                    labels = [f"{i.get('category', '?')} · @{i['handle']}"
                              + (f" — {i['name']}" if i.get('name') else "")
                              for i in roster] + ["➕ 自訂輸入"]
                    pick = st.selectbox("選擇博主(來自關注清單)", labels)
                    if pick == "➕ 自訂輸入":
                        handle = st.text_input("X 帳號(不含 @)", value="").strip()
                    else:
                        handle = roster[labels.index(pick)]["handle"]
                else:
                    handle = st.text_input(
                        "X 帳號(不含 @)", value=cfg["handles"][0],
                        help=f"建議:{', '.join('@' + h for h in cfg['handles'])}",
                    ).strip()
                target, context = handle, f"@{handle}"
            else:
                kw = st.text_input("關鍵字 / 代號", value=cfg["keyword"])
                target, context = kw, kw

        _btn_pad, col_btn = st.columns([3, 1])
        with col_btn:
            run = st.button(
                "分析", type="primary", disabled=not status["x_token"],
                help=None if status["x_token"] else "需設定 X_BEARER_TOKEN",
                use_container_width=True,
            )

    # ── Placeholder skeleton shown before first run ───────────────────────────
    if not run:
        with st.container(border=True):
            ph1, ph2 = st.columns([1, 2])
            with ph1:
                st.metric("整體情緒", "—", help="執行分析後顯示")
            with ph2:
                _shared.chips_row([("bullish", _shared.MUTED), ("neutral", _shared.MUTED),
                                   ("bearish", _shared.MUTED)])
            st.caption("分析完成後將在此顯示結果")
        return

    try:
        with st.spinner("抓取貼文中…"):
            if mode == "博主帳號":
                posts = x_analysis.fetch_user_posts(target, limit=limit)
            else:
                posts = x_analysis.fetch_keyword_posts(target, limit=limit)
    except x_analysis.XApiError as e:
        st.error(str(e))
        return

    if not posts:
        st.info("沒有抓到貼文。")
        return

    with st.spinner("分析情緒中…"):
        result = x_analysis.analyze(posts, context=context)

    if result.get("llm"):
        sentiment = result.get("overall_sentiment", "?")
        # coerce — sentiment_score is LLM-authored and may be a string/null
        try:
            score = float(result.get("sentiment_score"))
        except (TypeError, ValueError):
            score = None
        icon = {"bullish": "🟢", "bearish": "🔴", "neutral": "🟡"}.get(sentiment, "⚪")
        c1, c2 = st.columns([1, 2])
        with c1:
            st.metric("整體情緒", f"{icon} {sentiment}",
                      delta=f"{score:+.2f}" if isinstance(score, (int, float)) else None)
        with c2:
            if result.get("summary"):
                st.markdown(f"**重點:** {result['summary']}")

        themes = result.get("key_themes", [])
        if themes:
            st.markdown("**主題:** " + " ".join(f"`{t}`" for t in themes))

        if result.get("stance"):
            st.info(f"📌 該帳號近期傾向:{result['stance']}")

        highlights = result.get("highlights", [])
        if highlights:
            st.markdown("**代表貼文**")
            for h in highlights:
                st.markdown(f"- 「{h.get('text', '')}」 — *{h.get('why', '')}*")
    else:
        st.caption(result.get("note", ""))
        if result.get("raw"):
            st.code(result["raw"])

    with st.expander(f"原始貼文 ({len(posts)})"):
        for p in posts:
            meta = f"{p.get('created_at', '')} · ♥{p.get('likes', 0)} ↻{p.get('retweets', 0)}"
            st.markdown(f"**{p.get('author', '')}** · {meta}\n\n{p.get('text', '')}")
            st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# Tab 2 — 博主雷達: roster-wide influencer → ticker candidate radar
# ─────────────────────────────────────────────────────────────────────────────
_SKEW_ICON = {"bullish": "🟢 偏多", "bearish": "🔴 偏空",
              "mixed": "🟡 分歧", "neutral": "⚪ 中性"}


def _render_radar(market: str) -> None:
    st.caption("對「關注博主」整份清單跑 Grok x_search,萃取他們近期在談的 ticker → "
               "候選清單(也會餵進期權作戰台快選)。唯讀、自帶 citations、本機限定。")

    _render_radar_refresh(market)

    social = _shared.load_json(str(_SOCIAL_PATH))
    picks = _social_snapshot_to_legacy_picks(social) if social else None
    if not picks:
        picks = _shared.load_json(str(_PICKS_PATH))
    if not picks:
        st.info("尚無博主候選資料。請在本機(設好 `XAI_API_KEY`)跑:\n\n"
                f"```bash\npython scripts/social_intelligence.py --market {market}\n```")
        return

    # tolerate partial/hand-edited files: coerce null lists to [], skip non-dicts,
    # and only keep ticker rows that actually have a symbol.
    tickers = [t for t in (picks.get("tickers") or [])
               if isinstance(t, dict) and t.get("symbol")]
    st.caption(f"視窗 {picks.get('window', '?')} · 產生於 {picks.get('generated_at', '?')} "
               f"· 市場 {picks.get('market') or '?'} · {len(tickers)} 檔候選")

    if tickers:
        df = pd.DataFrame([{
            "代號": t.get("symbol"),
            "幾人提": t.get("count", 0),
            "傾向": _SKEW_ICON.get(t.get("skew"), t.get("skew") or "—"),
            "信心": t.get("conviction") or "—",
            "提及博主": ", ".join("@" + str(h) for h in (t.get("mentioned_by") or [])),
            "備註": t.get("note", ""),
        } for t in tickers])
        st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        st.caption("這次分析沒有萃取到任何 ticker(博主近期未談個股)。")

    by_infl = [e for e in (picks.get("by_influencer") or []) if isinstance(e, dict)]
    if by_infl:
        st.markdown("**各博主重點**")
        for e in by_infl:
            active = e.get("active", True)
            head = (f"@{e.get('handle', '?')} · "
                    f"{'🟢 有發文' if active else '⚪ 視窗內無相關'} · "
                    f"{e.get('substance_vs_hype', '')}")
            with st.expander(head, expanded=False):
                if e.get("summary"):
                    st.markdown(e["summary"])
                for tk in (e.get("tickers") or []):
                    if not isinstance(tk, dict):
                        continue
                    st.markdown(f"- **{tk.get('symbol')}** "
                                f"{_SKEW_ICON.get(tk.get('stance'), tk.get('stance') or '')} "
                                f"({tk.get('conviction') or '—'}) — {tk.get('note', '')}")
                for c in (e.get("citations") or [])[:5]:
                    st.caption(f"🔗 {c}")

    cites = picks.get("citations") or []
    if cites:
        with st.expander(f"全部 citations ({len(cites)})"):
            for c in cites[:30]:
                st.caption(f"- {c}")


def _social_snapshot_to_legacy_picks(snapshot: dict | None) -> dict | None:
    if not isinstance(snapshot, dict):
        return None
    rows = []
    for row in (snapshot.get("tickers") or []):
        if not isinstance(row, dict):
            continue
        labels = row.get("labels") if isinstance(row.get("labels"), dict) else {}
        badges = []
        for key, label in (
            ("x_mentioned", "X Mentioned"),
            ("agent_reach", "Agent Reach"),
            ("retail_heat", "Retail Heat"),
            ("crowded", "Crowded"),
            ("early_signal", "Early Signal"),
            ("paid_data_needed", "Paid Data Needed"),
        ):
            if labels.get(key):
                badges.append(label)
        rows.append({
            "symbol": row.get("ticker"),
            "mentioned_by": row.get("mentioned_by") or [],
            "count": len(row.get("mentioned_by") or []),
            "skew": row.get("skew") or "neutral",
            "conviction": row.get("conviction"),
            "note": " / ".join(badges) or row.get("note") or "",
        })
    citations = []
    for row in snapshot.get("tickers", []):
        if not isinstance(row, dict):
            continue
        citations.extend(c for c in (row.get("citations") or []) if c)
    return {
        "source": "social_intelligence",
        "market": snapshot.get("market"),
        "window": snapshot.get("as_of_date"),
        "generated_at": snapshot.get("generated_at"),
        "tickers": rows,
        "by_influencer": [],
        "citations": sorted({str(c) for c in citations}),
    }


def _render_radar_refresh(market: str) -> None:
    """Live re-run of the roster analysis. Local-only, read-only, never crashes."""
    from scripts import x_influencers as xi  # lazy

    import os
    if not os.environ.get("XAI_API_KEY"):
        st.button("↻ 重新分析博主", disabled=True, key=f"radar_refresh_{market}",
                  help="需要 xAI 開發者金鑰 XAI_API_KEY(與 X Premium 無關,"
                       "console.x.ai 另開,新帳號 ~$25 額度)。")
        return

    days = st.slider("回看天數", 1, 14, 3, key=f"radar_days_{market}")
    if not st.button("↻ 重新分析博主", type="primary", key=f"radar_refresh_{market}"):
        return
    rows = xi.load_handles(market=market)
    if not rows:
        st.warning(f"content/influencers.json 沒有 {market} 市場的博主。")
        return
    handles = [r["handle"] for r in rows][:xi.MAX_HANDLES]
    to_d, from_d = date.today().isoformat(), (date.today() - timedelta(days=days)).isoformat()
    with st.spinner(f"Grok 分析 {len(handles)} 位博主中(x_search,唯讀)…"):
        try:
            res = xi.analyze(handles, from_d, to_d, os.environ["XAI_API_KEY"])
        except Exception as e:  # defensive: never crash the page
            st.error(f"分析失敗:{e}")
            return
    if res.get("error") or res.get("parsed") is None:
        st.warning(f"分析未成功:{res.get('error') or '無法解析回應'}")
        return
    picks = xi.build_picks(res["parsed"], handles, f"{from_d}..{to_d}", market)
    from datetime import datetime, timezone
    picks["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    picks["citations"] = res.get("citations", [])
    try:
        _PICKS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _PICKS_PATH.write_text(__import__("json").dumps(picks, ensure_ascii=False, indent=2),
                               encoding="utf-8")
    except Exception:
        pass
    _shared.load_json.clear()
    st.success(f"完成,萃取 {len(picks['tickers'])} 檔候選。")
    st.rerun()
