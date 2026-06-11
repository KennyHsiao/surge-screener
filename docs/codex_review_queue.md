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

## ▶ Run order when credits return (triage — 2026-06-09)

**Strategy (user 2026-06-09): don't tunnel on one item for many rounds. Clear the quick PASSes
first; run the long-running one to completion.** Codex credits CYCLED: restored 2026-06-09 (ran the
C-10 SHIP confirmation 3 rounds), **OUT AGAIN 2026-06-10 mid-confirmation** (user said log + continue).
When credits return, go top-down:

| # | Item | State | Run FIRST? | Base |
|---|------|-------|-----------|------|
| — | **C-10** | ✅ **CODEX SHIPPED 2026-06-11** (round 7 "approve, no material findings") | done | — |
| — | **C-1b** | ✅ **CODEX SHIPPED 2026-06-11** ("approve, no material findings") | done | — |
| 1 | **C-5** | self-review PASS + cloud ultrareview already done | ▶ next | `a529238~1` |
| 3 | **C-8** | self-review PASS + cloud ultrareview already done | ✅ | `237a5f2~1` |
| 4 | **C-1** | self-review PASS; Codex r3 was cut off pre-verdict | ✅ | `1a0ca5e` |
| 5 | **C-9** | self-review PASS (depends on C-1b) | ✅ after C-1b | `561113d~1` |
| — | **C-11** | ✅ DONE (forward-track provenance, r19 `08b886d`) | — | — |

**C-10 CLOSED** (7 SHIP-confirm rounds, findings 2,2,1,3,1,1,0 — final verdict "approve"). Remaining:
the five quick items above, ~1 Codex round each, run serially (no commits mid-review, reset the
broker after any re-login). The radar-track items (RG-*, RR-*, MKT, SCREENER-CACHE, RR-CAL, TF-*)
are the other AI's and out of this scope.

---

## ⏳ Pending Codex review

### TF-1 — 主題資金流 (theme money-flow) + 內部人 Form-4 overlay + EDGAR daily upgrade
- **What**: New `主題資金流` feature — a US port of the 台股 sectorrotation.netlify.app
  money-flow idea over ~35 narrow theme baskets, using a Chaikin-$ price×volume **PROXY**
  (no free US 法人淨買超), labelled honestly throughout. Plus a **real-money corroboration**
  overlay: per-theme insider Form-4 net-buy with proxy-vs-insider **divergence** flags, from
  two sources — yfinance (6-month aggregate) and **SEC EDGAR open-market Form-4 P/S** (daily,
  `scripts/insider_edgar.py`). Phase-1 UI-only (NOT wired into scoring); complements the
  existing 熱錢板塊輪動 page (parent-sector bridge + cross-link).
- **Commits**: `b2fa9c6` (engine+baskets+LLM read+page+nav), `7489dfb` (gitignore theme_flow.json),
  `cbb42a5` (yfinance insider overlay + divergence), `09257b2` (EDGAR daily Form-4 upgrade).
  NOTE: retro/market-thesis commits are interleaved in history but OUT OF SCOPE for this item.
- **Codex history**: design hardened pre-merge by 2 Codex adversarial passes (P0 universe
  selection-bias; NaN-SUM, honest labels, overlap, bubble-size, sector bridge, eps_x, heat
  collinearity, chunk-failure). Post-merge reviews (2026-06-11, after the codex auth fix):
  - **r1** (`b2fa9c6~1`): needs-attention — 3 fail-opens (H1 chunk-coverage denominator
    excluded failed downloads; H2 EDGAR fetch-fail → silent zero, cacheable; M1 thin insider
    coverage could fire a one-ticker theme 背離) → **all fixed in `dac138b`** + 3 regressions.
  - **r2**: H1 confirmed FIXED; 2 residuals (H2b: malformed open-market P/S amounts still
    silently skipped inside well-formed XML; M2: LLM `insider_divergence` persisted
    unvalidated — hallucination could render as Form-4 evidence) → **both fixed in `d83375f`**
    (`_parse_form4` fails the document closed on unreadable open-market amounts;
    `_filter_insider_divergence` whitelists to themes carrying covered insider data) + 2
    regressions (14/14 + 7/7 green).
  - **r3 (final confirm) PENDING — workspace credits exhausted again at launch.** When
    refilled: confirm round at `b2fa9c6~1` (verify H2b/M2 + no new fail-open); a clean
    round ⇒ ✅ 放行.
