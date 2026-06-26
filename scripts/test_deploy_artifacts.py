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
    require("python3 -m venv" in script, "deploy script must create a venv")
    require("requirements.txt" in script, "deploy script must install project requirements")
    require('systemctl --user restart "$APP_SERVICE"' in script, "deploy script must restart user service")
    require("http://127.0.0.1:${APP_PORT}" in script, "deploy script must health check local Streamlit")


def test_service_template() -> None:
    service = read("deploy/surge-screener.service")
    require("WorkingDirectory=%h/apps/surge-screener/current" in service, "service must run from deployed checkout")
    require("--server.address 0.0.0.0" in service, "service must bind to private-network interfaces")
    require("--server.port 8501" in service, "service must use port 8501")
    require("Restart=on-failure" in service, "service must restart on failure")


def test_requirements_include_analytics_deps() -> None:
    req = read("requirements.txt")
    require("duckdb" in req, "requirements must include duckdb")
    require("pyarrow" in req, "requirements must include pyarrow")


if __name__ == "__main__":
    tests = [
        test_workflow,
        test_deploy_script,
        test_service_template,
        test_requirements_include_analytics_deps,
    ]
    for test in tests:
        test()
    print(f"deploy artifact tests: {len(tests)} passed")
