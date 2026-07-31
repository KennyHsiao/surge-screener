#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-$HOME/apps/surge-screener}"
APP_PORT="${APP_PORT:-8501}"
APP_SERVICE="${APP_SERVICE:-surge-screener}"
LEGACY_COMPOSE_PROJECT="${LEGACY_COMPOSE_PROJECT:-surge-screener}"
SOURCE_DIR="${GITHUB_WORKSPACE:-$(pwd)}"
RELEASE_DIR="$APP_ROOT/current"
VENV_DIR="$APP_ROOT/.venv"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SERVICE_SOURCE="$RELEASE_DIR/deploy/surge-screener.service"
SERVICE_TARGET="$SYSTEMD_USER_DIR/${APP_SERVICE}.service"
REFRESH_SERVICES=(
  surge-candidate-refresh.service
  surge-data-health-refresh.service
  surge-theme-flow-refresh.service
)
REFRESH_TIMERS=(
  surge-candidate-refresh.timer
  surge-data-health-refresh.timer
  surge-theme-flow-refresh.timer
)
GET_PIP_URL="${GET_PIP_URL:-https://bootstrap.pypa.io/get-pip.py}"
GET_PIP_FILE="$APP_ROOT/get-pip.py"
CODEX_HOME="${CODEX_HOME:-$APP_ROOT/.codex}"
AGENT_REACH_INSTALL_SOURCE="${AGENT_REACH_INSTALL_SOURCE:-https://github.com/Panniantong/agent-reach/archive/main.zip}"
AGENT_REACH_CHANNELS="${AGENT_REACH_CHANNELS:-twitter}"
TWITTER_CLI_PACKAGE="${TWITTER_CLI_PACKAGE:-twitter-cli}"
SURGE_ANALYTICS_DIR="$APP_ROOT/shared/data"
SURGE_CANDIDATE_OUTPUT_DIR="$APP_ROOT/shared/candidates"
SURGE_AI_CHAT_DIR="$APP_ROOT/shared/ai_chat_sessions"
SURGE_SOCIAL_INTELLIGENCE_DIR="$APP_ROOT/shared/social_intelligence"
SURGE_INFLUENCERS_PATH="$APP_ROOT/shared/content/influencers.json"
RUN_SOURCE_REFRESH="${RUN_SOURCE_REFRESH:-0}"
SOURCE_REFRESH_TIMEOUT_SECONDS="${SOURCE_REFRESH_TIMEOUT_SECONDS:-300}"
RUN_ANALYTICS_REFRESH="${RUN_ANALYTICS_REFRESH:-0}"
ANALYTICS_REFRESH_TIMEOUT_SECONDS="${ANALYTICS_REFRESH_TIMEOUT_SECONDS:-600}"

export SURGE_APP_ROOT="$APP_ROOT"
export SURGE_ANALYTICS_DIR
export SURGE_CANDIDATE_OUTPUT_DIR
export SURGE_AI_CHAT_DIR
export SURGE_INFLUENCERS_PATH
export CODEX_HOME
export PATH="$VENV_DIR/bin:$PATH"

install_agent_reach_cli() {
  if [ -x "$VENV_DIR/bin/agent-reach" ] && [ -x "$VENV_DIR/bin/twitter" ]; then
    return 0
  fi

  if ! "$VENV_DIR/bin/python" -m pip install --upgrade "$AGENT_REACH_INSTALL_SOURCE"; then
    echo "deploy: Agent Reach install failed; continuing with degraded X fallback" >&2
  fi

  if ! "$VENV_DIR/bin/python" -m pip install --upgrade "$TWITTER_CLI_PACKAGE"; then
    echo "deploy: twitter-cli install failed; continuing with degraded X fallback" >&2
  fi

  if [ -x "$VENV_DIR/bin/agent-reach" ] \
    && ! "$VENV_DIR/bin/agent-reach" install --env=auto --channels="$AGENT_REACH_CHANNELS"; then
    echo "deploy: Agent Reach channel install failed; continuing with degraded X fallback" >&2
  fi
}

