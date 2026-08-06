# Quant Radar UX-1B Sequence 16 E0 Lifecycle-Test Correction Continuation

## Document information

| Field | Value |
| --- | --- |
| Type | Corrective implementation plan and execution checklist |
| Version | `1.0-locally-reviewed` |
| Status | `LOCALLY REVIEWED — IMPLEMENTATION NOT STARTED` |
| Date | `2026-07-29` |
| Authorization | Repository maintainer requested creation of a reviewed lifecycle-test correction continuation |
| Author | Scribe |
| Plan reviewer | Local deterministic contract review; no independent Judge or multi-engine claim |
| Approver | Repository maintainer |
| Audience | Maintainers, implementers, test reviewers, and the later independent evidence reviewer |
| Sequence | `16` |
| Parent Sequence | Exact accepted Sequence 15 at `E0_PACKET` |
| Capture ID | `20260729T040000Z` |
| Packet continuation ID | `20260729T060000Z` |
| Parent external-review correction ID | `20260729T070000Z` |
| Lifecycle-test correction ID | `20260729T080000Z` |
| Lifecycle-test Tier ID | `20260729T081000Z` |
| Formal stop | `C2_REVIEW` |
| Related ledger | `docs/superpowers/plans/2026-07-29-quant-radar-ui-ux-ux1b-task9-sequence15-e0-lifecycle-test-correction-continuation.traceability.yaml` |

This plan is not implementation or formal execution authority. It authorizes
no source edit until blocking review is closed and the repository maintainer
separately accepts this reviewed plan for implementation. Formal Sequence 16
bootstrap, reviewer intake, and review publication later require separate
acceptance of an exact authorization document by whole-file SHA-256, byte
size, and mode.

The review provenance is intentionally narrow. The current session policy
does not permit subagent delegation, so this document received three local,
deterministic blocker-review passes. It does not claim independent Judge,
dual-engine, or multi-engine review.

## Purpose

Sequence 15 implementation passed `128/128` coordinator tests before formal
execution. After the maintainer accepted the exact authorization, Sequence 15
successfully created and read-only reopened its Tier and preflight at
`E0_PACKET`. The same permanent coordinator suite then passed `127/128`.

`TEST-161` still asserts that every Sequence 15 Tier and preflight path must
remain absent forever. That assertion was valid only at the implementation
boundary. It is false after the reviewed Phase S15-7 bootstrap/preflight
transition.

The obvious one-line test edit is unsafe. Sequence 15 preflight freezes exact
current records for:

```text
scripts/test_ui_ux_theme_handoff.py
  SHA-256 ef6826bf72977e68db62621719803c38651b9a0a78fa2972baa84aa2bb0c9936
  size   1154917
  mode   0444 in the source projection

scripts/ui_ux_theme_handoff.py
  SHA-256 93745f3fc6ecd9f040b8cc1d9ee22a190444b5259085e114c018b016e8c5a78c
  size   1537503
  mode   0444 in the source projection

Makefile
  SHA-256 d8610763c0189662769bf98b091995ca7fea013804e57f12041ca13b06f85ab8
  size   49908
  mode   0444 in the supplemental projection
```

Editing any of those files makes the live Sequence 15 preflight validator
correctly fail closed. Sequence 16 therefore must:

- import the exact retained Sequence 15 `E0_PACKET` as immutable historical
  authority without rebuilding its source/runtime projections;
- replace the implementation-only `TEST-161` absence assertion with a closed
  permanent lifecycle oracle;
- freeze corrected current source/runtime under a distinct Sequence 16
  authority;
- take authority over only the still-absent shared intake and manual-review
  paths;
- retain the exact Sequence 14 report and packet without capture or compare;
- preserve the Sequence 15 atomic broker, reviewer isolation, four-quadrant
  decision truth, and create-once publication behavior;
- stop at `C2_REVIEW` with candidate and root absent.

## Scope

### In scope

- Exact whole-file historical import of the accepted Sequence 15 plan,
  ledger, authorization, Tier, preflight, report, and packet.
- Exact validation of the embedded Sequence 15 source, supplemental, runtime,
  Make, namespace, reviewer, descriptor, and parent-H2 records without reading
  the old source members as current authority.
- A lifecycle-aware permanent `TEST-161` oracle that accepts only:
  - the wholly absent pre-formal Sequence 15 Tier with parent `E0_PACKET`; or
  - the exact complete retained Sequence 15 Tier/preflight imported as
    `S15_E0_PACKET`.
- A distinct Sequence 16 authorization candidate, deterministic PAX Tier,
  preflight, lease, source/runtime projections, command set, and Make routes.
- Reuse of the existing six forward paths, with Sequence 16 taking
  create-once ownership only of the still-absent intake and manual-review
  leaves.
- A new reviewer appointment/session and a new immutable 24-hour review
  deadline created by Sequence 16 preflight.
- Parameterization of the existing strict review validator, retained-material
  transaction, intake broker, and review publisher without changing Sequence
  15 or legacy public behavior.
- Exact current material cardinality of `291 + 270 + 64 = 625` unique leaves.
- Descriptor budget `625 + 252 + 64 = 941`, bounded by the existing `1536`
  ceiling, with exact soft-limit restoration.
- Complete targeted, coordinator, fail-soft API/UI, syntax, dependency,
  source-scope, runtime, cleanup, formal-absence, and protected-hash gates.

### Out of scope

- Editing, deleting, chmodding, replacing, or regenerating any Sequence 15
  authorization, Tier, preflight, report, packet, or predecessor artifact.
- Reopening Sequence 15 through its live source validator after current source
  changes.
- Treating the new source as proof that the historical Sequence 15 source
  projection was current.
- Capture, recapture, browser launch, compare, packet rebuild, image rewrite,
  sidecar rewrite, UI change, API change, provider change, dependency change,
  candidate publication, root publication, or theme application.
- Writing intake or review during implementation or authorization-candidate
  preparation.
- Reusing the expired or soon-to-expire Sequence 15 reviewer deadline.
- Letting a test hide, move, delete, or temporarily replace formal artifacts.
- Weakening `TEST-161` to accept arbitrary partial Tier, preflight, intake,
  review, candidate, or root states.
- Claiming that local plan review is independent Judge review.

## Non-goals

