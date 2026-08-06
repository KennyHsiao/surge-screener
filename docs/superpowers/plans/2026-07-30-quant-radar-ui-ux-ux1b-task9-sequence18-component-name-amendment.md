# Quant Radar UX-1B Sequence 18 Component-Name Amendment

## Document Control

| Field | Value |
|---|---|
| Type | Implementation-plan amendment |
| Version | `1.0-reviewed` |
| Status | `REVIEWED — pending exact-byte maintainer acceptance` |
| Date | 2026-07-30 |
| Author | Scribe |
| Reviewer | Judge-method local evidence review, then repository maintainer |
| Audience | Maintainer, implementation agent, formal reviewer, release gate |
| Sequence | `18` |
| Parent plan | `docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence17-o1-lifecycle-test-correction-continuation.md` |
| Parent ledger | Same parent basename with `.traceability.yaml` |
| Parent authorization | `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-o1-lifecycle-test-correction-seq18.md` |
| Amendment ledger | Same amendment basename with `.traceability.yaml` |
| Intended handoff | Builder after separate exact-byte amendment acceptance |

## Authority and Purpose

The accepted Sequence 18 bootstrap reached the production publisher and
stopped before its first write:

```text
theme-handoff contract error:
publisher name must be one normalized component
```

The Sequence 18 lease basename begins with `.`. The later Sequence 18 owner
basename has the same defect. Both violate the unchanged publisher rule:

```regex
[A-Za-z0-9][A-Za-z0-9._-]{0,127}
```

The existing disposable Sequence 18 lifecycle fixture used the simplified
names `lease` and `owner.json`, so its successful V0/V1/V2 flow did not
exercise the real production basenames.

This amendment removes the leading dot from only those two new Sequence 18
components, makes the exact production components part of the lifecycle-test
contract, preserves the global publisher policy, and replaces the now-stale
authorization with a distinct superseding authorization.

This document does not authorize source implementation or formal execution
until the maintainer separately accepts the final exact SHA-256, byte size,
and mode of this amendment and its ledger. A later superseding authorization
candidate must receive a second, separate exact-byte acceptance before any
formal bootstrap.

## Exact Incident State

### Retained authorities

| Authority | SHA-256 | Size | Mode |
|---|---|---:|---:|
| Parent plan | `c9189b386d548e5fcefcbb84a16cdbcc640717024dfcd435b51f2ec98d5d6eb2` | `45466` | `0644` |
| Parent ledger | `8ab7fea5009951565c98eb22b2721852b257cf5e61dad0246c67ec18a1c76ff2` | `25170` | `0644` |
| Accepted but superseded authorization | `d8f7b7d95b980f26543e49cb483a11a84c44a4d0d364809250239bba89d77c70` | `7675` | `0644` |

The parent plan's thirteen exact Sequence 17 `O1_INTAKE` references remain
the immutable historical inputs. This amendment imports that table without
changing any path, digest, size, mode, semantic binding, or PAX rule.

### Current implementation baseline

| Path | SHA-256 | Size | Mode |
|---|---|---:|---:|
| `Makefile` | `1f0c6078599c53e43a82cd787e0d9f47d192140ce9bccf3ca3310c31abee967f` | `68817` | `0644` |
| `scripts/ui_ux_theme_handoff.py` | `07430ec71857528895cc2031f5ab10885d43a2feaee7d50dc95848c10e5d5627` | `1842477` | `0644` |
| `scripts/test_ui_ux_theme_handoff.py` | `0fdfb3de96df2b98f3e9b0dda9b4ed1eb316ac91bb64b45f6668bb6c90e3772e` | `1244336` | `0644` |

These are the post-Sequence-18 implementation bytes that produced the
accepted authorization and the pre-first-write failure. They are baselines,
not immutable predecessor authorities; the two Python files are the intended
implementation surface. `Makefile` must remain exact.

### Observed namespace

The production classifier currently returns:

```text
IMPLEMENTATION_BOUNDARY
```

The complete Sequence 18 Tier/preflight presence vector is:

```text
false,false,false,false,false,false,false,false
```

Manual review, handoff candidate, and theme root also remain absent. The
retained Sequence 17 state remains exact `S17_O1_INTAKE`.
The distinct amendment authorization candidate path is also absent.

### Component-policy reproduction

| Step | Current basename | Length | Publisher result |
|---:|---|---:|---|
| 1 lease | `.external-review-o1-lifecycle-test-correction-20260730T030000Z.lease` | `68` | reject |
| 2 prechange | `quant-radar-ui-v2-ux1b-theme-handoff-external-review-o1-lifecycle-test-correction-prechange-seq18.json` | `102` | accept |
| 3 rollback | `quant-radar-ui-v2-ux1b-theme-handoff-external-review-o1-lifecycle-test-correction-rollback-seq18.json` | `101` | accept |
| 4 Tier directory | `theme-handoff-external-review-o1-lifecycle-test-correction-prechange-20260730T031000Z` | `85` | accept |
| 5 owner | `.quant-radar-theme-handoff-external-review-o1-lifecycle-test-correction-owner` | `77` | reject |
| 6 archive | `prechange-files.tar` | `19` | accept |
| 7 bundle | `bundle-manifest.json` | `20` | accept |
| 8 preflight | `theme-handoff-external-review-o1-lifecycle-test-correction-preflight-20260730T030000Z.json` | `90` | accept |

No other Sequence 18 component violates the publisher policy.

## Decision Summary

