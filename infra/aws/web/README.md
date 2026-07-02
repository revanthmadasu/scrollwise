# Frontend on S3 + CloudFront

Hosting plan for `apps/web` (the Vite + React SPA): static files live in a
**private S3 bucket**, and **CloudFront** serves them globally over HTTPS. S3 is
the origin (storage); CloudFront is the CDN (caching, TLS, custom domain).

We use **CloudFront Origin Access Control (OAC)** so the bucket stays private —
only CloudFront can read it, never the public internet directly.

**CloudFront serves the UI only — it has a single origin (the S3 bucket).** The
API is served on its own domain, `https://api.scrollwise.net`, and the browser
calls it directly (cross-origin, with CORS). There is no `/api/*` proxy.

```
UI   scrollwise.net      → CloudFront → S3            (static SPA)
API  api.scrollwise.net  → EC2/Caddy → uvicorn        (now)
                         → API Gateway → Lambda       (after the serverless migration)
```

`api.scrollwise.net` is just DNS: point it at EC2 now, re-point it at API Gateway
later. The UI and this CloudFront setup don't change when the API goes
serverless — only the DNS record + CORS. See "Serving the API on its own domain"
below.

---

## Prerequisites

- AWS account + AWS CLI v2 configured (`aws configure`; an IAM user/role with
  S3 + CloudFront + ACM permissions).
- Node 18+ to build (`nvm use 22`).
- (Optional) a domain you control, for a custom URL.

Pick names/region once and export them so the commands below are copy-paste:

```bash
export AWS_REGION=us-east-1            # ACM cert for CloudFront MUST be us-east-1
export WEB_BUNDLE_BUILD_BUCKET=scrollwise-web-bundle-prod  # globally-unique bucket name
export API_BASE=https://api.scrollwise.net   # the SPA calls this directly (CORS)
```

---

## One-time setup

### Step 1 — Build the bundle (sanity check)

**What:** produce the static files CloudFront will serve.
**Run:**
```bash
( cd apps/web && VITE_API_BASE="$API_BASE" npm ci && npm run build )
```
**Expected output:** a `apps/web/dist/` folder containing `index.html` and
`assets/*.js` / `*.css` with content-hashed filenames. This is everything that
gets uploaded. (~1–10 MB total for an app this size.)

### Step 2 — Create the private S3 bucket

**What:** the storage origin. Private — public access fully blocked.
**Run:**
```bash
aws s3api create-bucket --bucket "$WEB_BUNDLE_BUILD_BUCKET" --region "$AWS_REGION" \
  $( [ "$AWS_REGION" != us-east-1 ] && echo --create-bucket-configuration LocationConstraint="$AWS_REGION" )

aws s3api put-public-access-block --bucket "$WEB_BUNDLE_BUILD_BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```
**Expected output:** the create call returns the bucket `Location`. The second
call returns nothing (success). The bucket exists and is locked down — direct
S3 URLs will return `403`. That's intended; CloudFront reaches it via OAC.

### Step 3 — Create the Origin Access Control (OAC)

**What:** an identity that lets *only* CloudFront read the private bucket.
**Run:**
```bash
aws cloudfront create-origin-access-control --origin-access-control-config \
  Name="$WEB_BUNDLE_BUILD_BUCKET-oac",SigningProtocol=sigv4,SigningBehavior=always,OriginAccessControlOriginType=s3
```
**Expected output:** JSON with an `Id` (e.g. `E2ABC...`). **Save it** — you
reference it in the distribution config. Nothing is wired yet; this is just the
credential.

### Step 4 — (Optional) Request an HTTPS certificate for a custom domain

Skip if you'll use the default `*.cloudfront.net` URL.
**What:** a free ACM cert so `https://app.scrollwise.example` works.
**Run (must be us-east-1):**
```bash
aws acm request-certificate --region us-east-1 \
  --domain-name scrollwise.net --validation-method DNS
```
**Expected output:** a certificate ARN. ACM returns a CNAME record you must add
to your DNS; once added, the cert flips to `ISSUED` (a few minutes). Save the ARN.

### Step 5 — Create the CloudFront distribution

**What:** the CDN. Single S3 origin, the SPA routing fallback, and TLS.
**How:** copy `distribution-config.template.json` in this directory, fill in the
`__PLACEHOLDERS__` (bucket domain `$WEB_BUNDLE_BUILD_BUCKET.s3.$AWS_REGION.amazonaws.com`, the
OAC id from Step 3, and — if using a custom domain — the ACM ARN and aliases),
then:
```bash
aws cloudfront create-distribution --distribution-config file://distribution-config.json
```
**Expected output:** JSON with the distribution `Id` (e.g. `E1ABCDEF234567`),
its `DomainName` (`dxxxx.cloudfront.net`), and `Status: InProgress`. It takes
~5–15 min to deploy globally; wait until `Status: Deployed`.

