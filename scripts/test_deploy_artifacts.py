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


def test_deploy_workflow_avoids_redundant_scheduled_data_work() -> None:
    workflow = read(".github/workflows/deploy_test_server.yml")
    require("schedule:" not in workflow,
            "main pushes already deploy; a duplicate schedule wastes the self-hosted runner")
    require("workflow_dispatch:" in workflow,
            "deploy workflow must remain manually runnable")
    require("run_source_refresh:" in workflow and "type: boolean" in workflow,
            "manual deploy must expose a source-refresh toggle")
    require("RUN_SOURCE_REFRESH:" in workflow
            and "github.event_name == 'schedule'" not in workflow
            and "inputs.run_source_refresh" in workflow
            and 'RUN_ANALYTICS_REFRESH: "0"' in workflow,
            "deploy workflow must keep long refresh work out of scheduled/push deploys")


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


def test_daily_workflow_schedules_premarket_candidate_refresh() -> None:
    workflow = read(".github/workflows/surge_screener.yml")
    schedules = read("content/schedules.json")
    schedules_ui = read("ui/sys_schedules.py")
    require("'30 12 * * 1-5'" in workflow,
            "daily workflow must schedule premarket candidate refresh at 12:30 UTC weekdays")
    require("'candidate_refresh'" in workflow,
            "manual workflow dispatch must expose candidate_refresh job")
    require("candidate_refresh:" in workflow
            and "inputs.manual_job == 'candidate_refresh'" in workflow,
            "candidate refresh job must be manually runnable")
    require("scripts/run_candidate_pipeline.py" in workflow
            and "--mode full_refresh" in workflow
            and "--money-flow-prefetch-limit 80" in workflow,
            "candidate refresh job must run deterministic full refresh with money-flow prefetch")
    require("reports/analytics_checks/" in workflow,
            "candidate refresh job must persist Analytics checks refreshed by the pipeline")
    require("git add -f filtered_universe.json ranked_candidates.json reports/candidate_rankings/ reports/money_flow/ reports/analytics_checks/" in workflow,
            "candidate refresh job must commit ranked candidates, money flow, and analytics checks")
    require("deploy_after_candidate_refresh:" in workflow
            and "needs: candidate_refresh" in workflow
            and "needs.candidate_refresh.outputs.reports_changed == 'true'" in workflow,
            "candidate refresh reports must trigger an in-workflow test-server deploy")
    require('"id": "us_premarket_candidate_refresh"' in schedules
            and '"cron": "30 12 * * 1-5"' in schedules,
            "UI schedule registry must show the premarket candidate refresh")
    require("def _latest_candidate_refresh_result" in schedules_ui
            and '"candidate_refresh": _latest_candidate_refresh_result' in schedules_ui,
            "schedule UI must render candidate refresh result status")


