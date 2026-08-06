# Phase 5C-5E Frontend/Backend Separation Plan

- **Status:** implemented, reviewed, and verified
- **Date:** 2026-08-04
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `docs/api/frontend-backend-separation-phase4z-5b-plan.md`

## Objective

Execute three narrow, independently reversible presentation-read migrations by
reusing existing strict clients and public DTOs:

1. Phase 5C makes only the Schedules Crypto Universe result summary API-only.
2. Phase 5D makes only the Schedules Theme Flow result summary API-only.
3. Phase 5E makes only the live Options Cockpit IV-history display and its
   displayed Rank/Percentile projection API-only.

No API route, DTO, OpenAPI, registry, producer, artifact writer, dependency,
deployment, service, authentication, or mutation change is required. Every
other Schedules result reader remains local. Theme analysis/refresh/status,
Options Cockpit demo data, `momentum_options` strategy provider and its existing
recording behavior, live option chain, quote fallback, EDGAR, Trade State,
quick picks, and all sibling actions remain on their current boundaries. No
pull, commit, push, deployment, service action, authentication change,
dependency change, or artifact rewrite is authorized.

## Entry baseline and frozen bytes

The Phase 4Z-5B receipt has no unresolved regression. Fresh entry suites pass:

- Crypto Universe 8/8
- Theme Flow 7/7
- IV history 15/15 (sandbox-external rerun required only for loopback socket)
- Schedules candidate 5/5
- Schedules Options Flow 4/4
- Options Cockpit scored 4/4
- Options Cockpit Options Flow 4/4
- Options Cockpit display 19/19
- backend boundary 16/16
- navigation 60/60

The parent receipt records API/OpenAPI 47/47, fixed read client 12/12,
deterministic fixtures 26/26, and complete `make test` exit 0.

Exact pre-change shared-target hashes are:

- `ui/sys_schedules.py`: `af5b35130bd48763df853af01c4d0d84aeba5841013cf1c24ed38e497d61b19d`
- `ui/options_cockpit.py`: `6516c08d3f43a81fd866e7716ea335d3880405ed542d886e80498d50549affde`
- `ui/_read_api.py`: `340bb0b07255c6123a734746252ea2365acaeb4109a95f5ba4d0f79fc69fe11f`
- backend boundary: `ac6eb7bdfc207c227bf1b9f699aa8078980b408e18fdae7c944579bb8e05d199`
- navigation: `c37044ad80396542cb44bff052cabc2227451c8de1ca93435b4d5c0ebdd74e15`
- fixture suite: `69a760601e640095c4829127eba8daaeb1466618cac02141b5f177bc8eade0b0`
- fixture helper: `5354a6a100bb8ca91da8bfe500ab75e4ba8718662e49bfd6c54da4b99ca4a6ae`
- `Makefile`: `b47a7d5c85b0c9152c0547b0dd760c49893c803807201727c744dcbb7fd044c0`
- user guide: `0e678449ed47381808943cc418673eeba3c51ce78e67cc66e30e01fb8b557215`
- endpoint inventory: `d3842d7b0c993ea9215bc2628a6a14bf03155d4dec4224a2d6fcaf20a9e068f0`

Selected source artifacts are frozen at:

- Crypto Universe: `b11e48fe93fb0c5fa23cbed2e6e4452889f493a5a60eceb00f3f05e4ee83b755`
- Theme Flow: `ba815778c542ff70ba9c826768049230d7a62b7482d0a47cb713df1f7b8ac4b7`
- NVDA IV-history verification sample: `559aff05bc823afb8c9e677e241b97a755c36cbc3255bae4160b4192aab5238e`
- ranked candidates: `ca85c80320db03bedb2175f12f54a7c5d08fe1671fc4da7255b16e1d1ea8b5ea`
- scored candidates: `6af375439dd470ea6f3c0bd985b3bfc16cbef62ae56791f270db36a1cff57b99`
- Money Flow: `96ed833428bc08f4845f49d0d03bda5be651d8caad4d8e5c3f94eeb9b3961731`
- Options Flow: `4c389cf370f6ecb4ba5d3d2f697eb5b3691a431be48690790f78bd94bd527599`

Re-hash each shared target immediately before its first edit. Changed bytes
require re-review rather than overwrite.

## Source and impact trace

### Phase 5C

`ui/sys_schedules.py::_latest_crypto_result()` currently reads
`reports/crypto/universe_latest.json` through `_shared.load_json()`. Its entire
display projection already exists in `CryptoUniverseData`: `date`, `count`,
`added`, `removed`, and `compared_to`. The fixed
`_read_api.load_crypto_universe()` client already validates the strict envelope,
metadata, provenance, size cap, authoritative unavailable state, and client
failure state.

