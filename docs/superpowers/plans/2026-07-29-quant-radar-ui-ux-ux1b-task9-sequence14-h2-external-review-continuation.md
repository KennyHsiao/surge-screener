# Quant Radar UX-1B Sequence 15 External-Review Continuation

## Document information

| Field | Value |
| --- | --- |
| Type | Corrective implementation plan and execution checklist |
| Version | `1.0-reviewed` |
| Status | `REVIEWED — IMPLEMENTATION NOT STARTED` |
| Date | `2026-07-29` |
| Authorization | Repository maintainer authorized creation and review of this Sequence 15 plan |
| Author | Scribe |
| Plan reviewer | Independent Judge |
| Approver | Repository maintainer |
| Audience | Maintainers, implementers, independent evidence reviewers, and code reviewers |
| Sequence | `15` |
| Parent Sequence | Exact accepted Sequence 14 at `H2_PACKET` |
| Capture ID | `20260729T040000Z` |
| Parent continuation ID | `20260729T060000Z` |
| External-review correction ID | `20260729T070000Z` |
| External-review Tier ID | `20260729T071000Z` |
| Formal stop | `E2_REVIEW` |
| Related ledger | `docs/superpowers/plans/2026-07-29-quant-radar-ui-ux-ux1b-task9-sequence14-h2-external-review-continuation.traceability.yaml` |

This plan is not implementation or formal execution authority. It authorizes
no source edit until blocking review passes and the maintainer separately
accepts it for implementation. Formal bootstrap, intake, and review
publication later require separate acceptance of an exact Sequence 15
authorization document by whole-file SHA-256, byte size, and mode.

## Purpose

Sequence 14 successfully published an exact `125`-item control-migration
review packet and stopped at its mandatory `H2_PACKET` boundary. Its accepted
authority deliberately marks `H3_INTAKE` and `H4_REVIEW` as forbidden.

Sequence 15 will:

- import the exact accepted Sequence 14 `H2_PACKET` as immutable historical
  authority;
- freeze changed current source and runtime under a distinct Sequence 15
  authorization, Tier, and preflight;
- appoint one independent reviewer session and accept reviewer-authored bytes
  only through a locked, atomic intake-submission broker at the already
  reserved Sequence 14 intake path;
- validate all `125` item decisions against the exact review-packet v2 bytes
  and all referenced evidence bytes;
- publish one byte-identical manual review at a different inode;
- preserve either an `accepted` or `rejected` reviewer decision exactly;
- stop at `E2_REVIEW` with candidate and root absent;
- perform no capture, recapture, comparison, UI change, evidence rewrite, or
  root publication.

## Scope

### In scope

- Exact historical import of the accepted Sequence 14 authorization, Tier,
  preflight, report, and review packet.
- A distinct Sequence 15 authorization candidate, deterministic Tier,
  preflight, source package, runtime receipt, lease, command set, and Make
  routes.
- Three exact external-review lifecycle states: packet ready, intake present,
  and manual review published.
- External intake validation for the existing
  `quant-radar-ui-ux-manual-review/v2` schema.
- Exact review-packet v2 path override for the Sequence 14 continuation
  namespace.
- Descriptor-relative reauthentication of every packet input and every unique
  `before`, `after`, and `afterSidecar` artifact reference.
- Exact `125`-item reviewer order, identity, explanation, finding, and
  accepted/rejected decision semantics.
- Atomic create-once intake submission and manual-review publication, exact
  reopen, collision handling, crash reconciliation, and different-inode proof.
- Authority-bound reviewer appointment plus an explicit governance boundary:
  same-UID human authorship is confirmed by the independent-review assignment
  and maintainer, while the machine enforces the exact appointment/session,
  packet binding, freshness, and candidate digest.
- Independent reviewer OS write isolation that makes the workspace read-only,
  permits candidate output only outside the workspace, and protects the frozen
  `.venv`, source, evidence, capture, and predecessor trees.
- One descriptor-budgeted material transaction that retains all `622` unique
  source, supplemental, and review-material leaves through final commit.
- Complete targeted, recovery, fail-soft API/UI, runtime, syntax, dependency,
  scope, whitespace, diff, and protected-artifact gates.

### Out of scope

- Any Chromium, Streamlit, Playwright, browser-worker, full-page, focused,
  control-root, or sidecar capture.
- Re-running the Sequence 14 comparator or rebuilding its packet.
- Editing, replacing, deleting, chmodding, or regenerating any Sequence
  8–14 authority, capture, manifest, report, packet, intake, review, candidate,
  or root artifact.
- Editing production `ui/`, `api/`, providers, selectors, fixtures,
  `scripts/ui_ux_evidence.py`, capture stacks, capture manifests, theme source,
  or dependencies.
- Letting the implementer author the reviewer decision.
- Letting an independent reviewer edit implementation, plan, authorization,
  frozen runtime, capture, or evidence files.
- Candidate preparation, root verification/publication, theme batch/state
  work, or final theme handoff.
- Treating a valid `rejected` review as an execution failure or promoting it
  to `accepted`.

## Non-goals

- Sequence 15 does not guarantee reviewer acceptance.
- Sequence 15 does not repair or reinterpret a rejected item.
- Sequence 15 does not change comparison geometry, semantic tolerances,
  packet prompts, item IDs, or artifact bytes.
- Sequence 15 does not replace the existing manual-review v2 schema.
- Sequence 15 does not weaken Sequence 14 historical or current-stack
  authentication.
- Sequence 15 does not authorize a candidate or product root after an
  accepted review.

## Glossary

| Term | Definition |
| --- | --- |
| Parent H2 | Exact accepted Sequence 14 report plus packet, with all four later leaves absent. |
| Historical import | Exact byte, metadata, schema, and cross-link validation without comparing frozen Sequence 14 source members to changed current source. |
| Active authority | Sequence 15 source/runtime authority that must remain exact while intake and review are consumed. |
| External intake | Reviewer-authored canonical manual-review v2 bytes atomically brokered to the reserved intake path; the reviewer never writes that path directly. |
| Manual review | Coordinator-published byte-identical copy of the external intake at the recovery review path. |
| Evidence material | Every packet input plus every unique item artifact reference opened by path, no-follow, and checked by SHA-256 and size. |
| Blocking finding | An unresolved `High` or `Medium` finding. |
| Review publication success | The intake was validly preserved as manual review; it does not mean the review decision was accepted. |
| Reviewer appointment | Exact reviewer ID, one-use session ID, packet digest, freshness policy, and candidate-digest acceptance bound by authority and maintainer confirmation. |
| Material transaction | Global lock/lease plus retained no-follow descriptors, precommit named-identity/hash checks, atomic publication, and postcommit reauthentication. |

## Verified starting state

### Exact Sequence 14 authority

| Artifact | SHA-256 | Bytes | Mode |
| --- | --- | ---: | --- |
| Sequence 14 plan | `0766a4c9b22496ee029fc99b4147143dc6427450bfde6d55dfa86df241157f08` | `44664` | `0644` |
| Sequence 14 ledger | `27be78c3d0797d065ce269e704266192f7596358f6d9669683727b203096a99d` | `6956` | `0644` |
| Accepted Sequence 14 authorization | `eb378367be0d3a078c027782439323e4b78d98c26786583bfef6ae4d284a4ce6` | `6546` | `0644` |
| Sequence 14 lease | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `0` | `0600` |
| Sequence 14 prechange | `e5b5843c434cdd6031f703145a94b95b7b61a9f988a84ca960477d1f0c72d365` | `16757` | `0600` |
| Sequence 14 rollback | `6572d12324e32a5497b896087f70ddbe4b77ba5d042e1ec36ff6e8a76d5adcda` | `2980` | `0600` |
| Sequence 14 archive owner | `efc0b2c484a83d070012528be0cd4f66b8fccbd26ad8ba7194dc1bf737d69923` | `136` | `0600` |
| Sequence 14 PAX archive | `83309c137fff3aec04c650d7634ffa1d28f9f421f919a116468d6e79fc80b722` | `3102720` | `0600` |
| Sequence 14 bundle manifest | `008fa707c65b96079543e57627fec1a033cf8747b192dddc67b1278e2f9d6c14` | `1268` | `0600` |
| Sequence 14 preflight | `0e4f8eb49861558d0d5c02f86f7a0e46885d6d648582a7f2523fd784084da019` | `74345` | `0600` |
| Sequence 14 migration report | `97a37c01a7fefbaf20386a6bb732e87993e8f282ba3216885ad92f2530a7f553` | `12444` | `0600` |
| Sequence 14 review packet | `1a9f1a3c995c04d5db1137e25f861a333483a9ba2bb83176532f87a74cc024dd` | `89295` | `0600` |

