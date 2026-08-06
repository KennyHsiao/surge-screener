# Quant Radar UX-1B Task 9 Chromium Path-Budget Correction

## Document information

| Field | Value |
| --- | --- |
| Type | Corrective implementation plan and execution checklist |
| Version | 1.0 |
| Status | Accepted; blocking-issue review passed |
| Authorization | Maintainer instruction to complete the next corrective plan |
| Author | Codex |
| Reviewer / approver | Repository maintainer |
| Audience | Maintainers and implementation agents |
| Sequence | `7` |
| Recovery ID | `20260725T010000Z` |
| Tier ID | `20260725T011000Z` |
| Superseded active package | Sequence 6 browser-failure containment correction |
| Imported predecessor | Sequence 6 plan, ledger, preflight, intent, revoked terminal, and failed postcontrol manifest |
| Related plan | `docs/superpowers/plans/2026-07-24-quant-radar-ui-ux-ux1b-task9-browser-failure-containment-correction.md` |
| Related ledger | `docs/superpowers/plans/2026-07-25-quant-radar-ui-ux-ux1b-task9-chromium-path-budget-correction.traceability.yaml` |

## Context

Sequence 6 passed its complete implementation, recovery, fail-soft, syntax,
static, source-cardinality, and 81-page disposable canary gates. Tier 0 and
fresh-process preflight verification also passed.

Its single authorized formal `capture-task9` invocation then:

1. published a durable intent;
2. created the private Sequence 6 runtime epoch and postcontrol directories;
3. launched the postcontrol matrix once;
4. failed before its first browser calibration completed;
5. atomically published a failed postcontrol manifest;
6. published and reopened one revoked terminal;
7. returned the original public exit code `9`; and
8. left no owned process alive.

The Sequence 6 containment change therefore worked as designed. The new
blocker is earlier in the frozen isolation stack. Chromium's singleton socket
path is two bytes longer than the accepted maximum.

Recovery ID `20260724T110000Z` is burned. Sequence 6 MUST NOT be retried,
reconciled, or edited.

## Immutable Sequence 6 failure record

| Artifact | SHA-256 | Size | Inode |
| --- | --- | ---: | ---: |
| Plan | `541752db13466a3e5a90093195abf05dd04885fc927b1716ca438478b8b5fe53` | 21454 | 12961304 |
| Ledger | `b0291800a5b77bb3448713579afbf36d880463556d3f5e80fd31c45ae5ee7000` | 3999 | 12961824 |
| Preflight | `4b9e1068058bae33227a07e9de489f2d010b2cb03dda4305394b358f3c25f0a3` | 123152 | 13138504 |
| Intent | `c06d53f9f8d18ccdbd50c126d685f1668a41b942dd834f37a14ba2f2f3581ec7` | 58846 | 13139709 |
| Revoked terminal | `82a3fc3698f191c939423ad9e700766764e5522101c1c5403dddca1ba8905ab1` | 11077 | 13140053 |
| Failed postcontrol manifest | `8acfefd64b2c6545a9e86c1e255a37e7ddd2801df0842dd0eb5c9c5bb68bebcb` | 374 | 13140052 |

The control checkpoint, pretheme gate, pretheme checkpoint, and canonical
pretheme manifest are absent. These four absences are part of the immutable
failure record.

The revoked terminal has:

- `status: revoked`;
- `reason: control_nested_quiescence_unverified`;
- the exact intent reference above;
- null control, pretheme-gate, and pretheme-checkpoint references; and
- no retry or forward authority.

The failed postcontrol manifest is:

```json
{"error":{"message":"UX-1B isolation contract: browser Chromium singleton path is too long","type":"IsolationContractError"},"expectedCaptureCount":36,"fixtureEntrypoint":"scripts/ui_ux_selection_fixture_app.py","mode":"ux1b-selection-controls","phase":"postcontrol","runId":"ux1b-00eafbdc83297eb9e14811f3","schemaVersion":"quant-radar-ui-ux-evidence/v1","status":"failed"}
```

The six retained artifacts and four absent leaves MUST NOT be edited, deleted,
renamed, relinked, truncated, reconciled, or recreated.

## Investigation report

### Bug summary

