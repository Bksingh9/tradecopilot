"""Backtest endpoints: configure + queue + read results."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.common.exceptions import NotFound
from app.database import get_session
from app.scheduler import get_scheduler
from app.trading.learning import BacktestConfig, execute_run
from app.trading.models import BacktestRun

router = APIRouter()


@router.post("/run", response_model=BacktestRun)
def run_backtest(
    strategy: str,
    config: BacktestConfig,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BacktestRun:
    row = BacktestRun(
        user_id=current.id,
        tenant_id=current.tenant_id,
        strategy=strategy,
        config_json=config.model_dump(mode="json"),
        status="queued",
    )
    session.add(row)
    session.commit()
    session.refresh(row)

    sched = get_scheduler()
    sched.add_job(
        execute_run,
        "date",
        run_date=datetime.utcnow() + timedelta(seconds=1),
        kwargs={"run_id": row.id},
        id=f"bt_{row.id}",
        misfire_grace_time=300,
        replace_existing=True,
    )
    return row


@router.get("/", response_model=list[BacktestRun])
def list_runs(
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    limit: int = 50,
) -> list[BacktestRun]:
    rows = session.exec(
        select(BacktestRun)
        .where(BacktestRun.user_id == current.id, BacktestRun.tenant_id == current.tenant_id)
        .order_by(BacktestRun.created_at.desc())
        .limit(limit)
    ).all()
    return list(rows)


@router.get("/{run_id}", response_model=BacktestRun)
def get_run(
    run_id: int,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> BacktestRun:
    row = session.get(BacktestRun, run_id)
    if not row or row.user_id != current.id or row.tenant_id != current.tenant_id:
        raise NotFound("Backtest not found")
    return row
