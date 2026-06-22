# 大盤行情研判 — design v7 (event-driven market forecast)

> STATUS: **Codex adversarial review = APPROVE / no material findings** (after 6 iterations resolving
> 3+3+2+2+1+1 findings). Built so far: Phase 1 `market_regime_history.py` (to extend) + a Phase-2
> foundation `llm_client.chat_agentic` (Tier-2 only, NOT wired in, on hold). Nothing in Tier 2 is built.
> EXPLORATORY throughout; direction/期程 are not "accuracy" until the forward harness matures.

## Goal / intent (from the user)
A SEPARATE tool (NOT merged with the mechanical reversal/risk radars) that forecasts the **market as a
whole** (大盤, not per-stock) from an **event-driven** read and says **看多 / 看空 / 盤整觀望** with a
**duration** (short / mid / long), reaching "深度、廣度、不幻覺" in the spirit of p1/DEoT.

## What changed in v2 (responses to the adversarial review)
The v1 design put the riskiest pieces on unproven assumptions. v2 splits the system into a **provable
code-fed baseline (Tier 1)** and an **optional agentic enrichment (Tier 2) that must EARN its place**:
- **WebSearch is removed from the trust path.** Events are **code-owned** from allowlisted official
  sources; the LLM may only summarize persisted, verified event records (fixes v1 [high] #1).
- **A concrete ex-ante resolution contract** is defined before any agent is built (fixes [high] #2).
- **The analog corpus is de-biased + fail-closed** on thin bearish samples (fixes [high] #3).
- **Tier 1 runs in CI** (code-fed, no LLM-search) → real no-computer alerting; the local WebSearch agent
  becomes optional enrichment with NO alerting SLA (fixes [medium] local-only conflict).
- **The DEoT/WebSearch loop is gated behind a baseline ablation** — disabled until it beats Tier 1 on
  locked forward forecasts (fixes [medium] DEoT-before-proof).

---

## Tier 1 — code-fed deterministic baseline (PRIMARY; CI; alerting; forward-validated)

### 1a. Event ingestion (code-owned, verified — NO free WebSearch)
Code fetches from an ALLOWLIST of official/structured sources, normalizes to event records, persists with
provenance. The LLM (if used at all here) may ONLY summarize these records — never select or invent them.
- **Keyless-verifiable now**: SPY/^GSPC, ^VIX, ^TNX (10y), DX-Y.NYB (dollar) via
  `retro_reconstruct._hist_auto_adjust_false`; CFTC COT via `cot_es`; sector RRG via `sector_flow`;
  regime via `compute_regime_context`.
- **Mandatory event manifest (Tier-1 READINESS GATE) — executable per-type schema**: a forecast ALERTS only
  when EVERY required event is present AND within its type's freshness window relative to `as_of`; otherwise
  `manifest_status=degraded`. Per-type schema (so two implementations compute the SAME status):
  - `CPI` (`fred:CPIAUCSL`): required `{released_at, value, prior}`; `surprise` is **NULLABLE** — there is no
    free verified *consensus/expected* source, so it must NEVER be derived/faked from value−prior; readiness
    keys on a fresh actual `value`, not on `surprise`. Stale if no release within ~45d. (A future allowlisted
    consensus feed can populate `surprise`; until then it stays null and unused for gating.)
  - `JOBS` (`fred:PAYEMS`/BLS): required `{released_at, value, prior}`; `surprise` NULLABLE (same rule);
    stale if none within ~45d.
  - `FOMC` (`calendar:fomc` = committed `content/fomc_calendar.json`, manually curated from the official
    federalreserve.gov FOMC schedule): `{last_decision_at, last_rate, next_meeting_at}` (prior/surprise
    nullable); stale if `next_meeting_at` is in the past (calendar not refreshed).
  - `UST10Y` (`yf:^TNX`), `DXY` (`yf:DX-Y.NYB`): `{released_at=close_date, value, delta_1d}` (prior/surprise
    nullable); stale if the close date is older than the last completed session.
  Per-type `{required, nullable}` fields + `max_age/valid_until` are config; failing records carry a
  `stale_reason`. FIXTURES for missing / stale / future / calendar-only records gate Telegram before enable.
- **Freshness/completeness gate → `manifest_status` drives ALL delivery**: each run computes
  `manifest_status ∈ {ready, degraded}`. `degraded` (ANY required event missing/stale) ⇒ **suppress EVERY
  Telegram push (forecast AND digest, no "event-driven" wording loophole)** and persist to a SEPARATE,
  schema-separated **`regime_only_forecast_*.json`** family stamped `manifest_status=degraded` — NOT the
  event-driven `forecast_*.json` ledger. Regime-only records accumulate + are forward-scored in their OWN
  `support_class`/readiness namespace, and are EXCLUDED from event-driven readiness, CI-alert, and Telegram
  paths (so they can never contaminate or pad the event-driven ledger). Until a real macro source (FRED free
  key / calendar) is wired, `manifest_status` is `degraded` BY DEFINITION ⇒ Tier 1 is non-alerting, period.
- A record with no allowlisted source is DROPPED. (Result Validation = every event row has a whitelisted
  `source_id` + timestamp; every number echoed matches the fetched record; coverage gate passed.)

### 1b. History-analog corpus — de-biased + fail-closed (extend `market_regime_history.py`)
- **Multi-cycle lookback** (≥15y, must include 2008 / 2018-Q4 / 2020 / 2022 bears), not 5y.
- Per regime report **tail metrics** (max drawdown/MDD over the window, p10 forward return, worst case),
  not just mean/up-rate — so a "correction" analog can't read as gentle mean-reversion.
- **Bearish floor (independent episodes, NOT raw sessions)**: a 看空 ANALOG claim requires the matched key
  to draw on ≥ `MIN_BEAR_EPISODES` DISTINCT correction episodes (default 3, spanning ≥2 calendar years) AND
  ≥ `BEARISH_FLOOR` NON-OVERLAPPING matured windows (default 10; windows ≥H sessions apart, same greedy rule
  as 1c) — so one prolonged bear can't supply 30 autocorrelated near-duplicates. The matched key INCLUDES
  the VIX bucket (and rates bucket once wired). Raw session counts are TELEMETRY only, never the unlock.
- **Correction-episode labelling (deterministic, testable)**: walk `^GSPC` Close; an episode spans from a
  running-peak to its FIRST FULL RECLAIM (close ≥ that peak / new high) and QUALIFIES as a correction iff its
  max peak→trough drawdown ≥ `EP_DRAWDOWN` (default 10%). A dip <10% that reclaims is no episode (peak just
  advances); a prolonged unrecovered bear stays ONE episode (anti-over-segmentation — no 50% partial split),
  and a trailing qualifying drop with no reclaim before series end is an `ongoing` episode. `start`=peak date,
  `trough`=min close, `end`=reclaim (or last) date, stable `episode_id`=trough date (ISO); non-overlapping by
  construction. Pinned fixtures: distinct episodes covering 2008 (GFC), 2018-Q4, 2020 (COVID), 2022 — unit-tested.
- **Behavior below floor**: suppress only the ANALOG reasoning — `retrieve_regime_analogs` returns
  `insufficient_bearish_analogs` (no 歷史前例 claim). The forecaster MAY still emit 看空 from event/regime
  signals, flagged `analog_unsupported=true` and scored in a **separate event-only bucket**. Insufficient
  analogs blocks the analog, NOT the forecast — so a real crash regime (thin analogs) is never silenced.
- **Telemetry**: persist + expose the suppression rate (fraction of 看空 outputs that are analog_unsupported).
- Optionally stratify/reweight by VIX + rates state.

### 1c. Forecast resolution CONTRACT — executable schema, locked ex-ante
Ship as a code/JSON schema + scorer BEFORE any forecaster, so a "miss" can never be re-spun:
- **Benchmark (exactly one)**: `^GSPC` (S&P 500 INDEX) daily **Close**, UNADJUSTED — an index has no
  dividend/split adjustment, removing near-threshold ambiguity. Single source; no fallback.
- **t0** = the thesis `as_of` session's `^GSPC` Close (no look-ahead). **Buckets (sessions)**:
  `short=20 / mid=40 / long=60`. Each forecast names exactly **ONE** primary `(direction, bucket)`.
- **EXHAUSTIVE, mutually-exclusive realized-state machine** over (t0, t0+H], with
  `r = ^GSPC[t0+H]/^GSPC[t0] − 1` and `peak = max|^GSPC[t]/^GSPC[t0] − 1|` over t in the window
  (θ_dir default 3%):
  - **看多** = `r ≥ +θ_dir`
  - **看空** = `r ≤ −θ_dir`
  - **盤整** = whole path stayed inside ±θ_dir (`peak < θ_dir`) — a TRUE range, so a +4.9%→+2.9%
    round-trip is NOT 盤整.
  - **OTHER** = everything else (breached ±θ_dir intra-window but ended inside it; whipsaw). OTHER is a
    real state and counts as a **denominator MISS** — never silently dropped.
  Every matured forecast resolves to exactly one of {看多,看空,盤整,OTHER}.
- **Cadence / non-overlap scoring (ONE locked algorithm — no "or")**: forecasts issued at most weekly. The
  walk operates on the SAME full key as the score — **`(direction, bucket, support_class)`** INDEPENDENTLY:
  oldest→newest, COUNT a forecast only if its `as_of` is ≥ H sessions after the previously COUNTED one IN
  THAT KEY (greedy; skipped ones dropped; tie-break = earliest `as_of` then lexical id). Because the walk is
  per-direction, a counted 看多 can NEVER drop or suppress an independent 看空 in the same bucket/class.
  Readiness + Wilson use ONLY this per-key `counted_N`; both `raw_N` and `counted_N` are reported.
  Block/overlap-adjusted CIs may NOT use `raw_N` for any readiness threshold. `support_class ∈
  {analog_supported, event_only, regime_only}` are separate denominators, never pooled — degraded-run
  records carry `support_class=regime_only` and can NEVER be mapped to `event_only` or enter event-driven readiness.
- **Maturity / lock**: scored only after H real sessions elapse; predictions written once to dated
  `forecast_*.json`, never edited.
- **Score**: P(realized state = predicted state) keyed on the FULL `(direction, bucket, support_class)` —
  the same key for hit-rate, Wilson CI, readiness gate, and any reported accuracy; support classes are NEVER
  pooled. Wrong-direction AND OTHER both count as miss; PROVISIONAL until ≥N **non-overlapping** matured per
  key (N≥100). A cross-class aggregate, if shown, is TELEMETRY-only and forbidden from gates/claims. TOUCH is secondary.

### 1d. Forecaster (Tier 1)
Deterministic + (optionally) a SINGLE bounded LLM summary over the verified base (regime + events +
de-biased analogs), emitting the contract's `(direction, bucket)` + reasons + falsification + the
`探索性,未驗證,非投資建議` label. No tools, no search → runs in CI.

### 1e. Delivery (gated on `manifest_status`, resolves local-only)
- **CI** (own cron): Tier 1 code-fed digest + forecast. A Telegram push happens **ONLY when
  `manifest_status == ready`** (1a); `degraded` ⇒ local `regime_only_non_alerting` artifact, ZERO pushes.
  No "event-driven" wording loophole — the gate suppresses ALL forecast/digest alerts, not a subset.
- **Persistence (two schema-separated ledgers)**: `forecast_*.json` (event-driven, fills ONLY on `ready`)
  and `regime_only_forecast_*.json` (degraded runs) are BOTH committed under an un-ignored subpath (like
  reversal_radar) so each accumulates forward evidence in its OWN namespace — never merged. `regime_history.json`
  + local Tier-2 enrichment stay gitignored (regenerable / machine-local).
- **Local**: optional Tier 2 enrichment, run by hand, NO alerting SLA. Local-only is never presented as
  satisfying automated notification.

---

## Tier 2 — agentic WebSearch/DEoT enrichment (OPTIONAL; gated; OFF by default)
The full DEoT loop (News Search + Breadth/Depth/ERIR + Result Validation) and `chat_agentic` live here.
- **Hard gate**: stays DISABLED until a baseline **ablation** shows it BEATS Tier 1 on **locked** forward
  forecasts (same resolution contract, predefined min sample). If no measurable lift after cost/failure
  modes → it does not ship.
- If/when enabled, `chat_agentic` must be **truly web-only** first (per the other review's [high]):
  `tools=["WebSearch","WebFetch"]`, `allowed_tools` exactly that subset, `strict_mcp_config=True`,
  a non-prompting permission mode, and a `can_use_tool`/PreToolUse gate that denies every non-web tool by name.

---

## Go / no-go gates (all must pass before the NEXT step)
1. Resolution contract (1c) locked in code + a forward harness that scores ONLY matured, locked predictions.
2. Corpus adequacy (1b): multi-cycle, ≥ bearish-sample floor, MDD/tail reported, fail-closed wired.
3. Tier 1 (code-fed) ships + accumulates forward results BEFORE Tier 2 is even built.
4. Tier 2 ablation lift proven on locked forecasts → only then harden+enable `chat_agentic`.

## Phases (reordered)
- **P1 (DONE→to extend)** regime corpus: extend `market_regime_history.py` to ≥15y + MDD/tail + bearish-floor fail-closed.
- **P2** event ingestion (code-owned allowlist) + the resolution contract (`forecast schema`) + `market_thesis_forward.py` (scores locked predictions).
- **P3** Tier-1 forecaster (deterministic / single bounded summary) + CI cron + Telegram.
- **P4 (gated)** ablation harness; only if it shows lift → harden `chat_agentic` web-only + Tier-2 enrichment.

## Anti-hallucination / honesty (unchanged principle, stronger now)
Hard numbers + events are BOTH code-owned/verified now (events no longer AI-selected). Forecast direction
+期程 are EXPLORATORY and labelled so until the forward harness matures; "精準/accuracy" is only ever the
forward-validated, locked-prediction hit-rate. Tier 2 cannot affect a shipped thesis until it earns it.

## Reused components
`market_regime_history.py`, `retro_reconstruct._hist_auto_adjust_false`, `compute_regime_context`,
`sector_flow`, `cot_es`, `reversal_radar_forward` skeleton + `retro_factor_lift._wilson` (forward harness),
`reversal_radar_scan._notify`/`_load` (Telegram), `025_engine_controller` + `chat_agentic` (Tier 2 only).

## Threat model & the writer-identity boundary (Codex P2 r34 — owner-accepted 2026-06-22)

The forward lock (`_git_lock_error`) and the ledger validator together provide, and are tested for:
1. **Tamper-evidence** — a post-hoc edit of a committed ledger breaks the `blob == GitHub-attested-blob`
   match (server-side run records, trusted = schedule-event runs on main, uniqueness rule), so a silently
   altered historical record cannot stay in the scored denominator.
2. **The HONEST writer's no-look-ahead** — `generated_at` ≥ as_of close, the lock window `[close, next open)`,
   and the in-session first-appearance witness (no run created during `[open, close)` may already hold the
   ledger blob/path). The real writer (the `market_thesis` CI job: `GITHUB_TOKEN`, runs post-close, has a
   pre-close guard) never trips these.

**Out of scope — writer IDENTITY against a `main` write-access holder.** A person with push access can author
a self-consistent `regime_only` ledger *inside* the lock window (post-close, so not even look-ahead) via a
PAT push, or launder an intraday commit through GitHub's `paths`-filter net-diff, and a later scheduled run
will attest it. This is a **maintainer-level** threat: no offline mechanism defends against the repository
owner, who can equally rewrite the code, the corpus, or the validation summary. Codex (an adversarial
reviewer with no ship incentive) will keep flagging it; that is expected and is **not** a ship blocker.

Fully binding writer identity requires **cryptographic writer attestation** — GitHub-verified /
`GITHUB_TOKEN`-signed commits, or OIDC artifact attestation tying each ledger to a `market_thesis` run.
That is genuine new infrastructure with high blast radius (a verification bug false-rejects *every* legit
ledger → the whole scorer rejects everything), so it is **DEFERRED** with the analog/macro source-recompute
provenance work, to be built **if/when Tier-1 alerts on real capital**. Until then the impact is bounded:
ready/notify is gated (no Telegram), so only the `regime_only` research-track denominator is exposed, and
that is a labelled, exploratory, non-investment-advice accuracy record — not a trade signal.

**Decision:** P2 ships on *in-model soundness + this documented boundary*, consistent with the already-gated
analog_supported / forecast_ (macro) / FOMC-fixture provenance residuals. We stop the writer-identity
whack-a-mole here rather than build owner-defeating crypto-attestation infra for a maintainer-level threat.

## P3 shipped scope: NON-ALERTING generation; the ready⇒Telegram path is built + gated (Codex MKT-P3 r5)

P3 (the Tier-1 forecaster GENERATION + DELIVERY code) ships as **non-alerting regime_only generation**. The
design's `ready ⇒ Telegram` path is fully **built and unit-tested** (decide → forecast_*.json → notify chain,
delivery-honesty render, family-scoped cadence, fail-closed notify, source-acquisition guards), but it is
**GATED at TWO layers** and therefore structurally unreachable today — by design, not a defect:

1. **`manifest_status` gate (design v7 §1a/§1e):** without `FRED_API_KEY`, every required event is missing ⇒
   `manifest_status == degraded` ⇒ `build_forecast` writes a `regime_only_forecast_*.json` artifact, never a
   `forecast_*.json`, and `_notify` suppresses ALL Telegram. So the live, shipped path is the regime_only
   research ledger that accumulates for forward validation with ZERO pushes.
2. **`ready_family_gated` validator gate (P2 r30):** even if FRED were wired, `validate_ledger_record`
   currently REJECTS every `forecast_*` (ready) ledger, because the live macro/analog evidence cannot be
   independently re-verified in the offline forward validator (the same class as the analog/macro
   source-recompute residual). A ready ledger would therefore fail the CI validation step (red) and never
   reach `--notify-only`.

**Consequence (the honest state):** the source-time guard (`fetch_started ≥ session_close_utc`) and fresh
cache-bypassing fetch DO apply to the LIVE regime_only generation path; the ready-DELIVERY improvements
(render honesty, family-scoped cadence, fail-closed notify, delivery retry) are **forward-looking** — correct
for when the gate lifts, inert today. **Enabling alerting requires ALL of:** wiring `FRED_API_KEY` AND
building source-backed manifest+analog provenance verification AND lifting the `ready_family_gated` gate —
these land TOGETHER (tracked with the analog/macro provenance work), gated further behind P4's ablation
proving forward-validated lift. Until then Tier-1 is non-alerting, period — and the CI ready path failing
closed (red) on a `forecast_*` ledger is the intended fail-safe, not a delivery regression.
