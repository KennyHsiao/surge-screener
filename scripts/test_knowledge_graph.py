#!/usr/bin/env python3
"""Offline tests for the knowledge graph parser and tag merger."""

from __future__ import annotations

import tempfile
from pathlib import Path

import knowledge_graph as kg


def test_current_vault_shape() -> None:
    graph = kg.build_graph()
    nodes = {n["id"]: n for n in graph["nodes"]}
    assert "MOC" in nodes
    assert "Dim1" in nodes
    assert "bb_squeeze" in nodes
    assert "pan-poteshman-2006-option-volume" in nodes
    assert nodes["bb_squeeze"]["type"] == "factor"
    assert nodes["bb_squeeze"]["blocked"] is True
    assert nodes["bb_squeeze"]["status"] == "exploratory"
    assert any(e for e in graph["edges"] if e["source"] == "bb_squeeze" and e["target"] == "Dim1")


def test_unresolved_links_are_diagnostics() -> None:
    with tempfile.TemporaryDirectory() as d:
        vault = Path(d)
        (vault / "a.md").write_text(
            "---\nid: a\nnode_type: paper\ndimension: Dim1\n---\n[[missing]]\n",
            encoding="utf-8",
        )
        graph = kg.build_graph(vault)
        assert graph["nodes"][0]["id"] == "a"
        assert graph["diagnostics"]["unresolved_links"] == [{"source": "a", "target": "missing"}]


def test_kg_tags_preserve_custom_tags() -> None:
    text = (
        "---\n"
        "id: x\n"
        "node_type: factor\n"
        "dimension: Dim1\n"
        "status: seed\n"
        "tags: [manual, kg/status/old]\n"
        "---\n"
        "# x\n"
    )
    out = kg.update_kg_tags_in_text(text, {"blocked": True})
    assert "manual" in out
    assert "kg/status/old" not in out
    assert "kg/status/exploratory" in out
    assert "kg/block/blocked" in out


if __name__ == "__main__":
    test_current_vault_shape()
    test_unresolved_links_are_diagnostics()
    test_kg_tags_preserve_custom_tags()
    print("ok")