One thing in the config worth knowing:
- **SPA routing:** `CustomErrorResponses` maps `403` and `404` → `/index.html`
  with response code `200`. React Router deep links (`/feed`, `/progress`) work
  because every unknown path serves the SPA shell.

(There is no API cache behavior — the SPA calls `api.scrollwise.net` directly.)

### Step 6 — Lock the bucket policy to this distribution

**What:** allow the CloudFront distribution (and only it) to read the bucket.
**Run** (substitute your account id + distribution id):
```bash
aws s3api put-bucket-policy --bucket "$WEB_BUNDLE_BUILD_BUCKET" --policy '{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "AllowCloudFrontRead",
    "Effect": "Allow",
    "Principal": { "Service": "cloudfront.amazonaws.com" },
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::'"$WEB_BUNDLE_BUILD_BUCKET"'/*",
    "Condition": { "StringEquals": {
      "AWS:SourceArn": "arn:aws:cloudfront::339140804013:distribution/E3RSA4VCIHJJ90" } }
  }]
}'
```
**Expected output:** nothing (success). Now CloudFront can serve the files while
the bucket stays private.

### Step 7 — (Optional) Point your domain at CloudFront

**What:** a DNS alias from your UI domain to the distribution.
- **Route 53:** create an A/AAAA *alias* record for `scrollwise.net` → the
  distribution domain.
- **Other DNS:** a CNAME → `dxxxx.cloudfront.net` (apex domains need an
  ALIAS/ANAME record, which Route 53 provides).

**Expected output:** after DNS propagates, `https://scrollwise.net` loads the app.

> Make sure `scrollwise.net` now points at CloudFront, and the API is reachable
> at the *separate* `api.scrollwise.net` (next section) — not at
> `scrollwise.net/api` anymore.

### Step 8 — First deploy + every deploy after

**What:** build, upload, invalidate cache. Use the script:
```bash
WEB_BUNDLE_BUILD_BUCKET=$WEB_BUNDLE_BUILD_BUCKET CF_DISTRIBUTION_ID=E3RSA4VCIHJJ90 ./infra/aws/web/deploy.sh
```
**Expected output:** files synced to S3, an invalidation id printed, new bundle
live in ~1–3 min. Hashed assets are cached forever; `index.html` is never cached
so users always pull the current shell.

---

## Cost

For an app this size with low-to-moderate traffic, this is **effectively free to
a few dollars a month**. CloudFront has a large *always-free* tier.

| Item | Price | Typical ScrollWise cost |
|---|---|---|
| **S3 storage** | ~$0.023/GB-month | bundle is ~5–10 MB → **< $0.01/mo** |
| **S3 requests** | ~$0.0004 / 1k GET | served via CloudFront, near-zero → **~$0** |
| **CloudFront — data out** | **first 1 TB/mo free**, then ~$0.085/GB | small app stays in free tier → **$0** |
| **CloudFront — requests** | **first 10M HTTPS/mo free**, then ~$0.01/10k | in free tier → **$0** |
| **ACM certificate** | **free** | $0 |
| **Route 53 hosted zone** | $0.50/zone-month + ~$0.40/M queries | only if custom domain → **~$0.50–1/mo** |
| **CloudFront invalidations** | first 1,000 paths/mo free | we invalidate `/*` (1 path) per deploy → **$0** |

**Realistic total:**
- Default `*.cloudfront.net` URL, modest traffic: **$0–1 / month.**
- With a custom domain on Route 53: **~$0.50–1.50 / month.**

Costs only climb past the free tier at real scale: e.g. 5 TB/month of transfer
≈ ~$340/mo of CloudFront egress — but that's hundreds of thousands of active
users. At launch scale this is essentially free.

> Note: the free tier figures are the standard CloudFront *always-free* tier
> (1 TB out + 10M requests/mo). Confirm current numbers on the AWS pricing page
> before relying on them for budgeting.

---

## CI/CD — deploy automatically from GitHub (recommended)

Instead of running `deploy.sh` from a laptop, let GitHub Actions run it on every
push to `master` that touches the frontend. Authentication uses an **IAM user's
access keys**, stored as encrypted GitHub repo secrets. (Secrets are encrypted
and are NOT exposed in public repos or to fork PRs.)

