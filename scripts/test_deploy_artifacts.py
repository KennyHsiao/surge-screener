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


def test_daily_workflow_persists_candidate_score_snapshots() -> None:
    workflow = read(".github/workflows/surge_screener.yml")
    require("reports/candidate_scores" in workflow,
            "daily workflow must persist scored candidate snapshots under reports/candidate_scores")
    require("scored_candidates.json" in workflow and "candidate_scores" in workflow,
            "daily workflow must copy scored_candidates.json into the reports tree")


def test_options_flow_workflow_runs_forward_validator() -> None:
    workflow = read(".github/workflows/surge_screener.yml")
    require("scripts/options_flow_forward.py" in workflow,
            "options-flow workflow must run the forward validator after the scan")
    require("git add reports/options_flow/" in workflow,
            "options-flow workflow must commit the validation summary with the dated scan")


def test_deploy_script() -> None:
    script = read("scripts/deploy_test_server.sh")
    require("set -euo pipefail" in script, "deploy script must use strict shell mode")
    require("rsync -a --delete" in script, "deploy script must sync the checked-out commit")
    require("python3 -m venv" in script, "deploy script must create a venv")
    require("--without-pip" in script, "deploy script must support servers without ensurepip")
    require("get-pip.py" in script, "deploy script must bootstrap pip without sudo")
    require("requirements.txt" in script, "deploy script must install project requirements")
    require("@anthropic-ai/claude-code" in script, "deploy script must install Claude CLI for auth")
    require("SURGE_APP_ROOT" in script, "deploy script must pass app root to the service")
    require('SURGE_ANALYTICS_DIR="$APP_ROOT/shared/data"' in script,
            "deploy script must keep DuckDB/Parquet under shared data")
    require("analytics_store.py" in script and "refresh" in script
            and '--reports-dir "$RELEASE_DIR/reports"' in script
            and '--analytics-dir "$SURGE_ANALYTICS_DIR"' in script,
            "deploy script must refresh the analytics store after dependency install")
    require("analytics_checks.py" in script and "run" in script
            and '--analytics-dir "$SURGE_ANALYTICS_DIR"' in script
            and '--output "$RELEASE_DIR/reports/analytics_checks/latest.json"' in script
            and "--allow-block" in script,
            "deploy script must publish analytics checks after refresh")
    require("$APP_ROOT/shared/run_status" in script and "reports/run_status" in script
            and "ln -s" in script,
            "deploy script must preserve local run status history across releases")
    require("docker compose -p" in script, "deploy script must stop the legacy Docker deployment")
    require("down --remove-orphans" in script, "deploy script must release the old container port")
    require("systemctl --user restart surge-screener" in script, "deploy script must restart user service")
    require("http://127.0.0.1:${APP_PORT}" in script, "deploy script must health check local Streamlit")


def test_service_template() -> None:
    service = read("deploy/surge-screener.service")
    require("WorkingDirectory=%h/apps/surge-screener/current" in service, "service must run from deployed checkout")
    require("CLAUDE_CONFIG_DIR=%h/apps/surge-screener/.claude" in service, "service must persist Claude auth")
    require("SURGE_APP_ROOT=%h/apps/surge-screener" in service, "service must expose deploy root")
    require("SURGE_ANALYTICS_DIR=%h/apps/surge-screener/shared/data" in service,
            "service must expose the shared DuckDB/Parquet analytics directory")
    require("--server.address 0.0.0.0" in service, "service must bind to private-network interfaces")
    require("--server.port 8501" in service, "service must use port 8501")
    require("Restart=on-failure" in service, "service must restart on failure")


def test_requirements_include_analytics_deps() -> None:
    req = read("requirements.txt")
    require("duckdb" in req, "requirements must include duckdb")
    require("pyarrow" in req, "requirements must include pyarrow")


def test_analytics_connection_doc() -> None:
    doc = read("docs/analytics-store-connection.md")
    require("DuckDB is embedded" in doc, "connection doc must explain DuckDB is not a TCP server")
    require("ssh antigravity" in doc, "connection doc must show the local-to-test-server SSH path")
    require("/home/kenny/apps/surge-screener/shared/data/analytics.duckdb" in doc,
            "connection doc must include the remote database file path")
    require("analytics_checks.py" in doc and "reports/analytics_checks/latest.json" in doc,
            "connection doc must include the automated checks report")


if __name__ == "__main__":
    tests = [
        test_workflow,
        test_daily_workflow_persists_candidate_score_snapshots,
        test_options_flow_workflow_runs_forward_validator,
        test_deploy_script,
        test_service_template,
        test_requirements_include_analytics_deps,
        test_analytics_connection_doc,
    ]
    for test in tests:
        test()
    print(f"deploy artifact tests: {len(tests)} passed")
