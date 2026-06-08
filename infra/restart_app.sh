#!/usr/bin/env bash
# Restart BOTH the ScrollWise API and web on EC2. Thin wrapper over
# restart_api.sh + restart_web.sh — runs both even if one fails, then reports.
# Does NOT reinstall deps; for a full install use infra/ec2_app_setup.sh.
#
# Usage:  ./infra/restart_app.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -t 2 ]; then RED=$'\033[31m'; RESET=$'\033[0m'; else RED=''; RESET=''; fi

api_rc=0; web_rc=0
"$SCRIPT_DIR/restart_api.sh" || api_rc=$?
echo ""
"$SCRIPT_DIR/restart_web.sh" || web_rc=$?

echo ""
if [ "$api_rc" -eq 0 ] && [ "$web_rc" -eq 0 ]; then
  echo "Both restarted. From your laptop:  ./infra/tunnel.sh <EC2_PUBLIC_IP>"
else
  echo "${RED}One or more services failed to come up (api_rc=$api_rc web_rc=$web_rc).${RESET}" >&2
  echo "${RED}Check infra/logs/api.log and infra/logs/web.log.${RESET}" >&2
  exit 1
fi
