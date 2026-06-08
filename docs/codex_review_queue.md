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
- **Commits**: `981c05d` (build) → `c6902bd` (adversarial-review fix).
- **Codex history**: gate OFF. A 4-reviewer Claude adversarial workflow (`tasks/w5ovqb8ck`)
  caught a real defect: the guard `if lift_universe and events_universe and lift!=events` was
  **FAIL-OPEN** — it short-circuited on a falsy side, so a legacy/forged lift missing
  coverage.universe paired with a real dataset's events slipped past. (Both real artifacts DO
  carry universe, so the live exposure was narrow — the reviewer down-graded it from blocker.)
- **Fixed in `c6902bd`**: extracted the pure `_universe_mismatch()` that fails CLOSED on ANY
  asymmetry (incl. one side missing; legacy↔legacy still passes); `test_retro_report_guard.py`
  pins it, including the asymmetric-missing escape the original guard allowed.
- **Self-review verdict**: PASS — fail-closed + tested.
- **Suggested review base**: `--base 981c05d~1` (whole C-1b) or `--base c6902bd` (the fix).

### C-9 — wire the knowledge closed-loop into monthly_retrospective (CI)
- **What**: the monthly job scanned only the CURRENT sp1500 (survivorship-biased) and never
  ran knowledge_sync. Added two steps before the commit: (1) best-effort PIT re-validation
  (re-runs the point-in-time sp500_pit chain, all outputs routed into sp500_pit/,
  `continue-on-error` so it can't block the proven sp1500 report); (2) close-the-loop
  (recompute runway/lane verdicts + knowledge_sync `--lift sp500_pit` + knowledge_runway_sync,
  also `continue-on-error`). Commit step now stages `knowledge/`. Cards intentionally sync
  from the survivorship-corrected sp500_pit, not the biased sp1500 pass.
- **Commits**: `561113d` (build) → `c6902bd` (adversarial-review fixes). Depends on C-1b.
- **Codex history**: gate OFF. The same 4-reviewer workflow (`tasks/w5ovqb8ck`) flagged two
  real issues (it down-graded both from blocker after verifying real artifacts carry consistent
  provenance): (1) `knowledge_sync` stamped `validated_on = date.today()`, so a re-sync from a
  stale/last-committed factor_lift (skipped/failed CI re-validation) made cards read as freshly
  validated; (2) no source-chain validation — a partial Leg-1 crash (fresh events + stale lift)
  could poison the synced cards.
- **Fixed in `c6902bd`**: `validated_on` now = the artifact's OWN `generated_at` date (honesty
  over freshness-theatre); `knowledge_sync` SOURCE-CHAIN validates (SystemExit if
  `factor_lift.source.events_generated_at != sibling surge_events.generated_at`); the CI sync
  leg is gated `if: steps.pit_revalidate.outcome == 'success'` (landed in HEAD via the
  concurrent RR-8 commit) so it only runs on a complete re-validation; misleading "falls back"
  comment corrected. Verified: tampered-events → exit 1; the 18 cards re-stamped 06-07→06-06.
- **Self-review verdict**: PASS on the honesty + source-chain fixes; CI execution still only
  runs in Actions (the `outcome`-gate + the in-script guard are the belt-and-suspenders).
- **Suggested review base**: `--base 561113d~1` (whole C-9) or `--base c6902bd` (the fixes).

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
- **Cloud ultrareview → `cfe76e6`** (3 nits): SPY-fetch-None no longer wipes every entry +
  mislabels `dropped_pct=1.0` as delisting (passes an empty baseline); entry older than the 2y
  fetch window dropped instead of measured against a wrong base; touch uses `np.nanmax` so a
  mid-window NaN can't mask an earlier real +pct touch. +1 test.

