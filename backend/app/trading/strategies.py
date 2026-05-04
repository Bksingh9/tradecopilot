"""Built-in baseline strategies. Each is a pure function over OHLCV → list of Signal.

Signals are NOT auto-traded. They are suggestions evaluated by the risk engine
and surfaced to the user via the API.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Literal, Optional

import pandas as pd

SignalSide = Literal["BUY", "SELL"]


@dataclass
class Signal:
    timestamp: datetime
    symbol: str
    side: SignalSide
    entry: float
    stop: float
    target: Optional[float]
    strategy: str
    rationale: str


def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


# ---------------------------------------------------------------------------
# 1) Momentum / trend-following on intraday candles (5m/15m).
# ---------------------------------------------------------------------------
def momentum(df: pd.DataFrame, symbol: str, fast: int = 9, slow: int = 21,
             stop_atr_mult: float = 1.5, atr_period: int = 14) -> list[Signal]:
    if df is None or df.empty or len(df) < max(slow, atr_period) + 2:
        return []
    df = df.copy()
    df["ema_fast"] = _ema(df["close"], fast)
    df["ema_slow"] = _ema(df["close"], slow)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["atr"] = tr.rolling(atr_period).mean()

    out: list[Signal] = []
    prev = df.iloc[-2]
    cur = df.iloc[-1]
    cross_up = prev["ema_fast"] <= prev["ema_slow"] and cur["ema_fast"] > cur["ema_slow"]
    cross_dn = prev["ema_fast"] >= prev["ema_slow"] and cur["ema_fast"] < cur["ema_slow"]
    atr = float(cur["atr"] or 0.0)
    if cross_up and atr > 0:
        out.append(
            Signal(
                timestamp=cur.name.to_pydatetime() if hasattr(cur.name, "to_pydatetime") else datetime.utcnow(),
                symbol=symbol,
                side="BUY",
                entry=float(cur["close"]),
                stop=float(cur["close"] - stop_atr_mult * atr),
                target=float(cur["close"] + 2 * stop_atr_mult * atr),
                strategy="momentum",
                rationale=f"EMA{fast} crossed above EMA{slow}; ATR-based stop {stop_atr_mult}x",
            )
        )
    elif cross_dn and atr > 0:
        out.append(
            Signal(
                timestamp=cur.name.to_pydatetime() if hasattr(cur.name, "to_pydatetime") else datetime.utcnow(),
                symbol=symbol,
                side="SELL",
                entry=float(cur["close"]),
                stop=float(cur["close"] + stop_atr_mult * atr),
                target=float(cur["close"] - 2 * stop_atr_mult * atr),
                strategy="momentum",
                rationale=f"EMA{fast} crossed below EMA{slow}; ATR-based stop {stop_atr_mult}x",
            )
        )
    return out


# ---------------------------------------------------------------------------
# 2) Mean reversion on range-bound stocks: RSI(2) Bollinger touch.
# ---------------------------------------------------------------------------
def mean_reversion(df: pd.DataFrame, symbol: str, lookback: int = 20,
                   z_thresh: float = 2.0) -> list[Signal]:
    if df is None or df.empty or len(df) < lookback + 1:
        return []
    df = df.copy()
    df["mean"] = df["close"].rolling(lookback).mean()
    df["std"] = df["close"].rolling(lookback).std()
    df["z"] = (df["close"] - df["mean"]) / df["std"].replace(0, pd.NA)
    cur = df.iloc[-1]
    if pd.isna(cur["z"]):
        return []
    if cur["z"] <= -z_thresh:
        stop = float(cur["close"] - 1.0 * cur["std"])
        return [
            Signal(
                timestamp=cur.name.to_pydatetime() if hasattr(cur.name, "to_pydatetime") else datetime.utcnow(),
                symbol=symbol,
                side="BUY",
                entry=float(cur["close"]),
                stop=stop,
                target=float(cur["mean"]),
                strategy="mean_reversion",
                rationale=f"Z-score {cur['z']:.2f} ≤ -{z_thresh}; mean-revert long to MA{lookback}",
            )
        ]
    if cur["z"] >= z_thresh:
        stop = float(cur["close"] + 1.0 * cur["std"])
        return [
            Signal(
                timestamp=cur.name.to_pydatetime() if hasattr(cur.name, "to_pydatetime") else datetime.utcnow(),
                symbol=symbol,
                side="SELL",
                entry=float(cur["close"]),
                stop=stop,
                target=float(cur["mean"]),
                strategy="mean_reversion",
                rationale=f"Z-score {cur['z']:.2f} ≥ {z_thresh}; mean-revert short to MA{lookback}",
            )
        ]
    return []


# ---------------------------------------------------------------------------
# 3) ORB (Opening Range Breakout) — for indices on intraday data.
# Assumes the index df has a tz-aware DateTimeIndex; it forms the OR over
# the first `or_minutes` of the trading day and fires on a breakout.
# ---------------------------------------------------------------------------
def opening_range_breakout(
    df: pd.DataFrame,
    symbol: str,
    or_minutes: int = 15,
    market_open: time = time(9, 15),  # NSE
) -> list[Signal]:
    if df is None or df.empty:
        return []
    df = df.copy()
    df["date"] = df.index.date
    today = df["date"].iloc[-1]
    today_df = df[df["date"] == today]
    if today_df.empty:
        return []
    or_end = (datetime.combine(today, market_open)).replace(microsecond=0)
    or_window = today_df[today_df.index.time <= (datetime.combine(today, market_open) +
                                                 pd.Timedelta(minutes=or_minutes)).time()]
    if or_window.empty:
        return []
    or_high = float(or_window["high"].max())
    or_low = float(or_window["low"].min())
    cur = today_df.iloc[-1]
    if cur["close"] > or_high:
        return [
            Signal(
                timestamp=cur.name.to_pydatetime() if hasattr(cur.name, "to_pydatetime") else datetime.utcnow(),
                symbol=symbol,
                side="BUY",
                entry=float(cur["close"]),
                stop=or_low,
                target=float(cur["close"] + (or_high - or_low)),
                strategy="orb",
                rationale=f"Close {cur['close']:.2f} > OR high {or_high:.2f} (first {or_minutes}m)",
            )
        ]
    if cur["close"] < or_low:
        return [
            Signal(
                timestamp=cur.name.to_pydatetime() if hasattr(cur.name, "to_pydatetime") else datetime.utcnow(),
                symbol=symbol,
                side="SELL",
                entry=float(cur["close"]),
                stop=or_high,
                target=float(cur["close"] - (or_high - or_low)),
                strategy="orb",
                rationale=f"Close {cur['close']:.2f} < OR low {or_low:.2f} (first {or_minutes}m)",
            )
        ]
    return []


STRATEGIES = {
    "momentum": momentum,
    "mean_reversion": mean_reversion,
    "orb": opening_range_breakout,
}
