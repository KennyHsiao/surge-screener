#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-$HOME/apps/surge-screener}"
APP_PORT="${APP_PORT:-8501}"
APP_SERVICE="${APP_SERVICE:-surge-screener}"
LEGACY_COMPOSE_PROJECT="${LEGACY_COMPOSE_PROJECT:-surge-screener}"
SOURCE_DIR="${GITHUB_WORKSPACE:-$(pwd)}"
RELEASE_DIR="$APP_ROOT/current"
VENV_DIR="$APP_ROOT/.venv"
NODE_DIR="$APP_ROOT/node"
NODE_GLOBAL_DIR="$APP_ROOT/node-global"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SERVICE_SOURCE="$RELEASE_DIR/deploy/surge-screener.service"
SERVICE_TARGET="$SYSTEMD_USER_DIR/${APP_SERVICE}.service"
GET_PIP_URL="${GET_PIP_URL:-https://bootstrap.pypa.io/get-pip.py}"
GET_PIP_FILE="$APP_ROOT/get-pip.py"
NODE_MAJOR="${NODE_MAJOR:-22}"
NODE_PLATFORM="${NODE_PLATFORM:-linux-x64}"
NODE_DIST_BASE="${NODE_DIST_BASE:-https://nodejs.org/dist}"
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$APP_ROOT/.claude}"
SURGE_ANALYTICS_DIR="$APP_ROOT/shared/data"

export SURGE_APP_ROOT="$APP_ROOT"
export SURGE_ANALYTICS_DIR
export CLAUDE_CONFIG_DIR
export PATH="$NODE_GLOBAL_DIR/bin:$NODE_DIR/bin:$PATH"

install_node_runtime() {
  if command -v npm >/dev/null 2>&1; then
    return 0
  fi

  if [ -x "$NODE_DIR/bin/npm" ]; then
    return 0
  fi

  local shasums archive_name node_version archive_path tmp_dir
  shasums="$(curl -fsSL "$NODE_DIST_BASE/latest-v${NODE_MAJOR}.x/SHASUMS256.txt")"
  archive_name="$(
    printf '%s\n' "$shasums" |
      awk -v platform="$NODE_PLATFORM" '$2 ~ ("node-v[0-9].*-" platform "\\.tar\\.xz$") { print $2; exit }'
  )"
  if [ -z "$archive_name" ]; then
    echo "deploy: unable to find Node.js archive for $NODE_PLATFORM" >&2
    exit 1
  fi

  node_version="${archive_name#node-}"
  node_version="${node_version%-${NODE_PLATFORM}.tar.xz}"
  archive_path="$APP_ROOT/$archive_name"
  tmp_dir="$NODE_DIR.tmp"

  curl -fsSL "$NODE_DIST_BASE/$node_version/$archive_name" -o "$archive_path"
  rm -rf "$tmp_dir" "$NODE_DIR"
  mkdir -p "$tmp_dir"
  tar -xJf "$archive_path" --strip-components=1 -C "$tmp_dir"
  mv "$tmp_dir" "$NODE_DIR"
  rm -f "$archive_path"
}

install_claude_cli() {
  mkdir -p "$NODE_GLOBAL_DIR" "$CLAUDE_CONFIG_DIR"
  if command -v claude >/dev/null 2>&1; then
    return 0
  fi

  install_node_runtime
  npm install -g --prefix "$NODE_GLOBAL_DIR" @anthropic-ai/claude-code
  command -v claude >/dev/null 2>&1
}

if [ ! -f "$SOURCE_DIR/app.py" ]; then
  echo "deploy: SOURCE_DIR does not look like surge-screener: $SOURCE_DIR" >&2
  exit 1
fi

if [ ! -f "$SOURCE_DIR/requirements.txt" ]; then
  echo "deploy: missing requirements.txt in $SOURCE_DIR" >&2
  exit 1
fi

mkdir -p "$APP_ROOT" "$RELEASE_DIR" "$SURGE_ANALYTICS_DIR/parquet" "$APP_ROOT/shared/run_status" "$SYSTEMD_USER_DIR" "$CLAUDE_CONFIG_DIR"

rsync -a --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '.playwright-mcp/' \
  --exclude 'reports/.cache/' \
  "$SOURCE_DIR"/ "$RELEASE_DIR"/

mkdir -p "$RELEASE_DIR/reports"
rm -rf "$RELEASE_DIR/reports/run_status"
ln -s "$APP_ROOT/shared/run_status" "$RELEASE_DIR/reports/run_status"

if [ ! -f "$SERVICE_SOURCE" ]; then
  echo "deploy: missing service template: $SERVICE_SOURCE" >&2
  exit 1
fi

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

"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV_DIR/bin/python" -m pip install -r "$RELEASE_DIR/requirements.txt"
install_claude_cli
"$VENV_DIR/bin/python" "$RELEASE_DIR/scripts/analytics_store.py" refresh \
  --reports-dir "$RELEASE_DIR/reports" \
  --analytics-dir "$SURGE_ANALYTICS_DIR"
mkdir -p "$RELEASE_DIR/reports/analytics_checks"
"$VENV_DIR/bin/python" "$RELEASE_DIR/scripts/analytics_checks.py" run \
  --analytics-dir "$SURGE_ANALYTICS_DIR" \
  --output "$RELEASE_DIR/reports/analytics_checks/latest.json" \
  --allow-block

if command -v docker >/dev/null 2>&1 && [ -f "$RELEASE_DIR/docker-compose.yml" ]; then
  docker compose -p "$LEGACY_COMPOSE_PROJECT" down --remove-orphans || true
fi

install -m 0644 "$SERVICE_SOURCE" "$SERVICE_TARGET"
systemctl --user daemon-reload
systemctl --user enable "$APP_SERVICE"
if [ "$APP_SERVICE" = "surge-screener" ]; then
  systemctl --user restart surge-screener
else
  systemctl --user restart "$APP_SERVICE"
fi

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
