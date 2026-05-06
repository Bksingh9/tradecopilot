# Railway-specific API Dockerfile.
#
# Why this file exists: Railway's `RAILWAY_DOCKERFILE_PATH` setting only changes
# which Dockerfile is used — it does NOT change the build context, which always
# stays at the repo root. So the canonical `backend/Dockerfile` (which assumes
# context=backend/) fails on Railway with `COPY requirements.txt: not found`.
#
# This file mirrors backend/Dockerfile but uses repo-root-relative paths.
# Other deploy targets (docker-compose, Render, Fly, DO, AWS) continue to use
# backend/Dockerfile unchanged.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .

EXPOSE 8000
# Bind IPv6 dual-stack (Railway's internal proxy is IPv6-only). Shell form so
# $PORT expands at runtime when Railway provides it.
CMD sh -c "uvicorn app.main:app --host :: --port ${PORT:-8000}"
