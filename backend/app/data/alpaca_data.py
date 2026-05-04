"""Alpaca Market Data API helper. Returns None when not configured / no data."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx
import pandas as pd

from app.common.logging import get_logger
from app.config import settings
from app.data.models import Quote

logger = get_logger(__name__)

_TIMEOUT = httpx.Timeout(8.0, connect=4.0)


def _headers() -> Optional[dict]:
    if not settings.alpaca_api_key or not settings.alpaca_api_secret:
        return None
    return {
        "APCA-API-KEY-ID": settings.alpaca_api_key,
        "APCA-API-SECRET-KEY": settings.alpaca_api_secret,
    }


def get_quote(symbol: str) -> Optional[Quote]:
    headers = _headers()
    if not headers:
        return None
    url = f"{settings.alpaca_data_base.rstrip('/')}/v2/stocks/{symbol}/quotes/latest"
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            r = client.get(url, headers=headers)
            r.raise_for_status()
            payload = r.json().get("quote", {})
        bid, ask = float(payload.get("bp", 0)), float(payload.get("ap", 0))
        ltp = (bid + ask) / 2 if (bid and ask) else (bid or ask)
        if not ltp:
            return None
        return Quote(
            symbol=symbol,
            exchange="US",
            ltp=ltp,
            bid=bid or None,
            ask=ask or None,
            currency="USD",
            timestamp=datetime.utcnow(),
            source="alpaca",
        )
    except Exception as e:
        logger.warning("alpaca quote failed for %s: %s", symbol, e)
        return None


def get_ohlcv(symbol: str, start: datetime, end: datetime, timeframe: str = "1d") -> Optional[pd.DataFrame]:
    headers = _headers()
    if not headers:
        return None
    tf_map = {"1d": "1Day", "1h": "1Hour", "15m": "15Min", "5m": "5Min", "1m": "1Min"}
    tf = tf_map.get(timeframe, "1Day")
    url = f"{settings.alpaca_data_base.rstrip('/')}/v2/stocks/{symbol}/bars"
    params = {
        "start": start.isoformat() + "Z",
        "end": end.isoformat() + "Z",
        "timeframe": tf,
        "limit": 10000,
        "adjustment": "raw",
    }
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            r = client.get(url, headers=headers, params=params)
            r.raise_for_status()
            bars = r.json().get("bars", [])
        if not bars:
            return None
        df = pd.DataFrame(bars).rename(
            columns={"t": "timestamp", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp")[["open", "high", "low", "close", "volume"]]
        return df
    except Exception as e:
        logger.warning("alpaca bars failed for %s: %s", symbol, e)
        return None
