# Omen project journal

## 2026-08-23 - Natural validation failure pre-mortem

DEEP FMEA identified two dominant preventable risks: post-ingestion could accept
unsupported nontechnical score credit (RPN 504), and a single GitHub content API
failure after producer success could become terminal (RPN 240). The accepted
controls enforce the same full-score contract at the fixed-SHA artifact boundary,
require exact unsupported-credit zero, retry only transient immutable reads until
the existing deadline, and retain last-known-good state for every terminal path.

Yahoo batch transport, empty, and partial responses plus local Data Health/Theme
failures receive bounded idempotent recovery. Missing tickers alone are retried.
Global GitHub/Yahoo outages remain explicit residual risk and must fail closed;
no manual dispatch, synthetic output, or relaxed gate may be used to manufacture
a natural PASS. Standalone remediation prompts are suppressed because the
controls are implemented and verified in this engagement.

Final boundary review added three failure modes that the first pass understated:
an Analytics projection could show zero unsupported credit while still being
legacy/partial, a lock or long build could cross 10:30 and persist a late PASS,
an initially empty GitHub jobs response could be cached forever, and a
start-limit window shorter than service timeouts could permit endless systemd
retries. The closed controls recompute the entire run receipt, require the exact
Analytics cohort/schema/date contract, refresh empty/incomplete job lists, gate
lock and PASS persistence by the deadline, run Analytics inside a killable child
owned by the lock-holding parent, and use a 16-hour three-start limit for every
recoverable unit.

The final durability review also found that atomic replacement alone did not
make the published-generation pointer crash-durable. The store directory is now
fsynced after both promotion and rollback pointer changes, and a successful
observer regression proves that a later recovery pass cannot roll the committed
generation back.
