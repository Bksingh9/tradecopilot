"""User preferences CRUD (tenant-scoped)."""
from __future__ import annotations

from sqlmodel import Session

from app.auth.models import User
from app.users.models import UserPreferences


def get_or_create_prefs(session: Session, user: User) -> UserPreferences:
    prefs = session.get(UserPreferences, user.id)
    if not prefs:
        prefs = UserPreferences(user_id=user.id, tenant_id=user.tenant_id)
        session.add(prefs)
        session.commit()
        session.refresh(prefs)
    return prefs


def update_prefs(session: Session, user: User, **fields) -> UserPreferences:
    prefs = get_or_create_prefs(session, user)
    for k, v in fields.items():
        if hasattr(prefs, k) and v is not None:
            setattr(prefs, k, v)
    session.add(prefs)
    session.commit()
    session.refresh(prefs)
    return prefs
