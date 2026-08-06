# Quant Radar UX-1B Sequence 20 Prerequisite Live-Authority Baseline Correction Amendment

## Document Control

| Field | Value |
|---|---|
| Type | Blocking prerequisite correction amendment |
| Version | `1.2` |
| Status | `REVIEW APPROVED — exact maintainer acceptance required` |
| Date | 2026-07-31 |
| Author | Scribe |
| Reviewer | Judge single-engine Codex review, then repository maintainer |
| Audience | Maintainer, implementation agent, formal-state reviewer |
| Sequence effect | No new formal sequence; amends the accepted prerequisite correction only |
| Parent plan | `2026-07-31-quant-radar-ui-ux-ux1b-task9-sequence20-prerequisite-live-authority-baseline-correction.md` |
| Sibling ledger | Same basename with `.traceability.yaml` |

## Purpose

Implementation of the accepted prerequisite plan correctly stopped when its
entry authority changed. The stop was required by Phase P0 and the plan's
risk controls. The worktree now contains:

- a bounded partial implementation in the three originally authorized source
  files;
- additional accepted Codex/API migration bytes that arrived after the
  prerequisite entry snapshot;
- ten new coordinator failures caused by those later live bytes;
- four compatibility-test failures in a file the parent plan protected.

The parent plan therefore cannot be completed safely as written. This
amendment rebases only the prerequisite correction boundary. It does not
authorize Sequence 20, does not edit any formal-state artifact, and does not
turn historical authority into current authority.

## Precedence and Authorization Boundary

This amendment has no implementation authority until both this document and
its sibling ledger have:

1. passed independent review;
2. been frozen by exact whole-file SHA-256, byte size, and mode; and
3. been explicitly accepted by the repository maintainer.

After acceptance, this amendment overrides the parent plan only where the two
documents conflict:

- the entry hashes and failure budget;
- the implementation file allowlist;
- the snapshot-subset current fixture binding;
- the selector postimage lifecycle model;
- the current Codex UI migration model;
- the current-versus-historical source-projection model;
- the inherited `AC-BLC-004` current-member value and `AC-BLC-008`
  implementation-file exception set;
- the verification gates and phase ordering added below.

All other parent requirements, prohibitions, historical bindings, Sequence 20
pause boundaries, and the final `169/176` target remain in force.

The accepted parent plan and ledger remain immutable:

| Path | SHA-256 | Size | Mode |
|---|---|---:|---:|
| `docs/superpowers/plans/2026-07-31-quant-radar-ui-ux-ux1b-task9-sequence20-prerequisite-live-authority-baseline-correction.md` | `31f51c6e1945bafc347004e728063ca19ce4ab453e10aee009bfdb0dd73517e4` | 30121 | `0644` |
| Same basename with `.traceability.yaml` | `1342a4c7e693961b35563f1793e868fcbe0e4fde4c54d7457a9263a7185b96b5` | 7854 | `0644` |

## Reviewed Stop Evidence

### Partial-state coordinator result

A fresh coordinator run at the amendment intake boundary reports:

```text
126/176 passed
0 controlled missing-behavior failures
50 unexpected failures
```

The exact unexpected-ID set is:

```text
003 005 013 017 021 026 033 034 035
081 084 096 098 099 100 101 102 103
121 136 148 149 150 151
157 158 164 167 169
177 178 179
183 184 186 187 189 190 191 194 195 196
200 202 203 204 206 207 208 209
```

This partitions exactly into:

- 33 still-red parent-plan prerequisite IDs;
- 10 newly exposed prerequisite IDs:
  `003,157,167,169,177,179,190,191,194,204`;
- the original seven Sequence 20 targets:
  `200,202,203,206,207,208,209`.

`TEST-006` is the one parent-plan prerequisite ID already green under the
partial implementation. It must remain green.

### Compatibility-gate result

An isolated run of all 19 functions in `scripts/test_ui_ux_contract.py`
reports `15/19`. The four failures are:

```text
test_primary_action_full_call_projection_and_mutations_fail_closed
test_ux1b_prechange_and_forward_mutations_fail_closed
test_ux1b_prechange_plan_pages_markers_and_rollback
test_ux1b_forward_classification_and_backward_projection
```

