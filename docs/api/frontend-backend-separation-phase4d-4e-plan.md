# Phase 4D/4E Frontend/Backend Separation Plan

- **Status:** Reviewed; approved for execution
- **Date:** 2026-08-01
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Planning skill note:** the repository-requested Superpowers skills are not
  installed in this session. This plan applies the same required plan-review,
  fail-first, staged-execution, and verification gates directly, with Gateway,
  Builder, and Artisan guidance.

## Baseline review

Phase 4B/4C has no blocking regression at the Phase 4D entry gate:

| Gate | Result |
| --- | --- |
| AI Updates API-only/presentation closure | 17/17 passed |
| Crypto Universe API/client/page | 8/8 passed |
| Backend boundary | 8/8 passed |
| Native presentation components | 6/6 passed |
| Loopback API/OpenAPI baseline | 44/44 passed |
| Current real Crypto artifact | strict 527-row artifact remained available |

The API test needed permission to bind a random `127.0.0.1` test port; the
initial sandbox denial was environmental, and the identical authorized run
passed 44/44.

## Accepted scope and invariants

### Phase 4D — Market Thesis latest

1. Keep the existing fixed
   `GET /api/v1/market-context/market-thesis/latest` URL, loopback trust,
   fail-soft HTTP 200 unavailable envelope, no-store policy, deadline, no proxy,
   no redirect, and bounded retained response.
2. Replace `MarketThesisData`'s open compatibility shape with a strict public
   projection containing only the fields rendered by `ui/market_thesis.py` plus
   the provenance fields required to bind `meta.asOf` and `meta.generatedAt`.
3. Preserve resolver ordering exactly: filename date first, then ready over
   `regime_only` on a same-date tie.
4. Migrate only `_latest_forecast()` to the fixed client. Keep
   `validation_summary.json` and `regime_history.json` as explicit local sibling
   reads, and keep all writers, validation jobs, notification gates, and Today
   Decision consumers unchanged.
5. Preserve the current forecast presentation and unavailable copy; no local
   latest-forecast fallback is permitted after a server unavailable result or a
   client failure.

### Phase 4E — Reversal/Oversold snapshots

1. Keep the existing fixed Reversal and Oversold latest URLs and the same
   loopback/fail-soft transport contract.
2. Reversal publishes the minimal persisted discovery projection needed by the
   Radar source selector: bounded snapshot provenance and source-ordered unique
   ticker references. Provider-derived analyst, insider, option, and detail
   payloads remain backend-only because the UI recomputes the live dual read.
3. Oversold publishes the bounded latest-display projection used by the coiled-
   base tab: exact summary, validation headline, caveats, and table columns.
   Source diagnostics and unused candidate fields are projected out.
4. Keep Radar's live `reversal_radar.analyze_reversal`, Risk Guard and IBKR
   position data, provider calls, and session-state result lifecycle unchanged.
   Keep both Reversal/Oversold forward-validation summaries as local reads.
5. Server unavailable and client failure results are authoritative for each
   migrated snapshot. Neither consumer may read `latest.json` as a fallback.

## Gateway review

- **Versioning:** existing `/api/v1` paths remain. The response models narrow
  from open compatibility objects to allowlisted internal-UI DTOs. This is a
  behavior-breaking contract refinement, explicitly authorized by the accepted
  Phase 4D/4E plan; there are no existing HTTP clients for these three routes.
- **Inputs:** all three GET routes remain parameter-free; no filesystem key,
  path, URL, query, identifier, pagination, or mutation surface is added.
- **Errors:** expected artifact states remain sanitized HTTP 200 unavailable
  envelopes. Unexpected defects remain the existing RFC 9457-style sanitized
  500 response. UI/client results expose only closed reason codes.
- **Security:** the service remains loopback-only with peer/Host enforcement and
  no CORS origins. No credential, position, account, Risk Guard, private runtime
  path, or provider diagnostic is added. Public projections reduce the existing
  compatibility exposure.
- **Rate limiting:** no new rate limiter is introduced for the fixed internal
  loopback reads. Any future non-loopback deployment remains blocked on auth,
  perimeter, rate-limit, origin, and field-level review.
- **Latency/bounds:** Market Thesis and Reversal use 512 KiB client caps;
  Oversold uses 2 MiB. All keep the existing one-second overall deadline and
  250 ms connect/read/write/pool limits. No N+1 request is introduced.

## Affected files

