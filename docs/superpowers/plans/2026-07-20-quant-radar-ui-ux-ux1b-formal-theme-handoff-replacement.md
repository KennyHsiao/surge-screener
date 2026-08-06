# UX-1B Formal Theme Handoff Replacement Plan

## Document info

| Field | Value |
| --- | --- |
| Type | Implementation checklist / low-level lifecycle contract |
| Version | `v1.0-review-candidate` |
| Status | Not authorized; implementation is blocked pending frozen-package review and V2 authorization |
| Owner | Quant Radar maintainer |
| Author | Scribe, informed by Atlas lifecycle analysis |
| Reviewers | Independent authority, lifecycle-semantics, and publication reviewers |
| Audience | Quant Radar maintainers and implementation agents |
| Recovery ID | `20260719T211915Z` |
| Traceability | `docs/superpowers/plans/2026-07-20-quant-radar-ui-ux-ux1b-formal-theme-handoff-replacement.traceability.yaml` |

## Replacement boundary

The rejected draft
`docs/superpowers/plans/2026-07-19-quant-radar-ui-ux-ux1b-formal-theme-handoff-remediation.md`
remains frozen at SHA-256
`f3c41effe742c18c145de254d76e5a15ba5384a0078f9d5b5ac0adfcb59136f4`
and size `64646`. It is not an accepted plan. Its third review found the same
unguarded-capture and publication blocker classes for the third time, so work
stopped as required by `AGENTS.md`. The maintainer subsequently authorized a
new replacement-planning phase on 2026-07-20. This file is that new baseline;
it is not a fourth revision of the rejected draft.

The replacement adopts these exact, independently validated sections from the
frozen draft as normative input:

| Imported section | Section SHA-256 |
| --- | --- |
| `Outcome` | `a205d253a113564f9484740d32c2688bfa85b16997f09b3591c39b2fb2a0349b` |
| `Blocking defect` | `74b2435b63d99ed4eab06f54e14f7b615de2de5b7de2470bcbb6f1ae7a0a7856` |
| `Requirements` | `b85179a9dae551ab139d729c6e89a2f34b90e418dadfe5b03adbf939e34f69e8` |
| `Architecture decision` | `261d720cbc8305d8abf77d5071b46c635348fb1a205cafa3efcc2caaf8f91afa` |
| `Sidecar and screenshot comparison` | `6df7ce86634802cbc611fbab7171d582446372d25eb07108e9237cad9c5eb266` |

Section extraction starts at the exact `## <name>\n` heading byte and ends
immediately before the next `## ` heading. The verifier rehashes these ranges.
All other frozen-draft sections are informative history only and are replaced
by this document. On conflict, this document wins. Neither file may drift
after package review.

The resulting outcome remains one fail-closed external bridge from the formal
recovery evidence to parent UX-1B Tasks 3-5. No route, provider, API, loader,
mutator, session-state, or fail-soft JSON behavior changes in this remediation.

## Architecture decision

### Current state

The frozen runners can create valid postcontrol and pretheme bundles, but they
cannot durably prove that one coordinator initiated both stages at most once.
The rejected design also separated theme authorization from the process that
wrote five live files, creating replay and staging-to-apply races.

### Considered options

| Option | Benefit | Cost / risk | Decision |
| --- | --- | --- | --- |
| Keep three read-only preflight gates around Make runner commands | Small Make diff | No durable `capture_started`; concurrent or crashed invocations remain indistinguishable | Rejected |
| Add resumable per-stage workers | Can continue after coordinator loss | Frozen runners lack a durable launch handshake; a second process could repeat a stage | Rejected |
| Use a single lock-owning Task 9 coordinator and burn the ID on partial loss | Exact at-most-once provenance without editing frozen runners | Any coordinator loss can sacrifice the recovery ID | Selected |
| Keep standalone theme authorization plus a later apply process | Familiar separation | Existing authorization can be replayed and staged descriptors cannot span the gap | Rejected |
| Use one lock-owning, one-shot theme apply transaction | Only the fresh claim creator may write; retained FDs close TOCTOU | Five files still require rollback-aware logical CAS | Selected |

### Desired dependency direction

```text
accepted replacement package + V2 authorization
                 |
                 v
          preflight / Tier 0
                 |
                 v
 capture-task9 --owns--> frozen runners
                 |
                 v
 review packet -> external review -> immutable root
                 |
                 v
 sealed theme batch -> external review -> apply-theme-batch
                 |
                 v
 applied receipt -> theme states -> posttheme -> final closure
```

Only the external verifier publishes lifecycle authority. Frozen capture tools
remain evidence producers, not authority issuers.

### Implementation shape

Full tactical DDD is rejected: this is a closed filesystem protocol, not an
evolving business aggregate. The verifier uses a functional core of frozen
Python 3.10-compatible dataclasses/enums and explicit tagged success/error
results for parsing, transitions, path derivation, and canonical bytes; a thin
imperative shell alone owns descriptors, locks, subprocesses, clocks, random
nonces, and publication. Illegal status combinations are represented by
separate closed transition constructors, not optional-flag soup. The one module
is deliberate because only two absent bootstrap files may exist before Tier 0;
it is organized into small pure sections/functions rather than one stateful God
object. PEP 695/3.12-only syntax is forbidden under the Python 3.10 AST gate.

## Authority and authorization

The exact accepted upstream authority set is unchanged:

| Authority | SHA-256 |
| --- | --- |
| `docs/superpowers/plans/2026-07-16-quant-radar-ui-ux-ux1b.md` | `48bfb4de8aea1003cceca1627f40a859858942f23b17b9f898841792936974e7` |
| `docs/superpowers/plans/2026-07-16-quant-radar-ui-ux-ux1b-evidence-recovery.md` | `c31b42e33d388a53f22b399fe259ef6fd74e206d3a4f5f9775492c8e55a39837` |
| `docs/superpowers/plans/2026-07-18-quant-radar-ui-ux-ux1b-focused-ax-remediation.md` | `4d55ad4428999fcaf61e60700d127033ac55e650d6fbe1b806c3e6fe6627882f` |
| `docs/superpowers/plans/2026-07-19-quant-radar-ui-ux-ux1b-semantic-readiness-remediation.md` | `63cf76d5dadb4125b2eaf5aa9d692035d738dc2db145075f232b475e70febde1` |
| `docs/superpowers/plans/2026-07-19-quant-radar-ui-ux-ux1b-geometry-quantization-remediation.md` | `a24c82369af2f9833c6c2c534bbee16beea7676be324931f4a8815aba9f8ab9f` |
| `docs/superpowers/plans/2026-07-19-quant-radar-ui-ux-ux1b-hidden-radio-label-remediation.md` | `c87484d7bb017fa9b0514ac20dcb4e24e8a933afaf16d6494946205af8b89cfe` |
| `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery-architecture.md` | `92c6359b9ae579d90aa90874d5d26852b0c435f81982075c7f2b79591633bf4c` |
| `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery-prechange.json` | `13d67dec94b51868fd54734d029123975d559fb513a211b8096eb63b59475101` |
| `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery-rollback.json` | `4246e4e77be28669fb7817b41d1f754b967358c32a3bd3e00467631c1207b6b1` |
| `.claude/ui_snapshots/ux1b/recovery/prechange-bundle-20260716T145533Z/prechange-files.tar` | `1101b22382420192369fb804d46bda6614a5bf5b6905bb760b700c8a668cdcf1` |
| `.claude/ui_snapshots/ux1b/recovery/prechange-bundle-20260716T145533Z/bundle-manifest.json` | `bde4b6db456c213c2f52fbb9122e3602dc589e35fa7614663e3d8dd84c9be4cc` |
| `docs/ui-ux/quant-radar-ui-v2-ux1b-task8-selector-delta.json` | `5b3ec3e04f4bee41e89072f52a38bdff3dc30abe937fad43ceebba6e6a7d5f24` |
| `.claude/ui_snapshots/ux1b/rollback-source/manifest.json` | `739df8db110428ff6cfe08b405524d17bd56fbbf52427de128e8b805165b3d69` |
| `docs/ui-ux/quant-radar-ui-v2-ux1b-prechange.json` | `38443c1483b03f7bf6bdc5095da161059e7f06e8859d9ba7f1d282413e50d674` |
| `docs/ui-ux/quant-radar-ui-v2-ux1b-classification.json` pending preimage | `c6c27801ffbd7aeffd86514156ba2e4c81f0699b78e6db7278dfdf72d3d6a77b` |
| `.claude/ui_snapshots/ux1b/rollback-source/.quant-radar-ux1b-owner` | `b1ca8a82cd967cf7b45a54985e4f0a9344b38cfbcf7bb1abba54bff4f60993d8` |
| `.claude/ui_snapshots/ux1b/rollback-source/app.py` | `1f0d8ec142aee605e51e126add8f867df06c81eb900475204630812acd019f85` |
| `.claude/ui_snapshots/ux1b/rollback-source/_design.py` | `0844c44dfc0b254f541ce7b9188cb71856e8549bcaaffea44db220c44a3be92d` |
| `.claude/ui_snapshots/ux1b/rollback-source/config.toml` | `102d584059084f741addab857c98fc7fda92799fd8fc1aa112d93830c72c6dbf` |
| `.claude/ui_snapshots/ux1b/rollback-source/requirements.txt` | `123fd3ee1559a93cf1e30efcf327dd93f6e8604cfa1a6a13487d6de6f3da7d16` |

The replacement package becomes authority only after its plan and sibling
traceability ledger are frozen, independently reviewed with no High/Medium,
and bound by exactly one V2 stanza in
`docs/ui-ux/quant-radar-ui-v2-ux1b-recovery.md`.

The raw-byte grammar is:

```text
START   = b"<!-- UX1B_FORMAL_HANDOFF_AUTHORIZATION_V2\n"
END     = b"\nUX1B_FORMAL_HANDOFF_AUTHORIZATION_V2 -->"
GENERIC = b"UX1B_FORMAL_HANDOFF_AUTHORIZATION_"
```

The retained recovery-document FD must contain exactly two `GENERIC`
occurrences total, one exact `START`, one exact `END`, in that order. The body
is exactly one nonempty UTF-8/NFC line with no leading or trailing whitespace.
Strict JSON rejects duplicate or unknown keys, floats, NaN/Infinity, invalid
UTF-8, and non-NFC strings. Canonical reserialization must equal the body.
Legacy, future, nested, extra, malformed, or unpaired markers fail closed.

The canonical body has exactly:

```text
schemaVersion,sequence,status,authorizedRecoveryId,amendment,traceability,precedence
```

It requires schema `quant-radar-ui-ux-formal-handoff-authorization/v2`, integer
`sequence: 1`, `status: "AUTHORIZED"`, recovery ID `20260719T211915Z`, exact
`ArtifactRef` records for this plan and its ledger, and this literal ordered
array:

```json
[{"authority":"authorization-record","level":1},{"authority":"accepted-replacement-amendment-package","level":2},{"authority":"accepted-recovery-authority-set","level":3},{"authority":"accepted-parent-ux1b-plan","level":4}]
```

The authorization SHA covers only the canonical JSON body and is not embedded
in that body. The mutable Markdown around the stanza is not authority. Its
pre-authorization diagnostic SHA
`c7445ae0cf7442f788a3ba78152ccbb88135003dec258ea211318d7b214b1be1`
must never be used as an authority hash. Every lifecycle command reopens and
validates the stanza, plan, ledger, base draft, and imported section hashes.

Freeze order is exact: finalize plan bytes; compute plan SHA/size; generate the
ledger that references that plan; freeze ledger bytes; review both immutable
files; append the V2 stanza; then implement. A review finding that changes
either file repeats this order. Review verdicts are external records, so the
reviewed package bytes are never edited merely to record acceptance.

## Additional requirements

- `CFR-007`: Authorization has exactly one canonical V2 marker pair and one
  literal precedence value; ambiguity blocks every lifecycle command.
- `CFR-008`: Historical selector modes come only from authenticated tar headers
  and reproduce the exact Task 6 source digest.
- `CFR-009`: Fixed and dynamically derived outputs have exact non-glob
  ownership/absence authority; the operational lock is never removed.
- `CFR-010`: The frozen traceability ledger has complete bidirectional
  requirement, acceptance, test, and implementation edges.
- `CFR-011`: Task 9 launches each frozen capture stage at most once and only
  from the process that freshly publishes its intent.
- `CFR-012`: Only the process that freshly publishes the root-keyed theme apply
  attempt may perform forward live writes.
- `CFR-013`: Every external review binds a verifier-produced packet containing
  the exact prompt, inputs, and item set; the verifier never authors judgment.

## Scope

### Planning artifacts

- this replacement plan;
- its sibling `.traceability.yaml` ledger.

### Fixed remediation paths

- `scripts/ui_ux_theme_handoff.py`;
- `scripts/test_ui_ux_theme_handoff.py`;
- `Makefile`;
- `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery.md`;
- `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-prechange.json`;
- `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-rollback.json`;
- `.claude/ui_snapshots/ux1b/recovery/theme-handoff-prechange-20260720T000000Z/`;
- `.claude/ui_snapshots/ux1b/.formal-theme-handoff.lock`;
- `.claude/ui_snapshots/ux1b/recovery/.capture-20260719T211915Z.lease`;
- `.claude/ui_snapshots/ux1b/recovery/theme-handoff-preflight-20260719T211915Z.json`;
- the five Task 9 capture lifecycle JSON leaves listed below;
- the fixed Task 9 after namespaces and migration report;
- the fixed control-migration review packet, intake, and published review;
- `.claude/ui_snapshots/ux1b/recovery/theme-handoff-candidate-20260719T211915Z.json`;
- `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json`;
- `.agents/scribe.md`, `.agents/atlas.md`, `.agents/builder.md`, and
  `.agents/PROJECT.md`.

### Dynamically derived theme paths

After the immutable root supplies root SHA `R`, and explicit batch/theme IDs
`B` and `T` are chosen, the verifier derives only:

```text
.claude/ui_snapshots/ux1b/theme-lineage-prechange-R.json
.claude/ui_snapshots/ux1b/theme-batch-prechange-R-B.json
.claude/ui_snapshots/ux1b/theme-batches/R/B/
.claude/ui_snapshots/ux1b/review-intake/theme-batch-R-B.json
.claude/ui_snapshots/ux1b/.theme-batch-postapply-R.lease
.claude/ui_snapshots/ux1b/theme-batch-attempt-R.json
.claude/ui_snapshots/ux1b/theme-batch-postapply-tests-R.json
.claude/ui_snapshots/ux1b/theme-batch-rollback-intent-R.json
.claude/ui_snapshots/ux1b/theme-batch-reconciliation-R.json
.claude/ui_snapshots/ux1b/theme-batch-applied-R.json
.claude/ui_snapshots/ux1b/.theme-states-T.lease
.claude/ui_snapshots/ux1b/theme-state-capture-intent-T.json
.claude/ui_snapshots/ux1b/theme-state-capture-checkpoint-T.json
.claude/ui_snapshots/ux1b/theme-states-T/
.claude/ui_snapshots/ux1b/theme-state-candidate-T.json
.claude/ui_snapshots/ux1b/review-packet-theme-states-T.json
.claude/ui_snapshots/ux1b/review-intake/theme-states-T.json
.claude/ui_snapshots/ux1b/theme-state-manual-review-T.json
.claude/ui_snapshots/ux1b/theme-state-attestation-T.json
.claude/ui_snapshots/ux1b/.posttheme-T.lease
.claude/ui_snapshots/ux1b/posttheme-capture-intent-T.json
.claude/ui_snapshots/ux1b/posttheme-capture-checkpoint-T.json
.claude/ui_snapshots/ux1b/posttheme-T/
.claude/ui_snapshots/ux1b/posttheme-comparison-candidate-T.json
.claude/ui_snapshots/ux1b/review-packet-posttheme-T.json
.claude/ui_snapshots/ux1b/review-intake/posttheme-T.json
.claude/ui_snapshots/ux1b/theme-delta-manual-review-T.json
.claude/ui_snapshots/ux1b/theme-closure-T.json
```

The one no-replace lineage prechange binds the only `T` permitted for root `R`
and exclusively owns every shared root-keyed and `T`-keyed destination. Each
batch prechange binds that lineage and owns only its `B`-specific directory and
theme-batch intake. No glob or placeholder is an absence claim. A rejected
review burns only `B`; a new `B` may bind the same `R/T` lineage while the fixed
root-keyed apply attempt remains absent. A second `T` for the same `R` is an
invalid collision requiring a reviewed supersession.

`R` is exactly 64 lowercase hexadecimal characters. `B` and `T` are each one
ASCII path component matching `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`; no Unicode,
slash, empty, `.`/`..`, percent-decoded, or normalized alternative is accepted.
This same closed grammar applies wherever a marker or evidence object stores a
batch/theme-run ID.

### Authorized production batch

The later theme transaction may replace exactly, in this order:

1. `.streamlit/config.toml`;
2. `app.py`;
3. `ui/_design.py`;
4. `requirements.txt`;
5. `docs/ui-ux/quant-radar-ui-v2-ux1b-classification.json`.

The classification ledger is last on apply and first on rollback. No fifth
production/runtime path or sixth total path is authorized. All nine frozen
capture-stack members, both Task 6 manifests and 234 artifacts, migrated
selector postimages, routes, providers, API code, loaders, mutators, sessions,
and fail-soft behavior remain byte/behavior protected.

## Lock, descriptor, and FD contract

The fixed lock and capture lease are currently absent. Bootstrap first opens
only the retained workspace/parents and calculates a bootstrap-specific FD
budget that includes both future control FDs. It creates the lock through a
retained parent FD with `O_CREAT|O_EXCL|O_RDWR|O_NOFOLLOW|O_CLOEXEC`, mode
`0600`; immediately locks it exclusively, validates regular-file type,
executor uid/gid, `nlink=1`, size zero, and fsyncs file and parent. That exact
successful create+flock+reopen mints an in-memory `FreshLockGrant`. Only its
holder may continue while Tier 0 is absent. It then creates, validates, and
fsyncs the exact zero-byte `0600` capture lease and publishes Tier 0 binding
both absent preconditions and both created `FileRecord`s. If the lock exists
without authenticated Tier 0 and the current process has no `FreshLockGrant`,
bootstrap fails; a creator crash before Tier 0 requires a separately reviewed
recovery/new baseline and neither leaf is unlinked or silently adopted. All
later top-level commands open no-follow,
validate before and after a nonblocking exclusive `flock`, and exit `7` when
busy. The lock is disposition `retain_operational` and is never unlinked, which
prevents waiter split-brain.

Top-level commands acquire the global lock exactly once. Lock order is global,
then at most one operation-specific lease: Task 9 capture, postapply, theme
states, or posttheme. Internal functions acquire neither again. Commands that
do not own a runner/apply phase acquire no secondary lease. The Task 9 capture
coordinator holds both for the complete 36 -> gate -> 81 sequence. Runner
children use `close_fds=True` and inherit only standard streams plus the
Task 9 capture-lease FD. They inherit no global-lock, workspace, authority, evidence,
or staged-output FD. If the coordinator dies, the active runner retains the
lease until it exits; reconciliation returns `7` while that lease remains
locked.

For normal commands, after opening global/workspace and any required lease control descriptors
but before any temp, intent, or public output, the command enumerates `/dev/fd`,
closes the inventory FD, and confirms each numeric candidate with `fstat`.
Bootstrap performs the same calculation before lock/lease creation and counts
both planned descriptors in `protocolAdditional`. It computes:

```text
protocolAdditional = worstCaseUniqueRetainedLeaves + 2 * maxPathDepth + 64
peakOpenCount = baselineOpenCount + protocolAdditional
requiredSoft = max(baselineMaxFd + 1, peakOpenCount)
```

At most eight temporary inventory descriptors are allowed. The worst-case
cardinality is for the whole command, not the current phase. Both
`peakOpenCount` and `requiredSoft` must be `<=1536`, and `requiredSoft` must not
exceed the hard limit. Failure exits `5` before output. Only this process's soft
limit may rise; `finally` restores it after all protocol FDs close. The reserve
includes stage/public/parent reopens, receipt pipe, and subprocess pipes.

Every workspace leaf is opened relative to the retained workspace FD. Unsafe
components, symlinks, hardlinks, non-regular files, wrong owner/mode/link count,
inode/path swaps, duplicates, unexpected keys/leaves, size/hash drift, and
traversal fail closed. A non-cooperating process under the same Unix owner is
outside this protocol's threat model.

### Fresh staged-root validator

The only lock-free verifier mode is private and read-only:

```text
__verify-staged-root-fd --workspace-fd N --stage-fd N --receipt-fd N --nonce 32_HEX
```

It is not a top-level command. It must not acquire/open the lock or lease,
resolve the workspace by path, or publish. It reads only inherited workspace
and staged-root FDs and writes one bounded canonical receipt to the inherited
receipt FD. The parent retains the global lock and all decision FDs, passes
exactly those three FDs, and requires receipt nonce/device/inode/owner/mode/
link-count/size/SHA/validation parity. Timeout, stdout/stderr output, extra FD,
wrong nonce, or mismatch fails before root rename. A public-command process
started concurrently must exit `7` while this child still completes.

## Publication classes

All JSON is canonical UTF-8, no BOM or trailing newline. A regular evidence
publisher writes `.tmp.<kind>.<32-lowercase-hex>` with
`O_CREAT|O_EXCL|O_RDWR|O_NOFOLLOW|O_CLOEXEC`, mode
`0600`, fsyncs/rehashes/retains it, reauthenticates inputs, then commits with
Darwin `renameatx_np(..., RENAME_EXCL)`. Rename is the sole linearization point.
It fsyncs the parent and requires the public reopen to match the retained stage
inode and bytes. `EEXIST` never overwrites; exact regular evidence may be
content-reconciled after full input validation, while a mismatch exits `4`.
Postcommit confirmation loss exits `6`; a fresh verifier may reconcile exact
regular evidence. Temps never grant authority and are never silently adopted.

Consumptive claims are different: Task 9 intent, the root-keyed theme apply
attempt, and the two theme-capture intents mint their named in-memory fresh
grant only when this invocation commits, fsyncs, and reopens the absent claim
while retaining the same lock and inode.
An existing exact claim, content reconciliation, or lost response never mints
that grant and never authorizes a forward runner or write. A consumptive
postcommit confirmation loss exits `6`; later exact discovery or known exact
`EEXIST` is `EXHAUSTED`/exit `8`, never generic exit `0`. Task-specific
reconcilers may inspect an exhausted claim. `reconcile-task9` returns `0` only
after it publishes or read-only verifies the one complete passed terminal.
`reconcile-theme-batch` returns `0` only after it publishes or read-only
verifies the applied receipt; aborted and rolled-back terminals are `8`, and
unknown live bytes are `9`. `reconcile-theme-states` and
`reconcile-posttheme` return `0` only after an authenticated passed checkpoint
has been deterministically advanced to, or already has, its exact candidate
and review packet without rerunning the capture. For either capture reconciler,
an active lease is `7`, a postcommit publication uncertainty is `6`, and every
shorter/revoked/partial chain is `8`. These rules override generic idempotent
evidence behavior.

## Task 9 at-most-once capture transaction

The five fixed lifecycle leaves are:

```text
.claude/ui_snapshots/ux1b/recovery/capture-intent-20260719T211915Z.json
.claude/ui_snapshots/ux1b/recovery/capture-control-checkpoint-20260719T211915Z.json
.claude/ui_snapshots/ux1b/recovery/capture-pretheme-gate-20260719T211915Z.json
.claude/ui_snapshots/ux1b/recovery/capture-pretheme-checkpoint-20260719T211915Z.json
.claude/ui_snapshots/ux1b/recovery/capture-terminal-20260719T211915Z.json
```

`capture-task9` is the sole command allowed to start either frozen runner. It
holds global lock, capture lease, and fresh intent grant while it executes:

```text
publish intent
-> run exact 36 postcontrol argv
-> authenticate 36/36, 72 artifacts, 73 leaves
-> publish control checkpoint
-> reauthenticate preflight/source/stack/runtime
-> publish pretheme gate
-> run exact 81 pretheme argv
-> authenticate 81/81, 162 artifacts, 163 leaves
-> publish pretheme checkpoint
-> reauthenticate the complete chain
-> publish terminal passed
```

The two `RunnerPlan.execution.argv` arrays are exactly:

```text
[".venv/bin/python","scripts/ui_ux_snapshot_matrix.py","--profile","ux1b-selection-controls","--phase","postcontrol","--browser","chromium","--out-dir",".claude/ui_snapshots/ux1b/recovery/postcontrol-controls-20260719T211915Z","--no-prompt","--json"]
[".venv/bin/python","scripts/ui_ux_snapshot_matrix.py","--profile","ux1b-full-pages","--phase","pretheme","--browser","chromium","--out-dir",".claude/ui_snapshots/ux1b/recovery/canonical-pretheme-20260719T211915Z","--no-prompt","--json"]
```

Both plans use the `CaptureRunnerPlan` arm. Their exact
`kind|stage|destination|expectedMode|expectedPhase|expectedCount` tuples are
`capture|postcontrol|.claude/ui_snapshots/ux1b/recovery/postcontrol-controls-20260719T211915Z|ux1b-selection-controls|postcontrol|36`
and
`capture|pretheme|.claude/ui_snapshots/ux1b/recovery/canonical-pretheme-20260719T211915Z|ux1b-full-pages|pretheme|81`,
respectively.

No shell interpolation or alternate executable/flag/order is accepted. Each
plan has cwd `.`, the exact closed capture environment below, stdin `devnull`,
timeout `14400`, stdout/stderr limits `67108864` bytes each, a fresh process
group, `passFds:["lease"]`, and capability `capture-coordinator-v1`. The
processFamily arm is exactly `outer_pgid`; it contains no environment key or
token hash. The
outer plan's `seatbeltProfileSha256` is null because the frozen runner builds
and records its own authenticated inner profiles. The preflight CLI path
argument must equal its one derived fixed path.

The intent binds preflight, nonce, lease identity, exact two argv arrays,
destinations, source, stack, and runtime. Checkpoints bind exact runner exit-0
receipts and terminal bundles. The gate binds the control checkpoint and fresh
input validation. Terminal has one fixed path and status `passed` or `revoked`;
separate success/failure filenames are forbidden. The root accepts only a
`passed` terminal. Passed manifests without this chain grant nothing.

Durable transitions are exact:

| State | Allowed next event | Result |
| --- | --- | --- |
| eligible | current process freshly commits intent | started |
| started | same process proves 36 bundle and commits checkpoint | control_verified |
| control_verified | same process commits fresh gate | pretheme_authorized |
| pretheme_authorized | same process proves 81 bundle and commits checkpoint | pretheme_verified |
| pretheme_verified | same or fresh reconciler validates full chain | terminal passed |
| any partial state after intent owner/lease ends | reconciliation | terminal revoked |
| passed | verify/reconcile | passed, no runner |
| revoked | any | exit `8`, no runner |
| invalid collision | any | exit `4` |

Unlisted transitions reject. A crash before intent commit leaves the state
eligible; a crash after intent commit burns the ID. An active inherited lease returns `7`.
Only a fully published pretheme checkpoint can be reconciled to passed. On
SIGINT/SIGTERM the owner drives the exact outer-family controller. An exact
quiescent receipt permits it to publish a revoked terminal whose reason is the stage-specific
`control_nested_quiescence_unverified|pretheme_nested_quiescence_unverified`,
then exit `130`; it does not claim inner frozen families were observed. Failure
to obtain that receipt leaves the durable prefix untouched, emits only the
same stage-specific diagnostic, and exits `9`. After owner loss or SIGKILL,
lease-aware reconciliation publishes the same no-authority/manual-audit
classification without claiming outer or inner closure. No new process continues a
missing stage, and no future capture amendment may run until an operator has
separately audited host processes.

## Source and runtime authority

This replacement directly defines its source/runtime policy; no unimported
section of the rejected draft supplies missing semantics. The canonical mirror
include rules are exactly `.streamlit/config.toml`, `app.py`, `api/**/*.py`,
`scripts/**/*.py`, `ui/**/*.py`, and
`docs/ui-ux/quant-radar-ui-v2-baseline.json`. Exclusions are exactly
`.agents/**`, `.claude/**`, `.git/**`, `.venv/**`, `**/.env*`,
`**/__pycache__/**`, `**/*.db`, `**/*.duckdb`, `**/*.key`, `**/*.pem`,
`**/*.pyc`, `data/**`, and `reports/**`. Glob expansion must produce unique,
sorted, regular no-link files; a declared include with no match fails.

Encoding and authentication are exactly the frozen
`scripts/ui_ux_isolation.py` source-mirror implementation bound by capture-stack
member SHA `cec1c7b6a982d34b7f84bf958cc06ddce601847947b840d754166b1f4d753497`;
the verifier reauthenticates that member before calling its closed
`build_source_mirror` / `authenticate_source_mirror` behavior. It does not
invent a second digest algorithm. Postcontrol and pretheme maps must equal one
another, preflight, and each new manifest's start/end source digest.

The supplemental projection is the unique path-sorted set consisting of
`requirements.txt`, `Makefile`, the fixed recovery Markdown, the frozen base
draft, this plan, its ledger, and every workspace-relative path in the authority
table, minus any path already present in the mirror. Before/post sets are
identical. Only `requirements.txt` and the classification authority may change
outside the mirror; only config/app/design may change inside it. All other
records remain exact. The classification preimage is the table hash
`c6c27801ffbd7aeffd86514156ba2e4c81f0699b78e6db7278dfdf72d3d6a77b`
with `state:"pending"`; the candidate supplies the reviewed exact
`state:"accepted"` postimage.

The canonical Task 6 page anchor is
`.claude/ui_snapshots/ux1b/recovery/precontrol-pages-20260719T211915Z/manifest.json`
at SHA `a72aa7cac95bfbd70b23a2033c49a0d03aa500204bd66ec738b757c2295e6404`,
81 captures, 162 artifacts, and 163 leaves. The control anchor is
`.claude/ui_snapshots/ux1b/recovery/precontrol-controls-20260719T211915Z/manifest.json`
at SHA `06f7320b0d56e54d584399e281a307a713b23a349207ac7b35b6bd1ee14154be`,
36 captures, 72 artifacts, and 73 leaves. Their historical source digest is
`4eeb3629fbd83ef9e61f553cd3eae93e7b8ede4b925e45774ece99847dfce8a5`.
The four pristine runtime preimages are the exact rollback-source config/app/
design/requirements rows in the authority table. Narrow sidecar normalization
is only the imported hashed section above.

