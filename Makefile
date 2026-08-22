# Quant Radar — dev tasks.  Usage: `make <target>` (run `make` for the list).
PY   := .venv/bin/python
PORT ?= 8501
API_PORT ?= 8000
MARKETS ?= US
UNIVERSE ?= sp1500
MIN_SCORE ?= 65
RANK_LIMIT ?= 50
OPTIONS_GATE_LIMIT ?= 0
CANDIDATE_LIMIT ?= 25
CANDIDATE_MODEL ?=
CANDIDATE_RETRIES ?= 1
CANDIDATE_DEFERRED_RETRIES ?= 0
CANDIDATE_SCORING_MODE ?= fast
RESCORE_STALE_LLM ?= 1
LLM_SCORE_INPUT ?= ranked_candidates.json
CODEX_SDK_TIMEOUT ?= 180
YF_BATCH_SIZE ?= 25
MIN_DATA_COVERAGE ?= 0.70
MIN_AVG_DOLLAR_VOL ?= 5000000
MIN_MARKET_CAP ?= 300000000
MIN_PRICE ?= 5
MAX_RET_5D ?= 30
MAX_RET_20D ?= 60
EARNINGS_EXCLUDE_DAYS ?= 2
CANDIDATES_STATUS ?= reports/run_status/candidates-local.json
UX1B_RUN_ID ?= $(shell date -u +%Y%m%dT%H%M%SZ)
UX1B_RECOVERY_ID ?=
UX1B_CONTINUATION_ID ?=
UX1B_CORRECTION_ID ?=
UX1B_LIFECYCLE_CORRECTION_ID ?=
UX1B_CAPTURE_BINDING_CORRECTION_ID ?=
UX1B_CAPTURE_BINDING_TIER_ID ?=
UX1B_CAPTURE_BINDING_CAPTURE_ID ?=
UX1B_RENDER_MANIFEST_CORRECTION_ID ?=
UX1B_RENDER_MANIFEST_TIER_ID ?=
UX1B_RENDER_MANIFEST_CAPTURE_ID ?=
UX1B_HISTORICAL_STACK_CORRECTION_ID ?=
UX1B_HISTORICAL_STACK_TIER_ID ?=
UX1B_HISTORICAL_STACK_CAPTURE_ID ?=
UX1B_HISTORICAL_STACK_CONTINUATION_ID ?=
UX1B_EXTERNAL_REVIEW_CAPTURE_ID ?=
UX1B_EXTERNAL_REVIEW_PARENT_CONTINUATION_ID ?=
UX1B_EXTERNAL_REVIEW_CORRECTION_ID ?=
UX1B_EXTERNAL_REVIEW_TIER_ID ?=
UX1B_EXTERNAL_REVIEW_INTAKE_SHA256 ?=
UX1B_EXTERNAL_REVIEW_INTAKE_SIZE ?=
UX1B_LIFECYCLE_TEST_CAPTURE_ID ?=
UX1B_LIFECYCLE_TEST_PARENT_CONTINUATION_ID ?=
UX1B_LIFECYCLE_TEST_PARENT_REVIEW_ID ?=
UX1B_LIFECYCLE_TEST_CORRECTION_ID ?=
UX1B_LIFECYCLE_TEST_TIER_ID ?=
UX1B_LIFECYCLE_TEST_INTAKE_SHA256 ?=
UX1B_LIFECYCLE_TEST_INTAKE_SIZE ?=
UX1B_FORMAL_STATE_ORACLE_CAPTURE_ID ?=
UX1B_FORMAL_STATE_ORACLE_PACKET_CONTINUATION_ID ?=
UX1B_FORMAL_STATE_ORACLE_PARENT_LIFECYCLE_ID ?=
UX1B_FORMAL_STATE_ORACLE_CORRECTION_ID ?=
UX1B_FORMAL_STATE_ORACLE_TIER_ID ?=
UX1B_FORMAL_STATE_ORACLE_INTAKE_SHA256 ?=
UX1B_FORMAL_STATE_ORACLE_INTAKE_SIZE ?=
UX1B_O1_LIFECYCLE_CAPTURE_ID ?=
UX1B_O1_LIFECYCLE_PACKET_CONTINUATION_ID ?=
UX1B_O1_LIFECYCLE_PARENT_CORRECTION_ID ?=
UX1B_O1_LIFECYCLE_CORRECTION_ID ?=
UX1B_O1_LIFECYCLE_TIER_ID ?=
UX1B_V1_LIFECYCLE_CAPTURE_ID ?=
UX1B_V1_LIFECYCLE_PACKET_CONTINUATION_ID ?=
UX1B_V1_LIFECYCLE_PARENT_CORRECTION_ID ?=
UX1B_V1_LIFECYCLE_CORRECTION_ID ?=
UX1B_V1_LIFECYCLE_TIER_ID ?=
UX1B_HANDOFF_PREFLIGHT ?=
UX1B_THEME_BATCH_ID ?=
UX1B_THEME_RUN_ID ?=

.DEFAULT_GOAL := help
.PHONY: run api restart stop run-bg logs test ui-ux-baseline ui-ux1b-focused-tests ui-ux1b-legacy ui-ux1b-pretheme ui-ux1b-awake-check ui-ux1b-theme-handoff-bootstrap ui-ux1b-theme-handoff-preflight ui-ux1b-theme-handoff-continuation-bootstrap ui-ux1b-theme-handoff-continuation-preflight ui-ux1b-theme-handoff-continuation-verify ui-ux1b-theme-handoff-correction-bootstrap ui-ux1b-theme-handoff-correction-preflight ui-ux1b-theme-handoff-correction-verify ui-ux1b-theme-handoff-descriptor-budget-correction-bootstrap ui-ux1b-theme-handoff-descriptor-budget-correction-preflight ui-ux1b-theme-handoff-descriptor-budget-correction-verify ui-ux1b-theme-handoff-forward-lifecycle-correction-bootstrap ui-ux1b-theme-handoff-forward-lifecycle-correction-preflight ui-ux1b-theme-handoff-forward-lifecycle-correction-verify ui-ux1b-capture-binding-bootstrap ui-ux1b-capture-binding-preflight ui-ux1b-capture-binding-verify ui-ux1b-capture-binding-capture ui-ux1b-capture-binding-reconcile ui-ux1b-capture-binding-compare ui-ux1b-capture-binding-prepare-review ui-ux1b-render-manifest-bootstrap ui-ux1b-render-manifest-preflight ui-ux1b-render-manifest-verify ui-ux1b-render-manifest-capture ui-ux1b-render-manifest-reconcile ui-ux1b-render-manifest-compare ui-ux1b-render-manifest-prepare-review ui-ux1b-historical-stack-bootstrap ui-ux1b-historical-stack-preflight ui-ux1b-historical-stack-verify ui-ux1b-historical-stack-compare ui-ux1b-historical-stack-prepare-review ui-ux1b-external-review-bootstrap ui-ux1b-external-review-preflight ui-ux1b-external-review-verify ui-ux1b-external-review-submit-intake ui-ux1b-external-review-publish ui-ux1b-external-review-lifecycle-test-bootstrap ui-ux1b-external-review-lifecycle-test-preflight ui-ux1b-external-review-lifecycle-test-verify ui-ux1b-external-review-lifecycle-test-submit-intake ui-ux1b-external-review-lifecycle-test-publish ui-ux1b-external-review-formal-state-oracle-bootstrap ui-ux1b-external-review-formal-state-oracle-preflight ui-ux1b-external-review-formal-state-oracle-verify ui-ux1b-external-review-formal-state-oracle-submit-intake ui-ux1b-external-review-formal-state-oracle-publish ui-ux1b-external-review-o1-lifecycle-test-bootstrap ui-ux1b-external-review-o1-lifecycle-test-preflight ui-ux1b-external-review-o1-lifecycle-test-verify ui-ux1b-external-review-o1-lifecycle-test-publish ui-ux1b-external-review-v1-lifecycle-test-bootstrap ui-ux1b-external-review-v1-lifecycle-test-preflight ui-ux1b-external-review-v1-lifecycle-test-verify ui-ux1b-external-review-v1-lifecycle-test-publish ui-ux1b-recovery-postcontrol ui-ux1b-recovery-reconcile ui-ux1b-control-migration-review-prepare ui-ux1b-control-migration-review ui-ux1b-theme-handoff-prepare ui-ux1b-theme-handoff ui-ux1b-theme-batch-init ui-ux1b-theme-batch-seal ui-ux1b-theme-batch-review ui-ux1b-theme-batch-ready ui-ux1b-theme-batch-apply ui-ux1b-theme-batch-reconcile ui-ux1b-theme-batch-verify ui-ux1b-theme-states ui-ux1b-theme-states-reconcile ui-ux1b-theme-states-review ui-ux1b-theme-states-close ui-ux1b-posttheme ui-ux1b-posttheme-reconcile ui-ux1b-posttheme-review ui-ux1b-theme-close ui-ux1b-recovery-tests ui-ux1b-recovery-precontrol ui-ux1b-recovery-verify-migration candidate-preflight candidates-local candidates-rank-local candidates-score-local reversal-test cot cot-data reversal-scan help

run: stop ## Start the dashboard (stops any running instance first), foreground
	$(PY) -m streamlit run app.py --server.port $(PORT) --browser.gatherUsageStats false

api: ## Start the loopback-only read API, foreground
	$(PY) -m uvicorn api.main:app --host 127.0.0.1 --port $(API_PORT)

restart: run ## Alias for run (stop + start)

stop: ## Stop any running dashboard
	-@pkill -f "streamlit run app.py" 2>/dev/null || true

run-bg: stop ## Start in the background (logs -> /tmp/streamlit.log)
	@nohup $(PY) -m streamlit run app.py --server.port $(PORT) \
		--server.headless true --browser.gatherUsageStats false > /tmp/streamlit.log 2>&1 &
	@echo "dashboard starting on http://localhost:$(PORT)  (logs: make logs)"

logs: ## Tail the background dashboard log
	@tail -f /tmp/streamlit.log