if [ ! -f "$SOURCE_DIR/app.py" ]; then
  echo "deploy: SOURCE_DIR does not look like surge-screener: $SOURCE_DIR" >&2
  exit 1
fi

if [ ! -f "$SOURCE_DIR/requirements.txt" ]; then
  echo "deploy: missing requirements.txt in $SOURCE_DIR" >&2
  exit 1
fi

mkdir -p \
  "$APP_ROOT" \
  "$RELEASE_DIR" \
  "$SURGE_ANALYTICS_DIR/parquet" \
  "$SURGE_CANDIDATE_OUTPUT_DIR" \
  "$SURGE_AI_CHAT_DIR" \
  "$SURGE_SOCIAL_INTELLIGENCE_DIR" \
  "$APP_ROOT/shared/run_status" \
  "$APP_ROOT/shared/analytics_checks" \
  "$APP_ROOT/shared/candidate_rankings" \
  "$APP_ROOT/shared/risk_guard" \
  "$APP_ROOT/shared/theme_flow_snapshots" \
  "$APP_ROOT/shared/sector_rotation_snapshots" \
  "$APP_ROOT/shared/universe" \
  "$APP_ROOT/shared/market_data/daily_bars" \
  "$APP_ROOT/shared/money_flow" \
  "$APP_ROOT/shared/trade_state" \
  "$APP_ROOT/shared/industry_roles" \
  "$APP_ROOT/shared/fundamentals" \
  "$APP_ROOT/shared/iv_history" \
  "$APP_ROOT/shared/social_intelligence_outcomes" \
  "$APP_ROOT/shared/content" \
  "$SYSTEMD_USER_DIR" \
  "$CODEX_HOME"

if [ -f "$RELEASE_DIR/reports/reconciliation.json" ] && [ ! -f "$APP_ROOT/shared/reconciliation.json" ]; then
  cp "$RELEASE_DIR/reports/reconciliation.json" "$APP_ROOT/shared/reconciliation.json"
fi
if [ -f "$RELEASE_DIR/reports/theme_flow_snapshot.json" ] && [ ! -f "$APP_ROOT/shared/theme_flow_snapshot.json" ]; then
  cp "$RELEASE_DIR/reports/theme_flow_snapshot.json" "$APP_ROOT/shared/theme_flow_snapshot.json"
fi
if [ -f "$RELEASE_DIR/reports/sector_rotation.json" ] && [ ! -f "$APP_ROOT/shared/sector_rotation.json" ]; then
  cp "$RELEASE_DIR/reports/sector_rotation.json" "$APP_ROOT/shared/sector_rotation.json"
