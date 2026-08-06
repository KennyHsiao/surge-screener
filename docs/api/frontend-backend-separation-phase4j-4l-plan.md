# Phase 4J/4K/4L Separation Audit and Next-Slice Plan

- **Status:** Audits executed and verified; Phase 4M plan reviewed; no product implementation in this phase
- **Date:** 2026-08-02
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** verified Phase 4G/4H/4I receipt in
  `docs/api/frontend-backend-separation-phase4g-4h-plan.md`

The repeated trailing `4J` in the request is treated as an input duplicate. This
phase covers 4J, 4K, and 4L once each.

## Objective

1. Trace the complete Industry Roles read/write boundary before moving any part
   of that composite page.
2. Rank every remaining Streamlit consumer of `scored_candidates.json` against
   the existing strict scored feed and select exactly one next slice.
3. Recalculate the global separation inventory and publish the ordered plan
   after Phase 4A-4I.

This is an audit and implementation-plan phase. It does not authorize a new
mutation endpoint, public role-state schema, deployment change, provider move,
or product-code edit.

## Entry review

The accepted parent plan covers these three audits and explicitly requires a
separate reviewed plan before implementation. The current shared worktree is
dirty with the already reviewed frontend/backend and unrelated concurrent UX
work; this phase preserves those bytes and does not use branch cleanup, reset,
commit, push, pull, or deployment operations.

The immediately preceding Phase 4G/4H/4I implementation passed its focused,
boundary, navigation, API/OpenAPI, UX fixture, static, and complete `make test`
gates. Its ranked, scored, and Money Flow artifacts were byte-identical after
implementation. The separately owned accessibility selector suite remains at
24/27 in the shared worktree: one frozen capture-stack authority mismatch and
two whole-file `ui/radar.py` state mismatches. Those failures predate and do not
intersect this audit, so their frozen authority is not weakened here.

## Phase 4J — Industry Roles read/write-boundary audit

### Exact dependency flow

| Surface | Current source/action | Ownership and dependants |
|---|---|---|
| Ranked candidate seeds | Local `ranked_candidates.json` through `_shared.load_json()` | Public presentation seed; only this half has an existing strict feed |
| Social candidate seeds | Local `reports/x_influencer_picks.json` | Independent persisted sibling; no existing strict client |
| Taxonomy | `content/industry_roles.json` through `engine.load_taxonomy()` | Curated role definitions used by the page and role resolver |
| Approved overrides | `content/industry_role_overrides.json` through `engine.load_overrides()` | Durable reviewed state used by Trade State |
| Suggestions | `reports/industry_role_suggestions.json` through `engine.load_suggestions()` | Review queue used by the page and Trade State |
| Generate action | `engine.generate_suggestions()` | Reads taxonomy, overrides, theme baskets, and existing suggestions; writes suggestions |
| Approve action | `engine.review_suggestion(..., "approve")` | Writes overrides, then writes suggestion review state |
| Reject/defer action | `engine.review_suggestion()` | Writes suggestion review state |
| Pipeline dependant | `scripts/run_candidate_pipeline.py` | Generates suggestions outside Streamlit |
| Trading dependant | `scripts/trade_state.py` | Reads taxonomy, overrides, and suggestions, then resolves display roles |

The page is therefore not one read surface. It combines two candidate sources,
three persisted role-state reads, role resolution, a generation action, and
three review actions. Calling the whole page API-only would be false.

### Blocking findings

1. `_write_json()` writes directly to the target path. An interrupted write can
   leave invalid or partial JSON.
2. Approve performs two separate durable writes: overrides first, suggestions
   second. A failure between them can leave a half-applied review.
3. The current API is fixed, loopback-only, unauthenticated, and GET-only. It has
   no identity, authorization, idempotency key, optimistic concurrency, audit
   actor, or transactional mutation contract suitable for review actions.
4. A public role-state read would need an explicit projection and privacy
   decision for review metadata; reflecting the current files is not an
   acceptable API design.
5. The deterministic UX fixture intentionally permits one combined state read
   and two shared JSON reads while requiring
   `mutator.industry_roles.write.attempt == 0`. A migration must preserve that
   authority rather than bypassing it.

**Verdict for whole-page or mutation migration: NO-GO.** The blockers are in
the proposed scope, not regressions caused by Phase 4A-4I. No write API may be
implemented until atomic persistence, concurrency/idempotency, identity,
authorization, audit attribution, and recovery semantics are separately
designed and tested.

### Safe read-only sub-slice

The ranked half of `_candidate_tickers()` can later use the existing strict
`GET /api/v1/candidates/ranked/feed` client. The X-picks source, taxonomy,
overrides, suggestions, resolver, pipeline generation, and review actions must
remain unchanged.

Required behavior for that future slice:

- request the ranked feed at most once per page rerun;
- treat valid empty separately from unavailable/client failure;
- never fall back to local `ranked_candidates.json`;
- preserve valid X picks when the ranked feed is unavailable;
- surface a fixed sanitized partial-state message without disabling generation
  from X-only seeds;
