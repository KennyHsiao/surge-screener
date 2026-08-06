# UX-1B Exact-Decimal Geometry Remediation Plan

**Status:** ACCEPTED EXECUTION AMENDMENT
**Date:** 2026-07-19
**Owner:** Codex
**Reviewers:** independent geometry correctness and execution-scope reviewers
**Audience:** maintainers of the UX-1B browser evidence and recovery pipeline

## 1. Objective and context

Remove one deterministic false positive in focused-control layout discovery,
then resume the already accepted UX-1B semantic-readiness verification and
recovery sequence.

The `institutions-controls/desktop` discovery row completed its owned
interaction (`generation 1 -> 2`), produced two identical semantic snapshots,
and passed exact labels, order, selection, primary projection, clipping, and
overflow checks. It failed only because two segmented buttons intentionally
share a one-pixel border:

```text
first:  x=80.000, width=197.359
second: x=276.359
mathematical overlap: 1.000px
binary-float overlap:  1.0000000000000568px
allowed tolerance:     1.000px
```

`_rounded_rect()` has already frozen every browser rectangle component to
three decimal places. Worker `_rects_overlap()` and trusted-verifier
`_focused_rects_overlap()` nevertheless add those binary floats and compare
the unquantized results, so both layers classify the legal shared border as
overlap.

## 2. Scope

### In scope

- `scripts/ui_ux_browser_worker.py`
  - make overlap comparison preserve the exact decimal meaning of the
    worker's existing 0.001px measurements;
  - temporarily scroll below-fold focused roots into an authenticated audit
    viewport, stabilize their geometry, and restore the original page scroll
    before final DOM projection;
- `scripts/ui_ux_evidence.py`
  - apply the same exact boundary rule at the independent trusted-validation
    boundary without importing one layer into the other;
  - add an expected-old-SHA, descriptor-authenticated capture-stack rotation
    path while preserving the existing create-only publisher;
- `scripts/test_ui_ux_evidence.py`
  - add fail-first worker, trusted-helper, and integrated-validator coverage
    using the exact Institutions geometry;
  - prove 1.000px is accepted while 1.0004px and 1.001px are rejected;
  - add rotation fault, race, archive, and reopen tests;
- `scripts/ui_ux_snapshot_matrix.py`
  - require explicit expected-old SHA authorization when a freeze rotates an
    existing canonical contract;
- `scripts/test_ui_ux_snapshot_matrix.py`
  - prove create and rotation modes are distinct and exactly wired;
- `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery.md`
  - remove stale Task 7 authorization, classify the old baseline, and publish
    the replacement identity only after replacement Task 6 passes;
- `.agents/PROJECT.md`
  - append corrective and final ledger entries without rewriting history;
- focused, full-suite, real-browser, discovery, and smoke verification;
- capture-stack refreeze only after all pre-publication gates pass.

### Out of scope

- changing `targetOverlapTolerance` (`1.0px` legacy, `0.5px` accessible);
- adding a generic epsilon or otherwise weakening final evidence validation;
- rounding untrusted evidence to millipixels, which could hide a real
  sub-millipixel excess;
- changing semantic-readiness observation or interaction behavior;
- changing any of the nine production selector files;
- publishing canonical evidence before discovery and smoke pass;
- beginning selector migration before the replacement Task 6 baseline passes.
- overwriting or renaming any prior manifest/evidence namespace.

## 3. Requirements and acceptance criteria

### REQ-GEOM-001 — deterministic exact-decimal geometry arithmetic

Both overlap helpers must convert each already validated numeric component and
the supplied tolerance with `Decimal(str(value))`, then perform edge and
overlap arithmetic only with those exact decimal values. Constructing a
`Decimal` directly from a binary float is forbidden.

- **AC-GEOM-001:** the exact real Institutions values above do not overlap at
  a 1.0px tolerance;
- **AC-GEOM-002:** an otherwise identical 1.001px overlap is rejected;
- **AC-GEOM-003:** the same inclusive-boundary/excessive-boundary distinction
  holds vertically;
- **AC-GEOM-004:** rectangles remain overlapping only when both axes exceed
  their tolerance, preserving the current two-dimensional rule;
- **AC-GEOM-005:** zero-overlap and disjoint rectangles remain non-overlapping.
- **AC-GEOM-006:** a forged 1.0004px overlap remains rejected by the trusted
  validator; the fix must not round untrusted evidence down to 1.000px.
