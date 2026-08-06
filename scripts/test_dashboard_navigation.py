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
DESIGN_PATH = ROOT / "ui" / "_design.py"
COMPONENTS_PATH = ROOT / "ui" / "_components.py"
TODAY = (ROOT / "ui" / "today_decision.py").read_text(encoding="utf-8")
CANDIDATE_CONTROLS_PATH = ROOT / "ui" / "_candidate_controls.py"
CANDIDATE_CONTROLS = (
    CANDIDATE_CONTROLS_PATH.read_text(encoding="utf-8")
    if CANDIDATE_CONTROLS_PATH.exists()
    else ""
)
TRADE_STATE = (ROOT / "ui" / "trade_state.py").read_text(encoding="utf-8")
INDUSTRY_ROLES = (ROOT / "ui" / "industry_roles.py").read_text(encoding="utf-8")
US_COT = (ROOT / "ui" / "us_cot.py").read_text(encoding="utf-8")
STOCK_CHECKUP = (ROOT / "ui" / "stock_checkup.py").read_text(encoding="utf-8")
US_SCREENER = (ROOT / "ui" / "us_screener.py").read_text(encoding="utf-8")
ANALYST_VIEWS = (ROOT / "ui" / "analyst_views.py").read_text(encoding="utf-8")
SECTOR_ROTATION = (ROOT / "ui" / "sector_rotation.py").read_text(encoding="utf-8")
COCKPIT = (ROOT / "ui" / "options_cockpit.py").read_text(encoding="utf-8")
RETRO_ANALYSIS = (ROOT / "ui" / "retro_analysis.py").read_text(encoding="utf-8")
CONTINUATION_VALIDATION = (ROOT / "ui" / "continuation_validation.py").read_text(encoding="utf-8")
PLAYBOOK_VALIDATION = (ROOT / "ui" / "playbook_validation.py").read_text(encoding="utf-8")
US_OPTIONS = (ROOT / "ui" / "us_options.py").read_text(encoding="utf-8")
OPTIONS_FLOW = (ROOT / "ui" / "options_flow.py").read_text(encoding="utf-8")
CRYPTO_UNIVERSE = (ROOT / "ui" / "crypto_universe.py").read_text(encoding="utf-8")
MARKET_THESIS = (ROOT / "ui" / "market_thesis.py").read_text(encoding="utf-8")
RADAR = (ROOT / "ui" / "radar.py").read_text(encoding="utf-8")
OVERSOLD_REVERSAL = (ROOT / "ui" / "oversold_reversal_lane.py").read_text(encoding="utf-8")
X_SENTIMENT = (ROOT / "ui" / "x_sentiment.py").read_text(encoding="utf-8")
THEME_FLOW = (ROOT / "ui" / "theme_flow.py").read_text(encoding="utf-8")
AGENT_REACH_AUTH = (ROOT / "scripts" / "agent_reach_auth.py").read_text(encoding="utf-8") \
    if (ROOT / "scripts" / "agent_reach_auth.py").exists() else ""
INFLUENCERS = (ROOT / "ui" / "influencers.py").read_text(encoding="utf-8")
ANALYTICS_DB = (ROOT / "ui" / "analytics_db.py").read_text(encoding="utf-8")
RISK_GUARD_UI = (ROOT / "ui" / "risk_guard.py").read_text(encoding="utf-8")
SYS_SCHEDULES = (ROOT / "ui" / "sys_schedules.py").read_text(encoding="utf-8")
SYS_AI_UPDATES = (ROOT / "ui" / "sys_ai_updates.py").read_text(encoding="utf-8")
INSTITUTION_PORTFOLIO = (ROOT / "ui" / "institution_portfolio.py").read_text(encoding="utf-8")
INSTITUTIONAL_HOLDINGS = (ROOT / "ui" / "institutional_holdings.py").read_text(encoding="utf-8")
READ_API = (ROOT / "ui" / "_read_api.py").read_text(encoding="utf-8")
DOCKER_COMPOSE = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
AUDIT = (ROOT / "docs" / "options_trader_function_audit.md").read_text(encoding="utf-8")
GUIDE = (ROOT / "docs" / "USER_GUIDE.md").read_text(encoding="utf-8")
API_INVENTORY = (
    ROOT / "docs" / "api" / "fastapi-endpoint-artifact-inventory.md"
).read_text(encoding="utf-8")
AI_CHAT_PATH = ROOT / "ui" / "ai_chat.py"
AI_CHAT = AI_CHAT_PATH.read_text(encoding="utf-8") if AI_CHAT_PATH.exists() else ""


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


def test_trade_state_cycle_filter_exposes_six_course_cycles() -> None:
    assert_contains(TRADE_STATE, '_CYCLE_FILTER_OPTIONS = ["全部", "Cycle1", "Cycle2", "Cycle3", "Cycle4", "Cycle5", "Cycle6"]')
    assert_contains(TRADE_STATE, "_cycle_matches_filter")
    assert_not_contains(TRADE_STATE, 'sorted({r.get("cycle") for r in rows if r.get("cycle")})')


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


def test_ux1a_shared_foundations_are_pure_and_native() -> None:
    if not DESIGN_PATH.exists() or not COMPONENTS_PATH.exists():
        raise AssertionError("UX-1A shared foundation modules are missing")
    design = DESIGN_PATH.read_text(encoding="utf-8")
    components = COMPONENTS_PATH.read_text(encoding="utf-8")
    assert_not_contains(design, "streamlit")
    assert_not_contains(design, "primaryColor")
    assert_not_contains(components, "unsafe_allow_html")
    for native in ("st.info", "st.warning", "st.error", "st.success", "st.caption"):
        assert_contains(components, native)
    assert_contains(SHARED, "html.escape(str(text), quote=True)")
    assert_contains(SHARED, "resolve_chip_color(color)")


def test_global_ai_chat_assistant_is_wired_into_app_shell() -> None:
    assert_contains(APP, "ai_chat")
    assert_contains(APP, "ai_chat.render()")
    assert_contains(AI_CHAT, "ai_chat_float")
    assert_contains(AI_CHAT, "保存此對話")
    assert_contains(AI_CHAT, "深度研究")
    assert_contains(AI_CHAT, "設定與歷史")
    assert_contains(AI_CHAT, "確認刪除")
    assert_contains(AI_CHAT, "確認清空")
    assert_contains(AI_CHAT, "safe-area-inset-bottom")
    assert_contains(AI_CHAT, "ai_chat_panel")
    assert_contains(AI_CHAT, "_OPEN")
    assert_not_contains(AI_CHAT, "st.dialog")


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
    assert_contains(ANALYTICS_DB, '"--include-supplemental"')
    assert_contains(ANALYTICS_DB, "include_supplemental=True")
    assert_contains(ANALYTICS_DB, "其他自動資料")
    failed_read_block = ANALYTICS_DB.split("Analytics DB 讀取失敗", 1)[1].split("return", 1)[0]
    assert_contains(failed_read_block, "_render_refresh_center(root)")


