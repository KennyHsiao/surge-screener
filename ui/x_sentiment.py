"""X 社群情緒/博主分析 — shared page, used by both 美股 and 幣圈.

Free-first social intelligence: free baseline first, with optional Codex
subscription web research. The page reads
reports/social_intelligence/latest.json when present and falls back to
reports/x_influencer_picks.json for compatibility.

Two views:
  1. 單帳號 / 關鍵字 — fetch one handle's posts via X API or Agent Reach
     fallback; keyword search still uses X API until Agent Reach search is wired.
     Sentiment uses scripts/x_analysis.py.
  2. 博主雷達 — roster-wide read of the followed influencers (content/influencers
     .json) via free-first social_intelligence snapshots. Optional Codex web
     research uses the same ChatGPT subscription as every other LLM feature.
     The picks also feed the cockpit quick-pick.
     The radar view auto-runs once per session and groups results into tabs.

render(market) parameterizes labels/presets/roster for US vs CRYPTO.
"""

import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from . import _shared
from . import _read_api
from . import influencers as influencers_mod

# Make repo-root `scripts` importable when run via `streamlit run app.py`.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_PICKS_PATH = _shared.REPORTS_DIR / "x_influencer_picks.json"
_SOCIAL_PATH = _shared.REPORTS_DIR / "social_intelligence" / "latest.json"
_SOCIAL_AI_AUTH_SESSION_KEY = "social_ai_summary_codex_auth_login"
_SOCIAL_RADAR_AUTO_RUN_KEY = "social_radar_auto_run"
_SOCIAL_AI_AUTO_SUMMARY_KEY = "social_ai_auto_summary"


_LOGIN_URL_RE = re.compile(r"https://[^\s\x1b]+")


@dataclass(frozen=True, slots=True)
class SocialSnapshotState:
    status: str
    snapshot: dict | None
    reason: str | None = None


def _ranked_candidates_seed() -> dict | None:
    """Convert the strict ranked feed into the refresh producer's input shape."""

    result = _read_api.load_ranked_candidates()
    if not isinstance(result, _read_api.RankedCandidatesApiAvailable):
        return None
    return {
        "ranked_candidates": [
            candidate.model_dump(mode="json")
            for candidate in result.feed.candidates
        ]
    }


def _social_snapshot_state(market: str) -> SocialSnapshotState:
    """Select one persisted API snapshot for the requested page market."""

    result = _read_api.load_social_intelligence()
    if isinstance(result, _read_api.SocialIntelligenceApiAvailable):
        snapshot = result.snapshot.model_dump(mode="json")
        if result.snapshot.market != market:
            return SocialSnapshotState("api_other_market", None)
        return SocialSnapshotState("api_available", snapshot)
    if isinstance(result, _read_api.SocialIntelligenceApiUnavailable):
        return SocialSnapshotState("api_unavailable", None, result.reason)
    return SocialSnapshotState("api_failure", None, result.reason)

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

    view = st.radio("檢視模式", ["單帳號 / 關鍵字", "📡 博主雷達"],
                    horizontal=True, key=f"x_sentiment_view_{market}")
    if view == "📡 博主雷達":
        _render_radar(market)
    else:
        _render_single(market, cfg)


