"""Analyst agent — turns OHLCV into AnalystSignal."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from app.agents.features import compute_features, directional_probability, news_sentiment_stub
from app.agents.models import AnalystSignal
from app.common.logging import get_logger
from app.data import get_ohlcv

logger = get_logger(__name__)


class AnalystAgent:
    """Reads recent bars, builds features, returns a directional view + regime hint."""

    def __init__(self, lookback_days: int = 200) -> None:
        self.lookback_days = lookback_days

    def assess(
        self,
        symbol: str,
        timeframe: str = "1d",
        exchange_hint: Optional[str] = None,
    ) -> AnalystSignal:
        end = datetime.utcnow()
        start = end - timedelta(days=self.lookback_days)
        df = get_ohlcv(symbol, start, end, timeframe, exchange_hint=exchange_hint)
        feats = compute_features(df) if isinstance(df, pd.DataFrame) else {}
        p_up = directional_probability(feats)
        regime = self._regime_hint(feats)
        sent = news_sentiment_stub(symbol)
        return AnalystSignal(
            symbol=symbol.upper(),
            exchange=(exchange_hint or "").upper() or None,
            timeframe=timeframe,
            timestamp=end,
            features=feats,
            p_up=p_up,
            regime=regime,
            sentiment=float(sent["sentiment"]),
            notes=[
                f"features over last ~{self.lookback_days}d",
                "directional probability is a transparent stub (see app.agents.features)",
            ],
        )

    @staticmethod
    def _regime_hint(feats: dict) -> Optional[str]:
        if not feats:
            return None
        atr = feats.get("atr_pct", 0.0)
        ret20 = feats.get("ret_20", 0.0)
        ema_fast = feats.get("ema_fast", 0.0)
        ema_slow = feats.get("ema_slow", 0.0)
        if atr >= 5.0:
            return "crash" if ret20 <= -0.10 else "high_vol"
        if ret20 >= 0.05 and ema_fast > ema_slow:
            return "bull"
        if ret20 <= -0.05 and ema_fast < ema_slow:
            return "bear"
        if atr <= 1.0:
            return "low_vol"
        return "range"