The accepted authorization body has `formalPause=H2_PACKET` and exactly five
allowed Sequence 14 commands. Sequence 15 must not reinterpret that authority
as permission for external review. It imports the exact H2 result and supplies
a new, separately accepted continuation authority.

### Exact packet facts

```text
schemaVersion       = quant-radar-ui-ux-review-packet/v2
kind                = control-migration
status              = review_required
lineageId           = 20260725T080000Z
machineReport SHA   = 97a37c01...f553
inputs              = 5
items               = 125
page items          = 81
control-root items  = 44
unchanged items     = 58
changed items       = 67
changed pages       = 23
changed roots       = 44
prompt SHA          = f5491454...5f73
inputs SHA          = 5f976297...a2b
item-set SHA        = b867db68...262c
```

The packet's `lineageId` intentionally remains the original capture recovery
ID. Its filesystem path intentionally uses the Sequence 14 continuation ID.
The generic legacy `_review_paths()` derivation therefore points at the old
Sequence 11 packet and must not be used without an explicit, closed Sequence
15 path override.

### Current forward presence

```text
report        present
packet        present
intake        absent
manual review absent
candidate     absent
root          absent
```

The formal paths are:

```text
0 .claude/ui_snapshots/ux1b/recovery/control-migration-20260729T060000Z.json
1 .claude/ui_snapshots/ux1b/recovery/control-migration-review-packet-20260729T060000Z.json
2 .claude/ui_snapshots/ux1b/review-intake/control-migration-20260729T060000Z.json
3 .claude/ui_snapshots/ux1b/recovery/control-migration-manual-review-20260729T060000Z.json
4 .claude/ui_snapshots/ux1b/recovery/theme-handoff-candidate-20260729T060000Z.json
5 docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json
```

## Authority design

### Sequence 15 identifiers

```text
captureId                  20260729T040000Z
parentContinuationId       20260729T060000Z
externalReviewCorrectionId 20260729T070000Z
externalReviewTierId       20260729T071000Z
```

These IDs are fixed. They are not timestamps supplied by a caller.

### Authorization candidate

Implementation will create:

```text
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-continuation-seq15.md
```

Its one-line canonical authorization body must bind:

- `schemaVersion`;
- `sequence=15`;
- `status=AUTHORIZED`;
- all four fixed IDs;
- exact parent Sequence 14 plan, ledger, authorization, Tier, preflight,
  report, and packet references;
- exact Sequence 15 plan and ledger references;
- exact source package paths;
- exact three-state lifecycle;
- exact intake and review paths;
- manual-review v2 and review-packet v2 schema identities;
- `reviewItems=125`, `inputs=5`, `pageItems=81`,
  `controlRootItems=44`;
- `formalPause=E2_REVIEW`;
- `noCaptureAuthority=true`;
- `noCandidateAuthority=true`;
- `noRootAuthority=true`;
- the five allowed public commands;
- one exact reviewer-submission capability for the independent intake;
- one exact reviewer appointment/session, packet digest, and freshness policy;
- precedence: Sequence 15 review continuation, Sequence 14 H2, retained
  Sequence 13/12/11 history.

The reviewer-submission capability must close:

```text
actorType       independent-code-reviewer
commitStart     E0_PACKET
commitPost      E1_INTAKE
reconcileStates E1_INTAKE,E2_REVIEW
reconcileMode   read-only exact bytes/digest/session only
path            .claude/ui_snapshots/ux1b/review-intake/control-migration-20260729T060000Z.json
schemaVersion   quant-radar-ui-ux-manual-review/v2
transport       bounded-stdin
reviewerId      judge-seq15-control-migration@seq15-20260729T070000Z-review-01
reviewSessionId seq15-20260729T070000Z-review-01
packetSha256    1a9f1a3c995c04d5db1137e25f861a333483a9ba2bb83176532f87a74cc024dd
reviewDeadline  preflight.createdAt + 86400 seconds, stored in preflight
initialClock    reviewedAt <= brokerNow + 300 seconds and brokerNow <= reviewDeadline + 300 seconds at E0 commit only
mode            0600
owner           current uid/gid
nlink           1
canonicalJson   true
maxBytes        16777216
createOnce      true
atomicPublish   same-directory temp + fsync + no-replace rename + parent fsync
```

The closed manual-review v2 schema has no separate session field, so its
`reviewer.id` must equal the exact composite `reviewerId` above; the session
component is not caller supplied. The reviewer prepares canonical candidate
bytes outside the workspace. Before
submission, the maintainer receives those bytes from the appointed reviewer
and explicitly accepts their exact SHA-256 and size as that review session's
candidate. The broker receives the candidate on bounded stdin and the accepted
digest as closed invocation authority; no candidate path is accepted.

The local process cannot prove the human author of bytes written by another
process running as the same OS uid. Sequence 15 therefore does not claim that
`reviewer.id` alone proves independence. Independence is a governance gate
provided by the independent Judge assignment plus maintainer acceptance of the
exact candidate digest. Machine enforcement covers the exact appointment ID,
one-use session, packet/preflight binding, timestamp freshness, candidate
digest, and create-once destination. A workflow requiring cryptographic
principal proof needs separately designed external signing infrastructure and
is out of scope for this continuation.

No wildcard path, caller-selected ID, output path, capture path, packet path,
review path, candidate path, root path, schema, decision, reviewer identity,
or session flag is allowed.

### Sequence 15 Tier and preflight paths

```text
.claude/ui_snapshots/ux1b/recovery/.historical-stack-external-review-continuation-20260729T070000Z.lease
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-continuation-prechange-seq15.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-continuation-rollback-seq15.json
.claude/ui_snapshots/ux1b/recovery/theme-handoff-historical-stack-external-review-continuation-prechange-20260729T071000Z/
.claude/ui_snapshots/ux1b/recovery/theme-handoff-historical-stack-external-review-continuation-preflight-20260729T070000Z.json
```

The global formal-handoff lock remains shared. The Sequence 15 lease and all
other Tier leaves are distinct.

### Source package

The deterministic PAX source package contains exactly:

```text
Makefile
docs/superpowers/plans/2026-07-29-quant-radar-ui-ux-ux1b-task9-sequence14-h2-external-review-continuation.md
docs/superpowers/plans/2026-07-29-quant-radar-ui-ux-ux1b-task9-sequence14-h2-external-review-continuation.traceability.yaml
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-continuation-seq15.md
scripts/test_ui_ux_theme_handoff.py
scripts/ui_ux_theme_handoff.py
```

No `.venv`, cache, image, sidecar, manifest, evidence module, capture stack,
UI, API, provider, fixture, secret, report, packet, intake, review, candidate,
root, or unrelated dirty-worktree file enters the package.

The existing deterministic PAX implementation must be reused. USTAR fallback,
path substitution, ambient directory enumeration, and package widening are
forbidden.

## Historical parent import

Sequence 15 must not call the live Sequence 14 preflight reauthentication
after Sequence 15 source edits. That call correctly rejects current-source
drift and would recreate the historical/live authority error already fixed by
Sequence 14.

