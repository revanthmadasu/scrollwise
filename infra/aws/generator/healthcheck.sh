#!/usr/bin/env bash
# Read-only health check for the event-driven Fargate content-generator.
#
# Verifies the plumbing and recent run health WITHOUT submitting a prompt:
#   1. task definition is registered/ACTIVE
#   2. the `ecs` VPC endpoint is available (so the API can call RunTask)
#   3. the scrollwise-api Lambda has the ECS_* trigger env vars set
#   4. the most recent task exited cleanly (+ how many run now)
#   5. recent generator logs (prompt_ready / prompt_failed counts, last hour)
#
# Exits non-zero if any hard check FAILs. Safe to run anytime (read-only).
#
# Usage: ./infra/aws/generator/healthcheck.sh
# Env:   AWS_PROFILE (default scrollwise), AWS_REGION (default us-east-1)
set -uo pipefail   # not -e: run all checks, then summarize

PROFILE="${AWS_PROFILE:-scrollwise}"
REGION="${AWS_REGION:-us-east-1}"
CLUSTER="scrollwise"
FAMILY="scrollwise-generator"
LOG_GROUP="/ecs/scrollwise-generator"
API_FUNCTION="${API_FUNCTION:-scrollwise-api}"
ECS_EP_SVC="com.amazonaws.$REGION.ecs"
aws() { command aws --profile "$PROFILE" --region "$REGION" "$@"; }

if [ -t 1 ]; then G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; B=$'\033[1m'; X=$'\033[0m'
else G=''; Y=''; R=''; B=''; X=''; fi
fails=0; warns=0
pass() { printf "  ${G}[OK]${X}   %s\n" "$*"; }
warn() { printf "  ${Y}[WARN]${X} %s\n" "$*"; warns=$((warns+1)); }
fail() { printf "  ${R}[FAIL]${X} %s\n" "$*"; fails=$((fails+1)); }
head() { printf "\n${B}%s${X}\n" "$*"; }

command -v jq >/dev/null || { echo "jq required (brew install jq)"; exit 2; }
aws sts get-caller-identity >/dev/null 2>&1 || { echo "${R}$PROFILE creds invalid — refresh and retry${X}"; exit 2; }

head "1. Task definition"
st=$(aws ecs describe-task-definition --task-definition "$FAMILY" \
  --query 'taskDefinition.status' --output text 2>/dev/null || echo MISSING)
[[ "$st" == "ACTIVE" ]] && pass "$FAMILY is ACTIVE" || fail "$FAMILY not registered/active (got: $st) — run setup.sh"

head "2. ecs VPC endpoint (lets the API call RunTask)"
ep=$(aws ec2 describe-vpc-endpoints --filters "Name=service-name,Values=$ECS_EP_SVC" \
  --query 'VpcEndpoints[0].State' --output text 2>/dev/null || echo None)
[[ "$ep" == "available" ]] && pass "ecs endpoint available" \
  || fail "ecs endpoint state=$ep — the API can't reach ECS to RunTask"

head "3. API Lambda trigger config ($API_FUNCTION)"
envj=$(aws lambda get-function-configuration --function-name "$API_FUNCTION" \
  --query 'Environment.Variables' --output json 2>/dev/null || echo '{}')
for k in ECS_CLUSTER ECS_TASK_DEFINITION ECS_SUBNETS ECS_SECURITY_GROUPS ECS_ASSIGN_PUBLIC_IP; do
  v=$(jq -r --arg k "$k" '.[$k] // empty' <<<"$envj")
  [[ -n "$v" ]] && pass "$k=$v" || fail "$k not set — run infra/aws/api/set-env.sh"
done
pubip=$(jq -r '.ECS_ASSIGN_PUBLIC_IP // empty' <<<"$envj")
[[ -z "$pubip" || "$pubip" == "ENABLED" ]] || warn "ECS_ASSIGN_PUBLIC_IP=$pubip — must be ENABLED for a public subnet"

head "4. Recent tasks"
arn=$(aws ecs list-tasks --cluster "$CLUSTER" --desired-status STOPPED \
  --query 'taskArns[0]' --output text 2>/dev/null || echo None)
if [[ "$arn" != "None" && -n "$arn" ]]; then
  read -r ec reason < <(aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$arn" \
    --query 'tasks[0].[containers[0].exitCode,stoppedReason]' --output text 2>/dev/null)
  [[ "$ec" == "0" ]] && pass "last task exited 0" || warn "last task exit=$ec ($reason)"
else
  warn "no stopped tasks in the last ~hour (none triggered yet, or aged out)"
fi
run=$(aws ecs list-tasks --cluster "$CLUSTER" --query 'length(taskArns)' --output text 2>/dev/null || echo 0)
printf "         %s task(s) running now\n" "$run"

head "5. Recent generator logs (last 1h)"
since=$(( ($(date +%s) - 3600) * 1000 ))
count() { aws logs filter-log-events --log-group-name "$LOG_GROUP" --start-time "$since" \
  --filter-pattern "$1" --query 'length(events)' --output text 2>/dev/null || echo 0; }
if aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" \
     --query 'logGroups[0].logGroupName' --output text 2>/dev/null | grep -q "$LOG_GROUP"; then
  ready=$(count prompt_ready); failed=$(count prompt_failed); errs=$(count '"level":"ERROR"')
  pass "prompt_ready: $ready   prompt_failed: $failed   errors: $errs (last 1h)"
  [[ "$failed" != "0" ]] && warn "$failed prompt_failed event(s) — check: aws logs tail $LOG_GROUP --since 1h"
  [[ "$errs"   != "0" ]] && warn "$errs ERROR log event(s) in the last hour"
else
  warn "log group $LOG_GROUP not found (no task has run yet)"
fi

head "Summary"
if [[ $fails -gt 0 ]]; then
  printf "${R}%d failed${X}, ${Y}%d warning(s)${X} — generation trigger NOT healthy.\n" "$fails" "$warns"; exit 1
elif [[ $warns -gt 0 ]]; then
  printf "${G}plumbing OK${X}, ${Y}%d warning(s)${X} — likely just no recent activity.\n" "$warns"; exit 0
else
  printf "${G}All checks passed — event-driven generation is healthy.${X}\n"; exit 0
fi
