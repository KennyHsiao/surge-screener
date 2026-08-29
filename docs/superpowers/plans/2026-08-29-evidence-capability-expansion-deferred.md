# Evidence Capability Expansion — Deferred Plan

## Document Info

| Field | Value |
|---|---|
| Version | v0.1 |
| Status | `DEFERRED — DO NOT IMPLEMENT` |
| Owner / approver | Repository maintainer |
| Audience | Maintainers, scoring/data engineers, reviewers, and 7F operators |
| Related baseline | `2026-08-21-promotion-reachability-shadow.md` |
| Traceability | `2026-08-29-evidence-capability-expansion-deferred.traceability.yaml` |

## Decision

Record lawful evidence-capability expansion as a future work package. It is not
an active release gate and does not block frontend/backend separation, UX-1B,
UX-2, UX-3, or UX-4.

Implementation may begin only after the maintainer records that at least one of
these predecessor workstreams has an accepted closure:

1. the frontend/backend separation workstream, for its separately accepted
   current-main scope; or
2. the UI/UX redesign workstream, for its separately accepted current-main
   scope.

After that closure, the maintainer must explicitly authorize re-entry. Passage
of time, another zero-pick EOD, or a Stage 7 `PASS_NOOP`/`PASS_UPDATED` does not
activate this plan. A plan draft, partial phase, baseline-only review, or
unverified implementation is not a qualifying closure.

## Context and Baseline

The promotion-reachability release is already complete. The latest retained
full-score cohort at planning time is `2026-08-27`: 25 scored candidates, zero
remaining rows, `unsupported_credit_count=0`, threshold 65, and maximum
supported/adjusted ceiling 50. Its state is truthfully `not_reachable`.

This plan records the current structural 15-point capability gap. Activation
must recalculate the gap against the then-applicable existing promotion
threshold, including the unchanged 72-point regime threshold when it applies.
It does not require or promise a confirmed pick. Organic confirmed picks and
Stage 7 updates remain non-blocking operating observations.

## Glossary

- **Evidence capability:** a versioned, testable contract proving that a score
  input can be obtained, attributed, validated, and used within its permitted
  rights and freshness window.
- **Lawful source:** a source whose access method, licence or terms, retention,
  attribution, redistribution, and credential handling have been reviewed and
  recorded. This plan does not declare any provider lawful in advance.
- **Supported ceiling:** the maximum score justified by available evidence under
  the existing rubric, caps, vetoes, threshold, and regime multiplier.
- **Unsupported credit:** awarded score above the evidence contract's supported
  maximum.

## Goal and Success Metrics

Increase the evidence-supported adjusted ceiling from the current 50 to the
then-applicable existing promotion threshold, currently 65 and 72 when the
unchanged regime rule applies, using real, attributable facts and deterministic
contracts.

Success requires all of the following:

- every enabled source has a recorded rights/security decision and stable owner;
- complete deterministic candidate fixtures reach the applicable existing
  65/72 thresholds under the unchanged scoring policy;
- the first eligible natural cohort reports
  `candidate_adjusted_ceiling_max>=threshold`, `unsupported_credit_count=0`,
  and no unknown contract reason;
- provider absence, staleness, malformed payloads, and revoked authorization
  produce zero credit or `unknown`, never guessed evidence;
- Analytics finishes with zero BLOCK and preserves last-known-good state on any
  build, gate, persistence, or deployment failure;
- no confirmed-pick count is required for release acceptance.

## Scope

### In Scope

- rebaseline current-main dimension ceilings, missing reasons, and provider
  availability after the predecessor workstream closes;
- rank the smallest evidence bundle capable of closing the verified 15-point
  gap without changing scoring policy;
- assess candidate sources or deterministic detectors for technical patterns,
  structured catalysts, sentiment, institutional activity, sector/market
  context, options flow, and analyst evidence;
- add only separately approved, versioned evidence contracts, provenance,
  freshness, and fail-closed validation;
- extend deterministic tests, Analytics projection/checks, deployment gates,
  and one natural EOD verification record.

### Out of Scope

- lowering the 65/72 thresholds or changing weights, caps, vetoes, DD rules, or
  the regime multiplier;
- granting credit from model prose, unverified inference, missing data, or a
  provider name without fact-level evidence;
- scraping against provider terms, using unapproved paid data, redistributing
  restricted payloads, or storing credentials in reports/evidence;
- fabricating or backfilling picks, ledger rows, reports, receipts, or returns;
- manually dispatching a producer to manufacture natural evidence;
- changing UI/UX, public/private API boundaries, schedules, or Stage 7 as part
  of this work package.

## Requirements

- `REQ-001` — The plan MUST remain inactive until one predecessor closure and a
  separate maintainer re-entry authorization are recorded.
- `REQ-002` — Activation MUST start with a current-main baseline and a ranked
  minimum-capability gap analysis; the 2026-08-27 ceiling MUST NOT be treated as
  a permanent implementation input.
- `REQ-003` — Every new capability MUST emit a versioned fact-level contract
  with source ID, observation/as-of time, freshness, input values, validation
  result, supported maximum, and explicit missing reasons.
- `REQ-004` — Enabled capabilities MUST raise the supported adjusted ceiling to
  the applicable existing 65/72 promotion threshold without altering the
  existing scoring policy.
- `REQ-005` — Missing, stale, malformed, unavailable, unlicensed, or
  unauthorized evidence MUST fail closed to zero credit or `unknown`.
- `REQ-006` — Release evidence MUST prove zero unsupported credit, zero BLOCK,
  transactional last-known-good preservation, and truthful zero-pick handling.
- `CFR-001` — Each external source MUST have an approved record covering access
  rights, permitted use, retention, attribution, redistribution, rate limits,
  cost owner, and revocation behavior before implementation.
