# Quant Radar UX-1B Sequence 19 Post-V1 Lifecycle-Test Correction Continuation

## Document Control

| Field | Value |
|---|---|
| Type | Implementation plan and formal-publication continuation |
| Version | `1.0-reviewed` |
| Status | `REVIEWED — pending exact-byte maintainer acceptance` |
| Date | 2026-07-30 |
| Author | Scribe-method local authoring |
| Reviewer | Deterministic local blocking review, then repository maintainer |
| Audience | Maintainer, implementation agent, formal reviewer, release gate |
| Sequence | `19` |
| Parent sequence | `18`, exact permanent state `V1_INTAKE` |
| Parent amendment plan | `docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence18-component-name-amendment.md` |
| Parent amendment ledger | Same parent basename with `.traceability.yaml` |
| Parent accepted authorization | `docs/ui-ux/quant-radar-ui-v2-ux1b-sequence18-component-name-amendment-authorization.md` |
| Continuation ledger | Same Sequence 19 basename with `.traceability.yaml` |
| Intended handoff | Builder only after separate exact-byte plan acceptance |

## Authority and Purpose

The accepted Sequence 18 component-name amendment successfully created and
authenticated its Tier and V1 preflight. The public verifier currently
returns:

```text
verified-V1_INTAKE
```

The production lifecycle is valid and its first three forward artifacts are
exact. The manual-review publication has not run. The full coordinator,
however, reports five stale lifecycle tests:

```text
TEST-180
TEST-183
TEST-189
TEST-198
TEST-199
```

Those tests were authored while the permanent Sequence 18 namespace was at
`IMPLEMENTATION_BOUNDARY`. They still assume either an absent Tier or an
absent entire formal namespace. After an authorized V1 transition those
assumptions are false by design. Re-running the old test expectations cannot
make them pass without deleting or disguising valid formal history.

This continuation makes the five tests lifecycle-aware, imports exact
Sequence 18 V1 as immutable history without consulting mutable current-source
builders, creates a distinct successor authorization and Tier, and only then
publishes the exact already-accepted intake to the manual-review path. It
stops at a new `W2_REVIEW` state. It does not create or authorize a handoff
candidate, theme root, capture, comparison, reviewer submission, or theme
operation.

This document and its ledger do not authorize implementation. The maintainer
must separately accept their final exact SHA-256, byte size, and mode.
Implementation may then produce a distinct Sequence 19 authorization
candidate. That later candidate requires a second, separate exact-byte
acceptance before any Sequence 19 formal bootstrap, preflight, or V2
publication.

## Exact Incident State

### Current implementation baseline

| Path | SHA-256 | Size | Mode |
|---|---|---:|---:|
| `Makefile` | `1f0c6078599c53e43a82cd787e0d9f47d192140ce9bccf3ca3310c31abee967f` | `68817` | `0644` |
| `scripts/ui_ux_theme_handoff.py` | `c0d85b7a7148d2cfafed28af877fb59b077028477cf8d875d41566a48931c33c` | `1847931` | `0644` |
| `scripts/test_ui_ux_theme_handoff.py` | `711e733333eea9e226ce95993f4e3dacaf7a8fc2294c5da2fa3f4ebc829fcc98` | `1263476` | `0644` |

The two Python files are frozen Sequence 18 V1 package bytes. They may change
only after exact acceptance of this plan and ledger. `Makefile` is also in
the intended implementation surface because Sequence 19 adds new public
targets and variables; it must otherwise preserve every existing target and
default.

### Retained planning and authorization authorities

| Authority | SHA-256 | Size | Mode |
|---|---|---:|---:|
| Sequence 17 continuation plan | `c9189b386d548e5fcefcbb84a16cdbcc640717024dfcd435b51f2ec98d5d6eb2` | `45466` | `0644` |
| Sequence 17 continuation ledger | `8ab7fea5009951565c98eb22b2721852b257cf5e61dad0246c67ec18a1c76ff2` | `25170` | `0644` |
| Sequence 18 amendment plan | `e803a10e11031b3e3e00ce010e3df0c87f57501edc9ce297387d910917a74aec` | `44986` | `0644` |
| Sequence 18 amendment ledger | `0e9530f9787165951a2827eb57f52905e73a08745bd7148cd5a081eb096e91c5` | `14370` | `0644` |
| Accepted Sequence 18 amendment authorization | `7927a907bdd7873dc4a863674af05b13f933e2f5b2bd4ed34c4c03a9c68f4e57` | `9800` | `0644` |
| Superseded Sequence 18 authorization | `d8f7b7d95b980f26543e49cb483a11a84c44a4d0d364809250239bba89d77c70` | `7675` | `0644` |

All six remain immutable history and members of the Sequence 19 source
package. Sequence 19 does not rewrite or replace them.

### Exact permanent Sequence 18 V1

| Role | Path | SHA-256 | Size | Mode |
|---|---|---|---:|---:|
| Lease | `.claude/ui_snapshots/ux1b/recovery/external-review-o1-lifecycle-test-correction-20260730T030000Z.lease` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `0` | `0600` |
| Prechange | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-o1-lifecycle-test-correction-prechange-seq18.json` | `64d8f377739b5026743dbdbf0dd43eff4a1b04536c4d1b1aba6ccf48eaf4e03a` | `6883` | `0600` |
| Rollback | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-o1-lifecycle-test-correction-rollback-seq18.json` | `92e90446d441053e0e00089709f24b32e6a27c3cdd61a7af77c859319f3f0a9c` | `3653` | `0600` |
| Owner | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-o1-lifecycle-test-correction-prechange-20260730T031000Z/quant-radar-theme-handoff-external-review-o1-lifecycle-test-correction-owner` | `997d9e287cf64ad11ae2b43eb2de60d234f61154790f1bb1358798b2033a976d` | `183` | `0600` |
| Archive | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-o1-lifecycle-test-correction-prechange-20260730T031000Z/prechange-files.tar` | `325818e674c14a02a9f75a6b81d1900e699d3da47f45c3e1b05855545765256b` | `3348480` | `0600` |
| Bundle | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-o1-lifecycle-test-correction-prechange-20260730T031000Z/bundle-manifest.json` | `311c97b12694d8a9745d72ed0455b25408d318cbb3058eee0f670d57e3b3b594` | `1561` | `0600` |
| Preflight | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-o1-lifecycle-test-correction-preflight-20260730T030000Z.json` | `16232eefe0ef1dc7f1b4ba35c0d3954af450ea0637861732d83c1f6e57d2731d` | `69038` | `0600` |

The Tier presence vector is:

```text
true,true,true,true,true,true,true,true
```

The retained forward state is:

| Role | Path | SHA-256 | Size | Mode | Presence |
|---|---|---|---:|---:|---|
| Report | `.claude/ui_snapshots/ux1b/recovery/control-migration-20260729T060000Z.json` | `97a37c01a7fefbaf20386a6bb732e87993e8f282ba3216885ad92f2530a7f553` | `12444` | `0600` | present |
| Packet | `.claude/ui_snapshots/ux1b/recovery/control-migration-review-packet-20260729T060000Z.json` | `1a9f1a3c995c04d5db1137e25f861a333483a9ba2bb83176532f87a74cc024dd` | `89295` | `0600` | present |
| Accepted intake | `.claude/ui_snapshots/ux1b/review-intake/control-migration-20260729T060000Z.json` | `cf95412e50f6dc7b6608752010d9bb791c77168e3fc913ecb9843d1e1d427081` | `33070` | `0600` | present |
| Manual review | `.claude/ui_snapshots/ux1b/recovery/control-migration-manual-review-20260729T060000Z.json` | — | — | — | absent |
| Handoff candidate | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-candidate-20260729T060000Z.json` | — | — | — | absent |
| Theme root | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json` | — | — | — | absent |

The two rejected dot-leading Sequence 18 paths remain absent. The new
Sequence 19 plan, ledger, authorization candidate, Tier, preflight, and
publication paths are also absent before this planning turn.

### Baseline verification

The accepted Sequence 18 verifier was run read-only with the exact accepted
five IDs and returned:

```json
{"kind":"verify-external-review-o1-lifecycle-test-correction-preflight","path":".claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-o1-lifecycle-test-correction-preflight-20260730T030000Z.json","sha256":"16232eefe0ef1dc7f1b4ba35c0d3954af450ea0637861732d83c1f6e57d2731d","status":"verified-V1_INTAKE"}
```

The full coordinator was run with the Makefile interpreter and returned:

```text
161/166 passed; 0 controlled missing-behavior failures; 5 unexpected failures
```

The five unexpected IDs were exactly `TEST-180`, `TEST-183`, `TEST-189`,
`TEST-198`, and `TEST-199`. Every other registered test passed. Any different
result at Phase S19-0 is a new blocker and forbids implementation.

## Root Cause

The failure is test-state coupling, not a corrupt V1:

| Test | Stale assumption | Lifecycle-aware correction |
|---|---|---|
| `TEST-180` | Every prefix from one through seven ordered Tier destinations is invalid. | Prefixes one through six remain invalid; the exact seven-destination bootstrap prefix without preflight is valid `V0_BOOTSTRAPPED`; all eight destinations plus exact forward state are valid V1/V2. Exercise synthetic prefixes only in a disposable namespace. |
| `TEST-183` | The permanent classifier must equal `IMPLEMENTATION_BOUNDARY`. | Authenticate the actual permanent state from the exact allowed set and require current baseline `V1_INTAKE`; keep later-review mutation checks in a disposable parent or against a state-relative snapshot. |
| `TEST-189` | The permanent wrapper must begin at `IMPLEMENTATION_BOUNDARY`. | Require permanent `V1_INTAKE`, then use an isolated production-shaped fixture to prove implementation boundary, V0, V1, and V2 transitions without touching permanent paths. |
| `TEST-198` | Every Sequence 18 formal and rejected path is absent before and after attacks. | Snapshot actual path identity, presence, mode, size, and digest; each mutation must fail before a new write and leave the snapshot identical. Use a fresh disposable namespace for the special pre-first-write absence scenario. |
| `TEST-199` | Every formal path is absent and authorization incident state equals current state. | Distinguish immutable authorization history from live state. The authorization body retains its historical zero-write incident boundary; the current classifier must authenticate V1, while manual review/candidate/root remain absent. |

No correction may weaken the production classifier merely to satisfy these
tests. The tests adapt to valid lifecycle state; valid state does not adapt
to stale test assumptions.

## Decision Summary

1. Create Sequence 19 rather than mutate or delete the accepted Sequence 18
   Tier, preflight, authorization, archive, or forward history.
2. Update exactly the five stale tests and add successor-specific tests. Do
   not suppress, skip, xfail, reorder away, or remove any coordinator test.
3. Add a standalone historical V1 importer that authenticates exact retained
   Sequence 18 bytes from its recorded archive, PAX headers, Tier, preflight,
   and forward records. It must not call current source/supplemental
   projection builders or compare archived source/test bytes with the newly
   edited live Python files.
4. Make all four active Sequence 18 routes, including its old live verifier,
   fail closed as superseded after the accepted Sequence 19 source
   transition. Existing Sequence 18 formal bytes stay readable only through
   the historical importer and the new Sequence 19 read-only classifier.
5. Add a distinct Sequence 19 marker, schema, authorization path, IDs,
   commands, Make variables, Make targets, Tier paths, and preflight path.
6. Reuse the exact accepted intake only as a retained descriptor. Publish an
   atomic create-once byte copy to the existing manual-review path with a
   different inode and exact `0600` ownership/mode/nlink contract.
7. Run the full coordinator at the real parent V1 before freezing the
   Sequence 19 authorization, then at production-shaped disposable W0, W1,
   and W2 states. After formal authorization acceptance, run it again after
   each real W0, W1, and W2 transition.
8. Stop at `W2_REVIEW`. Candidate, root, capture, compare, submit, reviewer,
   theme, and downstream authority remain forbidden.

## Scope

### In scope

- Exact immutable import of the accepted Sequence 18 V1.
- Lifecycle-aware corrections to `TEST-180`, `TEST-183`, `TEST-189`,
  `TEST-198`, and `TEST-199`.
- New successor tests `TEST-200..209`.
- Sequence 18 active-route supersession guard after plan acceptance.
- Sequence 19 authorization grammar, package, projections, material
  partitions, descriptor budget, namespace inventory, and deterministic PAX.
- New Sequence 19 bootstrap, preflight, verify, and publish commands and
  corresponding Make targets.
- Production-shaped disposable lifecycle fixtures using exact Sequence 19
  basenames under a temporary parent.
- Create-once publication and read-only lost-response reconciliation.
- Full-coordinator checkpoints at parent V1 and each successor lifecycle
  state.
- Plan, traceability ledger, authorization candidate, prechange, rollback,
  private Tier, preflight, and manual-review publication artifacts.

### Out of scope

- No deletion, rename, chmod, truncate, rewrite, or relocation of any
  Sequence 8-18 formal or authorization artifact.
- No change to accepted report, packet, intake, or decision truth.
- No reviewer submission; the accepted intake already exists.
- No handoff candidate, theme root, capture, comparison, render, image,
  sidecar, selector, provider, API, UI, dependency, or runtime-default edit.
- No relaxation of path, canonical JSON, PAX, descriptor, component-name,
  ownership, mode, nlink, create-once, or fsync contracts.
- No hidden formal cleanup to manufacture an implementation-boundary state.
- No changes to tests outside `TEST-180`, `183`, `189`, `198`, `199`, and
  newly appended `TEST-200..209`, except mechanical coordinator registry
  range/count updates.
- No publication during plan creation, plan review, source implementation,
  or authorization-candidate review.

## Requirements

### `REQ-021` — Correct post-V1 tests and continue exact V2 publication

