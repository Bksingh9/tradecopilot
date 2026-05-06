FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

EXPOSE 8000
# Bind IPv6 dual-stack (covers IPv4 too on Linux) and honour $PORT when set.
# Required for Railway (IPv6-only internal proxy); transparent on Render/Fly/local.
# Shell form is intentional so $PORT expands at start.
CMD sh -c "uvicorn app.main:app --host :: --port ${PORT:-8000}"
