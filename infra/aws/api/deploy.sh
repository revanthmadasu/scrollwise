#!/usr/bin/env bash
# Deploy the ScrollWise API (apps/api) — build the arm64 container image, push it
# to ECR, and roll the Lambda to it.
#
# This is the REPEATABLE deploy step (the local counterpart to the CI workflow
# .github/workflows/deploy-api.yml, for when you deploy by hand). The one-time
# infra (ECR repo, Lambda, VPC, API Gateway) already exists — see README.md.
#
# What it does:
#   1. Logs in to ECR.
#   2. Builds the image for arm64 (the Lambda is Graviton — amd64 would break it).
#   3. Pushes to ECR and rolls the Lambda with --publish, then waits.
#   4. Hits /health to confirm the new image booted.
#
# Usage:
#   ./infra/aws/api/deploy.sh
#
# Optional env (sensible prod defaults):
#   AWS_PROFILE   default scrollwise
#   AWS_REGION    default us-east-1
#   API_FUNCTION  default scrollwise-api
#   ECR_REPO      default scrollwise-api
#   HEALTH_URL    default https://api.scrollwise.net/health  (set empty to skip)
set -euo pipefail

if [ -t 2 ]; then RED=$'\033[31m'; GRN=$'\033[32m'; RESET=$'\033[0m'; else RED=''; GRN=''; RESET=''; fi
err() { echo "${RED}$*${RESET}" >&2; }
ok()  { echo "${GRN}$*${RESET}"; }

PROFILE="${AWS_PROFILE:-scrollwise}"
REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID="339140804013"
API_FUNCTION="${API_FUNCTION:-scrollwise-api}"
ECR_REPO="${ECR_REPO:-scrollwise-api}"
HEALTH_URL="${HEALTH_URL-https://api.scrollwise.net/health}"
IMAGE_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO:latest"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
API_DIR="$REPO_ROOT/apps/api"
aws() { command aws --profile "$PROFILE" --region "$REGION" "$@"; }

command -v docker >/dev/null 2>&1 || { err "!! docker not found — start Docker Desktop"; exit 1; }
command -v aws    >/dev/null 2>&1 || { err "!! aws CLI not found — install the AWS CLI v2 first"; exit 1; }
aws sts get-caller-identity >/dev/null || { err "!! $PROFILE creds invalid — refresh and retry"; exit 1; }

echo "==> Logging in to ECR"
aws ecr get-login-password | docker login --username AWS \
  --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

echo "==> Building image (linux/arm64 — Lambda is Graviton)"
docker build --platform linux/arm64 -t "$ECR_REPO" "$API_DIR"

echo "==> Pushing to $IMAGE_URI"
docker tag "$ECR_REPO:latest" "$IMAGE_URI"
docker push "$IMAGE_URI"

echo "==> Rolling Lambda $API_FUNCTION to the new image"
aws lambda update-function-code --function-name "$API_FUNCTION" \
  --image-uri "$IMAGE_URI" --publish >/dev/null
aws lambda wait function-updated --function-name "$API_FUNCTION"

if [ -n "$HEALTH_URL" ]; then
  echo "==> Health check $HEALTH_URL"
  # first hit after a code roll is a cold start (VPC ENI + container init) — retry.
  for i in 1 2 3 4 5; do
    if curl -fsS --max-time 20 "$HEALTH_URL" >/dev/null; then
      ok "Done. $API_FUNCTION rolled and healthy."
      exit 0
    fi
    echo "   not ready yet (attempt $i)… "; sleep 5
  done
  err "!! Deployed, but $HEALTH_URL didn't return healthy — check logs:"
  err "   aws logs tail /aws/lambda/$API_FUNCTION --since 5m --follow --profile $PROFILE --region $REGION"
  exit 1
fi
ok "Done. $API_FUNCTION rolled to the new image."
