#!/usr/bin/env python3
"""Build a graph view of the knowledge vault.

The vault is plain Markdown for Obsidian. This module keeps the graph semantics
code-owned too: parse frontmatter + wikilinks, derive fail-closed node status,
and maintain machine tags under the reserved ``kg/`` prefix without clobbering
hand-written tags.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
VAULT = ROOT / "knowledge"

KG_TAG_PREFIX = "kg/"
DIM_ORDER = ("Dim1", "Dim2", "Dim3", "Dim4", "Dim5", "Dim6", "Dim7")

_WIKILINK_RE = re.compile(r"\[\[([^\]#|]+)(?:[#|][^\]]*)?\]\]")
_TAG_SAFE_RE = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclass(frozen=True)
class Card:
    id: str
    path: Path
    relpath: str
    frontmatter: dict[str, Any]
    body: str


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {}, text
    fm: dict[str, Any] = {}
    for line in lines[1:end]:
        if not line.strip() or ":" not in line:
            continue
        key, raw = line.split(":", 1)
        fm[key.strip()] = _parse_value(raw.strip())
    return fm, "\n".join(lines[end + 1:])


def _parse_value(raw: str) -> Any:
    if raw == "":
        return ""
    if raw in ("True", "true"):
        return True
    if raw in ("False", "false"):
        return False
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_parse_value(x.strip()) for x in inner.split(",")]
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def _format_value(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(str(x) for x in value) + "]"
    s = str(value)
    return f'"{s}"' if (":" in s or s.startswith(("[", "#")) or '"' in s) else s


def _frontmatter_bounds(lines: list[str]) -> tuple[int, int] | None:
    if not lines or lines[0].strip() != "---":
        return None
    try:
        return 0, next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None


def read_card(path: Path, vault: Path = VAULT) -> Card:
    text = path.read_text(encoding="utf-8")
    return parse_card_text(path, vault, text)


def parse_card_text(path: Path, vault: Path, text: str) -> Card:
    """Parse one already-bounded card without performing filesystem I/O."""

    fm, body = _split_frontmatter(text)
    cid = str(fm.get("id") or path.stem)
    return Card(cid, path, path.relative_to(vault).as_posix(), fm, body)


def _infer_type(path: Path, fm: dict[str, Any]) -> str:
    node_type = str(fm.get("node_type") or "").strip()
    if node_type:
        return node_type
    parent = path.parent.name
    if parent == "factors":
        return "factor"
    if parent == "papers":
        return "paper"
    if parent == "dimensions":
        return "dimension"
    if path.name == "MOC.md":
        return "moc"
    return "note"


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1")
    return bool(value)


def derive_status(fm: dict[str, Any], node_type: str) -> str:
    blocked = _to_bool(fm.get("blocked")) or _to_bool(fm.get("runway_blocked"))
    raw = str(fm.get("status") or "").strip().lower()
    verdict = str(fm.get("verdict") or "").strip().upper()
    if node_type == "factor" and blocked:
        return "exploratory"
    if raw:
        return raw
    if verdict == "VALIDATED":
        return "validated"
    if verdict:
        return verdict.lower()
    return "seed" if node_type in ("factor", "paper") else "index"


def _tag_part(value: Any) -> str:
    s = str(value or "").strip()
    s = _TAG_SAFE_RE.sub("-", s).strip("-")
    return s or "unknown"


def kg_tags_for_meta(meta: dict[str, Any]) -> list[str]:
    node_type = str(meta.get("node_type") or "note")
    status = derive_status(meta, node_type)
    tags = [f"kg/type/{_tag_part(node_type)}", f"kg/status/{_tag_part(status)}"]
    dim = meta.get("dimension")
    if dim:
        tags.append(f"kg/dim/{_tag_part(dim)}")
    horizon = meta.get("horizon")
    if horizon:
        tags.append(f"kg/horizon/{_tag_part(horizon)}")
    if _to_bool(meta.get("blocked")) or _to_bool(meta.get("runway_blocked")):
        tags.append("kg/block/blocked")
    runway = meta.get("runway_verdict")
    if runway:
        tags.append(f"kg/runway/{_tag_part(runway)}")
    return sorted(dict.fromkeys(tags))


def _tags_from_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        s = value.strip()
        if s.startswith("[") and s.endswith("]"):
            return _tags_from_value(_parse_value(s))
        return [x.strip() for x in re.split(r"[,\s]+", s) if x.strip()]
    return []


def merge_kg_tags(existing: Any, meta: dict[str, Any]) -> list[str]:
    custom = [t for t in _tags_from_value(existing) if not t.startswith(KG_TAG_PREFIX)]
    return sorted(dict.fromkeys(custom + kg_tags_for_meta(meta)))


def update_kg_tags_in_text(text: str, meta_updates: dict[str, Any] | None = None) -> str:
    lines = text.split("\n")
    bounds = _frontmatter_bounds(lines)
    if bounds is None:
        return text
    start, end = bounds
    fm, _body = _split_frontmatter(text)
    if meta_updates:
        fm.update(meta_updates)
    tags = merge_kg_tags(fm.get("tags"), fm)

    out = lines[:]
    seen = False
    for i in range(start + 1, end):
        key = out[i].split(":", 1)[0].strip() if ":" in out[i] else ""
        if key == "tags":
            out[i] = f"tags: {_format_value(tags)}"
            seen = True
            break
    if not seen:
        out.insert(end, f"tags: {_format_value(tags)}")
    return "\n".join(out)


def _wikilinks(text: str) -> list[str]:
    text = re.sub(r"(?s)```.*?```", " ", text)
    text = re.sub(r"`[^`]*`", " ", text)
    return sorted(dict.fromkeys(m.group(1).strip() for m in _WIKILINK_RE.finditer(text)))


def _node_label(card: Card, node_type: str) -> str:
    if node_type == "paper":
        title = str(card.frontmatter.get("title") or "").strip()
        return title or card.id
    if node_type == "dimension":
        return card.id
    if node_type == "moc":
        return "MOC"
    return card.id


def build_graph_from_cards(cards: list[Card]) -> dict[str, Any]:
    """Compile parsed cards without discovering or rereading source files."""

    by_id = {c.id: c for c in cards}
    by_stem = {c.path.stem: c for c in cards}

    nodes = []
    edges = []
    diagnostics = {"unresolved_links": [], "duplicate_ids": []}

    seen_ids: set[str] = set()
    for card in cards:
        node_type = _infer_type(card.path, card.frontmatter)
        if card.id in seen_ids:
            diagnostics["duplicate_ids"].append(card.id)
        seen_ids.add(card.id)
        blocked = _to_bool(card.frontmatter.get("blocked")) or _to_bool(card.frontmatter.get("runway_blocked"))
        nodes.append({
            "id": card.id,
            "label": _node_label(card, node_type),
            "type": node_type,
            "dimension": card.frontmatter.get("dimension") or "",
            "horizon": card.frontmatter.get("horizon") or "",
            "status": derive_status(card.frontmatter, node_type),
            "blocked": blocked,
            "url": card.frontmatter.get("url") or "",
            "path": card.relpath,
            "lift_exploratory": card.frontmatter.get("lift_exploratory") or "",
            "runway_verdict": card.frontmatter.get("runway_verdict") or "",
            "verdict_raw": card.frontmatter.get("verdict_raw") or "",
        })

    node_ids = {n["id"] for n in nodes}
    seen_edges: set[tuple[str, str, str]] = set()

    def add_edge(source: str, target: str, edge_type: str) -> None:
        if source == target or source not in node_ids or target not in node_ids:
            return
        key = (source, target, edge_type)
        if key not in seen_edges:
            edges.append({"source": source, "target": target, "type": edge_type})
            seen_edges.add(key)

    for card in cards:
        node_type = _infer_type(card.path, card.frontmatter)
        if node_type in ("factor", "paper") and card.frontmatter.get("dimension"):
            add_edge(card.id, str(card.frontmatter["dimension"]), "belongs_to_dimension")
        sources = card.frontmatter.get("sources") or []
        if isinstance(sources, list):
            for source in sources:
                add_edge(card.id, str(source), "evidence")
        for link in _wikilinks(card.body):
            target = by_id.get(link) or by_stem.get(link)
            if target is None:
                diagnostics["unresolved_links"].append({"source": card.id, "target": link})
                continue
            edge_type = "index_link" if node_type in ("moc", "dimension") else "references"
            add_edge(card.id, target.id, edge_type)

    diagnostics["unresolved_links"] = sorted(diagnostics["unresolved_links"], key=lambda x: (x["source"], x["target"]))
    diagnostics["duplicate_ids"] = sorted(dict.fromkeys(diagnostics["duplicate_ids"]))
    return {"nodes": nodes, "edges": edges, "diagnostics": diagnostics}


def build_graph(vault: Path = VAULT) -> dict[str, Any]:
    cards = [read_card(p, vault) for p in sorted(vault.rglob("*.md"))]
    return build_graph_from_cards(cards)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the knowledge graph JSON")
    ap.add_argument("--vault", default=str(VAULT))
    args = ap.parse_args()
    graph = build_graph(Path(args.vault))
    print(json.dumps(graph, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
