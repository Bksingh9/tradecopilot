"""InMemoryVectorBackend round-trip + cosine query nearest-neighbor."""
from __future__ import annotations

import numpy as np

from app.vector_memory import db as vm_db
from app.vector_memory import (
    market_window_embedding,
    query_similar_market_windows,
    query_similar_user_trades,
    upsert_market_window,
    upsert_user_trade,
)


def _reset():
    vm_db._reset_backend_for_tests()


def test_market_round_trip_and_top_k():
    _reset()
    rng = np.random.default_rng(0)
    vecs = [rng.normal(size=32) for _ in range(5)]
    for i, v in enumerate(vecs):
        upsert_market_window(tenant_id=1, subject_id=f"win_{i}", vector=v.copy(), meta={"i": i})
    # Query with the 3rd vector → should rank itself first.
    hits = query_similar_market_windows(tenant_id=1, vector=vecs[2].copy(), top_k=3)
    assert len(hits) == 3
    assert hits[0][0].subject_id == "win_2"
    assert hits[0][1] >= 0.99


def test_trade_query_is_user_scoped():
    _reset()
    rng = np.random.default_rng(1)
    v = rng.normal(size=32)
    upsert_user_trade(tenant_id=1, user_id=10, trade_id=1, vector=v.copy())
    upsert_user_trade(tenant_id=1, user_id=20, trade_id=1, vector=v.copy())
    hits = query_similar_user_trades(tenant_id=1, user_id=10, vector=v.copy(), top_k=5)
    assert len(hits) == 1
    assert hits[0][0].user_id == 10


def test_market_window_embedding_is_unit_norm():
    import pandas as pd
    from datetime import datetime, timezone

    closes = np.linspace(100, 120, 200)
    idx = pd.date_range(datetime(2024, 1, 1, tzinfo=timezone.utc), periods=200, freq="D")
    df = pd.DataFrame({
        "open": closes, "high": closes + 0.5, "low": closes - 0.5,
        "close": closes, "volume": 1000,
    }, index=idx)
    v = market_window_embedding(df, dim=32)
    assert v.shape == (32,)
    n = float(np.linalg.norm(v))
    assert n == 0.0 or abs(n - 1.0) < 1e-6