The parent importer must:

1. open every listed Sequence 14 authority leaf descriptor-relative and
   no-follow;
2. verify SHA-256, size, mode, uid, gid, nlink, safe ancestors, and canonical
   bytes;
3. parse the accepted authorization body and require its exact known value;
4. validate Tier, archive, bundle, and preflight internal cross-references;
5. validate the report schema, passed status, `81/44/125`, nested `117`, and
   exact excluded-predecessor semantics;
6. validate the packet v2 schema, prompt, five inputs, exact report binding,
   `125` unique ordered items, `81/44` kind split, and item-set digest;
7. require the exact no-gap `[report, packet]` prefix with intake, review,
   candidate, and root absent when Sequence 15 preflight is first created;
8. return an immutable `S14_H2_PACKET` projection;
9. never rebuild report or packet bytes from current implementation source;
10. never read a Sequence 14 source member as current authority.

Any parent mutation, partial predecessor, unsafe metadata, extra later leaf,
or cross-link mismatch blocks Sequence 15 before its first write.

## Sequence 15 preflight

The preflight schema is:

```text
quant-radar-ui-ux-historical-stack-external-review-preflight/v1
```

It binds:

- accepted Sequence 15 authorization bytes and body digest;
- exact plan and traceability references;
- all fixed IDs;
- the complete `S14_H2_PACKET` projection;
- exact initial state `E0_PACKET`;
- current source and supplemental projections;
- deterministic PAX Tier references;
- current runtime receipt and descriptor profile;
- closed Make/parser/handler registry contract;
- exact reviewer appointment and atomic stdin-submission capability;
- immutable `createdAt` and `reviewDeadline=createdAt+86,400 seconds`; the
  deadline is computed once at preflight creation and never from ambient time
  during later reauthentication;
- a descriptor profile whose exact retained-leaf count is `622`, whose
  inherited protocol allowance is `252`, whose reserve is `64`, and whose
  required soft limit is therefore at least `938` and no more than the
  inherited `1536` raise ceiling;
- forward paths and state table;
- candidate/root forbidden flags.

Creation requires exact `E0_PACKET`. Reauthentication preserves the stored
initial fact and separately validates current `E0..E2` state. It must never
recompute the initial snapshot from evolving leaf presence.

## Forward lifecycle

### States

| State | Report | Packet | Intake | Review | Candidate | Root | Permitted next action |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `E0_PACKET` | 1 | 1 | 0 | 0 | 0 | 0 | Broker may atomically submit appointed reviewer intake |
| `E1_INTAKE` | 1 | 1 | 1 | 0 | 0 | 0 | Publish manual review or exactly reconcile submit read-only |
| `E2_REVIEW` | 1 | 1 | 1 | 1 | 0 | 0 | Mandatory stop; exact read-only reopen/reconcile only |

Every other existence pattern is invalid. Existing report and packet must
equal the imported Sequence 14 references. Candidate and root are forbidden
in every Sequence 15 state.

Every present intake/review leaf must be:

- a no-follow, one-link regular file;
- mode `0600`;
- owned by current uid/gid;
- canonical compact UTF-8 JSON with no trailing LF;
- at most `16,777,216` bytes;
- valid manual-review v2;
- bound exactly to the Sequence 14 packet.

### State semantics

`E0_PACKET` validates only the exact imported parent H2 and later absences.

`E1_INTAKE` additionally validates:

- exact closed manual-review v2 keys;
- `kind=control-migration`;
- `status == decision`;
- `reviewer.type=independent-code-reviewer`;
- reviewer ID exactly equals the authority-bound composite appointment/session
  ID;
- the authority-bound one-use review session is packet-specific and is
  consumed by exactly this intake path/digest; presence of exact intake is the
  immutable consumed-session fact, not a mutable ambient counter;
- UTC-seconds `reviewedAt` is no earlier than immutable
  `preflight.createdAt` and no later than immutable
  `preflight.reviewDeadline`;
- submitted bytes match the exact candidate SHA-256 and size explicitly
  accepted by the maintainer for that appointment/session;
- exact packet path/SHA/size;
- exact prompt, input, and item-set digests;
- exactly `125` decisions in packet order;
- every decision has a nonempty explanation;
- every verdict is `accepted` or `rejected`;
- findings have unique nonempty IDs, allowed severity/status, and nonempty
  summaries;
- `accepted` iff no item is rejected and no unresolved `High` or `Medium`
  finding exists;
- `rejected` iff at least one item is rejected **or** at least one unresolved
  `High` or `Medium` finding exists;
- every packet input and unique item artifact reference still matches exact
  SHA-256 and size.

`E2_REVIEW` additionally requires:

- manual-review bytes exactly equal intake bytes;
- review and intake have different device/inode identity;
- public decision equals the validated intake decision;
- candidate and root remain absent.

The exact review is retained whether accepted or rejected. A rejected review
returns publication success with `decision=rejected`; it does not authorize a
candidate.

## Independent reviewer contract

### Independence and trust boundary

The reviewer must not have authored or edited the Sequence 15 implementation
under review. The maintainer appoints that reviewer and one review session
before accepting the Sequence 15 authorization, and later accepts the exact
candidate SHA-256 and size received from that reviewer before the broker runs.
The machine validates the appointment/session, packet binding, freshness, and
candidate digest; it does not pretend that a same-UID string can prove human
authorship. The reviewer may read:

- the accepted Sequence 15 authority and preflight;
- the exact Sequence 14 report and packet;
- every packet input;
- every referenced image and sidecar;
- read-only review instructions and test output.

The formal reviewer process runs with the workspace mounted or sandboxed
read-only. It may write candidate bytes only to an isolated directory outside
the workspace and every frozen runtime tree. It must not write plan, source,
tests, Makefile, authorization, `.agents`, `.venv`, cache, capture, evidence,
report, packet, intake, manual review, candidate, or root workspace paths.
Only the coordinator broker may create the final intake.

### Runtime isolation

The previous Sequence 11 review changed the ctime-bound authorized `.venv`
tree by importing Pillow without a no-bytecode boundary. Sequence 15 makes
this a blocking gate:

- repository `.venv` must not be used for reviewer image processing;
- `PYTHONDONTWRITEBYTECODE=1` alone is not sufficient authority to use a
  frozen runtime when another non-bytecode write remains possible;
- prefer the platform image viewer or an isolated runtime outside the
  workspace and outside every frozen runtime tree;
- require an OS-enforced reviewer profile that denies every workspace write
  and grants writes only to a newly created isolated output directory; if the
  host cannot provide that enforcement, formal review remains blocked;
- no browser, server, capture, recapture, package install, cache creation, or
  dependency mutation is allowed;
- fingerprint the complete workspace namespace before and after reviewer
  execution and require an empty formal-review write set; `.git`, `.agents`,
  cache, and unrelated paths are not exceptions;
- defer reviewer skill-journal and project-activity writes until after
  `E2_REVIEW`, outside the protected formal-review interval;
- preflight source/runtime receipts must be reauthenticated after intake
  creation and before review publication.

Any runtime/source/evidence drift retains the intake for diagnosis but blocks
manual-review publication.

### Review procedure

The independent reviewer must:

1. reauthenticate the exact packet and its five inputs;
2. enumerate all `125` packet items in order;
3. verify the `58` unchanged items by exact before/after byte identity and
   record one item decision for each;
4. visually inspect both before and after images for all `67` changed items;
5. for all `44` control-root items, inspect the after image and exact sidecar,
   confirm the target selector/root is visible, and confirm screenshot-time
   binding is credible;
6. assess the prompt checks:
   `identity_exact`, `selection_semantics_preserved`, and
   `geometry_deltas_explained`;
7. produce exactly one explanation for each item in packet order;
8. record every finding with severity, resolution status, and summary;
9. choose `accepted` only when all items pass and no blocking finding remains;
10. choose `rejected` otherwise; item-only, finding-only, and combined
    rejection are all valid and must preserve the exact underlying truth;