**Title:** Sequence 6 formal capture exceeds the frozen Chromium singleton
path limit only after both production runtime layers are composed.

**Severity:** High for the formal handoff workflow. There is no production UI,
API, data-loss, or credential impact.

**Reproducibility:** Deterministic for the Sequence 6 formal postcontrol path.

### Exact path derivation

The formal environment sets:

```text
TMPDIR=/private/tmp/quant-radar-ux1b-runtime-sequence6/20260724T110000Z/postcontrol/tmp
```

The frozen matrix creates:

```text
quant-radar-ux1b-<32 lowercase hex>/browser
```

The frozen Darwin calibration then creates:

```text
.ux1b-calibration-<32 lowercase hex>/chromium-tmp/
com.google.chrome.for.testing.<6-character suffix>/SingletonSocket
```

The isolation contract measures the complete encoded path and rejects values
greater than `253` bytes.

The exact conservative Sequence 6 path model is:

```text
/private/tmp/quant-radar-ux1b-runtime-sequence6/20260724T110000Z/postcontrol/tmp/quant-radar-ux1b-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/browser/.ux1b-calibration-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/chromium-tmp/com.google.chrome.for.testing.XXXXXX/SingletonSocket
```

It is `255` bytes. It exceeds the frozen limit by `2` bytes.

### Why the Sequence 6 canary passed

The Sequence 6 canary launched the matrix from the caller's ordinary
temporary directory. It exercised the matrix and calibration layers, but it
did not include the formal coordinator's recovery-ID and stage directories.

The canary therefore proved the capture stack could complete 81 pages. It did
not prove the complete production path composition could start Chromium.

### Three tested hypotheses

1. **Intermittent page or Playwright failure.** Ruled out for this attempt.
   The failed manifest contains the deterministic isolation-contract error
   before a page capture result exists.
2. **Unsafe runtime ownership or stale residue.** Ruled out. The Sequence 6
   root is current-UID/current-GID mode `0700`, contains only the expected
   empty epoch directory tree, and no owned process remains.
3. **Formal-only nested path overflow.** Confirmed. The exact formal
   postcontrol path is `255` bytes, while the frozen contract limit is `253`.

### Root-cause confidence

- **Confirmed, confidence 1.00:** the formal Sequence 6 postcontrol singleton
  model is `255` bytes and the frozen limit is `253`.
- **Confirmed, confidence 1.00:** the normal Sequence 6 canary omitted the
  coordinator's outer recovery-ID and stage layers.
- **Confirmed, confidence 0.99:** a `23`-byte Sequence 7 root produces a
  `231`-byte postcontrol path and a `228`-byte pretheme path.
- **Unknown:** whether a later capture operation will encounter an unrelated
  runtime failure. Sequence 7 does not claim otherwise.

### Ruled-out actions

- No retry or reconcile of recovery ID `20260724T110000Z`.
- No increase to the `253`-byte frozen isolation limit.
- No shortening of frozen matrix, calibration, or Chromium leaf names.
- No mutation or rotation of the nine-member capture stack.
- No deletion or reuse of the Sequence 6 runtime root.
- No normal canary that omits the production outer path.

## Scope

### In scope

- Authorize Sequence 7 and recovery ID `20260725T010000Z`.
- Import and reauthenticate the exact six Sequence 6 artifacts and four
  absences above.
- Preserve every Sequence 1–6, Task 6, capture-stack, compatibility,
  global-lock, lease, and fail-soft authority.
- Use a new absent runtime root `/private/tmp/qr-ux1b-s7`.
- Add a pure coordinator-owned path-budget oracle.
- Require the oracle before a preflight can pass.
- Require at least `16` bytes of margin below the frozen `253`-byte limit.
- Test the Sequence 6 path as rejected and both Sequence 7 stages as accepted.
- Run one disposable 81-page canary under a production-shaped outer
  `TMPDIR` whose modeled longest socket path is exactly `237` bytes.
- Create new Sequence 7 Tier 0, preflight, lifecycle, and capture namespaces.
- Run one formal Sequence 7 Task 9 capture only after every gate passes.

### Non-goals

- Do not change `scripts/ui_ux_isolation.py`,
  `scripts/ui_ux_snapshot_matrix.py`, `scripts/ui_ux_browser_worker.py`, or
  any other capture-stack member.
