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
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
