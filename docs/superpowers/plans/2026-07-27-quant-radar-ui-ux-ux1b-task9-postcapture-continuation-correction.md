# Quant Radar UX-1B Task 9 Post-Capture Continuation Correction

## Document information

| Field | Value |
| --- | --- |
| Type | Corrective implementation plan and execution checklist |
| Version | `1.0-reviewed` |
| Status | Blocking-issue review passed; implementation authorization pending |
| Authorization | Repository maintainer authorized creation and review of Sequence 9 only |
| Author | Codex |
| Reviewer / approver | Repository maintainer |
| Audience | Maintainers, implementers, independent code reviewers, and visual reviewers |
| Sequence | `9` |
| Capture recovery ID | `20260725T080000Z` (immutable Sequence 8 lineage) |
| Continuation ID | `20260726T210000Z` |
| Continuation Tier ID | `20260726T211000Z` |
| Imported predecessor | Sequence 8 plan, ledger, preflight, complete Task 9 chain, passed terminal, manifests, canary, and runtime receipt |
| Parent execution plan | `docs/superpowers/plans/2026-07-20-quant-radar-ui-ux-ux1b-formal-theme-handoff-replacement.md` |
| Related ledger | `docs/superpowers/plans/2026-07-27-quant-radar-ui-ux-ux1b-task9-postcapture-continuation-correction.traceability.yaml` |

## Executive summary

Sequence 8 completed the browser work successfully. Its formal Task 9
terminal is `passed`, the post-control manifest is `36 / 36`, the canonical
pretheme manifest is `81 / 81`, and the disposable canary is `81 / 81`.
Those records are valid and must not be repeated.

The workflow is blocked after capture for two independent reasons:

1. `ui-ux1b-recovery-verify-migration` derives both before and after paths
   from `UX1B_RECOVERY_ID`. The authenticated before manifests actually belong
   to Task 6 recovery `20260719T211915Z`; the after manifests belong to
   Sequence 8 recovery `20260725T080000Z`.
2. The CLI advertises the rest of the handoff/theme lifecycle, but production
   dispatch maps all 18 post-capture commands to
   `_handle_unavailable_public_command`, which exits with contract failure.

Sequence 9 fixes the lineage and production-dispatch gaps without changing or
rerunning capture. It introduces a separate post-capture continuation
authority, binds the exact passed Sequence 8 terminal, implements every
remaining public lifecycle handler before the continuation preflight is
frozen, then resumes the parent plan at its migration-review boundary.

## Verified starting state

The following records were reopened during planning:

| Artifact | SHA-256 | Size |
| --- | --- | ---: |
| Sequence 8 plan | `c10f576b145ca6ab2833ec4795336421337b45cf80df11b2fed24b64af2ce5ec` | `22674` |
| Sequence 8 ledger | `adf7184f7249a3f0bd73a874bf2ddc6846e3fcfceb4b0a30df0099fa66022dc4` | `5602` |
| Sequence 8 authorization document | `9c82f8fe19d270515caeaac24d300b8e42f3ac2751e005fe9a818c94f1581c34` | `24979` |
| Sequence 8 preflight | `2b7abf239593186bcedf967d2f00313a5d77472cff2bd0ee67f3c5e753f325b5` | `128473` |
| Sequence 8 terminal | `07d2c953a193387d9a4824a55a20665ea1492ad3986ab5460c8f7f2566d3f2b2` | `11551` |
| Sequence 8 post-control manifest | `c1509a74c842eb0cafc84f01caa7e3ff4e441ac5f90cb565d4d532de8b284574` | `35103` |
| Sequence 8 canonical pretheme manifest | `60a9a736275af898ef15982ae5763484148e1b51dec2e72f8c477e6599db287c` | `70149` |
| Sequence 8 disposable canary manifest | `467ae3e820ada95dfe7479107d1efe7a58df3c0f11abddf798c8b49171b08700` | `70149` |
| Task 6 page manifest | `a72aa7cac95bfbd70b23a2033c49a0d03aa500204bd66ec738b757c2295e6404` | `70151` |
| Task 6 control manifest | `06f7320b0d56e54d584399e281a307a713b23a349207ac7b35b6bd1ee14154be` | `35100` |

The Sequence 8 terminal is canonical, status `passed`, recovery ID
`20260725T080000Z`, and binds all four earlier lifecycle records. Its two
manifests have exact namespace counts `73` and `163`. The formal runtime tree
`/private/tmp/qr-ux1b-s8` exists only as the expected empty `0 KB` directory
structure. No Sequence 9 namespace exists.

The following forward records are absent and remain eligible:

```text
.claude/ui_snapshots/ux1b/recovery/control-migration-20260725T080000Z.json
.claude/ui_snapshots/ux1b/recovery/control-migration-review-packet-20260725T080000Z.json
.claude/ui_snapshots/ux1b/review-intake/control-migration-20260725T080000Z.json
.claude/ui_snapshots/ux1b/recovery/control-migration-manual-review-20260725T080000Z.json
.claude/ui_snapshots/ux1b/recovery/theme-handoff-candidate-20260725T080000Z.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json
```

## Problem statement

The passed capture preflight froze the exact code that produced the evidence.
Editing that code and then treating the old preflight as current authority
would be false provenance. Repeating capture under a new recovery ID would
also be wrong because Sequence 8 is terminal and one-shot.

