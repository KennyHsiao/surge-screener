#!/usr/bin/env python3
"""
Stage 2 — LLM Scoring (Layer 0 + Layer 1)
Layer 0: Base Prompter — compute regime context once.
Layer 1: Breadth Pass — score each candidate on 7 dimensions via LLM.
Outputs scored_candidates.json with regime_context attached.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

# Shared LLM client (claude_agent / anthropic / openai / deepseek; see llm_client.py).
try:
    from llm_client import LLMClient
except ImportError:  # when imported as a package (scripts.02_llm_score)
    from scripts.llm_client import LLMClient


# ---------------------------------------------------------------------------
# Data enrichment helpers
# ---------------------------------------------------------------------------

def enrich_with_market_data(tickers: list[dict]) -> dict:
    """Fetch SPY and VIX data for regime context.

    SPY/VIX now go through the shared cached_closes helper (P1a dedup): SPY 1y is
    re-used by risk_guard within the cache TTL instead of each re-fetching. A
    fetch failure still propagates into the per-source except below (degrade, not
    crash) — cached_closes never masks a failure.
    """
    try:
        from _yfinance import cached_closes
    except ImportError:
        from scripts._yfinance import cached_closes

    regime = {}
    try:
        spy_close = cached_closes("SPY", "1y")
        if spy_close:
            regime["spy_price"] = float(spy_close[-1])
            regime["spy_50dma"] = float(sum(spy_close[-50:]) / 50) if len(spy_close) >= 50 else None
            regime["spy_200dma"] = float(sum(spy_close[-200:]) / 200) if len(spy_close) >= 200 else None
            # guard None (short history): float > None raises TypeError, which the
            # outer except would swallow — silently dropping the whole regime block
            regime["spy_vs_50dma"] = ("above" if regime["spy_50dma"] is not None
                                      and spy_close[-1] > regime["spy_50dma"] else "below")
            regime["spy_vs_200dma"] = ("above" if regime["spy_200dma"] is not None
                                       and spy_close[-1] > regime["spy_200dma"] else "below")
    except Exception as e:
        print(f"[llm_score] SPY data error: {e}", file=sys.stderr)

    try:
        # period "1mo" (not "5d") so this shares one cache key with
        # risk_guard._live_regime's VIX fetch — only the latest close is used
        # (vix_level = last value), so the longer window is identical here but
        # actually achieves the SPY+VIX regime dedup across both callers.
        vix_close = cached_closes("^VIX", "1mo")
        if vix_close:
            regime["vix_level"] = float(vix_close[-1])
    except Exception as e:
        print(f"[llm_score] VIX data error: {e}", file=sys.stderr)

    return regime


def fetch_options_flow_summary(ticker: str) -> dict | None:
    """Fetch options flow data. Tries Unusual Whales first, falls back to free yfinance."""
    # Try Unusual Whales (paid, full data)
    api_key = os.environ.get("UNUSUAL_WHALES_API_KEY")
    if api_key:
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        base = "https://api.unusualwhales.com/api"
        try:
            resp = httpx.get(f"{base}/stock/{ticker}/options-flow",
                             headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return {"source": "unusual_whales",
                        "flow_data": data.get("data", [])[:20]}
        except Exception:
            pass

    # Fallback: free yfinance options chain analysis
    try:
        from scripts.options_free import analyze_options
        result = analyze_options(ticker)
        if result.get("available"):
            return {"source": "yfinance_free", "options_analysis": result}
    except ImportError:
        # Try relative import for when run from project root
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "options_free",
                Path(__file__).parent / "options_free.py",
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            result = mod.analyze_options(ticker)
            if result.get("available"):
                return {"source": "yfinance_free", "options_analysis": result}
        except Exception:
            pass

    return None


def fetch_polygon_news(ticker: str) -> list[dict]:
    """Fetch recent news from Polygon API."""
    api_key = os.environ.get("POLYGON_API_KEY")
    if not api_key:
        return []

    try:
        resp = httpx.get(
            "https://api.polygon.io/v2/reference/news",
            params={"ticker": ticker, "limit": 5, "apiKey": api_key},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("results", [])
    except Exception:
        pass
    return []


def fetch_free_sentiment(ticker: str) -> dict | None:
    """Free social sentiment (StockTwits + Reddit/ApeWisdom). No API key needed.

    Never raises — returns None on any failure so a flaky free source cannot abort
    the whole scoring run (matches fetch_polygon_news / fetch_options_flow_summary).
    """
    try:
        try:
            from scripts.sentiment_free import gather_free_sentiment
        except ImportError:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "sentiment_free", Path(__file__).parent / "sentiment_free.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            gather_free_sentiment = mod.gather_free_sentiment
        return gather_free_sentiment(ticker)
    except Exception:
        return None


def _load_free_module(mod_name: str, func_name: str):
    """Import a scripts/<mod_name>.py free-data helper, with a path fallback for
    when 02_llm_score is run as a loose script rather than a package."""
    try:
        mod = __import__(f"scripts.{mod_name}", fromlist=[func_name])
        return getattr(mod, func_name)
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            mod_name, Path(__file__).parent / f"{mod_name}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return getattr(mod, func_name)


def fetch_fundamentals(ticker: str) -> dict | None:
    """Free fundamentals / key ratios (yfinance). Never raises."""
    try:
        return _load_free_module("fundamentals_free", "gather_fundamentals")(ticker)
    except Exception:
        return None


def fetch_institutional(ticker: str) -> dict | None:
    """Free institutional ownership + insider activity (Dim 4). Never raises."""
    try:
        return _load_free_module("institutional_free", "gather_institutional")(ticker)
    except Exception:
        return None


def fetch_analyst_views(ticker: str) -> dict | None:
    """Free sell-side analyst consensus (Dim 7 / 分析師共識). Never raises."""
    try:
        return _load_free_module("analyst_free", "gather_analyst_views")(ticker)
    except Exception:
        return None


_SECTOR_ROTATION_MEMO: dict = {}


def fetch_sector_rotation() -> dict | None:
    """Verified sector RRG summary for Dimension 5. Never raises.

    Memoized process-wide: the sector snapshot is a single point-in-time read for
    the whole run (like regime_context), so compute_regime_context and every
    per-candidate score_candidate call share ONE computation."""
    if "v" not in _SECTOR_ROTATION_MEMO:
        try:
            _SECTOR_ROTATION_MEMO["v"] = _load_free_module("sector_flow", "rotation_summary")()
        except Exception:
            _SECTOR_ROTATION_MEMO["v"] = None
    return _SECTOR_ROTATION_MEMO["v"]


def gics_to_etf(gics_sector: str | None) -> str | None:
    """Map a candidate's GICS sector string → its SPDR sector ETF. Never raises."""
    try:
        return _load_free_module("sector_flow", "etf_for_gics")(gics_sector)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Layer 0: Regime Context
