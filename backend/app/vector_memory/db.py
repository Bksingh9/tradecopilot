"""Vector backend abstraction + default in-memory implementation."""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import numpy as np

from app.common.logging import get_logger
from app.config import settings

logger = get_logger(__name__)


@dataclass
class VectorRecord:
    id: str                 # globally unique within (kind, scope)
    kind: str               # "market" | "trade" | "journal" | "report"
    tenant_id: int
    user_id: Optional[int] = None
    subject_id: Optional[str] = None
    vector: np.ndarray = field(default_factory=lambda: np.zeros(0))
    meta: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


# --- ABC ------------------------------------------------------------------
class VectorBackend(ABC):
    @abstractmethod
    def upsert(self, record: VectorRecord) -> None: ...

    @abstractmethod
    def query(
        self, kind: str, tenant_id: int, vec: np.ndarray, *,
        user_id: Optional[int] = None, top_k: int = 5,
    ) -> list[tuple[VectorRecord, float]]: ...


# --- In-memory implementation --------------------------------------------
class InMemoryVectorBackend(VectorBackend):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows: dict[tuple[str, str], VectorRecord] = {}  # (kind, id) -> record

    def upsert(self, record: VectorRecord) -> None:
        if record.vector is None or record.vector.size == 0:
            raise ValueError("VectorRecord.vector must be a non-empty np.ndarray")
        with self._lock:
            self._rows[(record.kind, record.id)] = record

    def query(
        self, kind: str, tenant_id: int, vec: np.ndarray, *,
        user_id: Optional[int] = None, top_k: int = 5,
    ) -> list[tuple[VectorRecord, float]]:
        if vec is None or vec.size == 0:
            return []
        with self._lock:
            candidates = [
                r for r in self._rows.values()
                if r.kind == kind and r.tenant_id == tenant_id
                and (user_id is None or r.user_id == user_id)
                and r.vector.shape == vec.shape
            ]
        if not candidates:
            return []
        v = vec / (np.linalg.norm(vec) or 1.0)
        scored: list[tuple[VectorRecord, float]] = []
        for r in candidates:
            n = np.linalg.norm(r.vector) or 1.0
            sim = float(np.dot(r.vector / n, v))
            scored.append((r, sim))
        scored.sort(key=lambda kv: kv[1], reverse=True)
        return scored[:top_k]


