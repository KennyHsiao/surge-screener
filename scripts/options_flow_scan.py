#!/usr/bin/env python3
"""Unusual options-flow scan → ranked alerts (bullflow.io / "godflow" X-post style).

Scans a curated universe of liquid optionable names (EOD) for UNUSUAL LARGE
VOLUME on the free yfinance options chain and emits short per-signal "posts":
ticker, direction, estimated premium $, the biggest strike/expiry, V/OI spike,
call/put skew. Writes reports/options_flow/{date}.json (+ latest.json) and can
push the top signals to Telegram (reuses scripts/05_notify.send_telegram_message).

FREE-DATA CEILING (honest): yfinance gives per-strike volume/OI/price snapshots —
enough for "unusual large volume" (V/OI spike, skew, est notional = volume × mid ×
100). It CANNOT see true sweeps / blocks / bid-ask aggressor side / dark pool —
those are the core of bullflow/godflow and need a PAID feed. `flow_provider` is
UW-ready: drop in `_uw_flow` (Unusual Whales) when UNUSUAL_WHALES_API_KEY is set;
until then every ticker uses `_free_flow`. Verified-data-to-AI: code detects; no
guessing. Never raises per-ticker — one bad symbol can't abort the scan.

CLI:
    python scripts/options_flow_scan.py                       # curated universe + today's candidates
    python scripts/options_flow_scan.py --universe NVDA,AMD,TSLA,AAPL
    python scripts/options_flow_scan.py --notify --min-notional 250000
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "reports" / "options_flow"

# Curated liquid, options-active US names (mega/large caps, popular ETFs, semis,
# high-options retail/meme names). Tunable; could move to content/liquid_optionable.json.
LIQUID_OPTIONABLE = [
    # Mega / large cap
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "BRK-B",
    "JPM", "V", "MA", "UNH", "HD", "PG", "COST", "WMT", "NFLX", "DIS", "BAC",
    "XOM", "CVX", "KO", "PEP", "MCD", "ABBV", "LLY", "MRK", "PFE", "TMO",
    "ORCL", "CRM", "ADBE", "CSCO", "ACN", "INTC", "TXN", "QCOM", "IBM", "NOW",
    # Semis / AI
    "AMD", "MU", "SMCI", "ARM", "TSM", "MRVL", "LRCX", "AMAT", "KLAC", "ON",
    "ASML", "DELL", "ANET", "PLTR", "CRWD", "SNOW", "NET", "DDOG", "PANW", "FTNT",
    # High-options retail / momentum
    "COIN", "MSTR", "SOFI", "HOOD", "RBLX", "SHOP", "UBER", "ABNB", "DASH", "RIVN",
    "LCID", "NIO", "AFRM", "UPST", "DKNG", "CVNA", "ROKU", "SQ", "PYPL", "BABA",
    "GME", "AMC", "F", "GM", "T", "VZ", "BA", "CAT", "DE", "GE",
    "WBD", "SNAP", "PINS", "U", "DOCU", "TWLO", "ZS", "MDB", "OKTA", "TEAM",
    # Sector / index / commodity ETFs
    "SPY", "QQQ", "IWM", "DIA", "SMH", "SOXX", "XLK", "XLF", "XLE", "XLV",
    "XLY", "XLI", "XLU", "XLP", "XLB", "XLRE", "XLC", "GLD", "SLV", "TLT",
    "GDX", "USO", "ARKK", "IBIT", "HYG", "EEM", "FXI", "XBI", "KRE", "ITB",
]

# ── detection thresholds (tunable) ───────────────────────────────────────────
VOI_UNUSUAL = 2.0          # V/OI ≥ this on a strike = unusual volume vs open interest
MIN_STRIKE_VOL = 200       # ignore tiny-volume strikes when summing notional
CP_STRONG = 3.0            # call/put volume ratio for a strong bullish signal
PCR_BEARISH = 1.8          # put/call ratio for a bearish signal (matches 6a veto)
MIN_NOTIONAL = 250_000     # default $ est-premium gate for an alert
DEFAULT_TOP = 30           # signals saved to JSON
DEFAULT_NOTIFY_TOP = 10    # signals pushed to Telegram


def _load(mod_name: str, func_name: str):
    """Import a scripts/<mod_name>.py member, path-independent (handles digit prefixes)."""
    try:
        mod = __import__(f"scripts.{mod_name}", fromlist=[func_name])
        return getattr(mod, func_name)
    except Exception:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            mod_name, REPO / "scripts" / f"{mod_name}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return getattr(mod, func_name)


def _flow_score(notional: float, max_voi: float, skew: float) -> float:
    """0-100 rank/display score: notional (log) + V/OI + skew. Heuristic, tunable."""
    n = 40 + 15 * math.log10(notional / MIN_NOTIONAL) if notional and notional > 0 else 0.0
    n = max(0.0, min(75.0, n))
    return round(min(100.0, n + min(15.0, (max_voi or 0) * 2.0)
                     + min(10.0, (skew or 0) * 2.0)), 1)


def _notional_and_biggest(rows: list[dict]) -> tuple[float, dict | None]:
    """Σ est notional over meaningful-volume strikes + the single most-active strike.

    NOTE: `biggest` is the strike with the largest DAILY-AGGREGATE notional (whole
    session's volume × mid × 100), NOT a single block/sweep — free data can't see
    individual prints. Labelled as 最活躍履約價 (most-active strike), not 最大單."""
    total = 0.0
    biggest = None
    for x in rows or []:
        n = x.get("notional")
        if not n or (x.get("volume") or 0) < MIN_STRIKE_VOL:
            continue
        total += n
        if biggest is None or n > biggest["notional"]:
            biggest = {"strike": x.get("strike"), "premium": x.get("premium"),
                       "volume": x.get("volume"), "notional": n, "voi": x.get("voi")}
    return total, biggest


def _free_flow(ticker: str, min_notional: int = MIN_NOTIONAL) -> dict | None:
    """Detect unusual options flow for one ticker from the free yfinance chain.

    Returns a signal dict or None (not unusual / no data). Never raises."""
    try:
        analyze = _load("options_free", "analyze_options")
        r = analyze(ticker)
    except Exception:
        return None
    if not r or not r.get("available"):
        return None

    spot = r.get("spot_price")
    d6a = (r.get("details") or {}).get("6a") or {}
    if not isinstance(d6a, dict):
        return None
    cp = d6a.get("call_put_volume_ratio")           # call/put volume ratio
    pcr = d6a.get("put_call_ratio")                  # put/call ratio
    max_voi = d6a.get("max_call_voi") or 0
    high_voi = d6a.get("high_voi_strike_count") or 0
    tcv = d6a.get("total_call_volume") or 0
    tpv = d6a.get("total_put_volume") or 0
    otm = d6a.get("otm_call_volume_5_20pct") or 0

    call_notional, call_biggest = _notional_and_biggest(r.get("top_active_calls"))
    put_notional, put_biggest = _notional_and_biggest(r.get("top_active_puts"))

    # Bearish from raw volumes too — put_call_ratio collapses to 0 when call
    # volume is 0 (the most extreme bearish case), so don't rely on pcr alone.
    bearish = (pcr is not None and pcr > PCR_BEARISH) or (tpv > 0 and tcv == 0) \
        or (tcv > 0 and tpv / tcv > PCR_BEARISH)
    bullish = (cp is not None and cp >= 1.5 and high_voi >= 1) or (cp is not None and cp >= CP_STRONG)

    if bearish and put_notional >= call_notional:
        direction, notional, biggest, ratio = "bearish", put_notional, put_biggest, pcr
    elif bullish:
        direction, notional, biggest, ratio = "bullish", call_notional, call_biggest, cp
    else:
        return None  # not unusual enough

    # Alert gate: must have a positive $ estimate (a "$0 unusual flow" alert is
    # self-contradictory — happens when every active strike lacks premium), AND
    # clear the notional floor OR a very strong skew + multi-strike V/OI.
    if notional <= 0 or (notional < min_notional
                         and not (high_voi >= 3 and (cp or 0) >= CP_STRONG)):
        return None

    tags = []
    if high_voi >= 3:
        tags.append("多檔V/OI暴量")
    elif high_voi >= 1:
        tags.append("V/OI暴量")
    if direction == "bullish" and otm and tcv and otm / tcv >= 0.5:
        tags.append("OTM偏多集中")
    if biggest and (biggest.get("notional") or 0) >= 1_000_000:
        tags.append("百萬級量")  # aggregate strike volume, NOT a single block (free data)
    if max_voi >= 5:
        tags.append(f"峰值V/OI {max_voi:g}")

    return {
        "ticker": ticker,
        "direction": direction,
        "flow_score": _flow_score(notional, max_voi, ratio or 0),
        "est_notional_usd": round(notional),
        "biggest": biggest,
        "expiry": r.get("expiration_analyzed"),
        "max_voi": round(float(max_voi), 2),
        "high_voi_strikes": int(high_voi),
        "call_put_ratio": cp,
        "put_call_ratio": pcr,
        "total_call_vol": int(tcv),
        "total_put_vol": int(tpv),
        "otm_call_vol": int(otm),
        "tags": tags,
        "spot": spot,
        "provider": r.get("source", "yfinance_free"),
    }


def _uw_flow(ticker: str, min_notional: int = MIN_NOTIONAL) -> dict | None:  # noqa: ARG001
    """Unusual Whales provider (real sweeps/blocks/aggressor) — NOT YET WIRED.

    When a UW subscription is available, parse the UW flow endpoint here and map
    to the same signal shape as _free_flow (add sweep/block/aggressor tags). Until
    then flow_provider falls back to _free_flow."""
    raise NotImplementedError("Unusual Whales provider not yet implemented")


def flow_provider(ticker: str, min_notional: int = MIN_NOTIONAL) -> dict | None:
    """Pick the flow source: Unusual Whales (paid, real sweeps) when wired + keyed,
    else the free yfinance detector. Never raises."""
    if os.environ.get("UNUSUAL_WHALES_API_KEY"):
        try:
            return _uw_flow(ticker, min_notional)
        except Exception:
            pass  # UW not implemented / failed → fall back to free
    return _free_flow(ticker, min_notional)


def scan(tickers: list[str], min_notional: int = MIN_NOTIONAL,
         sleep: float = 0.0) -> list[dict]:
    """Scan tickers for unusual flow; return signals ranked by flow_score desc."""
    signals = []
    deduped = list(dict.fromkeys(tickers))  # dedup, preserve order
    for i, t in enumerate(deduped):
        sig = flow_provider(t, min_notional)
        if sig:
            signals.append(sig)
        if sleep and i + 1 < len(deduped):
            time.sleep(sleep)
    signals.sort(key=lambda s: s.get("flow_score", 0), reverse=True)
    return signals


def _fmt_notional(n: float | None) -> str:
    if not n:
        return "$0"
    return f"${n / 1e6:.1f}M" if n >= 1e6 else f"${n / 1e3:.0f}K"


def _md_escape(s: str) -> str:
    """Neutralise legacy-Markdown specials in a dynamic token (e.g. odd tickers)."""
    for ch in ("_", "*", "`", "["):
        s = s.replace(ch, " ")
    return s


def _exp_short(exp: str | None) -> str:
    """YYYY-MM-DD → M/D; tolerate any other shape (return as-is) without raising."""
    try:
        if exp and len(exp) >= 10:
            return f"{int(exp[5:7])}/{int(exp[8:10])}"
    except (ValueError, TypeError):
        pass
    return exp or ""


def format_post(sig: dict) -> str:
    """One bullflow-style post (Telegram Markdown). Honest framing: this is unusual
    call/put VOLUME (skew), not a confirmed block/sweep or aggressor side."""
    bullish = sig.get("direction") == "bullish"
    emoji = "🟢" if bullish else "🔴"
    kind = "偏多 · 買權量異常" if bullish else "偏空 · 賣權量異常"
    b = sig.get("biggest") or {}
    exp_short = _exp_short(sig.get("expiry"))
    parts = [f"估 {_fmt_notional(sig.get('est_notional_usd'))}"]
    if b.get("strike") is not None:
        parts.append(f"{b['strike']:g}{'C' if bullish else 'P'} {exp_short}".strip())
    if sig.get("max_voi"):
        parts.append(f"V/OI {sig['max_voi']:g}")
    ratio = sig.get("call_put_ratio") if bullish else sig.get("put_call_ratio")
    if ratio:
        parts.append(f"{'call/put' if bullish else 'put/call'} {ratio:g}×")
    lines = [f"{emoji} *${_md_escape(str(sig.get('ticker', '')))}* {kind}", " · ".join(parts)]
    if sig.get("tags"):
        lines.append("標籤: " + " · ".join(sig["tags"]))
    return "\n".join(lines)


def _notify(signals: list[dict], top: int) -> bool:
    """Push the top-N signals to Telegram (silent skip if creds absent)."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[options_flow] TELEGRAM_* not set — skipping notify.", file=sys.stderr)
        return False
    if not signals:
        return False
    send = _load("05_notify", "send_telegram_message")
    head = f"🚨 *選擇權異常流* · {datetime.now(timezone.utc):%Y-%m-%d}（前 {min(top, len(signals))} 筆）"
    body = "\n\n".join([head] + [format_post(s) for s in signals[:top]])
    return bool(send(token, chat, body))


