# UX-1B TEST-021 Task 1 Second Cache-Incident Guard Correction

## Status and authority

- State: proposed v0.4; blocked until independent review reports zero High or
  Medium findings.
- Parent implementation authority:
  `2026-07-21-quant-radar-ui-ux-ux1b-task1-fail-closed-implementation-replacement.md`
  at SHA-256
  `f8bc4ed48c7addbc2de0bfba74a104f6908d5fc28c1a528e52c11bc3e7dba639`.
- Superseded first cache correction evidence:
  `2026-07-21-quant-radar-ui-ux-ux1b-task1-cache-incident-correction.md`
  at SHA-256
  `0dbc597352447eb6a020730e2a9468175d3c0b24bff8c0126c3b9beaa0892c27`,
  size `12126`.
- This correction is additive in semantics but replaces the first correction's
  live path after review. The accepted v0.3 bytes remain immutable at
  `/private/tmp/quant-radar-test021-v2.6QNxeu/allowed/cache-incident-plan.md`.
  The reviewed v0.4 bytes are first frozen as
  `allowed/cache-incident-2-plan.md`; after acceptance, those exact bytes
  replace the live
  `2026-07-21-quant-radar-ui-ux-ux1b-task1-cache-incident-correction.md`, and
  this temporary `...cache-incident-2-correction.md` proposal is removed.
  Therefore the running guard authenticates one live/frozen replacement pair,
  not two independently mutable live authority files.

## Incident record