1. Keep the existing publisher regex and maximum component length unchanged.
2. Rename only the Sequence 18 lease and owner basenames.
3. Validate every active Sequence 18 Tier/preflight basename against the
   exact publisher policy before the first formal write.
4. Make disposable lifecycle execution use the real production basenames
   under a temporary parent instead of aliases such as `lease` and
   `owner.json`.
5. Preserve the accepted authorization byte-for-byte as superseded history.
6. Generate a distinct authorization path, marker, schema, and exact
   `supersedesAuthorization` reference.
7. Reuse the Sequence 18 correction and Tier IDs only while every old and new
   Sequence 18 formal leaf remains absent. Any drift requires a new sequence
   or new identities, not cleanup.
8. Disable the old active authorization path/marker before making either
   corrected component reachable. The new authorization file remains absent
   until the implementation is frozen, so every intermediate source state is
   fail-closed.

## Scope

### In scope

- Two Sequence 18 component-name changes.
- One behavior-preserving shared publisher-policy predicate used by the
  existing publisher and the Sequence 18 destination precheck.
- Explicit rejected-path absence checks.
- Production-shaped disposable lifecycle basenames.
- Superseding authorization grammar and replay rejection.
- Updated source package, supplemental projection, content-material,
  retained-descriptor, and soft-floor cardinalities.
- Focused, mutation, crash-prefix, coordinator, protected-history, and
  deterministic-PAX tests.
- Amendment traceability and Scribe/Judge/Builder/project journals.

### Out of scope

- No relaxation of the publisher component grammar.
- No change to Sequence 8-17 paths or hidden-file conventions.
- No change to the four public Sequence 18 command names or their five IDs.
- No new submit, reviewer-intake, capture, comparison, candidate, root, or
  theme command.
- No change to intake or manual-review bytes, paths, decision truth, or
  publication semantics.
- No UI, API, provider, data, fixture app, selector, image, sidecar, theme,
  dependency, or runtime-default edit.
- No rewrite, deletion, or replacement of the accepted authorization.
- No manual creation of formal files to bypass the publisher.
- No formal bootstrap, preflight, or review publication in the planning or
  implementation phase.

## Non-Goals

- This amendment does not redesign the Sequence 18 lifecycle.
- It does not make dot-leading names legal for `_publish_regular_exact`.
- It does not retroactively change predecessor lease or owner names.
- It does not treat the failed command as a partial bootstrap because it
  committed zero formal leaves.
- It does not approve its own authorization candidate.

## Requirements

### `REQ-020` — Resume Sequence 18 without bypassing publication policy

The system must permit the already-reviewed Sequence 18 lifecycle to resume
using publisher-compliant names while preserving exact Sequence 17 history,
zero-write incident evidence, and all original scope restrictions.

### `CFR-097` — Exact component-name policy

Every active Sequence 18 Tier/preflight basename must match the unchanged
`[A-Za-z0-9][A-Za-z0-9._-]{0,127}` rule before any formal write.

### `CFR-098` — Authorization supersession and replay safety

The accepted failed authorization must remain exact and readable as history,
but the current implementation must accept only a distinct authorization
that binds this amendment and explicitly supersedes the old bytes.

### `CFR-099` — Exact amended source geometry

The active source package, projections, content materials, authority leaves,
retained descriptors, soft floor, and deterministic PAX membership must
include the parent plan/ledger, amendment plan/ledger, old authorization, and
new authorization exactly once.

### `CFR-100` — Production-shaped lifecycle verification

Disposable bootstrap, preflight, publication, and crash recovery must execute
the real production basenames through the real publisher without writing the
formal namespace.

### `CFR-101` — Zero-write and protected-scope preservation

All rejected and corrected Sequence 18 formal paths must remain absent until
new exact authorization acceptance. Parent O1, source-external files, and
forbidden candidate/root/capture/theme paths must remain unchanged.

The parent `REQ-019` and `CFR-091..096` remain active. This amendment
supersedes only the component-name, authorization-package, and material-count
portions of parent `CFR-094`, `CFR-095`, and `CFR-096`, plus the corresponding
clauses of `AC-SEQ18-004`, `AC-SEQ18-005`, `AC-SEQ18-007`, and
`AC-SEQ18-008`. All other parent acceptance clauses remain unchanged.

## Component-Name Contract

### Exact path replacement

| Role | Superseded path | Active amended path |
|---|---|---|
| Lease | `.claude/ui_snapshots/ux1b/recovery/.external-review-o1-lifecycle-test-correction-20260730T030000Z.lease` | `.claude/ui_snapshots/ux1b/recovery/external-review-o1-lifecycle-test-correction-20260730T030000Z.lease` |
| Owner | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-o1-lifecycle-test-correction-prechange-20260730T031000Z/.quant-radar-theme-handoff-external-review-o1-lifecycle-test-correction-owner` | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-o1-lifecycle-test-correction-prechange-20260730T031000Z/quant-radar-theme-handoff-external-review-o1-lifecycle-test-correction-owner` |

The amended lease basename is `67` characters. The amended owner basename is
`76` characters. Both begin with an ASCII alphanumeric and remain below the
`128`-character maximum.

### Policy predicate

Implementation may extract the current inline rule into one pure helper:

```text
input: exact str component
accept: fullmatch [A-Za-z0-9][A-Za-z0-9._-]{0,127}
reject: empty, slash, ".", "..", non-str, leading dot, >128 characters
```