def test_scheduled_market_snapshots_render_without_manual_refresh() -> None:
    assert_not_contains(SHARED, "def load_sector_flow(")
    assert_contains(READ_API, "def load_sector_rotation(")
    assert_contains(SECTOR_ROTATION, "_board_state()")
    assert_contains(RISK_GUARD_UI, "def _load_scheduled_risk_snapshot")
    assert_contains(RISK_GUARD_UI, 'st.session_state["rg_source"] = "Watchlist"')
    assert_contains(RISK_GUARD_UI, "session_data or scheduled_data")
    assert_contains(SYS_SCHEDULES, "def _latest_data_health_result")
    assert_contains(SYS_SCHEDULES, "def _latest_theme_flow_result")


def test_validation_lanes_live_inside_retro_analysis_hub() -> None:
    assert_contains(APP, "retro_analysis.render")
    assert_contains(APP, 'title="復盤分析"')
    assert_not_contains(APP, 'title="Playbook 驗證"')
    assert_not_contains(APP, 'url_path="playbook-validation"')
    assert_contains(RETRO_ANALYSIS, "playbook_validation")
    assert_contains(RETRO_ANALYSIS, "continuation_validation")
    assert_contains(RETRO_ANALYSIS, "暴漲事件復盤")
    assert_contains(RETRO_ANALYSIS, "續漲強者")
    assert_contains(RETRO_ANALYSIS, "Playbook 驗證")


def test_continuation_lane_distinguishes_blocked_from_accumulating() -> None:
    assert_contains(CONTINUATION_VALIDATION, 'data.status == "blocked"')
    assert_contains(CONTINUATION_VALIDATION, "load_continuation_validation")
    assert_not_contains(CONTINUATION_VALIDATION, "continuation_strength.json")
    assert_contains(CONTINUATION_VALIDATION, "resolved")
    assert_contains(CONTINUATION_VALIDATION, "min_resolved")
    assert_contains(CONTINUATION_VALIDATION, "續漲驗證暫時封鎖")


def test_options_cockpit_links_to_validation_hub_not_new_sidebar_page() -> None:
    assert_contains(COCKPIT, "查看 Playbook 驗證")
    assert_contains(COCKPIT, "validation_lane")
    assert_contains(COCKPIT, 'switch_page("retro-analysis")')
    assert_not_contains(APP, 'url_path="playbook-validation"')


def test_monthly_reflection_has_a_safe_structured_summary() -> None:
    assert_contains(APP, 'title="排程與結果"')
    assert_contains(SYS_SCHEDULES, "def _latest_reflection_detail")
    assert_contains(SYS_SCHEDULES, "def _extract_llm_reflection_json")
    assert_contains(SYS_SCHEDULES, 'st.expander("查看完整反思"')
    assert_contains(SYS_SCHEDULES, "def _render_reflection_summary")
    assert_contains(SYS_SCHEDULES, "def _safe_reflection_text")
    assert_contains(SYS_SCHEDULES, "資料缺口")
    assert_contains(SYS_SCHEDULES, "建議行動")
    assert_not_contains(SYS_SCHEDULES, "原始 LLM JSON")
    assert_not_contains(SYS_SCHEDULES, "完整 Markdown 原文")
    assert_not_contains(SYS_SCHEDULES, "st.json(")
    assert_not_contains(SYS_SCHEDULES, "st.download_button")


def test_schedules_registry_is_api_only_with_local_results_preserved() -> None:
    assert_contains(
        READ_API,
        'http://127.0.0.1:8000/api/v1/system/schedules',
    )
    assert_contains(READ_API, '"trust_env": False')
    assert_contains(READ_API, '"follow_redirects": False')
    assert_contains(READ_API, "asyncio.wait_for")
    assert_contains(SYS_SCHEDULES, "_read_api.load_schedules()")
    assert_not_contains(SYS_SCHEDULES, "read_artifact")
    assert_not_contains(SYS_SCHEDULES, "local_fallback")
    assert_not_contains(SYS_SCHEDULES, "all_unavailable")
    assert_contains(SYS_SCHEDULES, '"api_failure"')
    assert_contains(SYS_SCHEDULES, "_RESULT_FETCHERS")
    assert_contains(SYS_SCHEDULES, "_latest_reflection_detail")
    assert_contains(SYS_SCHEDULES, 'source_id="system.schedules"')
    assert_contains(SYS_SCHEDULES, "_components.render_state_banner(state)")
    assert_contains(GUIDE, "`make api`")
    assert_contains(GUIDE, "API_PORT=")
    assert_contains(GUIDE, "Docker Compose")
    assert_contains(GUIDE, "Schedules")
    assert_contains(GUIDE, "API-only")
    assert_contains(DOCKER_COMPOSE, "api.main:app")
    assert_contains(DOCKER_COMPOSE, 'network_mode: "service:api"')


def test_ai_updates_feed_is_api_first_with_preserved_ui_behavior() -> None:
    assert_contains(
        READ_API,
        'http://127.0.0.1:8000/api/v1/system/ai-updates',
    )
    assert_contains(SYS_AI_UPDATES, "_read_api.load_ai_updates()")
    assert_not_contains(SYS_AI_UPDATES, "read_artifact")
    assert_not_contains(SYS_AI_UPDATES, "local_fallback")
    assert_contains(SYS_AI_UPDATES, '"api_failure"')
    assert_not_contains(SYS_AI_UPDATES, "_shared.load_json")
    assert_contains(SYS_AI_UPDATES, 'st.multiselect("依標籤篩選"')
    assert_contains(SYS_AI_UPDATES, "with st.container(border=True):")
    assert_contains(
        SYS_AI_UPDATES,
        'st.columns([4, 1], vertical_alignment="center")',
    )
    assert_contains(SYS_AI_UPDATES, "st.caption(update.date)")
    assert_not_contains(SYS_AI_UPDATES, "unsafe_allow_html=True")
    assert_contains(SYS_AI_UPDATES, "st.markdown(update.summary)")
    assert_not_contains(SYS_AI_UPDATES, "_shared")
    assert_contains(SYS_AI_UPDATES, "_components.render_tag_row(tags)")
    assert_contains(SYS_AI_UPDATES, 'st.link_button("深化連結"')
    assert_contains(SYS_AI_UPDATES, 'source_id="system.ai-updates"')
    assert_contains(SYS_AI_UPDATES, "_components.render_state_banner(state)")
    assert_contains(GUIDE, "`GET /api/v1/system/ai-updates`")
    assert_contains(GUIDE, "AI 更新 API 無法使用")


