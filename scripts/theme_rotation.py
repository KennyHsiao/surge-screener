#!/usr/bin/env python3
"""Theme money-flow read — LLM synthesis over the verified theme-flow board.

scripts/theme_flow.py computes the numbers (the Chaikin-$ money-flow PROXY: per-
theme 5d net flow / acceleration / 20d cumulative, the 4-bucket capital state, the
抄底 divergence, heat, 代表股). This stage hands those VERIFIED numbers — plus a
light macro snapshot (SPY vs 50/200DMA, VIX) — to the LLM for a plain-language
zh-TW read: where capital is (proxy-)accelerating in, rotating out, and bottom-
fishing. The model explains; it never invents numbers, and — crucially — it is
told the flow axis is a price×volume PROXY, not real institutional net-buy (法人
淨買超), so it must not narrate it as real fund flow (verified-data-to-AI honesty).

Mirrors scripts/sector_rotation.py: same generate_*_read signature/flags, the
tolerant _extract_json (reused), a defensive _normalize_read (fail-closed on an
empty headline), the SPY/VIX _macro_snapshot (reused). Writes reports/theme_flow.json
(read by ui/theme_flow.py). Paid LLM call — run on demand / on a schedule, never
on every page load.

CLI:
    python scripts/theme_rotation.py                  # provider auto
    python scripts/theme_rotation.py --no-llm         # dry-run: verified data only
    python scripts/theme_rotation.py --provider anthropic --model claude-opus-4-8
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import theme_flow as tflow  # noqa: E402
# Reuse the (identical) macro snapshot + tolerant JSON extractor from the sector read.
from sector_rotation import _extract_json, _macro_snapshot  # noqa: E402

try:
    from llm_client import LLMClient
except ImportError:  # when imported as a package (scripts.theme_rotation)
    from scripts.llm_client import LLMClient

OUT = REPO / "reports" / "theme_flow.json"

SYSTEM = """You are a senior capital-flow strategist reading a US-equity THEME \
money-flow board. You are given VERIFIED, pre-computed numbers — DO NOT invent or \
change any number; reason only from what you are given.

