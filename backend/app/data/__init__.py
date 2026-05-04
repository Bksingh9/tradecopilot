"""Read-only market data layer.

Public surface (broker/exchange-agnostic):
    - get_realtime_quote(symbol, exchange_hint=None) -> Quote
    - get_ohlcv(symbol, start, end, timeframe="1d") -> pd.DataFrame
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from app.data import alpaca_data, global_equity, nse_india
from app.data.models import Quote


def get_realtime_quote(symbol: str, exchange_hint: Optional[str] = None) -> Quote:
    """Pick a data source based on a hint or simple heuristics.

    exchange_hint: 'NSE' | 'BSE' | 'US' | None
    """
    sym = symbol.strip().upper()
    hint = (exchange_hint or "").upper()
    if hint in {"NSE", "BSE"} or sym.endswith(".NS") or sym.endswith(".BO"):
        return nse_india.get_quote(sym, exchange_hint=hint or None)
    if hint == "US":
        return alpaca_data.get_quote(sym) or global_equity.get_quote(sym)
    # Heuristic fallback: try US via Alpaca, then yfinance
    return alpaca_data.get_quote(sym) or global_equity.get_quote(sym)


def get_ohlcv(
    symbol: str,
    start: datetime,
    end: datetime,
    timeframe: str = "1d",
    exchange_hint: Optional[str] = None,
) -> pd.DataFrame:
    """Unified OHLCV loader. Returns columns: open, high, low, close, volume (UTC index)."""
    sym = symbol.strip().upper()
    hint = (exchange_hint or "").upper()
    if hint in {"NSE", "BSE"} or sym.endswith(".NS") or sym.endswith(".BO"):
        return nse_india.get_ohlcv(sym, start, end, timeframe)
    if hint == "US":
        df = alpaca_data.get_ohlcv(sym, start, end, timeframe)
        if df is not None and not df.empty:
            return df
        return global_equity.get_ohlcv(sym, start, end, timeframe)
    return global_equity.get_ohlcv(sym, start, end, timeframe)
