#!/usr/bin/env bash
#
# Provision the ScrollWise content-generator on ECS/Fargate — end to end,
# EVENT-DRIVEN (no scheduler): apps/api fires an ECS RunTask on prompt submit.
#
# Networking model: the task runs in a PUBLIC subnet with a public IP, so it
# reaches ECR / Bedrock / CloudWatch Logs over the (free) Internet Gateway — no
# NAT, no per-service interface endpoints for the task. The only interface
# endpoint kept is `ecs`, so the private-subnet API Lambda can call RunTask.
# Public IP is billed only while a task runs (~cents/mo at event-driven volume).
#
# Idempotent: every step checks-then-creates, safe to re-run. Also DELETES the
# paid ecr/logs/bedrock endpoints an earlier (endpoint-based) run may have made.
# Does NOT tear down EC2 (manual — see README teardown checklist).
#
# Usage:
#   export DB_PASS='<rds-scrollwise-password>'        # from infra/passwords (gitignored)
#   ./infra/aws/generator/setup.sh                    # full provision
#   PUBLIC_SUBNETS='subnet-aaa subnet-bbb' ./...       # override public-subnet auto-discovery
#   SKIP_BUILD=1 ./infra/aws/generator/setup.sh       # skip docker build/push
#   SMOKE_TEST=1 ./infra/aws/generator/setup.sh       # also fire one task at the end
#
# Setting the API Lambda's ECS_* trigger env vars is a SEPARATE step (it's the
# API's config) — this script prints a ready-to-run infra/aws/api/set-env.sh
# command at the end.
#
# Prereqs: aws CLI v2 authenticated for the `scrollwise` profile, Docker running
# (unless SKIP_BUILD).
set -euo pipefail

# ---- config (established infra; see infra/aws/PROGRESS.md) -------------------
PROFILE="${AWS_PROFILE:-scrollwise}"
REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID="339140804013"
VPC_ID="vpc-043d8285225718949"
PRIVATE_SUBNET_A="subnet-0381b8136594335d2"   # where the API Lambda + RDS live
PRIVATE_SUBNET_B="subnet-047ca5c90a3dcfb4d"   # (the `ecs` endpoint goes here)
TASK_SG="sg-0f0cc540888358d41"                # reused API Lambda SG — allowed into RDS
                                              # (API Lambda uses the same SG)
ECR_REPO="scrollwise-generator"
IMAGE_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO:latest"
CLUSTER="scrollwise"
FAMILY="scrollwise-generator"
LOG_GROUP="/ecs/scrollwise-generator"
EXEC_ROLE="scrollwise-generator-exec"
TASK_ROLE="scrollwise-generator-task"
EP_SG_NAME="scrollwise-vpce"
OLD_SCHEDULE_NAME="scrollwise-generator-drain"   # deleted if a prior run created it
API_ROLE="${API_LAMBDA_ROLE:-scrollwise-api-lambdas}"   # confirmed in operational.txt; override if it differs

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../../.." && pwd)"
aws() { command aws --profile "$PROFILE" --region "$REGION" "$@"; }
say() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }

: "${DB_PASS:?Set DB_PASS (the RDS 'scrollwise' password, from infra/passwords)}"
say "Account $ACCOUNT_ID / $REGION — verifying credentials"
aws sts get-caller-identity >/dev/null

# ---- 1. ECR repo + image ----------------------------------------------------
say "1. ECR repo + image"
aws ecr describe-repositories --repository-names "$ECR_REPO" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "$ECR_REPO" >/dev/null
if [[ "${SKIP_BUILD:-0}" == "1" ]]; then
  echo "SKIP_BUILD=1 — not building/pushing."
else
  aws ecr get-login-password | docker login --username AWS \
    --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
  docker build --platform linux/arm64 -t "$ECR_REPO" "$REPO_ROOT/services/content-generator"
  docker tag "$ECR_REPO:latest" "$IMAGE_URI"
  docker push "$IMAGE_URI"
fi

