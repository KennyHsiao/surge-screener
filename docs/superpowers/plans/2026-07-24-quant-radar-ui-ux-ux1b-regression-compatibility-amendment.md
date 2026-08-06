# UX-1B Formal Theme Handoff Regression Compatibility Amendment

## Document Info

| Field | Value |
| --- | --- |
| Type | Implementation amendment |
| Version | 1.0 |
| Status | Accepted for sequence 2 authorization |
| Author | Quant Radar implementation session |
| Approver | Repository maintainer, authorized 2026-07-24 |
| Review | Passed, 0 blocker / 0 High / 0 Medium |
| Audience | Maintainer, verifier implementer, reviewer |
| Date | 2026-07-24 |
| Recovery ID | `20260719T211915Z` |

## Authority and purpose

This document is a narrow amendment to:

- `docs/superpowers/plans/2026-07-20-quant-radar-ui-ux-ux1b-formal-theme-handoff-replacement.md`
  at SHA-256
  `3a68b3e80f8b963181bfe439de299294cdba67642d9dad824d31a6a8ac29c581`;
- its traceability ledger at SHA-256
  `47f32c1b0a3235f56247d30b1341c9c6f315b6ac8592dcce904ca4dfe41ee9a8`.

It resolves one blocking contradiction discovered by real candidate execution.
The parent plan requires a `37/0/0` candidate regression but permits only two
new verifier files before Tier 0. Five additional compatibility patches are
required for that regression under the candidate sandbox. Reverting all five is
the only tested combination that reconstructs the historical source digest
`4eeb3629fbd83ef9e61f553cd3eae93e7b8ede4b925e45774ece99847dfce8a5`.

The maintainer authorized this amendment direction on 2026-07-24. The package
does not become executable authority until its final bytes and sibling
traceability ledger are bound by the sequence 2 V2 authorization stanza.

## Scope

### In scope

- Bind exactly five already-applied regression compatibility patches.
- Authenticate their exact historical preimages and live postimages.
- Reverse the five patches in memory when reconstructing historical source.
- Retain the parent plan's exact two verifier bootstrap paths.
- Retain the parent plan's exact five theme batch paths and apply order.
- Add mutation-resistant authorization, reconstruction, and regression tests.

### Out of scope

- No sixth compatibility path.
- No production theme path is added or removed.
- No historical evidence file is rewritten.
- No selector, capture-stack, Task 6, or recovery ID is changed.
- No Git reset, checkout, or destructive cleanup is authorized.
- No compatibility patch is applied again during the theme batch.
- No fail-soft API or Streamlit behavior is changed by this amendment.

## Requirements

### `REQ-001` — closed compatibility boundary

The verifier MUST accept only the exact path-sorted five-row compatibility
contract below. It MUST require each live source byte string to equal the bound
postimage before historical reconstruction.

### `CFR-001` — historical integrity

The verifier MUST reverse each patch using closed exact byte replacements,
require each replacement source to occur exactly once, and require the result
to equal the bound preimage SHA-256 and size.

### `CFR-002` — authority and scope integrity

The sequence 2 authorization MUST bind this amendment and its ledger. The
sequence 1 parent plan and ledger MUST remain byte-exact imported authorities.
The theme batch MUST remain the original five ordered paths.

### `CFR-003` — regression integrity

The five live postimages MUST remain executable inputs to the real candidate
regression. Sealing remains forbidden unless the exact result is `37/0/0`.

## Exact compatibility contract

Rows are path-sorted. `mode` is the immutable source-mirror mode. The canonical
JSON encoding of this array has size `1792` and SHA-256
`7db242fe074154ff1bfa32c252a99bc8dd1197c9cd87e38eaea40b9950d6e14e`.
Each row has exactly these keys:
`forwardPatchSha256,forwardPatchSize,mode,path,postSha256,postSize,preSha256,preSize`.
Sizes are non-boolean integers; all other values are strings. The exact
canonical bytes are the UTF-8 bytes of the following single line, excluding
the Markdown fences and their line endings:

