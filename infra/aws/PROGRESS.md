# ScrollWise serverless migration — progress & context

Branch: `feature/serverless-lambdas`. Goal: make the three services serverless on
AWS. This file is the running context — what's decided, what's done, the real
resource IDs, and what's left.

Last updated: 2026-06-30.

## Target architecture

```
UI    app.scrollwise.net  → CloudFront → S3 (private)              [web]
API   api.scrollwise.net  → API Gateway (HTTP API) → Lambda        [apps/api]
                                              │
                                              ▼  (VPC)
                                  RDS Postgres + pgvector  ← shared with generator
GEN   content-generator  → (still EC2 drain worker; serverless later)
```

Account: **339140804013** · Region: **us-east-1** · DNS host: **IONOS**
(`ns*.ui-dns.*` nameservers — records are managed in the IONOS panel, NOT Route 53).

---

## 1. Frontend (apps/web) — S3 + CloudFront  [MOSTLY DONE]

Decision: CloudFront serves **UI only** (single S3 origin). No `/api` proxy — the
SPA calls the API directly at `https://api.scrollwise.net` (CORS). Auth uses a JWT
in the `Authorization` header (not cookies), so CORS is simple.

Files: `infra/aws/web/` — `deploy.sh` (build→S3 sync→invalidate),
`distribution-config.json` (filled in), `distribution-config.template.json`,
`github-deploy-permissions.json`, `README.md`.

Real resources created:
| Thing | Value |
|---|---|
| S3 bucket | `scrollwise-web-bundle-prod` (us-east-1, private) |
| OAC id | `E1UQTYDP33AC79` |
| CloudFront distribution id | `E3RSA4VCIHJJ90` |
| CloudFront domain | `dkflt0h7ibwhb.cloudfront.net` |
| Alias (UI domain) | `app.scrollwise.net` |
| ACM cert (app.scrollwise.net) | `arn:aws:acm:us-east-1:339140804013:certificate/ea31dbf8-110b-4d33-a6da-bb18b043f70d` |
| ACM cert (scrollwise.net, unused) | `arn:aws:acm:us-east-1:339140804013:certificate/51f11116-fcc1-4cb3-9c86-51058e3c322b` |

**Still pending for the web to go fully live:**
- [ ] **Validate the `app.scrollwise.net` ACM cert** — add the CNAME at IONOS
      (host `_85156dfb8c25c6d141bf2ed9e0ef41f5.app`, value
      `_da76553854b8f5c08c70c48be2632d05.jkddzztszm.acm-validations.aws`), wait for
      `ISSUED`. The distribution was created, so this may already be done.
- [ ] **Bucket policy** (README Step 6) — allow `E3RSA4VCIHJJ90` to read the
      bucket. Account id `339140804013`, CloudFront ARN has no region.
- [ ] **DNS** — CNAME `app.scrollwise.net` → `dkflt0h7ibwhb.cloudfront.net` at IONOS.
- [ ] **First deploy** — `WEB_BUNDLE_BUILD_BUCKET=scrollwise-web-bundle-prod
      CF_DISTRIBUTION_ID=E3RSA4VCIHJJ90 ./infra/aws/web/deploy.sh`
      (note: NOT the placeholder `E1ABCDEF234567`).
- [ ] Verify: `curl -I https://dkflt0h7ibwhb.cloudfront.net` → 200.

## 1b. Web CI/CD — GitHub Actions  [SCAFFOLDED, NOT WIRED]

Decision: **Option B (stored IAM access keys)**, not OIDC. Repo is public, which is
fine — GitHub secrets are encrypted and not exposed to forks.

File: `.github/workflows/deploy-web.yml` (push to `master` touching `apps/web/**`).

To activate:
- [ ] IAM user `scrollwise-web-deploy` + `github-deploy-permissions.json` policy.
- [ ] Access key → GitHub repo **Secrets**: `AWS_ACCESS_KEY_ID`,
      `AWS_SECRET_ACCESS_KEY`.
- [ ] GitHub repo **Variables**: `AWS_REGION=us-east-1`,
      `WEB_BUNDLE_BUILD_BUCKET=scrollwise-web-bundle-prod`,
      `CF_DISTRIBUTION_ID=E3RSA4VCIHJJ90`,
      `VITE_API_BASE=https://api.scrollwise.net`.

---

