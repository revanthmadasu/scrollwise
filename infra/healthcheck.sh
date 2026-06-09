#!/usr/bin/env bash
# Health check for the content-generator service on EC2: the systemd drain
# worker plus the generation queue / DB. Exit 0 = healthy, 1 = unhealthy
# (suitable for cron or an external monitor).
#
# Usage:  ./infra/healthcheck.sh
set -uo pipefail

if [ -t 2 ]; then RED=$'\033[31m'; GREEN=$'\033[32m'; RESET=$'\033[0m'; else RED=''; GREEN=''; RESET=''; fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GEN_DIR="$REPO_ROOT/services/content-generator"
SERVICE="scrollwise-drain"
rc=0

# 1. systemd worker state.
if systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE}.service"; then
  if systemctl is-active --quiet "$SERVICE"; then
    echo "${GREEN}worker: active${RESET}  ($SERVICE)"
  else
    echo "${RED}worker: NOT active${RESET}  ($SERVICE)"
    rc=1
  fi
  echo "recent logs:"
  journalctl -u "$SERVICE" -n 5 --no-pager 2>/dev/null | sed 's/^/  /' || true
else
  echo "${RED}worker: not installed${RESET} — run ./infra/ec2_drain_setup.sh"
  rc=1
fi

echo ""

# 2. Queue + DB health (works even if the worker isn't installed).
if [ -x "$GEN_DIR/.venv/bin/python" ]; then
  ( cd "$GEN_DIR" && .venv/bin/python -m scripts.health ) || rc=1
else
  echo "${RED}generator venv missing${RESET} — run ./infra/ec2_drain_setup.sh"
  rc=1
fi

echo ""
[ "$rc" -eq 0 ] && echo "${GREEN}OVERALL: healthy${RESET}" || echo "${RED}OVERALL: unhealthy${RESET}"
exit $rc
