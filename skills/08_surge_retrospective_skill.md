---
name: surge_retrospective
description: Ground-truth surge retrospective. Reads pre-surge factor-lift tables mined from stocks that ACTUALLY surged (not the screener's own picks), judges which of the screener's technical/sector sub-factors are validated, noise, or contrarian, and proposes weight + prompt changes for human review. The forward-looking complement to monthly_performance_reflection's backward audit of picks.
---

# Surge Retrospective — Factor-Validation Skill

## When to invoke

- Monthly via GitHub Actions (offset from the self-reflection job)
- On-demand when the user wants to know which indicators actually precede surges
- After tuning the screener rubric, to re-check factor validity against ground truth

This is **ground-truth mining**, the complement to `monthly_performance_reflection`.
That skill audits the screener's OWN picks (selection-biased — only what passed the
filter). THIS skill mines ALL stocks that actually surged in the market and asks,
for each scoring sub-factor: was it present at the surge's launch more often than at
a random moment? Output is a report for human review, never auto-tuning.

## What the numbers mean

Inputs are pre-computed (pure numpy, no LLM): for each factor flag, measured at the
**confirmation day** (first session ~7% above the trough — the realistic momentum
screener entry, NOT the literal bottom):

- `p_surge` — share of surge events where the factor was present
- `p_control` — share of random non-surge (ticker, date) points where it was present
- `lift = p_surge / p_control` — how much more often before a surge than at random.
  >1 predictive, ≈1 noise, <1 present LESS before surges (contrarian).
- `lift_ci90` — 90% bootstrap confidence interval (capped at 50)
- `precision_lift` — lift of P(surge | factor) over the base rate
- `information_value` — WoE-weighted separation
- `support` — number of surge events with the factor present (the sample behind it)
- `verdict` — VALIDATED / WEAK / NOISE / CONTRARIAN / INSUFFICIENT (support-gated)

Tables are produced **per surge threshold** (+30%/20d, +40%/40d, +50%/60d) plus a
combined ALL table. A factor that stays predictive as the threshold rises is stronger
evidence than one that only works for the mildest surges.

## Scope and caveats (state these in the report)

- **Only Dim1 (Technical) and Dim5 (Sector/Market) are validated here.** Dim2
  (Catalyst), Dim3 (Sentiment), Dim4 (Institutional), Dim6 (Options flow) are NOT
  free-reconstructable historically — they are the job of Phase 1.5 (EDGAR backfill)
  and Phase 2 (forward snapshots). Do NOT make claims about those dimensions.
- **Survivorship bias**: index lists are current members only; delisted surgers are
  absent and some names joined the index after surging. This inflates "already in an
  uptrend" factors. Temper trend-factor conclusions accordingly.
- **Small samples**: if the run flags `low_confidence` (or any factor's support < 20),
  treat verdicts as directional, not conclusive. Recommend a wider universe / longer
  lookback before acting.
- **Contrarian ≠ useless**: a CONTRARIAN trend factor often means surges launched from
  reversals (oversold bottoms) that the continuation-biased rubric structurally MISSES
  — a coverage gap, not necessarily a factor to delete.

## The rubric you map recommendations back to (Dim1=30, Dim5=5)

- 1a Trend Template (10): MA stack, distance to 52w high/low, RS — `price_above_ma200`,
  `ma_stack_50_150_200`, `price_above_ma50`, `within_25pct_of_high`, `above_30pct_of_low`
- 1b Volume (8): `rvol_ge_2`, `breakout_above_resist`, `price_above_vwap`
- 1c Pattern (9): `bb_squeeze`, `rsi_40_65`
- 1d MACD (3): `macd_positive`, `macd_golden_cross_10d`
- 5a Sector RS (3): `rel_strength_vs_spy`
- 5b Regime (2): `market_regime_ok`

Keep Dim1 sub-allocations summing to 30 and Dim5 to 5 in any proposal.

## Output (return ONLY this JSON, then a short narrative)

```json
{
  "report_date": "2026-06-02",
  "universe": "sp1500",
  "lookback_days": 730,
  "surge_event_count": 312,
  "low_confidence": false,
  "validated_factors": [
    {"factor": "rvol_ge_2", "subfactor": "1b Volume", "lift": 14.1, "support": 120,
     "reading": "volume expansion is the single strongest pre-surge tell"}
  ],
  "noise_factors": [
    {"factor": "bb_squeeze", "subfactor": "1c Pattern", "lift": 0.94,
     "reading": "no edge over base rate in this sample"}
  ],
  "contrarian_factors": [
    {"factor": "ma_stack_50_150_200", "subfactor": "1a Trend", "lift": 0.26,
     "reading": "most surges launched from below-trend reversals the rubric filters out"}
  ],
  "coverage_gaps": [
    "Continuation-biased Dim1 + the below-200DMA hard filter structurally miss reversal/oversold-bounce surges, which dominate the ground truth."
  ],
  "proposed_changes": [
    {
      "file": "system_prompts/01_surge_screener_prompt.md",
      "section": "Dimension 1b — Volume Confirmation",
      "rationale": "rvol_ge_2 lift 14.1 (support 120) — by far the strongest validated factor.",
      "suggested_change": "Consider raising 1b volume weight; ensure breakout+volume is not capped low.",
      "user_action_required": true
    }
  ],
  "threshold_stability": "rvol/breakout lift rises with surge size; trend factors stay contrarian across all thresholds.",
  "narrative_summary": "..."
}
```

## Critical Rules

1. **Do not auto-modify prompts or weights.** Output is a report for human review.
2. **Only speak to Dim1/Dim5.** Explicitly say the other four dimensions are out of
   scope for this historical pass.
3. **Respect support gates.** Never label a factor VALIDATED on support < 20.
4. **Name the survivorship and trough/confirmation framing** so the reader weights the
   trend-factor results correctly.
5. **Coverage gaps are findings too.** If the biggest surges launch from setups the
   screener rejects, say so — that is the highest-value insight here.