def test_monthly_reflection_is_manually_runnable_with_90_day_lookback() -> None:
    workflow = read(".github/workflows/surge_screener.yml")
    require("'self_reflection'" in workflow,
            "manual workflow dispatch must expose self_reflection job")
    require("monthly_reflection:" in workflow
            and "inputs.manual_job == 'self_reflection'" in workflow,
            "monthly reflection job must be manually runnable")
    require("--lookback-days 90" in workflow,
            "monthly reflection must use 90 days so sparse ledgers do not produce empty reports")


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
    require('import openai_codex' in script,
            "deploy script must verify the Codex SDK runtime after dependency install")
    require(".requirements.sha256" in script
            and "Python requirements unchanged; skipping dependency install" in script,
            "deploy script must skip unchanged dependency installs")
    require("@anthropic-ai/claude-code" not in script,
            "deploy script must not retain the slow Claude/Node install path")
    require("AGENT_REACH_INSTALL_SOURCE" in script
            and "agent-reach/archive/main.zip" in script
            and 'AGENT_REACH_CHANNELS="${AGENT_REACH_CHANNELS:-twitter}"' in script,
            "deploy script must install Agent Reach Twitter fallback tooling")
    require('TWITTER_CLI_PACKAGE="${TWITTER_CLI_PACKAGE:-twitter-cli}"' in script
            and 'pip install --upgrade "$TWITTER_CLI_PACKAGE"' in script,
            "deploy script must install twitter-cli into the app venv")
    require("install_agent_reach_cli" in script
            and 'agent-reach" install --env=auto --channels="$AGENT_REACH_CHANNELS"' in script
            and "continuing with degraded X fallback" in script,
            "deploy script must keep Agent Reach install optional but attempted")
    require("SURGE_APP_ROOT" in script, "deploy script must pass app root to the service")
    require('RUN_SOURCE_REFRESH="${RUN_SOURCE_REFRESH:-0}"' in script,
            "deploy script must skip external source refresh by default")
    require('RUN_ANALYTICS_REFRESH="${RUN_ANALYTICS_REFRESH:-0}"' in script,
            "deploy script must skip the expensive Analytics DB rebuild by default")
    require('SURGE_ANALYTICS_DIR="$APP_ROOT/shared/data"' in script,
            "deploy script must keep DuckDB/Parquet under shared data")
    require('SURGE_CANDIDATE_OUTPUT_DIR="$APP_ROOT/shared/candidates"' in script,
            "deploy script must keep runtime candidate artifacts under shared storage")
    require('SURGE_INFLUENCERS_PATH="$APP_ROOT/shared/content/influencers.json"' in script,
            "deploy script must keep editable influencer roster under shared storage")
    require("analytics_store.py" in script and "refresh" in script
            and '--reports-dir "$RELEASE_DIR/reports"' in script
            and '--analytics-dir "$SURGE_ANALYTICS_DIR"' in script,
            "deploy script must retain an explicit Analytics DB rebuild path")
    require("ANALYTICS_REFRESH_TIMEOUT_SECONDS" in script
            and 'timeout "$ANALYTICS_REFRESH_TIMEOUT_SECONDS"' in script
            and "keeping the last good DB" in script,
            "optional Analytics rebuild must be bounded and preserve the last good DB")
    require("analytics_checks.py" in script and "run" in script
            and '--analytics-dir "$SURGE_ANALYTICS_DIR"' in script
            and '--output "$RELEASE_DIR/reports/analytics_checks/latest.json"' in script
            and "--allow-block" in script,
            "deploy script must publish analytics checks after refresh")
    require("scripts/continuation_strength.py" in script
            and '--features "$RELEASE_DIR/reports/retrospective/surge_features.json"' in script
            and '--analytics-dir "$SURGE_ANALYTICS_DIR"' in script
            and '--output "$RELEASE_DIR/reports/retrospective/continuation_strength.json"' in script,
            "deploy script must publish continuation-strength validation after analytics refresh")
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
    require("$APP_ROOT/shared/universe" in script and "reports/universe" in script,
            "deploy script must preserve universe snapshots across releases")
    require("$APP_ROOT/shared/market_data/daily_bars" in script
            and "reports/market_data/daily_bars" in script,
            "deploy script must preserve daily bar snapshots across releases")
    require("$APP_ROOT/shared/money_flow" in script and "reports/money_flow" in script,
            "deploy script must preserve money-flow snapshots across releases")
    require("$APP_ROOT/shared/trade_state" in script and "reports/trade_state" in script,
            "deploy script must preserve trade-state snapshots across releases")
    require("$APP_ROOT/shared/analytics_checks" in script and "reports/analytics_checks" in script,
            "deploy script must preserve the scheduled Data Health result across releases")
    require("$APP_ROOT/shared/fundamentals" in script and "reports/fundamentals" in script,
            "deploy script must preserve scheduled fundamental snapshots across releases")
    require("$APP_ROOT/shared/iv_history" in script and "reports/iv_history" in script,
            "deploy script must preserve locally accumulated IV history across releases")
    require("$APP_ROOT/shared/industry_roles" in script and "reports/industry_roles" in script,
            "deploy script must preserve industry-role snapshots across releases")
    require("$APP_ROOT/shared/social_intelligence" in script
            and "reports/social_intelligence" in script,
            "deploy script must preserve social radar snapshots and AI summaries across releases")
    require("$APP_ROOT/shared/social_intelligence_outcomes" in script
            and "reports/social_intelligence_outcomes" in script,
            "deploy script must preserve scheduled social forward outcomes across releases")
    require("$APP_ROOT/shared/x_influencer_picks.json" in script
            and "reports/x_influencer_picks.json" in script,
            "deploy script must preserve the scheduled social quick-pick compatibility artifact")
    require(script.find("reports/social_intelligence") < script.find("rsync -a --delete"),
            "deploy script must migrate existing social radar snapshots before rsync deletes release files")
    require("scripts/data_source_refresh.py" in script
            and script.find("scripts/data_source_refresh.py") < script.find("scripts/analytics_store.py"),
            "deploy script must refresh source artifacts before rebuilding Analytics DB")
    require("skipping source artifact refresh" in script,
            "deploy script must allow push deploys to skip external source refresh")
    require("SOURCE_REFRESH_TIMEOUT_SECONDS" in script
            and "timeout \"$SOURCE_REFRESH_TIMEOUT_SECONDS\"" in script
            and "keeping the last good analytics" in script,
            "deploy script must bound source refresh latency and preserve existing analytics")
    require("ranked_candidates.json" in script and 'ln -sfn "$SURGE_CANDIDATE_OUTPUT_DIR/$artifact"' in script,
            "deploy script must expose shared candidate artifacts through legacy root paths")
    require("docker compose -p" in script, "deploy script must stop the legacy Docker deployment")
    require("down --remove-orphans" in script, "deploy script must release the old container port")
    require("systemctl --user restart surge-screener" in script, "deploy script must restart user service")
    for timer in (
        "surge-candidate-refresh.timer",
        "surge-data-health-refresh.timer",
        "surge-theme-flow-refresh.timer",
    ):
        require(timer in script, f"deploy script must install and enable {timer}")
    require("systemctl --user enable --now" in script,
            "deploy script must activate refresh timers without a manual server step")
    require("systemctl --user is-enabled" in script
            and "systemctl --user is-active" in script,
            "deploy script must verify refresh timers after activation")
    require("http://127.0.0.1:${APP_PORT}" in script, "deploy script must health check local Streamlit")


