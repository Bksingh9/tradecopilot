# TradeCopilot Agent — Backend

> ## ⚠ Disclaimer (read this first)
>
> **TradeCopilot Agent is an educational and decision-support tool only. It does NOT provide guaranteed or assured returns.**
>
> - All trading involves **risk of loss**. You alone are responsible for your decisions.
> - **Past performance and backtest results are not indicative of future results.**
> - We deliberately avoid language like "guaranteed", "sure-shot", or "always accurate". The product is positioned as **risk-managed, process-focused, data-driven** — not a profit engine.
> - Always test in **paper trading** before going live. v1 covers spot equities only — no options, derivatives, or leveraged products.
> - Hard caps on max daily loss and max open positions are env-driven and cannot be loosened by AI suggestions or user edits.
> - User and admin can flip a **kill switch** that immediately blocks all new orders.

---

A multi-tenant agentic FastAPI backend for an "AI desk assistant" sitting on top of Zerodha, Upstox, and Alpaca. Reads market + account data, runs a multi-agent workflow (Analyst → Strategy → Risk → Execution → Coach), enforces user-defined risk rules, auto-journals trades, generates weekly performance reports, and exposes a partner API + embeddable widget.

## Stack

- Python 3.11, FastAPI (REST + WebSocket-ready)
- SQLModel + Alembic (SQLite for dev, Postgres for prod)
- Pydantic v2
- HTTPX, yfinance, 0xramm Indian Stock Market API, Alpaca Data API
- pykiteconnect / Upstox v2 / alpaca-py for trading
- APScheduler (in-process: backtests, ingest)
- Redis (cross-process: AI worker queue, rate limit, worker heartbeat)
- pytest

---

## Repo layout

```
.
├── docker-compose.yml          api + worker + Postgres + Redis
├── plugin/                     embeddable JS/TS widget + partner SDK
└── backend/
    ├── app/
    │   ├── main.py             FastAPI app, rate limit middleware, /disclaimer
    │   ├── config.py           Settings (incl. KILL_SWITCH_HARD_*, REDIS_URL, AI_SERVICE_URL)
    │   ├── database.py         engine + session helpers + db_ping
    │   ├── scheduler.py        APScheduler singleton
    │   ├── auth/               Tenant + User (role + autonomy_mode) + JWT + API tokens
    │   ├── users/              user preferences (tenant-scoped)
    │   ├── audit/              AuditEvent model + append-only writer
    │   ├── data/               nse_india, global_equity, alpaca_data
    │   ├── brokers/            Zerodha / Upstox / Alpaca on a unified ABC
    │   ├── trading/
    │   │   ├── models.py       Trade/Position/RiskRule/JournalEntry +
    │   │   │                   KillSwitch / StrategyTuningSuggestion / BacktestRun / Partner
    │   │   ├── strategies.py   momentum, mean_reversion, ORB
    │   │   ├── risk.py         hard caps + dynamic_risk_caps + kill switch (audit hooked)
    │   │   ├── execution.py    risk + kill-switch gate, broker dispatch (audit hooked)
    │   │   ├── backtesting.py  one-shot backtester
    │   │   └── learning.py     parquet ingest + walk-forward + tag_regime + by_regime metrics
    │   ├── agents/
    │   │   ├── analyst.py      AnalystAgent (features + ML-stub p_up + regime hint)
    │   │   ├── strategy.py     StrategyAgent (regime → strategy choice)
    │   │   ├── risk_agent.py   RiskAgent (approve | scale_down | reject)
    │   │   ├── execution_agent.py ExecutionAgent (mode-aware; EOD-flatten; manage open)
    │   │   ├── coach_agent.py  CoachAgent (weekly review wrapper)
    │   │   ├── orchestrator.py Orchestrator.run_cycle (Analyst → Strategy → Risk → Exec)
    │   │   ├── features.py     pure pandas features + ML-stub + news-stub
    │   │   └── models.py       AnalystSignal / CandidateTrade / RiskDecision / etc.
    │   ├── journal/            entries + analytics (incl. streaks + admin overview)
    │   ├── ai/                 prompts + AICoach + FakeCoach + ExternalQueueCoach (Redis)
    │   ├── api/                routes_auth, _users, _trading, _journal, _ai, _agents,
    │   │                       _audit, _admin, _backtest, _partner, _health
    │   ├── billing/            Subscription + Stripe stub + policy.py (plan gating)
    │   ├── workers/            ai_worker.py (BLPOP loop → AI_SERVICE_URL → /api/ai/callback)
    │   ├── common/             logging (redacting), exceptions, crypto, rate_limit middleware
    │   └── data_ingestion / strategy_signal / risk_portfolio /
    │       journal_analytics / ai_coach / backtest_simulation /
    │       partner_plugin_api    ← alias packages re-exporting the canonical modules
    ├── alembic/                migrations
    ├── tests/{unit,integration}
    ├── Dockerfile
    ├── Makefile
    ├── .env.example
    ├── pyproject.toml
    └── requirements.txt
```