- Sequence 16 does not repair a visual discrepancy or predetermine the review
  decision.
- Sequence 16 does not recapture any of the `81` page or `44` control-root
  items.
- Sequence 16 does not change the `125`-item packet, prompt, schema, ordering,
  item IDs, or evidence bytes.
- Sequence 16 does not make the old Sequence 15 live validator pass after
  source evolution.
- Sequence 16 does not authorize candidate or root work after `C2_REVIEW`.
- Sequence 16 does not use test-only path hiding as a completion gate.

## Glossary

| Term | Definition |
| --- | --- |
| Parent E0 | Exact retained Sequence 15 Tier/preflight at `E0_PACKET`, with report/packet present and intake/review/candidate/root absent when Sequence 16 initial authority is created. |
| Historical E0 import | Exact byte, metadata, schema, cross-link, embedded-projection, and archive validation that never compares frozen Sequence 15 source members with changed current source. |
| Live Sequence 15 validation | The old validator that rebuilds current source/runtime projections; it must fail closed after Sequence 16 changes the frozen files. |
| Permanent lifecycle oracle | A real-workspace test that authenticates valid monotonic states instead of assuming creation-time absence forever. |
| Shared forward paths | The existing report, packet, intake, review, candidate, and root paths originally reserved by Sequence 14/15. |
| Active authority | Sequence 16 source/runtime/preflight authority used for new intake and review operations. |
| Historical fact | An exact retained document or artifact proven by whole-file bytes and internal consistency, not by current live-member equality. |
| Formal pause | The mandatory Sequence 16 stop at `C2_REVIEW`; candidate and root remain forbidden. |

## Verified starting state

### Exact accepted Sequence 15 E0 authority

| Artifact | SHA-256 | Bytes | Mode |
| --- | --- | ---: | --- |
| Sequence 15 plan | `e8813f114b03e6a1ba3b82309d58f243fc53e96d842c6c2c57487114ddc60e0d` | `66419` | `0644` |
| Sequence 15 ledger | `2cf17ed0bbb62914ac0807b6b2169170a1b5f7668a8d8153f46fedd31b33ed2d` | `7986` | `0644` |
| Accepted Sequence 15 authorization | `c88b4a1aafeac3d282af2010bf40acd151bdf27fbdbd6e61db3c8cef6d30d2e5` | `7629` | `0644` |
| Sequence 15 lease | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `0` | `0600` |
| Sequence 15 prechange | `97f1d165b7cf6a2862e528a119c8fa55a8e2e31f986e40949a633688b6c755cb` | `5600` | `0600` |
| Sequence 15 rollback | `5fda42756cdbc4828d198e18d4fb82e99694713ef5d4c4ebba33c375a99fa5ad` | `2470` | `0600` |
| Sequence 15 archive owner | `b9f9467595e79facb249dfb7cf79790c3dd07bc1ba44fba89b2c4382c2f2f40b` | `182` | `0600` |
| Sequence 15 PAX archive | `15a4bee9a1a2df0b0390e03d4d93c33595f903d6f0b930388e7bdfe4e84e1ce9` | `2836480` | `0600` |
| Sequence 15 bundle manifest | `677c698d90d9b183f7b40304f1d86f557c506dc6eabe17457b3739bfbd75ed95` | `1216` | `0600` |
| Sequence 15 preflight | `21b2ba6fed6e84f820feb1a091348be6e7be7c048d196fb79ef5d7489264485a` | `65278` | `0600` |
| Sequence 14 migration report | `97a37c01a7fefbaf20386a6bb732e87993e8f282ba3216885ad92f2530a7f553` | `12444` | `0600` |
| Sequence 14 review packet | `1a9f1a3c995c04d5db1137e25f861a333483a9ba2bb83176532f87a74cc024dd` | `89295` | `0600` |

The Sequence 15 preflight has:

```text
createdAt       = 2026-07-29T13:02:33Z
reviewDeadline  = 2026-07-30T13:02:33Z
initialState    = E0_PACKET
formalPause     = E2_REVIEW
source records  = 270
supplemental    = 61
retained leaves = 622
descriptor floor= 938
```

The old deadline is historical input only. Sequence 16 must not use it for a
new initial intake.

The retained Sequence 15 plan, authorization, and formal artifacts have the
accepted current-user group. The retained Sequence 15 ledger has accepted
`gid=0`. Historical import must authenticate that existing mixed-group fact
without chmod, chown, normalization, or a blanket current-GID requirement.
New Sequence 16 source and formal files still require the current owner/group
policy at creation.

### Exact forward presence

```text
report        present and exact
packet        present and exact
intake        absent
manual review absent
candidate     absent
root          absent
```

The shared forward paths remain:

```text
0 .claude/ui_snapshots/ux1b/recovery/control-migration-20260729T060000Z.json
1 .claude/ui_snapshots/ux1b/recovery/control-migration-review-packet-20260729T060000Z.json
2 .claude/ui_snapshots/ux1b/review-intake/control-migration-20260729T060000Z.json
3 .claude/ui_snapshots/ux1b/recovery/control-migration-manual-review-20260729T060000Z.json
4 .claude/ui_snapshots/ux1b/recovery/theme-handoff-candidate-20260729T060000Z.json
5 docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json
```

### Reproduced blocker

`TEST-161` currently contains both permanent assertions:

```python
assert all(
    not (ROOT / path).exists()
    for path in handoff.EXTERNAL_REVIEW_TIER_DESTINATIONS[1:]
)
assert all(
    not (ROOT / path).exists()
    for path in handoff.EXTERNAL_REVIEW_FORWARD_PATHS[2:]
)
```

The first assertion rejects every legitimate Sequence 15 Tier/preflight
state. The second would later reject legitimate `E1_INTAKE` and `E2_REVIEW`.
The test must authenticate a lifecycle, not erase or ignore it.

## Authority design

### Fixed Sequence 16 identifiers

```text
captureId                         20260729T040000Z
packetContinuationId              20260729T060000Z
parentExternalReviewCorrectionId  20260729T070000Z
lifecycleTestCorrectionId         20260729T080000Z
lifecycleTestTierId               20260729T081000Z
reviewSessionId                   seq16-20260729T080000Z-review-01
```

Callers must supply all public IDs exactly. No ID is derived from wall clock,
packet contents, caller-selected path, or existing file name.

