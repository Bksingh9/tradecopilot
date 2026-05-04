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
