"""美股 · 今日決策 — trader-first dashboard.

Reads existing artifacts only. This page is the first stop for an options swing
trader: market gate, opportunity feeds, and risk/position follow-up in one dense
screen. It does not fetch live chains or place orders.
"""

from __future__ import annotations

import logging
import re

import pandas as pd
import streamlit as st

from . import _candidate_controls, _components, _read_api, _shared
from scripts import quote_fallback
from scripts import trade_state as trade_state_engine


LOGGER = logging.getLogger("surge.ui.today_decision")
_ARTIFACT_EVENT = "QR-TODAY-ARTIFACT-001"
_TRADE_STATE_EVENT = "QR-TODAY-TRADE-STATE-001"
_CANDIDATE_API_EVENT = "QR-TODAY-CANDIDATE-API-001"
_MARKET_THESIS_API_EVENT = "QR-TODAY-MARKET-THESIS-API-001"
_DAILY_SUMMARY_API_EVENT = "QR-TODAY-DAILY-SUMMARY-API-001"


class InvalidArtifactRoot(Exception):
    """Payload-free classification for a parsed artifact with the wrong root."""


def _log_failure(event_code: str, error_type: type[BaseException]) -> None:
    LOGGER.warning(
        "event_code=%s error_type=%s",
        event_code,
        error_type.__name__,
    )


def _object_or_none(value) -> dict | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    _log_failure(_ARTIFACT_EVENT, InvalidArtifactRoot)
    return None


def _money(v) -> str:
    if not isinstance(v, (int, float)):
        return "-"
    return f"${v / 1e6:.1f}M" if abs(v) >= 1e6 else f"${v / 1e3:.0f}K"


def _pct(v) -> str:
    return f"{v:+.1f}%" if isinstance(v, (int, float)) else "-"


def _dash(v):
    return "-" if v is None else v


def _candidate_price(row: dict) -> tuple[float | None, str]:
    value = row.get("last_price") if isinstance(row, dict) else None
    if isinstance(value, (int, float)) and value > 0:
        return float(value), "ranked_candidates"
    ticker = str((row or {}).get("ticker") or "").upper().strip()
    if not ticker:
        return None, "-"
    try:
        quote = quote_fallback.get_quote(ticker)
    except Exception:  # noqa: BLE001
        return None, "quote unavailable"
    if isinstance(quote, dict) and quote.get("status") == "ok":
        return float(quote["price"]), quote_fallback.quote_source_text(quote)
    return None, "quote unavailable"


def _market_thesis_view(
    result: _read_api.MarketThesisApiResult,
) -> dict | None:
    if isinstance(result, _read_api.MarketThesisApiAvailable):
        return result.forecast.model_dump(mode="json")
    if isinstance(result, _read_api.MarketThesisApiFailure):
        _log_failure(_MARKET_THESIS_API_EVENT, type(result))
    return None


def _daily_summary_view(
    result: _read_api.DailySummaryApiResult,
) -> tuple[str | None, dict | None]:
    if isinstance(result, _read_api.DailySummaryApiAvailable):
        return (
            result.summary.as_of_date,
            {
                "regime_summary": result.summary.regime_summary,
                "ranked_picks": [
                    candidate.model_dump(mode="json")
                    for candidate in result.summary.candidates
                ],
            },
        )
    if isinstance(result, _read_api.DailySummaryApiFailure):
        _log_failure(_DAILY_SUMMARY_API_EVENT, type(result))
    return None, None


def _ranked_feed_rows(result: _read_api.RankedCandidatesApiResult) -> list[dict]:
    if isinstance(result, _read_api.RankedCandidatesApiAvailable):
        return [candidate.model_dump() for candidate in result.feed.candidates]
    if isinstance(result, _read_api.RankedCandidatesApiFailure):
        _log_failure(_CANDIDATE_API_EVENT, type(result))
    return []


def _scored_feed_rows(result: _read_api.ScoredCandidatesApiResult) -> list[dict]:
    if isinstance(result, _read_api.ScoredCandidatesApiAvailable):
        return [candidate.model_dump() for candidate in result.feed.candidates]
    if isinstance(result, _read_api.ScoredCandidatesApiFailure):
        _log_failure(_CANDIDATE_API_EVENT, type(result))
    return []