- Do not change UI, theme, API, provider, writer, cache, or persisted artifact
  behavior.
- Do not change Streamlit or FastAPI fail-soft behavior.
- Do not add browser, page, stage, or whole-run retries.
- Do not increase timeouts or add sleeps.
- Do not treat the disposable canary as formal evidence.
- Do not continue to migration, manual review, root publication, or theme
  application.

## Success metrics

| Metric | Required result |
| --- | --- |
| Sequence 6 formal command count | exactly `1`; unchanged |
| Sequence 6 retained artifacts | `6 / 6` exact |
| Sequence 6 absent leaves | `4 / 4` absent |
| Frozen capture-stack members | `9 / 9` byte-identical |
| Sequence 6 modeled postcontrol bytes | exactly `255`; rejected |
| Sequence 7 modeled postcontrol bytes | exactly `231`; margin `22` |
| Sequence 7 modeled pretheme bytes | exactly `228`; margin `25` |
| Minimum accepted path margin | at least `16` bytes |
| Production-shaped canary path bytes | exactly `237` |
| Production-shaped canary captures | `81 / 81` passed |
| Formal Sequence 7 capture commands | at most `1` |
| Owned process closure | zero live descendants after every command |
| Fail-soft suites | all selected suites pass |

## Dependencies

- macOS/Darwin with the already authenticated Seatbelt backend.
- The existing Python `3.11.15` virtual environment.
- The immutable nine-member capture-stack contract.
- The immutable canonical Task 6 baseline.
- The exact Sequence 6 failure record above.
- Absence of every fixed Sequence 7 destination before authorization.

## Glossary

| Term | Definition |
| --- | --- |
| Path budget | The maximum encoded path length allowed by the frozen isolation contract. |
| Singleton socket | Chromium's `SingletonSocket` path below its temporary profile directory. |
| Production-shaped canary | A disposable capture using the formal recovery/stage directory shape, without lifecycle authority. |
| Runtime root | The private `/private/tmp` parent retained by the Task 9 coordinator. |
| Burned recovery ID | An ID whose durable intent exists and can never be retried. |
| Authority record | A digest-bound immutable input accepted by Tier 0 and preflight. |

## Authority and precedence

The recovery authorization document MUST contain exactly one canonical V2
marker pair. Its body MUST authorize:

- integer `sequence:7`;
- recovery ID `20260725T010000Z`;
- this plan and its canonical sibling traceability ledger; and
- the unchanged four-level precedence array.

The Sequence 7 package MUST reauthenticate:

1. this Sequence 7 plan and ledger;
2. the exact Sequence 6 plan and ledger;
3. the exact Sequence 6 preflight, intent, revoked terminal, and failed
   postcontrol manifest;
4. the exact absence of the Sequence 6 control checkpoint, pretheme gate,
   pretheme checkpoint, and canonical pretheme manifest;
5. every Sequence 1–5 authority imported by Sequence 6;
6. the Task 6 manifests and all `234` artifacts; and
7. capture-stack, runtime, selector-delta, compatibility, lock, and lease
   authority.

The Sequence 7 package contains exactly `30` package authority records. With
the unchanged `20` upstream records, Tier 0 contains exactly `50` authority
records.

The Tier 0 live input set contains exactly `315` records. The source mirror
contains exactly `268` records. The supplemental projection contains exactly
`54` records. Arrays are path-sorted and unique. Every authority record is
byte-for-byte identical to its live-set record.

Sequence 6 failure evidence is historical authority only. It MUST NOT
authorize a Sequence 7 runner or appear in an eligible Sequence 7
destination.

## Fixed Sequence 7 namespace

The following paths were verified absent before this plan was frozen:

