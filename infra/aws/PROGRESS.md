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

## 2. Backend (apps/api) — Lambda + RDS  [CODE SCAFFOLDED, NOT DEPLOYED]

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

**Not started (all in the API README):**
- [ ] RDS instance + pgvector + `pg_dump`/restore from EC2.
- [ ] Secrets Manager `scrollwise/api` (DATABASE_URL must use `postgresql+asyncpg://`).
- [ ] ECR repo + container build/push.
- [ ] Lambda (VPC-attached) + execution role.
- [ ] API Gateway HTTP API + custom domain `api.scrollwise.net` (regional ACM cert).
- [ ] Repoint the EC2 drain worker `DATABASE_URL` at RDS.
- [ ] API CI/CD workflow (not scaffolded yet).

### ⚠️ Open issues to resolve before deploying the backend
1. **NAT Gateway cost / Google OIDC.** A VPC Lambda has no internet by default, but
   auth fetches Google's JWKS. Options: add a NAT Gateway (~$32/mo), use a VPC
   endpoint / cache JWKS, or drop Google sign-in. Decide before building the VPC.
2. **Shared DB cutover.** API-Lambda and the generator must point at the SAME RDS.
   Don't decommission EC2 Postgres until both are migrated and verified.
3. **Cost reality.** ~$15/mo without NAT, ~$45+/mo with NAT. Serverless win here is
   operational, not necessarily cheaper at low/spiky traffic.

---

## 3. Content-generator — serverless  [NOT STARTED]

Currently the EC2 `scrollwise-drain` systemd poller (`drain_prompts.py`, has a
`--once` mode). Planned target: **SQS → Lambda** for short jobs, or **Step
Functions / Fargate** for long LLM batches (mind Lambda's 15-min cap). Must share
the same RDS as the API once that exists.

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
UI domain             app.scrollwise.net
API domain (planned)  api.scrollwise.net
ACM (app, us-east-1)  ...certificate/ea31dbf8-110b-4d33-a6da-bb18b043f70d
VITE_API_BASE         https://api.scrollwise.net
```

## Suggested next step
Finish the **web cutover** (validate cert → bucket policy → DNS → first deploy →
curl 200) so the UI is actually live, *then* start the backend with the
NAT/Google-OIDC decision, since it gates the VPC design.
