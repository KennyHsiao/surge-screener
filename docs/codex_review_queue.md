# Codex Review Queue

Items Claude has completed **and self-reviewed**, but that Codex has **not yet passed**
(Codex quota exhausted 2026-06-07). When quota recovers, review each item from the top
with `/codex:adversarial-review --base <base>` (focus text suggested per item); mark
`✅ codex-passed` or append findings to fix. Do NOT consider an item "放行" (cleared)
until Codex passes it.

Convention per item: **What / Commits / Codex history / Claude self-review / Suggested review base**.

---

## ⏳ Pending Codex review

### C-1 — point-in-time validation: honest re-block (delisted gap is the free wall)
- **What**: tried an evidence-based stale-clear to UNBLOCK the PIT validation; Codex showed
  it was not a defensible point-in-time proof, so reverted to an honest BLOCK and routed
  every gate consumer through the canonical fail-closed `is_recommendations_blocked`.
- **Commits**: `3cba5dc` (flawed unblock — superseded) → `1a0ca5e` (honest re-block:
  delisted_data_gap hard-blocks, audit evidence-only, fail-closed canonical gate, report
  branch) → `7b273ca` (route ALL consumers through canonical gate: lane source_blocked,
  knowledge_sync, retro_report output dir, UI _block_reasons; + test_retro_gate.py).
- **Codex history**: round 1 (no-ship — unblock not defensible) → addressed in `1a0ca5e`;
  round 2 (4 fail-open consumers + report path + UI reasons) → addressed in `7b273ca`;
  round 3 started but was **cut off by quota before a verdict** → PENDING.
- **Claude self-review**: grepped every `recommendations_blocked` read. All gate consumers
  now canonical: `retro_modules` stores `is_recommendations_blocked(lp)`; `retro_report`
  uses `_is_blocked`; UI uses the fixed `_gate_blocked`; lane + knowledge_sync use the
  predicate. `_exploratory_ok`'s stored-flag check is a conservative EXTRA gate (safe).
  Verified: PIT `recommendations_blocked=True`, lane `actionable=False`, forged
  unblocked-but-delisted artifact → blocked, all `test_retro_gate.py` pass. **No remaining
  fail-open found.** Honest conclusion stands: free data cannot make PIT actionable
  (delisted-survivor gap needs paid data).
- **Self-review verdict**: PASS (pending Codex confirmation).
- **Suggested review base**: `--base 1a0ca5e` (the consumer fixes), or `--base daa8586`
  (the whole C-1 arc). Focus: any remaining stored-flag fail-open? PIT events/features/
  factor_lift/latest/cards/lane self-consistent + consistently blocked?

### C-1b — report --events derived from --lift dataset dir (acts on Codex r3 hint)
- **What**: Codex round-3 (cut off by quota before a final verdict) left an intermediate
  hint — *"a likely path-regression candidate: retro_re…"*. Investigated: `retro_report.py`
  defaulted `--events` to the ROOT `surge_events.json` independently of `--lift`, so a caller
  passing only `--lift sp500_pit/…` would stamp that dataset's `latest.json` with the ROOT
  universe/event_count. The shipped PIT artifacts were clean (both args were passed), but #9 is
  about to codify these commands → hardened: `--events` derives from the `--lift` dataset dir,
  plus a fail-closed guard that refuses on `lift.coverage.universe != events.universe`.
- **Commits**: `981c05d`.
- **Codex history**: surfaced as the round-3 intermediate hint; not yet re-reviewed.
- **Claude self-review**: verified the generated `sp500_pit/latest.json` is self-consistent
  (universe=sp500_pit, event_count=361, blocked) and that a report-run with ONLY `--lift` now
  derives the right events; default (root) path byte-identical (no churn). py_compile OK.
- **Self-review verdict**: PASS (pending Codex confirmation).
- **Suggested review base**: `--base 7b273ca` (just this fix). Focus: is the universe guard
  correct for all datasets (root factor_lift lacks coverage.universe → guard no-ops safely)?

### RG-1 — Risk Guard V1 (風險雷達 MVP): final leg-completeness consistency
- **What**: V1 rule-based risk dashboard (`scripts/risk_guard.py`, `ui/risk_guard.py`,
  `app.py` nav) per `docs/risk_guard_plan.md` §4-5/§9. Codex reviewed 3 rounds; only the
  last item (#6 position leg-completeness) awaits a final verdict.
- **Commits**: `ea90b20` (V1) → `0cd53f4` (fail-closed: DATA_GAP not NORMAL/0) →
  `ebe2269` (review round-1 fixes) → `f2d9da7` (round-2: non-diluting market %, headline,
  leg) → `799da2f` (round-3: leg-completeness flag⇔skipped).
- **Codex history**: round 1 = FAIL (3 blockers + 8 should-fix + 1 nit) → all fixed in
  `ebe2269`. round 2 = #2/#3 **ACCEPTABLE** (kept real market_status, added non-diluting
  denominator; not DATA_GAP for missing background COT — would under-alarm), headline
  **RESOLVED**; #6 left. round 3 = sent for #6 but **cut off by quota before verdict** → PENDING.
