# Phase 6V-6X Private Read Boundary Plan

- **Status:** implemented and verified
- **Date:** 2026-08-06
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `frontend-backend-separation-phase6v-6x-decision-gate.md`

## Accepted deployment identity

The dashboard has one human operator on a private host. The host/VPN/SSH or
equivalent outer perimeter is responsible for exclusive human access and the
application principal is the fixed singleton `operator`. This does not make
every loopback caller trusted: Streamlit must present a separate, high-entropy
internal service credential to protected FastAPI routes.

Codex and X provider credentials are not application identity. The internal
credential is never returned by an endpoint, logged, committed, or accepted in
a query string. Public artifact routes remain unauthenticated and loopback-only.

## Objective

1. **Phase 6V — private deployment identity:** record the singleton operator
   trust model and add a rotatable internal service credential shared only by
   Streamlit and FastAPI.
2. **Phase 6W — protected contract:** add one fixed, bounded, read-only Industry
   Roles review-board projection with route-level bearer security, strict DTOs,
   sanitized errors, and no filesystem or credential disclosure.
3. **Phase 6X — consumer pilot:** make the Industry Roles page read taxonomy,
   approved roles, and suggestions only through the protected endpoint, with no
   local read fallback. Existing local generate/review commands remain in place.

This batch deliberately does not expose approve/reject/defer as network
mutations. `approve` currently writes two independent JSON resources and lacks
revision, conditional-write, idempotency, locking, transaction recovery, and an
audit ledger. Moving that writer before those guarantees exist would introduce
a partial-commit failure mode.

## Contract

- Route: `GET /api/v1/private/industry-roles/review-board`
- Operation: `getIndustryRoleReviewBoard`
- Security: route-level HTTP bearer scheme `InternalServiceBearer`; the token
  represents the Streamlit workload, while the outer private-host boundary
  represents the singleton human operator.
- Success: HTTP 200 `ArtifactAvailable` or fail-soft `ArtifactUnavailable`,
  always `Cache-Control: no-store`.
- Authentication failures: HTTP 401 RFC 9457 problem with
  `WWW-Authenticate: Bearer`; missing or invalid server credential
  configuration fails closed as HTTP 503. Bodies never distinguish submitted
  token values or expose configuration paths.
- Server errors: sanitized HTTP 500 RFC 9457 problem.
- Projection: fixed `operator`, taxonomy version, generated timestamp, bounded
  role id/name rows, bounded approved assignments, and bounded suggestions.
  Taxonomy descriptions, keywords, examples, paths, root notes, provider state,
  and credentials remain server-side.
- Limits: each source is size-bounded before JSON parsing; all collections,
  strings, tickers, identifiers, finite confidence values, status enums,
  uniqueness, and cross-resource role references are strictly validated.

## Credential lifecycle and deployment

- Local/Compose runtime uses `SURGE_INTERNAL_API_TOKEN`. The hardened systemd
  API unit instead receives only a `SURGE_INTERNAL_API_TOKEN_FILE` path from
  `LoadCredential`; no token value or path is accepted through HTTP.
- Tokens are bounded printable ASCII without whitespace and contain at least
  32 characters. Comparison is constant-time.
- The systemd deployment creates a mode-0600 environment file at
  `shared/runtime/internal-api.env` once with a cryptographically secure
  generator. Streamlit loads that dedicated environment file. FastAPI retains
  its clean `env -i` launch and receives the same file through systemd
  `LoadCredential`; neither service loads the application's broader `.env`.
- Compose injects `SURGE_INTERNAL_API_TOKEN` into both services. An empty or
  missing value leaves only the private route disabled; public health and read
  routes remain available.
- Rotation replaces that one environment file/value and restarts both services.
  Local development and tests can rotate the process environment without
  importing server implementation into the UI client.

## Affected files

- API contract/runtime: `api/models.py`, a new bounded Industry Roles reader,
  `api/main.py`, and `docs/api/quant-radar-v1.openapi.yaml`.
- Streamlit client/consumer: a separate `clients/private_api.py` so public
  client and frozen UI diagnostic closures remain unchanged, plus
  `ui/industry_roles.py`.
- Deployment: both systemd unit templates, `docker-compose.yml`,
  `scripts/deploy_test_server.sh`, and their static contract tests.
- Verification/receipts: focused API and UI tests, `scripts/test_api.py`,
  boundary/convergence tests if their exact inventories change, `Makefile`, API
  inventory, user guide, phase decision/closure documents, and journals.

