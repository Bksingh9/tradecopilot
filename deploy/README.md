# Deploy

> Educational use only. Not financial advice.

Pick whichever target fits. Each subdirectory is a self-contained bundle with its own README + the exact commands.

| Target | Best for | Time | Cost / mo (idle) | One-liner |
|---|---|---|---|---|
| **[Render](./render/)** | Free tier with Blueprint = single yaml. Cold-start ~50s. | ~10 min | $0 (free) – $15 (paid) | push → click "New Blueprint" |
| **[Railway](./railway/)** | No cold starts, simplest UX, managed PG+Redis. | ~10 min | ~$8–12 | `bash deploy/railway/deploy.sh` |
| **[Fly.io](./fly/)** | Fast global, Postgres + Upstash Redis built in. | ~10 min | ~$10 | `bash deploy/fly/deploy.sh` |
| **[DigitalOcean](./digitalocean/)** | Single managed app, managed Postgres + Redis. | ~10 min | ~$25 | `doctl apps create --spec deploy/digitalocean/app.yaml` |
| **[AWS](./aws/)** | Full VPC + ECS Fargate + RDS + ElastiCache + S3/CloudFront. | ~25 min | ~$30+ | `cd deploy/aws && terraform apply` |
| **[VPS](./vps/)** | Single Ubuntu box. Caddy auto-TLS. | ~5 min | ~$5 | `bash deploy/vps/install.sh DOMAIN ADMIN_EMAIL` |
| **Local** | Run on your laptop. | ~2 min | $0 | `docker compose -f docker-compose.prod.yml up --build` |

All paths converge on the same architecture:

```
                            ┌──────────────────────────┐
                            │  Frontend (Vite + nginx) │
                            └───────────┬──────────────┘
                                        │  /api/*, /health/*
                                        ▼
                            ┌──────────────────────────┐
                            │  FastAPI (uvicorn)       │
                            └───┬─────────┬────────────┘
                                │         │
                ┌───────────────┘         └──────────────┐
                ▼                                         ▼
        ┌──────────────┐                          ┌──────────────┐
        │ Postgres 16  │                          │ Redis 7      │
        └──────────────┘                          └──────┬───────┘
                                                          │ BLPOP
                                                          ▼
                                              ┌──────────────────────┐
                                              │  AI worker           │
                                              │  ↓ HTTP              │
                                              │  AI_SERVICE_URL ───► │  (Claude / OpenAI / echo;
                                              │                      │   see /llm_proxy)
                                              └──────────────────────┘
```

## What you'll need before deploying

- A GitHub repo of this codebase (Render / DO / Fly remote-only optionally need this).
- Provider credentials (Render account / `flyctl auth login` / `doctl auth init` / AWS CLI / SSH access).
- A domain name (optional — every target gives you a default URL).
- An LLM key (optional). The default is `AI_COACH_BACKEND=fake`. The reference LLM proxy at `/llm_proxy` accepts Anthropic or OpenAI keys and falls back to deterministic echo.

## Compliance / hard caps reminder

Every target sets these env defaults:

```
KILL_SWITCH_HARD_DAILY_LOSS_PCT=5.0
KILL_SWITCH_HARD_MAX_OPEN_POSITIONS=20
```

These are *absolute* ceilings; no UI knob and no AI suggestion can loosen them. Tighten them in env if you want stricter behaviour (e.g. set `…_DAILY_LOSS_PCT=2.0`).

## Local first

The fastest verification is local:

```bash
docker compose -f docker-compose.prod.yml up --build
# api      → http://localhost/api/health/core
# console  → http://localhost
```

Caddy answers on `localhost` (HTTP only, since no real domain). The frontend is served at `/` and `/api/*` is reverse-proxied to the backend, so it behaves exactly like every cloud target.
