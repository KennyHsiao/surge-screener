# Phase 4B/4C Frontend/Backend Separation Implementation

- **Status:** Implemented; verification complete
- **Date:** 2026-08-01
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Accepted scope:** Phase 4B AI Updates transitive separation, followed only
  after its gates pass by Phase 4C Crypto Universe API-only.

## Pre-change exact-byte receipt

The worktree already contains uncommitted Phase 3 and UX changes. These hashes
freeze the exact accepted inputs before either successor phase edits them; they
are evidence, not an instruction to restore files from Git.

| File | SHA-256 |
| --- | --- |
| `ui/_components.py` | `c654b1b4a9fd4be93525edb624d0d72d23ba3288df15a6caa59b54c7160d749b` |
| `ui/_design.py` | `0844c44dfc0b254f541ce7b9188cb71856e8549bcaaffea44db220c44a3be92d` |
| `ui/sys_ai_updates.py` | `3605e80a10ee5eb71cc0f72bdc68a106b3c16b59b9821a1ea85349a9e1e2a58b` |
| `ui/_read_api.py` | `04516567c4388e068b6dd41ee113bcb016861d43dcea5c75e568ca485f3fa000` |
| `api/artifacts.py` | `7a7a5fbfc82201e09f20bae0d47cc825def3aab3ca39b4c5903dbf53cfe6260e` |
| `api/models.py` | `c8dd54609e318ad3fb308aadc1091d14a550b8bbd9e51718f1f96cb30fcd8be0` |
| `api/main.py` | `ede9e96b67ad6a644988c49d59e175d10735b840fb95744033c0ec5ce2888396` |
| `scripts/test_ui_backend_boundary.py` | `311e18820dc87cb9148639b9b9bdb528db0fc34d4d99b9083e665fb9e3e8c74e` |
| `scripts/test_ui_ai_updates_api.py` | `ffc12477c58e9b30ef34bc24e835d3312fa79481f9dffe55188ea3d976c32149` |
| `scripts/test_ui_read_api.py` | `a780670d169847cad250ee608f41a048dd31b9b6f650003c0af8c84314036736` |
| `scripts/test_api.py` | `34ade127f600cf436d13a64814ad45ae6a9eed1e82798976476729817d4fe3af` |
| `docs/api/fastapi-endpoint-artifact-inventory.md` | `fc242df163e047190b63df01733ed4b865cc7f01d8dc6a3bd72c8fa3200c6ca2` |
| `docs/USER_GUIDE.md` | `1dedd6e3fe848aecb8c0dae10d7a1cc2c166ef7e9536eb37d2c4869c6c80849c` |

## Accepted execution gates

1. Phase 4B must remove only AI Updates' `_shared` edge, preserve the existing
   unsafe-HTML inventory, and prove the page's local dependency closure contains
   only the page, presentation modules, fixed client, and public models.
2. Phase 4C may start only after Phase 4B focused and boundary gates pass.
3. Crypto Universe must use one fixed strict endpoint and client, omit
   `fetch_error` and duplicate `symbols`, derive the TradingView download from
   validated `tv_symbol` rows, and never fall back to local files.
4. Existing writers, Schedules result readers, providers, deployment, and all
   other `_shared` consumers remain unchanged.

## Implemented outcome

### Phase 4B

- Declared `ui/_components.py` and `ui/_design.py` as a presentation island and
  added deterministic import/call and level-2 dependency guards.
- Added a native literal-text tag row and migrated AI Updates away from
  `_shared.chips_row` without moving or duplicating the historical unsafe-HTML
  sink.
- Froze the AI Updates local dependency closure to exactly `api/models.py`,
  `ui/_components.py`, `ui/_read_api.py`, and `ui/sys_ai_updates.py`.

### Phase 4C

- Added fixed `GET /api/v1/crypto/universe`, a strict public DTO and registry
  projection, and OpenAPI 1.6 contract coverage. Private `fetch_error` and the
  duplicate raw `symbols` array are validated at the source boundary but never
  published.
- Added a fixed, no-fallback client with the established loopback-only trust,
  `no-store`, media-type, no-redirect, no-proxy, deadline, 2 MiB retained-body,
  and strict-envelope checks.
- Replaced both Crypto Universe local reads with the API DTO. The TradingView
  download is derived only from validated `tv_symbol` rows; the writer and its
  sibling TXT output remain unchanged backend artifacts.
