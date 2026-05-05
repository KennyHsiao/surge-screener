---
name: monthly_performance_reflection
description: Monthly self-audit of the surge screener's predictions. Reads the performance ledger from the past 30/60/90 days, identifies which dimensions had predictive power and which didn't, flags systematic errors, and proposes prompt adjustments. Run on the 1st of each month or on-demand.
---

# Monthly Performance Reflection — Self-Audit Skill

## When to invoke

- 1st of each month, automatically via GitHub Actions
- On-demand when the user wants a system health check
- After a notable drawdown or unexpected hit-rate change

This is a backward-looking analysis, not a forward-looking recommendation. The output goes to the user as a report, NOT directly back into the prompt as auto-tuning.

---

## Inputs

- `ledger_path`: path to `reports/performance_ledger.csv`
- `lookback_days`: 30 / 60 / 90 (default 30)
- `current_prompts_dir`: path to active system_prompts/ (for reference, not modification)

## Ledger Format Expected

Each row is one recommendation made N days ago, with N-day forward results filled in:

```csv
scan_date,ticker,verdict,composite_score,regime_multiplier,
tech_score,catalyst_score,sentiment_score,inst_score,sector_score,options_score,
dim1_breakdown,pattern_type,macd_state,
layer2_path,layer2_outcome,
dd_verdict,dd_short_thesis_strength,
suggested_entry_low,suggested_entry_high,suggested_stop,suggested_size_pct,
fwd_3d_return,fwd_7d_return,fwd_14d_return,fwd_30d_return,fwd_60d_return,
hit_15pct_within_30d,hit_30pct_within_60d,
max_drawdown_30d,
notes
```

---

## Workflow

### Step 1 — Compute Baseline Metrics

For the lookback window, compute:

1. **Hit rate at multiple thresholds**:
   - % of CONFIRMED picks that hit +15% within 30 days
   - % that hit +30% within 60 days (true surge target)
   - % that hit stop loss before any gain
   - Average max drawdown
   - Average forward return at 7/14/30/60 days

2. **Hit rate by composite score band**:
   - 65–69 / 70–74 / 75–79 / 80–84 / 85+
   - Goal: monotonically increasing hit rate by score band. If 65–69 hits more often than 75–79, scoring is broken.

3. **Hit rate by regime**:
   - Bull regime (multiplier 1.0) vs. neutral (0.85) vs. correction (0.70)
   - Validate that the multiplier is doing real work, not over-penalizing or under-penalizing

### Step 2 — Dimension Predictive Power Analysis

For each of the 6 dimensions, compute:

**Dimension utility = Spearman correlation between dimension score and forward 30-day return.**

Output as table:

| Dimension | Avg score | Correlation with 30d return | Predictive? |
|---|---|---|---|
| Technical | 22.4 | +0.31 | ✅ working |
| Catalyst | 14.1 | +0.18 | ✅ working |
| Sentiment | 11.2 | -0.04 | ⚠️ no signal |
| Institutional | 7.8 | +0.22 | ✅ working |
| Sector | 3.9 | +0.05 | ⚠️ marginal |
| Options Flow | 14.5 | +0.41 | ✅ strong |

**Red flags:**
- Negative correlation = the dimension is actively misleading; should be inverted or removed
- Near-zero correlation (|r| < 0.1) = dimension adds noise, weight should be reduced
- Strong positive (r > 0.3) = dimension is doing heavy lifting, weight could potentially increase

### Step 3 — Hard Filter Audit

For each rejected candidate where data is available (the system saved their scores before rejection):

- How many rejected candidates would have hit +30% in 60 days? (False negatives — filter too tight)
- For each filter, compute its individual rejection rate and the forward return of those rejected

If Hard Filter X rejects 50 candidates per month and only 1 of them hit +30%, the filter is fine.
If Hard Filter X rejects 50 and 15 hit +30%, the filter is over-aggressive.

### Step 4 — Pattern-Type Subgroup Analysis

Group all CONFIRMED picks by `pattern_type` (VCP / Cup-handle / Flat base / Bull flag / W-bottom reversal / etc.):

| Pattern | N picks | Hit rate +30%/60d | Avg fwd 30d return |
|---|---|---|---|
| VCP | 12 | 50% | +18% |
| Cup-handle | 8 | 38% | +12% |
| Flat base | 5 | 40% | +9% |
| Bull flag | 14 | 21% | +4% |
| W-bottom reversal | 3 | 67% | +28% |
| Inverse H&S | 2 | 50% | +15% |

This identifies which patterns truly precede surges. Bull flags scoring 6 pts but hitting only 21% means they're overrated — should drop to 4 pts.

### Step 5 — Engine Controller Decision Audit

For each Layer 2 decision in the lookback:

- Did BREADTH calls find new disqualifying or confirming info? Or were they wasted?
- Did DEPTH calls verify the strong dimension or reveal it was noise?
- Did TERMINATE decisions correctly stop weak candidates from getting DD?

