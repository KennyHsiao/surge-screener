#!/usr/bin/env python3
"""Focused Phase 6G-6L public-resource API and UI-boundary tests."""

from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import yaml
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.artifacts import (  # noqa: E402
    read_influencer_roster,
    read_knowledge_graph,
    read_theme_taxonomy,
)
from api.main import create_app  # noqa: E402
from api.models import ArtifactAvailable  # noqa: E402
from scripts import knowledge_graph as graph_engine  # noqa: E402
from ui import _read_api, influencers, knowledge_graph, watchlist_categorize  # noqa: E402


def _write_graph(vault: Path) -> None:
    (vault / "dimensions").mkdir(parents=True)
    (vault / "factors").mkdir(parents=True)
    (vault / "dimensions" / "Dim1.md").write_text(
        "---\nid: Dim1\nnode_type: dimension\n---\n# Dim1\n",
        encoding="utf-8",
    )
    (vault / "factors" / "breakout.md").write_text(
        "---\nid: breakout\nnode_type: factor\ndimension: Dim1\n"
        "horizon: mid\nblocked: true\nlift_exploratory: 2.1\n"
        "runway_verdict: exploratory\nverdict_raw: VALIDATED\n"
        "url: https://private.example/card\n---\n[[Dim1]]\n",
        encoding="utf-8",
    )


def _taxonomy(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "_note": "private maintainer note",
                "themes": {"AI": "Artificial intelligence", "Energy": "Power"},
            }
        ),
        encoding="utf-8",
    )