The historical selector-mode source follows this exact additional rule.

Retain and authenticate the recovery prechange, archive, archive manifest, and
selector delta using their authority hashes above. The archive is additionally
exact size `1182208`, mode `0600`, uid `501`, gid `20`, and `nlink=1`; its
manifest is size `6367` with the same mode/uid/gid/link count. Parse the tar
from a duplicate of its retained read-only FD and never extract it. For each
exact selector path below, require one exact-name, normalized POSIX-relative,
regular member; empty linkname; no link; mode `0644`; uid `501`; gid `20`;
exact header size; and payload SHA equal to both recovery prechange and selector
delta. Duplicate requested names fail. Nonrequested members are ignored only
because the exact outer archive digest authenticates all bytes; the archive is
not falsely claimed to contain only the requested rows.

| Path | Legacy size | Legacy SHA-256 | Tar mode | Mirror mode |
| --- | ---: | --- | --- | --- |
| `ui/risk_guard.py` | 19820 | `2e81f16c9e828bbf5a58613b847e0dd0a9de32375e4aeba2e2ea17d7ee194e83` | `0644` | `0444` |
| `ui/institutions.py` | 1433 | `a02481a9f5aa9cc2137d5f919c7db6d6a51bd649991082ab443c6e22360d7361` | `0644` | `0444` |
| `ui/options_cockpit.py` | 80104 | `9b7e918f0b5c0b69041f26603f50db2c1fccac929c94e25bb1602d2e694d1a2f` | `0644` | `0444` |
| `ui/radar.py` | 15554 | `4428b8ab47ce51421f8bb4f0ec47365f10ff8b97208606cf2cd42d6ac650979a` | `0644` | `0444` |
| `ui/knowledge_graph.py` | 26285 | `22c293b7e28fd6fc9d0ed5ea4a1adebaa277e5d7c4201d0166a1ef4759c82bf6` | `0644` | `0444` |
| `ui/ai_chat.py` | 23226 | `b838db07fe125e061a39e7249d1a42611562e8cd32bf8a0420574bd4267f28d2` | `0644` | `0444` |
| `ui/retro_analysis.py` | 36853 | `2fb1b58b774e3c9154bc2bf25254fbe321aa19ca981bd657c5261f29f881f604` | `0644` | `0444` |
| `ui/analytics_db.py` | 43963 | `a63c08fcbf888620c9f9440d9219b40d412825068bf36020a1346c127cfffa58` | `0644` | `0444` |
| `ui/stock_checkup.py` | 25701 | `68e448fd012ff5ffbc988b8f5f7a4dc96acb264cdea8b28134ce9c0476777d97` | `0644` | `0444` |

Preflight and root embed these nine `historicalSelectorModes` records. Starting
from the descriptor-built preflight map, remove exactly the two then-absent
handoff script paths, substitute the nine legacy SHA/size/mode records, use the
existing source-mirror encoder, and require digest
`4eeb3629fbd83ef9e61f553cd3eae93e7b8ede4b925e45774ece99847dfce8a5`.
Current modes, guessing, and brute-force selection are forbidden.

Runtime remains CPython `3.11.15`, Streamlit `1.57.0`, Playwright `1.60.0`,
Chromium `148.0.7778.96` revision `1223`, macOS `26.5` build `25F71`, Darwin
`25.5.0`, and `macOS-26.5-arm64-arm-64bit`. The lifecycle coordinator's direct
execution authority resolves only to these exact regular leaves;
developer-invoked read-only verification commands outside a lifecycle
transaction grant no authority:

| Purpose | Absolute path | SHA-256 | Size | Mode / uid / gid / device / inode / nlink |
| --- | --- | --- | ---: | --- |
| Python | `/Users/ken/.local/share/uv/python/cpython-3.11.15-macos-aarch64-none/bin/python3.11` | `68100c5188b837802c7ae52398389d121b1c063ed244dec11649775b539c3a30` | 17204528 | `0755 / 501 / 20 / 16777229 / 595896 / 1` |
| Seatbelt | `/usr/bin/sandbox-exec` | `8857d087219f0f39d3e3c163e5d0a0aed690cc22f34b50c7eee3d74f93e69688` | 102560 | `0755 / 0 / 0 / 16777229 / 1152921500312572721 / 1` |
| Process observer | `/bin/ps` | `472992c470606d28f577590decfecd7f4a20f832fd92c671bebc6d44790b5d02` | 170816 | `4755 / 0 / 0 / 16777229 / 1152921500312571423 / 1` |

The invoked spelling is nevertheless the repository
`.venv/bin/python` symlink, not the resolved base interpreter: only that
launcher activates installed Streamlit/FastAPI/Playwright. The receipt binds
its target
`/Users/ken/.local/share/uv/python/cpython-3.11-macos-aarch64-none/bin/python3.11`
and lstat mode/uid/gid/device/inode/nlink/size
`0755/501/20/16777229/946523/1/80`; the external uv alias
`/Users/ken/.local/share/uv/python/cpython-3.11-macos-aarch64-none` targets
`/Users/ken/.local/share/uv/python/cpython-3.11.15-macos-aarch64-none` with
`0755/501/20/16777229/598229/1/68`. The receipt also binds exact
`pyvenv.cfg` SHA
`1a8123ff9ae832ec606e44c42d25b3c3c59a75e17cfc396480304cc75583d1cd`,
size/metadata `175/0644/501/20/16777229/946535/1`, and the closed parsed values
`home:/Users/ken/.local/share/uv/python/cpython-3.11-macos-aarch64-none/bin`,
`implementation:CPython`, `uv:0.11.16`, `version_info:3.11.15`, and
`include-system-site-packages:false`, plus the resolved CPython row above.
Candidate-regression browser commands also
set exact `PLAYWRIGHT_BROWSERS_PATH=/Users/ken/Library/Caches/ms-playwright`
and `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`; an inherited or HOME-derived browser
path is forbidden.

Candidate POST-018 is intentionally separate from the frozen capture runtime.
Playwright `1.60.0` reports the Chrome-for-Testing app through
`chromium.executable_path`, but its unqualified `chromium.launch(headless=True)`
actually launches this candidate-only headless-shell runtime:
`/Users/ken/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64`.
Its reviewed double-pass tree digest is
`51a3c1288a5bb4e361033b76e8a7c4c2668249584969b28711c5bba36cbca30c`
and root mode/uid/gid/device/inode is
`0755/501/20/16777229/968500`. Its sole process-exec leaf is
`chrome-headless-shell` at SHA
`aa25f2e795c02d5cb5ef5d6987745cc5bbe7d8bea58827390c7a4c81c8d2dd7b`,
size `157792208`, mode/uid/gid/device/inode/nlink
`0755/501/20/16777229/968506/1`. Executable-mode dylibs remain authenticated
tree-readable load images, not process-exec grants. This authority is used only
by candidate regression/probes and never added to the frozen capture stack.

The frozen isolation contract alone delegates descendant execution to the
authenticated Playwright Node driver and exact Chromium app-bundle executable
set described by `captureRuntime` below. The main Chromium member remains
`/Users/ken/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing` at SHA
`2447c7bdea8e8ad38b52594f1ba53e18821c05445e8a07ad1cf3b0f23931d89d`,
size `68624`, mode/uid/gid/device/inode/nlink
`0755/501/20/16777229/967800/1`; the Node driver is
`.venv/lib/python3.11/site-packages/playwright/driver/node` at SHA
`3200fbd9f7fd4410426dd541e10d1ab829d3472f270d743c7fabd1696c03fe32`,
size `119944608`, mode/uid/gid/device/inode/nlink
`0755/501/20/16777229/967447/1`; `/bin/ps` resolves to its exact system leaf at
SHA `472992c470606d28f577590decfecd7f4a20f832fd92c671bebc6d44790b5d02`,
size `170816`, mode/uid/gid/device/inode/nlink
`4755/0/0/16777229/1152921500312571423/1`. The verifier derives versions from the venv,
installed metadata, and owned Chromium bundle, and requires every fixed value
and runtime-set digest. Runtime drift blocks preflight and requires a reviewed
replacement package; no implicit executable allowlist exists.

The closed capture-coordinator environment is exactly this key set and no
inherited key: `PATH=/usr/bin:/bin:/usr/sbin:/sbin`, `LANG=C.UTF-8`,
`LC_ALL=C.UTF-8`, `TZ=UTC`, `HOME=<PRIVATE_HOME>`,
`TMPDIR=<PRIVATE_TMP>`, `TMP=<PRIVATE_TMP>`, `TEMP=<PRIVATE_TMP>`,
`XDG_CACHE_HOME=<PRIVATE_CACHE>`, `XDG_CONFIG_HOME=<PRIVATE_CONFIG>`,
`XDG_DATA_HOME=<PRIVATE_DATA>`, `PYTHONHASHSEED=0`,
`PYTHONNOUSERSITE=1`, `PYTHONDONTWRITEBYTECODE=1`,
`PYTHONPATH=<AUTHENTICATED_WORKSPACE>`,
`PLAYWRIGHT_BROWSERS_PATH=/Users/ken/Library/Caches/ms-playwright`,
`PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`,
`STREAMLIT_BROWSER_GATHER_USAGE_STATS=false`,
`NO_PROXY=127.0.0.1,localhost,::1`, and
`no_proxy=127.0.0.1,localhost,::1`. For each frozen capture runner, the five
private HOME/TMP/XDG directories are distinct mode-`0700` owned direct children
of `RuntimeReceipt.tempRootParent` and are descriptor-bound in the execution
plan; placeholders are canonical field references, not literal subprocess
values or CLI input. `PYTHONHOME`, every
proxy variable, credential-like key, and every unlisted variable is absent.
Candidate commands and capability probes use the `token_pgid` process-control
arm below. For each such launch, the imperative shell generates one unique raw
`QUANT_RADAR_UX1B_PROCESS_TOKEN=ux1b_<64hex>`, verifies the plan's
`tokenSha256`, and adds that sole secret key to the actual spawn environment.
The raw token is never serialized or logged by the protocol, reused, or
accepted from inherited input. The initial runner always receives it; a descendant inherits it unless
authenticated source deliberately builds a closed replacement environment.
The only authenticated source-reviewed replacement-environment builders that
intentionally omit the token are the synchronous POST-017 fixture helper and
POST-020 theme helper. Both remain in the initial process group and are reaped
before their parent returns. POST-018's Python, Playwright Node, and main
headless-shell launches preserve the injected marker. Internal headless-shell
helpers are trusted as part of the exact authenticated `candidateRuntime`; this
is not a complete descendant-enumeration claim. Static and runtime gates reject
any source-reviewed path that both drops the token and invokes `setsid`,
`setpgid`, `start_new_session`, or an equivalent process-group escape.
Candidate closure means the union of
the original PGID and same-UID exact marker rows—not an adversarial whole-host
family claim—and both sets must be empty before publication. Darwin `ps eww`
flattens argv and environment, so a marker row is conservatively defined by the
exact bounded command-field token `(?:^| )QUANT_RADAR_UX1B_PROCESS_TOKEN=<raw-token>(?: |$)` using literal ASCII spaces; it is not represented as proof that a descendant's
current environment owns the key. Any same-UID process exposing that
unpredictable raw marker in argv or environment is intentionally treated as
part of the family. Authorized code never places it in argv, and a hostile
same-UID process that learns/spoofs it is already outside the stated threat
model. Raw command bytes are hashed then discarded and never enter evidence.

Frozen capture runners instead use the `outer_pgid` arm. They intentionally
mint independent inner app/browser tokens and process groups under the frozen
isolation contract, so no outer token is injected and the outer receipt proves
only the runner PGID. A passed capture checkpoint additionally requires every
inner frozen manifest receipt to prove its own exact quiescence. An abnormal,
signaled, timed-out, overflowed, or owner-lost capture has no `RunnerReceipt`:
the active coordinator drives the exact signal/no-signal controller for only
the outer PGID when it still exists, while an owner-lost reconciler sends no
signal. Either path burns the lineage, records
`nested_quiescence_unverified`, and requires a manual process audit before any
future amendment may authorize another capture; inability to obtain an outer
family receipt additionally exits `9`. It never claims or automatically
reconciles complete nested cleanup.

Throughout this plan, a required manual host-process audit has one safe default
runbook: a trusted Quant Radar maintainer stops lifecycle commands, performs a
full host reboot so all live processes terminate and all zombies are reaped,
then records operator/reboot time in an external operations log that grants no
lifecycle authority. A logout, process-name/PID scan, or best-effort kill is
not an audit substitute. Capture lineages remain burned after that runbook;
only the candidate-session rule below permits the same B/T after removal.

Every process-control plan's `quiescenceTimeoutSeconds` is exactly `25`, with
TERM/KILL grace values `3/7`; the observer argv is
exactly `["/bin/ps","eww","-axo",
"pid=,uid=,pgid=,stat=,xstat=,command="]`, with stdin `devnull`, limits
`4194304/65536`, timeout `2`, wait timeout `0.5`, fresh process group, empty
pass-FDs, and environment exactly `PATH=/usr/bin:/bin:/usr/sbin:/sbin`,
`LANG=C`, `LC_ALL=C`. The authenticated parser applies the exact closed
observation schema below; raw process-table bytes and the token never enter
public evidence.

The observer is a distinct directly owned `/bin/ps` process, never a marker-
matched descendant. Its pipes are nonblocking and temporarily registered in
the same controller-owned bounded selector that continuously drains the runner
streams, so no reader thread can keep the coordinator alive. On its timeout,
either stream overflow, or wait failure, the observer result is invalid and can
never produce a `ProcessObservationSample`. Its separate cleanup authority
permits exactly one `killpg(observerPid,SIGKILL)` where observerPid equals the
observer's freshly created PGID. `ESRCH` is tolerated only as an already-exited
cleanup race. Darwin `EPERM` is tolerated only provisionally: the immediately
following bounded direct-child wait must return that exact observer PID with a
valid wait status, thereby proving the already-exited owned-child case; any
other wait result or expiry makes `EPERM` a cleanup failure. Neither tolerated
error makes the observation valid. The controller drains until EOF and waits
the direct child for at most the exact `waitTimeoutSeconds`; at that boundary
it deregisters and closes only the observer's local nonblocking pipe FDs. Any
other signal target/error, missing EOF/reap, or cleanup timeout yields no family
receipt and enters the owning candidate-session/capture-lineage manual gate.
This observer-only arm never calls `os.kill`, never targets the runner group,
marker PID, or detached marker PGID, and never turns a failed observation into
evidence.

The exact outer capture capability object is
`{"id":"capture-coordinator-v1","network":"delegated-frozen-isolation",
"execRoles":["resolved-python","sandbox-exec","ps-observer"],"readRoles":["workspace","venv",
"base-python-runtime","system-runtime","browser-runtime"],
"writeRoles":["bound-destination",
"fresh-private-environment"],"environmentId":"capture-v1",
"profileTemplateSha256":null}`. It grants the exact runner launch, Seatbelt
wrapper, and read-only process observer; the frozen inner isolation contract
owns the app/browser family-wide executable union and nested quiescence proof.

## Review packet and external assertion contract

The verifier never invents reviewer identity, time, decision, verdict,
explanation, or finding. A review is an authenticated external assertion, not
technical proof of a person's real-world identity. Machine review material is
first published as an immutable packet; only then may an operator author one
canonical JSON intake below the fixed excluded root
`.claude/ui_snapshots/ux1b/review-intake/`. The exact-copy publisher validates a
retained intake FD and stages the same bytes without rewriting them. Intake and
destination are distinct one-link regular inodes; alias, link, absolute path,
or path escape fails.

`quant-radar-ui-ux-review-packet/v1` has exactly:

```text
schemaVersion,status,kind,rootContract,lineageId,machineReport,prompt,
promptSha256,inputs,inputsSha256,itemSetSha256,items
```

`status` is `review_required`. `promptSha256` hashes canonical prompt bytes;
`inputsSha256` hashes the canonical path-sorted `ArtifactRef` array; and
`itemSetSha256` hashes the canonical sorted item-ID array. Packet production is
the sole source of prompt/input/item expectations. Review intake has exactly:

```text
schemaVersion,kind,status,reviewedAt,reviewer,packet,promptSha256,inputs,
inputsSha256,itemSetSha256,decision,items,findings
```

`reviewedAt` is bounded UTC RFC3339 seconds. `status` and `decision` are both
`accepted` or both `rejected`. Packet/input/hash values and the exact item-ID
set must match; machine subject records are not duplicated into the human
decision items. Accepted review has no unresolved High/Medium finding. The
publisher accepts these four kinds and exact input sets:

| Kind | Reviewer type | Exact machine inputs | Items |
| --- | --- | --- | ---: |
| `control-migration` | `human` | four manifests plus migration report | 117 pairs |
| `theme-batch` | `independent-code-reviewer` | root, batch prechange, bundle manifest, candidate, patch, combined scratch/candidate-regression test report | five file changes |
| `theme-states` | `human` | root, applied receipt, state candidate, theme manifest | 12 visuals |
| `posttheme` | `human` | root, applied receipt, state attestation, comparison, pretheme manifest, posttheme manifest | 81 pairs |

The exact theme-batch prompt is:

```json
{"checks":["scope_exact","semantic_theme_only","fail_soft_preserved","tests_passed","forward_classification_exact"],"decisionQuestionId":"accept_theme_batch_v1","kind":"theme-batch","schemaVersion":"quant-radar-ui-ux-review-prompt/v1"}
```

The other exact canonical prompts are:

```json
{"checks":["identity_exact","selection_semantics_preserved","geometry_deltas_explained"],"decisionQuestionId":"accept_control_migration_v1","kind":"control-migration","schemaVersion":"quant-radar-ui-ux-review-prompt/v1"}
{"checks":["all_states_visible","contrast_and_focus_accepted","no_danger_recoloring","no_layout_regression"],"decisionQuestionId":"accept_theme_states_v1","kind":"theme-states","schemaVersion":"quant-radar-ui-ux-review-prompt/v1"}
{"checks":["semantic_theme_only","content_and_layout_preserved","changed_visuals_explained","unchanged_hashes_confirmed"],"decisionQuestionId":"accept_posttheme_v1","kind":"posttheme","schemaVersion":"quant-radar-ui-ux-review-prompt/v1"}
```

Machine pair packet items are exactly
`{id,before,after,dimensions,changed}`. Machine standalone theme-state packet
items are exactly `{id,artifact,dimensions}`. Machine theme-batch packet items
are exactly `{id,path,preimage,postimage,patchSectionSha256}`. They contain no
verdict, explanation, decision, or finding. Human review decision items for all
kinds are exactly `{id,verdict,explanation}`; their IDs must equal the packet
set with no duplicate/missing item.

The patch and its per-item digest have one exact encoder. For each of the five
apply-order paths, retained pre/post bytes are strict UTF-8 and the section is
`"".join(difflib.unified_diff(pre.splitlines(keepends=True),
post.splitlines(keepends=True),fromfile="a/"+path,tofile="b/"+path,
fromfiledate="",tofiledate="",n=3,lineterm="\n")).encode("utf-8")` under the
authenticated runtime. Every section must be nonempty; `theme.patch` is their
byte concatenation in apply order. `patchSectionSha256` is SHA-256 over ASCII
domain `quant-radar-ui-ux-theme-patch-section/v1\0`, then UTF-8 path, one NUL,
then that exact section. No parser rediscovery of section boundaries is
authoritative. The golden path `app.py`, pre bytes `x = 1\n`, and post bytes
`x = 2\n` produce section bytes
`--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n` and digest
`35b9d371ad9e0e672e7f681d4f56da727b798f645442e8822a369640b16e0190`.

Pair before/after and standalone artifact values are `ArtifactRef`s;
dimensions is `Dimensions`; changed is a JSON boolean whose value must equal
the before/after SHA comparison. JSON booleans are never accepted as integers.
Review `inputs` are `ArtifactRef[]`; batch item pre/post values are
`SourceRecord`s; reviewer is exactly `{type,id}`; and findings are exact
`Finding[]`. Packet `rootContract` is required null for control migration and
an exact `ArtifactRef` for the other kinds. `machineReport` is always the exact
report/candidate `ArtifactRef`. Pair IDs are the authenticated capture IDs;
theme-batch IDs are their exact workspace paths; theme-state main IDs are the
capture IDs and crop IDs are `<captureId>::<supplementalArtifactId>`.
`lineageId` is recovery ID for control migration, batch ID for theme batch, and
theme run ID for theme-states/posttheme. Review intake remains external/user
owned before publication and becomes `retain_immutable` evidence afterward; no
rollback path deletes or rewrites it.
`unchanged_by_hash` is valid only for a pair whose packet hashes are equal;
all other accepted items require `accepted` and a bounded explanation.
`rejected` requires a bounded explanation and makes the whole review rejected.

## Root handoff contract

The root schema is `quant-radar-ui-ux-formal-theme-handoff/v2` and has exactly:

```text
schemaVersion,status,recoveryId,authorizationRecord,baseDraft,replacementPlan,
traceability,authorities,preflight,captureStack,task6,task9,migration,
historicalSelectorModes,sourceProjection,supplementalProjection,runtimeReceipt,
themeBatchBoundary,allowedChanges
```

It binds the imported frozen draft, replacement package, full upstream set,
preflight, capture stack, canonical Task 6 anchors, Task 9 terminal chain, four
manifests and all 468 after-artifacts, migration report/review, historical
projection, current source/runtime, and exact pristine theme boundary.
`task9` is exactly
`{intent,controlCheckpoint,prethemeGate,prethemeCheckpoint,terminal,postcontrol,pretheme}`.
`themeBatchBoundary` is exactly `{paths,preimages}` with the five ordered paths
and five `SourceRecord` preimages. `allowedChanges` remains exactly four
production paths plus the classification evidence path. The immutable root is
never edited, deleted, or used as a rollback target.

Root candidate schema `quant-radar-ui-ux-formal-handoff-candidate/v2` repeats
all decision-bearing root inputs and contains `proposedContract` plus
`proposedContractSha256`. `proposedContract` is exactly the complete closed
`quant-radar-ui-ux-formal-theme-handoff/v2` root object defined above, and
`proposedContractSha256` is SHA-256 of that object's no-newline canonical JSON
bytes with no domain prefix or suffix. The root publisher stages exactly those
same bytes, uses the private fresh-child validator, then commits the same
inode. A terminal manifest or candidate alone grants nothing.

## Theme batch lifecycle

Standalone `authorize-theme-batch` is removed. No process may convert a prior
authorization result into live writes. For root SHA `R`, batch ID `B`, and theme
run ID `T`, `init-theme-batch` first publishes or exact-reconciles the single
`theme-lineage-prechange-R.json` binding `T`, then publishes the disjoint exact
`theme-batch-prechange-R-B.json`, then creates:

```text
.claude/ui_snapshots/ux1b/theme-batches/R/B/
  work/
  sealed/
    .quant-radar-theme-batch-owner
    pre/{00-config.toml,01-app.py,02-design.py,03-requirements.txt,04-classification.json}
    post/{00-config.toml,01-app.py,02-design.py,03-requirements.txt,04-classification.json}
    theme.patch
    test-report.json
    bundle-manifest.json
  candidate.json
  review-packet.json
  review.json
```

`work/` is mutable authoring scratch and grants nothing. It initially contains
five copies of the pristine preimages. The implementation operator modifies
only those copies. `seal-theme-batch` retains their FDs, rejects extras/links/
unsafe modes/drift, creates independent sealed pre/post inodes, generates a
timestamp-free unified diff, runs the seven exact pure scratch checks, then
materializes and tests an isolated candidate workspace as defined below. Only
the combined passed `ThemeBatchTestReport` becomes `test-report.json`.
The command then publishes three ordered, independently durable objects: first
the 14-leaf sealed directory by directory `RENAME_EXCL`, then `candidate.json`
by the regular no-replace publisher, then deterministic `review-packet.json`
by that same regular publisher. This is a resumable three-step transaction,
not one atomic rename. Exact committed evidence may be reconciled; neither of
the first two prefixes authorizes live writes, and only the fully reopened
three-object chain lets sealing return success.

The candidate workspace is a fresh private mode-`0700` directory below the
authenticated temp parent, never the live repository. Its descriptor-built
manifest copies every unique safe regular workspace leaf from the catch-all
include `**` except exactly `.git/**`, `.venv/**`, `data/**`, `reports/**`,
`**/.env*`, `**/__pycache__/**`, `**/*.db`, `**/*.duckdb`, `**/*.key`,
`**/*.pem`, `**/*.pyc`, every `.tmp.*` leaf, and the current
`.claude/ui_snapshots/ux1b/theme-batches/R/B/**` subtree. Any other symlink,
special file, unsafe mode, hardlink, path race, file above 512 MiB, or total
above 1 GiB fails before a test launch. Copies are independent owned inodes;
every traversed directory, including an empty one, is independently created and
recorded with path/mode/owner/device/inode;
the five sealed postimages replace their matching copies before the manifest
digest is finalized.

Each overlay row maps one live apply path to its sealed `post/<path>` record
and candidate `<path>` record. Sealed and candidate SHA/size/mode/uid/gid must
match; both are owned one-link regular files; their `(device,inode)` pairs must
differ; candidate path equals the live relative path; sealed path equals its
exact sealed `post/` mapping. Full `FileRecord` equality is forbidden because
the candidate copy is intentionally an independent inode. The five overlay
rows follow apply order and each equals the matching records already present in
the sealed bundle and candidate manifest respectively.

The sole synthetic symlink is `candidate/.venv` to the authenticated live
`.venv`, recorded as `venvBridge`; Seatbelt permits it read/execute only and
denies every write through it. Candidate commands resolve their relative script
paths inside the candidate root, use the live venv launcher as argv[0], and may
write only to their capability's named candidate subpaths and fresh private
HOME/TMP/XDG roots. After
the suite, the verifier removes only its own stdout/stderr files outside that
root, descriptor-enumerates the candidate again, and requires the exact same
root identity, path-sorted directory identities/modes, regular-file
identities/content/modes, and sole bridge symlink, with `extraEntries:[]`.
Empty-directory addition/removal and directory-mode drift therefore fail just
like a file mutation. A test may create and clean fixtures, but any surviving
source/evidence mutation, including an auth-pending file, blocks sealing
without touching live bytes.
`protectedClosures.socialCli` contains exactly these five path-sorted records
from the authenticated preflight source projection:
`scripts/agent_reach_social_bridge.py`,
`scripts/influencer_roster_runtime.py`, `scripts/sentiment_free.py`,
`scripts/social_intelligence.py`, and
`scripts/test_social_intelligence.py`. Its digest is recomputed before and
after candidate tests. None is an overlay path.
`protectedClosures.snapshotMatrix` contains exactly the path-sorted
`scripts/test_ui_ux_snapshot_matrix.py` record followed by the nine exact
capture-stack members `scripts/ui_ux_browser_worker.py`,
`scripts/ui_ux_evidence.py`, `scripts/ui_ux_fixture_app.py`,
`scripts/ui_ux_fixtures.py`, `scripts/ui_ux_isolation.py`,
`scripts/ui_ux_selection_fixture_app.py`, `scripts/ui_ux_snapshot_matrix.py`,
`scripts/ui_ux_theme_fixture_app.py`, and `scripts/ui_ux_theme_matrix.py`.
The test record is additionally fixed to SHA-256
`1727c8a4fdec6c485bf08152d8eb1c1c3667b041ea4596899def981634c374be`;
the other nine equal the authenticated frozen capture stack. Its digest is
also recomputed before/after, and none of the ten paths is an overlay.

The sealed directory is built as a private `.tmp.sealed.<32hex>` sibling with
mode `0700`. All leaves/subdirectories are fsynced and descriptor-enumerated
before its private parent is fsynced. The complete directory is committed with
`renameatx_np(..., RENAME_EXCL)`, the retained destination parent is fsynced,
then the directory is reopened through that parent and required to be the same
inode containing the exact 14 leaves/inodes/hashes. A post-rename fsync/reopen
uncertainty exits `6`. `EEXIST` never merges directories. A fresh process may
reconcile only an exact complete sealed namespace and must fsync its retained
parent before success; partial temp directories remain non-authoritative.

After reopening sealed, the coordinator derives candidate bytes solely from
authenticated root/prechange/sealed/test/runtime inputs, publishes them with
the regular no-replace/fsync/same-inode-reopen primitive, then derives and
publishes the packet from that exact candidate. Each postcommit uncertainty
exits `6` before the next publication. The committing owner requires public
same-inode equality to its retained stage; an `EEXIST`/fresh reconciler instead
requires exact deterministic bytes, safe owner/mode/nlink, and stable
descriptor reopen without pretending to know another creator's inode.
Transient records nested in sealed `test-report.json`—candidate workspace/root/
directory/file/symlink and overlay candidate inodes, canary, process IDs, and
process observations—are immutable historical facts. Only the original sealing
owner validates them against live session descriptors before directory commit.
After sealed publication, a fresh reconciler reopens only persistent sealed
leaves and their referenced persistent authorities, validates those transient
records by closed schema/digest/cross-field rules, and must neither reopen nor
trust any former session path. Candidate and packet bytes therefore remain
identical whether the old session was fully deleted or survives as an
untrusted SIGKILL orphan.
Reconciliation is the
following closed prefix matrix:

| Exact public state | Reconciliation action |
| --- | --- |
| all three absent; no matching candidate-session entry | one fresh sealing owner may authenticate work, create its durable session marker, run tests, and attempt sealed publication; unrelated private/precommit trees grant nothing |
| all three absent; any schema-valid owned candidate-session entry | write/delete nothing; `candidate_nested_quiescence_unverified`, exit `9`, trusted-operator full-host-reboot runbook required |
| all three absent; any malformed, wrong-type/owner/mode, or invalid-marker matching candidate-session entry | write/delete nothing; collision `4`; this plan grants no removal authority and a separately reviewed ownership resolution is required |
| sealed exact; candidate/packet absent | reopen sealed, deterministically publish or reconcile candidate, then packet |
| sealed and candidate exact; packet absent | reopen both and deterministically publish or reconcile packet |
| sealed, candidate, and packet exact | reopen the complete chain; return success without rerunning tests |
| candidate without sealed, packet without candidate, any partial sealed tree, or any mismatching/colliding object | write nothing; collision `4` |

