# Fly.io deploy

> Educational use only. Not financial advice.

Three Fly apps:

| App | What | Public URL |
|---|---|---|
| `tradecopilot-api`    | FastAPI backend                 | `https://tradecopilot-api.fly.dev` |
| `tradecopilot-worker` | AI worker (no public listener)  | (internal) |
| `tradecopilot-web`    | Vite build → nginx              | `https://tradecopilot-web.fly.dev` |

Plus a Fly **Postgres** cluster (`tradecopilot-db`) and an Upstash **Redis** (`tradecopilot-redis`) provisioned via the Fly extension.

## One-shot

```bash
chmod +x deploy/fly/deploy.sh
bash deploy/fly/deploy.sh
```

The script is idempotent: re-running upgrades each app in place. It creates the apps, generates `JWT_SECRET` + Fernet key, attaches Postgres, provisions Redis, and deploys all three apps with the right secrets.

## Manual (per app)

See the comment block at the top of each `fly.*.toml`. Useful when you want to deploy one service at a time during debugging.

## Plug an LLM

```bash
fly secrets set --app tradecopilot-worker \
    AI_SERVICE_URL=https://your-llm-proxy.example/ \
    AI_SERVICE_API_KEY=... \
    AI_WORKER_ADMIN_TOKEN=tc_...
fly deploy --config deploy/fly/fly.worker.toml --app tradecopilot-worker --remote-only
```

You can run the reference proxy at `/llm_proxy` on a fourth Fly app or anywhere reachable from the worker.

## Pgvector

Fly Postgres ships with the `vector` extension available; enable it once:

```bash
fly postgres connect --app tradecopilot-db
postgres=> CREATE EXTENSION IF NOT EXISTS vector;
```

Then flip on the API + worker:

```bash
fly secrets set --app tradecopilot-api    VECTOR_BACKEND=pgvector
fly secrets set --app tradecopilot-worker VECTOR_BACKEND=pgvector
```