- **AC-GEOM-007:** the accessible-control 0.500px boundary is accepted and
  0.501px is rejected by both helpers.

### CFR-GEOM-001 — fail-closed oracle

The legal boundary is inclusive, not widened. Exact-decimal arithmetic may
remove binary representation noise only; it must preserve finer precision at
the trusted boundary. `1.0004px` and `1.001px` remain hard failures.

### CFR-GEOM-002 — immutable pre-publication state

Until discovery, real smoke, and independent review pass:

- the canonical capture-stack contract must retain SHA-256
  `197fb7ab9dd030f63a73c83aac30a3ef1f73daee69a5c71fdfe8fd265ab76424`;
- the prior Attempt 4/recovery evidence remains untouched;
- production selector bytes and hashes remain unchanged;
- disposable workers and fixture apps must be cleaned up.

### REQ-PUBLISH-001 — explicit compare-and-swap rotation

The existing create-only publisher remains unchanged for absent destinations.
Replacing an existing canonical leaf requires a separate API and an explicit
caller-supplied expected-old SHA-256.

- **AC-PUBLISH-001:** wrong/missing expected-old SHA cannot replace an existing
  canonical contract;
- **AC-PUBLISH-002:** before commit, the old leaf is descriptor-frozen, locked,
  rehashed, and matched to the current path identity;
- **AC-PUBLISH-003:** the exact old bytes are exclusively archived as
  `superseded-capture-stack-<old-sha>.json` and reopened before replacement;
- **AC-PUBLISH-004:** new canonical bytes replace the old leaf with one
  same-directory `os.replace`, followed by directory `fsync` and descriptor
  reopen/authentication;
- **AC-PUBLISH-005:** every failure before `os.replace` leaves the old canonical
  bytes and identity unchanged; a failure after replace is classified as
  durability-uncertain and must be resolved by reopening the canonical leaf;
- **AC-PUBLISH-006:** concurrent rotations authorized by the same old SHA have
  exactly one winner; the loser cannot replace the winner.

### REQ-STATE-001 — unambiguous recovery authority

`20260718T172855Z` is immutable but no longer authorized for Task 7 because its
capture contract lacks the required replacement semantic/geometry oracle.

- **AC-STATE-001:** before code execution, recovery status becomes
  `BLOCKED — REPLACEMENT BASELINE PENDING` and the old ID is recorded as
  `superseded-by-contract-gap`; prior manifests remain untouched;
- **AC-STATE-002:** after contract rotation but before Task 6 closure, no
  recovery ID is canonical or authorized for Task 7;
- **AC-STATE-003:** only a new ID with 81/81 pages, 36/36 controls, 234/234
  reopened artifacts, exact manifest hashes, new stack digest, and unchanged
  selector hashes becomes canonical;
- **AC-STATE-004:** `.agents/PROJECT.md` receives append-only correction/final
  entries; the historical 2026-07-18 entry is not rewritten.

## 4. Design

Use an independently defined private conversion helper in each security layer:

```python
from decimal import Decimal

def _geometry_decimal(value: float) -> Decimal:
    return Decimal(str(value))
```

Convert `x`, `y`, `width`, `height`, and tolerance before arithmetic, derive
right/bottom edges in Decimal space, and retain the existing strict `>`
relation on both axes. The worker must not import the trusted evidence module;
the two small implementations stay independent and a mirrored boundary table
proves their semantic equivalence.

This deliberately does not round components or final overlap, use
`math.isclose`, or raise the tolerance. `Decimal(str(value))` exactly recovers
the intended JSON/Python decimal spelling while preserving a malicious or
unexpected fourth decimal for fail-closed rejection.

### Capture-stack rotation protocol

Add a separate `rotate_capture_stack_contract()` boundary. Before the long
discovery/smoke phase, the runner freezes the canonical leaf's exact
`ArtifactContract` and expected SHA without requiring its now-superseded member
hashes to match the live workspace. It also retains and later reauthenticates
both the canonical and recovery-archive directory chains.

