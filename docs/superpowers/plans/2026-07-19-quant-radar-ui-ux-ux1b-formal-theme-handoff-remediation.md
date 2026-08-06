# UX-1B Formal Theme Handoff Remediation Plan

## Document info

| Field | Value |
| --- | --- |
| Type | Implementation checklist / technical contract amendment |
| Version | `v0.3-draft` |
| Status | Draft — implementation blocked until independent review passes |
| Author | Scribe, informed by Atlas architecture review |
| Reviewers | Builder, Judge, evidence-scope reviewer |
| Audience | Quant Radar maintainers and implementation agents |
| Recovery ID | `20260719T211915Z` — first-attempt-only Task 9 eligibility |

## Outcome

Create one fail-closed bridge from the formal recovery evidence schema to the
remaining parent UX-1B theme stages. The bridge consumes the canonical formal
  pre-theme manifest, authorizes the four runtime files plus their mandatory
  forward-classification ledger, authenticates
the theme-state gallery, and compares the later formal post-theme manifest.

The bridge must not modify the frozen nine-member capture stack. Recovery ID
`20260719T211915Z` remains usable only while its first Task 9 attempt has not
created either after-namespace.

## Blocking defect

The accepted recovery Task 9 cannot safely hand off today:

1. `load_authenticated_pretheme_manifest()` accepts only a direct legacy
   `.claude/ui_snapshots/ux1b/pretheme-*/manifest.json` and rejects the formal
   recovery path and schema.
2. `run_matrix()` returns through `_run_ux1b_recovery()` for a formal UX-1B
   profile before the legacy loader is reached. A formal post-theme run ignores
   `--theme-contract` and performs no pre/post comparison.
3. Copying, linking, renaming, or coercing the formal manifest into the legacy
   namespace would weaken evidence identity and would not repair the formal
   post-theme bypass.

Task 7 selector code and evidence are closed. Task 9 has not started. Three
independent reviews agreed that an external formal verifier is the least-risk
repair, but rejected v0.1's publication order, raw-sidecar equality, mutable
root-contract implication, and unverifiable human-review step.

## Authority and precedence

For the formal theme handoff only, authority is highest to lowest:

1. the recovery evidence document's `AUTHORIZED` entry naming this accepted
   amendment by exact workspace-relative path and SHA-256;
2. those exact accepted amendment bytes;
3. the accepted recovery plan and its accepted execution amendments;
4. the accepted parent UX-1B plan.

This amendment supersedes only:

- recovery Task 9's legacy theme-contract schema and publication mechanism;
- parent Task 2's legacy pre-theme handoff mechanism;
- parent Tasks 4 and 5 instructions to update the initial theme contract in
  place; and
- any interpretation that a terminal formal capture manifest alone closes a
  parent theme task.

Everything else remains governed by the accepted recovery and parent plans.
In particular, fail-soft JSON loading, routes, providers, mutators, selection
semantics, Option A palette, protected UX-0/UX-1A behavior, and rollback rules
remain active.

The upstream authority set is exact:

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

This draft cannot authenticate its own bytes. After review passes, change only
its version/status to `v0.3-accepted` / `ACCEPTED EXECUTION AMENDMENT`, record
the final review table in this file, and compute the final SHA-256. Before any
implementation file changes, append exactly one authorization stanza to
`docs/ui-ux/quant-radar-ui-v2-ux1b-recovery.md`:

```text
<!-- UX1B_FORMAL_HANDOFF_AUTHORIZATION_V1
<one canonical JSON object>
UX1B_FORMAL_HANDOFF_AUTHORIZATION_V1 -->
```

The canonical object has exactly
`schemaVersion`, `sequence`, `status`, `amendment`, `precedence`, and
`authorizedRecoveryId`; requires schema
`quant-radar-ui-ux-formal-handoff-authorization/v1`, integer `sequence: 1`,
`status: "AUTHORIZED"`, the exact amendment `{path,sha256,size}`, the ordered
four-level precedence above, and recovery ID `20260719T211915Z`. Canonical
bytes use the JSON rule below. Preflight records
`authorizationRecordSha256 = SHA256(canonical-object-bytes)` and requires
exactly one matching stanza. It never hashes the mutable surrounding Markdown.

The later proposed-root note is a separate `PENDING_PUBLICATION` stanza. It is
non-authoritative, excluded from source/root digests, and may appear only after
the candidate exists. Its presence does not change the first authorization
record. Any amendment-byte or authorization-record change revokes execution
authority and requires another reviewed plan.

## Requirements

- `REQ-001`: A formal canonical pre-theme bundle is referenceable by one
  immutable, workspace-relative root handoff contract.
- `REQ-002`: Parent Task 3 cannot edit production until a fresh pristine
  root-keyed authorization binds exact pre/post images for the four runtime
  files and classification ledger plus all unchanged source files.
- `REQ-003`: Parent Task 4 closes only through authenticated 3/3 theme-state
  capture, all 15 referenced artifacts, and an external manual review.
- `REQ-004`: Parent Task 5 closes only through authenticated 81/81 post-theme
  capture, machine comparison, external manual review, and an immutable final
  closure artifact.
- `CFR-001`: Every manifest, PNG, sidecar, supplemental artifact, report,
  source, review, and contract used for a decision is descriptor-authenticated
  with no symlink, hardlink, unsafe mode, wrong owner, inode, size, hash, path,
  or namespace drift.
- `CFR-002`: The nine frozen stack members, capture-stack contract SHA
  `8b354ec6d7f84e4bfbd96c098ffd1dae2db0d90f7f9cf86d168bc8a9298df820`,
  base digest
  `6c1f08266d479d3e3e3e77f35dc06b6b5cd81c5160c9a1df91ed0e7b7dcdbfe7`,
  and aggregate digest
  `69eeec0dcdffdab16d5696896cb4fc5ddb27071591953d04b4c907ea5b78055e`
  remain exact. Drift revokes this plan and requires stack rotation plus a new
  Task 6 baseline.
- `CFR-003`: All fallible prerequisites and external-input reauthentication
  occur before a public success leaf is linked. A prerequisite or staging
  failure leaves that leaf absent; a collision leaves the existing leaf exact.
- `CFR-004`: Source authority uses one duplicate-free canonical mirror map.
  Verifier and verifier tests occur once through `scripts/**/*.py`; supplemental
  records are disjoint and limited to the declared non-mirror authorities.
- `CFR-005`: Parent theme work may change exactly four production/runtime
  files—`.streamlit/config.toml`, `app.py`, `ui/_design.py`, and
  `requirements.txt`—plus the required pending-to-accepted evidence transition
  in `docs/ui-ux/quant-radar-ui-v2-ux1b-classification.json`. No fifth
  production path, sixth total path, addition, or deletion is permitted.
- `CFR-006`: The initial root contract is never updated or deleted. Revocation,
  supersession, theme-state attestation, and final closure are new immutable
  artifacts that reference it.

## Scope

### Create during this remediation

- `scripts/ui_ux_theme_handoff.py`
- `scripts/test_ui_ux_theme_handoff.py`
- `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-prechange.json`
- `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-handoff-rollback.json`
- owned rollback bundle below
  `.claude/ui_snapshots/ux1b/recovery/theme-handoff-prechange-20260720T000000Z/`
- preflight
  `.claude/ui_snapshots/ux1b/recovery/theme-handoff-preflight-20260719T211915Z.json`
- root `docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json`

### Create during Task 9 and parent Tasks 3–5

- existing formal Task 9 after-namespaces and migration report;
- immutable migration-review copy
  `.claude/ui_snapshots/ux1b/recovery/control-migration-manual-review-20260719T211915Z.json`;