Expected implementation scope:

- contracts/API: `api/models.py`, `api/artifacts.py`, `api/main.py`,
  `docs/api/quant-radar-v1.openapi.yaml`
- fixed clients/UI: `ui/_read_api.py`, `ui/market_thesis.py`, `ui/radar.py`,
  `ui/oversold_reversal_lane.py`
- focused/regression tests: `scripts/test_api.py`, new Phase 4D/4E focused test
  files, `scripts/test_ui_backend_boundary.py`,
  `scripts/test_dashboard_navigation.py`, `scripts/ui_ux_fixtures.py`,
  `scripts/test_ui_ux_fixtures.py`, and `Makefile`
- docs/receipts: endpoint inventory, user guide, implementation receipt, and
  required engineering journals/activity log

No dependency, Compose, deployment, environment, writer, provider, database,
authentication, mutation, or unrelated page file is in scope.

## Pre-change exact-byte receipt

These hashes freeze the shared dirty worktree inputs before the first plan/code
write. They are evidence only and are not instructions to restore from Git.

| File | SHA-256 |
| --- | --- |
| `api/models.py` | `b5b8518ae07e882eebaec65b918945d8f51afab555f347eedad516809b7b7dad` |
| `api/artifacts.py` | `58c2cec15ecad221fea866802dea4264f18f63e1432e44711af23da98441e154` |
| `api/main.py` | `c91cce9ad9240e13a5ef086fa82305b1575056a60bd12b29be9e6297e83b43a6` |
| `ui/_read_api.py` | `634aab9bb30b3b2f4dde0b416ad1b5b637ba1bd0f37f601cdf93e0cc02f3d1a5` |
| `ui/market_thesis.py` | `f3f557a353123f2a263293886d73447dc309de221131b5d33c2a9fb3959b6719` |
| `ui/radar.py` | `917a329ea8a8297cc29bed1f892c2133ce5934d643469b97df36ffe9216fcd1c` |
| `ui/oversold_reversal_lane.py` | `51d46ed0e4554731ef38dc41e92b127c14d71531ef94f50dc572f86e948cc5dc` |
| `scripts/test_api.py` | `bbe1f398c8b466116775169096c3d1ae0bca9230ff6b64dc76609141736d1267` |
| `scripts/test_ui_backend_boundary.py` | `6a4cee9c95eb69db2020ff1e09b9c40869c1c058430e4ee50a1bd53f034c4e09` |
| `scripts/test_dashboard_navigation.py` | `a455d7fa8db036a2fbfe144fa9bfdb4b44c5d8515279f979c1848b15a6fed333` |
| `scripts/ui_ux_fixtures.py` | `d6a162bed678b29e895da8bb0fa6301f360472d9a5794ad52e651e863d86ec7b` |
| `scripts/test_ui_ux_fixtures.py` | `5737f739e55a67ec6d53363e252e5c59a4ce110ed7a5dd1153ca56578c87844a` |
| `scripts/test_ui_ux_contract.py` | `9675f052ed7c35c7738893ffd00bf1feab86adf5a644a8fe759e70ee23d113d0` |
| `Makefile` | `2bab95c895b66459df287ad1d3a34a859639c9f111d4c464813a8e6d22d57bb0` |
| `docs/api/quant-radar-v1.openapi.yaml` | `8c93092f9656fa941d8024965661614f0e0bcd1cc12b6765ff1f8375fd76ae22` |
| `docs/api/fastapi-endpoint-artifact-inventory.md` | `ff7adcb0bdbf8c5d5287da32daafb74fd1dd93f108e01aec9d99d725547796b0` |
| `docs/USER_GUIDE.md` | `df51b382f37cd7a4e4cc03012409da1fcf95246cc782f01b8e308e6a9f9e8e94` |

The pre-change UX inventory is 27 pages, 28 unsafe-HTML sites, and 170
diagnostic candidates.

## Execution and verification gates

1. Add Phase 4D fail-first API/client/page/boundary/fixture tests; confirm the
   old compatibility/fallback implementation fails for the intended reasons.
2. Implement Phase 4D and run its focused suite, API/OpenAPI parity, real latest
   artifact validation, boundary, fixture, navigation, syntax, and whitespace
   gates. Do not start Phase 4E until they pass.
3. Add Phase 4E fail-first API/client/page/boundary/fixture tests and confirm the
   old local snapshot readers fail the API-only assertions.
