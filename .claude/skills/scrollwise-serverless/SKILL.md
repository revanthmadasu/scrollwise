---
name: scrollwise-serverless
description: >-
  Operate and troubleshoot the ScrollWise serverless AWS stack — the FastAPI
  backend on Lambda + API Gateway + RDS, and the web SPA on S3 + CloudFront. Use
  this whenever the user wants to redeploy or roll the API Lambda, sees the API
  returning 5xx / 500 / timeouts, asks to read CloudWatch logs for scrollwise-api,
  debugs "the API is down" / "api.scrollwise.net not working", debugs the DB
  connection from the Lambda (RDS reachability, asyncpg URL), pushes a new web
  build or "app.scrollwise.net is blank / not updating" (S3 sync + CloudFront
  invalidation), manages the api/app custom domains or their IONOS DNS / ACM
  certs, or asks about cold starts, the Lambda's env vars, or any of the concrete
  AWS resource ids for this deployment. Reach for it even when the user doesn't
  say "serverless" — "redeploy the api", "why is the api 500ing", "the site won't
  load", "update the frontend", and "where are the api logs in aws" are all this
  skill. Also covers the **content-generator on ECS/Fargate** (event-driven task
  `scrollwise-generator`): "redeploy the generator", "why isn't generation running
  after a prompt", "generation_trigger_failed", "the Fargate task is failing / won't
  pull the image", generator CloudWatch logs, changing the generator's task-def env
  vars. The legacy EC2 `scrollwise-drain` worker is being torn down — use the
  scrollwise-drain skill only for that box until it's decommissioned. For log
  *plumbing/config* use scrollwise-logging.
---

# Operating the ScrollWise serverless stack

The as-built architecture (diagram + all resource ids) lives in
[`ARCHITECTURE.md`](../../../ARCHITECTURE.md); the migration history + open items
in [`infra/aws/PROGRESS.md`](../../../infra/aws/PROGRESS.md); the build/design
walkthroughs in `infra/aws/api/README.md` and `infra/aws/web/README.md`. This
skill is the **operate/troubleshoot** layer on top of those.

All AWS CLI here uses the **`scrollwise` profile**, region **us-east-1**, account
**339140804013**. Claude can run these directly if that profile is authenticated
(`aws sts get-caller-identity --profile scrollwise`); otherwise hand the command
to the user.

## The three services
| Service | Runs on | Front door | Notes |
|---|---|---|---|
| Web (`apps/web`) | S3 `scrollwise-web-bundle-prod` + CloudFront `E3RSA4VCIHJJ90` | `app.scrollwise.net` | static SPA, calls API by URL |
| API (`apps/api`) | Lambda `scrollwise-api` (arm64 image) + API GW `4un2b4m7ij` | `api.scrollwise.net` | VPC, no NAT, reads RDS |
| Generator (`services/content-generator`) | **ECS Fargate** task `scrollwise-generator` (arm64, event-driven) | — | `apps/api` fires `RunTask` on prompt submit; drains `user_prompts`, writes posts to RDS via Bedrock |

Shared **RDS** `scrollwise-pg…:5432/scrollwise` (Postgres 16 + pgvector, private).

## Redeploy the API (roll the Lambda image)
The Lambda runs a **container image** from ECR `scrollwise-api`. To ship code:
```bash
# from repo root, Docker running (image MUST be arm64 — Lambda is Graviton)
aws ecr get-login-password --profile scrollwise --region us-east-1 \
  | docker login --username AWS --password-stdin 339140804013.dkr.ecr.us-east-1.amazonaws.com
docker build -t scrollwise-api apps/api                # native arm64 on M-series
docker tag scrollwise-api:latest 339140804013.dkr.ecr.us-east-1.amazonaws.com/scrollwise-api:latest
docker push 339140804013.dkr.ecr.us-east-1.amazonaws.com/scrollwise-api:latest
aws lambda update-function-code --profile scrollwise --region us-east-1 \
  --function-name scrollwise-api \
  --image-uri 339140804013.dkr.ecr.us-east-1.amazonaws.com/scrollwise-api:latest --publish
aws lambda wait function-updated --profile scrollwise --region us-east-1 --function-name scrollwise-api
```
Or push to `master` touching `apps/api/**` once `.github/workflows/deploy-api.yml`
is wired (needs the `scrollwise-api-deploy` IAM user + repo secrets).

## Deploy the web
```bash
WEB_BUNDLE_BUILD_BUCKET=scrollwise-web-bundle-prod CF_DISTRIBUTION_ID=E3RSA4VCIHJJ90 \
VITE_API_BASE=https://api.scrollwise.net ./infra/aws/web/deploy.sh
```
"Site not updating" is almost always a stale CloudFront cache — the script
invalidates, but you can force it: `aws cloudfront create-invalidation --profile
scrollwise --distribution-id E3RSA4VCIHJJ90 --paths '/*'`.