### Historical parent importer

Add one closed internal importer:

```text
_import_sequence15_e0_preflight(
    workspace_fd,
    *,
    source_root_fd,
    require_initial,
) -> S15_E0_PACKET
```

It must:

1. open every listed Sequence 15 artifact descriptor-relative and no-follow;
2. require regular file/directory type, exact owner policy, nlink, mode, size,
   SHA-256, and named identity;
3. parse the exact PAX archive descriptor-only with exact six-member order,
   path, type, size, mode, and payload digest;
4. parse the authorization, Tier JSON, preflight JSON, report, and packet from
   exact bytes;
5. validate all internal IDs, paths, cross-links, schema names, counts,
   source/supplemental records, runtime receipt, descriptor profile,
   appointment, namespace inventory, and `E0_PACKET`/`E2_REVIEW` claims;
6. require report `81`, root `44`, total `125`, packet inputs `5`, packet items
   `125`, and exact report/packet refs;
7. when `require_initial=True`, require the current shared prefix to be
   exactly report+packet with intake/review/candidate/root absent;
8. when `require_initial=False`, continue to require candidate/root absent,
   while leaving intake/review ownership to the Sequence 16 active classifier;
9. return immutable parsed values and exact refs under classification
   `S15_E0_PACKET`.

The importer must not call:

```text
_build_external_review_source_projections
_build_external_review_preflight_value
_validate_external_review_preflight_value
_reauthenticate_external_review_preflight
_validate_external_review_tier_complete
```

It must not open any path named only by an embedded frozen source or
supplemental record. Exact parent document bytes authenticate those historical
records; current Sequence 16 builders separately authenticate current source.

### Permanent TEST-161 lifecycle contract

`TEST-161` must retain formal-boundary coverage while replacing total absence
with this closed truth:

| Sequence 15 Tier/preflight shape | Shared forward shape | Result |
| --- | --- | --- |
| All Tier/preflight absent | Exact report+packet only | Valid implementation boundary |
| Complete exact Tier, preflight absent | Exact report+packet only | Valid bootstrap boundary |
| Complete exact Tier and exact preflight | Sequence 16 classifier says exact E0/E1/E2 | Valid retained historical parent |
| Any partial Tier | Any | Reject |
| Preflight without complete Tier | Any | Reject |
| Intake/review without exact Sequence 16 active authority | Any | Reject in Sequence 16 tests |
| Candidate or root present | Any | Reject |

When Sequence 16 seams exist, the real-workspace branch must use
`_import_sequence15_e0_preflight()` instead of the old live Sequence 15
preflight validator. Mutation coverage for creation-time absence remains in
disposable directories; the permanent workspace oracle never moves or deletes
formal artifacts. The historical importer validates the exact retained
Sequence 15 PAX. `TEST-161` must not rebuild a new Sequence 15 archive from
changed current source. Deterministic current Sequence 16 PAX coverage belongs
to `TEST-170`.

### Distinct active authority

Implementation will generate this authorization candidate only after all
implementation gates pass:

```text
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-lifecycle-test-correction-seq16.md
```

Its canonical body must bind:

- `sequence=16` and all fixed IDs;
- exact Sequence 15 E0 plan, ledger, authorization, Tier, preflight, report,
  and packet refs;
- exact Sequence 16 plan and ledger refs;
- exact six-path source package;
- the shared forward paths and three exact active states;
- the new reviewer ID/session and immutable new deadline policy;
- review-packet v2 and manual-review v2 schemas;
- `reviewItems=125`, `inputs=5`, `pageItems=81`,
  `controlRootItems=44`;
- `625` retained leaves, `252` protocol allowance, `64` reserve, `941`
  required soft floor, and `1536` ceiling;
- exactly five allowed Sequence 16 commands;
- `formalPause=C2_REVIEW`;
- no capture, compare, candidate, or root authority;
- precedence: Sequence 16 active authority, exact Sequence 15 E0 history,
  exact Sequence 14 H2 history, earlier retained history.

The authorization document is a candidate only until the maintainer accepts
its exact SHA-256, byte size, and mode.

### Source package

The deterministic Sequence 16 PAX package contains exactly:

```text
Makefile
docs/superpowers/plans/2026-07-29-quant-radar-ui-ux-ux1b-task9-sequence15-e0-lifecycle-test-correction-continuation.md
docs/superpowers/plans/2026-07-29-quant-radar-ui-ux-ux1b-task9-sequence15-e0-lifecycle-test-correction-continuation.traceability.yaml
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-lifecycle-test-correction-seq16.md
scripts/test_ui_ux_theme_handoff.py
scripts/ui_ux_theme_handoff.py
```

Use deterministic PAX, not USTAR. Member order is exactly the order above.
Each regular member has canonical metadata and payload bytes. Two builds from
the same source must be byte-identical.

### Tier and preflight namespace

Sequence 16 uses distinct create-once paths:

```text
.claude/ui_snapshots/ux1b/recovery/.external-review-lifecycle-test-correction-20260729T080000Z.lease
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-lifecycle-test-correction-prechange-seq16.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-lifecycle-test-correction-rollback-seq16.json
.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-lifecycle-test-correction-prechange-20260729T081000Z/
.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-lifecycle-test-correction-preflight-20260729T080000Z.json
```

The Tier directory contains exactly owner marker, deterministic PAX archive,
and bundle manifest. Bootstrap is create-once and idempotently reopens exact
bytes. Preflight is create-once, stores one `createdAt`, derives one
`reviewDeadline=createdAt+86400s`, and reopens without consulting ambient
time.

Before first Sequence 16 preflight:

- Sequence 15 E0 import must pass with `require_initial=True`;
- the complete Sequence 16 Tier must reauthenticate;
- shared intake/review/candidate/root must be absent;
- current source/runtime/Make/projections must be exact;
- reviewer sandbox must be available;
- the descriptor hard limit must support `941`.

### Active state machine

Sequence 16 owns only three active states:

```text
C0_PACKET = [report, packet, -,      -,      -, -]
C1_INTAKE = [report, packet, intake, -,      -, -]
C2_REVIEW = [report, packet, intake, review, -, -]
```

All other `64 - 3 = 61` existence patterns fail. Candidate or root presence
always fails. State names are distinct from Sequence 15 `E0..E2` so logs and
receipts cannot misrepresent which authority validated current source.