def _render_free_first_status(market: str) -> None:
    from scripts import social_intelligence

    statuses = social_intelligence.source_statuses()
    with st.container(border=True):
        st.caption("Free-first social intelligence · reports/social_intelligence/latest.json")
        items = []
        for key in (
            "stocktwits",
            "apewisdom",
            "agent_reach",
            "codex_web_research",
            "x_official_api",
        ):
            src = statuses.get(key, {})
            status = src.get("status", "unknown")
            cost = src.get("cost_mode", "unknown")
            color = _shared.GREEN if status in {"available", "configured"} else _shared.MUTED
            if status == "degraded":
                color = _shared.AMBER
            items.append((f"{src.get('label', key)} · {cost} · {status}", color))
        _shared.chips_row(items)
        st.caption(
            "博主研究的 LLM 一律走 Codex SDK / ChatGPT 訂閱；"
            "X_BEARER_TOKEN 只用於選配的 X 原始貼文資料。"
        )

        manual_codex_prompt = (
            f"請用繁中分析 {market} 市場近 3 天被高品質 X/Agent Reach 來源提到的 ticker，"
            "判斷是否仍是 early signal，或已被 StockTwits/ApeWisdom 擠成 crowded trade；"
            "每個 ticker 請列引用、敘事、反證、需要平台驗證的因子。"
        )
        with st.expander("Codex 研究 prompt", expanded=False):
            st.code(manual_codex_prompt, language="text")

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
                "- Codex SDK: 使用 ChatGPT 訂閱做博主 web research 與引用。\n"
                "- X official API (`X_BEARER_TOKEN`): 原始貼文查詢與完整 mention 補強。\n"
                "- 完整 X mention count: 付費 optional，不作為免費核心成功條件。"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Tab 1 — single handle / keyword (X official API, with Agent Reach handle fallback)
# ─────────────────────────────────────────────────────────────────────────────
def _fetch_agent_reach_posts_or_raise(
    handle: str,
    limit: int,
    *,
    official_error: str = "",
) -> tuple[list[dict], str]:
    from scripts import agent_reach_social_bridge as bridge
    from scripts import x_analysis

    runtime_env = os.environ
    payload = bridge.fetch_user_posts_payload(
        handle,
        credentials=bridge.load_credentials(env=runtime_env),
        twitter_bin=bridge.resolve_twitter_bin(env=runtime_env),
        env=runtime_env,
        limit=limit,
        timeout=10,
    )
    posts = payload.get("posts") if isinstance(payload, dict) else []
    if isinstance(posts, list) and payload.get("status") == "available" and posts:
        return posts, "Agent Reach"

    note = str(payload.get("note") or "Agent Reach returned no posts") if isinstance(payload, dict) else ""
    auth_status = str(payload.get("auth_status") or "") if isinstance(payload, dict) else ""
    tool_status = str(payload.get("tool_status") or "") if isinstance(payload, dict) else ""
    details = " · ".join(
        x for x in [
            note,
            f"auth={auth_status}" if auth_status else "",
            f"tool={tool_status}" if tool_status else "",
        ]
        if x
    )
    if official_error:
        details = f"{official_error} / Agent Reach fallback failed: {details}"
    raise x_analysis.XApiError(details or "Agent Reach fallback failed")


def _compact_text(text: str, limit: int = 220) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: max(limit - 1, 0)].rstrip() + "…"


def _raw_post_label(post: dict, index: int) -> str:
    author = str(post.get("author") or "").strip() or "unknown"
    created = str(post.get("created_at") or "").strip()[:19]
    preview = _compact_text(str(post.get("text") or ""), 72)
    return f"{index:02d} · {author}" + (f" · {created}" if created else "") + f" · {preview}"


def _render_raw_posts(posts: list[dict]) -> None:
    with st.expander(f"原始貼文 ({len(posts)})", expanded=False):
        if not posts:
            st.caption("沒有原始貼文。")
            return

        rows = []
        for idx, post in enumerate(posts, start=1):
            url = str(post.get("url") or "").strip()
            rows.append({
                "#": idx,
                "時間": str(post.get("created_at") or "")[:19],
                "作者": post.get("author") or "",
                "互動": f"♥{post.get('likes', 0)} ↻{post.get('retweets', 0)}",
                "內文預覽": _compact_text(str(post.get("text") or ""), 180),
                "連結": url,
            })
        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            use_container_width=True,
            height=min(360, 80 + 35 * len(rows)),
        )

        labels = [_raw_post_label(post, idx) for idx, post in enumerate(posts, start=1)]
        selected_label = st.selectbox("查看全文", labels, key="x_raw_post_detail")
        selected = posts[labels.index(selected_label)]
        meta = (
            f"{selected.get('author') or ''} · {selected.get('created_at') or ''} · "
            f"♥{selected.get('likes', 0)} ↻{selected.get('retweets', 0)}"
        ).strip(" ·")
        st.caption(meta)
        st.text_area(
            "完整內文",
            value=str(selected.get("text") or ""),
            height=140,
            disabled=True,
            key="x_raw_post_text",
        )
        url = str(selected.get("url") or "").strip()
        if url:
            st.markdown(f"[開啟原文]({url})")


