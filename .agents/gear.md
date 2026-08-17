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