def _universe(arg: str | None) -> list[str]:
    if arg:
        return [t.strip().upper() for t in arg.split(",") if t.strip()]
    tickers = list(LIQUID_OPTIONABLE)
    # Merge in the day's scored candidates so screener picks get a flow check.
    try:
        scored = json.loads((REPO / "scored_candidates.json").read_text(encoding="utf-8"))
        for c in scored.get("all_scored", []) or []:
            t = c.get("ticker")
            if t:
                tickers.append(t.upper())
    except Exception:
        pass
    return list(dict.fromkeys(tickers))


def main() -> int:
    ap = argparse.ArgumentParser(description="Unusual options-flow scan → alerts")
    ap.add_argument("--universe", default=None,
                    help="comma tickers; default = curated liquid list + today's candidates")
    ap.add_argument("--min-notional", type=int, default=MIN_NOTIONAL)
    ap.add_argument("--top", type=int, default=DEFAULT_TOP, help="signals saved to JSON")
    ap.add_argument("--notify-top", type=int, default=DEFAULT_NOTIFY_TOP)
    ap.add_argument("--notify", action="store_true", help="push top signals to Telegram")
    ap.add_argument("--sleep", type=float, default=0.0, help="seconds between tickers")
    ap.add_argument("--output", default=None)
    args = ap.parse_args()

    tickers = _universe(args.universe)
    print(f"[options_flow] scanning {len(tickers)} tickers "
          f"(min_notional=${args.min_notional:,}) …", file=sys.stderr)
    signals = scan(tickers, args.min_notional, args.sleep)
    print(f"[options_flow] {len(signals)} unusual-flow signals.", file=sys.stderr)

    now = datetime.now(timezone.utc)
    payload = {
        "generated_at": now.isoformat(),
        "as_of": now.strftime("%Y-%m-%d"),
        "provider": signals[0]["provider"] if signals else "yfinance_free",
        "universe_size": len(tickers),
        "min_notional": args.min_notional,
        "signal_count": len(signals),
        "note": "Free yfinance: unusual VOLUME (V/OI spike + skew + est notional). "
                "True sweeps/blocks/dark-pool need a paid feed (Unusual Whales).",
        "signals": signals[:args.top],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dated = Path(args.output) if args.output else OUT_DIR / f"{payload['as_of']}.json"
    dated.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "latest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[options_flow] → {dated}")

    for s in signals[:10]:
        print(f"  {s['flow_score']:5.1f}  {s['direction']:7}  {s['ticker']:6}  "
              f"{_fmt_notional(s['est_notional_usd']):>7}  V/OI {s['max_voi']:g}  "
              f"{'·'.join(s['tags'])}")

    if args.notify:
        try:  # the JSON is already persisted; a notify glitch must not fail the run
            ok = _notify(signals, args.notify_top)
        except Exception as e:  # noqa: BLE001
            print(f"[options_flow] notify error (report already written): {e}", file=sys.stderr)
            ok = False
        print(f"[options_flow] telegram: {'sent' if ok else 'skipped/failed'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