Those failures are outside the 176-test coordinator denominator but block
completion.

## Exact Amendment Entry State

All records below are read-only entry authority except the four implementation
files explicitly listed later.

| Path | SHA-256 | Size | Mode | Disposition |
|---|---|---:|---:|---|
| `requirements.txt` | `1ab5cc81e8e3aab7a3b48b80449087ddf250d22b12b1a8b9b4f5e46b0e790138` | 351 | `0644` | Preserve current dependency state |
| `scripts/ui_ux_inventory.py` | `d143f1e7e3daa7d7e031b6babe63beb017c966cf69585364cf338e21025428f3` | 58293 | `0644` | Partial parser fix retained |
| `scripts/ui_ux_fixtures.py` | `a396da4814167c096cc7ee7b931e5da902b85bf3f48cf829fe19149a49050c90` | 143259 | `0644` | Preserve; new current closure input |
| `scripts/ui_ux_evidence.py` | `4835c2e73c46274c77c232166d2e48ec0ccef49542a9a9dd2811b0d5b6ed39c9` | 417548 | `0644` | Preserve |
| `scripts/ui_ux_theme_handoff.py` | `0d0f2d90e5a3b89a6f01ad7282080aa61129506099d502d8d17fbe228d8f8656` | 1934154 | `0644` | Partial implementation; revise |
| `scripts/test_ui_ux_theme_handoff.py` | `f6ffb3b7e6ab0db6cd5beb689c01229b24f663dad15688c122ac1a6cd5b3bc6a` | 1295527 | `0644` | Partial tests; revise |
| `scripts/test_ui_ux_contract.py` | `39bf21d583f34399ed6d5477ec8dacb5f25504bfa540a84dcdf04f8d35b5a35a` | 69350 | `0644` | Newly allowed compatibility correction |
| `Makefile` | `8614f713b699087e2d55ff50d61467af6e79f2cd5c61824b9b8d6e8c05eec080` | 73833 | `0644` | Preserve current Codex routes |
| `ui/us_cot.py` | `e5f153faf3fa028f14ffbac67e640d01b8035135697bb21221c861f73d755c40` | 12651 | `0644` | Preserve |
| `ui/analytics_db.py` | `70c2f2fb22fd5ee7bd2e0da406946ca06168faf0b6f575246aac964c6e4dd067` | 44375 | `0644` | Preserve current API-backed UI |
| `ui/x_sentiment.py` | `fd5c4dea3bc7ccbbfbc320df2939980339edc9b5d9d2841575057940e20a7ec0` | 40603 | `0644` | Preserve current Codex UI |

The canonical aggregate over the 42 sorted `ui/**/*.py` records, where each
line is `sha256 size mode path\n`, is:

```text
7c1611734c7ee14c495e1432d7eea767cefb50a15f0a14487cc4b12ae84a9ddd
```

Any entry-record or aggregate mismatch before implementation blocks execution
and requires a new reviewed amendment. No implementation constant may be
silently rebased.

## Later Live Drift Model

### Current selector member

The accepted Task 8 selector-delta contract remains immutable and records:

```text
ui/analytics_db.py
SHA-256 9475fb3c8614ed8e102c2619c325562025768445c45d5f625f0ad54d71467fe7
44382 bytes
```

The current live file is the exact `70c2...`/44375 record in the entry table.
The old record is historical authority; the new record is current live input.
Neither may replace the other globally.

### Current snapshot-subset member

The current candidate closure must bind `scripts/ui_ux_fixtures.py` to
`a396da4814167c096cc7ee7b931e5da902b85bf3f48cf829fe19149a49050c90`,
143259 bytes. The Sequence 13 embedded historical member remains
`afb269fab1de91a8376d4ac1c61df7d7dff96ca31c03a2e6acea36f1e546cd43`,
143247 bytes. The intermediate `41ca...` record in the partial implementation
is stale and must not survive.

### Exact current UX migration deltas

Relative to the accepted UX-1A contract:

| Projection | Count | Canonical sorted-newline SHA-256 | Canonical bytes |
|---|---:|---|---:|
| Diagnostic additions | 9 | `b5b83165e1bcb8cbd63e8c002e79454b08f0e62c5a566f8c42a74af3fd371dc2` | 1112 |
| Diagnostic removals | 14 | `16335375241385b055ee387b0d08a9b417a5d8e90169ef431c0046b3451744a7` | 1699 |
| Primary-action additions | 4 | `8a0d8d5aa873d6902eeb0dfa287e7d7a39ae616183da38e5caa1ffa9949f9fe3` | 534 |
| Primary-action removals | 3 | `04bd4a0ca75cbb14917498613b4195345f79921581cf6e621f44cc080438bccf` | 393 |

The current diagnostic count is 176 versus the historical parent count 181.
The current primary-action count is 20 versus the historical classified
count 19. Production validation may store only the exact count, canonical
byte length, and digest. Tests must independently enumerate the full exact
sets and prove one-record mutation rejection.

### Exact amendment-entry source-projection delta

The retained Sequence 8 root source projection is 270 records with digest:

```text
ce35963d1cacba10eb562c616eb894c23b973d1fe2a03b9d23f4c95f6e77691f
```

At Phase A0, before any resumed implementation, the exact amendment-entry live
source projection is 271 records with digest:

```text
0509aaeeb43ab0e3584c5f5829209dcd1fa8f8a41368702e8cc0bc0ea10d0e56
```

The current-versus-Sequence-8 projection **path-set** transition is exactly
four removals and five additions:

| Operation | Path | SHA-256 | Size | Projected mode |
|---|---|---|---:|---:|
| remove | `scripts/claude_auth_flow.py` | `c94255ba4984b7ec8318c8d8f632fad6fea007df2b5437c661e2751c335df140` | 9136 | `0444` |
| remove | `scripts/poc_grok_x_sentiment.py` | `ef00207302fafd14920f268577698a198d6ba9e1f304711401dbe317935fb2ae` | 5442 | `0444` |
| remove | `scripts/test_claude_auth_flow.py` | `27653e78923934e3438de021fdd60529447ea8a08fd9425cc90a52a8d4866d1e` | 4611 | `0444` |
| remove | `scripts/test_llm_client_agentic.py` | `a7b6de1a95c806f21073acc226e5fb7a7595fa21483f3aab1f89034a46637f0f` | 4907 | `0444` |
| add | `scripts/codex_auth_flow.py` | `bde4c64e4941a7a8f031f47ab693bc46c599ca71baac8d9c61fa714b6f5ea018` | 7882 | `0444` |
| add | `scripts/poc_codex_x_sentiment.py` | `e9934ab5e510e1f758fa5ac1ca1c21fae80d88f20a3f22589c54ae0883cdd410` | 2368 | `0444` |
| add | `scripts/test_codex_auth_flow.py` | `f3749c7bb9821f6409cc63ca9b57eeb3842cbddf15475ffeeb3c6703127ce2b5` | 5825 | `0444` |
| add | `scripts/test_llm_client_codex.py` | `a9a9ddc4195c2d377c4f45005f8ee8e59bab9cabb964a0c418f4f752b35c4572` | 7066 | `0444` |
| add | `scripts/test_x_influencers_codex.py` | `be6f275299d1a7de82c199bad65cbd6da33b2ffcde42c7bf5cdf74d63134dafb` | 2759 | `0444` |

The canonical path-set operation payload is reproducible as follows:

1. emit the four `remove` rows sorted by path, followed by the five `add` rows
   sorted by path;
2. represent each row as an object with exactly the keys `operation`, `path`,
   `sha256`, `size`, and `mode`, where `mode` is the projected-mode string;
3. encode each object as UTF-8 JSON with lexicographically sorted keys,
   `ensure_ascii=False`, separators `(",", ":")`, and no surrounding array;
4. append one LF byte (`0x0a`) after every object, including the last, and
   concatenate the nine rows.

That payload is 1480 bytes with SHA-256
`0de1f29316171802cd30328bd386e0f7b741dc19bf618a5aa0b24a46f4b186b4`.

Same-path content changes at Phase A0 are bound by the full amendment-entry
projection digest, not by the path-set delta digest. No implementation may
infer that unchanged paths have unchanged bytes.

### Post-implementation entry-receipt substitution model