```json
[{"forwardPatchSha256":"9c99568dc9752c4553987d90396b41c2393407d1db728971df0338f855a634de","forwardPatchSize":632,"mode":"0444","path":"scripts/01_hard_filter.py","postSha256":"2366660da3487b98026c94dc292e27f2ac9c72ee4dc6bc527758ddc0486bdd38","postSize":28271,"preSha256":"ef95ed221299e082c6aaad857f721d0a89368973208da2e6838514b3a452a561","preSize":28271},{"forwardPatchSha256":"c37f344249be0198b2ba1fe6b86e58e09f0a6acfb54e47d95c9a2eaafec53d92","forwardPatchSize":796,"mode":"0444","path":"scripts/momentum_options.py","postSha256":"0a82e0d5e50a15c95cb4ad55241002892f95baad56ea35be5e28b100a79899e8","postSize":24077,"preSha256":"0811ae0c1e1a852ac71562bba759c5f296559ebab4ad0b9679c88099e5862968","preSize":23786},{"forwardPatchSha256":"0c33b92f0a3c32c305782aefddbdf3e4bed3f1dcec5ba4dedd638f4948d4a6fe","forwardPatchSize":1574,"mode":"0444","path":"scripts/test_ui_ux_components.py","postSha256":"a490457f7b8fc7fe20f75087ba7e11da111ce6ca0aa2c2c0df1ee07919d1f4ff","postSize":15363,"preSha256":"f9c89eff63cf8d263d8b1aeb8e50c9aacd5f7f899a3f73ad23fc123cbafec3b8","preSize":14412},{"forwardPatchSha256":"681e8b804dffeca7f7ebced0fb8a8db3f8d2cc26f358267809a7008fdcb48212","forwardPatchSize":475,"mode":"0444","path":"scripts/test_ui_ux_contract.py","postSha256":"39bf21d583f34399ed6d5477ec8dacb5f25504bfa540a84dcdf04f8d35b5a35a","postSize":69350,"preSha256":"c488fff2ff57880de9d44f065ee2850765a0b0fab39b2dbb72b2a36468481c4a","preSize":69276},{"forwardPatchSha256":"a9de6d64a0576f9be1c7c2cd953f89941fccae7a74c5c67276494c15b6f5bb35","forwardPatchSize":2391,"mode":"0444","path":"scripts/test_ui_ux_fixtures.py","postSha256":"93cd490a2b57f0fc9dae45192f910f7dd93d4d76df28dd73f22f40cddf9d9d70","postSize":63637,"preSha256":"57fe9cd56286b12cfa5bab779c4a8b00d3a5d475382bf32d55d529b09583073a","preSize":63990}]
```

