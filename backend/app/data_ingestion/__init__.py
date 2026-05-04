"""Alias package — re-exports the canonical `app.data` surface."""
from app.data import get_realtime_quote, get_ohlcv  # noqa: F401
from app.data import nse_india, global_equity, alpaca_data  # noqa: F401
from app.data.models import Quote, Candle  # noqa: F401