At commit, the rotation helper opens `.` relative to the canonical directory
FD as a **fresh open-file-description** and acquires
`fcntl.flock(LOCK_EX | LOCK_NB)` through final reopen; a busy lock fails
boundedly and it must not lock a `dup()` of the retained parent FD.
Inside that critical section it opens the expected-old artifact, requires its
inode/owner/mode/link-count-one/size/SHA to match, and rehashes it twice.

It exclusively publishes a **byte copy, never a hard link**, of the old raw
contract to the digest-named archive in the descriptor-opened recovery
directory. An existing archive is reused only when descriptor reopen proves
the expected owner, regular mode, link-count one, size, and exact bytes/SHA.
Archive directory `fsync` completes before canonical commit.

The new bytes are written and file-`fsync`ed to a same-directory temporary
leaf whose FD remains retained and is rehashed. Immediately before commit the
function revalidates the new live capture stack, rehashes the retained old
descriptor, reopens the canonical path to the same inode/SHA, and
reauthenticates the archive. It then uses one same-directory `os.replace`,
removes no prior archive/evidence, `fsync`s the canonical parent, and returns a
rotation receipt only after full canonical and archive descriptor reopen.
The receipt contains old SHA, archive path/SHA, new SHA, and capture-stack
digest. A canonical-directory `fsync` failure remains durability-uncertain even
when complete new bytes can be reopened; reopen alone cannot upgrade it to a
durable success.

Portable `os.replace` has no rename-if-current-inode primitive. The linear CAS
guarantee therefore covers every cooperative writer using this rotation API;
the owner-only, non-group/world-writable workspace remains the authority
boundary. A hostile non-cooperating same-UID writer is explicitly outside the
existing repository threat model because that identity can already rewrite
the source and parent directories. Tests still prove independent concurrent
rotation callers have exactly one winner.

`--freeze-capture-stack --json` gains a mandatory
`--expected-capture-stack-sha256 <sha>` only when the canonical leaf already
exists. The absent-leaf path still uses the create-only publisher. Supplying
the argument for an absent leaf or omitting it for an existing leaf fails
closed.

### Pre-implementation byte baseline

All code targets are currently untracked, so ordinary `git diff` cannot prove
their preimage. These exact hashes plus the applied hunks are the scope oracle:

| File | Pre-implementation SHA-256 |
| --- | --- |
| `scripts/ui_ux_browser_worker.py` | `af34fd8c8eab6302df1dc477823f6813d8a229d227b15743608dbb3705c3e57c` |
| `scripts/ui_ux_evidence.py` | `262a0e74faac66bd9ac8fc2a5a45ae7e60ccd81e13e165c8817131ef52aaedfe` |
| `scripts/test_ui_ux_evidence.py` | `8b382b4b93fb7404a19ff520f5ea2acb1719f3e4eff2a86a0bdbab78b54e10e3` |
| `scripts/ui_ux_snapshot_matrix.py` | `9a81b57e6980eb9e4fee2cc40606c1b1cda370380916091ff51ca1a9d1fe1d31` |
| `scripts/test_ui_ux_snapshot_matrix.py` | `c4c563795b2aa18d0837e1eaa03f7072bf299ea5e2795e7ec72f2a2d7018d9bd` |
| `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery.md` | `2d2cee08b627e0a00fe4ea401ad66a49a4fa713b8bc35cf09c870451a8d5a466` |
| `.agents/PROJECT.md` | `5b2b9500b46ed63cfc35c53d3f432b16c82ef11408feddb1c95cc8a500e4aec5` |

After implementation, inspect each applied hunk directly, list every changed
function/section, and rehash all protected non-target files and nine production
selectors. No ordinary untracked-file diff is accepted as sufficient proof.

## 5. Implementation sequence

### Task 0 — correct recovery authority before code execution

**Files:** `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery.md`,
`.agents/PROJECT.md`

1. Change the recovery status to `BLOCKED — REPLACEMENT BASELINE PENDING`.
2. Preserve `20260718T172855Z` and both old namespaces byte-for-byte, but mark
   that ID `superseded-by-contract-gap` and revoke Task 7–9 authorization.
3. Record the old contract SHA and state that no replacement ID is canonical.
4. Append one corrective project-ledger row; do not rewrite the historical
   success row.

**Gate:** documentation cannot direct another agent to run Task 7 against the
old baseline while remediation is in progress.

### Task 1 — fail-first boundary test

**File:** `scripts/test_ui_ux_evidence.py`