The correction therefore needs a new authority boundary after capture:

```text
Task 6 before evidence
        │
        ├── exact historical manifests: 20260719T211915Z
        │
Sequence 8 capture authority
        │
        ├── passed terminal and after manifests: 20260725T080000Z
        │
Sequence 9 continuation authority
        │
        ├── corrected coordinator source: 20260726T210000Z
        │
        └── migration review → immutable v2 root → parent Tasks 6–9
```

The three identities are not aliases. The comparator must cross the first two;
the continuation preflight must bind the second and authorize only the third.

## Scope

### In scope

- Add a separate Sequence 9 continuation authorization document and parser.
- Add fixed continuation bootstrap, preflight, and verification commands.
- Import and continuously reauthenticate the exact Sequence 8 passed chain.
- Move migration comparison behind the descriptor-bound coordinator.
- Bind the comparator to the exact Task 6 before manifests and Sequence 8
  after manifests; do not derive before paths from the after recovery ID.
- Implement production handlers for all 18 currently unavailable public
  lifecycle commands, not only the four commands immediately needed for root.
- Retain the existing CLI schemas, review schemas, root v2 schema, batch/apply,
  theme-state, posttheme, and closure primitives where their contracts are
  already complete.
- Add only the continuation arguments needed to authenticate post-capture
  lineage.
- Wire Make to the coordinator and preserve nonzero exit propagation.
- Produce the migration machine report and review packet, then pause for an
  independently authored 117-item intake.
- After accepted intake, prepare, verify, publish, and pristine-verify the
  immutable v2 root.
- Leave the full parent Task 3–5 lifecycle executable without another
  unavailable-handler blocker.

### Non-goals

- Do not rerun the Sequence 8 canary.
- Do not call `capture-task9` or `reconcile-task9` for Sequence 8.
- Do not create a second Task 9 recovery ID, intent, checkpoint, terminal, or
  capture output.
- Do not edit, replace, relink, chmod, truncate, or delete any Sequence 8
  evidence.
- Do not fabricate, prefill, or self-approve any external review intake.
- Do not apply the semantic UI theme as part of the correction implementation.
  Theme application remains parent-plan Task 6 after root publication.
- Do not redesign UI/UX in this sequence.
- Do not change capture-stack members, browser timeouts, path budgets,
  sandbox rules, process-family rules, API contracts, Streamlit behavior, or
  artifact fail-soft behavior.
- Do not clean, reset, or absorb unrelated dirty-worktree changes.

## Fixed Sequence 9 namespace

```text
Capture recovery ID:    20260725T080000Z
Continuation ID:        20260726T210000Z
Continuation Tier ID:   20260726T211000Z
Continuation lease:     .claude/ui_snapshots/ux1b/recovery/.continuation-20260726T210000Z.lease
Continuation preflight: .claude/ui_snapshots/ux1b/recovery/theme-handoff-continuation-preflight-20260726T210000Z.json
Continuation bundle:    .claude/ui_snapshots/ux1b/recovery/theme-handoff-continuation-prechange-20260726T211000Z/
```

The Sequence 9 plan, ledger, authorization document, Tier record, lease, and
preflight are new. All Sequence 8 paths remain at their original names.

## Continuation authority design

### Separate authorization record

Create:

```text
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-continuation-seq9.md
```

It contains exactly one closed
`UX1B_FORMAL_HANDOFF_CONTINUATION_V1` marker. It references:

- this accepted plan and canonical traceability ledger;
- the existing Sequence 8 authorization document without changing it;
- the exact Sequence 8 plan, ledger, preflight, lifecycle records, terminal,
  three manifests, and passed canary;
- the fixed capture recovery ID, continuation ID, and continuation Tier ID;
- the exact allowed command family; and
- the explicit prohibition on capture or reconciliation.

The existing `UX1B_FORMAL_HANDOFF_AUTHORIZATION_V2` block remains byte-exact.
The continuation parser rejects duplicate, legacy, future, malformed,
noncanonical, mismatched-ID, wrong-predecessor, or expanded-command markers.
The marker body is canonical JSON with the exact closed keys
`schemaVersion,sequence,continuationId,captureRecoveryId,tierId,plan,
traceability,predecessorAuthorization,allowedCommands,forbiddenCommands,
cardinalities,precedence`. `cardinalities` records exact package, authority,
live, mirror, and supplemental counts plus a membership digest derived from
the explicit closed path sets after implementation. These values are generated
before final changed-code review and are accepted with the marker; no
Sequence 8 count is copied or guessed.

`allowedCommands` is the exact sorted set of the four new continuation
commands plus the 18 post-capture commands in the production-handler table
below. `forbiddenCommands` is exactly `bootstrap,preflight,verify-preflight,
capture-task9,reconcile-task9`. The read-only
`verify-python-syntax` command grants no lifecycle authority and belongs to
neither set.

### Tier and preflight

Add these public commands:

```text
bootstrap-continuation
preflight-continuation
verify-continuation-preflight
compare-control-migration
```

The first three require both `--continuation-id 20260726T210000Z` and
`--capture-recovery-id 20260725T080000Z`. Bootstrap reuses the retained global
handoff lock, creates a distinct continuation lease, and publishes exact
Sequence 9 prechange/rollback records and an archive of the corrected
coordinator, test, Make, and continuation-authorization bytes.

