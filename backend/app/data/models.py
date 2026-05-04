"""Pydantic models for market data."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Quote(BaseModel):
    symbol: str
    exchange: Optional[str] = None  # "NSE" | "BSE" | "US"
    ltp: float = Field(..., description="Last traded price")
    bid: Optional[float] = None
    ask: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    prev_close: Optional[float] = None
    volume: Optional[int] = None
    currency: str = "INR"
    timestamp: datetime
    source: str  # "0xramm" | "yfinance" | "alpaca"


class Candle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
