FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

EXPOSE 8000
# Bind IPv4 (0.0.0.0) — Render's port-detection sniffer doesn't reliably
# discover IPv6-bound services and times out the deploy at the healthcheck
# stage even when /health/core responds. Railway needs IPv6 (`::`) instead;
# the Railway service has a Custom Start Command override configured in
# Railway's dashboard that uses `--host ::`. So this Dockerfile CMD is
# Render/local/compose-friendly; Railway-friendly via service-level override.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
