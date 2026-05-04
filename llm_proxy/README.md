# TradeCopilot LLM Proxy

A reference HTTP service that the TradeCopilot AI worker can point at. Accepts
`{system, user}` and returns `{text, backend}`.

> Educational use only. Not financial advice.

## Backends (auto-selected by env)

| Env set                 | Backend     |
|-------------------------|-------------|
| `ANTHROPIC_API_KEY`     | Claude Messages API |
| `OPENAI_API_KEY` (only) | OpenAI chat.completions |
| neither                 | deterministic echo (great for CI / dev) |

## Run

```bash
cd llm_proxy
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 7000
# or:
docker build -t tc-llm-proxy . && docker run --rm -p 7000:7000 \
  -e ANTHROPIC_API_KEY=sk-ant-... tc-llm-proxy
```

## Wire to the backend

```
# in backend/.env
AI_COACH_BACKEND=external
AI_SERVICE_URL=http://localhost:7000/
AI_SERVICE_API_KEY=any-shared-secret      # forwarded as Bearer
AI_WORKER_ADMIN_TOKEN=tc_...              # an admin user's API token
```

If you set `PROXY_SHARED_SECRET=any-shared-secret` on the proxy, it will
require that exact Bearer token from the worker.

## Test it

```bash
curl -s -X POST http://localhost:7000/ \
  -H 'Content-Type: application/json' \
  -d '{"system":"You are a calm trading coach.","user":"Tell me my last week was meh."}'
# → {"text":"...", "backend":"anthropic|openai|echo"}

curl -s http://localhost:7000/healthz
```
