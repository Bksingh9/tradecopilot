"""Broker-agnostic order execution layer with audit trail."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from app.audit import service as audit
from app.brokers import get_client
from app.brokers.models import OrderRequest, OrderResult
from app.common.crypto import decrypt
from app.common.exceptions import BrokerError, NotFound, RiskRuleViolation
from app.common.logging import get_logger, safe_event
from app.trading import risk as risk_mod
from app.trading.models import BrokerConnection, RiskRule, Trade

logger = get_logger(__name__)


def _ensure_rule(session: Session, user_id: int, tenant_id: int) -> RiskRule:
    rule = session.get(RiskRule, user_id)
    if not rule:
        rule = RiskRule(user_id=user_id, tenant_id=tenant_id)
        session.add(rule)
        session.commit()
        session.refresh(rule)
    return rule


def _simulate_paper_fill(broker: str, order: OrderRequest) -> OrderResult:
    """Synthesize a paper-mode broker fill without touching any broker API.

    For LIMIT orders we honour the user's stated limit price; for MARKET we
    try to pull a live quote, falling back to the limit/stop_price and finally
    to 0.0 if no source is reachable. Either way: ACCEPTED + FILLED in one
    step, deterministic enough for journaling and strategy qualification.
    """
    import uuid
    from app.data import get_realtime_quote

    fill_price: float = 0.0
    if order.order_type == "MARKET":
        try:
            q = get_realtime_quote(order.symbol, exchange_hint=order.exchange)
            fill_price = float(q.ltp) if q and q.ltp is not None else 0.0
        except Exception:
            fill_price = order.price or order.stop_price or 0.0
    else:
        fill_price = order.price or 0.0

    return OrderResult(
        broker=broker,                                      # type: ignore[arg-type]
        broker_order_id=f"PAPER-{uuid.uuid4().hex[:12].upper()}",
        status="FILLED",
        filled_qty=order.qty,
        avg_price=fill_price or None,
        raw={"paper": True, "simulated": True, "exchange": order.exchange},
    )


def _resolve_connection(session: Session, user_id: int, tenant_id: int, broker: str) -> BrokerConnection:
    conn = session.exec(
        select(BrokerConnection).where(
            BrokerConnection.user_id == user_id,
            BrokerConnection.tenant_id == tenant_id,
            BrokerConnection.broker == broker,
        )
    ).first()
    if not conn:
        raise NotFound(f"No {broker} connection for this user")
    return conn


def execute_order(
    session: Session,
    user_id: int,
    tenant_id: int,
    broker: str,
    order: OrderRequest,
    paper: Optional[bool] = None,
) -> OrderResult:
    blocked = risk_mod.is_blocked(session, user_id, tenant_id)
    if blocked:
        raise RiskRuleViolation(f"kill switch active: {blocked}")

    rule = _ensure_rule(session, user_id, tenant_id)
    if paper is not None:
        order.paper = paper

    ctx = risk_mod.build_context(session, user_id, rule)
    risk_mod.evaluate_order(order, rule, ctx)

    # Paper trading must NOT require a real broker connection. The whole point
    # of `paper=True` is that the user can validate strategies (and qualify
    # for full_auto) without ever wiring real broker credentials. Simulate
    # the fill in-process; the trade is still journaled with paper=True.
    if order.paper:
        result = _simulate_paper_fill(broker, order)
    else:
        conn = _resolve_connection(session, user_id, tenant_id, broker)
        access_token = decrypt(conn.encrypted_access_token) if conn.encrypted_access_token else None
        client = get_client(broker, access_token=access_token)
        try:
            result = client.place_order(order)
        except Exception as e:
            raise BrokerError(f"{broker} place_order failed: {e}") from e

    safe_event(
        logger, logging.INFO, "order.placed",
        user_id=user_id, tenant_id=tenant_id, broker=broker,
        symbol=order.symbol, side=order.side, qty=order.qty,
        broker_order_id=result.broker_order_id, paper=order.paper,
    )

    trade = Trade(
        user_id=user_id, tenant_id=tenant_id, broker=broker,
        symbol=order.symbol, exchange=order.exchange,
        side=order.side, qty=order.qty,
        entry_price=order.price or (result.avg_price or 0.0),
        stop_price=order.stop_price, strategy=order.strategy,
        status="OPEN", paper=order.paper, opened_at=datetime.utcnow(),
    )
    session.add(trade)
    session.commit()
    session.refresh(trade)

    audit.record(
        session, tenant_id=tenant_id, user_id=user_id, actor="user",
        action="order.placed",
        subject_type="trade", subject_id=trade.id,
        payload={
            "broker": broker, "symbol": order.symbol, "side": order.side,
            "qty": order.qty, "paper": order.paper,
            "broker_order_id": result.broker_order_id,
        },
    )
    return result
