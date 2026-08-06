# Phase 4Z-5B Frontend/Backend Separation Plan

- **Status:** implemented, reviewed, and verified
- **Date:** 2026-08-03
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `docs/api/frontend-backend-separation-phase4w-4y-plan.md`

## Objective

Execute three narrow, independently reversible read-boundary slices by reusing
the existing strict Money Flow and Options Flow clients:

1. Phase 4Z makes embedded Options Cockpit Money Flow API-only and removes the
   final presentation-local Money Flow reader.
2. Phase 5A makes only the Schedules Options Flow result summary API-only.
3. Phase 5B makes only standalone Options Cockpit Options Flow quick picks
   API-only.

The Money Flow and Options Flow producers, artifact writers, API routes and
schemas, standalone Options Flow page, Stock Checkup lazy-tab gate, live option
chain, EDGAR action, watchlist/social quick picks, scored quick picks, other
Schedules result readers, mutations, and Trade State remain unchanged. No pull,
commit, push, deployment, service action, authentication change, dependency
change, artifact rewrite, or unrelated UI work is authorized.

## Entry baseline and frozen bytes

The Phase 4W-4Y receipt has no unresolved regression. Fresh entry suites pass:

- Money Flow 6/6
- Schedules candidate 5/5
- Options Cockpit scored 4/4
- Options Flow 10/10
- backend boundary 15/15
- navigation 59/59

The prior full receipt records API/OpenAPI 47/47, fixed read client 12/12,
deterministic fixtures 26/26, and complete `make test` exit 0.

Exact pre-change target hashes are:

- `ui/options_cockpit.py`: `e7cf3ebad86786c6372e0adc59616ef5ac517071ec07abe0768d416d6610ab7a`
- `ui/sys_schedules.py`: `b17eeb5b817d470c17406ac1aa564bb6060f2fe22c2cc1e34375ea3fd3ed7842`
- `ui/_read_api.py`: `340bb0b07255c6123a734746252ea2365acaeb4109a95f5ba4d0f79fc69fe11f`
- Money Flow suite: `0829fcdf3e28321c438763e903326d3f1bde86f748d6cf6345f235a34e2f461a`
- Schedules suite: `e2c0faacd171f39fc6a44ec0d49f0619bc1e08d489518c4577fb9638886c1edd`
- Options Cockpit scored suite: `9955319ff3db824431284b53a93ec82e964a61747cf90710ae8e61c0ce7ce015`
- Options Flow suite: `70fca604018af4bb6f041b47cb12f7218253603481883292004163092dbbc68c`
- backend boundary: `1060e558d8d709bc1fe7d86de8708f310d9f44f76dfa24ea3322fdc3cd330ab7`
- navigation: `1f9003f4bf8439fb7988bee1c6278bdca71e2efac90a525e41092f6cc9c148fd`
- fixture helper: `fe83442b92036bbff5a427a5e3363c879de9125cb1ca5992eb817585c3c969e6`
- fixture suite: `66c59c2efb2ce0297c962ceeee9bf06eff4e850292e553882168e4a31a5c42aa`
- `Makefile`: `25faec0e01cd55bfbae84e9137a58cf4bf6690789760b0a88570a7bbb1425e8c`
- user guide: `d02b2830896df3d9b6a53e2f921a0fe4f0168cdf32c8af77e6c0a40979c7b809`
- endpoint inventory: `bf9d981adf6c7fada57c20881d6fffa88af115ffa3f7d38a889549020bc9f896`

The selected source artifacts remain frozen at:

- Money Flow: `96ed833428bc08f4845f49d0d03bda5be651d8caad4d8e5c3f94eeb9b3961731`
- Options Flow: `4c389cf370f6ecb4ba5d3d2f697eb5b3691a431be48690790f78bd94bd527599`

Re-hash each shared target immediately before its first edit. Changed bytes
require re-review rather than overwrite.

## Source and impact trace

The existing strict Options Flow contract contains every selected consumer
field: root `generated_at`, `as_of`, `provider`, `universe_size`,
`min_notional`, `signal_count`, and source-ordered bounded `signals`; each
signal exposes `ticker`, `direction`, and `flow_score` plus its existing public
detail fields. Runtime validation enforces real dates/timestamps, closed fields,
unique tickers, non-increasing score order, and count invariants. The fixed
client validates provenance and metadata, retains its decoded-body cap, and has
immutable available, authoritative-unavailable, and failure outcomes with no
local fallback.

The selected presentation consumers are:

- `ui/options_cockpit.py::render_for()`, which currently reaches the local
  Money Flow artifact through `_render_external_confirmation()`'s implicit
  default;
- `ui/sys_schedules.py::_latest_options_flow_result()`, which needs only date,
  signal count, bullish/bearish counts, and the first five ordered tickers;
- `ui/options_cockpit.py::_watchlist_quickpick()`, which needs the first five
  ordered signal tickers, directions, and flow scores.

The existing Money Flow typed state already preserves the external-confirmation
future-row rejection, latest-row choice, three-day staleness rule, and fixed
unavailable/failure copy. No API, DTO, OpenAPI, registry, or client change is
needed.