The canonical continuation preflight schema is
`quant-radar-ui-ux-formal-handoff-continuation-preflight/v1`. It binds:

- the Sequence 9 authorization record, plan, and ledger;
- the Sequence 8 authorization, preflight, full terminal chain, capture
  manifests, canary, runtime receipt, and empty runtime tree;
- the exact Task 6 page/control manifests;
- capture-stack and historical-selector digests;
- current full source and supplemental projections after all Sequence 9 code
  changes;
- exact fixed source files and Make coordinator contracts;
- the continuation lock/lease and descriptor budget;
- the existing six forward root/migration leaves plus the review-intake
  directory state as absent/safely owned according to the closed policy; and
- an authenticated inventory and closed derivation policy for batch,
  theme-state, posttheme, and closure namespaces. Because their lineage IDs
  are intentionally selected only after root publication, their exact path
  absence is checked by the later lineage initializer, not guessed by this
  preflight.

It grants no capture capability. Calling either Task 9 capture command after a
passed imported terminal remains a contract failure with zero writes.

Its exact top-level keys are
`schemaVersion,status,continuationId,captureRecoveryId,authorizationRecord,
replacementPlan,traceability,predecessor,task6,captureStack,
historicalSelectorModes,sourceProjection,supplementalProjection,
runtimeReceipt,makeContract,namespaceInventory,eligibleDestinations,
descriptorBudget,lease`. Unknown, missing, reordered-set, or wrong-type fields
are rejected before publication.

### Root v2 preservation

The final root remains
`quant-radar-ui-ux-formal-theme-handoff/v2` at:

```text
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json
```

Its top-level schema does not change. Its `recoveryId` remains the Sequence 8
capture recovery ID. Its `authorizationRecord`, `replacementPlan`, and
`traceability` references identify Sequence 9; `baseDraft` remains the parent
replacement plan. Its `preflight` reference points to the Sequence 9
continuation preflight, which in turn binds the original capture
authorization, preflight, and terminal. Its current source/supplemental
projections come from the continuation preflight. Candidate and consumer
validators must traverse this chain and reject a direct substitution of
either preflight.

## Comparator correction

Remove the direct `scripts/ui_ux_evidence.py compare-control-migration` Make
recipe. The new coordinator command accepts identifiers only, opens every
input with descriptor-bound, no-follow, exact-record checks, and uses these
closed inputs:

| Role | Exact source |
| --- | --- |
| Before pages | `precontrol-pages-20260719T211915Z/manifest.json` |
| Before controls | `precontrol-controls-20260719T211915Z/manifest.json` |
| After pages | `canonical-pretheme-20260725T080000Z/manifest.json` |
| After controls | `postcontrol-controls-20260725T080000Z/manifest.json` |
| Authority | Sequence 9 continuation preflight |
| Output | `control-migration-20260725T080000Z.json` |

The CLI exposes no arbitrary before/after path flags. A wrong Task 6 ID,
wrong capture ID, missing/changed manifest, stale continuation preflight,
output collision, source drift, or extra flag fails before publication.

The exact continuation-argument boundary is:

| Command family | Required lineage arguments |
| --- | --- |
| `bootstrap-continuation`, `preflight-continuation`, `verify-continuation-preflight`, `compare-control-migration` | `--capture-recovery-id` and `--continuation-id` |
| control-migration `prepare-review` / `publish-review` | `--recovery-id` and `--continuation-id` |
| `prepare-handoff`, `verify-handoff-candidate`, `publish-handoff` | `--recovery-id` and `--continuation-id` |
| `verify-handoff --require-pristine` | no caller-supplied lineage; reopen the one fixed root and traverse its authorities |
| theme batch/state/posttheme/final commands | their existing batch/run arguments; traverse the published root |

## Production handler closure

The production registry must map every command in `PUBLIC_COMMANDS` to a
specific handler. `_handle_unavailable_public_command` may remain only as a
test sentinel and must not appear as any production registry value.

The correction covers all currently unavailable families:

| Family | Commands |
| --- | --- |
| Migration review | `prepare-review`, `publish-review` |
| Root handoff | `prepare-handoff`, `verify-handoff-candidate`, `publish-handoff`, `verify-handoff` |
| Theme batch | `init-theme-batch`, `seal-theme-batch`, `verify-theme-batch-ready`, `apply-theme-batch`, `reconcile-theme-batch`, `verify-theme-batch-applied` |
| Theme states | `capture-theme-states`, `reconcile-theme-states`, `close-theme-states` |
| Posttheme | `capture-posttheme`, `reconcile-posttheme`, `finalize-theme` |

Each handler:

- validates an exact closed argument set;
- opens the production workspace and required authorities by retained
  descriptors;
- acquires the existing global lock and the correct lineage lease;
- invokes the existing contract primitive, or adds the missing orchestration
  needed to call that primitive;
- maps only the documented `0/3/4/5/6/7/8/9/130` exits;
- emits the normal public success envelope only after reopening the committed
  destination; and
- creates no record on grammar, contract, collision, busy, unavailable, or
  stale-authority failure.

Adding a handler name without executing its real descriptor-bound transition
does not satisfy this plan.

## Requirements

### `REQ-009` — resume after passed capture without recapture

