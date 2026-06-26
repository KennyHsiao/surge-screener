#!/usr/bin/env python3
"""Offline checks for test-server deployment artifacts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_workflow() -> None:
    workflow = read(".github/workflows/deploy_test_server.yml")
    require("branches: [main]" in workflow, "deploy workflow must run on main pushes")
    require("self-hosted" in workflow, "workflow must use a self-hosted runner")
    require("surge-screener-test" in workflow, "workflow must target the test-server runner label")
    require("scripts/deploy_test_server.sh" in workflow, "workflow must run deploy script")


def test_deploy_script() -> None:
    script = read("scripts/deploy_test_server.sh")
    require("set -euo pipefail" in script, "deploy script must use strict shell mode")
    require("rsync -a --delete" in script, "deploy script must sync the checked-out commit")
    require("docker compose" in script, "deploy script must use Docker Compose")
    require("up -d --build" in script, "deploy script must rebuild and start the app container")
    require("http://127.0.0.1:${APP_PORT}" in script, "deploy script must health check local Streamlit")
    require("APP_SERVICE" not in script, "deploy script must not reference the removed systemd app service")


def test_docker_artifacts() -> None:
    dockerfile = read("Dockerfile")
    compose = read("docker-compose.yml")
    dockerignore = read(".dockerignore")
    require("FROM python:3.11-slim" in dockerfile, "Dockerfile must pin the Python runtime")
    require("pip install -r requirements.txt" in dockerfile, "Dockerfile must install project requirements")
    require("--server.address" in dockerfile and "0.0.0.0" in dockerfile, "container must bind Streamlit to all interfaces")
    require('"8501:8501"' in compose, "compose must publish port 8501")
    require("restart: unless-stopped" in compose, "compose service must restart unless stopped")
    require("reports/.cache" in dockerignore, ".dockerignore must exclude local cache data")
    require(".venv" in dockerignore, ".dockerignore must exclude local virtualenvs")


def test_requirements_include_analytics_deps() -> None:
    req = read("requirements.txt")
    require("duckdb" in req, "requirements must include duckdb")
    require("pyarrow" in req, "requirements must include pyarrow")


if __name__ == "__main__":
    tests = [
        test_workflow,
        test_deploy_script,
        test_docker_artifacts,
        test_requirements_include_analytics_deps,
    ]
    for test in tests:
        test()
    print(f"deploy artifact tests: {len(tests)} passed")
