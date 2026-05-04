"""Shared pytest fixtures: in-memory SQLite engine + FastAPI client + helpers."""
from __future__ import annotations

import os
import tempfile

import pytest

# Ensure crypto + JWT are present BEFORE importing app modules.
os.environ.setdefault("SECRETS_FERNET_KEY", "")
os.environ.setdefault("JWT_SECRET", "test-secret-please-ignore")
os.environ.setdefault("AI_COACH_BACKEND", "fake")

from cryptography.fernet import Fernet  # noqa: E402

if not os.environ.get("SECRETS_FERNET_KEY"):
    os.environ["SECRETS_FERNET_KEY"] = Fernet.generate_key().decode()

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402

from app import database  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def engine():
    db_fd, path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    eng = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    database.engine = eng
    SQLModel.metadata.create_all(eng)
    yield eng
    os.unlink(path)


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture
def client(engine):
    return TestClient(app)


# --- Helpers ---------------------------------------------------------------
def signup(client, email: str = "t@example.com", password: str = "password123") -> dict:
    r = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def make_admin(engine, email: str = "admin@example.com", password: str = "password123") -> dict:
    """Create an admin user directly in the DB and return its bearer header."""
    from app.auth import service as auth_service
    from app.auth.models import User
    from sqlmodel import Session

    with Session(engine) as s:
        u = auth_service.signup(s, email, password)
        u.role = "admin"
        s.add(u)
        s.commit()
        s.refresh(u)
        token = auth_service.create_access_token(u.id)
    return {"Authorization": f"Bearer {token}"}
