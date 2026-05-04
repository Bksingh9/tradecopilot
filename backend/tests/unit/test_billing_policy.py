"""Plan gating denies disallowed actions on small plans."""
from __future__ import annotations

import pytest

from app.auth import service as auth_service
from app.billing.policy import enforce_plan
from app.common.exceptions import PermissionDenied


def test_free_plan_blocks_too_many_symbols(session):
    user = auth_service.signup(session, "p1@example.com", "password123")
    enforce_plan(session, user, "agent.cycle", {"symbols": ["A"]})
    with pytest.raises(PermissionDenied):
        enforce_plan(session, user, "agent.cycle", {"symbols": ["A", "B"]})


def test_free_plan_blocks_semi_auto(session):
    user = auth_service.signup(session, "p2@example.com", "password123")
    with pytest.raises(PermissionDenied):
        enforce_plan(session, user, "autonomy.set", {"mode": "semi_auto"})
    enforce_plan(session, user, "autonomy.set", {"mode": "advisory"})


def test_pro_plan_allows_semi_auto(session):
    from app.billing.models import Subscription

    user = auth_service.signup(session, "p3@example.com", "password123")
    session.add(Subscription(user_id=user.id, tenant_id=user.tenant_id, plan="pro"))
    session.commit()
    enforce_plan(session, user, "autonomy.set", {"mode": "semi_auto"})
    with pytest.raises(PermissionDenied):
        enforce_plan(session, user, "autonomy.set", {"mode": "full_auto"})