# ---------------------------------------------------------------------------

def compute_regime_context(llm: LLMClient, screener_prompt: str,
                           market_data: dict) -> dict:
    """Run Layer 0 Base Prompter to compute regime context."""
    from datetime import datetime

    vix = market_data.get("vix_level", 20)
    spy_vs_50 = market_data.get("spy_vs_50dma", "unknown")
    spy_vs_200 = market_data.get("spy_vs_200dma", "unknown")

    # Compute multiplier deterministically per the rules
    multiplier = 1.0
    if spy_vs_200 == "above" and spy_vs_50 == "below" and 20 <= vix <= 25:
        multiplier = 0.85
    elif spy_vs_200 == "below" and 25 <= vix <= 30:
        multiplier = 0.70
    elif spy_vs_200 == "below" and vix > 30:
        multiplier = 0.50

    # Determine VIX regime
    if vix < 15:
        vix_regime = "low"
    elif vix <= 20:
        vix_regime = "normal"
    elif vix <= 30:
        vix_regime = "elevated"
    else:
        vix_regime = "panic"

    # Use LLM to identify active themes
    user_msg = f"""Based on current market conditions:
- SPY vs 50DMA: {spy_vs_50}
- SPY vs 200DMA: {spy_vs_200}
- VIX: {vix}
- Date: {datetime.utcnow().strftime('%Y-%m-%d')}

Identify 3-5 currently active investment themes in the US stock market.
Return ONLY a JSON object with this structure:
{{
  "active_themes": ["theme1", "theme2", ...],
  "regime_warnings": ["warning1", ...],
  "earnings_season_phase": "pre | active | post"
}}"""

    try:
        resp = llm.chat(
            system="You are a market analyst. Return ONLY valid JSON.",
            user=user_msg,
            max_tokens=1024,
        )
        # Extract JSON from response
        themes_data = _extract_json(resp)
    except Exception as e:
        print(f"[llm_score] Theme detection error: {e}", file=sys.stderr)
        themes_data = {"active_themes": [], "regime_warnings": [],
                       "earnings_season_phase": "unknown"}

    regime_context = {
        "scan_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "spy_vs_50dma": spy_vs_50,
        "spy_vs_200dma": spy_vs_200,
        "vix_level": vix,
        "vix_regime": vix_regime,
        "global_score_multiplier": multiplier,
        "active_themes": themes_data.get("active_themes", []),
        "regime_warnings": themes_data.get("regime_warnings", []),
        "earnings_season_phase": themes_data.get("earnings_season_phase", "unknown"),
    }

    # Verified sector rotation (RRG): store only the LIGHT board-level context in
    # regime_context (small + ASCII) so every downstream prompt that dumps
    # regime_context stays lean. Layer-1 score_candidate pulls the full per-sector
    # by_etf itself (memoized) to ground Dimension 5 — no need to persist/forward the
    # heavy CJK board into the engine-controller / DD / report prompts that ignore it.
    _srot = fetch_sector_rotation()
    regime_context["sector_rotation"] = (
        {"as_of": _srot.get("as_of"), "leaders": _srot.get("leaders"),
         "improving": _srot.get("improving")} if _srot else None)

    return regime_context


