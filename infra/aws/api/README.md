# Backend API on Lambda (serverless)

Migrates `apps/api` (FastAPI) from the always-on EC2/uvicorn process to
**API Gateway → Lambda**, with the shared Postgres moved off the EC2 box to
**managed RDS Postgres** (so a Lambda can actually reach it).

```
app.scrollwise.net  → CloudFront → S3                     (UI — already done)
api.scrollwise.net  → API Gateway (HTTP API) → Lambda     (FastAPI via Mangum)
                                                 │
                                                 ▼  (inside a VPC)
                                   RDS Postgres + pgvector  ← shared with the generator
                                   (optionally via RDS Proxy)
```

## Code changes already in the repo (DB-independent)

- `apps/api/app/lambda_handler.py` — Mangum adapter; `handler` is the Lambda entry.
- `apps/api/Dockerfile` — Lambda container image (Amazon Linux base → correct
  native wheels for asyncpg/bcrypt).
- `apps/api/.dockerignore` — keeps the image lean.
- `apps/api/requirements.txt` — adds `mangum`.
- `apps/api/app/db.py` — `pool_pre_ping=True` for Lambda freeze/thaw resilience.

The FastAPI app itself is unchanged — uvicorn (dev) and Lambda (prod) run the
same `app.main:app`.

## Decisions baked into this guide

- **RDS PostgreSQL, `db.t4g.micro`** to start (cheap; pgvector available). Aurora
  Serverless v2 is the scale-up path — same steps, different create command.
- **API Gateway HTTP API** (v2) — cheaper/simpler than REST API, fine for a
  Lambda-proxy FastAPI.
- **Container image** packaging (not zip), because of native deps.
- **The content-generator must repoint at RDS too** — it shares this DB. Don't
  finish the cutover until both the API and the generator use the RDS URL.

---

## Prerequisites

```bash
export AWS_REGION=us-east-1
export ACCOUNT_ID=339140804013
export DB_NAME=scrollwise
export DB_USER=scrollwise
# pick a strong password; you'll store it in Secrets Manager later
export DB_PASS='<generate-a-strong-one>'
```
- AWS CLI v2 authenticated; Docker installed (for the image build).
- Know your EC2's VPC + subnets (RDS and Lambda should live in the same VPC).

---

## Step 1 — Create the RDS Postgres instance

