"""美股 · 今日決策 — trader-first dashboard.

Reads existing artifacts only. This page is the first stop for an options swing
trader: market gate, opportunity feeds, and risk/position follow-up in one dense
screen. It does not fetch live chains or place orders.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from . import _shared
from scripts.candidate_pipeline_controls import CandidateRunParams, RUN_MODE_LABELS, launch_background


_MARKET_THESIS_DIR = _shared.REPORTS_DIR / "market_thesis"
_FLOW_DIR = _shared.REPORTS_DIR / "options_flow"
_REVERSAL_DIR = _shared.REPORTS_DIR / "reversal_radar"
_OVERSOLD_DIR = _shared.REPORTS_DIR / "oversold_reversal"
_RUN_STATUS_PATH = _shared.REPORTS_DIR / "run_status" / "candidates-local.json"
_RUN_HISTORY_PATH = _shared.REPORTS_DIR / "run_status" / "candidates-local-history.jsonl"
_RANK_STAGE_ID = "rank_candidates"


def _money(v) -> str:
    if not isinstance(v, (int, float)):
        return "-"
    return f"${v / 1e6:.1f}M" if abs(v) >= 1e6 else f"${v / 1e3:.0f}K"


def _pct(v) -> str:
    return f"{v:+.1f}%" if isinstance(v, (int, float)) else "-"


def _dash(v):
    return "-" if v is None else v


def _latest_market_thesis() -> dict | None:
    if not _MARKET_THESIS_DIR.exists():
        return None
    files = list(_MARKET_THESIS_DIR.glob("*forecast_*.json"))
    if not files:
        return None

    def rank(path: Path) -> tuple[str, bool]:
        match = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
        return (match.group(1) if match else "", not path.name.startswith("regime_only"))

    return _shared.load_json(str(sorted(files, key=rank, reverse=True)[0]))


def _latest_daily_summary() -> tuple[str | None, dict | None]:
    dates = _shared.find_report_dates()
    if not dates:
        return None, None
    latest = dates[0]
    return latest, _shared.load_json(str(_shared.REPORTS_DIR / latest / "summary.json"))


def _scored_candidates(limit: int = 8) -> list[dict]:
    scored = _shared.load_json(str(_shared.DATA_DIR / "scored_candidates.json")) or {}
    rows = []
    for key in ("needs_layer2", "watchlist", "all_scored"):
        for row in scored.get(key, []) or []:
            if isinstance(row, dict) and row.get("ticker"):
                rows.append(row)
    seen = set()
    unique = []
    for row in rows:
        ticker = row.get("ticker")
        if ticker in seen:
            continue
        seen.add(ticker)
        unique.append(row)
    unique.sort(key=lambda r: r.get("regime_adjusted_score", r.get("composite_score", 0)) or 0,
                reverse=True)
    return unique[:limit]


def _ranked_candidates(limit: int = 8) -> list[dict]:
    ranked = _shared.load_json(str(_shared.DATA_DIR / "ranked_candidates.json")) or {}
    rows = ranked.get("ranked_candidates") or ranked.get("tickers") or []
    rows = [r for r in rows if isinstance(r, dict) and r.get("ticker")]
    rows.sort(key=lambda r: r.get("rank_score", 0) or 0, reverse=True)
    return rows[:limit]


def _flow_signals(limit: int = 8) -> list[dict]:
    data = _shared.load_json(str(_FLOW_DIR / "latest.json")) or {}
    signals = [s for s in data.get("signals", []) if isinstance(s, dict)]
    return signals[:limit]


def _validation_summary(folder: Path) -> dict | None:
    data = _shared.load_json(str(folder / "validation_summary.json"))
    return data if isinstance(data, dict) else None


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
    market_val = _validation_summary(_MARKET_THESIS_DIR)
    reversal_val = _validation_summary(_REVERSAL_DIR)
    oversold_val = _validation_summary(_OVERSOLD_DIR)

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
        f"已解決 {market_val.get('resolved', 0) if market_val else 0} 筆;未達門檻前不當方向警報。",
        color=_shared.AMBER,
    )
    _trust_card(
        c2,
        "反轉雷達",
        _maturity_text(r_done, r_required),
        "觀察-only",
        f"{reversal_val.get('entries_accumulated', 0) if reversal_val else 0} 筆累積;"
        f"{reversal_val.get('verdict', '無驗證摘要') if reversal_val else '無驗證摘要'}。",
        color=_shared.AMBER,
    )
    _trust_card(
        c3,
        "壓縮基底",
        _maturity_text(o_done, o_required),
        "觀察-only",
        f"{oversold_val.get('entries_accumulated', 0) if oversold_val else 0} 筆累積;"
        f"{oversold_val.get('verdict', '無驗證摘要') if oversold_val else '無驗證摘要'}。",
        color=_shared.AMBER,
    )
    st.caption("交易狀態只能由 validated 訊號或 risk-control 訊號改變;探索性訊號只能進 watchlist。")


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _status_is_active(data: dict | None) -> bool:
    if not isinstance(data, dict) or data.get("status") != "running":
        return False
    updated_dt = _parse_utc(data.get("updated_at"))
    if not updated_dt:
        return True
    return (datetime.now(timezone.utc) - updated_dt).total_seconds() <= 600


def _candidate_run_history(limit: int = 8) -> list[dict]:
    # History is JSONL: reports/run_status/candidates-local-history.jsonl
    if not _RUN_HISTORY_PATH.exists():
        return []
    rows = []
    try:
        lines = _RUN_HISTORY_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
        if len(rows) >= limit:
            break
    return rows


def _history_flow(row: dict) -> str:
    metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
    stage = row.get("stage") if isinstance(row.get("stage"), dict) else {}

    if (
        metrics.get("passed_hard_filters") is not None
        or metrics.get("completed_batches") is not None
        or metrics.get("filter_rules") is not None
    ):
        return "完整刷新 + 排名"
    if metrics.get("scored_candidates") is not None:
        return "少量 LLM"
    if (
        metrics.get("ranked_candidates") is not None
        or metrics.get("rank_source_candidates") is not None
        or "ranked" in str(stage.get("message") or "").lower()
    ):
        return "只重排"
    return "-"


def _status_zh(value) -> str:
    return {
        "running": "執行中",
        "succeeded": "成功",
        "failed": "失敗",
        "unknown": "未知",
    }.get(str(value or "unknown"), str(value or "未知"))


def _scored_progress_label(metrics: dict) -> str | None:
    scored = metrics.get("scored_candidates")
    if scored is None:
        return None
    limit = metrics.get("candidate_limit")
    if isinstance(scored, int) and isinstance(limit, int) and limit > 0:
        if scored <= limit:
            return f"LLM 深檢 {scored}/{limit}"
        return f"LLM 深檢累積 {scored}（本次上限 {limit}）"
    return f"LLM 深檢 {scored}"


def _status_message_zh(message: str) -> str:
    match = re.fullmatch(r"(\d+) candidates scored;\s*(\d+) remaining", message.strip())
    if match:
        scored, remaining = match.groups()
        return f"LLM 已累積 {scored} 檔；尚有 {remaining} 檔未深檢"
    return message


def _history_df(rows: list[dict]) -> pd.DataFrame:
    out = []
    for row in rows:
        metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
        out.append({
            "完成時間": row.get("finished_at") or row.get("started_at"),
            "狀態": _status_zh(row.get("status")),
            "流程": _history_flow(row),
            "通過基礎篩選": metrics.get("passed_hard_filters", metrics.get("rank_source_candidates", "-")),
            "排名產出": metrics.get("ranked_candidates", "-"),
            "Top N 上限": metrics.get("rank_limit", "-"),
            "期權檢查數": metrics.get("options_gate_checked", "-"),
        })
    return pd.DataFrame(out)


def _tail_text(path: str | Path | None, limit: int = 8) -> str:
    if not path:
        return ""
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-limit:])


def _ranked_result_df(limit: int = 50) -> pd.DataFrame:
    rows = _ranked_candidates(limit)
    out = []
    for idx, row in enumerate(rows, start=1):
        components = row.get("score_components") if isinstance(row.get("score_components"), dict) else {}
        tradability = (
            row.get("options_tradability")
            if isinstance(row.get("options_tradability"), dict)
            else {}
        )
        warnings = tradability.get("warnings") or row.get("warnings") or []
        out.append({
            "排名": idx,
            "代號": row.get("ticker"),
            "rank_score": _dash(row.get("rank_score")),
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


def _llm_detail_rows(limit: int = 12) -> list[dict]:
    scored = _shared.load_json(str(_shared.DATA_DIR / "scored_candidates.json")) or {}
    rows = []
    for bucket in ("needs_layer2", "watchlist", "all_scored"):
        for row in scored.get(bucket, []) or []:
            if isinstance(row, dict) and row.get("ticker"):
                rows.append(row)
    seen = set()
    out = []
    for row in sorted(
        rows,
        key=lambda r: r.get("regime_adjusted_score", r.get("composite_score", 0)) or 0,
        reverse=True,
    ):
        ticker = row.get("ticker")
        if ticker in seen:
            continue
        seen.add(ticker)
        out.append(row)
        if len(out) >= limit:
            break
    return out


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


def _llm_result_df(limit: int = 12) -> pd.DataFrame:
    out = []
    for row in _llm_detail_rows(limit):
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
        text_parts.append(str(row.get("suggested_stop") or ""))
        if re.search(r"[A-Za-z]{4,}", " ".join(text_parts)):
            return True
    return False


def _render_candidate_results() -> None:
    ranked_tab, llm_tab = st.tabs(["最新排名結果", "LLM 深檢結果"])
    with ranked_tab:
        ranked_df = _ranked_result_df()
        if ranked_df.empty:
            st.info("尚未產生 ranked_candidates.json。先執行完整刷新。")
        else:
            st.dataframe(ranked_df, hide_index=True, use_container_width=True, height=360)
            st.caption("資料來源：ranked_candidates.json。期權狀態為 options gate 初篩，不等於可直接下單。")
    with llm_tab:
        llm_rows = _llm_detail_rows()
        llm_df = _llm_result_df()
        if llm_df.empty:
            st.info("尚未產生 LLM 深檢結果。需要時執行少量 LLM。")
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


def _render_launch_tracking(status_data: dict | None) -> None:
    meta = st.session_state.get("candidate_pipeline_last_launch")
    if not isinstance(meta, dict):
        return

    mode = meta.get("mode")
    mode_label = meta.get("mode_label") or RUN_MODE_LABELS.get(mode, "本機篩選")
    command = meta.get("command") if isinstance(meta.get("command"), list) else []
    log_path = meta.get("log_path")
    stage = status_data.get("stage") if isinstance(status_data, dict) and isinstance(status_data.get("stage"), dict) else {}
    status = status_data.get("status") if isinstance(status_data, dict) else "unknown"
    status_label = _status_zh(status)
    stage_label = stage.get("label") or "-"

    st.caption(
        f"最近啟動：{mode_label} · pid={meta.get('pid', '-')} · "
        f"目前 {status_label} / {stage_label}。下方「本機候選刷新」每 8 秒更新。"
    )
    with st.expander("追蹤細節", expanded=False):
        st.caption(f"狀態檔：{_RUN_STATUS_PATH}")
        if log_path:
            st.caption(f"log：{log_path}")
        if command:
            st.code(" ".join(str(part) for part in command), language="bash")
        tail = _tail_text(log_path)
        if tail:
            st.code(tail, language="text")


def _launch_candidate_run(mode: str, *, rank_limit: int, options_gate_limit: int,
                          candidate_limit: int, universe: str, yf_batch_size: int,
                          min_data_coverage: float, min_avg_dollar_vol: int,
                          min_market_cap: int, min_price: float,
                          max_ret_5d: float, max_ret_20d: float,
                          earnings_exclude_days: int) -> None:
    params = CandidateRunParams(
        mode=mode,
        rank_limit=rank_limit,
        options_gate_limit=options_gate_limit,
        candidate_limit=candidate_limit,
        universe=universe,
        yf_batch_size=yf_batch_size,
        min_data_coverage=min_data_coverage,
        min_avg_dollar_vol=min_avg_dollar_vol,
        min_market_cap=min_market_cap,
        min_price=min_price,
        max_ret_5d=max_ret_5d,
        max_ret_20d=max_ret_20d,
        earnings_exclude_days=earnings_exclude_days,
    )
    meta = launch_background(params)
    st.session_state["candidate_pipeline_last_launch"] = meta


def _render_candidate_pipeline_controls() -> None:
    status_data = _shared.load_json(str(_RUN_STATUS_PATH))
    running = _status_is_active(status_data)

    with st.container(border=True):
        st.markdown("##### 本機篩選控制台")
        st.caption("日常先跑完整刷新產生今日排名；LLM 深檢只補少量標的的敘事與風險摘要。")
        top1, top2, top3 = st.columns(3)
        with top1:
            rank_limit = int(st.number_input(
                "排名 Top N",
                min_value=5,
                max_value=200,
                value=50,
                step=5,
                help="RANK_LIMIT：從基礎篩選後保留多少檔進入今日排名。",
            ))
        with top2:
            options_gate_limit = int(st.number_input(
                "期權檢查數",
                min_value=0,
                max_value=50,
                value=10,
                step=1,
                help="OPTIONS_GATE_LIMIT：只對排名前 N 檔做免費期權可交易性初篩；0 代表關閉。",
            ))
        with top3:
            candidate_limit = int(st.number_input(
                "LLM 深檢數",
                min_value=1,
                max_value=25,
                value=3,
                step=1,
                help="CANDIDATE_LIMIT：每次少量 LLM 要檢查的 ranked pool 標的數。",
            ))

        advanced = st.expander("過篩參數", expanded=False)
        with advanced:
            a1, a2, a3 = st.columns(3)
            with a1:
                universe = st.selectbox("UNIVERSE", ["sp1500", "nasdaq_only", "russell3000", "custom"],
                                        index=0)
                yf_batch_size = int(st.number_input("YF_BATCH_SIZE", min_value=1,
                                                    max_value=100, value=25, step=1))
                min_data_coverage = float(st.number_input("MIN_DATA_COVERAGE", min_value=0.1,
                                                          max_value=1.0, value=0.70,
                                                          step=0.05, format="%.2f"))
            with a2:
                min_avg_dollar_vol = int(st.number_input("MIN_AVG_DOLLAR_VOL", min_value=0,
                                                         max_value=1_000_000_000,
                                                         value=5_000_000,
                                                         step=1_000_000))
                min_market_cap = int(st.number_input("MIN_MARKET_CAP", min_value=0,
                                                     max_value=50_000_000_000,
                                                     value=300_000_000,
                                                     step=100_000_000))
                min_price = float(st.number_input("MIN_PRICE", min_value=0.0,
                                                  max_value=500.0, value=5.0,
                                                  step=1.0))
            with a3:
                max_ret_5d = float(st.number_input("MAX_RET_5D", min_value=1.0,
                                                   max_value=200.0, value=30.0,
                                                   step=1.0))
                max_ret_20d = float(st.number_input("MAX_RET_20D", min_value=1.0,
                                                    max_value=300.0, value=60.0,
                                                    step=1.0))
                earnings_exclude_days = int(st.number_input("EARNINGS_EXCLUDE_DAYS",
                                                            min_value=0, max_value=30,
                                                            value=2, step=1))
            st.divider()
            if st.button("只重排（進階）", key="candidate_rank_existing",
                         disabled=running, use_container_width=True):
                _launch_candidate_run(
                    "rank_existing",
                    rank_limit=rank_limit,
                    options_gate_limit=options_gate_limit,
                    candidate_limit=candidate_limit,
                    universe=universe,
                    yf_batch_size=yf_batch_size,
                    min_data_coverage=min_data_coverage,
                    min_avg_dollar_vol=min_avg_dollar_vol,
                    min_market_cap=min_market_cap,
                    min_price=min_price,
                    max_ret_5d=max_ret_5d,
                    max_ret_20d=max_ret_20d,
                    earnings_exclude_days=earnings_exclude_days,
                )

        if running:
            st.caption("已有本機篩選在執行;完成或超過 10 分鐘未更新後才能再啟動。")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("完整刷新", key="candidate_full_refresh",
                         disabled=running, use_container_width=True):
                _launch_candidate_run(
                    "full_refresh",
                    rank_limit=rank_limit,
                    options_gate_limit=options_gate_limit,
                    candidate_limit=candidate_limit,
                    universe=universe,
                    yf_batch_size=yf_batch_size,
                    min_data_coverage=min_data_coverage,
                    min_avg_dollar_vol=min_avg_dollar_vol,
                    min_market_cap=min_market_cap,
                    min_price=min_price,
                    max_ret_5d=max_ret_5d,
                    max_ret_20d=max_ret_20d,
                    earnings_exclude_days=earnings_exclude_days,
                )
        with b2:
            if st.button("少量 LLM", key="candidate_llm_deep_check",
                         disabled=running, use_container_width=True):
                _launch_candidate_run(
                    "llm_deep_check",
                    rank_limit=rank_limit,
                    options_gate_limit=options_gate_limit,
                    candidate_limit=candidate_limit,
                    universe=universe,
                    yf_batch_size=yf_batch_size,
                    min_data_coverage=min_data_coverage,
                    min_avg_dollar_vol=min_avg_dollar_vol,
                    min_market_cap=min_market_cap,
                    min_price=min_price,
                    max_ret_5d=max_ret_5d,
                    max_ret_20d=max_ret_20d,
                    earnings_exclude_days=earnings_exclude_days,
                )

        latest_status = _shared.load_json(str(_RUN_STATUS_PATH))
        _render_launch_tracking(latest_status)

        history = _candidate_run_history()
        if history:
            st.markdown("##### 篩選紀錄")
            st.dataframe(_history_df(history), hide_index=True, use_container_width=True,
                         height=220)


@st.fragment(run_every="8s")
def _render_local_refresh_status() -> None:
    # Single latest status file: reports/run_status/candidates-local.json
    # UI reads stage.progress_pct; it never parses CLI logs.
    data = _shared.load_json(str(_RUN_STATUS_PATH))
    if not isinstance(data, dict) or data.get("job") != "candidates-local":
        return

    status = str(data.get("status") or "unknown")
    status_label = _status_zh(status)
    stage = data.get("stage") if isinstance(data.get("stage"), dict) else {}
    metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
    pct = stage.get("progress_pct")
    pct = float(pct) if isinstance(pct, (int, float)) else 0.0
    pct = max(0.0, min(100.0, pct))
    updated_at = data.get("updated_at")
    updated_dt = _parse_utc(updated_at)
    stale = status == "running" and updated_dt and (
        datetime.now(timezone.utc) - updated_dt
    ).total_seconds() > 600

    color = {
        "running": _shared.BLUE,
        "succeeded": _shared.GREEN,
        "failed": _shared.RED,
    }.get(status, _shared.MUTED)
    label = stage.get("label") or "本機候選刷新"
    message = stage.get("message") or ""

    with st.container(border=True):
        head, meta = st.columns([2, 3])
        with head:
            st.markdown("##### 本機候選刷新")
            _shared.chips_row([(status_label, color)])
        with meta:
            parts = []
            if metrics.get("completed_batches") and metrics.get("total_batches"):
                parts.append(f"抓取行情 {metrics['completed_batches']}/{metrics['total_batches']}")
            scored_label = _scored_progress_label(metrics)
            if scored_label:
                parts.append(scored_label)
            if stage.get("id") == _RANK_STAGE_ID or metrics.get("ranked_candidates") is not None:
                parts.append(f"排名完成 {metrics.get('ranked_candidates', '-')}/{metrics.get('rank_limit', '-')}")
            if metrics.get("options_gate_checked"):
                parts.append(f"期權檢查 {metrics['options_gate_checked']}")
            st.caption(" · ".join([label, *parts]) if parts else label)
            if updated_at:
                st.caption(f"更新時間 {updated_at}" + (" · 可能已中斷" if stale else ""))

        st.progress(pct / 100, text=f"{label} · {pct:.1f}%")
        if message:
            st.caption(_status_message_zh(str(message)))
        errors = data.get("errors") if isinstance(data.get("errors"), list) else []
        if errors:
            st.error(errors[-1].get("message", "本機候選刷新失敗"))


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


def _render_opportunities(summary: dict | None) -> None:
    st.subheader("候選來源")
    left, right = st.columns(2)

    with left:
        st.markdown("##### 篩選器候選")
        ranked = (summary or {}).get("ranked_picks") or []
        candidates = ranked if ranked else (_ranked_candidates() or _scored_candidates())
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
        signals = _flow_signals()
        if signals:
            st.dataframe(_flow_df(signals), hide_index=True, use_container_width=True, height=260)
            ticker = str(signals[0].get("ticker", "")).upper()
            _shared.ticker_action_buttons(ticker, "td_flow")
        else:
            st.info("尚無 options-flow latest.json。")
            _jump("🚨 異常流", "options-flow", key="td_flow_empty")


def _render_risk_and_research() -> None:
    st.subheader("持倉與驗證")
    c1, c2, c3, c4 = st.columns(4)

    rec = _shared.load_reconciliation() or {}
    held = (rec.get("matched") or []) + (rec.get("held_not_in_ledger") or [])
    rev = _shared.load_json(str(_REVERSAL_DIR / "latest.json")) or {}
    oversold = _shared.load_json(str(_OVERSOLD_DIR / "latest.json")) or {}
    ledger = _shared.load_ledger()

    _shared.metric_card(c1, "IBKR 底層", len({r.get("ticker") for r in held if r.get("ticker")}))
    _shared.metric_card(c2, "反轉候選", rev.get("match_count", "-"))
    _shared.metric_card(c3, "蓄勢候選", oversold.get("match_count", "-"))
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

    _render_candidate_pipeline_controls()
    _render_local_refresh_status()
    _render_candidate_results()

    summary_date, summary = _latest_daily_summary()
    thesis = _latest_market_thesis()

    _render_gate(summary_date, summary, thesis)
    st.divider()
    _render_trust_boundary()
    st.divider()
    _render_opportunities(summary)
    st.divider()
    _render_risk_and_research()
