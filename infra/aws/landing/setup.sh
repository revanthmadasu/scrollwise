#!/usr/bin/env bash
# One-time (idempotent) infrastructure for the ScrollWise LANDING page.
#
# Hosts apps/landing (static index.html) on its own S3 bucket + CloudFront
# distribution + ACM cert, served at the apex scrollwise.net.
#
# Apex strategy (Option A): www.scrollwise.net is the canonical CNAME to
# CloudFront; the bare apex scrollwise.net is a 301 redirect to www configured
# in the IONOS control panel (domain forwarding) — NOT here. IONOS forbids a
# CNAME at the apex and CloudFront has no static IP, so the redirect lives at
# IONOS. This script prints the exact IONOS records you must add by hand.
#
# Safe to re-run: it reuses the bucket / OAC / cert / distribution if they
# already exist. Cert issuance requires you to add a DNS validation record at
# IONOS first — the script pauses and polls until the cert is ISSUED.
#
# Usage (from repo root):
#   ./infra/aws/landing/setup.sh
#
# After it finishes, deploy content with:
#   ./infra/aws/landing/deploy.sh
set -euo pipefail

PROFILE=scrollwise
REGION=us-east-1
BUCKET=scrollwise-landing-prod
APEX=scrollwise.net
WWW=www.scrollwise.net
OAC_NAME=scrollwise-landing-oac

if [ -t 2 ]; then RED=$'\033[31m'; GRN=$'\033[32m'; YEL=$'\033[33m'; RESET=$'\033[0m'; else RED=''; GRN=''; YEL=''; RESET=''; fi
err() { echo "${RED}$*${RESET}" >&2; }
ok()  { echo "${GRN}$*${RESET}"; }
note(){ echo "${YEL}$*${RESET}"; }

