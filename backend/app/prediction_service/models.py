"""Pydantic models for the prediction service."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

ModelKind = Literal["gbm", "xgboost", "lightgbm", "lstm_stub", "transformer_stub"]


class ModelConfig(BaseModel):
    strategy: str = "directional"           # logical bucket (e.g. directional, vol)
    symbol: str
    timeframe: str = "1d"
    label_horizon: int = Field(5, ge=1, le=60)   # bars ahead for the label
    label_kind: Literal["sign", "return"] = "sign"
    kind: ModelKind = "gbm"
    train_window_days: int = 365 * 2
    val_fraction: float = Field(0.2, ge=0.05, le=0.5)
    hyperparams: dict = Field(default_factory=dict)
    exchange_hint: Optional[str] = None


class PredictionResult(BaseModel):
    symbol: str
    timeframe: str
    prob_up: float = 0.5
    prob_down: float = 0.5
    expected_return: float = 0.0     # in fractional terms (e.g. 0.012 = 1.2%)
    risk_score: float = 0.5          # 0..1, higher = more uncertain / risky
    model_version: str = "baseline"
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    notes: list[str] = Field(default_factory=list)