`_publish_regular_exact` must call that helper without changing any accepted
or rejected value. The Sequence 18 bootstrap/preflight entry points must
validate the final component of all eight active Tier/preflight destinations
with the same helper before opening a destination for publication.

The full relative-path safety rules remain owned by the existing no-follow
path and directory-descriptor validators. This amendment changes only the
final-component precondition.

### Superseded-path absence

The two dot-leading superseded paths form a permanent Sequence 18 rejected
path set. Bootstrap, preflight, verify, publish, and workspace classification
must fail closed if either path exists, even if every active amended path is
otherwise exact.

No command may delete, rename, adopt, or reinterpret a superseded path.

## Authorization Supersession Contract

### Immutable old authorization

The accepted authorization remains at:

```text
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-o1-lifecycle-test-correction-seq18.md
```

with exact SHA-256
`d8f7b7d95b980f26543e49cb483a11a84c44a4d0d364809250239bba89d77c70`,
size `7675`, and mode `0644`.

It must not be edited, replaced, deleted, or parsed as active authority by the
amended implementation.

### New authorization candidate

The distinct active candidate path is:

```text
docs/ui-ux/quant-radar-ui-v2-ux1b-sequence18-component-name-amendment-authorization.md
```

It uses a distinct marker and schema:

```text
UX1B_FORMAL_HANDOFF_EXTERNAL_REVIEW_O1_LIFECYCLE_TEST_CORRECTION_COMPONENT_NAME_AMENDMENT_V1
quant-radar-ui-ux-formal-handoff-external-review-o1-lifecycle-test-correction-component-name-amendment-authorization/v1
```

The canonical authorization body must retain every parent Sequence 18 field
that is not explicitly amended and add exact:

- `amendment` and `amendmentTraceability` refs;
- `supersedesAuthorization` ref to the old accepted bytes;
- `componentNameContract` with the exact regex, maximum length, two
  superseded paths, two active paths, and `globalPolicyRelaxed:false`;
- `incidentBoundary` with `formalWrites:0`, state
  `IMPLEMENTATION_BOUNDARY`, and the all-false eight-leaf vector;
- amended `sourcePackagePaths`, projection cardinalities, and descriptor
  profile;
- precedence placing `sequence18-component-name-amendment` above the
  superseded Sequence 18 authorization and exact Sequence 17 history.

The four allowed commands and five existing IDs remain unchanged:

```text
captureId                          20260729T040000Z
packetContinuationId              20260729T060000Z
parentFormalStateOracleCorrectionId 20260730T010000Z
o1LifecycleTestCorrectionId       20260730T030000Z
o1LifecycleTestTierId             20260730T031000Z
```

Identity reuse is legal only because both the rejected and active formal
path sets are absent and the prior attempt made zero formal writes. This
condition must be checked:

1. before the first source edit;
2. after implementation stabilizes and before candidate generation;
3. immediately before accepted candidate bytes are consumed;
4. under the lifecycle lock immediately before the first amended Tier write.

If any check fails, this amendment is stale. No cleanup is authorized.

### Replay rejection

The amended parser and public handlers must:

- reject the old marker/schema as active authority;
- reject a missing or different old-authorization exact ref;
- reject a missing or different amendment/ledger ref;
- reject either superseded component as an active destination;
- reject old projection or descriptor counts;
- reject any command or ID expansion;
- perform every rejection before a formal write.

### Source-transition interlock

The accepted old authorization must lose active-parser status before either
corrected component is installed:

1. Change the active authorization path, marker, and schema to the distinct
   amendment values.
2. Require exact amendment, ledger, and superseded-authorization refs.
3. Keep the new authorization path absent.
4. Prove every public Sequence 18 command rejects both the old document and
   the absent new document before opening a Tier destination.
5. Only then change the lease/owner paths and component validation.

No intermediate implementation state may combine the old accepted
authorization with corrected publishable paths. `TEST-198` must exercise this
post-interlock/pre-candidate state directly.

## Current Source Authority

### Exact active package order

The amended deterministic PAX package has nine regular-file members in this
exact lexicographic order:

```text
Makefile
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence17-o1-lifecycle-test-correction-continuation.md
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence17-o1-lifecycle-test-correction-continuation.traceability.yaml
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence18-component-name-amendment.md
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence18-component-name-amendment.traceability.yaml
docs/ui-ux/quant-radar-ui-v2-ux1b-sequence18-component-name-amendment-authorization.md
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-o1-lifecycle-test-correction-seq18.md
scripts/test_ui_ux_theme_handoff.py
scripts/ui_ux_theme_handoff.py
```

The old authorization remains a package member as immutable incident and
supersession evidence. It is not active authority.

Every archive member must retain:

- regular-file type;
- UID/GID zero and empty uname/gname;
- mtime zero;
- mode `0644`;
- exact member size and SHA-256;
- no extraction during validation.

### Amended material and descriptor arithmetic

```text
sourceProjection       = 270
supplementalProjection = 67 + 6 = 73
contentMaterials       = 628 + 6 = 634
parentAuthorityOnly    = 9
currentAuthorityOnly   = 7
commitRetainedLeaves   = 634 + 9 + 7 = 650
protocolAdditional     = 252
reserve                = 64
requiredSoftFloor      = 650 + 252 + 64 = 966
raiseCeiling           = 1536
```

The six Sequence 18 supplemental/content additions above the Sequence 17
baseline are:

1. parent Sequence 18 plan;
2. parent Sequence 18 ledger;
3. superseded Sequence 18 authorization;
4. this amendment;
5. this amendment ledger;
6. the new superseding authorization.