- keep all role state and writes local and keep the existing zero-mutator
  fixture authority.

Ripple risk for this narrow sub-slice is **3.2/10 (low)**. The page is composite,
but the selected change is one fixed read, reversible, and covered by source,
fixture, navigation, and role-engine tests. This is queued after the simpler
Phase 4M scored consumer.

## Phase 4K — Remaining scored-consumer prioritization

The strict scored feed provides ordered, unique candidates with `scan_date`,
`ticker`, the canonical `REJECT | WATCHLIST | NEEDS_LAYER_2` verdict,
composite/regime-adjusted scores, seven allowlisted dimensions, missing-data
and due-diligence flags, signals, risks, and suggested entry zone. It
intentionally excludes root regime/count metadata, technical breakdown,
anti-example diagnostics, suggested stop, and suggested position size.

| Rank | Consumer | Feed-field fit | Adjacent work and risk | Decision |
|---:|---|---|---|---|
| 1 | `ui/us_options.py::_candidate_grid` | Exact: ticker, verdict, adjusted/composite score, `scores.options_flow` | One page-level feed; existing per-ticker local IV history remains local, so no HTTP N+1. Standalone grid only; embedded `render_for()` is unaffected. **3.1/10** | **Select for Phase 4M** |
| 2 | `ui/options_cockpit.py::_watchlist_quickpick` | Exact: scan date, ticker, verdict, adjusted score; official rows can be `verdict != REJECT` | Narrow helper but inside the 1,787-line highest-coupling page with eight direct backend bindings and several private/provider siblings. **3.9/10** | Queue after simpler slices |
| 3 | `ui/analyst_views.py::_render_grid` | Exact: ticker and verdict | One analyst-provider read per candidate remains; default-detail behavior depends on resulting order. **4.2/10** | Defer until provider fan-out contract is frozen |
| 4 | `ui/sector_rotation.py` candidate mapping | Exact: ticker and verdict | One cached sector-provider mapping per ticker plus snapshot/provider siblings and selection state. **4.5/10** | Defer |
| 5 | `ui/us_screener.py` | Insufficient | Requires root regime/counts and projected-out stop, size, technical-breakdown, and anti-example fields. **7.3/10** | **NO-GO on current feed** |

Scores use the existing Ripple weighting for impact, breaking potential,
pattern uncertainty, coverage gaps, and reversibility. They are comparative
risk estimates, not fabricated line-coverage measurements.

### Correctness prerequisite discovered during review

`ui/us_options.py` currently maps legacy `NEEDS_LAYER2` and `WATCH` strings, but
the writer and strict feed use canonical `NEEDS_LAYER_2` and `WATCHLIST`.
Without a correction, valid strict rows can receive the unknown grey icon and
default sort bucket. Phase 4M must first add a failing canonical-verdict test,
then correct only that mapping as part of the target grid. This is an existing
target-surface bug, not an API contract change.

### Gateway decision

Phase 4M needs no new endpoint, model, projector, route, request field, response
field, OpenAPI revision, or deployment setting. It adopts the existing fixed
strict scored client. The three loose compatibility endpoints remain
unadopted and must not replace strict feed clients.

## Phase 4L — Global separation re-audit

### Measured progress

| Measurement | Phase 4A baseline | Current | Delta |
|---|---:|---:|---:|
| Streamlit navigation pages | 27 | 27 | 0 |
| Python modules under `ui/` | 42 | 42 | 0 |
| FastAPI GET operations including health | 12 | 15 | +3 |
| Fixed Streamlit HTTP loaders | 5 | 11 | +6 |
| UI modules consuming fixed loaders | 5 | 12 | +7 |
| API-only Streamlit consumer slices | 5 | 13 | +8 |
| Direct `ui -> scripts` bindings | 65 / 21 modules | 65 / 21 modules | 0 |
| UI modules importing `_shared` | 34 | 32 | -2 |
| UI modules calling `_shared.load_json` | 24 | 19 | -5 |
| Implemented v1 routes without a fixed UI client | 6 | 3 | -3 |

The three unadopted routes are the source-preserving compatibility GETs for
ranked candidates, scored candidates, and Options Flow latest. New consumers
must continue to use their strict `/feed` siblings.

### Interpretation

- The repository has made real source-level progress: thirteen selected reads
  no longer fall back to their migrated artifacts in Streamlit.
- Process-level separation is not complete. The unchanged 65 direct script
  bindings, 19 remaining shared JSON consumers, DuckDB/Parquet access,
  subprocesses, live providers, durable writes, and operational/private state
  keep substantial backend work inside Streamlit.
- AI Updates has a reviewed presentation/API-only dependency closure. Crypto
  Universe is the only receipt explicitly classified as a complete API-only
  page. Most other achievements are deliberately narrow source slices on
  composite pages.
