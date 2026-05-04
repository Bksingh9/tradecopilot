"""SQLModel engine + session helpers."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args=connect_args,
    pool_pre_ping=True,
)


def init_db() -> None:
    """Create all tables. Used in dev / tests; prod uses Alembic migrations."""
    from app.auth import models as _auth_models  # noqa: F401
    from app.users import models as _user_models  # noqa: F401
    from app.trading import models as _trading_models  # noqa: F401
    from app.billing import models as _billing_models  # noqa: F401
    from app.audit import models as _audit_models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def db_ping() -> bool:
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
