# Industry Roles Legacy Retirement Gate

Current verdict: **READY**

Decision record: `industry-role-retirement-decision.md`, timestamp
`2026-08-11T15:27:42Z`.

This gate records whether `content/industry_role_overrides.json` and
`reports/industry_role_suggestions.json` may be treated as archive candidates.
It does not authorize deletion, automatic dual-write, or deployment changes.

## Repository consumer inventory

Live repository consumers read the canonical aggregate through
`scripts/industry_roles.py`. Eastmoney Money Flow and Universe Refresh use the
canonical-first approved-ticker projection and retain fail-soft supplemental
behavior when canonical state is invalid. The legacy filenames remain only in:

- `scripts/industry_roles.py` for the legal revision-zero seed and explicit
  compatibility projection;
- `api/main.py` for fixed legacy seed path injection while canonical state has
  not yet been committed.

The explicit export is rollback preparation, not a live writer. It holds the
canonical lock, writes a pending manifest, atomically replaces each legacy file,
verifies both hashes, and commits the manifest last.

## Operator evidence

Run from the deployed release without exposing the bearer credential:

```bash
.venv/bin/python scripts/industry_role_admin.py status --require-canonical
.venv/bin/python scripts/industry_role_admin.py export-legacy
.venv/bin/python scripts/industry_role_admin.py restore-backup
```

The latter two commands are previews. `--apply` is required for a real export
or restore. A valid current state also requires the preview's exact
`--expected-etag`; recovery from a corrupt/missing current state instead needs
the explicit `--allow-invalid-current` flag. A restore drill must use a copied
temporary state directory unless an incident has explicitly authorized
restoration of production state.

Phase 7F evidence for release
`566f5e373622a549302ce43f945eb09640c9c49e` completed on 2026-08-07. The
bounded host inventory returned zero repository-external consumers, and the
separately owner-authorized credential-config exact-filename check returned
`NO_MATCH` without emitting paths or contents. The complete diff to deployed
evidence release `4d5812726bd245e55046368f42fd738a88f80cb7` changed no
Industry Roles owner, consumer, retirement gate, deployment boundary, or
workflow. The deployed no-delete gate re-passed `3/3`; continuity is accepted.

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

## Conditions satisfied to leave HOLD

- [x] A deployment owner records the start and end of an agreed operating window
  with valid canonical status and no unresolved pending export.
- [x] Backup inspection reports either a valid retained copy or a documented reason
  that no second revision has yet created one.
- [x] The export preview succeeds; one temporary-directory restore drill produces
  the predicted new revision and ETag.
- [x] Every external consumer outside this repository is inventoried with an owner,
  path, read/write behavior, and migration status. An explicit external consumer
  attestation is required even when the current belief is “none”.
- [x] A separately reviewed archive proposal defines destination, permissions,
  retention, rollback, and verification. Archiving is not deletion.

All conditions have dated evidence, so the decision gate is **READY**. Both
live compatibility paths are currently missing. `READY` does not authorize
materializing them, archiving a live file, deleting data, removing compatibility
code, deploying, or changing the freeze. Each action requires a separately
authorized plan with exact targets, tests, and rollback.

This repository `READY` gate is bound to the dated Phase 7I decision and the
static no-delete test. Runtime administration deliberately remains `HOLD`;
this document records evidence eligibility and does not implement retirement.
No compatibility change, repository merge, deployment, or runtime action is
implied by `READY` alone.
