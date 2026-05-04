"""Auth + broker connection endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from app.auth import service as auth_service
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.brokers import get_client
from app.common.crypto import encrypt
from app.common.exceptions import ValidationError
from app.database import get_session
from app.trading.models import BrokerConnection

router = APIRouter()


# --- Email/password ----------------------------------------------------------
class SignupReq(BaseModel):
    email: EmailStr
    password: str


class LoginReq(BaseModel):
    email: EmailStr
    password: str


class TokenRes(BaseModel):
    access_token: str
    token_type: str = "bearer"


class APITokenRes(BaseModel):
    name: str
    token: str  # plaintext, returned ONCE


@router.post("/signup", response_model=TokenRes)
def signup(req: SignupReq, session: Session = Depends(get_session)) -> TokenRes:
    user = auth_service.signup(session, req.email, req.password)
    return TokenRes(access_token=auth_service.create_access_token(user.id))


@router.post("/login", response_model=TokenRes)
def login(req: LoginReq, session: Session = Depends(get_session)) -> TokenRes:
    user = auth_service.login(session, req.email, req.password)
    return TokenRes(access_token=auth_service.create_access_token(user.id))


class MeRes(BaseModel):
    id: int
    tenant_id: int
    email: str
    role: str
    is_active: bool
    autonomy_mode: str
    paper_qualified_at: Optional[str] = None
    consent_full_auto: bool
    created_at: Optional[str] = None


@router.get("/me", response_model=MeRes)
def me(current: User = Depends(get_current_user)) -> MeRes:
    return MeRes(
        id=current.id,
        tenant_id=current.tenant_id,
        email=current.email,
        role=current.role,
        is_active=current.is_active,
        autonomy_mode=current.autonomy_mode,
        paper_qualified_at=current.paper_qualified_at.isoformat() if current.paper_qualified_at else None,
        consent_full_auto=current.consent_full_auto,
        created_at=current.created_at.isoformat() if current.created_at else None,
    )


@router.post("/api-tokens", response_model=APITokenRes)
def issue_api_token(
    name: str = "default",
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> APITokenRes:
    _, plaintext = auth_service.issue_api_token(session, current, name)
    return APITokenRes(name=name, token=plaintext)


# --- Broker connect ----------------------------------------------------------
class BrokerLoginRes(BaseModel):
    broker: str
    login_url: str


class BrokerCallbackReq(BaseModel):
    broker: str
    code: Optional[str] = None
    request_token: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    is_paper: bool = True


@router.get("/broker/{broker}/login-url", response_model=BrokerLoginRes)
def broker_login_url(
    broker: str,
    current: User = Depends(get_current_user),
) -> BrokerLoginRes:
    client = get_client(broker)
    return BrokerLoginRes(broker=broker, login_url=client.login_url())


@router.post("/broker/connect")
def broker_connect(
    req: BrokerCallbackReq,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    if req.broker == "alpaca":
        if not (req.api_key and req.api_secret):
            raise ValidationError("Alpaca requires api_key + api_secret")
        token = encrypt(f"{req.api_key}:{req.api_secret}")
    else:
        client = get_client(req.broker)
        access_token = client.exchange_code(req.request_token or req.code or "")
        token = encrypt(access_token)

    existing = session.exec(
        select(BrokerConnection).where(
            BrokerConnection.user_id == current.id,
            BrokerConnection.tenant_id == current.tenant_id,
            BrokerConnection.broker == req.broker,
        )
    ).first()
    if existing:
        existing.encrypted_access_token = token
        existing.is_paper = req.is_paper
        session.add(existing)
    else:
        session.add(
            BrokerConnection(
                user_id=current.id,
                tenant_id=current.tenant_id,
                broker=req.broker,
                encrypted_access_token=token,
                is_paper=req.is_paper,
            )
        )
    session.commit()
    return {"broker": req.broker, "connected": True, "is_paper": req.is_paper}


@router.get("/broker/connections")
def list_connections(
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict]:
    rows = session.exec(
        select(BrokerConnection).where(
            BrokerConnection.user_id == current.id,
            BrokerConnection.tenant_id == current.tenant_id,
        )
    ).all()
    return [
        {
            "broker": r.broker,
            "is_paper": r.is_paper,
            "connected_at": r.connected_at.isoformat() if r.connected_at else None,
            "last_sync_at": r.last_sync_at.isoformat() if r.last_sync_at else None,
        }
        for r in rows
    ]
