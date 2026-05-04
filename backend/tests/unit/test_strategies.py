from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from app.trading.strategies import mean_reversion, momentum, opening_range_breakout


def _ohlcv_from_close(closes: list[float], start: datetime | None = None,
                     freq: str = "D") -> pd.DataFrame:
    start = start or datetime(2024, 1, 1, tzinfo=timezone.utc)
    idx = pd.date_range(start, periods=len(closes), freq=freq, tz="UTC")
    s = pd.Series(closes, index=idx, name="close")
    df = pd.DataFrame({
        "open": s,
        "high": s * 1.01,
        "low": s * 0.99,
        "close": s,
        "volume": 1000,
    })
    return df


def test_momentum_fires_on_bullish_cross():
    # 50 bars trending down then sharply up → forces an EMA cross
    closes = list(np.linspace(100, 80, 30)) + list(np.linspace(80, 130, 30))
    df = _ohlcv_from_close(closes)
    sigs = momentum(df, "TEST", fast=5, slow=15)
    assert len(sigs) == 1
    assert sigs[0].side == "BUY"


def test_momentum_no_signal_on_flat_data():
    df = _ohlcv_from_close([100] * 60)
    assert momentum(df, "TEST") == []


def test_mean_reversion_long_on_low_zscore():
    closes = [100] * 25 + [70]  # huge negative z-score on last bar
    df = _ohlcv_from_close(closes)
    sigs = mean_reversion(df, "TEST", lookback=20, z_thresh=2.0)
    assert sigs and sigs[0].side == "BUY"


def test_orb_long_on_breakout():
    # Build an intraday session: first 15m flat, then a breakout
    base = datetime(2024, 1, 2, 9, 15, tzinfo=timezone.utc)
    rows = []
    for i in range(15):
        rows.append((base + timedelta(minutes=i), 100, 101, 99, 100))
    for i in range(10):
        rows.append((base + timedelta(minutes=15 + i), 102, 105, 101, 105))
    df = pd.DataFrame(rows, columns=["t", "open", "high", "low", "close"]).set_index("t")
    df["volume"] = 1000
    sigs = opening_range_breakout(df, "NIFTY", or_minutes=15)
    assert sigs and sigs[0].side == "BUY"
