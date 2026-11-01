#!/usr/bin/env bash
# Update TheChef to the latest commit, but only if the tests pass.
# Usage:  cd ~/apps/the_chef && bash deploy/deploy.sh
#
# Steps: git pull -> uv sync -> pytest -> restart -> health check.
# If tests or the health check fail, it rolls back to the previous commit.
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${THECHEF_PORT:-8010}"
SERVICE="thechef.service"
export PATH="$HOME/.local/bin:$PATH"
cd "$APP_DIR"

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "Uncommitted changes in $APP_DIR - commit or discard them first:"
  git status --short --untracked-files=no
  exit 1
fi

OLD="$(git rev-parse HEAD)"
rollback() {
  echo "==> Rolling back to ${OLD:0:7}"
  git reset --hard -q "$OLD"
  uv sync --frozen -q
  [ "${1:-}" = "restart" ] && systemctl --user restart "$SERVICE"
  return 0
}

echo "==> Pulling $(git rev-parse --abbrev-ref HEAD)"
git pull --ff-only -q
NEW="$(git rev-parse HEAD)"
if [ "$OLD" = "$NEW" ]; then
  echo "Already up to date (${NEW:0:7}). Nothing to deploy."
  exit 0
fi
git log --oneline "$OLD..$NEW"

echo "==> Installing dependencies"
uv sync --frozen -q

echo "==> Running tests"
if ! uv run --frozen pytest -q; then
  echo "Tests failed - not deploying. The running app was not touched."
  rollback
  exit 1
fi

echo "==> Restarting $SERVICE"
systemctl --user restart "$SERVICE"

echo -n "==> Health check: "
for _ in $(seq 1 20); do
  if curl -fs "http://127.0.0.1:$PORT/healthz" >/dev/null; then
    echo "ok"
    echo "Deployed ${OLD:0:7} -> ${NEW:0:7}"
    exit 0
  fi
  sleep 0.5
done

echo "FAILED"
journalctl --user -u "$SERVICE" -n 20 --no-pager || true
rollback restart
exit 1