| Path | Preimage size / SHA-256 | Postimage size / SHA-256 | Forward patch size / SHA-256 | Mode |
| --- | --- | --- | --- | --- |
| `scripts/01_hard_filter.py` | `28271` / `ef95ed221299e082c6aaad857f721d0a89368973208da2e6838514b3a452a561` | `28271` / `2366660da3487b98026c94dc292e27f2ac9c72ee4dc6bc527758ddc0486bdd38` | `632` / `9c99568dc9752c4553987d90396b41c2393407d1db728971df0338f855a634de` | `0444` |
| `scripts/momentum_options.py` | `23786` / `0811ae0c1e1a852ac71562bba759c5f296559ebab4ad0b9679c88099e5862968` | `24077` / `0a82e0d5e50a15c95cb4ad55241002892f95baad56ea35be5e28b100a79899e8` | `796` / `c37f344249be0198b2ba1fe6b86e58e09f0a6acfb54e47d95c9a2eaafec53d92` | `0444` |
| `scripts/test_ui_ux_components.py` | `14412` / `f9c89eff63cf8d263d8b1aeb8e50c9aacd5f7f899a3f73ad23fc123cbafec3b8` | `15363` / `a490457f7b8fc7fe20f75087ba7e11da111ce6ca0aa2c2c0df1ee07919d1f4ff` | `1574` / `0c33b92f0a3c32c305782aefddbdf3e4bed3f1dcec5ba4dedd638f4948d4a6fe` | `0444` |
| `scripts/test_ui_ux_contract.py` | `69276` / `c488fff2ff57880de9d44f065ee2850765a0b0fab39b2dbb72b2a36468481c4a` | `69350` / `39bf21d583f34399ed6d5477ec8dacb5f25504bfa540a84dcdf04f8d35b5a35a` | `475` / `681e8b804dffeca7f7ebced0fb8a8db3f8d2cc26f358267809a7008fdcb48212` | `0444` |
| `scripts/test_ui_ux_fixtures.py` | `63990` / `57fe9cd56286b12cfa5bab779c4a8b00d3a5d475382bf32d55d529b09583073a` | `63637` / `93cd490a2b57f0fc9dae45192f910f7dd93d4d76df28dd73f22f40cddf9d9d70` | `2391` / `a9de6d64a0576f9be1c7c2cd953f89941fccae7a74c5c67276494c15b6f5bb35` | `0444` |

## Amended source-authority algorithm

The sequence 2 verifier MUST perform these steps in order:

1. Reauthenticate the sequence 2 amendment and ledger from retained
   descriptors.
2. Reauthenticate the imported sequence 1 plan and ledger by their existing
   hashes.
3. Build the current source mirror using the frozen
   `scripts/ui_ux_isolation.py` implementation and the parent include/exclude
   policy.
4. For every compatibility row, require the current mirror record and retained
   workspace bytes to equal the exact postimage.
5. Apply the path-specific reverse edits from Appendix A in memory. Every
   matched postimage fragment MUST occur exactly once. Missing, duplicate,
   reordered, or partially applied fragments fail closed.
6. Require every reconstructed byte string to equal its exact preimage.
7. Replace the five current mirror records with reconstructed preimage records.
8. Remove exactly
   `scripts/ui_ux_theme_handoff.py` and
   `scripts/test_ui_ux_theme_handoff.py`.
9. Substitute the existing nine authenticated legacy selector records.
10. Encode the resulting records with the frozen source-mirror encoder and
    require historical digest
    `4eeb3629fbd83ef9e61f553cd3eae93e7b8ede4b925e45774ece99847dfce8a5`.

The verifier MUST NOT obtain a green result by directly substituting the five
preimage hashes without first reconstructing and hashing the preimage bytes.

## Tier 0 and theme-batch amendment

`Tier0ExistingInputSet` becomes the parent set plus this amendment, its ledger,
and the five compatibility postimages. The parent plan and ledger remain in the
set. The existing Tier 0 schema does not change: `liveRecords` binds the five
live postimage `FileRecord`s, while `authorities` binds both package
generations. Reconstructed preimages are derived authority bound by this
amendment and are rederived during every historical check; they are not stored
in a new Tier 0 field. The five files are not `createdControls`,
`eligibleDestinations`, rollback targets, or theme changes.

The parent `APPLY_PATHS`, `themeBatchBoundary`, `allowedChanges`, overlay,
review packet, apply order, and rollback state machine remain unchanged:

1. `.streamlit/config.toml`
2. `app.py`
3. `ui/_design.py`
4. `requirements.txt`
5. `docs/ui-ux/quant-radar-ui-v2-ux1b-classification.json`

The amendment document and ledger join the supplemental authority projection.
The sequence 1 plan and ledger remain retained imported authorities.
Without changing any lifecycle schema key, every existing `replacementPlan`
field now binds this sequence 2 amendment, every `traceability` field binds its
sibling ledger, and the sequence 1 pair remains in `authorities`.

