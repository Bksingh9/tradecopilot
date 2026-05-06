"""Trading endpoints: quotes, signals, orders, positions, dashboard, kill switch, tuning."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.audit import service as audit
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.brokers.models import OrderRequest, OrderResult
from app.common.exceptions import NotFound, PermissionDenied
from app.data import get_ohlcv, get_realtime_quote
from app.data.models import Quote
from app.database import get_session
from app.trading import execution
from app.trading import risk as risk_mod
from app.trading.models import KillSwitch, RiskRule, StrategyTuningSuggestion
from app.trading.strategies import STRATEGIES
from app.users import service as user_service

router = APIRouter()


# --- Quotes ------------------------------------------------------------------
@router.get("/quote", response_model=Quote)
def quote(symbol: str, exchange_hint: Optional[str] = None) -> Quote:
    return get_realtime_quote(symbol, exchange_hint=exchange_hint)


# --- Signals -----------------------------------------------------------------
class SignalRes(BaseModel):
    timestamp: datetime
    symbol: str
    side: str
    entry: float
    stop: float
    target: Optional[float]
    strategy: str
    rationale: str


@router.get("/signals", response_model=list[SignalRes])
def signals(
    symbol: str,
    strategy: str = Query("momentum"),
    days: int = 30,
    timeframe: str = "1d",
    exchange_hint: Optional[str] = None,
) -> list[SignalRes]:
    if strategy not in STRATEGIES:
        return []
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    df = get_ohlcv(symbol, start, end, timeframe, exchange_hint=exchange_hint)
    fn = STRATEGIES[strategy]
    sigs = fn(df, symbol)
    return [
        SignalRes(
            timestamp=s.timestamp, symbol=s.symbol, side=s.side, entry=s.entry, stop=s.stop,
            target=s.target, strategy=s.strategy, rationale=s.rationale,
        )
        for s in sigs
    ]


# --- Orders ------------------------------------------------------------------
@router.post("/orders", response_model=OrderResult)
def place_order(
    broker: str,
    order: OrderRequest,
    paper: Optional[bool] = None,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> OrderResult:
    return execution.execute_order(
        session, current.id, current.tenant_id, broker, order, paper=paper
    )


# --- Risk --------------------------------------------------------------------
class RiskRuleReq(BaseModel):
    max_risk_per_trade_pct: Optional[float] = None
    daily_loss_limit_pct: Optional[float] = None
    max_open_positions: Optional[int] = None
    restricted_symbols: Optional[list[str]] = None
    paper_only: Optional[bool] = None
    starting_equity: Optional[float] = None


@router.get("/risk", response_model=RiskRule)
def get_risk(
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> RiskRule:
    rule = session.get(RiskRule, current.id)
    if not rule:
        rule = RiskRule(user_id=current.id, tenant_id=current.tenant_id)
        session.add(rule)
        session.commit()
        session.refresh(rule)
    return rule


@router.put("/risk", response_model=RiskRule)
def update_risk(
    req: RiskRuleReq,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> RiskRule:
    rule = session.get(RiskRule, current.id) or RiskRule(
        user_id=current.id, tenant_id=current.tenant_id
    )
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    audit.record(
        session, tenant_id=current.tenant_id, user_id=current.id, actor="user",
        action="risk.updated", subject_type="risk_rule", subject_id=current.id,
        payload=req.model_dump(exclude_unset=True),
    )
    return rule


# --- Dashboard ---------------------------------------------------------------
class DashboardRes(BaseModel):
    realized_pnl_today: float
    open_positions_count: int
    daily_loss_limit_value: float
    risk_used_pct: float
    watchlist: list[Quote]
    kill_switch_active: bool
    kill_switch_reason: Optional[str] = None
    autonomy_mode: str


@router.get("/dashboard", response_model=DashboardRes)
def dashboard(
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> DashboardRes:
    rule = session.get(RiskRule, current.id) or RiskRule(
        user_id=current.id, tenant_id=current.tenant_id
    )
    realized = risk_mod.realized_pnl_today(session, current.id)
    daily_limit = rule.starting_equity * (rule.daily_loss_limit_pct / 100.0)
    used_pct = abs(min(realized, 0.0)) / daily_limit * 100.0 if daily_limit else 0.0

    prefs = user_service.get_or_create_prefs(session, current)
    quotes: list[Quote] = []
    for sym in (prefs.watchlist or [])[:8]:
        try:
            quotes.append(get_realtime_quote(sym))
        except Exception:
            continue

    blocked_reason = risk_mod.is_blocked(session, current.id, current.tenant_id)
    return DashboardRes(
        realized_pnl_today=realized,
        open_positions_count=risk_mod.open_positions_count(session, current.id),
        daily_loss_limit_value=daily_limit,
        risk_used_pct=used_pct,
        watchlist=quotes,
        kill_switch_active=blocked_reason is not None,
        kill_switch_reason=blocked_reason,
        autonomy_mode=current.autonomy_mode,
    )


# --- Kill switch (user) ------------------------------------------------------
class UserKillReq(BaseModel):
    reason: str = "user-initiated"


@router.post("/kill-switch")
def user_kill_switch(
    req: UserKillReq,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Set a user-scoped kill switch.

    NOTE: deliberately dropped `response_model=KillSwitch` here — pydantic v2 +
    SQLModel `table=True` was returning an empty `{}` body in production (the
    field schema collapses for table classes that have FK-typed fields and an
    Optional datetime). We serialize explicitly so the frontend always sees the
    `id` it needs to call /kill-switch/{id}/clear.
    """
    row = risk_mod.set_kill_switch(
        session,
        tenant_id=current.tenant_id, user_id=current.id, scope="user",
        reason=req.reason, set_by=f"user:{current.id}",
    )
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "user_id": row.user_id,
        "scope": row.scope,
        "reason": row.reason,
        "set_by": row.set_by,
        "active": row.active,
        "cleared_at": row.cleared_at.isoformat() if row.cleared_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.post("/kill-switch/{kill_id}/clear")