def _render_single(market: str, cfg: dict) -> None:
    from scripts import x_analysis  # lazy so the page loads even if import fails
    from scripts import social_intelligence

    status = x_analysis.get_status()
    sources = social_intelligence.source_statuses()
    agent_status = sources.get("agent_reach", {})
    agent_can_try = agent_status.get("status") in {"available", "configured", "degraded"}
    if not status["x_token"]:
        if agent_can_try:
            st.info(
                "尚未設定 `X_BEARER_TOKEN`:單一博主帳號會改用 Agent Reach；"
                "關鍵字/全網搜尋仍需 X official API 或後續接 `twitter search`。"
            )
        else:
            st.warning(
                "尚未設定 `X_BEARER_TOKEN`,且 Agent Reach 尚不可用:可瀏覽/選擇下方清單,"
                "但抓取貼文需先完成 Agent Reach cookie/CLI 設定或設定 X official API。"
            )
    elif not status["codex"]:
        st.info("Codex ChatGPT 訂閱登入不可用:可抓貼文,但不會做 LLM 情緒分析。")

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
                roster = influencers_mod.for_market(market, api_only=True)
                if not getattr(roster, "available", True):
                    st.caption("關注博主 API 暫時無法使用；仍可手動輸入帳號。")
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
            can_run = status["x_token"] or (mode == "博主帳號" and agent_can_try)
            if status["x_token"]:
                run_help = None
            elif mode == "博主帳號" and agent_can_try:
                run_help = "使用 Agent Reach user-posts fallback"
            elif mode == "博主帳號":
                run_help = "需設定 Agent Reach cookie/CLI 或 X_BEARER_TOKEN"
            else:
                run_help = "關鍵字/全網搜尋目前需 X_BEARER_TOKEN"
            run = st.button(
                "分析", type="primary", disabled=not can_run,
                help=run_help,
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
                source_label = "X official API"
                if status["x_token"]:
                    try:
                        posts = x_analysis.fetch_user_posts(target, limit=limit)
                    except x_analysis.XApiError as official_error:
                        posts, source_label = _fetch_agent_reach_posts_or_raise(
                            target,
                            limit,
                            official_error=str(official_error),
                        )
                else:
                    posts, source_label = _fetch_agent_reach_posts_or_raise(target, limit)
            else:
                source_label = "X official API"
                posts = x_analysis.fetch_keyword_posts(target, limit=limit)
    except x_analysis.XApiError as e:
        st.error(str(e))
        return

    if not posts:
        st.info("沒有抓到貼文。")
        return

    st.caption(f"資料來源: {source_label}")
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

    _render_raw_posts(posts)


# ─────────────────────────────────────────────────────────────────────────────
# Tab 2 — 博主雷達: roster-wide influencer → ticker candidate radar
# ─────────────────────────────────────────────────────────────────────────────
_SKEW_ICON = {"bullish": "🟢 偏多", "bearish": "🔴 偏空",
              "mixed": "🟡 分歧", "neutral": "⚪ 中性"}


def _read_text(path: str | Path | None) -> str:
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _login_url_from_text(text: str) -> str | None:
    match = _LOGIN_URL_RE.search(text or "")
    if not match:
        return None
    return match.group(0).rstrip(")>.,")


def _login_url_from_path(path: str | Path | None) -> str | None:
    return _login_url_from_text(_read_text(path))


def _wait_for_login_url(path: str | Path | None, timeout: float = 3.0) -> str | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        url = _login_url_from_path(path)
        if url:
            return url
        time.sleep(0.25)
    return _login_url_from_path(path)


def _render_social_ai_codex_auth_status(meta: dict | None = None) -> bool:
    from scripts import codex_auth_flow

    auth = codex_auth_flow.refresh_status()
    ok = bool(auth.get("ok"))
    state = str(auth.get("state") or "unknown")
    log_path = (meta or {}).get("log_path") or auth.get("log_path") or str(codex_auth_flow.AUTH_LOG_PATH)
    prompt = codex_auth_flow.read_login_prompt()

    with st.container(border=True):
        st.markdown("##### Codex 登入" if not ok else "##### Codex 認證")
        _shared.chips_row([(
            "Codex 已登入" if ok else "Codex 尚未登入",
            _shared.GREEN if ok else _shared.AMBER,
        )])
        if ok:
            st.success("Codex 已透過 ChatGPT 訂閱登入，可以產生博主雷達 AI 摘要。")
        elif state == "missing_cli":
            st.error("Codex SDK/CLI 尚未安裝，登入暫時無法使用。")
        else:
            st.info("需要登入 Codex ChatGPT 訂閱才能產生 AI 摘要；候選清單不受影響。")
            url = (
                auth.get("auth_url")
                or (meta or {}).get("auth_url")
                or prompt.get("auth_url")
                or _login_url_from_path(log_path)
            )
            if url:
                st.link_button("前往 Codex 登入", url, type="primary",
                               use_container_width=True)
            else:
                st.caption("正在準備登入連結，請稍候幾秒後重新整理。")
            user_code = (
                auth.get("user_code")
                or (meta or {}).get("user_code")
                or prompt.get("user_code")
            )
            if user_code:
                st.caption(f"一次性代碼：`{user_code}`")
            st.caption("在登入頁輸入代碼；完成後回到這頁再按一次「產生 AI 摘要」。")
    return ok


def _ensure_social_ai_codex_auth(*, render: bool = True) -> bool:
    from scripts import codex_auth_flow

    auth = codex_auth_flow.refresh_status()
    if auth.get("ok"):
        return True

    meta = st.session_state.get(_SOCIAL_AI_AUTH_SESSION_KEY)
    if not isinstance(meta, dict) or meta.get("state") != "login_started":
        meta = codex_auth_flow.start_login()
        st.session_state[_SOCIAL_AI_AUTH_SESSION_KEY] = meta
        _wait_for_login_url(meta.get("log_path"))
    if render:
        _render_social_ai_codex_auth_status(meta)
    return False


def _render_ai_summary_payload(summary: dict) -> None:
    headline = str(summary.get("headline") or "AI 摘要").strip()
    st.markdown(f"**{headline}**")

    takeaways = [str(x) for x in (summary.get("takeaways") or []) if x]
    if takeaways:
        st.markdown("**重點**")
        for item in takeaways:
            st.markdown(f"- {item}")

    candidates = [c for c in (summary.get("candidates") or []) if isinstance(c, dict)]
    if candidates:
        rows = [{
            "代號": c.get("ticker"),
            "優先級": c.get("priority") or "watch",
            "傾向": _SKEW_ICON.get(c.get("stance"), c.get("stance") or "neutral"),
            "摘要": c.get("summary") or "",
            "主要風險": c.get("key_risk") or "",
        } for c in candidates]
        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            use_container_width=True,
            height=min(360, 80 + 38 * len(rows)),
        )

    risks = [str(x) for x in (summary.get("risks") or []) if x]
    next_steps = [str(x) for x in (summary.get("next_steps") or []) if x]
    if risks or next_steps:
        cols = st.columns(2)
        with cols[0]:
            st.markdown("**風險**")
            for item in risks or ["—"]:
                st.markdown(f"- {item}")
        with cols[1]:
            st.markdown("**下一步**")
            for item in next_steps or ["—"]:
                st.markdown(f"- {item}")

    st.caption(
        f"摘要時間 {summary.get('generated_at') or '?'} · "
        f"對應快照 {summary.get('snapshot_generated_at') or '?'} · "
        f"model {summary.get('model') or '?'}"
    )


