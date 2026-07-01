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
                              │  writes posts/curricula (still EC2 — see below)
                    EC2  content_generator_server (i-07f9dd1d8f1111f92)          GEN
                       systemd  scrollwise-drain  →  Bedrock (LLM)               (batch worker)
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

### Content-generator — EC2 drain worker  ⚠️ not yet serverless
- Producer (`services/content-generator`) runs as the **`scrollwise-drain`**
  systemd service on **EC2 `content_generator_server`** (`/opt/ScrollWise`).
- Polls the `user_prompts` queue, generates curricula + posts via **Bedrock**, and
  writes them to the shared RDS DB (repointed 2026-06-30). Uses the plain psycopg
  `DATABASE_URL` (not asyncpg). See the `scrollwise-drain` skill for ops.
- **This is the last non-serverless piece and the last reason the EC2 box exists.**
  Plan to move it to Lambda/Fargate and terminate EC2: PROGRESS.md §3.

## The shared database is the contract
RDS DB **`scrollwise`** is shared by the API and the generator. The generator
**owns** `posts` + `curricula` (writes them); the API reads them and owns
everything else (users, prompts, progress). Schema changes to the contract tables
are cross-component — canonical DDL is
`services/content-generator/storage/schema.sql`. The old local Postgres on EC2 is
now a **cold backup** (do not delete until the generator is serverless + verified).

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
| EC2 (generator) | i-07f9dd1d8f1111f92 |
```
