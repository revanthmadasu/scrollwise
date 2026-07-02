#!/usr/bin/env bash
# Migrate scrollwise.net DNS from IONOS to AWS Route 53.
#
# WHY: IONOS can't put an ALIAS/A record at the bare apex, so it can only serve
# https://scrollwise.net via a *paid* SSL redirect. Route 53 supports an apex
# ALIAS A record straight to CloudFront, using the free ACM cert already on the
# landing distribution. Net cost ~$0.50/mo (hosted zone).
#
# This keeps IONOS as the REGISTRAR — only the nameservers change.
#
# ─────────────────────────────────────────────────────────────────────────────
#  READ THIS BEFORE RUNNING
# ─────────────────────────────────────────────────────────────────────────────
# When you switch nameservers to Route 53, ANY record that exists at IONOS but
# NOT in this script goes dark. This script recreates the records we KNOW:
#     apex  scrollwise.net      ALIAS A  -> landing CloudFront   (NEW, direct)
#     www.scrollwise.net        ALIAS A  -> landing CloudFront   (NEW, direct)
#     app.scrollwise.net        CNAME    -> app CloudFront        (unchanged)
#     api.scrollwise.net        CNAME    -> API Gateway           (unchanged)
# You MUST review the EXTRA_RECORDS block below and add every MX / TXT / SPF /
# DKIM / other record you currently have at IONOS, or that service breaks
# (email especially). If you have none, leave it empty.
#
# Safe cutover order:
#   1. Run this script  -> creates the zone + records. Nothing breaks yet
#      (IONOS is still authoritative until you change nameservers).
#   2. Verify records resolve against the new zone (script prints how).
#   3. In IONOS, set the domain's nameservers to the 4 the script prints.
#   4. Wait for propagation, verify https://scrollwise.net, then delete the old
#      IONOS DNS records / forwarding.
set -euo pipefail

PROFILE=scrollwise
REGION=us-east-1
DOMAIN=scrollwise.net
LANDING_DIST_ID=E3Q8PG2M7ITPG1

# Existing subdomain targets (from the serverless stack; keep as CNAMEs).
APP_TARGET=dkflt0h7ibwhb.cloudfront.net           # app.scrollwise.net  -> web CloudFront
API_TARGET=d-25fxrdt7b2.execute-api.us-east-1.amazonaws.com  # api.scrollwise.net -> API GW

# CloudFront's fixed hosted-zone id for ALIAS records (same for every distro).
CF_HOSTED_ZONE_ID=Z2FDTNDATAQYW2

if [ -t 2 ]; then RED=$'\033[31m'; GRN=$'\033[32m'; YEL=$'\033[33m'; RESET=$'\033[0m'; else RED=''; GRN=''; YEL=''; RESET=''; fi
err() { echo "${RED}$*${RESET}" >&2; }
ok()  { echo "${GRN}$*${RESET}"; }
note(){ echo "${YEL}$*${RESET}"; }

aws() { command aws --profile "$PROFILE" --region "$REGION" "$@"; }

command -v aws >/dev/null 2>&1 || { err "!! aws CLI not found"; exit 1; }
aws sts get-caller-identity >/dev/null 2>&1 || { err "!! profile '$PROFILE' not authenticated"; exit 1; }

# ── 1. Landing distribution's CloudFront domain (target for apex + www ALIAS) ─
LANDING_CF="$(aws cloudfront get-distribution --id "$LANDING_DIST_ID" \
  --query 'Distribution.DomainName' --output text)"
[ -n "$LANDING_CF" ] && [ "$LANDING_CF" != "None" ] \
  || { err "!! could not read landing distribution $LANDING_DIST_ID"; exit 1; }
ok "==> Landing CloudFront: $LANDING_CF"

# ── 2. Hosted zone (idempotent) ──────────────────────────────────────────────
ZONE_ID="$(aws route53 list-hosted-zones-by-name --dns-name "$DOMAIN." \
  --query "HostedZones[?Name=='$DOMAIN.'].Id | [0]" --output text)"
