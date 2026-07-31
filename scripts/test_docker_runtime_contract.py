#!/usr/bin/env python3
"""Static deployment contract tests for the Docker runtime.

These tests keep Docker runtime state explicit: generated candidate artifacts and
Codex login credentials must live in mounted volumes, not only inside the image
layer that disappears when the container is recreated.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
COMPOSE = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")
DOCKERIGNORE = (ROOT / ".dockerignore").read_text(encoding="utf-8")
SHARED = (ROOT / "ui" / "_shared.py").read_text(encoding="utf-8")
CONTROLS = (ROOT / "scripts" / "candidate_pipeline_controls.py").read_text(encoding="utf-8")
CODEX_AUTH = (ROOT / "scripts" / "codex_auth_flow.py").read_text(encoding="utf-8")
PIPELINE = (ROOT / "scripts" / "run_candidate_pipeline.py").read_text(encoding="utf-8")
TODAY = (ROOT / "ui" / "today_decision.py").read_text(encoding="utf-8")
CANDIDATE_CONTROLS = (ROOT / "ui" / "_candidate_controls.py").read_text(encoding="utf-8")
DEPLOY_TEST_SERVER = (ROOT / "scripts" / "deploy_test_server.sh").read_text(encoding="utf-8")


def assert_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing: {needle}")


def test_docker_persists_candidate_outputs_and_codex_auth() -> None:
    for needle in [
        "SURGE_CANDIDATE_OUTPUT_DIR=/app/var/candidates",
        "CODEX_HOME=/app/.codex",
        "HOME=/app",
        "candidate_outputs:/app/var/candidates",
        "codex_config:/app/.codex",
        "candidate_outputs:",
        "codex_config:",
    ]:
        assert_contains(COMPOSE, needle)


def test_docker_links_legacy_root_candidate_artifacts_to_volume() -> None:
    for artifact in [
        "filtered_universe.json",
        "ranked_candidates.json",
        "scored_candidates.json",
        "layer2_results.json",
        "dd_results.json",
    ]:
        assert_contains(DOCKERFILE, f"/app/var/candidates/{artifact}")
        assert_contains(DOCKERFILE, f"/app/{artifact}")


def test_docker_build_context_excludes_runtime_candidate_artifacts() -> None:
    for artifact in [
        "filtered_universe.json",
        "ranked_candidates.json",
        "scored_candidates.json",
        "layer2_results.json",
        "dd_results.json",
    ]:
        assert_contains(DOCKERIGNORE, artifact)


def test_docker_build_context_excludes_sensitive_runtime_files() -> None:
    rules = {
        line.strip()
        for line in DOCKERIGNORE.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    required = {
        "reports/reconciliation.json",
        "reports/watchlist.json",
        "reports/risk_guard/",
        "reports/ai_chat_sessions/",
        "reports/analytics/",
        "reports/analytics-remote/",
        ".env",
        ".env.*",
        ".claude/settings.local.json",
        ".codex/auth.json",
    }
    missing = sorted(required - rules)
    if missing:
        raise AssertionError(f"missing sensitive .dockerignore rules: {', '.join(missing)}")


def test_docker_installs_codex_sdk_runtime_and_sandbox() -> None:
    for needle in [
        "openai-codex",
        "bubblewrap",
    ]:
        assert_contains(DOCKERFILE + (ROOT / "requirements.txt").read_text(encoding="utf-8"), needle)
    for forbidden in ["@anthropic-ai/claude-code", "nodejs npm"]:
        if forbidden in DOCKERFILE:
            raise AssertionError(f"legacy Claude runtime remains: {forbidden}")


def test_runtime_candidate_output_path_is_shared_by_pipeline_and_ui() -> None:
    assert_contains(SHARED, "candidate_output_path")
    assert_contains(SHARED, "CANDIDATE_OUTPUT_DIR")
    assert_contains(PIPELINE, "candidate_output_path")
    assert_contains(TODAY, '_shared.candidate_output_path("ranked_candidates.json")')
    assert_contains(TODAY, '_shared.candidate_output_path("scored_candidates.json")')


def test_codex_auth_flow_is_explicit_and_resumeable() -> None:
    for needle in [
        "Codex 登入中",
        "resume_pending_codex_run",
        "read_pending_codex_request",
        "refresh_codex_auth_status",
        "登入後自動接續",
        "codex-auth.log",
    ]:
        assert_contains(TODAY + CANDIDATE_CONTROLS + CONTROLS + CODEX_AUTH, needle)


def test_test_server_persists_editable_influencer_roster() -> None:
    for needle in [
        "$APP_ROOT/shared/content",
        "$APP_ROOT/shared/content/influencers.json",
        "SURGE_INFLUENCERS_PATH=\"$APP_ROOT/shared/content/influencers.json\"",
        "$RELEASE_DIR/content/influencers.json",
        "ln -sfn \"$SURGE_INFLUENCERS_PATH\"",
    ]:
        assert_contains(DEPLOY_TEST_SERVER, needle)


def test_docker_persists_editable_influencer_roster() -> None:
    for needle in [
        "SURGE_INFLUENCERS_PATH=/app/var/content/influencers.json",
        "influencer_roster:/app/var/content",
        "influencer_roster:",
    ]:
        assert_contains(COMPOSE, needle)


def test_ai_chat_saved_sessions_are_persisted() -> None:
    for needle in [
        "SURGE_AI_CHAT_DIR=/app/var/ai_chat_sessions",
        "ai_chat_sessions:/app/var/ai_chat_sessions",
        "ai_chat_sessions:",
    ]:
        assert_contains(COMPOSE, needle)
    for needle in [
        "SURGE_AI_CHAT_DIR=%h/apps/surge-screener/shared/ai_chat_sessions",
    ]:
        service = (ROOT / "deploy" / "surge-screener.service").read_text(encoding="utf-8")
        assert_contains(service, needle)
    for needle in [
        "$APP_ROOT/shared/ai_chat_sessions",
    ]:
        assert_contains(DEPLOY_TEST_SERVER, needle)


def main() -> None:
    tests = [
        test_docker_persists_candidate_outputs_and_codex_auth,
        test_docker_links_legacy_root_candidate_artifacts_to_volume,
        test_docker_build_context_excludes_runtime_candidate_artifacts,
        test_docker_build_context_excludes_sensitive_runtime_files,
        test_docker_installs_codex_sdk_runtime_and_sandbox,
        test_runtime_candidate_output_path_is_shared_by_pipeline_and_ui,
        test_codex_auth_flow_is_explicit_and_resumeable,
        test_test_server_persists_editable_influencer_roster,
        test_docker_persists_editable_influencer_roster,
        test_ai_chat_saved_sessions_are_persisted,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