1. Add one focused boundary-table test for worker `_rects_overlap()` and
   trusted `_focused_rects_overlap()`.
2. Use the exact real Institutions rectangles to require `False` at 1.0px.
3. Move the second rectangle left by exactly 0.001px and require `True`.
4. Add the equivalent vertical boundary, disjoint-axis, and accessible
   0.500/0.501px cases.
5. Add an integrated `_validate_focused_control_evidence()` assertion using
   the fractional real geometry, plus a 1.0004px forged-evidence rejection.
6. Register the test in the direct-script test list.
7. Run only this test and record that both current helpers fail the diagnosed
   shared-border assertions before production code changes.

**Gate:** the new real-value assertion fails for the diagnosed reason before
production code changes.

### Task 2 — minimal implementation

**Files:** `scripts/ui_ux_browser_worker.py`, `scripts/ui_ux_evidence.py`

1. Import `Decimal` and add one private exact-decimal helper independently in
   each module.
2. Rewrite only `_rects_overlap()` and `_focused_rects_overlap()` edge/overlap
   arithmetic.
3. Keep signatures, tolerance values, callers, evidence schema, layout flags,
   and exception behavior unchanged.
4. Run the new boundary and integrated-validator test; require green.

**Gate:** 1.000/0.500px pass, 1.0004/1.001/0.501px fail, both layers agree,
and no unrelated worker or trusted-validator behavior is modified.

### Task 3 — fail-first and implement safe contract rotation

**Files:** `scripts/ui_ux_evidence.py`, `scripts/test_ui_ux_evidence.py`,
`scripts/ui_ux_snapshot_matrix.py`, `scripts/test_ui_ux_snapshot_matrix.py`

1. Add evidence-layer tests for wrong expected SHA, exact archive, successful
   replace/reopen, every pre-commit fault, post-replace durability uncertainty,
   idempotent exact archive recovery, temp cleanup, and concurrent one-winner
   behavior.
   - Wrong-SHA and same-bytes/different-inode canonical mutations must fail
     before archive/temp creation.
   - A preexisting archive with wrong bytes, symlink type, or multiple links
     must fail while preserving the canonical inode/bytes.
   - Archive write/file-fsync/link/directory-fsync, new write/file-fsync,
     precommit validation/path reauth, and `os.replace` faults must preserve
     the old canonical inode, bytes, mode, and link count.
   - Canonical directory-fsync or post-replace reopen faults must return an
     uncertain classification; visible canonical bytes may only be the
     complete new document and automatic rollback is forbidden.
   - Four independent callers with the same expected-old SHA must yield one
     success, three CAS failures, one replace, exact old archive, and no temp.
2. Add runner tests for argument incompatibilities and exact create-vs-rotate
   dispatch. Prove the existing canonical case cannot silently use create-only
   publication.
3. Run only these new tests and record their missing-API/CLI red failures.
4. Implement `rotate_capture_stack_contract()` and the explicit expected-old
   CLI/wiring exactly as specified in the rotation protocol.
5. Run the focused rotation tests green, including descriptor reopen of old
   archive and new canonical bytes.

**Gate:** no-replace creation stays unchanged; authorized rotation is atomic,
archive-preserving, race-closed, and fault-classified.

### Task 4 — local and suite verification

1. Run the new focused geometry test.
2. Run all of `scripts/test_ui_ux_evidence.py` (49/49 plus new rotation tests).
3. Run the prior focused verification set:
   - isolation (29/29 or higher);
   - selection fixture (5/5 or higher);
   - fixtures (26/26 or higher);
   - snapshot matrix (52/52 or higher);
   - theme (9/9 or higher);
   - theme matrix (24/24 or higher);
   - contract (19/19 or higher);
   - dashboard navigation (51/51 or higher).
4. Run Python 3.10 AST parsing, `py_compile`, `compileall`, `tabnanny`,
   `pip check`, and `git diff --check`.
5. Run the real Institutions desktop/tablet/mobile/narrow sequence at least
   twice in owned disposable runtimes.

**Gate:** every relevant check passes and no disposable process remains.

Exact suite commands:

```bash
.venv/bin/python scripts/test_ui_ux_isolation.py
.venv/bin/python scripts/test_ui_ux_evidence.py
.venv/bin/python scripts/test_ui_ux_selection_fixture.py
.venv/bin/python scripts/test_ui_ux_fixtures.py
.venv/bin/python scripts/test_ui_ux_snapshot_matrix.py
.venv/bin/python scripts/test_ui_ux_theme.py
.venv/bin/python scripts/test_ui_ux_theme_matrix.py
.venv/bin/python scripts/test_ui_ux_contract.py
.venv/bin/python scripts/test_dashboard_navigation.py
```

The targeted Institutions run filters
`ux1b_control_discovery_rows()` to the exact four
`institutions-controls/{desktop,tablet,mobile,narrow}` rows, calls
`_run_ux1b_nonterminal_capture()` with expected selection-profile count `4`,
and requires the exact four capture IDs and sidecars. Run that owned snippet
twice; the helper's mandatory quiescence closure must pass both times.

### Task 5 — pre-publication browser gates

1. Run the exact contract-free 57-row control discovery.
2. Run the exact contract-free 10-scenario real mobile smoke.
3. Recheck canonical contract identity, prior recovery identity, process
   quiescence, and the nine protected selector hashes.
4. Obtain independent correctness, test, scope, and maintainability review.

**Gate:** 57/57 discovery, 10/10 smoke, and zero blocking review findings.

Exact commands and closure assertions:

```bash
.venv/bin/python - <<'PY'
from scripts import ui_ux_snapshot_matrix as runner
result = runner.run_ux1b_control_discovery()
assert len(result.sidecars) == 57
assert len(result.base_capture_stack_digest) == 64
assert len(result.source_digest) == 64
print("57/57 discovery passed")
PY

.venv/bin/python scripts/ui_ux_snapshot_matrix.py \
  --ux1b-real-smoke --json
```

The smoke JSON must report ten capture IDs, ten PNGs, ten sidecars, ten counter
IDs, and twelve quiescent processes. This standalone pair must pass before the
freeze command is allowed to repeat it.

### Task 5A — gate-discovered focused audit viewport remediation

The first exact 57-row discovery failed deterministically at
`knowledge-graph-controls/mobile`. Independent diagnostics proved that the
control itself was valid and non-overlapping, but its normal document position
was below the initial fold: root `y=1208.359`, target `y=1236.359`, viewport
height `844`. The old immutable sidecar shows the same below-fold placement
and contains no `controlEvidence`; it cannot authorize bypassing the current
layout contract. An in-memory worker-only scroll made the real row pass 1/1.

1. Add a fail-first real-Chromium test with a valid focused root below the
   mobile fold, including a nested scroll container. Require successful layout
   evidence, exact restoration of document and scrollable-ancestor offsets,
   and continued rejection of a root that remains too tall to fit after
   scrolling. Add a horizontal case that proves temporary scrolling cannot
   hide genuine x-axis clipping or overflow. Prove a one-time geometry change
   can settle, while perpetual movement fails within the bound; every failure
   path must still restore the original scroll state. Exercise below-fold
   legacy and accessible roots with different heights: their temporary audit
   offsets may differ, but their post-restore DOM-projection x/y/width values
   must each equal their own pre-scroll values exactly. Inject both a
   restore-only ancestor replacement and a primary audit failure followed by
   ancestor replacement: the first must fail closed, while the second preserves
   the primary error and attaches restoration context.
2. Split layout collection into a pure snapshot helper and a bounded wrapper.
   Retain the exact root element, save `document.scrollingElement` and every
   scrollable ancestor's offsets/identity vector, scroll that root into view,
   then restore every original horizontal offset before measurement so a
   temporary x-axis scroll cannot bypass clipping. Wait for
   fonts/readiness/document stability and require two consecutive identical
   snapshots at the existing 0.001px resolution. Before scrolling, require and
   retain the same two-snapshot stability oracle for root/targets/document.
   Retain the exact root and target handles before those prerequisites so a
   rerender still fails identity checks, but freeze the ancestor
   offsets/identity/metrics state only **after** the prerequisites complete
   and immediately before the pre-scroll two-snapshot oracle. No audit scroll
   may occur before that freeze. This ordering treats normal prerequisite-time
   Streamlit geometry growth as part of readiness, while every identity,
   offset, or metric change after the freeze remains fail-closed.
   Split the caller timeout into an audit deadline plus an explicit reserved
   cleanup budget; every Playwright wait receives the remaining bound and may
   not fall back to its default timeout. Font readiness must use an explicit
   remaining-deadline `wait_for_function`/bounded race, never the unbounded
   `page.evaluate(document.fonts.ready)` pattern; an unresolved-font test must
   fail within the bound and still restore scroll state.