- non-authoritative staged candidate
  `.claude/ui_snapshots/ux1b/recovery/theme-handoff-candidate-20260719T211915Z.json`;
- `.claude/ui_snapshots/ux1b/theme-batch-authorization-<root-contract-sha>.json`;
- `.claude/ui_snapshots/ux1b/theme-batch-staging-<root-contract-sha>/`;
- `.claude/ui_snapshots/ux1b/theme-batch-candidate-<root-contract-sha>.json`;
- `.claude/ui_snapshots/ux1b/theme-batch-review-<root-contract-sha>.json`;
- `.claude/ui_snapshots/ux1b/theme-state-candidate-<theme-run-id>.json`;
- `.claude/ui_snapshots/ux1b/theme-state-manual-review-<theme-run-id>.json`;
- `.claude/ui_snapshots/ux1b/theme-state-attestation-<theme-run-id>.json`;
- `.claude/ui_snapshots/ux1b/posttheme-comparison-candidate-<theme-run-id>.json`;
- `.claude/ui_snapshots/ux1b/theme-delta-manual-review-<theme-run-id>.json`;
- `.claude/ui_snapshots/ux1b/theme-closure-<theme-run-id>.json`.

### Modify during remediation

- `Makefile`
- `docs/ui-ux/quant-radar-ui-v2-ux1b-recovery.md`
- `.agents/scribe.md`, `.agents/atlas.md`, `.agents/PROJECT.md`

### Modify later only inside the authorized parent theme batch

- `.streamlit/config.toml`
- `app.py`
- `ui/_design.py`
- `requirements.txt`
- `docs/ui-ux/quant-radar-ui-v2-ux1b-classification.json` — evidence ledger,
  not a fifth production/runtime file

### Must remain byte-identical

- all nine members of the capture-stack contract and that contract itself;
- both canonical Task 6 manifests and all 234 referenced artifacts;
- all nine migrated selector production postimages;
- every production/runtime file until parent Task 3 receives authorization;
- every non-allowlisted source through final theme closure.

### Non-goals

- no route, provider, API, loader, mutator, session, or fail-soft behavior
  change;
- no edit to the unreachable legacy loader or any frozen stack member;
- no legacy-manifest conversion or evidence alias;
- no mutable in-place root-contract update;
- no Safari/WebKit or participant-usability claim.

## Architecture decision

Use an independent formal verifier rather than editing a frozen capture-stack
member.

| Option | Benefit | Cost / risk | Decision |
| --- | --- | --- | --- |
| Modify formal runner/evidence | Integrated capture and compare | Invalidates the stack and recovery ID; requires replacement Task 6 | Rejected for this bounded defect |
| External descriptor verifier | Preserves authenticated capture bytes and makes later closure explicit | Adds a coordinator whose bytes and Make wiring must be frozen | Selected |

The verifier is not a capture-stack member. It is present before canonical
pre-theme capture, therefore it and its tests occur once in the formal source
mirror. Its own recorded SHA is only a drift detector; the external trust
anchor is the accepted amendment SHA recorded by recovery authority.

## Immutable artifact lifecycle

| Artifact | Producer | Required status | Authority granted |
| --- | --- | --- | --- |
| `theme-handoff-preflight-*` | verifier, before Task 9 | `passed` | permits the one Task 9 attempt only |
| `control-migration-*` | existing formal comparator | `passed` | machine migration candidate only |
| `control-migration-manual-review-*` | exact-copy publisher from human-authored intake | `accepted` | proves external review of all 117 pairs |
| `theme-handoff-candidate-*` | verifier | `candidate` | none; contains exact proposed root bytes/SHA |
| root theme contract | verifier | `passed` | permits pristine Task 3 authorization |
| `theme-batch-candidate-*` | verifier from reviewed scratch bytes | `candidate` | none; binds exact five-file pre/post images |
| `theme-batch-authorization-<root-sha>` | verifier immediately before edit | `passed` | global one-shot claim permitting one four-runtime-plus-ledger CAS batch |
| `theme-state-candidate-*` | verifier after capture | `review_required` | none |
| `theme-state-manual-review-*` | exact-copy publisher from human-authored intake | `accepted` | external review input |
| `theme-state-attestation-*` | verifier | `passed` | closes parent Task 4 |
| `posttheme-comparison-candidate-*` | verifier | `review_required` | none |
| `theme-delta-manual-review-*` | exact-copy publisher from human-authored intake | `accepted` | external review input |
| `theme-closure-*` | verifier | `passed` | alone closes parent Task 5 |

A formal `manifest.json` with `status: "passed"`, including one created while
the formal runner ignores `--theme-contract`, never grants theme authorization
or closure by itself.

## Root handoff contract

Schema `quant-radar-ui-ux-formal-theme-handoff/v1` contains exactly:

- `status: "passed"`, recovery ID, accepted amendment path/SHA, and exact
  upstream authority path/SHA records;
- existing recovery prechange, rollback, archive, bundle manifest, selector
  delta, parent prechange, pending classification, parent rollback-source
  manifest plus its owner marker and four backup leaves, capture-stack
  contract, base digest, aggregate digest, and all nine member records;
- preflight path/SHA;
- all four Task 9 manifest path/SHA/mode/phase/count records and exact namespace
  leaf counts `163 / 73 / 163 / 73`;
- all `468` referenced PNG/sidecar records, with no unreferenced extra leaf;
- migration report and external migration-review path/SHA;
- one canonical formal source map and aggregate digest;
- disjoint supplemental records for `requirements.txt`, `Makefile`, accepted
  amendment, and upstream authority files;
- exact runtime identities, four runtime-file preimages, and the pending
  classification preimage;
- the exact four production/runtime paths plus one evidence-ledger transition.

The canonical Task 6 anchors are:

- page manifest SHA
  `a72aa7cac95bfbd70b23a2033c49a0d03aa500204bd66ec738b757c2295e6404`,
  81 captures, 162 artifacts, 163 namespace leaves;
- control manifest SHA
  `06f7320b0d56e54d584399e281a307a713b23a349207ac7b35b6bd1ee14154be`,
  36 captures, 72 artifacts, 73 namespace leaves;
- source digest
  `4eeb3629fbd83ef9e61f553cd3eae93e7b8ede4b925e45774ece99847dfce8a5`.

The authenticated parent rollback-source manifest freezes the original theme
batch preimages: `.streamlit/config.toml`
`102d584059084f741addab857c98fc7fda92799fd8fc1aa112d93830c72c6dbf`,
`app.py`
`1f0d8ec142aee605e51e126add8f867df06c81eb900475204630812acd019f85`,
`ui/_design.py`
`0844c44dfc0b254f541ce7b9188cb71856e8549bcaaffea44db220c44a3be92d`,
and `requirements.txt`
`123fd3ee1559a93cf1e30efcf327dd93f6e8604cfa1a6a13487d6de6f3da7d16`.
Task 0 must prove the live bytes still match; this plan does not silently
adopt later drift as a new theme preimage.

The classification preimage is
`c6c27801ffbd7aeffd86514156ba2e4c81f0699b78e6db7278dfdf72d3d6a77b`
with `state: "pending"`. Its later exact `state: "accepted"` postimage is
prepared, reviewed, and bound with the four runtime postimages before any live
theme write.

The root contract never references superseded or nonterminal evidence and is
never a rollback deletion target.

## Source and runtime contract

The canonical source map is a sorted unique mapping
`path -> {sha256, size, mode}` rebuilt from retained descriptors using the
existing formal mirror policy:

- `.streamlit/config.toml`, `app.py`, `api/**/*.py`, `scripts/**/*.py`,
  `ui/**/*.py`, and `docs/ui-ux/quant-radar-ui-v2-baseline.json`;
