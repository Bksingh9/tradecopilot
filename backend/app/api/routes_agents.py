"""Agent endpoints — manual cycle, EOD flatten, manage open trades, weekly coach."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.agent_orchestrator import DecisionOutcome, run_decision_cycle
from app.agents.coach_agent import CoachAgent
from app.agents.execution_agent import ExecutionAgent
from app.agents.models import CycleReport, ExecutionResult
from app.agents.orchestrator import Orchestrator
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.billing.policy import enforce_plan
from app.database import get_session
from app.trading.models import AIReport

router = APIRouter()


class CycleRunReq(BaseModel):
    symbols: list[str]
    timeframe: str = "1d"
    broker: str = "alpaca"
    exchange_hint: Optional[str] = None


@router.post("/cycle/run", response_model=CycleReport)
def run_cycle(
    req: CycleRunReq,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CycleReport:
    enforce_plan(session, current, "agent.cycle", {"symbols": req.symbols})
    orch = Orchestrator()
    return orch.run_cycle(
        session, current, req.symbols,
        timeframe=req.timeframe, broker=req.broker, exchange_hint=req.exchange_hint,
    )


# ---- Convenience: cycle over the user's watchlist ------------------------
class WatchlistCycleReq(BaseModel):
    timeframe: str = "1d"
    broker: str = "zerodha"
    exchange_hint: Optional[str] = "NSE"


@router.post("/cycle/watchlist", response_model=CycleReport)
def run_cycle_watchlist(
    req: WatchlistCycleReq = WatchlistCycleReq(),
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CycleReport:
    """Run the agent cycle over the user's saved watchlist (no symbols arg).

    The frontend's "Run cycle now" button hits this. The same code path is
    invoked by the periodic scheduler for users with autonomy>=semi_auto.
    """
    from app.users import service as user_service

    prefs = user_service.get_or_create_prefs(session, current)
    symbols = list(prefs.watchlist or [])
    if not symbols:
        # Empty cycle is fine — user just has no watchlist yet.
        return CycleReport(
            ran_at=__import__("datetime").datetime.utcnow(),
            symbols=[],
            decisions=[],
            placed_orders=[],
            errors=[],
        )

    enforce_plan(session, current, "agent.cycle", {"symbols": symbols})
    orch = Orchestrator()
    return orch.run_cycle(
        session, current, symbols,
        timeframe=req.timeframe, broker=req.broker, exchange_hint=req.exchange_hint,
    )


@router.post("/flatten-now", response_model=list[ExecutionResult])
def flatten_now(
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ExecutionResult]:
    return ExecutionAgent().flatten_eod(session, current)


@router.post("/manage-open", response_model=list[ExecutionResult])
def manage_open(
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ExecutionResult]:
    return ExecutionAgent().manage_open_trades(session, current)


class WeeklyCoachRes(BaseModel):
    id: int
    content: str


@router.post("/coach/weekly", response_model=WeeklyCoachRes)
def coach_weekly(
    days: int = 7,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> WeeklyCoachRes:
    row: AIReport = CoachAgent().weekly_review(session, current, days=days)
    return WeeklyCoachRes(id=row.id, content=row.content)


# --- ML + RAG decision cycle (richer than /cycle/run) ----------------------
class DecideReq(BaseModel):
    symbols: list[str]
    timeframe: str = "1d"
    broker: str = "alpaca"
    exchange_hint: Optional[str] = None


@router.post("/decide", response_model=list[DecisionOutcome])
def decide(
    req: DecideReq,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[DecisionOutcome]:
    enforce_plan(session, current, "agent.cycle", {"symbols": req.symbols})
    return run_decision_cycle(
        session, current, req.symbols,
        broker=req.broker, timeframe=req.timeframe, exchange_hint=req.exchange_hint,
    )
