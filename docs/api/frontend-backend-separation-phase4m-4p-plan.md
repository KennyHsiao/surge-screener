# Phase 4M-4P Frontend/Backend Separation Plan

- **Status:** implemented and verified
- **Date:** 2026-08-02
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `docs/api/frontend-backend-separation-phase4j-4l-plan.md`

## Objective

Execute four independently reversible changes without claiming that the
composite pages are fully separated:

1. Phase 4M moves only the standalone US Options scored candidate grid to the
   existing strict scored feed.
2. Phase 4N moves only the ranked half of Industry Roles candidate seeding to
   the existing strict ranked feed.
3. Phase 4O moves only the scored-candidate portion of Options Cockpit quick
   picks to the existing strict scored feed.
4. Phase 4P makes the Streamlit user unit declaratively start after and require
   the loopback API user unit.

No new endpoint, DTO, OpenAPI field, provider migration, mutation API, role
state publication, authentication mechanism, dependency, pull, commit, push,
or deployment is authorized by this plan.

## Entry review and frozen baseline

The Phase 4J-4L audit already proved that the selected ranked/scored fields fit
the strict feeds and that whole Industry Roles mutation migration remains
blocked. The current exact target hashes were recorded before implementation:

- `ui/us_options.py`: `7283accd...301a003`
- `ui/industry_roles.py`: `f38b249c...8af8a07`
- `ui/options_cockpit.py`: `9c8f131d...7ec9e5`
- `deploy/surge-screener.service`: `c6007301...79275`
- `deploy/surge-screener-api.service`: `1708a82b...78786`

The focused entry baseline passes IV 15/15, Industry Roles 8/8, Options
Cockpit 19/19, backend boundary 12/12, navigation 55/55, UX fixtures 26/26,
deployment artifacts 18/18, and Docker runtime contracts 11/11. Ranked,
scored, and Money Flow artifact hashes are respectively `ca85c803...b5ea8b5ea`,
`6af37543...1cff57b99`, and `96ed8334...b3961731`.

The shared worktree contains accepted frontend/backend work and unrelated
concurrent changes. Each production target must be re-hashed immediately
before editing. A changed hash requires re-review rather than overwriting the
new bytes.

## Blocking-issue review

No execution blocker remains for these four narrow changes:

- Both UI feeds, strict result unions, response caps, and fixed clients already
  exist and are verified.
- Phase 4M uses one scored request and retains local per-ticker IV reads, so it
  does not create HTTP N+1.
- Phase 4N preserves X picks and every role-state read/write. Ranked failure is
  a partial state and does not disable X-only generation.
- Phase 4O preserves watchlist, social/X, Options Flow, providers, private
  state, and embedded `render_for()` behavior.
- Phase 4P aligns the user-unit lifecycle with the already health-gated deploy
  sequence and Compose dependency. `Requires=` plus `After=` is intentionally
  fail-closed for the API-only UI slices while the API unit retains its own
  restart policy.

Whole Industry Roles state/mutations remain a blocking NO-GO until atomicity,
concurrency/idempotency, identity, authorization, actor audit, and recovery are
designed. That work is outside this plan.

## Phase 4M - US Options scored grid

1. Add a fail-first focused suite covering available, available-empty,
   unavailable, every bounded client failure, one request, no local scored
   fallback, canonical `WATCHLIST` / `NEEDS_LAYER_2` icon and order, local
   per-row IV history, and zero grid calls from embedded `render_for()`.
2. Add a small typed grid state in `ui/us_options.py`. Convert the strict feed
   items in memory and retain `_iv_rank_spark()` unchanged as a local read.
3. Render available-empty separately from API unavailable/failure using fixed
   sanitized copy. Keep manual ticker analysis and live option chain usable.
4. Correct only the canonical verdict map used by this grid. Do not broaden the
   public scored contract.

## Phase 4N - Industry Roles ranked seed

1. Add a fail-first focused suite covering ranked available/empty,
   unavailable, every bounded failure, one request, no local ranked fallback,
   X-only partial output, and preserved generation/review/state behavior.
2. Add a typed candidate-seed state in `ui/industry_roles.py`. Read the strict
   ranked feed once and merge its tickers with the unchanged local X picks.
3. Surface fixed sanitized partial-state copy near candidate generation while
   preserving X-only generation and all local taxonomy, override, suggestion,
   approve, reject, and defer operations.
4. Keep the deterministic fixture's mutator counters at exact zero.

## Phase 4O - Options Cockpit scored quick pick

1. Add a fail-first focused suite covering available official rows,
   REJECT-only fallback labeling, available-empty, unavailable, every bounded
   failure, one request, no local scored fallback, and preservation of all
   other quick-pick sources.
2. Replace only the scored-candidate block in `_watchlist_quickpick()` with one
   strict scored-feed result. Preserve feed order and use `verdict != REJECT`
   as the official subset, falling back to the highest feed rows only when the
   strict feed is available and contains REJECT-only candidates.
3. Show a fixed sanitized scored-source partial-state caption only inside an
   otherwise available quick-pick expander. Do not leak client reason strings
   or turn failure into valid empty.
4. Keep `render_for()` free of quick-pick/feed work and preserve watchlist,
   social/X fallback, local Options Flow, Money Flow, reconciliation, Trade
   State, live providers, demo fallback, and session handoffs.