# ---- 2. Networking: public subnet for the task + one `ecs` endpoint ----------
say "2. Networking — public subnet (free IGW egress) + ecs endpoint for the API"
# Public subnet(s): subnets whose route table sends 0.0.0.0/0 to the VPC's
# Internet Gateway. The task runs here with a public IP for free egress.
if [[ -z "${PUBLIC_SUBNETS:-}" ]]; then
  IGW=$(aws ec2 describe-internet-gateways \
    --filters "Name=attachment.vpc-id,Values=$VPC_ID" \
    --query 'InternetGateways[0].InternetGatewayId' --output text 2>/dev/null || echo "None")
  if [[ "$IGW" == "None" || -z "$IGW" ]]; then
    echo "!! No Internet Gateway on $VPC_ID — can't use a public subnet."
    echo "   Pass one explicitly: PUBLIC_SUBNETS='subnet-xxxx' ./setup.sh"; exit 1
  fi
  PUBLIC_SUBNETS=$(aws ec2 describe-route-tables \
    --filters "Name=vpc-id,Values=$VPC_ID" "Name=route.gateway-id,Values=$IGW" \
    --query 'RouteTables[].Associations[?SubnetId!=`null`].SubnetId' --output text)
fi
PUB_CSV=$(echo $PUBLIC_SUBNETS | xargs | tr ' ' ',')
if [[ -z "$PUB_CSV" ]]; then
  echo "!! Could not auto-find a public subnet in $VPC_ID (main-RT-implicit subnets"
  echo "   aren't detected). Pass one: PUBLIC_SUBNETS='subnet-xxxx' ./setup.sh"; exit 1
fi
echo "public subnet(s) for the task: $PUB_CSV"

# Endpoint SG (443 from the task/Lambda SG) for the one interface endpoint we keep.
EP_SG=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=$EP_SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")
if [[ "$EP_SG" == "None" || -z "$EP_SG" ]]; then
  EP_SG=$(aws ec2 create-security-group --group-name "$EP_SG_NAME" \
    --description "443 from scrollwise tasks/lambda" --vpc-id "$VPC_ID" \
    --query GroupId --output text)
  aws ec2 authorize-security-group-ingress --group-id "$EP_SG" \
    --protocol tcp --port 443 --source-group "$TASK_SG" >/dev/null
  echo "created endpoint SG $EP_SG (443 from $TASK_SG)"
else
  echo "endpoint SG exists: $EP_SG"
fi

# The `ecs` interface endpoint lives in the PRIVATE subnets (where the API Lambda
# ENIs are) so the Lambda can call RunTask without internet access.
ECS_EP_SVC="com.amazonaws.$REGION.ecs"
ECS_EP=$(aws ec2 describe-vpc-endpoints \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=service-name,Values=$ECS_EP_SVC" \
  --query 'VpcEndpoints[0].VpcEndpointId' --output text 2>/dev/null || echo "None")
if [[ "$ECS_EP" == "None" || -z "$ECS_EP" ]]; then
  aws ec2 create-vpc-endpoint --vpc-id "$VPC_ID" --vpc-endpoint-type Interface \
    --service-name "$ECS_EP_SVC" --subnet-ids "$PRIVATE_SUBNET_A" "$PRIVATE_SUBNET_B" \
    --security-group-ids "$EP_SG" --private-dns-enabled >/dev/null
  echo "created ecs interface endpoint"
else
  echo "ecs interface endpoint exists: $ECS_EP"
fi

# Cost cleanup: with the public-subnet task, the paid ecr/logs/bedrock interface
# endpoints (~$7/mo each) a previous endpoint-based run may have created are no
# longer needed — delete them. (The free S3 gateway endpoint, if any, is left.)
for svc in ecr.api ecr.dkr logs bedrock-runtime; do
  id=$(aws ec2 describe-vpc-endpoints \
    --filters "Name=vpc-id,Values=$VPC_ID" "Name=service-name,Values=com.amazonaws.$REGION.$svc" \
    --query 'VpcEndpoints[0].VpcEndpointId' --output text 2>/dev/null || echo "None")
  if [[ "$id" != "None" && -n "$id" ]]; then
    aws ec2 delete-vpc-endpoints --vpc-endpoint-ids "$id" >/dev/null
    echo "  deleted now-unneeded endpoint $svc ($id, ~\$7/mo saved)"
  fi
done

# ---- 3. IAM roles (task execution + task) -----------------------------------
say "3. IAM roles (execution + task)"
ECS_TRUST='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
ensure_role() {  # $1 name, $2 trust-json
  aws iam get-role --role-name "$1" >/dev/null 2>&1 \
    || aws iam create-role --role-name "$1" --assume-role-policy-document "$2" >/dev/null
}
ensure_role "$EXEC_ROLE" "$ECS_TRUST"
aws iam attach-role-policy --role-name "$EXEC_ROLE" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
ensure_role "$TASK_ROLE" "$ECS_TRUST"
aws iam put-role-policy --role-name "$TASK_ROLE" --policy-name bedrock-invoke \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["bedrock:InvokeModel"],"Resource":"*"}]}'
echo "waiting for role propagation…"; sleep 10