## 2. Backend (apps/api) — Lambda + RDS  [✅ LIVE on api.scrollwise.net (2026-07-01)]

FastAPI + async SQLAlchemy. Key constraint: the API **shares its Postgres with the
content-generator**, and that Postgres currently runs **on the EC2 box**. Decision:
**migrate the DB to managed RDS Postgres** so a Lambda can reach it.

Code changes already in the repo (DB-independent, done):
- `apps/api/app/lambda_handler.py` — Mangum adapter (`handler`).
- `apps/api/Dockerfile` + `.dockerignore` — Lambda container image.
- `apps/api/requirements.txt` — added `mangum`.
- `apps/api/app/db.py` — `pool_pre_ping=True` (Lambda freeze/thaw resilience).

Decisions: RDS PostgreSQL `db.t4g.micro` (Aurora SSv2 = scale path) · API Gateway
**HTTP API** · **container image** packaging · API at `api.scrollwise.net`.

Full walkthrough: `infra/aws/api/README.md` (RDS → pgvector → data migration →
Secrets Manager → ECR build/push → VPC Lambda → Alembic → API Gateway → custom
domain → CORS + repoint generator).

**Progress (started 2026-06-30, executed via the `scrollwise` CLI profile / root):**
- [x] RDS instance + pgvector + `pg_dump`/restore from EC2. **DONE** — local
      `content_generator` DB dumped + restored into RDS DB **`scrollwise`**;
      per-table row counts matched. pgvector came over with the dump.
- [x] Repoint the EC2 drain worker `DATABASE_URL` at RDS. **DONE** — edited
      `/opt/ScrollWise/services/content-generator/.env` (`DATABASE_URL` →
      `postgresql://scrollwise:***@<rds>:5432/scrollwise`, `.bak` kept), restarted
      `scrollwise-drain`; `active (running)`, drain loop clean on RDS. **RDS is now
      the single source of truth.** Local EC2 Postgres = cold backup, do not delete yet.
- [~] Secrets Manager `scrollwise/api` — **DEFERRED (v1 uses Lambda env vars).**
      API config lives as encrypted Lambda env vars (`DATABASE_URL` asyncpg,
      `JWT_SECRET` [reused from EC2 so logins survive], TTLs, `CORS_ORIGINS`).
      Secrets Manager rotation is a later hardening step (needs fetch code).
- [x] ECR repo + container build/push. **DONE** — `scrollwise-api` repo, **arm64**
      image (built native on M-series Mac), digest `sha256:57642cce…0c17ea`.
- [x] Lambda (VPC-attached) + execution role. **DONE** — `scrollwise-api`, arm64,
      512MB/30s, role `scrollwise-api-lambda` (+AWSLambdaVPCAccessExecutionRole),
      SG `sg-0f0cc540888358d41`, subnets 1a+1b. `/health` 200 + `/auth/register`
      201 → **RDS reachable through the VPC, verified end-to-end.**
- [x] API Gateway HTTP API. **DONE** — id `4un2b4m7ij`, endpoint
      `https://4un2b4m7ij.execute-api.us-east-1.amazonaws.com` (invoke permission set).
- [~] Custom domain `api.scrollwise.net` (regional ACM cert + IONOS DNS) — IN
      PROGRESS. Cert requested (us-east-1, DNS validation); validation CNAME added
      at IONOS. Waiting for `ISSUED`, then create-domain-name + api-mapping + the
      `api.scrollwise.net` CNAME → ApiGatewayDomainName.
      Cert ARN: `arn:aws:acm:us-east-1:339140804013:certificate/24dfbb94-e37f-4dbf-94bd-d4f8952c7f94`.
      Validation record: `_a56cee9e074a1ec0e165339ed2d9848b.api` →
      `_f977265c4feb4b8fcaa72fc9dbcf9daf.jkddzztszm.acm-validations.aws`.
      API Gateway id `4un2b4m7ij` · endpoint
      `https://4un2b4m7ij.execute-api.us-east-1.amazonaws.com`.
      Cert ISSUED; custom domain created → target
      `d-25fxrdt7b2.execute-api.us-east-1.amazonaws.com`. IONOS CNAME `api` →
      that target (TTL 300). api-mapping to `$default` stage. Then curl
      `https://api.scrollwise.net/health`.