11. serialize canonical compact manual-review v2 bytes with no trailing LF;
12. write the candidate only to the isolated output directory, report its
    exact SHA-256 and size to the maintainer, and perform no workspace write;
13. after maintainer acceptance of that exact digest, stream the same bytes to
    the fixed broker; the coordinator, not the reviewer, creates the intake.

Machine `changed`, geometry, or report status may guide review but cannot
replace visual examination of changed items. Sidecar claims cannot override
pixels when they disagree.

## Publication design

The existing `_validate_review_packet_value()` and
`_validate_manual_review_value()` may be reused only after Sequence
15-specific strengthening described above.

The old `_review_paths()` must remain unchanged for existing workflows.
Sequence 15 must supply an explicit internal path tuple:

```text
packet      .claude/ui_snapshots/ux1b/recovery/control-migration-review-packet-20260729T060000Z.json
intake      .claude/ui_snapshots/ux1b/review-intake/control-migration-20260729T060000Z.json
destination .claude/ui_snapshots/ux1b/recovery/control-migration-manual-review-20260729T060000Z.json
```

The path override must be callable only from the closed Sequence 15 handler.
It must equal the fixed tuple above. Caller-selected paths are forbidden.
Existing control-migration, theme-batch, theme-state, and posttheme callers
must retain their current behavior.

Submission from `E0_PACKET` must:

1. receive at most `16,777,216` candidate bytes on stdin and require EOF;
2. receive no caller-selected path, reviewer ID, session ID, schema, decision,
   timestamp, or output location;
3. acquire the global lock and Sequence 15 lease before lifecycle inspection;
4. reauthenticate authority, preflight, current source/runtime, exact parent
   H2, the appointed review session, the maintainer-accepted candidate digest,
   and all review materials;
5. at `E0_PACKET`, require the session unconsumed, require both
   `reviewedAt <= brokerNow + 300 seconds` and
   `brokerNow <= preflight.reviewDeadline + 300 seconds`, parse and validate
   the canonical candidate entirely in memory, and reject invalid bytes before
   any destination write;
6. reuse `_publish_regular_exact()` so the fixed intake is written to a
   same-directory random mode-`0600` temporary, file-fsynced, rehashed,
   atomically committed by no-replace rename, and parent-directory-fsynced;
7. reopen the named intake no-follow, require the committed identity and exact
   bytes, and fully validate `E1_INTAKE`;
8. at `E1_INTAKE` or `E2_REVIEW`, skip every stage/write operation and
   reconcile only when stdin, accepted digest/size, appointment/session,
   packet binding, and the named intake are exact; differing bytes fail
   without overwrite or deletion.

Temporary-file names and lifecycle are internal broker state, never public
arguments. Pre-rename failure removes only the broker-owned temporary. A
partial or invalid stdin payload never consumes the formal create-once path.
Competing submit, verify, bootstrap, or publish commands serialize on the same
global lock and lease. Ambient time is consulted only for the initial
`E0_PACKET` commit. Later `E1_INTAKE`/`E2_REVIEW` verification checks the
immutable preflight deadline and exact consumed-by-this-intake fact, so an
otherwise exact formal result never expires.

### Material transaction and TOCTOU boundary

The packet contains `291` unique input/image/sidecar material paths. The
Sequence 14 active projections contain another `270` source and `61`
supplemental paths, with no overlap, for exactly `622` retained leaves.
Before intake or review commit, the coordinator must raise its soft descriptor
limit to the authority-bound budget (`622 + 252 + 64 = 938`, bounded by the
existing `1536` ceiling) or fail before any write.

While holding the global lock and Sequence 15 lease, the operation must:

1. open all `622` content leaves descriptor-relative, no-follow, deduplicated
   by exact path, retaining every descriptor through commit;
2. validate expected device/inode, owner, mode, nlink, size, SHA-256, and safe
   named-path identity from those descriptors;
3. within the `252` protocol allowance, also retain every fixed Sequence 15
   authority/Tier/preflight, exact parent-H2, packet, intake, workspace-root,
   and required ancestor descriptor plus the runtime-root identity; verify the
   runtime tree receipt immediately before and after commit;
4. stage the destination but do not rename it;
5. immediately before rename, re-fstat and rehash every retained descriptor,
   reopen every name no-follow, and require named identity still equals the
   retained descriptor;
6. atomically no-replace rename and fsync the parent only after that complete
   precommit pass;
7. while the lock/lease and descriptors remain held, revalidate all retained
   descriptors, names, runtime receipt, and the new state before success;
8. close descriptors and restore the original soft limit on every exit path.

The global lock is a cooperative protocol boundary: every authorized
coordinator writer must honor it, and the OS sandbox prevents the reviewer
from writing the workspace. A malicious or unrelated same-UID process that
ignores both controls can still mutate a regular file in place and is outside
the formal threat model; precommit/postcommit identity and hash checks detect
such drift but cannot retroactively make an uncooperative host atomic.

Publication from `E1_INTAKE` must:

1. acquire the global lock and Sequence 15 lease;
2. establish the complete retained-descriptor material transaction above and
   reauthenticate Sequence 15 preflight, current source/runtime, exact parent
   H2, and all review materials;
3. open intake by fixed path with no-follow;
4. validate intake from the same retained descriptor;
5. stage identical bytes for the fixed destination, perform the final
   material/name precommit pass, and only then atomically publish with
   create-once semantics;
6. require a different inode;
7. reclassify and fully validate `E2_REVIEW`;
8. return exit `0`, publication status, exact review reference, and exact
   reviewer decision from the same descriptor operation.

Exact rerun from `E2_REVIEW` performs no write. It reauthenticates intake,
review, materials, source/runtime, and returns the same review reference and
decision. A differing destination collision fails closed and is never
overwritten or deleted.

## Public commands and Make targets

Exactly five Sequence 15 commands are allowed:

```text
bootstrap-historical-stack-external-review-continuation
preflight-historical-stack-external-review-continuation
verify-historical-stack-external-review-continuation-preflight
submit-historical-stack-review-intake
publish-historical-stack-review
```

Every command requires:

```text
--capture-id 20260729T040000Z
--parent-continuation-id 20260729T060000Z
--external-review-correction-id 20260729T070000Z
--external-review-tier-id 20260729T071000Z
--json
```

The submit command additionally requires exactly:

```text
--intake-stdin
--accepted-intake-sha256 <exact 64-lowercase-hex digest accepted by maintainer>
--accepted-intake-size <exact decimal byte count, 1..16777216>
```

Those values are an operator assertion of the preceding maintainer governance
gate, not a cryptographic proof of human identity. The broker requires stdin
bytes to match them exactly. The other four commands reject these flags.

No public command authors the external reviewer decision. The exact intake
submission command transports already reviewed and maintainer-accepted exact
bytes; it cannot synthesize, normalize, repair, or select the decision.

Exactly five Make targets route only to those commands:

```text
ui-ux1b-external-review-bootstrap
ui-ux1b-external-review-preflight
ui-ux1b-external-review-verify
ui-ux1b-external-review-submit-intake
ui-ux1b-external-review-publish
```

Every handler must execute through the production parser, fixed argument
validator, command registry, descriptor wrapper, lock/lease boundary, and
public JSON renderer. A nonzero operation result must propagate before any
second authority read or later write.

## Requirements

