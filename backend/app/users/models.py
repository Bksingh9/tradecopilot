"""User-scoped preferences (watchlist, default broker, base currency, etc.)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class UserPreferences(SQLModel, table=True):
    __tablename__ = "user_preferences"

    user_id: int = Field(foreign_key="users.id", primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    base_currency: str = "INR"
    default_broker: Optional[str] = None  # zerodha | upstox | alpaca
    watchlist: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    timezone: str = "Asia/Kolkata"
    updated_at: datetime = Field(default_factory=datetime.utcnow)