- [x] API CI/CD workflow **SCAFFOLDED (not wired)** — `.github/workflows/deploy-api.yml`
      (push to master touching `apps/api/**`: buildx arm64 → ECR → update Lambda).
      To activate: IAM user `scrollwise-api-deploy` with
      `infra/aws/api/github-deploy-permissions.json`, access key → repo secrets
      `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`. Region/repo/fn are hardcoded in
      the workflow `env:`.
- [ ] Cleanup: delete smoke-test user `lambda-smoketest@example.com` from RDS.
- [ ] Cold start: first hit is slow (VPC ENI + container init). Mitigate later
      (provisioned concurrency / slimmer image) only if it bothers real users.

> **DB name note:** prod RDS DB is **`scrollwise`** (user `scrollwise`), NOT
> `content_generator` (that was the old local name). Both the API's asyncpg URL and
> the generator's psycopg URL point at `…/scrollwise`.

**Real resources created (live):**
| Thing | Value |
|---|---|
| Shared VPC (from EC2 generator) | `vpc-043d8285225718949` |
| EC2 generator instance | `i-07f9dd1d8f1111f92` (content_generator_server) |
| EC2 security group | `sg-03eb9008178146650` |
| Private subnets (1a / 1b) | `subnet-0381b8136594335d2` / `subnet-047ca5c90a3dcfb4d` |
| RDS security group | `sg-0ec7b63d9aad80020` (ingress 5432 from EC2 SG + Lambda SG) |
| Lambda security group | `sg-0f0cc540888358d41` |
| DB subnet group | `scrollwise-db-subnets` (1a + 1b) |
| RDS instance | `scrollwise-pg` · postgres 16 · db.t4g.micro · gp3 20GB · private |
| DB name / master user | `scrollwise` / `scrollwise` (password saved out-of-band → Secrets Mgr) |
| RDS endpoint | `scrollwise-pg.c29wyqmsy86m.us-east-1.rds.amazonaws.com:5432` |

### ⚠️ Open issues to resolve before deploying the backend
1. **NAT Gateway / Google OIDC — RESOLVED 2026-06-30: no NAT.** A VPC Lambda has no
   internet by default. Verified the API's ONLY outbound call is the Google JWKS
   fetch in `app/services/google_oauth.py`, and that fetch only fires when
   `GOOGLE_CLIENT_ID` is set (else it raises "not configured" before any network
   call). Prod isn't using Google sign-in. **Decision: leave `GOOGLE_CLIENT_ID`
   unset on the Lambda (and `VITE_GOOGLE_CLIENT_ID` unset in the web build) → the
   API needs zero internet → put the Lambda in the VPC with NO NAT Gateway.** No
   code change needed (both halves auto-disable Google when the id is unset).
   Email/password JWT auth is fully local. Re-add a NAT only if/when Google
   sign-in is wanted in prod.
2. **Shared DB cutover.** API-Lambda and the generator must point at the SAME RDS.
   Don't decommission EC2 Postgres until both are migrated and verified.
3. **Cost reality.** ~$15/mo (no NAT, per decision above). Serverless win here is
   operational, not necessarily cheaper at low/spiky traffic.

> **Heads-up for whoever picks this up:** AWS CLI creds were expired in the dev
> shell on 2026-06-30 (`aws sts get-caller-identity` → `InvalidClientTokenId`).
> Refresh them (`aws sso login` / new keys) before any RDS/ECR/Lambda/API GW step.

---

## 3. Content-generator — serverless  [NOT STARTED — this is the last EC2 tenant]

**Goal: make generation serverless and then TERMINATE THE EC2 BOX ENTIRELY.**
The RDS migration already moved the DB off EC2 (§2), so the generator is now the
*only* reason `content_generator_server` (`i-07f9dd1d8f1111f92`) still exists.
Once this is done, nothing runs on EC2 and the instance (plus its local Postgres,
Caddy, and the old uvicorn API) can be shut down. The whole platform becomes
Lambda + API Gateway + RDS + S3/CloudFront.

Currently: EC2 `scrollwise-drain` systemd poller (`scripts/drain_prompts.py`,
polls `user_prompts` every 2s; has a `--once` mode; uses Bedrock for the LLM via
the EC2 instance role; writes posts/curricula to RDS).

### Proposed design (least change from what exists)
- **Package** the generator as an **arm64 container-image Lambda** (`scrollwise-generator`),
  same pattern as the API. Own ECR repo `scrollwise-generator`.