def _scored_candidates(rows: list[dict], limit: int = 8) -> list[dict]:
    return rows[:limit]


def _ranked_candidates(rows: list[dict], limit: int = 8) -> list[dict]:
    return rows[:limit]


def _num(data: dict | None, key: str, fallback: str | None = None) -> int | float | None:
    if not isinstance(data, dict):
        return None
    value = data.get(key)
    if value is None and fallback:
        value = data.get(fallback)
    return value if isinstance(value, (int, float)) else None


def _maturity_text(done: int | float | None, required: int | float | None) -> str:
    if done is None and required is None:
        return "-"
    if required is None:
        return str(done)
    return f"{done or 0}/{required}"


def _trust_card(col, title: str, maturity: str, action: str, detail: str,
                *, color: str) -> None:
    with col:
        with st.container(border=True):
            st.markdown(f"##### {title}")
            st.metric("成熟度", maturity)
            _shared.chips_row([(action, color)])
            st.caption(detail)


def _jump(label: str, page: str, *, key: str, ticker: str | None = None,
          state_key: str | None = None) -> None:
    if st.button(label, key=key, use_container_width=True):
        if ticker and state_key:
            st.session_state[state_key] = ticker
            if state_key == "checkup_ticker":
                st.session_state["checkup_handoff"] = ticker
        if not _shared.switch_page(page):
            st.caption("請由側欄開啟目標頁。")


def _render_gate(summary_date: str | None, summary: dict | None, thesis: dict | None) -> None:
    st.subheader("大盤與風控")
    c1, c2, c3, c4 = st.columns(4)
    regime = ((summary or {}).get("regime_summary") or "-")
    direction = (thesis or {}).get("direction") or "-"
    manifest = (thesis or {}).get("manifest_status") or "-"
    support = (thesis or {}).get("support_class") or "-"
    _shared.metric_card(c1, "最新篩選日", summary_date or "-")
    _shared.metric_card(c2, "Regime", regime)
    _shared.metric_card(c3, "大盤研判", direction)
    _shared.metric_card(c4, "研判狀態", manifest)

    chips = []
    if manifest == "ready":
        chips.append(("事件資料 ready", _shared.GREEN))
    elif manifest == "degraded":
        chips.append(("degraded 不警報", _shared.AMBER))
    if support:
        chips.append((support, _shared.MUTED))
    if (thesis or {}).get("label"):
        chips.append(("探索性", _shared.AMBER))
    if chips:
        _shared.chips_row(chips)

    nav1, nav2, nav3, nav4 = st.columns(4)
    with nav1:
        _jump("🧭 大盤行情", "market-thesis", key="td_market")
    with nav2:
        _jump("📑 COT", "us-cot", key="td_cot")
    with nav3:
        _jump("📡 雷達", "radar", key="td_radar")
    with nav4:
        _jump("🧾 IBKR", "ibkr-reconcile", key="td_ibkr")


def _render_trust_boundary() -> None:
    st.subheader("信任邊界")
    market_result = _read_api.load_market_thesis_validation()
    market_val = (
        market_result.summary.model_dump(mode="json")
        if isinstance(
            market_result,
            _read_api.MarketThesisValidationApiAvailable,
        )
        else None
    )
    reversal_result = _read_api.load_reversal_radar_validation()
    reversal_val = (
        reversal_result.summary.model_dump(mode="json")
        if isinstance(
            reversal_result,
            _read_api.ReversalRadarValidationApiAvailable,
        )
        else None
    )
    oversold_result = _read_api.load_oversold_reversal_validation()
    oversold_val = (
        oversold_result.summary.model_dump(mode="json")
        if isinstance(
            oversold_result,
            _read_api.OversoldReversalValidationApiAvailable,
        )
        else None
    )

    m_done = _num(market_val, "matured")
    m_required = _num(market_val, "min_resolved_for_verdict")
    r_done = _num(reversal_val, "min_resolved_across_tiers")
    r_required = _num(reversal_val, "min_resolved_for_verdict")
    o_done = _num(oversold_val, "min_resolved_across_tiers")
    o_required = _num(oversold_val, "min_resolved_for_verdict")

    c1, c2, c3 = st.columns(3)
    _trust_card(
        c1,
        "大盤 thesis",
        _maturity_text(m_done, m_required),
        "背景-only",
        (
            f"已解決 {market_val.get('resolved', 0)} 筆;未達門檻前不當方向警報。"
            if market_val
            else "API 暫無驗證摘要;未達門檻前不當方向警報。"
        ),
        color=_shared.AMBER,
    )
    _trust_card(
        c2,
        "反轉雷達",
        _maturity_text(r_done, r_required),
        "觀察-only",
        (
            f"{reversal_val.get('entries_accumulated', 0)} 筆累積;"
            f"{reversal_val.get('verdict', '無驗證摘要')}。"
            if reversal_val
            else "API 暫無驗證摘要;探索性訊號只能進 watchlist。"
        ),
        color=_shared.AMBER,
    )
    _trust_card(
        c3,
        "壓縮基底",
        _maturity_text(o_done, o_required),
        "觀察-only",
        (
            f"{oversold_val.get('entries_accumulated', 0)} 筆累積;"
            f"{oversold_val.get('verdict', '無驗證摘要')}。"
            if oversold_val
            else "API 暫無驗證摘要;探索性訊號只能進 watchlist。"
        ),
        color=_shared.AMBER,
    )
    st.caption("交易狀態只能由 validated 訊號或 risk-control 訊號改變;探索性訊號只能進 watchlist。")