The authority partition remains the exact parent `9` plus current `7`.
Renaming two current authority leaves changes their paths, not their count.

Implementation must derive one unique union and stop if the authenticated
profile is not exactly:

```text
270/73/634/16/650/966
```

No count may be changed merely to fit ambient state.

## Lifecycle Contract

The parent state machine remains:

```text
IMPLEMENTATION_BOUNDARY
        |
        | separately accepted amended bootstrap
        v
V0_BOOTSTRAPPED
        |
        | accepted amended preflight
        v
V1_INTAKE
        |
        | exact retained-intake publication
        v
V2_REVIEW  [mandatory stop]
```

Only the lease and owner path names, active authorization, source package,
and descriptor geometry change.

Bootstrap retains the exact create order:

```text
lease -> prechange -> rollback -> tier-directory -> owner -> archive -> bundle
```

Preflight remains the eighth step. Exact-prefix recovery, no-replace
publication, fsync boundaries, different-inode intake-to-review publication,
frozen reviewer time, read-only V2 reconciliation, and candidate/root
absence remain unchanged.

The production component precheck must run before step one. Crash and
collision tests must additionally prove that neither superseded path is ever
created or adopted.

## Acceptance Criteria

### `AC-SEQ18A-001` — exact two-component correction

Given the eight Sequence 18 Tier/preflight destinations, when the publisher
component policy is evaluated, then all active basenames pass, exactly the
two superseded dot-leading basenames fail, and no other path changes.

### `AC-SEQ18A-002` — immutable supersession

Given the accepted failed authorization and the reviewed amendment, when the
active authorization is parsed, then only the distinct superseding candidate
with exact old-authorization, amendment, and ledger refs is accepted.

### `AC-SEQ18A-003` — exact amended geometry

Given authenticated amended source, when package, projection, material, and
descriptor records are built, then the exact result is nine PAX members and
`270/73/634/16/650/966`.

### `AC-SEQ18A-004` — production-shaped lifecycle

Given a disposable parent directory, when bootstrap, preflight, publication,
and fault recovery run through the real publisher using production
basenames, then the flow reaches exact V0/V1/V2 and leaves no superseded
component or temporary residue.

### `AC-SEQ18A-005` — replay and drift fail closed

Given old authority, an old dotted path, a changed component, changed
amendment metadata, a package/count mismatch, or nonzero prior formal state,
when any amended command runs, then it fails before a formal write.

### `AC-SEQ18A-006` — protected scope and formal pause

Given the complete amended diff and later exact V2, when protected-reference,
namespace, and command-scope gates run, then parent O1 and old authorization
remain exact, candidate/root/capture/theme authority remains absent, and
execution stops at V2.

## Implementation Checklist

| ID | Deliverable | Requirements | Tests |
|---|---|---|---|
| `IMPL-153` | Shared behavior-preserving publisher-component predicate | `REQ-020`, `CFR-097` | `TEST-192`, `TEST-195` |
| `IMPL-154` | Corrected lease/owner paths and rejected-path set | `REQ-020`, `CFR-097`, `CFR-101` | `TEST-192`, `TEST-196`, `TEST-197` |
| `IMPL-155` | Pre-first-write destination-component validation | `REQ-020`, `CFR-097`, `CFR-101` | `TEST-192`, `TEST-195`, `TEST-198` |
| `IMPL-156` | Distinct authorization marker/schema/path and exact supersession | `REQ-020`, `CFR-098` | `TEST-193`, `TEST-198` |
| `IMPL-157` | Nine-member package and `270/73/634/16/650/966` profile | `REQ-020`, `CFR-099` | `TEST-194`, `TEST-199` |
| `IMPL-158` | Production-basename disposable fixture and prefix-fault matrix | `REQ-020`, `CFR-097`, `CFR-100` | `TEST-195`, `TEST-196` |
| `IMPL-159` | Replay, drift, old-path, protected-scope, and absence gates | `REQ-020`, `CFR-098`, `CFR-099`, `CFR-100`, `CFR-101` | `TEST-193`, `TEST-197`, `TEST-198`, `TEST-199` |
| `IMPL-160` | Candidate freeze, double coordinator run, journals, and handoff | `REQ-020`, `CFR-097`–`CFR-101` | `TEST-192`–`TEST-199` |

Parent `IMPL-143..152` remain active. The amendment changes only the path,
authorization, package/profile, and test-fixture portions of
`IMPL-147..149,151,152`.

## Test Plan

### Existing tests whose expectations change

```text
TEST-185  active authorization marker/path, package members
TEST-186  270/73/634/16/650/966 geometry
TEST-189  coordinator total and production-shaped states
TEST-190  amended refs, corrected/rejected paths, prefix inventory
TEST-191  superseding authorization body and traceability
```

All other parent tests remain active. No parent test ID is deleted or
renumbered.

### New amendment tests

| Test | Proof |
|---|---|
| `TEST-192` | Exact publisher predicate, all eight active components, exactly two rejected components, unchanged 128-character boundary |
| `TEST-193` | Old authorization is exact but inactive; only distinct exact superseding authority parses |
| `TEST-194` | Nine sorted PAX members and exact `270/73/634/16/650/966` geometry |
| `TEST-195` | Disposable real publisher uses exact production basenames and reaches V0/V1/V2 |
| `TEST-196` | Every seven-step bootstrap and eighth-step preflight fault resumes only an exact corrected-name prefix |
| `TEST-197` | Any superseded dotted leaf or active-component drift fails the namespace classifier |
| `TEST-198` | Old-authority replay, wrong amendment refs, wrong old-auth ref, old counts, and ID/command expansion fail before write |
| `TEST-199` | Full coordinator, protected refs, deterministic PAX, cleanup, formal absence/pause, and diff scope are exact |

