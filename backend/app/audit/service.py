"""Append-only audit writer. Strictly fire-and-forget on the application path."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlmodel import Session

from app.audit.models import AuditEvent
from app.common.logging import get_logger

logger = get_logger(__name__)


def record(
    session: Session,
    *,
    tenant_id: int,
    actor: str,
    action: str,
    user_id: Optional[int] = None,
    subject_type: Optional[str] = None,
    subject_id: Optional[Any] = None,
    payload: Optional[dict] = None,
) -> AuditEvent:
    """Insert a single AuditEvent. Never logs full payloads (they may contain
    PII). Application code should pass only the minimum useful payload.
    """
    row = AuditEvent(
        tenant_id=tenant_id,
        user_id=user_id,
        actor=actor,
        action=action,
        subject_type=subject_type,
        subject_id=str(subject_id) if subject_id is not None else None,
        payload=_safe_payload(payload or {}),
        at=datetime.utcnow(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    logger.info(
        "audit %s actor=%s tenant=%s user=%s subject=%s/%s",
        action, actor, tenant_id, user_id, subject_type, row.subject_id,
    )
    return row


_DROP_KEYS = {"password", "api_key", "api_secret", "access_token", "fernet_key", "token"}


def _safe_payload(p: dict) -> dict:
    return {k: ("***" if k in _DROP_KEYS else v) for k, v in p.items()}
