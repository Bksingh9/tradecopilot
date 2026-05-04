#!/usr/bin/env bash
# Install + run TradeCopilot on a fresh Ubuntu 22.04+ VPS.
#
# Idempotent: re-running pulls latest, rebuilds, and restarts.
#
# Run once on a fresh box:
#   sudo bash deploy/vps/install.sh tradecopilot.example.com you@example.com
#
# Args:
#   $1 = DOMAIN          (e.g. tradecopilot.example.com — must already point at this server's public IP)
#   $2 = ADMIN_EMAIL     (used for Let's Encrypt registration via Caddy)
#
# What this does:
#   - installs docker + docker compose plugin
#   - copies repo to /opt/tradecopilot (assumes you've cloned it nearby OR pulls from $REPO_URL)
#   - generates strong secrets in backend/.env if missing
#   - boots docker-compose.prod.yml under a systemd unit
set -euo pipefail

DOMAIN="${1:-localhost}"
ADMIN_EMAIL="${2:-admin@example.com}"
TARGET="/opt/tradecopilot"
REPO_URL="${REPO_URL:-}"          # set this if you want install.sh to git-clone instead of using the cwd

if [[ "$EUID" -ne 0 ]]; then
  echo "must run as root (sudo bash $0 ...)"; exit 1
fi

echo "==> [1/5] installing docker"
if ! command -v docker >/dev/null; then
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg openssl python3 python3-pip
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
       https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" \
       > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
fi

echo "==> [2/5] placing repo at $TARGET"
if [[ ! -d "$TARGET/.git" && -n "$REPO_URL" ]]; then
  rm -rf "$TARGET"
  git clone "$REPO_URL" "$TARGET"
elif [[ ! -d "$TARGET" ]]; then
  # fallback: copy the current dir
  mkdir -p "$TARGET"
  rsync -a --delete --exclude=node_modules --exclude=__pycache__ ./ "$TARGET/"
else
  ( cd "$TARGET" && git pull --ff-only || true )
fi

cd "$TARGET"

echo "==> [3/5] generating secrets (only if backend/.env is missing)"
if [[ ! -f backend/.env ]]; then
  cp backend/.env.example backend/.env
  JWT=$(openssl rand -hex 32)
  FERNET=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
  PARTNER=$(openssl rand -hex 32)
  sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${JWT}|" backend/.env
  sed -i "s|^SECRETS_FERNET_KEY=.*|SECRETS_FERNET_KEY=${FERNET}|" backend/.env
  sed -i "s|^PARTNER_API_SECRET=.*|PARTNER_API_SECRET=${PARTNER}|" backend/.env
  echo "secrets written to backend/.env (JWT_SECRET, SECRETS_FERNET_KEY, PARTNER_API_SECRET)"
fi

# Caddy needs the domain at runtime.
mkdir -p /etc/tradecopilot
cat > /etc/tradecopilot/env <<EOF
DOMAIN=${DOMAIN}
ACME_EMAIL=${ADMIN_EMAIL}
EOF

echo "==> [4/5] installing systemd unit"
cp deploy/vps/tradecopilot.service /etc/systemd/system/tradecopilot.service
systemctl daemon-reload
systemctl enable tradecopilot.service

echo "==> [5/5] building + starting"
systemctl restart tradecopilot.service

echo
echo "started. check:"
echo "  systemctl status tradecopilot"
echo "  journalctl -u tradecopilot -f"
echo "  docker compose -f $TARGET/docker-compose.prod.yml ps"
echo
echo "open https://$DOMAIN once DNS + Let's Encrypt finish (usually <1 min)."