The system must authenticate the accepted Sequence 18 V1, make the five
stale tests lifecycle-aware without weakening production contracts, and
publish only the exact accepted intake to manual review under a separately
accepted Sequence 19 authority.

### `CFR-102` — Immutable Sequence 18 V1 historical import

Sequence 19 must import the exact accepted amendment authorization, both
Sequence 18 authorization documents, all seven Sequence 18 current Tier
authority leaves, its exact preflight, and the report/packet/intake forward
prefix. The importer must validate canonical JSON, record metadata,
cross-document bindings, deterministic PAX membership, and material
partitions without rebuilding historical projections from mutable live
source.

### `CFR-103` — Lifecycle-aware test semantics

The five named tests must derive expectations from authenticated lifecycle
state. Valid implementation-boundary, V0, V1, and V2 states must be exercised
in isolated production-shaped fixtures. Partial, mixed, tampered, replayed,
or downstream-expanded states must still fail before write.

### `CFR-104` — Successor authorization and old-route interlock

Sequence 19 must use a distinct authorization marker, schema, document path,
correction ID, Tier ID, command set, and namespace. Once the accepted
Sequence 19 source transition is present, all four Sequence 18 active
commands, including its old live verifier, must fail with an explicit
superseded-authority violation before any publisher is reachable. No current
command may accept the old authorization as live authority.

### `CFR-105` — Exact source and descriptor geometry

The current source package must include immutable Sequence 17/18 plan,
ledger, and authorization history plus the new Sequence 19 plan, ledger, and
authorization exactly once. Projection, content, authority, retained-leaf,
soft-floor, and PAX counts must be exact and recomputed from unique paths.

### `CFR-106` — Atomic create-once V2 publication

From authenticated `W1_READY`, publication must copy the retained accepted
intake bytes to the existing manual-review path through a same-directory
temporary regular file, fsync, no-replace rename, and parent fsync. The
result must be mode `0600`, current uid/gid, nlink `1`, a different inode,
and byte-identical to the intake. Lost-response reconciliation is read-only.

### `CFR-107` — Phase-complete verification and protected scope

The full coordinator must pass at the real parent V1 before candidate freeze,
in disposable W0/W1/W2 rehearsals, and after each authorized real transition.
Every checkpoint must prove protected parent references unchanged, rejected
paths absent, no temporary debris, descriptor limits restored, and
candidate/root/downstream paths absent.

### `CFR-108` — Two explicit acceptance boundaries

The reviewed plan and ledger require exact-byte maintainer acceptance before
source implementation. The later authorization candidate requires separate
exact-byte acceptance before any formal Sequence 19 write. Neither code,
tests, a generated document, nor an automated reviewer may approve its own
authority.

The parent `REQ-019`, `REQ-020`, `CFR-091..101`, and accepted Sequence 18
component-name amendment remain historical contracts. This plan supersedes
only their assumption that Sequence 18 active commands may proceed from
V1 and only the stale state expectations in the five named tests.

## Sequence 19 Authority Contract

### Exact identities

| Field | Exact value |
|---|---|
| Capture ID | `20260729T040000Z` |
| Packet continuation ID | `20260729T060000Z` |
| Parent Sequence 18 correction ID | `20260730T030000Z` |
| Sequence 19 correction ID | `20260730T050000Z` |
| Sequence 19 Tier ID | `20260730T051000Z` |
| Marker | `UX1B_FORMAL_HANDOFF_EXTERNAL_REVIEW_V1_LIFECYCLE_TEST_CORRECTION_CONTINUATION_V1` |
| Schema | `quant-radar-ui-ux-formal-handoff-external-review-v1-lifecycle-test-correction-continuation-authorization/v1` |
| Authorization path | `docs/ui-ux/quant-radar-ui-v2-ux1b-sequence19-post-v1-lifecycle-test-correction-continuation-authorization.md` |
| Formal pause | `W2_REVIEW` |

### Exact commands

```text
bootstrap-external-review-v1-lifecycle-test-correction
preflight-external-review-v1-lifecycle-test-correction
verify-external-review-v1-lifecycle-test-correction-preflight
publish-v1-lifecycle-test-corrected-review
```

No submit command exists because the exact accepted intake is already present.
No reconcile command exists because publish performs read-only exact-output
reconciliation when the destination already exists.

### Exact lifecycle states

| State | Bootstrap destinations | New preflight | Parent forward prefix | Manual review | Candidate/root |
|---|---:|---|---|---|---|
| `IMPLEMENTATION_BOUNDARY` | `0/7` | absent | exact report/packet/intake | absent | absent |
| `W0_BOOTSTRAPPED` | `7/7` | absent | exact report/packet/intake | absent | absent |
| `W1_READY` | `7/7` | present and exact | exact report/packet/intake | absent | absent |
| `W2_REVIEW` | `7/7` | present and exact | exact report/packet/intake | present and exact | absent |

Any other prefix, any mixed parent/current leaf, any candidate/root presence,
or any drifted exact record is an error. Classification is read-only.

### Exact new Tier destinations

