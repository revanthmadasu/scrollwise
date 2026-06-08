#!/usr/bin/env bash
# Install the ScrollWise prompt-drain worker as an always-on systemd service.
#
# This makes the content-generator continuously poll the `user_prompts` queue
# and generate content the moment a prompt is enqueued by apps/api. systemd
# gives us the "always run" guarantees nohup can't: auto-restart on crash and
# auto-start on boot.
#
# It polls every DRAIN_INTERVAL seconds (default 2 — effectively "as soon as
# they occur" for a human). For true zero-latency push you'd wire the API's
# generation_service.enqueue() to SQS/Lambda or Postgres LISTEN/NOTIFY later;
# this poller is the simple, robust EC2 answer for now.
#
# Run on the EC2 box as a normal sudo user (e.g. ubuntu), from inside the repo:
#   chmod +x infra/ec2_drain_setup.sh
#   ./infra/ec2_drain_setup.sh
#
# Tunables (export before running):
#   DRAIN_INTERVAL=2   BATCH_SIZE=5
#   DB_NAME / DB_USER / DB_PASS / DB_HOST / DB_PORT  (must match the generator's
#                                                     ec2_setup.sh; used only if
#                                                     .env doesn't exist yet)
set -euo pipefail

if [ -t 2 ]; then RED=$'\033[31m'; RESET=$'\033[0m'; else RED=''; RESET=''; fi
err() { echo "${RED}$*${RESET}" >&2; }

DRAIN_INTERVAL="${DRAIN_INTERVAL:-2}"
BATCH_SIZE="${BATCH_SIZE:-5}"
DB_NAME="${DB_NAME:-content_generator}"
DB_USER="${DB_USER:-cguser}"
DB_PASS="${DB_PASS:-changeme}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GEN_DIR="$REPO_ROOT/services/content-generator"
RUN_USER="$(id -un)"
SERVICE="scrollwise-drain"
UNIT_PATH="/etc/systemd/system/${SERVICE}.service"

echo "==> Repo: $REPO_ROOT"
echo "==> Service will run as user: $RUN_USER"

# ----------------------------------------------------------- python + venv
echo "==> Setting up the content-generator venv"
sudo apt-get update -y
if command -v python3.12 >/dev/null 2>&1; then
  PYTHON=python3.12; sudo apt-get install -y python3.12-venv
elif command -v python3 >/dev/null 2>&1; then
  PYTHON=python3; sudo apt-get install -y python3-venv python3-pip
else
  err "!!  No python3 found. Aborting."; exit 1
fi

"$PYTHON" -m venv "$GEN_DIR/.venv"
"$GEN_DIR/.venv/bin/pip" install --upgrade pip >/dev/null
"$GEN_DIR/.venv/bin/pip" install -r "$GEN_DIR/requirements.txt"
# Postgres driver for the generator's Repository (DB_BACKEND=postgres).
"$GEN_DIR/.venv/bin/pip" install psycopg2-binary

# ------------------------------------------------------------------- .env
if [ ! -f "$GEN_DIR/.env" ]; then
  echo "==> Writing $GEN_DIR/.env (Bedrock + Postgres defaults)"
  cat > "$GEN_DIR/.env" <<ENV
# LLM backend — bedrock uses the EC2 instance role (no key needed)
LLM_BACKEND=bedrock
LLM_MODEL=anthropic.claude-opus-4-5
AWS_REGION=us-east-1

EMBEDDING_BACKEND=hash
IMAGE_BACKEND=stub

# Generator uses raw psycopg2 — plain libpq URL (NOT the +asyncpg the API uses).
DB_BACKEND=postgres
DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}
ENV
else
  echo "==> $GEN_DIR/.env already exists — leaving it untouched"
fi

# --------------------------------------------------------------- systemd unit
echo "==> Installing systemd unit: $UNIT_PATH"
sudo tee "$UNIT_PATH" >/dev/null <<UNIT
[Unit]
Description=ScrollWise prompt-drain worker (content-generator)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${GEN_DIR}
ExecStart=${GEN_DIR}/.venv/bin/python -m scripts.drain_prompts --interval ${DRAIN_INTERVAL} --batch-size ${BATCH_SIZE}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

echo "==> Enabling + starting the service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE" >/dev/null
sudo systemctl restart "$SERVICE"
sleep 2

if systemctl is-active --quiet "$SERVICE"; then
  echo "    Status: active ✓"
else
  err "!!  Service is not active. Check: journalctl -u $SERVICE -n 50 --no-pager"
fi

cat <<DONE

==========================================
  Prompt-drain worker installed
==========================================
  Service : ${SERVICE}   (polls every ${DRAIN_INTERVAL}s, batch ${BATCH_SIZE})
  Runs    : ${GEN_DIR}/.venv/bin/python -m scripts.drain_prompts

Manage it:
  systemctl status ${SERVICE}
  journalctl -u ${SERVICE} -f        # live logs (JSON: prompt_claimed/ready/failed)
  sudo systemctl restart ${SERVICE}
  sudo systemctl disable --now ${SERVICE}   # stop + don't start on boot

It auto-restarts on crash and on reboot. If apps/api hasn't created the
user_prompts table yet, the worker waits for it (no crash-loop).
DONE
