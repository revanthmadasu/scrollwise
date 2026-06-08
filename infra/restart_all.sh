#!/usr/bin/env bash
# Restart EVERYTHING on EC2: API, web, and the prompt-drain worker.
#
# API + web are nohup processes (restart_api.sh / restart_web.sh); the drain
# worker is a systemd service (scrollwise-drain), so it restarts via systemctl.
# Runs all three even if one fails, then reports. Does NOT reinstall deps —
# use ec2_app_setup.sh / ec2_drain_setup.sh for that.
#
# Usage:  ./infra/restart_all.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -t 2 ]; then RED=$'\033[31m'; RESET=$'\033[0m'; else RED=''; RESET=''; fi
SERVICE="scrollwise-drain"

api_rc=0; web_rc=0; drain_rc=0

"$SCRIPT_DIR/restart_api.sh" || api_rc=$?
echo ""
"$SCRIPT_DIR/restart_web.sh" || web_rc=$?
echo ""

# Drain worker: managed by systemd.
if systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE}.service"; then
  echo "==> Restarting $SERVICE (systemd)"
  if sudo systemctl restart "$SERVICE" && systemctl is-active --quiet "$SERVICE"; then
    echo "    $SERVICE: active ✓"
  else
    drain_rc=1
    echo "${RED}!!  $SERVICE failed to restart — journalctl -u $SERVICE -n 50 --no-pager${RESET}" >&2
  fi
else
  echo "${RED}(!) $SERVICE not installed — run ./infra/ec2_drain_setup.sh to set it up.${RESET}"
fi

echo ""
if [ "$api_rc" -eq 0 ] && [ "$web_rc" -eq 0 ] && [ "$drain_rc" -eq 0 ]; then
  echo "All services restarted. From your laptop:  ./infra/tunnel.sh <EC2_PUBLIC_IP>"
else
  echo "${RED}Something didn't come up (api=$api_rc web=$web_rc drain=$drain_rc).${RESET}" >&2
  echo "${RED}Check infra/logs/{api,web}.log and journalctl -u $SERVICE.${RESET}" >&2
  exit 1
fi