The post-amendment coordinator target is:

```text
166/166
```

### Test-quality requirements

- The lifecycle fixture must derive each disposable path by combining a
  temporary parent with the exact production basename.
- It must call the real publisher and directory creator.
- It must not mock `_publish_regular_exact`, the component predicate, or the
  active destination tuple in the production-shaped happy path.
- Mutation tests may patch one input at a time and must restore every global.
- No real network, ambient sleep, system-clock freshness, or shared mutable
  formal namespace is permitted.
- Every temporary path and injected fault must be cleaned or reopened as an
  authenticated exact prefix.

### Given-When-Then scenarios

| Scenario | Given | When | Then |
|---|---|---|---|
| `SC-AC-SEQ18A-001-HP-001` | Eight amended destinations | Check components | All eight pass |
| `SC-AC-SEQ18A-001-NP-001` | Superseded lease or owner | Check component | Exact rejection |
| `SC-AC-SEQ18A-001-BP-001` | 128/129-character component | Check component | 128 passes, 129 fails |
| `SC-AC-SEQ18A-002-HP-001` | Exact new authority | Parse | Exact body returned |
| `SC-AC-SEQ18A-002-NP-001` | Old accepted authority | Parse as active | Reject before write |
| `SC-AC-SEQ18A-002-NP-002` | Wrong amendment or old-auth ref | Parse | Reject before write |
| `SC-AC-SEQ18A-003-HP-001` | Nine exact package files | Build PAX/profile | Exact geometry |
| `SC-AC-SEQ18A-003-NP-001` | Missing/duplicate package member | Build | Contract violation |
| `SC-AC-SEQ18A-003-NP-002` | Old 70/631/647/963 counts | Validate | Contract violation |
| `SC-AC-SEQ18A-004-HP-001` | Disposable exact basenames | Bootstrap/preflight | Exact V0 then V1 |
| `SC-AC-SEQ18A-004-HP-002` | Exact disposable V1 | Publish/reconcile | Exact V2, then read-only |
| `SC-AC-SEQ18A-004-EP-001` | Fault after any atomic boundary | Rerun | Resume exact prefix only |
| `SC-AC-SEQ18A-005-NP-001` | Superseded dotted lease exists | Any command | Fail before write |
| `SC-AC-SEQ18A-005-NP-002` | Superseded dotted owner exists | Any command | Fail before write |
| `SC-AC-SEQ18A-005-NP-003` | Prior active formal leaf exists before implementation | Recheck | Amendment stale |
| `SC-AC-SEQ18A-005-NP-004` | Command/ID/path expands | Parse/dispatch | Reject |
| `SC-AC-SEQ18A-006-HP-001` | Complete implementation diff | Scope gate | Only planned files changed |
| `SC-AC-SEQ18A-006-HP-002` | Exact V2 | Formal gate | Candidate/root absent; stop |
| `SC-AC-SEQ18A-006-NP-001` | Parent O1 or old auth drifts | Any phase | Stop without cleanup |

## Implementation Phases and Gates

### Phase S18A-0 — amendment acceptance and exact freeze

- Recheck this amendment and ledger against separately accepted exact bytes.
- Recheck the parent plan, parent ledger, accepted old authorization, all
  thirteen O1 refs, and the three implementation baselines above.
- Reproduce `IMPLEMENTATION_BOUNDARY`, the all-false eight-leaf vector, and
  exactly two component-policy failures.
- Recheck both corrected paths and both superseded paths are absent.
- Recheck the distinct amendment authorization candidate path is absent.

**Gate:** no source or formal mutation; any formal leaf makes identity reuse
illegal and requires re-planning.

### Phase S18A-1 — fail-first component and supersession tests

- Add `TEST-192..199` and update the five affected parent-test expectations.
- Make `TEST-192` fail specifically because the current lease and owner begin
  with `.`.
- Make authorization/profile tests fail specifically because the active
  source still points to old authority and `270/70/631/16/647/963`.

**Gate:** controlled failures must match the amendment, not unrelated parent
O1, API, UI, dependency, or environment failures.

### Phase S18A-2 — old-authority execution interlock

- Add amendment/ledger refs after their exact-byte acceptance.
- Preserve the old authorization as an exact superseded ref.
- Add the distinct active authorization marker/schema/path and replay gates.
- Keep the new authorization candidate absent.
- Prove all four public commands reject the old document and the absent new
  document before opening any Tier destination.

**Gate:** old accepted authority has no executable path, corrected component
paths are not yet active, and every formal leaf remains absent.

### Phase S18A-3 — component, namespace, fixture, and geometry

- Extract the unchanged publisher predicate.
- Rename only the lease and owner constants.
- Add the pre-first-write eight-component validation.
- Add permanent absence checks for both superseded paths.
- Convert the disposable fixture to exact production basenames.
- Change the package to nine sorted members.
- Derive exact `270/73/634/16/650/966`.
- Keep all four commands and five IDs unchanged.

**Gate:** focused component, publisher-policy, rejected-path namespace, static
fixture-basename, and supersession tests pass without a real formal write.
Static package order and profile constants are exact. Authorization-bound
package/PAX and full disposable lifecycle tests remain one controlled failure
at the deliberately absent new authorization.