def _render_ai_summary_body(summary: dict | None, snapshot: dict, market: str) -> None:
    from scripts import social_intelligence_summary

    digest = social_intelligence_summary.snapshot_digest(snapshot)
    if isinstance(summary, dict) and summary.get("snapshot_digest") == digest:
        _render_ai_summary_payload(summary)
    elif isinstance(summary, dict):
        st.caption("目前已有 AI 摘要，但它對應的是舊快照；可重新產生以配合這次清單。")
    else:
        st.caption("AI 摘要是第二層整理：候選清單先保留原樣，需要時再讓 Codex 做濃縮。")

    meta = st.session_state.get(_SOCIAL_AI_AUTH_SESSION_KEY)
    auth_panel_rendered = isinstance(meta, dict)
    if isinstance(meta, dict):
        _render_social_ai_codex_auth_status(meta)

    if not st.button("產生 AI 摘要", key=f"social_ai_summary_generate_{market}"):
        return
    if not _ensure_social_ai_codex_auth(render=not auth_panel_rendered):
        return

    with st.spinner("正在根據博主雷達快照產生 AI 摘要…"):
        try:
            payload = social_intelligence_summary.generate_ai_summary(snapshot)
            path = social_intelligence_summary.write_ai_summary(
                payload,
                reports_dir=_shared.REPORTS_DIR,
                market=market,
            )
        except Exception as e:  # noqa: BLE001
            st.error(f"AI 摘要產生失敗:{type(e).__name__}: {e}")
            return
    _shared.load_json.clear()
    st.session_state.pop(_SOCIAL_AI_AUTH_SESSION_KEY, None)
    st.success(f"AI 摘要已儲存:{path}")
    st.rerun()