- exact existing exclusions remain active;
- aggregate encoding and file modes are the existing source-mirror schema's
  canonical rules, not a second invented digest algorithm;
- the postcontrol/pretheme map rebuilt after Task 9 must equal those two
  manifests' `sourceDigestStart` and `sourceDigestEnd` and the preflight map;
- each Task 6 precontrol bundle retains and authenticates its own older closed
  source digest; it is related to the after-bundles only through the accepted
  selector delta, exact allowed tooling additions, and migration comparator,
  never falsely asserted to equal the new map;
- verifier and verifier test appear only in this map; overlap with supplemental
  records is rejected.

Supplemental records are the exact disjoint non-mirror authorities named in
the root-contract section. Before/post source projections have the same path
set. Post-theme may differ only at `.streamlit/config.toml`, `app.py`, and
`ui/_design.py` inside the mirror, and at `requirements.txt` plus the required
pending-to-accepted classification record outside it. Every other record is
exact, no fifth production or sixth total path differs, and each formal mirror
aggregate equals its own manifest digest.

Task 6 did not retain a full historical source map. To validate its closed
digest without invention, start from the descriptor-built preflight map,
remove exactly the two then-absent paths `scripts/ui_ux_theme_handoff.py` and
`scripts/test_ui_ux_theme_handoff.py`, and replace exactly the nine current
migrated selector records with legacy SHA/size from the selector delta and
their mirror mode (`"0555"` iff the authenticated recovery-prechange source
mode is executable, otherwise `"0444"`). No other record may change. Re-encode
with the existing source-mirror algorithm and require exact digest
`4eeb3629fbd83ef9e61f553cd3eae93e7b8ede4b925e45774ece99847dfce8a5`.

Runtime identity is exact before and after:

- CPython `3.11.15`;
- Streamlit `1.57.0`;
- Playwright `1.60.0`;
- Chromium `148.0.7778.96` / cache revision `1223`;
- macOS `26.5` build `25F71`, Darwin kernel `25.5.0`, platform
  `macOS-26.5-arm64-arm-64bit`.

The formal manifest does not itself contain these versions. Every lifecycle
artifact therefore embeds the exact `runtimeReceipt` object defined below; no
extra receipt leaf is published. The verifier derives Python/package versions from the
running interpreter and installed metadata; binds resolved Python and Chromium
executable path/SHA/size/mode; takes Chromium version from the owned calibrated
Playwright browser rather than inferring it from a path; records the resolved
temporary-root parent used by the Analytics projection; and derives Darwin
identity from the live platform. Every receipt must be exact. Python 3.10 is
only an AST syntax gate, not a runtime claim.

## Descriptor and publication boundary

Every verifier command takes an exclusive advisory lock on the one fixed,
owner-only `.claude/ui_snapshots/ux1b/.formal-theme-handoff.lock`, opens the
workspace once as an owner-controlled directory descriptor, and normalizes
only bounded workspace-relative components. All cooperating commands use this
lock. A non-cooperating process with the same Unix owner is explicitly outside
this filesystem protocol's threat model; covering it would require a different
UID or external transaction service.

Before opening evidence leaves, the command computes
`requiredFd = uniqueRetainedLeaves + 2 * maxPathDepth + 64`, requires
`requiredFd <= 1536`, reads `RLIMIT_NOFILE`, and raises only its own soft limit
to at least `requiredFd` when the hard limit permits. Failure occurs before any
temporary/public output. It retains every decision-bearing leaf FD through the
commit, while intermediate directory FDs are bounded and closed. A fresh child
inherits only the exact workspace and staged-candidate FDs through
`close_fds=True` plus an exact `pass_fds` tuple; capture children inherit none.
The original soft limit is restored after all retained FDs close.

It rejects symlinks, hardlinks, non-regular leaves, unsafe components/modes,
wrong owner, changed device/inode/link count, hash/size drift, traversal,
duplicates, unexpected keys, unreferenced leaves, and every rename race
observable within the cooperating lock boundary.

Success publication uses Darwin `renameatx_np(..., RENAME_EXCL)`:

1. create `.tmp.<kind>.<32-lowercase-hex>` in the retained destination parent
   with `O_CREAT|O_EXCL`, mode `0600`, at most eight random-name attempts;
2. write already-canonical bytes once, fsync, rehash, and retain the stage FD;
3. finish every prerequisite and input reauthentication;
4. for the root only, pass that same stage FD to a fresh verifier child. The
   child reads the FD, validates the proposed root and its inputs, and returns
   canonical `{device,inode,sha256,size}`. The parent matches that receipt to
   `fstat(stageFd)` and never re-encodes the root;
5. immediately before rename, require the staged name's `lstat` and retained
   FD to have the same device/inode/owner/mode/size/hash/`nlink=1`;
6. atomically rename that staged name to the absent fixed public leaf with
   `RENAME_EXCL`. This syscall is the sole commit linearization point; it moves
   the same inode and never exposes an `nlink=2` interval.

After commit, the publisher attempts parent fsync and checks that public-name
`lstat` plus a public reopen match the still-retained stage FD's device/inode
and exact bytes. Those checks confirm the response but do not undo the atomic
commit; failure takes the reconciliation path below.

There is no permanently ambiguous `publication_uncertain` state. Before the
rename commits, failure leaves the public leaf absent and only an unreferenced
private temp may remain. On `EEXIST`, the existing leaf is never modified. If
the publisher loses its response or parent-directory fsync/reopen fails after
the atomic commit, it reports `committed_reconciliation_required`; it does not
republish. A fresh kind-specific verifier reopens the public name, requires the
exact candidate bytes and all bound inputs, fsyncs the retained parent, and may
return `reconciled`. Thus a complete exact committed leaf is safely adoptable;
an absent or non-exact leaf is rejected. Consumers always perform this same
verification, so no hidden process-history bit is required.

Crash-left temp leaves never grant authority and are neither reused nor
silently deleted. An existing exact public leaf makes publication idempotently
enter reconciliation; an invalid collision revokes that lineage. The verifier
never deletes an initial root contract. Revocation/supersession is a separate
immutable no-replace artifact under a reviewed later amendment.

## Sidecar and screenshot comparison

Raw sidecars are not byte-comparable across formal runs. Each sidecar and its
bundle is first fully descriptor-authenticated and validated by the existing
evidence schema. The external verifier then starts from the existing canonical
projection, which already omits `capturedAt`, `runId`, and `browserNodeId`, and
normalizes only these two additional authenticated volatilities:

1. `counterProvenance.counterDocumentSha256` is removed from pair equality
   only after requiring one valid value shared by all 81 sidecars within each
   bundle and validating schema
   `quant-radar-ui-ux-counter-enrichment/v1`, capture ID, frozen registry key,
   exact sidecar/manifest expected-and-actual provider aggregates, and zero
   mutators independently. Both original bundle hashes remain in the machine
   comparison report.
2. A fixture-owned path substitution is permitted only in
   `analytics-db/{desktop,tablet,mobile}`, whose identity is exactly route
   `/analytics-db` and callable `analytics_db.render`. Each viewport must have
   exactly one matching node, and the whole 81-row matrix exactly three. That
   node is exactly ID `dom-24284ea9380c1018121368f7`, `role=generic`,
   `flowScope=main`, null `parentId`/`boundaryId`/`rootSelector`, `visible=true`,
   `state={"tabIndex": -1}`, and `name == text`. Its complete value must be a
   normalized absolute POSIX path matching the runtime receipt's temporary-root
   parent plus
   `quant-radar-ux1b-<exactly 32 lowercase hex>/app/fixture-root/reports/analytics_checks/latest.json`.
   Only that complete value becomes
   `$OWNED_APP_ROOT/fixture-root/reports/analytics_checks/latest.json`.
   Any `..`, relative path, wrong suffix/case/token length, near-prefix,
   name/text mismatch, fourth occurrence, occurrence in another field/node, or
   other `quant-radar-ux1b-` text fails.

