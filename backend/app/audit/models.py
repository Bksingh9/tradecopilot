"""AuditEvent — append-only record of every consequential action.

We append rows for: kill-switch set/clear, autonomy upgrade/downgrade, agent
stage transitions, tuning accept/reject, partner trade push, broker order
placed/filled. Rows are NEVER updated or deleted by application code.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class AuditEvent(SQLModel, table=True):
    __tablename__ = "audit_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    actor: str                       # "user" | "admin" | "agent" | "system" | "partner"
    action: str                      # e.g. "kill_switch.set", "agent.execution.placed"
    subject_type: Optional[str] = None  # e.g. "trade", "kill_switch", "tuning_suggestion"
    subject_id: Optional[str] = None
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    at: datetime = Field(default_factory=datetime.utcnow, index=True)
