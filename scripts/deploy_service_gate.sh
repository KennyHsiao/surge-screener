#!/usr/bin/env bash
set -euo pipefail

API_SERVICE_SOURCE="${API_SERVICE_SOURCE:?deploy gate: API_SERVICE_SOURCE is required}"
API_SERVICE_TARGET="${API_SERVICE_TARGET:?deploy gate: API_SERVICE_TARGET is required}"
PYTHON_BIN="${PYTHON_BIN:?deploy gate: PYTHON_BIN is required}"
API_HEALTH_CHECK="${API_HEALTH_CHECK:?deploy gate: API_HEALTH_CHECK is required}"

API_SERVICE="${API_SERVICE:-surge-screener-api}"
APP_SERVICE="${APP_SERVICE:-surge-screener}"
API_PORT="${API_PORT:-8000}"
APP_PORT="${APP_PORT:-8501}"
API_HEALTH_URL="${API_HEALTH_URL:-http://127.0.0.1:${API_PORT}/healthz}"
STREAMLIT_HEALTH_URL="${STREAMLIT_HEALTH_URL:-http://127.0.0.1:${APP_PORT}/_stcore/health}"
STREAMLIT_ROOT_URL="${STREAMLIT_ROOT_URL:-http://127.0.0.1:${APP_PORT}}"
HEALTH_ATTEMPTS="${HEALTH_ATTEMPTS:-45}"
HEALTH_DELAY="${HEALTH_DELAY:-2}"

run_api_health_check() {
  local main_pid="$1"
  shift

  systemd-run --user --quiet --wait --pipe --collect --service-type=exec \
    "$PYTHON_BIN" "$API_HEALTH_CHECK" \
    "$API_HEALTH_URL" "$main_pid" --host 127.0.0.1 --port "$API_PORT" \
    "$@"
}

api_diagnostics() {
  local main_pid

  systemctl --user status "$API_SERVICE" --no-pager || true
  journalctl --user -u "$API_SERVICE" -n 160 --no-pager || true
  main_pid="$(
    systemctl --user show "$API_SERVICE" --property MainPID --value 2>/dev/null
  )" || return 0
  if [[ "$main_pid" =~ ^[1-9][0-9]*$ ]]; then
    run_api_health_check "$main_pid" --diagnose || true
  fi
}

streamlit_diagnostics() {
  systemctl --user status "$APP_SERVICE" --no-pager || true
  journalctl --user -u "$APP_SERVICE" -n 160 --no-pager || true
}

api_lifecycle_failure() {
  local stage="$1"
  echo "deploy: API service failed during $stage" >&2
  api_diagnostics
}

streamlit_lifecycle_failure() {
  local stage="$1"
  echo "deploy: Streamlit service failed during $stage" >&2
  streamlit_diagnostics
}

valid_settings() {
  [[ "$API_PORT" == "8000" ]] \
    && [[ "$HEALTH_ATTEMPTS" =~ ^[1-9][0-9]*$ ]] \
    && [[ "$HEALTH_DELAY" =~ ^[0-9]+([.][0-9]+)?$ ]]
}

api_service_ready() {
  local main_pid_before main_pid_after

  systemctl --user is-active --quiet "$API_SERVICE" || return 1
  main_pid_before="$(
    systemctl --user show "$API_SERVICE" --property MainPID --value 2>/dev/null
  )" || return 1
  [[ "$main_pid_before" =~ ^[1-9][0-9]*$ ]] || return 1

  run_api_health_check "$main_pid_before" || return 1

  main_pid_after="$(
    systemctl --user show "$API_SERVICE" --property MainPID --value 2>/dev/null
  )" || return 1
  systemctl --user is-active --quiet "$API_SERVICE" || return 1
  [[ "$main_pid_after" == "$main_pid_before" ]]
}

wait_for_api() {
  local attempt
  for ((attempt = 1; attempt <= HEALTH_ATTEMPTS; attempt += 1)); do
    if api_service_ready; then
      return 0
    fi
    if ((attempt < HEALTH_ATTEMPTS)); then
      sleep "$HEALTH_DELAY"
    fi
  done
  return 1
}

wait_for_streamlit() {
  local attempt
  for ((attempt = 1; attempt <= HEALTH_ATTEMPTS; attempt += 1)); do
    if curl --noproxy '*' -fsS "$STREAMLIT_HEALTH_URL" >/dev/null \
      || curl --noproxy '*' -fsS "$STREAMLIT_ROOT_URL" >/dev/null; then
      return 0
    fi
    if ((attempt < HEALTH_ATTEMPTS)); then
      sleep "$HEALTH_DELAY"
    fi
  done
  return 1
}

main() {
  if ! valid_settings; then
    echo "deploy: invalid service-gate settings" >&2
    return 1
  fi

  if ! install -m 0644 "$API_SERVICE_SOURCE" "$API_SERVICE_TARGET"; then
    api_lifecycle_failure "unit install"
    return 1
  fi
  if ! systemctl --user daemon-reload; then
    api_lifecycle_failure "daemon reload"
    return 1
  fi
  if ! systemctl --user enable "$API_SERVICE"; then
    api_lifecycle_failure "enable"
    return 1
  fi
  if ! systemctl --user restart "$API_SERVICE"; then
    api_lifecycle_failure "restart"
    return 1
  fi
  if ! wait_for_api; then
    api_lifecycle_failure "health verification"
    return 1
  fi
  echo "deploy: API service is healthy on $API_HEALTH_URL"

  if ! systemctl --user restart "$APP_SERVICE"; then
    streamlit_lifecycle_failure "restart"
    return 1
  fi
  if ! wait_for_streamlit; then
    streamlit_lifecycle_failure "health verification"
    return 1
  fi
  echo "deploy: Streamlit app is healthy on $STREAMLIT_ROOT_URL"
  echo "deploy: both Streamlit and loopback API services are healthy"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