Everything else remains exact: identity, route, callable, viewport, readiness,
node order/IDs/tree/text after that narrow substitution, semantics/state,
visibility, integer geometry, stable state, provider/mutator counters,
diagnostics, overflow, and known-debt classification. `runtimeProjection`
remains exactly `{"sourceRoot": "$OWNED_ROOT_0", "browserScratchRoot":
"$OWNED_ROOT_1"}` and receives no additional normalization.

The positive normalization regression uses the passed legacy-state page
baselines `20260719T114511Z` and `20260719T211915Z`. It must normalize all
81/81 sidecars: all 81 counter-document hashes differ and only the three
Analytics viewports contain six owned-root string occurrences. This replay
does not waive their different stack/source identities; those identities are
tested separately and still fail a handoff comparison. The test also proves
71/81 PNGs are byte-identical and therefore allowed.

Historical manifests predate `runtimeReceipt`. The replay test therefore uses
a test-only authenticated receipt fixture whose temp-root parent is the exact
common parent parsed from those retained Analytics paths and whose other
runtime fields are the frozen recovery identities. Production code may not
synthesize this fixture or use historical replay as top-level handoff success.

Every PNG pair must have exact dimensions. Byte-identical PNGs are recorded as
`unchanged_by_hash`. Only changed PNGs require an accepted visual explanation.

## External manual-review contract

The verifier must never invent a reviewer, verdict, timestamp, or explanation.
This artifact is an authenticated external assertion, not technical proof that
its author is human. Execution pauses at an explicit operator checkpoint; the
operator authors canonical JSON below the source-mirror-excluded fixed intake
root `.claude/ui_snapshots/ux1b/review-intake/`. The verifier validates the
retained intake FD and copies those same raw bytes to staging; it does not
rewrite or complete them. Intake and destination must be distinct one-link
regular inodes, and aliases, symlinks, hardlinks, or paths outside that root
fail.

Schema `quant-radar-ui-ux-manual-visual-review/v1` uses exact keys:

- `schemaVersion`, `kind`, `status: "accepted"`, `reviewedAt` as bounded UTC
  RFC3339 seconds, and `reviewer: {"type": "human", "id": <nonempty bounded>}`;
- `operatorCheckpoint: {"decision": "accepted", "promptSha256": <sha256>}`
  binding the exact review prompt/contact-sheet identity;
- exact sorted input `ArtifactRef` records, including the relevant machine report,
  manifests, and root contract when one exists;
- `itemSetSha256` over the exact sorted expected identity set;
- exact sorted `items`, with no duplicate or missing ID;
- every item has identity, artifact path/SHA, dimensions, `changed`, `verdict`,
  and a bounded explanation; pair reviews contain before/after PNG records.

Kind-specific sets are exact:

- `control-migration`: all 117 page/control pairs. Identical items use
  `unchanged_by_hash`; every changed item uses `accepted` and an explanation.
- `theme-states`: 3 main screenshots plus 9 supplemental crops, 12 visual
  items total, each with an `accepted` verdict.
- `posttheme`: all 81 pairs. Identical items use `unchanged_by_hash`; every
  changed item uses `accepted` and an explanation.

Absolute paths, unknown keys, unbounded notes, wrong kind, forged/missing
inputs, dimensions/hash drift, and set mismatch fail before immutable copy
publication.

## Parent Task 3–5 consumption

### Task 3 authorization and five-record logical CAS

Before authorization, `prepare-theme-batch` materializes the four proposed
runtime files and accepted classification ledger below the fixed staging root.
It requires exact root preimages, generates an exact unified patch digest and
five `{path,preimage,postimage}` records, runs the parent token/static/version/
forward-ledger tests against a scratch projection, and publishes a machine
candidate. Independent staged-diff review is recorded in the fixed
`theme-batch-review-<root-sha>.json`; neither artifact authorizes live writes.

`authorize-theme-batch` runs immediately before any production edit and is
equivalent to `verify-handoff --require-pristine`. It consumes the exact staged
candidate/review, binds every expected-old and intended-new SHA/size/mode,
selector/stack/runtime identity, and all unchanged source records. All theme
run IDs compete for the single fixed no-replace
`theme-batch-authorization-<root-contract-sha>.json`; the winner's receipt
binds exactly one explicit theme run ID. A failed/abandoned winner requires a
reviewed supersession and cannot choose a second ID.

Immediately before one five-record patch, recompare all live preimages with
that receipt. Apply the four runtime hunks plus the pending-to-accepted ledger
transition in one maintenance window, then require all five bound postimages,
no fifth production path, and no sixth total path. This is an expected-old-SHA
logical CAS, not a cross-file filesystem transaction. A partial batch publishes
no success record. Restore a member only if its live bytes equal that member's
exact bound postimage; never overwrite newer user work.

### Task 4 theme-state closure

The formal theme matrix must pass 3/3. Its manifest and namespace are
authenticated as 3 main PNGs, 3 render sidecars, and 9 supplemental crops:
15 referenced artifacts plus one manifest and no extra leaf. Machine
verification publishes `theme-state-candidate-*` with `review_required`.
After external review of 12 visuals, `close-theme-states` authenticates the root
contract, batch authorization, candidate, exact review copy, postimage source
projection, runtime, and 3/3 bundle, then publishes
`theme-state-attestation-*`. Only that attestation closes parent Task 4.

### Task 5 post-theme closure

The formal page matrix must pass 81/81 and its 162 artifacts must authenticate.
`compare-posttheme` consumes the root contract, batch authorization, theme-state
attestation, canonical pre-theme bundle, and post-theme bundle; rebuilds both
source projections; applies only the four-runtime-plus-ledger allowlist and narrow sidecar
normalization; checks every dimension; and publishes
`posttheme-comparison-candidate-*` with `review_required`.

After external review of all 81 pairs, `finalize-theme` authenticates the root,
authorization, state attestation, machine candidate, exact review copy,
post-theme manifest/artifacts/source/runtime, and publishes
`theme-closure-*`. This immutable closure alone closes parent Task 5. The root
contract remains unchanged.

## First-attempt-only Task 9 rule

Recovery ID `20260719T211915Z` remains usable only if the first capture begins
with both after-namespaces, migration report, immutable review destination,
handoff candidate, and root contract absent, and that one invocation completes
both postcontrol and canonical-pretheme outputs successfully.

The same-ID state machine is exact:

1. `eligible`: both after-namespaces and every downstream output are absent;
2. `capture_started`: the guarded Make invocation has begun; that invocation
   is never rerun;
3. `capture_complete`: both after-manifests are terminal `passed`, descriptor-
   authenticated, and tied to the preflight source/stack/runtime;
4. `migration_complete` -> `review_asserted` -> `candidate_prepared` ->
   `root_committed_or_reconciled`: downstream verification/publication may
   advance linearly under the same ID, but capture never resumes;
5. `revoked`: either capture is partial/nonterminal/failed, source/verifier
   drift occurs after preflight, migration semantically fails, the operator
   rejects a visual, or a public collision is invalid.

A malformed review intake may be corrected only while its immutable review
destination remains absent; that is not a capture retry. A committed exact root
whose publisher lost its response may be reconciled as defined above; that is
not a second publication. Every other `revoked` state preserves all evidence,
leaves parent theme work unauthorized, and requires a separately reviewed
cross-ID lineage amendment with a new Task 6 baseline. This plan never deletes
an after-namespace, rotates the stack, or invents an attempt namespace.

