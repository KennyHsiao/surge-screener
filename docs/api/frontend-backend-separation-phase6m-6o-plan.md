# Phase 6M-6O Frontend/Backend Separation Plan

- **Status:** implemented and verified
- **Date:** 2026-08-06
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `docs/api/frontend-backend-separation-phase6j-6l-plan.md`

## Objective

Determine whether any safe public read slice remains after the first 53
API-only slices before adding another endpoint:

1. **Phase 6M — residual gap inventory:** rebuild the source-to-consumer map for
   every remaining Streamlit filesystem, database, provider, and backend-module
   binding, including transitive `_shared` dependencies.
2. **Phase 6N — boundary/risk classification:** classify each residual read as
   public fixed artifact, private/Internal, provider/live, operational, or
   mutation-coupled; record writer atomicity, stale-write, identity/auth,
   credential, and arbitrary-query/path risks.
3. **Phase 6O — convergence and next-slice decision:** either accept one narrow
   fixed public projection for a later Phase 6P-6R implementation plan, or
   document that public read separation has converged and switch the next plan
   to identity/authorization plus mutation/concurrency architecture. Phase 6O
   does not implement an endpoint by assumption.

## Entry evidence

- The entry shrinking legacy inventory contains 62 direct `scripts.*`
  bindings across 20 UI modules. Thirty UI modules import `_shared`, and
  14 UI modules contain a `load_json` call; these counts include intentionally
  retained writers, providers, credentials, compatibility reads, and private
  operational state, so they are not themselves migration defects.
- The obvious residual surfaces are not automatically public-safe:
  - Trade State, Risk Guard, IBKR reconciliation, watchlists, ledger, and chat
    sessions contain position-bearing or user-private data.
  - Analytics exposes local DuckDB/table/query machinery and needs a fixed
    allowlist plus identity/authorization before any broader service boundary.
  - Industry Roles combines reads with non-atomic multi-file approval writes;
    publishing an initial snapshot without revision/conflict handling can cause
    stale overwrite.
  - Crypto Screener still lacks a stable producer/schema, so adding an endpoint
    would freeze a scaffold rather than a supported contract.
  - Schedules residual result readers are operational status/log/reflection or
    private ledger boundaries rather than generic public artifacts.
- Phase 6G-6L already removed the remaining clearly fixed public Knowledge
  Graph, theme-taxonomy, and roster presentation reads. Arbitrary files,
  details, SQL, provider execution, and writes remain explicitly denied.

## Phase execution

### Phase 6M — reproducible global audit

1. Re-run AST inventory over all `ui/*.py`, separating imports/calls by
   frontend presentation, fixed API client, local reader, provider, writer, and
   mutation/action role.
2. Trace each local reader through `_shared` and `scripts` to its source,
   consumers, sensitivity, producer/writer, configured runtime path, and
   deployment ownership.
3. Compare the result with the endpoint inventory, current OpenAPI surface,
   legacy-import allowlist, navigation pages, Docker/systemd path mappings, and
   all 53 API-only slice receipts. Correct stale counts or classifications;
   make no runtime behavior change in this phase.

### Phase 6N — risk and coupling matrix

1. For each residual source, record whether it contains positions, account or
   user data, credentials, prompts/logs/errors, arbitrary queries/paths, or
   provider-derived live state.
2. Record write topology: atomicity, symlink/runtime path behavior, concurrent
   editor risk, revision/ETag availability, idempotency, audit/recovery, and
   whether a read snapshot can later be written back.
3. Apply the public-read decision tree. Reject catalog/detail or generic-file
   designs where the current UI consumes one fixed aggregate. Defer any source
   whose safe projection or failure behavior is not fully known.

### Phase 6O — decision record and successor plan

1. Rank only remaining fixed, non-sensitive, bounded, useful presentation
   reads. A candidate must have a stable producer/schema, exact consumer,
   allowlisted DTO, resource caps, fail-soft semantics, and no stale-write
   hazard.
2. If one candidate passes, write and blocker-review a concrete Phase 6P-6R
   contract/client/consumer plan with affected files, tests, risk areas, and
   rollback. Do not implement it in Phase 6O.
3. If none passes, publish a convergence decision and make Phase 6P-6R an
   architecture plan for loopback identity/authorization, revisioned mutation,
   and atomic recovery before private/write boundaries move.

## Affected files

- Audit/decision documentation only:
  `docs/api/fastapi-endpoint-artifact-inventory.md`, this plan, one Phase 6O
  decision record, and a later Phase 6P-6R plan.
- Static audit tests may update expected shrinking counts only when the source
  inventory proves the change; no production API/UI/runtime file is planned to
  change in Phase 6M-6O.
- Durable receipts: `.agents/gateway.md`, `.agents/builder.md`, and one combined
  `.agents/PROJECT.md` row when this future audit batch is actually executed.

## Verification gates

- Reproducible AST counts and source-to-consumer ownership map.
- Endpoint inventory/OpenAPI/navigation/legacy-boundary parity.
- Explicit denylist review for paths, SQL, private positions, credentials,
  provider execution, logs, sessions, and writes.
- Two blocking-review iterations on the Phase 6O decision and any Phase 6P-6R
  successor plan.
- Documentation diff review and relevant static tests; no implementation claim
  or endpoint version bump from an audit-only batch.

## Blocking-issue review

No blocker prevents the audit itself after two review iterations.

- **Iteration 1:** rejected assuming every remaining direct binding is a public
  separation gap. The inventory must distinguish intended private/provider/
  mutation boundaries from fixed presentation reads.
- **Iteration 2:** rejected preselecting Industry Roles, Analytics, Crypto
  Screener, Trade State, Risk Guard, IBKR, ledger, or chat before their known
  schema/privacy/concurrency blockers are resolved. Phase 6O must be allowed to
  conclude that no safe public read remains.

Final verdict: **GO** for Phase 6M-6O as the next audit/decision batch only.

## Audit closure

- The AST inventory reproduced 62 direct bindings across 20 modules, 30
  `_shared` importers, 14 modules with 20 `load_json` calls, and 10 modules with
  19 direct filesystem/database-style calls. The earlier 15-module
  `load_json` entry count was stale and is corrected here; no runtime behavior
  caused the correction.
- The source-to-consumer and risk audit is recorded in
  `frontend-backend-separation-phase6m-6o-audit.md`. Private account/position
  state, arbitrary SQL/files, logs/sessions, live providers, job controls, and
  mutation-coupled state remain rejected.
- One narrow public read passed: the Sector Rotation page's fixed
  sector-to-theme drill projection from `content/theme_baskets.json`. Only
  theme names and parent SPDR ETF identifiers are useful to this consumer;
  tickers, descriptions, representative hints, root notes, and all producer
  behavior remain server-side.
- Two blocker-review iterations accepted the successor
  `frontend-backend-separation-phase6p-6r-plan.md`. No identity, authorization,
  revisioned mutation, provider execution, or deployment-topology change is
  required for that fixed release-owned read.

## Following queue

Phase 6P-6R is intentionally conditional on the Phase 6O decision: either one
reviewed narrow public read implementation, or identity/authorization and
revisioned-mutation architecture before any private or writable source moves.