**What:** a managed Postgres the Lambda (and the generator) can reach over the VPC.
**Run** (substitute your VPC's subnet group / security group, see notes):
```bash
aws rds create-db-instance \
  --db-instance-identifier scrollwise-pg \
  --engine postgres --engine-version 16 \
  --db-instance-class db.t4g.micro \
  --allocated-storage 20 --storage-type gp3 \
  --db-name "$DB_NAME" \
  --master-username "$DB_USER" --master-user-password "$DB_PASS" \
  --vpc-security-group-ids sg-XXXXXXXX \
  --no-publicly-accessible \
  --backup-retention-period 7 \
  --region "$AWS_REGION"
```
**Expected output:** JSON with `DBInstanceStatus: creating`. Wait ~5–10 min:
```bash
aws rds wait db-instance-available --db-instance-identifier scrollwise-pg --region "$AWS_REGION"
aws rds describe-db-instances --db-instance-identifier scrollwise-pg \
  --query 'DBInstances[0].Endpoint.Address' --output text --region "$AWS_REGION"
```
Save that endpoint as `DB_HOST`.

**Notes:**
- Put RDS in the **same VPC** as the Lambda (you'll attach the Lambda in Step 7).
  Its security group must allow inbound `5432` from the Lambda's security group.
- `--no-publicly-accessible` keeps it private. For the one-time data migration and
  Alembic you'll reach it from inside the VPC (the EC2 box works as a jump host).

## Step 2 — Enable pgvector

**What:** the `vector(1024)` columns the contract uses.
**Run** (from somewhere that can reach RDS — e.g. the EC2 box):
```bash
psql "postgresql://$DB_USER:$DB_PASS@$DB_HOST:5432/$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;"
```
**Expected output:** `CREATE EXTENSION`. (RDS Postgres ships pgvector; no install.)

## Step 3 — Migrate the data off EC2 Postgres

**What:** copy the existing DB (posts, curricula, users, …) into RDS.
**Run on the EC2 box:**
```bash
# dump the local DB the generator/API use today
sudo -u postgres pg_dump --no-owner --no-privileges "$DB_NAME" > scrollwise.sql

# restore into RDS
psql "postgresql://$DB_USER:$DB_PASS@$DB_HOST:5432/$DB_NAME" < scrollwise.sql
```
**Expected output:** a stream of `CREATE TABLE` / `COPY` lines, no errors.
**Verify:** `psql <rds-url> -c "\dt"` lists the tables and
`select count(*) from posts;` matches the old DB.

> Do this during a quiet window, or stop the generator first
> (`sudo systemctl stop scrollwise-drain`) so no writes are lost mid-dump.

## Step 4 — (Optional, recommended) RDS Proxy

**What:** pools connections so many concurrent Lambdas don't exhaust Postgres.
Skip at very low traffic; add before you scale.
**How:** create an RDS Proxy targeting `scrollwise-pg`, give it a Secrets Manager
secret with the DB creds, allow it in the security group. Then use the **proxy
endpoint** as `DB_HOST` in the Lambda's `DATABASE_URL`.
**Cost:** ~$0.015/vCPU-hr of the instance (~$11/mo for 1 vCPU).

## Step 5 — Store secrets

**What:** keep JWT/Google/DB creds out of code and out of plain Lambda env.
**Run:**
```bash
aws secretsmanager create-secret --name scrollwise/api --region "$AWS_REGION" \
  --secret-string "$(cat <<JSON
{
  "DATABASE_URL": "postgresql+asyncpg://$DB_USER:$DB_PASS@$DB_HOST:5432/$DB_NAME",
  "JWT_SECRET": "<paste a 48-char secret>"
}
JSON
)"
```
**Expected output:** JSON with the secret ARN. The Lambda reads these (Step 7).

> **No `GOOGLE_CLIENT_ID` here — intentional (decision 2026-06-30).** Prod isn't
> using Google sign-in, and leaving `GOOGLE_CLIENT_ID` unset means the API makes
> zero outbound internet calls (the JWKS fetch in `app/services/google_oauth.py`
> short-circuits to "not configured"). That's what lets the VPC Lambda run with
> **no NAT Gateway**. Only add Google creds back if you also add egress (a NAT).

> `DATABASE_URL` MUST use the `postgresql+asyncpg://` driver prefix — that's what
> the API's async engine expects.

## Step 6 — Build + push the container image to ECR

**What:** publish the Lambda image.
**Run:**
```bash
aws ecr create-repository --repository-name scrollwise-api --region "$AWS_REGION"

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# build for the Lambda runtime arch (amd64) from the apps/api dir
docker build --platform linux/amd64 -t scrollwise-api apps/api

docker tag scrollwise-api:latest "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/scrollwise-api:latest"
docker push "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/scrollwise-api:latest"
```
**Expected output:** ECR repo URI, then a successful push with a digest.

## Step 7 — Create the Lambda function

**What:** the function that runs FastAPI, attached to the VPC so it can reach RDS.
**Prereqs:** an execution role with `AWSLambdaVPCAccessExecutionRole` +
permission to read the `scrollwise/api` secret.
**Run:**
```bash
aws lambda create-function --function-name scrollwise-api --region "$AWS_REGION" \
  --package-type Image \
  --code ImageUri="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/scrollwise-api:latest" \
  --role "arn:aws:iam::$ACCOUNT_ID:role/scrollwise-api-lambdas" \
  --timeout 30 --memory-size 512 \
  --vpc-config SubnetIds=subnet-AAAA,subnet-BBBB,SecurityGroupIds=sg-LAMBDA \
  --environment "Variables={CORS_ORIGINS=https://app.scrollwise.net}"
```
**Expected output:** function ARN, `State: Pending` → `Active`.

**Two things that bite people here:**
- **VPC = no internet by default — and that's fine for us.** A VPC Lambda can reach
  RDS but NOT the public internet. The API's only would-be outbound call is the
  Google JWKS fetch, which is disabled while `GOOGLE_CLIENT_ID` is unset (the
  decision for prod). So put the Lambda in the VPC with **NO NAT Gateway**. If you
  ever enable Google sign-in, you'll also need egress (private subnets + a NAT).
- **Secrets:** wire the `scrollwise/api` secret into the function — either inject
  as env vars at deploy time, or read it at cold start. Pydantic settings pick up
  the env var names directly (`DATABASE_URL`, `JWT_SECRET`, …).

## Step 8 — Run Alembic migrations against RDS

**What:** create/upgrade the API-owned tables in RDS.
**Run** (from your machine or the EC2 box, with a SYNC psycopg URL — Alembic is
sync; the data migration in Step 3 already moved existing tables, this just
ensures `alembic_version` + any pending migrations):
```bash
cd apps/api
DATABASE_URL="postgresql+asyncpg://$DB_USER:$DB_PASS@$DB_HOST:5432/$DB_NAME" \
  alembic upgrade head
```
**Expected output:** `Running upgrade … -> …` then no errors. (If Step 3 already
restored everything, Alembic may just stamp head.)

## Step 9 — API Gateway (HTTP API) → Lambda

**What:** the public HTTP front door.
**Run:**
```bash
aws apigatewayv2 create-api --name scrollwise-api --protocol-type HTTP \
  --target "arn:aws:lambda:$AWS_REGION:$ACCOUNT_ID:function:scrollwise-api" \
  --region "$AWS_REGION"
```
`--target` auto-creates the integration, a default route (`$default`), and a
stage, and you'll still need to add the Lambda invoke permission:
```bash
aws lambda add-permission --function-name scrollwise-api --region "$AWS_REGION" \
  --statement-id apigw --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:$AWS_REGION:$ACCOUNT_ID:<api-id>/*/*"
```
**Expected output:** an `ApiEndpoint` like `https://<id>.execute-api.<region>.amazonaws.com`.
**Verify:** `curl https://<id>.execute-api.<region>.amazonaws.com/health` →
`{"status":"ok"}`.

## Step 10 — Custom domain `api.scrollwise.net`

**What:** map your domain to the HTTP API.
1. **ACM cert** for `api.scrollwise.net` in **this region** (HTTP API custom
   domains use a regional cert — NOT the us-east-1-for-CloudFront rule):
   ```bash
   aws acm request-certificate --region "$AWS_REGION" \
     --domain-name api.scrollwise.net --validation-method DNS
   ```
   Add the CNAME it returns to IONOS; wait for `ISSUED`.
2. **Domain + mapping:**
   ```bash
   aws apigatewayv2 create-domain-name --domain-name api.scrollwise.net \
     --domain-name-configurations CertificateArn=<regional-cert-arn> --region "$AWS_REGION"
   aws apigatewayv2 create-api-mapping --domain-name api.scrollwise.net \
     --api-id <api-id> --stage '$default' --region "$AWS_REGION"
   ```
3. **DNS at IONOS:** CNAME `api.scrollwise.net` → the API Gateway domain's
   `ApiGatewayDomainName` (from `create-domain-name` output).

**Expected output:** `curl https://api.scrollwise.net/health` → `{"status":"ok"}`.

## Step 11 — CORS + repoint the generator

- **CORS:** the Lambda's `CORS_ORIGINS` env already allows `https://app.scrollwise.net`
  (Step 7). FastAPI's `CORSMiddleware` handles it — no API Gateway CORS needed.
- **Generator:** update the EC2 drain worker's `DATABASE_URL` (and the generator's
  `DB_BACKEND=postgres`) to the **RDS** endpoint, then restart it:
  `sudo systemctl restart scrollwise-drain`. Both halves must use RDS now.

## Updating env vars later — `set-env.sh`

`aws lambda update-function-configuration --environment` **replaces the entire env
map**, so a hand-edit that forgets a key silently wipes `DATABASE_URL`/`JWT_SECRET`.
Use **`infra/aws/api/set-env.sh KEY=VALUE …`** instead — it fetches the current map,
overlays your keys, and applies the merge (skips the reserved `AWS_REGION`). Example
(the event-driven content-generator trigger; `infra/aws/generator/setup.sh` prints
this line pre-filled):
```bash
infra/aws/api/set-env.sh \
  ECS_CLUSTER=scrollwise ECS_TASK_DEFINITION=scrollwise-generator \
  ECS_SUBNETS=<public-subnet> ECS_SECURITY_GROUPS=sg-0f0cc540888358d41 \
  ECS_ASSIGN_PUBLIC_IP=ENABLED
```

## Cutover checklist

1. RDS up, pgvector enabled, data restored (Steps 1–3).
2. Generator repointed at RDS and writing there (Step 11).
3. Lambda deployed, `/health` green via API Gateway (Steps 6–9).
4. `api.scrollwise.net` resolves to API Gateway (Step 10).
5. Frontend `VITE_API_BASE=https://api.scrollwise.net` (already set).
6. Smoke test: log in, load the feed, submit a prompt end-to-end.
7. Decommission the EC2 uvicorn/Caddy-API once stable (keep the box if it still
   runs the generator — until that's serverless too).

---

## Cost (rough, us-east-1, launch scale)

| Item | Cost |
|---|---|
| Lambda (512 MB, low traffic) | free tier covers ~1M req/mo → **~$0** |
| API Gateway HTTP API | $1.00 / million requests → **~$0–1/mo** |
| **RDS `db.t4g.micro`** | ~**$12–15/mo** (on-demand; the main cost) |
| RDS storage (20 GB gp3) | ~$2.30/mo |
| NAT Gateway | **$0 — not used** (no Google OIDC in prod; see Step 7) |
| RDS Proxy (optional) | ~$11/mo |
| Secrets Manager | $0.40/secret/mo |
| ACM cert | free |

**Reality check:** the always-on pieces (RDS, and NAT if you need it) dominate —
this is **~$15/mo without NAT, ~$45+/mo with NAT**. At low, spiky traffic a small
EC2/App Runner running uvicorn can be cheaper than Lambda+RDS+NAT. The serverless
win here is operational (no servers to patch, autoscaling), not raw cost.

> Avoiding the NAT cost: if you can drop Google OIDC, or fetch Google's JWKS
> through a VPC endpoint / cache it, the Lambda needs no internet and you skip the
> ~$32/mo NAT. Worth designing around.

---

## Redeploying (roll the image)

**`infra/aws/api/deploy.sh`** is the repeatable local deploy — ECR login → build
**arm64** (Graviton) → push → `update-function-code --publish` → wait → `/health`
check. Run it after any `apps/api` change:
```bash
./infra/aws/api/deploy.sh
```
(The CI workflow below does the same on push to `master`, once wired.)

## CI/CD

Scaffolded: **`.github/workflows/deploy-api.yml`** (push to `master` touching
`apps/api/**`) builds the **arm64** image via buildx+QEMU, pushes to ECR, and
rolls the Lambda with `aws lambda update-function-code --image-uri … --publish`.

To activate (same Option-B static-keys pattern as the web deploy):
1. IAM user `scrollwise-api-deploy` with the least-privilege policy in
   **`infra/aws/api/github-deploy-permissions.json`** (ECR push + this one
   Lambda's update).
2. Create an access key for it → GitHub repo **Secrets**: `AWS_ACCESS_KEY_ID`,
   `AWS_SECRET_ACCESS_KEY`.
3. Region / ECR repo / function name are hardcoded in the workflow's `env:` block
   (`us-east-1` / `scrollwise-api` / `scrollwise-api`) — edit there if they change.

OIDC (no stored keys) is the better long-term option; swap the credentials step
for `role-to-assume` when you set up an OIDC provider.
