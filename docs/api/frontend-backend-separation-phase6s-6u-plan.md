# Phase 6S-6U Frontend/Backend Separation Plan

- **Status:** implemented and verified; former Phase 6V-6X gate resolved
- **Date:** 2026-08-06
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `frontend-backend-separation-phase6p-6r-plan.md`

## Objective

Close the public-read migration stage without inventing another endpoint:

1. **Phase 6S — post-6R baseline:** reproduce and freeze the remaining direct,
   transitive, filesystem, provider, private, operational, and mutation counts.
2. **Phase 6T — convergence guard:** document which retained boundaries are
   intentional and add static regression evidence that future removals shrink
   the inventory while new UI/backend bindings fail closed.
3. **Phase 6U — private-boundary entry criteria:** define the evidence and user
   decisions required before identity/authorization, revisioned mutation, or
   atomic recovery can be planned or implemented.

This is an audit/static-guard/documentation batch. It does not add an endpoint,
move private data, select an authentication mechanism, write a migration,
change deployment, or modify provider/mutation runtime behavior.

## Entry evidence

- Phase 6R leaves 61 direct `scripts.*` bindings across 20 UI modules, 30
  `_shared` importers, and 14 modules with `load_json` calls.
- The 54 accepted API-only slices cover the fixed public presentation reads
  currently proven safe. The remaining families contain private account or
  decision state, provider execution, commands/logs/auth, arbitrary data access,
  unstable producers, N+1 compatibility reads, or writable review state.
- The existing shrinking allowlist prevents new direct imports, but the audit
  narrative is not yet a single machine-checkable post-public-read baseline.
- Industry Roles demonstrates the next-stage minimum concurrency problem:
  multi-file direct writes, no revision/ETag, and no atomic recovery. Private
  IBKR/ledger/chat/analytics surfaces additionally require an identity and
  authorization decision before service-boundary implementation.

## Phase execution

### Phase 6S — baseline receipt

1. Re-run AST and dependency-closure inventory after Phase 6R and reconcile all
   counts with navigation, endpoint inventory, OpenAPI, Docker/systemd paths,
   and the 54-slice receipt.
2. Publish an exact retained-family table with consumer, source/capability,
   sensitivity, provider/writer, deployment ownership, and intentional-retention
   reason. Correct stale counts only from reproducible source evidence.
3. Record what was not found: no other fixed bounded public presentation read
   that can move without identity, concurrency, producer, or contract work.

### Phase 6T — convergence guard

1. Add or refine one static audit test that checks the post-6R counts and
   retained-family classification without duplicating the full import
   allowlist. It must permit inventory shrinkage and reject growth.
2. Keep `test_ui_backend_boundary.py` as the exact symbol allowlist authority;
   the convergence guard checks summary invariants and required deny families.
3. Verify no test locks private data into a future API, no fixture calls a real
   provider, and no frozen UX evidence is re-signed for an audit-only change.

### Phase 6U — next-stage entry criteria

1. Define decision inputs, not an auth implementation: deployment audience,
   user/process identity, trust boundary, roles/resource ownership, session or
   token lifecycle, CSRF/CORS implications, secret storage, and audit retention.
2. Define mutation preconditions: resource revision/ETag, conditional writes,
   idempotency, atomic multi-file commit, lock/lease behavior, crash recovery,
   audit trail, backup/restore, and conflict UX.
3. Rank private candidate families only after those inputs are supplied. The
   successor plan must ask for the material identity/auth choice before
   selecting or implementing a mechanism.

## Affected files

- Audit/architecture documentation, the endpoint inventory, one static audit
  test if needed, Makefile registration if a new test is created, journals, and
  one combined PROJECT receipt.
- No production `api/`, `ui/`, provider, source, writer, dependency,
  deployment, schedule, Compose, or systemd file is planned to change.

## Verification gates

- Reproducible 61/20 direct-binding, 30 `_shared`, 14 `load_json`, and 54-slice
  baseline or an explained source-derived shrinkage.
- Static guard proves additions fail and removals prompt baseline reduction.
- Endpoint/OpenAPI/navigation/deployment parity and explicit private/path/SQL/
  credential/provider/log/session/write denylist review.
- Two blocker-review iterations, documentation diff review, relevant static
  tests, `git diff --check`, and no runtime/version/slice increment.

## Blocking-issue review

No blocker prevents the audit/static-guard batch after two iterations.

- **Iteration 1:** rejected automatically choosing another endpoint or an
  authentication design. Phase 6M–6R found no second safe public read, and
  identity mechanism selection is a material user decision.
- **Iteration 2:** separated exact symbol authority from summary convergence
  evidence so the new guard cannot conflict with allowed inventory shrinkage or
  freeze implementation details unnecessarily.

Final verdict: **GO** for Phase 6S-6U after Phase 6P-6R verification closes.

## Implementation closure

- Reproduced and documented the 61/20 direct, 30 `_shared`, 14/20 `load_json`,
  10/19 direct I/O, and 54-slice post-public-read baseline.
- Added a summary convergence guard that permits shrinkage, rejects growth,
  preserves the exact allowlist as a separate authority, and checks retained
  private/provider/operational/mutation classifications and topology receipts.
- Defined identity/authorization and revisioned mutation entry criteria without
  adding a production endpoint or choosing an authentication mechanism.
- Phase 6V-6X review found a material blocker at this phase boundary: deployment
  audience and identity direction were not specified, while the repository had
  no reusable user identity/authorization perimeter. The later user decision
  and resolved implementation are recorded separately.

Verification passed: convergence guard 4/4, backend boundary 23/23, navigation
66/66, deploy 18/18, Docker 11/11, UX contract 19/19, Python/static/document
gates, `git diff --check`, and complete `make test` with exit code 0.

## Following queue

The user later selected a single human operator on a private host, and Phase
6V-6X implemented the protected read-only Industry Roles pilot. The successor
queue is Phase 6Y revision semantics, Phase 6Z durable transaction/recovery,
then Phase 7A mutation API adoption; no private write moves before those gates.
