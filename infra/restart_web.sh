#!/usr/bin/env bash
# Restart ONLY the ScrollWise web (Vite dev server) on EC2: stop the running
# server and start a fresh one. Does NOT reinstall deps — for that run
# infra/ec2_app_setup.sh. Binds 127.0.0.1:5173 only; reach it from your laptop
# via infra/tunnel.sh.
#
# Usage:  ./infra/restart_web.sh
set -euo pipefail

if [ -t 2 ]; then RED=$'\033[31m'; RESET=$'\033[0m'; else RED=''; RESET=''; fi
err() { echo "${RED}$*${RESET}" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WEB_DIR="$REPO_ROOT/apps/web"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

if [ ! -d "$WEB_DIR/node_modules" ]; then
  err "!!  apps/web/node_modules not found. Run ./infra/ec2_app_setup.sh first."
  exit 1
fi

echo "==> Stopping web"
[ -f "$LOG_DIR/web.pid" ] && kill "$(cat "$LOG_DIR/web.pid")" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 1

echo "==> Starting web (127.0.0.1:5173)"
( cd "$WEB_DIR" && nohup npm run dev -- --port 5173 --strictPort \
    > "$LOG_DIR/web.log" 2>&1 & echo $! > "$LOG_DIR/web.pid" )

sleep 4
if curl -fsS http://127.0.0.1:5173 >/dev/null 2>&1; then
  echo "    Web: OK  (pid $(cat "$LOG_DIR/web.pid"), log infra/logs/web.log)"
else
  err "!!  Web not responding yet — check infra/logs/web.log"
  exit 1
fi
