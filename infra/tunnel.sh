#!/usr/bin/env bash
# Open an SSH tunnel from your LAPTOP to the ScrollWise app tier on EC2.
#
# Forwards two local ports to the EC2 box's localhost:
#   localhost:5173 -> EC2 Vite  (the frontend)
#   localhost:8000 -> EC2 API   (the backend)
#
# Because both ends are "localhost", the apps' built-in defaults just work:
# the web bundle calls http://localhost:8000 (your tunnel -> EC2 API), and the
# API's CORS already allows http://localhost:5173. No app config changes needed.
#
# Prereq: infra/ec2_app_setup.sh has been run on the EC2 box so both services
# are up. Your security group only needs port 22 (SSH) open — not 8000/5173.
#
# Usage:
#   chmod +x infra/tunnel.sh
#   ./infra/tunnel.sh <EC2_PUBLIC_IP_OR_DNS> [ssh_user] [path_to_key.pem]
#
# Examples:
#   ./infra/tunnel.sh 12.34.56.78
#   ./infra/tunnel.sh ec2-12-34-56-78.compute-1.amazonaws.com ubuntu infra/models_server_keypair.pem
#
# Then open http://localhost:5173 in your browser. Ctrl-C closes the tunnel.

set -euo pipefail

HOST="${1:-}"
SSH_USER="${2:-ubuntu}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEY="${3:-$SCRIPT_DIR/models_server_keypair.pem}"

if [ -z "$HOST" ]; then
  echo "Usage: $0 <EC2_PUBLIC_IP_OR_DNS> [ssh_user] [path_to_key.pem]" >&2
  exit 2
fi
if [ ! -f "$KEY" ]; then
  echo "SSH key not found: $KEY" >&2
  exit 2
fi

# SSH refuses keys that are group/world-readable.
chmod 600 "$KEY" 2>/dev/null || true

echo "Tunneling localhost:5173 -> $HOST:5173  and  localhost:8000 -> $HOST:8000"
echo "Open http://localhost:5173 in your browser. Ctrl-C to disconnect."
echo ""

exec ssh -i "$KEY" \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -L 5173:localhost:5173 \
  -L 8000:localhost:8000 \
  "$SSH_USER@$HOST"
