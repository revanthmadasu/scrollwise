#!/usr/bin/env bash
# End-to-end smoke test for content-generator on EC2.
#
# Verifies the box is wired up correctly, then runs a tiny real generation
# and confirms rows landed in the DB. Safe to re-run.
#
# Usage:
#   cd /opt/content-generator
#   source .venv/bin/activate
#   chmod +x scripts/ec2_smoke_test.sh
#   ./scripts/ec2_smoke_test.sh
#
# Optional overrides:
#   TOPIC="Photosynthesis" ./scripts/ec2_smoke_test.sh

set -euo pipefail

TOPIC="${TOPIC:-Smoke Test Topic}"
MODULES="${MODULES:-1}"
SUBTOPICS="${SUBTOPICS:-2}"

pass() { printf '  \033[32mok\033[0m   %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; exit 1; }
step() { printf '\n==> %s\n' "$1"; }

# 0. Must run from the app dir so `python -m scripts.*` resolves.
[ -f scripts/generate.py ] || fail "run this from the app root (where scripts/generate.py lives)"

step "1. Environment"
command -v python >/dev/null || fail "python not on PATH (did you 'source .venv/bin/activate'?)"
pass "python: $(python --version 2>&1)"
[ -f .env ] || fail ".env missing — copy from ec2_setup output and fill in values"
# shellcheck disable=SC1091
set -a; . ./.env; set +a
pass ".env loaded (LLM_BACKEND=${LLM_BACKEND:-unset}, DB_BACKEND=${DB_BACKEND:-unset})"

step "2. Python deps import"
python - <<'PY' || fail "dependency import failed — check 'pip install -r requirements.txt'"
import importlib, sys
for m in ("anthropic", "pydantic", "boto3", "numpy", "PIL", "click"):
    importlib.import_module(m)
if __import__("os").environ.get("DB_BACKEND") == "postgres":
    importlib.import_module("psycopg2")
print("  imports ok")
PY
pass "core packages import"

step "3. Database connectivity"
python - <<'PY' || fail "could not connect to DB / posts table missing"
from storage.repository import Repository
repo = Repository()
n = repo.conn.cursor()
n.execute("SELECT count(*) FROM posts")
print(f"  connected; posts table has {n.fetchone()[0]} rows")
PY
pass "DB reachable and schema present"

step "4. LLM backend reachability"
if [ "${LLM_BACKEND:-}" = "bedrock" ]; then
  python - <<'PY' || fail "Bedrock not reachable — check the instance IAM role has bedrock:InvokeModel and AWS_REGION is set"
import boto3, os
sts = boto3.client("sts")
ident = sts.get_caller_identity()
print(f"  AWS identity: {ident['Arn']}")
print(f"  region: {os.environ.get('AWS_REGION', 'us-east-1')}, model: {os.environ.get('LLM_MODEL')}")
PY
  pass "AWS credentials/role resolved for Bedrock"
else
  pass "LLM_BACKEND=${LLM_BACKEND:-anthropic} (skipping Bedrock IAM check)"
fi

step "5. Tiny end-to-end generation"
BEFORE=$(python -c "from storage.repository import Repository as R;c=R().conn.cursor();c.execute('SELECT count(*) FROM posts');print(c.fetchone()[0])")
python -m scripts.generate \
  --topic "$TOPIC" \
  --modules "$MODULES" \
  --subtopics-per-module "$SUBTOPICS" \
  --levels 1,2,3 \
  --test-cadence 3 || fail "generation run failed"
AFTER=$(python -c "from storage.repository import Repository as R;c=R().conn.cursor();c.execute('SELECT count(*) FROM posts');print(c.fetchone()[0])")
[ "$AFTER" -gt "$BEFORE" ] || fail "no new posts written (before=$BEFORE after=$AFTER)"
pass "generation wrote $((AFTER - BEFORE)) new posts (total: $AFTER)"

step "6. Inspect a sample"
# topic_id is assigned by the LLM during curriculum generation, so read the
# most recently written one back from the DB rather than guessing it.
TOPIC_ID=$(python -c "from storage.repository import Repository as R;c=R().conn.cursor();c.execute('SELECT topic_id FROM posts ORDER BY created_at DESC LIMIT 1');print(c.fetchone()[0])" 2>/dev/null || true)
if [ -n "${TOPIC_ID:-}" ]; then
  python -m scripts.show_posts --topic "$TOPIC_ID" --level 2 --limit 3 || true
fi

printf '\n\033[32mSmoke test passed.\033[0m\n'
