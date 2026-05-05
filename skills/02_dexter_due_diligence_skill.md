---
name: us_surge_due_diligence
description: Deep due diligence on US stock candidates flagged by the surge screener. Pulls SEC filings, insider transactions, X sentiment, and competitor data, then issues a final go/no-go with reasoning. Use when a candidate scored ≥65 on the screener and `due_diligence_required: true`.
---

# US Surge Stock — Deep Due Diligence

## When to invoke

The screener has flagged a US ticker with composite score ≥65. Before this candidate enters the trade-ready watchlist, run this skill to verify the signal isn't a trap.

Your job is to FALSIFY the bull case. If after honest investigation you cannot break it, the candidate passes. If you find a material red flag, the candidate is downgraded or rejected, regardless of how good the technicals look.

---

## Inputs

- `ticker`: the US ticker symbol
- `screener_signals`: the JSON output from the surge screener for this ticker
- `as_of_date`: today's date

---

## Workflow

### Step 1 — Latest 10-Q Review

Use `read_filings` to pull the most recent 10-Q. Extract and verify:

1. Revenue trajectory (last 4 quarters): is growth accelerating, decelerating, or flat?
2. Gross margin trend: expanding, stable, or compressing?
3. Operating cash flow: positive and growing, or burning?
4. Debt structure: any covenant risk, refinancing wall in <12 months?
5. Share count: is the company aggressively diluting? (Compare diluted share count vs. 4 quarters ago.)
6. Risk factors section: any new risks added vs. prior 10-Q?

**Red flag thresholds:**
- Revenue growth decelerated by >10 percentage points QoQ → flag
- Gross margin contracted >200bps QoQ without explanation → flag
- Diluted share count up >5% YoY without buyback offset → flag
- New material risk factor added → flag

### Step 2 — Recent 8-K Scan (Last 90 Days)

Use `read_filings` for 8-K. For each 8-K in last 90 days:

- Categorize the event (Item 1.01, 2.02, 5.02, 7.01, 8.01, etc.)
- Determine if material positive, material negative, or routine
- For positive catalysts: verify the screener's catalyst score is properly attributed (don't double-count)
- For negative items (executive departures, going-concern, restated financials): **automatic veto** of WATCHLIST status

### Step 3 — Insider & Institutional Cross-Check

Use `financial_metrics` and web tools:

1. Form 4 filings last 90 days: count distinct insider buyers, total dollar value, biggest single buyer's role (CEO buying is more credible than director buying)
2. 13F latest quarter: net institutional change. If a top-tier fund (Tiger, Lone Pine, Coatue, Berkshire, etc.) initiated or doubled, note explicitly
3. Cross-check short interest: pull current short interest %, days-to-cover, and trend (rising or falling). A surge candidate with rising short interest into the catalyst is a high-octane setup; falling short interest may mean the squeeze is firing.

### Step 4 — X / Social Sentiment Verification

Use the `x_search` tool with the ticker symbol AND the company name. Check:

1. Mention velocity: pull last 48h and last 30d, calculate ratio
2. Top 10 most-engaged posts in last 48h: are they substantive (analysis, news links, fundamental commentary) or are they pure pump ("🚀🚀 to the moon")?
3. Account quality: are tracked credible accounts (financial journalists, known fund managers) discussing? Or is it dominated by anonymous accounts that joined in last 90 days?

**Red flag:** if >70% of recent mentions come from accounts <90 days old, this is likely a coordinated pump. Veto WATCHLIST.

### Step 4.5 — Options Flow Smart Money Verification (US tickers only)

If Unusual Whales MCP server (or equivalent options flow data) is connected, run this step. If unavailable, mark `data_gaps: ["options_flow"]` and proceed.

Pull and analyze:

1. **Last 5–10 trading days of unusual options activity for this ticker:**
   - Identify the largest sweeps and blocks
   - For each: note the strike, expiration, premium, side (bid/ask), and whether opening or closing
   - Map to an inferred thesis: "Big buyer accumulating 30DTE OTM calls = expects move within 30 days"

2. **Cross-reference with the catalyst:**
   - If options flow timing aligns with a known upcoming event (earnings, FDA decision, conference), the flow is corroborative
   - If options flow is heavy but NO known catalyst exists, this is either: (a) a leak/insider situation (rare, regulatory risk to follow), (b) a coordinated pump, or (c) someone with a private thesis. Treat with caution.

