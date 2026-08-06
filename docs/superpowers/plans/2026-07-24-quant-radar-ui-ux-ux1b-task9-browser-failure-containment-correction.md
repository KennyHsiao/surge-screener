# Quant Radar UX-1B Task 9 Browser Failure Containment Correction

## Document information

| Field | Value |
| --- | --- |
| Type | Corrective implementation plan and execution checklist |
| Version | 1.0 |
| Status | Accepted; blocking-issue review passed |
| Authorization | Maintainer instruction to continue the corrective workflow |
| Author | Codex |
| Reviewer / approver | Repository maintainer |
| Audience | Maintainers and implementation agents |
| Sequence | `6` |
| Recovery ID | `20260724T110000Z` |
| Tier ID | `20260724T111000Z` |
| Superseded active package | Sequence 5 system-temp group correction |
| Imported predecessor | Sequence 5 plan, ledger, preflight, intent, control checkpoint, pretheme gate, passed control manifest, and failed pretheme manifest |

## Context

Sequence 5 corrected Darwin `/private/tmp` group inheritance and passed its
complete implementation, recovery, fail-soft, syntax, static, scope, and
fresh-preflight gates. Its single authorized formal `capture-task9`
invocation:

1. normalized the retained shared runtime root from GID `0` to the current
   primary GID without changing its inode;
2. exclusively created recovery epoch `20260724T090000Z`;
3. completed 36/36 postcontrol captures;
4. published the intent, passed control checkpoint, and passed pretheme gate;
5. reopened the same retained runtime epoch under the active policy;
6. started the 81-page pretheme matrix; and
7. exited with public code `9` when the browser worker failed at
   `stock-checkup/desktop`.

The runner atomically published this failed manifest:

```json
{"error":{"message":"browser worker failed for stock-checkup/desktop: RuntimeError","type":"RuntimeError"},"expectedCaptureCount":81,"fixtureEntrypoint":"scripts/ui_ux_fixture_app.py","mode":"ux1b-full-pages","phase":"pretheme","runId":"ux1b-3f0cc3613901e628050c1a65","schemaVersion":"quant-radar-ui-ux-evidence/v1","status":"failed"}
```

The coordinator correctly did not publish a pretheme checkpoint or a passed
terminal. It also did not publish a revoked terminal because
`_Task9RunnerFailure` currently escapes `_task9_transition()` to the public
handler. Recovery ID `20260724T090000Z` is burned and MUST NOT be retried.

## Immutable Sequence 5 failure record

| Artifact | SHA-256 | Size | Inode |
| --- | --- | ---: | ---: |
| Plan | `d6d276b0fdb7c23f5d17a3389946a0bbd2d7289ca50eeed8cb7b27034363ba97` | 17043 | 12682687 |
| Ledger | `cc6cd0529c3994a3b89dc4cf9238f2fc33a4bc72df190f0a4344578fd6fd4ef6` | 3105 | 12682775 |
| Preflight | `230c2afb7e1d4619c1fe943e479ea07b60f0e15e250e3c0f94faae3fd77d574e` | 118614 | 12901034 |
| Intent | `70519dec43b2fb6127ffd2568411f1ffc81a0af573a84d59ea89729ae0c4ef62` | 58696 | 12902181 |
| Control checkpoint | `d59a9c94c5ed5d0f95d0b7d7e00eae95cef0b614a800bb36730fb3df57d53c5b` | 17347 | 12912483 |
| Pretheme gate | `7828765d9cf589fc339ff139537db51379e733aa1ebbcf9b6b8ae4d15068d5ef` | 55274 | 12912762 |
| Passed control manifest | `6382e27aa5b635eccca8a7883f5ac019e994a4bb02844a5f66b42530f376b946` | 35103 | 12912480 |
| Failed pretheme manifest | `1ea244689dad0b9bac84d524cbf8a860679f0057d2d3ae518070b5b644ed1221` | 335 | 12926664 |

The pretheme checkpoint and terminal are both absent. Those absences are part
of the failure record. The eight retained artifacts and the two absent leaves
MUST NOT be edited, deleted, renamed, relinked, truncated, reconciled, or
recreated.

## Investigation report

### Bug summary

**Title:** A single browser-worker failure burns a formal Task 9 recovery ID
without publishing a terminal lifecycle record.

**Severity:** High for the formal handoff workflow; no production UI, API, or
data-loss impact.

**Reproducibility:** Intermittent.

### Timeline