test: ## Run the options-analytics / momentum unit tests
	$(PY) scripts/test_artifact_loader.py
	$(PY) scripts/test_api.py
	$(PY) scripts/test_private_industry_roles_api.py
	$(PY) scripts/test_industry_role_store.py
	$(PY) scripts/test_industry_role_admin.py
	$(PY) scripts/test_industry_role_legacy_retirement.py
	$(PY) scripts/test_momentum_options.py
	$(PY) scripts/test_risk_guard_technical.py
	$(PY) scripts/test_risk_guard.py
	$(PY) scripts/test_publish_reports.py
	$(PY) scripts/test_cot_report_store.py
	$(PY) scripts/test_candidate_score_snapshot.py
	$(PY) scripts/test_analytics_store.py
	$(PY) scripts/test_analytics_checks.py
	$(PY) scripts/test_analytics_action_notify.py
	$(PY) scripts/test_deploy_artifacts.py
	$(PY) scripts/test_natural_validation_observer.py
	$(PY) scripts/test_analytics_refresh_transaction.py
	$(PY) scripts/test_post_producer_analytics.py
	$(PY) scripts/test_industry_roles.py
	$(PY) scripts/test_eastmoney_money_flow.py
	$(PY) scripts/test_universe_refresh.py
	$(PY) scripts/test_influencer_roster.py
	$(PY) scripts/test_trade_state.py
	$(PY) scripts/test_options_cockpit_display.py
	$(PY) scripts/test_ui_read_api.py
	$(PY) scripts/test_ui_backend_boundary.py
	$(PY) scripts/test_ui_separation_convergence.py
	$(PY) scripts/test_ui_ai_updates_api.py
	$(PY) scripts/test_ui_fund_catalog_api.py
	$(PY) scripts/test_ui_iv_history_api.py
	$(PY) scripts/test_ui_options_flow_api.py
	$(PY) scripts/test_ui_options_cockpit_options_flow_api.py
	$(PY) scripts/test_ui_options_cockpit_social_api.py
	$(PY) scripts/test_ui_crypto_universe_api.py
	$(PY) scripts/test_ui_market_thesis_api.py
	$(PY) scripts/test_ui_market_thesis_summaries_api.py
	$(PY) scripts/test_ui_daily_summary_api.py
	$(PY) scripts/test_ui_schedules_daily_summary_api.py
	$(PY) scripts/test_ui_playbook_validation_api.py
	$(PY) scripts/test_ui_continuation_validation_api.py
	$(PY) scripts/test_ui_cot_reports_api.py
	$(PY) scripts/test_ui_public_resources_api.py
	$(PY) scripts/test_ui_theme_drill_api.py
	$(PY) scripts/test_ui_reversal_snapshots_api.py
	$(PY) scripts/test_ui_candidate_feeds_api.py
	$(PY) scripts/test_ui_schedules_candidate_api.py
	$(PY) scripts/test_ui_schedules_options_flow_api.py
	$(PY) scripts/test_ui_schedules_crypto_api.py
	$(PY) scripts/test_ui_schedules_theme_flow_summary_api.py
	$(PY) scripts/test_ui_money_flow_api.py
	$(PY) scripts/test_ui_institutional_score_api.py
	$(PY) scripts/test_ui_analytics_ranked_api.py
	$(PY) scripts/test_ui_us_options_scored_api.py
	$(PY) scripts/test_ui_industry_roles_ranked_api.py
	$(PY) scripts/test_ui_industry_roles_private_api.py
	$(PY) scripts/test_ui_options_cockpit_scored_api.py
	$(PY) scripts/test_ui_options_cockpit_iv_history_api.py
	$(PY) scripts/test_ui_analyst_views_scored_api.py
	$(PY) scripts/test_ui_sector_rotation_scored_api.py
	$(PY) scripts/test_ui_sector_rotation_api.py
	$(PY) scripts/test_ui_us_screener_api.py
	$(PY) scripts/test_ui_x_sentiment_api.py
	$(PY) scripts/test_ui_theme_flow_api.py
	$(PY) scripts/test_ui_ux_components.py
	$(PY) scripts/test_ui_ux1a_safety.py
	$(PY) scripts/test_ui_ux_contract.py
	$(PY) scripts/test_ui_ux_fixtures.py
	$(PY) scripts/test_ui_ux_snapshot_matrix.py
	$(PY) scripts/test_ui_ux_theme.py
	$(PY) scripts/test_ui_ux_theme_matrix.py
	$(PY) scripts/test_ai_chat_store.py
	$(PY) scripts/test_candidate_controls_view.py
	$(PY) scripts/test_sys_schedules_reflection.py
	$(PY) scripts/test_dashboard_navigation.py
	$(PY) scripts/test_hard_filter_yfinance.py
	$(PY) scripts/test_candidate_pipeline_controls.py
	$(PY) scripts/test_candidate_outcomes.py
	$(PY) scripts/test_rank_candidates.py
	$(PY) scripts/test_agent_reach_auth.py
	$(PY) scripts/test_agent_reach_social_bridge.py
	$(PY) scripts/test_social_intelligence.py
	$(PY) scripts/test_social_intelligence_outcomes.py
	$(PY) scripts/test_llm_score_progress.py
	$(PY) scripts/test_promotion_reachability.py
	$(PY) scripts/test_build_report.py
	$(PY) scripts/test_append_ledger.py
	$(PY) scripts/test_verify_returns.py
	$(PY) scripts/test_run_status.py
	$(PY) scripts/test_docker_runtime_contract.py
	$(PY) scripts/test_codex_auth_flow.py
	$(PY) scripts/test_llm_client_codex.py
	$(PY) scripts/test_x_influencers_codex.py

ui-ux-baseline: ## Capture the deterministic UX-0 browser matrix (optional Playwright tool)
	$(PY) scripts/ui_ux_snapshot_matrix.py --no-prompt

ui-ux1b-focused-tests: ## Run UX-1B fixture, runner, theme, contract, and navigation gates
	$(PY) scripts/test_ui_ux_fixtures.py
	$(PY) scripts/test_ui_ux_snapshot_matrix.py
	$(PY) scripts/test_ui_ux_theme.py
	$(PY) scripts/test_ui_ux_theme_matrix.py
	$(PY) scripts/test_ui_ux_contract.py
	$(PY) scripts/test_dashboard_navigation.py

ui-ux1b-legacy: ## Revalidate UX-0, unmigrated UX-1A, and migrated selection controls
	$(PY) scripts/ui_ux_snapshot_matrix.py \
		--browser chromium \
		--out-dir .claude/ui_snapshots/ux1b/legacy-validation-$(UX1B_RUN_ID)-ux0 \
		--no-prompt --json
	$(PY) scripts/ui_ux_snapshot_matrix.py \
		--browser chromium \
		--case today-decision --case ai-chat-open --case ai-updates \
		--case schedules \
		--viewport desktop --viewport tablet --viewport mobile --viewport 320x844 \
		--out-dir .claude/ui_snapshots/ux1b/legacy-validation-$(UX1B_RUN_ID)-ux1a \
		--no-prompt --json
	$(PY) scripts/test_ui_accessible_selection_controls.py

ui-ux1b-pretheme: ## Capture the mandatory Chromium UX-1B pre-theme 27x3 matrix
	$(PY) scripts/ui_ux_snapshot_matrix.py \
		--profile ux1b-full-pages --phase pretheme --browser chromium \
		--out-dir .claude/ui_snapshots/ux1b/pretheme-$(UX1B_RUN_ID) \
		--no-prompt --json

ui-ux1b-awake-check: ## Verify the Sequence 8 AC/battery/clamshell precondition
	$(PY) -B scripts/ui_ux_awake_gate.py check --json

ui-ux1b-theme-handoff-bootstrap: ## Bootstrap the formal UX-1B handoff controls
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py bootstrap \
		--recovery-id "$(UX1B_RECOVERY_ID)" --json

ui-ux1b-theme-handoff-preflight: ## Publish the authenticated formal handoff preflight
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py preflight \
		--recovery-id "$(UX1B_RECOVERY_ID)" \
		--authorization-record-sha "51a007d9a4b71e2ce47a36af687acc06fecf0cec477bfd9cdb0b60697f2dc525" \
		--json

ui-ux1b-theme-handoff-continuation-bootstrap: ## Bootstrap the Sequence 9 post-capture continuation
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CONTINUATION_ID)" || (echo "UX1B_CONTINUATION_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py bootstrap-continuation \
		--capture-recovery-id "$(UX1B_RECOVERY_ID)" \
		--continuation-id "$(UX1B_CONTINUATION_ID)" --json

ui-ux1b-theme-handoff-continuation-preflight: ## Publish the Sequence 9 continuation preflight
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CONTINUATION_ID)" || (echo "UX1B_CONTINUATION_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py preflight-continuation \
		--capture-recovery-id "$(UX1B_RECOVERY_ID)" \
		--continuation-id "$(UX1B_CONTINUATION_ID)" --json

ui-ux1b-theme-handoff-continuation-verify: ## Reopen and verify the Sequence 9 continuation preflight
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CONTINUATION_ID)" || (echo "UX1B_CONTINUATION_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py verify-continuation-preflight \
		--capture-recovery-id "$(UX1B_RECOVERY_ID)" \
		--continuation-id "$(UX1B_CONTINUATION_ID)" --json

ui-ux1b-theme-handoff-correction-bootstrap: ## Bootstrap the Sequence 10 descriptor-budget correction
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CONTINUATION_ID)" || (echo "UX1B_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CORRECTION_ID)" || (echo "UX1B_CORRECTION_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py bootstrap-descriptor-budget-correction \
		--capture-recovery-id "$(UX1B_RECOVERY_ID)" \
		--continuation-id "$(UX1B_CONTINUATION_ID)" \
		--correction-id "$(UX1B_CORRECTION_ID)" --json

ui-ux1b-theme-handoff-correction-preflight: ## Publish the Sequence 10 correction preflight
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CONTINUATION_ID)" || (echo "UX1B_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CORRECTION_ID)" || (echo "UX1B_CORRECTION_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py preflight-descriptor-budget-correction \
		--capture-recovery-id "$(UX1B_RECOVERY_ID)" \
		--continuation-id "$(UX1B_CONTINUATION_ID)" \
		--correction-id "$(UX1B_CORRECTION_ID)" --json

ui-ux1b-theme-handoff-correction-verify: ## Reopen and verify the Sequence 10 correction preflight
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CONTINUATION_ID)" || (echo "UX1B_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CORRECTION_ID)" || (echo "UX1B_CORRECTION_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py verify-descriptor-budget-correction-preflight \
		--capture-recovery-id "$(UX1B_RECOVERY_ID)" \
		--continuation-id "$(UX1B_CONTINUATION_ID)" \
		--correction-id "$(UX1B_CORRECTION_ID)" --json

ui-ux1b-theme-handoff-descriptor-budget-correction-bootstrap: ui-ux1b-theme-handoff-correction-bootstrap

ui-ux1b-theme-handoff-descriptor-budget-correction-preflight: ui-ux1b-theme-handoff-correction-preflight

ui-ux1b-theme-handoff-descriptor-budget-correction-verify: ui-ux1b-theme-handoff-correction-verify

ui-ux1b-theme-handoff-forward-lifecycle-correction-bootstrap: ## Bootstrap the Sequence 11 forward-lifecycle correction
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CONTINUATION_ID)" || (echo "UX1B_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CORRECTION_ID)" || (echo "UX1B_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_CORRECTION_ID)" || (echo "UX1B_LIFECYCLE_CORRECTION_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py bootstrap-forward-lifecycle-correction \
		--capture-recovery-id "$(UX1B_RECOVERY_ID)" \
		--continuation-id "$(UX1B_CONTINUATION_ID)" \
		--correction-id "$(UX1B_CORRECTION_ID)" \
		--lifecycle-correction-id "$(UX1B_LIFECYCLE_CORRECTION_ID)" --json

ui-ux1b-theme-handoff-forward-lifecycle-correction-preflight: ## Publish the Sequence 11 forward-lifecycle preflight
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CONTINUATION_ID)" || (echo "UX1B_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CORRECTION_ID)" || (echo "UX1B_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_CORRECTION_ID)" || (echo "UX1B_LIFECYCLE_CORRECTION_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py preflight-forward-lifecycle-correction \
		--capture-recovery-id "$(UX1B_RECOVERY_ID)" \
		--continuation-id "$(UX1B_CONTINUATION_ID)" \
		--correction-id "$(UX1B_CORRECTION_ID)" \
		--lifecycle-correction-id "$(UX1B_LIFECYCLE_CORRECTION_ID)" --json

