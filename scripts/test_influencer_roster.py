#!/usr/bin/env python3
"""Self-contained tests for editable X influencer roster helpers."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_module():
    from ui import influencers

    return influencers


def _roster() -> dict:
    return {
        "categories_order": ["Momentum Options Trade", "Macro / News"],
        "influencers": [
            {
                "handle": "Remzztrades",
                "name": "Remzz",
                "category": "Momentum Options Trade",
                "market": "US",
                "note": "動能期權",
            },
            {
                "handle": "DeItaone",
                "name": "Walter Bloomberg",
                "category": "Macro / News",
                "market": "US",
            },
        ],
    }


def test_upsert_influencer_adds_category_and_normalises_handle() -> None:
    mod = _load_module()
    roster = _roster()

    changed = mod.upsert_influencer(
        roster,
        {
            "handle": "@StockMKTNewz",
            "name": "StockMKTNewz",
            "category": "Breaking News",
            "market": "US",
            "note": "news tape",
            "url": "",
        },
    )

    if changed["categories_order"][-1] != "Breaking News":
        raise AssertionError(changed)
    row = next(r for r in changed["influencers"] if r["handle"] == "StockMKTNewz")
    if row["url"] != "https://x.com/StockMKTNewz":
        raise AssertionError(row)
    if row["market"] != "US":
        raise AssertionError(row)


def test_upsert_influencer_edits_existing_handle_without_duplicate() -> None:
    mod = _load_module()
    roster = _roster()

    changed = mod.upsert_influencer(
        roster,
        {
            "handle": "Remzztrades",
            "name": "Remzz Trades",
            "category": "Option Flow",
            "market": "US",
            "note": "updated",
        },
        original_handle="Remzztrades",
        original_market="US",
    )

    rows = [r for r in changed["influencers"] if r["handle"].lower() == "remzztrades"]
    if len(rows) != 1:
        raise AssertionError(changed)
    if rows[0]["name"] != "Remzz Trades" or rows[0]["category"] != "Option Flow":
        raise AssertionError(rows[0])
    if "Option Flow" not in changed["categories_order"]:
        raise AssertionError(changed)


def test_upsert_influencer_renaming_to_existing_handle_deduplicates_target() -> None:
    mod = _load_module()
    roster = _roster()

    changed = mod.upsert_influencer(
        roster,
        {
            "handle": "DeItaone",
            "name": "Merged News",
            "category": "Macro / News",
            "market": "US",
        },
        original_handle="Remzztrades",
        original_market="US",
    )

    rows = [r for r in changed["influencers"] if r["handle"].lower() == "deitaone"]
    if len(rows) != 1:
        raise AssertionError(changed)
    if rows[0]["name"] != "Merged News":
        raise AssertionError(rows[0])


def test_rename_category_updates_order_and_members() -> None:
    mod = _load_module()

    changed = mod.rename_category(_roster(), "Macro / News", "Macro News")

    if "Macro / News" in changed["categories_order"]:
        raise AssertionError(changed)
    if "Macro News" not in changed["categories_order"]:
        raise AssertionError(changed)
    row = next(r for r in changed["influencers"] if r["handle"] == "DeItaone")
    if row["category"] != "Macro News":
        raise AssertionError(row)


def test_delete_influencer_removes_only_matching_market_handle() -> None:
    mod = _load_module()
    roster = _roster()
    roster["influencers"].append({
        "handle": "Remzztrades",
        "category": "Crypto",
        "market": "CRYPTO",
    })

    changed = mod.delete_influencer(roster, "Remzztrades", "US")

    remaining = [(r["handle"], r["market"]) for r in changed["influencers"]]
    if ("Remzztrades", "US") in remaining:
        raise AssertionError(remaining)
    if ("Remzztrades", "CRYPTO") not in remaining:
        raise AssertionError(remaining)


def test_save_roster_writes_atomic_json() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "influencers.json"

        mod.save_roster(_roster(), path=path)

        data = json.loads(path.read_text(encoding="utf-8"))
        if data["influencers"][0]["handle"] != "Remzztrades":
            raise AssertionError(data)
        if path.with_suffix(".json.tmp").exists():
            raise AssertionError("temporary file was not replaced")


def test_save_roster_updates_symlink_target_without_replacing_link() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        shared = root / "shared" / "content" / "influencers.json"
        release = root / "current" / "content" / "influencers.json"
        shared.parent.mkdir(parents=True)
        release.parent.mkdir(parents=True)
        shared.write_text(json.dumps(_roster(), ensure_ascii=False), encoding="utf-8")
        release.symlink_to(shared)

        changed = mod.upsert_influencer(
            _roster(),
            {
                "handle": "StockMKTNewz",
                "name": "StockMKTNewz",
                "category": "Breaking News",
                "market": "US",
            },
        )
        mod.save_roster(changed, path=release)

        if not release.is_symlink():
            raise AssertionError("save_roster replaced the persistent symlink")
        data = json.loads(shared.read_text(encoding="utf-8"))
        if not any(row.get("handle") == "StockMKTNewz" for row in data["influencers"]):
            raise AssertionError(data)


def test_resolve_roster_path_prefers_env_and_seeds_missing_runtime_file() -> None:
    mod = _load_module()
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        default_path = root / "repo" / "content" / "influencers.json"
        runtime_path = root / "shared" / "content" / "influencers.json"
        default_path.parent.mkdir(parents=True)
        default_path.write_text(json.dumps(_roster(), ensure_ascii=False), encoding="utf-8")

        resolved = mod.resolve_roster_path(
            env={"SURGE_INFLUENCERS_PATH": str(runtime_path)},
            default_path=default_path,
        )

        if resolved != runtime_path:
            raise AssertionError(resolved)
        seeded = json.loads(runtime_path.read_text(encoding="utf-8"))
        if seeded["influencers"][0]["handle"] != "Remzztrades":
            raise AssertionError(seeded)


def test_parse_bulk_influencers_accepts_handles_and_x_urls() -> None:
    mod = _load_module()

    rows = mod.parse_bulk_influencers(
        """
        @StockMKTNewz
        https://x.com/zerohedge
        x.com/unusual_whales
        """,
        default_market="US",
        default_category="Macro / News",
    )

    handles = [r["handle"] for r in rows]
    if handles != ["StockMKTNewz", "zerohedge", "unusual_whales"]:
        raise AssertionError(rows)
    if {r["market"] for r in rows} != {"US"}:
        raise AssertionError(rows)
    if {r["category"] for r in rows} != {"Macro / News"}:
        raise AssertionError(rows)
    if rows[1]["url"] != "https://x.com/zerohedge":
        raise AssertionError(rows[1])


def test_parse_bulk_influencers_accepts_csv_header_rows() -> None:
    mod = _load_module()

    rows = mod.parse_bulk_influencers(
        """handle,name,category,market,note,url