The `0509...` digest is an amendment-entry receipt. It is not, and must never
be presented as, the raw post-implementation source digest. All four
implementation files are members of `scripts/**/*.py`, so their authorized
edits necessarily change the raw 271-record digest.

After the first authorized source edit, validation of the accepted entry
boundary uses this exact substitution model:

1. build the raw live projection with the accepted Sequence 8 source-mirror
   policy and require exactly 271 unique, sorted records;
2. require the raw path-set transition from Sequence 8 to remain exactly the
   four removes and five adds above;
3. require each of the four authorized implementation paths to remain a
   regular, non-symlink file with projected mode `0444`;
4. replace only those four raw records with their exact Phase A0 records from
   the amendment entry table;
5. canonicalize the resulting 271 records with the source-mirror schema and
   require digest
   `0509aaeeb43ab0e3584c5f5829209dcd1fa8f8a41368702e8cc0bc0ea10d0e56`.

The four substituted paths are:

```text
scripts/ui_ux_inventory.py
scripts/ui_ux_theme_handoff.py
scripts/test_ui_ux_theme_handoff.py
scripts/test_ui_ux_contract.py
```

This normalized receipt proves that no protected source record or path-set
member changed while allowing only the accepted implementation records to
advance. Their actual postimages remain governed by the four-file diff audit,
tests, and code review. The raw post-implementation 271-record digest is
diagnostic only; it gains authority only if a later, separately reviewed
Sequence 20 amendment freezes it. No validator may embed an unknown
post-implementation digest or compare the raw postimage to `0509...`.

Each later accepted sequence has its own exact 270-record receipt. They are
not interchangeable:

| History role | Retained preflight path | File SHA-256 | Size | Mode | `sourceProjection.digest` |
|---|---|---|---:|---:|---|
| Sequence 15 | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-historical-stack-external-review-continuation-preflight-20260729T070000Z.json` | `21b2ba6fed6e84f820feb1a091348be6e7be7c048d196fb79ef5d7489264485a` | 65278 | `0600` | `4a27ce4df6fc722e53b1214181bab2da2aea9392a861d6df7b4afbb02da94b64` |
| Sequence 16 | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-lifecycle-test-correction-preflight-20260729T080000Z.json` | `bde901d616f32abdaf02c663f4ac353aca403bf0852eb8f78e57fe74949f0eb1` | 66754 | `0600` | `a44dac6c0b215f36f83fe453fe8189b4249995991172f7cf85339e9835f71766` |
| Sequence 17 | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-formal-state-oracle-correction-preflight-20260730T010000Z.json` | `77d22454739d31db37553f06fd8fac0af085998432f882c4f292dda98b243568` | 67964 | `0600` | `1e454250f26658d9087698364fce9e9458cdfd8a802749624702b2d9aebfb392` |
| Sequence 18 / Sequence 19 predecessor | `.claude/ui_snapshots/ux1b/recovery/theme-handoff-external-review-o1-lifecycle-test-correction-preflight-20260730T030000Z.json` | `16232eefe0ef1dc7f1b4ba35c0d3954af450ea0637861732d83c1f6e57d2731d` | 69038 | `0600` | `2e5c77d67a7c2383c0618252076b74ae805661b4c7acef0a82db1439d1e91a4a` |

The accepted Sequence 15–19 source counts, retained-leaf counts, descriptor
budgets, plans, authorizations, and artifacts remain historical and must not
be incremented or regenerated. Old live-authority builders must reject the
271-record projection. Each historical replay must consume its own
authenticated stored 270-record projection without reading the removed paths,
substituting the new paths, or borrowing another sequence's receipt.

## Failure Inventory Amendment

The parent clusters remain active with these entry-state refinements:

| Cluster | Red IDs now | Amendment |
|---|---|---|
| `BLC-A` | `005,013,026,033,034,035` | Preserve the migrated requirements fixture and add selector history/live separation for current `ui/analytics_db.py`. |
| `BLC-B` | `017` | Parser hardening is retained; finish exact current migration classification. |
| `BLC-C` | `021` | Replace stale `41ca...` current closure with exact `a396...`; preserve Sequence 13 history. |
| `BLC-D` | `081,084,096,098,099,100,101,102,103` | Parent plan unchanged. |
| `BLC-E` | `121,158,164,178,183,184,186,187,189,195,196` | Parent runtime-receipt split remains required and must compose with stored 270-record projection replay. |
| `BLC-F` | `136,148,149,150,151` | Parent embedded-stack split remains required. |
| `BLC-G` | `003,157,167,169,177,179,190,191,194,204` | New exact current-versus-history source-projection boundary. |
| `BLC-H` | four named UX contract functions | New exact current Codex projection and requirements rollback compatibility boundary. |

`BLC-H` is outside the coordinator denominator. `BLC-G` contains no Sequence
20 implementation permission: TEST-204 must be restored as a historical
geometry test while the seven existing Sequence 20 target IDs stay red.

## Scope

### Implementation files allowed after exact acceptance

- `scripts/ui_ux_inventory.py`
- `scripts/ui_ux_theme_handoff.py`
- `scripts/test_ui_ux_theme_handoff.py`
- `scripts/test_ui_ux_contract.py`

The first three continue the parent authorization. The fourth is added only
for `BLC-H`.

### Documentation and journal files allowed during this review

- this amendment;
- its sibling traceability ledger;
- `.agents/scribe.md`;
- `.agents/judge.md`;
- one corresponding row in `.agents/PROJECT.md`.

### Protected live inputs

Everything in the exact entry table other than the four implementation files
is read-only. In particular:

- do not edit, restore, or rename the nine source-projection migration paths;
- do not edit `requirements.txt`, `Makefile`, `scripts/ui_ux_fixtures.py`,
  `ui/analytics_db.py`, `ui/x_sentiment.py`, or any other UI file;
- do not edit classification, selector-delta, capture-stack, preflight,
  authorization, review, or publication artifacts;
- do not edit the accepted parent plan/ledger or the blocked Sequence 20
  plan/ledger.

## Added and Modified Requirements

### `CFR-119A` — Rebased current snapshot closure

This requirement supersedes the current-member value in `CFR-119`. The
current closure is exactly `a396...`/143259/mode `0644`; the historical
Sequence 13 member remains `afb269...`/143247. TEST-021 must pass exact
current bytes and reject a one-byte mutation without altering either source.

### `CFR-124` — Selector postimage history/live separation

Extract an exact selector-delta validation core with two explicit policies:

- live validation continues rehashing every current selector member and
  deliberately rejects the current `ui/analytics_db.py` drift under the old
  Task 8 authority;
- historical replay authenticates the accepted selector contract and stored
  postimage receipts without opening or comparing current selector members.

Only legacy/historical call sites may use the history policy. Tests must prove
zero current-member reads, stored-record mutation rejection, and retained
live rejection. The Task 8 JSON must not change.

### `CFR-125` — Exact Codex UI migration profile

Both the scratch verifier and the UX contract compatibility test must accept
only the four exact migration deltas bound above. Compatibility, unsafe-HTML,
page, route, and fail-soft projections remain unchanged.

Production comparison must use canonical sorted-newline count, byte length,
and SHA-256 values. Tests must own a separate full-row oracle and demonstrate
that addition, removal, substitution, occurrence, and fingerprint mutations
fail closed. A count-only or provider-name-only check is forbidden.

### `CFR-126` — Pending rollback lifecycle awareness

While UX-1B classification remains `pending`, the rollback test must prove:

- `.streamlit/config.toml`, `app.py`, and `ui/_design.py` still equal their
  exact rollback records;
- the rollback `requirements.txt` remains exact
  `123fd3...`/426/mode `0644`;
- current `requirements.txt` is exact
  `1ab5...`/351/mode `0644`;
- no other pending-state difference is accepted.

The test must not change classification state or rewrite the rollback
manifest.

### `CFR-127` — Source-projection history/entry-receipt separation

Preserve the accepted 270-record source projection and every derived
Sequence 15–19 historical geometry constant. Add an authenticated history
import seam for replay paths and a separate exact amendment-entry receipt
validator for the 271-record Codex path set.

Historical replay:

- validates the sequence-specific stored 270-record projection, policy,
  digest, ordering, uniqueness, modes, exact containing preflight record, and
  stable retained artifact;
- performs no `lstat`, `open`, or read of the four removed paths;
- does not substitute any of the five added paths;
- feeds old Sequence 15–19 material/descriptor calculations their accepted
  historical projection.

Amendment-entry receipt validation:

- proves the exact four-remove/five-add delta and, at A0, the raw 271-record
  digest;
- after authorized edits, applies only the four-record substitution model
  above and rejects any protected-record, path-set, mode, or policy drift;
- remains incompatible with old Sequence 15–19 bootstrap authority;
- never treats `0509...` as the raw post-implementation digest.

The raw post-implementation projection is not authority in this prerequisite.
Freezing it is reserved for the future reviewed Sequence 20 amendment.

Do not globally change `270` to `271`, and do not increment retained-leaf or
descriptor constants in old sequences.

### `CFR-123A` — Amended completion gate

This requirement supersedes the entry partition, but not the final result, in
`CFR-123`. Completion requires:

- exact coordinator result `169/176`;
- zero controlled failures;
- exactly seven unexpected failures with IDs
  `200,202,203,206,207,208,209`;
- no workspace-guard failure;
- `scripts/test_ui_ux_contract.py` exactly `19/19`;
- artifact loader exactly `14/14`;
- API exactly `44/44`;
- Codex auth, Codex LLM client, and dashboard navigation gates green;
- no protected-byte drift.

## Partial Implementation Disposition

| Partial change | Disposition |
|---|---|
| Total URL parsing in `scripts/ui_ux_inventory.py` | Retain and complete its tests. |
| `SNAPSHOT_SUBSET_CLOSURE` changed to `41ca...` | Replace with exact `a396...`; do not touch historical stack records. |
| Raw Codex migration sets in handoff | Replace stale rows with compact exact count/length/digest validation. |
| Requirements lifecycle helper | Correct its reversed preimage assertion; retain exact current and rollback checks. |
| Fixture application to six still-red `BLC-A` tests and green TEST-006 | Compose with exact selector/history fixtures; restore every patch. |
| Legacy Sequence 8 runtime fixture | Retain only as an explicit historical replay seam; production call-site audit remains required. |

## Amended Implementation Phases

### Phase A0 — Re-entry gate

- [ ] `IMPL-205`: Rehash every amendment entry record, the 42-file UI
  aggregate, parent plan/ledger, blocked Sequence 20 plan/ledger, and formal
  protected namespace.
- [ ] `IMPL-206`: Reproduce exact coordinator `126/176` with the 50-ID set
  and isolated UX contract `15/19` with the four-function set.
- [ ] `IMPL-207`: Mechanically verify the exact 270-to-271 source delta and
  four current UX delta digests.

Any mismatch stops execution. This is a fresh blocker audit, not permission to
rebase again.

### Phase A1 — Finish current parser, closure, and selector boundaries

- [ ] Complete parent P1 with current `a396...` closure.
- [ ] `IMPL-208`: Implement `CFR-124` selector history/live policies and
  apply the history seam only to legacy replay.
- [ ] Fix the requirements helper so it independently proves old rollback
  authority before applying the current exact fixture.

Checkpoint: TEST-005/006/013/017/021/026/033/034/035 pass; the old live
selector validator still rejects current analytics bytes.

### Phase A2 — Exact UI migration compatibility

- [ ] `IMPL-209`: Replace the stale handoff migration sets with exact
  canonical count/length/digest validation.
- [ ] `IMPL-210`: Make the four UX contract functions lifecycle-aware under
  `CFR-125` and `CFR-126`, including independent mutation tests.

Checkpoint: `scripts/test_ui_ux_contract.py` reports exactly `19/19`, and
TEST-017 passes all scratch checks.

### Phase A3 — Source-projection lifecycle

- [ ] `IMPL-211`: Implement sequence-specific authenticated stored 270-record
  projection importers and the exact 271-record amendment-entry receipt
  validator, including the four-record post-edit substitution model.
- [ ] `IMPL-212`: Enumerate every Sequence 15–19 projection/material builder
  call site. Route retained-lineage replay through stored history; keep old
  live-authority rejection and all historical geometry constants unchanged.
- [ ] `IMPL-213`: Correct TEST-003 and the ten `BLC-G` tests with positive,
  mutation, no-removed-path-read, and live-rejection assertions.

Checkpoint: all ten `BLC-G` IDs are green, including TEST-204, without turning
any of the seven Sequence 20 target IDs green.

### Phase A4 — Resume parent P3–P5

Complete parent `IMPL-191` through `IMPL-199` with the selector and projection
history seams composed explicitly. Historical imports must not touch absent
Sequence 8 runtime, current `.venv`, changed selector members, changed
capture-stack members, or removed source-projection paths.

### Phase A5 — Closure

- [ ] Complete parent `IMPL-200` through `IMPL-204`.
- [ ] `IMPL-214`: Run the amended compatibility matrix, compare the actual
  diff with the four-file allowlist, review all changed code, and fix every
  blocking finding before reporting completion.

Stop at the exact seven-only baseline. Sequence 20 plan amendment remains a
separate maintainer-opened documentation continuation.

## Added Acceptance Criteria

### `AC-BLC-009` — Exact amendment re-entry

All entry records, aggregate digests, the 50-ID coordinator partition, and the
four-function UX contract partition match before resumed implementation.

### `AC-BLC-010` — Selector and closure lifecycle fidelity

Current fixture and analytics bytes are preserved, historical selector and
capture-stack authority remains immutable, historical replay avoids current
member reads, and old live validation rejects drift.

This criterion retains and supersedes the parent `AC-BLC-004` current-member
binding: its two inherited scenarios and `IMPL-187` remain effective, but the
exact current fixture is the `CFR-119A` `a396...` record.

### `AC-BLC-011` — Exact current UX migration compatibility

Both validators accept exactly the four bound delta sets and exact
requirements lifecycle, reject mutations, and preserve every unrelated UX
projection.

### `AC-BLC-012` — Exact projection lifecycle fidelity

Stored 270-record history replays with accepted old geometry; the 271-record
amendment-entry receipt and its four-record post-edit substitution model
validate exactly; old live authority rejects the 271-record path set; and no
old geometry constant or artifact changes.

### Retained `AC-BLC-008` — Concurrent migration preservation

The parent criterion and its two scenarios remain effective. Its sole
amendment is that the protected-byte exception set is the four implementation
files in this document, not the parent's three-file set. `requirements.txt`,
fixtures, Makefile, UI files, evidence source, API behavior, formal artifacts,
and Codex migration bytes remain exact.

## Added Test Scenarios

| ID | Requirement | Scenario | Expected |
|---|---|---|---|
| `SC-AC-BLC-009-HP-001` | `CFR-123A` | Rehash exact continuation state | All entry records and both failure partitions match |
| `SC-AC-BLC-009-NP-001` | `CFR-123A` | Any record or failure ID drifts | Stop before implementation |
| `SC-AC-BLC-010-HP-001` | `CFR-119A`,`CFR-124` | Exact current fixture plus historical selector replay | Candidate closure and legacy replay pass |
| `SC-AC-BLC-010-NP-001` | `CFR-119A`,`CFR-124` | Fixture byte or stored selector receipt changes | Fail closed before operation |
| `SC-AC-BLC-010-BP-001` | `CFR-124` | Old live selector authority reads current analytics | Deliberate contract rejection |
| `SC-AC-BLC-011-HP-001` | `CFR-125`,`CFR-126` | Exact current Codex deltas and requirements lifecycle | Scratch and 19-test UX contract pass |
| `SC-AC-BLC-011-NP-001` | `CFR-125`,`CFR-126` | Delta row, occurrence, fingerprint, or requirements record mutates | Both validators fail closed |
| `SC-AC-BLC-012-HP-001` | `CFR-127` | Exact retained 270 projection drives old replay and the entry-normalized 271 projection is checked after authorized edits | Accepted Sequence 15–19 geometry and the `0509...` entry receipt pass |
| `SC-AC-BLC-012-NP-001` | `CFR-127` | Stored projection, protected live record, path set, mode, or policy mutates | Validation fails before removed-path reads or historical fallback |
| `SC-AC-BLC-012-BP-001` | `CFR-127` | Current 271 projection reaches old live authority | Rejected; no historical constant is updated |
| `SC-AC-BLC-001-HP-002` | `CFR-123A` | Full amended closure runs | Exact `169/176`, seven target IDs, UX contract `19/19` |

## Verification

Run from repository root:

```bash
.venv/bin/python -B -m py_compile \
  scripts/ui_ux_inventory.py \
  scripts/ui_ux_theme_handoff.py \
  scripts/test_ui_ux_theme_handoff.py \
  scripts/test_ui_ux_contract.py

