#!/usr/bin/env bash
# Deploy the frontend to the public site: rebuild the static bundle and copy it
# into Caddy's webroot. Run this after FRONTEND (apps/web) code changes when the
# site is served publicly via Caddy (ec2_proxy_setup.sh).
#
# This is NOT needed for backend changes — for those just run restart_api.sh
# (Caddy proxies to uvicorn live). And it's separate from the SSH-tunnel dev
# flow, which uses the Vite dev server instead of this static build.
#
# Usage:  ./infra/deploy_web.sh
set -euo pipefail

if [ -t 2 ]; then RED=$'\033[31m'; RESET=$'\033[0m'; else RED=''; RESET=''; fi
err() { echo "${RED}$*${RESET}" >&2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WEB_DIR="$REPO_ROOT/apps/web"
WEBROOT="/var/www/scrollwise"

if ! command -v node >/dev/null 2>&1; then
  err "!!  node not found — run ./infra/ec2_app_setup.sh first."
  exit 1
fi
if [ ! -d "$WEBROOT" ]; then
  err "!!  $WEBROOT doesn't exist — run ./infra/ec2_proxy_setup.sh <domain> first."
  exit 1
fi

# Same relative API base the proxy expects (frontend calls /api/* same-origin).
echo "==> Building frontend (VITE_API_BASE=/api)"
( cd "$WEB_DIR" && VITE_API_BASE=/api npm run build )

echo "==> Deploying to $WEBROOT"
sudo rm -rf "$WEBROOT"/*
sudo cp -r "$WEB_DIR/dist/." "$WEBROOT/"
sudo chmod -R a+rX "$WEBROOT"

echo "Done. Static files updated — no Caddy restart needed (hard-refresh your browser)."
