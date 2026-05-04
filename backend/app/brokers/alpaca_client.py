"""Alpaca trading adapter via REST. Defaults to paper if APP_ENV != prod."""
from __future__ import annotations

from typing import Optional

import httpx

from app.brokers.base import BrokerClient
from app.brokers.models import Order, OrderRequest, OrderResult, Position
from app.common.exceptions import BrokerError
from app.config import settings

_TIMEOUT = httpx.Timeout(8.0, connect=4.0)


class AlpacaClient(BrokerClient):
    name = "alpaca"

    def __init__(self) -> None:
        self.api_key = settings.alpaca_api_key
        self.api_secret = settings.alpaca_api_secret
        self.base = settings.alpaca_trade_base
        self.paper = settings.alpaca_paper

    def _headers(self) -> dict:
        if not (self.api_key and self.api_secret):
            raise BrokerError("Alpaca keys not configured")
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
            "Accept": "application/json",
        }

    # Alpaca uses static keys → no OAuth flow.
    def login_url(self, state: Optional[str] = None) -> str:
        return ""

    def exchange_code(self, code_or_request_token: str) -> str:
        return ""

    def place_order(self, order: OrderRequest) -> OrderResult:
        url = f"{self.base.rstrip('/')}/v2/orders"
        body = {
            "symbol": order.symbol,
            "qty": order.qty,
            "side": order.side.lower(),
            "type": "market" if order.order_type == "MARKET" else "limit",
            "time_in_force": "day",
            "client_order_id": order.client_order_id,
        }
        if order.price is not None and body["type"] == "limit":
            body["limit_price"] = order.price
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.post(url, json=body, headers=self._headers())
        if r.status_code >= 400:
            raise BrokerError(f"alpaca place_order failed: {r.text[:200]}")
        data = r.json()
        return OrderResult(
            broker="alpaca",
            broker_order_id=str(data.get("id", "")),
            status=data.get("status", "ACCEPTED").upper(),
            filled_qty=int(float(data.get("filled_qty") or 0)),
            avg_price=float(data.get("filled_avg_price") or 0) or None,
            raw=data,
        )

    def get_positions(self) -> list[Position]:
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.get(f"{self.base.rstrip('/')}/v2/positions", headers=self._headers())
        if r.status_code >= 400:
            raise BrokerError(f"alpaca positions failed: {r.text[:200]}")
        return [
            Position(
                broker="alpaca",
                symbol=p["symbol"],
                exchange="US",
                qty=int(float(p["qty"])),
                avg_price=float(p["avg_entry_price"]),
                last_price=float(p.get("current_price") or 0) or None,
                unrealized_pnl=float(p.get("unrealized_pl") or 0) or None,
            )
            for p in r.json()
        ]

    def get_orders(self, status_filter: Optional[str] = None) -> list[Order]:
        params = {"status": (status_filter or "all").lower(), "limit": 100}
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.get(f"{self.base.rstrip('/')}/v2/orders", headers=self._headers(), params=params)
        if r.status_code >= 400:
            raise BrokerError(f"alpaca orders failed: {r.text[:200]}")
        out: list[Order] = []
        for o in r.json():
            out.append(
                Order(
                    broker="alpaca",
                    broker_order_id=str(o["id"]),
                    symbol=o["symbol"],
                    side=o["side"].upper(),
                    qty=int(float(o["qty"])),
                    filled_qty=int(float(o.get("filled_qty") or 0)),
                    price=float(o.get("limit_price") or 0) or None,
                    avg_price=float(o.get("filled_avg_price") or 0) or None,
                    status=o["status"].upper(),
                )
            )
        return out
