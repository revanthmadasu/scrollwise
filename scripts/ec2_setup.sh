#!/usr/bin/env bash
# EC2 setup script for content-generator POC.
# Tested on Ubuntu 24.04 LTS (t3.small or larger).
#
# Usage:
#   chmod +x scripts/ec2_setup.sh
#   sudo ./scripts/ec2_setup.sh
#
# After this script finishes:
#   1. Edit /opt/content-generator/.env with your real values
#   2. Run: cd /opt/content-generator && python -m scripts.generate --topic "Your Topic"

set -euo pipefail

REPO_URL="https://github.com/YOUR_USERNAME/content-generator.git"  # TODO: update
APP_DIR="/opt/content-generator"
DB_NAME="content_generator"
DB_USER="cguser"
DB_PASS="changeme"   # TODO: change before running
PG_VERSION="16"

echo "==> Updating system packages"
apt-get update -y
apt-get upgrade -y

echo "==> Installing system dependencies"
apt-get install -y \
    python3.12 \
    python3.12-venv \
    python3-pip \
    git \
    curl \
    postgresql-${PG_VERSION} \
    postgresql-server-dev-${PG_VERSION}

echo "==> Installing pgvector"
apt-get install -y postgresql-${PG_VERSION}-pgvector

echo "==> Starting Postgres"
systemctl enable postgresql
systemctl start postgresql

echo "==> Creating database and user"
sudo -u postgres psql <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';
  END IF;
END
\$\$;

CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
SQL

sudo -u postgres psql -d ${DB_NAME} -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo "==> Cloning repo"
if [ -d "${APP_DIR}" ]; then
    echo "   ${APP_DIR} already exists — pulling latest"
    git -C "${APP_DIR}" pull
else
    git clone "${REPO_URL}" "${APP_DIR}"
fi

echo "==> Setting up Python virtualenv"
python3.12 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/pip" install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"
"${APP_DIR}/.venv/bin/pip" install psycopg2-binary

echo "==> Writing .env"
cat > "${APP_DIR}/.env" <<ENV
# LLM backend — bedrock uses the EC2 instance role (no key needed)
LLM_BACKEND=bedrock
LLM_MODEL=anthropic.claude-opus-4-5
AWS_REGION=us-east-1

# Embedding (hash is fine for POC; swap to voyage for semantic dedup)
EMBEDDING_BACKEND=hash

# Image (stub for POC)
IMAGE_BACKEND=stub

# Database
DB_BACKEND=postgres
DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}
ENV

echo "==> Initialising database schema"
cd "${APP_DIR}"
sudo -u postgres psql -d ${DB_NAME} -f storage/schema.sql

echo ""
echo "=========================================="
echo "  Setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Edit ${APP_DIR}/.env — update DB_PASS and AWS_REGION if needed"
echo "  2. Attach an IAM role to this EC2 instance with bedrock:InvokeModel permission"
echo "  3. Run:"
echo "       cd ${APP_DIR}"
echo "       source .venv/bin/activate"
echo "       python -m scripts.generate --topic 'Linear Algebra' --modules 3"
echo ""
