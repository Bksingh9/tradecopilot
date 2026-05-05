"""FastAPI app entrypoint."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    routes_admin,
    routes_agents,
    routes_ai,
    routes_audit,
    routes_auth,
    routes_backtest,
    routes_health,
    routes_journal,
    routes_partner,
    routes_predict,
    routes_trading,
    routes_users,
)
from app.common.exceptions import TradeCopilotError
from app.common.logging import configure_logging, get_logger
from app.common.rate_limit import RateLimitMiddleware
from app.config import settings
from app.database import init_db
from app.scheduler import get_scheduler, shutdown_scheduler

configure_logging()
logger = get_logger(__name__)


DISCLAIMER = (
    "TradeCopilot Agent is an educational and decision-support tool only. "
    "It does NOT provide guaranteed or assured returns. "
    "All trading involves risk of loss; you alone are responsible for your decisions. "
    "Past performance and backtest results are not indicative of future results. "
    "Always test in paper trading before going live. "
    "We focus on risk-managed, process-focused, data-driven workflows."
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    get_scheduler()
    logger.info("startup app=%s env=%s", settings.app_name, settings.app_env)
    try:
        yield
    finally:
        shutdown_scheduler()
        logger.info("shutdown app=%s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version="0.3.0",
    lifespan=lifespan,
    description=DISCLAIMER,
)

# Middleware: CORS (frontend may be served from a different origin in prod).
# Provide a comma-separated allow-list via CORS_ALLOW_ORIGINS env var; falls back
# to the canonical Render frontend + localhost dev ports.
_cors_default = "https://tradecopilot-web.onrender.com,http://localhost:5173,http://localhost:4173,http://localhost"
_cors_origins = [
    o.strip() for o in os.environ.get("CORS_ALLOW_ORIGINS", _cors_default).split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Token", "X-Partner-Key"],
    max_age=600,
)

# Middleware: rate limiting (Redis-backed if available, else in-process).
app.add_middleware(RateLimitMiddleware)


@app.exception_handler(TradeCopilotError)
async def trade_copilot_error_handler(_: Request, exc: TradeCopilotError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={"error": {"code": exc.code, "message": str(exc)}},
    )


# --- Routes -------------------------------------------------------------------
app.include_router(routes_auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(routes_users.router, prefix="/api/users", tags=["users"])
app.include_router(routes_trading.router, prefix="/api/trading", tags=["trading"])
app.include_router(routes_journal.router, prefix="/api/journal", tags=["journal"])
app.include_router(routes_ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(routes_agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(routes_audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(routes_admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(routes_backtest.router, prefix="/api/backtest", tags=["backtest"])
app.include_router(routes_predict.router, prefix="/api/predict", tags=["predict"])
app.include_router(routes_partner.router, prefix="/api/partner", tags=["partner"])
app.include_router(routes_health.router, prefix="/health", tags=["health"])


@app.get("/health", tags=["meta"])
def health_legacy() -> dict:
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


@app.get("/disclaimer", tags=["meta"])
def disclaimer() -> dict:
    return {"disclaimer": DISCLAIMER}