### Shared forward-path ownership

The Sequence 15 E0 checkpoint retains historical ownership of its Tier and
preflight. It grants no new writes after source drift.

Sequence 16 may take create-once ownership of the shared intake and review
paths only when:

1. exact Sequence 15 E0 historical import passes;
2. Sequence 16 Tier/preflight/current source/runtime pass;
3. the active prefix is exactly `C0_PACKET`;
4. candidate and root are absent;
5. the global lock and Sequence 16 lease are held;
6. the submitted bytes match the maintainer-accepted candidate digest and
   size for the new reviewer session.

Old Sequence 15 submit/publish commands must fail closed after current source
changes. Generic and legacy review publishers remain unchanged and cannot
consume the shared paths.

### Reviewer appointment and freshness

Sequence 16 creates a new appointment:

```text
reviewer type  independent-code-reviewer
reviewer ID    judge-seq16-control-migration@seq16-20260729T080000Z-review-01
session ID     seq16-20260729T080000Z-review-01
packet path    exact shared packet path
packet SHA     1a9f1a3c995c04d5db1137e25f861a333483a9ba2bb83176532f87a74cc024dd
```

Initial `C0_PACKET -> C1_INTAKE` submission must satisfy:

- `createdAt <= reviewedAt <= reviewDeadline`;
- `reviewedAt <= brokerNow+300s`;
- `brokerNow <= reviewDeadline+300s`;
- exact appointed reviewer/session;
- exact accepted candidate SHA-256 and size;
- canonical manual-review v2 bytes and complete four-quadrant truth.

Exact committed `C1_INTAKE` and `C2_REVIEW` reruns are read-only and do not
reapply ambient-time freshness.

### Review validator compatibility

Extract or parameterize one strict internal validator so the expected
appointment is supplied by the active preflight. Preserve a Sequence 15
wrapper with identical signature and behavior for existing callers/tests.

The validator must still enforce:

- canonical manual-review v2 bytes;
- exact packet path, digest, size, prompt, inputs, item set, and `125` order;
- exact reviewer type and authority-supplied ID/session;
- nonempty per-item explanations;
- unique nonempty finding IDs and summaries;
- accepted iff no rejected item and no unresolved High/Medium finding;
- rejected iff either rejection signal exists;
- accepted candidate digest/size binding.

### Material transaction and descriptor budget

Parameterize retained-leaf cardinality from the authenticated descriptor
profile instead of one global Sequence 15 constant.

Sequence 15 remains:

```text
622 retained + 252 protocol + 64 reserve = 938
```

Sequence 16 becomes:

```text
291 packet + 270 source + 64 supplemental = 625 retained
625 retained + 252 protocol + 64 reserve = 941
```

Both must:

- raise only as needed and never above `1536`;
- retain every content descriptor under lock/lease through commit;
- use no-follow descriptor-relative traversal;
- validate regular type, owner policy, nlink, safe mode, size, SHA-256, and
  named device/inode identity before and after commit;
- close every descriptor and restore the exact original limit on every exit.

Any implementation-time cardinality different from `625/941` is a blocking
plan mismatch. Do not silently update constants or weaken the gate.

### Atomic broker and review publication

Expose exactly five commands:

```text
bootstrap-external-review-lifecycle-test-correction
preflight-external-review-lifecycle-test-correction
verify-external-review-lifecycle-test-correction-preflight
submit-lifecycle-test-corrected-review-intake
publish-lifecycle-test-corrected-review
```

The first three manage distinct Sequence 16 Tier/preflight authority. The
last two reuse the existing bounded-stdin, canonical validation, no-replace
publication, parent fsync, exact collision, uncertain-commit reconcile, and
different-inode review semantics through authority-specific callbacks.

Public callers cannot supply a destination path, reviewer ID, session ID,
packet path, clock window, descriptor count, candidate/root flag, or legacy
route.

## Requirements

### `REQ-017` — restore a verifiable external-review continuation

The system must preserve exact Sequence 15 E0 history, repair the permanent
lifecycle-test contract, and provide a distinct current authority that can
reach review without capture, candidate, or root work.

### `CFR-079` — immutable history

Sequence 15 formal bytes and embedded frozen projections must remain exact.
Historical import must use zero current reads of frozen source-member paths.

### `CFR-080` — lifecycle completeness

Permanent tests and production classifiers must accept every authorized
monotonic state and reject every partial, skipped, candidate, or root state.

### `CFR-081` — current integrity

Sequence 16 must bind current source/runtime and retain all `625` material
leaves through any intake or review commit with a `941` descriptor floor.

### `CFR-082` — compatibility and atomicity

Legacy, Sequence 15, and generic routes must remain behaviorally unchanged;
only new Sequence 16 commands may consume the still-absent shared leaves.

### `CFR-083` — reviewer governance and scope

The new reviewer session, immutable deadline, accepted candidate digest,
read-only reviewer workspace, and `C2_REVIEW` pause must be exact.

### `CFR-084` — deterministic package and verification

Plan, ledger, authorization candidate, PAX package, tests, source scope, and
all verification outputs must be deterministic and machine-checkable.

## Acceptance criteria

### `AC-SEQ16-001` — exact parent E0 import

Given exact retained Sequence 15 E0 bytes and changed current source, when the
Sequence 16 parent importer runs, then it returns `S15_E0_PACKET`, validates
all embedded contracts, performs zero frozen live-member reads, and writes
nothing.

### `AC-SEQ16-002` — permanent lifecycle oracle

Given any Sequence 15 Tier/preflight and shared-forward presence pattern, when
the permanent oracle runs, then only the closed authorized historical/current
combinations pass. Partial Tier, unauthorized intake/review, candidate, and
root fail without moving formal artifacts.

### `AC-SEQ16-003` — distinct current authority

Given accepted exact Sequence 16 authorization and exact parent E0, when
bootstrap/preflight run, then distinct Tier/preflight reach `C0_PACKET`, bind
current source/runtime, expose exactly five commands, and leave shared
intake/review/candidate/root absent.

### `AC-SEQ16-004` — governed atomic intake

