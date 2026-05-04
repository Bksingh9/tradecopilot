# Single-VPS deploy (Ubuntu)

> Educational use only. Not financial advice.

What you get on one $5–$20/mo VPS (Hetzner / DO / Vultr / Linode / Lightsail):

- Caddy (auto-Let's-Encrypt) on `:80` and `:443` reverse-proxying `/api/*` → backend, everything else → frontend.
- FastAPI + AI worker + Postgres 16 + Redis 7 in containers.
- Systemd unit so the stack survives reboots and `apt upgrade`.

## Prereqs

- A fresh Ubuntu 22.04+ box with a public IP.
- A domain name with an A record pointing at that IP (else use `localhost` for dev).
- Ports 80 + 443 open in the firewall.

## One-liner (from your laptop)

```bash
# get the repo onto the box
ssh root@your-server 'apt-get update -y && apt-get install -y git'
ssh root@your-server 'git clone https://github.com/YOUR_GH_USER/tradecopilot.git /opt/tradecopilot'

# run the installer (it will git-pull on subsequent runs)
ssh root@your-server 'cd /opt/tradecopilot && bash deploy/vps/install.sh tradecopilot.example.com you@example.com'
```

## What the installer does

1. Installs Docker + the Compose plugin if missing.
2. Generates strong `JWT_SECRET`, `SECRETS_FERNET_KEY`, `PARTNER_API_SECRET` into `backend/.env` (only on first run).
3. Drops a systemd unit (`tradecopilot.service`) wrapping `docker compose -f docker-compose.prod.yml up`.
4. Starts the stack. Caddy obtains a TLS cert on first request to your domain.

## Operational

```bash
systemctl status tradecopilot
journalctl -u tradecopilot -f
docker compose -f /opt/tradecopilot/docker-compose.prod.yml ps
docker compose -f /opt/tradecopilot/docker-compose.prod.yml logs -f api
```

## Updating

The installer is idempotent. On subsequent runs it `git pull`s and rebuilds.

```bash
ssh root@your-server 'cd /opt/tradecopilot && bash deploy/vps/install.sh tradecopilot.example.com you@example.com'
```

## Plug an LLM

Edit `/opt/tradecopilot/backend/.env`:

```
AI_COACH_BACKEND=external
AI_SERVICE_URL=https://your-llm-proxy.example/
AI_SERVICE_API_KEY=...
AI_WORKER_ADMIN_TOKEN=tc_...
```

Then `systemctl restart tradecopilot`. The reference proxy lives at `/llm_proxy`.

## Backups

Tag the volumes (`tc_pgdata`, `tc_redisdata`) into your hourly snapshot policy. Or run `pg_dump` from inside the `db` container into S3/B2 on a cron.