## Blocking-issue review

No unresolved blocker remains after one review iteration.

- **4Z — GO, risk 3.6/10:** make the shared external-confirmation renderer
  require a typed state, load exactly once in both standalone and embedded
  entry points, and delete the now-dead local reader. Stock Checkup remains lazy,
  so no request occurs until its embedded cockpit tab actually renders.
- **5A — GO, risk 4.2/10:** available-empty must render an authoritative
  zero-signal summary instead of becoming “no data.” Authoritative unavailable
  and client failure keep distinct fixed copy and sanitized banner reasons.
  Cache one fetched result per visible selected result type so future duplicate
  Options Flow cards cannot create N+1 requests.
- **5B — GO, risk 4.5/10:** the Options Flow request is independent from the
  scored request. Either API can fail while watchlist, social, and the other API
  source still render. Available-empty is not a failure, and unavailable versus
  client failure uses distinct fixed safe notices without raw reason text.

No breaking route, data-loss path, credential exposure, provider migration, new
mutation, or unsafe side effect is part of the accepted scope. Overall weighted
risk is 4.2/10.

## UI state behavior

### Phase 4Z — embedded Options Cockpit Money Flow

`_render_external_confirmation()` accepts a required `MoneyFlowReadState`.
Both `render()` and `render_for()` load exactly one state and inject it. The
existing available, available-empty, unavailable, failure, future-row, and stale
row semantics remain unchanged. `_load_money_flow_artifact()` is deleted and no
presentation path reads `reports/money_flow/latest.json` locally. EDGAR remains
on-demand and independent.

### Phase 5A — Schedules Options Flow summary

`_latest_options_flow_result()` makes exactly one fixed client request and
returns the standard `(content, reason)` payload:

- available populated: preserve date, total signal count, bullish/bearish
  counts, source order, and top five tickers;
- available empty: render the date and authoritative zero counts with no failure
  banner;
- authoritative unavailable: render fixed “資料目前無法使用” summary plus the
  sanitized reason for the existing state banner;
- client failure: render fixed “服務目前無法使用” summary plus the sanitized
  reason for the existing state banner.

`render()` snapshots a selected result type at most once and reuses it across
duplicate visible cards. Other fetchers retain their current local boundaries.

### Phase 5B — standalone Options Cockpit Options Flow quick picks

`_watchlist_quickpick()` makes one existing Options Flow feed request beside its
one scored-feed request:

- available populated: preserve API order and render at most five direction and
  heat labels;
- available empty: render count zero without a failure notice;
- authoritative unavailable: preserve all other sources and append fixed
  “異常流資料目前無法使用” copy;
- client failure: preserve all other sources and append fixed
  “異常流服務目前無法使用” copy.

No raw reason is displayed and no local Options Flow fallback occurs. Embedded
`render_for()` does not call quick picks. Watchlist, social, legacy X, scored
feed, live chain, session handoff, and mutations remain unchanged.

## Execution steps

1. Add fail-first focused contracts for required typed Money Flow injection,
   Schedules Options Flow state behavior and duplicate-card request reuse, and
   Cockpit Options Flow independent partial states with no local fallback.
2. Phase 4Z: inject one typed Money Flow state in embedded mode, require state at
   the shared renderer, and remove the dead local artifact reader.
3. Phase 5A: replace only the selected Schedules local read and generalize
   visible-result caching without changing other fetchers.
4. Phase 5B: replace only the selected quick-pick local read with one fixed
   client call and independent safe notice.
5. Update exact boundary/navigation/source guards, deterministic fixtures,
   route counters, Make test inventory, endpoint inventory, user guide, and
   required skill/project receipts.
6. Compare the actual diff to this plan, review for bugs, regressions, missing
   tests, and maintainability, fix all blocking findings, then run focused and
   complete verification.
7. Audit remaining direct reads and record the concrete successor queue in the
   implementation receipt; completion reporting must include that next plan.

## Allowed implementation surfaces

- UI: `ui/options_cockpit.py`, `ui/sys_schedules.py`
- Focused suites: `scripts/test_ui_money_flow_api.py`,
  `scripts/test_ui_schedules_candidate_api.py`,
  `scripts/test_ui_options_cockpit_scored_api.py`, plus new focused Schedules
  Options Flow and Cockpit Options Flow suites when separation is clearer
- Exact contracts/fixtures: `scripts/test_ui_backend_boundary.py`,
  `scripts/test_dashboard_navigation.py`, `scripts/ui_ux_fixtures.py`,
  `scripts/test_ui_ux_fixtures.py`, `Makefile`
- Documentation/receipts: this plan, `docs/USER_GUIDE.md`,
  `docs/api/fastapi-endpoint-artifact-inventory.md`, and required
  Lens/Ripple/Gateway/Builder/Artisan/project journals

Any API schema/route/client change, producer, writer, Trade State, provider,
deployment, dependency, credential, unrelated page, mutation, or artifact edit
is unexplained scope drift and stops execution.