The accepted parent flow must resume from the exact Sequence 8 passed terminal
through migration review and root publication without launching or mutating
capture.

### `CFR-026` — immutable Sequence 8 predecessor

Every imported Sequence 8 record and the Task 6 manifests remain exact in
content and filesystem identity. Sequence 8 has no retry or reconciliation
path.

### `CFR-027` — dual-identity continuation authority

Capture recovery and post-capture continuation IDs are distinct, fixed,
explicitly bound, and cannot be substituted or inferred from one another.

### `CFR-028` — exact cross-recovery comparison

The comparator authenticates Task 6 before evidence and Sequence 8 after
evidence from fixed descriptor-bound records, not from a shared string
template.

### `CFR-029` — complete public dispatch

Every declared public lifecycle command has a real production handler,
closed arguments, documented exit mapping, and destination reopen.

### `CFR-030` — independent review boundary

Machine packet preparation and human review publication are separate. Missing,
malformed, rejected, incomplete, wrong-reviewer-metadata, or unresolved intake
blocks root/batch/state/final publication. Claimed reviewer identity is an
external assertion, not a coordinator-authenticated identity proof.

### `CFR-031` — root and downstream readiness

The immutable v2 root binds continuation provenance, and every parent Task 6–9
command is executable without another unavailable-handler stop.

### `CFR-032` — compatibility and fail-closed behavior

Capture, API, Streamlit, artifact-loader, sandbox, process, path-budget, and
fail-soft contracts remain exact; every stale, partial, collided, or unknown
state fails without forward mutation.

### `CFR-033` — scope, rollback, and traceability closure

Only planned files and new owned namespaces change. Unrelated dirty state and
all historical evidence remain untouched; plan, implementation, acceptance,
tests, and BDD scenarios are fully traceable.

## Acceptance criteria

### `AC-SEQ9-001` — predecessor immutability (CRITICAL)

Given the exact Sequence 8 evidence set, when any continuation command runs,
then all imported hashes, sizes, modes, owners, link counts, inodes, terminal
relationships, namespace counts, and runtime receipt reopen unchanged; no
capture/reconcile process launches.

### `AC-SEQ9-002` — continuation preflight (CRITICAL)

Given accepted Sequence 9 plan/ledger and absent Sequence 9 Tier paths, when
bootstrap and preflight run, then one canonical continuation authority freezes
the corrected code and exact predecessor. Any ID, marker, source, predecessor,
lease, descriptor, runtime, or future-destination mutation publishes nothing.

### `AC-SEQ9-003` — exact migration comparison (CRITICAL)

Given the exact Task 6 and Sequence 8 manifests, when comparison runs, then it
publishes one canonical migration report with `comparedCaptures:117` using the
fixed cross-ID pairing. A same-ID before path, caller path injection, missing
capture, changed artifact, or collision fails without replacing output.

### `AC-SEQ9-004` — complete production dispatch (CRITICAL)

Given the closed public command set, when production handlers are inspected
and each command is exercised in owned fixtures, then no registry value is the
unavailable sentinel and every handler reaches its real transition with exact
arguments, descriptors, locks, exits, and publication rules.

### `AC-SEQ9-005` — external review separation (HIGH)

Given a published 117-item packet, when no external accepted intake with the
exact independent-reviewer metadata exists, then publication and root
preparation stop. Only an exact accepted copy with all items and no unresolved
finding may publish the manual review. Reviewer identity remains an external
assertion, not a cryptographic proof made by the coordinator.

### `AC-SEQ9-006` — immutable v2 root (HIGH)

Given exact continuation preflight, passed terminal, migration report, and
accepted review, when root preparation/publication runs, then a candidate is
reopened, one immutable v2 root is published, and a fresh process verifies it
pristine; no theme source changes beforehand.

### `AC-SEQ9-007` — downstream command readiness (HIGH)

Given the published root and owned test lineages, when every theme-batch,
theme-state, posttheme, and finalization command is exercised through success,
busy, collision, interruption, uncertain, and reconciliation fixtures, then
each reaches its contracted state transition and none returns the placeholder
contract failure.

### `AC-SEQ9-008` — compatibility preservation (HIGH)

Given current capture, fail-soft, security, schema, Make, and source contracts,
when Sequence 9 changes and regressions run, then all unchanged suites pass,
the nine-member capture stack is byte-exact, direct runner Make calls remain
absent, and no API/UI behavior changes.

### `AC-SEQ9-009` — scope and closure (HIGH)

Given the dirty worktree and fixed plan, when the actual diff and new evidence
are reviewed, then only planned files/namespaces are explained, unrelated
fingerprints are unchanged, bidirectional traceability is 10000 bps, all
blocking findings are closed, and unavailable external reviews remain explicit
pause gates rather than fabricated completion.

## BDD scenario specification

Each CRITICAL criterion has five adversarial scenarios and each HIGH criterion
has three.