Given exact `C0_PACKET`, new appointment/session/deadline, read-only reviewer
workspace, and maintainer-accepted candidate bytes, when the broker receives
bounded stdin, then it atomically creates the exact intake and reaches
`C1_INTAKE`. Invalid, stale, partial, collided, or precommit-failed input does
not consume the path.

### `AC-SEQ16-005` — retained material integrity

Given any initial commit or exact reconcile, when material verification runs,
then exactly `625` current leaves remain descriptor/name/hash exact with a
`941` floor and exact limit restoration.

### `AC-SEQ16-006` — exact manual-review publication

Given exact `C1_INTAKE`, when publication runs, then it creates one
byte-identical different-inode review, propagates the exact accepted/rejected
decision, reopens read-only at `C2_REVIEW`, and leaves candidate/root absent.

### `AC-SEQ16-007` — compatibility and fail-closed predecessor

Given corrected current source, when old Sequence 15 live verification or
submit runs, then it fails closed. The exact historical importer and new
Sequence 16 commands pass; legacy routes remain unchanged.

### `AC-SEQ16-008` — exact implementation boundary

Given the complete planned implementation, when all focused, coordinator,
fail-soft, static, dependency, scope, cleanup, protected-hash, and PAX gates
run, then all pass with zero unauthorized formal write. Only an authorization
candidate may exist before separate exact acceptance.

## Planned implementation artifacts

| ID | Responsibility |
| --- | --- |
| `IMPL-125` | Exact whole-file Sequence 15 E0 historical importer and retained archive parser |
| `IMPL-126` | Lifecycle-aware `TEST-161` permanent real-workspace oracle |
| `IMPL-127` | Sequence 16 constants, authorization, Tier, preflight, source/runtime, and active classifier |
| `IMPL-128` | Authority-parameterized strict reviewer/session/freshness validator with legacy wrapper |
| `IMPL-129` | Authority-parameterized material set, descriptor profile, retained transaction, and exact restore |
| `IMPL-130` | Sequence 16 bounded intake broker, review publisher, reconcile, and shared-path ownership |
| `IMPL-131` | Five CLI handlers, fixed grammar, registry entries, and Make routes |
| `IMPL-132` | Deterministic PAX source package and authorization candidate generator/parser |
| `IMPL-133` | Focused tests, full gates, scope audit, and allowed implementation journals |

## Test plan

| Test | Contract |
| --- | --- |
| `TEST-161` | Preserve PAX/scope coverage and accept only exact lifecycle-aware Sequence 15 historical states; never hide formal files. |
| `TEST-162` | Import exact Sequence 15 E0 bytes and archive with zero frozen live-member reads; reject every artifact/schema/link/hash/mode/identity mutation. |
| `TEST-163` | Enumerate Tier/preflight/forward combinations across pre-formal, bootstrap-only, exact retained E0, and unauthorized partial states. |
| `TEST-164` | Verify Sequence 16 IDs, authority body, six-path package, Tier/preflight, new appointment/deadline, CLI, registry, and Make contracts. |
| `TEST-165` | Enumerate all `64` active forward shapes: only `C0_PACKET`, `C1_INTAKE`, and `C2_REVIEW` pass; candidate/root always fail. |
| `TEST-166` | Validate new reviewer/session, initial-only freshness, candidate binding, 125 decisions, unique findings, and all four decision quadrants. |
| `TEST-167` | Prove exact `291+270+64=625` materials, `941` floor, descriptor/name/hash retention, fault closure, and exact limit restoration. |
| `TEST-168` | Run production-shaped accepted/rejected broker flows, crash/collision/concurrency/reconcile boundaries, byte-identical different-inode review, and legacy route compatibility. |
| `TEST-169` | Prove old Sequence 15 live validation fails after source change while exact historical import and Sequence 16 current validation pass. |
| `TEST-170` | Prove deterministic PAX, exact affected files, protected Sequence 15 hashes, no UI/API/evidence/dependency drift, and pre-authorization formal absence. |
| `TEST-171` | Run complete coordinator/recovery/fail-soft API/UI/static/dependency/cleanup gates before candidate handoff and lifecycle-aware gates after later formal states. |

## Given-When-Then scenarios

| Scenario | Given | When | Then |
| --- | --- | --- | --- |
| `SC-AC-SEQ16-001-HP-001` | Exact Sequence 15 E0 | Historical importer runs | Return `S15_E0_PACKET` without write |
| `SC-AC-SEQ16-001-NP-001` | One parent byte or metadata field differs | Importer runs | Reject |
| `SC-AC-SEQ16-001-NP-002` | Embedded source/runtime/schema/link differs | Importer runs | Reject without live-member fallback |
| `SC-AC-SEQ16-001-EP-001` | Current source differs from frozen E0 | Importer runs | Historical E0 still authenticates |
| `SC-AC-SEQ16-002-HP-001` | All Sequence 15 formal Tier paths absent | Permanent oracle runs in fixture | Accept implementation boundary only |
| `SC-AC-SEQ16-002-HP-002` | Exact complete Sequence 15 E0 retained | Permanent oracle runs in workspace | Accept historical state |
| `SC-AC-SEQ16-002-NP-001` | Partial Tier or preflight without Tier | Permanent oracle runs | Reject |
| `SC-AC-SEQ16-002-NP-002` | Unauthorized intake/review or any candidate/root | Active oracle runs | Reject |
| `SC-AC-SEQ16-003-HP-001` | Accepted Sequence 16 auth and exact E0 | Bootstrap/preflight run | Reach `C0_PACKET` |
| `SC-AC-SEQ16-003-EP-001` | Exact Tier/preflight already exist | Commands rerun | Reopen read-only |
| `SC-AC-SEQ16-003-NP-001` | ID/source/runtime/authority drift | Any command runs | Fail before write |
| `SC-AC-SEQ16-004-HP-001` | Exact accepted candidate and fresh new appointment | Broker runs | Atomically reach `C1_INTAKE` |
| `SC-AC-SEQ16-004-NP-001` | Old Sequence 15 reviewer/session/deadline | Broker runs | Reject |
| `SC-AC-SEQ16-004-NP-002` | Partial stdin or pre-rename crash | Broker runs | Intake remains absent |
| `SC-AC-SEQ16-004-NP-003` | Differing final collision | Broker runs | Reject without overwrite |
| `SC-AC-SEQ16-004-EP-001` | Commit succeeded but response was lost | Same bytes resubmitted | Reopen exact without ambient time |
| `SC-AC-SEQ16-005-HP-001` | Exact 625 materials and adequate hard limit | Transaction runs | Retain all and restore exact limit |
| `SC-AC-SEQ16-005-NP-001` | Any material path/identity/hash changes | Boundary runs | Block commit |
| `SC-AC-SEQ16-005-NP-002` | Required floor unavailable | Transaction starts | Fail before publication |
| `SC-AC-SEQ16-006-HP-001` | Exact accepted intake | Publisher runs | Publish accepted review at different inode |
| `SC-AC-SEQ16-006-HP-002` | Exact rejected intake | Publisher runs | Publish rejected review successfully |
| `SC-AC-SEQ16-006-EP-001` | Exact review already exists | Publisher reruns | Read-only exact reopen |
| `SC-AC-SEQ16-006-NP-001` | Review bytes differ from intake | Validator runs | Reject |
| `SC-AC-SEQ16-007-HP-001` | Corrected current source | Sequence 16 verifier runs | Pass current authority |
| `SC-AC-SEQ16-007-NP-001` | Corrected current source | Sequence 15 live verifier runs | Fail closed |
| `SC-AC-SEQ16-007-EP-001` | Corrected current source | Sequence 15 historical importer runs | Pass exact history |
| `SC-AC-SEQ16-007-NP-002` | Legacy route targets shared packet | Legacy command runs | Cannot consume |
| `SC-AC-SEQ16-008-HP-001` | Complete planned diff | All gates run | Green exact scope |
| `SC-AC-SEQ16-008-NP-001` | UI/API/evidence/dependency drift | Scope gate runs | Block |
| `SC-AC-SEQ16-008-NP-002` | Intake/review/candidate/root exists before auth | Absence gate runs | Block |
| `SC-AC-SEQ16-008-EP-001` | Same source package built twice | PAX gate runs | Byte-identical ordered archive |

