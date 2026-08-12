# Industry Roles Retirement Continuity Re-attestation — 2026-08-12

Status: **PASS — OWNER-ATTESTED READ-ONLY RECHECK**

This record closes the Phase 7F recheck caused by later candidate and deployment
workflow changes. The single deployment owner supplied the required dated
`none found` attestation after reviewing the bounded technical inventory. The
separate authority grants only the reviewed R0/R1 implementation, tests, merge,
and test-server deployment; it does not authorize R3, data deletion, a legacy
export apply, or freeze mutation.

## Identity and trigger

- Historical Phase 7I decision timestamp: `2026-08-11T15:27:42Z`.
- Historical evidence release: `4d5812726bd245e55046368f42fd738a88f80cb7`.
- Current `origin/main`: `824f5465fc97c74a5cbea8f493f427b2541df565`.
- Current successful deployment: GitHub Actions run `31579438963`, completed
  `2026-08-12T08:41:29Z` on the exact current SHA.
- Re-attestation checkpoint: `2026-08-12T09:24:42Z`.

The complete historical-to-current diff includes changes to
`.github/workflows/surge_screener.yml` and
`.github/workflows/deploy_test_server.yml`. The Phase 7I decision explicitly
classifies a later relevant-surface change as an invalidation, so the old 7F
carry-forward was not reused without a fresh check.

## Repository and deployed-source binding

The current release changes candidate cohort bounding, one deferred Codex
retry, and immutable Node 24 first-party action pins. It does not change the
Industry Roles engine, store, admin command, API projector, API route, candidate
pipeline orchestration, deployment script, service/timer units, or external
consumer boundary.

The ordered source manifest was:

1. `.github/workflows/deploy_test_server.yml`
2. `.github/workflows/surge_screener.yml`
3. `api/industry_roles.py`
4. `api/main.py`
5. `scripts/deploy_test_server.sh`
6. `scripts/industry_role_admin.py`
7. `scripts/industry_role_store.py`
8. `scripts/industry_roles.py`
9. `scripts/run_candidate_pipeline.py`
10. `scripts/test_industry_role_legacy_retirement.py`
11. `docs/api/industry-role-legacy-retirement-gate.md`
12. `docs/api/industry-role-retirement-decision.md`

Local `origin/main` and deployed `current` were hashed independently. For each
path in the order above, the record is lowercase file SHA-256, one ASCII space,
the relative path, and newline. SHA-256 over the concatenated records produced:

```text
d8ec3309779be15a637799c94ffca5bf4fb8604f8fe4e158f609a2310c04597e
```

The command below reproduces the digest from either source root:

```bash
while IFS= read -r path; do
  digest="$(shasum -a 256 "$path" | awk '{print $1}')"
  printf '%s %s\n' "$digest" "$path"
done <<'EOF' | shasum -a 256
.github/workflows/deploy_test_server.yml
.github/workflows/surge_screener.yml
api/industry_roles.py
api/main.py
scripts/deploy_test_server.sh
scripts/industry_role_admin.py
scripts/industry_role_store.py
scripts/industry_roles.py
scripts/run_candidate_pipeline.py
scripts/test_industry_role_legacy_retirement.py
docs/api/industry-role-legacy-retirement-gate.md
docs/api/industry-role-retirement-decision.md
EOF
```

The deployed no-delete retirement gate passed `3/3` on that tree.

## Bounded host inventory

At `2026-08-12T09:23:44Z`, the read-only general inventory inspected only:

- fixed user/system systemd unit directories;
- the deployed user's crontab;
- fixed Compose filenames under the application root; and
- other bounded application roots outside the Surge Screener application.

It searched only for the exact filenames
`industry_role_overrides.json` and `industry_role_suggestions.json`. The result
was zero matches, zero read errors, and no truncated category. Neither live
compatibility source existed.

Under the deployment owner's earlier explicit delegation for the runner-account
credential-config boundary, Codex repeated the bounded boolean-only check. It
emitted exactly `NO_MATCH`; no path, context, environment value, command, or
file content was emitted.

## Runtime checkpoint

- Canonical state: valid revision `8`, taxonomy version `1`.
- Backup: valid revision `7`.
- Legacy export manifest: missing.
- Runtime retirement status: `HOLD`.
- API and UI: active/running, result `success`, zero restarts, HTTP health OK.
- Active GitHub workflows at the checkpoint: `0`.
- `PHASE7E_DEPLOY_FREEZE`: `false`.

## Owner attestation and authority

At `2026-08-12T13:23:00Z`, the deployment owner supplied this statement:

```text
我是 deployment owner。2026-08-12，我確認 release
824f5465fc97c74a5cbea8f493f427b2541df565 的 bounded inventory 在 repository
外未發現 Industry Roles legacy consumer：none found。並授權依 reviewed plan
執行 R0/R1、測試、merge 與 test-server deployment；不授權 R3、資料刪除、
legacy export apply 或 freeze 變更。
```

## Verdict and authority

Fresh Phase 7F relevant-surface technical evidence and the dated owner
attestation are **PASS** for release
`824f5465fc97c74a5cbea8f493f427b2541df565`. Phase 7I decision-only `READY`
eligibility is reissued against the current release.

Runtime administration remains `HOLD` until R0/R1 deploys and completes its R2
observation. The owner authorization permits only the reviewed R0/R1 automatic
reader retirement, tests, merge, and test-server deployment. R3, export apply,
legacy-file materialization, archive action, freeze mutation, and deletion
remain unauthorized.