def test_fund_catalog_is_api_only_with_manual_cik_preserved() -> None:
    assert_contains(
        READ_API,
        'http://127.0.0.1:8000/api/v1/institutions/funds',
    )
    assert_contains(INSTITUTION_PORTFOLIO, "_read_api.load_fund_catalog()")
    assert_not_contains(INSTITUTION_PORTFOLIO, "read_artifact")
    assert_not_contains(INSTITUTION_PORTFOLIO, "ARTIFACTS")
    assert_not_contains(INSTITUTION_PORTFOLIO, "local_fallback")
    assert_not_contains(INSTITUTION_PORTFOLIO, "all_unavailable")
    assert_contains(INSTITUTION_PORTFOLIO, "api_failure")
    assert_not_contains(INSTITUTION_PORTFOLIO, "_shared.load_json")
    assert_not_contains(INSTITUTION_PORTFOLIO, "_FUNDS_FILE")
    assert_contains(INSTITUTION_PORTFOLIO, "from scripts import edgar_13f")
    assert_contains(INSTITUTION_PORTFOLIO, 'text_input("或輸入 CIK"')
    assert_contains(INSTITUTION_PORTFOLIO, "target.query")
    assert_contains(INSTITUTION_PORTFOLIO, "仍可輸入 CIK")
    assert_contains(GUIDE, "`GET /api/v1/institutions/funds`")
    assert_contains(GUIDE, "SEC EDGAR")
    assert_contains(GUIDE, "第三個 **API-only**")


def test_single_ticker_iv_rank_is_api_only_without_candidate_n_plus_one() -> None:
    assert_contains(
        READ_API,
        'http://127.0.0.1:8000/api/v1/options/iv-history/',
    )
    assert_contains(READ_API, "def load_iv_history(")
    assert_contains(US_OPTIONS, "_read_api.load_iv_history(ticker)")
    assert_not_contains(US_OPTIONS, "read_artifact")
    assert_not_contains(US_OPTIONS, "iv_history_spec")
    assert_not_contains(US_OPTIONS, "local_fallback")
    assert_not_contains(US_OPTIONS, "all_unavailable")
    assert_contains(US_OPTIONS, "api_failure")
    assert_contains(US_OPTIONS, "response_too_large")
    candidate_section = US_OPTIONS.split("def _iv_rank_spark", 1)[1].split(
        "def _candidate_grid", 1
    )[0]
    assert_not_contains(candidate_section, "load_iv_history")
    assert_contains(GUIDE, "`GET /api/v1/options/iv-history/{ticker}`")
    assert_contains(GUIDE, "當日候選排行")
    assert_contains(GUIDE, "Options Cockpit")
    assert_contains(GUIDE, "第四個 **API-only**")


def test_options_flow_feed_is_api_only_with_preserved_live_boundary() -> None:
    assert_contains(OPTIONS_FLOW, "_read_api.load_options_flow()")
    assert_not_contains(OPTIONS_FLOW, "read_artifact")
    assert_not_contains(OPTIONS_FLOW, "ARTIFACTS")
    assert_not_contains(OPTIONS_FLOW, "local_fallback")
    assert_not_contains(OPTIONS_FLOW, "all_unavailable")
    assert_not_contains(OPTIONS_FLOW, "scripts.artifact_loader")
    assert_contains(OPTIONS_FLOW, "api_failure")
    assert_not_contains(OPTIONS_FLOW, "_shared.load_json")

    live_chain = OPTIONS_FLOW.split("def _live_chain", 1)[1].split(
        "def _fmt_notional", 1
    )[0]
    assert_contains(live_chain, "from scripts import options_free")
    assert_contains(live_chain, "options_free.analyze_options(ticker)")

    assert_contains(
        OPTIONS_FLOW,
        'st.tabs(["🔥 異常流排行", "🔎 個股明細"])',
    )
    feed_projection = OPTIONS_FLOW.split("df = pd.DataFrame([{", 1)[1].split(
        "} for s in signals])", 1
    )[0]
    projected_columns = [
        line.split('"', 2)[1]
        for line in feed_projection.splitlines()
        if line.lstrip().startswith('"')
    ]
    assert projected_columns == [
        "方向",
        "代號",
        "估權利金",
        "熱度",
        "V/OI峰值",
        "最活躍履約",
        "skew",
        "標籤",
    ]
    for metric in [
        '"估權利金"',
        '"最活躍履約價"',
        '"V/OI 峰值"',
        '"call/put 量比" if bullish else "put/call 量比"',
    ]:
        assert_contains(OPTIONS_FLOW, metric)

    assert_contains(
        OPTIONS_FLOW,
        "_shared.ticker_action_buttons(ticker, key_prefix)",
    )
    assert_contains(SHARED, "st.session_state[state_key] = sym")
    assert_contains(SHARED, 'if state_key == "checkup_ticker":')
    assert_contains(SHARED, 'st.session_state["checkup_handoff"]')
    assert_contains(GUIDE, "`GET /api/v1/signals/options-flow/feed`")
    assert_contains(GUIDE, "第五個 **API-only**")
    assert_contains(API_INVENTORY, "Phase 2K")
    assert_not_contains(
        API_INVENTORY,
        "Future standalone Options Flow consumer; no frontend migration in Phase 2J",
    )
    assert_not_contains(API_INVENTORY, "The page remains local in Phase 2J")
    assert_not_contains(
        API_INVENTORY,
        "Frontend adoption is intentionally deferred to a separate Phase 2K",
    )


def test_crypto_universe_page_is_strict_api_only() -> None:
    assert_contains(
        READ_API,
        'http://127.0.0.1:8000/api/v1/crypto/universe',
    )
    assert_contains(READ_API, "def load_crypto_universe(")
    assert_contains(CRYPTO_UNIVERSE, "_read_api.load_crypto_universe()")
    assert_contains(CRYPTO_UNIVERSE, "def _tradingview_export(")
    assert_contains(CRYPTO_UNIVERSE, "item.tv_symbol")
    for forbidden in (
        "_shared",
        "pandas",
        "Path(",
        "read_text(",
        "reports/crypto",
        "tradingview_watchlist.txt",
    ):
        assert_not_contains(CRYPTO_UNIVERSE, forbidden)
    assert_contains(GUIDE, "`GET /api/v1/crypto/universe`")
    assert_contains(GUIDE, "第六個 **API-only**")
    assert_contains(API_INVENTORY, "implemented in Phase 4C")


