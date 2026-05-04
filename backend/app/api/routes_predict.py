"""Prediction service endpoints.

`POST /api/predict/train` queues a background training job (APScheduler) — never
trains synchronously on the request thread. `GET /api/predict/{symbol}` runs
inference using the latest trained model (or returns a baseline result).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.database import get_session
from app.prediction_service.inference import get_prediction
from app.prediction_service.models import ModelConfig, PredictionResult
from app.prediction_service.training import execute_training_job
from app.scheduler import get_scheduler

router = APIRouter()


@router.post("/train")
def queue_training(
    cfg: ModelConfig,
    current: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    sched = get_scheduler()
    job_id = f"train_{cfg.strategy}_{cfg.symbol}_{cfg.timeframe}_{int(datetime.utcnow().timestamp())}"
    sched.add_job(
        execute_training_job,
        "date",
        run_date=datetime.utcnow() + timedelta(seconds=1),
        kwargs={"cfg_dict": cfg.model_dump()},
        id=job_id,
        misfire_grace_time=600,
        replace_existing=True,
    )
    return {"queued": True, "job_id": job_id, "cfg": cfg.model_dump(mode="json")}


@router.get("/{symbol}", response_model=PredictionResult)
def predict(
    symbol: str,
    timeframe: str = "1d",
    exchange_hint: Optional[str] = None,
    current: User = Depends(get_current_user),
) -> PredictionResult:
    return get_prediction(symbol, timeframe, exchange_hint=exchange_hint)