### Phase 5D

`ui/sys_schedules.py::_latest_theme_flow_result()` currently reads
`reports/theme_flow_snapshot.json` through `_shared.load_json()`. Its display
needs only `as_of`, `generated_at`, and `len(themes)`, all present in the strict
`ThemeFlowData` snapshot returned by `_read_api.load_theme_flow()`. Theme Flow
analysis coherence and every refresh/status/action path are separate siblings.

### Phase 5E

`ui/options_cockpit.py::_live_provider()` currently performs two direct local
presentation reads of IV history: `iv_history.iv_percentile()` and
`_load_iv_series()` via `_shared.load_json()`. The existing strict
`_read_api.load_iv_history(ticker)` returns validated, normalized, bounded
`IvHistoryPoint` values. The existing pure
`scripts.iv_history.iv_percentile_from_series()` applies the same 40/252-day
calculation without I/O.

`scripts.momentum_options.analyze()` also owns an independent strategy-provider
read/write of IV history, and its result drives the provider verdict/checklist.
That provider is deliberately preserved by this narrow phase; changing it
would alter other callers, cache keys, recording semantics, and strategy
decisions. Therefore “Phase 5E API-only” refers only to the Cockpit-owned
IV-history series and displayed Rank/Percentile projection, not the entire
Options Cockpit page or the strategy provider.

## Blocking-issue review

No unresolved blocker remains after one review iteration.

- **5C — GO, risk 3.5/10:** the current strict Crypto DTO is a superset of the
  summary. Available-empty (`count=0`, empty universe/diffs) is authoritative.
  Unavailable and client failure must render distinct fixed safe summaries and
  never read the local artifact.
- **5D — GO, risk 3.6/10:** the current strict Theme snapshot is a superset of
  the summary. The DTO requires at least one theme, so there is no valid empty
  theme-board state. Unavailable and client failure remain distinct and cannot
  trigger refresh or analysis work from Schedules.
- **5E — CONDITIONAL GO closed, risk 5.1/10:** one fixed IV request is made per
  uncached live-provider execution and remains inside the existing 15-minute
  cockpit cache. Available-empty, unavailable, invalid-ticker, and client
  failure yield an empty validated series without local presentation fallback.
  Only an explicitly labeled `realized_vol_proxy` from the preserved provider
  may remain as the accumulating gauge; a provider value labeled as local
  `iv_history` must never substitute for a failed/empty API result. UI copy must
  distinguish authoritative unavailable, service failure, invalid ticker, and
  valid empty without exposing raw reasons. The provider verdict/checklist is
  explicitly outside the selected read slice and remains unchanged.

No route break, data-loss path, credential exposure, N+1 request, provider
migration, or new side effect is introduced. Overall weighted risk is 4.2/10.

## Accepted UI state behavior

### Schedules summaries

Both selected fetchers return the standard `(content, reason)` payload:

- available: preserve current summary fields and formatting;
- authoritative unavailable: fixed “資料目前無法使用” content plus sanitized
  reason for the existing state banner;
- client failure: fixed “服務目前無法使用” content plus sanitized reason;
- unexpected client result: fail soft as `invalid_envelope` service failure.

`render()` caches `crypto_universe` and `theme_flow` beside the existing
`candidate_refresh` and `options_flow` types, so duplicate visible cards reuse
one request per result type. Other result fetchers retain current behavior.

### Options Cockpit IV history

Add one immutable Cockpit IV-history state resolver and preserve the current
`CockpitData` contract with additive status/reason fields:

- API available/populated: convert validated points to the chart frame and
  calculate Rank/Percentile from the same in-memory points;
- API available/empty: authoritative zero points, accumulating state, no local
  fallback;
- API unavailable: empty series plus fixed data-unavailable copy;
- client failure: empty series plus fixed service-unavailable copy, with a
  dedicated safe response-too-large message;
- invalid ticker: empty series plus fixed invalid-ticker copy.

The API-derived percentile is used when the base is complete. While the API
base is accumulating, an explicitly labeled provider
`realized_vol_proxy` may continue to power the existing proxy gauge. A
provider-local IV-history percentile is never reused as fallback. Demo data and
its existing history remain unchanged.

## Test-first implementation order

1. Add `scripts/test_ui_schedules_crypto_api.py` for populated/empty,
   unavailable/failure, duplicate cards, one fixed client, and no local fallback.
2. Add `scripts/test_ui_schedules_theme_flow_summary_api.py` for available,
   unavailable/failure, duplicate cards, one fixed client, and isolation from
   analysis/refresh/status.