if [ "$ZONE_ID" = "None" ] || [ -z "$ZONE_ID" ]; then
  echo "==> Creating hosted zone for $DOMAIN"
  ZONE_ID="$(aws route53 create-hosted-zone --name "$DOMAIN" \
    --caller-reference "scrollwise-$(date -u +%Y%m%dT%H%M%S)" \
    --query 'HostedZone.Id' --output text)"
fi
ZONE_ID="${ZONE_ID##*/}"   # strip /hostedzone/ prefix
ok "==> Hosted zone: $ZONE_ID"

# ─────────────────────────────────────────────────────────────────────────────
#  EXTRA_RECORDS — paste your IONOS MX / TXT / DKIM / etc. here.
#  Each entry is a full ResourceRecordSet change object. Examples (DELETE the
#  examples and replace with your real records; leave the array empty if none):
#
#   {"Action":"UPSERT","ResourceRecordSet":{
#     "Name":"scrollwise.net.","Type":"MX","TTL":3600,
#     "ResourceRecords":[{"Value":"10 mx00.ionos.com."},{"Value":"10 mx01.ionos.com."}]}},
#   {"Action":"UPSERT","ResourceRecordSet":{
#     "Name":"scrollwise.net.","Type":"TXT","TTL":3600,
#     "ResourceRecords":[{"Value":"\"v=spf1 include:_spf.ionos.com ~all\""}]}}
# ─────────────────────────────────────────────────────────────────────────────
# Filled from the IONOS export: email (MX/SPF/DMARC/DKIM/autodiscover) + the ACM
# cert-validation CNAMEs (kept so ACM can auto-renew the landing/app/api certs).
# The api validation value was fixed: IONOS had a broken '.acm-validations.AWS_REGION'
# literal; the correct suffix is '.acm-validations.aws'.
# Dropped as IONOS-only: _domainconnect, the two _dep_ws_mutex TXT locks, and the
# apex/www A+AAAA to 74.208.236.167 (replaced by the CloudFront ALIAS records above).
EXTRA_RECORDS='
    ,{"Action":"UPSERT","ResourceRecordSet":{"Name":"scrollwise.net.","Type":"MX","TTL":3600,"ResourceRecords":[{"Value":"10 mx00.ionos.com."},{"Value":"10 mx01.ionos.com."}]}}
    ,{"Action":"UPSERT","ResourceRecordSet":{"Name":"scrollwise.net.","Type":"TXT","TTL":3600,"ResourceRecords":[{"Value":"\"v=spf1 include:_spf-us.ionos.com ~all\""}]}}
    ,{"Action":"UPSERT","ResourceRecordSet":{"Name":"_dmarc.scrollwise.net.","Type":"CNAME","TTL":3600,"ResourceRecords":[{"Value":"dmarc.ionos.com."}]}}
    ,{"Action":"UPSERT","ResourceRecordSet":{"Name":"s1-ionos._domainkey.scrollwise.net.","Type":"CNAME","TTL":3600,"ResourceRecords":[{"Value":"s1.dkim.ionos.com."}]}}
    ,{"Action":"UPSERT","ResourceRecordSet":{"Name":"s2-ionos._domainkey.scrollwise.net.","Type":"CNAME","TTL":3600,"ResourceRecords":[{"Value":"s2.dkim.ionos.com."}]}}
    ,{"Action":"UPSERT","ResourceRecordSet":{"Name":"autodiscover.scrollwise.net.","Type":"CNAME","TTL":3600,"ResourceRecords":[{"Value":"adsredir.ionos.info."}]}}
    ,{"Action":"UPSERT","ResourceRecordSet":{"Name":"_4efa95d4bc7dade529652e68d0ec42bb.scrollwise.net.","Type":"CNAME","TTL":3600,"ResourceRecords":[{"Value":"_544ee2a3b1ee8820b71a9f5dff2ebba3.jkddzztszm.acm-validations.aws."}]}}
    ,{"Action":"UPSERT","ResourceRecordSet":{"Name":"_11faf25746f3b33d544e2f1f2239e8f4.www.scrollwise.net.","Type":"CNAME","TTL":3600,"ResourceRecords":[{"Value":"_949e1f372de2240f5543145328d49afb.jkddzztszm.acm-validations.aws."}]}}
    ,{"Action":"UPSERT","ResourceRecordSet":{"Name":"_85156dfb8c25c6d141bf2ed9e0ef41f5.app.scrollwise.net.","Type":"CNAME","TTL":3600,"ResourceRecords":[{"Value":"_da76553854b8f5c08c70c48be2632d05.jkddzztszm.acm-validations.aws."}]}}
    ,{"Action":"UPSERT","ResourceRecordSet":{"Name":"_a56cee9e074a1ec0e165339ed2d9848b.api.scrollwise.net.","Type":"CNAME","TTL":3600,"ResourceRecords":[{"Value":"_f977265c4feb4b8fcaa72fc9dbcf9daf.jkddzztszm.acm-validations.aws."}]}}
