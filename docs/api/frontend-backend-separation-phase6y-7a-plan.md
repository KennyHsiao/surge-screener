# Phase 6Y-7A Industry Roles Mutation Boundary Plan

- **Status:** implemented and verified
- **Date:** 2026-08-06
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `frontend-backend-separation-phase6v-6x-plan.md`

## Prior-phase review

Phase 6V-6X has no unresolved blocking finding. The protected review-board
reader, private client, ranked consumer, and complete API suite pass 62/62
focused checks, and `git diff --check` is clean. Streamlit's bare-mode and
`use_container_width` warnings are pre-existing, non-blocking warnings.

One intentional gap remains from that phase: generation and review commands
still write local files. This plan closes that gap without weakening the
singleton-operator private-host trust model or changing public read routes.

## Objective and phase boundaries

1. **Phase 6Y — revision model:** give the complete Industry Roles review
   state one monotonic revision and strong ETag. Require `If-Match` for every
   remote mutation and expose stale-write conflict handling to the UI.
2. **Phase 6Z — durable transaction:** replace the two-file write sequence with
   one canonical aggregate, advisory locking, atomic replacement, durable
   idempotency receipts, bounded audit history, backup, explicit recovery, and
   crash-injection tests.
3. **Phase 7A — mutation API pilot:** expose authenticated generate/approve/
   reject/defer actions through one bounded API action resource, adopt it in
   Streamlit with no local mutation fallback, and place the canonical state on
   the release-independent writable runtime path.

The scheduled candidate pipeline also participates in the same storage
transaction. Otherwise a pipeline generation can race a UI review after the UI
writer has moved to the API. Other non-UI readers may keep using the existing
engine functions, which will project from canonical state once it exists.

## Domain and persistence decision

Industry Roles review state is one small bounded aggregate because these
invariants cross both legacy resources:

- approving a suggestion must update assignment and suggestion status together;
- every successful command consumes exactly one aggregate revision;
- a receipt and its business result must commit together;
- an audit record must never claim a transaction that did not commit.

The canonical file is `reports/industry_roles/review-state.json`. It contains:

```json
{
  "schema_version": 1,
  "revision": 12,
  "taxonomy_version": 1,
  "updated_at": "2026-08-06T02:00:00Z",
  "overrides": {"version": 1, "tickers": {}},
  "suggestions": {"generated_at": null, "suggestions": []},
  "receipts": [],
  "audit": []
}
```

Receipts store only the SHA-256 digest of the idempotency key and the canonical
request digest, not the raw key. Audit and receipt arrays are bounded. The
strong ETag is derived from the revision and a SHA-256 digest of the canonical
business state, so manual state edits cannot preserve an old validator merely
by leaving `revision` unchanged.

When canonical state is absent, reads seed an in-memory revision-zero view from
the existing override and suggestion files. GET remains side-effect-free. The
first successful mutation atomically creates canonical state. Once canonical
state exists, invalid canonical data fails closed; it must never silently fall
back to stale legacy files.

Transactions use a same-directory lock file, bounded `flock` acquisition,
validated regular files, a mode-0600 temporary file, file `fsync`, `os.replace`,
and parent-directory `fsync`. Before replacement, the previous valid canonical
state is atomically preserved as `review-state.json.bak`. Recovery from backup
is an explicit library/CLI operation that creates a new revision and recovery
audit entry; GET never performs repair. This is a compact snapshot aggregate,
not event sourcing.

## REST contract

### Existing read

`GET /api/v1/private/industry-roles/review-board` retains its existing response
body and route-level bearer security. An available response gains a required
strong `ETag` header and keeps `Cache-Control: no-store`. Unavailable state has
no usable validator.

### Action resource

`POST /api/v1/private/industry-roles/review-board/actions`

- Security: existing route-level `InternalServiceBearer`.
- Required headers: `If-Match: "<strong-validator>"` and
  `Idempotency-Key: <bounded-printable-value>`.
- Content type: `application/json`; redirects are not followed by the client.
- Request: a strict discriminated union with no unknown fields:
  - `{"action":"generate","tickers":["AAPL","MSFT"]}`
  - `{"action":"approve","ticker":"AAPL","primaryRole":"leader","secondaryRoles":[]}`
  - `{"action":"reject","ticker":"AAPL"}`
  - `{"action":"defer","ticker":"AAPL"}`
- Success: HTTP 200 `IndustryRoleMutationResult`, a new strong `ETag`, and
  `Cache-Control: no-store`. A replay returns the original result with
  `replayed: true` and the committed ETag.
