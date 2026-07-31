#!/usr/bin/env python3
"""Sector rotation read — LLM synthesis over the verified RRG data.

scripts/sector_flow.py computes the numbers (RS-Ratio / RS-Momentum / quadrants /
heat); this stage hands those VERIFIED numbers — plus a light macro snapshot
(SPY vs 50/200DMA, VIX) — to the LLM and asks for a plain-language read:
WHERE hot money is now and WHERE it rotates next, grounded in business-cycle
rotation theory (early/mid/late cycle, risk-on/off). The model explains and
forecasts; it never invents numbers (verified-data-to-AI principle). Output is a
human-review reference, NOT investment advice.

Writes reports/sector_rotation.json (read by ui/sector_rotation.py). This uses
Codex subscription quota and runs on demand / on a schedule.

CLI:
    python scripts/sector_rotation.py                       # Codex subscription
    python scripts/sector_rotation.py --no-llm              # dry-run: verified data only
    python scripts/sector_rotation.py --provider codex
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import sector_flow as sf  # noqa: E402

try:
    from llm_client import LLMClient
except ImportError:  # when imported as a package (scripts.sector_rotation)
    from scripts.llm_client import LLMClient

OUT = REPO / "reports" / "sector_rotation.json"
SNAPSHOT_ARCHIVE_DIR = REPO / "reports" / "sector_rotation_snapshots"

SYSTEM = """You are a senior macro / sector strategist. You are given VERIFIED, \
pre-computed sector Relative-Rotation-Graph (RRG) data and a macro snapshot — \
all numbers are already calculated from real market data. DO NOT invent or change \
any number; reason only from what you are given.

RRG primer: RS-Ratio is the sector's relative strength vs SPY measured against its \
own ~10-month baseline — >100 means it is trading ABOVE that baseline (a durable \
outperformer), <100 a laggard. RS-Momentum is whether that relative strength is \
currently rising (>100) or fading (<100). Quadrants rotate clockwise: Leading \
(strong & rising) → Weakening (strong but fading) → Lagging (weak & falling) → \
Improving (weak but turning up) → Leading. "Hot money now" = Leading + high \
heat_score. "Next rotation" = Improving sectors (RS-Ratio<100 but RS-Momentum>100), \
the early rotation-in signal.

Ground your read in business-cycle sector rotation (early-cycle: financials, \
discretionary, industrials, materials; mid: tech; late: energy, staples, \
healthcare, utilities) and the risk-on/off macro regime. Be specific and concrete.

