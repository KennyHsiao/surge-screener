# Implementation checklist: deterministic score-cap enforcement

## Document info

| Field | Value |
| --- | --- |
| Version | v1.2 |
| Status | Release verified on 2026-08-20 |
| Author | Codex |
| Audience | surge-screener maintainers and 7F operators |
| Prerequisite | `main@e4e9990`, 7F Analytics 72 PASS / 2 WARN / 0 BLOCK |

## Goal and scope

Prevent Stage 2's deterministic technical recomputation from erasing the
existing critical risk caps in the screener rubric. The producer and workflow
gate must agree on the same capped score contract before a candidate can reach
Layer 2.

In scope: the existing no-volume technical cap, sentiment/technical composite
cap, options/technical composite cap, incomplete-dimension downgrade, retention
of an LLM risk downgrade, explicit score-adjustment provenance, workflow gate
validation, regression tests, PR/deployment, and 7F acceptance.

Out of scope: changing score weights or thresholds; inferring options aggressor
data unavailable from the provider; creating/backfilling picks; relaxing any
gate; treating a valid zero-pick run as failure.

## Requirements and acceptance criteria

- **REQ-SCE-001**: A verified pattern with zero volume points MUST cap the
  deterministic technical score at 10 while retaining the raw component total.
- **REQ-SCE-002**: With technical `< 12`, sentiment `>= 12` MUST cap composite
  at 50 and options flow `>= 15` MUST cap composite at 55. Both rules may apply;
  the stricter result wins before the regime multiplier.
- **REQ-SCE-003**: A would-be `NEEDS_LAYER_2` row with at least two whole scoring
  dimensions in `data_missing` MUST be downgraded to `WATCHLIST`.
- **REQ-SCE-004**: Finalization MUST NOT promote either an explicit LLM risk
  downgrade (verdict below its own pre-normalized composite) or the structured
  `bearish_options_flow` veto. A verdict that merely matches a lower original
  score is not a veto. The structured veto MUST remain empty unless the source
  explicitly proves the rubric's sweep/aggressor condition; aggregate free-chain
  PCR alone is insufficient.
- **REQ-SCE-005**: `due_diligence_required` MUST equal
  `verdict == NEEDS_LAYER_2`; stale LLM values must not survive normalization.
- **REQ-SCE-006**: Every full-score row MUST expose the LLM score/verdict, the
  uncapped deterministic composite, and structured adjustment provenance. One
  shared pure contract validator MUST be executed by both offline regressions
  and the workflow gate and reject any inconsistent cap, verdict, or regime score.
- **REQ-SCE-007**: Deployment MUST preserve 7F service health and Analytics
  `72 / 2 / 0` before confirmed-picks / ledger work resumes.

Given a row that triggers a cap or downgrade, when Stage 2 finalizes it, then
the output records the pre-cap value and rule identifier and cannot be accepted
by the workflow with a higher score or verdict. Given an ordinary row, its
composite remains the sum of its seven post-technical-cap dimensions.

## Implementation checklist

- [x] **IMPL-SCE-001**: Add fail-first unit regressions for each cap, downgrade,
  ordinary no-cap path, and stale due-diligence flag.
- [x] **IMPL-SCE-002**: Extend the grounded technical breakdown with raw total
  and applied cap; keep the unchanged 10/8/9/3 rubric.
- [x] **IMPL-SCE-003**: Normalize whole-dimension missing data, compute composite
  caps before regime adjustment, retain risk downgrades, and emit adjustments.
- [x] **IMPL-SCE-004**: Add a shared pure full-score contract validator, call it
  from the Actions gate, and cover arithmetic/provenance tampering by mutation.
- [x] **IMPL-SCE-005**: Update operator documentation and skill journals.
- [x] **IMPL-SCE-006**: Run focused/full verification, diff and correctness
  review, PR/merge/deploy, and 7F acceptance.

## Traceability

| Requirement | Implementation | Verification |
| --- | --- | --- |
| REQ-SCE-001 | IMPL-SCE-002/004 | TEST-SCE-001, TEST-SCE-007 |
| REQ-SCE-002 | IMPL-SCE-003/004 | TEST-SCE-002/003/007 |
| REQ-SCE-003 | IMPL-SCE-003 | TEST-SCE-004 |
| REQ-SCE-004 | IMPL-SCE-003 | TEST-SCE-005 |
| REQ-SCE-005 | IMPL-SCE-003 | TEST-SCE-004/005 |
| REQ-SCE-006 | IMPL-SCE-002/003/004 | TEST-SCE-001/002/003/006/007 |
| REQ-SCE-007 | IMPL-SCE-006 | GitHub checks, deployment run, 7F health and Analytics evidence |

