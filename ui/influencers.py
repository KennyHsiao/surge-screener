"""關注博主清單 — 依功能分類的 X 博主名單.

Cross-market reference list read from content/influencers.json. The same file
feeds the quick-pick selector on the X 社群情緒 pages, so the directory and the
analyzer never drift apart.
"""

import csv
import hashlib
import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import streamlit as st

from . import _shared
from scripts import influencer_roster_runtime


DEFAULT_ROSTER_PATH = _shared.CONTENT_DIR / "influencers.json"
ROSTER_PATH = influencer_roster_runtime.resolve_roster_path(default_path=DEFAULT_ROSTER_PATH)
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
_DETAIL_KEY = "influencer_detail_key"
_SEARCH_PREVIEW_KEY = "influencer_search_preview"
_HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")
_X_URL_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})(?:[/?#].*)?$",
    re.IGNORECASE,
)
_AI_CATEGORY_KEYWORDS = {
    "Momentum Options Trade": [
        "option", "options", "flow", "sweep", "premium", "momentum", "trade",
        "trading", "swing", "gamma", "期權", "選擇權", "動能",
    ],
    "Macro / News": [
        "macro", "news", "breaking", "headline", "headlines", "fed", "fomc",
        "cpi", "jobs", "bloomberg", "market news", "tape", "新聞", "總經",
    ],
    "Crypto": [
        "crypto", "bitcoin", "btc", "eth", "ethereum", "sol", "defi", "onchain",
        "鏈上", "幣", "加密",
    ],
}


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


def resolve_roster_path(
    *,
    env: dict[str, str] | None = None,
    default_path: str | Path = DEFAULT_ROSTER_PATH,
    seed: bool = True,
) -> Path:
    return influencer_roster_runtime.resolve_roster_path(
        env=env,
        default_path=default_path,
        seed=seed,
    )


def load_roster(path: str | Path | None = None) -> dict[str, Any]:
    data = _shared.load_json(str(path or ROSTER_PATH))
    return _normalise_roster(data if isinstance(data, dict) else None)


def save_roster(data: dict[str, Any], *, path: str | Path | None = None) -> Path:
    payload = _normalise_roster(data)
    dst = Path(path or ROSTER_PATH)
    write_dst = dst.resolve(strict=False) if dst.is_symlink() else dst
    write_dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = write_dst.with_suffix(write_dst.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(write_dst)
    try:
        _shared.load_json.clear()
    except Exception:
        pass
    return write_dst


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
    if record.get("category_source"):
        cleaned["category_source"] = str(record.get("category_source") or "").strip()
    if record.get("category_reason"):
        cleaned["category_reason"] = str(record.get("category_reason") or "").strip()
    if record.get("category_confidence") not in (None, ""):
        try:
            cleaned["category_confidence"] = round(float(record.get("category_confidence")), 3)
        except (TypeError, ValueError):
            pass
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


def _record_search_text(row: dict[str, Any]) -> str:
    parts = [
        row.get("handle"),
        row.get("name"),
        row.get("category"),
        row.get("market"),
        row.get("note"),
        row.get("url"),
        row.get("description"),
        row.get("bio"),
    ]
    for post in row.get("posts") or []:
        if isinstance(post, dict):
            parts.append(post.get("text"))
    return " ".join(str(part or "") for part in parts).strip()


def _similarity(query: str, value: str) -> float:
    q = query.strip().lower()
    v = value.strip().lower()
    if not q or not v:
        return 0.0
    if q in v:
        return 1.0
    return SequenceMatcher(None, q, v).ratio()


def suggest_ai_category(
    record: dict[str, Any],
    categories: list[str],
    *,
    fallback: str = _UNCATEGORIZED,
) -> dict[str, Any]:
    """Local AI-style category suggestion from profile text.

    This is intentionally deterministic: it gives the UI a default category and
    confidence, while leaving manual override as the final authority.
    """
    if record.get("category_source") == "manual" and record.get("category"):
        return {
            "category": _normalise_category(record.get("category")),
            "confidence": 1.0,
            "source": "manual",
            "reason": "manual override",
        }

    available = list(dict.fromkeys([_normalise_category(c) for c in categories if str(c).strip()]))
    if not available:
        available = [fallback]
    text = _record_search_text(record).lower()
    best_category = fallback if fallback in available else available[0]
    best_matches: list[str] = []
    best_score = 0.0

    for category in available:
        keywords = _AI_CATEGORY_KEYWORDS.get(category) or [
            token
            for token in re.split(r"[^A-Za-z0-9]+", category.lower())
            if len(token) >= 3
        ]
        matches = [kw for kw in keywords if kw.lower() in text]
        score = float(len(matches))
        if _normalise_category(record.get("category")) == category:
            score += 0.6
        if score > best_score:
            best_category = category
            best_matches = matches
            best_score = score

    if best_score <= 0:
        return {
            "category": best_category,
            "confidence": 0.35,
            "source": "ai",
            "reason": "no strong profile keyword match",
        }
    confidence = min(0.92, 0.55 + 0.12 * best_score)
    reason = "matched " + ", ".join(best_matches[:4])
    return {
        "category": best_category,
        "confidence": round(confidence, 2),
        "source": "ai",
        "reason": reason,
    }


def _existing_state(
    roster: dict[str, Any],
    handle: str,
    market: str,
    *,
    name: str = "",
) -> tuple[str, dict[str, Any] | None]:
    clean_handle = _normalise_handle(handle).lower()
    clean_market = _normalise_market(market)
    if not clean_handle:
        return "可加入", None
    same_handle_other_market: dict[str, Any] | None = None
    name_l = str(name or "").strip().lower()
    for row in roster.get("influencers", []):
        row_handle = _normalise_handle(row.get("handle")).lower()
        row_market = _normalise_market(row.get("market"))
        if row_handle == clean_handle and row_market == clean_market:
            return "已加入", row
        if row_handle == clean_handle:
            same_handle_other_market = row
    if same_handle_other_market:
        return "已加入其他市場", same_handle_other_market
    if name_l:
        for row in roster.get("influencers", []):
            existing_name = str(row.get("name") or "").strip().lower()
            if existing_name and _similarity(name_l, existing_name) >= 0.88:
                return "疑似重複", row
    return "可加入", None


def _candidate_action(state: str) -> str:
    if state == "可加入":
        return "加入"
    if state == "疑似重複":
        return "檢查"
    return "查看"


def _candidate_row(
    *,
    roster: dict[str, Any],
    market: str,
    handle: str,
    name: str = "",
    note: str = "",
    url: str = "",
    source: str = "local",
    match: str = "",
    posts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    clean_handle = _normalise_handle(handle)
    clean_market = _normalise_market(market)
    state, existing = _existing_state(roster, clean_handle, clean_market, name=name)
    display_market = _normalise_market((existing or {}).get("market") or clean_market)
    record = {
        "handle": clean_handle,
        "name": name or (existing or {}).get("name", ""),
        "note": note or (existing or {}).get("note", ""),
        "category": (existing or {}).get("category", ""),
        "market": display_market,
        "url": url or (existing or {}).get("url", "") or (f"https://x.com/{clean_handle}" if clean_handle else ""),
        "posts": posts or [],
    }
    suggestion = suggest_ai_category(record, _category_options(roster))
    return {
        "state": state,
        "action": _candidate_action(state),
        "handle": clean_handle,
        "name": record["name"],
        "market": display_market,
        "detail_handle": _normalise_handle((existing or {}).get("handle") or clean_handle),
        "detail_market": display_market,
        "category": (existing or {}).get("category", ""),
        "ai_category": suggestion["category"],
        "ai_confidence": suggestion["confidence"],
        "ai_reason": suggestion["reason"],
        "source": source,
        "match": match,
        "url": record["url"],
        "note": record["note"],
        "_existing": existing,
    }


def build_search_candidates(
    roster: dict[str, Any],
    query: str,
    *,
    market: str = "US",
    preview_payload: dict[str, Any] | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    q = str(query or "").strip()
    if not q and not preview_payload:
        return []
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    if isinstance(preview_payload, dict) and preview_payload.get("handle"):
        handle = _normalise_handle(preview_payload.get("handle"))
        posts = [p for p in (preview_payload.get("posts") or []) if isinstance(p, dict)]
        text_from_posts = " ".join(str(p.get("text") or "") for p in posts[:3])
        row = _candidate_row(
            roster=roster,
            market=market,
            handle=handle,
            name=str(preview_payload.get("name") or ""),
            note=str(preview_payload.get("note") or text_from_posts),
            url=str(preview_payload.get("url") or ""),
            source=str(preview_payload.get("source") or "x_lookup"),
            match="handle lookup",
            posts=posts,
        )
        key = (row["handle"].lower(), row["market"])
        rows.append(row)
        seen.add(key)
        if _is_handle_lookup(q):
            return rows[:limit]

    q_norm = _normalise_handle(q).lower()
    q_text = q.lower()
    local_matches: list[tuple[float, dict[str, Any], str]] = []
    for item in roster.get("influencers", []):
        if not isinstance(item, dict) or item.get("placeholder"):
            continue
        handle = _normalise_handle(item.get("handle"))
        fields = {
            "handle match": handle,
            "display name match": str(item.get("name") or ""),
            "note match": str(item.get("note") or ""),
            "category match": str(item.get("category") or ""),
        }
        best_label = ""
        best_score = 0.0
        for label, value in fields.items():
            score = _similarity(q_norm if label == "handle match" else q_text, str(value or ""))
            if score > best_score:
                best_score = score
                best_label = label
        if best_score >= 0.45:
            local_matches.append((best_score, item, best_label))

    for _score, item, label in sorted(
        local_matches,
        key=lambda x: (-x[0], _normalise_handle(x[1].get("handle")).lower()),
    ):
        row = _candidate_row(
            roster=roster,
            market=_normalise_market(item.get("market")),
            handle=str(item.get("handle") or ""),
            name=str(item.get("name") or ""),
            note=str(item.get("note") or ""),
            url=str(item.get("url") or ""),
            source="local_roster",
            match=label,
        )
        key = (row["handle"].lower(), row["market"])
        if key in seen:
            continue
        rows.append(row)
        seen.add(key)
        if len(rows) >= limit:
            break

    if not rows and _HANDLE_RE.fullmatch(_normalise_handle(q)):
        row = _candidate_row(
            roster=roster,
            market=market,
            handle=_normalise_handle(q),
            source="manual_input",
            match="handle input",
        )
        rows.append(row)

    return rows[:limit]


def roster_table_rows(
    items: list[dict[str, Any]],
    *,
    query: str = "",
    category: str = _ALL,
    data_status: str = _ALL,
    page: int = 1,
    page_size: int = 100,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    filtered = filter_influencers(
        [row for row in items if isinstance(row, dict)],
        query=query,
        category=category,
        data_status=data_status,
    )
    filtered.sort(key=lambda row: (
        _normalise_market(row.get("market")),
        _normalise_handle(row.get("handle")).lower(),
        _normalise_category(row.get("category")),
    ))
    size = max(25, min(int(page_size or 100), 500))
    total = len(filtered)
    pages = max(1, (total + size - 1) // size)
    current = max(1, min(int(page or 1), pages))
    start = (current - 1) * size
    end = start + size
    rows = []
    for row in filtered[start:end]:
        source = str(row.get("category_source") or "manual").strip()
        confidence = row.get("category_confidence")
        ai_label = ""
        if source == "ai" and confidence not in (None, ""):
            try:
                ai_label = f"AI {float(confidence):.0%}"
            except (TypeError, ValueError):
                ai_label = "AI"
        rows.append({
            "state": "模板" if row.get("placeholder") else "已加入",
            "handle": _normalise_handle(row.get("handle")),
            "name": str(row.get("name") or ""),
            "market": _normalise_market(row.get("market")),
            "category": _normalise_category(row.get("category")),
            "category_source": source,
            "ai": ai_label,
            "note": str(row.get("note") or ""),
            "url": str(row.get("url") or f"https://x.com/{_normalise_handle(row.get('handle'))}"),
        })
    return rows, {"total": total, "page": current, "pages": pages, "page_size": size}


def _normalise_preview_posts(
    posts: list[dict[str, Any]] | None,
    *,
    handle: str,
    limit: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in posts or []:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        out.append({
            "author": str(row.get("author") or f"@{handle}"),
            "text": text,
            "created_at": str(row.get("created_at") or ""),
            "url": str(row.get("url") or ""),
            "likes": int(row.get("likes") or 0),
            "retweets": int(row.get("retweets") or 0),
        })
        if len(out) >= limit:
            break
    return out


def _official_x_posts(handle: str, limit: int) -> list[dict[str, Any]]:
    from scripts import x_analysis

    return x_analysis.fetch_user_posts(handle, limit=limit)


def _agent_reach_posts(handle: str, limit: int) -> dict[str, Any]:
    from scripts import agent_reach_social_bridge as bridge

    runtime_env = dict(os.environ)
    return bridge.fetch_user_posts_payload(
        handle,
        credentials=bridge.load_credentials(env=runtime_env),
        twitter_bin=bridge.resolve_twitter_bin(env=runtime_env),
        env=runtime_env,
        limit=limit,
        timeout=10,
    )


def lookup_x_preview(
    handle: str,
    *,
    env: dict[str, str] | None = None,
    official_fetcher: Any | None = None,
    agent_fetcher: Any | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Look up a handle for the add-influencer preview without exposing secrets."""
    cleaned_handle = _normalise_handle(handle)
    if not _HANDLE_RE.fullmatch(cleaned_handle):
        return {
            "status": "degraded",
            "source": "input",
            "cost_mode": "free",
            "handle": cleaned_handle,
            "url": "",
            "posts": [],
            "note": "handle must be 1-15 letters/numbers/underscore characters",
        }

    runtime_env = env if env is not None else os.environ
    official = official_fetcher or _official_x_posts
    agent = agent_fetcher or _agent_reach_posts
    notes: list[str] = []
    limit = max(1, min(int(limit or 5), 20))

    if runtime_env.get("X_BEARER_TOKEN"):
        try:
            posts = _normalise_preview_posts(
                official(cleaned_handle, limit),
                handle=cleaned_handle,
                limit=limit,
            )
            return {
                "status": "available",
                "source": "x_official_api",
                "cost_mode": "paid_optional",
                "handle": cleaned_handle,
                "url": f"https://x.com/{cleaned_handle}",
                "posts": posts,
                "note": "" if posts else "X official API found the account but returned no recent posts",
            }
        except Exception as exc:  # noqa: BLE001
            notes.append(f"X official API unavailable: {exc}")

    try:
        payload = agent(cleaned_handle, limit)
    except Exception as exc:  # noqa: BLE001
        payload = {
            "source": "agent_reach",
            "cost_mode": "auth_required",
            "status": "degraded",
            "posts": [],
            "note": f"Agent Reach unavailable: {exc}",
        }

    posts = _normalise_preview_posts(
        payload.get("posts") if isinstance(payload, dict) else [],
        handle=cleaned_handle,
        limit=limit,
    )
    note_parts = [n for n in notes if n]
    if isinstance(payload, dict) and payload.get("note"):
        note_parts.append(str(payload.get("note")))
    return {
        "status": str((payload or {}).get("status") or "degraded") if isinstance(payload, dict) else "degraded",
        "source": str((payload or {}).get("source") or "agent_reach") if isinstance(payload, dict) else "agent_reach",
        "cost_mode": str((payload or {}).get("cost_mode") or "auth_required") if isinstance(payload, dict) else "auth_required",
        "auth_status": str((payload or {}).get("auth_status") or "") if isinstance(payload, dict) else "",
        "tool_status": str((payload or {}).get("tool_status") or "") if isinstance(payload, dict) else "",
        "handle": cleaned_handle,
        "url": str((payload or {}).get("url") or f"https://x.com/{cleaned_handle}") if isinstance(payload, dict) else f"https://x.com/{cleaned_handle}",
        "posts": posts,
        "note": " / ".join(note_parts),
    }


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
    st.header("關注博主")

    roster = load_roster()
    _render_delete_undo(roster)
    _render_roster_health(roster)
    _render_search_add_console(roster)

    influencers, order = roster.get("influencers", []), roster.get("categories_order", [])
    if not influencers:
        st.info("尚無博主。可從上方搜尋列加入。")
        _render_roster_editor(roster)
        return

    _render_roster_table_console(roster, influencers, order)
    _render_roster_editor(roster)


def _roster_health(roster: dict[str, Any]) -> dict[str, int]:
    rows = [r for r in roster.get("influencers", []) if isinstance(r, dict) and not r.get("placeholder")]
    uncategorized = sum(1 for r in rows if _normalise_category(r.get("category")) == _UNCATEGORIZED)
    def confidence(row: dict[str, Any]) -> float:
        try:
            return float(row.get("category_confidence") or 0)
        except (TypeError, ValueError):
            return 0.0
    low_conf = sum(
        1
        for r in rows
        if str(r.get("category_source") or "") == "ai"
        and confidence(r) < 0.65
    )
    missing_url = sum(1 for r in rows if not str(r.get("url") or "").strip())
    us = sum(1 for r in rows if _normalise_market(r.get("market")) == "US")
    crypto = sum(1 for r in rows if _normalise_market(r.get("market")) == "CRYPTO")
    return {
        "total": len(rows),
        "us": us,
        "crypto": crypto,
        "uncategorized": uncategorized,
        "low_confidence": low_conf,
        "missing_url": missing_url,
    }


def _render_roster_health(roster: dict[str, Any]) -> None:
    stats = _roster_health(roster)
    st.caption(
        f"總數 {stats['total']:,} · US {stats['us']:,} · CRYPTO {stats['crypto']:,} · "
        f"待分類 {stats['uncategorized']:,} · AI 低信心 {stats['low_confidence']:,} · "
        f"缺 URL {stats['missing_url']:,}"
    )


def _is_handle_lookup(query: str) -> bool:
    value = str(query or "").strip()
    handle = _normalise_handle(value)
    return bool(_HANDLE_RE.fullmatch(handle)) and (
        value.startswith("@")
        or "x.com/" in value.lower()
        or "twitter.com/" in value.lower()
        or " " not in value
    )


def _candidate_label(row: dict[str, Any]) -> str:
    handle = row.get("handle") or ""
    name = row.get("name") or ""
    state = row.get("state") or ""
    category = row.get("ai_category") or row.get("category") or ""
    bits = [state, f"@{handle}"]
    if name:
        bits.append(str(name))
    if category:
        bits.append(f"AI:{category}")
    return " · ".join(bits)


def _candidate_pick_key(candidates: list[dict[str, Any]], query: str, market: str) -> str:
    raw = "|".join(
        f"{row.get('state')}:{row.get('handle')}:{row.get('market')}"
        for row in candidates
    )
    digest = hashlib.sha1(f"{market}:{query}:{raw}".encode("utf-8")).hexdigest()[:10]
    return f"influencer_candidate_pick_{digest}"


def _candidate_record(row: dict[str, Any], *, category_choice: str | None = None) -> dict[str, Any]:
    use_ai = not category_choice or category_choice.startswith("AI 分類")
    category = str(row.get("ai_category") if use_ai else category_choice or row.get("ai_category") or _UNCATEGORIZED)
    return {
        "handle": row.get("handle"),
        "name": row.get("name") or row.get("handle"),
        "market": row.get("market") or "US",
        "category": category,
        "category_source": "ai" if use_ai else "manual",
        "category_confidence": row.get("ai_confidence") if use_ai else 1.0,
        "category_reason": row.get("ai_reason") if use_ai else "manual override",
        "note": row.get("note") or "",
        "url": row.get("url") or "",
    }


def _find_influencer(roster: dict[str, Any], handle: str, market: str) -> dict[str, Any] | None:
    target = _normalise_handle(handle).lower()
    target_market = _normalise_market(market)
    for row in roster.get("influencers", []):
        if (
            _normalise_handle(row.get("handle")).lower() == target
            and _normalise_market(row.get("market")) == target_market
        ):
            return row
    return None


def _detail_key(handle: str, market: str) -> str:
    return f"{_normalise_market(market)}::{_normalise_handle(handle).lower()}"


def _render_search_add_console(roster: dict[str, Any]) -> None:
    with st.container(border=True):
        st.markdown("**搜尋 / 加入**")
        c_query, c_market, c_lookup = st.columns([5, 1, 1])
        query = c_query.text_input(
            "搜尋帳號、名稱或 X URL",
            placeholder="@FLOWGOD、Flow God、https://x.com/FLOWGOD",
            key="influencer_compact_search",
        )
        market = c_market.selectbox("市場", _MARKETS, key="influencer_compact_market")
        lookup_clicked = c_lookup.button(
            "查 X",
            type="secondary",
            use_container_width=True,
            key="influencer_compact_lookup",
            disabled=not _is_handle_lookup(query),
        )
        if lookup_clicked:
            with st.spinner("查詢 X..."):
                st.session_state[_SEARCH_PREVIEW_KEY] = lookup_x_preview(query)

        preview = st.session_state.get(_SEARCH_PREVIEW_KEY)
        if (
            not isinstance(preview, dict)
            or _normalise_handle(preview.get("handle")).lower() != _normalise_handle(query).lower()
        ):
            preview = None
        candidates = build_search_candidates(
            roster,
            query,
            market=market,
            preview_payload=preview,
            limit=8,
        )
        if candidates:
            st.caption("候選清單")
            candidate_rows = [
                {
                    "狀態": row.get("state"),
                    "帳號": "@" + str(row.get("handle") or ""),
                    "名稱": row.get("name") or "",
                    "AI 分類": (
                        f"{row.get('ai_category')} {float(row.get('ai_confidence') or 0):.0%}"
                        if row.get("ai_category")
                        else ""
                    ),
                    "來源": row.get("source"),
                    "匹配": row.get("match"),
                    "動作": row.get("action"),
                }
                for row in candidates
            ]
            st.dataframe(candidate_rows, hide_index=True, use_container_width=True, height=220)
            labels = [_candidate_label(row) for row in candidates]
            default_idx = next(
                (idx for idx, row in enumerate(candidates) if row.get("state") == "可加入"),
                0,
            )
            selected_label = st.selectbox(
                "候選",
                labels,
                index=default_idx,
                key=_candidate_pick_key(candidates, query, market),
            )
            selected = candidates[labels.index(selected_label)]
            categories = _category_options(roster)
            ai_choice = f"AI 分類: {selected.get('ai_category')} ({float(selected.get('ai_confidence') or 0):.0%})"
            category_choice = st.selectbox(
                "分類覆寫",
                [ai_choice] + categories,
                key="influencer_candidate_category",
            )
            c_add, c_view = st.columns([1, 5])
            if selected.get("state") == "可加入":
                if c_add.button(
                    f"加入 @{selected.get('handle')}",
                    type="primary",
                    key="influencer_candidate_add",
                ):
                    next_roster = upsert_influencer(
                        roster,
                        _candidate_record(selected, category_choice=category_choice),
                    )
                    _save_and_rerun(next_roster)
            else:
                c_add.button(
                    selected.get("action") or "查看",
                    disabled=True,
                    key="influencer_candidate_add_disabled",
                )
            if c_view.button("查看", key="influencer_candidate_view"):
                st.session_state[_DETAIL_KEY] = _detail_key(
                    selected.get("detail_handle") or selected.get("handle") or "",
                    selected.get("detail_market") or selected.get("market") or market,
                )
        elif query:
            st.info("沒有符合的候選；可改用 @handle 或 X URL 查詢。")


def _render_roster_table_console(
    roster: dict[str, Any],
    influencers: list[dict[str, Any]],
    order: list[str],
) -> None:
    st.markdown("**名冊表格**")
    markets = [_ALL] + sorted({i.get("market", "US") for i in influencers})
    c_search, c_market, c_cat, c_status, c_size, c_page = st.columns([2, 1, 1, 1, 1, 1])
    query = c_search.text_input("搜尋帳號 / 名稱 / 備註", placeholder="Remzz、macro、flow", key="roster_query")
    market_filter = c_market.selectbox("市場", markets, key="roster_market")
    market_items = [i for i in influencers if market_filter == _ALL or i.get("market") == market_filter]
    filter_cats = [_ALL] + list(dict.fromkeys(
        order + sorted({_normalise_category(i.get("category")) for i in market_items})
    ))
    category_filter = c_cat.selectbox("分類篩選", filter_cats, key="roster_category")
    data_status = c_status.selectbox("資料狀態", [_ALL, "缺名稱", "缺備註", "缺 URL", "模板", "非模板"], key="roster_status")
    page_size = c_size.selectbox("每頁", [50, 100, 200, 500], index=1, key="roster_page_size")
    page = c_page.number_input("頁碼", min_value=1, value=1, step=1, key="roster_page")
    rows, meta = roster_table_rows(
        market_items,
        query=query,
        category=category_filter,
        data_status=data_status,
        page=int(page),
        page_size=int(page_size),
    )
    st.caption(
        f"顯示 {len(rows):,} / {meta['total']:,} · 第 {meta['page']:,} / {meta['pages']:,} 頁"
    )
    if rows:
        st.dataframe(
            [
                {
                    "狀態": row["state"],
                    "帳號": "@" + row["handle"],
                    "名稱": row["name"],
                    "市場": row["market"],
                    "分類": row["category"],
                    "AI": row["ai"],
                    "備註": row["note"],
                    "URL": row["url"],
                }
                for row in rows
            ],
            hide_index=True,
            use_container_width=True,
            height=460,
        )
        labels = [f"@{row['handle']} · {row['market']} · {row['category']}" for row in rows]
        selected = st.selectbox("快速查看 / 編輯", [""] + labels, key="roster_detail_pick")
        if selected:
            row = rows[labels.index(selected)]
            st.session_state[_DETAIL_KEY] = _detail_key(row["handle"], row["market"])
    else:
        st.info("目前篩選條件沒有符合的非模板博主。")

    detail_key = st.session_state.get(_DETAIL_KEY)
    if isinstance(detail_key, str) and "::" in detail_key:
        market, handle_key = detail_key.split("::", 1)
        detail = _find_influencer(roster, handle_key, market)
        if detail:
            _render_influencer_actions(roster, detail)


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


def _render_x_lookup_preview(preview: dict[str, Any]) -> None:
    status = str(preview.get("status") or "degraded")
    source = str(preview.get("source") or "unknown")
    cost_mode = str(preview.get("cost_mode") or "")
    auth_status = str(preview.get("auth_status") or "")
    tool_status = str(preview.get("tool_status") or "")
    handle = str(preview.get("handle") or "")
    url = str(preview.get("url") or f"https://x.com/{handle}")
    posts = [p for p in (preview.get("posts") or []) if isinstance(p, dict)]
    color = _shared.GREEN if status == "available" else _shared.AMBER
    chips = [
        (status, color),
        (source, _shared.BLUE),
    ]
    if source == "agent_reach":
        if auth_status:
            chips.append((
                f"cookie {auth_status}",
                _shared.GREEN if auth_status == "configured" else _shared.AMBER,
            ))
        if tool_status:
            chips.append((
                f"twitter-cli {tool_status}",
                _shared.GREEN if tool_status == "available" else _shared.AMBER,
            ))
    else:
        chips.append((cost_mode, _shared.MUTED))
    with st.container(border=True):
        st.markdown("**即時 X 預覽**")
        _shared.chips_row(chips)
        if source == "agent_reach":
            st.caption("Agent Reach 使用 X Cookie 認證；`auth_required` 是成本/認證模式，不代表工具鏈可執行。")
        if handle:
            st.markdown(f"[@{handle}]({url})")
        if preview.get("note"):
            st.caption(str(preview["note"]))
        if posts:
            st.markdown("**最近貼文**")
            for post in posts[:5]:
                metrics = []
                if post.get("created_at"):
                    metrics.append(str(post["created_at"]))
                metrics.append(f"like {int(post.get('likes') or 0)}")
                metrics.append(f"rt {int(post.get('retweets') or 0)}")
                text = str(post.get("text") or "").strip()
                st.markdown(f"- {text}")
                link = str(post.get("url") or "").strip()
                meta = " · ".join(metrics)
                st.caption(f"{meta}" + (f" · {link}" if link else ""))
        else:
            st.info("尚未取得最近貼文；仍可先新增，後續雷達會依來源狀態降級。")


def _render_roster_editor(roster: dict[str, Any]) -> None:
    categories = _category_options(roster)
    with st.expander("批次操作 / 進階", expanded=False):
        bulk_tab, cat_tab, raw_tab = st.tabs(["批次匯入", "分類清單", "進階 JSON"])
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
