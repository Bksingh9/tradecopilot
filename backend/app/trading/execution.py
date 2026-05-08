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


# Last-resort price floor for paper sims when every upstream feed fails.
# These are rough mid-2025 closes — used only when realtime + OHLCV all fail,
# and only so the journal has a non-zero entry_price for accounting purposes.
# Real prices come from get_realtime_quote / get_ohlcv when those work.
_LAST_KNOWN_PRICES: dict[str, float] = {
    # NSE blue chips
    "RELIANCE": 1450.0, "RELIANCE.NS": 1450.0,
    "TCS": 4100.0, "TCS.NS": 4100.0,
    "INFY": 1850.0, "INFY.NS": 1850.0,
    "HDFCBANK": 1720.0, "HDFCBANK.NS": 1720.0,
    "ICICIBANK": 1320.0, "ICICIBANK.NS": 1320.0,
    "HINDUNILVR": 2450.0, "HINDUNILVR.NS": 2450.0,
    "ITC": 470.0, "ITC.NS": 470.0,
    "SBIN": 820.0, "SBIN.NS": 820.0,
    "BHARTIARTL": 1650.0, "BHARTIARTL.NS": 1650.0,
    "WIPRO": 540.0, "WIPRO.NS": 540.0,
    # US blue chips
    "AAPL": 230.0, "MSFT": 420.0, "GOOGL": 175.0, "AMZN": 200.0,
    "META": 580.0, "TSLA": 280.0, "NVDA": 140.0, "JPM": 220.0,
    "BRK-B": 460.0, "V": 290.0,
}


def _last_known_price(symbol: str) -> Optional[float]:
    sym = symbol.strip().upper()
    return _LAST_KNOWN_PRICES.get(sym)


def _simulate_paper_fill(broker: str, order: OrderRequest) -> OrderResult:
    """Synthesize a paper-mode broker fill without touching any broker API.

    Price-discovery cascade for MARKET orders:
      1. Live quote via get_realtime_quote (yfinance/NSE/Alpaca etc.)
      2. Last daily close from OHLCV history (handles flaky realtime feeds)
      3. order.price / order.stop_price hint
      4. 0.0 (last resort — journal will still record the trade)

    For LIMIT orders we honour the user's limit price directly. Either way:
    ACCEPTED + FILLED in one step, deterministic enough for journaling and
    paper-qualification.
    """
    import uuid
    from datetime import datetime, timedelta
    from app.data import get_realtime_quote, get_ohlcv

    fill_price: float = 0.0
    price_source: str = "none"

    if order.order_type == "MARKET":
        # 1: live quote
        try:
            q = get_realtime_quote(order.symbol, exchange_hint=order.exchange)
            if q and q.ltp is not None:
                fill_price = float(q.ltp)
                price_source = "realtime"
        except Exception as e:
            logger.warning("paper_fill realtime fail %s: %s", order.symbol, e)

        # 2: last close from recent OHLCV (most useful when realtime breaks)
        if not fill_price:
            try:
                end = datetime.utcnow()
                start = end - timedelta(days=10)
                df = get_ohlcv(order.symbol, start, end, "1d", exchange_hint=order.exchange)
                if df is not None and not df.empty and "close" in df.columns:
                    last_close = float(df["close"].dropna().iloc[-1])
                    if last_close > 0:
                        fill_price = last_close
                        price_source = "last_close"
            except Exception as e:
                logger.warning("paper_fill ohlcv fail %s: %s", order.symbol, e)

        # 3: user-supplied hint
        if not fill_price:
            fill_price = order.price or order.stop_price or 0.0
            if fill_price:
                price_source = "user_hint"

        # 4: last-known-price floor for popular symbols (so the journal always
        #    has a non-zero entry_price even when every upstream feed is down)
        if not fill_price:
            lkp = _last_known_price(order.symbol)
            if lkp:
                fill_price = lkp
                price_source = "last_known_floor"
    else:
        fill_price = order.price or 0.0
        price_source = "limit_price"

    return OrderResult(
        broker=broker,                                      # type: ignore[arg-type]
        broker_order_id=f"PAPER-{uuid.uuid4().hex[:12].upper()}",
        status="FILLED",
        filled_qty=order.qty,
        avg_price=fill_price or None,
        raw={
            "paper": True,
            "simulated": True,
            "exchange": order.exchange,
            "price_source": price_source,
        },
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
