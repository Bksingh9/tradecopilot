"""Walk-forward returns numeric metrics on synthetic data."""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

from app.trading import learning
from app.trading.learning import BacktestConfig


def _write_synthetic_cache(symbol: str, timeframe: str = "1d") -> None:
    rng = np.random.default_rng(7)
    n = 600
    drift = np.linspace(0, 50, n)
    closes = 100 + drift + rng.normal(0, 1.5, n)
    idx = pd.date_range(datetime(2024, 1, 1, tzinfo=timezone.utc), periods=n, freq="D")
    df = pd.DataFrame({
        "open": closes, "high": closes + 0.5, "low": closes - 0.5,
        "close": closes, "volume": 1000,
    }, index=idx)
    os.makedirs("./data_cache", exist_ok=True)
    df.to_parquet(f"./data_cache/{symbol}_{timeframe}.parquet")


def test_walk_forward_returns_metrics(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.data_cache_dir", str(tmp_path))
    sym = "TEST"

    rng = np.random.default_rng(11)
    n = 600
    closes = 100 + np.linspace(0, 60, n) + rng.normal(0, 1.0, n)
    idx = pd.date_range(datetime(2024, 1, 1, tzinfo=timezone.utc), periods=n, freq="D")
    df = pd.DataFrame({
        "open": closes, "high": closes + 0.5, "low": closes - 0.5,
        "close": closes, "volume": 1000,
    }, index=idx)
    df.to_parquet(tmp_path / f"{sym}_1d.parquet")

    cfg = BacktestConfig(
        symbols=[sym],
        timeframe="1d",
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=600),
        train_test_ratio=0.7,
        walk_forward_folds=3,
    )
    res = learning.run_walk_forward("momentum", cfg)
    m = res["metrics"]
    assert isinstance(m["cagr"], float)
    assert isinstance(m["sharpe"], float)
    assert -1.0 <= m["max_dd"] <= 0.0
    assert 0.0 <= m["win_rate"] <= 1.0
    assert m["trade_count"] >= 0