> These keys are long-lived. Keep the IAM user least-privilege (S3 + CloudFront
> only, via `github-deploy-permissions.json`) and rotate the keys periodically.

Files involved:
- `.github/workflows/deploy-web.yml` — the workflow (path-filtered to `apps/web`).
- `github-deploy-permissions.json` — the IAM user's permissions (what it may do).

### One-time AWS setup

1. **Create a dedicated IAM user** for deploys (no console access, keys only):
   ```bash
   aws iam create-user --user-name scrollwise-web-deploy
   ```
   Expected: returns the user details.

2. **Attach least-privilege permissions** (replace `WEB_BUNDLE_BUILD_BUCKET`, `ACCOUNT_ID`,
   `DISTRIBUTION_ID` in `github-deploy-permissions.json` first):
   ```bash
   aws iam put-user-policy --user-name scrollwise-web-deploy \
     --policy-name deploy-web \
     --policy-document file://infra/aws/web/github-deploy-permissions.json
   ```
   Expected: nothing (success).

3. **Create an access key** for the user:
   ```bash
   aws iam create-access-key --user-name scrollwise-web-deploy
   ```
   Expected: JSON containing `AccessKeyId` and `SecretAccessKey`. **Copy the
   secret now — AWS never shows it again.** These two values go into GitHub next.

### One-time GitHub setup

In the repo → **Settings → Secrets and variables → Actions**:

| Kind | Name | Value |
|---|---|---|
| Secret | `AWS_ACCESS_KEY_ID` | `AccessKeyId` from step 3 |
| Secret | `AWS_SECRET_ACCESS_KEY` | `SecretAccessKey` from step 3 |
| Variable | `AWS_REGION` | e.g. `us-east-1` |
| Variable | `WEB_BUNDLE_BUILD_BUCKET` | e.g. `scrollwise-web-bundle-prod` |
| Variable | `CF_DISTRIBUTION_ID` | e.g. `E1ABCDEF234567` |
| Variable | `VITE_API_BASE` | `https://api.scrollwise.net` |

That's it. Push a change under `apps/web/` to `master` (or use **Run workflow**
in the Actions tab) and it builds, syncs, and invalidates automatically.

### Rotating the keys (do this periodically)

```bash
aws iam create-access-key --user-name scrollwise-web-deploy   # make a new key
# update the two GitHub secrets with the new values, confirm a deploy works, then:
aws iam delete-access-key --user-name scrollwise-web-deploy --access-key-id OLD_KEY_ID
```

---

## Serving the API on its own domain (`api.scrollwise.net`)

CloudFront serves only the UI. The SPA calls `https://api.scrollwise.net`
directly. That hostname is just DNS — it points at EC2 today and at API Gateway
after the serverless migration. **The UI / CloudFront / deploy pipeline above do
not change when the API goes serverless** — only the DNS record and CORS do.

### Now — point `api.scrollwise.net` at the existing EC2/Caddy box

1. **DNS:** add an A record `api.scrollwise.net` → the EC2 Elastic IP (same box
   that serves the app today).
2. **Caddy:** add a second site block so Caddy issues a TLS cert for the new
   host and proxies the whole host to uvicorn. Unlike the current
   `scrollwise.net` block, there's no `/api` prefix to strip — the host *is* the
   API:
   ```
   api.scrollwise.net {
       encode gzip
       reverse_proxy 127.0.0.1:8000
   }
   ```
   Reload: `sudo systemctl reload caddy`. Verify: `curl https://api.scrollwise.net/health`.
3. **CORS:** the UI (`https://scrollwise.net`) and API (`https://api.scrollwise.net`)
   are now different origins, so add the UI origin to the API's `CORS_ORIGINS`
   env (`apps/api/.env`). Auth uses a JWT in the `Authorization` header (not
   cookies), so a plain CORS allow is enough. Restart the API after editing.

> Note the path change: the old setup stripped `/api` (so the SPA called
> `/api/health` → uvicorn `/health`). On the dedicated host the SPA calls
> `https://api.scrollwise.net/health` directly — which is why `VITE_API_BASE` is
> the bare host with no `/api` suffix.

### Later — migrate the API to serverless

Deploy the API behind an **API Gateway custom domain** `api.scrollwise.net`,
then **re-point the DNS record** at the Gateway (and confirm CORS allows the UI
origin on the Gateway/Lambda side). Nothing in this web setup changes.