def _roster(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "_note": "private maintainer note",
                "categories_order": ["Macro"],
                "influencers": [
                    {
                        "handle": "MacroWatcher",
                        "name": "Macro Watcher",
                        "category": "Macro",
                        "market": "US",
                        "url": "https://x.com/MacroWatcher",
                    },
                    {
                        "handle": "ChainSignals",
                        "category": "Crypto",
                        "market": "CRYPTO",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def _response_transport(result: object) -> httpx.MockTransport:
    body = result.model_dump_json(by_alias=True).encode("utf-8")

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=body,
            headers={"Content-Type": "application/json", "Cache-Control": "no-store"},
            request=request,
        )

    return httpx.MockTransport(handler)


def test_knowledge_graph_reader_is_bounded_pure_and_private() -> None:
    with tempfile.TemporaryDirectory() as directory:
        vault = Path(directory) / "knowledge"
        _write_graph(vault)
        local = graph_engine.build_graph(vault)
        cards = [
            graph_engine.read_card(path, vault)
            for path in sorted(vault.rglob("*.md"))
        ]
        if graph_engine.build_graph_from_cards(cards) != local:
            raise AssertionError("pure graph core changed local parser semantics")
        with patch.object(
            graph_engine,
            "build_graph",
            side_effect=AssertionError("bounded API delegated to unbounded scan"),
        ):
            result = read_knowledge_graph(vault)
        if not isinstance(result, ArtifactAvailable):
            raise AssertionError(result)
        payload = result.data.model_dump(mode="json")
        serialized = json.dumps(payload)
        if "path" in serialized or "private.example" in serialized:
            raise AssertionError(serialized)
        if len(payload["nodes"]) != 2 or not payload["edges"]:
            raise AssertionError(payload)


def test_knowledge_graph_fail_soft_caps_symlinks_and_recovers() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        vault = root / "knowledge"
        if read_knowledge_graph(vault).reason != "missing":
            raise AssertionError("missing vault reason drift")
        _write_graph(vault)
        bad = vault / "factors" / "bad.md"
        bad.write_bytes(b"\xff")
        if read_knowledge_graph(vault).reason != "invalid_shape":
            raise AssertionError("invalid UTF-8 did not fail soft")
        bad.unlink()
        if not read_knowledge_graph(vault).available:
            raise AssertionError("valid source did not recover immediately")
        outside = root / "outside.md"
        outside.write_text("# outside", encoding="utf-8")
        link = vault / "linked.md"
        link.symlink_to(outside)
        if read_knowledge_graph(vault).reason != "unreadable":
            raise AssertionError("symlinked card was accepted")


def test_taxonomy_and_roster_projection_validation_and_privacy() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        taxonomy_path = root / "themes.json"
        roster_path = root / "influencers.json"
        _taxonomy(taxonomy_path)
        _roster(roster_path)
        taxonomy = read_theme_taxonomy(taxonomy_path)
        roster = read_influencer_roster(roster_path)
        if not taxonomy.available or not roster.available:
            raise AssertionError((taxonomy, roster))
        if [item.name for item in taxonomy.data.themes] != ["AI", "Energy"]:
            raise AssertionError(taxonomy.data)
        if roster.data.categories != ["Macro", "Crypto"]:
            raise AssertionError(roster.data)
        serialized = roster.model_dump_json(by_alias=True)
        if "private maintainer" in serialized or "_note" in serialized:
            raise AssertionError(serialized)

        duplicate = json.loads(roster_path.read_text(encoding="utf-8"))
        duplicate["influencers"].append(dict(duplicate["influencers"][0]))
        roster_path.write_text(json.dumps(duplicate), encoding="utf-8")
        if read_influencer_roster(roster_path).reason != "invalid_shape":
            raise AssertionError("duplicate market/handle was accepted")


def test_fixed_routes_are_no_store_and_get_does_not_seed_roster() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        vault = root / "knowledge"
        taxonomy_path = root / "themes.json"
        roster_path = root / "missing-roster.json"
        _write_graph(vault)
        _taxonomy(taxonomy_path)
        app = create_app(
            knowledge_vault=vault,
            theme_taxonomy_path=taxonomy_path,
            influencer_roster_path=roster_path,
        )
        with patch("api.main._is_loopback_peer", return_value=True):
            with TestClient(app) as client:
                responses = [
                    client.get(path, headers={"Host": "127.0.0.1"})
                    for path in (
                        "/api/v1/knowledge/graph",
                        "/api/v1/watchlists/theme-taxonomy",
                        "/api/v1/social/influencers",
                    )
                ]
        if [response.status_code for response in responses] != [200, 200, 200]:
            raise AssertionError([(response.status_code, response.text) for response in responses])
        if any(response.headers.get("cache-control") != "no-store" for response in responses):
            raise AssertionError([response.headers for response in responses])
        if responses[-1].json()["reason"] != "missing" or roster_path.exists():
            raise AssertionError("roster GET seeded or rewrote the missing source")


def test_immutable_clients_validate_metadata_and_recover_without_cache() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        vault = root / "knowledge"
        taxonomy_path = root / "themes.json"
        roster_path = root / "influencers.json"
        _write_graph(vault)
        _taxonomy(taxonomy_path)
        _roster(roster_path)
        server_results = (
            read_knowledge_graph(vault),
            read_theme_taxonomy(taxonomy_path),
            read_influencer_roster(roster_path),
        )
        client_results = (
            _read_api.load_knowledge_graph(transport=_response_transport(server_results[0])),
            _read_api.load_theme_taxonomy(transport=_response_transport(server_results[1])),
            _read_api.load_influencer_roster(transport=_response_transport(server_results[2])),
        )
        expected = (
            _read_api.KnowledgeGraphApiAvailable,
            _read_api.ThemeTaxonomyApiAvailable,
            _read_api.InfluencerRosterApiAvailable,
        )
        if any(not isinstance(value, kind) for value, kind in zip(client_results, expected)):
            raise AssertionError(client_results)
        try:
            client_results[0].graph = client_results[0].graph  # type: ignore[misc]
        except FrozenInstanceError:
            pass
        else:
            raise AssertionError("client outcome is mutable")

        invalid = server_results[0].model_copy(deep=True)
        invalid.meta.source_id = "wrong.source"
        failed = _read_api.load_knowledge_graph(transport=_response_transport(invalid))
        if failed != _read_api.KnowledgeGraphApiFailure("invalid_envelope"):
            raise AssertionError(failed)
        recovered = _read_api.load_knowledge_graph(
            transport=_response_transport(server_results[0])
        )
        if not isinstance(recovered, _read_api.KnowledgeGraphApiAvailable):
            raise AssertionError("client negative-cached a prior failure")


def test_ui_helpers_use_api_only_and_preserve_manual_roster_fields() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        vault = root / "knowledge"
        taxonomy_path = root / "themes.json"
        roster_path = root / "influencers.json"
        _write_graph(vault)
        _taxonomy(taxonomy_path)
        _roster(roster_path)
        graph_result = _read_api.KnowledgeGraphApiAvailable(
            read_knowledge_graph(vault).data
        )
        taxonomy_result = _read_api.ThemeTaxonomyApiAvailable(
            tuple(read_theme_taxonomy(taxonomy_path).data.themes)
        )
        roster_result = _read_api.InfluencerRosterApiAvailable(
            read_influencer_roster(roster_path).data
        )
        with patch.object(_read_api, "load_knowledge_graph", return_value=graph_result):
            graph = knowledge_graph._load_graph()
        with patch.object(_read_api, "load_theme_taxonomy", return_value=taxonomy_result):
            taxonomy, available = watchlist_categorize._load_taxonomy()
        with (
            patch.object(_read_api, "load_influencer_roster", return_value=roster_result),
            patch.object(influencers._shared, "load_json", side_effect=AssertionError("local fallback")),
        ):
            api_roster = influencers.load_roster(api_only=True)
            us_rows = influencers.for_market("US", api_only=True)
        if graph is None or taxonomy != {"AI": "Artificial intelligence", "Energy": "Power"} or not available:
            raise AssertionError((graph, taxonomy, available))
        if api_roster is None or api_roster["influencers"][0].get("placeholder") is not None:
            raise AssertionError(api_roster)
        if [row["handle"] for row in us_rows] != ["MacroWatcher"]:
            raise AssertionError(us_rows)


def test_page_consumers_load_once_and_fail_without_local_fallback() -> None:
    empty_roster = _read_api.InfluencerRosterApiAvailable(
        read_influencer_roster(ROOT / "content" / "influencers.json").data
    )
    influencer_st = MagicMock()
    with (
        patch.object(influencers, "st", influencer_st),
        patch.object(
            influencers._read_api,
            "load_influencer_roster",
            return_value=empty_roster,
        ) as roster_load,
        patch.object(influencers, "_render_delete_undo"),
        patch.object(influencers, "_render_roster_health"),
        patch.object(influencers, "_render_search_add_console"),
        patch.object(influencers, "_render_roster_table_console"),
        patch.object(influencers, "_render_roster_editor"),
    ):
        influencers.render()
    if roster_load.call_count != 1:
        raise AssertionError(roster_load.call_count)

    with (
        patch.object(influencers, "st", influencer_st),
        patch.object(
            influencers._read_api,
            "load_influencer_roster",
            return_value=_read_api.InfluencerRosterApiUnavailable("missing"),
        ) as unavailable_load,
        patch.object(
            influencers._shared,
            "load_json",
            side_effect=AssertionError("unavailable page used local fallback"),
        ),
    ):
        influencers.render()
    if unavailable_load.call_count != 1:
        raise AssertionError(unavailable_load.call_count)

    watch_st = MagicMock()
    with (
        patch.object(watchlist_categorize, "st", watch_st),
        patch.object(
            watchlist_categorize._read_api,
            "load_theme_taxonomy",
            return_value=_read_api.ThemeTaxonomyApiUnavailable("missing"),
        ) as taxonomy_load,
        patch.object(watchlist_categorize, "_render_tv_input", return_value=[]),
        patch.object(watchlist_categorize, "_render_ibkr_inputs", return_value={}),
    ):
        watchlist_categorize.render()
    if taxonomy_load.call_count != 1:
        raise AssertionError(taxonomy_load.call_count)

    graph_st = MagicMock()
    with (
        patch.object(knowledge_graph, "st", graph_st),
        patch.object(
            knowledge_graph._read_api,
            "load_knowledge_graph",
            return_value=_read_api.KnowledgeGraphApiUnavailable("missing"),
        ) as graph_load,
    ):
        knowledge_graph.render()
    if graph_load.call_count != 1:
        raise AssertionError(graph_load.call_count)


def test_openapi_static_and_generated_public_surface_are_in_parity() -> None:
    static = yaml.safe_load(
        (ROOT / "docs" / "api" / "quant-radar-v1.openapi.yaml").read_text(
            encoding="utf-8"
        )
    )
    app = create_app()
    generated = app.openapi()
    routes = {
        "/api/v1/knowledge/graph": ("getKnowledgeGraph", "KnowledgeGraphResponse"),
        "/api/v1/watchlists/theme-taxonomy": ("getThemeTaxonomy", "ThemeTaxonomyResponse"),
        "/api/v1/social/influencers": ("getInfluencerRoster", "InfluencerRosterResponse"),
    }
    if (
        static["info"]["version"] != "1.23.0-draft"
        or generated["info"]["version"] != "1.23.0-draft"
    ):
        raise AssertionError((static["info"], generated["info"]))
    for route, (operation_id, response_name) in routes.items():
        for document in (static, generated):
            operation = document["paths"][route]["get"]
            if operation["operationId"] != operation_id or operation.get("parameters") not in (None, []):
                raise AssertionError((route, operation))
            if set(operation["responses"]) != {"200", "500"}:
                raise AssertionError((route, operation["responses"]))
        generated_examples = generated["paths"][route]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["examples"]
        static_examples = static["components"]["responses"][response_name]["content"][
            "application/json"
        ]["examples"]
        if static_examples != generated_examples:
            raise AssertionError((route, static_examples, generated_examples))


TESTS = (
    test_knowledge_graph_reader_is_bounded_pure_and_private,
    test_knowledge_graph_fail_soft_caps_symlinks_and_recovers,
    test_taxonomy_and_roster_projection_validation_and_privacy,
    test_fixed_routes_are_no_store_and_get_does_not_seed_roster,
    test_immutable_clients_validate_metadata_and_recover_without_cache,
    test_ui_helpers_use_api_only_and_preserve_manual_roster_fields,
    test_page_consumers_load_once_and_fail_without_local_fallback,
    test_openapi_static_and_generated_public_surface_are_in_parity,
)


if __name__ == "__main__":
    failures = 0
    for test in TESTS:
        try:
            test()
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  FAIL {test.__name__}: {type(exc).__name__}: {exc}")
        else:
            print(f"  PASS {test.__name__}")
    print(f"\n{len(TESTS) - failures}/{len(TESTS)} passed")
    raise SystemExit(1 if failures else 0)