## Phase 4P - systemd lifecycle hardening

1. Add fail-first deployment contract assertions that the Streamlit unit has
   active `[Unit]` directives `After=network-online.target
   surge-screener-api.service`, `Wants=network-online.target`, and
   `Requires=surge-screener-api.service`.
2. Change only `deploy/surge-screener.service`; do not alter the loopback bind,
   clean API environment, health checker, deploy restart order, Compose
   topology, ports, credentials, or environment variables.
3. Verify the existing deploy script still health-gates API before restarting
   Streamlit and both units remain installable under `default.target`.
4. Rollback is the removal of the API service token from `After=` and the
   `Requires=` line; no data migration or external state is involved.

## Allowed implementation surfaces

- Production: `ui/us_options.py`, `ui/industry_roles.py`,
  `ui/options_cockpit.py`, `deploy/surge-screener.service`
- New focused tests: `scripts/test_ui_us_options_scored_api.py`,
  `scripts/test_ui_industry_roles_ranked_api.py`,
  `scripts/test_ui_options_cockpit_scored_api.py`
- Existing exact contracts: `scripts/test_ui_backend_boundary.py`,
  `scripts/test_dashboard_navigation.py`, `scripts/ui_ux_fixtures.py`,
  `scripts/test_deploy_artifacts.py`, `scripts/test_docker_runtime_contract.py`,
  `Makefile`
- Documentation/receipts: this file, `docs/USER_GUIDE.md`,
  `docs/api/fastapi-endpoint-artifact-inventory.md`, and the required
  Builder/Gear/Lens/Ripple/Gateway/project journal entries

Any API/OpenAPI/model/projector/client, provider, writer, workflow, Compose,
dependency, environment, or unrelated UI change is unexplained scope drift and
must stop execution unless a concrete blocking defect requires a reviewed plan
amendment.

## Verification gates

Run each new focused suite red-first and green after its phase. Before claiming
completion run:

- all three new focused suites;
- existing IV, Industry Roles, Options Cockpit, candidate-feed, fixed-client,
  API/OpenAPI, backend-boundary, navigation, UX fixture/contract, deployment,
  and Docker runtime suites;
- Python compile, Python 3.10 AST/static source checks, tabnanny, and diff
  whitespace checks;
- complete `make test`;
- before/after hashes for ranked candidates, scored candidates, and Money Flow;
- exact target-byte recheck and diff-to-plan review for bugs, regressions,
  missing tests, maintainability, and concurrent-worktree drift.

The separate accessibility authority suite has the known shared-worktree 24/27
baseline (one capture-stack member drift and two `ui/radar.py` whole-file state
mismatches). This plan must not modify or weaken that frozen authority.

## Rollback and subsequent queue

Each phase is independently reversible by restoring only its named production,
test, contract, and documentation hunks. No artifact rewrite or service action
is part of rollback.

After 4M-4P, the next reviewed plan is:

1. **Phase 4Q:** Analyst Views scored grid, after freezing the per-ticker
   analyst-provider fan-out and default-detail behavior.
2. **Phase 4R:** Sector Rotation candidate mapping, after freezing its cached
   per-ticker sector-provider fan-out and partial-state selection behavior.
3. **Phase 4S:** US Screener public-projection decision; the current scored feed
   is insufficient for regime/counts, stop, size, technical breakdown, and
   anti-example fields, so implementation remains NO-GO until that contract is
   reviewed.

## Implementation receipt

Phase 4M moved only the standalone US Options candidate grid to one strict
scored-feed snapshot. Phase 4N moved only the ranked half of Industry Roles
candidate seeding to one strict ranked-feed snapshot while retaining X-only
partial generation. Phase 4O moved only the scored block in Options Cockpit
quick picks to one strict scored-feed snapshot. Phase 4P made the Streamlit
user unit require and start after the loopback API user unit.

All three UI changes were implemented red-first. Their focused suites pass
4/4 each; IV passes 15/15, Industry Roles 8/8, Options Cockpit display 19/19,
backend boundary 13/13, navigation 56/56, fixtures 26/26, deployment 18/18,
Docker runtime contract 11/11, and API/OpenAPI 44/44. The complete `make test`
run exited 0. Compile, tabnanny, Python 3.10 AST, shell syntax, and scoped
whitespace checks also pass.

Fixture verification exposed one deterministic harness gap: a newly visible
strict-feed candidate reached the retained local IV-percentile calculation.
The fixture now patches that existing local computation deterministically;
the exact zero-mutator authority was not weakened. Final review found no
unexplained scope drift, local candidate fallback, request multiplication, or
raw client-reason disclosure.

The ranked, scored, and Money Flow artifacts remain byte-identical at
`ca85c803...b5ea8b5ea`, `6af37543...1cff57b99`, and
`96ed8334...b3961731`. The API unit is byte-identical at
`1708a82b...78786`. No endpoint, DTO, OpenAPI, provider, writer, mutation,
dependency, Compose, credential, pull, commit, push, service restart, or
deployment action was added. Whole Industry Roles mutation migration remains
NO-GO for the previously recorded atomicity, authentication, concurrency,
idempotency, audit, and recovery blockers.