## Dirty-worktree and rollback contract

Live authenticated bytes, never Git `HEAD`, are the expected-old authority.
The deterministic freeze ID is `20260720T000000Z`; every path below must be
absent before bootstrap. Creation order is exact:

1. publish the prechange JSON with
   `selfHash: "omitted-by-contract"`; it records itself, rollback JSON, owner
   marker, archive, and bundle manifest as `exists: false` and every other
   planned-created path as absent;
2. create the private bundle directory and its three and only three leaves:
   `.quant-radar-theme-handoff-owner`, `prechange-files.tar`, and
   `bundle-manifest.json`; the manifest uses
   `selfHash: "omitted-by-contract"`, binds the owner/archive bytes, and is
   reopened after the complete three-leaf set is fsynced;
3. publish rollback JSON with `selfHash: "omitted-by-contract"`, binding the
   already-published prechange SHA, bundle leaf hashes, create/delete rules,
   and exact existing-file hunk boundaries;
4. preflight externally binds and reopens the prechange and rollback hashes;
   neither file is ever rewritten to self-reference.

The prechange record and owned rollback bundle:

- records `exists: false` for every planned-created path;
- records path/SHA/size/mode/owner for every existing file in scope;
- archives exact prechange bytes for verifier-adjacent tooling/docs;
- records exact context anchors and append-only boundaries for dirty
  `Makefile`, recovery docs, and agent journals;
- binds the complete upstream authority set and prior authenticated rollback
  bundle;
- records the dirty porcelain digest only as diagnostic evidence.

The fixed bundle path is
`.claude/ui_snapshots/ux1b/recovery/theme-handoff-prechange-20260720T000000Z/`.
Any collision, extra leaf, wrong owner/mode/link count, or bootstrap failure
stops before implementation; no existing leaf is adopted or overwritten.

Immediately before every write, CAS-check its whole-file preimage or exact
owned hunk/append boundary. A mismatch not produced by this plan stops before
that write. Rollback deletes a planned-created file only when its live path,
owner, mode, `nlink`, size, and posthash match. It reverses an existing-file
hunk only when the live hunk equals the exact plan-produced postimage and its
surrounding anchors remain exact. No reset, checkout, whole dirty-file restore,
or root-contract deletion is authorized.

## Canonical schemas

All new JSON evidence is one UTF-8 object with no BOM or trailing newline,
encoded by `json.dumps(value, sort_keys=True, separators=(",", ":"),
ensure_ascii=False, allow_nan=False)`. New schemas allow no floating values,
duplicate keys, unknown keys, or non-NFC strings. SHA-256 is 64 lowercase hex;
paths are NFC workspace-relative POSIX paths of 1–512 bytes with no empty,
`.` or `..` component; IDs match `[0-9]{8}T[0-9]{6}Z`; strings are at most
512 bytes unless a smaller limit is stated. Machine artifacts are at most
16 MiB and review artifacts 8 MiB.

Shared exact objects are:

- `FileRecord`: `{path,sha256,size,mode,uid,gid,device,inode,nlink}` with
  nonnegative integers, regular file, owner equal to executor, safe mode, and
  `nlink: 1`;
- `ExternalFileRecord`: `{absolutePath,sha256,size,mode,uid,gid,device,inode,
  nlink}` where the normalized absolute path is below the frozen runtime
  allowlist and the leaf has the same safety invariants;
- `SourceRecord`: `{path,sha256,size,mode}` with mode exactly string `"0444"`
  or `"0555"`, matching the existing mirror schema;
- `ArtifactRef`: `{path,sha256,size}`;
- `BundleRecord`: `{manifest,mode,phase,expectedCaptureCount,capturedCount,
  artifactCount,namespaceLeafCount,captureIdsSha256,sourceDigest,
  captureStackDigest}`; `manifest` is `FileRecord` and all counts are exact;
- `SourceProjection`: `{schemaVersion,policy,records,digest}` where policy is
  the exact existing include/exclude arrays, records are unique path-sorted
  `SourceRecord`s, and digest uses the existing mirror algorithm;
- `RuntimeReceipt`: exactly `{schemaVersion,python,streamlit,playwright,
  chromium,platform,tempRootParent,sha256}`. Python and Chromium each contain
  exact version plus resolved executable `ExternalFileRecord`; Chromium also has revision;
  platform is `{macosVersion,build,darwinKernel,machine,identity}`; `sha256`
  hashes the other canonical fields.

Every collection is path/ID sorted before hashing. `itemSetSha256` is SHA-256
of canonical UTF-8 bytes for the sorted JSON array of item IDs. A pair review
item has exactly `{id,before,after,dimensions,changed,verdict,explanation}`;
a theme-state item has `{id,artifact,dimensions,changed,verdict,explanation}`.
Artifact fields are `ArtifactRef`, dimensions are positive integer
`{width,height}`, explanation is 0–512 bytes, and verdict is
`unchanged_by_hash` only when hashes match or `accepted` only when the operator
reviewed the visual.

The immutable schemas have these exact top-level keys; their named nested
values use only the shared objects above or exact-key objects asserted by the
verifier tests:

| Schema / artifact | Exact top-level keys | Status |
| --- | --- | --- |
| `quant-radar-ui-ux-formal-handoff-preflight/v1` | `schemaVersion,status,recoveryId,authorizationRecord,authorities,remediationRollback,captureStack,task6,selectorDelta,sourceProjection,supplementalProjection,runtimeReceipt,eligibleDestinations,descriptorBudget` | `passed` |
| `quant-radar-ui-ux-manual-visual-review/v1` | `schemaVersion,kind,status,reviewedAt,reviewer,operatorCheckpoint,inputs,itemSetSha256,items` | `accepted` |
| `quant-radar-ui-ux-formal-handoff-candidate/v1` | `schemaVersion,status,recoveryId,preflight,task6,task9,migration,sourceProjection,supplementalProjection,runtimeReceipt,proposedContract,proposedContractSha256` | `candidate` |
| `quant-radar-ui-ux-formal-theme-handoff/v1` | `schemaVersion,status,recoveryId,authorizationRecord,authorities,preflight,captureStack,task6,task9,migration,sourceProjection,supplementalProjection,runtimeReceipt,themeBatch,allowedChanges` | `passed` |
| `quant-radar-ui-ux-theme-batch-candidate/v1` | `schemaVersion,status,rootContract,themeRunId,patchSha256,preimages,postimages,stagedProjection,testReport` | `candidate` |
| `quant-radar-ui-ux-theme-batch-review/v1` | `schemaVersion,status,rootContract,themeRunId,candidate,reviewers,findings` | `accepted` |
| `quant-radar-ui-ux-theme-batch-authorization/v1` | `schemaVersion,status,rootContract,themeRunId,candidate,review,preimages,postimages,unchangedProjection,runtimeReceipt` | `passed` |
| `quant-radar-ui-ux-theme-state-candidate/v1` | `schemaVersion,status,rootContract,authorization,themeRunId,manifest,bundle,sourceProjection,runtimeReceipt,visualItems` | `review_required` |
| `quant-radar-ui-ux-theme-state-attestation/v1` | `schemaVersion,status,rootContract,authorization,themeRunId,candidate,manualReview,manifest,sourceProjection,runtimeReceipt` | `passed` |
| `quant-radar-ui-ux-posttheme-comparison/v1` | `schemaVersion,status,rootContract,authorization,stateAttestation,themeRunId,pretheme,posttheme,sourceComparison,runtimeReceipt,pairs,changedIdsSha256` | `review_required` |
| `quant-radar-ui-ux-theme-closure/v1` | `schemaVersion,status,rootContract,authorization,stateAttestation,themeRunId,machineComparison,manualReview,posttheme,sourceProjection,runtimeReceipt` | `passed` |

