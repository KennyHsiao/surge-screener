# Judge Journal

## 2026-08-15 - R3 Industry Roles Export Retirement Review

**Engines:** Codex CLI completed a fresh uncommitted-diff review. Claude CLI was
runtime-broken (`Not logged in`) and was not counted as a pass.

**Initial findings:** Two `MEDIUM` findings: permanent admin status could no
longer fail closed on a newly appeared manifest, and the API inventory retained
an R1/R2 present-tense claim. The same review confirmed the hard-coded
`retirement=PASS` field had no remaining inspection basis and should be removed.

**Resolution:** Kept filenames out of permanent production code, documented the
mandatory one-time exact-path preflight before every R3 merge/deploy, required
rollout evidence binding, removed the retirement field, and synchronized the
inventory. Closure review found no blocking, high, or medium finding and marked
intent alignment `PASS`.

**Apply when:** A compatibility inspection surface is intentionally removed.
Separate durable runtime health from a bounded rollout-only absence gate, and
never represent an uninspected condition with an unconditional success field.

## 2026-08-15 - Full-Test Baseline Recovery Review

**Engines:** Independent code and traceability reviewers plus Codex CLI reviewed
the implementation. Claude CLI remained unauthenticated and was not counted as
a pass.

**Finding and resolution:** Review found that legal, very large JSON integers
could overflow during float conversion; a second adversarial probe found
precision collapse for unequal integers above `2**53`. The shared numeric
helper now keeps integers exact, safely compares float-containing pairs, and is
covered by `10**400` plus exact-mismatch regressions.

**Verdict:** No remaining blocking, high, or medium finding; intent alignment
is `PASS`. Hardening the adjacent Reversal tail is accepted scope because it
uses the same fail-soft helper and changes no public projection.

## 2026-08-16 - Analytics Operations Gap Closure Review

**Engine status:** The exact Codex commit-review command started normally but
timed out after 300 seconds without a formal verdict, so it was not counted as a
pass. Claude was intentionally excluded. Independent bounded review therefore
provided the closure perspective with explicitly degraded engine confidence.

**Findings and resolution:** The partial engine output found feature-ref history
could be promoted by `HEAD:main` and that publisher-owned stashes would collect
on the persistent self-hosted runner. Follow-up review then found missing
source-ref evidence still failed open and two cleanup paths lacked permanent
tests. Publication now requires exact `refs/heads/main` provenance before any
Git mutation, cleans only its own stash on every exit path, preserves existing
operator stashes, and permanently tests retry, conflict, terminal push, fetch,
local-safety, missing-ref, and feature-ref cases.

**Verdict:** The earlier malformed-regime, no-picks, present-empty portfolio,
empty-scanner, and candidate-provenance findings remain closed. Final bounded
closure reports zero blocking/high/medium findings and intent alignment `PASS`.
