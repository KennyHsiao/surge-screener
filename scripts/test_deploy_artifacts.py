#!/usr/bin/env python3
"""Offline checks for test-server deployment artifacts."""

import importlib.util
import os
import shlex
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def active_directives(unit: str) -> dict[str, dict[str, list[str]]]:
    sections: dict[str, dict[str, list[str]]] = {}
    current_section: str | None = None
    for raw_line in unit.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1]
            sections.setdefault(current_section, {})
            continue
        key, separator, value = line.partition("=")
        if separator and current_section is not None:
            sections[current_section].setdefault(key.strip(), []).append(value.strip())
    return sections


def load_module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    require(spec is not None and spec.loader is not None,
            f"cannot load module spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workflow() -> None:
    workflow = read(".github/workflows/deploy_test_server.yml")
    require("branches: [main]" in workflow, "deploy workflow must run on main pushes")
    require("self-hosted" in workflow, "workflow must use a self-hosted runner")
    require("surge-screener-test" in workflow, "workflow must target the test-server runner label")
    require("scripts/deploy_test_server.sh" in workflow, "workflow must run deploy script")


def test_workflows_pin_approved_node24_actions() -> None:
    approved = {
        "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09": "v5.1.0",
        "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1": "v6.3.0",
        "actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f": "v6.0.0",
    }
    seen: set[str] = set()
    for path in (".github/workflows/deploy_test_server.yml",
                 ".github/workflows/surge_screener.yml"):
        for line in read(path).splitlines():
            if "uses: actions/" not in line:
                continue
            reference = line.split("uses:", 1)[1].split("#", 1)[0].strip()
            require(reference in approved,
                    f"{path} contains an unapproved or floating action: {reference}")
            require(f"# {approved[reference]}" in line,
                    f"{path} must document the release for {reference}")
            seen.add(reference)
    require(seen == set(approved), "workflows must exercise every approved Node 24 action")


def test_phase7e_deployment_freeze_covers_every_deploy_lane() -> None:
    deploy_workflow = read(".github/workflows/deploy_test_server.yml")
    daily_workflow = read(".github/workflows/surge_screener.yml")
    freeze_guard = "vars.PHASE7E_DEPLOY_FREEZE != 'true'"

    require(deploy_workflow.count(freeze_guard) == 1
            and f"  deploy:\n    if: {freeze_guard}\n" in deploy_workflow,
            "Phase 7E freeze must guard the normal main/manual deployment job")
    require(daily_workflow.count(freeze_guard) == 2,
            "Phase 7E freeze must guard exactly the two candidate deployment jobs")
    require(f"  deploy_after_candidate_refresh:\n    needs: candidate_refresh\n"
            f"    if: {freeze_guard} && needs.candidate_refresh.result == 'success'"
            in daily_workflow,
            "Phase 7E freeze must guard candidate-refresh deployment")
    require(f"  deploy_after_candidate_outcomes:\n    needs: candidate_outcomes\n"
            f"    if: {freeze_guard} && needs.candidate_outcomes.result == 'success'"
            in daily_workflow,
            "Phase 7E freeze must guard candidate-outcomes deployment")


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
    require("scripts/persist_candidate_scores.py" in workflow,
            "daily workflow must persist scored candidates through the provenance helper")
    required = ('SCREEN_CANDIDATE_LIMIT: "25"\n      CODEX_SDK_TIMEOUT: "120"\n      CODEX_RETRY_MAX_ATTEMPTS: "1"',
                "scripts/03_rank_candidates.py", '--history-dir ""', "--input ranked_candidates.json", "--input layer2_input.json", "--max-layers 1", "--max-nodes-per-candidate 3", "--max-candidates 5",
                "--candidate-retries 1", "--deferred-retries 1", 'score_limits.items()',
                "persist_candidate_scores.py", "skipping selection-biased retrospective")
    require(all(token in workflow for token in required) and "ranked_candidates.json" in workflow.split("Upload artifacts", 1)[1],
            "daily screener must bound and validate the Codex pool without biasing retrospectives")


def test_daily_report_publish_uses_race_safe_helper() -> None:
    workflow = read(".github/workflows/surge_screener.yml")
    upload_step = workflow.split("- name: Upload artifacts", 1)[1].split(
        "- name: Commit reports back to repo", 1,
    )[0]
    publish_step = workflow.split("- name: Commit reports back to repo", 1)[1].split(
        "  # ──────────────────────────────────────────────────────────────", 1,
    )[0]
    require("if: always()" in upload_step and "continue-on-error: true" in upload_step,
            "diagnostic upload must not prevent the authoritative report push")
    require("scripts/publish_reports.py" in publish_step,
            "EOD reports must use the tested bounded publisher")
    require("--discard-runtime-outputs" in publish_step,
            "uploaded runtime outputs must be explicitly discarded after publication")
    require('--source-ref "${{ github.ref }}"' in publish_step,
            "report publication must reject a manual run from a non-main source ref")
    require("git pull --rebase origin main" not in publish_step,
            "untested inline rebase retry must not remain in the EOD publisher")


def test_telegram_failure_does_not_suppress_authoritative_report_publication() -> None:
    workflow = read(".github/workflows/surge_screener.yml")
    notify_step = workflow.split("- name: Stage 5 — Push to Telegram", 1)[1].split(
        "- name: Stage 6 — Append picks to Performance Ledger", 1,
    )[0]
    require("continue-on-error: true" in notify_step,
            "Telegram delivery must not suppress report persistence")


def test_one_time_natural_validation_observer_contract() -> None:
    service = read("deploy/surge-natural-validation-20260818.service")
    timer = read("deploy/surge-natural-validation-20260818.timer")
    require("scripts/natural_validation_observer.py" not in service,
            "observer must execute from deploy-stable ops storage, not current/")
    require("ops/natural-validation-20260818/natural_validation_observer.py" in service,
            "observer service must use the isolated ops copy")
    require("shared/natural-validation/2026-08-18" in service,
            "observer evidence must survive application deployments")
    require("ExecStartPre=/usr/bin/install -d -m 0700 "
            "/home/kenny/apps/surge-screener/shared/natural-validation/2026-08-18" in service,
            "observer must create its log directory before systemd opens StandardOutput")
    require("--required-base-sha f181d814f0fc71aea4c49dd0738f8085aebc8d41" in service,
            "observer must bind evidence to the reviewed Analytics remediation")
    require(service.count("--expected-hash=") >= 8,
            "observer must bind all critical runtime and producer-unit hashes")
    require("OnCalendar=2026-08-18 05:50:00 Asia/Taipei" in timer,
            "observer must start before the first natural validation producer")
    require("Persistent=true" in timer and "RandomizedDelaySec=0" in timer,
            "one-time observer timer must be exact and recover missed activation")


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
    gate = read("scripts/deploy_service_gate.sh")
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
    require("SURGE_INTERNAL_API_ENV_FILE" in script
            and "secrets.token_urlsafe(48)" in script
            and 'if [ -L "$SURGE_INTERNAL_API_ENV_FILE" ]' in script
            and 'chmod 0600 "$SURGE_INTERNAL_API_ENV_FILE"' in script,
            "deploy script must create and protect the shared internal API credential")
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
    require("analytics_refresh_transaction.py" in script
            and '--reports-dir "$RELEASE_DIR/reports"' in script
            and '--published-reports-dir "$SURGE_PUBLISHED_REPORTS_DIR"' in script
            and '--analytics-dir "$SURGE_ANALYTICS_DIR"' in script,
            "deploy script must retain a transactional Analytics DB rebuild path")
    require("ANALYTICS_REFRESH_TIMEOUT_SECONDS" in script
            and 'timeout "$ANALYTICS_REFRESH_TIMEOUT_SECONDS"' in script
            and "keeping the last good DB" in script,
            "optional Analytics rebuild must be bounded and preserve the last good DB")
    require('SURGE_PUBLISHED_REPORTS_DIR="$APP_ROOT/shared/published_reports/current/reports"' in script
            and 'SURGE_ANALYTICS_LOCK="$APP_ROOT/shared/locks/analytics-refresh.lock"' in script
            and "$APP_ROOT/shared/post_ingestion" in script,
            "deploy script must provision the durable report mirror, verdicts, and shared lock")
    require("analytics_refresh_transaction.py" in script
            and '--checks-output "$RELEASE_DIR/reports/analytics_checks/latest.json"' in script
            and "--allow-block" in script,
            "transactional deploy refresh must publish Analytics checks")
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
    require('chmod 0700 "$APP_ROOT/shared/industry_roles"' in script,
            "deploy script must keep canonical Industry Roles state operator-private")
    require("scripts/industry_role_admin.py" in script
            and '--content-dir "$RELEASE_DIR/content"' in script
            and '--reports-dir "$RELEASE_DIR/reports"' in script,
            "deploy script must emit side-effect-free Industry Roles state health evidence")
    require(script.find('ln -s "$APP_ROOT/shared/industry_roles"')
            < script.find('"$RELEASE_DIR/scripts/industry_role_admin.py"')
            < script.find('bash "$SERVICE_GATE"'),
            "Industry Roles state health must inspect shared storage before service activation")
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
            and script.find("scripts/data_source_refresh.py") < script.find("scripts/analytics_refresh_transaction.py"),
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
    require('bash "$SERVICE_GATE"' in script,
            "deploy script must execute the behavior-tested service gate")
    gate_call_start = script.find('if ! API_SERVICE_SOURCE="$API_SERVICE_SOURCE"')
    gate_call_end = script.find('systemctl --user enable "$APP_SERVICE"')
    require(-1 not in (gate_call_start, gate_call_end) and gate_call_start < gate_call_end,
            "deploy script must have an explicit service-gate failure block")
    gate_call = script[gate_call_start:gate_call_end]
    expected_gate_call = r'''if ! API_SERVICE_SOURCE="$API_SERVICE_SOURCE" \
  API_SERVICE_TARGET="$API_SERVICE_TARGET" \
  API_SERVICE="$API_SERVICE" \
  APP_SERVICE="$APP_SERVICE" \
  API_PORT="$API_PORT" \
  APP_PORT="$APP_PORT" \
  PYTHON_BIN="$VENV_DIR/bin/python" \
  API_HEALTH_CHECK="$RELEASE_DIR/scripts/api_health_check.py" \
  API_HEALTH_URL="http://127.0.0.1:${API_PORT}/healthz" \
  STREAMLIT_HEALTH_URL="http://127.0.0.1:${APP_PORT}/_stcore/health" \
  STREAMLIT_ROOT_URL="http://127.0.0.1:${APP_PORT}" \
  bash "$SERVICE_GATE"; then
  echo "deploy: service gate failed" >&2
  exit 1
fi'''
    require(gate_call.strip() == expected_gate_call,
            "deploy script must preserve the exact fail-closed service-gate wiring")
    success_exits = [
        index for index, line in enumerate(script.splitlines())
        if line.strip() == "exit 0"
    ]
    last_timer_gate = script.rfind('systemctl --user is-active --quiet "$timer"')
    success_exit = script.find("\nexit 0\n")
    require(len(success_exits) == 1
            and -1 not in (last_timer_gate, success_exit)
            and last_timer_gate < success_exit
            and gate_call_end < success_exit,
            "deploy script must have one success exit after service and timer gates")
    require('systemctl --user restart "$APP_SERVICE"' in gate,
            "service gate must restart the Streamlit user service")
    for timer in (
        "surge-candidate-refresh.timer",
        "surge-data-health-refresh.timer",
        "surge-post-producer-analytics.timer",
        "surge-theme-flow-refresh.timer",
    ):
        require(timer in script, f"deploy script must install and enable {timer}")
    require("systemctl --user enable --now" in script,
            "deploy script must activate refresh timers without a manual server step")
    require("systemctl --user is-enabled" in script
            and "systemctl --user is-active" in script,
            "deploy script must verify refresh timers after activation")
    require("http://127.0.0.1:${APP_PORT}" in script
            and 'curl --noproxy \'*\' -fsS "$STREAMLIT_HEALTH_URL"' in gate,
            "service gate must health check local Streamlit directly")

    require('API_PORT=8000' in script and 'API_SERVICE="surge-screener-api"' in script,
            "deploy script must use the fixed loopback API service and port")
    require('deploy/surge-screener-api.service' in script,
            "deploy script must install the API unit template")
    require('systemctl --user enable "$API_SERVICE"' in gate
            and 'systemctl --user restart "$API_SERVICE"' in gate,
            "service gate must enable and restart the API service")
    require(gate.count('systemctl --user is-active --quiet "$API_SERVICE"') >= 2
            and gate.count('property MainPID --value') >= 2,
            "API readiness must require an active unit with a MainPID")
    require('scripts/api_health_check.py' in script
            and 'http://127.0.0.1:${API_PORT}/healthz' in script,
            "deploy script must validate the exact API health endpoint")
    require('api_lifecycle_failure' in gate
            and 'journalctl --user -u "$API_SERVICE"' in gate,
            "every API lifecycle failure must emit API-specific diagnostics")
    expected_transient_helper = r'''  systemd-run --user --quiet --wait --pipe --collect --service-type=exec \
    "$PYTHON_BIN" "$API_HEALTH_CHECK" \
    "$API_HEALTH_URL" "$main_pid" --host 127.0.0.1 --port "$API_PORT" \
    "$@"'''
    require(expected_transient_helper in gate,
            "health helper must execute inside the systemd user manager namespace")
    expected_helper_call = '''  run_api_health_check "$main_pid_before" || return 1'''
    require(expected_helper_call in gate,
            "service gate must invoke the configured exact-health helper command")
    require('HEALTH_ATTEMPTS="${HEALTH_ATTEMPTS:-45}"' in gate,
            "service gate must retain the 45-attempt production retry budget")

    api_restart = gate.find('systemctl --user restart "$API_SERVICE"')
    api_healthy = gate.find("deploy: API service is healthy")
    streamlit_restart = gate.find('systemctl --user restart "$APP_SERVICE"')
    streamlit_healthy = gate.find("deploy: Streamlit app is healthy")
    require(-1 not in (api_restart, api_healthy, streamlit_restart, streamlit_healthy),
            "deploy script is missing a required service gate")
    require(api_restart < api_healthy < streamlit_restart < streamlit_healthy,
            "API must be healthy before Streamlit restarts and before success")


def test_service_template() -> None:
    service = read("deploy/surge-screener.service")
    sections = active_directives(service)
    unit_directives = sections.get("Unit", {})
    require(
        unit_directives.get("After")
        == ["network-online.target surge-screener-api.service"],
        "Streamlit unit must start after the network and loopback API unit",
    )
    require(
        unit_directives.get("Wants") == ["network-online.target"],
        "Streamlit unit must retain network-online ordering",
    )
    require(
        unit_directives.get("Requires") == ["surge-screener-api.service"],
        "Streamlit unit must fail closed when its required API unit cannot start",
    )
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
    require("EnvironmentFile=%h/apps/surge-screener/shared/runtime/internal-api.env" in service,
            "Streamlit must load the dedicated internal API credential")
    require("ReadOnlyPaths=%h/apps/surge-screener/shared/industry_roles" in service,
            "Streamlit must not have a filesystem writer fallback for review state")
    require("--server.address 0.0.0.0" in service, "service must bind to private-network interfaces")
    require("--server.port 8501" in service, "service must use port 8501")
    require("Restart=on-failure" in service, "service must restart on failure")


def test_post_producer_service_restarts_for_crash_recovery() -> None:
    service = read("deploy/surge-post-producer-analytics.service")
    directives = active_directives(service).get("Service", {})
    require(
        directives.get("Restart") == ["on-abnormal"],
        "post-producer observer must restart after a signal or timeout",
    )
    require(
        directives.get("RestartSec") == ["5"],
        "post-producer crash recovery restart delay must be bounded",
    )


def test_api_service_template() -> None:
    service = read("deploy/surge-screener-api.service")
    sections = active_directives(service)
    unit_directives = sections.get("Unit", {})
    directives = sections.get("Service", {})
    install_directives = sections.get("Install", {})
    spaced = active_directives("[Service]\nSetCredential = secret:value\n")
    require(spaced.get("Service", {}).get("SetCredential") == ["secret:value"],
            "systemd parser must normalize directive whitespace before security checks")

    require(unit_directives.get("After") == ["network-online.target"]
            and unit_directives.get("Wants") == ["network-online.target"],
            "API unit ordering must be active under [Unit]")
    require(directives.get("Type") == ["simple"], "API service must use Type=simple")
    require(directives.get("WorkingDirectory") == ["%h/apps/surge-screener/current"],
            "API service must run from the deployed checkout")
    require(directives.get("Restart") == ["on-failure"]
            and directives.get("RestartSec") == ["5"]
            and directives.get("TimeoutStopSec") == ["15"],
            "API service lifecycle settings must be explicit")
    require(install_directives.get("WantedBy") == ["default.target"],
            "API service must be installable by the user manager")

    exec_values = directives.get("ExecStart", [])
    require(len(exec_values) == 1, "API service must have exactly one ExecStart")
    tokens = shlex.split(exec_values[0])
    expected = [
        "/usr/bin/env", "-i",
        "HOME=/nonexistent", "LANG=C.UTF-8", "PATH=/usr/bin:/bin",
        "PYTHONUNBUFFERED=1", "PYTHONDONTWRITEBYTECODE=1",
        "SURGE_CANDIDATE_OUTPUT_DIR=%h/apps/surge-screener/shared/candidates",
        "SURGE_INFLUENCERS_PATH=%h/apps/surge-screener/shared/content/influencers.json",
        "SURGE_INTERNAL_API_TOKEN_FILE=${CREDENTIALS_DIRECTORY}/internal-api-env",
        "%h/apps/surge-screener/.venv/bin/python", "-m", "uvicorn", "api.main:app",
        "--host", "127.0.0.1", "--port", "8000", "--workers", "1",
        "--no-proxy-headers", "--no-server-header", "--no-access-log",
    ]
    require(tokens == expected,
            "API ExecStart must be the exact clean-environment loopback command")
    require("%d/internal-api-env" not in service,
            "API ExecStart must use the credential environment exported by systemd")

    require(directives.get("LoadCredential") == [
        "internal-api-env:%h/apps/surge-screener/shared/runtime/internal-api.env"
    ], "API service must load only the dedicated internal credential")
    forbidden_credential_directives = {
        "Environment", "EnvironmentFile", "PassEnvironment",
        "LoadCredentialEncrypted", "ImportCredential",
        "SetCredential", "SetCredentialEncrypted",
    }
    require(not forbidden_credential_directives.intersection(directives),
            "API service must not inherit provider or inline credentials")
    unsupported_user_service_directives = {
        "CapabilityBoundingSet", "PrivateTmp", "ProtectSystem", "ProtectHome",
        "ReadWritePaths",
    }
    require(not unsupported_user_service_directives.intersection(directives),
            "API service must avoid sandboxing unsupported by the user manager")
    hardening = {
        "NoNewPrivileges": "yes",
        "RestrictSUIDSGID": "yes",
        "LockPersonality": "yes",
        "UMask": "0077",
        "RestrictAddressFamilies": "AF_UNIX AF_INET",
    }
    for directive, value in hardening.items():
        require(directives.get(directive) == [value],
                f"API service hardening mismatch: {directive}")


def test_api_health_validator_contract() -> None:
    health = load_module("scripts/api_health_check.py", "api_health_check_under_test")
    source = read("scripts/api_health_check.py")
    require('"ss", "-H", "-ltnp"' in source and 'pid=' in source,
            "API health validator must correlate the listener with MainPID")
    require('"net/tcp"' in source and '"net/tcp6"' in source and 'socket:' in source,
            "API health validator must provide a strict procfs ownership fallback")
    valid_payloads = [
        b'{"status":"ok","apiVersion":"v1"}',
        b'{ "apiVersion": "v1", "status": "ok" }',
    ]
    for payload in valid_payloads:
        require(health.is_expected_health_response(200, "application/json", payload),
                "semantic exact API health payload must pass")

    invalid_responses = [
        (201, "application/json", valid_payloads[0]),
        (200, "text/html", valid_payloads[0]),
        (200, "application/json", b'{"status":"ok","apiVersion":"v1","extra":null}'),
        (200, "application/json", b'{"status":"ok","apiVersion":"v2"}'),
        (200, "application/json", b'[]'),
        (200, "application/json", b'null'),
        (200, "application/json", b''),
        (200, "application/json", b'{'),
    ]
    for status, content_type, payload in invalid_responses:
        require(not health.is_expected_health_response(status, content_type, payload),
                "non-exact API health response must fail")

    owned = ('LISTEN 0 2048 127.0.0.1:8000 0.0.0.0:* '
             'users:(("python",pid=321,fd=6))')
    stale = owned.replace("pid=321", "pid=999")
    wildcard = owned.replace("127.0.0.1:8000", "0.0.0.0:8000")
    require(health.listener_is_owned(owned, 321, "127.0.0.1", 8000),
            "the sole IPv4 loopback listener owned by MainPID must pass")
    for output in ("", stale, wildcard, f"{owned}\n{wildcard}"):
        require(not health.listener_is_owned(output, 321, "127.0.0.1", 8000),
                "stale, wildcard, missing, or duplicate listeners must fail")

    with tempfile.TemporaryDirectory() as raw_proc:
        proc_root = Path(raw_proc)
        net = proc_root / "net"
        descriptors = proc_root / "321" / "fd"
        net.mkdir()
        descriptors.mkdir(parents=True)
        header = ("  sl  local_address rem_address   st tx_queue rx_queue tr tm->when "
                  "retrnsmt   uid  timeout inode\n")
        listener_row = ("   0: 0100007F:1F40 00000000:0000 0A 00000000:00000000 "
                        "00:00000000 00000000  1002 0 54321 1 0000000000000000\n")
        (net / "tcp").write_text(header + listener_row, encoding="ascii")
        (net / "tcp6").write_text(header, encoding="ascii")
        (descriptors / "6").symlink_to("socket:[54321]")
        require(health.proc_listener_is_owned(
            321, "127.0.0.1", 8000, proc_root=proc_root,
        ), "procfs fallback must correlate the sole loopback socket inode with MainPID")

        (net / "tcp6").write_text(
            header + listener_row.replace("0100007F", "00000000000000000000000000000000"),
            encoding="ascii",
        )
        require(not health.proc_listener_is_owned(
            321, "127.0.0.1", 8000, proc_root=proc_root,
        ), "procfs fallback must reject an additional IPv6 or wildcard listener")
        (net / "tcp6").write_text(header, encoding="ascii")
        (descriptors / "6").unlink()
        (descriptors / "6").symlink_to("socket:[99999]")
        require(not health.proc_listener_is_owned(
            321, "127.0.0.1", 8000, proc_root=proc_root,
        ), "procfs fallback must reject a listener not held by MainPID")

    for invalid_response in invalid_responses:
        owned_pair = iter((owned, owned))
        require(not health.api_is_ready(
            "http://127.0.0.1:8000/healthz", 321, "127.0.0.1", 8000,
            listener_probe=lambda _port, pair=owned_pair: next(pair),
            response_probe=lambda _url, response=invalid_response: response,
        ), "api_is_ready must reject every non-exact health response")

    owned_twice = iter((owned, owned))
    exact_response = (200, "application/json", valid_payloads[0])
    require(health.api_is_ready(
        "http://127.0.0.1:8000/healthz", 321, "127.0.0.1", 8000,
        listener_probe=lambda _port: next(owned_twice),
        response_probe=lambda _url: exact_response,
    ), "stable listener ownership around exact health must pass")
    no_pid = owned.split(" users:", 1)[0]
    no_pid_pair = iter((no_pid, no_pid))
    require(health.api_is_ready(
        "http://127.0.0.1:8000/healthz", 321, "127.0.0.1", 8000,
        listener_probe=lambda _port: next(no_pid_pair),
        response_probe=lambda _url: exact_response,
        proc_probe=lambda _pid, _host, _port: True,
    ), "procfs must recover exact ownership when ss omits process metadata")
    require(not health.api_is_ready(
        "http://127.0.0.1:8000/healthz", 321, "127.0.0.1", 8000,
        listener_probe=lambda _port: stale,
        response_probe=lambda _url: exact_response,
        proc_probe=lambda _pid, _host, _port: True,
    ), "procfs must not override contradictory ss PID evidence")
    replaced = iter((owned, stale))
    require(not health.api_is_ready(
        "http://127.0.0.1:8000/healthz", 321, "127.0.0.1", 8000,
        listener_probe=lambda _port: next(replaced),
        response_probe=lambda _url: exact_response,
    ), "listener replacement during health validation must fail")

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/healthz":
                self.send_response(302)
                self.send_header("Location", "/other")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(valid_payloads[0])

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/healthz"
        require(health._health_response(url) is None,
                "health validation must reject redirects")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    cli_args = [
        "http://127.0.0.1:8000/healthz", "321", "--host", "127.0.0.1",
        "--port", "8000",
    ]
    observed: list[tuple[str, int, str, int]] = []

    def ready_check(url: str, main_pid: int, host: str, port: int) -> bool:
        observed.append((url, main_pid, host, port))
        return True

    require(health.main(cli_args, ready_check=ready_check) == 0,
            "health CLI must exit zero only when the combined readiness check passes")
    require(observed == [("http://127.0.0.1:8000/healthz", 321, "127.0.0.1", 8000)],
            "health CLI must pass parsed arguments to the combined readiness check")
    require(health.main(cli_args, ready_check=lambda *_args: False) == 1,
            "health CLI must propagate a failed combined readiness check")

    default_observed: list[tuple[str, int, str, int]] = []

    def default_ready_check(url: str, main_pid: int, host: str, port: int) -> bool:
        default_observed.append((url, main_pid, host, port))
        return False

    original_ready_check = health.api_is_ready
    health.api_is_ready = default_ready_check
    try:
        require(health.main(cli_args) == 1,
                "health CLI default must propagate the real combined readiness result")
    finally:
        health.api_is_ready = original_ready_check
    require(default_observed == [
        ("http://127.0.0.1:8000/healthz", 321, "127.0.0.1", 8000)
    ], "health CLI default must resolve api_is_ready at runtime")


def test_api_service_gate_behavior() -> None:
    gate_path = ROOT / "scripts/deploy_service_gate.sh"

    def write_executable(path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)

    def run_gate(
        scenario: str,
        attempts: str = "1",
    ) -> tuple[subprocess.CompletedProcess[str], list[str]]:
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            bin_dir = tmp / "bin"
            bin_dir.mkdir()
            log = tmp / "commands.log"
            state = tmp / "pid-state"
            python_state = tmp / "python-state"
            curl_state = tmp / "curl-state"
            source = tmp / "surge-screener-api.service"
            target = tmp / "systemd" / "surge-screener-api.service"
            health_check = tmp / "api_health_check.py"
            target.parent.mkdir()
            source.write_text("[Service]\nExecStart=/bin/true\n", encoding="utf-8")
            health_check.write_text("# test helper\n", encoding="utf-8")

            write_executable(bin_dir / "systemctl", """#!/usr/bin/env bash
set -u
printf 'systemctl %s\n' "$*" >> "$STUB_LOG"
if [[ "$*" == "--user daemon-reload" && "$SCENARIO" == "daemon_reload_failure" ]]; then
  exit 1
fi
if [[ "$*" == "--user enable surge-screener-api" && "$SCENARIO" == "enable_failure" ]]; then
  exit 1
fi
if [[ "$*" == "--user restart surge-screener-api" && "$SCENARIO" == "api_restart_failure" ]]; then
  exit 1
fi
if [[ "$*" == "--user restart surge-screener" && "$SCENARIO" == "streamlit_restart_failure" ]]; then
  exit 1
fi
if [[ "${2:-}" == "is-active" ]]; then
  if [[ "$SCENARIO" == "inactive_api" && "${4:-}" == "surge-screener-api" ]]; then
    exit 1
  fi
  exit 0
fi
if [[ "${2:-}" == "show" ]]; then
  if [[ "$SCENARIO" == "zero_pid" ]]; then
    printf '0\n'
    exit 0
  fi
  if [[ "$SCENARIO" == "changed_pid" ]]; then
    count=0
    if [[ -f "$STUB_STATE" ]]; then
      read -r count < "$STUB_STATE"
    fi
    count=$((count + 1))
    printf '%s\n' "$count" > "$STUB_STATE"
    if [[ "$count" -eq 1 ]]; then
      printf '321\n'
    else
      printf '322\n'
    fi
    exit 0
  fi
  printf '321\n'
fi
""")
            write_executable(bin_dir / "journalctl", """#!/usr/bin/env bash
printf 'journalctl %s\n' "$*" >> "$STUB_LOG"
""")
            write_executable(bin_dir / "install", """#!/usr/bin/env bash
printf 'install %s\n' "$*" >> "$STUB_LOG"
if [[ "$SCENARIO" == "install_failure" ]]; then
  exit 1
fi
/usr/bin/install "$@"
""")
            write_executable(bin_dir / "curl", """#!/usr/bin/env bash
printf 'curl %s\n' "$*" >> "$STUB_LOG"
if [[ "$SCENARIO" == "streamlit_health_failure" ]]; then
  exit 1
fi
if [[ "$SCENARIO" == "streamlit_root_fallback" && "$*" == *"/_stcore/health"* ]]; then
  exit 1
fi
if [[ "$SCENARIO" == "transient_streamlit" ]]; then
  count=0
  if [[ -f "$STUB_CURL_STATE" ]]; then
    read -r count < "$STUB_CURL_STATE"
  fi
  count=$((count + 1))
  printf '%s\n' "$count" > "$STUB_CURL_STATE"
  if [[ "$count" -le 2 ]]; then
    exit 1
  fi
fi
""")
            write_executable(bin_dir / "sleep", """#!/usr/bin/env bash
printf 'sleep %s\n' "$*" >> "$STUB_LOG"
""")
            write_executable(bin_dir / "systemd-run", """#!/usr/bin/env bash
printf 'systemd-run %s\n' "$*" >> "$STUB_LOG"
if [[ "$SCENARIO" == "transient_unit_failure" ]]; then
  exit 1
fi
while [[ "$#" -gt 0 && "$1" == -* ]]; do
  shift
done
if [[ "$#" -eq 0 ]]; then
  exit 97
fi
"$@"
""")
            python_stub = bin_dir / "python"
            write_executable(python_stub, """#!/usr/bin/env bash
printf 'python %s\n' "$*" >> "$STUB_LOG"
if [[ "${1:-}" != "$API_HEALTH_CHECK" ]]; then
  exit 98
fi
case "$SCENARIO" in
  stale_listener|redirect_health|wrong_health)
    exit 1
    ;;
esac
if [[ "$SCENARIO" == "transient_api" ]]; then
  count=0
  if [[ -f "$STUB_PYTHON_STATE" ]]; then
    read -r count < "$STUB_PYTHON_STATE"
  fi
  count=$((count + 1))
  printf '%s\n' "$count" > "$STUB_PYTHON_STATE"
  if [[ "$count" -eq 1 ]]; then
    exit 1
  fi
fi
""")

            env = os.environ.copy()
            env.update({
                "PATH": f"{bin_dir}:{env.get('PATH', '')}",
                "SCENARIO": scenario,
                "STUB_LOG": str(log),
                "STUB_STATE": str(state),
                "STUB_PYTHON_STATE": str(python_state),
                "STUB_CURL_STATE": str(curl_state),
                "API_SERVICE_SOURCE": str(source),
                "API_SERVICE_TARGET": str(target),
                "API_SERVICE": "surge-screener-api",
                "APP_SERVICE": "surge-screener",
                "API_PORT": "8000",
                "APP_PORT": "8501",
                "PYTHON_BIN": str(python_stub),
                "API_HEALTH_CHECK": str(health_check),
                "API_HEALTH_URL": "http://127.0.0.1:8000/healthz",
                "STREAMLIT_HEALTH_URL": "http://127.0.0.1:8501/_stcore/health",
                "STREAMLIT_ROOT_URL": "http://127.0.0.1:8501",
                "HEALTH_ATTEMPTS": attempts,
                "HEALTH_DELAY": "0",
            })
            result = subprocess.run(
                ["bash", str(gate_path)],
                check=False,
                capture_output=True,
                text=True,
                env=env,
                timeout=10,
            )
            lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
            return result, lines

    api_failures = (
        "install_failure",
        "daemon_reload_failure",
        "enable_failure",
        "api_restart_failure",
        "transient_unit_failure",
        "inactive_api",
        "zero_pid",
        "changed_pid",
        "stale_listener",
        "redirect_health",
        "wrong_health",
    )
    for scenario in api_failures:
        result, lines = run_gate(scenario)
        require(result.returncode != 0, f"{scenario} must fail deployment")
        require("systemctl --user status surge-screener-api --no-pager" in lines
                and "journalctl --user -u surge-screener-api -n 160 --no-pager" in lines,
                f"{scenario} must emit API status and journal diagnostics")
        require("systemctl --user restart surge-screener" not in lines,
                f"{scenario} must not restart Streamlit")
        if scenario not in ("install_failure", "daemon_reload_failure", "enable_failure",
                            "api_restart_failure", "zero_pid"):
            require(any(line.startswith("systemd-run ") and line.endswith(" --diagnose")
                        for line in lines),
                    f"{scenario} must emit exact helper diagnostics after retries fail")

    for scenario in ("streamlit_restart_failure", "streamlit_health_failure"):
        result, lines = run_gate(scenario)
        require(result.returncode != 0, f"{scenario} must fail deployment")
        require("systemctl --user restart surge-screener" in lines,
                f"{scenario} must occur after the Streamlit restart gate")
        require("systemctl --user status surge-screener --no-pager" in lines
                and "journalctl --user -u surge-screener -n 160 --no-pager" in lines,
                f"{scenario} must emit Streamlit diagnostics")

    result, lines = run_gate("success")
    require(result.returncode == 0, "healthy API and Streamlit must pass deployment")
    api_restart = lines.index("systemctl --user restart surge-screener-api")
    app_restart = lines.index("systemctl --user restart surge-screener")
    require(api_restart < app_restart, "API must pass before Streamlit restarts")
    require(lines.count(
        "systemctl --user show surge-screener-api --property MainPID --value"
    ) == 2, "successful API health must prove MainPID stability")
    require(lines.count(
        "systemctl --user is-active --quiet surge-screener-api"
    ) == 2, "successful API health must prove active state before and after HTTP")
    require(any(line.startswith("python ") for line in lines),
            "successful API health must execute the exact-health/listener helper")
    require(sum(line.startswith("systemd-run ") for line in lines) == 1,
            "successful API health must use one transient user service")
    transient_line = next(line for line in lines if line.startswith("systemd-run "))
    require(
        transient_line.startswith(
            "systemd-run --user --quiet --wait --pipe --collect --service-type=exec "
        ),
        "ownership helper must run synchronously under the systemd user manager",
    )
    python_line = next(line for line in lines if line.startswith("python "))
    require(" http://127.0.0.1:8000/healthz 321 --host 127.0.0.1 --port 8000"
            in python_line,
            "service gate must pass exact URL, MainPID, host, and port to the helper CLI")
    require(any(line.startswith("curl --noproxy * -fsS ") for line in lines),
            "successful Streamlit health must bypass proxy settings")
    require("both Streamlit and loopback API services are healthy" in result.stdout,
            "success must be reported only after both service gates")

    result, lines = run_gate("transient_api", attempts="2")
    require(result.returncode == 0, "API readiness must recover within the retry budget")
    require(sum(line.startswith("python ") for line in lines) == 2
            and sum(line.startswith("systemd-run ") for line in lines) == 2
            and lines.count("sleep 0") == 1,
            "transient API failure must sleep once and retry the combined health helper")

    result, lines = run_gate("transient_streamlit", attempts="2")
    require(result.returncode == 0, "Streamlit readiness must recover within the retry budget")
    require(sum(line.startswith("curl ") for line in lines) == 3
            and lines.count("sleep 0") == 1,
            "transient Streamlit failure must try health/root, sleep, then retry")

    result, lines = run_gate("streamlit_root_fallback")
    require(result.returncode == 0,
            "legacy Streamlit root fallback must pass when _stcore health is unavailable")
    require(any("/_stcore/health" in line for line in lines if line.startswith("curl "))
            and any(line.endswith("http://127.0.0.1:8501")
                    for line in lines if line.startswith("curl ")),
            "Streamlit gate must retain both health and root probes")


def test_api_operator_documentation() -> None:
    doc = read("docs/api/test-server-loopback-api.md")
    require("ssh -o ExitOnForwardFailure=yes -N" in doc
            and "-L 127.0.0.1:18000:127.0.0.1:8000 antigravity" in doc,
            "operator docs must show a fail-closed, explicitly bound SSH tunnel")
    require("curl --noproxy '*' -fsS http://127.0.0.1:18000/healthz" in doc,
            "operator docs must show the distinct forwarded health check")
    require("systemctl --user status surge-screener-api" in doc
            and "journalctl --user -u surge-screener-api" in doc,
            "operator docs must include status and journal diagnostics")
    require("disable --now surge-screener-api.service" in doc
            and "daemon-reload" in doc,
            "operator docs must include complete rollback commands")
    for unsafe in ("GatewayPorts=yes", "--host 0.0.0.0",
                   "http://172.16.204.117:8000"):
        require(unsafe not in doc, f"operator docs must not recommend {unsafe}")


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
    require("--published-reports-dir %h/apps/surge-screener/shared/published_reports/current/reports"
            in data_health_service
            and "--analytics-lock %h/apps/surge-screener/shared/locks/analytics-refresh.lock"
            in data_health_service,
            "scheduled Data Health must layer the durable mirror under the shared writer lock")

    post_service = read("deploy/surge-post-producer-analytics.service")
    post_timer = read("deploy/surge-post-producer-analytics.timer")
    require("Type=oneshot" in post_service
            and "scripts/post_producer_analytics.py" in post_service,
            "post-producer ingestion must run as a 7F-local oneshot")
    require("--published-store %h/apps/surge-screener/shared/published_reports" in post_service
            and "--verdict-file %h/apps/surge-screener/shared/post_ingestion/latest.json" in post_service,
            "post-producer service must use durable report and evidence paths")
    require("OnCalendar=Tue..Sat *-*-* 06:35:00 Asia/Taipei" in post_timer
            and "Persistent=true" in post_timer
            and "Unit=surge-post-producer-analytics.service" in post_timer,
            "post-producer timer must start observation before producers complete")


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
        test_phase7e_deployment_freeze_covers_every_deploy_lane,
        test_deploy_workflow_avoids_redundant_scheduled_data_work,
        test_daily_workflow_persists_candidate_score_snapshots,
        test_daily_report_publish_uses_race_safe_helper,
        test_telegram_failure_does_not_suppress_authoritative_report_publication,
        test_one_time_natural_validation_observer_contract,
        test_options_flow_workflow_runs_forward_validator,
        test_daily_workflow_runs_no_llm_candidate_outcomes,
        test_daily_workflow_schedules_premarket_candidate_refresh,
        test_monthly_reflection_is_manually_runnable_with_90_day_lookback,
        test_verify_returns_runs_no_picks_alert_notifier,
        test_deploy_script,
        test_service_template,
        test_post_producer_service_restarts_for_crash_recovery,
        test_api_service_template,
        test_api_health_validator_contract,
        test_api_service_gate_behavior,
        test_api_operator_documentation,
        test_local_refresh_timer_templates,
        test_schedule_registry_includes_local_refresh_results,
        test_requirements_include_analytics_deps,
        test_analytics_connection_doc,
    ]
    for test in tests:
        test()
    print(f"deploy artifact tests: {len(tests)} passed")