@WatcherGuru,Watcher.Guru,Crypto,CRYPTO,news,https://x.com/WatcherGuru
Remzztrades,Remzz,Momentum Options Trade,US,options,
""",
        default_market="US",
        default_category="未分類",
    )

    if rows[0]["handle"] != "WatcherGuru" or rows[0]["market"] != "CRYPTO":
        raise AssertionError(rows)
    if rows[0]["name"] != "Watcher.Guru" or rows[0]["note"] != "news":
        raise AssertionError(rows[0])
    if rows[1]["url"] != "https://x.com/Remzztrades":
        raise AssertionError(rows[1])


def test_bulk_upsert_influencers_updates_existing_and_adds_new() -> None:
    mod = _load_module()

    rows = mod.parse_bulk_influencers(
        """Remzztrades,Remzz Trades,Option Flow,US,updated
StockMKTNewz,StockMKTNewz,Breaking News,US,news tape
""",
        default_market="US",
        default_category="未分類",
    )
    changed = mod.bulk_upsert_influencers(_roster(), rows)

    handles = [r["handle"] for r in changed["influencers"]]
    if handles.count("Remzztrades") != 1 or "StockMKTNewz" not in handles:
        raise AssertionError(changed)
    remzz = next(r for r in changed["influencers"] if r["handle"] == "Remzztrades")
    if remzz["name"] != "Remzz Trades" or remzz["category"] != "Option Flow":
        raise AssertionError(remzz)
    if "Breaking News" not in changed["categories_order"]:
        raise AssertionError(changed)


def test_bulk_upsert_preserve_existing_keeps_unspecified_fields() -> None:
    mod = _load_module()

    rows = mod.parse_bulk_influencers(
        "@Remzztrades",
        default_market="US",
        default_category="Macro / News",
    )
    changed = mod.bulk_upsert_influencers(_roster(), rows, mode="preserve")

    remzz = next(r for r in changed["influencers"] if r["handle"] == "Remzztrades")
    if remzz["name"] != "Remzz":
        raise AssertionError(remzz)
    if remzz["category"] != "Momentum Options Trade":
        raise AssertionError(remzz)
    if remzz["note"] != "動能期權":
        raise AssertionError(remzz)


def test_bulk_upsert_only_new_skips_existing_handles() -> None:
    mod = _load_module()

    rows = mod.parse_bulk_influencers(
        """Remzztrades,Remzz Trades,Option Flow,US,updated