def test_market_thesis_selected_reads_are_api_only() -> None:
    assert_contains(
        READ_API,
        "http://127.0.0.1:8000/api/v1/market-context/market-thesis/latest",
    )
    assert_contains(READ_API, "def load_market_thesis(")
    assert_contains(MARKET_THESIS, "_read_api.load_market_thesis()")
    assert_contains(READ_API, "/api/v1/market-context/market-thesis/validation")
    assert_contains(READ_API, "/api/v1/market-context/market-thesis/regime-history")
    assert_contains(MARKET_THESIS, "_read_api.load_market_thesis_validation()")
    assert_contains(MARKET_THESIS, "_read_api.load_market_thesis_regime_history()")
    assert_not_contains(MARKET_THESIS, "validation_summary.json")
    assert_not_contains(MARKET_THESIS, "regime_history.json")
    assert_not_contains(MARKET_THESIS, '_DIR.glob("*forecast_*.json")')
    assert_contains(GUIDE, "第七個 **API-only**")
    assert_contains(API_INVENTORY, "implemented in Phase 4D")


def test_reversal_and_oversold_snapshots_are_api_only_with_live_radar_preserved() -> None:
    for path in (
        "http://127.0.0.1:8000/api/v1/signals/reversal-radar/latest",
        "http://127.0.0.1:8000/api/v1/signals/oversold-reversal/latest",
        "http://127.0.0.1:8000/api/v1/signals/oversold-reversal/validation",
    ):
        assert_contains(READ_API, path)
    assert_contains(READ_API, "def load_reversal_radar(")
    assert_contains(READ_API, "def load_oversold_reversal(")
    assert_contains(READ_API, "def load_oversold_reversal_validation(")
    assert_contains(RADAR, "_read_api.load_reversal_radar()")
    assert_not_contains(RADAR, 'REPORTS_DIR / "reversal_radar" / "latest.json"')
    assert_contains(RADAR, "import reversal_radar")
    assert_contains(RADAR, "rgui._analyze")
    assert_contains(OVERSOLD_REVERSAL, "_read_api.load_oversold_reversal()")
    assert_contains(
        OVERSOLD_REVERSAL,
        "_read_api.load_oversold_reversal_validation()",
    )
    assert_not_contains(OVERSOLD_REVERSAL, "validation_summary.json")
    assert_contains(GUIDE, "第八與第九個 **API-only**")
    assert_contains(API_INVENTORY, "implemented in Phase 4E")


def test_secondary_candidate_consumers_are_api_only_with_local_siblings() -> None:
    assert_contains(SYS_SCHEDULES, "_read_api.load_ranked_candidates()")
    candidate_result = SYS_SCHEDULES.split(
        "def _latest_candidate_refresh_result", 1
    )[1].split("def _latest_data_health_result", 1)[0]
    assert_not_contains(candidate_result, 'candidate_output_path("ranked_candidates.json")')
    assert_contains(candidate_result, "_read_api.load_money_flow()")
    assert_not_contains(candidate_result, 'REPORTS_DIR / "money_flow" / "latest.json"')

    assert_contains(INSTITUTIONAL_HOLDINGS, "_read_api.load_scored_candidates()")
    score_context = INSTITUTIONAL_HOLDINGS.split(
        "def _render_score_context", 1
    )[1].split("def _render_detail", 1)[0]
    assert_not_contains(score_context, 'candidate_output_path("scored_candidates.json")')
    assert_contains(INSTITUTIONAL_HOLDINGS, "from scripts import institutional_free")

    assert_contains(ANALYTICS_DB, "_read_api.load_ranked_candidates()")
    ranked_defaults = ANALYTICS_DB.split("def _ranked_tickers", 1)[1].split(
        "def _parse_tickers", 1
    )[0]
    assert_not_contains(ranked_defaults, 'candidate_output_path("ranked_candidates.json")')
    assert_contains(ANALYTICS_DB, "def _refresh_fundamentals")

    assert_contains(GUIDE, "第十一至第十三個 **API-only** slices")
    for phase in ("Phase 4G", "Phase 4H", "Phase 4I"):
        assert_contains(API_INVENTORY, phase)


def test_phase4m_4p_candidate_slices_and_service_lifecycle_are_documented() -> None:
    options_grid = US_OPTIONS.split("def _candidate_grid", 1)[1].split("def _num", 1)[0]
    assert_contains(options_grid, "_read_api.load_scored_candidates()")
    assert_not_contains(options_grid, 'candidate_output_path("scored_candidates.json")')
    assert_contains(options_grid, "_iv_rank_spark(ticker)")

    role_seed = INDUSTRY_ROLES.split("def _candidate_tickers", 1)[1].split(
        "def _status_label", 1
    )[0]
    assert_contains(role_seed, "_read_api.load_ranked_candidates()")
    assert_not_contains(role_seed, 'candidate_output_path("ranked_candidates.json")')
    assert_contains(role_seed, 'REPORTS_DIR / "x_influencer_picks.json"')

    quickpick = COCKPIT.split("def _watchlist_quickpick", 1)[1].split(
        "def _social_quickpick_label", 1
    )[0]
    assert_contains(quickpick, "_read_api.load_scored_candidates()")
    assert_not_contains(quickpick, 'candidate_output_path("scored_candidates.json")')
    assert_contains(quickpick, "_read_api.load_options_flow()")

    assert_contains(GUIDE, "第十四至第十六個 **API-only** slices")
    for phase in ("Phase 4M", "Phase 4N", "Phase 4O", "Phase 4P"):
        assert_contains(API_INVENTORY, phase)


def test_phase4q_4s_scored_slices_are_api_only_and_documented() -> None:
    assert_contains(ANALYST_VIEWS, "_read_api.load_scored_candidates()")
    assert_not_contains(
        ANALYST_VIEWS, 'candidate_output_path("scored_candidates.json")'
    )
    assert_contains(ANALYST_VIEWS, "_shared.load_analyst_views(ticker)")

    assert_contains(SECTOR_ROTATION, "_read_api.load_scored_candidates()")
    assert_not_contains(
        SECTOR_ROTATION, 'candidate_output_path("scored_candidates.json")'
    )
    assert_contains(SECTOR_ROTATION, "_shared.ticker_sector_etf(ticker)")

    assert_contains(US_SCREENER, "_read_api.load_scored_candidates_screener()")
    assert_not_contains(
        US_SCREENER, 'candidate_output_path("scored_candidates.json")'
    )
    assert_contains(US_SCREENER, 'DATA_DIR / "layer2_results.json"')
    assert_contains(READ_API, "/api/v1/candidates/scored/screener")

    assert_contains(GUIDE, "第十七至第十九個 **API-only** slices")
    for phase in ("Phase 4Q", "Phase 4R", "Phase 4S"):
        assert_contains(API_INVENTORY, phase)


