.PHONY: dev dev-backend worker test up down migrate revision lint fmt clean

PY ?= python
UVICORN_OPTS ?= --reload --host 0.0.0.0 --port 8000

dev: dev-backend       ## Run API locally (worker is started separately)

dev-backend:
	$(PY) -m uvicorn app.main:app $(UVICORN_OPTS)

worker:
	$(PY) -m app.workers.ai_worker

test:
	$(PY) -m pytest

up:
	docker-compose -f ../docker-compose.yml up --build

down:
	docker-compose -f ../docker-compose.yml down

migrate:
	alembic upgrade head

revision:
	alembic revision --autogenerate -m "$(msg)"

clean:
	rm -rf .pytest_cache __pycache__ */__pycache__ */*/__pycache__ tradecopilot.db data_cache backtest_runs