## Verification and rollback

Run new tests red-first and green after each phase, then Money Flow, Schedules
candidate, Options Cockpit scored, Options Flow, API/OpenAPI, fixed read client,
backend boundary, navigation, deterministic UI fixtures, deployment, Docker,
compileall, tabnanny, Python 3.10 AST, YAML/reference parity, whitespace,
frozen-artifact integrity, and complete `make test` gates. Report every check
that cannot run.

Each phase rolls back through only its named UI/test/doc hunks. The API,
producers, artifacts, providers, mutations, and sibling local readers remain
unchanged, so rollback needs no data migration or artifact rewrite.

## Subsequent queue to audit after Phase 5B

The post-implementation audit must re-enumerate remaining local presentation
reads before numbering the next phases. At minimum it must separately assess:

1. Trade State's multi-source aggregate, including privacy, ownership, write
   boundaries, and whether one narrow read can be separated safely.
2. Remaining Schedules local result summaries, ranked by reuse of an existing
   strict endpoint before any new API contract is proposed.
3. Remaining Options Cockpit local read-only presentation sources, excluding
   live providers, mutations, and deliberate user-triggered actions.

The post-5B audit found three independently reversible consumers that can reuse
existing strict clients without adding API surface:

1. **Phase 5C — Schedules Crypto Universe summary:** replace only
   `_latest_crypto_result()` with one existing strict Crypto Universe request,
   reuse one result across duplicate visible cards, and preserve every other
   result reader.
2. **Phase 5D — Schedules Theme Flow summary:** replace only
   `_latest_theme_flow_result()` with one existing strict Theme Flow snapshot
   request, reuse one result across duplicate visible cards, and leave analysis,
   refresh/status, providers, and mutations on their current boundaries.
3. **Phase 5E — Options Cockpit IV history:** replace the live cockpit's local
   `_load_iv_series()` and local artifact-backed percentile read with one
   existing strict per-ticker IV history request, then apply the existing pure
   percentile calculation to validated points. Preserve the demo provider,
   live option chain, 15-minute cockpit cache, standalone/embedded behavior,
   and all sibling reads/actions.

Trade State remains deferred: its builder joins ranked candidates, legacy
social, Options Flow, position-bearing Risk Guard, Money Flow, theme baskets,
and industry roles, then also feeds snapshot writes. It needs a separate
aggregate privacy, ownership, source-coherence, authorization, and mutation
review. The Phase 5C-5E queue requires a fresh plan and blocking review; this
receipt does not authorize those successor changes.

## Implementation and verification receipt

Phase 4Z-5B matches the accepted production scope. Embedded and standalone
Options Cockpit now inject exactly one typed Money Flow state into the shared
external-confirmation renderer; the final local Money Flow presentation reader
is removed. Schedules now reads its Options Flow result through the existing
strict feed and reuses one selected result per visible result type. Standalone
Options Cockpit quick picks now read one existing strict Options Flow feed while
preserving watchlist, social/legacy X, scored candidates, partial-state copy,
live chain, EDGAR, session handoffs, and mutations. No API, DTO, registry,
OpenAPI, client, provider, writer, dependency, deployment, or artifact code was
changed.

Red-first evidence failed on all three pre-existing local boundaries, then the
focused suites passed after implementation: Money Flow 6/6, Schedules Options
Flow 4/4, Schedules candidate regression 5/5, Cockpit Options Flow 4/4, and
Cockpit scored regression 4/4. Actual-diff review found no production scope
drift. The deterministic fixture update is an explained verification-harness
change: Stock Checkup now expects one embedded Money Flow API call, standalone
Cockpit expects one Options Flow API call, and the old local JSON counter/read
is removed. The initial fixture/read/deploy attempts inside the filesystem
sandbox hit expected socket or low-level permission errors; their authorized
sandbox-external reruns passed and no test was waived.

Final gates pass: API/OpenAPI 47/47 with real Uvicorn, fixed read client 12/12,
Options Flow page 10/10, Options Cockpit display 19/19, backend boundary 16/16,
navigation 60/60, deterministic fixtures 26/26, deployment 18/18, Docker 11/11,
and complete `make test` exit 0. Compileall, tabnanny, Python 3.10 AST,
whitespace, and frozen-artifact integrity also pass. The ranked, scored, Money
Flow, and Options Flow artifacts remain exactly:

- `ca85c80320db03bedb2175f12f54a7c5d08fe1671fc4da7255b16e1d1ea8b5ea`
- `6af375439dd470ea6f3c0bd985b3bfc16cbef62ae56791f270db36a1cff57b99`
- `96ed833428bc08f4845f49d0d03bda5be651d8caad4d8e5c3f94eeb9b3961731`
- `4c389cf370f6ecb4ba5d3d2f697eb5b3691a431be48690790f78bd94bd527599`

No pull, commit, push, deploy, service action, authentication, dependency,
provider, writer, or artifact rewrite was performed. The inventory is now 27
narrow API-only slices, not full frontend/backend separation.