- **Claude self-review**: #6 rebuilt so completeness = fields scoring USES (return_pct for
  loss, OPT expiry→DTE); single pass builds `rets`/`opt_dtes` and a `skipped` flag →
  `position_data` gap. flag⇔skipped is exact; no valid loss/DTE signal dropped (dropping an
  unscored unrealized_pnl/strike would under-count = fail-closed regression). Synthetic test:
  NVDA (−30% stock leg w/o unrealized_pnl + 6-DTE opt) → score 10, no false gap, loss+DTE
  counted; AAPL leg w/o return_pct & expiry → skipped + gap. fail-closed intact (bogus
  ticker → DATA_GAP 15, never NORMAL/0). py_compile + dashboard 4 tabs render, no traceback.
- **Self-review verdict**: PASS (pending Codex round-3 confirmation).
- **Suggested review base**: `--base 0cd53f4~1` (whole V1 arc) or `--base f2d9da7`
  (just the #6 fix). Focus: #6 flag⇔skipped consistency + no fail-closed regression;
  re-confirm rounds 1-2 items unbroken.

### RG-2 — Risk Guard V2 (Portfolio Guard 持倉級風控)
- **What**: portfolio-level aggregation over IBKR reconciliation (per plan §V2): total
  unrealized P&L, options expiring ≤7/≤14/≤30d, by-underlying, by-sector concentration,
  held-not-tracked, high-loss-not-reduced + a 組合風控 UI section.
- **Commits**: `3fa559d`.
- **Codex history**: not yet reviewed.
- **Claude self-review**: `portfolio_summary(rows, recon)` reuses per-ticker rows (status+sector,
  no extra fetch). Synthetic 3-position book (NVDA −30% stock + 5-DTE option, AMD +, SOXX
  held_not_in_ledger) → total −$1450, 科技 concentration, NVDA worst-first & ≤7d, SOXX
  untracked, all 4 warning types fire; no reconciliation.json → {available:False} graceful.
  py_compile; dashboard 5 tabs + populated 組合風控 (temp synthetic recon) render, no traceback.
  Live concentration uses each ticker's REAL sector mapping (splits tech → ~47%, more correct
  than the isolated test's 87%).
- **Self-review verdict**: PASS (pending Codex confirmation).
- **Suggested review base**: `--base 799da2f` (V2 only = 3fa559d). Focus: aggregation
  correctness vs plan §V2, market-value-weighted concentration + 40% threshold, fail-closed
  when reconciliation.json absent, no double-count, leg market-value (option ×100) correctness.

### RG-3 — Risk Guard V3 (Options Risk Pro): IV term structure + put skew
- **What**: `scripts/options_term.py term_structure(ticker)` — near vs ~1-month ATM IV →
  near-term IV backwardation; OTM-put-vs-ATM put skew on the ~1-month tenor; cached 15m,
  never raises; + `OptionsRiskProvider` paid-feed stub. `options_component` scores
  backwardation (+5) and steep skew ≥10 vol pts (+5) and classifies `options_state`
  (OPTIONS_CALM / HEDGING_DEMAND / STRESS / DATA_GAP).
- **Commits**: `ed01c4a`.
- **Codex history**: not yet reviewed.
- **Claude self-review**: caught & fixed a real defect during self-review — skew was first
  measured on the 2-DTE front chain where OTM-put IV is artifactually inflated (NVDA showed
  a misleading +24pt skew); moved skew to the ~1-month tenor (NVDA → +1.6pt, realistic) and
  set a conservative ≥10pt absolute threshold (no per-name baseline on free data). NVDA:
  near 0.36 (2d) < far 0.41 (34d) = contango → no false backwardation; options_state CALM;
  skew does NOT fire. py_compile OK. options cap still 20.
- **Self-review verdict**: PASS (pending Codex confirmation).
- **Suggested review base**: `--base 3fa559d` (V3 only = ed01c4a). Focus: term-structure
  correctness (ATM-IV picking, backwardation 1.05× threshold), skew tenor/threshold
  defensibility, multi-expiry fetch latency/caching, fail-closed when chains unavailable,
  options_state thresholds vs cap.

---

## ✅ Codex-passed
(none yet in this queue)