def test_service_template() -> None:
    service = read("deploy/surge-screener.service")
    require("WorkingDirectory=%h/apps/surge-screener/current" in service, "service must run from deployed checkout")
    require("CODEX_HOME=%h/apps/surge-screener/.codex" in service,
            "service must persist Codex ChatGPT auth")
    require("AGENT_REACH_TWITTER_BIN=%h/apps/surge-screener/.venv/bin/twitter" in service,
            "service must point Agent Reach bridge at the deployed twitter CLI")
    require("%h/apps/surge-screener/.venv/bin" in service,
            "service PATH must include the app venv tools")
    require("SURGE_APP_ROOT=%h/apps/surge-screener" in service, "service must expose deploy root")
    require("SURGE_ANALYTICS_DIR=%h/apps/surge-screener/shared/data" in service,
            "service must expose the shared DuckDB/Parquet analytics directory")
    require("SURGE_CANDIDATE_OUTPUT_DIR=%h/apps/surge-screener/shared/candidates" in service,
            "service must persist runtime candidate artifacts outside the release directory")
    require("SURGE_INFLUENCERS_PATH=%h/apps/surge-screener/shared/content/influencers.json" in service,
            "service must persist editable influencer roster outside the release directory")
    require("--server.address 0.0.0.0" in service, "service must bind to private-network interfaces")
    require("--server.port 8501" in service, "service must use port 8501")
    require("Restart=on-failure" in service, "service must restart on failure")


