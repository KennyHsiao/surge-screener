"""關注博主清單 — 依功能分類的 X 博主名單.

Cross-market reference list read from content/influencers.json. The same file
feeds the quick-pick selector on the X 社群情緒 pages, so the directory and the
analyzer never drift apart.
"""

import json
import re
from pathlib import Path
from typing import Any

import streamlit as st

from . import _shared


ROSTER_PATH = _shared.CONTENT_DIR / "influencers.json"
_DEFAULT_NOTE = (
    "關注博主清單 — 每筆：handle(不含@)、name、category、market、note、url。"
    "這份清單會餵給 X 社群情緒頁與 Agent Reach bridge。"
)
_MARKETS = ["US", "CRYPTO"]
_UNCATEGORIZED = "未分類"
_HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")


def _normalise_handle(handle: Any) -> str:
    return str(handle or "").strip().lstrip("@")


def _normalise_market(market: Any) -> str:
    value = str(market or "US").strip().upper()
    return "CRYPTO" if value == "CRYPTO" else "US"


def _normalise_category(category: Any) -> str:
    return str(category or "").strip() or _UNCATEGORIZED


def _normalise_url(handle: str, url: Any) -> str:
    value = str(url or "").strip()
    return value or f"https://x.com/{handle}"


def _normalise_roster(data: dict[str, Any] | None) -> dict[str, Any]:
    src = data if isinstance(data, dict) else {}
    influencers = src.get("influencers") if isinstance(src.get("influencers"), list) else []
    order = [str(c).strip() for c in src.get("categories_order", []) if str(c).strip()]
    for row in influencers:
        if not isinstance(row, dict):
            continue
        category = _normalise_category(row.get("category"))
        if category not in order:
            order.append(category)
    return {
        "_note": str(src.get("_note") or _DEFAULT_NOTE),
        "categories_order": order,
        "influencers": [dict(r) for r in influencers if isinstance(r, dict)],
    }


def load_roster(path: str | Path = ROSTER_PATH) -> dict[str, Any]:
    data = _shared.load_json(str(path))
    return _normalise_roster(data if isinstance(data, dict) else None)