| Scenario | Given / When / Then |
| --- | --- |
| `SC-SEQ9-001A` | Given exact predecessor / verify continuation / then all exact records reopen. |
| `SC-SEQ9-001B` | Given changed terminal byte / verify / then exit contract and write nothing. |
| `SC-SEQ9-001C` | Given passed terminal / call capture / then reject before runner launch. |
| `SC-SEQ9-001D` | Given passed terminal / call reconcile / then reject before lifecycle write. |
| `SC-SEQ9-001E` | Given empty Sequence 8 runtime tree / verify / then preserve every directory identity and emptiness. |
| `SC-SEQ9-002A` | Given absent continuation Tier / bootstrap then preflight / then publish one reopened canonical chain. |
| `SC-SEQ9-002B` | Given wrong capture or continuation ID / bootstrap / then publish nothing. |
| `SC-SEQ9-002C` | Given malformed or duplicate continuation marker / preflight / then reject. |
| `SC-SEQ9-002D` | Given source drift after freeze / verify preflight / then reject without downstream writes. |
| `SC-SEQ9-002E` | Given concurrent bootstrap / run twice / then exactly one owner wins and collision is preserved. |
| `SC-SEQ9-003A` | Given fixed four manifests / compare / then publish a canonical report with `comparedCaptures:117`. |
| `SC-SEQ9-003B` | Given before paths derived from Sequence 8 ID / compare / then reject before output. |
| `SC-SEQ9-003C` | Given a changed Task 6 manifest / compare / then reject exact authority mismatch. |
| `SC-SEQ9-003D` | Given caller-supplied path or extra flag / parse / then grammar fails with no output. |
| `SC-SEQ9-003E` | Given existing output / compare / then collision preserves original inode and bytes. |
| `SC-SEQ9-004A` | Given production registry / inspect / then every public command has a non-sentinel callable. |
| `SC-SEQ9-004B` | Given each success fixture / dispatch / then its real transition and reopened destination are observed. |
| `SC-SEQ9-004C` | Given busy/collision/uncertain fixtures / dispatch / then exact nonzero exits propagate. |
| `SC-SEQ9-004D` | Given wrong identifier combinations / dispatch / then argument validation fails before workspace mutation. |
| `SC-SEQ9-004E` | Given a handler that only returns success / conformance test / then reject because no transition/destination occurred. |
| `SC-SEQ9-005A` | Given packet but no intake / publish review / then stop with no manual-review file. |
| `SC-SEQ9-005B` | Given incomplete/rejected intake or wrong reviewer metadata / publish / then reject. |
| `SC-SEQ9-005C` | Given exact independently authored accepted intake / publish / then exact-copy and reopen it. |
| `SC-SEQ9-006A` | Given all accepted inputs / publish root / then one immutable v2 root passes fresh pristine verification. |
| `SC-SEQ9-006B` | Given stale continuation preflight / prepare root / then reject before candidate. |
| `SC-SEQ9-006C` | Given any theme source changed before root / publish / then source projection mismatch blocks. |
| `SC-SEQ9-007A` | Given root and owned fixtures / run every downstream success path / then each reaches its contracted terminal. |
| `SC-SEQ9-007B` | Given active lineage lease / run competitor / then exit busy and write nothing. |
| `SC-SEQ9-007C` | Given interrupted partial state / reconcile / then only the documented safe forward/rollback/refusal branch occurs. |
| `SC-SEQ9-008A` | Given Sequence 9 diff / run capture and fail-soft suites / then all unchanged contracts pass. |
| `SC-SEQ9-008B` | Given Make targets / inspect recipes / then no direct capture runner and all nonzero exits propagate. |
| `SC-SEQ9-008C` | Given capture-stack digest set / compare / then all nine members remain byte-exact. |
| `SC-SEQ9-009A` | Given pre-change dirty snapshot / compare post-change / then unrelated paths are unchanged. |
| `SC-SEQ9-009B` | Given plan ledger / validate / then every edge is reciprocal, with no gaps/orphans. |
| `SC-SEQ9-009C` | Given missing external review / report status / then mark explicit pause, never passed completion. |

## Affected files

### Planned implementation changes

- `scripts/ui_ux_theme_handoff.py`
- `scripts/test_ui_ux_theme_handoff.py`
- `Makefile`
- `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-continuation-seq9.md`

### Plan, traceability, and journals

- this plan;
- its sibling traceability ledger;
- `.agents/scribe.md`;
- `.agents/attest.md`; and
- `.agents/PROJECT.md`.

### Explicitly unchanged

- every Sequence 8 Tier 0, preflight, lifecycle, manifest, canary, and runtime
  record;
- `scripts/ui_ux_evidence.py` and every other capture-stack member;
- FastAPI, Streamlit, and artifact-loader source;
- `.streamlit/config.toml`, `app.py`, `ui/_design.py`, `requirements.txt`, and
  classification until a later reviewed theme batch is applied; and
- unrelated current worktree changes.

## Implementation checklist

- [ ] `IMPL-048`: Add fixed Sequence 9 constants, separate continuation
  authorization parser, predecessor references, and schema validation without
  altering the Sequence 8 authorization record.
- [ ] `IMPL-049`: Add descriptor-bound continuation bootstrap, preflight, and
  verification with global lock, distinct lease, exact Tier paths, source
  projections, imported terminal validation, and no capture capability.
- [ ] `IMPL-050`: Add the coordinator-owned cross-recovery migration
  comparator and canonical report publisher.
- [ ] `IMPL-051`: Add migration review and root candidate/publication/
  consumer production handlers, including continuation arguments and exact
  external-intake handling.
- [ ] `IMPL-052`: Add real production handlers for theme batch init, seal,
  review readiness, apply, reconcile, and applied verification.