`authorities`, `inputs`, `preimages`, `postimages`, and supplemental records are
unique sorted arrays of exact typed records, never open mappings.
`allowedChanges` is exactly
`{"production":[".streamlit/config.toml","app.py","requirements.txt",
"ui/_design.py"],"evidence":["docs/ui-ux/quant-radar-ui-v2-ux1b-classification.json"]}`.
`themeBatch` contains exactly those five preimages. The preflight's
`eligibleDestinations` is the exact fixed path/`exists:false` array. Candidate
`proposedContract` must itself validate against the exact root schema;
publication writes those already-encoded bytes without regeneration.

Named nested objects are closed as follows:

- `authorizationRecord` is `{sha256,sequence,amendment}`; amendment is
  `{path,sha256,size}`. `authorities` is a sorted `FileRecord` array.
- `remediationRollback` is `{prechange,rollback,bundle}` with two
  `ArtifactRef`s and an exact three-record bundle array.
- `captureStack` is `{contract,baseDigest,digest,members}` with one
  `FileRecord`, two SHA values, and exactly nine sorted `FileRecord`s.
- `task6` is `{pages,controls,historicalSourceProjection}`; `task9` is
  `{postcontrol,pretheme}`; each named bundle is a `BundleRecord`.
- `selectorDelta` is `{contract,postimages}` with one `FileRecord` and exactly
  nine sorted `SourceRecord`s. `supplementalProjection` has the same closed
  shape as `SourceProjection` but schema `...supplemental-source/v1`.
- `eligibleDestinations[]` is exactly `{path,exists:false}`.
  `descriptorBudget` is `{softBefore,hard,required,softApplied,reserve}` with
  reserve 64 and required no greater than 1536.
- `migration` is `{machineReport,manualReview,comparedCaptures}` with two
  `FileRecord`s and `comparedCaptures:117`.
- Every cross-lifecycle field named `rootContract`, `preflight`, `candidate`,
  `review`, `authorization`, `stateAttestation`, `machineComparison`,
  `manualReview`, `manifest`, `pretheme`, or `posttheme` is one `ArtifactRef`;
  `bundle` is one `BundleRecord`. Batch `testReport` is embedded exactly as
  `{status:"passed",commands,passed,failed:0,sha256}` with a bounded nonempty
  command-ID array and digest over the other fields.
- A batch image record is `{path,preimage,postimage}` with two `SourceRecord`s
  sharing the same path. There are exactly five. `stagedProjection` and
  `unchangedProjection` are `SourceProjection`s.
- `reviewers[]` is `{id,scope,verdict}` with verdict `passed`; `findings[]` is
  `{id,severity,status,summary}`, severity in `High|Medium|Low`, status
  `resolved|nonblocking`, and no unresolved High/Medium.
- A machine visual item is `{id,artifact,dimensions}`. A post-theme pair is
  `{id,before,after,dimensions,changed,semanticProjectionSha256}`.
  `sourceComparison` is `{beforeDigest,afterDigest,allowedChangedPaths,
  changedRecords}` and its allowed list is exactly the five records above.
- `runtimeReceipt`, every projection, and every referenced artifact are
  repeated/reopened rather than accepted through a prior exit code.

Every formal bundle additionally passes full terminal validation after
`freeze_manifest_bundle_contract()`/`reauthenticate_manifest_bundle()`:
schema, `status=passed`, exact mode/phase/count and capture-ID set, closed source
digest, exact stack SHA/digest, comparator/calibration attestations, all child
processes quiescent with zero return codes, provider expected=actual, mutator
expected=actual, all prohibited counters plus denied proxy/socket/external
network attempts zero, allowed loopback counters exact, exact artifacts, and
no extra leaf. Theme state is specifically `mode="ux1b-theme"`,
`phase="posttheme"`, 3 captures, 15 artifacts, and 16 total leaves.

## CLI and Make contract

The production CLI resolves the verified repository root and derives every
output; it accepts no arbitrary output path. Internal functions accept an
explicit scratch workspace FD for tests, but the production CLI does not.
Exact grammar is:

```text
ui_ux_theme_handoff.py preflight --recovery-id ID --authorization-record-sha SHA --json
ui_ux_theme_handoff.py verify-preflight --recovery-id ID --stage {before-capture,before-pretheme,after-capture} --json
ui_ux_theme_handoff.py publish-review --kind {control-migration,theme-states,posttheme} (--recovery-id ID | --theme-run-id ID) --json
ui_ux_theme_handoff.py prepare-handoff --recovery-id ID --json
ui_ux_theme_handoff.py verify-handoff-candidate --recovery-id ID --json
ui_ux_theme_handoff.py publish-handoff --recovery-id ID --json
ui_ux_theme_handoff.py verify-handoff [--require-pristine] --json
ui_ux_theme_handoff.py prepare-theme-batch --theme-run-id ID --json
ui_ux_theme_handoff.py authorize-theme-batch --theme-run-id ID --json
ui_ux_theme_handoff.py verify-theme-states --theme-run-id ID --json
ui_ux_theme_handoff.py close-theme-states --theme-run-id ID --json
ui_ux_theme_handoff.py compare-posttheme --theme-run-id ID --json
ui_ux_theme_handoff.py finalize-theme --theme-run-id ID --json
```

The root is always
`docs/ui-ux/quant-radar-ui-v2-ux1b-theme-contract.json`; machine paths derive
from kind plus ID or root SHA exactly as listed in Scope. Review intake derives
as `.claude/ui_snapshots/ux1b/review-intake/<kind>-<id>.json`. Missing, extra,
or conflicting ID flags fail. `UX1B_RECOVERY_ID`,
`UX1B_HANDOFF_PREFLIGHT`, and `UX1B_THEME_RUN_ID` are empty-required Make
variables. Existing timestamp defaults are not used by formal theme-state or
posttheme targets. One accepted theme run ID is bound by the root-SHA claim and
reused through state, posttheme, and closure.

Exit `0` means created/verified/reconciled success; `2` CLI grammar; `3`
contract/data/authentication failure; `4` invalid collision; `5` missing
dependency or FD budget; `6` committed reconciliation required; `130`
interrupt. Success stdout is exactly one canonical object
`{kind,path,sha256,status}`; errors use bounded stderr and no success stdout.

Make adds:

- `ui-ux1b-theme-handoff-preflight`;
- `ui-ux1b-control-migration-review`;
- `ui-ux1b-theme-handoff-prepare`;
- `ui-ux1b-theme-handoff`;
- `ui-ux1b-theme-prepare`;
- `ui-ux1b-theme-authorize`;
- existing `ui-ux1b-theme-states`, extended with machine verification only;
- `ui-ux1b-theme-states-close`;
- existing `ui-ux1b-posttheme`, extended with machine comparison only;
- `ui-ux1b-theme-close`.

Make must propagate every nonzero status. Direct runner success is documented
as capture evidence only. Static integration tests reject missing, reordered,
shell-masked, or forced-success verifier steps.

The existing authoritative `ui-ux1b-recovery-postcontrol` recipe is changed,
not merely accompanied by a new target. Its first command is
`verify-preflight --stage before-capture`; after the 36-row command and before
the 81-row command it runs `--stage before-pretheme`; after both it runs
`--stage after-capture`. It requires the fixed preflight via
`UX1B_HANDOFF_PREFLIGHT`. A runner invoked before preflight makes preflight
ineligible because an after-namespace exists; a direct runner manifest can
never become root authority by itself.

## Implementation checklist

### Task 0 — accept and freeze the remediation boundary

