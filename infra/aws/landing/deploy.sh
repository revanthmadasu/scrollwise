#!/usr/bin/env bash
# Deploy the ScrollWise LANDING page (apps/landing) to S3 + CloudFront.
#
# Repeatable step — run after every landing-page edit. One-time infra (bucket,
# distribution, cert) is created by setup.sh in this directory.
#
# There is no build step: apps/landing is a static index.html.
#
# Usage (from repo root):
#   ./infra/aws/landing/deploy.sh
#
# Optional:
#   CF_DISTRIBUTION_ID   CloudFront distribution id. If unset, it's looked up
#                        by the www.scrollwise.net alias.
set -euo pipefail

PROFILE=scrollwise
REGION=us-east-1
BUCKET=scrollwise-landing-prod
WWW=www.scrollwise.net

if [ -t 2 ]; then RED=$'\033[31m'; GRN=$'\033[32m'; RESET=$'\033[0m'; else RED=''; GRN=''; RESET=''; fi
err() { echo "${RED}$*${RESET}" >&2; }
ok()  { echo "${GRN}$*${RESET}"; }

aws() { command aws --profile "$PROFILE" --region "$REGION" "$@"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
LANDING_DIR="$REPO_ROOT/apps/landing"

command -v aws >/dev/null 2>&1 || { err "!! aws CLI not found"; exit 1; }
[ -f "$LANDING_DIR/index.html" ] || { err "!! $LANDING_DIR/index.html not found"; exit 1; }

CF_DISTRIBUTION_ID="${CF_DISTRIBUTION_ID:-$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Aliases.Items[?@=='$WWW']].Id | [0]" --output text)}"
[ "$CF_DISTRIBUTION_ID" != "None" ] && [ -n "$CF_DISTRIBUTION_ID" ] \
  || { err "!! could not resolve CloudFront distribution — run setup.sh first or set CF_DISTRIBUTION_ID"; exit 1; }

echo "==> Syncing apps/landing to s3://$BUCKET"
# Static assets other than index.html can cache; index.html must not, or users
# keep loading the old page.
aws s3 sync "$LANDING_DIR/" "s3://$BUCKET/" \
  --delete \
  --exclude "index.html" \
  --cache-control "public,max-age=31536000,immutable"

echo "==> Uploading index.html (no cache)"
aws s3 cp "$LANDING_DIR/index.html" "s3://$BUCKET/index.html" \
  --cache-control "no-cache" \
  --content-type "text/html"

echo "==> Invalidating CloudFront cache ($CF_DISTRIBUTION_ID)"
INVALIDATION_ID="$(aws cloudfront create-invalidation \
  --distribution-id "$CF_DISTRIBUTION_ID" \
  --paths "/*" \
  --query 'Invalidation.Id' --output text)"

ok "Done. Invalidation $INVALIDATION_ID created — propagates in ~1-3 min."
echo "Live at: https://$WWW  (and https://scrollwise.net once the apex redirect is set)"
