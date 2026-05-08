"""Read-only market data layer.

Public surface (broker/exchange-agnostic):
    - get_realtime_quote(symbol, exchange_hint=None) -> Quote
    - get_ohlcv(symbol, start, end, timeframe="1d") -> pd.DataFrame

Includes a tiny in-memory TTL cache around upstream sources so a flaky
yfinance/NSE response doesn't take down the dashboard or paper-fill flow.
On a paid plan we'd swap this for Redis; for now process-local is fine since
Render free tier runs a single replica anyway.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

import pandas as pd

from app.common.logging import get_logger
from app.data import alpaca_data, global_equity, nse_india
from app.data.models import Quote

logger = get_logger(__name__)

# (key) -> (epoch_seconds, Quote_or_DataFrame)
_QUOTE_CACHE: dict[tuple[str, str], tuple[float, Quote]] = {}
_QUOTE_TTL_SECONDS = 30
_QUOTE_STALE_TTL_SECONDS = 600  # serve stale-but-real on upstream failure

_OHLCV_CACHE: dict[tuple[str, str, str], tuple[float, pd.DataFrame]] = {}
_OHLCV_TTL_SECONDS = 300


def _fetch_quote_uncached(sym: str, hint: str) -> Quote:
    if hint in {"NSE", "BSE"} or sym.endswith(".NS") or sym.endswith(".BO"):
        return nse_india.get_quote(sym, exchange_hint=hint or None)
    if hint == "US":
        return alpaca_data.get_quote(sym) or global_equity.get_quote(sym)
    return alpaca_data.get_quote(sym) or global_equity.get_quote(sym)


def get_realtime_quote(symbol: str, exchange_hint: Optional[str] = None) -> Quote:
    """Realtime quote with 30s cache + 10min stale fallback on upstream failure.

    exchange_hint: 'NSE' | 'BSE' | 'US' | None
    """
    sym = symbol.strip().upper()
    hint = (exchange_hint or "").upper()
    key = (sym, hint)
    now = time.time()

    cached = _QUOTE_CACHE.get(key)
    if cached and now - cached[0] < _QUOTE_TTL_SECONDS:
        return cached[1]

    try:
        q = _fetch_quote_uncached(sym, hint)
        if q and q.ltp is not None:
            _QUOTE_CACHE[key] = (now, q)
            return q
        # Empty/None response: try stale before giving up
        if cached and now - cached[0] < _QUOTE_STALE_TTL_SECONDS:
            logger.info("quote stale-served %s (upstream returned None)", sym)
            return cached[1]
        # No stale, return whatever we got (may be None Quote)
        return q
    except Exception as e:
        if cached and now - cached[0] < _QUOTE_STALE_TTL_SECONDS:
            logger.warning("quote stale-served %s on upstream error: %s", sym, e)
            return cached[1]
        raise


def get_ohlcv(
    symbol: str,
    start: datetime,
    end: datetime,
    timeframe: str = "1d",
    exchange_hint: Optional[str] = None,
) -> pd.DataFrame:
    """Unified OHLCV loader with 5min cache. Returns columns: open, high, low, close, volume (UTC index)."""
    sym = symbol.strip().upper()
    hint = (exchange_hint or "").upper()

    # Cache key uses the rounded date range so adjacent requests reuse the same fetch.
    key = (sym, hint, f"{timeframe}:{start.date().isoformat()}:{end.date().isoformat()}")
    now = time.time()
    cached = _OHLCV_CACHE.get(key)
    if cached and now - cached[0] < _OHLCV_TTL_SECONDS:
        return cached[1]

    try:
        if hint in {"NSE", "BSE"} or sym.endswith(".NS") or sym.endswith(".BO"):
            df = nse_india.get_ohlcv(sym, start, end, timeframe)
        elif hint == "US":
            df = alpaca_data.get_ohlcv(sym, start, end, timeframe)
            if df is None or df.empty:
                df = global_equity.get_ohlcv(sym, start, end, timeframe)
        else:
            df = global_equity.get_ohlcv(sym, start, end, timeframe)

        if df is not None and not df.empty:
            _OHLCV_CACHE[key] = (now, df)
        return df
    except Exception as e:
        # Serve stale-but-real on upstream failure.
        if cached:
            logger.warning("ohlcv stale-served %s on upstream error: %s", sym, e)
            return cached[1]
        raise