def _ranked_result_df(rows: list[dict], limit: int = 50) -> pd.DataFrame:
    out = []
    for idx, row in enumerate(_ranked_candidates(rows, limit), start=1):
        components = row.get("score_components") if isinstance(row.get("score_components"), dict) else {}
        tradability = (
            row.get("options_tradability")
            if isinstance(row.get("options_tradability"), dict)
            else {}
        )
        warnings = tradability.get("warnings") or row.get("warnings") or []
        price, price_source = _candidate_price(row)
        out.append({
            "排名": idx,
            "代號": row.get("ticker"),
            "rank_score": _dash(row.get("rank_score")),
            "現價": _dash(price),
            "價格來源": price_source,
            "期權狀態": tradability.get("status") or row.get("rank_bucket") or "-",
            "IV%": _dash(tradability.get("iv_percentile")),
            "價差%": _dash(tradability.get("spread_pct")),
            "期權分": _dash(tradability.get("flow_score")),
            "5日": _pct(row.get("ret_5d")),
            "20日": _pct(row.get("ret_20d")),
            "技術": _dash(components.get("technical_trend")),
            "動能": _dash(components.get("momentum_strength")),
            "啟動": _dash(components.get("launch_signal")),
            "流動性": _dash(components.get("liquidity_tradability")),
            "風險": _dash(components.get("overheat_risk_control")),
            "警告": str(warnings[0]) if warnings else "-",
        })
    return pd.DataFrame(out)


def _llm_detail_rows(rows: list[dict], limit: int = 12) -> list[dict]:
    return rows[:limit]


def _verdict_zh(value) -> str:
    return {
        "REJECT": "拒絕",
        "WATCHLIST": "觀察",
        "NEEDS_LAYER_2": "需二階深檢",
    }.get(str(value or ""), str(value or "-"))


def _missing_zh(value) -> str:
    return {
        "catalyst": "催化事件",
        "options_flow": "期權流",
        "sentiment": "情緒/社群",
        "institutional": "機構籌碼",
        "analyst": "分析師",
        "sector_rotation": "板塊輪動",
        "options": "期權資料",
    }.get(str(value), str(value))


def _llm_result_df(rows: list[dict], limit: int = 12) -> pd.DataFrame:
    out = []
    for row in rows[:limit]:
        scores = row.get("scores") if isinstance(row.get("scores"), dict) else {}
        out.append({
            "代號": row.get("ticker"),
            "LLM 判定": _verdict_zh(row.get("verdict")),
            "LLM 分數": row.get("regime_adjusted_score", row.get("composite_score", "-")),
            "技術": scores.get("technical", "-"),
            "催化": scores.get("catalyst", "-"),
            "情緒": scores.get("sentiment", "-"),
            "機構": scores.get("institutional", "-"),
            "板塊/大盤": scores.get("sector_market", "-"),
            "期權": scores.get("options_flow", "-"),
            "分析師": scores.get("analyst", "-"),
            "資料缺口": len(row.get("data_missing") or []),
        })
    return pd.DataFrame(out)


