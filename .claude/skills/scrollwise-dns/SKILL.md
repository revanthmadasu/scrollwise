---
name: scrollwise-dns
description: >-
  How ScrollWise's DNS, domains, TLS certs, and the landing page are wired — and
  how to change them. Use this whenever the user touches anything about
  scrollwise.net / www / app. / api. domains, DNS records, nameservers, ACM
  certificates, or the marketing landing page. Concrete triggers: "point X to
  Y", "add a DNS record", "why isn't <domain> resolving / showing SSL error /
  serving HTTPS", "the cert is PENDING_VALIDATION / won't issue", "renew the
  cert", "update the landing page", "scrollwise.net is broken", "move DNS", "add
  a subdomain", "set up email / MX / SPF / DKIM / DMARC", or any apex-vs-subdomain
  routing question. DNS is on **Route 53** (migrated off IONOS 2026-07-02; IONOS
  is registrar-only). Reach for it even when the user doesn't say "DNS" — "make
  scrollwise.net go to the landing page", "app.scrollwise.net 403", and "the
  https cert expired" are all this skill. For API/web/generator *runtime*
  oper/troubleshoot use `scrollwise-serverless`; this skill owns the naming layer
  in front of them.
---

# ScrollWise DNS, domains & the landing page

AWS profile **`scrollwise`**, region **us-east-1**, account **339140804013**.
Registrar is **IONOS**; authoritative DNS is **AWS Route 53** (hosted zone for
`scrollwise.net`) since the 2026-07-02 migration. Infra scripts live in
[`infra/aws/landing/`](../../../infra/aws/landing/).

## The domains

| Name | Type in Route 53 | Points at | Served by |
|---|---|---|---|
| `scrollwise.net` (apex) | ALIAS A + AAAA | landing CloudFront | landing page |
| `www.scrollwise.net` | ALIAS A + AAAA | landing CloudFront | landing page |
| `app.scrollwise.net` | CNAME | `dkflt0h7ibwhb.cloudfront.net` | web SPA (S3+CF) |
| `api.scrollwise.net` | CNAME | `d-25fxrdt7b2.execute-api.us-east-1.amazonaws.com` | API (Lambda+API GW) |

Email stays on IONOS mail: `MX` → `mx00/mx01.ionos.com`, plus SPF (`_spf-us.ionos.com`),
DMARC (`_dmarc` → `dmarc.ionos.com`), DKIM (`s1/s2-ionos._domainkey`), and
`autodiscover`. These are records in the Route 53 zone now — don't drop them.

**Why apex is an ALIAS, not a CNAME:** DNS forbids a CNAME at the bare apex.
IONOS could only serve `https://scrollwise.net` via a *paid* SSL redirect; Route 53
ALIAS → CloudFront gives direct HTTPS with the free ACM cert. That's the whole
reason DNS moved. Don't reintroduce a www-redirect — apex serves directly.

## The landing page stack

Static `apps/landing/index.html` on its own S3 + CloudFront + ACM, separate from
`app.`:
- S3 bucket `scrollwise-landing-prod` (private), OAC `scrollwise-landing-oac` (`E3872DXLYVEX1K`)
- CloudFront distribution **`E3Q8PG2M7ITPG1`** (aliases scrollwise.net + www)
- ACM cert `3af5722b-84a2-45d5-95fd-404b287e8b3c` (apex + www)

**Update the landing page:** edit `apps/landing/index.html`, then
```bash
./infra/aws/landing/deploy.sh          # syncs to S3 + CloudFront invalidation; no build step
```
It auto-discovers the distribution by the `www.scrollwise.net` alias.

**(Re)provision the stack from scratch** (idempotent):
```bash
./infra/aws/landing/setup.sh           # bucket, OAC, cert (pauses for DNS validation), distribution, bucket policy
```
Guards against reusing an apex-only cert that's missing `www`.

## Route 53 zone operations

```bash
# find the hosted zone id
aws route53 list-hosted-zones-by-name --profile scrollwise --dns-name scrollwise.net. \
  --query "HostedZones[?Name=='scrollwise.net.'].Id" --output text
# dump every record
aws route53 list-resource-record-sets --profile scrollwise --hosted-zone-id <ZONE_ID>
```
Add/modify records with `change-resource-record-sets` and an UPSERT change batch.
The full as-run migration (every record, correctly escaped) is
[`infra/aws/landing/migrate-dns-to-route53.sh`](../../../infra/aws/landing/migrate-dns-to-route53.sh)
— copy a record block from its `EXTRA_RECORDS` for the exact JSON shape.

**Adding a new subdomain** → UPSERT a CNAME (subdomains can CNAME) or an ALIAS A
if it fronts a CloudFront/API-GW/ELB target. Apex-level names must be ALIAS.

## ACM certificates (DNS-validated)

Every cert is DNS-validated via a `_xxx…acm-validations.aws.` CNAME **that must
stay in the Route 53 zone** — ACM auto-renews using it. Four such records live in
the zone (apex/www landing, app, api). Deleting one breaks that cert's renewal.

- Check status: `aws acm describe-certificate --profile scrollwise --region us-east-1 --certificate-arn <ARN> --query 'Certificate.{Status:Status,Domains:SubjectAlternativeNames}'`
- `PENDING_VALIDATION` → the validation CNAME isn't resolving; get it from
  `...DomainValidationOptions[].ResourceRecord` and add it to the zone.
- Certs for CloudFront **must be in us-east-1**. SANs must cover every alias on the
  distribution or CreateDistribution fails `InvalidViewerCertificate`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `scrollwise.net` doesn't resolve | NS delegation — `dig NS scrollwise.net +short` should list the 4 `awsdns` names; if not, IONOS nameservers reverted |
| resolves but **403 / SSL error** | alias not on the distribution, or the ACM cert doesn't cover that name |
| `https://` fails but `http://` works | (legacy IONOS-redirect symptom) — apex should now be a Route 53 ALIAS to CloudFront, not a redirect |
| landing page stale after deploy | CloudFront cache — force `aws cloudfront create-invalidation --profile scrollwise --distribution-id E3Q8PG2M7ITPG1 --paths '/*'` |
| cert won't renew | its `_acm…` validation CNAME was deleted from the zone — re-add it |
| email stopped | an MX/SPF/DKIM/DMARC record missing from the Route 53 zone |

Quick end-to-end check:
```bash
dig NS scrollwise.net +short
for h in scrollwise.net www.scrollwise.net app.scrollwise.net api.scrollwise.net; do
  echo -n "$h -> "; curl -sI "https://$h" | head -1
done
```

## Not covered here
Runtime of the API/web/generator (see `scrollwise-serverless`). Registrar-level
actions (transferring the domain, WHOIS/contact, renewal billing) are done in the
**IONOS** control panel — Route 53 only holds the DNS records.