| Event | Evidence |
| --- | --- |
| Sequence 5 formal run began | one `capture-task9` process for recovery `20260724T090000Z` |
| Postcontrol completed | passed 36-capture manifest and passed control checkpoint |
| Active runtime reopen completed | passed pretheme gate followed by a live pretheme runner |
| Pretheme advanced through the catalog | independently sampled worker IDs changed from `analytics-db/mobile` through `radar/tablet` |
| Case 55 failed | failed manifest identifies `stock-checkup/desktop` and `RuntimeError` |
| Cleanup completed | no capture runner, browser worker, or owned fixture process remained |
| Public command ended | exit code `9`; no pretheme checkpoint or terminal |

### Three tested hypotheses

1. **Stable page or selector defect.** Ruled out at the available evidence
   level. A normal single-page capture passed 1/1. Five same-stack,
   sandboxed, descriptor-owned `stock-checkup/desktop` browser workers all
   completed staging; the diagnostic harness rejected only its intentionally
   inapplicable mobile-dimension assertion after each worker succeeded.
2. **Sequence 5 runtime-root defect or resource exhaustion.** Ruled out.
   The root normalization and active reopen passed, the private runtime
   contained zero files and zero bytes after cleanup, disk use was 8%, VM
   throttling was zero, and no current Chrome crash report exists.
3. **Intermittent browser/Playwright failure.** Supported but the concrete
   inner exception is unconfirmed. The same frozen capture stack has three
   retained 81/81 passed manifests. The worker intentionally collapses all
   otherwise unclassified Playwright exceptions to `RuntimeError`, then emits
   only that safe type.

### Root-cause confidence

- **Confirmed, confidence 0.95:** `_Task9RunnerFailure` can escape after a
  durable intent and later prefix records exist, leaving no terminal.
- **Confirmed, confidence 0.90:** the frozen worker boundary removes the
  concrete Playwright cause before Task 9 can record it.
- **Estimated, confidence 0.65:** the observed page failure is intermittent
  rather than a stable page defect.
- **Unknown:** the concrete Playwright operation or exception that failed.

The frozen browser-worker and evidence protocol are capture-stack authority.
Changing their response schema would require a capture-stack rotation and a
new Task 6 baseline. This correction MUST NOT silently perform that larger
migration.

### Ruled-out actions

- No retry of recovery ID `20260724T090000Z`.
- No retry-until-pass logic inside browser capture.
- No timeout increase, sleep, or exception suppression without a confirmed
  cause.
- No mutation of the frozen capture stack.
- No claim that the failed pretheme manifest proves 81-page success.

## Scope

### In scope

- Authorize Sequence 6 and recovery ID `20260724T110000Z`.
- Import and reauthenticate the exact eight Sequence 5 artifacts and exact two
  absent lifecycle leaves above.
- Preserve all Sequence 1–4, Task 6, capture-stack, compatibility, global-lock,
  lease, and fail-soft authority imported by Sequence 5.
- Use a new absent shared runtime root
  `/private/tmp/quant-radar-ux1b-runtime-sequence6` so the retained Sequence 5
  runtime epoch remains untouched.
- Catch only `_Task9RunnerFailure` at each Task 9 runner boundary.
- Publish one revoked terminal with the already-declared conservative reason
  `control_nested_quiescence_unverified` or
  `pretheme_nested_quiescence_unverified`.
- Preserve the runner's original public nonzero exit code after the revoked
  terminal is durably reopened.
- Require a disposable, exact 81-page pretheme canary after all code and
  recovery gates pass but before Tier 0 bootstrap.
- Create new Sequence 6 Tier 0, preflight, lifecycle, and capture namespaces.
- Run one formal Sequence 6 Task 9 capture only if the canary and every other
  gate pass.

### Non-goals

- Do not retry or reconcile Sequence 5.
- Do not diagnose or claim the unknown inner Playwright exception.
- Do not change `scripts/ui_ux_browser_worker.py`,
  `scripts/ui_ux_evidence.py`, the canonical capture-stack contract, or the
  Task 6 manifests.
- Do not add browser, page, stage, or whole-run retries.
- Do not change page selectors, UI code, theme files, API code, Streamlit
  fail-soft behavior, or FastAPI fail-soft behavior.
- Do not accept a canary failure.
- Do not continue to migration, manual review, root publication, or theme
  application.

## Authority and precedence

The recovery authorization document MUST contain exactly one canonical V2
marker pair. Its body MUST authorize:

- integer `sequence:6`;
- recovery ID `20260724T110000Z`;
- this plan and its canonical sibling traceability ledger; and
- the unchanged four-level precedence array.

The Sequence 6 package MUST reauthenticate:

1. this Sequence 6 plan and ledger;
2. the exact Sequence 5 plan and ledger;
3. the exact Sequence 5 preflight, intent, control checkpoint, pretheme gate,
   passed control manifest, and failed pretheme manifest;
4. the exact absence of the Sequence 5 pretheme checkpoint and terminal;
5. the exact Sequence 4 plan, ledger, preflight, intent, and revoked terminal;
6. the exact Sequence 3 plan, ledger, passed preflight, and intent-only
   failure;
7. the Sequence 2 amendment, ledger, and preflight;
8. the Sequence 1 parent plan and ledger;
9. the Task 6 manifests and all 234 artifacts; and
10. capture-stack, runtime, selector-delta, compatibility, lock, and lease
    authority.

The resulting Tier 0 input set MUST contain exactly `309` live records and
`44` authority records. The source mirror MUST contain exactly `268` records
and the supplemental projection exactly `48` records. Arrays are sorted and
unique by path. Every authority record is byte-for-byte the identical record
in the live set.

Sequence 5 failure evidence is historical authority only. It MUST NOT
authorize a Sequence 6 runner or appear in an eligible Sequence 6
destination.

## Fixed Sequence 6 namespace

The following paths MUST be absent before this plan is frozen:

```text
/private/tmp/quant-radar-ux1b-runtime-sequence6
.claude/ui_snapshots/ux1b/sequence6-canary-20260724T110000Z/
.claude/ui_snapshots/ux1b/recovery/.capture-20260724T110000Z.lease
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-prechange-seq6.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-rollback-seq6.json
.claude/ui_snapshots/ux1b/recovery/theme-handoff-prechange-20260724T111000Z/
.claude/ui_snapshots/ux1b/recovery/theme-handoff-preflight-20260724T110000Z.json
.claude/ui_snapshots/ux1b/recovery/capture-intent-20260724T110000Z.json
.claude/ui_snapshots/ux1b/recovery/capture-control-checkpoint-20260724T110000Z.json
.claude/ui_snapshots/ux1b/recovery/capture-pretheme-gate-20260724T110000Z.json
.claude/ui_snapshots/ux1b/recovery/capture-pretheme-checkpoint-20260724T110000Z.json
.claude/ui_snapshots/ux1b/recovery/capture-terminal-20260724T110000Z.json
.claude/ui_snapshots/ux1b/recovery/postcontrol-controls-20260724T110000Z/
.claude/ui_snapshots/ux1b/recovery/canonical-pretheme-20260724T110000Z/
```

Later migration, review, candidate, intake, and root destinations retain the
Sequence 5 shape with the new recovery ID. The canonical root contract remains
absent.

## Requirements

### `REQ-006` — terminalize runner failures

Given a fresh Task 9 intent and a `_Task9RunnerFailure` from postcontrol or
pretheme, the coordinator MUST publish and reopen exactly one revoked
terminal before returning the original failure exit code. It MUST NOT publish
a passed checkpoint for the failed stage, launch a later stage, retry the
runner, or publish root authority.

### `CFR-013` — immutable predecessor failure

The exact Sequence 5 eight-artifact failure record and two absent leaves MUST
remain immutable before, during, and after every Sequence 6 command.

### `CFR-014` — isolated private runtime

Sequence 6 MUST create and retain only the new absent shared runtime root.
The exact `/private/tmp` retained-FD GID normalization from Sequence 5 remains
mandatory. The Sequence 5 root and epoch are never opened for Sequence 6
runner authority.

### `CFR-015` — no hidden retry

Every Sequence 6 stage has at most one runner launch. The disposable canary
is a separate pre-bootstrap gate with no lifecycle or forward authority. A
failed canary blocks Tier 0 and requires a new capture-stack remediation plan;
it MUST NOT be retried until passing.

### `CFR-016` — compatibility and fail-soft preservation

All existing capture-stack, selector, source, API, Streamlit, artifact-loader,
Python 3.10, descriptor, process, and immutable predecessor gates remain
exact.

## Corrected production design

`_task9_transition()` owns the lifecycle and already has durable publication
authority. Add one local failure-terminal path:

```text
runner boundary raises _Task9RunnerFailure
  -> do not retry
  -> do not publish the failed-stage checkpoint
  -> build terminal from the closed terminal template
  -> status = revoked
  -> bind only the prefix refs already durably published
  -> use the existing conservative nested-quiescence reason
  -> publish and reopen terminal exactly once
  -> return the original runner exit code
```