### C-5 — symmetric liquidity/microcap filter for factor-lift (Phase 1c)
- **What**: optional 20-session avg $-volume floor to strip penny-stock fake edges, applied
  SYMMETRICALLY to surge events AND controls (an asymmetric filter would itself bias the
  lift). Pure `avg_dollar_vol_20d(close,volume,k)` in retro_reconstruct (point-in-time, both
  arms' single source of truth); both arms attach the field at their confirmation day; one
  pure `_filter_by_liquidity` predicate + `--min-dollar-vol` (default 0=OFF) in
  retro_factor_lift; dropped counts in `coverage.liquidity_filter`; a guard REFUSES a >0
  floor on field-less (pre-Phase-1c) records (network + --from-cache paths) instead of
  dropping everything.
- **Commits**: `a529238` (build) → `5d6c7b7` (adversarial-review fixes).
- **Codex history**: gate OFF. 5-lens Claude adversarial workflow (`tasks/wsua5krie.output`):
  25 findings, verdict **NOT symmetric as first written** (3/5 lenses "asymmetric-bias";
  look-ahead lens = "symmetric-and-sound"). The look-ahead/point-in-time math was clean; the
  ASYMMETRY was in the control-exclusion windows.
- **Fixed in `5d6c7b7`**: (BLOCKER) surge windows were built from UNFILTERED events while
  positives were filtered → controls over-excluded by dropped surges' windows → lift biased
  up. Now `_build_surge_windows()` rebuilds windows from ONLY surviving (filtered) surges.
  (should-fix) `--from-cache` + `--min-dollar-vol` REFUSED (cache pool was selected against
  unfiltered windows, can't rebuild). (should-fix) control-pool sizing uses the filtered
  (scored) count — documented + `surge_count_prefilter` recorded. +2 tests pin the windows fix.
- **Deferred nits (logged)**: scanned_tickers fallback to filtered tickers when events_payload
  lacks scanned_tickers (latent — retro_surge_label always populates it); pre-existing
  Timestamp-hash/pos lookup (not introduced by #5).
- **Claude self-review**: 12 offline unit tests pass (look-ahead boundary, window/NaN,
  symmetric same-verdict-both-arms, None/bool fail floor, windows-off-uses-all,
  windows-on-excludes-dropped). Default-off `--from-cache` on real sp500_pit → ALL-table
  verdicts+lift BYTE-IDENTICAL to committed (no regression from the refactor); both refusal
  paths exit 1. Committed artifacts untouched.
- **Self-review verdict**: PASS — symmetry now enforced in code + pinned by tests. The filter's
  EFFECT (does rvol_ge_2 survive a $-vol floor?) still needs a full re-run with the field
  present (CI / on demand).
- **Suggested review base**: `--base a529238~1` (whole #5) or `--base a529238` (just the
  symmetry fixes). Focus: is `_build_surge_windows(surviving)` the complete asymmetry fix, or
  do control-pool SIZING / per-ticker `per_ticker` quotas still differ between arms post-filter?
- **Cloud ultrareview → `cfe76e6`** (nit): found a SECOND asymmetry — filter-ON derived
  `surviving_surges` only from reconstructed+liquid features, silently dropping the windows of
  surges retro_reconstruct couldn't score (which filter-OFF keeps). Now `surviving_surges =
  liquid ∪ unreconstructed`, so the two modes differ ONLY on the liquidity axis. Default-off
  still byte-identical.

### C-10 — pipeline-wide MANDATORY fail-closed provenance + blocked-machine-readable cards
- **What**: the user's requested **Codex adversarial review actually ran** (Codex was available
  — the earlier "no credits" was my mis-read of a `--effort minimal`+tools 400 error) on the
  whole retro/forward/knowledge pipeline (`--base 981c05d~1`). Verdict **needs-attention /
  No-ship**: provenance was not mandatory + the runway side-channel had no gate. A parallel
  6-lens Claude integration review (`tasks/wbkyv0o6b`) corroborated (stats lens = "consistent";
  provenance/gate/filter/vault = seam-gap/fail-open). 5 Codex + ~9 integration blockers,
  deduped to one coherent hardening.
- **Commits**: `7b7582d` (code) → `f17c980` (card re-stamp blocked-aware + regenerated
  runway_neutral with provenance).
- **Fixed**: shared `assert_same_run`/`events_fingerprint`; retro_factor_lift warn→HARD-FAIL +
  --from-cache control-source check + control_features.source records min_dollar_vol;
  retro_report requires `lift.source.events_generated_at == events.generated_at` (stale
  same-universe lift no longer mislabels latest.json); knowledge_sync fail-closed provenance +
  no today() fallback + **blocked ⇒ status: exploratory** (not the verdict); knowledge_runway_sync
  gains BOTH provenance + canonical gate (blocked ⇒ `runway_verdict: exploratory` + `runway_blocked`
  + 🔒, never machine-readable "genuine"); runway checks stamp source + validate same-run pools;
  retro_modules full-chain provenance + applies the liquidity floor to surgers symmetrically;
  workflow commit no longer stages partial PIT output (gated on pit_revalidate success).
- **Claude self-review**: +`test_provenance.py` (5) + all existing suites green; tampered
  control/lift/runway provenance each hard-fail (exit 1); blocked → status+runway_verdict
  exploratory verified on real + synthetic fixtures; --from-cache default-off verdicts
  byte-identical; retro_modules runs on consistent artifacts. Stats unchanged ("consistent").
- **RE-REVIEW round 2** (both ran on the hardened code). **Codex: needs-attention / No-ship
  AGAIN — the first pass was INCOMPLETE** (3 findings): (1) the knowledge-loop step was also
  continue-on-error so a runway-sync failure after knowledge_sync wrote cards still committed
  partial state; (2) blocked cards set status:exploratory but STILL wrote verdict:VALIDATED +
  validated_on; (3) module_lift had no source fingerprint. **Claude (`tasks/w9jkr9ayx`): 3/4
  lenses CLEARED, no regressions**; completeness still-open (lane_runway stale-no-source,
  oversold scan no cross-provenance, missing E2E test).
- **Fixed round 2 → `3246ee5` + `b9t5wj0gp`(lane regen)**: workflow commit now gated on BOTH
  pit_revalidate AND knowledge_loop success (all-or-nothing); knowledge_sync blocked run
  neutralises EVERY machine-readable field (verdict/verdict_mt → EXPLORATORY, validated_on
  blank, +blocked:true, raw reading kept as verdict_raw/exploratory_on); module_lift.json
  stamped with source.events_generated_at; oversold_reversal_scan cross-checks
  lane_runway.source == factor_lift.source (mismatch ⇒ source_blocked); lane_runway.json
  regenerated with source; +`test_integration_provenance.py` (full-chain + any-stale-link sweep).
- **RE-REVIEW round 3** (Codex). Verdict: all-or-nothing gate **ACCEPTED**; No-ship on 2 new
  findings → fixed in `f0b068f`: (1) the module_lift `source` fix was generator-only — the
  committed `sp500_pit/module_lift.json` was never regenerated, so it shipped without `source`;
  regenerated it + added an ARTIFACT-LEVEL test that loads the REAL committed chain (the
  synthetic test couldn't catch a shipped-but-un-regenerated file); (2) regression from #8 —
  `ui/oversold_reversal_lane.py` still read the removed `total_resolved` → now reads
  `min_resolved_across_tiers`. Trend converging: Codex findings 5 → 3 → 2, severity dropping.
- **Self-review verdict round 3**: PASS — both fixed + verified (committed-chain test green).
- **RE-REVIEW round 4** (Codex). Verdict: the named sp500_pit chain ACCEPTED as
  fingerprint-consistent; No-ship on 2 → fixed in `77bcf1d`: (1) latest.json (the UI bundle)
  was unfingerprinted — now stamped with source.events_generated_at + factor_lift_generated_at,
  committed sp500_pit/root latest.json regenerated, latest.json added to the committed-chain
  test; (2) test_retro_modules.py was stale + FAILING (18/28) — asserted delisted_data_gap=True
  unblocks (contradicts C-1), fixtures lacked source + C-1 coverage fields. Repaired to 28/28
  (C-1 invariant fixed, fixtures updated, retro_modules input provenance reverted to native
  GRACEFUL block). Trend: 5 → 3 → 2 → 2.
- **Self-review verdict round 4**: PASS — both fixed; all 7 retro suites green (modules 28/28,
  committed-chain incl. latest.json).
- **RE-REVIEW round 5** (Codex). No-ship on 2 → fixed in `9f95ab7`: (1) the committed-chain test
  required the GITIGNORED control_features.json (27MB, not in HEAD) → would fail a clean
  checkout; now covers only TRACKED artifacts (control_features validated at runtime); (2)
  --from-cache now fails closed unless control_features.source.min_dollar_vol matches the current
  floor (was: a filtered cache could be replayed against unfiltered surgers) + regression test.
  Findings trend: 5 → 3 → 2 → 2 → 2 (increasingly niche: artifact-regen, test-rot, gitignore,
  cache edge — the core provenance has held since round 2).
- **Self-review verdict round 5**: PASS — both fixed; all 7 suites green; legit --from-cache
  unaffected.
- **RE-REVIEW round 6** (Codex). No-ship on 2 real gaps → fixed in `22a746f`: (1) the committed
  ROOT (sp1500) module_lift.json was unprovenanced (r3 regenerated only sp500_pit) + the
  committed-chain test only checked sp500_pit → now regenerated root module_lift + the test
  validates EVERY committed dataset (root + sp500_pit); (2) --from-cache validated only
  events_generated_at, not features_generated_at — a rebuilt-features cache could launder stale
  control flags; now guarded + regression test. Findings: 5 → 3 → 2 → 2 → 2 → 2.
- **Self-review verdict round 6**: PASS — both fixed; all 7 suites green; legit cache unaffected.
- **RE-REVIEW round 7** (Codex). No-ship on 2 (the "same-events, stale derived artifact" class)
  → fixed in `25e9147`: (1) --from-cache fell back to the ALL control baseline for any threshold
  missing from the cache → now fails closed unless the cache covers every current threshold; (2)
  the committed-chain test only checked events_generated_at → added derived-from adjacency links
  (factor_lift/module_lift.features_generated_at == surge_features; latest.factor_lift_generated_at
  == factor_lift). Findings: 5 → 3 → 2 → 2 → 2 → 2 → 2.
- **Self-review verdict round 7**: PASS — both fixed; all 7 suites green; legit cache unaffected.
- **RE-REVIEW round 8** (Codex). No-ship on 3 — one a REAL bug, not niche → fixed COMPREHENSIVELY
  in `7f9a86c`: (1) retro_edgar_backfill mutated surge_features in place but bumped only
  generated_at_edgar → --from-cache silently missed EDGAR re-runs (Dim2/Dim4 corruption); now
  bumps generated_at; (2) runway/lane provenance was events-only → now stamp + validate
  features_generated_at end-to-end (generators + _load_pool + knowledge_runway_sync + oversold
  scan + committed-chain test); (3) blocked cards still wrote raw lift/precision/q_value/
  runway_neutral_lift → now BLANKED, raw kept under *_exploratory keys. Findings: 5,3,2,2,2,2,2,3.
- **Self-review verdict round 8**: PASS — all 3 fixed + verified (7 suites green incl. runway
  adjacency; 18 blocked cards expose no actionable numeric field; runway artifacts carry both
  fingerprints). Closed the WHOLE features-adjacency + blocked-numeric pattern to converge.
- **RE-REVIEW round 9** (after credit refill). No-ship on 2 → fixed in `c83df91`: round 8's
  "comprehensive" features-adjacency pass MISSED the two main consumers — retro_report +
  knowledge_sync were still events-only, so a stale factor_lift (rebuilt features via EDGAR,
  same events) passed. Added shared `assert_features_fresh`; both now require
  factor_lift.source.features_generated_at == sibling surge_features.generated_at, + stale-features
  regression tests. NOW every consumer validates events+features. Findings: 5,3,2,2,2,2,2,3,2.
- **Self-review verdict round 9**: PASS — both fixed; all 9 suites green; real sp500_pit chain
  passes (no false rejection).
- **RE-REVIEW round 10** (Codex). No-ship on 2 → fixed in `9509040`: (1) knowledge_runway_sync +
  oversold_reversal_scan only CROSS-MATCHED runway↔factor_lift tokens (two stale downstream
  artifacts agree) → now ANCHOR to the current surge_features; (2) committed PIT/root
  surge_features carried a PRE-EDGAR generated_at (token didn't move with the EDGAR mutation) →
  surgically corrected to generated_at_edgar + re-propagated features tokens (no data change), +
  committed-chain test asserts edgar_backfilled⇒generated_at>=generated_at_edgar. Findings:
  5,3,2,2,2,2,2,3,2,2.
- **Self-review verdict round 10**: PASS — both fixed; all 7 suites green; real bumped chain
  passes every consumer (no false rejection).
- **RE-REVIEW round 11** (Codex). No-ship on 2 → fixed in `b8da9d5`: (1) the runway loader had
  the #5 liquidity asymmetry (unfiltered surgers vs filtered controls when min_dollar_vol>0) →
  now filters the surger arm symmetrically + stamps the floor; (2) oversold_reversal_scan
  anchored to surge_features but not surge_events → now anchors to BOTH. +2 regression tests.
  Findings: 5,3,2,2,2,2,2,3,2,2,2.
- **Self-review verdict round 11**: PASS — both fixed; all 7 suites green incl. the 2 new
  regressions; real chain passes (no false rejection).
- **RE-REVIEW round 12** (Codex). No-ship on 1 (down from 2) → fixed in `9413b33`: the runway
  consumers ignored the liquidity-FLOOR provenance (floor doesn't change events/features, so a
  floor-0 runway could pass beside a floor>0 gate) → oversold + knowledge_runway_sync now require
  runway/lane source.min_dollar_vol == factor_lift's floor; committed-chain test asserts it;
  committed runway artifacts stamped. Findings: 5,3,2,2,2,2,2,3,2,2,2,1 (converging).
- **Self-review verdict round 12**: PASS — fixed; all 7 suites green; real chain passes.
- **RE-REVIEW round 13** (Codex). No-ship on 1 → fixed in `c1aa2c4`: the floor-adjacency
  (r12) was missing from retro_modules — it applied the control floor but didn't verify it
  matched the factor_lift floor → now requires coverage.liquidity_filter.min_dollar_vol ==
  control_features.source.min_dollar_vol for lift_ok, + committed-chain assertion + regression
  (29/29). Liquidity-floor now in the provenance contract for ALL consumers. Findings:
  5,3,2,2,2,2,2,3,2,2,2,1,1.
- **Self-review verdict round 13**: PASS — fixed; all 7 suites green; real chain consistent.
- **RE-REVIEW round 14** (Codex). NO-SHIP on 1 [high]: "Missing factor_lift liquidity floor is
  accepted as floor 0" — the floor checks defaulted a MISSING `coverage.liquidity_filter.min_dollar_vol`
  to 0 (fail-OPEN), and the committed factor_lift lacked the field entirely, so a floor-less/legacy
  lift passed as "unfiltered" and could pair with a filtered cohort. Fixed in `9a63f52`:
  (1) new `retro_factor_lift.strict_floor(artifact,*keys)` → float only if PRESENT + numeric
  (rejects bool/None/missing), else None — no default-to-zero; (2) wired into EVERY consumer
  (retro_modules `lift_ok`, knowledge_runway_sync runway↔lift, oversold_reversal_scan
  `source_provenance_ok`, committed-chain integration test require factor_lift floor present +
  each dependent `source.min_dollar_vol` == it); (3) backfilled
  `coverage.liquidity_filter{min_dollar_vol:0.0}` onto the committed factor_lift (root + sp500_pit)
  so the contract is satisfiable; (4) regression tests for the exact fail-open (module blocks when
  factor_lift floor absent + when control floor absent). Suites green: retro_modules **31/31**,
  provenance, liquidity, integration-provenance all pass; real sp500_pit chain floors all match
  (no false reject).
- **Self-review verdict round 14**: PASS — fail-open closed; strict presence required everywhere.
- **RE-REVIEW round 15** (Codex stop-time). NO-SHIP on 1: "retro_report still accepts floor-less
  factor_lift artifacts" — the SAME recurring tail (one more consumer missed the latest refinement).
  Instead of patching just retro_report, ran a **comprehensive multi-agent audit** (Claude Workflow
  `tasks/waett3626`, 25 agents) of **ALL 15 retro/knowledge consumers** against the full contract
  (same-run / features-fresh / strict-floor / blocked-gate), adversarially verifying each gap with a
  reproduced exploit. **8 confirmed gaps across 4 files** → all fixed in `93367c6`:
  - `retro_report` [high]: require `coverage.liquidity_filter.min_dollar_vol` present before
    republishing latest.json (floor-less = unknown cohort → refuse).
  - `retro_modules` [high]: same-run gap — anchored only on surge_features' SELF-REPORTED events
    fingerprint, never the authoritative `surge_events.json`. Added `--events`, folded the real
    `generated_at` into `provenance_ok`; wired `--events` into the PIT CI leg.
  - `knowledge_sync` [med]: require the floor present before stamping cards.
  - `live_factors` [high+med]: only checked the blocked bit → added `lift_provenance_ok`
    (same-run + features-fresh + strict-floor, graceful BLOCK) so a stale/cross-run/floor-less lift
    can't publish an unblocked 個股體檢 band.
  - `ui/retro_analysis` [high×3]: page gated only on stored bits → page-level re-anchor force-blocks
    any lift/module/latest not descending from the page's events+features or lacking a floor.
  - Backfilled `coverage.liquidity_filter` onto committed latest.json (root + PIT).
  Coverage matrix (post-fix): all 5 gating consumers + already-hardened
  oversold_reversal_scan / knowledge_runway_sync now `applies` on every facet; generators
  (knowledge_seed, retro_edgar_backfill, retro_forward_lift, retro_reconstruct,
  retro_runway_neutral_check) + pure displays (retro_confound_check, oversold_reversal_lane,
  stock_checkup) correctly `n/a`. Suites: retro_modules **34/34**, live_factors **7/7**,
  integration/provenance/liquidity green; real root+PIT chains verified fresh (no false reject).
- **WHY THIS ARC KEPT NOT PASSING (root cause, rounds 9–15):** the *contract* converged at round 2
  and was never re-broken. What did NOT converge was the **rollout** — each round a new refinement
  (features-adjacency r9, EDGAR token r10, floor adjacency r12/13, strict-floor r14) was applied to
  only the one or two consumers in front of me, so the next round Codex always found consumer N+1
  that hadn't received it (r9 retro_report+knowledge_sync, r13 retro_modules, r14 missing-floor, r15
  retro_report again + live_factors + ui). That is a reactive **whack-a-mole over consumers**, which
  structurally guarantees ~1 finding/round (the "tail of 1" in the Findings trend). Round 15 broke it
  by **enumerating every consumer at once** (the audit) and applying the *complete* contract to all
  of them in a single commit, instead of one consumer per round.
- **Self-review verdict round 15**: PASS — whole consumer surface swept; tail closed in one round.
  **Round-16 Codex confirmation running** (`tasks/blonlbi3a`, base `93367c6~1`). Mark C-10 fully
  PASS once r16 returns SHIP.
- **Findings trend (blocking/round):** 5,3,2,2,2,2,2,3,2,2,2,1,1,1,(r15 audit closed the tail).
- **Suggested review base**: `--base 981c05d~1` (full scope) or `93367c6~1` (round-15 sweep).

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

### RR-7 — Reversal Radar: beaten-down pre-screen universe (fixes matched=0)
- **What**: `scripts/reversal_radar_scan.py --universe beaten_down` — a cheap df-ONLY pre-screen
  (`_prescreen`) of sp1500 (1 fetch/name) keeping BEATEN-DOWN names (below MA200 or ≥20% off 52w high)
  with ≥1 early reversal technical sign; survivors get full reversal scoring. --prescreen-cap bounds it.
  The coiled-base universe surfaced 0 reversal candidates (quiet bases score ~0); this is the universe
  that actually finds 'down-then-turning' names.
- **Commits**: `146d020`.
- **Codex history**: not yet reviewed (gate OFF).
- **Claude self-review**: curated 12 beaten-down → pre-screen kept 3 (INTC/PYPL/DIS), dropped 9
  (discriminating). Full scoring → PYPL TURNING 50 (RSI+MACD bull divergence, sector Improving, insider),
  INTC/DIS STABILIZING → pipeline surfaces candidates + PYPL would fire --notify. Full sp1500 pre-screen
  is a slow cron — verified on a bounded sample, NOT run to completion; pre-screen thresholds (20%-off-high,
  RSI 30-45) not calibrated against forward outcomes.
- **Self-review verdict**: PASS for the pipeline; universe-threshold calibration unverified (RR-FWD).
- **Suggested review base**: `--base 146d020~1`. Focus: pre-screen criteria (too loose/tight? is "early
  sign" set defensible?), latency/cap, that beaten_down survivors are genuinely 'down-then-turning', and
  whether the pre-screen's df-only signals double-count with the full scorer.

### RR-FWD — Reversal Radar: reversal_radar_forward.py (forward validation)
- **What**: `scripts/reversal_radar_forward.py` — forward validator for the reversal lane
  (REVERSAL_LANE_ID): accumulate dated scans, enter at signal close, per-tier TOUCH hit-rate (Wilson) +
  strategy EV (hold-to-window-end, no look-ahead) + SPY β=1 baseline + survivorship/EV caveats.
  Bounce-sized tiers (+10/20d, +15/40d, +20/60d). Cloned from oversold_reversal_forward.py (reuses its
  pure _mean_block + rfl._wilson). PROVISIONAL until MIN_RESOLVED=100/tier. The ONLY thing that lifts the
  EXPLORATORY label off the reversal factors.
- **Commits**: `ee43035`.
- **Codex history**: not yet reviewed (gate OFF).
- **Claude self-review**: empty state → 0 entries / PROVISIONAL (no crash); evaluate_entry synthetic +12%
  bounce → resolved+hit horizon 0.12; short window → unresolved (no look-ahead). Maturity is calendar-gated.
  Cloned EV/baseline math NOT independently re-tested (relies on the lane tests + C-8 review) → keep-in-sync risk.
- **Self-review verdict**: PASS for plumbing/empty/synthetic; maturity + sync-with-lane unverified.
- **Suggested review base**: `--base ee43035~1`. Focus: reversal tier choice (+10/15/20%); did the clone
  faithfully carry the post-C-8 honesty fixes (no-ffill SPY, NaN-at-win gate, survivorship); share vs clone?

### RR-8 — Reversal Radar: daily CI/cron wiring + un-gitignore scans
- **What**: CI "Stage 6.8 — Reversal Radar" (surge_screener.yml) runs reversal_radar_scan.py --universe
  beaten_down --notify + reversal_radar_forward.py (Telegram secrets, continue-on-error). **Un-gitignored
  reports/reversal_radar/** so dated scans persist for forward accumulation (RR-3 bug: ignoring → never
  accumulates). Makefile `reversal-scan` + `reversal-test`.
- **Commits**: `81ee74b`.
- **Codex history**: not yet reviewed (gate OFF).
- **Claude self-review**: workflow YAML parses; Makefile targets listed; local matched=0 artifacts removed.
  CI execution + real Telegram + multi-day accumulation only verifiable in Actions, NOT locally.
- **Self-review verdict**: PASS for YAML/Makefile/gitignore; CI run + Telegram + accumulation unverified.
- **Suggested review base**: `--base 81ee74b~1`. Focus: CI runtime of the beaten_down sp1500 scan (vs
  --prescreen-cap); separate job (like options_flow) vs inline; repo bloat from committing reversal reports.

### RR-9 — CI push-permission fix (GITHUB_TOKEN contents:write) so the bot can commit reports
- **What**: the reversal_radar job (and every commit-back job) failed `Commit … exit 128` —
  `Permission to KennyHsiao/surge-screener.git denied to github-actions[bot]`. Root cause: repo
  `default_workflow_permissions=read`. Fix: a minimal **top-level `permissions: contents: write`** in
  surge_screener.yml (only contents, nothing else) — the documented per-workflow override of the read-only
  default, chosen over flipping the repo-wide setting (which the safety classifier blocked as too broad).
  Also set the `TELEGRAM_BOT_TOKEN` Actions secret (chat-id still pending). Unblocks no-computer alerts.
  **Plus (`b25c020`)**: gave the reversal radar its OWN cron (`45 22 * * 1-5`) — it was previously only
  reachable inline in surge_scan Stage 6.8 (which aborts when Stage 2 lacks ANTHROPIC_API_KEY) or via manual
  dispatch, so NO scheduled no-computer path existed. Standalone job is now first-class scheduled (pure-rules,
  no API key); inline Stage 6.8 dropped `--notify` (data-only) so the two never double-alert.
- **Commits**: `514d212`, `b25c020` (own-cron decouple).
- **Codex history**: not yet reviewed (gate OFF).
- **Claude self-review**: pre-fix run 27112519720 scan PASSED (scanned=140 matched=117) and ONLY the commit
  step 403'd → isolates permission as the sole remaining failure. Re-dispatched after the fix to confirm the
  commit/push step goes green. Open question for Codex: is top-level (all jobs) the right scope vs per-job
  `permissions:` on only the commit-back jobs? (top-level is simpler; all jobs here do commit back.)
- **Self-review verdict**: PASS pending the green CI commit step (verification in flight).
- **Suggested review base**: `--base 514d212~1`. Focus: least-privilege scope; any job that should NOT have
  contents:write; whether the read-only repo default still hard-caps the per-workflow grant.

### SCREENER-CACHE — Anthropic prompt caching for Layer-1 scoring (token reduction)
- **What**: Layer-1 reloads the ~5.6k-token screener rubric as the system prompt for ~250 candidates/day
  (~1.4M input tokens, ~39% of daily spend). Added opt-in `cache_system` to `LLMClient.chat()`; the anthropic
  backend then sends the system as a `cache_control:ephemeral` block so 2nd+ identical calls within the 5-min
  TTL read it at ~1/10 price. `02_llm_score` wires it on the per-candidate call ONLY (regime one-off stays
  uncached to avoid the ~25% write premium). No-op on claude_agent/openai/deepseek. Pure cost optimisation.
- **Commits**: `24c774f`.
- **Codex history**: not yet reviewed (gate OFF).
- **Claude self-review**: py_compile OK; structural monkeypatch test confirms cache_system=True → list with
  `cache_control={"type":"ephemeral"}` + text/type correct, and cache_system=False → plain string (no write
  premium). **NOT live-token-tested**: no ANTHROPIC_API_KEY locally (subscription) or in CI yet, and caching
  only helps the API backend (subscription/Agent SDK exposes no cache_control). Verify `usage.cache_read_
  input_tokens>0` on the 2nd candidate once an API key exists.
- **Self-review verdict**: PASS for wiring/structure; live token saving UNVERIFIED (needs API key).
- **Suggested review base**: `--base 24c774f~1`. Focus: cache_control schema for anthropic>=0.40 (beta header
  needed?); is the rubric truly byte-identical across candidates (else no cache hits)? any minimum-token risk?

### RR-CAL — Reversal Radar per-signal calibration (the monthly accuracy loop, no LLM)
- **What**: `reversal_radar_calibrate.py` breaks the forward hit-rate down BY SIGNAL so a human can see
  which reversal flags predict bounces and hand-tune `reversal_radar.py` (the pure-rules "improve accuracy
  over time" loop chosen over adding an LLM). Reads accumulated lane `scan_*.json`, resolves each entry via
  `reversal_radar_forward._resolve`/`TIERS` (EXACT same resolver — no drift), and per persisted signal flag
  (structure/momentum/options/sector/insider/analyst + tier) compares TOUCH hit-rate fired-vs-not (Wilson).
  PREDICTIVE only when fired n≥30 AND fired Wilson-lower > tier base rate; else NOISE/INSUFFICIENT.
  PROVISIONAL until ≥100 resolved/tier. NEVER auto-tunes. Outputs calibration.json + .md. Wired as a
  best-effort (continue-on-error, no LLM/secrets) step in the monthly_retrospective CI job.
- **Commits**: `936994c`.
- **Codex history**: not yet reviewed (gate OFF).
- **Claude self-review**: py_compile OK; synthetic test confirms PREDICTIVE (Wilson-lower>base), NOISE
  (lift≤0), INSUFFICIENT (n<30); real run vs the 96-entry 2026-06-08 scan → graceful PROVISIONAL (0
  resolvable same-day, no crash); workflow YAML re-parses. KNOWN LIMITATION (documented in the report):
  score-only contributors (ma_reclaim/snapback/RSI-band) are not persisted into scan_*.json → not
  attributable here. Maturity (real PREDICTIVE verdicts) needs ~1-3 months of forward accumulation.
- **Self-review verdict**: PASS for logic/structure/wiring; real-data verdicts UNVERIFIED until forward matures.
- **Suggested review base**: `--base 936994c~1`. Focus: resolver reuse stays in sync with forward.py; is
  MIN_CELL=30 / Wilson-lower>base the right PREDICTIVE bar (multiple-comparison risk across 17 signals×3
  tiers)? per-signal de-dupe correctness; should calibration also run daily vs monthly-only?

---

## ✅ Codex-passed
(none yet in this queue)
