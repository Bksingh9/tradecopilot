"""Pydantic models exchanged inside the decision pipeline."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.agents.models import AutonomyMode, CandidateTrade, ExecutionResult, RiskDecision
from app.prediction_service.models import PredictionResult


class DecisionContext(BaseModel):
    symbol: str
    timeframe: str
    prediction: PredictionResult
    similar_windows: list[dict] = Field(default_factory=list)
    current_features: dict = Field(default_factory=dict)
    risk_snapshot: dict = Field(default_factory=dict)
    autonomy: AutonomyMode = "advisory"
    user_behavior_profile: Optional[dict] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class DecisionProposal(BaseModel):
    candidate: CandidateTrade
    ml_confidence: float           # |p_up - 0.5| * 2 → 0..1
    rationale: str


class DecisionOutcome(BaseModel):
    context: DecisionContext
    proposal: Optional[DecisionProposal] = None
    decision: Optional[RiskDecision] = None
    execution: Optional[ExecutionResult] = None
    error: Optional[str] = None
