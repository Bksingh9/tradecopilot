from __future__ import annotations

import pytest

from app.brokers.models import OrderRequest
from app.common.exceptions import RiskRuleViolation
from app.trading import execution, risk as risk_mod
from app.trading.models import BrokerConnection, RiskRule


def _seed_user_and_broker(session, email="ks@example.com"):
    from app.auth import service as auth_service
    user = auth_service.signup(session, email, "password123")
    session.add(BrokerConnection(
        user_id=user.id, tenant_id=user.tenant_id, broker="alpaca",
        encrypted_access_token=None, is_paper=True,
    ))
    session.add(RiskRule(user_id=user.id, tenant_id=user.tenant_id))
    session.commit()
    return user


def test_kill_switch_blocks_orders(session):
    user = _seed_user_and_broker(session)
    risk_mod.set_kill_switch(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        scope="user",
        reason="manual halt",
        set_by="user",
    )
    order = OrderRequest(symbol="AAPL", side="BUY", qty=1, paper=True)
    with pytest.raises(RiskRuleViolation) as exc:
        execution.execute_order(session, user.id, user.tenant_id, "alpaca", order)
    assert "kill switch" in str(exc.value).lower()


def test_clear_kill_switch_unblocks(session):
    user = _seed_user_and_broker(session, email="ks2@example.com")
    row = risk_mod.set_kill_switch(
        session,
        tenant_id=user.tenant_id, user_id=user.id, scope="user",
        reason="cool-off", set_by="user",
    )
    assert risk_mod.is_blocked(session, user.id, user.tenant_id) is not None
    risk_mod.clear_kill_switch(session, row.id, by="test")
    assert risk_mod.is_blocked(session, user.id, user.tenant_id) is None


def test_tenant_kill_switch_blocks_all_users_in_tenant(session):
    user_a = _seed_user_and_broker(session, email="ks_a@example.com")
    risk_mod.set_kill_switch(
        session,
        tenant_id=user_a.tenant_id, user_id=None, scope="tenant",
        reason="market halt", set_by="admin",
    )
    assert risk_mod.is_blocked(session, user_a.id, user_a.tenant_id) is not None