**Compute "decision regret"**:
- BREADTH regret = candidates where BREADTH found nothing actionable AND prediction failed
- DEPTH regret = candidates where DEPTH confirmed strong signal AND prediction still failed
- TERMINATE regret = candidates terminated that would have been winners

If a single decision type has high regret, the Engine Controller decision matrix needs adjustment.

### Step 6 — Layer 3 Dexter DD Audit

For each candidate that received DD:

- Did "CONFIRMED" picks outperform "DOWNGRADED" picks? (Sanity check: DD should add value, not noise.)
- Did the mandatory short thesis correctly identify failure modes?
- Were there post-mortems where DD said CONFIRMED but stock failed for a reason DD should have caught?

### Step 7 — Synthesis & Recommendations

Output a structured report:

```json
{
  "report_date": "2026-06-01",
  "lookback_days": 30,
  "total_picks": 47,
  "confirmed_picks": 24,
  "headline_metrics": {
    "hit_15pct_30d": 0.46,
    "hit_30pct_60d": 0.21,
    "hit_stop_first": 0.29,
    "avg_30d_return": 0.087,
    "sharpe_proxy": 1.4
  },
  "scoring_health": {
    "monotonic_score_to_returns": true,
    "best_band": "80-84 (hit rate 67%)",
    "worst_band": "65-69 (hit rate 18%)",
    "verdict": "scoring works but threshold could move from 65 to 70"
  },
  "dimension_health": [
    {"dim": "options_flow", "correlation": 0.41, "verdict": "STRONG_KEEP"},
    {"dim": "technical", "correlation": 0.31, "verdict": "KEEP"},
    {"dim": "institutional", "correlation": 0.22, "verdict": "KEEP"},
    {"dim": "catalyst", "correlation": 0.18, "verdict": "KEEP"},
    {"dim": "sector", "correlation": 0.05, "verdict": "MARGINAL_CONSIDER_REDUCE"},
    {"dim": "sentiment", "correlation": -0.04, "verdict": "NO_SIGNAL_INVESTIGATE"}
  ],
  "pattern_winners": ["VCP", "W-bottom reversal"],
  "pattern_losers": ["Bull flag"],
  "filter_audit": {
    "filter_5_200dma": "appropriately tight — only 2 false negatives in 220 rejections",
    "filter_7_macd": "NEW filter, only 30 days data, monitor"
  },
  "engine_controller_audit": {
    "breadth_useful_pct": 0.62,
    "depth_useful_pct": 0.78,
    "terminate_regret_count": 2,
    "verdict": "DEPTH allocation healthy, BREADTH could be more selective"
  },
  "dd_audit": {
    "confirmed_vs_downgraded_alpha": 0.12,
    "verdict": "DD adds 12pp to forward returns — keep"
  },
  "proposed_prompt_changes": [
    {
      "file": "01_surge_screener_prompt.md",
      "section": "Dimension 3 (Sentiment)",
      "rationale": "Sentiment correlation -0.04 over 30 days. Either the X data source is noisy or the scoring rubric is wrong. Investigate before changing weights.",
      "suggested_change": "INVESTIGATE_DO_NOT_AUTO_CHANGE",
      "user_action_required": true
    },
    {
      "file": "01_surge_screener_prompt.md",
      "section": "1c Pattern recognition — Bull flag",
      "rationale": "Bull flag scored 6 pts but only 21% hit rate. Overrated.",
      "suggested_change": "Reduce bull flag from 6 pts to 4 pts",
      "user_action_required": true
    }
  ],
  "regime_specific_observations": [
    "All but 1 of the +30% hits occurred in regime multiplier 1.0 (bull). System should be even more conservative in lower-regime months."
  ],
  "narrative_summary": "30-day hit rate of 46% on +15% threshold is within target. Options flow remains the highest-utility dimension, validating the v3.1 architecture. Sentiment dimension is currently dead weight — needs investigation, possibly X API quality issue. Engine Controller's DEPTH bias is paying off; BREADTH could be tightened. No urgent action required, but two suggested changes flagged for human review."
}
```

---

## Critical Rules

1. **Do not auto-modify prompts.** Output is a report. The user reviews and decides which changes to apply. Auto-tuning would cause prompt drift over time.
2. **Be honest about small samples.** With <50 picks, statistical significance is weak. Flag this. Recommend longer lookback if needed.
3. **Don't confuse correlation with causation.** A dimension correlating with returns might just be capturing the same signal as another dimension. Watch for this in the multi-dim regression.
4. **Don't only celebrate wins.** Every report should explicitly call out the 2-3 worst losses and trace why the system didn't catch the failure ahead of time. This is where the real learning is.
5. **Account for regime drift.** A dimension that worked in bull regime may not work in correction. Always cross-tab dimension utility with regime.
6. **Survivorship bias warning.** If you only analyze CONFIRMED picks, you miss the rejected candidates that would have soared. Step 3 (filter audit) catches this.