3. Add `scripts/test_ui_options_cockpit_iv_history_api.py` for all typed states,
   pure-calculator parity, no direct local read, one request per uncached live
   provider, provider-proxy gating, demo preservation, and Python 3.10 AST.
4. Add the three red suites to `Makefile`; confirm they fail against the current
   direct local readers.
5. Implement 5C and 5D in `ui/sys_schedules.py` and extend selected-result cache.
6. Implement 5E in `ui/options_cockpit.py` without changing the API/client or
   `scripts/momentum_options.py`.
7. Extend backend-boundary and navigation contracts for the three named slices.
8. Update deterministic fixture expectations only if measured route ownership
   changes; no speculative counter edits.
9. Update the user guide, endpoint/artifact inventory, this receipt, and skill
   journals. Keep the inventory wording narrow and explicit.

## Verification gates

Run, in order:

1. three new red-first/focused suites;
2. existing Crypto Universe, Theme Flow, IV-history, Schedules candidate,
   Schedules Options Flow, Cockpit scored/Options Flow/display regressions;
3. backend boundary, navigation, fixed read-client, API/OpenAPI, deterministic
   fixtures, deployment, and Docker contracts;
4. `compileall`, `tabnanny`, Python 3.10 AST, whitespace, and frozen artifact
   hashes;
5. complete `make test`.

Loopback/socket tests may require the already-approved sandbox-external rerun;
no test may be waived. After implementation, compare the actual diff against
this plan and review every changed hunk for regressions, missing states,
maintainability, and unexplained scope drift before claiming completion.

## Rollback

Each phase rolls back through only its named UI/test/doc hunks. No route,
schema, source artifact, producer, writer, deployment, or data migration is
involved. The three source artifacts and all unrelated dirty-worktree changes
must remain byte-stable.

## Subsequent audit after Phase 5E

Re-enumerate remaining local presentation reads before assigning Phase 5F and
later numbers. Trade State stays deferred until a dedicated aggregate/privacy/
ownership/source-coherence/authorization/mutation review. Prefer narrow reads
that reuse an existing strict endpoint; do not infer whole-page or whole-process
separation from the completed slice count.

## Implementation and verification receipt

Phase 5C-5E matches the accepted production scope:

- Schedules Crypto Universe and Theme Flow summaries each use one existing
  strict client result per result type and never fall back to the selected
  local artifact.
- Options Cockpit makes one strict IV-history read per uncached live-provider
  execution, calculates displayed Rank/Percentile from those validated points,
  and permits only an explicitly labeled realized-volatility proxy during
  accumulation. The independent `momentum_options` strategy provider, its
  verdict/checklist and recording, live chain, demo data, and all other sibling
  boundaries remain unchanged.
- No API route, DTO, OpenAPI surface, registry, producer, writer, dependency,
  authentication, deployment, service, or source artifact was changed.

Red-first proof was observed for all three new suites before implementation.
Final focused and regression results are:

- Schedules Crypto 4/4 and Theme Flow summary 4/4;
- Options Cockpit IV-history 6/6 and display 19/19;
- Schedules candidate 5/5 and Options Flow 4/4;
- Crypto Universe 8/8, Theme Flow 7/7, and IV history 15/15;
- backend boundary 17/17, navigation 61/61, fixed client 12/12,
  API/OpenAPI 47/47, deterministic fixtures 26/26, deployment 18/18, and
  Docker 11/11;
- UX forward contract 19/19 with its diagnostic inventory still exactly 167;
- `compileall`, `tabnanny`, whitespace, and complete `make test` exit 0.

The first complete test run exposed one intended Phase 5E diagnostic-site
replacement: correcting the old proxy caption created a new semantic site ID.
Review consolidated both states into one caption sink and added an exact
one-addition/one-removal receipt to `scripts/test_ui_ux_contract.py`; the final
full rerun passed. This is the only necessary divergence from the initially
listed test files. Post-diff review also moved the IV status alias before its
consumer and corrected copy so a missing proxy is never described as an active
realized-vol proxy. No unexplained scope drift remains.

All seven frozen artifacts remained byte-identical:

- Crypto Universe `b11e48fe...3b755`;
- Theme Flow `ba815778...c4b7`;
- NVDA IV history `559aff05...38e`;
- ranked `ca85c803...5ea` and scored `6af37543...b99` candidates;
- Money Flow `96ed8334...1731` and Options Flow `4c389cf3...7599`.

The audited next plan is
`docs/api/frontend-backend-separation-phase5f-5h-plan.md`. Trade State and all
private or mutating reads remain deferred.