- [ ] `IMPL-053`: Add real production handlers for theme-state and posttheme
  capture/reconcile/review closure/finalization.
- [ ] `IMPL-054`: Replace the direct comparator Make recipe, add continuation
  targets/variables, update coordinator contract validation, and preserve
  argument order/nonzero propagation.
- [ ] `IMPL-055`: Add red-first unit, schema, registry, descriptor, fault,
  concurrency, mutation, scope, and compatibility tests for all acceptance
  criteria and BDD scenarios.
- [ ] `IMPL-056`: Run implementation gates, freeze continuation Tier/preflight,
  publish migration report/packet, pause for external intake, then publish and
  pristine-verify root only after accepted intake.

## Test specification

| Test | Verifies |
| --- | --- |
| `TEST-067` | Sequence 8 and Task 6 exact records, identity, no-retry, and no-launch invariants. |
| `TEST-068` | Continuation marker/parser, dual IDs, schema, predecessor chain, and root traversal. |
| `TEST-069` | Bootstrap/preflight single-winner, collisions, descriptor limits, lease, future absence, and zero-side-effect failures. |
| `TEST-070` | Exact cross-ID comparator inputs, `comparedCaptures:117`, path injection refusal, canonical publisher, and collision preservation. |
| `TEST-071` | Exact public command/parser/handler registry and real-transition coverage; no production sentinel. |
| `TEST-072` | Review packet/intake separation, exact independent accepted copy, rejection and unresolved-finding refusal. |
| `TEST-073` | Root candidate, v2 publication, continuation traversal, source binding, and fresh pristine consumer. |
| `TEST-074` | Theme-batch handler success/failure/concurrency/apply/reconcile/applied-receipt matrices. |
| `TEST-075` | Theme-state/posttheme handler capture/reconcile/review/attestation/finalization matrices. |
| `TEST-076` | Full capture, fail-soft API/Streamlit/artifact-loader, Make, source, and frozen-stack compatibility. |
| `TEST-077` | Public exits, lost-response, interruption, busy, collision, stale authority, partial state, and no false success. |
| `TEST-078` | Plan/diff scope, canonical ledger, reciprocal traceability, BDD inventory, schemas, and no unexplained drift. |
| `TEST-079` | Real continuation Tier/preflight, migration report/packet pause, accepted-review root publication, and pristine verification. |

## Implementation sequence and gates

### Phase 0 — re-open and snapshot

- Reopen every record in the verified-starting-state table.
- Capture a read-only fingerprint of all dirty paths before implementation.
- Prove all Sequence 9 paths and six downstream root/migration paths are
  absent.
- Prove no lifecycle-owned process or lease is active; ambient user Chrome and
  browser tooling are not treated as lifecycle ownership.

**Gate:** any predecessor drift, partial Sequence 9 namespace, or owned process
blocks implementation.

### Phase 1 — red tests and continuation contracts

- Add failing tests for all four new commands, dual-ID substitution, the
  separate marker, predecessor mutation, old capture-command refusal, registry
  completeness, and exact Make wiring.
- Add schemas and closed path sets before publication code.
- Keep the old capture preflight validator available only for imported capture
  validation; add a distinct continuation validator.

**Gate:** tests fail for the intended missing behavior, not fixture errors.

### Phase 2 — implement all correction code

- Complete `IMPL-048` through `IMPL-054`.
- Create the Sequence 9 continuation authorization document as part of
  `IMPL-048`, before final code review and source freezing.
- Populate its cardinalities and membership digest from the explicit final
  path sets, then make those exact values mutation-tested inputs to the final
  review; do not accept a count derived from an open glob.
- Route existing complete primitives through descriptor-bound public
  orchestration; implement only the missing glue/transition logic.
- Do not create any formal Sequence 9 evidence while source is changing.
- Run focused tests after each handler family.

**Gate:** every public registry value is a specific production handler and all
owned-fixture success/failure matrices pass.

### Phase 3 — compatibility and review

- Complete `IMPL-055`.
- Run the focused coordinator suite, complete recovery suite, capture-stack
  hashes, Python syntax/3.10 AST/tabnanny, dependency and whitespace gates.
- Run selected API, artifact-loader, Streamlit fail-soft, UI contract,
  component, navigation, UX-0/UX-1A, legacy, and Make propagation suites.
- Compare actual diff to this plan and the Phase 0 dirty fingerprint.
- Review changed code for bugs, regressions, missing tests, unsafe
  publication, and maintainability. Fix blockers before formal evidence.

**Gate:** all relevant checks pass; no unexplained scope drift remains.

### Phase 4 — freeze continuation authority

- Obtain maintainer acceptance of the exact already-reviewed continuation
  authorization document, then reopen it without editing.
- Run `bootstrap-continuation` once and reopen the full Tier.
- Run `preflight-continuation` once and verify it in a fresh process.
- Reopen Sequence 8 again and prove it is unchanged.

**Gate:** the continuation preflight passes and freezes the exact final code;
no source edit is allowed afterward without a new correction sequence.

### Phase 5 — migration review boundary

- Run `compare-control-migration` through Make.
- Reopen the exact report and require `comparedCaptures:117`.
- Run `prepare-review --kind control-migration`.
- Reopen the exact 117-item packet and stop.
- An independent reviewer authors the intake outside the coordinator.

