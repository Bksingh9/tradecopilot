"""Auth service: password hashing, JWT, API token issuance + verification.

On signup we always create a *personal tenant* for the new user. Partner-driven
signups (see app.api.routes_partner) attach the new user to the partner's tenant.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlmodel import Session, select

from app.auth.models import Tenant, User, UserAPIToken
from app.common.exceptions import AuthError, ValidationError
from app.config import settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- Passwords ----------------------------------------------------------------
def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters")
    return _pwd.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _pwd.verify(password, hashed)


# --- JWT ----------------------------------------------------------------------
def create_access_token(user_id: int, ttl_min: Optional[int] = None) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=ttl_min or settings.jwt_ttl_min)
    payload = {"sub": str(user_id), "exp": expires, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError) as e:
        raise AuthError("Invalid or expired token") from e


# --- API tokens ---------------------------------------------------------------
def _hash_api_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def issue_api_token(session: Session, user: User, name: str) -> tuple[UserAPIToken, str]:
    """Returns (token row, plaintext) — plaintext is only shown once."""
    plaintext = "tc_" + secrets.token_urlsafe(32)
    row = UserAPIToken(
        user_id=user.id,
        tenant_id=user.tenant_id,
        name=name,
        token_hash=_hash_api_token(plaintext),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row, plaintext


def verify_api_token(session: Session, plaintext: str) -> Optional[User]:
    row = session.exec(
        select(UserAPIToken).where(
            UserAPIToken.token_hash == _hash_api_token(plaintext),
            UserAPIToken.revoked == False,  # noqa: E712
        )
    ).first()
    if not row:
        return None
    user = session.get(User, row.user_id)
    if not user or not user.is_active:
        return None
    row.last_used_at = datetime.utcnow()
    session.add(row)
    session.commit()
    return user


# --- Tenants ------------------------------------------------------------------
def create_tenant(session: Session, name: str, plan: str = "free") -> Tenant:
    tenant = Tenant(name=name, plan=plan)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant


# --- Signup / login -----------------------------------------------------------
def signup(
    session: Session,
    email: str,
    password: str,
    *,
    tenant_id: Optional[int] = None,
    role: str = "user",
) -> User:
    """Create a user. If tenant_id is None, create a fresh personal tenant."""
    email = email.strip().lower()
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        raise ValidationError("Email already registered")

    if tenant_id is None:
        tenant = create_tenant(session, name=email)
        tenant_id = tenant.id

    user = User(
        email=email,
        hashed_password=hash_password(password),
        tenant_id=tenant_id,
        role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def login(session: Session, email: str, password: str) -> User:
    user = session.exec(select(User).where(User.email == email.strip().lower())).first()
    if not user or not verify_password(password, user.hashed_password):
        raise AuthError("Invalid email or password")
    if not user.is_active:
        raise AuthError("Account disabled")
    return user