Only transitions down that table are permitted. A lost response at directory
rename, candidate publication, packet publication, any parent fsync, or any
same-inode reopen is resolved by a fresh process observing one exact row; it
never reruns the 37 commands after exact sealed publication and never replaces
an existing byte.

Canonical change types are:

```text
MaterializedSourceRecord = {source:SourceRecord,artifact:FileRecord}
BatchChangeRecord = {path,preimage:MaterializedSourceRecord,postimage:MaterializedSourceRecord}
ProjectionChangeRecord = {path,before:SourceRecord,after:SourceRecord}
ProjectionComparison = {before,after,allowedChangedPaths,changes,unchangedRecordsSha256}
```

Paths distinguish logical source identity from physical materialization.
For every `BatchChangeRecord`, outer `path`, `preimage.source.path`, and
`postimage.source.path` are the same exact live apply path;
`preimage.artifact.path` is its exact physical
`sealed/pre/<index-name>` path and `postimage.artifact.path` is its exact
physical `sealed/post/<index-name>` path. Their source/content projections
match while physical artifact paths and inodes must not equal the logical live
path/inode. In `livePreimages|livePostimages`, by contrast, each
`MaterializedSourceRecord.source.path`, `.artifact.path`, and containing live
path are equal. Every `ProjectionChangeRecord` outer/before/after path is equal.
`changes` is exactly the five ordered records from Scope. Mirror comparison allows exactly config/app/design;
supplemental comparison allows exactly requirements/classification. There are
no separate ambiguous `preimages` and `postimages` arrays.
`ProjectionComparison.before` and `.after` are same-policy `SourceProjection`s;
`allowedChangedPaths` and `changes` have the corresponding three- or two-path
semantic order, and `unchangedRecordsSha256` hashes the canonical path-sorted
unchanged `{path,before,after}` array.

### One-shot apply

`apply-theme-batch` holds the global lock from first input open through applied
receipt or completed rollback. It retains root, prechange, candidate, packet,
accepted review, bundle manifest, patch, test report, all ten sealed pre/post
files, all five live preimages and parent directories, unchanged-source
authorities, and runtime. It reauthenticates all inputs and live path-to-FD
identities immediately before attempt publication.

Before the attempt, it fresh-creates or exact-reconciles the lineage-owned
zero-byte `0600` `.theme-batch-postapply-R.lease`, locks it exclusively, and
binds its `FileRecord` in the attempt. Lease creation is regular operational
evidence and grants no write authority; a crash before attempt leaves a fresh
apply eligible to reopen it. Live postapply validation has no child process:
the lock-owning parent retains the lease while it executes four pure
descriptor-based checks. A reconciler therefore returns `7` while the owner is
alive; after abrupt owner loss the released lease permits rollback-only
reconciliation.

Only a newly committed, fsynced, reopened
`.claude/ui_snapshots/ux1b/theme-batch-attempt-R.json` mints the current
process's opaque `FreshAttemptGrant`. `EEXIST`, exact reconciliation, or a lost
response exits nonzero and performs zero forward writes. With the grant, for
each exact path it calls the shared
`replace_live_exact(expectedLiveFd,expectedLiveRecord,desiredSourceFd,desiredContent)`
primitive with two deliberately distinct authorities. Forward `expected` is
the retained current-live preimage FD plus its exact `FileRecord`; forward
`desired` is the retained sealed-post source FD plus its pathless
`DesiredLiveContent`. Reverse rollback `expected` is the freshly retained
actual current-live postimage FD plus the live `FileRecord` observed in the
actor's current snapshot; reverse `desired` is the retained sealed-pre source
FD plus its pathless `DesiredLiveContent`. A sealed/candidate source
`FileRecord` is never used as expected-live inode identity.

`replace_live_exact` is one closed descriptor protocol. Under the retained
same parent FD it creates a random `.ux1b-replace.<32hex>` regular temp using
`O_CREAT|O_EXCL|O_RDWR|O_NOFOLLOW|O_CLOEXEC`, initial mode `0600`, copies desired bytes from the retained descriptor,
sets exact desired mode/owner, fsyncs, rehashes, and retains the temp FD. It
then nofollow-reopens the live name and requires exact expected
device/inode/owner/mode/link-count/size/SHA plus same-file equality to the
expected descriptor. Only then does one atomic same-parent `renameat` replace
the live name; it fsyncs the parent, nofollow-reopens the name, and requires
same-file equality to the retained temp plus equality to the pathless
`DesiredLiveContent` projection. On success it returns and the caller records a
new `FileRecord` whose path is the live destination and whose device/inode are
the renamed temp's actual identity; it never copies the desired source path or
inode into that record. A
definite failure before rename CAS-deletes only the exact temp and changes no
live byte. Once rename may have committed—including lost rename response,
parent-fsync failure, or reopen/authentication failure—the actor performs no
further forward or reverse write, publishes no reconciliation terminal, exits
`6`, and leaves classification to a fresh lease-owning reconciler's current
five-path snapshot. No caller infers commit from an exception or retries the
same primitive blindly.

There is no editor or shell gap. The attempt binds the exact four-row internal
postapply plan and the already passed sealed candidate-regression report, then
establishes a durable default: after any forward replacement, absence of an
exact passed postapply report means rollback-only. After all five, the original
process runs those four pure checks once over retained descriptors and
publishes the exact passed or failed report. Only a passed report permits final
postimage/source reauthentication and root-keyed applied receipt publication.
Failure or missing report can never be retried into success.

Theme apply crash reconciliation first acquires the global lock and then the
postapply lease; an active lease returns `7`. It never performs a missing
forward replacement. Before the original owner or a reconciler performs its
first reverse replacement, it no-replace publishes the regular-evidence
`theme-batch-rollback-intent-R.json`, binding the exact pre-rollback five-image
state and reverse-ordered paths it is allowed to restore. Its `actor` is the
closed literal `original|reconciler`; root, batch, theme run, attempt, runtime,
and nullable report equal the authenticated transaction inputs. Intent creation
has exactly two arms:

- a no-unknown intent may be `original|reconciler`; all five
  `observedStart` rows are present-regular `preimage|postimage`, the postimage
  set is one nonempty reachable forward/rollback prefix, and `plannedPaths` is
  exactly every postimage path in reverse apply order. An exact existing
  no-unknown intent may be resumed only from its reachable rollback prefixes;
- an unknown-bearing intent may be created only by the still-live original
  `FreshAttemptGrant` holder. `observedStart` contains at least one `unknown`
  union row and at least one exact present-regular `postimage`; `plannedPaths`
  is exactly all and only those current postimage paths in reverse apply order.
  Preimage, absent, nonregular, and unknown-regular rows are excluded. This arm
  need not be a hole-free prefix because external drift is the fact being
  closed; it is never resumable by any fresh process.

An original snapshot with at least one unknown but zero exact postimages uses
the null-intent/no-write branch below. Empty or reordered `plannedPaths`, a
reconciler-created unknown-bearing intent, or any other arm mismatch is
collision `4`.

The current-snapshot matrix is evaluated only through mutually exclusive rows:
an applied receipt first; then all-five-post with passed versus failed/missing
report; then all-five-pre; then a strict one-to-four-post reachable mixture;
then unknown/hole states. In particular, all-five-post plus an exact passed
report can never create a rollback intent and only takes `verified_applied`.

| Observed exact live state | Permitted action |
| --- | --- |
| applied receipt exists | read-only verification only |
| no attempt | a fresh apply may compete |
| attempt exists, applied receipt absent, all five postimages plus exact passed report, no rollback intent | do not rerun tests or create rollback intent; publish or exact-reconcile `verified_applied`, then applied receipt |
| attempt exists, applied receipt absent, all five postimages with failed/missing report, no rollback intent | publish rollback intent; restore all exact postimages in reverse order; publish `rolled_back` |
| attempt exists, all five preimages, no rollback intent | publish `aborted_before_write`; burn lineage |
| exact rollback intent exists, contains no unknown, and current state is its reachable rollback prefix, including current all-pre | resume only its still-postimage suffix; when all pre, publish truthful `rolled_back` from the intent and current actor-start snapshot |
| exact rollback intent exists but current state contains a new unknown/hole or is an unknown-bearing intent's later reachable prefix | fresh reconciler writes nothing; publish `blocked_unknown` using the exact current snapshot and intent ref |
| attempt exists, all rows present-regular with exactly one to four postimages in one reachable pre/post mixture, no rollback intent | publish no-unknown rollback intent; restore exact postimages in reverse order, ledger first; publish `rolled_back` |
| attempt exists and any unknown image is observed by a fresh reconciler outside an existing-intent row | write nothing; publish `blocked_unknown`; require manual coordination |

Rollback may resume after a crash from a durable no-unknown intent but replaces
only the next member of its reachable still-postimage suffix through
`replace_live_exact(actualLiveFd,actualLivePostRecord,sealedPreFd,
preimageDesiredContent)`. A hole, reversion,
or byte outside the bound pre/post images is unknown and never resumed. Every
rollback actor records its own exact pre-action current snapshot in
reconciliation `observedStart`; the intent's historical snapshot remains only
inside the referenced intent. A crash
after the final restore but before terminal publication therefore remains
distinguishable from a true before-write abort. If the original apply process
detects unknown drift immediately before a later replacement, it may publish
an `actor:original` intent only when at least one earlier exact postimage needs
reverse restore. It records the unknown state, leaves every unknown path
untouched, rolls back only its exact current postimage paths in reverse order,
publishes `blocked_unknown`, and exits `9`. If drift precedes the first forward
write—or if its fresh current snapshot has no exact postimage left to
restore—it publishes `blocked_unknown/original/no_write` with null rollback
intent and changes no bytes. An unknown-bearing intent is
never resumable by a fresh process: after owner loss the reconciler performs no
writes, even to other exact-post paths, and publishes or verifies
`blocked_unknown/reconciler/no_write` from its current exact snapshot. The
current state is classified either as an unknown-bearing intent's reachable
reverse-prefix (optionally with additional unknown drift), or as an invalid
continuation containing any hole, reversion, or unknown relative to the intent.
The fresh actor changes nothing, so `finalState` must preserve that exact
current `LiveImageRecord` union array: absent remains absent, and every regular
or nonregular artifact retains the same recorded inode/metadata, symlink
target, and hash/readability observation when present. A no-unknown intent that acquires a
hole/drift uses this same no-write branch. A
lost response after any rollback
replacement/parent-fsync/reopen is handled first by the fresh snapshot rule
above; a lost response after any rollback terminal commit is handled by
validating the already committed actor-specific
payload byte-for-byte; a fresh process never recomputes it with a different
actor. An aborted, rolled-back, or blocked
attempt permanently exhausts this root under this plan. No supersession command
or second attempt namespace is authorized here; another forward attempt needs
a separately accepted amendment defining a new immutable epoch/root contract.
The applied receipt, never the attempt, closes parent Task 3 and is the sole
batch authority consumed by Task 4.

## Theme-state and posttheme closure

Each capture has a lineage-owned zero-byte `0600` lease, consumptive intent,
and passed checkpoint. The coordinator creates or exact-reconciles and locks
the lease, freshly commits the absent intent to mint `FreshCaptureGrant`, then
launches exactly one frozen runner with `close_fds=True` and only standard
streams plus that lease FD. The two exact inner argv arrays are:

```text
[".venv/bin/python","scripts/ui_ux_theme_matrix.py","--browser","chromium","--out-dir",".claude/ui_snapshots/ux1b/theme-states-T","--no-prompt","--json"]
[".venv/bin/python","scripts/ui_ux_snapshot_matrix.py","--profile","ux1b-full-pages","--phase","posttheme","--browser","chromium","--out-dir",".claude/ui_snapshots/ux1b/posttheme-T","--no-prompt","--json"]
```

Both plans use the `CaptureRunnerPlan` arm. Their exact
`kind|stage|destination|expectedMode|expectedPhase|expectedCount` tuples are
`capture|theme-states|.claude/ui_snapshots/ux1b/theme-states-T|ux1b-theme|posttheme|3`
and
`capture|posttheme|.claude/ui_snapshots/ux1b/posttheme-T|ux1b-full-pages|posttheme|81`,
respectively. The frozen posttheme runner is only an
evidence producer and is not trusted to consume the v2 root; the external
coordinator binds root/applied/state authority and performs the comparison.
Alternate argv, shell interpolation, or direct runner invocation grants
nothing.

Both theme execution plans use cwd `.`, the exact closed capture environment,
stdin `devnull`, timeout `14400`, stdout/stderr limits `67108864` bytes each, a
fresh process group, `passFds:["lease"]`, and capability
`capture-coordinator-v1`, exact `outer_pgid` processFamily, and outer
`seatbeltProfileSha256:null`. Timeout, output overflow, spawn failure, signal,
or any nonzero exit prevents a `RunnerReceipt` or checkpoint and burns that
stage/T. The durable failure state is the committed intent plus absent
checkpoint; no undeclared failure artifact is written. The current actor emits
the no-authority `nested_quiescence_unverified` diagnostic, and every later
reconciler conservatively derives the same manual-audit requirement because it
cannot prove from that prefix whether an inner family ever started.

After runner exit zero, the same owner authenticates the exact terminal bundle
and publishes a checkpoint binding intent, `RunnerReceipt`, `BundleRecord`, and
runtime. Only then may it publish the machine candidate and deterministic
packet. Parent death is handled exactly: active inherited lease returns `7`;
absent intent permits one fresh owner; intent without a passed checkpoint burns
that stage/T and never reruns even if output looks complete; a fully valid
checkpoint may be reconciled forward to its deterministic candidate/packet;
candidate/packet may only be read-only verified. Partial output is never
deleted or completed. On SIGINT/SIGTERM the owner drives the same exact outer-
family controller: an exact quiescent receipt allows exit `130`, while a
missing receipt exits `9`; either way the durable intent remains burned and
the diagnostic is the stage-specific `nested_quiescence_unverified`. SIGKILL
waits on the inherited lease and then reconciles only to the same burned/
manual-audit outcome. No abnormal path claims the frozen inner groups are
closed.

The formal theme matrix must pass 3/3 and authenticate exactly 3 main PNGs,
3 sidecars, 9 crops, 15 artifacts, and 16 namespace leaves. Its candidate binds
the capture intent/checkpoint and is published before the 12-item packet,
avoiding a hash cycle. After accepted external review, `close-theme-states`
reopens root, applied receipt, candidate, packet/review, source/runtime,
manifest and every artifact, then publishes the immutable attestation.
Intent/checkpoint evidence alone cannot start or close Task 4.

The formal posttheme matrix must pass 81/81 and authenticate 162 artifacts and
163 leaves. `capture-posttheme` consumes root, applied receipt, state
attestation, pretheme and posttheme bundles; rebuilds exact mirror and
supplemental projections; applies only the five allowed change records and
imported narrow sidecar normalization; checks dimensions; publishes its machine
candidate; and then publishes the 81-item packet referencing that candidate.
After accepted review, `finalize-theme` reopens the whole chain and publishes
immutable final closure. The closure alone closes parent Task 5; root remains
unchanged.

`changedIdsSha256` has one exact preimage: take every comparison pair whose
boolean `changed` is true, require unique IDs, sort those IDs lexicographically,
encode that string array with this plan's canonical JSON encoder and no newline,
then hash ASCII domain
`quant-radar-ui-ux-posttheme-changed-ids/v1\0` followed by those canonical
bytes. Pair storage order never affects this digest. The golden changed-ID set
`["a","b::crop"]` encodes exactly as `["a","b::crop"]` and hashes to
`49bfb08f2c58acf5f366504659f246d6b85d30c2f0c062248c5414c602d04f6e`.

## Canonical encoding and schemas

Canonical JSON is one UTF-8/NFC object, no BOM or trailing newline, encoded by
`json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
allow_nan=False)`. Strict parsing rejects duplicate/unknown keys, floats,
non-NFC strings, and invalid paths. SHA is 64 lowercase hex. `RecoveryId` and
`TierId` match `[0-9]{8}T[0-9]{6}Z`; `BatchId` and `ThemeRunId` match
`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`; `GeneralId` matches
`[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}`. Every field named `recoveryId` or
`tierId` uses the first grammar, `batchId` uses `BatchId`, `themeRunId` uses
`ThemeRunId`, and `lineageId` uses the kind-selected grammar stated in the
review-packet contract. A bare field named `id` or `reviewer.id` uses
`GeneralId` unless this plan gives that field an exact literal/path/set.
Workspace paths are normalized relative POSIX paths with no empty, `.` or `..`
component. Machine artifacts are at most 16 MiB and review artifacts 8 MiB.

Unless a stricter literal is stated, path/argv elements are 1-1024 UTF-8
bytes; other machine strings are 0-512 bytes; review explanation and finding
summary are at most 1024 bytes. Rejected items and non-hash accepted items
require a nonempty explanation; finding summaries are nonempty. Numeric counts,
sizes, offsets, uid/gid/device/inode/link counts and numeric timestamps are exact JSON
integers in `0..2^63-1`; process IDs are `1..2^31-1`. Validation uses
`type(value) is int`, so JSON booleans never satisfy an integer field.

Mode and live-hash predicates are closed constants. A mode string always
matches `[0-7]{4}` and decodes in base 8. `SafeRegularMode(mode)` is true iff
`m <= 0o777`, `(m & 0o400) != 0`, `(m & 0o022) == 0`, and
`(m & 0o7000) == 0`: owner-read is required; setuid/setgid/sticky and
group/other write are forbidden. `SafeDirectoryMode(mode)` is true iff
`m <= 0o777`, `(m & 0o700) == 0o700`, `(m & 0o022) == 0`, and
`(m & 0o7000) == 0`: owner rwx is required under the same write/special-bit
ban. The candidate's synthetic venv symlink has exact lstat mode `0755`; no
other source symlink is accepted. `LIVE_IMAGE_HASH_LIMIT_BYTES` is exactly
`16777216`. A regular live path at or below that lstat size is opened with
`O_RDONLY|O_NOFOLLOW|O_CLOEXEC`, fstat-matched to the first observation, read
through exact-size EOF using at most `16777217` bytes, then surrounded by the
equal second nofollow lstat. Exact bytes yield `contentReadable:true` and their
hash. Open/read denial or size above the limit yields
`contentReadable:false,sha256:null` after the equal second lstat; identity,
metadata, size/read-count, or EOF drift aborts the snapshot rather than being
classified. These predicates—not implementation preference—select every
safe/unsafe and readable/unreadable arm below.

Shared exact types are:

- `ArtifactRef = {path,sha256,size}`;
- `ContentRecord = {path,sha256,size,mode}`, where mode satisfies
  `SafeRegularMode` and is not restricted to source-mirror modes;
- `AuthorizationBinding = {documentPath,bodySha256,sequence,amendment,
  traceability}`, where `documentPath` is exactly
  `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery.md`, `bodySha256` hashes the exact
  freshly extracted and fully validated canonical V2 body, `sequence` is
  integer `1`, and the last two values are the exact plan and ledger
  `ArtifactRef`s from that body; every field named `authorizationRecord` has
  this type and never contains the surrounding Markdown hash;
- `FileRecord = {path,sha256,size,mode,uid,gid,device,inode,nlink}`;
- `DesiredLiveContent = {sha256,size,mode,uid,gid,nlink}`, the pathless
  projection authenticated from a retained desired-source FD; `nlink` is
  exactly `1`. It deliberately contains no path, device, or inode and therefore
  never participates in same-file identity checks;
- `NonRegularLiveRecord = {path,fileType,size,mode,uid,gid,device,inode,nlink,
  target}`, where fileType is exactly
  `directory|symlink|fifo|socket|character_device|block_device|other`, target
  is the exact `readlink` text only for `symlink` and null otherwise, and no
  directory is traversed;
- `UnknownRegularLiveRecord = {path,size,mode,uid,gid,device,inode,nlink,
  contentReadable,sha256}`, an observation-only, never-authoritative regular
  file record. Mode is any four-octal permission string rather than a safe-mode
  grant; nlink may be any positive integer. `contentReadable:true` requires the
  exact 64-lowercase-hex hash, while false requires null. It is built from two
  equal retained-parent nofollow `fstatat` observations bracketing the bounded
  read/hash attempt; type/identity/metadata drift instead aborts the snapshot.
  It grants neither expected-live CAS nor desired-source authority;
- `ExternalFileRecord = {absolutePath,sha256,size,mode,uid,gid,device,inode,nlink}`;
- `SymlinkRecord = {path,target,size,mode,uid,gid,device,inode,nlink}`, where
  `target` is the exact uninterpreted `readlink` text and the descriptor-safe
  resolution chain is separately authenticated to its regular target;
- `ExternalSymlinkRecord = {absolutePath,target,size,mode,uid,gid,device,inode,nlink}`
  with the same lstat/readlink semantics;
- `RuntimeTreeRecord = {absolutePath,mode,uid,gid,device,inode,treeSha256}`,
  where the tree digest is the frozen isolation encoder over two identical
  descriptor-safe passes;
- `SourceRecord = {path,sha256,size,mode}`, mode string `0444|0555`;
- `BundleRecord = {manifest,mode,phase,expectedCaptureCount,capturedCount,
  artifactCount,namespaceLeafCount,captureIdsSha256,sourceDigest,
  captureStackDigest}`, where manifest is `FileRecord`, mode/phase/counts equal
  the bound runner/Task 6 contract, and counts are nonnegative exact integers.
  For every new capture checkpoint, the verifier also strictly parses that
  manifest and requires top-level `childrenQuiescent:true`, one exact
  quiescent/return-0/null-signal app process row, exactly
  expectedCaptureCount path-keyed quiescent/return-0/null-signal browser rows,
  and matching app/browser `attestationDigests`; these frozen inner receipts,
  together with the outer `outer_pgid` receipt, are mandatory for success;
- `SourceProjection = {schemaVersion,policy,records,digest}`, where policy is
  exactly `{include,exclude}`, both string arrays are the declared ordered
  policy, records are unique path-sorted `SourceRecord[]`, and digest is the
  frozen encoder result;
- `RuntimeReceipt = {schemaVersion,python,streamlit,playwright,chromium,
  platform,tempRootParent,directExecutables,captureRuntime,candidateRuntime,
  sha256}`;
- `CapabilitySet = {id,network,execRoles,readRoles,writeRoles,environmentId,
  profileTemplateSha256}`, with only the capture object and six candidate
  capability rows defined below; capture requires null profile hash and every
  candidate capability requires the exact nonnull table hash;
- `ObserverFailureCleanupPlan = {kind,target,signal,maxKillpgCalls,
  killPidCalls,allowEsrch,allowOwnedZombieEperm,closeLocalFdsOnTimeout}`,
  exactly
  `{"kind":"direct_owned_observer","target":"observer_pgid","signal":"SIGKILL","maxKillpgCalls":1,"killPidCalls":0,"allowEsrch":true,"allowOwnedZombieEperm":true,"closeLocalFdsOnTimeout":true}`;
- `ProcessObserverPlan = {executable,argv,environment,stdin,timeoutSeconds,
  waitTimeoutSeconds,stdoutLimitBytes,stderrLimitBytes,processGroup,passFds,
  failureCleanup}`,
  where executable is the authenticated `/bin/ps` `ExternalFileRecord` equal
  to the runtime direct-executable row and every other field is the exact
  observer literal fixed above; failureCleanup is the exact
  `ObserverFailureCleanupPlan`;
- `ExitWatchPlan = {kind,filter,flags,fflags,alreadyExitedFallback}`, exactly
  `{"kind":"darwin_kqueue_proc","filter":"EVFILT_PROC","flags":["EV_ADD","EV_ENABLE","EV_CLEAR"],"fflags":["NOTE_EXIT"],"alreadyExitedFallback":"esrch_requires_owned_zombie"}`;
- `ExitWatchResult = {registration,outcome,eventCount}`, a closed union:
  successful registration requires exactly
  `{"registration":"registered","outcome":"note_exit","eventCount":1}`;
  registration `ESRCH` requires exactly
  `{"registration":"esrch","outcome":"owned_zombie","eventCount":0}` and
  the first serialized sample must contain the unreaped owned zombie leader.
  No other registration error, event kind/count, or fallback is accepted;
- `TokenProcessFamilyPlan = {kind,environmentKey,tokenSha256,tokenFormat,
  observer,exitWatch,quiescenceTimeoutSeconds,termGraceSeconds,
  killGraceSeconds}`, where kind is `token_pgid`,
  the environment key is `QUANT_RADAR_UX1B_PROCESS_TOKEN`, format is
  `ux1b_<64hex>`, the token digest is SHA-256 of the raw ASCII token and is 64
  lowercase hex, observer is the exact `ProcessObserverPlan`, exitWatch is the
  exact `ExitWatchPlan`, and the three timeout values are `25/3/7`;
- `OuterGroupProcessPlan = {kind,observer,exitWatch,quiescenceTimeoutSeconds,
  termGraceSeconds,killGraceSeconds}`,
  where kind is `outer_pgid`, observer/exitWatch have the same exact bindings,
  and the three timeout values are `25/3/7`;
- `ProcessFamilyPlan = TokenProcessFamilyPlan|OuterGroupProcessPlan`, a closed
  kind-discriminated union. Every candidate command and capability probe uses
  `token_pgid`; every frozen capture runner uses `outer_pgid` and has no token
  fields;
- `ProcessObservationRow = {pid,uid,processGroupId,state,waitStatus,
  markerMatch}`, where pid and processGroupId are positive exact integers, uid
  and waitStatus are nonnegative exact integers, and state matches the exact
  Darwin token `[IRSTUZ][+<>AELNSsVWX]{0,15}`. The raw `xstat` column must match
  `[0-9a-f]+` and is decoded in base 16 into waitStatus (`300` therefore means
  POSIX wait status `0x0300`, not decimal 300). `markerMatch` is the boolean
  result of the exact conservative command-field marker rule above;
- `ProcessObservationSample = {phase,observerPid,observerProcessGroupId,rows,
  observerReturnCode,observerSignal,stdoutSha256,stderrSha256,stdoutBytes,
  stderrBytes,runnerStdoutEof,runnerStderrEof}`, where the two EOF fields are
  booleans sampled atomically after the observer exits, and observerPid and
  observerProcessGroupId are the same
  positive fresh-session `/bin/ps` PID, distinct from the runner PGID, and rows are unique
  PID-sorted `ProcessObservationRow[]` filtered to the original PGID plus, for
  `token_pgid` only, all same-UID exact marker matches. The observer must exit
  `0` with null signal, bounded streams, and empty stderr; stream hashes cover
  the raw bounded `/bin/ps` bytes, which are never serialized. Its own exact PID
  is required present in the raw snapshot, then excluded from rows; no other
  row in its observer PGID may exist;
- `LeaderTermination = {returnCode,signal,waitStatus}`, a closed union: exited
  has returnCode `N` in `0..255`, null signal, waitStatus `N << 8`, and satisfies
  `WIFEXITED/WEXITSTATUS`; signaled has null returnCode, positive signal `S`, a
  waitStatus satisfying `WIFSIGNALED/WTERMSIG==S`, and permits only the POSIX
  core bit `0x80` in addition to `S`;
- `ProcessFamilyReceipt = {plan,closureKind,leaderPid,processGroupId,ownerUid,
  exitWatchResult,samples,quiescent,leaderTermination,observationSha256}`, where plan is the
  exact enclosing `ExecutionPlan.processFamily` projection,
  leaderPid and processGroupId are the same positive start-new-session ID,
  ownerUid is the coordinator UID, closureKind is
  `clean_exit|failed_no_signal|terminated_term|terminated_kill`, and quiescent
  is true. Every sample before `post_reap` contains exactly one owner-UID row
  whose pid is leaderPid and whose processGroupId is the receipt group; the
  token-plan leader has markerMatch true while non-zombie and false once Darwin
  renders its zombie command as `<defunct>`, while the outer-plan leader always
  has it false. The zombie leader remains authenticated by its unreaped owned
  PID/PGID/UID/xstat rather than by command text. Every other serialized row
  also has ownerUid. A `clean_exit` sequence is zero or more `settling_exit` samples
  followed by exactly `pre_reap,post_reap`. Every `settling_exit` contains the
  owned zombie leader and either at least one other filtered row or at least
  one false runner EOF field; the controller
  neither signals nor reaps while waiting. A marker-only row means exactly
  `markerMatch:true` with a processGroupId different from the receipt group.
  `failed_no_signal` has exactly zero or more leading `settling_exit` samples,
  then `pre_no_signal`, zero or more `settling_no_signal`, then
  `pre_reap,post_reap`; `pre_no_signal` contains the owned zombie leader, no
  non-zombie original-PGID row, and any number of other filtered rows; it is
  taken only after `timed_out` or
  `output_overflow` has become decisive or during owned interruption cleanup. A `settling_no_signal` sample still
  contains the owned zombie leader, no non-zombie original-PGID row, and
  either at least one other filtered row or at least one false runner EOF
  field. Marker-only live rows and zombie original-group children can only be
  observed to disappear;
  they are never PID-signaled on Darwin.
  Every `pre_reap` contains exactly the owned zombie leader and no other
  filtered row, and both runner EOF fields are true. Its row waitStatus equals
  leaderTermination.waitStatus, and leaderTermination equals the enclosing
  `CommandResult|RunnerReceipt` returnCode/signal arm only for `clean_exit`;
  failure closures retain the independently observed leader termination while
  an enclosing `timed_out|output_overflow` arm keeps both fields null. An
  interruption may construct the same failure closure solely to authorize
  owned-session cleanup, but persists no `CommandResult` or `RunnerReceipt`.
  `terminated_term` has exactly zero or more leading `settling_exit` samples,
  `pre_term`, zero or more `settling_term`, then `pre_reap,post_reap`.
  `terminated_kill` has exactly zero or more leading `settling_exit` samples,
  `pre_term`, zero or more `settling_term`, `pre_kill`, zero or more `settling_kill`, then
  `pre_reap,post_reap`. `pre_term` is the complete conservative union
  immediately before one successful `killpg(SIGTERM)` and must contain at
  least one non-zombie original-PGID row. `pre_kill`, when present after the
  exact 3-second grace, is the fresh union immediately before one successful
  `killpg(SIGKILL)` and has the same non-zombie original-PGID requirement.
  `ESRCH`, `EPERM`, or any other signal error produces no receipt; in
  particular a zombie-only original group selects `failed_no_signal` instead
  of pretending a signal was delivered. A `settling_term|settling_kill`
  sample is nondecisive exactly when its leader is non-zombie, some row pid
  differs from leaderPid, or at least one runner EOF field is false. Within
  family cleanup, only the original runner PGID is ever signaled; its unreaped leader prevents PGID
  reuse. Marker-only detached rows are never signaled by PID because Darwin
  provides no race-free PID handle. Failure to reach the exact `pre_reap`
  union by the bound deadline means no receipt and manual audit. Every
  `post_reap` rows array is empty and both runner EOF fields are true. For `outer_pgid`, every markerMatch is false
  and filtering is by PGID only. `observationSha256` is SHA-256 over the ASCII domain bytes
  `quant-radar-ui-ux-process-observation/v1\0` followed by canonical JSON of
  the exact other nine receipt fields in displayed order-independent object
  encoding. This binds the observer record/argv policy through plan, PGID,
  owner, token hash when present, decisive samples, return status, and final
  empty union without exposing the token or process-table text;