StockMKTNewz,StockMKTNewz,Breaking News,US,news tape
""",
        default_market="US",
        default_category="未分類",
    )
    changed = mod.bulk_upsert_influencers(_roster(), rows, mode="only_new")

    remzz = next(r for r in changed["influencers"] if r["handle"] == "Remzztrades")
    if remzz["name"] != "Remzz" or remzz["category"] != "Momentum Options Trade":
        raise AssertionError(remzz)
    if not any(r["handle"] == "StockMKTNewz" for r in changed["influencers"]):
        raise AssertionError(changed)


def test_preview_bulk_import_reports_actions_and_line_errors() -> None:
    mod = _load_module()

    preview = mod.preview_bulk_import(
        _roster(),
        """@Remzztrades
bad-handle!
https://x.com/StockMKTNewz
""",
        default_market="US",
        default_category="Macro / News",
        mode="preserve",
    )

    statuses = [(r["line"], r["action"], r.get("handle"), r.get("error", "")) for r in preview]
    if statuses[0][:3] != (1, "更新", "Remzztrades"):
        raise AssertionError(statuses)
    if statuses[1][0] != 2 or statuses[1][1] != "錯誤" or "handle" not in statuses[1][3]:
        raise AssertionError(statuses)
    if statuses[2][:3] != (3, "新增", "StockMKTNewz"):
        raise AssertionError(statuses)


def test_apply_bulk_import_skips_error_and_duplicate_rows() -> None:
    mod = _load_module()

    preview = mod.preview_bulk_import(
        _roster(),
        """@StockMKTNewz
