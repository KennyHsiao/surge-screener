#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-$HOME/apps/surge-screener}"
APP_PORT="${APP_PORT:-8501}"
APP_SERVICE="${APP_SERVICE:-surge-screener}"
SOURCE_DIR="${GITHUB_WORKSPACE:-$(pwd)}"
RELEASE_DIR="$APP_ROOT/current"
VENV_DIR="$APP_ROOT/.venv"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SERVICE_SOURCE="$SOURCE_DIR/deploy/surge-screener.service"
SERVICE_TARGET="$SYSTEMD_USER_DIR/$APP_SERVICE.service"

if [ ! -f "$SOURCE_DIR/app.py" ]; then
  echo "deploy: SOURCE_DIR does not look like surge-screener: $SOURCE_DIR" >&2
  exit 1
fi

if [ ! -f "$SERVICE_SOURCE" ]; then
  echo "deploy: missing service template: $SERVICE_SOURCE" >&2
  exit 1
fi

mkdir -p "$APP_ROOT" "$RELEASE_DIR" "$SYSTEMD_USER_DIR"

rsync -a --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '.playwright-mcp/' \
  --exclude 'reports/.cache/' \
  "$SOURCE_DIR"/ "$RELEASE_DIR"/

if [ ! -x "$VENV_DIR/bin/python" ]; then
  python3 -m venv "$VENV_DIR"
fi

if ! "$VENV_DIR/bin/python" -m pip --version >/dev/null 2>&1; then
  curl -fsSL https://bootstrap.pypa.io/get-pip.py -o "$APP_ROOT/get-pip.py"
  "$VENV_DIR/bin/python" "$APP_ROOT/get-pip.py"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV_DIR/bin/python" -m pip install -r "$RELEASE_DIR/requirements.txt"

cp "$SERVICE_SOURCE" "$SERVICE_TARGET"
systemctl --user daemon-reload
systemctl --user enable "$APP_SERVICE"
systemctl --user restart "$APP_SERVICE"

health_url="http://127.0.0.1:${APP_PORT}/_stcore/health"
root_url="http://127.0.0.1:${APP_PORT}"

for _ in $(seq 1 45); do
  if curl -fsS "$health_url" >/dev/null || curl -fsS "$root_url" >/dev/null; then
    echo "deploy: $APP_SERVICE is healthy on $root_url"
    exit 0
  fi
  sleep 2
done

echo "deploy: $APP_SERVICE did not become healthy" >&2
systemctl --user status "$APP_SERVICE" --no-pager || true
journalctl --user -u "$APP_SERVICE" -n 120 --no-pager || true
exit 1