3. **Check for opposing flow:**
   - Are there ALSO meaningful put sweeps or block put buys?
   - If yes, this is a "battleground" name — institutions disagree. Lower confidence.
   - If put flow is purely small/retail-sized while calls are institutional-sized, the bullish thesis stands.

4. **Gamma exposure (GEX) regime:**
   - Negative GEX + call wall above current price = squeeze setup, mechanical price acceleration possible on rally
   - Positive GEX = price suppression regime, surges are harder
   - Use this to calibrate position sizing, not to overrule other signals

**Red flag:** Aggressive bid-side put sweeps in the last 5 trading days (>$2M total premium) — even if the bull case looks strong, smart money is hedging or shorting. Veto.

**Output for this step:**
```json
{
  "options_flow_verdict": "CORROBORATIVE | NEUTRAL | CONTRADICTORY | NO_DATA",
  "biggest_recent_sweep": "$1.8M premium, 30DTE 155C, bid-side, opening",
  "implied_thesis": "Buyer expects move to $155+ within 30 days — aligns with earnings 18 days out",
  "opposing_flow": "minimal put activity, retail-sized only",
  "gex_regime": "negative, call wall at $155 — squeeze setup confirmed",
  "veto_triggered": false
}
```

### Step 5 — Competitor & Industry Reality Check

Use `web_search` for:

1. The 2–3 closest competitors' recent earnings: is the whole industry surging, or is this an isolated story?
2. Industry-specific data points (e.g., for semis: foundry utilization; for biotech: trial pipeline; for SaaS: NRR benchmarks)
3. Any recent industry headwinds (regulation, supply chain, demand softening)

If the bull thesis depends on industry tailwinds that are weakening, mark as inconsistent.

### Step 6 — Falsification Test

Explicitly write the SHORT thesis. What would a smart short-seller say to bet against this?

- What's the most fragile assumption in the bull case?
- What single piece of news would crater the stock?
- Is anything currently priced in that hasn't actually happened yet?

If the short thesis has more concrete evidence than the long thesis, this is not a surge candidate.

---

## Output

```json
{
  "ticker": "NVDA",
  "dd_completed": "2026-05-05T22:14:00Z",
  "screener_score": 78,
  "dd_verdict": "CONFIRMED | DOWNGRADED | REJECTED",
  "dd_score_adjustment": -3,
  "final_score": 75,
  "filings_review": {
    "10q_health": "STRONG | MIXED | DETERIORATING",
    "key_findings": ["Revenue accel 28% → 42% YoY", "Gross margin +180bps QoQ", "No new material risk factors"],
    "red_flags": []
  },
  "8k_findings": {
    "positive_events_90d": 2,
    "negative_events_90d": 0,
    "biggest_catalyst": "$2B contract with major hyperscaler — Item 1.01, filed 3 days ago"
  },
  "insider_institutional": {
    "form4_buyers_90d": 3,
    "form4_total_value": "$2.1M",
    "top_13f_initiator": "Lone Pine Capital — new 0.8% position",
    "short_interest_pct": 4.2,
    "short_interest_trend": "stable"
  },
  "social_quality": {
    "velocity_ratio": 4.2,
    "top_post_quality": "SUBSTANTIVE",
    "credible_account_engagement": true,
    "pump_risk": "LOW"
  },
  "industry_context": {
    "industry_trend": "TAILWIND",
    "peer_comparison": "Outperforming TSM, AVGO on margin profile",
    "concerns": []
  },
  "short_thesis_summary": "Valuation rich on FY27 estimates. Revenue concentration in top-3 hyperscalers is the single biggest tail risk. Earnings miss in next print would trigger 15–20% drawdown.",
  "short_thesis_strength": "MODERATE",
  "final_recommendation": "PROCEED with sized entry. Use tight stops given valuation. Reduce or exit before next earnings if no further catalyst confirms.",
  "data_gaps": []
}
```

---

## Skill rules

1. **No fabricated filings.** If a 10-Q or 8-K isn't accessible, mark `data_gaps` and downgrade verdict by one notch (CONFIRMED → DOWNGRADED).
2. **One run per query.** This skill is heavy — don't loop it. If the analysis isn't conclusive, output `dd_verdict: "INCONCLUSIVE"` and explain.
3. **Always do Step 6 (Falsification).** Skipping the short thesis is the #1 way to fall in love with a position. Mandatory.
4. **Time-boxed.** If a step isn't yielding signal in reasonable token budget, summarize what you found and move on.