4. Implement Phase 4E and run both strict real artifacts through the registry,
   plus focused client/page and preserved-provider boundary tests.
5. Update static OpenAPI and docs, bind any UX inventory change to an exact
   successor receipt, then run focused suites, `scripts/test_api.py`, UX
   contract/fixtures, navigation, compileall, tabnanny, dependency/source
   scans, diff whitespace, and complete `make test`.
6. Compare the final diff to this plan, review for runtime bugs, regressions,
   missing tests, maintainability, private-data exposure, and unexplained scope
   drift. Fix every blocking finding before completion.

## Execution receipt

Phase 4D and Phase 4E were implemented without divergence from the accepted
scope:

- Market Thesis latest now uses a strict public projection and fixed client.
  The existing date-first, ready-over-regime-only resolver remains unchanged;
  validation summary, regime history, writers, notification gates, and Today
  Decision remain local.
- Reversal publishes only bounded provenance plus unique source-ordered ticker
  references. Radar still performs its live Reversal/Risk Guard work and keeps
  provider, position, and session-state behavior unchanged.
- Oversold publishes only the bounded coiled-base summary, validation headline,
  caveats, and displayed table columns. Its forward-validation summary remains
  local.
- The static OpenAPI and generated schema both use version `1.8.0-draft` and
  are gated for exact Phase 4D/4E public field sets, required fields, closed
  nested objects, and key collection bounds.

Fail-first evidence confirmed that the old compatibility models, missing fixed
clients, and local latest readers failed the new contract/boundary assertions.
After implementation, the current persisted artifacts validated through the
strict registry: Market Thesis resolved the 2026-07-27 degraded range forecast,
Reversal exposed 69 ticker references for 2026-07-30, and Oversold exposed 260
bounded rows for 2026-07-30.

Final gates:

| Gate | Result |
| --- | --- |
| Phase 4D focused API/client/page | 7/7 passed |
| Phase 4E focused API/client/page | 7/7 passed |
| Backend separation boundary | 10/10 passed |
| API and generated/static OpenAPI | 44/44 passed |
| Dashboard navigation/contracts | 54/54 passed |
| UX fixtures | 26/26 passed |
| Native UX components | 6/6 passed |
| Complete repository test target | `make test` passed |
| Static gates | compileall, tabnanny, `git diff --check` passed |

The API and fixture suites require local loopback sockets. Their first sandboxed
runs were denied by environment policy; the identical authorized commands and
the final authorized `make test` run passed. Existing Streamlit bare-mode and
`use_container_width` deprecation warnings remain non-blocking and originate in
unchanged presentation paths.

The final review found no writer, provider, dependency, deployment, database,
authentication, mutation, or unrelated-page scope drift. A misleading shared
timestamp-parser name found during maintainability review was generalized; no
behavior changed.

## Next queued plan after Phase 4E

### Phase 4F — ranked/scored candidate consumer decomposition

1. Freeze the current ranked/scored artifact bytes, runtime-path semantics,
   route contracts, and every UI consumer. Build an exact field-use matrix for
   each consumer before choosing a public DTO; do not serialize the open source
   objects by reflection.
2. Review blockers before implementation: duplicated scored buckets, runtime
   path overrides, stale/empty semantics, candidate ordering, quote fallback,
   private LLM detail, mutation controls, and the risk of repeated requests on
   a single Streamlit rerun.
3. Define strict bounded ranked and scored presentation projections. Preserve
   the compatibility routes until their consumers and breaking-change policy
   are explicit, or narrow them only with a separately accepted contract
   amendment.
4. Adopt the first consumer as one vertical slice, provisionally the Today
   Decision candidate presentation, with at most one ranked and one scored
   request per rerun shared across its panels. No per-ticker HTTP request may be
   introduced.
5. Keep quote/provider fallback, candidate pipeline controls and writes,
   runtime-path mutation, Options Cockpit, Trade State, positions, and other
   candidate consumers outside the slice. Add fail-first API/client/page,
   dependency, fixture, and request-count tests before implementation.
6. Validate real ranked/scored artifacts, generated/static OpenAPI parity,
   unavailable/failure recovery, complete regressions, and actual diff-to-plan
   scope before calling Phase 4F complete.

If the consumer/field matrix shows that Today Decision cannot be bounded
without private detail or repeated reads, Phase 4F must stop after the audit and
select the lowest-coupling read-only consumer in a reviewed plan amendment.
