#!/usr/bin/env python3
"""Static contract tests for the Streamlit navigation IA.

These tests intentionally avoid importing app.py because importing Streamlit page
objects can have UI side effects. The navigation is declarative in app.py, so a
small text-level contract is enough to catch accidental group drift.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "app.py").read_text(encoding="utf-8")
MAKEFILE = (ROOT / "Makefile").read_text(encoding="utf-8")
GITIGNORE = (ROOT / ".gitignore").read_text(encoding="utf-8")
SNAPSHOT = (ROOT / "scripts" / "ui_snapshot.py").read_text(encoding="utf-8")
SHARED = (ROOT / "ui" / "_shared.py").read_text(encoding="utf-8")
TODAY = (ROOT / "ui" / "today_decision.py").read_text(encoding="utf-8")
TRADE_STATE = (ROOT / "ui" / "trade_state.py").read_text(encoding="utf-8")
INDUSTRY_ROLES = (ROOT / "ui" / "industry_roles.py").read_text(encoding="utf-8")
US_COT = (ROOT / "ui" / "us_cot.py").read_text(encoding="utf-8")
STOCK_CHECKUP = (ROOT / "ui" / "stock_checkup.py").read_text(encoding="utf-8")
US_SCREENER = (ROOT / "ui" / "us_screener.py").read_text(encoding="utf-8")
COCKPIT = (ROOT / "ui" / "options_cockpit.py").read_text(encoding="utf-8")
US_OPTIONS = (ROOT / "ui" / "us_options.py").read_text(encoding="utf-8")
ANALYTICS_DB = (ROOT / "ui" / "analytics_db.py").read_text(encoding="utf-8")
RISK_GUARD_UI = (ROOT / "ui" / "risk_guard.py").read_text(encoding="utf-8")
SYS_SCHEDULES = (ROOT / "ui" / "sys_schedules.py").read_text(encoding="utf-8")
AUDIT = (ROOT / "docs" / "options_trader_function_audit.md").read_text(encoding="utf-8")
GUIDE = (ROOT / "docs" / "USER_GUIDE.md").read_text(encoding="utf-8")


def assert_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing: {needle}")


def assert_not_contains(text: str, needle: str) -> None:
    if needle in text:
        raise AssertionError(f"unexpected: {needle}")


def test_today_decision_page_is_default() -> None:
    assert_contains(APP, "today_decision")
    assert_contains(APP, 'title="今日決策"')
    assert_contains(APP, 'url_path="today-decision"')
    assert_contains(APP, "default=True")


def test_navigation_groups_match_trader_workflow() -> None:
    for group in ['"今日決策"', '"市場背景"', '"研究驗證"', '"資料維護"', '"幣圈"']:
        assert_contains(APP, group)

    # Core workflow pages should live in the first group in this order.
    today_group = APP.split('"今日決策": [', 1)[1].split("],", 1)[0]
    expected_order = [
        "today_decision.render",
        "trade_state.render",
        "us_screener.render",
        "options_flow.render",
        "stock_checkup.render",
        "options_cockpit.render",
        "radar.render",
        "ibkr_reconcile.render",
    ]
    positions = [today_group.index(item) for item in expected_order]
    if positions != sorted(positions):
        raise AssertionError(f"unexpected 今日決策 order: {positions}")

    # Research/detail pages should no longer interrupt the daily decision group.
    for detail_page in [
        "us_options.render",
        "analyst_views.render",
        "analytics_db.render",
        "institutions.render",
        "retro_analysis.render",
        "knowledge_graph.render",
    ]:
        if detail_page in today_group:
            raise AssertionError(f"{detail_page} should not be in 今日決策 group")

    research_group = APP.split('"研究驗證": [', 1)[1].split("],", 1)[0]
    assert_contains(research_group, "analytics_db.render")
    assert_contains(research_group, 'url_path="analytics-db"')


def test_trade_state_page_lives_in_daily_decision_group() -> None:
    assert_contains(APP, "trade_state")
    assert_contains(APP, 'title="交易狀態"')
    assert_contains(APP, 'url_path="trade-state"')
    today_group = APP.split('"今日決策": [', 1)[1].split("],", 1)[0]
    assert_contains(today_group, "trade_state.render")
    if today_group.index("trade_state.render") > today_group.index("us_screener.render"):
        raise AssertionError("交易狀態 should appear before 暴漲股篩選器")


def test_industry_roles_page_lives_in_data_maintenance_group() -> None:
    assert_contains(APP, "industry_roles")
    assert_contains(APP, 'title="產業鏈分類"')
    assert_contains(APP, 'url_path="industry-roles"')
    maintenance_group = APP.split('"資料維護": [', 1)[1].split("],", 1)[0]
    assert_contains(maintenance_group, "industry_roles.render")


def test_trade_state_exposes_industry_role_filter_and_tag() -> None:
    assert_contains(TRADE_STATE, '"產業鏈角色"')
    assert_contains(TRADE_STATE, "role = st.selectbox")
    assert_contains(TRADE_STATE, "_filter_rows(rows, signal, cycle, ce, theme, role)")
    assert_contains(TRADE_STATE, "industry_role_status")
    assert_contains(TRADE_STATE, "_role_color")


def test_trade_state_detail_and_story_are_trader_facing() -> None:
    assert_contains(TRADE_STATE, '"資料狀態"')
    assert_contains(TRADE_STATE, "_quality_color")
    assert_contains(TRADE_STATE, "def _render_detail_header")
    assert_contains(TRADE_STATE, "def _render_compact_facts")
    assert_contains(TRADE_STATE, "分類tag")
    assert_not_contains(TRADE_STATE, "top = st.columns([1, 2, 2, 2])")
    assert_contains(TRADE_STATE, "story_template = st.selectbox")
    assert_contains(TRADE_STATE, "_story_preview_df")
    assert_contains(TRADE_STATE, "預覽")
    assert_contains(TRADE_STATE, "複製文字")


def test_stock_checkup_search_refreshes_core_trade_data_and_gates_deep_options() -> None:
    assert_contains(STOCK_CHECKUP, "def _render_trade_data_status")
    assert_contains(STOCK_CHECKUP, "搜尋後已刷新")
    assert_contains(STOCK_CHECKUP, "作戰台核心")
    assert_contains(STOCK_CHECKUP, "ATM IV")
    assert_contains(STOCK_CHECKUP, "完整期權鏈明細")
    assert_contains(STOCK_CHECKUP, '_lazy("options", ticker, uo.render_for, label="載入完整期權鏈明細")')


def test_quote_fallback_is_adopted_on_price_surfaces() -> None:
    assert_contains(STOCK_CHECKUP, "quote_fallback")
    assert_contains(STOCK_CHECKUP, "_quote_source_chip")
    assert_contains(TODAY, "quote_fallback")
    assert_contains(TODAY, "價格來源")
    assert_contains(COCKPIT, "quote_source")
    assert_contains(COCKPIT, "_quote_source_chip")
    assert_contains(COCKPIT, "來源：")


def test_options_pages_split_decision_summary_from_full_chain_detail() -> None:
    assert_contains(COCKPIT, "期權鏈量分佈摘要")
    assert_contains(COCKPIT, "完整期權鏈明細")
    assert_contains(COCKPIT, "作戰台只顯示流動性與方向佐證")
    assert_contains(US_OPTIONS, "完整期權鏈明細")
    assert_contains(US_OPTIONS, "證據頁")
    assert_contains(US_OPTIONS, "最活躍 call 履約價")


def test_us_screener_reuses_embeddable_analyst_renderer() -> None:
    assert_contains(US_SCREENER, "analyst_views.render_for(ticker)")
    assert_not_contains(US_SCREENER, "_shared.load_analyst_views(ticker)")
    assert_not_contains(US_SCREENER, "data.get(\"recent_actions\")")


def test_industry_roles_review_page_surfaces_missing_and_status_views() -> None:
    assert_contains(INDUSTRY_ROLES, "def _missing_df")
    assert_contains(INDUSTRY_ROLES, "classification_pending")
    assert_contains(INDUSTRY_ROLES, "缺分類")
    assert_contains(INDUSTRY_ROLES, "搜尋")
    assert_contains(INDUSTRY_ROLES, "全部建議")
    assert_contains(INDUSTRY_ROLES, "狀態")


def test_snapshot_default_page_matches_navigation_default() -> None:
    assert_contains(SNAPSHOT, 'DEFAULT_PAGE = "today-decision"')


def test_analytics_db_renders_automated_checks() -> None:
    assert_contains(ANALYTICS_DB, "def _checks_path")
    assert_contains(ANALYTICS_DB, "analytics_checks")
    assert_contains(ANALYTICS_DB, "latest.json")
    assert_contains(ANALYTICS_DB, "def _render_checks")
    assert_contains(ANALYTICS_DB, "def _health_summary")
    assert_contains(ANALYTICS_DB, "今日 Analytics 狀態")
    assert_contains(ANALYTICS_DB, "today_signal_readiness")
    assert_contains(ANALYTICS_DB, "今日訊號發布狀態")
    assert_contains(ANALYTICS_DB, "資料健康摘要")
    assert_contains(ANALYTICS_DB, "可發布，需檢查")
    assert_contains(ANALYTICS_DB, "核心候選排序")
    assert_contains(ANALYTICS_DB, "資料可用")
    assert_contains(ANALYTICS_DB, "阻擋")
    assert_contains(ANALYTICS_DB, "需檢查")
    assert_contains(ANALYTICS_DB, "觀察候選")
    assert_contains(ANALYTICS_DB, "連線與原始檢查")
    assert_contains(ANALYTICS_DB, "def _human_reason")
    assert_contains(ANALYTICS_DB, "績效樣本")
    assert_contains(ANALYTICS_DB, "期權流重複")
    assert_contains(ANALYTICS_DB, '"candidate_scores": "scan_date"')
    assert_contains(ANALYTICS_DB, '"candidate_rankings": "scan_date"')
    assert_contains(ANALYTICS_DB, '"daily_reports": "report_date"')
    assert_contains(ANALYTICS_DB, '"portfolio_positions": "as_of_date"')
    assert_contains(ANALYTICS_DB, '"risk_guard_rows": "as_of_date"')
    assert_contains(ANALYTICS_DB, '"run_status_history": "started_at"')
    assert_contains(ANALYTICS_DB, '"sector_rotation_snapshots": "as_of_date"')
    assert_contains(ANALYTICS_DB, '"signal_outcomes": "as_of_date"')
    assert_contains(ANALYTICS_DB, '"theme_flow_snapshots": "as_of_date"')
    assert_contains(ANALYTICS_DB, '"validation_summaries": "as_of_date"')
    assert_contains(ANALYTICS_DB, '"watchlist_sources": "scan_date"')
    assert_contains(ANALYTICS_DB, "風險雷達重複")
    assert_contains(ANALYTICS_DB, "持倉快照")
    assert_contains(ANALYTICS_DB, "板塊輪動")
    assert_contains(ANALYTICS_DB, "主題資金流")
    assert_contains(ANALYTICS_DB, "驗證摘要")
    assert_contains(ANALYTICS_DB, "每日報告")
    assert_contains(ANALYTICS_DB, "自選清單")


def test_data_health_entry_and_refresh_center_are_discoverable() -> None:
    assert_contains(APP, 'title="資料健康 / Analytics DB"')
    assert_contains(APP, 'url_path="analytics-db"')
    assert_contains(TODAY, "def _render_data_health_entry")
    assert_contains(TODAY, 'switch_page("analytics-db")')
    assert_contains(TODAY, "查看資料健康")
    assert_contains(TODAY, "完整刷新只處理今日決策需要的資料")
    assert_contains(ANALYTICS_DB, 'st.header("資料健康 / Analytics DB")')
    assert_contains(ANALYTICS_DB, "def _render_refresh_center")
    assert_contains(ANALYTICS_DB, "完整刷新核心資料源（約 10-25 分鐘）")
    assert_contains(ANALYTICS_DB, "只重建 Analytics DB + 檢查")
    assert_contains(ANALYTICS_DB, "最近一次資料刷新")
    assert_contains(ANALYTICS_DB, "stage.progress_pct")
    assert_contains(ANALYTICS_DB, "data-health-refresh.json")
    assert_contains(ANALYTICS_DB, "約 250 檔")
    assert_contains(ANALYTICS_DB, "data_source_refresh")
    assert_contains(ANALYTICS_DB, "universe / daily bars / money flow")
    assert_contains(ANALYTICS_DB, "重建 Analytics DB + 檢查")
    assert_contains(ANALYTICS_DB, "刷新基本面")
    assert_contains(ANALYTICS_DB, "刷新主題資金流")
    assert_contains(ANALYTICS_DB, "刷新板塊輪動快照")
    assert_contains(ANALYTICS_DB, "IBKR 持倉需在本機對帳")
    assert_contains(ANALYTICS_DB, "fundamental_metrics_store")
    assert_contains(ANALYTICS_DB, "低頻研究資料")
    failed_read_block = ANALYTICS_DB.split("Analytics DB 讀取失敗", 1)[1].split("return", 1)[0]
    assert_contains(failed_read_block, "_render_refresh_center(root)")


def test_monthly_reflection_markdown_is_readable_from_schedules_page() -> None:
    assert_contains(APP, 'title="排程與結果"')
    assert_contains(SYS_SCHEDULES, "def _latest_reflection_detail")
    assert_contains(SYS_SCHEDULES, "def _extract_llm_reflection_json")
    assert_contains(SYS_SCHEDULES, 'st.expander("查看完整反思"')
    assert_contains(SYS_SCHEDULES, "人讀摘要")
    assert_contains(SYS_SCHEDULES, "資料缺口")
    assert_contains(SYS_SCHEDULES, "建議行動")
    assert_contains(SYS_SCHEDULES, "原始 LLM JSON")
    assert_contains(SYS_SCHEDULES, "完整 Markdown 原文")
    assert_contains(SYS_SCHEDULES, "st.download_button")
    assert_contains(SYS_SCHEDULES, 'mime="text/markdown"')
    assert_contains(SYS_SCHEDULES, "latest.name")


def test_risk_guard_scan_persists_analytics_snapshot() -> None:
    assert_contains(RISK_GUARD_UI, "def _compute_risk")
    assert_contains(RISK_GUARD_UI, "copy.deepcopy")
    assert_contains(RISK_GUARD_UI, "write_report")
    assert_contains(RISK_GUARD_UI, "refresh_analytics_for_report")
    assert_contains(RISK_GUARD_UI, "persistence_warning")


def test_candidate_tables_use_shared_action_trio() -> None:
    assert_contains(SHARED, "def ticker_action_buttons")
    for rel in [
        "ui/today_decision.py",
        "ui/us_screener.py",
        "ui/options_flow.py",
        "ui/sector_rotation.py",
    ]:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert_contains(text, "_shared.ticker_action_buttons")


def test_today_decision_renders_trust_boundary() -> None:
    assert_contains(TODAY, "def _render_trust_boundary")
    assert_contains(TODAY, "validation_summary.json")
    assert_contains(TODAY, "min_resolved_for_verdict")
    assert_contains(TODAY, "min_resolved_across_tiers")
    assert_contains(TODAY, "背景-only")
    assert_contains(TODAY, "觀察-only")
    assert_contains(TODAY, "risk-control")


def test_today_decision_renders_local_refresh_progress() -> None:
    assert_contains(TODAY, '@st.fragment(run_every="8s")')
    assert_contains(TODAY, "def _render_local_refresh_status")
    assert_contains(TODAY, "reports/run_status/candidates-local.json")
    assert_contains(TODAY, "st.progress")
    assert_contains(TODAY, "stage.progress_pct")
    assert_contains(TODAY, "rank_candidates")
    assert_contains(TODAY, "ranked_candidates.json")
    assert_contains(TODAY, "updated_at")
    assert_not_contains(TODAY, "components.html")
    assert_not_contains(TODAY, "window.parent.location.reload")
    assert_not_contains(TODAY, "setTimeout")
    assert_contains(TODAY, "可能已中斷")


def test_today_decision_reads_deterministic_ranked_candidates() -> None:
    assert_contains(TODAY, "def _ranked_candidates")
    assert_contains(TODAY, "ranked_candidates.json")
    assert_contains(TODAY, "rank_score")
    assert_contains(TODAY, "options_tradability")


def test_today_decision_surfaces_trade_state_entry_point() -> None:
    assert_contains(TODAY, "def _render_trade_state_summary")
    assert_contains(TODAY, "build_trade_state_rows")
    assert_contains(TODAY, 'switch_page("trade-state")')
    assert_contains(TODAY, "交易狀態")
    assert_contains(TODAY, "Cycle1")
    assert_contains(TODAY, "CE/Proxy 偏多")


def test_today_decision_renders_candidate_pipeline_controls() -> None:
    for needle in [
        "def _render_candidate_pipeline_controls",
        "CandidateRunParams",
        "launch_background",
        "st.number_input",
        "排名 Top N",
        "期權檢查數",
        "LLM 深檢數",
        "RANK_LIMIT",
        "OPTIONS_GATE_LIMIT",
        "MIN_AVG_DOLLAR_VOL",
        "MIN_MARKET_CAP",
        "MAX_RET_5D",
        "MAX_RET_20D",
        "完整刷新",
        "只重排（進階）",
        "少量 LLM",
        "candidates-local-history.jsonl",
        "def _candidate_run_history",
        "篩選紀錄",
    ]:
        assert_contains(TODAY, needle)


def test_today_decision_history_falls_back_to_rank_source_candidates() -> None:
    assert_contains(TODAY, 'metrics.get("passed_hard_filters", metrics.get("rank_source_candidates", "-"))')


def test_today_decision_history_uses_plain_language_column_names() -> None:
    for needle in [
        "def _status_zh",
        '"通過基礎篩選"',
        '"排名產出"',
        '"Top N 上限"',
        '"期權檢查數"',
        '"狀態": _status_zh(row.get("status"))',
    ]:
        assert_contains(TODAY, needle)


def test_today_decision_history_shows_flow_instead_of_repeated_output_path() -> None:
    for needle in [
        "def _history_flow",
        '"流程": _history_flow(row)',
        "完整刷新 + 排名",
        "只重排",
        "少量 LLM",
    ]:
        assert_contains(TODAY, needle)
    assert_not_contains(TODAY, '"output": ranked.get("path", "-")')


def test_today_decision_launch_tracking_surfaces_status_and_log() -> None:
    for needle in [
        "def _tail_text",
        "def _render_launch_tracking",
        "candidate_pipeline_last_launch",
        "最近啟動",
        "追蹤細節",
        "_RUN_STATUS_PATH",
        "log_path",
        "_tail_text(log_path)",
    ]:
        assert_contains(TODAY, needle)


def test_today_decision_surfaces_actual_ranked_and_llm_candidates() -> None:
    for needle in [
        "def _ranked_result_df(limit: int = 50)",
        "def _llm_result_df",
        "def _llm_detail_rows",
        "def _render_selected_llm_detail",
        "最新排名結果",
        "LLM 深檢結果",
        '"期權狀態"',
        '"rank_score"',
        '"LLM 分數"',
        "主要理由",
        "阻擋因素",
        "選擇標的查看完整詳情",
        "舊結果可能仍是英文",
        "def _has_english_llm_detail",
        "少量 LLM 會優先重算英文舊列",
        "按「少量 LLM」會把這些英文舊列排入重算",
        "同批摘要",
        "LLM 依據 7 維度",
        "_render_candidate_results()",
    ]:
        assert_contains(TODAY, needle)
    for cramped_column in [
        '"主要理由": str(signals[0])',
        '"阻擋因素": str(risks[0])',
        '"下一步": row.get("suggested_entry_zone")',
        "逐檔詳情",
        "def _render_llm_detail_cards",
        "def _zh_text",
        "點選上方任一列",
        "on_select=\"rerun\"",
        "selection_mode=\"single-row\"",
        "_selected_row_index",
        '"摘要"',
        '"風險摘要"',
    ]:
        assert_not_contains(TODAY, cramped_column)


def test_today_decision_status_panel_uses_user_facing_language() -> None:
    for needle in [
        "status_label = _status_zh(status)",
        "def _scored_progress_label",
        "def _status_message_zh",
        "抓取行情",
        "排名完成",
        "期權檢查",
        "LLM 深檢累積",
        "尚有",
        "更新時間",
    ]:
        assert_contains(TODAY, needle)
    for raw_ui in [
        "status.upper()",
        "updated_at {updated_at}",
        "ranked {metrics.get",
        "scored {metrics",
        "st.caption(message)",
    ]:
        assert_not_contains(TODAY, raw_ui)


def test_options_cockpit_contract_panel_is_tradeability_first() -> None:
    for needle in [
        "def _contract_tradeability",
        "def _render_tradeability_summary",
        "def _strategy_greeks",
        "def _chain_microstructure_summary",
        "def _render_microstructure_summary",
        "Greeks 面板",
        "P&L Payoff",
        "鏈微結構摘要",
        "Max Pain",
        "Put/Call OI",
        "_render_microstructure_summary(d)",
        "Delta 曝險",
        "Gamma 加速",
        "Theta 耗損",
        "Vega / +1 IV",
        "交易可行性",
        "候選合約",
        "不可直接下單",
        "資料可信度",
        "損益情境",
        "目標價",
        "停損價",
    ]:
        assert_contains(COCKPIT, needle)
    assert_not_contains(COCKPIT, "##### 建議合約 —")


def test_cot_report_generation_gates_on_claude_auth() -> None:
    for needle in [
        "from scripts import claude_auth_flow",
        "claude_auth_flow.refresh_status()",
        "claude_auth_flow.start_login()",
        "cot_claude_auth_login",
        "Claude 登入",
        "前往 Claude 登入",
        "完成登入後，回到這頁再按一次",
        "_login_url_from_text",
        "submit_login_code",
        "貼上 Claude 顯示的驗證碼",
        "st.text_input",
        "form_submit_button",
        "_ensure_claude_auth_for_generate(render=",
    ]:
        assert_contains(US_COT, needle)
    for technical in [
        "docker exec",
        "server shell",
        "claude-auth.log",
        "持久化 volume",
        "st.code(",
    ]:
        assert_not_contains(US_COT, technical)


def test_local_run_status_is_gitignored() -> None:
    assert_contains(GITIGNORE, "reports/run_status/")
    assert_contains(GITIGNORE, "reports/candidate_rankings/")
    assert_contains(GITIGNORE, "reports/risk_guard/")
    assert_contains(GITIGNORE, "reports/theme_flow_snapshots/")


def test_local_candidate_generation_defaults_to_deterministic_rank() -> None:
    for needle in [
        "RANK_LIMIT ?= 50",
        "OPTIONS_GATE_LIMIT ?= 0",
        "CANDIDATES_STATUS ?= reports/run_status/candidates-local.json",
        "candidates-local:",
        "candidates-rank-local:",
        "scripts/03_rank_candidates.py",
        "--start-status",
        "--limit $(RANK_LIMIT)",
        "--options-gate-limit $(OPTIONS_GATE_LIMIT)",
        "--status-file $(CANDIDATES_STATUS)",
    ]:
        assert_contains(MAKEFILE, needle)
    if "candidates-local: candidate-preflight" in MAKEFILE:
        raise AssertionError("candidates-local should not require Claude preflight")
    for text in (AUDIT, GUIDE):
        assert_contains(text, "ranked_candidates.json")
        assert_contains(text, "candidates-rank-local")


def test_optional_llm_candidate_scoring_uses_subscription_model() -> None:
    for needle in [
        "CANDIDATE_MODEL ?= claude-sonnet-4-6",
        "CANDIDATE_RETRIES ?= 1",
        "CANDIDATE_DEFERRED_RETRIES ?= 0",
        "CANDIDATE_SCORING_MODE ?= fast",
        "RESCORE_STALE_LLM ?= 1",
        "CLAUDE_AGENT_TIMEOUT ?= 180",
        "candidate-preflight:",
        "candidates-score-local:",
        "CLAUDE_AGENT_TIMEOUT=$(CLAUDE_AGENT_TIMEOUT) $(PY) scripts/02_llm_score.py",
        "--provider claude_agent",
        "--layer1-model $(CANDIDATE_MODEL)",
        "--resume",
        "--limit $(CANDIDATE_LIMIT)",
        "--candidate-retries $(CANDIDATE_RETRIES)",
        "--deferred-retries $(CANDIDATE_DEFERRED_RETRIES)",
        "--scoring-mode $(CANDIDATE_SCORING_MODE)",
        "--rescore-stale-language",
        "--status-file $(CANDIDATES_STATUS)",
    ]:
        assert_contains(MAKEFILE, needle)
    for text in (AUDIT, GUIDE):
        assert_contains(text, "candidates-score-local")
        assert_contains(text, "claude_agent")
        assert_contains(text, "layer1-model")


def test_make_help_documents_candidate_overrides() -> None:
    assert_contains(MAKEFILE, "scripts/test_trade_state.py")
    for needle in [
        "Candidate refresh examples",
        "make candidates-local RANK_LIMIT=50",
        "make candidates-rank-local RANK_LIMIT=50",
        "make candidates-score-local CANDIDATE_LIMIT=3",
        "RANK_LIMIT",
        "OPTIONS_GATE_LIMIT",
        "CANDIDATE_LIMIT",
        "CANDIDATE_RETRIES",
        "CANDIDATE_DEFERRED_RETRIES",
        "CANDIDATE_SCORING_MODE",
        "RESCORE_STALE_LLM",
        "CLAUDE_AGENT_TIMEOUT",
        "YF_BATCH_SIZE",
        "MIN_DATA_COVERAGE",
        "CANDIDATES_STATUS",
        "reports/run_status/candidates-local.json",
    ]:
        assert_contains(MAKEFILE, needle)


def test_llm_status_outputs_ranked_input_not_filtered_universe() -> None:
    llm_score = (ROOT / "scripts" / "02_llm_score.py").read_text(encoding="utf-8")
    assert_contains(llm_score, '"ranked_candidates": {"path": args.input')
    assert_not_contains(llm_score, '"filtered_universe": {"path": args.input')


def test_forward_sample_maturity_is_documented() -> None:
    for needle in [
        "Forward sample 成熟規則",
        "MIN_RESOLVED=100",
        "20/40/60",
        "非重疊",
        "不能手動補成熟",
    ]:
        assert_contains(AUDIT, needle)


def main() -> None:
    tests = [
        test_today_decision_page_is_default,
        test_navigation_groups_match_trader_workflow,
        test_trade_state_page_lives_in_daily_decision_group,
        test_industry_roles_page_lives_in_data_maintenance_group,
        test_trade_state_exposes_industry_role_filter_and_tag,
        test_trade_state_detail_and_story_are_trader_facing,
        test_stock_checkup_search_refreshes_core_trade_data_and_gates_deep_options,
        test_quote_fallback_is_adopted_on_price_surfaces,
        test_options_pages_split_decision_summary_from_full_chain_detail,
        test_us_screener_reuses_embeddable_analyst_renderer,
        test_industry_roles_review_page_surfaces_missing_and_status_views,
        test_snapshot_default_page_matches_navigation_default,
        test_analytics_db_renders_automated_checks,
        test_data_health_entry_and_refresh_center_are_discoverable,
        test_monthly_reflection_markdown_is_readable_from_schedules_page,
        test_candidate_tables_use_shared_action_trio,
        test_today_decision_renders_trust_boundary,
        test_today_decision_renders_local_refresh_progress,
        test_today_decision_reads_deterministic_ranked_candidates,
        test_today_decision_surfaces_trade_state_entry_point,
        test_today_decision_renders_candidate_pipeline_controls,
        test_today_decision_history_falls_back_to_rank_source_candidates,
        test_today_decision_history_uses_plain_language_column_names,
        test_today_decision_history_shows_flow_instead_of_repeated_output_path,
        test_today_decision_launch_tracking_surfaces_status_and_log,
        test_today_decision_surfaces_actual_ranked_and_llm_candidates,
        test_today_decision_status_panel_uses_user_facing_language,
        test_options_cockpit_contract_panel_is_tradeability_first,
        test_cot_report_generation_gates_on_claude_auth,
        test_local_run_status_is_gitignored,
        test_local_candidate_generation_defaults_to_deterministic_rank,
        test_optional_llm_candidate_scoring_uses_subscription_model,
        test_make_help_documents_candidate_overrides,
        test_llm_status_outputs_ranked_input_not_filtered_universe,
        test_forward_sample_maturity_is_documented,
    ]
    for test in tests:
        test()
        print(f"  PASS {test.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
