# Industry Roles Legacy Retirement Gate

Current verdict: **HOLD**

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

## Conditions required to leave HOLD

- A deployment owner records the start and end of an agreed operating window
  with valid canonical status and no unresolved pending export.
- Backup inspection reports either a valid retained copy or a documented reason
  that no second revision has yet created one.
- The export preview succeeds; one temporary-directory restore drill produces
  the predicted new revision and ETag.
- Every external consumer outside this repository is inventoried with an owner,
  path, read/write behavior, and migration status. An explicit external consumer
  attestation is required even when the current belief is “none”.
- A separately reviewed archive proposal defines destination, permissions,
  retention, rollback, and verification. Archiving is not deletion.

Until all conditions have dated evidence, the gate remains **HOLD** and both
legacy compatibility paths remain supported for bootstrap/rollback only.
