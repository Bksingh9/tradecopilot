"""FastAPI dependencies: extract & validate the current user from JWT or API token.

RBAC: User.role ∈ {"user","admin"}. require_admin() checks role=="admin".
Multi-tenant: callers should additionally scope queries by current.tenant_id.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header
from sqlmodel import Session

from app.auth import service as auth_service
from app.auth.models import User
from app.common.exceptions import AuthError, PermissionDenied
from app.database import get_session


def _bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    x_api_token: Optional[str] = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    if x_api_token:
        user = auth_service.verify_api_token(session, x_api_token)
        if user:
            return user
        raise AuthError("Invalid API token")
    token = _bearer_token(authorization)
    if not token:
        raise AuthError("Missing credentials")
    user_id = auth_service.decode_access_token(token)
    user = session.get(User, user_id)
    if not user or not user.is_active:
        raise AuthError("User not found or disabled")
    return user


def require_admin(current: User = Depends(get_current_user)) -> User:
    if current.role != "admin":
        raise PermissionDenied("Admin only")
    return current


def require_role(role: str):
    def dep(current: User = Depends(get_current_user)) -> User:
        if current.role != role:
            raise PermissionDenied(f"Role '{role}' required")
        return current
    return dep
