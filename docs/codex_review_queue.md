# Codex Review Queue

Items Claude has completed **and self-reviewed**, but that Codex has **not yet passed**.
The per-item **Codex review gate is OFF** as of 2026-06-07 (user decision: don't block on
Codex — Codex quota was also exhausted), so Claude keeps executing + self-reviewing and
**logs every completed item here** instead of waiting. When the gate is re-enabled / quota
recovers, review each item from the top with `/codex:adversarial-review --base <base>`
(focus text suggested per item); mark `✅ codex-passed` or append findings to fix. Items are
NOT considered "放行" (cleared) until Codex passes them; meanwhile work proceeds.

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

### C-9 — wire the knowledge closed-loop into monthly_retrospective (CI)
- **What**: the monthly job scanned only the CURRENT sp1500 (survivorship-biased) and never
  ran knowledge_sync. Added two steps before the commit: (1) best-effort PIT re-validation
  (re-runs the point-in-time sp500_pit chain, all outputs routed into sp500_pit/,
  `continue-on-error` so it can't block the proven sp1500 report); (2) close-the-loop
  (recompute runway/lane verdicts + knowledge_sync `--lift sp500_pit` + knowledge_runway_sync,
  also `continue-on-error`). Commit step now stages `knowledge/`. Cards intentionally sync
  from the survivorship-corrected sp500_pit, not the biased sp1500 pass.
- **Commits**: `561113d` (depends on `981c05d` C-1b for the report --events derivation).
- **Codex history**: not yet reviewed.
- **Claude self-review**: every script flag accepted (`--help`); both run blocks pass
  `bash -n`; YAML parses with both new steps + `continue-on-error=True`; the deterministic
  sync tail (runway checks + both syncs) reproduces the committed sp500_pit artifacts AND
  all factor cards **byte-for-byte** (idempotent, offline). **CI execution itself is NOT
  locally verifiable** — the heavy sp500_pit scan (label→reconstruct→EDGAR→lift) runs only
  in Actions; residual risk = a mid-chain scan failure leaving features/lift inconsistent
  for one month (mitigated by `set -euo pipefail` + continue-on-error + last-committed
  fallback, but not eliminated).
- **Self-review verdict**: PASS for the wiring I can verify; CI run unverified.
- **Suggested review base**: `--base 981c05d` (just the workflow). Focus: is best-effort the
  right failure model, or should a sync failure fail the job (fail-closed)? mid-chain
  partial-artifact inconsistency risk; should validated_on stamp the artifact's own
  generation date instead of today() so monthly re-stamps don't imply fresh re-validation?

### C-8 — strategy-level forward EV + equity + SPY baseline (coiled-base lane)
- **What**: the lane forward harness reported only a TOUCH hit-rate (a Close ever reaching
  +30/40/50% — sold-the-top optimistic, no market baseline). Added the plan's Milestone-C
  EV: realized hold-to-window-end return per tier (mean=EV + median/win-rate/normal-approx
  CI + one-trade equity curve) and ev_excess_vs_spy (SPY date-aligned per entry) so EV is
  edge, not beta. Math refactored to pure functions (evaluate_entry/_mean_block/
  _aggregate_tier) with offline unit tests.
- **Commits**: `237a5f2`.
- **Codex history**: gate OFF — not sent to Codex. Instead ran a 6-lens Claude adversarial
  verification workflow (look-ahead / baseline-survivorship / statistics / EV-equity
  semantics / crash-edge / test-coverage); findings + fixes to be folded in here.
- **Claude self-review**: 6 unit tests pin TOUCH≠horizon, excess-vs-SPY same span, unresolved
  window ⇒ no EV, short-SPY-tail blocks resolution, equity entry-date ordering. End-to-end on
  the real 2026-06-05 scan → 150 entries, 0 resolved (no window elapsed) ⇒ EV None: the
  no-look-ahead gate holds on live data. Calendar-gated (real EV needs MIN_RESOLVED=100
  matured entries). _(adversarial-workflow synthesis pending — update on completion)_
- **Self-review verdict**: PASS on the math I can test offline; honesty of the EV/baseline
  methodology under adversarial review = pending the workflow synthesis.
- **Suggested review base**: `--base 561113d` (just the harness). Focus: any residual
  look-ahead (SPY ffill alignment), is normal-approx EV CI honest on small skewed n, is the
  one-trade-at-a-time equity curve disclosed as not-a-backtest, forward-set survivorship.

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

### RG-4 — Risk Guard V4 (Backtest / Calibration)
- **What**: `scripts/risk_guard_backtest.py` — point-in-time (no look-ahead) recompute of
  PRICE(0-25)+MARKET(0-20) subscores over ~2y daily OHLCV, then forward 5/10/20d max
  drawdown bucketed by score band; false-positive (high score, no drawdown) + missed-
  drawdown (low score, big drop) rates for price+VIX. Writes
  reports/risk_guard/backtest_summary.{json,md} (gitignored). Options/sector NOT
  backtested (no historical IV/RRG); intraday-VWAP price leg dropped.
- **Commits**: `b628820`.
- **Codex history**: not yet reviewed.
- **Claude self-review**: 5-megacap/2y = 1405 obs; top band (30+) forward-20d MDD −7.3%
  vs lowest −6.24% (spread +1.06 → weakly discriminating); FP ~50%, missed 22%, middle
  bands non-monotonic → honest finding that the high-risk threshold is over-sensitive on
  benign mega-caps; needs longer/broader/more-volatile universe to truly validate. Fixed a
  self-caught wording bug (spread interpretation was inverted in the .md). py_compile OK.
- **Self-review verdict**: PASS for the harness; calibration result itself says the rules
  are only weakly predictive on this sample (a finding, not a code defect).
- **Suggested review base**: `--base ed01c4a` (just V4 = b628820). Focus: PIT correctness
  (no look-ahead in score or forward-MDD windows), market-series reindex/ffill alignment,
  band/threshold choices, whether FP/missed definitions are sound, MDD = min future low vs
  close[t] correctness.

### RR-1 — Reversal Radar: reversal_signals.py (leading bottoming detectors)
- **What**: new technical reversal detectors over daily OHLCV (`scripts/reversal_signals.py`) for
  the Reversal Radar (inverse of Risk Guard — see docs plan). macd()/rsi_divergence()/
  capitulation()/volume_dryup_then_expansion()/ma_reclaim()/lower_band_snapback()/all_signals().
  Consistency contract: RSI reuses momentum_options._technical's simple-mean(14)
  (_rsi_series[-1]==tech['rsi14']); MACD reuses retro_reconstruct._ema/_macd_flags (golden_cross
  agrees with validated macd_golden_cross_10d). Pure, never raises.
- **Commits**: `48602cc`.
- **Codex history**: not yet reviewed (gate OFF).
- **Claude self-review**: 13-case deterministic synthetic test (scripts/test_reversal_signals.py)
  ALL PASS — caught & fixed a real bug (`_bullish_divergence` unpacked the two swing-lows
  backwards → inverted divergence direction; now i1=earlier/i2=later). Pins RSI & MACD endpoints
  == the validated engines; capitulation spike/hammer/quiet; dry-up→expansion; ma_reclaim;
  clean-downtrend→no-divergence; short-df→available False. Live smoke on INTC OK.
- **Self-review verdict**: PASS (pending Codex).
- **Suggested review base**: `--base 48602cc~1`. Focus: divergence false-positive rate / swing-low
  pivot choice; capitulation thresholds (rvol 2.0, wick 0.6); RSI/MACD endpoint-equality claim;
  any look-ahead in the rolling windows.

---

## ✅ Codex-passed
(none yet in this queue)
