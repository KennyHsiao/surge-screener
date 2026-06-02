# Quant Radar — dev tasks.  Usage: `make <target>` (run `make` for the list).
PY   := .venv/bin/python
PORT ?= 8501

.DEFAULT_GOAL := help
.PHONY: run restart stop run-bg logs test help

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

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*## "}{printf "  \033[36m%-9s\033[0m %s\n", $$1, $$2}'