- [ ] Complete independent review; resolve all High/Medium/blocking findings.
- [ ] Mark this plan accepted, compute its final SHA, and append the exact
  `AUTHORIZED` record to recovery evidence. Any later plan edit repeats this
  gate.
- [ ] Reauthenticate all upstream authorities, rollback bundles, selector
  delta, capture-stack contract/members, both canonical Task 6 manifests, 234
  artifacts, 163/73 leaf counts, nine selector postimages, and exact runtime.
- [ ] Require every Task 9 and remediation-created destination absent.
- [ ] Create and reopen the remediation prechange/rollback records and bundle.

**Gate:** exact authority chain, dirty-worktree CAS/rollback coverage, and
first-attempt eligibility; otherwise stop before implementation.

### Task 1 — add fail-first verifier contracts

- [ ] Prove the formal recovery manifest is rejected by the legacy loader and
  prove the formal post-theme runner bypasses it.
- [ ] Add positive synthetic fixtures for every CLI lifecycle stage.
- [ ] Add exact-key/path/count/size/mode/runtime/authority/source mutations.
- [ ] Add descriptor attacks for symlink, hardlink, traversal, unsafe mode,
  owner, inode/rename, hash/size, duplicate, and extra leaf.
- [ ] Add low-hard-limit/real-cardinality FD tests and prove capture children
  inherit no verifier evidence descriptors.
- [ ] Add publication faults for staging, child wrong-inode receipt, stage-name
  swap, pre-rename crash, atomic-rename collision, post-commit lost response,
  fsync/reconciliation, and multiprocess one-winner behavior.
- [ ] Add manual-review missing/forged/duplicate/wrong-kind/set/hash/dimension
  mutations and prove the verifier never authors review judgments.
- [ ] Add sidecar normalization positive/negative replay, identical-PNG
  acceptance, dimension mismatch, unexplained-delta rejection, and distinct
  stack/source rejection.
- [ ] Add 3/3 plus 9-supplement, 81/81, first-attempt partial namespace, passed
  manifest alone, two-run-ID claim competition, and guarded-Make ordering/
  failure-propagation tests.

**Gate:** the new lifecycle tests fail only because the verifier/Make closure
does not exist; inherited suites remain green.

### Task 2 — implement the external verifier

- [ ] Implement the exact CLI, schemas, descriptor contracts, source/runtime
  projection, normalization, review-copy validation, and publication primitive.
- [ ] Reuse existing evidence/isolation validators without editing frozen
  stack members.
- [ ] Keep diagnostics bounded, workspace-relative, and secret-free.
- [ ] Prove candidate verification runs in a fresh process before public root
  rename, validates the exact passed stage FD/inode, and reconciliation accepts
  only exact committed bytes.

**Gate:** all success, mutation, filesystem, review, and publication tests
pass; stack members remain exact.

### Task 3 — wire fail-closed Make orchestration

- [ ] Add the verifier test to `ui-ux1b-recovery-tests`.
- [ ] Add the exact explicit-variable targets above.
- [ ] Make the existing recovery postcontrol target consume preflight before
  either irreversible namespace write and between the two captures.
- [ ] Keep human-authored review intake separate from machine capture and
  comparison targets.
- [ ] Ensure theme-state/posttheme capture success cannot mask verifier failure
  or claim closure.

**Gate:** static and subprocess integration tests prove exact order and nonzero
propagation.

### Task 4 — verify remediation code before canonical capture

- [ ] Run the verifier suite, all 310 current recovery checks, repository
  `make test`, artifact loader/API regressions, and exact UX-0/UX-1A safety,
  component, contract, navigation, and legacy gates.
- [ ] Run 57-row discovery and 10-row real Chromium smoke after verifier/test
  bytes freeze; require 12/12 process quiescence and unchanged stack digest.
- [ ] Run repository-wide compileall, focused py_compile/tabnanny, Python 3.10
  AST syntax parsing, `pip check`, `git diff --check`, `verify-prechange`,
  `verify-scope`, protected hashes, selector posthashes, source projection, and
  final `segmented_control` scan.
- [ ] Compare actual diff to this amendment and obtain independent correctness,
  publication/security, and scope reviews. Fix all blocking findings.
- [ ] Publish and reopen `theme-handoff-preflight-20260719T211915Z.json`.

**Gate:** preflight is immutable and every capture input exactly matches it.

### Task 5 — execute recovery Task 9 exactly once

- [ ] Recheck all first-attempt destinations absent, then once run
  `make ui-ux1b-recovery-postcontrol UX1B_RECOVERY_ID=20260719T211915Z
  UX1B_HANDOFF_PREFLIGHT=.claude/ui_snapshots/ux1b/recovery/theme-handoff-preflight-20260719T211915Z.json`.
- [ ] Require post-control 36/36 and canonical pre-theme 81/81 under the same
  source/stack/runtime identity.
- [ ] Run the existing migration verifier once; require `117 / 117` machine
  comparison.
- [ ] Descriptor-reopen four manifests, 468 referenced artifacts, exact leaf
  counts `163 / 73 / 163 / 73`, no extra leaves, and migration report.
- [ ] Obtain a human-authored 117-item migration review and publish its exact
  immutable assertion at the explicit operator checkpoint.
- [ ] Run `prepare-handoff`, record the proposed root path/SHA in recovery
  evidence as non-authoritative `PENDING_PUBLICATION`, and run
  `verify-handoff-candidate` from a fresh process.
- [ ] Reauthenticate all inputs and use `publish-handoff` as the final Task 9
  evidence-authority write. Then run read-only fresh-process `verify-handoff
  --require-pristine` as a consumer smoke.

**Gate:** immutable root exists, verifies pristine, and is consumable before
any parent theme edit. Any partial first attempt follows the revocation rule.

### Task 6 — authorize and execute parent Task 3

- [ ] Materialize and test the five exact staged postimages, publish the batch
  candidate, and obtain independent staged-diff review.
- [ ] Publish the one root-SHA-keyed authorization claim immediately before
  the live edit; it binds one explicit theme run ID.
- [ ] Recheck its five preimages, apply only the accepted semantic-theme batch
  plus ledger transition, and require all bound postimages, no fifth production
  path, and no sixth total path.
- [ ] Run focused token/static/forward-ledger/fail-soft gates and stop without a
  success claim on any partial batch.

**Gate:** exact four-runtime-plus-ledger logical CAS batch and all parent Task 3
gates pass.

### Task 7 — capture and close parent Task 4

- [ ] Run formal theme-state capture, then machine verification for exact 3/3
  and 15 referenced artifacts.
- [ ] Obtain and publish the human-authored 12-item visual review.
- [ ] Run `close-theme-states` and reopen the immutable attestation.

**Gate:** Task 4 closes only through the attestation.

### Task 8 — capture and close parent Task 5

- [ ] Run formal post-theme 81/81 capture and machine comparison.
- [ ] Require exact source/runtime/counter/semantic/geometry closure; allow
  byte-identical PNGs and require explanations only for changed PNGs.
- [ ] Obtain and publish the human-authored 81-item visual review.
- [ ] Run `finalize-theme` and reopen the immutable final closure.

**Gate:** the final closure, not the manifest or machine candidate, closes
parent Task 5.

### Task 9 — finish parent Tasks 6–8

- [ ] Run the complete parent regression/adversarial/scope gates and two fresh
  changed-code reviews.
- [ ] Rehearse the exact four-runtime-plus-ledger rollback in an owned scratch
  copy.
- [ ] Reconcile docs/journals/roadmap without changing immutable evidence.

**Gate:** all parent completion criteria and local completion gates pass.

## Verification commands

The implementation must expose these exact command families; all IDs/paths are
explicit in Make recipes:

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
make ui-ux1b-legacy

