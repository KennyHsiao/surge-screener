# Confirmed-Picks and Ledger Release Evidence — 2026-08-20

## Document Info

| Field | Value |
|---|---|
| Version | v1.0 |
| Status | Certified |
| Date | 2026-08-20 Asia/Taipei |
| Audience | surge-screener maintainers and 7F operators |
| Specification | `docs/superpowers/plans/2026-08-18-confirmed-picks-ledger-evidence.md` |
| Release PR | [#28](https://github.com/KennyHsiao/surge-screener/pull/28) |
| Natural EOD | [run 32310484686](https://github.com/KennyHsiao/surge-screener/actions/runs/32310484686) |
| Report commit | [`6d18ebc`](https://github.com/KennyHsiao/surge-screener/commit/6d18ebc8c32e33af0d48429e3f327bf5db671bf6) |

## Scope

This record closes the release gates for `REQ-CPL-001` through `REQ-CPL-010`:
deployment identity, 7F health, natural EOD evidence completeness, final-report
allowlisting, zero-pick behavior, ledger integrity, and terminal ingestion.

It does not claim that a non-zero confirmed pick occurred. It does not create a
pick, backfill a ledger row, change a threshold or weight, or reinterpret a
successful zero-pick report as a failure.

## Release Lineage

- PR #28 merged as `e4e999092fc549426b4a43a6b74c3de877939d60`.
- Deployment run
  [32207560081](https://github.com/KennyHsiao/surge-screener/actions/runs/32207560081)
  completed successfully for that merge.
- Score-contract hardening PR #29 merged as
  `fce31b8e783d501e4a86087a56f549c00c9c79a6`; deployment run
  [32210146401](https://github.com/KennyHsiao/surge-screener/actions/runs/32210146401)
  completed successfully.
- The final runtime release was `main@9e97408e38e08f649866a8d197b3177367190b2c`,
  deployed by run
  [32215547957](https://github.com/KennyHsiao/surge-screener/actions/runs/32215547957).
- The nine affected workflow/scoring/report/ledger/status files on 7F matched
  `origin/main` byte-for-byte. No affected code changed between `9e97408` and
  the natural-EOD repository head.

## Natural Window Evidence

All times below are Asia/Taipei. Success is based on actual terminal state, not
the nominal schedule minute.

| Producer / gate | Actual interval | Evidence | Verdict |
|---|---|---|---|
| Data Health | 06:15:09–06:46:34 | systemd `success`, exit `0`; status `succeeded` | PASS |
| EOD `surge_scan` | 06:48:24–07:36:00 | GitHub job `96252274789`; every executed step succeeded | PASS |
| Theme Flow | 07:45:00–07:45:14 | systemd `success`, 35 themes, `as_of=2026-08-19` | PASS |
| Post-producer ingestion | 06:35:00–07:46:01 | systemd `success`; terminal verdict `state=PASS` | PASS |
| API / Streamlit | after promotion | `/healthz` HTTP 200; `/_stcore/health` HTTP 200 | PASS |

Post-ingestion promoted fixed source SHA
`fcb46795d3f165c753a84207050aa731740e462f`. Its allowlisted artifacts were:

| Artifact | Contract | SHA-256 |
|---|---|---|
| `reports/2026-08-19/summary.json` | `successful_zero_pick`, `total_confirmed=0` | `2e37925ba493f012d3afd4b11f9e2bf59124261190ddb77505aceaf8e13858bf` |
| `reports/candidate_scores/2026-08-19.json` | 25 scored of rank limit 25; 850 ranked; 0 remaining | `5c61110b962558bfd87ab008cf20b71f423346c87f0af4ed9fbbddeb705d4add` |

The promoted Analytics database SHA-256 was
`0746cb47826478e6a45a60a43f53b1d3f9f12df645f2195c969249d5d6d67616`.
Analytics completed with 72 PASS, 2 WARN, and 0 BLOCK. Candidate scores and the
daily report both advanced to `2026-08-19`; portfolio remained the correct
`not_configured` PASS state.

## Criteria Summary

Operating mode: Attest `AUDIT`, default integrity level 2.

| Verdict | Count |
|---|---:|
| PASS | 10 |
| PARTIAL | 0 |
| FAIL | 0 |
| NOT_TESTED | 0 |
| AMBIGUOUS | 0 |

Overall verdict: **CERTIFIED**. Requirement-to-implementation and
requirement-to-test traceability are both 10/10.

## Traceability Matrix

| Requirement | Implementation / runtime evidence | Test / demonstration evidence | Verdict |
|---|---|---|---|
| `REQ-CPL-001` | Stage 1 evidence producer; natural candidate snapshot | `TEST-CPL-001/002`; 25/25 natural rows independently revalidated | PASS |
| `REQ-CPL-002` | Stage 2 workflow fail-closed gate | `TEST-CPL-003`; natural Stage 2 completed only after the gate | PASS |
| `REQ-CPL-003` | Deterministic technical rubric and score contract | `TEST-CPL-001/004`; 25/25 natural score contracts valid | PASS |
| `REQ-CPL-004` | Final-report exact confirmed-ticker projection | `TEST-CPL-005`; DD returned 0 and summary contained exactly 0 picks | PASS |
| `REQ-CPL-005` | Deterministic invalid-report fallback | `TEST-CPL-005`; focused report suite 4/4 | PASS |
| `REQ-CPL-006` | Shared `ledger_store` lock and fsynced atomic replacement | `TEST-CPL-006/007`; append suite 7/7 | PASS |
| `REQ-CPL-007` | Latest-read merge and `(scan_date,ticker)` deduplication | `TEST-CPL-006/008`; return suite 2/2 | PASS |
| `REQ-CPL-008` | Pre-replace and replace-failure rollback | `TEST-CPL-007`; exact prior-byte assertion | PASS |
| `REQ-CPL-009` | Non-cancelling `surge-screener-performance-ledger` group | `TEST-CPL-009`; deployment suite 25/25 | PASS |
| `REQ-CPL-010` | Equal `finished_at` / `completed_at` terminal timestamps | `TEST-CPL-010`; run-status suite 9/9 | PASS |

Focused post-release audit reran 78 checks: hard filter 12/12, Stage 2 score
contract 19/19, report 4/4, append 7/7, return merge 2/2, run status 9/9, and
deployment contract 25/25. The complete repository suite had already passed on
the release diff before merge.

## Ledger and No-Picks Result

The EOD log recorded:

`[ledger] Successful run with zero picks; ledger unchanged`

Report commit `6d18ebc` added the dated report, candidate scores, and IV history;
it did not contain `reports/performance_ledger.csv`. Analytics therefore moved
the successful zero-pick count from 16 to 17 without adding or changing a
ledger row. The two remaining WARN checks are truthful operational warnings:
the last confirmed pick is still `2026-05-05`, and 17 successful published
scans have produced zero picks.

## Adversarial Probe Results

| Probe | Category | Result |
|---|---|---|
| `PRB-BND-001` | Boundary | Exactly zero picks leaves ledger bytes unchanged: closed. |
| `PRB-BND-002` | Boundary | Minimum accepted bounded cohort is exactly 25 and all 25 validate: closed. |
| `PRB-OMS-001` | Omission | Positive-pick production append did not occur naturally; deterministic allowlist/append tests cover it, and future natural observation remains non-blocking. |
| `PRB-OMS-002` | Omission | Stage 7 is a separate scheduled job; merge/no-overwrite tests cover its writer contract: closed. |
| `PRB-CTR-001` | Contradiction | Local window `2026-08-20` maps to UTC report date `2026-08-19`: specified and consistent. |
| `PRB-CTR-002` | Contradiction | Analytics WARN does not contradict publish readiness when BLOCK is zero: specified and consistent. |
| `PRB-IMP-001` | Implicit | GitHub started EOD 18 minutes late; the observer waited for the actual terminal job: closed. |
| `PRB-IMP-002` | Implicit | Concurrent report commits cannot change downloaded evidence after source SHA resolution: artifact blob and SHA-256 receipts closed the risk. |
| `PRB-NEG-001` | Negative | Malformed or incomplete technical evidence fails the workflow contract: closed by tests and natural gate. |
| `PRB-NEG-002` | Negative | Invented, duplicate, or count-mismatched final picks are rejected: closed by report tests. |
| `PRB-CNC-001` | Concurrency | Stage 6 and Stage 7 share a non-cancelling Actions concurrency group: closed. |
| `PRB-CNC-002` | Concurrency | Local ledger writes retain concurrent appends and deduplicate identical keys: closed. |

No critical, high, or medium probe remains open. The unobserved natural
positive-pick path is not a release failure because the specification expressly
allows zero picks and forbids manufacturing one.

## Specification Quality Feedback

The specification is verifiable, consistent, and traceable. Its test cases were
defined before implementation. No retrospective Gherkin was generated during
this release audit; `TEST-CPL-001` through `TEST-CPL-010` remain the canonical
scenario set.

Supply-chain evidence is limited to GitHub commit, PR, Actions, artifact hash,
and deployed-file hash provenance. `sbom_ref` and `signature_ref` are recorded as
skipped because the repository does not declare Sigstore/SBOM infrastructure as
a release requirement.

## Next Handoff

Release closure is complete. A future organic non-zero confirmed-pick day may
add production evidence for the positive append path, but it must not be forced
and does not reopen this release gate.
