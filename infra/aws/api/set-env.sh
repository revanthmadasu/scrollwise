#!/usr/bin/env bash
#
# Merge-safe environment-variable setter for the scrollwise-api Lambda.
#
# Why: `aws lambda update-function-configuration --environment` REPLACES the whole
# env map — miss a key and you silently wipe DATABASE_URL / JWT_SECRET / CORS. This
# fetches the current map, overlays the KEY=VALUE pairs you pass, and applies the
# merge, so existing vars survive. Use it for any API Lambda env change.
#
# Usage:
#   infra/aws/api/set-env.sh KEY=VALUE [KEY=VALUE ...]
#
# Example — wire the event-driven content-generator trigger (values printed by
# infra/aws/generator/setup.sh):
#   infra/aws/api/set-env.sh \
#     ECS_CLUSTER=scrollwise ECS_TASK_DEFINITION=scrollwise-generator \
#     ECS_SUBNETS=subnet-xxxx ECS_SECURITY_GROUPS=sg-0f0cc540888358d41 \
#     ECS_ASSIGN_PUBLIC_IP=ENABLED
#
# Prereqs: aws CLI v2 authenticated for the `scrollwise` profile; jq.
set -euo pipefail

PROFILE="${AWS_PROFILE:-scrollwise}"
REGION="${AWS_REGION:-us-east-1}"
FUNCTION="${API_FUNCTION:-scrollwise-api}"

[[ $# -ge 1 ]] || { echo "usage: $0 KEY=VALUE [KEY=VALUE ...]"; exit 1; }
command -v jq >/dev/null || { echo "jq required (brew install jq)"; exit 1; }
aws() { command aws --profile "$PROFILE" --region "$REGION" "$@"; }

# Build a jq object from the KEY=VALUE args.
add='{}'
for kv in "$@"; do
  [[ "$kv" == *=* ]] || { echo "bad pair (need KEY=VALUE): $kv"; exit 1; }
  k="${kv%%=*}"; v="${kv#*=}"
  [[ -n "$k" ]] || { echo "empty key in: $kv"; exit 1; }
  if [[ "$k" == "AWS_REGION" ]]; then
    echo "skipping AWS_REGION — it's reserved and auto-set by Lambda."; continue
  fi
  add=$(jq -c --arg k "$k" --arg v "$v" '. + {($k): $v}' <<<"$add")
done

# Merge onto the current env map and apply.
merged=$(aws lambda get-function-configuration --function-name "$FUNCTION" \
  --query 'Environment.Variables' \
  | jq -c --argjson add "$add" '{Variables: (. + $add)}')

aws lambda update-function-configuration --function-name "$FUNCTION" \
  --environment "$merged" >/dev/null
aws lambda wait function-updated --function-name "$FUNCTION"

echo "updated $FUNCTION env (existing vars preserved). Set keys: $(jq -r 'keys | join(", ")' <<<"$add")"
aws lambda get-function-configuration --function-name "$FUNCTION" \
  --query 'Environment.Variables'