## Sequence 2 traceability ledger contract

The sibling ledger uses schema
`quant-radar-ui-ux-traceability/v3`. It is canonical JSON with sorted object
keys, compact separators, UTF-8 without BOM, no floats, and exactly one final
LF. Its exact path is
`docs/superpowers/plans/2026-07-24-quant-radar-ui-ux-ux1b-regression-compatibility-amendment.traceability.yaml`.
Duplicate or unknown keys, floats, NaN/Infinity, invalid UTF-8, non-NFC
strings, BOMs, alternate whitespace, missing/final-extra LF, undeclared IDs,
unsorted or duplicate edges, and asymmetric edges fail closed. Its exact
top-level key set is:

```text
schemaVersion,status,implementationStatus,testExecution,plan,requirements,
acceptance,implementation,tests,coverageBasisPoints,gaps,orphans
```

The fixed scalar/object values are:

- `status:"NOT_TESTED"`;
- `implementationStatus:"NOT_STARTED"`;
- `testExecution:{"executedAt":null,"results":[],"status":"NOT_RUN"}`;
- `plan` is the exact `{path,sha256,size}` artifact reference computed after
  this amendment's final bytes are frozen;
- `coverageBasisPoints:10000`;
- `gaps:[]`;
- `orphans:[]`.

The closed ordered identifier sets are:

- `requirements`:
  `CFR-001,CFR-002,CFR-003,REQ-001`;
- `acceptance`:
  `AC-COMPAT-001` through `AC-COMPAT-006`;
- `implementation`:
  `IMPL-001` through `IMPL-006`;
- `tests`:
  `TEST-001` through `TEST-006`.

Every requirement row has exactly
`id,acceptance,implementation,tests`; every acceptance row has exactly
`id,requirements,implementation,tests`; every implementation row has exactly
`id,requirements,acceptance,tests`; every test row has exactly
`id,requirements,acceptance,implementation`. All relation arrays are
nonempty, duplicate-free, and lexicographically sorted.

The following six rows are the complete relation source:

| Acceptance | Requirements | Implementation | Tests |
| --- | --- | --- | --- |
| `AC-COMPAT-001` | `REQ-001` | `IMPL-002,IMPL-003` | `TEST-001,TEST-002` |
| `AC-COMPAT-002` | `CFR-001,REQ-001` | `IMPL-002,IMPL-004` | `TEST-002` |
| `AC-COMPAT-003` | `CFR-001` | `IMPL-004` | `TEST-003` |
| `AC-COMPAT-004` | `CFR-002` | `IMPL-003,IMPL-005` | `TEST-004,TEST-006` |
| `AC-COMPAT-005` | `CFR-003` | `IMPL-005,IMPL-006` | `TEST-005,TEST-006` |
| `AC-COMPAT-006` | `CFR-002` | `IMPL-001,IMPL-003,IMPL-005` | `TEST-001,TEST-006` |

All other relation arrays are derived, not authored independently:

1. An identifier's `acceptance` array is every acceptance row containing it.
2. Its other relation arrays are the lexicographically sorted union of the
   corresponding columns over those acceptance rows.
3. All six bidirectional edge families
   requirement↔acceptance, requirement↔implementation, requirement↔test,
   acceptance↔implementation, acceptance↔test, and implementation↔test MUST
   be symmetric.
4. Every implementation↔test edge MUST share at least one acceptance row.
5. `coverageBasisPoints` is `10000` only when all four identifier sets equal
   the closed sets above, every relation is nonempty and symmetric, and
   `gaps`/`orphans` are both empty. Otherwise validation fails; no reduced
   coverage value is accepted.

The sequence 1 ledger remains validated by its frozen v2 contract. It is never
parsed as v3 and is never regenerated.

## Acceptance criteria

### `AC-COMPAT-001` — exact live boundary

