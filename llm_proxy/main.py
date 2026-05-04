"""Reference LLM proxy for the TradeCopilot AI worker.

The TradeCopilot backend pushes rendered prompts to a Redis queue. The AI worker
drains that queue and POSTs each job to `AI_SERVICE_URL`. This service is a
*reference implementation* of `AI_SERVICE_URL`: it accepts `{system, user}`
and returns `{text}`. Behavior depends on env:

    ANTHROPIC_API_KEY set    →  forwards to Claude Messages API
    OPENAI_API_KEY    set    →  forwards to OpenAI chat.completions
    neither set              →  returns deterministic echo (good for CI / dev)

Run locally:
    pip install -r requirements.txt
    uvicorn main:app --host 0.0.0.0 --port 7000

Then in the backend:
    AI_COACH_BACKEND=external
    AI_SERVICE_URL=http://localhost:7000/
    AI_SERVICE_API_KEY=any-shared-secret
    AI_WORKER_ADMIN_TOKEN=tc_...        # an admin user's API token
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
log = logging.getLogger("llm_proxy")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_MAX_TOKENS = int(os.environ.get("ANTHROPIC_MAX_TOKENS", "1024"))
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
SHARED_SECRET = os.environ.get("PROXY_SHARED_SECRET", "")     # optional Bearer

app = FastAPI(title="TradeCopilot LLM Proxy", version="0.1.0")


class CallReq(BaseModel):
    system: str = Field("", description="system prompt")
    user: str = Field(..., description="user prompt (rendered template)")
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None


class CallRes(BaseModel):
    text: str
    backend: str


def _check_secret(authorization: Optional[str]) -> None:
    if not SHARED_SECRET:
        return
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer")
    if authorization.split(None, 1)[1] != SHARED_SECRET:
        raise HTTPException(403, "bad token")


# ---- Backends ------------------------------------------------------------
def _echo(req: CallReq) -> str:
    return (
        "(echo backend — set ANTHROPIC_API_KEY or OPENAI_API_KEY to use a real LLM)\n"
        f"SYSTEM:\n{req.system[:200]}\n\nUSER:\n{req.user[:600]}"
    )


def _claude(req: CallReq) -> str:
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": req.max_tokens or ANTHROPIC_MAX_TOKENS,
        "system": req.system,
        "messages": [{"role": "user", "content": req.user}],
    }
    if req.temperature is not None:
        body["temperature"] = req.temperature
    with httpx.Client(timeout=httpx.Timeout(120.0)) as c:
        r = c.post("https://api.anthropic.com/v1/messages", json=body, headers=headers)
    r.raise_for_status()
    data = r.json()
    blocks = data.get("content") or []
    parts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
    return "\n".join(parts).strip() or "(empty response from Claude)"


def _openai(req: CallReq) -> str:
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": req.system or ""},
            {"role": "user", "content": req.user},
        ],
        "max_tokens": req.max_tokens or 1024,
    }
    if req.temperature is not None:
        body["temperature"] = req.temperature
    with httpx.Client(timeout=httpx.Timeout(120.0)) as c:
        r = c.post("https://api.openai.com/v1/chat/completions", json=body, headers=headers)
    r.raise_for_status()
    data = r.json()
    choices = data.get("choices", [])
    if not choices:
        return "(empty response from OpenAI)"
    return choices[0].get("message", {}).get("content", "") or ""


# ---- API -----------------------------------------------------------------
@app.get("/healthz")
def healthz() -> dict:
    return {
        "ok": True,
        "backend": _backend_name(),
        "model": ANTHROPIC_MODEL if ANTHROPIC_API_KEY else (OPENAI_MODEL if OPENAI_API_KEY else "echo"),
    }


@app.post("/", response_model=CallRes)
def call(
    req: CallReq,
    authorization: Optional[str] = Header(default=None),
) -> CallRes:
    _check_secret(authorization)
    backend = _backend_name()
    try:
        if backend == "anthropic":
            text = _claude(req)
        elif backend == "openai":
            text = _openai(req)
        else:
            text = _echo(req)
    except httpx.HTTPStatusError as e:
        log.warning("upstream %s error: %s", backend, e.response.status_code)
        raise HTTPException(502, f"upstream {backend} error: {e.response.status_code}")
    except Exception as e:
        log.exception("call failed: %s", e)
        raise HTTPException(500, f"proxy error: {e}")
    return CallRes(text=text, backend=backend)


def _backend_name() -> str:
    if ANTHROPIC_API_KEY:
        return "anthropic"
    if OPENAI_API_KEY:
        return "openai"
    return "echo"
