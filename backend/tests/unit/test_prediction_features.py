from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.prediction_service.features import build_feature_matrix, make_xy
from app.prediction_service.models import ModelConfig


def _df(n: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    closes = 100 + np.cumsum(rng.normal(0, 1, n))
    idx = pd.date_range(datetime(2024, 1, 1, tzinfo=timezone.utc), periods=n, freq="D")
    return pd.DataFrame({
        "open": closes, "high": closes + 0.5, "low": closes - 0.5,
        "close": closes, "volume": 1000,
    }, index=idx)


def test_feature_matrix_has_expected_columns_and_no_nan_at_tail():
    X = build_feature_matrix(_df())
    assert {"sma_20", "ema_9", "ema_21", "rsi_14", "macd_hist",
            "atr_pct", "bb_pos", "realized_vol_20"}.issubset(X.columns)
    last = X.tail(1).iloc[0]
    assert last.notna().all()


def test_make_xy_label_horizon_aligns():
    cfg = ModelConfig(symbol="X", timeframe="1d", label_horizon=5)
    X, y = make_xy(_df(), cfg)
    assert len(X) == len(y)
    assert set(y.unique()) <= {0, 1}
    # The last `horizon` rows must drop because the forward label is unknown.
    assert len(X) <= 300 - 5
