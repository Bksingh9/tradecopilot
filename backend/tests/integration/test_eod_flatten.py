"""EOD flatten closes open trades for an exchange that has hit its session close."""
from __future__ import annotations

from datetime import datetime, time as dtime
from unittest.mock import patch

from app.agents.execution_agent import ExecutionAgent
from app.auth import service as auth_service
from app.data.models import Quote
from app.trading.models import Trade


def test_flatten_eod_closes_nse_open_trades(session):
    user = auth_service.signup(session, "eod@example.com", "password123")
    t = Trade(
        user_id=user.id, tenant_id=user.tenant_id, broker="zerodha",
        symbol="RELIANCE", exchange="NSE", side="BUY", qty=10,
        entry_price=2500.0, stop_price=2450.0,
        status="OPEN", paper=True, opened_at=datetime.utcnow(),
    )
    session.add(t)
    session.commit()
    session.refresh(t)

    fake_quote = Quote(
        symbol="RELIANCE", exchange="NSE", ltp=2580.0,
        currency="INR", timestamp=datetime.utcnow(), source="test",
    )

    # Force the agent to think NSE has closed and the price is 2580.
    with patch("app.agents.execution_agent._EXCHANGE_CLOSE_UTC", {"NSE": dtime(0, 0)}), \
         patch("app.agents.execution_agent.get_realtime_quote", return_value=fake_quote):
        results = ExecutionAgent().flatten_eod(session, user)

    assert len(results) == 1
    session.refresh(t)
    assert t.status == "CLOSED"
    assert t.exit_price == 2580.0
    assert t.realized_pnl == (2580.0 - 2500.0) * 10