### Phase S18A-4 — candidate freeze and verification

- Recheck zero formal writes and exact parent O1.
- Generate the new authorization candidate only after source and tests
  stabilize.
- Reopen the candidate, then run the live nine-member package, PAX, projection,
  material, and descriptor-profile tests.
- Run the full production-basename disposable V0/V1/V2 and prefix-fault
  lifecycle only after the candidate reopens exactly.
- Run the coordinator twice at the implementation boundary.
- Run complete repository, recovery, syntax, Python 3.10, tabnanny,
  dependency, protected-ref, PAX, namespace, cleanup, and diff gates.
- Reproduce the deterministic nine-member PAX bytes twice.
- Compare the actual diff to this amendment.
- Recheck the old authorization remains exact.

Any edit to source, tests, parent/amendment plan or ledger, old
authorization, or new candidate invalidates the candidate and restarts this
phase.

**Gate:** `166/166`, zero implementation-caused failures, zero unexplained
scope drift, zero formal leaves.

### Phase S18A-5 — authorization handoff

- Report exact new candidate SHA-256, byte size, and mode.
- Require separate maintainer acceptance of those exact bytes.
- Immediately recheck both rejected and active formal path sets are absent.

**Gate:** no bootstrap or preflight before exact acceptance.

### Phase S18A-6 — amended bootstrap and V1 pause

- Under the lifecycle lock, repeat the zero-write identity-reuse check and
  validate all eight active components before step one.
- Bootstrap to exact `V0_BOOTSTRAPPED`.
- Preflight to exact `V1_INTAKE`.
- Run the full coordinator and protected-path gates.

**Gate:** both superseded paths, review, candidate, and root remain absent.

### Phase S18A-7 — publish and mandatory stop

- Publish the exact retained intake to manual review.
- Reopen exact `V2_REVIEW`.
- Run the full coordinator and final protected-ref checks.
- Stop.

**Gate:** candidate/root remain absent; no later authority is granted.

## Affected Files

### Planning outputs in this turn

```text
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence18-component-name-amendment.md
docs/superpowers/plans/2026-07-30-quant-radar-ui-ux-ux1b-task9-sequence18-component-name-amendment.traceability.yaml
.agents/scribe.md
.agents/judge.md
.agents/PROJECT.md
```

### Planned implementation edits after exact amendment acceptance

```text
scripts/ui_ux_theme_handoff.py
scripts/test_ui_ux_theme_handoff.py
docs/ui-ux/quant-radar-ui-v2-ux1b-sequence18-component-name-amendment-authorization.md
.agents/builder.md
.agents/scribe.md
.agents/judge.md
.agents/PROJECT.md
```

`Makefile` is an authenticated package member but is not an implementation
edit. Any Makefile drift blocks the amendment.

### Later formal outputs after new authorization acceptance

```text
.claude/ui_snapshots/ux1b/recovery/external-review-o1-lifecycle-test-correction-20260730T030000Z.lease
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-o1-lifecycle-test-correction-prechange-seq18.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-o1-lifecycle-test-correction-rollback-seq18.json
.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-o1-lifecycle-test-correction-prechange-20260730T031000Z/
.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-o1-lifecycle-test-correction-prechange-20260730T031000Z/quant-radar-theme-handoff-external-review-o1-lifecycle-test-correction-owner
.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-o1-lifecycle-test-correction-prechange-20260730T031000Z/prechange-files.tar
.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-o1-lifecycle-test-correction-prechange-20260730T031000Z/bundle-manifest.json
.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-o1-lifecycle-test-correction-preflight-20260730T030000Z.json
.claude/ui_snapshots/ux1b/recovery/control-migration-manual-review-20260729T060000Z.json
```

### Protected read-only paths

```text
Makefile
parent Sequence 18 plan and ledger
accepted superseded Sequence 18 authorization
all thirteen exact Sequence 17 O1 references
all Sequence 8-17 plans, ledgers, authorizations, Tier, preflights, reports,
packets, intakes, reviews, candidates, roots, captures, images, and sidecars
all production ui/, api/, provider, data, fixture, selector, and theme files
requirements.txt
.venv/
```

## Verification Commands

Minimum implementation checks:

```bash
.venv/bin/python -B scripts/test_ui_ux_theme_handoff.py
make test
make ui-ux1b-recovery-tests
.venv/bin/python -B scripts/ui_ux_theme_handoff.py verify-python-syntax --json
.venv/bin/python -B -m tabnanny scripts/ui_ux_theme_handoff.py scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -B -m pip check
git diff --check
```

Python 3.10 compatibility must use an actual Python 3.10 interpreter when
available. Otherwise both changed Python files must pass
`ast.parse(..., feature_version=(3, 10))`, and the limitation must be
reported.

Additional mandatory gates:

- exact parent plan, ledger, old authorization, and thirteen O1 refs;
- exact old and new component path absence before authorization;
- unchanged publisher accept/reject corpus, including 128/129 boundary;
- all eight active component names accepted before any write;
- old authorization replay and superseded paths rejected before write;
- post-interlock/pre-candidate execution rejects all four public commands;
- exact nine-member sorted deterministic PAX reproduction;
- exact `270/73/634/16/650/966` profile;
- coordinator `166/166` twice after candidate freeze;
- implementation-boundary, disposable V0/V1/V2, prefix-fault, and read-only
  V2 reconciliation;
