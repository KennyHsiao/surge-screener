#!/usr/bin/env python3
"""Binance USDT-M perpetual futures universe + daily diff + TradingView export.

Pulls the authoritative live list from Binance (no API key needed), filters to
TRADING USDT perpetuals, diffs against the previous snapshot to surface which
coins were added/removed, and writes:
  - reports/crypto/YYYY-MM-DD.json        (dated snapshot, used as next diff base)
  - reports/crypto/universe_latest.json   (latest snapshot + diff, for the UI)
  - reports/crypto/tradingview_watchlist.txt (BINANCE:SYM.P import file)

Verified-data philosophy: the list is exactly what Binance reports as live —
no LLM, no guessing. Delisted ghosts can't survive the status==TRADING filter.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

BINANCE_EXCHANGE_INFO = "https://fapi.binance.com/fapi/v1/exchangeInfo"


def _ms_to_date(ms) -> str | None:
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).date().isoformat()
    except (ValueError, TypeError, OSError):
        return None


def fetch_universe() -> list[dict]:
    """Live USDT-M perpetuals currently TRADING on Binance."""
    resp = httpx.get(BINANCE_EXCHANGE_INFO, timeout=30.0)
    resp.raise_for_status()
    out = []
    for s in resp.json().get("symbols", []):
        if (s.get("contractType") == "PERPETUAL"
                and s.get("quoteAsset") == "USDT"
                and s.get("status") == "TRADING"):
            sym = s["symbol"]
            out.append({
                "symbol": sym,
                "base": s.get("baseAsset"),
                "tv_symbol": f"BINANCE:{sym}.P",
                "onboard_date": _ms_to_date(s.get("onboardDate")),
            })
    out.sort(key=lambda x: x["symbol"])
    return out


def _previous_snapshot(out_dir: Path, today: str) -> dict | None:
    snaps = sorted(p for p in out_dir.glob("20*-*-*.json") if p.stem != today)
    if not snaps:
        return None
    with open(snaps[-1]) as f:
        return json.load(f)


def build_snapshot(out_dir: Path) -> dict:
    today = datetime.now(timezone.utc).date().isoformat()
    universe = fetch_universe()
    symbols = [u["symbol"] for u in universe]

    prev = _previous_snapshot(out_dir, today)
    prev_syms = set(prev.get("symbols", [])) if prev else set()
    cur_syms = set(symbols)
    return {
        "date": today,
        "source": "binance_fapi_exchangeInfo",
        "count": len(symbols),
        "symbols": symbols,
        "universe": universe,
        "added": sorted(cur_syms - prev_syms) if prev else [],
        "removed": sorted(prev_syms - cur_syms) if prev else [],
        "compared_to": prev.get("date") if prev else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", default="reports/crypto")
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    snap = build_snapshot(out_dir)
    payload = json.dumps(snap, ensure_ascii=False, indent=2)
    (out_dir / f"{snap['date']}.json").write_text(payload, encoding="utf-8")
    (out_dir / "universe_latest.json").write_text(payload, encoding="utf-8")
    (out_dir / "tradingview_watchlist.txt").write_text(
        "\n".join(u["tv_symbol"] for u in snap["universe"]) + "\n", encoding="utf-8")

    print(f"[crypto_universe] {snap['date']}: {snap['count']} USDT perps "
          f"(+{len(snap['added'])} / -{len(snap['removed'])} vs {snap['compared_to']})")
    if snap["added"]:
        print("  added:  ", ", ".join(snap["added"]))
    if snap["removed"]:
        print("  removed:", ", ".join(snap["removed"]))


if __name__ == "__main__":
    main()
