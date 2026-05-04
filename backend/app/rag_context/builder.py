"""Combine ML predictions, similar historical windows, and textual context
(news/journal notes for those windows) into a compact JSON blob suitable
for an LLM prompt or a downstream agent.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from app.common.logging import get_logger
from app.prediction_service import get_prediction
from app.prediction_service.features import build_feature_matrix
from app.vector_memory import market_window_embedding, query_similar_market_windows

logger = get_logger(__name__)


def _last_features(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {}
    feats = build_feature_matrix(df).dropna()
    if feats.empty:
        return {}
    last = feats.iloc[-1]
    keys = [k for k in ("ret_1", "ret_5", "ret_20", "rsi_14", "atr_pct", "macd_hist", "realized_vol_20")
            if k in last.index]
    return {k: float(last[k]) for k in keys}


def build_market_context(
    *,
    tenant_id: int,
    symbol: str,
    timeframe: str,
    recent_window: pd.DataFrame,
    k: int = 5,
    exchange_hint: Optional[str] = None,
) -> dict:
    """Returns a JSON-friendly dict with prediction + similar windows + features."""
    prediction = get_prediction(symbol, timeframe, recent_window, exchange_hint=exchange_hint)
    current_features = _last_features(recent_window)

    similar: list[dict] = []
    try:
        vec = market_window_embedding(recent_window)
        if vec.size and vec.any():
            for rec, score in query_similar_market_windows(tenant_id=tenant_id, vector=vec, top_k=k):
                similar.append({
                    "subject_id": rec.subject_id,
                    "score": float(score),
                    "period": rec.meta.get("period"),
                    "regime": rec.meta.get("regime"),
                    "return_n": rec.meta.get("return_n"),
                    "journal_excerpts": rec.meta.get("journal_excerpts", [])[:3],
                    "created_at": rec.created_at.isoformat() if isinstance(rec.created_at, datetime) else None,
                })
    except Exception as e:
        logger.warning("rag_context: vector lookup failed: %s", e)

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "prediction": prediction.model_dump(),
        "similar_windows": similar,
        "current_features": current_features,
    }