# ---------------------------------------------------------------------------
# Layer 1: Breadth Pass
# ---------------------------------------------------------------------------

def score_candidate(llm: LLMClient, screener_prompt: str, regime_context: dict,
                    candidate: dict, case_library: str = "") -> dict:
    """Score a single candidate on 7 dimensions via LLM."""
    ticker = candidate["ticker"]

    # Gather additional data
    news = fetch_polygon_news(ticker)
    options_flow = fetch_options_flow_summary(ticker)
    sentiment_data = fetch_free_sentiment(ticker)
    fundamentals = fetch_fundamentals(ticker)
    institutional = fetch_institutional(ticker)
    analyst = fetch_analyst_views(ticker)

    news_text = ""
    if news:
        news_text = "\n".join(
            f"- [{n.get('published_utc', '')}] {n.get('title', '')}"
            for n in news[:5]
        )

    # Serialize whichever options source we actually have: paid sweep flow_data OR
    # the FREE yfinance chain analysis (scores + chain_summary). Previously only
    # flow_data was used, so without Unusual Whales the free options signal was
    # silently dropped and Dimension 6 was always scored as "missing".
    options_text = ""
    options_available = bool(options_flow)
    if options_flow and options_flow.get("flow_data"):
        options_text = json.dumps(options_flow["flow_data"][:10], indent=2)
    elif options_flow and options_flow.get("options_analysis"):
        options_text = json.dumps(options_flow["options_analysis"], indent=2)
    else:
        options_available = False

    sentiment_text = ""
    if sentiment_data and sentiment_data.get("sources_available"):
        sentiment_text = json.dumps(sentiment_data, indent=2, ensure_ascii=False)

    fundamentals_text = json.dumps(fundamentals, indent=2) if fundamentals else ""
    institutional_text = (json.dumps(institutional, indent=2, ensure_ascii=False)
                          if institutional else "")
    analyst_text = (json.dumps(analyst, indent=2, ensure_ascii=False)
                    if analyst else "")

    # Verified sector rotation for Dimension 5: the candidate's OWN sector standing
    # (mapped from its GICS sector → SPDR ETF) plus the market leaders/improving.
    sector_text = ""
    srot = fetch_sector_rotation() or {}  # full board (memoized) — has per-sector by_etf
    if srot:
        cand_gics = (fundamentals or {}).get("sector")
        cand_etf = gics_to_etf(cand_gics)
        cand_sec = (srot.get("by_etf") or {}).get(cand_etf) if cand_etf else None
        sector_text = json.dumps({
            "candidate_sector": {"gics": cand_gics, "etf": cand_etf, **(cand_sec or {})},
            "market_leaders": srot.get("leaders"),
            "market_improving": srot.get("improving"),
            "as_of": srot.get("as_of"),
        }, ensure_ascii=False, indent=2)

    candidate_json = json.dumps(candidate, indent=2, default=str)

    user_msg = f"""Score the following candidate using the 7-dimension framework (100 pts total).

## Regime Context
{json.dumps(regime_context, indent=2)}

## Candidate Data
{candidate_json}

## Recent News
{news_text if news_text else "No recent news available."}

## Options Flow Data
{options_text if options_text else "No options flow data available — score Dimension 6 as 0 and mark data_missing."}

## Social Sentiment — free sources (StockTwits + Reddit/ApeWisdom)
{sentiment_text if sentiment_text else "No free sentiment data available — score Dimension 3 conservatively and mark data_missing."}
Use this as the primary input for Dimension 3 (Sentiment, 0-13). HEED the calibration_note: StockTwits skews structurally bullish, so reward RELATIVE signals (high message volume, a real bearish share, Reddit mention momentum) — not default bullishness. Judge whether buzz looks organic or coordinated and whether any high-follower / smart-money accounts are involved.

## Fundamentals — free (yfinance: valuation / profitability / growth / health / analyst estimates)
{fundamentals_text if fundamentals_text else "No fundamentals available."}
Use this verified data to ground the catalyst/quality read; do not invent ratios.

## Institutional & Insider Activity — free (yfinance, SEC 13F + Form-4 derived)
{institutional_text if institutional_text else "No institutional/insider data available — score Dimension 4 conservatively and mark data_missing."}
Use this as the PRIMARY input for Dimension 4 (Institutional / 籌碼, 0-10): weight institutional ownership %, notable holder pctChange, and insider net buying/selling. Do NOT guess this dimension when data is present.

## Analyst Consensus — free (yfinance: ratings / price targets / upgrades-downgrades / estimate revisions)
{analyst_text if analyst_text else "No analyst data available — score Dimension 7 conservatively and mark data_missing."}
Use this as the PRIMARY input for Dimension 7 (Analyst Consensus / 分析師共識, 0-8): rating distribution (strongBuy/buy skew), price_targets.upside_pct (mean target vs spot), and recent_actions (dated upgrades / PT raises) plus estimate_revisions (up_last_30d vs down_last_30d). Weight rating MOMENTUM (recent upgrades, PT raises, net-up estimate revisions) over the static consensus — targets are a lagging/anchoring signal. If analyst views contradict the technical/options read, say so in key_risks. Do NOT guess this dimension when data is present.

## Sector Rotation — free (yfinance sector-ETF RRG, RS-Ratio/RS-Momentum vs SPY)
{sector_text if sector_text else "No sector rotation data available — score Dimension 5a conservatively and mark data_missing."}
Use this as the PRIMARY, VERIFIED input for Dimension 5a (Sector RS, 0-2): score the candidate by its OWN sector's quadrant (candidate_sector.quadrant) — Leading=2, Improving or Weakening=1, Lagging=0 — corroborated by candidate_sector.excess_20d (sector return minus SPY). Do NOT guess sector strength; use these numbers. (5b market regime still comes from SPY/VIX in Regime Context.)

## Historical Case Library Reference
{case_library[:2000] if case_library else "No case library loaded."}

Return ONLY a valid JSON object matching this exact schema:
{{
  "ticker": "{ticker}",
  "as_of_date": "{regime_context.get('scan_date', '')}",
  "verdict": "REJECT | WATCHLIST | NEEDS_LAYER_2",
  "composite_score": <int 0-100>,
  "regime_adjusted_score": <float>,
  "scores": {{
    "technical": <int 0-30>,
    "catalyst": <int 0-16>,
    "sentiment": <int 0-13>,
    "institutional": <int 0-10>,
    "sector_market": <int 0-3>,
    "options_flow": <int 0-20>,
    "analyst": <int 0-8>
  }},
  "technical_breakdown": {{
    "trend_template": <float>,
    "volume": <int>,
    "pattern": <int>,
    "pattern_type": "<string>",
    "macd_confirmation": <int>,
    "macd_state": "<string>"
  }},
  "key_signals": ["<string>", ...],
  "key_risks": ["<string>", ...],
  "suggested_entry_zone": "<string>",
  "suggested_stop": "<string>",
  "suggested_size_pct": <float>,
  "similar_to_case": "<string or null>",
  "anti_example_warning": "<string or null>",
  "novel_pattern": <bool>,
  "data_missing": ["<string>", ...],
  "due_diligence_required": <bool>
}}"""

    try:
        # cache_system=True: the screener rubric (~5.6k tokens) is identical for every
        # candidate, so caching it bills the prompt once per 5-min TTL and reads it
        # cheaply for the other ~250 — the bulk of the daily token spend (anthropic only).
        resp = llm.chat(system=screener_prompt, user=user_msg, max_tokens=4096,
                        cache_system=True)
        result = _extract_json(resp)
        # MACHINE-enforce data_missing for the data-availability we actually know,
        # rather than trusting the LLM to infer it (Phase-2 forward lift reads this to
        # mark a dimension None instead of validating a placeholder/default score).
        dm = result.get("data_missing")
        dm = list(dm) if isinstance(dm, list) else []
        for tok, present in (("options_flow", options_available),
                             ("sentiment", bool(sentiment_text)),
                             ("institutional", bool(institutional_text)),
                             ("analyst", bool(analyst_text))):
            if not present and tok not in dm:
                dm.append(tok)
        result["data_missing"] = dm
        # Ensure regime-adjusted score
        composite = result.get("composite_score", 0)
        multiplier = regime_context.get("global_score_multiplier", 1.0)
        result["regime_adjusted_score"] = round(composite * multiplier, 1)

        # Apply verdict rules
        adj_score = result["regime_adjusted_score"]
        threshold = 72 if multiplier <= 0.7 else 65
        if adj_score >= threshold:
            result["verdict"] = "NEEDS_LAYER_2"
            result["due_diligence_required"] = True
        elif adj_score >= 50:
            result["verdict"] = "WATCHLIST"
        else:
            result["verdict"] = "REJECT"

        return result
    except Exception as e:
        print(f"[llm_score] Error scoring {ticker}: {e}", file=sys.stderr)
        return {
            "ticker": ticker,
            "verdict": "REJECT",
            "composite_score": 0,
            "regime_adjusted_score": 0,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    """Extract a JSON object from LLM response text."""
    # Try direct parse
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last ``` lines
        start = 1
        end = len(lines) - 1
        for i, line in enumerate(lines):
            if line.strip().startswith("```") and i > 0:
                end = i
                break
        text = "\n".join(lines[start:end])

    # Find JSON object boundaries
    brace_start = text.find("{")
    if brace_start == -1:
        raise ValueError("No JSON object found in response")

    depth = 0
    for i in range(brace_start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[brace_start : i + 1])

    raise ValueError("Malformed JSON in response")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Stage 2: LLM Scoring")
    parser.add_argument("--input", required=True, help="filtered_universe.json")
    parser.add_argument("--prompt", required=True, help="Path to screener prompt .md")
    parser.add_argument("--min-score", type=int, default=65)
    parser.add_argument("--provider", default="auto",
                        choices=["auto", "claude_agent", "anthropic", "openai", "deepseek"])
    parser.add_argument("--model", default="claude-opus-4-8",
                        help="Model for regime + scoring (unless --layer1-model overrides)")
    parser.add_argument("--layer1-model", default=None,
                        help="Cheaper model for the wide Layer-1 breadth scan "
                             "(e.g. claude-sonnet-4-6). Opus stays for Layer 2/3 "
                             "(separate scripts). Falls back to --model if unset.")
    parser.add_argument("--limit", "--max-candidates", type=int, default=None,
                        dest="limit", help="Score at most N (unscored) candidates "
                        "this run — for batching across runs/sessions.")
    parser.add_argument("--resume", action="store_true",
                        help="Skip tickers already in --output and merge; reuse the "
                             "stored regime_context. Lets you score in batches.")
    parser.add_argument("--output", default="scored_candidates.json")
    parser.add_argument("--case-library", default=None,
                        help="Path to 06_historical_case_library.md")
    args = parser.parse_args()

    # Load inputs
    with open(args.input) as f:
        universe = json.load(f)

    screener_prompt = Path(args.prompt).read_text(encoding="utf-8")

    case_library = ""
    if args.case_library and Path(args.case_library).exists():
        case_library = Path(args.case_library).read_text(encoding="utf-8")
    else:
        # Try default location
        default_case = Path("system_prompts/06_historical_case_library.md")
        if default_case.exists():
            case_library = default_case.read_text(encoding="utf-8")

    score_model = args.layer1_model or args.model
    llm = LLMClient(provider=args.provider, model=score_model)

    # Resume: load prior output, skip already-scored tickers, reuse regime.
    prior_scored, done_tickers, regime_context = [], set(), None
    if args.resume and Path(args.output).exists():
        try:
            prior = json.load(open(args.output))
            prior_scored = prior.get("all_scored", [])
            done_tickers = {s.get("ticker") for s in prior_scored}
            regime_context = prior.get("regime_context")
            print(f"[llm_score] Resume: {len(done_tickers)} already scored, "
                  "reusing stored regime_context." if regime_context else
                  f"[llm_score] Resume: {len(done_tickers)} already scored.")
        except Exception as e:
            print(f"[llm_score] Resume read failed ({e}); starting fresh.", file=sys.stderr)

    # Layer 0: Regime context (compute once; reuse on resume)
    if regime_context is None:
        print("[llm_score] Computing regime context (Layer 0) ...")
        market_data = enrich_with_market_data(universe.get("tickers", []))
        regime_context = compute_regime_context(llm, screener_prompt, market_data)
    print(f"[llm_score] Regime: VIX={regime_context.get('vix_level')}, "
          f"multiplier={regime_context.get('global_score_multiplier')}")

    # Layer 1: score the next batch of UNSCORED candidates
    all_candidates = universe.get("tickers", [])
    pending = [c for c in all_candidates if c.get("ticker") not in done_tickers]
    batch = pending[:args.limit] if args.limit else pending
    total = len(all_candidates)
    print(f"[llm_score] {len(done_tickers)} done · scoring {len(batch)} this run "
          f"· {len(pending) - len(batch)} will remain · model={score_model}")

    newly = []
    errored = []
    for i, cand in enumerate(batch):
        ticker = cand["ticker"]
        print(f"  [{i+1}/{len(batch)}] Scoring {ticker} ...")
        res = score_candidate(llm, screener_prompt, regime_context,
                              cand, case_library)
        # A transient failure (e.g. timeout/rate-limit after retries) must NOT be
        # persisted as a finished REJECT — otherwise --resume skips it forever.
        # Leave it out of all_scored so the next batch retries it.
        if res.get("error"):
            errored.append(ticker)
        else:
            newly.append(res)
        if llm.provider in ("anthropic", "claude_agent"):
            time.sleep(0.5)
    if errored:
        print(f"[llm_score] {len(errored)} errored this run (not persisted, will "
              f"retry on resume): {', '.join(errored)}", file=sys.stderr)

    # Merge prior + new, sort by regime_adjusted_score descending
    scored = prior_scored + newly
    scored.sort(key=lambda x: x.get("regime_adjusted_score", 0), reverse=True)
    remaining = total - len(scored)

    # Separate by verdict
    needs_layer2 = [s for s in scored if s.get("verdict") == "NEEDS_LAYER_2"]
    watchlist = [s for s in scored if s.get("verdict") == "WATCHLIST"]
    rejected = [s for s in scored if s.get("verdict") == "REJECT"]

    output = {
        "scan_date": regime_context.get("scan_date"),
        "regime_context": regime_context,
        "universe_size": universe.get("total_universe", 0),
        "passed_hard_filters": universe.get("passed_hard_filters", 0),
        "total_candidates": total,
        "scored_candidates_count": len(scored),
        "remaining_unscored": remaining,
        "needs_layer2_count": len(needs_layer2),
        "watchlist_count": len(watchlist),
        "rejected_count": len(rejected),
        "min_score_threshold": args.min_score,
        "needs_layer2": needs_layer2,
        "watchlist": watchlist,
        "all_scored": scored,
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"[llm_score] Done: {len(needs_layer2)} NEEDS_LAYER_2, "
          f"{len(watchlist)} WATCHLIST, {len(rejected)} REJECT · "
          f"scored {len(scored)}/{total} · {remaining} remaining → {args.output}")


if __name__ == "__main__":
    main()
