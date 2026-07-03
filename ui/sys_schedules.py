"""系統 · 排程與執行結果.

Reads content/schedules.json (a UI-side registry, not live GitHub Actions
state) and shows, per schedule, the most recent committed output. The schedule
set and what counts as a "result" is an initial proposal — pending the user's
full spec. schedules.json is the extension point: add crypto schedules by
appending an entry.
"""

import json

import streamlit as st

from . import _shared


def _load_schedules() -> list[dict]:
    path = _shared.CONTENT_DIR / "schedules.json"
    data = _shared.load_json(str(path))
    if not data:
        return []
    return data.get("schedules", [])


def _latest_report_result() -> str | None:
    """Newest reports/YYYY-MM-DD/summary.json — return a short markdown blurb."""
    dates = _shared.find_report_dates()
    if not dates:
        return None
    latest = dates[0]
    summary = _shared.load_json(str(_shared.REPORTS_DIR / latest / "summary.json"))
    if not summary:
        return f"最新報告資料夾:`{latest}`(無 summary.json)"
    # Canonical keys written by scripts/04_build_report.py: report_date /
    # total_confirmed / ranked_picks[].ticker (see 06_append_ledger.py:52).
    report_date = summary.get("report_date", latest)
    confirmed = summary.get("total_confirmed", "?")
    lines = [f"📅 報告日期:**{report_date}**", f"✅ 確認檔數:**{confirmed}**"]
    picks = summary.get("ranked_picks", [])
    if isinstance(picks, list) and picks:
        names = [p.get("ticker", "?") if isinstance(p, dict) else str(p) for p in picks[:5]]
        lines.append("🔝 " + ", ".join(f"${n}" for n in names))
    return "\n\n".join(lines)


def _latest_ledger_result() -> str | None:
    df = _shared.load_ledger()
    if df is None or df.empty:
        return None
    last_scan = df["scan_date"].max()
    last_scan_str = last_scan.date().isoformat() if last_scan is not None else "?"
    return f"📒 帳本筆數:**{len(df)}**\n\n🕒 最新掃描日期:**{last_scan_str}**"


def _latest_reflection_result() -> str | None:
    detail = _latest_reflection_detail()
    if not detail:
        return None
    return detail["summary"]


def _latest_reflection_detail() -> dict[str, str] | None:
    refl_dir = _shared.REPORTS_DIR / "reflections"
    if not refl_dir.exists():
        return None
    files = sorted(refl_dir.glob("*.md"), reverse=True)
    if not files:
        return None
    latest = files[0]
    try:
        text = latest.read_text(encoding="utf-8")
    except Exception:
        text = ""
    head = text.strip().splitlines()[:3]
    blurb = f"📝 最新反思:`{latest.name}`"
    if head:
        blurb += "\n\n" + "\n".join(head)
    return {
        "name": latest.name,
        "summary": blurb,
        "text": text,
    }


def _extract_llm_reflection_json(text: str) -> dict | None:
    marker = "## LLM Reflection"
    marker_at = text.find(marker)
    if marker_at < 0:
        return None

    body = text[marker_at + len(marker):].strip()
    if body.startswith("```"):
        lines = body.splitlines()
        for i, line in enumerate(lines[1:], start=1):
            if line.strip().startswith("```"):
                body = "\n".join(lines[1:i]).strip()
                break

    brace_at = body.find("{")
    if brace_at < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for i, ch in enumerate(body[brace_at:], start=brace_at):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(body[brace_at:i + 1])
                except Exception:
                    return None
                return data if isinstance(data, dict) else None
    return None


def _markdown_bullets(values: list) -> str:
    lines = []
    for value in values:
        if value:
            lines.append(f"- {value}")
    return "\n".join(lines)


def _render_reflection_summary(data: dict) -> None:
    st.markdown("### 人讀摘要")

    warning = data.get("sample_size_warning")
    if isinstance(warning, dict) and warning.get("message"):
        st.warning(warning["message"])

    narrative = data.get("narrative_summary")
    if narrative:
        st.markdown(str(narrative))

    flags = data.get("data_quality_flags")
    if isinstance(flags, list) and flags:
        st.markdown("#### 資料缺口")
        st.markdown(_markdown_bullets(flags))

    actions = data.get("proposed_prompt_changes")
    if isinstance(actions, list) and actions:
        st.markdown("#### 建議行動")
        for action in actions:
            if not isinstance(action, dict):
                continue
            change = action.get("suggested_change") or action.get("section") or "Review"
            rationale = action.get("rationale") or ""
            needs_user = action.get("user_action_required")
            suffix = "（需人工處理）" if needs_user else ""
            st.markdown(f"- **{change}**{suffix}\n\n  {rationale}")


def _render_reflection_detail(detail: dict[str, str]) -> None:
    text = detail.get("text", "")
    data = _extract_llm_reflection_json(text)
    if data:
        summary_tab, json_tab, markdown_tab = st.tabs([
            "人讀摘要",
            "原始 LLM JSON",
            "完整 Markdown 原文",
        ])
        with summary_tab:
            _render_reflection_summary(data)
        with json_tab:
            st.json(data)
        with markdown_tab:
            st.markdown(text)
    else:
        st.markdown(text)

    st.download_button(
        "下載 Markdown",
        data=text,
        file_name=detail["name"],
        mime="text/markdown",
        key=f"download_reflection_{detail['name']}",
    )


def _latest_crypto_result() -> str | None:
    data = _shared.load_json(str(_shared.REPORTS_DIR / "crypto" / "universe_latest.json"))
    if not data:
        return None
    return (f"🪙 USDT 永續:**{data.get('count', '?')}** 檔\n\n"
            f"📅 {data.get('date', '?')} · ➕{len(data.get('added', []))} / "
            f"➖{len(data.get('removed', []))}(對比 {data.get('compared_to') or '無'})")


