#!/usr/bin/env bash
# Restart/redeploy EVERYTHING in PUBLIC (Caddy) mode:
#   - API           : restart the uvicorn process (restart_api.sh)
#   - Frontend      : rebuild + redeploy static bundle to the webroot (deploy_web.sh)
#   - Caddy         : reload (picks up Caddyfile changes; serves the new static files)
#   - Drain worker  : restart the systemd service
#
# This is the public/Caddy counterpart to restart_dev.sh (which is for the
# SSH-tunnel dev mode with the Vite dev server). Use this on the live site.
# Runs every step even if one fails, then reports. Does NOT reinstall anything
# or rewrite the Caddyfile — for first-time setup use ec2_proxy_setup.sh.
#
# Usage:  ./infra/restart_prod.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -t 2 ]; then RED=$'\033[31m'; RESET=$'\033[0m'; else RED=''; RESET=''; fi
DRAIN="scrollwise-drain"

api_rc=0; web_rc=0; caddy_rc=0; drain_rc=0

"$SCRIPT_DIR/restart_api.sh" || api_rc=$?
echo ""
"$SCRIPT_DIR/deploy_web.sh" || web_rc=$?
echo ""

# Caddy: reload (graceful) if installed; fall back to restart.
if systemctl list-unit-files 2>/dev/null | grep -q '^caddy.service'; then
  echo "==> Reloading Caddy"
  if (sudo systemctl reload caddy || sudo systemctl restart caddy) \
       && systemctl is-active --quiet caddy; then
    echo "    caddy: active ✓"
  else
    caddy_rc=1
    echo "${RED}!!  caddy failed — journalctl -u caddy -n 50 --no-pager${RESET}" >&2
  fi
else
  echo "${RED}(!) caddy not installed — run ./infra/ec2_proxy_setup.sh <domain>.${RESET}"
fi
echo ""

# Drain worker.
if systemctl list-unit-files 2>/dev/null | grep -q "^${DRAIN}.service"; then
  echo "==> Restarting $DRAIN"
  if sudo systemctl restart "$DRAIN" && systemctl is-active --quiet "$DRAIN"; then
    echo "    $DRAIN: active ✓"
  else
    drain_rc=1
    echo "${RED}!!  $DRAIN failed — journalctl -u $DRAIN -n 50 --no-pager${RESET}" >&2
  fi
else
  echo "${RED}(!) $DRAIN not installed — run ./infra/ec2_drain_setup.sh.${RESET}"
fi

echo ""
if [ "$api_rc" -eq 0 ] && [ "$web_rc" -eq 0 ] && [ "$caddy_rc" -eq 0 ] && [ "$drain_rc" -eq 0 ]; then
  echo "Public site redeployed. Verify: curl https://<your-domain>/api/health"
else
  echo "${RED}Something didn't come up (api=$api_rc web=$web_rc caddy=$caddy_rc drain=$drain_rc).${RESET}" >&2
  exit 1
fi
