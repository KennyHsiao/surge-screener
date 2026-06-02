#!/usr/bin/env python3
"""
Stage 2 — LLM Scoring (Layer 0 + Layer 1)
Layer 0: Base Prompter — compute regime context once.
Layer 1: Breadth Pass — score each candidate on 6 dimensions via LLM.
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
    """Fetch SPY and VIX data for regime context."""
    import yfinance as yf

    regime = {}
    try:
        spy = yf.Ticker("SPY")
        spy_hist = spy.history(period="1y")
        if not spy_hist.empty:
            spy_close = spy_hist["Close"].values
            regime["spy_price"] = float(spy_close[-1])
            regime["spy_50dma"] = float(spy_close[-50:].mean()) if len(spy_close) >= 50 else None
            regime["spy_200dma"] = float(spy_close[-200:].mean()) if len(spy_close) >= 200 else None
            # guard None (short history): float > None raises TypeError, which the
            # outer except would swallow — silently dropping the whole regime block
            regime["spy_vs_50dma"] = ("above" if regime["spy_50dma"] is not None
                                      and spy_close[-1] > regime["spy_50dma"] else "below")
            regime["spy_vs_200dma"] = ("above" if regime["spy_200dma"] is not None
                                       and spy_close[-1] > regime["spy_200dma"] else "below")
    except Exception as e:
        print(f"[llm_score] SPY data error: {e}", file=sys.stderr)

    try:
        vix = yf.Ticker("^VIX")
        vix_hist = vix.history(period="5d")
        if not vix_hist.empty:
            regime["vix_level"] = float(vix_hist["Close"].values[-1])
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
            f"https://api.polygon.io/v2/reference/news",
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

    return regime_context


# ---------------------------------------------------------------------------
# Layer 1: Breadth Pass
# ---------------------------------------------------------------------------

def score_candidate(llm: LLMClient, screener_prompt: str, regime_context: dict,
                    candidate: dict, case_library: str = "") -> dict:
    """Score a single candidate on 6 dimensions via LLM."""
    ticker = candidate["ticker"]

    # Gather additional data
    news = fetch_polygon_news(ticker)
    options_flow = fetch_options_flow_summary(ticker)
    sentiment_data = fetch_free_sentiment(ticker)
    fundamentals = fetch_fundamentals(ticker)
    institutional = fetch_institutional(ticker)

    news_text = ""
    if news:
        news_text = "\n".join(
            f"- [{n.get('published_utc', '')}] {n.get('title', '')}"
            for n in news[:5]
        )

    options_text = ""
    if options_flow and options_flow.get("flow_data"):
        options_text = json.dumps(options_flow["flow_data"][:10], indent=2)

    sentiment_text = ""
    if sentiment_data and sentiment_data.get("sources_available"):
        sentiment_text = json.dumps(sentiment_data, indent=2, ensure_ascii=False)

    fundamentals_text = json.dumps(fundamentals, indent=2) if fundamentals else ""
    institutional_text = (json.dumps(institutional, indent=2, ensure_ascii=False)
                          if institutional else "")

    candidate_json = json.dumps(candidate, indent=2, default=str)

    user_msg = f"""Score the following candidate using the 6-dimension framework (100 pts total).

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
Use this as the primary input for Dimension 3 (Sentiment, 0-15). HEED the calibration_note: StockTwits skews structurally bullish, so reward RELATIVE signals (high message volume, a real bearish share, Reddit mention momentum) — not default bullishness. Judge whether buzz looks organic or coordinated and whether any high-follower / smart-money accounts are involved.

## Fundamentals — free (yfinance: valuation / profitability / growth / health / analyst estimates)
{fundamentals_text if fundamentals_text else "No fundamentals available."}
Use this verified data to ground the catalyst/quality read; do not invent ratios.

## Institutional & Insider Activity — free (yfinance, SEC 13F + Form-4 derived)
{institutional_text if institutional_text else "No institutional/insider data available — score Dimension 4 conservatively and mark data_missing."}
Use this as the PRIMARY input for Dimension 4 (Institutional / 籌碼, 0-10): weight institutional ownership %, notable holder pctChange, and insider net buying/selling. Do NOT guess this dimension when data is present.

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
    "catalyst": <int 0-20>,
    "sentiment": <int 0-15>,
    "institutional": <int 0-10>,
    "sector_market": <int 0-5>,
    "options_flow": <int 0-20>
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
        resp = llm.chat(system=screener_prompt, user=user_msg, max_tokens=4096)
        result = _extract_json(resp)
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
    parser.add_argument("--model", default="claude-opus-4-7",
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
