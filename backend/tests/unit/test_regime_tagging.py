"""tag_regime() labels synthetic price series correctly."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.trading.learning import tag_regime


def _make_df(closes: list[float]) -> pd.DataFrame:
    idx = pd.date_range(datetime(2024, 1, 1, tzinfo=timezone.utc),
                        periods=len(closes), freq="D")
    s = pd.Series(closes, index=idx)
    return pd.DataFrame({
        "open": s, "high": s * 1.005, "low": s * 0.995, "close": s, "volume": 1000,
    })


def test_bull_regime_dominant_in_strong_uptrend():
    closes = list(np.linspace(100, 200, 400))
    df = _make_df(closes)
    tags = tag_regime(df).dropna()
    # The latter half should be predominantly "bull"
    last_half = tags.iloc[len(tags) // 2:]
    assert (last_half == "bull").mean() > 0.5


def test_bear_regime_dominant_in_strong_downtrend():
    closes = list(np.linspace(200, 100, 400))
    df = _make_df(closes)
    tags = tag_regime(df).dropna()
    last_half = tags.iloc[len(tags) // 2:]
    assert (last_half == "bear").mean() > 0.5


def test_crash_label_appears_after_sharp_drop():
    closes = list(np.linspace(200, 200, 200)) + list(np.linspace(200, 130, 60))
    df = _make_df(closes)
    tags = tag_regime(df).dropna()
    assert "crash" in set(tags.iloc[-30:].unique())
