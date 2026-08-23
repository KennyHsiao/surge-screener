# Post-producer Analytics ingestion

The 7F host owns report ingestion after deployment. The laptop and VPN are not
part of the runtime path.

## Lifecycle

`surge-post-producer-analytics.timer` starts the observer at 06:35 Asia/Taipei
on Tuesday through Saturday. The start time is not a success assumption. The
service waits for these actual terminal producers:

- the scheduled GitHub `surge_scan` job;
- the scheduled `market_thesis` job when the report date is Monday;
- the local 7F Theme Flow service and its fresh snapshot.

After all required producers succeed, the service resolves `main` once. Every
GitHub Contents request then uses that full 40-character SHA. Only the daily
summary, candidate-score snapshot, and calendar-required Market Thesis file are
allowlisted. Their JSON contracts and SHA-256 values are validated into a new
immutable prepared generation. Preparation does not move
`shared/published_reports/current`.

The candidate contract is the same deterministic contract enforced inside the
EOD workflow. Every persisted row must carry authoritative
`evidence_capabilities_v1` provenance and pass `validate_full_score_contract`.
The run-level `promotion_reachability_v1` receipt is rebuilt from every
candidate diagnostic and must match exactly, report a complete known state,
exactly zero unsupported-credit rows, and an empty ticker list. Analytics then
requires the same report date, cohort size, complete shadow-contract row count,
schema/mode, and zero unsupported credit before promotion.

After all producers are successful, a transient GitHub API/transport error or a
short publication-propagation delay remains a non-terminal artifact `PENDING`
state. The service retries those idempotent fixed-SHA reads once per minute until
the existing 10:30 deadline. Malformed JSON and contract violations are not
retried. They fail closed immediately because another read cannot repair the
same immutable content.

Analytics reads an overlay: durable published files win over the same paths in
the deployed release, while release history and 7F runtime sources remain
visible. Data Health uses the same overlay on its next full run, so it cannot
regress the post-producer ingestion.

The strict Analytics build, checks, and provisional promotion run in a bounded
child process while the parent retains the shared writer lock. The parent owns
the 10:30 wall-clock deadline. If the child stalls, the parent terminates it,
recovers any pending journal under the same lock, restores the complete prior
state, and persists canonical deadline failure evidence. A `TimeoutError` from
the Analytics build is terminal; only the typed writer-lock timeout is retried.

## Transaction and failure behavior

Data Health and post-producer ingestion share:

`/home/kenny/apps/surge-screener/shared/locks/analytics-refresh.lock`

One acquisition of that lock covers report preparation, the complete Analytics
build, Analytics checks, the strict latest-date/cohort gate, the `current`
pointer switch, and Parquet/checks/DuckDB promotion. Data Health keeps using the
lock-owning transaction API and therefore cannot enter between those steps.

The strict build reads the prepared generation directly. Only after every gate
passes does the transaction switch `current` and fsync the published-store
directory; it then promotes Parquet and checks, followed by DuckDB. That data
promotion remains provisional: its
rollback backup is retained while the PASS verdict and succeeded status are
each atomically replaced and their containing directories are fsynced. Only
after both evidence writes succeed does the transaction discard its rollback
backup.

Before the first `current`, Parquet, checks, or DuckDB mutation, the service
fsyncs a versioned pending journal and complete rollback copies under
`shared/.analytics-backup-*`. If Python exits non-zero, is killed by a signal,
or times out, the host retries after five minutes. The initial attempt plus at
most two recovery starts share a 16-hour rate-limit window. That still contains
the initial start when a fourth maximum-duration post attempt would begin at
15 hours 15 minutes, so systemd blocks it. The next lock owner recovers any
pending journal before building, restores all four canonical artifacts
idempotently, and replaces partial PASS/succeeded evidence with the canonical
FAIL schema. A
durable `committed` marker means recovery keeps the new state and only removes
backup residue.

A producer failure, deadline, missing artifact, malformed contract, non-zero
BLOCK count, stale post-ingestion check, promotion failure, PASS-verdict write
failure, or succeeded-status write failure leaves the prior generation,
DuckDB, Parquet, and checks in place. Any failure after provisional promotion
invokes both the Analytics rollback and the companion `current` rollback before
releasing the shared lock. If the status write fails after the PASS verdict was
replaced, the failure path replaces that provisional PASS with the canonical
FAIL verdict. Unreferenced prepared generations are retained as immutable
forensic evidence and never become current after a failed transaction.

The service does not create picks, relax weights, or synthesize ledger rows.
A successful zero-pick report stays distinct from missing, failed, and
unpublished producer states.

Data Health, Theme Flow, and post-producer ingestion are locally recoverable
oneshots. They retry an explicit non-zero exit after five minutes, with at most
two recovery starts in a 16-hour interval. Post-producer ingestion therefore
keeps a failed Theme result pending until the deadline so a later fresh success
can replace it. A failed scheduled GitHub EOD or Market Thesis job remains
terminal; the service never dispatches a replacement and never labels one as
natural.

## Evidence and operations

The terminal verdict is:

`/home/kenny/apps/surge-screener/shared/post_ingestion/latest.json`

It uses one schema for PASS and for producer, deadline, artifact, gate, build,
or promotion failures. It contains producer run/job IDs, the fixed source SHA
when available, artifact paths and hashes, selected Analytics values, and the
promoted database identity. Evidence that does not exist at the failure point
is represented by the same stable empty or null fields rather than a different
payload shape.
Runtime status and logs are under `shared/run_status`.

```bash
ssh antigravity 'systemctl --user status surge-post-producer-analytics.service --no-pager'
ssh antigravity 'systemctl --user list-timers surge-post-producer-analytics.timer --no-pager'
ssh antigravity 'journalctl --user -u surge-post-producer-analytics.service -n 100 --no-pager'
ssh antigravity 'python3 -m json.tool /home/kenny/apps/surge-screener/shared/post_ingestion/latest.json'
```

Rollback is a normal code revert and redeploy. Existing durable generations
are retained; do not delete `shared/published_reports` or `shared/data` during
rollback.
