"""關注博主清單 — 依功能分類的 X 博主名單.

Cross-market reference list read from content/influencers.json. The same file
feeds the quick-pick selector on the X 社群情緒 pages, so the directory and the
analyzer never drift apart.
"""

import json
import re
import csv
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
_ALL = "全部"
_BULK_MODE_LABELS = {
    "preserve": "保留既有欄位",
    "only_new": "只新增",
    "overwrite": "完全覆蓋",
}
_BULK_MODE_HELP = (
    "保留既有欄位: 只更新貼上內容有提供的欄位; "
    "只新增: 已存在的 market+handle 會略過; "
    "完全覆蓋: 以貼上資料取代既有資料。"
)
_APPLY_ACTIONS = {"新增", "更新"}
_UNDO_DELETE_KEY = "influencer_last_deleted"
_HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")
_X_URL_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})(?:[/?#].*)?$",
    re.IGNORECASE,
)


def _normalise_handle(handle: Any) -> str:
    raw = str(handle or "").strip().lstrip("@")
    match = _X_URL_RE.match(raw)
    if match:
        return match.group(1)
    return raw


def _normalise_market(market: Any) -> str:
    value = str(market or "US").strip().upper()
    return "CRYPTO" if value == "CRYPTO" else "US"


def _normalise_category(category: Any) -> str:
    return str(category or "").strip() or _UNCATEGORIZED


def _normalise_bulk_mode(mode: str | None) -> str:
    value = str(mode or "overwrite").strip()
    if value in _BULK_MODE_LABELS:
        return value
    for key, label in _BULK_MODE_LABELS.items():
        if value == label:
            return key
    raise ValueError(f"unknown bulk import mode: {mode}")


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
    payload, _removed = delete_influencer_with_snapshot(data, handle, market)
    return payload


def delete_influencer_with_snapshot(
    data: dict[str, Any],
    handle: str,
    market: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = _normalise_roster(data)
    target_handle = _normalise_handle(handle).lower()
    target_market = _normalise_market(market)
    kept: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for row in payload["influencers"]:
        is_target = (
            _normalise_handle(row.get("handle")).lower() == target_handle
            and _normalise_market(row.get("market")) == target_market
        )
        if is_target:
            removed.append(dict(row))
        else:
            kept.append(row)
    payload["influencers"] = kept
    return payload, removed


def _csv_dialect(lines: list[tuple[int, str]]) -> type[csv.Dialect]:
    sample = "\n".join(line for _idx, line in lines)
    return csv.excel_tab if "\t" in sample and "," not in sample else csv.excel


def _read_csv_cells(line: str, dialect: type[csv.Dialect]) -> list[str]:
    return [cell.strip() for cell in next(csv.reader([line], dialect=dialect))]


def _normalised_x_url(value: str) -> str:
    handle = _normalise_handle(value)
    return f"https://x.com/{handle}" if handle else str(value or "").strip()


def _bulk_record_from_cells(
    cells: list[str],
    *,
    default_market: str,
    default_category: str,
) -> tuple[dict[str, Any], set[str]]:
    if not cells or not cells[0].strip():
        raise ValueError("handle is required")
    first = cells[0].strip()
    first_is_url = bool(_X_URL_RE.match(first.lstrip("@")))
    record: dict[str, Any] = {
        "handle": first,
        "name": cells[1] if len(cells) > 1 else "",
        "category": cells[2] if len(cells) > 2 and cells[2] else default_category,
        "market": cells[3] if len(cells) > 3 and cells[3] else default_market,
        "note": cells[4] if len(cells) > 4 else "",
        "url": cells[5] if len(cells) > 5 else (_normalised_x_url(first) if first_is_url else ""),
    }
    provided = {"handle"}
    if first_is_url:
        provided.add("url")
    for key, idx in (("name", 1), ("category", 2), ("market", 3), ("note", 4), ("url", 5)):
        if len(cells) > idx and cells[idx]:
            provided.add(key)
    return record, provided


def _bulk_record_from_dict(
    raw: dict[str, str],
    *,
    default_market: str,
    default_category: str,
) -> tuple[dict[str, Any], set[str]]:
    raw_handle = (raw.get("handle") or raw.get("account") or raw.get("url") or "").strip()
    if not raw_handle:
        raise ValueError("handle is required")
    record = {
        "handle": raw_handle,
        "name": raw.get("name") or "",
        "category": raw.get("category") or default_category,
        "market": raw.get("market") or default_market,
        "note": raw.get("note") or "",
        "url": raw.get("url") or "",
    }
    provided = {"handle"}
    for key in ("name", "category", "market", "note", "url"):
        if str(raw.get(key) or "").strip():
            provided.add(key)
    if not raw.get("handle") and raw.get("url"):
        provided.add("url")
    return record, provided


def _existing_influencer(
    data: dict[str, Any],
    handle: str,
    market: str,
) -> dict[str, Any] | None:
    target_handle = _normalise_handle(handle).lower()
    target_market = _normalise_market(market)
    for row in data.get("influencers", []):
        if (
            _normalise_handle(row.get("handle")).lower() == target_handle
            and _normalise_market(row.get("market")) == target_market
        ):
            return row
    return None


def _bulk_preview_row(
    *,
    line_number: int,
    action: str,
    record: dict[str, Any] | None = None,
    error: str = "",
) -> dict[str, Any]:
    row: dict[str, Any] = {"line": line_number, "action": action}
    if record:
        row.update({
            "handle": record.get("handle", ""),
            "market": record.get("market", ""),
            "category": record.get("category", ""),
            "name": record.get("name", ""),
            "note": record.get("note", ""),
            "url": record.get("url", ""),
            "_record": record,
        })
    if error:
        row["error"] = error
    return row


def preview_bulk_import(
    data: dict[str, Any],
    text: str,
    *,
    default_market: str = "US",
    default_category: str = _UNCATEGORIZED,
    mode: str = "preserve",
) -> list[dict[str, Any]]:
    payload = _normalise_roster(data)
    bulk_mode = _normalise_bulk_mode(mode)
    lines = [
        (idx, line.strip())
        for idx, line in enumerate(str(text or "").splitlines(), start=1)
        if line.strip()
    ]
    if not lines:
        return []

    dialect = _csv_dialect(lines)
    try:
        first_cells = [c.strip().lower() for c in _read_csv_cells(lines[0][1], dialect)]
    except Exception as exc:
        return [_bulk_preview_row(line_number=lines[0][0], action="錯誤", error=str(exc))]

    known = {"handle", "account", "name", "category", "market", "note", "url"}
    has_header = any(cell in known for cell in first_cells)
    seen: set[tuple[str, str]] = set()
    preview: list[dict[str, Any]] = []

    if has_header:
        headers = first_cells
        source_lines = lines[1:]
    else:
        headers = []
        source_lines = lines

    for line_number, line in source_lines:
        try:
            cells = _read_csv_cells(line, dialect)
            if has_header:
                raw = {headers[idx]: cells[idx] if idx < len(cells) else "" for idx in range(len(headers))}
                record, provided = _bulk_record_from_dict(
                    raw,
                    default_market=default_market,
                    default_category=default_category,
                )
            else:
                record, provided = _bulk_record_from_cells(
                    cells,
                    default_market=default_market,
                    default_category=default_category,
                )
            cleaned = _clean_record(record)
        except Exception as exc:
            preview.append(_bulk_preview_row(
                line_number=line_number,
                action="錯誤",
                error=str(exc),
            ))
            continue

        cleaned["_provided_fields"] = sorted(provided)
        key = (cleaned["handle"].lower(), cleaned["market"])
        if key in seen:
            action = "重複略過"
        else:
            seen.add(key)
            exists = _existing_influencer(payload, cleaned["handle"], cleaned["market"])
            if exists and bulk_mode == "only_new":
                action = "略過"
            else:
                action = "更新" if exists else "新增"
        preview.append(_bulk_preview_row(line_number=line_number, action=action, record=cleaned))

    return preview


def parse_bulk_influencers(
    text: str,
    *,
    default_market: str = "US",
    default_category: str = _UNCATEGORIZED,
) -> list[dict[str, Any]]:
    """Parse pasted influencer rows.

    Supported formats:
    - one handle or X URL per line
    - CSV/TSV rows: handle,name,category,market,note,url
    - CSV with a header containing any of those column names
    """
    preview = preview_bulk_import(
        {"influencers": []},
        text,
        default_market=default_market,
        default_category=default_category,
        mode="overwrite",
    )
    errors = [row for row in preview if row.get("action") == "錯誤"]
    if errors:
        first = errors[0]
        raise ValueError(f"第 {first.get('line')} 行: {first.get('error')}")
    return [
        dict(row["_record"])
        for row in preview
        if row.get("action") in _APPLY_ACTIONS and isinstance(row.get("_record"), dict)
    ]


def _merge_preserving_existing(
    existing: dict[str, Any],
    incoming: dict[str, Any],
    provided_fields: set[str],
) -> dict[str, Any]:
    merged = dict(existing)
    merged["handle"] = incoming["handle"]
    merged["market"] = incoming["market"]
    for key in ("category", "name", "note", "url"):
        if key in provided_fields or not str(merged.get(key) or "").strip():
            if key in incoming:
                merged[key] = incoming[key]
            elif key in provided_fields:
                merged.pop(key, None)
    return _clean_record(merged)


def bulk_upsert_influencers(
    data: dict[str, Any],
    records: list[dict[str, Any]],
    *,
    mode: str = "overwrite",
) -> dict[str, Any]:
    bulk_mode = _normalise_bulk_mode(mode)
    payload = _normalise_roster(data)
    for record in records:
        cleaned = _clean_record(record)
        provided_fields = set(record.get("_provided_fields") or cleaned.keys())
        existing = _existing_influencer(payload, cleaned["handle"], cleaned["market"])
        if existing and bulk_mode == "only_new":
            continue
        if existing and bulk_mode == "preserve":
            cleaned = _merge_preserving_existing(existing, cleaned, provided_fields)
        payload = upsert_influencer(
            payload,
            cleaned,
            original_handle=cleaned["handle"],
            original_market=cleaned["market"],
        )
    return payload


def apply_bulk_import(
    data: dict[str, Any],
    preview_rows: list[dict[str, Any]],
    *,
    mode: str = "preserve",
) -> dict[str, Any]:
    records = [
        dict(row["_record"])
        for row in preview_rows
        if row.get("action") in _APPLY_ACTIONS and isinstance(row.get("_record"), dict)
    ]
    return bulk_upsert_influencers(data, records, mode=mode)


def filter_influencers(
    items: list[dict[str, Any]],
    *,
    query: str = "",
    category: str = _ALL,
    data_status: str = _ALL,
) -> list[dict[str, Any]]:
    q = str(query or "").strip().lower()
    cat = str(category or _ALL).strip()
    status = str(data_status or _ALL).strip()
    result: list[dict[str, Any]] = []
    for row in items:
        if cat != _ALL and _normalise_category(row.get("category")) != cat:
            continue
        if q:
            haystack = " ".join(
                str(row.get(key) or "")
                for key in ("handle", "name", "category", "market", "note", "url")
            ).lower()
            if q not in haystack:
                continue
        if status == "缺名稱" and str(row.get("name") or "").strip():
            continue
        if status == "缺備註" and str(row.get("note") or "").strip():
            continue
        if status == "缺 URL" and str(row.get("url") or "").strip():
            continue
        if status == "模板" and not row.get("placeholder"):
            continue
        if status == "非模板" and row.get("placeholder"):
            continue
        result.append(row)
    return result


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
    _render_delete_undo(roster)
    _render_roster_editor(roster)

    influencers, order = roster.get("influencers", []), roster.get("categories_order", [])
    if not influencers:
        st.info("尚無博主。可用上方表單新增。")
        return

    markets = [_ALL] + sorted({i.get("market", "US") for i in influencers})
    mk = st.radio("市場", markets, horizontal=True)
    market_items = [i for i in influencers if mk == _ALL or i.get("market") == mk]
    filter_cats = [_ALL] + list(dict.fromkeys(
        order + sorted({_normalise_category(i.get("category")) for i in market_items})
    ))
    c_search, c_cat, c_status = st.columns([2, 1, 1])
    query = c_search.text_input("搜尋帳號 / 名稱 / 備註", placeholder="Remzz、macro、flow")
    category_filter = c_cat.selectbox("分類篩選", filter_cats)
    data_status = c_status.selectbox("資料狀態", [_ALL, "缺名稱", "缺備註", "缺 URL", "模板", "非模板"])
    items = filter_influencers(
        market_items,
        query=query,
        category=category_filter,
        data_status=data_status,
    )
    n_total = len([i for i in market_items if not i.get("placeholder")])
    n_filtered = len([i for i in items if not i.get("placeholder")])
    cats_present = len({_normalise_category(i.get("category")) for i in items})
    st.caption(f"顯示 {n_filtered} / {n_total} 位博主 · {cats_present} 個分類")

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
        st.info("目前篩選條件沒有符合的非模板博主。")


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


def _render_delete_undo(roster: dict[str, Any]) -> None:
    deleted = st.session_state.get(_UNDO_DELETE_KEY)
    if not isinstance(deleted, dict) or not deleted.get("handle"):
        return
    label = f"@{deleted.get('handle')} ({_normalise_market(deleted.get('market'))})"
    with st.container(border=True):
        st.warning(f"已刪除 {label}。")
        c_restore, c_clear = st.columns([1, 5])
        if c_restore.button("復原刪除", type="primary", key="influencer_restore_deleted"):
            st.session_state.pop(_UNDO_DELETE_KEY, None)
            _save_and_rerun(upsert_influencer(roster, deleted))
        if c_clear.button("清除提示", key="influencer_clear_deleted"):
            st.session_state.pop(_UNDO_DELETE_KEY, None)
            st.rerun()


def _render_roster_editor(roster: dict[str, Any]) -> None:
    categories = _category_options(roster)
    with st.expander("名冊管理", expanded=False):
        add_tab, bulk_tab, cat_tab, raw_tab = st.tabs(["新增博主", "批次匯入", "分類清單", "進階 JSON"])
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

        with bulk_tab:
            c_mode, c_cat, c_market = st.columns([2, 1, 1])
            mode_label = c_mode.radio(
                "匯入模式",
                list(_BULK_MODE_LABELS.values()),
                horizontal=True,
                help=_BULK_MODE_HELP,
            )
            mode = _normalise_bulk_mode(mode_label)
            default_category = c_cat.selectbox("預設分類", categories, key="bulk_category")
            default_market = c_market.selectbox("預設市場", _MARKETS, key="bulk_market")
            bulk_text = st.text_area(
                "貼上名單",
                height=220,
                placeholder=(
                    "@StockMKTNewz\n"
                    "https://x.com/zerohedge\n"
                    "handle,name,category,market,note,url\n"
                    "WatcherGuru,Watcher.Guru,Crypto,CRYPTO,news,https://x.com/WatcherGuru"
                ),
                help="支援一行一個 @handle / X URL，或 CSV/TSV: handle,name,category,market,note,url。",
            )
            preview_clicked = st.button("預覽批次匯入", key="bulk_preview")
            import_clicked = st.button("匯入 / 更新名冊", type="primary", key="bulk_import")
            if preview_clicked or import_clicked:
                rows = preview_bulk_import(
                    roster,
                    bulk_text,
                    default_market=default_market,
                    default_category=default_category,
                    mode=mode,
                )
                errors = [row for row in rows if row.get("action") == "錯誤"]
                applicable = [row for row in rows if row.get("action") in _APPLY_ACTIONS]
                if rows:
                    st.dataframe(
                        [
                            {
                                "行": row.get("line"),
                                "動作": row.get("action"),
                                "帳號": row.get("handle", ""),
                                "市場": row.get("market", ""),
                                "分類": row.get("category", ""),
                                "名稱": row.get("name", ""),
                                "備註": row.get("note", ""),
                                "URL": row.get("url", ""),
                                "錯誤": row.get("error", ""),
                            }
                            for row in rows
                        ],
                        hide_index=True,
                        use_container_width=True,
                    )
                    st.caption(
                        f"將套用 {len(applicable)} 筆；錯誤 {len(errors)} 筆；"
                        f"目前模式：{mode_label}。"
                    )
                    if errors:
                        st.error("有錯誤列，修正後再匯入；錯誤列不會寫入名冊。")
                else:
                    st.info("沒有可匯入的帳號。")
                if import_clicked and errors:
                    st.warning("未匯入：請先修正錯誤列。")
                elif import_clicked and applicable:
                    _save_and_rerun(apply_bulk_import(roster, rows, mode=mode))
                elif import_clicked:
                    st.info("沒有需要匯入 / 更新的帳號。")

        with cat_tab:
            with st.form("influencer_category_form"):
                c1, c2, c3 = st.columns([1, 1, 1])
                selected = c1.selectbox("分類", categories, key="category_selected")
                renamed = c2.text_input("改名為", value=selected)
                added = c3.text_input("新增分類")
                action = st.radio("動作", ["改名", "新增", "刪除"], horizontal=True)
                confirm_category_delete = st.checkbox(
                    "確認刪除分類",
                    help="只在動作選「刪除」時生效；該分類下的博主會移到「未分類」。",
                )
                submitted = st.form_submit_button("套用分類")
                if submitted:
                    if action == "新增":
                        next_roster = add_category(roster, added)
                    elif action == "刪除":
                        if not confirm_category_delete:
                            st.warning("未刪除：請先勾選確認刪除分類。")
                            return
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
            confirm_delete = st.checkbox(
                f"確認刪除 @{handle}",
                key=f"{key_base}_confirm_delete",
                help="刪除後會在頁面上方提供一次復原刪除。",
            )
            c_save, c_delete = st.columns([1, 1])
            save_clicked = c_save.form_submit_button("保存")
            delete_clicked = c_delete.form_submit_button("刪除", disabled=not confirm_delete)
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
                next_roster, removed = delete_influencer_with_snapshot(roster, handle, market)
                if removed:
                    st.session_state[_UNDO_DELETE_KEY] = removed[0]
                _save_and_rerun(next_roster)
