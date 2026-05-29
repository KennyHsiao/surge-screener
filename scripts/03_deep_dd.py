#!/usr/bin/env python3
"""
Stage 3 — Dexter Deep Due Diligence (Layer 3, US only)
Filters Layer 2 output to candidates with verdict CONTINUE_TO_DD.
Invokes Dexter DD skill per candidate via LLM.
Outputs dd_results.json.
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
except ImportError:  # when imported as a package (scripts.03_deep_dd)
    from scripts.llm_client import LLMClient


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1
        for i in range(1, len(lines)):
            if lines[i].strip().startswith("```"):
                text = "\n".join(lines[start:i])
                break
    brace = text.find("{")
    if brace == -1:
        raise ValueError("No JSON found")
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[brace : i + 1])
    raise ValueError("Malformed JSON")


# ---------------------------------------------------------------------------
# Data fetching for DD
# ---------------------------------------------------------------------------

def fetch_sec_filings(ticker: str) -> dict:
    """Fetch recent SEC filings summary."""
    user_agent = os.environ.get("SEC_EDGAR_USER_AGENT", "")
    if not user_agent:
        return {"available": False, "reason": "SEC_EDGAR_USER_AGENT not set"}

    headers = {"User-Agent": user_agent, "Accept": "application/json"}
    result = {"10q": [], "8k": []}

    try:
        # Get CIK
        resp = httpx.get(
            f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom"
            f"&startdt=2024-01-01&forms=10-Q,8-K",
            headers=headers, timeout=15,
        )
        # Use full-text search endpoint
        search_resp = httpx.get(
            f"https://efts.sec.gov/LATEST/search-index?q={ticker}&forms=10-Q,8-K&dateRange=custom"
            f"&startdt=2024-01-01",
            headers=headers, timeout=15,
        )
    except Exception:
        pass

    # Try EDGAR company API
    try:
        resp = httpx.get(
            f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
            f"&company=&CIK={ticker}&type=10-Q&dateb=&owner=include&count=3"
            f"&search_text=&action=getcompany&output=atom",
            headers=headers, timeout=15,
        )
        if resp.status_code == 200:
            result["10q_raw_available"] = True
    except Exception:
        pass

    try:
        resp = httpx.get(
            f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
            f"&company=&CIK={ticker}&type=8-K&dateb=&owner=include&count=5"
            f"&search_text=&action=getcompany&output=atom",
            headers=headers, timeout=15,
        )
        if resp.status_code == 200:
            result["8k_raw_available"] = True
    except Exception:
        pass

    result["available"] = True
    return result


def fetch_insider_data(ticker: str) -> dict:
    """Fetch insider transaction data from Polygon or Finnhub."""
    polygon_key = os.environ.get("POLYGON_API_KEY")
    if polygon_key:
        try:
            resp = httpx.get(
                f"https://api.polygon.io/v3/reference/tickers/{ticker}/insiders",
                params={"apiKey": polygon_key, "limit": 20},
                timeout=15,
            )
            if resp.status_code == 200:
                return {"source": "polygon",
                        "transactions": resp.json().get("results", [])}
        except Exception:
            pass

    finnhub_key = os.environ.get("FINNHUB_API_KEY")
    if finnhub_key:
        try:
            resp = httpx.get(
                f"https://finnhub.io/api/v1/stock/insider-transactions",
                params={"symbol": ticker, "token": finnhub_key},
                timeout=15,
            )
            if resp.status_code == 200:
                return {"source": "finnhub",
                        "transactions": resp.json().get("data", [])}
        except Exception:
            pass

    return {"source": None, "transactions": []}


def fetch_options_flow(ticker: str) -> dict:
    """Fetch options flow. Tries Unusual Whales first, falls back to free yfinance."""
    api_key = os.environ.get("UNUSUAL_WHALES_API_KEY")
    if api_key:
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        try:
            resp = httpx.get(
                f"https://api.unusualwhales.com/api/stock/{ticker}/options-flow",
                headers=headers, timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                return {"available": True, "source": "unusual_whales",
                        "flows": data[:30]}
        except Exception:
            pass

    # Fallback: free yfinance analysis
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "options_free", Path(__file__).parent / "options_free.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.analyze_options(ticker)
        if result.get("available"):
            return {"available": True, "source": "yfinance_free",
                    "analysis": result}
    except Exception:
        pass

    return {"available": False}


def fetch_social_sentiment(ticker: str) -> dict:
    """Fetch X/Twitter sentiment if token available."""
    bearer = os.environ.get("X_BEARER_TOKEN")
    if not bearer:
        return {"available": False}

    headers = {"Authorization": f"Bearer {bearer}"}
    try:
        resp = httpx.get(
            "https://api.twitter.com/2/tweets/search/recent",
            params={"query": f"${ticker} lang:en -is:retweet",
                    "max_results": 100,
                    "tweet.fields": "created_at,public_metrics"},
            headers=headers, timeout=15,
        )
        if resp.status_code == 200:
            tweets = resp.json().get("data", [])
            return {"available": True, "tweet_count": len(tweets),
                    "sample": tweets[:10]}
    except Exception:
        pass
    return {"available": False}


# ---------------------------------------------------------------------------
# DD Execution
# ---------------------------------------------------------------------------

def run_dd_for_candidate(llm: LLMClient, skill_prompt: str,
                         candidate: dict, regime_context: dict) -> dict:
    """Run the full Dexter DD skill for one candidate."""
    ticker = candidate["ticker"]

    # Gather all data
    sec_data = fetch_sec_filings(ticker)
    insider_data = fetch_insider_data(ticker)
    options_data = fetch_options_flow(ticker)
    social_data = fetch_social_sentiment(ticker)

    data_gaps = []
    if not sec_data.get("available"):
        data_gaps.append("sec_filings")
    if not insider_data.get("transactions"):
        data_gaps.append("insider_transactions")
    if not options_data.get("available"):
        data_gaps.append("options_flow")
    if not social_data.get("available"):
        data_gaps.append("social_sentiment")

    user_msg = f"""Run deep due diligence on {ticker}.

