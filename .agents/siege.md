# Siege project journal

## 2026-08-23 - Natural validation resilience and contract hardening

**Resilience:** fixed-SHA GitHub GETs retry only transport/API and not-yet-visible
publication failures with a deadline bound. Yahoo batch GETs retry only missing
tickers after transport, empty, or partial results. Data Health, Theme, and
post-ingestion oneshots use bounded
failure restarts whose 16-hour window still contains attempt one when systemd
evaluates a fourth maximum-duration start.
No production chaos or producer dispatch is part of verification.

**Contracts:** the post-producer boundary now validates every candidate through
`validate_full_score_contract`, requires authoritative evidence capabilities,
unique non-empty tickers, a complete >=25 cohort, and exact zero unsupported
credit. The run receipt is recomputed from every candidate instead of trusting
its stored summary. The Analytics gate requires the exact report date, cohort,
contract row count, schema/mode, known state, and zero unsupported credit before
atomic promotion. Lock wait, polling sleep, and PASS persistence are deadline
bounded. Analytics build/check/promotion runs in a killable child while the
parent retains the lock and owns journal recovery plus terminal persistence.
Fault tests retain the existing DB/Parquet/checks/current rollback contract and
canonical PASS/FAIL terminal schema.

**Crash durability:** `current` pointer promotion and rollback now fsync the
published-store directory before the transaction can advance. A successful
observer test then reacquires the writer lock, runs recovery, and proves the
committed generation, database, Parquet, and checks remain byte-stable with no
pending backup.