```text
/private/tmp/qr-ux1b-s7
.claude/ui_snapshots/ux1b/sequence7-canary-20260725T010000Z/
.claude/ui_snapshots/ux1b/recovery/.capture-20260725T010000Z.lease
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-prechange-seq7.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-rollback-seq7.json
.claude/ui_snapshots/ux1b/recovery/theme-handoff-prechange-20260725T011000Z/
.claude/ui_snapshots/ux1b/recovery/theme-handoff-preflight-20260725T010000Z.json
.claude/ui_snapshots/ux1b/recovery/capture-intent-20260725T010000Z.json
.claude/ui_snapshots/ux1b/recovery/capture-control-checkpoint-20260725T010000Z.json
.claude/ui_snapshots/ux1b/recovery/capture-pretheme-gate-20260725T010000Z.json
.claude/ui_snapshots/ux1b/recovery/capture-pretheme-checkpoint-20260725T010000Z.json
.claude/ui_snapshots/ux1b/recovery/capture-terminal-20260725T010000Z.json
.claude/ui_snapshots/ux1b/recovery/postcontrol-controls-20260725T010000Z/
.claude/ui_snapshots/ux1b/recovery/canonical-pretheme-20260725T010000Z/
```

Later migration, review, candidate, intake, and root destinations retain the
Sequence 6 shape with the new recovery ID. The canonical root contract remains
absent.

## Requirements

### `REQ-007` — reject unsafe Chromium path composition before capture

The coordinator MUST model the longest frozen Chromium singleton path for
both Task 9 stages. Preflight MUST fail closed unless each encoded path is at
most `237` bytes. No lifecycle intent or runner may be created from a failed
path-budget preflight.

### `CFR-017` — immutable Sequence 6 failure record

The exact six-artifact Sequence 6 failure record and four absent leaves MUST
remain immutable before, during, and after every Sequence 7 command.

### `CFR-018` — isolated short runtime root

Sequence 7 MUST create and retain only `/private/tmp/qr-ux1b-s7`. It MUST
never open, normalize, delete, or reuse the Sequence 6 runtime root.

### `CFR-019` — production-shaped canary and no retry

The disposable canary MUST include recovery-ID and stage layers. It runs at
most once and grants no lifecycle authority. Each formal stage runs at most
once.

### `CFR-020` — compatibility and fail-soft preservation

All capture-stack, selector, source, API, Streamlit, artifact-loader, Python
3.10, descriptor, process, and immutable predecessor gates remain exact.

## Corrected production design

### Runtime root

The Sequence 7 runtime receipt uses:

```text
tempRootParent = /private/tmp/qr-ux1b-s7
```

The longest exact path model becomes:

```text
/private/tmp/qr-ux1b-s7/20260725T010000Z/postcontrol/tmp/quant-radar-ux1b-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/browser/.ux1b-calibration-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/chromium-tmp/com.google.chrome.for.testing.XXXXXX/SingletonSocket
```

It is `231` bytes. The shorter `pretheme` stage produces `228` bytes.

### Pure path-budget oracle

`scripts/ui_ux_theme_handoff.py` adds a pure helper with closed constants:

```text
singleton limit = 253 bytes
required margin = 16 bytes
maximum accepted modeled path = 237 bytes
matrix prefix = quant-radar-ux1b- + 32 characters
browser leaf = browser
calibration prefix = .ux1b-calibration- + 32 characters
Chromium suffix directory = com.google.chrome.for.testing. + 6 characters
socket leaf = SingletonSocket
stages = postcontrol, pretheme
```

The pure model helper:

1. accepts a normalized absolute runtime root and a fixed-format recovery ID;
2. builds both complete paths with `pathlib.Path`;
3. measures with `os.fsencode`;
4. proves the path strings are absolute and contain the exact closed
   components;
5. returns the stage, path, byte count, limit, and margin to tests.

A production validation wrapper additionally requires the exact authorized
root and recovery ID. It raises `ContractViolation` if either identity differs
or any byte count exceeds `237`.

The helper does not create directories. It does not import or alter a
capture-stack member.

### Gate placement

`_build_runtime_receipt()` invokes the oracle before returning a runtime
receipt. Preflight construction and fresh-process preflight verification both
rebuild that receipt. An unsafe path therefore fails before formal intent
publication.

The existing Task 9 authority reauthentication remains unchanged. The
Sequence 6 runner-failure terminalization path also remains unchanged.

### Production-shaped canary

The canary uses a private `mktemp` root with this template:

```text
/private/tmp/qr-ux1b-c7.XXXXX
```

Below it, the command creates:

```text
20260725T010000Z/postcontrol/tmp
```

That makes the complete modeled canary socket path exactly `237` bytes. The
matrix then creates its normal owned run and calibration directories beneath
that `TMPDIR`.