- Docker Compose uses separate API and Streamlit processes, a shared loopback
  network namespace, and health-gated startup. Both services still share data
  volumes because many non-migrated Streamlit readers need them.
- The systemd deployment gate restarts and verifies API before Streamlit, but
  `surge-screener.service` itself declares only `After=network-online.target`;
  it does not encode an API unit dependency for host reboot/startup. This is a
  deployment-resilience gap, not a blocker for the selected read-only slice.
- The loopback service has peer/Host containment but no reusable user identity
  or authorization. Private portfolio/watchlist/chat data and all mutations
  remain outside this public read API.

**Global verdict: not fully separated.** Phase 4A-4I remain valid; no unexplained
scope drift, new direct script binding, strict-contract regression, or reason to
roll back a completed slice was found.

## Accepted next implementation plan — Phase 4M

**Objective:** migrate only the standalone US Options scored candidate grid to
the existing strict scored feed.

1. Add fail-first tests for available, available-empty, unavailable, every
   bounded client failure, exactly one scored request, no local scored fallback,
   canonical verdict icon/order, and preserved local per-ticker IV reads.
2. Change `_candidate_grid()` through a small typed page-state adapter. Consume
   `ScoredCandidateFeedItem` objects in memory and keep `_iv_rank_spark()` local.
3. Render valid empty and unavailable/failure as distinct sanitized states.
   Manual per-ticker options and embedded `render_for()` must remain usable.
4. Correct the canonical `WATCHLIST` and `NEEDS_LAYER_2` verdict mapping in the
   same target function; keep legacy aliases only if tests prove a still-valid
   non-feed caller requires them.
5. Update the exact backend-boundary, navigation, IV-history, UX fixture/counter,
   Make test inventory, endpoint inventory, user guide, and implementation
   receipt. No API/OpenAPI/provider/writer/deployment file should change.
6. Run the new focused suite, existing IV suite, candidate-feed suite, boundary,
   navigation, UX fixture/contract, API/OpenAPI, compile, whitespace, artifact
   integrity, and complete `make test` gates. Compare the final diff to this
   plan and stop on any unexplained scope expansion.

Estimated production impact is one UI module and roughly 35-70 changed lines.
Test/documentation impact is one new focused suite plus bounded amendments to
existing exact contracts. **Phase 4M verdict: GO after this reviewed plan; it is
not executed as part of the 4J/4K/4L audit.**

## Subsequent queue

1. **Phase 4N — Industry Roles ranked-seed API-only slice:** adopt only the
   ranked half described in Phase 4J; preserve X picks, state, pipeline, and all
   writes.
2. **Phase 4O — Options Cockpit scored quick-pick slice:** reassess the narrow
   helper after 4M/4N, with the private sibling reads and high-coupling fixture
   frozen explicitly.
3. **Phase 4P — systemd API lifecycle hardening:** after the concurrently edited
   deployment work is stable, review declarative API/app ordering and failure
   policy without widening the loopback trust boundary.
4. Continue with Analyst Views and Sector Rotation only after their existing
   per-ticker provider fan-out and partial-state behavior have focused tests.
   US Screener requires a separate public projection decision and remains last.

## Verification requirements for this audit

- focused Industry Roles engine tests;
- backend-boundary and dashboard-navigation contracts;
- candidate feed and API/OpenAPI suites;
- deterministic UX fixture contracts, while reporting the separately known
  accessibility authority failures without changing their baselines;
- static compilation and whitespace checks;
- exact artifact hashes before and after this documentation-only phase.

## Verification receipt

| Gate | Result |
|---|---|
| Industry Roles engine | 8/8 passed |
| Backend boundary | 12/12 passed |
| Dashboard/navigation | 55/55 passed |
| Candidate feeds | 8/8 passed |
| API/OpenAPI | 44/44 passed in the authorized loopback environment |
| Deterministic UX fixtures | 26/26 passed in the authorized low-level environment |
| Python compile | passed for `api`, `ui`, and `scripts` |
| Whitespace | `git diff --check` passed |
| Ranked artifact | `ca85c80320db03bedb2175f12f54a7c5d08fe1671fc4da7255b16e1d1ea8b5ea` unchanged |
| Scored artifact | `6af375439dd470ea6f3c0bd985b3bfc16cbef62ae56791f270db36a1cff57b99` unchanged |
| Money Flow artifact | `96ed833428bc08f4845f49d0d03bda5be651d8caad4d8e5c3f94eeb9b3961731` unchanged |

The first API and fixture attempts failed only where the workspace sandbox
forbids loopback sockets and low-level descriptor operations. The identical
authorized commands passed. The separately owned accessibility selector suite
was rerun and remains exactly 24/27 with the same frozen capture-stack and
unknown `ui/radar.py` whole-file authority failures described at entry. No
authority file was rewritten and no failure was reclassified.

Final review found no product-code diff, no new route or client, no changed
artifact byte, and no unexplained scope drift. Phase 4J/4K/4L are complete.
Phase 4M is ready for a separate implementation instruction.
