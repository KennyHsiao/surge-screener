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
- **Commits**: `237a5f2` (build) → `0f7db21` (adversarial-review honesty fixes).
- **Codex history**: gate OFF. (a) Codex STOP-TIME review caught a real bug — "SPY tail guard
  is bypassed in the real resolver" (reindex ffill forces equal lengths → length guard is a
  no-op; ffill silently substitutes a stale baseline). (b) Ran a 6-lens Claude adversarial
  workflow (look-ahead / baseline-survivorship / statistics / EV-equity / crash-edge /
  test-coverage): 40 findings, 7 blocker / 22 should-fix; verdict **PARTIALLY DEFENSIBLE —
  the harness OVER-CLAIMED honesty** (4/6 lenses "over-claims", 2 "look-ahead-present").
- **Fixed in `0f7db21`** (blocker + look-ahead + claim-honesty): SPY reindex no-ffill +
  finite-not-length baseline gate; RESOLVED (stock window + close[0]/close[win] non-NaN) split
  from BASELINE-OK; NaN-at-close[win] no longer resolves; base<=0 / pd.isna(date) / numpy-bool
  guards; **survivorship DISCLOSED** (dropped_count/pct + survivorship block: survivorship_free
  =False, universe_match=False); docstring downgraded from "the honest path"; ev_excess
  relabelled BETA=1; per-tier verdict_by_tier (global = conservative min); ev_caveats
  (gross-of-costs, normal-approx/exploratory CI, correlated readouts, one-trade equity).
  +4 tests (NaN-horizon, missing-baseline-keeps-horizon, empty-spy guard, excess_n). 8 pass.
- **Deferred should-fix (logged, low urgency — EV is None until entries mature)**: (i) full
  point-in-time `sp500_membership.was_member(ticker, entry_date)` gate instead of mere
  disclosure; (ii) realized-beta context + beta-adjusted excess (vs the beta=1 label);
  (iii) swap normal-approx CI → the seeded 1000-sample bootstrap already in retro_factor_lift;
  (iv) net-of-cost EV alongside gross; (v) one real-pandas reindex integration test (unit
  tests use hand-built arrays). Synthesis JSON: `tasks/w8qoet084.output`.
- **Self-review verdict**: PASS on math + the honesty-critical fixes; the deferred items are
  refinements that bite only once EV populates (calendar-gated, MIN_RESOLVED=100).
- **Suggested review base**: `--base 237a5f2~1` (whole harness) or `--base 237a5f2` (just the
  fixes). Focus: is disclosure-not-PIT-gate acceptable for the survivorship blocker, and is
  the resolved/baseline split fully look-ahead-free under real reindex?

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

### RR-2 — Reversal Radar: reversal_radar.py (analyze_reversal leading score)
- **What**: inverse-of-Risk-Guard scorer (`scripts/reversal_radar.py`). Beaten-down precondition
  (MA200 / ≤−20% off 52w high / ≤−15% drawdown → else N/A, distinct from DATA_GAP). Leading score
  0-100, NO COT: 結構22/動能22/期權18(inverse fear-receding)/板塊14(RRG Improving)/內部人12/分析師12.
  INVERSE fail-closed (structure or ≥2 cores missing → DATA_GAP, never a reversal tier; data_confidence
  penalty; except→score 0). COT only in a SEPARATE cot_confirmation field + lead_vs_confirm.front_run.
  exploratory_gate inherits is_recommendations_blocked. Tiers NONE/STABILIZING/TURNING/REVERSAL(探索性).
- **Commits**: `ed962cc`.
- **Codex history**: not yet reviewed (gate OFF).
- **Claude self-review**: INTC→STABILIZING 32, NVDA→N/A(not beaten down), ZZZZINVALID→DATA_GAP/0/conf0
  (inverse fail-closed holds). Asserted COT appears in NO row score (front-run requirement); exploratory
  + gate blocked True; Improving sectors surfaced. py_compile OK. NOT yet stress-tested with a
  beaten-down name that has partial missing sources (conf-drop path) on live data.
- **Self-review verdict**: PASS (pending Codex).
- **Suggested review base**: `--base ed962cc~1`. Focus: inverse fail-closed completeness (any path where
  missing data yields a high reversal?); precondition thresholds; options INVERSE read soundness
  (is "fear receding" honestly distinguished from "still falling"?); weights/caps; COT truly excluded.

