#!/usr/bin/env bash
# End-to-end Railway deploy.
#
# Prereqs:
#   * Railway account + a payment method on file (Hobby plan = $5/mo trial credit).
#   * Railway CLI: `npm i -g @railway/cli` then `railway login`.
#   * Local tools: jq, openssl, python3 (for Fernet key gen).
#
# What this does:
#   1. Creates a Railway project (or reuses TC_PROJECT_ID if exported).
#   2. Adds Postgres + Redis plugins.
#   3. Creates two services from this repo: api (backend/) and web (frontend/).
#   4. Generates JWT_SECRET + SECRETS_FERNET_KEY.
#   5. Wires DATABASE_URL / REDIS_URL via Railway service references.
#   6. Sets all hard-cap + autonomy env vars.
#   7. Deploys both services and prints the public URLs.
#
# Usage:  bash deploy/railway/deploy.sh
#
# Re-run-safe: skips already-existing resources where possible.
set -euo pipefail

if ! command -v railway >/dev/null; then
  echo "railway CLI not found. Install: npm i -g @railway/cli"; exit 1
fi
if ! command -v jq >/dev/null; then
  echo "jq required (brew install jq / apt install jq)"; exit 1
fi
if ! command -v openssl >/dev/null; then
  echo "openssl required"; exit 1
fi

cd "$(dirname "$0")/../.."

PROJECT_NAME=${PROJECT_NAME:-tradecopilot}
API_SERVICE=${API_SERVICE:-tradecopilot-api}
WEB_SERVICE=${WEB_SERVICE:-tradecopilot-web}

echo "==> ensuring you're logged in"
railway whoami >/dev/null

echo "==> creating / linking project [$PROJECT_NAME]"
if [[ -z "${TC_PROJECT_ID:-}" ]]; then
  railway init --name "$PROJECT_NAME" >/dev/null || true
else
  railway link --project "$TC_PROJECT_ID" >/dev/null
fi

echo "==> adding Postgres + Redis plugins (idempotent)"
railway add --plugin postgresql 2>/dev/null || echo "   postgres: already present"
railway add --plugin redis      2>/dev/null || echo "   redis: already present"

echo "==> generating secrets"
JWT_SECRET=$(openssl rand -hex 32)
FERNET=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
PARTNER_API_SECRET=$(openssl rand -hex 24)

echo "==> creating service [$API_SERVICE]"
railway service create "$API_SERVICE" 2>/dev/null || echo "   $API_SERVICE: already present"
railway service "$API_SERVICE"

# Point this service at the backend Dockerfile.
railway variables \
  --set "RAILWAY_DOCKERFILE_PATH=backend/Dockerfile" \
  --set "JWT_SECRET=$JWT_SECRET" \
  --set "SECRETS_FERNET_KEY=$FERNET" \
  --set "PARTNER_API_SECRET=$PARTNER_API_SECRET" \
  --set "APP_ENV=prod" \
  --set "AI_COACH_BACKEND=fake" \
  --set "VECTOR_BACKEND=memory" \
  --set "KILL_SWITCH_HARD_DAILY_LOSS_PCT=5.0" \
  --set "KILL_SWITCH_HARD_MAX_OPEN_POSITIONS=20" \
  --set 'DATABASE_URL=${{ Postgres.DATABASE_URL }}' \
  --set 'REDIS_URL=${{ Redis.REDIS_URL }}'

# Allow CORS from the web service domain (Railway auto-injects RAILWAY_PUBLIC_DOMAIN).
railway variables --set 'CORS_ALLOW_ORIGINS=https://${{ '"$WEB_SERVICE"'.RAILWAY_PUBLIC_DOMAIN }},http://localhost:5173,http://localhost:4173'

echo "==> deploying $API_SERVICE"
railway up --service "$API_SERVICE" --detach

# Public domain for the API — Railway needs this to issue a public URL.
railway domain --service "$API_SERVICE" >/dev/null 2>&1 || true
API_URL="https://$(railway status --json | jq -r --arg s "$API_SERVICE" '.services[] | select(.name==$s) | .domains[0]')"
echo "   API: $API_URL"

echo "==> creating service [$WEB_SERVICE]"
railway service create "$WEB_SERVICE" 2>/dev/null || echo "   $WEB_SERVICE: already present"
railway service "$WEB_SERVICE"

railway variables \
  --set "RAILWAY_DOCKERFILE_PATH=frontend/Dockerfile" \
  --set "VITE_API_BASE=$API_URL"

# Pass VITE_API_BASE through Docker build args so it's baked into the SPA bundle.
railway variables --set 'NIXPACKS_BUILD_ARGS=VITE_API_BASE='"$API_URL"

echo "==> deploying $WEB_SERVICE"
railway up --service "$WEB_SERVICE" --detach
railway domain --service "$WEB_SERVICE" >/dev/null 2>&1 || true
WEB_URL="https://$(railway status --json | jq -r --arg s "$WEB_SERVICE" '.services[] | select(.name==$s) | .domains[0]')"

echo
echo "All up:"
echo "  API: $API_URL"
echo "  WEB: $WEB_URL"
echo
echo "Smoke check:"
echo "  curl -s $API_URL/health/core"
echo "  open $WEB_URL"
echo
echo "Reminder: set AI_SERVICE_URL / AI_SERVICE_API_KEY to wire a real LLM (see /llm_proxy)."