CRITICAL HONESTY: the "flow" here is a FREE-DATA PROXY, not real institutional \
net-buying. It is estimated as the Chaikin money-flow dollar value (where each day's \
close sits in its high-low range, times dollar volume), summed across each theme's \
stocks. It is NOT 法人/主力淨買超, NOT order flow, and cannot see the aggressor side \
or block/sweep prints. NEVER claim real institutional or "smart money" buying — say \
"資金流向(價量推估)" / "推估流入/流出". Treat divergences (price down but proxy-flow up) \
as hypotheses, not facts.

The board's 4 capital states are: 加速流入(推估) = proxy-inflow and accelerating; \
流入趨緩 = proxy-inflow but decelerating; 中性 = near-zero; 流出(推估) = proxy-outflow. \
"抄底(bottom-fishing)" = price fell over 5 days yet proxy-flow is positive (possible \
accumulation into weakness). Big-cap stocks dominate a theme's dollar flow, and \
themes that share the same mega-cap (shown in shared_mega_caps) are NOT independent \
signals — don't double-count them.

Some themes also carry `insider_net_usd_6m` — REAL Form-4 insider net buying/selling \
over ~6 months (real money, NOT the proxy, but a 6-month aggregate, not daily). When \
its SIGN disagrees with the proxy flow — insiders BUYING a proxy-outflow theme \
(potential bullish), or SELLING a proxy-inflow one (potential bearish) — that \
divergence is the single most informative signal on the board; surface it in \
insider_divergence and weight it in your read.

Be specific and concrete, grounded in the verified flow/heat numbers and the macro \
regime (risk-on/off). Return ONLY a valid JSON object, no prose around it:
{
  "headline": "<one-sentence zh-TW summary of where capital is (proxy-)moving>",
  "accelerating_in": [{"theme": "HBM 高頻寬記憶體", "name": "<short zh-TW name>", "why": "<short zh-TW, cite the proxy nature>"}],
  "rotating_out": [{"theme": "...", "name": "...", "why": "<zh-TW>"}],
  "bottom_fishing": [{"theme": "...", "name": "...", "why": "<why this divergence is interesting, zh-TW>"}],
  "insider_divergence": [{"theme": "...", "name": "...", "why": "<real Form-4 insiders disagree with the proxy flow, zh-TW>"}],
  "next_thesis": "<2-3 sentences zh-TW on what the proxy-flow pattern implies next>",
  "confidence": "high | medium | low",
  "caveats": ["<key uncertainty, zh-TW — at least note the proxy is not real fund flow>"]
}"""


def _normalize_read(read) -> dict:
    """Coerce a raw LLM read to the exact shape the UI consumes, so a wrong-typed
    field can't be persisted as 'ready' and later crash the page. Mirrors
    sector_rotation._normalize_read but for the theme-flow read keys."""
    if not isinstance(read, dict):
        return {}

    def _s(v):
        return v if isinstance(v, str) else ("" if v is None else str(v))

    def _items(v):  # keep only dict entries (each rendered via .get())
        return [h for h in v if isinstance(h, dict)] if isinstance(v, list) else []

    return {
        "headline": _s(read.get("headline")),
        "confidence": _s(read.get("confidence")) or "—",
        "accelerating_in": _items(read.get("accelerating_in")),
        "rotating_out": _items(read.get("rotating_out")),
        "bottom_fishing": _items(read.get("bottom_fishing")),
        "insider_divergence": _items(read.get("insider_divergence")),
        "next_thesis": _s(read.get("next_thesis")),
        "caveats": [c for c in read.get("caveats", []) if isinstance(c, str)]
        if isinstance(read.get("caveats"), list) else [],
    }


def _verified_payload() -> dict | None:
    """Assemble the verified theme-flow board + macro fed to the LLM.

    Trim each theme to the fields the read needs (no heavy nested data — the board
    has no tails; reps are tiny) so the prompt stays lean."""
    flow = tflow.gather_theme_flow()
    if not flow:
        return None
    # Real Form-4 insider net-buy overlay (best-effort; 6h-cached, may be None).
    ins_by = (tflow.gather_theme_insider() or {}).get("by_theme", {})
    themes = []
    for r in flow["themes"]:
        t = {
            "theme": r["theme"], "desc": r.get("desc"),
            "state": r["capital_state"], "heat": r.get("heat_score"),
            "flow_5d_norm": r["flow_5d_norm"], "accel_norm": r.get("accel_norm"),
            "flow_20d_norm": r["flow_20d_norm"], "ret_5d": r.get("ret_5d"),
            "top_share": r.get("top_share"), "high_concentration": r["high_concentration"],
            "bottom_fishing": r["bottom_fishing"],
            "reps": [x["ticker"] for x in r["reps"]],
            "parents": r["parent_sector_etfs"],
        }
        ins = ins_by.get(r["theme"])
        if ins and ins.get("insider_net_usd") is not None:
            t["insider_net_usd_6m"] = ins["insider_net_usd"]
            t["insider_buy_sell_count"] = f"{ins.get('n_buy', 0)}buy/{ins.get('n_sell', 0)}sell"
            t["insider_coverage"] = f"{ins.get('n_cov')}/{ins.get('n_total')}"
        themes.append(t)
    return {
        "as_of": flow.get("as_of"),
        "benchmark": flow.get("benchmark"),
        "buckets": flow.get("buckets"),
        "bottom_fishing": flow.get("bottom_fishing"),
        "shared_mega_caps": flow.get("shared_mega_caps"),
        "macro": _macro_snapshot(),
        "themes": themes,
    }


def generate_theme_flow_read(provider: str = "auto",
                             model: str = "claude-opus-4-8",
                             no_llm: bool = False,
                             output: str = str(OUT)) -> dict:
    """Compute the verified board, ask the LLM for the theme-flow read, persist JSON.

    ``no_llm`` returns the verified payload WITHOUT calling the LLM or writing — a
    dry run for testing the data assembly. Never raises (returns a status dict)."""
    verified = _verified_payload()
    if not verified:
        return {"status": "no_data",
                "generated_at": datetime.now(timezone.utc).isoformat()}
    if no_llm:
        return {"status": "verified_only", **verified}

    user = ("Verified THEME money-flow PROXY board + macro (numbers are final — "
            "explain, don't recompute; the flow is a price×volume proxy, NOT real "
            "fund flow):\n" + json.dumps(verified, ensure_ascii=False, indent=2))
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
        "buckets": verified.get("buckets"),
        "bottom_fishing": verified.get("bottom_fishing"),
        "macro": verified.get("macro"),
        "read": read,
    }
    p = Path(output)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Theme money-flow — LLM read over the proxy board")
    ap.add_argument("--provider", default="auto",
                    choices=["auto", "claude_agent", "anthropic", "openai", "deepseek"])
    ap.add_argument("--model", default="claude-opus-4-8")
    ap.add_argument("--no-llm", action="store_true", help="dry run: verified data only")
    ap.add_argument("--output", default=str(OUT))
    args = ap.parse_args()

    res = generate_theme_flow_read(args.provider, args.model, args.no_llm, args.output)
    if args.no_llm:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get("status") == "verified_only" else 1  # no_data → exit 1
    if res.get("status") != "ready":
        print(f"[theme_rotation] {res.get('status')}: {res.get('error', '')}",
              file=sys.stderr)
        return 1
    r = res["read"]
    print(f"as_of={res['as_of']}  confidence={r.get('confidence')}")
    print(f"頭條: {r.get('headline')}")
    print(f"推估流入: {[h.get('theme') for h in r.get('accelerating_in', [])]}")
    print(f"推估流出: {[h.get('theme') for h in r.get('rotating_out', [])]}")
    print(f"抄底: {[h.get('theme') for h in r.get('bottom_fishing', [])]}")
    print(f"→ {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
