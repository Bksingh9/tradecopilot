"""Persisted models for trades, positions, journal, risk rules, broker connections,
kill switches, AI tuning suggestions, backtests, and partner integrations.

Multi-tenant: every row carries `tenant_id` (in addition to `user_id` where the row
is user-owned) so admin/partner queries can scope by tenant.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


# --- Risk ---------------------------------------------------------------------
class RiskRule(SQLModel, table=True):
    """One row per user holding their risk profile."""

    __tablename__ = "risk_rules"

    user_id: int = Field(foreign_key="users.id", primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    max_risk_per_trade_pct: float = 1.0   # % of equity at risk per trade
    daily_loss_limit_pct: float = 3.0     # % of equity / day
    max_open_positions: int = 5
    restricted_symbols: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    paper_only: bool = True
    starting_equity: float = 100000.0
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# --- Strategy config ----------------------------------------------------------
class StrategyConfig(SQLModel, table=True):
    __tablename__ = "strategy_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    strategy_name: str           # "momentum" | "mean_reversion" | "orb"
    params: dict = Field(default_factory=dict, sa_column=Column(JSON))
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- Broker connection (encrypted access token at rest) -----------------------
class BrokerConnection(SQLModel, table=True):
    __tablename__ = "broker_connections"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    broker: str                  # "zerodha" | "upstox" | "alpaca"
    encrypted_access_token: Optional[str] = None
    is_paper: bool = True
    last_sync_at: Optional[datetime] = None
    connected_at: datetime = Field(default_factory=datetime.utcnow)


# --- Trades / positions -------------------------------------------------------
class Trade(SQLModel, table=True):
    __tablename__ = "trades"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    broker: str
    symbol: str
    exchange: Optional[str] = None
    side: str                    # BUY | SELL
    qty: int
    entry_price: float
    exit_price: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    realized_pnl: Optional[float] = None
    r_multiple: Optional[float] = None
    strategy: Optional[str] = None
    status: str = "OPEN"         # OPEN | CLOSED | CANCELLED
    paper: bool = True
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None


class Position(SQLModel, table=True):
    __tablename__ = "positions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    broker: str
    symbol: str
    exchange: Optional[str] = None
    qty: int
    avg_price: float
    last_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# --- Journal ------------------------------------------------------------------
class JournalEntry(SQLModel, table=True):
    __tablename__ = "journal_entries"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    trade_id: Optional[int] = Field(default=None, foreign_key="trades.id")
    setup: Optional[str] = None
    emotion_tag: Optional[str] = None
    screenshot_url: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- AI report cache ----------------------------------------------------------
class AIReport(SQLModel, table=True):
    __tablename__ = "ai_reports"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    kind: str                  # "weekly" | "trade_comment" | "tuning_review"
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- Kill switch (user or tenant-wide) ---------------------------------------
class KillSwitch(SQLModel, table=True):
    """When `active=True` and `user_id` matches (or scope='tenant'), execution.execute_order
    short-circuits with a RiskRuleViolation. Writes are append-only; we mark inactive on clear.
    """

    __tablename__ = "kill_switches"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    scope: str = "user"          # "user" | "tenant"
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    reason: str
    set_by: str = "user"         # "user" | "admin" | "system"
    active: bool = True
    cleared_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- Strategy tuning suggestions (AI-proposed parameter tweaks) --------------
class StrategyTuningSuggestion(SQLModel, table=True):
    """AI may insert *pending* rows. They become effective only after the user
    or an admin POSTs to /api/trading/tuning/{id}/accept. AI can never directly
    activate a suggestion.
    """

    __tablename__ = "strategy_tuning_suggestions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    strategy: str
    current_params: dict = Field(default_factory=dict, sa_column=Column(JSON))
    suggested_params: dict = Field(default_factory=dict, sa_column=Column(JSON))
    rationale: str
    status: str = "pending"      # pending | accepted | rejected | expired
    reviewed_by: Optional[int] = Field(default=None, foreign_key="users.id")
    reviewed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- Backtest runs (walk-forward + ad-hoc) -----------------------------------
class BacktestRun(SQLModel, table=True):
    __tablename__ = "backtest_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    strategy: str
    config_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    metrics_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = "queued"       # queued | running | done | failed
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None


# --- Partner integrations -----------------------------------------------------
class Partner(SQLModel, table=True):
    """A Partner is a 3rd-party integrator that operates on top of TradeCopilot
    for one tenant (their own customer base). API keys are hashed at rest.
    """

    __tablename__ = "partners"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    name: str = Field(index=True)
    api_key_hash: str = Field(index=True, unique=True)
    scopes: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