def _latest_cot_result() -> str | None:
    cot_dir = _shared.REPORTS_DIR / "cot"
    if not cot_dir.exists():
        return None
    files = sorted(cot_dir.glob("*.md"), reverse=True)
    if not files:
        return None
    return f"📑 最新週報:`{files[0].name}`"


def _latest_options_flow_result() -> str | None:
    data = _shared.load_json(str(_shared.REPORTS_DIR / "options_flow" / "latest.json"))
    if not data or not data.get("signals"):
        return None
    sigs = data["signals"]
    bull = sum(1 for s in sigs if s.get("direction") == "bullish")
    bear = sum(1 for s in sigs if s.get("direction") == "bearish")
    top = ", ".join(s.get("ticker", "?") for s in sigs[:5])
    return (f"🚨 {data.get('as_of', '?')} · 偵測 **{data.get('signal_count', len(sigs))}** 筆"
            f"(🟢{bull} / 🔴{bear})\n\n前 5:{top}")


def _latest_candidate_refresh_result() -> str | None:
    ranked = _shared.load_json(str(_shared.candidate_output_path("ranked_candidates.json"))) or {}
    money_flow = _shared.load_json(str(_shared.REPORTS_DIR / "money_flow" / "latest.json")) or {}
    rows = ranked.get("ranked_candidates") if isinstance(ranked.get("ranked_candidates"), list) else []
    if not rows and not money_flow:
        return None

    scan_date = ranked.get("scan_date") or money_flow.get("as_of_date") or "?"
    top = ", ".join(str(row.get("ticker", "?")) for row in rows[:5] if isinstance(row, dict))
    coverage = money_flow.get("coverage") if isinstance(money_flow.get("coverage"), dict) else {}
    publishable = "可發布" if money_flow.get("publishable") else "未達門檻"
    ratio = coverage.get("coverage_ratio")
    ratio_text = f"{float(ratio) * 100:.0f}%" if isinstance(ratio, (int, float)) else "-"
    return (
        f"📅 {scan_date} · 排名 **{len(rows)}** 檔"
        f"\n\n資金流:{publishable} · 覆蓋率 **{ratio_text}**"
        + (f"\n\n前 5:{top}" if top else "")
    )


_RESULT_FETCHERS = {
    "report_dir": _latest_report_result,
    "ledger": _latest_ledger_result,
    "reflection": _latest_reflection_result,
    "crypto_universe": _latest_crypto_result,
    "cot": _latest_cot_result,
    "options_flow": _latest_options_flow_result,
    "candidate_refresh": _latest_candidate_refresh_result,
}


def _status_chip(result: str | None) -> str:
    """Return a chip indicating run status based on whether a result exists."""
    if result:
        return _shared.chip("有資料", _shared.GREEN)
    return _shared.chip("無資料", _shared.MUTED)


def render() -> None:
    st.header("⏱ 排程與執行結果")
    st.caption(
        "目前顯示的是 UI 端登錄表(`content/schedules.json`)+ 讀取已 commit 的最新產出。"
        "排程清單與「執行結果」的詳細定義為**初版提案**,待規格補完;之後要納管真實跑批狀態可再接 GitHub Actions API。"
    )

    schedules = _load_schedules()
    if not schedules:
        st.info("找不到 `content/schedules.json`,或內容為空。")
        return

    _CAT_ORDER = ["美股", "系統", "幣圈"]
    raw_cats = {s.get("category", "未分類") for s in schedules}
    ordered_cats = [c for c in _CAT_ORDER if c in raw_cats] + sorted(raw_cats - set(_CAT_ORDER))
    categories = ["全部"] + ordered_cats
    chosen = st.radio("分類", categories, horizontal=True)

    for sch in schedules:
        category = sch.get("category", "未分類")
        if chosen != "全部" and category != chosen:
            continue

        fetcher = _RESULT_FETCHERS.get(sch.get("result_type"))
        result = fetcher() if fetcher else None
        reflection_detail = (
            _latest_reflection_detail()
            if result and sch.get("result_type") == "reflection"
            else None
        )

        with st.container(border=True):
            # Fix 1: two-column layout — left=meta, right=status+result
            col_left, col_right = st.columns([3, 2])

            with col_left:
                # Name + category chip inline on one line
                name_text = sch.get("name", sch.get("id", "?"))
                cat_chip_html = _shared.chip(category, _shared.BLUE)
                st.markdown(
                    f"<h3 style='margin:0 0 .3rem'>{name_text} &nbsp; {cat_chip_html}</h3>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"🗓 `{sch.get('cron', '?')}`  ·  {sch.get('cron_note', '')}"
                )
                if sch.get("description"):
                    st.caption(sch["description"])

            with col_right:
                # Fix 1: prominent status chip at the top of the right column
                st.markdown(
                    _status_chip(result),
                    unsafe_allow_html=True,
                )
                st.markdown("**最近一次執行結果**")
                if result:
                    # Fix 2: use st.markdown instead of st.success to avoid
                    # the green background that hurts CJK readability
                    st.markdown(result)
                else:
                    st.caption("尚無可顯示的產出(管線可能還沒跑過,或尚未接上)。")

            if reflection_detail:
                if reflection_detail.get("text"):
                    with st.expander("查看完整反思", expanded=False):
                        _render_reflection_detail(reflection_detail)
                else:
                    st.caption("反思檔存在,但完整內容無法讀取。")