While repairing v2 review findings, the agent mistakenly ran:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m py_compile scripts/test_ui_ux_theme_handoff.py
```

`py_compile` writes its requested cache even with `PYTHONDONTWRITEBYTECODE`.
It replaced the pre-existing ignored cache leaf. The agent then misclassified
the replacement as newly created and, after explicit approval, removed it.
The authenticated original bytes cannot be recovered. No Python source,
test assertion, plan authority, journal, user data, or runtime artifact was
removed.

The immutable original workspace baseline proves the second affected row was
exactly:

```text
path: scripts/__pycache__/test_ui_ux_theme_handoff.cpython-311.pyc
type: file
sha256: dc5af406ae2445af6ad4aec1eb0422a813c54145d9f044562e046557c8e2a264
```

The same baseline proves the first incident row was exactly:

```text
path: scripts/__pycache__/ui_ux_theme_handoff.cpython-311.pyc
type: file
sha256: ef9f948638844e9dfffdd75841784aca4b03dd6d20679b4d7d08c10e3cfdbac1
```

The original cache projection has `223` rows and SHA-256
`0cc266913ed54886e3b294382385c9cc33a309f82084da3a2da35e6785ef433f`.
Removing exactly the first incident row derives the already accepted `222`-row
SHA-256
`7c98c6f4c9bda9aae2807dd3ef63452bb138f8faa628335a83193924830ac4da`.
Removing exactly the second incident row from that set derives the closed
`221`-row SHA-256
`e1131be3af68e9285df1ccab261c00e09e14e4b7d9913793044a78250e987cfb`.

## Requirements

### INC2-001 — Preserve evidence and authenticate one replacement authority

Every invocation must authenticate both immutable original workspace manifests,
the original cache digest evidence, both Task 1 source preimages, the accepted
implementation plan, and the single live/frozen replacement correction before
collection and again after every workspace/cache comparison. The old v0.3
frozen correction is acceptance-review evidence whose hash is incorporated by
this replacement; it has no live counterpart and is not a second per-invocation
authority after replacement.
The final replacement reauthentication occurs immediately before the final
two-name absence snapshot. A missing, nonregular, symlinked, size-changed,
hash-changed, or byte-different authority fails closed.

### INC2-002 — Two exact absent paths, no general exclusion

The guard must parse the immutable original workspace manifest and require
exactly one regular-file row for each incident path with the exact SHA above.
For each pre-collection and post-comparison absence snapshot it opens and
retains the authenticated workspace root, then opens `scripts` relative to the
root descriptor and `__pycache__` relative to the scripts descriptor. Every
open uses `O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC`. It verifies each exact
expected directory identity and records before `fstat` tuples for root,
scripts, and cache containing
`st_dev,st_ino,st_mode,st_mtime_ns,st_ctime_ns`.

It checks both incident basenames with
`os.stat(name, dir_fd=cache_fd, follow_symlinks=False)`. Only
`FileNotFoundError` is accepted for each name. After those checks it must:

1. `stat("__pycache__", dir_fd=scripts_fd, follow_symlinks=False)` and require
   the live entry to be a directory with the same `st_dev,st_ino,st_mode` as
   the retained cache descriptor;
2. `stat("scripts", dir_fd=root_fd, follow_symlinks=False)` and require the live
   entry to be a directory with the same `st_dev,st_ino,st_mode` as the
   retained scripts descriptor;
3. take after `fstat` tuples in the exact order root, scripts, then cache, and
   require every complete tuple to equal its before tuple.

Any file, directory replacement, symlink including dangling, FIFO, socket,
device, permission error, other lookup result, or namespace-parent change
fails. The successful root after `fstat` is the snapshot's linearization point.
The later scripts/cache after-`fstat` reads are mandatory retrospective proof
that neither descendant changed across that point. After the final cache
after-`fstat`, the function closes only the already retained descriptors and
returns success without another workspace read or fallible command. A mutation
strictly after the root linearization point belongs to a later workspace state;
if it occurs before its corresponding retrospective scripts/cache check, that
check still makes the current guard fail.
Creation of A after A's lookup but during B's lookup changes the cache tuple;
replacement or swap-back of the cache directory changes the scripts tuple or
breaks its live inode binding; replacement or swap-back of `scripts` changes
the root tuple or breaks its live inode binding.

The two authenticated rows are then removed from an in-memory copy of the
original expected rows. No pattern, directory, extension, or third path may be
excluded as an incident.

### INC2-003 — Exact remaining workspace and cache derivation

The collector retains the accepted no-follow traversal, raising `onerror`,
stable before/after `lstat`, bounded streaming file hashes, exact type handling,
sorted rows, and equality against the original manifest minus only the two
incident rows and already authorized Task 1 paths.

The cache projection must independently prove the original 223-row digest,
derive and prove the first 222-row digest, derive and prove the final 221-row
digest, then require a fresh current projection to equal the final digest.
A current-only hard-coded digest or broad cache omission fails.

### INC2-004 — Closed implementation and verification

Implementation is private-only under the existing owner directory:

- `cache-incident-2-corrected-guard.zsh`;
- `cache-incident-2-guard-selftest.py` and owned fixtures.

The self-test must prove the positive exact state and reject, one at a time:

1. either original incident row missing, duplicated, wrong-type, or wrong-SHA;
2. either current incident path as a file, directory, dangling symlink, or FIFO;
3. creation of either incident path after enumeration but before the final
   absence snapshot;
4. any third non-allowed workspace/cache addition, deletion, byte change, or
   type change;
5. substituted original, first-corrected, or final cache digests;
6. live/frozen replacement-correction drift before collection, after collection
   but before comparisons finish, and after every comparison but before the
   final absence snapshot;
7. traversal/hash failures and conditional-shell invocation contexts.
8. creation of path A after A's lookup but before B's lookup, creation of B
   after B's lookup but before the after `fstat`, and create-then-delete of
   either name inside the snapshot window; all must fail through the retained
   parent metadata check.
9. replace-away, replace-in, and swap-back races for the whole `__pycache__`
   directory after its descriptor opens; the same three races for `scripts`;
   and a replacement directory already containing either incident name or a
   third non-allowed cache entry.
10. creation of an incident/third entry after the root after-`fstat` but before
    the cache after-`fstat`, and replacement of `__pycache__` after the root
    after-`fstat` but before the scripts after-`fstat`; both retrospective
    checks must fail.

All later Python checks must use import execution with
`PYTHONDONTWRITEBYTECODE=1`, in-memory `compile()`, AST parsing, or an explicit
private `cfile`; no workspace `py_compile` target is permitted.

### INC2-005 — Disclosure and scope

The final Task 1 journal entry must disclose both unrecovered cache leaves and
state that completion relies on two independently reviewed corrections. The
replacement live plan, its owner-only frozen copy, private guard/self-test, and
existing Task 1 allowed paths are the only retained additions. The temporary
proposal path is removed immediately after its reviewed bytes replace the
original live correction path. No production behavior, Task 2
implementation, API/UI file, Makefile, parent authority, or baseline evidence
is authorized by this correction.

## Execution checklist

1. Freeze this postimage SHA/size and copy it owner-only beside the first
   correction evidence.
2. Obtain independent plan review with zero High/Medium.
3. Replace the original live correction path with the byte-identical accepted
   v0.4 postimage and remove the temporary proposal path; authenticate the new
   live/frozen pair before implementation.
4. Implement the private two-row guard by extending, not weakening, the
   accepted first correction algorithm.
5. Run all INC2-004 positive/negative self-tests.
6. Start or update a `zsh -f` supervisor with immutable SHA/size constants and
   require the two-row workspace/cache gates before and after every remaining
   edit or test.
7. Finish code closure, freeze the exact source/test postimages, and obtain a
   fresh independent implementation review.
8. Append one combined factual journal entry per required skill and one Project
   Activity row; prove append-only status where an original preimage exists.

## Acceptance criteria

- AC-INC2-001: both incident baseline rows and all authority/evidence bytes are
  authenticated exactly.
- AC-INC2-002: only the two named absent rows are removed; every other workspace
  row is exact, and the retained-parent snapshot rejects the A-then-B race.
- AC-INC2-003: 223-row original, 222-row first correction, and 221-row second
  correction cache digests are derived and verified in order.
- AC-INC2-004: every positive and adversarial self-test passes under `zsh -f`.
- AC-INC2-005: independent plan and implementation reviews report zero
  High/Medium before Task 1 completion.
- AC-INC2-006: final disclosure names both unrecovered cache leaves and no
  completion claim says the original cache fingerprint passed.

## Review questions

1. Can any object occupy either incident path and pass?
2. Can a third workspace/cache change be hidden?
3. Are both original rows and all three cache digests proved in order?
4. Can the single live replacement correction drift after being excluded from
   traversal, and is the old correction limited to immutable frozen evidence?
5. Is this correction limited to the factual second cache incident without
   authorizing source or Task 2 behavior?

PASS requires zero High and zero Medium findings.

## Review history

| Version | Result | Findings resolved |
| --- | --- | --- |
| v0.1 | FAIL — 1 High | Replaced sequential two-name `lstat` with one retained-parent metadata snapshot and explicit A-after-A/B-before-after-fstat injections; collapsed two live correction plans into one reviewed replacement live/frozen pair; fixed final post-comparison authority ordering. |
| v0.2 | FAIL — 1 High | Extended the retained snapshot through workspace-root/scripts/cache dirfds, re-bound both live directory pathnames to their retained inodes, and added replace-away/replace-in/swap-back races at both namespace levels. |
| v0.3 | FAIL — 1 High | Reordered descendant after-fstats to root/scripts/cache so the later checks retrospectively prove stability across the root linearization point; added exact lower-level-after/root-before injection windows. |
