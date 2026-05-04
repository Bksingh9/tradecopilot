"""NSE/BSE realtime quotes via 0xramm Indian Stock Market API + yfinance fallback for OHLCV.

NOTE: 0xramm's hosted API is community-maintained; treat all data as best-effort, never
authoritative. Always log errors but never log secrets.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx
import pandas as pd

from app.common.exceptions import DataSourceError
from app.common.logging import get_logger
from app.config import settings
from app.data.models import Quote

logger = get_logger(__name__)

_TIMEOUT = httpx.Timeout(8.0, connect=4.0)


def _yf_symbol(symbol: str, exchange_hint: Optional[str] = None) -> str:
    """Map a bare NSE ticker like RELIANCE → RELIANCE.NS for yfinance."""
    s = symbol.upper()
    if s.endswith(".NS") or s.endswith(".BO"):
        return s
    if (exchange_hint or "").upper() == "BSE":
        return f"{s}.BO"
    return f"{s}.NS"


def get_quote(symbol: str, exchange_hint: Optional[str] = None) -> Quote:
    """Fetch realtime quote from 0xramm; on any failure fall back to yfinance."""
    bare = symbol.upper().split(".")[0]
    base = settings.nse_api_base.rstrip("/")
    url = f"{base}/api/equity/{bare}"
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            r = client.get(url)
            r.raise_for_status()
            data = r.json()
        # 0xramm shape varies; defensively pull common fields
        price_info = data.get("priceInfo") or data.get("data") or {}
        ltp = float(price_info.get("lastPrice") or price_info.get("ltp") or 0.0)
        if ltp <= 0:
            raise DataSourceError("0xramm returned no price")
        return Quote(
            symbol=bare,
            exchange="BSE" if (exchange_hint or "").upper() == "BSE" else "NSE",
            ltp=ltp,
            open=_f(price_info.get("open")),
            high=_f(price_info.get("intraDayHighLow", {}).get("max") or price_info.get("dayHigh")),
            low=_f(price_info.get("intraDayHighLow", {}).get("min") or price_info.get("dayLow")),
            prev_close=_f(price_info.get("previousClose")),
            volume=_i(price_info.get("totalTradedVolume")),
            currency="INR",
            timestamp=datetime.utcnow(),
            source="0xramm",
        )
    except Exception as e:
        logger.warning("0xramm quote failed for %s: %s — falling back to yfinance", bare, e)

    # yfinance fallback
    try:
        import yfinance as yf

        t = yf.Ticker(_yf_symbol(symbol, exchange_hint))
        info = t.fast_info
        ltp = float(getattr(info, "last_price", 0.0) or 0.0)
        if ltp <= 0:
            raise DataSourceError(f"No price for {symbol}")
        return Quote(
            symbol=bare,
            exchange="BSE" if (exchange_hint or "").upper() == "BSE" else "NSE",
            ltp=ltp,
            open=float(getattr(info, "open", 0.0) or 0.0) or None,
            high=float(getattr(info, "day_high", 0.0) or 0.0) or None,
            low=float(getattr(info, "day_low", 0.0) or 0.0) or None,
            prev_close=float(getattr(info, "previous_close", 0.0) or 0.0) or None,
            volume=int(getattr(info, "last_volume", 0) or 0) or None,
            currency="INR",
            timestamp=datetime.utcnow(),
            source="yfinance",
        )
    except Exception as e:
        raise DataSourceError(f"All data sources failed for {symbol}: {e}") from e


def get_ohlcv(symbol: str, start: datetime, end: datetime, timeframe: str = "1d") -> pd.DataFrame:
    """Historical OHLCV via yfinance (daily/intraday). Index is tz-aware UTC."""
    import yfinance as yf

    interval_map = {"1d": "1d", "1h": "60m", "15m": "15m", "5m": "5m", "1m": "1m"}
    interval = interval_map.get(timeframe, "1d")
    df = yf.download(
        _yf_symbol(symbol),
        start=start,
        end=end,
        interval=interval,
        progress=False,
        auto_adjust=False,
    )
    if df.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    return df


def _f(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except Exception:
        return None


def _i(v) -> Optional[int]:
    try:
        return int(v) if v is not None else None
    except Exception:
        return None
