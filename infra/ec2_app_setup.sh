#!/usr/bin/env bash
# EC2 setup + run script for the ScrollWise APP tier (API + web).
#
# This is the app-tier companion to services/content-generator/scripts/ec2_setup.sh.
# That script provisions Postgres + the content-generator (the producer). THIS
# script sets up and starts the two long-running app processes that consume it:
#
#   - apps/api  : FastAPI backend  -> 127.0.0.1:8000
#   - apps/web  : Vite dev server  -> 127.0.0.1:5173
#
# Both bind to localhost ONLY. You reach them from your laptop over an SSH
# tunnel (see infra/tunnel.sh) — which is also why no CORS / VITE_API_BASE
# changes are needed: through the tunnel everything looks like localhost, which
# is exactly what the apps already default to.
#
# Prereqs:
#   - Run on the EC2 box as a normal sudo user (e.g. `ubuntu`), NOT as root,
#     from inside the checked-out repo. Tested on Ubuntu 24.04 LTS.
#   - The content-generator's ec2_setup.sh has already run (Postgres + the
#     shared `content_generator` DB with generated posts). If you skipped that,
#     set DATABASE_URL to a SQLite path instead (see below) — but the feed will
#     be empty until the generator has written posts.
#
# Usage:
#   chmod +x infra/ec2_app_setup.sh
#   ./infra/ec2_app_setup.sh                 # install + configure + start
#   ./infra/ec2_app_setup.sh --no-start      # install + configure only
#
# Re-running is safe (idempotent): deps are reinstalled, .env is preserved if
# present, and any previously started API/web processes are stopped first.

set -euo pipefail

# ---------------------------------------------------------------- configuration
# These DB values MUST match services/content-generator/scripts/ec2_setup.sh.
# Override by exporting before running, e.g. DB_PASS=... ./infra/ec2_app_setup.sh
DB_NAME="${DB_NAME:-content_generator}"
DB_USER="${DB_USER:-cguser}"
DB_PASS="${DB_PASS:-changeme}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

START_SERVICES=1
for arg in "$@"; do
  case "$arg" in
    --no-start) START_SERVICES=0 ;;
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

# Resolve repo root from this script's location (infra/ lives at the repo root).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_DIR="$REPO_ROOT/apps/api"
WEB_DIR="$REPO_ROOT/apps/web"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

echo "==> Repo root: $REPO_ROOT"

# ----------------------------------------------------------------- system deps
echo "==> Installing system dependencies (curl, Python, Node 22 + npm)"
sudo apt-get update -y

have() { command -v "$1" >/dev/null 2>&1; }

# curl — needed both for the NodeSource installer and the health checks below.
if ! have curl; then
  echo "    Installing curl"
  sudo apt-get install -y curl
fi

# Python 3.12 + venv (Ubuntu 24.04 ships 3.12; fall back to whatever python3 exists).
if have python3.12; then
  PYTHON=python3.12
  sudo apt-get install -y python3.12-venv
elif have python3; then
  PYTHON=python3
  sudo apt-get install -y python3-venv python3-pip
else
  echo "!!  No python3 found and none installable. Aborting." >&2
  exit 1
fi
have "$PYTHON" || { echo "!!  $PYTHON not found after install. Aborting." >&2; exit 1; }
echo "    Python: $($PYTHON --version)"

# Node 22 + npm via NodeSource. The NodeSource `nodejs` package bundles npm, so
# install it whenever node is missing/too old for Vite 5 OR npm is absent
# (e.g. a stray node install without npm — the case that broke the last run).
NODE_MAJOR="$(node -v 2>/dev/null | sed -E 's/v([0-9]+).*/\1/' || true)"
if ! have node || ! have npm || [ "${NODE_MAJOR:-0}" -lt 18 ]; then
  echo "    Installing Node 22 + npm via NodeSource"
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
# Verify both landed — don't limp forward to a confusing failure at `npm install`.
if ! have node || ! have npm; then
  echo "!!  node/npm still missing after install. Check the apt output above." >&2
  exit 1
fi
echo "    Node: $(node -v)  npm: $(npm -v)"

