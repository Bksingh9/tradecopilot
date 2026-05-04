"""Feature matrix builder for the prediction service.

Produces a `(X: pd.DataFrame, y: pd.Series)` pair from OHLCV bars. The features
include classical technical indicators + volatility + return lags + rolling
z-scores. All features are *causal* (only past data, no look-ahead).
"""
from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd

from app.prediction_service.models import ModelConfig


# -------- indicators ------------------------------------------------------
def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(s: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ema_f = _ema(s, fast)
    ema_s = _ema(s, slow)
    macd = ema_f - ema_s
    sig = _ema(macd, signal)
    hist = macd - sig
    return macd, sig, hist


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(n).mean()


def _bollinger(s: pd.Series, n: int = 20, k: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    mid = _sma(s, n)
    sd = s.rolling(n).std(ddof=0)
    return mid + k * sd, mid, mid - k * sd


# -------- public ----------------------------------------------------------
def build_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Build a feature matrix from a tz-aware OHLCV DataFrame.

    All features are based on *past* bars (`shift()` is implicit in indicators
    that look back). The returned DataFrame is the same length as `df`; rows
    with NaNs are kept and should be dropped by the caller during training.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    close = df["close"]
    out = pd.DataFrame(index=df.index)

    out["ret_1"] = close.pct_change()
    out["ret_5"] = close.pct_change(5)
    out["ret_20"] = close.pct_change(20)
    for lag in (1, 2, 3, 5):
        out[f"logret_lag{lag}"] = np.log1p(out["ret_1"]).shift(lag)

    out["sma_20"] = _sma(close, 20) / close - 1.0
    out["ema_9"] = _ema(close, 9) / close - 1.0
    out["ema_21"] = _ema(close, 21) / close - 1.0
    out["ema_200"] = _ema(close, 200) / close - 1.0
    out["rsi_14"] = _rsi(close, 14)
    macd, sig, hist = _macd(close)
    out["macd"] = macd / close
    out["macd_sig"] = sig / close
    out["macd_hist"] = hist / close

    atr = _atr(df, 14)
    out["atr_pct"] = atr / close * 100.0
    bb_up, bb_mid, bb_lo = _bollinger(close, 20, 2.0)
    out["bb_pos"] = (close - bb_lo) / (bb_up - bb_lo).replace(0, np.nan)

    # Realized volatility & rolling z of returns
    rv = out["ret_1"].rolling(20).std(ddof=0)
    out["realized_vol_20"] = rv * np.sqrt(252)
    out["ret_z_20"] = (out["ret_1"] - out["ret_1"].rolling(20).mean()) / rv.replace(0, np.nan)

    return out


def make_xy(df: pd.DataFrame, cfg: ModelConfig) -> Tuple[pd.DataFrame, pd.Series]:
    """Returns aligned X/y.

    label_kind="sign":  y = 1 if close[t+h]/close[t] - 1 > 0 else 0
    label_kind="return": y = close[t+h]/close[t] - 1   (regression-style; not used by GBM)
    """
    X = build_feature_matrix(df)
    h = cfg.label_horizon
    fwd = df["close"].shift(-h) / df["close"] - 1.0
    y = (fwd > 0).astype(int) if cfg.label_kind == "sign" else fwd
    aligned = pd.concat([X, y.rename("y")], axis=1).dropna()
    return aligned.drop(columns=["y"]), aligned["y"]
