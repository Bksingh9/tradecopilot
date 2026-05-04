"""Upstox v2 adapter.

Uses HTTPX directly so we don't force the upstox-python-sdk dependency for tests.
The official SDK can be swapped in later behind the same interface.
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlencode

import httpx

from app.brokers.base import BrokerClient
from app.brokers.models import Order, OrderRequest, OrderResult, Position
from app.common.exceptions import BrokerError
from app.config import settings


_TIMEOUT = httpx.Timeout(8.0, connect=4.0)
_BASE = "https://api.upstox.com/v2"


class UpstoxClient(BrokerClient):
    name = "upstox"

    def __init__(self, access_token: Optional[str] = None) -> None:
        self.client_id = settings.upstox_client_id
        self.client_secret = settings.upstox_client_secret
        self.redirect_uri = settings.upstox_redirect_uri
        self.access_token = access_token

    def _headers(self) -> dict:
        if not self.access_token:
            raise BrokerError("Upstox access_token missing")
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    def login_url(self, state: Optional[str] = None) -> str:
        if not self.client_id:
            raise BrokerError("UPSTOX_CLIENT_ID not configured")
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
        }
        if state:
            params["state"] = state
        return f"https://api.upstox.com/v2/login/authorization/dialog?{urlencode(params)}"

    def exchange_code(self, code_or_request_token: str) -> str:
        if not (self.client_id and self.client_secret):
            raise BrokerError("Upstox client credentials not configured")
        url = f"{_BASE}/login/authorization/token"
        data = {
            "code": code_or_request_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.post(url, data=data, headers={"Accept": "application/json"})
        if r.status_code >= 400:
            raise BrokerError(f"upstox token exchange failed: {r.text[:200]}")
        token = r.json().get("access_token")
        if not token:
            raise BrokerError("upstox: missing access_token in response")
        self.access_token = token
        return token

    def place_order(self, order: OrderRequest) -> OrderResult:
        url = f"{_BASE}/order/place"
        body = {
            "quantity": order.qty,
            "product": "I" if order.product == "MIS" else "D",
            "validity": "DAY",
            "price": order.price or 0,
            "tag": (order.strategy or "")[:32],
            "instrument_token": order.symbol,  # caller supplies upstox-style instrument key
            "order_type": "MARKET" if order.order_type == "MARKET" else "LIMIT",
            "transaction_type": order.side,
            "disclosed_quantity": 0,
            "trigger_price": order.stop_price or 0,
            "is_amo": False,
        }
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.post(url, json=body, headers=self._headers())
        if r.status_code >= 400:
            raise BrokerError(f"upstox place_order failed: {r.text[:200]}")
        data = r.json().get("data", {})
        return OrderResult(
            broker="upstox",
            broker_order_id=str(data.get("order_id", "")),
            status="ACCEPTED",
            raw=data,
        )

    def get_positions(self) -> list[Position]:
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.get(f"{_BASE}/portfolio/short-term-positions", headers=self._headers())
        if r.status_code >= 400:
            raise BrokerError(f"upstox positions failed: {r.text[:200]}")
        rows = r.json().get("data", []) or []
        return [
            Position(
                broker="upstox",
                symbol=p.get("trading_symbol") or p.get("tradingsymbol") or "",
                exchange=p.get("exchange"),
                qty=int(p.get("quantity") or 0),
                avg_price=float(p.get("average_price") or 0),
                last_price=float(p.get("last_price") or 0) or None,
                unrealized_pnl=float(p.get("unrealised") or 0) or None,
                realized_pnl=float(p.get("realised") or 0) or None,
            )
            for p in rows
        ]

    def get_orders(self, status_filter: Optional[str] = None) -> list[Order]:
        with httpx.Client(timeout=_TIMEOUT) as c:
            r = c.get(f"{_BASE}/order/retrieve-all", headers=self._headers())
        if r.status_code >= 400:
            raise BrokerError(f"upstox orders failed: {r.text[:200]}")
        rows = r.json().get("data", []) or []
        out: list[Order] = []
        for o in rows:
            if status_filter and o.get("status") != status_filter:
                continue
            out.append(
                Order(
                    broker="upstox",
                    broker_order_id=str(o.get("order_id")),
                    symbol=o.get("trading_symbol") or "",
                    side=o.get("transaction_type") or "BUY",
                    qty=int(o.get("quantity") or 0),
                    filled_qty=int(o.get("filled_quantity") or 0),
                    price=float(o.get("price") or 0) or None,
                    avg_price=float(o.get("average_price") or 0) or None,
                    status=o.get("status") or "UNKNOWN",
                )
            )
        return out