def _render_ticker_list_tab(picks: dict, tickers: list[dict]) -> None:
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


def _render_citations_tab(cites: list) -> None:
    rows = [{"#": idx, "引用": str(c)} for idx, c in enumerate(cites, start=1) if c]
    if not rows:
        st.caption("這次快照沒有 citations。")
        return
    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        use_container_width=True,
        height=min(520, 80 + 36 * len(rows)),
    )


def _auto_state_bucket(key: str) -> dict:
    bucket = st.session_state.get(key)
    if not isinstance(bucket, dict):
        bucket = {}
        st.session_state[key] = bucket
    return bucket


def _maybe_auto_refresh_radar(market: str) -> dict | None:
    bucket = _auto_state_bucket(_SOCIAL_RADAR_AUTO_RUN_KEY)
    if bucket.get(market):
        return None

    bucket[market] = {"status": "running"}
    with st.spinner("自動更新 free-first 社群快照…"):
        try:
            snapshot, paths = _write_free_first_snapshot_from_ui(market)
        except Exception as e:  # noqa: BLE001
            bucket[market] = {"status": "error", "message": str(e)}
            st.warning(f"自動更新 free-first 社群快照失敗:{e}")
            return None

    _shared.load_json.clear()
    agent_status = (snapshot.get("source_statuses") or {}).get("agent_reach", {})
    count = len(snapshot.get("tickers") or [])
    bucket[market] = {
        "status": "done",
        "generated_at": snapshot.get("generated_at"),
        "count": count,
    }
    if agent_status.get("status") == "available":
        st.success(f"自動更新 free-first 社群快照完成,產生 {count} 檔候選。")
    else:
        st.warning(
            "自動更新 free-first 社群快照完成,但 Agent Reach 未完整可用:"
            f"{agent_status.get('note') or agent_status.get('status') or 'unknown'}"
        )
    st.caption(
        f"latest: {paths.get('latest_path')} · legacy quick-pick: {paths.get('legacy_path')}"
    )
    return snapshot


