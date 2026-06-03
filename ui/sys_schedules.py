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
    refl_dir = _shared.REPORTS_DIR / "reflections"
    if not refl_dir.exists():
        return None
    files = sorted(refl_dir.glob("*.md"), reverse=True)
    if not files:
        return None
    latest = files[0]
    try:
        head = latest.read_text(encoding="utf-8").strip().splitlines()[:3]
    except Exception:
        head = []
    blurb = f"📝 最新反思:`{latest.name}`"
    if head:
        blurb += "\n\n" + "\n".join(head)
    return blurb


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


_RESULT_FETCHERS = {
    "report_dir": _latest_report_result,
    "ledger": _latest_ledger_result,
    "reflection": _latest_reflection_result,
    "crypto_universe": _latest_crypto_result,
    "cot": _latest_cot_result,
    "options_flow": _latest_options_flow_result,
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