def user_clear_kill_switch(
    kill_id: int,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    row = session.get(KillSwitch, kill_id)
    if not row:
        raise NotFound("Kill switch not found")
    if row.scope == "tenant":
        raise PermissionDenied("Tenant-wide kill switch can only be cleared by an admin")
    if row.user_id != current.id or row.tenant_id != current.tenant_id:
        raise PermissionDenied("Not your kill switch")
    ok = risk_mod.clear_kill_switch(session, kill_id, by=f"user:{current.id}")
    return {"ok": ok}


# --- Tuning suggestions ------------------------------------------------------
@router.get("/tuning", response_model=list[StrategyTuningSuggestion])
def list_tuning_suggestions(
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    status: Optional[str] = None,
    limit: int = 50,
) -> list[StrategyTuningSuggestion]:
    q = select(StrategyTuningSuggestion).where(
        StrategyTuningSuggestion.user_id == current.id,
        StrategyTuningSuggestion.tenant_id == current.tenant_id,
    )
    if status:
        q = q.where(StrategyTuningSuggestion.status == status)
    q = q.order_by(StrategyTuningSuggestion.created_at.desc()).limit(limit)
    return list(session.exec(q).all())


@router.post("/tuning/{suggestion_id}/accept", response_model=StrategyTuningSuggestion)
def accept_tuning_suggestion(
    suggestion_id: int,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> StrategyTuningSuggestion:
    row = session.get(StrategyTuningSuggestion, suggestion_id)
    if not row or row.user_id != current.id or row.tenant_id != current.tenant_id:
        raise NotFound("Suggestion not found")
    if row.status != "pending":
        raise PermissionDenied("Already reviewed")
    row.status = "accepted"
    row.reviewed_by = current.id
    row.reviewed_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    audit.record(
        session, tenant_id=current.tenant_id, user_id=current.id, actor="user",
        action="tuning.accepted",
        subject_type="tuning_suggestion", subject_id=suggestion_id,
        payload={"strategy": row.strategy},
    )
    return row


@router.post("/tuning/{suggestion_id}/reject", response_model=StrategyTuningSuggestion)
def reject_tuning_suggestion(
    suggestion_id: int,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> StrategyTuningSuggestion:
    row = session.get(StrategyTuningSuggestion, suggestion_id)
    if not row or row.user_id != current.id or row.tenant_id != current.tenant_id:
        raise NotFound("Suggestion not found")
    if row.status != "pending":
        raise PermissionDenied("Already reviewed")
    row.status = "rejected"
    row.reviewed_by = current.id
    row.reviewed_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    audit.record(
        session, tenant_id=current.tenant_id, user_id=current.id, actor="user",
        action="tuning.rejected",
        subject_type="tuning_suggestion", subject_id=suggestion_id,
        payload={"strategy": row.strategy},
    )
    return row