| ID | Requirement |
| --- | --- |
| `REQ-016` | Continue UX-1B formal handoff from the exact Sequence 14 `H2_PACKET` through independent intake and exact manual-review publication. |
| `CFR-073` | Import Sequence 14 H2 historically while freezing changed current source/runtime under distinct Sequence 15 authority. |
| `CFR-074` | Bind an exact independent-review appointment and maintainer candidate-digest acceptance, enforce a read-only reviewer workspace, and state honestly that same-UID human authorship is a governance rather than machine-verifiable property. |
| `CFR-075` | Require complete exact review of all `125` packet items and a total accepted/rejected truth table: accepted only when neither rejection signal exists, rejected when either exists. |
| `CFR-076` | Permit only the three exact no-gap states and broker both intake and review through locked, descriptor-retaining, crash-safe, atomic create-once publication. |
| `CFR-077` | Stop at `E2_REVIEW` with candidate/root absent and preserve fail-soft API/UI plus production scope. |
| `CFR-078` | Archive the exact Sequence 15 source package deterministically despite long authority filenames. |

## Acceptance criteria

### `AC-SEQ15-001` — exact parent H2 import

Given the exact accepted Sequence 14 authority, Tier, preflight, report, and
packet, when any Sequence 15 command runs, then the importer returns exactly
`S14_H2_PACKET` without current Sequence 14 source-member reads. Any byte,
metadata, schema, cross-link, cardinality, or later-leaf mutation is rejected
before a Sequence 15 write.

### `AC-SEQ15-002` — distinct active authority

Given accepted exact Sequence 15 authorization bytes and exact parent H2,
when bootstrap and preflight run, then the create-once authority reaches
`E0_PACKET`, binds current source/runtime, exposes only five fixed commands,
and grants no capture, comparison, candidate, or root authority.

### `AC-SEQ15-003` — independent complete intake

Given exact `E0_PACKET`, an authority-bound reviewer appointment, a read-only
reviewer workspace, and maintainer acceptance of the exact candidate digest,
when the broker receives those bytes on bounded stdin, then it atomically
creates one canonical mode-`0600` intake containing exactly `125` ordered
decisions, all packet bindings, a total accepted/rejected truth, and no
reviewer-caused workspace/source/runtime/evidence drift. Invalid, partial, or
crashed precommit input does not consume the formal path.

### `AC-SEQ15-004` — review-material integrity

Given `E1_INTAKE`, when verification or publication runs, then all five packet
inputs, all unique item image/sidecar references, and all active
source/supplemental leaves are retained as one `622`-descriptor transaction
through commit and reauthenticate by exact path, identity, SHA-256, and size.
Any missing, substituted, hardlinked, symlinked, unsafe, raced, or changed
material blocks review publication.

### `AC-SEQ15-005` — exact review publication

Given exact `E1_INTAKE`, when the real public review publisher runs, then it
stages the destination, completes the retained-descriptor precommit pass,
atomically publishes or exactly reopens byte-identical review bytes at a
different inode, completes postcommit validation while still locked, reaches
`E2_REVIEW`, and returns the exact reviewer decision from the same descriptor
operation.

### `AC-SEQ15-006` — decision truth and mandatory stop

Given an accepted or rejected valid intake, when it is published, then
publication succeeds while preserving that decision exactly. Candidate and
root remain absent, and every candidate/root command remains unauthorized.

### `AC-SEQ15-007` — compatibility and protected scope

Given the complete implementation diff, when targeted, recovery, fail-soft
API/UI, runtime, syntax, dependency, scope, diff, process, and protected-hash
gates run, then no unexplained failure, product behavior change, runtime
residue, or unplanned source/evidence mutation remains.

### `AC-SEQ15-008` — deterministic source authority

Given the same closed Sequence 15 source package twice, when deterministic
PAX archives are built, then both byte streams and ordered member sets are
identical; USTAR, path substitution, extra members, and missing members are
rejected.

## Implementation map

| ID | Planned implementation |
| --- | --- |
| `IMPL-117` | Exact Sequence 14 H2 historical importer and parent projection. |
| `IMPL-118` | Distinct Sequence 15 authorization, Tier, preflight, source/runtime, reviewer appointment, write-sandbox, and submission authority. |
| `IMPL-119` | Three-state prefix classifier and ordered current-state semantic validator. |
| `IMPL-120` | Sequence 15 packet/intake path override and strengthened manual-review v2 decision validator. |
| `IMPL-121` | Descriptor-relative `622`-leaf material transaction, descriptor-budget raise/restore, named-identity checks, and runtime reauthentication. |
| `IMPL-122` | Bounded-stdin atomic intake broker plus exact manual-review publisher, crash reconciliation, exact reopen, different-inode proof, and decision propagation. |
| `IMPL-123` | Five CLI handlers, argument validation, production registry, Make routes, and authorization candidate. |
| `IMPL-124` | Lifecycle, decision-quadrant, atomic-fault, race, production-shaped, compatibility, reviewer-isolation, and scope tests. |

## Test map

| ID | Test obligation |
| --- | --- |
| `TEST-152` | Reopen exact Sequence 14 authorization/Tier/preflight/report/packet and reject every byte, metadata, schema, cross-link, cardinality, or later-leaf mutation without live Sequence 14 source reads. |
| `TEST-153` | Verify Sequence 15 IDs, authorization body, source package, Tier/preflight, runtime receipt, exact reviewer appointment/session/freshness policy, submission capability, five-command grammar, registry, and Make routes. |
| `TEST-154` | Enumerate all `64` six-leaf existence patterns: only the three exact Sequence 15 states pass, and candidate/root fail in every state. |
| `TEST-155` | Validate exact `125`-item intakes, appointed reviewer/session, packet and candidate-digest binding, immutable preflight deadline, initial-only clock freshness, explanations, unique findings, and all four decision quadrants. |
| `TEST-156` | Mutate every manual-review field class and prove false acceptance, wrong appointed ID/session, pre-`createdAt`, post-deadline, future-at-initial-submit timestamp, or first submission after `reviewDeadline+300s`, cross-packet replay, candidate-digest mismatch, empty text, duplicate ID, packet-v1 substitution, and path derivation all fail; prove item-only, finding-only, and combined rejection pass. |
| `TEST-157` | Retain and reauthenticate every packet material plus active source/supplemental leaf; reject missing, changed, conflicting-ref, unsafe-mode, symlink, hardlink, directory, owner, named-identity, size/hash, and precommit/postcommit substitution drift at each fault boundary. |
| `TEST-158` | Production-shaped four-quadrant flows atomically broker intake and publish exact different-inode review bytes; inject partial stdin, temp write/fsync/rename/parent-fsync crashes, concurrent commands, immediate and post-deadline exact E1/E2 reruns, and differing collision; prove reconciles are read-only, propagate exact decision, and retain candidate/root absence. |
| `TEST-159` | Existing Sequence 8–14 and generic review publishers remain behaviorally unchanged; legacy path derivation cannot consume the Sequence 14 packet. |
| `TEST-160` | Reviewer OS-sandbox simulation proves a read-only workspace, isolated external candidate output, empty pre/post workspace write set, no `.agents`/`.git`/`.venv`/cache/source/evidence/capture/report/packet/intake/review/candidate/root write, and fail-closed behavior when sandbox enforcement is unavailable. |
| `TEST-161` | Deterministic PAX, complete recovery, fail-soft API/UI, Python 3.10 AST, compile, tabnanny, dependency, whitespace, dirty-worktree, source-scope, runtime, process, diff, and protected-hash gates pass. |

## Given-When-Then scenarios