# --- pgvector implementation ---------------------------------------------
class PgVectorBackend(VectorBackend):
    """Postgres + pgvector implementation.

    Schema (run once per database):

        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE TABLE IF NOT EXISTS embeddings (
            id           text PRIMARY KEY,
            kind         text NOT NULL,
            tenant_id    int  NOT NULL,
            user_id      int,
            subject_id   text,
            vector       vector NOT NULL,
            meta         jsonb DEFAULT '{}'::jsonb,
            created_at   timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS embeddings_kind_tenant_idx
            ON embeddings (kind, tenant_id);
        CREATE INDEX IF NOT EXISTS embeddings_vector_idx
            ON embeddings USING ivfflat (vector vector_cosine_ops) WITH (lists = 100);

    `query()` uses the cosine-distance operator `<=>`; we return cosine
    similarity = `1 - distance` so callers can compare to InMemoryVectorBackend.

    The DSN is taken from `settings.database_url` if it's a Postgres URL,
    otherwise we raise on first use with a clear error.
    """

    _SCHEMA_SQL = """
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE TABLE IF NOT EXISTS embeddings (
        id text PRIMARY KEY,
        kind text NOT NULL,
        tenant_id int NOT NULL,
        user_id int,
        subject_id text,
        vector vector NOT NULL,
        meta jsonb DEFAULT '{}'::jsonb,
        created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS embeddings_kind_tenant_idx ON embeddings (kind, tenant_id);
    CREATE INDEX IF NOT EXISTS embeddings_user_idx ON embeddings (kind, tenant_id, user_id);
    """

    def __init__(self, dsn: Optional[str] = None) -> None:
        self._dsn = dsn or self._infer_dsn()
        self._ensure_schema()

    def _infer_dsn(self) -> str:
        url = settings.database_url
        if not url.startswith(("postgresql://", "postgresql+psycopg2://", "postgres://")):
            raise RuntimeError(
                "PgVectorBackend requires DATABASE_URL to point at Postgres. "
                "Set VECTOR_BACKEND=memory for SQLite dev."
            )
        return url.replace("postgresql+psycopg2://", "postgresql://")

    def _connect(self):
        import psycopg2
        return psycopg2.connect(self._dsn)

    def _ensure_schema(self) -> None:
        try:
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(self._SCHEMA_SQL)
                conn.commit()
        except Exception as e:
            logger.warning("PgVectorBackend schema bootstrap failed: %s", e)

    @staticmethod
    def _vec_literal(v: np.ndarray) -> str:
        return "[" + ",".join(f"{float(x):.8f}" for x in v.tolist()) + "]"

    def upsert(self, record: VectorRecord) -> None:
        if record.vector is None or record.vector.size == 0:
            raise ValueError("VectorRecord.vector must be a non-empty np.ndarray")
        import json as _json

        sql = """
        INSERT INTO embeddings (id, kind, tenant_id, user_id, subject_id, vector, meta, created_at)
        VALUES (%s, %s, %s, %s, %s, %s::vector, %s::jsonb, now())
        ON CONFLICT (id) DO UPDATE
            SET vector = EXCLUDED.vector,
                meta = EXCLUDED.meta,
                created_at = now()
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, (
                record.id, record.kind, record.tenant_id, record.user_id,
                record.subject_id, self._vec_literal(record.vector),
                _json.dumps(record.meta or {}, default=str),
            ))
            conn.commit()

    def query(
        self, kind: str, tenant_id: int, vec: np.ndarray, *,
        user_id: Optional[int] = None, top_k: int = 5,
    ) -> list[tuple[VectorRecord, float]]:
        if vec is None or vec.size == 0:
            return []
        import json as _json

        params: list[Any] = [self._vec_literal(vec), kind, tenant_id]
        where = "WHERE kind = %s AND tenant_id = %s"
        if user_id is not None:
            where += " AND user_id = %s"
            params.append(user_id)
        params.append(int(top_k))
        sql = f"""
        SELECT id, kind, tenant_id, user_id, subject_id, vector::text, meta, created_at,
               (vector <=> %s::vector) AS dist
        FROM embeddings
        {where}
        ORDER BY vector <=> %s::vector
        LIMIT %s
        """
        # Reorder params to match placeholder order: query, kind, tenant, [user], k, query (twice)
        # easier: rewrite with explicit positional
        sql = f"""
        SELECT id, kind, tenant_id, user_id, subject_id, vector::text, meta, created_at,
               (vector <=> %s::vector) AS dist
        FROM embeddings
        {where}
        ORDER BY dist
        LIMIT %s
        """
        with self._connect() as conn, conn.cursor() as cur:
            ordered: list[Any] = [self._vec_literal(vec), kind, tenant_id]
            if user_id is not None:
                ordered.append(user_id)
            ordered.append(int(top_k))
            cur.execute(sql, ordered)
            rows = cur.fetchall()
        out: list[tuple[VectorRecord, float]] = []
        for r in rows:
            (rid, k, tid, uid, sid, vtext, meta, created_at, dist) = r
            try:
                arr = np.array([float(x) for x in vtext.strip("[]").split(",")])
            except Exception:
                arr = np.zeros(vec.size)
            try:
                meta_d = _json.loads(meta) if isinstance(meta, str) else (meta or {})
            except Exception:
                meta_d = {}
            similarity = float(1.0 - float(dist))
            out.append((VectorRecord(
                id=rid, kind=k, tenant_id=tid, user_id=uid,
                subject_id=sid, vector=arr, meta=meta_d,
                created_at=created_at if isinstance(created_at, datetime) else datetime.utcnow(),
            ), similarity))
        return out


# --- Factory --------------------------------------------------------------
_default_backend: Optional[VectorBackend] = None


def get_backend() -> VectorBackend:
    global _default_backend
    if _default_backend is not None:
        return _default_backend
    name = (getattr(settings, "vector_backend", "memory") or "memory").lower()
    if name == "pgvector":
        _default_backend = PgVectorBackend()
    else:
        _default_backend = InMemoryVectorBackend()
    return _default_backend


# --- Convenience helpers --------------------------------------------------
def upsert_market_window(
    *, tenant_id: int, subject_id: str, vector: np.ndarray, meta: dict | None = None,
) -> None:
    get_backend().upsert(VectorRecord(
        id=f"market:{subject_id}",
        kind="market",
        tenant_id=tenant_id,
        subject_id=subject_id,
        vector=vector,
        meta=meta or {},
    ))


def query_similar_market_windows(
    *, tenant_id: int, vector: np.ndarray, top_k: int = 5,
) -> list[tuple[VectorRecord, float]]:
    return get_backend().query("market", tenant_id, vector, top_k=top_k)


def upsert_user_trade(
    *, tenant_id: int, user_id: int, trade_id: int, vector: np.ndarray, meta: dict | None = None,
) -> None:
    get_backend().upsert(VectorRecord(
        id=f"trade:{user_id}:{trade_id}",
        kind="trade",
        tenant_id=tenant_id,
        user_id=user_id,
        subject_id=str(trade_id),
        vector=vector,
        meta=meta or {},
    ))


def query_similar_user_trades(
    *, tenant_id: int, user_id: int, vector: np.ndarray, top_k: int = 5,
) -> list[tuple[VectorRecord, float]]:
    return get_backend().query("trade", tenant_id, vector, user_id=user_id, top_k=top_k)


def upsert_user_journal(
    *, tenant_id: int, user_id: int, entry_id: int, vector: np.ndarray, meta: dict | None = None,
) -> None:
    get_backend().upsert(VectorRecord(
        id=f"journal:{user_id}:{entry_id}",
        kind="journal",
        tenant_id=tenant_id,
        user_id=user_id,
        subject_id=str(entry_id),
        vector=vector,
        meta=meta or {},
    ))


def upsert_user_report(
    *, tenant_id: int, user_id: int, report_id: int, vector: np.ndarray, meta: dict | None = None,
) -> None:
    get_backend().upsert(VectorRecord(
        id=f"report:{user_id}:{report_id}",
        kind="report",
        tenant_id=tenant_id,
        user_id=user_id,
        subject_id=str(report_id),
        vector=vector,
        meta=meta or {},
    ))


# Test hook: reset the singleton so tests can swap backends.
def _reset_backend_for_tests() -> None:
    global _default_backend
    _default_backend = None