## Affected files

### Planning outputs in this turn

```text
docs/superpowers/plans/2026-07-29-quant-radar-ui-ux-ux1b-task9-sequence15-e0-lifecycle-test-correction-continuation.md
docs/superpowers/plans/2026-07-29-quant-radar-ui-ux-ux1b-task9-sequence15-e0-lifecycle-test-correction-continuation.traceability.yaml
```

No implementation, authorization candidate, Tier, preflight, intake, review,
candidate, or root is created while planning.

### Planned implementation edits after separate acceptance

```text
Makefile
scripts/ui_ux_theme_handoff.py
scripts/test_ui_ux_theme_handoff.py
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-lifecycle-test-correction-seq16.md
.agents/builder.md
.agents/scribe.md
.agents/PROJECT.md
```

Journal rows are implementation records only after the maintainer accepts
this plan for implementation. No journal is written during the current
Sequence 15 `E0_PACKET` planning action.

### Later formal outputs after separate authorization acceptance

```text
.claude/ui_snapshots/ux1b/recovery/.external-review-lifecycle-test-correction-20260729T080000Z.lease
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-lifecycle-test-correction-prechange-seq16.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-lifecycle-test-correction-rollback-seq16.json
.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-lifecycle-test-correction-prechange-20260729T081000Z/
.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-lifecycle-test-correction-preflight-20260729T080000Z.json
.claude/ui_snapshots/ux1b/review-intake/control-migration-20260729T060000Z.json
.claude/ui_snapshots/ux1b/recovery/control-migration-manual-review-20260729T060000Z.json
```

The first five are Sequence 16-specific. The last two are shared create-once
paths that are currently absent and may be consumed only after exact
Sequence 16 formal authority and separate reviewer-candidate acceptance.

### Protected paths

```text
all Sequence 8-15 plans, ledgers, authorizations, Tier, preflights, captures,
stacks, manifests, reports, packets, intakes, reviews, candidates, and roots
all production ui/, api/, provider, fixture, selector, theme, and evidence files
all packet-referenced images and sidecars
requirements.txt
.venv/
```

The two new planning files are the only writes authorized in this planning
turn.

## Implementation sequence and gates

### Phase S16-0 — exact reopen and red reproduction

- Reopen exact accepted Sequence 15 authorization and all E0 artifacts.
- Re-run the Sequence 15 formal verify command and record
  `verified-E0_PACKET`.
- Run the complete coordinator suite and require the one reproduced
  `TEST-161` failure with `127/128`.
- Verify intake/review/candidate/root absence and no runtime/cache residue.

**Gate:** any different failure, parent drift, or unexpected leaf blocks
implementation.

### Phase S16-1 — historical E0 importer

- Add exact Sequence 15 E0 refs and descriptor-only PAX parser.
- Implement `_import_sequence15_e0_preflight()`.
- Prove zero opens of embedded frozen source-member paths.
- Prove exact internal schema/cross-link/count validation.

**Gate:** changed current source does not invalidate history; any parent byte
or semantic mutation does.

### Phase S16-2 — permanent lifecycle oracle

- Change `TEST-161` from total absence to the closed lifecycle table.
- Keep creation-time absence mutation coverage in disposable fixtures.
- Add exact real-workspace historical import.
- Reject partial Tier and unauthorized forward leaves.

**Gate:** `TEST-161` passes against retained real E0 without moving any formal
artifact and still rejects every invalid fixture state.

### Phase S16-3 — distinct current authority

- Add fixed Sequence 16 IDs, Tier, preflight, source/runtime, Make, namespace,
  reviewer, and descriptor contracts.
- Add deterministic PAX package and five-command grammar.
- Freeze a new immutable `createdAt`/`reviewDeadline`.

**Gate:** production-shaped disposable bootstrap/preflight reaches only
`C0_PACKET`; real formal outputs remain absent.

### Phase S16-4 — validator/material parameterization

- Extract appointment-specific strict review validation with a Sequence 15
  compatibility wrapper.
- Parameterize retained count from authenticated descriptor profiles.
- Keep exact `622/938` Sequence 15 behavior.
- Add exact `625/941` Sequence 16 behavior.

**Gate:** both legacy profiles pass; cross-profile counts, appointments, and
deadlines fail closed.

### Phase S16-5 — broker/publication continuation

- Add new authority-specific intake and review handlers.
- Reuse global lock, Sequence 16 lease, bounded stdin, exact candidate
  binding, material transaction, no-replace publication, and fsync.