ui-ux1b-theme-handoff-forward-lifecycle-correction-verify: ## Reopen the Sequence 11 forward-lifecycle preflight
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CONTINUATION_ID)" || (echo "UX1B_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CORRECTION_ID)" || (echo "UX1B_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_CORRECTION_ID)" || (echo "UX1B_LIFECYCLE_CORRECTION_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py verify-forward-lifecycle-correction-preflight \
		--capture-recovery-id "$(UX1B_RECOVERY_ID)" \
		--continuation-id "$(UX1B_CONTINUATION_ID)" \
		--correction-id "$(UX1B_CORRECTION_ID)" \
		--lifecycle-correction-id "$(UX1B_LIFECYCLE_CORRECTION_ID)" --json

ui-ux1b-capture-binding-bootstrap: ## Bootstrap the Sequence 12 capture-binding correction
	@test -n "$(UX1B_CAPTURE_BINDING_CORRECTION_ID)" || (echo "UX1B_CAPTURE_BINDING_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CAPTURE_BINDING_TIER_ID)" || (echo "UX1B_CAPTURE_BINDING_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CAPTURE_BINDING_CAPTURE_ID)" || (echo "UX1B_CAPTURE_BINDING_CAPTURE_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py bootstrap-capture-binding-correction \
		--correction-id "$(UX1B_CAPTURE_BINDING_CORRECTION_ID)" \
		--tier-id "$(UX1B_CAPTURE_BINDING_TIER_ID)" \
		--capture-id "$(UX1B_CAPTURE_BINDING_CAPTURE_ID)" --json

ui-ux1b-capture-binding-preflight: ## Publish the Sequence 12 capture-binding preflight
	@test -n "$(UX1B_CAPTURE_BINDING_CORRECTION_ID)" || (echo "UX1B_CAPTURE_BINDING_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CAPTURE_BINDING_TIER_ID)" || (echo "UX1B_CAPTURE_BINDING_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CAPTURE_BINDING_CAPTURE_ID)" || (echo "UX1B_CAPTURE_BINDING_CAPTURE_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py preflight-capture-binding-correction \
		--correction-id "$(UX1B_CAPTURE_BINDING_CORRECTION_ID)" \
		--tier-id "$(UX1B_CAPTURE_BINDING_TIER_ID)" \
		--capture-id "$(UX1B_CAPTURE_BINDING_CAPTURE_ID)" --json

ui-ux1b-capture-binding-verify: ## Reopen the Sequence 12 capture-binding preflight
	@test -n "$(UX1B_CAPTURE_BINDING_CORRECTION_ID)" || (echo "UX1B_CAPTURE_BINDING_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CAPTURE_BINDING_TIER_ID)" || (echo "UX1B_CAPTURE_BINDING_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CAPTURE_BINDING_CAPTURE_ID)" || (echo "UX1B_CAPTURE_BINDING_CAPTURE_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py verify-capture-binding-correction-preflight \
		--correction-id "$(UX1B_CAPTURE_BINDING_CORRECTION_ID)" \
		--tier-id "$(UX1B_CAPTURE_BINDING_TIER_ID)" \
		--capture-id "$(UX1B_CAPTURE_BINDING_CAPTURE_ID)" --json

ui-ux1b-capture-binding-capture: ## Capture the exact Sequence 12 36/44 root matrix
	@test -n "$(UX1B_CAPTURE_BINDING_CORRECTION_ID)" || (echo "UX1B_CAPTURE_BINDING_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CAPTURE_BINDING_TIER_ID)" || (echo "UX1B_CAPTURE_BINDING_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CAPTURE_BINDING_CAPTURE_ID)" || (echo "UX1B_CAPTURE_BINDING_CAPTURE_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py capture-capture-binding-controls \
		--correction-id "$(UX1B_CAPTURE_BINDING_CORRECTION_ID)" \
		--tier-id "$(UX1B_CAPTURE_BINDING_TIER_ID)" \
		--capture-id "$(UX1B_CAPTURE_BINDING_CAPTURE_ID)" --json

ui-ux1b-capture-binding-reconcile: ## Reconcile the retained Sequence 12 capture prefix
	@test -n "$(UX1B_CAPTURE_BINDING_CORRECTION_ID)" || (echo "UX1B_CAPTURE_BINDING_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CAPTURE_BINDING_TIER_ID)" || (echo "UX1B_CAPTURE_BINDING_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CAPTURE_BINDING_CAPTURE_ID)" || (echo "UX1B_CAPTURE_BINDING_CAPTURE_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py reconcile-capture-binding-controls \
		--correction-id "$(UX1B_CAPTURE_BINDING_CORRECTION_ID)" \
		--tier-id "$(UX1B_CAPTURE_BINDING_TIER_ID)" \
		--capture-id "$(UX1B_CAPTURE_BINDING_CAPTURE_ID)" --json

ui-ux1b-capture-binding-compare: ## Publish the Sequence 12 81/44/125 migration report
	@test -n "$(UX1B_CAPTURE_BINDING_CORRECTION_ID)" || (echo "UX1B_CAPTURE_BINDING_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CAPTURE_BINDING_TIER_ID)" || (echo "UX1B_CAPTURE_BINDING_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CAPTURE_BINDING_CAPTURE_ID)" || (echo "UX1B_CAPTURE_BINDING_CAPTURE_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py compare-capture-binding-migration \
		--correction-id "$(UX1B_CAPTURE_BINDING_CORRECTION_ID)" \
		--tier-id "$(UX1B_CAPTURE_BINDING_TIER_ID)" \
		--capture-id "$(UX1B_CAPTURE_BINDING_CAPTURE_ID)" --json

ui-ux1b-capture-binding-prepare-review: ## Prepare the Sequence 12 125-item packet and stop at R3
	@test -n "$(UX1B_CAPTURE_BINDING_CORRECTION_ID)" || (echo "UX1B_CAPTURE_BINDING_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CAPTURE_BINDING_TIER_ID)" || (echo "UX1B_CAPTURE_BINDING_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CAPTURE_BINDING_CAPTURE_ID)" || (echo "UX1B_CAPTURE_BINDING_CAPTURE_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py prepare-capture-binding-review \
		--correction-id "$(UX1B_CAPTURE_BINDING_CORRECTION_ID)" \
		--tier-id "$(UX1B_CAPTURE_BINDING_TIER_ID)" \
		--capture-id "$(UX1B_CAPTURE_BINDING_CAPTURE_ID)" --json

ui-ux1b-render-manifest-bootstrap: ## Bootstrap the Sequence 13 render/manifest correction
	@test -n "$(UX1B_RENDER_MANIFEST_CORRECTION_ID)" || (echo "UX1B_RENDER_MANIFEST_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_RENDER_MANIFEST_TIER_ID)" || (echo "UX1B_RENDER_MANIFEST_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_RENDER_MANIFEST_CAPTURE_ID)" || (echo "UX1B_RENDER_MANIFEST_CAPTURE_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py bootstrap-render-manifest-correction \
		--correction-id "$(UX1B_RENDER_MANIFEST_CORRECTION_ID)" \
		--tier-id "$(UX1B_RENDER_MANIFEST_TIER_ID)" \
		--capture-id "$(UX1B_RENDER_MANIFEST_CAPTURE_ID)" --json

ui-ux1b-render-manifest-preflight: ## Publish the Sequence 13 render/manifest preflight
	@test -n "$(UX1B_RENDER_MANIFEST_CORRECTION_ID)" || (echo "UX1B_RENDER_MANIFEST_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_RENDER_MANIFEST_TIER_ID)" || (echo "UX1B_RENDER_MANIFEST_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_RENDER_MANIFEST_CAPTURE_ID)" || (echo "UX1B_RENDER_MANIFEST_CAPTURE_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py preflight-render-manifest-correction \
		--correction-id "$(UX1B_RENDER_MANIFEST_CORRECTION_ID)" \
		--tier-id "$(UX1B_RENDER_MANIFEST_TIER_ID)" \
		--capture-id "$(UX1B_RENDER_MANIFEST_CAPTURE_ID)" --json

ui-ux1b-render-manifest-verify: ## Reopen the Sequence 13 render/manifest preflight
	@test -n "$(UX1B_RENDER_MANIFEST_CORRECTION_ID)" || (echo "UX1B_RENDER_MANIFEST_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_RENDER_MANIFEST_TIER_ID)" || (echo "UX1B_RENDER_MANIFEST_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_RENDER_MANIFEST_CAPTURE_ID)" || (echo "UX1B_RENDER_MANIFEST_CAPTURE_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py verify-render-manifest-correction-preflight \
		--correction-id "$(UX1B_RENDER_MANIFEST_CORRECTION_ID)" \
		--tier-id "$(UX1B_RENDER_MANIFEST_TIER_ID)" \
		--capture-id "$(UX1B_RENDER_MANIFEST_CAPTURE_ID)" --json

ui-ux1b-render-manifest-capture: ## Capture the exact Sequence 13 36/44 root matrix
	@test -n "$(UX1B_RENDER_MANIFEST_CORRECTION_ID)" || (echo "UX1B_RENDER_MANIFEST_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_RENDER_MANIFEST_TIER_ID)" || (echo "UX1B_RENDER_MANIFEST_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_RENDER_MANIFEST_CAPTURE_ID)" || (echo "UX1B_RENDER_MANIFEST_CAPTURE_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py capture-render-manifest-controls \
		--correction-id "$(UX1B_RENDER_MANIFEST_CORRECTION_ID)" \
		--tier-id "$(UX1B_RENDER_MANIFEST_TIER_ID)" \
		--capture-id "$(UX1B_RENDER_MANIFEST_CAPTURE_ID)" --json

ui-ux1b-render-manifest-reconcile: ## Reconcile the retained Sequence 13 capture prefix
	@test -n "$(UX1B_RENDER_MANIFEST_CORRECTION_ID)" || (echo "UX1B_RENDER_MANIFEST_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_RENDER_MANIFEST_TIER_ID)" || (echo "UX1B_RENDER_MANIFEST_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_RENDER_MANIFEST_CAPTURE_ID)" || (echo "UX1B_RENDER_MANIFEST_CAPTURE_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py reconcile-render-manifest-controls \
		--correction-id "$(UX1B_RENDER_MANIFEST_CORRECTION_ID)" \
		--tier-id "$(UX1B_RENDER_MANIFEST_TIER_ID)" \
		--capture-id "$(UX1B_RENDER_MANIFEST_CAPTURE_ID)" --json

ui-ux1b-render-manifest-compare: ## Publish the Sequence 13 81/44/125 migration report
	@test -n "$(UX1B_RENDER_MANIFEST_CORRECTION_ID)" || (echo "UX1B_RENDER_MANIFEST_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_RENDER_MANIFEST_TIER_ID)" || (echo "UX1B_RENDER_MANIFEST_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_RENDER_MANIFEST_CAPTURE_ID)" || (echo "UX1B_RENDER_MANIFEST_CAPTURE_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py compare-render-manifest-migration \
		--correction-id "$(UX1B_RENDER_MANIFEST_CORRECTION_ID)" \
		--tier-id "$(UX1B_RENDER_MANIFEST_TIER_ID)" \
		--capture-id "$(UX1B_RENDER_MANIFEST_CAPTURE_ID)" --json

ui-ux1b-render-manifest-prepare-review: ## Prepare the Sequence 13 125-item packet and stop at M3
	@test -n "$(UX1B_RENDER_MANIFEST_CORRECTION_ID)" || (echo "UX1B_RENDER_MANIFEST_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_RENDER_MANIFEST_TIER_ID)" || (echo "UX1B_RENDER_MANIFEST_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_RENDER_MANIFEST_CAPTURE_ID)" || (echo "UX1B_RENDER_MANIFEST_CAPTURE_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py prepare-render-manifest-review \
		--correction-id "$(UX1B_RENDER_MANIFEST_CORRECTION_ID)" \
		--tier-id "$(UX1B_RENDER_MANIFEST_TIER_ID)" \
		--capture-id "$(UX1B_RENDER_MANIFEST_CAPTURE_ID)" --json

ui-ux1b-historical-stack-bootstrap: ## Bootstrap the Sequence 14 historical-stack comparator correction
	@test -n "$(UX1B_HISTORICAL_STACK_CORRECTION_ID)" || (echo "UX1B_HISTORICAL_STACK_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_HISTORICAL_STACK_TIER_ID)" || (echo "UX1B_HISTORICAL_STACK_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_HISTORICAL_STACK_CAPTURE_ID)" || (echo "UX1B_HISTORICAL_STACK_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_HISTORICAL_STACK_CONTINUATION_ID)" || (echo "UX1B_HISTORICAL_STACK_CONTINUATION_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py bootstrap-historical-stack-comparator-correction \
		--correction-id "$(UX1B_HISTORICAL_STACK_CORRECTION_ID)" \
		--tier-id "$(UX1B_HISTORICAL_STACK_TIER_ID)" \
		--capture-id "$(UX1B_HISTORICAL_STACK_CAPTURE_ID)" \
		--continuation-id "$(UX1B_HISTORICAL_STACK_CONTINUATION_ID)" --json

ui-ux1b-historical-stack-preflight: ## Publish the Sequence 14 historical-stack preflight
	@test -n "$(UX1B_HISTORICAL_STACK_CORRECTION_ID)" || (echo "UX1B_HISTORICAL_STACK_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_HISTORICAL_STACK_TIER_ID)" || (echo "UX1B_HISTORICAL_STACK_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_HISTORICAL_STACK_CAPTURE_ID)" || (echo "UX1B_HISTORICAL_STACK_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_HISTORICAL_STACK_CONTINUATION_ID)" || (echo "UX1B_HISTORICAL_STACK_CONTINUATION_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py preflight-historical-stack-comparator-correction \
		--correction-id "$(UX1B_HISTORICAL_STACK_CORRECTION_ID)" \
		--tier-id "$(UX1B_HISTORICAL_STACK_TIER_ID)" \
		--capture-id "$(UX1B_HISTORICAL_STACK_CAPTURE_ID)" \
		--continuation-id "$(UX1B_HISTORICAL_STACK_CONTINUATION_ID)" --json

ui-ux1b-historical-stack-verify: ## Reopen the Sequence 14 historical-stack preflight
	@test -n "$(UX1B_HISTORICAL_STACK_CORRECTION_ID)" || (echo "UX1B_HISTORICAL_STACK_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_HISTORICAL_STACK_TIER_ID)" || (echo "UX1B_HISTORICAL_STACK_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_HISTORICAL_STACK_CAPTURE_ID)" || (echo "UX1B_HISTORICAL_STACK_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_HISTORICAL_STACK_CONTINUATION_ID)" || (echo "UX1B_HISTORICAL_STACK_CONTINUATION_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py verify-historical-stack-comparator-correction-preflight \
		--correction-id "$(UX1B_HISTORICAL_STACK_CORRECTION_ID)" \
		--tier-id "$(UX1B_HISTORICAL_STACK_TIER_ID)" \
		--capture-id "$(UX1B_HISTORICAL_STACK_CAPTURE_ID)" \
		--continuation-id "$(UX1B_HISTORICAL_STACK_CONTINUATION_ID)" --json

ui-ux1b-historical-stack-compare: ## Publish the Sequence 14 81/44/125 migration report
	@test -n "$(UX1B_HISTORICAL_STACK_CORRECTION_ID)" || (echo "UX1B_HISTORICAL_STACK_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_HISTORICAL_STACK_TIER_ID)" || (echo "UX1B_HISTORICAL_STACK_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_HISTORICAL_STACK_CAPTURE_ID)" || (echo "UX1B_HISTORICAL_STACK_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_HISTORICAL_STACK_CONTINUATION_ID)" || (echo "UX1B_HISTORICAL_STACK_CONTINUATION_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py compare-historical-stack-migration \
		--correction-id "$(UX1B_HISTORICAL_STACK_CORRECTION_ID)" \
		--tier-id "$(UX1B_HISTORICAL_STACK_TIER_ID)" \
		--capture-id "$(UX1B_HISTORICAL_STACK_CAPTURE_ID)" \
		--continuation-id "$(UX1B_HISTORICAL_STACK_CONTINUATION_ID)" --json

ui-ux1b-historical-stack-prepare-review: ## Prepare the Sequence 14 125-item packet and stop at H2
	@test -n "$(UX1B_HISTORICAL_STACK_CORRECTION_ID)" || (echo "UX1B_HISTORICAL_STACK_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_HISTORICAL_STACK_TIER_ID)" || (echo "UX1B_HISTORICAL_STACK_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_HISTORICAL_STACK_CAPTURE_ID)" || (echo "UX1B_HISTORICAL_STACK_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_HISTORICAL_STACK_CONTINUATION_ID)" || (echo "UX1B_HISTORICAL_STACK_CONTINUATION_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py prepare-historical-stack-review \
		--correction-id "$(UX1B_HISTORICAL_STACK_CORRECTION_ID)" \
		--tier-id "$(UX1B_HISTORICAL_STACK_TIER_ID)" \
		--capture-id "$(UX1B_HISTORICAL_STACK_CAPTURE_ID)" \
		--continuation-id "$(UX1B_HISTORICAL_STACK_CONTINUATION_ID)" --json

ui-ux1b-external-review-bootstrap: ## Bootstrap the accepted Sequence 15 external-review continuation
	@test -n "$(UX1B_EXTERNAL_REVIEW_CAPTURE_ID)" || (echo "UX1B_EXTERNAL_REVIEW_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_EXTERNAL_REVIEW_PARENT_CONTINUATION_ID)" || (echo "UX1B_EXTERNAL_REVIEW_PARENT_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_EXTERNAL_REVIEW_CORRECTION_ID)" || (echo "UX1B_EXTERNAL_REVIEW_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_EXTERNAL_REVIEW_TIER_ID)" || (echo "UX1B_EXTERNAL_REVIEW_TIER_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py bootstrap-historical-stack-external-review-continuation \
		--capture-id "$(UX1B_EXTERNAL_REVIEW_CAPTURE_ID)" \
		--parent-continuation-id "$(UX1B_EXTERNAL_REVIEW_PARENT_CONTINUATION_ID)" \
		--external-review-correction-id "$(UX1B_EXTERNAL_REVIEW_CORRECTION_ID)" \
		--external-review-tier-id "$(UX1B_EXTERNAL_REVIEW_TIER_ID)" --json

ui-ux1b-external-review-preflight: ## Publish the accepted Sequence 15 external-review preflight
	@test -n "$(UX1B_EXTERNAL_REVIEW_CAPTURE_ID)" || (echo "UX1B_EXTERNAL_REVIEW_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_EXTERNAL_REVIEW_PARENT_CONTINUATION_ID)" || (echo "UX1B_EXTERNAL_REVIEW_PARENT_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_EXTERNAL_REVIEW_CORRECTION_ID)" || (echo "UX1B_EXTERNAL_REVIEW_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_EXTERNAL_REVIEW_TIER_ID)" || (echo "UX1B_EXTERNAL_REVIEW_TIER_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py preflight-historical-stack-external-review-continuation \
		--capture-id "$(UX1B_EXTERNAL_REVIEW_CAPTURE_ID)" \
		--parent-continuation-id "$(UX1B_EXTERNAL_REVIEW_PARENT_CONTINUATION_ID)" \
		--external-review-correction-id "$(UX1B_EXTERNAL_REVIEW_CORRECTION_ID)" \
		--external-review-tier-id "$(UX1B_EXTERNAL_REVIEW_TIER_ID)" --json

ui-ux1b-external-review-verify: ## Reopen the Sequence 15 external-review preflight and current E0-E2 state
	@test -n "$(UX1B_EXTERNAL_REVIEW_CAPTURE_ID)" || (echo "UX1B_EXTERNAL_REVIEW_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_EXTERNAL_REVIEW_PARENT_CONTINUATION_ID)" || (echo "UX1B_EXTERNAL_REVIEW_PARENT_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_EXTERNAL_REVIEW_CORRECTION_ID)" || (echo "UX1B_EXTERNAL_REVIEW_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_EXTERNAL_REVIEW_TIER_ID)" || (echo "UX1B_EXTERNAL_REVIEW_TIER_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py verify-historical-stack-external-review-continuation-preflight \
		--capture-id "$(UX1B_EXTERNAL_REVIEW_CAPTURE_ID)" \
		--parent-continuation-id "$(UX1B_EXTERNAL_REVIEW_PARENT_CONTINUATION_ID)" \
		--external-review-correction-id "$(UX1B_EXTERNAL_REVIEW_CORRECTION_ID)" \
		--external-review-tier-id "$(UX1B_EXTERNAL_REVIEW_TIER_ID)" --json

ui-ux1b-external-review-submit-intake: ## Broker exact maintainer-accepted reviewer bytes from stdin
	@test -n "$(UX1B_EXTERNAL_REVIEW_CAPTURE_ID)" || (echo "UX1B_EXTERNAL_REVIEW_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_EXTERNAL_REVIEW_PARENT_CONTINUATION_ID)" || (echo "UX1B_EXTERNAL_REVIEW_PARENT_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_EXTERNAL_REVIEW_CORRECTION_ID)" || (echo "UX1B_EXTERNAL_REVIEW_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_EXTERNAL_REVIEW_TIER_ID)" || (echo "UX1B_EXTERNAL_REVIEW_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_EXTERNAL_REVIEW_INTAKE_SHA256)" || (echo "UX1B_EXTERNAL_REVIEW_INTAKE_SHA256 is required" >&2; exit 2)
	@test -n "$(UX1B_EXTERNAL_REVIEW_INTAKE_SIZE)" || (echo "UX1B_EXTERNAL_REVIEW_INTAKE_SIZE is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py submit-historical-stack-review-intake \
		--capture-id "$(UX1B_EXTERNAL_REVIEW_CAPTURE_ID)" \
		--parent-continuation-id "$(UX1B_EXTERNAL_REVIEW_PARENT_CONTINUATION_ID)" \
		--external-review-correction-id "$(UX1B_EXTERNAL_REVIEW_CORRECTION_ID)" \
		--external-review-tier-id "$(UX1B_EXTERNAL_REVIEW_TIER_ID)" \
		--intake-stdin \
		--accepted-intake-sha256 "$(UX1B_EXTERNAL_REVIEW_INTAKE_SHA256)" \
		--accepted-intake-size "$(UX1B_EXTERNAL_REVIEW_INTAKE_SIZE)" --json

ui-ux1b-external-review-publish: ## Publish the exact Sequence 15 intake as manual review and stop at E2
	@test -n "$(UX1B_EXTERNAL_REVIEW_CAPTURE_ID)" || (echo "UX1B_EXTERNAL_REVIEW_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_EXTERNAL_REVIEW_PARENT_CONTINUATION_ID)" || (echo "UX1B_EXTERNAL_REVIEW_PARENT_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_EXTERNAL_REVIEW_CORRECTION_ID)" || (echo "UX1B_EXTERNAL_REVIEW_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_EXTERNAL_REVIEW_TIER_ID)" || (echo "UX1B_EXTERNAL_REVIEW_TIER_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py publish-historical-stack-review \
		--capture-id "$(UX1B_EXTERNAL_REVIEW_CAPTURE_ID)" \
		--parent-continuation-id "$(UX1B_EXTERNAL_REVIEW_PARENT_CONTINUATION_ID)" \
		--external-review-correction-id "$(UX1B_EXTERNAL_REVIEW_CORRECTION_ID)" \
		--external-review-tier-id "$(UX1B_EXTERNAL_REVIEW_TIER_ID)" --json

ui-ux1b-external-review-lifecycle-test-bootstrap: ## Create or reopen the Sequence 16 lifecycle-test correction Tier
	@test -n "$(UX1B_LIFECYCLE_TEST_CAPTURE_ID)" || (echo "UX1B_LIFECYCLE_TEST_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_PARENT_CONTINUATION_ID)" || (echo "UX1B_LIFECYCLE_TEST_PARENT_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_PARENT_REVIEW_ID)" || (echo "UX1B_LIFECYCLE_TEST_PARENT_REVIEW_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_CORRECTION_ID)" || (echo "UX1B_LIFECYCLE_TEST_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_TIER_ID)" || (echo "UX1B_LIFECYCLE_TEST_TIER_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py bootstrap-external-review-lifecycle-test-correction \
		--capture-id "$(UX1B_LIFECYCLE_TEST_CAPTURE_ID)" \
		--parent-continuation-id "$(UX1B_LIFECYCLE_TEST_PARENT_CONTINUATION_ID)" \
		--parent-external-review-correction-id "$(UX1B_LIFECYCLE_TEST_PARENT_REVIEW_ID)" \
		--lifecycle-test-correction-id "$(UX1B_LIFECYCLE_TEST_CORRECTION_ID)" \
		--lifecycle-test-tier-id "$(UX1B_LIFECYCLE_TEST_TIER_ID)" --json

ui-ux1b-external-review-lifecycle-test-preflight: ## Publish or reopen the Sequence 16 C0 preflight
	@test -n "$(UX1B_LIFECYCLE_TEST_CAPTURE_ID)" || (echo "UX1B_LIFECYCLE_TEST_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_PARENT_CONTINUATION_ID)" || (echo "UX1B_LIFECYCLE_TEST_PARENT_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_PARENT_REVIEW_ID)" || (echo "UX1B_LIFECYCLE_TEST_PARENT_REVIEW_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_CORRECTION_ID)" || (echo "UX1B_LIFECYCLE_TEST_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_TIER_ID)" || (echo "UX1B_LIFECYCLE_TEST_TIER_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py preflight-external-review-lifecycle-test-correction \
		--capture-id "$(UX1B_LIFECYCLE_TEST_CAPTURE_ID)" \
		--parent-continuation-id "$(UX1B_LIFECYCLE_TEST_PARENT_CONTINUATION_ID)" \
		--parent-external-review-correction-id "$(UX1B_LIFECYCLE_TEST_PARENT_REVIEW_ID)" \
		--lifecycle-test-correction-id "$(UX1B_LIFECYCLE_TEST_CORRECTION_ID)" \
		--lifecycle-test-tier-id "$(UX1B_LIFECYCLE_TEST_TIER_ID)" --json

ui-ux1b-external-review-lifecycle-test-verify: ## Reopen the Sequence 16 C0-C2 lifecycle
	@test -n "$(UX1B_LIFECYCLE_TEST_CAPTURE_ID)" || (echo "UX1B_LIFECYCLE_TEST_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_PARENT_CONTINUATION_ID)" || (echo "UX1B_LIFECYCLE_TEST_PARENT_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_PARENT_REVIEW_ID)" || (echo "UX1B_LIFECYCLE_TEST_PARENT_REVIEW_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_CORRECTION_ID)" || (echo "UX1B_LIFECYCLE_TEST_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_TIER_ID)" || (echo "UX1B_LIFECYCLE_TEST_TIER_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py verify-external-review-lifecycle-test-correction-preflight \
		--capture-id "$(UX1B_LIFECYCLE_TEST_CAPTURE_ID)" \
		--parent-continuation-id "$(UX1B_LIFECYCLE_TEST_PARENT_CONTINUATION_ID)" \
		--parent-external-review-correction-id "$(UX1B_LIFECYCLE_TEST_PARENT_REVIEW_ID)" \
		--lifecycle-test-correction-id "$(UX1B_LIFECYCLE_TEST_CORRECTION_ID)" \
		--lifecycle-test-tier-id "$(UX1B_LIFECYCLE_TEST_TIER_ID)" --json

ui-ux1b-external-review-lifecycle-test-submit-intake: ## Broker exact accepted Sequence 16 reviewer bytes from stdin
	@test -n "$(UX1B_LIFECYCLE_TEST_CAPTURE_ID)" || (echo "UX1B_LIFECYCLE_TEST_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_PARENT_CONTINUATION_ID)" || (echo "UX1B_LIFECYCLE_TEST_PARENT_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_PARENT_REVIEW_ID)" || (echo "UX1B_LIFECYCLE_TEST_PARENT_REVIEW_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_CORRECTION_ID)" || (echo "UX1B_LIFECYCLE_TEST_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_TIER_ID)" || (echo "UX1B_LIFECYCLE_TEST_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_INTAKE_SHA256)" || (echo "UX1B_LIFECYCLE_TEST_INTAKE_SHA256 is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_INTAKE_SIZE)" || (echo "UX1B_LIFECYCLE_TEST_INTAKE_SIZE is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py submit-lifecycle-test-corrected-review-intake \
		--capture-id "$(UX1B_LIFECYCLE_TEST_CAPTURE_ID)" \
		--parent-continuation-id "$(UX1B_LIFECYCLE_TEST_PARENT_CONTINUATION_ID)" \
		--parent-external-review-correction-id "$(UX1B_LIFECYCLE_TEST_PARENT_REVIEW_ID)" \
		--lifecycle-test-correction-id "$(UX1B_LIFECYCLE_TEST_CORRECTION_ID)" \
		--lifecycle-test-tier-id "$(UX1B_LIFECYCLE_TEST_TIER_ID)" \
		--intake-stdin \
		--accepted-intake-sha256 "$(UX1B_LIFECYCLE_TEST_INTAKE_SHA256)" \
		--accepted-intake-size "$(UX1B_LIFECYCLE_TEST_INTAKE_SIZE)" --json

ui-ux1b-external-review-lifecycle-test-publish: ## Publish the exact Sequence 16 intake and stop at C2
	@test -n "$(UX1B_LIFECYCLE_TEST_CAPTURE_ID)" || (echo "UX1B_LIFECYCLE_TEST_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_PARENT_CONTINUATION_ID)" || (echo "UX1B_LIFECYCLE_TEST_PARENT_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_PARENT_REVIEW_ID)" || (echo "UX1B_LIFECYCLE_TEST_PARENT_REVIEW_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_CORRECTION_ID)" || (echo "UX1B_LIFECYCLE_TEST_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_TEST_TIER_ID)" || (echo "UX1B_LIFECYCLE_TEST_TIER_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py publish-lifecycle-test-corrected-review \
		--capture-id "$(UX1B_LIFECYCLE_TEST_CAPTURE_ID)" \
		--parent-continuation-id "$(UX1B_LIFECYCLE_TEST_PARENT_CONTINUATION_ID)" \
		--parent-external-review-correction-id "$(UX1B_LIFECYCLE_TEST_PARENT_REVIEW_ID)" \
		--lifecycle-test-correction-id "$(UX1B_LIFECYCLE_TEST_CORRECTION_ID)" \
		--lifecycle-test-tier-id "$(UX1B_LIFECYCLE_TEST_TIER_ID)" --json

ui-ux1b-external-review-formal-state-oracle-bootstrap: ## Create or reopen the Sequence 17 formal-state oracle Tier
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_CAPTURE_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_PACKET_CONTINUATION_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_PACKET_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_PARENT_LIFECYCLE_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_PARENT_LIFECYCLE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_CORRECTION_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_TIER_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_TIER_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py bootstrap-external-review-formal-state-oracle-correction \
		--capture-id "$(UX1B_FORMAL_STATE_ORACLE_CAPTURE_ID)" \
		--packet-continuation-id "$(UX1B_FORMAL_STATE_ORACLE_PACKET_CONTINUATION_ID)" \
		--parent-lifecycle-correction-id "$(UX1B_FORMAL_STATE_ORACLE_PARENT_LIFECYCLE_ID)" \
		--formal-state-oracle-correction-id "$(UX1B_FORMAL_STATE_ORACLE_CORRECTION_ID)" \
		--formal-state-oracle-tier-id "$(UX1B_FORMAL_STATE_ORACLE_TIER_ID)" --json

ui-ux1b-external-review-formal-state-oracle-preflight: ## Publish or reopen the Sequence 17 O0 preflight
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_CAPTURE_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_PACKET_CONTINUATION_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_PACKET_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_PARENT_LIFECYCLE_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_PARENT_LIFECYCLE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_CORRECTION_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_TIER_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_TIER_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py preflight-external-review-formal-state-oracle-correction \
		--capture-id "$(UX1B_FORMAL_STATE_ORACLE_CAPTURE_ID)" \
		--packet-continuation-id "$(UX1B_FORMAL_STATE_ORACLE_PACKET_CONTINUATION_ID)" \
		--parent-lifecycle-correction-id "$(UX1B_FORMAL_STATE_ORACLE_PARENT_LIFECYCLE_ID)" \
		--formal-state-oracle-correction-id "$(UX1B_FORMAL_STATE_ORACLE_CORRECTION_ID)" \
		--formal-state-oracle-tier-id "$(UX1B_FORMAL_STATE_ORACLE_TIER_ID)" --json

ui-ux1b-external-review-formal-state-oracle-verify: ## Reopen the Sequence 17 O0-O2 lifecycle
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_CAPTURE_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_PACKET_CONTINUATION_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_PACKET_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_PARENT_LIFECYCLE_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_PARENT_LIFECYCLE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_CORRECTION_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_TIER_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_TIER_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py verify-external-review-formal-state-oracle-correction-preflight \
		--capture-id "$(UX1B_FORMAL_STATE_ORACLE_CAPTURE_ID)" \
		--packet-continuation-id "$(UX1B_FORMAL_STATE_ORACLE_PACKET_CONTINUATION_ID)" \
		--parent-lifecycle-correction-id "$(UX1B_FORMAL_STATE_ORACLE_PARENT_LIFECYCLE_ID)" \
		--formal-state-oracle-correction-id "$(UX1B_FORMAL_STATE_ORACLE_CORRECTION_ID)" \
		--formal-state-oracle-tier-id "$(UX1B_FORMAL_STATE_ORACLE_TIER_ID)" --json

ui-ux1b-external-review-formal-state-oracle-submit-intake: ## Broker exact accepted Sequence 17 reviewer bytes from stdin
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_CAPTURE_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_PACKET_CONTINUATION_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_PACKET_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_PARENT_LIFECYCLE_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_PARENT_LIFECYCLE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_CORRECTION_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_TIER_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_TIER_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_INTAKE_SHA256)" || (echo "UX1B_FORMAL_STATE_ORACLE_INTAKE_SHA256 is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_INTAKE_SIZE)" || (echo "UX1B_FORMAL_STATE_ORACLE_INTAKE_SIZE is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py submit-formal-state-corrected-review-intake \
		--capture-id "$(UX1B_FORMAL_STATE_ORACLE_CAPTURE_ID)" \
		--packet-continuation-id "$(UX1B_FORMAL_STATE_ORACLE_PACKET_CONTINUATION_ID)" \
		--parent-lifecycle-correction-id "$(UX1B_FORMAL_STATE_ORACLE_PARENT_LIFECYCLE_ID)" \
		--formal-state-oracle-correction-id "$(UX1B_FORMAL_STATE_ORACLE_CORRECTION_ID)" \
		--formal-state-oracle-tier-id "$(UX1B_FORMAL_STATE_ORACLE_TIER_ID)" \
		--intake-stdin \
		--accepted-intake-sha256 "$(UX1B_FORMAL_STATE_ORACLE_INTAKE_SHA256)" \
		--accepted-intake-size "$(UX1B_FORMAL_STATE_ORACLE_INTAKE_SIZE)" --json

ui-ux1b-external-review-formal-state-oracle-publish: ## Publish the exact Sequence 17 intake and stop at O2
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_CAPTURE_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_PACKET_CONTINUATION_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_PACKET_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_PARENT_LIFECYCLE_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_PARENT_LIFECYCLE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_CORRECTION_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_FORMAL_STATE_ORACLE_TIER_ID)" || (echo "UX1B_FORMAL_STATE_ORACLE_TIER_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py publish-formal-state-corrected-review \
		--capture-id "$(UX1B_FORMAL_STATE_ORACLE_CAPTURE_ID)" \
		--packet-continuation-id "$(UX1B_FORMAL_STATE_ORACLE_PACKET_CONTINUATION_ID)" \
		--parent-lifecycle-correction-id "$(UX1B_FORMAL_STATE_ORACLE_PARENT_LIFECYCLE_ID)" \
		--formal-state-oracle-correction-id "$(UX1B_FORMAL_STATE_ORACLE_CORRECTION_ID)" \
		--formal-state-oracle-tier-id "$(UX1B_FORMAL_STATE_ORACLE_TIER_ID)" --json

ui-ux1b-external-review-o1-lifecycle-test-bootstrap: ## Create or resume the Sequence 18 O1 lifecycle-test correction Tier
	@test -n "$(UX1B_O1_LIFECYCLE_CAPTURE_ID)" || (echo "UX1B_O1_LIFECYCLE_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_O1_LIFECYCLE_PACKET_CONTINUATION_ID)" || (echo "UX1B_O1_LIFECYCLE_PACKET_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_O1_LIFECYCLE_PARENT_CORRECTION_ID)" || (echo "UX1B_O1_LIFECYCLE_PARENT_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_O1_LIFECYCLE_CORRECTION_ID)" || (echo "UX1B_O1_LIFECYCLE_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_O1_LIFECYCLE_TIER_ID)" || (echo "UX1B_O1_LIFECYCLE_TIER_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py bootstrap-external-review-o1-lifecycle-test-correction \
		--capture-id "$(UX1B_O1_LIFECYCLE_CAPTURE_ID)" \
		--packet-continuation-id "$(UX1B_O1_LIFECYCLE_PACKET_CONTINUATION_ID)" \
		--parent-formal-state-oracle-correction-id "$(UX1B_O1_LIFECYCLE_PARENT_CORRECTION_ID)" \
		--o1-lifecycle-test-correction-id "$(UX1B_O1_LIFECYCLE_CORRECTION_ID)" \
		--o1-lifecycle-test-tier-id "$(UX1B_O1_LIFECYCLE_TIER_ID)" --json

ui-ux1b-external-review-o1-lifecycle-test-preflight: ## Publish or reopen the Sequence 18 V1 preflight
	@test -n "$(UX1B_O1_LIFECYCLE_CAPTURE_ID)" || (echo "UX1B_O1_LIFECYCLE_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_O1_LIFECYCLE_PACKET_CONTINUATION_ID)" || (echo "UX1B_O1_LIFECYCLE_PACKET_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_O1_LIFECYCLE_PARENT_CORRECTION_ID)" || (echo "UX1B_O1_LIFECYCLE_PARENT_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_O1_LIFECYCLE_CORRECTION_ID)" || (echo "UX1B_O1_LIFECYCLE_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_O1_LIFECYCLE_TIER_ID)" || (echo "UX1B_O1_LIFECYCLE_TIER_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py preflight-external-review-o1-lifecycle-test-correction \
		--capture-id "$(UX1B_O1_LIFECYCLE_CAPTURE_ID)" \
		--packet-continuation-id "$(UX1B_O1_LIFECYCLE_PACKET_CONTINUATION_ID)" \
		--parent-formal-state-oracle-correction-id "$(UX1B_O1_LIFECYCLE_PARENT_CORRECTION_ID)" \
		--o1-lifecycle-test-correction-id "$(UX1B_O1_LIFECYCLE_CORRECTION_ID)" \
		--o1-lifecycle-test-tier-id "$(UX1B_O1_LIFECYCLE_TIER_ID)" --json

ui-ux1b-external-review-o1-lifecycle-test-verify: ## Reopen the Sequence 18 V1-V2 lifecycle
	@test -n "$(UX1B_O1_LIFECYCLE_CAPTURE_ID)" || (echo "UX1B_O1_LIFECYCLE_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_O1_LIFECYCLE_PACKET_CONTINUATION_ID)" || (echo "UX1B_O1_LIFECYCLE_PACKET_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_O1_LIFECYCLE_PARENT_CORRECTION_ID)" || (echo "UX1B_O1_LIFECYCLE_PARENT_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_O1_LIFECYCLE_CORRECTION_ID)" || (echo "UX1B_O1_LIFECYCLE_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_O1_LIFECYCLE_TIER_ID)" || (echo "UX1B_O1_LIFECYCLE_TIER_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py verify-external-review-o1-lifecycle-test-correction-preflight \
		--capture-id "$(UX1B_O1_LIFECYCLE_CAPTURE_ID)" \
		--packet-continuation-id "$(UX1B_O1_LIFECYCLE_PACKET_CONTINUATION_ID)" \
		--parent-formal-state-oracle-correction-id "$(UX1B_O1_LIFECYCLE_PARENT_CORRECTION_ID)" \
		--o1-lifecycle-test-correction-id "$(UX1B_O1_LIFECYCLE_CORRECTION_ID)" \
		--o1-lifecycle-test-tier-id "$(UX1B_O1_LIFECYCLE_TIER_ID)" --json

ui-ux1b-external-review-o1-lifecycle-test-publish: ## Publish the retained accepted intake and stop at Sequence 18 V2
	@test -n "$(UX1B_O1_LIFECYCLE_CAPTURE_ID)" || (echo "UX1B_O1_LIFECYCLE_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_O1_LIFECYCLE_PACKET_CONTINUATION_ID)" || (echo "UX1B_O1_LIFECYCLE_PACKET_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_O1_LIFECYCLE_PARENT_CORRECTION_ID)" || (echo "UX1B_O1_LIFECYCLE_PARENT_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_O1_LIFECYCLE_CORRECTION_ID)" || (echo "UX1B_O1_LIFECYCLE_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_O1_LIFECYCLE_TIER_ID)" || (echo "UX1B_O1_LIFECYCLE_TIER_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py publish-o1-lifecycle-test-corrected-review \
		--capture-id "$(UX1B_O1_LIFECYCLE_CAPTURE_ID)" \
		--packet-continuation-id "$(UX1B_O1_LIFECYCLE_PACKET_CONTINUATION_ID)" \
		--parent-formal-state-oracle-correction-id "$(UX1B_O1_LIFECYCLE_PARENT_CORRECTION_ID)" \
		--o1-lifecycle-test-correction-id "$(UX1B_O1_LIFECYCLE_CORRECTION_ID)" \
		--o1-lifecycle-test-tier-id "$(UX1B_O1_LIFECYCLE_TIER_ID)" --json

ui-ux1b-external-review-v1-lifecycle-test-bootstrap: ## Create or resume the Sequence 19 post-V1 correction Tier
	@test -n "$(UX1B_V1_LIFECYCLE_CAPTURE_ID)" || (echo "UX1B_V1_LIFECYCLE_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_V1_LIFECYCLE_PACKET_CONTINUATION_ID)" || (echo "UX1B_V1_LIFECYCLE_PACKET_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_V1_LIFECYCLE_PARENT_CORRECTION_ID)" || (echo "UX1B_V1_LIFECYCLE_PARENT_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_V1_LIFECYCLE_CORRECTION_ID)" || (echo "UX1B_V1_LIFECYCLE_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_V1_LIFECYCLE_TIER_ID)" || (echo "UX1B_V1_LIFECYCLE_TIER_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py bootstrap-external-review-v1-lifecycle-test-correction \
		--capture-id "$(UX1B_V1_LIFECYCLE_CAPTURE_ID)" \
		--packet-continuation-id "$(UX1B_V1_LIFECYCLE_PACKET_CONTINUATION_ID)" \
		--parent-o1-lifecycle-test-correction-id "$(UX1B_V1_LIFECYCLE_PARENT_CORRECTION_ID)" \
		--v1-lifecycle-test-correction-id "$(UX1B_V1_LIFECYCLE_CORRECTION_ID)" \
		--v1-lifecycle-test-tier-id "$(UX1B_V1_LIFECYCLE_TIER_ID)" --json

ui-ux1b-external-review-v1-lifecycle-test-preflight: ## Publish or reopen the Sequence 19 W1 preflight
	@test -n "$(UX1B_V1_LIFECYCLE_CAPTURE_ID)" || (echo "UX1B_V1_LIFECYCLE_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_V1_LIFECYCLE_PACKET_CONTINUATION_ID)" || (echo "UX1B_V1_LIFECYCLE_PACKET_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_V1_LIFECYCLE_PARENT_CORRECTION_ID)" || (echo "UX1B_V1_LIFECYCLE_PARENT_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_V1_LIFECYCLE_CORRECTION_ID)" || (echo "UX1B_V1_LIFECYCLE_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_V1_LIFECYCLE_TIER_ID)" || (echo "UX1B_V1_LIFECYCLE_TIER_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py preflight-external-review-v1-lifecycle-test-correction \
		--capture-id "$(UX1B_V1_LIFECYCLE_CAPTURE_ID)" \
		--packet-continuation-id "$(UX1B_V1_LIFECYCLE_PACKET_CONTINUATION_ID)" \
		--parent-o1-lifecycle-test-correction-id "$(UX1B_V1_LIFECYCLE_PARENT_CORRECTION_ID)" \
		--v1-lifecycle-test-correction-id "$(UX1B_V1_LIFECYCLE_CORRECTION_ID)" \
		--v1-lifecycle-test-tier-id "$(UX1B_V1_LIFECYCLE_TIER_ID)" --json

ui-ux1b-external-review-v1-lifecycle-test-verify: ## Reopen the Sequence 19 W1-W2 lifecycle
	@test -n "$(UX1B_V1_LIFECYCLE_CAPTURE_ID)" || (echo "UX1B_V1_LIFECYCLE_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_V1_LIFECYCLE_PACKET_CONTINUATION_ID)" || (echo "UX1B_V1_LIFECYCLE_PACKET_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_V1_LIFECYCLE_PARENT_CORRECTION_ID)" || (echo "UX1B_V1_LIFECYCLE_PARENT_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_V1_LIFECYCLE_CORRECTION_ID)" || (echo "UX1B_V1_LIFECYCLE_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_V1_LIFECYCLE_TIER_ID)" || (echo "UX1B_V1_LIFECYCLE_TIER_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py verify-external-review-v1-lifecycle-test-correction-preflight \
		--capture-id "$(UX1B_V1_LIFECYCLE_CAPTURE_ID)" \
		--packet-continuation-id "$(UX1B_V1_LIFECYCLE_PACKET_CONTINUATION_ID)" \
		--parent-o1-lifecycle-test-correction-id "$(UX1B_V1_LIFECYCLE_PARENT_CORRECTION_ID)" \
		--v1-lifecycle-test-correction-id "$(UX1B_V1_LIFECYCLE_CORRECTION_ID)" \
		--v1-lifecycle-test-tier-id "$(UX1B_V1_LIFECYCLE_TIER_ID)" --json

ui-ux1b-external-review-v1-lifecycle-test-publish: ## Publish the retained intake and stop at Sequence 19 W2
	@test -n "$(UX1B_V1_LIFECYCLE_CAPTURE_ID)" || (echo "UX1B_V1_LIFECYCLE_CAPTURE_ID is required" >&2; exit 2)
	@test -n "$(UX1B_V1_LIFECYCLE_PACKET_CONTINUATION_ID)" || (echo "UX1B_V1_LIFECYCLE_PACKET_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_V1_LIFECYCLE_PARENT_CORRECTION_ID)" || (echo "UX1B_V1_LIFECYCLE_PARENT_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_V1_LIFECYCLE_CORRECTION_ID)" || (echo "UX1B_V1_LIFECYCLE_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_V1_LIFECYCLE_TIER_ID)" || (echo "UX1B_V1_LIFECYCLE_TIER_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py publish-v1-lifecycle-test-corrected-review \
		--capture-id "$(UX1B_V1_LIFECYCLE_CAPTURE_ID)" \
		--packet-continuation-id "$(UX1B_V1_LIFECYCLE_PACKET_CONTINUATION_ID)" \
		--parent-o1-lifecycle-test-correction-id "$(UX1B_V1_LIFECYCLE_PARENT_CORRECTION_ID)" \
		--v1-lifecycle-test-correction-id "$(UX1B_V1_LIFECYCLE_CORRECTION_ID)" \
		--v1-lifecycle-test-tier-id "$(UX1B_V1_LIFECYCLE_TIER_ID)" --json

ui-ux1b-theme-states: ## Capture the mandatory Chromium UX-1B semantic-state gallery
	@test -n "$(UX1B_THEME_RUN_ID)" || (echo "UX1B_THEME_RUN_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py capture-theme-states \
		--theme-run-id "$(UX1B_THEME_RUN_ID)" --json

ui-ux1b-theme-states-reconcile: ## Reconcile a previously started theme-state capture
	@test -n "$(UX1B_THEME_RUN_ID)" || (echo "UX1B_THEME_RUN_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py reconcile-theme-states \
		--theme-run-id "$(UX1B_THEME_RUN_ID)" --json

ui-ux1b-theme-states-review: ## Publish the external theme-state review intake
	@test -n "$(UX1B_THEME_RUN_ID)" || (echo "UX1B_THEME_RUN_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py publish-review \
		--kind theme-states --theme-run-id "$(UX1B_THEME_RUN_ID)" --json

ui-ux1b-theme-states-close: ## Close the reviewed theme-state evidence
	@test -n "$(UX1B_THEME_RUN_ID)" || (echo "UX1B_THEME_RUN_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py close-theme-states \
		--theme-run-id "$(UX1B_THEME_RUN_ID)" --json

ui-ux1b-posttheme: ## Capture the mandatory Chromium UX-1B post-theme 27x3 matrix
	@test -n "$(UX1B_THEME_RUN_ID)" || (echo "UX1B_THEME_RUN_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py capture-posttheme \
		--theme-run-id "$(UX1B_THEME_RUN_ID)" --json

ui-ux1b-posttheme-reconcile: ## Reconcile a previously started post-theme capture
	@test -n "$(UX1B_THEME_RUN_ID)" || (echo "UX1B_THEME_RUN_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py reconcile-posttheme \
		--theme-run-id "$(UX1B_THEME_RUN_ID)" --json

ui-ux1b-posttheme-review: ## Publish the external post-theme review intake
	@test -n "$(UX1B_THEME_RUN_ID)" || (echo "UX1B_THEME_RUN_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py publish-review \
		--kind posttheme --theme-run-id "$(UX1B_THEME_RUN_ID)" --json

ui-ux1b-theme-close: ## Finalize the reviewed formal UX-1B theme
	@test -n "$(UX1B_THEME_RUN_ID)" || (echo "UX1B_THEME_RUN_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py finalize-theme \
		--theme-run-id "$(UX1B_THEME_RUN_ID)" --json

ui-ux1b-recovery-tests: ## Run the UX-1B recovery fixture, evidence, runner, and UI gates
	@tmp="$$(mktemp -d "$${TMPDIR:-/tmp}/qr-ux1b-awake-tests.XXXXXX")"; \
		trap 'rm -rf "$$tmp"' EXIT; \
		mkdir -p "$$tmp/scripts"; \
		cp scripts/ui_ux_awake_gate.py scripts/test_ui_ux_awake_gate.py "$$tmp/scripts/"; \
		PYTHONPATH="$$tmp" /usr/bin/sandbox-exec \
			-p '(version 1) (allow default) (deny file-read* (subpath "/private/tmp/qr-ux1b-s8"))' \
			$(PY) -B "$$tmp/scripts/test_ui_ux_awake_gate.py"
	$(PY) scripts/test_ui_ux_theme_handoff.py
	$(PY) scripts/test_ui_ux_isolation.py
	$(PY) scripts/test_ui_ux_evidence.py
	$(PY) scripts/test_ui_ux_selection_fixture.py
	$(PY) scripts/test_ui_accessible_selection_controls.py
	$(PY) scripts/test_ui_ux_fixtures.py
	$(PY) scripts/test_ui_ux_snapshot_matrix.py
	$(PY) scripts/test_ui_ux_theme.py
	$(PY) scripts/test_ui_ux_theme_matrix.py
	$(PY) scripts/test_ui_ux_contract.py
	$(PY) scripts/test_dashboard_navigation.py

ui-ux1b-recovery-precontrol: ## Capture and authenticate the pre-control page/control baselines
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	$(PY) scripts/ui_ux_snapshot_matrix.py \
		--profile ux1b-full-pages --phase precontrol --browser chromium \
		--out-dir .claude/ui_snapshots/ux1b/recovery/precontrol-pages-$(UX1B_RECOVERY_ID) \
		--no-prompt --json
	$(PY) scripts/ui_ux_snapshot_matrix.py \
		--profile ux1b-selection-controls --phase precontrol --browser chromium \
		--out-dir .claude/ui_snapshots/ux1b/recovery/precontrol-controls-$(UX1B_RECOVERY_ID) \
		--no-prompt --json
	$(PY) scripts/ui_ux_evidence.py verify-manifest \
		--manifest .claude/ui_snapshots/ux1b/recovery/precontrol-pages-$(UX1B_RECOVERY_ID)/manifest.json \
		--expected-mode ux1b-full-pages --expected-phase precontrol --expected-count 81 \
		--capture-stack-contract docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json
	$(PY) scripts/ui_ux_evidence.py verify-manifest \
		--manifest .claude/ui_snapshots/ux1b/recovery/precontrol-controls-$(UX1B_RECOVERY_ID)/manifest.json \
		--expected-mode ux1b-selection-controls --expected-phase precontrol --expected-count 36 \
		--capture-stack-contract docs/ui-ux/quant-radar-ui-v2-ux1b-capture-stack.json

ui-ux1b-recovery-postcontrol: ## Capture and authenticate post-control/canonical-pretheme evidence
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	@test -n "$(UX1B_HANDOFF_PREFLIGHT)" || (echo "UX1B_HANDOFF_PREFLIGHT is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py capture-task9 \
		--recovery-id "$(UX1B_RECOVERY_ID)" \
		--preflight "$(UX1B_HANDOFF_PREFLIGHT)" --json

ui-ux1b-recovery-reconcile: ## Reconcile the formal Task 9 capture lifecycle
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py reconcile-task9 \
		--recovery-id "$(UX1B_RECOVERY_ID)" --json

ui-ux1b-recovery-verify-migration: ## Verify authenticated page/control differences across migration
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CONTINUATION_ID)" || (echo "UX1B_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CORRECTION_ID)" || (echo "UX1B_CORRECTION_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py compare-control-migration \
		--capture-recovery-id "$(UX1B_RECOVERY_ID)" \
		--continuation-id "$(UX1B_CONTINUATION_ID)" \
		--correction-id "$(UX1B_CORRECTION_ID)" --json

ui-ux1b-control-migration-review-prepare: ## Prepare the control-migration review packet
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CONTINUATION_ID)" || (echo "UX1B_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CORRECTION_ID)" || (echo "UX1B_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_CORRECTION_ID)" || (echo "UX1B_LIFECYCLE_CORRECTION_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py prepare-review \
		--kind control-migration --recovery-id "$(UX1B_RECOVERY_ID)" \
		--continuation-id "$(UX1B_CONTINUATION_ID)" \
		--correction-id "$(UX1B_CORRECTION_ID)" \
		--lifecycle-correction-id "$(UX1B_LIFECYCLE_CORRECTION_ID)" --json

ui-ux1b-control-migration-review: ## Publish the external control-migration review intake
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CONTINUATION_ID)" || (echo "UX1B_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CORRECTION_ID)" || (echo "UX1B_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_CORRECTION_ID)" || (echo "UX1B_LIFECYCLE_CORRECTION_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py publish-review \
		--kind control-migration --recovery-id "$(UX1B_RECOVERY_ID)" \
		--continuation-id "$(UX1B_CONTINUATION_ID)" \
		--correction-id "$(UX1B_CORRECTION_ID)" \
		--lifecycle-correction-id "$(UX1B_LIFECYCLE_CORRECTION_ID)" --json

ui-ux1b-theme-handoff-prepare: ## Prepare the immutable formal handoff candidate
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CONTINUATION_ID)" || (echo "UX1B_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CORRECTION_ID)" || (echo "UX1B_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_CORRECTION_ID)" || (echo "UX1B_LIFECYCLE_CORRECTION_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py prepare-handoff \
		--recovery-id "$(UX1B_RECOVERY_ID)" \
		--continuation-id "$(UX1B_CONTINUATION_ID)" \
		--correction-id "$(UX1B_CORRECTION_ID)" \
		--lifecycle-correction-id "$(UX1B_LIFECYCLE_CORRECTION_ID)" --json

ui-ux1b-theme-handoff: ## Publish the immutable formal handoff root
	@test -n "$(UX1B_RECOVERY_ID)" || (echo "UX1B_RECOVERY_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CONTINUATION_ID)" || (echo "UX1B_CONTINUATION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_CORRECTION_ID)" || (echo "UX1B_CORRECTION_ID is required" >&2; exit 2)
	@test -n "$(UX1B_LIFECYCLE_CORRECTION_ID)" || (echo "UX1B_LIFECYCLE_CORRECTION_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py publish-handoff \
		--recovery-id "$(UX1B_RECOVERY_ID)" \
		--continuation-id "$(UX1B_CONTINUATION_ID)" \
		--correction-id "$(UX1B_CORRECTION_ID)" \
		--lifecycle-correction-id "$(UX1B_LIFECYCLE_CORRECTION_ID)" --json

ui-ux1b-theme-batch-init: ## Initialize a formal semantic-theme batch
	@test -n "$(UX1B_THEME_BATCH_ID)" || (echo "UX1B_THEME_BATCH_ID is required" >&2; exit 2)
	@test -n "$(UX1B_THEME_RUN_ID)" || (echo "UX1B_THEME_RUN_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py init-theme-batch \
		--batch-id "$(UX1B_THEME_BATCH_ID)" \
		--theme-run-id "$(UX1B_THEME_RUN_ID)" --json

ui-ux1b-theme-batch-seal: ## Seal and regression-test a formal semantic-theme batch
	@test -n "$(UX1B_THEME_BATCH_ID)" || (echo "UX1B_THEME_BATCH_ID is required" >&2; exit 2)
	@test -n "$(UX1B_THEME_RUN_ID)" || (echo "UX1B_THEME_RUN_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py seal-theme-batch \
		--batch-id "$(UX1B_THEME_BATCH_ID)" \
		--theme-run-id "$(UX1B_THEME_RUN_ID)" --json

ui-ux1b-theme-batch-review: ## Publish the external semantic-theme code review
	@test -n "$(UX1B_THEME_BATCH_ID)" || (echo "UX1B_THEME_BATCH_ID is required" >&2; exit 2)
	@test -n "$(UX1B_THEME_RUN_ID)" || (echo "UX1B_THEME_RUN_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py publish-review \
		--kind theme-batch --batch-id "$(UX1B_THEME_BATCH_ID)" \
		--theme-run-id "$(UX1B_THEME_RUN_ID)" --json

ui-ux1b-theme-batch-ready: ## Verify that a reviewed semantic-theme batch is ready
	@test -n "$(UX1B_THEME_BATCH_ID)" || (echo "UX1B_THEME_BATCH_ID is required" >&2; exit 2)
	@test -n "$(UX1B_THEME_RUN_ID)" || (echo "UX1B_THEME_RUN_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py verify-theme-batch-ready \
		--batch-id "$(UX1B_THEME_BATCH_ID)" \
		--theme-run-id "$(UX1B_THEME_RUN_ID)" --json

ui-ux1b-theme-batch-apply: ## Apply one accepted formal semantic-theme batch
	@test -n "$(UX1B_THEME_BATCH_ID)" || (echo "UX1B_THEME_BATCH_ID is required" >&2; exit 2)
	@test -n "$(UX1B_THEME_RUN_ID)" || (echo "UX1B_THEME_RUN_ID is required" >&2; exit 2)
	$(PY) -B scripts/ui_ux_theme_handoff.py apply-theme-batch \
		--batch-id "$(UX1B_THEME_BATCH_ID)" \
		--theme-run-id "$(UX1B_THEME_RUN_ID)" --json

ui-ux1b-theme-batch-reconcile: ## Reconcile an interrupted formal theme apply
	$(PY) -B scripts/ui_ux_theme_handoff.py reconcile-theme-batch --json

ui-ux1b-theme-batch-verify: ## Verify the immutable applied-batch receipt
	$(PY) -B scripts/ui_ux_theme_handoff.py verify-theme-batch-applied --json

candidate-preflight: ## Check Codex ChatGPT subscription auth for candidate scoring
	$(PY) scripts/llm_client.py --provider codex $(if $(strip $(CANDIDATE_MODEL)),--model $(CANDIDATE_MODEL),)

candidates-local: ## Refresh local candidates via hard filter + deterministic rank (no LLM)
	$(PY) scripts/01_hard_filter.py \
		--markets "$(MARKETS)" \
		--universe "$(UNIVERSE)" \
		--batch-size $(YF_BATCH_SIZE) \
		--min-data-coverage $(MIN_DATA_COVERAGE) \
		--min-avg-dollar-vol $(MIN_AVG_DOLLAR_VOL) \
		--min-market-cap $(MIN_MARKET_CAP) \
		--min-price $(MIN_PRICE) \
		--max-ret-5d $(MAX_RET_5D) \
		--max-ret-20d $(MAX_RET_20D) \
		--earnings-exclude-days $(EARNINGS_EXCLUDE_DAYS) \
		--status-file $(CANDIDATES_STATUS) \
		--output filtered_universe.json
	$(PY) scripts/03_rank_candidates.py \
		--input filtered_universe.json \
		--limit $(RANK_LIMIT) \
		--options-gate-limit $(OPTIONS_GATE_LIMIT) \
		--status-file $(CANDIDATES_STATUS) \
		--history-dir reports/candidate_rankings \
		--output ranked_candidates.json

candidates-rank-local: ## Rank existing filtered_universe.json deterministically (no LLM)
	$(PY) scripts/03_rank_candidates.py \
		--input filtered_universe.json \
		--start-status \
		--limit $(RANK_LIMIT) \
		--options-gate-limit $(OPTIONS_GATE_LIMIT) \
		--status-file $(CANDIDATES_STATUS) \
		--history-dir reports/candidate_rankings \
		--output ranked_candidates.json

candidates-score-local: candidate-preflight ## Optional LLM deep check via Codex SDK
		CODEX_SDK_TIMEOUT=$(CODEX_SDK_TIMEOUT) $(PY) scripts/02_llm_score.py \
			--input $(LLM_SCORE_INPUT) \
			--prompt system_prompts/01_surge_screener_prompt.md \
		--min-score $(MIN_SCORE) \
		--provider codex \
		$(if $(strip $(CANDIDATE_MODEL)),--model $(CANDIDATE_MODEL) --layer1-model $(CANDIDATE_MODEL),) \
		--limit $(CANDIDATE_LIMIT) \
		--candidate-retries $(CANDIDATE_RETRIES) \
		--deferred-retries $(CANDIDATE_DEFERRED_RETRIES) \
		--scoring-mode $(CANDIDATE_SCORING_MODE) \
		$(if $(filter 1 true yes,$(RESCORE_STALE_LLM)),--rescore-stale-language,) \
		--status-file $(CANDIDATES_STATUS) \
		--resume \
		--output scored_candidates.json

reversal-test: ## Run the reversal-signals unit tests (RR-1 gate)
	$(PY) scripts/test_reversal_signals.py
	$(PY) scripts/test_non_mkt_guards.py

cot: ## Generate the COT/ES weekly report via Codex ChatGPT subscription
	$(PY) scripts/cot_es.py --output-dir reports/cot

cot-data: ## COT/ES verified data ONLY — fetch + assemble, no LLM call (test)
	$(PY) scripts/cot_es.py --no-llm

reversal-scan: ## 反轉雷達: pre-screen beaten-down sp1500 → score → Telegram (TURNING+) + forward validation
	$(PY) scripts/reversal_radar_scan.py --universe beaten_down --notify
	$(PY) scripts/reversal_radar_forward.py || true

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*## "}{printf "  \033[36m%-9s\033[0m %s\n", $$1, $$2}'
	@printf "\n  Candidate refresh examples:\n"
	@printf "    make candidates-local RANK_LIMIT=50\n"
	@printf "    make candidates-local RANK_LIMIT=50 YF_BATCH_SIZE=10\n"
	@printf "    make candidates-rank-local RANK_LIMIT=50\n"
	@printf "    make candidates-rank-local RANK_LIMIT=30 OPTIONS_GATE_LIMIT=10\n"
	@printf "    make candidates-score-local CANDIDATE_LIMIT=3\n"
	@printf "\n  candidates-local overrides:\n"
	@printf "    %-18s %s\n" "RANK_LIMIT" "deterministic ranked pool size (default: $(RANK_LIMIT))"
	@printf "    %-18s %s\n" "OPTIONS_GATE_LIMIT" "top N to check with free options gate; 0 disables (default: $(OPTIONS_GATE_LIMIT))"
	@printf "    %-18s %s\n" "CANDIDATE_MODEL" "optional Codex model; blank uses account default"
	@printf "    %-18s %s\n" "CANDIDATE_LIMIT" "LLM deep-check tickers to score this run (default: $(CANDIDATE_LIMIT))"
	@printf "    %-18s %s\n" "CANDIDATE_RETRIES" "LLM attempts per ticker before defer (default: $(CANDIDATE_RETRIES))"
	@printf "    %-18s %s\n" "CANDIDATE_DEFERRED_RETRIES" "same-run retries for deferred timeouts (default: $(CANDIDATE_DEFERRED_RETRIES))"
	@printf "    %-18s %s\n" "CANDIDATE_SCORING_MODE" "fast=hard-filter-only, full=all enrichment (default: $(CANDIDATE_SCORING_MODE))"
	@printf "    %-18s %s\n" "RESCORE_STALE_LLM" "rescore stale-language LLM rows on resume; 1 enables (default: $(RESCORE_STALE_LLM))"
	@printf "    %-18s %s\n" "LLM_SCORE_INPUT" "LLM input JSON (default: $(LLM_SCORE_INPUT))"
	@printf "    %-18s %s\n" "CODEX_SDK_TIMEOUT" "seconds per Codex SDK call (default: $(CODEX_SDK_TIMEOUT))"
	@printf "    %-18s %s\n" "YF_BATCH_SIZE" "yfinance batch size; lower is slower but more stable (default: $(YF_BATCH_SIZE))"
	@printf "    %-18s %s\n" "MIN_DATA_COVERAGE" "abort floor for yfinance coverage (default: $(MIN_DATA_COVERAGE))"
	@printf "    %-18s %s\n" "MIN_AVG_DOLLAR_VOL" "hard-filter liquidity floor (default: $(MIN_AVG_DOLLAR_VOL))"
	@printf "    %-18s %s\n" "MIN_MARKET_CAP" "hard-filter market-cap floor (default: $(MIN_MARKET_CAP))"
	@printf "    %-18s %s\n" "MIN_PRICE" "hard-filter price floor (default: $(MIN_PRICE))"
	@printf "    %-18s %s\n" "MAX_RET_5D" "hard-filter 5d extension cap percent (default: $(MAX_RET_5D))"
	@printf "    %-18s %s\n" "MAX_RET_20D" "hard-filter 20d extension cap percent (default: $(MAX_RET_20D))"
	@printf "    %-18s %s\n" "EARNINGS_EXCLUDE_DAYS" "hard-filter earnings exclusion window (default: $(EARNINGS_EXCLUDE_DAYS))"
	@printf "    %-18s %s\n" "CANDIDATES_STATUS" "progress JSON path (default: $(CANDIDATES_STATUS))"