## Test-first verification matrix

1. Reader tests: valid projection, valid missing optional initial state,
   missing taxonomy, unreadable/invalid JSON,
   oversized sources, strict shape/type/range/reference and uniqueness failures,
   no path/root-note leakage, and recovery on the next read.
2. Auth tests: missing configuration, invalid configuration, missing/malformed/
   wrong/correct bearer value, constant response shape, no token in response or
   logs, loopback/Host enforcement before route access, public-route stability,
   cache headers, and OpenAPI route-level security parity.
3. Client tests: correct header injection, no query credential, missing local
   credential, 401/503/non-JSON/oversized/invalid-envelope/deadline handling,
   strict metadata validation, and rotation between requests.
4. UI tests: protected API read with no local taxonomy/override/suggestion
   fallback; unavailable/auth failure disables the board and mutation controls;
   existing local generate/review commands and ranked-candidate API read remain.
5. Deployment tests: the same credential source reaches API and Streamlit,
   systemd file mode/generation contract, Compose propagation, no API port
   publication, and existing hardening/topology remain.
6. Closure: changed-test subset, complete `scripts/test_api.py`, boundary,
   convergence, deploy, Docker, navigation/UX contracts, complete `make test`,
   compile/static schema checks, and `git diff --check`.

## Risk and rollback

- **Risk:** credential mismatch makes the private board unavailable.
  **Containment:** fail closed only on the private route; show a bounded UI
  error; document same-value/restart rotation.
- **Risk:** strict projection rejects legacy malformed state.
  **Containment:** return unavailable without local fallback or mutation
  controls; log only source id and reason.
- **Risk:** accidental secret disclosure.
  **Containment:** header-only transport, no access log in systemd, no token
  logging, no response detail, `.env` excluded from build context, and tests
  scanning responses/logs/config templates.
- **Rollback:** remove the private route/client adoption and credential wiring;
  the local Industry Roles writer and source files are unchanged by this batch.

## Blocking-issue review

No blocker remains for this bounded read pilot after two iterations.

- **Iteration 1:** the user selected a single-user private host, resolving the
  deployment-audience decision. Review rejected treating loopback or provider
  login as caller identity and required a distinct service credential.
- **Iteration 2:** review rejected moving approve/reject/defer because approve
  performs a non-atomic two-file write. Scope was narrowed to authenticated
  read projection and fail-closed UI adoption; no state-changing code or data
  migration is included.

Final verdict: **GO** for Phase 6V-6X protected read pilot.

## Implementation closure

- Added the singleton `operator` trust model and a separate Streamlit-to-API
  bearer credential. Public routes remain loopback-only and unauthenticated;
  only the Industry Roles private route declares bearer security.
- Added a strict, bounded, path-free review-board projection and a fixed private
  client. Taxonomy is required; missing override/suggestion files are a valid
  empty initial state, while malformed existing state fails closed.
- Replaced the Industry Roles taxonomy/override/suggestion local reads with the
  protected endpoint and no fallback. Generate and approve/reject/defer remain
  local commands; unavailable or unauthenticated state exposes none of those
  controls.
- Wired one cryptographically generated mode-0600 credential file into the
  systemd services without weakening the API unit's clean `env -i` boundary;
  Compose injects the same explicit value into both containers.
- Actual implementation matches the accepted read-only scope. Verification
  additionally required synchronizing eight frozen OpenAPI version assertions
  and removing two obsolete Industry Roles local-read fixture counters; these
  are contract receipt updates, not production-scope expansion.

Verification passed: protected API 6/6, private client/UI 5/5, ranked UI 4/4,
API 47/47, backend boundary 23/23, convergence 4/4, deploy 18/18, Docker 11/11,
navigation 66/66, UX contract 19/19, fixtures 26/26, Python/OpenAPI/shell/static
checks, `git diff --check`, and final complete `make test` with exit code 0.

## Following queue

- **Phase 6Y — revision model:** define canonical aggregate revision/ETag,
  `If-Match`, conflict UX, and immutable operator audit fields.
- **Phase 6Z — durable transaction:** implement locking, idempotency receipts,
  atomic persistence or a recoverable journal, crash injection tests, backup,
  restore, and reconciliation for approve/reject/defer.
- **Phase 7A — mutation API pilot:** expose the reviewed Industry Roles action
  contract only after 6Y-6Z verification, then remove the UI's direct review
  writer binding.
