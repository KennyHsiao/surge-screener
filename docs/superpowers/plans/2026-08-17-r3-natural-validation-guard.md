# R3 Natural Validation Guard Plan

Status: **ACCEPTED FOR EXECUTION — 2026-08-17**

## Goal

Make the 2026-08-18 natural validation fail closed without depending on the
operator laptop, fixed scheduler start times, a mutable local checkout, or stale
Analytics output. Preserve enough evidence to distinguish an application
failure, an external dependency failure, a delayed run, and an unexercised
push-race branch.

## Safety boundary

- Do not fabricate or backfill picks, weights, ledger rows, or `latest` files.
- Do not start IBKR, loosen score thresholds, force a Git push race, or manually
  run the production EOD pipeline.
- Keep the authoritative Data Health, EOD, and Theme Flow producers unchanged.
- Telegram delivery is non-authoritative and may fail without suppressing a
  successfully built report; ledger publication remains fail closed.
- Store observer code outside the deploy `current/` tree and evidence under
  `shared/` so a deployment cannot erase either one.

## Acceptance gates

### `VAL-PRE-001` — exact target and environment

The observer must prove that the deployed critical files match the reviewed
`main@f181d814f0fc71aea4c49dd0738f8085aebc8d41` hashes, required timers are
enabled and active, the self-hosted runner service is active, the host clock and
disk are healthy, and the public GitHub Actions API is reachable. The EOD run
head may advance because of scheduled report writers, but it must contain the
required revision as an ancestor.

### `VAL-DH-001` — fresh Data Health evidence

PASS requires a newly started 2026-08-18 Data Health invocation, a successful
terminal systemd/result status, a DuckDB mtime and Analytics `generated_at`
newer than that invocation, zero blockers, and publishable signal readiness.
It must independently verify:

- latest daily report is at least `2026-08-15`;
- portfolio is `not_configured` when reconciliation is absent;
- no-picks counts successful published reports and keeps missing, failed, and
  unpublished counts unknown;
- the expected pre-EOD successful zero-pick count is at least 14;
- Risk Guard observes UTC business date `2026-08-17` and exposes separate
  regime source/observation provenance.

### `VAL-EOD-001` — actual run lifecycle, UTC report date, publication

The observer must poll the actual scheduled workflow lifecycle rather than the
nominal 06:30 time. It identifies EOD by a non-skipped `surge_scan` job, records
queue/start/completion timestamps and head SHA, waits through scheduler/runner
delay, and accepts only terminal success. It then verifies on remote `main`:

- `reports/2026-08-17/summary.json` has the same report date, a non-negative
  integer `total_confirmed`, and a matching picks list;
- `reports/candidate_scores/2026-08-17.json` has a complete explicit cohort
  contract and zero remaining unscored candidates;
- both paths were committed after this workflow invocation.

A one-attempt publisher result proves the normal path only. Retry-path coverage
continues to come from the isolated concurrent-writer regression; the observer
must not manufacture a live race.

### `VAL-THEME-001` — independent Theme Flow result

Theme Flow passes only from its own fresh status file and successful systemd
result. It must not inherit a PASS from Data Health or EOD. A fresh non-empty
snapshot and expected business date are required.

### `VAL-EVID-001` — recoverable evidence

Every poll writes an atomic latest snapshot and an append-only JSONL timeline.
The final verdict contains per-gate PASS/FAIL/PENDING state, source revision,
observer hash, timestamps, GitHub rate-limit evidence, and actionable failure
reasons. Transient API errors remain evidence and do not immediately fail the
window; unresolved pending gates fail at the bounded deadline.

## Files

- Add `scripts/natural_validation_observer.py`.
- Add `scripts/test_natural_validation_observer.py`.
- Update `Makefile` so the observer regression runs in the standard test gate.
- Add one-time systemd service/timer templates under `deploy/`.
- Update `.github/workflows/surge_screener.yml` so Telegram failure does not
  suppress report persistence.
- Extend `scripts/test_deploy_artifacts.py` with workflow and observer-unit
  contracts.
- Update skill journals and `.agents/PROJECT.md` after verification.

## Verification

```bash
.venv/bin/python scripts/test_natural_validation_observer.py
.venv/bin/python scripts/test_deploy_artifacts.py
.venv/bin/python scripts/test_publish_reports.py
.venv/bin/python -m compileall -q scripts
python -c 'import yaml; yaml.safe_load(open(".github/workflows/surge_screener.yml"))'
git diff --check
make test
```

Operational verification:

1. Install the reviewed observer and units into the 7F `ops/` and user-systemd
   paths without touching `current/`.
2. Run `--preflight-only` for the 2026-08-18 window and require PASS.
3. Set `PHASE7E_DEPLOY_FREEZE=true`, record that external control, and keep all
   producer schedules and the GitHub runner active.
4. Enable the one-time 2026-08-18 05:50 Asia/Taipei observer timer.
5. Confirm the timer and service source hashes match the reviewed artifacts.
6. Restore `PHASE7E_DEPLOY_FREEZE=false` after the final verdict is captured.

## Risk and rollback

- **Observer risk: low.** It is read-only outside its dedicated evidence
  directory. Roll back by disabling/removing the one-time timer and service.
- **Workflow risk: low.** Telegram becomes best-effort; report generation,
  ledger consistency, and publication keep their existing gates. Roll back by
  reverting the workflow commit.
- **Freeze risk: medium and temporary.** It pauses deployments but not producer
  jobs. Roll back immediately by restoring the repository variable to `false`.

## Blocking review

- [x] The plan covers every identified false-pass/false-fail path without
  changing trading behavior.
- [x] The dirty, stale local checkout is isolated by a clean `origin/main`
  worktree and exact runtime hashes.
- [x] GitHub scheduler delay is handled by terminal lifecycle polling with a
  deadline after the producer timeouts.
- [x] The unauthenticated 7F GitHub API limit is respected by five-minute polling
  and cached job discovery; API errors are retained and retried.
- [x] Data Health, EOD, Theme Flow, and post-EOD ingestion expectations are not
  conflated.
- [x] Deployment overlap is controlled by the existing bounded freeze; the
  self-hosted runner remains online so EOD is still natural.
- [x] No unresolved credential, destructive-data, IBKR, pick, weight, or
  production-mutation blocker remains.