## Screener Signals (from Layer 1 + Layer 2)
{json.dumps(candidate, indent=2, default=str)}

## Regime Context
{json.dumps(regime_context, indent=2)}

## SEC Filings Data
{json.dumps(sec_data, indent=2, default=str)}

## Insider / Institutional Data
{json.dumps(insider_data, indent=2, default=str)}

## Options Flow Data
{json.dumps(options_data, indent=2, default=str) if options_data.get("available") else "NOT AVAILABLE — score options_flow_verdict as NO_DATA"}

## Social Sentiment Data
{json.dumps(social_data, indent=2, default=str) if social_data.get("available") else "NOT AVAILABLE"}

## Data Gaps
{json.dumps(data_gaps)}

Follow the DD workflow (Steps 1-6) from the skill document. ALWAYS complete Step 6 (Falsification).

Return ONLY a valid JSON object:
{{
  "ticker": "{ticker}",
  "dd_completed": "<ISO timestamp>",
  "screener_score": {candidate.get('final_score', candidate.get('composite_score', 0))},
  "dd_verdict": "CONFIRMED | DOWNGRADED | REJECTED",
  "dd_score_adjustment": <int>,
  "final_score": <int>,
  "filings_review": {{
    "10q_health": "STRONG | MIXED | DETERIORATING | NO_DATA",
    "key_findings": ["<string>"],
    "red_flags": ["<string>"]
  }},
  "8k_findings": {{
    "positive_events_90d": <int>,
    "negative_events_90d": <int>,
    "biggest_catalyst": "<string>"
  }},
  "insider_institutional": {{
    "form4_buyers_90d": <int>,
    "form4_total_value": "<string>",
    "short_interest_pct": <float>,
    "short_interest_trend": "<string>"
  }},
  "social_quality": {{
    "velocity_ratio": <float>,
    "top_post_quality": "SUBSTANTIVE | MIXED | PUMP",
    "pump_risk": "LOW | MODERATE | HIGH"
  }},
  "options_flow_verdict": "CORROBORATIVE | NEUTRAL | CONTRADICTORY | NO_DATA",
  "short_thesis_summary": "<string — MANDATORY>",
  "short_thesis_strength": "WEAK | MODERATE | STRONG",
  "final_recommendation": "<string>",
  "data_gaps": {json.dumps(data_gaps)}
}}"""

    try:
        resp = llm.chat(system=skill_prompt, user=user_msg, max_tokens=6144)
        result = _extract_json(resp)
        result["ticker"] = ticker
        return result
    except Exception as e:
        print(f"  [dd] Error for {ticker}: {e}", file=sys.stderr)
        return {
            "ticker": ticker,
            "dd_verdict": "DOWNGRADED",
            "dd_score_adjustment": -5,
            "final_score": candidate.get("final_score", 0) - 5,
            "error": str(e),
            "data_gaps": data_gaps + ["dd_execution_failed"],
            "short_thesis_summary": "DD could not complete — treat with caution",
            "short_thesis_strength": "UNKNOWN",
        }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Stage 3: Deep DD")
    parser.add_argument("--input", required=True, help="layer2_results.json")
    parser.add_argument("--skill", required=True,
                        help="Path to dexter DD skill .md")
    parser.add_argument("--max-candidates", type=int, default=10)
    parser.add_argument("--us-only", action="store_true")
    parser.add_argument("--provider", default="auto",
                        choices=["auto", "claude_agent", "anthropic", "openai", "deepseek"])
    parser.add_argument("--model", default="claude-opus-4-7")
    parser.add_argument("--output", default="dd_results.json")
    args = parser.parse_args()

    with open(args.input) as f:
        layer2_data = json.load(f)

    skill_prompt = Path(args.skill).read_text(encoding="utf-8")
    llm = LLMClient(provider=args.provider, model=args.model)

    regime_context = layer2_data.get("regime_context", {})
    candidates = layer2_data.get("continue_to_dd", [])

    # Limit to max candidates
    candidates = candidates[: args.max_candidates]

    print(f"[dd] Running deep DD on {len(candidates)} candidates ...")

    results = []
    for i, cand in enumerate(candidates):
        ticker = cand["ticker"]
        print(f"  [{i+1}/{len(candidates)}] DD for {ticker} ...")

        result = run_dd_for_candidate(llm, skill_prompt, cand, regime_context)
        results.append(result)

        verdict = result.get("dd_verdict", "UNKNOWN")
        print(f"    → {verdict} (final_score={result.get('final_score', '?')})")

        time.sleep(1)  # Rate limiting

    confirmed = [r for r in results if r.get("dd_verdict") == "CONFIRMED"]
    downgraded = [r for r in results if r.get("dd_verdict") == "DOWNGRADED"]
    rejected = [r for r in results if r.get("dd_verdict") == "REJECTED"]

    output = {
        "scan_date": regime_context.get("scan_date", ""),
        "regime_context": regime_context,
        "dd_input_count": len(candidates),
        "confirmed_count": len(confirmed),
        "downgraded_count": len(downgraded),
        "rejected_count": len(rejected),
        "confirmed": confirmed,
        "downgraded": downgraded,
        "rejected": rejected,
        "all_dd_results": results,
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"[dd] Done: {len(confirmed)} CONFIRMED, "
          f"{len(downgraded)} DOWNGRADED, {len(rejected)} REJECTED → {args.output}")


if __name__ == "__main__":
    main()