- Froze the Crypto Universe local dependency closure to exactly
  `api/models.py`, `ui/_components.py`, `ui/_read_api.py`, and
  `ui/crypto_universe.py`.

## Blocking finding closed during verification

The first real-artifact check correctly rejected three live Binance identifiers
containing Han characters. The writer preserves exchange identifiers exactly,
so an ASCII-only DTO would have made the current 527-row stale fallback
unavailable in production. The contract now permits bounded Unicode exchange
identifiers while still rejecting whitespace, controls, and the reserved
`:`, `.`, `/`, and `\\` separators. The exact `tv_symbol` derivation invariant
remains mandatory. The current `reports/crypto/universe_latest.json` now
validates as `ArtifactAvailable` with all 527 rows.

## Exact successor receipts

- UX diagnostic inventory: 171 -> 170 current sites. Two historical Crypto
  download payload sites were removed and one DTO-derived download payload site
  was added. Removal receipt:
  `(2, 240, d417bf1d29efcea747c379daf483d0c9d6b43cf008440ea7b45bd5b9315ea8e3)`;
  addition receipt:
  `(1, 120, 9e69b62d29bdc2e9338c55be8cb136f474bf33c5394bec3495b1f953e58d3cbf)`.
- UX fixture route ownership no longer assigns `reports/crypto` to the page.
  The exact per-render counter changed from `shared.json.read: 1` to
  `crypto_universe.load.execute: 1`.
- The shrinking direct `ui -> scripts` inventory remains 65 bindings. No new
  backend import was allowlisted; Phase 4B/C instead add exact level-2 closure
  checks. `_shared` importers decrease from the Phase 4A baseline of 34 to 32.

## Verification evidence

| Gate | Result |
| --- | --- |
| Phase 4B AI Updates | 17/17 passed |
| Crypto Universe API/client/page | 8/8 passed, including bounded Unicode exchange identifiers |
| Backend boundary | 8/8 passed |
| Native presentation components | 6/6 passed |
| API and static/generated OpenAPI parity | 44/44 passed |
| Fixed read clients | 12/12 passed |
| UX contract | 19/19 passed with exact successor receipts |
| UX fixture contract | 26/26 passed with API loader ownership |
| Dashboard navigation/static product contract | 52/52 passed |
| Full repository regression | `make test` passed through its final target |
| Static gates | compileall, tabnanny, whitespace, dependency/source scans passed |
| Real persisted Crypto artifact | available, source `crypto.universe`, as-of 2026-07-31, 527 rows |

Streamlit bare-mode warnings and deprecation warnings from unchanged pages were
present in the full log; they did not fail a gate and the migrated Crypto page
uses current `width="stretch"` arguments.

## Scope comparison

The actual diff matches the accepted Phase 4B/4C plan. The only unplanned code
adjustment was the necessary strict-contract correction for real bounded Unicode
Binance identifiers discovered by the production-artifact gate. No writer,
Schedules result reader, provider, deployment, runtime config, other `_shared`
consumer, mutation surface, or authentication boundary changed.

## Next plan: Phase 4D — Market Thesis latest API-only slice

1. Freeze the current Market Thesis route/model/page bytes and review the exact
   latest-forecast fields consumed by the UI. Keep validation summary and regime
   history as explicit sibling local reads in this phase.
2. Replace the open compatibility model with a strict bounded public latest DTO;
   preserve ready-over-regime-only same-day resolver semantics and project out
   source-only/private fields.
3. Add a fixed bounded client for the existing
   `GET /api/v1/market-context/market-thesis/latest` route with authoritative
   unavailable behavior and no local fallback.
4. Migrate only the page's latest-forecast resolver. Preserve writers, refresh
   actions, validation/history readers, navigation, and all unrelated
   `_shared` consumers.
5. Add fail-first API/client/page/boundary/navigation tests, bind any UX
   inventory change to an exact successor receipt, then run focused, real
   artifact, OpenAPI parity, static, and full repository gates.

Before execution, review this Phase 4D plan for blocking schema, provenance,
and scope issues. The queued Phase 4E candidate after it is the separate strict
Reversal/Oversold snapshot adoption; live Radar computation and position-bearing
Risk Guard data remain outside that public slice.