**Gate:** missing accepted intake is an expected external pause, not
permission to synthesize one or continue.

### Phase 6 — root closure after external acceptance

- Publish and reopen the exact accepted review.
- Prepare and verify the root candidate.
- Publish the immutable v2 root.
- Run `verify-handoff --require-pristine` in a fresh process.
- Prove the five future theme-change files still match pretheme bytes.

**Gate:** immutable v2 root exists and is pristine before parent Task 6.

### Phase 7 — hand back to parent plan

- Select fresh explicit theme batch/run IDs only after the root exists.
- Continue parent replacement plan Tasks 6–9.
- Use the now-wired handlers; each independent code/visual review remains a
  mandatory external pause.

**Gate:** Sequence 9 closes the infrastructure blocker; it does not waive any
parent review or evidence gate.

## Verification commands

Implementation must run at least:

```bash
.venv/bin/python -B scripts/test_ui_ux_theme_handoff.py
make ui-ux1b-recovery-tests
.venv/bin/python -B scripts/test_artifact_loader.py
.venv/bin/python -B scripts/test_api.py
.venv/bin/python -B scripts/test_ui_ux1a_safety.py
.venv/bin/python -B scripts/test_ui_ux_components.py
.venv/bin/python -B scripts/test_ui_ux_contract.py
.venv/bin/python -B scripts/test_dashboard_navigation.py
make ui-ux1b-legacy
.venv/bin/python -B scripts/ui_ux_theme_handoff.py verify-python-syntax --json
.venv/bin/python -B -m tabnanny scripts/ui_ux_theme_handoff.py scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -m pip check
git diff --check
```

Changed Python must parse with `ast.parse(..., feature_version=(3, 10))`.
The implementation review must report any unavailable command or suite and
must not claim completion from unrun checks.

The new continuation command shape is:

```bash
make ui-ux1b-theme-handoff-continuation-bootstrap \
  UX1B_RECOVERY_ID=20260725T080000Z \
  UX1B_CONTINUATION_ID=20260726T210000Z

make ui-ux1b-theme-handoff-continuation-preflight \
  UX1B_RECOVERY_ID=20260725T080000Z \
  UX1B_CONTINUATION_ID=20260726T210000Z

.venv/bin/python -B scripts/ui_ux_theme_handoff.py \
  verify-continuation-preflight \
  --capture-recovery-id 20260725T080000Z \
  --continuation-id 20260726T210000Z --json

make ui-ux1b-recovery-verify-migration \
  UX1B_RECOVERY_ID=20260725T080000Z \
  UX1B_CONTINUATION_ID=20260726T210000Z
```

There is deliberately no Sequence 9 capture command.

## Failure and pause policy

- Any Sequence 8 mismatch blocks all continuation work.
- A continuation bootstrap/preflight collision is never deleted or overwritten.
- Once the continuation preflight is committed, source drift requires a new
  accepted correction; the preflight is not regenerated in place.
- Comparator, packet, review, candidate, and root publishers are create-once
  and preserve collisions.
- Missing external review pauses the plan. Rejected review returns to a new
  corrected candidate/lineage according to the parent contract; it is not
  changed to accepted.
- A lost response is reconciled only by reopening the expected exact record.
- Unknown, partial, wrong-owner, wrong-mode, hardlinked, symlink, or changed
  evidence never grants cleanup, retry, or forward authority.
- No failed, stale, retired, partial, or review-required record grants root or
  theme authority.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Old passed preflight is incorrectly reused for changed code | Add a separate continuation preflight and make root traverse both authorities. |
| Recapture erases at-most-once provenance | Explicitly reject both capture commands after the passed terminal; no new recovery ID. |
| Comparator silently compares nonexistent same-ID before paths | Remove arbitrary/direct Make comparison; bind exact Task 6 constants. |
| Only immediate handlers are fixed and the next phase blocks again | Require every production public command to have a real handler before freezing continuation preflight. |
| A wrapper returns success without doing work | Test transition calls and reopened destination, not only function identity or exit code. |
| Coordinator manufactures human approval | Separate packet from intake; require exact independent-reviewer metadata and complete accepted items; treat identity as an external assertion rather than cryptographic proof. |
| Root schema is accidentally forked | Keep v2 top-level schema; bind continuation through its preflight chain. |
| Dirty worktree changes are overwritten or absorbed | Fingerprint before work, edit only planned files, compare actual diff, never reset/clean. |
| API or Streamlit becomes less fail-soft | Run targeted fail-soft suites; no API/UI source is in scope. |

## Rollback

- Before continuation Tier publication, revert only Sequence 9 implementation
  edits and newly created Sequence 9 files; preserve unrelated dirty work and
  all historical records.
- After Tier publication, Tier records, lock, and lease are retained evidence.
  No destructive Git command is authorized.
- Before root publication, no theme source has changed, so rollback is limited
  to refusing forward work and preserving evidence.
- After root publication, parent-plan tiered rollback rules apply to later
  theme batches; the root and Sequence 8/9 authorities remain immutable.

## Blocking-issue review

### Review iteration 1 — old preflight cannot authorize changed code

- **Finding:** Directly wiring handlers after Sequence 8 would make the root
  consume code not frozen by the capture preflight.