- original soft descriptor limit restored after every transaction;
- no owned process, temporary file, or test directory remains;
- no Make, UI, API, provider, fixture, selector, image, sidecar, theme,
  dependency, or runtime-tree drift;
- both superseded paths, candidate, and root always absent;
- actual diff contains only accepted amendment files.

## Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---:|---|
| Relaxing the global publisher to allow hidden components | High | Keep the exact existing regex and add accept/reject regression corpus |
| Editing or overwriting accepted authority | High | Preserve old file exact; create distinct path/marker/schema |
| Replaying old accepted authority after source changes | High | Active parser requires exact supersession and rejects old marker/path |
| Fixture still hides production names | High | Derive disposable paths from exact production basenames and use real publisher |
| Reusing IDs after a nonzero write | High | Four all-path absence checks; any drift forces re-planning |
| Superseded hidden path appears later | High | Permanent rejected-path set checked by every lifecycle entry/classifier |
| Descriptor profile omits new docs | High | Exact six-content delta and `270/73/634/16/650/966` mutation tests |
| Common helper extraction changes old behavior | Medium | Predicate is byte-for-byte-equivalent policy; existing publisher tests remain |
| PAX order becomes non-deterministic | Medium | Nine exact lexicographically ordered members, double reproduction |
| Planning mistaken for formal authority | Medium | Separate amendment acceptance and later authorization acceptance |

## Rollback and Recovery

### Before amendment implementation acceptance

- Preserve the exact incident boundary.
- Planning files may be revised through review.
- Do not modify source, old authorization, or formal namespace.

### During implementation

- Revert only explained amendment edits through the normal worktree workflow.
- Never delete or hide a formal leaf to make the zero-write check pass.
- Never restore predecessor PAX over the live worktree.
- If parent O1, old authorization, Makefile, or any formal path drifts, stop
  and re-plan.

### After candidate generation

- Treat any source, test, plan, ledger, old-auth, or candidate edit as
  invalidating the candidate.
- Preserve the candidate for audit or replace it only through an explicitly
  documented new freeze; never claim the old digest remains valid.

### After amended Tier

- Resume only exact corrected-name prefixes under the lifecycle lock.
- Do not rename an old dotted leaf into the active path.
- Stop on any non-prefix, different-byte, unexpected-member, or superseded
  path shape.

### After V1 or V2

- Follow the parent Sequence 18 preflight/publication rollback contract.
- V2 remains a mandatory stop with no candidate/root authority.

## Traceability Matrix

| Requirement | Acceptance | Implementation | Tests |
|---|---|---|---|
| `REQ-020` | `AC-SEQ18A-001`, `AC-SEQ18A-002`, `AC-SEQ18A-003`, `AC-SEQ18A-004`, `AC-SEQ18A-005`, `AC-SEQ18A-006` | `IMPL-153`, `IMPL-154`, `IMPL-155`, `IMPL-156`, `IMPL-157`, `IMPL-158`, `IMPL-159`, `IMPL-160` | `TEST-192`, `TEST-193`, `TEST-194`, `TEST-195`, `TEST-196`, `TEST-197`, `TEST-198`, `TEST-199` |
| `CFR-097` | `AC-SEQ18A-001`, `AC-SEQ18A-004`, `AC-SEQ18A-005` | `IMPL-153`, `IMPL-154`, `IMPL-155`, `IMPL-158`, `IMPL-160` | `TEST-192`, `TEST-195`, `TEST-196`, `TEST-197`, `TEST-198` |
| `CFR-098` | `AC-SEQ18A-002`, `AC-SEQ18A-005` | `IMPL-156`, `IMPL-159`, `IMPL-160` | `TEST-193`, `TEST-198`, `TEST-199` |
| `CFR-099` | `AC-SEQ18A-003`, `AC-SEQ18A-005` | `IMPL-157`, `IMPL-159`, `IMPL-160` | `TEST-194`, `TEST-198`, `TEST-199` |
| `CFR-100` | `AC-SEQ18A-004`, `AC-SEQ18A-005` | `IMPL-158`, `IMPL-159`, `IMPL-160` | `TEST-195`, `TEST-196`, `TEST-197`, `TEST-199` |
| `CFR-101` | `AC-SEQ18A-005`, `AC-SEQ18A-006` | `IMPL-154`, `IMPL-155`, `IMPL-159`, `IMPL-160` | `TEST-197`, `TEST-198`, `TEST-199` |

## Success Metrics

| Metric | Target | Measurement |
|---|---:|---|
| Active invalid component names | `0` | Exact eight-component policy test |
| Superseded paths present | `0` | Namespace/classifier gate |
| Old authorization bytes changed | `0` | Exact hash/size/mode |
| Formal writes before new acceptance | `0` | All-path presence vector |
| Package members | `9` | Deterministic PAX member audit |
| Source/supplemental/content/authority/retained/floor | `270/73/634/16/650/966` | Authenticated material builder |
| Coordinator failures | `0` | `166/166` twice after freeze |
| Traceability coverage | `10000` basis points | Amendment ledger validator |
| Unexplained diff paths | `0` | Accepted amendment versus actual diff |
| Candidate/root leaves | `0` | Namespace gate |

## Dependencies

- Exact parent plan, ledger, accepted old authorization, and thirteen O1
  references.
- Existing publisher, no-follow path, global lock, lease, retained-descriptor,
  canonical JSON, PAX, CLI dispatcher, and source-projection primitives.
