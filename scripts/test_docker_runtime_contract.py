#!/usr/bin/env python3
"""Static deployment contract tests for the Docker runtime.

These tests keep Docker runtime state explicit: generated candidate artifacts and
Claude login credentials must live in mounted volumes, not only inside the image
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
CLAUDE_AUTH = (ROOT / "scripts" / "claude_auth_flow.py").read_text(encoding="utf-8")
PIPELINE = (ROOT / "scripts" / "run_candidate_pipeline.py").read_text(encoding="utf-8")
TODAY = (ROOT / "ui" / "today_decision.py").read_text(encoding="utf-8")
CANDIDATE_CONTROLS = (ROOT / "ui" / "_candidate_controls.py").read_text(encoding="utf-8")
DEPLOY_TEST_SERVER = (ROOT / "scripts" / "deploy_test_server.sh").read_text(encoding="utf-8")


def assert_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing: {needle}")


def test_docker_persists_candidate_outputs_and_claude_auth() -> None:
    for needle in [
        "SURGE_CANDIDATE_OUTPUT_DIR=/app/var/candidates",
        "CLAUDE_CONFIG_DIR=/app/.claude",
        "HOME=/app",
        "candidate_outputs:/app/var/candidates",
        "claude_config:/app/.claude",
        "candidate_outputs:",
        "claude_config:",
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


def test_docker_installs_claude_cli_for_container_login() -> None:
    for needle in [
        "ARG INSTALL_CLAUDE_CLI=1",
        "npm install -g @anthropic-ai/claude-code",
    ]:
        assert_contains(DOCKERFILE, needle)


def test_runtime_candidate_output_path_is_shared_by_pipeline_and_ui() -> None:
    assert_contains(SHARED, "candidate_output_path")
    assert_contains(SHARED, "CANDIDATE_OUTPUT_DIR")
    assert_contains(PIPELINE, "candidate_output_path")
    assert_contains(TODAY, '_shared.candidate_output_path("ranked_candidates.json")')
    assert_contains(TODAY, '_shared.candidate_output_path("scored_candidates.json")')


def test_claude_auth_flow_is_explicit_and_resumeable() -> None:
    for needle in [
        "Claude 登入中",
        "resume_pending_claude_run",
        "read_pending_claude_request",
        "refresh_claude_auth_status",
        "登入後自動接續",
        "claude-auth.log",
    ]:
        assert_contains(TODAY + CANDIDATE_CONTROLS + CONTROLS + CLAUDE_AUTH, needle)


def test_test_server_persists_editable_influencer_roster() -> None:
    for needle in [
        "$APP_ROOT/shared/content",
        "$APP_ROOT/shared/content/influencers.json",
        "$RELEASE_DIR/content/influencers.json",
        "ln -sfn \"$APP_ROOT/shared/content/influencers.json\"",
    ]:
        assert_contains(DEPLOY_TEST_SERVER, needle)


def main() -> None:
    tests = [
        test_docker_persists_candidate_outputs_and_claude_auth,
        test_docker_links_legacy_root_candidate_artifacts_to_volume,
        test_docker_build_context_excludes_runtime_candidate_artifacts,
        test_docker_installs_claude_cli_for_container_login,
        test_runtime_candidate_output_path_is_shared_by_pipeline_and_ui,
        test_claude_auth_flow_is_explicit_and_resumeable,
        test_test_server_persists_editable_influencer_roster,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
