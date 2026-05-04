"""DB models for tenants, users, and per-user API tokens.

Multi-tenant: a Tenant owns Users; every user-scoped row carries `tenant_id`.
RBAC: `User.role` is "user" or "admin".
Autonomy: per-user mode controls whether the agent runs in advisory / semi-auto / full-auto.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Tenant(SQLModel, table=True):
    __tablename__ = "tenants"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    plan: str = "free"            # free | pro | team
    created_at: datetime = Field(default_factory=datetime.utcnow)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    is_active: bool = True
    role: str = "user"            # "user" | "admin"
    api_token_hash: Optional[str] = Field(default=None, index=True)

    # Autonomy
    autonomy_mode: str = "advisory"     # "advisory" | "semi_auto" | "full_auto"
    paper_qualified_at: Optional[datetime] = None
    consent_full_auto: bool = False

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserAPIToken(SQLModel, table=True):
    """One row per long-lived API token. Token plaintext is shown only once."""

    __tablename__ = "user_api_tokens"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    name: str
    token_hash: str = Field(index=True, unique=True)
    last_used_at: Optional[datetime] = None
    revoked: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