def test_phase4w_4z_money_flow_slices_are_api_only_and_documented() -> None:
    assert_contains(
        READ_API,
        "http://127.0.0.1:8000/api/v1/market-context/money-flow/latest",
    )
    assert_contains(READ_API, "def load_money_flow(")
    candidate_result = SYS_SCHEDULES.split(
        "def _latest_candidate_refresh_result", 1
    )[1].split("def _latest_data_health_result", 1)[0]
    assert_contains(candidate_result, "_read_api.load_money_flow()")
    assert_not_contains(candidate_result, 'REPORTS_DIR / "money_flow" / "latest.json"')

    standalone = COCKPIT.split("def render()", 1)[1]
    embedded = COCKPIT.split("def render_for", 1)[1].split("def render()", 1)[0]
    assert_contains(standalone, "_load_money_flow_state()")
    assert_contains(embedded, "_load_money_flow_state()")
    assert_not_contains(COCKPIT, "_load_money_flow_artifact")
    assert_contains(COCKPIT, "載入 EDGAR Form-4")
    assert_contains(GUIDE, "第二十三至第二十五個 **API-only** slices")
    for phase in ("Phase 4W", "Phase 4X", "Phase 4Y", "Phase 4Z"):
        assert_contains(API_INVENTORY, phase)


def test_phase5a_5b_options_flow_consumers_are_api_only_and_documented() -> None:
    options_result = SYS_SCHEDULES.split(
        "def _latest_options_flow_result", 1
    )[1].split("def _latest_candidate_refresh_result", 1)[0]
    assert_contains(options_result, "_read_api.load_options_flow()")
    assert_not_contains(options_result, 'REPORTS_DIR / "options_flow" / "latest.json"')
    assert_contains(SYS_SCHEDULES, "result_cache")

    quickpick = COCKPIT.split("def _watchlist_quickpick", 1)[1].split(
        "def _social_quickpick_label", 1
    )[0]
    assert_contains(quickpick, "_read_api.load_options_flow()")
    assert_not_contains(quickpick, 'reports / "options_flow" / "latest.json"')
    assert_contains(quickpick, "_read_api.load_scored_candidates()")
    assert_contains(GUIDE, "第二十六與第二十七個 **API-only** slices")
    for phase in ("Phase 5A", "Phase 5B"):
        assert_contains(API_INVENTORY, phase)


def test_phase5c_5e_selected_reads_are_api_only_and_documented() -> None:
    crypto_result = SYS_SCHEDULES.split(
        "def _latest_crypto_result", 1
    )[1].split("def _latest_cot_result", 1)[0]
    assert_contains(crypto_result, "_read_api.load_crypto_universe()")
    assert_not_contains(crypto_result, 'REPORTS_DIR / "crypto" / "universe_latest.json"')

    theme_result = SYS_SCHEDULES.split(
        "def _latest_theme_flow_result", 1
    )[1].split("_RESULT_FETCHERS", 1)[0]
    assert_contains(theme_result, "_read_api.load_theme_flow()")
    assert_not_contains(theme_result, 'REPORTS_DIR / "theme_flow_snapshot.json"')
    assert_contains(SYS_SCHEDULES, '"crypto_universe"')
    assert_contains(SYS_SCHEDULES, '"theme_flow"')

    assert_contains(COCKPIT, "_read_api.load_iv_history(ticker)")
    assert_contains(COCKPIT, "iv_percentile_from_series")
    assert_not_contains(COCKPIT, "def _load_iv_series")
    assert_contains(COCKPIT, "mo.analyze(ticker)")
    assert_contains(COCKPIT, "of.analyze_options(ticker)")
    assert_contains(GUIDE, "第二十八至第三十個 **API-only** slices")
    for phase in ("Phase 5C", "Phase 5D", "Phase 5E"):
        assert_contains(API_INVENTORY, phase)


def test_phase5f_5h_selected_reads_are_api_only_and_documented() -> None:
    quickpick = COCKPIT.split("def _watchlist_quickpick", 1)[1].split(
        "def _social_quickpick_label", 1
    )[0]
    assert_contains(quickpick, "_read_api.load_social_intelligence()")
    assert_not_contains(quickpick, 'reports / "social_intelligence" / "latest.json"')
    assert_contains(quickpick, 'reports / "x_influencer_picks.json"')
    assert_contains(MARKET_THESIS, "_read_api.load_market_thesis_validation()")
    assert_contains(MARKET_THESIS, "_read_api.load_market_thesis_regime_history()")
    assert_contains(GUIDE, "第三十一至第三十三個 **API-only** slices")
    for phase in ("Phase 5F", "Phase 5G", "Phase 5H"):
        assert_contains(API_INVENTORY, phase)


def test_phase5i_5k_sector_rotation_reads_are_api_only_and_documented() -> None:
    assert_contains(READ_API, "/api/v1/market-context/sector-rotation/latest")
    assert_contains(SECTOR_ROTATION, "_read_api.load_sector_rotation()")
    assert_not_contains(SECTOR_ROTATION, "load_sector_flow")
    assert_contains(STOCK_CHECKUP, "board_state = _sector_board_state()")
    assert_contains(STOCK_CHECKUP, "lambda selected: _sector_positioning(selected, board_state)")
    assert_not_contains(STOCK_CHECKUP, "load_sector_flow")
    assert_contains(GUIDE, "第三十四至第三十五個 **API-only** slices")
    for phase in ("Phase 5I", "Phase 5J", "Phase 5K"):
        assert_contains(API_INVENTORY, phase)


def test_phase5u_5w_today_gate_reads_are_api_only_and_documented() -> None:
    assert_contains(READ_API, "/api/v1/reports/daily-summary/latest")
    assert_contains(TODAY, "_read_api.load_market_thesis()")
    assert_contains(TODAY, "_read_api.load_daily_summary()")
    for retired in (
        "_latest_market_thesis",
        "_latest_daily_summary",
        "_MARKET_THESIS_DIR",
        '"summary.json"',
    ):
        assert_not_contains(TODAY, retired)
    assert_contains(GUIDE, "第四十三與第四十四個 **API-only** slices")
    for phase in ("Phase 5U", "Phase 5V", "Phase 5W"):
        assert_contains(API_INVENTORY, phase)