- **Trigger:** EventBridge Scheduler (rate ~1 min) → invoke the Lambda in a
  `--once`-style batch that drains pending `user_prompts` and returns. This reuses
  the existing drain logic and keeps the DB-as-queue design; the only change vs the
  systemd poller is a ~1-min latency instead of 2s (fine — generation itself takes
  ~40s for a topic). *Alt:* have `apps/api` publish to SQS on prompt submit and let
  SQS trigger the Lambda (lower latency, but changes the API's generation hand-off).
- **Duration:** observed ~40s to generate a 42-post topic → well under Lambda's
  15-min cap, so plain Lambda works. Only reach for **Fargate/Step Functions** if a
  single batch ever risks >15 min.
- **VPC:** attach to the same private subnets + a client SG allowed into RDS SG
  `sg-0ec7b63d9aad80020` (reuse `sg-0f0cc540888358d41` or a new one).
- **Bedrock egress:** the generator calls **Bedrock**, which is public — and a
  VPC Lambda has no internet (we run no NAT). Add an **interface VPC endpoint for
  `bedrock-runtime`** (~$7/mo, far cheaper than a NAT) so the Lambda reaches Bedrock
  privately. (If image posts get re-enabled — `IMAGE_POSTS_ENABLED`, S3 — add S3 +
  the image model endpoints too. Currently off.)
- **IAM:** execution role with `AWSLambdaVPCAccessExecutionRole` + `bedrock:InvokeModel`
  (replacing today's EC2 instance-role Bedrock access).
- **Config:** env vars mirror the drain `.env` — `DB_BACKEND=postgres`,
  `DATABASE_URL=postgresql://scrollwise:…@<rds>/scrollwise` (plain psycopg, NOT
  asyncpg), `LLM_BACKEND=bedrock`, `IMAGE_POSTS_ENABLED=false`.

### Cutover + EC2 teardown checklist
- [ ] Build/push `scrollwise-generator` image; create the Lambda (VPC, Bedrock endpoint, role).
- [ ] Wire the EventBridge Scheduler trigger; confirm it drains a test prompt end-to-end into RDS.
- [ ] Run in parallel with EC2 `scrollwise-drain` briefly, then **stop** the systemd service.
- [ ] Verify no double-generation (only one drainer active) and the feed still fills.
- [ ] Decommission EC2: stop/terminate `i-07f9dd1d8f1111f92`, release its EIP, remove
      local Postgres/Caddy/uvicorn. **Keep a final `pg_dump` backup first** — the
      local DB has been the cold backup since the RDS cutover.
- [ ] Clean up now-orphaned bits: EC2 SG `sg-03eb9008178146650` ingress rules, the
      `scrollwise-drain` unit, `infra/ec2_*setup.sh` references. Update ARCHITECTURE.md.

---

## Quick reference — established values

```
ACCOUNT_ID            339140804013
AWS_REGION            us-east-1
DNS host              IONOS (ns*.ui-dns.de/.org/.biz/.com)
Web bucket            scrollwise-web-bundle-prod
OAC id                E1UQTYDP33AC79
CloudFront dist id    E3RSA4VCIHJJ90
CloudFront domain     dkflt0h7ibwhb.cloudfront.net
UI domain             app.scrollwise.net           (LIVE)
API domain            api.scrollwise.net           (LIVE)
API Gateway id        4un2b4m7ij
Lambda / ECR (API)    scrollwise-api / scrollwise-api
RDS                   scrollwise-pg.c29wyqmsy86m.us-east-1.rds.amazonaws.com:5432/scrollwise
ACM (app, us-east-1)  ...certificate/ea31dbf8-110b-4d33-a6da-bb18b043f70d
ACM (api, us-east-1)  ...certificate/24dfbb94-e37f-4dbf-94bd-d4f8952c7f94
VITE_API_BASE         https://api.scrollwise.net
```

## Status & next step
**Web ✅ live** (app.scrollwise.net) and **API ✅ live** (api.scrollwise.net,
Lambda+API GW+RDS, DB round-trip verified). See `ARCHITECTURE.md` for the as-built
picture and the `scrollwise-serverless` skill for ops.

**Next: §3 — make the content-generator serverless and terminate the EC2 box.**
That's the last non-serverless piece. Loose ends meanwhile: delete the smoke-test
user from RDS, wire the API CI/CD IAM user + secrets, optional cold-start tuning.
