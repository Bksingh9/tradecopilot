"""Standalone AI worker.

Drains a Redis list (`AI_QUEUE_NAME`) of rendered prompts. For each job:
  1. POST to the configured `AI_SERVICE_URL` (Bearer auth from `AI_SERVICE_API_KEY`)
     with `{system, user}`. The service is whatever you wired Claude/OpenAI/etc up to.
  2. Take the response text and POST it to the local API `/api/ai/callback`
     using the admin JWT/API token in `AI_WORKER_ADMIN_TOKEN`.
  3. Heartbeat every loop tick into `AI_WORKER_HEARTBEAT_KEY` with a TTL so
     `/health/ai` can report worker freshness.

The worker is intentionally separate from the API process: if it dies, dashboards,
journaling, risk checks, and synchronous endpoints (FakeCoach fallback) all keep
working. Run with `python -m app.workers.ai_worker`.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import time
from typing import Any, Optional

import httpx

from app.common.logging import configure_logging, get_logger
from app.config import settings

configure_logging()
logger = get_logger("ai_worker")

# graceful shutdown
_running = True


def _handle_signal(_sig, _frame) -> None:
    global _running
    logger.info("ai_worker shutdown signal received")
    _running = False


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


def _redis():
    import redis as _r
    return _r.Redis.from_url(settings.redis_url, decode_responses=True)


def _heartbeat(r) -> None:
    try:
        r.set(
            settings.ai_worker_heartbeat_key,
            str(int(time.time())),
            ex=settings.ai_worker_heartbeat_ttl_s,
        )
    except Exception as e:
        logger.warning("heartbeat failed: %s", e)


def _call_ai_service(system: str, user: str) -> Optional[str]:
    if not settings.ai_service_url:
        logger.warning("AI_SERVICE_URL not configured — returning placeholder")
        return "(placeholder — configure AI_SERVICE_URL)"
    headers = {"Content-Type": "application/json"}
    if settings.ai_service_api_key:
        headers["Authorization"] = f"Bearer {settings.ai_service_api_key}"
    try:
        with httpx.Client(timeout=httpx.Timeout(60.0)) as c:
            r = c.post(
                settings.ai_service_url,
                json={"system": system, "user": user},
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()
        # Allow either {"text": "..."} or a raw string.
        if isinstance(data, str):
            return data
        return data.get("text") or data.get("content") or json.dumps(data)
    except Exception as e:
        logger.warning("ai service call failed: %s", e)
        return None


def _post_callback(payload: dict[str, Any]) -> None:
    if not settings.ai_worker_admin_token:
        logger.warning("AI_WORKER_ADMIN_TOKEN not set — skipping callback")
        return
    base = os.environ.get("API_BASE_URL", "http://localhost:8000")
    url = f"{base.rstrip('/')}/api/ai/callback"
    headers = {"X-API-Token": settings.ai_worker_admin_token}
    try:
        with httpx.Client(timeout=httpx.Timeout(10.0)) as c:
            r = c.post(url, json=payload, headers=headers)
            r.raise_for_status()
    except Exception as e:
        logger.warning("callback POST failed: %s", e)


def _process(job: dict) -> None:
    kind = job.get("kind", "weekly")
    system = job.get("system", "")
    user = job.get("user", "")
    text = _call_ai_service(system, user) or "(no response from AI service)"

    payload = {
        "user_id": job.get("user_id"),
        "tenant_id": job.get("tenant_id"),
        "kind": kind,
        "content": text,
    }

    if kind == "tuning_review":
        # Try to parse JSON from the model's output; tolerate noise.
        suggested_params: dict = {}
        rationale: str = text[:1000]
        try:
            data = json.loads(text)
            suggested_params = data.get("suggested_params", {}) or {}
            rationale = data.get("rationale", rationale)
        except Exception:
            pass
        payload["suggested_params"] = suggested_params
        payload["rationale"] = rationale
        payload["suggestion_id"] = job.get("suggestion_id")

    _post_callback(payload)


def main() -> None:
    logger.info("ai_worker starting; queue=%s", settings.ai_queue_name)
    r = _redis()
    while _running:
        _heartbeat(r)
        try:
            popped = r.brpop(settings.ai_queue_name, timeout=5)
        except Exception as e:
            logger.warning("brpop failed: %s — sleeping", e)
            time.sleep(2)
            continue
        if not popped:
            continue
        _, raw = popped
        try:
            job = json.loads(raw)
        except Exception:
            logger.warning("bad payload, dropping: %s", str(raw)[:200])
            continue
        try:
            _process(job)
        except Exception as e:
            logger.exception("job failed: %s", e)


if __name__ == "__main__":  # pragma: no cover
    main()
