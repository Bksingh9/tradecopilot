"""User self-management endpoints — primarily autonomy controls."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.audit import service as audit
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.billing.policy import enforce_plan
from app.common.exceptions import PermissionDenied
from app.database import get_session

router = APIRouter()

PAPER_QUALIFICATION_DAYS = 14
PAPER_QUALIFICATION_MIN_TRADES = 20


class AutonomyRes(BaseModel):
    autonomy_mode: str
    paper_qualified_at: Optional[datetime]
    consent_full_auto: bool
    eligible_for_full_auto: bool


class AutonomySetReq(BaseModel):
    autonomy_mode: str
    consent_full_auto: bool = False


@router.get("/autonomy", response_model=AutonomyRes)
def get_autonomy(current: User = Depends(get_current_user)) -> AutonomyRes:
    eligible = bool(current.paper_qualified_at) and current.consent_full_auto
    return AutonomyRes(
        autonomy_mode=current.autonomy_mode,
        paper_qualified_at=current.paper_qualified_at,
        consent_full_auto=current.consent_full_auto,
        eligible_for_full_auto=eligible,
    )


@router.put("/autonomy", response_model=AutonomyRes)
def set_autonomy(
    req: AutonomySetReq,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AutonomyRes:
    if req.autonomy_mode not in {"advisory", "semi_auto", "full_auto"}:
        raise PermissionDenied(f"unknown autonomy mode: {req.autonomy_mode}")

    enforce_plan(session, current, "autonomy.set", {"mode": req.autonomy_mode})

    if req.autonomy_mode == "full_auto":
        if not current.paper_qualified_at:
            raise PermissionDenied(
                "full_auto requires paper qualification "
                f"(≥{PAPER_QUALIFICATION_DAYS}d, ≥{PAPER_QUALIFICATION_MIN_TRADES} paper trades)"
            )
        if not req.consent_full_auto:
            raise PermissionDenied("full_auto requires explicit consent")

    prev = current.autonomy_mode
    current.autonomy_mode = req.autonomy_mode
    current.consent_full_auto = bool(req.consent_full_auto)
    current.updated_at = datetime.utcnow()
    session.add(current)
    session.commit()
    session.refresh(current)

    audit.record(
        session, tenant_id=current.tenant_id, user_id=current.id,
        actor="user", action="user.autonomy.set",
        subject_type="user", subject_id=current.id,
        payload={"from": prev, "to": current.autonomy_mode, "consent": current.consent_full_auto},
    )
    return AutonomyRes(
        autonomy_mode=current.autonomy_mode,
        paper_qualified_at=current.paper_qualified_at,
        consent_full_auto=current.consent_full_auto,
        eligible_for_full_auto=bool(current.paper_qualified_at) and current.consent_full_auto,
    )


# --- Watchlist ---------------------------------------------------------------
class WatchlistRes(BaseModel):
    watchlist: list[str]


class WatchlistReq(BaseModel):
    symbol: str


@router.get("/watchlist", response_model=WatchlistRes)
def get_watchlist(
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> WatchlistRes:
    from app.users import service as user_service
    prefs = user_service.get_or_create_prefs(session, current)
    return WatchlistRes(watchlist=list(prefs.watchlist or []))


@router.post("/watchlist/add", response_model=WatchlistRes)
def watchlist_add(
    req: WatchlistReq,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> WatchlistRes:
    from app.users import service as user_service
    prefs = user_service.get_or_create_prefs(session, current)
    sym = req.symbol.strip().upper()
    if not sym:
        raise PermissionDenied("symbol required")
    wl = list(prefs.watchlist or [])
    if sym not in wl:
        wl.append(sym)
    if len(wl) > 50:
        raise PermissionDenied("watchlist cap reached (50)")
    prefs.watchlist = wl
    session.add(prefs)
    session.commit()
    session.refresh(prefs)
    return WatchlistRes(watchlist=list(prefs.watchlist or []))


@router.post("/watchlist/remove", response_model=WatchlistRes)
def watchlist_remove(
    req: WatchlistReq,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> WatchlistRes:
    from app.users import service as user_service
    prefs = user_service.get_or_create_prefs(session, current)
    sym = req.symbol.strip().upper()
    wl = [s for s in (prefs.watchlist or []) if s.upper() != sym]
    prefs.watchlist = wl
    session.add(prefs)
    session.commit()
    session.refresh(prefs)
    return WatchlistRes(watchlist=list(prefs.watchlist or []))


@router.post("/qualify-paper", response_model=AutonomyRes)
def mark_paper_qualified(
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AutonomyRes:
    """Self-service marker: in production this would be computed from real
    paper-trading history (≥14 days, ≥20 trades). Here we expose a manual
    endpoint that an admin process / scheduled task would call.
    """
    current.paper_qualified_at = datetime.utcnow()
    session.add(current)
    session.commit()
    session.refresh(current)
    audit.record(
        session, tenant_id=current.tenant_id, user_id=current.id,
        actor="system", action="user.paper_qualified",
        subject_type="user", subject_id=current.id, payload={},
    )
    return AutonomyRes(
        autonomy_mode=current.autonomy_mode,
        paper_qualified_at=current.paper_qualified_at,
        consent_full_auto=current.consent_full_auto,
        eligible_for_full_auto=current.consent_full_auto,
    )