Given the five retained source files, when sequence 2 authority is
reauthenticated, then all five postimage SHA-256, size, path, order, and mirror
mode values match, and any mutation or extra path fails.

### `AC-COMPAT-002` — exact reverse reconstruction

Given all five exact postimages, when the closed reverse edits run, then all
five exact preimages are produced; a missing, duplicate, reordered, or mutated
edit source fails before a historical claim is emitted.

### `AC-COMPAT-003` — historical digest

Given reconstructed preimages, the two absent historical verifier paths, and
the nine authenticated legacy selector records, when the frozen mirror encoder
runs, then the digest equals
`4eeb3629fbd83ef9e61f553cd3eae93e7b8ede4b925e45774ece99847dfce8a5`.

### `AC-COMPAT-004` — unchanged theme batch

Given sequence 2 authorization, when batch fixtures, reviews, application, or
rollback are validated, then their ordered path set remains the parent plan's
exact five paths and none of the compatibility files is writable.

### `AC-COMPAT-005` — real candidate regression

Given the accepted theme candidate and exact compatibility postimages, when
the candidate regression executes under its declared capability profiles, then
the sealed report contains 37 passed, zero failed, and zero missing rows.

### `AC-COMPAT-006` — sequence 2 authorization

Given the recovery document, when authorization is parsed, then it contains one
canonical V2 marker pair, integer `sequence:2`, exact amendment and ledger
artifact references, unchanged recovery ID and precedence, and no unknown key.

## Implementation checklist

- [ ] `IMPL-001`: Freeze this document, generate its canonical traceability
  ledger, review both, and publish the sequence 2 authorization body.
- [ ] `IMPL-002`: Add the exact five-row contract and reverse byte edits to
  `scripts/ui_ux_theme_handoff.py`.
- [ ] `IMPL-003`: Reauthenticate sequence 1 parent artifacts plus sequence 2
  package and expose both in Tier 0 authority inputs.
- [ ] `IMPL-004`: Build the historical projection only from reconstructed
  bytes, the exact two removals, and the nine selector substitutions.
- [ ] `IMPL-005`: Add positive, negative, mutation, and full regression tests
  to `scripts/test_ui_ux_theme_handoff.py`.
- [ ] `IMPL-006`: Run package validation, Python 3.10 AST, focused verifier,
  full verifier, and real `37/0/0` candidate regression gates.

## Test specification

| Test | Observable result |
| --- | --- |
| `TEST-001` | Sequence 2 package, canonical marker grammar, parent imports, and artifact hashes pass; recodings fail. |
| `TEST-002` | Five exact reverse patches reconstruct all preimages; each fragment/path/record mutation fails. |
| `TEST-003` | Reconstructed historical projection equals the frozen digest; direct substitution or partial reversal fails. |
| `TEST-004` | `APPLY_PATHS`, Make lifecycle target contract, batch changes, and rollback remain exact five-path contracts. |
| `TEST-005` | Candidate regression seals only a real `37/0/0` report using the compatibility postimages. |
| `TEST-006` | Full verifier passes with zero controlled missing-behavior and zero unexpected failures. |

## Traceability matrix

| Requirement | Acceptance | Implementation | Tests |
| --- | --- | --- | --- |
| `REQ-001` | `AC-COMPAT-001`, `AC-COMPAT-002` | `IMPL-002`, `IMPL-003`, `IMPL-004` | `TEST-001`, `TEST-002` |
| `CFR-001` | `AC-COMPAT-002`, `AC-COMPAT-003` | `IMPL-002`, `IMPL-004` | `TEST-002`, `TEST-003` |
| `CFR-002` | `AC-COMPAT-004`, `AC-COMPAT-006` | `IMPL-001`, `IMPL-003`, `IMPL-005` | `TEST-001`, `TEST-004`, `TEST-006` |
| `CFR-003` | `AC-COMPAT-005` | `IMPL-005`, `IMPL-006` | `TEST-005`, `TEST-006` |