| Order | Role | Relative path |
|---:|---|---|
| 1 | Lease | `.claude/ui_snapshots/ux1b/recovery/external-review-v1-lifecycle-test-correction-20260730T050000Z.lease` |
| 2 | Prechange | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-v1-lifecycle-test-correction-prechange-seq19.json` |
| 3 | Rollback | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-v1-lifecycle-test-correction-rollback-seq19.json` |
| 4 | Private Tier directory | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-v1-lifecycle-test-correction-prechange-20260730T051000Z` |
| 5 | Owner | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-v1-lifecycle-test-correction-prechange-20260730T051000Z/quant-radar-theme-handoff-external-review-v1-lifecycle-test-correction-owner` |
| 6 | Archive | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-v1-lifecycle-test-correction-prechange-20260730T051000Z/prechange-files.tar` |
| 7 | Bundle | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-v1-lifecycle-test-correction-prechange-20260730T051000Z/bundle-manifest.json` |
| 8 | Preflight | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-v1-lifecycle-test-correction-preflight-20260730T050000Z.json` |

The seven bootstrap destinations are the lease, prechange, rollback, private
Tier directory, owner, archive, and bundle. Preflight is the eighth ordered
destination and is shown separately in the lifecycle table. All leaf
basenames must satisfy the unchanged component predicate
`[A-Za-z0-9][A-Za-z0-9._-]{0,127}`. The Tier directory must be mode `0700`.
All seven file leaves must be regular, current uid/gid, mode `0600`, nlink
`1`; the lease is the exact empty file. The private Tier directory must have
exactly the owner, archive, and bundle children and no temporary residue.

### Authorization body

The candidate body must be one canonical JSON object and bind:

- the exact marker, schema, sequence number, IDs, commands, states, forward
  paths, Tier destinations, and formal pause;
- exact references for this reviewed plan and ledger;
- exact immutable references for the six retained Sequence 17/18 planning
  and authorization files;
- the exact seven Sequence 18 V1 Tier/preflight records and three exact
  forward records;
- the exact ordered source package and all cardinalities;
- `noReviewerIntakeAuthority`, `noSubmitAuthority`,
  `noCaptureAuthority`, `noCompareAuthority`, `noCandidateAuthority`,
  `noRootAuthority`, and `noThemeAuthority` all true;
- the atomic publication contract and current component-name predicate;
- explicit `supersedesLiveCommands` for all four Sequence 18 commands;
- `status: AUTHORIZED`.

The Markdown envelope may contain only one heading, the marker fence, the
canonical JSON fence, and a terminal newline. Parsing must reject duplicate
keys, floats where integers are required, alternate Unicode spellings,
unknown fields, non-canonical JSON, trailing material, wrong mode, wrong
digest, replay of either Sequence 18 authorization, or mismatched body.

## Historical V1 Import Contract

The importer is a pure read/authentication boundary:

1. Open the workspace and retained directories by descriptor.
2. Authenticate the exact Sequence 18 amended authorization and its exact
   references to the amendment plan, ledger, and superseded authorization.
3. Authenticate lease, prechange, rollback, owner, archive, bundle, and
   preflight metadata and bytes.
4. Validate archive PAX headers, member order, member modes, member sizes,
   member digests, bundle manifest, and prechange/rollback cross-links.
5. Validate the stored historical `sourceProjection` and
   `supplementalProjection` against the retained archive members and recorded
   digests, not against mutable live source/test files.
6. Validate the exact report, packet, and accepted-intake records and
   semantic decision binding.
7. Reconstruct the exact sixteen Sequence 18 material-authority leaves:
   nine imported parent leaves and seven current Sequence 18 leaves.
8. Require manual review, candidate, root, and every Sequence 19 formal path
   absent when `require_initial=True`.
9. Return classification `S18_V1_INTAKE` plus exact content and authority
   partitions without writing, touching mtimes, extracting archive members,
   or following symlinks.

The implementation must not call the current Sequence 18 preflight builder or
live source projection builder from this importer. Doing so would make
historical validity depend on post-V1 test/source edits and recreate the
current blocker.

## Current Source Authority

### Exact ordered package

The candidate freezes this lexicographically ordered twelve-file package:

```text
Makefile
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence17-o1-lifecycle-test-correction-continuation.md
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence17-o1-lifecycle-test-correction-continuation.traceability.yaml
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence18-component-name-amendment.md
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence18-component-name-amendment.traceability.yaml
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence19-post-v1-lifecycle-test-correction-continuation.md
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence19-post-v1-lifecycle-test-correction-continuation.traceability.yaml
docs/ui-ux/quant-radar-ui-v2-ux1b-sequence18-component-name-amendment-authorization.md
docs/ui-ux/quant-radar-ui-v2-ux1b-sequence19-post-v1-lifecycle-test-correction-continuation-authorization.md
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-o1-lifecycle-test-correction-seq18.md
scripts/test_ui_ux_theme_handoff.py
scripts/ui_ux_theme_handoff.py
```

Every path appears once, is regular, mode `0644`, and has an exact SHA-256 and
size in prechange, rollback, archive PAX, bundle, preflight, and
authorization-derived package validation.

### Projection and descriptor arithmetic

Sequence 18 V1 is exact:

```text
source projection              270
supplemental projection         73
content materials              634
parent authority                 9
current Sequence 18 authority    7
authority total                 16
retained materials             650
protocol allowance             252
reserve                         64
required soft floor            966
raise ceiling                 1536
```

Sequence 19 adds exactly three supplemental records: its plan, ledger, and
authorization. It retains all prior package history. Its planned geometry is:

```text
source projection              270
supplemental projection         76   = 73 + 3
content materials              637   = 634 + 3
parent Sequence 18 authority    16
current Sequence 19 authority    7
authority total                 23   = 16 + 7
retained materials             660   = 637 + 23
protocol allowance             252
reserve                         64
required soft floor            976   = 660 + 252 + 64
raise ceiling                 1536
```

Before candidate freeze, implementation must derive one unique-path union and
prove:

- the three projection sets are exact and internally unique;
- content, parent authority, and current authority partitions are pairwise
  disjoint;
- material count equals the union count;
- no count is padded, duplicated, or inferred only from a constant;
- deterministic archive PAX membership equals the exact twelve-file package;
- the soft limit is raised only when below `976`, the hard limit is at least
  `976`, and the original soft limit is restored on success, failure, and
  fault injection.

Any observed count differing from `270/76/637/23/660/976` blocks candidate
generation and requires a reviewed amendment. Do not silently edit constants
to match a failing observation.

## Lifecycle-Aware Test Contract

### Existing tests to update

| ID | Permanent-state assertion | Disposable-state coverage | Negative guarantee |
|---|---|---|---|
| `TEST-180` | Authenticate actual Sequence 18 V1 without mutation. | Invalid prefixes `1..6`; valid V0 at seven Tier leaves; valid V1/V2 at eight leaves plus forward state. | Every other prefix or downstream expansion fails. |
| `TEST-183` | Require exact current `V1_INTAKE` and unchanged namespace snapshot. | Prove `IMPLEMENTATION_BOUNDARY -> V0_BOOTSTRAPPED -> V1_INTAKE`; later-review mutation only in disposable state. | `require_initial=True` rejects manual-review presence. |
| `TEST-189` | Require exact current `V1_INTAKE`. | Prove all four Sequence 18 states with production basenames. | Classifier performs no writes and rejects mixed states. |
| `TEST-198` | Snapshot actual V1 identity/presence/metadata/digests. | Run pre-first-write absence attacks in a fresh disposable namespace. | Every authorization, count, command, ID, path, or digest mutation fails before write and leaves snapshots exact. |
| `TEST-199` | Distinguish historical authorization incident boundary from current V1 classifier. | Verify phase-specific cleanup at implementation boundary/V0/V1/V2. | Candidate/root/rejected paths and temp debris remain absent. |

These tests keep their IDs and coordinator order. Their names may change only
to describe the lifecycle-aware contract accurately.

### New tests

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| `TEST-200` | Positive/history | Import exact permanent Sequence 18 V1 after patching current projection builders to raise. | Import returns `S18_V1_INTAKE`; patched live builders are never called; no path changes. |
| `TEST-201` | Negative/authority | Invoke all old Sequence 18 routes after successor source activation; invoke new routes before candidate exists. | Every route fails before formal write; old authority reports superseded and new authority reports absent. |
| `TEST-202` | Boundary/state | Classify permanent parent V1 and disposable Sequence 19 implementation/W0/W1/W2 states. | Only four exact successor states are accepted and classification is read-only. |
| `TEST-203` | Negative/state | Exercise every partial new Tier prefix, mixed parent/current paths, forward expansion, rejected path, symlink, directory, mode, nlink, owner, and digest mutation. | Each fails before write and preserves the before snapshot. |
| `TEST-204` | Positive/geometry | Build exact package, source/supplemental projections, content/authority partitions, unique union, descriptor profile, and deterministic PAX twice. | Counts are `270/76/637/23/660/976`; bytes and member order are identical. |
| `TEST-205` | Negative/grammar | Mutate marker, schema, IDs, commands, plan/ledger refs, parent refs, package order/count, geometry, publication capability, and forbidden flags. | Parser rejects each mutation and both Sequence 18 authorizations as live authority. |
| `TEST-206` | Positive/lifecycle | Run bootstrap and preflight in a production-shaped disposable parent with exact basenames and all write-boundary fault points. | Create-once W0/W1 transitions reconcile safely; no alias-only path can pass. |
| `TEST-207` | Positive/publication | Publish retained intake to disposable manual review; inject every publication boundary and lost response. | W2 is exact, byte-identical, different inode, mode/owner/nlink exact; reconciliation is read-only. |
| `TEST-208` | Negative/resources | Exercise hard limit below `976`, soft limit below/equal/above floor, sparse high descriptors, exceptions, and cleanup. | Unsafe hard limit fails before write; safe soft limit raises/restores; no descriptor leak. |
| `TEST-209` | Integration/scope | Run registry/coordinator shape, exact parent refs, journals if changed, cleanup, and phase stop assertions. | Expected IDs end at `TEST-209`, all protected refs exact, no drift, no candidate/root/downstream authority. |

The coordinator grows from `166` to `176` tests. The required green result is
exactly:

```text
176/176 passed; 0 controlled missing-behavior failures; 0 unexpected failures
```

### Test-quality requirements

- Positive, negative, boundary, crash, replay, mutation, resource-limit,
  cleanup, and integration cases are mandatory.
- Permanent formal paths are read-only test inputs.
- All write-path tests use disposable directories with exact production
  basenames.
- State-relative snapshots include path type, device, inode where relevant,
  mode, uid, gid, nlink, size, digest, and exact directory children.
- Patching only `Path.exists()` or a basename alias is insufficient evidence.
- No test may pass because a broad exception swallowed a failed assertion.
- No skip, xfail, timeout inflation, order dependency, hidden cleanup, or
  test removal is acceptable.

### Given-When-Then scenarios

| Scenario | Given | When | Then |
|---|---|---|---|
| `SC-SEQ19-001-HP` | Exact permanent Sequence 18 V1 and unchanged retained archive | Historical importer runs while current live builders are unavailable | It returns `S18_V1_INTAKE` and performs zero writes |
| `SC-SEQ19-001-NP` | A parent ref, archive PAX member, Tier record, preflight, or forward record drifts | Historical importer runs | It rejects before write and preserves the namespace snapshot |
| `SC-SEQ19-002-HP` | Exact permanent V1 | The five corrected tests run | They authenticate V1 and pass without modifying permanent paths |
| `SC-SEQ19-002-BP` | Production-shaped disposable implementation, V0, V1, and V2 states | Classifier runs | Exactly the four allowed states classify |
| `SC-SEQ19-002-NP` | A partial, mixed, downstream-expanded, or metadata-drifted state | Classifier or route runs | It rejects before write |
| `SC-SEQ19-003-HP` | Accepted successor source and exact accepted Sequence 19 candidate | New route runs | Only the exact successor command/ID/schema set can proceed |
| `SC-SEQ19-003-NP` | Old live authority, missing new candidate, or replayed authorization | Any active route runs | It reports superseded/absent/replayed authority before publisher access |
| `SC-SEQ19-004-HP` | Exact twelve-file package | Projections and material union build twice | Geometry is `270/76/637/23/660/976` and PAX bytes are deterministic |
| `SC-SEQ19-004-BP` | Soft/hard descriptor limits below, equal to, and above `976` | A descriptor-heavy operation runs | Unsafe hard limit rejects; safe soft limit raises and restores |
| `SC-SEQ19-004-NP` | Duplicate/overlapping material path or PAX/order/count drift | Geometry validator runs | It rejects instead of adjusting a constant |
| `SC-SEQ19-005-HP` | Exact W1 with retained accepted intake and absent manual review | Publish runs | It commits exact different-inode manual review and reaches W2 |
| `SC-SEQ19-005-EP` | A crash or lost response occurs at any publish boundary | The same operation resumes | It completes once or reconciles exact output read-only |
| `SC-SEQ19-005-NP` | Manual-review destination exists with wrong bytes or metadata | Publish resumes | It rejects and never overwrites |
| `SC-SEQ19-006-HP` | Parent V1 or an exact successor checkpoint | Full coordinator and protected-scope audit run | `176/176` passes and protected refs remain exact |
| `SC-SEQ19-006-NP` | Candidate, root, rejected path, temp debris, or downstream authority appears | Scope audit runs | It rejects the phase as expanded or dirty |
| `SC-SEQ19-007-HP` | Exact plan/ledger acceptance followed later by exact candidate acceptance | Implementation and formal phases run in order | Each phase stays within its accepted boundary and stops at W2 |
| `SC-SEQ19-007-NP` | Either exact acceptance is missing or bytes drift afterward | A gated phase is requested | It stops before source work or formal write, respectively |

## Acceptance Criteria

### `AC-SEQ19-001` — exact immutable V1 import

The successor authenticates the current Sequence 18 V1 and reconstructs its
exact historical projections and sixteen authority leaves without consulting
mutable live source builders or modifying history.

### `AC-SEQ19-002` — five lifecycle-aware corrections

All five named tests pass against the real permanent V1 and still reject
partial, mixed, drifted, replayed, and downstream-expanded states in
production-shaped disposable fixtures.

### `AC-SEQ19-003` — fail-closed successor boundary

Old Sequence 18 active routes cannot write after successor source activation;
new routes cannot write before the separately accepted Sequence 19
authorization; old authorization bytes remain exact readable history.

### `AC-SEQ19-004` — exact package and descriptor geometry

The twelve-file package, `270/76/637/23/660/976` geometry, unique material
union, descriptor restoration, and deterministic PAX archive are exact.

### `AC-SEQ19-005` — lifecycle and V2 publication

Bootstrap, preflight, verify, create-once publication, crash recovery, and
lost-response reconciliation produce only W0, W1, and W2 as specified, with
manual review an exact different-inode copy of accepted intake.

### `AC-SEQ19-006` — coordinator and protected scope

The full `176/176` coordinator passes at required checkpoints; parent refs,
rejected paths, candidate/root, temp cleanup, and scope restrictions remain
exact.

### `AC-SEQ19-007` — acceptance and formal pause

No source implementation starts before exact plan/ledger acceptance; no
formal write occurs before exact authorization-candidate acceptance; formal
execution stops at `W2_REVIEW`.

## Implementation Checklist

| ID | Work item | Files | Primary verification |
|---|---|---|---|
| `IMPL-161` | Freeze current baseline, exact parent V1 refs, namespace, and coordinator failure set. | read-only workspace | public V1 verify; exact five-failure baseline |
| `IMPL-162` | Add fail-first successor contracts and rewrite the five stale tests lifecycle-aware. | test script | focused `TEST-180/183/189/198/199/200..209` controlled red |
| `IMPL-163` | Add Sequence 18 active-route supersession guard and protect old bytes. | source, test | old commands fail before write; historical verify path remains |
| `IMPL-164` | Implement standalone Sequence 18 V1 importer and immutable material reconstruction. | source, test | live builders patched to raise; importer still authenticates |
| `IMPL-165` | Implement Sequence 19 constants, grammar, classifier, Tier, namespace, package, geometry, descriptor, and PAX contracts. | source, test | grammar/mutation/cardinality/resource suites |
| `IMPL-166` | Implement bootstrap, preflight, verify, and production-shaped disposable lifecycle. | source, test | W0/W1 and every fault boundary |
| `IMPL-167` | Implement atomic exact-intake V2 publication and reconciliation. | source, test | W2 copy/inode/mode/fsync/fault suite |
| `IMPL-168` | Add exact Make variables and four public targets without altering old defaults. | Makefile, source, test | `make -n`, CLI help, exact registry tests |
| `IMPL-169` | Run full pre-authorization gates and freeze the distinct authorization candidate. | package files | `176/176`, syntax/static/pip, double-generation determinism |
| `IMPL-170` | After separate candidate acceptance, run real W0/W1/W2 gates and stop. | formal outputs | coordinator after every state; public verify; protected diff |

## Implementation Phases and Gates

### Phase S19-0 — reviewed-plan acceptance and immutable freeze

1. Confirm final plan and ledger exact SHA-256, size, and mode.
2. Obtain explicit maintainer acceptance of both exact records.
3. Re-read all baseline paths and require the incident state in this plan.
4. Re-run the public Sequence 18 V1 verifier.
5. Re-run the coordinator and require exactly the five listed unexpected
   failures and no others.
6. Snapshot protected parent refs and formal namespace metadata.

**Gate:** any drift, a sixth failure, missing V1 artifact, present manual
review/candidate/root, or absent exact acceptance blocks implementation.

### Phase S19-1 — fail-first lifecycle-aware contracts

1. Extend expected coordinator IDs to `TEST-209`.
2. Rewrite only the five named tests according to the table above.
3. Append `TEST-200..209`.
4. Use exact production basenames in every new disposable fixture.
5. Run the focused tests before production implementation.

**Gate:** new missing behavior must fail in controlled, named successor tests.
Unexpected import errors, writes to permanent paths, or failures outside the
planned IDs are blockers.

### Phase S19-2 — old-authority interlock and historical importer

1. Install the Sequence 19 successor activation constant.
2. Make all four Sequence 18 active routes fail closed as superseded before
   any publisher or old live-verifier body is reachable.
3. Implement the standalone exact V1 importer.
4. Patch current projection builders to raise during importer tests.
5. Prove parent archive/PAX/material validation remains exact.
6. Re-run the five corrected tests and `TEST-200..203`.

**Gate:** old routes cannot write; valid V1 imports without live rebuilding;
all partial/drift attacks remain zero-write.

### Phase S19-3 — successor lifecycle and geometry

1. Implement exact constants, marker/schema parser, namespace, classifier,
   Tier builders, and record validators.
2. Implement exact twelve-file package and projections.
3. Build unique material partitions and descriptor profile.
4. Implement production-shaped bootstrap, preflight, and verify.
5. Implement atomic publication and read-only reconciliation.
6. Add Make variables/targets and CLI dispatch.
7. Run focused `TEST-204..209`.

**Gate:** exact `270/76/637/23/660/976` geometry, deterministic PAX, safe
descriptor behavior, exact W0/W1/W2 semantics, and protected scope all pass.

### Phase S19-4 — pre-authorization full rehearsal

1. Run syntax/static verification and dependency consistency checks.
2. Run all `176` coordinator tests against the real parent V1.
3. Run full coordinator-equivalent checkpoints in disposable W0, W1, W2.
4. Run authorization generation twice and compare bytes.
5. Confirm new formal paths and authorization candidate remain absent until
   all other checks are green.
6. Generate the authorization candidate once.
7. Re-run candidate parser, package, hash/mode, source diff, and protected
   namespace checks.

**Gate:** candidate exists only after all checks are green. Any byte change
after generation invalidates it and requires regeneration plus all gates.

### Phase S19-5 — authorization handoff

1. Report candidate path, exact SHA-256, byte size, and mode.
2. Report final source/test/Make hashes and relevant checks.
3. Stop without formal bootstrap.
4. Obtain explicit separate maintainer acceptance of the exact candidate.

**Gate:** no accepted exact candidate means no Sequence 19 formal writes.

### Phase S19-6 — formal bootstrap and W0 checkpoint

1. Re-authenticate the exact candidate and unchanged package.
2. Run the exact bootstrap command once.
3. Require `W0_BOOTSTRAPPED` and the exact seven-destination bootstrap
   prefix with preflight absent.
4. Run full `176/176` coordinator, source/package verification, and protected
   namespace checks.
5. Stop and report W0 evidence.

**Gate:** any check failure stops before preflight. No cleanup or retry may
delete committed exact leaves.

### Phase S19-7 — formal preflight and W1 checkpoint

1. Run the exact preflight command once.
2. Require `W1_READY` and exact preflight.
3. Run public Sequence 19 verify.
4. Run full `176/176` coordinator and protected namespace checks.
5. Confirm manual review, candidate, and root remain absent.
6. Stop and report W1 evidence.

**Gate:** any check failure stops before publication.

### Phase S19-8 — exact V2 publication and mandatory stop

1. Run the exact publish command once.
2. Require `W2_REVIEW`.
3. Re-run publish to prove read-only reconciliation.
4. Prove manual review is byte-identical to intake, different inode, mode
   `0600`, current uid/gid, nlink `1`, and parent directory durable.
5. Run public Sequence 19 verify and full `176/176` coordinator.
6. Compare all protected parent refs and namespace snapshots.
7. Confirm candidate/root and every downstream authority remain absent.
8. Stop.

**Gate:** no next sequence, handoff preparation, candidate publication, root,
capture, compare, submit, or theme action is implied by W2 completion.

## Affected Files

### Planning outputs in this turn

```text
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence19-post-v1-lifecycle-test-correction-continuation.md
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence19-post-v1-lifecycle-test-correction-continuation.traceability.yaml
```

### Planned implementation edits after exact plan acceptance

```text
Makefile
scripts/ui_ux_theme_handoff.py
scripts/test_ui_ux_theme_handoff.py
```

### Planned non-formal candidate after implementation gates

```text
docs/ui-ux/quant-radar-ui-v2-ux1b-sequence19-post-v1-lifecycle-test-correction-continuation-authorization.md
```

### Later formal outputs after separate candidate acceptance

```text
.claude/ui_snapshots/ux1b/recovery/external-review-v1-lifecycle-test-correction-20260730T050000Z.lease
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-v1-lifecycle-test-correction-prechange-seq19.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-v1-lifecycle-test-correction-rollback-seq19.json
.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-v1-lifecycle-test-correction-prechange-20260730T051000Z/
.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-v1-lifecycle-test-correction-preflight-20260730T050000Z.json
.claude/ui_snapshots/ux1b/recovery/control-migration-manual-review-20260729T060000Z.json
```

Every Sequence 8-18 artifact and all files outside the listed source package
remain protected read-only.

## Verification Commands

Use the repository interpreter fixed by `Makefile`: `.venv/bin/python`. The
current environment is Python `3.11.15` with exact installed runtime packages
including Streamlit `1.57.0`, FastAPI `0.139.0`, and Playwright `1.60.0`.
The system Python is not an accepted substitute because runtime-identity and
installed-package contracts are part of the frozen test suite.

Representative non-formal checks:

```bash
.venv/bin/python -B -m py_compile scripts/ui_ux_theme_handoff.py scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -B scripts/ui_ux_theme_handoff.py verify-python-syntax --json
.venv/bin/python -B scripts/test_ui_ux_theme_handoff.py
git diff --check
git diff -- Makefile scripts/ui_ux_theme_handoff.py scripts/test_ui_ux_theme_handoff.py docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence19-post-v1-lifecycle-test-correction-continuation.md docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence19-post-v1-lifecycle-test-correction-continuation.traceability.yaml docs/ui-ux/quant-radar-ui-v2-ux1b-sequence19-post-v1-lifecycle-test-correction-continuation-authorization.md
```

The exact Sequence 18 read-only baseline verifier:

```bash
.venv/bin/python -B scripts/ui_ux_theme_handoff.py \
  verify-external-review-o1-lifecycle-test-correction-preflight \
  --capture-id 20260729T040000Z \
  --packet-continuation-id 20260729T060000Z \
  --parent-formal-state-oracle-correction-id 20260730T010000Z \
  --o1-lifecycle-test-correction-id 20260730T030000Z \
  --o1-lifecycle-test-tier-id 20260730T031000Z \
  --json