- Prove shared-path ownership at `C0_PACKET`.
- Prove accepted/rejected `C1/C2` flows and read-only reruns.

**Gate:** candidate/root remain absent; old Sequence 15 and generic publishers
cannot consume the paths after source drift.

### Phase S16-6 — implementation verification

- Run `TEST-161..171` and the complete coordinator suite.
- Run complete repository `make test`.
- Run fail-soft artifact, API, UI read, navigation, selector, component,
  evidence, isolation, and snapshot regressions.
- Run compile, Python 3.10 AST, tabnanny, dependency, whitespace, diff,
  source-scope, runtime, process, cleanup, protected-hash, and PAX gates.
- Compare the actual diff to this affected-file list.
- Generate the authorization candidate but do not bootstrap.

**Gate:** zero failing test caused by the change, zero unexplained drift, and
all Sequence 16 formal outputs absent.

### Phase S16-7 — authorization handoff

- Report exact authorization candidate SHA-256, byte size, and mode.
- Require explicit maintainer acceptance of those exact bytes.
- Re-run protected hashes and every initial absence/collision gate.

**Gate:** without exact acceptance, no Sequence 16 formal output may exist.

### Phase S16-8 — bootstrap/preflight and reviewer pause

- Bootstrap and preflight Sequence 16.
- Reopen exact `C0_PACKET`.
- Run lifecycle-aware permanent coordinator tests.
- Stop for independent reviewer candidate.

**Gate:** Sequence 15 history and Sequence 16 Tier/preflight are exact;
intake/review/candidate/root remain absent.

### Phase S16-9 — independent review and atomic intake

- Appoint an actual independent reviewer for the fixed new session.
- Run the reviewer under an OS-enforced read-only workspace sandbox.
- Create the complete `125`-item candidate outside the workspace.
- Require maintainer acceptance of the exact candidate digest and size.
- Stream the same bytes to the new broker and verify `C1_INTAKE`.

**Gate:** exact appointment, deadline, candidate, source/runtime, `625`
materials, and empty reviewer workspace write set.

### Phase S16-10 — publish review and stop

- Publish byte-identical different-inode review.
- Reopen exact `C2_REVIEW`.
- Preserve accepted or rejected decision honestly.
- Stop with candidate/root absent.

**Gate:** no further command is authorized by Sequence 16.

## Verification commands

Implementation must expose and exercise these fixed Make routes:

```text
ui-ux1b-external-review-lifecycle-test-bootstrap
ui-ux1b-external-review-lifecycle-test-preflight
ui-ux1b-external-review-lifecycle-test-verify
ui-ux1b-external-review-lifecycle-test-submit-intake
ui-ux1b-external-review-lifecycle-test-publish
```

Repository gates include:

```bash
.venv/bin/python -B scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -B scripts/test_artifact_loader.py
.venv/bin/python -B scripts/test_api.py
.venv/bin/python -B scripts/test_ui_read_api.py
.venv/bin/python -B scripts/test_dashboard_navigation.py
make test
.venv/bin/python -m tabnanny scripts/ui_ux_theme_handoff.py scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -B -m pip check
git diff --check
```

Python 3.10 compatibility must use an actual Python 3.10 interpreter when
available. Otherwise use Python 3.11+ `ast.parse(..., feature_version=(3,10))`
and report the limitation.

## Rollback and recovery

### Before Sequence 16 authorization acceptance

- Remove only an unaccepted Sequence 16 authorization candidate when the
  reviewed plan explicitly authorizes regeneration.
- Do not touch Sequence 15 E0 or the shared forward paths.

### After Sequence 16 Tier but before preflight

- Use only the Sequence 16 rollback contract.
- Preserve partial exact evidence for diagnosis unless that contract
  authorizes cleanup.

### After Sequence 16 preflight at `C0_PACKET`

- Do not edit or delete Sequence 15 history, Sequence 16 preflight, or any
  protected path.
- Retry only exact reopen/verification commands.
- A source/test defect requires a separately reviewed continuation.

### After `C1_INTAKE`

- Never overwrite, delete, or replace intake.
- Resubmit only the same exact accepted bytes for read-only reconciliation.
- Differing bytes require a separately reviewed continuation.

### After `C2_REVIEW`

- Never rewrite reviewer bytes or decision.
- Preserve candidate/root absence.
- Any next action requires a separate reviewed and accepted authority.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| One-line TEST-161 fix invalidates E0 | Import exact E0 historically and freeze corrected source under Sequence 16 |
| Historical importer silently trusts malformed embedded data | Exact whole-file refs plus closed schema/cross-link/count validation and mutation tests |
| Historical importer reads changed live members | Descriptor-call spy requires zero embedded frozen source-member opens |
| New intake appears authorized by old Sequence 15 | Distinct command names, IDs, Tier/preflight, state names, reviewer session, and shared-path ownership gate |
| Shared path is consumed twice | Exact `C0` prefix, global lock, new lease, atomic no-replace publication, collision reconciliation |
| Old reviewer deadline expires during correction | New immutable Sequence 16 deadline and session |
| Material count remains stale at 622 | Exact `625/941` gate while preserving legacy `622/938` profile |
| TEST-161 accepts unauthorized intake | Parent test proves history only; Sequence 16 active classifier must authenticate any C1/C2 leaf |
| Generic route reaches shared packet | Legacy routing signatures and outputs remain unchanged and are tested |
| Candidate/root authority leaks into correction | Grammar, authorization, state matrix, and absence gates forbid both |
| Plan review is mistaken for independent review | Document and final response state local deterministic provenance explicitly |
| More source drift appears after Sequence 16 preflight | Permanent lifecycle test plus separate-continuation rollback rule |

## Review checklist

- [x] Exact retained Sequence 15 E0 is fully enumerated.
- [x] Parent history and corrected current authority are separated.
- [x] Frozen source is never treated as current after implementation.
- [x] TEST-161 accepts valid monotonic history and rejects partial states.
- [x] Unauthorized intake/review is rejected by the Sequence 16 classifier.
- [x] Shared forward-path ownership is create-once and distinct.
- [x] A new reviewer session/deadline replaces the parent deadline.
- [x] `625/941` current and `622/938` legacy descriptor profiles are explicit.
- [x] Atomic broker, decision truth, sandbox, and different-inode review remain exact.
- [x] Candidate/root remain absent and unauthorized.
- [x] Affected files, phases, tests, rollback, and formal pauses are explicit.
- [x] Traceability is closed and bidirectional.
- [x] Review provenance is accurate.
- [x] No unresolved blocker remains.

