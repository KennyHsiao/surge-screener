# Knowledge Vault

This folder is an Obsidian-compatible vault for the factor knowledge network.
It is also read by Quant Radar's `知識網路` dashboard page.

Integration style: native Obsidian Markdown. The repo does not depend on an
Obsidian plugin or a proprietary graph export. Obsidian reads the same `[[links]]`
and `kg/` tags that the dashboard parser reads.

## Open In Obsidian

1. Open Obsidian.
2. Choose **Open folder as vault**.
3. Select this repo's `knowledge/` folder.
4. Open `MOC.md` first, then use Graph View or Local Graph.

No community plugin is required. The graph is built from standard `[[wikilinks]]`
and YAML frontmatter tags.

## Useful Graph Filters

Use these in Obsidian Graph View's search/filter box:

- `tag:#kg/type/factor` — show factor cards.
- `tag:#kg/type/paper` — show paper cards.
- `tag:#kg/status/exploratory` — show non-actionable validation results.
- `tag:#kg/block/blocked` — show factors blocked by the fail-closed gate.
- `tag:#kg/dim/Dim1` — show one dimension.

Recommended workflow:

- Start from `MOC.md` for the full map.
- Open a factor card and use Local Graph depth 1 to see its papers and dimension.
- Use the Quant Radar `知識網路` page for the curated validation-decision graph.
  The default `星雲圖` view mirrors the Obsidian graph style with deterministic
  clusters, while `驗證泳道` keeps the dimension → factor → paper audit path.
- Use Obsidian Graph View when you want the free-form research map from the same
  vault files.
- Treat any `kg/block/blocked` or `kg/status/exploratory` factor as research-only,
  even if the prose contains raw historical lift numbers.

## How The Vault Is Maintained

- `scripts/knowledge_seed.py` creates factor, paper, dimension, and MOC cards.
- `scripts/knowledge_ingest.py <paper-url>` adds a paper card from fetched text.
- `scripts/knowledge_sync.py --lift .../factor_lift.json` writes validation
  state back into factor cards.
- `scripts/knowledge_runway_sync.py` writes ATR-normalized runway checks.

The reserved `kg/` tag prefix is code-owned. Hand-written tags are preserved, but
do not add custom meanings under `kg/`.