Cleanup uses bottom-up `rmdir` only. Unexpected residue makes cleanup fail and
blocks Tier 0. The Sequence 7 production root remains absent until its own
coordinator lifecycle creates it.

## Acceptance criteria

### `AC-SEQ7-001` — exact predecessor import

Given the Sequence 7 package, when authorization is validated, then all six
Sequence 6 records match their exact digest, size, inode, and bytes; all four
later leaves remain absent.

### `AC-SEQ7-002` — exact path-budget oracle

Given the frozen path components, when the oracle models Sequence 6 and
Sequence 7, then Sequence 6 postcontrol is exactly `255` bytes and rejected;
Sequence 7 postcontrol is `231`, pretheme is `228`, and both retain at least
`16` bytes of margin.

### `AC-SEQ7-003` — preflight fails before lifecycle

Given an over-budget runtime root, when preflight or fresh verification
rebuilds the runtime receipt, then it returns a contract failure; no intent,
runner, capture directory, or terminal is created.

### `AC-SEQ7-004` — isolated runtime root

Given the Sequence 7 root is absent and Sequence 6 is retained, when
Sequence 7 starts, then it creates and FD-normalizes only its exact root and
exclusive epoch. Every Sequence 6 runtime inode remains unchanged.

### `AC-SEQ7-005` — production-shaped canary

Given a private canary root whose complete modeled path is `237` bytes, when
the exact pretheme matrix runs once, then it passes `81 / 81`, publishes a
canonical disposable manifest, leaves no process alive, and removes only the
empty canary runtime directories.

### `AC-SEQ7-006` — formal one-shot and terminal closure

Given passed Tier 0, preflight, fresh verification, and canary, when the one
formal Sequence 7 command runs, then each stage launches at most once.
Success publishes a passed terminal. A typed runner failure publishes a
revoked terminal and preserves the original nonzero exit.

### `AC-SEQ7-007` — complete compatibility gates

Given the final implementation diff, when all focused, recovery, fail-soft,
syntax, static, source, predecessor, descriptor, and process gates run, then
all selected checks pass and all nine capture-stack members remain exact.

## Affected files

### Planned source changes

- `scripts/ui_ux_theme_handoff.py`
- `scripts/test_ui_ux_theme_handoff.py`
- `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery.md`

### Plan and traceability

- this plan
- `docs/superpowers/plans/2026-07-25-quant-radar-ui-ux-ux1b-task9-chromium-path-budget-correction.traceability.yaml`

### Planning journal updates

- `.agents/scribe.md`
- `.agents/PROJECT.md`

### Generated execution evidence

- Sequence 7 Tier 0 prechange, rollback, and preflight records
- Sequence 7 lifecycle and capture namespaces
- the disposable Sequence 7 canary namespace

### Explicitly unchanged

- all nine capture-stack members
- `Makefile`
- production UI and API files
- theme source files
- Sequence 1–6 evidence and runtime roots

## Implementation checklist

- [ ] `IMPL-033`: Freeze this plan and ledger; publish Sequence 7
  authorization.
- [ ] `IMPL-034`: Add Sequence 7 namespaces and import the exact Sequence 6
  failure authority and absences.
- [ ] `IMPL-035`: Add the short runtime root and pure two-stage path-budget
  oracle.
- [ ] `IMPL-036`: Invoke the oracle from runtime-receipt construction and
  fresh preflight verification.
- [ ] `IMPL-037`: Add red-first predecessor, path-budget, preflight, runtime,
  and compatibility tests.
- [ ] `IMPL-038`: Run complete recovery, fail-soft, static, source,
  predecessor, and process gates; then run the production-shaped canary once.
- [ ] `IMPL-039`: Bootstrap, publish preflight, reopen it in a fresh process,
  and run exactly one formal Task 9 command.

## Test specification

