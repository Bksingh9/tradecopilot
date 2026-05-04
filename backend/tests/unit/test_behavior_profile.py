"""get_user_behavior_profile detects observable tendencies."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.auth import service as auth_service
from app.journal.analytics import get_user_behavior_profile
from app.trading.models import Trade


def test_overtrading_flag_fires(session):
    user = auth_service.signup(session, "bp1@example.com", "password123")
    base = datetime.utcnow().replace(hour=10, minute=0, second=0, microsecond=0)
    for i in range(7):                                  # ≥6 same-symbol same-day → flag
        session.add(Trade(
            user_id=user.id, tenant_id=user.tenant_id, broker="alpaca",
            symbol="AAPL", side="BUY", qty=10, entry_price=150.0,
            status="OPEN", paper=True,
            opened_at=base + timedelta(minutes=i * 10),
        ))
    session.commit()
    p = get_user_behavior_profile(session, user)
    assert p["tendencies"]["overtrading_flag"] is True
    assert p["sample_size"] >= 7


def test_revenge_after_loss_flag(session):
    user = auth_service.signup(session, "bp2@example.com", "password123")
    t_close = datetime.utcnow() - timedelta(days=1)
    session.add(Trade(
        user_id=user.id, tenant_id=user.tenant_id, broker="alpaca",
        symbol="AAPL", side="BUY", qty=10, entry_price=150, exit_price=145,
        realized_pnl=-50.0, r_multiple=-1.0,
        status="CLOSED", paper=True,
        opened_at=t_close - timedelta(hours=1), closed_at=t_close,
    ))
    # New entry 10 minutes after the losing close.
    session.add(Trade(
        user_id=user.id, tenant_id=user.tenant_id, broker="alpaca",
        symbol="AAPL", side="BUY", qty=10, entry_price=145,
        status="OPEN", paper=True,
        opened_at=t_close + timedelta(minutes=10),
    ))
    session.commit()
    p = get_user_behavior_profile(session, user)
    assert p["tendencies"]["revenge_after_loss_flag"] is True
