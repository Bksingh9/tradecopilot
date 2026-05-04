"""Numeric "brain" — feature engineering, ML training, and inference.

Public surface:
    get_prediction(symbol, timeframe, recent_window) -> PredictionResult
    train_model(cfg) -> dict           # MUST run as background job, never on request path
    evaluate_model(cfg) -> dict
"""
from app.prediction_service.inference import get_prediction
from app.prediction_service.models import ModelConfig, PredictionResult
from app.prediction_service.training import evaluate_model, train_model

__all__ = [
    "ModelConfig", "PredictionResult",
    "get_prediction", "train_model", "evaluate_model",
]