def test_local_refresh_timer_templates() -> None:
    contracts = {
        "candidate": {
            "calendar": "Mon..Fri *-*-* 20:30:00 Asia/Taipei",
            "command": "scripts/run_candidate_pipeline.py --mode full_refresh",
            "status": "reports/run_status/candidates-local.json",
        },
        "data-health": {
            "calendar": "Tue..Sat *-*-* 06:15:00 Asia/Taipei",
            "command": "scripts/data_source_refresh.py",
            "status": "reports/run_status/data-health-refresh.json",
        },
        "theme-flow": {
            "calendar": "Tue..Sat *-*-* 07:45:00 Asia/Taipei",
            "command": "scripts/theme_flow_background.py --mode refresh_board",
            "status": "reports/run_status/theme-flow-refresh_board.json",
        },
    }

    for name, contract in contracts.items():
        service = read(f"deploy/surge-{name}-refresh.service")
        timer = read(f"deploy/surge-{name}-refresh.timer")
        require("Type=oneshot" in service, f"{name} refresh must be a oneshot service")
        require("WorkingDirectory=%h/apps/surge-screener/current" in service,
                f"{name} refresh must run from the deployed checkout")
        require("EnvironmentFile=-%h/apps/surge-screener/.env" in service,
                f"{name} refresh must load the deployed provider configuration")
        require(contract["command"] in service, f"{name} refresh command mismatch")
        require(contract["status"] in service, f"{name} refresh must update its UI status artifact")
        require(f"OnCalendar={contract['calendar']}" in timer,
                f"{name} refresh calendar or timezone mismatch")
        require("Persistent=true" in timer, f"{name} timer must catch up missed runs")
        require(f"Unit=surge-{name}-refresh.service" in timer,
                f"{name} timer must target its oneshot service")
    data_health_service = read("deploy/surge-data-health-refresh.service")
    require("--include-supplemental" in data_health_service
            and "--supplemental-limit 10" in data_health_service,
            "scheduled Data Health must include the bounded unattended datasets")


def test_schedule_registry_includes_local_refresh_results() -> None:
    schedules = read("content/schedules.json")
    schedules_ui = read("ui/sys_schedules.py")
    for schedule_id in (
        "us_premarket_candidate_refresh",
        "local_data_health_refresh",
        "local_theme_flow_refresh",
    ):
        require(f'"id": "{schedule_id}"' in schedules,
                f"schedule registry missing {schedule_id}")
    require('"result_type": "data_health"' in schedules
            and '"result_type": "theme_flow"' in schedules,
            "local schedules must declare real result readers")
    require('"data_health": _latest_data_health_result' in schedules_ui
            and '"theme_flow": _latest_theme_flow_result' in schedules_ui,
            "schedule UI must render local Data Health and Theme Flow results")
    require("fundamental" in schedules and "Risk Guard" in schedules
            and "social" in schedules.lower() and "IV" in schedules,
            "Data Health schedule must disclose its unattended supplemental datasets")


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
        test_deploy_workflow_avoids_redundant_scheduled_data_work,
        test_daily_workflow_persists_candidate_score_snapshots,
        test_options_flow_workflow_runs_forward_validator,
        test_daily_workflow_runs_no_llm_candidate_outcomes,
        test_daily_workflow_schedules_premarket_candidate_refresh,
        test_monthly_reflection_is_manually_runnable_with_90_day_lookback,
        test_verify_returns_runs_no_picks_alert_notifier,
        test_deploy_script,
        test_service_template,
        test_local_refresh_timer_templates,
        test_schedule_registry_includes_local_refresh_results,
        test_requirements_include_analytics_deps,
        test_analytics_connection_doc,
    ]
    for test in tests:
        test()
    print(f"deploy artifact tests: {len(tests)} passed")