def _bullet_list(items: list, *, empty: str = "-") -> None:
    if not items:
        st.caption(empty)
        return
    for item in items[:6]:
        st.markdown(f"- {item}")


def _render_selected_llm_detail(row: dict) -> None:
    with st.container(border=True):
        st.markdown(f"##### {row.get('ticker', '-')} 完整詳情")
        st.caption(
            f"LLM 判定：{_verdict_zh(row.get('verdict'))} · "
            f"分數：{row.get('regime_adjusted_score', row.get('composite_score', '-'))}"
        )
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("###### 主要理由")
            _bullet_list(row.get("key_signals") if isinstance(row.get("key_signals"), list) else [])
        with c2:
            st.markdown("###### 阻擋因素")
            _bullet_list(row.get("key_risks") if isinstance(row.get("key_risks"), list) else [])
        st.markdown("###### 下一步")
        st.caption(row.get("suggested_entry_zone") or ("需補資料" if row.get("due_diligence_required") else "-"))
        missing = row.get("data_missing") if isinstance(row.get("data_missing"), list) else []
        if missing:
            st.caption("資料缺口：" + "、".join(_missing_zh(x) for x in missing[:8]))


def _has_english_llm_detail(rows: list[dict]) -> bool:
    for row in rows:
        text_parts = []
        for key in ("key_signals", "key_risks"):
            values = row.get(key) if isinstance(row.get(key), list) else []
            text_parts.extend(str(v) for v in values)
        text_parts.append(str(row.get("suggested_entry_zone") or ""))
        if re.search(r"[A-Za-z]{4,}", " ".join(text_parts)):
            return True
    return False


def _render_candidate_results(
    ranked_rows: list[dict],
    scored_rows: list[dict],
    *,
    ranked_available: bool,
    scored_available: bool,
) -> None:
    ranked_tab, llm_tab = st.tabs(["最新排名結果", "LLM 深檢結果"])
    with ranked_tab:
        ranked_df = _ranked_result_df(ranked_rows)
        if ranked_df.empty:
            if ranked_available:
                st.info("候選排名 API 目前沒有資料。需要時執行完整刷新。")
            else:
                st.warning("候選排名 API 暫時無法提供資料；不會改讀本機檔案。")
        else:
            st.dataframe(ranked_df, hide_index=True, use_container_width=True, height=360)
            st.caption("資料來源：ranked_candidates.json。期權狀態為 options gate 初篩，不等於可直接下單。")
    with llm_tab:
        llm_rows = _llm_detail_rows(scored_rows)
        llm_df = _llm_result_df(llm_rows)
        if llm_df.empty:
            if scored_available:
                st.info("LLM 深檢 API 目前沒有資料。需要時執行少量 LLM。")
            else:
                st.warning("LLM 深檢 API 暫時無法提供資料；不會改讀本機檔案。")
        else:
            st.caption("LLM 依據 7 維度：技術、催化、情緒、機構、板塊/大盤、期權流、分析師。舊結果可能仍是英文；少量 LLM 會優先重算英文舊列。")
            if _has_english_llm_detail(llm_rows):
                st.warning("目前 scored_candidates.json 內有舊英文詳情；按「少量 LLM」會把這些英文舊列排入重算，新輸出會依 prompt 使用繁中。")
            options = [
                f"{row.get('ticker', '-')} · {_verdict_zh(row.get('verdict'))} · LLM {row.get('regime_adjusted_score', row.get('composite_score', '-'))}"
                for row in llm_rows
            ]
            selected_label = st.selectbox(
                "選擇標的查看完整詳情",
                options,
                index=0,
                key="today_llm_detail_ticker",
            )
            selected_idx = options.index(selected_label)
            _render_selected_llm_detail(llm_rows[selected_idx])
            st.markdown("##### 同批摘要")
            st.dataframe(llm_df, hide_index=True, use_container_width=True, height=280)
            st.caption("資料來源：scored_candidates.json。LLM 只做深檢與風險摘要，不取代可交易性檢查。")


