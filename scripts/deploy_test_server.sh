#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-$HOME/apps/surge-screener}"
APP_PORT="${APP_PORT:-8501}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-surge-screener}"
SOURCE_DIR="${GITHUB_WORKSPACE:-$(pwd)}"
RELEASE_DIR="$APP_ROOT/current"

if [ ! -f "$SOURCE_DIR/app.py" ]; then
  echo "deploy: SOURCE_DIR does not look like surge-screener: $SOURCE_DIR" >&2
  exit 1
fi

if [ ! -f "$SOURCE_DIR/docker-compose.yml" ]; then
  echo "deploy: missing docker-compose.yml in $SOURCE_DIR" >&2
  exit 1
fi

if [ ! -f "$SOURCE_DIR/Dockerfile" ]; then
  echo "deploy: missing Dockerfile in $SOURCE_DIR" >&2
  exit 1
fi

mkdir -p "$APP_ROOT" "$RELEASE_DIR"

rsync -a --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '.playwright-mcp/' \
  --exclude 'reports/.cache/' \
  "$SOURCE_DIR"/ "$RELEASE_DIR"/

if systemctl --user list-unit-files | grep -q '^surge-screener\.service'; then
  systemctl --user disable --now surge-screener.service || true
fi

cd "$RELEASE_DIR"
docker compose -p "$COMPOSE_PROJECT" up -d --build --remove-orphans

health_url="http://127.0.0.1:${APP_PORT}/_stcore/health"
root_url="http://127.0.0.1:${APP_PORT}"

for _ in $(seq 1 45); do
  if curl -fsS "$health_url" >/dev/null || curl -fsS "$root_url" >/dev/null; then
    echo "deploy: Docker app is healthy on $root_url"
    exit 0
  fi
  sleep 2
done

echo "deploy: Docker app did not become healthy" >&2
docker compose -p "$COMPOSE_PROJECT" ps || true
docker compose -p "$COMPOSE_PROJECT" logs --tail=160 || true
exit 1