| Test | Observable result |
| --- | --- |
| `TEST-050` | Sequence 6 six-artifact failure record and four absences remain exact. |
| `TEST-051` | Sequence 7 package, authority, live, mirror, and supplemental cardinalities are exact. |
| `TEST-052` | Sequence 6 models `255` and fails; Sequence 7 models `231` and `228` with required margin. |
| `TEST-053` | Unsafe runtime roots fail preflight before any lifecycle or runner side effect. |
| `TEST-054` | Sequence 7 uses only its exact absent runtime root and leaves Sequence 6 runtime inodes unchanged. |
| `TEST-055` | Successful and typed-runner-failure Task 9 terminal behavior remains exact and retry-free. |
| `TEST-056` | Complete gates pass and the one-shot production-shaped canary completes `81 / 81`. |
| `TEST-057` | Fresh preflight reopen and one formal Sequence 7 command produce one closed terminal outcome. |

## Traceability matrix

| Requirement | Acceptance | Implementation | Tests |
| --- | --- | --- | --- |
| `REQ-007` | `AC-SEQ7-002`, `AC-SEQ7-003` | `IMPL-035`, `IMPL-036`, `IMPL-037` | `TEST-052`, `TEST-053` |
| `CFR-017` | `AC-SEQ7-001` | `IMPL-033`, `IMPL-034`, `IMPL-037` | `TEST-050`, `TEST-051` |
| `CFR-018` | `AC-SEQ7-002`, `AC-SEQ7-004` | `IMPL-035`, `IMPL-037` | `TEST-052`, `TEST-054` |
| `CFR-019` | `AC-SEQ7-005`, `AC-SEQ7-006` | `IMPL-038`, `IMPL-039` | `TEST-055`, `TEST-056`, `TEST-057` |
| `CFR-020` | `AC-SEQ7-006`, `AC-SEQ7-007` | `IMPL-037`, `IMPL-038`, `IMPL-039` | `TEST-055`, `TEST-056`, `TEST-057` |

## Commands and gates

Before canary, Tier 0, or formal publication:

```bash
.venv/bin/python -B scripts/ui_ux_theme_handoff.py verify-python-syntax --json
.venv/bin/python -B scripts/test_ui_ux_theme_handoff.py
make ui-ux1b-recovery-tests
```

Also run:

- the selected API and Streamlit fail-soft suites;
- Python 3.10 AST parsing;
- `tabnanny`;
- dependency and whitespace checks;
- authorization-marker and traceability checks;
- source, authority, live, mirror, and supplemental cardinality checks;
- exact Sequence 6 digest, size, inode, and absence checks;
- exact capture-stack digest checks;
- new-namespace and runtime-root checks; and
- process-quiescence checks.

The one-shot production-shaped canary is:

```bash
set -euo pipefail
canary_root="$(mktemp -d /private/tmp/qr-ux1b-c7.XXXXX)"
canary_epoch="${canary_root}/20260725T010000Z"
canary_stage="${canary_epoch}/postcontrol"
canary_tmp="${canary_stage}/tmp"
trap 'rmdir "$canary_tmp" "$canary_stage" "$canary_epoch" "$canary_root"' EXIT
mkdir -m 0700 "$canary_epoch" "$canary_stage" "$canary_tmp"
TMPDIR="$canary_tmp" TMP="$canary_tmp" TEMP="$canary_tmp" \
  .venv/bin/python -B scripts/ui_ux_snapshot_matrix.py \
    --profile ux1b-full-pages \
    --phase pretheme \
    --browser chromium \
    --out-dir .claude/ui_snapshots/ux1b/sequence7-canary-20260725T010000Z \
    --no-prompt \
    --json
```

Before this command, an independent oracle MUST prove its modeled maximum is
exactly `237` bytes. The output directory and canary root MUST both be absent.

The formal order, only after the canary passes and cleanup succeeds, is:

```bash
make ui-ux1b-theme-handoff-bootstrap \
  UX1B_RECOVERY_ID=20260725T010000Z
make ui-ux1b-theme-handoff-preflight \
  UX1B_RECOVERY_ID=20260725T010000Z
.venv/bin/python -B scripts/ui_ux_theme_handoff.py verify-preflight \
  --recovery-id 20260725T010000Z --json
make ui-ux1b-recovery-postcontrol \
  UX1B_RECOVERY_ID=20260725T010000Z \
  UX1B_HANDOFF_PREFLIGHT=.claude/ui_snapshots/ux1b/recovery/theme-handoff-preflight-20260725T010000Z.json
```

