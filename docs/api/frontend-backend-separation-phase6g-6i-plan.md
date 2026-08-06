# Phase 6G-6I Frontend/Backend Separation Plan

- **Status:** implemented and verified
- **Date:** 2026-08-06
- **Branch:** `feat/frontend-backend-separation-phase3a`
- **Parent:** `docs/api/frontend-backend-separation-phase6d-6f-plan.md`

## Objective

Move only the Knowledge Graph page's persisted vault compilation read behind
the loopback read API:

1. **Phase 6G:** define a strict bounded public compiled-graph contract over the
   server-owned `knowledge/**/*.md` vault.
2. **Phase 6H:** add the fixed read endpoint and immutable bounded client.
3. **Phase 6I:** make `ui/knowledge_graph.py` consume one typed graph result per
   rerun with no local vault discovery or parser import. This becomes the
   fiftieth API-only slice.

The Markdown vault remains the source of truth. Course source Markdown,
frontmatter bodies/tags, image-derived notes outside the allowlisted vault,
ingest/seed/sync/tag-update commands, filesystem paths, arbitrary card detail,
and every write or refresh action remain local/Internal.

## Entry evidence and decisions

- `ui/knowledge_graph.py::_load_graph()` currently calls
  `scripts.knowledge_graph.build_graph()` directly and imports backend parser
  constants. The page also displays the absolute `kg.VAULT` path and receives a
  relative `path` plus unused external `url` on every node.
- The current vault has 43 Markdown cards, 43 nodes, 144 edges, five node types,
  three active statuses, and no unresolved or duplicate IDs. The source is
  small today, but `Path.rglob()` and per-file reads are unbounded and a single
  read error currently raises into Streamlit.
- The page renders only one aggregate graph. A separate catalog/detail endpoint
  would add unused enumeration and arbitrary-detail surface area, so this batch
  deliberately exposes one fixed compiled-graph endpoint only.
- The server may discover and compile only its configured vault root. The
  frontend never supplies a path, filename, ID, URL, or query. Compilation is a
  bounded read operation, not a persisted writer or refresh action.
- Public nodes omit `path`, `url`, card bodies, frontmatter, tags, and source
  filenames. The UI replaces the absolute vault-path panel with generic
  Obsidian guidance for the repository-relative `knowledge/` vault.

## API design

- **Method/path:** `GET /api/v1/knowledge/graph`
- **Source ID:** `knowledge.graph`
- **Envelope:** existing `available | unavailable` artifact envelope;
  expected source failures remain HTTP 200 and all responses use
  `Cache-Control: no-store`.
- **Metadata:** `asOf=null`, `generatedAt=null`; source cards have no canonical
  publication timestamp.
- **Data:**
  - `nodes`: unique source-ordered public nodes, maximum 500;
  - `edges`: unique source/target/type triples, maximum 5,000, with both ends
    present in `nodes`;
  - `diagnostics.unresolved_links`: bounded source/target ID pairs, maximum
    1,000;
  - `diagnostics.duplicate_ids`: must be empty for a publishable graph.
- **Node allowlist:** `id`, `label`, `type`, `dimension`, `horizon`, `status`,
  `blocked`, `lift_exploratory`, `runway_verdict`, and `verdict_raw`, with exact
  enum/text/finite-number bounds and blocked/status parity.
- **Edge allowlist:** `source`, `target`, and one of
  `belongs_to_dimension | evidence | references | index_link`.
- **Source resource bounds:** at most 500 direct/recursive Markdown cards, 256
  directories, and 2,000 total directory entries; no symlinked vault,
  directory, or card; at most 256 KiB per card and 8 MiB aggregate UTF-8 source
  bytes. Missing vault is `missing`; unreadable/symlinked inputs are
  `unreadable`; malformed, duplicate, oversized, traversal-limit, or
  incoherent graphs are `invalid_shape`. No partial graph or previous-result
  fallback is returned.
- **Client bounds:** fixed `127.0.0.1:8000` URL, one-second whole-request
  deadline, 2 MiB decoded-body cap, strict JSON/no-store/source/metadata/model
  validation, immutable outcomes, and no negative cache.

The operation is additive under `/api/v1`. The static and generated OpenAPI
documents advance together from `1.19.0-draft` to `1.20.0-draft`. Loopback
peer/Host validation and the no-CORS default remain unchanged; no auth,
dependency, service, Compose, or deployment topology change is required.

## Phase execution

### Phase 6G — fail-first source and public-model contract

1. Freeze the parser/source families and add fail-first tests for missing,
   empty, unreadable, invalid UTF-8, symlink, per-file/card-count/aggregate caps,
   malformed frontmatter-derived fields, duplicate IDs, dangling edges,
   duplicate edges, diagnostics bounds, privacy projection, and immediate
   recovery.
2. Add strict node, edge, diagnostics, graph, and envelope DTOs in
   `api/models.py`.
3. Extract a behavior-preserving pure `parse-card-text` / `build-from-cards`
   core in `scripts/knowledge_graph.py`; keep the existing local
   `build_graph(vault)` entry point delegating to that core for writer and test
   compatibility.
4. Add a bounded fixed-vault reader/compiler adapter in `api/artifacts.py`.
   It performs one capped, symlink-rejecting traversal and bounded byte read,
   then calls only the pure parser core. It must never delegate back to
   `build_graph(vault)` or perform a second filesystem scan. Do not add a path
   parameter or modify ingest/sync/tag writers.
