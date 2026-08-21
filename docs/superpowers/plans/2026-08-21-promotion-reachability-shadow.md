# Promotion reachability shadow diagnostic plan

Status: 7F LEGACY SEMANTICS VERIFIED — TYPE FIX LOCALLY VERIFIED / NATURAL EOD PENDING

## Document info

| Field | Value |
|---|---|
| Version | v1.1 |
| Author | Codex |
| Reviewer | Repository maintainer |
| Audience | Maintainers and 7F operators |
| Related evidence | `docs/stage7-natural-validation-release-evidence-2026-08-21.md` |

## Goal

Explain whether the configured Layer 1 evidence can honestly reach the existing
promotion threshold. Publish the explanation as a shadow diagnostic without
changing any production score, verdict, pick, ledger row, threshold, weight, or
schedule.

## Scope

In scope:

- Add a versioned, fail-closed evidence-capability manifest for all seven score
  dimensions.
- Calculate each candidate's maximum supportable score from evidence available
  to Layer 1, then calculate the regime-adjusted ceiling.
- Detect LLM dimension credit above the declared evidence ceiling.
- Add a run-level `promotion_reachability_v1` summary to
  `scored_candidates.json` and dated candidate snapshots.
- Project the summary into the existing `candidate_scores` Analytics table.
- Add one Analytics check that is separate from the successful zero-pick streak.
- Classify snapshots without the new manifest as `legacy_unknown`.
- Add deterministic unit, integration, workflow-contract, and no-mutation tests.

Non-goals:

- Do not change the 65-point promotion threshold or the low-regime 72-point
  threshold.
- Do not change scoring weights, score caps, verdict logic, Layer 2, DD, picks,
  reports, the performance ledger, or Stage 7.
- Do not add provider credentials or expose whether a secret value exists beyond
  a non-sensitive source-capability status.
- Do not reconstruct precise evidence ceilings for legacy snapshots.
- Do not force a producer, manually append a ledger row, or backfill picks.

## Requirements

- `REQ-001`: A full-score candidate MUST carry a versioned manifest containing
  each dimension's supported maximum, non-sensitive source IDs, and explicit
  missing reasons.
- `REQ-002`: A complete full-score run MUST carry a shadow reachability verdict
  of `reachable`, `not_reachable`, or `unknown`, plus threshold and ceiling
  provenance.
- `REQ-003`: The diagnostic MUST report every awarded dimension score above its
  supported maximum without altering that score or the production verdict.
- `REQ-004`: Analytics MUST report reachability separately from successful
  zero-pick, missing, failed, unpublished, and unclassified run states.
- `REQ-005`: Legacy or incomplete evidence MUST fail closed to `unknown`; it MUST
  NOT be classified as reachable or unreachable.
- `CFR-001`: Given identical scoring inputs and LLM output, all existing score,
  verdict, routing, pick, and ledger-authority fields MUST remain identical.
- `CFR-002`: Diagnostics MUST contain no secret values and MUST perform no
  network, report, pick, or ledger writes.

## Acceptance criteria

### AC-PROMOTION-001 — deterministic boundaries

Given a complete shadow manifest whose adjusted ceiling is 64, when the
diagnostic is built against threshold 65, then its state is `not_reachable`.
Given an adjusted ceiling of 65, then its state is `reachable`.

### AC-PROMOTION-002 — current free-source ceiling

Given the current Layer 1 contracts with unsupported technical patterns, no
Layer 1 8-K or earnings-surprise contract, free social data, bounded free
options data, and available remaining sources, when the diagnostic is built,
then the ceiling is below 65 and every missing capability has a reason.

### AC-PROMOTION-003 — unsupported credit

Given a dimension score above its declared supported maximum, when the shadow
diagnostic is attached, then the dimension, awarded score, supported maximum,
and delta are recorded. The original score, composite, verdict, and DD routing
remain unchanged.

### AC-PROMOTION-004 — unknown is fail closed

Given a legacy row, malformed manifest, incomplete cohort, or non-full scoring
mode, when reachability is summarized, then the state is `unknown` and no
reachable or unreachable claim is emitted.

### AC-PROMOTION-005 — Analytics separation

Given a latest complete snapshot, when Analytics checks run, then exactly one
reachability check reports PASS or WARN independently of
`performance:no_confirmed_picks_streak`. Missing run telemetry remains unknown
in the no-picks check and is not inferred from reachability.

