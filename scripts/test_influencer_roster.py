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