Return ONLY a valid JSON object, no prose around it:
{
  "headline": "<one-sentence summary of the current rotation state, in Traditional Chinese>",
  "hot_now": [{"etf": "XLK", "name": "科技", "why": "<short, in zh-TW>"}],
  "rotating_into": [{"etf": "XLI", "name": "工業", "why": "<why money is starting to flow here, zh-TW>"}],
  "next_rotation_thesis": "<2-3 sentences forecasting the next sector rotation, zh-TW>",
  "cycle_read": "<which business-cycle phase the rotation pattern implies + risk-on/off, zh-TW>",
  "confidence": "high | medium | low",
  "caveats": ["<key uncertainty, zh-TW>"]
}"""


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of an LLM response (tolerates fences/trailing prose).

    Uses a real JSON parser (raw_decode) from the first '{', so a brace inside a
    string value can't truncate it the way a naive brace counter would."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.split("\n")
        end = next((i for i in range(1, len(lines))
                    if lines[i].strip().startswith("```")), len(lines))
        t = "\n".join(lines[1:end])
    start = t.find("{")
    if start == -1:
        raise ValueError("no JSON object in response")
    obj, _ = json.JSONDecoder().raw_decode(t[start:])
    if not isinstance(obj, dict):
        raise ValueError("extracted JSON is not an object")
    return obj


def _normalize_read(read) -> dict:
    """Coerce a raw LLM read to the exact shape the UI consumes, so a wrong-typed
    field (e.g. hot_now as a string instead of a list of dicts) can't be persisted
    as 'ready' and later crash the page on `h.get(...)`. Unknown keys are dropped."""
    if not isinstance(read, dict):
        return {}

    def _s(v):
        return v if isinstance(v, str) else ("" if v is None else str(v))

    def _items(v):  # keep only dict entries (each rendered via .get())
        return [h for h in v if isinstance(h, dict)] if isinstance(v, list) else []

    return {
        "headline": _s(read.get("headline")),
        "confidence": _s(read.get("confidence")) or "—",
        "hot_now": _items(read.get("hot_now")),
        "rotating_into": _items(read.get("rotating_into")),
        "next_rotation_thesis": _s(read.get("next_rotation_thesis")),
        "cycle_read": _s(read.get("cycle_read")),
        "caveats": [c for c in read.get("caveats", []) if isinstance(c, str)]
        if isinstance(read.get("caveats"), list) else [],
    }


def _macro_snapshot() -> dict:
    """Best-effort SPY (vs 50/200DMA) + VIX context for the LLM. Never raises."""
    try:
        import numpy as np
        import yfinance as yf
        spy = yf.Ticker("SPY").history(period="1y")["Close"].dropna()
        vix = yf.Ticker("^VIX").history(period="1mo")["Close"].dropna()
        px = float(spy.iloc[-1])
        ma50 = float(spy.iloc[-50:].mean()) if len(spy) >= 50 else None
        ma200 = float(spy.iloc[-200:].mean()) if len(spy) >= 200 else None
        return {
            "spy_price": round(px, 2),
            "spy_vs_50dma": ("above" if ma50 and px > ma50 else "below") if ma50 else None,
            "spy_vs_200dma": ("above" if ma200 and px > ma200 else "below") if ma200 else None,
            "vix_level": round(float(vix.iloc[-1]), 2) if len(vix) else None,
        }
    except Exception:
        return {}


def _verified_payload() -> dict | None:
    """Assemble the verified RRG + macro data fed to the LLM (no tails — token thrift)."""
    flow = sf.gather_sector_flow()
    if not flow:
        return None
    sectors = [{k: v for k, v in s.items() if k != "tail"} for s in flow["sectors"]]
    return {
        "as_of": flow.get("as_of"),
        "benchmark": flow.get("benchmark"),
        "leaders": flow.get("leaders"),
        "improving": flow.get("improving"),
        "macro": _macro_snapshot(),
        "sectors": sectors,
    }


def _snapshot_date(payload: dict) -> str:
    for key in ("as_of", "as_of_date", "scan_date"):
        if payload.get(key):
            return str(payload.get(key))[:10]
    generated_at = str(payload.get("generated_at") or "")
    if generated_at:
        return generated_at[:10]
    return datetime.now(timezone.utc).date().isoformat()


def _write_json(path: Path, data: dict) -> None:
    if path.is_symlink():
        path = path.resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _write_rotation_snapshot(
    payload: dict,
    *,
    output: str | Path = OUT,
    archive_dir: str | Path | None = SNAPSHOT_ARCHIVE_DIR,
) -> None:
    out = Path(output)
    _write_json(out, payload)
    if archive_dir is None:
        return
    as_of = _snapshot_date(payload)
    if not as_of:
        return
    _write_json(Path(archive_dir) / f"{as_of}.json", payload)


def generate_rotation_read(provider: str = "codex",
                           model: str | None = None,
                           no_llm: bool = False,
                           output: str = str(OUT)) -> dict:
    """Compute the verified data, ask the LLM for the rotation read, persist JSON.

    ``no_llm`` returns the verified payload WITHOUT calling the LLM or writing —
    a dry run for testing the data assembly."""
    verified = _verified_payload()
    if not verified:
        return {"status": "no_data",
                "generated_at": datetime.now(timezone.utc).isoformat()}
    if no_llm:
        return {"status": "verified_only", **verified}

    user = ("Verified sector RRG + macro data (numbers are final — explain, "
            "don't recompute):\n" + json.dumps(verified, ensure_ascii=False, indent=2))
    try:
        resp = LLMClient(provider=provider, model=model).chat(SYSTEM, user, max_tokens=2500)
        read = _normalize_read(_extract_json(resp))
        if not read.get("headline"):  # reject an empty/garbage object → don't persist junk
            raise ValueError("LLM read missing required fields (headline)")
    except Exception as e:  # noqa: BLE001 — surface a status, never crash the caller
        return {"status": "error", "error": str(e),
                "as_of": verified.get("as_of"),
                "generated_at": datetime.now(timezone.utc).isoformat()}

    out = {
        "status": "ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": verified.get("as_of"),
        "benchmark": verified.get("benchmark"),
        "leaders": verified.get("leaders"),
        "improving": verified.get("improving"),
        "macro": verified.get("macro"),
        "sectors": verified.get("sectors"),
        "read": read,
    }
    p = Path(output)
    default_archive = SNAPSHOT_ARCHIVE_DIR
    if p.resolve(strict=False) != OUT.resolve(strict=False):
        default_archive = p.parent / "sector_rotation_snapshots"
    _write_rotation_snapshot(out, output=p, archive_dir=default_archive)
    return out


def write_verified_rotation_snapshot(
    *,
    archive_dir: str | Path = SNAPSHOT_ARCHIVE_DIR,
) -> dict:
    """Persist verified RRG data as a dated Analytics snapshot without calling the LLM."""
    verified = _verified_payload()
    if not verified:
        return {
            "status": "no_data",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    payload = {
        "status": "verified_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **verified,
    }
    as_of = _snapshot_date(payload)
    _write_json(Path(archive_dir) / f"{as_of}.json", payload)
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description="Sector rotation — LLM read over RRG data")
    ap.add_argument("--provider", default="codex", choices=["auto", "codex"])
    ap.add_argument("--model", default=None,
                    help="Optional Codex model; defaults to CODEX_MODEL/account setting")
    ap.add_argument("--no-llm", action="store_true", help="dry run: verified data only")
    ap.add_argument("--output", default=str(OUT))
    args = ap.parse_args()

    res = generate_rotation_read(args.provider, args.model, args.no_llm, args.output)
    if args.no_llm:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get("status") == "verified_only" else 1  # no_data → exit 1
    if res.get("status") != "ready":
        print(f"[sector_rotation] {res.get('status')}: {res.get('error', '')}",
              file=sys.stderr)
        return 1
    r = res["read"]
    print(f"as_of={res['as_of']}  confidence={r.get('confidence')}")
    print(f"頭條: {r.get('headline')}")
    print(f"現在熱錢: {[h.get('etf') for h in r.get('hot_now', [])]}")
    print(f"輪動進入: {[h.get('etf') for h in r.get('rotating_into', [])]}")
    print(f"下一波研判: {r.get('next_rotation_thesis')}")
    print(f"→ {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
