"""Journal CRUD + analytics summary."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database import get_session
from app.journal import analytics
from app.journal import journal_service as svc
from app.trading.models import JournalEntry, Trade

router = APIRouter()


class JournalEntryReq(BaseModel):
    trade_id: Optional[int] = None
    setup: Optional[str] = None
    emotion_tag: Optional[str] = None
    screenshot_url: Optional[str] = None
    notes: Optional[str] = None


@router.post("/entries", response_model=JournalEntry)
def add_entry(
    req: JournalEntryReq,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> JournalEntry:
    return svc.add_entry(session, current, **req.model_dump())


@router.get("/entries", response_model=list[JournalEntry])
def list_entries(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = Query(200, le=1000),
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[JournalEntry]:
    return svc.list_entries(session, current.id, start=start, end=end, limit=limit)


@router.get("/trades", response_model=list[Trade])
def list_trades(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    status: Optional[str] = None,
    strategy: Optional[str] = None,
    symbol: Optional[str] = None,
    limit: int = Query(500, le=2000),
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[Trade]:
    return svc.list_trades(
        session, current.id,
        start=start, end=end, status=status, strategy=strategy, symbol=symbol, limit=limit,
    )


class SummaryRes(BaseModel):
    summary: dict
    by_symbol: dict
    by_strategy: dict
    by_hour: dict
    r_distribution: dict
    streaks: dict
    best_hour: Optional[int]
    worst_hour: Optional[int]


@router.get("/summary", response_model=SummaryRes)
def summary(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SummaryRes:
    trades = svc.list_trades(session, current.id, start=start, end=end, limit=10_000)
    best, worst = analytics.best_worst_hour(trades)
    return SummaryRes(
        summary=analytics.summary(trades).__dict__,
        by_symbol={k: v.__dict__ for k, v in analytics.by_symbol(trades).items()},
        by_strategy={k: v.__dict__ for k, v in analytics.by_strategy(trades).items()},
        by_hour={str(k): v.__dict__ for k, v in analytics.by_hour_of_day(trades).items()},
        r_distribution=analytics.r_distribution(trades),
        streaks=analytics.streaks(trades),
        best_hour=best,
        worst_hour=worst,
    )
