# Content-generator on ECS/Fargate (serverless, event-driven)

Moves `services/content-generator` off the always-on EC2 `scrollwise-drain`
systemd poller to an **event-driven Fargate task** — the last step to terminate
the EC2 box. See `infra/aws/PROGRESS.md` §3 for the decision (Fargate over Lambda,
because the roadmap — LLM-synthesized templates, generated SVG/Lottie assets,
bigger topics — makes generation long, variable, and LLM-bound, which hits
Lambda's 15-min cap and pays for idle Bedrock wait per invocation).

```
apps/api  (POST /me/prompts)
        │  inserts user_prompts row, then ecs:RunTask   ← event-driven, no scheduler
        ▼
ECS Fargate task  scrollwise-generator  (arm64 container)
        │  drains pending user_prompts via `drain_prompts --once`, then exits
        ├──────────────► RDS Postgres (writes posts/curricula)   [via VPC]
        └──────────────► Bedrock (LLM)   [via bedrock-runtime interface VPC endpoint]
```

**Event-driven, not polled.** The API fires one `RunTask` per submit. Because the
task drains *all* pending rows (`SKIP LOCKED`), it's self-healing: concurrent
submits launch concurrent tasks that split the queue without double-processing,
and any prompt whose own trigger was lost is swept up by the next submit's task.
Trade-off vs a scheduler: no periodic safety sweep, so the pathological "one
prompt, its trigger failed, and no further submits ever arrive" case leaves that
row pending. Acceptable at current volume; add a *slow* safety schedule later if
it ever matters.

> **Networking: public subnet, no NAT, no per-service endpoints.** The task runs
> in a **public subnet with a public IP**, so it reaches ECR / Bedrock / Logs over
> the free **Internet Gateway** — no NAT, no ecr/logs/bedrock endpoints. Security
> is unchanged: the security group blocks all inbound; "public" only means the
> task can reach *out*. The public IP is billed only while a task runs
> (~cents/mo). The one kept interface endpoint is **`ecs`** (~$7/mo), so the
> private-subnet **API Lambda** can call `RunTask`. `setup.sh` also deletes any
> paid ecr/logs/bedrock endpoints a previous endpoint-based run created.

## One-command provision
Everything below (Steps 1–6, idempotent + safe to re-run) is scripted:
```bash
export DB_PASS='<rds-scrollwise-password>'     # from infra/passwords (gitignored)
./infra/aws/generator/setup.sh                 # add SMOKE_TEST=1 to also fire one task
```
The step-by-step below is the same commands, if you'd rather run them by hand or
understand what the script does. It does **not** tear down EC2 — that's the manual
checklist at the end.

## Code already in the repo
- `services/content-generator/Dockerfile` — plain arm64 container (NOT the Lambda
  base image), `CMD python -m scripts.drain_prompts --once`.
- `services/content-generator/.dockerignore` — keeps the image lean.
- `generators/prompt_consumer.py` — `drain_once()` / `SKIP LOCKED` claim already
  exist; `--once` mode already exists. No app change needed for this migration.
- `infra/aws/generator/task-definition.template.json` — the Fargate task def
  (fill in the two role ARNs + DB password, then register).

## Decisions baked into this guide
- **arm64 (Graviton)** — ~20% cheaper on Fargate. Build native on an M-series Mac.
- **Scheduled `RunTask`, not an always-on ECS service** — that would just recreate
  the EC2 always-on model. SQS-driven `RunTask` is the later lower-latency step.
- **Reuse the API's Lambda SG `sg-0f0cc540888358d41`** for the task — it's already
  allowed into the RDS SG on 5432, so no new RDS ingress rule is needed.
- **`bedrock-runtime` interface VPC endpoint** instead of a NAT (~$7/mo vs ~$32/mo).
- **v1 config = task-def env vars** (mirrors the API). DB password lives in the
  gitignored `infra/passwords`; moving `DATABASE_URL` to Secrets Manager (`secrets`
  block in the task def) is the later hardening step.

---

## Prerequisites
```bash
export AWS_PROFILE=scrollwise
export AWS_REGION=us-east-1
export ACCOUNT_ID=339140804013
# from infra/passwords (gitignored):
export DB_PASS='<rds-scrollwise-password>'
```
Docker running; `aws sts get-caller-identity --profile scrollwise` works (the dev
shell's creds were expired on 2026-06-30 — refresh first). Established infra:

| Thing | Value |
|---|---|
| VPC | `vpc-043d8285225718949` |
| Private subnets (1a / 1b) | `subnet-0381b8136594335d2` / `subnet-047ca5c90a3dcfb4d` |
| Task SG (reused API Lambda SG) | `sg-0f0cc540888358d41` |
| RDS SG | `sg-0ec7b63d9aad80020` (already allows 5432 from the task SG) |
| RDS endpoint | `scrollwise-pg.c29wyqmsy86m.us-east-1.rds.amazonaws.com:5432/scrollwise` |

---

## Step 1 — ECR repo + build/push the image
**What:** publish the arm64 generator image.
```bash
aws ecr create-repository --repository-name scrollwise-generator \
  --profile "$AWS_PROFILE" --region "$AWS_REGION"

aws ecr get-login-password --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# native arm64 on an M-series Mac
docker build --platform linux/arm64 -t scrollwise-generator services/content-generator
docker tag scrollwise-generator:latest "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/scrollwise-generator:latest"
docker push "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/scrollwise-generator:latest"
```
**Expected:** repo URI, then a successful push with a digest.

## Steps 2–5 — what `setup.sh` provisions (run the script; details here for reference)
- **Step 2 — networking (public subnet + one endpoint):** auto-discovers a public
  subnet (a subnet whose route table points `0.0.0.0/0` at the Internet Gateway;
  override with `PUBLIC_SUBNETS=…`) for the task to run in with a public IP. Keeps
  a single `ecs` interface endpoint (SG `scrollwise-vpce`, 443 from
  `sg-0f0cc540888358d41`) in the private subnets so the API Lambda can `RunTask`,
  and deletes any paid ecr/logs/bedrock endpoints from an earlier run.
- **Step 3 — IAM roles:** `scrollwise-generator-exec` (ECR pull + logs, via the
  managed `AmazonECSTaskExecutionRolePolicy`) and `scrollwise-generator-task`
  (`bedrock:InvokeModel`, replacing the old EC2 instance-role access).
- **Step 4 — task def:** log group `/ecs/scrollwise-generator`, ECS cluster
  `scrollwise`, and `register-task-definition` from
  `task-definition.template.json` with `<DB_PASS>` filled in (the temp file is
  shredded after — it holds the password).

## Step 5 — smoke-test one run by hand (or `SMOKE_TEST=1 setup.sh`)
```bash
aws ecs run-task --cluster scrollwise --launch-type FARGATE \
  --task-definition scrollwise-generator \
  --network-configuration 'awsvpcConfiguration={subnets=[subnet-0381b8136594335d2,subnet-047ca5c90a3dcfb4d],securityGroups=[sg-0f0cc540888358d41],assignPublicIp=DISABLED}' \
  --profile "$AWS_PROFILE" --region "$AWS_REGION"
```
**Verify:** `aws logs tail /ecs/scrollwise-generator --since 5m --follow` shows
`drain_loop_start` → `prompt_claimed`/`prompt_ready`; the task exits `0`. Submit a
prompt via the API first so there's something to drain. **If the task fails at
`CannotPullContainerError`, the VPC endpoints (Step 2) aren't in place.**

## Step 6 — event-driven trigger (the API fires RunTask; NO scheduler)
`setup.sh` deletes any old `scrollwise-generator-drain` schedule and attaches a
scoped `run-generator` policy (`ecs:RunTask` + guarded `iam:PassRole`) to the API
Lambda role, then prints a ready-to-run `infra/aws/api/set-env.sh` command (with
the discovered public subnet filled in) to set the trigger env vars on the
`scrollwise-api` Lambda — merge-safe, so existing vars survive:
```
ECS_CLUSTER=scrollwise
ECS_TASK_DEFINITION=scrollwise-generator
ECS_SUBNETS=<public-subnet-id(s), comma-separated>   # printed by setup.sh
ECS_SECURITY_GROUPS=sg-0f0cc540888358d41
ECS_ASSIGN_PUBLIC_IP=ENABLED                          # required for public-subnet egress
```
> Do **not** set `AWS_REGION` — it's a reserved Lambda var, auto-set. Leaving
> `ECS_CLUSTER` unset (dev) disables the trigger: `enqueue()` no-ops and a local
> poller drains the queue instead.

The API code seam is `apps/api/app/services/generation_service.py` (`enqueue`),
called from `POST /me/prompts`. It never raises — the `user_prompts` row is the
durable queue, so a failed trigger just means the row waits for the next submit's
task to sweep it up.

## Changing the task's env vars
The generator's env lives in the **task definition** (`task-definition.template.json`
→ `environment`), not a `.env`. Two ways to change it:
- **Permanent:** edit the template, then `setup.sh` (re-registers a new revision).
- **Quick/one-off:** `infra/aws/generator/set-env.sh KEY=VALUE …` — merges onto the
  latest revision and registers a new one (next task picks it up). ⚠️ `setup.sh`
  re-registers from the template, so put permanent vars there too or they're lost.

## Health check
`infra/aws/generator/healthcheck.sh` — read-only, no prompt needed. Verifies the
task def, the `ecs` endpoint, the API's `ECS_*` trigger env, the last task's exit
code, and recent `prompt_ready`/`prompt_failed` log counts; exits non-zero on any
hard failure.
```bash
./infra/aws/generator/healthcheck.sh
```

---

## Cutover + EC2 teardown checklist
1. `setup.sh` run + API env vars set + API image redeployed; a submitted prompt
   drains end-to-end into RDS via a Fargate task (watch the log group).
2. Run in parallel with EC2 `scrollwise-drain` briefly (SKIP LOCKED makes this
   safe), then on the EC2 box: `sudo systemctl stop scrollwise-drain`.
3. Verify only one drainer active (no double-generation) and the feed still fills.
4. **Final `pg_dump`** of the EC2-local Postgres (the cold backup) — keep it.
5. Terminate EC2 `i-07f9dd1d8f1111f92`, release its EIP, remove local
   Postgres/Caddy/old uvicorn.
6. Clean up: EC2 SG `sg-03eb9008178146650` ingress on RDS, the `scrollwise-drain`
   unit, `infra/ec2_*setup.sh` refs. Update `ARCHITECTURE.md` (drop the EC2 box).

Redeploy later (roll the image): repeat Step 1's build/push. The next
event-triggered task pulls `:latest`; force a new task-def revision only if
env/CMD changed.

## Future (not built now)
- **Safety-net schedule** — a *slow* (e.g. 15-min) EventBridge schedule as a
  backstop for a lost trigger + `recover_stuck`. Omitted per the event-driven-only
  decision; add if stuck-prompt tail risk ever bites.
- **SQS-driven `RunTask`** — a durable buffer + DLQ in front, if you outgrow the
  DB-as-queue (retries/poison handling) at higher volume.
- **Step Functions** — only if generation needs real orchestration (staged
  checkpointing, human-approval pause on synthesized templates). Not before.
- **CI/CD** — a `deploy-generator.yml` mirroring `deploy-api.yml` (push to master
  touching `services/content-generator/**` → buildx arm64 → ECR). Add the IAM user
  + repo secrets when wiring it.

---

## Cost (rough, us-east-1)
| Item | Billed | Cost |
|---|---|---|
| Public subnet + Internet Gateway | — | **free** |
| Public IPv4 on the task | only while a task runs (~minutes) | **~cents/mo** |
| Fargate task (0.5 vCPU / 1 GB, arm64), per-submit runs | task runtime | ~$1–3/mo |
| `ecs` interface endpoint (for the API's RunTask) | 24/7 | **~$7/mo** |
| CloudWatch logs | usage | ~$0–1/mo |
| Bedrock tokens | usage | the real spend (same as today) |
| **EC2 removed** | — | **−$10–15/mo saved** |

**≈ $7–10/mo** — vs ~$32 (NAT) or ~$35 (five interface endpoints). The trick: the
public IP is billed only for the *minutes a task runs*, while NAT/endpoints bill
24/7 for being available — a big win for a bursty, scale-to-zero workload. The EC2
teardown makes this net cost-negative. (If you later need the API to reach the
public internet — e.g. Google OIDC — that's a separate decision; a NAT would cover
it, but the generator itself no longer needs one.)