5. Project out paths, URLs, bodies, frontmatter, tags, and arbitrary fields
   before validating the public DTO.

### Phase 6H — fixed endpoint and client

1. Add `GET /api/v1/knowledge/graph` to `api/main.py` with exact generated
   `available`, `empty`, and `unavailable` examples, safe logging, no-store, and
   dependency-free operation metadata.
2. Add the matching static operation/schemas/examples and bump both OpenAPI
   versions once to `1.20.0-draft`.
3. Add frozen `KnowledgeGraphApiAvailable | ApiUnavailable | ApiFailure`
   outcomes and `load_knowledge_graph()` to `ui/_read_api.py` with the complete
   failure vocabulary, 2 MiB cap, strict metadata parity, deadline, recovery,
   and Python 3.10 compatibility.

### Phase 6I — API-only presentation

1. Replace `_load_graph()` with exactly one `load_knowledge_graph()` call per
   rerun. Available-empty remains authoritative; unavailable/failure shows
   fixed safe guidance and never calls the local compiler.
2. Keep filtering, focus, layout, chart modes, metrics, table, diagnostics,
   accessible control state, and Plotly behavior as presentation-only logic.
3. Replace `kg.DIM_ORDER` with a frontend presentation constant and remove the
   `scripts.knowledge_graph` import, `kg.build_graph`, `kg.VAULT`, node path
   hover/table fields, and every local source fallback.
4. Update deterministic fixtures and selection-control tests to inject the
   typed client result while preserving exact one-load counter behavior.

## Affected files

- Parser/contract/server: `scripts/knowledge_graph.py`, `api/models.py`,
  `api/artifacts.py`, `api/main.py`,
  `docs/api/quant-radar-v1.openapi.yaml`
- Client/consumer: `ui/_read_api.py`, `ui/knowledge_graph.py`
- Focused/global tests: a new Knowledge Graph API/client/page suite,
  `scripts/test_api.py`, `scripts/test_ui_backend_boundary.py`,
  `scripts/test_dashboard_navigation.py`, Knowledge Graph parser and accessible
  control tests, deterministic fixture suites, and UX contracts only where the
  exact rendered diagnostic inventory changes
- Documentation/receipts: `Makefile`, `docs/USER_GUIDE.md`,
  `docs/api/fastapi-endpoint-artifact-inventory.md`, `.agents/gateway.md`,
  `.agents/builder.md`, and exactly one combined `.agents/PROJECT.md` row

The parser module changes only to expose a pure core while preserving the
existing local `build_graph(vault)` behavior. No source Markdown, image note,
ingest/seed/sync/tag writer, provider, prompt, LLM/Codex path, dependency,
service, deployment, schedule, or mutation file is planned to change.

## Verification gates

- Focused red-to-green source/model/route/OpenAPI/client/renderer/privacy suite.
- Existing parser, ingest, seed, sync, Knowledge Graph layout/control, backend
  boundary, navigation, deterministic fixture, and UX inventory suites.
- API/OpenAPI, shared fixed client, deployment, and Docker contract suites.
- Python 3.10 AST, compileall, tabnanny, YAML/static-version parity,
  `git diff --check`, source/writer hash preservation, and complete `make test`.
- Post-implementation diff-to-plan comparison and review for runtime defects,
  privacy regression, unbounded reads, local fallback, missing tests, and scope
  drift before completion is claimed.

## Blocking-issue review

No unresolved blocking issue remains after three review iterations.

- **Iteration 1:** rejected catalog/detail and arbitrary node-ID designs because
  the current page consumes one aggregate and does not render card bodies.
  Selected one fixed aggregate endpoint and an allowlisted path-free node DTO.
- **Iteration 2:** closed unbounded `rglob`, symlink, per-file/aggregate size,
  duplicate-ID/edge, dangling-edge, parser exception, metadata, response-cap,
  negative-cache, fixture, and absolute-path disclosure gaps. Compilation stays
  a read-only server adapter; all source and writer workflows remain unchanged.
- **Iteration 3:** found that calling the existing `build_graph(vault)` after
  bounded file selection would silently re-run an unbounded `rglob()` and
  reread every card. Amended the plan to cap directories and all traversal
  entries, extract a behavior-preserving pure parser/build core, and prohibit a
  second filesystem scan. Parser compatibility and source/writer hash gates
  make this amendment verifiable.

Final verdict: **GO** for Phase 6G-6I after Phase 6A-6F is closed.

## Implementation closure

- Added the bounded single-scan compiler, strict path-free graph projection,
  fixed no-store endpoint/client, and one-result API-only Knowledge Graph page.
- Focused public-resource coverage passed 8/8; API 47/47, shared client 12/12,
  boundary 23/23, navigation 66/66, UX contract 19/19 with the exact Phase 6I
  removal receipt, fixtures 26/26, deploy 18/18, Docker 11/11, parser and
  Python/static gates, and complete `make test` all passed.
- The related Knowledge Graph figure/view/label accessibility checks passed.
  The separate frozen accessibility authority remains at its known 24/27 due
  only to pre-existing capture-stack and Options Cockpit selector baselines;
  those authorities were not changed or re-signed.
- Actual scope matches the accepted plan. No source Markdown, writer, provider,
  credential, dependency, deployment topology, or local fallback changed.

## Following queue

Phase 6J-6L should audit only the public Watchlist taxonomy and Influencer
roster reads. Private IBKR/watchlist/reconciliation data, live social lookup,
roster edits, approvals, and every writer remain Internal/Deferred until a
separate plan is reviewed and accepted.