## Risks and rollback

- A compatibility postimage drift is a contract failure, not permission to
  recalculate hashes.
- A reverse edit with zero or multiple matches is a contract failure.
- A sequence 2 package review finding requires new final document bytes,
  ledger regeneration, and authorization-body regeneration.
- Before Tier 0 publication, rollback of this amendment means restoring the
  sequence 1 authorization stanza and code constants only if their exact
  preimages remain available. The five compatibility patches remain ordinary
  dirty-worktree changes and MUST NOT be destructively reverted.
- After Tier 0 publication, only the parent lifecycle rollback rules apply.

## Review gates

- [x] Document scope, non-goals, exact rows, and parent imports are complete.
- [x] Every requirement has bidirectional acceptance, implementation, and test
  links in the sibling ledger.
- [x] All Appendix A forward patch hashes and sizes reproduce exactly.
- [x] The unique all-five reverse combination reproduces the historical digest.
- [x] No compatibility path appears in `APPLY_PATHS` or `allowedChanges`.
- [x] No High, Medium, blocking, runtime, destructive, or credential finding
  remains.

## Appendix A — exact authorized forward patches

The canonical bytes for each patch are the UTF-8 unified diff shown below,
including its final LF and no timestamps.

```diff
--- a/scripts/01_hard_filter.py
+++ b/scripts/01_hard_filter.py
@@ -39,11 +39,11 @@
     The repo cache is writable in this project and keeps the failure local.
     """
     try:
-        YF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
         cache = getattr(yf, "cache", None)
         setter = getattr(cache, "set_cache_location", None)
         if callable(setter):
             setter(str(YF_CACHE_DIR))
+        YF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
     except Exception as e:  # noqa: BLE001 - cache must never break the scan
         print(f"[hard_filter] yfinance cache setup skipped: {e}", file=sys.stderr)

```

```diff
--- a/scripts/momentum_options.py
+++ b/scripts/momentum_options.py
@@ -23,6 +23,7 @@
 from __future__ import annotations

 import math
+import sys
 from datetime import datetime
 from pathlib import Path

@@ -31,6 +32,10 @@
 # instance in-app; fall back to a flat/importlib load for CLI & test contexts.
 try:
     from scripts import options_analytics as _ana    # app / package context
+    # Direct script tests import the same source by its historical bare name.
+    # Keep both import spellings bound to one module when the repository root
+    # is present on PYTHONPATH, rather than executing the file twice.
+    sys.modules.setdefault("options_analytics", _ana)
 except ImportError:
     try:
         import options_analytics as _ana              # scripts/ on sys.path (CLI/tests)
```

```diff
--- a/scripts/test_ui_ux_components.py
+++ b/scripts/test_ui_ux_components.py
@@ -77,7 +77,6 @@
         "surface.panel": "#1a1f2b",
         "text.primary": "#e6e9ef",
         "text.secondary": "#8b93a7",
-        "interactive.primary": "#ef4444",
         "feedback.info": "#636efa",
         "feedback.success": "#00cc96",
         "feedback.warning": "#ffa15a",
@@ -91,6 +90,34 @@
         require(
             _design.COLOR_TOKENS[name] == expected,
             f"UX-1A changed an existing global/semantic token: {name}",
+        )
+
+    interaction = dict(_design.INTERACTIVE_TOKENS)
+    require(
+        interaction
+        in (
+            {
+                "interactive.primary": "#ef4444",
+                "interactive.hover": "#fb7185",
+                "interactive.disabled": "#6b7280",
+            },
+            {
+                "interactive.primary": "#2563eb",
+                "interactive.hover": "#1d4ed8",
+                "interactive.active": "#1e40af",
+                "interactive.accent": "#60a5fa",
+                "interactive.control": "#3b82f6",
+                "interactive.disabled": "#6b7280",
+            },
+        ),
+        "interaction tokens are neither the frozen UX-1A pretheme set nor the "
+        "accepted UX-1B semantic set",
+    )
+    if "interactive.active" in interaction:
+        require(
+            _design.COLOR_TOKENS["text.on-primary"] == "#ffffff"
+            and _design.COLOR_TOKENS["text.disabled"] == "#8b93a7",
+            "UX-1B interaction text roles differ",
         )

     try:
```

