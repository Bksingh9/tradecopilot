"""Partner API: per-partner API key auth, scoped to a single tenant.

Authentication: clients send `X-Partner-Key: <plaintext>`. We hash it and look up
the Partner row. The partner_id in the URL must match the row, otherwise 403.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from app.auth import service as auth_service
from app.auth.dependencies import require_admin
from app.auth.models import User
from app.common.exceptions import AuthError, NotFound, PermissionDenied
from app.database import get_session
from app.trading.models import AIReport, Partner, Trade

router = APIRouter()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def _hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def get_current_partner(
    partner_id: int,
    x_partner_key: Optional[str] = Header(default=None),
    session: Session = Depends(get_session),
) -> Partner:
    if not x_partner_key:
        raise AuthError("Missing X-Partner-Key")
    row = session.exec(
        select(Partner).where(
            Partner.api_key_hash == _hash_key(x_partner_key),
            Partner.is_active == True,  # noqa: E712
        )
    ).first()
    if not row or row.id != partner_id:
        raise PermissionDenied("Partner key does not match partner_id")
    return row


# ---------------------------------------------------------------------------
# Admin-only: provision a new partner under a tenant
# ---------------------------------------------------------------------------
class CreatePartnerReq(BaseModel):
    tenant_id: int
    name: str
    scopes: list[str] = []


class CreatePartnerRes(BaseModel):
    partner_id: int
    api_key: str  # plaintext, returned ONCE


@router.post("/admin/partners", response_model=CreatePartnerRes)
def create_partner(
    req: CreatePartnerReq,
    _: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> CreatePartnerRes:
    plaintext = "tcpartner_" + secrets.token_urlsafe(32)
    row = Partner(
        tenant_id=req.tenant_id,
        name=req.name,
        api_key_hash=_hash_key(plaintext),
        scopes=req.scopes,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return CreatePartnerRes(partner_id=row.id, api_key=plaintext)


# ---------------------------------------------------------------------------
# Partner endpoints
# ---------------------------------------------------------------------------
class PartnerCreateUserReq(BaseModel):
    email: EmailStr
    password: str


class PartnerUserRes(BaseModel):
    user_id: int
    email: EmailStr
    tenant_id: int


@router.post("/{partner_id}/users", response_model=PartnerUserRes)
def partner_create_user(
    partner_id: int,
    req: PartnerCreateUserReq,
    partner: Partner = Depends(get_current_partner),
    session: Session = Depends(get_session),
) -> PartnerUserRes:
    user = auth_service.signup(
        session, req.email, req.password, tenant_id=partner.tenant_id, role="user"
    )
    return PartnerUserRes(user_id=user.id, email=user.email, tenant_id=user.tenant_id)


class PartnerTradeReq(BaseModel):
    user_id: int
    broker: str = "external"
    symbol: str
    side: str          # BUY | SELL
    qty: int
    entry_price: float
    exit_price: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    realized_pnl: Optional[float] = None
    r_multiple: Optional[float] = None
    strategy: Optional[str] = None
    status: str = "CLOSED"
    paper: bool = True
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None


@router.post("/{partner_id}/trades", response_model=Trade)
def partner_push_trade(
    partner_id: int,
    req: PartnerTradeReq,
    partner: Partner = Depends(get_current_partner),
    session: Session = Depends(get_session),
) -> Trade:
    user = session.get(User, req.user_id)
    if not user or user.tenant_id != partner.tenant_id:
        raise PermissionDenied("user does not belong to this partner's tenant")
    t = Trade(
        user_id=req.user_id,
        tenant_id=partner.tenant_id,
        broker=req.broker,
        symbol=req.symbol,
        side=req.side,
        qty=req.qty,
        entry_price=req.entry_price,
        exit_price=req.exit_price,
        stop_price=req.stop_price,
        target_price=req.target_price,
        realized_pnl=req.realized_pnl,
        r_multiple=req.r_multiple,
        strategy=req.strategy,
        status=req.status,
        paper=req.paper,
        opened_at=req.opened_at or datetime.utcnow(),
        closed_at=req.closed_at,
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


class PartnerWeeklyReportRes(BaseModel):
    user_id: int
    period_start: datetime
    period_end: datetime
    content: str


@router.get("/{partner_id}/reports/{user_id}/weekly", response_model=PartnerWeeklyReportRes)
def partner_get_weekly(
    partner_id: int,
    user_id: int,
    partner: Partner = Depends(get_current_partner),
    session: Session = Depends(get_session),
) -> PartnerWeeklyReportRes:
    user = session.get(User, user_id)
    if not user or user.tenant_id != partner.tenant_id:
        raise PermissionDenied("user does not belong to this partner's tenant")
    # Generate fresh on demand using the configured coach.
    from app.ai.coach import get_coach
    from app.journal import journal_service as js
    from app.trading.models import RiskRule

    end = datetime.utcnow()
    start = end - timedelta(days=7)
    trades = js.list_trades(session, user_id, start=start, end=end, limit=10_000)
    journal = js.list_entries(session, user_id, start=start, end=end, limit=10_000)
    rule = session.get(RiskRule, user_id) or RiskRule(user_id=user_id, tenant_id=user.tenant_id)
    content = get_coach().generate_weekly_report(trades, journal, rule)

    row = AIReport(
        user_id=user_id, tenant_id=user.tenant_id, kind="weekly",
        period_start=start, period_end=end, content=content,
    )
    session.add(row)
    session.commit()
    return PartnerWeeklyReportRes(
        user_id=user_id, period_start=start, period_end=end, content=content
    )
