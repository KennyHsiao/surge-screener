# Industry Roles Legacy Retirement Gate

Current verdict: **R3 RETIRED**

Deployed evidence: `industry-role-retirement-r3-evidence-2026-08-15.md`, `PASS`
for release `43c38a04d3de97a1d933a8207c12166b45780631` and deploy run
`31867899113`.

Decision record: `industry-role-retirement-decision.md`, timestamp
`2026-08-11T15:27:42Z`.

Current-release continuity: `industry-role-retirement-continuity-2026-08-12.md`,
owner-attested `PASS` at `2026-08-12T13:23:00Z` for release
`824f5465fc97c74a5cbea8f493f427b2541df565`.

R2 passed on 2026-08-15 with the dated evidence in
`industry-role-retirement-r2-evidence-2026-08-15.md`. On 2026-08-15 the
deployment owner supplied the required second authorization to review and
execute R3. The authorized change removes the explicit export command,
manifest implementation, legacy inspection fields, and final filename
allowances. R3 does not authorize creating, archiving, moving, rewriting,
truncating, or deleting either compatibility file or an export manifest.

## Repository consumer inventory

Live repository consumers read only the canonical aggregate through
`scripts/industry_roles.py`. Eastmoney Money Flow and Universe Refresh use the
canonical-only approved-ticker projection and retain fail-soft supplemental
behavior when canonical state is invalid. The protected API reads the taxonomy
plus the exact injected canonical state path; its read and mutation surfaces no
longer accept or derive either legacy path.

Automatic runtime reads are retired in R1. The explicit emergency export is
retired in R3, leaving zero production Python owners of either legacy filename.
Canonical reads and mutations, the single retained backup, and guarded
backup preview/apply recovery remain unchanged.

## Operator evidence

Run from the deployed release without exposing the bearer credential:

```bash
.venv/bin/python scripts/industry_role_admin.py status --require-canonical
.venv/bin/python scripts/industry_role_admin.py restore-backup
```

Restore remains a preview unless `--apply` is supplied. A valid current state
also requires the preview's exact `--expected-etag`; recovery from a
corrupt/missing current state instead needs the explicit
`--allow-invalid-current` flag. A restore drill must use a copied temporary
state directory unless an incident has explicitly authorized restoration of
production state.

After R3, `status` intentionally reports only taxonomy, canonical, backup, and
overall health; it no longer infers compatibility-file or manifest state.
Immediately before every R3 merge/deploy, the operator must therefore run the
separate read-only exact-path preflight for both compatibility sources and the
manifest. Any regular file, symlink, unknown result, or check error is `HOLD`
before deployment. The dated result must be attached to the rollout evidence.

Phase 7F evidence for release
`566f5e373622a549302ce43f945eb09640c9c49e` completed on 2026-08-07. The
bounded host inventory returned zero repository-external consumers, and the
separately owner-authorized credential-config exact-filename check returned
`NO_MATCH` without emitting paths or contents. The original continuity to
deployed evidence release `4d5812726bd245e55046368f42fd738a88f80cb7`
was invalidated by later workflow changes. The fresh 2026-08-12 recheck binds
the exact current deployed release, repeats the bounded inventory and
boolean-only credential-boundary check, and records the deployment owner's
dated `none found` attestation. The deployed no-delete gate re-passed `3/3`;
current continuity is accepted.

## Dated retirement evidence

- Phase 7E: remediated operating window `PASS`, final checkpoint
  `2026-08-11T14:37:38Z`.
- Phase 7F: bounded inventory and delegated boolean check `PASS`, with the
  relevant-surface continuity above.
- Phase 7G: missing-source archive proposal accepted and `CERTIFIED` by
  `2026-08-11T14:51:52Z`.
- Phase 7H: overall `PASS` by `2026-08-11T15:11:59Z`; live payload `N/A`,
  temp-only mechanics `PASS`, production bundle unchanged, zero retained temp
  roots.
- Phase 7I: dated decision `READY` at `2026-08-11T15:27:42Z`.
- R2: natural Candidate, Data Health, and Theme Flow observation `PASS` on
  2026-08-15; candidate and follow-up verdicts passed `72/72` checks.
- R3: second deployment-owner authorization received on 2026-08-15; live
  sources and export manifest were revalidated missing before implementation.

## Conditions satisfied to leave HOLD

- [x] A deployment owner records the start and end of an agreed operating window
  with valid canonical status and no export manifest.
- [x] Backup inspection reports either a valid retained copy or a documented reason
  that no second revision has yet created one.
- [x] Before R3, the export preview succeeded; the preserved temporary-directory
  restore drill produces the predicted new revision and ETag.
- [x] Every external consumer outside this repository is inventoried with an owner,
  path, read/write behavior, and migration status. An explicit external consumer
  attestation is required even when the current belief is “none”.
- [x] A separately reviewed archive proposal defines destination, permissions,
  retention, rollback, and verification. Archiving is not deletion.

All R3 entry conditions have dated evidence, so runtime retirement is `PASS`
for the repository change. Both live compatibility paths and the export
manifest were missing at preflight; absence was treated only as a precondition,
never as cleanup authority. The static gate requires zero production filename
owners, zero export-surface symbols, and no obsolete `.gitignore` allowance.

Rollback is code revert and redeploy. R3 does not authorize materializing an
export, disposing of a live file, or changing the deployment freeze. Any
runtime legacy file or manifest appearance returns the rollout to `HOLD` and
requires a separate disposition plan. The permanent admin CLI is not a
replacement for this one-time rollout gate.