The final command is the only authorized formal Task 9 capture invocation for
Sequence 7.

## Failure policy

- A failed path-budget test blocks implementation.
- A failed production-shaped canary blocks Tier 0. Do not rerun it.
- Any committed Sequence 7 intent burns recovery ID `20260725T010000Z`.
- A formal runner failure MUST leave a revoked terminal. Do not retry.
- A terminal-publication failure requires a new accepted correction and ID.
- No failed, revoked, or disposable record grants migration or theme
  authority.
- If the same blocking issue survives three plan-review iterations, stop and
  report it.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| The path model drifts from the frozen stack | Bind exact closed components, retain capture-stack hashes, and run the production-shaped canary. |
| A short root weakens isolation | Ownership, mode, descriptor, GID normalization, and exclusive-epoch checks remain unchanged. |
| Canary residue affects formal runtime | Use a disjoint root and bottom-up `rmdir`; residue blocks Tier 0. |
| The new plan mutates historical evidence | Import exact records and absences; stat-check them before and after every gate. |
| Formal capture encounters an unrelated browser failure | Preserve Sequence 6 typed failure terminalization and original exit code; never retry. |
| Cardinalities are miscomputed | Require exact package `30`, authority `50`, live `315`, mirror `268`, and supplemental `54` tests. |

## Rollback

- Before Sequence 7 Tier 0 publication, rollback removes only uncommitted
  Sequence 7 code and authorization changes.
- The rollback MUST preserve all Sequence 1–6 evidence, runtime roots, and
  unrelated dirty-worktree changes.
- After Tier 0 publication, Sequence 7 evidence is immutable. Any correction
  requires a new accepted sequence and recovery ID.
- The canary namespace is disposable and never replaces formal evidence.

## Blocking-issue review

### Review iteration 1

- **Finding:** A shorter runtime root alone would fix the current path but
  would not prevent a later long root from reaching formal capture.
- **Resolution:** Add a pure preflight path-budget oracle with a `16`-byte
  required margin.

### Review iteration 2

- **Finding:** The prior canary did not contain the coordinator's recovery-ID
  and stage layers.
- **Resolution:** Use a disjoint production-shaped canary whose modeled path
  is exactly `237` bytes.

### Review iteration 3

- **Finding:** A same-root canary could create or contaminate the formal
  Sequence 7 runtime root.
- **Resolution:** Use `/private/tmp/qr-ux1b-c7.XXXXX`, require empty-only
  bottom-up cleanup, and keep `/private/tmp/qr-ux1b-s7` absent.

### Review iteration 4

- **Finding:** The draft counted the new plan and ledger inside the source
  mirror, but that mirror's fixed include policy excludes plan documents.
- **Resolution:** Keep the verified mirror count at `268`. Count the two new
  package files and four Sequence 6 runtime records in supplemental authority,
  producing exact counts `315 / 50 / 268 / 54`.

No blocking issue remains. The four findings are different review findings,
not one repeated unresolved blocker.

## Review checklist

- [x] The user request is covered by an executable corrective plan.
- [x] Affected files, verification steps, and risk areas are explicit.
- [x] Sequence 6 formal command count remains exactly one.
- [x] All six predecessor artifacts and four absences are exact.
- [x] The exact 255-byte root cause is reproducible.
- [x] The Sequence 7 root has at least 16 bytes of margin.
- [x] The canary includes the missing production outer layers.
- [x] No capture-stack member or 253-byte limit changes.
- [x] No retry, timeout increase, sleep, or failure suppression is introduced.
- [x] Existing runner-failure terminalization remains exact.
- [x] Requirement, acceptance, implementation, and test links are complete.
- [x] New namespaces are absent and disjoint.
- [x] No unresolved blocking issue remains.
- [ ] Changed-code review reports no blocking issue.
- [ ] Fresh-process preflight reopen passes before the formal one-shot.

## Change history

| Version | Date | Change |
| --- | --- | --- |
| 1.0 | 2026-07-25 | Accepted after four distinct blocking reviews closed exact path modeling, production-shaped canary coverage, runtime-root separation, and source/supplemental cardinalities. |
| 0.1 | 2026-07-25 | Drafted the short-root, preflight path-budget, immutable predecessor, and one-shot execution correction. |