.venv/bin/python -B scripts/test_ui_ux_contract.py
.venv/bin/python -B scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -B scripts/test_artifact_loader.py
.venv/bin/python -B scripts/test_api.py
.venv/bin/python -B scripts/test_codex_auth_flow.py
.venv/bin/python -B scripts/test_llm_client_codex.py
.venv/bin/python -B scripts/test_dashboard_navigation.py
```

Mechanically assert:

- coordinator denominator 176, passed 169, controlled 0, unexpected 7;
- unexpected IDs exactly
  `{200,202,203,206,207,208,209}`;
- UX contract `19/19`;
- artifact loader `14/14`;
- API `44/44`;
- no workspace-guard line;
- no change outside the four implementation files plus authorized review
  journals;
- raw current projection remains 271, its path-set delta remains exact, its
  four-record entry-normalized digest is `0509...`, and historical projection
  remains 270;
- old Sequence 15–19 retained-leaf and descriptor constants remain byte
  unchanged.

Skipped or cardinality-short checks are not passes.

## Risk Controls

- Never use broad mocking of `_source_file_record`, path access, or projection
  builders; fixtures must intercept only the explicit historical seam.
- A history importer must authenticate a retained artifact before returning
  stored records.
- An entry-receipt validator must never fall back to history after protected
  current drift.
- Do not make old Sequence 15–19 authority accept 271 records.
- Do not rewrite the selector-delta contract, classification JSON, rollback
  manifest, capture stack, or authorization documents.
- Do not weaken exact site-ID, occurrence, fingerprint, mode, ordering,
  stable-reopen, or canonical-byte checks.
- Every patch fixture restores state in `finally` or a context manager and has
  a restoration assertion.
- Implementation rollback is limited to restoring the exact Phase A0 records
  of the four authorized implementation files. Review documents and journals
  remain as the audit trail; protected files and formal artifacts are never
  rollback targets.
- If any additional non-target failure appears, stop and amend again. Do not
  grow the file allowlist during implementation.

## Review Checklist

Judge must verify:

- the `33 + 10 + 7 = 50` coordinator partition and external four-test gate;
- the entry records and migration deltas are reproducible;
- each sequence-specific historical 270 receipt, the amendment-entry 271
  receipt, and the raw post-implementation projection are not conflated;
- no accepted descriptor or retained-leaf constant is globally rebased;
- the four-file scope is sufficient and does not authorize live UI edits;
- mutation and no-read tests cover each new lifecycle seam;
- the base-ledger duplicate `IMPL-185` is removed in the superseding ledger;
- the final seven-only gate and Sequence 20 pause remain explicit.

Any unresolved likely runtime error, unchecked history fixture, protected-file
write, global geometry rebase, or unverifiable exact gate is blocking.

## Review Result

Review iteration 1: `REQUEST_CHANGES`.

- Resolved the self-invalidating raw post-implementation digest requirement by
  defining an exact four-record entry-receipt substitution model.
- Restored inherited `AC-BLC-004` and `AC-BLC-008` traceability.
- Replaced the unverifiable operation digest with a complete canonical-byte
  grammar and independently reproducible digest.

Review iteration 2: `APPROVE`.

Codex independently confirmed that all three iteration-1 findings are resolved
and reported no new blocker, high, or medium finding. The review was read-only:
no formal-state, bootstrap, publication, capture, comparison, test, or mutating
workflow was run.

## Handoff

If and only if review is approved, freeze this amendment and ledger and return
their exact SHA-256, byte size, and mode to the maintainer. Implementation may
resume only after a separate exact-byte acceptance. No authorization candidate
or formal lifecycle command is part of this handoff.
