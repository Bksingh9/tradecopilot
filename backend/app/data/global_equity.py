"""Global / US equity helpers via yfinance — used when Alpaca is not connected."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from app.common.exceptions import DataSourceError
from app.common.logging import get_logger
from app.data.models import Quote

logger = get_logger(__name__)


def get_quote(symbol: str) -> Quote:
    try:
        import yfinance as yf

        t = yf.Ticker(symbol)
        info = t.fast_info
        ltp = float(getattr(info, "last_price", 0.0) or 0.0)
        if ltp <= 0:
            raise DataSourceError(f"No price for {symbol}")
        return Quote(
            symbol=symbol,
            exchange="US",
            ltp=ltp,
            open=float(getattr(info, "open", 0.0) or 0.0) or None,
            high=float(getattr(info, "day_high", 0.0) or 0.0) or None,
            low=float(getattr(info, "day_low", 0.0) or 0.0) or None,
            prev_close=float(getattr(info, "previous_close", 0.0) or 0.0) or None,
            volume=int(getattr(info, "last_volume", 0) or 0) or None,
            currency="USD",
            timestamp=datetime.utcnow(),
            source="yfinance",
        )
    except Exception as e:
        raise DataSourceError(f"yfinance quote failed for {symbol}: {e}") from e


def get_ohlcv(symbol: str, start: datetime, end: datetime, timeframe: str = "1d") -> pd.DataFrame:
    import yfinance as yf

    interval_map = {"1d": "1d", "1h": "60m", "15m": "15m", "5m": "5m", "1m": "1m"}
    interval = interval_map.get(timeframe, "1d")
    df = yf.download(symbol, start=start, end=end, interval=interval, progress=False, auto_adjust=False)
    if df.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    return df


def get_quote_safe(symbol: str) -> Optional[Quote]:
    try:
        return get_quote(symbol)
    except DataSourceError:
        return None