def test_phase5x_5z_selected_reads_are_api_only_and_documented() -> None:
    report_result = SYS_SCHEDULES.split("def _latest_report_result", 1)[1].split(
        "def _latest_ledger_result", 1
    )[0]
    assert_contains(report_result, "_read_api.load_daily_summary()")
    assert_not_contains(report_result, "find_report_dates")
    assert_not_contains(report_result, '"summary.json"')
    assert_contains(SYS_SCHEDULES, '"report_dir"')
    assert_contains(READ_API, "/api/v1/reports/playbook-validation/latest")
    assert_contains(PLAYBOOK_VALIDATION, "_read_api.load_playbook_validation()")
    assert_not_contains(PLAYBOOK_VALIDATION, "_shared")
    assert_not_contains(PLAYBOOK_VALIDATION, "latest.json")
    assert_contains(RETRO_ANALYSIS, "continuation_validation")
    assert_contains(GUIDE, "第四十五與第四十六個 **API-only** slices")
    for phase in ("Phase 5X", "Phase 5Y", "Phase 5Z"):
        assert_contains(API_INVENTORY, phase)


def test_phase6a_6f_continuation_and_cot_are_api_only_and_documented() -> None:
    assert_contains(READ_API, "/api/v1/reports/continuation-validation/latest")
    assert_contains(READ_API, "/api/v1/reports/cot")
    assert_contains(CONTINUATION_VALIDATION, "_read_api.load_continuation_validation()")
    assert_not_contains(CONTINUATION_VALIDATION, "continuation_strength.json")
    assert_contains(US_COT, "_read_api.load_cot_catalog()")
    assert_contains(US_COT, "_read_api.load_cot_report(chosen)")
    assert_not_contains(US_COT, "_COT_DIR")
    assert_contains(SYS_SCHEDULES, "_read_api.load_cot_catalog()")
    assert_contains(GUIDE, "第四十八與第四十九個 **API-only** slices")
    assert_contains(GUIDE, "五十四個 API-only")
    for phase in ("Phase 6A", "Phase 6D", "Phase 6E", "Phase 6F"):
        assert_contains(API_INVENTORY, phase)


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
    trust = TODAY.split("def _render_trust_boundary", 1)[1].split(
        "def _ranked_result_df", 1
    )[0]
    for loader in (
        "_read_api.load_market_thesis_validation()",
        "_read_api.load_reversal_radar_validation()",
        "_read_api.load_oversold_reversal_validation()",
    ):
        if trust.count(loader) != 1:
            raise AssertionError((loader, trust))
    assert_not_contains(TODAY, "_local_validation_summary")
    assert_not_contains(TODAY, "validation_summary.json")
    assert_contains(TODAY, "_read_api.load_options_flow()")
    assert_contains(TODAY, "_read_api.load_reversal_radar()")
    assert_contains(TODAY, "_read_api.load_oversold_reversal()")
    for removed in ("_flow_signals", "_FLOW_DIR", "_REVERSAL_DIR", "_OVERSOLD_DIR"):
        assert_not_contains(TODAY, removed)
    assert_contains(TODAY, "_shared.load_reconciliation()")
    assert_contains(TODAY, "_shared.load_ledger()")
    assert_contains(TODAY, "min_resolved_for_verdict")
    assert_contains(TODAY, "min_resolved_across_tiers")
    assert_contains(TODAY, "背景-only")
    assert_contains(TODAY, "觀察-only")
    assert_contains(TODAY, "risk-control")
    assert_contains(GUIDE, "第四十至第四十二個 **API-only** slices")
    assert_contains(GUIDE, "五十四個 API-only")
    for phase in ("Phase 5R", "Phase 5S", "Phase 5T"):
        assert_contains(API_INVENTORY, phase)


def test_today_decision_renders_local_refresh_progress() -> None:
    assert_contains(CANDIDATE_CONTROLS, '@st.fragment(run_every="8s")')
    assert_contains(CANDIDATE_CONTROLS, "def _render_local_refresh_status")
    assert_contains(CANDIDATE_CONTROLS, "reports/run_status/candidates-local.json")
    assert_contains(CANDIDATE_CONTROLS, "st.progress")
    assert_contains(CANDIDATE_CONTROLS, 'stage.get("progress_pct")')
    assert_contains(CANDIDATE_CONTROLS, "rank_candidates")
    assert_contains(CANDIDATE_CONTROLS, "ranked_candidates.json")
    assert_contains(CANDIDATE_CONTROLS, "updated_at")
    assert_not_contains(CANDIDATE_CONTROLS, "components.html")
    assert_not_contains(CANDIDATE_CONTROLS, "window.parent.location.reload")
    assert_not_contains(CANDIDATE_CONTROLS, "setTimeout")
    assert_contains(CANDIDATE_CONTROLS, "可能已中斷")


def test_today_decision_reads_deterministic_ranked_candidates() -> None:
    assert_contains(TODAY, "def _ranked_candidates")
    assert_contains(TODAY, "_read_api.load_ranked_candidates()")
    assert_contains(TODAY, "_read_api.load_scored_candidates()")
    assert_not_contains(TODAY, 'candidate_output_path("ranked_candidates.json")')
    assert_not_contains(TODAY, 'candidate_output_path("scored_candidates.json")')
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
        "read_pending_codex_request",
        "resume_pending_codex_run",
        "candidate_pipeline_last_launch",
    ]:
        assert_contains(CANDIDATE_CONTROLS, needle)


def test_today_decision_delegates_candidate_controls_to_module() -> None:
    assert_contains(TODAY, "from . import _candidate_controls, _components, _read_api, _shared")
    assert_contains(TODAY, "_candidate_controls.render()")
    assert_not_contains(TODAY, "def _render_candidate_pipeline_controls")
    assert_not_contains(TODAY, "def _render_local_refresh_status")
    assert_not_contains(TODAY, "def _render_codex_auth_status")
    assert_contains(CANDIDATE_CONTROLS, "def render()")
    assert_contains(CANDIDATE_CONTROLS, "_render_candidate_pipeline_controls()")
    assert_contains(CANDIDATE_CONTROLS, "_render_codex_auth_status()")
    assert_contains(CANDIDATE_CONTROLS, "_render_local_refresh_status()")


def test_today_decision_history_falls_back_to_rank_source_candidates() -> None:
    assert_contains(CANDIDATE_CONTROLS, 'metrics.get("passed_hard_filters", metrics.get("rank_source_candidates"))')
    assert_contains(CANDIDATE_CONTROLS, "_safe_number(")


