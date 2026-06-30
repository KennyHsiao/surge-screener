# Quant Radar — dev tasks.  Usage: `make <target>` (run `make` for the list).
PY   := .venv/bin/python
PORT ?= 8501
MARKETS ?= US
UNIVERSE ?= sp1500
MIN_SCORE ?= 65
RANK_LIMIT ?= 50
OPTIONS_GATE_LIMIT ?= 0
CANDIDATE_LIMIT ?= 25
CANDIDATE_MODEL ?= claude-sonnet-4-6
CANDIDATE_RETRIES ?= 1
CANDIDATE_DEFERRED_RETRIES ?= 0
CANDIDATE_SCORING_MODE ?= fast
RESCORE_STALE_LLM ?= 1
LLM_SCORE_INPUT ?= ranked_candidates.json
CLAUDE_AGENT_TIMEOUT ?= 180
YF_BATCH_SIZE ?= 25
MIN_DATA_COVERAGE ?= 0.70
MIN_AVG_DOLLAR_VOL ?= 5000000
MIN_MARKET_CAP ?= 300000000
MIN_PRICE ?= 5
MAX_RET_5D ?= 30
MAX_RET_20D ?= 60
EARNINGS_EXCLUDE_DAYS ?= 2
CANDIDATES_STATUS ?= reports/run_status/candidates-local.json

.DEFAULT_GOAL := help
.PHONY: run restart stop run-bg logs test candidate-preflight candidates-local candidates-rank-local candidates-score-local reversal-test cot cot-data reversal-scan help

run: stop ## Start the dashboard (stops any running instance first), foreground
	$(PY) -m streamlit run app.py --server.port $(PORT) --browser.gatherUsageStats false

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
	$(PY) scripts/test_momentum_options.py
	$(PY) scripts/test_dashboard_navigation.py
	$(PY) scripts/test_hard_filter_yfinance.py
	$(PY) scripts/test_candidate_pipeline_controls.py
	$(PY) scripts/test_rank_candidates.py
	$(PY) scripts/test_llm_score_progress.py
	$(PY) scripts/test_run_status.py
	$(PY) scripts/test_docker_runtime_contract.py
	$(PY) scripts/test_claude_auth_flow.py

candidate-preflight: ## Check local Claude SDK subscription auth for candidate scoring
	$(PY) scripts/llm_client.py --provider claude_agent --model $(CANDIDATE_MODEL)

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

candidates-score-local: candidate-preflight ## Optional LLM deep check for ranked candidates via Claude SDK
		CLAUDE_AGENT_TIMEOUT=$(CLAUDE_AGENT_TIMEOUT) $(PY) scripts/02_llm_score.py \
			--input $(LLM_SCORE_INPUT) \
			--prompt system_prompts/01_surge_screener_prompt.md \
		--min-score $(MIN_SCORE) \
		--provider claude_agent \
		--model $(CANDIDATE_MODEL) \
		--layer1-model $(CANDIDATE_MODEL) \
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

cot: ## Generate the COT/ES weekly report (CFTC+ES=F -> Claude; uses your subscription)
	$(PY) scripts/cot_es.py --model claude-opus-4-8 --output-dir reports/cot

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
	@printf "    %-18s %s\n" "CANDIDATE_MODEL" "Claude SDK model (default: $(CANDIDATE_MODEL))"
	@printf "    %-18s %s\n" "CANDIDATE_LIMIT" "LLM deep-check tickers to score this run (default: $(CANDIDATE_LIMIT))"
	@printf "    %-18s %s\n" "CANDIDATE_RETRIES" "LLM attempts per ticker before defer (default: $(CANDIDATE_RETRIES))"
	@printf "    %-18s %s\n" "CANDIDATE_DEFERRED_RETRIES" "same-run retries for deferred timeouts (default: $(CANDIDATE_DEFERRED_RETRIES))"
	@printf "    %-18s %s\n" "CANDIDATE_SCORING_MODE" "fast=hard-filter-only, full=all enrichment (default: $(CANDIDATE_SCORING_MODE))"
	@printf "    %-18s %s\n" "RESCORE_STALE_LLM" "rescore stale-language LLM rows on resume; 1 enables (default: $(RESCORE_STALE_LLM))"
	@printf "    %-18s %s\n" "LLM_SCORE_INPUT" "LLM input JSON (default: $(LLM_SCORE_INPUT))"
	@printf "    %-18s %s\n" "CLAUDE_AGENT_TIMEOUT" "seconds per Claude Agent call (default: $(CLAUDE_AGENT_TIMEOUT))"
	@printf "    %-18s %s\n" "YF_BATCH_SIZE" "yfinance batch size; lower is slower but more stable (default: $(YF_BATCH_SIZE))"
	@printf "    %-18s %s\n" "MIN_DATA_COVERAGE" "abort floor for yfinance coverage (default: $(MIN_DATA_COVERAGE))"
	@printf "    %-18s %s\n" "MIN_AVG_DOLLAR_VOL" "hard-filter liquidity floor (default: $(MIN_AVG_DOLLAR_VOL))"
	@printf "    %-18s %s\n" "MIN_MARKET_CAP" "hard-filter market-cap floor (default: $(MIN_MARKET_CAP))"
	@printf "    %-18s %s\n" "MIN_PRICE" "hard-filter price floor (default: $(MIN_PRICE))"
	@printf "    %-18s %s\n" "MAX_RET_5D" "hard-filter 5d extension cap percent (default: $(MAX_RET_5D))"
	@printf "    %-18s %s\n" "MAX_RET_20D" "hard-filter 20d extension cap percent (default: $(MAX_RET_20D))"
	@printf "    %-18s %s\n" "EARNINGS_EXCLUDE_DAYS" "hard-filter earnings exclusion window (default: $(EARNINGS_EXCLUDE_DAYS))"
	@printf "    %-18s %s\n" "CANDIDATES_STATUS" "progress JSON path (default: $(CANDIDATES_STATUS))"
