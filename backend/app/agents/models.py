"""Pydantic models passed between agents."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

AutonomyMode = Literal["advisory", "semi_auto", "full_auto"]
RiskAction = Literal["approve", "scale_down", "reject"]


class AnalystSignal(BaseModel):
    symbol: str
    exchange: Optional[str] = None
    timeframe: str
    timestamp: datetime
    features: dict = Field(default_factory=dict)        # {ema_fast, ema_slow, atr_pct, rsi, ...}
    p_up: float = 0.5                                    # ML-stub directional probability
    regime: Optional[str] = None                         # bull | bear | range | high_vol | low_vol | crash
    sentiment: float = 0.0                               # -1..1 stub
    notes: list[str] = Field(default_factory=list)


class CandidateTrade(BaseModel):
    symbol: str
    exchange: Optional[str] = None
    side: Literal["BUY", "SELL"]
    qty: int
    entry: float
    stop: float
    target: Optional[float] = None
    strategy: str
    rationale: str
    paper: bool = True


class RiskDecision(BaseModel):
    candidate: CandidateTrade
    action: RiskAction
    final_qty: int = 0
    reason: str = ""
    rule_snapshot: dict = Field(default_factory=dict)


class ExecutionResult(BaseModel):
    candidate: CandidateTrade
    decision: RiskDecision
    status: Literal["placed", "proposed", "skipped", "blocked"]
    broker_order_id: Optional[str] = None
    error: Optional[str] = None
    at: datetime = Field(default_factory=datetime.utcnow)


class StageEvent(BaseModel):
    stage: Literal["analyst", "strategy", "risk", "execution", "coach"]
    ok: bool
    summary: str
    payload: dict = Field(default_factory=dict)


class CycleReport(BaseModel):
    user_id: int
    tenant_id: int
    mode: AutonomyMode
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    stages: list[StageEvent] = Field(default_factory=list)
    results: list[ExecutionResult] = Field(default_factory=list)
