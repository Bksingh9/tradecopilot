FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

EXPOSE 8000
# Bind IPv6 dual-stack (covers IPv4 too on Linux); required by Railway's
# IPv6-only internal proxy. Port is hardcoded to 8000 because Render's
# healthcheck URL is fixed to :8000 — letting it expand from $PORT (which
# Render dynamically sets to 10000) deadlocks the healthcheck. Railway
# overrides this CMD via its own Custom Start Command in service settings.
CMD ["uvicorn", "app.main:app", "--host", "::", "--port", "8000"]
