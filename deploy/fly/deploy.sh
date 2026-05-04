#!/usr/bin/env bash
# End-to-end Fly.io deploy.
#
# Prereqs: a Fly account, `fly auth login`, `jq`, `openssl`, `python3`.
#
# Usage:  bash deploy/fly/deploy.sh
set -euo pipefail

if ! command -v fly >/dev/null; then
  echo "fly CLI not found. Install: https://fly.io/docs/hands-on/install-flyctl/"
  exit 1
fi
if ! command -v jq >/dev/null; then
  echo "jq required (brew install jq / apt install jq)"; exit 1
fi

cd "$(dirname "$0")/../.."

API_APP=${API_APP:-tradecopilot-api}
WORKER_APP=${WORKER_APP:-tradecopilot-worker}
WEB_APP=${WEB_APP:-tradecopilot-web}
DB_APP=${DB_APP:-tradecopilot-db}
REDIS_APP=${REDIS_APP:-tradecopilot-redis}
REGION=${REGION:-iad}

echo "==> creating apps (idempotent)"
fly apps create "$API_APP"    --org personal 2>/dev/null || true
fly apps create "$WORKER_APP" --org personal 2>/dev/null || true
fly apps create "$WEB_APP"    --org personal 2>/dev/null || true

echo "==> generating secrets"
JWT_SECRET=$(openssl rand -hex 32)
FERNET=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

echo "==> postgres (Fly managed)"
fly postgres list | grep -q "$DB_APP" || \
  fly postgres create --name "$DB_APP" --region "$REGION" --initial-cluster-size 1 --vm-size shared-cpu-1x --volume-size 3
fly postgres attach "$DB_APP" --app "$API_APP"    || true
fly postgres attach "$DB_APP" --app "$WORKER_APP" || true

echo "==> redis (Upstash via Fly extension)"
fly redis status "$REDIS_APP" >/dev/null 2>&1 || fly redis create --name "$REDIS_APP" --region "$REGION" --no-replicas --plan free
REDIS_URL=$(fly redis status "$REDIS_APP" --json | jq -r .private_url)

echo "==> setting secrets"
fly secrets set --app "$API_APP" \
  JWT_SECRET="$JWT_SECRET" \
  SECRETS_FERNET_KEY="$FERNET" \
  REDIS_URL="$REDIS_URL"

fly secrets set --app "$WORKER_APP" \
  JWT_SECRET="$JWT_SECRET" \
  SECRETS_FERNET_KEY="$FERNET" \
  REDIS_URL="$REDIS_URL" \
  API_BASE_URL="https://$API_APP.fly.dev"

echo "==> deploying API"
fly deploy --config deploy/fly/fly.api.toml --app "$API_APP" --remote-only

echo "==> deploying worker"
fly deploy --config deploy/fly/fly.worker.toml --app "$WORKER_APP" --remote-only

echo "==> deploying web"
fly deploy --config deploy/fly/fly.web.toml --app "$WEB_APP" --remote-only \
  --build-arg "VITE_API_BASE=https://$API_APP.fly.dev"

echo
echo "All up:"
echo "  API: https://$API_APP.fly.dev"
echo "  WEB: https://$WEB_APP.fly.dev"
echo
echo "Reminder: set AI_SERVICE_URL / AI_SERVICE_API_KEY / AI_WORKER_ADMIN_TOKEN on $WORKER_APP"
echo "to enable the live LLM coach. Without these, FakeCoach is used."