def test_today_decision_history_uses_plain_language_column_names() -> None:
    for needle in [
        "def _status_zh",
        '"通過基礎篩選"',
        '"排名產出"',
        '"Top N 上限"',
        '"期權檢查數"',
        '"狀態": _status_zh(row.get("status"))',
    ]:
        assert_contains(CANDIDATE_CONTROLS, needle)


def test_today_decision_history_shows_flow_instead_of_repeated_output_path() -> None:
    for needle in [
        "def _history_flow",
        '"流程": _history_flow(row)',
        "完整刷新 + 排名",
        "只重排",
        "少量 LLM",
    ]:
        assert_contains(CANDIDATE_CONTROLS, needle)
    assert_not_contains(CANDIDATE_CONTROLS, '"output": ranked.get("path", "-")')


def test_today_decision_launch_tracking_uses_a_safe_projection() -> None:
    for needle in [
        "def _safe_launch_projection",
        "def _normalize_launch_session",
        "def _render_launch_tracking",
        "candidate_pipeline_last_launch",
        "最近啟動",
        '"mode_label": _MODE_LABELS[mode]',
        '"operation": projected_operation',
        '"event_code": projected_event',
    ]:
        assert_contains(CANDIDATE_CONTROLS, needle)
    for unsafe_surface in [
        "def _tail_text",
        "追蹤細節",
        "_tail_text(log_path)",
        "st.code(",
    ]:
        assert_not_contains(CANDIDATE_CONTROLS, unsafe_surface)


