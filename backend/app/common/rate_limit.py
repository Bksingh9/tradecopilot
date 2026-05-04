"""Token-bucket rate limit middleware.

- Uses Redis when configured (multi-process safe via INCR + EXPIRE).
- Falls back to a process-local dict (safe for single-process dev).
- Bucket key: client identifier (X-API-Token, partner key, or remote addr).
- Default: 120 requests / minute. Tunable via env (RATE_LIMIT_*).

Skips: /health/*, /disclaimer, /docs, /openapi.json.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.common.logging import get_logger
from app.config import settings

logger = get_logger(__name__)

_DEFAULT_LIMIT = 120
_DEFAULT_WINDOW_S = 60

_SKIP_PATH_PREFIXES = ("/health", "/disclaimer", "/docs", "/openapi.json", "/redoc")


class _LocalCounter:
    def __init__(self) -> None:
        self.lock = Lock()
        self.events: dict[str, deque] = defaultdict(deque)

    def hit(self, key: str, limit: int, window_s: int) -> tuple[bool, int]:
        now = time.time()
        with self.lock:
            q = self.events[key]
            while q and now - q[0] > window_s:
                q.popleft()
            if len(q) >= limit:
                return False, len(q)
            q.append(now)
            return True, len(q)


_local = _LocalCounter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, limit: int = _DEFAULT_LIMIT, window_s: int = _DEFAULT_WINDOW_S) -> None:
        super().__init__(app)
        self.limit = limit
        self.window_s = window_s
        self._redis = None
        self._tried_redis = False

    def _redis_client(self):
        if self._tried_redis:
            return self._redis
        self._tried_redis = True
        try:
            import redis as _r
            client = _r.Redis.from_url(settings.redis_url, decode_responses=True)
            client.ping()
            self._redis = client
        except Exception as e:
            logger.info("rate_limit: redis unavailable, falling back to local (%s)", e)
            self._redis = None
        return self._redis

    def _client_key(self, request: Request) -> str:
        if (h := request.headers.get("x-partner-key")):
            return f"partner:{h[:10]}"
        if (h := request.headers.get("x-api-token")):
            return f"apitoken:{h[:10]}"
        if (h := request.headers.get("authorization")):
            return f"jwt:{h[-12:]}"
        host = request.client.host if request.client else "unknown"
        return f"ip:{host}"

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(p) for p in _SKIP_PATH_PREFIXES):
            return await call_next(request)

        key = self._client_key(request)
        allowed, count = self._allow(key)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": {"code": "rate_limited",
                                   "message": f"limit {self.limit}/{self.window_s}s exceeded"}},
                headers={"Retry-After": str(self.window_s)},
            )
        return await call_next(request)

    def _allow(self, key: str) -> tuple[bool, int]:
        client = self._redis_client()
        if client is None:
            return _local.hit(key, self.limit, self.window_s)
        try:
            redis_key = f"rl:{key}"
            n = client.incr(redis_key)
            if n == 1:
                client.expire(redis_key, self.window_s)
            return (n <= self.limit, int(n))
        except Exception as e:
            logger.warning("rate_limit redis error: %s — using local", e)
            return _local.hit(key, self.limit, self.window_s)
