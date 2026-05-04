"""Centralized settings loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: Literal["dev", "staging", "prod"] = "dev"
    app_name: str = "TradeCopilot"
    log_level: str = "INFO"

    # DB
    database_url: str = "sqlite:///./tradecopilot.db"

    # Auth
    jwt_secret: str = "dev-only-change-me"
    jwt_alg: str = "HS256"
    jwt_ttl_min: int = 60
    secrets_fernet_key: str = ""  # required at runtime when storing broker tokens

    # Indian Stock Market API (0xramm)
    nse_api_base: str = "https://nse-api-khaki.vercel.app"

    # Alpaca
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    alpaca_paper: bool = True
    alpaca_data_base: str = "https://data.alpaca.markets"
    alpaca_trade_base: str = "https://paper-api.alpaca.markets"

    # Zerodha
    zerodha_api_key: str = ""
    zerodha_api_secret: str = ""

    # Upstox
    upstox_client_id: str = ""
    upstox_client_secret: str = ""
    upstox_redirect_uri: str = "http://localhost:8000/api/auth/upstox/callback"

    # Billing
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # AI coach
    ai_coach_backend: Literal["fake", "external"] = "fake"
    ai_external_webhook: str = ""           # legacy webhook (kept for compat)
    ai_service_url: str = ""                # base URL of the LLM service the worker calls
    ai_service_api_key: str = ""            # auth header for ai_service_url
    ai_worker_admin_token: str = ""         # API token the worker uses to call /api/ai/callback

    # Redis / queues
    redis_url: str = "redis://localhost:6379/0"
    ai_queue_name: str = "tradecopilot:ai_jobs"
    ai_worker_heartbeat_key: str = "tradecopilot:ai_worker:heartbeat"
    ai_worker_heartbeat_ttl_s: int = 60

    # Risk hard caps (cannot be overridden by AI suggestions)
    kill_switch_hard_daily_loss_pct: float = 5.0   # absolute ceiling
    kill_switch_hard_max_open_positions: int = 20  # absolute ceiling

    # Partner API
    partner_api_secret: str = ""           # used to sign / hash partner API keys

    # Data cache (parquet)
    data_cache_dir: str = "./data_cache"

    # Local cache for backtests
    backtest_workdir: str = "./backtest_runs"

    # Prediction service
    models_dir: str = "./models"

    # Vector memory backend
    vector_backend: Literal["memory", "pgvector"] = "memory"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