## Review findings

Any unresolved Blocker, High, or Medium finding prevents
`LOCALLY REVIEWED`.

| Iteration | Finding | Severity | Resolution |
| ---: | --- | --- | --- |
| `1` | A one-line TEST-161 edit would invalidate the exact Sequence 15 live source projection and make every old submit/verify path unusable. | High | Added exact whole-file `S15_E0_PACKET` historical import plus a distinct Sequence 16 active authority; the old live validator remains fail-closed. |
| `1` | Reusing shared intake/review paths did not identify which authority could consume them. | High | Sequence 16 takes create-once ownership only from exact initial E0 under a distinct Tier/preflight, lock/lease, command set, and reviewer session. |
| `1` | Lifecycle-aware TEST-161 could accept an unauthorized intake by checking only candidate/root absence. | High | Split parent historical proof from active Sequence 16 forward proof; any C1/C2 leaf requires exact Sequence 16 preflight and semantics. |
| `2` | Inheriting the Sequence 15 deadline could make the first legitimate corrected submission stale before implementation finished. | Medium | Mint a new immutable Sequence 16 `createdAt`, 24-hour deadline, reviewer ID, and session. |
| `2` | The retained material budget still used Sequence 15 `622/938` despite three new active package documents. | Medium | Close Sequence 16 at `291+270+64=625` retained leaves and a `941` floor; preserve Sequence 15 profile through parameterized compatibility tests. |
| `2` | A historical importer that only checked the preflight SHA could conceal malformed internal projections or archive links. | Medium | Require exact artifact refs plus closed parsing of authorization, Tier, PAX members, preflight schemas, embedded records, runtime, namespace, report, and packet cross-links. |
| `2` | The permanent test still rebuilt a Sequence 15 PAX from changed current source, producing deterministic but unauthorized bytes unrelated to retained history. | Medium | `TEST-161` reopens the exact retained PAX through the historical importer; deterministic current packaging moves to Sequence 16 `TEST-170`. |
| `2` | Sequence 16 active states were named `C0/C1/C2` but several authority and stop fields still said `E2_REVIEW`. | Medium | Use `C2_REVIEW` for every Sequence 16 authority, receipt, gate, and formal stop; retain `E2_REVIEW` only when parsing exact parent Sequence 15 history. |
| `3` | The exact retained Sequence 15 ledger has `gid=0`; a blanket current-GID source rule would reject accepted history or tempt an unauthorized chmod/chown. | Medium | Bind the exact accepted historical owner/group metadata and explicitly forbid normalization; apply current owner/group requirements only to new Sequence 16 outputs. |
| `3` | The first traceability draft connected the umbrella implementation-boundary AC to every implementation and test, making the graph structurally complete but semantically uninformative. | Medium | Limit `AC-SEQ16-008` to historical/package verification and full-gate artifacts/tests, then derive every reverse edge from the narrower acceptance graph. |
| `3` | The draft reviewer field could imply independent Judge review even though subagent delegation was unavailable. | Medium | Label provenance as local deterministic contract review and make independent review a later explicit gate. |
| `3` | Rechecked history/current separation, test lifecycle, shared ownership, deadline, descriptors, atomicity, compatibility, rollback, scope, and traceability. | None | Local deterministic review passed with no unresolved Critical, High, Medium, or useful Low finding. |

## Traceability summary

The sibling ledger must bind:

```text
REQ-017
CFR-079..084
AC-SEQ16-001..008
IMPL-125..133
TEST-161..171
```

All six relation families must be bidirectional with `10000` basis-point
structural coverage, no gaps, no orphans, and no asymmetric edges. Planning
verdicts remain `NOT_TESTED`; local plan review does not claim implementation
or runtime execution.

## Success metrics

| Metric | Target | Measurement |
| --- | ---: | --- |
| Parent E0 exactness | `100%` | All listed refs, archive members, and internal semantics pass |
| Frozen live-member reads | `0` | Instrumented historical-import path-open oracle |
| Permanent lifecycle states | Closed table only | Exhaustive fixture plus real-workspace test |
| Active forward matrix | `3/64` valid | Exhaustive Sequence 16 classifier |
| Parent source/runtime mutation | `0` | Protected-hash and exact historical import |
| Current material integrity | `625/625` | Retained descriptor/name/hash transaction |
| Descriptor floor | `>=941`, `<=1536` | Limit gate and exact restoration |
| Legacy material profile | `622/938` unchanged | Compatibility tests |
| Review item coverage | `125/125` | Candidate IDs equal packet IDs in exact order |
| Intake atomicity | `0` partial final leaves | Fault/concurrency/collision matrix |
| Reviewer workspace writes | `0` | OS sandbox and namespace fingerprint |
| Candidate/root writes | `0` | Grammar and formal namespace verification |
| Traceability coverage | `10000 bps` | Canonical ledger validator |
| Full coordinator | `100%` | No permanent real-workspace lifecycle failure |

## Dependencies

- Exact retained Sequence 15 E0 artifacts listed above.
- Exact retained Sequence 14 report and packet.
- Existing canonical JSON, descriptor, lock, lease, PAX, runtime receipt,
  manual-review v2, packet v2, atomic publication, and process-cleanup
  primitives.
- Maintainer acceptance of this reviewed plan before implementation.
- Maintainer acceptance of a later exact Sequence 16 authorization candidate.
- An actual independent reviewer after Sequence 16 preflight.

## Change history

| Version | Date | Change |
| --- | --- | --- |
| `0.1-draft` | `2026-07-29` | Draft lifecycle-test correction after formal E0 exposed TEST-161's implementation-only absence oracle. |
| `0.2-review-fixes` | `2026-07-29` | Add historical E0 import, distinct shared-path ownership, active authority, fresh reviewer session/deadline, and `625/941` material profile. |
| `1.0-locally-reviewed` | `2026-07-29` | Close internal parsing and review-provenance findings; no unresolved local blocker remains. |