```

The exact Sequence 19 commands are generated as Make targets during
implementation. They must pass all five IDs explicitly; no ambient default
may select a formal identity.

Required post-change checks also include:

- canonical JSON parse and duplicate-key rejection for ledger and candidate;
- plan hash/size/mode binding in the ledger;
- traceability closure with no gaps or orphans;
- exact package order and mode checks;
- deterministic double generation for PAX archive and authorization body;
- soft/hard descriptor boundary tests with restoration;
- source diff against this plan and unexplained-scope-drift review;
- protected-parent hash/mode/size and namespace snapshot comparison;
- current-state public verify and full coordinator at every gate.

Any unavailable check must be reported. Failing checks caused by the change
are blockers and must not be waived.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Historical importer accidentally calls live projection builders. | Valid V1 becomes unverifiable after source/test edits. | Patch every live builder to raise in `TEST-200`; validate historical projections only from retained archive/PAX and records. |
| Tests are weakened instead of made lifecycle-aware. | Corrupt partial states could pass. | Preserve all negative prefix/mutation cases in disposable production-shaped fixtures; only state expectations change. |
| Old accepted command publishes after code changes. | Publication occurs under authority that did not bind new bytes. | Explicit successor interlock before publisher; old active routes fail closed and are tested zero-write. |
| New plan drops retained Sequence 18 package history. | Projection/PAX geometry is incomplete. | Exact twelve-file package retains all nine current Sequence 18 package paths and adds three new paths. |
| Parent authority is counted twice or overlaps content. | Descriptor floor is under- or over-stated. | Build unique-path partitions; require pairwise disjointness and exact `23` authority leaves. |
| Permanent tests mutate formal paths. | Data loss or formal drift. | Permanent state is read-only; all synthetic writes occur under temporary parents with exact basenames. |
| Candidate is generated before tests pass. | Self-authorized or stale authority. | Candidate path must remain absent until `176/176` and all pre-authorization gates are green. |
| W0/W1 tests pass but real-state tests fail later. | Publication blocker recurs. | Full coordinator is mandatory at parent V1 and after every real W0/W1/W2 transition. |
| Lost response causes overwrite or duplicate output. | Manual review bytes or inode contract changes. | Create-once no-replace publish; existing exact destination reconciles read-only. |
| Incompatible system Python is used. | False test failure before import. | Use Makefile interpreter or compatible Python 3.11+; record interpreter in execution evidence. |

## Rollback and Recovery

### Before plan acceptance

Only this plan and ledger may exist. Remove neither automatically. No source
or formal rollback is needed because implementation and publication are
forbidden.

### During source implementation

Use the accepted Sequence 19 plan as scope authority. Restore only the three
planned mutable files from the captured exact prechange archive if a
maintainer explicitly chooses rollback. Never use destructive Git commands
or touch parent formal artifacts.

### After candidate generation

Any source, test, Makefile, plan, ledger, or candidate byte change invalidates
the candidate. Regenerate it only after repeating all pre-authorization
gates. Candidate removal does not authorize formal cleanup.

### After W0 or W1

Do not delete exact committed leaves to manufacture an earlier state. Resume
only through the accepted idempotent command after authentication and green
checkpoint evidence. Partial or drifted state requires a new reviewed
correction.

### After W2

The exact manual-review artifact is immutable. Lost-response retry is
read-only reconciliation. Any mismatch stops; it is not overwritten.

## Traceability Matrix

| Requirement | Acceptance | Implementation | Tests |
|---|---|---|---|
| `REQ-021` | `AC-SEQ19-001..007` | `IMPL-161..170` | five corrected tests, `TEST-200..209` |
| `CFR-102` | `AC-SEQ19-001`, `003`, `006` | `IMPL-161`, `163`, `164`, `169`, `170` | `TEST-183`, `189`, `199`, `200`, `201`, `203`, `209` |
| `CFR-103` | `AC-SEQ19-002`, `006` | `IMPL-162`, `164`, `169`, `170` | `TEST-180`, `183`, `189`, `198`, `199`, `202`, `203`, `209` |
| `CFR-104` | `AC-SEQ19-003`, `007` | `IMPL-163`, `165`, `168`, `169`, `170` | `TEST-198`, `199`, `201`, `205`, `209` |
| `CFR-105` | `AC-SEQ19-004`, `006` | `IMPL-165`, `168`, `169`, `170` | `TEST-198`, `199`, `204`, `205`, `208`, `209` |
| `CFR-106` | `AC-SEQ19-005`, `006`, `007` | `IMPL-166`, `167`, `169`, `170` | `TEST-183`, `189`, `202`, `203`, `206`, `207`, `209` |
| `CFR-107` | `AC-SEQ19-002`, `004`, `005`, `006`, `007` | `IMPL-161..170` | five corrected tests, `TEST-200..209` |
| `CFR-108` | `AC-SEQ19-003`, `006`, `007` | `IMPL-161`, `163`, `169`, `170` | `TEST-199`, `201`, `205`, `209` |

The canonical sibling ledger is normative for machine-verifiable many-to-many
closure. It must report `coverageBasisPoints: 10000`, `gaps: []`,
`orphans: []`, `status: NOT_TESTED`, and `testExecution.status: NOT_RUN`.

## Success Metrics

- Public parent verifier remains exact `verified-V1_INTAKE` before successor
  formal execution.
- Baseline is exactly five known unexpected tests and no others.
- The five corrected tests pass at the real permanent V1 and remain
  adversarial in disposable states.
- Historical V1 import passes while live builders are patched to raise.
- Source geometry is exactly `270/76/637/23/660/976`.
- Full coordinator is exactly `176/176` at all mandatory green checkpoints.
- Old Sequence 18 active routes and pre-acceptance Sequence 19 routes are
  zero-write fail-closed.
- W2 manual review is exact bytes, different inode, mode/owner/nlink exact.
- No protected parent record changes.
- Candidate, root, rejected paths, and downstream authority remain absent.
- Implementation diff contains only the planned files and required formal
  outputs.

## Dependencies

- Exact accepted Sequence 18 V1 records listed above.
- Compatible Python 3.11+ interpreter and standard library.
- Existing repository descriptor-safe publisher, canonical JSON, PAX, lock,
  fsync, retained-descriptor, and no-replace primitives.
- Filesystem support for regular-file metadata, fsync, and atomic rename.
- Separate maintainer acceptances for plan/ledger and later candidate.

No network service, package installation, browser, UI server, external
reviewer, or credential is required for this correction.

## Review Checklist

- [x] User request is fully covered: five tests become lifecycle-aware and V2
      publication resumes only afterward.
- [x] Exact current V1 and five-failure baseline are evidenced.
- [x] Affected files, commands, IDs, states, paths, checks, and risk areas are
      explicit.
- [x] Parent history is immutable and imported without live-source rebuild.
- [x] Old active authority is fail-closed after successor activation.
- [x] New authority has a separate exact acceptance boundary.
- [x] Source package retains history and arithmetic is internally consistent.
- [x] Positive, negative, boundary, crash, replay, resource, and cleanup tests
      are explicit.
- [x] Full coordinator runs at real parent V1 and every real successor state.
- [x] No plan step deletes or rewrites formal history.
- [x] Scope excludes candidate/root/theme and unrelated product changes.
- [x] Rollback is non-destructive and state-aware.
- [x] Traceability closes without gaps or orphans.
- [x] No unresolved blocking issue remains.

## Review Findings

### Round 1 findings and closure

| ID | Severity | Finding | Closure |
|---|---|---|---|
| `S19-R1-001` | Blocking | A diagnostic run used `/Users/ken/.local/bin/python3.11`, producing eight unrelated runtime-identity/package failures in addition to the five target failures. | Located the Makefile environment at `.venv/bin/python`; verified Python `3.11.15`, Streamlit `1.57.0`, FastAPI `0.139.0`, and Playwright `1.60.0`; reran the full coordinator to the exact `161/166` five-failure baseline. |
| `S19-R1-002` | Blocking | A live Sequence 18 preflight rebuild would compare historical V1 against edited current source/test bytes and make valid history unverifiable. | Made a standalone archive/PAX-bound V1 importer mandatory, prohibited live projection builders, and added `TEST-200` with those builders patched to raise. |
| `S19-R1-003` | Major | Treating Sequence 19 as a replacement package could drop the nine-file Sequence 18 package and undercount projections. | Retained all nine current package paths, added exactly plan/ledger/authorization, fixed the package at twelve paths, and derived `73 + 3 = 76` supplemental and `634 + 3 = 637` content leaves. |
| `S19-R1-004` | Major | Carrying only the seven current Sequence 18 leaves would omit its nine imported parent authority leaves. | Bound all sixteen Sequence 18 authority leaves as the successor parent partition, plus seven current leaves, yielding `23` authority and `660` retained leaves. |
| `S19-R1-005` | Major | “Seven Tier leaves” ambiguously included the preflight even though V0 has seven bootstrap destinations and no preflight. | Renamed the state column to bootstrap destinations, enumerated those seven destinations, and kept preflight as the separate eighth destination. |
| `S19-R1-006` | Major | Old-route language alternated between write-capable routes and all four active routes. | Standardized the successor interlock: all four old active routes, including the old live verifier, fail as superseded; historical reads use the new importer/classifier. |
| `S19-R1-007` | Major | Test cases were listed without compact Given-When-Then scenario IDs for machine traceability. | Added seventeen positive, negative, boundary, exception, and acceptance scenarios and closed them through the canonical ledger. |

### Round 2 verification

- The accepted Sequence 18 public verifier returned exact
  `verified-V1_INTAKE` with preflight
  `16232eefe0ef1dc7f1b4ba35c0d3954af450ea0637861732d83c1f6e57d2731d`.
- The correct-environment coordinator returned exact `161/166`, zero
  controlled failures, and only the five planned unexpected IDs.
- The V1 preflight independently reports `270/73/634/16/650/966`; its
  prechange and rollback each contain the exact ordered nine-file package.
- The successor package is the sorted unique nine-file parent package plus
  three new records. Arithmetic closes at `270/76/637/23/660/976`, with
  `1536` unchanged as the raise ceiling.
- Every new formal component is ASCII publisher-valid; measured basename
  lengths are `19..102`, below the unchanged `128` maximum.
- Report, packet, and intake retain their exact digests and modes. Manual
  review, candidate, root, authorization candidate, and every new Tier path
  remain absent.
- `git diff --check` passes for the plan. The sibling ledger is canonical
  JSON, binds the final plan, and passes bidirectional closure with
  `coverageBasisPoints: 10000`, no gaps, and no orphans.
- No unresolved blocking issue remains. The plan is executable only after
  exact-byte maintainer acceptance.

Review limitation: repository policy for this turn prohibited delegation, so
the Judge skill's independent multi-engine/subagent procedure was not
available. This is a deterministic local evidence review and does not claim
independent Judge consensus. The separate maintainer acceptance boundary
remains mandatory.

## Change History

| Date | Version | Change |
|---|---|---|
| 2026-07-30 | `0.9-draft` | Initial post-V1 lifecycle-aware correction and V2 continuation plan. |
| 2026-07-30 | `1.0-reviewed` | Closed interpreter, historical-import, package/authority geometry, lifecycle terminology, old-route, scenario, and verification findings. |

## Next Handoff

After blocking review closes and the ledger validates canonically, report the
exact SHA-256, byte size, and mode of both files. Stop. Do not edit the frozen
source/test/Makefile, generate the authorization candidate, create Sequence
19 formal artifacts, or publish V2 until the maintainer separately accepts
the exact reviewed plan and ledger.