def save_roster(data: dict[str, Any], *, path: str | Path = ROSTER_PATH) -> Path:
    payload = _normalise_roster(data)
    dst = Path(path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(dst)
    try:
        _shared.load_json.clear()
    except Exception:
        pass
    return dst


def add_category(data: dict[str, Any], category: str) -> dict[str, Any]:
    payload = _normalise_roster(data)
    cat = _normalise_category(category)
    if cat not in payload["categories_order"]:
        payload["categories_order"].append(cat)
    return payload


def rename_category(data: dict[str, Any], old: str, new: str) -> dict[str, Any]:
    payload = _normalise_roster(data)
    old_cat = _normalise_category(old)
    new_cat = _normalise_category(new)
    if old_cat == new_cat:
        return payload
    payload["categories_order"] = [
        new_cat if cat == old_cat else cat for cat in payload["categories_order"]
    ]
    if new_cat not in payload["categories_order"]:
        payload["categories_order"].append(new_cat)
    # Remove duplicates while preserving order.
    payload["categories_order"] = list(dict.fromkeys(payload["categories_order"]))
    for row in payload["influencers"]:
        if row.get("category") == old_cat:
            row["category"] = new_cat
    return payload


def delete_category(data: dict[str, Any], category: str, *, fallback: str = _UNCATEGORIZED) -> dict[str, Any]:
    payload = _normalise_roster(data)
    cat = _normalise_category(category)
    fallback_cat = _normalise_category(fallback)
    payload["categories_order"] = [c for c in payload["categories_order"] if c != cat]
    for row in payload["influencers"]:
        if row.get("category") == cat:
            row["category"] = fallback_cat
    if fallback_cat not in payload["categories_order"]:
        payload["categories_order"].append(fallback_cat)
    return payload


def _clean_record(record: dict[str, Any]) -> dict[str, Any]:
    handle = _normalise_handle(record.get("handle"))
    if not _HANDLE_RE.fullmatch(handle):
        raise ValueError("handle must be 1-15 letters/numbers/underscore characters")
    cleaned: dict[str, Any] = {
        "handle": handle,
        "category": _normalise_category(record.get("category")),
        "market": _normalise_market(record.get("market")),
        "url": _normalise_url(handle, record.get("url")),
    }
    for key in ("name", "note"):
        value = str(record.get(key) or "").strip()
        if value:
            cleaned[key] = value
    if record.get("placeholder"):
        cleaned["placeholder"] = True
    return cleaned


def upsert_influencer(
    data: dict[str, Any],
    record: dict[str, Any],
    *,
    original_handle: str | None = None,
    original_market: str | None = None,
) -> dict[str, Any]:
    payload = _normalise_roster(data)
    cleaned = _clean_record(record)
    orig_handle = _normalise_handle(original_handle or cleaned["handle"]).lower()
    orig_market = _normalise_market(original_market or cleaned["market"])
    target_handle = cleaned["handle"].lower()
    target_market = cleaned["market"]
    replaced = False
    rows: list[dict[str, Any]] = []
    for row in payload["influencers"]:
        same_original = (
            _normalise_handle(row.get("handle")).lower() == orig_handle
            and _normalise_market(row.get("market")) == orig_market
        )
        same_target = (
            _normalise_handle(row.get("handle")).lower() == target_handle
            and _normalise_market(row.get("market")) == target_market
        )
        if (same_original or same_target) and not replaced:
            rows.append(cleaned)
            replaced = True
        elif not same_original and not same_target:
            rows.append(row)
    if not replaced:
        rows.append(cleaned)
    payload["influencers"] = rows
    return add_category(payload, cleaned["category"])


def delete_influencer(data: dict[str, Any], handle: str, market: str) -> dict[str, Any]:
    payload = _normalise_roster(data)
    target_handle = _normalise_handle(handle).lower()
    target_market = _normalise_market(market)
    payload["influencers"] = [
        row for row in payload["influencers"]
        if not (
            _normalise_handle(row.get("handle")).lower() == target_handle
            and _normalise_market(row.get("market")) == target_market
        )
    ]
    return payload


def load_influencers() -> tuple[list[dict], list[str]]:
    data = load_roster()
    return data.get("influencers", []), data.get("categories_order", [])


def for_market(market: str) -> list[dict]:
    """Real influencers for a market (US/CRYPTO), grouped order preserved.

    Placeholder/template rows are excluded — this feeds the live X analyzer, so
    a fake handle must never become selectable there.
    """
    influencers, order = load_influencers()
    members = [i for i in influencers
               if i.get("market") == market and not i.get("placeholder")]
    rank = {c: n for n, c in enumerate(order)}
    members.sort(key=lambda i: (rank.get(i.get("category", ""), 999),
                                i.get("category", ""), i.get("handle", "")))
    return members


def render() -> None:
    st.header("👥 關注博主清單")
    st.caption("依功能分類的 X 博主名單(`content/influencers.json`)。"
               "「X 社群情緒」與 Agent Reach bridge 會讀這份名冊。")

    roster = load_roster()
    _render_roster_editor(roster)

    influencers, order = roster.get("influencers", []), roster.get("categories_order", [])
    if not influencers:
        st.info("尚無博主。可用上方表單新增。")
        return

    markets = ["全部"] + sorted({i.get("market", "US") for i in influencers})
    mk = st.radio("市場", markets, horizontal=True)
    items = [i for i in influencers if mk == "全部" or i.get("market") == mk]
    n_influencers = len([i for i in items if not i.get("placeholder")])
    cats_present = len({i.get("category", "未分類") for i in items})
    st.caption(f"{n_influencers} 位博主 / {cats_present} 個分類")

    # category order: explicit order first, then any extras alphabetically
    cats = list(dict.fromkeys(order + sorted({i.get("category", "未分類") for i in items})))

    shown = 0
    for cat in cats:
        members = [i for i in items if i.get("category", "未分類") == cat]
        if not members:
            continue
        real = [m for m in members if not m.get("placeholder")]
        st.subheader(f"📂 {cat}  ({len(real)})")
        n_cols = min(2, len(members))
        cols = st.columns(n_cols)
        for n, inf in enumerate(members):
            with cols[n % n_cols].container(border=True):
                if inf.get("placeholder"):
                    st.markdown(f"🧩 *{inf.get('name', '(模板)')}*")
                    if inf.get("note"):
                        st.caption(inf["note"])
                    continue
                shown += 1
                handle = inf.get("handle", "")
                url = inf.get("url") or f"https://x.com/{handle}"
                market_val = inf.get("market", "")
                is_crypto = market_val.upper() == "CRYPTO"
                market_color = _shared.BLUE if is_crypto else _shared.AMBER
                st.markdown(f"**{inf.get('name', handle)}**")
                _shared.chips_row([(market_val, market_color)] if market_val else [])
                st.markdown(f"[@{handle}]({url})")
                if inf.get("note"):
                    st.caption(inf["note"])
                _render_influencer_actions(roster, inf)

    if shown == 0:
        st.info("此市場底下尚無(非模板)博主。")


def _category_options(roster: dict[str, Any]) -> list[str]:
    cats = [
        str(c).strip()
        for c in roster.get("categories_order", [])
        if str(c).strip()
    ]
    for row in roster.get("influencers", []):
        cat = _normalise_category(row.get("category"))
        if cat not in cats:
            cats.append(cat)
    return cats or [_UNCATEGORIZED]


def _save_and_rerun(roster: dict[str, Any]) -> None:
    save_roster(roster)
    st.success("名冊已更新")
    st.rerun()


def _render_roster_editor(roster: dict[str, Any]) -> None:
    categories = _category_options(roster)
    with st.expander("名冊管理", expanded=False):
        add_tab, cat_tab, raw_tab = st.tabs(["新增博主", "分類清單", "JSON"])
        with add_tab:
            with st.form("influencer_add_form", clear_on_submit=True):
                c1, c2, c3 = st.columns([1, 1, 1])
                handle = c1.text_input("帳號", placeholder="Remzztrades")
                name = c2.text_input("名稱")
                market = c3.selectbox("市場", _MARKETS)
                c4, c5 = st.columns([1, 2])
                category = c4.selectbox("分類", categories)
                new_category = c4.text_input("新分類")
                note = c5.text_area("備註", height=76)
                url = st.text_input("URL", placeholder="https://x.com/handle")
                submitted = st.form_submit_button("新增 / 更新", type="primary")
                if submitted:
                    try:
                        next_roster = upsert_influencer(roster, {
                            "handle": handle,
                            "name": name,
                            "market": market,
                            "category": new_category or category,
                            "note": note,
                            "url": url,
                        })
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        _save_and_rerun(next_roster)

        with cat_tab:
            with st.form("influencer_category_form"):
                c1, c2, c3 = st.columns([1, 1, 1])
                selected = c1.selectbox("分類", categories, key="category_selected")
                renamed = c2.text_input("改名為", value=selected)
                added = c3.text_input("新增分類")
                action = st.radio("動作", ["改名", "新增", "刪除"], horizontal=True)
                submitted = st.form_submit_button("套用分類")
                if submitted:
                    if action == "新增":
                        next_roster = add_category(roster, added)
                    elif action == "刪除":
                        next_roster = delete_category(roster, selected)
                    else:
                        next_roster = rename_category(roster, selected, renamed)
                    _save_and_rerun(next_roster)
            st.caption("刪除分類時，該分類下的博主會移到「未分類」。")

        with raw_tab:
            raw = st.text_area(
                "名冊 JSON",
                value=json.dumps(roster, indent=2, ensure_ascii=False),
                height=320,
            )
            if st.button("保存 JSON", type="primary"):
                try:
                    parsed = json.loads(raw)
                    if not isinstance(parsed, dict):
                        raise ValueError("JSON root must be an object")
                except Exception as exc:
                    st.error(f"JSON 格式錯誤: {exc}")
                else:
                    _save_and_rerun(parsed)


def _render_influencer_actions(roster: dict[str, Any], inf: dict[str, Any]) -> None:
    handle = _normalise_handle(inf.get("handle"))
    market = _normalise_market(inf.get("market"))
    if not handle:
        return
    with st.expander("編輯", expanded=False):
        categories = _category_options(roster)
        current_cat = _normalise_category(inf.get("category"))
        if current_cat not in categories:
            categories.append(current_cat)
        key_base = f"{market}_{handle}".replace("-", "_").replace(".", "_")
        with st.form(f"influencer_edit_{key_base}"):
            c1, c2, c3 = st.columns([1, 1, 1])
            next_handle = c1.text_input("帳號", value=handle, key=f"{key_base}_handle")
            next_name = c2.text_input("名稱", value=str(inf.get("name") or ""), key=f"{key_base}_name")
            next_market = c3.selectbox("市場", _MARKETS, index=_MARKETS.index(market), key=f"{key_base}_market")
            category = st.selectbox(
                "分類",
                categories,
                index=categories.index(current_cat),
                key=f"{key_base}_category",
            )
            note = st.text_area("備註", value=str(inf.get("note") or ""), height=70, key=f"{key_base}_note")
            url = st.text_input("URL", value=str(inf.get("url") or f"https://x.com/{handle}"), key=f"{key_base}_url")
            c_save, c_delete = st.columns([1, 1])
            save_clicked = c_save.form_submit_button("保存")
            delete_clicked = c_delete.form_submit_button("刪除")
            if save_clicked:
                try:
                    next_roster = upsert_influencer(
                        roster,
                        {
                            "handle": next_handle,
                            "name": next_name,
                            "market": next_market,
                            "category": category,
                            "note": note,
                            "url": url,
                        },
                        original_handle=handle,
                        original_market=market,
                    )
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    _save_and_rerun(next_roster)
            if delete_clicked:
                _save_and_rerun(delete_influencer(roster, handle, market))