| Scenario | Given | When | Then |
| --- | --- | --- | --- |
| `SC-AC-SEQ15-001-HP-001` | Exact Sequence 14 H2 | Parent importer runs | Return `S14_H2_PACKET` |
| `SC-AC-SEQ15-001-NP-001` | One parent byte or metadata field differs | Importer runs | Reject before write |
| `SC-AC-SEQ15-001-NP-002` | Packet schema/count/link differs | Importer runs | Reject |
| `SC-AC-SEQ15-001-NP-003` | Intake or later leaf exists before first preflight | Preflight creation runs | Reject boundary |
| `SC-AC-SEQ15-001-EP-001` | Current coordinator differs from frozen Seq14 source | Importer runs | Historical H2 still authenticates |
| `SC-AC-SEQ15-002-HP-001` | Accepted Seq15 auth, exact H2 | Bootstrap/preflight run | Reach `E0_PACKET` |
| `SC-AC-SEQ15-002-NP-001` | ID/auth/source/runtime drift | Any Seq15 command runs | Fail before publication |
| `SC-AC-SEQ15-002-NP-002` | Capture/compare/candidate/root flag or command | Parser runs | Reject |
| `SC-AC-SEQ15-002-EP-001` | Exact Tier/preflight already exists | Bootstrap/preflight reruns | Read-only exact reopen |
| `SC-AC-SEQ15-003-HP-001` | Exact appointment and accepted candidate digest | Broker receives valid accepted bytes | Atomically reach `E1_INTAKE` |
| `SC-AC-SEQ15-003-HP-002` | Exact appointment and any valid rejection quadrant | Broker receives valid rejected bytes | Atomically reach `E1_INTAKE` |
| `SC-AC-SEQ15-003-NP-001` | Wrong appointment/session, packet, freshness, or candidate digest | Broker runs | Reject before destination write |
| `SC-AC-SEQ15-003-NP-002` | Reviewer sandbox attempts a workspace write | Reviewer runs | OS denies; broker never starts |
| `SC-AC-SEQ15-003-NP-003` | Partial stdin or pre-rename crash | Broker runs | No formal intake; owned temp reconciled |
| `SC-AC-SEQ15-003-NP-004` | First submit occurs after `reviewDeadline+300s` | Broker runs from E0 | Reject before stage/write |
| `SC-AC-SEQ15-003-EP-001` | Commit succeeded but response was lost | Exact broker rerun | Read-only exact `E1_INTAKE` reopen |
| `SC-AC-SEQ15-003-EP-002` | Exact E1/E2 is older than review deadline | Exact broker rerun | Read-only success; no ambient expiry |
| `SC-AC-SEQ15-003-EP-003` | Same-UID implementer copies appointed ID | Machine validator runs | Not claimed detectable; governance gate must block |
| `SC-AC-SEQ15-004-HP-001` | All packet materials exact | Material authenticator runs | Pass complete deduplicated set |
| `SC-AC-SEQ15-004-NP-001` | One image or sidecar differs | Verify/publish runs | Reject before review write |
| `SC-AC-SEQ15-004-NP-002` | Same path has conflicting refs | Authenticator runs | Reject |
| `SC-AC-SEQ15-004-EP-001` | Before and after refs are identical | Authenticator runs | Hash once, preserve two item roles |
| `SC-AC-SEQ15-004-NP-003` | One retained name/inode/hash changes before commit | Broker/publisher runs | Reject before atomic rename |
| `SC-AC-SEQ15-004-NP-004` | Descriptor budget cannot reach `938` | Broker/publisher runs | Reject before staging/write |
| `SC-AC-SEQ15-005-HP-001` | Exact accepted `E1_INTAKE` | Publisher runs | `E2_REVIEW`, decision accepted |
| `SC-AC-SEQ15-005-HP-002` | Exact rejected `E1_INTAKE` | Publisher runs | `E2_REVIEW`, decision rejected |
| `SC-AC-SEQ15-005-NP-001` | Destination collision differs | Publisher runs | Reject without overwrite |
| `SC-AC-SEQ15-005-EP-001` | Exact `E2_REVIEW` | Publisher reruns | Read-only exact reopen |
| `SC-AC-SEQ15-006-HP-001` | No rejected item and no blocker | Validator runs | Only `accepted` is valid |
| `SC-AC-SEQ15-006-HP-002` | Rejected item only | Validator runs | Only `rejected` is valid |
| `SC-AC-SEQ15-006-HP-003` | Blocking finding only | Validator runs | Only `rejected` is valid |
| `SC-AC-SEQ15-006-HP-004` | Rejected item and blocking finding | Validator runs | Only `rejected` is valid |
| `SC-AC-SEQ15-006-NP-001` | Accepted status with either rejection signal | Validator runs | Reject false acceptance |
| `SC-AC-SEQ15-006-NP-002` | Rejected status with neither rejection signal | Validator runs | Reject false rejection |
| `SC-AC-SEQ15-006-BP-001` | Exact accepted review exists | Candidate/root command attempted | Grammar/authority rejection |
| `SC-AC-SEQ15-006-BP-002` | Exact rejected review exists | Candidate/root command attempted | Grammar/authority rejection |
| `SC-AC-SEQ15-007-HP-001` | Complete planned diff | All verification gates run | Green exact scope |
| `SC-AC-SEQ15-007-NP-001` | UI/API/evidence/dependency drift | Scope gate runs | Block completion |
| `SC-AC-SEQ15-007-NP-002` | Owned process/cache/runtime residue remains | Cleanup gate runs | Block completion |
| `SC-AC-SEQ15-008-HP-001` | Same closed package twice | PAX build runs | Identical bytes/member order |
| `SC-AC-SEQ15-008-NP-001` | USTAR/path substitution/member drift | Archive test runs | Reject |

## Affected files

### Planned implementation edits

```text
Makefile
scripts/ui_ux_theme_handoff.py
scripts/test_ui_ux_theme_handoff.py
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-continuation-seq15.md
.agents/builder.md
.agents/scribe.md
.agents/PROJECT.md
```

The accepted plan and ledger become read-only implementation inputs. If
implementation requires editing either file, stop and return to plan review.

### Formal execution outputs after later authorization

```text
.claude/ui_snapshots/ux1b/recovery/.historical-stack-external-review-continuation-20260729T070000Z.lease
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-continuation-prechange-seq15.json
docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-external-review-continuation-rollback-seq15.json
.claude/ui_snapshots/ux1b/recovery/theme-handoff-historical-stack-external-review-continuation-prechange-20260729T071000Z/
.claude/ui_snapshots/ux1b/recovery/theme-handoff-historical-stack-external-review-continuation-preflight-20260729T070000Z.json
.claude/ui_snapshots/ux1b/review-intake/control-migration-20260729T060000Z.json
.claude/ui_snapshots/ux1b/recovery/control-migration-manual-review-20260729T060000Z.json
```

All seven formal outputs are coordinator-owned. The review decision bytes are
independently authored in an isolated candidate outside the workspace; the
coordinator atomically brokers those exact accepted bytes into intake and then
publishes the manual review from them.

### Protected paths

```text
all Sequence 8–14 plans, ledgers, authorizations, Tier, preflights, captures,
stacks, manifests, reports, packets, intakes, reviews, candidates, and roots
all production UI/API/provider/fixture/theme/evidence files
all packet-referenced images and sidecars
requirements.txt
.venv/
```

The only permitted writes outside planned implementation paths are
skill-journal/activity rows outside the `E0_PACKET..E2_REVIEW` protected
interval and, during later formal execution, the exact Sequence 15 outputs
listed above. Formal reviewer execution permits no workspace journal or cache
exception.

## Implementation sequence and gates

### Phase S15-0 — reopen and fingerprint

- Recompute every Sequence 14 hash, size, and mode listed in this plan.
- Reopen report and packet semantics read-only.
- Require current `[1,1,0,0,0,0]` forward presence.
- Inventory planned source preimages and unrelated dirty paths.
- Confirm no Sequence 15 Tier/preflight path exists.
- Reproduce the generic path mismatch read-only: the packet's original
  `lineageId` must not derive its Sequence 14 continuation path.

**Gate:** any parent drift, later leaf, unsafe metadata, or unexplained planned
path collision blocks implementation.

### Phase S15-1 — tests first

- Add `TEST-152..161` as red tests, including every decision quadrant,
  broker fault boundary, descriptor substitution boundary, competing command,
  reviewer-sandbox, and exact-rerun case.
- Use test-owned roots for all existence matrices, intake/review publication,
  mutation, collision, accepted/rejected, and runtime-drift simulations.
- Preserve exact real H2 bytes as read-only fixtures; do not copy formal
  intake/review into the real workspace.
