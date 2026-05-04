# Render deploy

> Educational use only. Not financial advice.

## What you get

- **tradecopilot-api**          — FastAPI on Render Web Service (Docker).
- **tradecopilot-worker**       — AI worker as a Render Background Worker.
- **tradecopilot-web**          — Vite build served as a Render Static Site, with rewrites to the API.
- **tradecopilot-db**           — Managed Postgres.
- **tradecopilot-redis**        — Render Key Value (Redis protocol).

Frontend and API share an origin (`/api/*` is rewritten on the static site), so there are no CORS issues and no `VITE_API_BASE` to fiddle with.

## Steps

1. Push this repo to GitHub.
2. Go to https://dashboard.render.com → **New → Blueprint** → connect the repo.
3. Render reads `deploy/render/render.yaml` and creates the 5 resources above.
4. After the first deploy:
   - Open `tradecopilot-api` → Environment → set `SECRETS_FERNET_KEY`:
     ```bash
     python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
     ```
   - (Optional) set `AI_SERVICE_URL`, `AI_SERVICE_API_KEY`, `AI_WORKER_ADMIN_TOKEN` to wire a real LLM (see `/llm_proxy`).
   - Click **Manual Deploy → Clear build cache & deploy** to pick up the secret.

## Verify

```bash
WEB=https://tradecopilot-web.onrender.com
API=https://tradecopilot-api.onrender.com

curl -s $API/health/core   # → {"ok": true, "db": "ok", ...}
curl -s $API/disclaimer
open $WEB                  # signup → dashboard → "Run cycle"
```

## Costs

Starter plans on Render are paid (the free tier sleeps after inactivity which is bad for a worker). Postgres starter is the cheapest tier; Key Value too. You can scale `api` and `worker` independently later.

## Compliance reminder

Always start in `paper_only` and `advisory`. The hard caps in `KILL_SWITCH_HARD_*` cannot be loosened from the UI or the AI; tighten them in the API service env if you want stricter behaviour.