- **Claude self-review**: green — `scripts/test_theme_flow.py` 14/14 + `scripts/test_insider_edgar.py`
  7/7 (nested-`<value>` parse, open-market filter, malformed-amount fail-closed, chunk-coverage
  suppression, thin-insider suppression, LLM-divergence whitelist, never-raises/None paths);
  engine + EDGAR validated on live data (NVDA yfinance +58M shares was grant/split noise →
  EDGAR shows −$225M open-market sells; the divergence the overlay is built to catch). All gathers
  fail-closed to None; EDGAR serial-throttled (<10/s) + 1d-cached; proxy honesty caveats everywhere.
- **Suggested review base**: `b2fa9c6~1` (focus ONLY the 8 theme-flow/insider files:
  `scripts/theme_flow.py`, `scripts/theme_rotation.py`, `scripts/insider_edgar.py`,
  `content/theme_baskets.json`, `ui/theme_flow.py`, `ui/_shared.py`, `ui/sector_rotation.py`,
  `app.py` + the two `scripts/test_*` — skip the interleaved retro/market-thesis commits).
  Focus: proxy honesty (no over-claim of real flow), EDGAR Form-4 parse correctness, fail-closed.

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

### C-1b — report --events derived from --lift dataset dir · ✅ **CODEX SHIPPED 2026-06-11**
> **VERDICT: "approve — SHIP. The scoped C-1b path derives default --events from the --lift dataset
> dir, _universe_mismatch fails closed on the asymmetric missing cases, and the later C-10 guards do
> not reopen this path. Guard test passed; committed sp1500 and sp500_pit chains passed universe,
> same-run, features-fresh, authoritative-coverage, and strict-floor checks. No material findings."**
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

### C-10 — pipeline-wide MANDATORY fail-closed provenance + blocked-machine-readable cards · ✅ **CODEX SHIPPED 2026-06-11** (round 7, base `c137be9~1`)
> **FINAL VERDICT (SHIP-confirm round 7): "approve — the scoped round-6 fix holds. I found no
> defensible remaining TOCTOU path in retro/forward/knowledge that returns or renders lift-derived
> values from a stale, forged-safe, or floor-less artifact, and no material over-block of a
> legitimate retro run. No material findings."** Full arc: 17 per-round Codex rounds → r15 25-agent
> all-consumer audit → r16 transitive fix → r18-r21 class-based passes (2 HIGH found+fixed) →
> 7 Codex SHIP-confirm rounds (findings 2,2,1,3,1,1,**0** — every fix held). **C-10 CLOSED.**
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
- **RE-REVIEW round 16** (Codex). NO-SHIP on 1 [high]: "latest.json can stay unblocked when its
  factor_lift is stale" — a TRANSITIVE-staleness gap the r15 audit MISSED. The UI latest re-anchor
  checked latest's events + `factor_lift_generated_at` but NOT features, so a rebuilt-features run
  (EDGAR F1→F2, same events) with `factor_lift`/`latest` left on the old lift L(F1) flagged the lift
  tab stale yet latest — chaining to that same stale lift — passed and `_recommendations_tab` could
  render stale LLM narrative/proposed_changes as actionable. Fixed in `86e02fe`: (1) retro_report
  stamps `source.features_generated_at` into latest.json; (2) the UI latest re-anchor now requires
  `features_generated_at == current surge_features.generated_at` AND latest transitively inherits the
  loaded factor_lift's staleness (belt-and-suspenders); (3) backfilled the features token onto the
  committed latest.json (root + PIT); (4) tests: ui rebuilt-features-stale + missing-token cases,
  committed-chain asserts latest carries the features token, subprocess test that retro_report stamps
  it. retro_modules 34/34, integration + live_factors green; real chains fresh.
- **WHY the r15 audit missed it:** the audit graded each consumer per-facet ("does it re-anchor
  features?") and the UI *did* have a latest re-anchor, so it scored features_fresh = applies — the
  agent didn't model the TRANSITIVITY (latest chained to factor_lift; a stale factor_lift poisons
  latest even though both tokens agree). Lesson: re-anchor every derived artifact DIRECTLY to the
  authoritative surge_events/surge_features, never transitively via another derived artifact.
