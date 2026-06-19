#!/usr/bin/env bash
# Put the ScrollWise app on a public domain over HTTPS, using Caddy as a
# reverse proxy. Single-domain layout:
#
#   https://DOMAIN/         -> the built web frontend (static files)
#   https://DOMAIN/api/*    -> the API on 127.0.0.1:8000  (/api prefix stripped)
#
# Because the frontend and API share one origin, there's no CORS to configure
# and the frontend just calls "/api/..." relative to the page.
#
# The app keeps binding to localhost (ec2_app_setup.sh) — Caddy is the only
# public-facing process. Caddy fetches + renews the TLS cert automatically.
#
# PREREQS (do these first, in order):
#   1. ec2_app_setup.sh has run (API on :8000, Node installed).
#   2. An Elastic IP is associated with this instance.
#   3. DNS A record(s) for DOMAIN point at that Elastic IP (verify: dig DOMAIN).
#   4. Security group allows inbound 80 AND 443 (Caddy needs 80 for the ACME
#      challenge and 443 to serve). Open these in the EC2 console — can't be
#      done from inside the box.
#
# Usage (on the EC2 box, from the repo root):
#   chmod +x infra/ec2_proxy_setup.sh
#   ./infra/ec2_proxy_setup.sh yourdomain.com [you@email.com]
#
# The optional email is used for Let's Encrypt expiry notices.
set -euo pipefail

if [ -t 2 ]; then RED=$'\033[31m'; RESET=$'\033[0m'; else RED=''; RESET=''; fi
err() { echo "${RED}$*${RESET}" >&2; }

DOMAIN="${1:-}"
ACME_EMAIL="${2:-}"
if [ -z "$DOMAIN" ]; then
  err "Usage: $0 <domain> [acme_email]"
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_DIR="$REPO_ROOT/apps/api"
WEBROOT="/var/www/scrollwise"   # frontend build/copy lives in deploy_web.sh

echo "==> Domain: $DOMAIN"

# --- sanity: does DNS already point here? (warn only — Caddy will retry) -------
RESOLVED="$(dig +short "$DOMAIN" 2>/dev/null | tail -n1 || true)"
MYIP="$(curl -fsS https://checkip.amazonaws.com 2>/dev/null | tr -d '[:space:]' || true)"
if [ -n "$RESOLVED" ] && [ -n "$MYIP" ] && [ "$RESOLVED" != "$MYIP" ]; then
  err "(!) $DOMAIN resolves to $RESOLVED but this box is $MYIP."
  err "(!) Certificate issuance will fail until DNS points here. Continuing anyway."
elif [ -z "$RESOLVED" ]; then
  err "(!) $DOMAIN doesn't resolve yet. Add the A record; Caddy will get the cert once it does."
fi

# --- install Caddy (official apt repo) ----------------------------------------
if ! command -v caddy >/dev/null 2>&1; then
  echo "==> Installing Caddy"
  sudo apt-get update -y
  sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y caddy
fi

# --- write the Caddyfile ------------------------------------------------------
echo "==> Writing /etc/caddy/Caddyfile"
EMAIL_BLOCK=""
[ -n "$ACME_EMAIL" ] && EMAIL_BLOCK=$'{\n    email '"$ACME_EMAIL"$'\n}\n\n'
sudo tee /etc/caddy/Caddyfile >/dev/null <<CADDY
${EMAIL_BLOCK}${DOMAIN} {
    encode gzip

    # API: strip the /api prefix, proxy to the backend on localhost.
    handle_path /api/* {
        reverse_proxy 127.0.0.1:8000
    }

    # Frontend: static SPA with client-side routing fallback.
    handle {
        root * ${WEBROOT}

        # Content-hashed build assets (index-<hash>.js, etc.) never change for a
        # given URL — cache them hard.
        @assets path /assets/*
        header @assets Cache-Control "public, max-age=31536000, immutable"

        # index.html and every SPA-fallback response must revalidate, so a fresh
        # deploy is picked up on the next load instead of from a stale cache.
        # (This is what makes /admin/login appear after a deploy without a manual
        # hard-refresh.)
        @html not path /assets/*
        header @html Cache-Control "no-cache"

        try_files {path} /index.html
        file_server
    }
}
CADDY

# --- defensively allow the domain in the API's CORS (same-origin won't need it,
#     but harmless and future-proofs an api. split) -----------------------------
if [ -f "$API_DIR/.env" ]; then
  ORIGIN="https://$DOMAIN"
  if grep -q '^CORS_ORIGINS=' "$API_DIR/.env"; then
    grep '^CORS_ORIGINS=' "$API_DIR/.env" | grep -q "$ORIGIN" \
      || sed -i "s|^CORS_ORIGINS=.*|&,$ORIGIN|" "$API_DIR/.env"
  else
    echo "CORS_ORIGINS=http://localhost:3000,http://localhost:5173,$ORIGIN" >> "$API_DIR/.env"
  fi
fi

# --- build + deploy the frontend (reuses deploy_web.sh) -----------------------
sudo mkdir -p "$WEBROOT"          # so deploy_web.sh's "webroot exists" guard passes
"$SCRIPT_DIR/deploy_web.sh"

# --- (re)load Caddy and restart the API to pick up CORS -----------------------
echo "==> Reloading Caddy"
sudo systemctl enable caddy >/dev/null 2>&1 || true
sudo systemctl restart caddy
"$SCRIPT_DIR/restart_api.sh" || err "(!) API restart reported a problem — check infra/logs/api.log"

sleep 3
cat <<DONE

==========================================
  Public site configured for ${DOMAIN}
==========================================
  Frontend : https://${DOMAIN}/
  API      : https://${DOMAIN}/api/...  -> 127.0.0.1:8000

Checks:
  curl -I https://${DOMAIN}            # should be 200 (after cert issues)
  curl https://${DOMAIN}/api/health    # {"status":"ok"}
  sudo systemctl status caddy
  journalctl -u caddy -f               # watch cert issuance / requests

If HTTPS doesn't come up:
  - confirm DNS: dig ${DOMAIN}  (must equal this box's Elastic IP)
  - confirm security group allows inbound 80 AND 443
  - check the log above for ACME errors

Re-deploy the frontend after code changes:
  ./infra/deploy_web.sh
DONE