- **Resolution:** Add a post-capture continuation authorization and preflight;
  root traverses it back to the exact capture preflight and terminal.
- **Status:** Closed.

### Review iteration 2 — a new recovery would violate one-shot capture

- **Finding:** Treating Sequence 9 as a new Task 9 recovery would invite a
  second browser capture and duplicate evidence.
- **Resolution:** Keep capture recovery ID fixed, use a separate continuation
  ID/lease/schema, and expose no Sequence 9 capture command.
- **Status:** Closed.

### Review iteration 3 — fixing only root handlers repeats the blocker

- **Finding:** Four immediate handler fixes would allow root publication but
  stop again at theme batch/state/posttheme commands.
- **Resolution:** Complete all 18 currently unavailable production handlers
  and their fixture matrices before continuation preflight.
- **Status:** Closed.

### Review iteration 4 — comparator lineage is ambiguous

- **Finding:** One `UX1B_RECOVERY_ID` cannot name both Task 6 before evidence
  and Sequence 8 after evidence.
- **Resolution:** Coordinator owns four fixed manifest references; caller
  provides no artifact paths and the report retains the Sequence 8 output ID.
- **Status:** Closed.

### Review iteration 5 — authorization-document mutation would damage history

- **Finding:** Replacing or appending the existing V2 marker would make the
  live Sequence 8 authorization document differ from the captured authority.
- **Resolution:** Preserve it byte-for-byte and create a separate,
  narrowly-scoped Sequence 9 continuation document and marker.
- **Status:** Closed.

### Review iteration 6 — external review cannot be implemented by the agent

- **Finding:** The 117-item intake is a human/independent decision, not a
  generated implementation artifact.
- **Resolution:** Make packet publication a terminal execution pause; continue
  only after exact independently authored accepted intake exists.
- **Status:** Closed as a planned external gate.

### Review iteration 7 — unverifiable planning claims

- **Finding:** A preflight cannot enumerate absent paths for lineage IDs that
  have not been selected, coordinator bytes cannot prove the real-world
  identity of a reviewer, and adding the authorization document after code
  review would leave it unreviewed.
- **Resolution:** Freeze a closed namespace inventory/derivation policy and
  check exact absence in each later initializer; validate exact
  independent-reviewer metadata while documenting identity as an external
  assertion; create the authorization document in Phase 2 and review it in
  Phase 3 before acceptance/freezing.
- **Status:** Closed.

### Review iteration 8 — schema, argument, and count ambiguity

- **Finding:** The draft did not close the continuation schema keys or specify
  which commands accept continuation IDs, and it described the comparator
  report itself as a 117-item packet.
- **Resolution:** Add exact marker/preflight key sets, an argument-boundary
  table, and separate `comparedCaptures:117` report semantics from the later
  117-item review packet.
- **Status:** Closed.

### Review iteration 9 — new cardinalities cannot reuse Sequence 8 values

- **Finding:** Sequence 9 adds plan, ledger, authorization, Tier, and source
  authority members, so Sequence 8 cardinalities are no longer valid; guessing
  final values before implementation would be equally unsafe.
- **Resolution:** Derive counts and a membership digest from explicit closed
  path sets after implementation, include them in the reviewed continuation
  marker, reject open-glob membership, and require maintainer acceptance before
  bootstrap.
- **Status:** Closed.

No unresolved blocking issue remains in the plan design. Implementation and
formal execution remain unauthorized until the maintainer accepts the reviewed
plan.

## Review checklist

- [x] User request is covered by a concrete correction and continuation path.
- [x] Sequence 8 passed evidence is reused read-only and never rerun.
- [x] Capture and continuation identities are distinct and fixed.
- [x] Comparator uses exact cross-recovery sources.
- [x] Every currently unavailable handler is in scope.
- [x] External review remains independent.
- [x] Root v2 is preserved.
- [x] API/Streamlit fail-soft behavior is explicitly protected.
- [x] Affected files, verification, risks, rollback, and scope gates are known.
- [x] BDD scenarios meet priority counts.
- [ ] Implementation is authorized.
- [ ] Red-first implementation tests pass.
- [ ] Continuation Tier/preflight is published.
- [ ] External 117-item intake is accepted.
- [ ] Root is published and pristine-verified.

## Traceability summary

The sibling ledger is authoritative and canonical JSON. It contains closed,
bidirectional links among `REQ-009`, `CFR-026..033`, `AC-SEQ9-001..009`,
`IMPL-048..056`, and `TEST-067..079`, with structural coverage `10000` basis
points, no gaps, and no orphans. Planning status remains `NOT_TESTED`,
implementation status `NOT_STARTED`, and test execution `NOT_RUN`.

## Change history

| Version | Date | Change |
| --- | --- | --- |
| `1.0-reviewed` | 2026-07-27 | Attest plan-quality review closed unverifiable namespace/reviewer/timing claims and exact schema/argument/report-count ambiguity; no implementation verdict is claimed. |
| `0.9-review-candidate` | 2026-07-27 | Created Sequence 9 plan; closed old-preflight, recapture, partial-handler, comparator-lineage, authorization-mutation, and external-review blockers. |

## Next handoff

The repository maintainer reviews this plan and ledger. On explicit
implementation acceptance, the implementer starts at Phase 0 and must stop at
the Phase 5 external-review boundary unless an independently authored accepted
intake is available.