@StockMKTNewz
bad-handle!
""",
        default_market="US",
        default_category="Breaking News",
        mode="preserve",
    )
    changed = mod.apply_bulk_import(_roster(), preview, mode="preserve")

    rows = [r for r in changed["influencers"] if r["handle"] == "StockMKTNewz"]
    if len(rows) != 1:
        raise AssertionError(changed)
    if any(r.get("handle") == "bad-handle!" for r in changed["influencers"]):
        raise AssertionError(changed)


def test_delete_influencer_with_snapshot_returns_removed_record_for_undo() -> None:
    mod = _load_module()

    changed, removed = mod.delete_influencer_with_snapshot(_roster(), "Remzztrades", "US")

    if len(removed) != 1 or removed[0]["handle"] != "Remzztrades":
        raise AssertionError(removed)
    if any(r["handle"] == "Remzztrades" and r["market"] == "US" for r in changed["influencers"]):
        raise AssertionError(changed)


def test_filter_influencers_searches_category_and_missing_fields() -> None:
    mod = _load_module()
    roster = _roster()
    roster["influencers"].append({
        "handle": "StockMKTNewz",
        "category": "Breaking News",
        "market": "US",
    })

    by_text = mod.filter_influencers(roster["influencers"], query="walter")
    if [r["handle"] for r in by_text] != ["DeItaone"]:
        raise AssertionError(by_text)
    by_category = mod.filter_influencers(roster["influencers"], category="Breaking News")
    if [r["handle"] for r in by_category] != ["StockMKTNewz"]:
        raise AssertionError(by_category)
    missing = mod.filter_influencers(roster["influencers"], data_status="缺名稱")
    if [r["handle"] for r in missing] != ["StockMKTNewz"]:
        raise AssertionError(missing)


def test_ai_category_suggestion_uses_profile_text_before_manual_override() -> None:
    mod = _load_module()

    suggestion = mod.suggest_ai_category(
        {
            "handle": "FlowTape",
            "name": "Flow Tape",
            "note": "momentum options flow and swing trade ideas",
        },
        ["Momentum Options Trade", "Macro / News", "Crypto"],
    )

    if suggestion["category"] != "Momentum Options Trade":
        raise AssertionError(suggestion)
    if suggestion["source"] != "ai" or suggestion["confidence"] < 0.7:
        raise AssertionError(suggestion)
    if "options" not in suggestion["reason"].lower():
        raise AssertionError(suggestion)


def test_build_search_candidates_marks_added_and_available_results() -> None:
    mod = _load_module()
    roster = _roster()
    roster["influencers"].append({
        "handle": "FlowGod",
        "name": "Flow God",
        "category": "Momentum Options Trade",
        "market": "CRYPTO",
        "note": "crypto flow",
    })

    existing = mod.build_search_candidates(
        roster,
        "@Remzztrades",
        market="US",
        preview_payload={"handle": "Remzztrades", "source": "agent_reach"},
    )
    if existing[0]["state"] != "已加入" or existing[0]["action"] != "查看":
        raise AssertionError(existing)

    other_market = mod.build_search_candidates(
        roster,
        "flowgod",
        market="US",
        preview_payload={"handle": "FlowGod", "source": "agent_reach"},
    )
    if other_market[0]["state"] != "已加入其他市場":
        raise AssertionError(other_market)

    available = mod.build_search_candidates(
        roster,
        "https://x.com/StockMKTNewz",
        market="US",
        preview_payload={
            "handle": "StockMKTNewz",
            "source": "agent_reach",
            "posts": [{"text": "breaking news tape and macro headlines"}],
        },
    )
    if available[0]["state"] != "可加入" or available[0]["action"] != "加入":
        raise AssertionError(available)
    if available[0]["ai_category"] != "Macro / News":
        raise AssertionError(available)

    duplicate_name = mod.build_search_candidates(
        roster,
        "Remzz Signals",
        market="US",
        preview_payload={"handle": "RemzzSignals", "name": "Remzz"},
    )
    if duplicate_name[0]["state"] != "疑似重複":
        raise AssertionError(duplicate_name)
    if duplicate_name[0]["detail_handle"] != "Remzztrades" or duplicate_name[0]["detail_market"] != "US":
        raise AssertionError(duplicate_name)


def test_explicit_handle_lookup_does_not_mix_unrelated_local_fuzzy_matches() -> None:
    mod = _load_module()
    roster = _roster()
    roster["influencers"].append({
        "handle": "Deltaone",
        "name": "Walter Bloomberg",
        "category": "Macro / News",
        "market": "US",
        "note": "mentions aleabitoreddit in a note but is a different account",
    })

    candidates = mod.build_search_candidates(
        roster,
        "@aleabitoreddit",
        market="US",
        preview_payload={"handle": "aleabitoreddit", "source": "agent_reach"},
    )

    if [row["handle"] for row in candidates] != ["aleabitoreddit"]:
        raise AssertionError(candidates)
    if candidates[0]["state"] != "可加入":
        raise AssertionError(candidates)


def test_name_lookup_candidate_uses_profile_identity_and_existing_categories() -> None:
    mod = _load_module()

    candidates = mod.build_search_candidates(
        _roster(),
        "Serenity",
        market="US",
        preview_payload={
            "handle": "aleabitoreddit",
            "name": "Serenity",
            "url": "https://x.com/aleabitoreddit",
            "source": "agent_reach",
            "description": "Momentum options flow and swing trade setups.",
            "bio": "Options trader.",
            "posts": [{"text": "watching unusual options flow and gamma squeeze"}],
        },
    )

    if not candidates:
        raise AssertionError(candidates)
    row = candidates[0]
    if row["handle"] != "aleabitoreddit" or row["name"] != "Serenity":
        raise AssertionError(row)
    if row["url"] != "https://x.com/aleabitoreddit":
        raise AssertionError(row)
    if row["match"] != "profile lookup":
        raise AssertionError(row)
    if row["ai_category"] != "Momentum Options Trade":
        raise AssertionError(row)
    if "options" not in row["ai_reason"].lower():
        raise AssertionError(row)


def test_candidate_table_markdown_links_profile_and_hides_internal_columns() -> None:
    mod = _load_module()

    markdown = mod.candidate_table_markdown([
        {
            "state": "可加入",
            "handle": "aleabitoreddit",
            "name": "Serenity",
            "ai_category": "Momentum Options Trade",
            "ai_confidence": 0.79,
            "source": "agent_reach",
            "url": "https://x.com/aleabitoreddit",
            "match": "profile lookup",
            "action": "加入",
        }
    ])

    if "[@aleabitoreddit](https://x.com/aleabitoreddit)" not in markdown:
        raise AssertionError(markdown)
    if "[Serenity](https://x.com/aleabitoreddit)" not in markdown:
        raise AssertionError(markdown)
    if "匹配" in markdown or "動作" in markdown:
        raise AssertionError(markdown)


def test_new_candidate_category_requires_confirmation() -> None:
    mod = _load_module()

    if mod.needs_new_category_confirmation(_roster(), "Macro / News"):
        raise AssertionError("existing category should not require confirmation")
    if not mod.needs_new_category_confirmation(_roster(), "New Signal Desk"):
        raise AssertionError("new category should require confirmation")


def test_roster_table_rows_are_paginated_for_large_rosters() -> None:
    mod = _load_module()
    roster = {
        "categories_order": ["Momentum Options Trade", "Macro / News"],
        "influencers": [
            {
                "handle": f"Trader{i:05d}",
                "name": f"Trader {i:05d}",
                "category": "Momentum Options Trade" if i % 2 else "Macro / News",
                "market": "US",
            }
            for i in range(10000)
        ],
    }

    rows, meta = mod.roster_table_rows(
        roster["influencers"],
        query="Trader09",
        category="全部",
        data_status="全部",
        page=2,
        page_size=50,
    )

    if len(rows) != 50:
        raise AssertionError((len(rows), meta))
    if meta["total"] != 1000 or meta["page"] != 2 or meta["pages"] != 20:
        raise AssertionError(meta)
    if rows[0]["handle"] != "Trader09050":
        raise AssertionError(rows[0])
    if rows[0]["state"] != "已加入":
        raise AssertionError(rows[0])


def test_lookup_x_preview_prefers_official_x_when_token_is_available() -> None:
    mod = _load_module()
    called = {"official": 0, "agent": 0}

    def official_fetcher(handle: str, limit: int) -> list[dict]:
        called["official"] += 1
        if handle != "godflow" or limit != 5:
            raise AssertionError((handle, limit))
        return [{"text": "latest thesis", "created_at": "2026-07-06T01:00:00Z"}]

    def agent_fetcher(handle: str, limit: int) -> dict:
        called["agent"] += 1
        raise AssertionError("agent fallback should not run")

    preview = mod.lookup_x_preview(
        "@godflow",
        env={"X_BEARER_TOKEN": "token"},
        official_fetcher=official_fetcher,
        agent_fetcher=agent_fetcher,
        limit=5,
    )

    if preview["status"] != "available" or preview["source"] != "x_official_api":
        raise AssertionError(preview)
    if preview["handle"] != "godflow" or preview["url"] != "https://x.com/godflow":
        raise AssertionError(preview)
    if preview["posts"][0]["text"] != "latest thesis":
        raise AssertionError(preview)
    if called != {"official": 1, "agent": 0}:
        raise AssertionError(called)


def test_lookup_x_preview_falls_back_to_agent_reach_without_x_token() -> None:
    mod = _load_module()

    def official_fetcher(handle: str, limit: int) -> list[dict]:
        raise AssertionError("official X API should not run without token")

    def agent_fetcher(handle: str, limit: int) -> dict:
        if handle != "godflow":
            raise AssertionError(handle)
        return {
            "source": "agent_reach",
            "cost_mode": "auth_required",
            "status": "available",
            "posts": [{"text": "agent post", "url": "https://x.com/godflow/status/1"}],
        }

    preview = mod.lookup_x_preview(
        "https://x.com/godflow",
        env={},
        official_fetcher=official_fetcher,
        agent_fetcher=agent_fetcher,
        limit=5,
    )

    if preview["status"] != "available" or preview["source"] != "agent_reach":
        raise AssertionError(preview)
    if preview["posts"][0]["text"] != "agent post":
        raise AssertionError(preview)


def test_lookup_x_preview_preserves_agent_reach_profile_fields() -> None:
    mod = _load_module()

    def agent_fetcher(handle: str, limit: int) -> dict:
        return {
            "source": "agent_reach",
            "cost_mode": "auth_required",
            "status": "available",
            "handle": handle,
            "name": "Serenity",
            "url": f"https://x.com/{handle}",
            "description": "Momentum options flow and swing trade setups.",
            "bio": "Options trader.",
            "posts": [{"text": "watching unusual options flow"}],
        }

    preview = mod.lookup_x_preview(
        "@aleabitoreddit",
        env={},
        official_fetcher=lambda handle, limit: [],
        agent_fetcher=agent_fetcher,
    )

    if preview["handle"] != "aleabitoreddit":
        raise AssertionError(preview)
    if preview["name"] != "Serenity":
        raise AssertionError(preview)
    if "Momentum options" not in preview["description"]:
        raise AssertionError(preview)
    if preview["bio"] != "Options trader.":
        raise AssertionError(preview)


def test_lookup_x_preview_resolves_display_name_before_fetching_posts() -> None:
    mod = _load_module()
    calls: list[tuple[str, str]] = []

    def account_searcher(query: str, limit: int) -> dict:
        calls.append(("search", query))
        return {
            "source": "agent_reach_search",
            "status": "available",
            "handle": "aleabitoreddit",
            "name": "Serenity",
            "url": "https://x.com/aleabitoreddit",
            "description": "Momentum options flow watchlist.",
        }

    def agent_fetcher(handle: str, limit: int) -> dict:
        calls.append(("posts", handle))
        return {
            "source": "agent_reach",
            "status": "available",
            "handle": handle,
            "posts": [{"text": "unusual options flow setups"}],
        }

    preview = mod.lookup_x_preview(
        "Serenity",
        env={},
        official_fetcher=lambda handle, limit: [],
        agent_fetcher=agent_fetcher,
        account_searcher=account_searcher,
        limit=5,
    )

    if preview["handle"] != "aleabitoreddit" or preview["name"] != "Serenity":
        raise AssertionError(preview)
    if calls != [("search", "Serenity"), ("posts", "aleabitoreddit")]:
        raise AssertionError(calls)


def test_lookup_x_preview_degrades_when_all_sources_unavailable() -> None:
    mod = _load_module()

    def agent_fetcher(handle: str, limit: int) -> dict:
        return {
            "source": "agent_reach",
            "cost_mode": "auth_required",
            "status": "degraded",
            "posts": [],
            "note": "Missing twitter_auth_token/twitter_ct0 in Agent Reach config",
        }

    preview = mod.lookup_x_preview(
        "godflow",
        env={},
        official_fetcher=lambda handle, limit: [],
        agent_fetcher=agent_fetcher,
    )

    if preview["status"] != "degraded":
        raise AssertionError(preview)
    if "Missing twitter_auth_token" not in preview["note"]:
        raise AssertionError(preview)


def test_lookup_x_preview_preserves_agent_reach_auth_and_tool_status() -> None:
    mod = _load_module()

    def agent_fetcher(handle: str, limit: int) -> dict:
        return {
            "source": "agent_reach",
            "cost_mode": "auth_required",
            "status": "degraded",
            "auth_status": "configured",
            "tool_status": "missing",
            "posts": [],
            "note": "Agent Reach twitter-cli missing",
        }

    preview = mod.lookup_x_preview(
        "godflow",
        env={},
        official_fetcher=lambda handle, limit: [],
        agent_fetcher=agent_fetcher,
    )

    if preview.get("auth_status") != "configured":
        raise AssertionError(preview)
    if preview.get("tool_status") != "missing":
        raise AssertionError(preview)


def main() -> int:
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, test in tests:
        try:
            test()
            print(f"  PASS {name}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
