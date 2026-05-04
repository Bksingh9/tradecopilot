"""Critical observability property: every consequential action writes one AuditEvent."""
from __future__ import annotations

from sqlmodel import select

from app.audit.models import AuditEvent
from app.auth import service as auth_service
from app.trading import risk as risk_mod


def test_kill_switch_set_and_clear_each_write_one_event(session):
    user = auth_service.signup(session, "audit1@example.com", "password123")
    pre = len(session.exec(select(AuditEvent).where(AuditEvent.user_id == user.id)).all())

    row = risk_mod.set_kill_switch(
        session, tenant_id=user.tenant_id, user_id=user.id,
        scope="user", reason="testing", set_by="user",
    )
    risk_mod.clear_kill_switch(session, row.id, by="user")

    events = session.exec(
        select(AuditEvent).where(AuditEvent.user_id == user.id).order_by(AuditEvent.id)
    ).all()
    assert len(events) - pre == 2
    actions = [e.action for e in events[-2:]]
    assert actions == ["kill_switch.set", "kill_switch.cleared"]


def test_tuning_accept_writes_audit(client, engine):
    r = client.post("/api/auth/signup",
                    json={"email": "audit2@example.com", "password": "password123"})
    assert r.status_code == 200
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.post("/api/ai/tuning/request",
                    json={"strategy": "momentum", "current_params": {"fast": 9}},
                    headers=h)
    assert r.status_code == 200
    sid = r.json()["id"]

    r = client.post(f"/api/trading/tuning/{sid}/accept", headers=h)
    assert r.status_code == 200

    r = client.get("/api/audit/me", headers=h)
    assert r.status_code == 200
    actions = [e["action"] for e in r.json()]
    assert "tuning.accepted" in actions