For a postcontrol failure, only `intent` is non-null. For a pretheme failure,
`intent`, `controlCheckpoint`, and `prethemeGate` are non-null.
`prethemeCheckpoint` is null in both cases. The successful path is
byte-for-byte unchanged.

The new runtime receipt uses:

```text
tempRootParent = /private/tmp/quant-radar-ux1b-runtime-sequence6
```

No code removes or reuses the Sequence 5 runtime root.

## Acceptance criteria

### `AC-SEQ6-001` — exact predecessor import

Given the Sequence 6 package, validation imports all eight exact Sequence 5
records, proves both later leaves absent, and leaves every retained byte,
inode, mtime, size, and digest unchanged.

### `AC-SEQ6-002` — postcontrol failure terminal

Given a deterministic postcontrol `_Task9RunnerFailure`, when capture runs,
then one revoked terminal is durably published with only the intent reference,
the conservative control reason, and the original exit code; no later runner
launches.

### `AC-SEQ6-003` — pretheme failure terminal

Given a passed control checkpoint and pretheme gate followed by a deterministic
pretheme `_Task9RunnerFailure`, when capture runs, then one revoked terminal
binds exactly that three-record prefix, carries no pretheme checkpoint, and
the original exit code is returned.

### `AC-SEQ6-004` — no retry and success compatibility

Every failure stage launches once. The existing successful two-stage path
still publishes the exact passed checkpoint and terminal chain.

### `AC-SEQ6-005` — isolated system temp root

Given the Sequence 5 root still contains its historical epoch and the
Sequence 6 root is absent, Sequence 6 creates and FD-normalizes only its new
root, then uses one exclusive Sequence 6 epoch.

### `AC-SEQ6-006` — complete gates and canary

All 41 handoff tests, complete recovery target, fail-soft suites, Python 3.10
AST, tabnanny, dependency, whitespace, source-cardinality, predecessor-stat,
namespace, descriptor, and process gates pass. The exact disposable pretheme
canary then passes 81/81 with a canonical manifest and quiescent processes.

### `AC-SEQ6-007` — formal one-shot

After Tier 0 and preflight publish, a fresh process reopens the preflight.
Exactly one formal Sequence 6 capture invocation launches each stage at most
once. Success publishes a passed terminal; any runner failure publishes a
revoked terminal and preserves its nonzero exit without retry.

## Implementation checklist

- [ ] `IMPL-025`: Freeze this plan and ledger; publish Sequence 6
  authorization.
- [ ] `IMPL-026`: Add Sequence 6 namespaces and import exact Sequence 5
  failure authority.
- [ ] `IMPL-027`: Move Sequence 6 to the new absent private runtime root.
- [ ] `IMPL-028`: Add red-first postcontrol runner-failure terminal test.
- [ ] `IMPL-029`: Add red-first pretheme runner-failure terminal and no-retry
  test.
- [ ] `IMPL-030`: Implement the closed revoked-terminal path without changing
  successful behavior.
- [ ] `IMPL-031`: Run complete recovery, fail-soft, static, scope,
  predecessor, and process gates; fix every blocking review finding.
- [ ] `IMPL-032`: Run the exact 81-page disposable canary, then bootstrap,
  preflight, fresh reopen, and exactly one formal Task 9 command.

## Test specification

| Test | Observable result |
| --- | --- |
| `TEST-042` | Sequence 5 plan, ledger, six runtime records, and two absences remain exact. |
| `TEST-043` | Sequence 6 package imports the complete Sequence 5 failed prefix and failed manifest. |
| `TEST-044` | Sequence 6 uses only its absent system-temp root and retains the Sequence 5 root unchanged. |
| `TEST-045` | Postcontrol runner failure publishes the exact revoked terminal and returns the original code. |
| `TEST-046` | Pretheme runner failure publishes the exact revoked terminal and returns the original code. |
| `TEST-047` | Failure launches once; the successful two-runner path remains exact. |
| `TEST-048` | Complete recovery, fail-soft, static, source, predecessor, process, and exact 81-page canary gates pass. |
| `TEST-049` | Sequence 6 bootstrap/preflight reopen and one formal Task 9 command produce a closed terminal outcome. |

## Traceability matrix