- The idempotency lookup precedes the conditional revision check: the same key
  and same request can safely replay after an ambiguous response even though
  its original `If-Match` is now stale. The same key with a different request
  is HTTP 409.
- Missing `If-Match` is HTTP 428; stale/malformed/weak/multiple validators are
  HTTP 412; domain conflicts are HTTP 409; invalid input is HTTP 422; lock or
  state unavailability is HTTP 503; sanitized unexpected errors are HTTP 500.
- Every non-2xx body is an RFC 9457 problem. No response exposes filesystem
  paths, tokens, raw idempotency keys, stack traces, or source payloads.

This is an additive Richardson Maturity Model level-2 command resource. It does
not remove or rename a public route, change public envelopes, or introduce a
new credential type.

## Functional core and imperative shell

- `scripts/industry_role_store.py` owns strict canonical parsing, validators,
  locking, atomic persistence, backup/restore, receipt lookup, and transaction
  commit.
- `scripts/industry_roles.py` keeps deterministic taxonomy classification and
  review state transitions. Legacy command functions become compatibility
  shells over the shared store instead of direct `Path.write_text` writers.
- `api/industry_roles.py` projects canonical state when present, legacy state
  only before migration, and returns the available snapshot validator.
- `api/main.py` authenticates before parsing or mutation, maps known failures to
  RFC 9457, and returns the committed validator.
- `clients/private_api.py` validates the strong ETag and performs a single
  bounded mutation attempt with no automatic retry.
- `ui/industry_roles.py` sends a fresh idempotency key per user intent, uses the
  board ETag, invalidates its read cache after any ambiguous or completed
  attempt, and never falls back to a local writer.

## Deployment and data lifecycle

- systemd grants only the API service
  `ReadWritePaths=%h/apps/surge-screener/shared/industry_roles`; code and all
  other artifact paths remain read-only under the existing hardening.
- The deployment script creates the release-independent directory mode 0700
  and links each release's `reports/industry_roles` to it.
- Compose mounts one named/shared `industry_role_state` volume at
  `/app/reports/industry_roles` for both services. Streamlit requires read
  access for compatibility helpers but does not perform review-board writes.
- Rollout order is API/storage support first, then Streamlit consumer. Legacy
  resources are retained during this phase for revision-zero import and
  rollback; no destructive migration runs at deploy time.
- Rotation of the existing internal bearer credential remains unchanged.

## Blast radius and cascade analysis

| Level | Impact | Evidence and containment |
|---|---|---|
| L0 direct | store/engine, API models/router/OpenAPI, private client, Industry Roles UI, systemd/Compose/deploy docs and tests | Same bounded context; strict contract and focused tests |
| L1 consumers | candidate pipeline, trade-state builder, money-flow/universe loaders, fixtures/boundary inventories | Engine compatibility functions read/write through the store; static inventory tests prevent hidden UI writers |
| L2 operations | scheduled candidate service, analytics snapshots, downstream Today/Options views, release rollback | One shared lock/revision; persistent shared path; legacy files retained; backup/recovery drill |

Cascade scenarios covered explicitly:

1. scheduled generation versus UI review is serialized under one lock;
2. commit succeeds but HTTP response is lost: replay uses the durable receipt;
3. stale cached board attempts mutation: `If-Match` returns 412 and UI reloads;
4. crash before replace leaves the old canonical state intact;
5. crash after durable replace returns ambiguous failure but replay is stable;
6. invalid canonical state fails closed and explicit backup restore produces a
   new audited revision;
7. a new release cannot hide or reset state because the path is shared.

Weighted Ripple risk is **5.1/10 (medium)**: scope 8, break potential 3,
pattern deviation 3, coverage risk 3, reversibility 4. Verdict is conditional
GO only after the fail-first and deployment/crash checks below pass.

## Test-first verification matrix

1. Store: revision-zero import; deterministic strong ETag; strict state shape,
   size, type, symlink, and taxonomy checks; monotonic commits; stale revision;
   receipt replay/conflict; no raw keys; bounded histories; concurrent writers;
   failure before/after replace; backup; explicit restore; recovery after an
   invalid current file.
2. Domain: generation and approve/reject/defer invariants; approve is one
   aggregate commit; missing ticker/role/status conflicts; scheduled generation
   preserves reviewed state and uses the same lock.