- **Self-review verdict round 16**: PASS — transitive hole closed + direct features anchor.
- **RE-REVIEW round 17: COULD NOT RUN — Codex genuinely out of credits** ("Your workspace is out of
  credits. Ask your workspace owner to refill"). Substituted a Claude SELF-AUDIT of the exact thing
  r17 would check — **any OTHER transitive-staleness path** (a consumer chaining to a derived
  artifact instead of re-anchoring to the authoritative surge_events/surge_features):
  - retro_report (latest now stamps + the UI requires the features token), retro_modules (reads the
    authoritative surge_events.json + surge_features directly), knowledge_sync / knowledge_runway_sync
    (assert_same_run + assert_features_fresh vs the SIBLING surge_events/surge_features), oversold scan
    (anchors BOTH directly), live_factors (lift_provenance_ok vs siblings), ui lift/module (direct).
    → every retro-chain consumer now re-anchors DIRECTLY; `latest` was the only transitive one and is
    fixed. **No other r16-class hole found in the retro chain.**
  - SELF-IDENTIFIED separate item (NOT r16-class, logged honestly): `forward_factor_lift.json` is
    rendered ungated in `ui/retro_analysis._forward_lift_section` and carries NO `source` provenance.
    But it is a DIFFERENT data lineage (built from `forward_snapshots.csv` + realized forward returns,
    the point-in-time / survivorship-free track) — it does NOT chain through factor_lift/surge_features,
    so re-anchoring it to them would be wrong. No forward artifact is committed yet (status
    `accumulating`). → tracked below as **C-11 (forward-track provenance, Phase 3)**, not a current
    fail-open in the retro events→features→lift→cards/latest contract.
- **Self-review verdict round 17 (Claude, in lieu of Codex)**: PASS for the retro chain (transitivity).
- **RE-REVIEW round 18 (Claude class-based adversarial workflow, in lieu of Codex)** — `tasks/whru092of`,
  11 agents, framed by ATTACK CLASS not per-consumer (the lesson from r16). It CONFIRMED **3 fail-opens
  (2 HIGH) that ALL 17 Codex rounds + the r15 per-consumer audit missed**; 5 classes clean
  (temporal-ordering, transitivity, floor-cohort, ui-display, helper-bypass). Fixed in `c137be9`:
  1. **[HIGH forge-tamper]** `is_recommendations_blocked` re-derives the gate from coverage's SAFETY
     fields, but those are self-reported in the same hand-editable factor_lift (merely COPIED from
     events by coverage_gate). A forged/legacy coverage with survivorship/membership_stale/delisted
     flipped safe (tokens+floor intact) UNBLOCKED cards, latest.json, LLM proposed_changes, UI
     VALIDATED, live band — reproduced end-to-end on the real sp500_pit artifacts. Added
     `events_implied_block()` + `assert_coverage_authoritative()` (cross-check the gate vs the
     AUTHORITATIVE surge_events), wired into EVERY consumer.
  2. **[HIGH cache-replay]** the `--from-cache` floor guard used `or 0.0` → a filtered cache with a
     missing floor replayed as 'unfiltered' (asymmetric biased lift). strict_floor + None-guard at
     retro_factor_lift / retro_runway_neutral_check / retro_modules.
  3. **[LOW blocked-leakage]** the UI re-anchor force-blocked a stale latest but left
     exploratory_override set → LLM prose still rendered. Exploratory gate now honors
     _stale_provenance + the re-anchor clears the opt-in.
  +regressions across 5 suites; retro_modules 35/35, all green; real chains no false-reject.
- **HONEST estimate correction:** at r17 I told the user "~1-2 rounds, 60% one round." r18 then found
  2 HIGH — so the per-round estimate is UNRELIABLE: new ATTACK CLASSES keep surfacing holes that
  per-round review misses. Better convergence metric = run class-based adversarial passes until ONE
  returns 0-confirmed across ALL classes, THEN one Codex confirm. Codex per-round missed this class
  for 17 rounds; the class-framed Claude workflow is the stronger detector. **Do NOT claim C-10 SHIP
  until a fresh class-based pass is fully clean AND Codex confirms.**
- **Findings trend (blocking/round):** 5,3,2,2,2,2,2,3,2,2,2,1,1,1,(r15 audit),1(r16),0(r17 self),
  3(r18 class-based: 2 HIGH).
- **r18 stop-review (Codex)** caught a fail-open IN the r18 fix: `events_implied_block` only blocked
  on explicitly-unsafe fields, so a forged events with `point_in_time_membership=True` but OMITTING
  membership_stale/delisted_data_gap passed as safe. Fixed `0756776` (block unless ALL three
  explicitly safe) + regression. Real chains still block.
- **RE-REVIEW round 19 (Claude class-based, in lieu of Codex)** — `tasks/w4ejoh319`, tried to BYPASS
  the r18 fixes + 4 new classes. **6/7 classes CLEAN** (bypass-forge, bypass-cache-floor, schema-type,
  numeric-stat, new-consumer-scan, helper-internal) — the r18 fixes held under direct bypass attempts.
  1 confirmed [MEDIUM]: the forward-lift UI section rendered VALIDATED/lift with NO provenance gate —
  the one derived artifact excluded from the r18 re-anchor (= the C-11 item). Fixed `08b886d`: stamp a
  freshness `source` on the forward payload + UI re-anchor (kind='forward', freshness-only since
  forward is survivorship-free) + `_forward_lift_section` refuses a stale/unprovenanced forward.
- **Findings trend (blocking/round):** ...,1(r16),0(r17 self),3(r18: 2 HIGH),1(stop-review),
  1(r19: forward, pre-known). Converging: r19's bypass-the-fix classes all clean.
- **RE-REVIEW round 20 (Claude convergence pass, in lieu of Codex)** — `tasks/wuvzgea5m`. **0 CONFIRMED,
  5/5 classes CLEAN**: forward-fix-bypass (the r19 forward gate holds), remaining-ui (events tab /
  oversold lane / stock_checkup — no other ungated surface), temporal-ci-deep (CI ordering + partial
  writes clean), **regression-from-fixes (my r18/r19 fixes introduced NO over-block / false-close)**,
  completeness-critic (no un-probed attack class found a hole). CONVERGENCE REACHED: across r18+r19+r20,
  ~19 distinct attack classes by 3 independent class-based passes are clean after fixing what r18/r19
  surfaced. This is the genuine SHIP signal the per-round loop never produced.
- **Findings trend (blocking/round):** ...,3(r18),1(stop-review),1(r19 forward),**0(r20 — all 5 clean)**.
- **CODEX SHIP CONFIRMATION (base `c137be9~1`) — 3 rounds run, each found valid issues my 3 class-based
  passes MISSED, all FIXED; FINAL SHIP now PENDING a credit refill** (Codex out of credits 2026-06-09/10):
  - **round 1 → NO-SHIP** (`aecc1e1`): [HIGH] forward freshness anchored to the WRONG input (events/
    features tokens, but forward derives from forward_snapshots.csv) → now fingerprints the CSV
    (`source.snapshots_sha256`) + UI hash-checks it; [MED] stock_checkup BATCH dropped the live blocked
    flag → score_surge returns `provenance_ok`; batch suppresses garbage / marks directional 探索性.
  - **round 2 → NO-SHIP** (`d1a0740`): [HIGH] the SINGLE-stock path still rendered bands from a
    provenance-bad lift (I'd only fixed batch) → `_provenance_locked()` hard-locks BOTH single
    (_header band + _scorecard) and batch; [MED] forward hash RACE (parsed rows then re-read file to
    hash) → now reads bytes ONCE, hashes those exact bytes, parses rows from the same buffer (atomic).
  - **round 3 → NO-SHIP** (`cfa0430`): [MED] the batch _bad row still leaked 符合/原型 (lift-derived) →
    score_surge now ZEROES every lift-derived field (band/score/match counts/lists) when
    provenance_ok is False, at the SOURCE, so no surface can leak; batch row blanks 符合→— / 原型→0.
  - **Self-review verdict (rounds 1-3): PASS** — proactively swept ALL band surfaces (grep: band renders
    ONLY in stock_checkup, all 3 paths gated; live_factors has no other UI consumer). Lesson: the
    class-based passes are strong for NOVEL classes (caught r18's 2 HIGH), but the iterative Codex
    sign-off caught INCOMPLETE ROLLOUT of a fix across surfaces (batch≠single, etc.). All suites green.
  - **r21 stand-in convergence pass** (Claude, in lieu of the pending Codex round) — `tasks/wi05u4lzr`,
    4 angles: **0 CONFIRMED, all clean** — exhaustive surface-leak sweep of stock_checkup (all tabs) +
    retro_analysis (all tabs), round-3 zeroing + forward atomicity verified, and a "predict Codex
    round 4" critic that found/predicted NOTHING. Plus the FULL my-track suite (15 offline suites) green.
  - **round 4 → NO-SHIP** (credits returned briefly; fixed in `e2f2f5d`): 3 valid findings the r21
    stand-in had cleared as not-real — [HIGH] `_lift_tab`/`_modules_tab` were banner-then-render, so a
    force-blocked (stale/forge) artifact still leaked lift/verdict/q_value tables → both tabs now
    HARD-HIDE (return early); [MED] `score_surge` parsed tables BEFORE the provenance gate — a
    schema-drifted garbage lift (string lift) crashed in `_factor_weight` instead of locking →
    provenance-FIRST early-return + numeric guards; [MED] `_forward_lift_section` showed accumulating
    progress counts before the provenance check → gate moved ahead of the accumulating branch.
    +3 regressions (live_factors 8/8, retro_modules 36/36).
  - (Codex session expired mid-batch after round 4; user re-ran `codex login` 2026-06-11; stale broker
    cleared via removing `broker.json` + the dead socket → fresh broker picked up the new auth.)
  - **round 5 → NO-SHIP** (fixed in `c20b94a`): [HIGH] `score_surge` classified a FORGED-safe coverage
    (self-reports UNBLOCKED while authoritative surge_events imply blocked — the r18 forge class) as
    `provenance_ok=True` and returned real band/score/n_matched/verdicts; stock_checkup rendered it as
    a directional band instead of the source lock. Fix: `assert_coverage_authoritative` semantics
    applied gracefully INSIDE score_surge BEFORE table traversal (`events_implied_block(_ev) and not
    is_recommendations_blocked(lift)` ⇒ garbage ⇒ locked zero-field early return). Codex confirmed
    "round-4 UI fixes hold". +forged-safe regression. live_factors 9/9.
  - **round 6 → NO-SHIP** (fixed in `0c2bc07`): [MED] TOCTOU — `lift_provenance_ok` read surge_events
    for the token check, then score_surge RE-read it for the forge/blocked checks; a regeneration
    between reads let a stale lift pass tokens vs E1 while the forge check saw safe E2. Fix:
    score_surge loads events+features EXACTLY ONCE, every check runs against the SAME snapshots
    (`_lift_provenance_ok_loaded`); flip-flop regression asserts exactly one read. live_factors 10/10.
    Codex confirmed "round-5 closes the forged-safe happy path".
  - **round 7 → COULD NOT RUN: Codex OUT OF CREDITS again** (2026-06-11). Claude self-review stand-in
    for round-7's question (any OTHER consumer with the same multi-read TOCTOU): retro_modules
    (`_events_art` read once, reused for anchor + events_implied_block), knowledge_sync (`events` read
    once for assert_same_run + assert_coverage_authoritative), oversold (`_ev_art` once), ui render()
    (loads each artifact once per render, all checks against those dicts) — **live_factors was the only
    double-reader; no other multi-read gate found.**
  - **PENDING (after credit refill):** round 7 at `--base c137be9~1` to confirm round-6 → then mark
    C-10 ✅. SHIP-confirm trend: 2,2,1,3,1,1 — each round confirms the prior fixes hold; the tail is
    single narrow findings on the newest code.
- **Findings trend:** ...,3(r18),1(stop),1(r19),0(r20 class-based clean),**SHIP-confirm 2,2,1,3,1,1
  (Codex, all fixed)** → round-7 confirm pending credits.
- **Suggested review base**: `--base c137be9~1` (r18→round-6 SHIP-confirm fixes) or `981c05d~1` (full C-10).
- **THEN the quick items** C-1b/C-5/C-8/C-1/C-9 (each ~1 Codex round; see run-order board at top).

### C-11 — forward-track provenance (Phase 3, self-identified r17) · ✅ DONE (r19, `08b886d`)
- **DONE 2026-06-09 (r19):** the forward artifact now carries a freshness `source` (events+features
  at compute time) and the UI re-anchors it (kind='forward', freshness-only — survivorship-free
  track) + `_forward_lift_section` fails closed on a stale/unprovenanced forward. Closed the MEDIUM
  fail-open r19 confirmed. Full snapshot-integrity provenance (date range / resolution) remains a
  nice-to-have once a forward artifact actually ships, but the fail-open is closed.
- ~~NOT STARTED~~ (historical note below):
- **What**: `retro_forward_lift.py` writes `forward_factor_lift.json` with NO `source` block, and
  `ui/retro_analysis._forward_lift_section` renders its per-factor lift/verdict with no freshness or
  blocked gate. The forward track is the point-in-time, survivorship-free ("唯一可行動") track, so it
  deserves its OWN provenance contract anchored to `forward_snapshots.csv` integrity (snapshot date
  range + resolution ratio + a generated_at the UI can stale-check), NOT to surge_events/surge_features.
- **Why deferred**: no forward artifact is committed yet (needs weeks of daily snapshots → currently
  `status: accumulating`), and it is a separate lineage from the C-10 retro chain. No live fail-open
  today; becomes relevant once forward_snapshots.csv accumulates enough to publish `status: ready`.
- **Codex history**: none yet (queue for review once Phase 3 forward provenance is implemented).

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

### MKT — 大盤行情研判 Agent (event-driven market forecast) — DESIGN ✅ codex-approved; build pending
- **What**: a SEPARATE tool (NOT merged with the mechanical radars) forecasting the MARKET (大盤, not per-stock)
  as 看多/看空/盤整觀總 + 期程(短/中/長). DESIGN doc = `docs/market_thesis_plan.md` (v7). Redesigned to a
  TWO-TIER shape during review: **Tier 1** = code-fed deterministic baseline (events code-owned from an
  allowlist, NO free WebSearch; de-biased ≥15y multi-cycle analog corpus w/ episode-based bearish fail-closed;
  a locked (direction,bucket,support_class) resolution contract + non-overlap scorer; CI-runnable → real
  no-computer alerting gated on `manifest_status`). **Tier 2** = the agentic WebSearch/DEoT loop, OFF by
  default, gated behind a baseline ABLATION proof. Plan also at `~/.claude/plans/floofy-launching-bubble.md`.
- **Codex DESIGN review history**: 6 adversarial rounds (3→3→2+1→2+1→1+1→1 highs) → **round 7 = APPROVE / no
  material findings** (session `019eb0dc-2f17…`). v1 attacked: WebSearch-breaks-anti-hallucination, no
  resolution contract, bull-biased corpus, local-only-vs-alerting, DEoT-before-proof → all resolved by the
  two-tier redesign + locked contract + episode corpus + manifest gate + ablation gate + nullable surprise.
- **Code status**:
  - **MKT-P1 (committed `3656717` + fixes `07f8a11`,`53dceca`,`1a10873`,`57babc6`,`b517849`,`48007e6`,`39a5816`)** ⏳ —
    `market_regime_history.py` extended to v7: ^GSPC ~20y multi-cycle, forward MDD/p10/worst tails,
    deterministic episode labeller, fail-closed bearish floor, corpus publish gate. **16 offline tests green**
    (+6 in `test_market_thesis.py` incl. the forecast-path gate).
    **Codex history — 6 rounds, EACH found a real hole, ALL fixed**: r1 (VIX-bucket ≥20 fallback + example
    leakage + missing fixtures) → `07f8a11`; r2 (unresolved-episode padding) → `53dceca`; r3 (vix_bucket=None
    fallback) → `1a10873`; r4 (truthy 'unknown' sentinel bypass → CONCRETE_VIX_BUCKETS allowlist); r5 (could
    publish an empty/short corpus → corpus_inadequacy() gate + fetch reuse; stop-gate also caught the forecast
    path bypassing it → build_forecast runs the same gate); r6 (dead/truncated VIX leg ⇒ all-'unknown'
    all-range corpus could publish → MAX_UNKNOWN_VIX_RATE=1% adequacy check) → `39a5816`.
    **Round 7 (verify `39a5816`) NOT RUN — credits exhausted AGAIN mid-marathon.** Self-review PASS; PENDING
    Codex round-7 on refill — `--base 3656717~1`, focus: any residual corpus/VIX-coverage fail-open.
  - **MKT-P2 (committed; PENDING Codex)** ⏳ — the locked resolution contract + scorer + event manifest:
    `market_thesis_contract.py` (frozen ^GSPC/θ=3%/buckets 20-40-60/exhaustive 看多·看空·盤整·OTHER state
    machine/`(direction,bucket,support_class)` key/validate_forecast); `market_thesis_forward.py` (resolve_one
    no-look-ahead, deterministic greedy non-overlap walk, per-key Wilson, classes never pooled, event-driven vs
    regime-only ledgers separate, PROVISIONAL<100); `market_events.py` + `content/fomc_calendar.json`
    (allowlist-only per-type manifest, freshness → manifest_status ready/degraded, FRED fail-closed without a
    key → degraded by default). **12 offline tests** (`test_market_thesis_forward.py` 6 + `test_market_events.py`
    6). Self-review PASS; **Codex review NOT run (credits out)** — base `4c…`(P2a commit)~1, focus: any way to
    inflate counted_N / pool support-classes / a manifest 'ready' with stale or missing required events.
  - **MKT-P3 (committed; PENDING Codex)** ⏳ — Tier-1 deterministic forecaster + CI: `market_thesis.py`
    (gather verified base → pure `decide()` → one locked (direction,bucket,support_class) → ledger; delivery
    gated on manifest_status: degraded ⇒ NO Telegram + regime_only_forecast_*; ready ⇒ Telegram + forecast_*;
    weekly cooldown); CI `market_thesis` job (own cron Mon 23:00 + manual_job, no API key); `.gitignore`
    re-includes the ledger families for accumulation. **5 offline decide() tests** + smoke run (regime 盤整,
    degraded → regime_only ledger, Telegram suppressed, scorer reads it). Self-review PASS; **Codex NOT run
    (credits)**. Codex focus: decide() honesty, delivery-gate leak-proof, cadence. **To ENABLE real alerts**:
    wire a free `FRED_API_KEY` (CPI/JOBS) so manifest→ready.
  - **MKT-P4 (NOT built — GATED)**: ablation (code-fed baseline vs agentic) needs accumulated forward data
    (~months) to prove Tier-2 lift before it ships; THEN harden+enable `chat_agentic` (still has review-1 [high]).
  - **MKT-2 (UNCOMMITTED, on disk)**: `llm_client.chat_agentic` (Tier-2 only). **Has the review-1 [high]**:
    web-only boundary not real (needs `tools=["WebSearch","WebFetch"]` + `strict_mcp_config` +
    non-prompting permission + `can_use_tool` deny gate). Tier 2 is gated OFF, so this stays unwired until the
    ablation gate passes; fix the boundary THEN.
  - **MKT build order** (Codex gate INTENDED per item, but **gate currently OFF — Codex credits exhausted**;
    per user 2026-06-10 "其餘繼續": Claude continues + self-reviews, logs each here, Codex re-reviews on refill):
    P1 corpus ⏳ → **P2 (NEXT)** resolution contract schema + scorer + `market_thesis_forward.py` + event
    manifest (per-type schema + `content/fomc_calendar.json`) → P3 Tier-1 forecaster + CI cron + Telegram (two
    ledgers `forecast_*.json` / `regime_only_forecast_*.json`) → P4 (gated) ablation → harden+enable Tier-2.
- **Self-review verdict**: DESIGN PASS (Codex approve). P1 self-PASS (12 tests, 3 fail-opens closed) PENDING
  Codex round-4. P2+ built under self-review until credits refill. MKT-2 chat_agentic held (Tier-2).
- **Suggested review base/focus (for the BUILD)**: review each P# build against the v7 contract; verify the
  scorer keys on the full (direction,bucket,support_class), the manifest `degraded`⇒no-push + regime_only
  ledger separation, and the episode labeller fixtures.

---

## ✅ Codex-passed
(none yet in this queue)