Test IDs:

- `TEST-SCE-001`: raw technical score above 10 with a pattern and zero volume is capped.
- `TEST-SCE-002`: low technical plus sentiment 12 caps composite at 50.
- `TEST-SCE-003`: low technical plus options 15 caps composite at 55; both caps choose 50.
- `TEST-SCE-004`: two missing dimensions prevent Layer 2 and clear DD required.
- `TEST-SCE-005`: a lower LLM risk verdict or structured bearish-options veto is never promoted.
- `TEST-SCE-006`: ordinary scores remain unchanged and have no adjustment.
- `TEST-SCE-007`: workflow source contains and exercises the deterministic cap contract.

## Affected files and verification

- `scripts/02_llm_score.py`
- `scripts/scoring_contract.py`
- `scripts/test_llm_score_progress.py`
- `.github/workflows/surge_screener.yml`
- `scripts/test_deploy_artifacts.py`
- `docs/confirmed-picks-ledger-operations.md`
- skill journals under `.agents/`

Commands:

```bash
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_llm_score_progress.py
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python scripts/test_deploy_artifacts.py
/Users/ken/Workspace/AI/surge-screener/.venv/bin/python -m compileall scripts/02_llm_score.py scripts/test_llm_score_progress.py
git diff --check
make PY=/Users/ken/Workspace/AI/surge-screener/.venv/bin/python test
```

## Risks and rollback

- Gate/producer drift: the workflow and offline mutation tests execute the same
  pure score-contract validator.
- Missing-data overcount: only exact seven-dimension tokens count; individual
  `technical:<input>` gaps do not represent a missing whole dimension.
- Unsupported bearish evidence: preserve an explicit LLM downgrade, but do not
  infer bid-side aggressor or real sweep premium from free chain aggregates.
- Rollback: revert the focused PR and redeploy; no report, pick, or ledger data
  is rewritten by deployment.

## Pre-implementation blocker review

- User intent and the discovered false-promotion path are covered: PASS.
- Existing weights, thresholds, and non-fabrication boundary are unchanged: PASS.
- Cap ordering is explicit (technical, composite, regime, verdict): PASS.
- Affected files, callers, verification, deployment, and rollback are known: PASS.
- Risk-veto behavior uses only existing LLM output when provider evidence lacks
- Risk-veto behavior requires original LLM score/verdict provenance to
  distinguish a true downgrade from a low-score verdict: PASS.
- Unresolved blocking questions: 0.

The user's instruction to review and continue authorizes this blocker repair
before the previously accepted confirmed-picks / ledger plan resumes.

## Post-implementation review

- Resolved: deterministic technical recomputation overwrote all composite caps.
- Resolved: preserving every lower LLM verdict would misclassify an ordinary
  low-score WATCHLIST as a risk veto after score recomputation.
- Resolved: a bearish-options veto could be ambiguous when the LLM's original
  score already implied WATCHLIST. The output now carries a closed structured
  veto ID, with prompt text explicitly rejecting free aggregate PCR as aggressor
  or sweep proof.
- Resolved: an inline workflow-only reconstruction had no executable mutation
  seam. Stage 2 tests and Actions now use the same pure contract validator.
- Actual diff versus plan: aligned. The added shared validator and LLM
  provenance fields implement REQ-SCE-004/006 and remove duplicate gate logic;
  no weights, thresholds, picks, ledger rows, providers, or schedules changed.
- Local review: zero remaining blocking/high/medium finding; intent alignment PASS.

## Release verification

- PR #29 merged as `fce31b8e783d501e4a86087a56f549c00c9c79a6`;
  deployment run `32210146401` succeeded.
- The final 7F runtime retained byte-identical scoring/workflow files through
  `main@9e97408`; Data Health completed at 72 PASS / 2 WARN / 0 BLOCK.
- Natural EOD run `32310484686` accepted all 25 rows through the shared score
  contract, with `remaining_unscored=0`; an independent 7F recheck also passed
  25/25.
- The run produced zero confirmed picks without changing weights, thresholds,
  or ledger contents. Detailed evidence is in
  `docs/confirmed-picks-ledger-release-evidence-2026-08-20.md`.

## Change history

| Version | Date | Change |
| --- | --- | --- |
| v1.0 | 2026-08-19 | Accepted after pre-implementation blocker review. |
| v1.1 | 2026-08-19 | Implemented, hardened through grounded review, and locally verified. |
| v1.2 | 2026-08-20 | Closed PR, deployment, 7F 72/2/0, and natural-EOD score-contract acceptance. |
