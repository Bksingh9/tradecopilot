"""Vector memory + RAG primitives.

Public surface:
    upsert_market_window(...)
    query_similar_market_windows(vec, top_k)
    upsert_user_trade(...)
    query_similar_user_trades(user_id, vec, top_k)
    market_window_embedding(df) -> np.ndarray
    text_embedding_stub(s) -> np.ndarray

The default backend is in-memory (numpy + cosine similarity), suitable for dev
and single-process tests. Production should swap in pgvector by setting
`VECTOR_BACKEND=pgvector` and providing the SQL DSN.
"""
from app.vector_memory.db import (
    InMemoryVectorBackend,
    PgVectorBackend,
    VectorBackend,
    get_backend,
    query_similar_market_windows,
    query_similar_user_trades,
    upsert_market_window,
    upsert_user_trade,
)
from app.vector_memory.embeddings import (
    market_window_embedding,
    text_embedding_stub,
)

__all__ = [
    "VectorBackend", "InMemoryVectorBackend", "PgVectorBackend", "get_backend",
    "upsert_market_window", "query_similar_market_windows",
    "upsert_user_trade", "query_similar_user_trades",
    "market_window_embedding", "text_embedding_stub",
]