def _render_trade_state_summary() -> None:
    """Compact entry point for the dedicated 交易狀態 page."""
    try:
        rows = trade_state_engine.build_trade_state_rows(limit=50)
    except Exception as exc:  # noqa: BLE001
        rows = []
        load_failed = True
        _log_failure(_TRADE_STATE_EVENT, type(exc))
    else:
        load_failed = False

    with st.container(border=True):
        head, action = st.columns([4, 1])
        with head:
            st.markdown("##### 交易狀態")
            st.caption("Cycle 取自 Notion 課程規則；CE/Proxy 用標的日線 Chandelier Exit 或資料不足 fallback 壓縮成操作狀態。")
        with action:
            if st.button("打開交易狀態", key="today_open_trade_state", use_container_width=True):
                if not _shared.switch_page("trade-state"):
                    st.caption("請從側欄開啟「交易狀態」。")

        if load_failed:
            _components.render_state_banner(
                _components.DataState(
                    source="unavailable",
                    content="unknown",
                    freshness="unknown",
                    operation="idle",
                    source_id="today.trade-state",
                    reason_code="computation_failure",
                    event_code=_TRADE_STATE_EVENT,
                    recovery_key="open-data-health",
                )
            )
            return
        if not rows:
            _components.render_state_banner(
                _components.DataState(
                    source="authoritative",
                    content="empty",
                    freshness="unknown",
                    operation="idle",
                    source_id="today.trade-state",
                    recovery_key="open-data-health",
                )
            )
            return

        s = trade_state_engine.summarize(rows)
        c1, c2, c3, c4 = st.columns(4)
        _shared.metric_card(c1, "Cycle1", s["cycle1"], help="Notion：穩定上升期 / 趨勢延續")
        _shared.metric_card(c2, "CE/Proxy 偏多", s["ce_bullish"], help="有標的 high/low/ATR 時為 CE；缺資料時為 Proxy")
        _shared.metric_card(c3, "Holding", s["holding"], help="Cycle + CE + risk 同向偏多")
        _shared.metric_card(c4, "停利/停損", s["take_profit"] + s["stop_loss"],
                            help="take_profit + stop_loss")


def _render_data_health_entry() -> None:
    with st.container(border=True):
        left, right = st.columns([4, 1])
        with left:
            st.markdown("##### 資料健康")
            st.caption(
                "完整刷新只處理今日決策需要的資料；低頻研究資料與 DB 重建放在資料健康中心。"
            )
        with right:
            if st.button("查看資料健康", key="today_open_data_health", use_container_width=True):
                if not _shared.switch_page("analytics-db"):
                    st.caption("請從側欄開啟「資料健康 / Analytics DB」。")


def _candidate_df(candidates: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{
        "代號": c.get("ticker"),
        "判定": ((c.get("options_tradability") or {}).get("status")
               or c.get("verdict")
               or c.get("rank_bucket")
               or "-"),
        "分數": c.get("rank_score", c.get("regime_adjusted_score", c.get("composite_score"))),
        "期權分": ((c.get("options_tradability") or {}).get("flow_score")
                or (c.get("scores") or {}).get("options_flow")),
        "進場區": c.get("suggested_entry_zone", "-"),
    } for c in candidates])


def _flow_df(signals: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{
        "代號": s.get("ticker"),
        "方向": "偏多" if s.get("direction") == "bullish" else "偏空" if s.get("direction") == "bearish" else "中性",
        "熱度": s.get("flow_score"),
        "估權利金": _money(s.get("est_notional_usd")),
        "V/OI峰值": s.get("max_voi"),
        "標籤": " · ".join((s.get("tags") or [])[:3]),
    } for s in signals])