```diff
--- a/scripts/test_ui_ux_contract.py
+++ b/scripts/test_ui_ux_contract.py
@@ -1305,6 +1305,7 @@
     _validate_ux1b_forward_projection(normalized, current_inventory)
     accepted_without_site = copy.deepcopy(normalized)
     accepted_without_site["state"] = "accepted"
+    accepted_without_site["unsafe_html"]["trusted_static_theme_css"] = []
     _expect_assertion(
         lambda: _validate_ux1b_forward_projection(
             accepted_without_site, current_inventory
```

```diff
--- a/scripts/test_ui_ux_fixtures.py
+++ b/scripts/test_ui_ux_fixtures.py
@@ -980,34 +980,27 @@
         else:
             raise AssertionError("mismatched ownership marker was accepted")

-    with tempfile.TemporaryDirectory(
-        prefix=".surge-ux0-invalid-",
-        dir=ROOT / "ui",
-    ) as temp:
-        run_dir = Path(temp).resolve()
-        root = run_dir / "fixture-root"
-        root.mkdir()
-        calls = run_dir / "fixture-calls.json"
-        token = secrets.token_urlsafe(32)
-        (run_dir / fixtures.OWNERSHIP_MARKER).write_text(token, encoding="utf-8")
-        invalid = {
-            "QUANT_RADAR_UX0_FIXTURES": "1",
-            "QUANT_RADAR_UX0_FIXTURE_ROOT": str(root),
-            "QUANT_RADAR_UX0_CALLS_PATH": str(calls),
-            "QUANT_RADAR_UX0_RUN_TOKEN": token,
-            "QUANT_RADAR_UX0_FIXED_NOW": "2026-07-15T06:30:00Z",
-            "SURGE_RUNTIME_DIR": str(root),
-            "SURGE_CANDIDATE_OUTPUT_DIR": str(root / "candidates"),
-            "SURGE_AI_CHAT_DIR": str(root / "ai-chat"),
-            "TZ": "UTC",
-        }
-        try:
-            fixtures.validate_fixture_environment(invalid)
-        except fixtures.FixtureConfigurationError as exc:
-            assert "repository source" in str(exc).lower()
-            assert token not in str(exc)
-        else:
-            raise AssertionError("owned marker inside a repository source tree was accepted")
+    root = (ROOT / "ui").resolve()
+    calls = ROOT / "fixture-calls.json"
+    token = secrets.token_urlsafe(32)
+    invalid = {
+        "QUANT_RADAR_UX0_FIXTURES": "1",
+        "QUANT_RADAR_UX0_FIXTURE_ROOT": str(root),
+        "QUANT_RADAR_UX0_CALLS_PATH": str(calls),
+        "QUANT_RADAR_UX0_RUN_TOKEN": token,
+        "QUANT_RADAR_UX0_FIXED_NOW": "2026-07-15T06:30:00Z",
+        "SURGE_RUNTIME_DIR": str(root),
+        "SURGE_CANDIDATE_OUTPUT_DIR": str(root / "candidates"),
+        "SURGE_AI_CHAT_DIR": str(root / "ai-chat"),
+        "TZ": "UTC",
+    }
+    try:
+        fixtures.validate_fixture_environment(invalid)
+    except fixtures.FixtureConfigurationError as exc:
+        assert "repository source" in str(exc).lower()
+        assert token not in str(exc)
+    else:
+        raise AssertionError("fixture root inside repository source was accepted")


 def test_entrypoint_fails_before_streamlit_without_opt_in() -> None:
```