- Prove old generic publishers remain unchanged.

**Gate:** new tests fail only for missing Sequence 15 behavior. Existing
Sequence 14 tests remain green.

### Phase S15-2 — historical import and active authority

- Implement `IMPL-117..119`.
- Add fixed IDs, parent refs, paths, schemas, allowed commands, and Tier
  destinations.
- Build the exact Sequence 14 historical H2 importer.
- Add deterministic PAX Tier and current source/runtime preflight.
- Add the three-state classifier and ordered semantic validator.

**Gate:** all `64` existence patterns produce the exact three-pass/61-fail
result; parent and source/runtime mutations fail before writes.

### Phase S15-3 — intake and material validation

- Implement `IMPL-120..121`.
- Add the fixed Sequence 15 path override without changing old derivation.
- Strengthen decision equivalence for this continuation.
- Add the exact reviewer appointment/session/freshness validator and document
  the external maintainer governance gate without claiming same-UID authorship
  proof.
- Authenticate and retain all `622` unique source, supplemental,
  input/image/sidecar leaves descriptor-relative through commit.
- Raise the descriptor soft limit to at least `938` before any stage and
  restore it on every exit.
- Reject conflicts where the same path carries different expected bytes.

**Gate:** accepted and rejected positive fixtures pass; every field/material
mutation fails before manual-review publication.

### Phase S15-4 — atomic intake/review publication and public surface

- Implement `IMPL-122..123`.
- Add bounded-stdin intake submission under the global lock/lease using
  `_publish_regular_exact()` and the fixed path only.
- Validate in memory before staging; cover temp write/fsync/rename/parent-fsync
  crash reconciliation and concurrent command serialization.
- Publish exact intake bytes once and prove a different inode.
- Reopen exact `E2_REVIEW` without writing.
- Return exact decision from the same descriptor operation.
- Add the five commands, fixed grammar, handlers, registry, Make routes, and
  authorization candidate generator.

**Gate:** production-shaped accepted and rejected flows both reach
`E2_REVIEW`; candidate/root remain absent and unauthorized.

### Phase S15-5 — implementation verification

- Run focused tests and the complete recovery coordinator suite.
- Run artifact-loader, fail-soft API/UI, navigation, and component regressions.
- Run compile, Python 3.10 AST, tabnanny, dependency, whitespace, diff, dirty
  worktree, source-scope, runtime, process, and protected-hash gates.
- Compare actual diff to this affected-file plan.
- Run deterministic PAX twice.
- Generate the authorization candidate but do not bootstrap.

**Gate:** no blocker/high/medium review finding, failing test caused by the
change, scope drift, protected mutation, cache/runtime residue, or unexplained
diff remains.

### Phase S15-6 — authorization acceptance

- Report exact whole-file SHA-256, size, and mode for the final authorization
  candidate.
- Before that candidate is frozen, appoint the independent reviewer and exact
  one-use review session in the authorization. The reviewer must not receive
  implementation authorship work.
- Maintainer explicitly accepts those exact bytes.
- Re-run pre-write protected hashes and all absence/collision gates.

**Gate:** without exact acceptance, no Sequence 15 formal output may be
created.

### Phase S15-7 — bootstrap and mandatory reviewer pause

- Bootstrap and preflight Sequence 15.
- Reopen exact `E0_PACKET`.
- Reauthenticate current source/runtime and exact parent H2.
- Stop for independent reviewer intake.

**Gate:** only Sequence 15 Tier/preflight exist. Intake, review, candidate, and
root remain absent.

### Phase S15-8 — independent review and atomic intake

- Use the exact independent Judge appointment already bound by accepted
  authority; do not substitute another reviewer/session.
- Use only isolated read-only image tooling outside frozen runtime trees.
- Run the reviewer under an OS write sandbox with the workspace read-only,
  capture a complete pre/post namespace fingerprint, and require an empty
  workspace write set.
- Review all `125` items and create one exact candidate outside the workspace.
- Report candidate SHA-256 and size; require the maintainer to explicitly
  accept those exact bytes for the appointed review session.
- Stream the same bytes to the atomic intake broker and reconcile exact reruns.
- Re-run Sequence 15 verification at `E1_INTAKE`.

**Gate:** appointment/session, maintainer-accepted candidate digest, and intake
are exact; the reviewer workspace write set is empty; source/runtime/evidence
remain exact. Any drift, sandbox unavailability, or digest mismatch blocks
submission/publication.

### Phase S15-9 — publish review and stop

- Run the real public review publisher.
- Reopen exact byte-identical, different-inode manual review.
- Verify exact accepted/rejected decision.
- Reauthenticate `E2_REVIEW`.
- Stop with candidate and root absent.

**Gate:** formal Sequence 15 execution ends at `E2_REVIEW` regardless of
reviewer decision. Any later continuation requires a new reviewed authority.

## Verification commands

Implementation must run at least:

```zsh
.venv/bin/python -B scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -B scripts/test_artifact_loader.py
.venv/bin/python -B scripts/test_api.py
.venv/bin/python -B scripts/test_ui_read_api.py
.venv/bin/python -B scripts/test_dashboard_navigation.py
make test
.venv/bin/python -B -m py_compile scripts/ui_ux_theme_handoff.py scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -B -m tabnanny scripts/ui_ux_theme_handoff.py scripts/test_ui_ux_theme_handoff.py
git diff --check
```

The implementation must also run the existing repository-specific Python 3.10
AST, dependency, duplicate-YAML, Make-contract, protected-hash, dirty-worktree,
runtime-tree, process, cleanup, and deterministic archive gates used by
Sequence 14. A skipped command must be reported with a concrete reason and
must not be counted as passing evidence.

Formal execution commands are intentionally absent from this plan until the
authorization candidate is implemented, reviewed, and accepted.

## Rollback

### Before formal bootstrap

- Revert only planned Sequence 15 implementation paths.
- Delete only an unaccepted Sequence 15 authorization candidate.
- Do not touch any Sequence 14 or unrelated dirty file.

### After Tier but before preflight

- Use only the Sequence 15 rollback contract.
- Preserve failed Tier artifacts for diagnosis unless that contract explicitly
  authorizes cleanup.

### After preflight at `E0_PACKET`

- Do not edit or delete preflight, parent H2, or any protected path.
- Retry only exact reopen/verification commands.
- Invalid/partial candidate bytes and every pre-rename broker failure leave the
  final intake absent; reconcile only the broker-owned same-directory temp
  according to `_publish_regular_exact()`.
- If the atomic intake commit completed but the response was lost, resubmit
  only the same exact accepted bytes for read-only `E1_INTAKE` or `E2_REVIEW`
  reconciliation. This remains valid after the immutable review deadline
  because no ambient freshness check is repeated. Differing bytes require a
  separately reviewed continuation and are never overwritten.

### After intake at `E1_INTAKE`

- Retain the already fully validated intake exactly, including a valid
  rejected intake.
- Do not rewrite, delete, normalize, or self-correct reviewer bytes.
- A postcommit environmental drift is an incident; retain the intake and use a
  separately reviewed correction. Invalid review content cannot reach the
  committed `E1_INTAKE` path.

### After review at `E2_REVIEW`

