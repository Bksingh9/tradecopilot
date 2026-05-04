"""End-to-end: signup → set risk → log dummy trades → fetch summary."""
from __future__ import annotations

from datetime import datetime, timedelta


def _auth(client, email="t@example.com", password="password123"):
    r = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_user_flow(client, session):
    headers = _auth(client)

    # 1) update risk
    r = client.put(
        "/api/trading/risk",
        json={"max_risk_per_trade_pct": 1.0, "daily_loss_limit_pct": 3.0,
              "max_open_positions": 5, "starting_equity": 100_000},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["max_open_positions"] == 5
    user_tenant_id = r.json()["tenant_id"]
    user_id = r.json()["user_id"]

    # 2) seed two dummy trades directly via DB
    from app.trading.models import Trade
    from sqlmodel import Session
    from app.database import engine
    with Session(engine) as s:
        s.add(Trade(
            user_id=user_id, tenant_id=user_tenant_id, broker="alpaca",
            symbol="AAPL", side="BUY", qty=10,
            entry_price=150, exit_price=160, stop_price=145,
            realized_pnl=100, r_multiple=2.0, strategy="momentum",
            status="CLOSED", paper=True,
            opened_at=datetime.utcnow() - timedelta(days=2),
            closed_at=datetime.utcnow() - timedelta(days=1, hours=23),
        ))
        s.add(Trade(
            user_id=user_id, tenant_id=user_tenant_id, broker="alpaca",
            symbol="AAPL", side="SELL", qty=10,
            entry_price=160, exit_price=155, stop_price=165,
            realized_pnl=-50, r_multiple=-1.0, strategy="momentum",
            status="CLOSED", paper=True,
            opened_at=datetime.utcnow() - timedelta(days=1),
            closed_at=datetime.utcnow() - timedelta(hours=23),
        ))
        s.commit()

    # 3) summary endpoint returns analytics + streaks
    r = client.get("/api/journal/summary", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary"]["closed_count"] == 2
    assert body["summary"]["total_pnl"] == 50
    assert "streaks" in body