- `ExecutionPlan = {argv,cwd,environment,stdin,timeoutSeconds,
  stdoutLimitBytes,stderrLimitBytes,processGroup,passFds,capability,
  seatbeltProfileSha256,processFamily}`, where `capability` is the exact
  embedded closed `CapabilitySet` (never an ID or open mapping), candidate and
  probe profile hashes are nonnull while an unsandboxed frozen-runner plan uses
  null, and every external plan has a nonnull `ProcessFamilyPlan`; `environment`
  is the exact public spawn map. For `token_pgid` it excludes the raw process
  token, which the imperative shell adds as the sole secret key after verifying
  its hash; `outer_pgid` adds no secret environment key;
  `stdin:"devnull"`, `processGroup:"new"`, `passFds` is an exact sorted closed
  token array, and the remaining family-specific literals are fixed below;
- `CaptureRunnerPlan = {kind,stage,execution,destination,expectedMode,
  expectedPhase,expectedCount}`, where kind is `capture` and the remaining
  fields equal the bound frozen stage contract;
- `ProbeRunnerPlan = {kind,stage,execution,capabilityId}`, where kind is
  `capability_probe`, stage is `capability-probe`, and capabilityId equals the
  embedded `execution.capability.id` string;
- `RunnerPlan = CaptureRunnerPlan|ProbeRunnerPlan`, a required closed
  kind-discriminated union; every lifecycle capture field requires the capture
  arm and every capability receipt requires the probe arm;
- `RunnerReceipt = {plan,startedAt,finishedAt,outcome,returnCode,signal,
  stdoutSha256,stderrSha256,stdoutBytes,stderrBytes,processGroupId,
  processFamily}` is success-only: outcome is `exited`, returnCode is `0`,
  signal is null, processGroupId is positive, and processFamily is the exact
  `clean_exit`, quiescent receipt whose plan equals
  `RunnerPlan.execution.processFamily` and whose processGroupId equals the
  enclosing result's processGroupId. Capture receipts require the `outer_pgid` arm plus separately
  authenticated inner frozen bundle receipts; probe receipts require
  `token_pgid`. startedAt/finishedAt are UTC RFC3339 seconds and finishedAt is
  not earlier than startedAt. Spawn/nonzero/signal/timeout/overflow failures
  never create or persist a `RunnerReceipt`;
- `Dimensions = {width,height}`, with positive exact integers;
- `Finding = {id,severity,status,summary}`, severity `High|Medium|Low`, status
  `resolved|nonblocking|unresolved`; accepted review forbids every unresolved
  High/Medium while rejected review permits it;
- `EligibleDestination = {path,exists:false}`;
- `BootstrapCreatedRecord = {path,preconditionAbsent,artifact,disposition}`,
  with `preconditionAbsent:true`, one `FileRecord`, and disposition
  `delete_scratch_if_exact|retain_operational`;
