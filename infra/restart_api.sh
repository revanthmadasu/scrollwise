#!/usr/bin/env bash
# Restart ONLY the ScrollWise API on EC2: stop the running uvicorn and start a
# fresh one. Does NOT reinstall deps or rewrite .env — for that run
# infra/ec2_app_setup.sh. Binds 127.0.0.1 only; reach it from your laptop via
# infra/tunnel.sh.
#
# Usage:  ./infra/restart_api.sh
set -euo pipefail

if [ -t 2 ]; then RED=$'\033[31m'; RESET=$'\033[0m'; else RED=''; RESET=''; fi
err() { echo "${RED}$*${RESET}" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_DIR="$REPO_ROOT/apps/api"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

if [ ! -x "$API_DIR/.venv/bin/python" ]; then
  err "!!  apps/api/.venv not found. Run ./infra/ec2_app_setup.sh first."
  exit 1
fi

echo "==> Stopping API"
[ -f "$LOG_DIR/api.pid" ] && kill "$(cat "$LOG_DIR/api.pid")" 2>/dev/null || true
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 1

echo "==> Starting API (127.0.0.1:8000)"
( cd "$API_DIR" && nohup .venv/bin/python -m uvicorn app.main:app \
    --host 127.0.0.1 --port 8000 > "$LOG_DIR/api.log" 2>&1 & echo $! > "$LOG_DIR/api.pid" )

sleep 4
if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "    API health: OK  (pid $(cat "$LOG_DIR/api.pid"), log infra/logs/api.log)"
else
  err "!!  API not responding yet — check infra/logs/api.log"
  exit 1
fi
