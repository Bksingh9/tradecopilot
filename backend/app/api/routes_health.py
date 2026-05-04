"""Health endpoints.

- GET /health/core: DB connectable + config loaded. If this fails, the API is down.
- GET /health/ai:   Redis reachable + worker heartbeat fresh. If this is "degraded",
                    synchronous endpoints still work (FakeCoach fallback) but live
                    LLM coaching is offline.
"""
from __future__ import annotations

import time

from fastapi import APIRouter

from app.config import settings
from app.database import db_ping

router = APIRouter()


@router.get("/core")
def health_core() -> dict:
    db_ok = db_ping()
    return {
        "ok": db_ok,
        "db": "ok" if db_ok else "down",
        "env": settings.app_env,
        "app": settings.app_name,
    }


@router.get("/ai")
def health_ai() -> dict:
    """Reports degraded (200) when Redis is up but no worker heartbeat,
    and unreachable (200) when Redis itself is down. /core is the gate."""
    redis_ok = False
    worker_fresh = False
    last_seen: int | None = None
    try:
        import redis as _redis

        r = _redis.Redis.from_url(settings.redis_url, decode_responses=True)
        r.ping()
        redis_ok = True
        ts = r.get(settings.ai_worker_heartbeat_key)
        if ts is not None:
            last_seen = int(ts)
            worker_fresh = (int(time.time()) - last_seen) <= settings.ai_worker_heartbeat_ttl_s
    except Exception:
        redis_ok = False

    if not redis_ok:
        status = "redis_unreachable"
    elif not worker_fresh:
        status = "worker_stale"
    else:
        status = "ok"

    return {
        "status": status,
        "redis_ok": redis_ok,
        "worker_fresh": worker_fresh,
        "last_seen": last_seen,
    }
