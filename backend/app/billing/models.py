"""Subscription models — kept minimal as a stub for billing integration."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Subscription(SQLModel, table=True):
    __tablename__ = "subscriptions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    plan: str = "free"          # free | pro | team
    status: str = "active"      # active | past_due | canceled
    provider: str = "stripe"    # stripe | razorpay | none
    provider_customer_id: Optional[str] = None
    provider_subscription_id: Optional[str] = None
    current_period_end: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