- `HunkAnchor = {path,kind,preimageSha256,postimageSha256,startByte,endByte,
  prefixSha256,suffixSha256,preimageSpanSha256,postimageSpanSha256}`. Let `P`
  and `Q` be the exact preimage and postimage byte strings. They must differ.
  `preimageSha256` and `postimageSha256` hash all of `P` and `Q`. If `Q` is a
  strict extension of `P`, kind is exactly `append`, `startByte=endByte=len(P)`,
  common-prefix bytes are `P`, common-suffix and preimage-span bytes are empty,
  and postimage-span bytes are `Q[len(P):]`. Otherwise kind is exactly `hunk`:
  `startByte` is the byte length of the unique longest common prefix of `P` and
  `Q`; after removing that prefix, `suffixLength` is the greatest value no
  larger than either remainder for which the two byte strings have the same
  suffix; `endByte=len(P)-suffixLength`, and the postimage span ends at
  `len(Q)-suffixLength`. Thus prefix is `P[:startByte]` and equals
  `Q[:startByte]`; suffix is `P[endByte:]` and equals the corresponding final
  `suffixLength` bytes of `Q`; preimage span is `P[startByte:endByte]`; and
  postimage span is `Q[startByte:len(Q)-suffixLength]`. Each of the four span/
  boundary fields is SHA-256 of exactly its raw byte slice with no domain bytes,
  encoding transform, or newline. All values are computed before the first
  existing-file write. For the hunk golden `P=b"abcOLDxyz"` and
  `Q=b"abcNEW!xyz"`, `startByte/endByte/suffixLength` are `3/6/3`; whole
  pre/post, prefix, suffix, pre-span, and post-span hashes are respectively
  `507be3b6270f1b18d140d3e744d2878c17059d9d6abff6f8a086a227cc54a0e4`,
  `7e547921f7a2e0f7369bb0d3abf1910ee55c0e3c97663fe46171df3b71c29d46`,
  `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`,
  `3608bca1e44ea6c4d268eb6db02260269892c0b42b86bbf1e77a6fa16c3c9282`,
  `099d90cbee62f89e6478e153eb3240efcbe4ac2231bedc3e84549bbeaaba87e8`,
  and `775653072817f6d0c39da9f29b7747925c12b57a0dd5414463423915c3f07555`.
  For append golden `P=b"abc"`, `Q=b"abc++"`, offsets are `3/3`, suffix and
  pre-span use the empty SHA
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`,
  whole-pre and prefix both hash to
  `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`,
  whole-post hashes to
  `d2a8fbab0db20adee57d10f25260e3309f108e2b198ad80ee605fdd7e193f2ad`,
  and post-span hashes to
  `cfc0c0607a3380f7975346b30c14af8284f5493d9781b0ed847f499f01b4768e`;
- `RollbackEntry = {path,preimage,postimage,anchor,disposition}`, where the two
  image values are required nullable `ContentRecord`s, anchor is a required
  nullable `HunkAnchor`, and disposition is one closed value listed below;
- `HistoricalSelectorMode = {path,sha256,size,tarMode,mirrorMode,uid,gid}` and
  is exactly one row from the authenticated tar table above;
- `PresentRegularLiveImage = {path,kind,state,artifact}`, where kind is
  `present_regular`, state is `preimage|postimage|unknown`, artifact is the
  descriptor-observed safe, one-link, readable `FileRecord`, and both paths
  match. Pre/post
  classification compares the artifact's pathless `DesiredLiveContent`
  projection to the corresponding authenticated desired projection; inode
  identity is never compared to a sealed/candidate source inode;
- `UnknownRegularLiveImage = {path,kind,state,artifact}`, exactly kind
  `unknown_regular`, state `unknown`, and one path-matching
  `UnknownRegularLiveRecord`. A regular path uses this arm when unsafe mode,
  wrong owner, `nlink != 1`, or bounded content open/read/hash prevents a safe
  `FileRecord`; readable safe one-link content that merely differs from both
  desired projections remains `PresentRegularLiveImage/state:unknown`;
- `AbsentLiveImage = {path,kind,state,artifact}`, exactly kind `absent`, state
  `unknown`, and artifact null;
- `NonRegularLiveImage = {path,kind,state,artifact}`, exactly kind
  `nonregular`, state `unknown`, and one path-matching `NonRegularLiveRecord`;
- `LiveImageRecord = PresentRegularLiveImage|UnknownRegularLiveImage|
  AbsentLiveImage|NonRegularLiveImage`, a closed kind-discriminated union. Every five-path
  snapshot is in exact apply order and therefore records missing paths and
  nonregular holes without pretending they are regular `FileRecord`s;
- `CommandRecord = {id,kind,execution}`, where kind is
  `candidate_python|internal`; candidate execution is one nonnull exact
  `ExecutionPlan` whose sole argv authority begins with the authenticated venv
  launcher and `-B`, while internal rows have execution null;
- `CommandResult = {id,kind,status,outcome,errorCode,returnCode,signal,
  stdoutSha256,stderrSha256,stdoutBytes,stderrBytes,processGroupId,
  processFamily}` with exact command ID/kind matching its `CommandRecord` and status
  `passed|failed|not_run`; hashes cover every byte drained through EOF or
  canonical empty bytes. Non-overflow counts are at most their plan limits; an
  overflow result has at least one count above its corresponding limit, while
  retained payload memory is still capped at the limit. An empty stream means
  byte count `0` and SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
  Fail-fast reports retain one `not_run` result for every row after the first
  failure. Every external arm has errorCode null. A passed external result
  requires positive processGroupId, outcome `exited`, returnCode `0`, null
  signal, and an exact quiescent
  `token_pgid` family receipt with closureKind `clean_exit` whose plan equals
  `CommandRecord.execution.processFamily` and whose processGroupId equals the
  result's processGroupId. An internal result has
  outcome `internal`, null returnCode/signal/processGroupId/processFamily,
  empty streams, and errorCode null when passed or exactly
  `assertion_failed|internal_exception` when failed. A `not_run` row has
  outcome `not_run`, null errorCode/returnCode/signal/processGroupId/
  processFamily, and empty streams. A `spawn_failed` arm has null returnCode,
  signal, processGroupId, and processFamily, both streams empty, and status
  failed; it is valid only for a
  definite spawn failure proven to leave no child or process group. Any
  external outcome other than `not_run|spawn_failed` has a positive
  processGroupId and a nonnull exact family
  receipt. An `exited` arm has the closed returnCode/null-signal pair above,
  closureKind `clean_exit`, and status passed only under the preceding success
  rule, otherwise failed. A `signaled` arm is failed and has closureKind
  `clean_exit`. `timed_out|output_overflow` are failed and map exactly to
  `failed_no_signal|terminated_term|terminated_kill`; both keep result
  returnCode/signal null, and only `output_overflow` may exceed a stream limit.
  Every external arm after spawn requires cleanup
  and an exact quiescent receipt whose plan equals
  `CommandRecord.execution.processFamily` and whose processGroupId equals the
  enclosing result's processGroupId before staging; for `exited|signaled`,
  leaderTermination equals the result pair, while timeout/overflow retain the
  independently observed leader termination only inside the family receipt;
- `ScratchTestReport = {schemaVersion,status,commands,results,passed,failed,
  sha256}`,
  with schema `quant-radar-ui-ux-theme-batch-scratch-tests/v1`, status
  `passed`, the exact seven `CommandRecord`s below, `passed:7`, `failed:0`, the
  seven matching passed `CommandResult`s, and digest over other fields;
- `ProtectedClosure = {records,digest}`, with unique path-sorted
  `SourceRecord[]` and the canonical array digest;
- `CandidateOverlayRecord = {path,sealed,candidate}`, where path is one exact
  live apply path and sealed/candidate are distinct `FileRecord`s satisfying
  the cross-image rules below;
- `CandidateDirectoryRecord = {path,mode,uid,gid,device,inode}`;
- `CandidateWorkspaceManifest = {root,directories,files,symlinks,digest}`,
  where root is exactly one `CandidateDirectoryRecord` whose path is the exact
  absolute candidate-root spelling, mode is `0700`, uid/gid equal the
  coordinator, and device/inode equal the retained root FD; every path
  in the other three arrays is candidate-root-relative, `directories` excludes
  root and is a unique relative-path-sorted `CandidateDirectoryRecord[]` whose
  modes satisfy `SafeDirectoryMode`,
  `files` is a path-sorted `FileRecord[]`, `symlinks` contains only the exact
  relative-path venv bridge, and digest hashes the three arrays plus root;
- `CandidateWorkspaceReceipt = {schemaVersion,beforeManifest,afterManifest,
  overlay,protectedClosures,venvBridge,extraEntries}`, where both manifests are
  exact and have equal digests, schema is
  `quant-radar-ui-ux-candidate-workspace/v1`, overlay is the exact five
  apply-order `CandidateOverlayRecord[]`,
  `protectedClosures` is exactly
  `{snapshotMatrix:ProtectedClosure,socialCli:ProtectedClosure}`, `venvBridge`
  equals the manifest's sole `SymlinkRecord`, and `extraEntries` is the exact
  empty `string[]` after tests;
- `CandidateSessionMarker = {schemaVersion,status,rootContract,batchId,
  themeRunId,sessionNonce,ownerUid,ownerPid,createdAt}`, where schema is
  `quant-radar-ui-ux-candidate-session/v1`, status is `active`, rootContract is
  the exact authenticated root `ArtifactRef`, both IDs satisfy the closed
  `B`/`T` grammar and record the creating invocation,
  sessionNonce is the directory's 32-lowercase-hex suffix, ownerUid is the
  coordinator UID, ownerPid is its positive PID, and createdAt is UTC RFC3339
  seconds. Its canonical JSON bytes have no trailing newline and live only in
  the mode-`0600` direct-child owner marker defined below; they are an
  operational manual-audit gate, never test evidence or publication authority.
  Global orphan classification does not require those valid IDs to equal the
  scanner's invocation; only creation and the original owner's automatic
  cleanup require exact current-invocation equality;
- `ProbeOutcome = {id,expectedOutcome,actualOutcome,errorClass,errorCode,
  returnCode,signal,passed}`, where expected outcome is `succeeded|denied` and
  actual outcome is `succeeded|denied|failed`; success requires null error
  fields and either null return/signal for an in-process operation or exact
  `0/null` for a child, denial requires null return/signal plus the exact
  operation-specific OS denial described below, and `passed` is true iff
  expected and actual match. `errorClass` is required null or exactly
  `PermissionError|OSError|gaierror|ProbeFailure`; denied file/exec/socket
  operations use `PermissionError|OSError` plus string code `EPERM|EACCES`,
  denied DNS uses `gaierror` plus `EAI_AGAIN|EAI_FAIL|EAI_NONAME`, and failed
  uses `ProbeFailure` plus
  `unexpected_success|unexpected_denial|nonzero_exit|signal|wrong_identity|
  wrong_payload|skipped|internal_error`. `returnCode` and `signal` are required
  nullable integers. For failed outcomes, `nonzero_exit` requires a nonzero
  return code and null signal; `signal` requires null return code and a
  positive signal; `unexpected_success` preserves the operation form's exact
  successful pair (`null/null` in-process or `0/null` for a child); and
  `unexpected_denial|wrong_identity|wrong_payload|skipped|internal_error`
  require `null/null`. An
  application error, ordinary nonzero child exit, skipped operation, or missing
  observation is `failed`, never a denial;
- `BrowserProbe = {apiExecutablePath,defaultExecutablePath,expectedVersion,
  observedVersion,defaultExecutableMatchesCandidateLeaf,defaultExecutableSha256,
  nodeSha256,launched,pageCreated,closed,childrenQuiescent}`, with every
  boolean true, API path equal to `RuntimeReceipt.chromium.executablePath`,
  default path/hash equal to
  `RuntimeReceipt.candidateRuntime.headlessShellExecutable`, expectedVersion
  equal to `RuntimeReceipt.chromium.version`, observedVersion equal to the
  launched browser's version, and nodeSha256 equal to the authenticated
  Playwright Node executable row. The `MatchesCandidateLeaf` boolean is a
  registry/path/hash comparison, not a claim to enumerate observed descendant
  executables; actual execution evidence is the successful launch under the
  profile's sole browser process-exec leaf plus outer family quiescence;
- `ProbeCanaryRecord = {artifact,contentSha256,unchangedAfterEveryProbe,
  deletedBeforeReport}`, where artifact is the descriptor-observed historical
  `ExternalFileRecord`, the digest equals the fixed bytes below, and both
  booleans are true;
- `CapabilityProbeReceipt = {schemaVersion,capabilityId,templateSha256,
  renderedProfileSha256,probeSourceSha256,probeModuleSha256,execution,
  positive:ProbeOutcome[],
  negative:ProbeOutcome[],browser:BrowserProbe|null,passed,sha256}`,
  where schema is `quant-radar-ui-ux-capability-probe/v1`, `execution` is the
  exact passed `RunnerReceipt` below, the assertion arrays have the exact
  ordered IDs assigned below, browser is required null except for the browser
  capability, `probeSourceSha256` is the fixed bootstrap hash below,
  `probeModuleSha256` equals the candidate manifest's handoff-module hash, and
  `capabilityId`, `templateSha256`, and `renderedProfileSha256` equal respectively
  `execution.plan.execution.capability.id`, that capability's nonnull template
  hash, and its execution Seatbelt hash. The digest covers every other field.
  `passed:true` requires a passed runner,
  every assertion passed, exact source/module/template/rendered hashes, and the
  closed browser nullability/equality rules;
- `SnapshotSubsetReceipt = {schemaVersion,commandId,bootstrapSha256,
  runnerModuleSha256,testModuleSha256,allTestsSha256,selectedTestsSha256,
  excludedTests,passed,failed,stdoutSha256,stdoutBytes,sha256}`, with the exact
  constants and cross-bindings in POST-018 below, and digest over every other
  field;
- `CandidateRegressionReport = {schemaVersion,status,workspace,probeCanary,
  capabilityProbes,snapshotSubset,commands,results,passed,failed,notRun,
  resultsSha256,sha256}`
  with the exact six capability-ID-sorted probe receipts and 37 candidate
  commands below; schema is `quant-radar-ui-ux-candidate-regression/v1`, status
  is `passed`, workspace is the exact `CandidateWorkspaceReceipt`, probeCanary
  is the coordinator-created `ProbeCanaryRecord`, and snapshotSubset is the
  exact passed POST-018 receipt below. Commands/results are both length `37` in
  the listed order, and every `results[i].id/kind` equals
  `commands[i].id/kind`; `resultsSha256` is SHA-256 of canonical results and
  `sha256` covers every other report field. Passed requires six passed probes
  containing, in aggregate, exact `63/131` positive/negative outcomes,
  `37/0/0`, exact equal workspace manifests, and empty extra entries;
- `ThemeBatchTestReport = {schemaVersion,status,scratch,regression,sha256}`,
  where schema is `quant-radar-ui-ux-theme-batch-tests/v1`, status is `passed`,
  both closed nested reports are passed, and `sha256` is SHA-256 of the
  no-newline canonical JSON object containing exactly the other four fields
  `{schemaVersion,status,scratch,regression}` with no domain prefix or suffix;
- `PostApplyPlan = {commands,sha256}`, containing only the four internal
  no-process/no-write rows below; `sha256` is SHA-256 of the no-newline
  canonical JSON object containing exactly `{"commands":commands}` with no
  domain prefix or suffix;
- `PostApplyTestReport = {schemaVersion,status,attempt,commands,results,passed,
  failed,notRun,resultsSha256,sha256}`, status `passed|failed`, exact plan
  equality, and integer counts summing to command count. `resultsSha256` is
  SHA-256 of the no-newline canonical `results` array; `sha256` is SHA-256 of
  the no-newline canonical object containing exactly every other field,
  including `resultsSha256`, with no domain prefix or suffix. Passed requires
  `passed:4,failed:0,notRun:0`; failed requires at least one failure and exact
  trailing `not_run` results.

All `FileRecord`s are descriptor-observed regular, one-link leaves whose mode
satisfies the exact `SafeRegularMode` predicate above.
Every array has a stated semantic order or is path/ID sorted. Nested objects are
closed; optional values are represented by required nullable fields, never by
shape drift.

`SourceProjection.schemaVersion` is exactly
`quant-radar-ui-ux-ux1b-source-mirror/v1` for every mirror/historical mirror
projection and exactly `quant-radar-ui-ux-supplemental-source/v1` for every
supplemental projection. `RuntimeReceipt.schemaVersion` is exactly
`quant-radar-ui-ux-runtime-receipt/v1`. Capture-intent `nonce` is exactly 32
lowercase hexadecimal characters; its `destinations` is the exact ordered
`EligibleDestination[]`. Every field named `lease` or `postApplyLease` is one
exact `FileRecord`.

`RollbackEntry` is a closed disposition-discriminated union:

| Disposition | Required null/equality pattern | Authority |
| --- | --- | --- |
| `restore_hunk_if_exact` | preimage/postimage/anchor nonnull; anchor path and image hashes equal the entry | only an authenticated owned `hunk|append` in a pre-existing dirty file |
| `restore_whole_if_exact` | preimage/postimage nonnull; anchor null | only a plan-created non-user whole file whose exact pre/post records are bound |
| `delete_scratch_if_exact` | preimage null; postimage nonnull; anchor null | only a path proven absent before plan creation and still equal to the bound final postimage |
| `retain_immutable` | anchor null; postimage nonnull; preimage is null for a newly published leaf or byte-equal nonnull for a pre-existing leaf | immutable root/evidence; never written or deleted by rollback |
| `retain_operational` | anchor null; postimage nonnull; preimage is null for a newly created leaf or byte-equal nonnull for a pre-existing leaf | lock/lease; never written or deleted by rollback |

Both images null, an anchor on any non-hunk disposition, unequal retained
pre/post bytes, or a path/disposition outside its exact Tier 0 authority fails.
For the two verifier scripts created before Tier 0, `delete_scratch_if_exact`
remains unresolved and unusable until preflight binds the exact final
`sourceProjection.records[path]` SHA/size/mode plus owner, safe mode, nlink, and
content CAS; bootstrap never deletes either provisional file.

Process outcomes are a closed union. `exited` requires integer return code,
null signal, and is passed only for code `0`; a nonzero code is failed.
`spawn_failed|timed_out|output_overflow` require failed status and null return
code/signal. `signaled` requires failed status, null return code, and a positive
signal. `timed_out` covers either the execution deadline or a post-exit family-
settlement deadline. An internal passed or failed row follows the exact errorCode/nullability
arm above and always has canonical empty streams. A skipped row uses
`status/outcome:"not_run"`, null errorCode/return code/signal, zero byte counts,
empty hashes, and null processGroupId/processFamily. Timeout or either stream
limit closes and waits for the complete candidate PGID-plus-marker union under
the exact signal/no-signal arms below before a result is published. A persisted runner receipt is always the
success-only arm above; capture success additionally authenticates every inner
frozen quiescence receipt. Missing, reused, raw-token-serializing,
wrong-observer, wrong-PGID, wrong-sample, unauthorized token drop, detached
tokenless child, or nonquiescent family evidence fails.

Before any permitted spawn, the controller requires
`signal.getsignal(SIGCHLD) is signal.SIG_DFL`; an inherited ignored/custom
disposition exits `5` before spawning, and the workflow never changes it. The
main-thread controller installs SIGINT/SIGTERM
handlers that only latch the first signal and never raise, exit, reap, or send
a signal. A latch already set at the final pre-spawn check prevents the spawn.
If it arrives during `Popen`, the controller does not branch on it until Popen
has either proved a definite no-child spawn failure or returned and the owner
has validated PID/PGID, registered both nonblocking stream FDs in its selector,
and registered kqueue (or proved the exact ESRCH fallback). It then enters the
same owned interruption cleanup
path; repeated signals remain latched, and original handlers are restored only
after closure or durable manual-audit disposition. SIGKILL remains the sole
uncatchable orphan case.

The imperative controller never calls `Popen.poll()`, `wait()`, or
`communicate()` before its decisive pre-reap observation. It creates no stream
reader thread. Runner stdout/stderr read FDs are nonblocking and remain
registered in one main-thread selector for the whole owned lifecycle; when an
observer is active, its two nonblocking FDs are temporarily registered in that
same selector. Every selector iteration waits at most 50 ms and never beyond
the earliest execution, settlement, cleanup, observer, or observer-wait
deadline. The exact stream constants are a 65,536-byte maximum `os.read`, at
most four reads and 262,144 bytes per ready FD per selector turn, and the fixed
role order `runner_stdout,runner_stderr,observer_stdout,observer_stderr`. The
start role rotates by one after every turn, skipping inactive roles; readiness
order or a continuously writable peer can never monopolize the loop. A ready
role stops for that turn on its first `EAGAIN`, EOF, four reads, 262,144 bytes,
or decisive state transition. After every nonempty read the controller hashes
and counts the chunk, retains at most the declared limit, samples the latched
interrupt and monotonic clock, performs a zero-time kqueue service, and checks
for the first limit crossing before another read. That first crossing latches
`output_overflow` and immediately returns control to the cleanup state machine;
later fair selector turns continue hashing/counting/draining while cleanup
advances. EOF deregisters/closes the role. HUP is not EOF until a read returns
zero bytes. Every selector turn—including a zero-event timeout, an
`EAGAIN`-only or EOF-only ready set, and a turn with zero active stream
roles—ends before another blocking wait or any non-overflow state transition
by sampling the latched interrupt and monotonic clock and performing exactly
one zero-time kqueue service. This end-of-turn service is additional to the
per-nonempty-read services above. A matching `NOTE_EXIT` found there is handled
immediately, so a quiet exit or an exit after its last output is recognized no
later than the first at-most-50-ms selector wait return after the event becomes
available. The latched
overflow dominates a simultaneous or earlier `NOTE_EXIT`, nonzero exit,
signal, and timeout. Absent overflow, an available `NOTE_EXIT` dominates the
execution timeout: immediately before declaring that deadline, the controller
drains every ready stream once and performs one zero-time kqueue read, then
follows the exit path if the event is present.

Any path that cannot obtain a receipt first reauthenticates and retains its
already-durable candidate-session gate or durably records its specified burned
capture-lineage manual gate, then deregisters and closes
all remaining local runner/observer read FDs, closes the selector and kqueue,
restores handlers, and releases its owned leases before returning the specified
bounded failure code. It never waits for EOF or joins an unbounded thread on
that path. A detached descendant that keeps either writer open therefore can
make quiescence fail but cannot keep the coordinator process or lease alive.
It immediately registers the child PID using the bound kqueue
`EVFILT_PROC/NOTE_EXIT` plan. Registration `ESRCH` is accepted only for the
short-lived race where an immediate authenticated observer sample contains
that same unreaped owned PID as a zombie; the PID cannot be reused while it
remains this process's unreaped child. That observation is retained as the
receipt's first phase under whichever closure grammar becomes decisive. A
successful registration must yield and consume exactly one matching NOTE_EXIT
before `pre_reap`; the controller services the watcher while settling and
cleanup observations run. The accepted ESRCH arm consumes no event. These are
the only two `ExitWatchResult` arms.

After `NOTE_EXIT` or its accepted fallback, a separate 25-second monotonic
family-settlement deadline starts. Without signaling or reaping, the
controller runs the exact observer immediately and then after each 50-ms
monotonic wait capped to the remaining budget. Every nondecisive valid sample
is retained in order as `settling_exit`. If overflow, family-settlement expiry,
or an owned interrupt later switches to failure cleanup, those samples remain
the permitted leading prefix of that failure receipt; they are never silently
discarded. Each observation is classified only after its two EOF fields and
the overflow latch are sampled. The first sample with exactly the owned zombie
leader, both runner streams at EOF without error, and no latched overflow is
the decisive `pre_reap` itself; this can be the immediate ESRCH-fallback
sample. If that succeeds, one
latched, one wait reaps the leader, verifies its result against base-16
`xstat`, and only then takes `post_reap`; its xstat selects `exited` versus
`signaled`. Overflow observed at any point switches to the failure cleanup
path. Expiry before natural family closure selects `timed_out` and also
switches to cleanup.

For `timed_out|output_overflow` or owned SIGINT/SIGTERM cleanup, a fresh
decision observation begins a separate 25-second monotonic cleanup deadline.
If it contains a non-zombie row in the
original PGID, it is `pre_term` and one successful `killpg(SIGTERM)` follows.
If instead it contains the owned zombie leader, no non-zombie original-PGID
row, and any number of other filtered rows, it is `pre_no_signal`; the controller
does not call `killpg`. After each unsuccessful closure observation it waits
50 ms capped to the remaining deadline and retains the sample under the
closureKind-specific `settling_*` phase. Such a sample is nondecisive exactly
when the leader is non-zombie, any non-leader filtered row exists, or either
runner EOF field is false. At the 3-second TERM grace boundary, a fresh union
containing a non-zombie original-PGID row becomes `pre_kill` and is followed by
the sole successful `killpg(SIGKILL)`; otherwise a nondecisive sample continues
passive `settling_term` observation. The 7-second KILL
grace does not extend the 25-second cleanup deadline: a non-zombie original-
PGID row at that boundary produces no receipt, while the same exact
nondecisive predicate with no non-zombie original-PGID row may be passively
observed as `settling_kill` until the cleanup deadline. Family cleanup signals
only the original PGID; the disjoint observer-failure arm may signal only its
directly owned observer PGID as defined above. A signal syscall error, a row
that violates its phase arm, persistent filtered rows, failure to reach a
fresh zombie-only `pre_reap`, or inability to obtain empty `post_reap` produces
no receipt and enters the operation-specific durable candidate-session or
capture-lineage manual-audit gate defined in this plan.
Every observer execution/wait is capped by the lesser of its plan timeout and
the remaining applicable budget, and no wait/sample/reap may start after that
deadline. The one leader wait result
must equal `leaderTermination.returnCode` or negative
`leaderTermination.signal`, and the decisive zombie xstat must equal its
waitStatus. Kqueue error, a missing event on an asserted exit path, a second
event after one was already consumed, early
reap, selector/stream failure, observer failure, or result mismatch
produces no quiescent receipt.

`RuntimeReceipt.python` is exactly
`{version,launcher,alias,resolvedExecutable,pyvenvConfig,sysPrefix,
sitePackages}`. The launcher is the authenticated workspace
`.venv/bin/python` `SymlinkRecord`; alias is the authenticated external
`cpython-3.11-macos-aarch64-none` `ExternalSymlinkRecord`; resolved executable
is the fixed CPython `ExternalFileRecord`; `pyvenvConfig` is the exact
workspace `FileRecord`; `sysPrefix` is the repository `.venv`; and
`sitePackages` is the `.venv` `RuntimeTreeRecord`. This separately binds the
launcher spelling that activates the venv and the executable leaf that
Seatbelt authorizes. `streamlit` and `playwright` are exact version strings;
`chromium` is exactly `{version,revision,executablePath}`. `directExecutables`
is the path-sorted three-record array containing only resolved CPython,
`/bin/ps`, and `/usr/bin/sandbox-exec`.

`captureRuntime` is exactly
`{pythonRuntimeRoots,browserRuntimeRoots,executables,executablesSha256}`. The
two Python runtime roots are `.venv` at reviewed tree digest
`d9802d618e8665deac940e1e65520f3d5aba29b8aff28fadc6f10e7c5a27f0cf`
and mode/uid/gid/device/inode `0755/501/20/16777229/946519`,
and resolved `sys.base_prefix` at reviewed tree digest
`30d9395d8b4a1efb614948a38fbbb472cfc9ce8be04230296986538431c1b332`
and `0755/501/20/16777229/595882`.
The one browser root is the exact Chromium app bundle at reviewed tree digest
`de171428dccc6cdbcc1da536bd4088f1e85f2ad9a42e32e7e74b06da1c33cf83`
and `0755/501/20/16777229/967797`.
These are frozen double-pass `_runtime_tree_sha256` constants; computing a new
digest and accepting it in the same invocation is forbidden. The path-sorted
`ExternalFileRecord[]` contains resolved Python, Seatbelt, `/bin/ps`, the
Playwright Node driver, and every executable regular file under that exact
Chromium app bundle; its 17-record canonical array digest is fixed to
`78c4b095bdce22c5399378a74dd63f1bbedd7c1e92b164aa7b4e33a301528ed6`.

`candidateRuntime` is exactly
`{headlessShellRuntime,headlessShellExecutable,sha256}`. The runtime is the
reviewed `RuntimeTreeRecord` at the candidate-only root/digest/metadata above;
the executable is the one exact `ExternalFileRecord` above; the digest covers
those two fields and is fixed to
`1fdaf2828d8a5a4d1ed0f6ee67acece3699d934747f146f8d32c60a85b31ed95`.
It is not a member of `captureRuntime`, and equality or
substitution between the app executable and default headless-shell executable
is forbidden.

OS execution enforcement is profile-wide, not parent-specific. The outer
coordinator may directly launch only exact venv Python, Seatbelt, and the
read-only `/bin/ps` observer. Within a frozen browser profile, the kernel grants
the authenticated family-wide union of Python, Node, and the frozen
Chromium bundle executable set; within the candidate browser profile, it grants
the authenticated family-wide union of Python, Node, and only the
candidate headless-shell process leaf. Source-reviewed code has the expected
Python-to-Node-to-browser launch graph, but neither schema nor review text
claims that Seatbelt enforces parent-specific edges. An
`sandbox-exec`-to-Python replacement is an exec transition inside the same
owned process family. `/usr/bin/true` and nested Seatbelt are expected-EPERM
negative targets and receive no authority. The frozen stack and candidate
coordinator revalidate their respective closed unions and prove descendant
quiescence, but do not observe or attest which Chromium helper/load image
appeared in an individual run; no receipt may contain or imply
`observedDescendantExecutables` without a reviewed stack rotation. `platform`
is exactly
`{macosVersion,build,darwinKernel,machine,identity}`; `tempRootParent` is the
normalized absolute owned temporary parent; and `sha256` hashes all preceding
fields.

The exact lifecycle top-level keys are:

| Schema | Exact top-level keys | Status |
| --- | --- | --- |
| `...theme-handoff-prechange/v1` | `schemaVersion,status,tierId,recoveryId,authorizationRecord,baseDraft,replacementPlan,traceability,createdControls,eligibleDestinations,liveRecords,anchors,authorities,priorRollbackSources,bundlePath,selfHash` | `captured` |
| `...theme-handoff-prechange-bundle/v1` | `schemaVersion,status,tierId,ownerMarker,archive,archivedPaths,namespaceLeafCount,selfHash` | `sealed` |
| `...theme-handoff-rollback/v1` | `schemaVersion,status,tierId,prechange,bundleManifest,entries,destructiveGitAllowed,selfHash` | `ready` |
| `...formal-handoff-preflight/v2` | `schemaVersion,status,recoveryId,authorizationRecord,baseDraft,replacementPlan,traceability,authorities,rollback,captureStack,task6,selectorDelta,historicalSelectorModes,sourceProjection,supplementalProjection,runtimeReceipt,eligibleDestinations,descriptorBudget,lease` | `passed` |
| `...capture-intent/v1` | `schemaVersion,status,recoveryId,preflight,nonce,lease,runnerPlans,sourceProjection,captureStack,runtimeReceipt,destinations` | `started` |
| `...capture-control-checkpoint/v1` | `schemaVersion,status,recoveryId,intent,runnerReceipt,bundle,runtimeReceipt` | `passed` |
| `...capture-pretheme-gate/v1` | `schemaVersion,status,recoveryId,intent,controlCheckpoint,runnerPlan,sourceProjection,captureStack,runtimeReceipt` | `passed` |
| `...capture-pretheme-checkpoint/v1` | `schemaVersion,status,recoveryId,gate,runnerReceipt,bundle,runtimeReceipt` | `passed` |
| `...capture-terminal/v1` | `schemaVersion,status,recoveryId,intent,controlCheckpoint,prethemeGate,prethemeCheckpoint,reason,runtimeReceipt` | `passed|revoked` |
| `...review-packet/v1` | `schemaVersion,status,kind,rootContract,lineageId,machineReport,prompt,promptSha256,inputs,inputsSha256,itemSetSha256,items` | `review_required` |
| `...manual-review/v2` | `schemaVersion,kind,status,reviewedAt,reviewer,packet,promptSha256,inputs,inputsSha256,itemSetSha256,decision,items,findings` | `accepted|rejected` |
| `...formal-handoff-candidate/v2` | `schemaVersion,status,recoveryId,authorizationRecord,baseDraft,replacementPlan,traceability,preflight,task6,task9,migration,historicalSelectorModes,sourceProjection,supplementalProjection,runtimeReceipt,proposedContract,proposedContractSha256` | `candidate` |
| `...formal-theme-handoff/v2` | the exact root keys above | `passed` |
| `...theme-lineage-prechange/v1` | `schemaVersion,status,rootContract,themeRunId,eligibleDestinations,runtimeReceipt` | `passed` |
| `...theme-batch-prechange/v1` | `schemaVersion,status,rootContract,lineagePrechange,batchId,themeRunId,livePreimages,eligibleDestinations,runtimeReceipt` | `passed` |
| `...theme-batch-bundle/v1` | `schemaVersion,status,rootContract,batchId,themeRunId,ownerMarker,changes,patch,testReport,mirrorComparison,supplementalComparison,namespaceLeafCount,selfHash` | `sealed` |
| `...theme-batch-candidate/v2` | `schemaVersion,status,rootContract,batchId,themeRunId,prechange,bundleManifest,changes,patch,testReport,mirrorComparison,supplementalComparison,runtimeReceipt,changesSha256` | `candidate` |
| `...theme-batch-attempt/v1` | `schemaVersion,status,rootContract,batchId,themeRunId,candidate,reviewPacket,manualReview,runtimeReceipt,livePreimages,applyOrder,changesSha256,postApplyLease,postApplyPlan` | `started` |
| `...theme-batch-postapply-tests/v1` | `schemaVersion,status,attempt,commands,results,passed,failed,notRun,resultsSha256,sha256` | `passed|failed` |
| `...theme-batch-rollback-intent/v1` | `schemaVersion,status,actor,rootContract,batchId,themeRunId,attempt,postApplyTestReport,observedStart,plannedPaths,runtimeReceipt` | `rollback_started` |
| `...theme-batch-reconciliation/v1` | `schemaVersion,status,actor,rootContract,batchId,themeRunId,attempt,postApplyTestReport,rollbackIntent,observedStart,action,finalState,affectedPaths,runtimeReceipt` | `verified_applied|aborted_before_write|rolled_back|blocked_unknown` |
| `...theme-batch-applied/v1` | `schemaVersion,status,rootContract,batchId,themeRunId,attempt,candidate,manualReview,reconciliation,livePostimages,mirrorProjection,supplementalProjection,runtimeReceipt,postApplyTestReport,changesSha256` | `passed` |
| `...theme-capture-intent/v1` | `schemaVersion,status,kind,rootContract,appliedBatch,stateAttestation,themeRunId,lease,runnerPlan,destination,runtimeReceipt` | `started` |
| `...theme-capture-checkpoint/v1` | `schemaVersion,status,kind,intent,runnerReceipt,bundle,runtimeReceipt` | `passed` |
| `...theme-state-candidate/v2` | `schemaVersion,status,rootContract,appliedBatch,themeRunId,captureIntent,captureCheckpoint,manifest,bundle,mirrorProjection,supplementalProjection,runtimeReceipt,visualItems` | `review_required` |
| `...theme-state-attestation/v2` | `schemaVersion,status,rootContract,appliedBatch,themeRunId,captureIntent,captureCheckpoint,candidate,reviewPacket,manualReview,manifest,mirrorProjection,supplementalProjection,runtimeReceipt` | `passed` |
| `...posttheme-comparison/v2` | `schemaVersion,status,rootContract,appliedBatch,stateAttestation,themeRunId,captureIntent,captureCheckpoint,pretheme,posttheme,sourceComparisons,runtimeReceipt,pairs,changedIdsSha256` | `review_required` |
| `...theme-closure/v2` | `schemaVersion,status,rootContract,appliedBatch,stateAttestation,themeRunId,machineComparison,reviewPacket,manualReview,posttheme,mirrorProjection,supplementalProjection,runtimeReceipt` | `passed` |

Every abbreviated schema prefix is exactly `quant-radar-ui-ux-`. Named nested
objects are closed as follows:

- `baseDraft`, `replacementPlan`, `traceability`, `preflight`, every lifecycle
  predecessor, every manifest/report/candidate/packet/review, and every
  cross-lifecycle authority is one `ArtifactRef`; `authorities` is the exact
  path-sorted `FileRecord[]` for the authority table above.
- Preflight `rollback` is exactly `{prechange,rollback,bundleManifest}` with
  three `ArtifactRef`s. `captureStack` is exactly
  `{contract,baseDigest,digest,members}` with one `FileRecord`, two SHA values,
  and the nine exact path-sorted member records. `task6` is exactly
  `{pages,controls,historicalSourceProjection}` with two `BundleRecord`s and
  one `SourceProjection`. `selectorDelta` is exactly `{contract,postimages}`
  with one `FileRecord` and the nine exact path-sorted `SourceRecord`s.
- `historicalSelectorModes` is the exact path-sorted nine-row
  `HistoricalSelectorMode[]`. Root/candidate `task9` has the exact seven fields
  defined above. `migration` is exactly
  `{machineReport,reviewPacket,manualReview,comparedCaptures}` with three
  `ArtifactRef`s and integer `comparedCaptures:117`.
- `themeBatchBoundary` is exactly `{paths,preimages}`, with the exact five
  ordered workspace paths and five path-matching `SourceRecord`s. `allowedChanges`
  is the literal object
  `{"production":[".streamlit/config.toml","app.py","ui/_design.py","requirements.txt"],"evidence":["docs/ui-ux/quant-radar-ui-v2-ux1b-classification.json"]}`.
- Tier 0 `createdControls` is the exact path-sorted four-record array for the
  two new scripts plus lock and lease. `eligibleDestinations` is the remaining
  exact Tier 0 table rows as `EligibleDestination[]`; `liveRecords` is the
  path-sorted retained `FileRecord[]` for `Tier0ExistingInputSet`;
  `anchors` is the exact path/kind-sorted `HunkAnchor[]` for every later
  Make/journal hunk. `priorRollbackSources` is the exact path-sorted
  `ArtifactRef[]` from the upstream rollback authorities; `bundlePath` is the
  one fixed bundle directory string. `selfHash` is literal
  `omitted-by-contract` and `destructiveGitAllowed` is false. The prechange
  schema deliberately has no `diagnosticPorcelainSha256`: the imported
  requirements do not authorize a Git subprocess, `directExecutables` remains
  the exact three-record set, and dirty-worktree safety is decided only by
  descriptor-authenticated `liveRecords`, exact `anchors`, and rollback
  records. That former diagnostic-only name is an unknown key and fails closed.
- Bundle `ownerMarker` and `archive` are `FileRecord`s, `archivedPaths` is the
  exact path-sorted array of existing files that a rollback hunk may read, and
  `namespaceLeafCount` is `3`. Rollback `entries` is a unique path-sorted
  `RollbackEntry[]`; a whole-file restore disposition is allowed only for a
  plan-created non-user file, while dirty Make/journal paths use exact hunk
  anchors. Nullable fields remain present.
- In `theme-batch-bundle`, `ownerMarker`, `patch`, and `testReport` are exact
  `FileRecord`s inside the sealed directory; in `theme-batch-candidate`,
  `patch` and `testReport` are exact `ArtifactRef`s to those same bytes.
  Batch/capture `lease` and attempt `postApplyLease` fields are exact
  `FileRecord`s, never path strings or generic artifact references.
- Review packet `inputs` is path-sorted `ArtifactRef[]`; `prompt` is the exact
  prompt object; `items` is exactly one machine-item shape for its kind.
  Manual-review `reviewer` is `{type,id}`, `items` is the matching sorted
  `{id,verdict,explanation}[]`, and `findings` is sorted `Finding[]`.
- Every `livePreimages`/`livePostimages` value is the exact ordered
  `MaterializedSourceRecord[]`; every batch `changes` value is the exact five
  ordered `BatchChangeRecord[]`; `applyOrder` is the exact five-path order in
  Scope. `observedStart` and `finalState` are exact five-record
  `LiveImageRecord[]`; reconciliation `observedStart` is always the current
  actor's descriptor-observed snapshot immediately before its action, whereas
  rollback-intent `observedStart` remains the historical pre-rollback snapshot;
  `affectedPaths` follows the exact reconciliation union above. Rollback-intent
  `plannedPaths` is the nonempty reverse-apply ordered
  subset whose intent-time images are postimages; an unknown-bearing intent is
  valid only for `actor:original` and records all current exact postimages—not
  necessarily a hole-free prefix—that owner may restore while every unknown
  union row remains untouched. A nullable `postApplyTestReport` and nullable
  `rollbackIntent` are still required keys.
- Theme-state `visualItems` is the exact 12 sorted standalone machine items;
  posttheme `pairs` is the exact 81 capture-ID-sorted pair items; and
  `sourceComparisons` is exactly
  `{mirror:ProjectionComparison,supplemental:ProjectionComparison}`. `bundle`
  is one `BundleRecord`; every `sourceProjection`, `mirrorProjection`, and
  `supplementalProjection` validates its exact closed projection schema.
- Theme capture intent `kind` is `theme-states|posttheme`; `stateAttestation`
  is required null for theme-states and the exact attestation `ArtifactRef` for
  posttheme. `lease` is a `FileRecord`, destination is the exact derived path,
  and `runnerPlan` is the one exact plan above. Capture checkpoint kind must
  match intent, its runner receipt must equal the plan and return zero, and its
  `BundleRecord` must equal the exact authenticated terminal namespace.

`reason` is
required null for passed terminal and one closed failure enum for revoked.
The enum is exactly `intent_owner_lost|control_runner_failed|
pretheme_gate_failed|pretheme_runner_failed|source_drift|stack_drift|
runtime_drift|control_nested_quiescence_unverified|
pretheme_nested_quiescence_unverified|interrupted`. Either nested-quiescence value is revoked,
non-authoritative, and permanently requires the manual host-process audit
described above; it is never evidence that an inner family was closed.
`control_runner_failed|pretheme_runner_failed` are permitted only for a
definite spawn failure proved to occur before any outer child/process group
exists. `interrupted` is permitted only when the same intent owner has not yet
launched the next runner. `intent_owner_lost` is permitted only when the exact
durable prefix ends at a valid control checkpoint with no pretheme gate, so a
second runner could not have started. Source/stack/runtime/gate reasons likewise
require a durable or same-owner proof that no next runner existed. Once an
outer runner exists, every non-success path,
including nonzero exit, signal, timeout, overflow, invalid/missing manifest, or
interruption, uses the stage-specific nested-quiescence value; a generic reason
must never conceal an unverified inner family.
Terminal checkpoint fields are required nullable `ArtifactRef`s; a passed
terminal requires all nonnull, while a revoked terminal requires precisely the
longest authenticated prefix and nulls thereafter. `RunnerReceipt` timestamps
are UTC RFC3339 seconds, return code/process-group ID are integers, and only
return code zero can enter a passed checkpoint.
Applied `reconciliation` is required null for the uninterrupted creator path
and the exact `verified_applied` `ArtifactRef` for the all-post crash-recovery
path; every other reconciliation status forbids an applied receipt.
The reconciliation discriminated union is exact. A nonnull `rollbackIntent`
is the exact `ArtifactRef` of the one committed intent for this attempt; its
root/batch/run/attempt/runtime/report fields equal the reconciliation fields.

| Status | Actor / action | State, report, and rollback-intent invariants |
| --- | --- | --- |
| `verified_applied` | `reconciler / verify_only` | observed/final are all postimage; exact passed report required; affected empty; rollback intent null |
| `aborted_before_write` | `reconciler / no_write` | observed/final are all preimage; report null; affected empty; rollback intent null |
| `rolled_back` | `original|reconciler / rollback_reverse` | nonnull exact rollback intent with no unknown; reconciliation `postApplyTestReport` equals the intent's `postApplyTestReport`; observed is this actor's exact start snapshot and is a reachable rollback prefix of the intent (equal to intent start for the original); final all preimage; affected equals the intent's full `plannedPaths`, including paths restored by an earlier crashed owner |
| `blocked_unknown` | `original / rollback_known_prefix` | nonnull exact unknown-bearing rollback intent; reconciliation `postApplyTestReport` equals the intent's `postApplyTestReport` and observed equals the intent snapshot; affected is one leading (possibly full) prefix of intent `plannedPaths` actually restored before any definite new drift, final makes exactly those rows preimage, and every other union row equals a fresh descriptor observation without overwriting unknown/absent/nonregular state |
| `blocked_unknown` | `original / no_write` | rollback intent null; observed contains at least one unknown union row and zero exact postimages, report equals the existing authenticated report or null if absent, final equals the exact observed union array, and affected is empty |
| `blocked_unknown` | `reconciler / no_write` | if any prior intent exists, rollback intent is its exact nonnull ref, reconciliation `postApplyTestReport` equals the intent's `postApplyTestReport`, and observed is the fresh current union snapshot: either any state after an unknown-bearing intent or an invalid hole/reversion/unknown continuation of a no-unknown intent; a no-unknown safe reachable prefix is forbidden here and must resume instead. Without an intent, rollback intent is null, `postApplyTestReport` equals the existing authenticated report or null if absent, and observed is current; final equals the exact observed union array and affected is empty |

`descriptorBudget` is exactly
`{baselineOpenCount,baselineMaxFd,hardLimit,protocolAdditional,peakOpenCount,
requiredSoft,softApplied,reserve}`, reserve `64`. `eligibleDestinations` is an
exact array of `{path,exists:false}`. Cross-lifecycle references are
`ArtifactRef`s and are always reopened rather than trusted by prior exit code.

The sealed bundle contains exactly 14 leaves: owner; five pre; five post; patch;
test report; manifest. Its `selfHash` is `omitted-by-contract`. Candidate
`changesSha256` hashes the canonical five-record array. `ProjectionComparison`
uses exact `changes: ProjectionChangeRecord[]`; the old undefined
`changedRecords` field does not exist. The root contains
`themeBatchBoundary`, not the old ambiguous `themeBatch` object.

## Tiered dirty-worktree and rollback contract

Live authenticated bytes, never Git `HEAD`, are expected-old authority. The
bootstrap circularity is explicit: after package authorization, implementation
may first create only the two currently absent verifier/test paths. Their add
operations must fail on collision, and scratch-only unit tests run before any
workspace evidence or existing file changes. The completed verifier then runs
`bootstrap`; no other implementation path may change before Tier 0 succeeds.
Tier 0 records those two paths as `preconditionAbsent:true`, their observed live
records, and deletion authority deferred to the exact final posthash in
preflight. This is the only pre-Tier-0 creation exception.

Tier 0 uses deterministic ID `20260720T000000Z`. The following table is exactly
`Tier0DestinationSet`; category labels, globs, and inherited naming assumptions
are forbidden:

| Exact path | Tier 0 observation / action |
| --- | --- |
| `scripts/ui_ux_theme_handoff.py` | `preconditionAbsent:true`; bootstrap-created live record |
| `scripts/test_ui_ux_theme_handoff.py` | `preconditionAbsent:true`; bootstrap-created live record |
| `.claude/ui_snapshots/ux1b/.formal-theme-handoff.lock` | absent, then fresh-created operational record |
| `.claude/ui_snapshots/ux1b/recovery/.capture-20260719T211915Z.lease` | absent, then fresh-created operational record |
| `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-prechange.json` | absent self-destination |
| `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-rollback.json` | absent future destination |
| `.claude/ui_snapshots/ux1b/recovery/theme-handoff-prechange-20260720T000000Z/` | absent owned bundle directory |
| `.claude/ui_snapshots/ux1b/recovery/theme-handoff-prechange-20260720T000000Z/.quant-radar-theme-handoff-owner` | absent bundle leaf |
| `.claude/ui_snapshots/ux1b/recovery/theme-handoff-prechange-20260720T000000Z/prechange-files.tar` | absent bundle leaf |
| `.claude/ui_snapshots/ux1b/recovery/theme-handoff-prechange-20260720T000000Z/bundle-manifest.json` | absent bundle leaf |
| `.claude/ui_snapshots/ux1b/recovery/theme-handoff-preflight-20260719T211915Z.json` | absent future destination |
| `.claude/ui_snapshots/ux1b/recovery/capture-intent-20260719T211915Z.json` | absent future destination |
| `.claude/ui_snapshots/ux1b/recovery/capture-control-checkpoint-20260719T211915Z.json` | absent future destination |
| `.claude/ui_snapshots/ux1b/recovery/capture-pretheme-gate-20260719T211915Z.json` | absent future destination |
| `.claude/ui_snapshots/ux1b/recovery/capture-pretheme-checkpoint-20260719T211915Z.json` | absent future destination |
| `.claude/ui_snapshots/ux1b/recovery/capture-terminal-20260719T211915Z.json` | absent future destination |
| `.claude/ui_snapshots/ux1b/recovery/postcontrol-controls-20260719T211915Z/` | absent future namespace |
| `.claude/ui_snapshots/ux1b/recovery/canonical-pretheme-20260719T211915Z/` | absent future namespace |
| `.claude/ui_snapshots/ux1b/recovery/control-migration-20260719T211915Z.json` | absent future destination |
| `.claude/ui_snapshots/ux1b/recovery/control-migration-review-packet-20260719T211915Z.json` | absent future destination |
| `.claude/ui_snapshots/ux1b/review-intake/` | absent future operational directory |
| `.claude/ui_snapshots/ux1b/review-intake/control-migration-20260719T211915Z.json` | absent external-intake destination |
| `.claude/ui_snapshots/ux1b/recovery/control-migration-manual-review-20260719T211915Z.json` | absent future destination |
| `.claude/ui_snapshots/ux1b/recovery/theme-handoff-candidate-20260719T211915Z.json` | absent future destination |
| `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json` | absent future destination |

The first bootstrap transaction has this exact order while retaining the
global lock and capture lease FDs:

1. revalidate authorization/package, the final two script records, all existing
   scoped preimages, and absence of every not-yet-created table path;
2. fresh-create, lock, fsync, and reopen the global lock, minting
   `FreshLockGrant`;
3. fresh-create, lock, fsync, and reopen the capture lease;
4. no-replace publish and reopen the prechange record, which binds both absent
   control preconditions, all four created control records, and all remaining
   absent destinations;
5. build the exact three-leaf bundle in a private sibling, fsync every leaf and
   directory, commit the whole directory with `RENAME_EXCL`, fsync the retained
   destination parent, and same-inode reopen the complete tree;
6. no-replace publish and reopen rollback JSON as the final Tier 0 marker; it
   binds the prechange and bundle-manifest `ArtifactRef`s and every exact
   rollback entry;
7. reopen and reauthenticate the entire lock/lease/prechange/three-leaf-bundle/
   rollback chain before reporting Tier 0 complete.

Only that complete seven-part chain is authenticated Tier 0. A later
`bootstrap` may acquire the retained existing lock and return read-only success
only after validating that exact complete chain; it creates or repairs nothing.
Any publication uncertainty exits `6` and stops the current owner. A later
bootstrap returns read-only success only if it finds and reauthenticates the
exact complete terminal chain; an absent or unresolved strict prefix, collision,
or mismatch burns this bootstrap lineage and requires a separately reviewed
recovery/new baseline. A prefix is never completed by adopting, deleting,
overwriting, or regenerating a missing member. The rollback JSON is therefore
the terminal marker, not the prechange file or bundle alone.

`Tier0ExistingInputSet` is separate and read-only. It is exactly: `Makefile`;
the fixed recovery Markdown; `.agents/scribe.md`, `.agents/atlas.md`,
`.agents/builder.md`, and `.agents/PROJECT.md`; the frozen base draft; this plan
and ledger; the capture
stack contract plus its exact nine declared members; both exact Task 6
manifests plus every uniquely referenced child artifact; every
workspace-relative authority-table path; and the five live production batch
preimages. These are retained inputs/CAS authority only and never absence or
creation ownership. Missing, duplicate, extra-reference, or drifting inputs
fail bootstrap.

Tier 0 records full live `FileRecord`s for existing Make, recovery
documentation, and skill journals, plus exact hunk/append anchors for later
Make/journal writes, the full upstream/package authority, and prior
authenticated rollback sources.
Lock and lease are not included in preflight's future-absence array: Tier 0
creates them, and preflight only reopens/binds their created records.

The bundle has exactly owner marker, archive, and manifest. Self-hashes are
`omitted-by-contract`; immutable records are never rewritten for self-reference.
Any collision, extra leaf, unsafe metadata, or reopen mismatch stops before an
existing source write.

Tier 1 has two nonoverlapping records. Their `eligibleDestinations` arrays are
exactly the rows assigned to them here after substituting authenticated `R/B/T`:

| Owner | Exact absent destination |
| --- | --- |
| lineage | `.claude/ui_snapshots/ux1b/.theme-batch-postapply-R.lease` |
| lineage | `.claude/ui_snapshots/ux1b/theme-batch-attempt-R.json` |
| lineage | `.claude/ui_snapshots/ux1b/theme-batch-postapply-tests-R.json` |
| lineage | `.claude/ui_snapshots/ux1b/theme-batch-rollback-intent-R.json` |
| lineage | `.claude/ui_snapshots/ux1b/theme-batch-reconciliation-R.json` |
| lineage | `.claude/ui_snapshots/ux1b/theme-batch-applied-R.json` |
| lineage | `.claude/ui_snapshots/ux1b/.theme-states-T.lease` |
| lineage | `.claude/ui_snapshots/ux1b/theme-state-capture-intent-T.json` |
| lineage | `.claude/ui_snapshots/ux1b/theme-state-capture-checkpoint-T.json` |
| lineage | `.claude/ui_snapshots/ux1b/theme-states-T/` |
| lineage | `.claude/ui_snapshots/ux1b/theme-state-candidate-T.json` |
| lineage | `.claude/ui_snapshots/ux1b/review-packet-theme-states-T.json` |
| lineage | `.claude/ui_snapshots/ux1b/review-intake/theme-states-T.json` |
| lineage | `.claude/ui_snapshots/ux1b/theme-state-manual-review-T.json` |
| lineage | `.claude/ui_snapshots/ux1b/theme-state-attestation-T.json` |
| lineage | `.claude/ui_snapshots/ux1b/.posttheme-T.lease` |
| lineage | `.claude/ui_snapshots/ux1b/posttheme-capture-intent-T.json` |
| lineage | `.claude/ui_snapshots/ux1b/posttheme-capture-checkpoint-T.json` |
| lineage | `.claude/ui_snapshots/ux1b/posttheme-T/` |
| lineage | `.claude/ui_snapshots/ux1b/posttheme-comparison-candidate-T.json` |
| lineage | `.claude/ui_snapshots/ux1b/review-packet-posttheme-T.json` |
| lineage | `.claude/ui_snapshots/ux1b/review-intake/posttheme-T.json` |
| lineage | `.claude/ui_snapshots/ux1b/theme-delta-manual-review-T.json` |
| lineage | `.claude/ui_snapshots/ux1b/theme-closure-T.json` |
| batch | `.claude/ui_snapshots/ux1b/theme-batches/R/B/` |
| batch | `.claude/ui_snapshots/ux1b/review-intake/theme-batch-R-B.json` |

The fixed `theme-lineage-prechange-R.json` binds the only `T` for `R` and all
24 lineage rows. One `theme-batch-prechange-R-B.json` per batch binds that
lineage, five live preimages, and only the two batch rows. A new reviewed `B`
may be claimed while the shared attempt is absent; it must reuse the one bound
`T`. The two claim paths themselves are separately required absent and are
committed no-replace; neither is included in its own destination array. No
record contains a glob or claims a path owned by the other.

Every rollback entry has one exact disposition:

```text
restore_hunk_if_exact
restore_whole_if_exact
delete_scratch_if_exact
retain_immutable
retain_operational
```

User-dirty files use exact hunk/append CAS against live bytes. Production batch
rollback uses the sealed preimages and refuses unknown live bytes. Root and
published evidence are `retain_immutable`; lock and lease are
`retain_operational`; this includes Task 9, postapply, theme-state, and
posttheme lease leaves. Scratch deletion requires exact path, owner, mode, link
count, lineage claim, namespace leaf set, and recorded posthash. Rollback never
uses reset/checkout, never restores a whole dirty file, and never deletes root,
evidence, lock, or lease.

Immediately before each source write, compare the whole preimage or exact
owned hunk/append boundary. Unexplained drift stops that write. Actual diff is
compared to this plan after implementation; scope drift is fixed or separately
reviewed before capture.

## CLI contract

Production CLI resolves the verified repository root and derives every path.
It accepts no arbitrary output/destination/workspace path. Internal functions
accept an explicit scratch workspace FD for tests. Exact public grammar is:

```text
ui_ux_theme_handoff.py bootstrap --recovery-id ID --json
ui_ux_theme_handoff.py verify-python-syntax --json
ui_ux_theme_handoff.py preflight --recovery-id ID --authorization-record-sha SHA --json
ui_ux_theme_handoff.py verify-preflight --recovery-id ID --json
ui_ux_theme_handoff.py capture-task9 --recovery-id ID --preflight PATH --json
ui_ux_theme_handoff.py reconcile-task9 --recovery-id ID --json
ui_ux_theme_handoff.py prepare-review --kind control-migration --recovery-id ID --json
ui_ux_theme_handoff.py publish-review --kind control-migration --recovery-id ID --json
ui_ux_theme_handoff.py prepare-handoff --recovery-id ID --json
ui_ux_theme_handoff.py verify-handoff-candidate --recovery-id ID --json
ui_ux_theme_handoff.py publish-handoff --recovery-id ID --json
ui_ux_theme_handoff.py verify-handoff [--require-pristine] --json
ui_ux_theme_handoff.py init-theme-batch --batch-id ID --theme-run-id ID --json
ui_ux_theme_handoff.py seal-theme-batch --batch-id ID --theme-run-id ID --json
ui_ux_theme_handoff.py publish-review --kind theme-batch --batch-id ID --theme-run-id ID --json
ui_ux_theme_handoff.py verify-theme-batch-ready --batch-id ID --theme-run-id ID --json
ui_ux_theme_handoff.py apply-theme-batch --batch-id ID --theme-run-id ID --json
ui_ux_theme_handoff.py reconcile-theme-batch --json
ui_ux_theme_handoff.py verify-theme-batch-applied --json
ui_ux_theme_handoff.py capture-theme-states --theme-run-id ID --json
ui_ux_theme_handoff.py reconcile-theme-states --theme-run-id ID --json
ui_ux_theme_handoff.py publish-review --kind theme-states --theme-run-id ID --json
ui_ux_theme_handoff.py close-theme-states --theme-run-id ID --json
ui_ux_theme_handoff.py capture-posttheme --theme-run-id ID --json
ui_ux_theme_handoff.py reconcile-posttheme --theme-run-id ID --json
ui_ux_theme_handoff.py publish-review --kind posttheme --theme-run-id ID --json
ui_ux_theme_handoff.py finalize-theme --theme-run-id ID --json
```

`seal-theme-batch`, `capture-theme-states`, and `capture-posttheme` publish
their deterministic review packets; therefore `prepare-review` is needed only
for the existing control-migration report. Theme-state/posttheme coordinators
hold the global lock while launching the frozen runner and verifying its
terminal bundle. Before a fresh intent, the operational lease may be absent or
an exact unlocked retained leaf; intent/checkpoint/output/candidate/packet must
all be absent. Partial same-ID output burns that `T`, is never deleted/retried,
and requires reviewed supersession. Direct runner output lacks a coordinator
intent/checkpoint/candidate/packet and can never close a task.

Every `--recovery-id` value is a `RecoveryId`, every `--batch-id` is a
`BatchId`, and every `--theme-run-id` is a `ThemeRunId`; CLI parsing and stored
schema fields use the same named grammar. Root path is fixed; `R` is derived
from its authenticated SHA. Missing, extra, duplicate, or conflicting flags exit `2`.
`probe-capability` is not public or private grammar and always exits `2`; real
capability probes use only the fixed authenticated `python -c` bootstrap below.
`--authorization-record-sha` is exactly the V2 canonical body SHA and must
equal `AuthorizationBinding.bodySha256`; it is never a Markdown file SHA.
The private child grammar is not exposed in help and is accepted only with the
inherited descriptor/nonce capability.

Exit codes are:

| Code | Meaning |
| ---: | --- |
| `0` | created, read-only verified, safe regular-evidence reconciliation, or completed |
| `2` | CLI grammar |
| `3` | precondition, schema, authentication, transition, or precommit failure |
| `4` | invalid fixed-path or owned lifecycle-namespace collision |
| `5` | dependency, filesystem primitive, runtime, or FD budget unavailable |
| `6` | a publication or private session/cleanup rename may have committed; no grant/advance; fresh reconciliation/scan required |
| `7` | global, Task 9, postapply, or theme-capture lease active |
| `8` | consumptive intent/attempt exists, revoked, aborted, partial, or rolled back; lineage burned |
| `9` | unknown live theme, capture-process, or candidate-session state; manual coordination required |
| `130` | interrupted after exact owned-process cleanup and any permitted revoke |

Private child returns only `0/3/5`. Success stdout is one canonical
`{kind,path,sha256,status}` object. Errors are bounded, workspace-relative,
secret-free stderr with no success stdout.

## Make contract

Make adds these fail-closed targets:

```text
ui-ux1b-theme-handoff-bootstrap
ui-ux1b-theme-handoff-preflight
ui-ux1b-recovery-postcontrol
ui-ux1b-recovery-reconcile
ui-ux1b-control-migration-review-prepare
ui-ux1b-control-migration-review
ui-ux1b-theme-handoff-prepare
ui-ux1b-theme-handoff
ui-ux1b-theme-batch-init
ui-ux1b-theme-batch-seal
ui-ux1b-theme-batch-review
ui-ux1b-theme-batch-ready
ui-ux1b-theme-batch-apply
ui-ux1b-theme-batch-reconcile
ui-ux1b-theme-batch-verify
ui-ux1b-theme-states
ui-ux1b-theme-states-reconcile
ui-ux1b-theme-states-review
ui-ux1b-theme-states-close
ui-ux1b-posttheme
ui-ux1b-posttheme-reconcile
ui-ux1b-posttheme-review
ui-ux1b-theme-close
```

The existing `ui-ux1b-recovery-postcontrol` recipe invokes exactly one
`capture-task9` coordinator; it contains no direct postcontrol or pretheme
runner command. Theme-state and posttheme targets likewise invoke their
coordinators. `UX1B_RECOVERY_ID`, `UX1B_HANDOFF_PREFLIGHT`,
`UX1B_THEME_BATCH_ID`, and `UX1B_THEME_RUN_ID` are explicit nonempty variables;
no timestamp default is allowed. Every nonzero status propagates. Static tests
reject masked, reordered, duplicated, direct-runner, forced-success, or
attempt-only closure paths.

## Exact theme test plans

The sealed scratch report's `commands` is exactly these seven internal
`CommandRecord`s in order; each implementation is a named pure verifier branch
over retained pre/post descriptors:

| ID | Exact obligation |
| --- | --- |
| `TB-SCRATCH-001-PATHS` | exact five path/order/mode set and no extra diff |
| `TB-SCRATCH-002-CONFIG` | TOML parses and exact R1B-04 primary/link/underline values hold |
| `TB-SCRATCH-003-SYNTAX` | changed Python parses with runtime and Python 3.10 AST grammar |
| `TB-SCRATCH-004-TOKENS-CSS` | exact semantic tokens, trusted scoped selectors, and forbidden-selector scan pass |
| `TB-SCRATCH-005-INJECTION` | one new static no-input CSS injection and unchanged legacy metric injection hold |
| `TB-SCRATCH-006-VERSION` | `requirements.txt` pins exactly installed Streamlit `1.57.0` as authorized |
| `TB-SCRATCH-007-CLASSIFICATION` | pending-to-accepted forward ledger, UX-1A backward projection, primary/danger unions, and fail-soft protected hashes pass |

Each record is `{id,kind:"internal",execution:null}`. Empty, missing,
reordered, duplicate, or unknown IDs fail; all seven `CommandResult`s must pass
before candidate/packet publication.

The sealed `CandidateRegressionReport.commands` is exactly the 37 rows below
in listed order. Row 031 is an internal protected-contract replacement for the
unsafe subprocess fixture described below. For rows 001-017, 019-030, and 032-036,
`execution.argv` is exactly
`["/Users/ken/Workspace/AI/surge-screener/.venv/bin/python","-B",SCRIPT]`;
row 018 has the one exact fixed-inline argv below;
for row 037 `execution.argv` is exactly the same first two values plus
`["-m","pip","check"]`. Those 36 external rows are
`kind:"candidate_python"` and execute with cwd equal to the descriptor-bound
candidate workspace, never live `.`. Row 031 is
`{kind:"internal",execution:null}`.

| ID | SCRIPT / exact action |
| --- | --- |
| `POST-001-ARTIFACT-LOADER` | `scripts/test_artifact_loader.py` |
| `POST-002-API` | `scripts/test_api.py` |
| `POST-003-MOMENTUM-OPTIONS` | `scripts/test_momentum_options.py` |
| `POST-004-RISK-GUARD` | `scripts/test_risk_guard_technical.py` |
| `POST-005-INDUSTRY-ROLES` | `scripts/test_industry_roles.py` |
| `POST-006-INFLUENCER` | `scripts/test_influencer_roster.py` |
| `POST-007-TRADE-STATE` | `scripts/test_trade_state.py` |
| `POST-008-OPTIONS-DISPLAY` | `scripts/test_options_cockpit_display.py` |
| `POST-009-READ-API` | `scripts/test_ui_read_api.py` |
| `POST-010-AI-UPDATES-API` | `scripts/test_ui_ai_updates_api.py` |
| `POST-011-FUND-CATALOG-API` | `scripts/test_ui_fund_catalog_api.py` |
| `POST-012-IV-HISTORY-API` | `scripts/test_ui_iv_history_api.py` |
| `POST-013-OPTIONS-FLOW-API` | `scripts/test_ui_options_flow_api.py` |
| `POST-014-COMPONENTS` | `scripts/test_ui_ux_components.py` |
| `POST-015-UX1A-SAFETY` | `scripts/test_ui_ux1a_safety.py` |
| `POST-016-CONTRACT` | `scripts/test_ui_ux_contract.py` |
| `POST-017-FIXTURES` | `scripts/test_ui_ux_fixtures.py` |
| `POST-018-SNAPSHOT-MATRIX` | exact 55-test candidate-safe subset bootstrap below |
| `POST-019-THEME` | `scripts/test_ui_ux_theme.py` |
| `POST-020-THEME-MATRIX` | `scripts/test_ui_ux_theme_matrix.py` |
| `POST-021-AI-CHAT-STORE` | `scripts/test_ai_chat_store.py` |
| `POST-022-CANDIDATE-VIEW` | `scripts/test_candidate_controls_view.py` |
| `POST-023-SCHEDULES` | `scripts/test_sys_schedules_reflection.py` |
| `POST-024-NAVIGATION` | `scripts/test_dashboard_navigation.py` |
| `POST-025-HARD-FILTER` | `scripts/test_hard_filter_yfinance.py` |
| `POST-026-PIPELINE-CONTROLS` | `scripts/test_candidate_pipeline_controls.py` |
| `POST-027-CANDIDATE-OUTCOMES` | `scripts/test_candidate_outcomes.py` |
| `POST-028-RANK` | `scripts/test_rank_candidates.py` |
| `POST-029-REACH-AUTH` | `scripts/test_agent_reach_auth.py` |
| `POST-030-REACH-SOCIAL` | `scripts/test_agent_reach_social_bridge.py` |
| `POST-031-SOCIAL-CLI-CONTRACT` | internal proof that the protected social CLI/test/import-closure hashes equal preflight, Streamlit runtime is unchanged, and none of the five overlays enters that closure |
| `POST-032-SOCIAL-OUTCOMES` | `scripts/test_social_intelligence_outcomes.py` |
| `POST-033-LLM-PROGRESS` | `scripts/test_llm_score_progress.py` |
| `POST-034-RUN-STATUS` | `scripts/test_run_status.py` |
| `POST-035-DOCKER-CONTRACT` | `scripts/test_docker_runtime_contract.py` |
| `POST-036-CLAUDE-AUTH` | `scripts/test_claude_auth_flow.py` |
| `POST-037-PIP-CHECK` | exact `-m pip check` argv described above |

Row 031 is not allowed to execute the current
`scripts/test_social_intelligence.py` inside this lifecycle because that test
creates a random writable-temp executable with an `/usr/bin/env python3`
shebang; granting temp-tree, env, and system-Python exec would violate the
closed runtime. Its internal replacement requires the exact five-record
`protectedClosures.socialCli`, installed-runtime parity, and disjoint overlays.
The original test command remains mandatory in the ordinary preflight and final
developer verification gates, where it grants no lifecycle authority.

Row 018 cannot execute the whole snapshot-matrix test file inside Seatbelt:
one test deliberately starts nested `/usr/bin/sandbox-exec`, and one exercises
a Darwin cleanup fallback that may execute setuid `/bin/ps`; both are required
to remain denied inside the candidate profile. Its argv is therefore exactly
`["/Users/ken/Workspace/AI/surge-screener/.venv/bin/python","-B","-c",
SNAPSHOT_SUBSET_BOOTSTRAP]`, where the bootstrap is the exact 103 UTF-8 bytes
(no newline)
`from scripts.ui_ux_theme_handoff import _run_snapshot_candidate_subset;_run_snapshot_candidate_subset()`
at SHA-256
`be07f63440b229d004bb477ca2599215f12234cae775c6d19e38037b3385046a`.
The private function accepts no arguments (`sys.argv` is exactly `["-c"]`), is
absent from argparse/help, and a production CLI token
`snapshot-candidate-subset` exits `2`.

Before executing a test, the helper requires the candidate test file SHA
`1727c8a4fdec6c485bf08152d8eb1c1c3667b041ea4596899def981634c374be`,
the exact `protectedClosures.snapshotMatrix`, and the candidate handoff-module
SHA bound by the candidate manifest. Because direct script execution normally
supplies `scripts/` as `sys.path[0]` while `python -c` does not, the helper
requires cwd to equal the descriptor-bound candidate root, derives that root's
symlink-free `scripts` directory from its authenticated `__file__`, rejects any
preloaded capture-stack module under either its exact bare name or
`scripts.<name>`, and temporarily prepends exactly that candidate scripts path
at `sys.path[0]`. It loads the test file with run name
`quant_radar_snapshot_subset`; before emitting success it requires every loaded
bare or package-qualified capture-stack module's normalized `__file__` and SHA to equal the
matching candidate-manifest/protected-closure record, then restores the exact
prior `sys.path`. A live-workspace or alternate module origin fails. The loaded
`TESTS` must be exactly 57 unique
ordered callable objects whose `__name__` values have canonical-array SHA
`d5eea7859ce4c25e37d4029d513e87a323b64262249ee04e2b0ee7975bd555b6`
and whose `__module__` values all equal that run name. The only excluded names,
in this exact order, are
`test_ux1b_cleanup_retries_real_child_and_retains_persistent_runtimes` and
`test_ux1b_darwin_sandbox_contract_has_only_two_allowed_ports`. The remaining
55 names retain source order and have canonical-array SHA
`21b850117a682e1ea5d152f6f352f7054691b476e5b035b512bd8e759aa92a7a`.

The helper first requires the authenticated Playwright/default-browser
preconditions so the selected real-Chromium test cannot take its optional
missing-browser return. It executes all 55 exactly once, captures their output,
requires captured stdout to be empty and captured stderr to be exactly 4475
bytes at SHA
`1f18b239be65c1b83ea21f049998b0dc152c27147c127279cf411813c934b9dd`,
then emits only this 328-byte canonical document with no newline and empty
process stderr:

```json
{"excluded":["test_ux1b_cleanup_retries_real_child_and_retains_persistent_runtimes","test_ux1b_darwin_sandbox_contract_has_only_two_allowed_ports"],"failed":0,"passed":55,"schemaVersion":"quant-radar-ui-ux-snapshot-subset/v1","selectedSha256":"21b850117a682e1ea5d152f6f352f7054691b476e5b035b512bd8e759aa92a7a","status":"passed"}
```

Those bytes have SHA-256
`7cbbba944c76360ffd12debafc148d61b7bfdd145b3c84c597c8cacda2b4fc49`.
The row-018 `CommandResult` must bind exactly that stdout hash/size, empty
stderr, and a quiescent `token_pgid` receipt over the original PGID unioned with
all same-UID exact marker matches. Its
`SnapshotSubsetReceipt` uses schema
`quant-radar-ui-ux-snapshot-subset-receipt/v1`, commandId
`POST-018-SNAPSHOT-MATRIX`, the bootstrap/test/all/selected/output constants
above, runnerModuleSha256 equal to the candidate manifest's
`scripts/ui_ux_theme_handoff.py` record, the exact exclusion array,
`passed:55`, and `failed:0`. Any skip, early return precondition, different
callable/module/name/order, extra output, missing test, or direct whole-file
execution fails the row.

The complete command
`.venv/bin/python -B scripts/test_ui_ux_snapshot_matrix.py` remains mandatory
and must report 57/57 in both the outer preflight and final developer gates. It
is not a candidate command and grants no lifecycle authority; the protected
source closure plus that outer result carry the two excluded OS-isolation
tests.

The 36 external execution plans have stdin `devnull`, a fresh process group,
`passFds:[]`, and stdout/stderr limits `1048576` bytes each. Timeout is `300`
seconds for rows 017/018/020, `120` for 002/009/012/014/016/019, and `60` for
every other external row. Each command receives new, distinct mode-`0700`
HOME/TMP/XDG directories; no command reuses another command's environment or
scratch. Each has a distinct nonnull `ProcessFamilyPlan`; no result is passed
until its exact family receipt is quiescent. All 42 probe/command token hashes
are pairwise distinct. TCP, the row-017 UDP bind/inbound need, and browser TCP/Unix are
deliberately separate. Seatbelt's `localhost:*` filter cannot distinguish IPv4
from IPv6, so that bounded family overgrant is explicit; unused UDP outbound
and Unix grants are removed. The exact six `CapabilitySet`s and
assignments are:

| Capability ID | Network | Exec roles | Additional read | Additional write | Environment | Rows | Template SHA-256 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `candidate-basic-v1` | `none` | `resolved-python` | none | none | `candidate-base-v1` | 001,003-008,010-011,013-016,019,021-025,027-030,032-037 | `41771d1db1840ca599237f1c51a7509a851da1f5fa42dfe9d0c757ff7f8c4536` |
| `candidate-tcp-loopback-v1` | `tcp-loopback` | `resolved-python` | none | none | `candidate-base-v1` | 002,009,012 | `6e0316024b183533c6f9c26a22fd50708ca035ae2b942b9fa640f36311a3bf0d` |
| `candidate-udp-bind-v1` | `udp-bind-inbound` | `resolved-python` | none | none | `candidate-base-v1` | 017 | `48ad3cf87424ba769e916c72fd91b50613ee2e52ad592041a6aae2190f92df5f` |
| `candidate-write-run-status-v1` | `none` | `resolved-python` | none | `candidate-run-status` | `candidate-base-v1` | 026 | `f36e1f26816d91f0ab5576676e56bfc4154b62ae99531557989fe061be75ebaf` |
| `candidate-tcp-loopback-ux1b-v1` | `tcp-loopback` | `resolved-python` | none | `candidate-ux1b` | `candidate-base-v1` | 020 | `f431e478dd63242288683e52631180470fa35917e7b852c260305d342447e42f` |
| `candidate-browser-tcp-unix-ux1b-v1` | `tcp-unix-loopback` | `resolved-python,playwright-node,headless-shell` | `headless-shell-runtime` | `candidate-ux1b,candidate-ui` | `candidate-browser-v1` | 018 | `46b855438f648fbf1f16bca8332617028eec3e09e4f900e69f32e77cc76d3320` |

Comma-separated exec cells denote exact arrays in displayed order. Every
`readRoles` array begins exactly
`candidate-root,private-home,private-tmp,private-cache,private-config,
private-data,live-venv,base-python-runtime,system-runtime` and appends the
displayed additional read roles; `none` appends nothing. `system-runtime` is
exactly the existing frozen isolation set `/System`, `/usr`,
`/Library/Apple/System/Library`, `/Library/Fonts`, `/private/etc`,
`/private/var/db/timezone`, and the existing literal files `/`, `/dev/null`,
`/dev/urandom`, `/dev/random`, `/dev/dtracehelper`. `headless-shell-runtime` is only the reviewed
candidate runtime root at digest
`51a3c1288a5bb4e361033b76e8a7c4c2668249584969b28711c5bba36cbca30c`;
the `ms-playwright` cache root,
revision wrapper/markers, Chrome-for-Testing app bytes, revision siblings, and
every other cache leaf remain unreadable. Metadata-only traversal and the
`chromium.executable_path` existence check remain possible under `allow
default`.

Every
`writeRoles` array begins exactly
`private-home,private-tmp,private-cache,private-config,private-data,dev-null`
and appends the displayed additional roles in order; `none` appends nothing.
Network and environment cells are exact closed literals.

`candidate-run-status` is exactly
`<CANDIDATE_ROOT>/reports/run_status`; `candidate-ux1b` is exactly
`<CANDIDATE_ROOT>/.claude/ui_snapshots/ux1b`; and `candidate-ui` is exactly
`<CANDIDATE_ROOT>/ui`. The coordinator precreates or authenticates those bound
directories as part of the baseline manifest. No profile grants a live
workspace write.

`candidate-base-v1` contains exactly the closed capture environment keys above
except that `PYTHONPATH=<CANDIDATE_ROOT>`, HOME/TMP/XDG are the row's fresh
mode-`0700` directories, each a distinct direct child of the one candidate-
regression session rather than of `RuntimeReceipt.tempRootParent`, and both
`PLAYWRIGHT_*` keys are absent. `candidate-browser-v1`
adds only
`PLAYWRIGHT_BROWSERS_PATH=/Users/ken/Library/Caches/ms-playwright` and
`PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`. Live-workspace source reads are denied;
the only live-workspace read subtree is the authenticated `.venv`, while code,
tests, fixtures, and all five overlays are read from the candidate root.
`PYTHONHOME`, credential keys, proxy variables, inherited keys, and shared
per-command state are absent. The actual spawn map additionally contains only
the one fresh raw process-family token described above; the serialized
environment does not. Exact POST-017/020 synchronous child builders may drop
that key only under the same-PGID/no-session-change exception above.

The six template hashes above are SHA-256 over canonical
`{"id":ID,"ruleIds":ARRAY}` bytes. `ARRAY` is the exact concatenation, in
renderer-slot order, of: `HEAD`, the capability's `EXEC`, `NETWORK_DENY`, the
capability's `NETWORK_ALLOW`, `WRITE_BASE`, the capability's
`WORKSPACE_WRITE`, `READ_BASE`, and the capability's `BROWSER_READ`:

```text
HEAD = version-1,allow-default,deny-process-exec,allow-resolved-venv-python
EXEC(browser) = allow-playwright-node-exec,allow-headless-shell-exec
EXEC(other) = <empty>
NETWORK_DENY = deny-network-outbound,deny-network-bind,deny-network-inbound
NETWORK_ALLOW(none) = <empty>
NETWORK_ALLOW(tcp-loopback) = allow-loopback-tcp-bind,allow-loopback-tcp-inbound,allow-loopback-tcp-outbound
NETWORK_ALLOW(udp-bind-inbound) = allow-loopback-udp-bind,allow-loopback-udp-inbound
NETWORK_ALLOW(tcp-unix-loopback) = allow-loopback-tcp-bind,allow-loopback-tcp-inbound,allow-loopback-tcp-outbound,allow-local-unix-bind,allow-local-unix-inbound
WRITE_BASE = deny-file-write,allow-private-home,allow-private-tmp,allow-private-xdg-cache,allow-private-xdg-config,allow-private-xdg-data
WORKSPACE_WRITE(basic/tcp/udp) = <empty>
WORKSPACE_WRITE(run-status) = allow-candidate-run-status-write
WORKSPACE_WRITE(ux1b) = allow-candidate-ux1b-write
WORKSPACE_WRITE(browser) = allow-candidate-ux1b-write,allow-candidate-ui-write
READ_BASE = allow-dev-null-write,deny-global-read-except,deny-live-workspace-data-except-venv,allow-candidate-read,allow-private-environment-read,allow-live-venv-read,allow-base-python-runtime-read,allow-system-runtime-read
BROWSER_READ(browser) = allow-headless-shell-runtime-read
BROWSER_READ(other) = <empty>
```

TCP allowances cover ephemeral TCP for both loopback families only. UDP permits
only bind/inbound on Seatbelt's indivisible `localhost:*` family filter; UDP
outbound remains denied. Local Unix permits bind/inbound only and is present
only for the browser profile; `socketpair()` needs no exception and remains
available under the default policy. DNS and non-loopback endpoints remain
denied. Unknown, reordered, duplicated, or wrong-slot rules fail.

The canonical Seatbelt renderer emits UTF-8 LF-separated rules with no trailing
newline and Scheme-escapes every descriptor-derived literal. Its exact slot
order is; angle-bracket tokens are named values from the authenticated
execution/workspace records, not unresolved text or operator input:

```text
(version 1)
(allow default)
(deny process-exec)
(allow process-exec (literal <VENV_LAUNCHER>))
(allow process-exec (literal <RESOLVED_VENV_PYTHON>))
<EXEC_ALLOW_RULES>
(deny network-outbound)
(deny network-bind)
(deny network-inbound)
<NETWORK_ALLOW_RULES>
(deny file-write*)
(allow file-write* (subpath <PRIVATE_HOME>))
(allow file-write* (subpath <PRIVATE_TMP>))
(allow file-write* (subpath <PRIVATE_CACHE>))
(allow file-write* (subpath <PRIVATE_CONFIG>))
(allow file-write* (subpath <PRIVATE_DATA>))
<WORKSPACE_WRITE_RULE>
(allow file-write-data (literal "/dev/null"))
(deny file-read-data (require-not (require-any <GLOBAL_READ_FILTERS>)))
(deny file-read-data (require-all (subpath <LIVE_WORKSPACE>) (require-not (subpath <LIVE_VENV>))))
(allow file-read* (subpath <CANDIDATE_ROOT>))
(allow file-read* (subpath <PRIVATE_HOME>))
(allow file-read* (subpath <PRIVATE_TMP>))
(allow file-read* (subpath <PRIVATE_CACHE>))
(allow file-read* (subpath <PRIVATE_CONFIG>))
(allow file-read* (subpath <PRIVATE_DATA>))
(allow file-read* (subpath <LIVE_VENV>))
(allow file-read* (subpath <BASE_PYTHON_RUNTIME>))
<SYSTEM_RUNTIME_READ_RULES>
<HEADLESS_SHELL_RUNTIME_READ_RULE>
```

`GLOBAL_READ_FILTERS` is one whitespace-separated, parenthesis-balanced filter
list in exactly `readRoles` order: subpaths for candidate root, the five private
environment roots, live venv, and base-Python runtime; then subpaths for the six
system runtime roots in the displayed order; then literals for the five system
runtime files in the displayed order; and, only for the browser profile, the authenticated headless-shell runtime
subpath. The explicit allow rules following
the two denies expand over those same paths and in that same order. A directory
uses `subpath`; `/` and the other four system files use `literal`. Thus all
other file content—including the live source tree outside `.venv`, the real
`~/.ssh`, other repositories, the Playwright cache root, and browser siblings—
is denied even though metadata traversal required by the runtime remains at
the default policy.

Empty slots emit zero bytes and no blank line. The logical
`allow-resolved-venv-python` ID expands to both displayed launcher and resolved
target rules. Browser exec expands to one literal rule each for Node and the
one authenticated headless-shell process leaf. `/bin/ps` is deliberately not
allowed inside Seatbelt because Darwin rejects that setuid execution; only the
outer coordinator invokes it. Loopback expands
according to the capability and preserves the following global slot order:

```text
(allow network-bind (local tcp "localhost:*"))
(allow network-inbound (local tcp "localhost:*"))
(allow network-outbound (remote tcp "localhost:*"))
(allow network-bind (local udp "localhost:*"))
(allow network-inbound (local udp "localhost:*"))
(allow network-bind (local unix))
(allow network-inbound (local unix))
```

Each capability emits only its named TCP, UDP, and/or Unix subset from that
displayed order. The workspace-write slot is empty or emits the assigned exact
subpath rules in write-role order for run-status, ux1b, then ui. The rendered
bytes hash must equal each execution's `seatbeltProfileSha256`; a real Darwin
calibration proves the profile before any candidate command. Each row launches
exactly
`["/usr/bin/sandbox-exec","-p",RENDERED_PROFILE,
*CommandRecord.execution.argv]` with `close_fds:true`. The first failure stops
launches and records exact trailing `not_run` rows. No failed or incomplete
candidate report can enter the sealed namespace.

Before any candidate command, the coordinator first resolves the public
sealed/candidate/packet prefix. An exact sealed prefix takes the publication-
only reconciliation path and never reopens or depends on a private session. If
sealed is absent, it descriptor-enumerates the direct children of
`RuntimeReceipt.tempRootParent` before creating anything. Every direct-child
name beginning `.ux1b-candidate-session.` is classified. Such an entry is a
valid final name only when its whole name matches
`.ux1b-candidate-session.<32-lowercase-hex>`. It is schema-valid and owned only
when descriptor inspection proves a direct-child, current-UID,
mode-`0700`, non-symlink directory on the temp-parent device with a canonical
mode-`0600`, one-link direct-child marker whose nonce equals the name and whose
root/ID-format/UID fields validate under this plan. This global classification
does not compare valid stored `batchId` or `themeRunId` to the scanner's current
invocation: a structurally valid owned session from any other `B/T` is still an
orphan gate. Such an entry blocks all new candidate execution, emits only
`candidate_nested_quiescence_unverified`, and exits `9`. A prefixed name with a
malformed suffix, or an exact-name entry with
the wrong type/owner/mode/device, missing or invalid marker, or unsafe traversal
is collision `4`: this workflow and the
runbook below grant no deletion, rename, adoption, or retry authority for it;
ownership resolution requires a separately reviewed procedure.

The workflow never deletes, adopts, or reuses a valid orphan. The only removal
runbook authorized by this plan is: a trusted Quant Radar maintainer stops
lifecycle commands, performs a full host reboot so every live process is
terminated and every zombie reaped, revalidates the exact owned directory and
canonical marker above, then uses same-device, no-follow OS administration
outside this CLI to remove that entry and verifies the authenticated temp
parent has no matching child. A logout, process-name scan, ownerPid lookup, or
best-effort kill is not sufficient because the raw token is intentionally
unavailable. The maintainer records operator, reboot, validated marker, and
removal time in an external operations log; that log grants no lifecycle
authority and is never consumed by the verifier. No in-band clear/adopt command
exists. Because no consumptive attempt or sealed authority exists at this
point, completed runbook removal leaves the same B/T eligible for a later fresh
run. This
durable directory gate replaces any need to persist or later recover a raw
process token.

With that scan empty, the coordinator creates a fresh mode-`0700` staging
directory named `.tmp.quant-radar-ux1b-session.<32-lowercase-hex>` using a
direct-child no-replace operation under the retained temp-parent FD. It writes,
fsyncs, reopens, and authenticates the canonical `CandidateSessionMarker` as
the mode-`0600`, owned, one-link regular direct child
`.quant-radar-candidate-session-owner.json`, then fsyncs staging and the temp
parent. Before any spawn it commits that complete directory to the final name
`.ux1b-candidate-session.<same-32-lowercase-hex>` with
`renameatx_np(...,RENAME_EXCL)`, fsyncs the temp parent, and reopens the same
directory inode and marker. Rename is the session-gate linearization point;
post-rename confirmation uncertainty exits `6`, and no process starts without
the confirmed final reopen. A crash before rename can leave only an ignored,
non-authoritative staging directory and no process; a crash after rename leaves
one schema-valid blocking gate, never a protocol-created malformed final name.
The coordinator then probes every one of the six distinct
profiles in a fresh probe process and fresh private environment. The candidate
root, every per-command private root, and one denied-read canary leaf are
mutually disjoint direct children of that session; only the individually
assigned directory subpaths enter profiles. The canary is one mode-`0600`,
owned, one-link regular file with canonical bytes
`quant-radar-capability-denied\n`, outside the candidate and every private
environment root. `probeCanary.artifact.sha256` and `contentSha256` are both
`0a1bf2c4c01bf5eda94c66c42390a243d6a078658adab144a89fcd274132357c`,
size is `30`, mode/uid/nlink are `0600/<current uid>/1`, and its normalized
absolute path is one regular grandchild of the authenticated temp parent,
disjoint from every read/write role. All six probe argvs bind that same absolute path.
The coordinator same-inode reopens it after every probe, then content-CAS
unlinks it, fsyncs the session parent, proves absence, and records both canary booleans
true before running the 37 command rows.

The probe is not a CLI subcommand. `PROBE_BOOTSTRAP` is exactly the 85 UTF-8
bytes (no newline)
`from scripts.ui_ux_theme_handoff import _run_capability_probe;_run_capability_probe()`
at SHA `2cc4512ad0cde91af302b0ce378065200c542abb9dcb2ab197d9f3266dbd66dc`.
`probeSourceSha256` equals that constant; `probeModuleSha256` equals the
candidate-manifest SHA for `scripts/ui_ux_theme_handoff.py`. The imported
private function strictly parses only `sys.argv` for this inline bootstrap; it
is absent from argparse/help, and a direct production CLI token
`probe-capability` exits `2`.
The probe argv is exactly
`[VENV_LAUNCHER,"-B","-c",PROBE_BOOTSTRAP,"--",
"--capability-id",ID,"--process-token-sha",PROCESS_TOKEN_SHA,
"--candidate-root",CANDIDATE_ROOT,"--live-source",
LIVE_MAKEFILE,"--denied-read-canary",CANARY,"--real-ssh-dir",
"/Users/ken/.ssh","--playwright-cache-root",
"/Users/ken/Library/Caches/ms-playwright","--api-browser-executable",
AUTHENTICATED_CHROMIUM_APP,"--headless-shell-executable",
AUTHENTICATED_HEADLESS_SHELL]`; its cwd is candidate root, environment and profile are
the bound capability's, stdin is `devnull`, timeout is `120` seconds (`180` for
browser), stream limits are `1048576`, process group is fresh, and
`passFds:[]`. Each argv element remains under the global 1024-byte bound. The
module bytes are already part of the authenticated candidate source projection.
Stdout must be one bounded canonical assertion document and stderr empty; the
coordinator—not the probe—constructs the final `RunnerReceipt`, verifies the
unique process-family marker/PGID quiescence with authenticated `/bin/ps`, and
hashes it. The stdout document is exactly
`{schemaVersion,capabilityId,positive,negative,browser}`; those five values must
byte-reencode to the receipt's corresponding fields and stdout hash, so parsed
assertions cannot diverge from process evidence.

Every `positive` array starts with these IDs in this exact order, each expecting
`succeeded`:

```text
venv-launcher-identity
venv-prefix-identity
venv-package-imports
candidate-source-read
private-environment-read-write
base-system-runtime-read
resolved-python-child-exec
process-family-token-binding
```

They prove the launcher spelling and prefix, load FastAPI/Streamlit/Playwright
from the authenticated live `.venv`, read the candidate copy of `Makefile`,
create/read/remove one canary in each of the five private roots, read the bound
base/system runtime, and run the exact venv launcher as a child with return code
zero. The final common assertion validates the initial probe's raw token format
and hash against its `TokenProcessFamilyPlan` without emitting it; it does not
claim that every authenticated descendant preserves the environment key. Each capability
then appends only the following positive IDs, in displayed order:

| Capability | Positive additions |
| --- | --- |
| `candidate-basic-v1` | none |
| `candidate-tcp-loopback-v1` | `tcp-ipv4-roundtrip`, `tcp-ipv6-roundtrip` |
| `candidate-udp-bind-v1` | `udp-ipv4-bind-recv-timeout`, `unix-socketpair-default` |
| `candidate-write-run-status-v1` | `candidate-run-status-write-read-remove` |
| `candidate-tcp-loopback-ux1b-v1` | `tcp-ipv4-roundtrip`, `tcp-ipv6-roundtrip`, `candidate-ux1b-write-read-remove` |
| `candidate-browser-tcp-unix-ux1b-v1` | `tcp-ipv4-roundtrip`, `tcp-ipv6-roundtrip`, `unix-path-bind-listen-close`, `candidate-ux1b-write-read-remove`, `candidate-ui-write-read-remove`, `playwright-node-exec`, `chromium-default-launch-page-close` |

Each TCP roundtrip creates both endpoints inside the probe and verifies payload
equality; IPv6 may not be silently skipped. The UDP probe performs the exact
row-017 IPv4 bind plus bounded empty receive, while `socketpair()` proves the
default operation needs no Unix grant. The browser Unix probe performs pathname
bind/listen/close/unlink in private TMP; actual Chromium launch exercises its
ProcessSingleton use. Each successful candidate
write uses a capability-ID-namespaced absent leaf, exact bytes, reopen, unlink,
and parent fsync. Node runs the authenticated driver with `--version` and
requires return code zero, bounded exact output, and the preflight hash. The
outer coordinator's exact family receipt separately proves authenticated
`/bin/ps` observation. The Chromium operation first
requires Playwright's API path to equal the authenticated app, then calls
`chromium.launch(headless=True)` with no `executable_path`, so it follows the
same default headless-shell path as POST-018. It creates a blank page, checks
the exact runtime version, closes page/context/browser, and proves the inherited
family is quiescent. The candidate browser profile's sole browser process-exec
leaf is the authenticated headless shell; the app itself is explicitly denied
execution. A missing browser, path-only check, caught
exception, early return, or Playwright test's existing optional skip is a probe
failure. The browser receipt is nonnull only for this capability and binds all
those facts; for every other capability, `browser` is exactly null.

Every `negative` array starts with these IDs in this exact order, each expecting
`denied`:

```text
unknown-true-exec-denied
nested-sandbox-exec-denied
ps-exec-denied
live-source-read-denied
outside-allowlist-read-denied
real-ssh-list-denied
playwright-cache-list-denied
live-source-write-open-denied
candidate-root-write-denied
live-venv-pyvenv-write-open-denied
headless-shell-write-open-denied
external-tcp-denied
external-udp-denied
dns-resolution-denied
```

The existing-leaf write-open probes target the authenticated live `Makefile`,
venv `pyvenv.cfg`, and headless-shell leaf. Each uses exactly
`O_WRONLY|O_NOFOLLOW|O_CLOEXEC`, contains none of
`O_RDWR|O_CREAT|O_TRUNC|O_APPEND`, and never writes even if unexpectedly
admitted. Because POSIX `O_RDONLY` is zero, a syscall recorder proves the
access-mode mask is exactly `O_WRONLY`, as well as the complete flag set. An
admitted descriptor is retained while its `fstat` identity is matched to the
preauthenticated target and the outer coordinator's separate retained read
authority reauthenticates the name identity and bytes; it is then closed before
the assertion returns `failed`. The
candidate-root write uses one absent direct-child canary outside every granted
subpath.
The outside-read target is `probeCanary`; the SSH and Playwright-cache probes
only attempt directory enumeration and never emit names or bytes. External TCP
uses TEST-NET-3 `203.0.113.1:9`; external UDP uses `1.1.1.1:53`; DNS resolves
`example.com` and is paired with that denied DNS-packet operation. File, exec,
bind/connect, and send denials accept only `PermissionError|OSError` carrying
`EPERM|EACCES`. DNS additionally requires no address result and one of
`EAI_AGAIN|EAI_FAIL|EAI_NONAME`; DNS alone cannot satisfy the paired external
UDP assertion. Each capability then appends these exact negative IDs:

| Capability | Negative additions |
| --- | --- |
| `candidate-basic-v1` | `tcp-ipv4-bind-denied`, `tcp-ipv6-bind-denied`, `udp-ipv4-bind-denied`, `udp-ipv6-bind-denied`, `unix-bind-denied`, `candidate-run-status-write-denied`, `candidate-ux1b-write-denied`, `candidate-ui-write-denied`, `playwright-node-exec-denied`, `headless-shell-exec-denied` |
| `candidate-tcp-loopback-v1` | `udp-ipv4-bind-denied`, `udp-ipv6-bind-denied`, `unix-bind-denied`, `candidate-run-status-write-denied`, `candidate-ux1b-write-denied`, `candidate-ui-write-denied`, `playwright-node-exec-denied`, `headless-shell-exec-denied` |
| `candidate-udp-bind-v1` | `tcp-ipv4-bind-denied`, `tcp-ipv6-bind-denied`, `unix-bind-denied`, `udp-loopback-outbound-denied`, `candidate-run-status-write-denied`, `candidate-ux1b-write-denied`, `candidate-ui-write-denied`, `playwright-node-exec-denied`, `headless-shell-exec-denied` |
| `candidate-write-run-status-v1` | `tcp-ipv4-bind-denied`, `tcp-ipv6-bind-denied`, `udp-ipv4-bind-denied`, `udp-ipv6-bind-denied`, `unix-bind-denied`, `candidate-ux1b-write-denied`, `candidate-ui-write-denied`, `playwright-node-exec-denied`, `headless-shell-exec-denied` |
| `candidate-tcp-loopback-ux1b-v1` | `udp-ipv4-bind-denied`, `udp-ipv6-bind-denied`, `unix-bind-denied`, `candidate-run-status-write-denied`, `candidate-ui-write-denied`, `playwright-node-exec-denied`, `headless-shell-exec-denied` |
| `candidate-browser-tcp-unix-ux1b-v1` | `udp-ipv4-bind-denied`, `udp-ipv6-bind-denied`, `candidate-run-status-write-denied`, `chromium-app-exec-denied` |

Every absent-leaf denied write probe uses a capability-ID-namespaced absent
leaf and exactly `O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC` with mode
`0600`; a syscall recorder proves that full flag/mode tuple. It never writes
content. If unexpectedly admitted, it closes and descriptor/name-CAS removes
only the exact created inode, fsyncs the parent, nofollow-verifies absence, and
returns `failed`. An identity swap deletes no inode; unlink failure,
parent-fsync failure, or inability to verify absence keeps the probe failed,
and any surviving or ambiguous entry is additionally caught by the candidate
after-manifest/extra-entry gate. Denied
Unix probes use their separately specified socket operation and no file-open
substitute. Non-browser
headless-shell and browser app exec probes use only `--version`, are bounded,
and are terminated if unexpectedly started. Across the six receipts there are
exactly 63 positive and 131 negative outcomes (194 total). Every assertion ID
is unique in its array; unknown, reordered,
duplicated, missing, wrong-outcome, wrong-error, or false `passed` values fail.
All six rendered profiles are therefore exercised positively and negatively on
real Darwin Seatbelt before the 37-row suite; a hash-only calibration or silent
return is insufficient.

The `ProbeOutcome` operation form is closed. Child-form outcomes are exactly
`resolved-python-child-exec`, `unknown-true-exec-denied`,
`nested-sandbox-exec-denied`, `ps-exec-denied`,
`playwright-node-exec`, `playwright-node-exec-denied`,
`headless-shell-exec-denied`, and `chromium-app-exec-denied`; their successful
return/signal pair is `0/null`. Every other assertion ID is in-process and uses
`null/null`. In particular `chromium-default-launch-page-close` is one
in-process Playwright API assertion even though the library creates the
separately controlled browser family. Unknown IDs or changing an ID's form
fails schema validation.

After canary deletion, all 37 rows run, the after-manifest and protected
closures are captured, and only then are `test-report.json` and the bundle
manifest staged/fsynced inside the private sealed tree. Neither leaf is a public
commit. Publication then follows the exact sealed-directory, candidate,
packet sequence and reconciliation matrix above. The current owner may remove
its session only while retaining and reauthenticating the exact temp-parent,
session, and marker descriptors and only when no external process was ever
spawned or every spawned group has an exact quiescent `ProcessFamilyReceipt`
ending in empty `post_reap`. Complete tree/session/marker reauthentication
finishes before cleanup's linearization point and, unlike the global orphan
scan, requires the marker's `batchId` and `themeRunId` to equal this original
owner's invocation exactly. The owner creates no directory;
it reserves an absent tombstone name
`.tmp.quant-radar-ux1b-cleanup.<32-lowercase-hex>`, then atomically renames the
whole final session directory to that tombstone with
`renameatx_np(...,RENAME_EXCL)`. The retained temp-parent FD is immediately
fsynced and must reopen the tombstone as the same session inode with the same
marker while proving the final name absent.

A lost rename response or post-rename parent-fsync/reopen failure re-enumerates
only through the retained parent FD. Its closed state/output table is:

| Reopened namespace state | Further writes/deletes | Diagnostic / exit | Future authority |
| --- | --- | --- | --- |
| final is the retained same inode; tombstone absent | none | `candidate_nested_quiescence_unverified` / `9` | final remains the blocking orphan gate; only the full-reboot runbook applies |
| final absent; tombstone is the retained same inode; parent durability or reopen is uncertain | none | `candidate_cleanup_completion_uncertain` / `6` | fresh public/session scan may proceed but must ignore, never adopt/delete, the tombstone |
| both names present, both absent before confirmed commit, either name is a different inode/type/owner/device, or enumeration/traversal is unsafe | none | `candidate_cleanup_namespace_collision` / `4` | no retry, rename, adoption, or removal authority; separately reviewed ownership resolution required |
| final absent; tombstone is the retained same inode; parent fsync and reopen both confirmed | only the exact descriptor deletion below | none yet; cleanup continues | only this uninterrupted original owner holds deletion authority |

No state is inferred from the rename syscall result alone. In particular, no
code claims the final marker/name still exists after either exact post-state,
and every collision row is terminal for this invocation even though all
process-family receipts are complete.

Only after the exact post-state and parent fsync are confirmed may the original
owner descriptor-delete tombstone contents: the venv bridge is unlinked as a
symlink leaf, every entry must have the expected owner/type/device, the marker
is unlinked last, then tombstone `rmdir` and parent fsync complete. Any later
I/O uncertainty exits `6` and may leave only that ignored tombstone; all
process families were already proven closed. Fresh workflows never delete or
adopt staging/cleanup tombstones. An ordinary probe/row/manifest failure
satisfying the receipt condition completes this cleanup and publishes no
sealed path. The uninterrupted success owner may begin it only after the
sealed directory is durable; candidate/packet publication never depends on
tombstone deletion.

For an ordinary probe/row/manifest failure, any missing family receipt,
persistent filtered row, observer/selector/stream failure, signal syscall race, cleanup
reauthentication failure, or any pre-rename cleanup error preserves the exact
final session without unlinking any child. It publishes no sealed path, emits only
`candidate_nested_quiescence_unverified`, and exits `9`. In particular no
ordinary failure without all receipts begins scratch, canary, marker, or
session deletion. Post-rename uncertainty instead follows the exact exit-`6`
state above and never falsely claims a durable gate remains.

SIGINT/SIGTERM follows the same per-family signal/no-signal controller. If all
launched families obtain exact receipts and the authorized cleanup completes,
it CAS-cleans owned scratch/canary and the session, publishes no sealed path,
and exits `130`. If any launched family lacks a receipt—including persistent
filtered rows, observer failure, or a signal race—or pre-rename cleanup cannot
begin, it preserves the final gate, publishes nothing, emits only
`candidate_nested_quiescence_unverified`, and exits `9`; post-rename cleanup
uncertainty exits `6`. Interruption
or uncertainty after any public step stops immediately with `6` and leaves
only an exact reconcilable public prefix plus possible non-authoritative
private objects.

SIGKILL may likewise leave the mode-`0700` session tree—including its
mode-`0600` owner marker/canary—a pre-rename session staging directory, a
post-quiescence cleanup tombstone, one or more owned precommit
`.tmp.sealed.*`/regular-publisher `.tmp.*` objects, and/or an exact public
prefix. A fresh run with no sealed directory is blocked by any matching
final session entry as specified above; staging never preceded a spawn and a
cleanup tombstone followed complete receipts, so neither private prefix blocks
or grants a run. The workflow does not reuse either nonce. A fresh run
with an exact sealed prefix ignores every private session/temp object and
applies only the public prefix matrix, because sealed publication was permitted
only after all candidate families were proven quiescent. No fresh run deletes,
reopens as evidence, or adopts a private object; regular precommit temps are
also never authority.

The live attempt's `PostApplyPlan.commands` is exactly these four internal
records in order:

| ID | Exact no-process/no-write action |
| --- | --- |
| `POST-038-COMPILE-NOWRITE` | `compile()` every changed Python byte sequence with no cache output |
| `POST-039-AST310` | `ast.parse(...,feature_version=(3,10))` every changed Python file |
| `POST-040-PROTECTED` | source/classification/protected-hash/fail-soft/selector/zero-`segmented_control` assertions |
| `POST-041-SCOPE-NOWRITE` | exact five live postimages and no unapproved workspace change |

Each is `{kind:"internal",execution:null}`. The apply owner runs them in-process
over retained descriptors; no executable, network, environment, stdout/stderr,
or workspace-write capability exists. The first failure yields exact trailing
`not_run`, a failed report, and rollback-only state. Reconciliation never reruns
either the sealed candidate suite or this live plan.

## Implementation checklist

### Task 0 — freeze and authorize the replacement package

- [ ] Finalize this file without an accepted-status self-edit.
- [ ] Compute its SHA/size; generate the sibling ledger with that exact ref.
- [ ] Validate 10000-bps forward/backward structural trace coverage, no gaps or
  orphans, and all imported section/upstream hashes.
- [ ] Freeze both files and obtain independent authority, lifecycle, and
  publication reviews on their exact SHA values.
- [ ] If and only if no High/Medium remains, append one canonical V2 stanza and
  reopen it; otherwise do not implement.

**Gate:** immutable reviewed package and one unambiguous V2 authority.

### Task 1 — fail-first bootstrap and verifier tests

- [ ] Confirm verifier/test paths absent; create only those two new files.
- [ ] Add fail-first tests for every public/private grammar and lifecycle
  transition before wiring existing files.
- [ ] Add authorization marker, tar member, runtime allowlist, descriptor,
  publication, FD, review packet, source, normalization, and rollback attacks.
- [ ] Add table-driven renderer/hash/read-boundary tests and all six real
  capability-probe positive/negative/browser assertion contracts. Cover both
  exact `HunkAnchor` longest-prefix/suffix algorithms and golden vectors,
  `proposedContractSha256`, and rejection of the removed
  `diagnosticPorcelainSha256` key. Use the fixed inline
  85-byte probe bootstrap, fixed 103-byte POST-018 bootstrap and exact 55/55
  candidate-safe subset, candidate-only headless-shell authority, and
  marker-plus-PGID process-family closure. Cover kqueue/overflow/timeout
  precedence, natural family settling, zombie-only no-signal cleanup, TERM/KILL
  escalation, exact receipt projections, and the durable candidate-session
  orphan gate. A syscall recorder must prove family-cleanup calls are only
  `killpg(original_pgid,SIGTERM)` followed optionally by
  `killpg(original_pgid,SIGKILL)`. A separately tagged injected observer
  timeout/overflow arm permits only one
  `killpg(observer_pid,SIGKILL)` followed by its bounded direct-child wait/
  pipe closure. Across both arms `os.kill` is never called, the observer never
  targets the runner, and neither arm targets a marker PID or detached marker
  PGID. Cover observer success, timeout, overflow, `ESRCH`, Darwin owned-zombie
  `EPERM` followed by exact bounded wait/reap, rejected unproved `EPERM`, and
  failed bounded reap. A real detached descendant must retain both runner pipe
  writers past leader exit; the selector path must durably retain the manual
  gate, close its local read FDs, return `9`, and release both leases within the
  total bound without waiting for descendant EOF. A separate real child writes
  stdout and stderr continuously faster than the reader and ignores TERM; the
  exact per-role quantum/rotation must still service deadline, overflow,
  kqueue, observer and interrupt state, drive TERM then KILL, obtain the exact
  overflow receipt, and return within the total bound. A quiet child and a
  child that exits immediately after its last output must exercise empty,
  `EAGAIN`-only, EOF-only, and zero-active-role selector turns; a recorder
  proves the mandatory end-of-turn zero-time kqueue service and `NOTE_EXIT`
  recognition within the first at-most-50-ms wait return. The capability-probe
  syscall recorder also proves the exact existing-leaf and absent-leaf writable
  open flag/mode tuples. On owned scratch replicas, fault injection forces each
  negative write open to succeed: existing-leaf cases prove zero write-family
  syscalls, unchanged descriptor/name identity and bytes, close, and a failed
  assertion; absent-leaf cases prove zero write-family syscalls, failed
  assertion, exact-created-inode CAS unlink, parent fsync, and verified absence.
  Identity swap, unlink failure, parent-fsync failure, or inability to verify
  absence must perform no foreign-inode deletion and must keep the assertion
  failed; any surviving or ambiguous entry must additionally fail the
  after-manifest/extra-entry gate. Also cover a live original-PGID row, zombie
  marker-false leader, that leader plus a marker-false same-
  PGID zombie non-leader with both EOF fields true, live detached marker-only
  row, vanished original group with persistent marker row, and every resulting
  exact zero/one/two-call trace. The zombie-non-leader case must exercise both
  no-signal and post-TERM passive settling without an extra signal. Candidate
  fixtures include same-invocation and foreign-but-valid `B/T` orphans returning
  `9`, true malformed collisions returning `4`, and every cleanup-table state
  with its exact diagnostic/exit and zero-deletion oracle. Keep the
  ordinary unsandboxed 57/57 snapshot-matrix gate
  separate and mandatory.
- [ ] Run all tests against owned scratch workspaces; no real lifecycle output
  or existing source changes occur.

**Gate:** new tests fail only for missing behavior; inherited suites stay green.

### Task 2 — bootstrap Tier 0 and implement the verifier

- [ ] Implement lock bootstrap, Tier 0 records/bundle, canonical schemas,
  descriptor helpers, regular/consumptive publishers, runtime/source checks,
  and exact diagnostics.
- [ ] Implement the one shared kqueue/process-observer controller,
  `ExitWatchResult` state machine, original-runner-PGID family signal policy,
  disjoint direct-observer-PGID failure cleanup, bounded streams, and
  candidate-session marker/orphan gate before any lifecycle coordinator may
  spawn.
- [ ] Run `bootstrap`, reopen its complete fixed path set, and stop on collision.
- [ ] Implement Task 9 coordinator/reconciler and lock-free fresh child.
- [ ] Implement packets/publisher, root candidate/publication, theme batch,
  apply/reconcile, and Task 4/5 coordinators/closures.

**Gate:** all verifier unit/fault/concurrency tests pass; frozen stack unchanged.

### Task 3 — wire Make orchestration

- [ ] Record exact Make/recovery/journal preimages and anchors from Tier 0.
- [ ] Add targets/variables above and exact nonzero propagation.
- [ ] Replace direct Task 9 runner recipe with one coordinator command.
- [ ] Wrap theme-state/posttheme capture in their lock-owning coordinators.
- [ ] Add verifier tests to `ui-ux1b-recovery-tests`.

**Gate:** static and subprocess Make tests prove exact order and failure paths.

### Task 4 — pre-capture closure

- [ ] Run verifier suite, all current 310 recovery checks, repository tests,
  artifact/API fail-soft regressions, UX-0/UX-1A safety, component, contract,
  navigation, and legacy gates.
- [ ] Run `.venv/bin/python -B scripts/test_ui_ux_snapshot_matrix.py` outside
  lifecycle Seatbelt and require 57/57; this read-only developer gate grants no
  lifecycle authority and cannot be replaced by the candidate-safe subset.
- [ ] Run discovery 57/57 and real Chromium smoke 10/10; require 12/12 process
  quiescence and exact frozen stack digests.
- [ ] On real Darwin Seatbelt, dry-run all six capability probes and the exact
  37-row candidate plan against an owned candidate fixture; require equal
  before/after directory/file/symlink manifests, default headless-shell launch
  identical to POST-018, 42 distinct `token_pgid` plans/token digests with
  quiescent PGID-plus-marker unions, and no optional browser skip.
- [ ] Run compile, Python 3.10 AST, tabnanny, dependency, scope, hash, diff, and
  zero-`segmented_control` gates.
- [ ] Compare actual diff to plan and obtain two fresh changed-code reviews;
  fix every blocker.
- [ ] Reopen the Tier 0-created fixed capture lease, bind its exact record in
  preflight, and publish/reopen preflight; preflight never creates the lease.

**Gate:** immutable preflight binds exact code, package, sources, runtime, and
eligible destinations before the one Task 9 attempt.

### Task 5 — execute and close Task 9

- [ ] Run `capture-task9` once through Make; require launch counts 36-stage=1,
  81-stage=1 and terminal passed.
- [ ] Reopen four manifests, 468 after-artifacts, exact 163/73/163/73 leaves,
  full terminal contracts, and process quiescence.
- [ ] Run migration comparator; prepare its exact review packet; pause for the
  externally authored 117-item intake; publish exact accepted bytes.
- [ ] Prepare/verify root candidate, publish root with fresh child, and run a
  new-process pristine consumer verification.

**Gate:** immutable v2 root exists and no parent theme file has changed.

### Task 6 — prepare, review, and apply parent Task 3

- [ ] Choose explicit `B/T`; publish Tier 1 prechange and initialize work copies.
- [ ] Implement semantic theme only in work copies; seal exact 14-leaf bundle;
  run scratch tests and publish candidate/packet.
- [ ] Pause for external five-item code review; exact-copy accepted intake.
- [ ] Verify readiness, then run one `apply-theme-batch`; require applied receipt
  and focused postapply gates. Candidate-suite failure prevents sealing; a live
  internal-postapply failure uses rollback-only reconciliation.

**Gate:** exact five postimages and applied receipt; attempt alone is failure.

### Task 7 — close parent Task 4

- [ ] Run the theme-state coordinator once for `T`; require exact lease/intent/
  checkpoint, 3/3, 15 artifacts, 16 leaves, source/runtime parity, candidate,
  and 12-item packet.
- [ ] Pause for external visual review; publish accepted intake.
- [ ] Publish/reopen state attestation.

**Gate:** attestation consumes the applied receipt and closes Task 4.

### Task 8 — close parent Task 5

- [ ] Run posttheme coordinator once for `T`; require exact lease/intent/
  checkpoint, 81/81, 162 artifacts, 163 leaves, exact projections,
  normalization, candidate, and 81-item packet.
- [ ] Pause for external visual review; publish accepted intake.
- [ ] Publish/reopen final closure.

**Gate:** final closure alone closes Task 5.

### Task 9 — final parent closure

- [ ] Run complete regression/adversarial/scope gates and two independent
  implementation reviews.
- [ ] Re-run `.venv/bin/python -B scripts/test_ui_ux_snapshot_matrix.py`
  outside lifecycle Seatbelt and require 57/57; retain the exact 55/55
  candidate receipt as a separate inner-sandbox obligation.
- [ ] Rehearse exact five-record rollback in owned scratch, including refusal
  on unknown bytes and crash-resumable reverse order.
- [ ] Reconcile documentation/journals/roadmap without mutating evidence.
- [ ] Record a five-axis impact verdict: callers/importers, tests, schema/types,
  Make/config/environment, and docs; none may remain unchecked or
  `NEEDS-REVIEW` at closure.

**Gate:** parent Tasks 6-8 and all local completion gates pass.

## Required verifier tests

| Test ID | Binary obligation |
| --- | --- |
| `TEST-001` | One canonical V2 stanza passes; extra/legacy/future/malformed/unpaired markers fail. |
| `TEST-002` | Unknown/duplicate auth keys, body recoding, plan/ledger/precedence mutation fail. |
| `TEST-003` | Exact nine tar headers/payloads project `0644 -> 0444` and reproduce Task 6 digest. |
| `TEST-004` | Duplicate/link/mode/uid/gid/size/payload tar mutations fail without extraction. |
| `TEST-005` | Tier 0 exact set/schemas include lock/lease and no placeholders; only the fully reopened rollback-terminal chain is complete. |
| `TEST-006` | Concurrent bootstrap has one safe lock creator; crash/lost-response injection at every ordered boundary makes each strict prefix permanently incomplete; lock is never removed or split. |
| `TEST-007` | 0/64/80 inherited and sparse-high FDs produce exact budget or pre-output exit `5`; soft limit restores. |
| `TEST-008` | Parent-held lock permits private child completion while public command exits `7`; wrong nonce/FD/inode/hash fails. |
| `TEST-009` | Real Darwin regular publisher uses exact `O_CREAT|O_EXCL|O_RDWR|O_NOFOLLOW|O_CLOEXEC`/`0600`; `RENAME_EXCL` tests same-inode move, one winner, collision preservation, lost response, and reconciliation. |
| `TEST-010` | Crash injection at every Task 9 boundary keeps each runner launch count `<=1`. |
| `TEST-011` | Active inherited lease prevents reconcile; partial chain revokes after lease release. |
| `TEST-012` | Only complete pretheme checkpoint chain can reconcile terminal passed. |
| `TEST-013` | Existing intent/terminal/direct manifests never launch or grant a runner/root. |
| `TEST-014` | Packet prompt/input/item hashes are deterministic for all four review kinds; theme-batch patch generation, five section boundaries, domain/path binding, the `app.py` golden vector, order/path/content mutations, and whole-patch concatenation are exact. |
| `TEST-015` | Review publisher exact-copies bytes and rejects wrong prompt/input/item/reviewer/finding state. |
| `TEST-016` | Theme-state standalone items reject `changed`; pair items enforce exact changed/hash semantics. |
| `TEST-017` | Sealed batch has exactly 14 leaves, independent one-link inodes, exact five content-equal/device-inode-distinct overlay mappings, and every BatchChange logical live path is distinct from and correctly maps to its physical sealed pre/post artifact path; seven scratch records and two exact protected closures pass. Candidate manifests use one exact mode-0700 absolute `CandidateDirectoryRecord` root plus closed relative directory/file/symlink arrays before/after; one mode-0700 session plus its durable mode-0600 owner marker and mode-0600 canary, six passed capability probes, 55/55 subset receipt, 37/0/0 results, empty extra entries, and private report staging are exact. Session creation proves staging create/marker fsync -> final `RENAME_EXCL` -> parent fsync/same-inode reopen before spawn; a pre-rename crash leaves only ignored staging, while a post-rename loss leaves an exact gate. Cleanup fault injection proves final -> same-inode cleanup-tombstone rename is the sole linearization: exact pre-state returns diagnostic `candidate_nested_quiescence_unverified`/`9`, exact post-state with durability uncertainty returns `candidate_cleanup_completion_uncertain`/`6`, and every both-present/both-absent/different-inode/type/owner/device/unsafe state returns `candidate_cleanup_namespace_collision`/`4`; every error row performs zero deletion, and only the original confirmed owner deletes tombstone contents marker-last. Publication permits only the closed prefixes `none -> sealed -> sealed+candidate -> sealed+candidate+packet`; every step requires its own parent fsync/reopen/lost-response reconciliation and no extra path. Before sealed, both same-invocation and foreign-but-valid `B/T` owned final sessions return `9`; malformed ID/marker or wrong-owner/type/mode/device collision returns `4` and has no removal authority. No in-band clear/adopt command exists, and only fixture removal of a revalidated valid session representing the completed trusted-operator full-host-reboot runbook leaves the same B/T eligible to retry. From sealed-only, a fresh process must produce byte-identical candidate/packet whether the old session is absent, remains final, or is a cleanup tombstone, without opening or adopting any historical private path. |
| `TEST-018` | One R/T lineage owns exactly 24 shared paths; distinct B claims own disjoint two-path sets; two apply processes yield one fresh attempt grant and the loser writes nothing. |
| `TEST-019` | Stage/live mutation before attempt leaves attempt absent; mutation before replace triggers reverse rollback. |
| `TEST-020` | Crash injection covers rollback-intent precommit/postcommit-loss and every forward/reverse `replace_live_exact` boundary: exact `O_CREAT|O_EXCL|O_RDWR|O_NOFOLLOW|O_CLOEXEC`/`0600` temp create, copy/metadata/fsync/rehash, actual expected-live FD/FileRecord reopen/CAS, rename, parent fsync, and desired-live reopen/authentication, plus final restore before terminal and terminal lost response. Sealed desired source path/device/inode are mutated independently and never participate in expected-live same-file checks; success returns the renamed temp's new live `FileRecord` while matching only `DesiredLiveContent`. Any rename-may-have-committed branch stops all writes/exits 6 for a fresh current-snapshot reconciler; only safe reachable prefixes resume. The exact `SafeRegularMode`/`SafeDirectoryMode` bitmasks and 16,777,216-byte live hash cap select safe hashable present-unknown, mode-0777/special-bit/wrong-owner/hardlinked, unreadable/over-limit regular, absent, symlink, directory, and special-file arms plus repeated-lstat drift rejection. All-post plus passed report and absent applied receipt takes only verified-applied; strict one-to-four-post mixture takes rollback. No-unknown intents resume only exact prefixes; original unknown-bearing intents contain at least one unknown plus one postimage and exactly the reverse-ordered post paths; unknown with zero post uses null-intent/no-write; fresh reconcilers preserve the exact union snapshot and never resume unknown-bearing intent. Actor-specific existing terminals are read-only verified. |
| `TEST-021` | Exact six-profile candidate-regression plus internal-postapply command/profile/environment arrays reject unknown executable/env/rule/read/write/network grants. The fixed 85-byte probe bootstrap and 103-byte POST-018 bootstrap/source/module hashes pass while both forbidden public CLI entry tokens exit 2. Exactly 194 real outcomes enforce the closed child/in-process return/signal mapping, venv/import/initial-token identity, all positive operations, OS-denied live/SSH/sentinel/cache/venv/headless writes, denied exec/external network/DNS including sandboxed `ps`, real Node plus outer coordinator `/bin/ps` observation, POST-018-identical default headless-shell launch/page/close/version/quiescence, and app-exec denial. A syscall recorder proves existing-leaf negative writes use exact `O_WRONLY|O_NOFOLLOW|O_CLOEXEC` with access mode `O_WRONLY` and no create/truncate/append, while absent-leaf negatives use exact `O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC`/`0600`. Forced-success scratch probes prove zero write-family syscalls and failed classification; existing leaves remain identity/byte-exact and close, while absent leaves CAS-unlink only the created inode, fsync the parent, and verify absence. Swap/unlink/fsync/absence-verification faults delete no foreign inode and keep the assertion failed; any surviving or ambiguous entry additionally fails the after-manifest/extra-entry gate. The exact 55/55 candidate subset and separate outer 57/57 host gate are both mandatory. Runtime-tree, executable-leaf, raw-token serialization/reuse/exposure, marker boundary/parser mutation, token-drop-plus-detachment, PGID/marker-union observation/digest, correct process-family plan/result projection, exact NOTE_EXIT/ESRCH `ExitWatchResult`, overflow-over-exit precedence, every empty/EAGAIN/EOF/zero-role selector-turn plus deadline zero-time exit check, quiet/last-output exit recognition within the first at-most-50-ms wait return, 25-second natural settlement, zombie-only `failed_no_signal`, successful TERM and TERM-then-KILL, signal-race refusal, EOF-before-reap, inherited SIGCHLD rejection, latched repeated interrupts, persistent-marker exit-9 manual gate, spawn, cleanup, failed/missing/not-run, optional-skip, and premature public mutations block sealing or roll back the live attempt without overwriting unknown bytes. A syscall recorder covers live original-PGID, marker-false zombie leader, that leader plus a marker-false same-PGID zombie non-leader with both EOF fields true, live detached marker-only, and original-group-gone/persistent-marker cases; the zombie-non-leader fixture must select `pre_no_signal|settling_no_signal` or passive post-TERM `settling_term` without an extra signal; family-cleanup traces are only zero calls, `killpg(original_pgid,SIGTERM)`, or that call followed by `killpg(original_pgid,SIGKILL)`; separately injected observer success has zero calls, while observer timeout/overflow cleanup has exactly one `killpg(observer_pid,SIGKILL)` plus bounded direct-child wait/nonblocking-FD closure, including `ESRCH`, owned-zombie `EPERM` accepted only after exact wait/reap, unproved-`EPERM` rejection, and failed-reap cases. Across both tagged arms `os.kill` is never called, target sets are disjoint, and marker PID/detached marker PGID are never targets; observer failure emits no observation sample and retains the owning manual gate. A detached descendant holding both runner pipe writers past leader exit must still cause the main-thread selector to close all local reads, durably retain the manual gate, release both leases, and return `9` within the total deadline without EOF or a thread join. A TERM-ignoring original-group child that continuously saturates both streams proves the exact 65,536-byte read/four-read/262,144-byte per-role quantum and rotating fair order still service overflow, deadlines, kqueue and observers, emit exactly TERM then KILL, obtain the exact overflow receipt, and return within the total bound. Ordinary or interrupted missing-receipt, observer/signal-race, cleanup-reauthentication, and other pre-rename cases retain the final gate, publish nothing, and return `9`; exact post-rename cleanup uncertainty returns `6` with only an ignored same-inode tombstone, mixed namespace collision returns `4` with zero deletion/retry authority, and only complete receipts plus confirmed cleanup remove the final gate. |
| `TEST-022` | Attempt-only evidence cannot close Task 3/start Task 4; applied receipt binds five exact postimages/tests/review. |
| `TEST-023` | Theme-state 3/3 plus 15/16 and posttheme 81/81 plus 162/163 authenticate exact execution/lease/intent/checkpoint chains; duplicate launch is impossible, and each capture owner's/reconciler's explicit `0/6/7/8/9/130` matrix proves active-lease busy, publication uncertainty, partial-intent burn, unknown process closure, cleaned interruption, and complete-checkpoint deterministic forward reconciliation. |
| `TEST-024` | Imported sidecar replay normalizes 81/81, accepts 71 identical PNGs, rejects every unlisted volatility, and proves `changedIdsSha256` from the lexicographically sorted unique changed-ID set including the exact two-ID golden vector and order/flag/ID/domain mutations. |
| `TEST-025` | Source comparison contains exact typed change records for three mirror plus two supplemental paths. |
| `TEST-026` | Make exposes only coordinator capture paths and propagates every nonzero exit. |
| `TEST-027` | Frozen stack/members, venv launcher/alias/`pyvenv.cfg`, Python/app/headless-shell runtime-tree constants, strict outer-PGID capture versus token-PGID candidate separation, frozen inner-manifest quiescence receipts, abnormal-capture lineage burn/manual audit, Node/`ps`/browser executable authority, Task 6 manifests/artifacts, selector postimages, and protected behavior remain exact. |
| `TEST-028` | Ledger v2 has exact closed node sets and all six bidirectional edge families; every requirement's direct implementation/tests equal the union through its ACs, every implementation/test edge co-occurs in an AC, all 13 ACs have nonempty requirement/implementation/test chains, coverage is exactly 10000 bps, gaps/orphans are empty, and missing/extra/asymmetric/orphan/undeclared edges or false coverage fail. |
| `TEST-029` | Table-driven recursion mutates every schema/nested union with missing/extra/wrong type, bool-as-int, enum/null/order/count/digest errors, including every `RollbackEntry` disposition and `HunkAnchor` longest-prefix/suffix offset/slice/golden arm, exact publisher/replace/negative-probe open flags and admitted-negative cleanup fault branches, closed safe-mode/hash-cap predicates, pathless `DesiredLiveContent`, all safe-present/unknown-regular/absent/nonregular `LiveImageRecord` arms and nullable unknown-regular hash/readability pairing, both rollback-intent arms/current-snapshot/reconciliation rules, patch-section and changed-ID digest domains/preimages plus exact `ThemeBatchTestReport`/`PostApplyPlan`/`PostApplyTestReport` no-domain preimages, logical-vs-physical BatchChange paths, exact CandidateDirectoryRecord manifest root, exact root `proposedContractSha256` preimage and rejected `diagnosticPorcelainSha256`, candidate overlay/manifest/session marker/canary/protected closure/subset receipt, token-PGID versus outer-PGID plans, every-turn kqueue polling cadence, observer failure-cleanup plan, exit-watch result, observation rows/EOF fields/closed phase sequences/digest, four process-family closure kinds and enclosing-plan/process-group projection, every external `CommandResult` outcome/errorCode/stream/process nullability arm including exact empty spawn-failure streams, success-only runner receipt, capability assertion form/error/browser union, and exact 194 probe count; every mutation fails. |

## Verification commands

At minimum, implementation runs:

```bash
.venv/bin/python scripts/test_ui_ux_theme_handoff.py
make ui-ux1b-recovery-tests
make test
.venv/bin/python scripts/test_artifact_loader.py
.venv/bin/python scripts/test_api.py
.venv/bin/python scripts/test_ui_ux1a_safety.py
.venv/bin/python scripts/test_ui_ux_components.py
.venv/bin/python scripts/test_ui_ux_contract.py
.venv/bin/python scripts/test_dashboard_navigation.py
.venv/bin/python -B scripts/test_social_intelligence.py
.venv/bin/python -B scripts/test_ui_ux_snapshot_matrix.py
make ui-ux1b-legacy

