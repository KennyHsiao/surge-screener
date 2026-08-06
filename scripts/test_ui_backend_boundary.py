#!/usr/bin/env python3
"""Prevent growth of direct Streamlit-to-backend implementation imports."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
UI_DIR = ROOT / "ui"
LOCAL_PACKAGES = frozenset({"api", "ui"})
FORBIDDEN_TRANSITIVE_IMPORTS = (
    "api.artifacts",
    "api.main",
    "duckdb",
    "os",
    "pandas",
    "pathlib",
    "polars",
    "pyarrow",
    "scripts",
    "subprocess",
    "yfinance",
)
FORBIDDEN_IO_CALLS = frozenset({
    "connect",
    "exists",
    "glob",
    "iterdir",
    "open",
    "read_bytes",
    "read_text",
    "rglob",
    "unlink",
    "write_bytes",
    "write_text",
})

# Temporary migration inventory. Removing entries is allowed; adding entries is
# a boundary regression and must instead be implemented through an HTTP API.
LEGACY_SCRIPT_IMPORTS = frozenset(
    {
        ("ui/_candidate_controls.py", "scripts.candidate_pipeline_controls.CandidateRunParams"),
        ("ui/_candidate_controls.py", "scripts.candidate_pipeline_controls.RUN_MODE_LABELS"),
        ("ui/_candidate_controls.py", "scripts.candidate_pipeline_controls.launch_background"),
        ("ui/_candidate_controls.py", "scripts.candidate_pipeline_controls.read_pending_codex_request"),
        ("ui/_candidate_controls.py", "scripts.candidate_pipeline_controls.refresh_codex_auth_status"),
        ("ui/_candidate_controls.py", "scripts.candidate_pipeline_controls.resume_pending_codex_run"),
        ("ui/_shared.py", "scripts.artifact_loader.ArtifactAvailable"),
        ("ui/_shared.py", "scripts.artifact_loader.load_json_artifact"),
        ("ui/_shared.py", "scripts.analyst_free"),
        ("ui/_shared.py", "scripts.runtime_paths.CANDIDATE_OUTPUT_DIR"),
        ("ui/_shared.py", "scripts.runtime_paths.candidate_output_path"),
        ("ui/_shared.py", "scripts.sector_flow"),
        ("ui/_shared.py", "scripts.theme_flow"),
        ("ui/ai_chat.py", "scripts.ai_chat_assistant"),
        ("ui/ai_chat.py", "scripts.ai_chat_store"),
        ("ui/analytics_db.py", "scripts.analytics_checks"),
        ("ui/analytics_db.py", "scripts.analytics_store"),
        ("ui/analytics_db.py", "scripts.data_source_refresh"),
        ("ui/analytics_db.py", "scripts.fundamental_metrics_store"),
        ("ui/analytics_db.py", "scripts.sector_rotation"),
        ("ui/analytics_db.py", "scripts.theme_flow"),
        ("ui/analytics_db.py", "scripts.theme_flow_controls"),
        ("ui/ibkr_reconcile.py", "scripts.ibkr_client"),
        ("ui/industry_roles.py", "scripts.industry_roles"),
        ("ui/influencers.py", "scripts.agent_reach_social_bridge"),
        ("ui/influencers.py", "scripts.influencer_roster_runtime"),
        ("ui/influencers.py", "scripts.x_analysis"),
        ("ui/institution_portfolio.py", "scripts.edgar_13f"),
        ("ui/institutional_holdings.py", "scripts.institutional_free"),
        ("ui/momentum_options.py", "scripts.cache_policy"),
        ("ui/options_cockpit.py", "scripts.insider_edgar"),
        ("ui/options_cockpit.py", "scripts.iv_history"),
        ("ui/options_cockpit.py", "scripts.momentum_options"),
        ("ui/options_cockpit.py", "scripts.options_analytics"),
        ("ui/options_cockpit.py", "scripts.options_free"),
        ("ui/options_cockpit.py", "scripts.quote_fallback"),
        ("ui/options_cockpit.py", "scripts.trade_state"),
        ("ui/options_cockpit.py", "scripts.trading_playbook_engine"),
        ("ui/options_flow.py", "scripts.options_free"),
        ("ui/sector_rotation.py", "scripts.sector_rotation"),
        ("ui/theme_flow.py", "scripts.sector_flow"),
        ("ui/theme_flow.py", "scripts.theme_flow_controls"),
        ("ui/theme_flow.py", "scripts.theme_rotation"),
        ("ui/today_decision.py", "scripts.quote_fallback"),
        ("ui/today_decision.py", "scripts.trade_state"),
        ("ui/trade_state.py", "scripts.trade_state"),
        ("ui/us_cot.py", "scripts.codex_auth_flow"),
        ("ui/us_cot.py", "scripts.cot_es"),
        ("ui/us_options.py", "scripts.iv_history"),
        ("ui/us_options.py", "scripts.options_analytics"),
        ("ui/us_options.py", "scripts.options_free"),
        ("ui/watchlist_categorize.py", "scripts.ibkr_client"),
        ("ui/watchlist_categorize.py", "scripts.sector_free"),
        ("ui/watchlist_categorize.py", "scripts.theme_classify"),
        ("ui/x_sentiment.py", "scripts.agent_reach_auth"),
        ("ui/x_sentiment.py", "scripts.agent_reach_social_bridge"),
        ("ui/x_sentiment.py", "scripts.codex_auth_flow"),
        ("ui/x_sentiment.py", "scripts.social_intelligence"),
        ("ui/x_sentiment.py", "scripts.social_intelligence_summary"),
        ("ui/x_sentiment.py", "scripts.x_analysis"),
        ("ui/x_sentiment.py", "scripts.x_influencers"),
    }
)


def _script_imports(path: Path) -> set[tuple[str, str]]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    relative_path = path.relative_to(ROOT).as_posix()
    imports: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "scripts" or alias.name.startswith("scripts."):
                    imports.add((relative_path, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module == "scripts":
                for alias in node.names:
                    imports.add((relative_path, f"scripts.{alias.name}"))
            elif node.module.startswith("scripts."):
                for alias in node.names:
                    imports.add((relative_path, f"{node.module}.{alias.name}"))
    return imports


def _imports(path: Path) -> set[str]:
    tree = ast.parse(
        path.read_text(encoding="utf-8"),
        filename=str(path),
        feature_version=(3, 10),
    )
    package = path.relative_to(ROOT).parent.as_posix().replace("/", ".")
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                package_parts = package.split(".") if package else []
                keep = len(package_parts) - (node.level - 1)
                base_parts = package_parts[:max(keep, 0)]
                if node.module:
                    imported.add(".".join((*base_parts, node.module)))
                else:
                    imported.update(
                        ".".join((*base_parts, alias.name))
                        for alias in node.names
                    )
            elif node.module:
                imported.add(node.module)
    return imported


def _local_module_path(module: str) -> Path | None:
    parts = module.split(".")
    if not parts or parts[0] not in LOCAL_PACKAGES:
        return None
    path = ROOT.joinpath(*parts).with_suffix(".py")
    return path if path.is_file() else None


def _local_dependency_closure(start: Path) -> set[Path]:
    pending = [start]
    visited: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        for module in sorted(_imports(path)):
            local_path = _local_module_path(module)
            if local_path is not None and local_path not in visited:
                pending.append(local_path)
    return visited


def _forbidden_io_calls(path: Path) -> set[str]:
    tree = ast.parse(
        path.read_text(encoding="utf-8"),
        filename=str(path),
        feature_version=(3, 10),
    )
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_IO_CALLS:
            found.add(node.func.id)
        elif isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_IO_CALLS:
            found.add(node.func.attr)
    return found


def _forbidden_imports(path: Path) -> set[str]:
    return {
        module
        for module in _imports(path)
        if any(
            module == prefix or module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_TRANSITIVE_IMPORTS
        )
    }


def test_ui_script_imports_match_the_shrinking_legacy_inventory() -> None:
    actual: set[tuple[str, str]] = set()
    for path in sorted(UI_DIR.glob("*.py")):
        actual.update(_script_imports(path))

    added = sorted(actual - LEGACY_SCRIPT_IMPORTS)
    removed = sorted(LEGACY_SCRIPT_IMPORTS - actual)
    if added:
        raise AssertionError(f"new UI backend imports must use HTTP APIs: {added}")
    if removed:
        raise AssertionError(
            "delete migrated imports from LEGACY_SCRIPT_IMPORTS: "
            f"{removed}"
        )


def test_api_only_slices_have_no_local_backend_import() -> None:
    guarded_files = [
        UI_DIR / "sys_ai_updates.py",
        UI_DIR / "sys_schedules.py",
        UI_DIR / "_read_api.py",
    ]
    found = set().union(*(_script_imports(path) for path in guarded_files))
    if found:
        raise AssertionError(f"API-only slice imports local backend: {sorted(found)}")
    for path in guarded_files:
        tree = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
            feature_version=(3, 10),
        )
        implementation_imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module in {"api.artifacts", "api.main"}
        }
        if implementation_imports:
            raise AssertionError(
                f"API-only slice imports backend implementation: {path.name} "
                f"{sorted(implementation_imports)}"
            )


def test_presentation_island_has_no_backend_or_io_dependency() -> None:
    for path in (UI_DIR / "_components.py", UI_DIR / "_design.py"):
        forbidden_imports = _forbidden_imports(path)
        forbidden_calls = _forbidden_io_calls(path)
        if forbidden_imports or forbidden_calls:
            raise AssertionError(
                f"presentation module crossed the backend boundary: {path.name} "
                f"imports={sorted(forbidden_imports)} calls={sorted(forbidden_calls)}"
            )


def test_ai_updates_level_two_closure_is_presentation_and_api_only() -> None:
    closure = _local_dependency_closure(UI_DIR / "sys_ai_updates.py")
    expected = {
        ROOT / "api" / "models.py",
        UI_DIR / "_components.py",
        UI_DIR / "_read_api.py",
        UI_DIR / "sys_ai_updates.py",
    }
    if closure != expected:
        raise AssertionError(
            "AI Updates local dependency closure drifted: "
            f"{sorted(path.relative_to(ROOT).as_posix() for path in closure)}"
        )
    for path in closure:
        forbidden_imports = _forbidden_imports(path)
        forbidden_calls = _forbidden_io_calls(path)
        if forbidden_imports or forbidden_calls:
            raise AssertionError(
                f"AI Updates transitive backend dependency: "
                f"{path.relative_to(ROOT).as_posix()} "
                f"imports={sorted(forbidden_imports)} calls={sorted(forbidden_calls)}"
            )


def test_crypto_universe_level_two_closure_is_presentation_and_api_only() -> None:
    closure = _local_dependency_closure(UI_DIR / "crypto_universe.py")
    expected = {
        ROOT / "api" / "models.py",
        UI_DIR / "_components.py",
        UI_DIR / "_read_api.py",
        UI_DIR / "crypto_universe.py",
    }
    if closure != expected:
        raise AssertionError(
            "Crypto Universe local dependency closure drifted: "
            f"{sorted(path.relative_to(ROOT).as_posix() for path in closure)}"
        )
    for path in closure:
        forbidden_imports = _forbidden_imports(path)
        forbidden_calls = _forbidden_io_calls(path)
        if forbidden_imports or forbidden_calls:
            raise AssertionError(
                f"Crypto Universe transitive backend dependency: "
                f"{path.relative_to(ROOT).as_posix()} "
                f"imports={sorted(forbidden_imports)} calls={sorted(forbidden_calls)}"
            )


def test_fund_catalog_slice_is_api_only_with_edgar_provider_preserved() -> None:
    path = UI_DIR / "institution_portfolio.py"
    expected_provider = {
        ("ui/institution_portfolio.py", "scripts.edgar_13f"),
    }
    found = _script_imports(path)
    if found != expected_provider:
        raise AssertionError(
            "Fund Catalog must be API-only while SEC EDGAR remains a provider: "
            f"{sorted(found)}"
        )

    tree = ast.parse(
        path.read_text(encoding="utf-8"),
        filename=str(path),
        feature_version=(3, 10),
    )
    implementation_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module in {"api.artifacts", "api.main"}
    }
    if implementation_imports:
        raise AssertionError(
            "Fund Catalog API-only slice imports backend implementation: "
            f"{sorted(implementation_imports)}"
        )


def test_single_ticker_iv_rank_is_api_only_with_local_page_paths_preserved() -> None:
    path = UI_DIR / "us_options.py"
    expected_providers = {
        ("ui/us_options.py", "scripts.iv_history"),
        ("ui/us_options.py", "scripts.options_analytics"),
        ("ui/us_options.py", "scripts.options_free"),
    }
    found = _script_imports(path)
    if found != expected_providers:
        raise AssertionError(
            "Single-ticker IV Rank must be API-only while candidate ranking and "
            f"the options chain remain local providers: {sorted(found)}"
        )

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    implementation_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module in {"api.artifacts", "api.main"}
    }
    if implementation_imports:
        raise AssertionError(
            "Single-ticker IV Rank API-only slice imports backend implementation: "
            f"{sorted(implementation_imports)}"
        )

    resolver = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_load_iv_history"
    )
    resolver_names = {
        node.id for node in ast.walk(resolver) if isinstance(node, ast.Name)
    }
    forbidden = resolver_names & {
        "_shared",
        "read_artifact",
        "iv_history_spec",
        "ArtifactAvailable",
        "ArtifactUnavailable",
        "IvHistoryData",
    }
    if forbidden:
        raise AssertionError(
            "Single-ticker IV Rank resolver bypasses the HTTP API: "
            f"{sorted(forbidden)}"
        )


def test_options_flow_slice_is_api_only_with_live_provider_preserved() -> None:
    path = UI_DIR / "options_flow.py"
    expected_provider = {
        ("ui/options_flow.py", "scripts.options_free"),
    }
    found = _script_imports(path)
    if found != expected_provider:
        raise AssertionError(
            "Options Flow feed must be API-only while the live chain remains a "
            f"direct provider: {sorted(found)}"
        )

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    implementation_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module in {"api.artifacts", "api.main"}
    }
    if implementation_imports:
        raise AssertionError(
            "Options Flow API-only slice imports backend implementation: "
            f"{sorted(implementation_imports)}"
        )

    resolver = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_load_options_flow"
    )
    resolver_names = {
        node.id for node in ast.walk(resolver) if isinstance(node, ast.Name)
    }
    forbidden = resolver_names & {
        "read_artifact",
        "ARTIFACTS",
        "ArtifactAvailable",
        "_read_local_options_flow",
    }
    if forbidden:
        raise AssertionError(
            "Options Flow resolver bypasses the HTTP API: "
            f"{sorted(forbidden)}"
        )


def test_market_thesis_selected_reads_are_api_only() -> None:
    path = UI_DIR / "market_thesis.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    implementation_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module in {"api.artifacts", "api.main"}
    }
    if implementation_imports:
        raise AssertionError(
            "Market Thesis latest imports backend implementation: "
            f"{sorted(implementation_imports)}"
        )

    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    for name, required in (
        ("_latest_forecast", "_read_api.load_market_thesis()"),
        ("_validation_summary", "_read_api.load_market_thesis_validation()"),
        ("_regime_history_summary", "_read_api.load_market_thesis_regime_history()"),
    ):
        resolver_source = functions[name]
        if required not in resolver_source:
            raise AssertionError(f"Market Thesis {name} does not use {required}")
        forbidden = ("glob(", ".exists(", "load_json", "read_artifact", "ARTIFACTS")
        retained = [item for item in forbidden if item in resolver_source]
        if retained:
            raise AssertionError(f"Market Thesis {name} retained local/backend code: {retained}")
    for forbidden in ("validation_summary.json", "regime_history.json"):
        if forbidden in source:
            raise AssertionError(f"Market Thesis retained local read: {forbidden}")


def test_signal_snapshots_and_oversold_validation_are_api_only() -> None:
    radar_path = UI_DIR / "radar.py"
    radar_source = radar_path.read_text(encoding="utf-8")
    radar_tree = ast.parse(radar_source, filename=str(radar_path), feature_version=(3, 10))
    discovery = next(
        node
        for node in radar_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_beaten_down_tickers"
    )
    discovery_source = ast.get_source_segment(radar_source, discovery) or ""
    if "_read_api.load_reversal_radar()" not in discovery_source:
        raise AssertionError("Reversal discovery does not use the fixed API client")
    if "load_json" in discovery_source or "reports/reversal_radar" in discovery_source:
        raise AssertionError("Reversal discovery retained a local latest fallback")
    for preserved in ("import reversal_radar", "rgui._analyze", "rgui._tab_portfolio"):
        if preserved not in radar_source:
            raise AssertionError(f"live/private Radar boundary removed: {preserved}")

    oversold_path = UI_DIR / "oversold_reversal_lane.py"
    oversold_source = oversold_path.read_text(encoding="utf-8")
    oversold_tree = ast.parse(
        oversold_source,
        filename=str(oversold_path),
        feature_version=(3, 10),
    )
    latest = next(
        node
        for node in oversold_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_load_latest"
    )
    latest_source = ast.get_source_segment(oversold_source, latest) or ""
    if "_read_api.load_oversold_reversal()" not in latest_source:
        raise AssertionError("Oversold latest does not use the fixed API client")
    if "load_json" in latest_source or "latest.json" in latest_source:
        raise AssertionError("Oversold latest retained a local fallback")
    validation = next(
        node
        for node in oversold_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_render_forward_validation"
    )
    validation_source = ast.get_source_segment(oversold_source, validation) or ""
    if "_read_api.load_oversold_reversal_validation()" not in validation_source:
        raise AssertionError("Oversold validation does not use the fixed API client")
    if "load_json" in validation_source or "validation_summary.json" in oversold_source:
        raise AssertionError("Oversold validation retained a local fallback")


def test_today_decision_candidate_feeds_are_api_only_with_local_controls_preserved() -> None:
    path = UI_DIR / "today_decision.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
    implementation_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module in {"api.artifacts", "api.main"}
    }
    if implementation_imports:
        raise AssertionError(
            "Today Decision candidate slice imports backend implementation: "
            f"{sorted(implementation_imports)}"
        )
    for local_read in (
        'candidate_output_path("ranked_candidates.json")',
        'candidate_output_path("scored_candidates.json")',
    ):
        if local_read in source:
            raise AssertionError(f"Today Decision retained local candidate read: {local_read}")

    render = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "render"
    )
    render_source = ast.get_source_segment(source, render) or ""
    for loader in ("load_ranked_candidates()", "load_scored_candidates()"):
        if render_source.count(loader) != 1:
            raise AssertionError((loader, render_source))
    trust = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_render_trust_boundary"
    )
    trust_source = ast.get_source_segment(source, trust) or ""
    for loader in (
        "load_market_thesis_validation()",
        "load_reversal_radar_validation()",
        "load_oversold_reversal_validation()",
    ):
        if trust_source.count(loader) != 1:
            raise AssertionError((loader, trust_source))
    if "_local_validation_summary" in source or "validation_summary.json" in source:
        raise AssertionError("Today Decision retained a local validation read")
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    for function_name, loader in (
        ("_render_opportunities", "load_options_flow()"),
        ("_render_risk_and_research", "load_reversal_radar()"),
        ("_render_risk_and_research", "load_oversold_reversal()"),
    ):
        if functions[function_name].count(loader) != 1:
            raise AssertionError((function_name, loader, functions[function_name]))
    for removed in ("_flow_signals", "_FLOW_DIR", "_REVERSAL_DIR", "_OVERSOLD_DIR"):
        if removed in source:
            raise AssertionError(f"Today Decision retained selected local source: {removed}")
    for preserved in (
        "_candidate_controls.render()",
        "quote_fallback.get_quote",
        "trade_state_engine.build_trade_state_rows",
        "_shared.load_reconciliation()",
        "_shared.load_ledger()",
    ):
        if preserved not in source:
            raise AssertionError(f"Today Decision local boundary removed: {preserved}")


def test_secondary_candidate_consumers_are_api_only_with_siblings_preserved() -> None:
    cases = (
        (
            UI_DIR / "sys_schedules.py",
            "_latest_candidate_refresh_result",
            "load_ranked_candidates()",
            'candidate_output_path("ranked_candidates.json")',
            "load_money_flow()",
        ),
        (
            UI_DIR / "institutional_holdings.py",
            "_render_score_context",
            "load_scored_candidates()",
            'candidate_output_path("scored_candidates.json")',
            "from scripts import institutional_free",
        ),
        (
            UI_DIR / "analytics_db.py",
            "_ranked_tickers",
            "load_ranked_candidates()",
            'candidate_output_path("ranked_candidates.json")',
            "def _refresh_fundamentals",
        ),
    )
    for path, function_name, loader, local_read, preserved in cases:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == function_name
        )
        function_source = ast.get_source_segment(source, function) or ""
        if local_read in function_source:
            raise AssertionError(f"{path.name}:{function_name} retained {local_read}")
        if loader not in source:
            raise AssertionError(f"{path.name} does not use {loader}")
        if preserved not in source:
            raise AssertionError(f"{path.name} removed sibling boundary: {preserved}")


def test_phase4m_4o_candidate_consumers_are_api_only_with_siblings_preserved() -> None:
    cases = (
        (
            UI_DIR / "us_options.py",
            "_candidate_grid",
            "load_scored_candidates()",
            'candidate_output_path("scored_candidates.json")',
            "_iv_rank_spark(ticker)",
        ),
        (
            UI_DIR / "industry_roles.py",
            "_candidate_tickers",
            "load_ranked_candidates()",
            'candidate_output_path("ranked_candidates.json")',
            'REPORTS_DIR / "x_influencer_picks.json"',
        ),
        (
            UI_DIR / "options_cockpit.py",
            "_watchlist_quickpick",
            "load_scored_candidates()",
            'candidate_output_path("scored_candidates.json")',
            "_read_api.load_options_flow()",
        ),
    )
    for path, function_name, loader, local_read, preserved in cases:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == function_name
        )
        function_source = ast.get_source_segment(source, function) or ""
        if local_read in function_source:
            raise AssertionError(f"{path.name}:{function_name} retained {local_read}")
        if function_source.count(loader) != 1:
            raise AssertionError(f"{path.name}:{function_name} must call {loader} once")
        if preserved not in function_source:
            raise AssertionError(f"{path.name}:{function_name} removed {preserved}")


def test_phase4q_4s_scored_slices_are_api_only_with_siblings_preserved() -> None:
    cases = (
        (
            UI_DIR / "analyst_views.py",
            "_candidate_grid_state",
            "load_scored_candidates()",
            'candidate_output_path("scored_candidates.json")',
            "_shared.load_analyst_views(ticker)",
        ),
        (
            UI_DIR / "sector_rotation.py",
            "_candidate_mapping_state",
            "load_scored_candidates()",
            'candidate_output_path("scored_candidates.json")',
            "_shared.ticker_sector_etf(ticker)",
        ),
        (
            UI_DIR / "us_screener.py",
            "_scored_state",
            "load_scored_candidates_screener()",
            'candidate_output_path("scored_candidates.json")',
            'DATA_DIR / "layer2_results.json"',
        ),
    )
    for path, function_name, loader, local_read, preserved in cases:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path), feature_version=(3, 10))
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == function_name
        )
        function_source = ast.get_source_segment(source, function) or ""
        if local_read in source:
            raise AssertionError(f"{path.name} retained {local_read}")
        if function_source.count(loader) != 1:
            raise AssertionError(f"{path.name}:{function_name} must call {loader} once")
        if preserved not in source:
            raise AssertionError(f"{path.name} removed sibling boundary: {preserved}")


def test_phase4w_4z_money_flow_slices_are_api_only_with_scopes_preserved() -> None:
    schedules_path = UI_DIR / "sys_schedules.py"
    schedules_source = schedules_path.read_text(encoding="utf-8")
    schedules_tree = ast.parse(
        schedules_source,
        filename=str(schedules_path),
        feature_version=(3, 10),
    )
    candidate_result = next(
        node
        for node in schedules_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_latest_candidate_refresh_result"
    )
    candidate_source = ast.get_source_segment(schedules_source, candidate_result) or ""
    if candidate_source.count("load_money_flow()") != 1:
        raise AssertionError("Schedules must issue one fixed Money Flow read")
    if 'REPORTS_DIR / "money_flow" / "latest.json"' in candidate_source:
        raise AssertionError("Schedules retained its selected local Money Flow read")

    cockpit_path = UI_DIR / "options_cockpit.py"
    cockpit_source = cockpit_path.read_text(encoding="utf-8")
    cockpit_tree = ast.parse(
        cockpit_source,
        filename=str(cockpit_path),
        feature_version=(3, 10),
    )
    functions = {
        node.name: ast.get_source_segment(cockpit_source, node) or ""
        for node in cockpit_tree.body
        if isinstance(node, ast.FunctionDef)
    }
    if functions["render"].count("_load_money_flow_state()") != 1:
        raise AssertionError("standalone Options Cockpit must load one API state")
    if functions["render_for"].count("_load_money_flow_state()") != 1:
        raise AssertionError("embedded Options Cockpit must load one API state")
    if "_load_money_flow_artifact" in cockpit_source:
        raise AssertionError("Options Cockpit retained a local Money Flow reader")
    if "_load_money_flow_artifact" in functions["_load_money_flow_state"]:
        raise AssertionError("Money Flow API state retained a local fallback")
    if ("ui/options_cockpit.py", "scripts.insider_edgar") not in _script_imports(
        cockpit_path
    ):
        raise AssertionError("Options Cockpit EDGAR sibling was removed")


def test_phase5a_5b_options_flow_consumers_are_api_only_with_scopes_preserved() -> None:
    schedules_path = UI_DIR / "sys_schedules.py"
    schedules_source = schedules_path.read_text(encoding="utf-8")
    schedules_tree = ast.parse(
        schedules_source,
        filename=str(schedules_path),
        feature_version=(3, 10),
    )
    schedules_functions = {
        node.name: ast.get_source_segment(schedules_source, node) or ""
        for node in schedules_tree.body
        if isinstance(node, ast.FunctionDef)
    }
    options_result = schedules_functions["_latest_options_flow_result"]
    if options_result.count("load_options_flow()") != 1:
        raise AssertionError("Schedules must issue one fixed Options Flow read")
    if 'REPORTS_DIR / "options_flow" / "latest.json"' in options_result:
        raise AssertionError("Schedules retained its selected local Options Flow read")
    if "result_cache" not in schedules_functions["render"]:
        raise AssertionError("Schedules does not reuse duplicate result types")

    cockpit_path = UI_DIR / "options_cockpit.py"
    cockpit_source = cockpit_path.read_text(encoding="utf-8")
    cockpit_tree = ast.parse(
        cockpit_source,
        filename=str(cockpit_path),
        feature_version=(3, 10),
    )
    cockpit_functions = {
        node.name: ast.get_source_segment(cockpit_source, node) or ""
        for node in cockpit_tree.body
        if isinstance(node, ast.FunctionDef)
    }
    quickpick = cockpit_functions["_watchlist_quickpick"]
    if quickpick.count("load_options_flow()") != 1:
        raise AssertionError("Options Cockpit must issue one fixed Options Flow read")
    if 'reports / "options_flow" / "latest.json"' in quickpick:
        raise AssertionError("Options Cockpit retained local Options Flow quick picks")
    for preserved in (
        'reports / "watchlist.json"',
        "load_social_intelligence()",
        'reports / "x_influencer_picks.json"',
        "load_scored_candidates()",
    ):
        if preserved not in quickpick:
            raise AssertionError(f"Options Cockpit removed sibling: {preserved}")
    if "_watchlist_quickpick" in cockpit_functions["render_for"]:
        raise AssertionError("embedded Options Cockpit loaded quick picks")


def test_phase5c_5e_selected_reads_are_api_only_with_siblings_preserved() -> None:
    schedules_path = UI_DIR / "sys_schedules.py"
    schedules_source = schedules_path.read_text(encoding="utf-8")
    schedules_tree = ast.parse(
        schedules_source,
        filename=str(schedules_path),
        feature_version=(3, 10),
    )
    schedules_functions = {
        node.name: ast.get_source_segment(schedules_source, node) or ""
        for node in schedules_tree.body
        if isinstance(node, ast.FunctionDef)
    }
    selected = {
        "_latest_crypto_result": (
            "load_crypto_universe()",
            'REPORTS_DIR / "crypto" / "universe_latest.json"',
        ),
        "_latest_theme_flow_result": (
            "load_theme_flow()",
            'REPORTS_DIR / "theme_flow_snapshot.json"',
        ),
    }
    for name, (client_call, local_path) in selected.items():
        result_source = schedules_functions[name]
        if result_source.count(client_call) != 1:
            raise AssertionError(f"Schedules {name} must issue one fixed API read")
        if local_path in result_source or "_shared.load_json" in result_source:
            raise AssertionError(f"Schedules {name} retained a local fallback")
    render = schedules_functions["render"]
    for result_type in ('"crypto_universe"', '"theme_flow"'):
        if result_type not in render:
            raise AssertionError(f"Schedules cache omitted {result_type}")
    for preserved in (
        "_latest_report_result",
        "_latest_ledger_result",
        "_latest_reflection_result",
        "_latest_cot_result",
        "_latest_data_health_result",
    ):
        if preserved not in schedules_source:
            raise AssertionError(f"Schedules removed local sibling: {preserved}")

    cockpit_path = UI_DIR / "options_cockpit.py"
    cockpit_source = cockpit_path.read_text(encoding="utf-8")
    cockpit_tree = ast.parse(
        cockpit_source,
        filename=str(cockpit_path),
        feature_version=(3, 10),
    )
    cockpit_functions = {
        node.name: ast.get_source_segment(cockpit_source, node) or ""
        for node in cockpit_tree.body
        if isinstance(node, ast.FunctionDef)
    }
    if "_load_iv_series" in cockpit_functions:
        raise AssertionError("Options Cockpit retained its local IV series reader")
    resolver = cockpit_functions["_load_cockpit_iv_history"]
    if resolver.count("load_iv_history(ticker)") != 1:
        raise AssertionError("Options Cockpit must issue one fixed IV history read")
    if "iv_percentile_from_series" not in resolver:
        raise AssertionError("Options Cockpit removed the pure IV calculator")
    live = cockpit_functions["_live_provider"]
    for forbidden in ("_load_iv_series", "ivh.iv_percentile(", "_shared.load_json"):
        if forbidden in resolver or forbidden in live:
            raise AssertionError(f"Options Cockpit retained local IV read: {forbidden}")
    for preserved in (
        "mo.analyze(ticker)",
        "of.analyze_options(ticker)",
        "mo_ui._chart_data(ticker)",
    ):
        if preserved not in live:
            raise AssertionError(f"Options Cockpit removed provider sibling: {preserved}")
    if ("ui/options_cockpit.py", "scripts.iv_history") not in _script_imports(
        cockpit_path
    ):
        raise AssertionError("Options Cockpit pure IV calculator import was removed")


def test_phase5f_5h_selected_reads_are_api_only_with_siblings_preserved() -> None:
    cockpit_path = UI_DIR / "options_cockpit.py"
    cockpit_source = cockpit_path.read_text(encoding="utf-8")
    cockpit_tree = ast.parse(
        cockpit_source,
        filename=str(cockpit_path),
        feature_version=(3, 10),
    )
    functions = {
        node.name: ast.get_source_segment(cockpit_source, node) or ""
        for node in cockpit_tree.body
        if isinstance(node, ast.FunctionDef)
    }
    quickpick = functions["_watchlist_quickpick"]
    if quickpick.count("load_social_intelligence()") != 1:
        raise AssertionError("Cockpit must issue one fixed Social read")
    if 'reports / "social_intelligence" / "latest.json"' in quickpick:
        raise AssertionError("Cockpit retained local Social presentation read")
    for sibling in (
        'reports / "watchlist.json"',
        'reports / "x_influencer_picks.json"',
        "load_scored_candidates()",
        "load_options_flow()",
    ):
        if sibling not in quickpick:
            raise AssertionError(f"Cockpit removed sibling: {sibling}")
    if "load_social_intelligence" in functions["render_for"]:
        raise AssertionError("embedded Cockpit loaded Social quick-picks")


def test_phase5i_5k_sector_rotation_reads_are_api_only_with_siblings_preserved() -> None:
    shared_source = (UI_DIR / "_shared.py").read_text(encoding="utf-8")
    standalone_source = (UI_DIR / "sector_rotation.py").read_text(encoding="utf-8")
    stock_source = (UI_DIR / "stock_checkup.py").read_text(encoding="utf-8")
    if "def load_sector_flow(" in shared_source:
        raise AssertionError("shared local/live Sector Rotation fallback remains")
    if "load_sector_flow" in standalone_source + stock_source:
        raise AssertionError("selected consumers retained local Sector Rotation board")

    standalone_functions = {
        node.name: ast.get_source_segment(standalone_source, node) or ""
        for node in ast.parse(standalone_source).body
        if isinstance(node, ast.FunctionDef)
    }
    if standalone_functions["_board_state"].count("load_sector_rotation()") != 1:
        raise AssertionError("standalone Sector Rotation must issue one fixed board read")
    for sibling in (
        'REPORTS_DIR / "sector_rotation.json"',
        "generate_rotation_read",
        "load_scored_candidates()",
        "ticker_sector_etf(ticker)",
    ):
        if sibling not in standalone_source:
            raise AssertionError(f"standalone Sector Rotation removed sibling: {sibling}")
    drill = standalone_functions["_render_sector_themes_drill"]
    if drill.count("load_theme_drill()") != 1 or "load_baskets" in drill:
        raise AssertionError("Sector Rotation theme drill is not API-only")

    stock_functions = {
        node.name: ast.get_source_segment(stock_source, node) or ""
        for node in ast.parse(stock_source).body
        if isinstance(node, ast.FunctionDef)
    }
    if stock_functions["_render_single"].count("_sector_board_state()") != 1:
        raise AssertionError("Stock Checkup must resolve one board per single render")
    for consumer in ("_header", "_sector_positioning"):
        if "board_state" not in stock_functions[consumer]:
            raise AssertionError(f"Stock Checkup {consumer} did not reuse injected board")
    if "_sector_board_state()" in stock_functions["_render_batch"]:
        raise AssertionError("Stock Checkup batch mode loaded Sector Rotation")
    if "ticker_sector_etf(ticker)" not in stock_functions["_sector_lookup"]:
        raise AssertionError("Stock Checkup removed ticker-to-sector provider")


def test_phase5u_5w_today_gate_reads_are_api_only_with_siblings_preserved() -> None:
    source = (UI_DIR / "today_decision.py").read_text(encoding="utf-8")
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef)
    }
    render = functions["render"]
    if render.count("load_market_thesis()") != 1:
        raise AssertionError("Today must issue one fixed Market Thesis read")
    if render.count("load_daily_summary()") != 1:
        raise AssertionError("Today must issue one fixed Daily Summary read")
    for retired in (
        "_latest_market_thesis",
        "_latest_daily_summary",
        "_MARKET_THESIS_DIR",
        '"summary.json"',
        "find_report_dates",
    ):
        if retired in source:
            raise AssertionError(f"Today retained selected local read: {retired}")
    for sibling in (
        "_shared.load_reconciliation()",
        "_shared.load_ledger()",
        "trade_state_engine.build_trade_state_rows",
        "_candidate_controls.render()",
        "quote_fallback.get_quote(ticker)",
    ):
        if sibling not in source:
            raise AssertionError(f"Today removed retained sibling: {sibling}")


def test_phase5x_5z_selected_reads_are_api_only_with_siblings_preserved() -> None:
    schedules_source = (UI_DIR / "sys_schedules.py").read_text(encoding="utf-8")
    schedules_functions = {
        node.name: ast.get_source_segment(schedules_source, node) or ""
        for node in ast.parse(schedules_source).body
        if isinstance(node, ast.FunctionDef)
    }
    report_result = schedules_functions["_latest_report_result"]
    if report_result.count("load_daily_summary()") != 1:
        raise AssertionError("Schedules report card must issue one Daily Summary read")
    for retired in ("find_report_dates", '"summary.json"', "_shared.load_json"):
        if retired in report_result:
            raise AssertionError(f"Schedules report card retained local read: {retired}")
    if '"report_dir"' not in schedules_source:
        raise AssertionError("Schedules report result must remain in the per-render cache")
    for sibling in (
        "_shared.load_ledger()",
        "_latest_reflection_detail()",
        "_latest_cot_result",
        "_latest_data_health_result",
    ):
        if sibling not in schedules_source:
            raise AssertionError(f"Schedules removed retained sibling: {sibling}")

    playbook_source = (UI_DIR / "playbook_validation.py").read_text(encoding="utf-8")
    playbook_tree = ast.parse(playbook_source, feature_version=(3, 10))
    render = next(
        node
        for node in playbook_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "render"
    )
    render_source = ast.get_source_segment(playbook_source, render) or ""
    if render_source.count("load_playbook_validation()") != 1:
        raise AssertionError("Playbook Validation must issue one fixed API read")
    for retired in ("_shared", "load_json", "latest.json", "REPORT"):
        if retired in playbook_source:
            raise AssertionError(f"Playbook Validation retained local read: {retired}")
    retro_source = (UI_DIR / "retro_analysis.py").read_text(encoding="utf-8")
    for sibling in ("playbook_validation", "continuation_validation"):
        if sibling not in retro_source:
            raise AssertionError(f"Retro Analysis removed validation sibling: {sibling}")


def test_phase6a_6f_continuation_and_cot_reads_are_api_only() -> None:
    continuation_source = (UI_DIR / "continuation_validation.py").read_text(
        encoding="utf-8"
    )
    continuation_render = next(
        node
        for node in ast.parse(continuation_source).body
        if isinstance(node, ast.FunctionDef) and node.name == "render"
    )
    continuation_body = (
        ast.get_source_segment(continuation_source, continuation_render) or ""
    )
    if continuation_body.count("load_continuation_validation()") != 1:
        raise AssertionError("Continuation Validation must issue one fixed API read")
    for retired in ("REPORTS_DIR", "Path(", "json.loads", "continuation_strength.json"):
        if retired in continuation_source:
            raise AssertionError(f"Continuation retained local read: {retired}")

    schedules_source = (UI_DIR / "sys_schedules.py").read_text(encoding="utf-8")
    schedules_functions = {
        node.name: ast.get_source_segment(schedules_source, node) or ""
        for node in ast.parse(schedules_source).body
        if isinstance(node, ast.FunctionDef)
    }
    cot_result = schedules_functions["_latest_cot_result"]
    if cot_result.count("load_cot_catalog()") != 1:
        raise AssertionError("Schedules COT card must issue one catalog read")
    for retired in ("REPORTS_DIR", ".glob(", "load_json"):
        if retired in cot_result:
            raise AssertionError(f"Schedules COT card retained local read: {retired}")

    cot_source = (UI_DIR / "us_cot.py").read_text(encoding="utf-8")
    cot_render = next(
        node
        for node in ast.parse(cot_source).body
        if isinstance(node, ast.FunctionDef) and node.name == "render"
    )
    cot_body = ast.get_source_segment(cot_source, cot_render) or ""
    if cot_body.count("load_cot_catalog()") != 1:
        raise AssertionError("COT page must issue one catalog read")
    if cot_body.count("load_cot_report(chosen)") != 1:
        raise AssertionError("COT page must issue one selected detail read")
    for retired in ("_COT_DIR", '.glob("*.md")', "_shared.load_json"):
        if retired in cot_source:
            raise AssertionError(f"COT page retained local persisted read: {retired}")
    for sibling in ("codex_auth_flow", "cot_es.generate_report", "_read_text"):
        if sibling not in cot_source:
            raise AssertionError(f"COT page removed local mutation/auth sibling: {sibling}")


def test_phase6g_6l_public_resource_reads_are_api_only() -> None:
    graph_source = (UI_DIR / "knowledge_graph.py").read_text(encoding="utf-8")
    graph_functions = {
        node.name: ast.get_source_segment(graph_source, node) or ""
        for node in ast.parse(graph_source).body
        if isinstance(node, ast.FunctionDef)
    }
    if graph_functions["_load_graph"].count("load_knowledge_graph()") != 1:
        raise AssertionError("Knowledge Graph must issue one fixed API read")
    for retired in ("scripts.knowledge_graph", "kg.VAULT", "kg.build_graph", "n.get('path')"):
        if retired in graph_source:
            raise AssertionError(f"Knowledge Graph retained backend/path read: {retired}")

    watch_source = (UI_DIR / "watchlist_categorize.py").read_text(encoding="utf-8")
    watch_functions = {
        node.name: ast.get_source_segment(watch_source, node) or ""
        for node in ast.parse(watch_source).body
        if isinstance(node, ast.FunctionDef)
    }
    taxonomy_body = watch_functions["_load_taxonomy"]
    if taxonomy_body.count("load_theme_taxonomy()") != 1 or "load_json" in taxonomy_body:
        raise AssertionError("Watchlist taxonomy retained a local read or wrong cardinality")
    for sibling in ("theme_classify.classify_themes", "_render_ibkr_inputs", "_render_tv_input"):
        if sibling not in watch_source:
            raise AssertionError(f"Watchlist removed local sibling: {sibling}")

    influencer_source = (UI_DIR / "influencers.py").read_text(encoding="utf-8")
    influencer_functions = {
        node.name: ast.get_source_segment(influencer_source, node) or ""
        for node in ast.parse(influencer_source).body
        if isinstance(node, ast.FunctionDef)
    }
    if influencer_functions["render"].count("load_roster(api_only=True)") != 1:
        raise AssertionError("Influencer page must issue one API-only roster read")
    load_body = influencer_functions["load_roster"]
    if load_body.count("load_influencer_roster()") != 1:
        raise AssertionError("Influencer API-only branch must issue one fixed read")
    for sibling in ("def save_roster", "lookup_x_preview", "bulk_upsert_influencers"):
        if sibling not in influencer_source:
            raise AssertionError(f"Influencer page removed mutation/provider sibling: {sibling}")

    x_source = (UI_DIR / "x_sentiment.py").read_text(encoding="utf-8")
    x_single = next(
        ast.get_source_segment(x_source, node) or ""
        for node in ast.parse(x_source).body
        if isinstance(node, ast.FunctionDef) and node.name == "_render_single"
    )
    if x_single.count("for_market(market, api_only=True)") != 1:
        raise AssertionError("X single-account quick-pick must use one API-only roster read")


def main() -> None:
    tests = [
        test_ui_script_imports_match_the_shrinking_legacy_inventory,
        test_api_only_slices_have_no_local_backend_import,
        test_presentation_island_has_no_backend_or_io_dependency,
        test_ai_updates_level_two_closure_is_presentation_and_api_only,
        test_crypto_universe_level_two_closure_is_presentation_and_api_only,
        test_fund_catalog_slice_is_api_only_with_edgar_provider_preserved,
        test_single_ticker_iv_rank_is_api_only_with_local_page_paths_preserved,
        test_options_flow_slice_is_api_only_with_live_provider_preserved,
        test_market_thesis_selected_reads_are_api_only,
        test_signal_snapshots_and_oversold_validation_are_api_only,
        test_today_decision_candidate_feeds_are_api_only_with_local_controls_preserved,
        test_secondary_candidate_consumers_are_api_only_with_siblings_preserved,
        test_phase4m_4o_candidate_consumers_are_api_only_with_siblings_preserved,
        test_phase4q_4s_scored_slices_are_api_only_with_siblings_preserved,
        test_phase4w_4z_money_flow_slices_are_api_only_with_scopes_preserved,
        test_phase5a_5b_options_flow_consumers_are_api_only_with_scopes_preserved,
        test_phase5c_5e_selected_reads_are_api_only_with_siblings_preserved,
        test_phase5f_5h_selected_reads_are_api_only_with_siblings_preserved,
        test_phase5i_5k_sector_rotation_reads_are_api_only_with_siblings_preserved,
        test_phase5u_5w_today_gate_reads_are_api_only_with_siblings_preserved,
        test_phase5x_5z_selected_reads_are_api_only_with_siblings_preserved,
        test_phase6a_6f_continuation_and_cot_reads_are_api_only,
        test_phase6g_6l_public_resource_reads_are_api_only,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
