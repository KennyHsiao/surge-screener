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


def test_daily_workflow_runs_no_llm_candidate_outcomes() -> None:
    workflow = read(".github/workflows/surge_screener.yml")
    require("'35 23 * * 1-5'" in workflow,
            "daily workflow must schedule no-LLM candidate paper outcomes after market close")
    require("manual_job == 'candidate_outcomes'" in workflow,
            "candidate outcomes job must be manually runnable")
    require("scripts/03_rank_candidates.py" in workflow and "--options-gate-limit 0" in workflow,
            "candidate outcomes job must use deterministic ranking without options/LLM gates")
    require("scripts/candidate_outcomes.py" in workflow,
            "candidate outcomes job must update candidate paper outcomes")
    require("git add -f reports/candidate_rankings/ reports/candidate_outcomes/" in workflow,
            "candidate outcomes job must force-add ignored ranking snapshots and outcomes")
    require("report_commit_sha: ${{ steps.commit_reports.outputs.report_commit_sha }}" in workflow
            and "reports_changed: ${{ steps.commit_reports.outputs.reports_changed }}" in workflow,
            "candidate outcomes job must expose the pushed report commit for deployment")
    require("deploy_after_candidate_outcomes:" in workflow
            and "needs: candidate_outcomes" in workflow
            and "needs.candidate_outcomes.outputs.reports_changed == 'true'" in workflow,
            "candidate outcomes reports must trigger an in-workflow test-server deploy")
    require("ref: ${{ needs.candidate_outcomes.outputs.report_commit_sha }}" in workflow
            and "scripts/deploy_test_server.sh" in workflow,
            "candidate outcome deploy must checkout the pushed report commit and run deploy script")


def test_verify_returns_runs_no_picks_alert_notifier() -> None:
    workflow = read(".github/workflows/surge_screener.yml")
    require("scripts/07_verify_returns.py" in workflow,
            "verify returns job must keep updating the performance ledger")
    require("scripts/analytics_store.py refresh" in workflow
            and "--analytics-dir /tmp/surge-analytics" in workflow,
            "verify returns job must refresh a temporary analytics store for checks")
    require("scripts/analytics_checks.py run" in workflow
            and "--output reports/analytics_checks/latest.json" in workflow
            and "--allow-block" in workflow,
            "verify returns job must publish analytics checks before notifying")
    require("scripts/analytics_action_notify.py" in workflow
            and "--checks reports/analytics_checks/latest.json" in workflow
            and "--receipts reports/analytics_checks/no_picks_alerts.json" in workflow,
            "verify returns job must run the no-picks Telegram notifier with durable receipts")
    require("TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}" in workflow
            and "TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}" in workflow,
            "no-picks notifier must reuse existing Telegram secrets")
    require("git add -f reports/analytics_checks/no_picks_alerts.json" in workflow,
            "no-picks receipt is ignored and must be force-added when present")


def test_deploy_script() -> None:
    script = read("scripts/deploy_test_server.sh")
    require("set -euo pipefail" in script, "deploy script must use strict shell mode")
    require("rsync -a --delete" in script, "deploy script must sync the checked-out commit")
    require("python3 -m venv" in script, "deploy script must create a venv")
    require("--without-pip" in script, "deploy script must support servers without ensurepip")
    require("get-pip.py" in script, "deploy script must bootstrap pip without sudo")
    require("requirements.txt" in script, "deploy script must install project requirements")
    require("requirements-ibkr.txt" in script,
            "deploy script must install optional IBKR requirements on the test server")
    require("@anthropic-ai/claude-code" in script, "deploy script must install Claude CLI for auth")
    require("SURGE_APP_ROOT" in script, "deploy script must pass app root to the service")
    require('SURGE_ANALYTICS_DIR="$APP_ROOT/shared/data"' in script,
            "deploy script must keep DuckDB/Parquet under shared data")
    require('SURGE_CANDIDATE_OUTPUT_DIR="$APP_ROOT/shared/candidates"' in script,
            "deploy script must keep runtime candidate artifacts under shared storage")
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
    require("$APP_ROOT/shared/candidate_rankings" in script and "reports/candidate_rankings" in script
            and "ln -s" in script,
            "deploy script must preserve local candidate ranking snapshots across releases")
    require("$APP_ROOT/shared/risk_guard" in script and "reports/risk_guard" in script
            and "ln -s" in script,
            "deploy script must preserve local Risk Guard snapshots across releases")
    require("$APP_ROOT/shared/reconciliation.json" in script
            and "reports/reconciliation.json" in script
            and "ln -sfn" in script,
            "deploy script must preserve local IBKR reconciliation across releases")
    require("$APP_ROOT/shared/theme_flow_snapshot.json" in script
            and "reports/theme_flow_snapshot.json" in script
            and "$APP_ROOT/shared/theme_flow_snapshots" in script
            and "reports/theme_flow_snapshots" in script,
            "deploy script must preserve Theme Flow snapshots across releases")
    require("$APP_ROOT/shared/sector_rotation.json" in script
            and "reports/sector_rotation.json" in script
            and "$APP_ROOT/shared/sector_rotation_snapshots" in script
            and "reports/sector_rotation_snapshots" in script,
            "deploy script must preserve Sector Rotation snapshots across releases")
    require("ranked_candidates.json" in script and 'ln -sfn "$SURGE_CANDIDATE_OUTPUT_DIR/$artifact"' in script,
            "deploy script must expose shared candidate artifacts through legacy root paths")
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
    require("SURGE_CANDIDATE_OUTPUT_DIR=%h/apps/surge-screener/shared/candidates" in service,
            "service must persist runtime candidate artifacts outside the release directory")
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
        test_daily_workflow_runs_no_llm_candidate_outcomes,
        test_verify_returns_runs_no_picks_alert_notifier,
        test_deploy_script,
        test_service_template,
        test_requirements_include_analytics_deps,
        test_analytics_connection_doc,
    ]
    for test in tests:
        test()
    print(f"deploy artifact tests: {len(tests)} passed")