.venv/bin/python scripts/ui_ux_snapshot_matrix.py --ux1b-discover --json
.venv/bin/python scripts/ui_ux_snapshot_matrix.py --ux1b-real-smoke --json
.venv/bin/python -B scripts/ui_ux_theme_handoff.py verify-python-syntax --json
.venv/bin/python -B -m tabnanny scripts/ui_ux_theme_handoff.py scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -m pip check
git diff --check
```

Changed Python must parse with `ast.parse(..., feature_version=(3, 10))`.
Existing `verify-prechange`, `verify-scope`, protected-hash, source-projection,
process-quiescence, and zero-`segmented_control` commands from accepted recovery
plans remain mandatory even when no Make alias exists.

The lifecycle command families are:

```bash
make ui-ux1b-theme-handoff-bootstrap UX1B_RECOVERY_ID=20260719T211915Z
make ui-ux1b-theme-handoff-preflight UX1B_RECOVERY_ID=20260719T211915Z
make ui-ux1b-recovery-postcontrol UX1B_RECOVERY_ID=20260719T211915Z \
  UX1B_HANDOFF_PREFLIGHT=.claude/ui_snapshots/ux1b/recovery/theme-handoff-preflight-20260719T211915Z.json
make ui-ux1b-recovery-verify-migration UX1B_RECOVERY_ID=20260719T211915Z
make ui-ux1b-control-migration-review-prepare UX1B_RECOVERY_ID=20260719T211915Z
make ui-ux1b-control-migration-review UX1B_RECOVERY_ID=20260719T211915Z
make ui-ux1b-theme-handoff-prepare UX1B_RECOVERY_ID=20260719T211915Z
make ui-ux1b-theme-handoff UX1B_RECOVERY_ID=20260719T211915Z