### AC-PROMOTION-006 — production non-interference

Given the same finalized candidate before and after shadow attachment, when
authoritative fields are compared, then scores, composites, score adjustments,
verdict, DD flag, ordering, and routing arrays are identical. No ledger or pick
writer is imported or called by the diagnostic module.

### AC-PROMOTION-007 — persisted provenance

Given a complete EOD score output, when the dated snapshot and Analytics export
are created, then schema version, state, threshold, maximum ceiling,
unsupported-credit count, and full diagnostic JSON remain queryable.

## Implementation checklist

- [x] `IMPL-001` -> `REQ-001`, `REQ-002`, `REQ-003`, `REQ-005`: add a pure
  `scripts/promotion_reachability.py` module with schema validation, per-source
  capability builders, candidate diagnostics, and run summaries.
- [x] `IMPL-002` -> `REQ-001`, `REQ-002`, `CFR-001`: attach shadow fields after
  the existing production score/verdict calculation in `scripts/02_llm_score.py`.
- [x] `IMPL-003` -> `REQ-004`, `REQ-005`: extend the existing candidate score
  Parquet projection and add one isolated Analytics check.
- [x] `IMPL-004` -> all requirements: add focused tests and register them in
  `Makefile`; update workflow/deployment contract tests only if persistence is
  not already covered by the existing candidate snapshot path.
- [x] `IMPL-005` -> `CFR-002`: update the operator documentation with shadow,
  legacy, warning-count, and rollback semantics.

## Test specification and traceability

| Test ID | Acceptance criterion | Required evidence |
|---|---|---|
| `TEST-001` | `AC-PROMOTION-001` | Exact 64/65 and 65/65 boundary assertions |
| `TEST-002` | `AC-PROMOTION-002` | Current free-source capability ceiling is below 65 |
| `TEST-003` | `AC-PROMOTION-003` | Unsupported credit is reported without mutation |
| `TEST-004` | `AC-PROMOTION-004` | Legacy, malformed, partial, and fast inputs are unknown |
| `TEST-005` | `AC-PROMOTION-005` | Reachability and no-picks checks coexist independently |
| `TEST-006` | `AC-PROMOTION-006` | Authoritative-field snapshot and no-writer import guard |
| `TEST-007` | `AC-PROMOTION-007` | Dated snapshot and Analytics round-trip preserve fields |
| `TEST-008` | `CFR-002` | Secret-pattern and forbidden-import/static checks pass |

## Verification

1. Run the new reachability tests fail-first.
2. Run focused scorer, persistence, Analytics store, Analytics checks, and
   deployment-contract suites.
3. Run Python syntax, whitespace, changed-file secret-pattern, and forbidden
   writer/import checks.
4. Run complete `make test`.
5. Compare the final diff to this plan and review runtime, data-loss,
   credential, compatibility, and maintainability risk.
6. Open a PR, merge only after checks pass, deploy through the formal workflow,
   and verify 7F code hashes and HTTP health.
7. Confirm report generation/current, published source artifacts, the performance
   ledger, and Stage 7 receipts are not changed by the shadow-only deploy. A normal
   Analytics rebuild is expected to change the DuckDB, `candidate_scores` Parquet,
   and checks bytes only for the added projection columns and reachability check;
   validate unchanged source-row counts/content, unchanged unrelated table schemas
   and rows, zero BLOCK, and no transaction/rollback residue. The rebuild
   MAY move the truthful total from `72 PASS / 2 WARN / 0 BLOCK` to
   `72 PASS / 3 WARN / 0 BLOCK` because the new independent reachability warning
   is expected.
8. Observe the next natural EOD for the first non-legacy shadow cohort. Do not
   claim `PASS_UPDATED` or a confirmed pick unless the ordinary pipeline creates
   one.

## Risks and rollback

- Repeated root diagnostics increase snapshot size. Keep the full diagnostic at
  the run root and only compact per-candidate capability data in candidate rows.
- Provider outages can lower a candidate ceiling. Distinguish unavailable from
  unknown and record only source IDs, never secret values.
- Legacy data cannot prove old capabilities. Preserve it and report unknown.
- Revert the feature commit and redeploy if the new projection or check causes a
  runtime regression. Existing score snapshots and ledger data require no
  migration or deletion.

## Blocking review

Review 1:

- User request coverage: complete. The plan diagnoses the structural promotion
  gap and continues without changing trading decisions.