fi
if [ -d "$RELEASE_DIR/reports/social_intelligence" ] && [ -z "$(find "$SURGE_SOCIAL_INTELLIGENCE_DIR" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/social_intelligence/." "$SURGE_SOCIAL_INTELLIGENCE_DIR/"
fi
if [ -d "$RELEASE_DIR/reports/analytics_checks" ] && [ -z "$(find "$APP_ROOT/shared/analytics_checks" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/analytics_checks/." "$APP_ROOT/shared/analytics_checks/"
fi
if [ -d "$RELEASE_DIR/reports/fundamentals" ] && [ -z "$(find "$APP_ROOT/shared/fundamentals" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/fundamentals/." "$APP_ROOT/shared/fundamentals/"
fi
if [ -d "$RELEASE_DIR/reports/iv_history" ] && [ -z "$(find "$APP_ROOT/shared/iv_history" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/iv_history/." "$APP_ROOT/shared/iv_history/"
fi
if [ -d "$RELEASE_DIR/reports/social_intelligence_outcomes" ] && [ -z "$(find "$APP_ROOT/shared/social_intelligence_outcomes" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/social_intelligence_outcomes/." "$APP_ROOT/shared/social_intelligence_outcomes/"
fi
if [ -f "$RELEASE_DIR/reports/x_influencer_picks.json" ] && [ ! -f "$APP_ROOT/shared/x_influencer_picks.json" ]; then
  cp "$RELEASE_DIR/reports/x_influencer_picks.json" "$APP_ROOT/shared/x_influencer_picks.json"
fi

for artifact in filtered_universe.json ranked_candidates.json scored_candidates.json layer2_results.json dd_results.json; do
  if [ -f "$RELEASE_DIR/$artifact" ] && [ ! -f "$SURGE_CANDIDATE_OUTPUT_DIR/$artifact" ]; then
    cp "$RELEASE_DIR/$artifact" "$SURGE_CANDIDATE_OUTPUT_DIR/$artifact"
  fi
done

rsync -a --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '.playwright-mcp/' \
  --exclude 'reports/.cache/' \
  "$SOURCE_DIR"/ "$RELEASE_DIR"/

mkdir -p "$RELEASE_DIR/reports"
if [ -f "$RELEASE_DIR/reports/sector_rotation.json" ] && [ ! -f "$APP_ROOT/shared/sector_rotation.json" ]; then
  cp "$RELEASE_DIR/reports/sector_rotation.json" "$APP_ROOT/shared/sector_rotation.json"
fi
if [ -d "$RELEASE_DIR/reports/sector_rotation_snapshots" ] && [ -z "$(find "$APP_ROOT/shared/sector_rotation_snapshots" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/sector_rotation_snapshots/." "$APP_ROOT/shared/sector_rotation_snapshots/"
fi
if [ -d "$RELEASE_DIR/reports/universe" ] && [ -z "$(find "$APP_ROOT/shared/universe" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/universe/." "$APP_ROOT/shared/universe/"
fi
if [ -d "$RELEASE_DIR/reports/market_data/daily_bars" ] && [ -z "$(find "$APP_ROOT/shared/market_data/daily_bars" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/market_data/daily_bars/." "$APP_ROOT/shared/market_data/daily_bars/"
fi
if [ -d "$RELEASE_DIR/reports/money_flow" ] && [ -z "$(find "$APP_ROOT/shared/money_flow" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/money_flow/." "$APP_ROOT/shared/money_flow/"
fi
if [ -d "$RELEASE_DIR/reports/trade_state" ] && [ -z "$(find "$APP_ROOT/shared/trade_state" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/trade_state/." "$APP_ROOT/shared/trade_state/"
fi
if [ -d "$RELEASE_DIR/reports/industry_roles" ] && [ -z "$(find "$APP_ROOT/shared/industry_roles" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/industry_roles/." "$APP_ROOT/shared/industry_roles/"
fi
if [ -d "$RELEASE_DIR/reports/social_intelligence" ] && [ -z "$(find "$SURGE_SOCIAL_INTELLIGENCE_DIR" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/social_intelligence/." "$SURGE_SOCIAL_INTELLIGENCE_DIR/"
fi
if [ -d "$RELEASE_DIR/reports/analytics_checks" ] && [ -z "$(find "$APP_ROOT/shared/analytics_checks" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/analytics_checks/." "$APP_ROOT/shared/analytics_checks/"
fi
if [ -d "$RELEASE_DIR/reports/fundamentals" ] && [ -z "$(find "$APP_ROOT/shared/fundamentals" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/fundamentals/." "$APP_ROOT/shared/fundamentals/"
fi
if [ -d "$RELEASE_DIR/reports/iv_history" ] && [ -z "$(find "$APP_ROOT/shared/iv_history" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/iv_history/." "$APP_ROOT/shared/iv_history/"
fi
if [ -d "$RELEASE_DIR/reports/social_intelligence_outcomes" ] && [ -z "$(find "$APP_ROOT/shared/social_intelligence_outcomes" -mindepth 1 -print -quit)" ]; then
  cp -a "$RELEASE_DIR/reports/social_intelligence_outcomes/." "$APP_ROOT/shared/social_intelligence_outcomes/"
fi
if [ -f "$RELEASE_DIR/reports/x_influencer_picks.json" ] && [ ! -f "$APP_ROOT/shared/x_influencer_picks.json" ]; then
  cp "$RELEASE_DIR/reports/x_influencer_picks.json" "$APP_ROOT/shared/x_influencer_picks.json"
fi
if [ -f "$RELEASE_DIR/content/influencers.json" ] && [ ! -f "$SURGE_INFLUENCERS_PATH" ]; then
  cp "$RELEASE_DIR/content/influencers.json" "$SURGE_INFLUENCERS_PATH"
fi
rm -rf "$RELEASE_DIR/reports/run_status"
ln -s "$APP_ROOT/shared/run_status" "$RELEASE_DIR/reports/run_status"
rm -rf "$RELEASE_DIR/reports/candidate_rankings"
ln -s "$APP_ROOT/shared/candidate_rankings" "$RELEASE_DIR/reports/candidate_rankings"
rm -rf "$RELEASE_DIR/reports/risk_guard"
ln -s "$APP_ROOT/shared/risk_guard" "$RELEASE_DIR/reports/risk_guard"
ln -sfn "$APP_ROOT/shared/reconciliation.json" "$RELEASE_DIR/reports/reconciliation.json"
rm -rf "$RELEASE_DIR/reports/theme_flow_snapshots"
ln -s "$APP_ROOT/shared/theme_flow_snapshots" "$RELEASE_DIR/reports/theme_flow_snapshots"
ln -sfn "$APP_ROOT/shared/theme_flow_snapshot.json" "$RELEASE_DIR/reports/theme_flow_snapshot.json"
rm -rf "$RELEASE_DIR/reports/sector_rotation_snapshots"
ln -s "$APP_ROOT/shared/sector_rotation_snapshots" "$RELEASE_DIR/reports/sector_rotation_snapshots"
ln -sfn "$APP_ROOT/shared/sector_rotation.json" "$RELEASE_DIR/reports/sector_rotation.json"
rm -rf "$RELEASE_DIR/reports/universe"
ln -s "$APP_ROOT/shared/universe" "$RELEASE_DIR/reports/universe"
mkdir -p "$RELEASE_DIR/reports/market_data"
rm -rf "$RELEASE_DIR/reports/market_data/daily_bars"
ln -s "$APP_ROOT/shared/market_data/daily_bars" "$RELEASE_DIR/reports/market_data/daily_bars"
rm -rf "$RELEASE_DIR/reports/money_flow"
ln -s "$APP_ROOT/shared/money_flow" "$RELEASE_DIR/reports/money_flow"
rm -rf "$RELEASE_DIR/reports/trade_state"
ln -s "$APP_ROOT/shared/trade_state" "$RELEASE_DIR/reports/trade_state"
rm -rf "$RELEASE_DIR/reports/industry_roles"
ln -s "$APP_ROOT/shared/industry_roles" "$RELEASE_DIR/reports/industry_roles"
rm -rf "$RELEASE_DIR/reports/social_intelligence"
ln -s "$SURGE_SOCIAL_INTELLIGENCE_DIR" "$RELEASE_DIR/reports/social_intelligence"
rm -rf "$RELEASE_DIR/reports/analytics_checks"
ln -s "$APP_ROOT/shared/analytics_checks" "$RELEASE_DIR/reports/analytics_checks"
rm -rf "$RELEASE_DIR/reports/fundamentals"
ln -s "$APP_ROOT/shared/fundamentals" "$RELEASE_DIR/reports/fundamentals"
rm -rf "$RELEASE_DIR/reports/iv_history"
ln -s "$APP_ROOT/shared/iv_history" "$RELEASE_DIR/reports/iv_history"
rm -rf "$RELEASE_DIR/reports/social_intelligence_outcomes"
ln -s "$APP_ROOT/shared/social_intelligence_outcomes" "$RELEASE_DIR/reports/social_intelligence_outcomes"
ln -sfn "$APP_ROOT/shared/x_influencer_picks.json" "$RELEASE_DIR/reports/x_influencer_picks.json"
ln -sfn "$SURGE_INFLUENCERS_PATH" "$RELEASE_DIR/content/influencers.json"
for artifact in filtered_universe.json ranked_candidates.json scored_candidates.json layer2_results.json dd_results.json; do
  ln -sfn "$SURGE_CANDIDATE_OUTPUT_DIR/$artifact" "$RELEASE_DIR/$artifact"
done

if [ ! -f "$SERVICE_SOURCE" ]; then
  echo "deploy: missing service template: $SERVICE_SOURCE" >&2
  exit 1
fi
for unit in "${REFRESH_SERVICES[@]}" "${REFRESH_TIMERS[@]}"; do
  if [ ! -f "$RELEASE_DIR/deploy/$unit" ]; then
    echo "deploy: missing refresh unit template: $RELEASE_DIR/deploy/$unit" >&2
    exit 1
  fi
done

if [ ! -x "$VENV_DIR/bin/python" ]; then
  if ! python3 -m venv "$VENV_DIR"; then
    echo "deploy: ensurepip unavailable; creating venv without pip" >&2
    python3 -m venv --without-pip "$VENV_DIR"
  fi
fi

if ! "$VENV_DIR/bin/python" -m pip --version >/dev/null 2>&1; then
  curl -fsSL "$GET_PIP_URL" -o "$GET_PIP_FILE"
  "$VENV_DIR/bin/python" "$GET_PIP_FILE"
  rm -f "$GET_PIP_FILE"
fi

requirements_hash="$(
  {
    sha256sum "$RELEASE_DIR/requirements.txt"
    if [ -f "$RELEASE_DIR/requirements-ibkr.txt" ]; then
      sha256sum "$RELEASE_DIR/requirements-ibkr.txt"
    fi
  } | sha256sum | awk '{print $1}'
)"
requirements_stamp="$APP_ROOT/.requirements.sha256"
installed_hash="$(cat "$requirements_stamp" 2>/dev/null || true)"
if [ "$requirements_hash" != "$installed_hash" ]; then
  "$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
  "$VENV_DIR/bin/python" -m pip install -r "$RELEASE_DIR/requirements.txt"
  if [ -f "$RELEASE_DIR/requirements-ibkr.txt" ]; then
    "$VENV_DIR/bin/python" -m pip install -r "$RELEASE_DIR/requirements-ibkr.txt"
  fi
  printf '%s\n' "$requirements_hash" > "$requirements_stamp"
else
  echo "deploy: Python requirements unchanged; skipping dependency install"
fi
"$VENV_DIR/bin/python" -c "import openai_codex"
install_agent_reach_cli
case "$RUN_SOURCE_REFRESH" in
  1|true|TRUE|yes|YES)
    source_refresh_cmd=(
      "$VENV_DIR/bin/python" "$RELEASE_DIR/scripts/data_source_refresh.py"
      --reports-dir "$RELEASE_DIR/reports"
      --content-dir "$RELEASE_DIR/content"
      --analytics-dir "$SURGE_ANALYTICS_DIR"
      --checks-output "$RELEASE_DIR/reports/analytics_checks/latest.json"
      --include-supplemental
      --supplemental-limit 10
      --json
    )
    echo "deploy: refreshing source artifacts (timeout ${SOURCE_REFRESH_TIMEOUT_SECONDS}s)"
    if command -v timeout >/dev/null 2>&1; then
      if ! timeout "$SOURCE_REFRESH_TIMEOUT_SECONDS" "${source_refresh_cmd[@]}"; then
        echo "deploy: source refresh failed or timed out; keeping the last good analytics" >&2
      fi
    elif ! "${source_refresh_cmd[@]}"; then
      echo "deploy: source refresh failed; keeping the last good analytics" >&2
    fi
    ;;
  *)
    echo "deploy: skipping source artifact refresh (RUN_SOURCE_REFRESH=$RUN_SOURCE_REFRESH)"
    ;;
esac
case "$RUN_ANALYTICS_REFRESH" in
  1|true|TRUE|yes|YES)
    analytics_refresh_cmd=(
      "$VENV_DIR/bin/python" "$RELEASE_DIR/scripts/analytics_store.py" refresh
      --reports-dir "$RELEASE_DIR/reports"
      --analytics-dir "$SURGE_ANALYTICS_DIR"
    )
    echo "deploy: rebuilding Analytics DB (timeout ${ANALYTICS_REFRESH_TIMEOUT_SECONDS}s)"
    analytics_refresh_ok=1
    if command -v timeout >/dev/null 2>&1; then
      if ! timeout "$ANALYTICS_REFRESH_TIMEOUT_SECONDS" "${analytics_refresh_cmd[@]}"; then
        analytics_refresh_ok=0
      fi
    elif ! "${analytics_refresh_cmd[@]}"; then
      analytics_refresh_ok=0
    fi
    if [ "$analytics_refresh_ok" -eq 1 ]; then
      mkdir -p "$RELEASE_DIR/reports/analytics_checks"
      "$VENV_DIR/bin/python" "$RELEASE_DIR/scripts/analytics_checks.py" run \
        --analytics-dir "$SURGE_ANALYTICS_DIR" \
        --output "$RELEASE_DIR/reports/analytics_checks/latest.json" \
        --allow-block
      if ! "$VENV_DIR/bin/python" "$RELEASE_DIR/scripts/continuation_strength.py" \
        --features "$RELEASE_DIR/reports/retrospective/surge_features.json" \
        --reports-dir "$RELEASE_DIR/reports" \
        --analytics-dir "$SURGE_ANALYTICS_DIR" \
        --output "$RELEASE_DIR/reports/retrospective/continuation_strength.json"; then
        echo "deploy: continuation-strength validation failed; continuing with app restart" >&2
      fi
    else
      echo "deploy: Analytics DB rebuild failed or timed out; keeping the last good DB" >&2
    fi
    ;;
  *)
    echo "deploy: skipping Analytics DB rebuild (RUN_ANALYTICS_REFRESH=$RUN_ANALYTICS_REFRESH)"
    ;;
esac

if command -v docker >/dev/null 2>&1 && [ -f "$RELEASE_DIR/docker-compose.yml" ]; then
  docker compose -p "$LEGACY_COMPOSE_PROJECT" down --remove-orphans || true
fi

install -m 0644 "$SERVICE_SOURCE" "$SERVICE_TARGET"
for unit in "${REFRESH_SERVICES[@]}" "${REFRESH_TIMERS[@]}"; do
  install -m 0644 "$RELEASE_DIR/deploy/$unit" "$SYSTEMD_USER_DIR/$unit"
done
systemctl --user daemon-reload
systemctl --user enable "$APP_SERVICE"
systemctl --user enable --now "${REFRESH_TIMERS[@]}"
if [ "$APP_SERVICE" = "surge-screener" ]; then
  systemctl --user restart surge-screener
else
  systemctl --user restart "$APP_SERVICE"
fi
for timer in "${REFRESH_TIMERS[@]}"; do
  systemctl --user is-enabled --quiet "$timer"
  systemctl --user is-active --quiet "$timer"
done

health_url="http://127.0.0.1:${APP_PORT}/_stcore/health"
root_url="http://127.0.0.1:${APP_PORT}"

for _ in $(seq 1 45); do
  if curl -fsS "$health_url" >/dev/null || curl -fsS "$root_url" >/dev/null; then
    echo "deploy: Streamlit app is healthy on $root_url"
    exit 0
  fi
  sleep 2
done

echo "deploy: Streamlit app did not become healthy" >&2
systemctl --user status "$APP_SERVICE" --no-pager || true
journalctl --user -u "$APP_SERVICE" -n 160 --no-pager || true
exit 1