def _maybe_auto_generate_ai_summary(snapshot: dict, market: str) -> dict | None:
    from scripts import social_intelligence_summary

    digest = social_intelligence_summary.snapshot_digest(snapshot)
    summary = social_intelligence_summary.load_ai_summary(
        reports_dir=_shared.REPORTS_DIR,
        market=market,
    )
    if isinstance(summary, dict) and summary.get("snapshot_digest") == digest:
        return summary

    bucket = _auto_state_bucket(_SOCIAL_AI_AUTO_SUMMARY_KEY)
    state = bucket.get(market)
    if (
        isinstance(state, dict)
        and state.get("digest") == digest
        and state.get("status") in {"done", "error"}
    ):
        return summary if isinstance(summary, dict) else None

    if not _ensure_social_ai_codex_auth(render=False):
        bucket[market] = {"status": "auth_pending", "digest": digest}
        return summary if isinstance(summary, dict) else None

    bucket[market] = {"status": "running", "digest": digest}
    with st.spinner("自動產生 AI 摘要…"):
        try:
            payload = social_intelligence_summary.generate_ai_summary(snapshot)
            social_intelligence_summary.write_ai_summary(
                payload,
                reports_dir=_shared.REPORTS_DIR,
                market=market,
            )
        except Exception as e:  # noqa: BLE001
            bucket[market] = {"status": "error", "digest": digest, "message": str(e)}
            st.warning(f"自動產生 AI 摘要失敗:{type(e).__name__}: {e}")
            return summary if isinstance(summary, dict) else None

    _shared.load_json.clear()
    bucket[market] = {"status": "done", "digest": digest}
    st.success("自動產生 AI 摘要完成。")
    return payload


def _render_radar(market: str) -> None:
    st.caption(
        "對「關注博主」整份清單用 Agent Reach 抓最近 posts,萃取近期在談的 ticker → "
        "free-first 社群候選清單(也會餵進期權作戰台快選)。LLM stance 分析可作下一層付費/本機增強。"
    )

    auto_snapshot = _maybe_auto_refresh_radar(market)
    _render_radar_refresh(market)

    if isinstance(auto_snapshot, dict):
        social = auto_snapshot
    else:
        social_state = _social_snapshot_state(market)
        social = social_state.snapshot
        if social_state.status == "api_other_market":
            st.caption("最新社群快照屬於其他市場;目前頁面改用相容候選資料。")
        elif social_state.status == "api_unavailable":
            st.caption("社群快照資料目前無法使用;目前頁面改用相容候選資料。")
        elif social_state.status == "api_failure":
            st.caption("社群快照服務目前無法使用;目前頁面改用相容候選資料。")
    _render_snapshot_agent_reach_status(social)
    picks = _social_snapshot_to_legacy_picks(social) if social else None
    if not picks:
        picks = _shared.load_json(str(_PICKS_PATH))
    if not picks:
        st.info("尚無博主候選資料。請先完成 `codex login`，再在本機執行:\n\n"
                f"```bash\npython scripts/social_intelligence.py --market {market}\n```")
        return

    # tolerate partial/hand-edited files: coerce null lists to [], skip non-dicts,
    # and only keep ticker rows that actually have a symbol.
    tickers = [t for t in (picks.get("tickers") or [])
               if isinstance(t, dict) and t.get("symbol")]
    st.caption(f"視窗 {picks.get('window', '?')} · 產生於 {picks.get('generated_at', '?')} "
               f"· 市場 {picks.get('market') or '?'} · {len(tickers)} 檔候選")

    summary_snapshot = social if isinstance(social, dict) and social.get("tickers") else picks
    tab_tickers, tab_ai, tab_cites = st.tabs(["Ticker 列表", "AI 摘要", "全部 citations"])
    with tab_tickers:
        _render_ticker_list_tab(picks, tickers)
    with tab_ai:
        if isinstance(summary_snapshot, dict) and tickers:
            summary = _maybe_auto_generate_ai_summary(summary_snapshot, market)
            if not isinstance(summary, dict):
                from scripts import social_intelligence_summary

                summary = social_intelligence_summary.load_ai_summary(
                    reports_dir=_shared.REPORTS_DIR,
                    market=market,
                )
            _render_ai_summary_body(summary, summary_snapshot, market)
        else:
            st.caption("這次分析沒有 ticker，暫不產生 AI 摘要。")
    with tab_cites:
        _render_citations_tab(picks.get("citations") or [])


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


