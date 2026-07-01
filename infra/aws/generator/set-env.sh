#!/usr/bin/env bash
#
# Merge-safe env-var setter for the scrollwise-generator Fargate task.
#
# Unlike a Lambda (mutable env), a Fargate TASK DEFINITION is immutable — you
# register a NEW REVISION. This fetches the latest revision, overlays your
# KEY=VALUE pairs onto the container's `environment` (existing vars survive), and
# registers a new revision. The event-driven RunTask references the family, so
# the NEXT triggered task uses the new revision automatically — nothing else to wire.
#
# Usage:
#   infra/aws/generator/set-env.sh KEY=VALUE [KEY=VALUE ...]
#
# Example (the vars a fuller generator config wants):
#   infra/aws/generator/set-env.sh \
#     LLM_MODEL=anthropic.claude-... \
#     EMBEDDING_BACKEND=bedrock \
#     IMAGE_S3_BUCKET=scrollwise-... IMAGE_BEDROCK_REGION=us-east-1 \
#     IMAGE_BEDROCK_MODEL=amazon.titan-image-generator-v2
#
# ⚠️ Source of truth: infra/aws/generator/setup.sh re-registers the task def from
# task-definition.template.json, which would DROP vars added only here. For
# permanent config, also add them to that template. Use this for quick/one-off changes.
#
# Prereqs: aws CLI v2 authenticated for the `scrollwise` profile; jq.
set -euo pipefail

PROFILE="${AWS_PROFILE:-scrollwise}"
REGION="${AWS_REGION:-us-east-1}"
FAMILY="${GENERATOR_FAMILY:-scrollwise-generator}"
aws() { command aws --profile "$PROFILE" --region "$REGION" "$@"; }

[[ $# -ge 1 ]] || { echo "usage: $0 KEY=VALUE [KEY=VALUE ...]"; exit 1; }
command -v jq >/dev/null || { echo "jq required (brew install jq)"; exit 1; }
aws sts get-caller-identity >/dev/null || { echo "$PROFILE creds invalid — refresh"; exit 1; }

# Build a jq object from the KEY=VALUE args.
add='{}'
for kv in "$@"; do
  [[ "$kv" == *=* ]] || { echo "bad pair (need KEY=VALUE): $kv"; exit 1; }
  k="${kv%%=*}"; v="${kv#*=}"
  [[ -n "$k" ]] || { echo "empty key in: $kv"; exit 1; }
  add=$(jq -c --arg k "$k" --arg v "$v" '. + {($k): $v}' <<<"$add")
done

# Fetch the latest revision, merge env on the first container, and strip the
# read-only fields that register-task-definition rejects.
td=$(aws ecs describe-task-definition --task-definition "$FAMILY" --query 'taskDefinition')
newtd=$(jq -c --argjson add "$add" '
  .containerDefinitions[0].environment =
    ( ((.containerDefinitions[0].environment // []) | map({(.name): .value}) | add + $add)
      | to_entries | map({name: .key, value: .value}) )
  | del(.taskDefinitionArn, .revision, .status, .requiresAttributes,
        .compatibilities, .registeredAt, .registeredBy)
' <<<"$td")

# Register (via a temp file — the JSON holds DATABASE_URL with the DB password).
tmp=$(mktemp); trap 'rm -f "$tmp"' EXIT
printf '%s' "$newtd" > "$tmp"
rev=$(aws ecs register-task-definition --cli-input-json "file://$tmp" \
  --query 'taskDefinition.revision' --output text)

echo "registered $FAMILY:$rev  (set: $(jq -r 'keys | join(", ")' <<<"$add"))"
echo "env now (secrets redacted):"
jq -r '.containerDefinitions[0].environment[]
       | "  \(.name)=\(if (.name|test("PASS|SECRET|DATABASE_URL")) then "***" else .value end)"' <<<"$newtd"
