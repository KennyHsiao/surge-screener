# Gear Journal

## 2026-08-16 - Race-Safe Report Publication

**Implementation pattern:** Stage and commit only `reports/`, upload diagnostics
before cleanup, and allow runtime-output stashing only behind an explicit
discard-runtime-outputs flag. Drop only the exact publisher-owned stash on both
success and failure. Use an explicit fetch/rebase/push loop with a bounded
attempt count and fail non-zero on conflicts or exhaustion.

**Verification insight:** A temporary bare remote can deterministically model a
concurrent writer. Cover successful retry, conflicting report edits, and refusal
to stash a developer's dirty local outputs; assert that runtime files never
enter the report commit.

**Apply when:** A CI producer writes generated artifacts back to a shared branch
while sibling jobs may advance that branch.

## 2026-08-17 - Isolate One-Time Natural Validation Operations

**Implementation pattern:** Make notification best-effort without weakening the
authoritative ledger or report publisher. Start a date-bound observer before
the first producer, create its log directory in `ExecStartPre`, execute an
immutable ops copy, retain output under `shared/`, and set a bounded deployment
freeze while leaving the GitHub runner and producer timers active.

**Verification insight:** Validate the service and timer with Linux
`systemd-analyze`, then run the exact final observer in preflight-only mode on
the target host. Check loaded producer-unit bytes against deployed templates,
not merely whether a timer name exists.

**Risk and rollback:** The observer is read-only outside its evidence directory.
Disable/remove the one-time unit to roll it back. The temporary deployment
freeze is the only medium operational risk and must return to `false` after the
final verdict; it does not pause Data Health, EOD, or Theme Flow.

## 2026-08-18 - Decouple Report Ingestion from Deploy Pushes

**Implementation pattern:** Start a 7F-local observer before the producer window,
but gate work on actual GitHub job and local Theme terminal states. Resolve
`main` once, fetch every allowlisted artifact at that immutable SHA, validate
contracts and hashes, then atomically switch a durable report generation.

**Deployment pattern:** Install the service and timer with the ordinary deploy
script, retain generations under `shared/`, and make both Data Health and the
post-producer lane use the same overlay and writer lock. A producer token push
does not need to trigger another application deployment.

**Risk and rollback:** Build and check Analytics in same-filesystem staging;
promote the materialized DB last and retain the old inode until checks evidence
is durable. Revert and redeploy the code to roll back; never delete shared
generations or Analytics data during rollback.

## 2026-08-18 - Preserve Analytics Import Context in Report Overlays

**Regression and gate:** The first 7F post-producer refresh correctly ingested
published reports but exposed only the temporary `reports/` subtree. The final
whole-Analytics comparison caught the resulting `watchlist_sources` warning;
the producer-specific checks alone would not have caught it.

**Fix and rollback:** The overlay now links the immutable release siblings used
by existing importers (`content/` and `ranked_candidates.json`) beside the
temporary reports union. Revert this small overlay change and redeploy to roll
back; durable generations and the last-good Analytics data remain untouched.

## 2026-08-18 - Deploy the Atomic Post-producer Transaction

**Change and risk:** This is a medium operational transaction-boundary change,
not a schema or trading change. The post-producer lane now holds the same shared
lock across preparation, strict build/gate, report-pointer promotion, and
Analytics promotion. Data Health retains its existing lock-owning entry point,
so deployment topology and service configuration do not change.

**Verification and rollback:** Focused transaction/observer/Data Health/deploy
tests, complete repository tests, and an isolated real Analytics build verify
the release before PR deployment. Target verification must include the standard
deployment run, unit/timer health, API/Streamlit health, terminal verdict shape,
generation/source identity, and exactly 72 PASS / 2 WARN / 0 BLOCK on 7F.
Rollback is a PR revert and standard redeploy; retain shared generations,
DuckDB, Parquet, and checks so the last-known-good state stays recoverable.