- Retain intake and manual review exactly.
- Do not promote a rejection or delete a blocking finding.
- Candidate/root work requires a new reviewed continuation.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Sequence 14 forbids intake/review | Supply a separately accepted Sequence 15 continuation; never reinterpret parent authority. |
| Live Sequence 14 preflight rejects changed source | Import exact H2 historically and freeze current source under Sequence 15. |
| Packet lineage derives the old packet path | Use one closed internal path override; leave generic path behavior unchanged. |
| Same-UID implementer impersonates reviewer | Bind the exact appointment/session/packet/freshness and maintainer-accepted candidate digest, require actual independent Judge assignment, and explicitly treat human authorship as a governance gate rather than make a false machine-verification claim. |
| Reviewer mutates workspace or frozen `.venv` | Run reviewer with OS-enforced read-only workspace and isolated external output; require an empty pre/post workspace write set and reauthenticate runtime/source after submission. |
| Partial/crashed intake consumes create-once path | Validate bounded stdin before staging and reuse same-directory fsync plus atomic no-replace publication; exact postcommit rerun reopens read-only. |
| Freshness makes a committed intake expire | Bind `reviewDeadline` once in preflight, use ambient clock only at initial E0 commit, and authorize exact read-only E1/E2 reconciliation indefinitely. |
| Machine pass substitutes for visual review | Require changed-item visual inspection and per-item explanations. |
| Sidecar disagrees with pixels | Pixels control the verdict; record and reject unexplained disagreement. |
| Evidence/source changes between validation and publication | Retain all `622` descriptors under the lock/lease, recheck named identity and hashes immediately before atomic commit, and revalidate before releasing the transaction. |
| Valid rejection is reported as command failure | Separate publication success from exact reviewer decision. |
| False accepted/rejected review passes schema | Enforce the complete four-quadrant complement: accepted iff neither rejection signal exists; rejected iff either exists. |
| Manual review aliases intake | Require byte identity and different inode. |
| Rerun overwrites formal review | Exact reopen is read-only; differing collisions fail closed. |
| Candidate/root appears early | Reject every state containing either path and expose no command authority. |
| Dirty worktree is damaged | Edit only planned paths, fingerprint before/after, never reset/clean. |
| Long plan path breaks archive | Reuse deterministic PAX and test byte equality plus ordered members. |
| API/UI becomes more brittle | Keep production paths read-only and run explicit fail-soft regressions. |

## Review checklist

- [x] Exact accepted Sequence 14 H2 is sufficient and fully enumerated.
- [x] Historical and active source/runtime authority are separated.
- [x] Packet v2 lineage/path mismatch has one closed correction.
- [x] All `64` forward existence patterns have a binary oracle.
- [x] Intake/review schemas, counts, order, bindings, and decisions are exact.
- [x] All `622` retained leaves remain descriptor/name/hash exact through the
  atomic commit, with budget raise/restore and substitution tests.
- [x] Intake submission is locked, bounded, atomic, crash-reconcilable, and
  unable to consume the final path on invalid or precommit failure.
- [x] Initial freshness is bound to immutable preflight time; exact committed
  E1/E2 reconciliation never expires or writes again.
- [x] Reviewer appointment/session/freshness and candidate digest are machine
  bound; same-UID authorship is honestly delegated to the independent-review
  and maintainer governance gates.
- [x] Reviewer workspace write isolation and frozen-runtime protection are
  OS-enforced, audited, and fail closed when unavailable.
- [x] Accepted and rejected reviews are both preserved honestly.
- [x] All four decision quadrants have an exact positive/negative oracle.
- [x] Manual review is byte-identical, different-inode, create-once, and
  exactly reopenable.
- [x] Candidate/root commands and writes remain absent.
- [x] Affected files, tests, risks, rollback, and formal pauses are explicit.
- [x] Traceability is closed and bidirectional.
- [x] No unresolved blocker remains.

## Review findings

Any unresolved Blocker, High, or Medium finding prevents `REVIEWED`.

| Iteration | Finding | Severity | Resolution |
| ---: | --- | --- | --- |
| `1` | Reviewer identity was only a self-asserted nonempty string. | High | Bound an exact composite reviewer/session, packet, immutable time window, and maintainer-accepted candidate digest; documented same-UID authorship honestly as an external governance gate. |
| `1` | Reviewer wrote the create-once final intake path directly, allowing partial/crashed bytes and command races. | High | Added the fixed bounded-stdin broker under the global lock/lease using same-directory fsync and atomic no-replace publication, with read-only exact reconciliation. |
| `1` | Rejected truth required both an item rejection and a blocking finding, leaving two quadrants invalid. | High | Defined the total complement: accepted iff neither signal exists; rejected iff either exists, and test all four quadrants. |
| `1` | Evidence/source validation did not retain identity through commit. | High | Retain exactly `291+270+61=622` content descriptors plus fixed authority/runtime descriptors, require a `938` floor under the `1536` ceiling, and revalidate before and after atomic commit. |
| `1` | Reviewer write isolation was asserted but not enforced and conflicted with journal exceptions. | Medium | Require an OS-enforced read-only workspace, isolated external candidate output, empty namespace write set, and no formal reviewer journal/cache writes. |
| `2` | Initial freshness rules would also expire committed E1/E2 exact reruns. | Medium | Store immutable `reviewDeadline`, apply ambient clock checks only at initial E0 commit, and authorize indefinite read-only exact E1/E2 reconciliation. |
| `3` | Initial submit lacked a lower bound tying broker time to the immutable deadline. | Medium | Require `brokerNow <= reviewDeadline+300s` at E0 and reject post-deadline first submission while retaining ambient-time-free E1/E2 reopen. |
| `3` | Rechecked complete authority, lifecycle, atomicity, truth table, descriptor transaction, reviewer isolation, rollback, tests, scope, and traceability. | None | Independent Judge returned `PASS` with no unresolved Critical, High, Medium, or useful Low finding. |

## Traceability summary

The sibling ledger must bind `REQ-016`, `CFR-073..078`,
`AC-SEQ15-001..008`, `IMPL-117..124`, and `TEST-152..161`
bidirectionally with `10000` basis-point structural coverage, no gaps, no
orphans, and no asymmetric edges.

Planning verdicts remain `NOT_TESTED`. Plan review does not claim
implementation or runtime execution.

## Success metrics

| Metric | Target | Measurement |
| --- | ---: | --- |
| Parent H2 exactness | `100%` | All listed refs and semantics reauthenticate |
| Lifecycle matrix | `3/64` valid | Exhaustive test-owned existence matrix |
| Review item coverage | `125/125` | Intake IDs equal packet IDs in exact order |
| Changed-item visual coverage | `67/67` | Reviewer item explanations and review record |
| Control-root sidecar coverage | `44/44` | Reviewer item explanations and exact refs |
| Material integrity | `100%` | All deduplicated refs hash/size pass |
| Retained descriptor transaction | `622/622` | Precommit/postcommit identity and hash oracle |
| Descriptor floor | `>=938`, `<=1536` | Runtime limit gate plus restoration test |
| Intake atomicity | `0` partial final leaves | Broker fault/concurrency matrix |
| Reviewer workspace writes | `0` | OS sandbox plus namespace write-set audit |
| Traceability coverage | `10000 bps` | Canonical ledger validator |
| Candidate/root writes | `0` | Formal namespace verification |
| Product/evidence/runtime drift | `0` | Protected-hash and runtime/source gates |

## Dependencies

- Exact accepted Sequence 14 H2 artifacts listed above.
- Existing canonical JSON, descriptor, lock/lease, PAX, runtime receipt,
  packet v2, manual-review v2, and formal publication primitives.
- An independent Judge reviewer available after Sequence 15 preflight.
- Maintainer acceptance of the later exact authorization candidate.

## Change history

| Version | Date | Change |
| --- | --- | --- |
| `0.1-draft` | `2026-07-29` | Initial Sequence 15 external-review continuation draft for independent blocking review. |
| `0.2-review-fixes` | `2026-07-29` | Resolve first-round identity-boundary, atomic intake, decision truth-table, material TOCTOU, and reviewer write-isolation findings, then close the second-round durable reconciliation/freshness conflict; pending final closure review. |
| `1.0-reviewed` | `2026-07-29` | Independent Judge closure review passed after the initial-submit deadline bound; no unresolved blocking finding remains. |

## Next handoff

1. Freeze this reviewed plan and canonical traceability ledger.
2. Report their exact SHA-256, byte size, and mode.
3. Wait for explicit maintainer approval before implementation.