make ui-ux1b-theme-batch-init UX1B_THEME_BATCH_ID="$B" UX1B_THEME_RUN_ID="$T"
make ui-ux1b-theme-batch-seal UX1B_THEME_BATCH_ID="$B" UX1B_THEME_RUN_ID="$T"
make ui-ux1b-theme-batch-review UX1B_THEME_BATCH_ID="$B" UX1B_THEME_RUN_ID="$T"
make ui-ux1b-theme-batch-ready UX1B_THEME_BATCH_ID="$B" UX1B_THEME_RUN_ID="$T"
make ui-ux1b-theme-batch-apply UX1B_THEME_BATCH_ID="$B" UX1B_THEME_RUN_ID="$T"
make ui-ux1b-theme-states UX1B_THEME_RUN_ID="$T"
make ui-ux1b-theme-states-review UX1B_THEME_RUN_ID="$T"
make ui-ux1b-theme-states-close UX1B_THEME_RUN_ID="$T"
make ui-ux1b-posttheme UX1B_THEME_RUN_ID="$T"
make ui-ux1b-posttheme-review UX1B_THEME_RUN_ID="$T"
make ui-ux1b-theme-close UX1B_THEME_RUN_ID="$T"
```

## Acceptance criteria

- `AC-HANDOFF-001`: Given exact frozen package/upstream bytes and one canonical
  V2 record, when preflight runs, then it publishes once; any second generic
  marker, malformed delimiter, key/precedence/package mutation publishes none.
- `AC-HANDOFF-002`: Given authenticated tar/archive authority, when historical
  projection is rebuilt, then all nine exact `0644 -> 0444` rows reproduce
  digest `4eeb...`; any header/payload mismatch blocks preflight.
- `AC-HANDOFF-003`: Given absent Task 9 outputs, when two coordinators compete,
  then one freshly creates intent and each frozen stage launch count is at most
  one; every partial owner-loss state becomes revoked rather than resumed.
- `AC-HANDOFF-004`: Given a complete pretheme checkpoint but missing terminal,
  when a fresh reconciler runs, then it may publish exact passed terminal;
  every shorter chain is revoked.
- `AC-HANDOFF-005`: Given the parent holds the global lock and staged root FD,
  when private child verification runs, then it completes without locking or
  publishing while a public command fails busy.
- `AC-HANDOFF-006`: Given exact Task 9 terminal and accepted 117-item packet
  review, when root publication commits, then one immutable v2 root is visible
  and a fresh consumer verifies it pristine.
- `AC-HANDOFF-007`: Given any review kind, when a review is published, then its
  raw assertion matches the machine packet's prompt, inputs, and full item set;
  the verifier supplies no human judgment field.
- `AC-HANDOFF-008`: Given exact sealed five-file candidate and accepted review,
  when apply begins, then only the fresh root-keyed attempt creator may replace
  files, using retained FDs and exact order; an existing claim writes nothing.
- `AC-HANDOFF-009`: Given crash/failure at any five-file boundary, when
  reconciliation runs, then it only rolls exact postimages back, verifies an
  all-post state that already has the exact passed report, or refuses unknown
  bytes; it never reruns failed/missing tests or completes missing forward writes.
- `AC-HANDOFF-010`: Given a passed 3/3 theme-state bundle, 15 artifacts, and an
  accepted 12-item packet review, when closure runs, then an attestation binding
  the applied receipt alone closes parent Task 4.
- `AC-HANDOFF-011`: Given passed 81/81 posttheme, exact source/runtime/semantic
  comparison, and accepted 81-item packet review, when finalization runs, then
  immutable final closure alone closes parent Task 5.
- `AC-HANDOFF-012`: Given Tier 0, one root/theme-lineage Tier 1, and disjoint
  per-batch Tier 1 records, when any create, edit, rollback, or deletion is
  attempted, then one exact ownership/CAS rule applies; root/evidence/lock/
  lease remain retained and drift is not overwritten.
- `AC-HANDOFF-013`: Given the frozen traceability ledger, when package or
  preflight validation runs, then every REQ/CFR has AC/TEST/IMPL edges, every
  AC has TEST/IMPL edges, every TEST/IMPL pair is linked through an AC, all
  edge families map back, full-chain AC coverage is 10000 bps, and
  gaps/orphans are empty.

## Implementation nodes

- `IMPL-001`: `scripts/ui_ux_theme_handoff.py` authorization parser, canonical
  regular/consumptive publisher, private staged-root validator, root
  candidate/publisher/consumer commands.
- `IMPL-002`: the same module's authenticated tar projection, source/
  supplemental reconstruction, runtime/executable receipt, and sidecar compare
  functions.
- `IMPL-003`: the same module's FD inventory, fresh lock/lease bootstrap, Tier
  0/Tier 1 claim, CAS rollback, and retained-evidence functions.
- `IMPL-004`: the same module's plan/import/ledger bidirectional validator.
- `IMPL-005`: the same module's `capture-task9` and `reconcile-task9`
  coordinators/state machine.
- `IMPL-006`: the same module's shared kqueue/process-observer controller,
  `ExitWatchResult` state machine, original-runner-PGID family signal policy,
  disjoint direct-observer-PGID failure cleanup, candidate-session gate,
  review packet/publisher, and theme batch
  init/seal/readiness functions.
- `IMPL-007`: the same module's theme apply, postapply report, rollback-only
  sandbox/environment/lease, reconciliation, and applied-receipt functions.
- `IMPL-008`: the same module's theme-state lease/intent/checkpoint,
  capture/reconcile/packet/attestation functions.
- `IMPL-009`: the same module's posttheme lease/intent/checkpoint,
  capture/reconcile/comparison/packet/finalization functions.
- `IMPL-010`: `Makefile` exact coordinator targets, explicit variables, test
  aggregation, ordering, and nonzero propagation.

## Traceability ledger contract

The sibling `.traceability.yaml` is deliberately canonical JSON, which is a
YAML 1.2 subset: one canonical UTF-8/NFC JSON object followed by exactly one LF.
It uses the same duplicate-key, unknown-key, type, float, and canonical
serialization rejection rules as machine evidence. The filename does not
permit YAML tags, anchors, aliases, merge keys, implicit typing, comments, or
alternate scalar spellings. Its exact top-level keys are
`schemaVersion,status,plan,implementationStatus,testExecution,requirements,
acceptance,implementation,tests,coverageBasisPoints,gaps,orphans`.

The exact fixed values are:

- `schemaVersion:"quant-radar-ui-ux-traceability/v2"`;
- `status:"NOT_TESTED"` and `implementationStatus:"NOT_STARTED"`;
- `plan` equal to this frozen plan's `ArtifactRef`;
- `testExecution:{"status":"NOT_RUN","executedAt":null,"results":[]}`;
- `coverageBasisPoints:10000`, `gaps:[]`, and `orphans:[]`.

`requirements` is an ID-sorted array of exact
`{id,acceptance,implementation,tests}` records for the complete closed set
`CFR-001..CFR-013` plus `REQ-001..REQ-004`. `acceptance` is an ID-sorted array
of exact `{id,requirements,implementation,tests}` records for
`AC-HANDOFF-001..013`. `implementation` is an ID-sorted array of exact
`{id,requirements,acceptance,tests}` records for `IMPL-001..010`; `tests` is
an ID-sorted array of exact `{id,requirements,acceptance,implementation}`
records for `TEST-001..029`. Every nested ID array is unique, nonempty, and
lexicographically sorted.

Requirement forward arrays are exactly the first human-readable table below.
Acceptance implementation/test arrays are exactly the second table;
acceptance requirements are the exact reverse of requirement acceptance.
Each requirement's direct implementation and test arrays must also equal the
set union of those arrays across its acceptance nodes—direct edges may not
claim coverage absent from an AC chain. Implementation/test requirement and
acceptance arrays are exact reverse edges. An implementation/test edge exists
iff at least one acceptance node contains both IDs; both corresponding reverse
arrays must contain that edge. Every expected ID occurs once and every edge in
the six families requirement↔acceptance, requirement↔implementation,
requirement↔test, acceptance↔implementation, acceptance↔test, and
implementation↔test occurs in both directions exactly once.

An acceptance node is full-chain covered only when it has at least one
requirement, implementation, and test and every incident/reachable edge above
is reciprocal. `coverageBasisPoints` is
`floor(10000 * fullChainAcceptanceCount / 13)` and equals `10000` only when all
13 acceptance nodes are covered, every closed-set node is non-orphaned, and
the requirement union rule holds. `gaps:[]` and `orphans:[]` are accepted only
under that same complete condition. The frozen planning ledger records
structural coverage only; it is never rewritten later to imply implementation
or test execution.

## Traceability summary

The sibling ledger is authoritative; this table is its human-readable summary.

| Requirement | Acceptance | Implementation | Tests |
| --- | --- | --- | --- |
| imported `REQ-001`, `CFR-001`, `CFR-002`, `CFR-003`, `CFR-004` | `AC-HANDOFF-002`, `AC-HANDOFF-003`, `AC-HANDOFF-004`, `AC-HANDOFF-005`, `AC-HANDOFF-006` | `IMPL-001`, `IMPL-002`, `IMPL-005`, `IMPL-006`, `IMPL-010` | `TEST-003`, `TEST-004`, `TEST-007`, `TEST-008`, `TEST-009`, `TEST-010`, `TEST-011`, `TEST-012`, `TEST-013`, `TEST-021`, `TEST-024`, `TEST-026`, `TEST-027`, `TEST-029` |
| imported `REQ-002`, `CFR-005`, `CFR-006` | `AC-HANDOFF-008`, `AC-HANDOFF-009`, `AC-HANDOFF-012` | `IMPL-003`, `IMPL-006`, `IMPL-007`, `IMPL-010` | `TEST-005`, `TEST-006`, `TEST-017`, `TEST-018`, `TEST-019`, `TEST-020`, `TEST-021`, `TEST-022`, `TEST-025`, `TEST-026`, `TEST-029` |
| imported `REQ-003` | `AC-HANDOFF-007`, `AC-HANDOFF-010` | `IMPL-006`, `IMPL-008`, `IMPL-009`, `IMPL-010` | `TEST-014`, `TEST-015`, `TEST-016`, `TEST-023`, `TEST-026`, `TEST-029` |
| imported `REQ-004` | `AC-HANDOFF-007`, `AC-HANDOFF-011` | `IMPL-006`, `IMPL-008`, `IMPL-009`, `IMPL-010` | `TEST-014`, `TEST-015`, `TEST-016`, `TEST-023`, `TEST-024`, `TEST-025`, `TEST-026`, `TEST-029` |
| `CFR-007` | `AC-HANDOFF-001` | `IMPL-001` | `TEST-001`, `TEST-002`, `TEST-029` |
| `CFR-008` | `AC-HANDOFF-002` | `IMPL-002` | `TEST-003`, `TEST-004`, `TEST-029` |
| `CFR-009` | `AC-HANDOFF-012` | `IMPL-003`, `IMPL-007` | `TEST-005`, `TEST-006`, `TEST-019`, `TEST-020`, `TEST-021`, `TEST-029` |
| `CFR-010` | `AC-HANDOFF-013` | `IMPL-004` | `TEST-028`, `TEST-029` |
| `CFR-011` | `AC-HANDOFF-003`, `AC-HANDOFF-004` | `IMPL-005`, `IMPL-006`, `IMPL-010` | `TEST-010`, `TEST-011`, `TEST-012`, `TEST-013`, `TEST-021`, `TEST-026`, `TEST-029` |
| `CFR-012` | `AC-HANDOFF-008`, `AC-HANDOFF-009` | `IMPL-006`, `IMPL-007`, `IMPL-010` | `TEST-017`, `TEST-018`, `TEST-019`, `TEST-020`, `TEST-021`, `TEST-022`, `TEST-025`, `TEST-026`, `TEST-029` |
| `CFR-013` | `AC-HANDOFF-007` | `IMPL-006`, `IMPL-008`, `IMPL-009` | `TEST-014`, `TEST-015`, `TEST-016`, `TEST-029` |

### Acceptance full-chain summary

| Acceptance | Implementation | Tests |
| --- | --- | --- |
| `AC-HANDOFF-001` | `IMPL-001` | `TEST-001`, `TEST-002`, `TEST-029` |
| `AC-HANDOFF-002` | `IMPL-002` | `TEST-003`, `TEST-004`, `TEST-029` |
| `AC-HANDOFF-003` | `IMPL-005`, `IMPL-006`, `IMPL-010` | `TEST-010`, `TEST-011`, `TEST-012`, `TEST-013`, `TEST-021`, `TEST-026`, `TEST-029` |
| `AC-HANDOFF-004` | `IMPL-005`, `IMPL-006`, `IMPL-010` | `TEST-010`, `TEST-011`, `TEST-012`, `TEST-013`, `TEST-021`, `TEST-026`, `TEST-029` |
| `AC-HANDOFF-005` | `IMPL-001`, `IMPL-002`, `IMPL-005`, `IMPL-006`, `IMPL-010` | `TEST-003`, `TEST-004`, `TEST-007`, `TEST-008`, `TEST-009`, `TEST-010`, `TEST-011`, `TEST-012`, `TEST-013`, `TEST-021`, `TEST-024`, `TEST-026`, `TEST-027`, `TEST-029` |
| `AC-HANDOFF-006` | `IMPL-001`, `IMPL-002`, `IMPL-005`, `IMPL-006`, `IMPL-010` | `TEST-003`, `TEST-004`, `TEST-007`, `TEST-008`, `TEST-009`, `TEST-010`, `TEST-011`, `TEST-012`, `TEST-013`, `TEST-021`, `TEST-024`, `TEST-026`, `TEST-027`, `TEST-029` |
| `AC-HANDOFF-007` | `IMPL-006`, `IMPL-008`, `IMPL-009` | `TEST-014`, `TEST-015`, `TEST-016`, `TEST-029` |
| `AC-HANDOFF-008` | `IMPL-006`, `IMPL-007`, `IMPL-010` | `TEST-017`, `TEST-018`, `TEST-019`, `TEST-020`, `TEST-021`, `TEST-022`, `TEST-025`, `TEST-026`, `TEST-029` |
| `AC-HANDOFF-009` | `IMPL-006`, `IMPL-007`, `IMPL-010` | `TEST-017`, `TEST-018`, `TEST-019`, `TEST-020`, `TEST-021`, `TEST-022`, `TEST-025`, `TEST-026`, `TEST-029` |
| `AC-HANDOFF-010` | `IMPL-006`, `IMPL-008`, `IMPL-009`, `IMPL-010` | `TEST-014`, `TEST-015`, `TEST-016`, `TEST-023`, `TEST-026`, `TEST-029` |
| `AC-HANDOFF-011` | `IMPL-006`, `IMPL-008`, `IMPL-009`, `IMPL-010` | `TEST-014`, `TEST-015`, `TEST-016`, `TEST-023`, `TEST-024`, `TEST-025`, `TEST-026`, `TEST-029` |
| `AC-HANDOFF-012` | `IMPL-003`, `IMPL-007` | `TEST-005`, `TEST-006`, `TEST-019`, `TEST-020`, `TEST-021`, `TEST-029` |
| `AC-HANDOFF-013` | `IMPL-004` | `TEST-028`, `TEST-029` |

## Risks, trade-offs, and abort rules

- Coordinator loss after intent may sacrifice recovery ID
  `20260719T211915Z`; this is the deliberate cost of at-most-once behavior with
  frozen runners. Cross-process resume requires a new baseline/amendment.
- A crash after theme attempt may burn the lineage before any write. Safety is
  preferred to replaying authorization.
- Five file replacements are a logical CAS, not a filesystem transaction.
  Maintenance-window locking plus rollback-only reconciliation is mandatory.
- The lock protects cooperating commands. Hostile/non-cooperating same-UID
  mutation requires a different UID or external transaction service and is
  outside scope.
- External review is an assertion, not proof of identity. Missing/rejected/
  malformed review blocks the related task.
- Runtime executable inode/hash drift, frozen-stack drift, Task 6 drift,
  selector drift, source drift, partial namespace, invalid collision, unknown
  live theme byte, or package/authorization drift aborts before forward work.
- An initial root, immutable lifecycle evidence, operational lock, and capture
  lease are never deleted by this workflow.

## Plan review gate

Before implementation, freeze this plan and ledger and review request fit,
authority, schema closure, lock/FD lifetime, Task 9 at-most-once transitions,
publication/reconciliation, review packets, theme CAS/recovery, source/runtime,
rollback, Make propagation, and traceability. Any High/Medium/blocker is fixed
and the package refrozen. If the same blocker survives three reviews of this
new baseline, stop and report. The rejected v0.3 review count is not erased; it
remains documented as the reason this separate baseline exists.

## Change history

| Version | Date | Change |
| --- | --- | --- |
| `v1.0-review-candidate` | 2026-07-20 | New baseline after mandated v0.3 stop; replaces read-only capture gates and standalone theme authorization with lock-owning, consumptive one-shot transactions; adds V2 authority, tar mode provenance, packets, exact schemas, tiered rollback, and traceability package. |
