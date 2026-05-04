"""Audit endpoints — user-scoped self view and admin-wide query."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.audit.models import AuditEvent
from app.auth.dependencies import get_current_user, require_admin
from app.auth.models import User
from app.database import get_session

router = APIRouter()


@router.get("/me", response_model=list[AuditEvent])
def my_audit(
    since: Optional[datetime] = None,
    limit: int = Query(100, le=500),
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[AuditEvent]:
    q = select(AuditEvent).where(
        AuditEvent.user_id == current.id,
        AuditEvent.tenant_id == current.tenant_id,
    )
    if since:
        q = q.where(AuditEvent.at >= since)
    q = q.order_by(AuditEvent.at.desc()).limit(limit)
    return list(session.exec(q).all())


@router.get("/admin", response_model=list[AuditEvent])
def admin_audit(
    user_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
    action: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = Query(200, le=2000),
    _: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> list[AuditEvent]:
    q = select(AuditEvent)
    if user_id is not None:
        q = q.where(AuditEvent.user_id == user_id)
    if tenant_id is not None:
        q = q.where(AuditEvent.tenant_id == tenant_id)
    if action:
        q = q.where(AuditEvent.action == action)
    if since:
        q = q.where(AuditEvent.at >= since)
    q = q.order_by(AuditEvent.at.desc()).limit(limit)
    return list(session.exec(q).all())