def test_today_decision_surfaces_actual_ranked_and_llm_candidates() -> None:
    for needle in [
        "def _ranked_result_df(rows: list[dict], limit: int = 50)",
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
        "ranked_available=isinstance(",
        "scored_available=isinstance(",
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
        assert_contains(CANDIDATE_CONTROLS, needle)
    for raw_ui in [
        "status.upper()",
        "updated_at {updated_at}",
        "ranked {metrics.get",
        "scored {metrics",
        "st.caption(message)",
    ]:
        assert_not_contains(CANDIDATE_CONTROLS, raw_ui)


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
    assert_contains(COCKPIT, "def _render_external_confirmation")
    assert_contains(COCKPIT, "外部確認")
    assert_contains(COCKPIT, "載入 EDGAR Form-4")
    assert_not_contains(COCKPIT, "##### 建議合約 —")


def test_x_sentiment_surfaces_free_first_social_boundaries() -> None:
    for needle in [
        "Free-first social intelligence",
        "source_statuses",
        "付費增強 / 下次優化",
        "Codex SDK / ChatGPT 訂閱",
        "manual_codex_prompt",
        "reports/social_intelligence/latest.json",
        "單一博主帳號會改用 Agent Reach",
        "整份清單用 Agent Reach 抓最近 posts",
        "_fetch_agent_reach_posts_or_raise",
        "上次快照 Agent Reach",
        "_render_snapshot_agent_reach_status",
        "_render_raw_posts",
        "內文預覽",
        "完整內文",
        "更新 free-first 社群快照",
        "Codex 博主研究重跑",
        "AI 摘要",
        "產生 AI 摘要",
        "social_intelligence_summary.generate_ai_summary",
        "social_intelligence_summary.load_ai_summary",
        "social_intelligence_summary.write_ai_summary",
        "codex_auth_flow.start_login",
        "codex_auth_flow.read_login_prompt",
        "一次性代碼",
        "st.radio(\"檢視模式\"",
        "_maybe_auto_refresh_radar",
        "_maybe_auto_generate_ai_summary",
        "_SOCIAL_RADAR_AUTO_RUN_KEY",
        "_SOCIAL_AI_AUTO_SUMMARY_KEY",
        "自動更新 free-first 社群快照",
        "自動產生 AI 摘要",
        "st.tabs([\"Ticker 列表\", \"AI 摘要\", \"全部 citations\"])",
        "_social_snapshot_state",
        "load_social_intelligence",
        "_ranked_candidates_seed",
        "load_ranked_candidates",
    ]:
        assert_contains(X_SENTIMENT, needle)


def test_theme_flow_persisted_reads_are_api_only_with_mutations_preserved() -> None:
    for needle in [
        "_theme_flow_state",
        "load_theme_flow",
        "_theme_flow_analysis_state",
        "load_theme_flow_analysis",
        'launch_background("refresh_board")',
        'launch_background("ai_read")',
        "load_theme_insider",
    ]:
        assert_contains(THEME_FLOW, needle)
    for needle in [
        "controls.read_snapshot()",
        "_shared.load_theme_flow()",
        "_load_theme_flow_read_payload",
        "from scripts.theme_rotation import board_fingerprint, is_current_read",
    ]:
        assert_not_contains(THEME_FLOW, needle)


def test_x_sentiment_shows_agent_reach_cookie_update_guide() -> None:
    for needle in [
        "X 登入 / 更新 Agent Reach Cookie",
        "開啟測試機 X 登入視窗",
        "登入完成，更新 Agent Reach Cookie",
        " dedicated browser/session ",
        "只會寫入 `auth_token` / `ct0` 到測試機 Agent Reach config",
        "不顯示 auth_token / ct0 明文",
        "/home/kenny/.agent-reach/config.yaml",
    ]:
        assert_contains(X_SENTIMENT, needle)
    for needle in [
        "agent_reach_auth.start_login_session",
        "agent_reach_auth.update_config_from_running_session",
        "agent_reach_auth.agent_reach_config_status",
    ]:
        assert_contains(X_SENTIMENT, needle)


def test_agent_reach_auth_never_logs_or_returns_raw_tokens() -> None:
    for needle in [
        "def _mask_secret",
        "def write_agent_reach_config",
        "def update_config_from_running_session",
        "twitter_auth_token",
        "twitter_ct0",
        "remote-debugging-address=127.0.0.1",
        "https://x.com/login",
    ]:
        assert_contains(AGENT_REACH_AUTH, needle)
    for forbidden in [
        "print(credentials",
        "st.code(credentials",
        "return credentials",
    ]:
        assert_not_contains(AGENT_REACH_AUTH, forbidden)


def test_influencers_page_exposes_roster_editor() -> None:
    for needle in [
        "搜尋 / 加入",
        "搜尋帳號、名稱或 X URL",
        "候選清單",
        "已加入",
        "可加入",
        "已加入其他市場",
        "AI 分類",
        "批次操作",
        "名冊表格",
        "每頁",
        "頁碼",
        "批次匯入",
        "預覽批次匯入",
        "匯入 / 更新名冊",
        "匯入模式",
        "保留既有欄位",
        "只新增",
        "完全覆蓋",
        "搜尋帳號 / 名稱 / 備註",
        "資料狀態",
        "確認刪除分類",
        "復原刪除",
        "分類清單",
        "進階 JSON",
        "保存 JSON",
        "parse_bulk_influencers",
        "lookup_x_preview",
        "preview_bulk_import",
        "apply_bulk_import",
        "filter_influencers",
        "roster_table_rows",
        "build_search_candidates",
        "suggest_ai_category",
        "bulk_upsert_influencers",
        "delete_influencer_with_snapshot",
        "upsert_influencer",
        "delete_influencer",
        "rename_category",
        "content/influencers.json",
    ]:
        assert_contains(INFLUENCERS, needle)
    for forbidden in [
        'st.subheader(f"📂',
        "cols[n % n_cols].container(border=True)",
    ]:
        assert_not_contains(INFLUENCERS, forbidden)


def test_cot_report_generation_gates_on_codex_auth() -> None:
    for needle in [
        "from scripts import codex_auth_flow",
        "codex_auth_flow.refresh_status()",
        "codex_auth_flow.start_login()",
        "cot_codex_auth_login",
        "Codex 登入",
        "前往 Codex 登入",
        "在登入頁輸入代碼",
        "_login_url_from_text",
        "read_login_prompt",
        "一次性代碼",
        "_ensure_codex_auth_for_generate(render=",
    ]:
        assert_contains(US_COT, needle)
    for technical in [
        "docker exec",
        "server shell",
        "codex-auth.log",
        "持久化 volume",
        "submit_login_code",
        "form_submit_button",
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
        raise AssertionError("candidates-local should not require Codex preflight")
    for text in (AUDIT, GUIDE):
        assert_contains(text, "ranked_candidates.json")
        assert_contains(text, "candidates-rank-local")


def test_optional_llm_candidate_scoring_uses_subscription_model() -> None:
    for needle in [
        "CANDIDATE_MODEL ?=",
        "CANDIDATE_RETRIES ?= 1",
        "CANDIDATE_DEFERRED_RETRIES ?= 0",
        "CANDIDATE_SCORING_MODE ?= fast",
        "RESCORE_STALE_LLM ?= 1",
        "CODEX_SDK_TIMEOUT ?= 180",
        "candidate-preflight:",
        "candidates-score-local:",
        "CODEX_SDK_TIMEOUT=$(CODEX_SDK_TIMEOUT) $(PY) scripts/02_llm_score.py",
        "--provider codex",
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
        assert_contains(text, "Codex")
        assert_contains(text, "CANDIDATE_MODEL")


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
        "CODEX_SDK_TIMEOUT",
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
        test_trade_state_cycle_filter_exposes_six_course_cycles,
        test_trade_state_detail_and_story_are_trader_facing,
        test_stock_checkup_search_refreshes_core_trade_data_and_gates_deep_options,
        test_quote_fallback_is_adopted_on_price_surfaces,
        test_options_pages_split_decision_summary_from_full_chain_detail,
        test_us_screener_reuses_embeddable_analyst_renderer,
        test_industry_roles_review_page_surfaces_missing_and_status_views,
        test_snapshot_default_page_matches_navigation_default,
        test_ux1a_shared_foundations_are_pure_and_native,
        test_global_ai_chat_assistant_is_wired_into_app_shell,
        test_analytics_db_renders_automated_checks,
        test_data_health_entry_and_refresh_center_are_discoverable,
        test_scheduled_market_snapshots_render_without_manual_refresh,
        test_validation_lanes_live_inside_retro_analysis_hub,
        test_continuation_lane_distinguishes_blocked_from_accumulating,
        test_options_cockpit_links_to_validation_hub_not_new_sidebar_page,
        test_monthly_reflection_has_a_safe_structured_summary,
        test_schedules_registry_is_api_only_with_local_results_preserved,
        test_ai_updates_feed_is_api_first_with_preserved_ui_behavior,
        test_fund_catalog_is_api_only_with_manual_cik_preserved,
        test_single_ticker_iv_rank_is_api_only_without_candidate_n_plus_one,
        test_options_flow_feed_is_api_only_with_preserved_live_boundary,
        test_crypto_universe_page_is_strict_api_only,
        test_market_thesis_selected_reads_are_api_only,
        test_reversal_and_oversold_snapshots_are_api_only_with_live_radar_preserved,
        test_secondary_candidate_consumers_are_api_only_with_local_siblings,
        test_phase4m_4p_candidate_slices_and_service_lifecycle_are_documented,
        test_phase4q_4s_scored_slices_are_api_only_and_documented,
        test_phase4w_4z_money_flow_slices_are_api_only_and_documented,
        test_phase5a_5b_options_flow_consumers_are_api_only_and_documented,
        test_phase5c_5e_selected_reads_are_api_only_and_documented,
        test_phase5f_5h_selected_reads_are_api_only_and_documented,
        test_phase5i_5k_sector_rotation_reads_are_api_only_and_documented,
        test_phase5u_5w_today_gate_reads_are_api_only_and_documented,
        test_phase5x_5z_selected_reads_are_api_only_and_documented,
        test_phase6a_6f_continuation_and_cot_are_api_only_and_documented,
        test_candidate_tables_use_shared_action_trio,
        test_today_decision_renders_trust_boundary,
        test_today_decision_renders_local_refresh_progress,
        test_today_decision_reads_deterministic_ranked_candidates,
        test_today_decision_surfaces_trade_state_entry_point,
        test_today_decision_renders_candidate_pipeline_controls,
        test_today_decision_delegates_candidate_controls_to_module,
        test_today_decision_history_falls_back_to_rank_source_candidates,
        test_today_decision_history_uses_plain_language_column_names,
        test_today_decision_history_shows_flow_instead_of_repeated_output_path,
        test_today_decision_launch_tracking_uses_a_safe_projection,
        test_today_decision_surfaces_actual_ranked_and_llm_candidates,
        test_today_decision_status_panel_uses_user_facing_language,
        test_options_cockpit_contract_panel_is_tradeability_first,
        test_x_sentiment_surfaces_free_first_social_boundaries,
        test_theme_flow_persisted_reads_are_api_only_with_mutations_preserved,
        test_x_sentiment_shows_agent_reach_cookie_update_guide,
        test_influencers_page_exposes_roster_editor,
        test_cot_report_generation_gates_on_codex_auth,
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
