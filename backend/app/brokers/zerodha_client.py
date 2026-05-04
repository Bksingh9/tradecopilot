"""Zerodha Kite Connect adapter.

Imports of pykiteconnect are deferred so the rest of the app works without it.
Real usage requires `pip install pykiteconnect`.
"""
from __future__ import annotations

from typing import Optional

from app.brokers.base import BrokerClient
from app.brokers.models import Order, OrderRequest, OrderResult, Position
from app.common.exceptions import BrokerError
from app.common.logging import get_logger
from app.config import settings

logger = get_logger(__name__)


class ZerodhaClient(BrokerClient):
    name = "zerodha"

    def __init__(self, access_token: Optional[str] = None) -> None:
        self.api_key = settings.zerodha_api_key
        self.api_secret = settings.zerodha_api_secret
        self.access_token = access_token
        self._kite = None

    # --- internal: lazy-load pykiteconnect ----------------------------------
    def _kc(self):
        if self._kite is not None:
            return self._kite
        try:
            from kiteconnect import KiteConnect  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise BrokerError("pykiteconnect not installed") from e
        if not self.api_key:
            raise BrokerError("ZERODHA_API_KEY not configured")
        kc = KiteConnect(api_key=self.api_key)
        if self.access_token:
            kc.set_access_token(self.access_token)
        self._kite = kc
        return kc

    # --- BrokerClient -------------------------------------------------------
    def login_url(self, state: Optional[str] = None) -> str:
        return self._kc().login_url()

    def exchange_code(self, code_or_request_token: str) -> str:
        if not self.api_secret:
            raise BrokerError("ZERODHA_API_SECRET not configured")
        try:
            data = self._kc().generate_session(code_or_request_token, api_secret=self.api_secret)
            self.access_token = data["access_token"]
            return self.access_token
        except Exception as e:
            raise BrokerError(f"zerodha exchange failed: {e}") from e

    def place_order(self, order: OrderRequest) -> OrderResult:
        kc = self._kc()
        try:
            order_id = kc.place_order(
                variety="regular",
                tradingsymbol=order.symbol,
                exchange=order.exchange or "NSE",
                transaction_type=order.side,
                quantity=order.qty,
                product=order.product,
                order_type=order.order_type,
                price=order.price,
                trigger_price=order.stop_price,
            )
            return OrderResult(
                broker="zerodha", broker_order_id=str(order_id), status="ACCEPTED"
            )
        except Exception as e:
            raise BrokerError(f"zerodha place_order failed: {e}") from e

    def get_positions(self) -> list[Position]:
        kc = self._kc()
        out: list[Position] = []
        try:
            data = kc.positions().get("net", [])
            for p in data:
                out.append(
                    Position(
                        broker="zerodha",
                        symbol=p["tradingsymbol"],
                        exchange=p.get("exchange"),
                        qty=int(p["quantity"]),
                        avg_price=float(p["average_price"]),
                        last_price=float(p.get("last_price") or 0) or None,
                        unrealized_pnl=float(p.get("unrealised") or 0) or None,
                        realized_pnl=float(p.get("realised") or 0) or None,
                    )
                )
        except Exception as e:
            raise BrokerError(f"zerodha get_positions failed: {e}") from e
        return out

    def get_orders(self, status_filter: Optional[str] = None) -> list[Order]:
        kc = self._kc()
        try:
            rows = kc.orders()
        except Exception as e:
            raise BrokerError(f"zerodha get_orders failed: {e}") from e
        out: list[Order] = []
        for r in rows:
            if status_filter and r.get("status") != status_filter:
                continue
            out.append(
                Order(
                    broker="zerodha",
                    broker_order_id=str(r["order_id"]),
                    symbol=r["tradingsymbol"],
                    side=r["transaction_type"],
                    qty=int(r["quantity"]),
                    filled_qty=int(r.get("filled_quantity") or 0),
                    price=float(r.get("price") or 0) or None,
                    avg_price=float(r.get("average_price") or 0) or None,
                    status=r.get("status", "UNKNOWN"),
                )
            )
        return out
