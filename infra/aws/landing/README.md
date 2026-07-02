# ScrollWise landing page (apex `scrollwise.net`)

Static marketing page ([`apps/landing/index.html`](../../../apps/landing/index.html))
hosted on its own **S3 + CloudFront + ACM** stack, mirroring `infra/aws/web`.

## Apex strategy (Option A)

DNS forbids a CNAME at the bare apex and CloudFront has no static IP, so:

- **`www.scrollwise.net`** is the canonical name → CNAME to the CloudFront domain.
- **`scrollwise.net`** (apex) is a **301 redirect → `https://www.scrollwise.net`**,
  configured as **domain forwarding in the IONOS control panel** (not in AWS).

`app.` and `api.` are unaffected — this is a separate distribution.

## One-time setup

```bash
./infra/aws/landing/setup.sh
```

Idempotent. It creates the bucket, Origin Access Control, ACM cert, and
distribution, then prints the IONOS records to add:

1. **Cert validation** CNAME(s) — the script pauses and polls until ACM issues
   the cert (add the record at IONOS while it waits).
2. **`www` CNAME** → the CloudFront domain it prints.
3. **Apex redirect** — IONOS domain forwarding `scrollwise.net → https://www.scrollwise.net` (301).

## Deploy / update the page

```bash
./infra/aws/landing/deploy.sh
```

Syncs `apps/landing/` to S3 and invalidates CloudFront. No build step.

## Resource names

| Thing | Value |
|---|---|
| S3 bucket | `scrollwise-landing-prod` |
| OAC | `scrollwise-landing-oac` |
| Distribution aliases | `scrollwise.net`, `www.scrollwise.net` |
| Profile / region | `scrollwise` / `us-east-1` |