'

# ── 3. Upsert the known records + any extras ─────────────────────────────────
echo "==> Writing records into the zone"
CHANGE_BATCH="$(cat <<JSON
{
  "Comment": "scrollwise.net apex+www direct to landing CloudFront; app/api unchanged",
  "Changes": [
    {"Action":"UPSERT","ResourceRecordSet":{
      "Name":"$DOMAIN.","Type":"A",
      "AliasTarget":{"HostedZoneId":"$CF_HOSTED_ZONE_ID","DNSName":"$LANDING_CF.","EvaluateTargetHealth":false}}},
    {"Action":"UPSERT","ResourceRecordSet":{
      "Name":"$DOMAIN.","Type":"AAAA",
      "AliasTarget":{"HostedZoneId":"$CF_HOSTED_ZONE_ID","DNSName":"$LANDING_CF.","EvaluateTargetHealth":false}}},
    {"Action":"UPSERT","ResourceRecordSet":{
      "Name":"www.$DOMAIN.","Type":"A",
      "AliasTarget":{"HostedZoneId":"$CF_HOSTED_ZONE_ID","DNSName":"$LANDING_CF.","EvaluateTargetHealth":false}}},
    {"Action":"UPSERT","ResourceRecordSet":{
      "Name":"www.$DOMAIN.","Type":"AAAA",
      "AliasTarget":{"HostedZoneId":"$CF_HOSTED_ZONE_ID","DNSName":"$LANDING_CF.","EvaluateTargetHealth":false}}},
    {"Action":"UPSERT","ResourceRecordSet":{
      "Name":"app.$DOMAIN.","Type":"CNAME","TTL":300,
      "ResourceRecords":[{"Value":"$APP_TARGET"}]}},
    {"Action":"UPSERT","ResourceRecordSet":{
      "Name":"api.$DOMAIN.","Type":"CNAME","TTL":300,
      "ResourceRecords":[{"Value":"$API_TARGET"}]}}
    $EXTRA_RECORDS
  ]
}
JSON
)"
aws route53 change-resource-record-sets --hosted-zone-id "$ZONE_ID" \
  --change-batch "$CHANGE_BATCH" \
  --query 'ChangeInfo.Status' --output text
ok "    records submitted"

# ── 4. Print the nameservers to set at IONOS ─────────────────────────────────
NS="$(aws route53 get-hosted-zone --id "$ZONE_ID" \
  --query 'DelegationSet.NameServers' --output text)"
ok ""
ok "════════════════════════════════════════════════════════════════════════"
ok " Zone is ready. NOTHING is live yet — IONOS is still authoritative."
ok "════════════════════════════════════════════════════════════════════════"
note ""
note " 1) Sanity-check the new zone answers correctly (before switching NS):"
for host in "$DOMAIN" "www.$DOMAIN" "app.$DOMAIN" "api.$DOMAIN"; do
  one_ns="$(echo "$NS" | awk '{print $1}')"
  note "      dig @$one_ns $host +short"
done
note ""
note " 2) Then, at IONOS, set the domain NAMESERVERS to these 4:"
for n in $NS; do note "      $n"; done
note ""
note " 3) After propagation:  curl -sI https://$DOMAIN | head -1   (expect 200)"
note "    Then remove the old IONOS DNS records + the apex forwarding."