### RR-3 — Reversal Radar: reversal_radar_scan.py (discovery scan) + gitignore
- **What**: `scripts/reversal_radar_scan.py` — thin wrapper over analyze_reversal (which fetches
  sector-flow + COT ONCE for the whole list), ranks beaten-down names by leading reversal conviction,
  drops non-candidate tiers, writes reports/reversal_radar/latest.json + scan_<date>.json with versioned
  REVERSAL_LANE_ID. Universe = coiled-base lane candidates (default) or sp1500 (--universe, heavier).
  reports/reversal_radar/ gitignored.
- **Commits**: `c8ec26c`.
- **Codex history**: not yet reviewed (gate OFF).
- **Claude self-review**: --limit 12 over the 150 coiled-base candidates → scanned 12, matched 0
  (quiet-base names legitimately score <25 STABILIZING; not a bug — coiled bases aren't yet "turning").
  latest.json + dated snapshot written; exploratory + lane_id present. NOT yet run over a full/large
  universe (latency) nor verified that matched>0 cases rank sensibly on live data.
- **Self-review verdict**: PASS for plumbing; reversal-rate calibration unverified (needs forward data).
- **Suggested review base**: the RR-3 commit. Focus: lane_id versioning, no per-ticker re-fetch (uses
  analyze_reversal once), candidate-tier filter, sp1500 fallback latency, signal_date for forward dedupe.

### RR-4 — Combined 雷達 page (dual-read 風險＋反轉 in one list)
- **What**: `ui/radar.py` — ONE page (replaced the standalone 風險雷達 nav entry; no separate 反轉雷達
  page) where each ticker shows BOTH a Risk Guard read and a Reversal Radar read in a single dual-read
  table; tabs filter 全部/風險警示/反轉候選/兩者共現. Reuses ui.risk_guard helpers (_collect/_analyze/
  _STATUS_*/_status_chip/_money/_tab_portfolio) + cached reversal _rev(). 單檔明細 = side-by-side
  risk & reversal score-breakdown bars + 共現/搶在COT前/exploratory/COT-lag notes. Live dual-compute
  capped at 40; 反轉候選(掃描) source reads the precomputed scan. app.py nav → "雷達 (風險＋反轉)"
  url_path=radar.
- **Commits**: `e7cade1`.
- **Codex history**: not yet reviewed (gate OFF).
- **Claude self-review**: run-dashboard — 4 tabs render, dual-coloured table (PYPL TURNING etc.),
  detail shows both panels, 組合風控 reused, exploratory gate in 資料來源, no traceback. NOT yet
  verified: the 40-cap UX on a large source, and that 反轉候選(掃描) source + live risk join is sane.
- **Self-review verdict**: PASS for rendering/wiring (pending Codex; UI polish could go via ui-feature).
- **Suggested review base**: `--base e7cade1~1`. Focus: dual-read join correctness, confluence
  definition, that replacing 風險雷達 nav didn't drop Portfolio Guard, cap/source handling.

### RR-6 — reversal_radar_scan --notify (Telegram on TURNING+)
- **What**: `scripts/reversal_radar_scan.py --notify [--notify-min]` pushes TURNING+ reversal
  candidates to Telegram (reuses 05_notify.send_telegram_message). Marks 🔴共現 (Risk Guard also flags
  REDUCE/EXIT) + ✅搶在COT前. Silent-skip if TELEGRAM_* absent; notify glitch never fails the scan.
- **Commits**: `166c612`.
- **Codex history**: not yet reviewed (gate OFF).
- **Claude self-review**: no-creds → skip; stubbed sender → message built correctly (INTC TURNING 52
  · 🔴共現 · ✅搶在COT前; STABILIZING excluded at TURNING floor; confluence via analyze_risk). NOT yet
  fired against a live TURNING+ candidate (coiled-base matched 0) nor a real Telegram endpoint.
- **Self-review verdict**: PASS for message/skip/confluence logic (live + real-endpoint unverified).
- **Suggested review base**: `--base 166c612~1`. Focus: dedupe/spam (a daily scan re-alerts the same
  names — should it track sent state?); confluence correctness; min-tier floor; never-fail-scan guard.

---

## ✅ Codex-passed
(none yet in this queue)
