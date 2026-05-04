"""Pure pandas feature builders + ML-stub directional model + news-stub.

The "ML model" here is a transparent logistic combination of normalized features.
It is intentionally simple and clearly labeled as a stub — operators are expected
to swap in a real model later via the same interface.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd


def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def _rsi(s: pd.Series, period: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def compute_features(df: pd.DataFrame) -> dict:
    """Returns the feature dict used by Analyst."""
    if df is None or df.empty or len(df) < 50:
        return {}
    close = df["close"]
    feats = {
        "close": float(close.iloc[-1]),
        "ret_1": float(close.pct_change().iloc[-1] or 0.0),
        "ret_5": float(close.pct_change(5).iloc[-1] or 0.0),
        "ret_20": float(close.pct_change(20).iloc[-1] or 0.0),
        "ema_fast": float(_ema(close, 9).iloc[-1]),
        "ema_slow": float(_ema(close, 21).iloc[-1]),
        "ema_200": float(_ema(close, 200).iloc[-1]) if len(close) >= 200 else float(close.mean()),
        "atr_pct": float((_atr(df).iloc[-1] / close.iloc[-1]) * 100.0) if not pd.isna(_atr(df).iloc[-1]) else 0.0,
        "rsi14": float(_rsi(close).iloc[-1] or 50.0),
    }
    return feats


def directional_probability(features: dict) -> float:
    """ML-stub: logistic combination of features → P(up) in (0,1).

    NOTE: This is *not* a real ML model. It is a transparent, deterministic
    combination intended to be swapped out for a real one with the same
    `(features) -> p_up` signature.
    """
    if not features:
        return 0.5
    z = 0.0
    z += 1.5 * np.tanh(features.get("ret_5", 0.0) * 50)
    z += 0.8 * np.tanh(features.get("ret_20", 0.0) * 25)
    z += 0.6 * (1 if features.get("ema_fast", 0) > features.get("ema_slow", 0) else -1)
    z += 0.4 * np.tanh((features.get("rsi14", 50) - 50) / 25)
    z -= 0.5 * max(0.0, features.get("atr_pct", 0.0) - 3.0)
    return float(1.0 / (1.0 + math.exp(-z)))


def news_sentiment_stub(symbol: str) -> dict:
    """Always returns neutral. Replace this with a real news/sentiment provider."""
    return {"sentiment": 0.0, "source": "stub", "symbol": symbol}
