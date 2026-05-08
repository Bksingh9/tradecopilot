"""Broker connection management.

Out-of-scope here: full OAuth dance per broker (Kite Connect / Upstox v2 each
have a redirect-and-callback flow that needs frontend coordination).

In-scope: a manual-paste flow that lets a user wire their own access_token
without us hosting a redirect callback. This unlocks the live (non-paper)
trading path on Render free tier where we can't run an OAuth callback URL
reliably anyway. The full OAuth flow can layer on top by calling the same
underlying `_save_connection` helper.

Endpoints:
    GET    /api/brokers/list                 — list this user's connections
    POST   /api/brokers/connect              — { broker, access_token, is_paper? }
    DELETE /api/brokers/disconnect/{broker}  — soft-delete by broker name
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.audit import service as audit
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.common.crypto import encrypt
from app.common.exceptions import NotFound, PermissionDenied
from app.database import get_session
from app.trading.models import BrokerConnection

router = APIRouter()

_SUPPORTED = {"zerodha", "upstox", "alpaca"}


class BrokerListItem(BaseModel):
    broker: str
    is_paper: bool
    connected_at: datetime
    last_sync_at: Optional[datetime] = None
    has_token: bool


class ConnectReq(BaseModel):
    broker: str = Field(..., description="zerodha | upstox | alpaca")
    access_token: Optional[str] = Field(
        None,
        description=(
            "Broker-issued access token. For Kite Connect, the value the user "
            "obtains after login. For Alpaca, the API secret. Optional when "
            "is_paper=True (paper-only connection record)."
        ),
    )
    is_paper: bool = True


@router.get("/list", response_model=list[BrokerListItem])
def list_brokers(
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[BrokerListItem]:
    rows = session.exec(
        select(BrokerConnection).where(
            BrokerConnection.user_id == current.id,
            BrokerConnection.tenant_id == current.tenant_id,
        )
    ).all()
    return [
        BrokerListItem(
            broker=r.broker,
            is_paper=bool(r.is_paper),
            connected_at=r.connected_at,
            last_sync_at=r.last_sync_at,
            has_token=bool(r.encrypted_access_token),
        )
        for r in rows
    ]


@router.post("/connect")
def connect_broker(
    req: ConnectReq,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Create or update a broker connection. Token is encrypted at rest."""
    broker = req.broker.lower().strip()
    if broker not in _SUPPORTED:
        raise PermissionDenied(f"unsupported broker: {req.broker}")

    if not req.is_paper and not req.access_token:
        raise PermissionDenied("access_token required for non-paper broker connection")

    existing = session.exec(
        select(BrokerConnection).where(
            BrokerConnection.user_id == current.id,
            BrokerConnection.tenant_id == current.tenant_id,
            BrokerConnection.broker == broker,
        )
    ).first()

    encrypted_token = encrypt(req.access_token) if req.access_token else None

    if existing:
        existing.encrypted_access_token = encrypted_token
        existing.is_paper = req.is_paper
        existing.last_sync_at = datetime.utcnow()
        session.add(existing)
        action = "broker.connect.updated"
        row = existing
    else:
        row = BrokerConnection(
            user_id=current.id,
            tenant_id=current.tenant_id,
            broker=broker,
            encrypted_access_token=encrypted_token,
            is_paper=req.is_paper,
            last_sync_at=datetime.utcnow(),
        )
        session.add(row)
        action = "broker.connect.created"

    session.commit()
    session.refresh(row)

    audit.record(
        session,
        tenant_id=current.tenant_id,
        user_id=current.id,
        actor="user",
        action=action,
        subject_type="broker_connection",
        subject_id=row.id,
        payload={"broker": broker, "is_paper": req.is_paper, "has_token": bool(encrypted_token)},
    )

    return {
        "id": row.id,
        "broker": row.broker,
        "is_paper": bool(row.is_paper),
        "connected_at": row.connected_at.isoformat(),
        "last_sync_at": row.last_sync_at.isoformat() if row.last_sync_at else None,
        "has_token": bool(row.encrypted_access_token),
    }


@router.delete("/disconnect/{broker}")
def disconnect_broker(
    broker: str,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    broker = broker.lower().strip()
    row = session.exec(
        select(BrokerConnection).where(
            BrokerConnection.user_id == current.id,
            BrokerConnection.tenant_id == current.tenant_id,
            BrokerConnection.broker == broker,
        )
    ).first()
    if not row:
        raise NotFound(f"no {broker} connection for this user")

    session.delete(row)
    session.commit()

    audit.record(
        session,
        tenant_id=current.tenant_id,
        user_id=current.id,
        actor="user",
        action="broker.disconnect",
        subject_type="broker_connection",
        subject_id=row.id,
        payload={"broker": broker},
    )

    return {"ok": True, "broker": broker}
