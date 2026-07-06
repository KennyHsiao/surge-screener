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
