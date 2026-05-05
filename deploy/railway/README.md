# Railway deploy

> Educational use only. Not financial advice.

Railway is a fast, no-cold-start alternative to Render's free tier. Hobby plan
($5/mo trial credit included) gives you always-on services + managed Postgres
+ managed Redis + private networking — same surface area as Fly.io, simpler UX.

## What you get

| Service                | What it is                                  | Source                  |
|------------------------|---------------------------------------------|-------------------------|
| `tradecopilot-api`     | FastAPI on a Railway service (Docker)       | `backend/Dockerfile`    |
| `tradecopilot-web`     | Vite build served by nginx (Docker)         | `frontend/Dockerfile`   |
| `tradecopilot-worker`  | (Optional) AI worker — only with real LLM   | `backend/Dockerfile` + alt CMD |
| Postgres plugin        | Managed Postgres 16                         | Railway plugin          |
| Redis plugin           | Managed Redis 7                             | Railway plugin          |

Postgres + Redis are wired into the API via Railway service references
(`${{ Postgres.DATABASE_URL }}`), so credentials never live in your shell history.

## Two paths to deploy

### A) CLI one-liner (recommended)

```bash
npm i -g @railway/cli
railway login
bash deploy/railway/deploy.sh
```

The script provisions both services + plugins, generates secrets, wires
DATABASE_URL / REDIS_URL, and prints the public URLs at the end.

### B) Dashboard (manual)

1. https://railway.app → **New Project → Deploy from GitHub repo** → select your fork.
2. **Add Plugin → Postgres**, then **Add Plugin → Redis**.
3. Create the **api** service:
   - Root directory: `backend`
   - Dockerfile path: `backend/Dockerfile` (auto-detected)
   - Variables (paste in bulk):
     ```
     APP_ENV=prod
     JWT_SECRET=<run: openssl rand -hex 32>
     SECRETS_FERNET_KEY=<run: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'>
     PARTNER_API_SECRET=<run: openssl rand -hex 24>
     AI_COACH_BACKEND=fake
     VECTOR_BACKEND=memory
     KILL_SWITCH_HARD_DAILY_LOSS_PCT=5.0
     KILL_SWITCH_HARD_MAX_OPEN_POSITIONS=20
     DATABASE_URL=${{ Postgres.DATABASE_URL }}
     REDIS_URL=${{ Redis.REDIS_URL }}
     CORS_ALLOW_ORIGINS=https://${{ tradecopilot-web.RAILWAY_PUBLIC_DOMAIN }},http://localhost:5173
     ```
   - Settings → Networking → **Generate domain**. Copy the URL.
4. Create the **web** service:
   - Root directory: `frontend`
   - Dockerfile path: `frontend/Dockerfile`
   - Variables:
     ```
     VITE_API_BASE=https://<paste API domain from step 3>
     ```
   - The `VITE_API_BASE` must be set as a **Build Variable** (not just a runtime
     env var) — Vite reads it at build time and bakes it into the bundle.
   - Settings → Networking → **Generate domain**.

Each push to the linked GitHub branch redeploys automatically.

## Verify

```bash
API=https://<your-api>.up.railway.app
WEB=https://<your-web>.up.railway.app

curl -s $API/health/core         # → {"ok": true, "db": "ok", "redis": "ok"}
curl -s $API/disclaimer | head
open $WEB                        # signup → dashboard → "Run cycle"
```

The Playwright suite at `e2e/` works against Railway too:

```bash
cd e2e
WEB_BASE_URL=$WEB API_BASE_URL=$API npm run test:api
```

## Costs (Hobby plan)

| Resource             | ~ Cost         |
|----------------------|----------------|
| API service          | $0.50 / month idle, scales with CPU/RAM |
| Web service          | $0.25 / month idle (mostly bandwidth) |
| Postgres (1GB)       | ~$5 base       |
| Redis (256MB)        | ~$1 base       |
| **Estimated total**  | ~$8 – $12 / mo for low traffic |

The $5 Hobby trial credit covers the first month for typical hobby usage.

## Why Railway vs Render

|                          | Railway (Hobby)        | Render (free)            |
|--------------------------|------------------------|--------------------------|
| Cold start               | None                   | ~50 s after 15 min idle  |
| Postgres lifetime        | Always                 | 30-day free tier reset   |
| Build envs at runtime    | Yes (with build vars)  | Static-site rebuild flaky|
| CORS / cross-origin      | Each service its own domain | Same as Railway      |
| Always-on worker         | Yes                    | Paid plan only           |
| Cost                     | ~$8–12/mo              | Free → $14/mo paid       |

Verdict: Render is fine for kicking the tyres; Railway is the saner long-term
free-tier replacement, and the two configs are now interchangeable.

## Compliance reminder

Always start in `paper_only` and `advisory`. The hard caps in `KILL_SWITCH_HARD_*`
cannot be loosened from the UI or the AI; tighten them in the API service env
if you want stricter behaviour.