# ----------------------------------------------------------- database grants
# The generator created the DB and tables as the postgres superuser, so the API
# user (cguser) owns the database but not the public schema. On PG15+ that means
# it can't CREATE its own tables or SELECT the generator's. Grant it here.
# Skipped (with a warning) if Postgres / the DB isn't present.
if command -v psql >/dev/null 2>&1 && sudo -u postgres psql -lqt 2>/dev/null | cut -d'|' -f1 | grep -qw "$DB_NAME"; then
  echo "==> Granting $DB_USER privileges on database $DB_NAME"
  sudo -u postgres psql -d "$DB_NAME" -v ON_ERROR_STOP=1 <<SQL
GRANT ALL ON SCHEMA public TO ${DB_USER};
GRANT ALL ON ALL TABLES IN SCHEMA public TO ${DB_USER};
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${DB_USER};
SQL
  API_DB_URL="postgresql+asyncpg://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
else
  echo "!!  Postgres DB '$DB_NAME' not found."
  echo "!!  Run services/content-generator/scripts/ec2_setup.sh first, or the"
  echo "!!  feed will have no posts. Falling back to a local SQLite DB for now."
  API_DB_URL="sqlite+aiosqlite:///${API_DIR}/scrollwise.db"
fi

# ------------------------------------------------------------------- API setup
echo "==> Setting up apps/api"
$PYTHON -m venv "$API_DIR/.venv"
"$API_DIR/.venv/bin/pip" install --upgrade pip >/dev/null
"$API_DIR/.venv/bin/pip" install -r "$API_DIR/requirements.txt"

if [ ! -f "$API_DIR/.env" ]; then
  echo "    Writing apps/api/.env"
  JWT_SECRET="$("$API_DIR/.venv/bin/python" -c 'import secrets; print(secrets.token_urlsafe(48))')"
  cat > "$API_DIR/.env" <<ENV
# Shared database (same as the content-generator). Async driver for SQLAlchemy.
DATABASE_URL=${API_DB_URL}

# Auth
JWT_SECRET=${JWT_SECRET}
JWT_ACCESS_TTL_MIN=30
JWT_REFRESH_TTL_DAYS=30

# Google OIDC (optional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# CORS — localhost:5173 is the tunneled Vite origin; no EC2 host needed.
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
ENV
else
  echo "    apps/api/.env already exists — leaving it untouched"
fi

# ------------------------------------------------------------------- web setup
echo "==> Setting up apps/web"
( cd "$WEB_DIR" && npm install )
# No web .env needed: the bundle's API base defaults to http://localhost:8000,
# which resolves through the SSH tunnel to the API on EC2.

if [ "$START_SERVICES" -eq 0 ]; then
  echo ""
  echo "Setup complete (services NOT started). Start them with:"
  echo "  ./infra/ec2_app_setup.sh        # re-run to install + start"
  exit 0
fi

# --------------------------------------------------------------- start services
echo "==> Stopping any previous API/web processes"
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 1

echo "==> Starting API (127.0.0.1:8000)"
( cd "$API_DIR" && nohup .venv/bin/python -m uvicorn app.main:app \
    --host 127.0.0.1 --port 8000 > "$LOG_DIR/api.log" 2>&1 & echo $! > "$LOG_DIR/api.pid" )

echo "==> Starting web (127.0.0.1:5173)"
( cd "$WEB_DIR" && nohup npm run dev -- --port 5173 --strictPort \
    > "$LOG_DIR/web.log" 2>&1 & echo $! > "$LOG_DIR/web.pid" )

# Give them a moment, then sanity-check.
sleep 5
echo ""
if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "    API health: OK  (http://127.0.0.1:8000/health)"
else
  echo "!!  API not responding yet — check $LOG_DIR/api.log"
fi
if curl -fsS http://127.0.0.1:5173 >/dev/null 2>&1; then
  echo "    Web:        OK  (http://127.0.0.1:5173)"
else
  echo "!!  Web not responding yet — check $LOG_DIR/web.log"
fi

cat <<DONE

==========================================
  App tier is running on EC2 (localhost-only)
==========================================

  API : 127.0.0.1:8000   log: infra/logs/api.log   pid: infra/logs/api.pid
  Web : 127.0.0.1:5173   log: infra/logs/web.log   pid: infra/logs/web.pid

Now, FROM YOUR LAPTOP, open the tunnel and browse:

  ./infra/tunnel.sh <EC2_PUBLIC_IP>
  # then open http://localhost:5173

To stop the services on EC2:
  pkill -f "uvicorn app.main:app"; pkill -f vite
DONE