## Operate the generator (Fargate, event-driven)
The content-generator runs as an **arm64 Fargate task** `scrollwise-generator`
(cluster `scrollwise`), triggered by `apps/api` calling `ecs:RunTask` on prompt
submit — no scheduler, no poller. It drains pending `user_prompts` (`SKIP LOCKED`)
and exits. Full runbook + all resource ids: `infra/aws/generator/README.md`.
The four scripts (run from repo root, `scrollwise` profile):
```bash
DB_PASS='…' ./infra/aws/generator/setup.sh   # (re)provision — idempotent; SKIP_BUILD=1 to skip image build
./infra/aws/api/deploy.sh                     # roll the API image (the trigger lives in apps/api)
./infra/aws/generator/set-env.sh KEY=VALUE …  # change task env → registers a new task-def revision
./infra/aws/generator/healthcheck.sh          # read-only: task def, ecs endpoint, API trigger env, recent runs
```
**Deploy new generator code:** rebuild/push the image (`setup.sh` does it, or the
build block in Step 1 of its README), then the next triggered task pulls `:latest`.

**Generator logs** → CloudWatch group `/ecs/scrollwise-generator`:
```bash
aws logs tail /ecs/scrollwise-generator --profile scrollwise --region us-east-1 --since 15m --follow
#   drain_loop_start → prompt_claimed → prompt_ready ; grep prompt_failed for errors
```
**Nothing generating after a submit?** Check the API logs for `generation_triggered`
(fired) vs `generation_trigger_failed` (couldn't RunTask — usually the `ecs` VPC
endpoint not `available`, or the `run-generator` IAM policy missing on
`scrollwise-api-lambdas`). Then check a stopped task's exit code
(`aws ecs list-tasks --cluster scrollwise --desired-status STOPPED …` → `describe-tasks`);
`CannotPullContainerError` = the public-subnet egress / image isn't right.
**Env vars** live in the **task definition** (immutable → new revision via `set-env.sh`),
NOT a `.env` and NOT Lambda config. `DATABASE_URL` is plain psycopg (not `+asyncpg`).

## Troubleshooting

**API 500 / "Unhandled" / timeouts — read the logs.** Lambda logs to CloudWatch
group `/aws/lambda/scrollwise-api`:
```bash
aws logs tail /aws/lambda/scrollwise-api --profile scrollwise --region us-east-1 --since 15m --follow
```
Fast isolation without API Gateway — invoke the function directly:
```bash
aws lambda invoke --profile scrollwise --region us-east-1 --function-name scrollwise-api \
  --cli-binary-format raw-in-base64-out \
  --payload '{"version":"2.0","rawPath":"/health","requestContext":{"http":{"method":"GET","path":"/health"}},"isBase64Encoded":false}' \
  /tmp/out.json && cat /tmp/out.json
```
- boots but every request 500s → usually the **DB**: check `DATABASE_URL` env var
  uses `postgresql+asyncpg://` and points at the RDS host; confirm the Lambda SG
  `sg-0f0cc540888358d41` is still allowed into RDS SG `sg-0ec7b63d9aad80020` on 5432.
- import-time crash (first line of logs) → a bad env var or a missing dep in the image.

**Check / change the Lambda's config (env vars):**
```bash
aws lambda get-function-configuration --profile scrollwise --region us-east-1 \
  --function-name scrollwise-api --query 'Environment.Variables'
aws lambda update-function-configuration --profile scrollwise --region us-east-1 \
  --function-name scrollwise-api --environment 'Variables={...}'   # note: REPLACES the whole map
```
Secret values (JWT_SECRET, RDS password/URL) are in the gitignored `infra/passwords`.

**Reach RDS by hand.** RDS is private — connect from inside the VPC. The EC2
generator box is the jump host (its SG is allowed into RDS). SSH in, then
`psql -h scrollwise-pg.c29wyqmsy86m.us-east-1.rds.amazonaws.com -U scrollwise -d scrollwise`.

**Cold starts.** First hit after idle is slow (VPC ENI + container init +
SQLAlchemy). Warm calls are fast. Only mitigate (provisioned concurrency / slimmer
image / more memory) if real users notice.

**Custom domain / DNS.** `app.` and `api.` are CNAMEs at **IONOS** (not Route 53).
`api.scrollwise.net` → `d-25fxrdt7b2.execute-api.us-east-1.amazonaws.com`;
`app.scrollwise.net` → `dkflt0h7ibwhb.cloudfront.net`. "Domain resolves but 403/SSL
error" → the alias/cert isn't on the distribution/API-GW domain; "doesn't resolve"
→ the IONOS record is missing.

## Not covered here
Building the stack from scratch (see the `infra/aws/**/README.md` walkthroughs) and
the **EC2 teardown** still pending in PROGRESS.md §3 (the generator is on Fargate
now; the old `scrollwise-drain` EC2 box is being decommissioned — `scrollwise-drain`
skill covers that box until it's gone).
