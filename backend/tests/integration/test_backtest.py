from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.trading.backtesting import backtest
from app.trading.strategies import momentum


def test_backtest_runs_end_to_end():
    rng = np.random.default_rng(42)
    n = 300
    drift = np.linspace(0, 30, n)
    noise = rng.normal(0, 2, n)
    closes = 100 + drift + noise
    idx = pd.date_range(datetime(2024, 1, 1, tzinfo=timezone.utc), periods=n, freq="h")
    df = pd.DataFrame({
        "open": closes,
        "high": closes + 1,
        "low": closes - 1,
        "close": closes,
        "volume": 1000,
    }, index=idx)
    res = backtest(df, momentum, "TEST", starting_equity=100_000.0)
    assert res.equity_curve.iloc[-1] >= 0
    assert res.trade_count >= 0
    assert -1.0 <= res.max_drawdown <= 0.0