def _render_opportunities(
    summary: dict | None,
    ranked_rows: list[dict],
    scored_rows: list[dict],
) -> None:
    st.subheader("候選來源")
    left, right = st.columns(2)

    with left:
        st.markdown("##### 篩選器候選")
        ranked_value = (summary or {}).get("ranked_picks") or []
        ranked = ranked_value if isinstance(ranked_value, list) else []
        if ranked_value and not isinstance(ranked_value, list):
            _log_failure(_ARTIFACT_EVENT, InvalidArtifactRoot)
        candidates = ranked if ranked else (
            _ranked_candidates(ranked_rows) or _scored_candidates(scored_rows)
        )
        if candidates:
            st.dataframe(_candidate_df(candidates), hide_index=True, use_container_width=True,
                         height=260)
            ticker = str(candidates[0].get("ticker", "")).upper()
            _shared.ticker_action_buttons(ticker, "td_screen")
        else:
            st.info("最新報告沒有 confirmed picks。")
            _jump("🌡 篩選器", "us-screener", key="td_screener_empty")

    with right:
        st.markdown("##### 選擇權異常流")
        flow_result = _read_api.load_options_flow()
        flow_available = isinstance(flow_result, _read_api.OptionsFlowApiAvailable)
        signals = (
            [signal.model_dump(mode="json") for signal in flow_result.feed.signals[:8]]
            if flow_available
            else []
        )
        if signals:
            st.dataframe(_flow_df(signals), hide_index=True, use_container_width=True, height=260)
            ticker = str(signals[0].get("ticker", "")).upper()
            _shared.ticker_action_buttons(ticker, "td_flow")
        else:
            if flow_available:
                st.info("Options Flow API 目前沒有訊號。")
            else:
                st.info("Options Flow API 暫時無法提供資料；不會改讀本機檔案。")
            _jump("🚨 異常流", "options-flow", key="td_flow_empty")


def _render_risk_and_research() -> None:
    st.subheader("持倉與驗證")
    c1, c2, c3, c4 = st.columns(4)

    rec = _object_or_none(_shared.load_reconciliation()) or {}
    matched = rec.get("matched")
    unmatched = rec.get("held_not_in_ledger")
    if matched is not None and not isinstance(matched, list):
        _log_failure(_ARTIFACT_EVENT, InvalidArtifactRoot)
    if unmatched is not None and not isinstance(unmatched, list):
        _log_failure(_ARTIFACT_EVENT, InvalidArtifactRoot)
    held = (matched if isinstance(matched, list) else []) + (
        unmatched if isinstance(unmatched, list) else []
    )
    reversal_result = _read_api.load_reversal_radar()
    reversal_count = (
        reversal_result.snapshot.match_count
        if isinstance(reversal_result, _read_api.ReversalRadarApiAvailable)
        else "-"
    )
    oversold_result = _read_api.load_oversold_reversal()
    oversold_count = (
        oversold_result.snapshot.match_count
        if isinstance(oversold_result, _read_api.OversoldReversalApiAvailable)
        else "-"
    )
    ledger = _shared.load_ledger()

    _shared.metric_card(
        c1,
        "IBKR 底層",
        len({r.get("ticker") for r in held if isinstance(r, dict) and r.get("ticker")}),
    )
    _shared.metric_card(c2, "反轉候選", reversal_count)
    _shared.metric_card(c3, "蓄勢候選", oversold_count)
    _shared.metric_card(c4, "Ledger 筆數", len(ledger) if ledger is not None else "-")

    nav1, nav2, nav3, nav4 = st.columns(4)
    with nav1:
        _jump("🧾 持倉對帳", "ibkr-reconcile", key="td_risk_ibkr")
    with nav2:
        _jump("📡 風險/反轉", "radar", key="td_risk_radar")
    with nav3:
        _jump("🔁 復盤", "retro-analysis", key="td_retro")
    with nav4:
        _jump("🔗 知識網路", "knowledge-graph", key="td_kg")


def render() -> None:
    st.header("今日決策")
    st.caption("唯讀決策面板。交易前以作戰台與風控頁為準;探索性訊號只進觀察。")

    _candidate_controls.render()
    _render_data_health_entry()
    _render_trade_state_summary()
    ranked_result = _read_api.load_ranked_candidates()
    scored_result = _read_api.load_scored_candidates()
    ranked_rows = _ranked_feed_rows(ranked_result)
    scored_rows = _scored_feed_rows(scored_result)
    _render_candidate_results(
        ranked_rows,
        scored_rows,
        ranked_available=isinstance(
            ranked_result, _read_api.RankedCandidatesApiAvailable
        ),
        scored_available=isinstance(
            scored_result, _read_api.ScoredCandidatesApiAvailable
        ),
    )

    daily_summary_result = _read_api.load_daily_summary()
    summary_date, summary = _daily_summary_view(daily_summary_result)
    thesis_result = _read_api.load_market_thesis()
    thesis = _market_thesis_view(thesis_result)

    _render_gate(summary_date, summary, thesis)
    st.divider()
    _render_trust_boundary()
    st.divider()
    _render_opportunities(summary, ranked_rows, scored_rows)
    st.divider()
    _render_risk_and_research()
