"""Broker-agnostic Pydantic models for orders/positions."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

BrokerName = Literal["zerodha", "upstox", "alpaca"]
Side = Literal["BUY", "SELL"]
OrderType = Literal["MARKET", "LIMIT", "SL", "SL-M"]
ProductType = Literal["CNC", "MIS", "NRML", "DAY", "GTC"]


class OrderRequest(BaseModel):
    symbol: str
    exchange: Optional[str] = None  # "NSE" | "BSE" | "US"
    side: Side
    qty: int = Field(..., gt=0)
    order_type: OrderType = "MARKET"
    price: Optional[float] = None
    stop_price: Optional[float] = None
    product: ProductType = "CNC"
    strategy: Optional[str] = None  # for journaling/analytics
    client_order_id: Optional[str] = None
    paper: bool = True  # default safe


class OrderResult(BaseModel):
    broker: BrokerName
    broker_order_id: str
    status: str  # "ACCEPTED" | "REJECTED" | "FILLED" | etc.
    filled_qty: int = 0
    avg_price: Optional[float] = None
    raw: dict = Field(default_factory=dict)
    submitted_at: datetime = Field(default_factory=datetime.utcnow)


class Position(BaseModel):
    broker: BrokerName
    symbol: str
    exchange: Optional[str] = None
    qty: int
    avg_price: float
    last_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    realized_pnl: Optional[float] = None


class Order(BaseModel):
    broker: BrokerName
    broker_order_id: str
    symbol: str
    side: Side
    qty: int
    filled_qty: int = 0
    price: Optional[float] = None
    avg_price: Optional[float] = None
    status: str
    placed_at: Optional[datetime] = None