3. Validate the stable audit-time snapshot with the unchanged clipping,
   horizontal-overflow, minimum-size, and exact-overlap rules. A stable invalid
   layout remains invalid; an unstable layout fails closed.
4. In `finally`, use the retained root to restore every original horizontal
   and vertical offset, require the same connected ancestor vector, verify
   exact numeric offset restoration, and require two identical post-restore
   root/target/document snapshots that are also
   exactly equal to the retained pre-scroll snapshot before later DOM
   projection and full-page screenshot collection. This restore verification
   uses only the reserved cleanup deadline, including after an audit timeout.
   Preserve a primary failure and attach restoration failure context;
   restoration failure without a primary also fails closed. Dispose retained
   state/root handles only after all restore, identity, stability, and
   pre-equals-post checks finish, in the outermost cleanup path.
5. Pass the existing per-capture timeout through all legacy, radio, and
   selectbox layout paths. Do not change fixtures, production pages, selector
   files, evidence schemas, tolerances, or trusted-validator acceptance rules.
6. Run the focused red/green test, the real Knowledge Graph mobile row twice,
   the existing native-radio and Analytics legacy/selectbox generation/counter
   tests, the full evidence suite, then restart Task 5 from exact 57/57
   discovery.

**Gate:** below-fold controls are audited in a stable temporary viewport;
genuine clipping/overflow/overlap and unstable geometry still fail; original
scroll and final projection semantics are restored exactly; all browser
processes quiesce.

### Task 6 — rotate, reopen, and classify canonical contract

1. Run the freeze transaction with explicit authorization:

   ```bash
   .venv/bin/python scripts/ui_ux_snapshot_matrix.py \
     --freeze-capture-stack \
     --expected-capture-stack-sha256 \
     197fb7ab9dd030f63a73c83aac30a3ef1f73daee69a5c71fdfe8fd265ab76424 \
     --json
   ```

2. Require the transaction to repeat 57-row discovery and 10-row smoke before
   commit, archive exact old bytes, rotate once, and descriptor-reopen the new
   canonical contract under its reported SHA and capture-stack digest.
3. Update the recovery ledger with old archive path/hash, new contract
   path/hash/digest, and `replacement baseline pending`; do not authorize a new
   recovery ID yet.

**Gate:** the canonical leaf is the authenticated new contract, the exact old
contract is immutable in its digest-named archive, and no Task 7 ID exists.

### Task 7 — replacement Task 6 baseline and pointer publication

1. Choose one new immutable recovery ID and execute replacement Task 6:
   full pages 81/81 plus focused controls 36/36 under the new digest.
2. Reopen and authenticate all 234 artifacts and both terminal manifests.
3. Recheck source start/end equality, clean children, prohibited-access zero,
   exact nine selector hashes, and all namespace counts.
4. Only after those checks, replace the recovery document's pending pointer
   with the new ID, manifest hashes, contract hash/digest, and authorization.
   Append the final project-ledger row.
5. Only then resume parent Task 7 red selector/accessibility tests. Task 7 may
   change test files only; production migration remains Task 8.

Run:

```bash
make ui-ux1b-recovery-precontrol UX1B_RECOVERY_ID=<new-immutable-id>
```

**Gate:** no selector migration or theme work begins before replacement Task 6
is fully authenticated.

## 6. Risks and rollback

- **Layer mismatch:** guarded by applying the same exact-decimal rule
  independently and running one mirrored boundary table against both helpers.
- **Oracle weakening:** guarded by explicit 1.0004px and 1.001px mutations and
  the unchanged strict Decimal `>` comparison.
- **Unexpected capture-stack change:** discovery and smoke precede atomic
  publication; on any earlier failure the old canonical path/bytes remain
  unchanged and recovery stays explicitly blocked (the old member binding is
  not represented as live-valid).
- **Scope drift in a dirty worktree:** compare exact target hunks and protected
  hashes; preserve all user-owned unrelated changes.
- **Pre-publish rollback:** revert only the exact-decimal/rotation code and
  tests, while leaving the corrective `replacement pending` classification
  accurate. The old canonical contract remains at its original path.