| Requirement | Acceptance | Implementation | Tests |
| --- | --- | --- | --- |
| `REQ-006` | `AC-SEQ6-002`, `AC-SEQ6-003`, `AC-SEQ6-004`, `AC-SEQ6-007` | `IMPL-028`, `IMPL-029`, `IMPL-030`, `IMPL-032` | `TEST-045`, `TEST-046`, `TEST-047`, `TEST-049` |
| `CFR-013` | `AC-SEQ6-001` | `IMPL-025`, `IMPL-026` | `TEST-042`, `TEST-043` |
| `CFR-014` | `AC-SEQ6-005` | `IMPL-027` | `TEST-044` |
| `CFR-015` | `AC-SEQ6-004`, `AC-SEQ6-006`, `AC-SEQ6-007` | `IMPL-028`, `IMPL-029`, `IMPL-031`, `IMPL-032` | `TEST-045`, `TEST-046`, `TEST-047`, `TEST-048`, `TEST-049` |
| `CFR-016` | `AC-SEQ6-006` | `IMPL-031` | `TEST-048` |

## Commands and gates

Before the canary, Tier 0, or formal publication:

```bash
.venv/bin/python -B scripts/ui_ux_theme_handoff.py verify-python-syntax --json
.venv/bin/python -B scripts/test_ui_ux_theme_handoff.py
make ui-ux1b-recovery-tests
```

Also run the relevant API and Streamlit fail-soft suites, Python 3.10 AST,
tabnanny, dependency, whitespace, authorization-marker, source-cardinality,
predecessor-stat, new-namespace, temp-root, descriptor, and
process-quiescence checks.

The canary command is:

```bash
.venv/bin/python -B scripts/ui_ux_snapshot_matrix.py \
  --profile ux1b-full-pages \
  --phase pretheme \
  --browser chromium \
  --out-dir .claude/ui_snapshots/ux1b/sequence6-canary-20260724T110000Z \
  --no-prompt \
  --json
```

The formal order, only after an 81/81 canary pass, is:

```bash
make ui-ux1b-theme-handoff-bootstrap \
  UX1B_RECOVERY_ID=20260724T110000Z
make ui-ux1b-theme-handoff-preflight \
  UX1B_RECOVERY_ID=20260724T110000Z
.venv/bin/python -B scripts/ui_ux_theme_handoff.py verify-preflight \
  --recovery-id 20260724T110000Z --json
make ui-ux1b-recovery-postcontrol \
  UX1B_RECOVERY_ID=20260724T110000Z \
  UX1B_HANDOFF_PREFLIGHT=.claude/ui_snapshots/ux1b/recovery/theme-handoff-preflight-20260724T110000Z.json
```

The final command is the only authorized formal Task 9 capture invocation for
Sequence 6.

## Failure policy

- A failed canary blocks bootstrap. Do not rerun it. Create a capture-stack
  remediation plan that adds closed operation/cause diagnostics and rotates
  Task 6 authority.
- Any committed Sequence 6 intent burns recovery ID `20260724T110000Z`.
- A formal runner failure MUST leave a revoked terminal. Do not retry.
- A terminal-publication failure remains a new correction requiring a new ID.
- No failed or revoked record grants migration, theme, review, or root
  authority.

## Risks and rollback

- The canary adds about 163 disposable files under an excluded `.claude`
  namespace. It grants no authority and is never accepted as formal evidence.
- A new runtime root avoids deleting or trusting prior private runtime
  residue. It may remain after execution as owner-only operational state.
- Before Sequence 6 Tier 0 publication, rollback removes only uncommitted
  Sequence 6 code and authorization changes while preserving all predecessor
  evidence and unrelated dirty worktree files.
- After Tier 0 publication, Sequence 6 evidence is immutable; any correction
  requires a new accepted sequence and recovery ID.

## Review checklist

- [x] Sequence 5 formal command count is exactly one.
- [x] All eight predecessor artifacts and two absences are exact.
- [x] The unknown Playwright cause is not overstated.
- [x] The plan does not modify or rotate capture-stack authority.
- [x] No retry, sleep, timeout increase, or failure suppression is introduced.
- [x] Runner failure terminalization returns the original nonzero exit.
- [x] The successful Task 9 path remains exact.
- [x] The new runtime root is absent and disjoint.
- [x] The 81-page canary is a hard pre-bootstrap gate.
- [x] Requirement, acceptance, implementation, and test links are
  bidirectional and complete.
- [ ] Changed-code review reports no blocking issue.
- [ ] Fresh-process preflight reopen passes before the formal one-shot.

## Change history

| Version | Date | Change |
| --- | --- | --- |
| 1.0 | 2026-07-24 | Accepted after confirming exact predecessor evidence, schema compatibility, source/Tier-0 exclusion of the disposable canary, cardinalities, and absence of every Sequence 6 namespace. |
| 0.1 | 2026-07-24 | Drafted failure-terminal containment, isolated runtime, and exact 81-page canary gates after the Sequence 5 pretheme worker failure. |