# ---- 4. Log group + cluster + task definition -------------------------------
say "4. Log group + ECS cluster + task definition"
aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" \
  --query 'logGroups[0].logGroupName' --output text 2>/dev/null | grep -q "$LOG_GROUP" \
  || aws logs create-log-group --log-group-name "$LOG_GROUP"
aws ecs create-cluster --cluster-name "$CLUSTER" >/dev/null   # idempotent
sed "s|<DB_PASS>|$DB_PASS|g" "$HERE/task-definition.template.json" \
  | grep -v '"//' > /tmp/scrollwise-generator-taskdef.json     # strip "// comment keys
aws ecs register-task-definition --cli-input-json file:///tmp/scrollwise-generator-taskdef.json >/dev/null
rm -f /tmp/scrollwise-generator-taskdef.json                   # it held the DB password
echo "registered task def $FAMILY"

# ---- 5. Event-driven wiring (NO scheduler) ----------------------------------
say "5. Event-driven — remove any old schedule + let the API RunTask"
if aws scheduler get-schedule --name "$OLD_SCHEDULE_NAME" >/dev/null 2>&1; then
  aws scheduler delete-schedule --name "$OLD_SCHEDULE_NAME"
  echo "deleted old schedule $OLD_SCHEDULE_NAME (now event-driven)"
fi
if aws iam get-role --role-name "$API_ROLE" >/dev/null 2>&1; then
  aws iam put-role-policy --role-name "$API_ROLE" --policy-name run-generator \
    --policy-document "$(cat <<JSON
{"Version":"2012-10-17","Statement":[
  {"Effect":"Allow","Action":"ecs:RunTask","Resource":"arn:aws:ecs:$REGION:$ACCOUNT_ID:task-definition/$FAMILY:*"},
  {"Effect":"Allow","Action":"iam:PassRole","Resource":[
    "arn:aws:iam::$ACCOUNT_ID:role/$EXEC_ROLE",
    "arn:aws:iam::$ACCOUNT_ID:role/$TASK_ROLE"],
   "Condition":{"StringEquals":{"iam:PassedToService":"ecs-tasks.amazonaws.com"}}}]}
JSON
)"
  echo "attached run-generator policy to $API_ROLE"
else
  echo "!! API role '$API_ROLE' not found — set API_LAMBDA_ROLE=<real-name> and re-run"
  echo "   (e.g. try scrollwise-api-lambda if the confirmed name differs)."
fi

# ---- 6. optional smoke test -------------------------------------------------
if [[ "${SMOKE_TEST:-0}" == "1" ]]; then
  say "6. Smoke test — firing one task now (public subnet + public IP)"
  aws ecs run-task --cluster "$CLUSTER" --launch-type FARGATE \
    --task-definition "$FAMILY" \
    --network-configuration "awsvpcConfiguration={subnets=[$PUB_CSV],securityGroups=[$TASK_SG],assignPublicIp=ENABLED}" \
    --query 'tasks[0].taskArn' --output text
  echo "tail logs: aws logs tail $LOG_GROUP --since 5m --follow --profile $PROFILE --region $REGION"
fi

say "Done. Event-driven Fargate generation is provisioned (public-subnet model)."
cat <<EOF

Next — wire the API trigger (its config, so it's a separate script):

1) Set the trigger env vars on the scrollwise-api Lambda (merge-safe):
   infra/aws/api/set-env.sh \\
     ECS_CLUSTER=$CLUSTER ECS_TASK_DEFINITION=$FAMILY \\
     ECS_SUBNETS=$PUB_CSV ECS_SECURITY_GROUPS=$TASK_SG ECS_ASSIGN_PUBLIC_IP=ENABLED

2) Redeploy the API image (it now needs boto3 + the new generation_service):
   see the scrollwise-serverless skill.

Verify:
  • Submit a prompt in the app, then:
    aws logs tail $LOG_GROUP --since 10m --follow --profile $PROFILE --region $REGION
    → expect drain_loop_start → prompt_claimed → prompt_ready, task exits 0.
  • Then stop EC2 drain:  ssh prod 'sudo systemctl stop scrollwise-drain'
  • Final pg_dump, terminate i-07f9dd1d8f1111f92, release EIP, clean up SGs (README teardown).
EOF
