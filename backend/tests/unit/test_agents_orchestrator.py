"""Risk agent must SCALE DOWN rather than reject when sizing is the only issue."""
from __future__ import annotations

from app.agents.models import CandidateTrade
from app.agents.risk_agent import RiskAgent
from app.auth import service as auth_service
from app.trading.models import RiskRule


def test_risk_agent_scales_down_oversized_notional(session):
    user = auth_service.signup(session, "ag@example.com", "password123")
    rule = RiskRule(
        user_id=user.id, tenant_id=user.tenant_id,
        max_risk_per_trade_pct=10.0,            # large risk %, but
        starting_equity=100_000.0,              # 20% notional cap will catch it
    )
    session.add(rule)
    session.commit()

    cand = CandidateTrade(
        symbol="ABC", side="BUY", qty=1, entry=1000.0, stop=950.0,
        strategy="momentum", rationale="test", paper=True,
    )
    decision = RiskAgent().review(session, cand, user)
    assert decision.action == "scale_down"
    assert 0 < decision.final_qty < 100
    assert "scaled" in decision.reason.lower() or "notional" in decision.reason.lower()


def test_risk_agent_rejects_when_kill_switch_active(session):
    from app.trading import risk as risk_mod

    user = auth_service.signup(session, "ag2@example.com", "password123")
    risk_mod.set_kill_switch(
        session, tenant_id=user.tenant_id, user_id=user.id,
        scope="user", reason="test halt", set_by="user",
    )
    cand = CandidateTrade(
        symbol="ABC", side="BUY", qty=1, entry=100.0, stop=95.0,
        strategy="momentum", rationale="test",
    )
    decision = RiskAgent().review(session, cand, user)
    assert decision.action == "reject"
    assert "kill switch" in decision.reason.lower()
