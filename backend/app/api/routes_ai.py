"""AI coaching endpoints.

- POST /weekly-report  → synchronous (FakeCoach + queues real run if external).
- POST /trade-comment/{id} → same.
- POST /tuning/request → enqueue a tuning review for a strategy.
- POST /callback → external worker writes a final result back (admin role required).
- GET /reports → list this user's stored reports.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.ai.coach import get_coach
from app.auth.dependencies import get_current_user, require_admin
from app.auth.models import User
from app.common.exceptions import NotFound
from app.database import get_session
from app.journal import journal_service as svc
from app.trading.models import AIReport, RiskRule, StrategyTuningSuggestion, Trade

router = APIRouter()


class WeeklyReportRes(BaseModel):
    id: int
    period_start: datetime
    period_end: datetime
    content: str


@router.post("/weekly-report", response_model=WeeklyReportRes)
def weekly_report(
    days: int = 7,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> WeeklyReportRes:
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    trades = svc.list_trades(session, current.id, start=start, end=end, limit=10_000)
    journal = svc.list_entries(session, current.id, start=start, end=end, limit=10_000)
    rule = session.get(RiskRule, current.id) or RiskRule(
        user_id=current.id, tenant_id=current.tenant_id
    )
    content = get_coach().generate_weekly_report(trades, journal, rule)
    row = AIReport(
        user_id=current.id, tenant_id=current.tenant_id, kind="weekly",
        period_start=start, period_end=end, content=content,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return WeeklyReportRes(id=row.id, period_start=start, period_end=end, content=content)


class TradeCommentRes(BaseModel):
    trade_id: int
    content: str


@router.post("/trade-comment/{trade_id}", response_model=TradeCommentRes)
def trade_comment(
    trade_id: int,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> TradeCommentRes:
    trade = session.get(Trade, trade_id)
    if not trade or trade.user_id != current.id or trade.tenant_id != current.tenant_id:
        raise NotFound("Trade not found")
    rule = session.get(RiskRule, current.id) or RiskRule(
        user_id=current.id, tenant_id=current.tenant_id
    )
    ctx = {
        "risk": {
            "max_risk_per_trade_pct": rule.max_risk_per_trade_pct,
            "max_open_positions": rule.max_open_positions,
        }
    }
    content = get_coach().comment_on_new_trade(trade, ctx)
    session.add(AIReport(
        user_id=current.id, tenant_id=current.tenant_id, kind="trade_comment", content=content
    ))
    session.commit()
    return TradeCommentRes(trade_id=trade_id, content=content)


# --- Tuning request ----------------------------------------------------------
class TuningRequestReq(BaseModel):
    strategy: str
    current_params: dict


@router.post("/tuning/request", response_model=StrategyTuningSuggestion)
def request_tuning(
    req: TuningRequestReq,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> StrategyTuningSuggestion:
    """Synchronously enqueues an LLM job and inserts a *pending* suggestion row.
    The worker is expected to update the row with `suggested_params + rationale`
    via /api/ai/callback.
    """
    guardrails = {
        "max_risk_per_trade_pct": [0.1, 5.0],
        "max_open_positions": [1, 10],
        "stop_atr_mult": [0.5, 5.0],
    }
    coach = get_coach()
    coach.request_tuning_review(
        {
            "user_id": current.id,
            "tenant_id": current.tenant_id,
            "strategy": req.strategy,
            "current_params": req.current_params,
        },
        guardrails,
    )
    row = StrategyTuningSuggestion(
        user_id=current.id,
        tenant_id=current.tenant_id,
        strategy=req.strategy,
        current_params=req.current_params,
        suggested_params={},
        rationale="(pending — awaiting LLM worker response)",
        status="pending",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


# --- Async callback for an external worker -----------------------------------
class CallbackReq(BaseModel):
    user_id: int
    tenant_id: int
    kind: str                 # "weekly" | "trade_comment" | "tuning_review"
    content: str
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    # Only used when kind == "tuning_review":
    suggestion_id: Optional[int] = None
    suggested_params: Optional[dict] = None
    rationale: Optional[str] = None


@router.post("/callback")
def callback(
    req: CallbackReq,
    _: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    """Worker pushes the LLM result back here. Admin role required."""
    if req.kind == "tuning_review" and req.suggestion_id is not None:
        row = session.get(StrategyTuningSuggestion, req.suggestion_id)
        if row and row.user_id == req.user_id and row.tenant_id == req.tenant_id:
            row.suggested_params = req.suggested_params or {}
            row.rationale = req.rationale or req.content[:1000]
            session.add(row)
            session.commit()
            return {"ok": True, "suggestion_id": row.id}

    rep = AIReport(
        user_id=req.user_id, tenant_id=req.tenant_id,
        kind=req.kind, content=req.content,
        period_start=req.period_start, period_end=req.period_end,
    )
    session.add(rep)
    session.commit()
    return {"ok": True, "id": rep.id}


@router.get("/reports", response_model=list[AIReport])
def list_reports(
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    limit: int = 20,
) -> list[AIReport]:
    rows = session.exec(
        select(AIReport)
        .where(AIReport.user_id == current.id, AIReport.tenant_id == current.tenant_id)
        .order_by(AIReport.created_at.desc())
        .limit(limit)
    ).all()
    return list(rows)
