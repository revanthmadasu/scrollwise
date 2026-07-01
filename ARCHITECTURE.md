# ScrollWise — current deployed architecture

As-built snapshot of what is running in AWS (account **339140804013**, region
**us-east-1**). For the migration history and what's still in flight, see
[`infra/aws/PROGRESS.md`](infra/aws/PROGRESS.md). For the design rationale of each
serverless piece, see [`infra/aws/api/README.md`](infra/aws/api/README.md) and
[`infra/aws/web/README.md`](infra/aws/web/README.md).

Last updated: 2026-07-01.

```
                          ┌──────────────────────────────────────────────┐
  app.scrollwise.net ───► │ CloudFront (E3RSA4VCIHJJ90) ──► S3 (private)  │   WEB
                          │   dkflt0h7ibwhb.cloudfront.net                │   (static SPA)
                          └──────────────────────────────────────────────┘

  api.scrollwise.net ───► API Gateway HTTP API (4un2b4m7ij)                    API
                              │  $default stage                                (FastAPI)
                              ▼
                          Lambda  scrollwise-api  (container image, arm64)
                              │  VPC: private subnets 1a/1b, SG sg-0f0cc540888358d41
                              ▼
                    ┌─────────────────────────────────────────┐
                    │ RDS PostgreSQL 16  scrollwise-pg          │  SHARED DB
                    │  db.t4g.micro · pgvector · private        │  (the contract)
                    │  DB "scrollwise" · SG sg-0ec7b63d9aad80020│
                    └─────────────────────────────────────────┘
                              ▲
                              │  writes posts/curricula
  apps/api ──RunTask──►  ECS Fargate task  scrollwise-generator (arm64)          GEN
  (on prompt submit)       public subnet · drains user_prompts · → Bedrock (LLM)  (event-driven)
```

## Components

### Web — S3 + CloudFront  ✅ live
- Static SPA (`apps/web`, Vite) built and synced to **S3 `scrollwise-web-bundle-prod`**
  (private, OAC `E1UQTYDP33AC79`).
- **CloudFront `E3RSA4VCIHJJ90`** (`dkflt0h7ibwhb.cloudfront.net`) serves it; alias
  **`app.scrollwise.net`**, ACM cert `…/ea31dbf8`.
- Calls the API directly at `https://api.scrollwise.net` (CORS, JWT bearer — no cookies).
- Deploy: [`infra/aws/web/deploy.sh`](infra/aws/web/deploy.sh) (build → S3 sync →
  CloudFront invalidate). CI: [`.github/workflows/deploy-web.yml`](.github/workflows/deploy-web.yml).

### API — API Gateway + Lambda + RDS  ✅ live
- **FastAPI** (`apps/api`) runs unchanged on Lambda via **Mangum**
  (`app/lambda_handler.py`). Same `app.main:app` as dev uvicorn.
- Packaged as an **arm64 container image** in ECR `scrollwise-api`, on Lambda
  **`scrollwise-api`** (512 MB / 30 s, role `scrollwise-api-lambda` +
  `AWSLambdaVPCAccessExecutionRole`).
- Attached to the **VPC** (private subnets 1a/1b, SG `sg-0f0cc540888358d41`) so it
  can reach RDS. **No NAT Gateway** — the API makes no outbound internet calls
  (Google OIDC is off; `GOOGLE_CLIENT_ID` unset → the only would-be egress,
  `app/services/google_oauth.py`'s JWKS fetch, is short-circuited).
- Fronted by **API Gateway HTTP API `4un2b4m7ij`**, custom domain
  **`api.scrollwise.net`** (regional cert `…/24dfbb94`, target
  `d-25fxrdt7b2.execute-api.us-east-1.amazonaws.com`).
- Config is **Lambda env vars** (`DATABASE_URL` asyncpg, `JWT_SECRET`, JWT TTLs,
  `CORS_ORIGINS=https://app.scrollwise.net`). Secrets Manager is a later hardening
  step. CI scaffolded: [`.github/workflows/deploy-api.yml`](.github/workflows/deploy-api.yml).

### Content-generator — ECS/Fargate task  ✅ serverless (event-driven)
- Producer (`services/content-generator`) runs as an **arm64 Fargate task**
  `scrollwise-generator` (ECS cluster `scrollwise`), **not** a poller.
- **Event-driven:** on prompt submit, `apps/api` fires `ecs:RunTask`
  (`app/services/generation_service.py`). The task drains pending `user_prompts`
  via `drain_prompts --once`, writes curricula + posts to RDS via **Bedrock**, and
  exits. `SKIP LOCKED` makes concurrent tasks safe + self-healing. Uses the plain
  psycopg `DATABASE_URL` (not asyncpg).
- **Networking:** runs in a **public subnet** with a public IP → free egress to
  ECR/Bedrock/Logs via the Internet Gateway (no NAT). One `ecs` interface endpoint
  lets the private-subnet API Lambda call RunTask. Task reuses SG
  `sg-0f0cc540888358d41`; task role has `bedrock:InvokeModel`.
- Ops + all resource ids: `infra/aws/generator/` (`setup.sh`, `set-env.sh`,
  `deploy.sh`→image, `healthcheck.sh`) and the `scrollwise-serverless` skill.
- ⏳ **EC2 teardown pending:** the old `scrollwise-drain` box
  (`i-07f9dd1d8f1111f92`) is being decommissioned — see PROGRESS.md §3. Until then
  its local Postgres remains a cold backup.

## The shared database is the contract
RDS DB **`scrollwise`** is shared by the API and the generator. The generator
**owns** `posts` + `curricula` (writes them); the API reads them and owns
everything else (users, prompts, progress). Schema changes to the contract tables
are cross-component — canonical DDL is
`services/content-generator/storage/schema.sql`. Both the API (asyncpg) and the
Fargate generator (psycopg) point at this RDS. The old local Postgres on EC2 is a
**cold backup** — keep it until the EC2 teardown is done (take a final `pg_dump` first).

## DNS (IONOS — not Route 53)
`scrollwise.net` nameservers are IONOS (`ns*.ui-dns.*`); all records are managed in
the IONOS panel. Live records: `app` → CloudFront, `api` → API Gateway domain, plus
the two ACM validation CNAMEs.

## Resource quick-reference
| Thing | Value |
|---|---|
| Account / region | 339140804013 / us-east-1 |
| VPC (shared) | vpc-043d8285225718949 |
| Private subnets | subnet-0381b8136594335d2 (1a), subnet-047ca5c90a3dcfb4d (1b) |
| RDS | scrollwise-pg.c29wyqmsy86m.us-east-1.rds.amazonaws.com:5432/scrollwise |
| RDS SG / Lambda SG / EC2 SG | sg-0ec7b63d9aad80020 / sg-0f0cc540888358d41 / sg-03eb9008178146650 |
| API Gateway | 4un2b4m7ij (api.scrollwise.net) |
| CloudFront | E3RSA4VCIHJJ90 (app.scrollwise.net) |
| ECR / Lambda (API) | scrollwise-api / scrollwise-api |
| ECR / ECS (generator) | scrollwise-generator / cluster `scrollwise`, task-def family `scrollwise-generator` |
| Generator roles | scrollwise-generator-exec (pull+logs), scrollwise-generator-task (bedrock) |
| Generator `ecs` VPC endpoint SG | scrollwise-vpce |
| EC2 (generator, ⏳ teardown pending) | i-07f9dd1d8f1111f92 |
```