---

## Quick start

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

cd backend
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# paste it into SECRETS_FERNET_KEY. Set JWT_SECRET to any long random string.

make dev                        # → http://localhost:8000/docs
```

In a second terminal (only needed if `AI_COACH_BACKEND=external`):

```bash
make worker
```

### Docker stack

```bash
make up                         # api + worker + Postgres + Redis
```

### Tests

```bash
make test
```

---

## Agentic workflow

A single cycle (`POST /api/agents/cycle/run`) chains five agents:

```
Analyst → Strategy → Risk → Execution → Coach
```

- **Analyst** reads OHLCV via the data layer, computes features (EMA/ATR/RSI/returns), produces a directional probability via a transparent ML-stub, and tags a regime (`bull|bear|range|high_vol|low_vol|crash`). News/sentiment is a stub that returns neutral.
- **Strategy** selects an existing strategy (`momentum` / `mean_reversion` / `orb`) by regime hint and emits `CandidateTrade`s.
- **Risk** wraps `app.trading.risk` (hard caps + dynamic + kill switch). It **scales down** rather than rejects when the only violation is sizing/notional. Hard caps and kill switch always win.
- **Execution** routes approved candidates by autonomy mode:
  - `advisory`  → returns `proposed` (no order placed).
  - `semi_auto` → places, with a one-open-per-symbol guard.
  - `full_auto` → places without per-call confirmation, gated at the orchestrator on `paper_qualified_at + consent_full_auto`.
  - Also exposes `flatten_eod` (NSE 15:30 IST, US 16:00 ET) and `manage_open_trades` (stop / target / time-stop).
- **Coach** wraps `AICoach` weekly review. Never modifies risk rules; only writes `AIReport` rows and `pending` `StrategyTuningSuggestion` entries.

Every stage transition writes an `AuditEvent`. View yours via `GET /api/audit/me`; admins can query the full set via `GET /api/audit/admin`.

## Autonomy modes

`User.autonomy_mode ∈ {"advisory", "semi_auto", "full_auto"}`.

Upgrades to `full_auto` require:
1. `paper_qualified_at` set (≥14 days of paper trading + ≥20 paper trades — enforced at the system layer).
2. Explicit `consent_full_auto: true` in the same `PUT /api/users/autonomy` request.
3. Plan allows it (`team` only).

Downgrade is always permitted. The orchestrator re-checks both flags on every cycle.

## Risk model — what AI can and cannot do

1. **Kill switch** (`KillSwitch` rows) — blocks new orders immediately.
2. **Hard caps** (env: `KILL_SWITCH_HARD_*`) — `effective_rule()` always picks the more conservative of (env, user). AI cannot loosen them.
3. **Dynamic caps** — further tighten when realized vol or drawdown rises.

The AI coach can only:
- Write `AIReport` rows (weekly review, trade comments).
- Write `pending` `StrategyTuningSuggestion` rows proposing parameter tweaks within explicit guardrails.

The AI coach **cannot**:
- Change source code, broker integrations, or risk rules.
- Activate a tuning suggestion — that requires a human `POST /api/trading/tuning/{id}/accept`.

## Plans + RBAC

| Plan | Modes allowed | Symbols/cycle | Backtest runs/day |
|------|---------------|---------------|-------------------|
| free | advisory      | 1             | 5                 |
| pro  | advisory, semi_auto | 25      | 50                |
| team | + full_auto eligible | 100   | 500               |

Roles: `user` (default) and `admin` (can view tenant-wide + anonymized aggregates, run audit queries, set tenant-wide kill switch, provision partners).

## Wiring an LLM in production

The backend never calls an LLM in-process. It pushes rendered prompts (see `app/ai/prompts.py`) onto a Redis list. A separate worker (`app/workers/ai_worker.py`) drains the list, calls `AI_SERVICE_URL` over HTTP, and POSTs the result to `/api/ai/callback` (admin-token auth).

Set in `.env`:

```
AI_COACH_BACKEND=external
AI_SERVICE_URL=https://your-llm-proxy.example/
AI_SERVICE_API_KEY=...
AI_WORKER_ADMIN_TOKEN=tc_...        # an admin user's API token
```

If the worker is down, the API still works — `FakeCoach` responds synchronously and `/health/ai` reports the degraded status.

## Health endpoints

| Endpoint | Meaning |
|---|---|
| `GET /health/core` | DB connectable + config loaded. If non-200, fail your LB probe. |
| `GET /health/ai`   | Redis + worker heartbeat freshness. `worker_stale` is OK to serve traffic. |

## Rate limits

A `RateLimitMiddleware` is installed by default (Redis-backed if available; in-process fallback). Limit: 120 requests / 60 s per identifier (X-Partner-Key, X-API-Token, JWT, or remote IP). `/health/*`, `/disclaimer`, `/docs`, and `/openapi.json` are exempted.

## Sample backtest

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"me@example.com","password":"hunter2hunter2"}' | jq -r .access_token)

# walk-forward over 2 years on RELIANCE (yfinance .NS)
curl -s -X POST "http://localhost:8000/api/backtest/run?strategy=momentum" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{
    "symbols": ["RELIANCE.NS"],
    "timeframe": "1d",
    "start": "2023-01-01T00:00:00Z",
    "end":   "2025-01-01T00:00:00Z",
    "walk_forward_folds": 4,
    "param_grid": {"fast": [9,12], "slow": [21,26]}
  }'
# → {"id": 1, "status": "queued", ...}

# poll until status="done", then read metrics:
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/backtest/1
# response includes metrics.cagr, metrics.sharpe, metrics.max_dd,
# metrics.win_rate, metrics.profit_factor, metrics.trade_count,
# and metrics.by_regime (per-regime breakout)
```

> **Reminder:** backtest results are not indicative of future results. The platform reports only what it actually computed; nothing is fabricated.

## Compliance language style guide

When you add UI copy, README sections, or marketing text:

- ✅ Use: "risk-managed", "process-focused", "data-driven", "decision-support", "improve discipline", "structure your risk".
- ❌ Avoid: "guaranteed", "guaranteed profits", "sure-shot", "always accurate", "no risk", "secret formula".

Every external response (`/disclaimer`, weekly reports, trade comments) carries an explicit "Educational use only. Not financial advice." footer.

---

## Key endpoints

```
POST   /api/auth/signup
POST   /api/auth/login
POST   /api/auth/api-tokens
GET    /api/auth/broker/{broker}/login-url
POST   /api/auth/broker/connect

GET    /api/users/autonomy
PUT    /api/users/autonomy
POST   /api/users/qualify-paper

GET    /api/trading/quote
GET    /api/trading/signals
POST   /api/trading/orders?broker=...
GET    /api/trading/risk
PUT    /api/trading/risk
GET    /api/trading/dashboard
POST   /api/trading/kill-switch
POST   /api/trading/kill-switch/{id}/clear
GET    /api/trading/tuning
POST   /api/trading/tuning/{id}/accept
POST   /api/trading/tuning/{id}/reject

POST   /api/agents/cycle/run
POST   /api/agents/flatten-now
POST   /api/agents/manage-open
POST   /api/agents/coach/weekly

POST   /api/journal/entries
GET    /api/journal/entries
GET    /api/journal/trades
GET    /api/journal/summary           # incl. streaks

POST   /api/ai/weekly-report
POST   /api/ai/trade-comment/{trade_id}
POST   /api/ai/tuning/request
POST   /api/ai/callback               # admin-only (worker writes here)
GET    /api/ai/reports

POST   /api/backtest/run              # async; result includes metrics.by_regime
GET    /api/backtest/{id}
GET    /api/backtest

GET    /api/audit/me
GET    /api/audit/admin               # admin-only

POST   /api/admin/kill-switch         # tenant-wide
POST   /api/admin/kill-switch/{id}/clear
GET    /api/admin/performance/overview  # anonymized aggregate
GET    /api/admin/users
GET    /api/admin/subscriptions

POST   /api/partner/admin/partners    # admin-only: issue partner API key
POST   /api/partner/{pid}/users
POST   /api/partner/{pid}/trades
GET    /api/partner/{pid}/reports/{user_id}/weekly

GET    /health/core
GET    /health/ai
GET    /disclaimer
```

> Educational use only. Not financial advice.
