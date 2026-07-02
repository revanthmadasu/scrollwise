#!/usr/bin/env bash
# Deploy the ScrollWise frontend (apps/web) to S3 + CloudFront.
#
# This is the REPEATABLE deploy step. Run it after every web change once the
# one-time infrastructure (bucket + distribution) exists — see README.md in this
# directory for the one-time setup.
#
# What it does:
#   1. Builds the Vite bundle (same /api same-origin contract as the EC2 flow).
#   2. Syncs dist/ to the S3 bucket (deletes removed files).
#   3. Invalidates the CloudFront cache so users get the new bundle immediately.
#
# Usage:
#   WEB_BUNDLE_BUILD_BUCKET=scrollwise-web-bundle-prod \
#   CF_DISTRIBUTION_ID=E1ABCDEF234567 \
#   ./infra/aws/web/deploy.sh
#
# Optional:
#   VITE_API_BASE   Base URL the SPA calls. Defaults to https://api.scrollwise.net
#                   — the API is served on its own domain (EC2/Caddy now, API
#                   Gateway later), so the browser calls it cross-origin. The API
#                   must allow the UI origin in CORS_ORIGINS.
set -euo pipefail

if [ -t 2 ]; then RED=$'\033[31m'; GRN=$'\033[32m'; RESET=$'\033[0m'; else RED=''; GRN=''; RESET=''; fi
err() { echo "${RED}$*${RESET}" >&2; }
ok()  { echo "${GRN}$*${RESET}"; }

: "${WEB_BUNDLE_BUILD_BUCKET:?Set WEB_BUNDLE_BUILD_BUCKET to the S3 bucket name (e.g. scrollwise-web-bundle-prod)}"
: "${CF_DISTRIBUTION_ID:?Set CF_DISTRIBUTION_ID to the CloudFront distribution id (e.g. E1ABCDEF234567)}"
VITE_API_BASE="${VITE_API_BASE:-https://api.scrollwise.net}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
WEB_DIR="$REPO_ROOT/apps/web"

command -v node >/dev/null 2>&1 || { err "!! node not found (need Node 18+; e.g. nvm use 22)"; exit 1; }
command -v aws  >/dev/null 2>&1 || { err "!! aws CLI not found — install the AWS CLI v2 first"; exit 1; }

echo "==> Installing frontend dependencies (npm ci)"
( cd "$WEB_DIR" && npm ci )

echo "==> Building frontend (VITE_API_BASE=$VITE_API_BASE)"
( cd "$WEB_DIR" && VITE_API_BASE="$VITE_API_BASE" npm run build )

# Hashed assets (JS/CSS with content hashes in the filename) can cache forever.
# index.html must NOT be cached long, or users keep loading the old bundle.
echo "==> Syncing hashed assets to s3://$WEB_BUNDLE_BUILD_BUCKET (long cache)"
aws s3 sync "$WEB_DIR/dist/" "s3://$WEB_BUNDLE_BUILD_BUCKET/" \
  --delete \
  --exclude "index.html" \
  --cache-control "public,max-age=31536000,immutable"

echo "==> Uploading index.html (no cache)"
aws s3 cp "$WEB_DIR/dist/index.html" "s3://$WEB_BUNDLE_BUILD_BUCKET/index.html" \
  --cache-control "no-cache" \
  --content-type "text/html"

echo "==> Invalidating CloudFront cache"
INVALIDATION_ID="$(aws cloudfront create-invalidation \
  --distribution-id "$CF_DISTRIBUTION_ID" \
  --paths "/*" \
  --query 'Invalidation.Id' --output text)"

ok "Done. Invalidation $INVALIDATION_ID created — propagates in ~1-3 min."
echo "Site: check your CloudFront domain (or custom domain) in a hard-refreshed browser."
