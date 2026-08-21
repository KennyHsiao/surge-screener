# Validation Release-State Evidence — 2026-08-21

## Document info

| Field | Value |
|---|---|
| Version | v1.0 |
| Status | Certified |
| Date | 2026-08-21 Asia/Taipei |
| Audience | surge-screener maintainers and 7F operators |
| Scope | Full-test baseline, R3 natural validation, and post-producer transaction releases |

## Conclusion

The six audited plans are release-complete. Their stale pending labels were
documentation drift, not an open runtime defect. Each closure below is backed
by a merged PR plus deployment or bounded 7F execution evidence. The original
R3 verdict is a real PASS; it was not reconstructed from a later run.

This audit changes documentation only. It does not trigger a producer, rewrite
reports, create picks or ledger rows, relax weights, or mutate 7F data.

## Release lineage

| Plan / gate | Merge | Release evidence | Closure |
|---|---|---|---|
| Clean-clone full-test baseline | PR [#18](https://github.com/KennyHsiao/surge-screener/pull/18), `21a459d` | Deploy [31891775411](https://github.com/KennyHsiao/surge-screener/actions/runs/31891775411) succeeded; focused and full local gates passed | PASS |
| R3 natural validation guard | PR [#22](https://github.com/KennyHsiao/surge-screener/pull/22), `c2f5959` | Bounded 7F observer terminal at `2026-08-17T23:47:57Z`; natural EOD [32077557851](https://github.com/KennyHsiao/surge-screener/actions/runs/32077557851) | PASS |
| Producer-terminal ingestion and overlay | PRs [#23](https://github.com/KennyHsiao/surge-screener/pull/23) / [#24](https://github.com/KennyHsiao/surge-screener/pull/24), `24d972e` / `ac1192d` | Deploys [32094624511](https://github.com/KennyHsiao/surge-screener/actions/runs/32094624511) / [32095197024](https://github.com/KennyHsiao/surge-screener/actions/runs/32095197024); 7F PASS at 72/2/0 after hotfix | PASS |
| Shared-lock atomic promotion | PR [#25](https://github.com/KennyHsiao/surge-screener/pull/25), `c6ca216` | Deploy [32108430625](https://github.com/KennyHsiao/surge-screener/actions/runs/32108430625); fixed-source terminal PASS at 72/2/0 | PASS |
| Verdict/status transaction boundary | PR [#26](https://github.com/KennyHsiao/surge-screener/pull/26), `9e07c7e` | Deploy [32112857402](https://github.com/KennyHsiao/surge-screener/actions/runs/32112857402); immutable generation and terminal PASS at 72/2/0 | PASS |
| Process-crash recovery | PR [#27](https://github.com/KennyHsiao/surge-screener/pull/27), `f5b79bd` | Deploy [32116201019](https://github.com/KennyHsiao/surge-screener/actions/runs/32116201019); later natural descendant executions remain PASS at 72/2/0 with no journal residue | PASS |

PR #22's ordinary deployment job was intentionally skipped while the bounded
deployment freeze protected the natural window. That is not treated as a
successful deploy. Its acceptance comes from the separately installed,
hash-recorded 7F observer and its terminal evidence. The freeze is now false,
and the dated service/timer are retired from active systemd configuration.

## R3 terminal evidence

The durable file
`shared/natural-validation/2026-08-18/verdict.json` records:

| Gate | State | Key evidence |
|---|---|---|
| Preflight | PASS | Clock synchronized, Asia/Taipei timezone, runner healthy, reviewed hashes matched |
| Data Health | PASS | Actual service terminal `success/0`; fresh 2026-08-18 Analytics observation |
| EOD | PASS | Natural run `32077557851`, job `surge_scan`, report date `2026-08-17` |
| Theme Flow | PASS | Actual service terminal `success/0`, `as_of=2026-08-17`, 35 themes |

The overall verdict is `PASS`, all gate reason lists are empty, and the exact
required base is `f181d814f0fc71aea4c49dd0738f8085aebc8d41`.

## Post-producer acceptance and current continuity

The 7F append-only post-producer log preserves the release progression:

- `ac1192d` closed the overlay regression and reached 72 PASS / 2 WARN / 0 BLOCK.
- `c6ca216` promoted under the shared lock at `2026-08-18T06:49:13Z` with
  72/2/0 and an aligned immutable generation.
- `9e07c7e` produced generation
  `2026-08-17-9e07c7edd232-08364dfc` and a matching PASS terminal.
- Descendant natural runs after `f5b79bd` continued to publish terminal PASS
  evidence, demonstrating that crash recovery did not regress the success path.

At the 2026-08-21 audit, the latest 7F terminal evidence reports:

| Check | Result |
|---|---|
| Post-ingestion verdict/status | `state=PASS`, `status=succeeded`, no reasons |
| Report date / fixed source | `2026-08-20` / `56dd7040f08497c592c85d85e513fe9b642ef235` |
| Current generation | `2026-08-20-56dd7040f084-e3024fab` |
| Analytics | 72 PASS / 2 WARN / 0 BLOCK |
| Candidate artifact | 25 scored, 826 ranked, 0 remaining |
| Daily and Risk Guard dates | `2026-08-20` |
| Portfolio | Correct optional `not_configured` PASS |
| No-picks | 18 successful published zero-pick scans; no pick or ledger row fabricated |
| Transaction recovery | No pending journal or rollback residue found |
| Service/timer | Service `success/0`, `Restart=on-abnormal`; timer enabled and active |
| Public health | 7F API `/healthz` HTTP 200; Streamlit `/_stcore/health` HTTP 200 |
| Schedulers | GitHub runner, Data Health timer, post-producer timer, and Theme timer active |

The two remaining WARNs are the truthful stale performance-ledger date and the
18-run successful zero-pick streak. They do not block publication and are not
release regressions.

## Audit findings

- Open critical/high/medium release findings: none.
- Documentation drift fixed: six plan status labels and their release closure
  sections now match the evidence.
- Runtime changes in this reconciliation: none.
- Still-natural future observations: a genuine positive pick and a real
  concurrent report push-race. Neither may be forced, and neither is a release
  blocker because deterministic failure/concurrency regressions already cover
  their contracts.