- Affected files: scorer, a new pure diagnostic module, candidate score export,
  Analytics check, focused tests, Makefile, and operator documentation.
- Verification: exact boundaries, fail-closed legacy handling, persistence,
  Analytics separation, non-interference, focused/full tests, PR/deploy/7F.
- Main risks: production decision drift, false precision on legacy data,
  credential exposure, warning-count drift, and accidental ledger writes.
- Resolution: all are bounded by explicit non-goals and executable acceptance
  criteria. No unresolved blocker remains.

Review 2 (post-implementation):

- Resolved production-rounding drift at the `64.95 -> 65.0` boundary and reused
  the existing technical/composite cap contracts for the maximum ceiling.
- Resolved malformed source payloads and tampered candidate diagnostics so they
  fail closed to `unknown`, rather than producing a numeric zero or known state.
- Resolved Analytics NULL-count and all-history fallback errors; partial modern
  contracts, malformed summaries, and legacy tables now remain distinct and
  latest-cohort scoped.
- Corrected the deployment plan: published source artifacts, generation,
  performance ledger, and Stage 7 receipts must remain unchanged, while the
  Analytics DB/Parquet/check bytes may change only for the declared projection
  and independent check.
- Actual diff matches the accepted scorer, pure diagnostic, persistence,
  Analytics, test, and documentation scope. No threshold, weight, verdict,
  producer, pick, ledger, schedule, provider, API, or Stage 7 code changed.
- Codex CLI was attempted on bounded commits but produced no terminal verdict
  because the installed CLI rejected prompt+commit mode, then failed on its
  models-cache schema. Claude remains removed and Antigravity is unavailable;
  no external-engine result is counted as PASS.

## Local verification evidence

- Reachability unit suite: `13/13`.
- Scorer progress/non-interference suite: `20/20`.
- Candidate snapshot: `3/3`; Analytics store: `36/36`; Analytics checks:
  `21/21`.
- Complete repository gate: `make test` exited `0` with the new suite registered.
- Python compile, `git diff --check`, forbidden writer/import scan, and changed
  diff secret-pattern scan passed.
- Isolated rebuild of 100 retained candidate rows classified the latest
  2026-08-20 25-row legacy cohort as `WARN / PROMOTION_REACHABILITY_UNKNOWN`,
  with `contract_rows=0`; it did not invent a reachable or unreachable result.
- The stable-type follow-up redeploy/rebuild and the first natural non-legacy
  EOD cohort remain required runtime gates.

## 7F legacy runtime evidence and schema correction

- PR #39 merged as `0709610`; deployment run `32463432350` succeeded and five
  selected runtime/documentation hashes matched the 7F release.
- The 2026-08-21 manual Data Health run completed successfully with 220 source
  tickers, zero supplemental failures, and an atomic Analytics promotion. The
  expected result was `72 PASS / 3 WARN / 0 BLOCK`; the new check reported
  `PROMOTION_REACHABILITY_UNKNOWN` for the retained 25-row 2026-08-20 legacy
  cohort with `contract_rows=0`.
- Published generation/current, its content-tree hash, the performance ledger,
  the host-local receipt, and post-ingestion verdict/status bytes were unchanged.
  API and Streamlit remained HTTP 200 and no Analytics transaction residue was
  present.
- Direct schema inspection found that Parquet inferred all nine new columns as
  `INTEGER` while every legacy value was null. Although the check remained
  truthful, that would make the DuckDB contract change types when the first
  non-legacy cohort arrived. The follow-up fix declares stable nullable string,
  boolean, double, and bigint dtypes before writing Parquet.
- A fail-first regression reproduced the all-`INTEGER` schema. The corrected
  Analytics Store suite is `37/37` and proves identical types for an all-null
  legacy cohort and mixed legacy/current history. Analytics Checks remained
  `21/21`; Python compile, diff check, and the complete repository `make test`
  gate passed. Redeploy and a 7F Analytics rebuild remain required before the
  natural EOD gate.

## Change history

| Version | Date | Change |
|---|---|---|
| v1.0 | 2026-08-21 | Accepted shadow-only implementation plan |
| v1.1 | 2026-08-21 | Recorded implementation review, corrected rollout-state semantics, and local verification evidence |
| v1.2 | 2026-08-21 | Recorded 7F legacy verification and added the stable nullable-type correction gate |
