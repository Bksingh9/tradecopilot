"""Admin endpoints — plan management, kill switch (tenant-wide), aggregate metrics."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.dependencies import require_admin
from app.auth.models import User
from app.billing.models import Subscription
from app.database import get_session
from app.journal import analytics
from app.trading import risk as risk_mod
from app.trading.models import KillSwitch

router = APIRouter()


@router.get("/users", response_model=list[User])
def list_users(_: User = Depends(require_admin), session: Session = Depends(get_session)) -> list[User]:
    return list(session.exec(select(User)).all())


@router.get("/subscriptions", response_model=list[Subscription])
def list_subscriptions(_: User = Depends(require_admin), session: Session = Depends(get_session)) -> list[Subscription]:
    return list(session.exec(select(Subscription)).all())


@router.post("/users/{user_id}/disable")
def disable_user(
    user_id: int,
    _: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    user = session.get(User, user_id)
    if not user:
        return {"ok": False}
    user.is_active = False
    session.add(user)
    session.commit()
    return {"ok": True}


# --- Anonymized aggregate ----------------------------------------------------
@router.get("/performance/overview")
def performance_overview(
    _: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    return analytics.aggregate_overview_anonymized(session)


# --- Tenant-wide kill switch -------------------------------------------------
class TenantKillReq(BaseModel):
    tenant_id: int
    reason: str


@router.post("/kill-switch", response_model=KillSwitch)
def admin_kill_switch(
    req: TenantKillReq,
    current: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> KillSwitch:
    return risk_mod.set_kill_switch(
        session,
        tenant_id=req.tenant_id,
        user_id=None,
        scope="tenant",
        reason=req.reason,
        set_by="admin",
    )


@router.post("/kill-switch/{kill_id}/clear")
def admin_clear_kill_switch(
    kill_id: int,
    current: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    ok = risk_mod.clear_kill_switch(session, kill_id, by=f"admin:{current.id}")
    return {"ok": ok}
