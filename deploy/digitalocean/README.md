# DigitalOcean App Platform deploy

> Educational use only. Not financial advice.

App Platform builds the backend Docker image, the frontend Vite static bundle, and runs the AI worker — all from one App Spec.

## Prereqs

```bash
# https://docs.digitalocean.com/reference/doctl/how-to/install/
brew install doctl
doctl auth init
```

## Steps

1. Edit `deploy/digitalocean/app.yaml` — replace `YOUR_GH_USER/tradecopilot` (3×) with your repo path.
2. Push the repo to GitHub. Grant DO access to the repo.
3. Create the app:
   ```bash
   doctl apps create --spec deploy/digitalocean/app.yaml
   ```
4. After the first deploy, fill the `TODO-…` secrets in the UI:
   - `JWT_SECRET` — `openssl rand -hex 32`
   - `SECRETS_FERNET_KEY` — `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`
   - `PARTNER_API_SECRET` — any long random string
   - `AI_SERVICE_URL` / `AI_SERVICE_API_KEY` / `AI_WORKER_ADMIN_TOKEN` — only if you want a live LLM

5. Trigger a redeploy (Settings → Force Rebuild) so the secrets take effect.

## Verify

App Platform exposes a single URL that does the routing for you. The frontend is served at `/`, the API at `/api/*`, `/health/*`, `/disclaimer`. Open the App URL from the dashboard, sign up, run a cycle.

## Pgvector

If you want pgvector instead of the in-memory backend:

```bash
doctl databases sql tradecopilot-db --command "CREATE EXTENSION IF NOT EXISTS vector;"
```

Then in App Platform set `VECTOR_BACKEND=pgvector` on both the `api` service and the `ai-worker`.