def _render_snapshot_agent_reach_status(snapshot: dict | None) -> None:
    if not isinstance(snapshot, dict):
        return
    statuses = snapshot.get("source_statuses")
    if not isinstance(statuses, dict):
        return
    agent = statuses.get("agent_reach")
    if not isinstance(agent, dict):
        return
    status = str(agent.get("status") or "unknown")
    note = str(agent.get("note") or "").strip()
    generated_at = str(snapshot.get("generated_at") or "?")
    label = f"上次快照 Agent Reach · {status}"
    if note:
        label = f"{label}: {note}"
    st.caption(f"{label} · {generated_at}")


def _render_radar_refresh(market: str) -> None:
    """Live re-run of the roster analysis. Local-only, read-only, never crashes."""
    from scripts import social_intelligence

    sources = social_intelligence.source_statuses()
    agent = sources.get("agent_reach", {})
    _shared.chips_row([
        (
            f"Agent Reach 設定 · {agent.get('status', 'unknown')}",
            _shared.GREEN if agent.get("status") in {"available", "configured"} else _shared.AMBER,
        )
    ])

    if st.button("↻ 更新 free-first 社群快照", type="primary", key=f"radar_free_refresh_{market}"):
        with st.spinner("使用 Agent Reach / 免費熱度來源更新社群快照…"):
            try:
                snapshot, paths = _write_free_first_snapshot_from_ui(market)
            except Exception as e:  # noqa: BLE001
                st.error(f"更新失敗:{e}")
                return
        _shared.load_json.clear()
        agent_status = (snapshot.get("source_statuses") or {}).get("agent_reach", {})
        count = len(snapshot.get("tickers") or [])
        if agent_status.get("status") == "available":
            st.success(f"完成,產生 {count} 檔社群候選。")
        else:
            st.warning(
                "快照已更新,但 Agent Reach 未完整可用:"
                f"{agent_status.get('note') or agent_status.get('status') or 'unknown'}"
            )
        st.caption(
            f"latest: {paths.get('latest_path')} · legacy quick-pick: {paths.get('legacy_path')}"
        )
        st.rerun()

    with st.expander("Codex 博主研究重跑", expanded=False):
        _render_paid_grok_refresh(market)


def _write_free_first_snapshot_from_ui(market: str) -> tuple[dict, dict[str, str]]:
    from scripts import social_intelligence

    timeout = float(
        os.environ.get("AGENT_REACH_TIMEOUT")
        or social_intelligence.DEFAULT_AGENT_REACH_TIMEOUT
    )
    agent_command = (
        os.environ.get("AGENT_REACH_COMMAND")
        or social_intelligence._default_agent_reach_command(market)
    )
    agent = social_intelligence.fetch_agent_reach(
        command=agent_command,
        timeout=timeout,
    )
    snapshot = social_intelligence.build_social_snapshot(
        x_picks=_shared.load_json(str(_PICKS_PATH)),
        agent_reach=agent,
        ranked_candidates=_ranked_candidates_seed(),
        options_flow=_shared.load_json(
            str(_shared.REPORTS_DIR / "options_flow" / "latest.json")
        ),
        market=market,
    )
    paths = social_intelligence.write_social_snapshot(snapshot, reports_dir=_shared.REPORTS_DIR)
    return snapshot, paths


def _render_paid_grok_refresh(market: str) -> None:
    """Legacy site-ID boundary; implementation uses subscription-only Codex."""
    from scripts import x_influencers as xi  # lazy

    days = st.slider("回看天數", 1, 14, 3, key=f"radar_days_{market}")
    if not st.button("↻ 重新分析博主", type="primary", key=f"radar_refresh_{market}"):
        return
    if not _ensure_social_ai_codex_auth():
        return
    rows = xi.load_handles(market=market)
    if not rows:
        st.warning(f"可編輯博主名冊沒有 {market} 市場的博主。")
        return
    handles = [r["handle"] for r in rows][:xi.MAX_HANDLES]
    to_d, from_d = date.today().isoformat(), (date.today() - timedelta(days=days)).isoformat()
    with st.spinner(f"Codex 研究 {len(handles)} 位博主中(web search,唯讀)…"):
        try:
            res = xi.analyze(handles, from_d, to_d)
        except Exception as exc:  # defensive: never crash the page
            st.error(f"分析失敗 ({type(exc).__name__})")
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
