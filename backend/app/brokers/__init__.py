"""Broker connector layer.

Each broker exposes the same interface (see app.brokers.base.BrokerClient).
Stateful sessions (access tokens) are stored in BrokerConnection (see trading.models)
and looked up per-user.
"""
from __future__ import annotations

from app.brokers.base import BrokerClient
from app.brokers.models import BrokerName, OrderRequest, OrderResult, Position, Order


def get_client(name: BrokerName, access_token: str | None = None) -> BrokerClient:
    """Factory: return a broker client by name."""
    from app.brokers.zerodha_client import ZerodhaClient
    from app.brokers.upstox_client import UpstoxClient
    from app.brokers.alpaca_client import AlpacaClient

    if name == "zerodha":
        return ZerodhaClient(access_token=access_token)
    if name == "upstox":
        return UpstoxClient(access_token=access_token)
    if name == "alpaca":
        return AlpacaClient()
    raise ValueError(f"Unknown broker: {name}")


__all__ = [
    "BrokerClient",
    "BrokerName",
    "OrderRequest",
    "OrderResult",
    "Position",
    "Order",
    "get_client",
]
