"""Inference API. Returns a baseline PredictionResult on registry miss so
callers (orchestrator, RAG, agents) never break before the first model trains.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
import pandas as pd

from app.common.logging import get_logger
from app.data import get_ohlcv
from app.prediction_service import registry
from app.prediction_service.features import build_feature_matrix
from app.prediction_service.models import ModelConfig, PredictionResult

logger = get_logger(__name__)


def _baseline(symbol: str, timeframe: str, note: str) -> PredictionResult:
    return PredictionResult(
        symbol=symbol.upper(),
        timeframe=timeframe,
        prob_up=0.5,
        prob_down=0.5,
        expected_return=0.0,
        risk_score=0.5,
        model_version="baseline",
        notes=[note, "Baseline returned because no trained model is available."],
    )


def get_prediction(
    symbol: str,
    timeframe: str = "1d",
    recent_window: Optional[pd.DataFrame] = None,
    *,
    strategy: str = "directional",
    kind: str = "gbm",
    exchange_hint: Optional[str] = None,
) -> PredictionResult:
    """Return a PredictionResult for the most recent bar of `recent_window`.

    If the caller doesn't pass a window, we'll pull a small one ourselves so
    the function is usable from any agent without ceremony.
    """
    cfg = ModelConfig(
        strategy=strategy, symbol=symbol, timeframe=timeframe,
        kind=kind, exchange_hint=exchange_hint,  # type: ignore[arg-type]
    )

    df = recent_window
    if df is None or df.empty:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=400)
        df = get_ohlcv(symbol, start, end, timeframe, exchange_hint=exchange_hint)
    if df is None or df.empty:
        return _baseline(symbol, timeframe, "no OHLCV available")

    loaded = registry.load_latest(cfg)
    if loaded is None:
        return _baseline(symbol, timeframe, "no trained model in registry")

    X = build_feature_matrix(df).dropna()
    if X.empty:
        return _baseline(symbol, timeframe, "feature matrix empty after dropna")

    # Align to model's feature names if recorded.
    if loaded.feature_names:
        missing = [c for c in loaded.feature_names if c not in X.columns]
        if missing:
            logger.warning("inference: missing features %s — falling back to baseline", missing[:5])
            return _baseline(symbol, timeframe, f"feature mismatch: missing {len(missing)}")
        X = X[loaded.feature_names]

    last = X.iloc[[-1]].values
    est = loaded.estimator
    try:
        if hasattr(est, "predict_proba"):
            p_up = float(est.predict_proba(last)[:, 1][0])
        else:
            p_up = float(est.predict(last)[0])
    except Exception as e:
        logger.warning("inference predict failed: %s — baseline", e)
        return _baseline(symbol, timeframe, f"predict failed: {e}")

    p_up = max(0.0, min(1.0, p_up))
    p_dn = 1.0 - p_up

    # Crude expected_return + risk_score from features.
    rv = X["realized_vol_20"].iloc[-1] if "realized_vol_20" in X.columns else 0.0
    atr_pct = X["atr_pct"].iloc[-1] if "atr_pct" in X.columns else 0.0
    expected_return = float((p_up - 0.5) * 2.0 * (atr_pct / 100.0))  # very rough
    risk_score = float(np.clip((rv or 0.0) / 0.5, 0.05, 0.95))

    return PredictionResult(
        symbol=symbol.upper(),
        timeframe=timeframe,
        prob_up=p_up,
        prob_down=p_dn,
        expected_return=expected_return,
        risk_score=risk_score,
        model_version=str(loaded.meta.get("version", "unknown")),
        notes=[
            f"learner={loaded.meta.get('config', {}).get('kind', 'gbm')}",
            f"trained_rows={loaded.meta.get('metrics', {}).get('n', 'n/a')}",
        ],
    )
