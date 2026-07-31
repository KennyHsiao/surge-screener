#!/usr/bin/env python3
"""Fundamentals read — LLM synthesis over the verified free-fundamentals snapshot.

scripts/fundamentals_free.py fetches the numbers (valuation / profitability /
growth / balance-sheet health / analyst backdrop, free yfinance .info, cached
6h); this stage hands those VERIFIED numbers to the LLM and asks for a
plain-language investment read: is this a quality business, is it cheap/fair/
rich, what's the thesis. The model reasons only from the given numbers — it never
invents ratios (verified-data-to-AI principle). Output is a human-review
reference, NOT investment advice.

The free snapshot has NO peer comparison and NO historical trend (those need paid
.financials), so the prompt frames valuation in ABSOLUTE terms and the caveats
must flag that limitation.

Writes reports/fundamentals_read/<TICKER>.json (read on demand by ui/_fundamentals.py).
This uses Codex subscription quota and runs on demand / on a schedule.

CLI:
    python scripts/fundamentals_read.py NVDA                 # Codex subscription
    python scripts/fundamentals_read.py NVDA --no-llm        # dry-run: verified data only
    python scripts/fundamentals_read.py NVDA --provider codex
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import fundamentals_free as ff  # noqa: E402

try:
    from llm_client import LLMClient
except ImportError:  # when imported as a package (scripts.fundamentals_read)
    from scripts.llm_client import LLMClient

OUT_DIR = REPO / "reports" / "fundamentals_read"

SYSTEM = """You are a senior equity research analyst. You are given VERIFIED, \
pre-computed fundamental ratios for ONE stock — valuation (P/E, forward P/E, P/B, \
P/S, PEG, EV/EBITDA), profitability margins (gross/operating/net, ROE, ROA), \
growth (revenue, earnings), balance-sheet health (debt/equity, current & quick \
ratio, free cash flow, cash, debt) and an analyst backdrop. All numbers are from \
real market/filing data. DO NOT invent or change any number; reason only from what \
you are given.

IMPORTANT context limits: these are FREE single-snapshot values. You are NOT given \
peer/sector comparables and NOT given any historical trend or CAGR. So judge \
valuation in ABSOLUTE terms (and say where peer/trend context would be needed), and \
do not claim a multi-year trajectory you cannot see. Margins/growth are already in \
percent. debt_to_equity is a percentage (e.g. 150 means 1.5x).

Return ONLY a valid JSON object, no prose around it:
{
  "headline": "<one sentence, Traditional Chinese: is this a quality business and is it cheap/fair/rich>",
  "quality_grade": "strong | ok | weak",
  "valuation_read": "cheap | fair | rich | expensive",
  "strengths": [{"metric": "毛利率 73%", "why": "<short, zh-TW>"}],
  "concerns": [{"metric": "預估本益比 65x", "why": "<short, zh-TW>"}],
  "thesis": "<2-3 sentences, zh-TW: the investment case grounded in the ratios>",
  "confidence": "high | medium | low",
  "caveats": ["<key uncertainty, zh-TW>", "免費單點快照,無同業比較與歷史趨勢,僅供方向性參考。"]
}"""


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of an LLM response (tolerates fences/trailing prose)."""
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
    """Coerce a raw LLM read to the exact shape the UI consumes so a wrong-typed
    field can't be persisted as 'ready' and later crash the page. Unknown keys dropped."""
    if not isinstance(read, dict):
        return {}

    def _s(v):
        return v if isinstance(v, str) else ("" if v is None else str(v))

    def _items(v):  # keep only dict entries with at least one string field
        return [{"metric": _s(h.get("metric")), "why": _s(h.get("why"))}
                for h in v if isinstance(h, dict)] if isinstance(v, list) else []

    return {
        "headline": _s(read.get("headline")),
        "quality_grade": _s(read.get("quality_grade")) or "—",
        "valuation_read": _s(read.get("valuation_read")) or "—",
        "strengths": _items(read.get("strengths")),
        "concerns": _items(read.get("concerns")),
        "thesis": _s(read.get("thesis")),
        "confidence": _s(read.get("confidence")) or "—",
        "caveats": [c for c in read.get("caveats", []) if isinstance(c, str)]
        if isinstance(read.get("caveats"), list) else [],
    }


def _output_path(ticker: str, output: str | None) -> Path:
    return Path(output) if output else (OUT_DIR / f"{ticker.upper()}.json")


def generate_fundamentals_read(ticker: str, provider: str = "codex",
                               model: str | None = None,
                               no_llm: bool = False,
                               output: str | None = None) -> dict:
    """Fetch verified fundamentals, ask the LLM for the read, persist JSON.

    ``no_llm`` returns the verified payload WITHOUT calling the LLM or writing —
    a dry run for testing the data assembly."""
    ticker = (ticker or "").strip().upper().lstrip("$")
    data = ff.gather_fundamentals(ticker)
    if not data:
        return {"status": "no_data", "ticker": ticker,
                "generated_at": datetime.now(timezone.utc).isoformat()}
    if no_llm:
        return {"status": "verified_only", **data}

    user = ("Verified fundamentals (numbers are final — explain, don't recompute):\n"
            + json.dumps(data, ensure_ascii=False, indent=2))
    try:
        resp = LLMClient(provider=provider, model=model).chat(SYSTEM, user, max_tokens=1800)
        read = _normalize_read(_extract_json(resp))
        if not read.get("headline"):  # reject empty/garbage → don't persist junk
            raise ValueError("LLM read missing required fields (headline)")
    except Exception as e:  # noqa: BLE001 — surface a status, never crash the caller
        return {"status": "error", "error": str(e), "ticker": ticker,
                "generated_at": datetime.now(timezone.utc).isoformat()}

    out = {
        "status": "ready",
        "ticker": ticker,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verified": data,
        "read": read,
    }
    p = _output_path(ticker, output)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Fundamentals — LLM read over verified ratios")
    ap.add_argument("tickers", nargs="*", default=["NVDA"], help="ticker(s)")
    ap.add_argument("--provider", default="codex", choices=["auto", "codex"])
    ap.add_argument("--model", default=None,
                    help="Optional Codex model; defaults to CODEX_MODEL/account setting")
    ap.add_argument("--no-llm", action="store_true", help="dry run: verified data only")
    ap.add_argument("--output", default=None, help="explicit output path (single ticker)")
    args = ap.parse_args()
    for t in (args.tickers or ["NVDA"]):
        res = generate_fundamentals_read(t, provider=args.provider, model=args.model,
                                         no_llm=args.no_llm, output=args.output)
        print(f"=== {t} === status={res.get('status')}")
        print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