3. API/OpenAPI: auth/host checks precede body mutation; strict action union;
   header requirements; 200/409/412/422/428/500/503 RFC 9457 mapping; ETag and
   no-store headers; replay; logs and bodies remain secret/path safe; static and
   runtime OpenAPI parity.
4. Client/UI: strict ETag parser; exact headers and URL; no redirect/env proxy;
   no automatic retry; bounded response/deadline; all failure mappings; cache
   refresh; no call to local generate/review writers; unavailable controls stay
   disabled.
5. Deploy: exact writable path, directory ownership/mode, release symlink,
   Compose volume on both services, no API port publication, and all existing
   hardening/credential checks remain.
6. Closure: changed-test subset, API/boundary/convergence/navigation/fixture
   suites, compile/OpenAPI/static/shell checks, complete `make test`, and
   `git diff --check`.

## Rollback and reconciliation

Application rollback removes UI mutation adoption and the action route while
retaining canonical state and its backup. The legacy files are not deleted.
Before re-enabling a legacy writer, an explicit reconciliation command exports
one validated canonical snapshot back to legacy format under the same lock;
automatic dual-writing is prohibited because it recreates the partial-commit
failure. Rollback must never delete `shared/industry_roles`.

## Blocking-issue review

- **Iteration 1:** rejected a narrow API wrapper around the existing override
  then suggestion writes. It could acknowledge a partial approval and could
  not make receipt/audit atomic. Resolution: one canonical aggregate, atomic
  replace, backup, and explicit restore.
- **Iteration 2:** rejected migrating only approve/reject/defer. The scheduled
  generator and UI generator touch the same suggestion state, so leaving either
  outside the lock permits lost updates. Resolution: include generate as an API
  action and move all compatibility writer entry points onto the shared store.

No blocker remains after those two reviews. Final verdict: **GO** for
Phase 6Y-7A, subject to the verification gates in this plan.

## Following queue

- **Phase 7B — canonical reader convergence:** move non-UI Industry Roles
  consumers off direct legacy-file reads and add an explicit, locked canonical
  export/reconciliation command.
- **Phase 7C — recovery operations:** add a dry-run status command, documented
  restore drill, retention/backup inspection, and deployment health evidence.
- **Phase 7D — legacy retirement gate:** after one verified operating window,
  inventory external consumers and decide whether legacy override/suggestion
  files can be archived; no deletion is authorized by this plan.

## Implementation closure

- Added the single canonical Industry Roles aggregate, strong revision-bound
  ETags, bounded advisory locking, mode-0600 atomic replace, parent/file fsync,
  previous-state backup, explicit audited restore, durable hashed idempotency
  receipts, and bounded audit history. Missing canonical state remains a
  side-effect-free revision-zero projection of legacy data.
- Added the authenticated action route and API draft `1.23.0-draft`. Authentication
  and conditional headers are checked before the bounded request body; exact
  generate/approve/reject/defer models and sanitized RFC 9457 failures cover
  409/412/422/428/500/503.
- Replaced every Industry Roles UI writer call with the fixed private client.
  It validates the board ETag, sends exactly one conditional/idempotent POST,
  clears cached state after every attempt, and has no local mutation fallback.
  The scheduled generator and compatibility commands use the same store lock.
- Persisted the aggregate outside releases. The hardened API unit receives one
  exact writable path, Streamlit receives the same path read-only, Compose uses
  a shared API-rw/app-ro volume, and deployment keeps the shared directory mode
  0700. Legacy sources remain untouched for initial import and rollback.
- Actual implementation matches the accepted scope. The only L1 production
  adjustment was passing paired content/reports directories through Trade State
  and the assignment snapshot builder; this was required to prevent custom
  runtimes from accidentally resolving the default canonical path and is
  explicitly covered by the plan's consumer-cascade scope.

Completion review fixed a non-regular-file descriptor leak, strengthened exact
receipt/audit validation, aligned the generate cardinality with the 64 KiB body
budget, and disabled empty generation. No blocking finding remains.

Verification passed: store 6/6, engine 8/8, Trade State 15/15, private API 8/8,
private client/UI 6/6, ranked UI 4/4, API 47/47, boundary 23/23, convergence
4/4, deploy 18/18, Docker static contract 11/11, navigation 66/66, UX contract
19/19, fixtures 26/26, Python compile and 3.10 AST, OpenAPI YAML, shell and
whitespace checks, and final complete `make test` with exit code 0. The Docker
CLI was not installed locally, so `docker compose config --quiet` could not be
run; the repository's Compose parser/static contract suite passed.
