#!/usr/bin/env bash
# End-to-end Railway deploy.
#
# Targets Railway CLI v3.x (current). The v2 `railway service create` was
# removed; v3 uses `railway add --service NAME` instead.
#
# Prereqs:
#   * Railway account on the Hobby plan ($5/mo trial credit included).
#   * Railway CLI v3.4+ : `brew install railway` or `npm i -g @railway/cli`.
#   * `railway login` once.
#   * Local tools: openssl, python3 (for Fernet key gen).
#
# What this does:
#   1. Initialises (or links) a Railway project named "tradecopilot".
#   2. Adds Postgres + Redis plugins (idempotent).
#   3. Creates two empty services: tradecopilot-api and tradecopilot-web.
#   4. Generates JWT_SECRET + SECRETS_FERNET_KEY + PARTNER_API_SECRET.
#   5. Sets all hard-cap, CORS, autonomy, and Dockerfile-path env vars per service.
#   6. Wires DATABASE_URL / REDIS_URL via Railway's `${{ Postgres.… }}` references.
#   7. Deploys both services from the repo root with `railway up`.
#   8. Generates public domains and prints the URLs.
#
# Usage:  bash deploy/railway/deploy.sh
#
# Re-run-safe — every step swallows "already exists" but surfaces real errors.
set -euo pipefail

if ! command -v railway >/dev/null; then
  echo "railway CLI not found. Install:"
  echo "    brew install railway          # macOS"
  echo "    npm i -g @railway/cli         # any platform"
  echo "Then: railway login"
  exit 1
fi
if ! command -v openssl >/dev/null; then
  echo "openssl required"; exit 1
fi
if ! command -v python3 >/dev/null; then
  echo "python3 required (for Fernet key generation)"; exit 1
fi

# Repo root.
cd "$(dirname "$0")/../.."

PROJECT_NAME=${PROJECT_NAME:-tradecopilot}
API_SERVICE=${API_SERVICE:-tradecopilot-api}
WEB_SERVICE=${WEB_SERVICE:-tradecopilot-web}

echo "==> verifying login"
railway whoami

echo "==> initialising / linking project [$PROJECT_NAME]"
if [[ -z "${TC_PROJECT_ID:-}" ]]; then
  # `railway init` prompts unless --name is supplied; --name makes it idempotent-ish.
  railway init --name "$PROJECT_NAME" || echo "   (project may already exist; continuing)"
else
  railway link --project "$TC_PROJECT_ID"
fi

echo "==> adding Postgres + Redis (idempotent)"
# v3 syntax. `--database` flag accepts: postgres, mysql, redis, mongo.
# Errors here usually mean "already added" — we tolerate them.
railway add --database postgres 2>&1 | grep -v -i "already" || true
railway add --database redis    2>&1 | grep -v -i "already" || true

echo "==> generating secrets (locally; never echoed to stdout)"
JWT_SECRET=$(openssl rand -hex 32)
FERNET=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
PARTNER_API_SECRET=$(openssl rand -hex 24)

# ----------------------------------------------------------------------------
# API service
# ----------------------------------------------------------------------------
echo "==> creating service [$API_SERVICE]"
railway add --service "$API_SERVICE" 2>&1 | grep -v -i "already" || true

echo "==> setting variables for [$API_SERVICE]"
railway variables --service "$API_SERVICE" \
  --set "RAILWAY_DOCKERFILE_PATH=backend/Dockerfile" \
  --set "APP_ENV=prod" \
  --set "JWT_SECRET=$JWT_SECRET" \
  --set "SECRETS_FERNET_KEY=$FERNET" \
  --set "PARTNER_API_SECRET=$PARTNER_API_SECRET" \
  --set "AI_COACH_BACKEND=fake" \
  --set "VECTOR_BACKEND=memory" \
  --set "KILL_SWITCH_HARD_DAILY_LOSS_PCT=5.0" \
  --set "KILL_SWITCH_HARD_MAX_OPEN_POSITIONS=20" \
  --set 'DATABASE_URL=${{ Postgres.DATABASE_URL }}' \
  --set 'REDIS_URL=${{ Redis.REDIS_URL }}'

# CORS allow-list — references the web service's auto-generated public domain.
railway variables --service "$API_SERVICE" \
  --set 'CORS_ALLOW_ORIGINS=https://${{ '"$WEB_SERVICE"'.RAILWAY_PUBLIC_DOMAIN }},http://localhost:5173,http://localhost:4173'

echo "==> deploying [$API_SERVICE]"
railway up --service "$API_SERVICE" --detach

echo "==> generating public domain for [$API_SERVICE]"
railway domain --service "$API_SERVICE" || true

# ----------------------------------------------------------------------------
# Web service
# ----------------------------------------------------------------------------
echo "==> creating service [$WEB_SERVICE]"
railway add --service "$WEB_SERVICE" 2>&1 | grep -v -i "already" || true

# The frontend client.ts auto-detects the Railway hostname pattern and
# points at $API_SERVICE.up.railway.app — no VITE_API_BASE build arg needed.
echo "==> setting variables for [$WEB_SERVICE]"
railway variables --service "$WEB_SERVICE" \
  --set "RAILWAY_DOCKERFILE_PATH=frontend/Dockerfile"

echo "==> deploying [$WEB_SERVICE]"
railway up --service "$WEB_SERVICE" --detach

echo "==> generating public domain for [$WEB_SERVICE]"
railway domain --service "$WEB_SERVICE" || true

echo
echo "================================================================"
echo "Deploy submitted. Both services are building/deploying."
echo
echo "Watch progress:"
echo "    railway logs --service $API_SERVICE"
echo "    railway logs --service $WEB_SERVICE"
echo
echo "Once both are healthy, find the public URLs in the Railway"
echo "dashboard or run:  railway status"
echo
echo "Smoke check (substitute the URLs you see in the dashboard):"
echo "    curl -s https://<api-domain>/health/core"
echo "    open  https://<web-domain>"
echo "================================================================"