- **Post-publish rollback:** never byte-revert a live capture-stack member.
  Repair forward or restore intended code, then repeat discovery, smoke,
  expected-old-SHA rotation, old-contract archival, and a new recovery
  classification/ID. Existing manifests and archives are never overwritten.

## 7. Traceability

| Requirement | Implementation | Verification |
| --- | --- | --- |
| REQ-GEOM-001 | exact-decimal edges in both overlap helpers | exact Institutions + mirrored horizontal/vertical boundary matrix |
| CFR-GEOM-001 | unchanged tolerance and strict `>` | 1.0004px and 1.001px mutations remain overlap |
| CFR-GEOM-002 | no pre-gate publish or selector changes | hashes, process audit, 57 discovery, 10 smoke |
| REQ-PUBLISH-001 | separate expected-old-SHA rotation API and CLI | archive/fault/race/reopen tests plus freeze receipt |
| REQ-STATE-001 | two-stage recovery and append-only project ledger | old ID revoked before code; new ID published only after 81+36+234 |

## 8. Blocking-plan review checklist

- [x] request and diagnosed runtime failure are both covered;
- [x] affected files and exact boundary behavior are explicit;
- [x] fail-first evidence is executable;
- [x] no tolerance widening or canonical pre-write is permitted;
- [x] existing-leaf publication has executable CAS, archive, fault, and race semantics;
- [x] recovery pointers cannot authorize the old or a provisional ID;
- [x] verification and cleanup steps are executable;
- [x] independent reviewers report no unresolved blocking issue.

Implementation must not begin until this checklist passes and status changes to
`ACCEPTED EXECUTION AMENDMENT`.

## 9. Review history

| Iteration | Verdict | Finding and resolution |
| --- | --- | --- |
| 1 | BLOCKED | The draft changed only the worker and proposed `round(value * 1000)`. Review found the duplicate trusted-validator calculation and demonstrated that rounding could accept forged 1.0004px evidence. v0.2 adds both independent layers, exact `Decimal(str(value))` arithmetic, mirrored tests, and explicit sub-millipixel rejection. |
| 2 | BLOCKED | Geometry was sound, but create-only hard-link publication could not replace the existing canonical leaf; the recovery pointer still authorized the superseded ID; rollback was unsafe after publish. v0.3 adds expected-old-SHA descriptor rotation, immutable archival, fault/race/reopen tests, two-stage recovery authority, exact commands, preimage hashes, and phase-aware rollback. |
| 3 | READY | v0.4 was checked against the live Darwin filesystem and code primitives. Fresh-directory nonblocking flock, descriptor CAS, byte-copy archive, same-directory replace/fsync/reopen, two-stage pointers, and phase-aware rollback are feasible; both reviewers reported no unresolved High/Medium finding. |
| 4 | BLOCKED | The mandatory 57-row gate exposed a separate focused-audit defect: a valid Knowledge Graph control below the initial mobile fold was classified as clipped because the worker measured viewport coordinates without a temporary audit scroll. The deterministic row failed twice; detailed isolated diagnostics identified root/target y positions and excluded overlap, horizontal overflow, timeout, cleanup, and resource exhaustion. Task 5A adds bounded scroll/stabilize/restore behavior and fail-first browser coverage; execution remains blocked pending review. |
| 5 | READY | Task 5A was revised to retain the exact root-to-document scroll ancestor chain, restore horizontal offsets before measurement, require pre/audit/post stable snapshots with exact pre/post parity, reserve cleanup time after audit timeout, keep handles live through restore verification, bound font readiness, and test restoration-only plus primary-and-restoration failures. Both reviewers reported no unresolved blocking issue. |
| 6 | READY | Exact Knowledge Graph mobile tracing found that the implementation froze ancestor metrics before its own font/readiness/document prerequisites. Normal late Streamlit growth then changed retained ancestor heights without changing node identity or offsets, producing a deterministic false mutation failure. The accepted amendment retains root/target handles first but defers the original scroll/metric-state freeze until prerequisites finish; a fail-first Chromium case reproduces the late-growth condition. Two independent reviewers confirmed that post-freeze identity, metric, offset, audit, and exact-restore checks remain fail-closed with no tolerance or evidence-schema change. |