- Existing four public Sequence 18 Make routes.
- Current Python virtual environment and macOS filesystem semantics.
- Separate exact-byte amendment acceptance before implementation.
- Separate exact-byte superseding authorization acceptance before formal
  bootstrap.

## Glossary

| Term | Meaning |
|---|---|
| Component | Final basename passed to `_publish_regular_exact` |
| Superseded path | Dot-leading rejected Sequence 18 path retained only as negative history |
| Active path | Corrected alphanumeric-leading Sequence 18 path |
| Superseded authorization | Accepted old candidate that made zero writes and is no longer active |
| Production-shaped fixture | Disposable parent combined with exact production basenames and real publisher |
| Zero-write boundary | All eight Sequence 18 Tier/preflight leaves and both old dotted paths are absent |
| Identity reuse | Reusing the Sequence 18 correction/Tier IDs only because zero formal bytes were committed |

## Review Checklist

- [x] Failure and zero-write boundary are reproducibly grounded.
- [x] Exactly two components change and both satisfy the unchanged policy.
- [x] Global publisher behavior is not broadened.
- [x] Old authorization remains immutable and cannot replay.
- [x] Old authorization is disabled before corrected paths become active.
- [x] Corrected and superseded paths are disjoint and collision-free.
- [x] Identity reuse is gated at four exact absence checkpoints.
- [x] Package membership and descriptor arithmetic include all six additions.
- [x] Production-shaped tests use real basenames and publisher.
- [x] Affected files, formal outputs, and protected paths are explicit.
- [x] Candidate freeze precedes final coordinator/PAX/profile gates.
- [x] Parent requirements not superseded here remain active.
- [x] Requirements, ACs, scenarios, implementation, and tests are
      bidirectionally traceable.
- [x] No unresolved Critical, High, or Medium review finding remains.
- [ ] Maintainer separately accepts exact amendment and ledger bytes.

## Review Findings

The review used a blocker-first local evidence pass. Higher-priority workspace
policy prohibited subagent delegation, so Judge multi-engine fan-out was not
performed and this is not represented as an independent review.

### Round 1 findings and closure

| Finding | Severity | Resolution |
|---|---:|---|
| Renaming components before disabling the already accepted old authorization could expose a transient replay path. | High | Added a mandatory source-transition interlock: active path/marker/schema switch to an absent new candidate first; old authority and all four commands must fail before corrected paths are installed. |
| The draft required the nine-member PAX/profile and authorization-bound lifecycle to pass while the new authorization member was deliberately absent. | High | Split the gate: static/fail-closed checks run before candidate creation; live PAX, geometry, and V0/V1/V2 run only after the frozen candidate reopens exactly. |
| Parent supersession named `CFR-094` and `CFR-096` but omitted the affected atomic-material clauses in `CFR-095` and parent ACs. | Medium | Limited supersession now explicitly names only the affected clauses of `CFR-094..096` and `AC-SEQ18-004/005/007/008`. |
| Abbreviated IDs in the traceability matrix made exact reciprocal validation ambiguous. | Medium | Expanded every requirement, AC, implementation, and test ID in the matrix. |
| The initial gate did not explicitly require the distinct new authorization path to be absent. | Medium | Added candidate-path absence to the grounded incident and Phase S18A-0. |

### Round 2 result

Round 2 rechecked authorization transition ordering, component grammar,
old/new path disjointness, zero-write identity reuse, package order,
cardinality arithmetic, candidate/PAX ordering, affected files, rollback,
formal pause, and reciprocal traceability. No unresolved Critical, High,
Medium, or actionable Low finding remains.

Grounded evidence:

- current classifier is exact `IMPLEMENTATION_BOUNDARY`;
- the eight current Tier/preflight leaves are all absent;
- exactly two current basenames fail the unchanged publisher rule;
- both corrected paths, both superseded paths, and the new authorization path
  are absent;
- parent plan, ledger, old authorization, source, tests, and Makefile match
  the exact metadata in this amendment;
- the nine proposed package paths are lexicographically ordered;
- the canonical ledger contains 6 requirements, 6 acceptance criteria, 19
  scenarios, 8 implementation nodes, and 8 tests with reciprocal direct
  edges, 10000 basis points, zero gaps, and zero orphans.

```text
intent_alignment: PASS
CRITICAL: 0 unresolved
HIGH:     0 unresolved
MEDIUM:   0 unresolved
LOW:      0 actionable
INFO:     local evidence review only; no subagent/multi-engine claim
verdict:  APPROVE FOR SEPARATE EXACT-BYTE AMENDMENT ACCEPTANCE
```

This review approves the plan package for a maintainer acceptance decision.
It does not authorize source implementation or formal execution.

## Change History

| Version | Date | Change |
|---|---|---|
| `0.1-review-candidate` | 2026-07-30 | Initial narrow component-name, supersession, production-fixture, and geometry amendment |
| `0.2-review-candidate` | 2026-07-30 | Closed old-authority transition, candidate/PAX ordering, parent-supersession, traceability, and candidate-absence findings |
| `1.0-reviewed` | 2026-07-30 | Round 2 found no unresolved blocker; frozen for separate exact-byte maintainer acceptance |

## Next Handoff

After blocker review:

1. Freeze this amendment and its ledger.
2. Report their exact SHA-256, size, and mode.
3. Wait for separate maintainer exact-byte acceptance.
4. Hand the accepted amendment to Builder for implementation.
5. Later report and separately accept the superseding authorization candidate
   before formal bootstrap.
