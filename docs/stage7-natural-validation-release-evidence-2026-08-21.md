# Stage 7 Natural Validation Release Evidence — 2026-08-21

## Document Info

| Field | Value |
|---|---|
| Version | v1.0 |
| Status | Certified |
| Date | 2026-08-21 Asia/Taipei |
| Audience | surge-screener maintainers and 7F operators |
| Implementation PR | [#33](https://github.com/KennyHsiao/surge-screener/pull/33) |
| Final workflow fix | [#35](https://github.com/KennyHsiao/surge-screener/pull/35) |
| Natural run | [32375707387](https://github.com/KennyHsiao/surge-screener/actions/runs/32375707387) |
| Natural run head | `79404422d674f2d61558bd0dd44ff120faeb27d3` |

## Scope

This record closes the natural scheduled-observation gate for the hardened
Stage 7 `verify_returns` job. It certifies run-head provenance, ledger and alert
receipt integrity, pre-publication gating, exact-path publication, terminal
evidence, and continuity with the authoritative 7F Analytics state.

It does not claim that a forward-return cell or alert receipt changed during
this run. It does not manufacture a pick, ledger mutation, alert, or push race,
and it does not treat the workflow's temporary Analytics build as 7F authority.

## Release Lineage

- PR #33 merged as `6807b4c` and added the bounded evidence transaction.
- PR #34 merged as `ea5be50` and corrected GitHub's invalid job-level runner
  context. Deployment run
  [32349822555](https://github.com/KennyHsiao/surge-screener/actions/runs/32349822555)
  completed successfully.
- PR #35 merged as `79404422` and corrected the evidence-upload path. Deployment
  run
  [32349988546](https://github.com/KennyHsiao/surge-screener/actions/runs/32349988546)
  completed successfully.
- The workflow, Stage 7 evidence helper, publisher, and their three regression
  suites are byte-unchanged from the natural run head through
  `main@f20d93a`.

## Natural Scheduled Execution

GitHub schedules are not exact start-time guarantees, so acceptance uses the
actual job terminal. All local times below are Asia/Taipei.

| Event | Time / result |
|---|---|
| Declared schedule | `0 13 * * 1-5` (21:00 Asia/Taipei) |
| Workflow created | 2026-08-20 21:41:29 |
| `verify_returns` started | 2026-08-20 21:41:33 |
| `verify_returns` completed | 2026-08-20 21:42:17 |
| Trigger / head binding | `schedule`; exact run head `79404422...` |
| Job / steps | success; every executed Stage 7 step succeeded |
| Terminal verdict | `PASS_NOOP`; empty `errors` |

The delayed scheduler start is not a missed validation: the bounded job ran
naturally, reached a terminal result in 44 seconds, and retained its evidence.

## Artifact and Integrity Evidence

Artifact `stage7-evidence-32375707387-1` has artifact ID `9408938769`, 90-day
retention through 2026-11-18, and digest
`sha256:f274528f3408ca2aeaf2ee594b97292c09fc627f283b53ccf47939a202fb576c`.

| File | SHA-256 |
|---|---|
| `baseline.json` | `433a8b5672e9c0e160e8b735731c10546beea36d63f1a4131ddfea3c06b54849` |
| `prepublish.json` | `042f21f238ee5ef09493827acd0be09fab74bcae3a20676fc7d9c4d337413184` |
| `publish.json` | `a7b0470b46c2c8c187d7f4fd4d00ccac49571315eff726a4c5d5333ee89306a2` |
| `verdict.json` | `150c6ee7030060f2b9264c2cc0b1004254d04369e1c3785b6958ef2cc38f86d6` |
| `verify.log` | `2bd3e471f256f1360fc2e268d141eaa55aced735e57b27a87d8f7e0fc8ca4fb5` |

The baseline ledger contained one valid `MU` row dated 2026-05-05, with no
blank required fields, duplicate keys, or invalid keys. Before and after the
run, ledger bytes had the same SHA-256:
`76710220d29a011028c6db5345a42a02e5076d6ea5d2a2ccd779893b39016032`.

The repository alert receipt contained three entries. Before and after the
run, its bytes had the same SHA-256:
`a9c9c8d622ed0707b50084a56b72c216e709229ba40fff32e08ce94372f8e3d4`.
The gate returned `READY_NOOP`; `verify_updated_rows` was zero; the publisher
returned `nothing_to_commit` with zero attempts. No commit or push was needed.

## Criteria Summary and Traceability

Operating mode: Attest `AUDIT`, default integrity level 2. Overall verdict:
**CERTIFIED**. All 10 criteria pass, with 100% requirement-to-evidence
traceability and no open critical, high, or medium finding.

| Requirement | Implementation / evidence | Verdict |
|---|---|---|
| `REQ-S7N-001` | 30-minute bounded job; natural scheduled run terminal | PASS |
| `REQ-S7N-002` | Baseline binds event, schedule, run ID, attempt, and head SHA | PASS |
| `REQ-S7N-003` | Ledger schema, required fields, unique keys, and bytes validated | PASS |
| `REQ-S7N-004` | Verifier outcome and mutation count correlated before publish | PASS |
| `REQ-S7N-005` | Analytics and ledger gate runs before the publisher | PASS |
| `REQ-S7N-006` | Publisher allowlist is ledger plus canonical alert receipt only | PASS |
| `REQ-S7N-007` | No-op preserves exact ledger and receipt bytes | PASS |
| `REQ-S7N-008` | `PASS_NOOP` verdict and complete artifact retained | PASS |
| `REQ-S7N-009` | Positive, failure, concurrent append, and push-race paths have deterministic regressions | PASS |
| `REQ-S7N-010` | Temporary workflow Analytics is non-authoritative; current 7F health remains authoritative | PASS |

Focused release tests cover no-op, positive update, immutable-cell rejection,
step failure, dirty-runtime rebase, source-ref rejection, rebase conflict,
owned-stash cleanup, exact-path publication, and workflow structure. Organic
positive update and push-race branches were not forced in production.

## Authority Boundary

The canonical automatic no-picks alert receipt is the tracked
`reports/analytics_checks/no_picks_alerts.json` in the Stage 7 GitHub checkout.
That workflow is the only automatic path that invokes
`scripts/analytics_action_notify.py`, and it gates and publishes that exact
receipt together with the ledger.

The 7F release symlinks `reports/analytics_checks` to persistent
`shared/analytics_checks`. Deploy seeds that directory only when empty, while
Data Health refreshes checks but does not invoke the notifier. Its host-local
`no_picks_alerts.json` may therefore lag and is not a Stage 7 receipt-hash
oracle. If notification ownership moves to 7F later, the tracked and host-local
receipts must first be explicitly reconciled under a separately reviewed
migration; silently combining them could duplicate alerts.

## 7F Continuity

After the natural run, 7F remained healthy: API and Streamlit returned HTTP
200, the deployed ledger matched the run and current main at
`76710220...`, and authoritative post-ingestion Analytics remained 72 PASS,
2 WARN, and 0 BLOCK with `status=succeeded`. No pending Analytics transaction
backup was present. The job-local 54 PASS / 13 WARN / 0 BLOCK build was
correctly marked `authoritative_for_7f=false` and does not contradict this
state.

The two 7F WARNs remain truthful operating signals: the performance ledger is
stale and successful published zero-pick scans continue. They do not invalidate
the Stage 7 transaction or authorize a fabricated ledger row.

## Adversarial Probe Results

| Probe | Result |
|---|---|
| Scheduler starts after 21:00 | Closed by actual terminal identity and bounded duration. |
| Zero eligible return updates | Closed by explicit `PASS_NOOP` and byte identity. |
| Repository advances after the run | Closed: all six Stage 7 runtime/test files and ledger are unchanged through `f20d93a`. |
| 7F receipt differs from tracked receipt | Closed by the documented ownership boundary; 7F does not automatically invoke the notifier. |
| Temporary Analytics disagrees with 7F | Closed by explicit non-authoritative provenance. |
| Positive update or push race is absent naturally | Non-blocking; covered deterministically and must not be manufactured. |

## Next Handoff

Stage 7 natural validation is closed. Continue routine observation of future
organic forward-return updates and confirmed picks. A later natural
`PASS_UPDATED` adds operating evidence but does not reopen this release gate.