aws() { command aws --profile "$PROFILE" --region "$REGION" "$@"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

command -v aws >/dev/null 2>&1 || { err "!! aws CLI not found"; exit 1; }
command -v jq  >/dev/null 2>&1 || { err "!! jq not found (brew install jq)"; exit 1; }
aws sts get-caller-identity >/dev/null 2>&1 || { err "!! profile '$PROFILE' not authenticated"; exit 1; }

# ── 1. S3 bucket (private; CloudFront reaches it via OAC) ────────────────────
if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  ok "==> Bucket s3://$BUCKET already exists"
else
  echo "==> Creating bucket s3://$BUCKET"
  aws s3api create-bucket --bucket "$BUCKET" >/dev/null   # us-east-1: no LocationConstraint
  aws s3api put-public-access-block --bucket "$BUCKET" \
    --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
  ok "    created (private)"
fi

# ── 2. Origin Access Control (lets the distribution read the private bucket) ─
OAC_ID="$(aws cloudfront list-origin-access-controls \
  --query "OriginAccessControlList.Items[?Name=='$OAC_NAME'].Id | [0]" --output text)"
if [ "$OAC_ID" = "None" ] || [ -z "$OAC_ID" ]; then
  echo "==> Creating Origin Access Control $OAC_NAME"
  OAC_ID="$(aws cloudfront create-origin-access-control \
    --origin-access-control-config \
    "Name=$OAC_NAME,SigningProtocol=sigv4,SigningBehavior=always,OriginAccessControlOriginType=s3" \
    --query 'OriginAccessControl.Id' --output text)"
fi
ok "==> OAC: $OAC_ID"

# ── 3. ACM certificate for apex + www (DNS-validated via IONOS) ──────────────
# Only reuse a cert that covers BOTH names — a bare apex-only cert (e.g. an older
# manually-created one) would be matched by DomainName here but then rejected at
# distribution-create because it can't back the www.scrollwise.net alias.
CERT_ARN="$(aws acm list-certificates \
  --query "CertificateSummaryList[?DomainName=='$APEX'].CertificateArn | [0]" --output text)"
if [ "$CERT_ARN" != "None" ] && [ -n "$CERT_ARN" ]; then
  CERT_DOMAINS="$(aws acm describe-certificate --certificate-arn "$CERT_ARN" \
    --query 'Certificate.SubjectAlternativeNames' --output text)"
  if ! grep -qw "$WWW" <<<"$CERT_DOMAINS"; then
    note "==> Existing cert $CERT_ARN covers only [$CERT_DOMAINS] — missing $WWW; requesting a new one"
    CERT_ARN=""
  fi
fi
if [ "$CERT_ARN" = "None" ] || [ -z "$CERT_ARN" ]; then
  echo "==> Requesting ACM certificate for $APEX + $WWW"
  CERT_ARN="$(aws acm request-certificate \
    --domain-name "$APEX" \
    --subject-alternative-names "$WWW" \
    --validation-method DNS \
    --query 'CertificateArn' --output text)"
  sleep 5   # give ACM a moment to populate the validation records
fi
ok "==> Certificate: $CERT_ARN"

CERT_STATUS="$(aws acm describe-certificate --certificate-arn "$CERT_ARN" \
  --query 'Certificate.Status' --output text)"
if [ "$CERT_STATUS" != "ISSUED" ]; then
  note ""
  note "── ACTION: add these CNAME record(s) at IONOS to validate the cert ──"
  aws acm describe-certificate --certificate-arn "$CERT_ARN" \
    --query 'Certificate.DomainValidationOptions[].ResourceRecord' --output json \
    | jq -r '.[] | "  host: \(.Name)\n  type: \(.Type)\n  value: \(.Value)\n"'
  note "(IONOS strips the trailing .scrollwise.net from the host field — enter"
  note " just the '_xxxx' label part. Records may repeat; add each unique one.)"
  note ""
  echo "==> Waiting for certificate to be ISSUED (polling; Ctrl-C to stop and re-run later)…"
  aws acm wait certificate-validated --certificate-arn "$CERT_ARN"
  ok "    certificate ISSUED"
fi

# ── 4. CloudFront distribution ───────────────────────────────────────────────
DIST_ID="$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Aliases.Items[?@=='$WWW']].Id | [0]" --output text 2>/dev/null || true)"
if [ "$DIST_ID" = "None" ] || [ -z "$DIST_ID" ]; then
  echo "==> Creating CloudFront distribution"
  CONFIG="$(mktemp)"
  sed -e "s|__CALLER_REFERENCE__|scrollwise-landing-$(date -u +%Y%m%dT%H%M%S)|" \
      -e "s|__BUCKET__|$BUCKET|" \
      -e "s|__OAC_ID__|$OAC_ID|" \
      -e "s|__CERT_ARN__|$CERT_ARN|" \
      "$SCRIPT_DIR/distribution-config.template.json" > "$CONFIG"
  DIST_ID="$(aws cloudfront create-distribution --distribution-config "file://$CONFIG" \
    --query 'Distribution.Id' --output text)"
  rm -f "$CONFIG"
fi
DIST_DOMAIN="$(aws cloudfront get-distribution --id "$DIST_ID" \
  --query 'Distribution.DomainName' --output text)"
ok "==> Distribution: $DIST_ID  ($DIST_DOMAIN)"

# ── 5. Bucket policy: allow this distribution (via OAC) to read objects ──────
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
echo "==> Applying bucket policy (OAC read access for the distribution)"
aws s3api put-bucket-policy --bucket "$BUCKET" --policy "$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "AllowCloudFrontServicePrincipalRead",
    "Effect": "Allow",
    "Principal": { "Service": "cloudfront.amazonaws.com" },
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::$BUCKET/*",
    "Condition": { "StringEquals": { "AWS:SourceArn": "arn:aws:cloudfront::$ACCOUNT_ID:distribution/$DIST_ID" } }
  }]
}
JSON
)"

# ── Done: print the IONOS DNS + redirect steps ──────────────────────────────
ok ""
ok "════════════════════════════════════════════════════════════════════════"
ok " Infrastructure ready. Two manual steps at IONOS:"
ok "════════════════════════════════════════════════════════════════════════"
note ""
note " 1) DNS record — CNAME:"
note "      host:  www"
note "      value: $DIST_DOMAIN"
note ""
note " 2) Apex redirect (IONOS domain forwarding on $APEX):"
note "      target: https://$WWW"
note "      type:   301 / permanent"
note ""
echo " Then deploy the page:  ./infra/aws/landing/deploy.sh"
echo " Distribution id (for deploy):  CF_DISTRIBUTION_ID=$DIST_ID"