- `CFR-002` — Credentials and private/account-bearing payloads MUST NOT appear in
  reports, logs, evidence artifacts, Analytics, commits, or UI/API responses.
- `CFR-003` — Existing thresholds, weights, caps, vetoes, DD rules, schedules,
  picks, ledger history, and Stage 7 contracts MUST remain unchanged.
- `CFR-004` — Provider calls MUST be bounded and observable; failure MUST retain
  the exact prior published generation and authoritative Analytics state.

## Acceptance Criteria

- `AC-ECE-001`: Given neither predecessor is closed, when implementation is
  requested, then work remains blocked and no runtime or provider change occurs.
- `AC-ECE-008`: Given a qualifying predecessor closure and explicit re-entry,
  when planning resumes, then the current main/7F dimension ceilings, threshold,
  missing reasons, source availability, and policy hashes replace the historical
  planning baseline before a capability bundle is selected.
- `AC-ECE-002`: Given a proposed source, when its rights/security record is
  missing, rejected, expired, or revoked, then the source cannot contribute
  evidence or score.
- `AC-ECE-009`: Given any enabled source, when reports, logs, Analytics,
  commits, artifacts, and UI/API projections are inspected, then no credential,
  restricted payload, or private/account-bearing value is present.
- `AC-ECE-003`: Given valid evidence, when its capability manifest is built,
  then every awarded maximum traces to concrete fresh facts and the manifest is
  deterministic for identical inputs.
- `AC-ECE-004`: Given missing, stale, malformed, or tampered evidence, when the
  scorer and reachability diagnostic run, then the dimension receives no
  unsupported credit and records the exact reason.
- `AC-ECE-005`: Given the approved minimum capability bundle, when the existing
  scoring contract computes its maximum, then adjusted ceiling reaches the
  applicable existing 65/72 threshold with weights, caps, vetoes, thresholds,
  and multiplier unchanged.
- `AC-ECE-006`: Given implementation and deployment success, when the first
  eligible natural EOD is ingested, then the cohort is complete, has zero
  unsupported credit and zero BLOCK, and does not require a confirmed pick.
- `AC-ECE-007`: Given any build, gate, provider, persistence, or deployment
  failure, when the transaction exits, then generation, DB, Parquet, checks,
  terminal evidence, picks, and ledger remain at their last-known-good state.

## Deferred Implementation Checklist

- [ ] `IMPL-001` — Record predecessor closure, re-entry authorization, current
  `main` SHA, 7F release identity, and fresh 25-row capability baseline.
- [ ] `IMPL-002` — Produce a source/detector option matrix with point delta,
  fact contract, licensing/security decision, cost, latency, coverage, and
  failure behavior; select the smallest approved bundle.
- [ ] `IMPL-003` — Define versioned evidence schemas and deterministic adapters
  or detectors for only the selected capabilities.
- [ ] `IMPL-004` — Integrate through the existing evidence-ceiling and scoring
  contracts without changing policy constants.
- [ ] `IMPL-005` — Persist provenance and capability summaries in candidate
  snapshots and Analytics without exposing restricted data or credentials.
- [ ] `IMPL-006` — Add fail-first contract, boundary, tamper, stale, outage,
  licensing-disable, non-interference, rollback, and secret-scan regressions.
- [ ] `IMPL-007` — Complete focused/full tests, blocker review, PR, deployment,
  7F verification, and one natural EOD release record.

## Verification Specification

| Test | Proves |
|---|---|
| `TEST-001` | Re-entry remains blocked until exactly documented predecessor and maintainer gates pass. |
| `TEST-008` | Re-entry replaces the historical baseline with current main, 7F, capability, threshold, and policy evidence. |
| `TEST-002` | Source-rights denial, expiry, or revocation disables credit without leaking restricted data. |
| `TEST-009` | Secrets, restricted payloads, and private/account values are absent from every durable and presentation surface. |
| `TEST-003` | Identical facts produce identical provenance, supported maxima, and adjusted ceiling. |
| `TEST-004` | Missing/stale/malformed/tampered evidence fails closed with zero unsupported credit. |
| `TEST-005` | The approved bundle reaches each applicable existing 65/72 threshold while policy constants remain byte-identical. |
| `TEST-006` | Provider/build/gate/persistence failure preserves exact last-known-good artifacts. |
| `TEST-007` | A natural cohort is complete and truthful without requiring a pick or ledger mutation. |

## Risks and Controls

- **Licensing ambiguity:** no adapter work begins until the source record is
  approved; uncertainty is a blocker, not an implicit permission.
- **Score inflation:** credit comes only from the existing deterministic rubric
  and fact contracts; unsupported-credit zero remains a hard gate.
- **Provider concentration/outage:** select bounded fallbacks only when each is
  independently approved; otherwise fail closed.
- **Credential or private-data exposure:** use non-sensitive source IDs and
  metadata-only receipts, plus repository/artifact secret scans.
- **Natural-window delay:** scheduled Actions may start late. Use terminal state
  and the established recovery window; never substitute a manual run.

## Re-entry Review

Before implementation, review this document against current main. Resolve all
blocking drift in schemas, providers, score contracts, Analytics checks,
deployment, and predecessor status. If the minimum lawful bundle cannot reach
the applicable existing promotion threshold, stop and return for
product/provider selection; do not widen scope or change scoring policy
implicitly.

## Next Handoff

Current handoff: `DEFERRED`. Continue frontend/backend separation or UI/UX work
and ordinary non-blocking observations. On a qualifying predecessor closure,
route this plan through fresh blocker review before any Builder/Radar work.

## Change History

| Version | Date | Change |
|---|---|---|
| v0.1 | 2026-08-29 | Recorded the deferred lawful evidence-capability work package and explicit re-entry gates. |
