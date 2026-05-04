"""RAG context builder returns expected keys; falls back gracefully when empty."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.rag_context import build_market_context
from app.vector_memory import db as vm_db
from app.vector_memory import upsert_market_window


def _df(n: int = 250) -> pd.DataFrame:
    closes = np.linspace(100, 130, n)
    idx = pd.date_range(datetime(2024, 1, 1, tzinfo=timezone.utc), periods=n, freq="D")
    return pd.DataFrame({
        "open": closes, "high": closes + 0.5, "low": closes - 0.5,
        "close": closes, "volume": 1000,
    }, index=idx)


def test_build_market_context_returns_expected_keys(monkeypatch, tmp_path):
    monkeypatch.setattr("app.config.settings.models_dir", str(tmp_path))
    vm_db._reset_backend_for_tests()
    df = _df()
    ctx = build_market_context(tenant_id=1, symbol="ABC", timeframe="1d", recent_window=df)
    assert {"symbol", "timeframe", "prediction", "similar_windows", "current_features"} <= ctx.keys()
    assert ctx["prediction"]["model_version"] == "baseline"
    # No history seeded → no neighbours.
    assert ctx["similar_windows"] == []


def test_build_market_context_finds_similar_when_seeded(monkeypatch, tmp_path):
    monkeypatch.setattr("app.config.settings.models_dir", str(tmp_path))
    vm_db._reset_backend_for_tests()
    df = _df()

    from app.vector_memory import market_window_embedding

    vec = market_window_embedding(df)
    upsert_market_window(
        tenant_id=1, subject_id="hist_1", vector=vec.copy(),
        meta={"period": "2023-Q4", "regime": "bull", "return_n": 0.04},
    )
    ctx = build_market_context(tenant_id=1, symbol="ABC", timeframe="1d", recent_window=df, k=3)
    assert ctx["similar_windows"], "expected at least one similar window after seeding"
    assert ctx["similar_windows"][0]["subject_id"] == "hist_1"
    assert ctx["similar_windows"][0]["regime"] == "bull"