.venv/bin/python scripts/ui_ux_snapshot_matrix.py --ux1b-discover --json
.venv/bin/python scripts/ui_ux_snapshot_matrix.py --ux1b-real-smoke --json
.venv/bin/python -m compileall -q app.py api ui scripts
.venv/bin/python -m py_compile scripts/ui_ux_theme_handoff.py scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -m tabnanny scripts/ui_ux_theme_handoff.py scripts/test_ui_ux_theme_handoff.py
.venv/bin/python -m pip check
git diff --check

make ui-ux1b-theme-handoff-preflight UX1B_RECOVERY_ID=20260719T211915Z
make ui-ux1b-recovery-postcontrol UX1B_RECOVERY_ID=20260719T211915Z \
  UX1B_HANDOFF_PREFLIGHT=.claude/ui_snapshots/ux1b/recovery/theme-handoff-preflight-20260719T211915Z.json
make ui-ux1b-recovery-verify-migration UX1B_RECOVERY_ID=20260719T211915Z
make ui-ux1b-control-migration-review \
  UX1B_RECOVERY_ID=20260719T211915Z
make ui-ux1b-theme-handoff-prepare UX1B_RECOVERY_ID=20260719T211915Z
make ui-ux1b-theme-handoff UX1B_RECOVERY_ID=20260719T211915Z

UX1B_THEME_RUN_ID=<explicit-id>
make ui-ux1b-theme-prepare UX1B_THEME_RUN_ID="$UX1B_THEME_RUN_ID"
make ui-ux1b-theme-authorize UX1B_THEME_RUN_ID="$UX1B_THEME_RUN_ID"
make ui-ux1b-theme-states UX1B_THEME_RUN_ID="$UX1B_THEME_RUN_ID"
make ui-ux1b-theme-states-close UX1B_THEME_RUN_ID="$UX1B_THEME_RUN_ID"
make ui-ux1b-posttheme UX1B_THEME_RUN_ID="$UX1B_THEME_RUN_ID"
make ui-ux1b-theme-close UX1B_THEME_RUN_ID="$UX1B_THEME_RUN_ID"
```

Every changed Python file must parse with
`ast.parse(..., feature_version=(3, 10))`. The implementation must also invoke
the existing exact `verify-prechange`, `verify-scope`, protected-hash,
source-projection, process-quiescence, and zero-`segmented_control` checks used
by the accepted recovery plan; a missing Make alias is invoked by its exact
underlying Python command rather than silently skipped.

## Acceptance criteria

- `AC-HANDOFF-001`: Given exact accepted authority and absent first-attempt
  destinations, when preflight publishes, then it binds the only legal Task 9
  inputs without changing a frozen stack member.
- `AC-HANDOFF-002`: Given authenticated Task 9 evidence and an accepted external
  migration review, when root publication succeeds, then exactly one immutable
  root is visible and a fresh consumer verifies it pristine.
- `AC-HANDOFF-003`: Given any prerequisite/path/inode/hash/source/stack/selector/
  runtime/review mutation before publication, when a verifier command runs,
  then it exits nonzero and publishes no success leaf; collisions remain exact.
- `AC-HANDOFF-004`: Given a lost response or durability error after atomic
  rename, when a fresh verifier runs, then it adopts only the exact same
  committed inode/bytes after full input revalidation and parent fsync; absent
  or non-exact output is rejected without republishing.
- `AC-HANDOFF-005`: Given the root contract, when Task 3 begins, then one fresh
  root-SHA-keyed authorization binds five exact pre/post records, one theme run
  ID, no fifth production path, and no sixth total path.
- `AC-HANDOFF-006`: Given a passed 3/3 theme-state bundle, when Task 4 closes,
  then all 15 artifacts and the external 12-item review are bound by an
  immutable attestation.
- `AC-HANDOFF-007`: Given a passed formal post-theme 81-row bundle, when Task 5
  closes, then exact non-theme semantics/geometry/counters/runtime/source pass,
  identical PNGs are allowed, changed PNGs are externally accepted, and one
  immutable final closure binds the full chain.
- `AC-HANDOFF-008`: Given a partial first Task 9 attempt, when any retry is
  requested with the same recovery ID, then it fails before capture and demands
  a reviewed cross-ID lineage amendment.

## Traceability

| Requirement | Implementation | Verification |
| --- | --- | --- |
| `REQ-001`, `CFR-001..004` | preflight, candidate, publish/verify root | authority, descriptor, source, publication fault tests |
| `REQ-002`, `CFR-005` | staged five-record candidate, global authorization, logical CAS | pre/postimage/two-run competition/fifth-production/sixth-total tests |
| `REQ-003`, `CFR-006` | state candidate, review copy, attestation | exact 3/3 + 15 artifacts + 12 visual items |
| `REQ-004`, `CFR-005..006` | posttheme candidate, review copy, final closure | exact 81 pairs, normalization mutations, source/runtime parity |
| first-attempt rule | preflight and namespace eligibility | partial/nonterminal/refusal tests |

## Risks and abort rules

- Any stack/member, upstream authority, canonical Task 6, selector postimage,
  runtime, or preflight drift aborts before Task 9.
- Any first-attempt partial namespace preserves evidence and revokes the ID; no
  cleanup or retry occurs under this plan.
- Any verifier/test/Make/source change after preflight invalidates preflight and
  revokes same-ID Task 9 eligibility.
- Any manual-review gap blocks the related attestation/closure; the verifier
  cannot self-approve it.
- Any partial four-runtime-plus-ledger theme batch follows exact postimage-aware rollback and
  never overwrites concurrent user bytes.
- An initial root contract is never deleted, even after revocation.

## Plan review gate

Review must cover request fit, precedence, dirty-worktree CAS, formal schemas,
descriptor lifetime, source/runtime projection, normalization bounds,
human-review provenance, publication atomicity, Make failure propagation,
first-attempt behavior, Task 3–5 consumption, rollback, and complete tests.
Resolve every High/Medium/blocking issue before implementation. If the same
blocker survives three review iterations, stop and report it.

## Review record

| Iteration | Version | Verdict | Findings |
| --- | --- | --- | --- |
| 1 | `v0.1-draft` | NO-GO | Authority/final-write order, raw sidecar equality, mutable root, manual review, Task 3–5 lifecycle, and retry semantics were blocking. |
| 2 | `v0.2-draft` | NO-GO | Independent authority, semantics, and publication reviews found 9 High in aggregate: missing classification authority, unguarded first capture, mutable authorization stanza, underspecified schemas/interfaces, unenforceable publication uncertainty, FD 256 exhaustion, child/stage inode gap, and concurrent theme claims. |
| 3 | `v0.3-draft` | PENDING | Acceptance requires three independent reviews with no High/Medium/blocking finding. |

## Change history

| Version | Date | Change |
| --- | --- | --- |
| `v0.1-draft` | 2026-07-19 | Initial external-verifier proposal; independent review found unresolved authority, publication, normalization, review, and lifecycle blockers. |
| `v0.2-draft` | 2026-07-20 | Added explicit precedence and upstream hashes, dirty-worktree CAS/rollback, staged root publication, exact external review schemas, narrow sidecar normalization, immutable Task 3–5 evidence, full inherited gates, and first-attempt-only semantics. |
| `v0.3-draft` | 2026-07-20 | Closed second-round blockers with an exact authorization stanza, parent prechange/rollback/classification authority, guarded one-shot capture state machine, FD-budget negotiation, same-inode fresh-child verification, atomic no-replace rename plus reconciliation, global root-keyed theme claim, exact five-record staged CAS, canonical artifact/CLI schemas, and full terminal validation. |
